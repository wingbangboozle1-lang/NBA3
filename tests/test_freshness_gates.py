#!/usr/bin/env python3
"""Tests for freshness + provenance gates (session arena/79341829-nba3)."""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import freshness_gates_round_79341829 as freshness_gates  # noqa: E402
import freshness_gates as live_freshness_gates  # noqa: E402


class FreshnessGatesTest(unittest.TestCase):
    def test_live_gate_selects_newest_report_by_real_clock_time(self):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            injury_dir = pathlib.Path(td)
            # This lexical ordering is wrong: "12_00AM" sorts after "01_00PM".
            for filename in (
                "Injury-Report_2026-11-15_12_00AM.md",
                "Injury-Report_2026-11-15_01_00PM.md",
                "Injury-Report_2026-11-15_11_45PM.md",
                "Injury-Report_2026-11-16_12_00AM.md",
            ):
                (injury_dir / filename).touch()
            with mock.patch.object(live_freshness_gates, "INJ", injury_dir):
                self.assertEqual(
                    live_freshness_gates.latest_report().name,
                    "Injury-Report_2026-11-16_12_00AM.md",
                )
                (injury_dir / "Injury-Report_2026-11-16_12_00AM.md").unlink()
                self.assertEqual(
                    live_freshness_gates.latest_report().name,
                    "Injury-Report_2026-11-15_11_45PM.md",
                )

    def test_live_gate_rejects_unparseable_report_filename(self):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            injury_dir = pathlib.Path(td)
            (injury_dir / "Injury-Report_2026-11-15_latest.md").touch()
            with mock.patch.object(live_freshness_gates, "INJ", injury_dir):
                with self.assertRaisesRegex(ValueError, "unexpected archived injury report"):
                    live_freshness_gates.latest_report()

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
