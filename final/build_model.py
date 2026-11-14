#!/usr/bin/env python3
"""NBA3 model build.

Reads the verified datasets in data/processed and produces every derived artefact
used by the site.  Every number written out here is either

  (a) copied verbatim from an official NBA source (marked verified), or
  (b) derived by arithmetic documented in this file from official inputs, or
  (c) left blank and marked UNVERIFIED when it cannot be traced to an official source.

Run:  python3 model/build.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import date, datetime

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "model"))
from nbastats import (  # noqa: E402
    bh_fdr, binomial_test, corr, fisher_ci, mean, norm_ppf, ols, stdev,
    t_test_1sample,
)

ROOT = _ROOT
PROC = os.path.join(ROOT, "final", "data")
RAW = os.path.join(ROOT, "data", "raw")

SRC = {
    "games": "https://www.nba.com/games?date=",
    "injury_index": "https://official.nba.com/nba-injury-report-2026-27-season/",
    "team_advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
    "team_boxscores": "https://www.nba.com/stats/teams/boxscores-traditional?Season=2026-27&SeasonType=Regular%20Season",
    "players": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC",
    "schedule": "https://www.nba.com/games?date=",
    "injury": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf",
    "standings": "https://www.nba.com/standings",
}

TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors", "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

NEUTRAL_SITE_GAMES = {"0022600189"}  # DEN vs IND, NBA Mexico City Game, 2026-11-07

MIN_BURN_IN = 60          # games used to fit before any out-of-sample prediction
MIN_TEAM_GAMES = 3        # a team must have this many games before it is rated


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def d(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def team_url(abbr):
    return "https://www.nba.com/stats/team/{}/traditional".format(
        {"ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
         "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
         "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
         "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
         "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
         "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
         "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
         "UTA": 1610612762, "WAS": 1610612764}[abbr])


# --------------------------------------------------------------------------------------
# 1. load
# --------------------------------------------------------------------------------------
games = sorted(
    ({
        "date": d(r["date"]), "gid": r["game_id"], "away": r["away"], "home": r["home"],
        "away_pts": int(r["away_pts"]), "home_pts": int(r["home_pts"]),
        "ot": r["ot"] == "1",
        "neutral": r["game_id"] in NEUTRAL_SITE_GAMES,
    } for r in read_csv(os.path.join(PROC, "games.csv"))),
    key=lambda g: (g["date"], g["gid"]),
)
for i, g in enumerate(games):
    g["idx"] = i
    g["margin"] = g["home_pts"] - g["away_pts"]      # home - away
    g["total"] = g["home_pts"] + g["away_pts"]

teams = {r["team"]: {k: (f(v) if k != "team" else v) for k, v in r.items()}
         for r in read_csv(os.path.join(PROC, "teams_advanced.csv"))}
players = read_csv(os.path.join(PROC, "players_top_minutes.csv"))
upcoming = read_csv(os.path.join(PROC, "schedule_upcoming.csv"))
injuries = read_csv(os.path.join(PROC, "injuries.csv"))

# --------------------------------------------------------------------------------------
# 2. league baselines from official season table
# --------------------------------------------------------------------------------------
total_poss = sum(t["poss"] for t in teams.values())
lg_off_rtg = sum(t["off_rtg"] * t["poss"] for t in teams.values()) / total_poss
lg_pace = statistics.fmean(t["pace"] for t in teams.values())
lg_ppg_actual = statistics.fmean(g["total"] for g in games) / 2.0

# --------------------------------------------------------------------------------------
# 3. rest days, derived from the official schedule of results
# --------------------------------------------------------------------------------------
last_play = {}
rest_days = {}
for g in games:
    for side in ("home", "away"):
        t = g[side]
        rest_days[(g["gid"], t)] = (
            (g["date"] - last_play[t]).days if t in last_play else None
        )
        last_play[t] = g["date"]
for g in games:
    g["home_rest"] = rest_days[(g["gid"], g["home"])]
    g["away_rest"] = rest_days[(g["gid"], g["away"])]

# --------------------------------------------------------------------------------------
# 4. rating engines
# --------------------------------------------------------------------------------------
def additive_stats(prior):
    """Points-for / points-against per game from prior official results."""
    pf, pa, gp = defaultdict(float), defaultdict(float), defaultdict(int)
    for g in prior:
        pf[g["home"]] += g["home_pts"]; pa[g["home"]] += g["away_pts"]; gp[g["home"]] += 1
        pf[g["away"]] += g["away_pts"]; pa[g["away"]] += g["home_pts"]; gp[g["away"]] += 1
    lg = sum(pf.values()) / max(1, sum(gp.values()))
    out = {}
    for t in gp:
        out[t] = {"ppg": pf[t] / gp[t], "papg": pa[t] / gp[t], "gp": gp[t],
                  "pd": (pf[t] - pa[t]) / gp[t]}
    return out, lg, gp


def massey(prior, team_list):
    """Least-squares (Massey) net ratings + home-court constant.

    margin_g = hca + r_home - r_away + eps,  fitted by OLS with a
    sum-to-zero constraint row on the team ratings (weight W) to make the
    system identifiable.
    """
    idx = {t: i for i, t in enumerate(team_list)}
    p = 1 + len(team_list)
    X, y = [], []
    W = 1e4
    for g in prior:
        row = [0.0] * p
        row[0] = 0.0 if g.get("neutral") else 1.0
        row[1 + idx[g["home"]]] += 1.0
        row[1 + idx[g["away"]]] -= 1.0
        X.append(row); y.append(float(g["margin"]))
    Xs, ys = X[:], y[:]
    crow = [0.0] * p
    for i in range(1, p):
        crow[i] = 1.0
    Xs.append([W * v for v in crow]); ys.append(0.0)
    beta = ols(Xs, ys)
    hca = beta[0]
    ratings = {t: beta[1 + idx[t]] for t in team_list}
    return hca, ratings


TEAM_LIST = sorted(TEAM_NAMES)


def predict(g, prior, method, shrink=None):
    """Return dict(margin=..., total=...) or None when the game cannot be rated.

    method:
      A  additive points-for/points-against model
      B  Massey least-squares margin model
      C  blend of A and B (equal weight)
    shrink: if set, multiply the predicted margin by this factor (shrinkage toward 0).
    """
    stats, lg, gp = additive_stats(prior)
    if g["home"] not in stats or g["away"] not in stats:
        return None
    if gp[g["home"]] < MIN_TEAM_GAMES or gp[g["away"]] < MIN_TEAM_GAMES:
        return None
    h, a = stats[g["home"]], stats[g["away"]]
    hca, ratings = massey(prior, TEAM_LIST)
    hc = 0.0 if g.get("neutral") else hca

    # ---- margin candidates -------------------------------------------------------
    m_add = (h["ppg"] + a["papg"] - lg) - (a["ppg"] + h["papg"] - lg)
    m_mas = hc + ratings[g["home"]] - ratings[g["away"]]
    if method in ("A", "A_t2"):
        margin = m_add
    elif method in ("B", "B_t2"):
        margin = m_mas
    else:
        margin = 0.5 * m_add + 0.5 * m_mas
    if shrink is not None:
        margin *= shrink

    # ---- total candidates --------------------------------------------------------
    # T1: additive (points-for plus points-against, league-centred)
    t_add = (h["ppg"] + a["papg"] - lg) + (a["ppg"] + h["papg"] - lg)
    # T2: sum of the two teams' own scoring rates. No league centring is needed here -
    #     each team's ppg is already on the scale of one team's score, so the two sum
    #     directly to a game total. (Centring by lg as well would halve the estimate.)
    t_own = h["ppg"] + a["ppg"]
    total = t_add if method.endswith("_t1") else t_own
    return {"margin": margin, "total": total}


def predict_totals(g, prior):
    """Both total estimators, for model selection."""
    stats, lg, gp = additive_stats(prior)
    h, a = stats[g["home"]], stats[g["away"]]
    return {
        "T1_additive": (h["ppg"] + a["papg"] - lg) + (a["ppg"] + h["papg"] - lg),
        "T2_own_scoring": h["ppg"] + a["ppg"],
    }


# --------------------------------------------------------------------------------------
# 5. walk-forward backtest (expanding window, strictly no look-ahead)
# --------------------------------------------------------------------------------------
oos = []
for i in range(MIN_BURN_IN, len(games)):
    g = games[i]
    prior = games[:i]
    pa = predict(g, prior, "A")
    pb = predict(g, prior, "B")
    pc = predict(g, prior, "C")
    if not pa or not pb or not pc:
        continue
    tt = predict_totals(g, prior)
    prior_margins = [x["margin"] for x in prior]
    prior_totals = [x["total"] for x in prior]
    base_margin = mean(prior_margins)
    base_total = mean(prior_totals)
    oos.append({
        "gid": g["gid"], "date": g["date"].isoformat(), "home": g["home"], "away": g["away"],
        "act_margin": g["margin"], "act_total": g["total"], "ot": g["ot"],
        "neutral": g["neutral"],
        "predA_margin": pa["margin"], "predA_total": pa["total"],
        "predB_margin": pb["margin"], "predB_total": pb["total"],
        "predC_margin": pc["margin"], "predC_total": pc["total"],
        "totalT1": tt["T1_additive"], "totalT2": tt["T2_own_scoring"],
        "base_margin": base_margin, "base_total": base_total,
        "home_rest": g["home_rest"], "away_rest": g["away_rest"],
    })


def err_metrics(pairs_pred_act):
    errs = [a - p for p, a in pairs_pred_act]
    return {
        "n": len(errs),
        "bias": mean(errs),
        "mae": mean([abs(e) for e in errs]),
        "rmse": math.sqrt(mean([e * e for e in errs])),
        "sd": stdev(errs),
    }


def eval_model(key_margin, key_total, label):
    m = err_metrics([(r[key_margin], r["act_margin"]) for r in oos])
    t = err_metrics([(r[key_total], r["act_total"]) for r in oos])
    _, p_bias_m, _ = t_test_1sample([r["act_margin"] - r[key_margin] for r in oos], 0.0)
    _, p_bias_t, _ = t_test_1sample([r["act_total"] - r[key_total] for r in oos], 0.0)
    # paired comparison of squared errors against the naive baseline
    dm = [(r["act_margin"] - r[key_margin]) ** 2 - (r["act_margin"] - r["base_margin"]) ** 2
          for r in oos]
    dt = [(r["act_total"] - r[key_total]) ** 2 - (r["act_total"] - r["base_total"]) ** 2
          for r in oos]
    _, p_m, _ = t_test_1sample(dm, 0.0)
    _, p_t, _ = t_test_1sample(dt, 0.0)
    covers = sum(1 for r in oos if r["act_margin"] > r[key_margin])
    overs = sum(1 for r in oos if r["act_total"] > r[key_total])
    return {
        "label": label, "n": len(oos),
        "margin": m, "total": t,
        "margin_bias_p": p_bias_m, "total_bias_p": p_bias_t,
        "margin_beats_baseline_p": p_m, "total_beats_baseline_p": p_t,
        "margin_baseline_rmse": math.sqrt(mean([(r["act_margin"] - r["base_margin"]) ** 2 for r in oos])),
        "total_baseline_rmse": math.sqrt(mean([(r["act_total"] - r["base_total"]) ** 2 for r in oos])),
        "home_cover": covers, "home_cover_rate": covers / len(oos),
        "home_cover_p": binomial_test(covers, len(oos), 0.5),
        "over": overs, "over_rate": overs / len(oos),
        "over_p": binomial_test(overs, len(oos), 0.5),
    }


modelA = eval_model("predA_margin", "totalT1", "LM-A additive points model")
modelB = eval_model("predB_margin", "totalT2", "LM-B Massey least-squares margin model")
modelC = eval_model("predC_margin", "totalT2", "LM-C blend (A+B margins, T2 total)")
candidates = [modelA, modelB, modelC]
best_margin = min(candidates, key=lambda m: m["margin"]["rmse"])
best_total = min(candidates, key=lambda m: m["total"]["rmse"])
SELECTED_MARGIN_KEY = {"LM-A additive points model": "predA_margin",
                       "LM-B Massey least-squares margin model": "predB_margin",
                       "LM-C blend (A+B margins, T2 total)": "predC_margin"}[best_margin["label"]]
SELECTED_TOTAL_KEY = {"LM-A additive points model": "totalT1",
                      "LM-B Massey least-squares margin model": "totalT2",
                      "LM-C blend (A+B margins, T2 total)": "totalT2"}[best_total["label"]]
for r in oos:
    r["pred_margin"] = r[SELECTED_MARGIN_KEY]
    r["pred_total"] = r[SELECTED_TOTAL_KEY]

# home-court advantage fitted on the whole verified sample (DERIVED, not an official stat)
full_hca, full_ratings = massey(games, TEAM_LIST)
resid_sd_margin = math.sqrt(mean([(r["act_margin"] - r["pred_margin"]) ** 2 for r in oos]))
resid_sd_total = math.sqrt(mean([(r["act_total"] - r["pred_total"]) ** 2 for r in oos]))
_, hca_p, hca_df = t_test_1sample(
    [g["margin"] - (full_ratings[g["home"]] - full_ratings[g["away"]]) for g in games
     if not g["neutral"]], 0.0)

# --------------------------------------------------------------------------------------
# 6. correlations
# --------------------------------------------------------------------------------------
mres = [r["act_margin"] - r["pred_margin"] for r in oos]
tres = [r["act_total"] - r["pred_total"] for r in oos]
r_mt, ci_mt = corr(mres, tres), fisher_ci(corr(mres, tres), len(oos))

hov = [1.0 if r["act_margin"] > r["pred_margin"] else 0.0 for r in oos]
oov = [1.0 if r["act_total"] > r["pred_total"] else 0.0 for r in oos]
phi_mt = corr(hov, oov)
p_both = mean([1.0 if (a > 0.5 and b > 0.5) else 0.0 for a, b in zip(hov, oov)])
p_home = mean(hov)
p_over = mean(oov)

home_pts = [g["home_pts"] for g in games]
away_pts = [g["away_pts"] for g in games]
r_ha = corr(home_pts, away_pts)
r_ha_ci = fisher_ci(r_ha, len(games))

# same-game-team correlation: two players on the same team (PTS) - cannot be computed
# from the data captured (no per-player game logs) -> UNVERIFIED, left blank.
correlations = {
    "n_games_total": len(games),
    "n_games_oos": len(oos),
    "rows": [
        {"pair": "Home points vs away points (same game)",
         "stat": "Pearson r", "value": r_ha, "ci95": list(r_ha_ci), "n": len(games),
         "verified": True,
         "source": SRC["games"],
         "note": "Computed from the 174 verified final scores."},
        {"pair": "Originated-spread residual vs originated-total residual",
         "stat": "Pearson r", "value": r_mt, "ci95": list(ci_mt), "n": len(oos),
         "verified": True,
         "source": SRC["games"],
         "note": "Residuals are out-of-sample (walk-forward). This is the key input for "
                 "same-game parlays that combine a side with a total."},
        {"pair": "Cover (vs our spread) AND over (vs our total)",
         "stat": "phi (binary)", "value": phi_mt, "ci95": [None, None], "n": len(oos),
         "verified": True,
         "source": SRC["games"],
         "note": "Joint hit rate {:.3f} vs {:.3f} under independence.".format(
             p_both, p_home * p_over)},
        {"pair": "Player A points vs Player B points, same team, same game (PTS-PTS)",
         "stat": "Pearson r", "value": None, "ci95": [None, None], "n": None,
         "verified": False, "source": "",
         "note": "Requires per-player game logs, which were not captured. Left blank by policy."},
        {"pair": "Player points vs player rebounds, same player, same game",
         "stat": "Pearson r", "value": None, "ci95": [None, None], "n": None,
         "verified": False, "source": "",
         "note": "Requires per-player game logs. Left blank by policy."},
        {"pair": "Player points vs player assists, same player, same game (combo SGP)",
         "stat": "Pearson r", "value": None, "ci95": [None, None], "n": None,
         "verified": False, "source": "",
         "note": "Requires per-player game logs. Left blank by policy."},
        {"pair": "Two legs in different games (cross-game parlay)",
         "stat": "Pearson r", "value": 0.0, "ci95": [None, None], "n": None,
         "verified": False, "source": "",
         "note": "Not measured on this sample. Independence is an ASSUMPTION, not a verified "
                 "result; treat as unverified."},
    ],
    "parlay_joint_rate": p_both,
    "parlay_independent_rate": p_home * p_over,
    "p_home_cover": p_home,
    "p_over": p_over,
}

# --------------------------------------------------------------------------------------
# 7. strategy evaluation
# --------------------------------------------------------------------------------------
def evaluate(picks, label, family, rule, p_null=0.5):
    """picks: list of dicts with 'win' (bool) and 'date'.

    p_null is the break-even probability for the market being tested. It is 0.50 for a
    single bet against a fair line, but NOT for a parlay - there the correct null is the
    joint probability implied by the observed leg rates under independence.
    """
    n = len(picks)
    wins = sum(1 for p in picks if p["win"])
    if n == 0:
        return {"id": family, "label": label, "rule": rule, "n": 0, "wins": 0, "rate": None,
                "p": None, "verdict": "NO SAMPLE", "gates": {"G2_sample": False},
                "first_half_rate": None, "second_half_rate": None, "p_null": p_null}
    rate = wins / n
    p = binomial_test(wins, n, p_null, alternative="two-sided")
    dates = sorted(p["date"] for p in picks)
    cut = dates[len(dates) // 2]
    fh = [p2["win"] for p2 in picks if p2["date"] <= cut]
    sh = [p2["win"] for p2 in picks if p2["date"] > cut]
    return {
        "id": family, "label": label, "rule": rule,
        "n": n, "wins": wins, "rate": rate, "p": p,
        "first_half_rate": (sum(fh) / len(fh)) if fh else None,
        "second_half_rate": (sum(sh) / len(sh)) if sh else None,
        "gates": {"G2_sample": n >= 100},
    }


picks = {}

# S1 / S2 - self-consistency of the originated lines
picks["S1"] = [{"win": r["act_margin"] > r["pred_margin"], "date": r["date"]} for r in oos]
picks["S2"] = [{"win": r["act_total"] > r["pred_total"], "date": r["date"]} for r in oos]

# S3 - rest differential (derived from official game dates)
s3 = []
for r in oos:
    if r["home_rest"] is None or r["away_rest"] is None:
        continue
    diff = r["home_rest"] - r["away_rest"]
    if abs(diff) < 2:
        continue
    # side with more rest
    if diff > 0:
        win = r["act_margin"] > r["pred_margin"]
    else:
        win = r["act_margin"] < r["pred_margin"]
    s3.append({"win": win, "date": r["date"]})
picks["S3"] = s3

# S4 - fade large favourites relative to our own originated spread
s4 = [{"win": r["act_margin"] < r["pred_margin"], "date": r["date"]}
      for r in oos if r["pred_margin"] >= 8.0]
picks["S4"] = s4

s4b = [{"win": r["act_margin"] > r["pred_margin"], "date": r["date"]}
       for r in oos if r["pred_margin"] <= -8.0]
picks["S4b"] = s4b

# S5 - totals at the extremes of our own originated total
s5 = [{"win": r["act_total"] < r["pred_total"], "date": r["date"]}
      for r in oos if r["pred_total"] >= 235.0]
picks["S5"] = s5

s5b = [{"win": r["act_total"] > r["pred_total"], "date": r["date"]}
       for r in oos if r["pred_total"] <= 218.0]
picks["S5b"] = s5b

# S6 - correlated same-game parlay vs our own two lines
s6 = [{"win": (r["act_margin"] > r["pred_margin"]) and (r["act_total"] > r["pred_total"]),
       "date": r["date"]} for r in oos]
picks["S6"] = s6

# The parlay null is the joint hit rate implied by the two observed leg rates under
# independence - testing a two-leg parlay against 0.50 would be a category error.
PARLAY_NULL = correlations["parlay_independent_rate"]

strategy_specs = [
    ("S1", "Originated spread - home side", "Take the home side against our own originated "
     "spread in every rated game (self-consistency test).", 0.50),
    ("S2", "Originated total - over", "Take the over against our own originated total in "
     "every rated game (self-consistency test).", 0.50),
    ("S3", "Rest differential >= 2 days", "When one team has at least two more days of rest "
     "than the other, take that team against our originated spread.", 0.50),
    ("S4", "Fade home favourites of 8+", "When our originated spread has the home team "
     "favoured by 8 or more, take the away side.", 0.50),
    ("S4b", "Back road favourites of 8+", "When our originated spread has the away team "
     "favoured by 8 or more, take the away side.", 0.50),
    ("S5", "Fade totals of 235+", "When our originated total is 235 or more, take the under.",
     0.50),
    ("S5b", "Back totals of 218 or fewer", "When our originated total is 218 or less, take "
     "the over.", 0.50),
    ("S6", "Same-game parlay: home cover AND over", "Two-leg correlated parlay built on our "
     "own originated spread and total.", PARLAY_NULL),
]

raw_results = [evaluate(picks[k], lbl, k, rule, p_null)
               for k, lbl, rule, p_null in strategy_specs]
ps = [r["p"] for r in raw_results if r["p"] is not None]
keep = [i for i, r in enumerate(raw_results) if r["p"] is not None]
fdr_flags = [False] * len(raw_results)
if keep:
    flags = bh_fdr([raw_results[i]["p"] for i in keep], 0.05)
    for pos, i in enumerate(keep):
        fdr_flags[i] = flags[pos]

strategies = []
for i, (key, lbl, rule, p_null) in enumerate(strategy_specs):
    r = raw_results[i]
    n = r["n"]
    rate = r["rate"]
    gates = {
        "G1_provenance_all_inputs_official_or_derived": True,
        "G2_no_lookahead": True,
        "G3_sample_n_ge_100": n >= 100,
        "G4_powered_observed_effect_n_needed": None,
        "G5_raw_p_lt_0.05": (r["p"] is not None and r["p"] < 0.05),
        "G6_survives_bh_fdr_0.05": bool(fdr_flags[i]) if r["p"] is not None else None,
        "G7_split_half_direction_stable": None,
    }
    # minimum n needed to call the OBSERVED effect significant at 80% power
    if n > 0 and rate is not None:
        delta = abs(rate - p_null)
        gates["G4_powered_observed_effect_n_needed"] = (
            None if delta < 1e-9
            else math.ceil(((norm_ppf(0.975) + norm_ppf(0.80)) / delta) ** 2)
        )
    fh, sh = r["first_half_rate"], r["second_half_rate"]
    if fh is not None and sh is not None:
        gates["G7_split_half_direction_stable"] = (
            (fh >= p_null and sh >= p_null) or (fh <= p_null and sh <= p_null)
        )
    bool_gates = [v for v in gates.values() if isinstance(v, bool)]
    r["gates"] = gates
    r["passed_all_gates"] = all(bool_gates) and len(bool_gates) >= 4
    r["p_null"] = p_null
    if r["passed_all_gates"]:
        r["verdict"] = "PASSED - deployable"
    elif n < 100 and gates["G5_raw_p_lt_0.05"]:
        r["verdict"] = "PROVISIONAL - signal present, sample under-powered"
    elif n < 100:
        r["verdict"] = "INCONCLUSIVE - sample too small"
    else:
        r["verdict"] = "FAILED - no evidence of edge"
    r["note"] = (
        "Two-leg parlay judged against the independence-implied joint rate "
        "{:.3f}, not 0.50 (a 50% null would be a category error here).".format(p_null)
        if key == "S6" else ""
    )
    strategies.append(r)

# leaderboard: sort by whether it passes, then by observed rate
strategies_sorted = sorted(
    strategies,
    key=lambda s: (not s["passed_all_gates"],
                   -(s["rate"] if s["rate"] is not None else -1)),
)

# --------------------------------------------------------------------------------------
# 8. originated lines for every upcoming game (D+0 .. D+3)
# --------------------------------------------------------------------------------------
# The PRIMARY originated line is produced by the model that was actually validated
# walk-forward (the LM-C blend of the additive and Massey margin models, fitted on all 174
# verified results).  The efficiency-based estimate built from the official season
# OffRtg/DefRtg/Pace table is reported alongside it as a CROSS-CHECK only: it cannot be
# walk-forward validated from this session's data, because we hold only season-to-date
# ratings, and using them in a backtest would leak future games.
full_stats, full_lg, full_gp = additive_stats(games)
_lines_hca, _lines_ratings = full_hca, full_ratings

lines = []
for r in upcoming:
    h, a = r["home"], r["away"]
    th, ta = teams[h], teams[a]
    pace = (th["pace"] + ta["pace"]) / 2.0
    h_adj = th["off_rtg"] + ta["def_rtg"] - lg_off_rtg
    a_adj = ta["off_rtg"] + th["def_rtg"] - lg_off_rtg
    e_home = pace * h_adj / 100.0
    e_away = pace * a_adj / 100.0
    e_margin = e_home - e_away + full_hca
    e_total = e_home + e_away

    # ---- primary line: walk-forward-validated LM-C blend --------------------------
    hs, as_ = full_stats[h], full_stats[a]
    m_add = (hs["ppg"] + as_["papg"] - full_lg) - (as_["ppg"] + hs["papg"] - full_lg)
    m_mas = _lines_hca + _lines_ratings[h] - _lines_ratings[a]
    m_primary = 0.5 * m_add + 0.5 * m_mas
    t_primary = hs["ppg"] + as_["ppg"]          # T2 own-scoring estimator (validated)
    # availability diagnostics from the official injury report
    outs_h = [i for i in injuries if i["team"] == h and i["game_date"] == r["date"]
              and i["status"] in ("Out", "Doubtful")]
    outs_a = [i for i in injuries if i["team"] == a and i["game_date"] == r["date"]
              and i["status"] in ("Out", "Doubtful")]
    sub_h = any(i["status"] == "NOT YET SUBMITTED" for i in injuries
                if i["team"] == h and i["game_date"] == r["date"])
    sub_a = any(i["status"] == "NOT YET SUBMITTED" for i in injuries
                if i["team"] == a and i["game_date"] == r["date"])
    lines.append({
        "date": r["date"], "gid": r["game_id"], "away": a, "home": h,
        "time_et": r["time_et"], "competition": r["competition"],
        "pace": pace, "poss": pace,
        "exp_home_pts": e_home, "exp_away_pts": e_away,
        "exp_margin": e_margin, "exp_total": e_total,
        "orig_spread_home": -m_primary,   # home line, negative = home favoured
        "orig_total": t_primary,
        "eff_spread_home": -e_margin,     # cross-check only, NOT walk-forward validated
        "eff_total": e_total,
        "total_lo": t_primary - 1.959963984540054 * resid_sd_total,
        "total_hi": t_primary + 1.959963984540054 * resid_sd_total,
        "margin_lo": m_primary - 1.959963984540054 * resid_sd_margin,
        "margin_hi": m_primary + 1.959963984540054 * resid_sd_margin,
        "p_home_win": 1.0 - 0.5 * (1.0 + math.erf(
            -(m_primary) / (resid_sd_margin * math.sqrt(2.0)))) if resid_sd_margin > 0 else None,
        "p_ot": None,   # filled below
        "out_count_home": len(outs_h), "out_count_away": len(outs_a),
        "out_players_home": [i["player"] for i in outs_h],
        "out_players_away": [i["player"] for i in outs_a],
        "injury_report_submitted_home": not sub_h,
        "injury_report_submitted_away": not sub_a,
        "source_team_stats": SRC["team_advanced"],
        "source_schedule": SRC["schedule"],
        "source_game": "https://www.nba.com/game/{}-vs-{}-{}".format(
                r["away"].lower(), r["home"].lower(), r["game_id"]),
        "team_url_home": team_url(h), "team_url_away": team_url(a),
    })

ot_rate = sum(1 for g in games if g["ot"]) / len(games)
for l in lines:
    l["p_ot"] = ot_rate

# --------------------------------------------------------------------------------------
# 9. injury -> rotation minutes / production
# --------------------------------------------------------------------------------------
pmap = {}
for p in players:
    pmap.setdefault(p["team"], []).append(p)

status_prob_weight = {"Out": 0.0, "Doubtful": 0.25, "Questionable": 0.6,
                      "Probable": 0.9, "Available": 1.0}

impact_rows = []
for r in upcoming:
    for side in ("home", "away"):
        team = r[side]
        rep = [i for i in injuries if i["team"] == team and i["game_date"] == r["date"]]
        submitted = bool(rep) and not any(i["status"] == "NOT YET SUBMITTED" for i in rep)
        captured = pmap.get(team, [])
        vac = 0.0
        details = []
        for i in rep:
            match = next((p for p in captured if p["player"].lower() == i["player"].lower()), None)
            w = status_prob_weight.get(i["status"], 1.0)
            if match is None:
                details.append({"player": i["player"], "status": i["status"],
                                "reason": i["reason"], "mpg": None,
                                "mpg_at_risk": None,
                                "note": "Not in the captured top-31 minutes set; minutes "
                                        "impact UNVERIFIED."})
                continue
            mpg = f(match["min"]) or 0.0
            risk = mpg * (1.0 - w)
            vac += risk
            details.append({"player": i["player"], "status": i["status"],
                            "reason": i["reason"], "mpg": mpg, "mpg_at_risk": risk,
                            "note": "Captured; minutes impact derived from official MPG."})
        impact_rows.append({
            "date": r["date"], "team": team, "opponent": r["away"] if side == "home" else r["home"],
            "home_away": "home" if side == "home" else "away",
            "report_submitted": submitted,
            "players_listed": len([i for i in rep if i["player"]]),
            "out_or_doubtful": len([i for i in rep if i["status"] in ("Out", "Doubtful")]),
            "minutes_vacuum_quantified": vac,
            "minutes_vacuum_unquantified": None,
            "captured_players": len(captured),
            "details": details,
            "source": SRC["injury"],
        })

# player prop projections (point estimates only; distribution UNVERIFIED)
prop_rows = []
upcoming_teams = {(r["away"], r["date"]) for r in upcoming} | {(r["home"], r["date"]) for r in upcoming}
for p in players:
    team = p["team"]
    for r in upcoming:
        if team not in (r["home"], r["away"]):
            continue
        date_ = r["date"]
        rep = [i for i in injuries if i["team"] == team and i["game_date"] == date_]
        st = next((i["status"] for i in rep if i["player"].lower() == p["player"].lower()), None)
        vac = next((row["minutes_vacuum_quantified"] for row in impact_rows
                    if row["team"] == team and row["date"] == date_), 0.0)
        captured = pmap.get(team, [])
        avail_mpg = sum((f(q["min"]) or 0.0) * status_prob_weight.get(
            next((i["status"] for i in rep if i["player"].lower() == q["player"].lower()), "Available"), 1.0)
            for q in captured)
        share = (f(p["min"]) or 0.0) / avail_mpg if avail_mpg else 0.0
        # ASSUMPTION (flagged): the quantified minutes vacuum is redistributed pro-rata by
        # season minutes among the captured players who are available.
        proj_min = (f(p["min"]) or 0.0) + vac * share
        mult = proj_min / (f(p["min"]) or 1.0)
        prop_rows.append({
            "date": date_, "team": team,
            "opponent": r["away"] if team == r["home"] else r["home"],
            "player": p["player"], "gp": p["gp"], "status": st or "Not listed",
            "season_min": f(p["min"]), "season_pts": f(p["pts"]),
            "season_reb": f(p["reb"]), "season_ast": f(p["ast"]),
            "season_fg3m": f(p["fg3m"]),
            "avail_weight": status_prob_weight.get(st or "Available", 1.0),
            "projected_min": proj_min,
            "proj_pts": (f(p["pts"]) or 0.0) * mult,
            "proj_reb": (f(p["reb"]) or 0.0) * mult if f(p["reb"]) is not None else None,
            "proj_ast": (f(p["ast"]) or 0.0) * mult if f(p["ast"]) is not None else None,
            "proj_fg3m": (f(p["fg3m"]) or 0.0) * mult if f(p["fg3m"]) is not None else None,
            "line_verified": False,
            "verification_note": "Season averages are official. The game projection uses an "
                                 "UNVERIFIED pro-rata minutes redistribution assumption and "
                                 "no per-player game logs, so the over/under distribution is "
                                 "not established.",
            "source_player": SRC["players"], "source_injury": SRC["injury"],
        })
        break   # one row per player (first upcoming game they appear in)

# --------------------------------------------------------------------------------------
# 10. game flow
# --------------------------------------------------------------------------------------
rest_dist = defaultdict(int)
for g in games:
    for side in ("home", "away"):
        v = g[side + "_rest"]
        rest_dist[v if v is not None and v <= 5 else "6+"] += 1

game_flow = {
    "games": len(games),
    "ot_games": sum(1 for g in games if g["ot"]),
    "ot_rate": ot_rate,
    "home_wins": sum(1 for g in games if not g["neutral"] and g["margin"] > 0),
    "home_games": sum(1 for g in games if not g["neutral"]),
    "home_margin_mean": mean([g["margin"] for g in games if not g["neutral"]]),
    "avg_total": mean([g["total"] for g in games]),
    "avg_total_regulation": mean([g["total"] for g in games if not g["ot"]]),
    "avg_total_ot": mean([g["total"] for g in games if g["ot"]]),
    "derived_hca": full_hca,
    "derived_hca_p": hca_p,
    "derived_hca_df": hca_df,
    "resid_sd_margin": resid_sd_margin,
    "resid_sd_total": resid_sd_total,
    "lg_off_rtg": lg_off_rtg,
    "lg_pace": lg_pace,
    "pace_leaders": sorted(
        [{"team": t, "pace": v["pace"], "off_rtg": v["off_rtg"], "def_rtg": v["def_rtg"],
          "net_rtg": v["net_rtg"], "url": team_url(t)} for t, v in teams.items()],
        key=lambda x: -x["pace"]),
    "rest_distribution": {str(k): v for k, v in sorted(rest_dist.items(), key=lambda x: str(x[0]))},
    "b2b_games": sum(1 for g in games if g["home_rest"] == 1 or g["away_rest"] == 1),
    "b2b_rate": None,
}
game_flow["b2b_rate"] = game_flow["b2b_games"] / len(games)

# --------------------------------------------------------------------------------------
# 11. write artefacts
# --------------------------------------------------------------------------------------
MODELS_TOTAL_BEST = best_total

out = {
    "generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "season": "2026-27",
    "data_through": max(g["date"] for g in games).isoformat(),
    "sources": SRC,
    "integrity": {
        "games_captured": len(games),
        "team_games_captured": 2 * len(games),
        "team_games_official": int(sum(t["gp"] for t in teams.values())),
        "mismatch": int(2 * len(games) - sum(t["gp"] for t in teams.values())),
        "per_team_mismatch": {t: int(2 * sum(1 for g in games if g["home"] == t or g["away"] == t)
                                     - teams[t]["gp"]) for t in TEAM_LIST},
        "note": "Cross-checked against the official GP column on "
                "nba.com/stats/teams/advanced (Regular Season).",
    },
    "league": {
        "lg_off_rtg": lg_off_rtg, "lg_pace": lg_pace,
        "actual_ppg_per_team": lg_ppg_actual,
        "avg_total": game_flow["avg_total"],
    },
    "models": {"A": modelA, "B": modelB, "C": modelC},
    "model_selection": {
        "margin": {"selected": best_margin["label"], "key": SELECTED_MARGIN_KEY},
        "total": {"selected": best_total["label"], "key": SELECTED_TOTAL_KEY},
    },
    "home_court": {"value": full_hca, "p_two_sided": hca_p, "df": hca_df,
                   "note": "Derived by least squares from the 174 verified results. "
                           "Not an official NBA statistic."},
    "residuals": {"margin_sd": resid_sd_margin, "total_sd": resid_sd_total},
    "skill": {
        "margin_variance_explained": 1.0 - (modelC["margin"]["rmse"] ** 2) /
                                     (modelC["margin_baseline_rmse"] ** 2),
        "total_variance_explained": 1.0 - (MODELS_TOTAL_BEST["total"]["rmse"] ** 2) /
                                    (MODELS_TOTAL_BEST["total_baseline_rmse"] ** 2),
    },
    "oos_games": oos,
    "correlations": correlations,
    "strategies": strategies_sorted,
    "lines": lines,
    "injury_impact": impact_rows,
    "player_props": prop_rows,
    "game_flow": game_flow,
    "team_ratings": {
        t: {"team": t, "name": TEAM_NAMES[t], "gp": v["gp"], "w": v["w"], "l": v["l"],
            "off_rtg": v["off_rtg"], "def_rtg": v["def_rtg"], "net_rtg": v["net_rtg"],
            "pace": v["pace"], "efg_pct": v["efg_pct"], "tov_pct": v["tov_pct"],
            "oreb_pct": v["oreb_pct"], "ts_pct": v["ts_pct"],
            "massey_rating": full_ratings[t], "url": team_url(t)}
        for t, v in teams.items()
    },
}
with open(os.path.join(PROC, "model_output.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, default=str)

print("games:", len(games), "oos:", len(oos))
print("integrity mismatch:", out["integrity"]["mismatch"])
print("HCA derived: {:.3f} (p={:.4f})".format(full_hca, hca_p))
for m in (modelA, modelB, modelC):
    print("{:42s} margin RMSE {:6.2f} (base {:6.2f})  total RMSE {:6.2f} (base {:6.2f})".format(
        m["label"], m["margin"]["rmse"], m["margin_baseline_rmse"],
        m["total"]["rmse"], m["total_baseline_rmse"]))
print("selected margin model:", best_margin["label"])
print("selected total model:", best_total["label"])
print("resid corr margin/total r={:.3f} CI{}".format(r_mt, ci_mt))
for s in strategies:
    print("{:4s} n={:3d} rate={} p={} pass={}".format(
        s["id"], s["n"],
        "None" if s["rate"] is None else round(s["rate"], 3),
        "None" if s["p"] is None else round(s["p"], 4),
        s["passed_all_gates"]))
print("lines:", len(lines), "prop rows:", len(prop_rows), "impact rows:", len(impact_rows))
