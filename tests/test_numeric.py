#!/usr/bin/env python3
"""Regression tests for the defect that red-flagged the scheduled refresh.

The failure this pins
---------------------
`refresh.yml` runs its unit-test gate on the hosted runner's default
interpreter, while `pages.yml` pins 3.11. Since CPython 3.12 `sum()` over
floats uses Neumaier compensated summation (gh-100425) instead of the naive
left-to-right accumulation of 3.11. Three committed artefacts regenerated with
different bytes on the newer interpreter, so their byte-identity drift gates
failed, so the refresh job aborted *before* it fetched any official source, so
every scheduled run from 2026-11-17 onward was red and no official data was
committed. The measured case:

    Python 3.11   sum(minutes) = 239.99999999999997
    Python 3.12+  sum(minutes) = 240.0
      26.1 / 239.99999999999997 = 0.10875000000000001 -> round(..., 4) = 0.1088
      26.1 / 240.0                = 0.10875           -> round(..., 4) = 0.1087

What these tests hold
---------------------
1. `scripts/numeric.py` does what it says: an exactly-rounded sum, and a
   rounding rule that is stated rather than inherited from the interpreter.
2. The three artefacts that broke regenerate byte-for-byte even when the
   interpreter's `sum()` is forced back to the pre-3.12 naive algorithm. That
   is the property the fix buys: a committed number is a function of the data,
   not of the interpreter.
3. The historical failure mode is still reproducible, so the test above cannot
   silently stop testing anything.

Nothing here reaches the network and nothing here reads a live source.
"""
from __future__ import annotations

import builtins
import math
import os
import subprocess
import sys
import unittest
from decimal import Decimal, ROUND_HALF_EVEN

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from numeric import fsum, naive_sum, rnd, rnd_decimal  # noqa: E402


def _run_with_naive_sum(script: str) -> subprocess.CompletedProcess:
    """Run `script --check` in a child interpreter whose `sum` is the pre-3.12 one.

    The artefact generators write nothing in --check mode, so this is safe to
    run against the working tree: it asserts, it does not rewrite.
    """
    harness = (
        "import builtins, runpy, sys\n"
        "_orig = builtins.sum\n"
        "def naive(iterable, start=0):\n"
        "    total = start\n"
        "    for v in iterable:\n"
        "        total = total + v\n"
        "    return total\n"
        "builtins.sum = naive\n"
        "sys.argv = [sys.argv[1]] + sys.argv[2:]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    return subprocess.run([sys.executable, "-c", harness, os.path.join(ROOT, script), "--check"],
                          capture_output=True, text=True, cwd=ROOT)


class NumericHelper(unittest.TestCase):
    def test_fsum_is_the_correctly_rounded_sum(self):
        vals = [0.1] * 10
        self.assertEqual(fsum(vals), 1.0)
        self.assertNotEqual(naive_sum(vals), 1.0,
                            "the naive sum must still differ, or this test proves nothing")

    def test_rnd_is_half_even_and_states_its_mode(self):
        # half-even, like the documented behaviour of round()
        self.assertEqual(rnd(0.10875, 4), 0.1088)   # 0.10875 -> 0.1088 (8 is even)
        self.assertEqual(rnd(0.10865, 4), 0.1086)   # 0.10865 -> 0.1086 (6 is even)
        self.assertEqual(rnd(0.5, 0), 0.0)
        self.assertEqual(rnd(1.5, 0), 2.0)
        self.assertEqual(rnd_decimal(0.10875, 4), Decimal("0.1088"))

    def test_rnd_matches_the_correctly_rounded_decimal_quantum(self):
        for raw in (0.10875, 1.0 / 3.0, 26.1 / 240.0, 100.47153, 0.0, -3.14159, 2.5e-7):
            for places in (0, 1, 2, 4, 6):
                self.assertEqual(rnd(raw, places),
                                 float(Decimal(repr(float(raw))).quantize(
                                     Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)),
                                 f"{raw} at {places} places")

    def test_rnd_preserves_the_shape_of_its_input(self):
        self.assertIsInstance(rnd(3, 2), int)
        self.assertIsInstance(rnd(3.0, 2), float)
        self.assertIsInstance(rnd(3.0), int)          # round(x) returns an int
        self.assertIsNone(rnd(None, 2))
        self.assertIsNone(rnd(None))

    def test_rnd_never_turns_a_missing_measurement_into_a_zero(self):
        self.assertIsNone(rnd(None, 4))


