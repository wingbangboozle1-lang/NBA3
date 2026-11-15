#!/usr/bin/env python3
"""Render the 11/14/26 01:30 PM ET injury-freshness audit (audit_736efb4b/index.html + flagged.html).

Inputs : audit_736efb4b/data/official_injury_report_2026-11-14_0130PM.json   (capture.py)
         audit_736efb4b/data/delta_1330PM_vs_canonical.json                 (compare.py)
         data/app/canonical.json                                             (published snapshot)
Run    : python3 audit_736efb4b/build.py
Every table row carries a link to the official NBA PDF it was read from. A value the official text
does not print is left blank and flagged; nothing is inferred to fill it.
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAP = json.loads((HERE / "data" / "official_injury_report_2026-11-14_0130PM.json").read_text(encoding="utf-8"))
DELTA = json.loads((HERE / "data" / "delta_1330PM_vs_canonical.json").read_text(encoding="utf-8"))
# Frozen 2026-11-14 snapshot: this page compares the 1:30 PM ET report against the
# snapshot that was published that day, so it must not follow a later refresh.
CANON = json.loads((ROOT / "data" / "snapshots" / "canonical_2026-11-14.json").read_text(encoding="utf-8"))

NEW_URL = CAP["source_url"]
NEW_STAMP = CAP["report_stamp"]
INDEX_URL = CAP["index_url"]
CANON_URL = CANON["injuries"]["source_url"]
CANON_STAMP = CANON["injuries"]["report_stamp"]
RAW_PATH = "data/official_injury_report_2026-11-14_0130PM_raw.md"
NYS = "NOT YET SUBMITTED"


def e(v):
    return html.escape("" if v is None else str(v), quote=True)


def link(url, label):
    return f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>'


def chip(text, kind="neutral"):
    return f'<span class="chip chip-{kind}">{e(text)}</span>'


def table(headers, rows, tid):
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="table-wrap"><table id="{tid}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def page(title, body, active):
    nav = (
        '<nav class="site-nav"><div class="wrap">'
        '<a href="../index.html">&larr; NBA Edge Lab home</a> &middot; '
        '<a href="index.html"' + (' class="active"' if active == "index" else "") + '>Injury freshness audit</a> &middot; '
        '<a href="flagged.html"' + (' class="active"' if active == "flagged" else "") + '>Flagged for Review</a> &middot; '
        '<a href="../app/injuries.html">Canonical injuries page</a>'
        '</div></nav>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} — NBA3 audit 736efb4b</title>
<link rel="stylesheet" href="../app/assets/app.css">
</head><body>
<header class="site-header"><div class="wrap"><div class="brand">NBA3 / NBA Edge Lab — injury freshness audit (736efb4b)</div></div></header>
{nav}
<main class="wrap">
{body}
</main>
<footer class="site-footer"><div class="wrap"><p>Built by <code>audit_736efb4b/build.py</code> from the official NBA
injury-report PDF (<a href="{e(NEW_URL)}" target="_blank" rel="noopener noreferrer">{e(NEW_STAMP)}</a>) and the published
snapshot in <code>data/app/canonical.json</code>. Not investment advice. Nothing here is a bet.</p></div></footer>
</body></html>
"""


# ---------------------------------------------------------------- derived sets
rows = CAP["rows"]
players_1330 = [r for r in rows if r["row_kind"] == "player"]
nys_1330 = [r for r in rows if r["row_kind"] == "not_yet_submitted"]
outcome_by_player = {o["player"]: o for o in DELTA["player_outcomes"]}
summary = DELTA["summary"]
counts = DELTA["counts"]
team_outcomes = DELTA["team_not_yet_submitted_outcomes"]

# Game-day slate from the canonical 2026-11-14 injury-impact block (one game per team per date).
slate_1114 = {}
for r in CANON["injury_impact"]:
    if r["date"] == "2026-11-14":
        slate_1114.setdefault(r["matchup"], {})[r["team"]] = r
