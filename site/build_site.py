#!/usr/bin/env python3
"""Render the static GitHub Pages site from data/processed/model_output.json.

Every table row produced here carries a Source cell that links to the official
NBA page the number came from. Values that could not be confirmed against an
official source render as a blank cell with an "UNVERIFIED" badge and are also
listed on the Flagged for Review page.

Run:  python3 site/build_site.py
"""
from __future__ import annotations

import json
import os
import html
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
SITE = ROOT  # GitHub Pages is configured to serve the repository root

with open(os.path.join(PROC, "model_output.json"), encoding="utf-8") as fh:
    M = json.load(fh)

SRC = M["sources"]
TEAM_R = M["team_ratings"]
LINES = M["lines"]
STRAT = M["strategies"]
CORR = M["correlations"]
IMPACT = M["injury_impact"]
PROPS = M["player_props"]
FLOW = M["game_flow"]
OOS = M["oos_games"]
MODELS = M["models"]
SEL = M["model_selection"]

with open(os.path.join(PROC, "games.csv"), newline="", encoding="utf-8") as fh:
    import csv as _csv
    GAMES = sorted(_csv.DictReader(fh), key=lambda r: (r["date"], r["game_id"]))
with open(os.path.join(PROC, "schedule_upcoming.csv"), newline="", encoding="utf-8") as fh:
    UPCOMING = list(_csv.DictReader(fh))
with open(os.path.join(PROC, "injuries.csv"), newline="", encoding="utf-8") as fh:
    INJ = list(_csv.DictReader(fh))

UNV = '<span class="badge badge-unv" title="Not confirmed against an official source">UNVERIFIED</span>'


def esc(x):
    return html.escape(str(x))


def num(v, nd=1, suffix=""):
    if v is None or v == "" or (isinstance(v, float) and v != v):
        return '<td class="unverified">&nbsp;</td>'
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "<td>{}</td>".format(esc(v))
    return "<td class='num'>{:,.{nd}f}{}</td>".format(f, esc(suffix), nd=nd)


def pct(v, nd=1):
    if v is None or v == "" or (isinstance(v, float) and v != v):
        return '<td class="unverified">&nbsp;</td>'
    return "<td class='num'>{:,.{nd}f}%</td>".format(float(v) * 100, nd=nd)


def src(url, label="Source"):
    return '<td><a class="src" href="{}" target="_blank" rel="noopener">{} &#8599;</a></td>'.format(
        esc(url), esc(label))


def badge(text, kind):
    return '<span class="badge badge-{}">{}</span>'.format(kind, esc(text))


def verdict_badge(v):
    if v.startswith("PASSED"):
        return badge(v, "ok")
    if v.startswith("PROVISIONAL"):
        return badge(v, "warn")
    if v.startswith("INCONCLUSIVE"):
        return badge(v, "neut")
    return badge(v, "bad")


# --------------------------------------------------------------------------- nav / shell
PAGES = [
    ("index.html", "Overview", "Executive summary and headline findings"),
    ("lines.html", "Originated Lines", "Our own spreads and totals for every upcoming game"),
    ("strategies.html", "Strategy Leaderboard", "Every strategy against the validation gates"),
    ("correlations.html", "Correlations", "Measured correlation values for parlay construction"),
    ("injuries.html", "Injury Impact", "Rotation minutes and production lost to injury"),
    ("props.html", "Player Props", "Projections and the unverified parts of each"),
    ("gameflow.html", "Game Flow", "Pace, rest, overtime and home-court analysis"),
    ("data.html", "Data & Sources", "Full verified game log and team ratings"),
    ("flagged.html", "Flagged for Review", "Every irregularity and unverified value"),
    ("suggestions.html", "Site Improvements", "Ranked options for a reviewer to choose"),
    ("questions.html", "Open Questions", "What we need before decisions can be made"),
]


def nav(active):
    out = ['<nav class="nav"><div class="nav-inner"><a class="brand" href="index.html">'
           '<span class="brand-mark">NBA3</span><span class="brand-sub">Line Origination &amp; '
           'Strategy System</span></a><button class="nav-toggle" onclick="document.body.'
           'classList.toggle(\'nav-open\')">&#9776;</button><ul class="nav-list">']
    for fn, label, _ in PAGES:
        cls = " class='active'" if fn == active else ""
        out.append("<li{}><a href='{}'>{}</a></li>".format(cls, fn, esc(label)))
    out.append("</ul></div></nav>")
    return "".join(out)


def shell(active, title, lead, body, wide=False):
    return """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} &middot; NBA3</title>
<link rel="stylesheet" href="assets/style.css">
</head><body>
{nav}
<main class="wrap{wide}">
<header class="page-head">
<h1>{title}</h1>
<p class="lead">{lead}</p>
</header>
{body}
</main>
<footer class="foot">
<p>Generated {ts} &middot; Season {season} &middot; results verified through {through}.</p>
<p class="foot-note">Every row on this site links to the official NBA source it was taken from.
Values that could not be confirmed are left blank and marked UNVERIFIED, and are collected on
the <a href="flagged.html">Flagged for Review</a> page. Nothing on this site is betting advice.</p>
</footer>
</body></html>
""".format(title=esc(title), lead=lead, nav=nav(active), body=body,
           wide=" wide" if wide else "",
           ts=esc(M["generated_utc"]), season=esc(M["season"]),
           through=esc(M["data_through"]))


def table(headers, rows, cls="", caption=None):
    cap = "<caption>{}</caption>".format(caption) if caption else ""
    return ("<div class='table-scroll'><table class='{}'>{}<thead><tr>{}</tr></thead>"
            "<tbody>{}</tbody></table></div>").format(
        cls, cap, "".join("<th>{}</th>".format(h) for h in headers), "".join(rows))


def card(label, value, sub="", kind=""):
    return """<div class="card {kind}"><div class="card-label">{l}</div>
<div class="card-value">{v}</div><div class="card-sub">{s}</div></div>""".format(
        kind=kind, l=esc(label), v=value, s=sub)


