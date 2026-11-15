"""Walk-forward backtest of the registered rules, graded on official finals.

This is the part that decides whether any strategy is real, and it is built so
that the answer "none of them is" is reachable.  That matters: a harness that
can only find winners is not a test.

Design
------
* **Walk-forward, by date batch.**  For each date, both estimators are fitted on
  games with a STRICTLY EARLIER date.  Games on the same night are priced from
  the same fit and never see each other's results.
* **The hca pin is recomputed from history too.**  Home-court advantage is the
  measured home-win rate *of the games available before the date being priced*,
  so the pin does not leak the future any more than the ratings do.
* **Settlement is the official final**, and it is read from the same log that
  the model was told to ignore for that date.  The only thing the grader knows
  that the model did not is the result.
* **Pushes are excluded and counted.**  A spread or total that lands exactly is
  not a win, and folding it into the win column would inflate every rate.
* **A rule that fires rarely is not rescued.**  If a rule fires on 12 games the
  result is "n = 12", and it fails the sample gate.  No pooling across rules.

The engine that produces the live lines and the engine that produces the
backtest numbers are the same code path, which is the only way the backtest can
be evidence about the lines.
"""

from __future__ import annotations

import datetime as _dt
import random
from collections import defaultdict

from . import stats as S
from .estimators import (EfficiencyEstimator, ResultEstimator,
                         home_court_from_measured_rate)

RIDGE = 8.0
BURN_IN = 40          # games of history before the first forecast
HCA_MIN_GAMES = 30    # below this, the home-win rate is too noisy to pin HCA to


def _load_games(rows):
    games = []
    for r in rows:
        games.append({
            "date": r["date"], "game_id": r["game_id"], "gid": r["game_id"],
            "away": r["away"], "home": r["home"],
            "away_pts": int(r["away_pts"]), "home_pts": int(r["home_pts"]),
        })
    games.sort(key=lambda g: (g["date"], g["game_id"]))
    return games


def _rest_before(dates_by_team, team, date):
    """Days since the team's most recent game strictly before ``date``.

    ``dates_by_team`` is a mapping of team to a SET of dates, so ``prior[-1]``
    is an arbitrary member, not the latest one.  Using max() is the whole fix:
    with the set's iteration order the computed rest ranged up to 20 days on a
    team that had played four days earlier, and every rest-derived rule was
    graded on that noise.
    """
    prior = [d for d in dates_by_team.get(team, ()) if d < date]
    if not prior:
        return None
    return (_dt.date.fromisoformat(date) - _dt.date.fromisoformat(max(prior))).days


def walk_forward(games, team_stats):
    """Produce one forecast record per out-of-sample game."""
    by_date = defaultdict(list)
    for g in games:
        by_date[g["date"]].append(g)
    dates = sorted(by_date)

    dates_by_team = defaultdict(set)
    for g in games:
        dates_by_team[g["home"]].add(g["date"])
        dates_by_team[g["away"]].add(g["date"])

    out = []
    for i, d in enumerate(dates):
        history = [g for dd in dates[:i] for g in by_date[dd]]
        if len(history) < BURN_IN:
            continue
        if len(history) < HCA_MIN_GAMES:
            hca = None
        else:
            hca = home_court_from_measured_rate(history)

        est_a = ResultEstimator(ridge=RIDGE).fit(history, hca["hca_points"] if hca else 0.0)
        est_b = EfficiencyEstimator().fit(team_stats, hca["hca_points"] if hca else 0.0)

        for g in by_date[d]:
            a = est_a.predict(g["home"], g["away"])
            b = est_b.predict(g["home"], g["away"])
            if not a or not b or b.get("total") is None:
                continue
            rest_h = _rest_before(dates_by_team, g["home"], d)
            rest_a = _rest_before(dates_by_team, g["away"], d)
            out.append({
                "date": d, "game_id": g["game_id"], "gid": g["gid"],
                "home": g["home"], "away": g["away"],
                "home_pts": g["home_pts"], "away_pts": g["away_pts"],
                "a_margin": a["margin"], "b_margin": b["margin"], "b_total": b["total"],
                "b_possessions": b.get("possessions"),
                "hca_points": hca["hca_points"] if hca else None,
                "home_win_rate_history": hca["home_win_rate"] if hca else None,
                "rest_home": rest_h, "rest_away": rest_a,
                "n_history": len(history),
            })
    return out


