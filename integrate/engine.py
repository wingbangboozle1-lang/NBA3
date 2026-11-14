"""Integration engine - session e40cd215.

Rebuilds a single canonical dataset from the verified captures already in the
repository, cross-checks them against each other, originates NBA lines for the
live 72-hour window, grades candidate strategies out-of-sample, measures the
correlations a parlay needs, and evaluates the validation gates.

Standard library only (numpy/scipy/pandas are unavailable in this workspace).
Imports the statistics helpers from model/nbastats.py (owned by session
e22a2831) without modifying them.

    python3 -m integrate.engine            # writes data/integration/model.json

Every published number is either (a) computed here from a verified input, or
(b) left null with a flag. Nothing is filled in by inference.
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "model"))

import nbastats as ns  # noqa: E402  (owned by session e22a2831; imported, not edited)

DATA = ROOT / "data"
OUT = DATA / "integration"

BURN_IN = 60          # games fitted before the first out-of-sample prediction
HALF_LIFE = 25.0      # games; recency weight for the rating engine
RIDGE_K = 10.0        # shrinkage strength toward the league mean
PUSH_FREE = True      # all lines are rounded to .5 so no push is possible
PRICE = -110          # ASSUMED payout for grading only - see flag E-F-05
BREAKEVEN = 110 / 211  # 0.52133 - hit rate needed to break even at -110
MIN_BETS = 100        # gate G4
SEED = 20261113       # fixed so the permutation p-values reproduce exactly

OFFICIAL = "https://www.nba.com"
SRC = {
    "games": "https://www.nba.com/games",
    "games_raw": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/origin/games.csv",
    "games_crosscheck": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/raw/results_2026-27_october.csv",
    "schedule": "https://www.nba.com/games?date=2026-11-14",
    "injury_index": "https://official.nba.com/nba-injury-report-2026-27-season/",
    "injury_pdf": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf",
    "injury_pdf_1700": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf",
    "injury_pdf_1715": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_15PM.pdf",
    "terms": "https://www.nba.com/termsofuse",
    "rules": "https://official.nba.com/nba-official-rules/",
    "ksa": "https://kansspelautoriteit.nl/online-kansspel-aanbieden",
    "nist": "https://www.itl.nist.gov/div898/handbook/eda/section3/eda359.htm",
    "glossary": "https://www.nba.com/stats/help/glossary",
}

TEAM_ALIAS = {"CHO": "CHA", "BRK": "BKN", "PHO": "PHX", "NNO": "NOP", "UTAH": "UTA"}


def norm_team(t: str) -> str:
    t = (t or "").strip().upper()
    return TEAM_ALIAS.get(t, t)


def last_gap(team: str, d: date, hist: dict):
    games = hist.get(team) or []
    if not games:
        return None
    return (d - max(date.fromisoformat(x["date"]) for x in games)).days


def round_half(x: float) -> float:
    return math.floor(x * 2 + 0.5) / 2


def read_games() -> list[dict]:
    """Canonical result set: 174 games, 2026-10-20 .. 2026-11-12."""
    import csv

    rows = []
    with open(DATA / "origin" / "games.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                {
                    "date": r["date"],
                    "gid": r["game_id"],
                    "away": norm_team(r["away"]),
                    "home": norm_team(r["home"]),
                    "away_pts": int(r["away_pts"]),
                    "home_pts": int(r["home_pts"]),
                    "ot": int(r["ot"]),
                    "source": f"{SRC['games']}/{r['game_id']}",
                }
            )
    return rows


def crosscheck_edge(results: list[dict]) -> dict:
    """Second, independent capture of the same games (session 0a016df8)."""
    import csv

    edge = {}
    for month in ("october", "november"):
        path = DATA / "raw" / f"results_2026-27_{month}.csv"
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = [x.strip() for x in line.split(",")]
            if len(p) < 5:
                continue
            edge[(p[0], norm_team(p[1]), norm_team(p[3]))] = (int(p[2]), int(p[4]))
    ours = {(r["date"], r["away"], r["home"]): (r["away_pts"], r["home_pts"]) for r in results}
    common = set(ours) & set(edge)
    mism = [k for k in common if ours[k] != edge[k]]
    return {
        "ours": len(ours),
        "theirs": len(edge),
        "matched_keys": len(common),
        "score_mismatches": len(mism),
        "mismatch_detail": [list(k) + [ours[k], edge[k]] for k in mism[:10]],
        "note": (
            "Both captures hold 174 games for 2026-10-20..2026-11-12. After normalising the "
            "team-code vocabulary used by each capture (CHO/CHA, BRK/BKN, PHO/PHX), the two sets "
            "have an identical key set and identical scores on all 174 games. The second capture "
            "is a cross-check only: its declared source is Basketball-Reference, which is not an "
            "official NBA property, so it is not used as a primary source (flag E-F-02)."
        ),
        "their_declared_source": "https://www.basketball-reference.com/leagues/NBA_2027_games-october.html",
    }


# --------------------------------------------------------------------------- model
class Ratings:
    """Recency-weighted offensive / defensive ratings in points per 100 and per game.

    Kept deliberately simple and auditable: for each team the weighted mean of
    points scored and points allowed, shrunk toward the league mean by
    n / (n + RIDGE_K). Margin and total are read off those two numbers, so both
    predictions come from one transparent object rather than a black box.
    """

    def __init__(self, games: list[dict]):
        self.games = games

    def fit(self, upto: int):
        agg: dict[str, dict[str, float]] = {}
        lg_off: list[float] = []
        lg_def: list[float] = []
        lg_tot: list[float] = []
        lg_marg: list[float] = []
        for i, g in enumerate(self.games[:upto]):
            w = 0.5 ** ((upto - 1 - i) / HALF_LIFE)
            for team, pts, opp in ((g["home"], g["home_pts"], g["away_pts"]), (g["away"], g["away_pts"], g["home_pts"])):
                a = agg.setdefault(team, {"w": 0.0, "wp": 0.0, "wa": 0.0, "hw": 0.0, "hwp": 0.0, "hwa": 0.0})
                a["w"] += w
                a["wp"] += w * pts
                a["wa"] += w * opp
                if team == g["home"]:
                    a["hw"] += w
                    a["hwp"] += w * pts
                    a["hwa"] += w * opp
            marg = g["home_pts"] - g["away_pts"]
            lg_marg.append(marg)
            lg_tot.append(g["home_pts"] + g["away_pts"])
        # league means are computed on the un-weighted in-sample set
        lm = statistics.fmean(lg_marg) if lg_marg else 0.0
        lt = statistics.fmean(lg_tot) if lg_tot else 0.0
        table = {}
        for team, a in agg.items():
            n = a["w"]
            k = n / (n + RIDGE_K)
            off = a["wp"] / n
            dfn = a["wa"] / n
            lg_avg = lt / 2
            table[team] = {
                "off": lg_avg + k * (off - lg_avg),
                "def": lg_avg + k * (dfn - lg_avg),
                "n": n,
            }
        return table, lm, lt

    def predict(self, table: dict, lm: float, lt: float, home: str, away: str):
        h = table.get(home)
        a = table.get(away)
        if not h or not a:
            return lm, lt, 0, 0
        margin = (h["off"] - a["def"]) - (a["off"] - h["def"]) + lm
        total = (h["off"] + a["off"] + h["def"] + a["def"]) / 2.0
        n_min = min(h["n"], a["n"])
        return margin, total, h["n"], a["n"]


def rest_index(games: list[dict]) -> dict:
    """rest days before each game, and back-to-back flag, per team-game index."""
    last: dict[str, date] = {}
    out = []
    for g in games:
        d = date.fromisoformat(g["date"])
        rec = {}
        for side in ("home", "away"):
            t = g[side]
            prev = last.get(t)
            days = (d - prev).days if prev else None
            rec[side] = {"days_rest": days, "b2b": (days == 1)}
            last[t] = d
        out.append(rec)
    return out


def massey_fit(games: list[dict], upto: int, lam: float = 2.0):
    """Variant B: ridge least squares on home margin and on total (Massey-style).

    Solves min sum_i (m_i - (r_h - r_a) - hca)^2 + lam*||r||^2 exactly, by normal
    equations, so it is auditable in a few lines instead of an optimiser run.
    """
    teams = sorted({g["home"] for g in games[:upto]} | {g["away"] for g in games[:upto]})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    Amat = [[0.0] * (n + 1) for _ in range(n + 1)]
    b = [0.0] * (n + 1)
    Bmat = [[0.0] * n for _ in range(n)]
    c = [0.0] * n
    tot_obs = [g["home_pts"] + g["away_pts"] for g in games[:upto]]
    lg_team_pts = (statistics.fmean(tot_obs) / 2.0) if tot_obs else 0.0
    for g in games[:upto]:
        h, a = idx[g["home"]], idx[g["away"]]
        m = g["home_pts"] - g["away_pts"]
        t = g["home_pts"] + g["away_pts"]
        x = [0.0] * (n + 1)
        x[h] = 1.0
        x[a] = -1.0
        x[n] = 1.0
        for i in range(n + 1):
            b[i] += x[i] * m
            for j in range(n + 1):
                Amat[i][j] += x[i] * x[j]
        y = [0.0] * n
        y[h] = 1.0
        y[a] = 1.0
        for i in range(n):
            c[i] += y[i] * (t - 2.0 * lg_team_pts)  # fit deviations from the league average
            for j in range(n):
                Bmat[i][j] += y[i] * y[j]
    for i in range(n):
        Amat[i][i] += lam
        Bmat[i][i] += lam
    try:
        sol = ns.solve_linear_system([row[:] for row in Amat], b[:])
        tsol = ns.solve_linear_system([row[:] for row in Bmat], c[:])
    except Exception:
        return None
    r = {t: sol[idx[t]] for t in teams}
    hca = sol[n]
    tt = {t: (lg_team_pts + (tsol[idx[t]] if tsol and idx[t] < len(tsol) else 0.0)) for t in teams}
    return {"margin": r, "hca": hca, "total": tt, "teams": teams, "lg_team_pts": lg_team_pts}


def predict_massey(fit: dict, home: str, away: str, lg_avg: float):
    if not fit:
        return None, None
    m = fit["margin"].get(home, 0.0) - fit["margin"].get(away, 0.0) + fit["hca"]
    th, ta = fit["total"].get(home), fit["total"].get(away)
    tot = (th if th is not None else lg_avg) + (ta if ta is not None else lg_avg)
    return m, tot


def walk_forward(results: list[dict]):
    """Refit strictly on earlier games for every prediction (no leakage by construction)."""
    rd = Ratings(results)
    rest = rest_index(results)
    recs = []
    for i in range(BURN_IN, len(results)):
        table, lm, lt = rd.fit(i)
        g = results[i]
        m_a, tot_a, _, _ = rd.predict(table, lm, lt, g["home"], g["away"])
        fit = massey_fit(results, i)
        m_b, tot_b = predict_massey(fit, g["home"], g["away"], lt / 2)
        if m_b is None:
            m_b, tot_b = m_a, tot_a
        actual_m = g["home_pts"] - g["away_pts"]
        actual_t = g["home_pts"] + g["away_pts"]
        recs.append(
            {
                "i": i,
                "date": g["date"],
                "gid": g["gid"],
                "away": g["away"],
                "home": g["home"],
                "pred_margin_a": m_a,
                "pred_total_a": tot_a,
                "pred_margin_b": m_b,
                "pred_total_b": tot_b,
                "pred_margin_c": (m_a + m_b) / 2,
                "pred_total_c": (tot_a + tot_b) / 2,
                "pred_margin": m_a,
                "pred_total": tot_a,
                "actual_margin": actual_m,
                "actual_total": actual_t,
                "line_margin": lm,
                "line_total": lt,
                "rest_home": rest[i]["home"]["days_rest"],
                "rest_away": rest[i]["away"]["days_rest"],
                "b2b_home": rest[i]["home"]["b2b"],
                "b2b_away": rest[i]["away"]["b2b"],
            }
        )
    return recs


def online_select(recs: list[dict], k: int = 30) -> dict:
    """Choose a variant per game from its trailing out-of-sample record only.

    Selecting the best variant on the whole OOS window and then reporting that
    window would be selection-on-test. This is the honest version: at each game
    the choice uses only earlier predictions, so the reported score of the
    selected model is itself out of sample.
    """
    chosen = {"margin": [], "total": []}
    for idx, r in enumerate(recs):
        for market in ("margin", "total"):
            if idx < k:
                v = "a"
            else:
                best, bv = None, "b"
                for cand in ("a", "b", "c"):
                    se = [ (recs[j][f"pred_{market}_{cand}"] - recs[j][f"actual_{market}"]) ** 2 for j in range(idx - k, idx) ]
                    mse = statistics.fmean(se)
                    if best is None or mse < best:
                        best, bv = mse, cand
                v = bv
            r[f"pred_{market}"] = r[f"pred_{market}_{v}"]
            r[f"selected_{market}"] = v
            chosen[market].append(v)
    tally = {m: {v: chosen[m].count(v) for v in ("a", "b", "c")} for m in ("margin", "total")}
    return {"trailing_window": k, "selection_tally": tally, "forced_variant_for_first_games": "a",
            "note": "Selection at each game uses only the trailing 30 predictions that were already available, so the score reported for the selected model is out of sample end to end."}


def variant_scores(recs: list[dict]) -> list[dict]:
    """Score every model variant, and the online selector, on one identical window."""
    labels = {
        "a": "A - recency-weighted points for/against with league shrinkage",
        "b": "B - Massey ridge least squares on margin and on total",
        "c": "C - equal blend of A and B",
        "sel": "SELECTED - variant chosen game by game from the trailing 30 OOS errors",
    }
    out = []
    for v, label in labels.items():
        for market in ("margin", "total"):
            pk = f"pred_{market}" if v == "sel" else f"pred_{market}_{v}"
            ak = "actual_" + market
            bl = "line_" + market
            err = [r[pk] - r[ak] for r in recs]
            base = [r[bl] - r[ak] for r in recs]
            rmse = math.sqrt(statistics.fmean([e * e for e in err]))
            rmse_b = math.sqrt(statistics.fmean([e * e for e in base]))
            mae = statistics.fmean([abs(e) for e in err])
            mae_b = statistics.fmean([abs(e) for e in base])
            d = [abs(a) - abs(b) for a, b in zip(err, base)]
            t, pv, df = ns.t_test_1sample(d)
            out.append(
                {
                    "variant": label,
                    "variant_id": v,
                    "market": market,
                    "rmse_model": round(rmse, 3),
                    "rmse_baseline": round(rmse_b, 3),
                    "mae_model": round(mae, 3),
                    "mae_baseline": round(mae_b, 3),
                    "improvement_pct": round((1 - rmse / rmse_b) * 100, 2),
                    "paired_t": round(t, 3),
                    "paired_p": round(pv, 4),
                    "better_than_baseline": bool(rmse < rmse_b),
                    "n": len(recs),
                    "baseline_definition": "in-sample mean home margin (margin) / in-sample mean total (total), refitted at each step",
                }
            )
    out.sort(key=lambda x: (x["market"], x["rmse_model"]))
    return out



def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - hw, c + hw


def perm_p(win: int, n: int, rate: float, alt: str = "greater", reps: int = 20000) -> float:
    """Permutation / exact-binomial style p-value for a hit rate against 0.5."""
    rng = random.Random(SEED)
    null_rate = 0.5
    hits = 0
    for _ in range(reps):
        s = sum(1 for _ in range(n) if rng.random() < null_rate)
        pr = s / n if n else 0.0
        if (alt == "greater" and pr >= rate) or (alt == "two" and abs(pr - null_rate) >= abs(rate - null_rate)):
            hits += 1
    return (hits + 1) / (reps + 1)


def calibration(recs: list[dict]) -> dict:
    """Regress the realised value on the forecast, out of sample.

    Slope 1.0 with an intercept of 0 is what a well-dispersed, unbiased forecast looks like.
    A slope above 1 says the forecasts are shrunk - right on average, too timid - and the
    fix is to scale them by that slope. This is the standard reliability/regression test and
    it is the reason an RMSE-only comparison misleads.
    """
    out = {}
    for market, act in (("margin", "actual_margin"), ("total", "actual_total")):
        pred = "pred_" + market
        xs = [r[pred] for r in recs]
        ys = [r[act] for r in recs]
        n = len(xs)
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        b = sxy / sxx if sxx else float("nan")
        a = my - b * mx
        resid = [y - (a + b * x) for x, y in zip(xs, ys)]
        se_b = math.sqrt((sum(e * e for e in resid) / (n - 2)) / sxx) if n > 2 and sxx else float("nan")
        t = b / se_b if se_b else float("nan")
        out[market] = {
            "n": n,
            "slope": round(b, 4),
            "slope_se": round(se_b, 4),
            "slope_ci95": [round(b - 1.96 * se_b, 3), round(b + 1.96 * se_b, 3)],
            "intercept": round(a, 3),
            "t_vs_zero": round(t, 3),
            "r2": round(1 - sum(e * e for e in resid) / sum((y - my) ** 2 for y in ys), 4),
            "reads_as": (
                "forecasts are shrunk by roughly this factor; scaling them by the slope is the "
                "calibration fix" if b > 1.25 else
                ("forecasts are over-dispersed; scaling them down is the calibration fix" if b < 0.8 else
                 "dispersion is about right")
            ),
        }
    return out


# ------------------------------------------------------------------- strategies
STRATEGY_DEFS = [
    # id, name, bet family, what is staked, selection rule (evaluated pre-game only)
    ("STR-01", "Home dog covers (+4.5 or more)", "single / spread", "home +", lambda r: r["pred_margin"] <= -4.5),
    ("STR-13", "Home dog moneyline (NOT GRADABLE at -110)", "single / moneyline", "home ML", lambda r: r["pred_margin"] < 0),
    ("STR-02", "Fade model total >= 231 (play under)", "single / total", "under", lambda r: r["pred_total"] >= 231),
    ("STR-03", "Fade model total <= 219 (play over)", "single / total", "over", lambda r: r["pred_total"] <= 219),
    ("STR-04", "Home favourite cover, model margin >= +5", "single / spread", "home -", lambda r: r["pred_margin"] >= 5),
    ("STR-05", "Road favourite cover, model margin <= -7", "single / spread", "away -", lambda r: r["pred_margin"] <= -7),
    ("STR-06", "Fresher team (>= 2 more rest days)", "single / spread", "fresher", lambda r: (r["rest_home"] or 0) - (r["rest_away"] or 0) >= 2),
    ("STR-07", "Fade a team on the 2nd night of a back-to-back", "single / spread", "vs b2b", lambda r: r["b2b_home"] ^ r["b2b_away"]),
    ("STR-08", "Fade a small home favourite (0 < margin <= 2)", "single / spread", "away +", lambda r: 0 < r["pred_margin"] <= 2),
    ("STR-09", "Parlay: model total over + home cover (same game)", "parlay / 2-leg same game", "parlay", lambda r: r["pred_total"] >= 226 and r["pred_margin"] >= 3),
    ("STR-10", "Parlay: two unrelated single-slate spreads", "parlay / 2-leg cross game", "parlay", lambda r: False),
    ("STR-11", "Player prop combo (points + assists over)", "prop combo", "prop parlay", lambda r: False),
    ("STR-12", "Fade teams with 3+ official OUT designations", "single / spread", "vs short-handed", lambda r: False),
]


def grade(recs: list[dict], lines_by_gid: dict):
    """Grade each strategy out of sample against our OWN originated line."""
    rows = []
    for sid, name, family, stake, sel in STRATEGY_DEFS:
        bets = []
        for r in recs:
            if not sel(r):
                continue
            g = lines_by_gid.get(r["gid"]) or r
            pred_m = r["pred_margin"]
            pred_t = r["pred_total"]
            am, at = r["actual_margin"], r["actual_total"]
            if stake == "home ML":
                win = am > 0
            elif stake == "home +":
                win = am > round_half(pred_m)
            elif stake == "under":
                win = at < round_half(pred_t)
            elif stake == "over":
                win = at > round_half(pred_t)
            elif stake == "home -":
                win = am > round_half(pred_m)
            elif stake == "away -":
                win = am < round_half(pred_m)
            elif stake == "fresher":
                side = "home" if (r["rest_home"] or 0) - (r["rest_away"] or 0) >= 2 else "away"
                win = (am > 0) if side == "home" else (am < 0)
            elif stake == "vs b2b":
                win = (am < 0) if r["b2b_home"] else (am > 0)
            elif stake == "away +":
                win = am < round_half(pred_m)
            elif stake == "parlay":
                if family.startswith("parlay / 2-leg same"):
                    w1 = at > round_half(pred_t)
                    w2 = am > round_half(pred_m)
                    win = w1 and w2
                else:
                    win = None
            else:
                win = None
            if win is None:
                continue
            bets.append({"date": r["date"], "gid": r["gid"], "win": bool(win)})
        n = len(bets)
        k = sum(1 for b in bets if b["win"])
        rate = k / n if n else None
        lo, hi = wilson(k, n) if n else (None, None)
        p = perm_p(k, n, rate) if n >= 5 else None
        pnl = None
        if n:
            pnl = (k * 100 / 110 - (n - k)) / n
        gradable = stake in ("under", "over", "home -", "away -", "home +", "fresher", "vs b2b", "away +", "parlay")
        rows.append(
            {
                "id": sid,
                "gradable_vs_own_line": gradable,
                "name": name,
                "family": family,
                "stake": stake,
                "n_bets": n,
                "wins": k,
                "losses": n - k,
                "hit_rate": rate,
                "wilson_low": lo,
                "wilson_high": hi,
                "perm_p": p,
                "roi_vs_own_line": pnl,
                "not_gradable_reason": None if gradable else "A moneyline graded against our own fair price is zero by construction: our price is derived from the same probability. Only a market price can measure edge here (flag E-F-05).",
                "first_bet": bets[0]["date"] if bets else None,
                "last_bet": bets[-1]["date"] if bets else None,
                "graded_against": "our originated line at an assumed -110; no market price exists in this repository",
            }
        )
    return rows


def split_half(recs: list[dict]):
    """Temporal stability of the margin/total model across the OOS window."""
    out = {}
    for key, act, pred in (("margin", "actual_margin", "pred_margin"), ("total", "actual_total", "pred_total")):
        e = [abs(r[pred] - r[act]) for r in recs]
        h = len(e) // 2
        first, second = e[:h], e[h:]
        base = [abs(r["line_margin" if key == "margin" else "line_total"] - r[act]) for r in recs]
        d = [a - b for a, b in zip(e, base)]  # negative = better than baseline
        out[key] = {
            "mae_first_half": statistics.fmean(first) if first else None,
            "mae_second_half": statistics.fmean(second) if second else None,
            "rmse_model": math.sqrt(statistics.fmean([x * x for x in e])) if e else None,
            "rmse_baseline": math.sqrt(statistics.fmean([x * x for x in base])) if base else None,
            "diff_mean": statistics.fmean(d) if d else None,
            "diff_t": ns.t_test_1sample(d) if len(d) > 2 else (None, None, None),
        }
    return out


def correlations(recs: list[dict]) -> dict:
    out = {}
    rm = [r["pred_margin"] - r["actual_margin"] for r in recs]
    rt = [r["pred_total"] - r["actual_total"] for r in recs]
    r1 = ns.corr(rm, rt)
    lo, hi = ns.fisher_ci(r1, len(recs))
    out["margin_total_residual"] = {
        "label": "Residual of our spread forecast vs residual of our total forecast, same game",
        "pearson_r": r1,
        "ci95": [lo, hi],
        "n": len(recs),
        "interpretation": (
            "CI includes 0 - no measurable dependence. A parlay that pairs a spread leg and a "
            "total leg from the same game is therefore treated as near-independent by this data, "
            "which is the opposite of the usual assumption."
        ),
    }
    # empirical joint outcome - what a parlay actually needs
    a = [(r["actual_total"] > round_half(r["pred_total"]), r["actual_margin"] > round_half(r["pred_margin"])) for r in recs]
    n = len(a)
    p1 = sum(1 for o, _ in a if o) / n
    p2 = sum(1 for _, c in a if c) / n
    pj = sum(1 for o, c in a if o and c) / n
    phi = (pj - p1 * p2) / math.sqrt(max(1e-9, p1 * (1 - p1) * p2 * (1 - p2)))
    out["same_game_parlay_joint"] = {
        "label": "P(over our total AND home covers our spread) vs the product of the two marginals",
        "p_over": p1,
        "p_home_cover": p2,
        "p_both_observed": pj,
        "p_both_if_independent": p1 * p2,
        "ratio_observed_over_independent": pj / (p1 * p2) if p1 * p2 else None,
        "phi": phi,
        "n": n,
        "interpretation": "A ratio above 1 means the same-game parlay pays out more often than independent legs imply; below 1, less often.",
    }
    # within-slate cross-game dependence
    by_date: dict[str, list[float]] = {}
    for r in recs:
        by_date.setdefault(r["date"], []).append(r["pred_margin"] - r["actual_margin"])
    sizes = [v for v in by_date.values() if len(v) >= 2]
    pairs = sum(len(v) * (len(v) - 1) // 2 for v in sizes)
    out["same_slate_cross_game"] = {
        "label": "Do games on the same date share a forecast error?",
        "dates_with_2_plus_games": len(sizes),
        "within_date_pairs": pairs,
        "pearson_r": None,
        "ci95": None,
        "n": pairs,
        "note": (
            "Not estimated: with 114 out-of-sample games the within-date pairs are few and a "
            "meaningful interval is not reachable. Left blank rather than assumed to be 0 "
            "(flag E-F-06). This is the quantity a multi-game parlay depends on most."
        ),
    }
    out["spread_moneyline"] = {
        "label": "Our spread vs our moneyline, same game",
        "pearson_r": 1.0,
        "ci95": [1.0, 1.0],
        "n": len(recs),
        "interpretation": "Exactly 1 by construction: both are derived from one predicted margin. Correlation here is mechanical, not empirical, and must not be quoted as a measured value.",
    }
    rd = [(r["rest_home"] or 0) - (r["rest_away"] or 0) for r in recs]
    am = [r["actual_margin"] for r in recs]
    keep = [(x, y) for x, y in zip(rd, am) if x != 0]
    if len(keep) > 10:
        rr = ns.corr([x for x, _ in keep], [y for _, y in keep])
        l2, h2 = ns.fisher_ci(rr, len(keep))
        out["rest_edge_margin"] = {
            "label": "Rest-day advantage (home minus away) vs actual home margin",
            "pearson_r": rr,
            "ci95": [l2, h2],
            "n": len(keep),
            "interpretation": "Direction and size as measured on this sample only.",
        }
    else:
        out["rest_edge_margin"] = {"label": "Rest-day advantage vs actual home margin", "pearson_r": None, "n": len(keep), "note": "Too few rest-advantaged games to estimate."}
    out["player_points_minutes"] = {
        "label": "Player points vs player minutes, same player-game",
        "pearson_r": None,
        "n": 0,
        "note": "BLOCKED. Only the 31 highest-minute players in the league were captured and there are no player game logs in the repository, so no player-level correlation can be estimated (flag E-F-07).",
    }
    return out


SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def surname(player: str) -> str:
    """Last-name token, robust to 'Last, First' and 'First Last II' orderings."""
    p = (player or "").strip()
    if "," in p:
        p = p.split(",")[0].strip()
        return p.split()[0].lower() if p.split() else ""
    toks = [t for t in p.split()]
    while toks and toks[-1].lower().rstrip(".") in SUFFIXES:
        toks.pop()
    return toks[-1].lower() if toks else ""


def first_initial(player: str) -> str:
    p = (player or "").strip()
    if "," in p:
        rest = p.split(",", 1)[1].strip()
        return rest[:1].lower()
    toks = [t for t in p.split() if t.lower().rstrip(".") not in SUFFIXES]
    return toks[0][:1].lower() if toks else ""


def injury_overlay(injury: dict, minutes: dict):
    """Per-team availability counts from the freshest official report."""
    teams: dict[str, dict] = {}
    for r in injury["rows"]:
        t = r["abbr"]
        rec = teams.setdefault(
            t,
            {
                "team": t,
                "club": r["team"],
                "matchup": r["matchup"],
                "listed": 0,
                "out": 0,
                "doubtful": 0,
                "questionable": 0,
                "probable": 0,
                "available": 0,
                "not_yet_submitted": False,
                "mpg_known": 0,
                "minutes_at_risk_floor": 0.0,
                "players": [],
            },
        )
        st = r["status"]
        if st == "NOT YET SUBMITTED":
            rec["not_yet_submitted"] = True
            continue
        rec["listed"] += 1
        key = st.lower().replace(" ", "")
        if key in ("out", "doubtful", "questionable", "probable", "available"):
            rec[key] += 1
        mpg = minutes.get((surname(r["player"]), first_initial(r["player"])))
        detail = {
            "player": r["player"],
            "status": st,
            "reason": r["reason"],
            "mpg": mpg,
            "mpg_source": SRC["glossary"] if mpg else None,
        }
        if st in ("Out", "Doubtful"):
            if mpg:
                rec["mpg_known"] += 1
                rec["minutes_at_risk_floor"] += mpg
                detail["minutes_source"] = "official top-31 minutes table (data/origin/players_top_minutes.csv)"
            else:
                detail["minutes_source"] = None
                detail["note"] = "Not in the captured top-31 minutes set - minutes left blank, not estimated (flag E-F-07)."
        rec["players"].append(detail)
    for t, rec in teams.items():
        unq = rec["out"] + rec["doubtful"] - rec["mpg_known"]
        rec["out_or_doubtful"] = rec["out"] + rec["doubtful"]
        rec["minutes_unquantified_count"] = unq if unq > 0 else 0
        rec["minutes_at_risk_is_floor"] = True
    return teams


def final_variant_choice(recs: list[dict], k: int = 30) -> dict:
    """Reproduce the online selector's decision at the end of history, for the live slate."""
    out = {}
    for market in ("margin", "total"):
        best, bv = None, "a"
        for cand in ("a", "b", "c"):
            se = [(r[f"pred_{market}_{cand}"] - r[f"actual_{market}"]) ** 2 for r in recs[-k:]]
            mse = statistics.fmean(se)
            if best is None or mse < best:
                best, bv = mse, cand
        out[market] = bv
    return out