team_name_for_abbr = {}
for r in CANON["injuries"]["rows"]:
    if r.get("team") and r.get("team_name"):
        team_name_for_abbr[r["team"]] = r["team_name"]
team_to_game = {}
for matchup, sides in slate_1114.items():
    for abbr in sides:
        team_to_game[abbr] = matchup
name_to_abbr = {v: k for k, v in team_name_for_abbr.items()}

# Attribution rule (documented on the page): a row names its team -> attributed to that team.
# If the matchup is printed it must equal the team's 11/14 game; if it is blank, the team plays
# exactly one game on 11/14 (official slate), so the row is attributed to that game and flagged.
def attribute_1114(row):
    abbr = name_to_abbr.get(row["team_name"])
    if not row["team_name"] or abbr not in team_to_game:
        return None, "team not printed" if not row["team_name"] else "team not on 11/14 slate"
    game = team_to_game[abbr]
    if row["matchup"] and row["matchup"] != game:
        return None, "matchup printed differs"
    return game, ("matchup printed" if row["matchup"] else "matchup blank; team has one 11/14 game")


team_rows_html = []
team_state_counts = {"filed": 0, "not_filed": 0}
for matchup in sorted(slate_1114):
    for abbr in sorted(slate_1114[matchup]):
        canon_side = slate_1114[matchup][abbr]
        name = team_name_for_abbr.get(abbr, "")
        mine = [r for r in players_1330 if r["team_name"] == name and attribute_1114(r)[0] == matchup]
        mine_nys = [r for r in nys_1330 if r["team_name"] == name and attribute_1114(r)[0] == matchup]
        if mine:
            state_1330 = f"filed ({len(mine)} player rows)"
            team_state_counts["filed"] += 1
        elif mine_nys:
            state_1330 = NYS
            team_state_counts["not_filed"] += 1
        else:
            state_1330 = "no attributable row"
            team_state_counts["not_filed"] += 1
        canon_state = canon_side.get("availability_state", "")
        canon_out = ", ".join(x if isinstance(x, str) else x.get("player", "") for x in canon_side.get("out", []))
        canon_q = ", ".join(x if isinstance(x, str) else x.get("player", "") for x in canon_side.get("questionable", []))
        out_1330 = ", ".join(r["player"] for r in mine if r["status"] == "Out")
        q_1330 = ", ".join(r["player"] for r in mine if r["status"] in ("Questionable", "Doubtful"))
        prob_1330 = ", ".join(r["player"] for r in mine if r["status"] == "Probable")
        changed = []
        if (canon_state == "FILED") != bool(mine):
            changed.append("filing state")
        if canon_out != out_1330:
            changed.append("Out list")
        if canon_q != q_1330:
            changed.append("Questionable/Doubtful list")
        basis = sorted({attribute_1114(r)[1] for r in mine + mine_nys}) or ["-"]
        kind = "warn" if changed else "ok"
        team_rows_html.append([
            e(name), e(matchup), e(canon_state or "-"), e(state_1330),
            e(out_1330 or "—"), e(q_1330 or "—"), e(prob_1330 or "—"),
            chip("changed: " + ", ".join(changed), "warn") if changed else chip("no change", "ok"),
            e("; ".join(basis)),
            link(NEW_URL, "1:30 PM PDF") + " · " + link(CANON_URL, f"{CANON_STAMP} PDF"),
        ])

# Attribution for the team-blank rows: none are attributed to a team.
blank_team_rows = [r for r in players_1330 if not r["team_name"]]

# ---------------------------------------------------------------- index page
card = lambda k, v, s: (f'<div class="card"><div class="k">{e(k)}</div><div class="v">{e(v)}</div>'
                        f'<div class="s">{e(s)}</div></div>')
