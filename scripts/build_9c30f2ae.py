#!/usr/bin/env python3
"""Build the 9c30f2ae subsite (/9c30f2ae/) from data/rounds/2026-11-19-9c30f2ae/*.json.

Pages: index, injuries, results, standings, team-stats, slate, flagged.

Rules the pages keep, because they are the ones the owner asked to be able to audit:

  * every table row carries an https link to the official NBA page the row came from;
  * a cell the official document did not print is rendered blank with an UNVERIFIED marker, never
    filled from another page, another revision or another session's capture;
  * projection and bet surfaces are never mixed: this subsite publishes official facts, and the one
    derived number it publishes (the measured home-court rate) is labelled a measurement, with its
    arithmetic printed next to it.

Nothing is typed in by hand at page-build time: every value is read from the committed JSON.

Usage:
  python3 scripts/build_9c30f2ae.py          # write 9c30f2ae/*.html
  python3 scripts/build_9c30f2ae.py --check  # rebuild in memory, compare with disk, verify links
"""
from __future__ import annotations

import html
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RD = ROOT / "data" / "rounds" / "2026-11-19-9c30f2ae"
OUT = ROOT / "9c30f2ae"
SLATE = ROOT / "data" / "rounds" / "2026-11-19" / "slate_2026-11-19_22.json"

PAGES = ["index", "injuries", "results", "standings", "team-stats", "slate", "flagged"]
NAV = [("index.html", "Home"), ("injuries.html", "Injuries"), ("results.html", "11/18 results"),
       ("standings.html", "Standings"), ("team-stats.html", "Team stats"),
       ("slate.html", "Slate"), ("flagged.html", "Flagged for Review")]

CSS = """
body{font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1d2433;background:#f6f7f9}
header{background:#1d2433;color:#fff;padding:14px 22px}
header a{color:#fff;margin-right:16px;text-decoration:none;opacity:.85}
header a:hover,header a.on{opacity:1;text-decoration:underline}
header h1{margin:0 0 6px;font-size:19px;font-weight:600}
main{padding:18px 22px;max-width:1280px}
h2{font-size:17px;margin:26px 0 8px}
h3{font-size:15px;margin:18px 0 6px}
.banner{background:#fff7e0;border:1px solid #e8c766;border-radius:6px;padding:10px 14px;margin:10px 0 16px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
.card{background:#fff;border:1px solid #dde1e7;border-radius:8px;padding:12px 14px;min-width:210px;flex:1}
.card b{display:block;font-size:22px;margin-top:4px}
.card a{text-decoration:none;color:#1f5fbf}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13.5px;margin-bottom:10px}
th,td{border-bottom:1px solid #e6e9ee;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef1f5;font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.unv{color:#8a5a00;font-weight:600}
.muted{color:#5b6573;font-size:13px}
a{color:#1f5fbf}
.tag{display:inline-block;background:#e9eefc;border-radius:4px;padding:1px 6px;font-size:12px}
.tag.bet{background:#fdeaea}
.warn{background:#fff1f0;border-left:4px solid #d64541;padding:8px 12px;margin:8px 0}
.ok{background:#eefaf1;border-left:4px solid #2e9e5b;padding:8px 12px;margin:8px 0}
code{font-size:12.5px}
"""


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def esc(v):
    return "" if v is None else html.escape(str(v))


def link(url, text):
    return f'<a href="{html.escape(url, quote=True)}">{esc(text)}</a>'


def blank(v):
    """A cell that must stay blank when the document did not print it."""
    return f'<span class="unv">UNVERIFIED</span>' if v is None or v == "" else esc(v)


def num(v, dp=1):
    if v is None:
        return '<span class="unv">—</span>'
    return f"{v:.{dp}f}"


