"""Build the arena/caad4c37-nba3 site pages (session arena/caad4c37-nba3).

Reads only committed files:
  data/arena_caad4c37/requirements.json   - the 20-item brief, verified line by line
  data/arena_caad4c37/register.json       - flags, questions, suggestions, change requests
  data/arena_caad4c37/result_feed_quarters.json
  data/arena_caad4c37/injuries/archive_index.json
  data/arena_caad4c37/injuries/deltas.json

Hard rules enforced while building, matching the brief:
  * every data row ends in an official-source link; a row with none fails the build
  * a value that could not be confirmed is rendered as a blank cell with 'unverified',
    never as a dash, a zero or a guess
  * no wall-clock is written into the output, so the build is reproducible

Run:  python3 scripts/build_caad4c37.py
      python3 scripts/build_caad4c37.py --check   (rebuild, diff, exit 1 on drift)
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "arena_caad4c37"
OUT = ROOT / "arena_caad4c37"
SESSION = "arena/caad4c37-nba3"
BASE = "main @ 5fde67e"

CSS = """
:root{--bg:#0f1216;--panel:#161b22;--line:#252c36;--ink:#e6edf3;--dim:#9aa7b4;--accent:#5aa9e6;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--card:#1c222b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header.site{background:var(--panel);border-bottom:1px solid var(--line)}
header.site .wrap{padding:16px 20px}
.brand{font-weight:700;font-size:17px;color:var(--ink);text-decoration:none}
.brand span{color:var(--accent)}
.back{float:right;color:var(--dim);text-decoration:none;font-size:12.5px;margin-top:4px}
.back:hover{color:var(--ink)}
.stamp{color:var(--dim);font-size:12.5px;margin-top:6px}
nav.site{background:var(--card);border-bottom:1px solid var(--line)}
nav.site .wrap{padding:0 20px;display:flex;flex-wrap:wrap;gap:2px}
nav.site a{color:var(--dim);text-decoration:none;padding:11px 12px;font-size:13.5px;
border-bottom:2px solid transparent}
nav.site a:hover{color:var(--ink)}
nav.site a.on{color:var(--ink);border-bottom-color:var(--accent)}
main.wrap{padding:26px 20px 64px}
h1{font-size:25px;margin:0 0 6px}
h2{font-size:18px;margin:30px 0 10px}
h3{font-size:15px;margin:20px 0 8px;color:var(--dim);text-transform:uppercase;letter-spacing:.04em}
p.lede{color:var(--dim);margin:0 0 22px;max-width:82ch}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:8px 0 6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px}
.card .k{font-size:26px;font-weight:700}
.card .l{color:var(--dim);font-size:12.5px;margin-top:2px}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:12px 0 8px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
caption{text-align:left;color:var(--dim);font-size:12.5px;padding:9px 12px;background:var(--card)}
th,td{padding:9px 11px;border-top:1px solid var(--line);text-align:left;vertical-align:top}
thead th{background:var(--card);color:var(--dim);font-weight:600;font-size:12.5px;
text-transform:uppercase;letter-spacing:.03em;white-space:nowrap}
tbody tr:hover{background:#141a21}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;font-weight:600;
border:1px solid transparent;white-space:nowrap}
.pill.ok{background:rgba(63,185,80,.13);color:var(--ok);border-color:rgba(63,185,80,.35)}
.pill.warn{background:rgba(210,153,34,.13);color:var(--warn);border-color:rgba(210,153,34,.35)}
.pill.bad{background:rgba(248,81,73,.13);color:var(--bad);border-color:rgba(248,81,73,.35)}
.pill.dim{background:rgba(154,167,180,.1);color:var(--dim);border-color:rgba(154,167,180,.3)}
.blank{color:var(--bad);font-size:12px;font-weight:600}
a{color:var(--accent)}
a:visited{color:#8ab4d8}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
.note{background:var(--panel);border-left:3px solid var(--accent);padding:11px 14px;
border-radius:0 6px 6px 0;color:var(--dim);font-size:13.5px;margin:14px 0;max-width:95ch}
.note.bad{border-left-color:var(--bad)}
.note.warn{border-left-color:var(--warn)}
footer.site{border-top:1px solid var(--line);background:var(--panel);color:var(--dim);
font-size:12.5px;padding:18px 0}
ul.tight{margin:6px 0 6px 18px;padding:0}
ul.tight li{margin:3px 0}
"""

NAV = [
    ("index.html", "Overview"),
    ("requirements.html", "Brief coverage"),
    ("result-feed.html", "Result feed & quarters"),
    ("injuries.html", "Injury chain"),
    ("flagged.html", "Flagged for review"),
    ("questions.html", "Open questions"),
    ("suggestions.html", "Suggestions"),
    ("sources.html", "Sources"),
]


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def pill(status: str) -> str:
    m = {"done": ("ok", "Done"), "done_caveat": ("warn", "Done, with a caveat"),
         "partial": ("warn", "Partial - blank and flagged"),
         "blocked": ("bad", "Blocked"),
         "not_on_main": ("dim", "Not on main"),
         "high": ("bad", "High"), "medium": ("warn", "Medium"), "low": ("dim", "Low")}
    cls, label = m.get(status, ("dim", status))
    return f'<span class="pill {cls}">{esc(label)}</span>'


def link(url: str, label: str | None = None) -> str:
    return (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(label or url)}</a>')


def page(title: str, active: str, body: str, subtitle: str = "") -> str:
    nav = "".join(
        f'<a href="{esc(h)}" class="{"on" if h == active else ""}">{esc(t)}</a>'
        for h, t in NAV)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 brief-coverage audit</title>
<meta name="description" content="Line-by-line verification of the NBA3 brief against main, session {SESSION}.">
<link rel="stylesheet" href="assets/site.css">
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="index.html">NBA3 <span>/</span> brief-coverage audit</a>
  <a class="back" href="../index.html">&larr; main dashboard</a>
  <div class="stamp">Session {esc(SESSION)} · verified against {esc(BASE)} · re-read 2026-11-16 ·
    every row links to the official source it was checked against</div>
</div></header>
<nav class="site"><div class="wrap">{nav}</div></nav>
<main class="wrap">
  <h1>{esc(title)}</h1>
  <p class="lede">{subtitle}</p>
{body}
</main>
<footer class="site"><div class="wrap">
  Built by <span class="mono">{esc(SESSION)}</span> from committed files only. No value on these
  pages was inferred: a figure that could not be confirmed from an official source is rendered as
  a blank cell marked <span class="blank">unverified</span>.
</div></footer>
</body>
</html>
"""


def table(caption: str, heads: list[str], rows: list[list[str]]) -> str:
    """Build-time gate, straight from the brief.

    Every body row must end either in an official-source link or in an explicit
    'unverified' marker. A silent blank fails the build: the brief allows a value that could not
    be confirmed, but only if it is marked as unverified rather than left empty.
    """
    for i, r in enumerate(rows, 1):
        last = r[-1] if r else ""
        if "nba.com" in last and "href" in last:
            continue
        if 'class="blank"' in last:
            continue
        raise SystemExit(
            f"row {i} of '{caption}' ends in neither an official-source link nor an "
            f"explicit unverified marker: {last!r}")
    th = "".join(f"<th>{esc(h)}</th>" for h in heads)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="table-wrap"><table>\n<caption>{esc(caption)}</caption>\n'
            f'<thead><tr>{th}</tr></thead>\n<tbody>\n{tr}</tbody>\n</table></div>')


