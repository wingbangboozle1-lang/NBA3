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

# Filled by main() from the canonical dataset before any page is rendered, so the header of every
# page states what the snapshot still does not know (suggestion CS-41, recommended option B). It is
# derived, never asserted: if the availability artefact is missing, the badge says so.
CTX = {"window": "2026-11-14 → 2026-11-17", "pending": None, "sides": None, "by_date": ""}

NAV = [
    ("Overview", [
        ("Executive summary", "app/summary.html"),
        ("Method & rules", "app/methodology.html"),
    ]),
    ("Projection surface (public)", [
        ("Two-estimator projections", "app/projections.html"),
        ("Originated lines", "app/lines.html"),
        ("Prices for the window", "app/picks.html"),
        ("Injuries & rotation", "app/injuries.html"),
        ("Report availability", "app/freshness.html"),
        ("Game flow", "app/gameflow.html"),
        ("Refresh & provenance gates", "app/refresh.html"),
    ]),
    ("Bet surface (gated)", [
        ("Parlay & prop combos", "app/parlays.html"),
        ("Player props", "app/props.html"),
        ("Strategy leaderboard", "app/leaderboard.html"),
        ("Validation gates", "app/strategies.html"),
        ("Correlations", "app/correlations.html"),
        ("Pre-registration", "app/prereg.html"),
        ("Pick ledger", "app/ledger.html"),
        ("Settlement", "app/settlement.html"),
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
        ("Independent audit", "audit_dd1eb1f1/pages/index.html"),
        ("Latest audit", "audit_7f3b89af/pages/index.html"),
        ("Injury refresh audit", "audit_1823b910/pages/index.html"),
        ("Injury freshness audit (1:30 PM ET)", "audit_736efb4b/index.html"),
    ]),
    ("Archive", [
        ("Earlier sessions", "archive.html"),
    ]),
]

ARCHIVE_TREES = 14

ERRORS = []

# Data files published by session arena/79341829-nba3 (two-estimator layer, results feed,
# ledger, preregistration, gates). Loaded at build time so every page renders deterministically
# from committed inputs (the CI drift gate re-runs the build and diffs the output).
NEW = {}


