"""Checks the NBA3 static site.

1. Every data row points to a source ID that exists and has an https:// URL.
2. Every internal href/src in docs/*.html resolves to a file in docs/.
3. Every data-view / data-count attribute is known to the renderer.
Exit code 0 = pass, 1 = failures (printed).
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
failures = []


def fail(msg):
    failures.append(msg)


def load():
    with open(os.path.join(ROOT, "data", "data.json"), encoding="utf-8") as f:
        return json.load(f)


def check_data(d):
    sources = d["sources"]
    for sid, s in sources.items():
        if not s.get("url", "").startswith("https://"):
            fail(f"source {sid} has no https URL")
        for key in ("title", "org", "method", "verified_on", "status"):
            if not s.get(key):
                fail(f"source {sid} missing field {key}")

    def src_ok(where, sid):
        if sid not in sources:
            fail(f"{where}: unknown source id {sid!r}")

    for r in d["injury_report"]["rows"]:
        if len(r) != 7:
            fail(f"injury row has {len(r)} cells: {r[:4]}")
        src_ok("injury row " + " ".join(map(str, r[:4])), r[-1])
    for r in d["slate"]["rows"]:
        if len(r) != 9:
            fail(f"slate row has {len(r)} cells: {r[:4]}")
        src_ok("slate row " + " ".join(map(str, r[:4])), r[-1])
    for r in d["rules"]["rows"]:
        if len(r) != 3:
            fail(f"rule row has {len(r)} cells: {r[:1]}")
        src_ok("rule " + r[0], r[-1])
    for q in d["questions"]:
        for sid in re.findall(r"\bS\d\b", q.get("sources", "")):
            src_ok("question " + q["id"], sid)
    for f in d["flags"]:
        for sid in re.findall(r"\bS\d\b", f.get("source", "")):
            src_ok("flag " + f["id"], sid)
    ids = [f["id"] for f in d["flags"]]
    if len(ids) != len(set(ids)):
        fail("duplicate flag ids")
    return len(d["injury_report"]["rows"]), len(d["slate"]["rows"]), len(d["rules"]["rows"])


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.views = []
        self.counts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.refs.append(a["href"])
        if tag == "link" and a.get("href"):
            self.refs.append(a["href"])
        if tag == "script" and a.get("src"):
            self.refs.append(a["src"])
        if a.get("data-view"):
            self.views.append(a["data-view"])
        if a.get("data-count"):
            self.counts.append(a["data-count"])


KNOWN_VIEWS = {"injuries", "slate", "rules", "questions", "gates", "suggestions", "sources", "flags"}
KNOWN_COUNTS = {"injury_rows", "slate_games", "rules", "questions", "open_questions", "suggestions",
                "flags", "sources", "strategies", "gates"}


def check_html():
    pages = sorted(p for p in os.listdir(ROOT) if p.endswith(".html"))
    if not pages:
        fail("no HTML pages found")
    for p in pages:
        parser = Links()
        with open(os.path.join(ROOT, p), encoding="utf-8") as f:
            parser.feed(f.read())
        for ref in parser.refs:
            if ref.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = ref.split("#")[0].split("?")[0]
            if target and not os.path.exists(os.path.join(ROOT, target)):
                fail(f"{p}: broken internal link {ref}")
        for v in parser.views:
            if v not in KNOWN_VIEWS:
                fail(f"{p}: unknown data-view {v}")
        for c in parser.counts:
            if c not in KNOWN_COUNTS:
                fail(f"{p}: unknown data-count {c}")
    return pages


def main():
    d = load()
    n_inj, n_slate, n_rules = check_data(d)
    pages = check_html()
    root_index = os.path.join(ROOT, "..", "index.html")
    if not os.path.exists(root_index):
        fail("root index.html (redirect to docs/) missing")
    elif "docs/index.html" not in open(root_index, encoding="utf-8").read():
        fail("root index.html does not redirect to docs/index.html")
    if failures:
        print("FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print(f"PASS: {len(pages)} pages, {n_inj} injury rows, {n_slate} slate rows, {n_rules} rule rows, "
          f"{len(d['sources'])} sources, all source IDs resolve to https URLs, no broken internal links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