def table_plain(caption: str, heads: list[str], rows: list[list[str]]) -> str:
    """Same markup as table(), WITHOUT the official-source gate.

    Used only for repository-process tables whose rows are about pull requests and file
    ownership and therefore cannot honestly carry an official-source link. Data tables must use
    table().
    """
    th = "".join(f"<th>{esc(h)}</th>" for h in heads)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="table-wrap"><table data-process-table="1">\n'
            f'<caption>{esc(caption)}</caption>\n'
            f'<thead><tr>{th}</tr></thead>\n<tbody>\n{tr}</tbody>\n</table></div>')


def quarters_cell(q) -> str:
    if not q:
        return '<span class="blank">unverified</span>'
    return " · ".join(str(x) for x in q)


# -------------------------------------------------------------------------------------- pages

def page_index(req: dict, reg: dict, feed: dict, inj: dict) -> str:
    items = req["items"]
    c = feed["counts"]
    done = sum(1 for i in items if i["status"] == "done")
    newest = inj["files"][-1]
    cards = [
        (f'{done} / {len(items)}', "brief items done with no caveat"),
        (f'{sum(1 for i in items if i["status"] == "done_caveat")}', "done, but with a published caveat"),
        (f'{sum(1 for i in items if i["status"] == "partial")}', "partial — blank and flagged"),
        (f'{sum(1 for i in items if i["status"] == "blocked")}', "blocked on a missing input"),
    ]
    card_html = "".join(f'<div class="card"><div class="k">{esc(k)}</div>'
                        f'<div class="l">{esc(l)}</div></div>' for k, l in cards)

    rows = [[f'<a href="requirements.html#{esc(i["id"])}">{esc(i["id"])}</a>',
             esc(i["requirement"])[:150] + ("…" if len(i["requirement"]) > 150 else ""),
             esc(i["category"]), pill(i["status"]),
             link(i["source_url"], i["source_label"])]
            for i in items]
    tbl = table("The brief as written, with the status verified by this session",
                ["ID", "Requirement", "Area", "Status", "Official source"], rows)

    body = f"""
<div class="cards">{card_html}</div>

<h2>What this session did</h2>
<div class="note">It did not rebuild the model. It re-read <span class="mono">{esc(BASE)}</span>
line by line against the brief, then closed the two gaps it could close from official sources and
logged the rest as change requests. Everything here is generated from committed files, so it can be
re-checked without re-running a fetch.</div>

<h3>Two gaps closed</h3>
<ul class="tight">
<li><strong>Quarter scores.</strong> The five games of 2026-11-14 already carried quarter scores;
all nine games of 2026-11-13 were blank and flagged. The field is printed by the official game
books, so it was read from them: this session added 60 cells to the 40 already there, giving
{esc(c["quarter_cells_written"])} of {esc(c["quarter_cells_possible"])}. Each reading is accepted
only where the printed quarters sum to the printed final.
{esc(c["both_teams_verified"])} of {esc(c["games"])} games have both teams' quarters;
{esc(c["partial"])} have one side blank and flagged.</li>
<li><strong>Late-evening injury reports.</strong> The newest report stored anywhere on main was
11/15 06:15 AM ET. The official index lists 11/15 reports through 09:00 PM ET. Both the 08:45 PM
and 09:00 PM versions were fetched and stored with their revision and retrieval times and diffed:
the consecutive pair shows no change, and the gap back to the published baseline shows
21 status changes and 72 new filings.</li>
</ul>

<h3>What it found instead</h3>
<ul class="tight">
<li>The published injury banner is <strong>14h45m behind</strong> the newest official report, and
the freshness gate cannot see it because it compares on-disk reports with each other.</li>
<li>Travel distance is <strong>blank on every row</strong> — the coordinate file the code reads is
empty, while a populated one sits elsewhere in the repository.</li>
<li>Minutes redistribution and per-player game logs each cover <strong>10 of 30 teams</strong>.</li>
<li>The market-anchored prior is implemented and <strong>correctly refuses</strong> to publish
without a closing-line feed.</li>
</ul>

<h2>Brief coverage</h2>
{tbl}

<h2>Where to go next</h2>
<div class="cards">
<div class="card"><div class="k">{esc(len(reg["flags"]))}</div>
<div class="l"><a href="flagged.html">flagged irregularities</a>, each with its source</div></div>
<div class="card"><div class="k">{esc(len(reg["questions"]))}</div>
<div class="l"><a href="questions.html">open questions</a> that block a decision</div></div>
<div class="card"><div class="k">{esc(len(reg["suggestions"]))}</div>
<div class="l"><a href="suggestions.html">suggestions</a>, none implemented</div></div>
<div class="card"><div class="k">{esc(newest["rows_total"])}</div>
<div class="l">rows in the newest stored injury report
({esc(newest["revision_time_et"])})</div></div>
</div>
"""
    return page("Overview", "index.html", body,
                "A line-by-line verification of the twenty-item brief against the published site, "
                "plus the two gaps this session could close from official sources. Every claim "
                "below was checked by opening a file, not read off a summary.")


