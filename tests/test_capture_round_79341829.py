#!/usr/bin/env python3
"""Tests for the 2026-11-15 official capture (session arena/79341829-nba3)."""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")


class Capture1115Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                         "capture_round_79341829.py")],
                           capture_output=True, text=True)
        cls.run_out = r.stdout
        cls.run_code = r.returncode
        cls.inj = json.load(open(os.path.join(APP, "official_injuries_2026-11-15_0615AM_79341829.json")))
        cls.feed = json.load(open(os.path.join(APP, "results_feed.json")))
        cls.logs = json.load(open(os.path.join(APP, "player_game_logs.json")))
        cls.delta = json.load(open(os.path.join(APP, "injury_delta_1115.json")))
        cls.shares = json.load(open(os.path.join(APP, "minutes_shares.json")))

    def test_all_capture_checks_pass(self):
        self.assertEqual(self.run_code, 0, self.run_out)
        self.assertIn("all capture checks passed", self.run_out)

    def test_injury_rows_have_sources_and_stamps(self):
        self.assertEqual(self.inj["source_url"],
                         "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf")
        self.assertEqual(self.inj["report_stamp"], "2026-11-15 06:15 AM ET")
        self.assertEqual(self.inj["retrieved_stamp"], "2026-11-15T11:33Z")
        self.assertTrue(self.inj["raw_sha256"])
        self.assertEqual(self.inj["count"],
                         self.inj["player_rows"] + self.inj["not_submitted_rows"])
        legal = {"Out", "Doubtful", "Questionable", "Probable", "Available", "NOT YET SUBMITTED"}
        for r in self.inj["rows"]:
            self.assertIn(r["status"], legal)
            self.assertTrue(r["matchup"])

    def test_results_feed_quarter_sums(self):
        nov14 = [g for g in self.feed["games"] if g["date"] == "2026-11-14"]
        self.assertEqual(len(nov14), 5)
        for g in nov14:
            self.assertTrue(g["verified"])
            self.assertTrue(g["settled"])
            self.assertTrue(g["settlement_stamp"])
            self.assertEqual(g["away_q1"] + g["away_q2"] + g["away_q3"] + g["away_q4"],
                             g["away_pts"])
            self.assertEqual(g["home_q1"] + g["home_q2"] + g["home_q3"] + g["home_q4"],
                             g["home_pts"])
            self.assertTrue(g["verified_from"].startswith("https://"))

    def test_results_feed_rows_carry_official_source(self):
        for g in self.feed["games"]:
            self.assertTrue((g.get("verified_from") or "").startswith("https://"))

    def test_player_game_logs_columns(self):
        self.assertGreaterEqual(self.logs["count"], 150)
        for r in self.logs["rows"][:50]:
            for k in ("date", "team", "opponent", "min", "pts", "reb", "ast", "source"):
                self.assertIn(k, r)
            self.assertTrue(r["source"].startswith("https://"))

    def test_minutes_shares_top8(self):
        self.assertEqual(len(self.shares["teams"]), 28)   # 10 team-games 11/14 + 18 on 11/15 (session arena/4a59430d)
        for v in self.shares["teams"].values():
            self.assertLessEqual(len(v["top8"]), 8)
            self.assertTrue(v["source"].startswith("https://"))

    def test_delta_vs_prior_report(self):
        self.assertGreater(self.delta["player_rows_added"], 0)
        self.assertEqual(self.delta["compared"]["prior_report_stamp"], "2026-11-14 01:30 PM ET")
        self.assertTrue(self.delta["sources"][0].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