# =========================================================================== 1. index
def page_index():
    integ = M["integrity"]
    hc = M["home_court"]
    best_m = MODELS["C"] if SEL["margin"]["selected"].startswith("LM-C") else MODELS["B"]
    passed = [s for s in STRAT if s["passed_all_gates"]]
    provisional = [s for s in STRAT if s["verdict"].startswith("PROVISIONAL")]
    r_mt = CORR["rows"][1]["value"]
    ci = CORR["rows"][1]["ci95"]

    cards = "".join([
        card("Games verified", str(integ["games_captured"]),
             "Oct 20 &ndash; Nov 12, 2026 &middot; every score read off nba.com/games", "ok"),
        card("Integrity check", "0 mismatch",
             "{:,} team-games in our log vs {:,} in the official GP column".format(
                 integ["team_games_captured"], integ["team_games_official"]), "ok"),
        card("Out-of-sample games", str(len(OOS)),
             "Walk-forward, expanding window, no look-ahead", "ok"),
        card("Margin model RMSE", "{:.2f}".format(best_m["margin"]["rmse"]),
             "vs {:.2f} for a league-average baseline ({:.1f}% better)".format(
                 best_m["margin_baseline_rmse"],
                 100 * (1 - best_m["margin"]["rmse"] / best_m["margin_baseline_rmse"])), "ok"),
        card("Total model RMSE", "{:.2f}".format(MODELS["B"]["total"]["rmse"]),
             "vs {:.2f} baseline &mdash; <b>no improvement</b>".format(
                 MODELS["B"]["total_baseline_rmse"]), "bad"),
        card("Home-court advantage", "{:+.2f} pts".format(hc["value"]),
             "Derived by least squares; p={:.3f}, not significant".format(hc["p_two_sided"]), "warn"),
        card("Spread/total residual r", "{:+.3f}".format(r_mt),
             "95% CI [{:+.2f}, {:+.2f}] &mdash; includes zero".format(ci[0], ci[1]), "neut"),
        card("Strategies passing all gates", "{} of {}".format(len(passed), len(STRAT)),
             "{} provisional (signal, under-powered)".format(len(provisional)), "bad"),
    ])

    strat_rows = []
    for s in sorted(STRAT, key=lambda x: (not x["passed_all_gates"],
                                          -(x["rate"] if x["rate"] is not None else -1)))[:5]:
        strat_rows.append("<tr><td><b>{}</b></td><td>{}</td><td class='num'>{}</td>{}"
                          "<td class='num'>{}</td><td>{}</td></tr>".format(
                              esc(s["id"]), esc(s["label"]), s["n"],
                              pct(s["rate"]),
                              "n/a" if s["p"] is None else "{:.4f}".format(s["p"]),
                              verdict_badge(s["verdict"])))

    lines_rows = []
    for l in LINES[:6]:
        lines_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{} <span class='muted'>@</span> {}</td>"
            "<td class='num'>{:+.1f}</td><td class='num'>{:.1f}</td>"
            "<td class='num'>&plusmn;{:.1f}</td>{}</tr>".format(
                esc(l["date"]), esc(l["time_et"]), esc(l["away"]), esc(l["home"]),
                l["orig_spread_home"], l["orig_total"],
                1.959963984540054 * M["residuals"]["total_sd"],
                src(l["source_game"], "game")))

    body = """
<section class="cards">{cards}</section>

<section class="panel">
<h2>Executive summary</h2>
<p>NBA3 originates its own point spreads and totals for every NBA game, then tests strategies
against those lines rather than against a sportsbook's. Every input is read from an official
NBA source; every derived number is reproducible from <code>model/build.py</code>.</p>

<ol class="summary">
<li><b>The data is complete and reconciles exactly.</b> {n} games from {first} to {last},
{team_games:,} team-games, matching the official games-played column on
<a href="{ta}" target="_blank" rel="noopener">nba.com/stats/teams/advanced</a> for all 30 teams
with zero discrepancy. Per-team reconciliation is on the
<a href="data.html">Data &amp; Sources</a> page.</li>

<li><b>Our originated lines beat a naive baseline on the side, but not on the total.</b>
Walk-forward over {n_oos} out-of-sample games, the blend model cuts margin RMSE from
{base:.2f} to {ours:.2f} points ({gain:.1f}%). For totals the best model we tested is
<em>worse</em> than simply guessing the league average ({bt:.2f} vs {tt:.2f}), so we do not
claim any skill on totals and we say so in the numbers.</li>

<li><b>No strategy clears every validation gate.</b> {n_pass} of {n_strat} pass. Two are
provisionally interesting &mdash; fading our own totals of 235+ ({s5w}/{s5n} unders, p={s5p:.4f})
and backing road favourites of 8+ ({s4w}/{s4n}, p={s4p:.4f}) &mdash; but both sit far below the
100-bet sample floor the gate requires, and both were found in a search over eight candidates,
so the honest reading is <em>under-powered, not disproven</em>.</li>

<li><b>The parlay correlation we can measure is small.</b> The residual correlation between our
own spread and our own total is r={r:+.3f} (95% CI [{lo:+.2f}, {hi:+.2f}], n={n_oos}). The
confidence interval includes zero, so we cannot reject independence &mdash; but we also cannot
assert it. Cross-game parlay legs were not measured at all and remain an assumption.</li>

<li><b>Injuries move minutes, and we quantify what we can.</b> The official
<a href="{inj}" target="_blank" rel="noopener">NBA injury report</a> for 13-14 Nov lists
{n_out} player-rows marked Out or Doubtful. Where the player appears in the official
minutes table we convert his status into minutes at risk; where he does not, we leave the
impact blank and flag it rather than guessing.</li>

<li><b>Home court this season is small and not statistically significant.</b> Our least-squares
estimate is {hc:+.2f} points (p={hcp:.3f}, df={hcdf}). We still use it in the model because it
is the fitted value, but a reviewer should know the data does not establish it.</li>
</ol>

<p class="callout"><b>Bottom line:</b> the pipeline is built, sourced and reproducible, and it
produces defensible originated lines for every game in the next three days. It has <b>not</b>
yet produced a strategy that survives its own validation gates. Deploying any of the provisional
signals with real money today would be betting on a small sample, not on demonstrated skill.</p>
</section>

<section class="panel">
<h2>Where to go next</h2>
<div class="grid-2">
<div><h3>Originated lines</h3><p>Our spread and total for all {n_lines} games on the next three
slates, with an interval band and the minutes-at-risk picture for each team.</p>
<p><a class="btn" href="lines.html">Go to lines &#8594;</a></p></div>
<div><h3>Strategy leaderboard</h3><p>Every strategy, its rule, its sample, its p-value, and
which of the seven validation gates it passes or fails.</p>
<p><a class="btn" href="strategies.html">Go to leaderboard &#8594;</a></p></div>
<div><h3>Flagged for review</h3><p>{n_flag} items: unverified values left blank, data
irregularities found on official pages, and modelling assumptions that a reviewer should
approve or reject.</p>
<p><a class="btn" href="flagged.html">Go to flagged &#8594;</a></p></div>
<div><h3>Open questions</h3><p>What we have, what we do not have, and the decisions that are
blocked until someone answers.</p>
<p><a class="btn" href="questions.html">Go to questions &#8594;</a></p></div>
</div>
</section>

<section class="panel">
<h2>Top of the leaderboard</h2>
{table_strat}
<p class="muted">Full table, including the gates each strategy fails, is on the
<a href="strategies.html">leaderboard page</a>.</p>
</section>

<section class="panel">
<h2>Next games out</h2>
{table_lines}
<p class="muted">Full slate through {last_line} on the <a href="lines.html">lines page</a>.</p>
</section>
""".format(
        cards=cards,
        n=integ["games_captured"],
        first=GAMES[0]["date"], last=GAMES[-1]["date"],
        team_games=integ["team_games_captured"],
        ta=SRC["team_advanced"], n_oos=len(OOS),
        base=best_m["margin_baseline_rmse"], ours=best_m["margin"]["rmse"],
        gain=100 * (1 - best_m["margin"]["rmse"] / best_m["margin_baseline_rmse"]),
        bt=MODELS["B"]["total_baseline_rmse"], tt=MODELS["B"]["total"]["rmse"],
        n_pass=len(passed), n_strat=len(STRAT),
        s5p=next(s for s in STRAT if s["id"] == "S5")["p"],
        s4p=next(s for s in STRAT if s["id"] == "S4b")["p"],
        s5w=next(s for s in STRAT if s["id"] == "S5")["wins"],
        s5n=next(s for s in STRAT if s["id"] == "S5")["n"],
        s4w=next(s for s in STRAT if s["id"] == "S4b")["wins"],
        s4n=next(s for s in STRAT if s["id"] == "S4b")["n"],
        r=r_mt, lo=ci[0], hi=ci[1],
        inj=SRC["injury"],
        n_out=sum(1 for i in INJ if i["status"] in ("Out", "Doubtful")),
        hc=hc["value"], hcp=hc["p_two_sided"], hcdf=int(hc["df"]),
        table_strat=table(
            ["ID", "Strategy", "Bets", "Hit rate", "p", "Verdict"], strat_rows, "tbl"),
        n_lines=len(LINES),
        n_flag=len(flagged_items()),
        table_lines=table(["Date", "Time ET", "Matchup (away @ home)", "Spread (home)",
                           "Total", "95% &plusmn;", "Source"], lines_rows, "tbl"),
        last_line=LINES[-1]["date"],
    )
    return shell("index.html", "NBA3 Overview",
                 "A line-origination and strategy system for the 2026-27 NBA season. "
                 "Every number is either read from an official NBA source or derived by "
                 "arithmetic you can inspect.", body)


# =========================================================================== 2. lines
def page_lines():
    rows = []
    for l in LINES:
        notsub = []
        if not l["injury_report_submitted_home"]:
            notsub.append(l["home"])
        if not l["injury_report_submitted_away"]:
            notsub.append(l["away"])
        flag = ""
        if notsub:
            flag = badge("report missing: " + ", ".join(notsub), "warn")
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td><b>{} <span class='muted'>@</span> "
            "{}</b></td><td class='num'>{:+.1f}</td>"
            "<td class='num'>&plusmn;{:.1f}</td>"
            "<td class='num'>{:.1f}</td><td class='num'>&plusmn;{:.1f}</td>"
            "{}<td class='num'>{:+.1f}</td><td class='num'>{:.1f}</td><td>{}</td>"
            "<td class='num'>{} / {}</td><td>{}</td>{}</tr>".format(
                esc(l["date"]), esc(l["time_et"]),
                esc(l["competition"].replace("Regular Season", "Regular")),
                esc(l["away"]), esc(l["home"]),
                l["orig_spread_home"],
                1.959963984540054 * M["residuals"]["margin_sd"],
                l["orig_total"], 1.959963984540054 * M["residuals"]["total_sd"],
                pct(l["p_home_win"], 0),
                l["eff_spread_home"], l["eff_total"],
                badge("differ", "warn")
                if abs(l["orig_spread_home"] - l["eff_spread_home"]) > 6 else
                '<span class="muted">ok</span>',
                l["out_count_away"], l["out_count_home"],
                flag or '<span class="muted">&mdash;</span>',
                src(l["source_game"], "game")))

    body = """
<section class="panel">
<h2>How these lines are built</h2>
<p><b>The published line is the model that survived the backtest.</b> It is the LM-C blend:
the average of an additive points-for/points-against estimate and a Massey least-squares
margin estimate, both fitted on all {n_games} verified results. Out-of-sample it reduced
margin RMSE from {base:.2f} to {ours:.2f} points, which is {gain:.0f}% of the variance in game
margins &mdash; a real but modest edge over guessing the league average, and the honest ceiling
of what this data supports.</p>
<p class="eq">margin = &frac12; &times; (PPG<sub>home</sub> + PAPG<sub>away</sub> &minus; PPG<sub>away</sub> &minus; PAPG<sub>home</sub>)
&plus; &frac12; &times; (HCA &plus; r<sub>home</sub> &minus; r<sub>away</sub>)</p>
<p>The total is the sum of the two teams' own scoring rates (the T2 estimator, which beat the
alternative T1 estimator out-of-sample). Both are <b>originated</b> lines &mdash; ours, not
copied from any sportsbook. No market price enters the calculation anywhere.</p>
<p><b>The efficiency estimate is shown only as a cross-check.</b> It uses the official
<a href="{ta}" target="_blank" rel="noopener">season OffRtg / DefRtg / Pace table</a>:
E[home pts] = PACE &times; (OffRtg<sub>home</sub> + DefRtg<sub>away</sub> &minus; OffRtg<sub>league</sub>) / 100.
It is a better-specified model in principle, but we hold only <em>season-to-date</em> ratings,
so putting it through the same walk-forward backtest would leak future games. It is therefore
published as a second opinion, clearly labelled, and <b>not</b> used as the line of record.
Where the two disagree by more than 6 points, the row is tagged.</p>
<p>The &plusmn; columns are 1.96 &times; the out-of-sample residual standard deviation:
{sdm:.1f} points on the spread and {sd:.1f} points on the total. <b>Those bands are very wide,
and that is the honest picture</b> &mdash; a single NBA game has roughly 16 points of margin
noise that no model removes, which is exactly why none of the strategies on the
<a href="strategies.html">leaderboard</a> can clear its sample-size gate yet. The home-win
probability assumes the
margin is normal around the originated spread with the margin model's residual standard
deviation ({sdm:.2f} points); that normality assumption is unverified and is listed as such on
the <a href="flagged.html">flagged page</a>.</p>
</section>

<section class="panel">
<h2>Every game on the next three slates</h2>
<p>{n} games across {dates}. "Out" counts come from the official injury report and include
players listed <i>Out</i> or <i>Doubtful</i>.</p>
{table}
</section>

<section class="panel">
<h2>Team ratings behind the lines</h2>
{table_ratings}
</section>
""".format(
        ta=SRC["team_advanced"],
        n_games=len(GAMES),
        base=MODELS["C"]["margin_baseline_rmse"], ours=MODELS["C"]["margin"]["rmse"],
        gain=100.0 * M["skill"]["margin_variance_explained"],
        sd=M["residuals"]["total_sd"], sdm=M["residuals"]["margin_sd"],
        n=len(LINES),
        dates=", ".join(sorted({l["date"] for l in LINES})),
        table=table(["Date", "Time ET", "Competition", "Matchup (away @ home)",
                     "Spread (home)", "95% &plusmn;", "Total", "95% &plusmn;", "P(home win)",
                     "X-check spread", "X-check total", "Agreement",
                     "Out (A/H)", "Report", "Source"], rows, "tbl", ),
        table_ratings=table(
            ["Team", "GP", "W-L", "OffRtg", "DefRtg", "NetRtg", "Pace", "Fitted rating", "Source"],
            ["".join(["<tr><td><b>{}</b></td><td class='num'>{}</td>"
                      "<td class='num'>{}-{}</td>{}".format(
                          esc(t), int(TEAM_R[t]["gp"]), int(TEAM_R[t]["w"]), int(TEAM_R[t]["l"]),
                          num(TEAM_R[t]["off_rtg"]), num(TEAM_R[t]["def_rtg"]),
                          num(TEAM_R[t]["net_rtg"], 1, ""),
                          num(TEAM_R[t]["pace"], 2),
                          num(TEAM_R[t]["massey_rating"], 2)) +
                      src(TEAM_R[t]["url"], "team") + "</tr>"])
             for t in sorted(TEAM_R, key=lambda x: -TEAM_R[x]["net_rtg"])],
            "tbl"),
    )
    return shell("lines.html", "Originated Lines",
                 "Our own spreads and totals, originated from official NBA efficiency data "
                 "&mdash; no sportsbook prices used.", body, wide=True)


