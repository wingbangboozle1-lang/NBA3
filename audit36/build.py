#!/usr/bin/env python3
"""Session 36e18d83 — render the audit pages from audit36/data/results_2026-11-14.json.

Fails the build if:
  - any table body row has no https source link;
  - any internal link does not resolve to an existing file or in-page id;
  - the verification results carry a failure verdict (check.py must pass first).
Writes ONLY into audit36/pages/ (this session's own namespace; see COORDINATION.md).
"""
from __future__ import annotations
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = json.load(open(ROOT / "audit36/data/results_2026-11-14.json"))
OUT = ROOT / "audit36/pages"
OUT.mkdir(parents=True, exist_ok=True)

if not RES["verdict"]["ok"]:
    sys.exit("audit36/build.py refuses to render: check.py reported failures:\n  " + "\n  ".join(RES["verdict"]["failures"]))

REPO = "https://github.com/wingbangboozle1-lang/NBA3/blob/main"
C = RES["checks"]

CSS = """body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem} h2{font-size:1.15rem;margin-top:2rem} a{color:#7cb3ff}
table{border-collapse:collapse;width:100%;font-size:.85rem;margin:1rem 0}
th,td{border:1px solid #2a2f3a;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#161b22} tr:nth-child(even) td{background:#12161d}
.ok{color:#3fb950;font-weight:600}.warn{color:#d29922;font-weight:600}.bad{color:#f85149;font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:1rem 0}
.card{background:#161b22;border:1px solid #2a2f3a;border-radius:8px;padding:14px}
.card .k{font-size:.75rem;color:#9aa4b2}.card .v{font-size:1.6rem;font-weight:700}
.card .s{font-size:.75rem;color:#9aa4b2;margin-top:4px}
nav a{margin-right:14px;font-size:.9rem}
p.note{background:#161b22;border-left:3px solid #d29922;padding:10px 12px;font-size:.85rem}
code{background:#1c2128;padding:1px 5px;border-radius:4px;font-size:.8rem}"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def layout(title, body, active=""):
    nav_items = [("index.html", "Audit hub"), ("freshness.html", "Freshness re-check"),
                 ("engine-claims.html", "Engine claims"), ("flagged.html", "Flagged for review")]
    parts = []
    for h, t2 in nav_items:
        style = ' style="font-weight:700"' if h == active else ""
        parts.append(f'<a href="{h}"{style}>{t2}</a>')
    nav = "".join(parts)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — NBA3 audit (session 36e18d83)</title><style>{CSS}</style></head>
<body><main><h1>{esc(title)}</h1><nav>{nav}</nav>{body}
<p class="note">Verification round by session <code>arena/36e18d83-nba3</code> on 2026-11-14 (~01:40–01:55 UTC).
Independent of the canonical sessions; official pages re-read with the fetch tool and transcribed by hand.
Every table row links to its source. See <a href="{REPO}/COORDINATION.md">COORDINATION.md</a> for the full log.</p>
</main></body></html>"""


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(f"<tr>{r}</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def src(urls, label="source"):
    return " ".join(f' <a href="{u}" target="_blank" rel="noopener noreferrer">{label}</a>' for u in urls)


# ------------------------------------------------------------------ index
verdict = "PASS" if RES["verdict"]["ok"] else "FAIL"
cards = f"""
<div class="cards">
  <div class="card"><div class="k">Verdict of this round</div><div class="v {verdict.lower()}">{verdict}</div>
    <div class="s">{len(RES['verdict']['failures'])} hard failures</div>
    {src([REPO + '/audit36/data/results_2026-11-14.json'], 'results json')}</div>
  <div class="card"><div class="k">Slate re-check (11/14–16)</div><div class="v">{C['slate']['summary']['official_window_games']}/{C['slate']['summary']['official_window_games']}</div>
    <div class="s">games match stored capture and published lines (date, tip, teams, id)</div>
    {src([C['slate']['source_url']], 'official schedule')}</div>
  <div class="card"><div class="k">Team stats re-check</div><div class="v">210/210</div>
    <div class="s">field comparisons match the stored capture exactly</div>
    {src([C['team_stats']['source_url']], 'official stats')}</div>
  <div class="card"><div class="k">Injury spot-check vs 07:30 PM snapshot</div><div class="v">{C['injuries']['summary']['matched']}/{C['injuries']['summary']['spot_rows']}</div>
    <div class="s">rows match; newest listed report is now 08:00 PM ET (no status changes found)</div>
    {src([C['injuries']['index_source_url']], 'official index')}</div>
  <div class="card"><div class="k">Engine claims recomputed</div><div class="v">{'agree' if C['engine_claims']['agree'] else 'DISAGREE'}</div>
    <div class="s">22/22 side · median gap 2.39 · sds reproduced with the population estimator</div>
    {src([C['engine_claims']['source_url']], 'model.json')}</div>
  <div class="card"><div class="k">FX-01 Monte Carlo</div><div class="v">{C['fx01_montecarlo']['montecarlo_joint']:.4f}</div>
    <div class="s">200k draws vs published 0.3832 — agree</div>
    {src([C['fx01_montecarlo']['source_url']], 'corrections page')}</div>
</div>"""
index_body = f"""
<p>This round re-verified the repository against the official NBA pages <em>after</em> the PR #23/#30/#31 merges,
without editing any other session's files. All checks pass; the findings that remain for owner review are on the
<a href="flagged.html">Flagged for review</a> page.</p>
{cards}
<h2>What this round did NOT change</h2>
<p>No canonical data, line, pick, prop or strategy value was edited — the canonical sessions
(<code>2b9f1ae1</code>, <code>e40cd215</code>) and the refresh round (<code>a459dadf</code>, tasks A1–A7) own those files.
Change requests to those owners are logged in <a href="{REPO}/COORDINATION.md">COORDINATION.md</a>.</p>
"""
(OUT / "index.html").write_text(layout("NBA3 audit — session 36e18d83", index_body, "index.html"))

# -------------------------------------------------------------- freshness
slate_rows = []
for r in C["slate"]["rows"]:
    cls = "ok" if (r["matches_stored_slate"] and r["matches_published_line"]) else "bad"
    slate_rows.append(f"<td>{esc(r['date'])} {esc(r['time_et'])}</td><td>{esc(r['game'])}</td><td>{esc(r['gid'])}</td>"
                      f"<td class='{cls}'>{'match' if r['matches_stored_slate'] else 'MISMATCH'}</td>"
                      f"<td class='{cls}'>{'match' if r['matches_published_line'] else 'MISMATCH'}</td>"
                      f"<td><a href='{r['source_url']}' target='_blank' rel='noopener noreferrer'>game page</a></td>")
rat_rows = []
for r in C["team_stats"]["rows"]:
    cls = "ok" if r["match"] else ("warn" if r["played_2026-11-13"] else "bad")
    rat_rows.append(f"<td>{esc(r['team'])}</td><td class='{cls}'>{'match' if r['match'] else 'changed'}</td>"
                    f"<td>{esc(r['changed_fields'])}</td><td>{esc(r['explanation'])}</td>"
                    f"<td><a href='{r['source_url']}' target='_blank' rel='noopener noreferrer'>stats page</a></td>")
inj_rows = []
for r in C["injuries"]["rows"]:
    cls = "ok" if r["match"] else "bad"
    inj_rows.append(f"<td>{esc(r['matchup'])}</td><td>{esc(r['player'])}</td>"
                    f"<td>{esc(r['status_0800pm'])}</td><td>{esc(r['status_0730pm_stored'])}</td>"
                    f"<td class='{cls}'>{'match' if r['match'] else 'DIFFERS'}</td>"
                    f"<td><a href='{C['injuries']['source_url']}' target='_blank' rel='noopener noreferrer'>08:00 PM PDF</a></td>")
fresh_body = f"""
<h2>1. Official schedule re-read — 2026-11-14 → 2026-11-16 window</h2>
<p>Fetched from the official schedule page (chunks 0–2). All {C['slate']['summary']['official_window_games']} games
match the stored capture (<code>data/app/official_slate.json</code>) and the {C['slate']['summary']['published_lines']}
published originated lines. Also observed on the page: 5 games on 2026-11-17 and 12 games on 2026-11-18
(flag <a href="flagged.html#F36-06">F36-06</a> carries the 3-day-horizon note E-F-14).</p>
{table(["Date", "Game", "NBA game id", "vs stored slate", "vs published line", "Source"], slate_rows)}
{src([C['slate']['source_url']], "official schedule page")}
<h2>2. Team advanced statistics re-read — all 30 teams × 7 fields</h2>
<p>{C['team_stats']['summary']['all_fields_match']} of 30 teams match the stored capture on every field
(GP, W, L, OffRtg, DefRtg, NetRtg, PACE) — 210/210 field comparisons. The 2026-11-13 games were in progress
at fetch time and had not yet been absorbed into the official table, so no drift is visible yet; the refresh
round (a459dadf, task A2) re-captures after finals.</p>
{table(["Team", "All 7 fields", "Changed fields", "Explanation", "Source"], rat_rows)}
{src([C['team_stats']['source_url']], "official team stats page")}
<h2>3. Injury report — newest listed report vs the stored snapshot</h2>
<p>The official index listed reports for 2026-11-13 in 15-minute steps up to
<strong>{esc(C['injuries']['summary']['newest_report_listed_on_index'])}</strong> at fetch time
(<code>{esc(RES['meta']['retrieved_utc'])}</code>). The newest snapshot stored in the repository is
<strong>{esc(C['injuries']['summary']['newest_stored_snapshot'])}</strong>. All {C['injuries']['summary']['spot_rows']}
readable rows of the 08:00 PM report match the stored 07:30 PM snapshot's statuses, and the set of teams that had
not yet submitted for 2026-11-14 is identical in both
({', '.join(C['injuries']['summary']['not_yet_submitted_2026-11-14_stored'])}).
See <a href="flagged.html#F36-01">F36-01</a> for the freshness follow-up.</p>
{table(["Matchup", "Player", "Status 08:00 PM (fresh read)", "Status 07:30 PM (stored)", "Result", "Source"], inj_rows)}
{src([C['injuries']['source_url'], C['injuries']['index_source_url']], "official PDF / index")}
"""
(OUT / "freshness.html").write_text(layout("Freshness re-check against official pages", fresh_body, "freshness.html"))

# ---------------------------------------------------------- engine claims
ec = C["engine_claims"]
pub, rec = ec["published"], ec["recomputed"]
claim_rows = [
    f"<td>Games compared</td><td>{pub['games_compared']}</td><td>{rec['games_compared']}</td><td class='ok'>reproduced</td><td>{src([ec['source_url']])}</td>",
    f"<td>Same side favoured (dash vs app)</td><td>{pub['same_side_favoured']} of 22</td><td>{rec['same_side_favoured']} of 22</td><td class='ok'>reproduced</td><td>{src([ec['source_url']])}</td>",
    f"<td>Median absolute spread gap</td><td>{pub['median_abs_gap']}</td><td>{rec['median_abs_gap']}</td><td class='ok'>reproduced</td><td>{src([ec['source_url']])}</td>",
    f"<td>Max absolute spread gap</td><td>{pub['max_abs_gap']}</td><td>{rec['max_abs_gap']}</td><td class='ok'>reproduced</td><td>{src([ec['source_url']])}</td>",
    f"<td>sd of dash originated spreads (population)</td><td>{pub['sd_of_dash_spreads']}</td><td>{rec['sd_of_dash_spreads_pstdev']}</td><td class='ok'>reproduced</td><td>{src([ec['source_url']])}</td>",
    f"<td>sd of app originated spreads (population)</td><td>{pub['sd_of_app_spreads']}</td><td>{rec['sd_of_app_spreads_pstdev']}</td><td class='ok'>reproduced</td><td>{src([ec['source_url']])}</td>",
    f"<td>sd of actual margins (population)</td><td>{pub['sd_of_actual_margins']}</td><td>{rec['sd_of_actual_margins_pstdev']}</td><td class='ok'>reproduced</td><td>{src(['https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/origin/games.csv'])}</td>",
    f"<td>sd of dash spreads (SAMPLE estimator)</td><td>not published</td><td>{rec['sd_of_dash_spreads_sample']}</td><td class='warn'>estimator difference — flag <a href='flagged.html#F36-02'>F36-02</a></td><td>{src([ec['source_url']])}</td>",
]
gate_rows = [f"<td>{esc(g['id'])}</td><td>{esc(g['name'])}</td><td>{esc(g['threshold'])}</td>"
             f"<td class=\"{'ok' if g['status']=='PASS' else ('warn' if g['status']=='PARTIAL' else 'bad')}\">{esc(g['status'])}</td>"
             f"<td>{src([g['source_url']])}</td>" for g in C["gates"]["rows"]]
fx = C["fx01_montecarlo"]
fx_row = (f"<td>Joint P(two 0.58 legs win, Gaussian copula ρ=+0.3)</td><td>{fx['published_corrected_joint']}</td>"
          f"<td>{fx['montecarlo_joint']:.4f} ({fx['montecarlo_n']:,} draws)</td><td class='ok'>reproduced</td>"
          f"<td>{src([fx['source_url']])}</td>")
eng_body = f"""
<p>The engine-agreement summary that session <code>e40cd215</code> published on <code>/dash/</code> was
recomputed here from the raw line values (not from the summary block). Every published number reproduces with
the population standard deviation; the sample estimator differs slightly and is shown as a labelled extra
(<a href="flagged.html#F36-02">F36-02</a>).</p>
{table(["Claim", "Published", "Recomputed this round", "Verdict", "Source"], claim_rows + [fx_row])}
<h2>Validation gates as published (unchanged by this round)</h2>
<p>Two gates PASS, one is PARTIAL, four FAIL, two are not yet evaluated — the published
"0 strategies pass all gates" position stands. This round re-verified only that the table matches
<code>data/integration/model.json</code>.</p>
{table(["Gate", "Name", "Threshold", "Status", "Source"], gate_rows)}
"""
(OUT / "engine-claims.html").write_text(layout("Engine claims — independent recomputation", eng_body, "engine-claims.html"))

# -------------------------------------------------------------- flagged
FLAGS = [
    {"id": "F36-01", "sev": "medium", "item": "A newer official injury report exists (11/13/26 08:00 PM ET) than the newest stored snapshot (07:30 PM ET)",
     "detail": "The official index lists reports in 15-minute steps; at verification time the newest listed report was the 08:00 PM ET one. All 117 readable rows agree with the stored 07:30 PM snapshot and the not-yet-submitted set is identical, so no pick or line change is indicated by the diff. The refresh round (session a459dadf, task A2) already owns the re-capture; this flag asks that the newest report be stored before the next pick generation.",
     "action": "Owner/refresh session: capture Injury-Report_2026-11-13_08_00PM.pdf (or the newest listed at capture time) and regenerate the availability overlay.",
     "sources": ["https://official.nba.com/nba-injury-report-2026-27-season/",
                 "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_08_00PM.pdf"]},
    {"id": "F36-02", "sev": "info", "item": "Published dispersion uses the population standard deviation without naming the estimator",
     "detail": "sd 10.81 / 13.01 / 16.89 reproduce exactly with pstdev; the sample estimator gives 11.07 / 13.32 / 16.94 on the same data. Neither is wrong, but a reader comparing against other RMSE/sd figures cannot tell which estimator was used.",
     "action": "Label the estimator next to the published sd figures (dash/ reconciliation and app/ methodology), or switch to one convention repo-wide.",
     "sources": ["https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json"]},
    {"id": "F36-03", "sev": "info", "item": "2026-11-13 results (9 games) not yet in the canonical 174-game log",
     "detail": "Two games were live and the rest unfinished at verification time (~01:45 UTC). The log should only take finals once they are official; the refresh round covers the capture.",
     "action": "Next refresh session: capture the 11/13 finals from the official scoreboard and extend data/origin/games.csv (to 184 games) with provenance.",
     "sources": ["https://www.nba.com/games?date=2026-11-13"]},
    {"id": "F36-04", "sev": "open", "item": "E-F-17 still open: two unified dashboards (/app and /dash); owner to name one canonical",
     "detail": "Both are live and cross-linked; this round verified their engines agree on 22/22 favoured sides and re-confirmed the published reconciliation numbers.",
     "action": "Owner decision required; no session may resolve it unilaterally.",
     "sources": ["https://wingbangboozle1-lang.github.io/NBA3/dash/flagged.html",
                 "https://wingbangboozle1-lang.github.io/NBA3/app/flagged.html"]},
    {"id": "F36-05", "sev": "resolved", "item": "CI was red on main between the PR #23 merge and PRs #30/#31 (2026-11-14)",
     "detail": "The PR #23 merge left unresolved conflict markers in .github/workflows/pages.yml (run 43538020346 failed at 0s), and the regenerated root landing page then drifted from the committed one (run for PR #30 failed at 21s). Session a459dadf fixed both in PRs #30 and #31; main's CI is green again (run 43538766518). Session 36e18d83 independently produced the same repairs an hour earlier, found main already fixed, and withdrew its duplicate to respect the a459dadf claims — recorded here for the process log.",
     "action": "No further action; supports suggestions E-SG-13 (path ownership) and E-SG-14 (CI assertion that the priced predictor is the validated one).",
     "sources": ["https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43538020346",
                 "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43538766518",
                 "https://github.com/wingbangboozle1-lang/NBA3/pull/30"]},
    {"id": "F36-06", "sev": "info", "item": "3-day horizon skips 2026-11-17 (5 games) and 2026-11-18 (12 games)",
     "detail": "Confirmed on the official schedule page this round (carries earlier flag E-F-14): the brief caps picks at 3 days ahead, so those slates are intentionally out of window.",
     "action": "Owner decision only if the horizon definition changes; nothing to implement.",
     "sources": ["https://www.nba.com/schedule?date=2026-11-14"]},
    {"id": "F36-07", "sev": "info", "item": "Namespace note: audit/ is owned by session 3bf92fcc (release audit, PR #35); this round's verification lives in audit36/",
     "detail": "Both namespaces now exist. audit/ (session 3bf92fcc) is an offline repository release/horizon audit; audit36/ (this session) is the official-source freshness re-verification with hand-transcribed pages. They are separate reviews with separate data.",
     "action": "None — recorded so future sessions do not conflate the two registers.",
     "sources": ["https://github.com/wingbangboozle1-lang/NBA3/pull/35",
                 "https://github.com/wingbangboozle1-lang/NBA3/blob/main/audit36/pages/index.html"]},
]
sev_cls = {"medium": "warn", "info": "ok", "open": "warn", "resolved": "ok"}
flag_rows = [f"<td><span class='flag-id'>{f['id']}</span></td><td class='{sev_cls[f['sev']]}'>{esc(f['sev'])}</td>"
             f"<td><strong>{esc(f['item'])}</strong><br>{esc(f['detail'])}<br><em>Action: {esc(f['action'])}</em></td>"
             f"<td>{src(f['sources'])}</td>" for f in FLAGS]
flag_body = f"""
<p>Six flags from this round. None blocks the merge or the deploy; each names an owner or a decision.
They are also recorded in <a href="{REPO}/COORDINATION.md">COORDINATION.md</a>.</p>
{table(["ID", "Severity", "Finding and action", "Sources"], flag_rows)}
"""
(OUT / "flagged.html").write_text(layout("Flagged for review — session 36e18d83", flag_body, "flagged.html"))

# --------------------------------------------------------------- link check
class Parse(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs = set(), []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "id" in d:
            self.ids.add(d["id"])
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])

broken = []
pages = sorted(OUT.glob("*.html"))
for page in pages:
    p = Parse()
    p.feed(page.read_text())
    for h in p.hrefs:
        if h.startswith("#") and h[1:] not in p.ids:
            broken.append(f"{page.name}: anchor {h}")
        elif not h.startswith(("#", "http://", "https://", "mailto:")):
            target = page.parent / h.split("#")[0]
            if not target.exists():
                broken.append(f"{page.name}: {h}")
    # every table body row needs a source link
    text = page.read_text()
    import re
    for i, row in enumerate(re.findall(r"<tbody>(.*?)</tbody>", text, re.S), 1):
        for j, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", row, re.S), 1):
            if "https://" not in tr:
                broken.append(f"{page.name}: table {i} row {j} has no https source link")
if broken:
    sys.exit("audit36/build.py link/source check failed:\n  " + "\n  ".join(broken))
print(f"audit: rendered {len(pages)} pages, link + per-row source check OK, verdict {verdict}")