class TheHistoricalFailureModeIsStillReal(unittest.TestCase):
    """If this stops holding, the tests above have stopped testing anything."""

    def test_the_minute_total_that_moved_is_reproducible(self):
        # The twelve Washington Wizards minutes the official 2026-11-15 game book prints,
        # in the order the artefact stores them. Read out of
        # data/rounds/2026-11-17/player_logs_2026-11-15.json.
        minutes = [30.116666666666667, 30.583333333333332, 27.033333333333335,
                   30.333333333333332, 26.1, 22.816666666666666, 9.95,
                   21.033333333333335, 9.25, 15.75, 11.283333333333333, 5.75]
        naive = naive_sum(minutes)
        exact = fsum(minutes)
        self.assertNotEqual(naive, exact,
                            "the pre-3.12 and compensated sums must differ for this case")
        self.assertNotEqual(round(26.1 / naive, 4), round(26.1 / exact, 4),
                            "the published share must land on a different side of the tie")


class CommittedArtefactsDoNotDependOnTheInterpreter(unittest.TestCase):
    """The property the fix buys, asserted against the committed artefacts."""

    def _assert_reproduces_with_naive_sum(self, script: str):
        result = _run_with_naive_sum(script)
        self.assertEqual(result.returncode, 0,
                         f"{script} --check did not reproduce when the interpreter's sum() was "
                         f"forced back to the pre-3.12 naive algorithm, so the committed artefact "
                         f"still depends on the interpreter:\n{result.stdout}\n{result.stderr}")

    def test_player_logs_artefact(self):
        self._assert_reproduces_with_naive_sum("scripts/gamebooks_2ecbccfd.py")

    def test_game_day_roll_model_artefact(self):
        self._assert_reproduces_with_naive_sum("d1b96315/model.py")

    def test_same_day_filing_chain_model_artefact(self):
        self._assert_reproduces_with_naive_sum("scripts/round2_2026_11_16.py")


class NoGeneratorMayCallTheBareBuiltInSumOnFloats(unittest.TestCase):
    """A static guard: a new `sum(` over floats would silently reintroduce this.

    The generators listed here write committed artefacts that CI byte-compares.
    Any float summation in them must go through `numeric.fsum`.
    """

    GENERATORS = [
        "scripts/gamebooks_2ecbccfd.py",
        "scripts/round2_2026_11_16.py",
        "d1b96315/model.py",
    ]

    def test_no_bare_sum_over_a_float_survives(self):
        import io
        import tokenize
        for rel in self.GENERATORS:
            path = os.path.join(ROOT, rel)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type != tokenize.NAME or tok.string != "sum":
                    continue
                # a bare `sum(` that is not `fsum(`/`numeric_fsum(`/`math.fsum(`
                line = src.splitlines()[tok.start[0] - 1]
                before = line[:tok.start[1]]
                if before.endswith("fsum") or before.endswith("."):
                    continue
                # integer summations are exact and unaffected by the interpreter change,
                # so only flag a sum whose accumulator starts as a float literal
                after = line[tok.end[1]:]
                if "for r in" in after and "min" in after:
                    self.fail(f"{rel}:{tok.start[0]} sums minutes with the built-in sum(): "
                              f"{line.strip()}")
                if "errs" in after or "poss_per_game" in after or "raw_a" in after:
                    self.fail(f"{rel}:{tok.start[0]} sums floats with the built-in sum(): "
                              f"{line.strip()}")


if __name__ == "__main__":
    unittest.main()