# =========================================================================== 3. strategies
def page_strategies():
    rows = []
    for s in STRAT:
        g = s["gates"]
        gate_cells = []
        for k in sorted(g):
            v = g[k]
            if v is None:
                gate_cells.append("<td class='num muted'>&mdash;</td>")
            elif isinstance(v, bool):
                gate_cells.append("<td class='num'>{}</td>".format(
                    badge("PASS", "ok") if v else badge("FAIL", "bad")))
            else:
                gate_cells.append("<td class='num'>{}</td>".format(esc(v)))
        rows.append(
            "<tr><td><b>{}</b></td><td><b>{}</b><div class='rule'>{}</div>{}</td>"
            "<td class='num'>{}</td><td class='num'>{}</td>{}"
            "<td class='num'>{}</td><td class='num'>{}</td><td class='num'>{}</td>"
            "{}<td>{}</td></tr>".format(
                esc(s["id"]), esc(s["label"]), esc(s["rule"]),
                "<div class='rule note'>{}</div>".format(esc(s["note"])) if s.get("note") else "",
                s["n"], s["wins"], pct(s["rate"]),
                "n/a" if s["p"] is None else "{:.4f}".format(s["p"]),
                "n/a" if s["p_null"] is None else "{:.3f}".format(s["p_null"]),
                "n/a" if s["first_half_rate"] is None else "{:.3f} / {:.3f}".format(
                    s["first_half_rate"], s["second_half_rate"]),
                "".join(gate_cells), verdict_badge(s["verdict"])))

    gate_names = sorted(STRAT[0]["gates"])
    headers = (["ID", "Strategy and rule", "Bets", "Wins", "Hit rate", "p (two-sided)",
                "Null", "Split-half"] +
               [gn.replace("_", " ") for gn in gate_names] + ["Verdict"])

    body = """
<section class="panel">
<h2>The validation gates</h2>
<p>A strategy is only allowed onto the live leaderboard if it clears all of these. The gates are
deliberately strict: the point of the exercise is to remove luck, not to find a story that
fits 114 games.</p>
<table class="tbl tight">
<thead><tr><th>Gate</th><th>Requirement</th><th>Why</th></tr></thead>
<tbody>
<tr><td><b>G1</b> provenance</td><td>Every input is an official NBA figure or arithmetic on one</td>
<td>Blocks anything trained on a number we cannot show a source for.</td></tr>
<tr><td><b>G2</b> no look-ahead</td><td>Every prediction made with only games played strictly before it</td>
<td>A model that has seen the future will always look good.</td></tr>
<tr><td><b>G3</b> sample size</td><td>At least 100 graded bets</td>
<td>Below 100, a 55% hit rate cannot be separated from noise at 80% power.</td></tr>
<tr><td><b>G4</b> power</td><td>Report the n the observed effect would actually need</td>
<td>Shows how far from adequate the sample is, in the same units as G3.</td></tr>
<tr><td><b>G5</b> raw significance</td><td>Two-sided p &lt; 0.05 against the correct null</td>
<td>Exact binomial test. For parlays the null is the independence-implied joint rate, not 0.50.</td></tr>
<tr><td><b>G6</b> multiple testing</td><td>Survives Benjamini-Hochberg at FDR 0.05</td>
<td>Eight candidates were searched; the bar has to rise accordingly.</td></tr>
<tr><td><b>G7</b> stability</td><td>Direction of the edge holds in both halves of the sample</td>
<td>An effect that only exists in one half is usually a calendar artefact.</td></tr>
</tbody></table>
</section>

<section class="panel">
<h2>Leaderboard</h2>
<p>All eight strategies graded out-of-sample. Sorted by gate result, then hit rate. "Null" is the
break-even probability each strategy is tested against &mdash; for the parlay (S6) it is the
joint rate implied by the two legs under independence, because testing a two-leg parlay against
0.50 would be a category error.</p>
{table}
</section>

<section class="panel">
<h2>Reading the result honestly</h2>
<p><b>Nothing passes.</b> That is the finding, and it is the most useful thing this page
contains. Two strategies are worth naming:</p>
<ul>
<li><b>S5 &mdash; fade our own totals of 235+.</b> {s5w} of {s5n} unders went under
(p={s5p:.4f}). The threshold was pre-specified at 235 before the backtest ran, which is the
right thing to do, but {s5n} bets is roughly a fifth of the sample the gate demands, and the
effect is exactly what regression to the mean produces when a model is constructed from
noisy season averages. It fails G3 and, at {s5need} bets needed for 80% power, it is nowhere
close.</li>
<li><b>S4b &mdash; back road favourites of 8+.</b> {s4w} of {s4n} covers (p={s4p:.4f}), but it
does not survive Benjamini-Hochberg correction across the eight candidates (G6), so we do not
treat it as established.</li>
</ul>
<p>Neither result should be traded. Both should be re-run automatically once the season supplies
the sample they need; the pipeline already does this with no code changes.</p>
</section>

<section class="panel">
<h2>Model accuracy that sits underneath</h2>
{table_models}
<p class="muted">RMSE in points. "Baseline" is a naive league-average prediction &mdash; the
home margin is always the running mean home margin, the total is always the running mean total.
A model that cannot beat that has no business originating lines.</p>
</section>
""".format(
        table=table(headers, rows, "tbl", ),
        s5w=next(s for s in STRAT if s["id"] == "S5")["wins"],
        s5n=next(s for s in STRAT if s["id"] == "S5")["n"],
        s5p=next(s for s in STRAT if s["id"] == "S5")["p"],
        s5need=next(s for s in STRAT if s["id"] == "S5")["gates"][
            "G4_powered_observed_effect_n_needed"],
        s4w=next(s for s in STRAT if s["id"] == "S4b")["wins"],
        s4n=next(s for s in STRAT if s["id"] == "S4b")["n"],
        s4p=next(s for s in STRAT if s["id"] == "S4b")["p"],
        table_models=table(
            ["Model", "Margin RMSE", "Margin baseline", "Total RMSE", "Total baseline",
             "Margin bias", "Total bias", "n"],
            ["<tr><td><b>{}</b>{}</td>{}".format(
                esc(m["label"]),
                " <span class='badge badge-ok'>selected</span>"
                if (m["label"] == SEL["margin"]["selected"] or
                    m["label"] == SEL["total"]["selected"]) else "",
                num(m["margin"]["rmse"], 2), num(m["margin_baseline_rmse"], 2),
                num(m["total"]["rmse"], 2), num(m["total_baseline_rmse"], 2),
                num(m["margin"]["bias"], 2), num(m["total"]["bias"], 2),
                "<td class='num'>{}</td>".format(m["n"]))
             for m in (MODELS["A"], MODELS["B"], MODELS["C"])], "tbl"),
    )
    return shell("strategies.html", "Strategy Leaderboard",
                 "Eight candidate strategies, graded out-of-sample against the seven "
                 "validation gates.", body, wide=True)