def page_requirements(req: dict) -> str:
    rows = []
    for i in req["items"]:
        caveat = i.get("caveat") or ""
        rows.append([
            f'<a id="{esc(i["id"])}"></a><strong>{esc(i["id"])}</strong>',
            esc(i["requirement"]),
            esc(i["category"]),
            pill(i["status"]),
            f'<div class="mono">{esc(i["evidence"])}</div>',
            esc(i["verification"]),
            (f'<strong>Gap.</strong> {esc(caveat)}' if caveat
             else '<span class="pill ok">no open gap</span>'),
            link(i["source_url"], i["source_label"]),
        ])
    tbl = table("Every row was checked by opening the file in 'evidence' and reading the field in "
                "'how it was verified'",
                ["ID", "Requirement", "Area", "Status", "Evidence (file)",
                 "How it was verified", "Open gap", "Official source"], rows)

    legend = "".join(f'<li><span class="mono">{esc(k)}</span> — {esc(v)}</li>'
                     for k, v in req["status_legend"].items())
    body = f"""
<div class="note">Status legend: <ul class="tight">{legend}</ul></div>
{tbl}
<div class="note">Nothing on this page is graded on effort. An item is <em>done</em> only because
the artefact was opened and the field read; an item is <em>blocked</em> only because the artefact
itself says it is blocked. Where a value does not exist, it is left blank rather than filled.</div>
"""
    return page("Brief coverage", "requirements.html", body,
                "The twenty items of the brief, in the order they were written, with the status "
                "each one actually has on main and the file that was opened to check it.")


