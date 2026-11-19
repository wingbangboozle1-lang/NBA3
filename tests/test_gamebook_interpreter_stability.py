"""Interpreter-stability of the gamebooks replay gate (session arena/f69a11c4-nba3, G1).

Scheduled run 44469939831 failed on the hosted runner while every 3.11 sandbox was green. The
check-run annotations (readable through the API where the artifact blobs are not) name the failing
test: the committed-tree replay of scripts/gamebooks_2ecbccfd.py --check, inside
tests/test_refresh_official.py. The cause is a language change, not data or time:

    CPython 3.12 changed builtin sum() for float items to Kahan-Babushka-Neumaier compensated
    summation (CPython gh-100425). The committed player-logs artefact was generated under 3.11's
    left-to-right float summation, so the replay on the runner's 3.12.3 re-derived one byte
    differently: a Washington Wizards top-8 minutes share rounded to 0.1087 instead of the
    committed 0.1087 vs 0.1088 pair. Reproduced in-sandbox by simulating the 3.12 algorithm over
    the committed minutes before the fix.

The fix routes every float aggregate that feeds the published payload through math.fsum, which is
correctly rounded and identical on every CPython version. These tests pin that property:

  1. the committed artefact still equals the script's own output (native interpreter);
  2. it ALSO equals the output when builtin sum() is replaced by a faithful 3.12-Neumaier
     simulation — so the published bytes cannot depend on the interpreter's summation;
  3. the simulation itself is proven non-vacuous: on the committed Wizards minutes the two
     summations disagree in the last bit, i.e. the test would have failed before the fix;
  4. the float aggregates are spelled math.fsum in the source, so the invariant survives review.

Offline: no network, no clock, and the real artefact is only ever read.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import runpy
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "gamebooks_2ecbccfd.py")
ARTEFACT = os.path.join(ROOT, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json")

# Driver source: patch builtins.sum with CPython 3.12 float semantics, then run the target
# script with `--check` via runpy, re-raising its SystemExit code.
DRIVER = r'''
import builtins, sys, runpy
_orig_sum = builtins.sum

def _sum_312(iterable, start=0):
    """builtin sum() as CPython 3.12 implements it for this workload: ints stay exact, and once a
    float appears the accumulation is Kahan-Babushka-Neumaier compensated (gh-100425)."""
    items = iter(iterable)
    acc = start
    f_result = 0.0
    c = 0.0
    floating = isinstance(acc, float)
    if not floating:
        buffered = []
        for x in items:
            if isinstance(x, float):
                f_result = float(acc)
                floating = True
                buffered.append(x)
                break
            acc = acc + x
        else:
            return acc
        items = _chain(buffered, items)
    for x in items:
        t = f_result + x
        if abs(f_result) >= abs(x):
            c += (f_result - t) + x
        else:
            c += (x - t) + f_result
        f_result = t
    return f_result + c

def _chain(head, tail):
    yield from head
    yield from tail

builtins.sum = _sum_312
sys.argv = [sys.argv[1], "--check"]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit as e:
    sys.exit(e.code or 0)
'''


def _load_module():
    spec = importlib.util.spec_from_file_location("gamebooks_2ecbccfd_stability", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _committed_minutes():
    """{club: [float minutes of every played row]} from the committed artefact."""
    data = json.load(open(ARTEFACT, encoding="utf-8"))
    clubs = {}
    for r in data["rows"]:
        if r["status"] == "played" and r.get("min") is not None:
            clubs.setdefault(r["club"], []).append(r["min"])
    return clubs


def _naive(xs):
    t = 0.0
    for x in xs:
        t = t + x
    return t


def _neumaier(xs):
    t = 0.0
    c = 0.0
    for x in xs:
        tt = t + x
        if abs(t) >= abs(x):
            c += (t - tt) + x
        else:
            c += (x - tt) + t
        t = tt
    return t + c


class InterpreterStabilityTests(unittest.TestCase):
    def test_committed_artefact_equals_script_output(self):
        r = subprocess.run([sys.executable, SCRIPT, "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         "gamebooks --check disagrees with the committed artefact on the "
                         f"native interpreter:\n{r.stdout}\n{r.stderr}")

    def test_committed_artefact_survives_3_12_summation_semantics(self):
        """The regression: before the fsum fix this exited 1 under simulated 3.12 semantics
        (the Wizards share regenerated as 0.1087 against a committed 0.1088), which is what
        failed the hosted scheduled runs since 2026-11-17."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix="_driver.py", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(DRIVER)
            driver = fh.name
        try:
            r = subprocess.run([sys.executable, driver, SCRIPT], cwd=ROOT,
                               capture_output=True, text=True)
        finally:
            os.unlink(driver)
        self.assertEqual(r.returncode, 0,
                         "the committed artefact is interpreter-sensitive: under simulated "
                         f"3.12 sum() semantics the replay disagrees\n{r.stdout}\n{r.stderr}")

    def test_simulation_is_not_vacuous(self):
        """The simulated 3.12 summation really differs from 3.11's on this data, otherwise test 2
        would pass without proving anything. At least one club's unrounded total must differ."""
        clubs = _committed_minutes()
        differing = [club for club, mins in clubs.items()
                     if _naive(mins) != _neumaier(mins)]
        self.assertTrue(differing,
                        "the Neumaier simulation no longer differs from naive summation on the "
                        "committed minutes; the guard is vacuous and must be re-derived")
        self.assertIn("WASHINGTON WIZARDS", differing,
                      "the club whose committed share byte the runner flipped is no longer "
                      "exercised by the simulation")

    def test_float_aggregates_are_fsum_in_source(self):
        src = open(SCRIPT, encoding="utf-8").read()
        self.assertIn("math.fsum", src, "gamebooks_2ecbccfd.py stopped using math.fsum")
        # every remaining builtin sum() in the script must sum integers only (exact on every
        # interpreter): the float-bearing ones must be spelled fsum.
        for m in re.finditer(r"(?<![\w.])sum\(([^)]*)\)", src):
            expr = m.group(1)
            self.assertFalse(re.search(r"\bmin\b", expr),
                             f"builtin sum() over minutes found in the payload path: {m.group(0)}")


if __name__ == "__main__":
    unittest.main()
