#!/usr/bin/env python3
"""Two independent estimators + their published disagreement (session arena/79341829-nba3).

Implements the required estimator policy on top of the verified official captures:

  * Estimator A — ridge margin model (Massey-style team strengths) fit on the official
    completed-game log (data/origin/games.csv + data/app/results_feed.json), with the
    home-court term PINNED to the measured home-win rate (never a free fit coefficient).
  * Estimator B — possession efficiency model from the three official team-stat pages
    captured 2026-11-15 (OffRtg / DefRtg / PACE): expected points = possessions x PPP.
  * The DISAGREEMENT between A and B is the headline; an equal-weight blend sits underneath.
  * Luck is published as a z-score per team (record vs the model's out-of-sample win
    probabilities). Teams outside |z| > 2 are outside the noise band; the bet surface
    refuses them (projection surface still publishes, flagged).
  * Parlays are priced with the MEASURED residual correlation rho; the naive product of
    the leg prices is printed beside every correlated price.
  * Market-anchored prior: the blended line is blank unless a closing-line feed is
    connected (data/app/closing_lines.json); the weight formula is printed.

Outputs: data/app/estimators.json
Usage:   python3 scripts/estimators.py
"""
import csv
import json
import math
import os
import sys
from datetime import date, datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

TEAM_STATS = os.path.join(APP, "official_team_stats_2026-11-15.json")
GAMES_CSV = os.path.join(ROOT, "data", "origin", "games.csv")
RESULTS_FEED = os.path.join(APP, "results_feed.json")
SLATE = os.path.join(APP, "official_slate_1115_1118.json")
ARENAS = os.path.join(APP, "arena_coordinates.json")
CLOSING = os.path.join(APP, "closing_lines.json")
OUT = os.path.join(APP, "estimators.json")

TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU",
         "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL",
         "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
IDX = {t: i for i, t in enumerate(TEAMS)}

SOURCES = {
    "results": "https://www.nba.com/games?date=2026-11-14",
    "results_1113": "https://www.nba.com/games?date=2026-11-13",
    "team_stats": ["https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
                   "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
                   "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"],
    "slate": "https://www.nba.com/games?date=2026-11-15",
    "gamebooks": [f"https://statsdmz.nba.com/pdfs/20261114/20261114_{ab}.pdf" for ab in
                  ("DENNOP", "DALCLE", "BKNMEM", "DETMIA", "CHIMIN")],
    "injury": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf",
}