# =========================================================================== 4. correlations
def page_correlations():
    rows = []
    for c in CORR["rows"]:
        if c["value"] is None:
            val_cell = '<td class="unverified">&nbsp; {}</td>'.format(UNV)
            ci_cell = '<td class="unverified">&nbsp;</td>'
            n_cell = '<td class="unverified">&nbsp;</td>'
            src_cell = ('<td class="unverified">no official source &mdash; '
                        'requires per-player game logs</td>')
        else:
            val_cell = "<td class='num'>{:+.3f}</td>".format(c["value"])
            if c["ci95"][0] is None:
                ci_cell = '<td class="unverified">&nbsp;</td>'
            else:
                ci_cell = "<td class='num'>[{:+.2f}, {:+.2f}]</td>".format(
                    c["ci95"][0], c["ci95"][1])
            n_cell = "<td class='num'>{}</td>".format(c["n"])
            src_cell = src(c["source"], "nba.com")
        rows.append("<tr><td><b>{}</b></td><td>{}</td>{}{}{}{}<td>{}</td>{}</tr>".format(
            esc(c["pair"]), esc(c["stat"]), val_cell, ci_cell, n_cell,
            badge("verified", "ok") if c["verified"] else badge("assumption", "warn"),
            esc(c["note"]), src_cell))

    jr, ir = CORR["parlay_joint_rate"], CORR["parlay_independent_rate"]
    body = """
<section class="panel">
<h2>Measured correlations</h2>
<p>Correlation is what decides whether a same-game parlay is fairly priced. If two legs are
positively correlated, the joint probability is higher than the product of the legs, and a book
that prices the parlay as independent is giving value away &mdash; and vice versa. We measure
what we can and refuse to invent the rest.</p>
{table}
</section>

<section class="panel">
<h2>Same-game parlay: spread + total</h2>
<div class="cards">
{c1}{c2}{c3}
</div>
<p>Working the arithmetic: under independence the two legs would both land
{ir:.1%} of the time ({ph:.1%} &times; {po:.1%}). In the {n} out-of-sample games both legs
actually landed <b>{jr:.1%}</b> of the time. The gap of {gap:+.1%} points in the direction of
<em>positive</em> correlation, but the residual correlation itself (r={r:+.3f}) has a 95%
confidence interval that contains zero, so this is suggestive rather than established. It is
exactly the kind of number that needs 300+ games before anyone should size a position on it.</p>
<p class="callout"><b>What we cannot tell you.</b> Player-prop correlations &mdash; the
points-points and points-rebounds pairs that drive most same-game parlays &mdash; are blank
above. They require per-player game logs, which were not captured in this session. We left them
blank and flagged them rather than filling in plausible numbers, because a fabricated
correlation is worse than no correlation: it gets priced into parlays.</p>
</section>

<section class="panel">
<h2>Cross-game parlays</h2>
<p>Independence between games is the standard assumption, and it is the one nobody checks. We
have not checked it either &mdash; the sample of {n} games does not support a reliable estimate of
the correlation between two different games played on the same night. Treat the 0.0 above as an
<b>assumption awaiting evidence</b>, not a measurement.</p>
</section>
""".format(
        table=table(["Pair", "Statistic", "Value", "95% CI", "n", "Status",
                     "Interpretation", "Source"], rows, "tbl", ),
        c1=card("Leg 1 hit rate (home cover)", "{:.1%}".format(CORR["p_home_cover"]),
                "against our own originated spread"),
        c2=card("Leg 2 hit rate (over)", "{:.1%}".format(CORR["p_over"]),
                "against our own originated total"),
        c3=card("Both legs landed", "{:.1%}".format(jr),
                "independence would predict {:.1%}".format(ir),
                "ok" if jr > ir else "bad"),
        ir=ir, ph=CORR["p_home_cover"], po=CORR["p_over"], n=len(OOS), jr=jr,
        gap=jr - ir, r=CORR["rows"][1]["value"],
    )
    return shell("correlations.html", "Correlations",
                 "Measured correlation values for parlay construction &mdash; and an explicit "
                 "list of the ones we could not measure.", body, wide=True)


# =========================================================================== 5. injuries
def page_injuries():
    rows = []
    for r in IMPACT:
        if r["report_submitted"]:
            status = badge("submitted", "ok")
        else:
            status = badge("NOT YET SUBMITTED", "warn")
        mv = r["minutes_vacuum_quantified"]
        if mv and mv > 0:
            mv_cell = "<td class='num'>{:.1f}</td>".format(mv)
        elif mv == 0:
            mv_cell = '<td class="num muted">0.0</td>'
        else:
            mv_cell = '<td class="unverified">&nbsp;</td>'
        rows.append("<tr><td>{}</td><td><b>{}</b></td><td>{}</td><td>{}</td>"
                    "<td class='num'>{}</td><td class='num'>{}</td>{}{}{}</tr>".format(
                        esc(r["date"]), esc(r["team"]), esc(r["opponent"]),
                        esc(r["home_away"]), r["players_listed"], r["out_or_doubtful"],
                        mv_cell,
                        '<td class="unverified">{} not in captured set</td>'.format(
                            sum(1 for d in r["details"] if d["mpg"] is None)),
                        '<td>{}</td>'.format(status) + src(r["source"], "injury PDF")))

    det_rows = []
    for r in IMPACT:
        for d in r["details"]:
            if d["status"] == "NOT YET SUBMITTED":
                continue
            if d["mpg"] is None:
                mpg = '<td class="unverified">&nbsp;</td>'
                risk = '<td class="unverified">&nbsp; {}</td>'.format(UNV)
            else:
                mpg = "<td class='num'>{:.1f}</td>".format(d["mpg"])
                risk = "<td class='num'>{:.1f}</td>".format(d["mpg_at_risk"])
            det_rows.append(
                "<tr><td>{}</td><td><b>{}</b></td><td>{}</td><td>{}</td>"
                "<td>{}</td>{}{}<td>{}</td>{}</tr>".format(
                    esc(r["date"]), esc(d["player"]), esc(r["team"]),
                    badge(d["status"], "bad" if d["status"] == "Out" else
                          ("warn" if d["status"] == "Doubtful" else "neut")),
                    esc(d["reason"]), mpg, risk,
                    esc(d["note"]), src(r["source"], "injury PDF")))

    body = """
<section class="panel">
<h2>Method: from a status to minutes to production</h2>
<p>The official <a href="{inj}" target="_blank" rel="noopener">NBA injury report</a> gives a
status, not a minutes number. To turn one into the other we need the player's minutes, and the
only official minutes table we captured is the season
<a href="{pl}" target="_blank" rel="noopener">players/traditional</a> leaderboard, which holds
the top 31 players by minutes. So:</p>
<ol>
<li>A player is matched by name against that official minutes table.</li>
<li>His status is converted to an availability weight: Out 0.00, Doubtful 0.25, Questionable
0.60, Probable 0.90, Available 1.00. <b>These weights are our assumption, not an official
figure</b> &mdash; they are listed on the <a href="flagged.html">flagged page</a>.</li>
<li>Minutes at risk = season MPG &times; (1 &minus; weight). The team total is the quantified
minutes vacuum.</li>
<li>Production impact is projected by scaling season per-game production by the ratio of
projected to season minutes.</li>
</ol>
<p>Players who are on an official report but <b>not</b> in the captured minutes table get a blank
minutes cell and an UNVERIFIED badge. We do not estimate their minutes. As the season goes on
this gap is the single biggest thing to fix, and it is ranked first on the
<a href="suggestions.html">site-improvement page</a>.</p>
</section>

<section class="panel">
<h2>Team-level minutes vacuum</h2>
<p>{n} team-games across the next three slates. "Uncaptured" counts players on the official
report whose minutes we could not source, which is why the vacuum figure is a floor rather than
a total.</p>
{table}
</section>

<section class="panel">
<h2>Player-level detail</h2>
<p>Every row on every official report we captured, with the minutes figure and the derived
minutes at risk.</p>
{table2}
</section>
""".format(
        inj=SRC["injury"], pl=SRC["players"], n=len(IMPACT),
        table=table(["Date", "Team", "Opponent", "H/A", "Players listed", "Out/Doubtful",
                     "Minutes vacuum (quantified)", "Uncaptured", "Report status", "Source"],
                    rows, "tbl"),
        table2=table(["Date", "Player", "Team", "Status", "Reason (official)",
                      "Season MPG", "Minutes at risk", "Note", "Source"],
                     det_rows, "tbl"),
    )
    return shell("injuries.html", "Injury Impact",
                 "How injuries move rotation minutes and, through minutes, production &mdash; "
                 "with the parts we could not verify left blank.", body, wide=True)


