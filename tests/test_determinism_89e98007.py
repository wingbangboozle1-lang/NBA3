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

# The rule the repository ratified for published float sums on 2026-11-19 (session f69a11c4,
# main@78f513d): the correctly-rounded exact sum. The artefact carries its answer; the pre-3.12
# naive fold is the one that used to be published and is still what the runner produced BEFORE the
# fix — both numbers stay asserted so nobody re-flips the rule by accident.
WA_PUBLISHED = 0.1087          # det.sum_ / math.fsum: what data/rounds/2026-11-17 now says
WA_UNDER_NAIVE_FOLD = 0.1088   # the pre-3.12 answer this file held until 2026-11-19


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

    def test_the_two_rules_still_differ_on_the_published_minutes(self):
        """The exposure is real, not theoretical: the two summations disagree on this input."""
        mins = washington_minutes()
        self.assertEqual(det.fold(mins), naive(mins))
        self.assertEqual(det.fold(mins), 239.99999999999997)
        self.assertEqual(det.sum_(mins), math.fsum(mins))
        self.assertNotEqual(det.fold(mins), det.sum_(mins),
                            "if these ever agree, the divergence is gone and the pin can be "
                            "revisited — see verify/determinism_89e98007.md")

    def test_ratified_rule_is_exact_for_floats_and_int_exact_for_counts(self):
        # an int count must stay an int: JSON publishes 24 and 24.0 differently
        self.assertEqual(det.sum_([1, 2, 3]), 6)
        self.assertIsInstance(det.sum_([1, 2, 3]), int)
        self.assertEqual(det.sum_([]), 0)
        self.assertEqual(det.sum_([0.1, 0.2, 0.7]), 1.0, "fsum: no drift")


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
        tot = det.sum_(mins)
        share = det.dq(26.1 / tot, 4)
        self.assertEqual(share, WA_PUBLISHED)
        with open(PLAYER_LOGS, encoding="utf-8") as fh:
            doc = json.load(fh)
        ent = [v for k, v in doc["top8_minutes_shares"].items() if "WAS" in k][0]
        self.assertEqual(ent["top8"][4]["player"], "Trae Young")
        self.assertEqual(ent["top8"][4]["share"], WA_PUBLISHED)

    def test_naive_fold_would_republish_the_old_number(self):
        """The rule choice is recorded, in both directions.

        main@78f513d republished this one field to the exact-sum answer. Anyone re-pinning the
        naive fold would silently move it back, which is a republish of a value the pick ledger
        hashed — so it must be a reviewed commit, not a side effect of a refactor.
        """
        mins = washington_minutes()
        self.assertEqual(det.dq(26.1 / det.fold(mins), 4), WA_UNDER_NAIVE_FOLD)
        self.assertNotEqual(WA_UNDER_NAIVE_FOLD, WA_PUBLISHED)

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

    def test_the_emulator_moves_the_unpinned_expression_and_nothing_else(self):
        """The shim must actually reproduce the runner, and the pinned expressions must not move.

        The first version of this test asserted what *this interpreter's* ``sum()`` returned, which is
        exactly the mistake it exists to catch: it passed on 3.11 and failed on the runner's 3.14.4
        (probe run 44478784862). So the assertion is now about the two pinned rules, which never call
        the builtin, plus one check that the shim itself works.
        """
        code = textwrap.dedent("""
            import json, math, os, sys
            sys.path.insert(0, os.path.join(sys.argv[2], "scripts"))
            import determinism as det
            doc = json.load(open(sys.argv[1], encoding="utf-8"))
            mins = [r["min"] or 0 for r in doc["clubs"]["WASHINGTON WIZARDS"]["rows"]
                    if r["status"] == "played"]
            print("fold", repr(det.fold(mins)), repr(det.dq(26.1 / det.fold(mins), 4)))
            print("exact", repr(det.sum_(mins)), repr(det.dq(26.1 / det.sum_(mins), 4)))
            print("builtin", repr(sum(mins)), repr(round(sum(mins), 2)))
        """)
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "probe.py")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(code)
            shim_dir = os.path.join(td, "shim")
            os.makedirs(shim_dir)
            with open(os.path.join(shim_dir, "sitecustomize.py"), "w", encoding="utf-8") as fh:
                fh.write(self.SHIM)
            env = dict(os.environ, PYTHONPATH=shim_dir)
            plain = subprocess.run([sys.executable, p, PLAYER_LOGS, ROOT], capture_output=True,
                                   text=True, cwd=ROOT, timeout=120)
            shim = subprocess.run([sys.executable, p, PLAYER_LOGS, ROOT], capture_output=True,
                                  text=True, env=env, cwd=ROOT, timeout=120)
        for out, label in ((plain.stdout, "plain"), (shim.stdout, "shim")):
            self.assertNotEqual(out, "", f"{label} run produced nothing: {plain.stderr}{shim.stderr}")
            self.assertIn(f"fold {239.99999999999997!r} {WA_UNDER_NAIVE_FOLD!r}", out,
                          f"det.fold must give the pre-3.12 answer on {label} (it never calls sum())")
            self.assertIn(f"exact {240.0!r} {WA_PUBLISHED!r}", out,
                          f"det.sum_ must give the ratified answer on {label}")
        self.assertIn("builtin 240.0 240.0", shim.stdout,
                      "the sitecustomize was not applied — this test would prove nothing")

class GateDiagnosisTests(unittest.TestCase):
    def test_value_drift_names_the_json_path(self):
        with open(PLAYER_LOGS, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["top8_minutes_shares"]["2026-11-15:WAS"]["top8"][4]["share"] = 0.1088
        blob = json.dumps(doc, indent=1) + "\n"
        ok, detail = det.check_artefact(PLAYER_LOGS, blob)
        self.assertFalse(ok)
        self.assertIn("top8_minutes_shares", detail)
        self.assertIn("0.1088", detail)
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