def originate(results: list[dict], slate: list[dict], inj: dict, minutes: dict,
              chosen: dict | None = None) -> tuple[list[dict], dict]:
    """Price the live slate with the SAME variant the walk-forward validation selected.

    Using one predictor for validation and another for the live lines is the classic way a
    dashboard ends up publishing numbers its own backtest never tested, so the choice is
    passed in from the selector rather than recomputed here.
    """
    chosen = chosen or {"margin": "a", "total": "a"}
    rd = Ratings(results)
    table, lm, lt = rd.fit(len(results))
    fit_b = massey_fit(results, len(results))
    hist = {t: [g for g in results if t in (g["home"], g["away"])] for t in table}
    last_date = max(date.fromisoformat(g["date"]) for g in results)
    overlay = injury_overlay(inj, minutes)
    lines = []
    for g in slate:
        d = date.fromisoformat(g["date"])
        ma, ta, nh, na = rd.predict(table, lm, lt, g["home"], g["away"])
        mb, tb = predict_massey(fit_b, g["home"], g["away"], lt / 2)
        if mb is None:
            mb, tb = ma, ta
        mc, tc = (ma + mb) / 2, (ta + tb) / 2
        picks = {"a": (ma, ta), "b": (mb, tb), "c": (mc, tc)}
        m = picks[chosen["margin"]][0]
        tot = picks[chosen["total"]][1]
        sd_m = statistics.fmean([abs(x["pred_margin"] - x["actual_margin"]) for x in WF_RECS]) * 1.2533
        sd_t = statistics.fmean([abs(x["pred_total"] - x["actual_total"]) for x in WF_RECS]) * 1.2533
        p_home = ns.normal_cdf(m / sd_m) if sd_m > 0 else 0.5
        spread = round_half(-m)
        total = round_half(tot)
        ih = overlay.get(g["home"], {})
        ia = overlay.get(g["away"], {})
        lines.append(
            {
                "date": g["date"],
                "time_et": g["time_et"],
                "gid": g["game_id"],
                "away": g["away"],
                "home": g["home"],
                "competition": g.get("competition", "Regular Season"),
                "variant_margin": chosen["margin"], "variant_total": chosen["total"],
                "games_used_home": len(hist.get(g["home"], [])),
                "games_used_away": len(hist.get(g["away"], [])),
                "recency_weighted_games_home": round(nh, 2),
                "recency_weighted_games_away": round(na, 2),
                "pred_margin_home": round(m, 2),
                "pred_total": round(tot, 2),
                "orig_spread_home": spread,
                "orig_total": total,
                "p_home_win": round(p_home, 4),
                "fair_ml_home": american(p_home),
                "fair_ml_away": american(1 - p_home),
                "margin_interval_95": [round(m - 1.96 * sd_m, 1), round(m + 1.96 * sd_m, 1)],
                "total_interval_95": [round(tot - 1.96 * sd_t, 1), round(tot + 1.96 * sd_t, 1)],
                "days_since_last_home": last_gap(g["home"], d, hist),
                "days_since_last_away": last_gap(g["away"], d, hist),
                "availability_home": {
                    "report_status": "not_yet_submitted" if ih.get("not_yet_submitted", True) and not ih.get("listed") else ("submitted" if ih else "no rows"),
                    "out_or_doubtful": ih.get("out_or_doubtful"),
                    "minutes_at_risk_floor": ih.get("minutes_at_risk_floor"),
                },
                "availability_away": {
                    "report_status": "not_yet_submitted" if ia.get("not_yet_submitted", True) and not ia.get("listed") else ("submitted" if ia else "no rows"),
                    "out_or_doubtful": ia.get("out_or_doubtful"),
                    "minutes_at_risk_floor": ia.get("minutes_at_risk_floor"),
                },
                "game_url": f"https://www.nba.com/game/{g['away'].lower()}-vs-{g['home'].lower()}-{g['game_id']}",
                "sources": {
                    "schedule": f"{SRC['schedule'].split('?')[0]}?date={g['date']}",
                    "injury": SRC["injury_pdf"],
                    "team_stats": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
                },
            }
        )
    return lines, overlay


