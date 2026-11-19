"""Pin cross-version float summation (session arena/e9295737-nba3).

The scheduled refresh failed at its committed-tree unit-test preflight from 2026-11-17
onward. The cause was not the data: CPython 3.12 changed the builtin ``sum()`` to use
Neumaier compensated summation for floats (gh-100425). Two committed artefacts divide by
a float sum and round the quotient, so one of their digits moved between the sandbox
(Python 3.11) and the hosted runner (Python 3.12):

  * ``data/rounds/2026-11-17/player_logs_2026-11-15.json`` — Trae Young's top-8 minutes
    share 0.1088 (3.11) vs 0.1087 (3.12);
  * ``data/v2/build.json`` — a published spread line 7.210020179238307 vs
    ...308, and therefore a different pick_sha256 for every bet under it.

These tests fail on any interpreter where the pipeline has drifted back to depending on
the builtin. They do not need Python 3.12: ``tests.simulate_new_sum`` reproduces the 3.12
algorithm exactly, so the check runs here.
"""
import contextlib
import importlib
import io
import math
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def simulate_new_sum(iterable, /, start=0):
    """CPython >=3.12 builtin sum() for floats, transcribed from gh-100425.

    Integer-only input keeps exact integer accumulation, which is what 3.12 does too.
    """
    it = iter(iterable)
    result = start
    for item in it:
        if type(item) is float:
            first = item
            break
        result = result + item
    else:
        return result
    if type(result) is not float:
        result = float(result)
    f = result
    c = 0.0
    for item in [first, *it]:
        x = float(item)
        t = f + x
        if abs(f) >= abs(x):
            c += (f - t) + x
        else:
            c += (x - t) + f
        f = t
    return f + c


class FloatSumShimTests(unittest.TestCase):
    def test_total_matches_the_311_algorithm_not_the_312_one(self):
        import floatsum
        # A case where the two disagree: the canonical gh-100425 example.
        # Minutes are nn + ss/60. 26.1 is 1566/60: its true value is not representable,
        # and this is the exact club sum behind the Trae Young share that broke the run.
        # The twelve WIZARDS minutes from the committed 11/15 game book (Trae Young 26.1).
        # Naive sum: 239.99999999999997 -> his share 0.1088. 3.12 sum: 240.0 -> 0.1087.
        values = [30.116666666666667, 30.583333333333332, 27.033333333333335,
                  30.333333333333332, 26.1, 22.816666666666666, 9.95, 21.033333333333335,
                  9.25, 15.75, 11.283333333333333, 5.75]
        naive = 0.0
        for v in values:
            naive += v
        self.assertEqual(floatsum.total(values), naive)
        self.assertNotEqual(floatsum.total(values), simulate_new_sum(values))
        # the shift is one ulp, but a share rounded to 4 places can move with it
        self.assertNotEqual(round(26.1 / floatsum.total(values), 4),
                            round(26.1 / simulate_new_sum(values), 4))

    def test_total_is_exactly_the_loop_it_replaces(self):
        import floatsum
        values = [26.1, 23.55, 40.0, 12.0, 7.75, 100.0]
        acc = 0
        for v in values:
            acc += v
        self.assertEqual(floatsum.total(values), acc)
        self.assertEqual(floatsum.total([]), 0)

    def test_mean_helper_matches_the_311_mean(self):
        import floatsum
        values = [0.1, 0.2, 0.3, 12.4, 9.95]
        self.assertEqual(floatsum.mean_total(values), sum(values) / len(values))
        self.assertIsNone(floatsum.mean_total([]))
        self.assertIsNone(floatsum.mean_total([None, None]))

    def test_share_guards_a_zero_denominator(self):
        import floatsum
        self.assertIsNone(floatsum.share(5, 0))
        self.assertIsNone(floatsum.share(None, 10))
        self.assertEqual(floatsum.share(26.1, 240, 4), round(26.1 / 240, 4))


class CommittedArtefactsSurviveNewSumTests(unittest.TestCase):
    """Re-derive the artefacts with the 3.12 sum() in force and compare the committed file."""

    def _check_under_new_sum(self, path, *args):
        code = (
            "import builtins, runpy, sys\n"
            "sys.path.insert(0, %r)\n"
            "from tests.test_float_sum_determinism import simulate_new_sum\n"
            "builtins.sum = simulate_new_sum\n"
            "sys.argv = [%r] + %r\n"
            "runpy.run_path(%r, run_name='__main__')\n"
        ) % (ROOT, path, list(args), os.path.join(ROOT, path))
        return subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                              capture_output=True, text=True)

    def test_player_log_minutes_shares_reproduce_under_the_312_sum(self):
        r = self._check_under_new_sum("scripts/gamebooks_2ecbccfd.py", "--check")
        self.assertEqual(r.returncode, 0,
                         "gamebooks_2ecbccfd.py --check fails when builtin sum() follows "
                         f"CPython 3.12; this is the failure the hosted runner hit.\n{r.stderr}{r.stdout}")

    def test_game_day_model_reproduces_under_the_312_sum(self):
        r = self._check_under_new_sum("d1b96315/model.py", "--check")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_v2_build_reproduces_under_the_312_sum(self):
        r = self._check_under_new_sum("pipeline/v2/build.py", "--check")
        self.assertEqual(r.returncode, 0,
                         "data/v2/build.json changes when builtin sum() follows CPython 3.12: "
                         "a published line and every pick hash under it move.\n" + r.stderr + r.stdout)
        # the file itself must be untouched by the check-only run
        self.assertEqual(subprocess.run(["git", "status", "--porcelain", "--", "data/v2"],
                                        cwd=ROOT, capture_output=True, text=True).stdout.strip(), "")


class NoRoundingDependsOnTheBuiltinSumTests(unittest.TestCase):
    """A source audit: no shipped module may divide by a builtin ``sum()`` to make a rounded value."""

    IMPORTANT = ["scripts/gamebooks_2ecbccfd.py", "d1b96315/model.py",
                 "pipeline/v2/stats.py", "pipeline/v2/estimators.py"]

    def test_the_known_offenders_use_the_shim(self):
        for rel in self.IMPORTANT:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                text = fh.read()
            with self.subTest(file=rel):
                if rel == "pipeline/v2/stats.py":
                    self.assertIn("def dsum(", text)
                    self.assertNotIn(" math.sqrt(sum(", text)
                elif rel == "pipeline/v2/estimators.py":
                    self.assertIn("S.dsum(", text)
                else:
                    self.assertIn("float_total", text)


if __name__ == "__main__":
    unittest.main()
