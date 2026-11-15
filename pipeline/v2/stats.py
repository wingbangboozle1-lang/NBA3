"""Statistical primitives.  Standard library only, no scipy.

Written so that each function can be checked against a brute-force or a
published table instead of being trusted.  The tests in ``tests/`` do exactly
that.

Everything here is deliberately explicit about its null hypothesis, because a
p-value whose null is unclear is not a p-value, it is a decoration.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# descriptive
# ---------------------------------------------------------------------------
def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def sd(xs: Sequence[float]) -> float:
    """Sample standard deviation (n-1).  Returns 0.0 for n < 2."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def rmse(xs: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0


def mae(xs: Sequence[float]) -> float:
    return sum(abs(x) for x in xs) / len(xs) if xs else 0.0


def zscore_per_team(values: dict, larger_is_better: bool = True) -> dict:
    """Turn raw per-team residuals into z-scores.

    A residual is (actual - expected): positive means the team beat what its
    rating implied.  ``larger_is_better`` flips the sign so that a "lucky"
    z-score is always positive regardless of which direction was accumulated.
    """
    if len(values) < 2:
        return {k: 0.0 for k in values}
    keys = sorted(values)
    xs = [values[k] for k in keys]
    m = mean(xs)
    s = sd(xs)
    if s == 0:
        return {k: 0.0 for k in keys}
    sign = 1.0 if larger_is_better else -1.0
    return {k: sign * (values[k] - m) / s for k in keys}


