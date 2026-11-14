#!/usr/bin/env python3
"""Mechanical scan: does every published table row carry a direct official link?

Reproduces and extends the check recorded as finding R-13 by the integration
session arena/2e50a71a.  It walks every HTML file in the repository, counts the
rows in every <tbody> and reports how many of them contain a link to an
official host (nba.com, official.nba.com, ak-static.cms.nba.com, cdn.nba.com,
data.nba.com, a.data.nba.com, kansspelautoriteit.nl, wetten.overheid.nl,
gokstop.nl) or to the GitHub repository itself.

This is a screen, not a judgement: a row can be a method description or a
repository fact that has no official NBA source.  It tells us where the strict
"every row carries an official link" rule is not met, so those rows can be
labelled or fixed.

Usage: python3 scripts/scan_table_sources.py [--json]
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OFFICIAL_HOSTS = (
    "nba.com", "official.nba.com", "ak-static.cms.nba.com", "cdn.nba.com",
    "data.nba.com", "a.data.nba.com", "kansspelautoriteit.nl",
    "wetten.overheid.nl", "gokstop.nl", "github.com", "itl.nist.gov",
)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache"}


class RowScanner(HTMLParser):
    """Collect every <tr> inside a <tbody> with the hrefs it contains."""

    def __init__(self):
        super().__init__()
        self.in_body = 0
        self.in_row = 0
        self.rows = []
        self._hrefs = []
        self._text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self.in_body += 1
        elif tag == "tr":
            self.in_row += 1
            self._hrefs = []
            self._text = []
        elif tag == "a" and self.in_row:
            href = a.get("href", "")
            if href:
                self._hrefs.append(href)

    def handle_endtag(self, tag):
        if tag == "tbody" and self.in_body:
            self.in_body -= 1
        elif tag == "tr" and self.in_row:
            self.in_row -= 1
            # only rows inside a <tbody> are counted
            if self.in_body:
                self.rows.append((list(self._hrefs), " ".join(self._text).strip()))

    def handle_data(self, data):
        if self.in_row:
            self._text.append(data.strip())


def is_official(href):
    if not href.startswith("https://"):
        return False
    host = href.split("/")[2].lower()
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def scan():
    per_folder = {}
    files = 0
    total_rows = 0
    without = 0
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            files += 1
            p = RowScanner()
            p.feed(text)
            folder = rel.split(os.sep)[0] if os.sep in rel else "."
            st = per_folder.setdefault(folder, {"files": 0, "rows": 0, "without_official_link": 0})
            st["files"] += 1
            st["rows"] += len(p.rows)
            total_rows += len(p.rows)
            for hrefs, text_ in p.rows:
                if not any(is_official(h) for h in hrefs):
                    without += 1
                    st["without_official_link"] += 1
                    offenders.append({"file": rel, "row": text_[:120]})
    return {
        "html_files": files,
        "table_rows": total_rows,
        "rows_without_official_link": without,
        "rows_with_official_link": total_rows - without,
        "per_folder": per_folder,
        "offenders": offenders,
    }


def main():
    result = scan()
    if "--json" in sys.argv:
        print(json.dumps(result, indent=1))
        return 0
    print(f"HTML files scanned: {result['html_files']}")
    print(f"table-body rows:   {result['table_rows']}")
    print(f"with an official link:    {result['rows_with_official_link']}")
    print(f"without an official link: {result['rows_without_official_link']}")
    print("\nby folder (files, rows, rows without an official link):")
    for folder, st in sorted(result["per_folder"].items()):
        print(f"  {folder:12s} {st['files']:4d} files {st['rows']:6d} rows "
              f"{st['without_official_link']:5d} without")
    if "--list" in sys.argv:
        print("\nrows without an official link:")
        for o in result["offenders"]:
            print(f"  {o['file']}: {o['row']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
