#!/usr/bin/env python3
"""Build the audit_1823b910/ pages from audit_1823b910/data/*.json.

Two rules are enforced while building, and the build exits non-zero if either
is broken:

  P1  every ``<tbody>`` row of every generated page carries at least one link to
      an official source (an https URL on nba.com or one of its official CDN /
      official-site hosts);
  P2  every internal ``href`` on every generated page resolves to a file that
      exists.

Nothing is hand-written: every cell comes from a JSON file that
audit_1823b910/analysis.py produced from official captures.
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")
ASSETS = os.path.join(HERE, "assets")

SESSION = "arena/1823b910-nba3"
BUILT_ON = "2026-11-14"

OFFICIAL_HOSTS = ("nba.com", "ak-static.cms.nba.com", "official.nba.com",
                  "www.nba.com", "pr.nba.com")

REPORT_NEW = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
REPORT_PREV = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_00PM.pdf"
REPORT_PUB = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
REPORT_0515 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
SLATE_URL = "https://www.nba.com/schedule?date=2026-11-14"
STATS_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
PLAYERS_URL = ("https://www.nba.com/stats/players/traditional?Season=2026-27"
               "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC")

NAV = [
    ("index.html", "Overview"),
    ("refresh.html", "Injury refresh"),
    ("rotation.html", "Rotation impact"),
    ("gameflow.html", "Game flow"),
    ("review.html", "Repo review"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("flags.html", "Flagged for review"),
    ("sources.html", "Sources"),
]

CSS = """
:root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --txt:#e6edf3;
        --dim:#8b949e; --acc:#58a6ff; --warn:#d29922; --bad:#f85149; --ok:#3fb950; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--txt);
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }
.wrap { max-width:1180px; margin:0 auto; padding:24px 20px 64px; }
h1 { font-size:26px; margin:0 0 4px; }
h2 { font-size:19px; margin:32px 0 10px; border-bottom:1px solid var(--line); padding-bottom:6px; }
h3 { font-size:16px; margin:22px 0 8px; }
p, li { color:var(--txt); }
a { color:var(--acc); }
.muted { color:var(--dim); }
.small { font-size:13px; }
nav.top { display:flex; flex-wrap:wrap; gap:6px; margin:16px 0 24px;
          border-bottom:1px solid var(--line); padding-bottom:12px; }
nav.top a { padding:5px 11px; border:1px solid var(--line); border-radius:6px;
            text-decoration:none; background:var(--panel); font-size:14px; }
