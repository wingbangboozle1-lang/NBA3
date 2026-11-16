#!/usr/bin/env python3
"""Build the audit_ef6e2e6c site (session arena/ef6e2e6c-nba3, 2026-11-16 evening round).

Reads only the committed artefacts in data/rounds/2026-11-16-eve/ and writes static
HTML into audit_ef6e2e6c/. Every table row carries a link to its official source.
Run: python3 scripts/build_audit_ef6e2e6c.py
"""
from __future__ import annotations

import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "rounds" / "2026-11-16-eve"
OUT = ROOT / "audit_ef6e2e6c"

CSS = """
:root { --ink:#16202c; --mut:#5b6b7c; --line:#dfe6ee; --bg:#f5f7fa; --card:#fff;
        --ok:#137a3f; --warn:#a4560a; --bad:#b3261e; --accent:#1a5fb4; }
* { box-sizing: border-box; }
body { margin:0; font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
       color:var(--ink); background:var(--bg); }
header { background:var(--card); border-bottom:1px solid var(--line); padding:14px 22px; }
header a { color:var(--accent); text-decoration:none; margin-right:14px; font-weight:600; }
header a:hover { text-decoration:underline; }
main { max-width:1180px; margin:18px auto; padding:0 16px 48px; }
h1 { font-size:24px; margin:10px 0 4px; } h2 { font-size:18px; margin:26px 0 8px; }
.sub { color:var(--mut); margin-bottom:14px; }
.cards { display:flex; flex-wrap:wrap; gap:12px; margin:14px 0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:12px 16px; min-width:150px; }
.card b { display:block; font-size:22px; } .card span { color:var(--mut); font-size:13px; }
table { border-collapse:collapse; width:100%; background:var(--card);
        border:1px solid var(--line); border-radius:10px; overflow:hidden; font-size:13.5px; }
th,td { border-bottom:1px solid var(--line); padding:7px 9px; text-align:left;
        vertical-align:top; }
th { background:#eef2f7; font-weight:600; position:sticky; top:0; }
tr:last-child td { border-bottom:none; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
a { color:var(--accent); }
.tag { display:inline-block; padding:1px 7px; border-radius:99px; font-size:12px; font-weight:600; }
.t-out { background:#fdecea; color:var(--bad); } .t-doub { background:#fdecea; color:var(--bad); }
.t-q { background:#fff4e0; color:var(--warn); } .t-pro { background:#e8f4ff; color:var(--accent); }
.t-av { background:#e6f6ec; color:var(--ok); } .t-nus { background:#eceff3; color:var(--mut); }
.t-ok { background:#e6f6ec; color:var(--ok); } .t-flag { background:#fff4e0; color:var(--warn); }
.note { background:var(--card); border:1px solid var(--line); border-left:3px solid var(--accent);
        border-radius:8px; padding:10px 14px; margin:12px 0; font-size:14px; }
.note.warn { border-left-color:var(--warn); } .note.ok { border-left-color:var(--ok); }
.small { font-size:13px; color:var(--mut); }
footer { color:var(--mut); font-size:13px; padding:18px 22px; border-top:1px solid var(--line);
         background:var(--card); margin-top:30px; }
.wrap { overflow-x:auto; }
"""


def page(title: str, body: str, active: str) -> str:
    nav = [("index", "Overview", "index.html"), ("injuries", "Injuries 01:30 PM", "injuries.html"),
           ("delta.html", "Injury delta", "delta.html"), ("slate", "Slate 11/16-19", "slate.html"),
           ("results", "Results 11/15", "results.html"), ("flags", "Flagged", "flags.html"),
           ("sources", "Sources", "sources.html")]
    links = []
    for key, label, href in nav:
        style = ' style="font-weight:700;text-decoration:underline"' if key == active else ""
        links.append(f'<a href="{href}"{style}>{label}</a>')
    links = " ".join(links)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — NBA3 audit</title><style>{CSS}</style></head>
