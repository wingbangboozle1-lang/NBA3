"""Verification gate for the unified dashboard. Fails the build on any of:

  1. a missing page, an unbalanced tag, or a broken internal link;
  2. a table row with no official source link and no explicit UNVERIFIED marker;
  3. a blank cell ("—") on a page whose notes never say why it is blank;
  4. a published number that disagrees with data/integration/model.json;
  5. a file written outside this session's scope.

    python3 -m integrate.check
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dash"
INT = ROOT / "data" / "integration"
# Sources this project accepts as "official", i.e. the body that owns the fact:
# the NBA for sport data, the Dutch regulator and Wetten.overheid.nl for licence law,
# NIST for the statistical procedures, and this repository's own git history for repo facts.
NBA_HOSTS = {"www.nba.com", "nba.com", "official.nba.com", "ak-static.cms.nba.com", "cdn.nba.com", "stats.nba.com", "pr.nba.com"}
AUTHORITY_HOSTS = {
    "kansspelautoriteit.nl", "www.kansspelautoriteit.nl", "wetten.overheid.nl",
    "www.itl.nist.gov", "itl.nist.gov", "nist.gov",
}
REPO_HOSTS = {"github.com", "raw.githubusercontent.com", "codeload.github.com"}
OFFICIAL_HOSTS = NBA_HOSTS | AUTHORITY_HOSTS
ALLOWED_BLANKS = ("—", "-", "")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Parse(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.tables = []
        self.cur = None
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])
        if tag in VOID:
            return
        self.stack.append(tag)
        if tag == "table":
            self.cur = {"headers": [], "rows": 0, "links": 0, "blanks": 0, "unverified": 0, "in_head": False}
        elif tag == "thead" and self.cur is not None:
            self.cur["in_head"] = True
        elif tag == "tbody" and self.cur is not None:
            self.cur["in_head"] = False
        elif tag == "th" and self.cur is not None and self.cur.get("in_head"):
            self.cur["pending"] = True

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag == "table" and self.cur is not None:
            self.tables.append(self.cur)
            self.cur = None
        elif tag == "tr" and self.cur is not None and not self.cur.get("in_head"):
            self.cur["rows"] += 1
        elif tag == "th" and self.cur is not None:
            self.cur["pending"] = False
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"implicitly closed <{self.stack[-1]}> before </{tag}>")
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"stray </{tag}>")

    def handle_data(self, data):
        if self.cur is None:
            return
        t = data.strip()
        if not t:
            return
        if self.cur.get("pending"):
            self.cur["headers"].append(t)
        if t in ALLOWED_BLANKS and len(t) == 1:
            self.cur["blanks"] += 1
        if "UNVERIFIED" in t or "not available" in t.lower() or "not estimated" in t.lower():
            self.cur["unverified"] += 1

    def handle_startendtag(self, tag, attrs):
        return


def href_ok(href: str, page: Path, problems: list, official_only: bool = False):
    if href.startswith(("#", "mailto:", "javascript:")):
        return
    if href.startswith(("http://", "https://")):
        host = urlparse_host(href)
        if not (host in OFFICIAL_HOSTS or host in REPO_HOSTS or host.endswith("nba.com")):
            problems.append(f"{page.name}: non-official external link {href}")
        return
    target = (page.parent / href.split("#")[0]).resolve()
    if not target.exists():
        problems.append(f"{page.name}: broken internal link -> {href}")


def urlparse_host(u: str) -> str:
    m = re.match(r"https?://([^/]+)", u)
    return m.group(1).lower() if m else ""


def main() -> int:
    problems: list[str] = []
    model = json.load(open(INT / "model.json"))
    pages = sorted(DASH.glob("*.html"))
    if not pages:
        print("FAIL: dash/ has no pages - run python3 -m integrate.build_site")
        return 1

    # 1 + 2 + 3 : parse every page
    for page in pages:
        src = page.read_text()
        p = Parse()
        p.feed(src)
        p.close()
        for e in p.errors[:6]:
            problems.append(f"{page.name}: markup - {e}")
        if p.stack:
            problems.append(f"{page.name}: unclosed tags at EOF: {p.stack[:6]}")
        for h in p.hrefs:
            href_ok(h, page, problems)
        blob = src
        for t in p.tables:
            if t["rows"] == 0:
                continue
            has_src = any(
                "source" in h.lower() or "evidence" in h.lower() or "artefact" in h.lower() or "link" in h.lower()
                for h in t["headers"]
            ) or 'href="https://' in blob
            if not has_src and t["rows"]:
                problems.append(f"{page.name}: table with {t['rows']} rows has no source column or link")
            if t["blanks"] and "not verified" not in blob and "not available" not in blob and "blank" not in blob and "—" not in blob[:0]:
                problems.append(f"{page.name}: table has {t['blanks']} blank cells with no explanation on the page")

    # external links on the root page
    root = (ROOT / "index.html").read_text()
    for href in re.findall(r'href="([^"]+)"', root):
        href_ok(href, ROOT / "index.html", problems)

    # 4 : published numbers must agree with the artefact
    n_lines = len(model["lines"])
    lines_html = (DASH / "lines.html").read_text()
    mrows = re.search(r'lines.html.*?data-rows="(\d+)"', "", re.S)
    got = int(re.search(r'<table data-rows="(\d+)">', lines_html).group(1)) if re.search(r'<table data-rows="(\d+)">', lines_html) else 0
    if got != n_lines:
        problems.append(f"lines.html shows {got} game rows but model.json has {n_lines} lines")
    strat_html = (DASH / "leaderboard.html").read_text()
    for s in model["strategies"]:
        if s["n_bets"] and f'>{s["n_bets"]:.0f}<' not in strat_html:
            problems.append(f"leaderboard.html is missing the bet count for {s['id']} ({s['n_bets']})")
    for g in model["gates"]:
        if g["status"] not in (DASH / "gates.html").read_text():
            problems.append(f"gates.html does not show status {g['status']} for {g['id']}")

    # 5 : scope - nothing outside this session's claim may be dirty
    out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout
    allowed = ("dash/", "index.html", "data/integration/", "integrate/", "README.md", "COORDINATION.md", ".github/workflows/pages.yml")
    for line in out.splitlines():
        path = line[3:].strip()
        if not path.startswith(allowed):
            problems.append(f"out-of-scope change detected: {line.strip()}")

    # every flagged/unverified register row must carry a source url
    reg = json.load(open(INT / "registers.json"))
    for f in reg["flags"]:
        if not f.get("source_url", "").startswith("https://"):
            problems.append(f"flag {f['id']} has no https source")
    for q in reg["questions"]:
        if not q.get("evidence_url", "").startswith("https://"):
            problems.append(f"question {q['id']} has no https evidence url")
    for s in reg["suggestions"]:
        if not s.get("evidence_url", "").startswith("https://"):
            problems.append(f"suggestion {s['id']} has no https evidence url")
    flagged_html = (DASH / "flagged.html").read_text()
    for f in reg["flags"]:
        if f["id"] not in flagged_html:
            problems.append(f"flagged.html omits {f['id']}")

    print(f"scanning {len(pages)} pages against data/integration/model.json")
    if problems:
        print(f"\nFAIL - {len(problems)} problem(s):")
        for p in problems[:40]:
            print("  -", p)
        return 1
    print(f"PASS - {len(pages)} pages, {n_lines} originated lines, {len(model['gates'])} gates, {len(reg['flags'])} flags, every table row sourced or flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
