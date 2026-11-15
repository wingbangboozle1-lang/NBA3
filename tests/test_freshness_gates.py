#!/usr/bin/env python3
"""Tests for freshness + provenance gates (session arena/79341829-nba3)."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import freshness_gates  # noqa: E402


class FreshnessGatesTest(unittest.TestCase):
    def test_report_structure(self):
        rep = freshness_gates.evaluate()
        ids = [g["id"] for g in rep["gates"]]
        for expected in ("F1_injury_freshness", "F2_slate_window", "F3_results_settled",
                         "P2_team_stats", "P3_feed_fields"):
            self.assertIn(expected, ids)
        self.assertIn("pass", rep)

    def test_team_stats_and_feed_fields_pass_on_committed_data(self):
        rep = freshness_gates.evaluate()
        by = {g["id"]: g for g in rep["gates"]}
        self.assertTrue(by["P2_team_stats"]["pass"], by["P2_team_stats"]["detail"])
        self.assertTrue(by["P3_feed_fields"]["pass"], by["P3_feed_fields"]["detail"])

    def test_f3_fails_with_unsettled_final_rows(self):
        import json, tempfile
        feed_path = os.path.join(ROOT, "data", "app", "results_feed.json")
        original = json.load(open(feed_path, encoding="utf-8"))
        try:
            broken = json.loads(json.dumps(original))
            for g in broken["games"]:
                if g["date"] == "2026-11-14":
                    g["settled"] = False
                    break
            with open(feed_path, "w", encoding="utf-8") as fh:
                json.dump(broken, fh)
            rep = freshness_gates.evaluate()
            by = {g["id"]: g for g in rep["gates"]}
            self.assertFalse(by["F3_results_settled"]["pass"])
            self.assertFalse(rep["pass"])
        finally:
            with open(feed_path, "w", encoding="utf-8") as fh:
                json.dump(original, fh, indent=1)
                fh.write("\n")


if __name__ == "__main__":
    unittest.main()