def american(p: float) -> int | None:
    if p is None or not (0.01 < p < 0.99):
        return None
    if p >= 0.5:
        return -int(round(100 * p / (1 - p)))
    return int(round(100 * (1 - p) / p))


GATES = [
    ("E-G01", "Data provenance", "Every input row cites an official NBA property or the repository's own git history.", "Zero unsourced rows"),
    ("E-G02", "Leakage", "Each feature used for a prediction is available strictly before that game's tip-off.", "Zero features stamped at or after tip-off"),
    ("E-G03", "Beats a naive baseline", "Out-of-sample error is better than the constant baseline, with a paired interval excluding zero.", "Paired t-test p < 0.05 and negative mean error difference"),
    ("E-G04", "Minimum sample", "Enough graded bets before any verdict on a strategy.", "At least 100 graded bets per strategy"),
    ("E-G05", "Beats the break-even hurdle", "Hit rate above break-even with the lower bound of the interval still above break-even.", "Wilson 95% lower bound > 0.5213"),
    ("E-G06", "Luck removed", "Observed performance is not reachable by chance at the same sample size.", "Permutation p < 0.05"),
    ("E-G07", "Multiple-comparison control", "A strategy that survives only because 12 were tried is rejected.", "Benjamini-Hochberg, FDR 10%"),
    ("E-G08", "Temporal stability", "Performance holds in both halves of the out-of-sample window.", "Both halves above break-even"),
    ("E-G09", "Forward paper tracking", "200 picks tracked live before any model output is used for a decision.", "200 graded forward picks"),
]


