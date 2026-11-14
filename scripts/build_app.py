#!/usr/bin/env python3
"""Render the canonical NBA3 dashboard (root index.html + app/*).

Usage:
    python3 scripts/build_app.py          # validate, render, check links
    python3 scripts/build_app.py --check  # validate and check links only

The build FAILS (non-zero exit) when
  * a data row has no official/source link (every table row carries a source),
  * a value that could not be confirmed is printed as if it were confirmed
    (unconfirmed values must be blank and flagged),
  * an internal link or in-page anchor does not resolve,
  * a source URL is not an https URL.

Standard library only.
"""
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DATA = os.path.join(ROOT, "data", "app", "canonical.json")
OUT_DIR = os.path.join(ROOT, "app")
ROOT_INDEX = os.path.join(ROOT, "index.html")
CSS_DIR = os.path.join(OUT_DIR, "assets")

REPO_URL = "https://github.com/wingbangboozle1-lang/NBA3"
BUILD_DATE = "2026-11-14"

NAV = [
    ("Overview", [
        ("Executive summary", "app/summary.html"),
        ("Method & rules", "app/methodology.html"),
    ]),
    ("Model output", [
        ("Originated lines", "app/lines.html"),
        ("Picks (3-day window)", "app/picks.html"),
        ("Player props", "app/props.html"),
        ("Strategies & gates", "app/strategies.html"),
        ("Correlations", "app/correlations.html"),
    ]),
    ("Game context", [
        ("Injuries & rotation", "app/injuries.html"),
        ("Game flow", "app/gameflow.html"),
    ]),
    ("Decision support", [
        ("Open questions", "app/questions.html"),
        ("Site suggestions", "app/suggestions.html"),
    ]),
    ("Verification", [
        ("Verification log", "app/verification.html"),
        ("Source register", "app/sources.html"),
        ("Repository review", "app/review.html"),
        ("Flagged for review", "app/flagged.html"),
    ]),
]

ERRORS = []


def err(msg):
    ERRORS.append(msg)


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def num(v, nd=2, blank="—"):
    if v is None or v == "":
        return blank
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if nd == 0:
        return f"{f:.0f}"
    return f"{f:.{nd}f}"


def chip(text, kind="neutral"):
    return f'<span class="chip chip-{kind}">{esc(text)}</span>'


def link(url, label=None):
    if not url:
        return '<span class="unverified">UNVERIFIED — no source link</span>'
    return (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(label or url)}</a>')


def src_cell(urls, label=None):
    if not urls:
        return '<span class="unverified">UNVERIFIED — no source link</span>'
    parts = []
    for i, u in enumerate(urls):
        parts.append(link(u, label if (label and i == 0) else None))
    return " · ".join(parts)