cards = "".join([
    card("Rows transcribed", counts["rows_in_1330_report"], f"{counts['player_rows_in_1330_report']} player rows + {counts['not_yet_submitted_rows_in_1330_report']} team rows NOT YET SUBMITTED"),
    card("Lines not transcribed", len(CAP["unparsed_lines"]), "one garbled line (see F736-06)"),
    card("Status changes vs published", summary.get("status_changed", 0), "same player, different status"),
    card("New player rows", summary.get("new_in_1330_report", 0), "not in the published snapshot"),
    card("Unchanged players", summary.get("unchanged", 0), "same status and reason"),
    card("Published players missing", len(DELTA["canonical_players_not_in_1330"]), "in snapshot, absent from 1:30 PM"),
])

player_rows_html = []
for r in players_1330:
    o = outcome_by_player[r["player"]]
    out_kind = {"unchanged": "ok", "status_changed": "bad", "new_in_1330_report": "warn"}.get(o["outcome"], "neutral")
    flags = "; ".join(r["flags"]) if r["flags"] else "—"
    player_rows_html.append([
        e(r["player"]), e(r["team_name"] or ""), e(r["matchup"] or ""), e(r["game_date"] or ""),
        e(r["status"]), e(r["reason"]),
        e(o["status_canonical"] or ""), e(o["reason_canonical"] or ""),
        chip(o["outcome"].replace("_", " "), out_kind),
        e(flags),
        link(NEW_URL, "1:30 PM PDF"),
    ])

team_nys_rows = []
for o in team_outcomes:
    if o["game_date"] != "11/15/2026" and o["outcome"] != "unverified_garbled_line_only":
        pass
    kind = {"still_not_yet_submitted": "neutral", "still_not_yet_submitted_matchup_blank": "neutral",
            "unverified_garbled_line_only": "bad"}.get(o["outcome"], "warn")
    team_nys_rows.append([
        e(o["game_date"]), e(o["game_time_et"]), e(o["matchup"]), e(o["team_name"]),
        e(NYS), chip(o["outcome"].replace("_", " "), kind),
        e(", ".join(o["players_printed_1330"]) or "—"),
        link(NEW_URL, "1:30 PM PDF") + " · " + link(CANON_URL, f"{CANON_STAMP} PDF"),
    ])

