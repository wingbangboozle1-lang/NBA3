"""Determinism tests (session arena/89e98007-nba3) — the EVE-F04 fix.

Every committed artefact in `data/rounds/2026-11-17` is re-derived by CI and compared byte-for-byte
with the committed file. That makes the published numbers a function of the *interpreter* as well
as of the data, and CPython 3.12 changed `sum()` for floats to Neumaier compensated summation
(https://docs.python.org/3/whatsnew/3.12.html, gh-100425;
https://docs.python.org/3/library/functions.html#sum "Changed in version 3.12"). GitHub's
`ubuntu-latest` ships 3.14.4, so from run 44143781953 (2026-11-17) on, the scheduled refresh died
at its committed-tree preflight and no official source has been fetched since.

These tests pin, rather than describe:

* `fold` reproduces the naive left-to-right addition the committed artefacts were built with, and
  every replayed gate stays green when `builtins.sum` is replaced by a 3.12+-style compensated
  summation (`EmulatedInterpreterTests` runs the real gate in a subprocess with a `sitecustomize`
  that installs Neumaier summation — the exact failure, reproducible on demand);
* the one field that moved is asserted at its published value, through the pinned rule;
* a drift failure now names the JSON path that moved.

Run: python3 -m unittest tests.test_determinism_89e98007
"""
from __future__ import annotations

import ast
import json
import math
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import determinism as det  # noqa: E402

RD = os.path.join(ROOT, "data", "rounds", "2026-11-17")
PLAYER_LOGS = os.path.join(RD, "player_logs_2026-11-15.json")

# The build chain the refresh workflow replays on the committed tree. Anything here must not lean
# on interpreter-flavoured float arithmetic.
BUILD_CHAIN = ["scripts/gamebooks_2ecbccfd.py", "scripts/capture_2ecbccfd.py",
               "scripts/slate_extra_2ecbccfd.py", "scripts/model_2ecbccfd.py",
               "scripts/ledger_2ecbccfd.py", "round_2ecbccfd/build.py"]

WA_SHOULD_BE = 0.1088          # the value the ledger and the site were built from
WA_UNDER_COMPENSATED_SUM = 0.1087   # what CPython >= 3.12 produced on the runner


def naive(values, start=0):
    acc = start
    for v in values:
        acc = acc + v
    return acc


class FoldTests(unittest.TestCase):
    def test_fold_is_plain_left_to_right_addition(self):
        vals = [1e100, 1.0, -1e100]
        self.assertEqual(det.fold(vals), 0.0, "a fold cancels; compensation would keep the 1.0")
        self.assertEqual(math.fsum(vals), 1.0, "the accurate rule, shown for contrast")

    def test_fold_keeps_ints_ints(self):
        self.assertEqual(det.fold([1, 2, 3]), 6)
        self.assertIsInstance(det.fold([1, 2, 3]), int)
        self.assertEqual(det.fold([]), 0)
        self.assertIsInstance(det.fold([]), int)
        self.assertEqual(det.fold([0.5, 0.5]), 1.0)

    def test_fold_matches_the_sum_that_generated_the_committed_artefacts(self):
        mins = washington_minutes()
        self.assertEqual(det.fold(mins), naive(mins))
        self.assertEqual(det.fold(mins), 239.99999999999997)
        self.assertNotEqual(det.fold(mins), math.fsum(mins),
                            "if these ever agree the divergence is gone and the pin can be "
                            "revisited — see verify/determinism_89e98007.md")


class DqTests(unittest.TestCase):
    def test_ties_to_even_on_the_exact_value(self):
        self.assertEqual(det.dq(0.5), 0)
        self.assertEqual(det.dq(1.5), 2)
        self.assertEqual(det.dq(2.675, 2), 2.67, "2.675 is below the tie in binary")

    def test_none_and_types(self):
        self.assertIsNone(det.dq(None, 4))
        self.assertEqual(det.dq(-107, 2), -107)
        self.assertIsInstance(det.dq(-107, 2), int, "a settled line must not become -107.0")
        self.assertIsInstance(det.dq(1.0, 2), float)

    def test_agrees_with_the_builtin_on_this_interpreter_for_clean_values(self):
        for x in (0.5, 1.25, 2.5, 3.14159, 10.0 - 9.99, 1234.5678, -0.005):
            for n in (0, 1, 2, 3, 4, 6):
                self.assertEqual(det.dq(x, n), round(x, n), f"dq({x!r}, {n})")