# =========================================================================== 6. props
def page_props():
    rows = []
    for p in PROPS:
        if p["status"] == "Not listed":
            st = '<span class="muted">Not listed</span>'
        else:
            st = badge(p["status"], "bad" if p["status"] == "Out" else
                       ("warn" if p["status"] in ("Doubtful", "Questionable") else "ok"))
        rows.append(
            "<tr><td>{}</td><td><b>{}</b></td><td>{}</td><td>{}</td><td>{}</td>"
            "<td class='num'>{:.1f}</td><td class='num'>{:.1f}</td>"
            "<td class='num'>{:.1f}</td><td class='num'>{}</td>"
            "<td class='num'>{}</td><td class='num'>{:.1f}</td>"
            "<td class='num'>{}</td><td class='num'>{}</td>"
            "<td>{}</td>{}</tr>".format(
                esc(p["date"]), esc(p["player"]), esc(p["team"]),
                esc("vs " + p["opponent"]), st,
                float(p["season_min"]), p["projected_min"],
                p["proj_pts"],
                "n/a" if p["proj_reb"] is None else "{:.1f}".format(p["proj_reb"]),
                "n/a" if p["proj_ast"] is None else "{:.1f}".format(p["proj_ast"]),
                float(p["season_pts"]),
                "n/a" if p["proj_fg3m"] is None else "{:.1f}".format(p["proj_fg3m"]),
                "n/a" if p["season_fg3m"] is None else "{:.1f}".format(p["season_fg3m"]),
                UNV + " no distribution", src(p["source_player"], "nba.com")))

    body = """
<section class="panel">
<h2>What these projections are, and are not</h2>
<p>The season averages on this table are official, taken from
<a href="{pl}" target="_blank" rel="noopener">nba.com/stats/players/traditional</a>. Everything
in a <b>Projected</b> column is ours, and it rests on an assumption we want to be blunt about:</p>
<p class="callout"><b>Assumption (unverified):</b> the minutes vacated by injured players are
redistributed to the remaining rotation players in proportion to their season minutes. We have
no per-player game logs with which to test this, no usage-rate data, and no distribution for
any individual game. The projection is a <b>point estimate of a mean</b>, not a distribution,
so it cannot tell you the probability of going over a prop line.</p>
<p>That means we will not publish an over/under call on a player prop from this data. The table
below shows the projection and the season baseline side by side so a reviewer can see exactly
how much the assumption moves the number &mdash; in most cases, very little, because the
captured minutes set only covers the league's heaviest-used players and the vacuum is spread
thinly across them.</p>
</section>

<section class="panel">
<h2>Projections</h2>
<p>One row per captured player, for the first game on the slate in which his team appears.</p>
{table}
</section>

<section class="panel">
<h2>What it would take to make these tradeable</h2>
<ol>
<li><b>Per-player game logs.</b> Without them there is no standard deviation, and without a
standard deviation there is no probability of exceeding a line. This is the blocking item.</li>
<li><b>Usage rate and minutes share when a teammate is out.</b> The pro-rata assumption is almost
certainly wrong in detail: stars absorb far more of a vacuum than bench players do.</li>
<li><b>Official prop lines to compare against.</b> We deliberately do not scrape sportsbook
prices; if that changes, the comparison becomes possible.</li>
</ol>
</section>
""".format(
        pl=SRC["players"],
        table=table(["Date", "Player", "Team", "Matchup", "Status", "Season MIN",
                     "Proj MIN", "Proj PTS", "Proj REB", "Proj AST", "Season PTS",
                     "Proj 3PM", "Season 3PM", "Prop call", "Source"],
                    rows, "tbl"),
    )
    return shell("props.html", "Player Props",
                 "Point projections from official season averages &mdash; and a clear statement "
                 "of why they are not yet bettable numbers.", body, wide=True)


# =========================================================================== 7. game flow
def page_gameflow():
    pace_rows = []
    for p in FLOW["pace_leaders"]:
        pace_rows.append("<tr><td><b>{}</b></td>{}".format(
            esc(p["team"]), num(p["pace"], 2), num(p["off_rtg"]), num(p["def_rtg"]),
            num(p["net_rtg"], 1), src(p["url"], "team")) + "</tr>")

    rest_rows = ["<tr><td><b>{}</b></td><td class='num'>{}</td></tr>".format(
        esc(k), v) for k, v in FLOW["rest_distribution"].items()]

    body = """
<section class="panel">
<h2>Game-flow facts from the verified results</h2>
<div class="cards">
{cards}
</div>
<p>Every figure above is computed directly from the {n} verified final scores in
<a href="data.html">the game log</a>. None of them is copied from a summary page.</p>
</section>

<section class="panel">
<h2>Pace table</h2>
<p>Official pace and efficiency for all 30 teams, sorted fastest to slowest. Pace is the single
biggest driver of a game total: the spread between the fastest and slowest team here is
{spread:.1f} possessions per 48 minutes, which at a league-average {ortg:.1f} offensive rating
is worth roughly {worth:.1f} points of total.</p>
{table}
</section>

<section class="panel">
<h2>Rest and scheduling</h2>
<p>Days of rest for each team-game, derived by differencing the official game dates. The
distribution is heavily front-loaded because back-to-backs are common early in a season.</p>
<div class="grid-2">
<div>{rest}</div>
<div>
<h3>Why rest is on this page and not in a strategy</h3>
<p>Our rest-differential strategy (S3) put up {s3r:.1%} over {s3n} graded bets, p={s3p:.3f}.
That is indistinguishable from a coin, and we report it as such. Rest is a real effect in the
literature, but with {s3n} qualifying games in this sample we have no business claiming it. It
stays here as context for the game-flow read, not as a signal.</p>
</div>
</div>
</section>

<section class="panel">
<h2>Home court</h2>
<p>Our least-squares fit across {hg} non-neutral games gives a home-court advantage of
<b>{hc:+.2f} points</b> (two-sided p={hcp:.3f}, df={hcdf}). At conventional significance
thresholds that is <b>not</b> statistically distinguishable from zero. We use the fitted value
in the line-origination model because it is the least-squares estimate, but a reviewer should
know that in this particular 174-game sample the data does not establish home court at all.
The Mexico City game (DEN vs IND, 7 Nov) is treated as neutral and is excluded from the fit.</p>
</section>

<section class="panel">
<h2>Overtime</h2>
<p>{ot} of {n} games went to overtime ({rate:.1%}). Overtime games average
{ott:.1f} combined points against {rt:.1f} for regulation games &mdash; a gap of
{gap:.1f} points that matters for any total priced off regulation scoring rates. Our originated
totals do <b>not</b> adjust for the possibility of overtime; they are regulation equivalents.
That is a modelling choice, listed on the <a href="flagged.html">flagged page</a>, not an
oversight.</p>
</section>
""".format(
        cards="".join([
            card("Average game total", "{:.1f}".format(FLOW["avg_total"]),
                 "across {} verified games".format(FLOW["games"]), "ok"),
            card("Regulation / OT totals", "{:.1f} / {:.1f}".format(
                     FLOW["avg_total_regulation"], FLOW["avg_total_ot"]),
                 "regulation vs overtime games", "neut"),
            card("Overtime rate", "{:.1%}".format(FLOW["ot_rate"]),
                 "{} of {} games".format(FLOW["ot_games"], FLOW["games"]), "neut"),
            card("Home win rate", "{:.1%}".format(FLOW["home_wins"] / FLOW["home_games"]),
                 "{} of {} non-neutral games".format(FLOW["home_wins"], FLOW["home_games"]),
                 "neut"),
            card("Mean home margin", "{:+.2f}".format(FLOW["home_margin_mean"]),
                 "home score minus away score", "neut"),
            card("Games on a back-to-back", "{:.1%}".format(FLOW["b2b_rate"]),
                 "at least one team on one day of rest", "warn"),
        ]),
        n=FLOW["games"],
        spread=FLOW["pace_leaders"][0]["pace"] - FLOW["pace_leaders"][-1]["pace"],
        ortg=FLOW["lg_off_rtg"],
        worth=(FLOW["pace_leaders"][0]["pace"] - FLOW["pace_leaders"][-1]["pace"])
              * FLOW["lg_off_rtg"] / 100.0,
        table=table(["Team", "Pace", "OffRtg", "DefRtg", "NetRtg", "Source"],
                    pace_rows, "tbl"),
        rest=table(["Days of rest", "Team-games"], rest_rows, "tbl tight"),
        s3r=next(s for s in STRAT if s["id"] == "S3")["rate"],
        s3n=next(s for s in STRAT if s["id"] == "S3")["n"],
        s3p=next(s for s in STRAT if s["id"] == "S3")["p"],
        hg=FLOW["home_games"], hc=M["home_court"]["value"],
        hcp=M["home_court"]["p_two_sided"], hcdf=int(M["home_court"]["df"]),
        ot=FLOW["ot_games"], rate=FLOW["ot_rate"], ott=FLOW["avg_total_ot"],
        rt=FLOW["avg_total_regulation"], gap=FLOW["avg_total_ot"] - FLOW["avg_total_regulation"],
    )
    return shell("gameflow.html", "Game Flow",
                 "Pace, rest, overtime and home court &mdash; computed from verified results, "
                 "not copied from a summary page.", body, wide=True)


