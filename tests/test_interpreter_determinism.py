"""Interpreter determinism for the byte-pinned artefacts (session arena/9c30f2ae-nba3).

WHY THIS FILE EXISTS
--------------------
On 2026-11-19 the scheduled `official data refresh` (run 44469939831) failed at its pre-fetch
unit-test step with

    FAIL: test_committed_round_captures_replay_before_the_live_fetch
          (tests.test_refresh_official.WorkflowGateTests...) (script='gamebooks_2ecbccfd.py')

and the hosted run's own annotation named the interpreter: "under Python 3.14.4 ... this tree is
green under another interpreter, so the interpreter line is part of the diagnosis". Twelve earlier
scheduled runs had failed the same step with no readable log body.

The cause is CPython 3.12's change of builtin sum() to Neumaier compensated summation for floats
(https://docs.python.org/3/whatsnew/3.12.html#other-language-changes). A float reduction through
sum() therefore returns a different float on 3.11 than on 3.12+. Two committed artefacts are
byte-pinned by their own --check and by tests:

  * data/rounds/2026-11-17/player_logs_2026-11-15.json (top-8 minutes shares), and
  * data/rounds/2026-11-16-1300PM/model.json (league averages).

Both are now computed from exact integer inputs (whole seconds; math.fsum), so the same bytes come
out of every interpreter. This test pins that property: exact arithmetic helpers, integer aggregates,
one correctly-rounded division per share, artefact reproduction on the running interpreter, and an
AST guard so a future edit cannot quietly reintroduce a float sum() into the producers.

Run: python3 -m unittest tests/test_interpreter_determinism.py
Verified under CPython 3.11.2 (sandbox) and CPython 3.14.4 (built from tag v3.14.4 to reproduce the
hosted failure): 315 tests OK on both after the fix.
"""
import ast
import json
import math
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gamebooks_2ecbccfd as gb  # noqa: E402

