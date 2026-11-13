"""Pure-Python statistics helpers.

No third-party packages are available in this sandbox (numpy/scipy/pandas are not
installed and the network is restricted to pypi.org), so every routine below is
implemented from first principles and is therefore auditable line by line.

Functions
---------
mean / stdev / corr / ols / binomial_test / t_test_1sample / bh_fdr
"""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs: Sequence[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def stdev(xs: Sequence[float], ddof: int = 1) -> float:
    return math.sqrt(variance(xs, ddof))


def corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(xs)
    if n != len(ys) or n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r: float, n: int, conf: float = 0.95) -> Tuple[float, float]:
    """Confidence interval for a Pearson correlation via the Fisher z transform."""
    if n < 4 or not math.isfinite(r) or abs(r) >= 1:
        return (float("nan"), float("nan"))
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    # 1.959964 = two-sided 95% normal critical value
    zc = 1.959963984540054
    lo = math.tanh(z - zc * se)
    hi = math.tanh(z + zc * se)
    return (lo, hi)


def solve_linear_system(A: List[List[float]], b: List[float]) -> List[float]:
    """Solve A x = b by Gaussian elimination with partial pivoting."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            raise ValueError("singular matrix")
        M[col], M[pivot] = M[pivot], M[col]
        pv = M[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col] / pv
            if factor == 0.0:
                continue
            for c in range(col, n + 1):
                M[r][c] -= factor * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def ols(X: List[List[float]], y: List[float], ridge: float = 0.0) -> List[float]:
    """Ordinary least squares (optionally ridge-penalised) via normal equations."""
    p = len(X[0])
    A = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for row, target in zip(X, y):
        for i in range(p):
            b[i] += row[i] * target
            for j in range(p):
                A[i][j] += row[i] * row[j]
    if ridge:
        for i in range(p):
            A[i][i] += ridge
    return solve_linear_system(A, b)


def binomial_test(k: int, n: int, p: float = 0.5, alternative: str = "two-sided") -> float:
    """Exact binomial test.

    alternative: 'two-sided' | 'greater' | 'less'
    """
    if n <= 0:
        return float("nan")
    k = int(k)
    n = int(n)
    p = float(p)

    def pmf(i: int) -> float:
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))

    if alternative == "greater":
        return min(1.0, sum(pmf(i) for i in range(k, n + 1)))
    if alternative == "less":
        return min(1.0, sum(pmf(i) for i in range(0, k + 1)))
    # two-sided: sum of all outcomes no more likely than the observed one
    observed = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= observed * (1 + 1e-12)))


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    maxit, eps, fpmin = 300, 3.0e-16, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(
        lbeta + b * math.log(1.0 - x) + a * math.log(x)
    ) * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """One-sided survival function P(T > t) for Student's t."""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    p_two = betainc(df / 2.0, 0.5, x)
    return p_two / 2.0 if t > 0 else 1.0 - p_two / 2.0


def t_test_1sample(xs: Sequence[float], mu: float = 0.0) -> Tuple[float, float, float]:
    """One-sample t-test. Returns (t statistic, two-sided p, degrees of freedom)."""
    n = len(xs)
    if n < 2:
        return (float("nan"), float("nan"), float("nan"))
    m, s = mean(xs), stdev(xs, ddof=1)
    if s == 0:
        return (float("inf"), 0.0, n - 1)
    t = (m - mu) / (s / math.sqrt(n))
    p = 2.0 * t_sf(abs(t), n - 1)
    return (t, p, n - 1)


def bh_fdr(pvalues: Sequence[float], alpha: float = 0.05) -> List[bool]:
    """Benjamini-Hochberg step-up procedure. Returns reject flags in input order."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    flags = [False] * m
    thresh = 0.0
    for rank, idx in enumerate(order, start=1):
        crit = alpha * rank / m
        if pvalues[idx] <= crit:
            thresh = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= thresh:
            flags[idx] = True
    return flags


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if not 0.0 < p < 1.0:
        return float("nan")
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
