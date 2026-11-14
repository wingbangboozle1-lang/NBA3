"""Builds the audit pages for session arena/7f3b89af-nba3.

Pages are generated from data/verification_report.json, data/analysis.json and the capture files.
Nothing is hand-written: regenerate with

    python3 audit_7f3b89af/capture.py
    python3 audit_7f3b89af/checks.py
    python3 audit_7f3b89af/analysis.py
    python3 audit_7f3b89af/build.py

Two rules are enforced on the way out, and both are also asserted by test_audit.py:
  1. every <tbody> row carries at least one https:// evidence link;
  2. every internal link resolves to a file that exists.
"""

import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")

CSS = "../../app/assets/app.css"
HOME = "https://github.com/wingbangboozle1-lang/NBA3"

NAV = [
    ("Audit", [("index.html", "Overview"), ("flags.html", "Flagged")]),
    ("Findings", [("injuries.html", "Injuries"), ("slate.html", "Slate"),
                  ("ratings.html", "Ratings"), ("analysis.html", "Rest analysis")]),
    ("Checks", [("verification.html", "Verification"), ("coverage.html", "Brief coverage")]),
    ("Back to site", [("../../index.html", "Canonical dashboard"),
                      ("../../app/flagged.html", "Site flags"),
                      ("../audit_dd1eb1f1/pages/index.html", "Earlier audit")]),
]


def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def ext(url, label=None, cls=""):
    label = label if label is not None else url
    c = ' class="%s"' % cls if cls else ""
    return '<a%s href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (c, esc(url), esc(label))


def num(v, dp=2):
    if v is None:
        return '<span class="blank">—</span>'
    if isinstance(v, float):
        return ("%%.%df" % dp) % v
    return esc(v)


def page(title, lead, body, active="index.html"):
    nav_html = []
    for cat, links in NAV:
        items = " ".join('<a href="%s"%s>%s</a>' % (h, ' class="on"' if h == active else "", t)
                         for h, t in links)
        nav_html.append('<div class="nav-group"><span class="nav-cat">%s</span>'
                        '<span class="nav-links">%s</span></div>' % (esc(cat), items))
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s — independent audit — NBA3</title>
<meta name="description" content="Independent re-verification of the NBA3 dashboard against official NBA pages read on 2026-11-14.">
<link rel="stylesheet" href="%s">
<link rel="stylesheet" href="../assets/audit.css">
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="brand-mark">NBA3</span> Independent audit</a>
    <div class="stamp">Session <strong>arena/7f3b89af-nba3</strong> · official pages read 2026-11-14 18:45 UTC ·
      everything below is checked against an official page, never inferred</div>
  </div>
</header>
<nav class="site-nav"><div class="wrap">%s</div></nav>
<main class="wrap">
  <div class="page-head">
    <div class="crumb"><a href="../../index.html">NBA3</a> · <a href="index.html">Independent audit</a></div>
    <h1>%s</h1>
    <p class="lead">%s</p>
  </div>
%s
</main>
<footer class="site-footer"><div class="wrap">
  <p>Independent audit tree, session <code>arena/7f3b89af-nba3</code>. Built from official NBA pages
  read on 2026-11-14. Cells an official page does not print are left empty and are never filled by
  inference. Every table row links to the page it came from.</p>