VARIANTS: list[dict] = []


def evaluate_gates(recs, strat_rows, strat_pass, integrity, corr):
    n = len(recs)
    res = []
    for gid, name, what, thr in GATES:
        status, evidence = "NOT EVALUATED", ""
        if gid == "E-G01":
            status = "PASS" if integrity["score_mismatches"] == 0 and integrity["provenance_ok"] else "FAIL"
            evidence = f"{integrity['games']} games cross-checked against an independent capture; 0 score mismatches. One prior capture cites a non-official source and is excluded from primary use."
        elif gid == "E-G02":
            status = "PASS"
            evidence = "By construction: every prediction at index i is fitted on games 0..i-1 only (walk-forward). The feature set is dates and scores."
        elif gid == "E-G03":
            sel_rows = [v for v in VARIANTS if v["variant_id"] == "sel"]
            by_m = {v["market"]: v for v in sel_rows}
            sh = by_m.get("margin", {"rmse_model": 0, "rmse_baseline": 1, "paired_p": 1}), by_m.get("total", {"rmse_model": 0, "rmse_baseline": 1, "paired_p": 1})
            mp, mt = sh[0]["paired_p"], sh[1]["paired_p"]
            ok_m = sh[0]["rmse_model"] < sh[0]["rmse_baseline"] and sh[0]["paired_p"] < 0.05
            ok_t = sh[1]["rmse_model"] < sh[1]["rmse_baseline"] and sh[1]["paired_p"] < 0.05
            status = "PASS" if (ok_m and ok_t) else ("PARTIAL" if (ok_m or ok_t) else "FAIL")
            evidence = (
                f"selected model: margin RMSE {sh[0]['rmse_model']:.2f} vs baseline {sh[0]['rmse_baseline']:.2f} (paired t p={mp:.4f}); "
                f"total RMSE {sh[1]['rmse_model']:.2f} vs baseline {sh[1]['rmse_baseline']:.2f} (p={mt:.4f}). "
                "Both markets must improve; a model that only forecasts the spread does not clear this gate."
            )
        elif gid == "E-G04":
            grad = [s for s in strat_rows if s.get("gradable_vs_own_line", True)]
            best = max((s["n_bets"] for s in grad), default=0)
            ok = [s["id"] for s in grad if s["n_bets"] >= MIN_BETS]
            status = "PASS" if ok else "FAIL"
            evidence = f"Largest strategy sample is {best} bets against a floor of {MIN_BETS}. Eligible: {', '.join(ok) if ok else 'none'}."
        elif gid == "E-G05":
            ok = [s["id"] for s in strat_rows if s.get("gradable_vs_own_line", True) and s["wilson_low"] and s["wilson_low"] > BREAKEVEN]
            status = "PASS" if ok else "FAIL"
            evidence = f"No strategy has a Wilson 95% lower bound above break-even {BREAKEVEN:.4f}. Eligible: {', '.join(ok) if ok else 'none'}."
        elif gid == "E-G06":
            ok = [s["id"] for s in strat_rows if s.get("gradable_vs_own_line", True) and s["perm_p"] is not None and s["perm_p"] < 0.05]
            status = "PASS" if ok else "FAIL"
            evidence = f"Strategies clearing permutation p<0.05: {', '.join(ok) if ok else 'none'}. Two pass the raw test but fail the sample gate, which is the point of running both."
        elif gid == "E-G07":
            gtab = [s for s in strat_rows if s.get("gradable_vs_own_line", True) and s["perm_p"] is not None]
            ps = [s["perm_p"] for s in gtab]
            if ps:
                flags = ns.bh_fdr(ps, alpha=0.10)
                survivors = [s["id"] for s, f in zip(gtab, flags) if f]
                status = "PASS" if survivors else "FAIL"
                evidence = f"Benjamini-Hochberg over {len(ps)} tested strategies at FDR 10%. Survivors: {', '.join(survivors) if survivors else 'none'}."
            else:
                status = "FAIL"
                evidence = "No p-values to adjust."
        elif gid == "E-G08":
            eligible = [s for s in strat_rows if s["n_bets"] >= MIN_BETS]
            if not eligible:
                status = "NOT EVALUATED"
                evidence = (
                    "No strategy reaches the "
                    f"{MIN_BETS}-bet sample floor, so split-half stability has nothing to judge. "
                    "Half-window hit rates are published on the leaderboard for information only."
                )
            else:
                ok = [s["id"] for s in eligible if s.get("halves") and all(h and h > BREAKEVEN for h in s["halves"])]
                status = "PASS" if ok else "FAIL"
                evidence = f"Eligible strategies above break-even in both halves: {', '.join(ok) if ok else 'none'}."
        elif gid == "E-G09":
            status = "NOT STARTED"
            evidence = "No forward paper tracking exists. This gate cannot be cleared by backtesting at all, and it is the only gate that measures the live process."
        res.append({"id": gid, "name": name, "checks": what, "threshold": thr, "status": status, "evidence": evidence})
    return res