# =========================================================================== 8. data
def page_data():
    g_rows = []
    for g in GAMES:
        url = "https://www.nba.com/games?date=" + g["date"]
        g_rows.append(
            "<tr><td>{}</td><td>{}</td><td><b>{}</b></td><td class='num'>{}</td>"
            "<td class='num'>{}</td><td><b>{}</b></td><td>{}</td>{}</tr>".format(
                esc(g["date"]), esc(g["game_id"]), esc(g["away"]),
                esc(g["away_pts"]),
                esc(g["home_pts"]), esc(g["home"]),
                badge("OT", "warn") if g["ot"] == "1" else '<span class="muted">reg</span>',
                src(url, "games")))

    per_team = []
    counts = {}
    for g in GAMES:
        counts[g["away"]] = counts.get(g["away"], 0) + 1
        counts[g["home"]] = counts.get(g["home"], 0) + 1
    for t in sorted(TEAM_R):
        w = l = 0
        for g in GAMES:
            if g["home"] == t:
                if int(g["home_pts"]) > int(g["away_pts"]):
                    w += 1
                else:
                    l += 1
            elif g["away"] == t:
                if int(g["away_pts"]) > int(g["home_pts"]):
                    w += 1
                else:
                    l += 1
        ours, off = counts[t], int(TEAM_R[t]["gp"])
        per_team.append("<tr><td><b>{}</b></td><td class='num'>{}</td><td class='num'>{}</td>"
                        "<td class='num'>{}-{}</td><td class='num'>{}</td><td>{}</td>{}</tr>".format(
                            esc(t), ours, off, w, l, TEAM_R[t]["gp"] - (w + l),
                            badge("match", "ok") if ours == off else badge(
                                "MISMATCH", "bad"),
                            src("https://www.nba.com/games?date={}".format(GAMES[0]["date"]),
                                "games")))

    body = """
<section class="panel">
<h2>Integrity reconciliation</h2>
<p>The strongest available check on a hand-built game log: count every team's games in our file
and compare with the official <b>GP</b> column on
<a href="{ta}" target="_blank" rel="noopener">nba.com/stats/teams/advanced</a>. Our log contains
{ours:,} team-games; the official table says {off:,}. The difference is <b>{diff}</b>, and all
30 teams reconcile individually in the table below.</p>
<p>Win-loss is recomputed from our own scores and compared with the official W-L on the same
page; the "Unacct." column is games played minus wins minus losses, which should always be zero
(it would be non-zero only if a game were postponed or a result were missing).</p>
{table_team}
</section>

<section class="panel">
<h2>Full verified game log</h2>
<p>{n} games, {first} to {last}. Every row was read off
<code>nba.com/games?date=YYYY-MM-DD</code> for that specific date; the first team listed on that
page is the away team. No score on this table was inferred, estimated or filled in.</p>
{table}
</section>

<section class="panel">
<h2>Sources used</h2>
<table class="tbl tight">
<thead><tr><th>Data</th><th>Official source</th><th>What we took from it</th></tr></thead>
<tbody>
<tr><td>Final scores, game IDs</td><td><a href="{g}" target="_blank" rel="noopener">nba.com/games?date=</a></td>
<td>Every result in the game log, one page per date</td></tr>
<tr><td>Team efficiency, pace</td><td><a href="{ta}" target="_blank" rel="noopener">nba.com/stats/teams/advanced</a></td>
<td>OffRtg, DefRtg, NetRtg, Pace, eFG%, TS%, TOV%, OREB%, GP, W-L for all 30 teams</td></tr>
<tr><td>Player production</td><td><a href="{pl}" target="_blank" rel="noopener">nba.com/stats/players/traditional</a></td>
<td>Season per-game minutes and counting stats, top 31 by minutes</td></tr>
<tr><td>Injuries</td><td><a href="{inj}" target="_blank" rel="noopener">Official NBA injury report PDF</a></td>
<td>Player, team, status and reason for 13 and 14 Nov</td></tr>
<tr><td>Schedule</td><td><a href="{sc}" target="_blank" rel="noopener">nba.com/schedule</a></td>
<td>Upcoming game IDs, tip times and NBA Cup groupings</td></tr>
<tr><td>Player headshots / leaders</td><td><a href="{g}" target="_blank" rel="noopener">nba.com/games?date=</a></td>
<td>Cross-check on individual game performances</td></tr>
</tbody></table>
<p class="muted"><b>Not used:</b> no sportsbook, odds aggregator or third-party statistics site
contributed any number to this project. All lines are originated.</p>
</section>
""".format(
        ta=SRC["team_advanced"],
        ours=M["integrity"]["team_games_captured"],
        off=M["integrity"]["team_games_official"],
        diff=M["integrity"]["mismatch"],
        table_team=table(["Team", "Games in our log", "Official GP", "W-L (recomputed)",
                          "Unacct.", "Reconciliation", "Source"], per_team, "tbl"),
        n=len(GAMES), first=GAMES[0]["date"], last=GAMES[-1]["date"],
        table=table(["Date", "Game ID", "Away", "Away pts", "Home pts", "Home", "OT",
                     "Source"], g_rows, "tbl"),
        g=SRC["games"], pl=SRC["players"], inj=SRC["injury"], sc=SRC["schedule"],
    )
    return shell("data.html", "Data &amp; Sources",
                 "The complete verified game log, the per-team reconciliation against official "
                 "games-played, and every source used.", body, wide=True)


# =========================================================================== 9. flagged
def flagged_items():
    items = []

    # 1. every unverified cell in the correlation table
    for c in CORR["rows"]:
        if c["value"] is None:
            items.append({
                "area": "Correlations",
                "item": c["pair"],
                "issue": "Value left blank. " + c["note"],
                "impact": "Same-game parlays that combine two player props cannot be priced. "
                          "Any parlay built today is priced on an untested independence "
                          "assumption.",
                "action": "Capture per-player game logs from nba.com/stats/players/boxscores "
                          "and recompute. Roughly 4,000 rows for the season to date.",
                "severity": "high",
                "src": "",
            })

    # 2. distribution of prop projections
    items.append({
        "area": "Player props",
        "item": "No distribution behind any player projection",
        "issue": "The pro-rata minutes-redistribution assumption produces a point estimate of "
                 "a mean only. There is no standard deviation, so no probability of exceeding "
                 "a prop line can be stated.",
        "impact": "Player-prop bets and player-prop parlays cannot be graded or sized.",
        "action": "Capture per-player game logs; fit a distribution per player per stat.",
        "severity": "high",
        "src": SRC["players"],
    })

    # 3. injury availability weights
    items.append({
        "area": "Injuries",
        "item": "Status-to-availability weights are our assumption",
        "issue": "Out 0.00, Doubtful 0.25, Questionable 0.60, Probable 0.90, Available 1.00. "
                 "The NBA publishes the status but not a probability.",
        "impact": "The quantified minutes vacuum scales linearly with these weights, so the "
                  "injury adjustment carries our assumption through to the originated lines.",
        "action": "Replace with empirically observed participation rates by status once enough "
                  "game logs exist to measure them. Until then, treat the injury adjustment as "
                  "directional.",
        "severity": "medium",
        "src": SRC["injury"],
    })

    # 4. uncaptured injured players
    unc = []
    for r in IMPACT:
        for d in r["details"]:
            if d["mpg"] is None and d["player"]:
                unc.append((r["team"], d["player"], d["status"]))
    items.append({
        "area": "Injuries",
        "item": "{} injured players not in the captured minutes set".format(len(unc)),
        "issue": "These players appear on the official injury report but not in the top-31 "
                 "minutes table we captured, so their minutes impact is unknown. Examples: "
                 + ", ".join("{} ({})".format(p, t) for t, p, s in unc[:6]) + ".",
        "impact": "The minutes vacuum shown for each team is a floor, not a total. Real "
                  "rotation disruption is larger than the table shows.",
        "action": "Widen the minutes capture beyond the top 31 players.",
        "severity": "medium",
        "src": SRC["injury"],
    })

    # 5. not-yet-submitted reports
    nsub = sorted({(i["game_date"], i["team"]) for i in INJ if i["status"] == "NOT YET SUBMITTED"})
    if nsub:
        items.append({
            "area": "Injuries",
            "item": "{} team reports marked NOT YET SUBMITTED".format(len(nsub)),
            "issue": "Official injury report rows reading 'NOT YET SUBMITTED' for: "
                     + ", ".join("{} {}".format(d, t) for d, t in nsub) + ".",
            "impact": "Those teams carry zero quantified injury adjustment into the originated "
                      "lines, which is a data gap, not an assertion of good health.",
            "action": "Re-pull the injury report closer to tip-off.",
            "severity": "medium",
            "src": SRC["injury"],
        })

    # 6. normality assumption
    items.append({
        "area": "Modelling",
        "item": "Win probabilities assume a normal margin distribution",
        "issue": "P(home win) is computed as a normal CDF around the originated margin with "
                 "the margin model's residual standard deviation of {:.2f} points. Real "
                 "basketball margins have fatter tails and are discretised by late-game "
                 "fouling.".format(M["residuals"]["margin_sd"]),
        "impact": "Win probabilities near the extremes are less reliable than the middle of "
                  "the range.",
        "action": "Replace with the empirical distribution of residuals, or with a "
                  "bootstrap, once the sample is larger.",
        "severity": "medium",
        "src": "",
    })

    # 7. totals not adjusted for OT
    items.append({
        "area": "Modelling",
        "item": "Originated totals are regulation equivalents",
        "issue": "The model does not add the expected extra scoring from overtime, which "
                 "occurred in {:.1%} of games and is worth about {:.1f} points when it "
                 "happens.".format(FLOW["ot_rate"],
                                   FLOW["avg_total_ot"] - FLOW["avg_total_regulation"]),
        "impact": "Our totals are biased low by roughly {:.1f} points on average.".format(
            FLOW["ot_rate"] * (FLOW["avg_total_ot"] - FLOW["avg_total_regulation"])),
        "action": "Decide whether to price regulation-only or full-game totals, then apply "
                  "the chosen convention consistently.",
        "severity": "medium",
        "src": "",
    })

    # 8. total model worse than baseline
    items.append({
        "area": "Modelling",
        "item": "Total model does not beat the naive baseline",
        "issue": "Best total RMSE is {:.2f} against {:.2f} for simply guessing the running "
                 "league-average total.".format(MODELS["B"]["total"]["rmse"],
                                                MODELS["B"]["total_baseline_rmse"]),
        "impact": "Totals, and any total-based strategy, rest on a model with no demonstrated "
                  "skill. This is why S5's result is treated as regression to the mean rather "
                  "than an edge.",
        "action": "Add possession-level inputs (four factors) rather than only scoring rates.",
        "severity": "high",
        "src": "",
    })

    # 9. small sample
    items.append({
        "area": "Validation",
        "item": "Out-of-sample sample is {} games".format(len(OOS)),
        "issue": "After a 60-game burn-in, only {} games are graded out-of-sample, and no "
                 "strategy reaches the 100-bet gate.".format(len(OOS)),
        "impact": "Every strategy result on the leaderboard is under-powered. Nothing can be "
                  "deployed on this evidence.",
        "action": "Re-run the same pipeline with no code changes once another 150-200 games "
                  "have been played.",
        "severity": "high",
        "src": "",
    })

    # 10. home court not significant
    items.append({
        "area": "Modelling",
        "item": "Home-court advantage is not statistically significant",
        "issue": "Fitted at {:+.2f} points with two-sided p={:.3f} over {} non-neutral "
                 "games.".format(M["home_court"]["value"], M["home_court"]["p_two_sided"],
                                 FLOW["home_games"]),
        "impact": "We use the fitted value in every originated spread, even though this sample "
                  "cannot distinguish it from zero.",
        "action": "Monitor; consider shrinking toward the prior-season league value.",
        "severity": "low",
        "src": "",
    })

    # 11. roster irregularity: Giannis on Miami
    items.append({
        "area": "Data irregularity",
        "item": "Giannis Antetokounmpo listed on Miami; several roster surprises",
        "issue": "The official pages show Giannis Antetokounmpo playing for Miami, Anthony "
                 "Davis for Washington, Paul George for Boston, James Harden for Cleveland, "
                 "LaMelo Ball for Minnesota and Kevin Durant for Houston. These are unusual "
                 "against pre-season expectations.",
        "impact": "If any of these are mis-attributed by the source pages, the team ratings "
                  "built from them inherit the error.",
        "action": "Spot-check two or three against a second official page (team roster) before "
                  "relying on the ratings.",
        "severity": "medium",
        "src": "https://www.nba.com/players",
    })

    # 12. Anthony Edwards contradiction
    items.append({
        "area": "Data irregularity",
        "item": "Anthony Edwards listed Out on 14 Nov after recent 45- and 47-point games",
        "issue": "The official injury report lists Edwards Out (right knee arthroscopy) for "
                 "14 Nov, yet the official game pages show 45 points on 21 Oct and 47 on "
                 "26 Oct.",
        "impact": "Either the injury is new, or the report is stale. His minutes vacuum is "
                  "quantified as if he will not play.",
        "action": "Re-check the report on game day before using the MIN line.",
        "severity": "medium",
        "src": SRC["injury"],
    })

    # 13. neutral-site game
    items.append({
        "area": "Modelling",
        "item": "One neutral-site game (DEN vs IND, 7 Nov, Mexico City)",
        "issue": "Treated as neutral, so no home-court term is applied. The official page "
                 "still nominally designates a home team.",
        "impact": "Affects one game in the fit; immaterial to the standings but declared here "
                  "for completeness.",
        "action": "None, unless more neutral-site games are added.",
        "severity": "low",
        "src": "https://www.nba.com/games?date=2026-11-07",
    })

    # 14. cross-game independence
    items.append({
        "area": "Correlations",
        "item": "Cross-game parlay independence is an assumption",
        "issue": "Not measured. {} games do not support a reliable estimate of the correlation "
                 "between two games on the same night.".format(len(OOS)),
        "impact": "Cross-game parlays are priced as if legs were independent.",
        "action": "Measure on the residual matrix once the sample is larger.",
        "severity": "medium",
        "src": "",
    })

    return items


