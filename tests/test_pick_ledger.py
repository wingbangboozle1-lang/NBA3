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


if __name__ == "__main__":
    unittest.main()
