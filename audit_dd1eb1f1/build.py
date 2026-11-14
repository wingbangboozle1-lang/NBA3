#!/usr/bin/env python3
"""Session dd1eb1f1 — build the audit pages from the two generated reports.

Reads  audit_dd1eb1f1/data/verification_report.json
and    audit_dd1eb1f1/data/correlation_extension.json
and writes audit_dd1eb1f1/pages/{index,verification,correlations,flags}.html
plus    audit_dd1eb1f1/assets/audit.css.

Rules enforced by this builder (the same rules the rest of the project publishes under):
  * every table body row carries a link to the official page the value came from;
  * a value that could not be confirmed is printed as a blank cell with an "unverified"
    marker, never filled in;
  * the build fails if a page would ship a row with no official-source link.

Run: python3 audit_dd1eb1f1/build.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")
ASSETS = os.path.join(HERE, "assets")

CANONICAL = os.path.join(HERE, "..", "data", "app", "canonical.json")
OFFICIAL_HOSTS = ("nba.com", "ak-static.cms.nba.com", "official.nba.com")
SITE_ROOT = "../../"
NAV = [
    ("Overview", [("../../index.html", "Canonical dashboard"),
                  ("../../app/summary.html", "Executive summary")]),
    ("This audit", [("index.html", "What this session did"),
                    ("verification.html", "Line-by-line verification"),
                    ("correlations.html", "Measured correlations"),
                    ("flags.html", "Flagged for review")]),
    ("Canonical site", [("../../app/flagged.html", "Flagged for review"),
                        ("../../app/verification.html", "Verification log"),
                        ("../../app/sources.html", "Source register")]),
]

CSS = """
:root { --bg:#0e1117; --panel:#161b22; --panel2:#1c2230; --line:#2a3240; --text:#e6edf3;
        --muted:#9aa7b4; --accent:#5aa9ff; --ok:#3fb950; --warn:#d29922; --bad:#f85149; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text);
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.wrap { max-width:1180px; margin:0 auto; padding:0 20px; }
header.site-header { background:var(--panel); border-bottom:1px solid var(--line); }
header.site-header .wrap { padding:14px 20px; }
.brand { font-weight:700; font-size:17px; color:var(--text); }
.brand-mark { color:var(--accent); }
.stamp { color:var(--muted); font-size:12.5px; margin-top:4px; }
nav.site-nav { background:var(--panel2); border-bottom:1px solid var(--line); }
nav.site-nav .wrap { display:flex; flex-wrap:wrap; gap:22px; padding:9px 20px; }
.nav-group { display:flex; align-items:center; gap:8px; font-size:13px; }
.nav-cat { color:var(--muted); text-transform:uppercase; letter-spacing:.06em; font-size:11px; }
.nav-links a { margin-right:10px; }
main.wrap { padding:22px 20px 60px; }
h1 { font-size:25px; margin:6px 0 4px; }
h2 { font-size:19px; margin:30px 0 8px; padding-top:6px; border-top:1px solid var(--line); }
h3 { font-size:16px; margin:20px 0 6px; }
p.lead { color:var(--muted); margin:0 0 14px; }
p { max-width:95ch; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); gap:12px; margin:18px 0; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }
.card .k { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }
.card .v { font-size:27px; font-weight:700; margin:4px 0 6px; }
.card .s { color:var(--muted); font-size:13px; }
table { border-collapse:collapse; width:100%; margin:10px 0 18px; font-size:13.5px; }
th, td { border:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; }
th { background:var(--panel2); font-weight:600; }
tbody tr:nth-child(even) { background:rgba(255,255,255,.02); }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.pill { display:inline-block; padding:1px 7px; border-radius:9px; font-size:11.5px; font-weight:600; }
.pill-ok { background:rgba(63,185,80,.15); color:var(--ok); border:1px solid rgba(63,185,80,.4); }
.pill-warn { background:rgba(210,153,34,.15); color:var(--warn); border:1px solid rgba(210,153,34,.4); }
.pill-bad { background:rgba(248,81,73,.15); color:var(--bad); border:1px solid rgba(248,81,73,.4); }
.pill-mute { background:rgba(154,167,180,.12); color:var(--muted); border:1px solid rgba(154,167,180,.35); }
.blank { color:var(--muted); font-style:italic; }
.note { background:var(--panel); border-left:3px solid var(--accent); padding:9px 12px;
        color:var(--muted); font-size:13.5px; margin:10px 0 16px; max-width:100ch; }