<body><header><a href="../index.html">NBA3 home</a>{links}</header>
<main>{body}</main>
<footer>Session <b>arena/ef6e2e6c-nba3</b> · 2026-11-16 evening round · every value below is
linked to an official NBA source; unverified values are blank and flagged, never inferred.</footer>
</body></html>
"""


def status_tag(s: str | None) -> str:
    if s is None:
        return '<span class="tag t-flag">blank</span>'
    cls = {"Out": "t-out", "Doubtful": "t-doub", "Questionable": "t-q",
           "Probable": "t-pro", "Available": "t-av"}.get(s, "t-nus")
    return f'<span class="tag {cls}">{html.escape(s)}</span>'


def write(name: str, title: str, body: str, active: str) -> None:
    (OUT / name).write_text(page(title, body, active), encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    inj = json.loads((DATA / "injuries_0130pm.json").read_text(encoding="utf-8"))
    delta = json.loads((DATA / "injury_delta.json").read_text(encoding="utf-8"))
    slate = json.loads((DATA / "slate_2026-11-16_19.json").read_text(encoding="utf-8"))
    res = json.loads((DATA / "results_2026-11-15.json").read_text(encoding="utf-8"))
    flags = json.loads((DATA / "flags.json").read_text(encoding="utf-8"))
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    rep = inj["source_url"]

    # ---------- index ----------
    body = f"""
<h1>2026-11-16 evening refresh — session arena/ef6e2e6c-nba3</h1>
<p class="sub">Official capture read 19:05–19:30 UTC · newest injury report 1:30 PM ET ·
slate window 11/16→11/19 · 11/15 game day now settled 9/9.</p>
<div class="cards">
 <div class="card"><b>{inj['count']}</b><span>injury rows (01:30 PM)</span></div>
 <div class="card"><b>{inj['player_rows']}</b><span>player rows</span></div>
 <div class="card"><b>{len(delta['status_changes'])}</b><span>status changes vs 09:15</span></div>
 <div class="card"><b>{slate['count']}</b><span>slate games (4 days)</span></div>
 <div class="card"><b>{res['settled_count']}/{res['count']}</b><span>11/15 finals settled</span></div>
 <div class="card"><b>{len(flags['flags'])}</b><span>flags raised</span></div>
</div>
<div class="note ok"><b>ATL@MIL settled.</b> The game day's last blocked game
(0022600243) is now verified from three official reads — the game page linescore, the gamebook
summary line and the gamebook team totals all give ATL 113 – MIL 106 with MIL quarters
37/16/<b>27</b>/26. The gamebook's own SCORE BY PERIOD cell (Q3=37, which sums to 116 against its
printed final of 106) is rejected as self-inconsistent and preserved as a flagged reading.
See <a href="results.html">Results</a>.</div>
<div class="note warn"><b>Scheduled refresh repair (E1).</b> Runs 43815576157 / 43864808752 failed
at the commit step (already repaired by session c449d46a) and run 43925193575 failed at the unit-test
step. The root cause was reproduced offline: tests coupled to the rolling
<code>official_slate_current.json</code>. Three test files were decoupled; the full 181-test suite
passes in a correct-order CI simulation. Live validation is the 23:15 UTC cron run after merge.
See flag EVE-F04.</div>
<h2>What this round captured</h2>
<table><tr><th>Artefact</th><th>Contents</th></tr>
<tr><td><a href="injuries.html">Injuries 01:30 PM</a></td>
<td>{inj['count']} rows transcribed cell-for-cell from the official PDF, parser validation PASS,
every row linked to the report</td></tr>
<tr><td><a href="delta.html">Injury delta</a></td>
<td>09:15 AM → 01:30 PM: {len(delta['status_changes'])} status changes,
{len(delta['reason_changes'])} reason change, {len(delta['newly_listed'])} newly listed,
{len(delta['delisted'])} delisted, {len(delta['nus_filed_since_base'])} teams filed</td></tr>
<tr><td><a href="slate.html">Slate 11/16–11/19</a></td>
<td>{slate['count']} games with official tips and records; 11/16–11/18 cross-checked
game-by-game against the committed verified slate (0 mismatches)</td></tr>
<tr><td><a href="results.html">Results 11/15</a></td>
<td>9 rows, {res['settled_count']} settled, including the ATL@MIL resolution with all readings kept</td></tr>
<tr><td><a href="flags.html">Flagged for review</a></td>
<td>{len(flags['flags'])} items with source links — none blocks the merge</td></tr>
<tr><td><a href="sources.html">Sources</a></td>
<td>{len(sources['sources'])} official reads with retrieval stamps</td></tr></table>
<h2>Scope boundaries</h2>
<p class="small">No 11/16 finals exist at capture time (first tip 7:00 PM ET) — nothing about
today's outcomes is published. No lines, picks, projections or performance claims are made here;
this is capture + verification only. Repo-wide decision pages:
<a href="../app/summary.html">executive summary</a> ·
<a href="../app/questions.html">open questions</a> ·
<a href="../app/suggestions.html">suggestions</a> ·
<a href="../app/flagged.html">repo flagged register</a>.</p>
"""
    write("index.html", "2026-11-16 evening refresh", body, "index")

    # ---------- injuries ----------
    rows_html = []
    for r in inj["rows"]:
        name = html.escape(r.get("player") or "—")
        note = ""
        if r.get("status_missing_note"):
            note = ' <span class="small">(status cell not printed — blank)</span>'
        if r.get("page_break_reason_cells"):
            note += f' <span class="small">(reason continues across page break: {" ".join(r["page_break_reason_cells"])})</span>'
        if r.get("carried"):
            note += f' <span class="small">(carried: {", ".join(r["carried"])})</span>'
        if r["kind"] == "NOT_YET_SUBMITTED":
            st = '<span class="tag t-nus">NOT YET SUBMITTED</span>'
        else:
            st = status_tag(r.get("status")) + note
        rows_html.append(
            f'<tr><td>{html.escape(r.get("date") or "")}</td>'
            f'<td>{html.escape(r.get("game_time") or "")}</td>'
            f'<td>{html.escape(r.get("matchup") or "")}</td>'
            f'<td>{html.escape(r.get("team") or "")}</td>'
            f'<td>{name}</td><td>{st}</td>'
            f'<td>{html.escape(r.get("reason") or "")}</td>'
            f'<td><a href="{rep}">report</a></td></tr>')
    body = f"""