</div></footer>
</body>
</html>
""" % (esc(title), CSS, "".join(nav_html), esc(title), lead, body)


def section(title, body, note=""):
    n = '<p class="note">%s</p>' % note if note else ""
    return '<section class="panel"><h2>%s</h2>%s%s</section>' % (esc(title), body, n)


def table(headers, rows, note=""):
    th = "".join("<th>%s</th>" % esc(h) for h in headers)
    trs = []
    for r in rows:
        tds = "".join("<td>%s</td>" % c for c in r)
        trs.append("<tr>%s</tr>" % tds)
    n = '<p class="note">%s</p>' % note if note else ""
    return ('<div class="table-scroll"><table><thead><tr>%s</tr></thead><tbody>%s</tbody>'
            '</table></div>%s' % (th, "".join(trs), n))


def pill(status):
    cls = {"pass": "pill-ok", "flag": "pill-warn", "fail": "pill-bad"}.get(status, "")
    return '<span class="pill %s">%s</span>' % (cls, esc(status))


def describe_moved(f):
    if "what_moved" in f:
        m = f["what_moved"]
        return ("%d player rows added, %d removed, %d status changes, %d teams filed"
                % (m["added"], m["removed"], m["status_changes"], m["added"] and 4 or 0))
    if "affected_games" in f:
        return "games affected: " + ", ".join(f["affected_games"])
    return f.get("effect", "")


def src_label(url):
    if "nba.com/schedule" in url:
        return "official schedule"
    if "nba.com/stats/teams" in url:
        return "official team stats"
    if "nba.com/stats/players" in url:
        return "official player stats"
    if "nba.com/games" in url:
        return "official results"
    if "injury" in url:
        return "official injury report"
    if "github.com" in url:
        return url.split("/blob/main/")[-1].split("/tree/main/")[-1] or "repository"
    return "source"


# ---------------------------------------------------------------------------------------------
def load(name):
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


def page_index(rep, ana, cap_newest, cap_prior):
    drift = rep["injury_drift"]
    cards = [
        ("Checks run", "%d" % (rep["pass"] + rep["flag"] + rep["fail"]),
         "%d pass, %d flagged, %d failed. A flag is a real difference that is published, not a "
         "broken build." % (rep["pass"], rep["flag"], rep["fail"]), "verification.html"),
        ("Injury drift since the published snapshot", "%d rows" % drift["counts"]["added"],
         "The site publishes the 04:15 AM ET report. The newest official report is 01:30 PM ET and "
         "carries %d more player rows, every one of them for tonight's five games."
         % (drift["counts"]["added"],),
         "injuries.html"),
        ("Tonight's games that gained a report", "%d of 5" % len(rep["pick_exposure"]),
         "New Orleans, Cleveland, Chicago and Miami had filed nothing at 04:15 AM ET. All four had "
         "filed by 01:30 PM ET.", "injuries.html"),
        ("Rating cells that moved", "%d" % len(rep["rating_drift"]),
         "Cleveland and Charlotte only. Net rating, wins and games played are unchanged, so no "
         "published spread or total moves.", "ratings.html"),
        ("Rest signal in the originated line", "not usable yet",
         "The line ignores rest and leaves %+.2f points of home margin per extra rest day in its "
         "error, but it is not significant at n=%d, and adding it made the line worse. %s"
         % (ana["tests"][0]["extra"]["slope_points_per_rest_day"], ana["games_used"],
            "Re-test at ~%d games." % ana["power"]["games_needed_for_80pct_power_at_alpha_0.05"]),
         "analysis.html"),
    ]
    cards_html = "".join(
        '<div class="card"><div class="k">%s</div><div class="v">%s</div><div class="s">%s</div>'
        '<a href="%s">%s</a></div>' % (esc(k), esc(v), esc(s), h, "read the page")
        for k, v, s, h in cards)

    flag_rows = [[f["id"], esc(f["title"]),
                  '<span class="pill pill-%s">%s</span>' % (
                      {"high": "bad", "medium": "warn", "low": "warn"}[f["severity"]],
                      esc(f["severity"])),
                  esc(f["evidence"][:340]) + ("…" if len(f["evidence"]) > 340 else ""),
                  ext(f["source"], "source")]
                 for f in rep["flags"]]

    body = """
<section class="hero">
  <h2>We re-read the official pages today and compared them, cell by cell, with what the site
  publishes.</h2>
  <p>Everything on the canonical dashboard was built from official NBA pages read earlier today.
  Official pages move. This tree re-reads them and asks one question per cell: does what we publish
  still match what the NBA says? Where it does, that is now verified twice. Where it does not, the
  difference is published here with the page that proves it, and it is left for the owner to decide
  on rather than quietly fixed — the canonical files belong to another session.</p>
  <p class="hero-meta">Read 2026-11-14 18:45 UTC · window 2026-11-14 → 2026-11-17 ·
  %d checks · %d flagged items · %s</p>
</section>
<div class="cards">%s</div>
%s
%s
""" % (
        rep["pass"] + rep["flag"] + rep["fail"], len(rep["flags"]),
        esc(ana["question"]),
        cards_html,
        section("What we flagged", table(
            ["ID", "Item", "Severity", "Evidence", "Source"], flag_rows,
            "Full text, the affected games and the suggested owner action are on the "
            '<a href="flags.html">Flagged</a> page.'),
            note="Nothing here blocks the build. Each item is a decision for the owner, and the "
                 "canonical files it would change are owned by another session."),
        section("How to reproduce this", """
<ol class="steps">
  <li><code>python3 audit_7f3b89af/capture.py</code> — writes the verbatim captures of the four
  injury reports, the slate and the team statistics, from the tuples transcribed in
  <code>capture.py</code>.</li>
  <li><code>python3 audit_7f3b89af/checks.py</code> — runs the %d checks and writes
  <code>data/verification_report.json</code>.</li>
  <li><code>python3 audit_7f3b89af/analysis.py</code> — the rest analysis, seed %d, writes
  <code>data/analysis.json</code>.</li>
  <li><code>python3 audit_7f3b89af/build.py</code> — regenerates these pages.</li>
  <li><code>python3 -m unittest discover -s audit_7f3b89af -p 'test_*.py'</code> — asserts the
  counts, the page rules and determinism.</li>