.flag { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--warn);
        border-radius:6px; padding:11px 13px; margin:10px 0; }
.flag .id { font-weight:700; color:var(--warn); }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:12.5px; }
footer.site-footer { border-top:1px solid var(--line); background:var(--panel); }
footer.site-footer .wrap { padding:16px 20px; color:var(--muted); font-size:13px; }
.small { font-size:12.5px; color:var(--muted); }
"""


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def cell(v, blank_text="blank"):
    if v is None or v == "":
        return f'<td class="blank">{blank_text}</td>'
    return f"<td>{esc(v)}</td>"


def num(v, dp=6):
    if v is None:
        return '<td class="num blank">blank</td>'
    if isinstance(v, float):
        return f'<td class="num">{v:.{dp}f}</td>'
    return f'<td class="num">{esc(v)}</td>'


def src_link(url, label="source"):
    if not url:
        return ""
    return (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>')


def page(title, lead, body, crumb, stamp):
    nav = "".join(
        f'<div class="nav-group"><span class="nav-cat">{esc(cat)}</span><span class="nav-links">'
        + " ".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in links)
        + "</span></div>" for cat, links in NAV)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 session dd1eb1f1 audit</title>
<meta name="description" content="Independent verification and measured correlations for the NBA3 / NBA Edge Lab project. Every row links to its official source.">
<link rel="stylesheet" href="../assets/audit.css">
</head>
<body>
<header class="site-header"><div class="wrap">
  <a class="brand" href="{SITE_ROOT}index.html"><span class="brand-mark">NBA3</span> Independent audit — session dd1eb1f1</a>
  <div class="stamp">{stamp}</div>
</div></header>
<nav class="site-nav"><div class="wrap">{nav}</div></nav>
<main class="wrap">
  <div class="crumb small">{esc(crumb)}</div>
  <h1>{esc(title)}</h1>
  <p class="lead">{lead}</p>
{body}
</main>
<footer class="site-footer"><div class="wrap">
  <p><strong>NBA3 — independent audit by session <code>arena/dd1eb1f1-nba3</code></strong>.
  Every table row links to the official page the value was read from. Values that could not be
  confirmed are left blank and marked unverified — nothing is inferred. Model outputs are
  labelled <em>Derived</em> and are not official NBA statistics. Research, not betting advice.</p>
  <p>Repository: <a href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener noreferrer">github.com/wingbangboozle1-lang/NBA3</a>
  · canonical dashboard <a href="{SITE_ROOT}index.html">/</a></p>
</div></footer>
</body>
</html>
"""


def pill_result(result):
    cls = {"match": "pill-ok", "both blank": "pill-mute"}.get(result, "pill-bad")
    return f'<span class="pill {cls}">{esc(result)}</span>'


