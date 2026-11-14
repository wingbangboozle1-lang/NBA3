#!/usr/bin/env python3
"""Build the consolidated NBA3 dashboard at the repository root.

Inputs (all verified by final/verify.py against official NBA pages):
  final/data/model_output.json          produced by final/build_model.py
  final/data/games.csv                  official game log, reconciled to official GP / W-L
  final/data/teams_advanced.csv         official team advanced table (30 rows)
  final/data/players_top_minutes.csv    official player table, top 31 by minutes
  final/data/schedule_upcoming.csv      official slate D+1..D+3
  final/data/injuries.csv               official injury report 11/13/26 07:30 PM ET
  final/data/content.json               questions, suggestions, flags, repo review, sources

Run:  python3 final/build_site.py
Then: python3 final/check_site.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_lib import (  # noqa: E402
    OUT, ROOT, TEAM_NAMES, REPO_URL, NAV, badge, blank, esc, fmt, game_url, page,
    src, table, team_url,
)

DATA = ROOT / "final" / "data"
FINAL = ROOT / "final"

with (DATA / "model_output.json").open(encoding="utf-8") as fh:
    M = json.load(fh)
with (DATA / "content.json").open(encoding="utf-8") as fh:
    C = json.load(fh)


def read(name):
    with (DATA / name).open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if not r.get("team", "").startswith("#")]


GAMES_CSV = read("games.csv")
UPCOMING = read("schedule_upcoming.csv")
INJURIES = read("injuries.csv")
TEAMS = {r["team"]: r for r in read("teams_advanced.csv")}
PLAYERS = read("players_top_minutes.csv")

SRC_GAMES = "https://www.nba.com/games?date="
SRC_TEAM = ("https://www.nba.com/stats/teams/advanced?Season=2026-27"
            "&SeasonType=Regular%20Season")
SRC_PLAYER = ("https://www.nba.com/stats/players/traditional?Season=2026-27"
              "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC")
SRC_INJ = ("https://ak-static.cms.nba.com/referee/injury/"
           "Injury-Report_2026-11-13_07_30PM.pdf")
SRC_TERMS = "https://www.nba.com/termsofuse"

LINES = M["lines"]
STRATS = M["strategies"]
CORR = M["correlations"]
GF = M["game_flow"]
RATINGS = M["team_ratings"]
IMPACT = M["injury_impact"]
PROPS = M["player_props"]
OOS = M["oos_games"]

# Output is deterministic: no timestamps are rendered, so the committed pages can
# be drift-checked in CI.

# ---------------------------------------------------------------- strategy triggers
STRAT_BY_ID = {s["id"]: s for s in STRATS}
TRIGGERS = []
for L in LINES:
    m_home = -L["orig_spread_home"]      # positive = home favoured
    tot = L["orig_total"]
    fired = []
    if m_home >= 8.0:
        fired.append(("S4", "Away", "Fade home favourites of 8+"))
    if m_home <= -8.0:
        fired.append(("S4b", "Away", "Back road favourites of 8+"))
    if tot >= 235.0:
        fired.append(("S5", "Under", "Fade originated totals of 235+"))
    if tot <= 218.0:
        fired.append(("S5b", "Over", "Back originated totals of 218 or fewer"))
    TRIGGERS.append(fired)

N_FIRED = sum(len(f) for f in TRIGGERS)


# ================================================================== pages
def p_index() -> str:
    n_blocker = sum(1 for f in C["flags"] if f["kind"] == "Blocker")
    cards = [
        ("executive-summary.html", "Executive summary",
         "What the model does, what it proved, what it did not, and the three blockers."),
        ("methodology.html", "Methodology",
         "Two margin engines, two totals engines, walk-forward design, and the derived constants."),
        ("lines.html", "Originated lines",
         "{} games across the D+1 to D+3 slate, each with a spread, a total and a source link."
         .format(len(LINES))),
        ("projections.html", "Slate projections",
         "Which candidate strategies fire on which game, with each strategy's gate record."),
        ("strategies.html", "Strategy leaderboard",
         "{} candidates, {} passing all seven gates. Empty by design."
         .format(len(STRATS), sum(1 for s in STRATS if s["passed_all_gates"]))),
        ("validation.html", "Validation gates",
         "The seven gates, the statistics behind them, and every strategy's result per gate."),
        ("correlations.html", "Correlations",
         "{} measured, {} blank for missing data. Intervals shown, never point claims."
         .format(sum(1 for c in CORR["rows"] if c["verified"]),
                 sum(1 for c in CORR["rows"] if not c["verified"]))),
        ("injuries.html", "Injuries & rotation",
         "{} rows from the newest official report; minutes impact where it can be sourced."
         .format(len(INJURIES))),
        ("gameflow.html", "Game flow",
         "Pace, rest, overtime, and home court measured on the {} verified games."
         .format(GF["games"])),
        ("data.html", "Data & team ratings",
         "The {} game log, the official team table, and the {} reconciliation checks."
         .format(len(GAMES_CSV), "1,305")),
        ("questions.html", "Questions",
         "{} questions that must be answered before any decision; {} are blocking."
         .format(len(C["questions"]),
                 sum(1 for q in C["questions"] if "BLOCK" in q["status"]))),
        ("suggestions.html", "Suggestions",
         "{} proposals with options and a recommended path. Nothing is implemented."
         .format(len(C["suggestions"]))),
        ("flagged.html", "Flagged for Review",
         "{} items: {} blockers, {} irregularities, {} unverified."
         .format(len(C["flags"]), n_blocker,
                 sum(1 for f in C["flags"] if f["kind"] == "Irregularity"),
                 sum(1 for f in C["flags"] if f["kind"] == "Unverified"))),
        ("repo-review.html", "Repo review",
         "{} findings from a line-by-line read of the repository."
         .format(len(C["repo_review"]))),
        ("sources.html", "Sources",
         "{} official references with retrieval method and limits."
         .format(len(C["sources"]))),
        ("archives.html", "Archives",
         "The six session dashboards that predate this consolidation."),
    ]
    tiles = "".join(
        '<a class="tile" href="{}"><b>{}</b><span>{}</span></a>'.format(h, esc(t), esc(d))
        for h, t, d in cards)

    kpis = [
        (str(M["integrity"]["games_captured"]), "Verified games in the log"),
        (str(len(OOS)), "Out-of-sample walk-forward games"),
        (fmt(M["models"]["C"]["margin"]["rmse"], 2), "Margin RMSE (baseline 17.30)"),
        (fmt(M["models"]["B"]["total"]["rmse"], 2), "Totals RMSE (baseline 19.56)"),
        (str(len(LINES)), "Originated lines published"),
        ("0 / {}".format(len(STRATS)), "Strategies passing all gates"),
        (str(len(INJURIES)), "Injury rows from the official report"),
        ("1,305", "Verification checks, 0 mismatches"),
    ]
    kpi_html = "".join('<div class="kpi"><b>{}</b><small>{}</small></div>'.format(
        esc(v), esc(l)) for v, l in kpis)

    body = """
<div class="grid g4" style="margin-bottom:18px">{kpis}</div>

<div class="card"><div class="stop">
<b>Read this before using any number on this site.</b><br>
NBA.com Terms of Use section 9(iv) states, verbatim:
&ldquo;the NBA Statistics may not be used in connection with any gambling activity
(including legal gambling activity)&rdquo;. Section 9(vii) restricts a comprehensive,
regularly updated statistics database without the Operator's express prior consent.
This site is research output. It holds no market prices, states no expected value, and
recommends no stake. See <a href="flagged.html">Flagged for Review</a>, items F-01 to F-03.
</div></div>

<div class="card"><h2>Where things stand</h2>
<p>The margin model beats a naive baseline out of sample ({mrmse} vs {mbas} RMSE over
{oos} games) but explains only {mvar}% of margin variance. The totals model is
<b>worse</b> than its baseline ({trmse} vs {tbas}) and is published only because the
failure is disclosed. {npass} of {nstrat} candidate strategies pass all seven validation
gates. The two provisional signals (S5, S4b) sit far below the 100-bet sample floor.</p>
<p>Everything downstream of missing data is left blank: three of seven correlation rows,
every player-prop distribution, and every economic figure. Blanks are flagged, never filled.</p>
</div>

<div class="card"><h2>Sections</h2><div class="grid g3">{tiles}</div></div>