body_index = f"""
<h1>Injury freshness audit: official report 11/14/26 01:30 PM ET</h1>
<p class="lead">On 2026-11-14, the official NBA injury-report index lists game-day reports up to
<strong>{e(NEW_STAMP)}</strong>. The published injury snapshot on this site is the
<strong>{e(CANON_STAMP)}</strong> report. This page transcribes the newer report row by row, compares it with the
published snapshot, and lists every item that could not be confirmed.</p>

<div class="callout warn"><p><strong>What this page does not do.</strong> It does not re-run the model. The published
picks, lines, injury-impact minutes and strategy numbers were computed from the 04:15 AM ET snapshot and still
read that snapshot. Treat every changed row below as a reason to re-run the pipeline, not as a repriced number.</p></div>

<div class="cards">{cards}</div>

<h2>1. Read-time check</h2>
<ul>
<li>Official index (read 2026-11-14, ~13:42 ET): {link(INDEX_URL, "official.nba.com injury report index")} lists the
11/14 reports from 12:00 a.m. to <strong>1:30 p.m. ET</strong>. The index text says reports are "updated on a continual basis".</li>
<li>Newest report transcribed: {link(NEW_URL, "Injury-Report_2026-11-14_01_30PM.pdf")} ({e(NEW_STAMP)}). Verbatim text saved in
<code>{e(RAW_PATH)}</code>.</li>
<li>Next report probe: {link("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_45PM.pdf", "Injury-Report_2026-11-14_01_45PM.pdf")}
returned <code>AccessDenied</code> (not published at read time). No newer report was verifiable.</li>
<li>Published snapshot compared: {link(CANON_URL, f"Injury-Report_2026-11-14_04_15AM.pdf ({CANON_STAMP})")}, as stored in
<code>data/app/canonical.json</code>.</li>
</ul>

<h2>2. Games on the 11/14 slate: filing state before and after</h2>
<p>Attribution rule: a row is attributed to a team only when the team name is printed. If the matchup is printed it must equal the
team's 11/14 game. If the matchup is blank, the team plays exactly one game on 11/14 in the official slate, so the row is attributed
to that game and labelled as such. Rows with no team printed are never attributed (section 4).</p>
{table(["Team", "Game (11/14)", "Published state (04:15 AM)", "1:30 PM state", "Out (1:30 PM)", "Doubtful / Questionable (1:30 PM)", "Probable (1:30 PM)", "Change", "Attribution basis", "Sources"], team_rows_html, "team-1114")}

<h2>3. Every player row in the 1:30 PM report</h2>
<p>{counts['player_rows_in_1330_report']} rows with a status. Status and reason are copied from the report; blank cells are blank.
Outcome compares by player name with the published snapshot (no player name is duplicated in either report).</p>
{table(["Player", "Team (as printed)", "Matchup (as printed)", "Game date (as printed)", "Status 1:30 PM", "Reason 1:30 PM", "Status published", "Reason published", "Outcome", "Flags", "Source"], player_rows_html, "players-1330")}

<h2>4. Team rows marked NOT YET SUBMITTED (11/14 and 11/15)</h2>
<p>Published snapshot: 23 team rows. 1:30 PM report: {counts['not_yet_submitted_rows_in_1330_report']} team rows
(the garbled line is not counted here). A team with players printed in the report is no longer "not yet submitted".</p>
{table(["Game date", "Time (ET)", "Matchup", "Team", "Status 1:30 PM", "Outcome", "Players printed for this team", "Sources"], team_nys_rows, "team-nys")}

<h2>5. Rows the report prints with no team</h2>
<p>{len(blank_team_rows)} player rows have a blank team cell in the extraction. They are listed on the
<a href="flagged.html">Flagged for Review</a> page with their status. They are not assigned to any team, because the
text does not show it.</p>

<h2>6. Method and limits</h2>
<ul>
<li>Capture: verbatim fetch of the PDF text; transcription by <code>audit_736efb4b/capture.py</code>. The status counts of the
transcription equal the raw counts of each status word in the report text ({e(str(CAP['checks']['status_counts_match_raw']).lower())}).</li>
<li>Comparison: <code>audit_736efb4b/compare.py</code>. Rebuild: <code>python3 audit_736efb4b/capture.py &amp;&amp; python3 audit_736efb4b/compare.py &amp;&amp; python3 audit_736efb4b/build.py</code>.</li>
<li>Tests: <code>python3 -m unittest discover -s audit_736efb4b -p 'test_*.py'</code> (counts, official-link rule, blank-not-filled rule).</li>
<li>The official text extraction loses column headers after page 1. This is why several rows print no date, matchup or team.</li>
</ul>
<h2>7. Reconciliation with PR #75 (session 965fbd17, merged to main first)</h2>
<p>Both sessions compared the same official 01:30 PM ET report. Where the two differ, the difference is a counting convention, not a conflicting reading of a row.</p>
<table id="reconcile-965"><thead><tr><th>Item</th><th>This page (736efb4b)</th><th>PR #75 (965fbd17)</th><th>Status</th><th>Source</th></tr></thead><tbody>
<tr><td>Rows transcribed</td><td>67 (50 player, 17 NOT YET SUBMITTED); 1 garbled line not transcribed</td><td>68 raw table rows parsed; the same garbled line kept as an unattributed fragment</td><td>agree</td><td>{link(NEW_URL, "1:30 PM PDF")}</td></tr>
<tr><td>Status changes vs the stored snapshot</td><td>4: Christie Q→Doubtful; Brown Jr. Q→Probable; Harkless Q→Available; Jones Q→Available</td><td>4 (Christie in the counted tier; Brown Jr., Harkless, Jones in the no-date tier)</td><td>agree</td><td>{link(NEW_URL, "1:30 PM PDF")}</td></tr>
<tr><td>Rows with no team printed</td><td>13, not attributed</td><td>13 name-only rows, not attributed</td><td>agree</td><td>{link(NEW_URL, "1:30 PM PDF")}</td></tr>
<tr><td>Rows with a team but no matchup (Minnesota 3, Miami 4)</td><td>Attributed to CHI@MIN and DET@MIA by the one-game-per-team rule, labelled</td><td>Not counted (team, no matchup)</td><td>convention differs (F736-12)</td><td>{link(NEW_URL, "1:30 PM PDF")}</td></tr>
<tr><td>Team filing state, 10 teams on 11/14</td><td>Table in section 2: 9 filed, Memphis not filed</td><td>Not presented as a team-level filing table in its flags</td><td>added here</td><td>{link(NEW_URL, "1:30 PM PDF")}</td></tr>
</tbody></table>
<p>See also: <a href="flagged.html">Flagged for Review (F736-01 … F736-12)</a>.</p>
"""

