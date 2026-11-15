"""Tests for the ledger chain, pre-registration write-once rule, and settlement grading.

The point of these tests is negative: they prove that a tampered pick and a broken chain are
DETECTED, and that a pick cannot be published without a frozen pre-registration or after tip.
"""

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ledger  # noqa: E402


def minimal_strategy(sid="T1"):
    return {
        "id": sid, "name": "test strategy", "author": "test",
        "frozen_utc": "2026-11-15T00:00Z",
        "signal": "s", "thresholds": {"a": 1}, "universe": {"u": 1},
        "settlement_rule": "SPREAD",
        "settlement_rule_text": "settle on the official final",
        "stake_rule": "flat 1 unit",
    }


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self._saved = (ledger.PREREG, ledger.LEDGER, ledger.LEDGER_DIR, ledger.INDEX)
        ledger.PREREG = base / "prereg"
        ledger.LEDGER_DIR = base / "ledger"
        ledger.LEDGER = ledger.LEDGER_DIR / "ledger.jsonl"
        ledger.INDEX = ledger.LEDGER_DIR / "index.json"
        ledger.freeze(minimal_strategy())

    def tearDown(self):
        ledger.PREREG, ledger.LEDGER, ledger.LEDGER_DIR, ledger.INDEX = self._saved
        self.tmp.cleanup()

    def pick(self, **over):
        p = {"strategy_id": "T1", "game_id": "g1", "date": "2026-11-15",
             "matchup": "A @ B", "tip_et": "7:00 PM", "tip_et_iso": "2026-11-16T00:00Z",
             "pick": "A +3.5", "line": 3.5, "settlement_rule_id": "SPREAD"}
        p.update(over)
        return p

    def test_publish_requires_frozen_preregistration(self):
        with self.assertRaises(ValueError):
            ledger.publish(self.pick(strategy_id="NOPE"), now="2026-11-15T10:00Z")

    def test_publish_refuses_at_or_after_tip(self):
        with self.assertRaises(ValueError):
            ledger.publish(self.pick(), now="2026-11-16T00:00Z")

    def test_chain_verifies_then_detects_tampering(self):
        ledger.publish(self.pick(), now="2026-11-15T10:00Z")
        ledger.publish(self.pick(game_id="g2", pick="A +1.0", line=1.0), now="2026-11-15T10:01Z")
        self.assertTrue(ledger.verify()["verified"])

        lines = ledger.LEDGER.read_text().splitlines()
        entry = json.loads(lines[1])
        entry["pick"]["pick"] = "A +9.5"          # rewrite the published pick
        lines[1] = json.dumps(entry, sort_keys=True)
        ledger.LEDGER.write_text("\n".join(lines) + "\n")

        v = ledger.verify()
        self.assertFalse(v["verified"])
        self.assertTrue(any("no longer hashes" in p["problem"] for p in v["problems"]))

    def test_settle_uses_the_preregistered_rule(self):
        ledger.publish(self.pick(), now="2026-11-15T10:00Z")
        final = {"home_final": 100, "away_final": 102}   # away wins by 2
        out = ledger.settle("g1", final=final, now="2026-11-16T06:00Z", source_url="https://www.nba.com/")
        self.assertEqual(out["result"]["outcome"], "WIN")   # A +3.5 with away winning by 2

    def test_settle_detects_a_rewritten_pick(self):
        ledger.publish(self.pick(), now="2026-11-15T10:00Z")
        lines = ledger.LEDGER.read_text().splitlines()
        entry = json.loads(lines[0])
        entry["pick"]["pick"] = "B -3.5"
        lines[0] = json.dumps(entry, sort_keys=True)
        ledger.LEDGER.write_text("\n".join(lines) + "\n")
        v = ledger.verify()
        self.assertFalse(v["verified"])

    def test_preregistration_is_write_once(self):
        with self.assertRaises(FileExistsError):
            ledger.freeze(minimal_strategy())


if __name__ == "__main__":
    unittest.main()