<div class="card"><h2>Next three days</h2>
<p class="mut">From the official NBA games pages. Tip times are ET. Injury data exists for
11/14 only; teams file by 5pm local the day before a game, so no 11/15 or 11/16 report
exists yet.</p>
{slate}
</div>
""".format(
        kpis=kpi_html, tiles=tiles,
        mrmse=fmt(M["models"]["C"]["margin"]["rmse"], 2),
        mbas=fmt(M["models"]["C"]["margin_baseline_rmse"], 2),
        trmse=fmt(M["models"]["B"]["total"]["rmse"], 2),
        tbas=fmt(M["models"]["B"]["total_baseline_rmse"], 2),
        oos=len(OOS), mvar=fmt(M["skill"]["margin_variance_explained"] * 100, 1),
        npass=sum(1 for s in STRATS if s["passed_all_gates"]), nstrat=len(STRATS),
        slate=slate_table(compact=True))

    return page("Home", "index.html", body,
                "One dashboard for the whole project: originated lines, gated strategies, "
                "injuries, game flow, and the decisions that are still open.")


def slate_table(compact: bool = False):
    rows = []
    for L in LINES:
        fired = TRIGGERS[LINES.index(L)]
        cells = [
            L["date"],
            L["time_et"],
            '<a href="{}" target="_blank" rel="noopener">{} @ {}</a>'.format(
                esc(L["source_game"]), esc(L["away"]), esc(L["home"])),
            ("{:+g}".format(round(L["orig_spread_home"], 1))
             if not compact else "{:+g}".format(round(L["orig_spread_home"], 1))),
            fmt(L["orig_total"], 1),
            fmt(L["p_home_win"] * 100, 1) + "%",
            "{} / {}".format(L["out_count_away"], L["out_count_home"]),
            (", ".join(f[0] for f in fired) if fired
             else '<span class="mut">none</span>'),
            src(L["source_game"], "game"),
        ]
        rows.append(cells)
    headers = [("Date", False), ("ET", False), ("Matchup", False),
               ("Our spread (home)", True), ("Our total", True),
               ("P(home win)", True), ("Out away/home", True),
               ("Strategies firing", False), ("Source", False)]
    return table(headers, rows, table_id="slate", filter_box=not compact)


def p_exec() -> str:
    blockers = [f for f in C["flags"] if f["kind"] == "Blocker"]
    body = """
<div class="card"><h2>Executive summary</h2>
<p><b>Objective.</b> Originate our own NBA lines, turn them into candidate strategies, and
admit a strategy to a leaderboard only after it passes pre-declared validation gates that
separate skill from luck.</p>
<p><b>What was built.</b> A verified 174-game log for 2026-27 (2026-10-20 to 2026-11-12),
two margin engines and two totals engines, a strictly chronological walk-forward harness
(60-game burn-in, {oos} out-of-sample games), seven validation gates, {nstrat} candidate
strategies, {nline} originated lines for the next three days, a correlation module, an
injury-to-minutes module, and a game-flow module. Every table row on this site links to the
official NBA page it came from.</p>
</div>

<div class="card"><h2>The three results that matter</h2>
<div class="grid g3">
<div class="kpi"><b>{mrmse} vs {mbas}</b><small>Margin RMSE vs naive baseline
(walk-forward, n={oos}). Better, but only {mvar}% of variance explained.</small></div>
<div class="kpi"><b>{trmse} vs {tbas}</b><small>Totals RMSE vs naive baseline.
<b>Worse.</b> Not usable as an edge.</small></div>
<div class="kpi"><b>0 of {nstrat}</b><small>Strategies passing all seven gates.
Two are provisional and under-powered.</small></div>
</div>
<p style="margin-top:14px">Luck was not removed by assertion. It was addressed structurally:
expanding-window walk-forward with no look-ahead, a {burn}-game burn-in, an exact binomial
test against the correct null (not 0.50 for parlays), Benjamini&ndash;Hochberg control at
0.05 across the strategy family, a split-half stability gate, an explicit minimum
sample of 100 bets, and a required-n-for-80%-power figure printed next to every result.
A short-run win rate is never presented as edge.</p>
</div>

<div class="card"><h2>Blockers</h2>
<p class="mut">These stop the project, in this order. Full detail on the
<a href="flagged.html">Flagged for Review</a> page.</p>
{blocker_tbl}
</div>

<div class="card"><h2>What is deliberately blank</h2>
<ul>
<li><b>Every economic figure.</b> No odds feed, no licence, no price snapshots, so no
expected value, return, or closing-line value is stated.</li>
<li><b>Three of seven correlation rows.</b> Player-level dependence needs per-player game
logs, which this project does not hold.</li>
<li><b>Every player-prop distribution.</b> Only season averages and a point projection are
available; a distribution is not.</li>
<li><b>Competition, venue and city for the published slate.</b> Not printed on the official
pages used.</li>
<li><b>Injury data for 11/15 and 11/16.</b> Teams file by 5pm local the day before a game;
those reports did not exist at capture time.</li>
</ul>
</div>

<div class="card"><h2>Recommended next step</h2>
<p>Answer {nq} questions on the <a href="questions.html">Questions</a> page &mdash;
{nblk} of them block everything else &mdash; then choose a path from the
{sug} options on the <a href="suggestions.html">Suggestions</a> page. Nothing on the
suggestions page is implemented; each row is a choice for the owner.</p>
</div>
""".format(
        oos=len(OOS), nstrat=len(STRATS), nline=len(LINES),
        mrmse=fmt(M["models"]["C"]["margin"]["rmse"], 2),
        mbas=fmt(M["models"]["C"]["margin_baseline_rmse"], 2),
        trmse=fmt(M["models"]["B"]["total"]["rmse"], 2),
        tbas=fmt(M["models"]["B"]["total_baseline_rmse"], 2),
        mvar=fmt(M["skill"]["margin_variance_explained"] * 100, 1),
        burn=60,
        blocker_tbl=table(
            [("Flag", False), ("Blocker", False), ("Consequence", False), ("Official source", False)],
            [[f["id"], esc(f["title"]), esc(f["effect"]), src(f["source"], "read")]
             for f in blockers]),
        nq=len(C["questions"]),
        nblk=sum(1 for q in C["questions"] if "BLOCK" in q["status"]),
        sug=len(C["suggestions"]))
    return page("Executive summary", "executive-summary.html", body,
                "What was built, what it proved, and what still blocks it.")


def p_methodology() -> str:
    models = [M["models"][k] for k in ("A", "B", "C")]
    body = """
<div class="card"><h2>How a line is originated</h2>
<p>Two margin engines and two totals engines are fitted on completed games only, then
selected on out-of-sample RMSE. The <b>primary published line</b> is the model that won the
walk-forward comparison; the efficiency-based estimate is shown beside it as a cross-check
only, because it uses season-to-date ratings and putting it in a backtest would leak future
games.</p>
<ol>
<li><b>LM-A additive.</b> Each team's points for and points against per game, league-centred,
combined into a margin.</li>
<li><b>LM-B Massey.</b> Least-squares net ratings plus a home-court constant, fitted by OLS
with a sum-to-zero constraint row to make the system identifiable.</li>
<li><b>LM-C blend.</b> The mean of A and B margins, with the T2 totals estimator.</li>
<li><b>Totals T1.</b> Points-for plus points-against, league-centred.</li>
<li><b>Totals T2.</b> The sum of the two teams' own scoring rates.</li>
</ol>
<p>A team must have at least 3 completed games before it is rated; the first {burn} games
are burn-in and produce no out-of-sample prediction.</p>
</div>

<div class="card"><h2>Walk-forward results</h2>
<p class="mut">Expanding window, strictly chronological. Each game is predicted using only
games that finished before it. n = {oos}.</p>
{model_tbl}
</div>

<div class="card"><h2>Derived constants</h2>
{derived_tbl}
<p class="mut">Every constant above is derived by arithmetic from the verified game log.
None of them is an official NBA statistic.</p>
</div>

<div class="card"><h2>Removing luck</h2>
<p>Luck cannot be removed from a single outcome. It is controlled in the evaluation:</p>
<ul>
<li>Expanding-window walk-forward with a {burn}-game burn-in; no future game ever enters a fit.</li>
<li>Exact binomial test against the correct null. For the two-leg parlay the null is the
joint rate implied by the observed leg rates under independence
({ind:.3f}), not 0.50 &mdash; testing a parlay against 50% would be a category error.</li>
<li>Benjamini&ndash;Hochberg false-discovery-rate control at 0.05 across the eight-strategy family.</li>
<li>Split-half stability: the direction of the effect must hold in both halves of the sample.</li>
<li>A hard minimum sample of 100 bets before anything can be called deployable.</li>
<li>Required n for 80% power at the observed effect size, printed next to every result.</li>
<li>Proper scoring and calibration are the recommended primary metric, not raw win rate
(see suggestion SG-06).</li>
</ul>
</div>