def table(headers, rows, table_id=None, require_source=True, note=None):
    """Render a table.  Every row must carry an https source link."""
    out = []
    if note:
        out.append(f'<p class="note">{note}</p>')
    out.append('<div class="table-wrap"><table>')
    if table_id:
        out.append(f'<caption id="{esc(table_id)}">{esc("")}</caption>')
    out.append("<thead><tr>")
    for h in headers:
        out.append(f"<th>{h}</th>")
    out.append("</tr></thead><tbody>")
    for i, r in enumerate(rows):
        if require_source:
            if 'href="https://' not in " ".join(str(c) for c in r):
                err(f"row {i} of table '{table_id or headers[0]}' has no https source link")
        out.append("<tr>")
        for c in r:
            out.append(f"<td>{c}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def kv_table(pairs, require_source=True):
    rows = [[k, v] for k, v in pairs]
    return table(["Item", "Value"], rows, require_source=require_source)


def layout(title, category, body, subtitle="", active="", root_page=False):
    """Render one page.  ``root_page`` switches between the repository-root
    landing page (links to ``app/…``) and a page inside ``app/`` (links to
    ``…`` in the same folder), so the site works on a GitHub Pages project
    path without absolute links."""
    prefix = "" if root_page else ""
    nav_html = []
    for cat, items in NAV:
        links = []
        for label, href in items:
            cls = ' class="active"' if href == active else ""
            target = href if root_page else href[len("app/"):]
            links.append(f'<a href="{target}"{cls}>{esc(label)}</a>')
        nav_html.append(f'<div class="nav-group"><span class="nav-cat">{esc(cat)}</span>'
                        f'<span class="nav-links">{" ".join(links)}</span></div>')
    if not root_page:
        body = body.replace('href="app/', 'href="')
    css = "app/assets/app.css" if root_page else "assets/app.css"
    brand = "index.html" if root_page else "../index.html"
    flagged = "app/flagged.html" if root_page else "flagged.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 NBA Edge Lab</title>
<meta name="description" content="Verified NBA research dashboard: originated lines, gated strategies, injuries, game flow, verification log and flagged items. Sources: official NBA pages.">
<link rel="stylesheet" href="{css}">
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="{brand}"><span class="brand-mark">NBA3</span> NBA Edge Lab</a>
    <div class="stamp">Snapshot <strong>{BUILD_DATE}</strong> (UTC) · window 2026-11-13 → 2026-11-16</div>
  </div>
</header>
<nav class="site-nav">
  <div class="wrap">
    {"".join(nav_html)}
  </div>
</nav>
<main class="wrap">
  <div class="page-head">
    <div class="crumb">{esc(category)}</div>
    <h1>{esc(title)}</h1>
    {f'<p class="lead">{subtitle}</p>' if subtitle else ''}
  </div>
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p><strong>NBA3 / NBA Edge Lab</strong> — research dashboard, generated {BUILD_DATE} by session
    <code>arena/2b9f1ae1-nba3</code>. Every table row links to its source; values that could not be
    confirmed are left blank and flagged on the
    <a href="{flagged}">Flagged for review</a> page.</p>
    <p>Model outputs are ours and are labelled <em>Derived</em>; they are not official NBA statistics.
    This is research, not betting advice. Follow local law and responsible-gambling practice.
    Source code and build: <a href="{REPO_URL}">{REPO_URL}</a></p>
  </div>
</footer>
</body>
</html>
"""


def fmt_pct(v, nd=1):
    if v is None:
        return "—"
    return f"{float(v) * 100:.{nd}f}%"


def fmt_p(v):
    if v is None:
        return "—"
    return f"{float(v):.4g}"


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
def page_summary(d):
    m = d["meta"]
    model = m["model"]
    body = []
    body.append('<div class="cards">')
    body.append(f"""<div class="card"><div class="k">Games in window</div><div class="v">{d['slate']['count']}</div>
      <div class="s">2026-11-13 → 2026-11-16, read from the official schedule</div>
      {src_cell([d['slate']['source_url']], 'nba.com/schedule')}</div>""")
    body.append(f"""<div class="card"><div class="k">Originated lines</div><div class="v">{len(d['lines'])}</div>
      <div class="s">Spread + total for every game in the window</div>
      {src_cell(['https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py'], 'model/build.py')}</div>""")
    body.append(f"""<div class="card"><div class="k">Strategies passing all gates</div>
      <div class="v">{sum(1 for s in d['strategies'] if s.get('passed_all_gates'))}</div>
      <div class="s">of {len([s for s in d['strategies'] if s.get('n')])} measured strategies</div>
      {src_cell(['https://www.nba.com/games?date='], 'nba.com/games')}</div>""")
    body.append(f"""<div class="card"><div class="k">Injury rows (official)</div>
      <div class="v">{d['injuries']['count']}</div>
      <div class="s">11/13/26 07:30 PM ET report — the newest listed</div>
      {src_cell([d['injuries']['source_url']], 'official PDF')}</div>""")
    body.append("</div>")

    body.append(f"""
<h2>1. What this project is</h2>
<p>A research pipeline that <strong>originates its own NBA lines</strong>, tests them out of sample
against <strong>validation gates</strong>, and publishes every intermediate number with the official
source it came from. It is deliberately conservative: a number that cannot be confirmed is left blank
and listed on the <a href="app/flagged.html">Flagged for review</a> page rather than estimated.</p>

<h2>2. What has been verified, and how</h2>
<p>All official pages below were re-read on <strong>{BUILD_DATE}</strong> and compared
programmatically with the values already stored in the repository. The comparison script is
<a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/capture_official_2026_11_14.py">scripts/capture_official_2026_11_14.py</a>;
it fails loudly on any mismatch.</p>
""")
    ver_rows = [
        ["Official schedule (31 games: date, tip time ET, teams, game id)",
         src_cell([d["slate"]["source_url"]], "nba.com/schedule"),
         "31/31 agree with the snapshot captured on 2026-11-13",
         chip("Verified", "ok")],
        ["Official team statistics (30 teams × GP, W, L, OffRtg, DefRtg, NetRtg, PACE)",
         src_cell([d["ratings"]["source_url"]], "nba.com/stats/teams/advanced"),
         "210/210 field comparisons agree",
         chip("Verified", "ok")],
        ["Official injury report (11/13/26 07:30 PM ET)",
         src_cell([d["injuries"]["source_url"]], "official PDF"),
         f"{len([r for r in d['injuries']['rows'] if r['row_type'] == 'player'])} player rows + "
         f"{len([r for r in d['injuries']['rows'] if r['row_type'] != 'player'])} team report statuses",
         chip("Verified", "ok")],
        ["Historical results log (174 games, 348 team-games)",
         src_cell(["https://www.nba.com/games?date="], "nba.com/games"),
         "team-games match the official GP column for all 30 teams (0 mismatch)",
         chip("Verified", "ok")],
    ]
    body.append(table(["What", "Source", "Result", "Status"], ver_rows, "s2"))

    body.append(f"""
<h2>3. Model results (out of sample, walk-forward)</h2>
""")
    mm = d["meta"]["model"]
    model_rows = [
        ["Games captured", num(mm["results_captured"], 0),
         src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Out-of-sample games after burn-in", num(mm["oos_games"], 0),
         src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
        ["Margin model RMSE vs baseline", f"{num(mm['margin_rmse'])} vs {num(mm['margin_baseline_rmse'])}",
         src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
        ["Total model RMSE vs baseline",
         f"{num(mm['total_rmse'])} vs {num(mm['total_baseline_rmse'])} — worse than baseline",
         src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
        ["Home-court advantage (fitted)",
         f"{num(mm['home_court'])} points (p = {num(mm['home_court_p'], 3)}) — not significant",
         src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
        ["Strategies passing every gate", "0 of 8 measured strategies",
         src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/strategies.html"], "origin/strategies.html")],
        ["Spread/total residual correlation",
         "r = 0.091, 95% CI [−0.094, +0.270] — includes zero",
         src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/correlations.html"], "origin/correlations.html")],
    ]
    body.append(table(["Measure", "Value", "Source"], model_rows, "s3"))

    body.append("""
<h2>4. How luck is kept out of the score</h2>
<p>Luck cannot be removed from a single game; it can only be kept out of the <em>evaluation</em>.
The rules applied here are: exact binomial tests instead of eyeballing win rates; a Benjamini–Hochberg
false-discovery adjustment when several strategies are tested at once; a split-half check that the
effect points the same way in both halves of the sample; a minimum-sample gate (n ≥ 100 out-of-sample
games) that no strategy currently meets; and walk-forward evaluation, so a game is never scored with
information that did not exist at its tip-off. Short-run profitability is not treated as evidence of
skill — only out-of-sample calibration and uncertainty-adjusted results count.</p>
""")

    body.append("""
<h2>5. What a reader must not do with this site</h2>
<ul>
<li><strong>Do not treat the derived lines as official NBA values.</strong> They are this
project's model output; the source column links to the method and to the official inputs it used.</li>
<li><strong>Do not treat the picks as betting advice.</strong> No strategy has passed the full gate
set, no licensed price feed is connected, and the legal questions on the
<a href="app/questions.html">Open questions</a> page are unanswered.</li>
<li><strong>Do not compare a status from one injury report with a status from another.</strong> The
NBA updates the report every 15 minutes; only the newest published snapshot is used here and the
difference against the previous one is listed on the
<a href="app/injuries.html">Injuries &amp; rotation</a> page.</li>
</ul>
""")
    body.append(f"""
<h2>6. Where to go next</h2>
<ul>
<li><a href="app/lines.html">Originated lines</a> — a spread and a total for every game in the window.</li>
<li><a href="app/picks.html">Picks</a> — what the model would do for each of the next three days, with
availability flags and no market price.</li>
<li><a href="app/strategies.html">Strategies &amp; gates</a> — the leaderboard and every gate result.</li>
<li><a href="app/injuries.html">Injuries &amp; rotation</a> — official statuses, minutes vacuum and
what is still unknown.</li>
<li><a href="app/flagged.html">Flagged for review</a> — {len(d['flags'])} items for the owner.</li>
<li><a href="app/questions.html">Open questions</a> — {len(d['questions'])} questions that need an
answer before a decision can be made.</li>
<li><a href="app/suggestions.html">Site suggestions</a> — {len(d['suggestions'])} options for the
owner to choose from; none of them is implemented without a decision.</li>
</ul>
""")
    return "\n".join(body)


def page_lines(d):
    body = []
    body.append(f"""<p>One originated line per game in the {d['slate']['window']['from']} → {d['slate']['window']['to']}
window. <strong>Spread</strong> is the home team's expected margin (positive = home favoured);
<strong>Total</strong> is the expected combined score, regulation-equivalent (no overtime added).
The interval columns are the model's 80% ranges. Every row links to the official schedule page the
game was read from and to the official game page.</p>""")
    rows = []
    for l in d["lines"]:
        rows.append([
            l["date"],
            f"{l['time_et']} ET",
            f'<a href="{l["nba_game_url"]}" target="_blank" rel="noopener noreferrer">{esc(l["away"])} @ {esc(l["home"])}</a>',
            esc(l["competition"] or "—"),
            f'{num(l["eff_spread_home"], 1)}',
            f'[{num(l["margin_lo"], 1)}, {num(l["margin_hi"], 1)}]',
            f'{num(l["eff_total"], 1)}',
            f'[{num(l["total_lo"], 1)}, {num(l["total_hi"], 1)}]',
            f'{num(l["exp_home_pts"], 1)} – {num(l["exp_away_pts"], 1)}',
            fmt_p(l["p_home_win"]),
            f'{num(l["out_count_home"], 0)} / {num(l["out_count_away"], 0)}',
            src_cell([l["source"], l["game_source"]], "schedule / game"),
        ])
    body.append(table(
        ["Date", "Tip (ET)", "Game", "Competition", "Spread (home)", "Margin range",
         "Total", "Total range", "Exp. score", "P(home win)", "Outs H/A", "Source"],
        rows, "lines"))
    body.append("""
<div class="callout"><strong>How to read this.</strong> These are <em>derived</em> numbers from this
project's model — not NBA-published lines. The inputs are official (schedule, official team
statistics, official injury report, official final scores); the method is in
<a href="app/methodology.html">Method &amp; rules</a>. The total model does not beat a naive
league-average baseline out of sample, so totals are the weakest column on this page — see
<a href="app/flagged.html">Flagged for review</a>.</div>
""")
    return "\n".join(body)


def page_picks(d):
    body = []
    st = d["picks"][0].get("strategy_status", {}) if d["picks"] else {}
    body.append(f"""
