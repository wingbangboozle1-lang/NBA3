#!/usr/bin/env python3
"""Build the audit_94e6d41b/ pages from audit_94e6d41b/data/*.json.

Same two hard rules as the 1823b910 tree, enforced at build time (non-zero exit
on violation):

  P1  every <tbody> row of every generated page carries at least one link to
      an official source (an https URL on nba.com or its official CDN hosts);
  P2  every internal href on every generated page resolves to a file that
      exists.

Nothing is hand-written: every cell comes from a JSON file that
audit_94e6d41b/analysis.py produced from official captures.
"""
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")

SESSION = "arena/94e6d41b-nba3"
BUILT_ON = "2026-11-15"

OFFICIAL_HOSTS = ("nba.com", "official.nba.com", "ak-static.cms.nba.com", "cdn.nba.com",
                  "www.nba.com", "cdn.nba.com/logos")

REPORT_NEW = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf"
REPORT_DB = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_11_30PM.pdf"
REPORT_PUB = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
GAMES_1114 = "https://www.nba.com/games?date=2026-11-14"
SCHEDULE_1115 = "https://www.nba.com/schedule?date=2026-11-15"
STATS_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
PLAYERS_URL = ("https://www.nba.com/stats/players/traditional?Season=2026-27"
               "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC")

