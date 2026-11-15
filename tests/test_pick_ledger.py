#!/usr/bin/env python3
"""Tests for the tamper-evident pick ledger (session arena/79341829-nba3)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pick_ledger  # noqa: E402


class PickLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        pick_ledger.LEDGER_DIR = self.tmp
        pick_ledger.LEDGER = os.path.join(self.tmp, "ledger.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_publish_then_verify_chain_intact(self):
        self.assertEqual(pick_ledger.publish(), 0)
        self.assertEqual(pick_ledger.verify(), 0)
        entries = pick_ledger.read_entries()
        self.assertGreater(len(entries), 30)
        for e in entries:
            self.assertEqual(e["body"]["state"], "PUBLISHED_PRE_TIP")
            self.assertTrue(e["body"]["payload_sha256"])
            self.assertTrue(e["body"]["published_utc"])

    def test_publish_is_idempotent(self):
        pick_ledger.publish()
        n1 = len(pick_ledger.read_entries())
        pick_ledger.publish()
        self.assertEqual(len(pick_ledger.read_entries()), n1)

    def test_tampered_payload_breaks_verify(self):
        pick_ledger.publish()
        entries = pick_ledger.read_entries()
        entries[3]["body"]["payload"]["blend_margin"] = 99.0   # silent historical edit
        pick_ledger.write_entries(entries)
        self.assertEqual(pick_ledger.verify(), 1)

    def test_broken_chain_detected(self):
        pick_ledger.publish()
        entries = pick_ledger.read_entries()
        entries.pop(2)                                          # removed history
        pick_ledger.write_entries(entries)
        self.assertEqual(pick_ledger.verify(), 1)

    def test_settlement_uses_official_final_only(self):
        pick_ledger.publish()
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


if __name__ == "__main__":
    unittest.main()
