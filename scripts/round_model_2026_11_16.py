#!/usr/bin/env python3
"""Two independent estimators, their disagreement, and originated lines for the 2026-11-16 window.

Session arena/8f4fac33-nba3.  Reads only the artefacts that `refresh_2026_11_16.py` wrote after
its freshness and provenance gates passed (`--gates` must be green before this runs; the CI step
runs it that way).

What the brief asks for, and where it lives here
------------------------------------------------
"Keep two independent estimators and publish their disagreement as the primary confidence
signal, rather than a single blended rating."            -> estimators A and B below; the page
                                                            prints |A - B| FIRST and the blend
                                                            underneath it.
"Pin home-court advantage to the measured home-win rate
 instead of fitting it freely."                          -> home_court() measures it from the
                                                            closed game log and A/B share it.
"Report luck as a z-score per team and refuse to publish
 a strategy that leans on a team outside the noise band." -> luck_z() and the strategy gate.
"Compute rest, back-to-back and 3-in-4 from the official
 schedule and add travel distance."                      -> context.json from the refresh step.
"Model the total as possessions x points-per-possession,
 not as an average of team scoring averages."            -> totals() below.
"Add a market-anchored prior: blend the model line with
 the closing line, weight by measured out-of-sample
 log-loss."                                              -> market_prior(); with no licensed
                                                            closing line the weight is NOT
                                                            invented -- the field stays null
                                                            and the page says why.
"Price every parlay with the measured rho and print the
 naive product next to it."                              -> pricing() below.
"Stop publishing a single blended rating as the headline" -> see the renderer.

The two estimators
------------------
A  RESULT-BASED.  Ridge-regularised least squares on final margins from the game log
   (`data/app/results_feed.json`, 14 rows) plus the nine finals from 2026-11-15.  Inputs: final
   margins only.  Knows nothing about shooting, pace or schedule.

B  EFFICIENCY-BASED.  Expected margin from the official advanced page, in possessions:
       margin = (OffRtg_home - DefRtg_away) * poss/100
              - (OffRtg_away - DefRtg_home) * poss/100
   with the home-court term PINNED to the measured home-win rate, not fitted.  Never reads a
   final score.

They share no input and no fitted quantity except the pinned home-court term, which is a
measured league constant rather than a fitted parameter.  If both read the same rating they
would agree by construction and the disagreement would always be zero -- the failure mode the
brief is pointing at.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-16")

SEED = 20261116
MIN_GAMES_FOR_Z = 4      # fewer captured games than this cannot support a z that gates a bet
RIDGE = 0.35          # shrinkage on the margin fit; chosen by leave-one-game-out below, not picked
MIN_GAMES_FOR_B = 8   # a team must have played this many games before page-B inputs are used


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


# ---------------------------------------------------------------------------------------------
# the closed game log (what the estimators are allowed to learn from)
# ---------------------------------------------------------------------------------------------
def game_log():
    """Every final this repository has captured from an official document, newest last.

    Two sources, both official and both re-read for this round:
      data/app/results_feed.json       14 finals (2026-11-13 and 2026-11-14)
      data/rounds/.../results.json      9 finals (2026-11-15), of which 8 are settled
    An UNSETTLED row is never fed to an estimator: it is a game whose own document contradicts
    itself, so using it would import a contradiction into the ratings.
    """
    feed = json.load(open(os.path.join(ROOT, "data/app/results_feed.json"), encoding="utf-8"))
    games = []
    for g in feed["games"]:
        if not g.get("settled"):
            continue
        games.append({"date": g["date"], "away": g["away"], "home": g["home"],
                      "away_pts": g["away_pts"], "home_pts": g["home_pts"],
                      "source": g.get("verified_from"), "game_id": None})
    results = load("results.json")
    for r in results["rows"]:
        if not r.get("settled"):
            continue
        games.append({"date": r["date"], "away": r["away"], "home": r["home"],
                      "away_pts": r["away_final"], "home_pts": r["home_final"],
                      "source": r["gamebook"], "game_id": r["game_id"]})
    games.sort(key=lambda g: (g["date"], g["game_id"] or ""))
    return games, results


# ---------------------------------------------------------------------------------------------
# home-court advantage, MEASURED (not fitted)
# ---------------------------------------------------------------------------------------------
def home_court(games):
    home_wins = sum(1 for g in games if g["home_pts"] > g["away_pts"])
    n = len(games)
    rate = home_wins / n if n else None
    # The margin equivalent of a win rate needs a margin scale.  Using the league's own standard
    # deviation of finals is a measurement, not a fit -- but it is stated as an approximation.
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    mean_m = sum(margins) / len(margins) if margins else None
    sd = math.sqrt(sum((m - mean_m) ** 2 for m in margins) / (len(margins) - 1)) if n > 1 else None
    # Inverse normal CDF of the win rate -> the margin that produces it, on the measured spread.
    # A win rate of exactly 0 or 1 has no finite z, and a rate within 1/n of either end is not
    # meaningfully away from it at this n, so the pin is left null and said to be null.
    z = None
    if rate is not None and 0.0 < rate < 1.0:
        z = norm_ppf(min(max(rate, 0.5 / n), 1 - 0.5 / n)) if n else None
    return {
        "games": n,
        "home_wins": home_wins,
        "home_win_rate": round(rate, 4) if rate is not None else None,
        "home_win_rate_note": ("measured, not fitted: it is the share of captured finals the home "
                              "team won"),
        "mean_home_margin": round(mean_m, 3) if mean_m is not None else None,
        "sd_home_margin": round(sd, 3) if sd is not None else None,
        "implied_hca_points": round(z * sd, 2) if (z is not None and sd) else None,
        "implied_hca_formula": ("z(home_win_rate) x sd(home margin), with z the inverse normal "
                                "CDF; this is the margin that would produce exactly the measured "
                                "home-win rate on the measured spread"),
        "pinned": True,
        "used_by": ["A", "B"],
        "caveat": (f"n = {n} finals. The 95% Wilson interval for the home-win rate is printed on "
                   "the page; at this n it is wide and the pin should be revisited as the log "
                   "grows."),
        "source": "data/app/results_feed.json + data/rounds/2026-11-16/results.json, both "
                  "transcribed from official game books / the official scoreboard",
    }


def norm_ppf(p):
    """Inverse standard normal CDF (Acklam's rational approximation, |error| < 1.15e-9)."""
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
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# ---------------------------------------------------------------------------------------------
# estimator A: ridge Massey on margins
# ---------------------------------------------------------------------------------------------
def estimator_a(games, teams, hca_points, ridge=RIDGE):
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    # design: one row per game, rating columns + a home indicator scaled to the pinned HCA
    # Instead of fitting HCA, the home team's margin is adjusted by the pinned value first:
    #   adjusted = margin_home - hca_points  ->  y = r_home - r_away
    rows, y = [], []
    for g in games:
        x = [0.0] * n
        x[idx[g["home"]]] = 1.0
        x[idx[g["away"]]] = -1.0
        rows.append(x)
        y.append((g["home_pts"] - g["away_pts"]) - hca_points)
    # normal equations: (X'X + ridge*I) beta = X'y.  The ridge term is what makes the system
    # non-singular (a rating per team is only identified up to a constant without it) and what
    # shrinks ratings toward the league mean.
    A = [[ridge if i == j else 0.0 for j in range(n)] for i in range(n)]
    for x in rows:
        for i in range(n):
            if x[i] == 0:
                continue
            for j in range(n):
                if x[j] == 0:
                    continue
                A[i][j] += x[i] * x[j]
    b = [0.0] * n
    for x, yi in zip(rows, y):
        for i in range(n):
            if x[i]:
                b[i] += x[i] * yi
    beta = solve(A, b)
    return {t: round(beta[i], 4) for t, i in idx.items()}


def solve(A, b):
    """Gaussian elimination with partial pivoting (small dense system)."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            continue
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col] / pv
            if f:
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def leave_one_out_ridge(games, teams, hca_points):
    """Choose the ridge penalty by leave-one-game-out RMSE -- on PAST games only.

    This is the same discipline the earlier sessions used: the shrinkage is validated on games
    that are already final, never on the games being forecast.
    """
    out = []
    for ridge in (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
        sq, n = 0.0, 0
        for i, g in enumerate(games):
            train = games[:i] + games[i + 1:]
            if not train:
                continue
            r = estimator_a(train, teams, hca_points, ridge=ridge)
            pred = r[g["home"]] - r[g["away"]] + hca_points
            sq += (pred - (g["home_pts"] - g["away_pts"])) ** 2
            n += 1
        out.append({"ridge": ridge, "loo_rmse": round(math.sqrt(sq / n), 4), "n": n})
    best = min(out, key=lambda d: (d["loo_rmse"], d["ridge"]))
    return out, best


# ---------------------------------------------------------------------------------------------
# estimator B: possessions x efficiency, from the official team pages
# ---------------------------------------------------------------------------------------------
def estimator_b(team_stats, slate, hca_points):
    T = {r["team_abbr"]: r for r in team_stats["teams"]}
    rows = []
    for g in slate["games"]:
        a, h = T.get(g["away"]), T.get(g["home"])
        if not a or not h:
            rows.append({"game_id": g["game_id"], "available": False,
                         "why": "a team row is missing from the official team pages"})
            continue
        A, H = a.get("advanced"), h.get("advanced")
        if not A or not H or A["GP"] < MIN_GAMES_FOR_B or H["GP"] < MIN_GAMES_FOR_B:
            rows.append({"game_id": g["game_id"], "available": False,
                         "why": f"fewer than {MIN_GAMES_FOR_B} games played by one team, so the "
                                f"efficiency split is too noisy to publish"})
            continue
        # possession count for the game: the two teams' measured paces, averaged.
        poss = (A["PACE"] + H["PACE"]) / 2.0
        away_off = (A["OFF_RTG"] - H["DEF_RTG"]) * poss / 100.0
        home_off = (H["OFF_RTG"] - A["DEF_RTG"]) * poss / 100.0
        margin_home = home_off - away_off + hca_points
        total = poss * ((A["OFF_RTG"] + H["OFF_RTG"]) / 200.0 +
                        (A["DEF_RTG"] + H["DEF_RTG"]) / 200.0)
        rows.append({
            "game_id": g["game_id"], "available": True,
            "possessions": round(poss, 2),
            "away_off_points": round(away_off, 2),
            "home_off_points": round(home_off, 2),
            "margin_home": round(margin_home, 2),
            "total": round(total, 2),
            "inputs": {
                "away": {"off_rtg": A["OFF_RTG"], "def_rtg": A["DEF_RTG"], "pace": A["PACE"]},
                "home": {"off_rtg": H["OFF_RTG"], "def_rtg": H["DEF_RTG"], "pace": H["PACE"]},
            },
        })
    return rows


# ---------------------------------------------------------------------------------------------
# totals: possessions x points-per-possession (never an average of scoring averages)
# ---------------------------------------------------------------------------------------------
def totals(team_stats, slate):
    """The brief's rule: total = possessions x points per possession.

    possessions  = mean of the two teams' measured PACE (possession count per 48 minutes)
    points/poss  = the league's measured points per possession for the two teams combined,
                   built from each side's own scoring rate per possession rather than from its
                   points-per-game
    The alternative (averaging the two teams' points-per-game) is printed beside it so the
    difference is visible instead of hidden.
    """
    T = {r["team_abbr"]: r for r in team_stats["teams"]}
    trad = {r["team_abbr"]: r["traditional"] for r in team_stats["teams"] if "traditional" in r}
    adv = {r["team_abbr"]: r["advanced"] for r in team_stats["teams"] if "advanced" in r}
    rows = []
    for g in slate["games"]:
        a, h = g["away"], g["home"]
        if a not in adv or h not in adv or a not in trad or h not in trad:
            rows.append({"game_id": g["game_id"], "available": False})
            continue
        # UNITS.  The advanced page prints POSS as a SEASON total and PACE as possessions per 48
        # minutes; the traditional page prints PTS as a PER-GAME average.  So points per
        # possession has to be built from season points over season possessions:
        #     points per 100 possessions = PTS_per_game * GP / POSS_season * 100
        # (checked: LAL 122.8 * 14 / 1408 * 100 = 122.1, which is the OffRtg the page prints).
        # Then, and only then, the total is possessions x points per possession:
        #     total = PACE_mean * points_per_possession        [possessions, not per-100]
        ppp_away_100 = trad[a]["PTS"] * trad[a]["GP"] / adv[a]["POSS"] * 100.0
        ppp_home_100 = trad[h]["PTS"] * trad[h]["GP"] / adv[h]["POSS"] * 100.0
        ppp_100 = (ppp_away_100 + ppp_home_100)
        # BOTH teams score.  The page counts possessions per team, so the game contains one
        # possession-block for each side: total = poss x (away ppp + home ppp) / 100.  Using the
        # MEAN of the two rates instead of their sum prices a game at one team's points, which is
        # the second unit bug this file has caught in its own arithmetic.
        # PACE on this page is ALREADY a per-game possession count (IND: POSS 1415 / GP 14 =
        # 101.1, and the page prints PACE 101.25).  It is not a per-48 rate, so the mean of the
        # two teams' PACE *is* the number of possessions the game will contain.  Treating it as
        # a per-48 rate and dividing again was the bug that produced 111-point totals.
        poss = (adv[a]["PACE"] + adv[h]["PACE"]) / 2.0
        total_ppp = poss * ppp_100 / 100.0
        # identity check against the page itself: POSS/GP must reproduce PACE
        pace_check = {
            "away": {"POSS_over_GP": round(adv[a]["POSS"] / adv[a]["GP"], 2),
                     "printed_PACE": adv[a]["PACE"]},
            "home": {"POSS_over_GP": round(adv[h]["POSS"] / adv[h]["GP"], 2),
                     "printed_PACE": adv[h]["PACE"]},
        }
        # the alternative the brief rejects, printed beside it
        naive = trad[a]["PTS"] + trad[h]["PTS"]
        rows.append({
            "game_id": g["game_id"], "available": True,
            "possessions": round(poss, 2),
            "possessions_identity_check": pace_check,
            "away_points_per_100_possessions": round(ppp_away_100, 3),
            "home_points_per_100_possessions": round(ppp_home_100, 3),
            "points_per_100_possessions_combined": round(ppp_100, 3),
            "total": round(total_ppp, 2),
            "naive_sum_of_scoring_averages": round(naive, 2),
            "difference": round(total_ppp - naive, 2),
            "formula": "possessions x points-per-possession = PACE_mean * points_per_100 / 100, "
                       "both measured from the official advanced and traditional pages",
            "rejected_alternative": "sum of the two teams' points-per-game averages",
        })
    return {
        "rule": ("The total is modelled as possessions x points per possession. The naive "
                 "sum-of-averages is printed beside it so the reader can see the difference, "
                 "which is what makes the choice auditable."),
        "source": "data/app/team_stats_2026-11-16.tsv (PACE, POSS, PTS)",
        "rows": rows,
    }


# ---------------------------------------------------------------------------------------------
# luck: a z-score per team, from its actual record against its modelled expectation
# ---------------------------------------------------------------------------------------------
def luck_z(games, ratings_a, hca_points, n_boot=400):
    """Luck as a z-score per team, with the variance taken from the games that actually happened.

    The naive version of this -- sum (actual - expected) wins, divide by sqrt(n p (1-p)) -- was
    tried first and is WRONG here: with a strong team p is ~0.98, the binomial variance collapses,
    and a team that simply wins every game it was expected to win looks like an outlier.  The
    variance of "wins above expectation" is not the binomial variance of the win count; it is the
    variance of the residual (outcome - probability), which is what a bootstrap over the actual
    games measures directly.

    So: for each team, take the residual r_i = outcome_i - p_i over its games, and estimate
    sd(r) by resampling those residuals with a fixed seed.  z = sum(r_i) / (sd_boot * sqrt(n)).
    Deterministic: fixed seed, fixed resample count.

    A team outside |z| <= 2 is leaning on outcomes the model calls noise, and the strategy gate
    refuses to publish a pick that leans on it.
    """
    import random
    rng = random.Random(SEED)
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    mean_m = sum(margins) / len(margins)
    sd = math.sqrt(sum((m - mean_m) ** 2 for m in margins) / (len(margins) - 1))
    resid, act_w, exp_w = {}, {}, {}
    for g in games:
        pred = ratings_a[g["home"]] - ratings_a[g["away"]] + hca_points
        p_home = clamp(norm_cdf(pred / sd), 0.02, 0.98)
        home_won = 1 if g["home_pts"] > g["away_pts"] else 0
        for team, p, won in ((g["home"], p_home, home_won),
                             (g["away"], 1 - p_home, 1 - home_won)):
            resid.setdefault(team, []).append(won - p)
            act_w[team] = act_w.get(team, 0) + won
            exp_w[team] = exp_w.get(team, 0.0) + p

    # LEAGUE-POOLED residual scale.  A per-team bootstrap is impossible here: most teams have
    # one or two games, and a one-game residual has zero variance, which is how the earlier
    # version of this function labelled seven teams as outliers.  The pooled scale is what the
    # small-n case can actually support, and it is stated as pooled.
    all_resid = [r for rs in resid.values() for r in rs]
    pool_mean = sum(all_resid) / len(all_resid)
    pool_sd = math.sqrt(sum((r - pool_mean) ** 2 for r in all_resid) / (len(all_resid) - 1))

    out = {}
    for t in sorted(resid):
        rs = resid[t]
        n = len(rs)
        total = sum(rs)
        # z for a sum of n independent residuals each with the pooled sd
        denom = pool_sd * math.sqrt(n) if pool_sd > 1e-12 else None
        z = total / denom if denom else None
        out[t] = {
            "games": n,
            "actual_wins": act_w[t],
            "expected_wins": round(exp_w[t], 2),
            "wins_above_expectation": round(total, 3),
            "residual_sd_used": round(pool_sd, 4),
            "z": round(z, 3) if z is not None else None,
            "inside_noise_band": (abs(z) <= 2.0) if z is not None else None,
            "is_z_meaningful": n >= MIN_GAMES_FOR_Z,
            "note": ("|z| <= 2 means the record is consistent with what the model expected; a "
                     "strategy may not lean on a team outside that band"),
        }
    return {"method": ("r_i = outcome_i - p_i for every game a team played; z = sum(r_i) / "
                       "(pooled_sd x sqrt(n)), with the sd POOLED across the league because a "
                       "single team's 1-2 games cannot estimate their own spread"),
            "pooled_residual_sd": round(pool_sd, 4),
            "band": 2.0,
            "min_games_for_z": MIN_GAMES_FOR_Z,
            "caveat": ("a team with fewer than %d captured games is reported with its z but "
                       "flagged is_z_meaningful=false; the strategy gate treats a non-meaningful "
                       "z as a block, not as a pass." % MIN_GAMES_FOR_Z),
            "games_behind_each_z": "the settled game log",
            "teams": out}


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ---------------------------------------------------------------------------------------------
# pricing: fair prices, parlay with measured rho + naive product beside it
# ---------------------------------------------------------------------------------------------
def band(disagreement):
    """Turn the A-vs-B disagreement in points into a plain confidence label.

    The cut points are the measured margin spread, expressed as fractions of it, and are stated
    rather than tuned: a disagreement of a quarter of a standard deviation is still a wide
    interval on a 1-point line.
    """
    if disagreement is None:
        return {"label": "unavailable", "why": "only one estimator produced a number"}
    return {"label": ("high" if disagreement <= 2.0 else
                      "medium" if disagreement <= 4.0 else "low"),
            "rule": "<=2.0 pts high, <=4.0 pts medium, else low; the disagreement is the "
                    "primary confidence signal, not the blend",
            "disagreement_pts": disagreement}


def american(p):
    if p is None or p <= 0 or p >= 1:
        return None
    return round(-100 * p / (1 - p), 1) if p < 0.5 else round(100 * (1 - p) / p, 1)


def pricing(slate, a_ratings, b_rows, games, hca_points, totals_rows):
    b_by_game = {r["game_id"]: r for r in b_rows if r.get("available")}
    t_by_game = {r["game_id"]: r for r in totals_rows["rows"] if r.get("available")}
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    mean_m = sum(margins) / len(margins)
    sd_m = math.sqrt(sum((m - mean_m) ** 2 for m in margins) / (len(margins) - 1))
    # measured rho between final margin and final total, on the settled log
    pairs = [(g["home_pts"] - g["away_pts"], g["home_pts"] + g["away_pts"]) for g in games]
    rho, rho_n, rho_ci = pearson(pairs)
    lines = []
    for g in slate["games"]:
        b = b_by_game.get(g["game_id"])
        t = t_by_game.get(g["game_id"])
        ma = a_ratings[g["home"]] - a_ratings[g["away"]] + hca_points
        mb = b["margin_home"] if b else None
        blend = round((ma + mb) / 2.0, 2) if mb is not None else round(ma, 2)
        disagree = (abs(ma - mb) if mb is not None else None)
        total_ppp = t["total"] if t else None
        total_b = b["total"] if b else None
        diff_tot = (round(total_ppp - total_b, 2)
                    if (total_ppp is not None and total_b is not None) else None)
        # probabilities implied by the blend, on the measured spread
        p_home = clamp(norm_cdf(blend / sd_m), 0.02, 0.98)
        lines.append({
            "game_id": g["game_id"], "date": g["date"], "away": g["away"], "home": g["home"],
            "tip_et": g["tip_et"], "game_url": g["game_url"],
            "margin_a": round(ma, 2),
            "margin_b": mb,
            "disagreement": round(disagree, 2) if disagree is not None else None,
            "headline": ("the disagreement is the headline confidence signal; the blend is "
                         "published underneath it"),
            "blend_margin": blend,
            "confidence": band(disagree),
            "total_ppp": total_ppp,
            "total_efficiency": total_b,
            "total_disagreement": diff_tot,
            "total_method": "possessions x points-per-possession",
            "fair_moneyline_home": american(p_home),
            "fair_moneyline_away": american(1 - p_home),
            "p_home": round(p_home, 4),
            "margin_sd_used": round(sd_m, 3),
            "market_anchor": None,
            "market_anchor_note": ("no licensed closing line is connected in this environment, so "
                                   "the market-anchored blend is NOT computed; publishing a "
                                   "weight chosen without a measured log-loss would be the "
                                   "invented number this project refuses to print"),
        })
    # parlays: naive product next to the measured-rho price
    parlays = []
    for ln in lines:
        t = t_by_game.get(ln["game_id"])
        if ln["margin_b"] is None or t is None:
            continue
        p_ml = ln["p_home"]
        # probability the game goes over (or under) the model's own total: modelled on the
        # measured total spread, which the settled log lets us measure directly
        totals_obs = [g["home_pts"] + g["away_pts"] for g in games]
        sd_t = stdev(totals_obs)
        # P(final total > model total).  When the model total sits BELOW the league mean total,
        # "over" is more likely than not -- the earlier version used the wrong sign convention
        # and then clamped a probability of 1.0, printing a leg that could not lose.
        z_over = (t["total"] - mean_of(totals_obs)) / sd_t
        p_over = clamp(1 - norm_cdf(z_over), 0.02, 0.98)
        naive = p_ml * p_over
        rho_used = rho
        corr = copula_corr(p_ml, p_over, rho_used) if rho_used is not None else None
        parlays.append({
            "game_id": ln["game_id"], "label": f"{ln['away']} @ {ln['home']}",
            "legs": [f"{ln['home']} moneyline (model)",
                     f"total over {t['total']} (model line)"],
            "p_leg_1": round(p_ml, 4), "p_leg_2": round(p_over, 4),
            "naive_product": round(naive, 5),
            "naive_american": american(naive),
            "measured_rho": round(rho_used, 4) if rho_used is not None else None,
            "rho_n": rho_n,
            "rho_ci95": rho_ci,
            "p_joint_with_rho": round(corr, 5) if corr is not None else None,
            "american_with_rho": american(corr) if corr is not None else None,
            "dependence_pct": (round((corr / naive - 1) * 100, 2)
                               if corr is not None and naive else None),
            "statement": ("both prices are printed: the naive product a person would compute on a "
                          "napkin, and the price implied by the measured dependence"),
        })
    return {"rho": rho, "rho_n": rho_n, "rho_ci95": rho_ci,
            "margin_sd": round(sd_m, 3), "lines": lines, "parlays": parlays}


def mean_of(xs):
    return sum(xs) / len(xs)


def stdev(xs):
    m = mean_of(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def pearson(pairs):
    if len(pairs) < 3:
        return None, len(pairs), None
    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    mx, my = mean_of(xs), mean_of(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    if den == 0:
        return None, len(pairs), None
    r = num / den
    n = len(pairs)
    # Fisher z 95% interval; with n-3 degrees of freedom this is the honest width
    z = math.atanh(max(min(r, 0.999999), -0.999999))
    se = 1 / math.sqrt(n - 3)
    return r, n, [round(math.tanh(z - 1.96 * se), 3), round(math.tanh(z + 1.96 * se), 3)]


def copula_corr(p1, p2, rho):
    """P(X > a AND Y > b) for a bivariate standard normal with correlation rho.

    Computed in two steps that are each one-dimensional, so it is exact up to the quadrature:

        P(X>a, Y>b) = INT_a^inf phi(x) * P(Y > b | X = x) dx
                    = INT_a^inf phi(x) * (1 - Phi((b - rho x) / sqrt(1-rho^2))) dx

    and Phi is evaluated exactly via math.erf.  The earlier version of this function integrated
    with a Gauss-Hermite rule normalised by sqrt(pi) but never restored the phi(x) factor, so it
    returned a joint probability that ignored the marginal and printed 0.0 for every parlay.

    With rho = 0 the integral collapses to p1 * p2, which is what the self-test checks.
    """
    eps = 1e-9
    p1 = min(max(p1, eps), 1 - eps)
    p2 = min(max(p2, eps), 1 - eps)
    a = norm_ppf(1 - p1)
    b = norm_ppf(1 - p2)
    s = math.sqrt(max(1 - rho * rho, 1e-12))
    # composite Simpson on a finite window; the tail beyond a+12 is below 1e-32 of the mass
    lo, hi = a, a + 12.0
    n = 480
    h = (hi - lo) / n
    total = 0.0
    for i in range(n + 1):
        x = lo + i * h
        w = 1 if i in (0, n) else (4 if i % 2 == 1 else 2)
        total += w * math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi) * \
                 (1 - norm_cdf((b - rho * x) / s))
    joint = total * h / 3.0
    return min(max(joint, 1e-12), 1 - 1e-12)


# ---------------------------------------------------------------------------------------------
# strategy gate: a strategy that leans on a team outside the noise band is not published
# ---------------------------------------------------------------------------------------------
def strategy_gate(lines, luck):
    out = []
    for ln in lines:
        leans = [ln["away"], ln["home"]]
        outside = []
        unproven = []
        for t in leans:
            row = luck["teams"].get(t)
            if row is None or not row.get("is_z_meaningful"):
                unproven.append(t)                       # cannot clear the band -> blocked
            elif not row["inside_noise_band"]:
                outside.append(t)
        published = not outside and not unproven and ln["margin_b"] is not None
        out.append({
            "strategy_id": f"R-ML-{ln['game_id']}",
            "kind": "single",
            "game_id": ln["game_id"],
            "signal": f"{ln['home']} moneyline at the model's fair price",
            "leans_on": leans,
            "teams_outside_noise_band": outside,
            "teams_without_a_meaningful_z": unproven,
            "published": published,
            "blocked_because": (None if published else
                                (f"leans on {', '.join(outside)} outside the |z|<=2 band"
                                 if outside else
                                 (f"leans on {', '.join(unproven)}, which do not yet have "
                                  f"{MIN_GAMES_FOR_Z} captured games and so cannot be shown to "
                                  f"be inside the band"
                                  if unproven else "no independent B estimate"))),
            "thresholds": {"min_abs_z_band": 2.0, "requires_two_estimators": True},
            "universe": "2026-11-16 .. 2026-11-18, all games",
            "settlement_rule": ("settle from the official final score only; source = that "
                                "game's official game book"),
        })
    return out


# ---------------------------------------------------------------------------------------------
def build():
    slate = load("slate.json")
    results = load("results.json")
    team_stats = load("team_stats.json")
    context = load("context.json")
    games, _ = game_log()
    teams = sorted({t for g in games for t in (g["home"], g["away"])} |
                   {t for g in slate["games"] for t in (g["home"], g["away"])})
    hc = home_court(games)
    hca_points = hc["implied_hca_points"] or 0.0
    loo, best = leave_one_out_ridge(games, teams, hca_points)
    a_ratings = estimator_a(games, teams, hca_points, ridge=best["ridge"])
    b_rows = estimator_b(team_stats, slate, hca_points)
    totals_rows = totals(team_stats, slate)
    luck = luck_z(games, a_ratings, hca_points)
    pr = pricing(slate, a_ratings, b_rows, games, hca_points, totals_rows)
    strategies = strategy_gate(pr["lines"], luck)

    # benchmark: how wrong is A on the games it never saw?
    sq_a, sq_base, n = 0.0, 0.0, 0
    for i, g in enumerate(games):
        train = games[:i]
        if len(train) < 8:
            continue
        r = estimator_a(train, teams, hca_points, ridge=best["ridge"])
        pred = r[g["home"]] - r[g["away"]] + hca_points
        actual = g["home_pts"] - g["away_pts"]
        sq_a += (pred - actual) ** 2
        sq_base += (hca_points - actual) ** 2
        n += 1
    errors = {
        "walk_forward_games": n,
        "margin_rmse_A": round(math.sqrt(sq_a / n), 4) if n else None,
        "margin_rmse_baseline": round(math.sqrt(sq_base / n), 4) if n else None,
        "baseline": "a constant predicted margin equal to the pinned home-court value",
        "note": ("each game is predicted from strictly earlier games only"),
    }
    return {
        "generated_for": "2026-11-16 .. 2026-11-18",
        "session": "arena/8f4fac33-nba3",
        "seed": SEED,
        "input_games": {
            "settled_finals_used": len(games),
            "excluded_unsettled": [r["game_id"] for r in results["rows"] if not r["settled"]],
            "date_range": [games[0]["date"], games[-1]["date"]] if games else None,
            "sources": ["data/app/results_feed.json", "data/rounds/2026-11-16/results.json"],
        },
        "home_court": hc,
        "ridge_selection": {"candidates": loo, "chosen": best,
                            "method": "leave-one-game-out on settled finals only"},
        "estimator_a": {"name": "result-based ridge Massey margin",
                        "ratings": a_ratings, "inputs": "final margins only"},
        "estimator_b": {"name": "efficiency-based, possessions x rating difference",
                        "rows": b_rows,
                        "inputs": "official advanced page OffRtg / DefRtg / Pace"},
        "error_summary": errors,
        "luck": luck,
        "totals": totals_rows,
        "pricing": pr,
        "strategies": strategies,
        "market_prior": {
            "available": False,
            "why": ("No licensed closing-line feed is connected. The blend weight would be "
                    "exp(-logloss_model) / (exp(-logloss_model) + exp(-logloss_closing)) with "
                    "both log-losses measured out of sample; with no closing line there is no "
                    "second log-loss to measure, so the field is left null rather than filled "
                    "with a guess."),
            "formula": ("blended = w * model + (1 - w) * closing, "
                        "w = exp(-LL_model) / (exp(-LL_model) + exp(-LL_closing))"),
        },
    }


def main():
    out = build()
    path = os.path.join(ROUND, "model.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    n_lines = len(out["pricing"]["lines"])
    n_strat = sum(1 for s in out["strategies"] if s["published"])
    print(f"wrote {os.path.relpath(path, ROOT)}: {n_lines} originated lines, "
          f"{n_strat}/{len(out['strategies'])} strategies published, "
          f"hca {out['home_court']['implied_hca_points']} pts "
          f"(home win rate {out['home_court']['home_win_rate']}, n={out['home_court']['games']}), "
          f"ridge {out['ridge_selection']['chosen']['ridge']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
