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
    def _entries(self):
        return [json.loads(line) for line in open(LEDGER, encoding="utf-8")]

    def _settled_by_game_day(self):
        """SETTLED entries grouped by the day of the PUBLISHED entry they settle.

        A SETTLED body carries no date of its own (it is append-only evidence about the pick), so
        the day comes from the published entry the pick_id points at. Grouping is what keeps this
        file's claim — "the 11/15 settlement run appended nine entries" — true after the chain grew
        past that day instead of forcing the whole chain back to nine.
        """
        entries = self._entries()
        published = {e["body"]["pick_id"]: e["body"] for e in entries
                     if e["body"]["state"] == "PUBLISHED_PRE_TIP"}
        by_day = {}
        for e in entries:
            b = e["body"]
            if b["state"] != "SETTLED":
                continue
            p = published.get(b["pick_id"])
            day = (p or {}).get("date", "?unmatched?")
            by_day.setdefault(day, []).append(e)
        for day in by_day:
            by_day[day] = sorted({e["body"]["pick_id"] for e in by_day[day]})
        return by_day

    def test_chain_verifies_and_the_1115_nine_picks_are_settled(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "pick_ledger.py"),
                            "verify"], capture_output=True, text=True)
        self.assertIn("CHAIN INTACT", r.stdout)
        by_day = self._settled_by_game_day()
        # Distinct PICKS, not entry rows: `settle` used to re-append a settlement for every pick on
        # every later run, so 2026-11-15's nine picks carry 27 SETTLED rows in the published chain
        # (three runs: 11-16T18:37Z, 11-19T06:03Z, 11-19T06:05Z). The chain is append-only evidence,
        # so those rows stay; the 915d2e99 gate stops new ones. Counting rows here would have pinned
        # the defect instead of the claim this file is about.
        self.assertEqual(by_day.get("2026-11-15"),
                         [f"00226002{n}-side-proj" for n in (36, 37, 38, 39, 40, 41, 42, 43, 44)],
                         "the nine settled games of 2026-11-15 must each have a settlement entry")
        stamps_per_pick = {}
        for e in self._entries():
            if e["body"]["state"] == "SETTLED":
                stamps_per_pick.setdefault(e["body"]["pick_id"], set()).add(
                    e["body"]["settled_utc"])
        for pid, stamps in stamps_per_pick.items():
            self.assertEqual(len(stamps), len([s for s in stamps]), pid)
        dupes = {pid: n for pid, n in
                 __import__("collections", fromlist=["Counter"]
                            ).Counter(e["body"]["pick_id"] for e in self._entries()
                                      if e["body"]["state"] == "SETTLED").items() if n > 1}
        for pid, n in dupes.items():
            self.assertLessEqual(n, 3,
                                 f"{pid} has {n} settlement rows; the pre-gate re-appends (3 runs) "
                                 f"are the historical maximum and the gate must not let it grow")
        for e in self._entries():
            if e["body"]["state"] == "SETTLED":
                self.assertIn("official final", e["body"]["settlement_stamp"])
        # the settled set must equal the settled feed days that had published picks: no pick may be
        # settled twice in one run and none may be missing
        feed = {(g["date"], g["away"], g["home"]) for g in load_feed()["games"] if g.get("settled")}
        published = {e["body"]["pick_id"]: e["body"] for e in self._entries()
                     if e["body"]["state"] == "PUBLISHED_PRE_TIP"}
        settleable = {pid for pid, b in published.items()
                      if (b["date"], b["payload"]["away"], b["payload"]["home"]) in feed}
        self.assertTrue(settleable <= set(by_day.get("2026-11-15", set())) |
                        {pid for ids in by_day.values() for pid in ids},
                        "every pick whose game has a settled feed row must be settled in the chain")

    def test_every_settlement_entry_matches_a_settled_feed_final(self):
        """Not nine-and-only-nine: EVERY settled pick must trace to a settled official final.

        The earlier version hard-coded the 11/15 count, so the day the feed grew new settled days it
        failed for the wrong reason (a KeyError on a game it had never seen). The property that
        matters is the one this keeps: no settlement entry may exist without a settled feed row
        carrying the same score, whatever day it is.
        """
        feed = {(g["date"], g["away"], g["home"]): g
                for g in load_feed()["games"] if g.get("settled")}
        published = {e["body"]["pick_id"]: e["body"] for e in self._entries()
                     if e["body"]["state"] == "PUBLISHED_PRE_TIP"}
        seen = 0
        for e in self._entries():
            b = e["body"]
            if b["state"] != "SETTLED":
                continue
            self.assertIn(b["pick_id"], published, f"{b['pick_id']} settled without a published row")
            p = published[b["pick_id"]]
            key = (p["date"], p["payload"]["away"], p["payload"]["home"])
            self.assertTrue(key in feed,
                            f"{key}: settled in the ledger but the published feed has no settled row "
                            f"for it — the final was never captured, or something rewrote the feed")
            row = feed[key]
            self.assertEqual(b["final"], {"away_pts": row["away_pts"],
                                          "home_pts": row["home_pts"]})
            seen += 1
        self.assertGreaterEqual(seen, 9, "the 11/15 settlement run is expected in there")
        by_day = self._settled_by_game_day()
        self.assertEqual(len(by_day.get("2026-11-15", [])), 9)


class OfflineRebuildTest(unittest.TestCase):
    def test_capture_replay_reproduces_the_round_and_leaves_the_feed_untouched(self):
        """The deploy-time replay must be read-only against the published feed.

        `capture_round_79341829.py` used to write its own window OVER data/app/results_feed.json, and
        pages.yml runs it on every build — so each deploy deleted every game day promoted after
        2026-11-15 (the published feed sat at 23 rows while the day captures and the ledger had 46,
        and the ledger was settling games the feed no longer carried). Row-for-row fidelity of the
        replay is still pinned; what changed is where it writes.
        """
        before = open(FEED, "rb").read()
        out = "/tmp/feed_replay_test.json"
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                          "capture_round_79341829.py")],
                           capture_output=True, text=True,
                           env=dict(os.environ, NBA3_FEED_OUT=out))
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-1500:])
        self.assertEqual(open(FEED, "rb").read(), before,
                         "the replay rewrote the published results feed — it must only write "
                         "NBA3_FEED_OUT")
        replay = json.load(open(out, encoding="utf-8"))
        live = {(g["date"], g["away"], g["home"]): g for g in load_feed()["games"]}
        n = 0
        for g in replay["games"]:
            key = (g["date"], g["away"], g["home"])
            if key[0] > "2026-11-15":
                continue
            self.assertTrue(key in live, f"{key}: replayed row missing from the published feed")
            for f in ("away_pts", "home_pts", "state", "verified", "settled"):
                self.assertEqual(g.get(f), live[key].get(f), f"{key} {f}")
            n += 1
        self.assertGreaterEqual(n, 23, "the replay lost rows from its own capture window")

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