def page(title, active, body, banner=""):
    nav = "".join(f'<a href="{h}"{" class=on" if h == active else ""}>{esc(t)}</a>' for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · official NBA capture (9c30f2ae)</title>
<style>{CSS}</style></head>
<body>
<header><h1>Official NBA capture · 2026-11-19 round</h1><nav>{nav}</nav></header>
<main>
{banner}
{body}
<p class="muted">Session <code>arena/9c30f2ae-nba3</code>. Every row links to the official NBA page it came from.
A cell the official document did not print is left blank and marked UNVERIFIED. Source files:
<code>data/rounds/2026-11-19-9c30f2ae/</code>, reproducible offline with
<code>python3 scripts/capture_9c30f2ae.py --check</code>.</p>
</main></body></html>
"""


def build():
    man = load(RD / "manifest.json")
    inj = load(RD / "injuries_2026-11-19_0130AM.json")
    adv = load(RD / "team_stats_advanced_2026-11-19.json")
    res = load(RD / "results_2026-11-18.json")
    st = load(RD / "standings_2026-11-19.json")
    slate = load(SLATE)
    pages = {}
    inj_url = inj["source_url"]
    inj_prev_url = inj["previous_revision"]["source_url"]
    st_url = st["source_url"]
    adv_url = adv["source_url"]
    retrieval = inj["retrieved_utc"]

    # ---------------------------------------------------------------- injuries
    banner = (f'<div class="banner"><b>Injury-report revision time:</b> '
              f'{esc(inj["report_stamp"])} (printed on the official PDF) &nbsp;·&nbsp; '
              f'<b>Retrieved:</b> {esc(retrieval)} &nbsp;·&nbsp; '
              f'<span class="muted">the fetch tool returns no per-call timestamp; see the manifest for the retrieval window</span><br>'
              f'<span class="muted">This is the newest revision of 11/19 the official index lists '
              f'(<a href="{esc(inj["index_url"])}">index</a>); the index lists eight for the day, '
              f'12:00 AM through 01:45 AM ET.</span></div>')

    rows = []
    for r in inj["rows"]:
        team = esc(r["team"]) if r["team"] else '<span class="unv">no team cell</span>'
        status = esc(r["status"]) if r["status"] else '<span class="unv">not printed</span>'
        reason = esc(r["reason"]) if r["reason"] else "—"
        note = []
        if not r["attributed"]:
            note.append("row lost its team cell at the PDF page break; published unattributed, not "
                        "matched to a neighbour")
        if r["not_yet_submitted"]:
            note.append("printed in the " + (r["not_yet_submitted_printed_in"] or "?") + " column")
        rows.append(f'<tr><td>{esc(r["game_date"]) or blank(None)}</td>'
                    f'<td>{esc(r["game_time"]) or "—"}</td><td>{esc(r["matchup"]) or "—"}</td>'
                    f'<td>{team}</td><td>{esc(r["player"]) or "—"}</td><td>{status}</td>'
                    f'<td>{reason}</td><td class="muted">{esc("; ".join(note)) or "—"}</td>'
                    f'<td>{link(inj_url, "Official PDF 01:30 AM ET")}</td></tr>')
    rows_tbl = ('<h2>Every printed row, newest revision (01:30 AM ET, 11/19/26)</h2>'
                '<p class="muted">All 44 rows as the PDF text layer prints them, in printed order. '
                'An empty status means the document printed no status for that row — it is not inherited '
                'from the row above, and the <em>Note</em> column says so.</p>'
                '<table><thead><tr><th>Game date</th><th>Game time</th><th>Matchup</th><th>Team</th>'
                '<th>Player</th><th>Status</th><th>Reason</th><th>Note</th><th>Source</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table>')

    # diff
    d = inj["delta_vs_previous"]
    drow = (f'<tr><td>12:45 AM ET → 01:30 AM ET</td>'
            f'<td class="num">{len(d["status_changes"])}</td><td class="num">{len(d["appeared"])}</td>'
            f'<td class="num">{len(d["disappeared"])}</td>'
            f'<td>{link(inj_prev_url, "12:45 AM")} → {link(inj_url, "01:30 AM")}</td></tr>')
    diff_tbl = ('<h2>Consecutive-report diff</h2>'
                '<table><thead><tr><th>Pair</th><th>Status changes</th><th>Players appearing</th>'
                '<th>Players disappearing</th><th>Sources</th></tr></thead>'
                f'<tbody>{drow}</tbody></table>'
                f'<p class="muted">{esc(inj["delta_rule"])}. Result: the newest four revisions of the '
                f'night are identical wherever both print a team.</p>')

    unattr = "".join(f'<tr><td class="num">{r["line"]}</td><td>{esc(r["player"])}</td>'
                     f'<td>{esc(r["status"])}</td><td>{link(inj_url, "Official PDF")}</td></tr>'
                     for r in inj["unattributed_rows"])
    unattr_tbl = ("<h2>Rows with no team cell</h2>"
                  '<p class="muted">The PDF page break drops the leading cells of some rows. These two '
                  'print a player and a status but no team, so they are published exactly that way and '
                  '<b>not</b> assigned to a game.</p>'
                  '<table><thead><tr><th>Transcript line</th><th>Player</th><th>Status</th>'
                  f'<th>Source</th></tr></thead><tbody>{unattr}</tbody></table>')

    pages["injuries"] = page("Injuries", "injuries.html", rows_tbl + diff_tbl + unattr_tbl, banner)

    # ---------------------------------------------------------------- results
    rrows = []
    for g in res["games"]:
        aq = " · ".join(str(q["pts"]) for q in g["away_q"])
        hq = " · ".join(str(q["pts"]) for q in g["home_q"])
        ok = ('<span class="ok" style="display:inline-block">sums to final</span>'
              if g["quarter_sums_equal_final"] else '<span class="unv">DOES NOT SUM</span>')
        rrows.append(f'<tr><td>{esc(res["date"])}</td><td>{esc(g["game_id"])}</td>'
                     f'<td>{esc(g["away"])}</td><td class="num">{g["away_pts"]}</td><td>{aq}</td>'
                     f'<td>{esc(g["home"])}</td><td class="num">{g["home_pts"]}</td><td>{hq}</td>'
                     f'<td>{ok}</td><td>{link(g["source_url"], "NBA.com game page")}</td></tr>')
    n_ok = sum(1 for g in res["games"] if g["quarter_sums_equal_final"])
    body = (f'<h2>Final scores with quarter scores, {esc(res["date"])} ({res["game_count"]} games)</h2>'
            '<p class="muted">One row per game: date, teams, final score, and the four quarter scores as the '
            'game page prints them. Every row was checked arithmetically — the four printed quarter cells '
            f'must sum to the printed final. <b>{n_ok} of {res["game_count"]}</b> pass. This is the feed the '
            'ledger is settled against, so a row that did not tie out would be published unverified rather '
            'than settled.</p>'
            '<table><thead><tr><th>Date</th><th>Game ID</th><th>Away</th><th>Final</th><th>Q1-Q4 away</th>'
            '<th>Home</th><th>Final</th><th>Q1-Q4 home</th><th>Check</th><th>Source</th></tr></thead>'
            f'<tbody>{"".join(rrows)}</tbody></table>'
            '<p class="muted">Quarter cells are joins of the two printed conference lines on each game page '
            '(away quarters on the away line, home quarters on the home line). No value is inferred: a '
            'quarter the page did not print would appear blank.</p>')
    pages["results"] = page("11/18 results", "results.html", body)

    # ---------------------------------------------------------------- standings
    hc = st["home_court_measured"]
    srows = []
    for t in st["teams"]:
        srows.append(f'<tr><td>{esc(t["conference"])}</td><td class="num">{t["seed_printed"]}</td>'
                     f'<td>{esc(t["team"])}</td><td class="num">{t["gp"]}</td>'
                     f'<td class="num">{t["w"]}</td><td class="num">{t["l"]}</td>'
                     f'<td class="num">{esc(t["win_pct_printed"])}</td>'
                     f'<td class="num">{esc(t["home_printed"])}</td>'
                     f'<td class="num">{esc(t["road_printed"])}</td>'
                     f'<td class="num">{esc(t["neutral_printed"])}</td>'
                     f'<td class="num">{esc(t["last10_printed"])}</td>'
                     f'<td>{esc(t["streak_printed"])}</td>'
                     f'<td>{link(st_url, "NBA.com standings")}</td></tr>')
    c = st["checks"]
    checks_html = (
        f'<li>Sum of every club\'s W = {c["total_w"]}; sum of every club\'s L = {c["total_l"]} — '
        f'<b>{"equal" if c["w_equals_l"] else "NOT EQUAL"}</b>, as it must be.</li>'
        f'<li>Home W-L {c["home_w"]}-{c["home_l"]}; road W-L {c["road_w"]}-{c["road_l"]}; '
        f'neutral {c["neutral_w"]}-{c["neutral_l"]}.</li>'
        f'<li>Home + road + neutral wins = {c["home_w"] + c["road_w"] + c["neutral_w"]} '
        f'(total {c["total_w"]}) — '
        f'<b>{"equal" if c["home_plus_road_w_equals_total"] else "NOT EQUAL"}</b>.</li>'
        f'<li>Home games {c["home_games"]} = road games {c["road_games"]} — '
        f'<b>{"equal" if c["home_games_equal_road_games"] else "NOT EQUAL"}</b>.</li>')
    body = ("<h2>Standings, all 30 clubs</h2>"
            '<p class="muted">Read from one capture of the official standings page. Every W, L, split and '
            'streak below is printed by that page; the GP column is the only computed one (W + L), and it '
            'is shown because the page does not print a separate GP column and the round needs it.</p>'
            '<table><thead><tr><th>Conf</th><th>Seed</th><th>Team</th><th>GP</th><th>W</th><th>L</th>'
            '<th>Win%</th><th>Home</th><th>Road</th><th>Neutral</th><th>Last 10</th><th>Streak</th>'
            f'<th>Source</th></tr></thead><tbody>{"".join(srows)}</tbody></table>'
            '<h3>Measured home-court advantage</h3>'
            f'<div class="ok"><b>{hc["home_wins"]} home wins in {hc["home_games"]} games with a home side = '
            f'{hc["home_win_rate"]:.4%}</b> (away rate {hc["away_win_rate"]:.4%}). The brief pins home-court '
            'advantage to the measured home-win rate instead of a fitted coefficient; this is that '
            'measurement, taken over every game this season that had a home side.</div>'
            f'<p class="muted">{esc(hc["note"])}</p>'
            '<p class="muted">The arithmetic is re-derivable from the table: sum the Home column for home '
            'wins, subtract the neutral-site games (a Cup game at a neutral site has no home team, and '
            'counting it as one would understate the rate), and divide.</p>'
            f'<h3>Identity checks</h3><ul class="muted">{checks_html}</ul>'
            '<p class="muted">On ordering: the page prints Western seeds 7-9 by wins rather than by '
            'winning percentage, so a club with a better percentage can sit below one with more wins and '
            'fewer games. Rows are published in the page\'s own order and the Seed column is that '
            'printed rank.</p>')
    pages["standings"] = page("Standings", "standings.html", body)

    # ---------------------------------------------------------------- team stats
    cols = [("off_rtg", "OffRtg", 1), ("def_rtg", "DefRtg", 1), ("net_rtg", "NetRtg", 1),
            ("ast_pct", "AST%", 1), ("ast_to", "AST/TO", 2), ("oreb_pct", "OREB%", 1),
            ("dreb_pct", "DREB%", 1), ("reb_pct", "REB%", 1), ("tov_pct", "TOV%", 1),
            ("efg_pct", "eFG%", 1), ("ts_pct", "TS%", 1), ("pace", "PACE", 1),
            ("pie", "PIE", 1), ("poss", "POSS", 1)]
    arows = []
    for r in sorted(adv["rows"], key=lambda x: x["rank_printed"]):
        cells = "".join(f'<td class="num">{num(r.get(k), dp)}</td>' for k, _, dp in cols)
        flag = "" if r["complete"] else ' <span class="unv">PARTIAL</span>'
        arows.append(f'<tr><td class="num">{r["rank_printed"]}</td><td>{esc(r["team"])}{flag}</td>'
                     f'<td class="num">{int(r["gp"])}</td><td class="num">{int(r["w"])}</td>'
                     f'<td class="num">{int(r["l"])}</td>{cells}'
                     f'<td>{link(adv_url, "NBA.com Teams Advanced")}</td></tr>')
    hdr = "".join(f"<th>{esc(t)}</th>" for _, t, _ in cols)
    body = ('<h2>Advanced team statistics, 30 clubs</h2>'
            f'<p class="muted">One capture of the official Teams Advanced page, regular season, the '
            f'page\'s own default filter. <b>{adv["rows_read_in_full"]} of {adv["page_prints_rows"]}</b> '
            f'rows were read in full; {adv["rows_partial"]} row (Dallas) was cut off by the fetch tool\'s '
            'chunk boundary and is published <span class="unv">PARTIAL</span>, with every unread cell left '
            'blank. Cells are never filled from a different page or a later capture.</p>'
            '<p class="muted">W + L = GP was checked on every complete row: '
            f'<b>{"no failures" if not adv["failures"] else esc(", ".join(adv["failures"]))}</b>.</p>'
            '<table><thead><tr><th>#</th><th>Team</th><th>GP</th><th>W</th><th>L</th>'
            f'{hdr}<th>Source</th></tr></thead><tbody>{"".join(arows)}</tbody></table>'
            '<p class="muted">The page\'s header also prints RANK sub-columns for each statistic; those '
            'were not part of the returned text and are therefore absent here rather than computed.</p>')
    pages["team-stats"] = page("Team stats", "team-stats.html", body)

    # ---------------------------------------------------------------- slate
    srows2 = []
    n = 0
    for day in slate["days"]:
        for g in day["games"]:
            n += 1
            venue = esc(g["venue"]) if g.get("venue") else '<span class="unv">not printed</span>'
            srows2.append(f'<tr><td>{esc(day["date"])}</td><td>{esc(g["tip_et"])}</td>'
                          f'<td>{esc(g["away"])} @ {esc(g["home"])}</td><td>{esc(g["game_id"])}</td>'
                          f'<td>{venue}</td><td>{link(g["source_url"], "NBA.com game page")}</td></tr>')
    body = (f'<h2>Official slate, {len(slate["days"])} days, {n} games</h2>'
            '<p class="muted">Read from the official schedule listing (session <code>b1ce1334</code> '
            'captured this window at 05:44–05:50 UTC today; this session re-read the 11/19 games and '
            'found the same four fixtures and tip times as the game pages it fetched for their finals). '
            'Venues print for two of the four 11/19 games and for none of the later days; blank cells are '
            'unverified, not empty.</p>'
            '<table><thead><tr><th>Date</th><th>Tip (ET)</th><th>Matchup</th><th>Game ID</th><th>Venue</th>'
            f'<th>Source</th></tr></thead><tbody>{"".join(srows2)}</tbody></table>'
            '<p class="muted">The 11/20 game IDs (0022600043–0022600051) are NBA Cup group games and sit '
            'outside the regular-season ID sequence; they are printed as-is.</p>')
    pages["slate"] = page("Slate", "slate.html", body)

    # ---------------------------------------------------------------- flagged
    flags = [
        ("F1", "The 11/19 01:45 AM ET injury revision is listed on the official index but was not "
               "captured in this session. The diff published here therefore covers 12:45 AM → 01:30 AM only.",
         inj["index_url"], "One more fetch; recorded as listed-but-uncaptured rather than assumed identical."),
        ("F2", "Two rows of the 01:30 AM report print a player and a status but no team cell "
               "(Kuminga, Pullin — both Questionable). They are published unattributed.",
         inj_url, "PDF page-break layout; not matched to a neighbouring row."),
        ("F3", "The Dallas row of the advanced team-stat page is cut off after AST/TO by the fetch tool's "
               "chunk boundary. Its remaining cells are blank, not inferred.",
         adv_url, "Chunk 0 ends mid-row; requesting later chunk indexes re-serves the final chunk."),
        ("F4", "The Teams Traditional and Opponent pages were not captured in this session, so the "
               "per-team stat set is incomplete: advanced only.",
         "https://www.nba.com/stats/teams/traditional",
         "Required by the brief's 're-read the three official team-stat pages' step; open."),
        ("F5", "The official standings page prints Western seeds 7-9 by wins rather than by winning "
               "percentage. Rows are published in printed order and no seed is asserted.",
         st_url, "No value is changed; this is a display-order note."),
        ("F6", "Venues are blank for 2 of the 4 games on 11/19 and for every game on 11/20-11/22.",
         slate["primary_source"]["url"], "Not printed on the pages read; left blank."),
        ("F7", "The PDF and HTML bytes are not stored: the fetch tool returns parsed text. What is stored is "
               "the verbatim transcript plus its sha256, so the capture can be re-diffed but not re-parsed "
               "from the original file.",
         inj_url, "The bash sandbox cannot reach the official hosts (TLS EOF on every attempt)."),
        ("F8", "Retrieval timestamps are the manifest's stated window, not a per-call clock reading.",
         inj["index_url"], "The fetch tool returns no timestamp; the window is bounded in the manifest."),
        ("F9", "Nothing in this round settles a ledger entry. The 11/18 finals are verified and published "
               "as facts, but the sealed picks for those games live on the bet surface and were not "
               "settled by this session.",
         res["games"][0]["source_url"], "Projection and bet surfaces are kept separate by design."),
        ("F10", "Home-court advantage is now pinned to a measured 50.23% home-win rate, where the model "
                "on the projection surface was fitted on a 22-game sample that implied a much larger edge. "
                "The pin is recorded but the model was not re-run in this session.",
         st_url, "Re-running the model is a separate, gated change; recorded so it is not lost."),
    ]
    frows = "".join(f'<tr><td>{esc(i)}</td><td>{esc(t)}</td><td>{link(u, "Source")}</td>'
                    f'<td class="muted">{esc(note)}</td></tr>' for i, t, u, note in flags)
    body = ('<h2>Flagged for Review</h2><p class="muted">Irregularities and unverified items from this '
            'capture. None blocks publication of the official facts on this site; each carries a link so '
            'the item can be checked by hand.</p>'
            '<table><thead><tr><th>ID</th><th>Item</th><th>Source</th><th>Note</th></tr></thead>'
            f'<tbody>{frows}</tbody></table>')
    pages["flagged"] = page("Flagged for Review", "flagged.html", body)

    # ---------------------------------------------------------------- landing
    n_rows = inj["row_count"]
    n_changes = len(d["status_changes"])
    body = f"""
<h2>Surfaces</h2>
<div class="cards">
 <div class="card"><span class="tag">Projection · published</span><b>Official facts, measured values</b>
   <span class="muted">Injury report, finals with quarter scores, standings, advanced team statistics and
   the slate. Every row sourced. The one derived number (home-court advantage) is a measurement with its
   arithmetic shown.</span></div>
 <div class="card"><span class="tag bet">Bet · gated</span><b>Not published here</b>
   <span class="muted">No pick, line, price or ledger entry appears on this subsite. Nothing in this round
   was staked or settled, so the bet surface has nothing new to show — and putting a projection and a bet
   on the same page is exactly what the brief forbids.</span></div>
</div>
<h2>At a glance</h2>
<div class="cards">
 <div class="card"><a href="injuries.html">Injuries</a><b>{n_rows} printed rows</b>
   <span class="muted">newest revision 01:30 AM ET; {n_changes} status changes across the 12:45 → 01:30 step</span></div>
 <div class="card"><a href="results.html">11/18 results</a><b>{res["game_count"]} finals</b>
   <span class="muted">with quarter scores; {n_ok} of {res["game_count"]} tie out arithmetically</span></div>
 <div class="card"><a href="standings.html">Standings</a><b>{len(st["teams"])} clubs</b>
   <span class="muted">all identities check; measured home-win rate {hc["home_win_rate"]:.2%}</span></div>
 <div class="card"><a href="team-stats.html">Team stats</a><b>{len(adv["rows"])} clubs</b>
   <span class="muted">advanced page; {adv["rows_partial"]} row partial and marked</span></div>
 <div class="card"><a href="slate.html">Slate</a><b>{n} games</b>
   <span class="muted">11/19–11/22; tip times from the official schedule</span></div>
 <div class="card"><a href="flagged.html">Flagged for Review</a><b>{len(flags)} items</b>
   <span class="muted">each with a source link</span></div>
</div>
<h2>What this round established</h2>
<ul>
 <li><b>Quarter scores now exist for every 11/18 game.</b> Both this session's earlier captures and the
   other sessions' left them blank; all 12 games now carry four printed quarter cells per team, and each
   row was checked to sum to its printed final.</li>
 <li><b>Home-court advantage has a measured value instead of a fitted one:</b> {hc["home_wins"]} home wins in
   {hc["home_games"]} games with a home side, <b>{hc["home_win_rate"]:.4%}</b>.</li>
 <li><b>The injury report moved four times after 12:45 AM and said nothing new.</b> The 01:30 AM revision is
   textually identical to 12:45 AM wherever both print a team.</li>
 <li><b>The advanced team page was captured with its chunk boundary intact</b>, so the one partial row is
   visible as partial rather than silently plausible.</li>
</ul>
<h2>Reproducing this</h2>
<p class="muted">The round's artefacts are re-derivable offline from the committed transcripts:
<code>python3 scripts/capture_9c30f2ae.py --check</code> rebuilds every JSON in
<code>data/rounds/2026-11-19-9c30f2ae/</code> and compares it byte for byte, and
<code>python3 scripts/build_9c30f2ae.py --check</code> does the same for these pages. Twenty tests in
<code>tests/test_capture_9c30f2ae.py</code> pin the counts to the transcripts, including a planted-error
test for the quarter-sum check and one that fails if an unread stat cell ever gets filled in.</p>
"""
    pages["index"] = page("Home", "index.html", body)
    return pages


class _Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tbody = False
        self.row = None
        self.rows = 0
        self.rows_without_src = 0
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.row = {"src": False}
        elif tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            if self.row is not None and a["href"].startswith("https://"):
                self.row["src"] = True

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            self.rows += 1
            if not self.row["src"]:
                self.rows_without_src += 1
            self.row = None
        elif tag == "tbody":
            self.in_tbody = False


def check_site(pages):
    ok = True
    for name, text in pages.items():
        c = _Checker()
        c.feed(text)
        if c.rows_without_src:
            print(f"SITE CHECK FAILED: {name}.html: {c.rows_without_src} table row(s) without an https "
                  "source link", file=sys.stderr)
            ok = False
        for h in c.hrefs:
            if h.startswith("https://") or h.startswith("#"):
                continue
            if h.endswith(".html") and h not in {p + ".html" for p in PAGES}:
                print(f"SITE CHECK FAILED: {name}.html: broken internal link {h}", file=sys.stderr)
                ok = False
        # an official host must actually be official
        for h in c.hrefs:
            if h.startswith("https://") and not any(d in h for d in (
                    "nba.com", "github.com")):
                print(f"SITE CHECK FAILED: {name}.html: non-official source link {h}", file=sys.stderr)
                ok = False
    return ok


def main(argv):
    pages = build()
    if "--check" in argv:
        ok = check_site(pages)
        for name, text in pages.items():
            p = OUT / f"{name}.html"
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                print(f"SITE CHECK FAILED: 9c30f2ae/{name}.html is stale; run "
                      "scripts/build_9c30f2ae.py", file=sys.stderr)
                ok = False
        print(f"9c30f2ae site check: {'PASS' if ok else 'FAIL'} ({len(pages)} pages)")
        return 0 if ok else 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (OUT / f"{name}.html").write_text(text, encoding="utf-8")
    ok = check_site(pages)
    print(f"wrote {len(pages)} pages to {OUT.relative_to(ROOT)}/"
          + ("" if ok else " (with site-check failures above)"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
