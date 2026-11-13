"""Validation gates and statistics helpers for strategy scoring.

Standard library only. Thresholds are PROPOSED defaults (see docs/strategies.html)
and must be approved before they are used for any decision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

# Proposed defaults — not approved.
MIN_SETTLED_BETS = 300
ALPHA = 0.05
MIN_STABLE_BLOCKS = 3  # out of 4 time blocks


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), computed exactly."""
    if not 0 <= p <= 1:
        raise ValueError("p must be in [0, 1]")
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def exact_binomial_pvalue(wins: int, n: int, p0: float = 0.5) -> float:
    """One-sided exact p-value for 'win rate > p0'."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= wins <= n:
        raise ValueError("wins must be between 0 and n")
    return binom_sf(wins, n, p0)


def wilson_interval(wins: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a proportion (default 95%)."""
    if n <= 0:
        raise ValueError("n must be positive")
    phat = wins / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def benjamini_hochberg(pvalues: Sequence[float]) -> list[float]:
    """Benjamini–Hochberg adjusted p-values (q-values), same order as input."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        adjusted[i] = min(running, 1.0)
    return adjusted


def pearson_r(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation coefficient."""
    if len(xs) != len(ys):
        raise ValueError("series must have equal length")
    n = len(xs)
    if n < 2:
        raise ValueError("need at least two points")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        raise ValueError("correlation undefined for constant series")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def parlay_dependence_ratio(joint_rate: float, leg_a_rate: float, leg_b_rate: float) -> float:
    """Joint hit rate divided by the product of marginal rates.

    1.0 means independence; >1 positive dependence; <1 negative dependence.
    """
    if leg_a_rate <= 0 or leg_b_rate <= 0:
        raise ValueError("marginal rates must be positive")
    return joint_rate / (leg_a_rate * leg_b_rate)


def break_even_rate(decimal_odds: float) -> float:
    """Win rate needed to break even at decimal odds (no margin adjustment)."""
    if decimal_odds <= 1:
        raise ValueError("decimal odds must be greater than 1")
    return 1 / decimal_odds


@dataclass
class StrategyRecord:
    name: str
    wins: Sequence[int]          # wins per time block (oldest first)
    bets: Sequence[int]          # settled bets per time block
    decimal_odds_mean: float | None = None  # required for the luck-control gate
    adjusted_p: float | None = None         # filled by evaluate_portfolio


def evaluate_strategy(rec: StrategyRecord, min_bets: int = MIN_SETTLED_BETS,
                      alpha: float = ALPHA, min_blocks: int = MIN_STABLE_BLOCKS) -> dict:
    """Evaluate one strategy against the proposed gates.

    Returns a dict of gate -> (passed: bool | None, detail). None means
    'cannot evaluate' (missing input), which is never counted as a pass.
    """
    if len(rec.wins) != len(rec.bets):
        raise ValueError("wins and bets must align per block")
    total_n = sum(rec.bets)
    total_w = sum(rec.wins)
    gates: dict[str, tuple[bool | None, str]] = {}

    gates["G1_min_sample"] = (total_n >= min_bets, f"{total_n} settled bets (min {min_bets})")

    if total_n > 0:
        p = exact_binomial_pvalue(total_w, total_n)
        gates["G3_beats_no_skill"] = (
            (rec.adjusted_p if rec.adjusted_p is not None else p) < alpha,
            f"one-sided p={p:.4f}" + (f", adjusted p={rec.adjusted_p:.4f}" if rec.adjusted_p is not None else " (not multiple-test adjusted)"),
        )
    else:
        gates["G3_beats_no_skill"] = (None, "no bets")

    if total_n > 0 and rec.decimal_odds_mean:
        be = break_even_rate(rec.decimal_odds_mean)
        lo, hi = wilson_interval(total_w, total_n)
        gates["G4_luck_control"] = (lo > be, f"Wilson 95% lower bound {lo:.4f} vs break-even {be:.4f}")
    else:
        gates["G4_luck_control"] = (None, "needs decimal odds (unsourced)")

    gates["G5_market_benchmark"] = (None, "BLOCKED: no verified odds source")

    blocks_pos = sum(1 for w, n in zip(rec.wins, rec.bets) if n > 0 and w / n > 0.5)
    evaluated_blocks = sum(1 for n in rec.bets if n > 0)
    if evaluated_blocks >= 4:
        gates["G6_stability"] = (blocks_pos >= min_blocks, f"{blocks_pos}/{evaluated_blocks} blocks above 50%")
    else:
        gates["G6_stability"] = (None, f"needs 4 blocks with bets, has {evaluated_blocks}")

    gates["G7_parlay_dependence"] = (None, "not applicable to single-bet strategies")
    return {"name": rec.name, "gates": gates}


def passes_all_evaluable(result: dict) -> bool:
    """True only if every gate that can be evaluated passed AND none are missing."""
    vals = [v[0] for v in result["gates"].values()]
    return all(v is True for v in vals)


def evaluate_portfolio(records: Iterable[StrategyRecord], alpha: float = ALPHA) -> list[dict]:
    """Apply BH correction across strategies, then evaluate each one."""
    records = list(records)
    raw = []
    for r in records:
        n = sum(r.bets)
        raw.append(exact_binomial_pvalue(sum(r.wins), n) if n > 0 else 1.0)
    adj = benjamini_hochberg(raw)
    out = []
    for r, q in zip(records, adj):
        r.adjusted_p = q
        out.append(evaluate_strategy(r, alpha=alpha))
    return out
