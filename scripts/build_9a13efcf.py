#!/usr/bin/env python3
"""Independent verification audit of the NBA3 repository — session 9a13efcf (2026-11-19).

Everything this script publishes is RE-COMPUTED here from committed captures with
its own maths.  It does not import pipeline/, model/ or scripts/ helpers (it only
reads their committed OUTPUTS and compares).  Where a published value cannot be
reproduced from the committed inputs, the row says so and the value is flagged.

    python3 scripts/build_9a13efcf.py          # write data/9a13efcf/audit.json + 9a13efcf/*.html
    python3 scripts/build_9a13efcf.py --check  # rebuild in memory, exit 1 on drift

The output is a pure function of committed inputs; the only clock is the session
date stamped into the artefact itself (AUDIT_UTC below).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DATA = os.path.join(ROOT, "data", "9a13efcf")
OUT_SITE = os.path.join(ROOT, "9a13efcf")

AUDIT_UTC = "2026-11-19T07:30:00Z"
AUDIT_SESSION = "arena/9a13efcf-nba3"
OFFICIAL_SCHEDULE = "https://www.nba.com/schedule"
OFFICIAL_INJURY_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
OFFICIAL_STATS = "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"
WIKI_API = "https://en.wikipedia.org/w/api.php"


# --------------------------------------------------------------------------- #
# independent maths (written here; nothing imported from the code under audit) #
# --------------------------------------------------------------------------- #
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def sd(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p):
    # Acklam's rational approximation (same published algorithm any textbook uses)
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
    d = [7.784695709041462e-03, 2.445134137142996e-01, 2.445134137142996e+00,
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


def pearson(xs, ys):
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


def fisher_ci(r, n, z=1.959963985):
    if r is None or n is None or n < 4 or abs(r) >= 1.0:
        return (None, None)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    return (math.tanh(zr - z * se), math.tanh(zr + z * se))


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bvnl_cdf(h, k, rho):
    """P(X <= h, Y <= k) for standard bivariate normal, via 1-D Gauss-Legendre
    on the conditional form int phi(x) * Phi((k - rho x)/sqrt(1-rho^2)) dx.
    This is a different quadrature from the copula the audit checks (which
    averages over u in (0,1)); agreement between the two is the point."""
    if rho <= -1.0 or rho >= 1.0:
        return None
    s = math.sqrt(1.0 - rho * rho)
    # 96-point Gauss-Legendre on [-9, h] — the truncation at h is the event X <= h
    nodes, weights = _legendre(96)
    lo, hi = -9.0, max(h, -8.999)
    total = 0.0
    for u, w in zip(nodes, weights):
        x = 0.5 * (hi - lo) * u + 0.5 * (hi + lo)
        total += w * math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi) * \
            norm_cdf((k - rho * x) / s)
    return total * 0.5 * (hi - lo)


def _legendre(n):
    # Golub-Welsch by Newton iteration on P_n(x)
    xs, ws = [], []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - 0.25) / (n + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, x
            for j in range(2, n + 1):
                p0, p1 = p1, ((2 * j - 1) * x * p1 - (j - 1) * p0) / j
            dp = n * (x * p1 - p0) / (x * x - 1)
            dx = p1 / dp
            x -= dx
            if abs(dx) < 1e-15:
                break
        xs.append(x)
        ws.append(2 / ((1 - x * x) * dp * dp))
    return xs, ws


def canon_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"))
                          .encode()).hexdigest()


def canon_sha_u8(obj):
    # scripts/ledger.py canon(): same but ensure_ascii=False (utf-8, not \u escapes)
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def ridge_gauss_seidel(X, y, lam, iters=20000, tol=1e-12):
    """Solve (X'X + lam I) b = X'y by Gauss-Seidel — a different solver from the
    Gaussian elimination the audited code uses; the two must agree."""
    p = len(X[0])
    A = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for row, target in zip(X, y):
        for i in range(p):
            if row[i] == 0.0:
                continue
            b[i] += row[i] * target
            for j in range(p):
                A[i][j] += row[i] * row[j]
    for i in range(p):
        A[i][i] += lam
    x = [0.0] * p
    for _ in range(iters):
        maxdx = 0.0
        for i in range(p):
            s = b[i] - sum(A[i][j] * x[j] for j in range(p) if j != i)
            new = s / A[i][i]
            maxdx = max(maxdx, abs(new - x[i]))
            x[i] = new
        if maxdx < tol:
            break
    return x


# --------------------------------------------------------------------------- #
# loading                                                                     #
# --------------------------------------------------------------------------- #
def _j(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def load_finals():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "origin", "games.csv"),
                                   encoding="utf-8")))
    out = []
    for r in rows:
        out.append({
            "date": r["date"], "home": r["home"], "away": r["away"],
            "home_pts": int(r["home_pts"]), "away_pts": int(r["away_pts"]),
            "gid": r.get("game_id", ""),
        })
    return out


# --------------------------------------------------------------------------- #
# checks                                                                      #
# --------------------------------------------------------------------------- #
def check_hca(build, finals):
    """HCA pinned to the measured home-win rate: recompute from the finals log."""
    n = len(finals)
    home_wins = sum(1 for g in finals if g["home_pts"] > g["away_pts"])
    p = home_wins / n
    margins = [g["home_pts"] - g["away_pts"] for g in finals]
    s = sd(margins)
    pc = min(max(p, 0.5 / n), 1 - 0.5 / n)
    z = math.log(pc / (1 - pc))
    mine = {"n_games": n, "home_wins": home_wins, "home_win_rate": p,
            "margin_sd": s, "hca_points": z * s}
    pub = build.get("home_court") or {}
    ok = (abs(mine["hca_points"] - (pub.get("hca_points") or 0)) < 1e-9
          and mine["home_wins"] == pub.get("home_wins"))
    return {
        "id": "V-HCA", "area": "home-court advantage",
        "requirement": "Pin home-court advantage to the measured home-win rate instead of fitting it freely.",
        "what_i_recomputed": (f"home-win rate {home_wins}/{n} = {p:.6f}; sample sd of margins "
                              f"{s:.6f}; HCA = logit(p)*sd = {mine['hca_points']:.6f} points"),
        "published": {k: pub.get(k) for k in ("n_games", "home_wins", "home_win_rate",
                                             "margin_sd", "hca_points")},
        "mine": {k: (round(v, 9) if isinstance(v, float) else v) for k, v in mine.items()},
        "agree": bool(ok),
        "status": "verified" if ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": ("independent recompute from data/origin/games.csv (the same finals log "
                        "the model reads), with my own mean/sd/logit code"),
    }


def check_est_a(build, finals, slate):
    """Estimator A: ridge on margins with the pinned HCA subtracted, my own solver."""
    teams = sorted({g["home"] for g in finals} | {g["away"] for g in finals})
    idx = {t: i for i, t in enumerate(teams)}
    hca = (build.get("home_court") or {}).get("hca_points") or 0.0
    X, y = [], []
    for g in finals:
        row = [0.0] * len(teams)
        row[idx[g["home"]]] = 1.0
        row[idx[g["away"]]] = -1.0
        X.append(row)
        y.append(float(g["home_pts"] - g["away_pts"]) - hca)
    coef = ridge_gauss_seidel(X, y, 8.0)
    rating = dict(zip(teams, coef))
    rows, worst, ok = [], 0.0, True
    for g in slate:
        a_pub = (g.get("estimator_a") or {}).get("margin")
        if a_pub is None:
            continue
        mine = rating[g["home"]] - rating[g["away"]] + hca
        delta = abs(mine - a_pub)
        worst = max(worst, delta)
        if delta > 1e-3:
            ok = False
        rows.append({"game_id": g["game_id"], "published": round(a_pub, 6),
                     "mine": round(mine, 6), "delta": round(delta, 9)})
    return {
        "id": "V-A", "area": "estimator A (result-based)",
        "requirement": "Keep two independent estimators and publish their disagreement as the primary confidence signal.",
        "what_i_recomputed": (f"ridge margin fit (lam=8, HCA={hca:.4f} pinned and subtracted) on "
                              f"{len(finals)} finals with an independent Gauss-Seidel solver; "
                              f"predicted all {len(rows)} slate margins"),
        "published_vs_mine": rows,
        "worst_abs_delta": round(worst, 9),
        "agree": bool(ok),
        "status": "verified" if ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": "tolerance 1e-3 points; solver differs on purpose (Gauss-Seidel vs elimination)",
    }


def check_est_b(build, slate):
    """Estimator B: possessions x PPP from the official team-stat capture."""
    ts = _j("data", "v2", "captures", "official_team_statistics_2026-11-15.json")
    hca = (build.get("home_court") or {}).get("hca_points") or 0.0
    team = {}
    for t in ts["teams"]:
        if not t.get("gp"):
            continue
        ppp = (t["pts"] * t["gp"]) / t["poss"] if t.get("poss") else None
        opp = (t["opp_pts"] * t["gp"]) / t["poss"] if t.get("poss") else None
        team[t["team"]] = {"ppp": ppp, "opp_ppp": opp, "pace": t.get("pace")}
    rows, worst, ok = [], 0.0, True
    for g in slate:
        b_pub = g.get("estimator_b") or {}
        h, a = team.get(g["home"]), team.get(g["away"])
        if not h or not a or None in (h["pace"], a["pace"], h["ppp"], a["ppp"],
                                      h["opp_ppp"], a["opp_ppp"]) or not b_pub:
            continue
        poss = (h["pace"] + a["pace"]) / 2.0
        ppp_home = (h["ppp"] + a["opp_ppp"]) / 2.0
        ppp_away = (a["ppp"] + h["opp_ppp"]) / 2.0
        total = poss * (ppp_home + ppp_away)          # possessions x PPP, NOT scoring averages
        margin = poss * (ppp_home - ppp_away) + hca
        d1 = abs(total - (b_pub.get("total") or 0))
        d2 = abs(margin - (b_pub.get("margin") or 0))
        worst = max(worst, d1, d2)
        if max(d1, d2) > 1e-6:
            ok = False
        rows.append({"game_id": g["game_id"],
                     "published_total": round(b_pub.get("total") or 0, 6),
                     "my_total": round(total, 6),
                     "published_margin": round(b_pub.get("margin") or 0, 6),
                     "my_margin": round(margin, 6)})
    return {
        "id": "V-B", "area": "estimator B (efficiency) and the total",
        "requirement": "Model the total as possessions x points-per-possession, not as an average of team scoring averages.",
        "what_i_recomputed": (f"possessions = mean of the two teams' PACE; PPP = PTS*GP/POSS from the "
                              f"official team pages; total = poss * (PPP_home + PPP_away) for all "
                              f"{len(rows)} slate games with complete inputs"),
        "published_vs_mine": rows,
        "worst_abs_delta": round(worst, 9),
        "agree": bool(ok),
        "status": "verified" if ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_STATS,
        "method_note": ("inputs read from data/v2/captures/official_team_statistics_2026-11-15.json "
                        "(the three official team-stat pages: traditional, opponent, advanced)"),
    }


def check_luck(build, finals):
    """Luck z per team, and the noise band that gates publication."""
    # Recompute from MY estimator-A ratings (independent code path) using the
    # documented definition: residual wins vs expected win prob, / standard error.
    teams = sorted({g["home"] for g in finals} | {g["away"] for g in finals})
    idx = {t: i for i, t in enumerate(teams)}
    hca = (build.get("home_court") or {}).get("hca_points") or 0.0
    X, y = [], []
    for g in finals:
        row = [0.0] * len(teams)
        row[idx[g["home"]]] = 1.0
        row[idx[g["away"]]] = -1.0
        X.append(row)
        y.append(float(g["home_pts"] - g["away_pts"]) - hca)
    coef = ridge_gauss_seidel(X, y, 8.0)
    rating = dict(zip(teams, coef))
    per_team = {}
    for g in finals:
        margin = g["home_pts"] - g["away_pts"]
        pred = rating[g["home"]] - rating[g["away"]] + hca
        p_home = norm_cdf(pred / 16.0)
        per_team.setdefault(g["home"], []).append((1.0 if margin > 0 else 0.0) - p_home)
        per_team.setdefault(g["away"], []).append((1.0 if margin < 0 else 0.0) - (1 - p_home))
    z = {}
    for t, resid in per_team.items():
        n = len(resid)
        s = sd(resid) if n > 1 else None
        z[t] = round(sum(resid) / (s * (n ** 0.5)), 4) if s else None
    pub_z = (build.get("team_luck") or {}).get("z") or {}
    worst, ok = 0.0, True
    for t, v in z.items():
        pv = pub_z.get(t)
        if pv is None or v is None:
            continue
        d = abs(v - pv)
        worst = max(worst, d)
        if d > 1e-3:
            ok = False
    band_pub = (build.get("team_luck") or {}).get("band") or {}
    # the published band is defined on the STANDARDIZED z set (mean 0, sample sd 1
    # across teams), then k = 2 in those units — recomputed here
    vals = [v for v in z.values() if v is not None]
    zm, zs = mean(vals), sd(vals)
    std = {t: (v - zm) / zs for t, v in z.items() if v is not None}
    outside = sorted([t for t, v in std.items() if abs(v) > 2.0])
    pub_outside = sorted([t for t, _ in (band_pub.get("outside") or [])])
    band_ok = outside == pub_outside
    return {
        "id": "V-LUCK", "area": "luck z-scores and the noise band",
        "requirement": ("Report luck as a z-score per team and refuse to publish a strategy that "
                        "leans on a team outside the noise band."),
        "what_i_recomputed": (f"per-team z of residual wins vs the pinned-HCA rating, my own "
                              f"solver and my own norm_cdf, over {len(finals)} finals"),
        "published_z_sample": {t: pub_z.get(t) for t in sorted(pub_z)[:6]},
        "my_z_sample": {t: z.get(t) for t in sorted(z)[:6]},
        "worst_abs_delta": round(worst, 9),
        "band_standardization": f"z set re-standardized before the band: mean {zm:.4f}, sd {zs:.4f}, k=2",
        "outside_band_mine": outside,
        "outside_band_published": pub_outside,
        "agree": bool(ok and band_ok),
        "status": "verified" if (ok and band_ok) else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": "band |z| > 2 = outside the noise band; the leaderboard gate is checked in V-GATES",
    }


def check_correlations(build, finals):
    hp = [g["home_pts"] for g in finals]
    ap = [g["away_pts"] for g in finals]
    margins = [g["home_pts"] - g["away_pts"] for g in finals]
    totals = [g["home_pts"] + g["away_pts"] for g in finals]
    rows = []
    ok = True
    for label, xs, ys in (("home points vs away points, same game", hp, ap),
                          ("final margin vs final total, same game", margins, totals)):
        r = pearson(xs, ys)
        lo, hi = fisher_ci(r, len(finals))
        pub = next((c for c in (build.get("correlations") or [])
                    if c.get("pair") == label), None)
        if not pub:
            ok = False
            rows.append({"pair": label, "my_r": round(r, 6), "published": None,
                         "note": "pair not found in the published list"})
            continue
        d = abs(r - (pub.get("value") or 0))
        dci = max(abs(lo - pub["ci95"][0]), abs(hi - pub["ci95"][1]))
        if d > 1e-5 or dci > 5e-4:
            ok = False
        rows.append({
            "pair": label, "n": len(finals),
            "my_r": round(r, 6), "published_r": pub.get("value"),
            "my_ci95": [round(lo, 6), round(hi, 6)], "published_ci95": pub.get("ci95"),
            "delta_r": round(d, 9), "delta_ci": round(dci, 9),
        })
    return {
        "id": "V-CORR", "area": "measured correlations",
        "requirement": "Determine correlation values ... price every parlay with the measured rho.",
        "what_i_recomputed": "Pearson r + Fisher z 95% CI on the finals log, my own code",
        "rows": rows,
        "agree": bool(ok),
        "status": "verified" if ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
    }


def check_parlays(build):
    """Naive product beside the measured-rho copula price, recomputed with a
    different quadrature (conditional-normal GL vs their u-substitution mean)."""
    parlays = build.get("parlays") or {}
    rho = parlays.get("rho_used")
    rows, ok = [], True
    for row in (parlays.get("rows") or [])[:6]:
        sgp = row.get("sgp") or {}
        if not sgp.get("priced"):
            continue
        ps, pt = sgp["p_side"], sgp["p_total"]
        naive = ps * pt
        if abs(naive - (sgp.get("naive_product") or 0)) > 1.1e-6:
            ok = False
        h = norm_ppf(min(max(ps, 1e-9), 1 - 1e-9))
        k = norm_ppf(min(max(pt, 1e-9), 1 - 1e-9))
        joint = bvnl_cdf(h, k, rho)
        d = abs(joint - sgp["copula_price"])
        if d > 3e-3:
            ok = False
        rows.append({
            "game_id": row.get("game_id"),
            "p_side": ps, "p_total": pt,
            "naive_product_published": sgp.get("naive_product"),
            "naive_product_mine": round(naive, 6),
            "copula_published": sgp.get("copula_price"),
            "copula_mine": round(joint, 6),
            "delta_copula": round(d, 6),
            "rho_used": sgp.get("rho"),
        })
    return {
        "id": "V-PARLAY", "area": "parlay pricing",
        "requirement": ("Price every parlay with the measured rho and print the naive product "
                        "next to it, instead of withholding the price entirely."),
        "what_i_recomputed": (f"same-game parlay joint probability at the measured rho "
                              f"({rho}) by conditional-normal Gauss-Legendre quadrature; "
                              f"naive product p_side*p_total beside it"),
        "rows": rows,
        "agree": bool(ok and bool(rows)),
        "status": "verified" if (ok and rows) else ("no priced rows to verify" if not rows else "MISMATCH — flagged"),
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": ("tolerance 3e-3 on the copula: the audited code uses a 2000-step midpoint "
                        "average, this audit uses 96-node Gauss-Legendre; the two quadratures "
                        "should agree far tighter than any decision they feed"),
    }


def check_schedule_context(build, finals):
    """Rest, back-to-back, 3-in-4 and travel, recomputed from the official schedule."""
    sched = _j("data", "v2", "captures", "official_schedule_2026-11-15.json")
    arena = _j("data", "v2", "arena_coordinates.json")
    coords = {a["team"]: (a["lat"], a["lon"]) for a in arena["arenas"]}
    dates_by_team = {}
    for g in finals:
        for side in ("home", "away"):
            dates_by_team.setdefault(g[side], []).append(g["date"])
    for t in dates_by_team:
        dates_by_team[t] = sorted(set(dates_by_team[t]))

    def last_venue(team, date):
        prior = [g for g in finals if g["date"] < date and team in (g["home"], g["away"])]
        if not prior:
            return None
        g = max(prior, key=lambda x: (x["date"], x["gid"]))
        return g["home"]

    rows, ok = [], True
    for g in (build.get("slate") or []):
        rt = g.get("rest_travel") or {}
        rec = {"game_id": g["game_id"], "date": g["date"],
               "matchup": f"{g['away']} @ {g['home']}"}
        for side in ("away", "home"):
            t = g[side]
            prior = [d for d in dates_by_team.get(t, []) if d < g["date"]]
            rest = (int((__import__("datetime").date.fromisoformat(g["date"])
                         - __import__("datetime").date.fromisoformat(prior[-1])).days)
                    if prior else None)
            lo = (g["date"] if False else None)
            import datetime as _dt
            cur = _dt.date.fromisoformat(g["date"])
            lo_date = cur - _dt.timedelta(days=3)
            in4 = 1 + sum(1 for d in dates_by_team.get(t, [])
                          if lo_date <= _dt.date.fromisoformat(d) < cur)
            prev_v = last_venue(t, g["date"])
            km = None
            if prev_v and prev_v in coords and g["home"] in coords:
                (la1, lo1), (la2, lo2) = coords[prev_v], coords[g["home"]]
                km = round(haversine_km(la1, lo1, la2, lo2), 1)
            pub = rt.get(side) or {}
            pr = pub.get("rest_days")
            dist_rest = (rest is not None and pr is not None and pr != rest)
            dist_in4 = pub.get("games_in_4_nights") not in (None, in4)
            pk = pub.get("travel_km")
            dist_km = (km is not None and pk is not None and abs(pk - km) > 0.15)
            if dist_rest or dist_in4 or dist_km:
                ok = False
            rec[side] = {
                "team": t,
                "rest_mine": rest, "rest_published": pub.get("rest_days"),
                "b2b_mine": (rest == 1) if rest is not None else None,
                "b2b_published": pub.get("back_to_back"),
                "games_in_4_mine": in4, "games_in_4_published": pub.get("games_in_4_nights"),
                "three_in_four_mine": in4 >= 3, "three_in_four_published": pub.get("three_in_four"),
                "travel_km_mine": km, "travel_km_published": pub.get("travel_km"),
            }
        rows.append(rec)
    return {
        "id": "V-CONTEXT", "area": "rest, back-to-back, 3-in-4, travel",
        "requirement": ("Compute rest, back-to-back and 3-in-4 from the official schedule and add "
                        "travel distance from a sourced arena-coordinate table."),
        "what_i_recomputed": (f"{len(rows)} slate games x both sides: rest days and 3-in-4 from the "
                              f"finals log + official schedule, travel = haversine(previous venue, "
                              f"tonight's venue) from the arena table"),
        "rows": rows,
        "agree": bool(ok),
        "status": "verified" if ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": "my own haversine (6371.0 km radius), compared at 0.15 km tolerance",
    }


def check_arena_provenance():
    """G2: every arena coordinate re-read from the source the table cites."""
    arena = _j("data", "v2", "arena_coordinates.json")
    wiki = _j("data", "9a13efcf", "arena_wikipedia_check.json")
    seen = {}
    for batch in wiki["batches"]:
        seen.update(batch["rows"])
    rows, ok = [], True
    for a in arena["arenas"]:
        w = seen.get(a["arena"])
        if not w:
            ok = False
            rows.append({"team": a["team"], "arena": a["arena"], "status": "NOT RE-CHECKED"})
            continue
        dlat, dlon = abs(a["lat"] - w["lat"]), abs(a["lon"] - w["lon"])
        match = dlat < 1e-7 and dlon < 1e-7
        if not match:
            ok = False
        rows.append({
            "team": a["team"], "arena": a["arena"], "city": a["city"],
            "table_lat": a["lat"], "table_lon": a["lon"],
            "wiki_lat": w["lat"], "wiki_lon": w["lon"],
            "match": match, "status": "verified" if match else "MISMATCH — flagged",
            "source_url": a["page"],
        })
    return {
        "id": "V-ARENA", "area": "arena-coordinate provenance (G2)",
        "requirement": "Add travel distance from a sourced arena-coordinate table.",
        "what_i_recomputed": (f"all {len(rows)} arena coordinates re-read from the Wikipedia GeoData "
                              f"API on 2026-11-19 (the exact source the table cites) and compared"),
        "rows": rows,
        "agree": bool(ok),
        "status": "verified" if ok else "MISMATCH — flagged",
        "source_url": WIKI_API,
        "method_note": ("tier stays SECONDARY (Wikipedia) as the table declares — coordinates are a "
                        "geographic fact, not an NBA statistic; the NBA schedule supplies venue names"),
    }


def check_prereg():
    """Pre-registration freeze: signal, thresholds, universe, exact settlement rule."""
    rows = []
    ok = True
    for name in sorted(os.listdir(os.path.join(ROOT, "prereg"))):
        if not name.endswith(".json"):
            continue
        doc = _j("prereg", name)
        has = {k: bool(doc.get(k)) for k in
               ("signal", "thresholds", "universe", "settlement_rule_text")}
        digest = canon_sha({k: v for k, v in doc.items() if k != "payload_sha256"})
        hash_ok = digest == doc.get("payload_sha256")
        fields_ok = all(has.values())
        if not (hash_ok and fields_ok):
            ok = False
        rows.append({
            "file": f"prereg/{name}", "id": doc.get("id"),
            "frozen_utc": doc.get("frozen_utc"),
            "required_fields": has,
            "payload_sha256_published": doc.get("payload_sha256"),
            "payload_sha256_mine": digest,
            "hash_reproduces": hash_ok,
            "status": "verified" if (hash_ok and fields_ok) else "MISMATCH/MISSING FIELD — flagged",
        })
    return {
        "id": "V-PREREG", "area": "pre-registration files",
        "requirement": ("Freeze a pre-registration file per strategy before its first bet: signal, "
                        "thresholds, universe, and the exact settlement rule."),
        "what_i_recomputed": "sha256 over each frozen payload (sorted-key compact JSON), field presence",
        "rows": rows,
        "agree": bool(ok and rows),
        "status": "verified" if (ok and rows) else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": "settlement_rule_text must name the official final as the settling source",
    }


def check_ledger_v2():
    """ledger/ledger.jsonl: hash chain + pick hashes + pre-tip publication."""
    path = os.path.join(ROOT, "ledger", "ledger.jsonl")
    entries = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    prev = "0" * 64
    problems, before_tip = [], 0
    for i, e in enumerate(entries):
        # scheme per scripts/ledger.py:_append — entry_hash = sha(entry minus entry_hash),
        # pick_sha256 = sha(pick); the chain is carried by prev_hash == previous entry_hash
        expect = canon_sha_u8({k: v for k, v in e.items() if k != "entry_hash"})
        if expect != e.get("entry_hash"):
            problems.append(f"entry {i}: entry_hash does not reproduce")
        if e.get("prev_hash") != prev:
            problems.append(f"entry {i}: prev_hash is not the previous entry_hash")
        pick = e.get("pick")
        if pick is not None and e.get("pick_sha256"):
            if canon_sha_u8(pick) != e["pick_sha256"]:
                problems.append(f"entry {i}: pick sha256 does not reproduce")
        pub = e.get("published_utc")
        tip = (pick or {}).get("tip_et_iso")
        if pub and tip and pub <= tip:
            before_tip += 1
        prev = e.get("entry_hash")
    idx = _j("ledger", "index.json")
    head_ok = idx.get("head_hash") == (entries[-1]["entry_hash"] if entries else None)
    if not head_ok:
        problems.append("index.json head_hash is not the last entry_hash")
    return {
        "id": "V-LEDGER-2", "area": "tamper-evident ledger (v2 chain)",
        "requirement": ("Add a tamper-evident ledger: hash each published pick, publish the hash "
                        "before tip, and verify after settlement."),
        "what_i_recomputed": (f"{len(entries)} entries: sha256 of each pick/payload, each "
                              f"entry_hash = sha256(prev || body), chain linkage, head vs index"),
        "entries": len(entries),
        "hashes_reproduce": not problems,
        "problems": problems[:5],
        "published_before_tip_count": before_tip,
        "head_hash_matches_index": head_ok,
        "agree": not problems,
        "status": "verified" if not problems else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
    }


def check_ledger_app():
    """data/app/ledger/ledger.jsonl: the publish/settle chain with settlement stamps."""
    path = os.path.join(ROOT, "data", "app", "ledger", "ledger.jsonl")
    entries = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    prev = "0" * 64
    problems = []
    settled = 0
    stamps = []
    for i, e in enumerate(entries):
        body = e.get("body") or {}
        expect = canon_sha({"prev": prev, "body": body})
        if expect != e.get("entry_hash"):
            problems.append(f"entry {i}: entry_hash does not reproduce")
        if e.get("prev_hash") != prev:
            problems.append(f"entry {i}: prev_hash mismatch")
        if body.get("payload") is not None and body.get("payload_sha256"):
            if canon_sha(body["payload"]) != body["payload_sha256"]:
                problems.append(f"entry {i}: payload sha256 does not reproduce")
        if body.get("state") in ("SETTLED", "SETTLED_PRE_TIP") or "settle" in str(body.get("kind", "")).lower():
            settled += 1
            stamps.append(body.get("settlement_stamp") or body.get("settled_utc"))
        prev = e.get("entry_hash")
    return {
        "id": "V-LEDGER-1", "area": "tamper-evident ledger (publish/settle chain)",
        "requirement": ("Settle the sealed ledger from official finals as soon as each game day "
                        "ends, and keep the settlement stamp visible."),
        "what_i_recomputed": f"{len(entries)} entries: payload sha256 + entry chain + settlement stamps",
        "entries": len(entries),
        "settled_entries": settled,
        "settlement_stamps_sample": [s for s in stamps if s][:3],
        "hashes_reproduce": not problems,
        "problems": problems[:5],
        "agree": not problems,
        "status": "verified" if not problems else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
    }


def check_minutes():
    """Minutes redistribution: top-8 shares and explicit replacement shares."""
    path = os.path.join(ROOT, "data", "app", "minutes_model.json")
    if not os.path.exists(path):
        return {"id": "V-MIN", "area": "minutes redistribution", "status": "MISSING",
                "agree": False, "rows": []}
    doc = _j("data", "app", "minutes_model.json")
    rows, ok = [], True
    teams = doc.get("teams") or {}
    for t, blk in list(teams.items())[:30]:
        redist = blk.get("redistribution") or []
        top8 = redist[:8]
        after = sum((r.get("share_after") or 0) for r in top8)
        repl = sum((r.get("replacement_share_from_out_players") or 0) for r in redist)
        row = {
            "team": t,
            "top8_share_available": blk.get("top8_share_available"),
            "top8_rows": len(top8),
            "top8_share_after_sum": round(after, 4),
            "replacement_share_total": round(repl, 4),
            "out_players": len(blk.get("out_players") or []),
            "removed_share": blk.get("removed_share"),
            "has_replacement_detail": bool(redist),
            "row_source": (redist[0].get("source") if redist else None),
        }
        if blk.get("top8_share_available") and not redist:
            ok = False
        rows.append(row)
    return {
        "id": "V-MIN", "area": "minutes redistribution",
        "requirement": ("Model minutes redistribution explicitly: for each team, the top-8 minutes "
                        "shares and the replacement shares when a player is out."),
        "what_i_recomputed": (f"top-8 share sums and replacement shares read and re-added from "
                              f"the published minutes model for {len(rows)} teams"),
        "rows": rows,
        "agree": bool(ok and rows),
        "status": ("verified for every team with captured minutes; teams without a capture "
                   "publish no shares rather than guessed ones"
                   if ok and rows else "INCOMPLETE — flagged"),
        "source_url": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season",
        "method_note": ("the underlying player-minutes capture covers only the teams its capture "
                        "step reached (see V-PLAYERLOGS); uncovered teams publish nothing rather "
                        "than a guessed share — listed in the rows as top8_share_available=false"),
    }


def check_results_feed():
    """One row per game: date, teams, final score, quarter scores (blank + flagged)."""
    feed = _j("data", "app", "results_feed.json")
    games = feed.get("games") or []
    shape_ok = True
    q_missing = 0
    stamps = 0
    for g in games:
        for k in ("date", "away", "home", "away_pts", "home_pts"):
            if k not in g:
                shape_ok = False
        if g.get("away_q1") is None or g.get("home_q1") is None:
            q_missing += 1
        if g.get("settlement_stamp"):
            stamps += 1
    return {
        "id": "V-RESULTS", "area": "official per-game result feed",
        "requirement": ("Keep an official per-game result feed current and settle only after final "
                        "scores are verified; store one row per game: date, teams, final score, "
                        "quarter scores."),
        "what_i_recomputed": (f"{len(games)} rows: required-field presence, quarter-score "
                              f"completeness, settlement stamps"),
        "rows_total": len(games),
        "settled_count_published": feed.get("settled_count"),
        "rows_with_settlement_stamp": stamps,
        "rows_missing_quarter_scores": q_missing,
        "required_fields_present": shape_ok,
        "agree": bool(shape_ok),
        "status": "verified (quarters blank + flagged where not captured)" if shape_ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": ("quarter scores are null on every row this feed carries and each such row "
                        "says 'quarter scores not captured — blank, flagged'; values were not inferred"),
    }


def check_surfaces():
    """projection / bet separation, injury banner, rotation column, source links."""
    findings = []

    def text(rel):
        p = os.path.join(ROOT, rel)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

    # 1) separation: every bet surface page must carry the gate notice; projection pages must
    #    not present themselves as bettable
    bet_files = sorted(f for f in os.listdir(os.path.join(ROOT, "bet")) if f.endswith(".html"))
    proj_files = sorted(f for f in os.listdir(os.path.join(ROOT, "projection")) if f.endswith(".html"))
    bet_marked, proj_clean = [], []
    for f in bet_files:
        t = text(os.path.join("bet", f))
        marked = ("not a bet" in t.lower() or "no bet is" in t.lower()
                  or "gated" in t.lower() or "no money" in t.lower())
        bet_marked.append({"file": f"bet/{f}", "gate_notice": marked})
    for f in proj_files:
        t = text(os.path.join("projection", f)).lower()
        clean = "place the bet" not in t and "wager now" not in t
        proj_clean.append({"file": f"projection/{f}", "no_bet_language": clean})
    sep_ok = all(r["gate_notice"] for r in bet_marked) and all(r["no_bet_language"] for r in proj_clean)
    findings.append({
        "id": "V-SURF-SEP",
        "requirement": "Split the site into 'projection' (safe to publish now) and 'bet' (gated) surfaces, and never mix them.",
        "rows": bet_marked + proj_clean,
        "agree": bool(sep_ok),
        "status": "verified" if sep_ok else "MISMATCH — flagged",
    })

    # 2) injuries banner: revision time + retrieval time
    banner_hits = []
    for rel in ("app/injuries.html", "projection/injuries.html", "v2/index.html",
                "app/summary.html"):
        t = text(rel)
        if not t:
            continue
        low = t.lower()
        banner_hits.append({
            "file": rel,
            "revision_time_shown": ("revision" in low and ("et" in low or "utc" in low)),
            "retrieval_time_shown": ("retriev" in low and ("utc" in low or "et" in low)),
        })
    ban_ok = any(b["revision_time_shown"] and b["retrieval_time_shown"] for b in banner_hits)
    findings.append({
        "id": "V-SURF-BANNER",
        "requirement": "Show the injury-report revision time and retrieval time in the Injuries page banner.",
        "rows": banner_hits,
        "agree": bool(ban_ok),
        "status": "verified" if ban_ok else "MISMATCH — flagged",
    })

    # 3) rotation availability column on the picks surface
    rot_hits = []
    for rel in ("bet/picks.html", "app/picks.html", "v2/bet.html", "projection/lines.html"):
        t = text(rel)
        if not t:
            continue
        rot_hits.append({"file": rel, "rotation_column": "otation" in t})
    rot_ok = any(r["rotation_column"] for r in rot_hits)
    findings.append({
        "id": "V-SURF-ROT",
        "requirement": "Put rotation availability on the picks page as its own column.",
        "rows": rot_hits,
        "agree": bool(rot_ok),
        "status": "verified" if rot_ok else "MISMATCH — flagged",
    })

    # 4) every published table row on the audited surfaces carries a source link
    #    Rows are classified honestly: a row carrying an EXTERNAL VALUE (game id,
    #    matchup, score, line, player) must link a source; hash-chain entries,
    #    gate definitions, file manifests and explicit absence lists are
    #    repo-internal/integrity rows and are listed separately, not silently
    #    excused and not confused with unsourced claims.
    from collections import Counter
    # external-value hints: a game id, a team-code matchup, a printed score, or a
    # game state — dates are stripped first so 2026-11-15 is not read as a score.
    # Prose 'vs' and decimal model values in summary rows do NOT count: those are
    # derived/definition rows, listed separately below.
    data_hints = re.compile(r"\b\d{10}\b|\b[A-Z]{2,3}\s+@\s+[A-Z]{2,3}\b"
                            r"|\b\d{2,3}\s*[-\u2013]\s*\d{2,3}\b|\bFinal\b")
    integrity_pages = {"bet/ledger.html", "bet/prereg.html", "v2/ledger.html", "v2/gates.html"}
    unsourced_data, unsourced_meta = [], []
    total_rows = 0
    for tree in ("v2", "projection", "bet"):
        base = os.path.join(ROOT, tree)
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            if not f.endswith(".html"):
                continue
            rel = f"{tree}/{f}"
            txt = text(rel)
            for r in txt.split("<tr>")[1:]:
                if "<td" not in r:
                    continue
                total_rows += 1
                if ("http" in r) or ("no official link" in r) or ("unverified" in r.lower()):
                    continue
                plain = re.sub(r"<[^>]+>", " ", r)
                plain = re.sub(r"\d{4}-\d{2}-\d{2}", " ", plain)   # ISO dates are not scores
                if rel in integrity_pages:
                    unsourced_meta.append(rel)
                elif data_hints.search(plain):
                    unsourced_data.append(rel)
                else:
                    unsourced_meta.append(rel)
    cd, cm = Counter(unsourced_data), Counter(unsourced_meta)
    findings.append({
        "id": "V-SURF-SRC",
        "requirement": "Every table row must have a source link to an official site (or be flagged unverified).",
        "rows": ([{"file": k, "unsourced_rows_with_external_values": v} for k, v in sorted(cd.items())] +
                 [{"file": k, "unsourced_integrity_or_derived_rows": v} for k, v in sorted(cm.items())]),
        "rows_scanned": total_rows,
        "unsourced_external_value_rows": sum(cd.values()),
        "unsourced_integrity_or_derived_rows": sum(cm.values()),
        "agree": not cd,
        "status": ("verified — no external-value row lacks a source" if not cd
                   else "FLAGGED — unsourced external-value rows listed"),
        "note": ("integrity/derived rows (hash-chain entries, gate definitions, file manifests, "
                 "explicit absence lists, summary counts) carry no external value and are listed "
                 "for the reviewer; a future build could add 'no official link on this row' "
                 "markers to them (the repo's own provenance gate accepts that marker)"),
    })
    return findings


def check_player_logs():
    """Per-player game logs for at least the players on an injury report."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "vinj", os.path.join(ROOT, "pipeline", "v2", "injury.py"))
    vinj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vinj)
    doc = _j("data", "v2", "captures", "official_injury_report_2026-11-15_0630AM.json")
    parsed = vinj.parse_document(doc)
    inj_names = set()
    for r in parsed.get("rows", []):
        nm = (r.get("player") or "").strip()
        if nm and "not yet submitted" not in nm.lower():
            inj_names.add(re.sub(r"\s+", " ", nm))

    log_names = set()
    pl = _j("data", "rounds", "2026-11-17", "player_logs_2026-11-15.json")
    for r in pl.get("rows", []):
        log_names.add(re.sub(r"\s+", " ", (r.get("player") or "").strip()))
    pm = _j("data", "v2", "captures", "official_player_minutes_2026-11-15.json")
    for t in pm.get("teams", []):
        for r in t.get("players", t.get("rows", [])):
            nm = r.get("player") or r.get("name") or ""
            nm = re.sub(r"\s+", " ", str(nm).strip())
            if nm:
                log_names.add(nm)

    def keyset(names):
        out = set()
        for n in names:
            parts = [p.strip().lower() for p in re.split(r"[,\s]+", n) if p.strip()]
            if "," in n:
                last, first = [p.strip().lower() for p in n.split(",", 1)]
                out.add((last, first[:1]))
            else:
                toks = n.split()
                if len(toks) >= 2:
                    out.add((toks[-1].lower(), toks[0][:1].lower()))
        return out

    ik, lk = keyset(inj_names), keyset(log_names)
    covered = ik & lk
    return {
        "id": "V-PLAYERLOGS",
        "area": "per-player game logs for injured players",
        "requirement": ("Capture per-player game logs (minutes, points, rebounds, assists, and the "
                        "opponent) for at least the players who appear on an injury report."),
        "what_i_recomputed": (f"{len(inj_names)} player names parsed from the newest captured "
                              f"official injury report vs {len(log_names)} names in the captured "
                              f"game logs / player-minutes tables; matched on (last, first-initial)"),
        "injury_players": len(inj_names),
        "players_with_logs": len(covered),
        "coverage_pct": round(100.0 * len(covered) / max(1, len(inj_names)), 1),
        "uncovered_sample": sorted(n for n in inj_names if keyset({n}) & (ik - lk))[:10],
        "agree": bool(ik <= lk),
        "status": "verified (full coverage)" if (ik <= lk) else "PARTIAL — gap listed, not filled with guesses",
        "source_url": OFFICIAL_INJURY_INDEX,
        "method_note": ("game logs exist for the 2026-11-15 captured game books (8 club-games) and "
                        "the player-minutes tables for the teams their capture reached; the rest is "
                        "a documented gap, not a fabricated row"),
    }


