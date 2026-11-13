"""Verification gate for the data files and the built site (standard library only).

Exit code 0 only if every check passes. Run after pipeline/build_site.py.

Checks
1. Data: every row that carries a source link has an https link on an allowed official host.
2. Data: injury rows with a blank team, matchup, date, time or reason carry a flag ID that exists in flags.csv.
3. Data: no correlation value is filled in (none has been measured), and no strategy is marked PASS.
4. Site: every internal link resolves to a built file.
5. Site: every external link is https and on an allowed host.
6. Site: every table body row contains at least one allowed source link.
7. Site: every blank cell is marked unverified.
"""

from __future__ import annotations

import csv
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "research"  # generated research pages, published under /research/

ALLOWED_HOSTS = {
    "nba.com", "www.nba.com", "official.nba.com", "ak-static.cms.nba.com", "cdn.nba.com", "stats.nba.com",
    "kansspelautoriteit.nl", "www.kansspelautoriteit.nl",
    "wetten.overheid.nl",
    "itl.nist.gov", "www.itl.nist.gov",
    "docs.github.com", "github.com", "api.github.com",
    "gokstop.nl", "www.gokstop.nl",
}

# (file, column) pairs that must hold a source link on every row
SOURCE_COLUMNS = {
    "sources.csv": ["url"],
    "slates.csv": ["nba_game_page", "source_url"],
    "injuries_2026-11-13_1100AM.csv": ["source_url"],
    "strategies.csv": ["source_url"],
    "gates.csv": ["method_reference_url"],
    "correlations.csv": ["source_url"],
    "gameflow.csv": ["definition_source_url"],
    "repo_review.csv": ["evidence_url"],
    "questions.csv": ["evidence_url"],
    "suggestions.csv": ["evidence_url"],
    "flags.csv": ["source_url"],
    "requirements.csv": ["evidence_url"],
}


def url_problem(url: str) -> str | None:
    """Return a description of the problem with a source URL, or None if acceptable."""
    if not url:
        return "missing"
    p = urlparse(url)
    if p.scheme != "https":
        return f"not https ({url})"
    if p.hostname not in ALLOWED_HOSTS:
        return f"host not on allow-list ({p.hostname})"
    return None


def read_csv(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_data() -> list[str]:
    errors: list[str] = []

    for fname, cols in SOURCE_COLUMNS.items():
        rows = read_csv(fname)
        for i, row in enumerate(rows, start=2):
            for col in cols:
                problem = url_problem(row.get(col, ""))
                if problem:
                    errors.append(f"{fname} line {i} column {col}: {problem}")

    flags = {f["flag_id"] for f in read_csv("flags.csv")}
    for i, row in enumerate(read_csv("injuries_2026-11-13_1100AM.csv"), start=2):
        ids = set(row["flag_ids"].split())
        unknown = ids - flags
        if unknown:
            errors.append(f"injuries line {i}: unknown flag IDs {sorted(unknown)}")
        if row["row_type"] == "player":
            missing = [c for c in ("game_date", "game_time_et_as_listed", "matchup", "team", "reason")
                       if not row[c]]
            if missing and not ids:
                errors.append(f"injuries line {i}: blank {missing} without a flag")
        elif row["row_type"] == "team_status":
            if "F11" not in ids:
                errors.append(f"injuries line {i}: team_status row without F11")
        else:
            errors.append(f"injuries line {i}: unknown row_type {row['row_type']}")

    for row in read_csv("correlations.csv"):
        if row["correlation_value"].strip():
            errors.append(f"correlations {row['pair_id']}: value filled without measured data")

    for row in read_csv("strategies.csv"):
        if row["gate_status"].upper() == "PASS":
            errors.append(f"strategies {row['strategy_id']}: PASS without approved gates and data")

    return errors


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.in_tbody = False
        self.rows: list[dict] = []  # each body row: {'links': [...], 'blank_cells': n, 'blank_unverified': n}
        self._row: dict | None = None
        self._cell_blank = False
        self._cell_text: list[str] = []
        self.blank_cells = 0
        self.blank_unverified = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            if self._row is not None:
                self._row["links"].append(a["href"])
        if tag == "tbody":
            self.in_tbody = True
        if tag == "tr" and self.in_tbody:
            self._row = {"links": [], "cells": 0}
        if tag == "td" and self._row is not None:
            self._row["cells"] += 1
            self._cell_blank = "blank" in (a.get("class") or "")
            self._cell_text = []

    def handle_data(self, data):
        if self._row is not None and self._cell_blank:
            self._cell_text.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None and self._cell_blank:
            self.blank_cells += 1
            text = "".join(self._cell_text)
            # the blank marker must be present: the cell itself reads "unverified"
            self._cell_blank = False
        if tag == "tbody":
            self.in_tbody = False
        if tag == "tr" and self._row is not None and self.in_tbody:
            self.rows.append(self._row)
            self._row = None


def check_site() -> list[str]:
    errors: list[str] = []
    if not SITE.exists():
        return ["research/ not found; run pipeline/build_site.py first"]
    pages = sorted(SITE.glob("*.html"))
    if not pages:
        return ["no generated HTML pages in research/"]
    names = {p.name for p in pages}
    for page in pages:
        parser = SiteParser()
        text = page.read_text(encoding="utf-8")
        parser.feed(text)
        for href in parser.hrefs:
            p = urlparse(href)
            if p.scheme in ("http", "https"):
                problem = url_problem(href)
                if problem:
                    errors.append(f"{page.name}: external link {problem}")
            elif p.scheme == "" and p.path and not p.path.startswith("#"):
                if p.path not in names and p.path != "style.css":
                    errors.append(f"{page.name}: broken internal link {href}")
            elif p.fragment and not p.path:
                if p.fragment not in parser.ids:
                    errors.append(f"{page.name}: broken anchor {href}")
        for i, row in enumerate(parser.rows, start=1):
            ext = [h for h in row["links"] if url_problem(h) is None]
            if not ext:
                errors.append(f"{page.name}: table row {i} has no allowed source link")
        blank_marks = text.count('class="blank"')
        unverified_marks = text.count('<span class="flag">unverified')
        if blank_marks > unverified_marks:
            errors.append(f"{page.name}: {blank_marks - unverified_marks} blank cells without an unverified marker")
    return errors


def main() -> int:
    errors = check_data() + check_site()
    if errors:
        print("VERIFY FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("VERIFY OK: data rules and built-site checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
