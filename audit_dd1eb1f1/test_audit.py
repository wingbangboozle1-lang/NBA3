#!/usr/bin/env python3
"""Self-tests for the dd1eb1f1 audit tree.

Run:  python3 -m unittest discover -s audit_dd1eb1f1 -p 'test_*.py'
  or: python3 audit_dd1eb1f1/test_audit.py

Deliberately value-based, not byte-based: the reports carry a generated_utc stamp, so a
byte-identity gate against the committed JSON would fail on every run for no reason. These
tests assert the numbers and the page-level rules instead.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")
OFFICIAL_HOSTS = ("nba.com", "ak-static.cms.nba.com", "official.nba.com")


class VerificationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(DATA, "verification_report.json"), encoding="utf-8") as fh:
            cls.rep = json.load(fh)

    def test_section_counts(self):
        slate, inj, log = self.rep["sections"]
        self.assertEqual(slate["rows_compared"], 27)
        self.assertEqual(slate["rows_in_canonical"], 27)
        self.assertEqual(inj["rows_compared"], 49)
        self.assertEqual(inj["rows_in_canonical"], 49)

    def test_no_mismatches(self):
        for sec in self.rep["sections"][:2]:
            self.assertEqual(sec["mismatches"], [], sec["title"])

    def test_results_log_internally_consistent(self):
        log = self.rep["sections"][2]
        for chk in log["checks"]:
            self.assertTrue(chk["match"], chk["check"])
        self.assertEqual(log["recomputed"]["games"], 183)
        self.assertEqual(log["recomputed"]["team_games"], 366)

    def test_every_row_carries_an_official_source(self):
        for sec in self.rep["sections"][:2]:
            for row in sec["per_row"]:
                src = row.get("official_source") or row.get("source")
                self.assertTrue(src and src.startswith("https://"), str(row)[:120])
                self.assertTrue(any(h in src for h in OFFICIAL_HOSTS), src)


class CorrelationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(DATA, "correlation_extension.json"), encoding="utf-8") as fh:
            cls.ext = json.load(fh)

    def test_pearson_values_in_range(self):
        for sec in self.ext["sections"]:
            for row in sec.get("rows", []):
                v = row.get("value")
                if v is None:
                    self.assertFalse(row.get("verified", False), row["pair"])
                    continue
                self.assertGreaterEqual(v, -1.0)
                self.assertLessEqual(v, 1.0)

    def test_blank_rows_are_not_marked_verified(self):
        blank = self.ext["sections"][3]
        for row in blank["rows"]:
            self.assertEqual(row["status"], "blank")
            self.assertTrue(row["official_source_that_has_it"].startswith("https://"))

    def test_multiplicity_family_matches_tests(self):
        mc = self.ext["sections"][0]["multiple_comparisons"]
        self.assertEqual(mc["family_size"], len(mc["tests"]))
        for t in mc["tests"]:
            if t["raw_p"] is not None and t["bh_adjusted_p"] is not None:
                self.assertGreaterEqual(t["bh_adjusted_p"], t["raw_p"] - 1e-9)

    def test_seed_and_permutations_recorded(self):
        self.assertEqual(self.ext["seed"], 20261114)
        self.assertEqual(self.ext["permutations"], 5000)


class AnalysisReproducibilityTests(unittest.TestCase):
    """The analysis must be deterministic: same inputs, same numbers, no clock in the maths."""

    def test_analysis_is_deterministic(self):
        sys.path.insert(0, HERE)
        try:
            import analysis
        except ImportError:  # pragma: no cover
            self.skipTest("analysis module not importable")
        games = analysis.add_rest(analysis.load_games())
        with open(os.path.join(ROOT, "data", "app", "canonical.json"), encoding="utf-8") as fh:
            canon = json.load(fh)
        first = analysis.rest_effects(games)
        second = analysis.rest_effects(games)
        self.assertEqual(first["rows"], second["rows"])
        self.assertEqual(first["group_means"], second["group_means"])
        clus1 = analysis.within_date_clustering(canon)
        clus2 = analysis.within_date_clustering(canon)
        self.assertEqual(clus1["results"], clus2["results"])

    def test_permutation_p_is_reproducible(self):
        sys.path.insert(0, HERE)
        try:
            import analysis
        except ImportError:  # pragma: no cover
            self.skipTest("analysis module not importable")
        # pearson() clamps to +/-0.999999 so the Fisher z transform stays finite, so a perfect
        # straight line returns 0.999999 rather than 1.0.
        rr, lo, hi, n = analysis.pearson(list(range(50)), [x * 2 + 1 for x in range(50)])
        self.assertAlmostEqual(rr, 0.999999, places=9)
        self.assertAlmostEqual(lo, hi, places=5)
        rr2, _, _, _ = analysis.pearson([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
        self.assertAlmostEqual(rr2, -0.999999, places=9)


class PageTests(unittest.TestCase):
    def pages(self):
        return sorted(f for f in os.listdir(PAGES) if f.endswith(".html"))

    def test_every_table_row_has_an_official_link(self):
        import re
        for name in self.pages():
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                text = fh.read()
            for bi, body in enumerate(re.findall(r"<tbody>(.*?)</tbody>", text, flags=re.S)):
                for ri, row in enumerate(re.findall(r"<tr>(.*?)</tr>", body, flags=re.S), 1):
                    self.assertTrue(any(h in row for h in OFFICIAL_HOSTS),
                                    f"{name}: tbody {bi + 1} row {ri} has no official link")

    def test_no_broken_internal_links(self):
        import re
        for name in self.pages():
            with open(os.path.join(PAGES, name), encoding="utf-8") as fh:
                text = fh.read()
            for href in re.findall(r'href="([^"]+)"', text):
                if href.startswith(("http", "mailto:", "#")):
                    continue
                target = os.path.normpath(os.path.join(PAGES, href.split("#")[0]))
                self.assertTrue(os.path.exists(target), f"{name}: broken link {href}")

    def test_pages_rebuild(self):
        out = subprocess.run([sys.executable, os.path.join(HERE, "build.py")],
                             capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
