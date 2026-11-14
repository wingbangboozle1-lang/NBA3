#!/usr/bin/env python3
"""Session dd1eb1f1 — measured correlations that the canonical site leaves blank.

Everything here is computed, not assumed, and every input is either an official NBA value or
a value the site already publishes as its own out-of-sample output:

  * official final scores  : data/app/games_2026-11-14c.csv  (183 games, source nba.com/games)
  * official game dates    : same file (used to derive days of rest)
  * our own predictions    : data/app/canonical.json  -> oos_sample (140 games, walk-forward)

Nothing is filled in from memory, from a rule of thumb, or from an outside model. Where a
number cannot be computed from these inputs, the cell is left blank and marked unverified.

Outputs: audit_dd1eb1f1/data/correlation_extension.json
Run:     python3 audit_dd1eb1f1/analysis.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")

GAMES_CSV = os.path.join(ROOT, "data", "app", "games_2026-11-14c.csv")
CANONICAL = os.path.join(ROOT, "data", "app", "canonical.json")

SEED = 20261114
PERMUTATIONS = 5000
DP = 6

SOURCE_SCORES = "https://www.nba.com/games?date="
SOURCE_ADVANCED = ("https://www.nba.com/stats/teams/advanced?Season=2026-27"
                   "&SeasonType=Regular%20Season")


def benjamini_hochberg(pvals):
    """BH-adjusted p-values (Benjamini-Hochberg, 1995). Returns [] for an empty input and
    None wherever the input p is None. Used because this section tests several rest
    hypotheses at once; reporting the smallest raw p as if it were the only test is how a
    noise fluctuation gets published as a signal."""
    indexed = [(i, p) for i, p in enumerate(pvals) if p is not None]
    if not indexed:
        return [None for _ in pvals]
    indexed.sort(key=lambda t: t[1])
    m = len(indexed)
    out = [None] * len(pvals)
    prev = 1.0
    for rank in range(m, 0, -1):
        i, pv = indexed[rank - 1]
        adj = min(prev, pv * m / rank)
        out[i] = adj
        prev = adj
    return out


def r(v):
    """Round for publication; None stays None so a blank never becomes a number."""
    return None if v is None else round(v, DP)


# --------------------------------------------------------------- statistics ----
def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None, None, None, n
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None, None, None, n
    rr = sxy / math.sqrt(sxx * syy)
    rr = max(-0.999999, min(0.999999, rr))
    # Fisher z 95% interval
    z = 0.5 * math.log((1 + rr) / (1 - rr))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = z - 1.959964 * se, z + 1.959964 * se
    return rr, math.tanh(lo), math.tanh(hi), n


def two_sided_p_from_permutation(observed, null_values):
    """Fraction of |null| >= |observed|. No distributional assumption."""
    if observed is None or not null_values:
        return None
    a = abs(observed)
    ge = sum(1 for v in null_values if abs(v) >= a - 1e-12)
    return (ge + 1) / (len(null_values) + 1)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def welch_t_p(a, b):
    """Two-sample Welch t statistic and a normal-approximation two-sided p.
    Used only as a descriptive comparison; the permutation tests are the primary evidence."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None, None
    ma, mb = mean(a), mean(b)
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se2 = va / na + vb / nb
    if se2 <= 0:
        return None, None
    t = (ma - mb) / math.sqrt(se2)
    p = math.erfc(abs(t) / math.sqrt(2))
    return t, p


