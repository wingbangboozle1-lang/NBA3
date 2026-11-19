#!/usr/bin/env python3
"""Settlement round tests (session arena/4c69ab99-nba3).

Pin the 2026-11-15 settlement against the committed captures: the nine finals read from
official sources (data/app/finals_1115_4c69ab99.json, an independent line-by-line read),
the OT row, the ATL@MIL quarter-conflict handling (both readings kept, never repaired),
the sealed-ledger settlement entries and the byte-stability of the offline feed rebuild.
Everything is offline. The feed schema is the merged-main one (q1..q5 quarter keys,
`flag` field on conflicted rows).

Run: python3 -m unittest tests.test_finals_1115_settlement
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

APP = os.path.join(ROOT, "data", "app")
CAPTURE = os.path.join(APP, "finals_1115_4c69ab99.json")
FEED = os.path.join(APP, "results_feed.json")
LEDGER = os.path.join(APP, "ledger", "ledger.jsonl")


def load_feed():
    return json.load(open(FEED, encoding="utf-8"))


class Finals1115RowsTest(unittest.TestCase):
    def test_every_captured_final_is_in_the_feed_with_exact_cells(self):
        cap = json.load(open(CAPTURE, encoding="utf-8"))["games"]
        feed = {(g["date"], g["away"], g["home"]): g for g in load_feed()["games"]}
        self.assertEqual(len(cap), 9)
        for g in cap:
            row = feed[(g["date"], g["away"], g["home"])]
            self.assertEqual(row.get("game_id"), g["game_id"])
            self.assertEqual(row["away_pts"], g["away_final"])
            self.assertEqual(row["home_pts"], g["home_final"])
            for i in range(4):
                self.assertEqual(row[f"away_q{i + 1}"], g["away_periods"][i])
                self.assertEqual(row[f"home_q{i + 1}"], g["home_periods"][i])
            if g["away_ot1"] is not None:
                self.assertEqual(row.get("away_q5"), g["away_ot1"])
                self.assertEqual(row.get("home_q5"), g["home_ot1"])
            self.assertTrue(row["gamebook"].startswith("https://statsdmz.nba.com/"))

    def test_all_nine_rows_are_settled_and_verified(self):
        rows = [g for g in load_feed()["games"] if g["date"] == "2026-11-15"]
        self.assertEqual(len(rows), 9)
        for g in rows:
            self.assertTrue(g["verified"], g.get("game_id"))
            self.assertTrue(g["settled"], g.get("game_id"))
            self.assertIn("official final", g["settlement_stamp"])
            self.assertIn("2026-11-15", g["settlement_stamp"])


class OvertimeRowTest(unittest.TestCase):
    def test_nyk_tor_ot_period_counts_into_the_sum(self):
        row = next(g for g in load_feed()["games"] if g.get("game_id") == "0022600241")
        self.assertEqual(row["state"], "Final/OT")
        self.assertEqual(row.get("away_q5"), 17)
        self.assertEqual(row.get("home_q5"), 13)
        self.assertTrue(row["verified"])
        # the captured quarters plus OT sum to the printed final for both sides
        self.assertEqual(sum(row[f"away_q{i}"] for i in range(1, 6)), 112)
        self.assertEqual(sum(row[f"home_q{i}"] for i in range(1, 6)), 108)


class QuarterConflictTest(unittest.TestCase):
    def setUp(self):
        self.row = next(g for g in load_feed()["games"] if g.get("game_id") == "0022600243")

    def test_both_readings_are_kept(self):
        # stored reading: MIL Q3 = 27 (game-page LINESCORES + AP recap + summary line,
        # sums to the printed final 106); the game book's period-table reading (37) is
        # recorded in the row's flag text — never deleted, never repaired
        self.assertEqual(self.row["home_q3"], 27)
        flag = self.row.get("flag") or self.row.get("quarter_conflict_note") or ""
        self.assertIn("37", flag)
        self.assertIn("27", flag)

    def test_row_is_settled_on_the_verified_final(self):
        self.assertTrue(self.row["verified"])
        self.assertTrue(self.row["settled"])
        self.assertEqual((self.row["away_pts"], self.row["home_pts"]), (113, 106))


class LedgerSettlementTest(unittest.TestCase):
    def test_settlement_entries_appended_and_chain_intact(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "pick_ledger.py"),
                            "verify"], capture_output=True, text=True)
        self.assertIn("CHAIN INTACT", r.stdout)
        entries = [json.loads(l) for l in open(LEDGER, encoding="utf-8")]
        settled = [e for e in entries if e["body"]["state"] == "SETTLED"]
        # 9 settlements of the 2026-11-15 slate (this session) + 25 of the
        # 2026-11-16..18 slates (session 04a81bce, CR-B1-01), each against an
        # official game book
        self.assertEqual(len(settled), 34)
        for e in settled:
            self.assertIn("official final", e["body"]["settlement_stamp"])

    def test_settlement_entries_match_the_feed_finals(self):
        feed = {(g["date"], g["away"], g["home"]): g
                for g in load_feed()["games"] if g.get("settled")}
        # second official record: the 04a81bce game-book capture (11/16..18)
        q = json.load(open(os.path.join(ROOT, "data", "rounds", "2026-11-19-04a81bce",
                                        "verified", "quarters_2026-11-16_18.json"),
                           encoding="utf-8"))
        for g in q["games"]:
            feed.setdefault((g["date"], g["away"], g["home"]),
                            {"away_pts": g["final"]["away"],
                             "home_pts": g["final"]["home"]})
        entries = [json.loads(l) for l in open(LEDGER, encoding="utf-8")]
        published = {e["body"]["pick_id"]: e["body"] for e in entries
                     if e["body"]["state"] == "PUBLISHED_PRE_TIP"}
        seen = 0
        for e in entries:
            b = e["body"]
            if b["state"] != "SETTLED":
                continue
            p = published[b["pick_id"]]
            row = feed[(p["date"], p["payload"]["away"], p["payload"]["home"])]
            self.assertEqual(b["final"], {"away_pts": row["away_pts"],
                                          "home_pts": row["home_pts"]})
            seen += 1
        self.assertEqual(seen, 34)


class OfflineRebuildTest(unittest.TestCase):
    def test_capture_replay_reproduces_the_feed_byte_for_byte(self):
        before = open(FEED, "rb").read()
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                         "capture_round_79341829.py")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = open(FEED, "rb").read()
        self.assertEqual(before, after,
                         "the offline rebuild changed results_feed.json — the committed "
                         "file must be the replay's output")

    def test_game_log_dedupes_and_excludes_the_conflicting_row(self):
        import round_model_2026_11_16 as rm
        games, _ = rm.game_log()
        keys = [(g["date"], g["away"], g["home"]) for g in games]
        self.assertEqual(len(keys), len(set(keys)), "double-counted game in the closed log")
        self.assertNotIn(("2026-11-15", "ATL", "MIL"), keys,
                         "the quarter-conflicting document must not enter the ratings")
        self.assertIn(("2026-11-15", "IND", "PHI"), keys)


if __name__ == "__main__":
    unittest.main()