# ---------------------------------------------------------------- flagged page
def flag_row(fid, title, detail, evidence, status):
    return [e(fid), e(title), detail, evidence, chip(status, "warn" if status != "fixed" else "ok")]

flags = [
    flag_row("F736-01", "Published pages describe the 04:15 AM report as the newest listed",
             e("The injury page, the summary card and the sources row said the 04:15 AM ET report was the newest one on the official index. At ~13:42 ET the index lists the 01:30 PM ET report. Session 965fbd17 corrected these statements and merged to main first (PR #75, flag 965-F-01). Still stale on other canonical pages and logged as CR-736EFB4B-01 (owner of scripts/assemble_canonical.py): the freshness page (five teams 'not filed'; four of them have now filed), the review page, the requirements page and the flagged register."),
             link(INDEX_URL, "official index") + " · " + link(NEW_URL, "1:30 PM PDF"), "superseded by PR #75 in part"),
    flag_row("F736-02", "Four published players have a different status in the 1:30 PM report",
             e("Christie, Max (Dallas): Questionable → Doubtful. Brown Jr., Mikel (Brooklyn): Questionable → Probable. Harkless, Elijah (Detroit): Questionable → Available. Jones, Isaac (Detroit): Questionable → Available. Picks and injury-impact figures were not re-run."),
             link(NEW_URL, "1:30 PM PDF") + " · " + link(CANON_URL, "04:15 AM PDF"), "open"),
    flag_row("F736-03", "New player rows: 24 players are not in the published snapshot",
             e("Includes Mobley, Evan (Out), Mitchell, Donovan (Questionable), Harden, James (Questionable), Antetokounmpo, Giannis (Probable), Allen, Jarrett (Questionable), Thompson, Klay (Probable). None of these can be checked against the published data until the pipeline is re-run."),
             link(NEW_URL, "1:30 PM PDF"), "open"),
    flag_row("F736-04", "Teams now filed that the published snapshot shows as not yet submitted",
             e("New Orleans (5 rows), Cleveland (1 row), Chicago (1 row), Miami (4 rows, matchup blank). The published injury-impact block still reads NOT_YET_DUE for these four teams, so their availability is unknown in the published pages."),
             link(NEW_URL, "1:30 PM PDF") + " · " + link(CANON_URL, "04:15 AM PDF"), "open"),
    flag_row("F736-05", "13 player rows print no team in the text extraction",
             e("Harden, James; Merrill, Sam; Mitchell, Donovan; Mobley, Evan; Tomlin, Nae'Qwan; Udeh, Jr., Ernest; Watson, Peyton (block after the DAL@CLE rows); Claxton, Nic; Powell, Norman; Sellers, Jaylin; Smith, Jalen; Swain, Dailyn; Wilson, Caleb (block after the BKN@MEM rows). Team, matchup and date are left blank; none is attributed. A person must read the PDF page to confirm the team column."),
             link(NEW_URL, "1:30 PM PDF"), "unverified"),
    flag_row("F736-06", "One line is garbled and was not transcribed",
             e("Raw line: <code>| 09:00 (ET) | Milwaukee Bucks OKC@SAC | Milwaukee Bucks Oklahoma City Thunder | NOT YET SUBMITTED NOT YET SUBMITTED |</code>. Two team names and two NOT YET SUBMITTED values share one cell, so the team-to-status pairing is unverified. Milwaukee (11/15) and Oklahoma City (11/15) are marked unverified."),
             link(NEW_URL, "1:30 PM PDF"), "unverified"),
    flag_row("F736-07", "Game date is printed only on the first row of each table block",
             e("Rows after the first of each 11/14 block print no game date. Date is left blank and not filled from the block heading."),
             link(NEW_URL, "1:30 PM PDF"), "open"),
    flag_row("F736-08", "Four Miami rows print no matchup",
             e("The four Miami Heat rows print the team name only. They are attributed to DET@MIA because Miami plays one game on 11/14 in the official slate, and this is labelled on the page."),
             link(NEW_URL, "1:30 PM PDF") + " · " + link("https://www.nba.com/schedule?date=2026-11-14", "nba.com schedule"), "open"),
    flag_row("F736-09", "Next report not verifiable",
             e("The 01:45 PM ET probe returned AccessDenied, and the index stops at 1:30 PM ET. The site cannot prove that no report exists after that time. Reports are described by the NBA as updated continually."),
             link("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_45PM.pdf", "01:45 PM probe") + " · " + link(INDEX_URL, "official index"), "open"),
    flag_row("F736-10", "The published snapshot is still the basis of the pick and injury pages",
             e("No model re-run was done in this change. Picks and injury-impact figures remain computed from the 04:15 AM snapshot. Re-running the pipeline is the next step; it needs a human decision on the publication window (CQ-36 and the open CR items in COORDINATION.md)."),
             link(CANON_URL, "04:15 AM PDF"), "open"),
    flag_row("F736-11", "One stale sentence on the injuries page (fixed here)",
             e("The paragraph after the injury table said five of the ten 11/14 teams had not filed, and tied that to a back-to-back rule. At 01:30 PM ET four of those five have printed players (New Orleans, Cleveland, Chicago, Miami); Memphis has not. The sentence now gives both readings, and the back-to-back explanation is labelled as not re-verified in this round."),
             link(NEW_URL, "1:30 PM PDF") + " · " + link(CANON_URL, "04:15 AM PDF"), "fixed"),
    flag_row("F736-12", "Overlap with PR #75 (session 965fbd17): same report, different counting",
             e("Both sessions compared the 01:30 PM report with the stored snapshots. The four status changes and the 13 no-team rows agree. The two sessions count differently: this page attributes 7 rows with a team but no matchup (Minnesota, Miami) through the one-game-per-team rule and labels them; PR #75 does not count them. Both are published; neither overwrites the other. See section 7 of the index page."),
             link(NEW_URL, "1:30 PM PDF") + " · " + link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/injury_delta_0130pm.json", "PR #75 delta JSON"), "info"),
]
body_flagged = f"""
<h1>Flagged for Review</h1>
<p class="lead">Irregularities and unverified items from the 11/14/26 01:30 PM ET injury-freshness audit. These do not block
publication. Each has its evidence link. Request changes by editing <code>audit_736efb4b/build.py</code> or
<code>audit_736efb4b/capture.py</code>, or by replying in COORDINATION.md.</p>
{table(["ID", "Item", "Detail", "Evidence (official source)", "Status"], flags, "flags-736")}
"""

(HERE / "index.html").write_text(page("Injury freshness audit", body_index, "index"), encoding="utf-8")
(HERE / "flagged.html").write_text(page("Flagged for Review", body_flagged, "flagged"), encoding="utf-8")
print("wrote", HERE / "index.html", "and", HERE / "flagged.html")
print("team states:", team_state_counts, "| blank-team player rows:", len(blank_team_rows))
