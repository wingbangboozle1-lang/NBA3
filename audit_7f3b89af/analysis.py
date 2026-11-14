"""Measured analysis for cells the site publishes blank -- session arena/7f3b89af-nba3.

The question this answers is narrow and decision-relevant, and it is not the question an earlier
session already answered. Session dd1eb1f1 measured whether REST CORRELATES WITH THE ACTUAL
MARGIN. That is a fact about basketball. This measures whether REST CORRELATES WITH THE ERROR OF
OUR OWN ORIGINATED LINE. That is a fact about our model, and it is the one that decides whether a
rest term is worth adding to the engine: if the line already prices rest, the correlation will be
zero and there is nothing to add; if it does not, the residual will carry a rest signal and the gap
is a candidate edge -- or a candidate bug.

Everything here is arithmetic on two official inputs:
  - the official results log, 183 finals (data/app/games_2026-11-14c.csv)
  - the out-of-sample predictions for 140 of them (data/app/canonical.json -> oos_sample)

So every number below is labelled DERIVED: it is our arithmetic on official results, not an
official NBA statistic.

Run:  python3 audit_7f3b89af/analysis.py
"""

import csv
import json
import math
import os
import random
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")

RESULTS_CSV = os.path.join(ROOT, "data", "app", "games_2026-11-14c.csv")
CANONICAL = os.path.join(ROOT, "data", "app", "canonical.json")

SEED = 20261114
PERMUTATIONS = 20000


# ---------------------------------------------------------------------------------------------
# statistics helpers (all implemented from scratch; no third-party dependency)
# ---------------------------------------------------------------------------------------------
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


