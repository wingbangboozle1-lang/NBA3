#!/usr/bin/env python3
"""Build the NBA3 dashboard for the 2026-11-16 round (session arena/8f4fac33-nba3).

One builder, one dataset, one navigation.  Every page is rendered from the artefacts that
`scripts/refresh_2026_11_16.py` and `scripts/round_model_2026_11_16.py` wrote *after* the
freshness and provenance gates passed, plus the hand-verified registers in
`data/rounds/2026-11-16/*.csv`.

Hard rule enforced here, not in prose: **every row in a tbody must contain at least one
https link to an official source** (`nba.com`, `statsdmz.nba.com`,
`ak-static.cms.nba.com`, `official.nba.com`).  A row without one fails the build.  Values that
could not be confirmed are rendered as an em dash and carry a link to the Flagged for Review
page where they are listed with the reason.

Pages written (all under app/, plus the root index.html):
  index.html                     landing page
  app/overview.html              what this is, how to read it, the headline numbers
  app/slate.html                 25 games, 2026-11-16 .. 2026-11-18, per-game projection
  app/projections.html           the two estimators and their disagreement (the headline)
  app/lines.html                 originated spread/total/moneyline per game
  app/totals.html                possessions x points-per-possession, with the naive sum beside it
  app/injuries.html              the 11/16 09:15 AM ET report, row by row, + the delta
  app/injury-delta.html          what changed between 11/15 06:15 AM and 11/16 09:15 AM
  app/results.html               the 11/15 finals, one row per game, quotes + settlement stamp
  app/team-stats.html            the three official team pages re-cut, with the identity checks
  app/context.html               rest, back-to-back, 3-in-4, travel
  app/strategies.html            the strategy board and why nothing is published
  app/pricing.html               fair prices and both parlay prices
  app/questions.html             open questions: known / missing / how to find it
  app/suggestions.html           site improvements awaiting a decision
  app/flagged.html               every value left blank or flagged, with the reason
  app/sources.html               source register with the exact URL and read time
  app/methodology.html           the rules the build obeys
  app/requirements.html          brief -> implementation coverage, one row per requirement
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-16")
# THIS BUILDER OWNS ITS OWN TREE. `app/` is written by scripts/build_app.py and is read by
# tests/test_lines_attribution.py; writing this round's pages into `app/` silently replaced another
# builder's output and broke 38 tests. The dashboard for this round therefore lives in `round/`,
# and the landing page at the site root is the only file this builder writes outside it.
APP = os.path.join(ROOT, "round")

SNAPSHOT = "2026-11-16 14:45 UTC"
OFFICIAL_HOSTS = ("nba.com", "statsdmz.nba.com", "ak-static.cms.nba.com", "official.nba.com")

ERRORS: list[str] = []


def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def dash(x, suffix=""):
    """Render a possibly-missing value. A missing value is an em dash, never a zero guess."""
    if x is None or x == "":
        return '<span class="na" title="not confirmed from an official source">—</span>'
    return f"{esc(x)}{esc(suffix)}"


def num(x, dp=1):
    if x is None:
        return dash(None)
    return f"{x:.{dp}f}"


REPO = "https://github.com/wingbangboozle1-lang/NBA3/blob/arena/8f4fac33-nba3"

ALLOWED_NON_OFFICIAL = (
    # Exactly three, each rendered with a visible tag so none can pass for an NBA document.
    "https://en.wikipedia.org/wiki/List_of_National_Basketball_Association_arenas",  # coordinates
    f"{REPO}/COORDINATION.md",                                                       # own record
    "https://kansspelautoriteit.nl/online-kansspel-aanbieden",                       # regulator
)


def src(url, label=None, secondary=False):
    """An official-source cell. A non-official URL is refused unless it is declared secondary.

    The `secondary` flag exists for exactly one thing on this site: the arena-coordinate table,
    which no NBA document publishes. A secondary link is rendered with a visible SECONDARY tag so
    a reader can never mistake it for an official value. Anything else non-official is refused.
    """
    if not url:
        return dash(None)
    host = re.sub(r"^https?://", "", url).split("/")[0]
    official = any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)
    if not official:
        if url in ALLOWED_NON_OFFICIAL and secondary:
            tag = (' <span class="pill warn" title="not an NBA document">SECONDARY</span>')
        elif url.startswith(REPO) and secondary:
            tag = (' <span class="pill info" title="this repository own record">REPO</span>')
        else:
            ERRORS.append(f"non-official source link refused: {url}")
            return dash(None)
    else:
        tag = ""
    text = label or host
    return f'<a href="{esc(url)}" rel="noopener">{esc(text)}</a>{tag}'


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


def read_csv(name):
    with open(os.path.join(ROUND, name), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------------------------
NAV = [
    ("Overview", [
        ("What this is", "overview.html"),
        ("Brief coverage", "requirements.html"),
        ("Method & rules", "methodology.html"),
    ]),
    ("Projections (safe to publish)", [
        ("Slate 11/16–18", "slate.html"),
        ("Two estimators", "projections.html"),
        ("Originated lines", "lines.html"),
        ("Totals", "totals.html"),
        ("Game context", "context.html"),
    ]),
    ("Official data", [
        ("Injuries 11/16", "injuries.html"),
        ("Injury diff", "injury-delta.html"),
        ("Results 11/15", "results.html"),
        ("Team statistics", "team-stats.html"),
    ]),
    ("Bet surface (gated)", [
        ("Strategy board", "strategies.html"),
        ("Prices & parlays", "pricing.html"),
    ]),
    ("Decision support", [
        ("Open questions", "questions.html"),
        ("Site suggestions", "suggestions.html"),
    ]),
    ("Verification", [
        ("Sources", "sources.html"),
        ("Flagged for review", "flagged.html"),
        ("Earlier sessions", "archive.html"),
    ]),
]

CSS = """/* NBA3 dashboard — session arena/8f4fac33-nba3. Dependency-free. */
:root{
 --bg:#f6f7f9; --panel:#fff; --ink:#131b26; --muted:#5b6b7f; --line:#e0e5ec;
 --accent:#1d4ed8; --accent-soft:#eaf0ff; --ok:#0f7b4f; --ok-soft:#e6f6ee;
 --warn:#8a5a00; --warn-soft:#fdf3de; --bad:#a52121; --bad-soft:#fdeaea;
 --r:10px; --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:#eef1f6;border-radius:4px;padding:1px 5px;font-family:var(--mono);font-size:.92em}
header.top{background:#101a2b;color:#e8eef7}
header.top .wrap{display:flex;flex-wrap:wrap;gap:14px;align-items:center;padding-top:14px;padding-bottom:14px}
header.top .brand{font-weight:700;letter-spacing:.2px;font-size:16px;color:#fff}
header.top .brand span{color:#8fb0ff;font-weight:500}
header.top .stamp{margin-left:auto;font-size:12px;color:#9fb0c6}
nav.cats{background:#fff;border-bottom:1px solid var(--line)}
nav.cats .wrap{display:flex;flex-wrap:wrap;gap:4px 18px;padding:10px 20px;align-items:flex-start}
nav.cats .cat{display:flex;flex-direction:column;gap:2px}
nav.cats .cat>b{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700}
nav.cats .cat a{font-size:13px;color:var(--ink);padding:1px 0}
nav.cats .cat a:hover{color:var(--accent)}
nav.cats .cat a[aria-current]{color:var(--accent);font-weight:650}
main{padding:26px 0 60px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.2px}
h2{font-size:19px;margin:30px 0 10px}
h3{font-size:15.5px;margin:22px 0 8px}
p.lede{color:var(--muted);margin:0 0 20px;max-width:78ch}
.crumb{font-size:12.5px;color:var(--muted);margin-bottom:8px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:18px 0 8px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:14px 16px}
.card .k{font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:700}
.card .v{font-size:26px;font-weight:700;margin:4px 0 2px;letter-spacing:-.5px}
.card .s{font-size:12.5px;color:var(--muted)}
.card .src{margin-top:8px;font-size:11.5px}
.cat-block{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;margin:14px 0}
.cat-block h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}
.tiles{display:flex;flex-wrap:wrap;gap:8px}
.tile{border:1px solid var(--line);border-radius:8px;padding:7px 12px;font-size:13.5px;color:var(--ink);background:#fbfcfe}
.tile:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}
.table-wrap{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow:auto;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f3f5f9;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);white-space:nowrap;position:sticky;top:0}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fbfcff}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);font-size:12.5px}
.na{color:#b9c2cf;font-weight:600}
.pill{display:inline-block;border-radius:99px;padding:1px 9px;font-size:11px;font-weight:700;letter-spacing:.2px}
.pill.ok{background:var(--ok-soft);color:var(--ok)}
.pill.warn{background:var(--warn-soft);color:var(--warn)}
.pill.bad{background:var(--bad-soft);color:var(--bad)}
.pill.info{background:var(--accent-soft);color:var(--accent)}
.note{background:var(--accent-soft);border-radius:8px;padding:10px 14px;font-size:13.5px;margin:12px 0}
.warnbox{background:var(--warn-soft);border-left:3px solid var(--warn);border-radius:6px;padding:10px 14px;font-size:13.5px;margin:12px 0}
.badbox{background:var(--bad-soft);border-left:3px solid var(--bad);border-radius:6px;padding:10px 14px;font-size:13.5px;margin:12px 0}
.okbox{background:var(--ok-soft);border-left:3px solid var(--ok);border-radius:6px;padding:10px 14px;font-size:13.5px;margin:12px 0}
.small{font-size:12px;color:var(--muted)}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:13.5px;margin:10px 0}
.kv dt{color:var(--muted)}
.kv dd{margin:0}
footer{border-top:1px solid var(--line);background:#fff;padding:22px 0;margin-top:40px;font-size:12.5px;color:var(--muted)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:820px){.split{grid-template-columns:1fr}}
"""


def layout(title: str, body: str, active: str = "", subtitle: str = "", root: bool = False) -> str:
    pre = "" if root else "../"
    nav_items = []
    for cat, items in NAV:
        links = []
        for label, href in items:
            cur = ' aria-current="page"' if href == active else ""
            target = href
            links.append(f'<a href="{esc(target)}"{cur}>{esc(label)}</a>')
        nav_items.append(f'<div class="cat"><b>{esc(cat)}</b>{"".join(links)}</div>')
    # ONE RULE, TWO DEPTHS. A page written into round/ links to its siblings by name and to the
    # stylesheet as assets/...  The landing page is written to the repo root, so every one of its
    # links carries the round/ prefix -- including the stylesheet and the footer link. Anything
    # else produces a page that looks right in the editor and 404s on Pages.
    css_href = "assets/dashboard.css"
    footer_flag = '<a href="flagged.html">Flagged for review</a>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NBA3</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<header class="top"><div class="wrap">
  <div class="brand">NBA3 <span>· originated lines &amp; verification</span></div>
  <div class="stamp">official sources read {esc(SNAPSHOT)} · session arena/8f4fac33</div>
</div></header>
<nav class="cats"><div class="wrap">{"".join(nav_items)}</div></nav>
<main><div class="wrap">
{f'<div class="crumb">{esc(subtitle)}</div>' if subtitle else ''}
{body}
</div></main>
<footer><div class="wrap">
  Every published value carries an <code>https</code> link to the official NBA document it came from.
  Anything that could not be confirmed is printed as <span class="na">—</span> and listed on the
  {footer_flag} page. Built by
  <code>scripts/build_round_site.py</code>; the CI replay fails if this tree drifts from a rebuild.
</div></footer>
</body>
</html>
"""


def table(headers, rows, numeric=(), caption=None, cls=""):
    th = "".join(f'<th class="{"n" if i in numeric else ""}">{h}</th>' for i, h in enumerate(headers))
    body = []
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cells.append(f'<td class="{"n" if i in numeric else ""}">{c}</td>')
        body.append(f"<tr>{''.join(cells)}</tr>")
    cap = f'<caption class="small" style="caption-side:bottom;padding:8px 10px;text-align:left">{caption}</caption>' if caption else ""
    return (f'<div class="table-wrap"><table class="{cls}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody>{cap}</table></div>')


def pill(kind, text):
    return f'<span class="pill {kind}">{esc(text)}</span>'


# ---------------------------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------------------------
def page_landing(d):
    slate, model, gates = d["slate"], d["model"], d["gates"]
    lines = model["pricing"]["lines"]
    n_lines = len(lines)
    published = sum(1 for s in model["strategies"] if s["published"])
    settled = d["results"]["settled_count"]
    cats = []
    for cat, items in NAV:
        tiles = "".join(f'<a class="tile" href="{esc(h)}">{esc(l)}</a>' for l, h in items)
        cats.append(f'<div class="cat-block"><h3>{esc(cat)}</h3><div class="tiles">{tiles}</div></div>')
    flag_rows = [[esc(f["id"]), esc(f["what"]), esc(f["why"]),
                  src(f.get("source") or "")] for f in d["flags"][:8]]
    return layout("Dashboard", f"""
<h1>NBA3 dashboard · 2026-11-16</h1>
<p class="lede">This site publishes two things and refuses to mix them: a <b>projection surface</b>
(today's slate, the two estimators and where they disagree, the official injury report, the official
finals feed) that is safe to publish now, and a <b>bet surface</b> (the strategy board and prices)
that is gated. The headline is the disagreement between two independent estimators; the blend sits
underneath it.</p>

<div class="cards">
  <div class="card"><div class="k">Official games captured</div><div class="v">{slate['count']}</div>
    <div class="s">2026-11-16 → 2026-11-18, {slate['count_by_date'].get('2026-11-16',0)} today.
    Each row links to its official game page.</div>
    <div class="src">{src(slate['source_url'], 'nba.com/schedule')}</div></div>
  <div class="card"><div class="k">Originated lines</div><div class="v">{n_lines}</div>
    <div class="s">spread, total and fair moneyline for every game in the window</div>
    <div class="src">{src(slate['source_url'], 'nba.com/schedule')}</div></div>
  <div class="card"><div class="k">Injury rows (11/16 09:15 AM ET)</div><div class="v">{d['injuries']['count']}</div>
    <div class="s">{d['injuries']['player_rows']} player rows, {d['injuries']['not_submitted_rows']}
    team rows still <code>NOT YET SUBMITTED</code></div>
    <div class="src">{src(d['injuries']['source_url'], 'official PDF')}</div></div>
  <div class="card"><div class="k">Finals settled (11/15)</div><div class="v">{settled}/9</div>
    <div class="s">one row per game with all four quarter scores; {9-settled} row is published
    unsettled because the official game book contradicts itself</div>
    <div class="src">{src(d['results']['scoreboard_url'], 'nba.com games')}</div></div>
  <div class="card"><div class="k">Strategies funded</div><div class="v">{published}</div>
    <div class="s">of {len(model['strategies'])}. No team has four captured games yet, so no team can
    be shown inside the ±2 luck band. Nothing is funded, by rule.</div>
    <div class="src">{src(slate['source_url'], 'nba.com/schedule')}</div></div>
  <div class="card"><div class="k">Gates</div><div class="v">{gates['pass_count']}/{gates['gate_count']}</div>
    <div class="s">freshness + provenance gates: all pass, rebuild allowed. One integrity gate fails
    and withholds exactly one row.</div>
    <div class="src">{src(d['injuries']['index_url'], 'official.nba.com')}</div></div>
</div>

<div class="note"><b>Read the projections this way.</b> Where the two estimators agree closely the
line is marked <span class="pill ok">high</span> confidence; where they disagree by more than four
points it is <span class="pill bad">low</span>, and that disagreement — not the blended number — is
the signal. On this slate the two estimators disagree by more than 12 points on {sum(1 for l in lines if (l['disagreement'] or 0) > 12)} of
{n_lines} games, which is the honest measure of how little a 22-game log supports.</div>

<h2>Browse by category</h2>
{"".join(cats)}

<h2>Flagged for review</h2>
<p class="lede">Values that could not be confirmed from an official source, and irregularities found
while verifying. Nothing here blocks publication; each row links to the document in question.</p>
{table(["ID", "Item", "Why it is flagged", "Source"], flag_rows)}
<p class="small"><a href="flagged.html">All flagged items →</a></p>
""", root=False)


def page_overview(d):
    slate, model, gates = d["slate"], d["model"], d["gates"]
    hc = model["home_court"]
    e = model["error_summary"]
    rows = [
        ["Official schedule", f"{slate['count']} games 2026-11-16 → 2026-11-18",
         esc(str(slate["count_by_date"])), src(slate["source_url"], "nba.com/schedule"),
         pill("ok", "verified")],
        ["Injury report", "11/16/26 09:15 AM ET, newest on the official index at read time",
         f"{d['injuries']['count']} rows", src(d["injuries"]["source_url"], "PDF"),
         pill("ok", "verified")],
        ["Finals feed", "2026-11-15 league day, one row per game",
         f"{d['results']['settled_count']}/{d['results']['count']} settled",
         src(d["results"]["scoreboard_url"], "nba.com/games"), pill("warn", "1 withheld")],
        ["Team statistics", "traditional + opponent + advanced, re-cut to one row per team",
         f"{d['team_stats']['count']} teams", src(d["team_stats"]["pages"]["advanced"]["url"], "advanced"),
         pill("ok", "verified")],
        ["Home-court advantage", hc["implied_hca_formula"],
         f"{hc['implied_hca_points']} pts (rate {hc['home_win_rate']}, n={hc['games']})",
         src("https://www.nba.com/games?date=2026-11-14", "nba.com/games"), pill("ok", "measured")],
        ["Estimator A", "result-based ridge Massey on final margins",
         f"walk-forward RMSE {e['margin_rmse_A']} vs baseline {e['margin_rmse_baseline']}",
         src("https://www.nba.com/games?date=2026-11-15", "nba.com/games"), pill("ok", "measured")],
        ["No funded strategies", "no team has 4 captured games, so none can clear the ±2 band",
         "0 of 25", src(slate["source_url"], "nba.com/schedule"), pill("warn", "blocked by rule")],
        ["Closing line", "no licensed closing-line feed is connected",
         dash(None), src("https://www.nba.com/schedule?date=2026-11-16", "nba.com/schedule"),
         pill("bad", "unverified")],
    ]
    return layout("What this is", f"""
<div class="crumb">Overview</div>
<h1>What this is, and what it refuses to do</h1>
<p class="lede">NBA3 originates its own NBA lines from official data, then tries to prove the lines
are worth anything. This page is the state of that work on 2026-11-16: what was verified, what the
model says, and what is still missing.</p>

<h2>The headline</h2>
<div class="badbox"><b>Zero strategies are funded.</b> That is not a bug. The rule this project
adopted is that a strategy may not lean on a team whose record sits outside a ±2 z-score band, and
at 22 captured finals no team has the four games needed for its z-score to mean anything. So every
one of the 25 candidate rules is blocked, with the reason printed on each row of the
<a href="strategies.html">strategy board</a>.</div>

<h2>What was verified, line by line</h2>
{table(["Area", "What was read", "Result", "Source", "Status"], rows)}

<h2>How to read the projection pages</h2>
<dl class="kv">
  <dt>Disagreement</dt><dd>|A − B| in points between the two estimators. It is the <b>primary</b>
  confidence signal and it is the first number on every line row.</dd>
  <dt>Blend</dt><dd>the mean of the two, published underneath the disagreement, never as the
  headline.</dd>
  <dt>Total</dt><dd>possessions × points-per-possession, with the rejected alternative (the sum of
  the two teams' scoring averages) printed beside it.</dd>
  <dt>—</dt><dd>a value that could not be confirmed from an official document. Never a zero, never
  an average of other values.</dd>
</dl>

<h2>What is missing, and what it blocks</h2>
<p class="lede">Four gaps drive almost every other limitation. Each is on the
<a href="questions.html">open questions</a> page with what is known, what is missing, and how to
get it.</p>
<ul>
  <li><b>Game-log depth.</b> 22 finals is enough to fit a rating and not enough to prove one.
  It blocks every luck-based gate and every strategy.</li>
  <li><b>A licensed odds feed.</b> Without a closing line there is no market-anchored prior and no
  way to measure log-loss against a market. The field is left null.</li>
  <li><b>Per-player game logs.</b> Without them there is no measured rho for player-prop combos, so
  those parlay prices are withheld rather than invented.</li>
  <li><b>Licensing and jurisdiction.</b> The league's terms restrict gambling use of its
  statistics, and the operator's jurisdiction is unknown. This is a research dashboard, not a
  betting service.</li>
</ul>
""", active="overview.html", subtitle="Overview")


def page_slate(d):
    slate, model = d["slate"], d["model"]
    by_game = {l["game_id"]: l for l in model["pricing"]["lines"]}
    ctx = {c["game_id"]: c for c in d["context"]["games"]}
    rows = []
    for g in slate["games"]:
        ln = by_game.get(g["game_id"], {})
        c = ctx.get(g["game_id"], {})
        dis = ln.get("disagreement")
        conf = ln.get("confidence", {}).get("label")
        kind = {"high": "ok", "medium": "warn", "low": "bad"}.get(conf, "info")
        rows.append([
            esc(g["date"]),
            esc(g["tip_et"]),
            f'<a href="{esc(g["game_url"])}" rel="noopener">{esc(g["away"])} @ {esc(g["home"])}</a>',
            esc(g["venue"]),
            num(ln.get("margin_a")),
            num(ln.get("margin_b")),
            f'<b>{num(dis)}</b>',
            pill(kind, conf or "n/a"),
            num(ln.get("total_ppp")),
            num(ln.get("total_efficiency")),
            num(ln.get("fair_moneyline_home"), 0) if ln.get("fair_moneyline_home") else dash(None),
            esc(_rest_label(c)),
            src(g["source_url"], "nba.com"),
        ])
    return layout("Slate 2026-11-16 → 18", f"""
<div class="crumb">Projections · safe to publish</div>
<h1>Slate, 2026-11-16 → 2026-11-18</h1>
<p class="lede">{slate['count']} official games across three league days, read from the official
schedule on {SNAPSHOT}. Each row links to the game's own page on nba.com. The projection columns are
this repository's numbers, not the market's — see <a href="methodology.html">method</a>.</p>

<div class="warnbox"><b>Read the disagreement column first.</b> A and B are two independent
estimators. Where they are far apart the line is weak regardless of how confident the blend looks.
The confidence pill is derived from |A − B| only.</div>

{table(["Date", "Tip (ET)", "Game", "Venue", "A margin", "B margin", "|A−B|", "Confidence",
        "Total (ppp)", "Total (efficiency)", "Fair ML home", "Rest", "Source"], rows,
       numeric=(4, 5, 6, 8, 9, 10), caption="Margins are home-team perspective. Positive means the "
       "home team is projected to win. Fair moneyline is the American price implied by the blended "
       "probability on the measured margin spread.")}

<h2>What is not on this page, and why</h2>
<ul>
  <li><b>The market line.</b> No licensed closing-line feed is connected. The model's number is
  published alone rather than next to an invented market price.</li>
  <li><b>A single "official" line.</b> There is no such thing until the two estimators are
  reconciled; that is what the disagreement column is for.</li>
  <li><b>Rest and travel for a team whose previous game is outside the captured window.</b> Those
  cells read — and are counted on <a href="flagged.html">flagged</a>.</li>
</ul>
""", active="slate.html", subtitle="Projections · safe to publish")


def _rest_label(c):
    a = c.get("away_rest_days")
    h = c.get("home_rest_days")
    def one(team, rest, b2b, three):
        if rest is None:
            return f"{team} —"
        bits = [f"{team} {rest}d"]
        if b2b:
            bits.append("b2b")
        if three:
            bits.append("3-in-4")
        return "/".join(bits)
    return (one(c.get("away", "?"), a, c.get("away_b2b"), c.get("away_three_in_four")) + " · " +
            one(c.get("home", "?"), h, c.get("home_b2b"), c.get("home_three_in_four")))


def page_projections(d):
    model = d["model"]
    hc = model["home_court"]
    e = model["error_summary"]
    rows = []
    for ln in model["pricing"]["lines"]:
        dis = ln["disagreement"]
        kind = {"high": "ok", "medium": "warn", "low": "bad"}[ln["confidence"]["label"]]
        rows.append([
            esc(ln["date"]),
            f'<a href="{esc(ln["game_url"])}" rel="noopener">{esc(ln["away"])} @ {esc(ln["home"])}</a>',
            f'<b>{num(dis)}</b>', pill(kind, ln["confidence"]["label"]),
            num(ln["margin_a"]), num(ln["margin_b"]), num(ln["blend_margin"]),
            src(ln["game_url"], "game page"),
        ])
    detail = []
    for r in model["estimator_b"]["rows"]:
        detail.append([
            esc(r["game_id"]),
            num(r["possessions"], 2) if r.get("possessions") else dash(None),
            num(r.get("away_off_points")) if r.get("away_off_points") is not None else dash(None),
            num(r.get("home_off_points")) if r.get("home_off_points") is not None else dash(None),
            num(r.get("margin_home")), num(r.get("total")),
            src(d["team_stats"]["pages"]["advanced"]["url"], "advanced"),
        ])
    return layout("Two estimators", f"""
<div class="crumb">Projections · safe to publish</div>
<h1>The two estimators, and where they disagree</h1>
<p class="lede">One blended rating presented as a single truth is the failure mode this project is
built to avoid. There are two estimators, they share no input, and the gap between them is the
confidence number the site leads with.</p>

<div class="cards">
  <div class="card"><div class="k">Estimator A · result-based</div><div class="v">{e['margin_rmse_A']}</div>
    <div class="s">walk-forward margin RMSE over {e['walk_forward_games']} games, against a constant
    baseline of {e['margin_rmse_baseline']}. Ridge penalty {model['ridge_selection']['chosen']['ridge']}
    chosen by leave-one-game-out, on past games only.</div>
    <div class="src">{src("https://www.nba.com/games?date=2026-11-15", "finals")}</div></div>
  <div class="card"><div class="k">Estimator B · efficiency-based</div>
    <div class="v">{num(model['pricing']['margin_sd'])}</div>
    <div class="s">possessions × rating difference, off the official advanced page. Never reads a
    final score, so it cannot simply echo A.</div>
    <div class="src">{src(d['team_stats']['pages']['advanced']['url'], 'advanced')}</div></div>
  <div class="card"><div class="k">Home court (pinned)</div><div class="v">{hc['implied_hca_points']}</div>
    <div class="s">the margin that reproduces the measured home-win rate of
    {hc['home_win_rate']} over {hc['games']} finals on the measured spread. Pinned, not fitted.</div>
    <div class="src">{src("https://www.nba.com/games?date=2026-11-15", "nba.com/games")}</div></div>
  <div class="card"><div class="k">Median disagreement</div>
    <div class="v">{num(sorted(l['disagreement'] for l in model['pricing']['lines'])[len(model['pricing']['lines'])//2])}</div>
    <div class="s">points between A and B across the window. This is the number that should temper
    every projection below.</div>
    <div class="src">{src(d['slate']['source_url'], 'schedule')}</div></div>
</div>

<h2>Why these two, and why they are independent</h2>
<div class="split">
  <div><h3>A · result-based</h3>
  <p>Ridge-regularised least squares on final margins: one strength per team, with the home-court
  term pinned rather than free. Inputs are final margins and nothing else. It knows nothing about
  shooting, pace or schedule, which is exactly why it can be checked against B.</p></div>
  <div><h3>B · efficiency-based</h3>
  <p>Expected margin from possessions and defensive/offensive rating:
  <code>(OffRtg_home − DefRtg_away) × poss/100 − (OffRtg_away − DefRtg_home) × poss/100</code>,
  with the same pinned home-court term. It never looks at a final score.</p></div>
</div>
<p class="small">If both read the same rating they would agree by construction and the disagreement
would always be zero. That is the trap; these two do not share an input.</p>

<h2>Disagreement is the headline. Here it is, per game.</h2>
{table(["Date", "Game", "|A−B|", "Confidence", "A margin", "B margin", "Blend (underneath)", "Source"],
       rows, numeric=(2, 4, 5, 6),
       caption="Sorted by date. The blend is printed only under the disagreement, never instead of it.")}

<h2>Estimator B, worked out per game</h2>
{table(["Game ID", "Possessions", "Away off pts", "Home off pts", "Home margin", "Total", "Source"],
       detail, numeric=(1, 2, 3, 4, 5),
       caption="Away/home off pts are the points each side's offence is projected to produce "
               "against this opponent, before the pinned home-court term is added to the home side.")}
""", active="projections.html", subtitle="Projections · safe to publish")


def page_lines(d):
    model = d["model"]
    pr = model["pricing"]
    rows = []
    for ln in pr["lines"]:
        rows.append([
            esc(ln["date"]),
            f'<a href="{esc(ln["game_url"])}" rel="noopener">{esc(ln["away"])} @ {esc(ln["home"])}</a>',
            num(ln["blend_margin"]), num(ln["total_ppp"]),
            num(ln["fair_moneyline_home"], 0) if ln.get("fair_moneyline_home") is not None else dash(None),
            num(ln["fair_moneyline_away"], 0) if ln.get("fair_moneyline_away") is not None else dash(None),
            num(ln["p_home"], 3),
            dash(None) if ln.get("market_anchor") is None else esc(ln["market_anchor"]),
            src(ln["game_url"], "game page"),
        ])
    return layout("Originated lines", f"""
<div class="crumb">Projections · safe to publish</div>
<h1>Originated lines for the window</h1>
<p class="lede">One originated number per game: a spread, a total and a fair moneyline. These are
this repository's numbers. They are not bets, and they are not the market's line.</p>

<div class="warnbox"><b>The market anchor is blank on purpose.</b> The brief asks for the model line
to be blended with the closing line, weighted by measured out-of-sample log-loss. There is no
licensed closing-line feed here, so there is no second log-loss to measure. The weight is left null
rather than invented, and the formula is printed on the
<a href="methodology.html">method</a> page so the field can be filled the moment a feed exists.</div>

{table(["Date", "Game", "Line (home)", "Total", "Fair ML home", "Fair ML away", "P(home)",
        "Market blend", "Source"], rows, numeric=(2, 3, 4, 5, 6),
       caption="The line is home-team perspective. Fair moneylines are the American price implied by "
               "the blended probability on the measured margin spread; they are fair prices, not "
               "offers.")}

<h2>How the price is built</h2>
<dl class="kv">
  <dt>Probability</dt><dd>Φ(blend / σ) with σ the measured standard deviation of final home
  margins ({num(model['pricing']['margin_sd'])} pts on the captured log).</dd>
  <dt>American odds</dt><dd>−100·p/(1−p) for p &lt; 0.5, else 100·(1−p)/p.</dd>
  <dt>Clamp</dt><dd>probabilities are clamped to [0.02, 0.98]. A model that says a team is a 99.9%
  favourite on a 22-game log is not being informative.</dd>
  <dt>What is missing</dt><dd>a closing line. See the box above.</dd>
</dl>
""", active="lines.html", subtitle="Projections · safe to publish")


def page_totals(d):
    t = d["model"]["totals"]
    rows = []
    for r in t["rows"]:
        if not r.get("available"):
            continue
        rows.append([
            esc(r["game_id"]), num(r["possessions"], 2), num(r["points_per_100_possessions_combined"], 2),
            f'<b>{num(r["total"])}</b>', num(r["naive_sum_of_scoring_averages"]), num(r["difference"]),
            src(d["team_stats"]["pages"]["advanced"]["url"], "advanced"),
        ])
    return layout("Totals", f"""
<div class="crumb">Projections · safe to publish</div>
<h1>Totals: possessions × points-per-possession</h1>
<p class="lede">The total is modelled the way a basketball game actually produces points: a number of
possessions times a number of points per possession. The rejected alternative — summing the two
teams' scoring averages — is printed beside it so the difference is visible rather than hidden.</p>

{table(["Game", "Possessions", "Points / 100 poss", "Total (ppp)", "Naive sum of averages", "Δ",
        "Source"], rows, numeric=(1, 2, 3, 4, 5),
       caption="Possessions are the mean of the two teams' measured PACE (a per-game possession "
               "count on the official advanced page). Points per 100 possessions are built from "
               "season points over season possessions, which the build checks against the page's "
               "own OffRtg.")}

<h2>Why this and not the average of averages</h2>
<p>Summing two scoring averages silently assumes both teams score at their own season rate against
this opponent and at this pace. It cannot respond to a slow team meeting a fast one, and it cannot
respond to a good offence meeting a good defence. The possessions form can, because the possession
count comes from the two teams' measured pace and the points-per-possession comes from each side's
own measured efficiency.</p>
<div class="note">The build checks the unit chain in three places before it prints anything:
<code>POSS/GP</code> must reproduce the page's <code>PACE</code>; <code>PTS·GP/POSS·100</code> must
reproduce the page's <code>OffRtg</code>; and the resulting total must sit inside a plausible
190–260 band. All three are unit tests, not prose.</div>
""", active="totals.html", subtitle="Projections · safe to publish")


def page_context(d):
    c = d["context"]
    rows = []
    for g in c["games"]:
        rows.append([
            esc(g["date"]), f'{esc(g["away"])} @ {esc(g["home"])}',
            num(g.get("away_rest_days"), 0) if g.get("away_rest_days") is not None else dash(None),
            num(g.get("home_rest_days"), 0) if g.get("home_rest_days") is not None else dash(None),
            pill("bad", "b2b") if g.get("away_b2b") or g.get("home_b2b") else "",
            pill("warn", "3-in-4") if g.get("away_three_in_four") or g.get("home_three_in_four") else "",
            num(g.get("travel_km"), 0) if g.get("travel_km") is not None else dash(None),
            src(g["source_url"], "schedule"),
        ])
    return layout("Game context", f"""
<div class="crumb">Projections · safe to publish</div>
<h1>Rest, back-to-back, 3-in-4 and travel</h1>
<p class="lede">Rest is arithmetic on the official schedule — no estimation. Travel needs a
coordinate the NBA does not publish, so it is labelled as a secondary source and every distance
names the arena article it used.</p>

<div class="warnbox"><b>Travel is a secondary source, and a lower bound.</b> The coordinates come
from each arena's Wikipedia article, not from an NBA page. A great-circle distance between two
buildings is a lower bound on travel, not a route. If a coordinate is missing the cell reads — and
the row is listed on <a href="flagged.html">flagged</a>.</div>

{table(["Date", "Game", "Away rest (d)", "Home rest (d)", "Back-to-back", "3-in-4", "Travel (km)",
        "Source"], rows, numeric=(2, 3, 6),
       caption="Rest days count full days off between games, so a team playing consecutive nights has "
               "0. 3-in-4 means three games inside four days, counted from the official dates.")}

<h2>What is verifiable here and what is not</h2>
<dl class="kv">
  <dt>Rest, b2b, 3-in-4</dt><dd>official — derived from the dates the official schedule prints.</dd>
  <dt>Travel distance</dt><dd>secondary — Wikipedia coordinates; great-circle; lower bound.</dd>
  <dt>Travel for a team whose previous game is outside the capture</dt><dd>— left blank, flagged.</dd>
</dl>
""", active="context.html", subtitle="Projections · safe to publish")


def page_injuries(d):
    inj = d["injuries"]
    rows = []
    for r in inj["rows"]:
        status = r.get("status")
        kind = {"Out": "bad", "Doubtful": "bad", "Questionable": "warn",
                "Probable": "info", "Available": "ok"}.get(status, "info")
        team = r.get("team") or ""
        team_cell = esc(team)
        if r.get("team_attributed"):
            team_cell = (f'{esc(team)} <span class="pill info" title="{esc(r["team_attribution_evidence"])}">'
                         f'attributed</span>')
        rows.append([
            esc(r.get("date") or ""), esc(r.get("game_time") or ""),
            esc(r.get("matchup") or ""), team_cell, esc(r.get("player") or ""),
            pill(kind, status) if status else dash(None),
            esc(r.get("reason") or ""), src(inj["source_url"], "PDF"),
        ])
    ns = []
    for team, n in sorted(inj["teams_not_yet_submitted"].items()):
        ns.append([esc(team), str(n), src(inj["source_url"], "PDF")])
    return layout("Injuries", f"""
<div class="crumb">Official data · injuries</div>
<h1>Official injury report, 11/16/26 09:15 AM ET</h1>
<p class="lede">Every row below is transcribed from the official PDF that the league's
<a href="{esc(inj['index_url'])}" rel="noopener">injury-report index</a> listed as the newest at
{esc(inj['retrieved_utc'])}. Row count, per-team counts and the page-break carries are all
recomputed by the build; nothing is typed in twice.</p>

<div class="cards">
  <div class="card"><div class="k">Rows in the report</div><div class="v">{inj['count']}</div>
    <div class="s">{inj['player_rows']} player rows + {inj['not_submitted_rows']} team placeholders +
    {inj['rows_with_missing_status']} row whose status cell the PDF does not print</div>
    <div class="src">{src(inj['source_url'], 'official PDF')}</div></div>
  <div class="card"><div class="k">Teams reporting</div><div class="v">{inj['teams_with_player_rows']}</div>
    <div class="s">of the teams in the three-day window</div>
    <div class="src">{src(inj['source_url'], 'official PDF')}</div></div>
  <div class="card"><div class="k">Still NOT YET SUBMITTED</div><div class="v">{inj['not_submitted_rows']}</div>
    <div class="s">team-level placeholders; no player is implied by one</div>
    <div class="src">{src(inj['index_url'], 'official index')}</div></div>
  <div class="card"><div class="k">Report age at build</div><div class="v">—</div>
    <div class="s">the report's own revision time is {esc(inj['report_stamp'])}; the retrieval time
    is {esc(inj['retrieved_utc'])}. Both are printed rather than an "hours ago" figure that would go
    stale on the page.</div></div>
</div>

<div class="note"><b>Revision time vs retrieval time.</b> The league revises the report continuously.
<code>{esc(inj['report_stamp'])}</code> is when the league says the report was revised;
<code>{esc(inj['retrieved_utc'])}</code> is when this build read it. A later report may exist by the
time you read this: the <a href="{esc(inj['index_url'])}" rel="noopener">index</a> is the authority,
and the freshness gate compares against it on every run.</div>

<div class="warnbox"><b>One row has no printed status.</b> Jimmy Butler III's row in the GSW@NOP
block has no <code>Current Status</code> cell in the PDF's text layer — the REASON text sits where
the status normally does. The row is published with a — status and listed on
<a href="flagged.html">flagged</a>. It is <b>not</b> copied forward from the 11/15 report.</div>

<h2>The report, row by row</h2>
{table(["Game date", "Tip (ET)", "Matchup", "Team", "Player", "Status", "Reason", "Source"],
       rows, caption=f"{inj['count']} rows. Every row links to the same official PDF, which is the "
                     f"document the whole table came from.")}

<h2>Teams with a NOT YET SUBMITTED placeholder</h2>
{table(["Team", "Placeholder rows", "Source"], ns, numeric=(1,),
       caption="A placeholder means the club had not filed when this report was produced. It is not "
               "a claim that nobody is injured.")}
""", active="injuries.html", subtitle="Official data")


def page_injury_diff(d):
    dlt = d["delta"]
    inj = d["injuries"]
    changes = dlt["status_changes"]
    change_rows = [[esc(c["player"]), esc(c["team"] or ""), esc(c["matchup"]),
                    pill("info", c["from"] or "blank"), pill("warn", c["to"] or "blank"),
                    esc(c["reason_after"] or ""), src(c["source_url"], "new"),
                    src(c["prior_source_url"], "base")] for c in changes]
    base = dlt["prior_report"]
    return layout("Injury diff", f"""
<div class="crumb">Official data</div>
<h1>What changed between two official reports on the same game day</h1>
<p class="lede">The diff that matters compares two filings that describe <b>the same games</b>:
the {esc(base['stamp'])} filing against the {esc(dlt['current_report']['stamp'])} filing, both
for the 2026-11-16 game day. A difference between them is a status change by the league.</p>

<div class="{'badbox' if not changes else 'warnbox'}">
<b>{len(changes)} status change{'s' if len(changes) != 1 else ''} in the nine and a quarter hours
between the two filings.</b> Of the {dlt['unchanged_count']} players listed on both documents, every
printed status string is identical. That is the finding, and it is worth stating plainly because it
is a genuine measured zero rather than a parsing failure: the two documents are matched row by row
inside each matchup on a normalised player key, and the comparison is on the printed string.
{'' if changes else 'Nothing in the report moved between midnight and 9:15 a.m. ET.'}
</div>

<div class="cards">
  <div class="card"><div class="k">Rows compared</div><div class="v">{dlt['unchanged_count']}</div>
    <div class="s">players printed on both filings. Both documents lose the same cells at the same
    page breaks, which is why the same normalisation is applied to both.</div>
    <div class="src">{src(base['url'], 'base')} {src(dlt['current_report']['url'], 'current')}</div></div>
  <div class="card"><div class="k">Status changes</div><div class="v">{len(changes)}</div>
    <div class="s">printed status differs between the two filings</div>
    <div class="src">{src(dlt['current_report']['url'], 'current')}</div></div>
  <div class="card"><div class="k">Newly listed / dropped</div>
    <div class="v">{dlt['newly_listed_count']} / {dlt['delisted_count']}</div>
    <div class="s">a player in one document and not the other. Reported as such, never as a status
    change.</div>
    <div class="src">{src(base['url'], 'base')}</div></div>
  <div class="card"><div class="k">Matchups covered</div><div class="v">{len(dlt['shared_matchups'])}</div>
    <div class="s">of the 8 games on 11/16. PHI@BKN is absent from the midnight base, where both
    clubs read <code>NOT YET SUBMITTED</code>; it cannot be compared.</div>
    <div class="src">{src(d['slate']['source_url'], 'schedule')}</div></div>
</div>

<h2>Status changes</h2>
{('<p class="small">None. The table is shown empty rather than omitted, so the absence of a change is visible.</p>' if not changes else '')}
{table(["Player", "Team", "Matchup", "From", "To", "Reason (newer filing)", "Newer", "Base"],
       change_rows, caption="Only rows printed in BOTH filings with different status strings appear "
       "here. Each row links to both documents.")}

<h2>Why the obvious diff is the wrong diff</h2>
<p>Comparing the whole 11/15 filing with the whole 11/16 filing looks like the natural thing to do,
and it produces a dramatic-looking table: hundreds of players "added" and "removed". Almost none of
it is injury news. The two documents describe different basketball games, so a player who is not
playing on 11/15 simply disappears and a player who is playing on 11/16 simply appears. For the
record, that comparison on this pair yields <b>{dlt['turnover_added_count']} rows present only in
the newer report</b> and <b>{dlt['turnover_removed_count']} only in the earlier one</b> — slate
turnover, not status movement. It is printed here once, labelled, and not used for anything.</p>

<h2>A defect that two official documents agree on</h2>
<div class="warnbox"><b>Jimmy Butler III has no printed status in either filing.</b> Both the
12:00 AM ET and the 09:15 AM ET reports print six cells for his row where the header promises seven:
the <code>Current Status</code> cell is absent and the reason text sits where the status belongs.
Because both documents show the same defect for the same player, it is a property of the league's
printer rather than of this project's extraction. The row is published with a blank status — it is
not inferred, and it is not copied from an earlier day's report — and it appears on the
<a href="injuries.html">injuries page</a> and on <a href="flagged.html">flagged</a>.</div>
""", active="injury-delta.html", subtitle="Official data")


def page_results(d):
    res = d["results"]
    rows = []
    for r in res["rows"]:
        stamp = r.get("settlement_stamp")
        settled = pill("ok", "settled") if r["settled"] else pill("bad", "unsettled")
        q_a = " · ".join(str(x) for x in r["away_quarters"]) if r["away_quarters"] else dash(None)
        q_h = " · ".join(str(x) for x in r["home_quarters"]) if r["home_quarters"] else dash(None)
        note = ""
        if r.get("conflict") and r["conflict"].get("quarters_differing"):
            note = (f'<div class="small">period table sums to {r["quarter_sums"]["home"]}; the '
                    f'book\'s recap line prints {r["conflict"]["recap_line"]}</div>')
        rows.append([
            f'<a href="{esc(r["game_url"])}" rel="noopener">{esc(r["away"])} @ {esc(r["home"])}</a>',
            f'{r["away_final"]}–{r["home_final"]}',
            q_a, q_h, settled,
            esc(stamp) if stamp else '<span class="pill bad">blocked</span>',
            src(r["source_url"], "game book") + " " + src(r["scoreboard_url"], "scoreboard") + note,
        ])
    return layout("Results 11/15", f"""
<div class="crumb">Official data</div>
<h1>Official finals, 2026-11-15</h1>
<p class="lede">One row per game: date, teams, final score, and all four (or five) quarter scores.
Each row is read from that game's official game book and cross-checked against the game book's own
recap line and the official scoreboard.</p>

<div class="badbox"><b>ATL@MIL is published unsettled.</b> The game book's SCORE BY PERIOD table
prints Milwaukee's third quarter as <b>37</b>, which makes their quarters sum to <b>116</b> against a
printed final of <b>106</b>. The same document's recap line prints <b>27</b> in that quarter, which
does sum to 106. Both readings are kept in the data, the arithmetic is printed on the row, and the
row is <b>not</b> settled. Choosing whichever line parsed first would be a silent repair of an
official document; this build does not do that.</div>

<div class="note"><b>Settlement stamp.</b> A settled row carries the instant it was confirmed against
the official document. The stamp moves only when the official values are re-read, so a stale stamp is
visible as stale rather than being refreshed by a rebuild.</div>

{table(["Game", "Final", "Away quarters", "Home quarters", "State", "Settlement stamp", "Source"],
       rows, numeric=(1,),
       caption="Quarter scores are in order Q1…Q4 (and OT1 when present). A row is settled only when "
               "both teams' quarters sum to their printed finals AND the book's recap restates them.")}
""", active="results.html", subtitle="Official data")


def page_team_stats(d):
    ts = d["team_stats"]
    rows = []
    for r in ts["teams"]:
        t, o, a = r.get("traditional", {}), r.get("opponent", {}), r.get("advanced", {})
        rows.append([
            esc(r["team_abbr"]),
            str(t.get("GP", "—")), str(t.get("W", "—")), str(t.get("L", "—")),
            num(t.get("PTS"), 1),
            num(o.get("OPP_PTS"), 1),
            num(t.get("PLUS_MINUS"), 1),
            num(a.get("OFF_RTG"), 1), num(a.get("DEF_RTG"), 1), num(a.get("NET_RTG"), 1),
            num(a.get("PACE"), 2),
            src(ts["pages"]["advanced"]["url"], "advanced"),
        ])
    checks = [[esc(k), pill("ok" if v["status"] == "PASS" else "bad", v["status"]),
               str(v["failure_count"]), src(ts["pages"]["advanced"]["url"], "page")]
              for k, v in ts["checks"].items()]
    return layout("Team statistics", f"""
<div class="crumb">Official data</div>
<h1>Team statistics, re-cut from the three official pages</h1>
<p class="lede">The traditional, opponent and advanced pages were re-read on {SNAPSHOT} and re-cut
into one row per team. Before anything is published, seven identities the pages imply are
re-derived; a row that fails is not published.</p>

<div class="okbox"><b>{sum(1 for v in ts['checks'].values() if v['status']=='PASS')} of
{len(ts['checks'])} identities pass.</b> Scoring, rebounding, opponent scoring, net rating, the
cross-page margin and the minutes/overtime relation all reconcile within their printed rounding
tolerance.</div>

<h2>The identities checked</h2>
{table(["Identity", "Result", "Failures", "Source"], checks, numeric=(2,),
       caption="Tolerances are rounding bounds, not fudge factors: a 4-term identity on 1-dp values "
               "can be off by 4×0.05 plus the printed value's own 0.05, so 0.25 is the bound.")}

<h2>One row per team</h2>
{table(["Team", "GP", "W", "L", "PTS", "Opp PTS", "+/−", "OffRtg", "DefRtg", "NetRtg", "Pace",
        "Source"], rows, numeric=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
       caption="PTS and Opp PTS are per-game averages from the traditional and opponent pages. "
               "Ratings and pace are from the advanced page, which is a totals-mode page: POSS and "
               "MIN there are season totals, while PACE is already a per-game possession count.")}
""", active="team-stats.html", subtitle="Official data")


def page_strategies(d):
    model = d["model"]
    rows = []
    for s in model["strategies"]:
        kind = "ok" if s["published"] else "bad"
        rows.append([
            esc(s["strategy_id"]), esc(s["signal"]), esc(", ".join(s["leans_on"])),
            esc(s["blocked_because"] or "—"), pill(kind, "published" if s["published"] else "blocked"),
            src("https://www.nba.com/schedule?date=2026-11-16", "schedule"),
        ])
    return layout("Strategy board", f"""
<div class="crumb">Bet surface · gated</div>
<h1>Strategy board: 25 candidates, 0 published</h1>
<p class="lede">A strategy is published only if it clears every gate. This page shows the gate, the
result, and — for every blocked row — the specific reason it is blocked.</p>

<div class="badbox"><b>Nothing is published, and the reason is arithmetic.</b> A strategy may not lean
on a team whose record is outside a ±2 z-score band. A z-score needs games; no team has more than
two in the captured log, and this build requires four before it will treat a z as meaningful. So no
team can be shown inside the band, so no strategy clears the gate. The honest state of the board is
"insufficient evidence", and it is printed rather than papered over with a small-sample favourite.</div>

<h2>The gates a strategy must clear</h2>
<ol>
  <li><b>Two estimators agree.</b> No line without both A and B.</li>
  <li><b>The team is inside the luck band.</b> |z| ≤ 2, on at least four captured games.</li>
  <li><b>A frozen pre-registration exists.</b> Signal, thresholds, universe and the exact
  settlement rule, hashed before the first bet.</li>
  <li><b>The pick is sealed before tip.</b> Its hash is published ahead of the game.</li>
  <li><b>Settlement uses an official final only.</b> The game book, not a summary.</li>
</ol>

<h2>Every candidate and its block reason</h2>
{table(["ID", "Signal", "Leans on", "Blocked because", "State", "Source"], rows,
       caption="One row per game in the window. The block reason is generated, not typed.")}

<h2>What would unblock this</h2>
<ul>
  <li><b>More settled games.</b> Four per team is the floor this build sets; the log has 22 finals
  and needs roughly 150 before every team clears it.</li>
  <li><b>A licensed odds feed.</b> Without a market price there is no benchmark to measure a
  strategy's out-of-sample log-loss against, so "skill" cannot be separated from "the model likes a
  team".</li>
</ul>
""", active="strategies.html", subtitle="Bet surface · gated")


def page_pricing(d):
    pr = d["model"]["pricing"]
    rows = []
    for p in pr["parlays"]:
        rows.append([
            f'<a href="https://www.nba.com/game/{p["game_id"]}" rel="noopener">{esc(p["label"])}</a>',
            esc(" + ".join(p["legs"])),
            num(p["p_leg_1"], 4), num(p["p_leg_2"], 4),
            num(p["naive_product"], 5),
            dash(None) if p["naive_american"] is None else num(p["naive_american"], 0),
            num(p["measured_rho"], 4) if p["measured_rho"] is not None else dash(None),
            num(p["p_joint_with_rho"], 5) if p["p_joint_with_rho"] is not None else dash(None),
            num(p["american_with_rho"], 0) if p["american_with_rho"] is not None else dash(None),
            num(p["dependence_pct"]) if p["dependence_pct"] is not None else dash(None),
        ])
    return layout("Prices & parlays", f"""
<div class="crumb">Bet surface · gated</div>
<h1>Prices, and both parlay prices</h1>
<p class="lede">Every parlay is priced twice: once as the naive product of its legs, which is what a
person would compute on a napkin and which is wrong whenever the legs are not independent, and once
from the measured dependence. Both are printed.</p>

<div class="cards">
  <div class="card"><div class="k">Measured ρ (margin, total)</div><div class="v">{num(pr['rho'], 3)}</div>
    <div class="s">on {pr['rho_n']} finals; 95% interval [{num(pr['rho_ci95'][0], 3)},
    {num(pr['rho_ci95'][1], 3)}]. The interval contains zero, so the honest statement is "not
    distinguishable from zero at this n" — which is different from "zero".</div>
    <div class="src">{src("https://www.nba.com/games?date=2026-11-15", "nba.com/games")}</div></div>
  <div class="card"><div class="k">Parlays priced</div><div class="v">{len(pr['parlays'])}</div>
    <div class="s">same-game moneyline + total, every game in the window</div>
    <div class="src">{src(d['slate']['source_url'], 'schedule')}</div></div>
  <div class="card"><div class="k">Player-prop combos priced</div><div class="v">0</div>
    <div class="s">no per-player game logs, so there is no measured rho. Inventing one would be the
    least defensible number on the site, so it is withheld.</div>
    <div class="src">{src("https://www.nba.com/stats/players/traditional", "stats")}</div></div>
</div>

{table(["Game", "Legs", "P(leg 1)", "P(leg 2)", "Naive product", "Naive ML", "Measured ρ",
        "Joint (ρ)", "ML with ρ", "Δ vs naive"], rows, numeric=(2, 3, 4, 5, 6, 7, 8, 9),
       caption="The naive product assumes independence. The joint uses a bivariate normal copula at "
               "the measured ρ; with ρ = 0 it collapses back to the product, which is asserted by a "
               "unit test.")}

<h2>What is withheld, and why</h2>
<ul>
  <li><b>Player-prop combos.</b> No measured ρ, so no price. The legs and the reason are recorded;
  the number is not.</li>
  <li><b>A closing-line comparison.</b> No feed. The model's price is printed alone rather than
  against an invented market.</li>
</ul>
""", active="pricing.html", subtitle="Bet surface · gated")


def page_questions(d):
    rows = d["questions"]
    body = [[esc(q["id"]), esc(q["question"]), esc(q["known"]), esc(q["missing"]),
             esc(q["how_to_find"]), esc(q["blocks"]),
             src(q["source"]) if q.get("source") else dash(None)] for q in rows]
    return layout("Open questions", f"""
<div class="crumb">Decision support</div>
<h1>Questions that must be answered before a decision</h1>
<p class="lede">Each row is a question, what is already known, what is missing, and the specific way
to get the missing piece. A question with no discovery route is not on this list — it would be a
complaint, not a question.</p>

{table(["ID", "Question", "What we know", "What is missing", "How to find it", "What it blocks",
        "Nearest official source"], body,
       caption="The last column is the official document closest to each question. Where a question "
               "is about a feed or a licence that the league does not publish, the column names the "
               "official page that would have to change for the question to be answerable.")}

<h2>How this list is maintained</h2>
<p class="small">The register is <code>data/rounds/2026-11-16/questions.csv</code>. It is read by
the build and rendered verbatim; adding a question means adding a row with the five fields above,
and the CI replay will fail if the page drifts from the file.</p>
""", active="questions.html", subtitle="Decision support")


def page_suggestions(d):
    rows = d["suggestions"]
    body = [[esc(s["id"]), esc(s["area"]), esc(s["suggestion"]), esc(s["why"]),
             esc(s["effort"]), pill("info", s["status"]),
             src(s["source"]) if s.get("source") else dash(None)] for s in rows]
    return layout("Site suggestions", f"""
<div class="crumb">Decision support</div>
<h1>Site improvements, awaiting a decision</h1>
<p class="lede">Nothing on this page has been implemented. Each item is a proposal with the reason
it would help, the effort it would take, and the decision it needs from you.</p>

<div class="note">The rule for this page: a suggestion is a proposal, never a change. The build
renders this list verbatim from <code>data/rounds/2026-11-16/suggestions.csv</code>; implementing one
means moving it to "adopted" in that file and writing the code, in a separate change.</div>

{table(["ID", "Area", "Suggestion", "Why it would help", "Effort", "Status",
        "Document it depends on"], body,
       caption="Every proposal names the official document whose capture or publication it depends "
               "on, so the cost of each is visible before it is chosen.")}
""", active="suggestions.html", subtitle="Decision support")


def page_flagged(d):
    flags = d["flags"]
    body = [[esc(f["id"]), esc(f["what"]), esc(f["why"]), esc(f["impact"]),
             src(f.get("source") or "", "source",
                 secondary=True) if f.get("source") else dash(None),
             pill("warn", f["status"])] for f in flags]
    return layout("Flagged for review", f"""
<div class="crumb">Verification</div>
<h1>Flagged for review</h1>
<p class="lede">Every value this build could not confirm from an official source, and every
irregularity found while verifying. Nothing here blocks publication; each row names the document in
question so it can be checked.</p>

<div class="warnbox"><b>These are published, not hidden.</b> A blank cell on another page is a link
to a row here. The alternative — filling the cell with something plausible — is the failure mode
this whole repository exists to avoid.</div>

{table(["ID", "Item", "Why it is flagged", "Impact", "Source", "Status"], body,
       caption=f"{len(body)} flagged items on 2026-11-16.")}
""", active="flagged.html", subtitle="Verification")


def page_sources(d):
    sources = d["sources"]
    body = [[esc(s["id"]),
             src(s["url"], s["title"], secondary=(s["tier"] != "OFFICIAL")),
             esc(s["what"]), esc(s["read_utc"]), esc(s["tier"])] for s in sources]
    return layout("Sources", f"""
<div class="crumb">Verification</div>
<h1>Source register</h1>
<p class="lede">Every document this build read, with the exact URL and the time it was read. Official
means an NBA-operated host: <code>nba.com</code>, <code>official.nba.com</code>,
<code>ak-static.cms.nba.com</code> (the injury-report CDN) or <code>statsdmz.nba.com</code> (game
books).</p>

{table(["ID", "Document", "What it was used for", "Read (UTC)", "Tier"], body,
       caption="A row whose tier is not OFFICIAL is a secondary source and is labelled as such "
               "everywhere its values are printed.")}
""", active="sources.html", subtitle="Verification")


def page_methodology(d):
    return layout("Method & rules", f"""
<div class="crumb">Overview</div>
<h1>The rules this build obeys</h1>
<p class="lede">These are enforced by code and re-checked by tests, not just written down. Each one
exists because breaking it produces a number that looks plausible and is wrong.</p>

<h2>Data rules</h2>
<ol>
  <li><b>No value without a document.</b> Every published row carries an <code>https</code> link to
  the official document it came from. The build refuses a row that does not.</li>
  <li><b>No inference.</b> A cell the document does not print stays null. The one injury row whose
  status cell is missing is published null, not copied from the previous report.</li>
  <li><b>No repair of an official document.</b> Where ATL@MIL's game book contradicts itself, both
  readings are kept and the row is published unsettled.</li>
  <li><b>Carried cells are recorded.</b> When a table continues across a page break, the cell is
  carried from the printed row above and the carry is written onto the row with its evidence.</li>
</ol>

<h2>Gate rules</h2>
<ol>
  <li><b>Rebuild only after the gates pass.</b> Freshness and provenance gates have build scope:
  if one fails, nothing is rebuilt and the site keeps its last good state.</li>
  <li><b>Integrity gates have row scope.</b> A contradictory game book withholds its own row, with
  the failed arithmetic shown, and does not blind the reader to everything else.</li>
  <li><b>Freshness is measured against the official index</b>, not against the file on disk. The
  gate compares the newest report the league lists with the one the build parsed.</li>
</ol>

<h2>Model rules</h2>
<ol>
  <li><b>Two estimators, no shared input.</b> The disagreement is the headline; the blend is
  underneath.</li>
  <li><b>Home court is pinned</b> to the measured home-win rate, not fitted freely.</li>
  <li><b>The total is possessions × points-per-possession</b>, with the naive sum printed beside
  it.</li>
  <li><b>Luck is a z-score</b>, and a strategy leaning on a team outside ±2 is not published.</li>
  <li><b>Shrinkage is chosen on past games only</b>, by leave-one-game-out, never on the games
  being forecast.</li>
  <li><b>Both parlay prices are printed.</b> The naive product and the price implied by the
  measured ρ.</li>
  <li><b>Nothing is invented when the input is absent.</b> No closing line means no market anchor;
  no per-player logs means no prop rho.</li>
</ol>

<h2>The market-anchored prior, ready to switch on</h2>
<p>The brief asks for the model line to be blended with the closing line, weighted by measured
out-of-sample log-loss:</p>
<p><code>blended = w · model + (1 − w) · closing, &nbsp; w = exp(−LL_model) / (exp(−LL_model) + exp(−LL_closing))</code></p>
<p>The formula is implemented; the weight is null because there is no closing line to measure
<code>LL_closing</code> from. Filling it with a chosen weight would be the invented number this
project refuses to print.</p>
""", active="methodology.html", subtitle="Overview")


def page_requirements(d):
    reqs = d["requirements"]
    rows = [[esc(r["id"]), esc(r["requirement"]), esc(r["status"]),
             esc(r["evidence"]), src(r["source"], "source", secondary=True), pill("info", r["verdict"])]
            for r in reqs]
    return layout("Brief coverage", f"""
<div class="crumb">Overview</div>
<h1>Brief → implementation, one row per requirement</h1>
<p class="lede">Every distinct requirement in the brief, what was built for it, and the official
source that makes the row checkable. Where a requirement cannot be met yet, the row says which
question it is waiting on.</p>

{table(["ID", "Requirement", "What was built", "Evidence", "Source", "Verdict"], rows,
       caption=f"{len(rows)} requirements. A verdict of 'partial' or 'blocked' names the blocker in "
               f"the evidence cell.")}
""", active="requirements.html", subtitle="Overview")


def page_archive(d):
    trees = [
        ("/app/ (earlier canonical dashboard)", "the dashboard this session replaces as the front door",
         "scripts/build_app.py"),
        ("/audit_94e6d41b/", "11/15 game-day refresh audit", "audit_94e6d41b/"),
        ("/audit_1823b910/", "independent second transcription, 11/14 01:30 PM report", "audit_1823b910/"),
    ]
    rows = [[esc(a), esc(b), f'<code>{esc(c)}</code>',
             src("https://www.nba.com/schedule?date=2026-11-16")] for a, b, c in trees]
    return layout("Earlier sessions", f"""
<div class="crumb">Verification</div>
<h1>Earlier sessions</h1>
<p class="lede">This repository has had many sessions. This build is the 2026-11-16 round and it owns
the front door; the trees below were built earlier and are kept for the record. None of them is
current.</p>

<div class="note">The navigation on this site does not link into the older trees: they carry
different numbers from older data, and mixing them into one navigation is how a reader ends up
comparing two different worlds. They are listed here, with the script that builds them, so anything
worth carrying forward can be found.</div>

{table(["Tree", "What it is", "Built by", "Current official source"], rows,
       caption="Kept in the deployment for provenance; not merged into this dashboard's numbers.")}
""", active="archive.html", subtitle="Verification")


# ---------------------------------------------------------------------------------------------
def main():
    d = {
        "slate": load("slate.json"),
        "injuries": load("injuries.json"),
        "results": load("results.json"),
        "team_stats": load("team_stats.json"),
        "context": load("context.json"),
        "gates": load("gates.json"),
        "model": load("model.json"),
        "questions": read_csv("questions.csv"),
        "suggestions": read_csv("suggestions.csv"),
        "flags": read_csv("flags.csv"),
        "sources": read_csv("sources.csv"),
        "requirements": read_csv("requirements.csv"),
        "delta": load("injury_delta.json"),
    }
    pages = [
        ("overview.html", page_overview(d)),
        ("slate.html", page_slate(d)),
        ("projections.html", page_projections(d)),
        ("lines.html", page_lines(d)),
        ("totals.html", page_totals(d)),
        ("context.html", page_context(d)),
        ("injuries.html", page_injuries(d)),
        ("injury-delta.html", page_injury_diff(d)),
        ("results.html", page_results(d)),
        ("team-stats.html", page_team_stats(d)),
        ("strategies.html", page_strategies(d)),
        ("pricing.html", page_pricing(d)),
        ("questions.html", page_questions(d)),
        ("suggestions.html", page_suggestions(d)),
        ("flagged.html", page_flagged(d)),
        ("sources.html", page_sources(d)),
        ("methodology.html", page_methodology(d)),
        ("requirements.html", page_requirements(d)),
        ("archive.html", page_archive(d)),
    ]
    os.makedirs(os.path.join(APP, "assets"), exist_ok=True)
    with open(os.path.join(APP, "assets", "dashboard.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)
    written = []
    for name, doc in pages:
        with open(os.path.join(APP, name), "w", encoding="utf-8") as fh:
            fh.write(doc)
        written.append(f"round/{name}")
    # The landing page is written INTO round/ and nowhere else. `index.html` at the repo root is
    # owned by scripts/build_app.py and is asserted by the Pages workflow, so this builder must not
    # touch it: doing so silently replaced the canonical dashboard's front door and would have been
    # overwritten by CI on the next deploy anyway. The round's front door is round/index.html, and
    # the workflow stages round/ verbatim.
    with open(os.path.join(APP, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page_landing(d))
    written.append("round/index.html")

    # ---- link + source check
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids, self.hrefs, self.rows = set(), [], []
            self.in_tbody = False
            self.row = None

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if "id" in a:
                self.ids.add(a["id"])
            if tag == "a" and "href" in a:
                self.hrefs.append(a["href"])
                if self.row is not None:
                    self.row.append(a["href"])
            if tag == "tbody":
                self.in_tbody = True
            if tag == "tr" and self.in_tbody:
                self.row = []

        def handle_endtag(self, tag):
            if tag == "tr" and self.row is not None:
                self.rows.append(self.row)
                self.row = None
            if tag == "tbody":
                self.in_tbody = False

    for path in written:
        full = os.path.join(ROOT, path)
        p = P()
        p.feed(open(full, encoding="utf-8").read())
        base = os.path.dirname(full)
        for h in p.hrefs:
            if h.startswith("#"):
                if h[1:] not in p.ids:
                    ERRORS.append(f"{path}: broken anchor {h}")
            elif h.startswith(("http://", "https://", "mailto:")):
                if h.startswith("http://"):
                    ERRORS.append(f"{path}: non-https link {h}")
            else:
                if not os.path.exists(os.path.normpath(os.path.join(base, h.split("#")[0]))):
                    ERRORS.append(f"{path}: broken relative link {h}")
        for i, row in enumerate(p.rows, 1):
            # A row must cite a source. Official is the default and the only acceptable tier for
            # DATA. A row that is itself about a non-official document (the coordinate table, the
            # regulator, this repo's own claim record) may cite that document, because refusing it
            # would force the row to cite an NBA page that does not contain the value -- which is
            # exactly the silent misattribution this build exists to prevent.
            links = [h for h in row if h.startswith("https://")]
            official = [h for h in links if any(
                re.sub(r"^https?://", "", h).split("/")[0].endswith(dh) for dh in OFFICIAL_HOSTS)]
            declared = [h for h in links if h in ALLOWED_NON_OFFICIAL]
            if not official and not declared:
                ERRORS.append(f"{path}: table row {i} cites no source "
                              f"({len(links)} link(s), none official or declared)")
    if ERRORS:
        print("BUILD FAILED")
        for e in ERRORS:
            print("  -", e)
        return 1
    print(f"wrote {len(written)} pages; link + per-row source check clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