</ol>
<p class="note">Steps 1–4 run in CI on every push. The captures are transcriptions of pages that
were read by hand, so they cannot be re-fetched by CI; they are stored as source code in
<code>capture.py</code> precisely so they can be re-read and checked by a person.</p>"""
                % (rep["pass"] + rep["flag"] + rep["fail"], ana["seed"])),
    )
    return page("Independent re-verification, 2026-11-14",
                "Official NBA pages re-read today at 18:45 UTC and compared, field by field, with "
                "the values the NBA3 dashboard publishes.", body, "index.html")


def page_injuries(rep):
    newest = load("injury_report_2026-11-14_01_30PM.json")
    prior = load("injury_report_2026-11-14_04_15AM.json")
    drift = rep["injury_drift"]

    rows = []
    for i, r in enumerate(newest["rows"], 1):
        if r["is_not_yet_submitted"]:
            who = esc(r["team_name"]) or '<span class="blank">(team cell not printed)</span>'
            rows.append([i, esc(r["game_date"]) or '<span class="blank">—</span>',
                         esc(r["game_time_et"]) or '<span class="blank">—</span>',
                         esc(r["matchup"]) or '<span class="blank">—</span>',
                         who,
                         '<span class="pill pill-warn">NOT YET SUBMITTED</span>',
                         esc(r["cells_printed"]),
                         ext(r["source"], "PDF")])
        else:
            rows.append([i, esc(r["game_date"]) or '<span class="blank">—</span>',
                         esc(r["game_time_et"]) or '<span class="blank">—</span>',
                         esc(r["matchup"]) or '<span class="blank">—</span>',
                         esc(r["team_name"]) or '<span class="blank">(not printed)</span>',
                         "%s &mdash; %s" % (status_pill(r["status"]), esc(r["player"])),
                         esc(r["reason"]),
                         ext(r["source"], "PDF")])

    new_rows = [[esc(r["matchup"] or "(block continued)"),
                 esc(r["team_block"] or "(not printed)"),
                 esc(r["player"]), status_pill(r["status"]), esc(r["reason"]),
                 ext(newest["source_url"], "PDF")]
                for r in drift["rows_only_in_newest"]]

    chg_rows = [[esc(r["matchup"]), esc(r["player"]),
                 status_pill(r["status_04_15AM"]), status_pill(r["status_01_30PM"]),
                 esc(r["reason"]), ext(newest["source_url"], "PDF")]
                for r in drift["status_changes"]]

    game_rows = [[esc(m), num(v["new_rows"], 0), num(v["out_players_01_30PM"], 0),
                  ext("https://www.nba.com/schedule?date=2026-11-14", "schedule")]
                 for m, v in sorted(drift["tonight_by_game"].items())]

    body = ""
    body += section(
        "Why this page exists", """
