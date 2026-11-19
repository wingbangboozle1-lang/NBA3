#!/usr/bin/env python3
"""The committed round artefacts must not depend on the interpreter's float-summation rule.

CPython 3.12 changed the builtin ``sum()`` for floats to compensated (Neumaier) summation
(CPython changelog, gh-100425). The same committed game-book transcripts therefore produce a
team-minutes total one ULP apart on 3.11 and on 3.12+, and a published 4-decimal minutes share
moves with it. That is exactly what broke the scheduled "official data refresh" job on
2026-11-18: the job ran the runner's default interpreter (Python 3.14.4) while the artefact had
been produced under 3.11, so ``scripts/gamebooks_2ecbccfd.py --check`` -- a byte-for-byte
comparison -- failed, the refresh chain never ran, and no official source was refreshed for two
days. The evidence is recorded in COORDINATION.md under session arena/64d8f868-nba3.

The fix is in the producer, not in the checker: the minutes totals are accumulated with
``math.fsum`` (the correctly rounded total, identical on every supported interpreter) and the
integer counters keep integer arithmetic. These tests hold that property in place: they rebuild
the artefact with ``builtins.sum`` replaced by a compensated implementation and require the bytes
to be unchanged.

Run: python3 -m unittest tests/test_interpreter_stability.py
"""
import builtins
import math
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gamebooks_2ecbccfd as gamebooks  # noqa: E402

ARTEFACT = os.path.join(ROOT, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json")


def compensated_sum(iterable, start=0):
    """CPython >= 3.12 builtin sum() for floats, with integer sums left exact."""
    values = list(iterable)
    if type(start) is int and all(type(v) is int for v in values):
        total = start
        for v in values:
            total += v
        return total
    total = float(start)
    comp = 0.0
    for v in values:
        x = float(v)
        t = total + x
        if abs(total) >= abs(x):
            comp += (total - t) + x
        else:
            comp += (x - t) + total
        total = t
    return total + comp


class InterpreterStabilityTests(unittest.TestCase):
    def test_player_log_artefact_is_identical_under_compensated_sum(self):
        """The byte-for-byte --check must mean the same thing on 3.11 and on 3.12+."""
        committed = open(ARTEFACT, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "player_logs.json")
            original = gamebooks.OUT
            gamebooks.OUT = out
            try:
                with mock.patch.object(builtins, "sum", compensated_sum):
                    rc = gamebooks.main()
            finally:
                gamebooks.OUT = original
            self.assertEqual(rc, 0)
            self.assertEqual(open(out, encoding="utf-8").read(), committed,
                             "the artefact changed when sum() was given the CPython>=3.12 "
                             "compensated-summation semantics: a float sum() is still in use")

    def test_compensated_sum_really_is_a_different_float_total(self):
        """Guard the guard: the replacement must not be a no-op."""
        # The twelve Washington minutes as the official game book prints them (mm:ss).
        values = [30.116666666666667, 30.583333333333332, 27.033333333333335,
                  30.333333333333332, 26.1, 22.816666666666666, 9.95,
                  21.033333333333335, 9.25, 15.75, 11.283333333333333, 5.75]
        self.assertNotEqual(compensated_sum(values), sum(values))
        self.assertEqual(math.fsum(values), 240.0)
        self.assertEqual(sum(values), 239.99999999999997)

    def test_published_washington_minutes_total_is_exactly_240(self):
        """A regulation NBA club-game is 5 x 48:00. The published share follows from it."""
        import json
        data = json.load(open(ARTEFACT, encoding="utf-8"))
        mins = [r["min"] for r in data["rows"]
                if r["date"] == "2026-11-15" and r["team"] == "WAS" and r["status"] == "played"]
        self.assertEqual(math.fsum(mins), 240.0)
        share = data["top8_minutes_shares"]["2026-11-15:WAS"]
        trae = [t for t in share["top8"] if t["player"] == "Trae Young"][0]
        self.assertEqual(trae["min"], 26.1)
        self.assertEqual(trae["share"], round(26.1 / 240.0, 4))
        self.assertEqual(share["total_min_played"], 240.0)


if __name__ == "__main__":
    unittest.main()