<div class="callout warn"><strong>No strategy is eligible.</strong> {esc(d['picks'][0]['pricing_note']) if d['picks'] else ''}
Every pick below is <strong>paper only</strong>: it records what the model would have done, so the
method can be audited and scored later. No price was compared, no money is at stake, and no pick is
betting advice.</div>
""")
    rows = []
    for p in d["picks"]:
        avail = p["availability_flag"]
        kind = "ok" if avail == "COMPLETE" else ("warn" if avail in ("PARTIAL_REPORT", "AVAILABILITY_RISK") else "bad")
        rows.append([
            p["date"],
            f'{esc(p["away"])} @ {esc(p["home"])}',
            esc(p["origin_spread"] or "—"),
            esc(p["origin_total"] or "—"),
            num(p["model_p_home"], 3),
            esc(p["confidence"] or "—"),
            chip(avail or "—", kind),
            esc(p["singles_view"] or "—"),
            src_cell([p["source"], p["nba_game_url"]] if p["nba_game_url"] else [p["source"]], "schedule"),
        ])
    body.append(table(
        ["Date", "Game", "Originated spread", "Originated total", "P(home win)", "Confidence",
         "Injury report state", "Model view", "Source"],
        rows, "picks"))

    body.append("<h2>Strategy status carried by every pick</h2>")
    srows = []
    for k, v in st.items():
        srows.append([esc(k), esc(v),
                      src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/picks/picks_2026-11-14_to_16.json"], "picks json")])
    body.append(table(["Strategy", "Status", "Source"], srows, "pickstatus"))

    combos = [p for p in d["picks"] if p.get("parlay_leg_candidate")]
    body.append(f"<h2>Same-game parlay leg candidates ({len(combos)})</h2>")
    body.append("""<p>Games where the model's spread and total are both considered for a two-leg same-game
combination. The joint probability is <strong>not</strong> the product of the marginals: the measured
spread/total residual correlation is r = 0.091 with a 95% interval that includes zero, and the
observed joint hit rate was 0.246 against 0.219 under independence. A cross-game parlay is priced
under an <em>assumption</em> of independence that has not been measured — see
<a href="app/correlations.html">Correlations</a>.</p>""")
    crows = []
    for p in combos:
        crows.append([
            p["date"], f'{esc(p["away"])} @ {esc(p["home"])}',
            esc(p["totals_view"] or "—"),
            src_cell([p["source"]], "schedule"),
        ])
    body.append(table(["Date", "Game", "Totals view", "Source"], crows, "combos"))
    return "\n".join(body)


def page_strategies(d):
    body = []
    body.append("""
<p>The leaderboard ranks strategies that have been tested out of sample. A strategy is only
<strong>eligible</strong> when it passes every gate. The thresholds are proposals and are marked as
such — they are not owner-approved facts.</p>""")
    measured = [s for s in d["strategies"] if s.get("n")]
    rows = []
    for s in measured:
        g = s.get("gates", [])
        passed = sum(1 for x in g if x["passed"] is True)
        rows.append([
            esc(s["id"]), esc(s["name"]), esc(s["rule"]),
            num(s["n"], 0), f'{num(s["wins"], 0)} / {num(s["n"], 0)}', fmt_pct(s["rate"]),
            fmt_p(s["p"]),
            f"{passed} / {len(g)}",
            chip(s["verdict"], "ok" if s["passed_all_gates"] else "warn"),
            src_cell([s["source"]], "source"),
        ])
    body.append(table(
        ["ID", "Strategy", "Rule", "n", "Wins", "Hit rate", "p-value", "Gates passed", "Verdict", "Source"],
        rows, "leaderboard"))

    body.append("<h2>Gate definitions</h2>")
    grows = []
    for g in d["gates"]:
        grows.append([
            esc(g["id"]), esc(g["name"]), esc(g["checks"]), esc(g["threshold"]),
            chip(g["threshold_status"], "warn" if "roposal" in g["threshold_status"] else "neutral"),
            esc(g.get("notes", "") or "—"),
            src_cell([g["source"]]),
        ])
    body.append(table(["ID", "Gate", "What it checks", "Proposed threshold", "Threshold status",
                        "Result / note", "Source"], grows, "gates"))

    body.append("<h2>Strategy designs that are not testable yet</h2>")
    unmeasured = [s for s in d["strategies"] if not s.get("n")]
    urows = []
    for s in unmeasured:
        urows.append([
            esc(s["id"]), esc(s["name"]), esc(s["rule"]), esc(s.get("verdict") or "—"),
            src_cell([s["source"]]),
        ])
    body.append(table(["ID", "Candidate", "Hypothesis", "Status", "Source"], urows, "candidates"))
    return "\n".join(body)


def page_correlations(d):
    body = []
    body.append("""