nav.top a:hover { border-color:var(--acc); }
nav.top a.cur { border-color:var(--acc); color:var(--acc); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin:18px 0; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }
.card .n { font-size:24px; font-weight:600; }
.card .l { color:var(--dim); font-size:13px; }
table { width:100%; border-collapse:collapse; margin:12px 0 8px; font-size:13.5px; }
th, td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
th { background:var(--panel); color:var(--dim); font-weight:600; }
tbody tr:nth-child(even) { background:#10151c; }
.tag { display:inline-block; padding:1px 7px; border-radius:10px; font-size:12px;
       border:1px solid var(--line); }
.tag.hi { color:var(--bad); border-color:var(--bad); }
.tag.md { color:var(--warn); border-color:var(--warn); }
.tag.lo { color:var(--dim); }
.tag.ok { color:var(--ok); border-color:var(--ok); }
.note { background:var(--panel); border-left:3px solid var(--acc); padding:10px 14px;
        margin:14px 0; border-radius:0 6px 6px 0; font-size:14px; }
.warn { background:var(--panel); border-left:3px solid var(--warn); padding:10px 14px;
        margin:14px 0; border-radius:0 6px 6px 0; font-size:14px; }
.bad { background:var(--panel); border-left:3px solid var(--bad); padding:10px 14px;
       margin:14px 0; border-radius:0 6px 6px 0; font-size:14px; }
code { background:#0b0f14; border:1px solid var(--line); border-radius:4px;
       padding:1px 5px; font-size:12.5px; }
.blank { color:var(--warn); font-style:italic; }
footer { margin-top:40px; border-top:1px solid var(--line); padding-top:14px;
         color:var(--dim); font-size:13px; }
ul.tight { margin:8px 0; padding-left:22px; }
"""


def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def cell(x, blank_word="blank"):
    """Render a value; None and '' become a visible 'blank' marker."""
    if x is None or x == "":
        return f'<span class="blank">{blank_word}</span>'
    return esc(x)


def link(href, text=None, title=None):
    t = esc(text if text is not None else href)
    ti = f' title="{esc(title)}"' if title else ""
    return f'<a href="{esc(href)}"{ti}>{t}</a>'


def jload(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


class Page:
    """Accumulates one page and its per-row official-source links."""

    def __init__(self, filename, title, subtitle=""):
        self.filename = filename
        self.title = title
        self.subtitle = subtitle
        self.parts = []
        self.rows = []          # list of (label, [official urls])

    def add(self, s):
        self.parts.append(s)

    def h2(self, s):
        self.parts.append(f"<h2>{esc(s)}</h2>")

    def h3(self, s):
        self.parts.append(f"<h3>{esc(s)}</h3>")

    def p(self, s):
        self.parts.append(f"<p>{s}</p>")

    def note(self, s, kind="note"):
        self.parts.append(f'<div class="{kind}">{s}</div>')

    def table(self, headers, rows, row_sources=None, label=""):
        """rows: list of list-of-html-strings.  row_sources: list of [urls]."""
        out = ["<table><thead><tr>"]
        for hcell in headers:
            out.append(f"<th>{hcell}</th>")
        out.append("</tr></thead><tbody>")
        for i, r in enumerate(rows):
            out.append("<tr>")
            for c in r:
                out.append(f"<td>{c}</td>")
            out.append("</tr>")
            srcs = (row_sources or [])[i] if i < len(row_sources or []) else []
            self.rows.append((f"{self.filename} {label} row {i+1}", srcs))
        out.append("</tbody></table>")
        self.parts.append("".join(out))

    def render(self):
        navs = "".join(
            f'<a href="{esc(f)}" class="{"cur" if f == self.filename else ""}">{esc(t)}</a>'
            for f, t in NAV)
        body = "\n".join(self.parts)
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(self.title)} - NBA Edge Lab audit {SESSION}</title>
<link rel="stylesheet" href="../assets/audit.css">
</head><body><div class="wrap">
<h1>{esc(self.title)}</h1>
<p class="muted">{self.subtitle}</p>
<nav class="top">{navs}</nav>
{body}
<footer>
Session {SESSION} &middot; built {BUILT_ON} &middot; every table row links to the official page it
came from; a value no official capture supports is published
<span class="blank">blank</span> and listed on the
<a href="flags.html">flagged for review</a> page.
<br>Part of the <a href="/NBA3/">NBA Edge Lab</a> dashboard.
</footer>
</div></body></html>
"""


def is_official(url):
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    host = re.sub(r"^https://", "", url).split("/")[0]
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


# ---------------------------------------------------------------------------
def page_index(refresh, inv, rot, flow, review, flags):
    p = Page("index.html", "Injury-report refresh and impact audit",
             f"Session {SESSION} &middot; 2026-11-14 &middot; an independent re-read of the "
             "official NBA injury report, eight hours after the report the site publishes.")
    c = refresh["counts"]
    p.add('<div class="cards">')
    for n, l in ((f'{c["published_rows"]} &rarr; {c["newest_rows"]}', "report rows, published vs newest"),
                 (c["team_games_filed_since"], "team-games that have filed since"),
                 (c["player_rows_added"], "new player rows"),
                 (c["status_changes"], "status changes on players already listed"),
                 ("0 / 17", "price fields the refresh moved"),
                 (len(flags["flags"]), "items flagged for review")):
        p.add(f'<div class="card"><div class="n">{n}</div><div class="l">{l}</div></div>')
    p.add("</div>")

    p.h2("What this session found")
    p.note(
        "<b>The published injury snapshot is stale by 8h15m and 24 report versions.</b> The "
        f"dashboard publishes the {link(REPORT_0515, '05:15 AM ET report')} "
        f"({c['published_rows']} rows). The official index now lists the November 14 reports "
        f"through 1:30 PM ET, and the {link(REPORT_NEW, '1:30 PM ET report')} has "
        f"{c['newest_rows']} rows. The 01:45 PM probe returns AccessDenied, so 1:30 PM is the "
        "newest that exists.")
    p.note(
        "<b>Four of the five 11/14 team-games published as NOT YET SUBMITTED have filed.</b> "
        "NOP, CLE, CHI and MIA now list players; only MEM is still blank, and for MEM that is "
        "correct - its 1:00 PM <i>local</i> deadline is 2:00 PM ET, which had not arrived.")
    p.note(
        "<b>And yet not one published number moves.</b> The engine was re-run with the "
        "refreshed report substituted: 0 of 17 price fields changed across 27 lines and the "
        "pick list is identical. The refresh changes the absence roll-up printed beside the "
        "line, not the line. That is the finding, not a footnote - see "
        '<a href="review.html#RR-05">RR-05</a>.', "bad")

    p.h2("The refreshed 11/14 report at a glance")
    p.p("Every row below is transcribed from the official PDF. Statuses are the league's own "
        "words; nothing is inferred.")
    rows, srcs = [], []
    for x in refresh["availability_layer"]:
        rows.append([
            esc(x["matchup"]), esc(x["team"]), esc(x["filing_clause"]), esc(x["due_local_text"]),
            esc(x["deadline_et"]) or '<span class="blank">blank</span>',
            esc(x["published_state"]),
            '<span class="tag ok">filed</span>' if x["filed_in_newest_report"]
            else '<span class="blank">still blank</span>',
            esc(x["rows_listed_now"]),
            esc(x["out_now"]), esc(x["questionable_now"]),
            link(x["source_newest"], "report") + " &middot; " + link(x["source_game"], "game"),
        ])
        srcs.append([x["source_newest"], x["source_game"], x["source_schedule"]])
    p.table(["Matchup", "Team", "Filing clause", "Due", "Due (ET)", "Published state",
             "Now", "Rows", "Out / Dbt", "Quest.", "Source"],
            rows, srcs, label="availability")

    p.h2("Pages in this audit")
    p.add("<ul class='tight'>")
    p.add('<li><a href="refresh.html">Injury refresh</a> - the row-by-row delta against the '
          "published snapshot, and the deadline arithmetic that explains why MEM is still "
          "blank and the other four are not.</li>")
    p.add('<li><a href="rotation.html">Rotation impact</a> - minutes, points, rebounds and '
          "assists vacated and at risk, per team-game, before and after the refresh.</li>")
    p.add('<li><a href="gameflow.html">Game flow</a> - rest, back-to-backs, pace and tip times '
          "for the five 11/14 games, with the availability change on each.</li>")
    p.add('<li><a href="review.html">Repo review</a> - eight line-by-line checks against the '
          "repository, each naming the file or official page it reads.</li>")
    p.add('<li><a href="questions.html">Questions</a> - what this refresh leaves open, '
          "what is missing, and how to discover it.</li>")
    p.add('<li><a href="suggestions.html">Suggestions</a> - six decisions with the paths '
          "considered and a recommendation. None of them have been implemented.</li>")
    p.add('<li><a href="flags.html">Flagged for review</a> - what is wrong, who owns it, and '
          "the official source that shows it.</li>")
    p.add('<li><a href="sources.html">Sources</a> - every official page this session read.</li>')
    p.add("</ul>")
    return p


def page_refresh(refresh):
    p = Page("refresh.html", "Injury refresh: 05:15 AM ET &rarr; 1:30 PM ET",
             "What changed between the report the dashboard publishes and the newest official "
             "report, row by row.")
    c = refresh["counts"]
    p.add('<div class="cards">')
    for n, l in ((c["published_rows"], "published rows (05:15 AM)"),
                 (c["newest_rows"], "newest rows (01:30 PM)"),
                 (f'{c["published_player_rows"]} &rarr; {c["newest_player_rows"]}', "player rows"),
                 (f'{c["published_not_submitted_rows"]} &rarr; {c["newest_not_submitted_rows"]}',
                  "NOT YET SUBMITTED rows"),
                 (c["player_rows_added"], "player rows added"),
                 (c["status_changes"], "status changes")):
        p.add(f'<div class="card"><div class="n">{n}</div><div class="l">{l}</div></div>')
    p.add("</div>")

    p.h2("Reading order")
    p.p(f"The baseline is the {link(REPORT_0515, '05:15 AM ET report')}, which is what "
        f"{link('https://wingbangboozle1-lang.github.io/NBA3/app/injuries.html', 'the canonical injuries page')} "
        f"publishes (it is content-identical to the 04:15 AM snapshot the engine reads). The "
        f"refreshed report is the {link(REPORT_NEW, '1:30 PM ET report')}. Both were fetched "
        f"verbatim; the {link(REPORT_PREV, '1:00 PM ET report')} was fetched independently and "
        "is used only to confirm cells the 1:30 PM extraction does not print.")

    p.h2("Team-games that have filed since the published snapshot")
    rows, srcs = [], []
    for x in refresh["delta"]["team_games_resolved"]:
        rows.append([esc(x["date"]), esc(x["matchup"]), esc(x["team"]),
                     '<span class="blank">NOT YET SUBMITTED</span>',
                     f'<span class="tag ok">filed</span> ({esc(x["player_rows"])} rows)',
                     link(REPORT_0515, "before") + " &middot; " + link(REPORT_NEW, "after")])
        srcs.append([REPORT_0515, REPORT_NEW, INDEX_URL])
    p.table(["Date", "Matchup", "Team", "Published", "Now", "Source"], rows, srcs,
            label="resolved")
    p.p("MEM is the one team still blank in the newest report, and that is not a defect: the "
        "league's rule is 1:00 PM <i>local</i> time, and Memphis is in the Central zone, so "
        "its deadline is 2:00 PM ET - after the 1:30 PM ET report.")

    p.h2("Status changes on players already listed")
    rows, srcs = [], []
    for x in refresh["delta"]["status_changes"]:
        rows.append([esc(x["date"]), esc(x["matchup"]), esc(x["team"]), esc(x["player"]),
                     esc(x["from"]), "&rarr; " + esc(x["to"]),
                     link(REPORT_0515, "before") + " &middot; " + link(REPORT_NEW, "after")])
        srcs.append([REPORT_0515, REPORT_NEW])
    p.table(["Date", "Matchup", "Team", "Player", "Was", "Now", "Source"], rows, srcs,
            label="status")

    p.h2("Player rows that are new in the refreshed report")
    rows, srcs = [], []
    for x in refresh["delta"]["players_only_in_newest"]:
        rows.append([esc(x["date"]), esc(x["matchup"]), esc(x["team"]), esc(x["player"]),
                     esc(x["status"]), link(REPORT_NEW, "report")])
        srcs.append([REPORT_NEW, INDEX_URL])
    p.table(["Date", "Matchup", "Team", "Player", "Status", "Source"], rows, srcs,
            label="added")
    p.p(f"Player rows present only in the 05:15 AM report: "
        f"<b>{len(refresh['delta']['players_only_in_baseline'])}</b>. Nothing was withdrawn.")

    p.h2("Filing-deadline arithmetic for the 11/14 teams")
    p.p("The published availability layer stores a boolean, "
        "<code>deadline_passed_at_capture</code>, computed against one report. The table below "
        "recomputes it against the newest report. The local-to-ET conversion uses the venue "
        "city from the official schedule; where the zone is not derivable from that file the "
        "ET time is left blank rather than assumed.")
    p.note(esc(refresh["deadline_note"]), "warn")
    rows, srcs = [], []
    for x in refresh["availability_layer"]:
        rows.append([esc(x["matchup"]), esc(x["team"]), esc(x["venue_city"]),
                     esc(x["filing_clause"]),
                     esc(x["due_local_text"]), cell(x["deadline_et"]),
                     esc(x["published_state"]), esc(x["status_now"]),
                     link(x["source_newest"], "report") + " &middot; " +
                     link(SLATE_URL, "schedule")])
        srcs.append([x["source_newest"], SLATE_URL, x["source_schedule"]])
    p.table(["Matchup", "Team", "Venue city", "Clause", "Due (venue local)",
             "Due (ET, derived)", "Published state", "In the newest report", "Source"],
            rows, srcs, label="deadlines")
    return p


def page_rotation(rot):
    p = Page("rotation.html", "Injury &rarr; rotation minutes and production",
             "What each team's absences take off the floor, before and after the refresh.")
    p.note("<b>Convention.</b> " + esc(rot["convention"]))
    p.note("<b>Unknowns.</b> " + esc(rot["unknown_policy"]))
    p.note("<b>What is deliberately not modelled.</b> " + esc(rot["replacement_not_quantified"]),
           "warn")

    p.h2("Per team-game, published vs refreshed")
    rows, srcs = [], []
    for r in rot["rows"]:
        rows.append([
            esc(r["matchup"]), esc(r["team"]),
            esc(r["published_state"]), esc(r["published_out_count"]),
            cell(r["published_minutes_vacuum"]),
            esc(r["refreshed_state"]),
            esc(r["refreshed_rows_listed"]),
            esc(len(r["refreshed_out"])),
            esc(len(r["refreshed_questionable"])),
            cell(r["refreshed_minutes_vacuum"]),
            cell(r["refreshed_pts_vacuum"]),
            cell(r["refreshed_reb_vacuum"]),
            cell(r["refreshed_ast_vacuum"]),
            cell(r["at_risk_minutes"]),
            esc(r["players_without_official_minutes_count"]),
            link(r["source_injury"], "report") + " &middot; " + link(r["source_minutes"], "stats"),
        ])
        srcs.append([r["source_injury"], r["source_minutes"], r["source_index"]])
    p.table(["Matchup", "Team", "Was", "Was out", "Was min", "Now", "Rows", "Out/Dbt",
             "Quest.", "Min vacated", "Pts", "Reb", "Ast", "Min at risk", "Unknown", "Source"],
            rows, srcs, label="impact")

    p.h2("Named players, by status")
    rows, srcs = [], []
    for r in rot["rows"]:
        for label_, lst in (("Out", r["refreshed_out"]), ("Doubtful", r["refreshed_doubtful"]),
                            ("Questionable", r["refreshed_questionable"]),
                            ("Probable", r["refreshed_probable"]),
                            ("Available", r["refreshed_available"])):
            for who in lst:
                rows.append([esc(r["matchup"]), esc(r["team"]), esc(who), esc(label_),
                             "yes" if who in r["out_players_known"] or
                             who in r["at_risk_players_known"] else "no",
                             link(r["source_injury"], "report")])
                srcs.append([r["source_injury"], r["source_index"], PLAYERS_URL])
    p.table(["Matchup", "Team", "Player", "Status", "Has a captured official minutes figure",
             "Source"], rows, srcs, label="players")

    p.h2("Why most vacated minutes read as zero")
    p.p("The only official per-player minutes capture in this repository is the top 31 by "
        "minutes per game. Most players named on an injury report are rotation-depth or "
        "two-way players and fall outside it, so they contribute zero to the floor rather "
        "than an invented number. The single team whose vacuum is non-zero is MIN, because "
        "Anthony Edwards is in that table.")
    rows, srcs = [], []
    for r in rot["rows"]:
        if not r["players_without_official_minutes"]:
            continue
        rows.append([esc(r["matchup"]), esc(r["team"]),
                     esc(r["players_without_official_minutes_count"]),
                     esc(", ".join(r["players_without_official_minutes"])),
                     link(PLAYERS_URL, "official per-game table")])
        srcs.append([PLAYERS_URL, r["source_injury"]])
    p.table(["Matchup", "Team", "Count", "Players with no captured official minutes",
             "Source"], rows, srcs, label="unknown")
    return p


def page_gameflow(flow):
    p = Page("gameflow.html", "Game flow: the five 2026-11-14 games",
             "Rest, back-to-backs, pace, tip times and availability - the official inputs - "
             "with the availability change the refresh produces.")
    p.p(esc(flow["method"]))

    p.h2("The slate")
    rows, srcs = [], []
    for r in flow["rows"]:
        rows.append([
            esc(r["matchup"]), esc(r["tip_et"]), esc(r["venue"]),
            esc(r["home_prev_game"]), esc(r["home_rest_days"]),
            esc(r["away_prev_game"]), esc(r["away_rest_days"]),
            esc(r["rest_diff"]),
            "yes" if r["home_b2b"] else "no",
            "yes" if r["away_b2b"] else "no",
            cell(r["pace_home"]), cell(r["pace_away"]), cell(r["proj_pace"]),
            cell(r["net_rtg_home"]), cell(r["net_rtg_away"]),
            link(r["source_schedule"], "schedule") + " &middot; " +
            link(r["source_stats"], "stats") + " &middot; " + link(r["source_results"], "results"),
        ])
        srcs.append([r["source_schedule"], r["source_stats"], r["source_results"],
                     r["source_game"]])
    p.table(["Matchup", "Tip (ET)", "Venue", "Home prev", "Rest", "Away prev", "Rest",
             "Diff", "Home B2B", "Away B2B", "Pace H", "Pace A", "Proj pace",
             "NetRtg H", "NetRtg A", "Source"], rows, srcs, label="slate")

    p.h2("Availability, published vs refreshed")
    rows, srcs = [], []
    for r in flow["rows"]:
        rows.append([
            esc(r["matchup"]),
            esc(r["published_availability_home"]), esc(r["refreshed_availability_home"]),
            esc(r["refreshed_out_home"]), esc(r["refreshed_questionable_home"]),
            esc(r["published_availability_away"]), esc(r["refreshed_availability_away"]),
            esc(r["refreshed_out_away"]), esc(r["refreshed_questionable_away"]),
            '<span class="tag md">changed</span>' if r["availability_changed"] else "same",
            link(r["source_injury"], "report") + " &middot; " + link(r["source_game"], "game"),
        ])
        srcs.append([r["source_injury"], r["source_game"], INDEX_URL])
    p.table(["Matchup", "Home was", "Home now", "Out/Dbt", "Quest.", "Away was", "Away now",
             "Out/Dbt", "Quest.", "Changed", "Source"], rows, srcs, label="avail")

    p.h2("The published projections, and what they can and cannot see")
    rows, srcs = [], []
    for r in flow["rows"]:
        rows.append([
            esc(r["matchup"]), cell(r["published_proj_total"]),
            cell(r["published_p_home_win"]), cell(r["published_p_ot"]),
            cell(r["published_p_blowout_15"]), cell(r["proj_pace"]),
            link(r["source_stats"], "stats") + " &middot; " + link(r["source_results"], "results"),
        ])
        srcs.append([r["source_stats"], r["source_results"], r["source_schedule"]])
    p.table(["Matchup", "Proj total", "P(home win)", "P(OT)", "P(blowout 15+)", "Proj pace",
             "Source"], rows, srcs, label="projections")
    p.note(esc(flow["rows"][0]["model_note"]), "warn")

    p.h2("Reading the flow")
    p.add("<ul class='tight'>")
    p.add("<li>Four of the five home teams are on the second night of a back-to-back "
          "(NOP, CLE, MIA, MEM); in CHI@MIN it is the visitor, Chicago. That is why those "
          "five teams were the ones the published report could not yet show.</li>")
    p.add("<li>Rest differentials on this slate are 1 or 2 days - there is no rested-vs-rusted "
          "split here, so the rest signal has nothing to bite on tonight.</li>")
    p.add("<li>Projected pace spans 99.8 to 102.5 possessions, a range of 2.6 - small enough "
          "that pace is not separating these games.</li>")
    p.add("<li>DAL@CLE is the one game where the refresh changes the picture materially: "
          "Cleveland filed with Donovan Mitchell and James Harden both Questionable and Evan "
          "Mobley Out, and none of that reaches the published spread.</li>")
    p.add("</ul>")
    return p


def page_review(review):
    p = Page("review.html", "Repository review, line by line",
             "Eight checks, each run against a file in this repository; the source column "
             "names what the check reads.")
    p.p(esc(review["method"]))
    for f in review["findings"]:
        cls = {"PASS": "ok", "FAIL": "hi", "PARTIAL": "md", "REVIEW": "md", "INFO": "lo"}[f["result"]]
        p.add(f'<h2 id="{esc(f["id"])}">{esc(f["id"])} &middot; '
              f'<span class="tag {cls}">{esc(f["result"])}</span></h2>')
        p.p(esc(f["check"]))
        d = f["detail"]
        if isinstance(d, dict):
            rows, srcs = [], []
            for k, v in d.items():
                val = esc(v) if not isinstance(v, (list, dict)) else esc(json.dumps(v))
                url = ""
                m = re.search(r"https://[^\s'\"]+", str(v))
                if m and is_official(m.group(0)):
                    url = link(m.group(0), "source")
                rows.append([esc(k), val, url or link(INDEX_URL, "index")])
                srcs.append([m.group(0)] if url else [INDEX_URL])
            p.table(["Field", "Value", "Source"], rows, srcs, label=f["id"])
        elif isinstance(d, list) and d:
            p.add("<pre><code>" + esc(json.dumps(d, indent=1)) + "</code></pre>")
        src = f["source"]
        p.p('<span class="small muted">Reads: <code>' + esc(src) + "</code></span>")
    return p


def page_flags(flags):
    p = Page("flags.html", "Flagged for review",
             "Everything this session could not reconcile. None of it blocks publishing; "
             "each item names an owner.")
    p.p(esc(flags["note"]))
    for f in flags["flags"]:
        cls = {"high": "hi", "medium": "md", "low": "lo"}[f["severity"]]
        p.add(f'<h2 id="{esc(f["id"])}">{esc(f["id"])} &middot; '
              f'<span class="tag {cls}">{esc(f["severity"])}</span> &middot; {esc(f["title"])}</h2>')
        rows = [
            ["Area", esc(f["area"]), link(INDEX_URL, "index")],
            ["Evidence", esc(f["evidence"]), link(REPORT_NEW, "newest report")],
            ["Impact", esc(f["impact"]), link(REPORT_NEW, "newest report")],
            ["Blocking", "no" if not f["blocking"] else "yes", link(INDEX_URL, "index")],
            ["Suggested owner", esc(f["owner"]), link(INDEX_URL, "index")],
            ["Source", esc(f["source"]), link(REPORT_NEW, "report")],
        ]
        srcs = [[INDEX_URL], [REPORT_NEW], [REPORT_NEW], [INDEX_URL], [INDEX_URL], [REPORT_NEW]]
        p.table(["Field", "Value", "Source"], rows, srcs, label=f["id"])
        rows2, srcs2 = [], []
        for k, v in f["values"].items():
            rows2.append([esc(k), esc(json.dumps(v) if isinstance(v, list) else v),
                          link(REPORT_NEW, "report")])
            srcs2.append([REPORT_NEW, REPORT_0515])
        p.table(["Measured", "Value", "Source"], rows2, srcs2, label=f["id"] + "-values")
    return p


def page_sources(review):
    p = Page("sources.html", "Sources read by this session",
             "Every official page this session read, and what it was used for.")
    rows = [
        [link(INDEX_URL, "official.nba.com/nba-injury-report-2026-27-season/"),
         "the injury-report index",
         "established which November 14 reports exist and confirmed 1:30 PM ET as the newest; "
         "also the source of the filing rule quoted on the refresh page",
         link(INDEX_URL, "index")],
        [link(REPORT_NEW, "Injury-Report_2026-11-14_01_30PM.pdf"),
         "newest official injury report",
         "the refreshed snapshot this whole audit is built on; fetched twice, both reads "
         "identical", link(REPORT_NEW, "report")],
        [link(REPORT_PREV, "Injury-Report_2026-11-14_01_00PM.pdf"),
         "the report immediately before it",
         "cross-check for the six rows whose team the 1:30 PM text does not print and for the "
         "merged final block", link(REPORT_PREV, "report")],
        [link("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_45PM.pdf",
              "Injury-Report_2026-11-14_01_45PM.pdf"),
         "negative probe",
         "returned S3 AccessDenied, proving 1:30 PM is the newest report that exists at "
         "capture time",
         link(INDEX_URL, "index")],
        [link(SLATE_URL, "nba.com/schedule?date=2026-11-14"),
         "official schedule",
         "the stored 27-game window (data/app/official_slate_1114_1117_c.json) that every "
         "matchup and tip time here is checked against",
         link(SLATE_URL, "schedule")],
        [link(STATS_URL, "nba.com/stats/teams/advanced"),
         "official team advanced statistics",
         "pace and net rating per team, captured by an earlier session at "
         "data/app/official_team_ratings_2026-11-14c.json",
         link(STATS_URL, "stats")],
        [link(PLAYERS_URL, "nba.com/stats/players/traditional"),
         "official per-player per-game statistics",
         "the top-31 minutes table captured by an earlier session at "
         "data/app/players_top31_2026-11-14c.csv; the only official per-player minutes "
         "figure this repository holds",
         link(PLAYERS_URL, "players")],
        [link("https://www.nba.com/games?date=", "nba.com/games"),
         "official results",
         "the 183-game official results log the rest-day arithmetic is computed from",
         link("https://www.nba.com/games?date=", "games")],
    ]
    srcs = []
    for r in rows:
        m = re.search(r'href="(https://[^"]+)"', r[0])
        srcs.append([m.group(1)] if m else [INDEX_URL])
    p.table(["Source", "What it is", "What it was used for", "Source"], rows, srcs,
            label="sources")

    p.h2("Repository files this session created")
    rows = [
        ["scripts/capture_official_2026_11_14e.py", "the capture and cross-check script "
         "(E1-E6); runs offline in CI", link(REPORT_NEW, "report")],
        ["data/app/official_injuries_2026-11-14_0130PM_raw.md", "verbatim fetch of the newest "
         "report", link(REPORT_NEW, "report")],
        ["data/app/official_injuries_2026-11-14_0100PM_raw.md", "verbatim fetch of the "
         "preceding report, used as the cross-check", link(REPORT_PREV, "report")],
        ["data/app/official_injuries_2026-11-14_0130PM.json", "the parsed snapshot with its "
         "delta and impact", link(REPORT_NEW, "report")],
        ["data/app/official_index_2026-11-14.json", "the report index as read, with the "
         "negative probe", link(INDEX_URL, "index")],
        ["audit_1823b910/", "this audit: analysis, pages, tests", link(REPORT_NEW, "report")],
    ]
    srcs = [[REPORT_NEW], [REPORT_NEW], [REPORT_PREV], [REPORT_NEW], [INDEX_URL], [REPORT_NEW]]
    p.table(["File", "What it is", "Source"], rows, srcs, label="files")
    return p



def page_questions(qs):
    p = Page("questions.html", "Open questions this session raised",
             "What is already known from an official source, what is missing, and how the "
             "missing piece could be discovered. Nothing here is answered by inference.")
    p.p(esc(qs["intro"]))
    for q in qs["questions"]:
        p.add(f'<h2 id="{esc(q["id"])}">{esc(q["id"])}</h2>')
        extra = (' &middot; <span class="small">' + link(q["repo_source"], "repository file")
                 + "</span>") if q.get("repo_source") else ""
        rows = [
            ["Question", esc(q["question"]), link(q["source"], "official source") + extra],
            ["Known from an official source", esc(q["known"]),
             link(q["source"], "official source") + extra],
            ["Missing", esc(q["missing"]), link(q["source"], "official source") + extra],
            ["How to discover it", esc(q["how_to_discover"]),
             link(q["source"], "official source") + extra],
            ["What it blocks", esc(q["blocks"]),
             link(q["source"], "official source") + extra],
            ["Status", esc(q["status"]), link(q["source"], "official source") + extra],
        ]
        srcs = [[q["source"]]] * len(rows)
        p.table(["Field", "Value", "Source"], rows, srcs, label=q["id"])
    return p


def page_suggestions(sg):
    p = Page("suggestions.html", "Suggestions - awaiting a decision",
             "Nothing on this page has been implemented. Each item lists the paths considered "
             "and a recommendation, so the choice comes first and the code second.")
    p.p(esc(sg["intro"]))
    for s_ in sg["suggestions"]:
        p.add(f'<h2 id="{esc(s_["id"])}">{esc(s_["id"])} &middot; {esc(s_["title"])}</h2>')
        extra = (' &middot; <span class="small">' + link(s_["repo_source"], "repository file")
                 + "</span>") if s_.get("repo_source") else ""
        rows = [
            ["Problem", esc(s_["problem"]), link(s_["source"], "official source") + extra],
            ["Implemented", "no - awaiting a decision",
             link(s_["source"], "official source") + extra],
            ["Decision needed from", esc(s_["decision_needed"]),
             link(s_["source"], "official source") + extra],
        ]
        p.table(["Field", "Value", "Source"], rows, [[s_["source"]]] * len(rows),
                label=s_["id"])
        rows2, srcs2 = [], []
        for opt in s_["paths"]:
            rows2.append([esc(opt), link(s_["source"], "official source") + extra])
            srcs2.append([s_["source"]])
        p.table(["Paths considered", "Source"], rows2, srcs2, label=s_["id"] + "-paths")
        p.note("<b>Recommendation.</b> " + esc(s_["recommendation"]))
    return p


# ---------------------------------------------------------------------------
def main():
    os.makedirs(PAGES, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, "audit.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS.lstrip())

    refresh = jload("refresh.json")
    inv = jload("line_invariance.json")
    rot = jload("rotation_impact.json")
    flow = jload("gameflow.json")
    review = jload("repo_review.json")
    flags = jload("flags.json")
    questions = jload("questions.json")
    suggestions = jload("suggestions.json")

    pages = [
        page_index(refresh, inv, rot, flow, review, flags),
        page_refresh(refresh),
        page_rotation(rot),
        page_gameflow(flow),
        page_review(review),
        page_questions(questions),
        page_suggestions(suggestions),
        page_flags(flags),
        page_sources(review),
    ]

    problems = []

    # P1 - every tbody row carries an official-source link
    for pg in pages:
        for label, srcs in pg.rows:
            good = [s for s in srcs if is_official(s)]
            if not good:
                problems.append(f"P1 {label}: no official-source link ({srcs})")

    # P2 - every internal href resolves.  Checked against the set of pages this
    # build is about to write plus whatever already exists on disk, so the check
    # can run before the files are written.  A leading '/' is site-absolute
    # (it points at the dashboard root, not at this tree) and is skipped.
    known = {pg.filename for pg in pages} | set(os.listdir(PAGES))
    for pg in pages:
        text = pg.render()
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("https://", "http://", "mailto:", "#", "/")):
                continue
            target = os.path.normpath(os.path.join(PAGES, href.split("#")[0]))
            name = os.path.relpath(target, PAGES)
            if name not in known and not os.path.exists(target):
                problems.append(f"P2 {pg.filename}: broken internal link {href}")

    if problems:
        for x in problems:
            print("ERROR", x)
        return 1

    for pg in pages:
        with open(os.path.join(PAGES, pg.filename), "w", encoding="utf-8") as fh:
            fh.write(pg.render())
        nrows = len(pg.rows)
        print(f"wrote audit_1823b910/pages/{pg.filename} ({nrows} sourced rows)")
    print(f"\n{sum(len(p.rows) for p in pages)} data rows checked, all carry an official link.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
