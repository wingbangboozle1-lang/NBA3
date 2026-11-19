#!/usr/bin/env python3
"""Tests for the session 9a13efcf verification audit.

The audit's own maths is checked here against closed forms and known values, so
a bug in the auditor cannot silently certify a bug in the repository.
"""
import json
import math
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_9a13efcf as A  # noqa: E402


class TestMaths(unittest.TestCase):
    def test_haversine_known_distance(self):
        # NYC (40.7128, -74.0060) -> Boston (42.3601, -71.0589) ~ 305-310 km
        km = A.haversine_km(40.7128, -74.0060, 42.3601, -71.0589)
        self.assertAlmostEqual(km, 306, delta=6)

    def test_haversine_zero(self):
        self.assertAlmostEqual(A.haversine_km(33.75, -84.39, 33.75, -84.39), 0.0, places=9)

    def test_bvnl_independent(self):
        # rho = 0 -> joint = product of marginals
        h, k = 0.3, -0.2
        j = A.bvnl_cdf(h, k, 0.0)
        self.assertAlmostEqual(j, A.norm_cdf(h) * A.norm_cdf(k), places=8)

    def test_bvnl_zero_zero_closed_form(self):
        # Phi2(0, 0; rho) = 1/4 + arcsin(rho) / (2 pi)   (Sheppard's formula)
        for rho in (-0.4, -0.1, 0.2, 0.75):
            j = A.bvnl_cdf(0.0, 0.0, rho)
            expect = 0.25 + math.asin(rho) / (2 * math.pi)
            self.assertAlmostEqual(j, expect, places=8, msg=f"rho={rho}")

    def test_bvnl_symmetry(self):
        self.assertAlmostEqual(A.bvnl_cdf(0.4, -0.7, 0.3),
                               A.bvnl_cdf(-0.7, 0.4, 0.3), places=8)

    def test_fisher_ci_contains_r(self):
        lo, hi = A.fisher_ci(0.122578, 188)
        self.assertLess(lo, 0.122578)
        self.assertGreater(hi, 0.122578)
        self.assertAlmostEqual(lo, -0.020899, places=5)
        self.assertAlmostEqual(hi, 0.261108, places=5)

    def test_ridge_solver_matches_direct_inverse_on_small_system(self):
        X = [[1.0, -1.0, 0.0], [0.0, 1.0, -1.0], [1.0, 0.0, -1.0]]
        y = [4.0, 6.0, 10.0]
        lam = 2.0
        b = A.ridge_gauss_seidel(X, y, lam, iters=50000, tol=1e-14)
        # direct solve of (X'X + lam I) b = X'y
        p = 3
        M = [[sum(X[r][i] * X[r][j] for r in range(3)) + (lam if i == j else 0.0)
              for j in range(p)] for i in range(p)]
        rhs = [sum(X[r][i] * y[r] for r in range(3)) for i in range(p)]
        # gaussian elimination
        import copy
        Mc = copy.deepcopy(M)
        rc = list(rhs)
        for col in range(p):
            piv = max(range(col, p), key=lambda r: abs(Mc[r][col]))
            Mc[col], Mc[piv] = Mc[piv], Mc[col]
            rc[col], rc[piv] = rc[piv], rc[col]
            for r in range(col + 1, p):
                f = Mc[r][col] / Mc[col][col]
                for c in range(col, p):
                    Mc[r][c] -= f * Mc[col][c]
                rc[r] -= f * rc[col]
        x = [0.0] * p
        for r in range(p - 1, -1, -1):
            x[r] = (rc[r] - sum(Mc[r][c] * x[c] for c in range(r + 1, p))) / Mc[r][r]
        for a, b_ in zip(b, x):
            self.assertAlmostEqual(a, b_, places=6)

    def test_canon_sha_matches_known(self):
        self.assertEqual(
            A.canon_sha({"b": 1, "a": 2}),
            __import__("hashlib").sha256(b'{"a":2,"b":1}').hexdigest())