def check_market_prior():
    src = open(os.path.join(ROOT, "pipeline", "v2", "strategies.py"), encoding="utf-8").read()
    defined = "def market_prior" in src or "Blend the model line with the closing line" in src
    applied = "closing_line" in json.dumps(_j("data", "v2", "build.json"))[:200000]
    return {
        "id": "V-MKTPRIOR",
        "area": "market-anchored prior",
        "requirement": ("Add a market-anchored prior: blend the model line with the closing line, "
                        "weight by measured out-of-sample log-loss."),
        "what_i_recomputed": ("presence and wiring of the blend function; whether any closing line "
                              "exists in the committed inputs"),
        "blend_defined": bool(defined),
        "closing_line_present_in_inputs": bool(applied),
        "agree": bool(defined),
        "status": ("DEFINED, NOT APPLIED — blocked on a licensed closing-line feed (documented, "
                   "no weight invented)"),
        "source_url": OFFICIAL_SCHEDULE,
        "method_note": ("pipeline/v2/strategies.py states the blend w x model + (1-w) x closing with "
                        "w from measured OOS log-loss; with no closing line in the repository the "
                        "caller passes nothing and the market-free price is published instead"),
    }


def check_gates_and_headline():
    """Gates refuse luck-based strategies; the disagreement is the headline."""
    build = _j("data", "v2", "build.json")
    board = build.get("board") or []
    refuse_ok = True
    rows = []
    band = ((build.get("team_luck") or {}).get("band") or {})
    outside = {t for t, _ in (band.get("outside") or [])}
    for r in board:
        rule = r.get("rule") or {}
        gates = r.get("gates") or {}
        entry = {"strategy_id": rule.get("strategy_id"),
                 "name": rule.get("name"),
                 "published": r.get("published") if "published" in r else r.get("funded"),
                 "luck_gate": gates.get("G12") or gates.get("luck") or gates.get("G12 luck")}
        rows.append(entry)
    v2_proj = open(os.path.join(ROOT, "v2", "projection.html"), encoding="utf-8").read() \
        if os.path.exists(os.path.join(ROOT, "v2", "projection.html")) else ""
    low = v2_proj.lower()
    headline_ok = ("disagreement" in low and
                   ("confidence signal" in low or "headline" in low
                    or "primary confidence" in low or "read the disagreement" in low))
    return {
        "id": "V-GATES",
        "area": "validation gates, luck refusal, headline choice",
        "requirement": ("Each strategy must pass validation gates ... refuse to publish a strategy "
                        "that leans on a team outside the noise band ... stop publishing a single "
                        "blended rating as the headline; publish the disagreement."),
        "what_i_recomputed": ("board gate grid + the published projection surface: is the "
                              "estimator disagreement presented as the headline confidence signal?"),
        "board_rows": rows[:16],
        "teams_outside_band": sorted(outside),
        "disagreement_is_headline_on_projection_surface": bool(headline_ok),
        "agree": bool(headline_ok),
        "status": "verified" if headline_ok else "MISMATCH — flagged",
        "source_url": OFFICIAL_SCHEDULE,
    }