LOGS = os.path.join(ROOT, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json")
MODEL_1300 = os.path.join(ROOT, "data", "rounds", "2026-11-16-1300PM", "model.json")


class MinutesArithmeticTests(unittest.TestCase):
    def test_seconds_are_exact_integers(self):
        self.assertEqual(gb.minutes_seconds_of("33:51"), 2031)
        self.assertEqual(gb.minutes_seconds_of("00:00"), 0)
        self.assertEqual(gb.minutes_seconds_of("240:00"), 14400)
        self.assertIsNone(gb.minutes_seconds_of(""))
        self.assertIsNone(gb.minutes_seconds_of("DNP"))

    def test_minutes_are_one_rounded_division_of_the_exact_seconds(self):
        for text in ("33:51", "24:30", "26:06", "02:19", "02:34", "00:01", "48:00"):
            sec = gb.minutes_seconds_of(text)
            self.assertEqual(gb.minutes_of(text), sec / 60.0, text)

    def test_the_two_cells_where_the_spellings_disagree_are_pinned(self):
        # 2:19 and 2:34 are the two cells where ``mm + ss/60`` and ``(mm*60+ss)/60`` differ in the
        # last bit, so the published value must not depend on which spelling a future edit picks.
        self.assertEqual(gb.minutes_seconds_of("2:19"), 139)
        self.assertEqual(gb.minutes_of("2:19"), 139 / 60.0)
        self.assertEqual(gb.minutes_of("2:34"), 154 / 60.0)

    def test_float_reductions_are_what_moved_between_interpreters(self):
        many = [gb.minutes_of("33:51"), gb.minutes_of("24:30"), gb.minutes_of("19:24"),
                gb.minutes_of("26:41"), gb.minutes_of("22:45"), gb.minutes_of("23:04"),
                gb.minutes_of("25:40"), gb.minutes_of("26:43"), gb.minutes_of("18:07"),
                gb.minutes_of("08:58"), gb.minutes_of("06:39"), gb.minutes_of("03:38")]
        self.assertEqual(sum(int(round(m * 60)) for m in many), 14400)
        self.assertEqual(math.fsum(many), 240.0)


class PublishedArtefactTests(unittest.TestCase):
    def _logs(self):
        with open(LOGS, encoding="utf-8") as fh:
            return json.load(fh)

    def test_every_published_aggregate_is_an_integer(self):
        d = self._logs()
        for club, blk in d["clubs"].items():
            self.assertIsInstance(blk["sum_min_seconds"], int, club)
            # sum_min is the ROUNDED float total this artefact has always published (f69a11c4's
            # math.fsum, kept); sum_min_seconds is the exact integer. The rounded value must be the
            # integer total rounded to the two decimals the artefact prints.
            self.assertEqual(blk["sum_min"], round(blk["sum_min_seconds"] / 60.0, 2), club)
            self.assertEqual(blk["sum_min_exactly_240"], blk["sum_min_seconds"] == 14400, club)
        for key, blk in d["top8_minutes_shares"].items():
            self.assertIsInstance(blk["total_min_seconds"], int, key)

    def test_every_share_is_a_rounded_division_of_two_integers(self):
        d = self._logs()
        for key, blk in d["top8_minutes_shares"].items():
            for row in blk["top8"]:
                self.assertEqual(row["share"],
                                 round(row["min_seconds"] / blk["total_min_seconds"], 4), key)

    def test_every_player_row_keeps_the_exact_seconds(self):
        d = self._logs()
        for row in d["rows"]:
            if row["status"] != "played":
                continue
            self.assertIsInstance(row["min_seconds"], int, row["player"])
            self.assertEqual(row["min"], row["min_seconds"] / 60.0, row["player"])

    def test_the_two_club_games_that_miss_240_are_published_as_such(self):
        # LAL 240:03 and PHX 240:01 by their anchor cells do not equal the 240:00 their own PDF
        # prints. The published tolerance flag says "within 21 s"; the exact flag says which club.
        # Both are published so the discrepancy is visible instead of hidden inside a tolerance.
        d = self._logs()
        exact = {c: blk["sum_min_exactly_240"] for c, blk in d["clubs"].items()}
        self.assertEqual(exact["Lakers"], False)
        self.assertEqual(exact["PHOENIX SUNS"], False)
        for club in ("Dallas Mavericks", "BOSTON CELTICS", "Houston Rockets",
                     "WASHINGTON WIZARDS", "Indiana Pacers", "PHILADELPHIA 76ERS"):
            self.assertEqual(exact[club], True, club)

    def test_the_gamebook_artefact_reproduces_on_this_interpreter(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gamebooks_2ecbccfd.py"),
                            "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         f"gamebooks_2ecbccfd.py --check is not byte-stable on "
                         f"{sys.version.split()[0]}:\n{r.stdout}\n{r.stderr}")

    def test_the_league_averages_reproduce_on_this_interpreter(self):
        import round2_2026_11_16 as R
        fresh = json.dumps(R.build_all()["model"], indent=1, ensure_ascii=False) + "\n"
        with open(MODEL_1300, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), fresh,
                             "model.json is not byte-identical to a fresh build on "
                             + sys.version.split()[0])


class NoFloatSumTests(unittest.TestCase):
    """Static guard: the producers must not reduce floats with the builtin sum() again."""

    def _src(self, name):
        with open(os.path.join(ROOT, "scripts", name), encoding="utf-8") as fh:
            return fh.read()

    def test_gamebooks_sums_are_over_integers_only(self):
        tree = ast.parse(self._src("gamebooks_2ecbccfd.py"))
        offenders = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "sum" and node.args):
                continue
            rendered = ast.unparse(node.args[0])
            # integer counts and integer box-score columns are exact and cannot move with the
            # interpreter; only a float reduction can. List what is allowed, not what is not.
            if ("_seconds" in rendered or "_pts" in rendered or "r.get('pts')" in rendered
                    or "r.get(\"pts\")" in rendered or "r[k]" in rendered
                    or rendered.startswith("(1 for ") or "len(d['clubs'])" in rendered):
                continue
            offenders.append((node.lineno, rendered))
        self.assertEqual(offenders, [], f"float-looking sum() in gamebooks: {offenders}")

    def test_league_averages_use_fsum(self):
        src = self._src("round2_2026_11_16.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "league_averages":
                body = ast.unparse(node)
                self.assertIn("fsum", body, "league_averages must use math.fsum")
                self.assertNotRegex(body, r"\bsum\(r\[")
                return
        self.fail("league_averages not found")


if __name__ == "__main__":
    unittest.main()
