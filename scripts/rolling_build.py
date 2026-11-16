#!/usr/bin/env python3
"""Build the rolling site (rolling/*.html) from the rolling captures.

Pages: index (status), slate, injuries (banner shows revision + retrieval time),
results (one row per game: date, teams, final score, quarter scores + settlement stamp),
gates. Every table row carries its official source link; blanks stay blank and flagged.
The build runs AFTER the gates pass (the refresh refuses a rebuild otherwise).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
REFRESH = os.path.join(APP, "refresh")
ROLLING = os.path.join(APP, "rolling")
OUT = os.path.join(ROOT, "rolling")

CSS = (":root{--ink:#14181f;--mut:#5b6675;--line:#dfe4ea;--bg:#fff;--soft:#f6f8fa;"
       "--acc:#1b4f9c;--warn:#8a5a00;--bad:#a3241c;--ok:#1c6b3a}\n"
       "*{box-sizing:border-box}\n"
       "body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
       "Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}\n"
       "header.site{background:var(--ink);color:#fff;padding:14px 0}\n"
       "header.site a{color:#fff}\n.wrap{max-width:1180px;margin:0 auto;padding:0 20px}\n"
       ".brand{font-weight:700;text-decoration:none}\n"
       ".brand span{background:#fff;color:var(--ink);border-radius:3px;padding:1px 5px;"
       "margin-right:7px}\n.stamp{color:#b9c3d0;font-size:13px;margin-top:3px}\n"
       "nav.site{background:var(--soft);border-bottom:1px solid var(--line);padding:9px 0;"
       "font-size:14px}\nnav.site a{margin-right:14px;color:var(--acc);text-decoration:none}\n"
       "nav.site a.active{font-weight:700;border-bottom:2px solid var(--acc)}\n"
       "main{padding:26px 0 60px}\n"
       "h1{font-size:26px;margin:4px 0 6px}\n"
       "h2{font-size:19px;margin:30px 0 8px;padding-bottom:5px;"
       "border-bottom:1px solid var(--line)}\n"
       ".lead{color:var(--mut);max-width:74ch}\n"
       ".tw{overflow-x:auto;margin:12px 0 4px;border:1px solid var(--line);border-radius:6px}\n"
       "table{border-collapse:collapse;width:100%;font-size:13.5px}\n"
       "th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;"
       "vertical-align:top}\n"
       "th{background:var(--soft);font-weight:600;white-space:nowrap}\n"
       "td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}\n"
       "a{color:var(--acc)}\n"
       ".chip{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;"
       "border-radius:10px;white-space:nowrap}\n"
       ".ok{background:#e4f3e9;color:var(--ok)}.bad{background:#fbe6e4;color:var(--bad)}\n"
       ".warn{background:#fdf1d8;color:var(--warn)}.grey{background:#eceff3;color:var(--mut)}\n"
       ".unv{color:var(--bad);font-size:12px}\n"
       ".callout{background:var(--soft);border-left:3px solid var(--acc);padding:11px 14px;"
       "margin:16px 0;border-radius:0 5px 5px 0}\n"
       ".callout.bad{border-left-color:var(--bad);background:#fdf4f3}\n"
       "code{background:var(--soft);padding:1px 5px;border-radius:3px;font-size:12.5px}\n"
       "footer.site{border-top:1px solid var(--line);color:var(--mut);font-size:12.5px;"
       "padding:16px 0 30px}\n")

NAV = [("index.html", "Status"), ("slate.html", "Slate"), ("injuries.html", "Injuries"),
       ("results.html", "Results & settlement"), ("gates.html", "Gates")]


def esc(x) -> str:
    import html
    return html.escape(str(x)) if x is not None else ""


def blank_flag(label="unverified") -> str:
    return '<span class="unv">— blank + flagged: ' + esc(label) + "</span>"


def page(title: str, body: str, stamp: str, active: str) -> str:
    links = []
    for h, t in NAV:
        cls = ' class="active"' if h == active else ""
        links.append(f'<a href="{h}"{cls}>{t}</a>')
    nav = "".join(links)
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{esc(title)} — NBA3 Rolling</title>\n"
            "<meta name=\"description\" content=\"NBA3 rolling official refresh: every row "
            "links to an official NBA source; unconfirmed values are blank and flagged.\">\n"
            "<style>" + CSS + "</style>\n</head>\n<body>\n"
            '<header class="site"><div class="wrap">\n'
            '<a class="brand" href="index.html"><span>NBA3</span>Rolling refresh</a>\n'
            f'<div class="stamp">Rolling capture {esc(stamp)} · session '
            '<code>arena/43d54bfe-nba3</code> · rebuild only after the freshness and '
            'provenance gates pass</div>\n</div></header>\n'
            f'<nav class="site"><div class="wrap">{nav}</div></nav>\n'
            f'<main><div class="wrap">{body}</div></main>\n'
            '<footer class="site"><div class="wrap">Sources are the official NBA pages and '
            "PDFs each row links to. Unverified cells are deliberately blank and flagged; "
            "values are never inferred.</div></footer>\n</body>\n</html>\n")


def write(name: str, title: str, body: str, stamp: str, active: str) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(page(title, body, stamp, active))
    print("wrote", os.path.join("rolling", name))


def build(stamp: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    promo_path = os.path.join(ROLLING, "promotion_report.json")
    promo = json.load(open(promo_path, encoding="utf-8")) if os.path.exists(promo_path) else {}

    gates_path = os.path.join(REFRESH, stamp, "rolling_gate_report.json")
    gates = json.load(open(gates_path, encoding="utf-8")) if os.path.exists(gates_path) else {}

    # ---------------- index: status + gates
    chips = ""
    for g in gates.get("gates", []):
        cls = "ok" if g["pass"] else "bad"
        chips += f'<span class="chip {cls}">{esc(g["id"])} {"PASS" if g["pass"] else "FAIL"}</span> '
    overall = gates.get("pass")
    verdict = ("NOT EVALUATED — no refresh capture promoted yet" if overall is None
               else "PASS — rebuild allowed" if overall
               else "FAILED — rebuild refused")
    body = f"""<h1>Rolling refresh status</h1>
