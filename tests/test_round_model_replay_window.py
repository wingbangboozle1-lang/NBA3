"""The 2026-11-16 round's model must replay byte-for-byte as the feed grows.

Why this test exists: the Pages build rebuilds `scripts/round_model_2026_11_16.py` and
then fails if `data/rounds/2026-11-16/` changed. That model read
`data/app/results_feed.json` -- a *live* artefact that later game days keep appending to
(it went 23 -> 46 rows on 2026-11-19). With no window the replay learned from games played
after the round priced its slate, so it republished different lines (home-court pin 4.12 ->
-1.35 points, ridge 0.1 -> 1.0) and the drift check failed on every run after 2026-11-17.
That is the red `11/16 refresh gates, two-estimator model and the round dashboard` step in
PR #143's build (run 44471618213).

The invariant pinned here is a correctness rule as well as a reproducibility one: a line
originated for 2026-11-16..18 may only learn from finals dated on or before 2026-11-15.
"""

import builtins
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import round_model_2026_11_16 as M      # noqa: E402

FEED = os.path.join(ROOT, "data", "app", "results_feed.json")
MODEL = os.path.join(ROOT, "data", "rounds", "2026-11-16", "model.json")


class TestReplayWindow(unittest.TestCase):
    def test_log_end_is_the_day_before_the_priced_slate(self):
        self.assertEqual(M.LOG_END, "2026-11-15")
        self.assertEqual(M.LOG_END, M.load("slate.json")["window"]["from"] and M.LOG_END)

    def test_no_game_after_the_cutoff_enters_the_log(self):
        games, results = M.game_log()
        self.assertTrue(games, "empty learning log")
        for g in games:
            self.assertLessEqual(g["date"], M.LOG_END,
                                 "a game played after the priced slate entered the ratings")
        for r in results["rows"]:
            self.assertLessEqual(r["date"], M.LOG_END)

    def test_the_published_model_uses_the_frozen_window(self):
        with open(MODEL, encoding="utf-8") as fh:
            published = json.load(fh)
        games, _ = M.game_log()
        self.assertEqual(published["input_games"]["settled_finals_used"], len(games))
        self.assertEqual(published["input_games"]["date_range"],
                         [games[0]["date"], games[-1]["date"]])
        self.assertLessEqual(published["input_games"]["date_range"][1], M.LOG_END)

    def test_a_later_game_day_does_not_change_the_replay(self):
        """Point the model at a copy of the feed with a later final appended.

        The learning log must be identical: a game played after 2026-11-15 cannot inform a
        line originated for 2026-11-16..18, and reading it would also break byte-identical
        replay of the committed artefacts.
        """
        with open(FEED, encoding="utf-8") as fh:
            feed = json.load(fh)
        self.assertTrue(any(g["date"] > M.LOG_END for g in feed["games"]),
                        "the live feed should already reach past the frozen window; "
                        "if it does not, this test cannot prove anything")
        grown = json.loads(json.dumps(feed))
        grown["games"].append({
            "date": "2026-12-01", "game_id": "0022600999", "away": "BOS", "home": "GSW",
            "away_pts": 101, "home_pts": 99, "state": "Final", "settled": True,
            "verified": True, "verified_from": "https://www.nba.com/games?date=2026-12-01",
        })
        grown["count"] = len(grown["games"])
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                          encoding="utf-8")
        with tmp as fh:
            json.dump(grown, fh)
        self.addCleanup(os.unlink, tmp.name)

        before, _ = M.game_log()
        real_open = builtins.open

        def fake_open(path, *a, **k):
            if os.path.abspath(str(path)) == os.path.abspath(FEED):
                return real_open(tmp.name, *a, **k)
            return real_open(path, *a, **k)

        builtins.open = fake_open
        try:
            after, _ = M.game_log()
        finally:
            builtins.open = real_open
        self.assertEqual([(g["date"], g["away"], g["home"]) for g in before],
                         [(g["date"], g["away"], g["home"]) for g in after],
                         "the learning log changed when a later game day was added to the feed")


if __name__ == "__main__":
    unittest.main()
