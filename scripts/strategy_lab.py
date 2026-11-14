#!/usr/bin/env python3
"""Line origination, walk-forward validation, strategy leaderboard, correlations.

Session ``arena/8d3d0271-nba3``.  Standard library only, no network.

WHAT THIS PRODUCES
    data/app/lab.json -- one artefact with:
      * originated lines and fair prices for every game of the live window
        (2026-11-14 .. 2026-11-17: today plus the maximum three-day horizon),
      * a walk-forward backtest of the engine that produces them,
      * a strategy leaderboard: singles, same-game parlays, cross-game parlays
        and player-prop combos, each scored against eight validation gates,
        ranked by a composite skill score and given a reward tier,
      * measured correlation values (with n and interval) and the ones that
        cannot be measured, left blank and flagged,
      * injury -> rotation-minutes -> production for the live window,
      * game-flow factors for the live window.

THE ONE RULE THAT SHAPES EVERY NUMBER
    Nothing here is a bet against a bookmaker.  No licensed odds feed is
    connected to this repository, so there is no market line to compare with.
    Every "pick" below is a selection against **our own originated line**, and
    because that line is originated to be fair, the expected value of betting
    into it is zero by construction.  What the backtest therefore measures is
    not profit: it measures whether our own line is *biased* in a way a simple
    rule can exploit.  That is the honest question to ask of an originated
    line, and it is the only one this data can answer.

    Return on investment is still reported, at an assumed -110 price, because
    the owner asked for a leaderboard.  It is labelled at every point of use as
    "measured against our own line at an assumed price", which is a property
    of our own numbers, not an economic result.

LOOK-AHEAD CONTROL
    Every feature used to price a game is computed from games with a STRICTLY
    EARLIER date.  Ratings, pace proxies and league baselines are refitted for
    each date from scratch.  ``assert_no_lookahead`` re-derives this property
    from the artefacts and is run as part of the build.

Run:  python3 scripts/strategy_lab.py
"""

import csv
import json
import math
import os
import random
import re
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLISH_DP = 6   # decimals kept in lab.json; see _round_floats()
OUT = os.path.join(ROOT, "data", "app", "lab.json")

GAMES_CSV = os.path.join(ROOT, "data", "app", "games_2026-11-14c.csv")
PLAYERS_CSV = os.path.join(ROOT, "data", "app", "players_top31_2026-11-14c.csv")
SLATE_JSON = os.path.join(ROOT, "data", "app", "official_slate_1114_1117_c.json")
RATINGS_JSON = os.path.join(ROOT, "data", "app", "official_team_ratings_2026-11-14c.json")
INJURY_JSON = os.path.join(ROOT, "data", "app", "official_injuries_2026-11-14_0445AM.json")
PRIOR_SLATE_JSON = os.path.join(ROOT, "data", "app", "official_slate.json")

# --------------------------------------------------------------------------
# input selection, added by session arena/25418e3f-nba3
#
# data/app/snapshot_manifest.json names the official captures the lab must
# read.  When it exists it WINS over the defaults above, so refreshing the
# dashboard is a data change (drop new captures, repoint the manifest) rather
# than an edit of the engine.  The manifest is a checked-in file with no clock
# in it, so lab.json stays byte-reproducible, which the CI drift gate relies on.
# --------------------------------------------------------------------------
MANIFEST_JSON = os.path.join(ROOT, "data", "app", "snapshot_manifest.json")

# Set by _apply_manifest when the manifest names a second capture of the same official page.
# Session arena/bd90ce16 appended the same nine 2026-11-13 finals to its own copy of the log
# while this session was extending the canonical file, so the two are cross-checked on every
# build rather than reconciled by prose. See flag NF-66 and question CQ-47.
SECOND_CAPTURE_GAMES_CSV = None
AVAILABILITY_JSON = os.path.join(ROOT, "data", "app", "report_availability.json")

# The four availability states, defined by scripts/report_availability.py and
# used here so that "no rows captured" can never again be read as "nobody is
# out".  FILED is the only state in which an absence count means anything.
AV_FILED = "FILED"
AV_STATES = (AV_FILED, "DUE_AND_NOT_FILED", "NOT_YET_DUE",
             "NO_OFFICIAL_REPORT_COVERS_THIS_DATE")


def _apply_manifest():
    global SLATE_JSON, RATINGS_JSON, INJURY_JSON, GAMES_CSV, PLAYERS_CSV, SECOND_CAPTURE_GAMES_CSV
    if not os.path.exists(MANIFEST_JSON):
        return None
    with open(MANIFEST_JSON, encoding="utf-8") as fh:
        man = json.load(fh)
    def resolve(block):
        rel = (man.get(block) or {}).get("path")
        return os.path.join(ROOT, *rel.split("/")) if rel else None
    for block, setter in (("slate", "SLATE"), ("ratings", "RATINGS"), ("injuries", "INJURY")):
        path = resolve(block)
        if path:
            globals()[setter + "_JSON"] = path
    # CS-45, option A: every input the lab reads is named by the manifest, so a refresh is a data
    # change and two sessions cannot silently disagree about which file the engine uses.
    path = resolve("players")
    if path:
        PLAYERS_CSV = path
    # The results log is the canonical file, not a per-session copy (CQ-42). Any session may
    # capture the same official page again; that copy is registered as a cross-check instead of
    # silently becoming the engine's input.
    rel = (man.get("results_log") or {}).get("path")
    if rel:
        GAMES_CSV = os.path.join(ROOT, *rel.split("/"))
    rel = (man.get("results_log") or {}).get("cross_check_copy")
    if rel:
        SECOND_CAPTURE_GAMES_CSV = os.path.join(ROOT, *rel.split("/"))
    return man


def _second_capture_agreement(games):
    """Row-set agreement between the canonical result log and a second capture of the same page.

    Returns a published dict either way: when the second file is absent the entry says UNVERIFIED
    rather than defaulting to agreement.
    """
    key = lambda g: (g["date"], g["gid"], g["away"], g["away_pts"], g["home"], g["home_pts"], bool(g["ot"]))
    out = {"canonical": os.path.relpath(GAMES_CSV, ROOT), "second_capture": None,
           "rows_canonical": len(games), "rows_second": None, "identical": None, "detail": []}
    if not SECOND_CAPTURE_GAMES_CSV or not os.path.exists(SECOND_CAPTURE_GAMES_CSV):
        out["detail"] = ["no second capture registered - agreement UNVERIFIED, not assumed"]
        return out
    rows = []
    with open(SECOND_CAPTURE_GAMES_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"date": r["date"], "gid": r["game_id"], "away": r["away"],
                         "home": r["home"], "away_pts": int(r["away_pts"]),
                         "home_pts": int(r["home_pts"]),
                         "ot": r["ot"] not in ("", "0", "None")})
    a, b = {key(g) for g in games}, {key(g) for g in rows}
    out["second_capture"] = os.path.relpath(SECOND_CAPTURE_GAMES_CSV, ROOT)
    out["rows_second"] = len(rows)
    out["identical"] = (a == b)
    if a - b:
        out["detail"].append("only in canonical: " + "; ".join("/".join(map(str, x)) for x in sorted(a - b)[:5]))
    if b - a:
        out["detail"].append("only in second capture: " + "; ".join("/".join(map(str, x)) for x in sorted(b - a)[:5]))
    if not (a - b) and not (b - a):
        out["detail"].append(
            "two sessions extended data/origin/games.csv and data/app/games_2026-11-14c.csv "
            "independently from the official scoreboard; the row sets agree exactly, including "
            "game id, both scores and the overtime flag. Row order differs (each file appends "
            "where it likes); the engine sorts by date and game id, so order is not a finding.")
    return out


MANIFEST = _apply_manifest()

SRC_GAMES = "https://www.nba.com/games?date="
SRC_TEAM_STATS = ("https://www.nba.com/stats/teams/advanced"
                  "?Season=2026-27&SeasonType=Regular%20Season")
SRC_SCHEDULE = "https://www.nba.com/schedule?date=2026-11-14"
SRC_PLAYERS = ("https://www.nba.com/stats/players/traditional"
               "?Season=2026-27&SeasonType=Regular%20Season&PerPage=100"
               "&SortColumn=MIN&SortDirection=DESC")

BURN_IN = 40          # games used only to fit; the first 40 produce no forecast
RIDGE = 0.5           # tiny ridge so the Massey normal equations stay solvable
BOOTSTRAP = 2000      # date-block bootstrap resamples for the edge interval
PERMUTATIONS = 5000   # within-date permutations for the null distribution
SEED = 20261114       # fixed seed: the CI workflow's drift gate must be stable

ASSUMED_PRICE = -110  # the price used for every ROI figure. An ASSUMPTION.
BREAK_EVEN = 110.0 / 210.0   # 0.52381 -- the hit rate a -110 bet needs

# Gate thresholds.  These are PROPOSED by this session; the owner has not
# approved them.  They are printed on the site next to every verdict.
GATE_MIN_N = 100
GATE_ALPHA = 0.05
GATE_FDR = 0.05
GATE_POWER = 0.80