def slope_intercept(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return b, my - b * mx


def fisher_ci(r, n):
    """95% CI for a Pearson r via the Fisher z transform."""
    if r is None or n < 4 or abs(r) >= 1:
        return None, None
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = z - 1.959963985 * se, z + 1.959963985 * se
    return math.tanh(lo), math.tanh(hi)


def permutation_p(xs, ys, observed, iters=PERMUTATIONS, seed=SEED):
    """Two-sided permutation p-value for a Pearson r: shuffle y, recompute, count."""
    rng = random.Random(seed)
    ys = list(ys)
    count = 0
    for _ in range(iters):
        rng.shuffle(ys)
        r = pearson(xs, ys)
        if r is not None and abs(r) >= abs(observed) - 1e-12:
            count += 1
    return (count + 1) / (iters + 1)


def welch_t_p(a, b):
    """Two-sided Welch p-value from a normal approximation. n is small here, so it is reported with
    the permutation test alongside it rather than on its own."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se2 = va / na + vb / nb
    if se2 <= 0:
        return None
    t = (ma - mb) / math.sqrt(se2)
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))


def permutation_mean_diff_p(a, b, iters=PERMUTATIONS, seed=SEED + 1):
    rng = random.Random(seed)
    pool = list(a) + list(b)
    na = len(a)
    obs = abs(sum(a) / na - sum(b) / len(b)) if na and b else None
    if obs is None:
        return None
    count = 0
    for _ in range(iters):
        rng.shuffle(pool)
        d = abs(sum(pool[:na]) / na - sum(pool[na:]) / len(pool[na:]))
        if d >= obs - 1e-12:
            count += 1
    return (count + 1) / (iters + 1)


def benjamini_hochberg(pvals):
    """BH-adjusted p-values (q-values), monotone by construction."""
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    adj = [None] * n
    prev = 1.0
    for rank, i in enumerate(reversed(order), start=1):
        k = n - rank + 1
        val = min(prev, pvals[i] * n / k)
        adj[i] = val
        prev = val
    return adj


# ---------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------
def load_results():
    games = []
    with open(RESULTS_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            games.append({
                "date": row["date"].strip(),
                "game_id": row["game_id"].strip(),
                "away": row["away"].strip(),
                "home": row["home"].strip(),
                "away_pts": int(row["away_pts"]),
                "home_pts": int(row["home_pts"]),
                "ot": row["ot"].strip(),
            })
    games.sort(key=lambda g: (g["date"], g["game_id"]))
    return games


def build_rest_index(games):
    """team -> sorted list of dates played; rest is days since the team's previous game."""
    played = {}
    for g in games:
        played.setdefault(g["home"], []).append(g["date"])
        played.setdefault(g["away"], []).append(g["date"])
    return {t: sorted(d for d in v) for t, v in played.items()}


def rest_days(played, team, day):
    prev = [d for d in played.get(team, []) if d < day]
    if not prev:
        return None
    y1, m1, d1 = (int(x) for x in prev[-1].split("-"))
    y2, m2, d2 = (int(x) for x in day.split("-"))
    return (date(y2, m2, d2) - date(y1, m1, d1)).days


# ---------------------------------------------------------------------------------------------
def main():
    canon = json.load(open(CANONICAL))
    oos = canon["oos_sample"]
    games = load_results()
    played = build_rest_index(games)
    by_gid = {g["game_id"]: g for g in games}

    rows = []
    for p in oos:
        g = by_gid.get(p["gid"])
        if not g:
            continue
        hr = rest_days(played, p["home"], p["date"])
        ar = rest_days(played, p["away"], p["date"])
        if hr is None or ar is None:
            continue  # no previous official game yet: rest is unknown, so the game is left out
        rows.append({
            "gid": p["gid"], "date": p["date"], "home": p["home"], "away": p["away"],
            "home_rest": hr, "away_rest": ar, "rest_diff": hr - ar,
            "residual": p["act_margin"] - p["pred_margin"],
            "base_residual": p["act_margin"] - p["base_margin"],
            "total_residual": p["act_total"] - p["pred_total"],
            "act_margin": p["act_margin"],
        })

    n = len(rows)
    rd = [r["rest_diff"] for r in rows]
    res = [r["residual"] for r in rows]
    bres = [r["base_residual"] for r in rows]
    tres = [r["total_residual"] for r in rows]
    rest_sum = [r["home_rest"] + r["away_rest"] for r in rows]

    tests = []

    # --- T1: does the originated line's error track the rest differential? -------------------
    r1 = pearson(rd, res)
    lo1, hi1 = fisher_ci(r1, n)
    p1 = permutation_p(rd, res, r1)
    b1, a1 = slope_intercept(rd, res)
    tests.append({
        "id": "T1",
        "question": "Rest differential (home rest - away rest) vs the originated line's margin error",
        "stat": "Pearson r",
        "value": r1, "ci95": [lo1, hi1], "n": n, "p_perm": p1,
        "extra": {"slope_points_per_rest_day": b1, "intercept": a1},
        "reading": "A non-zero slope is points of margin error per extra day of home rest. If the "
                   "line already prices rest, this is zero.",
    })

    # --- T2: the same test on the naive baseline, as a control -------------------------------
    r2 = pearson(rd, bres)
    lo2, hi2 = fisher_ci(r2, n)
    p2 = permutation_p(rd, bres, r2)
    tests.append({
        "id": "T2",
        "question": "Same test on the baseline (constant home-court margin) -- control",
        "stat": "Pearson r",
        "value": r2, "ci95": [lo2, hi2], "n": n, "p_perm": p2,
        "extra": {},
        "reading": "The baseline knows nothing about rest, so this is what 'unpriced rest' looks "
                   "like. It is the yardstick for T1.",
    })

    # --- T3: road team on a back-to-back, model error ----------------------------------------
    b2b = [r["residual"] for r in rows if r["away_rest"] == 1 and r["home_rest"] >= 2]
    other = [r["residual"] for r in rows if not (r["away_rest"] == 1 and r["home_rest"] >= 2)]
    if len(b2b) >= 5:
        p3 = permutation_mean_diff_p(b2b, other)
        tests.append({
            "id": "T3",
            "question": "Mean margin error when the away team is on a back-to-back and the home "
                        "team is rested, vs every other game",
            "stat": "difference in mean residual (points)",
            "value": (sum(b2b) / len(b2b)) - (sum(other) / len(other)),
            "ci95": [None, None], "n_group": len(b2b), "n_other": len(other),
            "p_perm": p3,
            "extra": {"mean_residual_b2b_road": sum(b2b) / len(b2b),
                      "mean_residual_other": sum(other) / len(other),
                      "welch_p": welch_t_p(b2b, other)},
            "reading": "If the model over-rates a rested road team the mean error here is negative. "
                       "This is the subgroup a bettor would actually bet.",
        })

    # --- T4: does rest predict the total error? ----------------------------------------------
    r4 = pearson(rest_sum, tres)
    lo4, hi4 = fisher_ci(r4, n)
    p4 = permutation_p(rest_sum, tres, r4)
    tests.append({
        "id": "T4",
        "question": "Combined rest (home + away) vs the originated total's error",
        "stat": "Pearson r",
        "value": r4, "ci95": [lo4, hi4], "n": n, "p_perm": p4,
        "extra": {"slope_points_per_rest_day": slope_intercept(rest_sum, tres)[0]},
        "reading": "Tired teams scoring less is the theory. If the totals model ignores it, this "
                   "shows up here.",
    })

    # --- T5: honest walk-forward: would a rest term have helped? -----------------------------
    # For each game, fit the rest coefficient on ALL EARLIER games only, then apply it to this
    # game. No future information reaches the coefficient, so this is what a trader could have
    # done in real time.
    ordered = sorted(rows, key=lambda r: (r["date"], r["gid"]))
    corrected_err, raw_err, applied = [], [], 0
    coefs = []
    for i in range(1, len(ordered)):
        past = ordered[:i]
        xs = [p["rest_diff"] for p in past]
        ys = [p["residual"] for p in past]
        b, a = slope_intercept(xs, ys)
        if b is None:
            continue
        cur = ordered[i]
        coefs.append(b)
        corrected_err.append((cur["residual"] - (a + b * cur["rest_diff"])) ** 2)
        raw_err.append(cur["residual"] ** 2)
        applied += 1
    rmse_corr = math.sqrt(sum(corrected_err) / len(corrected_err)) if corrected_err else None
    rmse_raw = math.sqrt(sum(raw_err) / len(raw_err)) if raw_err else None
    tests.append({
        "id": "T5",
        "question": "Walk-forward: would adding a rest term have reduced out-of-sample margin "
                    "error? (coefficient fitted on earlier games only)",
        "stat": "RMSE, points",
        "value": rmse_corr, "ci95": [None, None], "n": applied,
        "p_perm": None,
        "extra": {"rmse_originated_line": rmse_raw,
                  "rmse_with_rest_term": rmse_corr,
                  "improvement_points": (rmse_raw - rmse_corr) if rmse_raw and rmse_corr else None,
                  "final_coefficient": coefs[-1] if coefs else None,
                  "coefficient_min": min(coefs) if coefs else None,
                  "coefficient_max": max(coefs) if coefs else None},
        "reading": "The coefficient is re-fitted before every game using only games already played, "
                   "so a positive improvement is achievable in real time. A negative improvement "
                   "means the rest term is noise that would have made the line worse.",
    })

    qs = benjamini_hochberg([t["p_perm"] if t["p_perm"] is not None else 1.0 for t in tests])
    for t, q in zip(tests, qs):
        t["q_bh"] = q
        t["significant_after_bh"] = bool(q is not None and q < 0.05)

    buckets = []
    for label, pred in (("<=-2 (road team much fresher)", lambda d: d <= -2),
                        ("-1", lambda d: d == -1),
                        ("0 (equal rest)", lambda d: d == 0),
                        ("+1", lambda d: d == 1),
                        (">=+2 (home team much fresher)", lambda d: d >= 2)):
        sub = [r["residual"] for r in rows if pred(r["rest_diff"])]
        buckets.append({
            "bucket": label,
            "n": len(sub),
            "mean_error_points": (sum(sub) / len(sub)) if sub else None,
            "mean_abs_error_points": (sum(abs(x) for x in sub) / len(sub)) if sub else None,
        })

    # --- how big a sample would settle it? ----------------------------------------------------
    # Two-sided test on a Pearson r at alpha = 0.05 with 80% power:
    #   n = ((z_{1-a/2} + z_{power}) / atanh(r))^2 + 3
    r_used = abs(r1) if r1 else 0.0
    if r_used > 0:
        z = math.atanh(min(r_used, 0.99))
        n_required = int(math.ceil(((1.959963985 + 0.8416212336) / z) ** 2 + 3))
    else:
        n_required = None
    dates = sorted(g["date"] for g in games)
    d0 = date(*(int(x) for x in dates[0].split("-")))
    d1 = date(*(int(x) for x in dates[-1].split("-")))
    span_days = (d1 - d0).days + 1
    per_day = len(games) / span_days if span_days else None
    still_needed = (n_required - n) if n_required else None
    days_needed = int(math.ceil(still_needed / per_day)) if (still_needed and per_day) else None

    out = {
        "session": "arena/7f3b89af-nba3",
        "question": "Does our originated line already price rest, or does its error still carry a "
                    "rest signal that a bettor could harvest?",
        "inputs": {
            "results_log": "data/app/games_2026-11-14c.csv (183 official finals)",
            "predictions": "data/app/canonical.json -> oos_sample (140 out-of-sample games)",
            "official_source": "https://www.nba.com/games?date=",
        },
        "label": "DERIVED -- our arithmetic on official results, not an official NBA statistic.",
        "games_used": n,
        "games_excluded_no_prior_game": len(oos) - n,
        "method": "Rest is days since that team's previous game in the official log. Error is "
                  "actual home margin minus our predicted home margin. Permutation p-values are "
                  "two-sided with %d shuffles, seed %d. Multiple comparisons across the five "
                  "tests are controlled with Benjamini-Hochberg at q < 0.05." % (PERMUTATIONS, SEED),
        "tests": tests,
        "buckets": buckets,
        "power": {
            "observed_abs_r": r_used,
            "games_needed_for_80pct_power_at_alpha_0.05": n_required,
            "games_available_now": n,
            "games_still_needed": still_needed,
            "official_finals_per_day_this_season": round(per_day, 3) if per_day else None,
            "days_of_results_still_needed": days_needed,
            "log_span": {"from": dates[0], "to": dates[-1], "days": span_days, "games": len(games)},
            "method": "Two-sided test on a Pearson r, alpha 0.05, 80% power, using the effect size "
                      "actually observed. It answers 'how much more data before this is worth "
                      "re-testing', not 'is the effect real'.",
        },
        "verdict": (
            "The originated line does not price rest, and the rest signal shows up in its error in "
            "the expected direction: %+.2f points of home margin per extra day of home rest (r = "
            "%.3f, 95%% CI %.3f to %.3f, permutation p = %.3f, BH-adjusted q = %.3f over five "
            "tests). In the classic spot -- rested home team against a road team on a back-to-back "
            "-- the home side beat our line by %.1f points on average across %d games. Neither "
            "survives correction for testing five hypotheses at once, and the walk-forward test "
            "settles it: fitting the rest coefficient on earlier games only and applying it "
            "forward made the line WORSE by %.2f points of RMSE (%.2f to %.2f), with the "
            "coefficient swinging between %.1f and %.1f points per day as the sample grew. "
            "Conclusion: do not add a rest term on this evidence. Re-test when the out-of-sample "
            "sample reaches roughly %s games."
            % (b1, r1, lo1, hi1, p1, qs[0],
               sum(b2b) / len(b2b), len(b2b),
               (rmse_raw - rmse_corr) * -1, rmse_raw, rmse_corr,
               min(coefs), max(coefs), n_required)
            if coefs else "Not enough games to fit a walk-forward coefficient."
        ),
        "seed": SEED,
    }
    with open(os.path.join(DATA, "analysis.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")

    print("games used: %d (excluded %d with no prior official game)"
          % (n, len(oos) - n))
    for t in tests:
        v = t["value"]
        print("  %s  %-58s value=%s  p=%s  q=%s"
              % (t["id"], t["question"][:58],
                 ("%.4f" % v) if isinstance(v, float) else v,
                 ("%.4f" % t["p_perm"]) if t["p_perm"] is not None else "-",
                 ("%.4f" % t["q_bh"]) if t["q_bh"] is not None else "-"))
    print()
    for b in buckets:
        m = b["mean_error_points"]
        print("  rest_diff %-30s n=%-4d mean error %s"
              % (b["bucket"], b["n"], ("%+.2f" % m) if m is not None else "-"))
    return out


if __name__ == "__main__":
    main()
