#!/usr/bin/env python3
"""Build the NBA Edge Lab static site from data/*.json.

Usage:
    python3 scripts/build_site.py          # validate, render site/, check links
    python3 scripts/build_site.py --check  # validate and check links only

The build FAILS (non-zero exit) when:
  * a data row has no official https source and is not flagged as unverified,
  * a source link points outside the allow-list of official domains,
  * a referenced source id (S01...) does not exist,
  * a generated internal link or in-page anchor is broken.
Only Python 3 standard library is used.
"""
import html
import json
import os
import re
import sys
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
BUILD_DATE = "2026-11-13"
REPO_URL = "https://github.com/wingbangboozle1-lang/NBA3"

# Official / primary domains allowed as sources (NBA, Dutch regulator, GitHub for repo facts).
OFFICIAL_DOMAINS = {
    "nba.com", "www.nba.com", "cdn.nba.com", "ak-static.cms.nba.com", "official.nba.com",
    "kansspelautoriteit.nl", "www.kansspelautoriteit.nl", "github.com", "api.github.com",
}

ERRORS = []


def err(msg):
    ERRORS.append(msg)


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def is_official(url):
    if not url:
        return False
    p = urlparse(url)
    return p.scheme == "https" and p.netloc.lower() in OFFICIAL_DOMAINS


def link(url, label=None):
    if not url:
        return '<span class="flag">UNVERIFIED — no official link</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label or url)}</a>'


def src_links(ids, sources):
    if not ids:
        return '<span class="muted">none</span>'
    out = []
    for i in ids:
        s = sources.get(i)
        if s:
            out.append(f'<a href="sources.html#{esc(i)}" title="{esc(s["title"])}">{esc(i)}</a> ' + link(s["url"], "↗"))
    return " · ".join(out)


def chip(text, kind="neutral"):
    return f'<span class="chip chip-{kind}">{esc(text)}</span>'


def table(headers, rows, table_id=None, filterable=False):
    attrs = f' id="{table_id}"' if table_id else ""
    cls = ' class="tbl"'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    filt = ""
    if filterable:
        filt = (f'<div class="filterbar"><input type="search" placeholder="Filter rows (team, player, status, game)…" '
                f'data-filter-table="{esc(table_id)}" aria-label="Filter table"></div>')
    return f'{filt}<div class="table-wrap"><table{attrs}{cls}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


NAV = [
    ("Overview", [("index.html", "Home"), ("executive-summary.html", "Executive summary")]),
    ("Data", [("slate.html", "3-day slate"), ("injuries.html", "Injury tracker"), ("game-flow.html", "Game flow")]),
    ("Research", [("strategies.html", "Strategies"), ("validation.html", "Validation & correlation")]),
    ("Decisions", [("questions.html", "Questions"), ("suggestions.html", "Suggestions")]),
    ("Governance", [("sources.html", "Sources"), ("repo-review.html", "Repo review"), ("flagged.html", "Flagged for Review")]),
]
PAGES = [p for _, items in NAV for p, _ in items]


def nav_html(active):
    parts = []
    for group, items in NAV:
        links = ""
        for p, l in items:
            cur = ' class="on" aria-current="page"' if p == active else ""
            links += f'<a href="{p}"{cur}>{esc(l)}</a>'

        parts.append(f'<div class="navgroup"><div class="navlabel">{esc(group)}</div>{links}</div>')
    return "".join(parts)