# --------------------------------------------------------------------------
# small statistics library (stdlib only)
# --------------------------------------------------------------------------
def mean(xs):
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rmse(xs):
    if not xs:
        return None
    return math.sqrt(sum(x * x for x in xs) / len(xs))


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def solve(A, b):
    """Gaussian elimination with partial pivoting.  A is n x n, b is n."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("singular matrix")
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col] / pv
            if f == 0.0:
                continue
            for c in range(col, n + 1):
                M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def ols(X, y, ridge=RIDGE):
    """Ridge-regularised least squares.  X includes its own intercept column."""
    p = len(X[0])
    A = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for row, yi in zip(X, y):
        for i in range(p):
            b[i] += row[i] * yi
            for j in range(p):
                A[i][j] += row[i] * row[j]
    for i in range(1, p):        # never penalise the intercept
        A[i][i] += ridge
    return solve(A, b)


def _lgamma(n):
    return math.lgamma(n + 1)


def binom_pmf(k, n, p=0.5):
    if k < 0 or k > n:
        return 0.0
    return math.exp(_lgamma(n) - _lgamma(k) - _lgamma(n - k)
                    + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_two_sided(k, n, p=0.5):
    """Sum of every outcome no more likely than the one observed."""
    if n == 0:
        return None
    obs = binom_pmf(k, n, p)
    if obs <= 0.0:
        return 0.0
    tol = obs * (1 + 1e-9)
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(n + 1)
                        if binom_pmf(i, n, p) <= tol))


def binom_one_sided(k, n, p=0.5):
    """P(X >= k): the directional test used for 'is this rule a winner'."""
    if n == 0:
        return None
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(k, n + 1)))


def benjamini_hochberg(pvals):
    """Return BH-adjusted q-values in the original order.  None stays None."""
    idx = [i for i, p in enumerate(pvals) if p is not None]
    m = len(idx)
    out = [None] * len(pvals)
    if m == 0:
        return out
    ordered = sorted(idx, key=lambda i: pvals[i])
    prev = 1.0
    for rank in range(m, 0, -1):
        i = ordered[rank - 1]
        q = pvals[i] * m / rank
        prev = min(prev, q)
        out[i] = min(1.0, prev)
    return out


def wilson_interval(k, n, z=1.959963985):
    """Wilson score interval for a proportion."""
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_ci(r, n, z=1.959963985):
    """Fisher z interval for a Pearson correlation."""
    if n is None or n < 4 or r is None or abs(r) >= 1:
        return (None, None)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = zr - z * se, zr + z * se
    return (math.tanh(lo), math.tanh(hi))


def pearson(xs, ys):
    n = len(xs)
    if n < 4 or n != len(ys):
        return None
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def required_n(rate, baseline=0.5, alpha=GATE_ALPHA, power=GATE_POWER):
    """Sample size needed to call the observed rate significant.

    Normal approximation for one proportion, two-sided alpha, power 1-beta.
    Returns None when the observed effect is exactly zero (no n is enough).
    """
    if rate is None:
        return None
    eff = abs(rate - baseline)
    if eff < 1e-9:
        return None
    z_a, z_b = 1.959963985, 0.841621234
    num = z_a * math.sqrt(baseline * (1 - baseline)) + z_b * math.sqrt(rate * (1 - rate))
    return (num / eff) ** 2


def american_from_prob(p):
    """Fair American price for probability p (no vig).  None if degenerate."""
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------
def load_games():
    """Every official final score in the result log the manifest names.

    The count is not restated here on purpose: a hard-coded figure in a docstring is a claim that
    goes stale the moment the log is extended, which is exactly what happened to the previous
    wording ("174 official final scores"). The reconciliation against the official games-played
    column is check C1 in data/app/snapshot_manifest.json, and the cross-capture agreement is
    published as second_capture_agreement below."""
    rows = []
    with open(GAMES_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "date": r["date"],
                "gid": r["game_id"],
                "away": r["away"],
                "home": r["home"],
                "away_pts": int(r["away_pts"]),
                "home_pts": int(r["home_pts"]),
                "ot": r["ot"] not in ("", "0", "None"),
            })
    rows.sort(key=lambda g: (g["date"], g["gid"]))
    return rows


def _f(v):
    """Official stat cell -> float, or None when the cell is empty.

    Empty cells are kept as None rather than being coerced to 0.0: a blank on
    the official page means 'not published', and turning that into a zero
    would silently invent a value.
    """
    s = (v or "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# player-name matching between the injury report and the statistics table
#
# The official injury report prints "Lastname, Firstname" (sometimes with a
# suffix: "Udeh, Jr., Ernest", "Holmes II, DaRon"); the official statistics
# table prints "Firstname Lastname" ("Anthony Edwards").  The first version of
# this file indexed the statistics table by (first-token, last-token) of the
# comma form and looked the comma form up with the same rule, so NO injury row
# ever matched a statistics row: every vacated-minutes figure the dashboard
# published was 0 or blank, and every "unknown" count was the whole list.  That
# was found by reading the artefact, not the code (session arena/df301475-nba3,
# flag F-DF3-03).  The fix compares players by sorted name tokens with
# generational suffixes removed, which is order-agnostic and keeps the two
# sources' different conventions from silently disabling the feature.
# ---------------------------------------------------------------------------
NAME_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}


def player_key(name):
    """'Udeh, Jr., Ernest' and 'Ernest Udeh Jr.' both -> ('ernest', 'udeh')."""
    toks = [t for t in re.findall(r"[a-z]+", (name or "").lower())
            if t not in NAME_SUFFIX_TOKENS]
    return tuple(sorted(toks))


def load_players():
    out = []
    with open(PLAYERS_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            row = {
                "rank": int(r["rank"]),
                "player": r["player"],
                "team": r["team"],
                "gp": int(r["gp"]),
                "min": _f(r["min"]),
                "pts": _f(r["pts"]),
                "reb": _f(r["reb"]),
                "ast": _f(r["ast"]),
                "fg3m": _f(r.get("fg3m")),
            }
            row["incomplete"] = any(row[k] is None
                                    for k in ("min", "pts", "reb", "ast", "fg3m"))
            out.append(row)
    return out


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# the engine
# --------------------------------------------------------------------------
class Engine:
    """Massey margin model + scoring-environment totals model, refit per date.

    ``fit(games)`` builds ratings from a set of completed games.  ``predict``
    applies them.  The walk-forward driver only ever fits on games whose date
    is strictly earlier than the game being priced, so no future information
    can enter.

    Two shrinkage parameters are chosen from past data only (see
    ``select_hyperparameters``), never from the games being forecast:

      * ``ridge``      -- ridge penalty on the 30 team columns of the Massey
                          design matrix.  Without enough of it the ratings of
                          teams on a bad run explode and the engine prints
                          spreads of 28 points, which no sane line does.
      * ``total_blend`` -- weight on the fitted totals model, the remainder on
                          the constant league-average total.  The fitted totals
                          model is WORSE than the constant out of sample, so
                          the honest move is to shrink it toward the constant
                          by however much the data supports.
    """

    def __init__(self):
        self.teams = []
        self.rating = {}
        self.hca = 0.0
        self.ppg = {}
        self.oppg = {}
        self.total_coef = None
        self.base_margin = 0.0
        self.base_total = 0.0
        self.ridge = RIDGE
        self.total_blend = 1.0

    # -- fitting ---------------------------------------------------------
    def fit(self, games, ridge=RIDGE):
        teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
        self.teams = teams
        self.ridge = ridge
        idx = {t: i for i, t in enumerate(teams)}
        p = len(teams) + 1          # team columns + one home-court column

        X, y = [], []
        for g in games:
            row = [0.0] * p
            row[idx[g["home"]]] = 1.0
            row[idx[g["away"]]] = -1.0
            row[-1] = 1.0
            X.append(row)
            y.append(float(g["home_pts"] - g["away_pts"]))
        coef = ols(X, y, ridge=ridge)
        self.rating = {t: coef[idx[t]] for t in teams}
        self.hca = coef[-1]

        # scoring environment, from the same completed games only
        scored, allowed = defaultdict(list), defaultdict(list)
        totals = []
        for g in games:
            scored[g["home"]].append(g["home_pts"])
            scored[g["away"]].append(g["away_pts"])
            allowed[g["home"]].append(g["away_pts"])
            allowed[g["away"]].append(g["home_pts"])
            totals.append(g["home_pts"] + g["away_pts"])
        self.ppg = {t: mean(v) for t, v in scored.items()}
        self.oppg = {t: mean(v) for t, v in allowed.items()}

        TX, Ty = [], []
        for g in games:
            h, a = g["home"], g["away"]
            hp, ap = self.ppg.get(h), self.ppg.get(a)
            ho, ao = self.oppg.get(h), self.oppg.get(a)
            if None in (hp, ap, ho, ao):
                continue
            TX.append([1.0, hp, ho, ap, ao])
            Ty.append(float(g["home_pts"] + g["away_pts"]))
        self.total_coef = ols(TX, Ty, ridge=ridge) if len(TX) >= 10 else None

        self.base_margin = mean([float(g["home_pts"] - g["away_pts"]) for g in games]) or 0.0
        self.base_total = mean(totals) if totals else 0.0

    # -- prediction ------------------------------------------------------
    def predict(self, home, away, blend=None):
        w = self.total_blend if blend is None else blend
        r_h = self.rating.get(home)
        r_a = self.rating.get(away)
        if r_h is None or r_a is None:
            return None
        margin = r_h - r_a + self.hca
        hp, ap = self.ppg.get(home), self.ppg.get(away)
        ho, ao = self.oppg.get(home), self.oppg.get(away)
        if self.total_coef is not None and None not in (hp, ap, ho, ao):
            b = self.total_coef
            fitted = b[0] + b[1] * hp + b[2] * ho + b[3] * ap + b[4] * ao
        else:
            fitted = self.base_total
        total = w * fitted + (1.0 - w) * self.base_total
        return {"margin": margin, "total": total, "fitted_total": fitted}

    def baseline(self, home, away):
        """Naive comparator: constant home-court margin, league-mean total."""
        return {"margin": self.base_margin, "total": self.base_total}


RIDGE_GRID = [0.5, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0]
BLEND_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]


def select_hyperparameters(history):
    """Choose ridge and totals blend from PAST games only.

    ``history`` is split at 80% by date order; every candidate is fitted on
    the first part and scored on the second.  Nothing from the date being
    forecast takes part in the choice, so this is not look-ahead -- it is the
    same thing a person does when they tune on last season and bet this one.
    """
    if len(history) < 30:
        return RIDGE, 1.0
    cut = int(len(history) * 0.8)
    fit_g, val_g = history[:cut], history[cut:]
    if not fit_g or not val_g:
        return RIDGE, 1.0

    best_ridge, best_r = RIDGE, None
    for lam in RIDGE_GRID:
        e = Engine()
        try:
            e.fit(fit_g, ridge=lam)
        except ValueError:
            continue
        errs = []
        for g in val_g:
            pr = e.predict(g["home"], g["away"])
            if pr:
                errs.append((g["home_pts"] - g["away_pts"]) - pr["margin"])
        r = rmse(errs)
        if r is not None and (best_r is None or r < best_r):
            best_r, best_ridge = r, lam

    e = Engine()
    e.fit(fit_g, ridge=best_ridge)
    best_w, best_t = 1.0, None
    for w in BLEND_GRID:
        errs = []
        for g in val_g:
            pr = e.predict(g["home"], g["away"], blend=w)
            if pr:
                errs.append((g["home_pts"] + g["away_pts"]) - pr["total"])
        t = rmse(errs)
        if t is not None and (best_t is None or t < best_t):
            best_t, best_w = t, w
    return best_ridge, best_w


def walk_forward(games, burn_in=BURN_IN):
    """Refit for every date from strictly-earlier games, forecast that date.

    Games are processed in date batches so a game never sees another game
    played the same day (an earlier session's pipeline had exactly this
    leakage bug; batching by date is what removes it).
    """
    by_date = defaultdict(list)
    for g in games:
        by_date[g["date"]].append(g)
    dates = sorted(by_date)

    out = []
    for i, d in enumerate(dates):
        history = [g for dd in dates[:i] for g in by_date[dd]]
        if len(history) < burn_in:
            continue
        ridge, blend = select_hyperparameters(history)
        eng = Engine()
        eng.fit(history, ridge=ridge)
        eng.total_blend = blend
        preds = {}
        for g in by_date[d]:
            p = eng.predict(g["home"], g["away"])
            b = eng.baseline(g["home"], g["away"])
            if p is None:
                continue
            preds[g["gid"]] = {
                "pred_margin": p["margin"],
                "pred_total": p["total"],
                "base_margin": b["margin"],
                "base_total": b["total"],
            }
        out.append({"date": d, "n_history": len(history), "preds": preds,
                    "ridge": ridge, "total_blend": blend})
    return out


def last_played(dates_by_team, team, date):
    """Most recent date strictly before ``date`` on which ``team`` played."""
    prev = [d for d in dates_by_team.get(team, []) if d < date]
    return max(prev) if prev else None


def days_between(a, b):
    from datetime import date as _d
    ya, ma, da = (int(x) for x in a.split("-"))
    yb, mb, db = (int(x) for x in b.split("-"))
    return (_d(yb, mb, db) - _d(ya, ma, da)).days


def rest_map(all_games, extra_dates=None):
    """date -> team -> rest days.  None when a team has no earlier game on
    record (start of the captured season), which keeps the cell blank rather
    than inventing an off-season."""
    played = defaultdict(list)
    for g in all_games:
        played[g["home"]].append(g["date"])
        played[g["away"]].append(g["date"])
    if extra_dates:
        for team, ds in extra_dates.items():
            for d in ds:
                if d not in played[team]:
                    played[team].append(d)
    for t in played:
        played[t].sort()

    rest = {}
    for g in all_games:
        for side in ("home", "away"):
            prev = last_played(played, g[side], g["date"])
            rest[(g["date"], g[side])] = (
                days_between(prev, g["date"]) if prev else None)
    return rest, played


# --------------------------------------------------------------------------
# strategies
# --------------------------------------------------------------------------
# Each rule is a predicate over one priced game.  It returns +1 to back the
# home side / the over, -1 to back the away side / the under, or None to pass.
# ``market`` is one of "spread", "total", "sgp", "cross".
#
# The rules deliberately test *our own line*, because that is the only line we
# have.  A rule that wins more than half the time against our own fair line is
# evidence that our line is biased in that subset -- which is the thing worth
# knowing before any money is risked anywhere.

def r_home_big_fav(g):
    return 1 if g["pred_margin"] >= 8 else None


def r_fade_home_big_fav(g):
    return -1 if g["pred_margin"] >= 8 else None


def r_away_big_fav(g):
    return -1 if g["pred_margin"] <= -8 else None


def r_fade_away_big_fav(g):
    return 1 if g["pred_margin"] <= -8 else None


def r_under_high_total(g):
    """Top tercile of projected totals, measured against the totals we had
    ALREADY projected for strictly earlier games.

    The first draft of this board used a fixed 235 points.  Once the totals
    model was shrunk toward the league mean (see select_hyperparameters) the
    projections all landed between 223 and 232 and the fixed rule selected two
    games.  A threshold that dies when the model improves is not a strategy, it
    is an artefact, so the cut is now a rolling tercile of our own prior
    projections -- declared in advance, recomputed from the past only.
    """
    return -1 if g.get("total_high") else None


def r_over_high_total(g):
    return 1 if g.get("total_high") else None


def r_over_low_total(g):
    return 1 if g.get("total_low") else None


def r_under_low_total(g):
    return -1 if g.get("total_low") else None


def r_back_rested(g):
    if g.get("rest_diff") is None:
        return None
    if g["rest_diff"] >= 2:
        return 1
    if g["rest_diff"] <= -2:
        return -1
    return None


def r_fade_rested(g):
    s_ = r_back_rested(g)
    return -s_ if s_ is not None else None


def r_back_home_vs_b2b_road(g):
    return 1 if g.get("away_rest") == 1 else None


def r_fade_home_b2b(g):
    return -1 if g.get("home_rest") == 1 else None


def r_always_home(g):
    return 1


def r_sgp_side_and_over(g):
    """Same-game parlay: model side covers AND the game goes over our total."""
    return 1


def r_cross_two_sides(g):
    """Cross-game parlay leg: back the model side (the home side when our
    margin is positive, otherwise the away side)."""
    return 1 if g["pred_margin"] >= 0 else -1


# --- form / recent-result features, all strictly from earlier games -------
# Computed from the verified results log only, and only from games with a date
# strictly before the game being priced, so they satisfy the same no-look-ahead
# rule the ratings do (assert_no_lookahead covers the walk-forward fit; the
# form block is asserted separately, see tests/test_strategy_lab_df301475.py).
def build_team_history(games, graded):
    """team -> sorted [(date, margin, ot, model_err)] from the results log.

    ``model_err`` is positive when the team beat OUR line expectation (its
    actual margin exceeded the margin we had projected for it).  Only games that
    carry a walk-forward prediction have an error term, so the feature is
    missing for the burn-in games rather than imputed.
    """
    hist = defaultdict(list)
    err_by_gid = {}
    for g in graded:
        err_by_gid[g["gid"]] = g["act_margin"] - g["pred_margin"]
    for g in games:
        m = g["home_pts"] - g["away_pts"]
        e = err_by_gid.get(g["gid"])
        hist[g["home"]].append((g["date"], m, bool(g["ot"]), None if e is None else e))
        hist[g["away"]].append((g["date"], -m, bool(g["ot"]),
                               None if e is None else -e))
    for t in hist:
        hist[t].sort(key=lambda x: x[0])
    return hist


def prior_features(hist, team, date, key):
    """One feature of ``team``'s most recent game strictly before ``date``."""
    prev = [h for h in hist.get(team, []) if h[0] < date]
    if not prev:
        return None
    last = prev[-1]
    if key == "margin":
        return last[1]
    if key == "ot":
        return last[2]
    if key == "err":
        return last[3]
    if key == "streak":
        n = 0
        for (_, m, _, _) in reversed(prev):
            if m > 0 and n >= 0:
                n += 1
            elif m < 0 and n <= 0:
                n -= 1
            else:
                break
        return n
    if key == "last3":
        xs = [m for (_, m, _, _) in prev[-3:]]
        return mean(xs) if xs else None
    return None


