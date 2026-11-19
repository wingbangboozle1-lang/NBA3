#!/usr/bin/env python3
"""Tests for the tamper-evident pick ledger (session arena/79341829-nba3)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pick_ledger  # noqa: E402

# The committed window (2026-11-15..18) is all after this instant, so every row is pre-tip
# and the date gates are deterministic. The clock-dependent gates have their own tests below.
EARLY = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


class PickLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        pick_ledger.LEDGER_DIR = self.tmp
        pick_ledger.LEDGER = os.path.join(self.tmp, "ledger.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_publish_then_verify_chain_intact(self):
        self.assertEqual(pick_ledger.publish(now_utc=EARLY), 0)
        self.assertEqual(pick_ledger.verify(), 0)
        entries = pick_ledger.read_entries()
        # Roll-safe (session arena/4c69ab99-nba3): the expected set is derived from the
        # CURRENT priced window and the CURRENT promoted slate — a window-count pin broke
        # whenever the scheduled refresh rolled the window.
        est = json.load(open(pick_ledger.EST, encoding="utf-8"))
        slate = json.load(open(pick_ledger.SLATE, encoding="utf-8"))
        on_slate = {(g["date"], g["game_id"]) for g in slate["games"]}
        expect = {f"{r['game_id']}-side-proj" for r in est["window"]
                  if (r["date"], r["game_id"]) in on_slate}
        self.assertEqual({e["body"]["pick_id"] for e in entries}, expect)
        self.assertGreater(len(expect), 0, "the priced window publishes nothing — empty pin")
        for e in entries:
            self.assertEqual(e["body"]["state"], "PUBLISHED_PRE_TIP")
            self.assertTrue(e["body"]["payload_sha256"])
            self.assertTrue(e["body"]["published_utc"])

    def test_publish_is_idempotent(self):
        pick_ledger.publish(now_utc=EARLY)
        n1 = len(pick_ledger.read_entries())
        pick_ledger.publish(now_utc=EARLY)
        self.assertEqual(len(pick_ledger.read_entries()), n1)

    def test_tampered_payload_breaks_verify(self):
        pick_ledger.publish(now_utc=EARLY)
        entries = pick_ledger.read_entries()
        entries[3]["body"]["payload"]["blend_margin"] = 99.0   # silent historical edit
        pick_ledger.write_entries(entries)
        self.assertEqual(pick_ledger.verify(), 1)

    def test_broken_chain_detected(self):
        pick_ledger.publish(now_utc=EARLY)
        entries = pick_ledger.read_entries()
        entries.pop(2)                                          # removed history
        pick_ledger.write_entries(entries)
        self.assertEqual(pick_ledger.verify(), 1)

    def test_settlement_uses_official_final_only(self):
        pick_ledger.publish(now_utc=EARLY)
        est = json.load(open(pick_ledger.EST, encoding="utf-8"))
        target = est["window"][0]
        feed = {"games": [{
            "date": target["date"], "away": target["away"], "home": target["home"],
            "away_pts": 100, "home_pts": 110, "state": "Final",
            "verified": True, "settled": True,
            "settlement_stamp": "settled from the official final",
        }]}
        saved = pick_ledger.FEED
        try:
            pick_ledger.FEED = os.path.join(self.tmp, "feed.json")
            with open(pick_ledger.FEED, "w", encoding="utf-8") as fh:
                json.dump(feed, fh)
            pick_ledger.settle()
            entries = pick_ledger.read_entries()
            settled = [e for e in entries if e["body"]["state"] == "SETTLED"]
            self.assertEqual(len(settled), 1)
            self.assertEqual(settled[0]["body"]["final"], {"away_pts": 100, "home_pts": 110})
            self.assertIn(settled[0]["body"]["settlement_stamp"], ("settled from the official final",))
            self.assertTrue(settled[0]["body"]["hash_verified_at_settlement"])
        finally:
            pick_ledger.FEED = saved


def _row(gid, day, tip, away="AAA", home="BBB"):
    return {"game_id": gid, "date": day, "tip_et": tip, "away": away, "home": home,
            "blend_margin": 1.0, "blend_total": 200.0, "disagreement_abs": 2.0,
            "est_a_margin": 0.5, "est_b_margin": 1.5, "hca_points_pinned": 1.1}


class PublishGateTests(unittest.TestCase):
    """Publish only what is provably before tip; one entry per game id (session c449d46a)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = (pick_ledger.LEDGER_DIR, pick_ledger.LEDGER)
        pick_ledger.LEDGER_DIR = self.tmp
        pick_ledger.LEDGER = os.path.join(self.tmp, "ledger.jsonl")
        self.est = os.path.join(self.tmp, "est.json")
        self.slate = os.path.join(self.tmp, "slate.json")

    def tearDown(self):
        pick_ledger.LEDGER_DIR, pick_ledger.LEDGER = self.saved
        shutil.rmtree(self.tmp)

    def _write(self, rows, slate_pairs):
        with open(self.est, "w", encoding="utf-8") as fh:
            json.dump({"window": rows}, fh)
        with open(self.slate, "w", encoding="utf-8") as fh:
            json.dump({"games": [{"date": d, "game_id": g} for d, g in slate_pairs]}, fh)

    def _publish(self, now):
        return pick_ledger.publish(now_utc=now, est_path=self.est, slate_path=self.slate)

    def _ids(self):
        return [e["body"]["pick_id"] for e in pick_ledger.read_entries()]

    def test_same_game_id_on_four_dates_is_published_once(self):
        # The 2026-11-16 run appended one game four times (the leaked DAL@CLE rows).
        rows = [_row("0022600232", d, None, "DAL", "CLE")
                for d in ("2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18")]
        self._write(rows, [("2026-11-17", "0022600232")])
        self._publish(EARLY)
        self.assertEqual(self._ids(), ["0022600232-side-proj"])
        self.assertEqual(pick_ledger.verify(), 0)

    def test_game_before_today_is_not_published(self):
        now = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)   # 10:00 AM ET 11/16
        self._write([_row("G1", "2026-11-15", "1:00 PM")], [("2026-11-15", "G1")])
        self._publish(now)
        self.assertEqual(self._ids(), [])

    def test_today_without_verified_tip_is_not_published(self):
        now = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
        self._write([_row("G2", "2026-11-16", None)], [("2026-11-16", "G2")])
        self._publish(now)
        self.assertEqual(self._ids(), [])

    def test_today_with_future_tip_is_published_and_passed_tip_is_not(self):
        now = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)   # 10:00 AM ET
        self._write([_row("G3", "2026-11-16", "7:30 PM"),           # 7:30 PM ET: still ahead
                     _row("G4", "2026-11-16", "9:00 AM")],          # already passed at 10 AM
                    [("2026-11-16", "G3"), ("2026-11-16", "G4")])
        self._publish(now)
        self.assertEqual(self._ids(), ["G3-side-proj"])

    def test_tips_printed_with_a_zone_token_are_verified(self):
        """Regression (session arena/915d2e99-nba3): the official card prints "8:00 PM ET".

        `_tip_as_et` accepted only "%I:%M %p", so a tip that WAS printed on the official page read as
        "tip time not verified", and publish() refused every game tipping today while sealing the
        later ones: on 2026-11-19 it published 15 rows and skipped all four of the day's games. The
        entry still carries the page's own string — only the parse learned to ignore the zone suffix,
        and an unreadable tip must still refuse (never publish without a provable pre-tip instant).
        """
        now = datetime(2026, 11, 19, 6, 0, tzinfo=timezone.utc)     # 01:00 AM ET on 11/19
        self._write([_row("G6", "2026-11-19", "8:00 PM ET"),        # tips 20:00 ET: still ahead
                     _row("G7", "2026-11-19", "12:30 AM ET")],      # already tipped at 01:00 ET
                    [("2026-11-19", "G6"), ("2026-11-19", "G7")])
        self._publish(now)
        self.assertEqual(self._ids(), ["G6-side-proj"])

    def test_unreadable_tip_refuses_and_zone_variants_resolve(self):
        self.assertIsNone(pick_ledger._tip_as_et("TBD", date(2026, 11, 19)))
        self.assertIsNone(pick_ledger._tip_as_et("", date(2026, 11, 19)))
        self.assertIsNone(pick_ledger._tip_as_et(None, date(2026, 11, 19)))
        # the zone token is dropped and the day is interpreted in ET either way, so the same wall
        # clock resolves across the DST boundary without a hard-coded offset
        for tip, day in (("8:00 PM EDT", date(2026, 3, 9)), ("8:00 PM EST", date(2026, 11, 19))):
            with self.subTest(tip=tip):
                got = pick_ledger._tip_as_et(tip, day)
                self.assertEqual((got.hour, got.minute), (20, 0))
                self.assertEqual(got.date(), day)

    def test_future_day_is_published_without_a_tip_time(self):
        now = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
        self._write([_row("G5", "2026-11-17", None)], [("2026-11-17", "G5")])
        self._publish(now)
        self.assertEqual(self._ids(), ["G5-side-proj"])

    def test_row_not_on_official_slate_is_not_published(self):
        self._write([_row("G6", "2026-11-17", None)], [("2026-11-18", "G6")])   # wrong date
        self._publish(EARLY)
        self.assertEqual(self._ids(), [])

    def test_committed_window_matches_committed_chain_without_new_entries(self):
        # Against the real committed files: a publish run at the chain's own newest
        # timestamp adds nothing — every row that passes the date/tip gates at that clock
        # is already in the chain. Roll-safe: the earlier fixed clock (2026-11-16 15:00 UTC)
        # failed once the scheduled refresh rolled the window past it (run 43925193575).
        shutil.copy(os.path.join(ROOT, "data", "app", "ledger", "ledger.jsonl"),
                    pick_ledger.LEDGER)                       # a copy: never write the real file
        entries = pick_ledger.read_entries()
        before = len(entries)
        stamps = [e["body"].get("published_utc") or e["body"].get("settled_utc")
                  for e in entries]
        stamps = [s for s in stamps if s]
        if not stamps:
            self.skipTest("empty chain")
        now = datetime.strptime(max(stamps), "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        pick_ledger.publish(now_utc=now)
        self.assertEqual(len(pick_ledger.read_entries()), before)


class SettleIdempotencyTests(unittest.TestCase):
    """settle() must append one settlement per pick, ever (session arena/915d2e99-nba3)."""

    def test_rerunning_settle_adds_nothing_for_a_pick_already_settled(self):
        self.tmp = tempfile.mkdtemp()
        saved = (pick_ledger.LEDGER_DIR, pick_ledger.LEDGER, pick_ledger.FEED)
        try:
            pick_ledger.LEDGER_DIR = self.tmp
            pick_ledger.LEDGER = os.path.join(self.tmp, "ledger.jsonl")
            feed = os.path.join(self.tmp, "feed.json")
            with open(feed, "w", encoding="utf-8") as fh:
                json.dump({"games": [{"game_id": "X1", "date": "2026-11-15", "away": "DAL",
                                      "home": "CLE", "away_pts": 113, "home_pts": 106,
                                      "verified": True, "settled": True}]}, fh)
            pick_ledger.FEED = feed
            # the pre-existing publication has to be a real chained entry: settle() reads the head
            # hash off the last row, so a hand-written body without entry_hash is not a fixture
            payload = {"away": "DAL", "home": "CLE", "blend_margin": 3.0, "blend_total": 219.0}
            body = {"pick_id": "X1-side-proj", "state": "PUBLISHED_PRE_TIP", "date": "2026-11-15",
                    "payload": payload, "payload_sha256": pick_ledger.sha(payload)}
            entry = {"prev_hash": pick_ledger.GENESIS, "body": body}
            entry["entry_hash"] = pick_ledger.chain_hash(pick_ledger.GENESIS, body)
            with open(pick_ledger.LEDGER, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
            # settle() takes no arguments: the settled day comes from the feed, so re-running the
            # command is exactly what CI does, and it must be a no-op after the first stamp.
            for _ in range(3):
                self.assertEqual(pick_ledger.settle(), 0)
            entries = pick_ledger.read_entries()
            self.assertEqual([e["body"]["state"] for e in entries],
                             ["PUBLISHED_PRE_TIP", "SETTLED"],
                             "one publication, exactly one settlement")
            self.assertEqual(pick_ledger.verify(), 0)
        finally:
            (pick_ledger.LEDGER_DIR, pick_ledger.LEDGER, pick_ledger.FEED) = saved
            shutil.rmtree(self.tmp)


if __name__ == "__main__":
    unittest.main()
