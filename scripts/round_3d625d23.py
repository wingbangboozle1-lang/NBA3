#!/usr/bin/env python3
"""Session arena/3d625d23-nba3 — originated lines for the rolling slate.

Pure standard library, deterministic, offline: everything is computed from committed
official captures, so the CI drift gate catches any real change.

Model shape (brief, in order)

* Two INDEPENDENT estimators, never blended into a single headline number:
    E1  "results log"     — ratings fitted to the official game log (margins + totals).
    E2  "efficiency page" — possessions x points-per-possession from the official team
                            advanced page (+ the official standings).
  The published headline is their DISAGREEMENT; the blend is printed underneath, never above.
* Home-court advantage is PINNED to the measured home-win rate of the official log
  (HCA = sigma * probit(home_win_rate)); it is never fitted as a free parameter.
* Luck: per-team z-score of actual wins against expected wins; a strategy may not lean on a
  team outside the +-1.96 noise band.
* Parlays are priced with the measured rho and the naive product is printed next to them.
* A closing line is not connected, so the market-anchored blend stays BLANK and flagged.

Outputs: data/slate/model.json, data/slate/picks.json, data/slate/parlays.json,
         data/slate/prior.json, data/slate/luck.json
"""
import json
import math
import os
import re
from datetime import date, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "slate")
SLATE_UTC = "2026-11-15T23-50Z"          # newest official source read in this round
WARMUP = 60                              # games before walk-forward scoring starts
SHRINK_K = 6.0                           # prior weight (in games) for the rating/total shrinkage
SHRINK_GRID = (0.0, 6.0, 12.0, 20.0)     # published sensitivity, see the flagged note
MIN_OOS_FOR_WEIGHT = 30                  # pre-registered: an estimator needs this many
NOISE_BAND = 1.96                        # luck z-score band

SCHED_URL = "https://www.nba.com/schedule?date=2026-11-16"
ADV_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
STAND_URL = "https://www.nba.com/standings"
INJ_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_30PM.pdf"
LOG_SOURCES = ["data/origin/games.csv (official results capture, 188 games)",
               "data/live/results/settled_2026-11-14.json (5 finals, official game books)",
               "data/slate/results_feed.json (11/15 IND@PHI, official game book)"]


def pkey(name):
    """(surname, first initial) key that matches 'Maxey, Tyrese' to '0 Tyrese Maxey'."""
    if not name:
        return None
    n = re.sub(r"^\d+\s+", "", name.strip())
    if "," in n:
        last, first = [x.strip().lower() for x in n.split(",", 1)]
    else:
        parts = n.lower().split()
        if len(parts) < 2:
            return None
        first, last = parts[0], parts[-1]
    return (last, first[:1])


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
        fh.write("\n")


# --------------------------------------------------------------------------- statistics helpers