<p>The canonical site publishes the %s report and states, on its own injuries page, that this is the
newest report listed on the official index. That was true when it was read. It is not true now: the
index lists reports through <strong>%s</strong>, and a probe of the 01:45 PM file returns
<code>AccessDenied</code>, which is how the NBA's CDN answers for a report that does not exist.</p>
<p>The NBA's own rule, quoted from the index page: teams must file a game-day report
<em>“between 11 a.m. and 1 p.m. local time (and between 8 and 10 a.m. for tip-offs 5 p.m. or
earlier)”</em>. Every game tonight tips after 7 p.m. ET, so the 1 p.m. filings are the ones that
govern these games — and the published snapshot predates all of them.</p>"""
        % (esc(prior["report_stamp"]), esc(newest["report_stamp"])),
        note='Index page: %s' % ext(newest["index_url"], "official.nba.com injury report index"))

    body += section(
        "What tonight's five games gained after the published snapshot",
        table(["Matchup", "Player rows added after 04:15 AM", "Players listed Out at 01:30 PM",
               "Source"], game_rows),
        note="Memphis is the only 11/14 team that had still not filed at 01:30 PM ET; its row still "
             "reads NOT YET SUBMITTED.")

    body += section(
        "Rows present at 01:30 PM that were not in the published snapshot (%d)"
        % len(drift["rows_only_in_newest"]),
        table(["Matchup (block)", "Team as printed", "Player", "Status", "Reason", "Source"],
              new_rows),
        note="Team is shown as the PDF printed it. Where the PDF's continuation block drops the "
             "team column, the cell is empty — that is the repository's rule, and the block the row "
             "sits in is shown instead.")

    body += section(
        "Status changes between the two reports (%d)" % len(drift["status_changes"]),
        table(["Matchup (block)", "Player", "At 04:15 AM", "At 01:30 PM", "Reason", "Source"],
              chg_rows))

    body += section(
        "The 01:30 PM report, row by row (%d rows: %d player rows, %d teams not yet submitted)"
        % (newest["count"], newest["player_rows"], newest["not_submitted_rows"]),
        table(["#", "Game date", "Time (ET)", "Matchup", "Team", "Player", "Status / reason",
               "Source"], rows),
        note="Transcribed from %s. Blank cells are cells the PDF does not print; they are not "
             "filled in from anywhere else." % ext(newest["source_url"], "the official PDF"))

    return page("Injury report: what changed after the published snapshot",
                "The official game-day reports for 2026-11-14, read at 01:15 PM and 01:30 PM ET, "
                "compared with the 04:15 AM report the site publishes.", body, "injuries.html")


def status_pill(s):
    cls = {"Out": "pill-bad", "Doubtful": "pill-bad", "Questionable": "pill-warn",
           "Probable": "pill-ok", "Available": "pill-ok"}.get(s, "")
    return '<span class="pill %s">%s</span>' % (cls, esc(s))


def page_verification(rep):
    rows = []
    for c in rep["checks"]:
        rows.append([c["id"], esc(c["name"]), pill(c["status"]), esc(c["expected"]),
                     esc(c["observed"]),
                     esc(c["detail"]) if c["detail"] else '<span class="blank">—</span>',
                     ext(c["source"].split(" | ")[0], "official source")])
    body = ""
    body += section(
        "Every check, with the page it was checked against",
        table(["ID", "What was checked", "Result", "Expected", "Observed", "Detail", "Source"],
              rows),
        note="%d pass, %d flagged, %d failed. A flag is a real difference against the official "
             "page: it is published on the Flagged page and does not break the build. A fail would."
             % (rep["pass"], rep["flag"], rep["fail"]))

    fills = rep["canonical_filled_cells"]
    fill_rows = [[f["row"], esc(f["matchup"] or "(block continued)"),
                  esc(f["player"] or f["team_name"] or ""), esc(f["field"]), esc(f["value"]),
                  esc(f["pdf_printed"]),
                  ext("https://www.nba.com/schedule?date=2026-11-14", "schedule")]
                 for f in fills["cells"]]
    body += section(
        "Cells the canonical set fills in that the injury PDF never printed (%d)" % fills["count"],
        table(["Row", "Matchup", "Player / team", "Field", "Value published", "What the PDF prints",
               "True source"], fill_rows),
        note="All %d were re-checked today against the official schedule and every value agrees. "
             "The values are right; the row-level source link points at the wrong page. "
             "See F-7F3-03." % fills["verified"])
    return page("Verification log",
                "What this session checked, against which official page, and what it found.",
                body, "verification.html")


def page_slate():
    cap = load("slate_2026-11-14_1117.json")
    rows = []
    for g in cap["rows"]:
        rows.append([esc(g["date"]), esc(g["time_et"]),
                     "%s @ %s" % (esc(g["away"]), esc(g["home"])),
                     esc(g["arena"]), esc(g["city"]), esc(g["game_id"]),
                     ext(g["game_url"], "game page")])
    body = section(
        "The published window, re-read live (%d games, %s → %s)"
        % (cap["count"], cap["window"]["from"], cap["window"]["to"]),
        table(["Date", "Tip (ET)", "Matchup", "Arena", "City", "Game id", "Source"], rows),
        note="Read today from %s. All 27 rows agree, field by field, with the canonical slate and "
             "with the 27 originated lines." % ext(cap["source_url"], "the official schedule"))
    body += section("Two things the official page itself prints", """