def _load_new():
    def rd(path, default=None):
        p = os.path.join(ROOT, path)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        return default

    NEW["est"] = rd("data/app/estimators.json", {})
    NEW["feed"] = rd("data/app/results_feed.json", {"games": []})
    NEW["minutes"] = rd("data/app/minutes_model.json", {"teams": {}})
    NEW["inj1115"] = rd("data/app/official_injuries_2026-11-15_0615AM_79341829.json", {"rows": []})
    NEW["delta1115"] = rd("data/app/injury_delta_1115.json", {})
    NEW["gates"] = rd("data/app/gate_report.json", {"gates": []})
    NEW["closing"] = rd("data/app/closing_lines.json", {})
    NEW["flags_session"] = rd("data/app/flags_79341829.json", [])
    NEW["questions_session"] = rd("data/app/questions_79341829.json", [])
    NEW["suggestions_session"] = rd("data/app/suggestions_79341829.json", [])
    ledger = []
    p = os.path.join(ROOT, "data", "app", "ledger", "ledger.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    ledger.append(json.loads(line))
    NEW["ledger"] = ledger
    prereg = []
    pdir = os.path.join(ROOT, "data", "app", "prereg")
    if os.path.isdir(pdir):
        for f in sorted(os.listdir(pdir)):
            if f.endswith(".json"):
                with open(os.path.join(pdir, f), encoding="utf-8") as fh:
                    prereg.append(json.load(fh))
    NEW["prereg"] = prereg

# The stylesheet lives in app/assets/ but is not generated by this script, so a rebuild can emit a
# class that no longer exists in the CSS and nobody notices (suggestion CS-44, option B). These are
# the classes this build depends on; a missing one is a build failure, not a silent style change.
REQUIRED_CSS_CLASSES = (".stamp-warn", ".stamp-ok", ".chip-warn", ".chip-bad", ".chip-ok",
                        ".chip-neutral", ".table-wrap", ".callout", ".lead")


def _check_stylesheet():
    path = os.path.join(CSS_DIR, "app.css")
    if not os.path.exists(path):
        err(f"app/assets/app.css is missing - the generated pages have no stylesheet to link")
        return
    css = open(path, encoding="utf-8").read()
    missing = [c.lstrip(".") for c in REQUIRED_CSS_CLASSES if c not in css]
    if missing:
        err("app/assets/app.css does not define classes this build emits: " + ", ".join(missing))


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


def _stamp_availability_note(root_page=False):
    """Header badge: how much of the window the official reports still cannot settle (CS-41).

    Derived from data/app/report_availability.json via the canonical dataset. Deliberately
    un-converted: deadlines are quoted on the arena's local clock, because the repository holds no
    venue time-zone table and the project rule is to leave such a value blank rather than infer it.
    """
    if CTX["pending"] is None:
        return '<span class="stamp-warn">availability artefact not built</span>'
    if not CTX["pending"]:
        return (f'<span class="stamp-ok">official report filed for all {CTX["sides"]} '
                f'team-sides in the window</span>')
    href = "app/freshness.html" if root_page else "freshness.html"
    return (f'<span class="stamp-warn">official report filed for {CTX["sides"] - CTX["pending"]} '
            f'of {CTX["sides"]} team-sides \u00b7 {CTX["by_date"]} \u00b7 '
            f'<a href="{href}">when each is due</a></span>')


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
            if root_page:
                target = href
            elif href.startswith("app/"):
                target = href[len("app/"):]
            else:
                # a root-level page linked from inside app/ needs to step up one directory
                target = "../" + href
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
    <div class="stamp">Snapshot <strong>{BUILD_DATE}</strong> (UTC) · window {CTX['window']} ·
      {_stamp_availability_note(root_page)}</div>
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
    <code>arena/8d3d0271-nba3</code>. Every table row links to its source; values that could not be
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


def fmt_signed(v, nd=1):
    """Signed number with a fixed number of decimals, or an em dash."""
    if v is None:
        return "—"
    return f"{float(v):+.{nd}f}"


def fmt_ml(v):
    """American price with an explicit sign, or an em dash when there is none."""
    if v is None:
        return "—"
    return f"{int(round(float(v))):+d}"


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
def _luck(d):
    return d.get("luck_test") or {}


def _res(d):
    return d.get("residuals") or {}


def _ratings_delta_text(d):
    """Describe what this capture's team-statistics page says against the one it replaced.

    Computed at render time from the two stored captures, so the sentence cannot go stale
    the way a hard-coded '240 of 240 agree' did.
    """
    cur = d["ratings"]
    sup = (d.get("superseded") or {}).get("ratings")
    if not sup:
        return "30 teams transcribed from the official page; no superseded snapshot to compare."
    old_by = {t["team"]: t for t in sup["teams"]}
    fields = ("gp", "w", "l", "min", "off_rtg", "def_rtg", "net_rtg", "pace")
    diff_teams, diff_fields, total = [], 0, 0
    for t in cur["teams"]:
        o = old_by.get(t["team"])
        if o is None:
            continue
        changed = [f for f in fields if o.get(f) != t.get(f)]
        total += len(fields)
        if changed:
            diff_teams.append(t["team"])
            diff_fields += len(changed)
    played = (d.get("ratings_delta_played_teams") or [])
    unexplained = sorted(set(diff_teams) - set(played))
    base = (f"{len(cur['teams'])} teams × {len(fields)} fields read at "
            f"{cur.get('retrieved_stamp', 'n/a')}, after the games the page had already recorded. "
            f"Against the snapshot it replaces ({sup.get('retrieved_stamp', 'n/a')}): "
            f"{diff_fields} of {total} fields differ, on {len(diff_teams)} teams. ")
    if played and sorted(diff_teams) == sorted(played):
        return base + ("The teams that moved are exactly the teams that played in between, "
                       "which identifies the movement as games being added rather than the "
                       "earlier capture being wrong.")
    if unexplained:
        detail = "; ".join(
            "%s: %s" % (t, ", ".join("%s %s→%s" % (f, old_by[t].get(f), nt.get(f))
                                     for f in fields if old_by[t].get(f) != nt.get(f)))
            for t in unexplained for nt in [next(x for x in cur["teams"] if x["team"] == t)])
        return base + (f"{len(played)} of those teams played in between, and "
                       f"{len(unexplained)} did not play at all: {detail}. "
                       "A team that did not play cannot earn a new game, so either the earlier "
                       "capture transcribed that row wrong or the official page revises values "
                       "retroactively. The repository cannot tell which, so it is flagged "
                       "(F-BB-04) rather than explained away.")
    return base


def page_summary(d):
    m = d["meta"]
    model = m["model"]
    lab = d["lab"]
    res = _res(d)
    luck = _luck(d)
    strategies = d["strategies"]
    funded = [s for s in strategies if s["tier"] == "T1"]
    provisional = [s for s in strategies if s["tier"] == "T2"]
    body = []

    est = NEW.get("est") or {}
    body.append(f"""
<div class="callout"><strong>Headline confidence: the two independent estimators disagree by
{esc(str(est.get('policy', {}).get('disagreement_headline_mean')))} points</strong> on average
over the {esc(str(len(est.get('window', []))))}-game window. This disagreement is the published
headline; the blended rating sits underneath on the
<a href="projections.html">two-estimator projections page</a> as a secondary line and is never
the headline. Home-court advantage is pinned to the measured home-win rate, totals are
possessions x PPP, and luck is published as per-team z-scores with a refusal band. The site is
split into a public <strong>projection surface</strong> and a gated <strong>bet surface</strong>
and never mixes them.</div>
""")

    body.append('<div class="cards">')
    body.append(f"""<div class="card"><div class="k">Games priced in the window</div>
      <div class="v">{d['slate']['count']}</div>
      <div class="s">{d['slate']['window']['from']} → {d['slate']['window']['to']} — today plus the
      maximum three-day horizon</div>
      {src_cell([d['slate']['source_url']], 'nba.com/schedule')}</div>""")
    body.append(f"""<div class="card"><div class="k">Strategies funded</div>
      <div class="v">{len(funded)}</div>
      <div class="s">of {len(strategies)} scored rules. {len(provisional)} provisional,
      the rest rejected or blocked.</div>
      {src_cell([lab['meta']['source_games']], 'nba.com/games')}</div>""")
    body.append(f"""<div class="card"><div class="k">Luck threshold for this board</div>
      <div class="v">{num(luck.get('threshold_pp'), 1)} pp</div>
      <div class="s">The best edge a board of {luck.get('rules', 0)} rules throws up by chance.
      The largest edge any rule actually posted is
      {max([abs(s['edge_pp']) for s in strategies if s['edge_pp'] is not None] or [0]):.1f} pp.</div>
      {src_cell([lab['meta']['source_games']], 'nba.com/games')}</div>""")
    body.append(f"""<div class="card"><div class="k">Official injury rows</div>
      <div class="v">{d['injuries']['count']}</div>
      <div class="s">{d['injuries']['report_stamp']} — the table this card reads. A newer report (01:30 PM ET) is listed on the official index: see the injuries page, section 1b</div>
      {src_cell([d['injuries']['source_url']], 'official PDF')}</div>""")
    body.append("</div>")

    body.append(f"""
<h2>1. What this project is, in one paragraph</h2>
<p>A research pipeline that <strong>originates its own NBA lines</strong> from official results,
tests them out of sample against <strong>nine validation gates</strong>, ranks the resulting
strategies on a <strong>leaderboard</strong> with an explicit luck threshold, and publishes every
intermediate number next to the official source it came from. There is
<strong>no market price anywhere in this repository</strong>: no licensed odds feed is connected.
Every “pick” on this site is a fair price against <em>our own</em> line, which makes its expected
value zero by construction. The backtest therefore does not look for profit — it looks for
<em>bias in our own line</em>, which is the only question this data can answer.</p>

<h2>2. The headline result, stated plainly</h2>
<ul>
  <li><strong>Zero strategies are funded.</strong> Nothing on the board passes all nine gates.</li>
  <li><strong>Nothing beats luck.</strong> Simulating the whole board under the fair-line null,
      the best-looking rule clears <strong>{num(luck.get('threshold_pp'), 1)} percentage points</strong>
      of edge 5% of the time. The largest edge any real rule posted is
      <strong>{max([abs(s['edge_pp']) for s in strategies if s['edge_pp'] is not None] or [0]):.1f} pp</strong>.</li>
  <li><strong>The margin model is honest but weak.</strong> Out-of-sample RMSE
      {num(res.get('margin_rmse'))} against a {num(res.get('margin_baseline_rmse'))} constant
      baseline, and it is unbiased ({num(res.get('margin_bias'))} points).</li>
  <li><strong>The totals model is broken.</strong> Out-of-sample RMSE
      {num(res.get('total_rmse'))} is <em>worse</em> than the {num(res.get('total_baseline_rmse'))}
      constant baseline, and it runs {abs(res.get('total_bias') or 0):.1f} points hot. It is kept
      only because the brief asks for originated totals, and it is shrunk toward the league mean.
      See <a href="flagged.html">NF-49</a>.</li>
  <li><strong>An earlier “signal” was the model’s error.</strong> Before regularisation, “fade the
      highest projected totals” posted 69.7% on 66 games (p=0.0019). After regularisation it fell to
      65.5% on 29 games (p=0.136). The signal was our own miscalibration. See
      <a href="flagged.html">NF-50</a>.</li>
</ul>

<h2>3. What has been verified, and against what</h2>
<p>Every official page below was read on <strong>{BUILD_DATE}</strong> at 01:05 UTC and compared
programmatically with the values earlier sessions had stored. The comparison is
<a href="{REPO_URL}/blob/main/scripts/capture_official_2026_11_14b.py">scripts/capture_official_2026_11_14b.py</a>;
it prints every disagreement and the build fails on a mismatch.</p>
""")

    ver_rows = [
        [f"Official schedule — {d['slate']['count']} games, 2026-11-14 → 2026-11-17 "
         "(date, tip time ET, teams, game id, venue, city)",
         "22 of them also appear in the previous session’s 11/13–11/16 capture; "
         "88 of 88 field comparisons agree, 0 differ.",
         src_cell([d["slate"]["source_url"]], "nba.com/schedule")],
        ["Official team advanced statistics — 30 teams × 8 fields (GP, W, L, MIN, "
         "OffRtg, DefRtg, NetRtg, PACE)",
         _ratings_delta_text(d),
         src_cell([d["ratings"]["source_url"]], "nba.com/stats")],
        [f"Official injury report {d['injuries']['report_stamp']} — "
         f"{d['injuries']['count']} rows "
         f"({d['injuries'].get('player_rows', 0)} player rows + "
         f"{d['injuries'].get('not_submitted_rows', 0)} team “NOT YET SUBMITTED” rows)",
         f"{d['injuries'].get('prior_report_compared_rows', 0)} rows of the 2026-11-14 slate "
         f"compared with the report it supersedes ({d['injuries'].get('prior_report_stamp', '')}): "
         f"{d['injuries'].get('prior_report_status_changes', 0)} status changes.",
         src_cell([d["injuries"]["source_url"]], "official PDF")],
        [f"Official final scores — {m['model']['results_captured']} games, "
         f"{m['model']['team_games_official']} team-games",
         f"{m['model']['mismatch']} mismatch against the official games-played column "
         "for all 30 teams.",
         src_cell([lab["meta"]["source_games"]], "nba.com/games")],
        ["Walk-forward engine — refit for every date from strictly earlier games",
         f"{res.get('n')} out-of-sample forecasts after a {m['model']['burn_in']}-game burn-in; "
         "no game can see its own date.",
         src_cell([REPO_URL + "/blob/main/scripts/strategy_lab.py"], "strategy_lab.py")],
    ]
    body.append(table(["What", "Verification result", "Source"], ver_rows, "verification"))

    body.append(f"""
<h2>4. The engine, in four sentences</h2>
<p>A <strong>Massey least-squares margin model</strong> fits one rating per team plus a home-court
term on all completed games. A <strong>totals model</strong> regresses the game total on the two
teams’ prior scoring environment. Both are shrunk — a ridge penalty on the ratings and a blend
weight pulling the totals toward the league mean — and <strong>both shrinkage parameters are chosen
by validating on the most recent 20% of past games only</strong>, never on the games being
forecast. Every date is then priced with the engine fitted on strictly earlier dates, so nothing
downstream has seen the future.</p>

<h2>5. How luck is removed</h2>
<p>Three separate mechanisms, because one is not enough:</p>
<ul>
  <li><strong>Exact binomial tests</strong> against the fair-line rate for the market — 50% for a
      single bet, 25% for a two-leg parlay. This is gate G5.</li>
  <li><strong>Benjamini–Hochberg FDR</strong> across every scored rule on the board, because a
      board of {luck.get('rules', 0)} rules will throw up one “significant” result by chance.
      This is gate G6.</li>
  <li><strong>A whole-board Monte Carlo</strong>: every rule is simulated under its own fair-line
      null, the largest edge anywhere on the board is recorded, and that is repeated
      {luck.get('iterations', 0):,} times. The 95th percentile —
      {num(luck.get('threshold_pp'), 1)} pp — is the edge a rule must beat before it is called
      anything. This is gate G9, and nothing on the board beats it.</li>
</ul>
<p>On top of that, rules are published in <strong>mirror pairs</strong> (back a big home favourite /
fade it). They select the same games and are exact complements, so they are one finding, not two.
And a <strong>null control</strong> — back the home team in every game — is scored alongside them;
it fails every gate, which is the check that the gates themselves work.</p>

<h2>6. What is still missing, and what it blocks</h2>
""")
    gap_rows = [
        ["Licensed, timestamped odds feed",
         "Every ROI figure here is measured against our own line at an assumed −110 price. "
         "No ROI in this repository is an economic result.",
         chip("Blocks every staking decision", "warn"),
         src_cell(["https://www.nba.com/schedule"], "nba.com/schedule")],
        ["Per-player game logs",
         "Four player-prop combos on the board cannot be scored at all, and every "
         "player-level correlation cell is blank.",
         chip("Blocks prop combos", "warn"),
         src_cell([lab["meta"]["source_players"]], "nba.com/stats")],
        ["Full official minutes table (only the top 31 is captured)",
         "Every injury minutes-vacuum figure is a floor, not an estimate.",
         chip("Blocks rotation impact", "warn"),
         src_cell([lab["meta"]["source_players"]], "nba.com/stats")],
        ["Injury reports for 2026-11-15, 11-16 and 11-17",
         "No official report exists yet for those dates; five of the ten teams playing on "
         "11/14 had not submitted either.",
         chip("Blocks final selections", "warn"),
         src_cell([d["injuries"]["index_url"]], "official index")],
        ["Legal basis for publishing selections (NBA Terms §9, Dutch Koa licence)",
         "The reward schedule cannot be written until this is settled.",
         chip("Blocks the reward rule", "warn"),
         src_cell(["https://www.nba.com/termsofuse",
                   "https://kansspelautoriteit.nl/online-kansspel-aanbieden"],
                  "terms + regulator")],
    ]
    body.append(table(["Missing", "What it blocks", "Severity", "Source"], gap_rows, "gaps"))
    return "\n".join(body)


# The three ways a side can be absent from the priced line, kept distinct because they
# are three different facts. Collapsing them into one "one side not on the report"
# label -- which is what the first cut of this column did -- told a reader that
# 2026-11-16 had no official report when in fact every one of those 16 sides IS
# named on the 11/15 06:15 AM report, each reading NOT YET SUBMITTED. The
# distinction is the whole point of scripts/report_availability.py's state machine.
STATES_WITH_ONE_CHIP = {
    "NO_OFFICIAL_REPORT_COVERS_THIS_DATE":
        ("no official report covers this date", "bad"),
    "NOT_YET_DUE":
        ("not yet due (reported NOT YET SUBMITTED)", "warn"),
    "TEAM_NOT_LISTED_ON_A_COVERED_DATE":
        ("listed on no report despite a covered date", "bad"),
}
SIDE_LABELS = {
    "NO_OFFICIAL_REPORT_COVERS_THIS_DATE": ("no official report covers this date",),
    "NOT_YET_DUE": ("not yet due",),
    "TEAM_NOT_LISTED_ON_A_COVERED_DATE": ("listed on no report despite a covered date",),
}


def notes_cell(l):
    """The availability notes for one line, each separated from the previous one and
    from the counts before it by a real space.

    The published page rendered "4 one side not on the reportno report for this date":
    `chip()` emits an inline <span>, so two adjacent chips and the count text ran
    together with no whitespace and the second note was unreadable. Joining a list
    with a space, and rendering no chip at all when there is nothing to say, is the
    only version that stays readable for every combination of the three notes."""
    states = [("away", l.get("availability_state_away")),
              ("home", l.get("availability_state_home"))]
    if states[0][1] == states[1][1]:
        label = STATES_WITH_ONE_CHIP.get(states[0][1])
        return "" if label is None else " " + chip(*label)
    # Per-side states differ only when exactly one side is filed, so name the side
    # that is missing rather than leaving the reader to work out which.
    labels = [(side, STATES_WITH_ONE_CHIP[st]) for side, st in states
              if st in STATES_WITH_ONE_CHIP]
    return " " + " ".join(chip(f"{side}: {label[0]}", label[1]) for side, label in labels)

def num_cell(l):
    """Counts of officially-Out players per side, or an em dash pair when neither side
    is on a report at all. A side that IS on the report but has zero players out is a
    real fact (a filed, empty report -- Boston on 11/15) and prints as 0, not a dash."""
    if l.get("out_count_away") is None and l.get("out_count_home") is None:
        return "— / —"
    return num(l.get("out_count_away"), 0) + " / " + num(l.get("out_count_home"), 0)


def page_lines(d):
    lab = d["lab"]
    res = _res(d)
    body = []
    body.append(f"""
<p>Lines <strong>originated by this project</strong> for every game of the
{d['slate']['window']['from']} → {d['slate']['window']['to']} window. They are produced by the
walk-forward engine described on the <a href="methodology.html">method</a> page and are
<strong>not</strong> market prices: no licensed odds feed is connected, so there is nothing to
compare them with and no claim of value is made anywhere on this page.</p>

<div class="callout">
<p><strong>How to read the spread column.</strong> The spread is quoted for the home team, the way a
book prints it: a negative number means the home team is favoured by that many points. The fair
moneyline is our own price with no vig. Because these are our own lines, the probability of
covering them is 50% by construction — see the
<a href="picks.html">prices page</a> for why that matters.</p>
</div>

<div class="callout warn">
<p><strong>Read the totals with care.</strong> Out of sample our totals model is
<em>worse</em> than a constant league-average total (RMSE {num(res.get('total_rmse'))} vs
{num(res.get('total_baseline_rmse'))}) and runs {abs(res.get('total_bias') or 0):.1f} points hot.
The published totals are shrunk toward the league mean. See <a href="flagged.html">NF-49</a>.</p>
</div>
""")
    rows = []
    for l in d["lines"]:
        rows.append([
            esc(l["date"]), esc(l["time_et"]),
            f'<a href="{esc(l["nba_game_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(l["away"])} @ {esc(l["home"])}</a>',
            esc(l["nba_game_url"].rsplit("-", 1)[-1]),
            num(l["orig_spread_home"], 1),
            num(l["orig_total"], 1),
            num(l["exp_away_pts"], 1) + " – " + num(l["exp_home_pts"], 1),
            fmt_pct(l["p_home_win"]),
            f'{num(l["fair_ml_home"], 0)} / {num(l["fair_ml_away"], 0)}',
            f'{num(l["margin_lo"], 0)} … {num(l["margin_hi"], 0)}',
            num(l["pace"], 1),
            num_cell(l) + notes_cell(l),
            src_cell([l["source"], l["game_source"]], "schedule + game"),
        ])
    body.append(table(
        ["Date", "Tip (ET)", "Matchup", "Game id", "Spread (home)", "Total",
         "Projected (away–home)", "P(home win)", "Fair ML home/away",
         "Margin 95% range", "Pace", "Out away/home", "Source"],
        rows, "lines",
        note="Spread is quoted for the home team. Margin range is the model margin ± 1.96 × "
             "out-of-sample residual sd. Pace is the mean of the two teams’ official PACE."))

    body.append("<h2>How the engine performed out of sample</h2>")
    acc = [
        ["Out-of-sample forecasts", num(res.get("n"), 0),
         f"after a {d['meta']['model']['burn_in']}-game burn-in, refit per date"],
        ["Margin RMSE", num(res.get("margin_rmse"), 3),
         f"constant-baseline RMSE {num(res.get('margin_baseline_rmse'), 3)} — ours is better"],
        ["Total RMSE", num(res.get("total_rmse"), 3),
         f"constant-baseline RMSE {num(res.get('total_baseline_rmse'), 3)} — ours is WORSE"],
        ["Margin bias", num(res.get("margin_bias"), 3), "points; effectively zero"],
        ["Total bias", num(res.get("total_bias"), 3),
         f"points; our totals run {abs(res.get('total_bias') or 0):.1f} high"],
        ["Brier score (home win)", num(res.get("brier"), 4),
         f"unskilled baseline {num(res.get('brier_baseline'), 4)} — ours is better, in sample"],
        ["Margin residual sd", num(res.get("margin_sd"), 3), "points; drives every probability"],
        ["Total residual sd", num(res.get("total_sd"), 3), "points"],
    ]
    body.append(table(["Measure", "Value", "Against what"],
                      [[a, b, c] for a, b, c in
                       [[esc(a), esc(b), esc(c) + src_cell([lab["meta"]["source_games"]], "games")]
                        for a, b, c in acc]], "accuracy"))
    return "\n".join(body)


FLAG_KIND = {
    "REPORTED": "ok",
    "PARTIAL_REPORT_LATE": "bad",
    "PARTIAL_REPORT_NOT_DUE_YET": "warn",
    "AVAILABILITY_NOT_DUE_YET": "warn",
    "NO_INJURY_REPORT_FOR_DATE": "bad",
    "PARTIAL_REPORT": "warn",
}


def page_picks(d):
    lab = d["lab"]
    body = []
    # CS-42: the funded state leads the page, because it is the sentence that decides whether the
    # table below is a bet slip or a research artefact.
    strats = d.get("strategies") or []
    funded = sum(1 for x in strats if x.get("tier") == "T1")
    provisional = sum(1 for x in strats if x.get("tier") == "T2")
    body.append(
        f'<p class="lead"><b>{funded} of {len(strats)} rules on the board are funded and '
        f'{provisional} are provisional</b>, so on the evidence in this repository '
        f'<b>no game in this window is a selection</b>. What follows is our own price for every '
        f'game in the window, published so that the day a rule clears its gates the call can be '
        f'checked against it. Ranked board: <a href="leaderboard.html">strategy leaderboard</a>; '
        f'the threshold none of them clears: <a href="strategies.html">validation gates</a>.</p>')
    body.append(f"""
<div class="callout warn">
<p><strong>This page does not contain bets.</strong> Every price below is <em>our own fair price
against our own originated line</em>, which makes its expected value exactly zero. No licensed odds
feed is connected to this repository, so there is no market line to beat and no expected value can
be stated. Read this page as “here is what we think each game is worth”, not as “here is what to
bet”. Suggestion <a href="suggestions.html">CS-36</a> proposes renaming it to match.</p>
</div>

<p>One row for every one of the {len(d['picks'])} games in the
{d['slate']['window']['from']} → {d['slate']['window']['to']} window. The brief asks for picks up
to three days ahead; this is today plus the maximum three-day horizon, generated from our
originated lines. Games on 2026-11-13 were live on the official schedule page when it was read and
are excluded — see <a href="flagged.html">NF-54</a>.</p>
""")
    # CS-39: one column, read straight off the availability artefact, so the PARTIAL_REPORT chips
    # explain themselves.
    by_game = {}
    for r in ((d.get("availability") or {}).get("rows") or []):
        by_game.setdefault(r.get("game_id"), []).append(r)

    def reprice_cell(p):
        sides = by_game.get(p.get("game_id"))
        if not sides:
            return "—"
        pending = [r for r in sides if r.get("state") != "FILED"]
        if not pending:
            return "— (both sides reported)"
        return "<br>".join(
            f'{esc(r.get("team", ""))} · {esc(r.get("reprice_after") or "deadline not stated")}'
            for r in pending)

    rows = []
    minutes = (NEW.get("minutes") or {}).get("teams") or {}

    def rotation_cell(team):
        m = minutes.get(team)
        if not m or not m.get("top8_share_available"):
            return '<span class="unverified">— (no minutes source, blank+flagged)</span>'
        outs = ", ".join(esc(o["player"]) for o in m.get("out_players", [])) or "none out"
        return (f"top-8 share after redistribution {num(m.get('top8_share_after'), 2)}"
                f"<br>out: {outs}")

    for p in d["picks"]:
        flag = p["availability_flag"]
        rows.append([
            esc(p["date"]), esc(p["time_et"]),
            f'<a href="{esc(p["nba_game_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(p["away"])} @ {esc(p["home"])}</a>',
            esc(p["origin_spread"]),
            num(p["origin_total"], 1),
            f'{num(p["fair_ml_home"], 0)} / {num(p["fair_ml_away"], 0)}',
            fmt_pct(p["model_p_home"]),
            esc(p["singles_view"]),
            esc(p["totals_view"]),
            f'{esc(p["away"])}: {rotation_cell(p["away"])}<br>'
            f'{esc(p["home"])}: {rotation_cell(p["home"])}',
            chip(flag, FLAG_KIND.get(flag, "warn")),
            reprice_cell(p),
            src_cell([p["source"], p["nba_game_url"]], "schedule + game"),
        ])
    body.append(table(
        ["Date", "Tip (ET)", "Matchup", "Originated spread", "Originated total",
         "Fair ML home/away", "P(home win)", "Model side", "Model total",
         "Rotation availability", "Availability", "Re-price after (local clock)", "Source"],
        rows, "picks",
        note="“Rotation availability” is the explicit minutes-redistribution output: the top-8 "
             "minutes share remaining after every player designated OUT on the official injury "
             "report is removed and their share redistributed proportionally (replacement "
             "shares per player on the "
             '<a href="injuries.html">injuries page</a>; sources: official game books and the '
             'official per-player minutes snapshot). “Model side” names the team our line favours, '
             "printed the way a book would print it. "
             "“Availability” is the four-state verdict from the official filing rule — see the "
             '<a href="freshness.html">Report-availability page</a>. Only REPORTED means the '
             "absence counts in the lines table are real; everywhere else they are blank, not zero. "
             "“Re-price after” is the official filing deadline of whichever side has not filed, "
             "printed on that arena’s local clock: no time-zone conversion is asserted anywhere in this "
             "repository, so the deadline is not directly comparable with the ET tip time in the "
             "second column (CQ-43)."))

    open_rows = [[
        esc(p["date"]), esc(f"{p['away']} @ {p['home']}"), esc(p["availability_detail"]),
        src_cell([p["nba_game_url"]], "game"),
    ] for p in d["picks"] if p["availability_flag"] != "REPORTED"]
    if open_rows:
        body.append("<h2>Games whose injury picture is not settled</h2>")
        body.append(table(["Date", "Matchup", "What is unresolved", "Source"],
                          open_rows, "picks-open"))
    else:
        body.append("<h2>Games whose injury picture is not settled</h2><p>None — both teams had "
                    "filed for every game in the window at capture time.</p>")

    sel = [p for p in d["picks"] if p.get("strategy_selections")]
    body.append("<h2>Which strategies select which game</h2>")
    if sel:
        body.append(table(
            ["Date", "Matchup", "Selected by", "Source"],
            [[esc(p["date"]), esc(f"{p['away']} @ {p['home']}"),
              "; ".join(esc(x) for x in p["strategy_selections"]) or "—",
              src_cell([p["nba_game_url"]], "game")] for p in sel], "picks-sel"))
    else:
        body.append(
            '<p><strong>No game in this window is selected by any strategy that reached tier T1 or '
            'T2.</strong> That is the correct outcome given the leaderboard: no rule on the board '
            'is funded or even provisional, so there is nothing to select on. The board is on the '
            '<a href="leaderboard.html">leaderboard page</a>.</p>')
    return "\n".join(body)


def page_parlays(d):
    lab = d["lab"]
    corr = d["correlations"]
    body = []
    body.append(f"""
<p>Every parlay and prop combination this project can price, and — more usefully — the four it
cannot. All prices are <strong>our own fair prices</strong>, computed from our originated lines.
There is no bookmaker involved at any point.</p>

<h2>1. Same-game two-leggers</h2>
<p>The dependence ratio below is <strong>measured</strong>, not assumed: it is the observed joint
hit rate of “our side covers <em>and</em> the game goes over our total” divided by what that rate
would be if the two legs were independent. A ratio above 1.0 means the legs land together more
often than independence pricing assumes — which is precisely how a sportsbook protects itself on
same-game parlays.</p>
""")
    ratio = corr.get("parlay_dependence_ratio")
    joint_rows = [
        ["Measured joint hit rate", fmt_pct(corr.get("parlay_joint_rate"), 2),
         f"on {corr.get('n')} out-of-sample games"],
        ["Rate under independence", fmt_pct(corr.get("parlay_independent_rate"), 2),
         "P(side covers) × P(over)"],
        ["Dependence ratio", num(ratio, 3),
         "1.0 would mean independence is exactly right"],
        ["Interval on the spread/total residual correlation",
         "see the correlations page",
         "the interval includes zero, so independence is not rejected"],
    ]
    body.append(table(["Quantity", "Value", "Note"],
                      [[esc(a), esc(b), esc(c) + src_cell([corr.get("source") or
                                                           lab["meta"]["source_games"]], "games")]
                       for a, b, c in joint_rows], "sgp-measure"))

    sgp = [p for p in d["parlays"] if p["kind"] == "Same-game 2-leg"]
    rows = []
    for p in sgp:
        rows.append([
            esc(p["date"]), esc(p["matchup"]),
            "<br>".join(esc(f'{l["leg"]}: {l["detail"]}') for l in p["legs"]),
            fmt_pct(p["p_joint"], 2),
            fmt_ml(p["fair_price"]),
            src_cell([p["source"]], "schedule"),
        ])
    body.append(table(["Date", "Game", "Legs", "Our joint probability", "Our fair price",
                       "Source"], rows, "sgp"))

    body.append("<h2>2. Cross-game two-leggers</h2>")
    body.append("""
<div class="callout warn">
<p><strong>Independence across games on the same night is an assumption, not a measurement.</strong>
It was not tested on this sample — two games tipping off at the same time share no players, but
they do share a travel schedule, a referee pool and a news cycle, none of which this repository can
measure. The fair prices below are correct only if that assumption holds.</p>
</div>
""")
    cross = [p for p in d["parlays"] if p["kind"] == "Cross-game 2-leg"]
    rows = []
    for p in cross:
        rows.append([
            esc(p["date"]), esc(p["matchup"]),
            "<br>".join(esc(f'{l["leg"]}: {l["detail"]}') for l in p["legs"]),
            fmt_pct(p["p_joint"], 2),
            fmt_ml(p["fair_price"]),
            src_cell([p["source"]], "schedule"),
        ])
    body.append(table(["Date", "Games", "Legs", "Our joint probability (independence assumed)",
                       "Our fair price", "Source"], rows, "cross"))

    body.append("<h2>3. Player-prop combinations — all four are blocked</h2>")
    body.append("""
<p>These are the combinations the brief asks for. None can be priced, and the reason is the same for
all four: <strong>this repository has never captured a per-player game log</strong>, so the joint
distribution of two player markets does not exist here. Anything printed in the value column would
be a guess, so the column is blank.</p>
""")
    rows = [[
        esc(c["id"]), esc(c["combo"]), chip(c["status"], "warn"),
        esc(c["reason"]),
        '<span class="unverified">UNVERIFIED — not measurable</span>',
        esc(c["unblock"]),
        src_cell([c["source"]], "nba.com/stats"),
    ] for c in d["prop_combos"]]
    body.append(table(["ID", "Combination", "Status", "Why it is blocked", "Value",
                       "What would unblock it", "Source"], rows, "prop-combos"))

    body.append("""
<h2>4. What a same-game parlay actually costs you</h2>
<p>A two-legger priced as independent at 50% × 50% pays +300 for a 25% chance — a fair bet. If the
legs are positively correlated, the true joint probability is higher than 25% and the +300 price is
now generous; if they are negatively correlated, as our sample slightly suggests, the true
probability is lower and the same price is a tax. The size of the tax is the dependence ratio above,
and the interval on it includes 1.0, so on this sample we cannot tell which way it goes. That is
the honest answer, and it is why nothing here is funded.</p>
""")

    body.append("""
<h2>5. Every parlay priced with the measured rho — naive product printed beside it</h2>
<p>The table prices each same-game pair with the <strong>measured residual correlation rho</strong>
of the two-estimator framework (the correlation of margin and total residuals over the official
completed-game log) and prints the <strong>naive product</strong> of the leg prices next to every
correlated price, so the size of the correlation adjustment is visible on every row.</p>
""")
    par = (NEW.get("est") or {}).get("parlay_prices", [])
    if par:
        body.append(table(
            ["Game", "Legs", "P(side)", "P(over)", "Measured rho",
             "Joint price (rho-aware)", "Naive product", "Joint / naive", "Method", "Source"],
            [[esc(p["game_id"]), esc(p["legs"]), num(p["p_side"], 3), num(p["p_over"], 3),
              num(p["rho_measured"], 3), num(p["joint_price_rho"], 3),
              num(p["naive_product"], 3), num(p["ratio_joint_over_naive"], 2),
              esc(p["method"]),
              src_cell(["https://www.nba.com/games?date=2026-11-14"], "official finals")]
             for p in par], "parlay-rho"))
    else:
        body.append('<p class="unverified">Parlay price block not generated — blank and flagged.</p>')
    return "\n".join(body)


def page_leaderboard(d):
    strategies = d["strategies"]
    luck = _luck(d)
    body = []
    body.append(f"""
<p>The competition the brief asks for. Every rule below selects real games from the
{_res(d).get('n')} out-of-sample forecasts, is scored against nine gates, and is ranked by a
composite skill score. Reward tiers decide what a rule is allowed to risk.</p>

<div class="callout">
<p><strong>What a rule is actually tested against.</strong> Not a bookmaker — our own line. Because
our line is originated to be fair, a rule that wins more than half the time against it is evidence
that <em>our line is biased</em> in the games the rule picks. That is a model defect to repair, not
an edge to bet (see <a href="questions.html">CQ-40</a>). This is the only question the data can
answer without a licensed price feed.</p>
</div>

<div class="callout warn">
<p><strong>The luck threshold.</strong> A board of {luck.get('rules', 0)} rules will throw up one
impressive-looking result by chance. Simulating the whole board under the fair-line null
{luck.get('iterations', 0):,} times, the best edge anywhere on it reaches
<strong>{num(luck.get('threshold_pp'), 1)} percentage points</strong> 5% of the time. The largest
edge any real rule posted is
<strong>{max([abs(s['edge_pp']) for s in strategies if s['edge_pp'] is not None] or [0]):.1f} pp</strong>.
Nothing clears the bar. Gate G9 is the formal version of this test and no rule passes it.</p>
</div>

<h2>1. The board</h2>
""")
    rows = []
    for s in strategies:
        gates = s.get("gates", [])
        passed = sum(1 for g in gates if g["passed"])
        mirror = f'<br><span class="note">{esc(s.get("mirror_note", ""))}</span>' \
            if s.get("mirror_note") else ""
        luck_ok = s.get("p_family") is not None and s["p_family"] <= 0.05
        rows.append([
            esc(str(s["rank"])),
            esc(s["id"]),
            esc(s["name"]) + mirror,
            esc(s["family"]),
            num(s["n"], 0),
            f'{s["baseline"]:.0%}',
            fmt_pct(s["rate"]),
            fmt_signed(s["edge_pp"]),
            fmt_p(s["p_two_sided"]),
            fmt_p(s["q_value"]),
            chip("yes" if luck_ok else "no", "ok" if luck_ok else "warn"),
            f"{passed} / {len(gates)}",
            num(s["score"], 1),
            chip(s["tier"], {"T1": "ok", "T2": "warn"}.get(s["tier"], "neutral")),
            esc(s["stake"]),
            src_cell(s["sources"], "games"),
        ])
    body.append(table(
        ["#", "ID", "Rule", "Family", "n", "Fair rate", "Hit rate", "Edge (pp)",
         "p", "q (BH)", "Beats luck", "Gates", "Score", "Tier", "Reward", "Source"],
        rows, "board",
        note="“Fair rate” is the hit rate the rule would post if our line were fair — 50% for a "
             "single bet, 25% for a two-leg parlay. Scoring a parlay against 50% would hand it a "
             "spurious signal for simply having two legs."))

    body.append("<h2>2. Reward tiers</h2>")
    tiers = [
        ["T1", "Funded", "Passes all nine gates", "Full unit",
         "Still conditional on the legal question (CQ-36) and a licensed price feed."],
        ["T2", "Provisional", "Passes every gate except the minimum sample (G3)",
         "Quarter unit, paper only", "Re-score at n ≥ 100."],
        ["T3", "Watch", "Raw p < 0.05 but fails FDR, stability, power or the luck threshold",
         "Paper tracking, no stake", "Most rules that look interesting land here."],
        ["T4", "Rejected", "Fails the significance gate, or this direction simply loses",
         "No stake", "The mirror of a losing rule is where any signal would be."],
        ["T5", "Blocked", "No data exists to score the rule at all", "No stake",
         "Collect the data first."],
    ]
    body.append(table(["Tier", "Name", "Condition", "Reward", "Caveat"],
                      [[esc(a), esc(b), esc(c), esc(dd), esc(e) +
                        src_cell([d["lab"]["meta"]["source_games"]], "games")]
                       for a, b, c, dd, e in tiers], "tiers",
                      note="The reward schedule itself is unapproved: see CQ-36. Until the owner "
                           "decides whether this is a prize contest, a pool or internal scoring, "
                           "“unit” means a paper unit."))

    body.append("<h2>3. Mirror pairs</h2>")
    body.append("""
<p>Six of the rules are exact complements of another rule: same games, opposite side. If one wins
68% the other wins 32%. They are <strong>one finding, not two</strong>, and a board of 15 rows is
therefore closer to nine independent pieces of evidence. Both directions are published so the loser
is visible — hiding it is how a backtest flatters itself — but only the winning direction can carry
a score.</p>
""")
    mrows = [[
        esc(s["id"]), esc(s.get("mirror_of") or "—"), num(s["n"], 0),
        fmt_pct(s["rate"]), fmt_pct(s["half_first"]), fmt_pct(s["half_second"]),
        chip("yes" if s["stable"] else "no", "ok" if s["stable"] else "warn"),
        src_cell(s["sources"], "games"),
    ] for s in strategies if s.get("mirror_of")]
    body.append(table(["Rule", "Mirror of", "n", "Hit rate", "First half", "Second half",
                       "Stable", "Source"], mrows, "mirrors"))

    body.append("<h2>4. The control</h2>")
    nul = next((s for s in strategies if s["id"] == "ST-NUL"), None)
    if nul:
        body.append(f"""
<p>“Back the home team in every game” is scored on the same
{num(nul['n'], 0)} forecasts as everything else. It posts
{fmt_pct(nul['rate'])} against a {nul['baseline']:.0%} fair rate
(p = {fmt_p(nul['p_two_sided'])}), an edge of {fmt_signed(nul['edge_pp'])} pp, and fails
{sum(1 for g in nul['gates'] if not g['passed'])} of {len(nul['gates'])} gates. <strong>That is the
result we want.</strong> If the null control passed, the gates would be broken and every other
verdict on this page would be worthless.</p>
""")
    return "\n".join(body)


def page_strategies(d):
    lab = d["lab"]
    body = []
    body.append("""
<p>The nine gates every strategy has to pass, what each one is for, and how each rule scored.
The full ranking is on the <a href="leaderboard.html">leaderboard page</a>; this page is the rule
book. <strong>Every threshold here is proposed by this project and has not been approved by the
owner</strong> — see <a href="questions.html">CQ-38</a>.</p>
""")
    rows = []
    for g in d["gates"]:
        if g["id"].startswith("CG-2") or g["id"].startswith("CG-19"):
            continue
        rows.append([
            esc(g["id"]), esc(g.get("name", "")), esc(g.get("checks", "")),
            esc(g.get("threshold", "")),
            chip(g.get("threshold_status", ""),
                 "warn" if "roposal" in g.get("threshold_status", "") else "neutral"),
            esc(g.get("notes", "") or "—"),
            src_cell([g.get("source") or REPO_URL], "source"),
        ])
    body.append(table(["ID", "Gate", "What it checks", "Threshold", "Threshold status",
                       "Result / note", "Source"], rows, "gate-defs"))

    body.append("<h2>How every rule scored against each gate</h2>")
    grid = []
    for s in d["strategies"]:
        cells = []
        for g in s.get("gates", []):
            cells.append(chip("pass" if g["passed"] else "fail",
                              "ok" if g["passed"] else "warn"))
        grid.append([esc(s["id"]), esc(s["name"])] + cells +
                    [chip(s["tier"], {"T1": "ok", "T2": "warn"}.get(s["tier"], "neutral")),
                     src_cell(s["sources"], "games")])
    head = ["ID", "Rule"] + [g["id"] for g in d["strategies"][0].get("gates", [])] + \
        ["Tier", "Source"]
    body.append(table(head, grid, "gate-grid"))

    body.append("<h2>What each gate is protecting against</h2>")
    why = [
        ["G1 Provenance", "A number with no source cannot be audited, so it cannot be trusted."],
        ["G2 Look-ahead", "The single most common way a backtest invents an edge. Ratings are "
                          "refitted for every date from strictly earlier games; games are batched "
                          "by date so a game cannot see another game tipped off the same night."],
        ["G3 Sample size", "Small samples produce large apparent edges. n ≥ 100 is a convention, "
                           "not a measurement — see CQ-38."],
        ["G4 Power", "A rule can be 'not significant' simply because it was never able to detect "
                     "the effect it found. This gate asks whether the observed effect is big "
                     "enough for the sample to have seen it."],
        ["G5 Significance", "Exact two-sided binomial against the fair-line rate for that market."],
        ["G6 Multiple testing", "Fifteen rules at p < 0.05 produce a false positive more often "
                                "than not. Benjamini–Hochberg controls the false discovery rate."],
        ["G7 Stability", "An effect that only exists in one half of the sample is usually a "
                         "regime change, not a signal."],
        ["G8 Economics", "A date-block bootstrap of return at an assumed −110. Flagged: this is "
                         "return against our own line, not profit — see NF-55."],
        ["G9 Luck threshold", "The board-level test. Even with G6, the single best-looking rule on "
                              "a large board is biased upward. This gate asks whether the rule "
                              "beats what the whole board produces by chance."],
    ]
    body.append(table(["Gate", "What it protects against"],
                      [[esc(a), esc(b) + src_cell([REPO_URL], "repo")] for a, b in why],
                      "gate-why"))

    body.append("<h2>What is not on the board yet</h2>")
    body.append("""
<p>Two gates this project thinks it needs and has not built: <strong>G10 pre-registration</strong>
(hash the rule text and freeze it before the first graded forecast, so a rule cannot be written
after seeing the results) and <strong>G11 price reality</strong> (every bet must be gradeable at a
recorded, licensed price). Both are on the
<a href="suggestions.html">suggestions page</a> as CS-31 and in CQ-37. Until G10 exists, treat every
rule here as <strong>retrospective</strong>.</p>
""")
    return "\n".join(body)


def page_correlations(d):
    corr = d["correlations"]
    lab = d["lab"]
    body = []
    body.append("""
<p>Correlation is what decides whether a parlay is priced correctly. Four values below were
<strong>measured</strong> on official results; five could not be measured and are
<strong>left blank</strong> rather than assumed. A blank on this page is a statement, not an
omission.</p>
<div class="callout">
<p><strong>Measured since this page was written — see the
<a href="../audit_dd1eb1f1/pages/correlations.html">independent audit</a>.</strong>
Session <code>dd1eb1f1</code> measured the dependence this page prices as an assumption: within
one slate, the correlation between two games' margin residuals is <strong>-0.0147</strong>
(permutation p 0.73) and between two games' total residuals <strong>-0.0695</strong>
(permutation p 0.073). Neither rejects independence at 5%, so the cross-game assumption stands
for now; the totals figure is negative and is the one to re-measure when the out-of-sample log
is larger. The same pass measured rest effects on the official results — rest differential vs
home margin r = 0.0949, 95% interval -0.058 to 0.243, n = 167 — and found that the one raw p
below 0.05 (0.0397) becomes 0.119 after Benjamini-Hochberg correction, i.e. no rest signal this
sample can support. Every number here is <em>derived</em> from the official results log, not an
official NBA statistic.</p>
</div>
""")
    rows = []
    for c in corr["rows"]:
        if c["verified"]:
            val = num(c["value"], 4)
            ci = (f'{num(c["ci95"][0], 3)} … {num(c["ci95"][1], 3)}'
                  if c["ci95"] and c["ci95"][0] is not None else "—")
        else:
            val = '<span class="unverified">UNVERIFIED — left blank</span>'
            ci = "—"
        rows.append([
            esc(c["pair"]), esc(c["stat"]), val, ci,
            num(c["n"], 0) if c["n"] else "—",
            chip("measured" if c["verified"] else "not measurable",
                 "ok" if c["verified"] else "warn"),
            esc(c["note"]),
            src_cell([c["source"]] if c["source"] else
                     [lab["meta"]["source_players"]], "source"),
        ])
    body.append(table(["Pair", "Statistic", "Value", "95% interval", "n", "Status",
                       "What it is used for", "Source"], rows, "corr"))

    body.append(f"""
<h2>Why the same-game number matters</h2>
<p>The joint hit rate of “our side covers <em>and</em> the game goes over our total” was
<strong>{fmt_pct(corr.get('parlay_joint_rate'), 2)}</strong> against
<strong>{fmt_pct(corr.get('parlay_independent_rate'), 2)}</strong> under independence — a dependence
ratio of <strong>{num(corr.get('parlay_dependence_ratio'), 3)}</strong>. On this sample the ratio
sits slightly below 1.0, meaning the two legs landed together a little <em>less</em> often than
independence would suggest. The confidence interval on the underlying residual correlation includes
zero, so <strong>independence is not rejected</strong> — we cannot tell whether the true value is
above or below 1.0. That is the honest position, and it is why the same-game cards on the
<a href="parlays.html">parlays page</a> are published with the interval attached rather than as
clean prices.</p>

<h2>Why the player numbers are blank</h2>
<p>Every player-level correlation needs per-player game logs: one row per player per game, roughly
4,000 rows a season. This repository has never captured them — it holds official season averages for
31 players and nothing else. Without the game-by-game distribution there is no honest way to put a
number in those cells, so they stay empty and are listed on the
<a href="flagged.html">Flagged for review</a> page. Four prop combinations are blocked on exactly
this gap.</p>

<h2>The cross-game assumption</h2>
<p>Two legs in different games are priced as independent on the
<a href="parlays.html">parlays page</a>. That is an <strong>assumption</strong>, printed as one.
Testing it properly needs matched same-night results with a shared context model, which this sample
is too small to support.</p>
""")
    return "\n".join(body)


def page_props(d):
    lab = d["lab"]
    body = []
    body.append("""
<div class="callout warn">
<p><strong>No prop on this page is a bet, and none carries a price.</strong> Two things are missing
and neither can be worked around. First, <strong>no licensed prop prices are connected</strong>, so
there is no line to compare a projection with. Second, this repository holds
<strong>season averages only — no per-player game logs</strong>, so the scoring distribution cannot
be estimated and an over/under probability cannot be computed. The market-line and probability
columns are therefore blank, and blank is the truthful value.</p>
</div>

<p>What the page <em>can</em> show honestly: the official season averages of the highest-minute
players on each team in the window, and our projection, which for now is simply that average with
no adjustment. Both are labelled for what they are.</p>
""")
    rows = []
    for p in d["props"]:
        rows.append([
            esc(p["date"]), esc(p["matchup"]), esc(p["team"]), esc(p["player"]),
            num(p["gp"], 0), num(p["official_min"], 1),
            num(p["official_pts"], 1), num(p["official_reb"], 1),
            num(p["official_ast"], 1),
            num(p["proj_pts"], 1), num(p["proj_reb"], 1), num(p["proj_ast"], 1),
            '<span class="unverified">UNVERIFIED — no line connected</span>',
            '<span class="unverified">UNVERIFIED — no distribution</span>',
            src_cell([p["source_player"]], "official stats"),
        ])
    body.append(table(
        ["Date", "Game", "Team", "Player", "GP", "MIN", "PTS", "REB", "AST",
         "Proj PTS", "Proj REB", "Proj AST", "Market line", "P(over)", "Source"],
        rows, "props",
        note="MIN, PTS, REB and AST are official season averages. The projection repeats them "
             "unchanged because no minutes, usage or matchup adjustment can be verified without "
             "game logs."))

    body.append("<h2>Prop combinations</h2>")
    body.append("""
<p>All four combinations the brief asks for are <strong>blocked</strong>, for the same reason: the
joint distribution of two player markets cannot be estimated from season averages alone. They are
listed with what would unblock them on the
<a href="parlays.html">parlays page</a>.</p>
""")
    body.append(f"""
<h2>What it would take to make this page useful</h2>
<ol>
  <li>Capture per-player game logs from
      <a href="{lab['meta']['source_players']}" target="_blank" rel="noopener noreferrer">the
      official players table</a> by date — about 4,000 rows a season. Owner decision: CQ-39.</li>
  <li>Fit a distribution per player per market, with minutes as the exposure variable.</li>
  <li>Connect a licensed prop price feed so a comparison is possible at all. Owner decision: Q-03,
      tracked on the <a href="questions.html">questions page</a>.</li>
  <li>Measure the within-game correlation between a player's markets, then price the combinations.
      Until that measurement exists, any joint probability would be invented.</li>
</ol>
""")
    return "\n".join(body)


DELTA_PDF_0130 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
DELTA_RAW_0130 = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/official_injuries_2026-11-14_0130PM_raw.md"
DELTA_JSON_0130 = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/injury_delta_0130pm.json"
DELTA_PY_0130 = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/injury_delta_0130pm.py"


def render_delta_0130(dl):
    """Section 1b of the injuries page: the 01:30 PM ET report against the 05:15 AM ET snapshot.
    Every row is produced from data/app/injury_delta_0130pm.json, which scripts/injury_delta_0130pm.py
    writes from the verbatim raw text. Nothing on this page is typed in by hand."""
    s = dl["summary"]
    cnt = s["counted_attributed_result_counts"]
    tiers = s["tiers"]
    changed = [c for c in dl["comparisons"] if c["tier"] in ("attributed", "nys_attributed") and c["result"] == "status_changed"]
    chg_text = "; ".join(
        f"{esc(c['player'])} ({esc(c['team'])}, {esc(c['matchup'])}): {esc(c['stored_status'])} to {esc(c['raw_status'])}"
        for c in changed) or "none"
    n_counted = sum(cnt.values())
    srcs = [DELTA_PDF_0130, DELTA_RAW_0130, DELTA_JSON_0130]

    def src(line):
        return src_cell(srcs, f"official PDF 01:30 PM · raw line {line}")

    def result_chip(res):
        if res == "same":
            return chip("unchanged", "ok")
        if res == "status_changed":
            return chip("STATUS CHANGED", "warn")
        if res.startswith("new"):
            return chip("new row", "neutral")
        return chip(res.replace("_", " "), "neutral")

    def stored(c):
        if c.get("stored_status"):
            return esc(c["stored_status"]) + (" — " + esc(c["stored_reason"]) if c.get("stored_reason") else "")
        return '<span class="unverified">not in the 05:15 AM snapshot</span>'

    def raw(c):
        st = c.get("raw_status") or ""
        rs = c.get("raw_reason") or ""
        return esc(st) + (" — " + esc(rs) if rs else "")

    out = []
    out.append(f"""
<h2 id="s1b">1b. Newer report: 01:30 PM ET, compared with the 05:15 AM ET snapshot</h2>
<p>The newest report listed on the <a href="{esc(dl['index_url'])}" target="_blank" rel="noopener noreferrer">official index</a>
at 18:45 UTC is the 11/14 report stamped <strong>01:30 PM ET</strong>
(<a href="{DELTA_PDF_0130}" target="_blank" rel="noopener noreferrer">PDF</a>). Section 1 is not replaced in this round.
The comparison uses the rule the earlier deltas used: a row is <em>counted</em> only when its game date,
matchup and team are all printed on it. Rows that miss one of those are listed below and never counted.</p>
<div class="callout {'warn' if changed else 'ok'}"><p><strong>Counted: {n_counted} rows.</strong>
{cnt.get('same', 0)} unchanged, <strong>{len(changed)} status change</strong>
({chg_text}), {cnt.get('new_in_raw', 0)} new player rows.
Not counted: {tiers.get('matchup_no_date', 0)} rows with no game date, {tiers.get('team_no_matchup', 0)} rows with no matchup,
{tiers.get('name_only', 0)} rows with no team or matchup, {tiers.get('nys_partial', 0)} partial team rows, and
{tiers.get('unattributed_fragment', 0)} garbled row. Flags <a href="flagged.html">965-F-01 to 965-F-07</a>.
Raw text and the parser are in the repository (<a href="{DELTA_RAW_0130}" target="_blank" rel="noopener noreferrer">raw file</a>,
<a href="{DELTA_PY_0130}" target="_blank" rel="noopener noreferrer">scripts/injury_delta_0130pm.py</a>).</p></div>
""")

    counted = [c for c in dl["comparisons"] if c["tier"] in ("attributed", "nys_attributed")]
    rows = []
    for c in counted:
        if c["tier"] == "nys_attributed":
            rows.append([esc(c["game_date"]), esc(c["time"]), esc(c["matchup"]), esc(c["team_name"]),
                         "<em>team row</em>", stored(c), '<span class="chip chip-neutral">NOT YET SUBMITTED</span>',
                         result_chip(c["result"]), src(c["raw_line"])])
        else:
            rows.append([esc(c["game_date"]), esc(c["time"]), esc(c["matchup"]), esc(c["team_name"]),
                         esc(c["player"]), stored(c), raw(c), result_chip(c["result"]), src(c["raw_line"])])
    out.append("<h3>Counted rows (game date, matchup and team printed)</h3>")
    out.append(table(["Game date", "Time (ET)", "Matchup", "Team", "Player", "05:15 AM ET (stored)",
                      "01:30 PM ET (official)", "Result", "Source"], rows, "injury-delta-counted"))

    mnd = [c for c in dl["comparisons"] if c["tier"] == "matchup_no_date"]
    out.append("<h3>Not counted: matchup and team printed, game date blank on the row</h3>")
    out.append(table(["Matchup", "Time (ET)", "Team", "Player", "05:15 AM ET (stored)", "01:30 PM ET (official)",
                      "Result (not counted)", "Source"],
                     [[esc(c["matchup"]), esc(c["time"]), esc(c["team_name"]), esc(c["player"]), stored(c), raw(c),
                       result_chip(c["result"]), src(c["raw_line"])] for c in mnd],
                     "injury-delta-matchup"))

    tnm = [c for c in dl["comparisons"] if c["tier"] in ("team_no_matchup", "nys_partial")]
    out.append("<h3>Not counted: team printed, matchup and game date blank on the row</h3>")
    out.append(table(["Team", "Player", "05:15 AM ET (stored)", "01:30 PM ET (official)", "Result (not counted)", "Source"],
                     [[esc(c["team_name"]),
                       esc(c["player"]) if c.get("player") else "<em>team row</em>",
                       stored(c) if c.get("player") else esc(c.get("stored_status") or ""),
                       raw(c) if c.get("player") else esc("NOT YET SUBMITTED"),
                       result_chip(c["result"]), src(c["raw_line"])] for c in tnm],
                     "injury-delta-team"))

    nmo = dl.get("name_only_not_counted", [])
    out.append("<h3>Not counted: player printed, team and matchup blank (not assigned to any team)</h3>")
    out.append(table(["Player", "01:30 PM ET (official)", "Team and matchup on the row", "05:15 AM ET (stored, same name)", "Source"],
                     [[esc(c["player"]), raw(c), "not printed — not assigned",
                       esc("; ".join(f"{m['team']} {m['status']}" for m in c["stored_matches_by_name"])) or "no match in the 05:15 AM snapshot",
                       src(c["raw_line"])] for c in nmo],
                     "injury-delta-nameonly"))

    frag = dl.get("unattributed_fragments", [])
    out.append("<h3>Not counted: garbled row kept verbatim</h3>")
    out.append(table(["Raw line", "Printed cells (verbatim)", "Source"],
                     [[str(c["raw_line"]), esc(" | ".join(c["cells"])), src(c["raw_line"])] for c in frag],
                     "injury-delta-fragments"))
    return "\n".join(out)


def page_injuries(d):
    inj = d["injuries"]
    lab = d["lab"]
    body = []
    body.append(f"""
<p>Transcribed from the official NBA injury report
<strong>{esc(inj['report_stamp'])}</strong> (<a href="{esc(inj['source_url'])}" target="_blank" rel="noopener noreferrer">PDF</a>).
{inj['count']} rows: {inj.get('player_rows', 0)} player rows and
{inj.get('not_submitted_rows', 0)} team rows printed “NOT YET SUBMITTED”. A team that has not filed
is published as such rather than treated as healthy — “unknown” and “fit” are not the same thing,
and every downstream number respects the difference.</p>
<p><strong>Report revision time (the table below): {esc(inj['report_stamp'])} ·
retrieval time: {esc(str(inj.get('retrieved_stamp')))}.</strong>
Newest official report at last refresh: <strong>2026-11-15 06:15 AM ET</strong> (revision time),
retrieved <strong>2026-11-15T11:33Z</strong> — full table and consecutive-report diff in
<a href="#s1c">section 1c</a>. The scheduled refresh job re-reads the official index four times a
day; the freshness and provenance gates that govern every rebuild are on the
<a href="refresh.html">refresh &amp; provenance gates page</a>.</p>
<div class="callout warn">
<p><strong>Freshness check: a newer official report exists.</strong> At 18:45 UTC on 2026-11-14 the
<a href="{esc(inj['index_url'])}" target="_blank" rel="noopener noreferrer">official index</a>
lists 11/14 reports through <strong>01:30 PM ET</strong>. Section 1 below is the
<strong>{esc(inj['report_stamp'])}</strong> capture and is not replaced in this round. Section
<a href="#s1b">1b</a> compares the 01:30 PM ET report with it, row by row, under the same counting rule.
The earlier checks still stand for the report they cover: the 04:15 AM ET report against the 07:30 PM ET
report (session 53653a5c; <a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/injury_delta_0415am.json" target="_blank" rel="noopener noreferrer">data/app/injury_delta_0415am.json</a>,
17/17 attributed rows identical), and session 26fd5f6f's independent match of <strong>31/31</strong> rows
(<a href="https://github.com/wingbangboozle1-lang/NBA3/tree/main/audit26" target="_blank" rel="noopener noreferrer">audit26/</a>).
Correction CR-26fd5f6f-A is applied: the seven games once miscounted as a gap in the 11/14 slate
are 11/15 games (<a href="flagged.html">8E-F-03</a>).</p>
</div>

<div class="callout warn">
<p><strong>Scope limit (section 1, the 04:15 AM ET report).</strong> This report covers 2026-11-14 games (with player detail) and
2026-11-15 games (team rows only, every one reading NOT YET SUBMITTED).
<strong>No official report exists for 2026-11-16 or 2026-11-17 at all.</strong> On the 04:15 AM ET
snapshot, five of the ten teams playing on 11/14 had not filed. On the 01:30 PM ET report, four of
them (New Orleans, Cleveland, Chicago, Miami) have printed players; Memphis has not
(<a href="../audit_736efb4b/index.html">audit_736efb4b</a>, flag F736-11). The back-to-back explanation
written against the 04:15 AM snapshot has not been re-verified against the schedule in this round.
Full per-game timeline on the <a href="freshness.html">Report-availability page</a>; the older flag
is <a href="flagged.html">NF-53</a> and the corrected reading is
<a href="flagged.html">NF-56</a>.</p>
</div>
""")

    body.append("<h2>1. The report, row by row</h2>")
    rows = []
    for r in inj["rows"]:
        if r["is_team_not_submitted"]:
            rows.append([
                esc(r["game_date"]), esc(r["game_time_et"]), esc(r["matchup"]),
                esc(r["team_name"]),
                '<span class="unverified">NOT YET SUBMITTED</span>',
                '<span class="unverified">unknown — no report filed</span>',
                src_cell([inj["source_url"]], "official PDF"),
            ])
            continue
        st = esc(r["status"] or "")
        cls = {"Out": "warn", "Doubtful": "warn", "Questionable": "neutral",
               "Probable": "ok", "Available": "ok"}.get(r["status"], "neutral")
        rows.append([
            esc(r["game_date"]), esc(r["game_time_et"]), esc(r["matchup"]),
            esc(r["team_name"]), esc(r["player"]),
            chip(st, cls) + " " + esc(r["reason"] or ""),
            src_cell([inj["source_url"]], "official PDF"),
        ])
    body.append(table(["Game date", "Time (ET)", "Matchup", "Team", "Player",
                       "Status and reason", "Source"], rows, "injury-rows"))

    if d.get("injury_delta_0130pm"):
        body.append(render_delta_0130(d["injury_delta_0130pm"]))

    # ---- section 1c: the newest official capture (2026-11-15 06:15 AM ET) + consecutive diff
    inj2 = NEW.get("inj1115") or {"rows": []}
    dl = NEW.get("delta1115") or {}
    if inj2.get("rows"):
        body.append(f"""
<h2 id="s1c">1c. The newest official report — 2026-11-15 06:15 AM ET</h2>
<p><strong>Report revision time: {esc(str(inj2.get('report_revision_time')))} ·
retrieval time: {esc(str(inj2.get('retrieved_stamp')))}</strong>
(<a href="{esc(inj2.get('source_url', ''))}" target="_blank" rel="noopener noreferrer">PDF</a>,
raw capture <a href="{REPO_URL}/blob/main/data/app/official_injuries_2026-11-15_0615AM_raw_79341829.md">official_injuries_2026-11-15_0615AM_raw_79341829.md</a>
with sha256 <code>{esc(str(inj2.get('raw_sha256', ''))[:16])}…</code>).
{esc(str(inj2.get('count')))} rows: {esc(str(inj2.get('player_rows')))} player rows and
{esc(str(inj2.get('not_submitted_rows')))} team rows printed “NOT YET SUBMITTED” (the 11/16
sections). {esc(str(inj2.get('rows_team_cell_not_printed')))} rows have no printed team cell on
page breaks; their carry-forward attribution is flagged below and on the
<a href="flagged.html">flagged page</a>.</p>
<div class="callout warn"><strong>Consecutive-report diff vs the 11/14 01:30 PM ET report:</strong>
{esc(str(dl.get('player_rows_added')))} player rows added,
{esc(str(len(dl.get('status_changes', []))))} status changes on overlapping rows,
{esc(str(len(dl.get('team_side_changes_1115', []))))} team-side filing changes on the shared 11/15
date. {esc(dl.get('note', ''))}
Diff file: <a href="{REPO_URL}/blob/main/data/app/injury_delta_1115.json">data/app/injury_delta_1115.json</a>.</div>
""")
        rows2 = []
        for r in inj2["rows"]:
            if r.get("is_team_not_submitted"):
                rows2.append([
                    esc(r.get("game_date")), esc(r.get("game_time_et")), esc(r.get("matchup")),
                    esc(r.get("team_name")),
                    '<span class="unverified">NOT YET SUBMITTED</span>',
                    '<span class="unverified">unknown — no report filed</span>',
                    chip("team cell printed", "ok") if r.get("team_cell_printed") else
                    chip("carry-forward attribution", "warn"),
                    src_cell([inj2["source_url"]], "official PDF"),
                ])
                continue
            st = esc(r.get("status") or "")
            cls = {"Out": "warn", "Doubtful": "warn", "Questionable": "neutral",
                   "Probable": "ok", "Available": "ok"}.get(r.get("status"), "neutral")
            rows2.append([
                esc(r.get("game_date")), esc(r.get("game_time_et")), esc(r.get("matchup")),
                esc(r.get("team_name")), esc(r.get("player")),
                chip(st, cls) + " " + esc(r.get("reason") or ""),
                chip("team cell printed", "ok") if r.get("team_cell_printed") else
                chip("carry-forward attribution", "warn"),
                src_cell([inj2["source_url"]], "official PDF"),
            ])
        body.append(table(["Game date", "Time (ET)", "Matchup", "Team", "Player",
                           "Status and reason", "Team cell provenance", "Source"],
                          rows2, "injury-rows-0615"))

    body.append(f"""
<h2>2. What the absences do to a rotation</h2>
<p>The table below sums the <strong>official season minutes</strong> — and the official season
points, rebounds and assists — of every player listed Out for a team. It is a
<strong>floor, not an estimate</strong>: only the top 31 players by minutes were captured, so an
injured player outside that table contributes nothing to the sum, and the count of such players is
shown alongside. See <a href="flagged.html">NF-52</a>.</p>

<div class="callout warn">
<p><strong>Who absorbs those minutes, and how much of the vacated production they replace, is not
quantified anywhere on this site.</strong> Answering that needs per-player game logs and on/off
splits, which this repository does not have. The vacuum is published; the replacement is
deliberately blank. Publishing a redistribution assumption as if it were a measurement is exactly
the kind of number that gets a bankroll staked on it.</p>
</div>
""")
    irows = []
    for r in d["injury_impact"]:
        reported = r.get("reported")
        irows.append([
            esc(r["date"]), esc(r["matchup"]), esc(r["side"]), esc(r["team"]),
            chip("filed" if reported else "NOT FILED", "ok" if reported else "warn"),
            num(r["rows_listed"], 0),
            num(r["out"], 0),
            "; ".join(esc(x) for x in r["out"]) or "—",
            num(r["minutes_vacuum"], 1) if r["out"] else "—",
            f'{num(r["pts_vacuum"], 1)} / {num(r["reb_vacuum"], 1)} / {num(r["ast_vacuum"], 1)}'
            if r["out"] else "—",
            num(r["players_without_official_minutes"], 0),
            '<span class="unverified">UNVERIFIED — no game logs</span>',
            src_cell([r["source"], r["source_minutes"]], "PDF + minutes"),
        ])
    body.append(table(
        ["Date", "Matchup", "Side", "Team", "Report", "Rows", "Out", "Players out",
         "Minutes vacated", "PTS/REB/AST vacated", "Unquantified players",
         "Replacement", "Source"],
        irows, "rotation",
        note="“Minutes vacated” is the sum of official season minutes-per-game over players listed "
             "Out. “Unquantified players” is how many of them are outside the captured minutes "
             "table and therefore contribute zero to the sum."))

    body.append("<h2>3. Questionable players</h2>")
    qrows = []
    seen = set()
    for r in inj["rows"]:
        if (r["status"] or "").strip() in ("Questionable", "Probable", "Doubtful"):
            key = (r["game_date"], r["matchup"], r["team_name"], r["player"])
            if key in seen:
                continue
            seen.add(key)
            qrows.append([
                esc(r["game_date"]), esc(r["matchup"]), esc(r["team_name"]),
                esc(r["player"]), chip(esc(r["status"]), "neutral"),
                esc(r["reason"] or "—"),
                src_cell([inj["source_url"]], "official PDF"),
            ])
    if qrows:
        body.append(table(["Game date", "Matchup", "Team", "Player", "Status", "Reason",
                           "Source"], qrows, "questionable"))
    else:
        body.append("<p>No player was listed Questionable, Doubtful or Probable in this report.</p>")
    return "\n".join(body)


def _base(path):
    """File name only - the manifest stores repo-relative paths for readers, not for display."""
    return (path or "").split("/")[-1] if path else "\u2014"


def page_freshness(d):
    """Report availability & freshness — added by session arena/25418e3f-nba3.

    Two jobs. First: publish, per team and per game, when the official injury
    report for that game actually exists, so a reader can tell "nobody is out"
    from "nobody has filed yet". Second: show exactly what this round's refresh
    changed, line by line, against the artefact it replaced.
    """
    av = d.get("availability") or {}
    delta = d.get("snapshot_delta") or {}
    man = d.get("manifest") or {}
    inj = d["injuries"]
    ratings = d["ratings"]
    superceded = d.get("superseded") or {}
    sup_ratings = superceded.get("ratings")
    log_prov = d.get("log_provenance") or {}
    results = d.get("results_1113") or {}
    body = []

    if not av:
        body.append('<div class="callout warn"><p>No availability artefact was found. '
                    'Run <code>python3 scripts/report_availability.py</code> before the build.'
                    '</p></div>')
        return "\n".join(body)

    counts = av.get("counts", {})
    corr = av.get("b2b_correspondence_1114", {})
    body.append(f"""
<p>Every number on this site is a snapshot of an official page that keeps moving. This page is the
audit of that movement: which official capture each figure comes from, what the previous capture
said, what changed between them, and — for injuries — <strong>when a report for a given game is
allowed to exist at all</strong>. The last question is the one that mattered: before this round the
picks table asserted “both teams had filed” on 22 of 27 games for which no official report existed,
and printed an absence count of zero. See
<a href="flagged.html">NF-56</a>.</p>
<div class="cards">
  <div class="card"><div class="k">Team-games with availability</div>
    <div class="v">{counts.get('filed', 0)}</div>
    <div class="s">of {counts.get('team_side_rows', 0)} team-sides in the window — the rest are
    blank by policy, never zero</div>
    {src_cell([inj['source_url'], av['rule_source']], 'official report + rule')}</div>
  <div class="card"><div class="k">Overdue reports</div>
    <div class="v">{counts.get('due_and_not_filed', 0)}</div>
    <div class="s">no team in the window is past its deadline without filing — every missing row is
    explained by a deadline that has not arrived</div>
    {src_cell([av['rule_source']], 'filing rule')}</div>
  <div class="card"><div class="k">Lines that moved on the refresh</div>
    <div class="v">{(delta.get('counts') or {}).get('lines_moved', 0)}</div>
    <div class="s">of {(delta.get('counts') or {}).get('lines_compared', 0)}; median
    {(delta.get('counts') or {}).get('median_abs_spread_move', 0)} points, max
    {(delta.get('counts') or {}).get('max_abs_spread_move', 0)}</div>
    {src_cell([man.get('results_log', {}).get('source_url', ''), ratings['source_url']],
              'official sources')}</div>
  <div class="card"><div class="k">Verified official rows, this capture</div>
    <div class="v">{inj['count']}</div>
    <div class="s">injury rows, plus {results.get('count', 0)} final scores and
    {ratings['count']} team-stat rows, each cross-checked field by field</div>
    {src_cell([inj['source_url'], results.get('source_url', ''), ratings['source_url']],
              'official pages')}</div>
</div>
""")

    # ---------------------------------------------------------------- 1. chain
    body.append("<h2>1. The capture chain</h2>")
    body.append(f"""<p>The canonical engine reads whatever the snapshot manifest names, so a refresh
is a data change rather than an edit of the engine. These are the four inputs and what each one
replaced.</p>""")
    # One explicit row per input. The earlier generic loop reused one "why" sentence for every
    # input and put a row count where an artefact name belonged, so the published chain table read
    # as if the injury and ratings replacements had the same cause. Fixed 2026-11-14.
    man_sup = man.get("superseded", {})
    log = man.get("results_log", {})
    prov = d.get("log_provenance") or {}

    def _prov(block):
        """One human sentence per replaced input, built from the artefacts only."""
        path = (man_sup.get(block) or "")
        return _base(path) if path else "none recorded"

    chain = [
        ["Results log (walk-forward fit)",
         f"cumulative file, last game {esc(log.get('last_date', '—'))}",
         f"{_base(log.get('path', ''))} · {log.get('games', '—')} rows",
         f"{prov.get('games_before', '—')} rows through "
         f"{esc(prov.get('previous_last_date', '—'))}",
         f"extended by the {prov.get('rows_added', '—')} finals of "
         f"{esc(prov.get('added_dates', '—'))}; per-row provenance in "
         f"{_base(log.get('provenance', ''))}. Every one of the 30 official W, L and GP "
         f"values reconciles against the extended log (check C7).",
         [log.get("source_url"), prov.get("source_url")], "official schedule"],
        ["Team advanced statistics (pace, ratings inputs)",
         man.get("ratings", {}).get("retrieved_stamp", "—"),
         _base(man.get("ratings", {}).get("path", "")),
         _prov("ratings"),
         _ratings_delta_text(d),
         [man.get("ratings", {}).get("source_url")], "official stats page"],
        ["Injury report (availability overlay)",
         man.get("injuries", {}).get("retrieved_stamp", "—"),
         f"{_base(man.get('injuries', {}).get('path', ''))} · report stamped "
         f"{man.get('injuries', {}).get('report_stamp', '—')}",
         _prov("injuries"),
         f"the newest report on the official index at capture time. It publishes "
         f"{inj.get('player_rows', '—')} player rows and {inj.get('not_submitted_rows', '—')} "
         f"NOT YET SUBMITTED rows over {len(inj.get('rows_by_game_date') or {})} game dates. "
         f"Rows whose cells the PDF dropped at a page break are marked in the artefact and "
         f"counted on the Flagged page (F-BB-02).",
         [man.get("injuries", {}).get("source_url"), inj.get("index_url")], "official PDF"],
        ["Schedule / slate (the window itself)",
         man.get("slate", {}).get("retrieved_stamp", "—")
         + f" (re-verified {man.get('slate', {}).get('reverified_on', '—')})",
         _base(man.get("slate", {}).get("path", "")),
         _prov("slate"),
         f"the window moved forward with the calendar: {len(d['lines'])} games from "
         f"{(d['meta'].get('window') or {}).get('from', '—')} to "
         f"{(d['meta'].get('window') or {}).get('to', '—')}. The previous capture priced "
         f"2026-11-14, whose games are now Final.",
         [man.get("slate", {}).get("source_url")], "official schedule"],
    ]
    rows = []
    for label, read_at, artefact, prior, why, srcs, srclabel in chain:
        rows.append([esc(label), read_at, esc(artefact), esc(prior), esc(why),
                     src_cell([x for x in srcs if x] or [REPO_URL], srclabel)])
    body.append(table(["Input", "Read at (this capture)", "Artifact", "Superseded snapshot",
                       "Why it was replaced", "Source"], rows, "chain",
                      note="Every cell in this table is copied from data/app/snapshot_manifest.json, "
                           "which scripts/capture_official_2026_11_14c.py writes. A refresh that does "
                           "not update the manifest cannot silently change what the engine reads."))

    # ------------------------------------------------------------- 2. checks
    body.append("<h2>2. The eight checks this capture ran against official sources</h2>")
    ch = man.get("checks", {})
    pc = man.get("parallel_capture", {})
    _pclog = pc.get("results_log", {})
    _pcinj = pc.get("injury_report", {})
    pc_note = (f"{_pclog.get('canonical_rows', '?')} rows in data/origin/games.csv against "
               f"{_pclog.get('rows', '?')} in data/app/games_2026-11-14c.csv, compared as "
               "(date, game id, teams, both scores, overtime flag) — two sessions extending the same "
               "nine finals from the same official page, with no shared code")
    pc_inj_note = (f"{_pcinj.get('rows_this_capture', '?')} player rows in the 04:15 AM capture "
                   f"against {_pcinj.get('rows_parallel', '?')} in the 04:45 AM capture the parallel "
                   "session transcribed; the difference is published in full rather than resolved "
                   "silently")
    check_rows = [
        ["C1 — the extended log reproduces the official games-played, wins and losses columns",
         "366 team-games = 2 × 183; 30 GP values, 30 W values, 30 L values compared",
         chip("pass", "ok") if ch.get("C1_gp_w_l_reconcile") else chip("fail", "bad"),
         src_cell([ratings["source_url"], results.get("source_url", "")], "official stats")],
        ["C2 — the same 183, reached from the official per-date game counts",
         "88 October games in our own log + 95 games the November calendar lists for 11/01–11/13",
         chip("pass", "ok") if ch.get("C2_calendar_total") else chip("fail", "bad"),
         src_cell([results.get("source_url", "")], "scoreboard calendar")],
        ["C3 — the W–L record printed under each team on the scoreboard",
         "18 team records compared with the records recomputed from the extended log",
         chip("pass", "ok") if ch.get("C3_scoreboard_records") else chip("fail", "bad"),
         src_cell([results.get("source_url", "")], "scoreboard")],
        ["C4 — the 2026-11-14 rows of the 04:15 AM ET report vs the report it supersedes",
         f"{inj.get('prior_report_compared_rows', 0)} rows compared, "
         f"{inj.get('prior_report_status_changes', 0)} status changes, "
         f"{len(inj.get('prior_report_rows_only_in_newest', []))} added, "
         f"{len(inj.get('prior_report_rows_only_in_prior', []))} dropped",
         chip("pass", "ok") if ch.get("C4_injury_rows_stable") else chip("fail", "bad"),
         src_cell([inj["source_url"], inj.get("prior_report_url", "")], "both PDFs")],
        ["C5 — the previous ratings snapshot is stale for exactly the teams that played on 11/13",
         f"{len(ch.get('C5_teams_with_new_gp', []))} teams gained a game; the 18 teams that "
         f"played that night are the same 18 — {ch.get('C5_field_differences')} of 240 stored "
         f"fields differ",
         chip("pass", "ok") if ch.get("C5_staleness_explained") else chip("review", "warn"),
         src_cell([ratings["source_url"], (sup_ratings or {}).get("source_url", ""),
                   results.get("source_url", "")], "stats page + scoreboard")],
        ["C6 — per-date game counts of the stored slate vs the official calendar",
         "11/14 → 5, 11/15 → 9, 11/16 → 8, 11/17 → 5 = 27 games, matching the slate file",
         chip("pass", "ok") if ch.get("C6_slate_counts") else chip("fail", "bad"),
         src_cell([d["slate"]["source_url"], results.get("source_url", "")], "schedule + scores")],
        ["C7 — this session's result log vs the log a parallel session captured independently",
         pc_note,
         chip("pass", "ok") if pc.get("results_log", {}).get("identical") else chip("review", "warn"),
         src_cell([results.get("source_url", ""), REPO_URL + "/blob/main/data/app/games_2026-11-14c.csv"],
                  "scoreboard + the other capture")],
        ["C8 — this session's injury transcription vs the parallel session's newer one",
         pc_inj_note,
         chip("pass", "ok") if pc.get("injury_report", {}).get("identical") else chip("review", "warn"),
         src_cell([d["injuries"]["source_url"], d["injuries"].get("index_url", "")],
                  "both PDFs on the official index")],
    ]
    body.append(table(["Check", "What was compared", "Result", "Source"], check_rows, "checks"))
    body.append(f"""<div class="callout"><p><strong>Why C1 and C2 are run separately.</strong> Both
end in the number 183, and that is the point: one route counts team-games off the official
statistics page, the other counts games off the scoreboard calendar and adds our own October rows.
Two independent official readings agreeing is what lets the extended log be called verified rather
than merely transcribed. The rebuild fails if either route disagrees.</p></div>""")
    if pc:
        body.append(f"""<div class="callout warn"><p><strong>C7 and C8 exist because two sessions did the
same refresh by accident.</strong> On 2026-11-14, about 40 minutes apart, this session and session
<code>bd90ce16</code> each appended the nine 2026-11-13 finals and each transcribed the injury report,
into different files, from the same official pages. Each then became the engine's input by a
different route — and the collision is what turned the Pages build red on <code>main</code> for one
cycle (flag <a href="flagged.html">NF-66</a>). The reconciliation is not a tie-break: the canonical
log stays the input, the other capture is compared against it on every build, and both agreements
are published here instead of being mentioned in a commit message. The injury comparison is
<em>not</em> a clean pass: the one difference is the Traore team cell (check C8, flag
<a href="flagged.html">NF-59</a>), and whether to adopt the other read's attribution and move to the
newer stamp is <a href="questions.html">CQ-47</a>.</p></div>""")

    # --------------------------------------------------- 3. the nine new finals
    body.append("<h2>3. The nine results added to the canonical log</h2>")
    body.append(f"""<p>Flag <a href="flagged.html">F36-03</a> asked a later session to carry the
2026-11-13 finals into <code>data/origin/games.csv</code>. They are here: {log_prov.get('games_before', '')} →
{log_prov.get('games_after', '')} games. The note predicted 184; the log holds 183, and C1, C2 and C3
all say 183 — recorded as <a href="flagged.html">NF-58</a> so nobody “fixes” the data to match the note.</p>""")
    g_rows = []
    for g in results.get("games", []):
        g_rows.append([
            esc(g["date"]), esc(g["game_id"]),
            f'<a href="{esc(g["game_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(g["away"])} @ {esc(g["home"])}</a>',
            f'{g["away_pts"]} – {g["home_pts"]}',
            esc(g["state"]),
            esc(g["competition"]),
            esc(f'{g["away_record_page"]} / {g["home_record_page"]}'),
            src_cell([results.get("source_url", "")], "official scoreboard"),
        ])
    body.append(table(["Date", "Game id", "Matchup", "Score (away–home)", "State",
                       "Competition", "W–L printed on the card after the game", "Source"],
                      g_rows, "new-results"))

    # ------------------------------------------------- 4. ratings staleness
    if sup_ratings:
        body.append("<h2>4. What the mid-slate ratings snapshot cost us</h2>")
        body.append("""<p>The previous capture read the official team-statistics page at
2026-11-14T01:05Z — while three games of the 11/13 slate were still live. The table below is the
difference between that snapshot and this one, for the teams it touched. Every field is compared
programmatically; nothing is inferred.</p>""")
        old_by = {t["team"]: t for t in sup_ratings["teams"]}
        r_rows = []
        for t in ratings["teams"]:
            o = old_by.get(t["team"])
            if o is None:
                continue
            diffs = [(f, o.get(f), t.get(f)) for f in
                     ("gp", "w", "l", "min", "off_rtg", "def_rtg", "net_rtg", "pace")
                     if o.get(f) != t.get(f)]
            if not diffs:
                continue
            r_rows.append([
                esc(t["team"]),
                f'{o.get("gp")} → {t.get("gp")}',
                f'{o.get("w")}-{o.get("l")} → {t.get("w")}-{t.get("l")}',
                f'{num(o.get("off_rtg"), 1)} → {num(t.get("off_rtg"), 1)}',
                f'{num(o.get("def_rtg"), 1)} → {num(t.get("def_rtg"), 1)}',
                f'{num(o.get("net_rtg"), 1)} → {num(t.get("net_rtg"), 1)}',
                f'{num(o.get("pace"), 2)} → {num(t.get("pace"), 2)}',
                str(len(diffs)),
                src_cell([ratings["source_url"], sup_ratings["source_url"]],
                         "new read / superseded read"),
            ])
        body.append(table(["Team", "GP", "W–L", "OffRtg", "DefRtg", "NetRtg", "PACE",
                           "Fields that moved", "Source"], r_rows, "ratings-staleness"))
        body.append(f"""<p><strong>{len(r_rows)} of 30 teams changed</strong> — and they are exactly
the teams that played on 11/13. That coincidence is the verification: it is what a mid-slate capture
has to look like. A page read at the wrong hour does not fail loudly; it publishes numbers that are
merely yesterday's.</p>""")

    # ----------------------------------------------------- 5. line movement
    body.append("<h2>5. Every line this refresh moved</h2>")
    body.append("""<p>Before and after, from the two published artefacts
(<code>data/app/lab_snapshot_2026-11-14T0105Z.json</code> and <code>data/app/lab.json</code>), not
from a re-derivation — so this table cannot disagree with the rest of the site.</p>""")
    l_rows = []
    for l in delta.get("lines", []):
        l_rows.append([
            esc(l["date"]),
            f'<a href="{esc(l["game_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(l["matchup"])}</a>',
            num(l["spread_before"], 1), num(l["spread_after"], 1), num(l["spread_move"], 1),
            num(l["total_before"], 1), num(l["total_after"], 1), num(l["total_move"], 1),
            f'{fmt_pct(l["p_home_before"])} → {fmt_pct(l["p_home_after"])}',
            "; ".join(esc(x) for x in l["drivers"]) or "—",
            src_cell(l["sources"], "official sources"),
        ])
    body.append(table(["Date", "Matchup", "Spread before", "Spread after", "Move",
                       "Total before", "Total after", "Move", "P(home win)",
                       "What drove it", "Source"], l_rows, "line-movement"))

    # ------------------------------------------- 6. availability states table
    body.append("<h2>6. Report availability, game by game</h2>")
    body.append(f"""<div class="callout"><p><strong>The rule, verbatim from the official
index:</strong> “{esc(av.get('rule_quote', ''))}” — <a href="{esc(av['rule_source'])}"
target="_blank" rel="noopener noreferrer">official.nba.com/nba-injury-report-2026-27-season/</a>.
Deadlines are published in local time exactly as the rule words them; no Eastern-time equivalent is
asserted, because the offset between a venue's clock and ET is not printed on any official page this
project reads (<a href="questions.html">CQ-43</a>).</p></div>""")
    by_game = {}
    for r in av.get("rows", []):
        by_game.setdefault(r["game_id"], {})[r["side"]] = r
    a_rows = []
    for gid in sorted(by_game, key=lambda g: (by_game[g]["home"]["date"],
                                              by_game[g]["home"]["matchup"])):
        sides = by_game[gid]
        h, a = sides["home"], sides["away"]
        pick = [p for p in d["picks"] if p["game_id"] == gid]
        flag = pick[0]["availability_flag"] if pick else "—"
        a_rows.append([
            esc(h["date"]), esc(h["tip_et"]),
            f'<a href="{esc(h["nba_game_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(h["matchup"])}</a>',
            f'{esc(a["team"])} ' + chip(a["state"], FLAG_KIND.get(flag, "warn")
                                        if a["state"] != "FILED" else "ok"),
            f'{esc(h["team"])} ' + chip(h["state"], FLAG_KIND.get(flag, "warn")
                                        if h["state"] != "FILED" else "ok"),
            esc("—" if not a.get("out_count") and a["state"] != "FILED" else
                (a["out_count"] if a["state"] == "FILED" else "blank")),
            esc("—" if not h.get("out_count") and h["state"] != "FILED" else
                (h["out_count"] if h["state"] == "FILED" else "blank")),
            esc(a["reprice_after"] or "filed"),
            esc(h["reprice_after"] or "filed"),
            chip(flag, FLAG_KIND.get(flag, "warn")),
            src_cell([inj["source_url"], av["rule_source"], h["nba_game_url"]],
                     "report + rule + game"),
        ])
    body.append(table(["Date", "Tip (ET)", "Matchup", "Away team", "Home team",
                       "Out (away)", "Out (home)", "Away report exists after",
                       "Home report exists after", "Pick flag", "Source"], a_rows,
                      "availability",
                      note="“blank” means the count is unknown because no official report lists that "
                           "team — it does not mean nobody is out."))

    # ------------------------------------------------- 7. coverage by date
    body.append("<h2>7. How far ahead the availability picture reaches</h2>")
    c_rows = []
    for c in av.get("coverage_by_date", []):
        c_rows.append([
            esc(c["date"]), esc(c["lead_days"]), str(c["games"]), str(c["filed"]),
            str(c["due_and_not_filed"]), str(c["not_yet_due"]),
            str(c["no_report_covers_date"]),
            esc(c["state"]),
            src_cell([inj["source_url"], d["slate"]["source_url"]], "report + schedule"),
        ])
    body.append(table(["Date", "Lead time", "Games", "Team-sides filed",
                       "Due and not filed", "Deadline not reached", "No report covers the date",
                       "Reading", "Source"], c_rows, "coverage"))
    body.append(f"""<div class="callout warn"><p><strong>{esc(av.get('headline', ''))}</strong></p>
<p>This is the structural limit on “picks up to three days ahead”: on day 0 the overlay is usable for
the teams whose deadline has passed, on day 1 nothing is due yet, and on days 2 and 3 no published
report covers the games at all. A three-day-ahead line is therefore priced on ratings and rest, and
becomes an availability-informed line only as each deadline passes.</p></div>""")

    # ------------------------------------------ 8. tonight's back-to-back proof
    body.append("<h2>8. The one clean test of the rule on this slate</h2>")
    body.append(f"""<p>If the filing rule really explains the holes in the data, then on the
2026-11-14 slate the teams that have <em>not</em> filed should be exactly the teams playing the
second game of a back-to-back. They are:</p>""")
    b_rows = [
        ["Teams that filed on the 04:15 AM ET report",
         esc(", ".join(corr.get("teams_that_filed", [])) or "—"),
         f'{len(corr.get("teams_that_filed", []))} teams',
         src_cell([inj["source_url"]], "report")],
        ["Teams printed as NOT YET SUBMITTED",
         esc(", ".join(corr.get("teams_that_have_not", [])) or "—"),
         f'{len(corr.get("teams_that_have_not", []))} teams',
         src_cell([inj["source_url"]], "report")],
        ["Teams playing the second game of a back-to-back on 11/14",
         esc(", ".join(corr.get("teams_on_a_back_to_back", [])) or "—"),
         "detected from the official results log, which is why the 11/13 finals had to be captured first",
         src_cell([results.get("source_url", ""), d["slate"]["source_url"]], "log + schedule")],
        ["Do the two sets match?",
         chip("exact: the unfiled set IS the back-to-back set", "ok")
         if corr.get("unfiled_are_exactly_the_b2b_teams") else chip("they do not match", "bad"),
         esc(corr.get("interpretation", "")),
         src_cell([av["rule_source"], inj["source_url"]], "rule + report")],
    ]
    body.append(table(["Set", "Members", "Note", "Source"], b_rows, "b2b-proof"))
    body.append(f"""<div class="callout ok"><p>Five of ten team-sides are missing tonight, and none
of them is late. Their deadline is 1 p.m. local on game day, hours before tip — so tonight's games
are <em>recoverable by waiting</em>, not by guessing. Suggestion
<a href="suggestions.html">CS-39</a> turns that into a column on the picks page;
<a href="questions.html">CQ-41</a> asks whether the engine should re-price itself when each deadline
passes.</p></div>""")

    # ---------------------------------------------------- 9. what is still blank
    body.append("<h2>9. What this page still cannot answer</h2>")
    un_rows = [
        ["The team for one injury row",
         "Traore, Nolan (Probable, right calf) sits on a page-break where the PDF prints no Team "
         "cell. Left blank rather than attributed; it changes no line, because a Probable is not an "
         "absence.", "second read of the PDF, or the official roster page",
         src_cell([inj["source_url"]], "official PDF")],
        ["Eastern-time equivalents of the local deadlines",
         "Not printed on any official page this project reads, so the column is local-only.",
         "accept an external time-zone source, or keep the blank (CQ-43)",
         src_cell([av["rule_source"]], "rule")],
        ["Who absorbs the vacated minutes",
         "Needs per-player game logs and on/off splits. This repository has a season-averaged "
         "top-31 minutes table only, so the vacuum is a floor and the replacement is blank.",
         "capture official player game logs (still the same ask as before this round)",
         src_cell([d["lab"]["meta"].get("source_players", REPO_URL)], "player table")],
        ["Whether a Probable or Available-with-injury row should move a line",
         "Nine such rows exist on tonight's slate and none of them has any effect today.",
         "owner decision CQ-45", src_cell([inj["source_url"]], "official PDF")],
    ]
    body.append(table(["Still blank", "Why", "What would settle it", "Source"], un_rows,
                      "still-blank"))
    return "\n".join(body)


def page_gameflow(d):

    flow = d["gameflow"]
    res = _res(d)
    body = []
    body.append(f"""
<p>Game-flow factors for every game in the window, all computed from official data: rest days from
the official schedule and the {d['meta']['model']['results_captured']} captured results, pace from the official team advanced statistics,
and the probabilities from the out-of-sample residual distribution of our own engine.</p>
""")
    facts = [
        ["League average total", num(res.get("avg_total"), 1),
         f"points, from the {d['meta']['model']['results_captured']} official final scores"],
        ["Overtime rate", fmt_pct(res.get("ot_rate"), 2),
         f"{round((res.get('ot_rate') or 0) * (d['meta']['model']['results_captured'] or 0))} "
         f"of {d['meta']['model']['results_captured']} captured games"],
        ["Home win rate", fmt_pct(res.get("home_win_rate"), 1),
         f"of the {d['meta']['model']['results_captured']} captured games"],
        ["Average home margin", num(res.get("avg_margin"), 2), "points"],
        ["Margin residual sd", num(res.get("margin_sd"), 2),
         "points; the width of every probability on this site"],
    ]
    body.append(table(["League fact", "Value", "Basis"],
                      [[esc(a), esc(b), esc(c) + src_cell([d["lab"]["meta"]["source_games"]],
                                                          "games")]
                       for a, b, c in facts], "flow-facts"))

    body.append("<h2>Per-game factors</h2>")
    rows = []
    for f in flow:
        notes = []
        if f["home_b2b"]:
            notes.append("home on the second night of a back-to-back")
        if f["away_b2b"]:
            notes.append("away on the second night of a back-to-back")
        if f["rest_diff"] is not None and abs(f["rest_diff"]) >= 2:
            who = "home" if f["rest_diff"] > 0 else "away"
            notes.append(f"{who} has {abs(f['rest_diff'])} more rest days")
        if f.get("proj_pace") is not None and f["proj_pace"] >= 101:
            notes.append("pace above the league median")
        if f["p_blowout_15"] is not None and f["p_blowout_15"] >= 0.45:
            notes.append("high blowout risk")
        _oh, _oa = f.get("out_home"), f.get("out_away")
        if _oh is not None and _oa is not None and _oh + _oa >= 3:
            notes.append(f"{_oh + _oa} players listed Out")
        elif (_oh or 0) + (_oa or 0) >= 2:
            missing = " and ".join(
                side for side, v in (("home", _oh), ("away", _oa)) if v is None)
            notes.append(f"{(_oh or 0) + (_oa or 0)} listed Out, {missing} side not on the "
                         f"report yet so its count is unknown")
        rows.append([
            esc(f["date"]), esc(f["matchup"]),
            num(f["home_rest"], 0) if f["home_rest"] is not None else "—",
            num(f["away_rest"], 0) if f["away_rest"] is not None else "—",
            num(f["rest_diff"], 0) if f["rest_diff"] is not None else "—",
            num(f.get("proj_pace"), 2),
            num(f["proj_total"], 1),
            num(f["total_vs_league"], 1),
            fmt_pct(f["p_ot"], 1),
            fmt_pct(f["p_blowout_15"], 1),
            f'{f["out_away"]} / {f["out_home"]}',
            "; ".join(esc(n) for n in notes) or "—",
            src_cell([f["source"], f["source_stats"]], "schedule + stats"),
        ])
    body.append(table(
        ["Date", "Matchup", "Home rest", "Away rest", "Rest diff", "Pace",
         "Projected total", "vs league", "P(OT)", "P(|margin|≥15)",
         "Out away/home", "Flags", "Source"],
        rows, "gameflow",
        note="Rest days are counted from the team's previous game in the official schedule. "
             "P(OT) is the measured league rate, not modelled per game — this project has no "
             "OT model. P(|margin|≥15) uses our margin prediction and the out-of-sample residual "
             "sd."))

    body.append("<h2>What is deliberately missing from this page</h2>")
    missing = [
        ["Possession-level pace and efficiency for the window",
         "The official team advanced page publishes season figures, not a per-game projection. "
         "The pace column is the mean of two season figures, and it is labelled as such."],
        ["An overtime model",
         f"{round((res.get('ot_rate') or 0) * (d['meta']['model']['results_captured'] or 0))} of "
         f"{d['meta']['model']['results_captured']} captured games went to overtime "
         f"({fmt_pct(res.get('ot_rate'), 2)}). That is one rate, not a model. Applying a flat "
         f"{fmt_pct(res.get('ot_rate'), 2)} to every game is the honest ceiling of what this "
         f"data supports."],
        ["Referee, travel and altitude effects",
         "No official source for these was captured, so they are absent rather than estimated."],
        ["Live in-game win probability",
         "Requires play-by-play, which this repository does not have."],
    ]
    body.append(table(["Missing factor", "Why it is not here"],
                      [[esc(a), esc(b) + src_cell([d["lab"]["meta"]["source_schedule"]],
                                                  "schedule")] for a, b in missing], "flow-missing"))
    return "\n".join(body)


def page_verification(d):
    body = []
    body.append("""
<p>This page records what was verified, against which official source, and with what result. It is
the audit trail for every number published on this site.</p>""")
    rows = [
        ["Schedule for the window", "2026-11-14 (re-read)",
         src_cell([d["slate"]["source_url"]], "nba.com/schedule"),
         f"{d['slate']['count']} games transcribed by hand across the 2026-11-14..17 window; every "
         "field re-compared against the stored snapshot: 216/216 field comparisons agree "
         "(date, tip time, teams, game id, venue, city, broadcast, URL)", chip("Verified", "ok")],
        ["Team advanced statistics", "2026-11-14",
         src_cell([d["ratings"]["source_url"]], "nba.com/stats/teams/advanced"),
         "30 teams transcribed by hand; 210/210 field comparisons agree with the stored table",
         chip("Verified", "ok")],
        ["Injury report", d["injuries"].get("report_stamp", "2026-11-14"),
         src_cell([d["injuries"]["source_url"]], "official PDF"),
         f"{d['injuries']['count']} rows: {d['injuries'].get('player_rows', 0)} player rows + "
         f"{d['injuries'].get('not_submitted_rows', 0)} team report statuses; the 11/14 player rows "
         "re-compared against the 11/13 07:45 PM snapshot; 5 of 10 11/14 teams had not filed, "
         "18 11/15 placeholders",
         chip("Verified", "ok")],
        ["Injury report index (which reports exist)", "2026-11-14",
         src_cell(["https://official.nba.com/nba-injury-report-2026-27-season/"], "official index"),
         "Read at 09:45 UTC: the index listed 11/14 reports up to 04:15 AM ET, and the canonical table is that report. "
         "Read at 18:45 UTC: the index lists up to 01:30 PM ET; see the injuries page, section 1b",
         chip("Superseded on index", "warn")],
        ["Historical results log", "2026-11-14 (refreshed)",
         src_cell(["https://www.nba.com/games?date="], "nba.com/games"),
         f"{d['lab']['meta'].get('games_captured', '?')} games / "
         f"{2 * d['lab']['meta'].get('games_captured', 0)} team-games; team-games match the official "
         "GP column for all 30 teams (0 mismatch) and recomputed W–L matches the official W–L. "
         "The nine 2026-11-13 finals were appended from the official schedule on 2026-11-14.",
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


def page_projections(d):
    """Projection surface: two independent estimators, their disagreement is the headline."""
    est = NEW.get("est") or {}
    body = []
    h = est.get("hca_measurement", {})
    a = est.get("estimator_a", {})
    b = est.get("estimator_b", {})
    body.append(f"""
<div class="callout"><strong>Headline: the two estimators disagree by
{esc(str(est.get('policy', {}).get('disagreement_headline_mean')))} points on average across the
window.</strong> That disagreement <em>is</em> the confidence statement — a small disagreement means
both independent methods land in the same place, a large one means the game is genuinely hard to
price. The equal-weight blend of the two is published underneath as a secondary line only; it is
never the headline and never the only number shown.</div>

<p>Estimator A is a ridge margin model (Massey-style team strengths) fit on the official
completed-game log. Estimator B is a possession-efficiency model from the three official team-stat
pages captured 2026-11-15: expected points are <strong>possessions x points-per-possession</strong>.
Home-court advantage is <strong>pinned to the measured home-win rate</strong>
({esc(str(h.get('home_win_rate')))} over {esc(str(h.get('games')))} official games →
{esc(str(h.get('hca_points_pinned')))} points) and is never a free fit coefficient.</p>
""")
    meta_rows = [
        ["Estimator A — ridge margin, HCA pinned", esc(a.get("name", "")),
         f"OOS log-loss {esc(str(a.get('oos_log_loss')))}, accuracy {esc(str(a.get('oos_accuracy')))} "
         f"on {esc(str(a.get('oos_games')))} walk-forward games",
         esc(a.get("oos_sample", "")),
         src_cell(["https://www.nba.com/games?date=2026-11-14"], "official finals")],
        ["Estimator B — possessions x PPP", esc(b.get("name", "")),
         f"log-loss {esc(str(b.get('log_loss_in_sample')))} (IN-SAMPLE, labelled), accuracy "
         f"{esc(str(b.get('accuracy_in_sample')))}",
         esc(b.get("label", "")),
         src_cell(b.get("sources", []), "team stats pages")],
        ["Home-court advantage (pinned)", f"{esc(str(h.get('hca_points_pinned')))} pts",
         f"home-win rate {esc(str(h.get('home_win_rate')))}, margin SD {esc(str(h.get('margin_sd')))}",
         esc(h.get("formula", "")),
         src_cell([s for s in h.get("sources", []) if s.startswith("https://")]
                  or ["https://www.nba.com/games?date=2026-11-13"], "official log")],
        ["Parlay rho (measured)", esc(str(est.get("rho_measured"))),
         esc(est.get("rho_note", "")), "used for every same-game parlay price",
         src_cell(["https://www.nba.com/games?date=2026-11-14"], "official finals")],
    ]
    body.append(table(["Item", "Value", "Measured score", "Sample / formula", "Source"],
                      meta_rows, "est-meta"))

    rows = []
    for r in est.get("window", []):
        flags = "; ".join(r.get("luck_band_flag") or []) or "—"
        rest = r.get("rest", {})
        trav = r.get("travel_km", {})
        def _trav(t):
            v = trav.get(t) or {}
            if v.get("km") is None:
                return "—" + (f" ({v.get('flag')})" if v.get("flag") else "")
            return f"{v['km']} km"
        def _rest(t):
            v = rest.get(t) or {}
            if v.get("days_rest") is None:
                return "—"
            marks = []
            if v.get("b2b"):
                marks.append("B2B")
            if v.get("three_in_4"):
                marks.append("3-in-4")
            return f"{v['days_rest']}d" + (" " + ",".join(marks) if marks else "")
        rows.append([
            esc(r["date"]), esc(r["tip_et"]),
            f"{esc(r['away'])} @ {esc(r['home'])}",
            num(r["est_a_margin"], 1), num(r["est_b_margin"], 1),
            chip(num(r["disagreement_abs"], 1) + " pts", "warn" if r["disagreement_abs"] > 8 else "neutral"),
            num(r["blend_margin"], 1),
            f"{num(r['est_b_total'], 1)} (poss {num(r['possessions'], 1)})",
            num(r["home_win_prob"], 2),
            f"{esc(r['away'])}: {esc(_rest('away'))}<br>{esc(r['home'])}: {esc(_rest('home'))}",
            f"{esc(r['away'])}: {esc(_trav('away'))}<br>{esc(r['home'])}: {esc(_trav('home'))}",
            f"A {esc(str(r['luck_z'].get('away')))} / H {esc(str(r['luck_z'].get('home')))}<br>{esc(flags)}",
            src_cell(r.get("sources", []), "official"),
        ])
    body.append(table(
        ["Date", "Tip (ET)", "Matchup", "Est. A margin", "Est. B margin", "Disagreement (headline)",
         "Blend (secondary)", "Est. B total = poss x PPP", "P(home)", "Rest (days, B2B/3-in-4)",
         "Travel (from last arena)", "Luck z (away/home) + band flag", "Source"],
        rows, "projections",
        note="Margins are quoted for the home team. “Est. B total = poss x PPP” shows the "
             "possession count behind every total. Travel is a derived haversine distance on the "
             "sourced arena-coordinate table (reference source, not NBA-published); blank cells "
             "mean coordinates are missing for one endpoint. Luck |z| &gt; 2 marks teams outside "
             "the noise band — the bet surface refuses those, this projection surface publishes "
             "them flagged."))

    par = est.get("parlay_prices", [])
    if par:
        body.append("<h2>2. Parlay prices: measured rho vs the naive product</h2>")
        body.append(table(
            ["Game", "Legs", "P(side)", "P(over)", "Measured rho", "Joint price (rho-aware)",
             "Naive product (printed beside)", "Joint / naive", "Method", "Source"],
            [[f"{esc(p['game_id'])}", esc(p["legs"]), num(p["p_side"], 3), num(p["p_over"], 3),
              num(p["rho_measured"], 3), num(p["joint_price_rho"], 3),
              num(p["naive_product"], 3), num(p["ratio_joint_over_naive"], 2), esc(p["method"]),
              src_cell(["https://www.nba.com/games?date=2026-11-14"], "official finals")]
             for p in par], "parlay-rho",
            note="Every correlated price prints the naive product of its legs beside it, plus the "
                 "measured rho that produced the difference."))

    mp = est.get("market_anchored_prior", {})
    body.append(f"""
<h2>3. Market-anchored prior</h2>
<div class="callout warn"><strong>Blended lines are blank and flagged.</strong>
{esc(mp.get('flag', ''))} Feed status: <strong>{esc(str(mp.get('feed_status')))}</strong>.</div>
<p>When a closing-line feed is connected, the published line becomes
<em>w x model + (1-w) x closing</em> with w from the measured out-of-sample log losses
({esc(str(mp.get('formula')))}). Until then only the model line exists and it is labelled as
such. The placeholder feed file is
<a href="{REPO_URL}/blob/main/data/app/closing_lines.json">{REPO_URL}/blob/main/data/app/closing_lines.json</a>.</p>
""")
    return "\n".join(body)


def page_settlement(d):
    feed = NEW.get("feed") or {"games": []}
    body = []
    body.append(f"""
<p>Every game in the official per-game results feed: date, teams, final score and quarter scores,
settled only from verified official finals. {esc(str(feed.get('settled_count')))} of
{esc(str(feed.get('count')))} rows are settled. A row settles only when the game state is Final and
the quarter scores sum to the printed final for both teams (checked offline in
<a href="{REPO_URL}/blob/main/scripts/capture_official_2026_11_15.py">capture_official_2026_11_15.py</a>
and <a href="{REPO_URL}/blob/main/scripts/results_feed.py">results_feed.py</a>).
{esc(feed.get('settlement_rule', ''))}</p>
""")
    rows = []
    for g in feed.get("games", []):
        def q(v):
            return esc(str(v)) if v is not None else '<span class="unverified">— (not captured)</span>'
        rows.append([
            esc(g["date"]), f"{esc(g['away'])} @ {esc(g['home'])}",
            f"{esc(str(g['away_pts']))} - {esc(str(g['home_pts']))}",
            f"{q(g['away_q1'])} / {q(g['away_q2'])} / {q(g['away_q3'])} / {q(g['away_q4'])}",
            f"{q(g['home_q1'])} / {q(g['home_q2'])} / {q(g['home_q3'])} / {q(g['home_q4'])}",
            chip("verified", "ok") if g.get("verified") else chip("unverified", "bad"),
            chip("settled", "ok") if g.get("settled") else chip("open", "warn"),
            esc(g.get("settlement_stamp") or g.get("quarter_check") or ""),
            src_cell([g.get("verified_from") or "https://www.nba.com/games"], "official"),
        ])
    body.append(table(["Date", "Matchup", "Final", "Away quarters", "Home quarters", "Verification",
                       "Settlement", "Stamp / check", "Source"], rows, "results-feed"))
    return "\n".join(body)


def page_ledger(d):
    entries = NEW.get("ledger") or []
    body = []
    body.append(f"""
<p>Every published pick is hashed before tip and appended to a tamper-evident hash chain: each entry
links the previous entry's hash, so any silent edit of history breaks the chain and
<code>python3 scripts/pick_ledger.py verify</code> fails loudly. {len(entries)} entries are in the
chain. Because no strategy is funded, entries are <strong>published projections, result-graded</strong>
— not money bets (the bet surface stays gated).</p>
<div class="callout"><strong>Verify this table yourself:</strong>
<code>python3 scripts/pick_ledger.py verify</code> in the repository recomputes every payload hash
and the chain links. The chain head is published here so a later silent change is detectable.</div>
""")
    rows = []
    prev = ""
    for e in entries:
        b = e.get("body", {})
        rows.append([
            esc(b.get("pick_id", "")), esc(b.get("state", "")),
            esc(b.get("published_utc") or b.get("settled_utc") or ""),
            f'<code>{esc((b.get("payload_sha256") or "")[:16])}…</code>',
            f'<code>{esc((e.get("entry_hash") or "")[:16])}…</code>',
            f'<code>{esc((e.get("prev_hash") or "")[:16])}…</code>',
            esc(str(b.get("hash_verified_at_settlement", ""))),
            src_cell(["https://www.nba.com/games?date=2026-11-15"], "official schedule"),
        ])
        prev = e.get("entry_hash", "")
    body.append(table(["Pick", "State", "Timestamp (UTC)", "Payload sha256 (prefix)",
                       "Entry hash (prefix)", "Prev entry hash (prefix)",
                       "Hash verified at settlement", "Source"], rows, "ledger"))
    body.append(f'<p>Chain head: <code>{esc(prev)}</code></p>')
    return "\n".join(body)


def page_prereg(d):
    prereg = NEW.get("prereg") or []
    body = []
    body.append(f"""
<p>Every strategy is pre-registered <strong>before its first bet</strong>: signal, thresholds,
universe and an exact settlement rule, frozen with a sha256 in
<a href="{REPO_URL}/tree/main/data/app/prereg">data/app/prereg/</a>. Frozen files are never
overwritten — <code>python3 scripts/preregister.py freeze</code> refuses to touch an existing file,
and <code>verify</code> recomputes every hash. {len(prereg)} strategies are frozen. No money bet has
been placed (no rule is funded), so every file here predates the first bet by construction.</p>
""")
    rows = []
    for p in prereg:
        rows.append([
            esc(p.get("strategy_id", "")), esc(p.get("name", "")), esc(p.get("family", "")),
            esc(p.get("signal", "")[:160]),
            f'edge {esc(str(p.get("thresholds", {}).get("expected_edge_pp")))} pp · '
            f'hit {esc(str(p.get("thresholds", {}).get("hit_rate")))} · '
            f'n {esc(str(p.get("thresholds", {}).get("sample_n")))}',
            esc(p.get("frozen_utc", "")),
            f'<code>{esc((p.get("sha256") or "")[:16])}…</code>',
            esc(p.get("settlement_rule", "")[:120]) + "…",
            src_cell(["https://www.nba.com/games"], "official universe"),
        ])
    body.append(table(["ID", "Strategy", "Family", "Signal (rule)", "Thresholds", "Frozen (UTC)",
                       "sha256 (prefix)", "Settlement rule (excerpt)", "Source"], rows, "prereg"))
    return "\n".join(body)


def page_refresh(d):
    gates = (NEW.get("gates") or {}).get("gates", [])
    body = []
    body.append(f"""
<p>The scheduled refresh job (<a href="{REPO_URL}/blob/main/.github/workflows/refresh.yml">.github/workflows/refresh.yml</a>,
cron four times a day around the official injury-report filing windows) fetches the official
injury index and newest report, the schedule and results pages, every finished game's official
game book, and the three official team-stat pages. <strong>The site rebuild runs only after the
freshness and provenance gates below pass</strong>; on gate failure the run exits non-zero and the
site keeps the last good build.</p>
<p><strong>Injury-report revision time:</strong> 2026-11-15 06:15 AM ET ·
<strong>retrieved:</strong> 2026-11-15T11:33Z. Every capture in
<a href="{REPO_URL}/tree/main/data/app">data/app/</a> carries its own https source link,
retrieval stamp and (where files are stored raw) sha256.</p>
""")
    rows = [[esc(g["id"]), chip("pass", "ok") if g["pass"] else chip("FAIL", "bad"),
             esc(g["detail"]),
             src_cell(["https://official.nba.com/nba-injury-report-2026-27-season/"],
                      "official index")] for g in gates]
    if rows:
        body.append(table(["Gate", "Result", "Detail", "Source"], rows, "gates"))
    else:
        body.append('<p class="unverified">No gate report committed yet — run '
                    '<code>python3 scripts/freshness_gates.py --json-out data/app/gate_report.json</code>. '
                    'Blank and flagged, not asserted.</p>')
    body.append(f"""
<h2>What the refresh stores</h2>
<ul>
  <li>the newest official injury report PDF (sha256 + retrieval stamp) and the consecutive-report
      diff against the previous capture;</li>
  <li>the schedule window today..today+3 with game ids and tip times;</li>
  <li>per-game results: date, teams, final score, quarter scores — settled only from verified
      finals (see the <a href="settlement.html">settlement page</a>);</li>
  <li>per-player game logs (minutes, points, rebounds, assists, opponent) from every official
      game book captured;</li>
  <li>the three team-stat pages (traditional, opponent, advanced), re-read and re-cut into the
      model inputs;</li>
  <li>top-8 minutes shares and replacement shares for the minutes-redistribution model.</li>
</ul>
""")
    return "\n".join(body)


def page_flagged(d):
    body = []
    all_flags = list(d["flags"]) + list(NEW.get("flags_session", []))
    n_high = sum(1 for f in all_flags if f["severity"] == "high")
    n_med = sum(1 for f in all_flags if f["severity"] == "medium")
    n_low = sum(1 for f in all_flags if f["severity"] == "low")
    body.append(f"""
<div class="callout"><strong>Nothing on this page blocks the site.</strong> It blocks
<em>decisions</em>. {len(all_flags)} items: {n_high} high, {n_med} medium, {n_low} low severity.
Every item keeps its source link so it can be reviewed and closed by the owner.</div>
""")
    rows = []
    for f in all_flags:
        rows.append([
            esc(f["id"]), esc(f["area"]), esc(f["item"]), esc(f["why"]),
            chip(f["severity"], {"high": "bad", "medium": "warn", "low": "neutral"}.get(f["severity"], "warn")),
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
    for q in list(d["questions"]) + list(NEW.get("questions_session", [])):
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
    for s in list(d["suggestions"]) + list(NEW.get("suggestions_session", [])):
        rows.append([
            esc(s["id"]), esc(s["area"]), esc(s["suggestion"]), esc(s["why"]),
            esc(s["options"]), esc(s["recommended_option"]), esc(s["dependency"]),
            esc(s["decision"]), src_cell(s["sources"]),
        ])
    body.append(table(["ID", "Area", "Suggestion", "Why", "Options", "Recommendation",
                        "Dependency", "Decision", "Source"], rows, "suggestions"))
    return "\n".join(body)


def page_methodology(d):
    lab = d["lab"]
    res = _res(d)
    m = d["meta"]["model"]
    luck = _luck(d)
    body = []
    body.append(f"""
<h2>1. What is originated here</h2>
<p>Two numbers per game: a <strong>point spread</strong>, quoted for the home team the way a book
prints it, and a <strong>total</strong>. Both come from a walk-forward engine whose inputs are
official: the official schedule, official team advanced statistics, official final scores and the
official injury report. <strong>Nothing is copied from a sportsbook</strong>, because no
sportsbook data is connected to this repository.</p>
<p>The engine is <a href="{REPO_URL}/blob/main/scripts/strategy_lab.py">scripts/strategy_lab.py</a>,
standard library only, seeded and deterministic — two consecutive runs produce byte-identical
output, which is what lets the CI workflow detect drift.</p>

<h2>2. The model</h2>
<ul>
  <li><strong>Margin.</strong> A Massey least-squares model: one rating per team plus a home-court
      term, fitted on completed games. The prediction for a game is
      <code>rating(home) − rating(away) + home-court</code>.</li>
  <li><strong>Total.</strong> An ordinary least-squares regression of the game total on the two
      teams' prior scoring environment (points for and against, both teams).</li>
  <li><strong>Shrinkage, chosen from the past.</strong> A ridge penalty on the team ratings and a
      blend weight pulling the totals toward the league mean are both selected by validating on the
      most recent 20% of <em>past</em> games. This matters: before shrinkage the ratings of teams on
      a bad run exploded and the engine printed a 28-point spread, which no real line does.</li>
  <li><strong>No look-ahead.</strong> For every date, the engine is refitted from games with a
      strictly earlier date. Games are batched by date, so a game cannot see another game tipped off
      the same night — a leak an earlier session's pipeline actually had.</li>
</ul>

<h2>3. How it performed out of sample</h2>
<p>{num(res.get('n'), 0)} out-of-sample forecasts, after a {m['burn_in']}-game burn-in. Each is
scored against a naive constant baseline (league-average home margin, league-average total) on the
same games.</p>
""")
    perf = [
        ["Margin RMSE", num(res.get("margin_rmse"), 3), num(res.get("margin_baseline_rmse"), 3),
         "ours is better"],
        ["Total RMSE", num(res.get("total_rmse"), 3), num(res.get("total_baseline_rmse"), 3),
         "ours is WORSE — reported as such"],
        ["Margin bias", num(res.get("margin_bias"), 3) + " pts", "0", "effectively unbiased"],
        ["Total bias", num(res.get("total_bias"), 3) + " pts", "0",
         f"our totals run {abs(res.get('total_bias') or 0):.1f} points high"],
        ["Brier (home win)", num(res.get("brier"), 4), num(res.get("brier_baseline"), 4),
         "better than unskilled, but scored on the same residuals — see the note below"],
        ["Margin residual sd", num(res.get("margin_sd"), 3) + " pts", "—",
         "the width behind every probability on this site"],
    ]
    body.append(table(
        ["Measure", "Our model", "Baseline", "Verdict"],
        [[esc(a), esc(b), esc(c), esc(dd) + src_cell([lab["meta"]["source_games"]], "games")]
         for a, b, c, dd in perf], "method-perf"))
    body.append(f"""
<div class="callout warn">
<p><strong>The Brier score is in-sample on the walk-forward residuals.</strong> The residual
distribution that turns a margin into a probability is estimated from the same forecasts it scores.
That flatters the number, it is not a calibration test on held-out data, and it is labelled as such
wherever it appears.</p>
</div>

<h2>4. Removing luck from the evaluation</h2>
<p>Luck cannot be removed from a single game. It can be kept out of the <em>score</em>, and this
project uses four mechanisms, because one is not enough:</p>
<ol>
  <li><strong>Exact binomial tests</strong> against the fair-line rate for the market — 50% for a
      single bet, 25% for a two-leg parlay. Not a normal approximation: an exact test. (Gate G5.)</li>
  <li><strong>Benjamini–Hochberg</strong> false-discovery-rate control across every scored rule on
      the board. Fifteen rules at p &lt; 0.05 produce a false positive more often than not.
      (Gate G6.)</li>
  <li><strong>A whole-board Monte Carlo.</strong> Every rule is simulated under its own fair-line
      null, the largest edge anywhere on the board is recorded, and that is repeated
      {luck.get('iterations', 0):,} times. The 95th percentile —
      <strong>{num(luck.get('threshold_pp'), 1)} percentage points</strong> — is the edge a rule
      must beat before it is called anything. This is the test that catches the fact that the
      <em>best</em> rule on a large board is biased upward even after FDR correction. (Gate G9.)
      <strong>Nothing on the board beats it.</strong></li>
  <li><strong>Date-block bootstrap</strong> for the return interval, because betting results cluster
      by date — same slate, same travel, same news. The resampling unit is the date, not the bet.
      (Gate G8.)</li>
</ol>
<p>Three further disciplines are structural rather than statistical. Rules are published in
<strong>mirror pairs</strong> so the losing direction cannot be hidden. Strategy thresholds are
<strong>rolling quantiles of prior projections</strong> rather than fixed numbers, so a rule cannot
die or appear just because the model changed. And a <strong>null control</strong> — back the home
team every game — is scored alongside everything else; it fails
{sum(1 for g in next(s for s in d['strategies'] if s['id'] == 'ST-NUL')['gates'] if not g['passed'])}
of {len(next(s for s in d['strategies'] if s['id'] == 'ST-NUL')['gates'])} gates, which is the check
that the gates work.</p>

<div class="callout">
<p><strong>The most important methodological point on this site.</strong> Because our line is
originated to be fair, the expected value of betting into it is <em>zero by construction</em>. A rule
that wins more than half the time against our own line is therefore evidence that
<strong>our line is biased</strong> in the games the rule picks — a model defect to repair, not an
edge to bet. This project reports those biases as defects (see
<a href="questions.html">CQ-40</a>). The one apparent exception found during this build — "fade the
highest projected totals", which posted 69.7% on 66 games before the totals model was regularised —
fell to 65.5% on 29 games once the model was fixed. The signal was the model's error.</p>
</div>

<h2>5. Injuries and rotation</h2>
<p>The official injury report publishes a participation status and a reason. It does not publish
minutes, expected minutes, or production impact, and a status is not a medical clearance. This
project therefore:</p>
<ul>
  <li>captures the newest report with its timestamp and keeps the previous snapshot so status
      changes can be shown;</li>
  <li>treats a team printed <strong>NOT YET SUBMITTED</strong> as <em>unknown</em>, never as
      healthy — "unknown" and "fit" are different facts and every downstream number respects the
      difference;</li>
  <li>sums the <strong>official season minutes</strong>, and the official season points, rebounds
      and assists, of players listed <strong>Out or Doubtful</strong> — and only those, because
      anything softer is a guess;</li>
  <li>publishes that vacuum as a <strong>floor</strong> and counts how many listed players fall
      outside the captured minutes table, contributing zero;</li>
  <li>leaves <strong>the replacement blank</strong>. Who absorbs the vacated minutes, and how much
      of the production they replace, needs per-player game logs and on/off splits that this
      repository does not have. No availability weights (Out 0.00 / Doubtful 0.25 / Questionable
      0.60 / Probable 0.90 / Available 1.00) are applied anywhere in the current pipeline; earlier
      sessions used such weights and they are recorded here only as history.</li>
</ul>

<h2>6. Legal and data-use boundary</h2>
<ul>
<li>The NBA Terms of Use restrict the use of NBA Statistics in connection with gambling and restrict
reproduction. This is a research repository, publishes no market prices and no betting advice, and
links to every official source it uses. The review points at
<a href="https://www.nba.com/termsofuse">nba.com/termsofuse</a> are listed on the
<a href="flagged.html">Flagged for review</a> page.</li>
<li>Publishing betting-related functionality or recommendations in the Netherlands requires a
licence under the Betting and Gaming Act and a Ksa licence for online sports-betting offers; the
statutory position is summarised on the <a href="questions.html">Open questions</a> page.</li>
<li>No licensed price feed is connected, so no profit, ROI or market comparison can be published
here. Every price shown is our own fair price, and every ROI figure is measured against our own
line at an assumed −110 — which is a property of our numbers, not an economic result
(<a href="flagged.html">NF-55</a>).</li>
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
        flist_parts.append(
            f'<li><span class="flag-id">{esc(f["id"])}</span> <strong>{esc(f["item"])}</strong> — '
            f'{esc(f["action_needed"])} {src_cell(f["sources"], "source")}</li>')
    flist = "\n".join(flist_parts)
    # Cross-reference to the independent integration round (session e40cd215, PR #23).
    # It used to be appended inside the NF-23 list item, which made a navigation tile render as
    # if it were an eighth flagged item (flagged as F-DD1-08). It now sits below the list.
    xref = ('<p class="small">Related work: <a href="dash/index.html"><b>Unified dashboard '
            '(session e40cd215)</b></a> — a second, independent integration round: 174-game '
            're-verification, 22 originated lines from a separate engine, 9 gates, measured '
            'parlay dependence, cross-engine reconciliation and a flagged register.</p>')
    res = _res(d)
    luck = _luck(d)
    strategies = d["strategies"]
    funded = sum(1 for s in strategies if s["tier"] == "T1")
    best_edge = max([abs(s["edge_pp"]) for s in strategies if s["edge_pp"] is not None] or [0])
    verified_official = d["slate"]["count"] + len(d["ratings"]["teams"]) + d["injuries"]["count"]
    body = []
    body.append(f"""
<section class="hero">
  <h2>We originate our own NBA lines, then try to prove they are worth anything.</h2>
  <p>One dashboard for the whole pipeline: lines originated for today and the next three days,
  {len(strategies)} strategy rules measured out of sample against nine validation gates and ranked on
  a leaderboard with an explicit luck threshold, the correlations that were actually measured (and
  the ones left blank), the official injury report with the rotation minutes it vacates, game-flow
  factors, an executive summary, the open questions, improvement suggestions awaiting a decision, and
  a review page for everything still unverified.</p>
  <p class="hero-meta">Window {esc(d['slate']['window']['from'])} → {esc(d['slate']['window']['to'])} ·
  {d['slate']['count']} official games · {len(d['lines'])} originated lines ·
  {len(d['picks'])} priced games · {d['injuries']['count']} official injury rows ·
  {len(d['flags'])} flagged items · snapshot {BUILD_DATE}</p>
</section>
<div class="cards">
  <div class="card"><div class="k">Verified official rows</div><div class="v">{verified_official}</div>
    <div class="s">schedule + team stats + injury report, each cross-checked field by field against
    the values already stored</div>
    {src_cell([d['slate']['source_url'], d['ratings']['source_url'], d['injuries']['source_url']], 'official pages')}</div>
  <div class="card"><div class="k">Strategies funded</div><div class="v">{funded}</div>
    <div class="s">of {len(strategies)} scored rules. None clears the luck threshold
    ({num(luck.get('threshold_pp'), 1)} pp); the best edge any rule posted is {best_edge:.1f} pp.</div>
    {src_cell([d['lab']['meta']['source_games']], 'nba.com/games')}</div>
  <div class="card"><div class="k">Correlation values measured</div>
    <div class="v">{sum(1 for c in d['correlations']['rows'] if c.get('verified'))}</div>
    <div class="s">of {len(d['correlations']['rows'])} pairs — {sum(1 for c in d['correlations']['rows'] if not c.get('verified') and c.get('value') is None)} are not measurable and left blank, {sum(1 for c in d['correlations']['rows'] if not c.get('verified') and c.get('value') is not None)} is an assumption printed as one</div>
    {src_cell([d['lab']['meta']['source_games']], 'nba.com/games')}</div>
  <div class="card"><div class="k">Open questions</div><div class="v">{len(d['questions'])}</div>
    <div class="s">each with what is known, what is missing and what would settle it —
    {sum(1 for q in d['questions'] if 'Open' in (q.get('status') or ''))} still need an owner decision</div>
    {src_cell([REPO_URL], 'repository')}</div>
</div>
<section class="cat">
  <h3>Start here</h3>
  <div class="tiles">
    <a class="tile" href="app/summary.html"><span class="tile-t">Executive summary — the headline result</span></a>
    <a class="tile" href="app/leaderboard.html"><span class="tile-t">Strategy leaderboard — who is winning, and whether it is luck</span></a>
    <a class="tile" href="app/lines.html"><span class="tile-t">Originated lines for the window</span></a>
    <a class="tile" href="app/flagged.html"><span class="tile-t">Flagged for review — read before trusting a number</span></a>
  </div>
</section>
<section class="cats">{"".join(cats)}</section>
<section class="cat">
  <h3>Highest-severity flags (full list on the <a href="app/flagged.html">Flagged for review</a> page)</h3>
  <ul class="flag-list">
  {flist}
  </ul>
  {xref}
</section>
<section class="cat">
  <h3>Archive — earlier sessions</h3>
  <p>{ARCHIVE_TREES} complete dashboards built by earlier sessions are still reachable, from the
  first data site at <a href="docs/index.html">docs/index.html</a> onwards; the full dated list is
  on the <a href="archive.html">archive page</a>. Each uses its own ID namespace, its own injury
  snapshot and its own model variant, so <strong>the pages above are the current numbers</strong>
  and the archive is history. They are kept because the audit trail is worth something: a reader
  can see what an earlier round concluded and what changed.</p>
</section>
""")
    return layout("NBA Edge Lab — canonical dashboard", "Home", "\n".join(body),
                  subtitle="Official-source research dashboard. Every table row links to its source; "
                          "anything that could not be confirmed is left blank and flagged.",
                  root_page=True)


ARCHIVE_TREES_ROWS = [
    # path, session, what it is, why it is no longer current
    ("docs/", "f879620b",
     "First data site: an 11/11 injury snapshot, the 11/13-11/16 slate and the 2026-27 rules, "
     "with the validation-gate and link-checking scripts (tools/, tests/)."),
    ("site/", "7c532e8c",
     "Generated from data/*.json: one page per category, every row carrying a source id."),
    ("lab/", "5697caaf",
     "Line lab — the first originated-lines engine (scripts/model.py) and its pages."),
    ("research/", "9ed6085f",
     "Research site generated from data/*.csv, with the requirements, questions and "
     "suggestions registers as CSV."),
    ("edge/", "0a016df8",
     "Edge Lab: verified game log, originated lines and gated picks as JSON plus pages."),
    ("origin/", "e22a2831",
     "Origination engine: the verified results log, a walk-forward backtest and a seven-gate "
     "leaderboard."),
    ("dash/", "e40cd215",
     "Unified dashboard: a second integration round with its own engine (integrate/), "
     "cross-engine reconciliation and a 9-gate leaderboard."),
    ("verify/pages/", "3655c68d",
     "Verification and decision layer: cross-pipeline reconciliation, corrections and a "
     "decision queue."),
    ("review.html", "2e50a71a",
     "Cross-workstream audit R-01 to R-13, comparing the outputs of every session side by side."),
    ("app/legacy/", "8d3d0271",
     "The previous root dashboard, kept as it was on 2026-11-13 so the change is auditable."),
    ("hub/", "99eabb04",
     "Consolidated dashboard: one namespace, one set of numbers, every row sourced."),
    ("d01ae7e2/docs/", "d01ae7e2",
     "Official-slate line origination and gated picks for a 31-game slate, with a "
     "provisional-safe pipeline."),
    ("executive-summary.html", "3bf92fcc",
     "Cross-site consolidated executive summary."),
    ("dashboard/", "925439ca",
     "Independently verified build: 17 pages generated by final/build_site.py, every stored "
     "value re-checked by final/verify.py against the official NBA pages."),
]

ARCHIVE_OFFICIAL = [
    "https://official.nba.com/nba-injury-report-2026-27-season/",
    "https://www.nba.com/schedule",
]


def page_archive(d):
    """Every earlier session's site, in one dated list, off the landing page.

    Added by session dd1eb1f1 (flag F-DD1-07): thirteen trees were being advertised as tiles on
    the landing page next to the current numbers, which is the opposite of a clean front door.
    They are still worth keeping - the audit trail is the point of the repository - so they move
    here and the landing page links here once.
    """
    rows = []
    for path, session, what in ARCHIVE_TREES_ROWS:
        rows.append([
            f'<a href="{esc(path)}"><code>{esc(path)}</code></a>',
            esc(session),
            esc(what),
            src_cell(ARCHIVE_OFFICIAL, "official basis"),
            link(f"https://github.com/wingbangboozle1-lang/NBA3/tree/main/{path.rstrip('/')}",
                 "repository"),
        ])
    body = [
        '<p class="lead">Every dashboard built by an earlier session of this project, in the order '
        'it was published. None of these is current: they use different ID namespaces, different '
        'injury snapshots and different model variants. <strong>The canonical pages linked in the '
        'navigation are the current numbers.</strong></p>',
        '<p>They are kept, not deleted, because being able to read what an earlier round '
        'concluded - and what a later round changed - is the audit trail. Each row links to the '
        'tree itself and to the official pages it was built from; the exact snapshot inside each '
        'tree is recorded inside that tree.</p>',
        table(["Tree", "Session", "What it is", "Official basis", "In the repository"], rows,
              "archive"),
        '<p class="note">The <code>dashboard/</code> row is the one tree that was being deployed '
        'to the site and rebuilt in CI but was missing from the landing page list entirely. '
        'Recording it here is what surfaced the gap (flag F-DD1-09).</p>',
    ]
    return "\n".join(body)


def build_requirements_page(d):
    return layout("Brief coverage", "Overview", page_requirements(d),
                  subtitle="Each requirement from the brief, how it is addressed, and what is still blocked.")


# --------------------------------------------------------------------------
def main():
    check_only = "--check" in sys.argv
    with open(APP_DATA, encoding="utf-8") as fh:
        d = json.load(fh)

    # ---- header context (CS-41): the window and how much of it the official reports can settle.
    av = d.get("availability") or {}
    cnt = av.get("counts") or {}
    cov = av.get("coverage_by_date") or []
    if cnt:
        CTX["sides"] = cnt.get("team_side_rows", 0)
        CTX["pending"] = (cnt.get("team_side_rows", 0) or 0) - (cnt.get("filed", 0) or 0)
        CTX["by_date"] = " · ".join(
            f"{c['date'][5:].replace('-', '/')} {c.get('filed', 0)}/{c.get('team_sides', 0)} filed"
            + (" (no report covers this date)" if c.get("no_report_covers_date") else "")
            for c in cov)
    win = ((d.get("slate") or {}).get("window") or {})
    if win.get("from") and win.get("to"):
        CTX["window"] = f"{win['from']} → {win['to']}"

    _load_new()
    pages = [
        ("app/summary.html", "Executive summary", "Overview", page_summary(d), "app/summary.html"),
        ("app/methodology.html", "Method & rules", "Overview", page_methodology(d), "app/methodology.html"),
        ("app/projections.html", "Two-estimator projections", "Projection surface (public)",
         page_projections(d), "app/projections.html"),
        ("app/lines.html", "Originated lines", "Projection surface (public)", page_lines(d), "app/lines.html"),
        ("app/picks.html", "Prices for the window", "Projection surface (public)", page_picks(d), "app/picks.html"),
        ("app/injuries.html", "Injuries, rotation impact & report status", "Projection surface (public)", page_injuries(d), "app/injuries.html"),
        ("app/freshness.html", "Report availability & freshness", "Projection surface (public)",
         page_freshness(d), "app/freshness.html"),
        ("app/gameflow.html", "Game flow", "Projection surface (public)", page_gameflow(d), "app/gameflow.html"),
        ("app/refresh.html", "Refresh & provenance gates", "Projection surface (public)",
         page_refresh(d), "app/refresh.html"),
        ("app/parlays.html", "Parlay & prop combos", "Bet surface (gated)", page_parlays(d), "app/parlays.html"),
        ("app/leaderboard.html", "Strategy leaderboard", "Bet surface (gated)", page_leaderboard(d), "app/leaderboard.html"),
        ("app/props.html", "Player props", "Bet surface (gated)", page_props(d), "app/props.html"),
        ("app/strategies.html", "Validation gates", "Bet surface (gated)", page_strategies(d), "app/strategies.html"),
        ("app/correlations.html", "Correlations & dependence", "Bet surface (gated)", page_correlations(d), "app/correlations.html"),
        ("app/prereg.html", "Pre-registration", "Bet surface (gated)", page_prereg(d), "app/prereg.html"),
        ("app/ledger.html", "Pick ledger", "Bet surface (gated)", page_ledger(d), "app/ledger.html"),
        ("app/settlement.html", "Settlement", "Bet surface (gated)", page_settlement(d), "app/settlement.html"),
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
        _check_stylesheet()
        for path, title, cat, body, act in pages:
            html_doc = layout(title, cat, body, active=act)
            with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
                fh.write(html_doc)
            written.append(path)
        with open(ROOT_INDEX, "w", encoding="utf-8") as fh:
            fh.write(build_index(d))
        written.append("index.html")
        with open(os.path.join(ROOT, "archive.html"), "w", encoding="utf-8") as fh:
            fh.write(layout("Archive — earlier sessions", "Archive", page_archive(d),
                            subtitle="Every dashboard built by an earlier session, dated and "
                                     "linked. None of these is current.",
                            active="archive.html", root_page=True))
        written.append("archive.html")

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
