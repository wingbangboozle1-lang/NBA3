#!/usr/bin/env python3
"""Tests for the audit_1823b910/ tree (session arena/1823b910-nba3).

Run: python3 -m unittest discover -s audit_1823b910 -p 'test_*.py'
"""
import json
import os
import re
import subprocess
import sys
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")
APP = os.path.join(ROOT, "data", "app")

OFFICIAL_HOSTS = ("nba.com", "ak-static.cms.nba.com", "official.nba.com",
                  "www.nba.com", "pr.nba.com")


def jload(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return json.load(fh)


def is_official(url):
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    host = re.sub(r"^https://", "", url).split("/")[0]
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


class RowParser(HTMLParser):
    """Collects the hrefs of each <tbody> row, and every anchor on the page."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.in_tbody = False
        self.row = None
        self.rows = []
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            if self.row is not None:
                self.row.append(a["href"])
        if tag == "tbody":
            self.in_tbody = True
        if tag == "tr" and self.in_tbody:
            self.row = []

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "tbody":
            self.in_tbody = False


class TestPageRules(unittest.TestCase):
    """P1 every data row carries an official link; P2 no broken internal link."""

    def page_names(self):
        return sorted(f for f in os.listdir(PAGES) if f.endswith(".html"))

    def test_every_tbody_row_has_an_official_source_link(self):
        self.assertTrue(self.page_names())
        for name in self.page_names():
            p = RowParser()
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                p.feed(fh.read())
            self.assertTrue(p.rows, f"{name} has no data rows")
            for i, hrefs in enumerate(p.rows, 1):
                self.assertTrue(
                    any(is_official(h) for h in hrefs),
                    f"{name} tbody row {i} has no official-source link: {hrefs}")

    def test_no_broken_internal_links(self):
        # Links within this tree must name a page this build emits. A link that
        # walks out of the tree ("../../...") is resolved against the repository
        # root and must exist there; audit_1823b910/pages/ links to the parallel
        # session's audit that way.
        known = set(self.page_names())
        for name in self.page_names():
            p = RowParser()
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                p.feed(fh.read())
            for href in p.hrefs:
                if href.startswith(("https://", "http://", "mailto:", "#", "/")):
                    continue
                target = href.split("#")[0]
                if target.startswith("../"):
                    self.assertTrue(
                        os.path.exists(os.path.normpath(os.path.join(PAGES, target))),
                        f"{name}: broken out-of-tree link {href}")
                    continue
                self.assertIn(target, known, f"{name}: broken internal link {href}")

    def test_in_page_anchors_resolve(self):
        for name in self.page_names():
            p = RowParser()
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                p.feed(fh.read())
            for href in p.hrefs:
                if href.startswith("#") and len(href) > 1:
                    self.assertIn(href[1:], p.ids,
                                  f"{name}: dangling in-page anchor {href}")

    def test_no_double_escaped_entities_in_titles(self):
        """A title is escaped by esc(); a pre-written &rarr; would render literally."""
        for name in self.page_names():
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                text = fh.read()
            for tag in ("<title>", "<h1>"):
                start = text.find(tag)
                self.assertNotEqual(start, -1, f"{name} has no {tag}")
                end = text.find("<", start + len(tag))
                chunk = text[start:end]
                self.assertNotIn("&amp;", chunk,
                                 f"{name}: double-escaped entity in {tag}: {chunk}")

    def test_pages_are_html5_and_link_the_stylesheet(self):
        for name in self.page_names():
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertTrue(text.startswith("<!DOCTYPE html>"), name)
            self.assertIn("../assets/audit.css", text, name)
            self.assertIn("</html>", text, name)


class TestCapture(unittest.TestCase):
    """The capture script's own E-checks, replayed offline."""

    def test_e_checks_pass_on_the_committed_files(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                         "capture_official_2026_11_14e.py")],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("All E-checks passed.", r.stdout)

    def test_snapshot_shape(self):
        d = jload(APP, "official_injuries_2026-11-14_0130PM.json")
        self.assertEqual(d["count"], 69)
        self.assertEqual(d["player_rows"], 50)
        self.assertEqual(d["not_submitted_rows"], 19)
        self.assertEqual(d["report_stamp"], "2026-11-14 01:30 PM ET")
        for row in d["rows"]:
            if not row["is_team_not_submitted"]:
                self.assertIn(row["status"],
                              ("Out", "Doubtful", "Questionable", "Probable", "Available"),
                              row)
                self.assertTrue(row["player"], row)
            self.assertTrue(row["matchup"], row)
            self.assertIn(row["game_date"], ("11/14/2026", "11/15/2026"), row)

    def test_the_six_teamless_rows_are_attributed(self):
        d = jload(APP, "official_injuries_2026-11-14_0130PM.json")
        want = {"Claxton, Nic": ("CHI@MIN", "CHI"),
                "Powell, Norman": ("CHI@MIN", "CHI"),
                "Sellers, Jaylin": ("CHI@MIN", "CHI"),
                "Smith, Jalen": ("CHI@MIN", "CHI"),
                "Swain, Dailyn": ("CHI@MIN", "CHI"),
                "Wilson, Caleb": ("CHI@MIN", "CHI")}
        got = {r["player"]: (r["matchup"], r["team"]) for r in d["rows"] if r["player"] in want}
        self.assertEqual(got, want)

    def test_the_merged_tail_expanded_to_three_rows(self):
        d = jload(APP, "official_injuries_2026-11-14_0130PM.json")
        tail = [(r["matchup"], r["team_name"], r["game_time_et"]) for r in d["rows"]
                if r["game_date"] == "11/15/2026"
                and r["team_name"] in ("Milwaukee Bucks", "Oklahoma City Thunder",
                                       "Sacramento Kings")]
        self.assertEqual(
            sorted(tail),
            [("ATL@MIL", "Milwaukee Bucks", "08:00"),
             ("OKC@SAC", "Oklahoma City Thunder", "09:00"),
             ("OKC@SAC", "Sacramento Kings", "09:00")])


