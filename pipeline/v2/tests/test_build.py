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
        """In memory, with no write: the test must never mutate the artefact it checks."""
        a, code_a = B.build(write=False)
        b, code_b = B.build(write=False)
        self.assertEqual(code_a, code_b)
        self.assertEqual(json.dumps(B._strip_volatile(a), sort_keys=True),
                         json.dumps(B._strip_volatile(b), sort_keys=True))

    def test_committed_artefact_matches_a_fresh_rebuild(self):
        ok, diff = B.check()
        self.assertTrue(ok, "rebuild differs:\n" + "\n".join(diff))

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
        doc, code = B.build(write=False)
        self.assertEqual(code, 0, f"blocking gates failed: {doc['gates']['blocking_failures']}")
        self.assertTrue(doc["gates"]["may_publish"])

    def test_nothing_is_bettable(self):
        """The honest end state: no rule may be a bet, because no market price exists."""
        doc, _ = B.build(write=False)
        self.assertEqual([e["rule"]["strategy_id"] for e in doc["board"]
                          if e["verdict"]["may_be_a_bet"]], [])

    def test_ledger_verifies(self):
        doc, _ = B.build(write=False)
        self.assertTrue(doc["ledger_counts"]["all_hashes_match"])
        # every settlement came from an official game page
        for row in doc["ledger"]:
            self.assertTrue(row["settlement_source"].startswith("https://www.nba.com/game/"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "data", "v2", "build.json")),
                     "artefact not present")
class TestPagesDoNotDependOnTheClock(unittest.TestCase):
    """The rendered pages must not contain anything that changes between runs.

    This is not pedantry. CI regenerates v2/ and fails on any change, so a page
    that prints the gate evaluation time makes the drift check fail on every
    run for a reason that has nothing to do with the data -- and a check that
    fails for noise is a check people start ignoring. The gate page used to
    print that timestamp.

    The failure mode is worse than a red build, though: it trains the reader to
    read a drift failure as "the clock again" when it might be a real input
    change, which is the one thing the check exists to surface.
    """

    @classmethod
    def setUpClass(cls):
        import subprocess
        cls._before = {}
        cls.ok = None
        v2 = os.path.join(ROOT, "v2")
        for name in sorted(os.listdir(v2)):
            if name.endswith(".html"):
                with open(os.path.join(v2, name), encoding="utf-8") as fh:
                    cls._before[name] = fh.read()

    def test_pages_contain_no_evaluated_at_timestamp(self):
        for name, body in self._before.items():
            self.assertNotIn("evaluated_at_utc=", body, name)
            # an ISO timestamp with a minute precision other than the fixed
            # publication date would be a clock leak
            import re
            for stamp in re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", body):
                self.assertTrue(stamp.startswith("2026-11-15"),
                                f"{name} embeds a build-time clock: {stamp}")
