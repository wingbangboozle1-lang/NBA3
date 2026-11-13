"""Unit tests for pipeline/rotation.py (synthetic minutes only)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import redistribute_minutes  # noqa: E402


def total(new, residual):
    return sum(new.values()) + residual


class RotationTests(unittest.TestCase):
    def test_pro_rata_redistribution_conserves_minutes(self):
        baseline = {"A": 30.0, "B": 20.0, "C": 10.0, "D": 20.0, "E": 20.0, "F": 20.0,
                    "G": 20.0, "H": 20.0, "I": 20.0, "J": 20.0, "K": 20.0}
        # Team total = sum of synthetic baseline minutes (220 here)
        team = sum(baseline.values())
        new, residual = redistribute_minutes(baseline, ["A"], team_minutes=team, cap=48.0)
        self.assertAlmostEqual(total(new, residual), team, places=9)
        self.assertNotIn("A", new)
        self.assertAlmostEqual(residual, 0.0, places=9)
        # Remaining baseline minutes sum to 190; B (20 of 190) receives 20/190 of A's 30 minutes
        self.assertAlmostEqual(new["B"], 20.0 + 30.0 * 20.0 / 190.0, places=9)

    def test_cap_limits_each_player_and_spills_to_others(self):
        baseline = {"A": 30.0, "B": 30.0, "C": 10.0}
        new, residual = redistribute_minutes(baseline, ["C"], team_minutes=70.0, cap=35.0)
        self.assertLessEqual(max(new.values()), 35.0 + 1e-9)
        self.assertAlmostEqual(total(new, residual), 70.0, places=9)

    def test_residual_reported_when_everyone_capped(self):
        baseline = {"A": 20.0, "B": 20.0, "C": 20.0}
        new, residual = redistribute_minutes(baseline, ["C"], team_minutes=60.0, cap=20.0)
        self.assertAlmostEqual(new["A"], 20.0)
        self.assertAlmostEqual(new["B"], 20.0)
        self.assertAlmostEqual(residual, 20.0)

    def test_unknown_out_player_rejected(self):
        with self.assertRaises(ValueError):
            redistribute_minutes({"A": 10.0}, ["Z"], team_minutes=10.0, cap=20.0)

    def test_requires_explicit_cap_and_total(self):
        with self.assertRaises(TypeError):
            redistribute_minutes({"A": 10.0}, [], team_minutes=10.0)  # cap missing


if __name__ == "__main__":
    unittest.main()