CSS = """
:root{--ink:#152033;--muted:#5d6b82;--line:#dfe6f1;--bg:#f5f7fb;--card:#fff;--navy:#0f1e38;--blue:#2457d6;--red:#b42318;--redbg:#fef3f2;--amber:#8a5a00;--amberbg:#fff7e0;--green:#0f7a4a;--greenbg:#e8f7ef;--grey:#eef1f6}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--bg)}
a{color:#1d4fc0}header.top{background:var(--navy);color:#fff;padding:18px 24px}header.top .brand{font-weight:800;font-size:20px;letter-spacing:.2px}header.top .sub{color:#c9d6ee;font-size:13px}
.layout{display:grid;grid-template-columns:230px 1fr;gap:22px;max-width:1280px;margin:0 auto;padding:20px}
nav.side{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;height:max-content;position:sticky;top:12px}
.navgroup{margin-bottom:10px}.navlabel{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:700;padding:6px 8px}
nav.side a{display:block;padding:7px 10px;border-radius:7px;color:var(--ink);text-decoration:none}nav.side a:hover{background:#edf2ff}nav.side a.on{background:#e6edff;color:#143b9e;font-weight:700}
main{min-width:0}section.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin-bottom:16px}
h1{font-size:26px;margin:4px 0 6px}h2{font-size:19px;margin:0 0 10px}h3{font-size:15px;margin:14px 0 6px}
.lede{color:var(--muted);margin:0 0 6px;max-width:860px}.muted{color:var(--muted)}
.banner{border-radius:10px;padding:12px 14px;margin:0 0 14px;border:1px solid}.banner.warn{background:var(--amberbg);border-color:#f0d58a;color:#5b3d00}.banner.stop{background:var(--redbg);border-color:#fecdca;color:#7a1a12}.banner.ok{background:var(--greenbg);border-color:#b7e4c9;color:#0b5333}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.metric{background:#f8faff;border:1px solid var(--line);border-radius:10px;padding:14px}.metric b{display:block;font-size:24px}.metric small{color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.cardlink{display:block;background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;text-decoration:none;color:var(--ink)}.cardlink:hover{border-color:#9db7f5;box-shadow:0 2px 10px #1d4fc01a}.cardlink b{color:#143b9e}.cardlink span{display:block;color:var(--muted);font-size:13px;margin-top:4px}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px}table.tbl{border-collapse:collapse;width:100%;font-size:13.5px}table.tbl th,table.tbl td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
table.tbl th{background:#f3f6fc;position:sticky;top:0;font-weight:700;white-space:nowrap}table.tbl tr:last-child td{border-bottom:0}table.tbl tbody tr:hover{background:#fbfcff}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.filterbar{margin:0 0 8px}.filterbar input{width:100%;max-width:420px;padding:8px 10px;border:1px solid #c8d3e6;border-radius:8px;font:inherit}
.chip{display:inline-block;border-radius:999px;padding:2px 9px;font-size:12px;font-weight:700;white-space:nowrap}
.chip-blocker{background:var(--redbg);color:var(--red)}.chip-unverified{background:var(--amberbg);color:var(--amber)}.chip-irregular{background:#eef2ff;color:#2c3f8f}.chip-ok{background:var(--greenbg);color:var(--green)}.chip-neutral{background:var(--grey);color:#34405a}
.flag{color:var(--amber);font-weight:700}
footer{max-width:1280px;margin:0 auto;padding:4px 20px 30px;color:var(--muted);font-size:12.5px}
ul.tight li{margin:3px 0}code{background:#eef1f6;padding:1px 5px;border-radius:4px;font-size:12.5px}
@media(max-width:820px){.layout{grid-template-columns:1fr}nav.side{position:static}}
"""

JS = """
document.querySelectorAll('input[data-filter-table]').forEach(function(inp){
  var t=document.getElementById(inp.getAttribute('data-filter-table'));
  if(!t)return;
  inp.addEventListener('input',function(){
    var q=inp.value.toLowerCase();
    t.querySelectorAll('tbody tr').forEach(function(tr){
      tr.style.display = tr.textContent.toLowerCase().indexOf(q)>-1 ? '' : 'none';
    });
  });
});
"""