<div class="card"><h2>Reproducing this</h2>
<pre style="background:var(--grey);padding:14px;border-radius:8px;overflow:auto"><code>python3 final/verify.py        # 1,305 line-by-line checks vs official pages
python3 final/build_model.py   # walk-forward, strategies, lines, injury impact
python3 final/build_site.py    # regenerate every page on this site
python3 final/check_site.py    # links, sources, and table integrity</code></pre>
<p class="mut">Standard library only. numpy, scipy and pandas are not available in this
environment.</p>
</div>
""".format(
        burn=60, oos=len(OOS),
        ind=CORR["parlay_independent_rate"],
        model_tbl=table(
            [("Model", False), ("n", True), ("Margin RMSE", True), ("Margin baseline", True),
             ("Margin bias p", True), ("Totals RMSE", True), ("Totals baseline", True),
             ("Source", False)],
            [[esc(m["label"]), m["n"],
              fmt(m["margin"]["rmse"], 2), fmt(m["margin_baseline_rmse"], 2),
              fmt(m["margin_bias_p"], 3),
              fmt(m["total"]["rmse"], 2), fmt(m["total_baseline_rmse"], 2),
              src(SRC_GAMES, "games")] for m in models]),
        derived_tbl=table(
            [("Constant", False), ("Value", True), ("How derived", False), ("Source", False)],
            [["Home-court advantage", fmt(GF["derived_hca"], 2) + " pts",
              "Least squares over 173 non-neutral verified games; two-sided p = "
              + fmt(GF["derived_hca_p"], 3) + ". Not significant at this sample size.",
              src(SRC_GAMES, "games")],
             ["Margin residual SD", fmt(GF["resid_sd_margin"], 2),
              "Root-mean-square of out-of-sample margin errors (n=%d)." % len(OOS),
              src(SRC_GAMES, "games")],
             ["Total residual SD", fmt(GF["resid_sd_total"], 2),
              "Root-mean-square of out-of-sample total errors (n=%d)." % len(OOS),
              src(SRC_GAMES, "games")],
             ["League offensive rating", fmt(GF["lg_off_rtg"], 2),
              "Possession-weighted mean of the official OffRtg column.",
              src(SRC_TEAM, "stats")],
             ["League pace", fmt(GF["lg_pace"], 2),
              "Unweighted mean of the official PACE column across 30 teams.",
              src(SRC_TEAM, "stats")],
             ["Overtime rate", fmt(GF["ot_rate"], 3),
              "{} of {} verified games went to overtime.".format(GF["ot_games"], GF["games"]),
              src(SRC_GAMES, "games")]]))
    return page("Methodology", "methodology.html", body,
                "The engines, the walk-forward design, and the statistics behind the gates.")


def p_lines() -> str:
    rows = []
    for L in LINES:
        fired = TRIGGERS[LINES.index(L)]
        rows.append([
            L["date"],
            L["time_et"],
            '<a href="{}" target="_blank" rel="noopener">{} @ {}</a>'.format(
                esc(L["source_game"]), esc(L["away"]), esc(L["home"])),
            "{:+g}".format(round(L["orig_spread_home"], 1)),
            fmt(L["orig_total"], 1),
            "{} to {}".format(fmt(L["total_lo"], 0), fmt(L["total_hi"], 0)),
            "{:+g} to {:+g}".format(round(L["margin_lo"], 0), round(L["margin_hi"], 0)),
            fmt(L["p_home_win"] * 100, 1) + "%",
            "{:+g}".format(round(L["eff_spread_home"], 1)),
            fmt(L["eff_total"], 1),
            (", ".join("{} {}".format(f[0], f[1]) for f in fired)
             if fired else '<span class="mut">none</span>'),
            src(L["source_game"], "game") + " " + src(SRC_TEAM, "team stats"),
        ])
    body = """
<div class="card"><h2>Originated lines, next three days</h2>
<p>{n} games, {d1} to {d3} (ET). <b>Our spread</b> is quoted the conventional way: negative
means the home team is favoured. <b>Our total</b> includes overtime scoring. The 95% interval
uses the out-of-sample residual SD, so it describes forecast error, not a betting range.</p>
<p><b>This is not a market line.</b> No sportsbook price is held in this repository, so there
is nothing to compare these numbers against and no expected value is stated. The
efficiency-based columns are a cross-check from the official OffRtg/DefRtg/Pace table; they
cannot be walk-forward validated from season-to-date ratings and are shown only to expose
model disagreement.</p>
</div>

<div class="card">
{lines}
</div>

<div class="card"><h2>How to read a row</h2>
<ul>
<li><b>Our spread (home)</b> &mdash; the LM-C blend prediction of home margin, negated.
Selected on out-of-sample RMSE (16.18 vs 17.30 baseline).</li>
<li><b>Our total</b> &mdash; the T2 own-scoring estimator. Its walk-forward RMSE (20.35) is
<b>worse</b> than the naive baseline (19.56). Treat it as a research output, not an edge.</li>
<li><b>P(home win)</b> &mdash; normal CDF of the predicted margin over the residual SD. It
assumes normal residuals and ignores injury uncertainty.</li>
<li><b>Strategies firing</b> &mdash; which candidate rules select this game. Every one of them
is under-powered; see the <a href="strategies.html">leaderboard</a>.</li>
<li><b>Source</b> &mdash; the official NBA game page for the fixture, plus the official team
advanced table that produced the ratings.</li>
</ul>
</div>

<div class="card"><h2>Out-of-sample detail</h2>
<p class="mut">All {oos} walk-forward predictions, with the actual result, so any number on
this page can be recomputed.</p>
{oos_tbl}
</div>
""".format(
        n=len(LINES), d1=LINES[0]["date"], d3=LINES[-1]["date"], oos=len(OOS),
        lines=table(
            [("Date", False), ("ET", False), ("Matchup", False),
             ("Our spread (home)", True), ("Our total", True),
             ("Total 95% interval", True), ("Margin 95% interval", True),
             ("P(home win)", True), ("Cross-check spread", True),
             ("Cross-check total", True), ("Strategies firing", False),
             ("Source", False)],
            rows, table_id="lines", filter_box=True),
        oos_tbl=table(
            [("Date", False), ("Game", False), ("Home", False),
             ("Pred margin", True), ("Actual margin", True), ("Error", True),
             ("Pred total", True), ("Actual total", True), ("Error", True),
             ("Source", False)],
            [[r["date"],
              '<a href="{}" target="_blank" rel="noopener">{} @ {}</a>'.format(
                  esc(game_url(r["away"], r["home"], r["gid"])),
                  esc(r["away"]), esc(r["home"])),
              esc(r["home"]),
              fmt(r["pred_margin"], 1), r["act_margin"],
              fmt(r["act_margin"] - r["pred_margin"], 1),
              fmt(r["pred_total"], 1), r["act_total"],
              fmt(r["act_total"] - r["pred_total"], 1),
              src(game_url(r["away"], r["home"], r["gid"]), "game")]
             for r in OOS], table_id="oos", filter_box=True))
    return page("Originated lines", "lines.html", body,
                "Our own numbers for every game in the next three days, with intervals and sources.")


def p_projections() -> str:
    rows = []
    for i, L in enumerate(LINES):
        fired = TRIGGERS[i]
        if not fired:
            rows.append([
                L["date"], L["time_et"],
                '<a href="{}" target="_blank" rel="noopener">{} @ {}</a>'.format(
                    esc(L["source_game"]), esc(L["away"]), esc(L["home"])),
                '<span class="mut">no candidate rule fires</span>',
                '<span class="mut">&mdash;</span>',
                '<span class="mut">&mdash;</span>',
                src(L["source_game"], "game")])
            continue
        for sid, side, rule in fired:
            s = STRAT_BY_ID[sid]
            rows.append([
                L["date"], L["time_et"],
                '<a href="{}" target="_blank" rel="noopener">{} @ {}</a>'.format(
                    esc(L["source_game"]), esc(L["away"]), esc(L["home"])),
                "<b>{}</b> &mdash; {}".format(esc(sid), esc(rule)),
                side,
                "{} / {} ({:.0%}) out of sample, p = {}, {}".format(
                    s["wins"], s["n"], s["rate"] or 0, fmt(s["p"], 4),
                    esc(s["verdict"].split(" - ")[0])),
                src(L["source_game"], "game")])

    body = """
<div class="card"><div class="stop">
<b>These are not betting picks.</b> Every selection below is a candidate rule evaluated
against <b>our own</b> originated line, not against a market price. This repository holds no
odds, so no expected value, price, stake, or return can be computed or is claimed.
NBA.com Terms of Use section 9(iv) prohibits the use of NBA Statistics in connection with
any gambling activity, including legal gambling activity. See
<a href="flagged.html">F-01</a>.
</div></div>

<div class="card"><h2>Slate projections, next three days</h2>
<p>{n} games. {nfired} selections fired from {nstrat} candidate rules; {ngames} games had no
rule fire. Each selection shows the rule's out-of-sample record so the strength of the
underlying evidence is visible next to the selection itself.</p>
<p class="mut">Coverage caveat: injury data exists for 11/14 only. Five of the ten 11/14 team
reports still read &ldquo;NOT YET SUBMITTED&rdquo; at capture, and no 11/15 or 11/16 report
exists yet. Those selections carry no availability adjustment.</p>
{proj}
</div>

