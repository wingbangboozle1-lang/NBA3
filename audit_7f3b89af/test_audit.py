"""Self-tests for the audit tree of session arena/7f3b89af-nba3.

Run:  python3 -m unittest discover -s audit_7f3b89af -p 'test_*.py'

Nothing here asserts that the NBA published a particular value. These tests assert that this tree
is internally consistent, reproducible and honest: the captures regenerate identically, the checks
find what they say they find, the analysis is deterministic, and both page rules hold.
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")

sys.path.insert(0, HERE)


def load(name):
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


def run(script):
    proc = subprocess.run([sys.executable, os.path.join(HERE, script)],
                          cwd=ROOT, capture_output=True, text=True)
    return proc


class TestCaptures(unittest.TestCase):
    def test_captures_regenerate_identically(self):
        """capture.py writes data from the transcribed tuples; nothing is edited by hand."""
        before = {}
        for name in sorted(os.listdir(DATA)):
            if name.startswith(("injury_report_", "slate_", "team_ratings_")):
                with open(os.path.join(DATA, name)) as fh:
                    before[name] = fh.read()
        proc = run("capture.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name, text in before.items():
            with open(os.path.join(DATA, name)) as fh:
                self.assertEqual(fh.read(), text, "%s changed on regeneration" % name)

    def test_row_counts(self):
        for key, total, players, nys in (
            ("2026-11-14_04_15AM", 49, 26, 23),
            ("2026-11-14_04_45AM", 49, 26, 23),
            ("2026-11-14_01_15PM", 69, 50, 19),
            ("2026-11-14_01_30PM", 69, 50, 19),
        ):
            with self.subTest(key=key):
                d = load("injury_report_%s.json" % key)
                self.assertEqual(d["count"], total)
                self.assertEqual(d["player_rows"], players)
                self.assertEqual(d["not_submitted_rows"], nys)
                self.assertEqual(players + nys, total)

    def test_every_row_carries_its_source(self):
        for name in os.listdir(DATA):
            if not name.startswith("injury_report_"):
                continue
            d = load(name)
            for r in d["rows"]:
                self.assertTrue(r["source"].startswith("https://"), name)
                self.assertTrue(r["source_index"].startswith("https://"), name)

    def test_blank_cells_stay_blank(self):
        """The no-inference rule: a row marked 'continuation' must not carry a team or matchup."""
        d = load("injury_report_2026-11-14_01_30PM.json")
        for r in d["rows"]:
            if r["cells_printed"] == "continuation":
                for f in ("game_date", "game_time_et", "matchup", "team_name", "team"):
                    self.assertEqual(r[f], "", "%s filled on a continuation row" % f)

    def test_slate_window_is_complete(self):
        s = load("slate_2026-11-14_1117.json")
        self.assertEqual(s["count"], 27)
        self.assertEqual(len(s["rows"]), 27)
        dates = sorted({r["date"] for r in s["rows"]})
        self.assertEqual(dates, ["2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17"])
        ids = [r["game_id"] for r in s["rows"]]
        self.assertEqual(len(set(ids)), 27, "duplicate game id in the window")
        for r in s["rows"]:
            self.assertTrue(r["game_url"].startswith("https://www.nba.com/game/"))


class TestChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = run("checks.py")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        cls.report = load("verification_report.json")

    def test_no_failed_checks(self):
        self.assertEqual(self.report["fail"], 0)

    def test_check_ids_are_unique_and_present(self):
        ids = [c["id"] for c in self.report["checks"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("C1", ids)
        self.assertEqual(len(ids), 14)

    def test_canonical_matches_the_pdf_it_came_from(self):
        by = {c["id"]: c for c in self.report["checks"]}
        self.assertEqual(by["C4"]["observed"].split(",")[-1].strip(), "0 mismatches")
        self.assertEqual(by["C3"]["status"], "pass")

    def test_slate_matches_the_live_schedule(self):
        by = {c["id"]: c for c in self.report["checks"]}
        self.assertIn("0 differences", by["C7"]["observed"])

    def test_rating_drift_is_exactly_what_is_documented(self):
        teams = sorted({d["team"] for d in self.report["rating_drift"]})
        self.assertEqual(teams, ["CHA", "CLE"])
        for d in self.report["rating_drift"]:
            self.assertIn(d["field"], ("off_rtg", "def_rtg", "pace"))
        # net rating, games played, wins and losses must be unchanged for every team
        for d in self.report["rating_drift"]:
            self.assertNotIn(d["field"], ("net_rtg", "gp", "w", "l", "min"))

    def test_pace_impact_is_below_a_tenth_of_a_possession(self):
        self.assertTrue(self.report["pace_impact"])
        for r in self.report["pace_impact"]:
            self.assertLess(abs(r["delta"]), 0.1)

    def test_injury_drift_counts(self):
        d = self.report["injury_drift"]
        self.assertEqual(d["counts"]["added"], 24)
        self.assertEqual(d["counts"]["removed"], 0)
        self.assertEqual(d["counts"]["status_changes"], 4)
        affected = [m for m, v in d["tonight_by_game"].items() if v["new_rows"]]
        self.assertEqual(len(affected), 4)
        self.assertNotIn("BKN@MEM", affected)   # Memphis still had not filed at 01:30 PM

    def test_every_status_change_is_a_real_change(self):
        for c in self.report["injury_drift"]["status_changes"]:
            self.assertNotEqual(c["status_04_15AM"], c["status_01_30PM"])

    def test_flags_are_sourced(self):
        self.assertEqual(len(self.report["flags"]), 5)
        for f in self.report["flags"]:
            self.assertTrue(f["source"].startswith("https://"))
            self.assertIn(f["severity"], ("high", "medium", "low"))
            self.assertTrue(f["owner_action"])

    def test_checks_are_deterministic(self):
        a = json.dumps(self.report["checks"], sort_keys=True)
        proc = run("checks.py")
        self.assertEqual(proc.returncode, 0)
        b = json.dumps(load("verification_report.json")["checks"], sort_keys=True)
        self.assertEqual(a, b)


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = run("analysis.py")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        cls.ana = load("analysis.json")

    def test_sample(self):
        self.assertEqual(self.ana["games_used"], 140)
        self.assertEqual(self.ana["games_excluded_no_prior_game"], 0)

    def test_correlations_are_in_range(self):
        for t in self.ana["tests"]:
            if t["stat"] == "Pearson r":
                self.assertGreaterEqual(t["value"], -1.0)
                self.assertLessEqual(t["value"], 1.0)
                lo, hi = t["ci95"]
                self.assertLessEqual(lo, t["value"])
                self.assertGreaterEqual(hi, t["value"])

    def test_bh_adjustment_is_monotone_and_no_larger_than_one(self):
        ps = [t["p_perm"] for t in self.ana["tests"] if t["p_perm"] is not None]
        qs = [t["q_bh"] for t in self.ana["tests"] if t["p_perm"] is not None]
        for p, q in zip(ps, qs):
            self.assertGreaterEqual(q, p - 1e-12)
            self.assertLessEqual(q, 1.0)

    def test_no_test_claims_significance_after_correction(self):
        for t in self.ana["tests"]:
            self.assertFalse(t["significant_after_bh"],
                             "%s is reported as significant; the verdict text must be updated" % t["id"])

    def test_walk_forward_made_the_line_worse(self):
        t5 = [t for t in self.ana["tests"] if t["id"] == "T5"][0]
        self.assertLess(t5["extra"]["improvement_points"], 0)

    def test_power_calculation_is_consistent(self):
        p = self.ana["power"]
        self.assertGreater(p["games_needed_for_80pct_power_at_alpha_0.05"], p["games_available_now"])
        self.assertEqual(p["games_still_needed"],
                         p["games_needed_for_80pct_power_at_alpha_0.05"] - p["games_available_now"])

    def test_analysis_is_deterministic(self):
        a = json.dumps(self.ana, sort_keys=True)
        run("analysis.py")
        b = json.dumps(load("analysis.json"), sort_keys=True)
        self.assertEqual(a, b)


class TestPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build
        cls.written = build.main()

    def test_pages_exist(self):
        for name in self.written:
            self.assertTrue(os.path.exists(os.path.join(PAGES, name)))

    def test_page_rules(self):
        """Both rules: every tbody row carries an https evidence link; every internal link resolves.

        build.main() already raises on a violation, so reaching this point is the assertion."""
        import build
        self.assertEqual(build.validate(PAGES, self.written), [])

    def test_pages_link_back_to_the_site(self):
        with open(os.path.join(PAGES, "index.html")) as fh:
            text = fh.read()
        self.assertIn('../../index.html', text)
        self.assertIn('../../app/assets/app.css', text)


if __name__ == "__main__":
    unittest.main()
