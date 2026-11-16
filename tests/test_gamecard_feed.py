#!/usr/bin/env python3
"""Tests for the official game-card feed parser (session arena/4054e125-nba3).

The committed capture at data/app/refresh/2026-11-16T00-57Z/games_2026-11-15.html is a
REAL official games page as downloaded by the scheduled refresh. Its card feed carried
four finished games at capture time; the parser must accept exactly those (period sums
equal the printed finals) and skip the live/scheduled cards without inventing rows.
"""
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import gamecard_feed  # noqa: E402

CAPTURE = os.path.join(ROOT, "data", "app", "refresh", "2026-11-16T00-57Z",
                       "games_2026-11-15.html")


class GameCardFeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CAPTURE, encoding="utf-8", errors="replace") as fh:
            cls.cards = gamecard_feed.parse_games_page(fh.read())

    def test_parses_all_nine_cards(self):
        self.assertEqual(len(self.cards), 9)
        ids = {c["gameId"] for c in self.cards}
        self.assertIn("0022600236", ids)
        self.assertIn("0022600244", ids)

    def test_finished_rows_accept_only_finals_with_summing_periods(self):
        rows, rejected = gamecard_feed.finished_rows(self.cards)
        by_id = {r["game_id"]: r for r in rows}
        # the four games that were Final at capture time
        self.assertEqual(set(by_id), {"0022600236", "0022600237", "0022600238", "0022600239"})
        self.assertEqual(rejected, [])
        r = by_id["0022600236"]
        self.assertEqual((r["away"], r["home"]), ("IND", "PHI"))
        self.assertEqual((r["away_pts"], r["home_pts"]), (124, 131))
        self.assertEqual(r["away_q"], [35, 22, 30, 37])
        self.assertEqual(r["home_q"], [29, 29, 39, 34])
        self.assertEqual(r["state"], "Final")
        self.assertEqual(r["date"], "2026-11-15")
        for row in rows:
            self.assertEqual(sum(row["away_q"]), row["away_pts"])
            self.assertEqual(sum(row["home_q"]), row["home_pts"])

    def test_live_and_scheduled_cards_are_not_ingested(self):
        rows, rejected = gamecard_feed.finished_rows(self.cards)
        ids = {r["game_id"] for r in rows} | {b["game_id"] for b in rejected}
        self.assertNotIn("0022600240", ids)   # was live (Q4 3:52) at capture time
        self.assertNotIn("0022600243", ids)   # was scheduled at capture time

    def test_sum_mismatch_rejects_row_and_records_reason(self):
        bad = {
            "gameId": "0022600999", "gameStatusText": "Final",
            "gameTimeEastern": "2026-11-15T20:00:00Z", "shareUrl": "https://www.nba.com/game/x",
            "awayTeam": {"teamTricode": "AAA", "score": 100, "periods": [
                {"period": 1, "score": 30}, {"period": 2, "score": 30},
                {"period": 3, "score": 30}, {"period": 4, "score": 30}]},
            "homeTeam": {"teamTricode": "BBB", "score": 90, "periods": [
                {"period": 1, "score": 37}, {"period": 2, "score": 30},
                {"period": 3, "score": 10}, {"period": 4, "score": 13}]},
        }
        rows, rejected = gamecard_feed.finished_rows([bad])
        self.assertEqual(rows, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("do not equal printed finals", rejected[0]["reason"])
        # both sums and both printed finals are reported; nothing is repaired
        self.assertIn("120/90", rejected[0]["reason"])
        self.assertIn("100/90", rejected[0]["reason"])

    def test_missing_periods_rejected(self):
        bad = {"gameId": "0022600998", "gameStatusText": "Final",
               "awayTeam": {"teamTricode": "AAA", "score": 100, "periods": []},
               "homeTeam": {"teamTricode": "BBB", "score": 90, "periods": []}}
        rows, rejected = gamecard_feed.finished_rows([bad])
        self.assertEqual(rows, [])
        self.assertIn("without score or period scores", rejected[0]["reason"])


if __name__ == "__main__":
    unittest.main()