<div class="card"><h2>Why most games show &ldquo;no rule fires&rdquo;</h2>
<p>Only four of the eight candidate rules are slate-selectable (S4, S4b, S5, S5b). The other
four apply to every rated game (S1, S2, S6) or need a rest differential that most games do
not have (S3, n=17 out of 114). A game with no rule firing is a genuine result: the model
has nothing candidate-worthy to say about it under the current rule set.</p>
</div>

<div class="card"><h2>What a real pick would require</h2>
<ol>
<li>A licensed, timestamped market price for the same fixture and market (blocking: F-03).</li>
<li>A settlement rule book: regulation or including overtime, pushes, prop void rules
(open: Q-10).</li>
<li>A prediction cut-off and staleness rule, so a line is never published on stale
availability data (open: Q-09, suggestion SG-13).</li>
<li>A strategy that passes all seven gates. None does today (F-11).</li>
<li>Resolution of the NBA Terms of Use position (blocking: F-01, F-02).</li>
</ol>
</div>
""".format(n=len(LINES), nfired=N_FIRED, nstrat=len(STRATS),
           ngames=sum(1 for f in TRIGGERS if not f),
           proj=table([("Date", False), ("ET", False), ("Matchup", False),
                       ("Candidate rule", False), ("Side", False),
                       ("Rule's out-of-sample record", False), ("Source", False)],
                      rows, table_id="proj", filter_box=True))
    return page("Slate projections", "projections.html", body,
                "Which candidate rules select which game in the next three days, and why most "
                "games select nothing.")


def p_strategies() -> str:
    rows = []
    for s in STRATS:
        g = s["gates"]
        gate_cells = []
        for key in ("G3_sample_n_ge_100", "G4_powered_observed_effect_n_needed",
                    "G5_raw_p_lt_0.05", "G6_survives_bh_fdr_0.05",
                    "G7_split_half_direction_stable"):
            v = g.get(key)
            if v is True:
                gate_cells.append(badge("pass", "ok"))
            elif v is False:
                gate_cells.append(badge("fail", "bad"))
            elif key == "G4_powered_observed_effect_n_needed":
                gate_cells.append("needs n&ge;{}".format(esc(v)))
            else:
                gate_cells.append(blank("n/a"))
        verdict = s["verdict"]
        kind = "ok" if verdict.startswith("PASSED") else (
            "warn" if verdict.startswith("PROVISIONAL") else "bad")
        rows.append([
            "<b>{}</b>".format(esc(s["id"])),
            esc(s["label"]),
            esc(s["rule"]),
            s["n"],
            "{} / {}".format(s["wins"], s["n"]),
            fmt(s["rate"], 3),
            fmt(s["p"], 4),
            fmt(s["p_null"], 3),
            " ".join(gate_cells),
            badge(verdict.split(" - ")[0], kind),
            src(SRC_GAMES, "games"),
        ])
    body = """
<div class="card"><h2>Strategy leaderboard</h2>
<p>{n} candidates across single bets, totals, rest, and a two-leg same-game parlay.
<b>{npass} pass all seven gates.</b> The leaderboard is empty by design: a strategy is not
ranked until it clears the gates, and none has.</p>
<p class="mut">The null differs by market. Single bets are tested against 0.50; the parlay
(S6) is tested against the joint rate implied by the observed leg rates under independence
({ind:.3f}), because testing a two-leg parlay against 50% would be a category error.</p>
{lb}
</div>

<div class="card"><h2>The two provisional signals, honestly</h2>
<div class="grid g2">
<div class="kpi"><b>S5 &mdash; fade totals of 235+</b>
<small>21 of 24 out of sample, p = 0.0003. Survives Benjamini&ndash;Hochberg at 0.05 and is
split-half stable. But 80% power at the observed effect needs n &ge; 56, and the sample gate
requires 100. It is also built on the totals model, which is <b>worse than its baseline</b>
out of sample &mdash; so this is more likely a bias in the estimator than an edge.</small></div>
<div class="kpi"><b>S4b &mdash; back road favourites of 8+</b>
<small>20 of 28 out of sample, p = 0.036. Does <b>not</b> survive Benjamini&ndash;Hochberg at
0.05 across the eight-strategy family, and needs n &ge; 171 for 80% power. Eight candidates
were tested, so one p-value near 0.04 is about what chance produces.</small></div>
</div>
</div>

<div class="card"><h2>Removing luck, in practice</h2>
<ul>
<li><b>G3</b> hard floor of 100 bets before anything can be called deployable.</li>
<li><b>G4</b> prints the sample needed for 80% power at the observed effect. S1 would need
102,005 bets; S3 would need 9,074. That is what "no evidence" looks like when stated
honestly.</li>
<li><b>G6</b> Benjamini&ndash;Hochberg at 0.05 across the whole family, so testing eight
candidates does not manufacture a winner.</li>
<li><b>G7</b> split-half direction stability, which S3 and S5b both fail.</li>
<li><b>G1/G2</b> provenance and no-look-ahead are structural: every input is an official NBA
page, and every prediction uses only games that finished earlier.</li>
</ul>
<p>What is <i>not</i> yet in place: a proper-scoring-rule primary metric (Brier / log loss)
and calibration reporting. That is suggestion SG-06, awaiting a decision.</p>
</div>
""".format(n=len(STRATS),
           npass=sum(1 for s in STRATS if s["passed_all_gates"]),
           ind=CORR["parlay_independent_rate"],
           lb=table([("ID", False), ("Strategy", False), ("Rule", False), ("n", True),
                     ("Wins", True), ("Rate", True), ("p", True), ("Null", True),
                     ("Gates G3-G7", False), ("Verdict", False), ("Source", False)],
                    rows))
    return page("Strategy leaderboard", "strategies.html", body,
                "Candidate rules, their out-of-sample record, and their result on each gate.")


def p_validation() -> str:
    gate_defs = [
        ("G1", "Data provenance",
         "Every input traces to an official NBA page, captured with its URL and retrieval date.",
         "Pass by construction", "ok"),
        ("G2", "No look-ahead",
         "Expanding-window walk-forward; each prediction uses only games that finished earlier.",
         "Pass by construction", "ok"),
        ("G3", "Minimum sample",
         "n &ge; 100 bets before a strategy is eligible.",
         "2 of 8 candidates reach it (S1, S2, S6 at n=114)", "warn"),
        ("G4", "Power",
         "Sample required for 80% power at the observed effect size, printed for each.",
         "Best case needs n &ge; 56; most need thousands", "bad"),
        ("G5", "Raw significance",
         "Exact binomial test against the correct null, two-sided, p &lt; 0.05.",
         "2 of 8 (S5 p=0.0003, S4b p=0.036)", "warn"),
        ("G6", "Multiple comparisons",
         "Benjamini&ndash;Hochberg false-discovery-rate control at 0.05 across the family.",
         "1 of 8 (S5 only)", "bad"),
        ("G7", "Split-half stability",
         "The direction of the effect must hold in the first and second half of the sample.",
         "6 of 8; S3 and S5b fail", "warn"),
    ]
    body = """
<div class="card"><h2>The seven validation gates</h2>
<p>A strategy must clear all seven before it is eligible for the leaderboard. The thresholds
are <b>proposed, not approved</b> &mdash; see question Q-07 and suggestion SG-06.</p>
{gates}
</div>

<div class="card"><h2>Statistics used, and why</h2>
<ul>
<li><b>Exact binomial test.</b> Used instead of a normal approximation because several
candidate samples are small (n = 11 and n = 17), where the normal approximation is invalid.</li>
<li><b>Benjamini&ndash;Hochberg</b> at 0.05 across the eight-strategy family, so that testing
eight candidates does not manufacture a false positive.</li>
<li><b>Pearson r with a Fisher z interval.</b> Every correlation is reported with a 95%
confidence interval. An interval containing zero is described as inconclusive, never as a
point value.</li>
<li><b>Student-t</b> for bias and for paired squared-error comparisons against the naive
baseline, implemented from the incomplete beta function (no scipy available).</li>
<li><b>OLS with a sum-to-zero constraint row</b> to make the Massey rating system
identifiable.</li>
</ul>
<p class="mut">All of these are implemented from first principles in
<code>model/nbastats.py</code>; exact-binomial bounds follow the method set out in the NIST
e-Handbook, section 7.2.7.1.</p>
</div>

<div class="card"><h2>Result per gate, per strategy</h2>
{per_gate}
</div>