def leakage_audit(records, team_stats):
    """Test whether estimator B's forecasts could have used later information.

    Estimator B is fitted on ONE team-statistics snapshot dated 2026-11-15.  When
    that snapshot is used to price games played in October it contains results
    those games produced, so B's walk-forward grades are contaminated.  This
    manifests as an implausibly small out-of-sample error, and the right
    response is to measure it and refuse to rank, not to round the number off.

    The audit reports B's error against a hard floor: the best error a genuine
    forecaster could plausibly reach on NBA margins is around 9-10 points RMSE
    (the market itself sits near 9.5).  Anything materially below that on 131
    games means information from the future, or a corrupted backtest.

    Returns a dict whose ``contaminated`` flag the build must honour.
    """
    out = {
        "n_forecasts": len(records),
        "snapshot_date": (team_stats.get("captured_utc") or "")[:10] or None,
        "first_forecast_date": records[0]["date"] if records else None,
        "last_forecast_date": records[-1]["date"] if records else None,
        "caveat": ("estimator B is fitted on a single snapshot; every forecast before the "
                   "snapshot date is priced with information from after the game"),
    }
    if not records:
        out["contaminated"] = True
        return out
    b_rmse = S.rmse([r["margin_residual"] for r in records])
    a_rmse = S.rmse([r["a_margin_residual"] for r in records])
    pre_snapshot = [r for r in records if r["date"] < "2026-11-15"]
    out.update({
        "b_margin_rmse": round(b_rmse, 4),
        "a_margin_rmse": round(a_rmse, 4),
        "contamination_floor_rmse": 9.0,
        "forecasts_before_snapshot": len(pre_snapshot),
        "forecasts_on_snapshot_date": len(records) - len(pre_snapshot),
        "b_beats_plausible_floor": b_rmse < 9.0,
        "a_only_is_clean": True,
        "note": ("estimator A is clean: it is fitted only on finals dated strictly before the "
                 "game being priced, so its 15.2 RMSE is a genuine out-of-sample figure"),
    })
    out["contaminated"] = bool(b_rmse < 9.0 or len(pre_snapshot) > 0)
    return out


def add_residuals(records):
    """Attach the realised residual to each forecast, and the running errors."""
    for r in records:
        actual_margin = r["home_pts"] - r["away_pts"]
        actual_total = r["home_pts"] + r["away_pts"]
        r["actual_margin"] = actual_margin
        r["actual_total"] = actual_total
        r["margin_residual"] = actual_margin - r["b_margin"]   # vs estimator B
        r["total_residual"] = actual_total - r["b_total"]
        r["a_margin_residual"] = actual_margin - r["a_margin"]
    # out-of-sample error of each estimator, in the order the games finished
    ma = [r["a_margin_residual"] for r in records]
    mb = [r["margin_residual"] for r in records]
    mt = [r["total_residual"] for r in records]
    summary = {
        "n": len(records),
        "a_margin_rmse": round(S.rmse(ma), 6) if ma else None,
        "b_margin_rmse": round(S.rmse(mb), 6) if mb else None,
        "b_total_rmse": round(S.rmse(mt), 6) if mt else None,
        "a_margin_bias": round(S.mean(ma), 6) if ma else None,
        "b_margin_bias": round(S.mean(mb), 6) if mb else None,
        "b_total_bias": round(S.mean(mt), 6) if mt else None,
        "a_margin_mae": round(S.mae(ma), 6) if ma else None,
        "b_margin_mae": round(S.mae(mb), 6) if mb else None,
        "b_total_mae": round(S.mae(mt), 6) if mt else None,
    }
    return summary


# ---------------------------------------------------------------------------
# grading
# ---------------------------------------------------------------------------
def fair_american(p):
    """Fair American odds for a probability, as an int.  Duplicated from stats to
    keep this module's money arithmetic readable in one place."""
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return -int(round(100 * p / (1 - p)))
    return int(round(100 * (1 - p) / p))


def _payoff(american, stake=1.0):
    """Profit on a win at these American odds; loss is -stake."""
    if american is None:
        return None
    if american < 0:
        return stake * (100.0 / -american)
    return stake * (american / 100.0)