<h1>Injury report — 11/16/26 01:30 PM ET</h1>
<p class="sub">Source: <a href="{rep}">official PDF</a> · index
<a href="{inj['index_url']}">official injury-report index</a> · retrieved 2026-11-16 19:05 UTC ·
transcribed cell for cell; parser validation
<b>{"PASS" if inj["validation"]["pass"] else "FAIL"}</b> ({inj['count']} rows).</p>
<div class="cards">
 <div class="card"><b>{inj['player_rows']}</b><span>player rows</span></div>
 <div class="card"><b>{inj['not_submitted_rows']}</b><span>NOT YET SUBMITTED</span></div>
 <div class="card"><b>{inj['rows_with_missing_status']}</b><span>status cell not printed</span></div>
 <div class="card"><b>{inj['rows_with_carried_cells']}</b><span>rows with carried cells</span></div>
</div>
<div class="note">Rows with <b>carried</b> markers had a cell dropped by a page break in the PDF;
the carried value comes from the row directly above in the same game block and is recorded, never
guessed. A blank status means the printed row has no status cell — it is not copied from an
earlier report.</div>
<div class="wrap"><table>
<tr><th>Date</th><th>Time</th><th>Matchup</th><th>Team</th><th>Player</th><th>Status</th><th>Reason</th><th>Source</th></tr>
{''.join(rows_html)}</table></div>
"""
    write("injuries.html", "Injuries 01:30 PM", body, "injuries")

    # ---------- delta ----------
    def dtable(head: str, cols: list[str], rows: list[dict], fmt) -> str:
        if not rows:
            return f"<h2>{head}</h2><p class='small'>None.</p>"
        tr = "".join("<tr>" + "".join(f"<td>{fmt(c, r)}</td>" for c in cols) + "</tr>" for r in rows)
        return (f"<h2>{head} ({len(rows)})</h2><div class='wrap'><table>"
                + "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>" + tr + "</table></div>")

    sc = dtable("Status changes", ["Team", "Player", "From", "To", "Reason", "Source"],
                delta["status_changes"],
                lambda c, r: {"Team": html.escape(r["team"]), "Player": html.escape(r["player"]),
                              "From": status_tag(r["from"]), "To": status_tag(r["to"]),
                              "Reason": html.escape(r.get("reason") or ""),
                              "Source": f'<a href="{delta["new"]["url"]}">01:30 PM</a>'}[c])
    rc = dtable("Reason changes (status unchanged)", ["Team", "Player", "Status", "09:15 reason", "01:30 reason", "Source"],
                delta["reason_changes"],
                lambda c, r: {"Team": html.escape(r["team"]), "Player": html.escape(r["player"]),
                              "Status": status_tag(r["status"]),
                              "09:15 reason": html.escape(r["from_reason"] or ""),
                              "01:30 reason": html.escape(r["to_reason"] or ""),
                              "Source": f'<a href="{delta["base"]["url"]}">09:15</a> → <a href="{delta["new"]["url"]}">01:30</a>'}[c])
    nl = dtable("Newly listed", ["Team", "Player", "Status", "Reason", "Source"],
                delta["newly_listed"],
                lambda c, r: {"Team": html.escape(r["team"]), "Player": html.escape(r["player"]),
                              "Status": status_tag(r["status"]), "Reason": html.escape(r["reason"]),
                              "Source": f'<a href="{delta["new"]["url"]}">01:30 PM</a>'}[c])
    dl = dtable("Delisted", ["Team", "Player", "Was status", "Source"],
                delta["delisted"],
                lambda c, r: {"Team": html.escape(r["team"]), "Player": html.escape(r["player"]),
                              "Was status": status_tag(r["was_status"]),
                              "Source": f'<a href="{delta["base"]["url"]}">09:15 AM</a>'}[c])
    nf = dtable("Teams that filed (were NOT YET SUBMITTED at 09:15)", ["Team", "Matchup", "Source"],
                delta["nus_filed_since_base"],
                lambda c, r: {"Team": html.escape(r["team_abbr"] or ""), "Matchup": html.escape(r["matchup"] or "(matchup not printed on base row)"),
                              "Source": f'<a href="{delta["new"]["url"]}">01:30 PM</a>'}[c])
    body = f"""
