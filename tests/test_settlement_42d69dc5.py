#!/usr/bin/env python3
"""Settlement from official finals (session arena/42d69dc5-nba3).

What this pins, and why each guard exists:

* Only a final with TWO official read URLs may settle. A scoreboard snapshot is not a final.
* The printed quarter scores must sum to the printed final for both teams.
* The settlement stamp must be the moment the final was confirmed and must be later than the end of
  the game's own day. The first settlement written this session stamped 12:10Z on a game that tipped
  at 18:00Z; that guard now refuses it.
* The ledger chain still verifies after a settlement is appended, and the settlement repeats the
  hash published before tip.
"""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publish_picks  # noqa: E402
import ledger  # noqa: E402

FEED = ROOT / "data" / "live" / "results" / "settled_2026-11-15.json"
VIEW = ROOT / "data" / "live" / "picks_ledger_view.json"


class FinalFeedTest(unittest.TestCase):
    def setUp(self):
        self.feed = json.loads(FEED.read_text())

    def test_every_published_final_has_two_official_reads(self):
        for g in self.feed["games"]:
            self.assertTrue(g["verified"], g["game_id"])
            self.assertTrue(g["source_url"].startswith("https://www.nba.com/game/"), g["game_id"])
            self.assertTrue(g["gamebook_url"].startswith("https://statsdmz.nba.com/pdfs/"), g["game_id"])

    def test_quarters_sum_to_the_printed_final(self):
        for g in self.feed["games"]:
            self.assertEqual(sum(g["away_q"]), g["away_final"], g["game_id"])
            self.assertEqual(sum(g["home_q"]), g["home_final"], g["game_id"])

    def test_the_final_matches_the_two_official_reads_character_for_character(self):
        """IND 124 — PHI 131, read from the nba.com game page and from the game book."""
        g = self.feed["games"][0]
        self.assertEqual((g["away"], g["home"], g["away_final"], g["home_final"]),
                         ("IND", "PHI", 124, 131))
        self.assertEqual(g["away_q"], [35, 22, 30, 37])
        self.assertEqual(g["home_q"], [29, 29, 39, 34])
        local = (ROOT / "data" / "live" / "raw" / "gamebook_20261115_INDPHI.md").read_text()
        self.assertIn("| Pacers | 35 | 22 | 30 | 37 | 124 |", local)
        self.assertIn("| 76ERS | 29 | 29 | 39 | 34 | 131 |", local)

    def test_games_not_read_twice_are_not_settled(self):
        self.assertLess(self.feed["counts"]["captured"], self.feed["counts"]["games_on_date"])
        self.assertIn("NOT settled", self.feed["coverage_note"])
        self.assertEqual(len(self.feed["games"]), self.feed["counts"]["captured"])


class StampTest(unittest.TestCase):
    def test_accepts_a_stamp_after_the_game_day_ends(self):
        final = {"game_id": "x", "date": "2026-11-15", "settled_utc": "2026-11-16T00:05Z"}
        self.assertEqual(publish_picks.settlement_stamp(final, "2026-11-15T12:10Z"), "2026-11-16T00:05Z")

    def test_refuses_a_stamp_before_the_game_day_ends(self):
        final = {"game_id": "x", "date": "2026-11-15", "settled_utc": "2026-11-15T12:10Z"}
        with self.assertRaises(ValueError) as ctx:
            publish_picks.settlement_stamp(final, "2026-11-15T12:10Z")
        self.assertIn("precedes the end of its own game day", str(ctx.exception))

    def test_refuses_a_missing_stamp_rather_than_inventing_one(self):
        with self.assertRaises(ValueError) as ctx:
            publish_picks.settlement_stamp({"game_id": "x", "date": "2026-11-15"}, "2026-11-16T00:00Z")
        self.assertIn("refusing to invent a settlement time", str(ctx.exception))


class LedgerViewTest(unittest.TestCase):
    def setUp(self):
        self.view = json.loads(VIEW.read_text())
        self.settled = [e for e in self.view["entries"] if e["kind"] == "SETTLE"]

    def test_chain_verifies(self):
        self.assertTrue(self.view["integrity"]["verified"], self.view["integrity"]["problems"])
        self.assertEqual(self.view["integrity"]["problems"], [])

    def test_the_settlement_repeats_the_hash_published_before_tip(self):
        for e in self.settled:
            published = [p for p in self.view["entries"]
                         if p["kind"] == "PUBLISH" and p["pick"]["game_id"] == e["game_id"]]
            self.assertTrue(published, e["game_id"])
            self.assertEqual(e["pick_sha256_at_publish"], published[-1]["pick_sha256"])
            self.assertEqual(e["pick_sha256"], published[-1]["pick_sha256"])

    def test_settlement_is_not_stamped_before_its_own_game(self):
        for e in self.settled:
            self.assertGreater(e["settled_utc"], e["pick"]["date"] + "T23:59Z",
                               f"{e['game_id']}: settlement stamped {e['settled_utc']}")

    def test_every_open_pick_on_an_ended_game_day_is_published(self):
        """Rows that cannot be graded yet appear in outstanding_picks rather than vanishing."""
        for o in self.view.get("outstanding_picks", []):
            self.assertTrue(o["why_open"])
            self.assertTrue(o["game_id"])
            self.assertNotIn(o["game_id"], {e["game_id"] for e in self.settled})

    def test_the_one_verified_final_graded_a_win(self):
        g = next(e for e in self.settled if e["game_id"] == "0022600236")
        self.assertEqual(g["pick"]["pick"], "PHI moneyline")
        # PHI won 131-124, and the pick was the PHI moneyline: WIN by the pick's own rule.
        self.assertEqual(g["result"]["outcome"], "WIN")
        self.assertGreater(g["final"]["home_final"], g["final"]["away_final"])


class FeedSelectionTest(unittest.TestCase):
    def test_every_settled_feed_on_disk_is_read(self):
        feeds = publish_picks.SETTLED_FEEDS
        self.assertGreaterEqual(len(feeds), 2, "a single hard-coded feed was the defect")
        names = {p.name for p in feeds}
        self.assertIn("settled_2026-11-14.json", names)
        self.assertIn("settled_2026-11-15.json", names)

    def test_a_final_without_both_reads_cannot_settle(self):
        src = (ROOT / "scripts" / "publish_picks.py").read_text()
        self.assertIn("if not g.get(\"gamebook_url\") or not g.get(\"source_url\"):", src)
        self.assertIn('g["verified"] = False', src)


if __name__ == "__main__":
    unittest.main()
