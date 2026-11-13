import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import validate_gates as vg  # noqa: E402


class BinomialTests(unittest.TestCase):
    def test_binom_sf_matches_bruteforce(self):
        for n, k, p in [(10, 0, 0.5), (10, 7, 0.5), (20, 15, 0.3), (50, 30, 0.6)]:
            brute = sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))
            self.assertAlmostEqual(vg.binom_sf(k, n, p), brute, places=12)

    def test_known_value_60_of_100(self):
        # P(X >= 60) for Binomial(100, 0.5) is about 0.0284
        self.assertAlmostEqual(vg.exact_binomial_pvalue(60, 100), 0.02844, places=4)

    def test_pvalue_edges(self):
        self.assertEqual(vg.exact_binomial_pvalue(0, 10), 1.0)
        self.assertAlmostEqual(vg.exact_binomial_pvalue(10, 10), 0.5 ** 10, places=12)
        with self.assertRaises(ValueError):
            vg.exact_binomial_pvalue(11, 10)


class IntervalTests(unittest.TestCase):
    def test_wilson_contains_phat_and_is_bounded(self):
        lo, hi = vg.wilson_interval(60, 100)
        self.assertTrue(lo < 0.6 < hi)
        self.assertTrue(0 <= lo and hi <= 1)
        # Wilson 95% interval for 60/100 (hand-computed: 0.5020, 0.6906)
        self.assertAlmostEqual(lo, 0.5020, places=3)
        self.assertAlmostEqual(hi, 0.6906, places=3)

    def test_break_even(self):
        self.assertAlmostEqual(vg.break_even_rate(1.91), 1 / 1.91)
        with self.assertRaises(ValueError):
            vg.break_even_rate(1.0)


class MultipleTestingTests(unittest.TestCase):
    def test_bh_matches_hand_example(self):
        # Classic example: p = [0.01, 0.04, 0.03, 0.005] -> q = [0.02, 0.04, 0.04, 0.02]
        q = vg.benjamini_hochberg([0.01, 0.04, 0.03, 0.005])
        for got, exp in zip(q, [0.02, 0.04, 0.04, 0.02]):
            self.assertAlmostEqual(got, exp, places=12)

    def test_bh_empty_and_capped(self):
        self.assertEqual(vg.benjamini_hochberg([]), [])
        self.assertTrue(all(x <= 1 for x in vg.benjamini_hochberg([0.9, 0.95])))


class CorrelationTests(unittest.TestCase):
    def test_pearson_perfect_and_zero(self):
        self.assertAlmostEqual(vg.pearson_r([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(vg.pearson_r([1, 2, 3], [6, 4, 2]), -1.0)
        self.assertAlmostEqual(vg.pearson_r([1, 2, 3, 4], [1, -1, -1, 1]), 0.0)

    def test_pearson_undefined_for_constant(self):
        with self.assertRaises(ValueError):
            vg.pearson_r([1, 1, 1], [1, 2, 3])

    def test_parlay_dependence(self):
        self.assertAlmostEqual(vg.parlay_dependence_ratio(0.30, 0.5, 0.6), 1.0)
        self.assertAlmostEqual(vg.parlay_dependence_ratio(0.36, 0.5, 0.6), 1.2)


class GateTests(unittest.TestCase):
    def test_blocked_gates_are_none_not_pass(self):
        rec = vg.StrategyRecord("s", wins=[60, 60, 60, 60], bets=[100, 100, 100, 100])
        res = vg.evaluate_strategy(rec)
        self.assertIsNone(res["gates"]["G5_market_benchmark"][0])
        self.assertFalse(vg.passes_all_evaluable(res) and res["gates"]["G5_market_benchmark"][0] is True)

    def test_min_sample_gate(self):
        rec = vg.StrategyRecord("small", wins=[30], bets=[50])
        res = vg.evaluate_strategy(rec)
        self.assertFalse(res["gates"]["G1_min_sample"][0])

    def test_portfolio_applies_bh(self):
        recs = [vg.StrategyRecord("a", [70], [100]), vg.StrategyRecord("b", [50], [100])]
        out = vg.evaluate_portfolio(recs)
        self.assertEqual(len(out), 2)
        self.assertIsNotNone(recs[0].adjusted_p)
        self.assertGreaterEqual(recs[0].adjusted_p, vg.exact_binomial_pvalue(70, 100))


if __name__ == "__main__":
    unittest.main()