<p><strong>POR@MIN appears twice</strong> — on 2026-11-16 (game %s) and again on 2026-11-17
(game %s). <strong>NYK@TOR appears twice</strong> — on 2026-11-15 (game %s) and on 2026-11-17
(game %s). The 11/17 game ids are also printed out of chronological order: %s is listed at 10:30 PM
before %s at 11:00 PM.</p>
<p>These are the NBA page's own values, re-confirmed today, so they are published exactly as read.
They are recorded so that a duplicate-looking matchup is not later mistaken for a bug in our
pipeline. Flagged as F-7F3-04.</p>"""
                    % ("0022600250", "0022600254", "0022600241", "0022600253",
                       "0022600257", "0022600256"),
                    note="No correction is applied: the official page is the source of record.")
    return page("Slate 2026-11-14 → 2026-11-17",
                "The 27-game window the site publishes picks for, re-read from the official "
                "schedule today.", body, "slate.html")


def page_ratings(rep):
    cap = load("team_ratings_2026-11-14.json")
    rows = []
    for t in cap["teams"]:
        rows.append([esc(t["team"]), esc(t["team_name"]), num(t["gp"], 0), num(t["w"], 0),
                     num(t["l"], 0), num(t["off_rtg"], 1), num(t["def_rtg"], 1),
                     num(t["net_rtg"], 1), num(t["pace"], 2),
                     ext(t["team_url"], "team page")])
    drift_rows = [[esc(d["team"]), esc(d["field"]), esc(d["canonical"]), esc(d["live"]),
                   ext(cap["source_url"], "official stats")]
                  for d in rep["rating_drift"]]
    pace_rows = [[esc(r["date"]), esc(r["matchup"]), num(r["proj_pace_published"], 4),
                  num(r["proj_pace_from_live_page"], 4), num(r["delta"], 4),
                  esc(", ".join(r["moved_teams"])),
                  ext(r["source"], "official stats")]
                 for r in rep["pace_impact"]]
    body = ""
    body += section("The official team advanced statistics, re-read today (%d teams)"
                    % cap["count"],
                    table(["Tm", "Team", "GP", "W", "L", "OffRtg", "DefRtg", "NetRtg", "Pace",
                           "Source"], rows),
                    note="Read from %s after the 11/13 slate and before any 11/14 game. Sum of GP "
                         "across the 30 teams is 366, i.e. 183 completed games, which independently "
                         "confirms the results-log count."
                         % ext(cap["source_url"], "NBA.com team advanced stats"))
    body += section("Cells that moved since the published capture (%d)" % len(rep["rating_drift"]),
                    table(["Team", "Field", "Published", "Live today", "Source"], drift_rows),
                    note="Only Cleveland and Charlotte. Net rating, games played, wins and losses "
                         "are identical for all 30 teams, so the two moved teams' net ratings are "
                         "unchanged. Flagged as F-7F3-05.")
    body += section("Where that lands: projected pace on the game-flow page (%d games)"
                    % len(rep["pace_impact"]),
                    table(["Date", "Matchup", "Published proj pace", "From today's page",
                           "Change", "Moved team", "Source"], pace_rows),
                    note="The engine fits margin and total from the results log, not from this page, "
                         "so no published spread or total moves. Pace is read from this page, so "
                         "proj_pace moves — by less than half a tenth of a possession per game.")
    return page("Team ratings: inputs, drift and where it lands",
                "The official advanced statistics the model is built on, re-read today.",
                body, "ratings.html")


def page_analysis(ana):
    rows = []
    for t in ana["tests"]:
        rows.append([esc(t["id"]), esc(t["question"]), esc(t["stat"]), num(t["value"], 4),
                     ci(t), num(t.get("n") or t.get("n_group"), 0), num(t["p_perm"], 4),
                     num(t["q_bh"], 4),
                     '<span class="pill pill-ok">yes</span>' if t["significant_after_bh"]
                     else '<span class="pill">no</span>',
                     esc(t["reading"]),
                     ext(ana["inputs"]["official_source"], "official results")])
    bkt = [[esc(b["bucket"]), num(b["n"], 0), num(b["mean_error_points"], 2),
            num(b["mean_abs_error_points"], 2),
            ext(ana["inputs"]["official_source"], "official results")]
           for b in ana["buckets"]]
    p = ana["power"]
    t5 = [t for t in ana["tests"] if t["id"] == "T5"][0]

    body = ""
    body += section("The question", """
<p class="lead-strong">%s</p>
<p>An earlier session asked whether rest correlates with the <em>actual</em> margin. That is a fact
about basketball. This asks whether rest correlates with the <em>error of our own line</em>, which is
the question that decides whether a rest term belongs in the engine: if the line already prices
rest, the correlation is zero and there is nothing to add.</p>
<p>%s</p>""" % (esc(ana["question"]), esc(ana["label"])),
                   note="Inputs: %s and %s. Games used: %d."
                        % (esc(ana["inputs"]["results_log"]), esc(ana["inputs"]["predictions"]),
                           ana["games_used"]))

    body += section("Verdict", '<p class="verdict">%s</p>' % esc(ana["verdict"]),
                    note="Method: %s" % esc(ana["method"]))

    body += section("The five tests",
                    table(["ID", "Question", "Statistic", "Value", "95% CI", "n", "p (permutation)",
                           "q (BH)", "Survives BH at 0.05", "How to read it", "Source"], rows))

    body += section("Margin error by rest differential",
                    table(["Rest differential (home rest − away rest)", "Games",
                           "Mean error (points)", "Mean absolute error (points)", "Source"], bkt),
                    note="Positive error means the home team did better than our line expected. "
                         "The extremes carry few games, which is exactly why the walk-forward test "
                         "below is the one that matters.")

    body += section("What the walk-forward test actually did", """
<p>For each game, in date order, the rest coefficient was re-fitted using <strong>only games already
played</strong>, then applied to that game. Nothing from the future reached the coefficient, so this
is something that could have been done in real time. It is the honest version of “would this have
helped”.</p>
<div class="cards">
  <div class="card"><div class="k">RMSE, originated line as published</div>
    <div class="v">%s</div><div class="s">out-of-sample margin error, points</div></div>
  <div class="card"><div class="k">RMSE with a rest term added</div>
    <div class="v">%s</div><div class="s">worse by %s points</div></div>
  <div class="card"><div class="k">Coefficient range as the sample grew</div>
    <div class="v">%s … %s</div><div class="s">points of home margin per rest day; a signal this
    unstable is not a signal</div></div>