<h1>Injury delta — 09:15 AM → 01:30 PM ET (11/16)</h1>
<p class="sub">Base: <a href="{delta['base']['url']}">{delta['base']['report_stamp']}</a>
({delta['base']['player_rows']} player rows, session 8f4fac33) →
<a href="{delta['new']['url']}">{delta['new']['report_stamp']}</a>
({delta['new']['player_rows']} player rows). Keyed on (team, normalised name); a spelling change
between official prints shows as delisted + newly listed and is never silently merged.</p>
<div class="note warn"><b>Name-form flag:</b> Mathurin is printed “Bennedict” at 09:15 and
“Benedict” at 01:30 — see delisted/newly listed below and flag EVE-F03.</div>
{sc}{rc}{nl}{dl}{nf}
"""
    write("delta.html", "Injury delta", body, "delta.html")

    # ---------- slate ----------
    srows = "".join(
        f'<tr><td>{g["date"]}</td><td>{html.escape(g["time_et"])}</td>'
        f'<td>{g["away"]} @ {g["home"]}</td><td>{g["game_id"]}</td>'
        f'<td class="num">{g["away_record"]}</td><td class="num">{g["home_record"]}</td>'
        f'<td>{"committed slate ✓" if g["in_committed_verified_slate"] else "new to window"}</td>'
        f'<td><a href="{g["game_url"]}">game</a> · <a href="{g["source"]}">schedule</a></td></tr>'
        for g in slate["games"])
    body = f"""
