"""
Model layer. Reads only scripts/raw_data.py. Emits data/*.json for the site.

Design rules enforced here:
  * No value is invented. Anything absent from raw_data stays None and is
    surfaced as "unverified" by build_site.py and validate_site.py.
  * League constants are MEASURED from the transcribed game results where the
    sample allows, with the measurement printed alongside. The prior
    assumptions are kept only as a sensitivity band.
  * Every number carries `basis` = MEASURED | DERIVED | ASSUMPTION | MARKET |
    UNVERIFIED plus a source key, so the renderer cannot lose provenance.
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
from itertools import combinations

from raw_data import (
    ALIAS, ASSUMPTIONS, BBR_LEADERS_SOURCE, COMPLETED_GAMES, GAME_PREVIEW_SOURCE,
    INJURIES, LEAGUE_AVG, MARKET, MARKET_DETAILS_STRING, PLAYER_RATES,
    PROP_INVENTORY, RETRIEVED_UTC, SOURCES, TEAM_NAMES, TEAM_RATINGS,
    UPCOMING_GAMES,
)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)

norm = lambda t: ALIAS.get(t, t)


# ---------------------------------------------------------------- statistics
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def am_to_dec(am: float | None) -> float | None:
    if am is None:
        return None
    return 1.0 + (am / 100.0 if am > 0 else 100.0 / abs(am))


def dec_to_am(d: float | None) -> float | None:
    if d is None or d <= 1.0:
        return None
    return (d - 1.0) * 100.0 if d < 2.0 else -100.0 / (d - 1.0)


def devig(p_a: float, p_b: float) -> tuple[float, float]:
    s = p_a + p_b
    return p_a / s, p_b / s


def imp(dec: float | None) -> float | None:
    return None if not dec else 1.0 / dec


# ------------------------------------------------- 1. measure league constants
def measure_constants():
    n = len(COMPLETED_GAMES)
    margins = [hp - ap for _, _, ap, _, hp, _ in COMPLETED_GAMES]
    totals = [hp + ap for _, _, ap, _, hp, _ in COMPLETED_GAMES]
    home_wins = sum(1 for m in margins if m > 0)

    mean_m = st.mean(margins)
    sd_m = st.stdev(margins)
    mean_t = st.mean(totals)
    sd_t = st.stdev(totals)
    se_m = sd_m / math.sqrt(n)
    se_t = sd_t / math.sqrt(n)

    # t-interval, df = n-1; 1.99 ~ 95% for df>60
    tcrit = 1.99 if n > 60 else 2.0
    return dict(
        n=n,
        home_margin_mean=round(mean_m, 2), home_margin_se=round(se_m, 2),
        home_margin_ci95=[round(mean_m - tcrit * se_m, 2), round(mean_m + tcrit * se_m, 2)],
        margin_sd=round(sd_m, 2),
        total_mean=round(mean_t, 2), total_se=round(se_t, 2),
        total_ci95=[round(mean_t - tcrit * se_t, 2), round(mean_t + tcrit * se_t, 2)],
        total_sd=round(sd_t, 2),
        home_win_rate=round(home_wins / n, 3),
        home_wins=home_wins,
        basis="MEASURED",
        source="bbr_schedule",
        note=("Measured from the %d completed games transcribed for 2026-11-01..11-12. "
              "Margin sd and total sd are used as the Gaussian scales; se/CI are shown "
              "so the reader can see how thin the sample is." % n),
    )


CONST = None  # filled in main()


def team_params(team: str) -> dict:
    """Shrunk per-team net rating and pace, plus a plausible spread of ratings."""
    r = TEAM_RATINGS[team]
    g = r["w"] + r["l"]
    k = ASSUMPTIONS["shrink_k"]["value"]
    factor = g / (g + k)
    return dict(
        team=team,
        games=g,
        ortg=r["ortg"], drtg=r["drtg"], nrtg=r["nrtg"],
        pace=r["pace"],
        mov=r["mov"], srs=r["srs"],
        shrink_factor=round(factor, 4),
        nrtg_shrunk=round(r["nrtg"] * factor, 2),
        basis="DERIVED",
        source="bbr_advanced",
    )


def matchup(away: str, home: str) -> dict:
    """Log5-style multiplicative ratings, the standard basketball box-score model.

    Each side's expected points = own offensive rating x opponent's defensive
    rating / league average defensive rating x expected possessions. This uses
    BOTH the offence and the defence of each team, rather than assuming the
    league average nets out, which would ignore that a good offence beating a
    bad defence produces more points than the reverse.
    """
    aw, hm = team_params(away), team_params(home)
    exp_pace = (aw["pace"] + hm["pace"]) / 2.0
    poss = exp_pace / 100.0

    lg = LEAGUE_AVG["drtg"]
    home_pts = hm["ortg"] * (aw["drtg"] / lg) * poss
    away_pts = aw["ortg"] * (hm["drtg"] / lg) * poss
    total = home_pts + away_pts
    # SIGN CONVENTION: margin_home is positive when the home team is expected to
    # win by that many points. spread_home is the handicap HANDED TO THE HOME
    # SIDE in the standard US book format, i.e. negative when home is favoured,
    # so that it can be compared directly with a listed line like "ORL -9.5".
    margin_home = (home_pts - away_pts) + CONST["home_margin_mean"]
    spread_home = -margin_home

    return dict(
        away=away, home=home,
        exp_pace=round(exp_pace, 1),
        home_pts=round(home_pts, 2),
        away_pts=round(away_pts, 2),
        margin_home=round(margin_home, 2),
        spread_home=round(spread_home, 2),
        total=round(total, 2),
        basis="DERIVED",
        source="bbr_advanced",
        formula=("home_pts = home_ORtg x away_DRtg/114.0 x (pace/100); "
                 "away_pts = away_ORtg x home_DRtg/114.0 x (pace/100); "
                 "margin_home = home_pts - away_pts + measured HCA; "
                 "spread_home = -margin_home (negative = home favoured)"),
    )


# ------------------------------------------------- 2. originated lines for slate
def build_lines():
    rows = []
    for date, time_et, away_raw, home_raw, nba_id, ev_id, cup in UPCOMING_GAMES:
        away, home = norm(away_raw), norm(home_raw)
        m = matchup(away, home)
        mk = MARKET.get(ev_id)

        row = dict(
            date=date, time_et=time_et, away=away, home=home,
            away_name=TEAM_NAMES[away], home_name=TEAM_NAMES[home],
            nba_game_id=nba_id, espn_event_id=ev_id, cup=cup,
            nba_url=f"https://www.nba.com/game/{away_raw.lower()}-vs-{home_raw.lower()}-{nba_id}",
            model_spread_home=m["spread_home"],
            model_margin_home=m["margin_home"],
            model_home_pts=m["home_pts"],
            model_away_pts=m["away_pts"],
            model_total=m["total"],
            exp_pace=m["exp_pace"],
            away_nrtg_shrunk=team_params(away)["nrtg_shrunk"],
            home_nrtg_shrunk=team_params(home)["nrtg_shrunk"],
            basis="DERIVED",
            source="bbr_advanced",
        )

        # P(home wins) = P(margin > 0) under the Gaussian margin model, where the
        # model spread already equals the expected margin. The intercept pushes
        # the probability away from 0.5 for a pick'em because a mean-zero margin
        # with sd 17.15 would otherwise give exactly 50%.
        p_home = norm_cdf(m["margin_home"] / CONST["margin_sd"])
        row["p_home_ml"] = round(p_home, 4)
        row["p_away_ml"] = round(1 - row["p_home_ml"], 4)
        row["p_over"] = round(1 - norm_cdf((m["total"] - CONST["total_mean"]) / CONST["total_sd"]), 4)
        row["p_under"] = round(1 - row["p_over"], 4)

        if mk:
            row.update(
                market_open_spread=mk["open_spread"],
                market_spread=mk["cur_spread"],
                market_open_total=mk["open_total"],
                market_total=mk["cur_total"],
                market_away_ml=mk["away_ml"],
                market_home_ml=mk["home_ml"],
                market_away_spread_odds=mk["away_spread_odds"],
                market_home_spread_odds=mk["home_spread_odds"],
                market_over_odds=mk["over_odds"],
                market_under_odds=mk["under_odds"],
                market_details_string=MARKET_DETAILS_STRING[ev_id],
                market_basis="MARKET",
                market_source="espn_odds",
            )
            row["line_move_total"] = round(mk["cur_total"] - mk["open_total"], 1)
            row["line_move_spread"] = round(mk["cur_spread"] - mk["open_spread"], 1)

            # de-vigged market probabilities
            p_h = imp(am_to_dec(mk["home_ml"]))
            p_a = imp(am_to_dec(mk["away_ml"]))
            fh, fa = devig(p_h, p_a)
            row["market_p_home_ml"], row["market_p_away_ml"] = round(fh, 4), round(fa, 4)
            row["ml_vig"] = round(p_h + p_a - 1, 4)

            pov = imp(am_to_dec(mk["over_odds"]))
            pun = imp(am_to_dec(mk["under_odds"]))
            fo, fu = devig(pov, pun)
            row["market_p_over"], row["market_p_under"] = round(fo, 4), round(fu, 4)

            edge_ml = row["p_home_ml"] - fh
            row["edge_home_ml"] = round(edge_ml, 4)
            row["edge_away_ml"] = round(row["p_away_ml"] - fa, 4)
            row["edge_over"] = round(row["p_over"] - fo, 4)
            row["edge_under"] = round(row["p_under"] - fu, 4)
            # spread edge in points, model vs market
            row["spread_edge_pts"] = round(m["spread_home"] - mk["cur_spread"], 2)
            row["total_edge_pts"] = round(m["total"] - mk["cur_total"], 2)
        else:
            row["market_basis"] = "UNVERIFIED"
            row["market_source"] = None
            row["note_market"] = ("No market snapshot captured for this game in this session. "
                                  "All market columns and edges are left blank, not estimated.")
        rows.append(row)

    return rows


# ------------------------------------------------------ 3. prop market rows
PROPS = [
    # athlete_id, name, team, stat, line, over_am, under_am, open_line, open_over_am, updated
    ("3136195", "Karl-Anthony Towns", "NYK", "Points", 21.5, -102, -124, 19.5, -124, "2026-11-14T00:54Z"),
    ("3133603", "Kelly Oubre Jr.",    "PHI", "Points", 10.5, -125, -102, 11.5, -106, "2026-11-13T23:29Z"),
    ("3062679", "Josh Hart",          "NYK", "Points",  9.5, -107, -119,  9.5, -107, "2026-11-13T09:36Z"),
    ("3147657", "Mikal Bridges",      "NYK", "Points",  8.5, -108, -118,  8.5, -108, "2026-11-13T18:11Z"),
    ("6585",    "Andre Drummond",     "NYK", "Points",  3.5, -142,  111,  3.5, -146, "2026-11-13T20:39Z"),
]


def build_props():
    rows = []
    for aid, name, team, stat, line, ov, un, oline, oov, upd in PROPS:
        po = imp(am_to_dec(ov))
        pu = imp(am_to_dec(un))
        fo, fu = devig(po, pu)
        rate = PLAYER_RATES.get(name, {})
        market_p_over = fo
        # Season average is on a different scale to the line's window; without a
        # games-played distribution we can only state the sign of the gap.
        season_avg = rate.get("ppg")
        row = dict(
            athlete_id=aid, player=name, team=team, stat=stat,
            line=line, over_odds=ov, under_odds=un,
            open_line=oline, open_over_odds=oov,
            market_p_over=round(market_p_over, 4), market_p_under=round(fu, 4),
            vig=round(po + pu - 1, 4),
            line_move=round(line - oline, 1),
            season_avg=season_avg,
            season_avg_source=("nba_game_preview" if rate.get("src", "").startswith("nba_game_preview")
                               else ("bbr_leaders" if rate else None)),
            last_updated=upd,
            basis="MARKET",
            source="espn_props",
            nba_url=f"https://www.espn.com/nba/player/_/id/{aid}",
        )
        # Model probability: NOT produced. A prop model needs a minutes
        # distribution, which this session has no source for.
        row["model_p_over"] = None
        row["edge"] = None
        row["status"] = "MODEL NOT AVAILABLE — minutes distribution missing"
        rows.append(row)
    return rows


# --------------------------------------------------- 4. correlation measurement
def build_correlation():
    """Real, sample-based correlation between the legs a parlay would combine.

    Only measurable relationships are reported. Anything that needs prop-level
    player logs (points vs rebounds, etc.) is left None and flagged, because no
    player game log was retrieved this session.
    """
    rows = []
    # Leg A = away team total points, Leg B = home team total points (same game).
    a_pts = [ap for _, _, ap, _, hp, _ in COMPLETED_GAMES]
    h_pts = [hp for _, _, ap, _, hp, _ in COMPLETED_GAMES]
    margins = [hp - ap for _, _, ap, _, hp, _ in COMPLETED_GAMES]
    totals = [hp + ap for _, _, ap, _, hp, _ in COMPLETED_GAMES]

    r_ah = st.correlation(a_pts, h_pts)
    r_mt = st.correlation(margins, totals)
    n = len(COMPLETED_GAMES)
    # Fisher z CI
    z = math.atanh(r_ah)
    se = 1.0 / math.sqrt(n - 3)

    def fisher_ci(r, se):
        zz = math.atanh(r)
        lo, hi = zz - 1.96 * se, zz + 1.96 * se
        return round(math.tanh(lo), 3), round(math.tanh(hi), 3)

    rows.append(dict(
        leg_a="Away team total points", leg_b="Home team total points",
        n=n, r=round(r_ah, 3), ci95=list(fisher_ci(r_ah, se)),
        interpretation=("Positive: both teams' scoring is driven by a shared possession count, "
                        "so opposing totals move together. This is the mechanism behind "
                        "same-game total correlation."),
        basis="MEASURED", source="bbr_schedule",
        note="Pearson r on %d completed games." % n,
    ))
    se2 = 1.0 / math.sqrt(n - 3)
    rows.append(dict(
        leg_a="Game margin (home-away)", leg_b="Game total",
        n=n, r=round(r_mt, 3), ci95=list(fisher_ci(r_mt, se2)),
        interpretation=("Near zero means spread and total legs in the same game are close to "
                        "independent, so a spread+total parlay can be multiplied with little error."),
        basis="MEASURED", source="bbr_schedule",
        note="Pearson r on %d completed games." % n,
    ))
    # Team-vs-opponent: a team's own points and its opponent's points, per team.
    per_team = {}
    for _, aw, ap, hm, hp, _ in COMPLETED_GAMES:
        per_team.setdefault(aw, []).append((ap, hp))
        per_team.setdefault(hm, []).append((hp, ap))
    rs = []
    for t, pairs in sorted(per_team.items()):
        if len(pairs) >= 5:
            rs.append(st.correlation([p[0] for p in pairs], [p[1] for p in pairs]))
    rows.append(dict(
        leg_a="Team own points", leg_b="Opponent points (pooled within team)",
        n=len(rs), r=round(st.mean(rs), 3), ci95=None,
        interpretation=("Average within-team correlation across %d teams with >=5 games. "
                        "Catches pace-driven teams that inflate both sides." % len(rs)),
        basis="MEASURED", source="bbr_schedule",
        note="Mean of per-team Pearson r. Not a population CI.",
    ))

    # Unmeasurable relationships are declared, never filled.
    for a, b, why in [
        ("Player points", "Player rebounds (same player)", "needs per-player game logs"),
        ("Player points", "Same-team teammate points", "needs per-player game logs"),
        ("Player points over", "Team total over", "needs matched player+team game logs"),
        ("Player minutes", "Any prop", "no minutes source retrieved this session"),
    ]:
        rows.append(dict(leg_a=a, leg_b=b, n=None, r=None, ci95=None,
                         interpretation="Not measured.",
                         basis="UNVERIFIED", source=None,
                         note=f"Requires {why}, which was not collected. Left blank by rule."))
    return rows


# ---------------------------------------------- 5. diagnostic model evaluation
def build_backtest():
    """Walk-forward-ish diagnostic.

    Honest disclosure: the team ratings were measured through 2026-11-12, so
    predicting 2026-11-01..11-12 with them is IN-SAMPLE. It measures whether the
    rating arithmetic reproduces reality, not whether it would have made money.
    No historical closing line exists in this session, so no ROI is claimed.
    """
    rows = []
    brier, brier_base, correct, n = 0.0, 0.0, 0, 0
    for date, aw, ap, hm, hp, ot in COMPLETED_GAMES:
        a, h = norm(aw), norm(hm)
        m = matchup(a, h)
        p_home = norm_cdf(m["margin_home"] / CONST["margin_sd"])
        actual_home = 1.0 if hp > ap else 0.0
        pred_home = 1.0 if p_home >= 0.5 else 0.0
        brier += (p_home - actual_home) ** 2
        base = CONST["home_win_rate"]
        brier_base += (base - actual_home) ** 2
        correct += int(pred_home == actual_home)
        n += 1
        rows.append(dict(
            date=date, away=a, home=h, away_pts=ap, home_pts=hp, ot=ot,
            model_spread_home=m["spread_home"], model_margin_home=m["margin_home"],
            model_total=m["total"],
            model_p_home=round(p_home, 4), actual_home_win=int(actual_home == 1.0),
            pick_correct=int(pred_home == actual_home),
            basis="DERIVED", source="bbr_schedule",
        ))
    summary = dict(
        n=n,
        brier=round(brier / n, 4),
        brier_baseline_home_rate=round(brier_base / n, 4),
        accuracy=round(correct / n, 4),
        in_sample=True,
        caveat=("In-sample diagnostic. Ratings cover the same window as the games "
                "being scored, so this overstates any real edge. It is published to "
                "show the arithmetic is internally consistent, not as a performance claim."),
        basis="DERIVED", source="bbr_schedule",
    )
    return rows, summary


# --------------------------------------------- 6. luck-removal / skill scoring
def binom_two_sided_p(z: float) -> float:
    """Two-sided normal approximation to a binomial tail."""
    return round(math.erfc(abs(z) / math.sqrt(2.0)), 4)


def required_n(p: float, edge: float, power: float = 0.8) -> int | None:
    if edge <= 0 or not (0 < p < 1):
        return None
    z_a, z_b = 1.96, 0.8416
    n = ((z_a + z_b) ** 2) * p * (1 - p) / (edge ** 2)
    return int(math.ceil(n))


def build_strategies(backtest_rows, bt_summary, corr_rows):
    f = lambda key: next(r for r in corr_rows if r["leg_a"] == key)

    n = bt_summary["n"]
    preds = [r["model_p_home"] for r in backtest_rows]
    outs = [r["actual_home_win"] for r in backtest_rows]
    exp_wins = sum(preds)
    obs_wins = sum(outs)
    sd = math.sqrt(sum(p * (1 - p) for p in preds))
    z = (obs_wins - exp_wins) / sd if sd else 0.0
    p_val = binom_two_sided_p(z)

    def gate(gate_id, name, status, evidence):
        return dict(id=gate_id, name=name, status=status, evidence=evidence)

    strategies = []

    # ---- S1: model-favoured side on the spread
    strategies.append(dict(
        id="S1",
        name="Favourite-side spread (model vs market)",
        market="Single bet — point spread",
        thesis=("Where the originated spread differs from the listed spread, take the side "
                "the model favours. Edge is measured in points and converted to probability "
                "with the measured margin distribution."),
        signal="sign(model_spread - market_spread)",
        stake_rule="flat 1 unit; no progression, no chase",
        evidence=dict(
            sample=9,
            sample_unit="games with a captured market line (2026-11-13 slate only)",
            brier=None,
            accuracy=None,
            note="No historical closing line exists in this session, so S1 cannot be scored on returns. Only a present-tense signal count is shown.",
        ),
        gates=[
            gate("G1", "Data provenance", "PASS",
                 "Ratings: Basketball-Reference advanced table. Prices: ESPN core odds endpoint (DraftKings). Both transcribed with URL and retrieval time."),
            gate("G2", "Leakage prevention", "FAIL",
                 "Ratings are measured through 2026-11-12 and the market prices are a 2026-11-13 snapshot, so the comparison is live-clean. But no historical price archive exists, which means the strategy cannot be tested without look-ahead."),
            gate("G3", "Baseline & calibration", "FAIL",
                 "No scored sample of S1 signals exists, so no calibration plot can be produced."),
            gate("G4", "Robustness", "FAIL", "Sample of 9 live games. Power is far below the required n."),
            gate("G5", "Dependence (combos)", "PASS",
                 "If combined, spread legs across games are near-independent; the measured margin/total correlation is reported on the correlation page."),
            gate("G6", "Economic test", "FAIL", "No closing-line history and no settlement archive."),
            gate("G7", "Prospective monitoring", "PENDING",
                 "Signal must be frozen, logged pre-tip, and scored after settlement."),
        ],
        basis="DERIVED", source="espn_odds",
    ))

    # ---- S2: totals vs market
    strategies.append(dict(
        id="S2",
        name="Total vs market (pace/ratings divergence)",
        market="Single bet — game total",
        thesis=("Originated total = league average scoring scaled by the two teams' expected "
                "possessions. Divergence from the listed total is the signal."),
        signal="model_total - market_total",
        stake_rule="flat 1 unit",
        evidence=dict(sample=9, sample_unit="games with a captured total",
                      brier=None, accuracy=None,
                      note="Directional signal only; no historical totals archive."),
        gates=[
            gate("G1", "Data provenance", "PASS", "Same sources as S1."),
            gate("G2", "Leakage prevention", "FAIL", "No historical totals archive."),
            gate("G3", "Baseline & calibration", "FAIL", "Unscored."),
            gate("G4", "Robustness", "FAIL", "9 live games."),
            gate("G5", "Dependence (combos)", "PASS",
                 "Measured margin vs total correlation documented; over legs in different games are weakly dependent through pace only."),
            gate("G6", "Economic test", "FAIL", "No closing prices."),
            gate("G7", "Prospective monitoring", "PENDING", "Not yet running."),
        ],
        basis="DERIVED", source="espn_odds",
    ))

    # ---- S3: moneyline underdog value
    strategies.append(dict(
        id="S3",
        name="Moneyline value on the dog",
        market="Single bet — moneyline",
        thesis=("Devig the two-way moneyline, compare the de-vigged implied probability with "
                "the model's win probability, and only act when the model is higher by more "
                "than the measured noise floor."),
        signal="model_p - devigged_market_p",
        stake_rule="flat 1 unit; quarter-Kelly cap as an upper bound only",
        evidence=dict(sample=9, sample_unit="games with a captured moneyline",
                      brier=None, accuracy=None,
                      note="Only the 2026-11-13 slate carried prices this session."),
        gates=[
            gate("G1", "Data provenance", "PASS", "ESPN core odds endpoint, both moneylines, vig reported per game."),
            gate("G2", "Leakage prevention", "FAIL", "No historical prices."),
            gate("G3", "Baseline & calibration", "FAIL", "Unscored."),
            gate("G4", "Robustness", "FAIL", "9 live games."),
            gate("G5", "Dependence (combos)", "PASS", "Cross-game legs independent by construction."),
            gate("G6", "Economic test", "FAIL", "No settlement data."),
            gate("G7", "Prospective monitoring", "PENDING", "Not yet running."),
        ],
        basis="DERIVED", source="espn_odds",
    ))

    # ---- S4: margin/total forecasting skill (the only fully scored strategy)
    strategies.append(dict(
        id="S4",
        name="Win-probability calibration (scored)",
        market="Forecast skill, not a bet",
        thesis=("Emit a win probability for every completed game and score it with a proper "
                "rule. This is the one strategy in this build with a real, computed score, "
                "because it needs no price history."),
        signal="norm_cdf(model_spread / margin_sd)",
        stake_rule="n/a — scored on Brier and calibration, not staked",
        evidence=dict(
            sample=n, sample_unit="completed games 2026-11-01..11-12",
            brier=bt_summary["brier"],
            brier_baseline=bt_summary["brier_baseline_home_rate"],
            accuracy=bt_summary["accuracy"],
            expected_wins=round(exp_wins, 1),
            observed_wins=obs_wins,
            z_score=round(z, 3),
            luck_p_value=p_val,
            note="In-sample: ratings overlap the scored window, so treat as a consistency check.",
        ),
        gates=[
            gate("G1", "Data provenance", "PASS", "All 86 game results transcribed with the source page."),
            gate("G2", "Leakage prevention", "FAIL", "In-sample by construction; no earlier-season ratings available this session."),
            gate("G3", "Baseline & calibration", "PASS",
                 f"Brier {bt_summary['brier']} vs home-rate baseline {bt_summary['brier_baseline_home_rate']}."),
            gate("G4", "Robustness", "FAIL", f"n={n}; a single 12-day window in one season."),
            gate("G5", "Dependence (combos)", "n/a", "Forecast scoring, no legs to combine."),
            gate("G6", "Economic test", "n/a", "No stake taken."),
            gate("G7", "Prospective monitoring", "PENDING", "Requires frozen snapshot scoring going forward."),
        ],
        basis="DERIVED", source="bbr_schedule",
    ))

    # ---- S5: parlay construction
    strategies.append(dict(
        id="S5",
        name="Cross-game parlay (independent legs)",
        market="Parlay",
        thesis=("Multiply de-vigged leg probabilities across games only where measured "
                "correlation is indistinguishable from zero, then compare with the offered "
                "parlay price."),
        signal="prod(leg p) vs offered price",
        stake_rule="flat, small; cap at 2 legs until G2 and G6 pass",
        evidence=dict(sample=None, sample_unit="requires multi-book parlay pricing",
                      brier=None, accuracy=None,
                      note="No parlay price was captured. Leg independence IS measured: see the correlation page."),
        gates=[
            gate("G1", "Data provenance", "PARTIAL", "Leg prices exist for 9 games; parlay prices do not."),
            gate("G2", "Leakage prevention", "FAIL", "No price history."),
            gate("G3", "Baseline & calibration", "FAIL", "Unscored."),
            gate("G4", "Robustness", "FAIL", "No sample."),
            gate("G5", "Dependence (combos)", "PASS",
                 "Margin-vs-total r and away-vs-home total r measured with 95% CI on 86 games."),
            gate("G6", "Economic test", "FAIL", "Parlay price and settlement rules not captured."),
            gate("G7", "Prospective monitoring", "PENDING", "Not frozen."),
        ],
        basis="DERIVED", source="bbr_schedule",
    ))

    # ---- S6: player prop combos (same game)
    strategies.append(dict(
        id="S6",
        name="Same-game player prop combo",
        market="Player prop combo / SGP",
        thesis=("Legs on the same game share minutes, usage and score state. The joint "
                "probability must be estimated directly, never by multiplying marginals."),
        signal="joint scenario simulation",
        stake_rule="blocked",
        evidence=dict(sample=None, sample_unit="none",
                      brier=None, accuracy=None,
                      note="Blocked: no minutes distribution and no per-player game logs were retrieved."),
        gates=[
            gate("G1", "Data provenance", "PARTIAL", "1,170 prop price points are exposed for one game, but athlete names needed 1 lookup each and only 5 were resolved."),
            gate("G2", "Leakage prevention", "FAIL", "No player game logs."),
            gate("G3", "Baseline & calibration", "FAIL", "No prop model."),
            gate("G4", "Robustness", "FAIL", "No sample."),
            gate("G5", "Dependence (combos)", "FAIL", "Points-vs-rebounds and teammate correlations are unmeasured; see the blank rows on the correlation page."),
            gate("G6", "Economic test", "FAIL", "No settlement rules captured."),
            gate("G7", "Prospective monitoring", "BLOCKED", "Cannot start without G2 and G5."),
        ],
        basis="UNVERIFIED", source="espn_props",
    ))

    # ---- leaderboard: luck-adjusted ranking
    leaderboard = []
    for s in strategies:
        e = s["evidence"]
        passes = sum(1 for g in s["gates"] if g["status"] == "PASS")
        fails = sum(1 for g in s["gates"] if g["status"] == "FAIL")
        if e.get("z_score") is not None:
            skill = round(-(e["brier"] - e.get("brier_baseline", e["brier"])), 4)
            luck = e["luck_p_value"]
            adj = round(skill * (1 - min(luck, 1.0)), 4)
            note = ("Scored on Brier improvement over the home-rate baseline, then multiplied "
                    "by (1 - luck p-value) so a result whose deviation from expectation is "
                    "consistent with chance scores near zero.")
        else:
            skill, luck, adj = None, None, None
            note = "Unscored: no honest sample exists for this strategy in this build."
        leaderboard.append(dict(
            id=s["id"], name=s["name"], market=s["market"],
            gates_passed=passes, gates_failed=fails, gates_total=len(s["gates"]),
            sample=e.get("sample"), brier=e.get("brier"),
            skill_component=skill, luck_p=luck, luck_adjusted=adj,
            eligible=(fails == 0 and passes >= 6),
            status=("ELIGIBLE" if (fails == 0 and passes >= 6) else
                    ("PRE-VALIDATION" if fails > 0 else "INCOMPLETE")),
            note=note,
            req_sample=required_n(
                (e.get("expected_wins") or 0) / n if e.get("expected_wins") else 0.55,
                abs((e.get("accuracy") or 0) - 0.5) if e.get("accuracy") else 0.05),
        ))

    leaderboard.sort(key=lambda r: (r["luck_adjusted"] is not None, r["luck_adjusted"] or 0), reverse=True)
    for i, r in enumerate(leaderboard, 1):
        r["rank"] = i

    return strategies, leaderboard, dict(
        exp_wins=round(exp_wins, 1), obs_wins=obs_wins, z=round(z, 3),
        p_value=p_val,
        required_games_for_5pct_edge=required_n(0.55, 0.05),
        required_games_for_3pct_edge=required_n(0.55, 0.03),
        reading=("A z-score inside ±1.96 is entirely consistent with luck. The published "
                 "leaderboard multiplies skill by (1 - p) so that a lucky run cannot top it."),
    )


# --------------------------------------------------------------- 7. injuries
STATUS_WEIGHT = {"Out": 1.0, "Doubtful": 0.75, "Questionable": 0.5,
                 "Probable": 0.25, "Available": 0.0}


def build_injuries():
    by_game = {}
    for date, matchup_s, team, player, status, reason in INJURIES:
        by_game.setdefault(matchup_s, []).append(
            dict(team=team, player=player, status=status, reason=reason,
                 g_league=reason.startswith("G League"),
                 basis="OFFICIAL", source="nba_injury"))

    rows = []
    for g, items in by_game.items():
        counts = {s: 0 for s in ["Out", "Doubtful", "Questionable", "Probable", "Available"]}
        for it in items:
            counts[it["status"]] = counts.get(it["status"], 0) + 1
        rotation = [i for i in items if not i["g_league"]]
        avail = {t: 0.0 for t in {i["team"] for i in items}}
        for i in rotation:
            avail[i["team"]] += STATUS_WEIGHT.get(i["status"], 0.0)
        rows.append(dict(
            game=g, rows=len(items),
            counts=counts,
            g_league_rows=sum(1 for i in items if i["g_league"]),
            rotation_rows=len(rotation),
            availability_drag={k: round(v, 2) for k, v in sorted(avail.items())},
            players=rotation,
            basis="OFFICIAL", source="nba_injury",
            url=SOURCES["nba_injury"]["url"],
        ))

    # Rotation-minutes impact: only computable where a season-average points
    # figure exists for the named player. Never imputed.
    points_at_risk = []
    for date, matchup_s, team, player, status, reason in INJURIES:
        if player in PLAYER_RATES and status in ("Out", "Doubtful", "Questionable"):
            r = PLAYER_RATES[player]
            points_at_risk.append(dict(
                game=matchup_s, team=team, player=player, status=status,
                season_ppg=r.get("ppg"),
                basis="DERIVED" if r.get("src") == "nba_game_preview" else "TRUSTED-2",
                source=r.get("src"),
                note=("Season points-per-game as printed on the source page. This is the "
                      "player's own individual scoring, NOT the team's expected loss of "
                      "points: a replacement absorbs part of it."),
            ))
    return rows, points_at_risk


def build_line_movement(lines):
    """Observed market movement paired with the official availability list.

    The pairing is presented as context, never as proof of cause.
    """
    out = []
    for r in lines:
        if r.get("market_basis") != "MARKET":
            continue
        key = f"{r['away']}@{r['home']}"
        inj = [i for i in INJURIES if i[1] == key or i[1].replace("BRK", "BKN") == key]
        outs = [i[3] for i in inj if i[4] == "Out"]
        qs = [i[3] for i in inj if i[4] in ("Questionable", "Doubtful")]
        out.append(dict(
            game=key, date=r["date"],
            spread_open=r["market_open_spread"], spread_now=r["market_spread"],
            spread_move=r["line_move_spread"],
            total_open=r["market_open_total"], total_now=r["market_total"],
            total_move=r["line_move_total"],
            official_outs=len(outs), official_questionable=len(qs),
            notable_outs=outs[:6],
            basis="MARKET+OFFICIAL", source="espn_odds+nba_injury",
            causal_status="UNVERIFIED — the league publishes statuses, not the reason a price moved.",
        ))
    return out


# ------------------------------------------------------------------- 8. main
def main():
    global CONST
    CONST = measure_constants()

    lines = build_lines()
    corridor = build_correlation()
    backtest, bt_summary = build_backtest()
    strategies, leaderboard, luck = build_strategies(backtest, bt_summary, corridor)
    injuries, points_at_risk = build_injuries()
    movement = build_line_movement(lines)

    team_rows = []
    for t in sorted(TEAM_RATINGS, key=lambda x: -TEAM_RATINGS[x]["nrtg"]):
        p = team_params(t)
        rows_b = [r for r in backtest if r["away"] == t or r["home"] == t]
        team_rows.append(dict(
            team=t, name=TEAM_NAMES[t],
            w=TEAM_RATINGS[t]["w"], l=TEAM_RATINGS[t]["l"],
            mov=TEAM_RATINGS[t]["mov"], srs=TEAM_RATINGS[t]["srs"],
            ortg=p["ortg"], drtg=p["drtg"], nrtg=p["nrtg"], pace=p["pace"],
            nrtg_shrunk=p["nrtg_shrunk"], shrink_factor=p["shrink_factor"], games=p["games"],
            bbr_url=f"https://www.basketball-reference.com/teams/{t}/2027.html",
            basis="DERIVED", source="bbr_advanced",
        ))

    # ---- picks: only rows with a real market line AND an edge past the noise floor.
    # Spread and moneyline edges are measured in probability terms against the
    # de-vigged market; totals likewise. An edge is never implied from a raw
    # points difference alone.
    picks = []
    noise_floor = 0.03  # 3 percentage points of de-vigged probability
    sd_m, sd_t = CONST["margin_sd"], CONST["total_sd"]

    for r in lines:
        if r.get("market_basis") != "MARKET":
            continue
        key = f"{r['away']}@{r['home']}"
        inj = [i for i in INJURIES if i[1] == key]
        outs = [i[3] for i in inj if i[4] == "Out"]
        qs = [i[3] for i in inj if i[4] in ("Questionable", "Doubtful")]

        cands = []

        # Spread: P(home covers) under the model vs the de-vigged market price.
        hs = r["market_spread"]
        # The home side covers the handicap hs (negative when the home team is
        # giving points) when  home_margin + hs > 0.  So the z-score is
        # (model_margin + hs) / sd, NOT (model_margin - hs) / sd.
        p_home_cover = norm_cdf((r["model_margin_home"] + hs) / sd_m)
        p_away_cover = 1 - p_home_cover
        dec_h = am_to_dec(r["market_home_spread_odds"])
        dec_a = am_to_dec(r["market_away_spread_odds"])
        fair_h, fair_a = devig(imp(dec_h), imp(dec_a))
        for side, p, fair, dec, odds_am in (
                ("Home", p_home_cover, fair_h, dec_h, r["market_home_spread_odds"]),
                ("Away", p_away_cover, fair_a, dec_a, r["market_away_spread_odds"])):
            cands.append(dict(
                market="Spread", side=side,
                pick=(f"{r['home']} {hs:+.1f}" if side == "Home" else f"{r['away']} {-hs:+.1f}"),
                p_model=p, p_market=fair, dec=dec, am=odds_am,
                model_edge_pts=round((r["model_margin_home"] + hs) * (1 if side == "Home" else -1), 2),
                edge_unit="points",
            ))

        # Moneyline
        for side, p, fair, am in (("Home", r["p_home_ml"], r["market_p_home_ml"], r["market_home_ml"]),
                                  ("Away", r["p_away_ml"], r["market_p_away_ml"], r["market_away_ml"])):
            cands.append(dict(
                market="Moneyline", side=side,
                pick=f"{r['home'] if side == 'Home' else r['away']} ML",
                p_model=p, p_market=fair, dec=am_to_dec(am), am=am,
                model_edge_pts=None, edge_unit="probability",
            ))

        # Total
        mt = r["market_total"]
        p_over = 1 - norm_cdf((mt - r["model_total"]) / sd_t)
        for side, p, fair, am in (("Over", p_over, r["market_p_over"], r["market_over_odds"]),
                                  ("Under", 1 - p_over, r["market_p_under"], r["market_under_odds"])):
            cands.append(dict(
                market="Total", side=side,
                pick=f"{side} {mt}",
                p_model=p, p_market=fair, dec=am_to_dec(am), am=am,
                model_edge_pts=round((r["model_total"] - mt) * (1 if side == "Over" else -1), 2),
                edge_unit="points",
            ))

        for c in cands:
            edge_p = c["p_model"] - c["p_market"]
            if edge_p < noise_floor:
                continue
            # How much of this divergence could simply be our model not knowing
            # who is playing? Record it; never silently adjust.
            blind_risk = "HIGH" if len(outs) >= 3 else ("MEDIUM" if len(outs) >= 1 else "LOW")
            ev = (c["p_model"] * (c["dec"] - 1.0) - (1 - c["p_model"])) if c["dec"] else None
            picks.append(dict(
                game=key, date=r["date"], time_et=r["time_et"],
                market=c["market"], side=c["side"], pick=c["pick"],
                p_model=round(c["p_model"], 4),
                p_market=round(c["p_market"], 4),
                market_edge_prob=round(edge_p, 4),
                model_edge_pts=c["model_edge_pts"], edge_unit=c["edge_unit"],
                decimal_odds=round(c["dec"], 3) if c["dec"] else None,
                american_odds=c["am"],
                fair_decimal_odds=round(1.0 / c["p_model"], 3) if c["p_model"] else None,
                # EV per 1 unit staked = p*(dec-1) - (1-p)
                ev_per_unit=(round(c["p_model"] * (c["dec"] - 1.0) - (1 - c["p_model"]), 4)
                             if c["dec"] else None),
                official_outs=len(outs), official_questionable=len(qs),
                notable_outs=outs[:5],
                injury_blind_risk=blind_risk,
                value_status=("POSITIVE EV" if (ev or 0) > 0 else "NO VALUE AT THIS PRICE"),
                _divergence=abs(r["model_spread_home"] - r["market_spread"])
                if c["market"] != "Total" else abs(r["model_total"] - r["market_total"]),
                tier="TIER C - pre-validation, paper only",
                basis="DERIVED", source="espn_odds+bbr_advanced",
                nba_url=r["nba_url"],
                caveat=("The originated model does NOT adjust for injuries. Where the "
                        "official report lists several outs, a divergence from the market "
                        "is far more likely to be our model's blind spot than real edge."
                        if outs else
                        "No official outs listed for either side at the report timestamp."),
            ))
    # ---- Sanity gate. Without an injury adjustment the model's largest
    # disagreements with the market are more likely to be OUR blind spot than
    # the market's. A divergence is only treated as a candidate signal when it
    # is small enough that the model is not effectively re-pricing the roster.
    MAX_DIV_SPREAD, MAX_DIV_TOTAL = 4.0, 5.0
    for p in picks:
        cap = MAX_DIV_TOTAL if p["market"] == "Total" else MAX_DIV_SPREAD
        over = p["_divergence"] > cap
        p["divergence"] = round(p["_divergence"], 2)
        p["divergence_cap"] = cap
        del p["_divergence"]
        if over:
            p["screen"] = "REJECTED - divergence too large"
            p["screen_reason"] = (
                f"Model differs from the market by {p['divergence']:.1f}, above the "
                f"{cap:.0f}-point screen. With no injury adjustment in the model, a gap "
                "this wide is far more likely to be a missed-availability effect than "
                "genuine edge.")
        elif p["injury_blind_risk"] == "HIGH":
            p["screen"] = "REJECTED - injury exposure"
            p["screen_reason"] = (
                f"The official report lists {p['official_outs']} players Out across the two "
                "teams. The model does not adjust for that, so the probability cannot be "
                "defended even though it clears the divergence screen.")
        else:
            p["screen"] = "PASSED SCREENS"
            p["screen_reason"] = (
                "Divergence is within the screen and injury exposure is not elevated. "
                "Still TIER C: screens are not the same as validation gates.")

    passed = [p for p in picks if p["screen"] == "PASSED SCREENS"]
    passed.sort(key=lambda p: -(p["ev_per_unit"] or -9))
    for i, p in enumerate(passed, 1):
        p["candidate_rank"] = i
    picks.sort(key=lambda p: (p["screen"] != "PASSED SCREENS",
                              -(p["ev_per_unit"] or -9)))
    for i, p in enumerate(picks, 1):
        p["rank"] = i

    payload = dict(
        meta=dict(
            snapshot_utc=RETRIEVED_UTC,
            season="2026-27",
            season_phase="Regular season + Emirates NBA Cup group stage",
            games_completed_in_sample=CONST["n"],
            slate_games=len(lines),
            slate_window="2026-11-13 .. 2026-11-15 (72h)",
            sources=SOURCES,
            extra_sources={"game_preview": GAME_PREVIEW_SOURCE, "bbr_leaders": BBR_LEADERS_SOURCE},
            # Publish the assumptions block as USED, not as first drafted. The
            # measured values replace the placeholder ones so the site can never
            # show a stale constant next to a live calculation.
            assumptions=dict(
                ASSUMPTIONS,
                hca_points=dict(ASSUMPTIONS["hca_points"], value=CONST["home_margin_mean"],
                                label="Home-court advantage, points",
                                status="MEASURED from the 86-game sample (95% CI shown on the method page)"),
                sd_margin=dict(ASSUMPTIONS["sd_margin"], value=CONST["margin_sd"],
                               status="MEASURED from the 86-game sample"),
                sd_total=dict(ASSUMPTIONS["sd_total"], value=CONST["total_sd"],
                              status="MEASURED from the 86-game sample"),
            ),
            league_avg_rating=LEAGUE_AVG["ortg"],
            noise_floor_prob=noise_floor,
        ),
        constants=CONST,
        teams=team_rows,
        lines=lines,
        picks=picks,
        pick_screen=dict(
            max_divergence_spread=4.0,
            max_divergence_total=5.0,
            total_signals=len(picks),
            passed=sum(1 for p in picks if p["screen"] == "PASSED SCREENS"),
            rejected_divergence=sum(1 for p in picks if p["screen"].startswith("REJECTED - divergence")),
            rejected_injury=sum(1 for p in picks if p["screen"].startswith("REJECTED - injury")),
            positive_ev=sum(1 for p in picks if p["value_status"] == "POSITIVE EV"),
            self_check=("A model that ignores injuries will disagree with a market that prices "
                        "them, and every disagreement looks like edge. The screens exist to throw "
                        "most of those disagreements away rather than to package them as picks."),
        ),
        props=build_props(),
        prop_inventory=PROP_INVENTORY,
        correlation=corridor,
        backtest=backtest,
        backtest_summary=bt_summary,
        strategies=strategies,
        leaderboard=leaderboard,
        luck=luck,
        injuries=injuries,
        points_at_risk=points_at_risk,
        movement=movement,
    )

    for name in ("lines", "picks", "props", "correlation", "strategies", "injuries"):
        with open(os.path.join(OUT, f"{name}.json"), "w") as fh:
            json.dump(payload[name], fh, indent=2, sort_keys=False)
    with open(os.path.join(OUT, "model.json"), "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)

    print("== measured constants ==")
    for k in ("home_margin_mean", "home_margin_ci95", "margin_sd", "total_mean", "total_ci95", "total_sd", "n"):
        print(f"  {k}: {CONST[k]}")
    print(f"== slate: {len(lines)} games, {sum(1 for r in lines if r.get('market_basis')=='MARKET')} with market ==")
    print(f"== picks: {len(picks)} ==")
    print(f"== backtest brier {bt_summary['brier']} vs base {bt_summary['brier_baseline_home_rate']} acc {bt_summary['accuracy']} ==")
    print(f"== luck: exp {luck['exp_wins']} obs {luck['obs_wins']} z {luck['z']} p {luck['p_value']} ==")
    print("== leaderboard ==")
    for r in leaderboard:
        print(f"  {r['rank']}. {r['id']} {r['name'][:44]:44s} gates {r['gates_passed']}/{r['gates_total']} "
              f"luck_adj={r['luck_adjusted']} {r['status']}")


if __name__ == "__main__":
    main()