class TestAuditArtefact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = A.build_audit()
        cls.pages = A.render(cls.audit)
        with open(os.path.join(ROOT, "data", "9a13efcf", "audit.json"), encoding="utf-8") as fh:
            cls.committed = json.load(fh)

    def test_all_check_ids_present(self):
        ids = {c["id"] for c in self.audit["checks"]}
        for want in ("V-HCA", "V-A", "V-B", "V-LUCK", "V-CORR", "V-PARLAY", "V-CONTEXT",
                     "V-ARENA", "V-PREREG", "V-LEDGER-2", "V-LEDGER-1", "V-MIN",
                     "V-RESULTS", "V-PLAYERLOGS", "V-MKTPRIOR", "V-GATES",
                     "V-SURF-SEP", "V-SURF-BANNER", "V-SURF-ROT", "V-SURF-SRC"):
            self.assertIn(want, ids)

    def test_reproduces_committed_artefact(self):
        fresh = json.dumps(self.audit, indent=1, default=str) + "\n"
        ondisk = open(os.path.join(ROOT, "data", "9a13efcf", "audit.json"),
                      encoding="utf-8").read()
        self.assertEqual(fresh, ondisk, "audit.json drifted; rebuild and commit")

    def test_pages_reproduce(self):
        for name, html in self.pages.items():
            path = os.path.join(ROOT, "9a13efcf", name)
            self.assertTrue(os.path.exists(path), name)
            self.assertEqual(open(path, encoding="utf-8").read(), html, name)

    def test_every_requirement_row_is_complete(self):
        for row in self.audit["requirements"]:
            self.assertEqual(len(row), 5)
            self.assertTrue(row[0].startswith("R"))
            self.assertTrue(row[1] and row[2])

    def test_hca_reproduces(self):
        c = next(x for x in self.audit["checks"] if x["id"] == "V-HCA")
        self.assertTrue(c["agree"], c)
        self.assertEqual(c["mine"]["home_wins"], 99)
        self.assertEqual(c["mine"]["n_games"], 188)

    def test_arena_rows_all_verified(self):
        c = next(x for x in self.audit["checks"] if x["id"] == "V-ARENA")
        self.assertTrue(c["agree"], "an arena coordinate no longer matches its source")
        self.assertEqual(len(c["rows"]), 30)
        self.assertTrue(all(r["match"] for r in c["rows"]))

    def test_ledgers_reproduce(self):
        for cid in ("V-LEDGER-2", "V-LEDGER-1"):
            c = next(x for x in self.audit["checks"] if x["id"] == cid)
            self.assertTrue(c["agree"], f"{cid}: {c.get('problems')}")

    def test_prereg_hashes_reproduce(self):
        c = next(x for x in self.audit["checks"] if x["id"] == "V-PREREG")
        self.assertTrue(c["agree"])
        self.assertEqual(len(c["rows"]), 3)
        self.assertTrue(all(r["hash_reproduces"] for r in c["rows"]))
        self.assertTrue(all(all(r["required_fields"].values()) for r in c["rows"]))

    def test_surface_checks(self):
        for cid in ("V-SURF-SEP", "V-SURF-BANNER", "V-SURF-ROT", "V-SURF-SRC"):
            c = next(x for x in self.audit["checks"] if x["id"] == cid)
            self.assertTrue(c["agree"], f"{cid}: {c.get('rows')}")

    def test_no_broken_internal_links(self):
        import re
        for name, html in self.pages.items():
            for href in re.findall(r"href='([^']+)'", html):
                if href.startswith("http") or href.startswith("#"):
                    continue
                self.assertTrue(os.path.exists(os.path.join(ROOT, "9a13efcf", href)),
                                f"{name} -> {href}")

    def test_playerlog_gap_is_reported_not_hidden(self):
        c = next(x for x in self.audit["checks"] if x["id"] == "V-PLAYERLOGS")
        self.assertFalse(c["agree"])
        self.assertIn("PARTIAL", c["status"])
        self.assertGreater(c["injury_players"], c["players_with_logs"])

    def test_flag_register_nonempty(self):
        self.assertTrue(self.audit["flags"])
        ids = {f["id"] for f in self.audit["flags"]}
        self.assertIn("9A-F-01", ids)


if __name__ == "__main__":
    unittest.main()