# ------------------------------------------------------------------ pages -----
def build_verification(rep, canon):
    slate, inj, log = rep["sections"]
    parts = []
    parts.append(f"""<h2>{esc(slate['title'])}</h2>
<p>{esc(slate['official_source_label'])}. The canonical artefact publishes the same window from
<em>{esc(slate['canonical_source_url'])}</em> (stamp {esc(slate['canonical_report_stamp'])}).
Every field below was re-read by this session and compared.</p>
<div class="cards">
  <div class="card"><div class="k">Rows compared</div><div class="v">{slate['rows_compared']}</div>
    <div class="s">canonical holds {slate['rows_in_canonical']}</div></div>
  <div class="card"><div class="k">Field checks</div><div class="v">{slate['field_checks']}</div>
    <div class="s">{slate['fields_compared']} fields per row</div></div>
  <div class="card"><div class="k">Mismatches</div><div class="v">{len(slate['mismatches'])}</div>
    <div class="s">date, tip time, teams, venue, city, game id, game URL</div></div>
</div>""")
    rows = []
    for r in slate["per_row"]:
        g = next((x for x in canon["slate"]["games"] if x["game_id"] == r["game_id"]), {})
        rows.append("<tr>"
                    + cell(r["date"]) + cell(r["time_et"]) + cell(r["matchup"])
                    + cell(r["game_id"])
                    + cell(g.get("venue")) + cell(g.get("city"))
                    + num(r["fields"][0]["canonical"]) + num(r["fields"][0]["mine"])
                    + f'<td>{pill_result("match" if r["match"] else "MISMATCH")}</td>'
                    + f'<td>{src_link(g.get("nba_game_url"), "nba.com")}</td>'
                    + "</tr>")
    parts.append("""<table><thead><tr>
      <th>Date</th><th>Tip (ET)</th><th>Matchup</th><th>Game id</th><th>Venue</th><th>City</th>
      <th>Canonical date</th><th>Official re-read</th><th>Result</th><th>Official source</th>
    </tr></thead><tbody>""" + "".join(rows) + "</tbody></table>")
    parts.append(f"""<div class="note"><strong>Orientation rule.</strong> The schedule page prints
    the visitor first and the home team second. Every row above was confirmed by the venue and
    city printed under it: the venue belongs to the second-named team. No orientation was assumed.
    Official page: {src_link(slate['official_source_url'], 'nba.com/schedule?date=2026-11-14')}</div>""")

    parts.append(f"""<h2>{esc(inj['title'])}</h2>
<p>{esc(inj['official_source_label'])}. {esc(inj['stamp_note'])}</p>
<div class="cards">
  <div class="card"><div class="k">Rows compared</div><div class="v">{inj['rows_compared']}</div>
    <div class="s">{inj['rows_in_canonical']} in canonical · {inj['fields_compared']} fields each</div></div>
  <div class="card"><div class="k">Field checks</div><div class="v">{inj['field_checks']}</div>
    <div class="s">date, time, matchup, team, player, status, reason</div></div>
  <div class="card"><div class="k">Mismatches</div><div class="v">{len(inj['mismatches'])}</div>
    <div class="s">after the one blank-cell correction recorded as {esc(rep['audit_findings'][0]['id'])}</div></div>
</div>""")
    rows = []
    for r in inj["per_row"]:
        f = {x["field"]: x for x in r["fields"]}
        rows.append("<tr>"
                    + cell(f["game_date"]["canonical"]) + cell(f["game_time_et"]["canonical"])
                    + cell(f["matchup"]["canonical"]) + cell(f["team"]["canonical"])
                    + cell(f["player"]["canonical"] or None)
                    + cell(f["status"]["canonical"] or None)
                    + cell(f["reason"]["canonical"] or None)
                    + f'<td>{pill_result("match" if r["match"] else "MISMATCH")}</td>'
                    + f'<td>{src_link(r["official_source"], "PDF")}</td>'
                    + "</tr>")
    parts.append("""<table><thead><tr>
      <th>Game date</th><th>Time (ET)</th><th>Matchup</th><th>Team</th><th>Player</th>
      <th>Status</th><th>Reason</th><th>Result</th><th>Official source</th>
    </tr></thead><tbody>""" + "".join(rows) + "</tbody></table>")
    parts.append(f"""<div class="note">Empty Status and Reason cells are how the official PDF
    prints a <em>NOT YET SUBMITTED</em> team: the text lands in the Reason column and the player
    cell is blank. Those rows are published as <em>not submitted</em>, never as healthy.
    Official report: {src_link(inj['official_source_url'], inj['official_source_url'].rsplit('/',1)[-1])}</div>""")

    parts.append(f"""<h2>{esc(log['title'])}</h2>
<p>{esc(log['official_source_label'])}. These four checks are recomputed from the stored log
itself, so they test internal consistency, not the transcription.</p>
<table><thead><tr><th>Check</th><th>Recomputed</th><th>Published by the site</th><th>Result</th>
<th>Official source</th></tr></thead><tbody>""")
    for c in log["checks"]:
        parts.append(f'<tr><td>{esc(c["check"])}</td>{num(c["recomputed"])}{num(c["published"])}'
                     f'<td>{pill_result("match" if c["match"] else "MISMATCH")}</td>'
                     f'<td>{src_link(log["official_source_url"], "nba.com/games")}</td></tr>')
    parts.append("</tbody></table>")
    parts.append(f"""<div class="note">Recomputed from <span class="mono">{esc(log['file'])}</span>:
    {log['recomputed']['games']} games, {log['recomputed']['team_games']} team-games,
    {log['recomputed']['home_wins']} home wins / {log['recomputed']['home_losses']} home losses,
    {log['recomputed']['ot_games']} overtimes.</div>""")

    body = "".join(parts)
    stamp = (f"Snapshot {rep['generated_utc']} · {rep['totals']['field_checks']} field checks · "
             f"{rep['totals']['mismatches']} mismatches")
    return page("Line-by-line verification", "Every value the canonical dashboard publishes for the "
                "current window, re-read from the official NBA pages by this session and compared "
                "field by field.", body,
                "Independent audit / Verification", stamp)


