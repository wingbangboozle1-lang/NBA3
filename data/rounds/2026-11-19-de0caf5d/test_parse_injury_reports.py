"""Pins the 11/19 injury-report transcript counts and the raw-file hashes (session de0caf5d, X2)."""
import hashlib
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class InjuryCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "injury_2026-11-19_0045AM.json"), encoding="utf-8") as fh:
            cls.d = json.load(fh)

    def test_raw_hashes_match_stored_transcripts(self):
        for key in ("newest_revision", "previous_revision"):
            meta = self.d[key]
            with open(os.path.join(HERE, meta["raw_file"]), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), meta["raw_sha256"], key)

    def test_newest_revision_counts(self):
        n = self.d["newest_revision"]
        self.assertEqual(n["row_count"], 44)
        self.assertEqual(n["player_rows"], 23)
        self.assertEqual(n["team_placeholder_rows"], 15)
        self.assertEqual(n["unreadable_rows"], 6)
        self.assertFalse(n["linked_from_index"])

    def test_player_rows_are_never_attributed_by_inference(self):
        for r in self.d["rows_newest"]:
            if r.get("row_kind") == "player" and r.get("attribution") == "matchup_and_team_blank":
                self.assertEqual(r["matchup"], "")
                self.assertEqual(r["team"], "")

    def test_toronto_status_is_flagged_not_filled(self):
        rows = [r for r in self.d["rows_newest"] if r.get("team") == "Toronto Raptors"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "")
        self.assertEqual(rows[0]["attribution"], "status_missing")

    def test_diff_reports_no_status_change_on_keyed_rows(self):
        diff = self.d["diff_previous_to_newest"]
        self.assertEqual(diff["status_changes"], [])
        self.assertEqual(diff["added_keyed_rows"], [])
        self.assertEqual(len(diff["unreadable_or_absent_in_newest"]), 10)
        self.assertEqual(diff["unchanged_keyed_rows"], 29)


if __name__ == "__main__":
    unittest.main()