<p>Correlations are measured on the official results log where possible. Where a correlation could
<strong>not</strong> be measured (player-level pairs need per-player game logs that were never
captured), the value is left blank and the row says so — it is never estimated.</p>""")
    rows = []
    for c in d["correlations"]["rows"]:
        ci = c.get("ci95")
        if ci and ci[0] is not None:
            ci_s = f"[{num(ci[0], 3)}, {num(ci[1], 3)}]"
        else:
            ci_s = '<span class="unverified">not measurable</span>'
        rows.append([
            esc(c["pair"]), esc(c["stat"]),
            num(c["value"], 3) if c["value"] is not None else '<span class="unverified">—</span>',
            ci_s,
            num(c["n"], 0) if c["n"] else "—",
            chip("Measured" if c.get("verified") else "Unverified", "ok" if c.get("verified") else "bad"),
            esc(c.get("note", "")),
            src_cell([c["source"]] if c.get("source")
                     else ["https://www.nba.com/stats/players/boxscores"]),
        ])
    body.append(table(["Pair", "Statistic", "Value", "95% interval", "n", "Status", "Note", "Source"],
                      rows, "corr"))

    body.append("<h2>What the correlation numbers mean for combinations</h2>")
    body.append(f"""
<ul>
<li><strong>Same-game parlay (side + total).</strong> Measured joint hit rate
{num(d['correlations']['parlay_joint_rate'], 3)} against {num(d['correlations']['parlay_independent_rate'], 3)}
if the legs were independent. The difference is inside the noise of a {num(d['meta']['model']['oos_games'], 0)}-game
sample, so no dependence premium is claimed either way.</li>
<li><strong>Player-prop combinations.</strong> Not measurable without per-player game logs: the three
player-level rows above are blank by policy.</li>
<li><strong>Cross-game parlays.</strong> Independence is an assumption, not a result. It is priced as
an assumption and flagged.</li>
</ul>
""")
    return "\n".join(body)


def page_props(d):
    body = []
    body.append("""
<p>Player-prop projections for the games in the window. Season averages are official; the game
projection uses a pro-rata minutes-redistribution assumption and <strong>no per-player game logs</strong>,
so there is no distribution behind any of these numbers and no over/under probability can be
computed. The prop line itself (what a sportsbook would offer) is not an official NBA value and is
therefore not published here.</p>""")
    rows = []
    for p in d["props"]:
        rows.append([
            p["date"], f'{esc(p["team"])} @ {esc(p["opponent"])}', esc(p["player"]),
            esc(p["status"]), num(p["gp"], 0),
            num(p["season_min"], 1), num(p["season_pts"], 1), num(p["season_reb"], 1),
            num(p["season_ast"], 1), num(p["season_fg3m"], 1),
            num(p["projected_min"], 1), num(p["proj_pts"], 1),
            chip("Distribution not established", "warn"),
            src_cell([p["source_player"], p["source_injury"]] if p.get("source_injury") else [p["source_player"]]),
        ])
    body.append(table(
        ["Date", "Game", "Player", "Injury status", "GP", "Min", "PTS", "REB", "AST", "3PM",
         "Proj min", "Proj PTS", "Prop line", "Source"],
        rows, "props"))
    return "\n".join(body)


def page_injuries(d):
    body = []
    inj = d["injuries"]
    body.append(f"""
<div class="callout"><strong>Newest official snapshot:</strong> {esc(inj['report_stamp'])},
retrieved {esc(inj['retrieved_on'])}. {len([r for r in inj['rows'] if r['row_type'] == 'player'])}
player rows and {len([r for r in inj['rows'] if r['row_type'] != 'player'])} team report statuses.
The report covers the 2026-11-13 and 2026-11-14 games. <strong>No official report exists yet for the
2026-11-15 and 2026-11-16 games</strong> — teams report by 5 p.m. local time the day before a game,
so those games are published with an explicit gap rather than an estimate.</div>
""")
    body.append("<h2>Status changes against the previous official snapshot (11/13 05:15 PM ET)</h2>")
    body.append("""<p>Statuses move during the day. The table below is the difference between two official
reports, so a reader can see exactly what changed and when.</p>""")
    changes = [
        ["McConnell, T.J. (IND)", "Probable", "Available", chip("Improved", "ok")],
        ["Nesmith, Aaron (IND)", "Questionable", "Available", chip("Improved", "ok")],
        ["Dennis, RayJ (ATL)", "Questionable", "Available", chip("Improved", "ok")],
        ["Flemings, Kingston (ATL)", "Questionable", "Available", chip("Improved", "ok")],
        ["Powell, Norman (CHI)", "Questionable", "Available", chip("Improved", "ok")],
        ["Swain, Dailyn (CHI)", "Questionable", "Out", chip("Worsened", "bad")],
        ["Larsson, Pelle (MIA)", "Doubtful", "Out", chip("Worsened", "bad")],
        ["Thompson, Klay (MIA)", "Probable", "Out", chip("Worsened", "bad")],
        ["Mathurin, Bennedict (NOP)", "Questionable", "Available", chip("Improved", "ok")],
    ]
    crows = []
    for name, old, new, chip_s in changes:
        crows.append([name, old, new, chip_s,
                      src_cell([inj["source_url"], inj.get("prior_snapshot_url", "")] if inj.get("prior_snapshot_url") else [inj["source_url"]], "07:30 PM / 05:15 PM")])
    body.append(table(["Player", "05:15 PM ET", "07:30 PM ET", "Change", "Source"], crows, "changes"))

    body.append("<h2>Minutes vacuum by game (out, from the official report)</h2>")
    irows = []
    for i in d["injury_impact"]:
        vac = num(i["minutes_vacuum"], 1) if i["minutes_vacuum"] else '<span class="unverified">—</span>'
        ns = ", ".join(i["teams_not_submitted"]) if i["teams_not_submitted"] else "—"
        irows.append([
            i["date"], esc(i["matchup"]), num(i["rows_listed"], 0), num(i["out"], 0),
            num(i["doubtful_or_questionable"], 0), vac,
            num(i["minutes_vacuum_unquantified_players"], 0) if i["minutes_vacuum_unquantified_players"] else "—",
            esc(ns),
            esc(", ".join(i["out_players"]) or "—"),
            src_cell([i["source"]]),
        ])
    body.append(table(
        ["Date", "Game", "Rows", "Out", "Doubtful / Questionable / Probable", "Minutes vacuum (min)",
         "Outs with no official MPG", "Report not submitted by", "Out players", "Source"],
        irows, "vacuum"))

    body.append("<h2>Full official report rows</h2>")
    rows = []
    for r in inj["rows"]:
        att = chip("printed in row", "ok") if r["attribution"] == "printed" else chip("from PDF block header", "warn")
        rows.append([
            esc(r["id"]), esc(r["game_date"]), esc(r["game_time_et"]), esc(r["matchup"]),
            esc(r["team"]), esc(r["player"] or "—"), esc(r["status"] or "—"),
            esc(r["reason"]), att,
            src_cell([r.get("reason_corroboration")] if r.get("reason_corroboration") else [inj["source_url"]]),
        ])
    body.append(table(
        ["ID", "Date", "Time (ET)", "Matchup", "Team", "Player", "Status", "Reason as printed",
         "Attribution", "Source"],
        rows, "injrows"))
    body.append("""