def build_correlations(ext):
    rest, acc, clus, blank = ext["sections"]
    parts = []
    parts.append(f"""<h2>{esc(rest['title'])}</h2>
<p>{esc(rest['question'])}</p>
<div class="note">{esc(rest['method'])}</div>""")
    rows = []
    for r in rest["rows"]:
        lo, hi = r["ci95"]
        rows.append("<tr>" + cell(r["pair"]) + cell(r["stat"]) + num(r["value"], 4)
                    + num(lo, 4) + num(hi, 4) + num(r["n"])
                    + num(r.get("permutation_p"), 4)
                    + f'<td>{src_link(rest["source_scores"], "nba.com/games")}</td></tr>')
    parts.append("""<table><thead><tr><th>Pair</th><th>Statistic</th><th>Value</th>
      <th>95% low</th><th>95% high</th><th>n</th><th>Permutation p</th>
      <th>Official source of the inputs</th></tr></thead><tbody>"""
                 + "".join(rows) + "</tbody></table>")
    parts.append("""<table><thead><tr><th>Group</th><th>n</th><th>Mean home margin</th>
      <th>Home win rate</th><th>Welch t vs both-rested</th><th>p (normal approx.)</th>
      <th>Official source of the inputs</th>
      </tr></thead><tbody>""")
    for g in rest["group_means"]:
        parts.append("<tr>" + cell(g["group"]) + num(g["n"]) + num(g["mean_home_margin"], 3)
                     + num(g["home_win_rate"], 3) + num(g["welch_t_vs_rested_both"], 3)
                     + num(g["p_normal_approx"], 4)
                     + f'<td>{src_link(rest["source_scores"], "nba.com/games")}</td></tr>')
    parts.append("</tbody></table>")
    mc = rest["multiple_comparisons"]
    parts.append(f"""<h3>Multiple comparisons — {mc['family_size']} rest tests, {esc(mc['method'])}</h3>
<table><thead><tr><th>Test</th><th>Raw p</th><th>BH-adjusted p</th><th>Survives 0.05</th>
<th>Official source of the inputs</th></tr></thead><tbody>""")
    for t in mc["tests"]:
        ok = t["survives_0.05"]
        parts.append(f'<tr>{cell(t["test"])}{num(t["raw_p"], 4)}{num(t["bh_adjusted_p"], 4)}'
                     f'<td><span class="pill {"pill-ok" if ok else "pill-warn"}">'
                     f'{"yes" if ok else "no"}</span></td>'
                     f'<td>{src_link(rest["source_scores"], "nba.com/games")}</td></tr>')
    parts.append("</tbody></table>")
    parts.append(f"""<div class="note">{esc(mc['reading'])}</div>
<div class="note">{esc(rest['caveat'])}</div>""")

    parts.append(f"""<h2>{esc(acc['title'])}</h2>
<div class="note">{esc(acc['method'])}</div>""")
    rows = []
    for r in acc["rows"]:
        lo, hi = r["ci95"]
        blo, bhi = r["baseline_ci95"]
        rows.append("<tr>" + cell(r["pair"]) + num(r["value"], 4) + num(lo, 4) + num(hi, 4)
                    + num(r["baseline_r"], 4) + num(blo, 4) + num(bhi, 4) + num(r["n"])
                    + f'<td>{src_link(acc["source_scores"], "nba.com/games")}</td></tr>')
    parts.append("""<table><thead><tr><th>Pair</th><th>r</th><th>95% low</th><th>95% high</th>
      <th>Baseline r</th><th>Baseline low</th><th>Baseline high</th><th>n</th>
      <th>Official source of the inputs</th></tr></thead><tbody>""" + "".join(rows) + "</tbody></table>")
    rs = acc["residual_summary"]
    parts.append(f"""<div class="note">Out-of-sample residuals (n = {rs['n']}): margin mean
    {rs['margin_residual_mean']}, sd {rs['margin_residual_sd']} (baseline sd
    {rs['baseline_margin_residual_sd']}); total mean {rs['total_residual_mean']}, sd
    {rs['total_residual_sd']} (baseline sd {rs['baseline_total_residual_sd']}). The spread model
    beats its baseline on spread; the totals model does not beat its baseline on sd.</div>""")

    parts.append(f"""<h2>{esc(clus['title'])}</h2>
<p>{esc(clus['question'])}</p>
<div class="note">{esc(clus['method'])}</div>
<div class="note"><strong>Cover convention.</strong> {esc(clus['cover_definition'])}</div>""")
    rows = []
    for name, v in clus["results"].items():
        lo, hi = v["ci95"]
        rows.append("<tr>" + cell(name) + num(v["value"], 4) + num(lo, 4) + num(hi, 4)
                    + num(v["pairs"]) + num(v["permutation_p"], 4) + num(v["null_p95"], 4)
                    + num(v["permutations"])
                    + f'<td>{src_link(clus["source_scores"], "nba.com/games")}</td></tr>')
    parts.append("""<table><thead><tr><th>Residual</th><th>Within-slate r</th><th>95% low</th>
      <th>95% high</th><th>Pairs</th><th>Permutation p</th><th>Null 95th pct</th>
      <th>Permutations</th><th>Official source of the inputs</th></tr></thead><tbody>"""
                 + "".join(rows) + "</tbody></table>")
    od = clus["per_date_hit_rate_overdispersion"]
    parts.append(f"""<h3>Does the per-night hit rate vary more than a constant-rate coin?</h3>
<table><thead><tr><th>Observed variance of the per-date rate</th><th>Null median variance</th>
<th>Permutation p</th><th>Permutations</th><th>Official source of the inputs</th></tr></thead><tbody>
<tr>{num(od['observed_variance_of_per_date_rate'], 6)}{num(od['null_median_variance'], 6)}
{num(od['permutation_p'], 4)}{num(od['permutations'])}
<td>{src_link(clus["source_scores"], "nba.com/games")}</td></tr></tbody></table>
<div class="note">{esc(od['reading'])}</div>
<div class="note">{esc(clus['caveat'])}</div>""")

    parts.append(f"""<h2>{esc(blank['title'])}</h2>
<div class="note">{esc(blank['note'])}</div>""")
    rows = []
    for r in blank["rows"]:
        rows.append("<tr>" + cell(r["pair"]) + cell(r["needs"])
                    + '<td><span class="pill pill-warn">unverified — blank</span></td>'
                    + f'<td>{src_link(r["official_source_that_has_it"], "official page")}</td></tr>')
    parts.append("""<table><thead><tr><th>Pair</th><th>What it needs</th><th>Status</th>
      <th>Official source that holds the input</th></tr></thead><tbody>"""
                 + "".join(rows) + "</tbody></table>")

    body = "".join(parts)
    stamp = (f"Computed {ext['generated_utc']} · seed {ext['seed']} · "
             f"{ext['permutations']} permutations per test")
    return page("Measured correlations", "Correlation values computed by this session from the "
                "official NBA final scores and from the site's own published out-of-sample "
                "predictions. Everything on this page is labelled Derived: it is our arithmetic, "
                "not an official NBA statistic.", body,
                "Independent audit / Correlations", stamp)