# --------------------------------------------------------------- inputs -------
def load_games():
    out = []
    with open(GAMES_CSV, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            out.append({
                "date": row["date"].strip(),
                "game_id": row["game_id"].strip(),
                "away": row["away"].strip(),
                "home": row["home"].strip(),
                "away_pts": int(row["away_pts"]),
                "home_pts": int(row["home_pts"]),
                "ot": row["ot"].strip() not in ("0", "", "False"),
            })
    out.sort(key=lambda g: (g["date"], g["game_id"]))
    return out


def add_rest(games):
    """Days since each team's previous game. Derived from the official dates only.

    The log is the complete season to date (the site's own cross-check: the sum of official GP
    on the team advanced page equals 366 = 2 x 183), so 'days since the previous game in the
    log' is 'days of rest'. A team's first game of the season has no computable rest and is
    left blank rather than assumed to be fully rested.
    """
    last_seen = {}
    for g in games:
        d = date.fromisoformat(g["date"])
        g["home_rest"] = (d - last_seen[g["home"]]).days if g["home"] in last_seen else None
        g["away_rest"] = (d - last_seen[g["away"]]).days if g["away"] in last_seen else None
        g["home_b2b"] = g["home_rest"] == 1
        g["away_b2b"] = g["away_rest"] == 1
        last_seen[g["home"]] = d
        last_seen[g["away"]] = d
    return games


# --------------------------------------------------------------- sections -----
def rest_effects(games):
    rows = [g for g in games if g["home_rest"] is not None and g["away_rest"] is not None]
    rest_diff = [g["home_rest"] - g["away_rest"] for g in rows]
    home_margin = [g["home_pts"] - g["away_pts"] for g in rows]
    total = [g["home_pts"] + g["away_pts"] for g in rows]
    abs_margin = [abs(m) for m in home_margin]

    rr, lo, hi, n = pearson(rest_diff, home_margin)
    perm = []
    rng = random.Random(SEED)
    for _ in range(PERMUTATIONS):
        sh = home_margin[:]
        rng.shuffle(sh)
        v, _, _, _ = pearson(rest_diff, sh)
        if v is not None:
            perm.append(v)

    r_tot, lo_tot, hi_tot, n_tot = pearson(rest_diff, total)
    r_abs, lo_abs, hi_abs, n_abs = pearson(rest_diff, abs_margin)
    sum_rest = [g["home_rest"] + g["away_rest"] for g in rows]
    r_sum, lo_sum, hi_sum, n_sum = pearson(sum_rest, total)

    hb = [g for g in rows if g["home_b2b"] and not g["away_b2b"]]
    hb_margin = [g["home_pts"] - g["away_pts"] for g in hb]
    rest = [g for g in rows if not g["home_b2b"] and not g["away_b2b"]]
    rest_margin = [g["home_pts"] - g["away_pts"] for g in rest]
    ab = [g for g in rows if g["away_b2b"] and not g["home_b2b"]]
    ab_margin = [g["home_pts"] - g["away_pts"] for g in ab]

    t_hb, p_hb = welch_t_p(hb_margin, rest_margin)
    t_ab, p_ab = welch_t_p(ab_margin, rest_margin)

    # Multiple comparisons: this section tests one correlation and two group contrasts.
    # Publish the raw p AND the Benjamini-Hochberg adjusted p, and say how many tests the
    # family contains. A raw p below 0.05 that does not survive adjustment is reported as
    # "not distinguishable from noise on this sample", not as a finding.
    family = [("Rest differential vs home margin", two_sided_p_from_permutation(rr, perm)),
              ("Home team on a back-to-back, opponent rested", p_hb),
              ("Away team on a back-to-back, home team rested", p_ab)]
    adjusted = benjamini_hochberg([p for _, p in family])
    family_out = [{"test": name, "raw_p": r(raw), "bh_adjusted_p": r(adj),
                   "survives_0.05": bool(adj is not None and adj < 0.05)}
                  for (name, raw), adj in zip(family, adjusted)]

    return {
        "title": "Rest, back-to-backs and the official final scores",
        "question": "Does days-of-rest carry a measurable signal in the official results, or is "
                    "it noise? The site lists rest as a game-flow factor (GF04) but records the "
                    "effect as unmeasured. These numbers measure it.",
        "inputs": {"games": len(rows),
                   "games_excluded_no_prior_game": len(games) - len(rows),
                   "exclusion_reason": "a team's first game of the season has no computable rest"},
        "source_scores": SOURCE_SCORES,
        "method": "Days of rest = the gap in days between a team's game and its previous game, "
                  "derived from the official game dates in the 183-game log. rest_diff = home "
                  "rest minus away rest. Correlations are Pearson with a Fisher z 95% interval; "
                  "the p-value for rest_diff vs home margin comes from 5,000 permutations of the "
                  "margins (seed 20261114), which assumes nothing about the distribution.",
        "rows": [
            {"pair": "Rest differential (home rest - away rest) vs home margin",
             "stat": "Pearson r", "value": r(rr),
             "ci95": [r(lo), r(hi)], "n": n,
             "permutation_p": r(two_sided_p_from_permutation(rr, perm)),
             "verified": True, "kind": "derived",
             "reading": "Positive means the better-rested home team does better than the "
                        "rest-neutral expectation. The interval is the honest answer: if it "
                        "covers zero, this sample cannot distinguish the effect from noise."},
            {"pair": "Rest differential vs game total",
             "stat": "Pearson r", "value": r(r_tot), "ci95": [r(lo_tot), r(hi_tot)],
             "n": n_tot, "verified": True, "kind": "derived",
             "reading": "Whether rest asymmetry is associated with higher or lower scoring."},
            {"pair": "Rest differential vs absolute margin (blowout size)",
             "stat": "Pearson r", "value": r(r_abs), "ci95": [r(lo_abs), r(hi_abs)],
             "n": n_abs, "verified": True, "kind": "derived",
             "reading": "Whether tired teams get blown out, which matters for props and "
                        "fourth-quarter minutes."},
            {"pair": "Combined rest (home + away) vs game total",
             "stat": "Pearson r", "value": r(r_sum), "ci95": [r(lo_sum), r(hi_sum)],
             "n": n_sum, "verified": True, "kind": "derived",
             "reading": "Whether two rested teams score more in total."},
        ],
        "group_means": [
            {"group": "Home team on a back-to-back, opponent rested", "n": len(hb),
             "mean_home_margin": r(mean(hb_margin)),
             "home_win_rate": r(sum(1 for m in hb_margin if m > 0) / len(hb_margin)) if hb_margin else None,
             "welch_t_vs_rested_both": r(t_hb), "p_normal_approx": r(p_hb)},
            {"group": "Neither team on a back-to-back", "n": len(rest),
             "mean_home_margin": r(mean(rest_margin)),
             "home_win_rate": r(sum(1 for m in rest_margin if m > 0) / len(rest_margin)) if rest_margin else None,
             "welch_t_vs_rested_both": None, "p_normal_approx": None},
            {"group": "Away team on a back-to-back, home team rested", "n": len(ab),
             "mean_home_margin": r(mean(ab_margin)),
             "home_win_rate": r(sum(1 for m in ab_margin if m > 0) / len(ab_margin)) if ab_margin else None,
             "welch_t_vs_rested_both": r(t_ab), "p_normal_approx": r(p_ab)},
        ],
        "multiple_comparisons": {
            "family_size": len(family_out),
            "method": "Benjamini-Hochberg (1995) across the three rest tests in this section",
            "tests": family_out,
            "reading": "One raw p-value in this section sits below 0.05 on its own. After "
                       "adjusting for the fact that three rest hypotheses were tested on the "
                       "same sample, none of them reaches 0.05. Publishing that one would have "
                       "been a manufactured signal.",
        },
        "caveat": "These are observational counts of one 25-day slice of one season, not a "
                  "controlled experiment. Rest is confounded with travel, opponent quality and "
                  "coaching. A small n in the back-to-back cells is exactly why the intervals "
                  "are published next to the point estimates.",
    }


def model_accuracy(canon):
    oos = canon["oos_sample"]
    pm = [g["pred_margin"] for g in oos]
    am = [g["act_margin"] for g in oos]
    pt = [g["pred_total"] for g in oos]
    at = [g["act_total"] for g in oos]
    rm = [a - p for a, p in zip(am, pm)]
    rt = [a - p for a, p in zip(at, pt)]
    bp_m = [g["base_margin"] for g in oos]
    bp_t = [g["base_total"] for g in oos]
    rbm = [a - p for a, p in zip(am, bp_m)]
    rbt = [a - p for a, p in zip(at, bp_t)]

    out = {"title": "How much of the official result our originated numbers actually track",
           "source_scores": SOURCE_SCORES,
           "method": "Pearson r between our walk-forward prediction and the official result, on "
                     "the 140 out-of-sample games only. The baseline column is the same "
                     "correlation for the site's constant baseline, so the comparison shows what "
                     "the model adds. A model that beats the baseline on RMSE but not on "
                     "correlation is picking up level, not ordering.",
           "rows": []}
    for label, pred, act, base in (
            ("Originated spread (home margin) vs official home margin", pm, am, bp_m),
            ("Originated total vs official total", pt, at, bp_t)):
        rr, lo, hi, n = pearson(pred, act)
        br, blo, bhi, bn = pearson(base, act)
        out["rows"].append({
            "pair": label, "stat": "Pearson r", "value": r(rr), "ci95": [r(lo), r(hi)],
            "n": n, "baseline_r": r(br), "baseline_ci95": [r(blo), r(bhi)],
            "verified": True, "kind": "derived",
            "reading": "Positive correlation means the ordering of games is informative even "
                       "where the level is off."})
    def sd(xs):
        m = mean(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

    out["residual_summary"] = {
        "n": len(oos),
        "margin_residual_mean": r(mean(rm)),
        "margin_residual_sd": r(sd(rm)),
        "total_residual_mean": r(mean(rt)),
        "total_residual_sd": r(sd(rt)),
        "baseline_margin_residual_sd": r(sd(rbm)),
        "baseline_total_residual_sd": r(sd(rbt)),
    }
    return out


def within_date_clustering(canon):
    """Do our errors cluster inside a slate? This is the number that decides whether a
    cross-game parlay can be priced as independent."""
    oos = canon["oos_sample"]
    by_date = {}
    for g in oos:
        by_date.setdefault(g["date"], []).append(g)
    dates = sorted(by_date)

    def pairs(getter):
        xs, ys = [], []
        for d in dates:
            vals = [getter(g) for g in by_date[d]]
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    xs.append(vals[i])
                    ys.append(vals[j])
                    xs.append(vals[j])
                    ys.append(vals[i])
        return xs, ys

    mres = lambda g: g["act_margin"] - g["pred_margin"]   # noqa: E731
    tres = lambda g: g["act_total"] - g["pred_total"]     # noqa: E731

    res = {}
    for name, getter in (("margin residual", mres), ("total residual", tres)):
        xs, ys = pairs(getter)
        obs, lo, hi, n = pearson(xs, ys)
        rng = random.Random(SEED + 1)
        pool = [getter(g) for g in oos]
        sizes = [len(by_date[d]) for d in dates]
        null = []
        for _ in range(PERMUTATIONS):
            rng.shuffle(pool)
            nx, ny = [], []
            k = 0
            for s in sizes:
                grp = pool[k:k + s]
                k += s
                for i in range(s):
                    for j in range(i + 1, s):
                        nx.append(grp[i]); ny.append(grp[j])
                        nx.append(grp[j]); ny.append(grp[i])
            v, _, _, _ = pearson(nx, ny)
            if v is not None:
                null.append(v)
        res[name] = {
            "stat": "within-slate pairwise Pearson r of residuals",
            "value": r(obs), "ci95": [r(lo), r(hi)],
            "pairs": n, "games": len(oos), "dates": len(dates),
            "permutation_p": r(two_sided_p_from_permutation(obs, null)),
            "null_median": r(sorted(null)[len(null) // 2]),
            "null_p95": r(sorted(null)[int(0.95 * len(null))]),
            "permutations": PERMUTATIONS,
        }

    # Overdispersion of the per-date hit rate of our own spread.
    # Grading uses the site's own convention (scripts/strategy_lab.py::grade_game):
    # the home side covers our originated spread when act_margin > pred_margin.
    def covers(g):
        return 1 if (g["act_margin"] - g["pred_margin"]) > 0 else 0

    hit = [covers(g) for g in oos]
    by_date_hits = {d: [covers(g) for g in by_date[d]] for d in dates}
    obs_var = None
    per_date_rates = [sum(v) / len(v) for v in by_date_hits.values()]
    obs_var = sum((x - mean(per_date_rates)) ** 2 for x in per_date_rates) / len(per_date_rates)
    rng = random.Random(SEED + 2)
    null_var = []
    for _ in range(PERMUTATIONS):
        sh = hit[:]
        rng.shuffle(sh)
        k = 0
        rates = []
        for s in [len(by_date[d]) for d in dates]:
            grp = sh[k:k + s]; k += s
            rates.append(sum(grp) / s)
        null_var.append(sum((x - mean(rates)) ** 2 for x in rates) / len(rates))
    p_var = (sum(1 for v in null_var if v >= obs_var - 1e-15) + 1) / (len(null_var) + 1)

    return {
        "title": "Do our errors cluster inside one slate? (cross-game parlay dependence)",
        "question": "Cross-game parlays are priced as if the legs are independent. That is an "
                    "assumption, and the site says so. If residuals on the same night move "
                    "together, a cross-game parlay of our own picks is mispriced in a known "
                    "direction.",
        "source_scores": SOURCE_SCORES,
        "cover_definition": "The home side covers our originated spread when act_margin > pred_margin, the same convention the site uses in scripts/strategy_lab.py::grade_game.",
        "method": "For every pair of games that share a date, correlate their out-of-sample "
                  "residuals (both orderings, so the estimate is symmetric). The null shuffles "
                  "residuals across dates 5,000 times (seed 20261114+1), which destroys any "
                  "within-night structure while keeping the same residuals and the same slate "
                  "sizes. p is the fraction of shuffled values at least as extreme as observed. "
                  "The second test asks whether the per-date side hit rate varies more than a "
                  "coin with a constant rate would (5,000 shuffles, seed 20261114+2).",
        "results": res,
        "per_date_hit_rate_overdispersion": {
            "observed_variance_of_per_date_rate": r(obs_var),
            "null_median_variance": r(sorted(null_var)[len(null_var) // 2]),
            "permutation_p": r(p_var),
            "permutations": PERMUTATIONS,
            "reading": "A p near 1 means the per-night hit rates vary less than chance, i.e. no "
                       "detectable slate effect. A p near 0 means our errors share a nightly "
                       "component, which is the thing that would break independent parlay "
                       "pricing."},
        "caveat": "140 games over roughly 30 dates is a small sample for a variance-component "
                  "question, and the 1,176 pairs are not independent: one game on a ten-game "
                  "night contributes eighteen pairs. The Fisher-z interval above therefore "
                  "assumes something that is not true and is printed only for completeness - "
                  "the permutation p, which reshuffles whole slates and keeps the dependence "
                  "structure, is the number to read. The honest output here is 'no detectable "
                  "slate effect', not a verdict of independence."
    }


def still_blank():
    return {
        "title": "Correlations still left blank, and exactly what would fill them",
        "note": "These are the cells the site publishes empty. This session did not fill them, "
                "because the input they need does not exist in this repository.",
        "rows": [
            {"pair": "Player A points vs player B points, same team, same game",
             "needs": "per-player box scores for the season", "status": "blank",
             "official_source_that_has_it": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"},
            {"pair": "Player points vs player rebounds, same player, same game",
             "needs": "per-player game logs", "status": "blank",
             "official_source_that_has_it": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"},
            {"pair": "Player points vs team total, same game",
             "needs": "per-player game logs joined to game totals", "status": "blank",
             "official_source_that_has_it": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"},
            {"pair": "Minutes played vs production when a teammate is out",
             "needs": "per-player game logs plus the injury history by date", "status": "blank",
             "official_source_that_has_it": "https://official.nba.com/nba-injury-report-2026-27-season/"},
        ]}


# --------------------------------------------------------------- main ---------
def main():
    canon = json.load(open(CANONICAL, encoding="utf-8"))
    games = add_rest(load_games())

    report = {
        "schema": "nba3.audit_dd1eb1f1.correlation_extension.v1",
        "session": "arena/dd1eb1f1-nba3",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "seed": SEED,
        "permutations": PERMUTATIONS,
        "what_this_is": ("Measured values computed by this session from official NBA final "
                         "scores and from the site's own published out-of-sample predictions. "
                         "They are labelled Derived: they are not official NBA statistics and "
                         "they are not the canonical site's numbers."),
        "sources": {"official_final_scores": SOURCE_SCORES,
                    "official_team_advanced": SOURCE_ADVANCED,
                    "games_log_file": "data/app/games_2026-11-14c.csv",
                    "oos_predictions_file": "data/app/canonical.json -> oos_sample"},
        "sections": [rest_effects(games), model_accuracy(canon),
                     within_date_clustering(canon), still_blank()],
    }
    out = os.path.join(DATA, "correlation_extension.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")
    for s in report["sections"]:
        print(f"\n== {s['title']}")
        for row in s.get("rows", []):
            v = row.get("value")
            print(f"   {row['pair'][:70]:<70} r={v}")
        if "results" in s:
            for k, v in s["results"].items():
                print(f"   {k:<20} r={v['value']} p={v['permutation_p']} pairs={v['pairs']}")
        if "group_means" in s:
            for g in s["group_means"]:
                print(f"   {g['group'][:60]:<60} n={g['n']} mean_margin={g['mean_home_margin']} "
                      f"home_win%={g['home_win_rate']}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