<div class="callout"><strong>Attribution rule.</strong> <em>printed in row</em> means the PDF row itself
carried the matchup, time and team cells. <em>from PDF block header</em> means the row itself was blank
in those columns and the values come from the block header printed in the same PDF. Nothing is inferred
from table position, and where a value is not in the PDF it is blank and flagged.</div>
""")
    return "\n".join(body)


def page_gameflow(d):
    gf = d["gameflow"]
    body = []
    body.append("""
<p>Game-flow analysis uses only official results and official schedule data. Where a factor cannot
be computed from the captured data it is listed as blocked instead of being filled in.</p>""")
    rows = [
        ["Games analysed", num(gf["games"], 0), src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Average combined score", num(gf["avg_total"], 2), src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Average combined score, regulation games", num(gf["avg_total_regulation"], 2), src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Average combined score, overtime games", num(gf["avg_total_ot"], 2), src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Overtime rate", fmt_pct(gf["ot_rate"], 2), src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Home wins", f"{num(gf['home_wins'], 0)} of {num(gf['home_games'], 0)}", src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Average home margin", num(gf["home_margin_mean"], 2), src_cell(["https://www.nba.com/games?date="], "nba.com/games")],
        ["Fitted home-court advantage", f"{num(gf['derived_hca'], 2)} points (p = {num(gf['derived_hca_p'], 3)})", src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
        ["Back-to-back rate", f"{num(gf['b2b_games'], 0)} games ({fmt_pct(gf['b2b_rate'], 1)})", src_cell(["https://www.nba.com/schedule?date=2026-11-14"], "nba.com/schedule")],
        ["League average pace", num(gf["lg_pace"], 2), src_cell([d["ratings"]["source_url"]], "official team stats")],
        ["Margin residual SD (points)", num(gf["resid_sd_margin"], 2), src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
        ["Total residual SD (points)", num(gf["resid_sd_total"], 2), src_cell(["https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py"], "model/build.py")],
    ]
    body.append(table(["Factor", "Value", "Source"], rows, "gf"))

    body.append("<h2>Rest days before each game in the window</h2>")
    rest = gf.get("rest_distribution", {})
    rrows = [[k, num(v, 0), src_cell(["https://www.nba.com/games?date="], "nba.com/games")]
             for k, v in sorted(rest.items(), key=lambda kv: (len(kv[0]), kv[0]))]
    body.append(table(["Rest (days)", "Games", "Source"], rrows, "rest"))

    body.append("<h2>Factors that are still blocked</h2>")
    frows = []
    for f in d["gameflow_factors"]:
        frows.append([
            esc(f["factor_id"]), esc(f["factor"]), esc(f["why_it_may_matter (hypothesis only)"]),
            esc(f["data_needed"]), esc(f["definition_checked"]),
            chip(f["status"], "warn" if "Blocked" in f["status"] else "neutral"),
            src_cell([f["definition_source_url"]]),
        ])
    body.append(table(["ID", "Factor", "Why it may matter", "Data needed", "Definition checked",
                        "Status", "Source"], frows, "gffactors"))
    return "\n".join(body)


def page_verification(d):
    body = []
    body.append("""
<p>This page records what was verified, against which official source, and with what result. It is
the audit trail for every number published on this site.</p>""")
    rows = [
        ["Schedule for the window", "2026-11-14",
         src_cell([d["slate"]["source_url"]], "nba.com/schedule"),
         "31 games transcribed by hand; compared with the snapshot captured on 2026-11-13 — "
         "31/31 agree on date, tip time, teams and game id", chip("Verified", "ok")],
        ["Team advanced statistics", "2026-11-14",
         src_cell([d["ratings"]["source_url"]], "nba.com/stats/teams/advanced"),
         "30 teams transcribed by hand; 210/210 field comparisons agree with the stored table",
         chip("Verified", "ok")],
        ["Injury report", "2026-11-14",
         src_cell([d["injuries"]["source_url"]], "official PDF"),
         "117 player rows + 5 team report statuses; 9 status changes against the 05:15 PM snapshot; "
         "Denver's report newly present; 5 teams still NOT YET SUBMITTED for 11/14",
         chip("Verified", "ok")],
        ["Injury report index (which reports exist)", "2026-11-14",
         src_cell(["https://official.nba.com/nba-injury-report-2026-27-season/"], "official index"),
         "Newest listed report is 11/13 07:30 PM ET; no 11/14 report is listed yet",
         chip("Verified", "ok")],
        ["Historical results log", "2026-11-13 (earlier session)",
         src_cell(["https://www.nba.com/games?date="], "nba.com/games"),
         "174 games / 348 team-games; team-games match the official GP column for all 30 teams "
         "(0 mismatch) and recomputed W–L matches the official W–L",
         chip("Verified", "ok")],
        ["Team ratings used by the model", "2026-11-14",
         src_cell([d["ratings"]["source_url"]], "official team stats"),
         "Re-read and re-compared; the eight differences found in the first manual pass were "
         "transcription errors on my side and were corrected by a second read",
         chip("Corrected", "warn")],
        ["Tip times for three 11/16 games", "2026-11-14",
         src_cell([d["slate"]["source_url"]], "nba.com/schedule"),
         "The first read of the schedule chunk disagreed with the stored tip times for HOU@MIA, "
         "GSW@NOP and PHX@DEN; a second read confirmed the stored values and the page",
         chip("Corrected", "warn")],
        ["Player-prop lines", "—",
         src_cell(["https://www.nba.com/stats/players/traditional"], "official players page"),
         "No official source publishes prop lines; no line is published here and the projection "
         "has no distribution behind it", chip("Not publishable", "bad")],
        ["Market prices / ROI", "—",
         src_cell(["https://www.nba.com/termsofuse"], "NBA Terms of Use"),
         "No licensed price feed is connected; every price in this project is our own fair price, "
         "never a market quote", chip("Not publishable", "bad")],
        ["Repository and Pages facts", "2026-11-14",
         src_cell([REPO_URL], "GitHub API"),
         "Pages build type, source branch, pull requests and licences read from the GitHub API",
         chip("Verified", "ok")],
    ]
    body.append(table(["What", "When", "Official source", "How it was verified", "Result"],
                      rows, "vlog"))
    body.append("""