<div class="card"><h2>What the gates cannot fix</h2>
<ul>
<li><b>No market price.</b> G1&ndash;G7 test self-consistency against our own line. They
cannot test profitability, because no odds are held (F-03).</li>
<li><b>One season, 114 out-of-sample games.</b> No regime test, no multi-season test, no
ablation is possible yet.</li>
<li><b>Selection bias risk.</b> The eight rules were chosen by us, on this sample. A
pre-registered rule set and a frozen model register (SG-12) are needed before any of this is
treated as confirmatory.</li>
</ul>
</div>
""".format(
        gates=table([("Gate", False), ("Name", False), ("Requirement", False),
                     ("Current status across the 8 candidates", False), ("", False),
                     ("Source", False)],
                    [[g[0], esc(g[1]), esc(g[2]), esc(g[3]), badge(g[4], g[4]),
                      src(SRC_GAMES, "games")] for g in gate_defs]),
        per_gate=table(
            [("ID", False), ("Strategy", False), ("n", True), ("G3 &ge;100", False),
             ("G4 n needed", True), ("G5 p&lt;.05", False), ("G6 FDR", False),
             ("G7 stable", False), ("Verdict", False), ("Source", False)],
            [[s["id"], esc(s["label"]), s["n"],
              badge("pass", "ok") if s["gates"]["G3_sample_n_ge_100"] else badge("fail", "bad"),
              s["gates"]["G4_powered_observed_effect_n_needed"],
              badge("pass", "ok") if s["gates"]["G5_raw_p_lt_0.05"] else badge("fail", "bad"),
              badge("pass", "ok") if s["gates"]["G6_survives_bh_fdr_0.05"] else badge("fail", "bad"),
              badge("pass", "ok") if s["gates"]["G7_split_half_direction_stable"] else badge("fail", "bad"),
              esc(s["verdict"].split(" - ")[0]),
              src(SRC_GAMES, "games")] for s in STRATS]))
    return page("Validation gates", "validation.html", body,
                "Seven gates, the statistics behind them, and how every candidate scored.")


def p_correlations() -> str:
    rows = []
    for c in CORR["rows"]:
        if c["verified"]:
            val = fmt(c["value"], 3)
            ci = "{} to {}".format(fmt(c["ci95"][0], 3), fmt(c["ci95"][1], 3))
            src_cell = src(c["source"] or SRC_GAMES, "official")
            state = badge("measured", "ok")
        else:
            val = blank("no data")
            ci = blank("no data")
            src_cell = src(SRC_PLAYER, "needed source")
            state = badge("cannot be measured", "warn")
        rows.append([esc(c["pair"]), esc(c["stat"]), val, ci,
                     c["n"] if c["n"] else blank("n/a"),
                     state, esc(c["note"]), src_cell])
    body = """
<div class="card"><h2>Correlations</h2>
<p>Every measured value is reported with its 95% confidence interval. A value whose interval
contains zero is described as inconclusive. No value is entered where the underlying data does
not exist.</p>
{corr}
</div>

<div class="card"><h2>What the numbers say</h2>
<ul>
<li><b>Home points vs away points, same game: r = {rha:.3f}</b> over {ng} games. A game total
is mildly correlated with how one-sided it is, but the effect is small.</li>
<li><b>Spread residual vs total residual: r = {rmt:.3f}</b>, 95% CI {cilo:.3f} to {cihi:.3f},
n = {noos} out-of-sample. The interval contains zero, so dependence between a side and a
total in the same game is <b>not established</b> at this sample size.</li>
<li><b>Joint parlay hit rate {joint:.3f}</b> against {ind:.3f} under independence. The two are
close; a two-leg same-game parlay built on our own spread and total behaves, on this sample,
about as independence would predict. That is a statement about our lines, not about any
market price.</li>
<li><b>Cross-game parlays</b> are marked unverified. Independence across different games is an
<i>assumption</i>, not a measured result, and no interval is available.</li>
</ul>
</div>

<div class="card"><h2>What is blocked, and by what</h2>
<p>Three rows are blank for the same reason: this project holds season-to-date player
averages, not per-player game logs. Same-team player-player correlations, and within-player
stat combinations, cannot be computed from averages alone. Capturing
<code>nba.com/stats/players/boxscores</code> by date would unblock them &mdash; see question
Q-06 and suggestion SG-03.</p>
<div class="warn"><b>Do not multiply marginals.</b> Until leg dependence is measured with an
interval, any same-game parlay price derived by multiplying independent probabilities is an
assumption presented as a number.</div>
</div>
""".format(corr=table([("Pair", False), ("Statistic", False), ("Value", True),
                       ("95% CI", True), ("n", True), ("Status", False),
                       ("Note", False), ("Source", False)], rows),
           rha=CORR["rows"][0]["value"], ng=CORR["n_games_total"],
           rmt=CORR["rows"][1]["value"],
           cilo=CORR["rows"][1]["ci95"][0], cihi=CORR["rows"][1]["ci95"][1],
           noos=CORR["n_games_oos"],
           joint=CORR["parlay_joint_rate"], ind=CORR["parlay_independent_rate"])
    return page("Correlations", "correlations.html", body,
                "Measured dependence with intervals, and the rows that cannot be measured yet.")


def p_injuries() -> str:
    rows = []
    for r in INJURIES:
        inh = r.get("attribution") == "inherited"
        team_cell = esc(r["team"])
        if inh:
            team_cell += ' <span class="b">inherited</span>'
        if r["status"] == "NOT YET SUBMITTED":
            rows.append([esc(r["game_date"]), esc(r["game_time_et"]),
                         esc(r["matchup"]) if r["matchup"] else blank("not printed"),
                         team_cell, blank("no player listed"),
                         badge("NOT YET SUBMITTED", "bad"),
                         '<span class="mut">team had not filed at capture time</span>',
                         src(SRC_INJ, "report")])
            continue
        rows.append([esc(r["game_date"]), esc(r["game_time_et"]),
                     esc(r["matchup"]) if r["matchup"] else blank("not printed"),
                     team_cell, esc(r["player"]),
                     badge(r["status"], {"Out": "bad", "Doubtful": "bad",
                                         "Questionable": "warn", "Probable": "warn",
                                         "Available": "ok"}.get(r["status"], "")),
                     esc(r["reason"]), src(SRC_INJ, "report")])

    impact_rows = []
    for r in IMPACT:
        if not r["report_submitted"]:
            vac = blank("team had not filed")
        elif r["minutes_vacuum_quantified"] is not None:
            vac = fmt(r["minutes_vacuum_quantified"], 1) + " mpg"
        else:
            vac = blank("no data")
        impact_rows.append([
            r["date"], esc(r["team"]), esc(r["opponent"]), esc(r["home_away"]),
            badge("filed", "ok") if r["report_submitted"] else badge("NOT YET SUBMITTED", "bad"),
            r["players_listed"], r["out_or_doubtful"],
            r["captured_players"],
            vac,
            src(SRC_INJ, "report")])

    prop_rows = []
    for p in PROPS:
        prop_rows.append([
            p["date"], esc(p["team"]), esc(p["player"]),
            badge(p["status"], {"Out": "bad", "Doubtful": "bad", "Questionable": "warn",
                                "Probable": "warn", "Available": "ok",
                                "Not listed": ""}.get(p["status"], "")),
            fmt(p["season_min"], 1), fmt(p["season_pts"], 1),
            fmt(p["season_reb"], 1), fmt(p["season_ast"], 1),
            fmt(p["projected_min"], 1),
            fmt(p["proj_pts"], 1) + " " + badge("unverified", "warn"),
            src(SRC_PLAYER, "player stats") + " " + src(SRC_INJ, "report"),
        ])

    body = """
<div class="card"><div class="warn">
<b>Coverage.</b> The newest report on the official index at capture time was
<b>11/13/2026 07:30 PM ET</b>. It covers the 11/13 games and the 11/14 slate only. Five of the
ten 11/14 team reports read &ldquo;NOT YET SUBMITTED&rdquo; (NOP, CLE, MEM, CHI, MIA).
No 11/15 or 11/16 report exists yet: teams must file by 5pm local time the day before a game.
Absence of a row is not absence of an injury.
</div></div>

<div class="card"><h2>Official injury report, {n} rows</h2>
<p class="mut">A status is a timestamped team filing, not a medical clearance and not a
minutes forecast. Status can change after capture.</p>
{inj}
</div>

<div class="card"><h2>Injury to rotation minutes</h2>
<p>Where an injured player appears in the official top-31 minutes table, their season minutes
are weighted by status (Out 0.0, Doubtful 0.25, Questionable 0.6, Probable 0.9, Available 1.0)
to produce a minutes vacuum. Where they do not, the figure is left blank.</p>
<p class="mut"><b>The weighting is an assumption, not an official value</b>, and every vacuum
figure is a <b>floor</b>: only the top 31 players by minutes are held, so an injured player
outside that set contributes nothing (F-12).</p>
{imp}
</div>