<p class="lead">This surface is rebuilt by the scheduled <code>official data refresh</code> job
from the official sources linked on every row. Freshness and provenance gates run first;
if any gate fails the job exits non-zero without rebuilding, and the site keeps the last
good build.</p>
<div class="callout {'bad' if overall is False else ''}">
<strong>Gate verdict for capture {esc(stamp)}:</strong> {verdict}</div>
<p>{chips or 'no gate report for this stamp'}</p>
<h2>Promotion report</h2>
<div class="tw"><table><thead><tr><th>Stage</th><th>Result</th></tr></thead><tbody>
<tr><td>Injury report archive + parse</td><td>{esc(json.dumps(promo.get('injuries', {}))[:180])}</td></tr>
<tr><td>Results from official game books</td><td>{esc(json.dumps(promo.get('results', {}))[:180])}</td></tr>
</tbody></table></div>
<h2>What rolls forward</h2>
<ul>
<li>Official schedule window (today..today+3 Eastern) promoted from the fetched
<em>official games pages</em>: see <a href="slate.html">Slate</a>.</li>
<li>Newest official injury report archived verbatim (PDF + sha256 + retrieval stamp) and
row-parsed; consecutive reports diffed for status changes: see
<a href="injuries.html">Injuries</a>.</li>
<li>Official game books for the previous two Eastern game days parsed into one row per game
(date, teams, final score, quarter scores) and settled with a visible stamp: see
<a href="results.html">Results &amp; settlement</a>.</li>
</ul>"""
    write("index.html", "Status", body, stamp, "index.html")

    # ---------------- slate
    slate_path = os.path.join(APP, "official_slate_current.json")
    rows = []
    if os.path.exists(slate_path):
        slate = json.load(open(slate_path, encoding="utf-8"))
        for g in slate.get("games", []):
            tip = g.get("time_et") or blank_flag("tip time not printed by the fetched page")
            rows.append(
                f"<tr><td>{esc(g['date'])}</td><td>{tip}</td>"
                f"<td>{esc(g['away'])} @ {esc(g['home'])}</td>"
                f"<td><a href=\"{esc(g['game_url'])}\">{esc(g['game_id'])}</a></td>"
                f"<td><a href=\"{esc(g['source'])}\">official games page</a></td></tr>")
        src = slate.get("source_url")
        body = f"""<h1>Slate — rolling window (today..today+3 Eastern)</h1>
