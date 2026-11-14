#!/usr/bin/env python3
"""Check the consolidated dashboard: links, sources, and table integrity.

Rules enforced:
  1. Every internal href resolves to a file that exists.
  2. Every in-page anchor target exists.
  3. Every page links to every other page (navigation completeness).
  4. Every table row carries at least one link to an official external source.
  5. Every page carries the NBA.com attribution required by Terms of Use section 9(i).
  6. No page contains a stray unescaped placeholder.

Run:  python3 final/check_site.py
"""
from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dashboard"

PAGES = [
    "index.html", "executive-summary.html", "methodology.html", "lines.html",
    "projections.html", "strategies.html", "validation.html", "correlations.html",
    "injuries.html", "gameflow.html", "data.html", "questions.html",
    "suggestions.html", "flagged.html", "repo-review.html", "sources.html",
    "archives.html",
]

OFFICIAL_HOSTS = (
    "www.nba.com", "official.nba.com", "ak-static.cms.nba.com", "cdn.nba.com",
    "github.com", "kansspelautoriteit.nl",
)


class Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []
        self._cur_idx = 0
        self.ids: set[str] = set()
        self.rows: list[list[str]] = []
        self.header_rows: set[int] = set()
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            if self._cell is not None:
                self._cell.append(a["href"])
        if tag == "tr":
            self._row = []
            self._cur_idx = len(self.rows)
        if tag == "th":
            self.header_rows.add(len(self.rows))
        if tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append(" ".join(self._cell))
            self._cell = None
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def main() -> int:
    errors: list[str] = []
    total_rows = 0
    total_links = 0

    for name in PAGES:
        path = BASE / name
        if not path.exists():
            errors.append("{}: missing".format(name))
            continue
        html = path.read_text(encoding="utf-8")
        p = Collect()
        p.feed(html)

        # 1 & 2: links
        for href in p.hrefs:
            total_links += 1
            if href.startswith("#"):
                if href[1:] not in p.ids:
                    errors.append("{}: broken anchor {}".format(name, href))
            elif href.startswith(("http://", "https://", "mailto:")):
                continue
            else:
                target = href.split("#")[0]
                if target and not (BASE / target).exists():
                    errors.append("{}: broken internal link {}".format(name, href))

        # 3: navigation completeness
        for other in PAGES:
            if other != name and other not in p.hrefs:
                errors.append("{}: nav missing link to {}".format(name, other))

        # 4: every non-header table row carries an official external source link
        for i, row in enumerate(p.rows):
            if not row or i in p.header_rows:
                continue
            total_rows += 1
            joined = " ".join(row)
            if not any("http://" in c or "https://" in c for c in row):
                errors.append("{}: table row {} has no source link: {!r}".format(
                    name, i + 1, joined[:90]))

        # 5: attribution
        if "nba.com/stats" not in html:
            errors.append("{}: missing NBA.com attribution".format(name))

        # 6: placeholders
        for bad in ("{", "None", "nan"):
            if bad == "{" and re.search(r"\{[a-z_]+\}", html):
                errors.append("{}: unresolved format placeholder".format(name))
        if ">None<" in html:
            errors.append("{}: literal None rendered".format(name))

    # official-source sanity: every external link should be to a known host
    hosts: set[str] = set()
    for name in PAGES:
        html = (BASE / name).read_text(encoding="utf-8")
        for m in re.finditer(r'href="https?://([^/"]+)', html):
            hosts.add(m.group(1))
    unknown = sorted(h for h in hosts if not any(h == o or h.endswith("." + o)
                                                 for o in OFFICIAL_HOSTS))
    if unknown:
        errors.append("unexpected external hosts: {}".format(", ".join(unknown)))

    print("NBA3 site check")
    print("=" * 60)
    print("pages            : {} (under dashboard/)".format(len(PAGES)))
    print("links checked    : {}".format(total_links))
    print("table rows       : {}".format(total_rows))
    print("external hosts   : {}".format(len(hosts)))
    print("-" * 60)
    if errors:
        for e in errors[:60]:
            print("  ERROR " + e)
        if len(errors) > 60:
            print("  ... {} more".format(len(errors) - 60))
        print("FAILED: {} error(s)".format(len(errors)))
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