<h1>Rolling slate — 11/16 → 11/19</h1>
<p class="sub">Source: <a href="{slate['source_url']}">official schedule listing</a> ·
retrieved {slate['retrieved_utc']} · {slate['count']} games
({', '.join(f'{d}: {n}' for d, n in slate['by_date'].items())}).</p>
<div class="note ok">Cross-check vs the committed verified slate
(<a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/official_slate_1115_1118.json">official_slate_1115_1118.json</a>):
{slate['cross_check_vs_committed']['overlap_rows']} overlapping rows,
<b>{len(slate['cross_check_vs_committed']['mismatches'])} mismatches</b>. Tips are as printed on the
official listing (ET); the scheduled promote leaves tips blank by design.</div>
<div class="wrap"><table>
<tr><th>Date</th><th>Tip (ET)</th><th>Matchup</th><th>Game id</th><th class="num">Away rec</th>
<th class="num">Home rec</th><th>Window note</th><th>Source</th></tr>{srows}</table></div>
"""
    write("slate.html", "Slate 11/16-19", body, "slate")

    # ---------- results ----------
    rrows = []
    for r in res["rows"]:
        aq = "/".join(str(x) for x in r["away_quarters"])
        hq = "/".join(str(x) for x in r["home_quarters"])
        qnote = ""
        if r["game_id"] == "0022600243":
            cr = r["conflict_resolution"]
            qnote = (f' <span class="small">(period-table reading {"/".join(str(x) for x in cr["period_table"])} '
                     f'rejected — self-inconsistent; see <a href="#atlmil">detail</a>)</span>')
        rrows.append(
            f'<tr><td>{r["date"]}</td><td>{r["away"]} @ {r["home"]}</td><td>{r["game_id"]}</td>'
            f'<td class="num"><b>{r["away_final"]}–{r["home_final"]}</b></td>'
            f'<td class="num">{aq}</td><td class="num">{hq}{qnote}</td>'
            f'<td><span class="tag {"t-ok" if r["settled"] else "t-flag"}">'
            f'{"settled" if r["settled"] else "open"}</span></td>'
            f'<td><a href="{r["game_url"]}">game page</a> · <a href="{r["gamebook"]}">gamebook</a></td></tr>')
    atl = next(r for r in res["rows"] if r["game_id"] == "0022600243")
    reads = "".join(
        f'<tr><td>{html.escape(rd["label"])}</td><td>{html.escape(rd["value"])}</td>'
        f'<td><a href="{rd["url"]}">open</a></td></tr>' for rd in atl["reads"])
    body = f"""
<h1>Results — 11/15 game day (settled {res['settled_count']}/{res['count']})</h1>
<p class="sub">Settlement rule: quarter sums must equal the printed final for both teams AND the
official game-page final must equal the gamebook final. Rows re-published from the
<a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/rounds/2026-11-16/results.json">round capture</a>
except ATL@MIL, resolved here.</p>
<div class="wrap"><table>
<tr><th>Date</th><th>Matchup</th><th>Game id</th><th class="num">Final</th>
<th class="num">Away quarters</th><th class="num">Home quarters</th><th>State</th><th>Source</th></tr>
{''.join(rrows)}</table></div>
<h2 id="atlmil">ATL @ MIL (0022600243) — resolution of the blocked row</h2>
<div class="note ok">Settled 2026-11-16T19:20Z by this session. Three official reads agree on
<b>ATL 113 – MIL 106</b> with MIL quarters 37/16/<b>27</b>/26 (sums to 106). The gamebook's
SCORE BY PERIOD table prints MIL Q3=37 (sums 116 against its own printed FINAL 106) — rejected as
self-inconsistent, preserved below. The AP recap on the official page corroborates 27:
55-53 at the half, 87-80 after three quarters.</div>
<div class="wrap"><table>
<tr><th>Read</th><th>Value as printed</th><th>Source</th></tr>{reads}</table></div>
<p class="small">Supersedes the blocked row in
<a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/rounds/2026-11-16/results.json">data/rounds/2026-11-16/results.json</a>
(round question Q09); both readings remain available in
<a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/rounds/2026-11-16-eve/results_2026-11-15.json">results_2026-11-15.json</a>.</p>
"""
    write("results.html", "Results 11/15", body, "results")

    # ---------- flags ----------
    flinks = []
    for f in flags["flags"]:
        srcs = " · ".join('<a href="%s">source</a>' % u for u in f["source_urls"])
        flinks.append(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td><b>%s</b><br><span class="small">%s</span></td><td>%s</td></tr>'
            % (f["id"], html.escape(f["severity"]), html.escape(f["status"]),
               html.escape(f["title"]), html.escape(f["detail"]), srcs))
    frows = "".join(flinks)
    body = f"""
<h1>Flagged for review — this round</h1>
<p class="sub">{len(flags["flags"])} items · none blocks the merge · every item links its source.
Repo-wide register: <a href="../app/flagged.html">app/flagged.html</a>.</p>
<div class="wrap"><table>
<tr><th>ID</th><th>Severity</th><th>Status</th><th>Item</th><th>Sources</th></tr>{frows}</table></div>
"""
    write("flags.html", "Flagged for review", body, "flags")

    # ---------- sources ----------
    srows2 = "".join(
        f'<tr><td>{s["id"]}</td><td>{html.escape(s["label"])}</td>'
        f'<td><a href="{s["url"]}">{html.escape(s["url"])}</a></td>'
        f'<td>{s["retrieved_utc"]}</td></tr>' for s in sources["sources"])
    body = f"""
<h1>Source register — 2026-11-16 evening round</h1>
<p class="sub">Every official read behind the pages on this site, with its retrieval stamp.</p>
<div class="wrap"><table>
<tr><th>ID</th><th>Label</th><th>URL</th><th>Retrieved (UTC)</th></tr>{srows2}</table></div>
<p class="small">Raw transcripts: <code>data/rounds/2026-11-16-eve/raw/</code>
(verbatim injury-report markdown + <a href="https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/rounds/2026-11-16-eve/raw/READS.md">READS.md</a>).</p>
"""
    write("sources.html", "Sources", body, "sources")
    print(f"wrote {len(list(OUT.glob('*.html')))} pages -> audit_ef6e2e6c/")


if __name__ == "__main__":
    main()