# ---------------------------------------------------------------------------
# normal
# ---------------------------------------------------------------------------
def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard normal (Acklam's rational approximation, |err| < 1.2e-9)."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ---------------------------------------------------------------------------
# exact binomial
# ---------------------------------------------------------------------------
def binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    if k < 0 or k > n or n < 0:
        return 0.0
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_two_sided(k: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial test by summing outcomes no more likely than k.

    This is the method R uses for ``binom.test`` (the "sum of probabilities
    less than or equal to the observed one" definition).  It is used instead of
    a normal approximation because the strategy samples here are small: with
    n = 100 and p0 = 0.5 the normal approximation is off in the third decimal,
    and at n around 50 it is off by more than the gate margin.
    """
    if n == 0:
        return 1.0
    obs = binom_pmf(k, n, p)
    total = 0.0
    for i in range(n + 1):
        pi = binom_pmf(i, n, p)
        if pi <= obs * (1 + 1e-7):
            total += pi
    return min(1.0, total)


def binom_one_sided(k: int, n: int, p: float = 0.5) -> float:
    """P(X >= k) under H0: rate = p."""
    if n == 0:
        return 1.0
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(k, n + 1)))


def benjamini_hochberg(pvals: Sequence[float]) -> list:
    """BH step-up.  Returns q-values in the input order."""
    n = len(pvals)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [0.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        val = min(prev, pvals[i] * n / rank)
        q[i] = val
        prev = val
    return q


def wilson_interval(k: int, n: int, z: float = 1.959963985) -> tuple:
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------
def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r: float, n: int, z: float = 1.959963985) -> tuple:
    """95% CI for a Pearson r via Fisher's z.  Needs n >= 4 to mean anything."""
    if r is None or n is None or n < 4 or abs(r) >= 1.0:
        return (None, None)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = zr - z * se, zr + z * se
    return (math.tanh(lo), math.tanh(hi))


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Rank correlation with average ranks for ties."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    return pearson(ranks(xs), ranks(ys))


def required_n(rate: float, baseline: float = 0.5, alpha: float = 0.05,
               power: float = 0.80) -> int:
    """Games needed to distinguish ``rate`` from ``baseline`` with a one-sided
    exact-ish approximation.  Published as an approximation, not an exact
    power calculation."""
    if rate <= baseline:
        return None
    za = norm_ppf(1 - alpha)
    zb = norm_ppf(power)
    pbar = (rate + baseline) / 2
    num = za * math.sqrt(pbar * (1 - pbar)) + zb * math.sqrt(rate * (1 - rate))
    return int(math.ceil((num / (rate - baseline)) ** 2))


# ---------------------------------------------------------------------------
# pricing
# ---------------------------------------------------------------------------
def american_from_prob(p: float) -> int:
    """Fair American odds for a probability.  No vig; this is a fair price."""
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return -int(round(100 * p / (1 - p)))
    return int(round(100 * (1 - p) / p))


def prob_from_american(a: int) -> float:
    if a is None:
        return None
    if a < 0:
        return (-a) / (-a + 100.0)
    return 100.0 / (a + 100.0)


def parlay_price(legs: Sequence[float], rho: float = 0.0,
                 rho_method: str = "") -> dict:
    """Price a parlay two ways and print both.

    ``legs`` are fair single-leg probabilities.  The naive product assumes
    independence.  The measured-rho price applies a Gaussian copula with a
    single common correlation, which is the standard way to move from a
    measured pairwise rho to a joint probability when the legs are all
    "my side wins" style binaries.

    Both numbers are returned.  Neither is withheld: the brief asks for the
    measured price and the naive product side by side, and hiding one of them
    is what makes a parlay page untrustworthy.
    """
    if not legs or any(p is None or p <= 0 or p >= 1 for p in legs):
        return {"naive": None, "with_rho": None, "reason": "a leg probability is missing or degenerate"}
    naive = 1.0
    for p in legs:
        naive *= p
    if rho == 0.0 or len(legs) == 1:
        return {"naive": naive, "with_rho": naive, "rho": rho, "rho_method": rho_method,
                "note": "identical because rho is zero or the parlay has one leg"}
    if not (-1.0 < rho < 1.0):
        return {"naive": naive, "with_rho": None, "rho": rho, "rho_method": rho_method,
                "reason": "rho outside (-1,1); copula undefined"}
    # Gaussian copula, equicorrelated: integrate over one common normal factor.
    steps = 2000
    # Equicorrelated Gaussian copula.  Each leg is modelled as
    #     X_j = a_j * sqrt(|rho|) * Z + sqrt(1 - |rho|) * E_j
    # with Z, E_j independent standard normals.  For rho > 0 every leg loads on
    # Z with the SAME sign, so the legs tend to land together; for rho < 0 the
    # legs alternate sign, so they tend to land apart.  Loading every leg with
    # the same sign regardless of rho makes the negative case come out identical
    # to the positive case, which is the bug this comment prevents.
    #
    # Substituting u = Phi(z) turns the integral over Z into a plain average
    # over u in (0,1); the phi(z) weight is absorbed by the substitution.  Using
    # phi(z) as an extra weight inflates the answer by ~steps.
    ar = min(abs(rho), 0.999999)
    rho = ar if rho >= 0 else -ar
    weighted = []
    for j, p in enumerate(legs):
        sign = 1.0 if (j == 0 or rho > 0) else -1.0
        weighted.append((norm_ppf(p), sign))
    total = 0.0
    w = 1.0 / steps
    for i in range(steps):
        u = (i + 0.5) / steps
        z = norm_ppf(u)
        cond = 1.0
        for zi, sign in weighted:
            cond *= norm_cdf((zi - sign * math.sqrt(ar) * z) / math.sqrt(1 - ar))
        total += cond * w
    return {"naive": naive, "with_rho": total, "rho": rho, "rho_method": rho_method,
            "quadrature_steps": steps}


def dependence_ratio(joint: float, p1: float, p2: float) -> float:
    """joint / (p1*p2).  1.0 = independent, >1 = legs land together more often."""
    if not p1 or not p2:
        return None
    return joint / (p1 * p2)


# ---------------------------------------------------------------------------
# luck: is a strategy's edge more than the best of a board of nulls?
# ---------------------------------------------------------------------------
def board_luck_threshold(ns: Iterable[int], iterations: int = 4000,
                         seed: int = 20261115, ci: float = 0.95) -> dict:
    """The 95th percentile of "best edge on the board" when nothing is real.

    This is the number that makes a leaderboard honest.  When 12 rules are
    screened, the winner of the screen looks good even if all 12 have exactly
    zero edge, purely because 12 chances were taken.  The threshold is the edge
    the best rule would show in that all-null world, and a rule that does not
    clear it has not demonstrated skill -- it has demonstrated that it was the
    luckiest of 12.

    **The comparison must be like for like.**  Every rule's edge on the board is
    measured against a COIN (see ``score_rule``), so the null simulation must
    also measure each simulated rule against a coin.  Simulating the null
    against each rule's own observed rate instead produces a meaningless
    threshold: it compares a real edge to a re-centred null and can report a
    threshold above 100 percentage points.

    ``ns`` is each rule's out-of-sample sample size.  Rules with n = 0 are
    skipped, because a rule that never fires cannot win the screen.
    """
    import random

    rng = random.Random(seed)
    ns = [int(n) for n in ns if n and int(n) > 0]
    best = []
    for _ in range(iterations):
        top = -1.0
        for nn in ns:
            hits = sum(1 for _ in range(nn) if rng.random() < 0.5)
            edge = (hits / nn - 0.5) * 100.0
            if edge > top:
                top = edge
        best.append(top)
    best.sort()
    idx = min(len(best) - 1, int(ci * len(best)))
    return {
        "iterations": iterations,
        "seed": seed,
        "rules": len(ns),
        "rules_skipped_no_sample": 0,
        "ci": ci,
        "threshold_pp": round(best[idx], 4),
        "median_best_pp": round(best[len(best) // 2], 4),
        "baseline": "coin flip at 50%, matching how each rule's edge is measured",
        "note": ("the threshold is the 95th percentile of the single best edge across all "
                 "screened rules under a zero-skill null; it grows with the number of rules"),
    }


def noise_band(values: dict, k: float = 2.0) -> dict:
    """Which teams sit outside +/- k standard deviations of a residual set.

    Used for the luck test: a team whose season-to-date result is more than
    ``k`` z from what its rating predicted is either genuinely different or
    just noisy, and until that is settled a strategy that leans on it is not
    publishable.  The band is symmetric and stated in z units.
    """
    z = zscore_per_team(values, larger_is_better=True)
    inside = {t: v for t, v in z.items() if abs(v) <= k}
    outside = {t: v for t, v in z.items() if abs(v) > k}
    return {"k": k, "z": z, "inside": inside, "outside": outside,
            "n_inside": len(inside), "n_outside": len(outside)}