<p class="lead">Promoted from the fetched official schedule pages. Tip times stay blank where
the fetched page pattern did not carry them — blank and flagged, never inferred.
Source page: <a href="{esc(src)}">{esc(src)}</a> · retrieved {esc(slate.get('retrieved_utc'))}.</p>
<div class="tw"><table><thead><tr><th>Date (ET)</th><th>Tip (ET)</th><th>Matchup</th>
<th>Game id</th><th>Source</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""
    else:
        body = ("<h1>Slate</h1><div class=\"callout bad\">No promoted slate for this stamp — "
                "the rebuild was refused before promotion.</div>")
    write("slate.html", "Slate", body, stamp, "slate.html")

    # ---------------- injuries
    inj_dir = os.path.join(ROLLING, "injuries")
    idx_path = os.path.join(inj_dir, "archive_index.json")
    body = "<h1>Injuries — official report archive</h1>"
    if os.path.exists(idx_path):
        idx = json.load(open(idx_path, encoding="utf-8"))
        newest = next((e for e in idx["reports"] if e["report_name"] == idx.get("newest_report")),
                      None)
        if newest:
            rec_path = os.path.join(inj_dir, newest["report_name"] + ".json")
            rec = json.load(open(rec_path, encoding="utf-8")) if os.path.exists(rec_path) else {}
            body += f"""
<div class="callout"><strong>Current report: {esc(newest['report_name'])}</strong> —
revision (official stamp): {esc(rec.get('report_stamp'))} · retrieval: {esc(newest['retrieved_utc'])}
UTC · sha256 <code>{esc(newest['sha256'][:16])}…</code> ·
<a href="{esc(newest['source_url'])}">official PDF</a> ·
rows parsed {esc(newest.get('n_parsed'))}/{esc(newest.get('n_rows'))}.
The revision time and the retrieval time are both shown here, as required.</div>"""
        rows = []
        for e in idx["reports"]:
            rows.append(
                f"<tr><td>{esc(e['report_name'])}</td><td>{esc(e['retrieved_utc'])}</td>"
                f"<td>{esc(e.get('n_rows'))}/{esc(e.get('n_parsed'))}</td>"
                f"<td><a href=\"{esc(e['source_url'])}\">official PDF</a></td></tr>")
        body += ("<h2>Archive (every stored report keeps its timestamp)</h2>"
                 '<div class="tw"><table><thead><tr><th>Report</th><th>Retrieved (UTC)</th>'
                 "<th>Rows parsed</th><th>Source</th></tr></thead><tbody>"
                 + "".join(rows) + "</tbody></table></div>")
        delta_path = os.path.join(ROLLING, "injury_delta.json")
        if os.path.exists(delta_path):
            d = json.load(open(delta_path, encoding="utf-8"))
            drows = "".join(
                f"<tr><td>{esc(c['team'])}</td><td>{esc(c['player'])}</td>"
                f"<td>{esc(c['was'])}</td><td>{esc(c['now'])}</td></tr>"
                for c in d.get("changes", [])) or (
                "<tr><td colspan=\"4\">No status changes between the two newest consecutive "
                "reports</td></tr>")
            body += f"""<h2>Consecutive-report diff (status changes)</h2>
<p class="lead">{esc(d.get('note'))}</p>
<div class="tw"><table><thead><tr><th>Team</th><th>Player</th><th>Was</th><th>Now</th>
</tr></thead><tbody>{drows}</tbody></table></div>"""
        if newest and newest.get("n_parsed") and rec.get("rows"):
            prows = "".join(
                f"<tr><td>{esc(r.get('team'))}</td><td>{esc(r.get('player'))}</td>"
                f"<td>{esc(r.get('status'))}</td><td>{esc(r.get('reason') or blank_flag())}</td></tr>"
                for r in rec["rows"] if r.get("parsed"))
            unparsed_n = newest["n_rows"] - newest["n_parsed"]
            body += f"""<h2>Player rows (current report)</h2>
{f'<p><span class="unv">{unparsed_n} report rows could not be attributed to a player from the PDF text — left unparsed and flagged, never guessed.</span></p>' if unparsed_n else ''}
<div class="tw"><table><thead><tr><th>Team</th><th>Player</th><th>Status</th><th>Reason</th>
</tr></thead><tbody>{prows}</tbody></table></div>"""
    else:
        body += ('<div class="callout bad">No rolling injury archive yet.</div>')
    write("injuries.html", "Injuries", body, stamp, "injuries.html")

    # ---------------- results
    res_path = os.path.join(ROLLING, "results.json")
    body = "<h1>Results &amp; settlement — official game books</h1>"
    if os.path.exists(res_path):
        res = json.load(open(res_path, encoding="utf-8"))
        rows = []
        for g in res.get("games", []):
            q = lambda arr: esc(" · ".join(str(x) for x in arr))
            rows.append(
                f"<tr><td>{esc(g['date'])}</td><td>{esc(g['away'])} @ {esc(g['home'])}</td>"
                f"<td class=\"n\">{esc(g['away_pts'])} – {esc(g['home_pts'])}</td>"
                f"<td class=\"n\">{q(g['away_q'])} / {q(g['home_q'])}</td>"
                f"<td>{'settled' if g.get('settled') else 'open'}</td>"
                f"<td>{esc(g.get('settlement_stamp'))}</td>"
                f"<td><a href=\"{esc(g['source_url'])}\">official game book</a></td></tr>")
        if res.get("unparsed"):
            rows.append("<tr><td colspan=\"7\"><span class=\"unv\">"
                        + esc(len(res["unparsed"])) + " fetched game book(s) could not be "
                        "parsed — listed as unparsed, never guessed:</span> "
                        + "; ".join(esc(u["url"]) for u in res["unparsed"]) + "</td></tr>")
        body += f"""<p class="lead">One row per game: date, teams, final score, quarter scores.
Settlement happens only after the official final is verified (quarter sums equal the printed
final for both teams), and the settlement stamp stays visible.
Window {esc(res.get('window', {}).get('from'))} .. {esc(res.get('window', {}).get('to'))} ·
{esc(res.get('settled_count'))}/{esc(res.get('count'))} settled · retrieved {esc(res.get('retrieved_utc'))}.</p>
<div class="tw"><table><thead><tr><th>Date (ET)</th><th>Matchup</th><th class="n">Final</th>
<th class="n">Quarters (A / H)</th><th>State</th><th>Settlement stamp</th><th>Source</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""
    else:
        body += '<div class="callout bad">No rolling results capture yet.</div>'
    write("results.html", "Results", body, stamp, "results.html")

    # ---------------- gates
    grow = []
    for g in gates.get('gates', []):
        cls = 'ok' if g['pass'] else 'bad'
        verdict = 'PASS' if g['pass'] else 'FAIL'
        grow.append("<tr><td>" + esc(g['id']) + '</td><td><span class="chip ' + cls
                    + '">' + verdict + "</span></td><td>" + esc(g['detail']) + "</td></tr>")
    gate_rows = "".join(grow) or '<tr><td colspan="3">No gate report for this stamp</td></tr>'
    body = f"""<h1>Freshness &amp; provenance gates — capture {esc(stamp)}</h1>
<p class="lead">The rebuild runs only if every gate below passes. Every gate is evaluated
from stored artifacts, so it replays offline in CI.</p>
<div class="tw"><table><thead><tr><th>Gate</th><th>Verdict</th><th>Detail</th></tr></thead>
<tbody>{gate_rows}</tbody></table></div>"""
    write("gates.html", "Gates", body, stamp, "gates.html")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", required=True)
    args = ap.parse_args()
    build(args.stamp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
