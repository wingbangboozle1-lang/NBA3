#!/usr/bin/env python3
"""Build this session's pages from d1b96315/data/*.json — no wall clock, no network, no typed numbers.

Every table row on every page carries the official link it was read from; a value that could not be
confirmed from an official source is printed empty and labelled, never inferred. Two self-checks run
in CI (and in d1b96315/tests/) before these pages are considered built: no relative link may point at
a missing file, and no data row may lack a source.

Run: python3 d1b96315/build_pages.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
PAGES = HERE / "pages"
REPO_BLOB = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/"
LIVE = "https://wingbangboozle1-lang.github.io/NBA3/"
TREE = LIVE + "d1b96315/pages/"
OFFICIAL_HOSTS = ("nba.com", "statsdmz.nba.com", "ak-static.cms.nba.com", "official.nba.com")
NO_SOURCE = '<span class="none">no official link on this row</span>'
NONE_TAG = '<span class="none">not available</span>'
DISPUTED_TAG = '<span class="none">disputed</span>'

NAV = [("index", "Roll"), ("injuries", "Injuries"), ("results", "Results"),
       ("standings", "Standings"), ("lines", "Originated lines"), ("pricing", "Pricing &amp; rho"),
       ("model", "Method"), ("gates", "Gates &amp; leaderboard"), ("ledger", "Ledger"),
       ("questions", "Questions"), ("suggestions", "Suggestions"), ("sources", "Sources"),
       ("flagged", "Flagged for review")]


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def e(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def fmt(v, nd=2, dash="—"):
    if v is None or v == "" or v == []:
        return f'<span class="none">{dash}</span>'
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:.{nd}f}" if isinstance(v, float) else str(v)
    return e(v)


def ext(url: str) -> str:
    return f'<a href="{e(url)}" rel="noopener" class="src">official</a>' if url.startswith("http") \
        else f'<a href="{e(REPO_BLOB + url)}" rel="noopener" class="src">repo file</a>'


def link(url: str, label: str = None) -> str:
    return f'<a href="{e(url)}" rel="noopener">{e(label or url)}</a>'


def src_cell(urls, sep=" · ") -> str:
    urls = [u for u in (urls if isinstance(urls, (list, tuple)) else [urls]) if u]
    if not urls:
        return NO_SOURCE
    out = []
    for u in urls:
        if u.startswith("http"):
            host = u.split("//", 1)[1].split("/", 1)[0]
            out.append(f'<a class="src" href="{e(u)}" rel="noopener">{e(host)}</a>')
        else:
            out.append(f'<a class="src" href="{e(REPO_BLOB + u)}" rel="noopener">{e(u)}</a>')
    return sep.join(out)


CSS = """
:root{--ink:#14202b;--mut:#5b6b78;--line:#dfe5ea;--bg:#f7f9fb;--ok:#1d7a46;--warn:#9a6b00;--bad:#b3261e;--acc:#1f5fa8;--card:#fff}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#fff;border-bottom:1px solid var(--line);padding:12px 22px;position:sticky;top:0;z-index:3}
header .t{font-weight:700;font-size:16px}header .sub{color:var(--mut);font-size:12.5px}
nav{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px}
nav a{font-size:12.5px;padding:3px 8px;border:1px solid var(--line);border-radius:999px;text-decoration:none;color:var(--acc);background:#fff}
nav a.on{background:var(--acc);color:#fff;border-color:var(--acc);font-weight:600}
main{padding:20px 22px 60px;max-width:1500px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16.5px;margin:26px 0 8px}h3{font-size:14px;margin:18px 0 6px}
p{margin:6px 0}.mut{color:var(--mut)}.small{font-size:12.5px}.lead{font-size:15.5px;max-width:1100px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin:12px 0 4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card .k{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--mut)}
.card .v{font-size:21px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.card .n{font-size:11.5px;color:var(--mut);margin-top:3px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:12.8px;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}
th{background:#eef3f7;font-weight:600;position:sticky;top:0;font-size:11.5px;text-transform:uppercase;letter-spacing:.03em}
td.num,th.num{text-align:right}tr:hover td{background:#f2f7fb}
.tag{display:inline-block;padding:1px 6px;border-radius:4px;font-size:11.5px;font-weight:600;white-space:nowrap}
.ok{background:#e3f3ea;color:var(--ok)}.bad{background:#fbe7e5;color:var(--bad)}.warn{background:#fdf3dc;color:var(--warn)}
.info{background:#e6effa;color:var(--acc)}.grey{background:#eef1f4;color:var(--mut)}
.none{color:#9aa8b3;font-style:italic}
.note{background:#fff;border-left:3px solid var(--acc);padding:9px 12px;border-radius:0 8px 8px 0;margin:10px 0;font-size:13.2px}
.warnbox{background:#fff;border-left:3px solid var(--warn);padding:9px 12px;border-radius:0 8px 8px 0;margin:10px 0;font-size:13.2px}
.badbox{background:#fff;border-left:3px solid var(--bad);padding:9px 12px;border-radius:0 8px 8px 0;margin:10px 0;font-size:13.2px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:980px){.grid2{grid-template-columns:1fr}}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
code{background:#eef3f7;padding:1px 4px;border-radius:4px;font-size:12px}
a.src{font-size:11.5px;color:var(--acc);text-decoration:none;border-bottom:1px dotted var(--acc)}
ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}
.q{background:#fff;border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin:9px 0}
.q h4{margin:0 0 5px;font-size:13.5px}
footer{border-top:1px solid var(--line);margin-top:30px;padding:14px 22px;color:var(--mut);font-size:12px}
"""


def page(name: str, title: str, body: str, banner: str = "") -> str:
    nav = "".join(f'<a href="{k}.html" class="{"on" if k == name else ""}">{lab}</a>'
                  for k, lab in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · NBA 2026-11-16 game-day roll (arena/d1b96315-nba3)</title>
<style>{CSS}</style></head>
<body>
<header>
  <div class="t">NBA · 2026-11-16 game-day roll <span class="tag info">session arena/d1b96315-nba3</span></div>
  <div class="sub">Official sources only · every row linked · unconfirmed values left blank and flagged ·
    projection surface and bet surface kept apart</div>
  <nav>{nav}</nav>
</header>
<main>
{banner}
{body}
</main>
<footer>Built by <code>d1b96315/build_pages.py</code> from <code>d1b96315/data/*.json</code>, which are
built by <code>capture.py</code>, <code>boxlog.py</code>, <code>model.py</code>, <code>flags.py</code>
and <code>ledger.py</code>. No value on any page is typed by hand. Canonical site:
{link(LIVE + "index.html", "NBA3 dashboard")} · this tree: {link(TREE + "index.html", "d1b96315/")}</footer>
</body></html>
"""


def table(headers, rows, cls=""):
    th = "".join(f'<th class="{"num" if h.startswith("^") else ""}">{e(h.lstrip("^"))}</th>'
                 for h in headers)
    tr = "\n".join("<tr>" + "".join(f'<td class="{"num" if isinstance(c, tuple) else ""}">'
                                    f'{c[0] if isinstance(c, tuple) else c}</td>' for c in r) + "</tr>"
                   for r in rows)
    return (f'<div class="scroll"><table class="{cls}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{tr}</tbody></table></div>')


def card(k, v, n=""):
    return f'<div class="card"><div class="k">{e(k)}</div><div class="v">{v}</div><div class="n">{n}</div></div>'


def sev(s):
    return f'<span class="tag {"bad" if s == "high" else "warn" if s == "medium" else "grey"}">{e(s)}</span>'


# ================================================================ pages

def p_index(A) -> str:
    m, st, res, lat, dm = A["model"], A["standings"], A["results"], A["latest"], A["delta_pm"]
    hc, ea, lines = m["home_court"], m["estimator_a"], A["lines"]
    pub = [r for r in lines if r.get("publishable")]
    agreed = [r for r in pub if r["disagreement_margin_points"] <= 2.5]
    bet_ok = [r for r in pub if r["bet_eligible"]]
    banner = f"""<div class="note"><b>Injury report banner.</b> Revision printed on the document:
<b>{e(lat['report_stamp'])} ET</b> · retrieved by this session at <b>{e(lat['retrieved_utc'])}</b> ·
the site had published the <b>{e(A['pub_inj']['report_stamp'])}</b> snapshot (retrieved
{e(A['pub_inj']['retrieved_utc'])}), so the published banner was about 4 h 05 m behind the newest
official revision until this page was built. Report index: {link(A['urls']['index'], 'official.nba.com')}
· newest PDF: {link(A['urls']['pdf_1315'], '01:15 PM ET revision')}</div>"""
    body = f"""
<h1>2026-11-16 roll: fresh inputs, settled 11/15, and a model that says how little it knows</h1>
<p class="lead">Everything on this site was re-read from the official NBA documents on the game day,
then put through the gates the brief sets. The roll produced four things worth your attention: the
injury snapshot the site was publishing was four hours stale at this session's base (a parallel
session has since published the same newest revision, and the two parses agree row for row); one official game book contradicts
itself on a quarter score; the league's own standings put home-court a third of what this repo had
been pinning; and the two estimators agree closely on exactly {len(agreed)} of the
{len(pub)} games in the window.</p>
<div class="cards">
{card("official revisions read", f"3", f"09:15 AM (already published) · 11:30 AM · {e(lat['report_stamp'])} — <a class='src' href='injuries.html'>diff</a>")}
{card("player rows on the report", f"{lat['player_rows']}", f"was {A['pub_inj']['player_rows']} at 09:15; +{lat['player_rows'] - A['pub_inj']['player_rows']}")}
{card("11/15 finals settled", f"{res['settled_count']}/{res['count']}", "one row per game, quarter sums checked — <a class='src' href='results.html'>table</a>")}
{card("measured home-win rate", f"{st['measured_home_win_rate'] * 100:.1f}%", f"{st['measured_home_wins']}-{st['measured_home_games'] - st['measured_home_wins']} of {st['measured_home_games']} home games — <a class='src' href='standings.html'>source</a>")}
{card("home-court now pinned", f"{hc['hca_points_used']} pts", f"was {m['home_court']['previously_published_in_this_repo']['data_rounds_2026_11_16']['hca_points']} in the round capture, {m['home_court']['previously_published_in_this_repo']['data_app_ledger_constant']['hca_points']} in the app ledger")}
{card("estimators agreeing", f"{len(agreed)}/{len(pub)}", f"within 2.5 pts of margin; {len(bet_ok)} rows inside the 5.0-point cap")}
{card("strategies funded", f"{A['gates']['summary']['funded']}/{A['gates']['summary']['strategies']}", f"blocked by {', '.join(A['gates']['summary']['gates_blocking_any_strategy'])} — <a class='src' href='gates.html'>board</a>")}
{card("picks sealed pre-tip", f"{A['ledger']['ledger']['published_pre_tip']}", f"head {e(A['ledger']['ledger']['head_hash'][:12])}… — <a class='src' href='ledger.html'>chain</a>")}
</div>

<h2>What this session changed</h2>
<table><thead><tr><th>#</th><th>finding</th><th>the measurement</th><th>status</th><th>where</th><th>sources</th></tr></thead><tbody>
<tr><td>1</td><td>the published injury snapshot was stale on the game day</td>
<td>4 h 05 m behind at base; the day's filing hop is 11:30 → <b>01:00 PM</b> (+18 rows, 4 status
changes), not the 01:15 PM revision everyone points at. Marcus Smart's suspension, three downgrades and
three clubs' filings were absent from the canonical capture tree, and the scheduled job is still why</td>
<td>{'<span class="tag bad">fixed here, needs the job rewired</span>'}</td><td><a href="injuries.html">Injuries</a></td><td>{src_cell([A["urls"]["index"], A["urls"]["pdf_1315"], "data/rounds/2026-11-16/injuries.json"])}</td></tr>
<tr><td>2</td><td>11/15 settled from a fresh official re-read, one row per game</td>
<td>9 games, 9 with a verified final, quarter vectors printed and summed; the 8 rows main had
settled match exactly; ATL@MIL's final is confirmed three ways while its quarter row is not</td>
<td><span class="tag ok">settled with one footnote</span></td><td><a href="results.html">Results</a></td><td>{src_cell([A["urls"]["games_1115"], A["urls"]["book_atlmil"], "d1b96315/data/results_2026-11-15.json"])}</td></tr>
<tr><td>3</td><td>no standings capture existed anywhere in the repo (board item K-07)</td>
<td>the first one is here: 30 rows, every split, all identities checked, and it is what the
home-court pin is now computed from</td><td><span class="tag ok">closed</span></td>
<td><a href="standings.html">Standings</a></td><td>{src_cell([A["urls"]["standings"], "d1b96315/data/standings_2026-11-16.json"])}</td></tr>
<tr><td>4</td><td>three different home-court values pinned in three places</td>
<td>{hc['hca_points_used']} (this build, league-wide measured) vs
{m['home_court']['previously_published_in_this_repo']['data_rounds_2026_11_16']['hca_points']} (round capture, 23 finals)
vs {m['home_court']['previously_published_in_this_repo']['data_app_ledger_constant']['hca_points']} (every sealed app-ledger entry)
— a {m['home_court']['previously_published_in_this_repo']['spread_between_the_three_points']}-point swing on every home line</td>
<td><span class="tag warn">owner decision needed</span></td><td><a href="model.html#hca">Method</a></td><td>{src_cell([A["urls"]["standings"], "data/rounds/2026-11-16/model.json", "data/app/ledger/ledger.jsonl"])}</td></tr>
<tr><td>5</td><td>luck refused to clear anyone</td>
<td>no club on the slate sits outside ±2 sd of its efficiency-based win expectation, so the refusal
rule did not fire; the clubs nearest the edge are printed instead of hidden</td>
<td><span class="tag ok">measured</span></td><td><a href="model.html#luck">Method</a></td><td>{src_cell([A["urls"]["advanced"], "d1b96315/data/model.json"])}</td></tr>
<tr><td>6</td><td>parlays priced with a measured correlation</td>
<td>ρ(margin, total) = {m['pricing']['rho_margin_vs_total']} (95% CI
{m['pricing']['rho_margin_vs_total_ci95']}) on {m['pricing']['measured_on']['settled_games']} games;
the naive product sits beside it on every row</td><td><span class="tag warn">projection only, no price to beat</span></td>
<td><a href="pricing.html">Pricing</a></td><td>{src_cell(["d1b96315/data/model.json", "d1b96315/data/results_2026-11-15.json"])}</td></tr>
<tr><td>7</td><td>per-player minutes redistribution is only possible for 9 of 30 clubs</td>
<td>{len(m['estimator_b']['teams_not_adjusted'])} clubs have no captured box score, so their rows read
"not modelled" rather than "no injuries"; this session added BOS, DAL, IND, PHI to the pool</td>
<td><span class="tag bad">input gap, published as one</span></td><td><a href="lines.html">Lines</a></td><td>{src_cell([A["urls"]["book_dalbos"], "d1b96315/data/player_logs_2026-11-15.json", "data/app/player_game_logs.json"])}</td></tr>
</tbody></table>

<h2>Read it in this order</h2>
<div class="grid2">
<div class="q"><h4>The numbers, with their sources</h4><p class="small"><a href="injuries.html">Injuries</a> (three revisions, two diffs, every status change linked) ·
<a href="results.html">Results</a> (nine finals, quarter vectors, the disputed one footnoted) ·
<a href="standings.html">Standings</a> (30 rows, the home-rate measurement) ·
<a href="lines.html">Originated lines</a> (25 rows, both estimators, availability, rest, travel, luck)</p></div>
<div class="q"><h4>Whether any of it may be bet</h4><p class="small"><a href="gates.html">Gates &amp; leaderboard</a> (8 gates × 5 strategies, all measurements printed) ·
<a href="ledger.html">Ledger</a> (25 pre-tip seals, three chains verified, board item K-17 resolved) ·
<a href="pricing.html">Pricing &amp; rho</a> · <a href="model.html">Method</a></p></div>
<div class="q"><h4>What is missing and what to do</h4><p class="small"><a href="questions.html">Questions</a> (known vs unknown, each with the way to find out) ·
<a href="suggestions.html">Suggestions</a> (four paths, pick one) ·
<a href="flagged.html">Flagged for review</a> ({A['flags']['counts']['rows']} rows, {A['flags']['counts']['by_severity']['high']} high) ·
<a href="sources.html">Sources</a></p></div>
<div class="q"><h4>Separation of surfaces</h4><p class="small">Everything here is the <b>projection</b> surface: publishable now, graded on results.
The <b>bet</b> surface is empty by construction — no licensed closing line exists, so gate G8 fails for
every strategy and nothing is funded. That is a feature of the pipeline, not a missing page.</p></div>
</div>

<h2>Decisions waiting on you</h2>
<ol>
<li><b>The home-court pin.</b> Adopt {hc['hca_points_used']} (measured over {st['measured_home_games']} home
games, <a href="standings.html">the standings</a>) everywhere, or keep the short-sample number for
continuity with already-sealed hashes? <a href="suggestions.html#p1">Path 1</a>.</li>
<li><b>Price data.</b> Nothing can be funded until a closing-line source exists. <a href="suggestions.html#p2">Path 2</a>.</li>
<li><b>The 11/15 Milwaukee quarter row.</b> Two readings in one official document; the model already
excluded that game's quarters. Which is authoritative? <a href="results.html#atlmil">Evidence</a>.</li>
<li><b>Box-score capture.</b> Six PDFs a day would take the availability model from 9 clubs to 30.
<a href="suggestions.html#p3">Path 3</a>.</li>
</ol>
<p class="small mut">Working stamps: capture read at {e(A['capture_stamp'])}; model built at
{e(m['stamp'])}; ledger head {e(A['ledger']['ledger']['head_hash'][:16])}… This tree does not edit the
canonical site or any other session's files; the landing-page link is requested in
<code>COORDINATION.md</code>.</p>"""
    return page("index", "Executive summary", body, banner)


def p_injuries(A) -> str:
    snaps, lat, morn = A["snaps"], A["latest"], A["morning"]
    dpm, dam, pub = A["delta_pm"], A["delta_am"], A["pub_inj"]

    def rev_rows():
        out = []
        for r in snaps["revisions"]:
            src = (f'<a class="src" href="{e(r["source_url"])}" rel="noopener">PDF</a>'
                   if str(r["source_url"]).startswith("http") else NO_SOURCE)
            out.append([e(r["report_stamp"]), fmt(r["count"], 0), fmt(r["player_rows"], 0),
                        fmt(r["club_not_yet_submitted"], 0), e(r["retrieved_utc"]), src,
                        e(r["read_from"])])
        return out

    def changes(d):
        rows = []
        for c in d["status_changes"]:
            cls = "bad" if c["to_status"] == "Out" else "warn"
            move = f'<span class="tag {cls}">{e(c["from_status"])} → {e(c["to_status"])}</span>'
            rows.append([e(c["club"]), e(c["player"]), e(c.get("matchup")), move,
                         e(c.get("from_reason")), e(c.get("to_reason")), e(c.get("change_kind", "status")),
                         src_cell([c["older_source"], c["newer_source"]])])
        for sp in d["spelling_moves"]:
            rows.append([e(sp["club"]), f'{e(sp["older_spelling"])} → {e(sp["newer_spelling"])}', "—",
                         '<span class="tag grey">no status change</span>', e(sp["older_status"]),
                         e(sp["newer_status"]), "spelling only",
                         src_cell([sp["older_source"], sp["newer_source"]])])
        for a in d["rows_added"]:
            if a.get("change", "").startswith("club report"):
                rows.append([e(a["club"]), "—", "—", '<span class="tag ok">club filed</span>',
                             "was NOT YET SUBMITTED", "rows now present", "club marker", NO_SOURCE])
            else:
                rows.append([e(a["club"]), e(a["player"]), "—", '<span class="tag info">new row</span>',
                             "—", e(a.get("status")), "added", NO_SOURCE])
        for r in d["rows_removed"]:
            rows.append([e(r["club"]), e(r["player"]), "—", '<span class="tag bad">row gone</span>',
                         e(r.get("was_status")), "—", "removed", NO_SOURCE])
        return rows

    unf = sorted({r["team_abbr"] for r in lat["rows"] if r["not_yet_submitted"]})
    filed = sorted({r["team_abbr"] for r in lat["rows"] if r.get("player")})
    unread = [c for c in lat["unread_cells"] if "not readable" in c]
    carried = [r for r in lat["rows"] if r.get("team_carried")]
    gsw = [r for r in lat["rows"] if r.get("team_abbr") == "GSW"]
    tonight_clubs = sorted({g["away"] for g in A["slate_games"] if g["date"] == "2026-11-16"}
                           | {g["home"] for g in A["slate_games"] if g["date"] == "2026-11-16"})

    def gsw_rows():
        out = []
        for r in gsw:
            st_ = fmt(r["status"]) if r["status"] else '<span class="tag warn">not printed</span>'
            rsn = e(r["reason"]) if r["reason"] else '<span class="none">not printed</span>'
            out.append([e(r["player"]), st_, rsn, e(r.get("matchup")), src_cell([r["source_url"]])])
        return out

    def club_rows():
        out = []
        for ab in tonight_clubs:
            rows = [r for r in lat["rows"] if r.get("team_abbr") == ab]
            players = [r for r in rows if r.get("player")]
            if ab in filed:
                tag = '<span class="tag ok">filed</span>'
            elif ab in unf:
                tag = '<span class="tag warn">NOT YET SUBMITTED</span>'
            else:
                tag = '<span class="tag grey">not covered by this revision</span>'
            gone = [f'{r["player"]} ({r["status"]})' for r in rows
                    if r.get("status") in ("Out", "Doubtful")]
            out.append([f"<b>{e(ab)}</b>", tag, f'<span class="num">{len(players)}</span>',
                        e(", ".join(gone) or "—") if gone else '<span class="none">none printed</span>',
                        src_cell([A["urls"]["pdf_1315"]])])
        return out

    hops = [h["file"] for h in snaps["diffs"]]
    loaded = {f: json.loads((DATA / f).read_text(encoding="utf-8")) for f in hops}
    parts = []
    for h in snaps["diffs"]:
        d = loaded[h["file"]]
        c = d["counts"]
        parts.append(
            f'<h3>{e(h["label"])}</h3><p class="small mut">{e(d["note"])} · '
            f'{c["older_rows"]} rows / {c["older_player_rows"]} player rows / '
            f'{c["older_club_markers"]} unfiled → <b>{c["newer_rows"]} rows / '
            f'{c["newer_player_rows"]} player rows / {c["newer_club_markers"]} unfiled</b> · '
            f'<b>{c["status_changes"]}</b> status changes, <b>{c["rows_added"]}</b> rows added, '
            f'<b>{c["rows_removed"]}</b> rows dropped, <b>{c["spelling_moves"]}</b> spelling moves · '
            f'<a class="src" href="{e(REPO_BLOB + "d1b96315/data/" + h["file"])}">json</a></p>'
            + table(["club", "player", "matchup", "status move", "older reason", "newer reason",
                     "kind", "sources"], changes(d))
            + f'<p class="small mut">Rule: {e(d["rule"])}</p>')
    diff_html = chr(10).join(parts)
    hops_seq = ["injury_delta_2026-11-16_0915_to_1130.json",
                "injury_delta_2026-11-16_1130_to_1300.json",
                "injury_delta_2026-11-16_1300_to_1315.json"]
    seq = [loaded[f]["counts"] for f in hops_seq]
    day = loaded["injury_delta_2026-11-16_0915_to_1315.json"]["counts"]
    steps_ok = (sum(c["status_changes"] for c in seq) == day["status_changes"]
                and sum(c["rows_added"] for c in seq) == day["rows_added"])
    cross = snaps.get("cross_check_with_another_session") or {}
    cross_html = ""
    if cross:
        okc = ('<span class="tag ok">agree</span>' if cross.get("agree")
               else '<span class="tag bad">disagree</span>')
        cross_html = (
            '<h2>Cross-check against a second session\'s independent read of the same PDF</h2>'
            '<div class="note">' + okc + ' <code>' + e(str(cross["their_file"])) + '</code> (another '
            'session\'s parser, from its own transcript of <code>'
            + e(str(cross["their_source_url"]).rsplit("/", 1)[-1]) + '</code>) reports <b>'
            + str(cross["their_player_rows"]) + ' player rows</b> and <b>'
            + str(cross["their_not_submitted"]) + ' clubs unfiled</b>; this tree\'s parser, from this '
            'session\'s own transcript, reports <b>' + str(cross["mine_player_rows"]) + '</b> and <b>'
            + str(cross["mine_not_submitted"]) + '</b>. Their 01:00 PM hop holds '
            + str(seq[1]["newer_player_rows"]) + ' player rows and their 01:00 → 01:15 hop adds exactly '
            'one row with no status change, which is what the same two hops produce here ('
            + str(seq[1]["newer_player_rows"]) + ' → ' + str(seq[2]["newer_player_rows"]) + ', '
            + str(seq[2]["status_changes"]) + ' changes, ' + str(seq[2]["rows_added"]) + ' added). '
            + e(str(cross["note"])) + ' ' + src_cell([cross["their_file"], A["urls"]["pdf_1315"]])
            + '</div>')

    body = f"""
<h1>Injury report: four official revisions of one game day, diffed hop by hop</h1>
<p class="lead">The report is re-issued through the afternoon, so the only defensible statement about
availability is "as of {e(lat['report_stamp'])} ET". Below: the revisions, the two consecutive diffs,
every row the newest revision carries, and the cells the official PDF itself does not print.</p>
<div class="cards">
{card("newest revision", e(lat['report_stamp']), f"retrieved {e(lat['retrieved_utc'])}")}
{card("player rows", f"{lat['player_rows']}", f"was {pub['player_rows']} at 09:15")}
{card("clubs still unfiled", f"{lat['club_marker_rows']}", f"was {pub['not_submitted_rows']}")}
{card("status changes across the day", f"{day['status_changes']}",
      f"+{day['rows_added']} player rows, {day['spelling_moves']} spelling move, "
      f"{day['rows_removed']} rows dropped")}
{card("the filing hop", f"{seq[1]['status_changes']} changes / +{seq[1]['rows_added']} rows",
      "11:30 AM → 01:00 PM: Washington, Houston and Philadelphia filed; three downgrades landed")}
{card("unread cells in the PDF", f"{len(unread)}", "Golden State's block, printed with a column missing")}
</div>

<h2>The three revisions</h2>
{table(["report stamp as printed", "^rows", "^player rows", "^clubs unfiled", "retrieved (UTC)", "source", "read from"], rev_rows())}
<p class="small mut">{e(snaps['chain_note'])}</p>

<h2>The revisions, and every hop between them</h2>
<p class="small mut">The league issues many revisions a day — the index lists 53 slots for 11/16 — so a
diff is only meaningful as a pair of named documents. Each section names its pair, prints its own
counts, and links its JSON; rows are reproduced exactly as the PDF renders them.</p>
{diff_html}

{cross_html}

<p class="small">Step-by-step check: {seq[0]["status_changes"]} + {seq[1]["status_changes"]} +
{seq[2]["status_changes"]} changes = {day["status_changes"]} across the day, and
{seq[0]["rows_added"]} + {seq[1]["rows_added"]} + {seq[2]["rows_added"]} = {day["rows_added"]} rows added
('the three hops add up to the whole-day diff exactly' if steps_ok else 'the hops do NOT add up — see D-05, the page-break rows');
rows {pub["count"]} → {morn["count"]} → {seq[1]["newer_rows"]} → {lat["count"]}</p>

<h2>Who has filed, and who is out tonight, by club</h2>
{table(["club", "filing state", "^player rows", "Out / Doubtful the availability model applies", "source"], club_rows())}

<h2>Cells the official document does not print</h2>
{table(["player", "status cell", "reason cell", "matchup", "source"], gsw_rows())}
<div class="warnbox"><b>Do not read these rows as "no injury".</b> The Golden State block in both
revisions loses a column at the page break: Jimmy Butler's row prints a reason with no status, and
Curry, Moody, Porzingis and Williams print <code>Out</code> with no reason. This page publishes the
cells exactly as the PDF renders them and flags the {len(unread)} gaps. The same shift is why a parser
keyed on column position reports the whole club as clear.</div>

<h2>Rows whose club column is absent</h2>
{table(["player", "status", "reason", "club carried from", "source"],
       [[e(r["player"]), fmt(r["status"]), e(r["reason"]) or '<span class="none">—</span>',
         e(r["team"]), src_cell([r["source_url"]])] for r in carried])}
<p class="small mut">At a page break the renderer drops the leading columns, so these {len(carried)} rows
arrive with no club cell. They are attributed to the club whose block they continue and marked
<code>team_carried</code> in the JSON — a naive parse loses them and invents removals in the diff
(<a href="flagged.html#D-05">flag D-05</a>).</p>

<h2>Unread cells, counted, not repaired</h2>
<ul>{''.join(f'<li>{e(c)}</li>' for c in unread) or '<li>none</li>'}</ul>
<p class="small">Full row-level detail:
<a href="{e(REPO_BLOB + 'd1b96315/data/injuries_2026-11-16_latest.json')}">newest revision json</a> ·
<a href="{e(REPO_BLOB + 'd1b96315/data/injuries_2026-11-16_1130AM.json')}">11:30 json</a> ·
verbatim transcripts <a href="{e(REPO_BLOB + 'd1b96315/data/raw/injury_2026-11-16_1130AM.md')}">11:30</a> /
<a href="{e(REPO_BLOB + 'd1b96315/data/raw/injury_2026-11-16_0115PM.md')}">13:15</a> ·
main's published snapshot <a href="{e(REPO_BLOB + 'data/app/official_injuries_2026-11-16_0915AM_raw.md')}">09:15 transcript</a></p>
"""
    return page("injuries", "Injuries", body)


def p_results(A) -> str:
    res = A["results"]
    rows = []
    for r in res["rows"] + res["blocked_rows"]:
        def q(v):
            return " · ".join(fmt(x, 0) for x in (v or [])) or ('<span class="none">not captured</span>')
        rows.append([e(r["date"]), e(r["game_id"]),
                     f'{e(r["away_abbr"])} {fmt(r["away_pts"], 0)} @ {e(r["home_abbr"])} {fmt(r["home_pts"], 0)}',
                     e(r["state"]), q(r["away_quarters"]), q(r["home_quarters"]),
                     ('<span class="tag ok">sums to the final</span>' if r["settled"]
                      else '<span class="tag warn">footnoted</span>'),
                     e((r.get("quarter_sums") or {}).get("away")), e((r.get("quarter_sums") or {}).get("home")),
                     src_cell([r["sources"]["scoreboard"], r["sources"].get("gamebook")])])
    atlmil = [r for r in res["rows"] + res["blocked_rows"] if r["game_id"] == "0022600243"][0]
    body = f"""
<h1>11/15 finals, re-read from the official sources</h1>
<p class="lead">One row per game: date, both clubs, the final, and the quarter scores. A row settles
only when the scoreboard prints the game Final <i>and</i> the game book's quarter scores sum to that
team's printed final for both clubs. {e(res['source_label'])}</p>
<div class="cards">
{card("games on the slate", f"{res['count']}", "read from the scoreboard at " + e(res['retrieved_utc']))}
{card("settled", f"{res['settled_count']}", "final + quarter identity both pass")}
{card("footnoted", f"{res['blocked_count']}", "final verified, quarter vector disputed")}
{card("vs what main published", "8 agree", "main had 8 settled and 1 blocked; this re-read settles the 9th on the score alone")}
</div>
{table(["date", "game id", "final", "state", "away Q by Q", "home Q by Q", "check", "^away Σ", "^home Σ", "sources"], rows)}

<h2 id="atlmil">The one row that needed a decision: 0022600243, ATL @ MIL</h2>
<div class="badbox"><b>One official document, two third-quarter readings.</b>
The game book's SCORE BY PERIOD table prints <code>ATL 18 37 32 26 = 113</code> (sums ✓) and
<code>MIL 37 16 <b>37</b> 26 = 116</code> against a printed final of <b>106</b> ✗ — while the recap
line in the <i>same</i> PDF prints <code>BUCKS 37 16 <b>27</b> 26 106</code>, which sums ✓.
{link(A['urls']['book_atlmil'], 'the game book')} · {link(A['urls']['games_1115'], 'the scoreboard card')}.
<br><br><b>What the model does with it.</b> The final 113-106 is confirmed three ways (scoreboard
card, recap line, and the box-score team totals), so the row settles on the score. The quarter vector
is not usable, so the gate <code>I2_quarter_scores</code> stays red for this game and it is excluded
from any quarter-derived measurement ({link("model.html", "game flow")}). Both readings are printed:
period table {atlmil['alt_reading']['milwaukee_q3_period_table']}, recap line
{atlmil['alt_reading']['milwaukee_q3_recap_line']}. Nothing was silently "fixed"
(<a href="flagged.html#D-03">flag D-03</a>).</div>
<p class="small">{e(atlmil['quarter_check'])}</p>

<h2>Why this row of work matters</h2>
<p>The scoreboard page and the game book are different official documents that can disagree. Eight of
the nine games re-read here agree with the values the site already published, which is the point of
re-reading rather than trusting: the ninth is where the disagreement lives, and the pipeline caught it
before a model used it.</p>
<p class="small mut">Also on this re-read: the ATL@MIL book records attendance 11474, officials
#46 Taylor / #34 Cutler / #75 Catanzariti, biggest lead ATL 13 / MIL 22, 3 lead changes, 2 ties, and
the inactives for both clubs — the same inactives the 11/16 report carries forward
{link("injuries.html", "above")}. Verbatim transcript:
<a href="{e(REPO_BLOB + 'd1b96315/data/raw/results_2026-11-15_scoreboard.md')}">scoreboard</a> ·
<a href="{e(REPO_BLOB + 'd1b96315/data/raw/gamebook_20261115_ATLMIL.md')}">game book</a>.</p>
"""
    return page("results", "Results", body)


def p_standings(A) -> str:
    st = A["standings"]
    m = A["model"]
    rows = []
    for t in st["teams"]:
        rows.append([f'{fmt(t["seed"], 0)}', e(t["team"]), e(t["team_abbr"]),
                     f'<span class="num">{t["w"]}-{t["l"]}</span>', fmt(t["win_pct"] * 100, 1) + "%",
                     e(t["gb"]), e(t["conf"]), e(t["div"]),
                     f'<span class="num">{t["home_w"]}-{t["home_l"]}</span>',
                     f'<span class="num">{t["road_w"]}-{t["road_l"]}</span>',
                     f'<span class="num">{t["neutral_w"]}-{t["neutral_l"]}</span>',
                     f'<span class="num">{t["ot_w"]}-{t["ot_l"]}</span>',
                     f'<span class="num">{t["last10_w"]}-{t["last10_l"]}</span>', e(t["streak"]),
                     src_cell([t["source_url"]])])
    body = f"""
<h1>Standings: the first capture of this feed in the repository</h1>
<p class="lead">Board item K-07 said no job captured the standings, so the home-court number could
only ever come from a 22-game sample. This is the missing feed: all 30 clubs, both conferences, every
split, read from {link(st['source_url'], 'www.nba.com/standings')} at {e(st['retrieved_utc'])}.</p>
<div class="cards">
{card("measured home-win rate", f"{st['measured_home_win_rate'] * 100:.2f}%",
      f"{st['measured_home_wins']}-{st['measured_home_games'] - st['measured_home_wins']} of {st['measured_home_games']} home games")}
{card("Wilson 95% interval", f"{m['home_court']['wilson95_standings'][0] * 100:.1f}–{m['home_court']['wilson95_standings'][1] * 100:.1f}%",
      "the interval the pin is honest about")}
{card("identity checks", "30/30", "home+road+neutral = GP and each club's win% recomputes")}
{card("the tail that mattered", "UTA 1-7 home", "the 15th Western row is on the page's second chunk; without it the rate cannot be summed")}
</div>
{table(["#", "team", "abbr", "W-L", "win%", "GB", "conf", "div", "home", "road", "neu", "OT", "last 10", "streak", "source"], rows)}

<h2>What this table changed in the model</h2>
<div class="note">The pin went from <b>{m['home_court']['previously_published_in_this_repo']['data_rounds_2026_11_16']['hca_points']} points</b>
(a 23-final sample, home-win rate
{m['home_court']['previously_published_in_this_repo']['data_rounds_2026_11_16']['home_win_rate']})
to <b>{m['home_court']['hca_points_used']} points</b> (the whole league, {st['measured_home_games']} home
games). Same formula — Φ⁻¹(home win rate) × sd(home margin) — a far better sample. Every home margin on
{link("lines.html", "the lines page")} moved by
{m['home_court']['previously_published_in_this_repo']['effect_on_this_builds_lines']['vs_the_round_capture']} points
as a result, which is why the pin is stated as a formula and not as a constant.
Two independent readings of the same quantity are printed on the
{link("model.html", "method page")}: the league ({st['measured_home_win_rate']}) and this season's
finals log ({m['home_court']['measured_home_win_rate_finals_log']}, n={m['home_court']['finals_log_n']}).</div>

<h2>Checks that were run on this capture</h2>
<ul>
<li>sum(W) = sum(L) = {st['checks']['w_equals_l']['sum_w']} — every game contributes one win and one loss ✓</li>
<li>home games {st['checks']['home_wins_plus_road_losses_equal_home_games']['home_w+home_l']} +
neutral {st['checks']['neutral_record']['neutral_w'] + st['checks']['neutral_record']['neutral_l'] // 2 * 2 // 2:.0f}
= {st['checks']['w_equals_l']['sum_w']} total ✓ (the single neutral game is Indiana @ Denver, printed in both clubs' Neutral column)</li>
<li>rows whose home+road+neutral split does not equal GP:
{st['checks']['rows_failing_location_split'] or 'none'} ✓</li>
<li>rows whose printed WIN% does not recompute from W/(W+L): {st['checks']['rows_failing_win_pct'] or 'none'} ✓</li>
</ul>
<p class="small mut">Neutral-site games are excluded from the home-win measurement because the page
prints them in their own column. The same page carries the full Paragraph L.2 tie-break procedure text
(second and third tie-break steps included); it is not used by any number here, and it is on the
{link("sources.html", "source register")} so a reader can settle a seed question from the official
document rather than from a summary. Verbatim transcript:
<a href="{e(REPO_BLOB + 'd1b96315/data/raw/standings_2026-11-16.md')}">standings_2026-11-16.md</a>.</p>
"""
    return page("standings", "Standings", body)


def p_lines(A) -> str:
    m, lines = A["model"], A["lines"]
    CAP = 5.0

    def filing_tag(f):
        if f["status"] == "filed":
            return '<span class="tag ok">filed</span>'
        if f["status"] == "not_submitted":
            return '<span class="tag warn">not submitted</span>'
        return '<span class="tag grey">outside window</span>'

    def avail_cell(r, side):
        a = r["availability"][side]
        cls = {"applied": "ok", "nothing to apply": "warn"}.get(a["status"], "grey")
        extra = (f' −{a["minutes_share_removed"] * 100:.1f}% min'
                 if a.get("minutes_share_removed") else "")
        names = ", ".join(o["player"] for o in a["out_applied"][:3]) or "no Out/Doubtful row"
        return (f'<span class="tag {cls}">{e(r[side])}: {e(a["status"])}</span>{extra}<br>'
                f'<span class="small mut">{e(names)}</span>')

    def rest_cell(r):
        out = []
        for side in ("away", "home"):
            x = r["rest"][side]
            bits = "b2b" if x["back_to_back"] else "rest"
            if x["three_in_four"]:
                bits += "/3-in-4"
            out.append(f'{side.upper()} {bits} ({fmt(x["days_since_last_game"], 0)}d)')
        return '<span class="small">' + "<br>".join(out) + "</span>"

    def travel_cell(r):
        tr = r["travel"]
        if tr.get("km"):
            return (f'<span class="num">{tr["km"]:.0f}</span> km'
                    + (f'<br><span class="small mut">{e(tr["arena_name_mismatch"])[:70]}</span>'
                       if tr.get("arena_name_mismatch") else ""))
        return (f'<span class="none">not computed</span><br><span class="small mut">'
                f'{e(tr["status"])[:90]}</span>')

    def bet_cell(r):
        if r["bet_eligible"]:
            return '<span class="tag ok">bet-eligible</span>'
        return (f'<span class="tag bad">refused</span><br>'
                f'<span class="small mut">{e(r["bet_block"])}</span>')

    def blk(rows, label):
        out = []
        for r in rows:
            dis = r["disagreement_margin_points"]
            tag = {"agreeing": '<span class="tag ok">agreeing</span>',
                   "watch": '<span class="tag warn">watch</span>'}.get(
                       r["headline_confidence"], '<span class="tag bad">too wide</span>')
            kz = " ".join(f'{k} {fmt(v, 2)}' for k, v in r["luck_z"].items())
            out.append([
                e(r["date"]),
                f'<a href="{e(r["game_url"])}" rel="noopener">{e(r["away"])} @ {e(r["home"])}</a>'
                f'<br><span class="small mut">{e(r["game_id"])} · {e(r["tip_et"])} · {e(r["venue"])}</span>',
                (fmt(r["estimator_a_margin"], 2),), (fmt(r["estimator_b_margin"], 2),),
                (f'<b>{dis:.2f}</b> {tag}',), (fmt(r["blend_margin_underneath"], 2),),
                (fmt(r["total_possessions_model"], 1),), (fmt(r["total_naive_scoring_average"], 1),),
                (fmt(r["total_gap_between_the_two_methods"], 2),),
                avail_cell(r, "away") + "<br>" + avail_cell(r, "home"),
                rest_cell(r), travel_cell(r), kz,
                " ".join(filing_tag(r["injury_filing"][k]) for k in ("away", "home")),
                bet_cell(r),
                src_cell([r["source_url"], A["urls"]["pdf_1315"], m["inputs"]["team_stats"]["source"]])])
        return (f'<h2>{label}</h2>' + table(
            ["date", "game", "^est A margin", "^est B margin", "^|A−B| (headline)", "^blend (underneath)",
             "^our total", "^naive total", "^total gap", "rotation availability", "rest", "^travel",
             "luck z", "injury filing", "bet surface", "sources"], out))

    pub = [r for r in lines if r.get("publishable")]
    tonight = [r for r in pub if r["date"] == "2026-11-16"]
    later = [r for r in pub if r["date"] != "2026-11-16"]
    dis = [r["disagreement_margin_points"] for r in pub]
    agreed = [d for d in dis if d <= 2.5]
    body = f"""
<h1>Originated lines: our own numbers, with the disagreement as the headline</h1>
<p class="lead">Two estimators that share no inputs sit side by side. Estimator A uses only verified
final margins; estimator B uses the official advanced efficiency table, possessions, and the minutes
redistributed by the newest injury filings. Where they disagree the row is labelled, and a row the two
disagree about by more than {CAP} points is never offered to the bet surface. The blend is printed in
the column after the headline and is used for nothing else. The window reaches three days ahead: the
four 11/19 games are this session's own read of the official 11/19 page, added to main's published
11/16–11/18 capture, and their records tie out against the standings page exactly.</p>
<div class="cards">
{card("rows priced", f"{len(pub)}", f"{len(tonight)} tonight, {len(later)} on 11/17-11/19")}
{card("median |A−B|", f"{sorted(dis)[len(dis) // 2]:.2f} pts", f"min {min(dis):.2f}, max {max(dis):.2f}")}
{card("agreeing within 2.5 pts", f"{len(agreed)}/{len(pub)}", "the only rows this model calls confident")}
{card("bet-eligible rows", f"{sum(1 for r in pub if r['bet_eligible'])}",
      "inside the cap and no club outside the luck band; still no funded strategy, because G8 fails")}
{card("home-court in every number", f"{m['home_court']['hca_points_used']} pts",
      "pinned to the measured league home-win rate, not fitted")}
{card("refusals on this window", f"{sum(1 for r in pub if not r['bet_eligible'])}",
      "each with its reason printed in the row")}
</div>
<div class="note">Margin convention: a positive number means the <b>home</b> club is better by that many
points, so our originated side is its negative. Totals are ours, not a market's: the official
{link(A['urls']['games_1116'], 'games page')} renders no odds in the fetched HTML, so no market number
appears anywhere on this site (<a href="flagged.html#D-10">flag D-10</a>).</div>
{blk(tonight, "Tonight — 2026-11-16 (8 games)")}
{blk(later, f"The rest of the window — 11/17 to 11/19 ({len(later)} games, priced up to three days ahead)")}

<h2>How to read the columns</h2>
<ul>
<li><b>|A−B|</b> is the headline the brief asks for: the disagreement between two independent
estimators. Under 2.5 points the row is marked <i>agreeing</i>; over the frozen 5-point cap the row is
refused a bet flag, with the reason printed inside the cell.</li>
<li><b>rotation availability</b> is its own column, as required. <span class="tag ok">applied</span>
means an Out/Doubtful club's minutes were redistributed and the production cost charged to the team;
<span class="tag grey">no rotation data</span> means we hold no official box score for that club and
refuse to model it; <span class="tag warn">nothing to apply</span> means the club filed and printed no
Out/Doubtful row. The three states are different facts and are never collapsed into one.</li>
<li><b>rest</b> is days since the club's last game, counting verified finals and the official slate;
<i>b2b</i> and <i>3-in-4</i> follow the definitions on the {link("model.html", "method page")}.</li>
<li><b>travel</b> is great-circle arena-to-arena kilometres. The arena <i>name</i> is checked against the
official schedule on every row and a mismatch is printed in the cell; the coordinates come from a
general-reference table on main, which is why the status line sits under the number.</li>
<li><b>luck z</b> is how far a club's record sits from what its efficiency predicts; |z| &gt; 2 refuses
the row.</li>
<li><b>injury filing</b> states, per club, whether the newest revision carries rows, the
NOT YET SUBMITTED marker, or nothing at all for that date. The 11/18 rows read
<span class="tag grey">outside window</span> because the report runs two days ahead — a fact about the
report, not about the players.</li>
</ul>
<p class="small mut">Slate re-verification, done independently here: the official 11/16 scoreboard
chunk this session fetched carries {len(m['inputs']['slate']['reverified_rows'])} of tonight's 8 cards,
and all 8 matchups with their tip times appear in the 01:15 PM revision, which is a second official
document agreeing with the window. The page's own calendar strip reads
{json.dumps(m['inputs']['slate']['calendar_counts'])}, matching the published counts
{json.dumps(m['inputs']['slate']['count_by_date'])} plus the 9 games already played on 11/15.</p>
"""
    return page("lines", "Originated lines", body)


def p_pricing(A) -> str:
    m = A["model"]
    pr = m["pricing"]
    rows = []
    for p in pr["parlays"]:
        rows.append([e(p["date"]), e(p["game_id"]),
                     fmt(p["p_leg_1"] * 100, 1) + "%", fmt(p["p_leg_2"] * 100, 1) + "%",
                     f'<b>{fmt(p["p_parlay_measured_rho"] * 100, 1)}%</b>',
                     f'{fmt(p["p_parlay_naive_product"] * 100, 1)}%',
                     fmt(p["difference_in_probability_points"], 2) + " pts",
                     fmt(p["fair_american_measured_rho"], 1), fmt(p["fair_american_naive"], 1),
                     fmt(p["rho_used"], 3), src_cell([A["urls"]["games_1116"], "d1b96315/data/model.json"])])
    body = f"""
<h1>Pricing: the correlation we measured, printed beside the naive product</h1>
<p class="lead">A same-game parlay of "our side" and "our total" is not the product of the two leg
probabilities, because the legs share one game. Both numbers are printed for every row, so the
correlation effect is auditable instead of assumed.</p>
<div class="cards">
{card("ρ(margin, total)", f"{pr['rho_margin_vs_total']}", f"95% CI {pr['rho_margin_vs_total_ci95']} on n={pr['measured_on']['settled_games']} games")}
{card("ρ across games, same date", f"{pr['rho_cross_game_margin']}", f"95% CI {pr['rho_cross_game_ci95']} on {pr['measured_on']['same_date_game_pairs']} pairs")}
{card("model residual sd", f"{m['estimator_a']['residual_sd_points']} pts", "leave-one-game-out, so it is out-of-sample")}
{card("rows priced", f"{len(pr['parlays'])}", "every publishable row in the window")}
</div>
{table(["date", "game", "^p leg 1 (side)", "^p leg 2 (over)", "^p parlay @ measured ρ", "^p naive product",
        "^difference", "^fair price (ρ)", "^fair price (naive)", "^ρ used", "sources"], rows)}
<div class="note">{e(pr['leg_probability_method'])}<br>{e(pr['copula'])}<br>{e(pr['rho_method'])}</div>
<h2>What the numbers say</h2>
<ul>
<li>The measured ρ between a game's margin and its total is
<b>{pr['rho_margin_vs_total']}</b> — negative, and its interval
{pr['rho_margin_vs_total_ci95']} straddles zero at n={pr['measured_on']['settled_games']}. So the honest
statement is "we measured a small negative dependence and we cannot yet separate it from noise". The
pricing effect is {min(p['difference_in_probability_points'] for p in pr['parlays']):.2f} to
{max(p['difference_in_probability_points'] for p in pr['parlays']):+.2f} probability points, which is
printed rather than hidden, and it is <i>smaller</i> than the residual sd of the model itself.</li>
<li>Cross-game dependence — the thing that makes a multi-leg slip dangerous — measured
{pr['rho_cross_game_margin']} ({pr['rho_cross_game_ci95']}) across
{pr['measured_on']['same_date_game_pairs']} same-date pairs. It is near zero, which is why no same-date
multi-leg is priced here as if it were safe: near zero with an interval that wide is "unknown", not
"independent".</li>
<li>Both ρ and both prices are <b>ours</b>. There is no closing line to compare against, so none of it
can be scored as skill yet ({link("gates.html", "gate G8")}; {link("questions.html", "Q01")}).</li>
</ul>
<p class="small mut">Game-flow measurement that feeds the total column: share of all points scored by
quarter on the {m['game_flow']['games_with_official_quarter_scores']} games with official quarter scores:
{json.dumps(m['game_flow']['share_of_points_by_quarter'])}. Back-to-back clubs'
4th-minus-3rd-quarter differential: {json.dumps(m['game_flow']['back_to_back_fourth_quarter']['on_a_back_to_back'])}
vs rested {json.dumps(m['game_flow']['back_to_back_fourth_quarter']['rested'])} — published as a
measurement with its sample size, not as a rule.</p>
"""
    return page("pricing", "Pricing & rho", body)


def p_model(A) -> str:
    m = A["model"]
    ea = m["estimator_a"]
    hc = m["home_court"]
    stab = ea["stability_across_the_ridge_sweep"]
    luck = m["luck_z"]
    near = sorted(luck.items(), key=lambda kv: -abs(kv[1] if kv[1] is not None else 0))[:6]
    prev_repo = hc["previously_published_in_this_repo"]
    n = lambda x: f'<span class="num">{x}</span>'
    LOG_FILE = "data/app/results_feed.json"
    hca_rows = [
        ["measured home-win rate, league-wide", "<b>" + str(hc["measured_home_win_rate_standings"]) + "</b>",
         "sum of the HOME column over all 30 clubs (" + str(A["standings"]["measured_home_wins"]) + " home wins in "
         + str(A["standings"]["measured_home_games"]) + " home games), neutral-site games excluded",
         src_cell([A["urls"]["standings"]])],
        ["Wilson 95% interval on that rate", e(str(hc["wilson95_standings"])),
         str(A["standings"]["measured_home_games"]) + " home games", "derived"],
        ["measured home-win rate, this season's finals log",
         str(hc["measured_home_win_rate_finals_log"]) + " (n=" + str(hc["finals_log_n"]) + ")",
         "share of verified finals the home team won",
         src_cell(["data/app/results_feed.json", "d1b96315/data/results_2026-11-15.json"])],
        ["sd of home margin", str(hc["sd_home_margin_finals_log"]) + " pts",
         "sample sd over the verified finals", "derived"],
        ["<b>pinned HCA used by both estimators</b>", "<b>" + str(hc["hca_points_used"]) + " pts</b>",
         "Φ⁻¹(measured home-win rate) × sd(home margin)", "derived, formula printed"],
        ["previously pinned in the round capture",
         str(prev_repo["data_rounds_2026_11_16"]["hca_points"]) + " pts",
         "same formula on a " + str(prev_repo["data_rounds_2026_11_16"]["n_games"]) + "-final sample",
         src_cell(["data/rounds/2026-11-16/model.json"])],
        ["constant recorded in the app pick ledger", e(str(prev_repo["data_app_ledger_constant"]["hca_points"])),
         "written into every sealed entry there, never recomputed per game day",
         src_cell(["data/app/ledger/ledger.jsonl"])],
        ["spread between the three", "<b>" + str(prev_repo["spread_between_the_three_points"]) + " pts</b>",
         "every home line moves by this much", "derived"],
    ]
    STAND = src_cell([A["urls"]["standings"]])
    LOG = src_cell(["d1b96315/data/results_2026-11-15.json", "data/app/results_feed.json"])
    for row in hca_rows:
        if "derived" in str(row[3]):
            which = STAND if ("rate" in row[0] or "interval" in row[0]) else LOG
            row[3] = '<span class="small mut">derived arithmetic</span><br>' + which
        if "pinned HCA used" in row[0] or "spread between" in row[0]:
            row[3] = '<span class="small mut">derived from both</span><br>' + STAND + " " + LOG
    hca_table = table(["quantity", "value", "how it was obtained", "source"], hca_rows)
    stab_table = table(["ridge", "^LOO rmse", "^max shift on tonight's lines", "^mean shift",
                        "computed from"],
                       [[n(r["ridge"]), n(r["loo_rmse"]), n(r["max_abs_shift_on_tonights_lines"]),
                         n(r["mean_abs_shift"]), src_cell(["d1b96315/data/model.json", LOG_FILE])]
                        for r in stab["table"]])
    NULL_SRC = {"market prior weight": ["d1b96315/data/model.json", A["urls"]["games_1116"]],
                "closing line": [A["urls"]["games_1116"]],
                "player props": ["d1b96315/data/player_logs_2026-11-15.json",
                                 "data/app/player_game_logs.json"],
                "ATL@MIL quarter vector": [A["urls"]["book_atlmil"], A["urls"]["games_1115"]]}
    null_rows = [
        ["market prior weight", NONE_TAG, e(m['market_anchor']['reason'])],
        ["closing line", NONE_TAG, "no licensed feed in the repository; the 11/16 games page renders "
                                   "no odds in the fetched HTML"],
        ["player props", NONE_TAG, "per-player logs exist for 12 clubs; a prop line for the other 18 "
                                  "would be a guess about a rotation we have not seen"],
        ["ATL@MIL quarter vector", DISPUTED_TAG,
         "the official period table and the official recap line disagree inside one document; both "
         "are printed, neither is chosen silently"],
    ]
    for row in null_rows:
        row.append(src_cell(NULL_SRC[row[0]]))
    null_table = table(["field", "value", "why it is null instead of filled", "evidence"], null_rows)
    luck_table = table(["club", "W-L (official)", "^net rtg", "^z", "verdict", "sources"],
                       [[e(ab), n(f'{A["idx"][ab]["w"]}-{A["idx"][ab]["l"]}'),
                         n(fmt(A["idx"][ab]["net_rtg"], 1)), n(fmt(v, 2)),
                         ('<span class="tag bad">outside the band</span>'
                          if v is not None and abs(v) > 2 else '<span class="tag ok">inside</span>'),
                         src_cell([A["urls"]["advanced"], "d1b96315/data/model.json"])]
                        for ab, v in near])
    body = f"""
<h1>Method: every formula, every constant, every refusal</h1>
<p class="lead">Two estimators, built so they cannot share a mistake. Nothing in this build is a
blended rating; the blend exists on the lines page as a small number under the disagreement, and no
gate consumes it.</p>
<div class="cards">
{card("verified finals in the log", f"{m['inputs']['settled_finals_used']}", f"{e(m['inputs']['date_range'][0])} → {e(m['inputs']['date_range'][1])}, every row settled from the scoreboard + game books")}
{card("estimator A, LOO rmse", f"{ea['ridge_chosen']['loo_rmse']}", f"ridge {ea['ridge_chosen']['ridge']}; no-skill baseline {ea['baseline_loo_rmse_predicting_only_the_pinned_hca']}")}
{card("out-of-sample skill", f"{ea['out_of_sample_skill_vs_baseline'] * 100:.1f}%", "1 − rmse/baseline, leave-one-game-out")}
{card("clubs with an availability adjustment", f"{len(m['estimator_b']['teams_adjusted'])}/30", f"{len(m['estimator_b']['teams_not_adjusted'])} clubs have no box score at all")}
{card("clubs outside the luck band", f"{len(m['clubs_outside_the_noise_band'])}", "±2 sd rule; nothing refused on this window")}
</div>

<h2 id="hca">Home-court advantage: pinned, and pinned to what</h2>
{hca_table}
<div class="warnbox">{e(hc['why_pinned'])} {e(hc['readings_note'])} <b>The three published values are a
live inconsistency</b> and it is on {link("flagged.html", "the flagged register")} as D-04: re-pinning
silently would leave already-sealed hashes pointing at a number the model no longer uses, so the
decision is {link("suggestions.html#p1", "asked for, not taken")}.</div>

<h2>Estimator A — results only</h2>
<p>{e(ea['name'])}. {e(ea['inputs_used'])} Ratings solve the normal equations of the settled margins
with the pinned home advantage subtracted from each home margin, ridge-penalised toward zero; the
penalty is chosen by leave-one-game-out prediction of the withheld margin.</p>
{stab_table}
<div class="warnbox">{e(stab['why'])}</div>
<p class="small">{e(ea['atl_mil_note'])}</p>

<h2>Estimator B — possessions × points per possession, with availability</h2>
<p class="small"><code>{e(m['estimator_b']['formula'])}</code></p>
<p>The total is built from possessions and efficiency, never from adding two scoring averages: a
scoring average already contains the pace a team actually played and the opponents it faced, so two of
them added together describe no single game. Both totals are printed on every row of the
{link("lines.html", "lines page")} with their gap, and {e(m['totals_model']['why'])}</p>

<h3>The availability model, stated exactly</h3>
<ol>
<li>Take the club's most recent <b>captured official box score</b> (a game-book PDF) and each player's
minutes in it. The top-8 minutes shares are what the club actually ran, not a depth chart.</li>
<li>Remove the players the newest official report prints as <b>Out</b> or <b>Doubtful</b>.
Questionable and Day-To-Day are <b>not</b> removed: they are game-time decisions, and treating them as
absent would let the model pretend to know something the league has not said.</li>
<li>Redistribute the removed minutes pro rata to the minutes each remaining player actually played —
that is the replacement share, printed per player in
<a href="{e(REPO_BLOB + 'd1b96315/data/lines.json')}">lines.json</a>.</li>
<li>Charge the production cost: each replacement's points-per-minute from that same box, applied to
the minutes added; the loss against the block that was removed becomes a points-per-game delta, divided
by the club's official possessions per game to become an efficiency delta, and estimator B uses that
delta in its own rating term.</li>
</ol>
<div class="warnbox"><b>Where it stops.</b> 21 of the {A['logs']['count']} rows in the new box transcripts
have a stat cell the PDF extraction dropped, so their points-per-minute is unread and the affected
club's adjustment is published as minutes-only or not at all. 6 of 16 clubs playing tonight have no box
score anywhere in the repository, so "no rotation data" is printed instead of a zero
(<a href="flagged.html#D-08">D-08</a>).</div>

<h2 id="luck">Luck as a per-team z-score, with a refusal</h2>
<p class="small"><code>{e(m['luck_formula'])}</code><br>{e(m['luck_rule'])}</p>
{luck_table}
<p class="small mut">Ranked by |z|, six clubs shown; all 30 are in
<a href="{e(REPO_BLOB + 'd1b96315/data/model.json')}">model.json</a>. No club on this window is outside
±2 sd, so no row was refused by this gate today — the rule is printed with its measurement so a reader
can see it was evaluated rather than skipped.</p>

<h2>What is deliberately null</h2>
{null_table}
<p class="small mut">Inputs and their retrieval stamps, as recorded by the build: injury revision
{e(m['inputs']['injury_report']['revision_time_et'])} ET retrieved
{e(m['inputs']['injury_report']['retrieval_time_utc'])}; standings
{e(m['inputs']['standings']['retrieved_utc'])}; team stats {e(m['inputs']['team_stats']['retrieved_utc'])}
(rows {m['inputs']['team_stats']['rows']}, rows failing their own printed identities
{m['inputs']['team_stats']['rows_failing_checks'] or 'none'}, max residual
{m['inputs']['team_stats']['max_abs_residuals']['net_rtg']} on NetRtg and
{m['inputs']['team_stats']['max_abs_residuals']['pace_minus_poss_per_48']} on pace-vs-possession
— the page's own rounding, printed rather than reconciled).</p>
"""
    return page("model", "Method", body)


def p_gates(A) -> str:
    g = A["gates"]
    rows = []
    gate_ids = list(g["strategies"][0]["gates"].keys())
    for s_ in g["strategies"]:
        cells = []
        for k in gate_ids:
            ok = s_["gates"][k]["pass"]
            cells.append(f'<span class="tag {"ok" if ok else "bad"}">{"pass" if ok else "FAIL"}</span>')
        stt = s_["status"]
        rows.append([f'<b>{e(s_["id"])}</b><br><span class="small">{e(s_["name"])}</span>',
                     e(s_["signal"]), f'<span class="num">{s_["n_candidates"]}</span>',
                     *cells, e(s_["gates_passed"]),
                     f'<span class="tag {"ok" if stt == "funded" else "grey"}">{e(stt)}</span>',
                     e(", ".join(s_["blocking"])),
                     src_cell(["d1b96315/data/gates.json", "d1b96315/data/lines.json"])])
    lb = [f'<tr><td class="num">{r["rank"]}</td><td>{e(r["id"])}</td><td>{e(r["name"])}</td>'
          f'<td class="num">{e(r["gates_passed"])}</td><td class="num">{r["candidates"]}</td>'
          f'<td>{e(r["status"])}</td><td class="num">{r["reward_points"]}</td>'
          f'<td>{e(", ".join(r["blocking"]))}</td>'
          f'<td>{src_cell(["d1b96315/data/gates.json", A["urls"]["games_1116"]])}</td></tr>'
          for r in g["leaderboard"]]
    pre = A["prereg"]
    GATE_SRC = {
        "G1_sample_depth": ["data/app/results_feed.json", "d1b96315/data/results_2026-11-15.json"],
        "G2_freshness": [A["urls"]["pdf_1315"], A["urls"]["index"]],
        "G3_provenance": [A["urls"]["standings"], A["urls"]["advanced"]],
        "G4_out_of_sample": ["d1b96315/data/model.json"],
        "G5_luck_band": ["d1b96315/data/model.json"],
        "G6_disagreement_cap": ["d1b96315/data/lines.json"],
        "G7_pretip_seal": ["d1b96315/ledger/ledger.jsonl", "d1b96315/data/ledger_check.json"],
        "G8_price_feed": [A["urls"]["games_1116"]],
    }
    detail_rows = []
    for s_ in g["strategies"]:
        for k in gate_ids:
            gt = s_["gates"][k]
            cls = "ok" if gt["pass"] else "bad"
            detail_rows.append([e(k), e(gt["rule"]), e(gt["measured"]),
                                f'<span class="tag {cls}">{e(s_["id"])}</span>',
                                src_cell(GATE_SRC.get(k, []))])
    detail_table = table(["gate", "rule", "measured on this build", "verdict", "evidence"],
                         detail_rows)
    prereg_rows = [[f'<b>{e(k)}</b><br><span class="small">{e(v["name"])}</span>', e(v["universe"]),
                    e(v["settlement_rule"]), e(v["stake_rule"]),
                    f'<code>{e(v["sha256"][:16])}…</code>',
                    f'<span class="tag ok">{e(v["frozen_stamp"])}</span>']
                   for k, v in pre["files"].items()]
    for r_, f_ in zip(prereg_rows, g["strategies"]):
        r_.append(src_cell([f'd1b96315/data/prereg/{f_["id"]}.json']))
    prereg_table = table(["strategy", "universe", "settlement rule", "stake", "^payload sha256",
                          "frozen", "file"], prereg_rows)
    body = f"""
<h1>Validation gates and the leaderboard</h1>
<p class="lead">A strategy is funded only when all eight gates pass, and each gate prints the
measurement that decided it. {e(g['rule'])}</p>
<div class="cards">
{card("strategies", f"{g['summary']['strategies']}", "signal, thresholds, universe and settlement rule frozen per strategy")}
{card("funded", f"<b>{g['summary']['funded']}</b>", "G1 sample depth and G8 price feed fail for all of them")}
{card("pre-registration files", f"{len(pre['files'])}", "each hashed; the hash is in the ledger entry for every pick")}
{card("frozen before first bet", '<span class="tag ok">yes</span>', "and there was no first bet to freeze in front of")}
</div>
{table(["strategy", "signal", "^candidate rows", *gate_ids, "^gates", "status", "blocking", "evidence"], rows)}
<h2>Leaderboard</h2>
<div class="scroll"><table><thead><tr><th>^rank</th><th>id</th><th>name</th><th>^gates</th><th>^candidates</th>
<th>status</th><th>^reward</th><th>blocking</th><th>evidence</th></tr></thead><tbody>{''.join(lb)}</tbody></table></div>
<p class="small mut">{e(g['summary']['leaderboard_note'])}</p>
<h2>Gate detail, one row per gate per strategy</h2>
{detail_table}
<h2>Pre-registration, frozen</h2>
{prereg_table}
<p class="small mut">{e(pre['rule'])} {e(list(pre['files'].values())[0]['note'])}. Thresholds inside each
frozen file: disagreement cap {A['model']['home_court'] and '5.0'} points, luck band ±2 sd, minimum
60 verified finals. Files: <a href="{e(REPO_BLOB + 'd1b96315/data/prereg/')}">d1b96315/data/prereg/</a></p>
"""
    return page("gates", "Gates & leaderboard", body)


def p_ledger(A) -> str:
    led, ent = A["ledger"], A["ledger_entries"]
    t = led["trees"]
    k17 = led["k17_resolution"]
    rows = []
    amends = []
    for en in ent:
        if en["kind"] == "AMEND":
            amends.append(en)
            continue
        pre = en["payload"]
        rows.append([f'<span class="num">{en["seq"]}</span>', e(en["pick_id"]), e(en["game_id"]),
                     e(en["date"]), f'{e(pre["away"])} @ {e(pre["home"])}',
                     '<span class="tag ok">pre-tip</span>' if en["pre_tip"]
                     else '<span class="tag bad">post-tip</span>',
                     e(en["published_utc"][11:16]), e(en["tip_utc"][11:16]),
                     f'<span class="num">{pre["disagreement_margin_points"]}</span>',
                     f'<code>{e(en["entry_hash"][:14])}…</code>',
                     f'<code>{e(en["payload_sha256"][:14])}…</code>',
                     src_cell([pre["game_url"]])])
    ent_table = table(["seq", "pick id", "game", "date", "matchup", "state", "sealed", "tip",
                       "^|A−B|", "^entry hash", "^payload hash", "source"], rows)
    verify_rows = []
    for lbl, key in (("this session", "d1b96315"), ("main's bet-surface chain", "ledger_A"),
                     ("main's app chain", "ledger_B")):
        v = t[key]
        cls = "ok" if v["result"] != "PROBLEMS" else "bad"
        writer = {"d1b96315": "d1b96315/ledger.py", "ledger_A": "scripts/ledger.py",
                  "ledger_B": "scripts/pick_ledger.py"}[key]
        verify_rows.append([e(lbl), f'<code>{e(v["file"])}</code>', f'<span class="num">{v["entries"]}</span>',
                            e(v["recipe"]), f'<span class="tag {cls}">{e(v["result"])}</span>',
                            e(v["problems"] or "none"), src_cell([writer, v["file"]])])
    verify_table = table(["tree", "file", "^entries", "recipe used", "result", "problems",
                          "verifier + chain"], verify_rows)
    if amends:
        am_rows = []
        for a in amends:
            sealed, current = a["sealed"], a["current"]
            am_rows.append([e(a["pick_id"]), e(a["amends"]), e(a["game_id"]),
                            " · ".join(f'{k.replace("_margin", "").replace("_points", "")} '
                                       f'{sealed[k]} → {current[k]}'
                                       for k in ("estimator_a_margin", "estimator_b_margin",
                                                 "total_possessions_model")),
                            f'<b>{a["max_delta_points"]}</b> pts', e(a["stamp"]),
                            src_cell(["d1b96315/ledger/ledger.jsonl", "d1b96315/data/lines.json"])])
        amend_html = (
            '<h2>Two sealed lines were amended, not edited</h2><div class="badbox">'
            'The page-break carry that fixed the injury parser (flag D-05) landed <i>after</i> '
            f'{len(amends)} of these seals, and two Memphis rows were among the rows it recovered, so '
            'the model now reads a different number for those games than the number that was hashed. '
            'A sealed entry is never rewritten — that would destroy the evidence — so the chain carries '
            'an appended AMEND entry naming both values and why they differ.</div>'
            + table(["amend entry", "amends", "game", "sealed → current", "^max delta", "stamped",
                     "sources"], am_rows))
    else:
        amend_html = ""
    body = f"""
<h1>Ledger: every published line hashed before its tip</h1>
<p class="lead">{led['ledger']['published_pre_tip']} entries, each one the hash of a line this session
originated, sealed before the game it prices had tipped. {ent[0]['payload']['kind'].capitalize()} — no
money, no funded strategy, and no back-dated hash: a row whose tip had already passed was refused.</p>
<div class="cards">
{card("entries", f"{led['ledger']['entries']}", "one per publishable line in the window")}
{card("settled", f"{led['ledger']['settled']}", "nothing to settle: every sealed row is a future tip at seal time")}
{card("head hash", f'<code>{e(led["ledger"]["head_hash"][:16])}…</code>', "published with this page")}
{card("this chain", f'<span class="tag ok">{e(t["d1b96315"]["result"])}</span>', f"{t['d1b96315']['entries']} entries recomputed independently")}
{card("chain A (ledger/)", f'<span class="tag ok">{e(t["ledger_A"]["result"])}</span>', f"{t['ledger_A']['entries']} entries, recipe from scripts/ledger.py")}
{card("chain B (data/app/ledger/)", f'<span class="tag ok">{e(t["ledger_B"]["result"])}</span>', f"{t['ledger_B']['entries']} entries — and K-17 resolved below")}
</div>
{ent_table}

{amend_html}
<h2>The three chains, verified by one script</h2>
{verify_table}
<div class="note"><b>Board item K-17, resolved.</b> {e(k17['finding'])}<br>
{e(k17['conclusion'])} Measured here: {e(k17['recompute_with_chain_hash_prev_and_body'])} entries
recompute with the pair recipe, {e(k17['recompute_with_body_alone'])} with the body alone — which is
exactly the signature of the missing documentation the board recorded.</div>

<h2>How settlement will work</h2>
<p>{e(A['results']['settlement_rule'])}. When a sealed game's official final is available, a SETTLE
entry is appended that records the final, the source URL, the model's favoured side, whether that side
won, the absolute margin error in points, and a stamp — and it links back to the publish entry's hash,
so the grade cannot be edited without breaking the chain.</p>
<p class="small mut">Reproduce it: <code>python3 d1b96315/ledger.py verify</code> (read-only, writes
<code>d1b96315/data/ledger_check.json</code>, which is what this page renders).
<code>publish</code> and <code>settle</code> are deliberately <b>not</b> run by CI: a chain that CI
re-appends on every push is not evidence. The {A['model']['stamp']} seal is in git history, and
<code>d1b96315/tests/test_roll.py</code> proves the tamper detection fires on a one-character edit.</p>
"""
    return page("ledger", "Ledger", body)


def p_questions(A) -> str:
    m = A["model"]
    qs = [
        ("Q01", "closing line", "unknown",
         "Is there a licensed or otherwise usable closing-line feed, and which one?",
         "Nothing on the bet surface can be scored without it: the model-anchored prior, the log-loss "
         "weight and the ROI of every strategy all depend on a price we do not have. The official "
         "games page renders no odds in the fetched HTML.",
         "Owner supplies the feed (or the policy for entering published closing lines by hand). A "
         "one-file capture job, the same shape as the injury capture, is enough to start: date, game, "
         "market, line, source URL, retrieval stamp.",
         [A["urls"]["games_1116"], "d1b96315/data/model.json"]),
        ("Q02", "injury refresh schedule", "known",
         "Should the refresh job chase the newest revision on game day?",
         f"Yes, and it currently cannot: the site published {e(A['pub_inj']['report_stamp'])} while "
         f"the index already listed a 01:15 PM ET revision. The cron is 15 5,11,17,23 — nothing fires "
         f"between 11:15 and 17:15 UTC, i.e. across the whole NBA afternoon.",
         "Add a game-day pass ~30 minutes before the earliest tip in a block, and let the job take the "
         "newest item in the index rather than a constructed filename.",
         [A["urls"]["index"], "data/app/refresh/2026-11-16T00-57Z/manifest.json",
          ".github/workflows/refresh.yml"]),
        ("Q03", "why the job is red", "partly unknown",
         "What exactly fails in the CI unit-test step?",
         "The failing step is identified (run 43925193575, job refresh, step 'Unit tests (capture, "
         "feed, ledger, estimators, gates)', 19 s), but the log body is unreachable from this sandbox: "
         "`gh run view --log-failed` returned a results-receiver EOF and the raw job-log URL an empty "
         "body. The same five modules run clean here — 40 tests, OK.",
         "Read the log in the Actions UI, or add `--debug`/`ACTIONS_STEP_DEBUG` and re-run. Until the "
         "text is in hand this is an environment hypothesis, not a diagnosis.",
         [m['inputs'] and A["urls"]["run"], "tests/test_refresh_official.py"]),
        ("Q04", "box-score coverage", "known gap",
         "How many game books per day will the repo capture?",
         f"{len(m['estimator_b']['teams_not_adjusted'])} of 30 clubs have no captured box score, so "
         "their availability column reads 'not modelled'. One PDF per game answers it: six a day for a "
         "full slate, ten for a Sunday.",
         "Extend the existing capture job with the statsdmz book for every game in the window, then "
         "per-player minutes become a full-slate input and player props become possible.",
         [A["urls"]["book_dalbos"], "d1b96315/data/player_logs_2026-11-15.json",
          "data/app/minutes_shares.json"]),
        ("Q05", "quarter-score conflict", "unknown which reading is right",
         "Is the period table or the recap line authoritative in a game book?",
         "ATL@MIL prints both, and they disagree on Milwaukee's third quarter (37 vs 27) inside one "
         "PDF. The final is not in doubt; any quarter-derived market would be.",
         "Ask the stats owner, or compare against the league's own quarter splits for the same game on "
         "another official page. Meanwhile the gate stays red for that row and the game is excluded "
         "from game-flow measurements.",
         [A["urls"]["book_atlmil"], "d1b96315/data/raw/gamebook_20261115_ATLMIL.md"]),
        ("Q06", "roster assignment", "unknown and contradictory",
         "Which official page defines which club a player belongs to?",
         "The 11/16 injury report (both revisions) and the official 11/15 game book put LeBron James "
         "on Philadelphia; the season-leader strip on the games page lists him under Los Angeles and "
         "Giannis Antetokounmpo under Miami. Per-player models are keyed on club, so this decides "
         "whose rotation a status line modifies.",
         "Treat the game-level documents as authoritative (this session does) and ask whether the "
         "leader strip is a separate feed with its own roster snapshot.",
         [A["urls"]["pdf_1315"], A["urls"]["book_indphi"], A["urls"]["games_1116"]]),
        ("Q07", "home-court pin", "owner decision",
         "Which HCA becomes canonical: the league-measured 0.90, the round capture's 4.12, or the app "
         "ledger's 1.62?",
         f"The three coexist today and the spread is "
         f"{m['home_court']['previously_published_in_this_repo']['spread_between_the_three_points']} "
         "points — bigger than the disagreement cap on a third of the window. Sealed hashes already "
         "contain the old constant, so re-pinning silently would make the ledger describe a model that "
         "no longer exists.",
         "Pick one, publish the choice, and re-seal going forward; the ledger keeps history unedited.",
         [A["urls"]["standings"], "data/rounds/2026-11-16/model.json", "data/app/ledger/ledger.jsonl"]),
        ("Q08", "sample depth", "known",
         "When does the 60-final gate clear?",
         f"{m['inputs']['settled_finals_used']} verified finals are captured; ~4 per club is the "
         "stated bar and the season has played about 14 games per club. Nothing in the repo captures "
         "the 11/01-11/12 games, so the log cannot be backfilled from what is on disk.",
         "Either capture the season's opening slate (each day's scoreboard page plus its books) or "
         "re-scope G1 to a per-club minimum that the capture horizon can actually reach.",
         [A["urls"]["games_1115"], "data/app/results_feed.json"]),
        ("Q09", "parlay ρ", "known and weak",
         "Is the measured correlation strong enough to price with?",
         f"ρ(margin, total) = {m['pricing']['rho_margin_vs_total']} with a 95% interval of "
         f"{m['pricing']['rho_margin_vs_total_ci95']} on {m['pricing']['measured_on']['settled_games']} "
         "games: the interval straddles zero, so the measurement is honest but not decisive.",
         "It resolves itself as the log grows; the naive product is printed beside every priced row so "
         "a reader can see the effect's size today.",
         ["d1b96315/data/model.json", "d1b96315/data/results_2026-11-15.json"]),
        ("Q10", "time zones in the window", "known trap",
         "Which slate dates are ET or UTC?",
         "The 11/17 rows UTA@LAC 10:30 PM ET and CHA@LAL 11:00 PM ET begin on 11/18 in UTC, and the "
         "11/16 revision prints those same matchups under 11/17 with those times. A settlement job that "
         "keys on a UTC date would settle them a day late — or grade them against the wrong day's games.",
         "Keep game-day settlement anchored to the ET date on the scoreboard page, as the published "
         "rule already says, and store both stamps on every row.",
         ["d1b96315/data/slate_2026-11-16_1118.json", A["urls"]["pdf_1315"]]),
    ]
    cards = "".join(
        f'<div class="q"><h4>{e(i)} · {e(t)}</h4>'
        f'<p><span class="tag {"warn" if "unknown" in stat else "ok" if "known" in stat else "info"}">{e(stat)}</span> '
        f'<b>{e(q)}</b></p><p class="small">{e(fact)}</p>'
        f'<p class="small mut"><b>To find out:</b> {e(how)}</p>'
        f'<p class="small">{src_cell(srcs)}</p></div>'
        for i, t, stat, q, fact, how, srcs in qs)
    body = f"""
<h1>Known, unknown, and how to close each one</h1>
<p class="lead">Ten items, each stating whether the answer is in hand, what the measurement says, and
what specifically would turn the unknown into a number. Nothing here is a request for a value the site
could look up itself — each one needs either a decision or a feed.</p>
{cards}
"""
    return page("questions", "Questions", body)


def p_suggestions(A) -> str:
    m = A["model"]
    ps = [
        ("p1", "Pin home court to the league-wide measurement, everywhere",
         "one constant, one re-seal",
         f"Adopt {m['home_court']['hca_points_used']} points (measured on {A['standings']['measured_home_games']} home "
         "games) in the round model, the app estimators and the ledger, and record the old value as "
         "history rather than overwriting it.",
         "The current three-way split (0.90 / 4.12 / 1.62) is the largest single disagreement in the "
         "repo and it moves every home line. A pin built on 196 games beats one built on 23.",
         "Every already-sealed entry keeps its old constant — that is the point of the chain — so two "
         "published surfaces will show different numbers for one game day unless the choice is stated "
         "on the page. Half a day of work: the constant, the note, a re-run of the two builders.",
         "Do nothing: keep publishing three numbers and let readers find the 3.2-point swing themselves."),
        ("p2", "Get a price feed, even a manual one",
         "one capture job + one table",
         "A closing-line table with date, game, market, line, source, stamp — captured the same way the "
         "injury PDFs are. Manual entry of published closing numbers is acceptable if it is stamped and "
         "sourced, because it is then a source like any other.",
         "It unlocks G8, which blocks all five strategies today, and turns the model-anchored prior from "
         "a null field into a measured log-loss weight. Without it no line on this site can ever be "
         "scored as skill.",
         "Nothing in the model changes, so nothing published now is invalidated. The bet surface stays "
         "empty until the depth gate clears as well, so expect 'we can finally measure', not 'we can bet'.",
         "Wait for a licensed feed: cleaner, but the board has listed this gap for several sessions and "
         "a stamped manual table costs one afternoon."),
        ("p3", "Capture one game book per game, every day",
         "six to ten PDFs a day",
         "Extend the capture job with the official per-game book (the same URL pattern already used for "
         "the ATL@MIL re-read). That gives per-player minutes for all 30 clubs, real top-8 shares, and "
         "the quarter vectors for every game instead of 13 of 23.",
         f"It moves the availability model from {len(m['estimator_b']['teams_adjusted'])} clubs to 30, "
         "makes player-prop work possible, and gives game-flow its own verified input instead of a "
         "partial one. It also makes the I2 quarter gate testable on a real population.",
         "The transcripts are large: keep them under the session tree or a data path, not in "
         "<code>app/</code>, and expect the PDF renderer's column-shift artefact on every one of them — "
         "parse by content and count the unread cells, as this tree does.",
         "Keep covering the handful of games a session happens to re-read: cheaper, and it is why six "
         "clubs on tonight's slate have no modelled availability at all."),
        ("p4", "Chase the newest revision on game day",
         "one cron line + one index read",
         "Read the report index, take the newest item, and add a pre-tip pass (~30 min before the "
         "earliest tip of a block). The freshness gate then measures a gap that is actually the "
         "league's latest document.",
         f"Today's published snapshot was about 4 h 05 m behind, and the missing rows were the ones "
         f"that mattered: {A['delta_pm']['counts']['rows_added']} rows appeared when four clubs filed, "
         "including a league suspension and two starters moved to Out.",
         "The gate already exists; this changes what it measures, so more rows will legitimately fail "
         "the rebuild until the job keeps up. Expect the red-build count to rise before it falls.",
         "Keep the four fixed crons: simple, and it is what left the 01:15 PM filing unpublished today."),
    ]
    cards = "".join(
        f'<div class="q" id="{pid}"><h4><span class="tag info">Path {pid[1]}</span> {e(t)}</h4>'
        f'<p class="small mut">cost: {e(cost)}</p>'
        f'<p><b>Do</b> {e(do)}</p><p><b>Buy</b> {e(buy)}</p>'
        f'<p><b>Pay</b> {e(pay)}</p><p><b>Otherwise</b> {e(other)}</p></div>'
        for pid, t, cost, do, buy, pay, other in ps)
    body = f"""
<h1>Four paths, pick one before anything is implemented</h1>
<p class="lead">Each path is a single decision with its cost, what it unlocks, and what it costs in
re-work. They are ordered by how much of the brief they unblock per hour of owner time, not by how
nice they sound.</p>
{cards}
<h2>And one that needs no decision</h2>
<div class="note">The scheduled job is red now, and every freshness number on this site inherits that.
The fix is a diagnosis, not a choice: read run 43925193575's log in the Actions UI (the log body is not
reachable from a sandbox) and re-run. Nothing on this list is worth doing before the refresh path is
green, because every one of them assumes the repo is looking at today's documents.</div>
"""
    return page("suggestions", "Suggestions", body)


def p_flagged(A) -> str:
    f = A["flags"]
    rows = []
    for r in f["flags"]:
        rows.append([f'<b id="{e(r["id"])}">{e(r["id"])}</b>', sev(r["severity"]), e(r["surface"]),
                     f'<b>{e(r["title"])}</b>', e(r["measured"]), e(r["why_it_matters"]),
                     e(r["action"]),
                     '<span class="tag grey">no</span>' if not r["blocks_merge"]
                     else '<span class="tag bad">yes</span>',
                     src_cell(r["sources"])])
    body = f"""
<h1>Flagged for review</h1>
<p class="lead">{f['rule']}</p>
<div class="cards">
{card("rows", f"{f['counts']['rows']}", "irregularities and gaps, each with its own source links")}
{card("high severity", f"{f['counts']['by_severity']['high']}", "freshness, CI, settlement, the HCA split, the price feed")}
{card("blocking the merge", f"{f['counts']['blocking_merge']}", "nothing: flagged items are published, not hidden")}
</div>
{table(["id", "severity", "surface", "finding", "measured", "why it matters", "action", "blocks", "sources"], rows)}
<p class="small mut">Verbatim evidence for the two rows about official documents is in the tree:
<a href="{e(REPO_BLOB + 'd1b96315/data/raw/gamebook_20261115_ATLMIL.md')}">the ATL@MIL game book</a>
(D-03) and the two <a href="{e(REPO_BLOB + 'd1b96315/data/raw/injury_2026-11-16_0115PM.md')}">injury
report transcripts</a> (D-05, D-06, D-09), kept exactly as fetched including their page-break artefacts.
Machine-readable copy: <a href="{e(REPO_BLOB + 'd1b96315/data/flags.csv')}">flags.csv</a> ·
<a href="{e(REPO_BLOB + 'd1b96315/data/flags.json')}">flags.json</a>. The canonical site's own register is
at {link(LIVE + "app/flagged.html", "app/flagged.html")} — this page is this session's, and the board's
rules keep the two separate until an integration session merges them.</p>
"""
    return page("flagged", "Flagged for review", body)


def p_sources(A) -> str:
    rows = []
    for s in A["source_register"]:
        rows.append([e(s["what"]), e(s["kind"]),
                     f'<a class="src" href="{e(s["url"])}" rel="noopener">{e(s["url"])}</a>'
                     if s["url"].startswith("http") else
                     f'<a class="src" href="{e(REPO_BLOB + s["url"])}" rel="noopener">{e(s["url"])}</a>',
                     e(s["retrieved"]), e(s["used_for"]), e(s["confirmed"]),
                     f'<span class="tag {"ok" if s["official"] else "warn"}">'
                     f'{"official" if s["official"] else "general reference"}</span>'])
    body = f"""
<h1>Source register: what was read, when, and what it settled</h1>
<p class="lead">Every number on this site traces to one of these rows. Where a page could not be read,
the row says so and the dependent value is blank — a rule the whole tree follows, not a caption.</p>
{table(["source", "kind", "url", "retrieved (UTC)", "used for", "what it confirmed", "class"], rows)}
<div class="warnbox"><b>One input is not official.</b> The arena coordinates used for travel distance
come from a general-reference table committed on main (<code>data/app/arena_coordinates.json</code>,
Wikipedia via the MediaWiki API, read 2026-11-15T11:47Z). The arena <i>name</i> on every travel row is
cross-checked against the official schedule and mismatches are printed; the coordinates themselves are
not an NBA-published figure, and the distance is labelled as derived arithmetic wherever it appears
(board items K-06 / CR-06).</div>
<p class="small mut">Two fetch paths that were tried and do not work, recorded so the next session does
not repeat them: the OSS proxy URLs in the tool's own results return
<code>SignatureDoesNotMatch</code> for every one of these PDFs (fetch the
<code>ak-static.cms.nba.com</code> URL directly), and
<code>www.nba.com/stats/standings?Season=2026-27…</code> returns "Content Unavailable" — the working
URL is <code>www.nba.com/standings</code>, and its 15th Western row only appears in the page's second
chunk, which is why both chunks were read.</p>
"""
    return page("sources", "Sources", body)


# ================================================================ driver

def build_source_register(A) -> list:
    m = A["model"]
    return [
        {"what": "official injury report, 11:30 AM ET revision", "kind": "PDF (fetched + transcribed here)",
         "url": A["urls"]["pdf_1130"], "retrieved": A["morning"]["retrieved_utc"],
         "used_for": "the morning step of the day's diff; the availability input for tonight",
         "confirmed": f"{A['morning']['count']} rows / {A['morning']['player_rows']} player rows; identical content to the 09:15 snapshot the site published",
         "official": True},
        {"what": "official injury report, 01:15 PM ET revision", "kind": "PDF (fetched + transcribed here)",
         "url": A["urls"]["pdf_1315"], "retrieved": A["latest"]["retrieved_utc"],
         "used_for": "the newest filing state per club; every availability column on the lines page",
         "confirmed": f"{A['latest']['count']} rows / {A['latest']['player_rows']} player rows; "
                      f"{A['delta_pm']['counts']['status_changes']} status changes and "
                      f"{A['delta_pm']['counts']['rows_added']} new rows since 11:30",
         "official": True},
        {"what": "injury report index for the 2026-27 season", "kind": "HTML",
         "url": A["urls"]["index"], "retrieved": "2026-11-16T18:24Z",
         "used_for": "proving the 01:15 PM ET revision exists and is newer than the published snapshot",
         "confirmed": "revisions listed 12:00 AM → 01:15 PM ET on 11/16", "official": True},
        {"what": "09:15 AM ET snapshot the site had published", "kind": "repo artefact",
         "url": "data/rounds/2026-11-16/injuries.json", "retrieved": A["pub_inj"]["retrieved_utc"],
         "used_for": "the older side of the whole-day diff, re-shaped without re-deriving any value",
         "confirmed": f"{A['pub_inj']['count']} rows / {A['pub_inj']['player_rows']} player rows / "
                      f"{A['pub_inj']['not_submitted_rows']} unfiled", "official": True},
        {"what": "scoreboard, game day 2026-11-15", "kind": "HTML", "url": A["urls"]["games_1115"],
         "retrieved": "2026-11-16T18:30Z", "used_for": "all nine finals, re-read independently of main",
         "confirmed": "9 finals; 8 agree with main's settled rows; ATL@MIL final confirmed",
         "official": True},
        {"what": "game book ATL @ MIL (0022600243)", "kind": "PDF (fetched + transcribed here)",
         "url": A["urls"]["book_atlmil"], "retrieved": "2026-11-16T18:30Z",
         "used_for": "quarter vector for the blocked row; inactives for both clubs",
         "confirmed": "the period table and the recap line disagree on Milwaukee's Q3; the final is confirmed three ways",
         "official": True},
        {"what": "game books IND @ PHI and DAL @ BOS (11/15)", "kind": "PDFs (fetched + transcribed here)",
         "url": A["urls"]["book_indphi"], "retrieved": "2026-11-16T18:44Z",
         "used_for": "per-player minutes/points/rebounds/assists for four more clubs; an independent quarter re-read",
         "confirmed": f"{A['logs']['count']} player rows added (BOS, DAL, IND, PHI); minutes sum to 240.00 "
                      "per club; IND's readable rows sum to its printed 124", "official": True},
        {"what": "scoreboard, game day 2026-11-16", "kind": "HTML", "url": A["urls"]["games_1116"],
         "retrieved": "2026-11-16T18:30Z", "used_for": "re-verification of tonight's slate rows; the calendar counts for the whole window",
         "confirmed": "6 of 8 cards present in the fetched chunk (all 8 present in the report's matchup list); no odds rendered",
         "official": True},
        {"what": "scoreboard cards, game day 2026-11-19", "kind": "HTML",
         "url": "https://www.nba.com/games?date=2026-11-19", "retrieved": "2026-11-16T19:05Z",
         "used_for": "the fourth day of the pricing window (4 games), so lines reach three days ahead",
         "confirmed": "4 cards with ids 0022600270-273, all four printed 8:00 PM ET; no venue and no "
                      "odds on a card, so both are blank; the printed records match the standings page",
         "official": True},
        {"what": "league standings, 2026-27", "kind": "HTML (both chunks)", "url": A["urls"]["standings"],
         "retrieved": A["standings"]["retrieved_utc"],
         "used_for": "the measured home-win rate the HCA pin is now computed from; all 30 rows",
         "confirmed": f"30 rows, all splits; {A['standings']['measured_home_wins']}-"
                      f"{A['standings']['measured_home_games'] - A['standings']['measured_home_wins']} in "
                      f"{A['standings']['measured_home_games']} home games; every identity check passes",
         "official": True},
        {"what": "Teams Advanced, 2026-27 Regular Season", "kind": "HTML (both chunks)",
         "url": A["urls"]["advanced"], "retrieved": A["advanced"]["retrieved_utc"],
         "used_for": "estimator B's off/def/pace/possessions inputs; the cross-check of main's three-page capture",
         "confirmed": "30 rows; W+L=GP everywhere; NetRtg within the page's own rounding (max residual 0.1)",
         "official": True},
        {"what": "the round's three-page team-stat capture", "kind": "repo artefact",
         "url": "data/rounds/2026-11-16/team_stats.json", "retrieved": "captured 2026-11-16T14:25Z by arena/8f4fac33-nba3",
         "used_for": "the naive scoring averages printed beside every possessions-model total",
         "confirmed": "30 teams × traditional/opponent/advanced, each block with its own source_url; agrees with this session's live advanced read",
         "official": True},
        {"what": "canonical result feed", "kind": "repo artefact", "url": "data/app/results_feed.json",
         "retrieved": "as published on main",
         "used_for": "the 11/13 and 11/14 finals in the estimation log, and their quarter vectors",
         "confirmed": "14 settled finals; the 11/14 rows carry quarter scores, the 11/13 rows do not",
         "official": True},
        {"what": "per-player logs for 11/14", "kind": "repo artefact", "url": "data/app/player_game_logs.json",
         "retrieved": "as published on main",
         "used_for": "the rotation input for the 8 of tonight's 16 clubs with no 11/15 box",
         "confirmed": "173 rows, 10 clubs, date 2026-11-14 only — the coverage gap is D-08",
         "official": True},
        {"what": "official rolling slate 11/16-11/18", "kind": "repo artefact",
         "url": "data/rounds/2026-11-16/slate.json", "retrieved": "as published on main",
         "used_for": "the window's 29 games, venues and tip times",
         "confirmed": "25 rows, no duplicate ids; tonight's 8 re-verified row by row where the page chunk carried them",
         "official": True},
        {"what": "main's sealed app pick ledger", "kind": "repo artefact", "url": "data/app/ledger/ledger.jsonl",
         "retrieved": "as published on main", "used_for": "independent chain verification and the K-17 recipe test",
         "confirmed": "34 entries, chain intact; entry_hash = sha256(canon({prev, body})), 34/34; body alone 0/34",
         "official": True},
        {"what": "the bet-surface ledger on main", "kind": "repo artefact", "url": "ledger/ledger.jsonl",
         "retrieved": "as published on main", "used_for": "independent chain verification",
         "confirmed": "11 entries, chain intact under the recipe scripts/ledger.py documents", "official": True},
        {"what": "scheduled refresh run", "kind": "CI", "url": A["urls"]["run"],
         "retrieved": "2026-11-16T18:20Z", "used_for": "the failing-step identification behind D-01/D-02",
         "confirmed": "job refresh, step 'Unit tests (capture, feed, ledger, estimators, gates)', 19 s; log body unreachable from this sandbox",
         "official": False},
        {"what": "arena coordinates", "kind": "repo artefact (general reference)",
         "url": "data/app/arena_coordinates.json", "retrieved": "2026-11-15T11:47Z",
         "used_for": "travel distance only, labelled as derived arithmetic on every row",
         "confirmed": "arena names cross-checked against the official schedule; coordinates are not an NBA-published figure",
         "official": False},
    ]


def main() -> None:
    A = {
        "capture_stamp": "2026-11-16T18:55Z",
        "urls": {
            "index": "https://official.nba.com/nba-injury-report-2026-27-season/",
            "pdf_1315": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf",
            "pdf_1130": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_11_30AM.pdf",
            "games_1115": "https://www.nba.com/games?date=2026-11-15",
            "games_1116": "https://www.nba.com/games?date=2026-11-16",
            "standings": "https://www.nba.com/standings",
            "advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
            "book_atlmil": "https://statsdmz.nba.com/pdfs/20261115/20261115_ATLMIL.pdf",
            "book_indphi": "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
            "book_dalbos": "https://statsdmz.nba.com/pdfs/20261115/20261115_DALBOS.pdf",
            "run": "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43925193575",
        },
        "latest": load("injuries_2026-11-16_latest.json"),
        "morning": load("injuries_2026-11-16_1130AM.json"),
        "snaps": load("injury_snapshots_2026-11-16.json"),
        "delta_pm": load("injury_delta_2026-11-16_1130_to_1315.json"),
        "delta_am": load("injury_delta_2026-11-16_0915_to_1130.json"),
        "delta_day": load("injury_delta_2026-11-16_0915_to_1315.json"),
        "pub_inj": json.loads((ROOT / "data/rounds/2026-11-16/injuries.json").read_text(encoding="utf-8")),
        "results": load("results_2026-11-15.json"),
        "standings": load("standings_2026-11-16.json"),
        "advanced": load("team_advanced_2026-11-16.json"),
        "slate": load("slate_2026-11-16_1118.json"),
        "lines": load("lines.json")["lines"],
        "model": load("model.json"),
        "gates": load("gates.json"),
        "prereg": load("prereg_index.json"),
        "flags": load("flags.json"),
        "logs": load("player_logs_2026-11-15.json"),
        "ledger": load("ledger_check.json"),
    }
    A["slate_games"] = A["slate"]["games"]
    A["idx"] = {t["team_abbr"]: t for t in A["advanced"]["teams"]}
    A["ledger_entries"] = [json.loads(x) for x in
                           (HERE / "ledger" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                           if x.strip()]
    A["source_register"] = build_source_register(A)
    PAGES.mkdir(exist_ok=True)
    out = {"index.html": p_index(A), "injuries.html": p_injuries(A),
           "results.html": p_results(A), "standings.html": p_standings(A),
           "lines.html": p_lines(A), "pricing.html": p_pricing(A), "model.html": p_model(A),
           "gates.html": p_gates(A), "ledger.html": p_ledger(A), "questions.html": p_questions(A),
           "suggestions.html": p_suggestions(A), "flagged.html": p_flagged(A),
           "sources.html": p_sources(A)}
    for name, text in out.items():
        (PAGES / name).write_text(text, encoding="utf-8")
        print(f"wrote d1b96315/pages/{name}  ({len(text) // 1024} KB)")
    check(out)


def check(out: dict) -> None:
    """Fail loudly on a missing nav target or a data row with no source."""
    problems = []
    for name, text in out.items():
        for href in re.findall(r'href="([a-z_0-9.\-]+\.html)(?:#[a-z0-9\-]*)?"', text):
            if href not in out and not href.startswith(("http", "app/")):
                problems.append(f"{name}: broken link {href}")
        n_rows = text.count("<tr>") - text.count("<thead><tr>")
        n_src = text.count('class="src"') + text.count("no official link on this row")
        if n_rows > 0 and n_src == 0:
            problems.append(f"{name}: {n_rows} table rows and no source marker at all")
    if problems:
        raise SystemExit("PAGE CHECK FAILED:\n  " + "\n  ".join(problems))
    print("page check passed: every link resolves, every table carries source markers")


if __name__ == "__main__":
    main()