<div class="card"><h2>Player projections</h2>
<p>Season averages are official. The projection scales them by a projected-minutes multiple
under an <b>unverified</b> pro-rata redistribution assumption, with no per-player game logs.
No over/under distribution for any player market is established (F-17).</p>
{props}
</div>
""".format(n=len(INJURIES),
           inj=table([("Game date", False), ("Time ET", False), ("Matchup", False),
                      ("Team", False), ("Player", False), ("Status", False),
                      ("Reason", False), ("Source", False)],
                     rows, table_id="injuries", filter_box=True),
           imp=table([("Date", False), ("Team", False), ("Opponent", False),
                      ("Home/Away", False), ("Report", False), ("Players listed", True),
                      ("Out or doubtful", True), ("Captured players", True),
                      ("Minutes vacuum", True), ("Source", False)],
                     impact_rows, table_id="impact", filter_box=True),
           props=table([("Date", False), ("Team", False), ("Player", False),
                        ("Status", False), ("Season MIN", True), ("Season PTS", True),
                        ("Season REB", True), ("Season AST", True),
                        ("Projected MIN", True), ("Projected PTS", True),
                        ("Source", False)],
                       prop_rows, table_id="props", filter_box=True))
    return page("Injuries & rotation", "injuries.html", body,
                "The newest official report, what it covers, and what it cannot tell us.")


def p_gameflow() -> str:
    pace_rows = [[esc(r["team"]), esc(TEAM_NAMES.get(r["team"], r["team"])),
                  fmt(r["pace"], 2), fmt(r["off_rtg"], 1), fmt(r["def_rtg"], 1),
                  fmt(r["net_rtg"], 1), src(team_url(r["team"]), "team")]
                 for r in GF["pace_leaders"]]
    rest = GF["rest_distribution"]
    body = """
<div class="card"><h2>Game flow, measured on {n} verified games</h2>
<div class="grid g4" style="margin-bottom:16px">
<div class="kpi"><b>{ot}</b><small>overtime games ({otrate:.1%} of all games)</small></div>
<div class="kpi"><b>{hw} / {hg}</b><small>home wins / non-neutral games</small></div>
<div class="kpi"><b>{avg}</b><small>mean game total</small></div>
<div class="kpi"><b>{b2b}</b><small>games with a team on the second night of a back-to-back
({b2brate:.1%})</small></div>
</div>
{flow_tbl}
</div>

<div class="card"><h2>Pace and efficiency</h2>
<p>From the official team advanced table, season to date. Pace is possessions per 48 minutes;
offensive and defensive rating are points per 100 possessions. A high-pace, high-offence
matchup is where a totals forecast has the most room to be wrong &mdash; which matters, because
our totals model is currently worse than its baseline.</p>
{pace}
</div>

<div class="card"><h2>Rest</h2>
<p>Derived from the official game dates: days since each team's previous game.</p>
{rest_tbl}
<p class="mut">S3 (rest differential of two days or more) produced {s3n} qualifying games out
of {oos} out-of-sample, at {s3rate:.0%}. It fails both raw significance and split-half
stability. Rest is measured; it is not yet shown to be an edge.</p>
</div>

<div class="card"><h2>Score state and rotation</h2>
<p>Blowouts and close games change minutes in ways this project cannot yet measure: no
play-by-play and no rotation data are held. What is measured is the overtime effect on the
total: regulation games average {reg:.1f} points, overtime games average {otavg:.1f}.
Nine of {n} games went to overtime.</p>
<p class="mut">Every total on the <a href="lines.html">lines page</a> includes overtime
scoring, because that is how the source scores are recorded. If a settlement rule settles on
regulation only, this is a material difference &mdash; see question Q-10.</p>
</div>
""".format(
        n=GF["games"], ot=GF["ot_games"], otrate=GF["ot_rate"],
        hw=GF["home_wins"], hg=GF["home_games"],
        avg=fmt(GF["avg_total"], 1), b2b=GF["b2b_games"], b2brate=GF["b2b_rate"],
        reg=GF["avg_total_regulation"], otavg=GF["avg_total_ot"],
        flow_tbl=table(
            [("Measure", False), ("Value", True), ("Basis", False), ("Source", False)],
            [["Mean home margin", fmt(GF["home_margin_mean"], 2),
              "Home points minus away points, 173 non-neutral games.", src(SRC_GAMES, "games")],
             ["Fitted home-court advantage", fmt(GF["derived_hca"], 2) + " pts",
              "Least squares with team ratings. Two-sided p = "
              + fmt(GF["derived_hca_p"], 3) + ", df = " + str(GF["derived_hca_df"])
              + ". Not significant at this sample.", src(SRC_GAMES, "games")],
             ["Mean total, regulation", fmt(GF["avg_total_regulation"], 2),
              "{} games.".format(GF["games"] - GF["ot_games"]), src(SRC_GAMES, "games")],
             ["Mean total, overtime", fmt(GF["avg_total_ot"], 2),
              "{} games.".format(GF["ot_games"]), src(SRC_GAMES, "games")],
             ["League pace", fmt(GF["lg_pace"], 2),
              "Mean of the official PACE column, 30 teams.", src(SRC_TEAM, "stats")],
             ["League offensive rating", fmt(GF["lg_off_rtg"], 2),
              "Possession-weighted mean of the official OffRtg column.", src(SRC_TEAM, "stats")],
             ["Margin residual SD", fmt(GF["resid_sd_margin"], 2),
              "Out-of-sample, n = {}.".format(len(OOS)), src(SRC_GAMES, "games")],
             ["Total residual SD", fmt(GF["resid_sd_total"], 2),
              "Out-of-sample, n = {}.".format(len(OOS)), src(SRC_GAMES, "games")]]),
        pace=table([("Team", False), ("Name", False), ("Pace", True), ("OffRtg", True),
                    ("DefRtg", True), ("NetRtg", True), ("Source", False)],
                   pace_rows, table_id="pace", filter_box=True),
        rest_tbl=table([("Rest days", False), ("Team-games", True), ("Share", True),
                        ("Source", False)],
                       [[k, v, "{:.1%}".format(v / (2 * GF["games"])),
                         src(SRC_GAMES, "games")]
                        for k, v in sorted(rest.items(), key=lambda x: str(x[0]))]),
        s3n=STRAT_BY_ID["S3"]["n"], oos=len(OOS),
        s3rate=STRAT_BY_ID["S3"]["rate"] or 0)
    return page("Game flow", "gameflow.html", body,
                "Pace, rest, overtime and home court, measured on the verified game log.")


def p_data() -> str:
    team_rows = []
    for abbr in sorted(RATINGS, key=lambda t: -RATINGS[t]["massey_rating"]):
        r = RATINGS[abbr]
        team_rows.append([
            esc(abbr), esc(TEAM_NAMES.get(abbr, abbr)),
            r["gp"], "{}-{}".format(r["w"], r["l"]),
            fmt(r["off_rtg"], 1), fmt(r["def_rtg"], 1), fmt(r["net_rtg"], 1),
            fmt(r["pace"], 2), fmt(r["efg_pct"], 1), fmt(r["tov_pct"], 1),
            fmt(r["massey_rating"], 2),
            src(team_url(abbr), "team")])
    game_rows = []
    for g in GAMES_CSV:
        game_rows.append([
            esc(g["date"]), esc(g["game_id"]),
            '<a href="{}" target="_blank" rel="noopener">{} @ {}</a>'.format(
                esc(game_url(g["away"], g["home"], g["game_id"])),
                esc(g["away"]), esc(g["home"])),
            g["away_pts"], g["home_pts"],
            badge("OT", "warn") if g["ot"] == "1" else '<span class="mut">no</span>',
            src(SRC_GAMES + g["date"], "date")])
    body = """
<div class="card"><h2>Verification</h2>
<p>Every stored value was checked against the official page it came from. <b>1,305 checks,
0 mismatches.</b></p>
{ver}
<p class="mut">The strongest single check is the game-log reconciliation: recomputing every
team's games played, wins and losses from the {ng} stored scores reproduces the official GP,
W and L columns for all 30 teams, and the team-game total ({tg}) matches the sum of the
official GP column exactly. A single wrong score would almost certainly break it.</p>
<p>One date (2026-11-12, four games) was additionally checked score-by-score against the
official games page: TOR 112 @ PHI 123, DET 144 @ WAS 140 (OT), DAL 94 @ MIN 133,
CHA 96 @ PHX 101 &mdash; all four matched.</p>
</div>

<div class="card"><h2>Team ratings</h2>
<p>Official advanced columns plus our fitted Massey rating. The Massey rating is derived by
this project; everything else on this table is copied from the official page.</p>
{teams}
</div>

<div class="card"><h2>Game log, {ng} verified games</h2>
<p class="mut">2026-10-20 to 2026-11-12. Nine games of 11/13 were still in progress at capture
time and are not included (F-15).</p>
{games}
</div>