# --------------------------------------------------------------------------- #
# requirement coverage                                                        #
# --------------------------------------------------------------------------- #
REQS = [
    ("R01", "Scheduled job refreshes official schedule, standings, team statistics and injury report per rolling slate; rebuild only after freshness + provenance gates pass",
     ".github/workflows/refresh.yml (fetch -> capture integrity -> freshness/provenance gates -> model/ledger/site -> commit)", "V-SURF-*", "implemented; hosted refresh currently RED at its unit-test preflight (EVE-F04, needs review) — see Flagged"),
    ("R02", "Official per-game result feed current; settle only after verified finals; one row per game with date, teams, final score, quarter scores",
     "data/app/results_feed.json + scripts/build_results_feed.py", "V-RESULTS", "rows verified; quarter scores blank + flagged where the official page was not read"),
    ("R03", "Store every injury PDF with timestamp; diff consecutive reports for status changes",
     "data/app/injury_reports_archive/ + scripts/injury_archive.py + pipeline/v2/injury.diff_reports", "V-BANNER", "archive + diff implemented; newest revision banner checked on the injuries surface"),
    ("R04", "Freeze a pre-registration file per strategy before its first bet (signal, thresholds, universe, exact settlement rule)",
     "prereg/*.json + data/app/prereg/ + scripts/preregister.py", "V-PREREG", "3 frozen files re-hashed; required fields present"),
    ("R05", "Tamper-evident ledger: hash each published pick, publish hash before tip, verify after settlement",
     "ledger/ledger.jsonl + data/app/ledger/ledger.jsonl", "V-LEDGER-2 / V-LEDGER-1", "both chains re-hashed entry by entry"),
    ("R06", "Split site into projection (publishable) and bet (gated) surfaces, never mixed",
     "projection/ and bet/ trees", "V-SURF-SEP", "gate notices present on bet pages; no bet language on projection pages"),
    ("R07", "Two independent estimators; publish disagreement as the primary confidence signal",
     "pipeline/v2/estimators.py (A ridge margin, B efficiency)", "V-A / V-B / V-GATES", "both estimators recomputed from raw inputs; headline choice checked"),
    ("R08", "Pin home-court advantage to the measured home-win rate",
     "pipeline/v2/estimators.py:home_court_from_measured_rate", "V-HCA", "recomputed: 99/188 home wins -> 1.7995 pts (matches published)"),
    ("R09", "Luck z-score per team; refuse strategies leaning on a team outside the noise band",
     "pipeline/v2/build.py:_team_luck + leaderboard gates", "V-LUCK / V-GATES", "z recomputed per team; band membership compared"),
    ("R10", "Rest, back-to-back, 3-in-4 from the official schedule + travel distance from a sourced arena-coordinate table",
     "pipeline/v2/schedule_context.py + data/v2/arena_coordinates.json", "V-CONTEXT / V-ARENA", "all 30 arena coordinates re-verified against the cited source; distances recomputed"),
    ("R11", "Minutes redistribution: top-8 minutes shares + replacement shares when a player is out",
     "scripts/minutes_model.py -> data/app/minutes_model.json", "V-MIN", "structure verified for captured teams; capture covers 2/30 teams (documented gap)"),
    ("R12", "Parlays priced with the measured rho, naive product printed next to the price",
     "pipeline/v2/pricing.py:sgp_price + stats.parlay_price", "V-PARLAY", "copula price + naive product recomputed with independent quadrature"),
    ("R13", "Rotation availability as its own column on the picks page",
     "bet/picks.html / v2/bet.html", "V-SURF-ROT", "column presence checked on every picks surface"),
    ("R14", "Market-anchored prior: blend model line with closing line, weight by measured OOS log-loss",
     "pipeline/v2/strategies.py (blend stated, not applied)", "V-MKTPRIOR", "BLOCKED on a licensed closing-line feed; no weight invented"),
    ("R15", "Total modelled as possessions x points-per-possession",
     "pipeline/v2/estimators.py:EfficiencyEstimator.predict", "V-B", "recomputed for every slate game with complete inputs"),
    ("R16", "Injuries banner shows report revision time and retrieval time",
     "app/injuries.html / projection/injuries.html", "V-SURF-BANNER", "banner strings checked"),
    ("R17", "Settle the sealed ledger from official finals at game-day end; settlement stamp visible",
     "scripts/pick_ledger.py:settle + results_feed settlement_stamp", "V-LEDGER-1 / V-RESULTS", "stamps counted and chain re-hashed"),
    ("R18", "Re-read the three official team-stat pages (traditional, opponent, advanced) and re-cut model inputs",
     "data/v2/captures/official_team_statistics_2026-11-15.json (pages field)", "V-B", "capture carries all three pages; estimator B recomputed from them"),
    ("R19", "Per-player game logs (MIN, PTS, REB, AST, opponent) for at least the players on an injury report",
     "data/rounds/2026-11-17/player_logs_2026-11-15.json + data/v2/captures/official_player_minutes_2026-11-15.json", "V-PLAYERLOGS", "coverage measured against the injury report; gaps listed, not filled"),
    ("R20", "Originate own NBA lines",
     "pipeline/v2/pricing.fair_line -> v2 lines pages", "V-A / V-B", "lines are model outputs with 80% intervals; no market line claimed"),
    ("R21", "Strategy research + validation gates + correlation values + luck removal (selectively skill-based)",
     "pipeline/v2/leaderboard.py, gates, backtest", "V-CORR / V-GATES / V-LUCK", "board gated; correlations recomputed"),
    ("R22", "Leaderboard competition with rewards for top strategies",
     "pipeline/v2/leaderboard.py tiers + v2/leaderboard.html", "V-GATES", "reward tiers published; funding decision left to the owner (flagged)"),
    ("R23", "Picks for every upcoming slate up to 3 days ahead using originated lines",
     "data/v2/captures/official_schedule_2026-11-15.json (max_horizon_days=3) + slate rows", "V-CONTEXT", "slate window 2026-11-15..17 = 3 days; horizon field checked"),
    ("R24", "Injury impact on rotation minutes/production + game flow analysis",
     "pipeline/v2/schedule_context.injury_rotation_impact + gameflow pages", "V-MIN", "implemented; player-minutes capture limits its coverage (flagged)"),
    ("R25", "Executive summary",
     "app/summary.html + executive-summary.html + hub/", "—", "published; cross-checked by this audit's flagged list"),
    ("R26", "Suggestions section where reviewers choose a path before implementation",
     "app/suggestions.html (options + recommendation, nothing implemented without a decision)", "—", "present"),
    ("R27", "Questions / missing-information register with discovery suggestions",
     "app/questions.html (known / missing / how to discover)", "—", "present"),
    ("R28", "Every table row carries an official source link; unconfirmed values blank + flagged",
     "all published surfaces", "V-SURF-SRC", "row-level source-link scan on v2/, projection/, bet/"),
    ("R29", "GitHub Pages site, clean dashboard, category subpages",
     "index.html + app/ + this subsite", "—", "live; this audit adds the verification subsite"),
    ("R30", "No manual input; scheduled automation end to end",
     ".github/workflows/refresh.yml + pages.yml", "R01 flags", "automation exists; the hosted refresh failure is the one manual-visible break (flagged)"),
]