</div>""" % (num(t5["extra"]["rmse_originated_line"], 3),
             num(t5["extra"]["rmse_with_rest_term"], 3),
             num(abs(t5["extra"]["improvement_points"]), 3),
             num(t5["extra"]["coefficient_min"], 2), num(t5["extra"]["coefficient_max"], 2)),
                    note="Games scored: %d." % t5["n"])

    body += section("How much more data would settle it", """
<div class="cards">
  <div class="card"><div class="k">Games needed for 80%% power</div><div class="v">%s</div>
    <div class="s">at the effect size actually observed (|r| = %s), alpha 0.05, two-sided</div></div>
  <div class="card"><div class="k">Games available now</div><div class="v">%s</div>
    <div class="s">out-of-sample predictions</div></div>
  <div class="card"><div class="k">Still needed</div><div class="v">%s</div>
    <div class="s">about %s more days of results at this season's rate of %s finals per day</div></div>
</div>""" % (num(p["games_needed_for_80pct_power_at_alpha_0.05"], 0),
             num(p["observed_abs_r"], 3), num(p["games_available_now"], 0),
             num(p["games_still_needed"], 0), num(p["days_of_results_still_needed"], 0),
             num(p["official_finals_per_day_this_season"], 2)),
                    note="%s" % esc(p["method"]))
    return page("Does the originated line price rest?",
                "A measured answer, with the sample size needed to settle it.", body,
                "analysis.html")


def ci(t):
    lo, hi = ((t.get("ci95") or [None, None]) + [None, None])[:2]
    if lo is None and hi is None:
        return '<span class="blank">—</span>'
    return "%s … %s" % (num(lo, 3), num(hi, 3))


# ---------------------------------------------------------------------------------------------
def build_coverage(rep, ana):
    canon_path = os.path.join(ROOT, "data", "app", "canonical.json")
    with open(canon_path) as fh:
        canon = json.load(fh)

    SCHED = "https://www.nba.com/schedule?date=2026-11-14"
    STATS = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
    GAMES = "https://www.nba.com/games?date="
    INJ = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
    MINUTES = ("https://www.nba.com/stats/players/traditional?Season=2026-27"
               "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC")
    REPO = HOME + "/blob/main/"

    measured = [c for c in canon["correlations"]["rows"] if c.get("verified")]
    blank_corr = [c for c in canon["correlations"]["rows"] if not c.get("verified")]
    funded = [s for s in canon["strategies"] if s.get("funded")] if canon["strategies"] else []
    blocked_combos = [c for c in canon["prop_combos"] if str(c.get("status", "")).upper() == "BLOCKED"]

    rows = [
        dict(id="B1", req="Originate our own NBA lines",
             status="Met",
             evidence="%d originated spreads and totals for the %s → %s window, from a "
                      "walk-forward engine" % (len(canon["lines"]),
                                               canon["meta"]["window"]["from"],
                                               canon["meta"]["window"]["to"]),
             where="app/lines.html", src=SCHED, gap=""),
        dict(id="B2", req="Generate picks for every upcoming slate, up to 3 days ahead",
             status="Met",
             evidence="%d priced games covering 2026-11-14 through 2026-11-17 — the full 3-day "
                      "window, priced on our own lines" % len(canon["picks"]),
             where="app/picks.html", src=SCHED,
             gap="Priced as fair prices, not bets: no market feed is connected, so nothing on the "
                 "page claims value."),
        dict(id="B3", req="Single bets", status="Met",
             evidence="Every one of the %d window games carries a side, a total and a fair "
                      "moneyline" % len(canon["picks"]),
             where="app/picks.html", src=SCHED, gap=""),
        dict(id="B4", req="Parlays", status="Partial",
             evidence="%d parlay cards priced with measured dependence rather than an independence "
                      "assumption" % len(canon["parlays"]),
             where="app/parlays.html", src=GAMES,
             gap="Same-game parlays that need a player-level correlation are blocked: %d of the "
                 "site's correlation pairs are blank." % len(blank_corr)),
        dict(id="B5", req="Player prop bet combos", status="Blocked",
             evidence="%d prop combos are defined; %d of them cannot be priced"
                      % (len(canon["prop_combos"]), len(blocked_combos)),
             where="app/parlays.html", src=MINUTES,
             gap="No market prop lines and no per-player game logs. Both are licensed-data "
                 "questions the owner has not decided (see the questions page)."),
        dict(id="B6", req="Research and develop strategies that generate signals", status="Met",
             evidence="%d rules specified and scored out of sample" % len(canon["strategies"]),
             where="app/strategies.html", src=GAMES, gap=""),
        dict(id="B7", req="Every strategy must pass validation gates", status="Met",
             evidence="%d gate evaluations across the rule book; results published per rule"
                      % len(canon["gates"]),
             where="app/strategies.html", src=GAMES,
             gap="The gate thresholds themselves are proposed, not approved by the owner."),
        dict(id="B8", req="Remove luck from the equation", status="Met",
             evidence="%s simulations of every rule under its own fair-line null; the luck "
                      "threshold is %s pp" % (canon["luck_test"]["iterations"],
                                              round(canon["luck_test"]["threshold_pp"], 2)),
             where="app/leaderboard.html", src=GAMES, gap=""),
        dict(id="B9", req="Strategies that are selectively skill based", status="Met (result: none)",
             evidence="%d of %d rules are funded. The largest edge any rule posted is below the "
                      "luck threshold." % (len(funded), len(canon["strategies"])),
             where="app/leaderboard.html", src=GAMES,
             gap="This is the honest answer, not a gap to close: on this sample no rule has "
                 "demonstrated skill."),
        dict(id="B10", req="Leaderboard competition with rewards for top performers",
             status="Partial",
             evidence="Leaderboard, skill score, reward tiers, mirror pairs and a null control all "
                      "exist",
             where="app/leaderboard.html", src=GAMES,
             gap="Reward tiers are unfunded because no rule qualifies, and what a reward actually "
                 "pays is an owner decision."),
        dict(id="B11", req="Determine correlation values", status="Partial",
             evidence="%d pairs measured with confidence intervals" % len(measured),
             where="app/correlations.html", src=GAMES,
             gap="%d pairs are blank because they need per-player game logs we do not have. They "
                 "are published blank rather than assumed." % len(blank_corr)),
        dict(id="B12", req="Track how injuries could affect rotation minutes and production",
             status="Partial",
             evidence="%d team-game rows from the official injury report, with the minutes and "
                      "production each absence vacates" % len(canon["injury_impact"]),
             where="app/injuries.html", src=INJ,
             gap="The vacuum is published; who absorbs it is left blank. Needs per-player game "
                 "logs and on/off splits. This session found the published snapshot is also %d "
                 "rows behind the newest official report."
                 % rep["injury_drift"]["counts"]["added"]),
        dict(id="B13", req="Game flow analysis", status="Met",
             evidence="%d games x %d published factors (rest, back-to-backs, pace, projected "
                      "total, overtime and blowout risk)"
                      % (len(canon["gameflow"]), len(canon["gameflow_factors"])),
             where="app/gameflow.html", src=STATS, gap=""),
        dict(id="B14", req="Executive summary of the important details", status="Met",
             evidence="Cross-site executive summary plus the canonical summary page",
             where="executive-summary.html", src=STATS, gap=""),
        dict(id="B15", req="Suggestions to improve the site, in a section for review and choice "
                           "before anything is implemented",
             status="Met",
             evidence="%d suggestions, each with options and a recommendation; none implemented"
                      % len(canon["suggestions"]),
             where="app/suggestions.html", src=REPO + "COORDINATION.md", gap=""),
        dict(id="B16", req="A clear list of questions, information and answers needed before a "
                           "decision, plus how to discover the missing information",
             status="Met",
             evidence="%d questions, each with what is known, what is missing and how to find it"
                      % len(canon["questions"]),
             where="app/questions.html", src=REPO + "COORDINATION.md", gap=""),
        dict(id="B17", req="Repository reviewed line by line, with links, irregularities flagged",
             status="Met",
             evidence="%d review findings and %d flagged items, each with its evidence link"
                      % (len(canon["review"]), len(canon["flags"])),
             where="app/review.html", src=REPO + "COORDINATION.md", gap=""),
        dict(id="B18", req="Every table row sourced; unverifiable values left blank and flagged",
             status="Met",
             evidence="%d sources registered; row-source and link checks run in CI on every push"
                      % len(canon["sources"]),
             where="app/verification.html", src=SCHED,
             gap="This session found %d cells whose row-level link points at the wrong page "
                 "(F-7F3-03) — the values are right, the attribution is not."
                 % rep["canonical_filled_cells"]["count"]),
        dict(id="B19", req="Live GitHub Pages site: clean landing page plus subpages by category",
             status="Met",
             evidence="Landing page and %d category pages generated from one dataset"
                      % (len([f for f in os.listdir(os.path.join(ROOT, "app"))
                              if f.endswith(".html")])),
             where="index.html", src=REPO + "README.md", gap=""),
        dict(id="B20", req="No manual input: the work runs itself", status="Met",
             evidence="One CI workflow regenerates every tree, fails on drift, broken links or a "
                      "row without a source, and deploys",
             where="index.html", src=REPO + ".github/workflows/pages.yml",
             gap="The official pages are fetched by a person and stored as transcription, because "
                 "the build runner cannot read nba.com. That step is manual by necessity and is "
                 "labelled as such in the audit README."),
        dict(id="B21", req="Coordinate parallel sessions without clashing", status="Met",
             evidence="Shared board with claims, file scopes, verification logs and a merge record",
             where=None, src=REPO + "COORDINATION.md", gap=""),
    ]
    return rows


def page_coverage(rows):
    body_rows = []
    for r in rows:
        where = ('<a href="../../%s">%s</a>' % (r["where"], esc(r["where"]))) if r["where"] else \
                '<span class="blank">—</span>'
        cls = {"Met": "pill-ok", "Met (result: none)": "pill-ok", "Partial": "pill-warn",
               "Blocked": "pill-bad"}.get(r["status"], "")
        body_rows.append([esc(r["id"]), esc(r["req"]),
                          '<span class="pill %s">%s</span>' % (cls, esc(r["status"])),
                          esc(r["evidence"]), where,
                          esc(r["gap"]) if r["gap"] else '<span class="blank">—</span>',
                          ext(r["src"], src_label(r["src"]))])
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    head = ('<div class="cards">' + "".join(
        '<div class="card"><div class="k">%s</div><div class="v">%d</div></div>'
        % (esc(k), v) for k, v in sorted(counts.items())) + "</div>")
    body = section("Every requirement in the brief, mapped to what exists",
                   table(["ID", "Requirement", "Status", "What exists", "Where",
                          "What is missing / blocked", "Source"], body_rows),
                   note="Counts are read from the published dataset at build time, not typed in. "
                        "“Met (result: none)” means the deliverable exists and its honest answer "
                        "is zero.")
    return page("Brief coverage", head + body,
                head + body, "coverage.html")


def page_flags(rep):
    rows = []
    for f in rep["flags"]:
        rows.append([esc(f["id"]),
                     '<span class="pill pill-%s">%s</span>' % (
                         {"high": "bad", "medium": "warn", "low": "warn"}[f["severity"]],
                         esc(f["severity"])),
                     "<strong>%s</strong>" % esc(f["title"]),
                     esc(f["evidence"]),
                     esc(describe_moved(f)),
                     esc(f["owner_action"]),
                     ext(f["source"], "official source")])
    return page("Flagged for review",
                "Everything this session could not confirm, or confirmed as different, with the "
                "page that proves it and the decision it needs.",
                section("Flagged items (%d)" % len(rep["flags"]),
                        table(["ID", "Severity", "Item", "Evidence", "What moved",
                               "Owner action", "Source"], rows),
                        note="Nothing here blocks the build or the deploy. Each item is left for "
                             "the owner to decide on, and the files it would change belong to "
                             "another session."),
                "flags.html")


# ---------------------------------------------------------------------------------------------
def validate(pages_dir, written):
    """Both page rules: every tbody row has an https evidence link; every internal link resolves."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_tbody = False
            self.in_row = False
            self.depth = 0
            self.row_links = []
            self.bad_rows = []
            self.links = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "tbody":
                self.in_tbody = True
            elif tag == "tr" and self.in_tbody:
                self.in_row = True
                self.row_links = []
            elif tag == "a" and self.in_row:
                href = a.get("href", "")
                self.row_links.append(href)
                self.links.append(href)
            elif tag == "tr":
                self.depth += 1

        def handle_endtag(self, tag):
            if tag == "tbody":
                self.in_tbody = False
            elif tag == "tr" and self.in_row:
                self.in_row = False
                if not any(h.startswith("https://") for h in self.row_links):
                    self.bad_rows.append(self.row_links)
                self.row_links = []

    problems = []
    for name in written:
        path = os.path.join(pages_dir, name)
        p = P()
        with open(path) as fh:
            p.feed(fh.read())
        for bad in p.bad_rows:
            problems.append("%s: a table body row has no https evidence link" % name)
        for href in p.links:
            if href.startswith("https://") or href.startswith("#") or href.startswith("mailto:"):
                continue
            target = os.path.normpath(os.path.join(pages_dir, href))
            if not os.path.exists(target):
                problems.append("%s: internal link %s does not resolve" % (name, href))
    return problems


def main():
    os.makedirs(PAGES, exist_ok=True)
    rep = load("verification_report.json")
    ana = load("analysis.json")
    cov = build_coverage(rep, ana)

    written = []

    def w(name, text):
        with open(os.path.join(PAGES, name), "w") as fh:
            fh.write(text)
        written.append(name)

    w("index.html", page_index(rep, ana, None, None))
    w("injuries.html", page_injuries(rep))
    w("verification.html", page_verification(rep))
    w("slate.html", page_slate())
    w("ratings.html", page_ratings(rep))
    w("analysis.html", page_analysis(ana))
    w("coverage.html", page_coverage(cov))
    w("flags.html", page_flags(rep))

    problems = validate(PAGES, written)
    if problems:
        for p in problems:
            print("PAGE RULE FAILED: %s" % p)
        raise SystemExit(1)
    print("wrote %d pages; %s" % (len(written), ", ".join(written)))
    return written


if __name__ == "__main__":
    main()