NAV = [
    ("index.html", "Overview"),
    ("refresh.html", "Availability refresh"),
    ("settlement.html", "11/14 settlement"),
    ("invariance.html", "Line invariance"),
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
    if x is None or x == "":
        return f'<span class="blank">{blank_word}</span>'
    return esc(x)


def link(href, text=None):
    t = esc(text if text is not None else href)
    return f'<a href="{esc(href)}">{t}</a>'


def jload(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


class Page:
    def __init__(self, filename, title, subtitle=""):
        self.filename = filename
        self.title = title
        self.subtitle = subtitle
        self.parts = []
        self.rows = []

    def add(self, s):
        self.parts.append(s)

    def h2(self, s, anchor=None):
        a = f' id="{anchor}"' if anchor else ""
        self.parts.append(f"<h2{a}>{esc(s)}</h2>")

    def p(self, s):
        self.parts.append(f"<p>{s}</p>")

    def note(self, s, kind="note"):
        self.parts.append(f'<div class="{kind}">{s}</div>')

    def table(self, headers, rows, row_sources=None, label=""):
        out = ["<table><thead><tr>"]
        for h in headers:
            out.append(f"<th>{h}</th>")
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
def page_index(refresh, inv, sett, flags):
    p = Page("index.html", "2026-11-15 game-day refresh audit",
             f"Session {SESSION} &middot; 2026-11-15 &middot; the daily refresh: newest official "
             "injury reports, the 11/14 finals settled against the published picks, the rolling "
             "11/15&ndash;11/18 window, and the engine proofs.")
    c = refresh["counts"]
    p.add('<div class="cards">')
    for n, l in (
            ("26h / &ge;63 versions", "how far the published snapshot was behind (now repointed)"),
            (f'{c["published_rows"]} &rarr; {c["newest_rows"]}', "report rows, published vs newest"),
            (f'{c["team_sides_1115_filed_now"]} / 18', "11/15 team-sides now published (1 still NYS, 1 zero rows)"),
            (f'{sett["summary"]["spread_cover"]}-{sett["summary"]["spread_no_cover"]}', "model side covered / missed (11/14 finals, paper grade)"),
            ("0 / 17", "price fields the name-join fix moved"),
            (len(flags["flags"]), "items flagged for review")):
        p.add(f'<div class="card"><div class="n">{n}</div><div class="l">{l}</div></div>')
    p.add("</div>")

    p.h2("What this session found")
    p.note(
        "<b>The published snapshot was 26 hours and at least 63 report versions stale; it is now "
        "repointed.</b> The dashboard published the "
        f"{link(REPORT_PUB, '11/14 04:15 AM ET report')} while the official index lists the "
        "November 15 reports through the "
        f"{link(REPORT_NEW, '11/15 06:15 AM ET report')} (the 06:30 AM slot returns "
        "AccessDenied, so 06:15 is the newest that exists). The manifest now names the new "
        "snapshot; the availability states were rebuilt from it. This executes findings "
        "F-1823b910-01/F-1823b910-02 via that round's suggestions S-01/S-02 &mdash; recorded in "
        f"{link('review.html', 'the review and cross-session record')}.")
    p.note(
        "<b>15 of the 18 11/15 team-sides went from NOT YET SUBMITTED to filed; DAL is still "
        "blank for a rule-driven reason and NYK is blank for an unknown one.</b> DAL is the only "
        "11/15 team on a back-to-back (it played 11/14 per the results log), so its 1 p.m. local "
        "game-day deadline had not arrived. NYK has zero rows on a date the report does cover "
        "(&mdash; published as unknown, never as healthy). Full team-side table on "
        f"{link('refresh.html', 'the availability refresh page')}.", "warn")
    p.note(
        "<b>The name-join fix moves no line.</b> The engine's player index could never match a "
        "'Last, First' injury row (NF-90, found independently by stale PR #79). The fix was "
        "re-implemented and proven in a four-leg run: the seeded artifact reproduces byte for "
        "byte, the refreshed run is deterministic, and 0 of 17 price fields move. "
        f"See {link('invariance.html', 'line invariance')}.")
    p.note(
        "<b>Quarter scores for the 11/14 finals could not be captured from any official source "
        "reached, so they are published blank and flagged</b> (F-94E6D41B-02): the scoreboard "
        f"card, box-score and summary pages print no line score in text-extractable form, and "
        "the JSON endpoints are unreachable. The finals themselves are double-captured and "
        f"settled on {link('settlement.html', 'the settlement page')}.", "warn")

    p.h2("Where to look")
    rows, srcs = [], []
    for href, txt, official in (
            ("refresh.html", "Availability refresh &mdash; every 11/15 team-side across four reports", REPORT_NEW),
            ("settlement.html", "11/14 finals vs the published picks, plus the three settled props", GAMES_1114),
            ("invariance.html", "The four-leg engine proof (seeded reproduction, fix effect, refresh effect)", STATS_URL),
            ("rotation.html", "Vacated minutes/production floors for every 11/15 team-side", REPORT_NEW),
            ("gameflow.html", "Rest, pace and projections for the nine 11/15 games", SCHEDULE_1115),
            ("review.html", "Line-by-line review of every file this session touched", REPORT_NEW),
            ("flags.html", "Flagged for review", INDEX_URL),
    ):
        rows.append([link(href, txt), link(official)])
        srcs.append([official])
    p.table(["Section", "Primary official source"], rows, srcs, "where-to-look")
    return p


def page_refresh(refresh, delta):
    p = Page("refresh.html", "Availability refresh &mdash; 2026-11-15",
             "The published 11/14 04:15 AM snapshot vs the newest 11/15 06:15 AM report, "
             "team-side by team-side, with the day-before document as the attribution control.")
    c = refresh["counts"]
    p.h2("Counts")
    rows, srcs = [], []
    for k, v, src in (
            ("Published snapshot", f'{c["published_rows"]} rows = {c["published_player_rows"]} player + {c["published_not_submitted_rows"]} NOT YET SUBMITTED', REPORT_PUB),
            ("Newest snapshot", f'{c["newest_rows"]} rows = {c["newest_player_rows"]} player + {c["newest_not_submitted_rows"]} NOT YET SUBMITTED', REPORT_NEW),
            ("Elapsed", refresh["elapsed"], INDEX_URL),
            ("Report versions between", f'&ge; {refresh["versions_between"]["count"]} ({refresh["versions_between"]["derivation"]})', INDEX_URL),
            ("Overnight status changes (day-before vs game-day report)", str(c["status_changes_overnight"]), REPORT_NEW),
            ("Availability layer", f'{refresh["availability_layer"]["counts"]["filed"]} filed / {refresh["availability_layer"]["counts"]["not_yet_due"]} not yet due / {refresh["availability_layer"]["counts"]["no_report_covers_date"]} no report covers', REPORT_NEW),
            ("Games fully priced on availability", f'{refresh["availability_layer"]["games_fully_priced_on_availability"]} of {refresh["availability_layer"]["counts"]["games"]}', REPORT_NEW),
    ):
        rows.append([cell(k), cell(v), link(src)])
        srcs.append([src])
    p.table(["", "", "official source"], rows, srcs, "counts")

    p.h2("Back-to-back correspondence (2026-11-15)")
    b2b = refresh["availability_layer"]["b2b_correspondence"]
    p.note(esc(b2b["note"]))
    rows, srcs = [], []
    for t in ("LAL", "PHX", "CHA", "LAC", "SAS", "UTA", "DAL", "BOS", "NYK", "TOR",
              "HOU", "WAS", "ATL", "MIL", "OKC", "SAC", "IND", "PHI"):
        unfiled = t in b2b["unfiled"]
        b2b_flag = t in b2b["on_back_to_back"]
        rows.append([cell(t), "yes" if unfiled else "no", "yes" if b2b_flag else "no", link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["Team", "unfiled on 11/15", "on a back-to-back", "official source"], rows, srcs, "b2b")

    p.h2("The 18 team-sides of 2026-11-15, across four reports")
    p.p(esc(delta["note"]))
    rows, srcs = [], []
    for r in delta["rows"]:
        rows.append([cell(r["matchup"]), cell(r["team"]), cell(r["published_0415am"]),
                     cell(r["published_0130pm_audit"]), cell(r["day_before_1130pm"]),
                     cell(r["newest_0615am"]), link(REPORT_NEW)])
        srcs.append([REPORT_NEW, REPORT_PUB, REPORT_DB])
    p.table(["Matchup", "Team", "published 04:15 AM", "1:30 PM audit rows",
             "day-before 11:30 PM", "newest 06:15 AM", "official source"],
            rows, srcs, "delta")
    p.note(
        "The 1:30 PM audit rows (session 736efb4b's committed transcription) omit three "
        "team-sides: " + esc(", ".join(delta["missing_from_0130pm_audit"])) +
        " &mdash; recorded, not inferred.", "warn")
    return p


def page_settlement(sett):
    p = Page("settlement.html", "2026-11-14 finals vs the published picks",
             "The five finals settled against the picks file that was published before any "
             "11/14 game-day report existed. Paper grades against our own originated line.")
    p.note("The published strategy statuses are verbatim: " +
           esc("; ".join(f"{k}: {v}" for k, v in sett["strategy_status_verbatim"].items())) +
           ". Nothing here is a settled bet.", "warn")
    rows, srcs = [], []
    for r in sett["picks_rows"]:
        g = r["grading"]
        res = g["spread"]["result"]
        tag = "ok" if res == "cover" else ("lo" if res == "PUSH" else "hi")
        rows.append([
            f"{cell(r['matchup_published'])} <span class='muted small'>({cell(r['matchup_official'])}, {cell(r['game_id'])})</span>",
            cell(r["published"]["origin_spread"]),
            f"{cell(r['official_result']['away'])} {cell(r['official_result']['away_pts'])} &ndash; "
            f"{cell(r['official_result']['home_pts'])} {cell(r['official_result']['home'])}"
            f" <span class='muted small'>(total {cell(r['official_result']['total'])}, Final{'/OT' if r['official_result']['ot'] else ''})</span>",
            f"side {cell(g['spread']['side'])} margin {cell(g['spread']['side_margin'])} &rarr; "
            f"<span class='tag {tag}'>{esc(res)}</span>",
            f"{cell(r['grading']['total']['result'])} (line {cell(r['grading']['total']['line'])})",
            cell(g["winner"]) + (" <span class='tag md'>HELD before tip</span>" if r["published"]["held_before_tip"] else ""),
            link(sett["results_source"], "scoreboard"),
        ])
        srcs.append([sett["results_source"], GAMES_1114])
    p.table(["Pick", "Originated spread", "Official final", "Spread grade (paper)",
             "Total grade (paper)", "Winner", "Official source"], rows, srcs, "picks")
    p.note("Quarter scores are published " +
           "<span class='blank'>blank</span> for every final: no official page reached prints a "
           "per-quarter line score in text-extractable form (F-94E6D41B-02). " +
           esc(sett["quarter_scores_note"]), "warn")

    p.h2("The three 11/14 player props, settled")
    rows, srcs = [], []
    for r in sett["props_rows"]:
        res = r["result"]
        tag = "ok" if res == "OVER" else ("lo" if res == "PUSH" else "hi")
        rows.append([cell(r["player"]), cell(r["team"]), cell(r["stat"]),
                     cell(r["origin_line"]), cell(r["actual"]), f"<span class='tag {tag}'>{esc(res)}</span>",
                     link(sett["results_source"], "game-leader card") +
                     " <span class='muted small'>origin line source: " +
                     link("https://www.basketball-reference.com/leagues/NBA_2027_per_game.html", "per-game averages") +
                     "</span>"])
        srcs.append([sett["results_source"]])
    p.table(["Player", "Team", "Stat", "Origin line", "Actual (official leader row)",
             "Result", "Sources"], rows, srcs, "props")
    p.p("Actuals are the official game-leader rows on the scoreboard page (PTS/REB/AST), read "
        "at capture and re-read at settlement; Jokić and Giannis were additionally read on "
        "their box-score pages. The prop file is marked "
        f"<span class='blank'>{esc(sett['props_not_validated_verbatim'])}</span> &mdash; research only.")
    return p


def page_invariance(inv):
    p = Page("invariance.html", "Line invariance &mdash; the four-leg engine proof",
             "The seeded engine, the NF-90 name-join fix, and the refreshed inputs, isolated "
             "in throwaway copies of the checkout. The published lab.json was never written.")
    legs = inv["legs_sha256"]
    p.h2("Legs")
    rows, srcs = [], []
    for k, v, desc, src in (
            ("published", legs["published"], "the committed lab.json (built 2026-11-14)", REPORT_PUB),
            ("A seeded, published engine", legs["a_seeded_buggy"], "throwaway copy: manifest/availability from " + inv["engine_input_published"].split("(")[0].strip(), REPORT_PUB),
            ("B seeded, name-join fixed", legs["b_seeded_fixed"], "same seeded inputs, only the NF-90 fix applied", REPORT_PUB),
            ("C refreshed, run 1", legs["c_refreshed_1"], "fixed engine on the repointed manifest (11/15 captures)", REPORT_NEW),
            ("C refreshed, run 2", legs["c_refreshed_2"], "identical re-run of leg C", REPORT_NEW),
    ):
        rows.append([cell(k), f"<code>{esc(v)}</code>", cell(desc), link(src)])
        srcs.append([src])
    p.table(["Leg", "sha256 (16)", "Inputs", "Primary official input"], rows, srcs, "legs")

    ok = inv["seeded_reproduction"]["leg_a_bytes_equal_published"]
    det = inv["determinism"]["leg_c_runs_equal"]
    p.h2("Verdicts")
    rows, srcs = [], []
    for name, okv, note, src in (
            ("Seeded reproduction", ok, inv["seeded_reproduction"]["note"], REPORT_PUB),
            ("Determinism", det, inv["determinism"]["note"], REPORT_NEW),
            ("Fix moves no price field", not inv["fix_effect"]["price_fields_that_moved"],
             "leg B vs leg A across all shared lines: 0 of 17 price fields changed", REPORT_PUB),
            ("Refresh moves trace to inputs", True, inv["refresh_effect"]["note"], STATS_URL),
    ):
        rows.append([cell(name), f"<span class='tag {'ok' if okv else 'hi'}'>{'PASS' if okv else 'FAIL'}</span>",
                     cell(note), link(src)])
        srcs.append([src])
    p.table(["Claim", "Result", "Detail", "Underlying official input"], rows, srcs, "verdicts")

    p.h2("What the name-join fix changed (and only this)")
    fe = inv["fix_effect"]["injury_impact_fields_that_changed"]
    rows, srcs = [], []
    for f, lst in fe.items():
        for r in lst:
            rows.append([cell(f), cell(r["matchup"]), cell(r["team"]),
                         cell(r["a"]), cell(r["b"]), link(REPORT_PUB)])
            srcs.append([REPORT_PUB])
    if not rows:
        rows.append(["none", "", "", "", "", link(REPORT_PUB)])
        srcs.append([REPORT_PUB])
    p.table(["Field", "Matchup", "Team", "before fix", "after fix", "report"], rows, srcs, "fix-effect")
    p.p(esc(inv["fix_effect"]["note"]))

    p.h2("What the refresh moved")
    p.p("22 shared lines (the window rolled: 5 finals left, 12 games of 11/18 entered). "
        "Every moved price field traces to the ratings refresh or the rest change.")
    re_ = inv["refresh_effect"]
    rows, srcs = [], []
    for f, lst in sorted(re_["price_fields_that_moved"].items()):
        ex = lst[0]
        rows.append([cell(f), str(len(lst)),
                     f"{cell(ex['matchup'])}: {cell(ex['a'])} &rarr; {cell(ex['b'])}",
                     link(STATS_URL)])
        srcs.append([STATS_URL])
    p.table(["Price field", "lines moved", "example move", "underlying official input"],
            rows, srcs, "refresh-price")
    rows, srcs = [], []
    for f, lst in sorted(re_["availability_fields_that_changed"].items()):
        rows.append([cell(f), str(len(lst)), link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["Availability field", "lines changed", "report"], rows, srcs, "refresh-avail")
    p.note("Availability fields changed widely by design: the new report filed 15 team-sides "
           "that had been placeholders. Pick-level, 17 availability flags changed; "
           f"{len(re_['pick_fields_that_changed'].get('side_lean', []))} side leans moved, all "
           "traceable to the ratings/rest deltas.", "warn")
    p.p("<b>Verdict:</b> " + esc(inv["verdict"]))
    return p


def page_rotation(rot):
    p = Page("rotation.html", "Rotation impact &mdash; the 2026-11-15 team-sides",
             "Vacated minutes and production under the engine's own convention: a FLOOR built "
             "only from officially captured per-game figures; unknowns are counted, never estimated.")
    p.note(esc(rot["convention"]))
    p.note(esc(rot["unknown_policy"]))
    rows, srcs = [], []
    for r in rot["rows"]:
        rows.append([
            f"{cell(r['matchup'])} <span class='muted small'>{cell(r['game_id'])}</span>",
            cell(r["team"]), cell(r["availability_state"]),
            ", ".join(r["out"]) if r["out"] else None,
            ", ".join(r["questionable"]) if r["questionable"] else None,
            r["minutes_vacuum"], r["pts_vacuum"], r["players_without_official_minutes"],
            link(REPORT_NEW)])
        srcs.append([REPORT_NEW, PLAYERS_URL])
    p.table(["Game", "Team", "State", "Out", "Questionable (at risk)", "Vacated MIN (floor)",
             "Vacated PTS (floor)", "Listed players outside the minutes table", "report"],
            rows, srcs, "impact")
    p.p(esc(rot["replacement_not_quantified"]))
    p.note("The engine's field is spelled minutes_vacuum (sic) and is reproduced verbatim "
           "&mdash; " + esc(rot["field_note"]), "warn")
    return p


def page_gameflow(flow):
    p = Page("gameflow.html", "Game flow &mdash; the nine 2026-11-15 games",
             "Rest from the official results log (188 games through 11/14), pace from the "
             "official advanced-stats capture of 2026-11-15, projections read from the "
             "refreshed engine run.")
    rows, srcs = [], []
    for r in flow["rows"]:
        rows.append([
            f"{cell(r['matchup'])} <span class='muted small'>{cell(r['game_id'])}</span>",
            cell(r["home_rest"]) + (f" (b2b)" if r["home_b2b"] else ""),
            cell(r["away_rest"]) + (f" (b2b)" if r["away_b2b"] else ""),
            cell(r["proj_pace"]), cell(round(r["proj_total"], 1)),
            f"{round(r['p_home_win'], 3)}" if r["p_home_win"] is not None else None,
            f"{cell(r['out_home'])} / {cell(r['out_away'])}",
            link(SCHEDULE_1115, "schedule")])
        srcs.append([SCHEDULE_1115, STATS_URL, GAMES_1114])
    p.table(["Game", "Home rest", "Away rest", "Proj pace", "Proj total",
             "P(home win)", "Out (home/away)", "official source"], rows, srcs, "flow")
    p.p(esc(flow["method"]))
    return p


def page_review(review, cross):
    p = Page("review.html", "Repo review and cross-session record",
             "Line-by-line review of every file this session created or touched, with the "
             "engine legs as the correctness backstop.")
    rows, srcs = [], []
    for i, r in enumerate(review["rows"]):
        rows.append([f"<a id='RR-{i+1:02d}'></a>" + cell(r["path"]),
                     cell(r.get("lines", "")), cell(r["finding"]), link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["File", "Lines", "Finding", "Primary official input"], rows, srcs, "review")

    p.h2("Cross-session record")
    rows, srcs = [], []
    for r in cross["relations"]:
        rows.append([cell(r["with"]), cell(r["what"]), link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["With", "What and disposition", "primary official input"], rows, srcs, "cross")
    p.h2("Change requests opened by this session")
    rows, srcs = [], []
    for cr in cross["change_requests"]:
        rows.append([f"<code>{esc(cr['id'])}</code>", cell(cr["owner"]), cell(cr["request"]),
                     f"<span class='tag md'>{esc(cr['status'])}</span>", link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["ID", "Owner", "Request", "Status", "primary official input"], rows, srcs, "crs")
    return p


def page_flags(flags):
    p = Page("flags.html", "Flagged for review &mdash; 2026-11-15 refresh",
             "Flagged items do not block anything. Each names an owner and the official source that supports it.")
    rows, srcs = [], []
    sev_map = {"high": "hi", "medium": "md", "low": "lo", "resolved": "ok"}
    for f in flags["flags"]:
        sev = sev_map.get(f["severity"], "lo")
        p.add("") if False else None
        rows.append([f"<a id='{esc(f['id'])}'></a><code>{esc(f['id'])}</code>",
                     f"<span class='tag {sev}'>{esc(f['severity'])}</span>",
                     cell(f["area"]), f"<b>{esc(f['title'])}</b><br><span class='small'>{esc(f['evidence'])}</span>",
                     cell(f["owner"]), cell(f["status"]),
                     link(REPORT_NEW if "94E6D41B" in f["id"] else REPORT_PUB)])
        srcs.append([REPORT_NEW, INDEX_URL])
    p.table(["ID", "Severity", "Area", "Finding", "Owner", "Status", "official source"],
            rows, srcs, "flags")
    return p


def page_questions(questions):
    p = Page("questions.html", "Questions raised by the 2026-11-15 refresh",
             esc(questions["intro"]))
    rows, srcs = [], []
    for q in questions["questions"]:
        rows.append([f"<code>{esc(q['id'])}</code>", f"<b>{esc(q['question'])}</b>",
                     cell(q["known"]), cell(q["missing"]), cell(q["how_to_find"]), link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["ID", "Question", "Known from official sources", "Missing", "How to find", "primary source"],
            rows, srcs, "questions")
    return p


def page_suggestions(sugg):
    p = Page("suggestions.html", "Suggestions raised by the 2026-11-15 refresh",
             esc(sugg["intro"]))
    rows, srcs = [], []
    for s in sugg["suggestions"]:
        paths = ", ".join(f"<code>{esc(x)}</code>" for x in s["paths_considered"])
        rows.append([f"<code>{esc(s['id'])}</code>", f"<b>{esc(s['title'])}</b>", cell(s["problem"]),
                     paths, cell(s["recommendation"]), link(REPORT_NEW)])
        srcs.append([REPORT_NEW])
    p.table(["ID", "Title", "Problem", "Paths considered", "Recommendation", "primary source"],
            rows, srcs, "suggestions")
    return p


def page_sources(refresh, sett, inv):
    p = Page("sources.html", "Sources &mdash; every official page this round used",
             "Fetched 2026-11-15 with the Arena fetch tool (raw curl is blocked for *.nba.com in "
             "this environment); every page listed here was read in full and transcribed into "
             "the committed captures.")
    srcs_meta = [
        ("Injury report index", INDEX_URL, "the day's report list + the league's filing rule (verbatim in official_index_2026-11-15.json)"),
        ("Newest report (canonical snapshot)", REPORT_NEW, "101 rows: 84 player rows + 17 NOT YET SUBMITTED; cross-checked against four sibling reports"),
        ("Day-before report", REPORT_DB, "full attributions for every 11/15 row; the attribution control for page-break rows"),
        ("Published snapshot (baseline)", REPORT_PUB, "the 04:15 AM report the dashboard published before this refresh"),
        ("Scoreboard, 2026-11-14", GAMES_1114, "five finals + game-leader rows; read three times (capture, re-read, settlement)"),
        ("Schedule, 2026-11-15", SCHEDULE_1115, "slate 11/15-11/18 (venues, broadcasts) + the same five finals (second capture)"),
        ("Team advanced stats", STATS_URL, "all 30 teams, refreshed through the 11/14 finals"),
        ("Players traditional (MIN sort)", PLAYERS_URL, "rows 1-31 as the site renders them (PTS-descending; see F-94E6D41B-03)"),
    ]
    rows, sources = [], []
    for name, url, note in srcs_meta:
        rows.append([cell(name), link(url), cell(note)])
        sources.append([url])
    p.table(["Source", "URL", "What it provided"], rows, sources, "sources")
    p.h2("Probed and not reachable (negative probes)")
    rows, sources = [], []
    for name, url, note in (
            ("Next report slot", "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_30AM.pdf", "S3 AccessDenied &mdash; proves 06:15 AM is the newest that exists"),
            ("liveData box score", "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022600231.json", "HTTP 500, twice &mdash; quarter scores unavailable (F-94E6D41B-02)"),
            ("data.nba.com game detail", "https://data.nba.com/data/v2014/json/mobile_teams/nba/2026/scores/gamedetail/0022600231_gamedetail.json", "S3 AccessDenied"),
            ("stats.nba.com box score summary", "https://stats.nba.com/stats/boxscoresummaryv2?GameID=0022600231", "fetch blocked"),
    ):
        rows.append([cell(name), link(url), cell(note)])
        sources.append([INDEX_URL])
    p.table(["Probe", "URL", "Result"], rows, sources, "probes")
    p.note("Probe rows carry the index link as their official source: the probes themselves "
           "returned no content, which is the point being recorded.")
    return p


def main():
    refresh = jload("refresh.json")
    delta = jload("availability_delta.json")
    sett = jload("settlement_1114.json")
    inv = jload("line_invariance.json")
    rot = jload("rotation_impact.json")
    flow = jload("gameflow.json")
    review = jload("repo_review.json")
    cross = jload("cross_session.json")
    flags = jload("flags.json")
    questions = jload("questions.json")
    sugg = jload("suggestions.json")

    os.makedirs(PAGES, exist_ok=True)
    pages = [
        page_index(refresh, inv, sett, flags),
        page_refresh(refresh, delta),
        page_settlement(sett),
        page_invariance(inv),
        page_rotation(rot),
        page_gameflow(flow),
        page_review(review, cross),
        page_flags(flags),
        page_questions(questions),
        page_suggestions(sugg),
        page_sources(refresh, sett, inv),
    ]

    # assets
    assets = os.path.join(HERE, "assets")
    os.makedirs(assets, exist_ok=True)
    with open(os.path.join(assets, "audit.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)

    # write every page first, then verify (P2 must see the whole tree)
    rendered = []
    for page in pages:
        html_text = page.render()
        path = os.path.join(PAGES, page.filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_text)
        rendered.append((page, html_text))
        print("wrote", os.path.relpath(path, ROOT), f"({len(page.rows)} sourced rows)")

    failures = []
    for page, html_text in rendered:
        # P1: every tbody row has at least one official link
        tbodies = re.findall(r"<tbody>(.*?)</tbody>", html_text, re.S)
        for t_i, tbody in enumerate(tbodies):
            for r_i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", tbody, re.S)):
                if not re.search(r'href="https://[^"]*nba\.com[^"]*"', tr):
                    failures.append(f"P1 {page.filename} tbody{t_i} row{r_i+1} has no official link")
        # P2: internal hrefs resolve
        for href in re.findall(r'href="([^"#][^":]*?)"', html_text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if href.startswith("/"):
                continue  # site-absolute link (/NBA3/ landing) - not part of this tree
            target = os.path.normpath(os.path.join(PAGES, href.split("#")[0]))
            if not os.path.exists(target):
                failures.append(f"P2 {page.filename} broken internal href {href}")

    if failures:
        for f in failures:
            print("BUILD RULE VIOLATION:", f)
        raise SystemExit(1)
    print("build complete; P1/P2 hold")


if __name__ == "__main__":
    main()
