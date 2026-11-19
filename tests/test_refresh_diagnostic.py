"""Guards for scripts/run_suite_battery.py — the step that must never fail silently.

Context (evidence, not theory): the scheduled `official data refresh` job was red from run
43982186917 through 44424736929 at its unit-test step, which could only report "at least one
unittest suite failed". The suites passed in a sandbox, so the red was an interpreter difference —
the runner's `/usr/bin/python3` is 3.12.3 while this workflow's publishing job pins 3.11 — and no
session could name the failing suite because the Actions log body is not retrievable from every
environment (an annotation from run 44616982969 is what finally localised it: `suite
test_refresh_official.py failed under Python 3.12.3 ... tail: FAIL:
test_published_slate_matches_the_promotion (unittest.loader._FailedTest.`). A loader failure, not a
data failure: the step was invoking one suite as a FILE PATH (`python -m unittest
tests/test_refresh_official.py`), which 3.11 deprecated and newer interpreters no longer accept.

These tests pin the three properties that make that failure class impossible to repeat: the
invocation is interpreter-portable, the workflow has exactly one suite list, and a failure is
reported through the annotations API rather than only in a log body.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import run_suite_battery as battery  # noqa: E402


class InvocationTests(unittest.TestCase):
    def test_no_suite_is_invoked_as_a_file_path(self):
        """`python -m unittest <path>/<file>.py` is the deprecated form; keep the argv clean of it.

        Only the TEST-NAME position matters: `discover -s tests -p test_x.py` passes a filename to
        `-p`, which is the documented, stable form (the pattern is matched against names inside the
        directory). What must never appear again is a path or file name in the position where
        unittest expects a dotted module name.
        """
        for pattern, mode in battery.SUITES:
            with self.subTest(pattern=pattern):
                argv = battery.suite_command("PY", pattern, mode)
                self.assertEqual(argv[:3], ["PY", "-m", "unittest"], argv)
                name_pos = argv[3]   # the position unittest reads as a test/module name
                self.assertNotIn("/", name_pos, f"{argv}: unittest's name position holds a path")
                self.assertFalse(name_pos.endswith(".py"),
                                 f"{argv}: unittest's name position holds a file name "
                                 f"(deprecated 3.11, removed in newer interpreters)")
                if mode == "discover":
                    self.assertEqual(name_pos, "discover")
                    self.assertEqual(argv[argv.index("-s") + 1], "tests")
                    self.assertNotIn("/", argv[argv.index("-p") + 1])

    def test_module_form_resolves_to_a_dotted_import_name(self):
        argv = battery.suite_command("PY", "test_refresh_official.py", "module")
        self.assertEqual(argv, ["PY", "-m", "unittest", "tests.test_refresh_official", "-v"])

    def test_discover_form_keeps_the_pattern_untouched(self):
        argv = battery.suite_command("PY", "test_*1115*.py", "discover")
        self.assertEqual(argv, ["PY", "-m", "unittest", "discover", "-s", "tests",
                                "-p", "test_*1115*.py", "-v"])

    def test_module_form_actually_loads_tests_under_this_interpreter(self):
        """A silent zero-test run would look exactly like the bug this file guards."""
        proc = subprocess.run(battery.suite_command(sys.executable, "test_refresh_official.py",
                                                    "module"),
                              cwd=ROOT, capture_output=True, text=True)
        combined = (proc.stdout or "") + (proc.stderr or "")
        # This test is about the argv SHAPE, not about whether the suite is currently green: a data
        # failure inside the suite must fail its own test, not turn into a second, misleading
        # "the invocation is broken" report.
        self.assertNotIn("unittest.loader._FailedTest", combined,
                         "the interpreter could not load the suite by this name: "
                         + combined[-400:])
        self.assertGreaterEqual(battery_ran(proc), 20,
                                "the dotted module form loaded almost no tests; it is not equivalent")


class SuiteListTests(unittest.TestCase):
    def test_workflow_has_no_inline_list_to_fork(self):
        self.assertIsNone(battery.workflow_suite_list(),
                          ".github/workflows/refresh.yml gained its own suite list again; the "
                          "script's SUITES constant is the single source of truth")

    def test_workflow_runs_the_battery_as_a_hard_gate(self):
        with open(os.path.join(ROOT, ".github", "workflows", "refresh.yml"), encoding="utf-8") as fh:
            text = fh.read()
        step = text[text.index("- name: Unit tests against the committed tree"):]
        step = step[:step.index("\n      - name:")]
        self.assertIn("scripts/run_suite_battery.py", step)
        self.assertNotIn("--report-only", step,
                         "the refresh job must not downgrade its own unit-test gate to a report")
        self.assertNotIn("always()", step)

    def test_every_pattern_matches_a_real_file(self):
        names = sorted(os.listdir(os.path.join(ROOT, "tests")))
        for pattern, _mode in battery.SUITES:
            with self.subTest(pattern=pattern):
                if "*" in pattern:
                    import fnmatch
                    self.assertTrue([n for n in names if fnmatch.fnmatch(n, pattern)],
                                    f"{pattern} matches nothing in tests/")
                else:
                    self.assertIn(pattern, names, f"{pattern} is not a file in tests/")

    def test_step_keeps_both_diagnostic_intents(self):
        """Merge resolution with session b1ce1334 (B1-1): their per-suite transcript and artifact
        must survive the battery that replaced their shell loop."""
        with open(os.path.join(ROOT, ".github", "workflows", "refresh.yml"), encoding="utf-8") as fh:
            text = fh.read()
        step = text[text.index("- name: Unit tests against the committed tree"):]
        step = step[:step.index("\n      - name:", 1)]
        self.assertIn('--log-dir "$RUNNER_TEMP/unit-logs"', step,
                      "the battery must still write the per-suite logs the artifact uploads")
        self.assertIn("unit-test-logs-${{ github.run_id }}", text,
                      "b1ce1334's unit-test-logs artifact step was dropped")
        self.assertIn("${{ runner.temp }}/unit-logs", text)

    def test_pages_parity_step_exists_and_is_report_only(self):
        with open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8") as fh:
            text = fh.read()
        marker = "- name: Refresh-job parity battery"
        self.assertIn(marker, text)
        step = text[text.index(marker):]
        step = step[:step.index("\n      - name:") + 1 if "\n      - name:" in step[1:] else len(step)]
        self.assertIn("--python /usr/bin/python3", step)
        self.assertIn("--report-only", step)
        self.assertIn("continue-on-error: true", step)


class AnnotationTests(unittest.TestCase):
    def test_workflow_command_escaping(self):
        # GitHub drops a workflow command whose payload still contains a raw CR/LF or a bare %.
        line = battery.escape_annotation("a 50% win\r\nrate\nsecond line")
        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)
        self.assertEqual(line, "a 50%25 win%0Arate%0Asecond line")

    def test_every_annotation_fits_the_runner_limit(self):
        # Observed on run 44616982969: the API cut the message at 563 characters.
        self.assertLessEqual(battery.ANNOTATION_MAX, 500)
        long = "x" * 4000
        self.assertLessEqual(len(battery.escape_annotation(long)), battery.ANNOTATION_MAX + 10)

    def test_failing_test_ids_are_extracted(self):
        out = ("test_a (tests.test_x.Case.test_a) ... ok\n"
               "test_b (tests.test_x.Case.test_b) ... FAIL\n"
               "======================================================================\n"
               "FAIL: test_b (tests.test_x.Case.test_b)\n"
               "----------------------------------------------------------------------\n"
               "AssertionError: 1 != 2\n")
        self.assertEqual(battery.failed_test_ids(out), ["test_b (tests.test_x.Case.test_b)"])

    def test_loader_failure_detail_is_surfaced(self):
        out = ("ERROR: test_z (unittest.loader._FailedTest.test_z)\n"
               "----------------------------------------------------------------------\n"
               "ImportError: Failed to import test module: tests/test_z.py\n"
               "Traceback (most recent call last):\n"
               "  File \"<frozen importlib._bootstrap>\", line 1, in _find\n"
               "ModuleNotFoundError: No module named 'tests.test_z.py'\n"
               "----------------------------------------------------------------------\n"
               "Ran 1 test in 0.001s\n")
        detail = battery.loader_failure(out)
        self.assertIn("ImportError", detail)
        self.assertIn("ModuleNotFoundError", detail)

    def test_zero_test_run_is_reported_as_a_failure(self):
        rc, ran = battery.summarize(subprocess.CompletedProcess(
            [], 5, stdout="", stderr="Ran 0 tests in 0.000s\n\nOK\n"))
        self.assertEqual(rc, 5)
        self.assertEqual(ran, 0)


def battery_ran(proc):
    import re
    m = re.search(r"^Ran (\d+) tests?", proc.stderr or proc.stdout or "", re.M)
    return int(m.group(1)) if m else 0


if __name__ == "__main__":
    unittest.main()
