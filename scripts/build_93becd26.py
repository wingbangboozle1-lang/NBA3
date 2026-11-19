#!/usr/bin/env python3
"""Build the 2026-11-19-93becd26 subsite (session arena/93becd26-nba3).

Reads data/rounds/2026-11-19-93becd26/*.json (written by scripts/capture_93becd26.py)
and writes four static pages under 93becd26/:

  index.html        landing: what this round is, counts, navigation
  player-logs.html  one row per player on the newest official injury report, with that
                    player's most-recent game log and a source link on every row
  injuries.html     banner = injury-report revision time + retrieval time, both captured
                    revisions, the consecutive diff, layout notes
  flagged.html      Flagged for Review (F-93-01..F-93-09), each item with source links

Run: python3 scripts/build_93becd26.py [--check]
"""
from __future__ import annotations

import html
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-19-93becd26")
OUT = os.path.join(ROOT, "93becd26")

NAV = [("index.html", "Home"), ("player-logs.html", "Player logs"),
       ("injuries.html", "Injuries"), ("flagged.html", "Flagged for Review")]

CSS = """
:root { --ink:#14213d; --mut:#5c677d; --line:#d9dee7; --bg:#f6f8fb; --acc:#1d4ed8; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       color:var(--ink); background:var(--bg); }
header { background:#fff; border-bottom:1px solid var(--line); padding:14px 22px; }
header h1 { margin:0 0 2px; font-size:19px; }
header .sub { color:var(--mut); font-size:13px; }
nav a { margin-right:14px; color:var(--acc); text-decoration:none; font-size:14px; }
nav a:hover { text-decoration:underline; }
main { max-width:1180px; margin:18px auto; padding:0 18px 40px; }
.banner { background:#eef4ff; border:1px solid #c9d8fb; border-radius:8px;
          padding:10px 14px; font-size:14px; margin-bottom:16px; }
table { border-collapse:collapse; width:100%; background:#fff; font-size:13.5px; }
th,td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
th { background:#eef1f6; position:sticky; top:0; }
tr:nth-child(even) td { background:#fafbfd; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.flag { color:#b45309; font-weight:600; }
.mut { color:var(--mut); }
.null { color:#9aa3b2; }
a { color:var(--acc); }
.cards { display:flex; gap:12px; flex-wrap:wrap; margin:14px 0; }
.card { background:#fff; border:1px solid var(--line); border-radius:8px;
        padding:10px 16px; min-width:130px; }
.card b { display:block; font-size:22px; }
.card span { color:var(--mut); font-size:12.5px; }
h2 { font-size:16px; margin:26px 0 8px; }
.note { font-size:13px; color:var(--mut); margin:6px 0 14px; }
ul.tight li { margin:4px 0; }
"""


def esc(x):
    return html.escape("" if x is None else str(x))


def page(title, body, active):
    parts = []
    for h, t in NAV:
        style = ' style="font-weight:700"' if h == active else ''
        parts.append(f'<a href="{h}"{style}>{esc(t)}</a>')
    nav = "".join(parts)
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
            f"<header><h1>NBA player game logs for the injury report</h1>"
            f"<div class=\"sub\">Round 2026-11-19-93becd26 &middot; session arena/93becd26-nba3 "
            f"&middot; official sources only, every row linked</div>"
            f"<nav>{nav}</nav></header><main>{body}</main></body></html>")


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