def r_bounce_loss(g):
    """Back the team that lost its previous game by 15 or more."""
    h = g.get("home_prev_margin")
    a = g.get("away_prev_margin")
    h_bad = h is not None and h <= -15
    a_bad = a is not None and a <= -15
    if h_bad and not a_bad:
        return 1
    if a_bad and not h_bad:
        return -1
    return None


def r_fade_bounce(g):
    v = r_bounce_loss(g)
    return None if v is None else -v


def r_letdown(g):
    """Fade the team that won its previous game by 20 or more."""
    h = g.get("home_prev_margin")
    a = g.get("away_prev_margin")
    h_hot = h is not None and h >= 20
    a_hot = a is not None and a >= 20
    if h_hot and not a_hot:
        return -1
    if a_hot and not h_hot:
        return 1
    return None


def r_fade_letdown(g):
    v = r_letdown(g)
    return None if v is None else -v


def r_follow_model_error(g):
    """Back the team our PREVIOUS line under-rated by 4 points or more.

    This rule is not a market hypothesis at all: it asks whether our own engine
    has a short-run bias a bettor could anticipate.  If it wins, the engine is
    slow, and the honest response is to fix the engine rather to place bets.
    """
    h = g.get("home_prev_err")
    a = g.get("away_prev_err")
    h_hi = h is not None and h >= 4.0
    a_hi = a is not None and a >= 4.0
    if h_hi and not a_hi:
        return 1
    if a_hi and not h_hi:
        return -1
    return None


def r_fade_model_error(g):
    v = r_follow_model_error(g)
    return None if v is None else -v


def r_fresh_over(g):
    """Both teams on 2+ days' rest: the legs are there, take the over."""
    h, a = g.get("home_rest"), g.get("away_rest")
    if h is None or a is None:
        return None
    return 1 if (h >= 2 and a >= 2) else None


def r_fresh_under(g):
    v = r_fresh_over(g)
    return None if v is None else -v


# Declared mirror pairs: same games, opposite side.  The board must show them
# as ONE finding, and tests/test_strategy_lab_df301475.py asserts the
# declaration is true (identical selection sets, complementary outcomes) instead
# of trusting the prose.
MIRROR_PAIRS = [("ST-01", "ST-02"), ("ST-03", "ST-04"), ("ST-05", "ST-06"),
                ("ST-07", "ST-08"), ("ST-09", "ST-10"),
                ("ST-17", "ST-18"), ("ST-19", "ST-20"),
                ("ST-21", "ST-22"), ("ST-23", "ST-24")]

# baseline_rate: the hit rate a rule would produce if our own line were fair.
#   0.50 for a single bet into our own spread or total;
#   0.25 for a fair two-leg parlay (0.5 x 0.5) -- scoring a parlay against 50%
#   would award it a "signal" for simply being two legs, which is a bug that
#   put a losing same-game parlay at the top of an earlier draft of this board.
# payout: profit per 1 unit staked on a win, at an assumed -110 per leg.
#   singles: 100/110 = 0.9091.  two-leggers: (1 + 100/110)^2 - 1 = 2.6446.
SINGLE_BASELINE = 0.5
PARLAY2_BASELINE = 0.25
SINGLE_PAYOUT = 100.0 / 110.0
PARLAY2_PAYOUT = (1.0 + 100.0 / 110.0) ** 2 - 1.0

STRATEGY_DEFS = [
    # id, family, name, market, predicate, plain-English rule, baseline, payout
    ("ST-01", "Single bet - spread", "Back big home favourites", "spread",
     r_home_big_fav, "When our originated spread favours the home team by 8 or more, back the home team.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-02", "Single bet - spread", "Fade big home favourites", "spread",
     r_fade_home_big_fav, "Mirror of ST-01: the same games, the other side.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-03", "Single bet - spread", "Back big road favourites", "spread",
     r_away_big_fav, "When our originated spread favours the away team by 8 or more, back the away team.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-04", "Single bet - spread", "Fade big road favourites", "spread",
     r_fade_away_big_fav, "Mirror of ST-03: the same games, the other side.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-05", "Single bet - total", "Unders in the highest-projected totals", "total",
     r_under_high_total, "When our originated total is in the top tercile of the totals we had already projected, take the under.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-06", "Single bet - total", "Overs in the highest-projected totals", "total",
     r_over_high_total, "Mirror of ST-05: the same games, the other side.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-07", "Single bet - total", "Overs in the lowest-projected totals", "total",
     r_over_low_total, "When our originated total is in the bottom tercile of the totals we had already projected, take the over.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-08", "Single bet - total", "Unders in the lowest-projected totals", "total",
     r_under_low_total, "Mirror of ST-07: the same games, the other side.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-09", "Single bet - rest", "Back the better-rested team", "spread",
     r_back_rested, "When one team has at least two more rest days than the other, back it against our spread.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-10", "Single bet - rest", "Fade the better-rested team", "spread",
     r_fade_rested, "Mirror of ST-09: the same games, the other side.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-11", "Single bet - rest", "Back home against a road back-to-back", "spread",
     r_back_home_vs_b2b_road, "When the away team is on the second night of a back-to-back, back the home team against our spread.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-12", "Single bet - rest", "Fade the home team on no rest", "spread",
     r_fade_home_b2b, "When the home team is on the second night of a back-to-back, back the away team. Not a mirror of ST-11: a different set of games.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-15", "Parlay - same game", "Side covers AND over", "sgp",
     r_sgp_side_and_over, "Same-game two-legger: our side covers and the game goes over our total. A fair price for this is 25%, not 50%.", PARLAY2_BASELINE, PARLAY2_PAYOUT),
    ("ST-17", "Single bet - form", "Back the team off a 15+ point loss", "spread",
     r_bounce_loss, "When exactly one team lost its previous game by 15 or more, back that team against our spread (the bounce-back hypothesis).", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-18", "Single bet - form", "Fade the team off a 15+ point loss", "spread",
     r_fade_bounce, "Mirror of ST-17: the same games, the other side (the continued-slump hypothesis).", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-19", "Single bet - form", "Fade the team off a 20+ point win", "spread",
     r_letdown, "When exactly one team won its previous game by 20 or more, back the other side (the let-down hypothesis).", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-20", "Single bet - form", "Back the team off a 20+ point win", "spread",
     r_fade_letdown, "Mirror of ST-19: the same games, the other side (momentum).", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-21", "Single bet - calibration", "Back the team our last line under-rated", "spread",
     r_follow_model_error, "When exactly one team beat the margin we had projected for it in its previous game by 4+ points, back that team. Tests our own engine for a short-run bias.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-22", "Single bet - calibration", "Fade the team our last line under-rated", "spread",
     r_fade_model_error, "Mirror of ST-21: over-reaction is the alternative story, and it is scored, not assumed away.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-23", "Single bet - rest x total", "Overs when both teams are on 2+ days' rest", "total",
     r_fresh_over, "Both teams rested at least two days: take the over of our originated total.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-24", "Single bet - rest x total", "Unders when both teams are on 2+ days' rest", "total",
     r_fresh_under, "Mirror of ST-23: the same games, the other side.", SINGLE_BASELINE, SINGLE_PAYOUT),
    ("ST-NUL", "Control", "Back the home team in every game", "spread",
     r_always_home, "Null baseline. It must fail every gate; if it does not, the gates are broken.", SINGLE_BASELINE, SINGLE_PAYOUT),
]

# Prop-combo strategies are listed but cannot be scored at all: player game
# logs were never captured, so the joint distribution does not exist here.
PROP_COMBO_DEFS = [
    ("PC-01", "Two teammates, same game: points and rebounds",
     "Needs per-player game logs to measure the within-game correlation between a player's points and rebounds."),
    ("PC-02", "Two teammates, same game: points and points",
     "Needs per-player game logs to measure how two teammates' scoring moves together."),
    ("PC-03", "Star points and team total, same game",
     "Needs per-player game logs to measure the dependence between one player's scoring and the game total."),
    ("PC-04", "Points and assists, same player",
     "Needs per-player game logs; usage correlation is not published anywhere official."),
]


# --------------------------------------------------------------------------
# strategy evaluation
# --------------------------------------------------------------------------
def grade_game(g, side):
    """Did the selection win against our own originated line?

    ``side`` is +1 for home/over, -1 for away/under.  A push against our own
    line has probability zero (our line is a real number), so every graded
    game resolves to a win or a loss.
    """
    if g["market"] == "spread":
        actual = g["act_margin"]
        pred = g["pred_margin"]
        diff = actual - pred          # >0 favours the home side
        return (diff > 0) if side > 0 else (diff < 0)
    if g["market"] == "total":
        actual = g["act_total"]
        pred = g["pred_total"]
        diff = actual - pred
        return (diff > 0) if side > 0 else (diff < 0)
    return None


def evaluate(strategy_id, name, family, market, rule, rule_text, graded,
             rng, baseline=SINGLE_BASELINE, payout=SINGLE_PAYOUT):
    """Run one rule over the graded walk-forward games and score it.

    ``baseline`` is the hit rate the rule would post if our own line in that
    market were fair.  Every significance test, every edge and every ROI uses
    it, so a two-leg parlay is never compared against a single-bet 50%.
    """
    picks = []
    for g in graded:
        side = rule(g)
        if side is None:
            continue
        if market == "sgp":
            leg_side = 1 if g["pred_margin"] >= 0 else -1
            win = (grade_game({**g, "market": "spread"}, leg_side)
                   and grade_game({**g, "market": "total"}, 1))
            picks.append({"date": g["date"], "gid": g["gid"], "win": bool(win)})
        else:
            win = grade_game({**g, "market": market}, side)
            picks.append({"date": g["date"], "gid": g["gid"], "win": bool(win)})

    n = len(picks)
    rec = {
        "id": strategy_id, "family": family, "name": name, "market": market,
        "rule": rule_text, "baseline": baseline, "payout": payout,
        "n": n, "wins": sum(1 for p in picks if p["win"]),
        "rate": None, "edge_pp": None, "roi_pct": None,
        "p_two_sided": None, "p_one_sided": None, "q_value": None,
        "p_family": None, "ci_low": None, "ci_high": None,
        "roi_ci_low": None, "roi_ci_high": None, "n_required": None,
        "half_first": None, "half_second": None, "stable": None,
        "directional": None, "score": 0.0, "tier": "", "tier_label": "",
        "stake": "", "verdict": "", "gates": [], "blocked": False,
        "block_reason": "", "note": "", "sources": [SRC_GAMES],
        "dates": sorted({p["date"] for p in picks}),
    }

    if n == 0:
        rec["blocked"] = True
        rec["block_reason"] = "The rule selected no games in the walk-forward sample."
        rec["verdict"] = "NOT TESTABLE"
        rec["tier"] = "T5"
        assign_tier(rec)
        return rec, picks

    wins = rec["wins"]
    rate = wins / n
    rec["rate"] = rate
    rec["directional"] = bool(rate > baseline)
    rec["edge_pp"] = (rate - baseline) * 100.0
    # ROI at an assumed price: win ``payout`` per unit, lose 1 per unit.
    rec["roi_pct"] = ((wins * payout - (n - wins)) / n) * 100.0

    rec["p_two_sided"] = binom_two_sided(wins, n, baseline)
    rec["p_one_sided"] = binom_one_sided(wins, n, baseline)
    lo, hi = wilson_interval(wins, n)
    rec["ci_low"], rec["ci_high"] = lo, hi
    rec["n_required"] = required_n(rate, baseline=baseline)

    # --- date-block bootstrap: hit rate and ROI ---------------------------
    # Betting results cluster by date (same slate, same travel, same news),
    # so the resampling unit is the date, not the individual bet.
    win_by_date = defaultdict(lambda: [0, 0])
    for p in picks:
        win_by_date[p["date"]][1] += 1
        if p["win"]:
            win_by_date[p["date"]][0] += 1
    keys = sorted(win_by_date)
    boots, boot_roi = [], []
    for _ in range(BOOTSTRAP):
        tw = tc = 0
        for _ in range(len(keys)):
            k = keys[rng.randrange(len(keys))]
            tw += win_by_date[k][0]
            tc += win_by_date[k][1]
        if tc:
            boots.append(tw / tc)
            boot_roi.append(((tw * payout - (tc - tw)) / tc) * 100.0)
    if boots:
        boots.sort()
        rec["ci_low"] = boots[int(0.025 * len(boots))]
        rec["ci_high"] = boots[min(len(boots) - 1, int(0.975 * len(boots)))]
    if boot_roi:
        boot_roi.sort()
        rec["roi_ci_low"] = boot_roi[int(0.025 * len(boot_roi))]
        rec["roi_ci_high"] = boot_roi[min(len(boot_roi) - 1, int(0.975 * len(boot_roi)))]

    # --- stability: direction must hold in both halves --------------------
    half = n // 2
    first, second = picks[:half], picks[half:]
    r1 = sum(1 for p in first if p["win"]) / len(first) if first else None
    r2 = sum(1 for p in second if p["win"]) / len(second) if second else None
    rec["half_first"], rec["half_second"] = r1, r2
    rec["stable"] = bool(r1 is not None and r2 is not None
                         and (r1 - baseline) * (r2 - baseline) > 0)
    return rec, picks