def washington_minutes():
    with open(PLAYER_LOGS, encoding="utf-8") as fh:
        doc = json.load(fh)
    blk = doc["clubs"]["WASHINGTON WIZARDS"]
    return [r["min"] or 0 for r in blk["rows"] if r["status"] == "played"]


class TheFieldThatMovedTests(unittest.TestCase):
    """The single number that froze the pipeline, asserted at its published value."""

    def test_pinned_rule_reproduces_the_published_share(self):
        mins = washington_minutes()
        tot = det.fold(mins)
        share = det.dq(26.1 / tot, 4)
        self.assertEqual(share, WA_SHOULD_BE)
        with open(PLAYER_LOGS, encoding="utf-8") as fh:
            doc = json.load(fh)
        ent = [v for k, v in doc["top8_minutes_shares"].items() if "WAS" in k][0]
        self.assertEqual(ent["top8"][4]["player"], "Trae Young")
        self.assertEqual(ent["top8"][4]["share"], WA_SHOULD_BE)

    def test_compensated_rule_would_republish_a_different_number(self):
        """Why the pin is the naive fold and not the more accurate sum.

        The more accurate summation is not free here: model.json, the sealed pick hashes and the
        published pages were built from the naive value. Switching rules is a republish, not a
        bug fix, so it is a decision for the owner (flagged for review, not made here).
        """
        mins = washington_minutes()
        self.assertEqual(det.dq(26.1 / math.fsum(mins), 4), WA_UNDER_COMPENSATED_SUM)
        self.assertNotEqual(WA_UNDER_COMPENSATED_SUM, WA_SHOULD_BE)

    def test_the_gate_passes_on_the_committed_tree(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gamebooks_2ecbccfd.py"),
                            "--check"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class EmulatedInterpreterTests(unittest.TestCase):
    """Run the real gate on an interpreter whose sum()/round() behave like CPython >= 3.12."""

    SHIM = textwrap.dedent("""
        # Sitecustomize: install the float summation CPython >= 3.12 uses, so this repository can be
        # replayed on an interpreter that behaves like the runner's, from any interpreter.
        #
        # Only sum() is replaced. CPython 3.14.4's round(x, n) agrees with det.dq on the field that
        # moved (0.108749999999999999444 -> 0.1087 is the exact-value half-even answer), which is how
        # run 44467720829 reported 0.1087 once its sum() had become 240.0. The summation rule is the
        # whole defect; rounding was never it.
        import builtins

        _real_sum = builtins.sum

        def sum_(iterable=(), start=0):
            items = list(iterable)
            if any(isinstance(v, float) for v in items):
                acc = float(start)
                c = 0.0
                for v in items:
                    t = acc + v
                    if abs(acc) >= abs(v):
                        c += (acc - t) + v
                    else:
                        c += (v - t) + acc
                    acc = t
                return acc + c
            return _real_sum(items, start)

        builtins.sum = sum_
    """)

    def _run(self, script):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "sitecustomize.py"), "w", encoding="utf-8") as fh:
                fh.write(self.SHIM)
            env = dict(os.environ, PYTHONPATH=td + os.pathsep + os.environ.get("PYTHONPATH", ""))
            r = subprocess.run([sys.executable, os.path.join(ROOT, script), "--check"],
                               capture_output=True, text=True, cwd=ROOT, env=env, timeout=600)
            return r

    def test_every_replayed_gate_survives_a_3_12_style_interpreter(self):
        for script in ("scripts/gamebooks_2ecbccfd.py", "scripts/capture_2ecbccfd.py",
                       "scripts/slate_extra_2ecbccfd.py", "scripts/model_2ecbccfd.py",
                       "scripts/ledger_2ecbccfd.py", "round_2ecbccfd/build.py"):
            with self.subTest(script=script):
                r = self._run(script)
                self.assertEqual(r.returncode, 0,
                                 f"{script} --check drifted under an emulated 3.12+ interpreter:"
                                 f"\n{r.stdout}\n{r.stderr}")

    def test_the_emulator_would_have_caught_the_original_failure(self):
        """The shim is not a no-op: it reproduces the divergence on the un-pinned expression."""
        code = textwrap.dedent('''
            import json, sys
            doc = json.load(open(sys.argv[1], encoding="utf-8"))
            mins = [r["min"] or 0 for r in doc["clubs"]["WASHINGTON WIZARDS"]["rows"]
                    if r["status"] == "played"]
            print(round(sum(mins), 2), round(26.1 / sum(mins), 4))
        ''')
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "sitecustomize.py"), "w", encoding="utf-8") as fh:
                fh.write(self.SHIM)
            p = os.path.join(td, "check.py")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(code)
            env = dict(os.environ, PYTHONPATH=td)
            shim = subprocess.run([sys.executable, p, PLAYER_LOGS], capture_output=True,
                                  text=True, env=env, cwd=ROOT, timeout=120)
            plain = subprocess.run([sys.executable, p, PLAYER_LOGS], capture_output=True,
                                   text=True, cwd=ROOT, timeout=120)
        self.assertIn(f"{WA_SHOULD_BE}", plain.stdout, "plain interpreter must give the published value")
        self.assertIn("240.0", shim.stdout)
        self.assertIn(f"{WA_UNDER_COMPENSATED_SUM}", shim.stdout,
                      "the emulator must move the share exactly as the runner did")
        self.assertNotEqual(shim.stdout, plain.stdout,
                            "the sitecustomize was not applied — this test would prove nothing")