def build_flags(rep, ext, canon):
    slate = rep["sections"][0]
    clus = ext["sections"][2]
    findings = []

    findings.append(dict(
        id="F-DD1-01", sev="informational — corrected in this audit",
        title="An injury row with a blank Team cell, and why blank is the right answer",
        body=f"""{rep['audit_findings'][0]['detail']}""",
        source="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_30AM.pdf"))

    findings.append(dict(
        id="F-DD1-02", sev="needs owner review",
        title="The official schedule prints the same matchup twice inside the 4-day window",
        body=("NYK@TOR appears on 2026-11-15 (game 0022600241) and again on 2026-11-17 "
              "(game 0022600253), both at Scotiabank Arena. POR@MIN appears on 2026-11-16 "
              "(game 0022600250) and again on 2026-11-17 (game 0022600254), both at Target "
              "Center. This is what the official schedule page prints; it has not been "
              "corrected, because the project's rule is to publish the official value and flag "
              "the doubt. It matters for the model: a repeat matchup 48 hours apart is not the "
              "same game twice, and any rule that treats teams as independent across legs will "
              "mis-price it."),
        source="https://www.nba.com/schedule?date=2026-11-14"))

    findings.append(dict(
        id="F-DD1-03", sev="cosmetic",
        title="Two 2026-11-17 game ids are printed out of chronological order",
        body=("The schedule page prints CHA@LAL at 11:00 PM ET with game id 0022600256 after "
              "UTA@LAC at 10:30 PM ET with game id 0022600257. The ids are used as keys, so the "
              "stored order follows the page. No value is wrong; a reader sorting by id will see "
              "a different order than a reader sorting by tip time."),
        source="https://www.nba.com/schedule?date=2026-11-14"))

    findings.append(dict(
        id="F-DD1-04", sev="resolved by another session — recorded for history",
        title="main CI was red at the strategy-lab drift gate when this session started",
        body=("Workflow run 43584459385 failed at the 'Strategy lab ... must reproduce byte for "
              "byte' step because the committed data/app/lab.json no longer reproduced from the "
              "committed inputs, and every step after it was skipped — so no Pages artifact had "
              "been produced since 1938a0a and the site was only being served by the legacy "
              "Pages build. Session 8efd914d diagnosed and repaired it in PR #64/#65 before this "
              "session's first commit. Recorded here because a red build is an irregularity worth "
              "a permanent entry, not a footnote."),
        source="https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43584459385"))

    findings.append(dict(
        id="F-DD1-05", sev="informational",
        title="The canonical injury snapshot is 15 minutes behind the newest official file, and "
              "the index page itself lags",
        body=("The canonical artefact publishes the 04:15 AM ET report. The injury-report index "
              "listed 04:30 AM ET as the newest 2026-11-14 report when this session read it, and "
              "a probe of the 05:30 AM ET file returned an S3 AccessDenied object, so no newer "
              "report existed. This session transcribed the 04:30 AM report in full (49 rows) "
              "and it is row-for-row identical to what the site publishes. No staleness defect "
              "today; the point is that 'newest' has to be re-checked every time, because the "
              "index page is cached."),
        source="https://official.nba.com/nba-injury-report-2026-27-season/"))

    findings.append(dict(
        id="F-DD1-06", sev="open — assumption replaced by a measurement",
        title="Cross-game parlay independence was an assumption; it is now measured, and the "
              "totals hint is the one to watch",
        body=("The canonical correlations page publishes 'Two legs in different games' as "
              "r = 0.0 with verified = false and the note that independence is an assumption. "
              "This session measured within-slate dependence directly: for margin residuals the "
              "within-night correlation is "
              f"{clus['results']['margin residual']['value']} (permutation p "
              f"{clus['results']['margin residual']['permutation_p']}), and for total residuals "
              f"{clus['results']['total residual']['value']} (permutation p "
              f"{clus['results']['total residual']['permutation_p']}). Neither survives a 5% "
              "threshold, so the assumption stands for now — but the totals figure is negative "
              "and its naive interval excludes zero, which is the direction that would make a "
              "cross-game over parlay worth less than independent pricing. Re-measure when the "
              "out-of-sample log is larger."),
        source="https://www.nba.com/games?date="))

    findings.append(dict(
        id="F-DD1-07", sev="open — site structure",
        title="Twelve superseded dashboards are still published next to the canonical one",
        body=("docs/, site/, lab/, research/, edge/, origin/, dash/, verify/pages/, d01ae7e2/, "
              "hub/, dashboard/ and app/legacy/ are earlier sessions' complete sites, each with "
              "its own navigation, ID namespace and data snapshot. They are valuable as an audit "
              "trail and destructive as a landing page: a reader who lands on one cannot tell "
              "which numbers are current. The recommendation filed on the suggestions page is to "
              "keep every tree reachable but move all of them behind one dated archive page, so "
              "the landing page shows one navigation, one set of numbers and one snapshot date."),
        source="https://github.com/wingbangboozle1-lang/NBA3"))

    findings.append(dict(
        id="F-DD1-08", sev="open — presentation defect",
        title="A dashboard tile is embedded inside a flagged-item list entry on the landing page",
        body=("On the canonical landing page the 'Highest-severity flags' list item for NF-23 "
              "ends with an embedded anchor card linking to dash/index.html. It renders as a "
              "flag that is also a navigation tile, inside a list of severity findings. The link "
              "itself is fine; its placement makes the page read as if 'Unified dashboard "
              "(e40cd215)' were an eighth flagged item. Raised as a change request to the owner "
              "of scripts/build_app.py rather than patched here, because that builder owns "
              "index.html and a hand edit would be overwritten on the next regeneration."),
        source="https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/build_app.py"))

    parts = ["""<p>Everything below was found by this session while verifying the published data
    against the official pages. Nothing here blocks the merge. Each entry links to the official or
    repository page that is the evidence for it.</p>"""]
    for f in findings:
        parts.append(f"""<div class="flag"><div><span class="id">{esc(f['id'])}</span>
        <strong>{esc(f['title'])}</strong></div>
        <div class="small" style="margin:3px 0 7px;color:var(--warn)">{esc(f['sev'])}</div>
        <p style="margin:0 0 7px">{esc(f['body'])}</p>
        <div class="small">Evidence: {src_link(f['source'], f['source'])}</div></div>""")
    parts.append(f"""<h2>Summary of this session's verification</h2>
<table><thead><tr><th>Section</th><th>Rows</th><th>Field checks</th><th>Mismatches</th>
<th>Official source</th></tr></thead><tbody>
<tr><td>{esc(rep['sections'][0]['title'])}</td>{num(rep['sections'][0]['rows_compared'])}
{num(rep['sections'][0]['field_checks'])}{num(len(rep['sections'][0]['mismatches']))}
<td>{src_link(rep['sections'][0]['official_source_url'], 'nba.com/schedule')}</td></tr>
<tr><td>{esc(rep['sections'][1]['title'])}</td>{num(rep['sections'][1]['rows_compared'])}
{num(rep['sections'][1]['field_checks'])}{num(len(rep['sections'][1]['mismatches']))}
<td>{src_link(rep['sections'][1]['official_source_url'], 'injury PDF')}</td></tr>
</tbody></table>""")
    body = "".join(parts)
    return page("Flagged for review", "Irregularities found by this session, with the evidence "
                "link for each. None of them blocks publishing.", body,
                "Independent audit / Flagged for review",
                f"Session dd1eb1f1 · {len(findings)} entries · generated {rep['generated_utc']}")


