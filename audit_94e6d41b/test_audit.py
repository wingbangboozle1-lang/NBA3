#!/usr/bin/env python3
"""Tests for the audit_94e6d41b/ tree (session arena/94e6d41b-nba3).

Run: python3 -m unittest discover -s audit_94e6d41b -p 'test_*.py'

These are the same guarantees the 1823b910 tree tests, applied to this round's
artifacts: page rules P1/P2, the invariance verdicts, the settlement arithmetic
against the committed finals, and the manifest/availability coherence.
"""
import csv
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

OFFICIAL_HOSTS = ("nba.com", "ak-static.cms.nba.com", "official.nba.com", "www.nba.com")

REPORT_0615 = os.path.join(APP, "official_injuries_2026-11-15_0615AM.json")


def jload(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return json.load(fh)


def is_official(url):
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    host = re.sub(r"^https://", "", url).split("/")[0]
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


class RowParser(HTMLParser):
    """Collects the hrefs of each <tbody> row and every id on the page."""

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
    def page_names(self):
        return sorted(f for f in os.listdir(PAGES) if f.endswith(".html"))

    def test_every_tbody_row_has_an_official_source_link(self):
        self.assertTrue(self.page_names())
        for name in self.page_names():
            p = RowParser()
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                p.feed(fh.read())
            self.assertTrue(p.rows, f"{name} has no data rows")
            for i, row in enumerate(p.rows):
                self.assertTrue(any(is_official(h) for h in row),
                                f"{name} data row {i+1} has no official source link: {row}")

    def test_no_broken_internal_links(self):
        for name in self.page_names():
            p = RowParser()
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                p.feed(fh.read())
            for href in p.hrefs:
                if href.startswith(("http://", "https://", "mailto:")) or href.startswith("/"):
                    continue
                target = os.path.normpath(os.path.join(PAGES, href.split("#")[0]))
                self.assertTrue(os.path.exists(target),
                                f"{name} broken internal href {href}")

    def test_anchor_ids_resolve_within_each_page(self):
        for name in self.page_names():
            p = RowParser()
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                p.feed(fh.read())
            for href in p.hrefs:
                if href.startswith("#"):
                    self.assertIn(href[1:], p.ids, f"{name} dead anchor {href}")


class TestInvariance(unittest.TestCase):
    def setUp(self):
        self.inv = jload(DATA, "line_invariance.json")

    def test_seeded_reproduction_is_byte_exact(self):
        self.assertTrue(self.inv["seeded_reproduction"]["leg_a_bytes_equal_published"])

    def test_refreshed_engine_is_deterministic(self):
        self.assertTrue(self.inv["determinism"]["leg_c_runs_equal"])

    def test_refreshed_build_is_adopted_as_canonical(self):
        self.assertTrue(self.inv["canonical_adoption"]["leg_c_equals_committed_lab_json"])

    def test_fix_moves_no_price_field(self):
        self.assertEqual(self.inv["fix_effect"]["price_fields_that_moved"], {})

    def test_fix_only_touches_vacated_fields(self):
        allowed = {"minutes_vacuum", "pts_vacuum", "reb_vacuum", "ast_vacuum",
                   "players_without_official_minutes"}
        moved = set(self.inv["fix_effect"]["injury_impact_fields_that_changed"])
        self.assertTrue(moved)
        self.assertTrue(moved <= allowed,
                        f"fix touched unexpected fields: {moved - allowed}")

    def test_refresh_price_moves_carry_examples(self):
        for field, rows in self.inv["refresh_effect"]["price_fields_that_moved"].items():
            self.assertTrue(rows, f"{field} reported moved with no example rows")

    def test_window_roll_recorded(self):
        self.assertIn("0022600231", " ".join(self.inv["refresh_effect"]["lines_only_in_seeded"]))
        self.assertEqual(len(self.inv["refresh_effect"]["lines_only_in_refreshed"]), 12)


class TestSettlement(unittest.TestCase):
    def setUp(self):
        self.sett = jload(DATA, "settlement_1114.json")

    def test_all_five_1114_games_settled(self):
        self.assertEqual(len(self.sett["picks_rows"]), 5)

    def test_scores_match_the_committed_log(self):
        log = {}
        with open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                log[r["game_id"]] = (r["away"], r["away_pts"], r["home"], r["home_pts"])
        for row in self.sett["picks_rows"]:
            gid = row["game_id"]
            a, ap, h, hp = log[gid]
            self.assertEqual((a, int(ap), h, int(hp)),
                             (row["official_result"]["away"], row["official_result"]["away_pts"],
                              row["official_result"]["home"], row["official_result"]["home_pts"]),
                             f"settlement score for {gid} disagrees with the results log")

    def test_total_results_are_consistent_arithmetic(self):
        for row in self.sett["picks_rows"]:
            total = row["official_result"]["away_pts"] + row["official_result"]["home_pts"]
            self.assertEqual(total, row["official_result"]["total"])
            line = row["published"]["origin_total"]
            expected = "PUSH" if total == line else ("OVER" if total > line else "UNDER")
            self.assertEqual(row["grading"]["total"]["result"], expected)

    def test_spread_results_are_consistent_arithmetic(self):
        for row in self.sett["picks_rows"]:
            g = row["grading"]["spread"]
            expected = "PUSH" if g["decision_margin"] == 0 else \
                ("cover" if g["decision_margin"] > 0 else "no_cover")
            self.assertEqual(g["result"], expected)

    def test_quarter_scores_are_null_and_flagged(self):
        for row in self.sett["picks_rows"]:
            self.assertIsNone(row["official_result"]["quarters"])
        self.assertIn("F-94E6D41B-02", self.sett["quarter_scores_note"])

    def test_props_reference_captured_actuals(self):
        actuals = {("Nikola Jokic", "pts"): 26, ("Nikola Jokic", "reb"): 8,
                   ("Nikola Jokic", "ast"): 10, ("Cade Cunningham", "pts"): 33,
                   ("Cade Cunningham", "reb"): 5, ("Cade Cunningham", "ast"): 8,
                   ("Giannis Antetokounmpo", "pts"): 34,
                   ("Giannis Antetokounmpo", "reb"): 14,
                   ("Giannis Antetokounmpo", "ast"): 8}
        import unicodedata
        fold = lambda s: "".join(ch for ch in unicodedata.normalize("NFD", s)
                                 if unicodedata.category(ch) != "Mn").lower()
        self.assertEqual(len(self.sett["props_rows"]), 9)
        for r in self.sett["props_rows"]:
            key = (fold(r["player"]).title(), {"points": "pts", "rebounds": "reb",
                                               "assists": "ast"}[r["stat"]])
            self.assertEqual(r["actual"], actuals[key])


class TestRefreshAndDelta(unittest.TestCase):
    def setUp(self):
        self.refresh = jload(DATA, "refresh.json")
        self.delta = jload(DATA, "availability_delta.json")
        self.inj = jload(REPORT_0615)

    def test_delta_covers_all_18_team_sides(self):
        self.assertEqual(len(self.delta["rows"]), 18)

    def test_every_0415_side_was_nys(self):
        for r in self.delta["rows"]:
            self.assertEqual(r["published_0415am"], "NOT YET SUBMITTED")

    def test_dal_still_nys_and_nyk_zero_rows(self):
        by_team = {(r["matchup"], r["team"]): r for r in self.delta["rows"]}
        self.assertEqual(by_team[("DAL@BOS", "DAL")]["newest_0615am"], "NYS")
        self.assertEqual(by_team[("NYK@TOR", "NYK")]["newest_0615am"], "no rows published")

    def test_day_before_confirms_every_filed_team(self):
        for r in self.delta["rows"]:
            if r["newest_0615am"].startswith("filed"):
                self.assertNotEqual(r["day_before_1130pm"], "absent",
                                    f"{r['matchup']} {r['team']} filed with no day-before row")

    def test_row_inventory(self):
        self.assertEqual(self.inj["count"], 101)
        self.assertEqual(self.inj["player_rows"], 84)
        self.assertEqual(self.inj["not_submitted_rows"], 17)

    def test_capture_checks_all_pass(self):
        # Integration (f300fe08): the canonical 06:15 AM capture on main is
        # session bb0c83a4's transcription and records its checks under
        # cross_checks (dict of {ok: ...}); this session's capture recorded a
        # checks list. Accept either schema; both must be all-green.
        if "checks" in self.inj:
            self.assertTrue(all(c["result"] == "PASS" for c in self.inj["checks"]),
                            "the capture script's own checks include a FAIL")
        else:
            cc = self.inj["cross_checks"]
            self.assertTrue(cc, "capture cross_checks missing")
            self.assertTrue(all(v.get("ok") for v in cc.values()),
                            "a capture cross-check is not ok: "
                            + str([k for k, v in cc.items() if not v.get("ok")]))

    def test_status_changes_are_empty(self):
        self.assertEqual(self.refresh["counts"]["status_changes_overnight"], 0)


class TestCoherence(unittest.TestCase):
    """The refreshed manifest names files that exist and agree with the engine's output."""

    def test_manifest_paths_exist(self):
        man = jload(APP, "snapshot_manifest.json")
        for block in ("slate", "ratings", "injuries", "players"):
            path = os.path.join(ROOT, man[block]["path"])
            self.assertTrue(os.path.exists(path), f"manifest {block} -> {path} missing")
        self.assertTrue(os.path.exists(os.path.join(ROOT, man["results_log"]["path"])))

    def test_window_is_1115_1118(self):
        man = jload(APP, "snapshot_manifest.json")
        self.assertEqual((man["window"]["from"], man["window"]["to"]),
                         ("2026-11-15", "2026-11-18"))

    def test_availability_states_derive_from_the_manifest_report(self):
        av = jload(APP, "report_availability.json")
        man = jload(APP, "snapshot_manifest.json")
        self.assertEqual(av["as_of_report"], man["injuries"]["report_stamp"])

    def test_rotation_rows_cover_the_nine_1115_games(self):
        rot = jload(DATA, "rotation_impact.json")
        self.assertEqual(len({r["game_id"] for r in rot["rows"]}), 9)
        self.assertEqual(len(rot["rows"]), 18)

    def test_gameflow_rows_cover_the_nine_1115_games(self):
        flow = jload(DATA, "gameflow.json")
        self.assertEqual(len(flow["rows"]), 9)

    def test_b2b_correspondence_names_dal(self):
        refresh = jload(DATA, "refresh.json")
        b2b = refresh["availability_layer"]["b2b_correspondence"]
        self.assertEqual(b2b["on_back_to_back"], ["DAL"])
        self.assertIn("DAL", b2b["unfiled"])

    def test_committed_lab_is_the_refreshed_engine_output(self):
        """The adopted data/app/lab.json is exactly leg C's output (the CI drift gate's claim)."""
        import hashlib
        blob = open(os.path.join(APP, "lab.json"), "rb").read()
        inv = jload(DATA, "line_invariance.json")
        self.assertEqual(hashlib.sha256(blob).hexdigest()[:16],
                         inv["legs_sha256"]["c_refreshed_1"])


if __name__ == "__main__":
    unittest.main()