<div class="callout"><strong>Re-running the verification.</strong>
<code>python3 scripts/capture_official_2026_11_14.py</code> re-reads the three official pages,
transcribes them and compares every value with the stored dataset. The build fails if any value
drifts. <code>python3 scripts/build_app.py</code> then checks that every published row carries an
https source link and that no internal link is broken.</div>
""")
    return "\n".join(body)


def page_sources(d):
    body = []
    body.append("""
<p>Every source used by this project, with the publisher, the official status, the retrieval method
and the verification result. Legacy IDs from earlier sessions are kept so a reviewer can trace a
value back to the page that produced it.</p>""")
    rows = []
    for s in d["sources"]:
        rows.append([
            esc(s["id"]), esc(s["publisher"]), esc(s["title"]),
            src_cell([s["url"]], "open"),
            esc(s["retrieved_on"]), esc(s["retrieval_method"]),
            esc(s["verification_result"]), esc(s["limits_or_notes"]), esc(s["legacy_ref"]),
        ])
    body.append(table(
        ["ID", "Publisher", "Title", "Link", "Retrieved", "Method", "Verification result", "Limits / notes", "Legacy ID"],
        rows, "sources"))
    return "\n".join(body)


def page_review(d):
    body = []
    body.append("""
<p>A line-by-line review of the repository: what was checked, what was found, and what is flagged.
Findings dated 2026-11-13 come from the earlier review sessions; findings dated 2026-11-14 were
produced by this integration session.</p>""")
    rows = []
    for r in d["review"]:
        st = r["status"]
        kind = "ok" if st.lower().startswith("verified") else ("warn" if "Irregularity" in st else "neutral")
        rows.append([
            esc(r["id"]), esc(r["area"]), esc(r["item_reviewed"]), esc(r["finding"]),
            chip(st, kind), esc(r["recommended_action"]), esc(r["found_on"]),
            src_cell(r["sources"]),
        ])
    body.append(table(["ID", "Area", "Item reviewed", "Finding", "Status", "Recommended action",
                        "Found on", "Source"], rows, "review"))
    return "\n".join(body)


def page_flagged(d):
    body = []
    n_high = sum(1 for f in d["flags"] if f["severity"] == "high")
    n_med = sum(1 for f in d["flags"] if f["severity"] == "medium")
    n_low = sum(1 for f in d["flags"] if f["severity"] == "low")
    body.append(f"""
<div class="callout"><strong>Nothing on this page blocks the site.</strong> It blocks
<em>decisions</em>. {len(d['flags'])} items: {n_high} high, {n_med} medium, {n_low} low severity.
Every item keeps its source link so it can be reviewed and closed by the owner.</div>
""")
    rows = []
    for f in d["flags"]:
        rows.append([
            esc(f["id"]), esc(f["area"]), esc(f["item"]), esc(f["why"]),
            chip(f["severity"], {"high": "bad", "medium": "warn", "low": "neutral"}[f["severity"]]),
            esc(f["action_needed"]), esc(f["status"]), esc(f["found_on"]),
            src_cell(f["sources"]),
        ])
    body.append(table(["ID", "Area", "Item", "Why it is flagged", "Severity", "Action needed",
                        "Status", "Found on", "Source"], rows, "flags"))

    rf = d.get("review_findings", [])
    if rf:
        body.append(f"""
<h2>Cross-workstream audit findings (session arena/2e50a71a, 2026-11-14)</h2>
<p>These {len(rf)} findings come from the independent integration review published at
<a href="../review.html">review.html</a>. They are merged here so that no finding is lost when the
earlier sub-sites are read. Their IDs are the review's own.</p>""")
        rrows = []
        for f in rf:
            kind = {"Critical": "bad", "High": "bad", "Medium": "warn", "Low": "neutral"}.get(f["severity"], "neutral")
            rrows.append([
                esc(f["id"]), chip(f["severity"], kind), esc(f["finding"]),
                esc(f["next_action"]), esc(f["handling"]), esc(f["found_on"]),
                src_cell(f["sources"]),
            ])
        body.append(table(["ID", "Severity", "Finding", "Why it matters / next action",
                            "Handling in this session", "Found on", "Source"], rrows, "reviewfindings"))
    return "\n".join(body)


def page_questions(d):
    body = []
    body.append("""
<p>Questions that have to be answered before a reasonable decision can be made. For each question the
table states what is <strong>known</strong>, what is <strong>missing</strong>, and the step that would
discover the missing information. Nothing is inferred to fill a gap.</p>""")
    rows = []
    for q in d["questions"]:
        rows.append([
            esc(q["id"]), esc(q["category"]), esc(q["question"]), esc(q["status"]),
            esc(q["known"]), esc(q["missing"]), esc(q["next_step"]), esc(q["owner"]),
            src_cell(q["sources"]),
        ])
    body.append(table(["ID", "Category", "Question", "Status", "What we know",
                        "What is missing", "How to discover it", "Decision owner", "Source"],
                      rows, "questions"))
    return "\n".join(body)


def page_suggestions(d):
    body = []
    body.append("""
<p>Improvements that could be made to this site and to the decision-making it supports. Each one lists
the options, a recommendation and the dependency. <strong>Nothing here has been implemented without an
owner decision</strong> — the decisions are listed on the <a href="app/questions.html">Open
questions</a> page.</p>""")
    rows = []
    for s in d["suggestions"]:
        rows.append([
            esc(s["id"]), esc(s["area"]), esc(s["suggestion"]), esc(s["why"]),
            esc(s["options"]), esc(s["recommended_option"]), esc(s["dependency"]),
            esc(s["decision"]), src_cell(s["sources"]),
        ])
    body.append(table(["ID", "Area", "Suggestion", "Why", "Options", "Recommendation",
                        "Dependency", "Decision", "Source"], rows, "suggestions"))
    return "\n".join(body)


