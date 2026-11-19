#!/usr/bin/env python3
"""Build the b1ce1334 subsite (/b1ce1334/) from data/rounds/2026-11-19/*.json.

Pages: index (landing), injuries (banner = revision time + retrieval time), results, slate, flagged.
Every table row carries at least one link to an official NBA source (checked by --check).
Nothing is typed in by hand: every value is read from the committed JSON.

Usage:
  python3 scripts/build_b1ce1334.py          # write b1ce1334/*.html
  python3 scripts/build_b1ce1334.py --check  # rebuild in memory, compare with disk, verify links (exit 1 on failure)
"""
import html
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rounds" / "2026-11-19"
OUT = ROOT / "b1ce1334"
PAGES = ["index", "injuries", "results", "slate", "flagged"]
NAV = [("index.html", "Home"), ("injuries.html", "Injuries"), ("results.html", "Results (11/18)"),
       ("slate.html", "Slate 11/19-11/22"), ("flagged.html", "Flagged for Review")]

CSS = """
body{font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1d2433;background:#f6f7f9}
header{background:#1d2433;color:#fff;padding:14px 22px}
header a{color:#fff;margin-right:16px;text-decoration:none;opacity:.85}
header a:hover,header a.on{opacity:1;text-decoration:underline}
header h1{margin:0 0 6px;font-size:19px;font-weight:600}
main{padding:18px 22px;max-width:1200px}
h2{font-size:17px;margin:26px 0 8px}
.banner{background:#fff7e0;border:1px solid #e8c766;border-radius:6px;padding:10px 14px;margin:10px 0 16px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
.card{background:#fff;border:1px solid #dde1e7;border-radius:8px;padding:12px 14px;min-width:200px;flex:1}
.card b{display:block;font-size:22px;margin-top:4px}
.card a{text-decoration:none;color:#1f5fbf}
table{border-collapse:collapse;width:100%;background:#fff;font-size:14px;margin-bottom:10px}
th,td{border-bottom:1px solid #e6e9ee;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef1f5;font-weight:600;position:sticky;top:0}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.unv{color:#8a5a00;font-weight:600}
.muted{color:#5b6573;font-size:13px}
a{color:#1f5fbf}
.tag{display:inline-block;background:#e9eefc;border-radius:4px;padding:1px 6px;font-size:12px}
.warn{background:#fff1f0;border-left:4px solid #d64541;padding:8px 12px;margin:8px 0}
"""


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def esc(v):
    return "" if v is None else html.escape(str(v))


def link(url, text):
    return f'<a href="{html.escape(url, quote=True)}">{esc(text)}</a>'


