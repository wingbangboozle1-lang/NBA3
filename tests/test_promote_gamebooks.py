#!/usr/bin/env python3
"""Offline tests for scripts/promote_gamebooks.py (session arena/c94a5531-nba3).

The parser is fed the committed verbatim game-book transcriptions (the same text
the runner extracts from the fetched PDFs) — no network.
Run: python3 -m unittest tests/test_promote_gamebooks.py
"""
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import promote_gamebooks as pg  # noqa: E402

BOOK = os.path.join(ROOT, "data", "app", "gamebooks_20261115",
                    "20261115_INDPHI_c94a5531.md")


class ParseBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = open(BOOK, encoding="utf-8").read()
        cls.book = pg.parse_book_text(cls.text, "https://example.test/book.pdf")

    def test_quarters_sum_to_printed_finals(self):
        self.assertTrue(self.book["ok"], self.book["finals"])
        self.assertEqual(self.book["finals"], {"away": 124, "home": 131})
        self.assertEqual(self.book["quarters"]["away"], [35, 22, 30, 37])
        self.assertEqual(self.book["quarters"]["home"], [29, 29, 39, 34])

    def test_teams_resolved_to_abbreviations(self):
        self.assertEqual(self.book["teams"]["away"]["abbr"], "IND")
        self.assertEqual(self.book["teams"]["home"]["abbr"], "PHI")

    def test_player_points_sum_to_team_finals(self):
        for side, abbr in (("away", "IND"), ("home", "PHI")):
            s = sum(p["pts"] for p in self.book["players"]
                    if p["team"] == abbr and p["status"] == "played")
            self.assertEqual(s, self.book["finals"][side])

    def test_player_lines_carry_min_pts_reb_ast(self):
        # the parsed line must agree with the scoreboard card's Game Leaders
        # (Maxey 27 PTS / 4 REB / 6 AST on the 11/15 IND@PHI card)
        rows = [p for p in self.book["players"] if p["player"] == "Tyrese Maxey"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pts"], 27)
        self.assertEqual(rows[0]["reb"], 4)
        self.assertEqual(rows[0]["ast"], 6)


class PromoteIdempotentTests(unittest.TestCase):
    def test_promote_never_duplicates_rows(self):
        text = open(BOOK, encoding="utf-8").read()
        feed = {"games": [], "count": 0, "settled_count": 0}
        logs = {"rows": [], "count": 0}
        shares = {"teams": {}}
        ok1 = pg.promote(BOOK, text, feed, logs, shares)
        ok2 = pg.promote(BOOK, text, feed, logs, shares)
        self.assertTrue(ok1 and ok2)
        self.assertEqual(len(feed["games"]), 1)
        self.assertEqual(len([r for r in logs["rows"] if r["date"] == "2026-11-15"]), len(logs["rows"]))
        # promotion preserves settlement state that is already stamped
        feed["games"][0]["settled"] = True
        feed["games"][0]["settlement_stamp"] = "settled at ... (kept)"
        pg.promote(BOOK, text, feed, logs, shares)
        self.assertEqual(feed["games"][0]["settlement_stamp"], "settled at ... (kept)")

    def test_failed_book_is_flagged_not_guessed(self):
        feed = {"games": [], "count": 0, "settled_count": 0}
        logs = {"rows": [], "count": 0}
        shares = {"teams": {}}
        bad = "| SCORE BY PERIOD | 1 | 2 | 3 | 4 | FINAL |\n| A | 1 | 1 | 1 | 1 | 5 |\n"
        self.assertFalse(pg.promote("x/20261116_BOSCLE.md", bad, feed, logs, shares))
        self.assertEqual(feed["games"], [])


if __name__ == "__main__":
    unittest.main()