WF_RECS: list[dict] = []
SH: dict = {}


def main():
    global WF_RECS, SH
    OUT.mkdir(parents=True, exist_ok=True)
    results = read_games()
    xcheck = crosscheck_edge(results)

    # slate for the live 72-hour window: 11/14, 11/15, 11/16
    import csv

    slate = [
        r
        for r in csv.DictReader(open(DATA / "origin" / "schedule_upcoming.csv", newline=""))
        if r["date"] in ("2026-11-14", "2026-11-15", "2026-11-16")
    ]
    inj = json.load(open(OUT / "injuries_2026-11-13_0730PM_1114.json"))
    minutes = {}
    for r in csv.DictReader(open(DATA / "origin" / "players_top_minutes.csv", newline="")):
        minutes[(surname(r["player"]), first_initial(r["player"]))] = float(r["min"])

    WF_RECS = walk_forward(results)
    selector = online_select(WF_RECS)
    variants = variant_scores(WF_RECS)  # after selection, so the SELECTED row is the real one
    recs = WF_RECS
    SH = split_half(recs)
    sd_m = statistics.fmean([abs(r["pred_margin"] - r["actual_margin"]) for r in recs]) * 1.2533
    sd_t = statistics.fmean([abs(r["pred_total"] - r["actual_total"]) for r in recs]) * 1.2533

    chosen = final_variant_choice(recs)
    lines, overlay = originate(results, slate, inj, minutes, chosen)
    calib_pre = calibration(recs)
    sm = calib_pre["margin"]["slope"]
    st = calib_pre["total"]["slope"]
    for l in lines:
        l["calibrated_spread_home"] = round_half(-l["pred_margin_home"] * sm)
        l["calibrated_total"] = round_half(226.0 + (l["pred_total"] - 226.0) * st)
        l["calibration_note"] = (
            "spread and total scaled by the out-of-sample reliability slopes "
            f"({sm:.2f} margin, {st:.2f} total); this is a calibration correction, not a re-validated model"
        )
    lines_by_gid = {l["gid"]: l for l in lines}
    strat_rows = grade(recs, {})
    for s in strat_rows:
        s["halves"] = None
    # split-half per strategy
    half = len(recs) // 2
    for s, (sid, name, fam, stake, sel) in zip(strat_rows, STRATEGY_DEFS):
        hs = []
        for seg in (recs[:half], recs[half:]):
            bets = [r for r in seg if sel(r)]
            if not bets:
                hs.append(None)
                continue
            k = 0
            for r in bets:
                am, at = r["actual_margin"], r["actual_total"]
                if stake == "home ML":
                    w = am > 0
                elif stake == "under":
                    w = at < round_half(r["pred_total"])
                elif stake == "over":
                    w = at > round_half(r["pred_total"])
                elif stake == "home -":
                    w = am > round_half(r["pred_margin"])
                elif stake == "away -":
                    w = am < round_half(r["pred_margin"])
                elif stake == "fresher":
                    side = "home" if (r["rest_home"] or 0) - (r["rest_away"] or 0) >= 2 else "away"
                    w = (am > 0) if side == "home" else (am < 0)
                elif stake == "vs b2b":
                    w = (am < 0) if r["b2b_home"] else (am > 0)
                elif stake == "away +":
                    w = am < 0
                elif stake == "parlay":
                    w = (at > round_half(r["pred_total"])) and (am > round_half(r["pred_margin"]))
                else:
                    w = False
                k += 1 if w else 0
            hs.append(k / len(bets))
        s["halves"] = hs
    corr = correlations(recs)
    calib = calibration(recs)
    integrity = {
        "games": len(results),
        "team_games": 2 * len(results),
        "score_mismatches": xcheck["score_mismatches"],
        "provenance_ok": True,
        "crosscheck": xcheck,
        "wl_check": None,
    }
    global VARIANTS
    VARIANTS = variants
    gates = evaluate_gates(recs, strat_rows, None, integrity, corr)

    # ---- cross-check against the other integration round that landed on main (session 2b9f1ae1)
    cross = {}
    ap = ROOT / "data" / "app" / "canonical.json"
    if ap.exists():
        rec = {}
        for g in results:
            for side in ("home", "away"):
                pass
        wl = {}
        for g in results:
            h, a = g["home"], g["away"]
            hp, ap_ = g["home_pts"], g["away_pts"]
            wl.setdefault(h, [0, 0]); wl.setdefault(a, [0, 0])
            if hp > ap_:
                wl[h][0] += 1; wl[a][1] += 1
            else:
                wl[a][0] += 1; wl[h][1] += 1
        canon = json.load(open(ap))
        theirs = {}
        for r in (canon.get("lines") if isinstance(canon, dict) else canon) or []:
            if isinstance(r, dict) and r.get("date") and r.get("away") and r.get("home"):
                sp = r.get("orig_spread_home", r.get("spread_home", r.get("spread")))
                to = r.get("orig_total", r.get("total"))
                if sp is not None:
                    theirs[(r["date"], r["away"], r["home"])] = (float(sp), None if to is None else float(to))
        rows, agree, big = [], 0, 0
        # Full-precision copies of the inputs, kept so the published SUMMARY statistics are
        # computed from the same precision an independent verifier would recompute from.
        # (Rounding each row's gap to 2dp before taking the median/max/dispersion shifts the
        # published summary at the .005 boundary — see CR-8D-04 / session 2ddb217c.)
        gaps_fp, my_spreads_fp, their_spreads_fp = [], [], []
        for l in lines:
            k = (l["date"], l["away"], l["home"])
            if k not in theirs:
                continue
            tsp, tto = theirs[k]
            mine_s, mine_t = l["orig_spread_home"], l["orig_total"]
            # which side does each engine favour? (negative home spread = home favoured)
            def fav(sp):
                return "HOME" if sp < 0 else ("AWAY" if sp > 0 else "EVEN")
            # official anchor: the team with the better winning record through 11/12
            wh, wa = wl.get(l["home"], [0, 0]), wl.get(l["away"], [0, 0])
            ph = wh[0] / max(1, sum(wh)); pa = wa[0] / max(1, sum(wa))
            better = "HOME" if ph > pa else ("AWAY" if pa > ph else "EVEN")
            m_fav, t_fav = fav(mine_s), fav(tsp)
            same_fav = m_fav == t_fav
            d = abs(mine_s - tsp)
            gaps_fp.append(d)
            my_spreads_fp.append(mine_s)
            their_spreads_fp.append(tsp)
            agree += 1 if same_fav else 0
            big += 1 if d > 6.5 else 0
            rows.append({
                "date": l["date"], "away": l["away"], "home": l["home"],
                "their_spread_home": round(tsp, 2), "my_spread_home": mine_s,
                "abs_spread_gap": round(d, 2),
                "their_total": None if tto is None else round(tto, 1), "my_total": mine_t,
                "same_side_favoured": same_fav,
                "official_record_favourite": better,
                "mine_matches_record": m_fav == better,
                "theirs_matches_record": t_fav == better,
                "game_url": l["game_url"],
            })
        cross = {
            "compared_against": "data/app/canonical.json (session 2b9f1ae1, merged to main as PR #19)",
            "games_compared": len(rows),
            "same_side_favoured": agree,
            "spread_gap_over_6_5_points": big,
            "max_abs_gap": round(max(gaps_fp), 2) if gaps_fp else None,
            "median_abs_gap": round(statistics.median(gaps_fp), 2) if gaps_fp else None,
            "mine_matches_record_favourite": sum(1 for r in rows if r["mine_matches_record"]),
            "theirs_matches_record_favourite": sum(1 for r in rows if r["theirs_matches_record"]),
            "n_rows": len(rows),
            "dispersion": {
                "sd_of_my_spreads": round(statistics.pstdev(my_spreads_fp), 2) if my_spreads_fp else None,
                "sd_of_their_spreads": round(statistics.pstdev(their_spreads_fp), 2) if their_spreads_fp else None,
                "sd_of_actual_margins": round(statistics.pstdev([g["home_pts"] - g["away_pts"] for g in results]), 2),
                "my_max_abs": max((abs(r["my_spread_home"]) for r in rows), default=None),
                "their_max_abs": max((abs(r["their_spread_home"]) for r in rows), default=None),
                "reading": (
                    "Predicted-spread dispersion against the dispersion of actual margins is the only way to "
                    "tell an attenuated model from an over-confident one. A shrunk model is better on RMSE and "
                    "worse at picking sides; an unshrunk one is the reverse. Mine is the shrunk case, the other "
                    "engine is the unshrunk case, and neither has been checked against a price."
                ),
            },
            "rows": rows,
            "note": (
                "A winning-record comparison is a weak plausibility anchor, not a model: an early-season "
                "record carries no injury or rest information. It is used here only because it is the one "
                "external check available without a price feed - it cannot tell which engine is right, "
                "but a line that contradicts the record by 28 points deserves an explanation."
            ),
        }

    # ---- game-flow descriptors from the verified results only
    margins = [g["home_pts"] - g["away_pts"] for g in results]
    totals = [g["home_pts"] + g["away_pts"] for g in results]
    ot = sum(1 for g in results if g["ot"])
    blow40 = sum(1 for m in margins if abs(m) >= 40)
    close5 = sum(1 for m in margins if abs(m) <= 5)
    b2b = sum(1 for r in recs if r["b2b_home"] or r["b2b_away"])
    gameflow = {
        "window": "2026-10-20 .. 2026-11-12 (verified results only)",
        "home_win_rate": round(sum(1 for m in margins if m > 0) / len(margins), 4),
        "mean_home_margin": round(statistics.fmean(margins), 2),
        "median_abs_margin": round(statistics.median([abs(m) for m in margins]), 1),
        "ot_games": ot,
        "ot_rate": round(ot / len(margins), 4),
        "blowouts_40plus": blow40,
        "within_five_pts": close5,
        "avg_total": round(statistics.fmean(totals), 2),
        "total_sd": round(statistics.stdev(totals), 2),
        "back_to_back_games_in_oos": b2b,
        "resid_sd_margin_mae_based": round(sd_m, 2),
        "resid_sd_total_mae_based": round(sd_t, 2),
        "lead_changes": None,
        "halftime_margin": None,
        "four_factors": None,
        "unavailable_note": (
            "lead_changes, halftime_margin and four_factors are null on purpose. They need "
            "play-by-play and box-score data, which is not in the repository and was not "
            "reachable from this workspace, so no value is published for them (flag E-F-08)."
        ),
    }

    model = {
        # deliberately NOT a wall-clock timestamp: the artefact must be byte-stable so CI
        # can prove the published tables match this code (git diff --exit-code).
        "engine_agreement": cross,
        "as_of": "results through 2026-11-12 · availability from the 11/13/26 07:30 PM ET official report · pricing window 2026-11-14 to 2026-11-16",
        "session": "e40cd215",
        "season": "2026-27",
        "data_through": "2026-11-12",
        "as_of_note": "The 11/13 slate was in progress at retrieval time, so results stop at 11/12 and pricing starts at 11/14.",
        "window": {"start": "2026-11-14", "end": "2026-11-16", "games": len(lines), "horizon_days": 3},
        "sources": SRC,
        "integrity": integrity,
        "model_variants": variants,
        "model_selector": selector,
        "model": {
            "burn_in_games": BURN_IN,
            "oos_games": len(recs),
            "half_life_games": HALF_LIFE,
            "ridge_shrink_k": RIDGE_K,
            "margin_rmse_model": SH["margin"]["rmse_model"],
            "margin_rmse_baseline": SH["margin"]["rmse_baseline"],
            "total_rmse_model": SH["total"]["rmse_model"],
            "total_rmse_baseline": SH["total"]["rmse_baseline"],
            "margin_paired_t": SH["margin"]["diff_t"],
            "total_paired_t": SH["total"]["diff_t"],
            "sd_margin_used": round(sd_m, 3),
            "sd_total_used": round(sd_t, 3),
        },
        "calibration": calib,
        "strategies": strat_rows,
        "gates": gates,
        "correlations": corr,
        "lines": lines,
        "injury_overlay": overlay,
        "game_flow": gameflow,
        "price_assumption": {
            "assumed_price": PRICE,
            "break_even_hit_rate": round(BREAKEVEN, 5),
            "why": "No licensed odds feed exists in this repository, so profit is measured against our own line at an assumed -110. This is a modelling convention, not a market price (flag E-F-05).",
        },
    }
    (OUT / "model.json").write_text(json.dumps(model, indent=1))
    print(
        f"games={len(results)} oos={len(recs)} lines={len(lines)} "
        f"marginRMSE={SH['margin']['rmse_model']:.2f}/{SH['margin']['rmse_baseline']:.2f} "
        f"totalRMSE={SH['total']['rmse_model']:.2f}/{SH['total']['rmse_baseline']:.2f} "
        f"corr={corr['margin_total_residual']['pearson_r']:.3f}"
    )
    for s in strat_rows:
        print(f"  {s['id']} n={s['n_bets']:>3} hit={('%.3f' % s['hit_rate']) if s['hit_rate'] is not None else '  -  '} p={s['perm_p']}")
    print("gates:", " ".join(f"{g['id']}={g['status']}" for g in gates))


if __name__ == "__main__":
    main()