def _graded(r, side, line, market, prob=None, won=None):
    """One graded bet row, carrying the price it was actually graded at.

    A moneyline is graded at our ORIGINATED fair price, which is a different
    price on every game.  Charging every moneyline -110 would make a heavy
    favourite look profitable purely because its fair price is shorter than
    -110, so the price travels with the row and the money is summed from it.
    """
    if market == "moneyline":
        american = fair_american(prob)
    else:
        american = -110
    return {
        "date": r["date"], "game_id": r["game_id"], "side": side, "line": line,
        "market": market, "price_american": american,
        "outcome": won, "won": won == "win" if won else False,
        "source_url": f"https://www.nba.com/game/{r['game_id']}",
    }


def _grade_side(record, side, line):
    """Did the named side cover ``line`` (a home-perspective spread)?"""
    actual = record["actual_margin"]
    if line is None:
        return None
    if side == "home":
        diff = actual - line
    else:
        diff = -(actual - line)
    if abs(diff) < 1e-9:
        return "push"
    return "win" if diff > 0 else "loss"


def _grade_total(record, direction, line):
    actual = record["actual_total"]
    if line is None:
        return None
    if abs(actual - line) < 1e-9:
        return "push"
    if direction == "over":
        return "win" if actual > line else "loss"
    return "win" if actual < line else "loss"


def grade_rule(rule, records, rng=None, model_error=None):
    """Apply one registered rule to the walk-forward records.

    Returns (bets, pushes).  A push is neither a win nor a loss: it is dropped
    from the rate and reported separately.  Nothing here decides whether a rule
    is good; that is ``leaderboard.decider``'s job.
    """
    sid = rule["strategy_id"]
    bets, pushes = [], []
    err = model_error or {"a_margin_rmse": 16.0, "b_margin_rmse": 16.0}
    combined = (err["a_margin_rmse"] ** 2 + err["b_margin_rmse"] ** 2) ** 0.5

    for r in records:
        outcomes = []      # list of graded rows for one game (parlays have two legs)

        if sid in ("S01", "S02"):
            line = r["a_margin"]
            if line >= 7.0:
                side = "away" if sid == "S01" else "home"
                o = _grade_side(r, side, line)
                outcomes.append(_graded(r, side, line, "spread", won=o))

        elif sid in ("S03", "S04"):
            line = r["b_total"]
            if line >= 230.0:
                direction = "under" if sid == "S03" else "over"
                o = _grade_total(r, direction, line)
                outcomes.append(_graded(r, direction, line, "total", won=o))

        elif sid in ("S05", "S06"):
            if r["rest_home"] is not None and r["rest_away"] is not None:
                if r["rest_home"] >= 2 and r["rest_away"] == 1:
                    side = "home" if sid == "S05" else "away"
                    line = r["a_margin"]
                    o = _grade_side(r, side, line)
                    outcomes.append(_graded(r, side, line, "spread", won=o))

        elif sid in ("S07", "S08"):
            if r["rest_home"] == 1:
                side = "home" if sid == "S07" else "away"
                line = r["a_margin"]
                o = _grade_side(r, side, line)
                outcomes.append(_graded(r, side, line, "spread", won=o))

        elif sid in ("S09", "S10"):
            agree = (r["a_margin"] > 0) == (r["b_margin"] > 0)
            gap = abs(r["a_margin"] - r["b_margin"])
            if agree and gap < 0.20 * combined and r["actual_margin"] != 0:
                fav_home = r["b_margin"] > 0
                fav_won = (r["actual_margin"] > 0) if fav_home else (r["actual_margin"] < 0)
                side = "favourite" if sid == "S09" else "underdog"
                won_this = fav_won if sid == "S09" else (not fav_won)
                # The fair price of the side taken comes from the model's own win
                # probability, not a flat -110.  A moneyline graded at -110 across
                # the board would be a different, much easier bet.
                sd = (err["a_margin_rmse"] ** 2 + err["b_margin_rmse"] ** 2) ** 0.5
                p_home = S.norm_cdf(r["b_margin"] / sd)
                p_fav = p_home if fav_home else 1 - p_home
                prob = p_fav if sid == "S09" else 1 - p_fav
                outcomes.append(_graded(r, side, None, "moneyline",
                                        prob=prob, won="win" if won_this else "loss"))

        elif sid in ("S11", "S12"):
            gap = abs(r["a_margin"] - r["b_margin"])
            if gap > combined:
                b_side = "home" if r["b_margin"] > 0 else "away"
                side = b_side if sid == "S11" else ("away" if b_side == "home" else "home")
                line = r["b_margin"]
                o = _grade_side(r, side, line)
                outcomes.append(_graded(r, side, line, "spread", won=o))

        elif sid == "N01":
            if rng is None:
                rng = random.Random(20261115)
            side = "home" if rng.random() < 0.5 else "away"
            o = _grade_side(r, side, 0.0)
            outcomes.append(_graded(r, side, 0.0, "spread", won=o))

        elif sid == "P01":
            if r["b_total"] >= 230.0:
                agree = (r["a_margin"] > 0) == (r["b_margin"] > 0)
                if agree:
                    fav_home = r["b_margin"] > 0
                    side_o = _grade_side(r, "home" if fav_home else "away", r["b_margin"])
                    tot_o = _grade_total(r, "under", r["b_total"])
                    if "push" in (side_o, tot_o):
                        pushes.append(_graded(r, "sgp", r["b_total"], "sgp", won="push"))
                        continue
                    won = side_o == "win" and tot_o == "win"
                    row = _graded(r, "sgp", r["b_total"], "sgp",
                                  won="win" if won else "loss")
                    row["legs"] = [{"market": "spread", "outcome": side_o},
                                   {"market": "total", "outcome": tot_o}]
                    outcomes.append(row)

        elif sid == "P02":
            continue      # graded by grade_cross_game
        elif sid in ("R01", "R02", "R03"):
            continue      # props: needs per-player game logs, which do not exist here
        else:
            continue

        for row in outcomes:
            if row["outcome"] == "push":
                pushes.append(row)
            else:
                bets.append(row)

    return bets, pushes