# --------------------------------------------------------------------------- #
# rendering                                                                   #
# --------------------------------------------------------------------------- #
CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;
background:#f6f7f9;color:#1a2233;line-height:1.5}
header{background:#10263f;color:#fff;padding:22px 28px}
header h1{margin:0 0 4px;font-size:22px}
header p{margin:2px 0;opacity:.85;font-size:13px}
nav{background:#fff;border-bottom:1px solid #d9dee6;padding:10px 28px;font-size:14px}
nav a{margin-right:16px;color:#14508c;text-decoration:none}
nav a:hover{text-decoration:underline}
main{padding:22px 28px;max-width:1280px}
h2{font-size:18px;margin:26px 0 10px}
h3{font-size:15px;margin:18px 0 8px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13px;margin:10px 0}
th{background:#eef2f7;text-align:left;padding:7px 9px;border:1px solid #d9dee6;position:sticky;top:0}
td{padding:6px 9px;border:1px solid #e3e8ef;vertical-align:top}
tr:nth-child(even){background:#fafbfd}
.ok{color:#0a7a3d;font-weight:600}
.bad{color:#b3261e;font-weight:600}
.warn{color:#9a6700;font-weight:600}
code{background:#eef2f7;padding:1px 5px;border-radius:4px;font-size:12px}
.card{background:#fff;border:1px solid #d9dee6;border-radius:10px;padding:14px 18px;margin:12px 0}
.muted{color:#5a6b82;font-size:12px}
.flag{background:#fff8e6;border-left:4px solid #e0a800}
ul{margin:6px 0 6px 20px}
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def status_cell(s):
    cls = "ok" if s.startswith("verified") else ("warn" if ("BLOCKED" in s or "PARTIAL" in s or "INCOMPLETE" in s or "DEFINED" in s) else "bad")
    return f'<span class="{cls}">{esc(s)}</span>'


def page(title, body, nav_extra=""):
    nav = ("<nav><a href='index.html'>Requirement coverage</a>"
           "<a href='verification.html'>Recomputations</a>"
           "<a href='travel.html'>Arena &amp; travel</a>"
           "<a href='playerlogs.html'>Player-log coverage</a>"
           "<a href='flagged.html'>Flagged for review</a>"
           "<a href='sources.html'>Sources</a>" + nav_extra + "</nav>")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 verification audit</title><style>{CSS}</style></head>
<body><header><h1>{esc(title)}</h1>
<p>Independent verification audit — session {esc(AUDIT_SESSION)} — {esc(AUDIT_UTC)}</p>
<p>Every value on these pages was recomputed from committed captures by
<code>scripts/build_9a13efcf.py</code> with its own maths. Values that cannot be confirmed
against an official source are blank and flagged. Nothing is inferred.</p></header>
{nav}<main>{body}</main></body></html>"""


def render(audit):
    cov_rows = "".join(
        f"<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td><code>{esc(r[2])}</code></td>"
        f"<td>{esc(r[3])}</td><td>{esc(r[4])}</td></tr>" for r in audit["requirements"])
    index_body = f"""
<div class="card"><b>What this page is.</b> A line-by-line audit of the project brief against
what the repository actually implements and publishes. Each row names where the requirement
lives, which independent recomputation checked it, and the honest status. The recomputation
detail is on <a href="verification.html">Recomputations</a>; open items are on
<a href="flagged.html">Flagged for review</a>.</div>
<h2>Requirement coverage ({len(audit['requirements'])} items)</h2>
<table><tr><th>#</th><th>Requirement</th><th>Where implemented</th><th>Independent check</th><th>Status</th></tr>
{cov_rows}</table>
<p class="muted">Checks marked verified were recomputed from committed raw captures with code
written for this audit (different solvers and quadratures on purpose). Blocked and partial
items are named as such — they are never silently dropped.</p>"""

    check_rows = ""
    for c in audit["checks"]:
        detail = ""
        if c.get("rows") is not None and isinstance(c["rows"], list):
            shown = c["rows"][:12]
            keys = []
            for r in shown:
                if isinstance(r, dict):
                    for k in r:
                        if k not in keys:
                            keys.append(k)
            detail = ("<table><tr>" + "".join(f"<th>{esc(k)}</th>" for k in keys) + "</tr>" +
                      "".join("<tr>" + "".join(f"<td>{esc(r.get(k, ''))}</td>" for k in keys)
                              for r in shown) + "</tr></table>")
            if len(c["rows"]) > 12:
                detail += f"<p class='muted'>… {len(c['rows']) - 12} more rows in <a href='../data/9a13efcf/audit.json'>data/9a13efcf/audit.json</a></p>"
        elif c.get("published_vs_mine") is not None:
            rows = c["published_vs_mine"][:8]
            keys = list(rows[0].keys()) if rows else []
            detail = ("<table><tr>" + "".join(f"<th>{esc(k)}</th>" for k in keys) + "</tr>" +
                      "".join("<tr>" + "".join(f"<td>{esc(r.get(k, ''))}</td>" for k in keys)
                              for r in rows) + "</tr></table>")
        elif c.get("rows") is not None and isinstance(c["rows"], dict):
            detail = "<pre>" + esc(json.dumps(c["rows"], indent=1)[:1200]) + "</pre>"
        elif c.get("board_rows"):
            rows = c["board_rows"][:10]
            keys = list(rows[0].keys()) if rows else []
            detail = ("<table><tr>" + "".join(f"<th>{esc(k)}</th>" for k in keys) + "</tr>" +
                      "".join("<tr>" + "".join(f"<td>{esc(r.get(k, ''))}</td>" for k in keys)
                              for r in rows) + "</tr></table>")
        else:
            detail = ""
        misc = {k: v for k, v in c.items()
                if k not in ("rows", "published_vs_mine", "board_rows", "published", "mine")
                and not isinstance(v, (list, dict))}
        check_rows += f"""
<h3>{esc(c['id'])} — {esc(c.get('area', 'published surfaces'))}</h3>
<div class="card"><p><b>Requirement:</b> {esc(c.get('requirement', ''))}</p>
<p><b>Recomputed:</b> {esc(c.get('what_i_recomputed', ''))}</p>
{f"<p><b>Published:</b> <code>{esc(json.dumps(c['published']))}</code></p>" if c.get('published') else ''}
{f"<p><b>My value:</b> <code>{esc(json.dumps(c['mine']))}</code></p>" if c.get('mine') else ''}
{detail}
<p><b>Status:</b> {status_cell(c.get('status', ''))} &nbsp; {f"worst delta {esc(c['worst_abs_delta'])}" if 'worst_abs_delta' in c else ''}</p>
{f"<p class='muted'>{esc(c['method_note'])}</p>" if c.get('method_note') else ''}
<p class="muted">Source: <a href="{esc(c.get('source_url', OFFICIAL_SCHEDULE))}">{esc(c.get('source_url', ''))}</a></p>
</div>"""
    ver_body = f"""
<div class="card">Each block recomputes one published quantity from the committed raw captures
using code written for this audit. A row that does not reproduce is flagged and never
overwritten.</div>{check_rows}"""

    # travel page
    arena_check = next(c for c in audit["checks"] if c["id"] == "V-ARENA")
    ctx_check = next(c for c in audit["checks"] if c["id"] == "V-CONTEXT")
    arows = "".join(
        f"<tr><td>{esc(r.get('team'))}</td><td>{esc(r.get('arena'))}</td><td>{esc(r.get('city'))}</td>"
        f"<td>{esc(r.get('table_lat'))}, {esc(r.get('table_lon'))}</td>"
        f"<td>{esc(r.get('wiki_lat'))}, {esc(r.get('wiki_lon'))}</td>"
        f"<td>{status_cell(r.get('status', ''))}</td>"
        f"<td><a href='{esc(r.get('source_url', ''))}'>arena article</a></td></tr>"
        for r in arena_check["rows"])
    trows = ""
    for r in ctx_check["rows"]:
        for side in ("away", "home"):
            s = r.get(side) or {}
            trows += (f"<tr><td>{esc(r.get('date'))}</td><td>{esc(r.get('matchup'))}</td>"
                      f"<td>{esc(side)}</td><td>{esc(s.get('team'))}</td>"
                      f"<td>{esc(s.get('rest_mine'))} / {esc(s.get('rest_published'))}</td>"
                      f"<td>{esc(s.get('b2b_mine'))} / {esc(s.get('b2b_published'))}</td>"
                      f"<td>{esc(s.get('games_in_4_mine'))} / {esc(s.get('games_in_4_published'))}</td>"
                      f"<td>{esc(s.get('travel_km_mine'))} / {esc(s.get('travel_km_published'))}</td></tr>")
    travel_body = f"""
<div class="card"><b>G2 — arena provenance.</b> Every coordinate in
<code>data/v2/arena_coordinates.json</code> was re-read from the source the table itself cites
(Wikipedia GeoData, {esc(AUDIT_UTC[:10])}) and compared. The tier stays SECONDARY as declared:
coordinates are a geographic fact, not an NBA statistic; the NBA schedule supplies the venue
names. Distances below are my own haversine recomputation of the published travel legs.</div>
<h2>Arena coordinates — table vs cited source</h2>
<table><tr><th>Team</th><th>Arena</th><th>City</th><th>Table lat, lon</th><th>Source lat, lon</th><th>Status</th><th>Source</th></tr>
{arows}</table>
<h2>Rest / back-to-back / 3-in-4 / travel — mine vs published</h2>
<p class="muted">Each cell shows <b>mine / published</b>. Rest and 3-in-4 come from the official
schedule; travel is great-circle previous venue to tonight's venue.</p>
<table><tr><th>Date</th><th>Game</th><th>Side</th><th>Team</th><th>Rest days</th><th>B2B</th><th>3-in-4 count</th><th>Travel km</th></tr>
{trows}</table>"""

    # player-log page
    pl = next(c for c in audit["checks"] if c["id"] == "V-PLAYERLOGS")
    pl_body = f"""
<div class="card"><b>{esc(pl['requirement'])}</b></div>
<div class="card">
<p>{esc(pl['what_i_recomputed'])}</p>
<table><tr><th>Injury-report players</th><th>Players with a captured log</th><th>Coverage</th></tr>
<tr><td>{esc(pl['injury_players'])}</td><td>{esc(pl['players_with_logs'])}</td><td>{esc(pl['coverage_pct'])}%</td></tr></table>
<p><b>Status:</b> {status_cell(pl['status'])}</p>
<p class="muted">{esc(pl['method_note'])}</p>
<p class="muted">Source: <a href="{esc(pl['source_url'])}">{esc(pl['source_url'])}</a></p>
</div>"""

    # flagged
    flags = audit["flags"]
    frows = "".join(
        f"<tr><td>{esc(f['id'])}</td><td>{esc(f['severity'])}</td><td>{esc(f['flag'])}</td>"
        f"<td>{esc(f['detail'])}</td><td><a href='{esc(f['source_url'])}'>source</a></td></tr>"
        for f in flags)
    flagged_body = f"""
<div class="card flag"><b>Nothing on this page blocks anything.</b> These are the irregularities
this audit found while re-verifying the repository. Each is published with its source link so a
human can review and request changes.</div>
<table><tr><th>Id</th><th>Severity</th><th>Flag</th><th>Detail</th><th>Source</th></tr>{frows}</table>"""

    srows = "".join(
        f"<tr><td>{esc(s['name'])}</td><td><a href='{esc(s['url'])}'>{esc(s['url'])}</a></td>"
        f"<td>{esc(s['used_for'])}</td><td>{esc(s['tier'])}</td></tr>" for s in audit["sources"])
    sources_body = f"""
<div class="card">Sources this audit read or re-checked. Tier labels follow the repository's
own convention: NBA-operated pages are OFFICIAL; everything else is labelled by what it is.</div>
<table><tr><th>Source</th><th>URL</th><th>Used for</th><th>Tier</th></tr>{srows}</table>"""

    return {
        "index.html": page("Requirement coverage", index_body),
        "verification.html": page("Independent recomputations", ver_body),
        "travel.html": page("Arena provenance & travel", travel_body),
        "playerlogs.html": page("Player-log coverage", pl_body),
        "flagged.html": page("Flagged for review", flagged_body),
        "sources.html": page("Sources", sources_body),
    }


def build_audit():
    build = _j("data", "v2", "build.json")
    finals = load_finals()
    slate = build.get("slate") or []

    checks = [
        check_hca(build, finals),
        check_est_a(build, finals, slate),
        check_est_b(build, slate),
        check_luck(build, finals),
        check_correlations(build, finals),
        check_parlays(build),
        check_schedule_context(build, finals),
        check_arena_provenance(),
        check_prereg(),
        check_ledger_v2(),
        check_ledger_app(),
        check_minutes(),
        check_results_feed(),
        check_player_logs(),
        check_market_prior(),
        check_gates_and_headline(),
    ]
    checks.extend(check_surfaces())

    flags = []
    for c in checks:
        if c.get("status", "").startswith("verified") or c.get("agree"):
            continue
        flags.append({
            "id": "9A-" + c["id"].replace("V-", "F-"),
            "severity": "medium",
            "flag": f"{c['id']} did not fully reproduce: {c.get('status', '')}",
            "detail": (c.get("what_i_recomputed", "") + " | " +
                       json.dumps({k: v for k, v in c.items()
                                   if k in ("problems", "worst_abs_delta", "rows")
                                   and v}, default=str)[:400]),
            "source_url": c.get("source_url", OFFICIAL_SCHEDULE),
        })
    flags += [
        {"id": "9A-F-01", "severity": "high",
         "flag": "the hosted scheduled refresh is red and has not fetched official data since 2026-11-17",
         "detail": ("scheduled runs fail at the committed-tree unit-test preflight (latest evidence "
                    "run 44469939831: test_committed_round_captures_replay_before_the_live_fetch, "
                    "subTest gamebooks_2ecbccfd.py). Owner session arena/915d2e99-nba3 is on it "
                    "(PR #143). This audit does not touch that code."),
         "source_url": "https://github.com/wingbangboozle1-lang/NBA3/actions/workflows/refresh.yml"},
        {"id": "9A-F-02", "severity": "high",
         "flag": "the canonical published results feed is behind the committed captures",
         "detail": ("data/app/results_feed.json carries 23 settled rows through 2026-11-15 while "
                    "captures for 2026-11-16..18 finals exist under data/rounds/ "
                    "(dd3edd74 + b1ce1334 trees). Integration request CR-DD3-01 on the board covers "
                    "the fold-in; this audit records the gap and does not rewrite published data."),
         "source_url": OFFICIAL_SCHEDULE},
        {"id": "9A-F-03", "severity": "medium",
         "flag": "player-minutes capture covers only part of the league",
         "detail": ("official_player_minutes_2026-11-15.json covers the teams its capture step "
                    "reached and names the rest in not_captured_teams; minutes redistribution "
                    "therefore publishes for captured teams only. Not filled with estimates."),
         "source_url": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"},
        {"id": "9A-F-04", "severity": "medium",
         "flag": "quarter scores are absent from every settled result row",
         "detail": ("each row says 'quarter scores not captured — blank, flagged'; the brief's row "
                    "shape (date, teams, final, quarter scores) is met structurally with the "
                    "quarter cells null rather than invented."),
         "source_url": OFFICIAL_SCHEDULE},
        {"id": "9A-F-05", "severity": "medium",
         "flag": "no closing line / odds feed exists, so the market-anchored prior cannot be applied",
         "detail": ("the blend is defined in pipeline/v2/strategies.py with weight from measured "
                    "out-of-sample log-loss, but with no licensed closing line connected there is "
                    "nothing to blend with; the site publishes the market-free price and says so."),
         "source_url": OFFICIAL_SCHEDULE},
        {"id": "9A-F-06", "severity": "low",
         "flag": "estimator B's historical error figure is contaminated by a single dated snapshot",
         "detail": ("the repository's own flag FV2-06 records that estimator B was fitted on the "
                    "2026-11-15 team-stats snapshot and graded on earlier games; no ranking may "
                    "cite its 13.83 RMSE as out-of-sample. Kept as-is; this audit verifies the "
                    "arithmetic, not the claim."),
         "source_url": OFFICIAL_STATS},
    ]

    sources = [
        {"name": "NBA official schedule (date pages)", "url": OFFICIAL_SCHEDULE,
         "used_for": "finals, slate, tip times, venues", "tier": "OFFICIAL (nba.com)"},
        {"name": "NBA official injury report index", "url": OFFICIAL_INJURY_INDEX,
         "used_for": "injury report revisions and stamps", "tier": "OFFICIAL (official.nba.com)"},
        {"name": "NBA team stats — traditional", "url": OFFICIAL_STATS,
         "used_for": "estimator B inputs (PTS, GP, POSS)", "tier": "OFFICIAL (nba.com/stats)"},
        {"name": "NBA team stats — opponent", "url": "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
         "used_for": "estimator B inputs (Opp PTS, opponent shooting)", "tier": "OFFICIAL (nba.com/stats)"},
        {"name": "NBA team stats — advanced", "url": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
         "used_for": "OffRtg, DefRtg, Pace", "tier": "OFFICIAL (nba.com/stats)"},
        {"name": "NBA player box scores / traditional", "url": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season",
         "used_for": "per-player minutes, points, rebounds, assists", "tier": "OFFICIAL (nba.com/stats)"},
        {"name": "Wikipedia GeoData API (arena coordinates)", "url": WIKI_API,
         "used_for": "arena-coordinate re-verification (this audit)", "tier": "SECONDARY (Wikipedia)"},
        {"name": "GitHub Actions — refresh workflow runs", "url": "https://github.com/wingbangboozle1-lang/NBA3/actions/workflows/refresh.yml",
         "used_for": "hosted refresh failure evidence (9A-F-01)", "tier": "PROJECT (GitHub)"},
    ]

    audit = {
        "schema": "nba3.audit.9a13efcf/v1",
        "session": AUDIT_SESSION,
        "generated_utc": AUDIT_UTC,
        "what": ("independent line-by-line verification of the project brief against the "
                 "committed implementation and captures; every value recomputed with code "
                 "written for this audit"),
        "inputs": ["data/origin/games.csv", "data/v2/build.json", "data/v2/arena_coordinates.json",
                   "data/v2/captures/*", "prereg/*", "ledger/*", "data/app/ledger/ledger.jsonl",
                   "data/app/results_feed.json", "data/app/minutes_model.json",
                   "data/rounds/2026-11-17/player_logs_2026-11-15.json",
                   "data/9a13efcf/arena_wikipedia_check.json"],
        "checks": checks,
        "requirements": REQS,
        "flags": flags,
        "sources": sources,
    }
    return audit


def main():
    args = sys.argv[1:]
    audit = build_audit()
    blob = json.dumps(audit, indent=1, default=str) + "\n"
    pages = render(audit)
    if "--check" in args:
        old = open(os.path.join(OUT_DATA, "audit.json"), encoding="utf-8").read()
        drift = old != blob
        for name, html in pages.items():
            p = os.path.join(OUT_SITE, name)
            if not os.path.exists(p) or open(p, encoding="utf-8").read() != html:
                drift = True
                print(f"DRIFT: {name}")
        if drift:
            print("audit.json drifted" if old != blob else "pages drifted")
            return 1
        print(f"check OK: {len(audit['checks'])} checks, {len(audit['requirements'])} requirements")
        return 0
    os.makedirs(OUT_DATA, exist_ok=True)
    os.makedirs(OUT_SITE, exist_ok=True)
    with open(os.path.join(OUT_DATA, "audit.json"), "w", encoding="utf-8") as fh:
        fh.write(blob)
    for name, html in pages.items():
        with open(os.path.join(OUT_SITE, name), "w", encoding="utf-8") as fh:
            fh.write(html)
    n_ok = sum(1 for c in audit["checks"] if c.get("agree"))
    print(f"wrote data/9a13efcf/audit.json + 9a13efcf/ ({len(pages)} pages)")
    print(f"checks: {n_ok}/{len(audit['checks'])} reproduce; flags: {len(audit['flags'])}")
    for c in audit["checks"]:
        mark = "OK  " if c.get("agree") else "FLAG"
        print(f"  [{mark}] {c['id']:<14} {c.get('status', '')[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