def page_result_feed(feed: dict) -> str:
    rows = []
    for g in feed["games"]:
        note = g.get("away_quarters_note", "") or g.get("home_quarters_note", "")
        rows.append([
            esc(g["date"]),
            f'{esc(g["away"])} @ {esc(g["home"])}',
            f'<span class="num">{esc(g["away_pts"])}</span>',
            f'<span class="num">{esc(g["home_pts"])}</span>',
            f'<span class="num">{quarters_cell(g["away_quarters"])}</span>',
            f'<span class="num">{quarters_cell(g["home_quarters"])}</span>',
            esc(g["state"]),
            pill("ok" if g["quarters_verified"] == "both" else "warn"),
            esc(note) if note else '<span class="pill ok">sums to the printed final</span>',
            link(g["gamebook_source"], "official game book"),
        ])
    tbl = table(feed["rule"], ["Date", "Matchup", "Away final", "Home final",
                               "Away quarters", "Home quarters", "State", "Quarters",
                               "Verification note", "Official source"], rows)

    c = feed["counts"]
    body = f"""
<div class="cards">
<div class="card"><div class="k">{esc(c["games"])}</div><div class="l">games in the feed</div></div>
<div class="card"><div class="k">{esc(c["both_teams_verified"])}</div>
<div class="l">both teams' quarters verified</div></div>
<div class="card"><div class="k">{esc(c["partial"])}</div>
<div class="l">one side blank and flagged</div></div>
<div class="card"><div class="k">{esc(c["quarter_cells_written"])}/{esc(c["quarter_cells_possible"])}</div>
<div class="l">quarter cells written</div></div>
</div>

<div class="note">Before this session, the five games of <strong>2026-11-14</strong> already
carried quarter scores (40 of 112 cells) and all nine games of <strong>2026-11-13</strong> were
null with the note "quarter scores not captured — blank, flagged". The official game books print a
"SCORE BY PERIOD" block, so the 11/13 half was obtainable from an official source after all: this
session added 60 cells, taking the feed to 100 of 112. <em>This session's first reading said every
cell was null; that was wrong and is recorded as F-CAAD4C37-14.</em>
A quarter score is written only where the printed quarters sum to the printed final; that test is
the game book's own arithmetic, and it is what makes a corrupted extraction detectable instead of
usable.</div>

{tbl}

<h2>Why three team-sides are still blank</h2>
<ul class="tight">
<li><strong>GSW in GSW @ SAS</strong> — the extraction returned the San Antonio row only; no
Warriors period row and no Warriors line-score line exists in it.</li>
<li><strong>MEM in MEM @ NOP</strong> — the row prints five values against a six-column header
(25 · 25 · 27 · 140): Q4 and FINAL are missing and 140 is neither a quarter nor the official final
of 142.</li>
<li><strong>ORL in MIL @ ORL</strong> — the row prints 33 · 30 · 32 · 33 · FINAL 107, which sums to
128. The PDF was fetched twice and returned the identical extraction, so it is not a transient
read error.</li>
</ul>
<div class="note bad">None of these was filled in. Deriving a missing quarter from the final and
the other three quarters would produce a number that looks verified and is not, which is the one
failure mode this project cannot afford.</div>

<h2>Two rows where the official PDF contradicts itself</h2>
<div class="note warn">In CLE @ MIA and OKC @ LAC the rendered period table disagrees with the
line-score text line printed beneath it in the same document. Both were resolved to the text line,
because the text line, the team-totals row and the official scoreboard all agree and only one table
cell disagrees. The table reading is preserved in the stored excerpts — it was not overwritten.
Both are listed on the <a href="flagged.html">Flagged for review</a> page.</div>
"""
    return page("Result feed & quarter scores", "result-feed.html", body,
                "One row per game: date, teams, final score, quarter scores — filled from the "
                "official game books, with anything the source did not print left blank.")


