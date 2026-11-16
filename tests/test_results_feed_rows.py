#!/usr/bin/env python3
"""Tests for the results-feed ingest/settle extensions (session arena/4054e125-nba3).

Covers: OT quarter arithmetic, ingest merge semantics (one row per game, never
overwrite, conflicting finals reported), and the committed 11/15 rows themselves
(every quarter list sums to its final; the ATL@MIL flag is present).
"""
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import results_feed  # noqa: E402

FEED = os.path.join(ROOT, "data", "app", "results_feed.json")
CAPTURE = os.path.join(ROOT, "data", "app", "official_results_2026-11-15.json")


def blank_feed():
    return {"source_label": "", "retrieved_stamp": "", "settlement_rule": "",
            "count": 0, "settled_count": 0, "games": [], "sources": []}


class ResultsFeedRowsTest(unittest.TestCase):
    def test_committed_1115_rows_all_sum_to_finals(self):
        cap = json.load(open(CAPTURE, encoding="utf-8"))
        self.assertEqual(cap["count"], 9)
        for g in cap["games"]:
            self.assertEqual(sum(g["away_q"]), g["away_pts"], g["game_id"])
            self.assertEqual(sum(g["home_q"]), g["home_pts"], g["game_id"])
            self.assertEqual(len(g["away_q"]), len(g["home_q"]), g["game_id"])
            self.assertIn("https://www.nba.com/game/", g["game_url"])

    def test_atl_mil_flag_present_and_conflict_recorded(self):
        cap = json.load(open(CAPTURE, encoding="utf-8"))
        atl = next(g for g in cap["games"] if g["game_id"] == "0022600243")
        self.assertIn("QUARTER CONFLICT", atl["flag"])
        self.assertFalse(atl["cross_checks"]["gamebook_transcription_audit_00b0c780_periods_equal_linescore"])
        self.assertEqual(atl["home_q"], [37, 16, 27, 26])

    def test_feed_contains_settled_1115_rows(self):
        feed = json.load(open(FEED, encoding="utf-8"))
        rows = [g for g in feed["games"] if g["date"] == "2026-11-15"]
        self.assertEqual(len(rows), 9)
        for g in rows:
            self.assertTrue(g["settled"])
            self.assertTrue(g["verified"])
            self.assertIn("settled at", g["settlement_stamp"])
        nyk = next(g for g in rows if g["game_id"] == "0022600241")
        self.assertEqual(nyk["away_q5"], 17)   # OT1 captured
        self.assertEqual(nyk["home_q5"], 13)

    def test_verify_sums_including_ot(self):
        feed = blank_feed()
        feed["games"] = [{
            "date": "2026-11-15", "game_id": "T1", "away": "AAA", "home": "BBB",
            "away_pts": 112, "home_pts": 108,
            "away_q1": 23, "away_q2": 24, "away_q3": 20, "away_q4": 28, "away_q5": 17,
            "home_q1": 17, "home_q2": 26, "home_q3": 31, "home_q4": 21, "home_q5": 13,
            "state": "Final/OT", "verified": False, "quarter_check": "",
            "settled": False, "settlement_stamp": None}]
        results_feed.verify(feed)
        self.assertTrue(feed["games"][0]["verified"])
        self.assertEqual(feed["games"][0]["quarter_check"], "quarter sums equal the final")

    def test_verify_rejects_mismatched_quarter_sums(self):
        feed = blank_feed()
        feed["games"] = [{
            "date": "2026-11-15", "game_id": "T2", "away": "AAA", "home": "BBB",
            "away_pts": 100, "home_pts": 90,
            "away_q1": 30, "away_q2": 30, "away_q3": 30, "away_q4": 30,
            "home_q1": 20, "home_q2": 20, "home_q3": 20, "home_q4": 20,
            "state": "Final", "verified": True, "quarter_check": "",
            "settled": False, "settlement_stamp": None}]
        results_feed.verify(feed)
        self.assertFalse(feed["games"][0]["verified"])
        self.assertEqual(feed["games"][0]["quarter_check"], "quarter sums MISMATCH")

    def test_ingest_is_idempotent_and_reports_conflicts(self):
        feed = blank_feed()
        row = {"date": "2026-11-15", "game_id": "T3", "away": "AAA", "home": "BBB",
               "away_pts": 100, "home_pts": 90, "away_q": [25, 25, 25, 25],
               "home_q": [22, 22, 23, 23], "state": "Final"}
        added, conflicts = results_feed.ingest_rows(feed, [row], "t")
        self.assertEqual((added, conflicts), (1, []))
        added, conflicts = results_feed.ingest_rows(feed, [row], "t")
        self.assertEqual((added, conflicts), (0, []))
        clash = dict(row, away_pts=101)
        added, conflicts = results_feed.ingest_rows(feed, [clash], "t")
        self.assertEqual(added, 0)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("final differs", conflicts[0][1])

    def test_settle_requires_verified_final(self):
        feed = blank_feed()
        feed["games"] = [{
            "date": "2026-11-15", "game_id": "T4", "away": "AAA", "home": "BBB",
            "away_pts": None, "home_pts": None,
            "away_q1": None, "away_q2": None, "away_q3": None, "away_q4": None,
            "home_q1": None, "home_q2": None, "home_q3": None, "home_q4": None,
            "state": "", "verified": False, "quarter_check": "",
            "settled": False, "settlement_stamp": None}]
        results_feed.verify(feed)
        n = results_feed.settle(feed, "2026-11-15")
        self.assertEqual(n, 0)
        self.assertFalse(feed["games"][0]["settled"])


if __name__ == "__main__":
    unittest.main()