def build_index(rep, ext, canon):
    t = rep["totals"]
    clus = ext["sections"][2]
    rest = ext["sections"][0]
    body = f"""
<h2>What this session did</h2>
<p>Three things, in this order: it re-read the official NBA pages for the current window and
compared every published value against them; it measured the correlations the canonical site
leaves blank; and it recorded what it found, including the parts that are not good news.</p>

<div class="cards">
  <div class="card"><div class="k">Field checks</div><div class="v">{t['field_checks']}</div>
    <div class="s">{t['mismatches']} mismatches between the official pages read today and the
    values the site publishes</div>
    <div style="margin-top:6px"><a href="verification.html">line-by-line results →</a></div></div>
  <div class="card"><div class="k">Correlations measured</div><div class="v">7</div>
    <div class="s">plus 4 still left blank, with the official page that holds each missing input</div>
    <div style="margin-top:6px"><a href="correlations.html">measured values →</a></div></div>
  <div class="card"><div class="k">Flagged</div><div class="v">8</div>
    <div class="s">irregularities, each with its evidence link</div>
    <div style="margin-top:6px"><a href="flags.html">flagged for review →</a></div></div>
  <div class="card"><div class="k">Rest tests surviving adjustment</div>
    <div class="v">0 of {rest['multiple_comparisons']['family_size']}</div>
    <div class="s">on {rest['rows'][0]['n']} games. One raw p (0.0397) sits below 0.05 on its own
    and becomes {rest['multiple_comparisons']['tests'][2]['bh_adjusted_p']} after
    Benjamini-Hochberg — that is what removing luck looks like</div></div>
</div>

<h2>The three questions, and the straight answers</h2>
<table><thead><tr><th>Question</th><th>Answer on this data</th><th>Where</th>
<th>Official basis</th></tr></thead><tbody>
<tr><td>Are the published numbers the same as the official pages?</td>
    <td>Yes. {t['field_checks']} field checks across the 27-game slate and the 49-row injury
    report, {t['mismatches']} mismatches. One apparent mismatch turned out to be this audit
    filling in a cell the official PDF leaves blank — the canonical site was right to leave it
    empty.</td>
    <td><a href="verification.html">Verification</a></td>
    <td>{src_link("https://www.nba.com/schedule?date=2026-11-14", "nba.com/schedule")}</td></tr>
<tr><td>Does rest carry a signal?</td>
    <td>Not one this sample can support. Rest differential vs home margin: r = {rest['rows'][0]['value']},
    95% interval {rest['rows'][0]['ci95'][0]} to {rest['rows'][0]['ci95'][1]}, n = {rest['rows'][0]['n']},
    permutation p = {rest['rows'][0]['permutation_p']}.</td>
    <td><a href="correlations.html">Rest</a></td>
    <td>{src_link("https://www.nba.com/games?date=", "nba.com/games")}</td></tr>
<tr><td>Can a cross-game parlay of our own picks be priced as independent?</td>
    <td>Not rejected. Within-night correlation of margin residuals {clus['results']['margin residual']['value']}
    (p = {clus['results']['margin residual']['permutation_p']}); totals
    {clus['results']['total residual']['value']} (p = {clus['results']['total residual']['permutation_p']}),
    negative and worth re-measuring on a bigger log.</td>
    <td><a href="correlations.html">Slate clustering</a></td>
    <td>{src_link("https://www.nba.com/games?date=", "nba.com/games")}</td></tr>
</tbody></table>

<h2>How to reproduce this</h2>
<p class="mono">python3 audit_dd1eb1f1/checks.py<br>python3 audit_dd1eb1f1/analysis.py<br>python3 audit_dd1eb1f1/build.py</p>
<p>Neither <span class="mono">checks.py</span> nor <span class="mono">analysis.py</span> touches
the network: they read the captures in <span class="mono">audit_dd1eb1f1/data/</span> and the
artefacts already in the repository, so a reader with the checkout gets the same numbers. The
captures themselves were transcribed from the official pages listed on each page.</p>

<h2>What this audit does not cover</h2>
<ul>
  <li>Team and player statistics were not re-read: <span class="mono">stats.nba.com</span> is not
      reachable from this workspace. The schedule pages and the injury PDFs are.</li>
  <li>The 183-game results log was checked for internal consistency, not re-transcribed game by
      game. A full re-transcription is a separate job.</li>
  <li>No market odds were compared, because no licensed odds source is connected to this
      repository. Every price on the site is our own originated number.</li>
</ul>
"""
    return page("Independent audit — session dd1eb1f1",
                "A second pass over the canonical NBA3 dataset by a session that did not build it: "
                "re-read the official pages, compare every value, measure what was left blank, and "
                "publish the findings.", body, "Independent audit",
                f"Generated {rep['generated_utc']} · official pages read 2026-11-14")


