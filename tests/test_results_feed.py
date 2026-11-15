#!/usr/bin/env python3
"""Tests for the results feed + settlement stamps (session arena/79341829-nba3)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import results_feed  # noqa: E402


class ResultsFeedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.feed_path = os.path.join(self.tmp, "results_feed.json")
        shutil.copy(os.path.join(ROOT, "data", "app", "results_feed.json"), self.feed_path)
        results_feed.FEED = self.feed_path

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_verify_marks_quarter_consistency(self):
        feed = results_feed.load()
        results_feed.verify(feed)
        nov14 = [g for g in feed["games"] if g["date"] == "2026-11-14"]
        for g in nov14:
            self.assertTrue(g["verified"])
            self.assertEqual(g["quarter_check"], "quarter sums equal the final")

    def test_settle_is_idempotent_and_stamped(self):
        feed = results_feed.load()
        for g in feed["games"]:          # reset settlement state, then settle fresh
            g["settled"] = False
            g["settlement_stamp"] = None
        results_feed.verify(feed)
        n1 = results_feed.settle(feed, "2026-11-14")
        n2 = results_feed.settle(feed, "2026-11-14")
        self.assertEqual(n1, 5)
        self.assertEqual(n2, 0, "settling twice must not re-stamp rows")
        for g in feed["games"]:
            if g["date"] == "2026-11-14":
                self.assertTrue(g["settled"])
                self.assertIn("official final", g["settlement_stamp"])

    def test_quarter_mismatch_never_settles(self):
        feed = results_feed.load()
        for g in feed["games"]:
            g["settled"] = False
            g["settlement_stamp"] = None
        for g in feed["games"]:
            if g["date"] == "2026-11-14":
                g["home_q1"] = 99
                break
        results_feed.verify(feed)
        bad = [g for g in feed["games"] if g["date"] == "2026-11-14" and not g["verified"]]
        self.assertEqual(len(bad), 1)
        n = results_feed.settle(feed, "2026-11-14")
        self.assertEqual(n, 4, "the mismatched row must stay unsettled")


if __name__ == "__main__":
    unittest.main()
