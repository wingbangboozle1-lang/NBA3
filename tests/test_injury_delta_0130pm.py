"""Session 965fbd17: tests for scripts/injury_delta_0130pm.py.

They pin the counting rule and the published counts so a change to the parser or to the raw
text is caught by CI rather than by a reader. Standard library only.
"""
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/app/injury_delta_0130pm.json"


class InjuryDelta0130PM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "scripts/injury_delta_0130pm.py")], check=True,
                       stdout=subprocess.DEVNULL)
        cls.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_counted_rows_match_the_published_counts(self):
        cnt = self.d["summary"]["counted_attributed_result_counts"]
        self.assertEqual(cnt, {"new_in_raw": 6, "same": 24, "status_changed": 1})
        self.assertEqual(sum(cnt.values()), 31)

    def test_the_only_counted_status_change_is_christie(self):
        changed = [c for c in self.d["comparisons"] if c["result"] == "status_changed"
                   and c["tier"] in ("attributed", "nys_attributed")]
        self.assertEqual([(c["player"], c["stored_status"], c["raw_status"]) for c in changed],
                         [("Christie, Max", "Questionable", "Doubtful")])

    def test_uncounted_tiers_are_never_counted(self):
        tiers = Counter(c["tier"] for c in self.d["comparisons"])
        self.assertEqual(tiers["matchup_no_date"], 14)
        self.assertEqual(tiers["team_no_matchup"], 7)
        self.assertEqual(tiers["nys_partial"], 2)
        self.assertEqual(len(self.d["name_only_not_counted"]), 13)
        self.assertEqual(len(self.d["unattributed_fragments"]), 1)
        counted = [c for c in self.d["comparisons"] if c["tier"] in ("attributed", "nys_attributed")]
        self.assertEqual(len(counted), 31)
        for c in counted:
            self.assertTrue(c["game_date"] and c["matchup"] and c["team"], c)

    def test_name_only_rows_are_never_assigned_a_team(self):
        for r in self.d["name_only_not_counted"]:
            self.assertEqual(r["result"], "name_only_not_counted")
            self.assertNotIn("team", r)

    def test_every_row_points_back_to_a_raw_line(self):
        raw_lines = (ROOT / "data/app/official_injuries_2026-11-14_0130PM_raw.md").read_text(
            encoding="utf-8").splitlines()
        for c in self.d["comparisons"]:
            n = c["raw_line"]
            self.assertTrue(1 <= n <= len(raw_lines), n)
            self.assertTrue(raw_lines[n - 1].startswith("|"), (n, raw_lines[n - 1]))

    def test_output_is_deterministic(self):
        before = OUT.read_text(encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "scripts/injury_delta_0130pm.py")], check=True,
                       stdout=subprocess.DEVNULL)
        self.assertEqual(before, OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