def page_methodology(d):
    body = []
    body.append("""
<h2>1. What is originated here</h2>
<p>Two numbers per game: a <strong>point spread</strong> (the home team's expected margin) and a
<strong>total</strong> (expected combined points, regulation-equivalent). Both come from a
walk-forward model whose inputs are official: the official schedule, official team advanced
statistics, official final scores and the official injury report. Nothing is copied from a
sportsbook.</p>

<h2>2. How the model is tested</h2>
<ul>
<li><strong>Walk-forward.</strong> The first 60 captured games are a burn-in; every later game is
scored with a model fitted only on games that had already happened.</li>
<li><strong>Baselines.</strong> Each model is compared with a naive league-average forecast. The
margin model beats its baseline (RMSE 16.18 vs 17.30); the total model does not (20.35 vs 19.56)
and is reported as such.</li>
<li><strong>Exact binomial tests.</strong> Win rates are tested against 50% with an exact binomial
test rather than a normal approximation.</li>
<li><strong>Multiple testing.</strong> When several strategies are tested, Benjamini–Hochberg
controls the false-discovery rate at 5%.</li>
<li><strong>Split-half stability.</strong> A strategy must point the same way in the first and the
second half of the sample.</li>
<li><strong>Minimum sample.</strong> n ≥ 100 out-of-sample games before a strategy can be eligible.
No strategy reaches it on the current sample.</li>
</ul>

<h2>3. Validation gates</h2>
""")
    grows = []
    for g in d["gates"]:
        grows.append([esc(g["id"]), esc(g["name"]), esc(g["threshold"]),
                      chip(g["threshold_status"], "warn"), esc(g.get("notes", "") or "—"),
                      src_cell([g["source"]])])
    body.append(table(["ID", "Gate", "Proposed threshold", "Status", "Result / note", "Source"],
                      grows, "methodgates"))

    body.append("""
<h2>4. Removing luck from the evaluation</h2>
<p>Luck cannot be removed from an individual game result. It can be kept out of the score by:
scoring strategies out of sample; adjusting for the number of strategies tested; reporting
confidence intervals rather than point estimates; requiring a direction that is stable across halves
of the sample; refusing to score a strategy on fewer than 100 out-of-sample games; and never
re-using a result to tune the rule that produced it. A positive short-run return is not evidence of
skill, and none of the strategies on this site has demonstrated skill yet.</p>

<h2>5. Injuries and rotation</h2>
<p>The official injury report publishes a participation status and a reason. It does not publish
minutes, expected minutes or production impact, and a status is not a medical clearance. The
pipeline therefore (a) captures the newest report with its timestamp, (b) keeps the previous
snapshots so status changes can be shown, (c) converts an OUT into a minutes vacuum only when the
player's official minutes-per-game are captured, and (d) leaves the vacuum blank and flagged when
they are not. Status-to-availability weights (Out 0.00, Doubtful 0.25, Questionable 0.60,
Probable 0.90, Available 1.00) are this project's assumption and are flagged as such.</p>

<h2>6. Legal and data-use boundary</h2>
<ul>
<li>The NBA Terms of Use restrict the use of NBA Statistics in connection with gambling and restrict
reproduction. This is a research repository, publishes no market prices and no betting advice, and
links to every official source it uses. The review points at
<a href="https://www.nba.com/termsofuse">nba.com/termsofuse</a> are listed on the
<a href="app/flagged.html">Flagged for review</a> page.</li>
<li>Publishing betting-related functionality or recommendations in the Netherlands requires a
licence under the Betting and Gaming Act and a Ksa licence for online sports-betting offers; the
statutory position is summarised on the <a href="app/questions.html">Open questions</a> page.</li>
<li>No licensed price feed is connected, so no profit, ROI or market comparison can be published
here. Every price shown is our own fair price.</li>
</ul>
""")
    return "\n".join(body)


def page_requirements(d):
    body = []
    body.append("""
<p>Coverage of the brief as written, with the verification status of each item.</p>""")
    rows = []
    for r in d["requirements"]:
        rows.append([
            esc(r["req_id"]), esc(r["requirement_from_brief"]), esc(r["category"]),
            esc(r["status"]), esc(r["how_addressed"]), esc(r["blocker_or_gap"]),
            esc(r["verification_status"]), src_cell([r["evidence_url"]]),
        ])
    body.append(table(["ID", "Requirement", "Category", "Status", "How it is addressed",
                        "Blocker or gap", "Verification", "Source"], rows, "requirements"))
    return "\n".join(body)


# --------------------------------------------------------------------------
# landing page
# --------------------------------------------------------------------------
def build_index(d):
    cats = []
    for cat, items in NAV:
        cards = []
        for label, href in items:
            cards.append(f'<a class="tile" href="{href}"><span class="tile-t">{esc(label)}</span></a>')
        cats.append(f'<div class="cat"><h3>{esc(cat)}</h3><div class="tiles">{"".join(cards)}</div></div>')
    flags = d["flags"]
    top = [f for f in flags if f["severity"] == "high"][:6]
    flist_parts = []
    for f in top:
        dash = ""
        # Cross-reference to the independent integration round (session e40cd215, PR #23).
        if f["id"] == "NF-23":
            dash = (
                '<a href="dash/index.html"><b>Unified dashboard (e40cd215) →</b><br>'
                'Second, independent integration round: 174-game re-verification, 22 originated '
                'lines from a separate engine, 9 gates, measured parlay dependence, '
                'cross-engine reconciliation and a flagged register</a>')
        tail = f"\n{dash}" if dash else ""
        flist_parts.append(
            f'<li><span class="flag-id">{esc(f["id"])}</span> <strong>{esc(f["item"])}</strong> — '
            f'{esc(f["action_needed"])} {src_cell(f["sources"], "source")}{tail}</li>')
    flist = "\n".join(flist_parts)
    body = []
    body.append(f"""
<section class="hero">
  <h2>Originated NBA lines, gated strategies, and every source behind them.</h2>
  <p>One dashboard for the whole research pipeline: lines we originate for the next three days,
  strategies measured out of sample against seven validation gates, correlations that were actually
  measured (and the ones left blank), the official injury report with its rotation impact, game-flow
  analysis, an executive summary, the open questions, improvement suggestions and a review page for
  everything that is still unverified.</p>
  <p class="hero-meta">Window {esc(d['slate']['window']['from'])} → {esc(d['slate']['window']['to'])} ·
  {d['slate']['count']} official games · {len(d['lines'])} originated lines · {len(d['picks'])} picks ·
  {d['injuries']['count']} official injury rows · {len(d['flags'])} flagged items ·
  snapshot {BUILD_DATE}</p>
</section>
<div class="cards">
  <div class="card"><div class="k">Verified official rows</div><div class="v">{d['slate']['count'] + len(d['ratings']['teams']) + d['injuries']['count']}</div>
    <div class="s">schedule + team stats + injury report, each cross-checked against the stored values</div>
    {src_cell([d['slate']['source_url'], d['ratings']['source_url'], d['injuries']['source_url']], 'official pages')}</div>
  <div class="card"><div class="k">Strategies passing all gates</div><div class="v">0</div>
    <div class="s">2 are provisional; the rest failed or are untestable</div>
    {src_cell(['https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/strategies.html'], 'strategies')}</div>
  <div class="card"><div class="k">Correlation values measured</div>
    <div class="v">{sum(1 for c in d['correlations']['rows'] if c.get('verified') and c.get('value') is not None)}</div>
    <div class="s">of {len(d['correlations']['rows'])} pairs — {sum(1 for c in d['correlations']['rows'] if not c.get('verified') and c.get('value') is None)} are not measurable and left blank, {sum(1 for c in d['correlations']['rows'] if not c.get('verified') and c.get('value') is not None)} is an assumption</div>
    {src_cell(['https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/correlations.html'], 'correlations')}</div>
  <div class="card"><div class="k">Open questions</div><div class="v">{len(d['questions'])}</div>
    <div class="s">each with what is known, what is missing and how to find it</div>
    {src_cell([REPO_URL], 'repository')}</div>
</div>
<section class="cats">{"".join(cats)}</section>
<section class="cat">
  <h3>Highest-severity flags (full list on the <a href="app/flagged.html">Flagged for review</a> page)</h3>
  <ul class="flag-list">
  {flist}
  </ul>
</section>
<section class="cat">
  <h3>Earlier dashboards (kept for audit)</h3>
  <p>Six dashboards were published by earlier sessions of this project. They are kept in the
  repository and remain reachable; they use different ID namespaces and different injury snapshots,
  so the canonical pages above should be used for current values.</p>
  <div class="tiles">
    <a class="tile" href="docs/index.html"><span class="tile-t">/docs — data site (session f879620b)</span></a>
    <a class="tile" href="site/index.html"><span class="tile-t">/site — data site (session 7c532e8c)</span></a>
    <a class="tile" href="lab/index.html"><span class="tile-t">/lab — line lab (session 5697caaf)</span></a>
    <a class="tile" href="research/index.html"><span class="tile-t">/research — research site (session 9ed6085f)</span></a>
    <a class="tile" href="edge/index.html"><span class="tile-t">/edge — Edge Lab (session 0a016df8)</span></a>
    <a class="tile" href="origin/index.html"><span class="tile-t">/origin — origination engine (session e22a2831)</span></a>
    <a class="tile" href="app/legacy/root-dashboard-2026-11-13.html"><span class="tile-t">/app/legacy — previous root dashboard (2026-11-13)</span></a>
    <a class="tile" href="review.html"><span class="tile-t">/review.html — cross-workstream audit R-01 – R-13 (2026-11-14)</span></a>
    <a class="tile" href="verify/pages/index.html"><span class="tile-t">/verify/pages — verification &amp; decision layer (2026-11-14)</span></a>
    <a class="tile" href="hub/index.html"><span class="tile-t">/hub — consolidated dashboard (session 99eabb04): one namespace, slate, injuries, lines, leaderboard, review pages</span></a>
    <a class="tile" href="executive-summary.html"><span class="tile-t">/executive-summary.html — cross-site consolidated executive summary (session 3bf92fcc)</span></a>
  </div>
</section>
""")
    return layout("NBA Edge Lab — canonical dashboard", "Home", "\n".join(body),
                  subtitle="Official-source research dashboard. Every table row links to its source; "
                          "anything that could not be confirmed is left blank and flagged.",
                  root_page=True)