def page_injuries(inj: dict, deltas: dict) -> str:
    rows = []
    for f in inj["files"]:
        sc = f["status_counts"]
        rows.append([
            f'<strong>{esc(f["revision_time_et"])}</strong>',
            esc(f["retrieved_utc"]),
            f'<span class="num">{esc(f["rows_total"])}</span>',
            f'<span class="num">{esc(f["player_rows"])}</span>',
            f'<span class="num">{esc(f["team_rows_not_yet_submitted"])}</span>',
            f'<span class="num">{esc(f["unattributed_player_rows"])}</span>',
            " · ".join(f"{k} {v}" for k, v in sc.items() if v),
            esc(f["captured_by"]),
            esc(f["role"]),
            link(f["source_url"], "official PDF"),
        ])
    tbl = table("One stored file per official version, each carrying both the revision time "
                "printed in the PDF and the UTC retrieval time",
                ["Revision time (ET)", "Retrieved (UTC)", "Rows", "Player rows",
                 "NOT YET SUBMITTED", "Unattributed", "Status counts", "Captured by",
                 "Role", "Official source"], rows)

    drows = []
    for d in deltas["deltas"]:
        c = d["counts"]
        chg = "".join(
            f'<li>{esc(s["player"])} ({esc(s["team"])}): {esc(s["from"])} → '
            f'<strong>{esc(s["to"])}</strong></li>' for s in d["status_changes"])
        drows.append([
            f'{esc(d["from_revision_time_et"])} → {esc(d["to_revision_time_et"])}',
            "yes" if d["consecutive"] else "no",
            f'<span class="num">{esc(c["status_changes"])}</span>',
            f'<span class="num">{esc(c["reason_changes"])}</span>',
            f'<span class="num">+{esc(c["added"])}</span>',
            f'<span class="num">−{esc(c["removed"])}</span>',
            f'<ul class="tight">{chg}</ul>' if chg else
            '<span class="pill ok">no status changed</span>',
            link(d["to_source"], "official PDF"),
        ])
    dtbl = table("Consecutive versions are diffed to surface status changes",
                 ["Pair", "Consecutive", "Status changes", "Reason changes", "Added",
                  "Removed", "What changed", "Official source"], drows)

    body = f"""
<div class="note bad"><strong>The published banner is behind the official feed.</strong>
<span class="mono">app/injuries.html</span> prints revision time 2026-11-15 06:15 AM ET. The
official index read at 2026-11-16T02:13Z lists 11/15 reports through 09:00 PM ET and no 11/16
report yet. The gap is 14h45m, and the delta below shows what happened inside it. The gate that
should catch this compares the newest report <em>on disk</em> with itself, not with the index —
carried as <span class="mono">CR-CAAD4C37-02</span>.</div>

<h2>Stored versions</h2>
{tbl}

<h2>Diffs</h2>
{dtbl}

<div class="note">The 72 added rows between 06:15 AM and 08:45 PM are mostly teams filing, not 72
new injuries: both reports cover the same game dates (11/15/2026 and 11/16/2026), so the added rows
are new filings. The single removed row is the official PDF changing
"Embid, Joel" to "Embiid, Joel" — a spelling change, reported as a remove plus an add rather than
merged, because merging it would be a guess about identity.</div>

<h2>Retrieval times, and why they are printed separately</h2>
<div class="note">A report has two times that matter and they are not the same thing. The
<strong>revision time</strong> is printed inside the PDF and tells you how old the league's
information is. The <strong>retrieval time</strong> tells you how old <em>our</em> copy is. Both
are recorded per file, so a stale publication is distinguishable from a stale source.</div>
"""
    return page("Injury-report chain", "injuries.html", body,
                "Every stored version of the official injury report with both of its timestamps, "
                "and the diff between consecutive versions that shows the status changes.")


