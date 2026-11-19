"""Structural checks on the scheduled refresh's unit-test step (session de0caf5d, task X1).

These do not run the workflow. They pin the properties that make a red run diagnosable and
guarantee that the gate itself was not weakened: every suite still runs, the exit status is not
masked, and the failure artifact includes the unit-test log.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "refresh.yml")

SUITES = [
    "test_*1115*.py", "test_results_feed.py", "test_pick_ledger.py",
    "test_freshness_gates.py", "test_refresh_official.py",
    "test_results_feed_rows.py", "test_gamecard_feed.py", "test_standings_feed.py",
    "test_round_2ecbccfd.py",
]


def _step(text, name_prefix):
    start = text.index(f"- name: {name_prefix}")
    end = text.find("\n      - name:", start + 1)
    return text[start:] if end < 0 else text[start:end]


class UnitStepDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.unit = _step(cls.text, "Unit tests against the committed tree")
        cls.upload = _step(cls.text, "Upload refresh diagnostics from a failed gate")

    def test_every_suite_is_still_in_the_gate(self):
        for suite in SUITES:
            self.assertIn(f'"{suite}"', self.unit, suite)

    def test_no_failure_is_masked(self):
        # "|| true" is allowed only on the annotation grep, which runs after the failure is known
        # and is followed by an unconditional `exit 1`.
        for line in self.unit.splitlines():
            if "|| true" in line:
                self.assertIn("failing test:", line)
        self.assertNotIn("continue-on-error", self.unit)
        self.assertIn("exit 1", self.unit)
        self.assertIn("set -uo pipefail", self.unit)  # pipefail: tee cannot hide a failing python

    def test_unit_output_is_kept_and_named(self):
        self.assertIn('LOG="${RUNNER_TEMP}/nba3-unit-tests.log"', self.unit)
        self.assertRegex(self.unit, r"2>&1 \| tee -a \"\$LOG\"")
        self.assertIn("::error::failing test:", self.unit)
        self.assertRegex(self.unit, r"\^\(ERROR\|FAIL\):")

    def test_failure_artifact_includes_the_unit_log(self):
        self.assertIn("if: failure() && !cancelled()", self.upload)
        self.assertIn("${{ runner.temp }}/nba3-unit-tests.log", self.upload)
        self.assertIn("if-no-files-found: ignore", self.upload)

    def test_upload_step_runs_only_on_failure(self):
        self.assertNotIn("success()", self.upload)


if __name__ == "__main__":
    unittest.main()
