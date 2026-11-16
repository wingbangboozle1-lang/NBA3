"""Regression test: archived injury reports must be ordered by their own timestamp.

Defect found on 2026-11-16 (session 4f194ba2): a lexical filename sort ranks
'12_00AM' (midnight, the OLDEST report of a day) after '06_45PM', so
`sorted(...) + [-1]` in availability.py, estimators.py and freshness_gates.py
silently selected a 24-hour-old report as "newest" while the archive carried the
evening report. The gates then compared the model against the same wrong file and
passed. The authoritative order is the stamp inside the filename.
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import injury_archive as ia          # noqa: E402
import availability                 # noqa: E402


class TestReportStampKey(unittest.TestCase):
    def key(self, name):
        return ia.report_stamp_key(Path(name))

    def test_evening_report_sorts_after_midnight_of_the_same_day(self):
        self.assertGreater(self.key("Injury-Report_2026-11-15_06_45PM.md"),
                           self.key("Injury-Report_2026-11-15_12_00AM.md"))

    def test_am_slots_sort_in_clock_order(self):
        self.assertLess(self.key("Injury-Report_2026-11-15_06_00AM.md"),
                        self.key("Injury-Report_2026-11-15_06_15AM.md"))
        self.assertLess(self.key("Injury-Report_2026-11-15_11_45AM.md"),
                        self.key("Injury-Report_2026-11-15_12_00PM.md"))
        self.assertLess(self.key("Injury-Report_2026-11-15_12_00AM.md"),
                        self.key("Injury-Report_2026-11-15_01_30AM.md"))

    def test_dates_order_before_times(self):
        self.assertLess(self.key("Injury-Report_2026-11-14_11_00PM.md"),
                        self.key("Injury-Report_2026-11-15_12_00AM.md"))

    def test_unrecognised_name_sorts_last_and_never_crashes(self):
        k = self.key("some_other_file.md")
        self.assertGreater(k, self.key("Injury-Report_2026-11-15_06_45PM.md"))


class TestCommittedArchiveUsesTimestampOrder(unittest.TestCase):
    """Guards the real failure on the committed tree: every consumer must select the
    newest report BY STAMP, and the newest must be the evening report, not midnight."""

    def test_newest_report_is_the_latest_by_stamp_not_lexically(self):
        files = list((Path(ROOT) / "data" / "live" / "injuries").glob("Injury-Report_*.md"))
        self.assertTrue(files)
        lexical = max(files, key=lambda p: p.name)          # the old, broken choice
        stamped = max(files, key=ia.report_stamp_key)
        self.assertEqual(stamped.name, "Injury-Report_2026-11-15_06_45PM.md")
        if lexical.name != stamped.name:
            # when they differ, the lexical choice must be OLDER by stamp — that is the defect
            self.assertLess(ia.report_stamp_key(lexical), ia.report_stamp_key(stamped))

    def test_availability_latest_agrees_with_stamped_order(self):
        files = list((Path(ROOT) / "data" / "live" / "injuries").glob("Injury-Report_*.md"))
        self.assertEqual(availability.latest().name,
                         max(files, key=ia.report_stamp_key).name)

    def test_archive_diff_pairs_are_chronological(self):
        import json
        d = json.load(open(os.path.join(ROOT, "data", "live", "injuries", "deltas.json")))
        for delta in d["deltas"]:
            a = ia.report_stamp_key(Path(delta["from_file"]))
            b = ia.report_stamp_key(Path(delta["to_file"]))
            self.assertLessEqual(a, b,
                                 f"diff pairs must be chronological: {delta['from_file']} -> {delta['to_file']}")


if __name__ == "__main__":
    unittest.main()