def family_luck_test(strategies, rng):
    """How big an edge can luck produce somewhere in a board this size?

    Every rule is simulated under its own fair-line null (each selected game
    is a coin flip at the rule's baseline), the LARGEST absolute edge anywhere
    on the board is recorded, and that is repeated.  The result is the
    distribution of the best-looking finding a board of this size throws up
    when nothing is real.

    Reporting only each rule's own p-value would be the classic leaderboard
    error: with this many rules, one of them looks significant by chance.  The
    95th percentile below is the edge a rule must beat to be called anything.
    """
    specs = [(r["n"], r["baseline"]) for r in strategies
             if not r["blocked"] and r["n"] >= 5]
    if not specs:
        return {"iterations": 0, "threshold_pp": None, "rules": len(specs)}
    maxes = []
    for _ in range(PERMUTATIONS):
        best = 0.0
        for n, base in specs:
            # normal approximation to Binomial(n, base); n >= 5, base in {0.25, 0.5}
            sd = math.sqrt(n * base * (1 - base))
            k = int(round(n * base + rng.gauss(0, sd)))
            k = min(n, max(0, k))
            edge = abs(k / n - base) * 100.0
            if edge > best:
                best = edge
        maxes.append(best)
    maxes.sort()
    thresh = maxes[min(len(maxes) - 1, int(0.95 * len(maxes)))]
    return {
        "iterations": PERMUTATIONS,
        "rules": len(specs),
        "threshold_pp": thresh,
        "median_pp": maxes[len(maxes) // 2],
        "max_pp": maxes[-1],
        "method": ("Each rule simulated under its own fair-line null; the largest "
                   "absolute edge on the board per iteration; 95th percentile "
                   "reported as the luck threshold."),
    }


def apply_family_test(strategies, luck):
    """Per-rule p-value against the luck distribution, and gate G9."""
    thresh = luck.get("threshold_pp")
    for r in strategies:
        if r["blocked"] or r["n"] < 5:
            r["p_family"] = None
            continue
        if not r["directional"]:
            # A rule that LOSES against its own fair line cannot be "skill"
            # however large the deviation is; its mirror is the candidate.
            r["p_family"] = 1.0
            continue
        if thresh is None:
            r["p_family"] = None
            continue
        r["p_family"] = 0.0 if r["edge_pp"] >= thresh else 1.0


def annotate_mirrors(strategies):
    """Mark complementary pairs.

    "Back big home favourites" and "Fade big home favourites" select exactly
    the same games and are exact complements: if one wins 71% the other wins
    29%.  They are ONE finding, not two, and the board must say so -- otherwise
    a board of 16 rules reads like 16 independent pieces of evidence when it
    is closer to eight.
    """
    pairs = MIRROR_PAIRS
    by_id = {r["id"]: r for r in strategies}
    for a, b in pairs:
        ra, rb = by_id.get(a), by_id.get(b)
        if not ra or not rb:
            continue
        ra["mirror_of"] = b
        rb["mirror_of"] = a
        # the winner of the pair is the one above its baseline
        if (ra["rate"] or 0) > ra["baseline"]:
            ra["mirror_note"] = (f"Complement of {b}: same games, opposite side. "
                                 f"{b} wins {100 - (ra['rate'] or 0) * 100:.1f}% of them. "
                                 f"These are one finding, not two.")
            rb["mirror_note"] = (f"Complement of {a}: same games, opposite side. "
                                 f"{a} wins {(ra['rate'] or 0) * 100:.1f}% of them, so this "
                                 f"direction loses. The signal, if any, is on the other side.")
        else:
            rb["mirror_note"] = (f"Complement of {a}: same games, opposite side. "
                                 f"{a} wins {(rb['rate'] or 0) * 100:.1f}% of them. "
                                 f"These are one finding, not two.")
            ra["mirror_note"] = (f"Complement of {b}: same games, opposite side. "
                                 f"{b} wins {(rb['rate'] or 0) * 100:.1f}% of them, so this "
                                 f"direction loses. The signal, if any, is on the other side.")
    for r in strategies:
        r.setdefault("mirror_of", "")
        r.setdefault("mirror_note", "")


def assign_tier(rec):
    """Reward tier and stake, from the gates actually passed."""
    if rec.get("blocked"):
        rec["tier"] = "T5"
        rec["tier_label"] = "Blocked - collect the data first"
        rec["stake"] = "No stake. No data exists to score this rule."
        return
    passed = {g["id"]: g["passed"] for g in rec.get("gates", [])}
    all_pass = all(passed.values()) if passed else False
    if all_pass:
        rec["tier"] = "T1"
        rec["tier_label"] = "Funded"
        rec["stake"] = "Full unit, subject to the legal gate (Q-LEG-01) and a licensed price feed (Q-03)."
    elif all(v for k, v in passed.items() if k != "G3"):
        rec["tier"] = "T2"
        rec["tier_label"] = "Provisional - signal present, sample under-powered"
        rec["stake"] = "Quarter unit, paper only. Re-score at n >= 100."
    elif passed.get("G5"):
        rec["tier"] = "T3"
        rec["tier_label"] = "Watch - raw signal, incomplete evidence"
        rec["stake"] = "Paper tracking only, no stake."
    else:
        rec["tier"] = "T4"
        rec["tier_label"] = "Rejected - no evidence of skill"
        rec["stake"] = "No stake."
    if not passed.get("G5"):
        rec["tier"] = "T4"
        rec["tier_label"] = "Rejected - not distinguishable from luck"
        rec["stake"] = "No stake."
    if not rec.get("directional"):
        rec["tier"] = "T4"
        rec["tier_label"] = "Rejected - this direction loses; the mirror is the candidate"
        rec["stake"] = "No stake on this side."


def apply_gates(rec, family_p=None, luck=None, log_n=None):
    """Nine gates.  G1 and G2 are design rules satisfied by construction and
    separately asserted; G3-G9 are measured."""
    n = rec["n"]
    p = rec["p_two_sided"]
    q = rec["q_value"]
    base = rec["baseline"]
    gates = []

    def add(gid, gname, passed, value, note=""):
        gates.append({"id": gid, "name": gname, "passed": bool(passed),
                      "value": value, "note": note})

    add("G1", "Every input has an official or reproducible source", True,
        "pass", "%s official final scores; ratings refit per date."
        % (f"{log_n} games" if log_n else "the captured results log"))
    add("G2", "No look-ahead: every feature exists before tip-off", True,
        "pass", "Ratings refit from games with a strictly earlier date.")
    add("G3", f"Out-of-sample sample size n >= {GATE_MIN_N}", n >= GATE_MIN_N,
        f"n = {n}", "Threshold proposed by this session, not approved by the owner.")
    need = rec["n_required"]
    add("G4", "Observed effect is powered at 80%",
        bool(need is not None and need <= n),
        ("n needed %.0f" % need) if need else "no measurable effect",
        "Normal approximation, alpha 0.05 two-sided, power 0.80.")
    add("G5", f"Distinguishable from luck (exact binomial vs the {base:.0%} fair-line rate, p < {GATE_ALPHA})",
        p is not None and p < GATE_ALPHA,
        "p = %.4f" % p if p is not None else "n/a")
    add("G6", f"Survives Benjamini-Hochberg FDR {GATE_FDR}",
        q is not None and q <= GATE_FDR,
        "q = %.4f" % q if q is not None else "n/a",
        "Adjusted across the %d scored rules on this board." % (family_p or 0))
    add("G7", "Direction stable in both halves of the sample", bool(rec["stable"]),
        ("first %.3f, second %.3f" % (rec["half_first"], rec["half_second"]))
        if rec["half_first"] is not None else "n/a",
        f"Both halves must sit on the same side of the {base:.0%} fair-line rate.")
    add("G8", "Return interval excludes zero at an assumed price",
        bool(rec["roi_ci_low"] is not None and rec["roi_ci_low"] > 0),
        ("95%% interval %.1f%% to %.1f%%" % (rec["roi_ci_low"], rec["roi_ci_high"]))
        if rec["roi_ci_low"] is not None else "n/a",
        "Measured against our own line at an assumed price. Not an economic result: "
        "no licensed odds feed is connected.")
    thr = (luck or {}).get("threshold_pp")
    add("G9", "Beats the best edge this board can produce by luck alone",
        bool(rec["p_family"] is not None and rec["p_family"] <= 0.05),
        ("edge %.1f pp vs luck threshold %.1f pp" % (rec["edge_pp"], thr))
        if (thr is not None and rec["edge_pp"] is not None) else "n/a",
        "95th percentile of the largest edge across %d rules simulated under the "
        "fair-line null, %d iterations." % ((luck or {}).get("rules", 0),
                                            (luck or {}).get("iterations", 0)))

    rec["gates"] = gates

    # --- composite skill score -------------------------------------------
    if rec["blocked"] or n < 5:
        rec["score"] = 0.0
    else:
        ev = min(1.0, (-math.log10(max(p, 1e-12))) / 3.0) if p else 0.0
        # only a POSITIVE edge scores: the losing side of a mirror pair is not
        # a strategy, it is the other side of one.
        ef = min(1.0, max(0.0, rec["edge_pp"]) / 8.0)
        st = 1.0 if (rec["stable"] and rec["directional"]) else 0.0
        fd = 1.0 if (q is not None and q <= GATE_FDR and rec["directional"]) else 0.0
        score = 30 * ev + 30 * ef + 20 * st + 20 * fd
        if n < GATE_MIN_N:
            score = min(score, 55.0)
        if n < 30:
            score = min(score, 30.0)
        rec["score"] = round(score, 1)

    assign_tier(rec)
    passed = {g["id"]: g["passed"] for g in gates}
    if rec["tier"] == "T1":
        rec["verdict"] = "PASSES ALL GATES"
    elif rec["tier"] == "T2":
        missing = [k for k, v in passed.items() if not v]
        rec["verdict"] = "PROVISIONAL - fails " + ", ".join(missing)
    elif rec["tier"] == "T3":
        rec["verdict"] = "WATCH - raw signal only"
    elif rec["tier"] == "T4" and not rec["directional"]:
        rec["verdict"] = "REJECTED - this direction loses against our own line"
    else:
        rec["verdict"] = "FAILS - no evidence of skill"


# --------------------------------------------------------------------------
# correlations
# --------------------------------------------------------------------------
def hist_all(games):
    """team -> chronological [(date, margin, ot)] over the official results log.

    Shared by the correlation block: "margin" is from the team's point of view,
    so one game contributes one row to each of its two teams.
    """
    out = defaultdict(list)
    for g in games:
        m = g["home_pts"] - g["away_pts"]
        out[g["home"]].append((g["date"], m, bool(g["ot"])))
        out[g["away"]].append((g["date"], -m, bool(g["ot"])))
    for t in out:
        out[t].sort(key=lambda x: x[0])
    return out


def date_of(iso):
    import datetime
    y, m, d = (int(x) for x in iso.split("-"))
    return datetime.date(y, m, d)


def build_correlations(games, graded, player_logs_available=False, rng=None,
                       ratings=None):
    rows = []
    graded_err = {g["gid"]: g["act_margin"] - g["pred_margin"] for g in graded}

    # 1. Home points vs away points, over the whole captured season.
    hp = [g["home_pts"] for g in games]
    ap = [g["away_pts"] for g in games]
    r = pearson(hp, ap)
    lo, hi = fisher_ci(r, len(hp))
    rows.append({
        "pair": "Home points vs away points (same game)", "stat": "Pearson r",
        "value": r, "ci95": [lo, hi], "n": len(hp), "verified": True,
        "source": SRC_GAMES,
        "note": "Computed from the %d official final scores. This is the number that "
                "decides whether a same-game side+total parlay is fairly priced as "
                "independent." % len(hp),
    })

    # 2. Margin residual vs total residual, out of sample.
    mres = [g["act_margin"] - g["pred_margin"] for g in graded]
    tres = [g["act_total"] - g["pred_total"] for g in graded]
    r2 = pearson(mres, tres)
    lo2, hi2 = fisher_ci(r2, len(mres))
    rows.append({
        "pair": "Originated-spread residual vs originated-total residual",
        "stat": "Pearson r", "value": r2, "ci95": [lo2, hi2], "n": len(mres),
        "verified": True, "source": SRC_GAMES,
        "note": "Out-of-sample residuals from the walk-forward run. The key input for "
                "pricing a same-game parlay that combines a side with a total. The "
                "interval includes zero, so independence is not rejected here.",
    })

    # 3. Joint hit rate of the same-game parlay vs independence.
    indep = sum(1 for g in graded if grade_game({**g, "market": "spread"},
                                                1 if g["pred_margin"] >= 0 else -1))
    joint = sum(1 for g in graded
                if grade_game({**g, "market": "spread"}, 1 if g["pred_margin"] >= 0 else -1)
                and grade_game({**g, "market": "total"}, 1))
    n3 = len(graded)
    p_side = indep / n3
    p_over = sum(1 for g in graded if g["act_total"] > g["pred_total"]) / n3
    joint_rate = joint / n3
    indep_rate = p_side * p_over
    phi = None
    if 0 < p_side < 1 and 0 < p_over < 1:
        phi = ((joint_rate - indep_rate)
               / math.sqrt(p_side * (1 - p_side) * p_over * (1 - p_over)))
    rows.append({
        "pair": "Cover (vs our spread) AND over (vs our total), same game",
        "stat": "phi (binary association)", "value": phi, "ci95": [None, None],
        "n": n3, "verified": True, "source": SRC_GAMES,
        "note": ("Joint hit rate %.4f vs %.4f under independence; dependence ratio %.3f. "
                 "A ratio above 1.0 means the two legs land together more often than "
                 "independent pricing assumes, which is how a book protects itself on "
                 "same-game parlays." % (joint_rate, indep_rate,
                                         (joint_rate / indep_rate) if indep_rate else 0)),
    })

    # 4. Cross-game dependence, measured instead of assumed.  Legs of a
    #    cross-game parlay that share a date are only independent if the
    #    residuals of the games on that date are uncorrelated; the test is a
    #    within-date Pearson r with a permutation null that shuffles residual
    #    values inside each date (which preserves the date structure and so
    #    cannot manufacture significance by resampling across nights).
    if rng is not None:
        by_date = defaultdict(list)
        for g in graded:
            by_date[g["date"]].append(g)
        for label, getter in (("margin", lambda g: g["act_margin"] - g["pred_margin"]),
                              ("total", lambda g: g["act_total"] - g["pred_total"])):
            pairs_ = []
            for d, gs in sorted(by_date.items()):
                vals = [getter(g) for g in gs]
                for i in range(len(vals)):
                    for j in range(i + 1, len(vals)):
                        pairs_.append((vals[i], vals[j]))
            if len(pairs_) < 20:
                continue
            xs, ys = [x for x, _ in pairs_], [y for _, y in pairs_]
            r_obs = pearson(xs, ys)
            null_vals = [v for _, v in pairs_]
            slots = []
            for d, gs in sorted(by_date.items()):
                idx = [k for k, g in enumerate(graded) if g["date"] == d]
                slots.append(idx)
            n_perm = 400
            extremes = 0
            flat = [getter(g) for g in graded]
            for _ in range(n_perm):
                shuffled = flat[:]
                for idx in slots:
                    got = [flat[idx[k]] for k in range(len(idx))]
                    rng.shuffle(got)
                    for pos, k in enumerate(idx):
                        shuffled[k] = got[pos]
                pv = []
                for d, gs in sorted(by_date.items()):
                    idx = [k for k, g in enumerate(graded) if g["date"] == d]
                    vals = [shuffled[k] for k in idx]
                    for i in range(len(vals)):
                        for j in range(i + 1, len(vals)):
                            pv.append((vals[i], vals[j]))
                if len(pv) == len(pairs_):
                    rp = pearson([x for x, _ in pv], [y for _, y in pv])
                    if rp is not None and r_obs is not None and abs(rp) >= abs(r_obs):
                        extremes += 1
            p_perm = (extremes + 1) / (n_perm + 1)
            lo_, hi_ = fisher_ci(r_obs, len(pairs_)) if r_obs is not None else (None, None)
            rows.append({
                "pair": f"Same-night games: {label} residuals of one game vs the other",
                "stat": "Pearson r (within-date pairs)", "value": r_obs,
                "ci95": [lo_, hi_], "n": len(pairs_), "verified": True,
                "source": SRC_GAMES,
                "note": (f"Derived (our arithmetic on the official final scores), not an "
                         f"official statistic. {len(pairs_)} same-night game pairs. "
                         f"Permutation p = {p_perm:.3f} from {n_perm} within-date "
                         f"reshuffles. A value near 0 is what cross-game parlay pricing "
                         f"assumes; the interval, not the point estimate, is the finding."),
            })

    # 5. Rest advantage and recent form, measured on the official log.
    rd = [(g["rest_diff"], g["act_margin"]) for g in graded
          if g.get("rest_diff") is not None]
    if len(rd) >= 20:
        r5 = pearson([x[0] for x in rd], [x[1] for x in rd])
        lo5, hi5 = fisher_ci(r5, len(rd))
        rows.append({
            "pair": "Rest-days differential vs actual home margin",
            "stat": "Pearson r", "value": r5, "ci95": [lo5, hi5], "n": len(rd),
            "verified": True, "source": SRC_GAMES,
            "note": "Derived. Rest days are counted from the official schedule and the "
                    "official results log; the margin is the official final score. The "
                    "interval is the result to read: if it covers 0 the sample cannot "
                    "support a rest-based angle, whatever the point estimate says.",
        })
    # 4b. Engine drift: is OUR error predictable?  A rule that beats our own
    #     line by repeating our previous error (ST-21) is only interesting if
    #     the error is autocorrelated, so the autocorrelation is published next
    #     to the rule instead of being argued in prose.  Pairs are consecutive
    #     games by the same team, always (earlier, later), never (later,
    #     earlier), so the measure has no look-ahead in it.
    err_pairs = []
    for team, seq in hist_all(games).items():
        pass  # placeholder replaced below
    err_hist = defaultdict(list)
    for g in games:
        e = graded_err.get(g["gid"])
        if e is None:
            continue
        err_hist[g["home"]].append((g["date"], e))
        err_hist[g["away"]].append((g["date"], -e))
    for team, seq in err_hist.items():
        seq.sort(key=lambda x: x[0])
        err_pairs += [(seq[i][1], seq[i + 1][1]) for i in range(len(seq) - 1)
                      if seq[i + 1][0] > seq[i][0]]
    if len(err_pairs) >= 20:
        re_ = pearson([x[0] for x in err_pairs], [x[1] for x in err_pairs])
        loe, hie = fisher_ci(re_, len(err_pairs))
        rows.append({
            "pair": "Our margin error on a team's previous game vs on its next game",
            "stat": "Pearson r", "value": re_, "ci95": [loe, hie], "n": len(err_pairs),
            "verified": True, "source": SRC_GAMES,
            "note": ("Derived: the engine's own out-of-sample residuals, paired across "
                     "consecutive games of the same team. A positive value means our line "
                     "is slow - the team we under-rated last game is likely to beat it "
                     "again - which is a defect to fix in the estimator, not an edge over "
                     "any bookmaker (we are our own counterparty here)."),
        })

    h_all = hist_all(games)
    form = []
    for team, seq in h_all.items():
        # consecutive games by the same team: (previous margin, next margin)
        form += [(seq[i][1], seq[i + 1][1]) for i in range(len(seq) - 1)
                 if seq[i + 1][0] > seq[i][0]]
    if len(form) >= 20:
        r6 = pearson([x[0] for x in form], [x[1] for x in form])
        lo6, hi6 = fisher_ci(r6, len(form))
        rows.append({
            "pair": "A team's margin in its previous game vs in its next game",
            "stat": "Pearson r", "value": r6, "ci95": [lo6, hi6], "n": len(form),
            "verified": True, "source": SRC_GAMES,
            "note": "Derived. The number the let-down and bounce-back rules implicitly "
                    "assume: how much of a team's margin carries from one game to the "
                    "next. Near zero means recent-result rules are choosing noise.",
        })
    after_ot, after_normal = [], []
    for team, seq in h_all.items():
        for i in range(1, len(seq)):
            prev_ot, prev_date = seq[i - 1][2], seq[i - 1][0]
            if seq[i][0] <= prev_date:
                continue
            gap = (date_of(seq[i][0]) - date_of(prev_date)).days
            if gap > 3:
                continue                     # too far apart to call it fatigue
            (after_ot if prev_ot else after_normal).append(seq[i][1])
    if len(after_ot) >= 5 and len(after_normal) >= 5:
        diff = mean(after_ot) - mean(after_normal)
        pool = after_ot + after_normal
        n_ot = len(after_ot)
        extremes = 0
        for _ in range(2000 if rng is None else 400):
            s_ = pool[:]
            if rng is not None:
                rng.shuffle(s_)
            d_ = mean(s_[:n_ot]) - mean(s_[n_ot:])
            if abs(d_) >= abs(diff):
                extremes += 1
        rows.append({
            "pair": "Margin in the game after an overtime game vs after a normal game "
                   "(within 3 days)",
            "stat": "mean difference (points)",
            "value": diff, "ci95": [None, None], "n": len(after_ot) + len(after_normal),
            "verified": True, "source": SRC_GAMES,
            "note": (f"Derived. n = {len(after_ot)} after OT vs {len(after_normal)} after a "
                     f"regulation game; permutation p = "
                     f"{(extremes + 1) / (401):.3f} on a 3-day window. This is the input a "
                     f"'tired team' angle needs; the window choice is ours, not the "
                     f"league's, and a different cut-off is a different number."),
        })

    # 6. Descriptive associations against the official team table.  These use
    #    the season-to-date ratings as captured on the dashboard's as-of date,
    #    so they describe the games that produced those ratings; they are NOT a
    #    walk-forward forecast and are labelled as such wherever they print.
    if ratings and isinstance(ratings, dict) and "teams" in ratings:
        rmap = {t["team"]: t for t in ratings["teams"]}
        nd, pt = [], []
        for g in games:
            a, h = rmap.get(g["away"]), rmap.get(g["home"])
            if not a or not h:
                continue
            if None in (a.get("net_rtg"), h.get("net_rtg"), a.get("pace"), h.get("pace")):
                continue
            nd.append((h["net_rtg"] - a["net_rtg"], g["home_pts"] - g["away_pts"]))
            pt.append((h["pace"] + a["pace"], g["home_pts"] + g["away_pts"]))
        for label, data, note in (
            ("Net-rating differential (official advanced table) vs actual home margin",
             nd, "Descriptive, NOT a forecast: the ratings are season-to-date as of the "
                 "capture, so they already contain the games being compared. It says the "
                 "official rating spread tracks the scoreboard; it does not say a line "
                 "built from it would have been right before tip-off."),
            ("Pace sum (official advanced table) vs actual game total",
             pt, "Descriptive, NOT a forecast, for the same reason as the net-rating row."),
        ):
            if len(data) >= 20:
                rr = pearson([x[0] for x in data], [x[1] for x in data])
                lo_, hi_ = fisher_ci(rr, len(data))
                rows.append({"pair": label, "stat": "Pearson r", "value": rr,
                             "ci95": [lo_, hi_], "n": len(data), "verified": True,
                             "source": SRC_TEAM_STATS, "note": note})

    # 7. Everything that needs per-player game logs: blank by policy.    # 8. Everything that needs per-player game logs: blank by policy.
    for pair, stat, note in [
        ("Player A points vs player B points, same team, same game", "Pearson r",
         "Needs per-player game logs. None were captured, so the cell is blank by "
         "policy rather than filled with an assumption. Probed again on 2026-11-14 "
         "by session arena/df301475-nba3: stats.nba.com is unreachable from this "
         "environment (fetch error), and the nba.com/stats game-log routes "
         "(players/gamelog, players/boxscoregamelog, teams/boxsrctraditional, "
         "teams/boxscoretraditional) all answer 'Content Unavailable'. The only "
         "official per-player game data reachable here is the per-game box-score "
         "page (https://www.nba.com/game/<slug>/<game_id>/box-score), which is one "
         "page per game and cannot be transcribed at the sample size a correlation "
         "needs without hand-keying numbers - which this project does not do."),
        ("Player points vs player rebounds, same player, same game", "Pearson r",
         "Needs per-player game logs. Blank by policy."),
        ("Player points vs player assists, same player, same game", "Pearson r",
         "Needs per-player game logs. Blank by policy."),
        ("Player points vs team total, same game", "Pearson r",
         "Needs per-player game logs. Blank by policy."),
    ]:
        rows.append({"pair": pair, "stat": stat, "value": None, "ci95": [None, None],
                     "n": None, "verified": False, "source": "", "note": note})

    # 5. Cross-game legs: an assumption, published as such.
    rows.append({
        "pair": "Two legs in different games (cross-game parlay)", "stat": "Pearson r",
        "value": 0.0, "ci95": [None, None], "n": None, "verified": False, "source": "",
        "note": ("Assumption, not measurement, for the pricing itself: the two same-night rows "
                 "measured above (margin residuals r = -0.013, total residuals r = -0.062, 588 "
                 "same-night pairs) do not reject independence, but failing to reject is not the "
                 "same as establishing a factorisation, so cross-game parlays keep their "
                 "independent pricing and their caveat. Re-measure as the log grows."),
    })

    return {
        "rows": rows,
        "parlay_joint_rate": joint_rate,
        "parlay_independent_rate": indep_rate,
        "parlay_dependence_ratio": (joint_rate / indep_rate) if indep_rate else None,
        "p_home_cover": p_side,
        "p_over": p_over,
        "n": n3,
        "player_logs_available": player_logs_available,
        "source": SRC_GAMES,
    }


# --------------------------------------------------------------------------
# live window: lines, picks, parlays, props, injuries, game flow
# --------------------------------------------------------------------------
def originate_window(games, slate, ratings, injury, players, resid):
    """Price every game of the live window with the full-history engine."""
    ridge, blend = select_hyperparameters(games)
    eng = Engine()
    eng.fit(games, ridge=ridge)
    eng.total_blend = blend

    # rest context: completed games plus the official 11/13 slate, which is the
    # only source for "team X played last night" once 11/13 games tip off.
    extra = defaultdict(list)
    if os.path.exists(PRIOR_SLATE_JSON):
        for g in jload(PRIOR_SLATE_JSON).get("games", []):
            if g["date"] < "2026-11-14":
                extra[g["home"]].append(g["date"])
                extra[g["away"]].append(g["date"])
    _, played = rest_map(games, extra)

    rat = {t["team"]: t for t in ratings["teams"]}
    players_by_team = defaultdict(list)
    for p in players:
        players_by_team[p["team"]].append(p)
    player_index = {}
    for p in players:
        player_index[player_key(p["player"])] = p

    # injury roll-up by (date, matchup, team)
    inj = defaultdict(list)
    for r in injury["rows"]:
        inj[(r["game_date"], r["matchup"], r["team"])].append(r)
    # Which game dates the newest official report actually covers.  A date with
    # no rows at all is NOT a date with no injuries: it is a date no report has
    # reached yet.  Before this, "no rows" fell through to "submitted, 0 out".
    covered_dates = {r["game_date"] for r in injury["rows"]}

    # scripts/report_availability.py decides each team's state from the official
    # filing rule and the official schedule; this reads its verdict instead of
    # re-deriving it, so the site and the engine can never disagree about it.
    avail_rows = {}
    if os.path.exists(AVAILABILITY_JSON):
        for ar in jload(AVAILABILITY_JSON).get("rows", []):
            avail_rows[(ar["game_id"], ar["team"])] = ar

    out_lines, out_picks, out_flow, out_inj = [], [], [], []

    for g in slate["games"]:
        home, away, gid, date = g["home"], g["away"], g["game_id"], g["date"]
        p = eng.predict(home, away)
        if p is None:
            continue
        margin, total = p["margin"], p["total"]
        sd_m = resid["margin_sd"]
        sd_t = resid["total_sd"]

        p_home_win = 1.0 - norm_cdf((0.0 - margin) / sd_m) if sd_m else None
        p_ot = resid["ot_rate"]

        matchup = f"{away}@{home}"
        key_date = "%s/%s" % (date[5:7], date[8:10]) + "/" + date[0:4]
        key_date = date[5:7] + "/" + date[8:10] + "/" + date[0:4]

        home_rows = inj.get((key_date, matchup, home), [])
        away_rows = inj.get((key_date, matchup, away), [])
        home_ns = any(r["is_team_not_submitted"] for r in home_rows)
        away_ns = any(r["is_team_not_submitted"] for r in away_rows)

        def avail_state(team, rows, ns):
            """One of the four availability states, for one team of one game."""
            ar = avail_rows.get((gid, team))
            if ar:
                return ar
            if key_date not in covered_dates:
                return {"state": "NO_OFFICIAL_REPORT_COVERS_THIS_DATE",
                        "out_count": None, "reprice_after": "", "filing_clause": "",
                        "played_previous_day": None, "out_players": [],
                        "state_reading": ("No official injury report covers "
                                          f"{key_date} yet, so this team's absences are "
                                          "unknown and are left blank rather than counted "
                                          "as zero.")}
            return {"state": (AV_FILED if not ns else "DUE_AND_NOT_FILED"),
                    "out_count": None, "reprice_after": "", "filing_clause": "",
                    "played_previous_day": None, "out_players": [],
                    "state_reading": ""}

        h_av, a_av = avail_state(home, home_rows, home_ns), avail_state(away, away_rows, away_ns)

        def rollup(rows, team):
            """Minutes and production vacated by players listed Out/Doubtful.

            Only the 31 players in the captured minutes table can contribute a
            number.  Everyone else -- and every player whose official row has a
            blank cell -- is counted in ``unknown`` and left out of the sum, so
            the published total is a floor rather than an estimate.
            """
            out_p, question = [], []
            minutes, pts, reb, ast = 0.0, 0.0, 0.0, 0.0
            unknown, team_mismatch = 0, 0
            for r in rows:
                if r["is_team_not_submitted"]:
                    continue
                st = (r["status"] or "").strip()
                if st == "Questionable":
                    question.append(r["player"])
                    continue
                if st not in ("Out", "Doubtful"):
                    continue
                out_p.append(r["player"])
                pi = player_index.get(player_key(r["player"]))
                if pi is not None and pi.get("team") and team and pi["team"] != team:
                    # the names match but the teams do not: refuse the match rather
                    # than credit one club's player to another club's injury list
                    team_mismatch += 1
                    pi = None
                vals = [pi["min"], pi["pts"], pi["reb"], pi["ast"]] if pi else None
                if not vals or any(v is None for v in vals):
                    # not in the captured table, or the official row is blank
                    unknown += 1
                    continue
                minutes += vals[0]
                pts += vals[1]
                reb += vals[2]
                ast += vals[3]
            return {"out": out_p, "questionable": question, "minutes": minutes,
                    "pts": pts, "reb": reb, "ast": ast, "unknown": unknown,
                    "team_mismatch": team_mismatch, "table_size": len(players),
                    "submitted": not any(r["is_team_not_submitted"] for r in rows)}

        h_roll = rollup(home_rows, home)
        a_roll = rollup(away_rows, away)

        # An absence count is only meaningful when the report actually lists the
        # team.  Everywhere else it is blank -- "we do not know" -- never 0.
        def with_state(roll, av):
            state = av["state"]
            known = state == AV_FILED
            roll = dict(roll)
            roll["state"] = state
            roll["out_count"] = len(roll["out"]) if known else None
            roll["known"] = known
            roll["reprice_after"] = av.get("reprice_after", "")
            roll["filing_clause"] = av.get("filing_clause", "")
            roll["b2b"] = av.get("played_previous_day")
            return roll

        h_roll, a_roll = with_state(h_roll, h_av), with_state(a_roll, a_av)
        h_av_state, a_av_state = h_roll["state"], a_roll["state"]
        if h_av_state == AV_FILED and a_av_state == AV_FILED:
            avail_basis = "both teams listed on the newest official report"
        elif AV_FILED in (h_av_state, a_av_state):
            avail_basis = "one side only: the other team is not on the newest official report"
        else:
            avail_basis = "no usable official availability for this date; priced on ratings and rest alone"

        # rest
        def rest_for(team):
            prev = [d for d in played.get(team, []) if d < date]
            return days_between(max(prev), date) if prev else None

        h_rest, a_rest = rest_for(home), rest_for(away)

        pace_h = rat.get(home, {}).get("pace")
        pace_a = rat.get(away, {}).get("pace")
        proj_pace = mean([x for x in (pace_h, pace_a) if x is not None])

        line = {
            "date": date, "time_et": g["time_et"], "away": away, "home": home,
            "game_id": gid, "venue": g["venue"], "city": g["city"],
            "competition": g["competition"], "broadcast": g["broadcast"],
            "nba_game_url": g["nba_game_url"],
            "model_margin": margin,           # home - away
            "orig_spread_home": -margin,      # the line we originate
            "orig_total": total,
            "proj_home_pts": (total + margin) / 2.0,
            "proj_away_pts": (total - margin) / 2.0,
            "margin_lo": margin - 1.959963985 * sd_m,
            "margin_hi": margin + 1.959963985 * sd_m,
            "total_lo": total - 1.959963985 * sd_t,
            "total_hi": total + 1.959963985 * sd_t,
            "p_home_win": p_home_win,
            "p_home_cover": 0.5,              # by construction: our own line
            "p_over": 0.5,
            "fair_ml_home": american_from_prob(p_home_win),
            "fair_ml_away": american_from_prob(None if p_home_win is None else 1 - p_home_win),
            "p_ot": p_ot,
            "p_blowout_15": (norm_cdf((-15 - margin) / sd_m) + 1 - norm_cdf((15 - margin) / sd_m))
            if sd_m else None,
            "pace": proj_pace,
            "out_count_home": h_roll["out_count"], "out_count_away": a_roll["out_count"],
            "out_players_home": h_roll["out"], "out_players_away": a_roll["out"],
            "questionable_home": h_roll["questionable"],
            "questionable_away": a_roll["questionable"],
            "home_reported": h_av_state == AV_FILED,
            "away_reported": a_av_state == AV_FILED,
            "availability_state_home": h_av_state,
            "availability_state_away": a_av_state,
            "availability_basis": avail_basis,
            "reprice_after_home": h_av.get("reprice_after", ""),
            "reprice_after_away": a_av.get("reprice_after", ""),
            "source": SRC_SCHEDULE,
            "source_stats": SRC_TEAM_STATS,
            "source_game": g["nba_game_url"],
            "note": ("Line originated by this session's walk-forward engine. "
                     "No market price is connected, so there is no comparison "
                     "and no claim of value."),
        }
        out_lines.append(line)

        # ---- pick / selection -------------------------------------------
        # quote the side the model favours, as a book would print it
        if margin >= 0:
            lean = "%s %+.1f" % (home, line["orig_spread_home"])
        else:
            lean = "%s %+.1f" % (away, line["orig_spread_home"])
        def avail_note(roll, team):
            if roll["state"] == AV_FILED:
                return None
            return f"{team}: {roll['state'].replace('_', ' ').lower()}" + (
                f" (re-price after {roll['reprice_after']})" if roll["reprice_after"] else "")

        avail = [x for x in (avail_note(h_roll, home), avail_note(a_roll, away)) if x]
        # A four-way flag, because the three cases read very differently:
        # a team that is LATE is a risk; a team whose deadline has not arrived is
        # a schedule; a date no report covers is simply unpriced on availability.
        states = {h_av_state, a_av_state}
        if states == {AV_FILED}:
            flag = "REPORTED"
        elif "DUE_AND_NOT_FILED" in states:
            flag = "PARTIAL_REPORT_LATE"
        elif AV_FILED in states:
            flag = "PARTIAL_REPORT_NOT_DUE_YET"
        elif states == {"NOT_YET_DUE"}:
            flag = "AVAILABILITY_NOT_DUE_YET"
        else:
            flag = "NO_INJURY_REPORT_FOR_DATE"
        out_picks.append({
            "date": date, "time_et": g["time_et"], "away": away, "home": home,
            "game_id": gid, "nba_game_url": g["nba_game_url"],
            "orig_spread_home": line["orig_spread_home"],
            "orig_total": total,
            "fair_ml_home": line["fair_ml_home"],
            "fair_ml_away": line["fair_ml_away"],
            "model_margin_home": margin,
            "p_home_win": p_home_win,
            "side_lean": lean,
            "totals_lean": ("Over %.1f" % total) if total >= resid["avg_total"]
                           else ("Under %.1f" % total),
            "availability_flag": flag,
            "availability_detail": (
                ("Both teams appear as filed on the newest official report (" +
                 injury["report_stamp"] + "), so the absence counts below are real.")
                if flag == "REPORTED" else
                "; ".join(avail) +
                " -- availability is unresolved at capture time, so this game cannot be "
                "treated as a final selection, and its absence count is published blank "
                "rather than as zero."),
            "availability_states": {"home": h_av_state, "away": a_av_state},
            "availability_basis": avail_basis,
            "pricing_note": ("These are our own fair prices against our own originated "
                             "line. No licensed odds feed is connected, so no expected "
                             "value against a bookmaker can be stated and none is claimed."),
            "source": SRC_SCHEDULE,
            "strategy_selections": [],
        })

        # ---- game flow ---------------------------------------------------
        out_flow.append({
            "date": date, "matchup": matchup, "game_id": gid,
            "home": home, "away": away,
            "home_rest": h_rest, "away_rest": a_rest,
            "rest_diff": (h_rest - a_rest) if (h_rest is not None and a_rest is not None) else None,
            "home_b2b": h_rest == 1, "away_b2b": a_rest == 1,
            "pace_home": pace_h, "pace_away": pace_a, "proj_pace": proj_pace,
            "proj_total": total, "league_avg_total": resid["avg_total"],
            "total_vs_league": total - resid["avg_total"],
            "p_home_win": p_home_win,
            "p_ot": p_ot,
            "p_blowout_15": line["p_blowout_15"],
            "margin_sd": sd_m,
            "out_home": h_roll["out_count"], "out_away": a_roll["out_count"],
            "availability_states": {"home": h_av_state, "away": a_av_state},
            "availability_note": (
                "Absence counts are blank for this game: no official report covers it yet, "
                "so nothing is known about who sits out."
                if AV_FILED not in (h_av_state, a_av_state) else
                "Absence counts cover only the side that has filed."),
            "notes": [],
            "source": SRC_SCHEDULE,
            "source_stats": SRC_TEAM_STATS,
        })

        # ---- injury -> rotation minutes -> production --------------------
        for side, team, roll in ((home, home, h_roll), ("away", away, a_roll)):
            out_inj.append({
                "date": date, "matchup": matchup, "game_id": gid,
                "side": side, "team": team,
                "reported": roll["submitted"],
                "rows_listed": len([r for r in (home_rows if side == home else away_rows)
                                    if not r["is_team_not_submitted"]]),
                "out": roll["out"], "questionable": roll["questionable"],
                "availability_state": roll["state"],
                "minutes_vacuum": (roll["minutes"] if roll["out"] else 0.0) if roll["known"] else None,
                "pts_vacuum": (roll["pts"] if roll["out"] else 0.0) if roll["known"] else None,
                "reb_vacuum": (roll["reb"] if roll["out"] else 0.0) if roll["known"] else None,
                "ast_vacuum": (roll["ast"] if roll["out"] else 0.0) if roll["known"] else None,
                "players_without_official_minutes": roll["unknown"],
                "minutes_note": (
                    "No usable official report for this team at this date, so the minutes "
                    "vacated are UNKNOWN and are published blank rather than as zero."
                    if not roll["known"] else
                    ("Sum of the official season minutes-per-game of the players listed "
                     "Out. It is a FLOOR: %d listed player(s) are outside the captured "
                     "%d-player minutes table, so their minutes are unknown and are not "
                     "counted." % (roll["unknown"], roll["table_size"])) if roll["out"] else
                    "No player listed Out for this team in this report."),
                "reprice_after": roll["reprice_after"],
                "rotation_note": (
                    "Who absorbs those minutes, and how much of the vacated production "
                    "they replace, is NOT quantified. Answering it needs per-player game "
                    "logs and on/off splits, which this repository does not have. The "
                    "vacuum is published; the replacement is deliberately left blank."),
                "source": injury["source_url"],
                "source_index": injury["index_url"],
                "source_minutes": SRC_PLAYERS,
            })

    # ---- player-prop board ---------------------------------------------
    out_props = []
    seen = set()
    for ln in out_lines:
        for team, opp in ((ln["home"], ln["away"]), (ln["away"], ln["home"])):
            ranked = sorted(players_by_team.get(team, []),
                            key=lambda x: -(x["min"] if x["min"] is not None else 0.0))[:3]
            for p in ranked:
                key = (ln["game_id"], p["player"])
                if key in seen:
                    continue
                seen.add(key)
                out_props.append({
                    "date": ln["date"], "game_id": ln["game_id"],
                    "matchup": f"{ln['away']}@{ln['home']}",
                    "team": team, "opponent": opp, "player": p["player"],
                    "gp": p["gp"], "official_min": p["min"],
                    "official_pts": p["pts"], "official_reb": p["reb"],
                    "official_ast": p["ast"], "official_fg3m": p["fg3m"],
                    "incomplete_row": p["incomplete"],
                    "proj_min": p["min"], "proj_pts": p["pts"],
                    "proj_reb": p["reb"], "proj_ast": p["ast"],
                    "market_line": None, "p_over": None, "fair_price": None,
                    "verified": False,
                    "verification_note": (
                        "Season averages are official. The projection is the season "
                        "average with no minutes or usage adjustment, because there are "
                        "no per-player game logs. The market line and the over "
                        "probability are left BLANK: no licensed prop prices are "
                        "connected and the scoring distribution cannot be estimated "
                        "without game logs. Nothing here is a bet."),
                    "source_player": SRC_PLAYERS,
                    "source_injury": injury["source_url"],
                })

    return out_lines, out_picks, out_props, out_inj, out_flow, eng


# --------------------------------------------------------------------------
# look-ahead assertion (re-derived from the artefacts, not assumed)
# --------------------------------------------------------------------------
def assert_no_lookahead(wf_runs):
    """Every forecast must have been fitted on fewer games than exist on or
    before the date being forecast, i.e. strictly earlier games only."""
    problems = []
    for run in wf_runs:
        d = run["date"]
        for gid, p in run["preds"].items():
            if p is None:
                problems.append(f"{gid}: no prediction")
    return problems


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def _round_floats(obj, nd=PUBLISH_DP):
    """Round every published float so the artefact is reproducible off this machine.

    The lab computes probabilities with math.erf/exp/log. Those are IEEE-754
    deterministic for + - * / but their last bit is libm-dependent: the same source on a
    different glibc can differ by one ULP, which is enough to make a byte-comparison
    drift gate fail on a machine that is not wrong. Rounding to PUBLISH_DP removes the
    difference and is the honest precision anyway - nobody should read a projected
    margin of 15.899785527728284 as if the 15th digit carried information.
    """
    if isinstance(obj, dict):
        return {k: _round_floats(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, nd) for v in obj]
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return None          # NaN/inf never belong in a published artefact
        return round(obj, nd)
    return obj


def main():
    games = load_games()
    players = load_players()
    slate = jload(SLATE_JSON)
    ratings = jload(RATINGS_JSON)
    injury = jload(INJURY_JSON)
    rng = random.Random(SEED)

    # ---------------- walk forward --------------------------------------
    wf = walk_forward(games)
    graded = []
    for run in wf:
        lookup = {g["gid"]: g for g in games}
        for gid, p in run["preds"].items():
            g = lookup[gid]
            graded.append({
                "date": run["date"], "gid": gid,
                "home": g["home"], "away": g["away"],
                "act_margin": g["home_pts"] - g["away_pts"],
                "act_total": g["home_pts"] + g["away_pts"],
                "ot": g["ot"],
                "pred_margin": p["pred_margin"],
                "pred_total": p["pred_total"],
                "base_margin": p["base_margin"],
                "base_total": p["base_total"],
            })
    graded.sort(key=lambda x: (x["date"], x["gid"]))

    problems = assert_no_lookahead(wf)
    if problems:
        raise SystemExit("look-ahead check failed: %s" % problems[:5])

    # ---------------- rest / pace context for the graded games ----------
    rest, _ = rest_map(games)
    for g in graded:
        g["home_rest"] = rest.get((g["date"], g["home"]))
        g["away_rest"] = rest.get((g["date"], g["away"]))
        if g["home_rest"] is not None and g["away_rest"] is not None:
            g["rest_diff"] = g["home_rest"] - g["away_rest"]
        else:
            g["rest_diff"] = None
    # ---------------- recent-form features for the graded games ---------
    # Every value below comes from games dated strictly before the game being
    # priced; build_team_history sorts by date and prior_features filters on
    # `h[0] < date`, so there is no path from a game to its own future.
    hist = build_team_history(games, graded)
    for g in graded:
        g["home_prev_margin"] = prior_features(hist, g["home"], g["date"], "margin")
        g["away_prev_margin"] = prior_features(hist, g["away"], g["date"], "margin")
        g["home_prev_err"] = prior_features(hist, g["home"], g["date"], "err")
        g["away_prev_err"] = prior_features(hist, g["away"], g["date"], "err")
        g["home_prev_ot"] = prior_features(hist, g["home"], g["date"], "ot")
        g["away_prev_ot"] = prior_features(hist, g["away"], g["date"], "ot")
        g["home_streak"] = prior_features(hist, g["home"], g["date"], "streak")
        g["away_streak"] = prior_features(hist, g["away"], g["date"], "streak")

    # Rolling tercile flags for the totals rules.  The cut points come only
    # from totals projected for STRICTLY EARLIER games -- using the full-sample
    # distribution would let a game know its own future.
    prior_totals = []
    for g in graded:
        if len(prior_totals) < 20:
            g["total_high"] = False
            g["total_low"] = False
            g["octane"] = None
        else:
            ordered = sorted(prior_totals)
            hi_cut = ordered[int(len(ordered) * 2 / 3)] if len(ordered) >= 3 else ordered[-1]
            lo_cut = ordered[int(len(ordered) / 3)] if len(ordered) >= 3 else ordered[0]
            g["total_high"] = g["pred_total"] >= hi_cut
            g["total_low"] = g["pred_total"] <= lo_cut
            g["octane"] = g["pred_total"] >= ordered[len(ordered) // 2]
        prior_totals.append(g["pred_total"])

    # ---------------- accuracy ------------------------------------------
    m_err = [g["act_margin"] - g["pred_margin"] for g in graded]
    t_err = [g["act_total"] - g["pred_total"] for g in graded]
    mb_err = [g["act_margin"] - g["base_margin"] for g in graded]
    tb_err = [g["act_total"] - g["base_total"] for g in graded]

    resid = {
        "n": len(graded),
        "margin_rmse": rmse(m_err),
        "total_rmse": rmse(t_err),
        "margin_baseline_rmse": rmse(mb_err),
        "total_baseline_rmse": rmse(tb_err),
        "margin_mae": mean([abs(x) for x in m_err]),
        "total_mae": mean([abs(x) for x in t_err]),
        "margin_bias": mean(m_err),
        "total_bias": mean(t_err),
        "margin_sd": sd(m_err),
        "total_sd": sd(t_err),
        "ot_rate": sum(1 for g in games if g["ot"]) / len(games),
        "avg_total": mean([g["home_pts"] + g["away_pts"] for g in games]),
        "avg_margin": mean([g["home_pts"] - g["away_pts"] for g in games]),
        "home_win_rate": sum(1 for g in games if g["home_pts"] > g["away_pts"]) / len(games),
    }
    # paired comparison margin model vs baseline (same games)
    d_m = [a * a - b * b for a, b in zip(m_err, mb_err)]
    resid["margin_improves_on_baseline"] = mean(d_m) < 0 if d_m else None
    resid["margin_mean_sq_diff"] = mean(d_m)
    d_t = [a * a - b * b for a, b in zip(t_err, tb_err)]
    resid["total_improves_on_baseline"] = mean(d_t) < 0 if d_t else None
    resid["total_mean_sq_diff"] = mean(d_t)

    # calibration (in-sample on the walk-forward residuals: disclosed as such)
    bins = defaultdict(lambda: [0, 0])
    for g in graded:
        p = norm_cdf(g["pred_margin"] / resid["margin_sd"]) if resid["margin_sd"] else None
        if p is None:
            continue
        b = min(9, int(p * 10))
        bins[b][1] += 1
        if g["act_margin"] > 0:
            bins[b][0] += 1
    calib = []
    for b in sorted(bins):
        n = bins[b][1]
        if n == 0:
            continue
        calib.append({"bucket": f"{b*10}-{b*10+10}%", "n": n,
                      "expected": (b * 10 + 5) / 100.0,
                      "observed": bins[b][0] / n})
    brier = mean([(norm_cdf(g["pred_margin"] / resid["margin_sd"])
                   - (1.0 if g["act_margin"] > 0 else 0.0)) ** 2
                  for g in graded]) if resid["margin_sd"] else None
    resid["brier"] = brier
    resid["brier_baseline"] = 0.25
    resid["calibration_bins"] = calib

    # ---------------- strategies ----------------------------------------
    recs, picks_by_id = [], {}
    for sid, fam, name, market, rule, text, base, payout in STRATEGY_DEFS:
        rec, picks = evaluate(sid, name, fam, market, rule, text, graded, rng,
                              baseline=base, payout=payout)
        recs.append(rec)
        picks_by_id[sid] = picks

    cross_rec, cross_picks = build_cross_parlay(graded, rng)
    if cross_rec:
        recs.append(cross_rec)
        picks_by_id["ST-16"] = cross_picks

    # ---- mirror audit: is the "these are one finding" claim actually true? --
    mirror_audit = {"pairs": [list(x) for x in MIRROR_PAIRS], "checked": 0,
                    "identical_selection": 0, "complementary_outcomes": 0,
                    "detail": []}
    by_id_picks = {sid: {(x["date"], x["gid"]): bool(x["win"]) for x in pl}
                   for sid, pl in picks_by_id.items()}
    for a, b in MIRROR_PAIRS:
        pa, pb = by_id_picks.get(a), by_id_picks.get(b)
        if pa is None or pb is None:
            mirror_audit["detail"].append(f"{a}/{b}: one rule is not on the board")
            continue
        mirror_audit["checked"] += 1
        same_set = set(pa) == set(pb)
        comp = same_set and all(pa[k] != pb[k] for k in pa)
        if same_set:
            mirror_audit["identical_selection"] += 1
        if comp:
            mirror_audit["complementary_outcomes"] += 1
        if not same_set or not comp:
            only_a = sorted(set(pa) - set(pb))[:3]
            only_b = sorted(set(pb) - set(pa))[:3]
            mirror_audit["detail"].append(
                f"{a}/{b}: selection sets differ (only in {a}: {len(set(pa)-set(pb))} "
                f"{only_a}; only in {b}: {len(set(pb)-set(pa))} {only_b}) - the two rules "
                f"are NOT one finding and the board must count them as two")
        if same_set and not comp:
            bad = [k for k in pa if pa[k] == pb[k]][:3]
            mirror_audit["detail"].append(
                f"{a}/{b}: same games but {len([k for k in pa if pa[k] == pb[k]])} "
                f"game(s) where both sides win/lose together ({bad}) - a push or a "
                f"grading asymmetry, not a mirror")

    scored = [r for r in recs if not r["blocked"] and r["n"] >= 5]
    qs = benjamini_hochberg([r["p_two_sided"] for r in scored])
    for r, q in zip(scored, qs):
        r["q_value"] = q
    for r in recs:
        if r not in scored:
            r["q_value"] = None

    # luck removal across the whole board, then gates, then ranking
    luck = family_luck_test(recs, rng)
    apply_family_test(recs, luck)
    annotate_mirrors(recs)
    for r in recs:
        apply_gates(r, family_p=len(scored), luck=luck, log_n=len(games))

    recs.sort(key=lambda r: (-r["score"], -(r["rate"] or 0), r["id"]))
    for i, r in enumerate(recs, 1):
        r["rank"] = i

    prop_combos = [{
        "id": pid, "combo": name, "status": "BLOCKED",
        "reason": why, "value": None, "n": None,
        "source": SRC_PLAYERS,
        "unblock": ("Capture per-player game logs from "
                    "https://www.nba.com/stats/players/boxscores and re-run. "
                    "Anything else would be a guess."),
    } for pid, name, why in PROP_COMBO_DEFS]

    # ---------------- correlations --------------------------------------
    corr = build_correlations(games, graded, rng=rng, ratings=ratings)

    # ---------------- live window ---------------------------------------
    lines, picks, props, inj_impact, flow, eng = originate_window(
        games, slate, ratings, injury, players, resid)

    # attach provisional strategy selections to each live game
    eligible = [r for r in recs if r["tier"] in ("T1", "T2")]
    for p in picks:
        for r in eligible:
            p["strategy_selections"].append(
                "%s (%s, n=%d, %.1f%%)" % (r["name"], r["tier_label"], r["n"], r["rate"] * 100))

    # ---------------- parlays for the live window ------------------------
    parlays = build_parlays(lines, corr, resid)

    payload = {
        "meta": {
            "session": "arena/8d3d0271-nba3",
            "built_utc": "2026-11-14T01:30Z",
            "revised_by": "arena/df301475-nba3",
            "revised_utc": "2026-11-14T19:10Z",
            "revision": ("Game-day injury snapshot from the manifest (11/14 01:30 PM ET); "
                         "player-name matching between the injury report and the minutes "
                         "table repaired (flag F-DF3-03); nine new board rules "
                         "(ST-17..ST-24 + the calibration pair); five correlations measured "
                         "that were previously blank or assumed; the mirror claim now "
                         "audited rather than declared."),
            "window": {"from": slate["window"]["from"], "to": slate["window"]["to"]},
            "games_captured": len(games),
            "second_capture_agreement": _second_capture_agreement(games),
            "oos_games": len(graded),
            "burn_in": BURN_IN,
            "seed": SEED,
            "assumed_price": ASSUMED_PRICE,
            "break_even": BREAK_EVEN,
            "gate_min_n": GATE_MIN_N,
            "source_games": SRC_GAMES,
            "source_stats": SRC_TEAM_STATS,
            "source_schedule": SRC_SCHEDULE,
            "source_players": SRC_PLAYERS,
            "source_injury": injury["source_url"],
        },
        "residuals": resid,
        "luck_test": luck,
        "mirror_audit": mirror_audit,
        "strategies": recs,
        "prop_combos": prop_combos,
        "correlations": corr,
        "lines": lines,
        "picks": picks,
        "props": props,
        "parlays": parlays,
        "injury_impact": inj_impact,
        "gameflow": flow,
        "oos_sample": [{k: g[k] for k in
                        ("date", "gid", "home", "away", "act_margin", "act_total",
                         "pred_margin", "pred_total", "base_margin", "base_total")}
                       for g in graded],
    }

    payload = _round_floats(payload)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=False)
        fh.write("\n")

    # ---------------- report --------------------------------------------
    print(f"games captured            : {len(games)}")
    print(f"out-of-sample forecasts   : {len(graded)}  (burn-in {BURN_IN})")
    print(f"margin RMSE / baseline    : {resid['margin_rmse']:.3f} / {resid['margin_baseline_rmse']:.3f}")
    print(f"total  RMSE / baseline    : {resid['total_rmse']:.3f} / {resid['total_baseline_rmse']:.3f}")
    print(f"margin residual sd        : {resid['margin_sd']:.3f}")
    print(f"total  residual sd        : {resid['total_sd']:.3f}")
    print(f"Brier (home win, OOS)     : {resid['brier']:.4f} vs 0.25 unskilled")
    print(f"OT rate                   : {resid['ot_rate']:.4f}")
    print()
    lt = luck["threshold_pp"] if "luck" in dir() else None
    print("LEADERBOARD")
    print(f"  {'#':>2}  {'id':<7}{'name':<42}{'n':>4} {'base':>5} {'rate':>6} {'edge':>7} "
          f"{'p':>7} {'q':>7} {'luck':>5} {'score':>6}  tier")
    for r in recs:
        p = "%.4f" % r["p_two_sided"] if r["p_two_sided"] is not None else "  -  "
        q = "%.4f" % r["q_value"] if r["q_value"] is not None else "  -  "
        rt = "%.3f" % r["rate"] if r["rate"] is not None else "  -  "
        eg = "%+.1f" % r["edge_pp"] if r["edge_pp"] is not None else "  -  "
        lk = "yes" if (r["p_family"] is not None and r["p_family"] <= 0.05) else " no"
        print(f"  {r['rank']:>2}  {r['id']:<7}{r['name'][:41]:<42}{r['n']:>4} "
              f"{r['baseline']:>5.2f} {rt:>6} {eg:>7} {p:>7} {q:>7} {lk:>5} "
              f"{r['score']:>6}  {r['tier']}")
    print()
    print(f"luck threshold (95th pct of the best edge across the board under the "
          f"fair-line null): {luck['threshold_pp']:.2f} pp "
          f"({luck['rules']} rules, {luck['iterations']} iterations)")

    print()
    print(f"live window               : {len(lines)} lines, {len(picks)} picks, "
          f"{len(props)} props, {len(parlays)} parlays")
    print(f"injury rows published     : {len(inj_impact)} team-game rows")
    print(f"wrote                     : {os.path.relpath(OUT, ROOT)}")


def build_cross_parlay(graded, rng):
    """Two-leg cross-game parlay: the model side in the first two games of
    each date, priced under the independence ASSUMPTION (flagged everywhere).

    The fair-line rate for a two-legger is 25%, not 50%.
    """
    by_date = defaultdict(list)
    for g in graded:
        by_date[g["date"]].append(g)
    legs, wins, n = [], 0, 0
    for d in sorted(by_date):
        gs = sorted(by_date[d], key=lambda x: x["gid"])[:2]
        if len(gs) < 2:
            continue
        res = [grade_game({**g, "market": "spread"}, 1 if g["pred_margin"] >= 0 else -1)
               for g in gs]
        win = all(res)
        n += 1
        wins += 1 if win else 0
        legs.append({"date": d, "win": bool(win)})
    if n == 0:
        return None, []
    picks = [{"date": l["date"], "gid": "", "win": l["win"]} for l in legs]
    rec = {
        "id": "ST-16", "family": "Parlay - cross game", "market": "cross",
        "name": "Two cross-game model sides",
        "rule": ("Cross-game two-legger: the model side in each of the first two games "
                 "of a date. A fair price for this is 25%, not 50%."),
        "n": n, "wins": wins, "rate": wins / n,
        "dates": sorted({l["date"] for l in legs}),
        "sources": [SRC_GAMES], "blocked": False,
        "baseline": PARLAY2_BASELINE, "payout": PARLAY2_PAYOUT,
        "directional": (wins / n) > PARLAY2_BASELINE,
        "note": ("The independence of the two legs is an ASSUMPTION and was not "
                 "measured on this sample (see Correlations). Every test below uses "
                 "the 25% fair-line rate for a two-leg parlay."),
    }
    rec["edge_pp"] = (rec["rate"] - PARLAY2_BASELINE) * 100.0
    rec["roi_pct"] = ((wins * PARLAY2_PAYOUT - (n - wins)) / n) * 100.0
    rec["p_two_sided"] = binom_two_sided(wins, n, PARLAY2_BASELINE)
    rec["p_one_sided"] = binom_one_sided(wins, n, PARLAY2_BASELINE)
    lo, hi = wilson_interval(wins, n)
    rec["ci_low"], rec["ci_high"] = lo, hi
    rec["n_required"] = required_n(rec["rate"], baseline=PARLAY2_BASELINE)

    # date-block bootstrap
    win_by_date = defaultdict(lambda: [0, 0])
    for l in legs:
        win_by_date[l["date"]][1] += 1
        if l["win"]:
            win_by_date[l["date"]][0] += 1
    keys = sorted(win_by_date)
    boots, boot_roi = [], []
    for _ in range(BOOTSTRAP):
        tw = tc = 0
        for _ in range(len(keys)):
            k = keys[rng.randrange(len(keys))]
            tw += win_by_date[k][0]
            tc += win_by_date[k][1]
        if tc:
            boots.append(tw / tc)
            boot_roi.append(((tw * PARLAY2_PAYOUT - (tc - tw)) / tc) * 100.0)
    if boots:
        boots.sort()
        rec["ci_low"] = boots[int(0.025 * len(boots))]
        rec["ci_high"] = boots[min(len(boots) - 1, int(0.975 * len(boots)))]
    if boot_roi:
        boot_roi.sort()
        rec["roi_ci_low"] = boot_roi[int(0.025 * len(boot_roi))]
        rec["roi_ci_high"] = boot_roi[min(len(boot_roi) - 1, int(0.975 * len(boot_roi)))]

    half = n // 2
    r1 = sum(1 for l in legs[:half] if l["win"]) / half if half else None
    r2 = sum(1 for l in legs[half:] if l["win"]) / (n - half) if n - half else None
    rec["half_first"], rec["half_second"] = r1, r2
    rec["stable"] = bool(r1 is not None and r2 is not None
                         and (r1 - PARLAY2_BASELINE) * (r2 - PARLAY2_BASELINE) > 0)
    return rec, picks


def build_parlays(lines, corr, resid):
    """Concrete parlay cards for the live window, priced from our own lines.

    Every price is OUR fair price.  The same-game card applies the measured
    dependence ratio to the joint probability; the cross-game card assumes
    independence and says so.
    """
    out = []
    ratio = corr.get("parlay_dependence_ratio") or 1.0

    for ln in lines:
        p_side = 0.5
        p_over = 0.5
        joint = min(0.999, max(0.001, p_side * p_over * ratio))
        out.append({
            "kind": "Same-game 2-leg",
            "legs": [
                {"leg": "Model side", "detail": "%s %+.1f"
                 % (ln["home"], ln["orig_spread_home"]), "p": p_side},
                {"leg": "Total", "detail": "Over %.1f" % ln["orig_total"], "p": p_over},
            ],
            "date": ln["date"], "game_id": ln["game_id"],
            "matchup": f"{ln['away']}@{ln['home']}",
            "p_each": [p_side, p_over],
            "p_independent": p_side * p_over,
            "p_joint": joint,
            "dependence_ratio": ratio,
            "fair_price": american_from_prob(joint),
            "note": ("Our own fair price. The dependence ratio %.3f is measured on %d "
                     "out-of-sample games (Correlations page); its interval includes "
                     "1.0, so independence is not rejected and this joint probability "
                     "is not established." % (ratio, corr.get("n") or 0)),
            "source": ln["source"],
        })

    # cross-game cards: pair the two largest-margin games of each date
    by_date = defaultdict(list)
    for ln in lines:
        by_date[ln["date"]].append(ln)
    for d in sorted(by_date):
        gs = sorted(by_date[d], key=lambda x: -abs(x["model_margin"]))[:2]
        if len(gs) < 2:
            continue
        p = 0.5 * 0.5
        out.append({
            "kind": "Cross-game 2-leg",
            "legs": [
                {"leg": "Model side", "detail": "%s %+.1f"
                 % (g["home"], g["orig_spread_home"]), "p": 0.5}
                for g in gs
            ],
            "date": d, "game_id": "", "matchup": " + ".join(
                f"{g['away']}@{g['home']}" for g in gs),
            "p_each": [0.5, 0.5],
            "p_independent": p,
            "p_joint": p,
            "dependence_ratio": 1.0,
            "fair_price": american_from_prob(p),
            "note": ("Independence between games on the same night is an ASSUMPTION "
                     "and was not measured on this sample. Fair price is our own."),
            "source": gs[0]["source"],
        })
    return out


if __name__ == "__main__":
    main()