def page_flagged(reg: dict) -> str:
    rows = [[f'<strong>{esc(f["id"])}</strong>', pill(f["severity"]), esc(f["title"]),
             esc(f["detail"]), esc(f["disposition"]), link(f["source_url"], "official source")]
            for f in reg["flags"]]
    tbl = table("Irregularities found by this session's re-read, highest severity first",
                ["ID", "Severity", "Finding", "Detail", "Disposition", "Official source"], rows)

    proc = "".join(
        f'<h3>{esc(p["id"])} — {esc(p["title"])}</h3>'
        f'<p>{esc(p["detail"])}</p>'
        f'<div class="note"><strong>Disposition.</strong> {esc(p["disposition"])}<br>'
        f'<em>{esc(p["why_not_in_the_table_above"])}</em></div>'
        for p in reg.get("process_notes", []))

    cr = [[f'<strong>{esc(c["id"])}</strong>', esc(c["to"]), esc(c["request"]), esc(c["why"]),
           esc(c["status"])] for c in reg["change_requests"]]
    crt = table_plain(
        "Change requests to other sessions' files — logged, deliberately not executed. "
        "These are process rows, so they carry no official-source link by design.",
        ["ID", "To the owner of", "Request", "Why", "Status"], cr)

    body = f"""
<div class="note">These do not block anything. They are published so they can be reviewed after the
site is live. Every one carries the official source it was found in, so it can be re-checked
without trusting this session's reading.</div>
{tbl}
<h2>Repository-process notes</h2>
{proc}
<h2>Change requests made instead of edits</h2>
<div class="note">Four other sessions had open pull requests when this session claimed, and they
own the files these changes belong to. Editing them would have produced a conflict nobody could
review, so each is recorded below as a request with the reason it matters.</div>
{crt}
"""
    return page("Flagged for review", "flagged.html", body,
                "Irregularities and unverified values found during the line-by-line re-read, "
                "each with the official source it was found in.")


def page_questions(reg: dict, req: dict) -> str:
    by_id = {i["id"]: i for i in req["items"]}
    rows = []
    for q in reg["questions"]:
        first = (q["blocks"].split(",")[0].strip() if q["blocks"] else "")
        src = by_id.get(first, {})
        rows.append([f'<strong>{esc(q["id"])}</strong>', esc(q["question"]), esc(q["known"]),
                     esc(q["missing"]), esc(q["how_to_discover"]), esc(q["blocks"]),
                     link(src["source_url"], src["source_label"])
                     if src else '<span class="blank">unverified</span>'])
    tbl = table("What is known, what is missing, and how to discover the missing part",
                ["ID", "Question", "What we already have", "What is missing",
                 "How to discover it", "Blocks", "Official source of the blocked item"], rows)
    body = f"""
<div class="note">These are the questions that have to be answered before a decision based on this
project is reasonable. They are split three ways on purpose: what the repository can already
answer, what it cannot, and the concrete step that would close the gap.</div>
{tbl}
"""
    return page("Open questions", "questions.html", body,
                "A clear list of what is known, what is missing, and the step that would find the "
                "missing part — so a decision can be made on the information, not around it.")


