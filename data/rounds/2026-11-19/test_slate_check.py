"""Pins the 11/19-11/21 official games capture (session de0caf5d, X3)."""
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class SlateCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "slate_check.json"), encoding="utf-8") as fh:
            cls.d = json.load(fh)

    def test_counts_match_calendar_cells(self):
        self.assertEqual(self.d["captured_counts"], {"2026-11-19": 4, "2026-11-20": 9, "2026-11-21": 6})
        self.assertEqual(self.d["captured_counts"], self.d["calendar_counts"])

    def test_every_row_has_an_official_source_link(self):
        for g in self.d["games"]:
            self.assertTrue(g["source_url"].startswith("https://www.nba.com/games?date="), g["game_id"])
            self.assertTrue(g["game_url"].startswith("https://www.nba.com/game/"), g["game_id"])

    def test_game_ids_are_unique(self):
        ids = [g["game_id"] for g in self.d["games"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_committed_counts_agree(self):
        for day, check in self.d["count_cross_check"].items():
            self.assertTrue(check["match"], day)

    def test_eleven_nineteen_rows_agree_with_committed_slate(self):
        for g in self.d["games"]:
            if g["date"] == "2026-11-19":
                self.assertEqual(g["committed_slate_check"], "match", g["game_id"])

    def test_non_chronological_ids_are_flagged(self):
        self.assertTrue(any("not chronological" in f for f in self.d["flags"]))


if __name__ == "__main__":
    unittest.main()