def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probit(p):
    """Inverse normal CDF (Acklam's rational approximation, |error| < 1.15e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError(p)
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


def solve(matrix, rhs):
    """Gaussian elimination with partial pivoting."""
    n = len(matrix)
    m = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("singular")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    out = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = m[r][n] - sum(m[r][c] * out[c] for c in range(r + 1, n))
        out[r] = s / m[r][r]
    return out


def ols(X, y, ridge=1e-6):
    """Least squares with a tiny ridge; returns coefficients."""
    k = len(X[0])
    a = [[sum(X[i][p] * X[i][q] for i in range(len(X))) + (ridge if p == q else 0.0)
          for q in range(k)] for p in range(k)]
    b = [sum(X[i][p] * y[i] for i in range(len(X))) for p in range(k)]
    return solve(a, b)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def bvn(h, k, r):
    """P(X<h, Y<k) for standard bivariate normal with correlation r (Simpson, 2000 steps)."""
    if abs(r) < 1e-9:
        return phi(h) * phi(k)
    lo, hi, steps = -8.0, h, 2000
    if hi <= lo:
        return 0.0
    step = (hi - lo) / steps
    total = 0.0
    sr = math.sqrt(1 - r * r)
    for i in range(steps + 1):
        x = lo + i * step
        w = 1 if i in (0, steps) else (4 if i % 2 else 2)
        total += w * math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi) * \
            phi((k - r * x) / sr)
    return total * step / 3.0


# --------------------------------------------------------------------------- the official log

def load_log(feed):
    games = []
    for g in feed["games"]:
        if g.get("verified") and g.get("away_final") is not None:
            games.append({"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                          "home": g["home"], "away_pts": g["away_final"],
                          "home_pts": g["home_final"]})
    with open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8") as fh:
        import csv
        for r in csv.DictReader(fh):
            games.append({"date": r["date"], "game_id": r["game_id"], "away": r["away"],
                          "home": r["home"], "away_pts": int(r["away_pts"]),
                          "home_pts": int(r["home_pts"])})
    seen, out = set(), []
    for g in sorted(games, key=lambda x: (x["date"], x["game_id"])):
        if g["game_id"] in seen:
            continue
        seen.add(g["game_id"])
        out.append(g)
    return out


# --------------------------------------------------------------------------- E1: results log

def fit_e1(games, hca, k=SHRINK_K):
    """Margin ratings (sum-to-zero) + a symmetric team 'game environment' total model.

    Both parameter sets are shrunk toward zero by n_i / (n_i + k), where n_i is the club's games
    in the fitting sample and k is a prior weight expressed in games. The shrink constant is
    fixed before scoring (it is NOT tuned on the out-of-sample games); the sensitivity to it is
    published in the model artefact.
    """
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
    played = {t: 0 for t in teams}
    for g in games:
        played[g["home"]] += 1
        played[g["away"]] += 1
    idx = {t: i for i, t in enumerate(teams)}
    X, y = [], []
    for g in games:
        row = [0.0] * (len(teams) - 1)
        for t, sign in ((g["home"], 1.0), (g["away"], -1.0)):
            j = idx[t]
            if j < len(teams) - 1:
                row[j] += sign
            else:                                   # last team = -(sum of the others)
                for jj in range(len(teams) - 1):
                    row[jj] -= sign
        X.append(row)
        y.append(g["home_pts"] - g["away_pts"] - hca)
    coef = ols(X, y)
    rating = {t: (coef[idx[t]] if idx[t] < len(teams) - 1
                  else -sum(coef)) for t in teams}
    mean = sum(rating.values()) / len(rating)
    rating = {t: (v - mean) * played[t] / (played[t] + k) for t, v in rating.items()}

    # totals: total = mu + s_home + s_away, symmetric, sum-to-zero
    Xt = [[1.0] + [0.0] * (len(teams) - 1) for _ in games]
    yt = []
    for i, g in enumerate(games):
        for t in (g["home"], g["away"]):
            j = idx[t]
            if j < len(teams) - 1:
                Xt[i][j + 1] += 1.0
            else:
                for jj in range(len(teams) - 1):
                    Xt[i][jj + 1] -= 1.0
        yt.append(g["home_pts"] + g["away_pts"])
    ct = ols(Xt, yt)
    mu = ct[0]
    env = {t: (ct[idx[t] + 1] if idx[t] < len(teams) - 1 else -sum(ct[1:])) for t in teams}
    m = sum(env.values()) / len(env)
    env = {t: (v - m) * played[t] / (played[t] + k) for t, v in env.items()}
    return {"rating": rating, "mu_total": mu, "env": env, "teams": teams}


def e1_predict(fit, away, home, hca):
    margin = fit["rating"].get(home, 0.0) - fit["rating"].get(away, 0.0) + hca
    total = fit["mu_total"] + fit["env"].get(home, 0.0) + fit["env"].get(away, 0.0)
    return margin, total


# --------------------------------------------------------------------------- E2: efficiency page

def e2_model(advanced):
    rows = advanced["rows"]
    tot_pts = sum(r["off_rtg"] / 100.0 * r["poss"] for r in rows)
    tot_poss = sum(r["poss"] for r in rows)
    league_ppp = tot_pts / tot_poss
    adv = {r["team"]: r for r in rows}
    return {"league_ppp": league_ppp, "league_ppp_per_100": league_ppp * 100,
            "adv": adv, "tot_poss": tot_poss, "tot_pts": tot_pts}


def e2_predict(model, away, home, hca):
    a = model["adv"]
    if home not in a or away not in a:
        return None, None, None
    lg = model["league_ppp_per_100"]
    poss = (a[home]["pace"] + a[away]["pace"]) / 2.0
    home_ppp = (a[home]["off_rtg"] / 100.0) * (a[away]["def_rtg"] / 100.0) / (lg / 100.0)
    away_ppp = (a[away]["off_rtg"] / 100.0) * (a[home]["def_rtg"] / 100.0) / (lg / 100.0)
    home_pts = poss * home_ppp
    away_pts = poss * away_ppp
    return home_pts - away_pts + hca, home_pts + away_pts, poss


# --------------------------------------------------------------------------- main

def main():
    feed = load("results_feed.json")
    advanced = load("team_advanced.json")
    standings = load("standings.json")
    slate = load("slate.json")
    travel = load("travel.json")
    minutes = load("minutes.json")
    injury = load("injuries/injury_2026-11-15_0630PM.json")

    games = load_log(feed)

    # ---- HCA pinned to the measured home-win rate -------------------------------------
    home_wins = sum(1 for g in games if g["home_pts"] > g["away_pts"])
    home_rate = home_wins / len(games)
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    sigma = math.sqrt(sum((m - sum(margins) / len(margins)) ** 2 for m in margins) /
                      (len(margins) - 1))
    hca = sigma * probit(home_rate)
    hca_doc = {
        "rule": "HCA is pinned to the measured home-win rate, never fitted: "
                "HCA = sigma x probit(home_win_rate), where sigma is the standard deviation of "
                "the game margin (home - away) over the official log.",
        "home_wins": home_wins, "games": len(games), "home_win_rate": round(home_rate, 4),
        "margin_sigma_pts": round(sigma, 3),
        "hca_points": round(hca, 3),
        "sources": LOG_SOURCES,
    }

    # ---- walk-forward, E1 only (E2 has no historical snapshot in this repository) ------
    oos = []
    for i in range(WARMUP, len(games)):
        g = games[i]
        fit = fit_e1(games[:i], hca)
        margin, total = e1_predict(fit, g["away"], g["home"], hca)
        resid = [games[j]["home_pts"] - games[j]["away_pts"]
                 - e1_predict(fit, games[j]["away"], games[j]["home"], hca)[0]
                 for j in range(i)]
        sig = math.sqrt(sum(r * r for r in resid) / max(1, len(resid)))
        p = min(0.99, max(0.01, phi(margin / sig)))
        win = 1 if g["home_pts"] > g["away_pts"] else 0
        oos.append({"game_id": g["game_id"], "date": g["date"], "p_home": p, "win": win,
                    "margin": margin, "actual_margin": g["home_pts"] - g["away_pts"],
                    "total": total, "actual_total": g["home_pts"] + g["away_pts"]})
    n_oos = len(oos)
    ll_e1 = -sum(math.log(o["p_home"] if o["win"] else 1 - o["p_home"]) for o in oos) / n_oos
    acc_e1 = sum(1 for o in oos if (o["p_home"] > 0.5) == bool(o["win"])) / n_oos
    mae_margin = sum(abs(o["margin"] - o["actual_margin"]) for o in oos) / n_oos
    mae_total = sum(abs(o["total"] - o["actual_total"]) for o in oos) / n_oos

    # ---- sensitivity of E1 to the shrink constant (published, not tuned) -----------------
    sens = []
    for k in SHRINK_GRID:
        rows = []
        for i in range(WARMUP, len(games)):
            g = games[i]
            f = fit_e1(games[:i], hca, k)
            m, t = e1_predict(f, g["away"], g["home"], hca)
            resid = [games[j]["home_pts"] - games[j]["away_pts"]
                     - e1_predict(f, games[j]["away"], games[j]["home"], hca)[0]
                     for j in range(i)]
            sg = math.sqrt(sum(r * r for r in resid) / max(1, len(resid)))
            p = min(0.99, max(0.01, phi(m / sg)))
            rows.append((p, 1 if g["home_pts"] > g["away_pts"] else 0, m,
                         g["home_pts"] - g["away_pts"], t, g["home_pts"] + g["away_pts"]))
        sens.append({"shrink_k": k,
                     "log_loss": round(-sum(math.log(p if w else 1 - p)
                                            for p, w, *_ in rows) / len(rows), 4),
                     "accuracy": round(sum(1 for p, w, *_ in rows if (p > 0.5) == bool(w))
                                       / len(rows), 4),
                     "mae_margin": round(sum(abs(m - a) for _, _, m, a, _, _ in rows)
                                         / len(rows), 2),
                     "mae_total": round(sum(abs(t - at) for *_, t, at in rows) / len(rows), 2)})

    # ---- E2 out-of-sample: only games settled after the efficiency page was read -------
    e2_model_ = e2_model(advanced)
    page_gp = {r["team"]: r["gp"] for r in advanced["rows"]}
    e2_oos = []
    for g in feed["games"]:
        if not g.get("verified") or g["date"] <= "2026-11-14":
            continue
        m2, t2, poss = e2_predict(e2_model_, g["away"], g["home"], hca)
        if m2 is None:
            continue
        p2 = min(0.99, max(0.01, phi(m2 / sigma)))
        win = 1 if g["home_final"] > g["away_final"] else 0
        e2_oos.append({"game_id": g["game_id"], "date": g["date"], "p_home": p2, "win": win,
                       "margin": m2, "actual_margin": g["home_final"] - g["away_final"],
                       "total": t2, "actual_total": g["home_final"] + g["away_final"]})
    ll_e2 = (-sum(math.log(o["p_home"] if o["win"] else 1 - o["p_home"]) for o in e2_oos)
             / len(e2_oos)) if e2_oos else None
    acc_e2 = (sum(1 for o in e2_oos if (o["p_home"] > 0.5) == bool(o["win"])) / len(e2_oos)
              if e2_oos else None)

    # ---- blend weights from measured OOS log-loss (pre-registered minimum sample) ------
    def weight(ll, n):
        if ll is None or n < MIN_OOS_FOR_WEIGHT:
            return 0.0
        return math.exp(-ll)

    w1, w2 = weight(ll_e1, n_oos), weight(ll_e2, len(e2_oos))
    if w1 + w2 == 0:
        w1, w2 = 1.0, 0.0
    w1, w2 = w1 / (w1 + w2), w2 / (w1 + w2)
    blend_doc = {
        "rule": f"w_i = exp(-logloss_i) normalised; an estimator receives weight only once it "
                f"has at least {MIN_OOS_FOR_WEIGHT} out-of-sample games. Until then the measured "
                f"estimator carries the blend and the weights are published with the sample sizes.",
        "w_E1": round(w1, 4), "w_E2": round(w2, 4),
        "n_oos_E1": n_oos, "n_oos_E2": len(e2_oos),
        "logloss_E1": round(ll_e1, 4), "logloss_E2": None if ll_e2 is None else round(ll_e2, 4),
        "blend_is_measured": False,
        "note": "E2's weight is 0 because the official efficiency page is a single current "
                "snapshot: it has produced one out-of-sample game so far. The blend therefore "
                "equals E1 today and the published headline is the disagreement, not the blend.",
    }

    # ---- fit on everything, then project the rolling window ---------------------------
    fit_all = fit_e1(games, hca)
    projections = []
    travel_by_gid = {r["game_id"]: r for r in travel["rows"]}
    for g in slate["upcoming"]:
        m1, t1 = e1_predict(fit_all, g["away"], g["home"], hca)
        m2, t2, poss = e2_predict(e2_model_, g["away"], g["home"], hca)
        p1 = phi(m1 / sigma)
        p2 = phi(m2 / sigma) if m2 is not None else None
        blend_margin = w1 * m1 + w2 * (m2 if m2 is not None else m1)
        blend_total = w1 * t1 + w2 * (t2 if t2 is not None else t1)
        tr = travel_by_gid.get(g["game_id"], {})
        rotations = {}
        for side in ("away", "home"):
            team = g[side]
            mins = minutes["teams"].get(team)
            rows = [r for r in injury["rows"] if r["team"] == team and r["player"]]
            out_keys = {pkey(r["player"]) for r in rows if r["status"] == "Out"}
            ques_keys = {pkey(r["player"]) for r in rows if r["status"] == "Questionable"}
            if not mins:
                rotations[side] = {"team": team, "available": None,
                                   "minutes_at_risk": None, "out_in_top8": None,
                                   "note": "no captured game book for this club — rotation "
                                           "minutes are blank, not inferred"}
                continue
            top8 = mins["top8"]
            out_hits = [p for p in top8 if pkey(p["player"]) in out_keys]
            rotations[side] = {
                "team": team, "game": mins["game"], "source": mins["source"],
                "top8_size": len(top8),
                "out_in_top8": [p["player"] for p in out_hits],
                "minutes_at_risk": round(sum(p["minutes"] for p in out_hits), 1),
                "share_at_risk": round(sum(p["share_of_team_minutes"] for p in out_hits), 4),
                "questionable_in_top8": [p["player"] for p in top8
                                         if pkey(p["player"]) in ques_keys],
                "note": "minutes from the most recent captured official game book for the club",
            }
        projections.append({
            "date": g["date"], "game_id": g["game_id"], "away": g["away"], "home": g["home"],
            "tip_et": g["tip_et"], "venue": g.get("arena"), "city": g.get("city"),
            "E1_margin": round(m1, 2), "E2_margin": None if m2 is None else round(m2, 2),
            "disagreement_pts": None if m2 is None else round(abs(m1 - m2), 2),
            "blend_margin": round(blend_margin, 2),
            "E1_total": round(t1, 2), "E2_total": None if t2 is None else round(t2, 2),
            "total_disagreement": None if t2 is None else round(abs(t1 - t2), 2),
            "blend_total": round(blend_total, 2),
            "possessions": None if poss is None else round(poss, 2),
            "p_home_E1": round(p1, 4),
            "p_home_E2": None if p2 is None else round(p2, 4),
            "p_disagreement": None if p2 is None else round(abs(p1 - p2), 4),
            "rest_travel": {k: tr.get(k) for k in
                            ("away_rest_days", "away_b2b", "away_games_in_4d",
                             "away_travel_mi", "home_rest_days", "home_b2b",
                             "home_games_in_4d", "home_travel_mi")},
            "rotation": rotations,
            "sources": {"slate": SCHED_URL, "efficiency": ADV_URL, "standings": STAND_URL,
                        "injury": INJ_URL, "game": g["game_url"]},
        })
    projections.sort(key=lambda p: (p["date"], p["game_id"]))

    # ---- luck: z-score of actual vs expected wins --------------------------------------
    exp_w, exp_v, act_w = {}, {}, {}
    for o in oos:
        g = next(x for x in games if x["game_id"] == o["game_id"])
        for team, p in ((g["home"], o["p_home"]), (g["away"], 1 - o["p_home"])):
            exp_w[team] = exp_w.get(team, 0.0) + p
            exp_v[team] = exp_v.get(team, 0.0) + p * (1 - p)
    for o in oos:
        g = next(x for x in games if x["game_id"] == o["game_id"])
        winner = g["home"] if g["home_pts"] > g["away_pts"] else g["away"]
        act_w[winner] = act_w.get(winner, 0) + 1
    luck = []
    for team in sorted(exp_w):
        n = round(exp_v[team] / 0.25) if exp_v[team] else 0     # ~games, from the variance sum
        sd = math.sqrt(exp_v[team]) if exp_v[team] > 0 else None
        z = ((act_w.get(team, 0) - exp_w[team]) / sd) if sd else None
        luck.append({"team": team, "expected_wins": round(exp_w[team], 2),
                     "actual_wins": act_w.get(team, 0), "var_sum": round(exp_v[team], 3),
                     "z": None if z is None else round(z, 3),
                     "outside_noise_band": bool(z is not None and abs(z) > NOISE_BAND)})
    luck_doc = {"schema": "nba3.slate.luck/v1", "session": "arena/3d625d23-nba3",
                "rule": "z = (actual wins - expected wins) / sqrt(sum p(1-p)) over the "
                        "walk-forward out-of-sample games, where p is E1's pre-game probability "
                        "for that club. |z| > 1.96 means the club's record is outside the noise "
                        "band: a strategy may not lean on it.",
                "oos_games": n_oos, "teams": luck,
                "outside_band": [l["team"] for l in luck if l["outside_noise_band"]]}

    # ---- measured correlations (rho) ---------------------------------------------------
    rho_margin_total = pearson([g["home_pts"] - g["away_pts"] for g in games],
                               [g["home_pts"] + g["away_pts"] for g in games])
    rho_team_totals = pearson([g["home_pts"] for g in games], [g["away_pts"] for g in games])
    sigma_total = math.sqrt(sum((o["total"] - o["actual_total"]) ** 2 for o in oos) / len(oos))

    # cross-game rho: home-win indicators of two games on the same date with no shared club
    by_date = {}
    for g in games:
        by_date.setdefault(g["date"], []).append(g)
    pair_x, pair_y = [], []
    for d, gs in by_date.items():
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                a, b = gs[i], gs[j]
                if {a["home"], a["away"]} & {b["home"], b["away"]}:
                    continue
                pair_x.append(1 if a["home_pts"] > a["away_pts"] else 0)
                pair_y.append(1 if b["home_pts"] > b["away_pts"] else 0)
    rho_cross = pearson(pair_x, pair_y)
    corr_doc = {
        "schema": "nba3.slate.correlations/v1", "session": "arena/3d625d23-nba3",
        "note": "Pearson r over the official game log (n = %d games). These are the "
                "correlations this round can measure from official data; the cells the brief "
                "asks for that need a settled line feed are left blank." % len(games),
        "n": len(games),
        "rows": [
            {"pair": "game margin (home - away) vs game total", "r": None if rho_margin_total
             is None else round(rho_margin_total, 4), "n": len(games), "basis": "MEASURED",
             "use": "rho for a same-game spread+total parlay"},
            {"pair": "home team points vs away team points", "r": None if rho_team_totals
             is None else round(rho_team_totals, 4), "n": len(games), "basis": "MEASURED",
             "use": "rho for a same-game over/over parlay"},
            {"pair": "home-win indicator, two different games on the same date, no shared club",
             "r": None if rho_cross is None else round(rho_cross, 4), "n": len(pair_x),
             "basis": "MEASURED",
             "use": "rho for a cross-game parlay"},
            {"pair": "player prop vs team side", "r": None, "n": 0, "basis": "NOT MEASURED",
             "use": "left blank: no prop line feed and no per-player prop results"},
        ],
        "sigma_margin_pts": round(sigma, 3), "sigma_total_pts": round(sigma_total, 3),
        "sources": LOG_SOURCES,
    }

    # ---- parlays: measured rho price + naive product ------------------------------------
    ALT_SPREAD = 5.0        # alt line: home covers our spread by 5 or more
    ALT_TOTAL = 8.0         # alt line: total finishes 8 or more above our total
    p_spread_alt = phi(-ALT_SPREAD / sigma)
    p_total_alt = phi(-ALT_TOTAL / sigma_total)
    rho_same = rho_margin_total or 0.0
    rho_x = rho_cross or 0.0
    parlays = []
    for pr in projections:
        joint = bvn(probit(min(0.99, max(0.01, p_spread_alt))),
                    probit(min(0.99, max(0.01, p_total_alt))), rho_same)
        naive = p_spread_alt * p_total_alt
        parlays.append({
            "kind": "same-game alt lines", "date": pr["date"], "game_id": pr["game_id"],
            "matchup": f"{pr['away']}@{pr['home']}",
            "legs": [f"home covers our originated spread by {ALT_SPREAD:.0f}+",
                     f"total finishes {ALT_TOTAL:.0f}+ over our originated total"],
            "p_leg1": round(p_spread_alt, 4), "p_leg2": round(p_total_alt, 4),
            "rho": round(rho_same, 4), "rho_n": len(games),
            "naive_product": round(naive, 4), "rho_priced": round(joint, 4),
            "difference": round(joint - naive, 4),
            "fair_price_naive": round(1 / naive, 3), "fair_price_rho": round(1 / joint, 3),
            "note": "both legs are alt lines on OUR originated numbers, so each leg's price is "
                    "the same in every game; what changes with the game is nothing, and what "
                    "matters is the joint price under the measured rho versus the naive product, "
                    "which is printed beside it.",
        })
    # cross-game: the two strongest sides in the window, priced with the measured cross-game rho
    strongest = sorted(projections, key=lambda x: -abs(x["p_home_E1"] - 0.5))[:2]
    if len(strongest) == 2:
        legs = []
        for pr in strongest:
            fav = pr["home"] if pr["p_home_E1"] >= 0.5 else pr["away"]
            legs.append({"matchup": f"{pr['away']}@{pr['home']}", "date": pr["date"],
                         "side": fav, "p": pr["p_home_E1"] if fav == pr["home"]
                         else round(1 - pr["p_home_E1"], 4)})
        joint = bvn(probit(min(0.99, max(0.01, legs[0]["p"]))),
                    probit(min(0.99, max(0.01, legs[1]["p"]))), rho_x)
        naive = legs[0]["p"] * legs[1]["p"]
        parlays.append({
            "kind": "cross-game moneylines", "date": "window", "game_id": None,
            "matchup": " + ".join(l["matchup"] for l in legs),
            "legs": [f"{l['side']} wins ({l['matchup']}, {l['date']})" for l in legs],
            "p_leg1": legs[0]["p"], "p_leg2": legs[1]["p"],
            "rho": round(rho_x, 4), "rho_n": len(pair_x),
            "naive_product": round(naive, 4), "rho_priced": round(joint, 4),
            "difference": round(joint - naive, 4),
            "fair_price_naive": round(1 / naive, 3), "fair_price_rho": round(1 / joint, 3),
            "note": "the two largest originated edges in the window, priced with the measured "
                    "cross-game rho; the naive product is printed beside it.",
        })
    parlay_doc = {"schema": "nba3.slate.parlays/v1", "session": "arena/3d625d23-nba3",
                  "rule": "joint price from a Gaussian copula with the measured rho; the naive "
                          "product is always printed beside it, never withheld",
                  "rho_same_game": round(rho_same, 4), "rho_cross_game": round(rho_x, 4),
                  "sigma_margin_pts": round(sigma, 3), "sigma_total_pts": round(sigma_total, 3),
                  "alt_spread": ALT_SPREAD, "alt_total": ALT_TOTAL,
                  "count": len(parlays), "rows": parlays}

    # ---- market-anchored prior: no licensed closing line --------------------------------
    prior_doc = {
        "schema": "nba3.slate.market_prior/v1", "session": "arena/3d625d23-nba3",
        "feed_status": "not connected",
        "formula": "blended = w*model + (1-w)*closing, "
                   "w = exp(-LL_model) / (exp(-LL_model) + exp(-LL_closing))",
        "w_model": round(w1, 4), "w_closing": None,
        "logloss_model": round(ll_e1, 4), "logloss_closing": None,
        "rows": [],
        "note": "No licensed closing-line feed is connected in this environment, so every blended "
                "line is BLANK and flagged; the model line is published alone and the weight is "
                "computed from the model side only.",
    }

    model = {
        "schema": "nba3.slate.model/v1",
        "session": "arena/3d625d23-nba3",
        "generated_utc": SLATE_UTC,
        "generated_from": "the newest official source read in this round (never a wall clock)",
        "hca": hca_doc,
        "log": {"games": len(games), "first": games[0]["date"], "last": games[-1]["date"],
                "sources": LOG_SOURCES},
        "estimators": {
            "E1": {"name": "results log", "inputs": "official game log (margins and totals)",
                   "fitting": "least-squares ratings on game margin with HCA pinned; a symmetric "
                              "team 'environment' term for the total",
                   "oos": {"n": n_oos, "log_loss": round(ll_e1, 4), "accuracy": round(acc_e1, 4),
                           "mae_margin": round(mae_margin, 3), "mae_total": round(mae_total, 3),
                           "baseline_log_loss": round(math.log(2), 4),
                           "walk_forward": f"fit on all earlier games, score game "
                                           f"{WARMUP + 1} onward",
                           "shrink_k": SHRINK_K,
                           "shrink_sensitivity": sens,
                           "shrink_note": "the shrink constant is fixed before scoring; the grid "
                                          "is published so the choice can be inspected. Selecting "
                                          "the constant by looking at these four rows would be "
                                          "selection, so the figure above should be read as "
                                          "slightly optimistic."}},
            "E2": {"name": "efficiency page",
                   "inputs": "official team advanced page (OffRtg, DefRtg, Pace) + official "
                             "standings",
                   "fitting": "total = possessions x points-per-possession; "
                              "ppp = OffRtg/100 x DefRtg_opp/100 / (league ppp), "
                              "possessions = mean pace of the two clubs",
                   "league_ppp": round(e2_model_["league_ppp"], 4),
                   "oos": {"n": len(e2_oos),
                           "log_loss": None if ll_e2 is None else round(ll_e2, 4),
                           "accuracy": None if acc_e2 is None else round(acc_e2, 4),
                           "note": "only games settled after the page was read can score E2 out "
                                   "of sample; one so far, which is far too few to weight it"}},
        },
        "blend": blend_doc,
        "headline": "disagreement",
        "headline_rule": "the headline number on every projection row is |E1 - E2| (points and "
                         "win probability). The blend is printed underneath it and is never the "
                         "headline.",
        "projections": projections,
        "luck": luck_doc,
        "correlations": corr_doc,
    }
    write_json(os.path.join(OUT, "model.json"), model)
    write_json(os.path.join(OUT, "luck.json"), luck_doc)
    write_json(os.path.join(OUT, "parlays.json"), parlay_doc)
    write_json(os.path.join(OUT, "prior.json"), prior_doc)

    print(f"log games            {len(games)}  ({games[0]['date']}..{games[-1]['date']})")
    print(f"home win rate        {home_rate:.4f}  sigma {sigma:.3f}  HCA pinned {hca:.3f}")
    print(f"E1 OOS               n={n_oos} logloss {ll_e1:.4f} acc {acc_e1:.4f} "
          f"(coin {math.log(2):.4f}) mae margin {mae_margin:.2f} total {mae_total:.2f}")
    print(f"E2 OOS               n={len(e2_oos)} "
          f"{'logloss %.4f' % ll_e2 if ll_e2 is not None else '(not enough games to score)'}")
    print(f"blend weights        E1 {w1:.3f} / E2 {w2:.3f}")
    print(f"projections          {len(projections)} games "
          f"{slate['window']['from']}..{slate['window']['to']}")
    print(f"luck outside band    {luck_doc['outside_band']}")
    print(f"parlays priced       {len(parlays)}  rho same-game {rho_same:.4f} "
          f"cross-game {rho_x:.4f}")


if __name__ == "__main__":
    main()