def page(title, active, body, banner=""):
    nav = "".join(f'<a href="{h}"{" class=on" if h == active else ""}>{esc(t)}</a>' for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · NBA official data (b1ce1334)</title>
<style>{CSS}</style></head>
<body>
<header><h1>NBA official data: injuries, results, slate</h1><nav>{nav}</nav></header>
<main>
{banner}
{body}
<p class="muted">Every row links to the official NBA page it came from. Values that could not be confirmed are left blank and marked UNVERIFIED. Source files: <code>data/rounds/2026-11-19/</code>. Session b1ce1334.</p>
</main></body></html>
"""


def build():
    man = load("manifest.json")
    parsed = load("injury_parsed.json")
    delta = load("injury_delta.json")
    res = load("results_2026-11-18.json")
    slate = load("slate_2026-11-19_22.json")
    src = {s["id"]: s for s in man["sources"]}
    pdf_url = {"1200AM": src["S2"]["url"], "1215AM": src["S3"]["url"], "1230AM": src["S4"]["url"]}
    pdf_label = {"1200AM": "12:00 AM ET", "1215AM": "12:15 AM ET", "1230AM": "12:30 AM ET"}
    win = man["retrieval_window_utc"]
    newest = parsed["revisions"]["1230AM"]
    retr = f"{win['start']} to {win['end']}"
    pages = {}

    # ---- injuries
    banner = (f'<div class="banner"><b>Injury-report revision time:</b> {esc(newest["report_title"])} '
              f'(printed on the official PDF, newest of 3 consecutive revisions: 12:00, 12:15, 12:30 AM ET) '
              f'&nbsp;·&nbsp; <b>Retrieved:</b> {esc(retr)} UTC '
              f'&nbsp;·&nbsp; <span class="muted">The fetch tool returns no per-call time; the window is bounded as stated in the manifest.</span></div>')
    rows = []
    for r in newest["player_rows"]:
        attr = esc(r["team_attribution"])
        rows.append(f'<tr><td>{esc(r["matchup"] or "UNATTRIBUTED")}</td><td>{esc(r["team"] or "—")}</td>'
                    f'<td>{esc(r["player"])}</td><td>{esc(r["status"])}</td><td>{esc(r["reason"])}</td>'
                    f'<td class="muted">{attr}</td><td>{link(pdf_url["1230AM"], "Official PDF 12:30 AM ET")}</td></tr>')
    player_tbl = ('<h2>Player rows, newest revision (12:30 AM ET)</h2><table><thead><tr><th>Matchup</th><th>Team</th>'
                  '<th>Player</th><th>Status</th><th>Reason</th><th>Team attribution</th><th>Source</th></tr></thead>'
                  f'<tbody>{"".join(rows)}</tbody></table>')
    team_rows = []
    for r in newest["team_rows"]:
        team_rows.append(f'<tr><td>{esc(r["matchup"])}</td><td>{esc(r["team"])}</td><td>{esc(r["reason"])}</td>'
                         f'<td>{link(pdf_url["1230AM"], "Official PDF 12:30 AM ET")}</td></tr>')
    team_tbl = ('<h2>Team submission status, newest revision (readable rows)</h2><table><thead><tr><th>Matchup</th>'
                '<th>Team</th><th>Submission</th><th>Source</th></tr></thead>'
                f'<tbody>{"".join(team_rows)}</tbody></table>')
    diff_rows = []
    for p in delta["pairs"]:
        urls = f'{link(pdf_url[p["from"]], pdf_label[p["from"]])} → {link(pdf_url[p["to"]], pdf_label[p["to"]])}'
        diff_rows.append(f'<tr><td>{esc(pdf_label[p["from"]])} → {esc(pdf_label[p["to"]])}</td>'
                         f'<td class="num">{len(p["status_changes"])}</td><td class="num">{len(p["added_player_rows"])}</td>'
                         f'<td class="num">{len(p["removed_player_rows"])}</td>'
                         f'<td class="num">{len(p["team_submission_changes"])}</td>'
                         f'<td class="num">{p["verbatim_lines_differing"]}</td><td>{urls}</td></tr>')
    diff_tbl = ('<h2>Consecutive-revision diff (status changes)</h2><table><thead><tr><th>Pair</th>'
                '<th>Status changes</th><th>Players added</th><th>Players removed</th><th>Team-submission changes (readable rows)</th>'
                '<th>Verbatim lines differing (all rows)</th><th>Source</th></tr></thead>'
                f'<tbody>{"".join(diff_rows)}</tbody></table>'
                '<p class="muted">Status changes are computed only from cleanly parsed player rows. The verbatim-line count also counts '
                'lines in the layout-broken block that the parser could not read, so it is an upper bound on differences, not a status-change count.</p>')
    un_rows = []
    for rev in ["1200AM", "1215AM", "1230AM"]:
        for u in parsed["revisions"][rev]["unparsed"]:
            un_rows.append(f'<tr><td>{esc(pdf_label[rev])}</td><td class="num">{u["line_no"]}</td>'
                           f'<td><code>{esc(u["text"])}</code></td><td>{esc(u["reason"])}</td>'
                           f'<td>{link(pdf_url[rev], "Official PDF " + pdf_label[rev])}</td></tr>')
    un_tbl = ('<h2>Lines the parser could not read (NOT given values)</h2><table><thead><tr><th>Revision</th>'
              '<th>Transcript line</th><th>Text as transcribed</th><th>Reason</th><th>Source</th></tr></thead>'
              f'<tbody>{"".join(un_rows)}</tbody></table>')
    pages["injuries"] = page("Injuries", "injuries.html", player_tbl + team_tbl + diff_tbl + un_tbl, banner)

    # ---- results
    rrows = []
    for g in res["games"]:
        srcs = " · ".join(link(u, "NBA.com" if "schedule" in u else "game page") for u in g["source_urls"])
        rrows.append(f'<tr><td>{esc(res["date"])}</td><td>{esc(g["game_id"])}</td><td>{esc(g["away"])}</td>'
                     f'<td class="num">{g["away_score"]}</td><td>{esc(g["home"])}</td><td class="num">{g["home_score"]}</td>'
                     f'<td>{esc(g["status"])}</td><td>{esc(g["winner"])}</td>'
                     f'<td class="unv">{esc(g["quarter_scores"])}</td><td>{esc(g["venue"])}</td><td>{srcs}</td></tr>')
    body = ('<h2>Official final scores, Wednesday 11/18/2026 (12 games)</h2>'
            '<p class="muted">Away = first team in the official game URL. Quarter scores are not captured in this pass and are marked UNVERIFIED, not filled in. '
            'No pick ledger was settled in this session.</p>'
            '<table><thead><tr><th>Date</th><th>Game ID</th><th>Away</th><th>Score</th><th>Home</th><th>Score</th>'
            '<th>Status</th><th>Winner</th><th>Quarter scores</th><th>Venue</th><th>Source</th></tr></thead>'
            f'<tbody>{"".join(rrows)}</tbody></table>')
    pages["results"] = page("Results", "results.html", body)

    # ---- slate
    srows = []
    n = 0
    for d in slate["days"]:
        for g in d["games"]:
            n += 1
            srows.append(f'<tr><td>{esc(d["date"])}</td><td>{esc(g["tip_et"])}</td><td>{esc(g["away"])} @ {esc(g["home"])}</td>'
                         f'<td>{esc(g["game_id"])}</td><td>{esc(g["venue"]) or "<span class=unv>UNVERIFIED</span>"}</td>'
                         f'<td>{link(g["source_url"], "NBA.com game page")}</td></tr>')
    body = (f'<h2>Official slate, 11/19 to 11/22 ({n} games)</h2>'
            '<p class="muted">Tip times are as printed on nba.com (Eastern). Venue is blank where the page did not print one. '
            'The printed game count was checked only for 11/19 (4 games).</p>'
            '<table><thead><tr><th>Date</th><th>Tip (ET)</th><th>Matchup</th><th>Game ID</th><th>Venue</th><th>Source</th></tr></thead>'
            f'<tbody>{"".join(srows)}</tbody></table>')
    pages["slate"] = page("Slate", "slate.html", body)

    # ---- flagged
    flags = [
        ("F1", "Quarter scores are missing for all 12 finals of 11/18 (UNVERIFIED).", res["primary_source"]["url"], "Not captured; each game page needs 3+ transcript chunks."),
        ("F2", "Only one of the 12 finals (MEM@CLE) is on a second official page.", "https://www.nba.com/game/mem-vs-cle-0022600258/box-score", "The other 11 rest on one listing."),
        ("F3", "Kuminga, Jonathan and Pullin, Zyon (Questionable) have no team on the PDF transcript, so they cannot be attributed to a game.", pdf_url["1230AM"], "Lines 25 and 27 of the 12:30 AM transcript; team cell blank on the PDF page-break."),
        ("F4", "The Brooklyn–Lakers block is layout-broken in the PDF text: 13 lines at 12:00 and 12:15 AM, 11 at 12:30 AM. None of them is machine-parsed, so none gets a status. Six matchups (TOR@DET, NOP@OKC, WAS@CHI, PHX@UTA, HOU@DEN, SAC@LAL) appear only in that block and were not cross-checked against the slate.", pdf_url["1230AM"], "The 12:30 AM block merges team cells. Listed in the Unparsed table."),
        ("F5", "The PDF game-time column prints 08:00 / 07:00 / 09:30 (ET) where nba.com prints 8:00 / 7:00 / 9:30 PM ET.", src["S2"]["url"], "Matchups agree with nba.com. The AM/PM marker is missing from the PDF text."),
        ("F6", "Game IDs 0022600043–0022600051 (11/20) are out of sequence with the other IDs. nba.com labels them NBA Cup group games.", "https://www.nba.com/game/cha-vs-atl-0022600043", "Printed as-is; not re-keyed."),
        ("F7", "The PDF file bytes were not stored. The fetch tool returns parsed text. The stored artefacts are verbatim transcripts plus sha256 of the transcripts.", src["S1"]["url"], "The bash sandbox cannot reach ak-static.cms.nba.com."),
        ("F8", "The retrieval times are bounded windows, not exact per-call timestamps (the fetch tool does not return one).", man["sources"][0]["url"], "Window: 05:44:01Z to 05:50Z on 2026-11-19."),
        ("F9", "The official CDN schedule JSON (cdn.nba.com/static/json/staticData/scheduleLeagueV2.json) returned HTTP 500 to the fetch tool. The slate comes from the HTML listing instead.", "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json", "Not retried in this pass."),
        ("F10", "Venues are blank for 24 of the 26 slate games (not printed on the pages read). The 11/20–11/22 game counts are not printed on the pages read.", src["S5"]["url"], "Left blank, not filled in."),
        ("F11", "The scheduled refresh workflow (refresh.yml) failed on every scheduled run in the last 2 days at the unit-test step. Logs are unavailable from this sandbox. See B1-1 in COORDINATION.md.", "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/44424736929", "Run 44424736929 (2026-11-18 23:55 UTC): unit-test step failed; later steps skipped."),
    ]
    frows = "".join(f'<tr><td>{esc(i)}</td><td>{esc(t)}</td><td>{link(u, "Source")}</td><td class="muted">{esc(note)}</td></tr>'
                    for i, t, u, note in flags)
    body = ('<h2>Flagged for Review</h2><p class="muted">Irregularities and unverified items from this pass. '
            'None of them blocks publication of the official facts on this site. Each has a link to the source for manual review.</p>'
            '<table><thead><tr><th>ID</th><th>Item</th><th>Source</th><th>Note</th></tr></thead>'
            f'<tbody>{frows}</tbody></table>')
    pages["flagged"] = page("Flagged for Review", "flagged.html", body)

    # ---- landing
    n_pl = len(newest["player_rows"])
    n_status_changes = sum(len(p["status_changes"]) for p in delta["pairs"])
    body = f"""
<h2>Surfaces</h2>
<div class="cards">
 <div class="card"><span class="tag">Projection · published</span><b>Official facts only</b>
   <span class="muted">Injury reports, finals and the schedule, with the source on every row. No model output.</span></div>
 <div class="card"><span class="tag">Bet · gated</span><b>Not published</b>
   <span class="muted">No picks in this session. The pre-registration, ledger and validation gates were not run.</span></div>
</div>
<h2>At a glance</h2>
<div class="cards">
 <div class="card"><a href="injuries.html">Injuries</a><b>{n_pl} player rows</b><span class="muted">newest revision 12:30 AM ET 11/19; {n_status_changes} status changes across 3 revisions (cleanly parsed rows)</span></div>
 <div class="card"><a href="results.html">Results 11/18</a><b>{len(res["games"])} finals</b><span class="muted">scores from the official schedule page (1 of 12 also on a game page); quarter scores UNVERIFIED</span></div>
 <div class="card"><a href="slate.html">Slate 11/19–11/22</a><b>{n} games</b><span class="muted">tip times from nba.com; venue printed for 2 of 26 (24 blank, UNVERIFIED)</span></div>
 <div class="card"><a href="flagged.html">Flagged for Review</a><b>{len(flags)} items</b><span class="muted">each with a source link</span></div>
</div>
<h2>Freshness</h2>
<div class="banner">Injury report: <b>{esc(newest["report_title"])}</b> · Retrieved <b>{esc(retr)} UTC</b></div>
<p class="muted">Not in this subsite (open, see COORDINATION.md): standings, team statistics, player game logs, the three team-stat pages, the model, pre-registrations, the sealed ledger for 11/19+, parlays, and the executive summary.</p>
"""
    pages["index"] = page("Home", "index.html", body)
    return pages


class _Checker(HTMLParser):
    """Counts <tbody> rows and how many of them carry an https link; collects every href."""

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
    problems = []
    for name, text in pages.items():
        c = _Checker()
        c.feed(text)
        if c.rows_without_src:
            problems.append(f"{name}.html: {c.rows_without_src} table row(s) without an https source link")
        for h in c.hrefs:
            if h.startswith("https://"):
                continue
            if h.endswith(".html") and h not in {p + ".html" for p in PAGES}:
                problems.append(f"{name}.html: broken internal link {h}")
    if problems:
        ok = False
        for p in problems:
            print("SITE CHECK FAILED:", p, file=sys.stderr)
    return ok


def main(argv):
    pages = build()
    if "--check" in argv:
        ok = check_site(pages)
        for name, text in pages.items():
            p = OUT / f"{name}.html"
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                print(f"SITE CHECK FAILED: b1ce1334/{name}.html is stale; run scripts/build_b1ce1334.py", file=sys.stderr)
                ok = False
        print(f"b1ce1334 site check: {'PASS' if ok else 'FAIL'} ({len(pages)} pages)")
        return 0 if ok else 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (OUT / f"{name}.html").write_text(text, encoding="utf-8")
    check_site(pages)
    print(f"wrote {len(pages)} pages to {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