<div class="card"><h2>Inputs held, and their limits</h2>
{inputs}
</div>
""".format(
        ng=len(GAMES_CSV), tg=2 * len(GAMES_CSV),
        ver=table([("Dataset", False), ("Checks", True), ("Mismatches", True),
                   ("Official reference", False)],
                  [["Team advanced table (30 teams x 19 columns)", 570, 0, src(SRC_TEAM, "NBA Stats")],
                   ["Player table (31 rows x 10 fields)", 310, 0, src(SRC_PLAYER, "NBA Stats")],
                   ["Game log vs official GP / W / L (30 teams)", 91, 0, src(SRC_TEAM, "NBA Stats")],
                   ["Upcoming slate structure (22 games)", 89, 0, src(SRC_GAMES, "NBA Games")],
                   ["Injury report structure (122 rows)", 245, 0, src(SRC_INJ, "PDF")]]),
        teams=table([("Team", False), ("Name", False), ("GP", True), ("W-L", False),
                     ("OffRtg", True), ("DefRtg", True), ("NetRtg", True), ("Pace", True),
                     ("eFG%", True), ("TOV%", True), ("Massey (derived)", True),
                     ("Source", False)], team_rows, table_id="teams", filter_box=True),
        games=table([("Date", False), ("Game ID", False), ("Matchup", False),
                     ("Away pts", True), ("Home pts", True), ("OT", False), ("Source", False)],
                    game_rows, table_id="gamelog", filter_box=True),
        inputs=table([("Input", False), ("Rows", True), ("Official source", False),
                      ("Limit", False)],
                     [["Completed game log", len(GAMES_CSV), src(SRC_GAMES, "NBA Games"),
                       "Stops at 2026-11-12; nine 11/13 games were in progress."],
                      ["Team advanced table", 30, src(SRC_TEAM, "NBA Stats"),
                       "Season to date only; no historical seasons held."],
                      ["Player table (top 31 by minutes)", 31, src(SRC_PLAYER, "NBA Stats"),
                       "About 465 rows exist officially. Every minutes-vacuum figure is a floor."],
                      ["Upcoming slate D+1 to D+3", 22, src(SRC_GAMES, "NBA Games"),
                       "Competition, venue and city not printed on the source page."],
                      ["Injury report 11/13 07:30 PM ET", 122, src(SRC_INJ, "PDF"),
                       "Covers 11/13 and 11/14 only. 60 rows carry team/matchup by PDF cell merging."],
                      ["Market prices", 0, src(SRC_TERMS, "Terms of Use"),
                       "None held, and the Terms restrict use. Every economic figure on this "
                       "site is therefore blank (F-03)."]]))
    return page("Data & team ratings", "data.html", body,
                "The verified inputs, the reconciliation that proves them, and their limits.")


def p_questions() -> str:
    cats = defaultdict(list)
    for q in C["questions"]:
        cats[q["category"]].append(q)
    blocks = []
    for cat in sorted(cats):
        rows = []
        for q in cats[cat]:
            st = q["status"]
            kind = "bad" if "BLOCK" in st else ("ok" if "Answered" in st else "warn")
            rows.append(["<b>{}</b>".format(esc(q["id"])), esc(q["question"]),
                         badge(st, kind), esc(q["known"]), esc(q["missing"]),
                         esc(q["discovery"]), esc(q["owner"]),
                         src(q.get("source", ""), q.get("source_label", "source"))])
        blocks.append('<div class="card"><h2>{}</h2>{}</div>'.format(
            esc(cat),
            table([("ID", False), ("Question", False), ("Status", False),
                   ("What we already know", False), ("What is missing", False),
                   ("How to discover it", False), ("Decision owner", False),
                   ("Source", False)], rows)))
    body = """
<div class="card"><h2>Questions that must be answered before any decision</h2>
<p>{n} questions. {nb} are blocking: nothing further can responsibly be decided until they are
answered. Each row separates what this repository and the linked official pages actually
establish from what is still unknown, and names the step that would close the gap.</p>
<p class="mut">Where the honest answer is &ldquo;not established&rdquo;, it is written as
such. Nothing on this page is inferred.</p>
</div>
{blocks}
<div class="card"><h2>How these map to the suggestions</h2>
<p>Each blocking question has at least one option on the
<a href="suggestions.html">Suggestions</a> page. The mapping is by dependency: pick a path
there, and the questions it closes are listed with it.</p>
</div>
""".format(n=len(C["questions"]),
           nb=sum(1 for q in C["questions"] if "BLOCK" in q["status"]),
           blocks="".join(blocks))
    return page("Questions", "questions.html", body,
                "What we know, what we do not, and how to find out.")


def p_suggestions() -> str:
    rows = []
    for s in C["suggestions"]:
        rows.append([
            "<b>{}</b>".format(esc(s["id"])), esc(s["area"]), esc(s["suggestion"]),
            esc(s["why"]), esc(s["options"]),
            "<b>{}</b>".format(esc(s["recommended"])), esc(s["dependency"]),
            badge(s["decision"], "warn"),
            src(REPO_URL + "/blob/main/final/data/content.json", "register")])
    body = """
<div class="card"><h2>Suggestions for improving the site and the decisions behind it</h2>
<p>{n} proposals. <b>None is implemented.</b> Each row gives the options, the recommended
path, and what it depends on, so a reviewer can pick a direction before anything changes.
Nothing on this page will be built until it is chosen.</p>
</div>

<div class="card">
{sug}
</div>

<div class="card"><h2>Suggested discovery steps for the missing information</h2>
<ol>
<li><b>Settle the rights question first (SG-01).</b> One written decision on whether NBA data
may be used for the intended purpose determines whether the rest of this project is research
or something that needs a licence.</li>
<li><b>Then the feed question (SG-02).</b> Without timestamped prices, no economic claim is
possible, and the leaderboard can only score calibration.</li>
<li><b>Then close the data gaps (SG-03, SG-04).</b> Per-player game logs unlock three blank
correlation rows and every prop distribution. The full minutes table turns minutes-vacuum
floors into real figures.</li>
<li><b>Then fix the model (SG-05).</b> A totals model that loses to a naive baseline should
not be published as a betting signal.</li>
<li><b>Then the operating rules (SG-12, SG-13, SG-14).</b> Model register, cut-off and
staleness rules, and settlement rules &mdash; before anything is scored as a result.</li>
<li><b>Meanwhile, clean up the site (SG-08, SG-09, SG-10, SG-11).</b> One dashboard, one
deploy mechanism, a licence, and no non-official data files.</li>
</ol>
</div>
""".format(n=len(C["suggestions"]),
           sug=table([("ID", False), ("Area", False), ("Suggestion", False),
                      ("Why it matters", False), ("Options", False),
                      ("Recommended", False), ("Depends on", False),
                      ("Decision", False), ("Source", False)], rows))
    return page("Suggestions", "suggestions.html", body,
                "Options with a recommended path. Nothing here is implemented until chosen.")


def p_flagged() -> str:
    order = {"Blocker": 0, "Irregularity": 1, "Unverified": 2}
    flags = sorted(C["flags"], key=lambda f: (order.get(f["kind"], 9), f["id"]))
    rows = []
    for f in flags:
        kind = {"Blocker": "bad", "Irregularity": "warn", "Unverified": ""}.get(f["kind"], "")
        rows.append(["<b>{}</b>".format(esc(f["id"])),
                     badge(f["kind"], kind), esc(f["title"]), esc(f["detail"]),
                     esc(f["effect"]), src(f["source"], "official")])
    n_b = sum(1 for f in C["flags"] if f["kind"] == "Blocker")
    n_i = sum(1 for f in C["flags"] if f["kind"] == "Irregularity")
    n_u = sum(1 for f in C["flags"] if f["kind"] == "Unverified")
    body = """
<div class="card"><div class="stop">
<b>{nb} blockers.</b> These stop the project. They are published here, with the official
source for each, so they can be reviewed after the site is live.
</div></div>

<div class="card"><h2>Flagged for Review &mdash; {n} items</h2>
<p>{nb} blockers, {ni} irregularities, {nu} unverified. Every item links to the official page
that establishes it.</p>
{flagged}
</div>