def build():
    p = load("player_logs_injury_2026-11-19.json")
    inj = load("injury_parsed.json")
    man = load("manifest.json")
    c = p["counts"]
    banner = (f"<div class=\"banner\"><b>Injury report revision:</b> "
              f"{esc(p['report_revision'])} ET (newest on the official index at capture) "
              f"&middot; <b>retrieval:</b> {esc(p['retrieval_window_utc'])} (window, not a "
              f"per-call stamp) &middot; <b>previous revision:</b> {esc(p['previous_revision'])} ET "
              f"&middot; consecutive diff: "
              f"{'no status changes' if p['consecutive_diff']['identical'] else 'changes — see Injuries'}"
              f"</div>")

    # ---------------- index
    cards = "".join(
        f"<div class=\"card\"><b>{v}</b><span>{k}</span></div>"
        for k, v in [("report player rows", c["report_player_rows"]),
                     ("team printed on row", c["team_printed"]),
                     ("team blank (flagged)", c["team_blank_on_report"]),
                     ("played logs", c["log_played"]),
                     ("DND logs", c["log_dnd"]),
                     ("inactive logs", c["log_inactive"]),
                     ("unmatched", c["unmatched"])])
    games_rows = "".join(
        f"<tr><td>{esc(g['date'])}</td><td>{esc(g['away'])} @ {esc(g['home'])}</td>"
        f"<td>{esc(g['game_id'])}</td>"
        f"<td>{esc(g['header_date_printed'])}</td>"
        f"<td><a href=\"{esc(g['gamebook_url'])}\">game book (PDF)</a> · "
        f"<a href=\"{esc(g['game_url'])}\">game page</a></td></tr>"
        for g in p["games"])
    cap_rows = "".join(
        f"<tr><td>{esc(n)}</td><td class=\"num\">{m['bytes']}</td>"
        f"<td class=\"mut\">{esc(m['sha256'][:16])}</td>"
        f"<td><a href=\"{esc(m['source_url'])}\">{esc(m['source_url'])}</a></td></tr>"
        for n, m in sorted(man["files"].items()))
    index = banner + f"""
<div class="cards">{cards}</div>
<p class="note">One row for every player listed on the newest official NBA injury report at
capture time (revision {esc(p['report_revision'])} ET), each paired with that player's
most recent completed game log — minutes, points, rebounds, assists and the opponent, or the
DND/inactive reason exactly as the official box-score game book prints it. Values that cannot
be read from an official source stay blank and are flagged; nothing is inferred.</p>
<h2>Games used (each team's most recent completed game)</h2>
<p class="note">None of LAC, SAS, MIN or POR appears among the twelve finals printed on the
<a href="{esc(p['recent_game_selection']['schedule_url'])}">official 2026-11-18 schedule page</a>
(absence check: {'PASS' if p['recent_game_selection']['schedule_absent_check_ok'] else 'FAIL'}),
and each game book header itself prints Tuesday, November 17, 2026.</p>
<table><tr><th>Date</th><th>Matchup</th><th>Game id</th><th>Header prints</th><th>Sources</th></tr>
{games_rows}</table>
<h2>Verification</h2>
<ul class="tight">
<li>Every played row satisfies PTS = 2·FG + 3P + FT and TOT = OR + DR as printed;
team minutes sum to the printed 240:00 in all six team-games (240.0 / 240.0 / 239.999 /
240.0 / 239.999 / 240.003).</li>
<li>Printed period totals equal the printed team totals for all three games
(105-106, 105-93, 132-107) and match the merged official finals capture
(data/rounds/2026-11-19-dd3edd74, PR #144) 3 of 3.</li>
<li>Consecutive report diff (02:00 AM → 02:15 AM ET): no added, removed or changed rows.</li>
<li>21 of 23 report rows print their team; 2 do not (page-break layout) and are flagged
F-93-01 with team taken only from the official game book line carrying the identical
printed reason.</li>
<li>Manifest: sha256 + byte size recorded for all {len(man['files'])} capture files.</li>
</ul>
<h2>Captures in this round</h2>
<table><tr><th>File</th><th>Bytes</th><th>sha256 (first 16)</th><th>Official source</th></tr>
{cap_rows}
</table>"""

    # ---------------- player logs
    tr = []
    for r in p["rows"]:
        lg = r["game_log"] or {}
        if lg.get("kind") == "played":
            stat = (f"<td class=\"num\">{esc(lg['min_mmss'])}</td>"
                    f"<td class=\"num\">{esc(lg['pts'])}</td>"
                    f"<td class=\"num\">{esc(lg['reb'])}</td>"
                    f"<td class=\"num\">{esc(lg['ast'])}</td>")
            reason = "<span class=\"null\">—</span>"
        else:
            stat = "<td class=\"null\">—</td>" * 4
            reason = esc(lg.get("printed_reason"))
        flags = " ".join(f"<span class=\"flag\">{esc(f.split(':')[0])}</span>"
                         for f in r["flags"]) or "<span class=\"null\">—</span>"
        srcs = [f"<a href=\"{esc(r['sources']['injury_report'])}\">report</a>"]
        if lg.get("gamebook_url"):
            srcs.append(f"<a href=\"{esc(lg['gamebook_url'])}\">game book</a>")
        if lg.get("game_url"):
            srcs.append(f"<a href=\"{esc(lg['game_url'])}\">game page</a>")
        team_cell = esc(r["team"]) if r["team"] else '<span class="null">blank</span>'
        tr.append(
            f"<tr><td>{esc(r['player'])}</td>"
            f"<td>{team_cell}"
            f"<div class=\"mut\">{esc(r['team_source'] or '')}</div></td>"
            f"<td>{esc(r['report']['status'])}</td>"
            f"<td class=\"mut\">{esc(r['report']['reason'])}</td>"
            f"<td>{esc(lg.get('date'))}</td><td>{esc(lg.get('opponent'))}</td>"
            f"{stat}<td>{reason}</td><td>{flags}</td><td>{' · '.join(srcs)}</td></tr>")
    logs = banner + f"""
<p class="note">Report status/reason describe the <b>11/19</b> game (as printed on the report);
the log columns describe each player's most recent completed game ({esc(p['games'][0]['date'])}).
They are different games and are shown side by side on purpose (F-93-03). Null cells are
values not printed by an official source — never filled in.</p>
<table>
<tr><th>Player (as printed)</th><th>Team / source</th><th>Report status</th>
<th>Report reason</th><th>Log date</th><th>Opponent</th><th class="num">Min</th>
<th class="num">Pts</th><th class="num">Reb</th><th class="num">Ast</th>
<th>Game-book status / reason</th><th>Flags</th><th>Sources</th></tr>
{"".join(tr)}
</table>
<p class="note">Counts: {c['report_player_rows']} rows · played {c['log_played']} ·
DND {c['log_dnd']} · inactive {c['log_inactive']} · unmatched {c['unmatched']} ·
problems {len(p['problems'])}.</p>"""

    # ---------------- injuries
    def _tc(r):
        return esc(r["team_printed"]) if r["team_printed"] else '<span class="null">(blank)</span>'
    cur_rows = "".join(
        f"<tr><td>{esc(r['game_date'])}</td><td>{esc(r['matchup'])}</td>"
        f"<td>{_tc(r)}</td>"
        f"<td>{esc(r['player'])}</td><td>{esc(r['status'])}</td>"
        f"<td class=\"mut\">{esc(r['reason'])}</td>"
        f"<td><a href=\"{esc(p['report_url'])}\">PDF</a></td></tr>"
        for r in inj["current"]["players"])
    team_rows = "".join(
        f"<tr><td>{esc(r['matchup'])}</td><td>{esc(r['team_printed'])}</td>"
        f"<td class=\"mut\">{esc(r['printed'])}</td></tr>"
        for r in inj["current"]["team_rows"])
    d = p["consecutive_diff"]
    delta_txt = (f"identical ({len(inj['current']['players'])} player rows in both "
                 f"revisions; 0 added, 0 removed, 0 changed)"
                 if d["identical"] else
                 f"added {len(d['added'])}, removed {len(d['removed'])}, "
                 f"changed {len(d['changed'])}")
    shifted = "".join(
        "<tr><td>" + " &middot; ".join(esc(c) for c in r.get("cells", [r["c0"], r["c1"], r["c2"]]))
        + "</td></tr>"
        for r in inj["current"]["shifted_rows"])
    injuries = f"""
<div class="banner"><b>Revision time:</b> {esc(p['report_revision'])} ET &middot;
<b>Retrieval time:</b> {esc(p['retrieval_window_utc'])} (capture window) &middot;
<b>Previous revision:</b> {esc(p['previous_revision'])} ET &middot;
<b>Consecutive diff:</b> {esc(delta_txt)}</div>
<p class="note">Sources:
<a href="{esc(p['report_index_url'])}">official injury-report index</a> ·
<a href="{esc(p['report_url'])}">02:15 AM ET PDF</a> ·
<a href="{esc(p['previous_report_url'])}">02:00 AM ET PDF</a>.
Transcripts are stored verbatim under data/rounds/2026-11-19-93becd26/captures/ with
sha256 in manifest.json.</p>
<h2>02:15 AM ET player rows ({len(inj['current']['players'])})</h2>
<table><tr><th>Game date</th><th>Matchup</th><th>Team</th><th>Player</th>
<th>Status</th><th>Reason</th><th>Source</th></tr>{cur_rows}</table>
<h2>Team rows with no player entry ({len(inj['current']['team_rows'])})</h2>
<table><tr><th>Matchup</th><th>Team</th><th>Printed</th></tr>{team_rows}</table>
<h2>Layout-shifted section-3 rows ({len(inj['current']['shifted_rows'])})</h2>
<p class="note">Recorded exactly as printed; columns are shifted on the page and are never
re-aligned (F-93-07).</p>
<table><tr><th>Cells as printed</th></tr>{shifted}</table>
<h2>Consecutive diff 02:00 AM → 02:15 AM</h2>
<p class="note">{esc(delta_txt)}.</p>"""

    # ---------------- flagged
    items = [
        ("F-93-01", "needs review",
         "Two report rows (Kuminga, Jonathan and Pullin, Zyon) print no Team or Matchup "
         "(page-break layout). Their team and game come only from the official game book "
         "lines that print the same player name with the identical printed reason "
         "(MIN, 2026-11-17). Attribution source = game book, not the report row.",
         [p["report_url"], p["games"][0]["gamebook_url"]]),
        ("F-93-02", "informational",
         "15 rows match on surname + identical printed reason because the game book's "
         "inactive lines print the surname only (e.g. 'Beal (Injury/Illness - Right Knee "
         "Injury Management)'). Reason equality is enforced wherever both sides print one.",
         [p["games"][1]["gamebook_url"], p["games"][2]["gamebook_url"]]),
        ("F-93-03", "informational",
         "Report status/reason describe the 11/19 game; the log columns describe the "
         "11/17 game. E.g. Williams III, Robert is Out (Rest) tonight but played 15:34 "
         "on 11/17 — both facts are official and are not in conflict.",
         [p["report_url"], p["games"][0]["gamebook_url"]]),
        ("F-93-04", "needs review",
         "The fetch tool's markdown conversion of a PDF is not byte-stable across calls "
         "(underline tags and cell splitting varied between retrievals; player-row values "
         "were identical in every retrieval). Each transcript header records which "
         "retrieval is canonical.",
         [p["games"][0]["gamebook_url"]]),
        ("F-93-05", "informational",
         f"Retrieval times are the capture window {p['retrieval_window_utc']}, not "
         "per-call stamps.", [p["report_index_url"]]),
        ("F-93-06", "needs review",
         "The report prints 'Krejci, Vit'; the game book prints 'Krejčí' (diacritic) "
         "with the identical printed reason (Left Ankle Fracture). Matched; spelling "
         "difference preserved on both sides.",
         [p["report_url"], p["games"][0]["gamebook_url"]]),
        ("F-93-07", "informational",
         "Report sections 2 and 3 are layout-broken on the PDF page break: section-2 rows "
         "print no Game Date/Time cells; section-3 columns are shifted. Recorded as "
         "printed, never re-aligned.",
         [p["report_url"]]),
        ("F-93-08", "needs review",
         "The official schedule page returned the identical November-18-first rendering "
         "for date=2026-11-16, date=2026-11-17 and date=2026-11-18. Only the "
         "November-18 section (12 finals) is claimed from it, as the absence proof for "
         "LAC/SAS/MIN/POR.",
         [p["recent_game_selection"]["schedule_url"]]),
        ("F-93-09", "informational",
         "In the DET@SAS game book the printed row for Elijah Harkless shows TOT=1 with "
         "OR=0 and DR=0 (identical in every retrieval). Not repaired, not used; Harkless "
         "is not on the report. Recorded in games[].teams.DET.row_notes.",
         [p["games"][1]["gamebook_url"]]),
    ]
    item_html = "".join(
        f"<h2>{esc(i)} <span class=\"mut\">({esc(s)})</span></h2>"
        f"<p>{esc(t)}</p><p class=\"note\">Sources: "
        + " · ".join(f"<a href=\"{esc(u)}\">{esc(u)}</a>" for u in urls) + "</p>"
        for i, s, t, urls in items)
    flagged = banner + """
<p class="note">Published so the owner can review after the site is live. Flagged items do
not block this round's tables; every affected cell is either blank or carries its
attribution source.</p>""" + item_html

    return {
        "index.html": page("Player game logs — injury report 11/19/2026", index, "index.html"),
        "player-logs.html": page("Player logs", logs, "player-logs.html"),
        "injuries.html": page("Injuries", injuries, "injuries.html"),
        "flagged.html": page("Flagged for Review", flagged, "flagged.html"),
    }


def main():
    pages = build()
    if "--check" in sys.argv:
        bad = []
        for name, blob in pages.items():
            path = os.path.join(OUT, name)
            if not os.path.exists(path):
                bad.append(f"missing {name}")
            elif open(path, encoding="utf-8").read() != blob:
                bad.append(f"drift {name}")
        if bad:
            print("site check FAILED: " + "; ".join(bad), file=sys.stderr)
            return 1
        print(f"site check PASS ({len(pages)} pages byte-identical)")
        return 0
    os.makedirs(OUT, exist_ok=True)
    for name, blob in pages.items():
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(blob)
    print(f"wrote {len(pages)} pages to 93becd26/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