# ------------------------------------------------------------------ small math helpers

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p):
    """Inverse normal CDF (Acklam's rational approximation; |error| < 1.15e-9)."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")
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


def solve_ridge(X, y, lam, skip_cols=0):
    """Solve (X'X + lam I) b = X'y for the penalised columns; unpenalised first columns."""
    n = len(X[0])
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for i in range(len(X)):
        xi, yi = X[i], y[i]
        for a in range(n):
            b[a] += xi[a] * yi
            for c in range(a, n):
                A[a][c] += xi[a] * xi[c]
    for a in range(n):
        for c in range(a):
            A[a][c] = A[c][a]
        if a >= skip_cols:
            A[a][a] += lam
    # gaussian elimination
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        b[i], b[piv] = b[piv], b[i]
        if abs(A[i][i]) < 1e-12:
            A[i][i] = 1e-12
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = b[i] - sum(A[i][c] * x[c] for c in range(i + 1, n))
        x[i] = s / A[i][i]
    return x


def bivar_prob(a, b_, rho):
    """P(X > a and Y > b) for standard bivariate normal with correlation rho,
    computed as int_a^inf phi(x) * Phi((b - rho x)/sqrt(1-rho^2)) dx (Simpson)."""
    if rho == 0:
        return (1 - norm_cdf(a)) * (1 - norm_cdf(b_))
    s = math.sqrt(max(1e-12, 1 - rho * rho))
    lo, hi = a, max(a + 10.0, 10.0)
    n = 200
    h = (hi - lo) / n
    tot = 0.0
    for i in range(n + 1):
        x = lo + i * h
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        phi = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
        tot += w * phi * norm_cdf((b_ - rho * x) / s)
    return max(0.0, min(1.0, tot * h / 3.0))


# ------------------------------------------------------------------ data loading

def load_completed():
    games = []
    with open(GAMES_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            games.append({"date": r["date"], "game_id": r["game_id"], "away": r["away"],
                          "home": r["home"], "away_pts": int(r["away_pts"]),
                          "home_pts": int(r["home_pts"]),
                          "source": "data/origin/games.csv (verified official finals)"})
    feed = json.load(open(RESULTS_FEED, encoding="utf-8"))
    for g in feed["games"]:
        if not g["verified"]:
            continue
        games.append({"date": g["date"], "game_id": f"{g['date']}_{g['away']}{g['home']}",
                      "away": g["away"], "home": g["home"],
                      "away_pts": g["away_pts"], "home_pts": g["home_pts"],
                      "source": g.get("verified_from") or SOURCES["results"]})
    # de-duplicate: the completed log may already contain games the results feed also carries
    seen = set()
    unique = []
    for g in games:
        key = (g["date"], g["away"], g["home"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(g)
    games = unique
    games.sort(key=lambda g: g["date"])
    for g in games:
        g["margin"] = g["home_pts"] - g["away_pts"]     # positive = home win
        g["total"] = g["home_pts"] + g["away_pts"]
    return games


def fit_margin_model(games, hca_pts, lam=30.0):
    """Ridge on (margin - hca): margin' = s_home - s_away, one strength per team (+1/-1
    design), no intercept, HCA never free (it is pinned upstream)."""
    n = len(TEAMS)
    X, y = [], []
    for g in games:
        xi = [0.0] * n
        xi[IDX[g["home"]]] = 1.0
        xi[IDX[g["away"]]] = -1.0
        X.append(xi)
        y.append(g["margin"] - hca_pts)
    coef = solve_ridge(X, y, lam, skip_cols=0)
    return {t: coef[i] for i, t in enumerate(TEAMS)}


def fit_total_model(games, lam=30.0):
    n = len(TEAMS)
    X, y = [], []
    for g in games:
        xi = [0.0] * n
        xi[IDX[g["home"]]] = 1.0
        xi[IDX[g["away"]]] = 1.0
        X.append(xi)
        y.append(g["total"])
    coef = solve_ridge(X, y, lam, skip_cols=0)
    return {t: coef[i] for i, t in enumerate(TEAMS)}


def margin_pred(r, g, hca):
    return r[g["home"]] - r[g["away"]] + hca


# ------------------------------------------------------------------ main

def main():
    now = "2026-11-15T11:47Z"  # = the team-stats capture stamp; deterministic for CI drift
    games = load_completed()

    # ---- home-court advantage: PINNED to the measured home-win rate of the official log
    home_wins = sum(1 for g in games if g["margin"] > 0)
    p_home = home_wins / len(games)
    margins = [g["margin"] for g in games]
    mu_m = sum(margins) / len(margins)
    sigma_margin = math.sqrt(sum((m - mu_m) ** 2 for m in margins) / (len(margins) - 1))
    hca_pts = norm_ppf(min(max(p_home, 0.01), 0.99)) * sigma_margin

    # ---- Estimator A: walk-forward OOS (expanding fit), true out-of-sample
    warmup = 45
    oos = []
    for t in range(warmup, len(games)):
        r = fit_margin_model(games[:t], hca_pts)
        g = games[t]
        m = margin_pred(r, g, hca_pts)
        resid = g["margin"] - m
        oos.append({**g, "pred_margin": round(m, 2), "resid": round(resid, 2)})
    logloss_a = 0.0
    hits_a = 0
    sigma_e = math.sqrt(sum(o["resid"] ** 2 for o in oos) / len(oos))
    for o in oos:
        p = norm_cdf(o["pred_margin"] / max(sigma_e, 1e-6))
        p = min(max(p, 1e-6), 1 - 1e-6)
        logloss_a += -(math.log(p) if o["margin"] > 0 else math.log(1 - p))
        if (o["pred_margin"] > 0) == (o["margin"] > 0):
            hits_a += 1
    logloss_a /= len(oos)

    # ---- Estimator B: possessions x PPP from the official three-page snapshot (in-sample
    # labelled; no historical stat snapshots are stored)
    ts = json.load(open(TEAM_STATS, encoding="utf-8"))
    cols = ts["pages"]["advanced"]["columns"]
    adv = {r[0]: dict(zip(cols, r)) for r in ts["pages"]["advanced"]["rows"]}
    lg_avg_drtg = sum(float(adv[t]["def_rtg"]) for t in TEAMS) / len(TEAMS)

    def eff_pair(home, away):
        poss = (float(adv[home]["pace"]) + float(adv[away]["pace"])) / 2.0
        eff_h = float(adv[home]["off_rtg"]) * float(adv[away]["def_rtg"]) / lg_avg_drtg
        eff_a = float(adv[away]["off_rtg"]) * float(adv[home]["def_rtg"]) / lg_avg_drtg
        return eff_h, eff_a, poss

    ll_b, hits_b, resids_b = 0.0, 0, []
    for g in games:
        eff_h, eff_a, poss = eff_pair(g["home"], g["away"])
        m_b = (eff_h - eff_a) * poss / 100.0 + hca_pts
        resid = g["margin"] - m_b
        resids_b.append(resid)
    sigma_b = math.sqrt(sum(x * x for x in resids_b) / len(resids_b))
    for g in games:
        eff_h, eff_a, poss = eff_pair(g["home"], g["away"])
        m_b = (eff_h - eff_a) * poss / 100.0 + hca_pts
        p = norm_cdf(m_b / max(sigma_b, 1e-6))
        p = min(max(p, 1e-6), 1 - 1e-6)
        ll_b += -(math.log(p) if g["margin"] > 0 else math.log(1 - p))
        if (m_b > 0) == (g["margin"] > 0):
            hits_b += 1
    ll_b /= len(games)

    # ---- final fits (all games) + measured rho between margin and total residuals
    r_final = fit_margin_model(games, hca_pts)
    t_final = fit_total_model(games)
    e_m, e_t = [], []
    for g in games:
        e_m.append(g["margin"] - margin_pred(r_final, g, hca_pts))
        e_t.append(g["total"] - (t_final[g["home"]] + t_final[g["away"]]))
    n_ = len(e_m)
    mm = sum(e_m) / n_
    mt = sum(e_t) / n_
    cov = sum((e_m[i] - mm) * (e_t[i] - mt) for i in range(n_)) / (n_ - 1)
    sd_m = math.sqrt(sum((x - mm) ** 2 for x in e_m) / (n_ - 1))
    sd_t = math.sqrt(sum((x - mt) ** 2 for x in e_t) / (n_ - 1))
    rho = cov / (sd_m * sd_t)

    # ---- luck z-scores per team (record vs OOS win probabilities)
    luck = {}
    for team in TEAMS:
        w, exp, n_t, exp_var = 0, 0.0, 0, 0.0
        close_w, close_n = 0, 0
        for o in oos:
            for side in ("home", "away"):
                if o[side] != team:
                    continue
                p_team = norm_cdf(o["pred_margin"] / max(sigma_e, 1e-6))
                if side == "away":
                    p_team = 1 - p_team
                won = (o["margin"] > 0) if side == "home" else (o["margin"] < 0)
                w += 1 if won else 0
                exp += p_team
                exp_var += p_team * (1 - p_team)
                n_t += 1
                if abs(o["margin"]) <= 5:
                    close_n += 1
                    close_w += 1 if won else 0
        if n_t:
            z = (w - exp) / math.sqrt(max(exp_var, 1e-9))
            luck[team] = {
                "team": team, "games_oos": n_t, "wins": w,
                "expected_wins": round(exp, 2),
                "luck_z": round(z, 2),
                "close_games": close_n, "close_wins": close_w,
                "outside_noise_band": abs(z) > 2.0,
                "source": "walk-forward predictions over data/origin/games.csv + data/app/results_feed.json",
            }

    # ---- window projections (the slate 11/15-11/18)
    slate_path = os.path.join(APP, "official_slate_current.json")
    if not os.path.exists(slate_path):
        slate_path = SLATE
    slate = json.load(open(slate_path, encoding="utf-8"))
    arenas = json.load(open(ARENAS, encoding="utf-8"))
    team_arena = {}
    for a in arenas["arenas"]:
        if a.get("team"):
            team_arena[a["team"]] = a

    def haversine(a, b):
        R = 6371.0088
        la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    # previous game per team from the completed log (for rest + travel)
    # arena/c94a5531-nba3 fix: look strictly before the row's own date. The old
    # 'last occurrence in the log' collapsed to the row's own game once that game
    # was completed and joined the log (rest 0, travel 0 km from its own arena).
    def last_before(team, game_date):
        prev = None
        for g in games:
            if g["date"] < game_date and team in (g["away"], g["home"]):
                prev = g
        return prev

    def rest_for(team, game_date):
        lg = last_before(team, game_date)
        if not lg:
            return {"days_rest": None, "b2b": None, "three_in_4": None,
                    "note": "no earlier game in the stored log"}
        d0 = date.fromisoformat(lg["date"])
        d1 = date.fromisoformat(game_date)
        gap = (d1 - d0).days
        # count games in the trailing 3 days
        three = sum(1 for g in games if g["date"] >= str(d1.fromordinal(d1.toordinal() - 3))
                    and g["date"] < game_date and team in (g["away"], g["home"]))
        return {"days_rest": gap, "b2b": gap == 1, "three_in_4": three >= 2,
                "last_game": lg["date"]}

    def travel_for(team, game_home, game_date):
        lg = last_before(team, game_date)
        cur = team_arena.get(game_home)
        if not lg or not cur:
            return {"km": None, "from_arena": None,
                    "flag": "arena coordinates missing for one endpoint (see arena_coordinates.json)"}
        prev_home = lg["home"]
        prev = team_arena.get(prev_home)
        if not prev or prev.get("lat") is None or cur.get("lat") is None:
            return {"km": None, "from_arena": prev.get("arena") if prev else None,
                    "flag": "arena coordinates missing for one endpoint (see arena_coordinates.json)"}
        return {"km": round(haversine(prev, cur), 1), "from_arena": prev["arena"],
                "method": "haversine on Wikipedia arena coordinates (reference source)"}

    window_rows = []
    for g in slate["games"]:
        away, home = g["away"], g["home"]
        eff_h, eff_a, poss = eff_pair(home, away)
        m_a = margin_pred(r_final, {"home": home, "away": away}, hca_pts)
        m_b = (eff_h - eff_a) * poss / 100.0 + hca_pts
        t_a = t_final[home] + t_final[away]
        t_b = (eff_h + eff_a) * poss / 100.0
        blend_m = 0.5 * (m_a + m_b)
        blend_t = 0.5 * (t_a + t_b)
        p_home_win = norm_cdf(blend_m / max(sigma_e, 1e-6))
        ra, ta = rest_for(away, g["date"]), rest_for(home, g["date"])
        window_rows.append({
            "game_id": g["game_id"], "date": g["date"], "tip_et": g["time_et"],
            "away": away, "home": home,
            "est_a_margin": round(m_a, 1), "est_b_margin": round(m_b, 1),
            "disagreement_abs": round(abs(m_a - m_b), 1),
            "blend_margin": round(blend_m, 1),           # secondary, never the headline
            "est_a_total": round(t_a, 1), "est_b_total": round(t_b, 1),
            "total_model": "possessions x PPP (est. B); ridge total (est. A)",
            "possessions": round(poss, 1),
            "blend_total": round(blend_t, 1),
            "home_win_prob": round(p_home_win, 3),
            "hca_points_pinned": round(hca_pts, 2),
            "rest": {"away": ra, "home": ta},
            "travel_km": {"away": travel_for(away, home, g["date"]), "home": travel_for(home, home, g["date"])},
            "luck_z": {"away": luck.get(away, {}).get("luck_z"), "home": luck.get(home, {}).get("luck_z")},
            "luck_band_flag": (f"{t} outside |z|>2 luck noise band"
                               for t in (away, home) if luck.get(t, {}).get("outside_noise_band")),
            "sources": [SOURCES["results"], SOURCES["team_stats"][2], SOURCES["slate"]],
        })
    for row in window_rows:
        row["luck_band_flag"] = list(row["luck_band_flag"])

    # ---- parlay pricing demo block (rho-aware vs naive) using the window's own lines
    parlay_rows = []
    for row in window_rows[:10]:
        s = row["blend_margin"]            # spread ~ 0 (pick 'em on our own line)
        tline = row["blend_total"]
        p_side = norm_cdf(row["blend_margin"] / max(sigma_e, 1e-6))
        p_over = norm_cdf((row["blend_total"] - tline) / max(sd_t, 1e-6))
        # joint price of "home side + over" under the measured rho of (margin, total) residuals
        a_ = -row["blend_margin"] / max(sigma_e, 1e-6)
        b_ = -(row["blend_total"] - tline) / max(sd_t, 1e-6)
        joint = bivar_prob(a_, b_, rho)
        naive = p_side * p_over
        parlay_rows.append({
            "game_id": row["game_id"], "legs": "home side + over (same game, our own lines)",
            "p_side": round(p_side, 4), "p_over": round(p_over, 4),
            "rho_measured": round(rho, 3),
            "joint_price_rho": round(joint, 4),
            "naive_product": round(naive, 4),
            "ratio_joint_over_naive": round(joint / naive, 3) if naive else None,
            "method": ("bivariate normal with rho = measured correlation of the ridge model's "
                       "margin and total residuals over the official completed-game log"),
        })

    # ---- market-anchored prior (closing-line feed)
    if not os.path.exists(CLOSING):
        with open(CLOSING, "w", encoding="utf-8") as fh:
            json.dump({
                "feed_status": "not connected",
                "note": ("No licensed closing-line feed is connected in this environment. "
                         "Blended lines stay BLANK and flagged; the model line is published alone."),
                "formula": ("blended = w * model + (1 - w) * closing, "
                            "w = exp(-logloss_model) / (exp(-logloss_model) + exp(-logloss_closing)), "
                            "log losses measured out-of-sample"),
                "rows": [],
            }, fh, indent=1)
            fh.write("\n")
    closing = json.load(open(CLOSING, encoding="utf-8"))

    out = {
        "generated_utc": now,
        "policy": {
            "headline": "the disagreement between the two independent estimators",
            "hca": ("pinned to the measured home-win rate of the official completed-game log; "
                    "never a free fit coefficient"),
            "luck": "z-score per team vs walk-forward win probabilities; |z|>2 refuses the bet surface",
            "totals": "possessions x points-per-possession (estimator B) beside the ridge total (A)",
            "parlays": "measured rho printed with every correlated price; naive product printed beside it",
            "market_prior": ("blank unless a closing-line feed is connected; weight formula printed "
                             "in data/app/closing_lines.json"),
            "disagreement_headline_mean": None,
        },
        "hca_measurement": {
            "home_wins": home_wins, "games": len(games), "home_win_rate": round(p_home, 4),
            "margin_sd": round(sigma_margin, 2),
            "hca_points_pinned": round(hca_pts, 2),
            "formula": "hca = Phi^-1(home-win rate) * SD(margin) over the official log",
            "sources": [SOURCES["results"], SOURCES["results_1113"], "data/origin/games.csv"],
        },
        "estimator_a": {
            "name": "ridge margin model (Massey-style), HCA pinned",
            "oos_log_loss": round(logloss_a, 4), "oos_accuracy": round(hits_a / len(oos), 3),
            "oos_games": len(oos),
            "oos_sample": ("expanding walk-forward over the official completed-game log "
                           "(games 1-45 warm-up; each later game predicted from games before it)"),
            "resid_sd": round(sigma_e, 2),
            "source": "data/origin/games.csv + data/app/results_feed.json (official finals)",
        },
        "estimator_b": {
            "name": "possession efficiency (possessions x PPP) from the three official pages",
            "log_loss_in_sample": round(ll_b, 4), "accuracy_in_sample": round(hits_b / len(games), 3),
            "resid_sd": round(sigma_b, 2),
            "label": ("IN-SAMPLE against the 2026-11-15 stat snapshot (no historical snapshots "
                      "are stored) — flagged, not presented as out-of-sample"),
            "sources": SOURCES["team_stats"],
        },
        "blend": {
            "weights": {"a": 0.5, "b": 0.5},
            "note": "the blend is published underneath the disagreement, never as the headline",
        },
        "rho_measured": round(rho, 3),
        "rho_note": ("correlation of the ridge model's margin and total residuals over the "
                     f"{n_}-game official log; used for every same-game parlay price"),
        "luck_band": luck,
        "window": window_rows,
        "parlay_prices": parlay_rows,
        "market_anchored_prior": {
            "feed_status": closing.get("feed_status"),
            "blended_lines": [],
            "flag": ("blank + unverified: no closing-line feed is connected, so no blended line "
                     "may be published"),
            "formula": closing.get("formula"),
        },
        "injury_input": {
            "report": "data/app/official_injuries_2026-11-15_0615AM.json",
            "source": SOURCES["injury"],
            "note": "status designations ride along with each window row via minutes_model.json",
        },
        "sources": [SOURCES["results"], SOURCES["results_1113"]] + SOURCES["team_stats"]
                   + [SOURCES["slate"], SOURCES["injury"]] + SOURCES["gamebooks"],
    }
    mean_dis = sum(r["disagreement_abs"] for r in window_rows) / len(window_rows)
    out["policy"]["disagreement_headline_mean"] = round(mean_dis, 1)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")

    print(f"completed games: {len(games)} | HCA pinned: {hca_pts:.2f} pts "
          f"(home-win rate {p_home:.3f}, margin SD {sigma_margin:.1f})")
    print(f"estimator A OOS: log-loss {logloss_a:.4f}, accuracy {hits_a/len(oos):.3f} on {len(oos)} games")
    print(f"estimator B (in-sample, labelled): log-loss {ll_b:.4f}, accuracy {hits_b/len(games):.3f}")
    print(f"rho measured: {rho:.3f} | window rows: {len(window_rows)} | mean disagreement {mean_dis:.1f} pts")
    outside = [t for t, v in luck.items() if v["outside_noise_band"]]
    print(f"luck |z|>2 teams (bet surface refuses): {outside or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
