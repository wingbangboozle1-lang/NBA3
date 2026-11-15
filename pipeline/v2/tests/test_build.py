"""The build must be reproducible byte for byte.

The repo's own CI asserts that a rebuild produces identical output, and the
whole point of a tamper-evident ledger is that a rerun changes nothing.  Two
things had to be pinned to get there, and both are worth a test because both
were broken:

* the publication timestamp, which otherwise differs in the microseconds;
* the pre-registration stamps, which otherwise move forward on every build and
  make "registered before the first bet" unfalsifiable.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from pipeline.v2 import build as B                          # noqa: E402


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "data", "v2", "captures")),
                     "captures not present")
class TestReproducible(unittest.TestCase):
    def test_two_builds_are_identical(self):
        a, code_a = B.build()
        b, code_b = B.build()
        self.assertEqual(code_a, code_b)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_registrations_are_frozen(self):
        rows = B._registrations(__import__("datetime").datetime(
            2026, 11, 15, 12, 0, tzinfo=__import__("datetime").timezone.utc))
        stamps = {r["registered_utc"] for r in rows}
        self.assertEqual(len(stamps), 1, "every rule shares the freeze time")
        # a second read must return the same file, not a new stamp
        again = B._registrations(__import__("datetime").datetime(
            2027, 1, 1, tzinfo=__import__("datetime").timezone.utc))
        self.assertEqual([r["preregistration_sha256"] for r in rows],
                         [r["preregistration_sha256"] for r in again])
        self.assertEqual([r["registered_utc"] for r in rows],
                         [r["registered_utc"] for r in again])

    def test_gates_all_pass_in_the_committed_state(self):
        doc, code = B.build()
        self.assertEqual(code, 0, f"blocking gates failed: {doc['gates']['blocking_failures']}")
        self.assertTrue(doc["gates"]["may_publish"])

    def test_nothing_is_bettable(self):
        """The honest end state: no rule may be a bet, because no market price exists."""
        doc, _ = B.build()
        self.assertEqual([e["rule"]["strategy_id"] for e in doc["board"]
                          if e["verdict"]["may_be_a_bet"]], [])

    def test_ledger_verifies(self):
        doc, _ = B.build()
        self.assertTrue(doc["ledger_counts"]["all_hashes_match"])
        # every settlement came from an official game page
        for row in doc["ledger"]:
            self.assertTrue(row["settlement_source"].startswith("https://www.nba.com/game/"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
