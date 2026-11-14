"""Unit tests for pipeline/gates.py.

All inputs here are synthetic and exist only to check the math.
They are not NBA results and must not be cited as performance.
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gates  # noqa: E402

UTC = timezone.utc
THRESHOLDS = {
    "min_graded": 1000, "alpha": 0.05, "score_diff_ci_low_min": 0.0,
    "return_ci_low_min": 0.0, "min_positive_blocks": 2, "min_prospective": 200,
}


class ExactBinomialTests(unittest.TestCase):
    def test_eight_of_ten_fair_coin(self):
        # P(X >= 8) for Binomial(10, 0.5) = (45 + 10 + 1) / 1024 = 56 / 1024
        self.assertAlmostEqual(gates.exact_binomial_p_value_greater(8, 10, 0.5), 56 / 1024, places=12)

    def test_zero_successes_is_certain(self):
        self.assertAlmostEqual(gates.exact_binomial_p_value_greater(0, 25, 0.5), 1.0, places=12)

    def test_all_successes(self):
        self.assertAlmostEqual(gates.exact_binomial_p_value_greater(10, 10, 0.5), 1 / 1024, places=12)

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            gates.exact_binomial_p_value_greater(11, 10, 0.5)
        with self.assertRaises(ValueError):
            gates.exact_binomial_p_value_greater(1, 10, 1.0)


class HolmTests(unittest.TestCase):
    def test_step_down_example(self):
        # sorted: 0.005 <= 0.05/4 yes; 0.01 <= 0.05/3 yes; 0.03 <= 0.05/2 no -> stop
        self.assertEqual(gates.holm_reject([0.01, 0.04, 0.03, 0.005], 0.05),
                         [True, False, False, True])

    def test_nothing_rejected_when_all_large(self):
        self.assertEqual(gates.holm_reject([0.5, 0.6], 0.05), [False, False])


class PermutationTests(unittest.TestCase):
    def test_identical_samples_not_significant(self):
        a = [0.0, 1.0] * 15
        b = [0.0, 1.0] * 15
        self.assertGreater(gates.permutation_p_value_mean_difference(a, b, 2000, seed=1), 0.5)

    def test_separated_samples_significant(self):
        a = [0.0] * 30
        b = [1.0] * 30
        self.assertLess(gates.permutation_p_value_mean_difference(a, b, 2000, seed=1), 0.01)


class BootstrapTests(unittest.TestCase):
    def test_constant_clusters_give_point_interval(self):
        clusters = {"2026-11-13": [1.0, 1.0], "2026-11-14": [1.0]}
        lo, hi = gates.cluster_bootstrap_mean_ci(clusters, 500, 0.05, seed=3)
        self.assertEqual((lo, hi), (1.0, 1.0))

    def test_interval_orders_and_brackets_mean(self):
        clusters = {"d1": [-1.0, 1.0], "d2": [-1.0, -1.0, 1.0], "d3": [1.0]}
        lo, hi = gates.cluster_bootstrap_mean_ci(clusters, 1000, 0.05, seed=7)
        self.assertLessEqual(lo, hi)
        self.assertGreaterEqual(lo, -1.0)
        self.assertLessEqual(hi, 1.0)


class PriceTests(unittest.TestCase):
    def test_break_even_and_profit(self):
        self.assertAlmostEqual(gates.break_even_probability(2.0), 0.5)
        self.assertAlmostEqual(gates.profit_per_unit(1.91, True), 0.91)
        self.assertEqual(gates.profit_per_unit(1.91, False), -1.0)

    def test_invalid_price_rejected(self):
        with self.assertRaises(ValueError):
            gates.break_even_probability(1.0)


class LeakageTests(unittest.TestCase):
    def test_flags_feature_at_or_after_tipoff(self):
        tip = datetime(2026, 11, 13, 19, 0, tzinfo=UTC)
        feats = {
            "rest_days": tip - timedelta(hours=5),
            "closing_total": tip,
            "post_game_points": tip + timedelta(hours=2),
        }
        self.assertEqual(sorted(gates.leakage_violations(feats, tip)),
                         ["closing_total", "post_game_points"])

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            gates.leakage_violations({}, datetime(2026, 11, 13, 19, 0))


class EvaluateGatesTests(unittest.TestCase):
    def test_no_evidence_is_blocked_not_pass(self):
        result = gates.evaluate_gates({}, THRESHOLDS)
        self.assertEqual(result["overall"], "BLOCKED")
        self.assertTrue(all(v == "BLOCKED" for v in result["gates"].values()))

    def test_all_metrics_passing_gives_pass(self):
        metrics = {
            "unsourced_rows": 0, "leakage_count": 0, "score_diff_ci_low": 0.01,
            "n_graded": 1500, "p_value_holm": 0.01, "net_return_ci_low": 0.02,
            "positive_blocks": 3, "joint_within_interval": True,
            "net_return_recorded_prices_ci_low": 0.01, "prospective_n": 250,
            "control_passed_any_gate": False,
        }
        self.assertEqual(gates.evaluate_gates(metrics, THRESHOLDS)["overall"], "PASS")

    def test_control_passing_any_gate_fails_overall(self):
        metrics = {"unsourced_rows": 0, "leakage_count": 0, "control_passed_any_gate": True}
        self.assertEqual(gates.evaluate_gates(metrics, THRESHOLDS)["overall"], "FAIL")

    def test_missing_threshold_raises(self):
        partial = {k: v for k, v in THRESHOLDS.items() if k != "alpha"}
        with self.assertRaises(ValueError):
            gates.evaluate_gates({}, partial)


if __name__ == "__main__":
    unittest.main()
