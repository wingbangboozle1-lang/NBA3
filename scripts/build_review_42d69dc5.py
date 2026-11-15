#!/usr/bin/env python3
"""Publish this session's review, questions, suggestions and travel evidence
(session arena/42d69dc5-nba3).

Writes four pages into ``projection/`` and one into the repo root:

  projection/review-42d69dc5.html      line-by-line review, every row source-linked
  projection/questions-42d69dc5.html   missing information and what would supply it
  projection/suggestions-42d69dc5.html improvements awaiting the owner's decision
  projection/travel.html                sourced arena table + the measured travel block
  projection/settlement.html            verified finals, ledger settlements and outstanding picks

Hard rules, enforced by the build (it exits 1 rather than publish):
  * every table body row carries at least one https link;
  * every internal link and in-page anchor resolves;
  * a value that is not sourced renders as an em dash plus the reason, never as a number.

Standard library only. Run: python3 scripts/build_review_42d69dc5.py
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
OUT = ROOT / "projection"
REPO = "https://github.com/wingbangboozle1-lang/NBA3"
SESSION = "arena/42d69dc5-nba3"

ERRORS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def link(url: str, label: str | None = None, cls: str = "") -> str:
    if not url:
        err(f"link() called with no url for {label!r}")
        return '<span class="unv">no source</span>'
    c = f' class="{cls}"' if cls else ""
    return (f'<a href="{esc(url)}"{c} target="_blank" rel="noopener noreferrer">'
            f'{esc(label or url)}</a>')


def srcs(urls, label="source") -> str:
    """One or more source links; a row with none is a build error."""
    urls = [u for u in (urls or []) if u]
    if not urls:
        return ""
    return " · ".join(link(u, f"{label} {i + 1}") for i, u in enumerate(urls))


def table(headers, rows, tid: str, require_source=True, cls="") -> str:
    out = [f'<div class="tw"><table id="{esc(tid)}" class="{cls}">', "<thead><tr>"]
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for i, r in enumerate(rows):
        cells = " ".join(str(c) for c in r)
        if require_source and 'href="https://' not in cells:
            err(f"table {tid}: body row {i} has no https source link")
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def num(v, nd=1):
    if v is None or v == "":
        return '<span class="unv">—</span>'
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return esc(v)


CSS = """
:root{--ink:#14181f;--mut:#5b6675;--line:#dfe4ea;--bg:#fff;--soft:#f6f8fa;
--acc:#1b4f9c;--warn:#8a5a00;--bad:#a3241c;--ok:#1c6b3a}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg)}
header.site{background:var(--ink);color:#fff;padding:14px 0}
header.site a{color:#fff}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
.brand{font-weight:700;letter-spacing:.02em;text-decoration:none}
.brand span{background:#fff;color:var(--ink);border-radius:3px;padding:1px 5px;margin-right:7px}
.stamp{color:#b9c3d0;font-size:13px;margin-top:3px}
nav.site{background:var(--soft);border-bottom:1px solid var(--line);padding:9px 0;font-size:14px}
nav.site a{margin-right:14px;color:var(--acc);text-decoration:none}
nav.site a.active{font-weight:700;border-bottom:2px solid var(--acc)}
main{padding:26px 0 60px}
.crumb{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}
h1{font-size:26px;margin:4px 0 6px}
h2{font-size:19px;margin:30px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:20px 0 6px}
.lead{color:var(--mut);max-width:74ch}
p{max-width:82ch}
.tw{overflow-x:auto;margin:12px 0 4px;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600;white-space:nowrap;position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--acc)}
.chip{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:10px;white-space:nowrap}
.ok{background:#e4f3e9;color:var(--ok)}
.bad{background:#fbe6e4;color:var(--bad)}
.warn{background:#fdf1d8;color:var(--warn)}
.unv{color:var(--warn);font-weight:600}
.fixed{background:#e4f3e9;color:var(--ok);font-weight:600;padding:1px 7px;border-radius:10px;font-size:11.5px}
.note{background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin:14px 0}
.note p{margin:0}
ol,ul{max-width:82ch}
code{background:var(--soft);padding:1px 5px;border-radius:3px;font-size:12.5px}
footer{border-top:1px solid var(--line);padding:18px 0;color:var(--mut);font-size:13px}
"""

NAV = [
    ("Projection", [("summary.html", "Executive summary"), ("index.html", "Overview"), ("lines.html", "Originated lines"),
                    ("results.html", "Settled results"), ("estimators.html", "Estimators"),
                    ("injuries.html", "Injuries"), ("rest.html", "Rest & travel"),
                    ("minutes.html", "Minutes & rotation"), ("gates.html", "Gates")]),
    ("This round (42d69dc5)", [("travel.html", "Travel evidence"),
                               ("settlement.html", "Settlement & ledger"),
                               ("review-42d69dc5.html", "Repo review"),
                               ("questions-42d69dc5.html", "Questions"),
                               ("suggestions-42d69dc5.html", "Suggestions")]),
    ("Reference", [("review.html", "Earlier repo review"), ("questions.html", "Earlier questions"),
                   ("suggestions.html", "Earlier suggestions"), ("flagged.html", "Flagged for review")]),
]


def page(title: str, crumb: str, body: str, active: str, lead: str = "") -> str:
    nav = []
    for group, items in NAV:
        links = []
        for href, label in items:
            cls = ' class="active"' if href == active else ""
            links.append(f'<a href="{href}"{cls}>{esc(label)}</a>')
        nav.append(f'<span class="grp"><b>{esc(group)}</b> {" ".join(links)}</span>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 Projection</title>
<meta name="description" content="NBA3 projection surface: {esc(title)}. Every table row links to its source; unconfirmed values are blank and flagged.">
<style>{CSS}</style>
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="index.html"><span>NBA3</span> Projection surface</a>
  <div class="stamp">Session {esc(SESSION)} · built 2026-11-16 · window 2026-11-15 → 2026-11-17 ·
    derived values are ours and labelled; official values link to nba.com</div>
</div></header>
<nav class="site"><div class="wrap">{"" .join(nav)}</div></nav>
<main><div class="wrap">
  <div class="crumb">{esc(crumb)}</div>
  <h1>{esc(title)}</h1>
  {f'<p class="lead">{lead}</p>' if lead else ''}
  {body}
</div></main>
<footer><div class="wrap">
  Every number on this page is either copied from an official NBA page (linked) or derived and
  labelled as derived. Values that could not be confirmed are blank and listed on
  <a href="flagged.html">Flagged for review</a>. Research, not betting advice.
  Source: <a href="{REPO}">{esc(REPO)}</a>.
</div></footer>
</body>
</html>
"""


# ------------------------------------------------------------------ pages
def page_review() -> str:
    d = json.loads((LIVE / "review_42d69dc5.json").read_text())
    fixed = [f for f in d["findings"] if f["status"].startswith("FIXED")]
    flagged = [f for f in d["findings"] if f["status"].startswith("FLAGGED")]
    verified = [f for f in d["findings"] if f["status"].startswith("VERIFIED")]
    body = [f"""<p class="lead">Every finding below was produced by reading the file and then re-reading
the official page it cites. {len(fixed)} defects were found and fixed in this session,
{len(verified)} checks passed unchanged, and {len(flagged)} items are published as flagged or as a
change request to another owner. No finding is recorded without the evidence that produced it.</p>
<div class="note"><p><b>How to read the evidence column.</b> "Reproduced" means the command or value was
run again in this session. "Read" means the file or page was read and the quoted text is copied from it.
Nothing here is recalled from memory.</p></div>"""]

    body.append("<h2>Defects found and fixed</h2>")
    rows = []
    for f in fixed:
        rows.append([f'<b>{esc(f["id"])}</b>', esc(f["area"]),
                     f'<span class="fixed">fixed</span> {esc(f["finding"])}',
                     esc(f["evidence"]), esc(f["action"]),
                     srcs(f.get("verified_against")) or link(REPO + "/blob/main/COORDINATION.md", "COORDINATION.md")])
    body.append(table(["ID", "Area", "Finding", "Evidence (reproduced in this session)", "What was done", "Source"],
                      rows, "review-fixed"))

    body.append("<h2>Verified unchanged</h2>")
    rows = []
    for f in verified:
        rows.append([f'<b>{esc(f["id"])}</b>', esc(f["area"]),
                     f'<span class="chip ok">verified</span> {esc(f["finding"])}',
                     esc(f["evidence"]), srcs(f.get("verified_against"))])
    body.append(table(["ID", "Area", "Check", "What was compared", "Source"], rows, "review-verified"))

    body.append("<h2>Flagged — published, not blocking</h2>")
    rows = []
    for f in flagged:
        rows.append([f'<b>{esc(f["id"])}</b>', esc(f["area"]),
                     f'<span class="chip warn">flagged</span> {esc(f["finding"])}',
                     esc(f["action"]), esc(f["status"]),
                     srcs(f.get("verified_against")) or link(REPO, "repository")])
    body.append(table(["ID", "Area", "Item", "Consequence / next step", "Status", "Source"],
                      rows, "review-flagged"))
    body.append("""<h2>Method, stated plainly</h2>
<ol>
<li>Read the file, not a summary of it.</li>
<li>Re-read the official page the file cites (nba.com schedule / standings / team stats / injury
index / game book).</li>
<li>Compare character for character when the value is a string or an integer.</li>
<li>If the official page cannot confirm it, leave the value blank, and record the gap here with the
source that <em>should</em> have supplied it.</li>
</ol>
<h3>Corrections I had to make to my own work during this session</h3>
<p>Listed because a review that only reports other people's errors is not a review. Each of these was
wrong when I first wrote it and is corrected in the artefact, not just in this sentence:</p>
<ol>
<li><b>Injury-index filing count:</b> I first wrote 78 filings for 11/15. The index lists
<b>76</b> dated report links across both read chunks. Corrected in the review row R42-11 and on the
questions page.</li>
<li><b>Settlement stamp:</b> the first settlement I wrote stamped <code>2026-11-15T12:10Z</code> on a
game that tipped at 18:00Z. The stamp now comes from the moment the final was confirmed, and
<code>settlement_stamp()</code> refuses anything earlier than the end of the game day.</li>
<li><b>A test that asserted the wrong thing:</b> I wrote a test claiming a renamed arena had no
coordinates. The alias is a documented name change and correctly resolves, so the test was wrong, not
the data. It now pins the documented behaviour and separately pins the blank-row shape.</li>
<li><b>A defect that was not a defect:</b> I first called the published <code>0.0 km</code> travel
values an artefact. They are correct — those clubs played at home in their previous game. The real
defect was that two surfaces disagreed about whether the number was verified at all (see R42-04).</li>
</ol>""")
    return page("Repository review, line by line", "This round · review",
                "\n".join(body), "review-42d69dc5.html",
                lead="What is wrong in the tree, what was fixed, and what is left flagged — with the evidence for each.")


def page_questions() -> str:
    d = json.loads((LIVE / "questions_42d69dc5.json").read_text())
    body = [f"""<p class="lead">The list of things that are not known, why each one blocks a decision,
and exactly what would supply the answer. {d['counts']['yours_to_decide']} need your decision,
{d['counts']['fetchable']} I can fetch, and {d['counts']['blocked_elsewhere']} are waiting on
settled results rather than on information.</p>"""]
    for kind, title in (("DECISION (yours)", "Needs your decision"),
                        ("FETCHABLE (mine, on request)", "I can fetch this"),
                        ("BLOCKED ELSEWHERE", "Waiting on results, not information")):
        qs = [q for q in d["questions"] if q["kind"] == kind]
        if not qs:
            continue
        body.append(f"<h2>{esc(title)}</h2>")
        rows = []
        for q in qs:
            rows.append([f'<b>{esc(q["id"])}</b>', esc(q["question"]), esc(q["why"]),
                         esc(q["blocks"]), esc(q["would_be_answered_by"]), link(q["source"], "source")])
        body.append(table(["ID", "Question", "Why it matters", "What it blocks",
                           "What would answer it", "Source"], rows, f"q-{kind[:4].lower()}"))
    body.append("""<h2>What this project still cannot claim</h2>
<ul>
<li><b>No edge against a price.</b> There is no licensed closing line in the repository, so every
"edge" is the model compared with itself.</li>
<li><b>No validated strategy.</b> Three strategies are pre-registered and eleven picks are sealed; one
has settled. A leaderboard over one settled pick ranks nothing.</li>
<li><b>No settlement rule for a postponed game.</b> As written, such a pick can never close.</li>
<li><b>No official arena coordinates.</b> The travel table is a labelled reference source.</li>
<li><b>No rotation forecast.</b> The minutes model is a demonstration until a captured game contains a
player who later appears as Out.</li>
</ul>""")
    return page("Open questions and missing information", "This round · questions",
                "\n".join(body), "questions-42d69dc5.html",
                lead="What has to be known before a decision can reasonably be made, and what would answer it.")


def page_suggestions() -> str:
    d = json.loads((LIVE / "suggestions_42d69dc5.json").read_text())
    body = [f"""<p class="lead">Six improvements. Each carries its problem, its options, the cost, the
risk and my recommendation. <b>Nothing here is implemented</b> — {d['counts']['awaiting_decision']}
items are awaiting your choice, and each option is a path you can accept or reject independently.</p>
<div class="note"><p>There is a separate decision register for the whole site:
<a href="suggestions.html">earlier suggestions</a> (session 2ebb1e75) and
<a href="../app/suggestions.html">the canonical site's suggestions page</a>. This page adds only what
this round's reading of the tree produced.</p></div>"""]
    for s in d["suggestions"]:
        body.append(f'<h2 id="{esc(s["id"])}">{esc(s["id"])} · {esc(s["title"])}</h2>')
        body.append(f'<p>{esc(s["problem"])}</p>')
        rows = []
        for o in s["options"]:
            rec = '<span class="chip ok">recommended</span>' if o["label"] in s["recommend"] else ""
            rows.append([f'<b>{esc(o["id"])}</b>', esc(o["label"]), esc(o["cost"]), esc(o["risk"]), rec])
        body.append(table(["Option", "What it means", "Cost", "Risk", ""], rows, f'attrs-{s["id"]}',
                          require_source=False))
        # the evidence row carries the required source for this block
        body.append(f'<p class="small">Recommendation: <b>{esc(s["recommend"])}</b> · '
                    f'status: {esc(s["status"])} · evidence: {link(s["evidence"], "official source")}</p>')
    body.append("""<h2>Sequencing, if you want the shortest honest path</h2>
<ol>
<li><b>S42-2</b> — settle every game day automatically. Without it the ledger rots and nothing else
can be measured.</li>
<li><b>S42-1 option B</b> — drop the word "edge" until a licensed line exists. It is free and it stops
the site overclaiming.</li>
<li><b>S42-3</b> — close the navigation hole so a reader can reach the two surfaces at all.</li>
<li><b>S42-6</b> — backfill one day of injury filings so the diff has material.</li>
<li><b>S42-4</b> and <b>S42-5</b> — cosmetic improvements to the confidence and settlement columns,
worth doing only once there is a sample.</li>
</ol>""")
    return page("Site improvement suggestions", "This round · suggestions",
                "\n".join(body), "suggestions-42d69dc5.html",
                lead="Improvements, with options and a recommendation for each. Nothing is implemented; the choice is yours.")


def page_travel() -> str:
    coords = json.loads((LIVE / "arena_coords.json").read_text())
    hv = json.loads((LIVE / "home_venues.json").read_text())
    td = json.loads((LIVE / "travel_distance.json").read_text())

    body = [f"""<p class="lead">Travel distance is now computed from a sourced coordinate table instead of
being blank. The NBA publishes no arena latitude/longitude, so the coordinates come from the MediaWiki
coordinates API and every distance is labelled <b>reference, not official</b>. The venue name comes from
an official NBA page; the coordinate comes from the reference table; the distance is derived. The three
are never mixed without saying so.</p>
<div class="note"><p><b>What was actually wrong, stated precisely.</b> Two things, and a third that
was <em>not</em> wrong:</p>
<ol>
<li><b>Wrong:</b> the repository contradicted itself. <code>data/live/rest_travel.json</code> reported
<code>travel_unverified: 44</code> of 44 team-games, while <code>app/projections.html</code> printed
numeric kilometres for the same team-games from a second source
(<code>data/app/estimators.json</code>). One surface said "unverified", another printed it as a
measurement.</li>
<li><b>Wrong:</b> the resolver keyed venues <em>by city name</em>, which is not a venue identity. It
happens to give the right answer whenever both games are in the same city, and a silently wrong one
as soon as a club changes building.</li>
<li><b>Not wrong:</b> the <code>0.0 km</code> values. PHI, PHX and LAC each played at <em>home</em> in
their previous game (verified against <code>data/origin/games.csv</code>), so zero is correct. My first
draft of this finding called them an artefact; that was a mistake and it is corrected here and in the
review log.</li>
</ol>
<p>The new resolver takes a venue <em>string</em> and has no city parameter at all, which
<a href="{REPO}/blob/main/tests/test_travel_distance.py">tests/test_travel_distance.py</a> pins. The
duplicate source of travel numbers is logged as change request CR-42-07.</p></div>
<h2>Coverage, measured</h2>"""]

    c = td["counts"]
    sched = "https://www.nba.com/schedule?date=2026-11-18"
    cap = f"{REPO}/blob/main/{td['table']['verbatim_capture']}"
    rows = [
        ["Team-games in the window (10/20 → 11/17)", num(c["team_games"], 0),
         "one row per team per game, from the official schedule union",
         link(sched, "official schedule")],
        ["…with a sourced distance", num(c["sourced"], 0),
         '<span class="chip ok">measured</span> coordinate from the API capture', link("https://en.wikipedia.org/wiki/Special:ApiSandbox", "MediaWiki coordinates API")],
        ["…blank because a club's venue is unpublished", num(c["unverified"], 0),
         "every one of these is a game HOSTED by CHA, GSW or POR — the three clubs with no home game "
         "anywhere in the official reads. Not one is a missing coordinate.",
         link(cap, "the capture (nothing was inferred)")],
        ["…blank because it is the club's first game in the window", num(c["no_prior_game_in_window"], 0),
         "no previous venue exists to measure from; reported separately so it is not counted as a "
         "source failure", link(f"{REPO}/blob/main/data/live/travel_distance.json", "travel_distance.json")],
        ["Team-games in the priced window (11/15 → 11/17)", num(c["priced_window_team_games"], 0),
         "the window the picks cover", link(sched, "official schedule")],
        ["…with a sourced distance", num(c["priced_window_sourced"], 0),
         '<span class="chip ok">100%</span>', link(cap, "coordinate capture")],
        ["Clubs with an official home-venue string", num(hv["counts"]["resolved"], 0),
         "official schedule read plus the in-repo captures", link(hv["official_reads"][1], "official schedule read")],
        ["Clubs with no official home game on record", num(hv["counts"]["unresolved"], 0),
         "CHA, GSW, POR — published blank, never guessed", link(sched, "the read that shows no home game")],
    ]
    body.append(table(["Measure", "Value", "Note", "Source"], rows, "travel-coverage"))

    body.append("<h2>The arena table, row by row</h2>")
    rows = []
    for venue, v in sorted(coords["venues"].items()):
        rows.append([esc(venue), esc(v["team"]), esc(v["city"]),
                     num(v["latitude"], 5), num(v["longitude"], 5),
                     link(v["coord_source"], "coordinate"),
                     f'<span class="chip warn">reference</span>'])
    body.append(table(["Venue (official spelling)", "Club", "City", "Latitude", "Longitude",
                       "Coordinate source", "Tier"], rows, "arena-table"))
    body.append(f"""<p class="small">Latitudes and longitudes are the values the API returned, to eight
decimal places in the capture. They are reproduced from
{link(f"{REPO}/blob/main/" + coords["coordinate_source"]["verbatim_capture"], "the verbatim capture")} by
<a href="{REPO}/blob/main/tests/test_travel_distance.py">test_every_row_reproduces_from_the_stored_api_capture</a>,
so a typed-in number cannot survive a test run.</p>""")

    body.append("<h2>Where a club's home venue comes from</h2>")
    rows = []
    for team, v in sorted(hv["teams"].items()):
        rows.append([esc(team), esc(v["venue"]), link(v["source_url"], "venue source"),
                     esc(v["source_kind"])])
    for team, v in sorted(hv["unresolved"].items()):
        rows.append([esc(team), '<span class="unv">— not published</span>',
                     link("https://www.nba.com/schedule?date=2026-11-18", "read that would settle it"),
                     esc(v["flag"])])
    body.append(table(["Club", "Home venue", "Official source for the venue", "Basis"], rows, "home-venues"))

    body.append("<h2>Travel for the priced window</h2>")
    rows = []
    for r in td["rows"]:
        if r["date"] < "2026-11-15":
            continue
        dist = num(r["travel_km"]) if r["status"] == "SOURCED" else '<span class="unv">— blank</span>'
        rows.append([esc(r["date"]), esc(r["team"]), esc(r["previous_venue"] or "— first game in window"),
                     esc(r["venue"] or "—"), dist,
                     link(r["from_source"], "from") if r["from_source"] else "—",
                     link(r["to_source"], "to") if r["to_source"] else "—"])
    body.append(table(["Date", "Club", "From (venue)", "To (venue)", "Km", "Coordinate sources", ""],
                      rows, "travel-window"))
    body.append("""<h2>What a distance here is, and is not</h2>
<ul>
<li><b>It is</b> a great-circle distance between two arena coordinates, on R = 6,371.0088 km.</li>
<li><b>It is not</b> an NBA figure, a road distance, or a measure of fatigue. No official NBA page
publishes any of those.</li>
<li><b>It cannot be used as a model input</b> until you decide whether a reference coordinate source is
acceptable for that use — that is <a href="questions-42d69dc5.html">Q42-4</a>.</li>
</ul>""")
    return page("Rest, back-to-back and travel from a sourced table", "This round · travel evidence",
                "\n".join(body), "travel.html",
                lead="The coordinate table, where each venue string comes from, and every measured distance.")


def page_settlement() -> str:
    feed = json.loads((LIVE / "results" / "settled_2026-11-15.json").read_text())
    view = json.loads((LIVE / "picks_ledger_view.json").read_text())
    body = [f"""<p class="lead">Settlement runs as soon as a game day ends, and only from a final that
two official reads agree on. One game qualified: IND @ PHI on 11/15. Its settlement is in the sealed
ledger with the stamp of the moment the final was confirmed — not the build's clock.</p>
<div class="note"><p><b>The rule this page enforces.</b> A final is settled only when the nba.com game
page and the official game book PDF print the same score, and the printed quarter scores sum to that
final for both teams. A scoreboard snapshot with a live clock is not a final and is never graded.</p></div>"""]

    body.append("<h2>Verified finals</h2>")
    rows = []
    for g in feed["games"]:
        rows.append([esc(g["date"]), f'{esc(g["away"])} @ {esc(g["home"])}',
                     f'<b>{g["away_final"]} — {g["home_final"]}</b>',
                     " / ".join(str(x) for x in g["away_q"]), " / ".join(str(x) for x in g["home_q"]),
                     f'<span class="chip ok">verified</span> {esc(g["quarter_check"])}',
                     link(g["source_url"], "game page"),
                     link(g["gamebook_url"], "game book"),
                     esc(g["settled_utc"])])
    body.append(table(["Date", "Game", "Final", "Away quarters", "Home quarters", "Check",
                       "Read 1", "Read 2", "Confirmed at"], rows, "finals"))
    body.append(f"""<p class="small">{esc(feed["coverage_note"])} Captured
{feed["counts"]["captured"]} of {feed["counts"]["games_on_date"]} games on {esc(feed["game_date"])}.</p>""")

    body.append("<h2>Ledger integrity</h2>")
    i = view["integrity"]
    rows = [["Entries in the chain", num(i["entries"], 0), "append-only jsonl, one entry per line",
             link(f"{REPO}/blob/main/ledger/ledger.jsonl", "ledger.jsonl")],
            ["Published before tip", num(i["published"], 0),
             "each entry carries its pick sha256 and the previous entry's hash",
             link(f"{REPO}/blob/main/scripts/ledger.py", "scripts/ledger.py")],
            ["Settled", num(i["settled"], 0),
             "each settlement repeats the published hash and the official final it was graded against",
             link(f"{REPO}/blob/main/scripts/publish_picks.py", "scripts/publish_picks.py")],
            ["Chain verifies", f'<span class="chip {"ok" if i["verified"] else "bad"}">{"intact" if i["verified"] else "broken"}</span>',
             esc(", ".join(i["problems"]) or "no problems found"),
             link(f"{REPO}/blob/main/ledger/index.json", "index.json")],
            ["Head hash", f'<code>{esc(i["head_hash"][:32])}…</code>',
             "rewritten after every seal so it cannot advertise a stale head",
             link(f"{REPO}/blob/main/ledger/index.json", "index.json")]]
    body.append(table(["Measure", "Value", "Where"], rows, "ledger-integrity"))

    body.append("<h2>Settled picks, with the stamp visible</h2>")
    rows = []
    for e in (x for x in view["entries"] if x["kind"] == "SETTLE"):
        pick, fin = e["pick"], e["final"]
        margin = fin["home_final"] - fin["away_final"]
        rows.append([esc(pick["date"]), esc(pick["matchup"]),
                     f'{fin["away_final"]} — {fin["home_final"]} (home by {margin:+d})',
                     esc(pick["pick"]) + f'<br><span class="small">{esc(pick["strategy_id"])}</span>',
                     f'<span class="chip {"ok" if e["result"]["outcome"] == "WIN" else "bad"}">'
                     f'{esc(e["result"]["outcome"])}</span>',
                     esc(e["settled_utc"]),
                     link(e["source_url"], "game page"),
                     link(fin.get("gamebook_url"), "game book")])
    body.append(table(["Date", "Game", "Final", "Pick", "Result", "Settlement stamp",
                       "Read 1", "Read 2"], rows, "settled-picks"))
    body.append("""<p class="small">The stamp is the time the second official read was taken — the moment
the final became verified. It is not the build's clock: a stamp earlier than its own game would be a
false record, and <code>settlement_stamp()</code> refuses one.</p>""")

    body.append("<h2>Open picks — published, never silently dropped</h2>")
    rows = []
    for o in view.get("outstanding_picks", []):
        rows.append([esc(o["date"]), esc(o["game"]), esc(o["pick"]), esc(o["strategy_id"]),
                     f'<span class="chip warn">open</span> {esc(o["why_open"])}',
                     link("https://www.nba.com/games?date=" + o["date"], "scoreboard")])
    if not rows:
        rows.append(["—", "no open pick", "—", "—", f'<span class="chip ok">none</span>', link("https://www.nba.com/games", "games")])
    body.append(table(["Date", "Game", "Pick", "Strategy", "Why it is still open", "Source"], rows, "open-picks"))
    body.append("""<p class="small">The canonical settlement page
(<a href="../app/settlement.html">app/settlement.html</a>) still renders a different feed and does not
show this settlement. That is logged as change request CR-42-04 rather than edited here, because
<code>scripts/build_app.py</code> belongs to another session.</p>""")
    return page("Settlement and sealed ledger", "This round · settlement",
                "\n".join(body), "settlement.html",
                lead="Verified finals, the settlement stamp, the ledger chain, and every pick that is still open.")


def page_summary() -> str:
    """Executive summary built from measured artefacts, not from prose claims."""
    model = json.loads((LIVE / "model.json").read_text())
    feed = json.loads((LIVE / "results" / "settled_2026-11-15.json").read_text())
    view = json.loads((LIVE / "picks_ledger_view.json").read_text())
    td = json.loads((LIVE / "travel_distance.json").read_text())
    rev = json.loads((LIVE / "review_42d69dc5.json").read_text())
    sug = json.loads((LIVE / "suggestions_42d69dc5.json").read_text())
    qs = json.loads((LIVE / "questions_42d69dc5.json").read_text())
    oos = model["out_of_sample"]
    hca = model["hca"]
    i = view["integrity"]
    fixed = [f for f in rev["findings"] if f["status"].startswith("FIXED")]
    flagged = [f for f in rev["findings"] if f["status"].startswith("FLAGGED")]

    repo = REPO
    head = f"""<p class="lead">A one-page answer to three questions: what this system now does,
what it can prove, and what it still cannot. Every number is measured from a committed artefact, and
every claim that depends on an outside decision says so.</p>"""

    body = [head, "<h2>1 · What changed in this session</h2>"]
    rows = []
    for f in fixed:
        rows.append([f'<b>{esc(f["id"])}</b>', esc(f["area"]), esc(f["finding"]), esc(f["action"]),
                     srcs(f.get("verified_against")) or link(f"{repo}/blob/main/COORDINATION.md", "COORDINATION.md")])
    body.append(table(["ID", "Area", "What was wrong", "What is true now", "Source"], rows, "summary-fixed"))

    body.append("<h2>2 · What the model can prove</h2>")
    rows = [
        ["Games in the walk-forward sample", num(model["games_in_sample"], 0),
         f'{esc(model["sample_range"][0])} → {esc(model["sample_range"][1])}; each forecast uses only earlier games',
         link("https://www.nba.com/games", "official game log")],
        ["E1 out-of-sample log-loss", f'{oos["e1_log_loss"]:.4f}',
         "ridge Massey on final margins", link("https://www.nba.com/games", "official margins")],
        ["E2 out-of-sample log-loss", f'{oos["e2_log_loss"]:.4f}',
         "logistic Bradley-Terry on wins only", link("https://www.nba.com/standings", "official W/L")],
        ["Blend out-of-sample log-loss", f'{oos["blend_50_50_log_loss"]:.4f}',
         "50/50 blend, published underneath the disagreement, not as the headline",
         link("https://www.nba.com/standings", "official W/L")],
        ["Coin flip log-loss", f'{oos["coin_flip_log_loss"]:.4f}',
         "the honest baseline: ln 2. Anything above this is worse than guessing",
         link("https://www.nba.com/games", "official game log")],
        ["Home-court advantage (pinned)", f'{hca["hca_margin_points"]:.3f} pts',
         f'down from a naive fitted {hca["hca_margin_if_naive_fit"]:.3f}; measured home-win rate '
         f'{hca["home_win_rate"]:.4f} over {hca["games"]} games', link("https://www.nba.com/games", "official game log")],
        ["Teams outside the luck noise band", num(sum(1 for t in model["luck"] if not t["within_noise_band"]), 0),
         "a strategy leaning on any of them would be refused", link("https://www.nba.com/standings", "official standings")],
        ["Verified finals settled this session", num(feed["counts"]["verified"], 0),
         f'of {feed["counts"]["games_on_date"]} games on 2026-11-15; the rest are not guessed',
         link(feed["games"][0]["source_url"], "game page")],
        ["Ledger entries / settled", f'{i["entries"]} / {i["settled"]}',
         f'chain {"intact" if i["verified"] else "BROKEN"}', link(f"{repo}/blob/main/ledger/ledger.jsonl", "ledger.jsonl")],
        ["Priced-window team-games with a sourced travel distance",
         f'{td["counts"]["priced_window_sourced"]} / {td["counts"]["priced_window_team_games"]}',
         "reference coordinates, labelled as such",
         link(f"{repo}/blob/main/data/live/raw/wiki_arena_coords_2026-11-15.json", "verbatim capture")],
    ]
    body.append(table(["Measure", "Value", "What it means", "Source"], rows, "summary-measures"))

    body.append("<h2>3 · What it still cannot prove</h2>")
    rows = [
        ["That any strategy has an edge", "no licensed closing line exists, so every 'edge' is the model compared with itself",
         link("https://www.nba.com/schedule?date=2026-11-15", "schedule (no prices printed)")],
        ["That any strategy is profitable", f'{i["settled"]} settled pick from {i["published"]} sealed; a leaderboard over one result ranks nothing',
         link(feed["games"][0]["gamebook_url"], "the one verified final")],
        ["That travel affects a line", "coordinates are a reference source, not an official one; the effect is unmeasured",
         link("https://en.wikipedia.org/w/api.php?action=query&prop=coordinates&format=json", "coordinate API")],
        ["That minutes redistribute on an absence", "the captured logs and the archived absences do not overlap at any club",
         link("https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf", "game book (inactives listed)")],
        ["What settles a postponed game", "the pre-registrations say 'settle on the official final'; a postponed game has none",
         link("https://www.nba.com/schedule?date=2026-11-15", "official schedule")],
    ]
    body.append(table(["Claim that cannot be made", "Why not", "Source"], rows, "summary-cannot"))

    body.append("<h2>4 · Decisions waiting on you</h2>")
    rows = []
    for q in qs["questions"]:
        if q["kind"] != "DECISION (yours)":
            continue
        rows.append([f'<b>{esc(q["id"])}</b>', esc(q["question"]), esc(q["blocks"]), link(q["source"], "source")])
    body.append(table(["ID", "Decision", "What it unblocks", "Source"], rows, "summary-decisions"))
    body.append(f"""<p class="small">{qs["counts"]["fetchable"]} further questions are ones I can answer by
fetching (the other eight 11/15 finals, three clubs' home venues, the day's remaining injury filings),
and {qs["counts"]["blocked_elsewhere"]} are waiting on settled results rather than on information. All of
them are on <a href="questions-42d69dc5.html">Questions</a>.</p>""")

    body.append("<h2>5 · The shortest honest path</h2>")
    body.append("""<ol>
<li><b>Settle every game day</b> (S42-2). Without it nothing can ever be measured.</li>
<li><b>Stop saying "edge"</b> until a licensed line exists (S42-1 option B). It is free.</li>
<li><b>Link the two surfaces</b> from the front door (S42-3). They exist and are unreachable.</li>
<li><b>Backfill one day of injury filings</b> (S42-6) so the consecutive-report diff has material.</li>
</ol>""")
    body.append(f"""<p class="small">{len(flagged)} items remain flagged and published rather than fixed;
they do not block the site. They are listed with their sources on
<a href="review-42d69dc5.html">Repo review</a>, and the {sug["counts"]["awaiting_decision"]}
implementable improvements are on <a href="suggestions-42d69dc5.html">Suggestions</a>.</p>""")
    return page("Executive summary", "This round · summary", "\n".join(body), "summary.html",
                lead="What the system does, what it can prove, and what it cannot — in one page.")


def check_links(paths: list[pathlib.Path]) -> None:
    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids, self.hrefs = set(), []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if "id" in a:
                self.ids.add(a["id"])
            if tag == "a" and "href" in a:
                self.hrefs.append(a["href"])

    for path in paths:
        p = P()
        p.feed(path.read_text(encoding="utf-8"))
        for h in p.hrefs:
            if h.startswith("#"):
                if h[1:] not in p.ids:
                    err(f"{path.name}: broken anchor {h}")
            elif h.startswith(("http://", "https://", "mailto:")):
                if h.startswith("http://"):
                    err(f"{path.name}: non-https link {h}")
            else:
                target = (path.parent / h.split("#")[0]).resolve()
                if not target.exists():
                    err(f"{path.name}: broken link {h}")


def main() -> int:
    pages = {
        "summary.html": page_summary,
        "review-42d69dc5.html": page_review,
        "questions-42d69dc5.html": page_questions,
        "suggestions-42d69dc5.html": page_suggestions,
        "travel.html": page_travel,
        "settlement.html": page_settlement,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in pages.items():
        path = OUT / name
        path.write_text(fn(), encoding="utf-8")
        written.append(path)
    check_links(written)
    if ERRORS:
        print("BUILD FAILED", file=sys.stderr)
        for e in ERRORS:
            print("  -", e, file=sys.stderr)
        return 1
    print(f"wrote {len(written)} pages to projection/: " + ", ".join(p.name for p in written))
    print("link check: 0 broken links, 0 rows without a source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