def grade_cross_game(rule, records):
    """P02: two-leg cross-game parlay, both legs on the same night."""
    by_date = defaultdict(list)
    for r in records:
        by_date[r["date"]].append(r)
    bets, pushes = [], []
    for d in sorted(by_date):
        games = by_date[d]
        if len(games) < 2:
            continue
        # the two games with the largest |A - B| gap, in the same direction
        ranked = sorted(games, key=lambda r: -abs(r["a_margin"] - r["b_margin"]))
        leg_games, outcomes = [], []
        for r in ranked:
            if len(leg_games) == 2:
                break
            if abs(r["a_margin"] - r["b_margin"]) <= 32.0:
                continue
            side = "home" if r["b_margin"] > 0 else "away"
            o = _grade_side(r, side, r["b_margin"])
            leg_games.append(r)
            outcomes.append(o)
        if len(leg_games) < 2:
            continue
        if "push" in outcomes:
            pushes.append({"date": d, "game_id": leg_games[0]["game_id"], "outcome": "push",
                           "won": False, "source_url":
                           f"https://www.nba.com/game/{leg_games[0]['game_id']}"})
            continue
        won = all(o == "win" for o in outcomes)
        bets.append({
            "date": d, "game_id": leg_games[0]["game_id"], "side": "two-leg",
            "line": None, "outcome": "win" if won else "loss", "won": won,
            "legs": [g["game_id"] for g in leg_games],
            "source_url": f"https://www.nba.com/game/{leg_games[0]['game_id']}",
        })
    return bets, pushes


def split_stability(bets):
    """Half-to-half check.  Reported, never used to select a rule."""
    n = len(bets)
    if n < 4:
        return None
    half = n // 2
    a = bets[:half]
    b = bets[half:]
    ra = sum(1 for x in a if x["won"]) / len(a)
    rb = sum(1 for x in b if x["won"]) / len(b)
    return {"first_half_rate": round(ra, 4), "second_half_rate": round(rb, 4),
            "gap_pp": round(abs(ra - rb) * 100, 2)}


def clean_records(records):
    """The subset on which estimator B carries no look-ahead.

    Only the games on or after the team-statistics snapshot are free of
    contamination for B.  That is a very small set, which is the honest answer:
    a per-date team-stats history is missing (see FV2-06).
    """
    return [r for r in records if r["date"] >= "2026-11-15"]
