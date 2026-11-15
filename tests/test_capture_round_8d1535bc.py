"""Checks for scripts/capture_round_8d1535bc.py (session arena/8d1535bc-nba3, U1).

Runs offline against the committed verbatim transcriptions. Expected values were read
from the official PDFs (see the transcript headers for URLs) and cross-checked by hand
for the rows named here.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import capture_round_8d1535bc as cap  # noqa: E402


class CaptureRound8d1535bcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.am, cls.am_un, _ = cap.parse(cap.AM, "AM")
        cls.pm, cls.pm_un, _ = cap.parse(cap.PM, "PM")
        cls.diff = cap.diff(cls.am, cls.pm)

    def test_row_counts(self):
        self.assertEqual(sum(r["kind"] == "player" for r in self.pm), 150)
        self.assertEqual(sum(r["kind"] == "not_submitted" for r in self.pm), 5)
        self.assertEqual(sum(r["kind"] == "player" for r in self.am), 84)

    def test_known_status_changes(self):
        ch = {c["player"]: c for c in self.diff["changes"]["status"]}
        self.assertEqual(ch["Nembhard, Andrew"]["am_status"], "Questionable")
        self.assertEqual(ch["Nembhard, Andrew"]["pm_status"], "Out")
        self.assertEqual(ch["McConnell, T.J."]["pm_status"], "Available")
        self.assertEqual(ch["Johnson, Tre"]["pm_status"], "Out")

    def test_printed_spelling_change_is_visible_not_silently_merged(self):
        removed = {r["player"] for r in self.diff["changes"]["removed"]}
        added = {r["player"] for r in self.diff["changes"]["added"]}
        self.assertIn("Embid, Joel", removed)
        self.assertIn("Embiid, Joel", added)

    def test_ambiguous_name_excluded(self):
        self.assertIn("Penda, Noah", self.diff["ambiguous_names_not_diffed"])

    def test_no_transcript_markers_in_reasons(self):
        for r in self.am + self.pm:
            self.assertNotIn("<!--", r["reason"] or "")

    def test_only_unattributed_line_is_the_fracture_fragment(self):
        self.assertEqual(len(self.pm_un), 1)
        self.assertIn("Fracture", self.pm_un[0]["text"])

    def test_outputs_match_script(self):
        with open(cap.OUT_DIFF, encoding="utf-8") as fh:
            committed = json.load(fh)
        self.assertEqual(committed["counts"], self.diff["counts"])


if __name__ == "__main__":
    unittest.main()
