"""Tests for session arena/dd3edd74-nba3 (tasks D1 and D2). Offline; no network, no clock.

D2 — the official finals for 2026-11-16/17/18 artefact is re-verified against the committed slate and
     the independent 11/18 capture, and the checks are shown to FAIL on planted errors (a check that cannot
     fail proves nothing).
D1 — the gamebooks `--check` gate keeps its exit code, and on a mismatch it names the first differing line.
     Exercised on a scratch copy of the three committed inputs, never on the real artefact.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "capture_dd3edd74.py")


def _load():
    spec = importlib.util.spec_from_file_location("capture_dd3edd74", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CAP = _load()


class FinalsArtefactTests(unittest.TestCase):
    def setUp(self):
        with open(CAP.OUT, encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_artefact_is_exactly_the_script_output(self):
        self.assertEqual(self.data, CAP.payload())

    def test_every_check_passes_on_the_committed_artefact(self):
        failed = [name for name, ok, _ in CAP.checks(self.data) if not ok]
        self.assertEqual(failed, [])

    def test_check_mode_exits_zero(self):
        rc = subprocess.run([sys.executable, SCRIPT, "--check"], cwd=ROOT,
                            capture_output=True, text=True).returncode
        self.assertEqual(rc, 0)

    def test_twenty_five_games_one_row_each(self):
        self.assertEqual(len(self.data["games"]), 25)
        self.assertEqual(self.data["counts"], {"2026-11-16": 8, "2026-11-17": 5, "2026-11-18": 12})

    def test_no_quarter_score_is_invented(self):
        for g in self.data["games"]:
            self.assertIsNone(g["quarter_scores"], g["game_id"])
            self.assertIn("UNVERIFIED", g["quarter_scores_flag"])

    def test_every_row_has_an_official_https_source(self):
        for g in self.data["games"]:
            self.assertTrue(g["sources"], g["game_id"])
            for url in g["sources"]:
                self.assertTrue(url.startswith("https://www.nba.com/"), url)

    def test_planted_score_error_is_caught(self):
        bad = copy.deepcopy(self.data)
        bad["games"][0]["home_pts"] += 1  # 0022600245 ORL 115 - BOS 105 -> BOS 106
        results = dict((name, ok) for name, ok, _ in CAP.checks(bad))
        self.assertFalse(results["recap slugs repeat the score table (winner score first)"])

    def test_planted_11_18_disagreement_is_caught(self):
        bad = copy.deepcopy(self.data)
        for g in bad["games"]:
            if g["game_id"] == "0022600262":
                g["away_pts"] = 138
        results = dict((name, ok) for name, ok, _ in CAP.checks(bad))
        self.assertFalse(results["11/18 finals agree with the independent b1ce1334 capture (12/12)"])

    def test_planted_filled_quarter_is_caught(self):
        bad = copy.deepcopy(self.data)
        bad["games"][3]["quarter_scores"] = [30, 30, 30, 30]
        results = dict((name, ok) for name, ok, _ in CAP.checks(bad))
        self.assertFalse(results["no quarter value is filled in (all null)"])

    def test_planted_team_mismatch_against_slate_is_caught(self):
        bad = copy.deepcopy(self.data)
        bad["games"][0]["home"] = "NYK"
        results = dict((name, ok) for name, ok, _ in CAP.checks(bad))
        self.assertFalse(results["every game matches the committed official slate (date, away, home)"])


class GamebookCheckDiagnosticTests(unittest.TestCase):
    """D1: the failing `--check` names its cause; the gate's exit codes are unchanged."""

    INPUTS = [
        os.path.join("scripts", "gamebooks_2ecbccfd.py"),
        # the script imports floatsum from its own directory so that its float sums are
        # interpreter-independent; the scratch copy needs that module or the import fails
        # before --check can run (E929-F01 / E1 float-sum fix).
        os.path.join("scripts", "floatsum.py"),
        os.path.join("data", "live", "team_registry.json"),
    ]

    def _scratch(self):
        tmp = tempfile.mkdtemp(prefix="dd3-gb-")
        self.addCleanup(shutil.rmtree, tmp, True)
        for rel in self.INPUTS:
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(os.path.join(ROOT, rel), dst)
        shutil.copytree(os.path.join(ROOT, "data", "rounds", "2026-11-17", "captures"),
                        os.path.join(tmp, "data", "rounds", "2026-11-17", "captures"))
        shutil.copy(os.path.join(ROOT, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json"),
                    os.path.join(tmp, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json"))
        return tmp

    def _check(self, tmp):
        return subprocess.run([sys.executable, os.path.join(tmp, "scripts", "gamebooks_2ecbccfd.py"), "--check"],
                              cwd=tmp, capture_output=True, text=True)

    def test_committed_inputs_pass_with_exit_zero(self):
        tmp = self._scratch()
        self.assertEqual(self._check(tmp).returncode, 0)

    def test_mismatch_exits_one_and_names_the_first_differing_line(self):
        tmp = self._scratch()
        p = os.path.join(tmp, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json")
        with open(p, encoding="utf-8") as fh:
            s = fh.read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(s.replace('"pts"', '"pts "', 1))
        res = self._check(tmp)
        self.assertEqual(res.returncode, 1)
        self.assertIn("first differing line 27", res.stdout)
        self.assertIn('"pts "', res.stdout)
        self.assertIn("committed  :", res.stdout)
        self.assertIn("regenerated:", res.stdout)


if __name__ == "__main__":
    unittest.main()