def page_suggestions(reg: dict) -> str:
    by_id = {f["id"]: f for f in reg["flags"]}
    rows = []
    for s in reg["suggestions"]:
        first = (s["linked_flag"].split(",")[0].strip() if s["linked_flag"] else "")
        src = by_id.get(first, {})
        rows.append([f'<strong>{esc(s["id"])}</strong>', esc(s["area"]), esc(s["suggestion"]),
                     esc(s["options"]), esc(s["recommendation"]), esc(s["linked_flag"]),
                     f'<span class="pill warn">{esc(s["status"])}</span>',
                     link(src["source_url"], "official source of " + first)
                     if src else '<span class="blank">unverified</span>'])
    tbl = table("Nothing here has been implemented — each is a choice for the owner",
                ["ID", "Area", "Suggestion", "Options", "Recommendation",
                 "Linked finding", "Status", "Official source"], rows)
    body = f"""
<div class="note">These exist so a path can be chosen before anything is built. Each row gives the
options, which one this session would pick, and the finding that prompted it. None of them has been
implemented, and none will be until one is chosen.</div>
{tbl}
"""
    return page("Suggestions", "suggestions.html", body,
                "Ways to improve the site and the decision it supports, with the options and a "
                "recommendation for each. Nothing here has been implemented.")


def page_sources(req: dict, feed: dict, inj: dict) -> str:
    seen: dict[str, str] = {}
    for i in req["items"]:
        seen.setdefault(i["source_url"], i["source_label"])
    for g in feed["games"]:
        seen.setdefault(g["gamebook_source"], f"Official game book — {g['away']} @ {g['home']}, {g['date']}")
        seen.setdefault(g["scoreboard_source"], f"Official scoreboard — {g['date']}")
    for f in inj["files"]:
        seen.setdefault(f["source_url"], f"Official injury report — {f['revision_time_et']}")
    seen.setdefault("https://official.nba.com/nba-injury-report-2026-27-season/",
                    "NBA Official — injury report index (2026-27 season)")

    rows = [[esc(i + 1), esc(l), link(u, u)] for i, (u, l) in enumerate(sorted(seen.items()))]
    tbl = table("Every official page read to produce these pages",
                ["#", "What it was used for", "URL"], rows)
    body = f"""
<div class="note">{esc(len(seen))} distinct official URLs. All of them are on
<span class="mono">nba.com</span> (including the stats CDN
<span class="mono">statsdmz.nba.com</span> and the injury-report CDN
<span class="mono">ak-static.cms.nba.com</span>, both of which serve official NBA documents).
The one non-NBA source in the wider repository — Wikipedia, for arena coordinates — is not used
anywhere on these pages.</div>
{tbl}
"""
    return page("Sources", "sources.html", body,
                "Every official source read to build these pages, with what it was used for.")


# ---------------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    req = json.loads((DATA / "requirements.json").read_text())
    reg = json.loads((DATA / "register.json").read_text())
    feed = json.loads((DATA / "result_feed_quarters.json").read_text())
    inj = json.loads((DATA / "injuries" / "archive_index.json").read_text())
    deltas = json.loads((DATA / "injuries" / "deltas.json").read_text())

    reg["flags"] = sorted(reg["flags"],
                          key=lambda f: {"high": 0, "medium": 1, "low": 2}[f["severity"]])

    pages = {
        "index.html": page_index(req, reg, feed, inj),
        "requirements.html": page_requirements(req),
        "result-feed.html": page_result_feed(feed),
        "injuries.html": page_injuries(inj, deltas),
        "flagged.html": page_flagged(reg),
        "questions.html": page_questions(reg, req),
        "suggestions.html": page_suggestions(reg),
        "sources.html": page_sources(req, feed, inj),
    }

    if args.check:
        bad = [n for n, t in pages.items() if (OUT / n).read_text(encoding="utf-8") != t]
        if bad:
            print("pages do not reproduce from the committed data:", ", ".join(bad),
                  file=sys.stderr)
            return 1
        print(f"OK: {len(pages)} pages reproduce from the committed data")
        return 0

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    for name, text in pages.items():
        (OUT / name).write_text(text, encoding="utf-8")

    # Build-time link check: every internal href resolves, every data row has a source.
    import os
    import re
    for name, text in pages.items():
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http", "#", "mailto:")):
                continue
            if not (OUT / href.split("#")[0]).exists():
                raise SystemExit(f"{name}: broken internal link -> {href}")
    print(f"wrote {len(pages)} pages + assets to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
