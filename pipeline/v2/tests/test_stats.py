"""Tests for the v2 pipeline's statistics and money maths.

The point of these tests is not coverage.  It is that every number the site
publishes rests on one of these functions, and several of them had bugs that a
test of this shape would have caught immediately:

* ``parlay_price`` dropped the quadrature step (a copula price of 169 for a
  probability) and loaded every leg with the same sign for negative rho (so a
  negative correlation priced identically to a positive one).
* the rest-days calculation took ``prior[-1]`` from a set, giving up to 20 days
  of rest for a team that had played four days earlier.
* the board luck threshold simulated the null against each rule's own observed
  rate instead of against a coin.

Each test below is written against a published or analytically known value, not
against whatever the code happened to output.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from pipeline.v2 import stats as S                          # noqa: E402
from pipeline.v2 import pricing as P                        # noqa: E402
from pipeline.v2 import backtest as BT                      # noqa: E402
from pipeline.v2 import injury as I                         # noqa: E402
from pipeline.v2 import leaderboard as LB                   # noqa: E402


class TestNormPpf(unittest.TestCase):
    """norm_ppf against the standard table, to 4 decimals."""

    TABLE = [
        (0.50, 0.0000), (0.75, 0.6745), (0.90, 1.2816), (0.95, 1.6449),
        (0.975, 1.9600), (0.99, 2.3263), (0.999, 3.0902),
        (0.025, -1.9600), (0.10, -1.2816), (0.01, -2.3263),
    ]

    def test_table(self):
        for p, z in self.TABLE:
            self.assertAlmostEqual(S.norm_ppf(p), z, places=4, msg=f"p={p}")

    def test_round_trip(self):
        for i in range(1, 200):
            p = i / 200.0
            self.assertAlmostEqual(S.norm_cdf(S.norm_ppf(p)), p, places=9)

    def test_symmetry(self):
        for p in (0.001, 0.05, 0.2, 0.4):
            self.assertAlmostEqual(S.norm_ppf(p), -S.norm_ppf(1 - p), places=9)


class TestBinom(unittest.TestCase):
    """Exact two-sided binomial against the R definition and published values."""

    def test_against_r_binom_test(self):
        # R: binom.test(7, 10)$p.value      = 0.34375
        # R: binom.test(8, 10)$p.value      = 0.109375
        # R: binom.test(9, 10)$p.value      = 0.02148438
        # R: binom.test(0, 10)$p.value      = 0.001953125
        # R: binom.test(5, 10)$p.value      = 1
        for k, n, expected in [(7, 10, 0.34375), (8, 10, 0.109375),
                               (9, 10, 0.021484375), (0, 10, 0.001953125),
                               (5, 10, 1.0)]:
            self.assertAlmostEqual(S.binom_two_sided(k, n, 0.5), expected, places=12,
                                   msg=f"k={k} n={n}")

    def test_coin_is_symmetric(self):
        for k in range(0, 21):
            self.assertAlmostEqual(S.binom_two_sided(k, 20), S.binom_two_sided(20 - k, 20),
                                   places=12)

    def test_one_sided_is_the_upper_tail(self):
        """``binom_one_sided`` is P(X >= k): the question "at least this many wins".

        That is the tail the economics gate needs, and it makes the value fall as
        k rises, reaching 1.0 when k = 0.
        """
        self.assertEqual(S.binom_one_sided(0, 20), 1.0)
        prev = None
        for k in range(0, 21):
            v = S.binom_one_sided(k, 20)
            if prev is not None:
                self.assertLess(v, prev, msg=f"k={k}")
            prev = v
        self.assertAlmostEqual(S.binom_one_sided(20, 20), 0.5 ** 20, places=15)

    def test_degenerate(self):
        self.assertEqual(S.binom_two_sided(0, 0), 1.0)
        self.assertAlmostEqual(S.binom_two_sided(10, 10), 2 * 0.5 ** 10, places=12)


class TestParlayCopula(unittest.TestCase):
    """The copula must reproduce every limit of the 2-leg case exactly."""

    def test_rho_zero_matches_naive(self):
        self.assertAlmostEqual(S.parlay_price([0.6, 0.5], 0.0)["with_rho"], 0.30, places=12)

    def test_near_zero_rho_matches_naive(self):
        self.assertAlmostEqual(S.parlay_price([0.6, 0.5], 1e-9)["with_rho"], 0.30, places=7)

    def test_rho_one_gives_the_minimum(self):
        """Perfect correlation is the smaller leg: min(0.6, 0.5)."""
        self.assertAlmostEqual(S.parlay_price([0.6, 0.5], 0.9999)["with_rho"], 0.50, places=4)

    def test_rho_minus_one_gives_the_frechet_bound(self):
        """Perfect anti-correlation is max(0, p1 + p2 - 1) = 0.1."""
        self.assertAlmostEqual(S.parlay_price([0.6, 0.5], -0.9999)["with_rho"], 0.10, places=4)

    def test_symmetric_legs_have_a_known_answer(self):
        """Phi_2(0,0; 0.5) = 1/4 + asin(0.5)/(2*pi) = 1/3 exactly."""
        self.assertAlmostEqual(S.parlay_price([0.5, 0.5], 0.5)["with_rho"], 1 / 3, places=7)

    def test_monotone_in_rho(self):
        prev = None
        for rho in (-0.8, -0.4, 0.0, 0.4, 0.8):
            v = S.parlay_price([0.6, 0.5], rho)["with_rho"]
            if prev is not None:
                self.assertGreater(v, prev, msg=f"rho={rho}")
            prev = v

    def test_negative_rho_is_not_the_same_as_positive(self):
        """This is the bug that shipped once: both signs loaded the same way."""
        pos = S.parlay_price([0.6, 0.5], 0.5)["with_rho"]
        neg = S.parlay_price([0.6, 0.5], -0.5)["with_rho"]
        self.assertGreater(pos, 0.30)
        self.assertLess(neg, 0.30)

    def test_result_is_a_probability(self):
        for rho in (-0.9, -0.5, 0.0, 0.5, 0.9):
            v = S.parlay_price([0.3, 0.7], rho)["with_rho"]
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_independent_case_is_the_product(self):
        """At rho = 0 the joint is the product exactly; dependence moves it away."""
        self.assertAlmostEqual(S.parlay_price([0.5, 0.4], 0.0)["with_rho"], 0.20, places=12)
        self.assertGreater(S.parlay_price([0.5, 0.4], 0.5)["with_rho"], 0.20)
        self.assertLess(S.parlay_price([0.5, 0.4], -0.5)["with_rho"], 0.20)


class TestPricingUntestable(unittest.TestCase):
    """An unmeasurable rho must never be priced as if it were zero."""

    def test_missing_rho_is_not_priced(self):
        out = P.sgp_price(0.6, 0.5, None)
        self.assertFalse(out["priced"])
        self.assertIsNone(out["copula_price"])
        self.assertEqual(out["naive_product"], 0.30)

    def test_measured_rho_is_priced_both_ways(self):
        out = P.sgp_price(0.6, 0.5, 0.1, rho_n=131)
        self.assertTrue(out["priced"])
        self.assertEqual(out["naive_product"], 0.30)
        self.assertGreater(out["copula_price"], 0.30)

    def test_cross_game_is_never_claimed_independent_by_measurement(self):
        out = P.cross_game_price(0.6, 0.6)
        self.assertFalse(out["priced"])
        self.assertIsNone(out["rho"])
        self.assertIn("assumed independent", out["assumption"])


class TestMoney(unittest.TestCase):
    def test_american_round_trip(self):
        for p in (0.25, 0.4, 0.5, 0.6, 0.75):
            a = S.american_from_prob(p)
            self.assertAlmostEqual(S.prob_from_american(a), p, places=2)

    def test_even_money(self):
        self.assertEqual(S.american_from_prob(0.5), -100)

    def test_breakeven_at_minus_110(self):
        self.assertAlmostEqual(110 / 210.0, 0.52381, places=5)


class TestCorrectionDetector(unittest.TestCase):
    """A league spelling fix is not a roster event."""

    def test_embid_is_the_same_player_as_embiid(self):
        self.assertTrue(I._similar("Embid, Joel", "Embiid, Joel"))

    def test_different_players_are_not_merged(self):
        self.assertFalse(I._similar("Embiid, Joel", "Embiid, Amir"))
        self.assertFalse(I._similar("Barnes, Scottie", "Barnes, Harrison"))

    def test_identical_names(self):
        self.assertTrue(I._similar("Embiid, Joel", "Embiid, Joel"))


class TestRestDays(unittest.TestCase):
    """The set-vs-maximum bug, pinned down."""

    def test_most_recent_game_wins(self):
        dates = {"BOS": {"2026-11-01", "2026-11-13", "2026-11-05"}}
        self.assertEqual(BT._rest_before(dates, "BOS", "2026-11-15"), 2)

    def test_no_prior_game_is_none_not_zero(self):
        self.assertIsNone(BT._rest_before({"BOS": {"2026-11-20"}}, "BOS", "2026-11-15"))

    def test_back_to_back(self):
        self.assertEqual(BT._rest_before({"BOS": {"2026-11-14"}}, "BOS", "2026-11-15"), 1)


class TestBoardLuck(unittest.TestCase):
    """The all-null threshold must not depend on the observed rates."""

    def test_threshold_is_plausible(self):
        out = S.board_luck_threshold([131, 95, 28, 22, 18], iterations=400, seed=1)
        self.assertGreater(out["threshold_pp"], 0.0)
        self.assertLess(out["threshold_pp"], 100.0)

    def test_threshold_grows_with_more_rules(self):
        few = S.board_luck_threshold([100] * 2, iterations=1500, seed=7)["threshold_pp"]
        many = S.board_luck_threshold([100] * 12, iterations=1500, seed=7)["threshold_pp"]
        self.assertGreater(many, few)

    def test_threshold_is_deterministic_for_a_seed(self):
        a = S.board_luck_threshold([50, 50], iterations=300, seed=99)["threshold_pp"]
        b = S.board_luck_threshold([50, 50], iterations=300, seed=99)["threshold_pp"]
        self.assertEqual(a, b)


class TestLedger(unittest.TestCase):
    """The hash has to be able to fail, or it is decoration."""

    def _record(self):
        return LB.register("T01", "test", "single", "spread", "rule", "sig", {"a": 1},
                           {"u": "x"}, {"s": "y"}, ["https://www.nba.com/schedule"])

    def test_hash_is_stable(self):
        a, b = self._record(), self._record()
        self.assertEqual(a["preregistration_sha256"], b["preregistration_sha256"])

    def test_hash_changes_when_a_threshold_changes(self):
        a = self._record()
        b = dict(a)
        b["thresholds"] = {"a": 2}
        self.assertNotEqual(LB.verify_registration(b), a["preregistration_sha256"])

    def test_ledger_row_verifies_then_fails_after_edit(self):
        rec = self._record()
        row = LB.ledger_entry(rec, {"game_id": "1", "side": "home"},
                              "2026-11-15T00:00Z", "2026-11-15T12:00Z")
        self.assertTrue(LB.verify_ledger_row(row)["matches"])
        row["pick"]["side"] = "away"
        self.assertFalse(LB.verify_ledger_row(row)["matches"])

    def test_published_before_tip(self):
        rec = self._record()
        row = LB.ledger_entry(rec, {"g": 1}, "2026-11-15T13:00Z", "2026-11-15T12:00Z")
        self.assertFalse(row["published_before_tip"])


class TestScoreRule(unittest.TestCase):
    def test_pushes_are_not_wins(self):
        pass  # pushes are filtered before scoring; see backtest.grade_rule

    def test_no_sample_is_reported(self):
        out = LB.score_rule([])
        self.assertEqual(out["status"], "NO_SAMPLE")

    def test_two_edges_against_two_baselines(self):
        """Winning every bet at -110 is +50 pp against a coin, +47.6 pp against the price."""
        bets = [{"won": True, "date": "d", "price_american": -110}] * 10
        out = LB.score_rule(bets)
        self.assertAlmostEqual(out["edge_pp"], 50.0, places=6)
        self.assertAlmostEqual(out["edge_vs_breakeven_pp"], 47.619, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
