"""Validation-gate helpers (standard library only).

Design rules:
- No threshold has a default value. Callers must pass thresholds that the
  owner has approved, so nothing silently uses a number from this file.
- Missing evidence yields BLOCKED, never PASS.
- Functions here are tested on synthetic inputs only. They have not been run
  on NBA data, because no authorised historical data is reachable (see Q-DATA-01).
"""

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Sequence

GATE_IDS = ("G01", "G02", "G03", "G04", "G05", "G06", "G07", "G08", "G09", "G10", "G11")


def exact_binomial_p_value_greater(successes: int, n: int, p0: float) -> float:
    """One-sided exact p-value P(X >= successes) for X ~ Binomial(n, p0)."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0.0 < p0 < 1.0:
        raise ValueError("p0 must be strictly between 0 and 1")
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    log_p = math.log(p0)
    log_q = math.log1p(-p0)
    total = 0.0
    for k in range(successes, n + 1):
        log_term = (
            math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * log_p + (n - k) * log_q
        )
        total += math.exp(log_term)
    return min(1.0, total)


def holm_reject(p_values: Sequence[float], alpha: float) -> List[bool]:
    """Holm step-down procedure. Returns one reject flag per input p-value."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    reject = [False] * m
    for rank, idx in enumerate(order):
        if p_values[idx] <= alpha / (m - rank):
            reject[idx] = True
        else:
            break
    return reject


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean of empty sequence")
    return sum(values) / len(values)


def permutation_p_value_mean_difference(a: Sequence[float], b: Sequence[float],
                                        n_perm: int, seed: int) -> float:
    """Two-sided permutation p-value for a difference in means (add-one corrected)."""
    if not a or not b:
        raise ValueError("both samples must be non-empty")
    if n_perm <= 0:
        raise ValueError("n_perm must be positive")
    rng = random.Random(seed)
    observed = abs(_mean(a) - _mean(b))
    pooled = list(a) + list(b)
    n_a = len(a)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        diff = abs(_mean(pooled[:n_a]) - _mean(pooled[n_a:]))
        if diff >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def cluster_bootstrap_mean_ci(clusters: Mapping[str, Sequence[float]], n_boot: int,
                              alpha: float, seed: int) -> tuple:
    """Bootstrap CI for the mean, resampling whole clusters (e.g., game dates).

    Resampling by cluster keeps same-date observations together, so the
    interval is not too narrow when games on one date are correlated.
    """
    if not clusters:
        raise ValueError("no clusters")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    keys = list(clusters)
    rng = random.Random(seed)
    stats = []
    for _ in range(n_boot):
        sample: List[float] = []
        for _k in keys:
            sample.extend(clusters[rng.choice(keys)])
        stats.append(_mean(sample))
    stats.sort()
    lo_idx = int((alpha / 2.0) * n_boot)
    hi_idx = min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot))
    return stats[lo_idx], stats[hi_idx]


def break_even_probability(decimal_odds: float) -> float:
    """Implied probability of a decimal price (1 / odds). Ignores vig removal."""
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1")
    return 1.0 / decimal_odds


def profit_per_unit(decimal_odds: float, won: bool) -> float:
    """Profit on one unit staked at a decimal price (losses return -1)."""
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1")
    return (decimal_odds - 1.0) if won else -1.0


def leakage_violations(feature_times: Mapping[str, datetime], tipoff: datetime) -> List[str]:
    """Names of features that are not strictly available before tip-off."""
    if tipoff.tzinfo is None:
        raise ValueError("tipoff must be timezone-aware")
    out = []
    for name, stamp in feature_times.items():
        if stamp.tzinfo is None:
            raise ValueError(f"feature time for {name} must be timezone-aware")
        if stamp >= tipoff:
            out.append(name)
    return out


REQUIRED_THRESHOLDS = (
    "min_graded", "alpha", "score_diff_ci_low_min", "return_ci_low_min",
    "min_positive_blocks", "min_prospective",
)


def evaluate_gates(metrics: Mapping[str, object], thresholds: Mapping[str, float]) -> Dict[str, object]:
    """Return {'gates': {gate_id: status}, 'overall': status}.

    Status is PASS, FAIL, or BLOCKED. A gate is BLOCKED when its metric is
    missing. Overall is PASS only when every gate passes.
    """
    missing_thresholds = [k for k in REQUIRED_THRESHOLDS if k not in thresholds]
    if missing_thresholds:
        raise ValueError(f"approved thresholds missing: {missing_thresholds}")

    def gate(key: str, passed) -> str:
        if key not in metrics or metrics[key] is None:
            return "BLOCKED"
        return "PASS" if passed(metrics[key]) else "FAIL"

    results = {
        "G01": gate("unsourced_rows", lambda v: v == 0),
        "G02": gate("leakage_count", lambda v: v == 0),
        "G03": gate("score_diff_ci_low", lambda v: v > thresholds["score_diff_ci_low_min"]),
        "G04": gate("n_graded", lambda v: v >= thresholds["min_graded"]),
        "G05": gate("p_value_holm", lambda v: v <= thresholds["alpha"]),
        "G06": gate("net_return_ci_low", lambda v: v > thresholds["return_ci_low_min"]),
        "G07": gate("positive_blocks", lambda v: v >= thresholds["min_positive_blocks"]),
        "G08": gate("joint_within_interval", lambda v: v is True),
        "G09": gate("net_return_recorded_prices_ci_low", lambda v: v > thresholds["return_ci_low_min"]),
        "G10": gate("prospective_n", lambda v: v >= thresholds["min_prospective"]),
        "G11": gate("control_passed_any_gate", lambda v: v is False),
    }
    statuses = list(results.values())
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "BLOCKED" in statuses:
        overall = "BLOCKED"
    else:
        overall = "PASS"
    return {"gates": results, "overall": overall}


if __name__ == "__main__":  # pragma: no cover - manual use only
    print("gates.py defines helpers; run the unit tests in pipeline/tests.")
