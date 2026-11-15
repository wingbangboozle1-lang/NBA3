"""Regression tests for the two schedule-union bugs found while building rest/travel.

Both bugs produced plausible-looking output, which is why they are pinned here:

1. The 11/14 finals lived only in the settled feed while `data/origin/games.csv` stopped at 11/13.
   Reading either source alone silently dropped 5 games, and every back-to-back across that seam
   disappeared (0 back-to-backs instead of 8).
2. The 4-day window excluded the current game, so PHX playing 11/13, 11/15 and 11/16 was not
   reported as 3-in-4.

A third bug arrived with the rebase: once another session extended `games.csv` to 11/14, counting
rows instead of distinct games double-counted every 11/14 club and failed a games-played check that
should pass. That one is pinned in scripts/repo_review.py (R9) and covered here too.
"""

import datetime as dt
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rest_travel  # noqa: E402


class ScheduleUnionTests(unittest.TestCase):
    def test_union_covers_the_whole_window(self):
        rows, prov = rest_travel.load_schedule()
        dates = sorted({r["date"] for r in rows})
        self.assertEqual(dates[0], "2026-10-20")
        self.assertGreaterEqual(dates[-1], "2026-11-15")
        # the settled 11/14 feed must be represented even if the CSV lags
        self.assertIn("2026-11-14", dates)
        seams = {s["seam"] for s in prov["sources"]}
        self.assertEqual(seams, {"origin", "settled", "slate"})

    def test_back_to_backs_exist_across_the_seam(self):
        payload = rest_travel.build()
        b2b = [t for g in payload["games"] for t in g["teams"] if t["back_to_back"]]
        self.assertTrue(b2b, "no back-to-backs found -- the 11/14 seam was probably dropped again")
        for t in b2b:
            self.assertEqual(t["rest_days"], 0)

    def test_three_in_four_includes_the_current_game(self):
        payload = rest_travel.build()
        for g in payload["games"]:
            for t in g["teams"]:
                self.assertGreaterEqual(t["games_in_4_day_window"], 1)
                if t["back_to_back"]:
                    # a back-to-back is necessarily at least the second game in a 4-day window
                    self.assertGreaterEqual(t["games_in_4_day_window"], 2)

    def test_every_team_game_has_an_explicit_travel_state(self):
        payload = rest_travel.build()
        for g in payload["games"]:
            for t in g["teams"]:
                self.assertIn(t["travel"]["status"], ("SOURCED", "UNVERIFIED"))
                if t["travel"]["status"] == "UNVERIFIED":
                    self.assertIsNone(t["travel"]["km"],
                                      "an unverified distance must be null, never a guessed number")

    def test_distinct_games_union_does_not_double_count(self):
        """The exact arithmetic that failed R9 after the rebase."""
        games = []
        with (ROOT / "data" / "origin" / "games.csv").open() as fh:
            import csv
            games = list(csv.DictReader(fh))
        settled = json.loads((ROOT / "data" / "live" / "results"
                              / "settled_2026-11-14.json").read_text())["games"]
        union = {g["game_id"]: (g["home"], g["away"]) for g in games}
        before = len(union)
        for g in settled:
            union.setdefault(g["game_id"], (g["home"], g["away"]))
        self.assertEqual(len(union), before,
                         "the settled feed duplicates games already in the capture; union by game_id")
        # and no club may be counted twice for the same game
        for gid, (h, a) in union.items():
            self.assertNotEqual(h, a)


if __name__ == "__main__":
    unittest.main()