class TestAnalysis(unittest.TestCase):

    def test_line_invariance_moved_no_price_field(self):
        li = jload(DATA, "line_invariance.json")
        self.assertEqual(li["price_fields_that_moved"], {})
        self.assertEqual(li["lines_compared"], 27)
        self.assertTrue(li["picks_identical"])
        self.assertGreater(len(li["availability_fields_that_changed"]), 0)

    def test_refresh_counts(self):
        r = jload(DATA, "refresh.json")
        c = r["counts"]
        self.assertEqual(c["published_rows"], 49)
        self.assertEqual(c["newest_rows"], 69)
        self.assertEqual(c["team_games_filed_since"], 4)
        self.assertEqual(c["player_rows_added"], 24)
        self.assertEqual(c["player_rows_removed"], 0)
        self.assertEqual(c["status_changes"], 4)

    def test_only_mem_is_still_blank(self):
        r = jload(DATA, "refresh.json")
        blank = [x for x in r["availability_layer"] if not x["filed_in_newest_report"]]
        self.assertEqual([x["team"] for x in blank], ["MEM"])

    def test_unknowns_are_never_estimated(self):
        rot = jload(DATA, "rotation_impact.json")
        for row in rot["rows"]:
            if row["refreshed_state"] != "FILED":
                for f in ("refreshed_minutes_vacuum", "refreshed_pts_vacuum",
                          "refreshed_reb_vacuum", "refreshed_ast_vacuum", "at_risk_minutes"):
                    self.assertIsNone(row[f], (row["team"], f))

    def test_gameflow_covers_the_five_1114_games(self):
        gf = jload(DATA, "gameflow.json")
        self.assertEqual(len(gf["rows"]), 5)
        self.assertEqual(sorted(r["matchup"] for r in gf["rows"]),
                         ["BKN@MEM", "CHI@MIN", "DAL@CLE", "DEN@NOP", "DET@MIA"])
        for r in gf["rows"]:
            self.assertIn(r["home_b2b"] or r["away_b2b"], (True, False, None))
            if r["home_rest_days"] is not None and r["away_rest_days"] is not None:
                self.assertEqual(r["rest_diff"], r["home_rest_days"] - r["away_rest_days"])

    def test_repo_review_results(self):
        rr = jload(DATA, "repo_review.json")
        by_id = {f["id"]: f["result"] for f in rr["findings"]}
        self.assertEqual(by_id["RR-01"], "PASS")   # every JSON parses
        self.assertEqual(by_id["RR-02"], "PASS")   # no conflict markers
        self.assertEqual(by_id["RR-03"], "FAIL")   # snapshot is stale
        self.assertEqual(by_id["RR-04"], "FAIL")   # availability layer disagrees
        self.assertEqual(by_id["RR-05"], "FAIL")   # lines are injury-blind
        self.assertEqual(len(rr["findings"]), 8)

    def test_flags_are_sourced_and_owned(self):
        fl = jload(DATA, "flags.json")
        self.assertTrue(fl["flags"])
        for f in fl["flags"]:
            self.assertTrue(f["owner"], f["id"])
            self.assertTrue(f["source"], f["id"])
            self.assertIn(f["severity"], ("high", "medium", "low"), f["id"])
            self.assertFalse(f["blocking"], f["id"])


class TestDeterminism(unittest.TestCase):
    """The generated JSON must be reproducible from the committed inputs."""

    def test_rerun_produces_identical_refresh_and_rotation(self):
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                     "capture_official_2026_11_14e.py")],
                       cwd=ROOT, capture_output=True, text=True, check=True)
        before = {n: open(os.path.join(DATA, n), encoding="utf-8").read()
                  for n in ("refresh.json", "rotation_impact.json")}
        r = subprocess.run([sys.executable, os.path.join(HERE, "analysis.py")],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        after = {n: open(os.path.join(DATA, n), encoding="utf-8").read()
                 for n in ("refresh.json", "rotation_impact.json")}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