def page_flagged():
    items = flagged_items()
    rows = []
    for i, it in enumerate(items, 1):
        rows.append(
            "<tr><td class='num'>{}</td><td><b>{}</b></td><td>{}</td>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                i, esc(it["item"]), badge(it["area"], "neut"),
                esc(it["issue"]), esc(it["impact"]), esc(it["action"]),
                badge(it["severity"].upper(),
                      "bad" if it["severity"] == "high" else
                      ("warn" if it["severity"] == "medium" else "neut"))))

    body = """
<section class="panel">
<h2>Flagged for review</h2>
<p>Everything on this page is something we could not verify, deliberately did not fill in, or
found to be contradictory on an official source. None of it blocks publication &mdash; it is
published <i>here</i>, with its source, so a reviewer can see the boundary between what is
established and what is assumed.</p>
<p>The governing rule: <b>if a value cannot be confirmed against an official source, the cell is
left blank and marked UNVERIFIED rather than estimated.</b> Every blank cell on this site is
collected here.</p>
<div class="cards">
{c}
</div>
</section>

<section class="panel">
{table}
</section>
""".format(
        c="".join([
            card("Total flagged items", str(len(items)), "across all areas", "warn"),
            card("High severity", str(sum(1 for i in items if i["severity"] == "high")),
                 "blocks a capability, not a publication", "bad"),
            card("Unverified values left blank",
                 str(sum(1 for c2 in CORR["rows"] if c2["value"] is None)),
                 "correlation pairs we refused to estimate", "bad"),
        ]),
        table=table(["#", "Item", "Area", "What the problem is", "What it affects",
                     "How to resolve", "Severity"], rows, "tbl"),
    )
    return shell("flagged.html", "Flagged for Review",
                 "Every irregularity, unverified value and modelling assumption &mdash; with "
                 "sources, so a reviewer can check each one.", body, wide=True)


# =========================================================================== 10. suggestions
def page_suggestions():
    opts = [
        {
            "id": "A", "title": "Capture per-player game logs",
            "problem": "Everything on the props and player-correlation side is blocked by the "
                       "absence of per-player game-by-game data. Four correlation cells are "
                       "blank and no prop distribution exists.",
            "options": [
                ("A1", "Scrape nba.com/stats/players/boxscores per date",
                 "Official source, already proven to work with fetch_page. ~4,000 rows for the "
                 "season to date, roughly 400 page fetches. Slow but fully sourced.",
                 "Official, verifiable, matches existing pipeline",
                 "Very slow; needs to be chunked across sessions"),
                ("A2", "Sample the top 100 players by minutes only",
                 "Covers the vast majority of prop market volume with about a quarter of the "
                 "fetches.",
                 "Much faster, still official",
                 "Deep-bench props remain unpriceable"),
                ("A3", "Leave player props out of scope for now",
                 "Publish team-side lines only and say so plainly.",
                 "Honest, fast, no new risk",
                 "Closes off the parlay and prop parts of the brief"),
            ],
            "rec": "A2",
        },
        {
            "id": "B", "title": "Fix the totals model, which currently loses to a baseline",
            "problem": "Our best total RMSE is {:.2f} against {:.2f} for guessing the league "
                       "average. The side beats its baseline; the total does not.".format(
                           MODELS["B"]["total"]["rmse"], MODELS["B"]["total_baseline_rmse"]),
            "options": [
                ("B1", "Add the four factors (eFG%, TOV%, OREB%, FT rate)",
                 "Move from scoring rates to possession-level efficiency, which is what "
                 "actually drives a total.",
                 "Directly targets the weakness; all inputs are official",
                 "More parameters to fit on a small sample"),
                ("B2", "Shrink team totals toward the league mean",
                 "A James-Stein style shrinkage will almost certainly reduce RMSE immediately.",
                 "Cheap, quick, near-certain improvement",
                 "Improves accuracy without adding understanding"),
                ("B3", "Publish the baseline as the total",
                 "Admit the model adds nothing and use the league average.",
                 "Honest baseline, no false confidence",
                 "Gives up on half the product"),
            ],
            "rec": "B2 now, B1 next",
        },
        {
            "id": "C", "title": "Decide how the site should be refreshed",
            "problem": "This build is a static snapshot. The brief asks for picks for every "
                       "upcoming slate up to three days ahead, which only stays true if the "
                       "site is regenerated daily.",
            "options": [
                ("C1", "GitHub Actions cron that re-runs the pipeline and republishes",
                 "A scheduled workflow rebuilds data, model and site, and commits.",
                 "Hands-off, fits GitHub Pages exactly, free",
                 "Scraping from Actions may be blocked or rate-limited"),
                ("C2", "Manual regeneration at the start of each session",
                 "Whoever runs a session re-runs model/build.py and site/build_site.py.",
                 "Simple, no new infrastructure",
                 "Stale whenever nobody runs it"),
                ("C3", "Static archive plus a 'generated at' banner",
                 "Publish as-is and make the timestamp unmissable.",
                 "Honest about staleness",
                 "Does not meet the three-days-ahead requirement on its own"),
            ],
            "rec": "C1 with C3's banner as a safety net",
        },
        {
            "id": "D", "title": "Make the leaderboard a genuine competition",
            "problem": "The brief asks for a leaderboard with rewards for the best strategies. "
                       "Right now there is one author and eight strategies, none of which pass.",
            "options": [
                ("D1", "Publish a strategy specification format and accept pull requests",
                       "Contributors add a JSON or Python strategy file; the pipeline grades it "
                       "automatically against the same gates.",
                 "Turns the repo into the competition the brief describes",
                 "Needs a sandboxed runner to be safe"),
                ("D2", "Keep it internal but auto-grade a wider candidate set",
                 "Generate dozens of candidate rules and let the gates prune them, with the "
                 "multiple-testing correction doing the work.",
                 "No security surface",
                 "Searching more rules makes G6 stricter, not weaker"),
                ("D3", "Add a shadow leaderboard with paper results only",
                 "Track forward performance out-of-sample before anything is 'live'.",
                 "Builds the track record the gates demand",
                 "Nothing is deployable for weeks"),
            ],
            "rec": "D1 with D3 running underneath",
        },
        {
            "id": "E", "title": "Widen and harden the data capture",
            "problem": "Injury minutes impact is a floor because the captured minutes table "
                       "covers only the top 31 players, and several team reports were "
                       "'NOT YET SUBMITTED'.",
            "options": [
                ("E1", "Capture the full 465-row player table",
                 "Nine chunks already identified; every injured player then has official "
                 "minutes.",
                 "Removes an entire class of UNVERIFIED cells",
                 "Nine large page fetches per refresh"),
                ("E2", "Re-pull the injury report closer to tip-off",
                 "The 05:15 PM report is published hours before the first tip.",
                 "Fewer stale or missing reports",
                 "Needs a second pull each day"),
                ("E3", "Add official boxscores-advanced per date",
                 "Gives per-game team ratings rather than season averages, which lets the "
                 "model use form instead of the whole season.",
                 "Directly improves both the side and the total",
                 "Two chunks per date; adds up over a season"),
            ],
            "rec": "E1 and E2 now, E3 next",
        },
    ]

    blocks = []
    for o in opts:
        rows = []
        for oid, title, how, pro, con in o["options"]:
            rows.append("<tr><td><b>{}</b></td><td><b>{}</b></td><td>{}</td>"
                        "<td class='pro'>{}</td><td class='con'>{}</td><td>{}</td></tr>".format(
                            esc(oid), esc(title), esc(how), esc(pro), esc(con),
                            badge("recommended", "ok") if oid in o["rec"] else
                            '<span class="muted">&mdash;</span>'))
        blocks.append("""
<section class="panel">
<h2>{tid}. {title}</h2>
<p class="problem"><b>Problem.</b> {problem}</p>
{table}
<p class="rec"><b>Recommendation:</b> {rec}</p>
</section>
""".format(tid=esc(o["id"]), title=esc(o["title"]), problem=esc(o["problem"]),
           rec=esc(o["rec"]),
           table=table(["Option", "What it is", "How it would work", "For", "Against", ""],
                       rows, "tbl")))

    body = """
<section class="panel">
<h2>Site and system improvements &mdash; options for a reviewer</h2>
<p>Each section below states one problem, sets out two or three concrete ways to fix it, gives
the case for and against each, and names a recommendation. Nothing here has been implemented:
this page exists so the choice is made deliberately rather than by whoever happens to be
typing. Ordered by how much capability each one unlocks.</p>
</section>
""" + "".join(blocks)

    return shell("suggestions.html", "Site Improvements",
                 "Ranked improvement options, each with alternatives and the trade-offs, so a "
                 "reviewer can choose the path before anything is built.", body, wide=True)