def page(filename, title, body, desc=""):
    active = filename
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · NBA Edge Lab</title>
<meta name="description" content="{esc(desc or 'NBA Edge Lab research dashboard')}">
<link rel="stylesheet" href="assets/site.css">
</head><body>
<header class="top"><div class="brand">NBA Edge Lab</div><div class="sub">Research dashboard · data as of {BUILD_DATE} · research only, not betting advice</div></header>
<div class="layout">
<nav class="side" aria-label="Site sections">{nav_html(active)}</nav>
<main>
{body}
</main>
</div>
<footer>Generated from <code>data/*.json</code> by <code>scripts/build_site.py</code>. Values with no official source are left blank and flagged (see <a href="flagged.html">Flagged for Review</a>). Source of this site: <a href="{REPO_URL}" target="_blank" rel="noopener">GitHub repository</a> · <a href="{REPO_URL}/blob/main/COORDINATION.md" target="_blank" rel="noopener">coordination board</a>.</footer>
<script src="assets/site.js"></script>
</body></html>
"""


def banner_research():
    return ('<div class="banner stop"><b>No lines, picks, or correlation values are published.</b> '
            'Blocking items: NBA Terms §9 (7C-F-01), Dutch licence requirement (7C-F-02), and no licensed odds data (7C-F-03). '
            'Everything shown is either sourced to an official link or flagged.</div>')


def load_all():
    d = {}
    d["sources"] = load("sources.json")
    d["schedule"] = load("schedule.json")
    d["injuries"] = load("injuries.json")
    d["flags"] = load("flags.json")
    d["repo"] = load("repo_review.json")
    d["questions"] = load("questions.json")
    d["suggestions"] = load("suggestions.json")
    d["strategies"] = load("strategies.json")
    d["gates"] = load("validation_gates.json")
    return d


def validate(d):
    sources = {s["id"]: s for s in d["sources"]}
    if len(sources) != len(d["sources"]):
        err("duplicate source ids")
    for s in d["sources"]:
        if not is_official(s["url"]):
            err(f"{s['id']}: source URL not https or not on allow-list: {s['url']}")
    sched_url = d["schedule"]["source_url"]
    if not is_official(sched_url):
        err("schedule source_url not official")
    for g in d["schedule"]["games"]:
        if not g.get("team_1") or not g.get("team_2"):
            err(f"schedule game {g.get('game_no')} missing teams")
    seen_ids = set()
    for r in d["injuries"]:
        if r["id"] in seen_ids:
            err(f"duplicate injury id {r['id']}")
        seen_ids.add(r["id"])
        if not is_official(r["report_source"]):
            err(f"{r['id']}: report source not official")
        if r.get("schedule_source") and not is_official(r["schedule_source"]):
            err(f"{r['id']}: schedule source not official")
        if r["attribution"] not in {"R", "S", "U", "T"}:
            err(f"{r['id']}: bad attribution")
        if r["attribution"] == "U" and (r["team"] or r["matchup"]):
            err(f"{r['id']}: unattributed row must leave team/matchup blank")
        if r["attribution"] in {"U", "S"} and not r.get("flag"):
            err(f"{r['id']}: attributed-by-inference row missing flag")
    for f in d["flags"]:
        for i in f["sources"]:
            if i not in sources:
                err(f"{f['id']}: unknown source {i}")
        if f["type"] not in {"Blocker", "Unverified", "Irregularity"}:
            err(f"{f['id']}: bad flag type")
    for r in d["repo"]:
        if not is_official(r["src"]):
            err(f"{r['id']}: source not official: {r['src']}")
    for q in d["questions"]:
        for i in q["src"]:
            if i not in sources:
                err(f"{q['id']}: unknown source {i}")
    for s in d["suggestions"]:
        for i in s["src"]:
            if i not in sources:
                err(f"{s['id']}: unknown source {i}")
    for s in d["strategies"]:
        if s["official"] and not is_official(s["official"]):
            err(f"{s['id']}: strategy source not official")
        if not s["official"] and "Blocked" not in s["status"]:
            err(f"{s['id']}: row without official source must be flagged as blocked/unverified")
    for g in d["gates"]:
        for i in g["src"]:
            if i not in sources:
                err(f"{g['id']}: unknown source {i}")
    # Reference check across all text fields for S\d+ ids
    text_blob = json.dumps(d, ensure_ascii=False)
    for ref in set(re.findall(r'"(S\d{2})"', text_blob)):
        if ref not in sources:
            err(f"reference to unknown source {ref}")


def team_matches(key, team):
    return bool(team) and key in team


def game_flow_rows(d):
    rows = []
    inj = d["injuries"]
    for g in d["schedule"]["games"]:
        if g["date"] not in ("2026-11-13", "2026-11-14"):
            continue
        for side, key in (("team_1", g["team_1"]), ("team_2", g["team_2"])):
            # injury rows store ISO dates (YYYY-MM-DD), matching the schedule's date field
            matched = [r for r in inj if r["attribution"] in {"R", "S", "T"} and r["team"] and team_matches(key, r["team"]) and r["game_date"] == g["date"]]
            unatt = [r for r in inj if r["attribution"] == "U" and r["game_date"] == g["date"]]
            cnt = {"Out": 0, "Questionable/Doubtful": 0, "Probable": 0, "Available": 0, "Other": 0}
            not_sub = False
            for r in matched:
                st = r["status_as_printed"]
                if st == "NOT YET SUBMITTED":
                    not_sub = True
                elif st == "Out":
                    cnt["Out"] += 1
                elif st in ("Questionable", "Doubtful"):
                    cnt["Questionable/Doubtful"] += 1
                elif st == "Probable":
                    cnt["Probable"] += 1
                elif st == "Available":
                    cnt["Available"] += 1
                else:
                    cnt["Other"] += 1
            rows.append({
                "game_no": g["game_no"], "date": g["date"], "tip_et": g["tip_et"],
                "matchup": f"{g['team_1']} @ {g['team_2']}", "team": key, "side": side,
                "out": cnt["Out"], "q": cnt["Questionable/Doubtful"], "prob": cnt["Probable"], "avail": cnt["Available"],
                "other": cnt["Other"], "not_submitted": not_sub, "rows": len(matched),
                "unattributed_rows_same_day": len(unatt),
            })
    return rows


def render_pages(d):
    S = {s["id"]: s for s in d["sources"]}
    out = {}
    sched = d["schedule"]
    inj = d["injuries"]
    flags = d["flags"]
    blockers = [f for f in flags if f["type"] == "Blocker"]
    n_unv = len([f for f in flags if f["type"] == "Unverified"])
    n_irr = len([f for f in flags if f["type"] == "Irregularity"])
    n_u = len([r for r in inj if r["attribution"] == "U"])
    n_s = len([r for r in inj if r["attribution"] == "S"])
    n_nys = len([r for r in inj if r["status_as_printed"] == "NOT YET SUBMITTED"])
    n_games = len(sched["games"])
    n_dates = len({g["date"] for g in sched["games"]})

    # ---------- Landing ----------
    cards = [
        ("executive-summary.html", "Executive summary", "Key facts, blockers, and what can and cannot be decided yet."),
        ("slate.html", "3-day slate", f"{n_games} games, 11/13–11/16/2026, from the official schedule PDF."),
        ("injuries.html", "Injury tracker", f"{len(inj)} rows from the official 11/13/26 5:00 PM injury report."),
        ("game-flow.html", "Game flow", "Team status counts for games with a report; models not built."),
        ("strategies.html", "Strategies", f"{len(d['strategies'])} candidate single bets, props, parlays, and combos. All blocked."),
        ("validation.html", "Validation & correlation", f"{len(d['gates'])} gates, none run. Correlation values left blank."),
        ("questions.html", "Questions", f"{len(d['questions'])} questions: what is answered, partly answered, or missing."),
        ("suggestions.html", "Suggestions", f"{len(d['suggestions'])} proposals. Awaiting your selection; nothing is implemented."),
        ("sources.html", "Sources", f"{len(d['sources'])} official sources, with retrieval status and limits."),
        ("repo-review.html", "Repo review", f"{len(d['repo'])} repository findings with source links."),
        ("flagged.html", "Flagged for Review", f"{len(flags)} items: {len(blockers)} blockers, {n_unv} unverified, {n_irr} irregularities."),
    ]
    card_html = "".join(f'<a class="cardlink" href="{p}"><b>{esc(t)}</b><span>{esc(x)}</span></a>' for p, t, x in cards)
    metrics = [
        (str(n_games), f"games in the window (official schedule, {n_dates} dates)"),
        (str(len(inj)), "injury-report rows (11/13 5:00 PM official report)"),
        ("0", "originated lines published"),
        ("0", "picks published"),
        (str(len(blockers)), "open blockers (7C-F-01 to 7C-F-03)"),
        (str(len(flags)), "items flagged for review"),
    ]
    met_html = "".join(f'<div class="metric"><b>{esc(a)}</b><small>{esc(b)}</small></div>' for a, b in metrics)
    body = f"""
<section class="card">
<h1>NBA Edge Lab</h1>
<p class="lede">A research dashboard for originating NBA line ideas, testing them, and tracking the official inputs behind them. It shows the official slate and injury report and the open legal and data blockers. It publishes no lines, picks, or correlation values yet.</p>
{banner_research()}
<div class="grid">{met_html}</div>
</section>
<section class="card">
<h2>Sections</h2>
<div class="cards">{card_html}</div>
</section>
<section class="card">
<h2>Verified at a glance</h2>
<ul class="tight">
<li>Injury-report deadlines: teams report status by 5 p.m. local the day before a game (2nd game of a back-to-back: 1 p.m. local on game day); the game-day report runs 11 a.m.–1 p.m. local. {link(S['S02']['url'], 'NBA Official, 2026-27 injury report index')}</li>
<li>The official injury PDF lists status and reason only; it has no minutes field. {link(S['S04']['url'], 'Injury report 11/13/26 5:00 PM')}</li>
<li>NBA Terms §9: NBA Statistics may not be used in connection with any gambling activity, including legal gambling. {link(S['S07']['url'], 'NBA.com Terms of Use')}</li>
<li>Dutch online sports betting requires a Koa licence under art. 31a of the Betting and Gaming Act. {link(S['S09']['url'], 'Kansspelautoriteit: online kansspel aanbieden')}</li>
<li>The 2026-27 schedule was released August 13, 2026 and is labelled "subject to change". {link(S['S05']['url'], 'Schedule PDF')}</li>
</ul>
</section>
"""
    out["index.html"] = ("Home", body, "NBA Edge Lab home: status, metrics, and sections.")

    # ---------- Executive summary ----------
    body = f"""
<section class="card">
<h1>Executive summary</h1>
<p class="lede">Prepared {BUILD_DATE}. Scope: repository review, official-source verification, the official 3-day slate, injury tracking, strategy design, validation gates, questions, and suggestions.</p>
{banner_research()}
<h2>Bottom line</h2>
<ul class="tight">
<li><b>Picks for the next 3 days cannot yet be responsibly generated.</b> No licensed odds, no authorized statistics, and no validated model are in place. Picks would be unsupported.</li>
<li><b>Two legal items must be resolved first.</b> (1) NBA Terms §9 bars using NBA Statistics for gambling. (2) Dutch online sports-betting offers require a Koa licence. Both are flagged as blockers; neither is a finding of unlawfulness.</li>
<li><b>The official 3-day slate is confirmed:</b> {n_games} games across {n_dates} dates (11/13–11/16/2026), from the official schedule. It is subject to change.</li>
<li><b>Injury tracking is possible from official reports, but not minutes.</b> The 11/13 5:00 PM report yields {len(inj)} rows. {n_nys} rows are 'NOT YET SUBMITTED'. The report does not quantify minutes or production.</li>
<li><b>Correlation values and ROI are blank</b> by policy. Nothing has been measured.</li>
</ul>
<h2>What is verified (with links)</h2>
<div class="table-wrap"><table class="tbl"><thead><tr><th>Fact</th><th>Source</th><th>Status</th></tr></thead><tbody>
<tr><td>2026-27 schedule: 31 games 11/13–11/16 (Team 1 / Team 2 as printed)</td><td>{link(S['S05']['url'], 'Schedule PDF')}</td><td>{chip('Verified to source', 'ok')} subject to change</td></tr>
<tr><td>11/13/26 5:00 PM injury report: {len(inj)} rows transcribed</td><td>{link(S['S04']['url'], 'Injury PDF')}</td><td>{chip('Verified to source', 'ok')} {n_u} rows left blank</td></tr>
<tr><td>Injury reporting deadlines</td><td>{link(S['S02']['url'], 'Injury report index')}</td><td>{chip('Verified to source', 'ok')}</td></tr>
<tr><td>NBA Statistics restricted for gambling use (§9)</td><td>{link(S['S07']['url'], 'Terms of Use')}</td><td>{chip('Verified to source', 'ok')} read in part</td></tr>
<tr><td>Online sports betting offers need a Koa licence</td><td>{link(S['S09']['url'], 'Ksa')}</td><td>{chip('Verified to source', 'ok')} (Dutch)</td></tr>
</tbody></table></div>
<h2>What is not known (and why it blocks decisions)</h2>
<ul class="tight">
<li>Odds and prop prices, with timestamps, under a licence (7C-F-03).</li>
<li>Authorized historical statistics and minutes (7C-F-01, 7C-F-04, 7C-F-05).</li>
<li>Any measured correlation (7C-F-06) or any out-of-sample result.</li>
<li>Your leaderboard metric, thresholds, and risk limits (Q-10, Q-11).</li>
</ul>
<h2>Decisions needed from you</h2>
<p>See the <a href="suggestions.html">Suggestions</a> page. Each proposal has options (for example SG-01: legal path A, B, or C; SG-02: data-rights path A, B, or C). Nothing is implemented until you choose.</p>
</section>
"""
    out["executive-summary.html"] = ("Executive summary", body, "Executive summary of NBA Edge Lab.")

    # ---------- Slate ----------
    rows = []
    for g in sched["games"]:
        orient = g["orientation"]
        conf = orient.startswith("Confirmed")
        rows.append([
            esc(g["game_no"]),
            esc(g["day"]) + " " + esc(g["date"]),
            esc(g["team_1"]) + " @ " + esc(g["team_2"]) if conf else esc(g["team_1"]) + " vs " + esc(g["team_2"]) + ' <span class="muted">(printed order)</span>',
            esc(g["tip_et"]),
            esc(g["national_tv"]) or '<span class="muted">—</span>',
            esc(g["hash_col"]) or '<span class="muted">—</span>',
            chip("Orientation confirmed", "ok") if conf else chip("Unverified order", "unverified"),
            '<span class="muted">No pick — gates not passed (7C-F-03)</span>',
            link(sched["source_url"], "S05 schedule PDF"),
        ])
    body = f"""
<section class="card">
<h1>3-day slate (11/13–11/16/2026)</h1>
<p class="lede">Source: {link(sched['source_url'], sched['source_title'])}. Release page: {link(sched['release_page'], 'NBA.com schedule release')}. Tip times are the ET column. {esc(sched['times_note'])}</p>
{banner_research()}
<div class="banner warn"><b>Subject to change.</b> The PDF is labelled as of August 13, 2026. Re-pull before use (7C-F-09). "@" marks away @ home only where the injury report confirms it (11/13 and 11/14). For 11/15 and 11/16 the order is as printed (7C-F-10). The marker column (C/R) has no legend in the text read (7C-F-11).</div>
{table(["Game #", "Day / date", "Matchup", "Tip (ET)", "National TV", "Marker", "Orientation", "Pick / line", "Source"], rows, "slate", True)}
</section>
"""
    out["slate.html"] = ("3-day slate", body, "Official 2026-27 schedule for 11/13–11/16/2026.")

    # ---------- Injuries ----------
    rows = []
    attr_chip = {"R": chip("R · printed", "ok"), "S": chip("S · via schedule", "unverified"), "U": chip("U · blank", "blocker"), "T": chip("T · team row", "neutral")}
    for r in inj:
        matchup = esc(r["matchup"]) if r["matchup"] else '<span class="flag">blank</span>'
        team = esc(r["team"]) if r["team"] else '<span class="flag">blank</span>'
        player = esc(r["player"]) if r["player"] else '<span class="muted">— (team row)</span>'
        rows.append([
            esc(r["id"]), esc(r["game_date"]), esc(r["game_time_et"]) or '<span class="muted">—</span>', matchup, team,
            player, esc(r["status_as_printed"]), esc(r["reason_as_printed"]) or '<span class="muted">—</span>',
            attr_chip.get(r["attribution"], esc(r["attribution"])), esc(r["flag"]) or '<span class="muted">—</span>',
            link(r["report_source"], "S04 PDF"),
        ])
    body = f"""
<section class="card">
<h1>Injury tracker — official report 11/13/26 5:00 PM</h1>
<p class="lede">Every player row printed in the official report, transcribed as printed. Source: {link(inj[0]['report_source'], 'Injury Report PDF, 11/13/26 05:00 PM')}. Index: {link(S['S02']['url'], 'NBA Official injury report 2026-27')}.</p>
{banner_research()}
<div class="banner warn"><b>What this does not show.</b> The report has no minutes or production fields, so no effect on rotation minutes is estimated (7C-F-05). Blank cells are values the PDF text did not attribute (7C-F-08). Reports are updated through the day (S02); this is a single snapshot.</div>
<h3>Attribution key</h3>
<ul class="tight">
<li><b>R</b>: team and matchup printed in the same row or block.</li>
<li><b>S</b>: team printed; matchup linked to the official schedule pairing (S05). Confirm in the PDF.</li>
<li><b>U</b>: team and matchup not extracted from the PDF text. Left blank.</li>
<li><b>T</b>: team-level row printed as "NOT YET SUBMITTED".</li>
</ul>
<p class="muted">Counts: {len(inj)} rows · {n_u} unattributed · {n_s} schedule-linked · {n_nys} team rows not yet submitted.</p>
{table(["ID", "Date", "Time (ET)", "Matchup", "Team", "Player (as printed)", "Status", "Reason (as printed)", "Attribution", "Flag", "Source"], rows, "injuries", True)}
</section>
"""
    out["injuries.html"] = ("Injury tracker", body, "Official 11/13/26 5:00 PM NBA injury report, transcribed.")

    # ---------- Game flow ----------
    gf = game_flow_rows(d)
    rows = []
    for g in gf:
        status_cell = (chip("NOT YET SUBMITTED", "neutral") if g["not_submitted"] else "")
        if g["rows"] == 0:
            status_cell += ' <span class="muted">no player rows for this team in the report</span>'
        rows.append([
            esc(g["game_no"]), esc(g["date"]), esc(g["matchup"]), esc(g["team"]),
            f'<span class="num">{g["out"]}</span>', f'<span class="num">{g["q"]}</span>',
            f'<span class="num">{g["prob"]}</span>', f'<span class="num">{g["avail"]}</span>', f'<span class="num">{g["rows"]}</span>',
            status_cell or '<span class="muted">—</span>',
            f'<span class="flag">not estimated</span>', f'<span class="flag">not estimated</span>',
            link(sched["source_url"], "S05") + " · " + link(inj[0]["report_source"], "S04"),
        ])
    body = f"""
<section class="card">
<h1>Game flow and injury impact (11/13–11/14)</h1>
<p class="lede">Counts below come only from attributed rows of the official 11/13 5:00 PM report (attribution R or S). Unattributed rows (U) are excluded and noted. Games on 11/15–11/16 have no report in this snapshot.</p>
{banner_research()}
<div class="banner warn"><b>Game-flow analysis is not built.</b> Pace, possessions, scoring model, lineup and minutes data are not verified (7C-F-04, 7C-F-05). The two rightmost columns stay blank until authorized data exists. Counts are facts about the report, not impact estimates.</div>
{table(["Game #", "Date", "Matchup (schedule order)", "Team", "Out", "Questionable / Doubtful", "Probable", "Available", "Rows", "Team status", "Rotation minutes effect", "Production effect", "Sources"], rows, "gameflow", True)}
<h3>Unattributed rows excluded</h3>
<p class="muted">{n_u} rows (U) carry no team or matchup text in the PDF extraction. They are on the Injury tracker, left blank, and not assigned to any game here.</p>
</section>
"""
    out["game-flow.html"] = ("Game flow", body, "Team status counts from the official 11/13 injury report.")

    # ---------- Strategies ----------
    rows = []
    for s in d["strategies"]:
        off = link(s["official"], "official source") if s["official"] else '<span class="flag">UNVERIFIED — none</span>'
        kind = "blocker" if "Blocked" in s["status"] else "unverified"
        rows.append([
            esc(s["id"]), esc(s["cat"]), esc(s["name"]), esc(s["hyp"]), esc(s["inputs"]),
            off, chip(s["status"], kind),
            '<span class="flag">blank (unmeasured)</span>', '<span class="flag">blank</span>', '<span class="flag">blank</span>',
        ])
    body = f"""
<section class="card">
<h1>Strategy research</h1>
<p class="lede">Candidate strategies for single bets, player props, parlays, and combos, plus injury and context signals. These are hypotheses to test. None has passed a gate, and none is a claimed edge.</p>
{banner_research()}
<h2>Candidates</h2>
{table(["ID", "Type", "Strategy", "Hypothesis", "Inputs needed", "Official source for inputs", "Gate status", "Correlation", "ROI", "CLV / calibration"], rows, "strategies", True)}
<h2>Leaderboard rules (proposal only)</h2>
<p>Pre-registration is proposed as SG-04: a primary metric (for example Brier or log loss against a no-vig market baseline, closing-line value, or net ROI with a bootstrap interval), a minimum sample, a horizon, and thresholds. Owner-set values are required before any evaluation. No thresholds are set here.</p>
<h2>Parlay and combo policy</h2>
<ul class="tight">
<li>A parlay's probability is not the product of its legs unless independence is tested (G7).</li>
<li>Same-game correlations are unmeasured. Blank by policy (7C-F-06).</li>
<li>Player-prop combos need minutes data (7C-F-05) and price data (7C-F-03).</li>
</ul>
</section>
"""
    out["strategies.html"] = ("Strategies", body, "Candidate strategies and blocked status.")

    # ---------- Validation ----------
    rows = []
    for g in d["gates"]:
        rows.append([esc(g["id"]), esc(g["name"]), esc(g["crit"]), src_links(g["src"], S) if g["src"] else '<span class="flag">UNVERIFIED — methodology proposal, no official source</span>', chip(g["status"], "blocker" if "Blocked" in g["status"] else "unverified")])
    body = f"""
<section class="card">
<h1>Validation gates and correlation</h1>
<p class="lede">Each strategy must pass these gates in order before it can be ranked. None has been run. Thresholds are owner-set (SG-04).</p>
{banner_research()}
{table(["Gate", "Name", "Pass criterion (what must be shown)", "Official source", "Status"], rows, "gates", False)}
<h2>Correlation values</h2>
<p>No correlation values are published. Correlations between markets, players, or games are blank until measured out-of-sample with an interval and sample count (G7). Estimates are not filled in.</p>
</section>
"""
    out["validation.html"] = ("Validation & correlation", body, "Validation gates and correlation policy.")

    # ---------- Questions ----------
    rows = []
    for q in d["questions"]:
        st = q["status"]
        kind = "ok" if st.startswith("Answered") and "restricted" not in st and "no" not in st.lower() else ("blocker" if st.startswith("Answered — restricted") else "unverified")
        if st == "Answered — no":
            kind = "neutral"
        rows.append([esc(q["id"]), esc(q["q"]), chip(st, kind), esc(q["known"]), esc(q["missing"]), esc(q["next"]), src_links(q["src"], S) if q["src"] else '<span class="flag">UNVERIFIED — none</span>'])
    body = f"""
<section class="card">
<h1>Questions — what is known and what is missing</h1>
<p class="lede">Each question is answered only from the sources listed. "Not answered" means the information is not in the repository and no official source provides it. Answers are not inferred.</p>
{banner_research()}
{table(["ID", "Question", "Status", "Known (sourced)", "Missing", "Next step", "Sources"], rows, "questions", True)}
</section>
"""
    out["questions.html"] = ("Questions", body, "Questions, answers, and gaps.")

    # ---------- Suggestions ----------
    rows = []
    for s in d["suggestions"]:
        opts = "<br>".join(esc(o) for o in s["options"])
        rows.append([esc(s["id"]), esc(str(s["priority"])), esc(s["suggestion"]), esc(s["why"]), esc(s["dependency"]), opts,
                     src_links(s["src"], S) if s["src"] else '<span class="muted">none</span>',
                     chip("Awaiting your selection", "neutral")])
    body = f"""
<section class="card">
<h1>Suggestions — choose a path before anything changes</h1>
<p class="lede">These are proposals. Nothing is implemented until you choose an option. To decide, reply with the ID and option (for example, "SG-01: A").</p>
{banner_research()}
{table(["ID", "Priority", "Suggestion", "Why", "Dependency", "Options", "Sources", "Decision"], rows, "suggestions", True)}
<h2>Suggested review order</h2>
<ol class="tight"><li>SG-01 (legal) and SG-02 (data rights): they gate everything else.</li><li>SG-03 and SG-04: provenance and pre-registration.</li><li>SG-05 and SG-06: scope the models after data is in place.</li><li>SG-07 to SG-10: site and governance.</li></ol>
</section>
"""
    out["suggestions.html"] = ("Suggestions", body, "Suggestion queue for owner decisions.")

    # ---------- Sources ----------
    rows = []
    for s in d["sources"]:
        rows.append([f'<span id="{esc(s["id"])}">{esc(s["id"])}</span>', esc(s["title"]), esc(s["publisher"]), link(s["url"]), esc(s["retrieved"]), esc(s["result"]), esc(s["checked"]), esc(s["limit"])])
    body = f"""
<section class="card">
<h1>Official sources</h1>
<p class="lede">Every source used in this site, with the date checked, what was read, and what it does not support. A source marked FAILED or 'search snippet only' is not used as evidence.</p>
{table(["ID", "Source", "Publisher", "Link", "Checked", "Result", "What it supports (as read)", "Limits"], rows, "sources", True)}
</section>
"""
    out["sources.html"] = ("Sources", body, "Official source register with verification notes.")

    # ---------- Repo review ----------
    rows = []
    for r in d["repo"]:
        rows.append([esc(r["id"]), esc(r["item"]), esc(r["obs"]), link(r["src"], "source"), esc(r["status"])])
    body = f"""
<section class="card">
<h1>Repository review</h1>
<p class="lede">Findings from reviewing the repository, with the GitHub or API source for each. Irregularities are flagged for owner review (see <a href="flagged.html">Flagged for Review</a>).</p>
{table(["ID", "Item", "Observation", "Source", "Status"], rows, "repo", True)}
</section>
"""
    out["repo-review.html"] = ("Repo review", body, "Repository review with source links.")

    # ---------- Flagged ----------
    rows = []
    kind_map = {"Blocker": "blocker", "Unverified": "unverified", "Irregularity": "irregular"}
    for f in flags:
        rows.append([esc(f["id"]), chip(f["type"], kind_map[f["type"]]), esc(f["item"]), esc(f["why"]), esc(f["action"]), src_links(f["sources"], S) if f["sources"] else '<span class="flag">none</span>'])
    body = f"""
<section class="card" id="flagged">
<h1>Flagged for Review</h1>
<p class="lede">Published for owner review after go-live. These items do not block the merge. Each has its source link where one exists. Request changes by ID.</p>
<div class="banner warn"><b>Blockers:</b> 7C-F-01 (NBA Terms §9) and 7C-F-02 (Dutch licence) prevent the betting features from being built. 7C-F-03 blocks lines and picks. Everything else is unverified or an irregularity.</div>
{table(["ID", "Type", "Item", "Why flagged", "Action / review", "Sources"], rows, "flags", True)}
</section>
"""
    out["flagged.html"] = ("Flagged for Review", body, "Flagged for Review: blockers, unverified items, irregularities.")

    return out


def write_site(pages, site_dir):
    os.makedirs(os.path.join(site_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(site_dir, "data"), exist_ok=True)
    with open(os.path.join(site_dir, "assets", "site.css"), "w", encoding="utf-8") as f:
        f.write(CSS.strip() + "\n")
    with open(os.path.join(site_dir, "assets", "site.js"), "w", encoding="utf-8") as f:
        f.write(JS.strip() + "\n")
    for name, (title, body, desc) in pages.items():
        with open(os.path.join(site_dir, name), "w", encoding="utf-8") as f:
            f.write(page(name, title, body, desc))
    # Downloadable copies of the data (JSON)
    for fn in sorted(os.listdir(DATA)):
        if fn.endswith(".json"):
            with open(os.path.join(DATA, fn), encoding="utf-8") as src, open(os.path.join(site_dir, "data", fn), "w", encoding="utf-8") as dst:
                dst.write(src.read())
    with open(os.path.join(site_dir, ".nojekyll"), "w") as f:
        f.write("")


class LinkCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a and a["id"]:
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag in ("link", "script") and (a.get("href") or a.get("src")):
            self.hrefs.append(a.get("href") or a.get("src"))


def check_links(site_dir):
    pages = {}
    for fn in sorted(os.listdir(site_dir)):
        if fn.endswith(".html"):
            p = LinkCheck()
            with open(os.path.join(site_dir, fn), encoding="utf-8") as f:
                p.feed(f.read())
            pages[fn] = p
    n = 0
    for fn, p in pages.items():
        for h in p.hrefs:
            n += 1
            if h.startswith(("http://", "https://", "mailto:")):
                continue
            if h.startswith("#"):
                if h[1:] and h[1:] not in p.ids:
                    err(f"{fn}: broken in-page anchor {h}")
                continue
            target, _, frag = h.partition("#")
            path = os.path.normpath(os.path.join(site_dir, target))
            if not os.path.exists(path):
                err(f"{fn}: broken link {h}")
                continue
            if frag and target.endswith(".html"):
                tp = pages.get(os.path.basename(target))
                if tp and frag not in tp.ids:
                    err(f"{fn}: broken anchor {h}")
    return n, len(pages)


def main():
    check_only = "--check" in sys.argv
    d = load_all()
    validate(d)
    if ERRORS:
        print("VALIDATION FAILED:")
        for e in ERRORS:
            print(" -", e)
        sys.exit(1)
    import tempfile
    pages = render_pages(d)
    target = tempfile.mkdtemp() if check_only else SITE
    write_site(pages, target)
    n, np_ = check_links(target)
    if ERRORS:
        print("LINK CHECK FAILED:")
        for e in ERRORS:
            print(" -", e)
        sys.exit(1)
    print(f"OK: validated {len(d['injuries'])} injury rows, {len(d['schedule']['games'])} games, {len(d['sources'])} sources; "
          f"checked {n} links across {np_} pages.")


if __name__ == "__main__":
    main()