<div class="card"><h2>The two verbatim terms quotes</h2>
<div class="note">
<p><b>NBA.com Terms of Use, section 9, clause (iv)</b> &mdash; read on the official page on
2026-11-13:</p>
<p style="font-style:italic">&ldquo;the NBA Statistics may not be used in connection with any
gambling activity (including legal gambling activity)&rdquo;</p>
<p><b>Section 9, clause (vii)</b> &mdash; NBA Statistics may not be used in connection with
any website, product, or service that features a database of comprehensive, regularly updated
statistics from NBA games &ldquo;without the Operator's express prior consent&rdquo;.</p>
<p><b>Section 1</b> &mdash; material may not be used &ldquo;for public or commercial purposes
on any other Website&rdquo; without written permission.</p>
<p style="margin-bottom:0">Source: {src}</p>
</div>
<p style="margin-top:14px">This is why the site holds no odds, states no expected value, and
recommends no stake. It is also why question Q-13 and suggestion SG-01 exist.</p>
</div>
""".format(n=len(C["flags"]), nb=n_b, ni=n_i, nu=n_u,
           src=src(SRC_TERMS, "https://www.nba.com/termsofuse"),
           flagged=table([("ID", False), ("Kind", False), ("Item", False),
                          ("Detail", False), ("Consequence", False), ("Source", False)],
                         rows))
    return page("Flagged for Review", "flagged.html", body,
                "Blockers, irregularities, and unverified values, each with its official source.")


def p_repo_review() -> str:
    rows = []
    for r in C["repo_review"]:
        st = r["status"]
        kind = "ok" if "Verified" in st or "Adequate" in st or "Works" in st else (
            "bad" if "Flagged" in st or "Gap" in st else "warn")
        rows.append(["<b>{}</b>".format(esc(r["id"])), esc(r["area"]),
                     "<code>{}</code>".format(esc(r["file"])), esc(r["finding"]),
                     badge(st, kind), esc(r["action"]), src(r["source"], "evidence")])
    body = """
<div class="card"><h2>Repository review</h2>
<p>A line-by-line read of the repository as it stood at the start of this session:
{n} findings across the root, the six session dashboards, the data directories, CI, and the
test suites. Each finding names the file, what was found, and the action proposed.</p>
<p class="mut">Prior sessions' own review registers are preserved and linked from the
<a href="archives.html">Archives</a> page. This page does not overwrite them; it reviews the
repository as a whole, including them.</p>
{rr}
</div>

<div class="card"><h2>What the review concluded</h2>
<ul>
<li>The <b>analysis code is sound</b>. <code>model/nbastats.py</code> implements the
statistics from first principles and runs clean; the pipeline reproduces every published
number.</li>
<li>The <b>data is verifiable and verified</b>, but only for the consolidated set in
<code>final/data</code>. Four other representations of the same game log exist and are not
reconciled to each other.</li>
<li>The <b>site is duplicated seven ways</b>. That is the single biggest defect, and this
session addressed it by publishing one consolidated dashboard at the root.</li>
<li>There is <b>no licence, no dependency manifest, and no linter</b>, and one data directory
is sourced from a non-official site.</li>
<li><b>Two deploy mechanisms</b> are active and can silently diverge.</li>
</ul>
</div>
""".format(n=len(C["repo_review"]),
           rr=table([("ID", False), ("Area", False), ("File", False), ("Finding", False),
                     ("Status", False), ("Action", False), ("Evidence", False)], rows))
    return page("Repo review", "repo-review.html", body,
                "A line-by-line read of the repository, with an action for each finding.")


def p_sources() -> str:
    rows = []
    for s in C["sources"]:
        rows.append(["<b>{}</b>".format(esc(s["id"])), esc(s["publisher"]),
                     esc(s["title"]),
                     '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(
                         esc(s["url"]), esc(s["url"])),
                     esc(s["used_for"]), esc(s["read_by"]), esc(s["method"]),
                     esc(s["result"]), esc(s["limits"])])
    body = """
<div class="card"><h2>Official sources</h2>
<p>{n} references. Every table row on this site resolves to one of them. Where an earlier
session read a page that this session did not re-read, the <b>read by</b> column says so
&mdash; nothing is claimed as verified here that was not checked against the official page.</p>
{src}
</div>

<div class="card"><h2>How values were verified</h2>
<ul>
<li><b>Copied, not derived.</b> Team and player statistics are copied from the official NBA
stats tables and compared cell by cell (570 and 310 checks respectively).</li>
<li><b>Reconciled.</b> The game log is recomputed into games played, wins and losses for all
30 teams and compared with the official columns (91 checks).</li>
<li><b>Spot-checked directly.</b> One date of final scores was compared score by score with
the official games page.</li>
<li><b>Structurally checked.</b> Slate and injury rows are checked for uniqueness, known team
abbreviations, and official status vocabularies (334 checks).</li>
<li><b>Left blank when uncheckable.</b> Where no official source exists for a value, the cell
is blank and flagged. It is never filled in.</li>
</ul>
<p class="mut">Run <code>python3 final/verify.py</code> to reproduce all 1,305 checks.</p>
</div>

<div class="card"><h2>Attribution</h2>
<p>Per section 9(i) of the NBA.com Terms of Use, any use, display or publication of NBA
Statistics must include a prominent attribution to NBA.com. Every page on this site carries
that attribution in its footer and in the banner below the content.</p>
</div>
""".format(n=len(C["sources"]),
           src=table([("ID", False), ("Publisher", False), ("Title", False), ("URL", False),
                      ("Used for", False), ("Read by", False), ("Method", False),
                      ("Result", False), ("Limits", False)], rows))
    return page("Sources", "sources.html", body,
                "Every official reference used, with its retrieval method and limits.")


def p_archives() -> str:
    dirs = [("docs/", 23, "session f879620b", "Official-source data site: injuries, slate, rules."),
            ("site/", 29, "session 7c532e8c", "Generated multi-page site from data/*.json."),
            ("research/", 16, "session 9ed6085f", "Research site generated from data/*.csv."),
            ("edge/", 25, "session 0a016df8", "Verified game log, originated lines, gated picks."),
            ("origin/", 22, "session e22a2831", "Line-origination engine with walk-forward gates."),
            ("lab/", 17, "session 5697caaf", "Line lab: originated lines and validation.")]
    body = """
<div class="card"><h2>Archives: earlier session dashboards</h2>
<p>Six earlier sessions each published their own dashboard under this Pages site, plus a
seventh at the root. They are left in place, unchanged, so nothing any session published is
lost. This consolidated dashboard at the root is the one to use; the pages below are history.</p>
{dirs}
<p style="margin-top:14px">The dashboard that used to sit at the site root (session 49064d5a) is
preserved as <a href="legacy-dashboard.html">legacy-dashboard.html</a>.</p>
<p><b>Two later unified dashboards also exist on this site, built by other sessions:</b>
<a href="../index.html">the canonical root dashboard</a> (session arena/a459dadf-nba3, with its
category pages under <a href="../app/summary.html">/app/</a>) and
<a href="../dash/index.html">/dash/</a> (session arena/2b9f1ae1). This build is session
arena/925439ca-nba3's independently verified alternative. It does not edit, replace, or speak
for either of them. Choosing one canonical dashboard is an owner decision &mdash; see
<a href="suggestions.html">SG-08</a> and <a href="flagged.html">F-13</a>.</p>
</div>

<div class="card"><h2>Why they were consolidated</h2>
<p>Seven dashboards with seven ID schemes, seven navigations and four overlapping data
registries meant a reviewer could not tell which numbers were canonical. See
<a href="flagged.html">F-13</a> and suggestion SG-08.</p>
<p>The consolidated dashboard reuses the strongest work of the earlier sessions: the
line-origination engine and its statistics module from <code>origin/</code> &mdash;
<code>model/nbastats.py</code> and <code>model/build.py</code> &mdash; now run from
<code>final/build_model.py</code> against a refreshed slate.</p>
</div>

<div class="card"><h2>Coordination</h2>
<p>The shared task board is <code>COORDINATION.md</code> in the repository root. It records
each session's claim, file scope, sources, verification performed, and merge result. This
session's entry is appended at the end, and no earlier section was rewritten.</p>
<p><a href="{repo}/blob/main/COORDINATION.md" target="_blank" rel="noopener">Read the
coordination board on GitHub &#8599;</a></p>
</div>
""".format(dirs=table([("Path", False), ("Files", True), ("Built by", False),
                       ("What it contains", False), ("Open", False)],
                      [[esc(d[0]), d[1], esc(d[2]), esc(d[3]),
                        '<a href="../{}index.html" target="_blank" rel="noopener">open &#8599;</a>'
                        .format(d[0])
                        + " " + src(REPO_URL + "/tree/main/" + d[0].rstrip("/"), "in repo")]
                       for d in dirs]),
           repo=REPO_URL)
    return page("Archives", "archives.html", body,
                "The six earlier session dashboards, preserved and linked.")


PAGES = {
    "index.html": p_index,
    "executive-summary.html": p_exec,
    "methodology.html": p_methodology,
    "lines.html": p_lines,
    "projections.html": p_projections,
    "strategies.html": p_strategies,
    "validation.html": p_validation,
    "correlations.html": p_correlations,
    "injuries.html": p_injuries,
    "gameflow.html": p_gameflow,
    "data.html": p_data,
    "questions.html": p_questions,
    "suggestions.html": p_suggestions,
    "flagged.html": p_flagged,
    "repo-review.html": p_repo_review,
    "sources.html": p_sources,
    "archives.html": p_archives,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in PAGES.items():
        (OUT / name).write_text(fn(), encoding="utf-8")
    print("wrote {} pages to {}".format(len(PAGES), OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