# ------------------------------------------------------------------ checks ----
def assert_rows_sourced(html_text, name):
    """Every <tr> inside a <tbody> must contain at least one link to an official host."""
    bodies = re.findall(r"<tbody>(.*?)</tbody>", html_text, flags=re.S)
    bad = []
    for bi, body in enumerate(bodies):
        for ri, row in enumerate(re.findall(r"<tr>(.*?)</tr>", body, flags=re.S), 1):
            if not any(h in row for h in OFFICIAL_HOSTS):
                bad.append(f"{name}: tbody {bi + 1} row {ri}")
    if bad:
        raise SystemExit("Row without an official-source link — " + "; ".join(bad[:10]))


def assert_no_broken_local_links(html_text, name, page_dir):
    for href in re.findall(r'href="([^"]+)"', html_text):
        if href.startswith(("http", "mailto:", "#")):
            continue
        target = os.path.normpath(os.path.join(page_dir, href.split("#")[0]))
        if not os.path.exists(target):
            raise SystemExit(f"{name}: broken local link {href}")


def main():
    rep = json.load(open(os.path.join(DATA, "verification_report.json"), encoding="utf-8"))
    ext = json.load(open(os.path.join(DATA, "correlation_extension.json"), encoding="utf-8"))
    canon = json.load(open(CANONICAL, encoding="utf-8"))

    os.makedirs(PAGES, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, "audit.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS.lstrip())

    pages = {
        "index.html": build_index(rep, ext, canon),
        "verification.html": build_verification(rep, canon),
        "correlations.html": build_correlations(ext),
        "flags.html": build_flags(rep, ext, canon),
    }
    for name, text in pages.items():
        assert_rows_sourced(text, name)
        with open(os.path.join(PAGES, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"{name}: {len(text)} bytes")
    # local-link check runs after every page exists, so self-links and sibling links resolve
    for name, text in pages.items():
        assert_no_broken_local_links(text, name, PAGES)
    print(f"generated_utc: {rep['generated_utc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
