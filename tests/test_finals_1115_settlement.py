#!/usr/bin/env python3
"""Settlement round tests (session arena/4c69ab99-nba3).

Pin the 2026-11-15 settlement: the nine finals captured from official sources, the OT
schema, the ATL@MIL quarter-conflict handling, the sealed-ledger settlement entries and
the byte-stability of the offline feed rebuild. Everything is offline.

Run: python3 -m unittest tests.test_finals_1115_settlement
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import results_feed  # noqa: E402

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
            self.assertEqual(row["away_ot1"], g["away_ot1"])
            self.assertEqual(row["home_ot1"], g["home_ot1"])
            self.assertEqual(bool(row.get("quarter_conflict")),
                             bool(g.get("quarter_conflict")))
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
        self.assertEqual(row["away_ot1"], 17)
        self.assertEqual(row["home_ot1"], 13)
        self.assertEqual(results_feed.period_sums(row), (112, 108))
        self.assertTrue(row["verified"])
        self.assertEqual(row["quarter_check"], "quarter sums equal the final")

    def test_period_sums_none_without_regulation_quarters(self):
        self.assertIsNone(results_feed.period_sums(
            {"away_q1": 1, "away_q2": 2, "away_q3": None, "away_q4": 4,
             "home_q1": 1, "home_q2": 2, "home_q3": 3, "home_q4": 4}))

    def test_ot2_field_is_summed_when_present(self):
        row = {"away_q1": 10, "away_q2": 10, "away_q3": 10, "away_q4": 10,
               "home_q1": 10, "home_q2": 10, "home_q3": 10, "home_q4": 10,
               "away_ot1": 5, "home_ot1": 5, "away_ot2": 3, "home_ot2": 2,
               "away_pts": 48, "home_pts": 47, "game_id": "X"}
        self.assertEqual(results_feed.period_sums(row), (48, 47))


class QuarterConflictTest(unittest.TestCase):
    def setUp(self):
        self.row = next(g for g in load_feed()["games"] if g.get("game_id") == "0022600243")

    def test_both_readings_are_kept(self):
        # stored reading: MIL Q3 = 27 (summary line, sums to the printed final 106)
        self.assertEqual(self.row["home_q3"], 27)
        # conflicting reading: 37 (period table) — never deleted
        self.assertIn("37", self.row["quarter_conflict_note"])
        self.assertIn("27", self.row["quarter_conflict_note"])

    def test_verify_labels_the_stored_reading(self):
        row = json.loads(json.dumps(self.row))
        results_feed.verify({"games": [row]})
        self.assertTrue(row["verified"])
        self.assertIn("conflicting period reading", row["quarter_check"])

    def test_settle_stamp_names_the_conflict(self):
        row = json.loads(json.dumps(self.row))
        row["settled"] = False
        row["settlement_stamp"] = None
        results_feed.verify({"games": [row]})
        results_feed.settle({"games": [row], "settled_count": 0}, "2026-11-15",
                            now="2026-11-16T18:40Z")
        self.assertTrue(row["settled"])
        self.assertIn("period table conflicts", row["settlement_stamp"])


class LedgerSettlementTest(unittest.TestCase):
    def test_nine_settlement_entries_appended_and_chain_intact(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "pick_ledger.py"),
                            "verify"], capture_output=True, text=True)
        self.assertIn("CHAIN INTACT", r.stdout)
        entries = [json.loads(l) for l in open(LEDGER, encoding="utf-8")]
        settled = [e for e in entries if e["body"]["state"] == "SETTLED"]
        self.assertEqual(len(settled), 9)
        for e in settled:
            self.assertTrue(e["body"]["hash_verified_at_settlement"])
            self.assertIn("official final", e["body"]["settlement_stamp"])
            self.assertEqual(e["body"]["payload_sha256"],
                             next(p["body"]["payload_sha256"] for p in entries
                                  if p["body"].get("payload")
                                  and p["body"]["pick_id"] == e["body"]["pick_id"]))

    def test_settlement_entries_match_the_feed_finals(self):
        feed = {(g["date"], g["away"], g["home"]): g
                for g in load_feed()["games"] if g.get("settled")}
        entries = [json.loads(l) for l in open(LEDGER, encoding="utf-8")]
        published = {e["body"]["pick_id"]: e["body"] for e in entries
                     if e["body"]["state"] == "PUBLISHED_PRE_TIP"}
        for e in entries:
            b = e["body"]
            if b["state"] != "SETTLED":
                continue
            p = published[b["pick_id"]]
            row = feed[(p["date"], p["payload"]["away"], p["payload"]["home"])]
            self.assertEqual(b["final"], {"away_pts": row["away_pts"],
                                          "home_pts": row["home_pts"]})


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
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import round_model_2026_11_16 as rm
        games, _ = rm.game_log()
        keys = [(g["date"], g["away"], g["home"]) for g in games]
        self.assertEqual(len(keys), len(set(keys)), "double-counted game in the closed log")
        self.assertNotIn(("2026-11-15", "ATL", "MIL"), keys,
                         "the quarter-conflicting document must not enter the ratings")
        self.assertIn(("2026-11-15", "IND", "PHI"), keys)


if __name__ == "__main__":
    unittest.main()