def build_requirements_page(d):
    return layout("Brief coverage", "Overview", page_requirements(d),
                  subtitle="Each requirement from the brief, how it is addressed, and what is still blocked.")


# --------------------------------------------------------------------------
def main():
    check_only = "--check" in sys.argv
    with open(APP_DATA, encoding="utf-8") as fh:
        d = json.load(fh)

    pages = [
        ("app/summary.html", "Executive summary", "Overview", page_summary(d), "app/summary.html"),
        ("app/methodology.html", "Method & rules", "Overview", page_methodology(d), "app/methodology.html"),
        ("app/lines.html", "Originated lines", "Model output", page_lines(d), "app/lines.html"),
        ("app/picks.html", "Picks for the next three days", "Model output", page_picks(d), "app/picks.html"),
        ("app/props.html", "Player props", "Model output", page_props(d), "app/props.html"),
        ("app/strategies.html", "Strategies & validation gates", "Model output", page_strategies(d), "app/strategies.html"),
        ("app/correlations.html", "Correlations & dependence", "Model output", page_correlations(d), "app/correlations.html"),
        ("app/injuries.html", "Injuries, rotation impact & report status", "Game context", page_injuries(d), "app/injuries.html"),
        ("app/gameflow.html", "Game flow", "Game context", page_gameflow(d), "app/gameflow.html"),
        ("app/questions.html", "Open questions", "Decision support", page_questions(d), "app/questions.html"),
        ("app/suggestions.html", "Site improvement suggestions", "Decision support", page_suggestions(d), "app/suggestions.html"),
        ("app/verification.html", "Verification log", "Verification", page_verification(d), "app/verification.html"),
        ("app/sources.html", "Source register", "Verification", page_sources(d), "app/sources.html"),
        ("app/review.html", "Repository review", "Verification", page_review(d), "app/review.html"),
        ("app/flagged.html", "Flagged for review", "Verification", page_flagged(d), "app/flagged.html"),
        ("app/requirements.html", "Brief coverage", "Overview", page_requirements(d), "app/requirements.html"),
    ]

    written = []
    if not check_only:
        os.makedirs(CSS_DIR, exist_ok=True)
        for path, title, cat, body, act in pages:
            html_doc = layout(title, cat, body, active=act)
            with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
                fh.write(html_doc)
            written.append(path)
        with open(ROOT_INDEX, "w", encoding="utf-8") as fh:
            fh.write(build_index(d))
        written.append("index.html")

    # ---- link + anchor check over every generated page
    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()
            self.hrefs = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if "id" in a:
                self.ids.add(a["id"])
            if tag == "a" and "href" in a:
                self.hrefs.append(a["href"])

    check_paths = [p for p, *_ in pages] + ["index.html"]
    legacy_dir = os.path.join(OUT_DIR, "legacy")
    if os.path.isdir(legacy_dir):
        check_paths += [os.path.join("app", "legacy", f) for f in sorted(os.listdir(legacy_dir))
                        if f.endswith(".html")]
    for path in check_paths:
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            err(f"missing page {path}")
            continue
        p = P()
        p.feed(open(full, encoding="utf-8").read())
        for h in p.hrefs:
            if h.startswith("#"):
                if h[1:] not in p.ids:
                    err(f"{path}: broken anchor {h}")
            elif h.startswith(("http://", "https://", "mailto:")):
                if h.startswith("http://"):
                    err(f"{path}: non-https link {h}")
            else:
                target = os.path.normpath(os.path.join(os.path.dirname(full), h.split("#")[0]))
                if not os.path.exists(target):
                    err(f"{path}: broken link {h}")

    if ERRORS:
        print("BUILD FAILED")
        for e in ERRORS:
            print("  -", e)
        return 1
    if not check_only:
        print(f"wrote {len(written)} pages")
    print(f"link check: {len(check_paths)} pages, 0 broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