class GateDiagnosisTests(unittest.TestCase):
    def test_value_drift_names_the_json_path(self):
        with open(PLAYER_LOGS, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["top8_minutes_shares"]["2026-11-15:WAS"]["top8"][4]["share"] = 0.1087
        blob = json.dumps(doc, indent=1) + "\n"
        ok, detail = det.check_artefact(PLAYER_LOGS, blob)
        self.assertFalse(ok)
        self.assertIn("top8_minutes_shares", detail)
        self.assertIn("0.1087", detail)
        self.assertTrue(detail.startswith("value drift"), detail)

    def test_formatting_only_drift_is_not_called_a_value_change(self):
        with open(PLAYER_LOGS, encoding="utf-8") as fh:
            raw = fh.read()
        blob = json.dumps(json.loads(raw), indent=2) + "\n"
        ok, detail = det.check_artefact(PLAYER_LOGS, blob)
        self.assertTrue(ok, detail)
        self.assertIn("formatting only", detail)

    def test_missing_artefact_is_reported_as_missing(self):
        ok, detail = det.check_artefact(os.path.join(ROOT, "nope.json"), "{}\n")
        self.assertFalse(ok)
        self.assertIn("missing", detail)


class BuildChainStyleTests(unittest.TestCase):
    """No artefact writer in the replayed chain may lean on the interpreter's sum()/round()."""

    def _bare_calls(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src)
        out = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("sum", "round"):
                out.append((n.func.id, n.lineno))
        return out

    def test_build_chain_has_no_bare_sum_or_round(self):
        for rel in BUILD_CHAIN:
            with self.subTest(file=rel):
                self.assertEqual(self._bare_calls(rel), [],
                                 f"{rel} calls the interpreter's sum()/round(); artefacts it writes "
                                 f"must go through det.fold/det.dq (scripts/determinism.py)")

    def test_determinism_module_is_the_pinned_documented_rule(self):
        with open(os.path.join(ROOT, "scripts", "determinism.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("Neumaier", src)
        self.assertIn("whatsnew/3.12", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