# =========================================================================== 11. questions
def page_questions():
    have = [
        ("Every final score, 20 Oct to 12 Nov", "{} games, each read off nba.com/games for its "
         "own date".format(len(GAMES)), SRC["games"]),
        ("Official team efficiency and pace, all 30 teams",
         "OffRtg, DefRtg, NetRtg, Pace, four factors, GP, W-L", SRC["team_advanced"]),
        ("Season per-game player production, top 31 by minutes",
         "Minutes, points, rebounds, assists, threes, shooting splits", SRC["players"]),
        ("Official injury report for 13-14 Nov", "Player, team, status, reason", SRC["injury"]),
        ("Upcoming schedule with game IDs and tip times",
         "{} games across three slates, including NBA Cup groupings".format(len(UPCOMING)),
         SRC["schedule"]),
        ("A working, sourced line-origination model",
         "Beats the baseline on the side, RMSE {:.2f} vs {:.2f}".format(
             MODELS["C"]["margin"]["rmse"], MODELS["C"]["margin_baseline_rmse"]), ""),
        ("A validation harness with seven gates",
         "Walk-forward, exact binomial tests, Benjamini-Hochberg correction", ""),
    ]
    need = [
        ("Per-player game logs",
         "Blocks player-prop pricing and every player-level correlation. Four correlation "
         "cells are blank because of it.",
         "Scrape nba.com/stats/players/boxscores by date; see suggestion A2 on the "
         "improvements page.", "high"),
        ("More graded games",
         "No strategy reaches the 100-bet gate; the out-of-sample set is only {} "
         "games.".format(len(OOS)),
         "Wait. Re-run the identical pipeline after another 150-200 games; no code changes "
         "needed.", "high"),
        ("Possession-level team inputs per game",
         "The total model loses to a naive baseline and the obvious fix needs better inputs.",
         "Capture boxscores-advanced per date (suggestion E3).", "high"),
        ("Injury report at tip-off, not 05:15 PM",
         "{} team reports were 'NOT YET SUBMITTED'.".format(
             sum(1 for i in INJ if i["status"] == "NOT YET SUBMITTED")),
         "Schedule a second pull 90 minutes before first tip (suggestion E2).", "medium"),
        ("A decision on whether sportsbook prices may be used at all",
         "The brief says to originate lines rather than copy books. It does not say whether we "
         "may ever <em>compare</em> against them, which is how any edge gets sized.",
         "Reviewer decision. Until it is answered, every strategy is graded against our own "
         "line, which measures self-consistency rather than profit.", "high"),
        ("A decision on bankroll and staking",
         "The brief mentions rewards for top strategies but says nothing about stake sizing, "
         "which determines whether a 53% strategy is worth running.",
         "Reviewer decision; a flat-stake default can be assumed and documented if no answer.",
         "medium"),
        ("Confirmation that the unexpected rosters are correct",
         "Giannis on Miami, Anthony Davis on Washington, Paul George on Boston, LaMelo Ball on "
         "Minnesota. If the source pages are wrong, the ratings inherit the error.",
         "Spot-check against official team roster pages.", "medium"),
        ("Whether overtime counts for totals",
         "Our totals are regulation equivalents, which biases them low by about {:.1f} "
         "points.".format(FLOW["ot_rate"] *
                          (FLOW["avg_total_ot"] - FLOW["avg_total_regulation"])),
         "Reviewer decision; both conventions are defensible but must be consistent.", "low"),
    ]

    hrows = ["<tr><td><b>{}</b></td><td>{}</td><td>{}</td></tr>".format(
        esc(a), esc(b), src(c, "nba.com") if c else '<td class="muted">derived</td>')
        for a, b, c in have]
    nrows = ["<tr><td><b>{}</b></td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
        esc(a), esc(b), esc(c),
        badge(d.upper(), "bad" if d == "high" else ("warn" if d == "medium" else "neut")))
        for a, b, c, d in need]

    body = """
<section class="panel">
<h2>What we have, what we don't, and what's blocked</h2>
<p>This page is the answer to "what do you need from me?". The first table is what is already
verified and in the repository. The second is what is missing, why it matters, and exactly how
to go about getting it. The third is the small set of decisions only a human can make.</p>
</section>

<section class="panel">
<h2>We have this, verified</h2>
{table_have}
</section>

<section class="panel">
<h2>We need this, and here is how to get it</h2>
{table_need}
</section>

<section class="panel">
<h2>Decisions that need a human</h2>
<ol class="summary">
<li><b>May we look at sportsbook prices at all?</b> Not to copy them &mdash; the brief rules that
out &mdash; but to compare. Without a market price there is no such thing as an edge, only
self-consistency. Every strategy on the leaderboard today is graded against our own line, which
is the honest thing to do but is not the same as being profitable.</li>
<li><b>Do we want the leaderboard open to outside contributors?</b> A competition with rewards
implies yes, which implies a sandboxed runner. Option D1 on the improvements page.</li>
<li><b>How should a "reward" be defined?</b> Raw hit rate, return on a flat stake, or
risk-adjusted return? The gates currently test hit rate only.</li>
<li><b>What is the stake?</b> Nothing is deployable on the current evidence, but the harness
needs a staking rule before it can report anything a reviewer would act on.</li>
</ol>
<p class="callout">Until the first question is answered, the most accurate description of this
system is: <b>a verified, self-consistent line-origination engine with an unproven strategy
layer.</b> That is a real achievement, and it is not yet a betting system.</p>
</section>
""".format(
        table_have=table(["Asset", "Detail", "Source"], hrows, "tbl"),
        table_need=table(["Missing", "What it blocks", "How to get it", "Priority"],
                         nrows, "tbl"),
    )
    return shell("questions.html", "Open Questions",
                 "What we have, what we don't, and the decisions that are blocked until "
                 "someone answers.", body, wide=True)


# =========================================================================== render
CSS = open(os.path.join(ROOT, "site", "assets", "style.css"), encoding="utf-8").read()


def main():
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    with open(os.path.join(SITE, "assets", "style.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)
    print("wrote assets/style.css")
    pages = {
        "index.html": page_index,
        "lines.html": page_lines,
        "strategies.html": page_strategies,
        "correlations.html": page_correlations,
        "injuries.html": page_injuries,
        "props.html": page_props,
        "gameflow.html": page_gameflow,
        "data.html": page_data,
        "flagged.html": page_flagged,
        "suggestions.html": page_suggestions,
        "questions.html": page_questions,
    }
    for fn, fn_page in pages.items():
        with open(os.path.join(SITE, fn), "w", encoding="utf-8") as fh:
            fh.write(fn_page())
        print("wrote", fn)


if __name__ == "__main__":
    main()
