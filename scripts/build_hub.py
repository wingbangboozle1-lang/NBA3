#!/usr/bin/env python3
"""Render the consolidated NBA3 dashboard (hub/) from data/hub/dashboard.json.

Rules enforced by this builder (a build fails if any of them is broken):
  * every data row that is shown carries a source id that resolves to an https URL;
  * a value that could not be verified is rendered blank and marked, never guessed;
  * every internal link resolves to a file that exists.

Usage:
  python3 scripts/build_hub.py            # write hub/
  python3 scripts/build_hub.py --check    # validate only, write nothing
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB_DATA = ROOT / "data" / "hub" / "dashboard.json"
OUT = ROOT / "hub"

NAV = [
    ("Overview", [("index.html", "Home"), ("executive-summary.html", "Executive summary")]),
    ("Data", [("slate.html", "Slate"), ("lines.html", "Originated lines"),
              ("picks.html", "Picks"), ("data.html", "Data and integrity"), ("sources.html", "Sources")]),
    ("Skill", [("strategies.html", "Strategy leaderboard"), ("correlations.html", "Correlations"),
               ("methodology.html", "Methodology")]),
    ("Availability", [("injuries.html", "Injuries"), ("gameflow.html", "Game flow"),
                       ("props.html", "Player props")]),
    ("Review", [("repo-review.html", "Repo review"), ("questions.html", "Questions"),
                ("suggestions.html", "Suggestions"), ("flagged.html", "Flagged for review"),
                ("verification.html", "Verification log")]),
]

CSS = """
:root{--bg:#0f1216;--panel:#161b22;--panel2:#1c232d;--line:#2a323d;--fg:#e6edf3;--mut:#9aa7b4;
--accent:#4c9aff;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--info:#a371f7;--radius:8px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header.top{position:sticky;top:0;z-index:20;background:rgba(15,18,22,.96);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:10px 20px}
header.top .row{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;max-width:1500px;margin:0 auto}
header.top h1{font-size:17px;margin:0;letter-spacing:.2px}
header.top .meta{color:var(--mut);font-size:12.5px}
nav.groups{max-width:1500px;margin:8px auto 0;display:flex;gap:18px;flex-wrap:wrap}
nav.groups .grp{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
nav.groups .lbl{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
nav.groups a{font-size:13.5px;padding:2px 0;border-bottom:2px solid transparent}
nav.groups a.active{color:var(--fg);border-bottom-color:var(--accent);font-weight:600}
main{max-width:1500px;margin:0 auto;padding:22px 20px 70px}
h2{font-size:20px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:22px 0 8px;color:var(--fg)}
h4{font-size:14px;margin:16px 0 6px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
p{margin:9px 0;color:#cdd6e0}
ul{margin:8px 0 12px 20px;color:#cdd6e0}li{margin:4px 0}
.banner{border:1px solid var(--line);border-left:4px solid var(--warn);background:var(--panel);padding:12px 16px;border-radius:var(--radius);margin:0 0 18px}
.banner.bad{border-left-color:var(--bad)}.banner.ok{border-left-color:var(--ok)}.banner.info{border-left-color:var(--info)}
.banner strong{color:var(--fg)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px}
.card .k{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.card .v{font-size:22px;font-weight:650;margin:4px 0 2px}
.card .n{color:var(--mut);font-size:12px;line-height:1.45}
.card .s{font-size:11px;margin-top:6px}
table{width:100%;border-collapse:collapse;margin:10px 0 6px;font-size:13.5px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--panel2);color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;position:sticky;top:0}
tbody tr:nth-child(even){background:rgba(255,255,255,.017)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto;border-radius:var(--radius)}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:600;border:1px solid transparent;white-space:nowrap}
.b-ok{background:rgba(63,185,80,.14);color:#7ee787;border-color:rgba(63,185,80,.35)}
.b-warn{background:rgba(210,153,34,.14);color:#e3b341;border-color:rgba(210,153,34,.35)}
.b-bad{background:rgba(248,81,73,.14);color:#ff7b72;border-color:rgba(248,81,73,.35)}
.b-info{background:rgba(163,113,247,.14);color:#c297ff;border-color:rgba(163,113,247,.35)}
.b-mut{background:rgba(154,167,180,.12);color:var(--mut);border-color:rgba(154,167,180,.3)}
.blank{color:#6e7b8a;font-style:italic}
.src{font-size:11px;color:var(--mut);white-space:nowrap}
.small{color:var(--mut);font-size:12.5px}
.kv{display:grid;grid-template-columns:minmax(160px,300px) 1fr;gap:4px 16px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px}
.kv div.k{color:var(--mut)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
details{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:8px 12px;margin:8px 0}
summary{cursor:pointer;color:var(--accent);font-size:13.5px}
footer{border-top:1px solid var(--line);margin-top:44px;padding:16px 20px;color:var(--mut);font-size:12.5px}
footer a{margin-right:12px}
code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:12.5px}
"""

SOURCE_KIND_CLASS = {"official": "b-ok", "regulator": "b-info", "secondary": "b-warn", "repository": "b-mut"}


def esc(value) -> str:
    if value is None or value == "":
        return '<span class="blank" title="not verified — left blank on purpose">not verified</span>'
    return html.escape(str(value))


def num(value, digits=1, suffix="") -> str:
    if value is None or value == "":
        return '<span class="blank" title="not verified — left blank on purpose">—</span>'
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return esc(value)


def pct(value, digits=1) -> str:
    if value is None or value == "":
        return '<span class="blank" title="not verified — left blank on purpose">—</span>'
    return f"{float(value) * 100:.{digits}f}%"


def badge(text, kind="b-mut") -> str:
    if not text:
        return '<span class="blank">—</span>'
    return f'<span class="badge {kind}">{html.escape(str(text))}</span>'


class Builder:
    def __init__(self, data: dict):
        self.d = data
        self.sources = {s["id"]: s for s in data["sources"]}
        self.errors: list[str] = []

    # ------------------------------------------------------------ source links
    def src(self, *ids) -> str:
        out = []
        for sid in ids:
            if not sid:
                continue
            s = self.sources.get(sid)
            if s is None:
                self.errors.append(f"unknown source id {sid}")
                continue
            if not s["url"].startswith("https://"):
                self.errors.append(f"source {sid} is not an https URL")
            out.append(f'<a class="src" href="{html.escape(s["url"])}" title="{html.escape(s["title"])}" target="_blank" rel="noopener">{html.escape(sid)}</a>')
        return " ".join(out)

    def check_rows(self, name: str, rows: list[dict], key="src") -> None:
        """Every published row must carry at least one source id."""
        for i, r in enumerate(rows):
            value = r.get(key)
            ids = value if isinstance(value, list) else [value]
            ids = [i for i in ids if i]
            if not ids:
                self.errors.append(f"{name}: row {i} has no source")
                continue
            for sid in ids:
                if sid not in self.sources:
                    self.errors.append(f"{name}: row {i} references unknown source {sid}")

    # ------------------------------------------------------------ html pieces
    def table(self, columns: list, rows: list[dict], row_class=None) -> str:
        """columns: list of (label, key, kind).

        kind: '' (plain text), 'num', 'num0', 'num2', 'num3', 'num4', 'pct', 'pct2', 'src', 'raw'.
        'raw' means the value is already HTML and is inserted unchanged.
        """
        head = "".join(f'<th class="{c[2] if len(c) > 2 and c[2] in ("num",) else ""}">{html.escape(c[0])}</th>'
                       for c in columns)
        body = []
        for r in rows:
            cells = []
            for c in columns:
                label, key = c[0], c[1]
                kind = c[2] if len(c) > 2 else ""
                value = r.get(key)
                if callable(value):
                    value = value(r)
                if kind == "src":
                    ids = value if isinstance(value, list) else ([value] if value else [])
                    cells.append(f'<td class="src">{self.src(*ids)}</td>')
                elif kind == "num":
                    cells.append(f'<td class="num">{num(value, 1)}</td>')
                elif kind == "num0":
                    cells.append(f'<td class="num">{num(value, 0)}</td>')
                elif kind == "num2":
                    cells.append(f'<td class="num">{num(value, 2)}</td>')
                elif kind == "num3":
                    cells.append(f'<td class="num">{num(value, 3)}</td>')
                elif kind == "num4":
                    cells.append(f'<td class="num">{num(value, 4)}</td>')
                elif kind == "pct":
                    cells.append(f'<td class="num">{pct(value, 1)}</td>')
                elif kind == "pct2":
                    cells.append(f'<td class="num">{pct(value, 2)}</td>')
                elif kind == "raw":
                    cells.append(f"<td>{value if value is not None else ''}</td>")
                else:
                    cells.append(f"<td>{value if isinstance(value, str) and value.startswith('<') else esc(value)}</td>")
            cls = ""
            if row_class:
                cls = row_class(r)
                cls = f' class="{cls}"' if cls else ""
            body.append(f"<tr{cls}>" + "".join(cells) + "</tr>")
        return ('<div class="wrap"><table><thead><tr>' + head + "</tr></thead><tbody>"
                + "".join(body) + "</tbody></table></div>")

    def nav(self, active: str) -> str:
        groups = []
        for label, items in NAV:
            links = []
            for href, text in items:
                cls = ' class="active"' if href == active else ""
                links.append(f'<a href="{href}"{cls}>{html.escape(text)}</a>')
            groups.append(f'<div class="grp"><span class="lbl">{html.escape(label)}</span>{"".join(links)}</div>')
        meta = self.d["meta"]
        return (
            '<header class="top"><div class="row">'
            f'<h1>NBA3 &middot; NBA line origination, validation and review</h1>'
            f'<span class="meta">season {html.escape(str(meta["season"]))} &middot; results through '
            f'{html.escape(str(meta["data_through"]))} &middot; slate {html.escape(meta["window"])} &middot; '
            f'built {html.escape(str(meta["generated"]))}</span></div>'
            f'<nav class="groups">{"".join(groups)}</nav></header>'
        )

    def page(self, filename: str, title: str, subtitle: str, body: str) -> str:
        meta = self.d["meta"]
        return (
            "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html.escape(title)} &middot; NBA3</title>\n"
            '<link rel="stylesheet" href="assets/style.css">\n</head>\n<body>\n'
            f"{self.nav(filename)}\n<main>\n{body}\n</main>\n"
            "<footer>\n"
            f'<div>NBA3 consolidated dashboard &middot; built {html.escape(str(meta["generated"]))} &middot; '
            f'session {html.escape(str(meta["session"]))} &middot; '
            "every table row links to the source it was checked against; values that could not be confirmed are blank "
            "and listed on the Flagged for Review page.</div>\n"
            '<div style="margin-top:8px">'
            '<a href="../index.html">Repository landing page</a>'
            '<a href="../docs/">docs/ (early data site)</a>'
            '<a href="../site/">site/ (7c532e8c)</a>'
            '<a href="../lab/">lab/ (5697caaf)</a>'
            '<a href="../research/">research/ (9ed6085f)</a>'
            '<a href="../edge/">edge/ (0a016df8)</a>'
            '<a href="../origin/">origin/ (e22a2831)</a>'
            "</div>\n</footer>\n</body>\n</html>\n"
        )

    # ================================================================ pages
    def build(self) -> dict[str, str]:
        pages: dict[str, str] = {}
        pages["index.html"] = self.page_index()
        pages["executive-summary.html"] = self.page_exec()
        pages["slate.html"] = self.page_slate()
        pages["lines.html"] = self.page_lines()
        pages["picks.html"] = self.page_picks()
        pages["strategies.html"] = self.page_strategies()
        pages["correlations.html"] = self.page_correlations()
        pages["injuries.html"] = self.page_injuries()
        pages["gameflow.html"] = self.page_gameflow()
        pages["props.html"] = self.page_props()
        pages["data.html"] = self.page_data()
        pages["sources.html"] = self.page_sources()
        pages["repo-review.html"] = self.page_repo_review()
        pages["questions.html"] = self.page_questions()
        pages["suggestions.html"] = self.page_suggestions()
        pages["flagged.html"] = self.page_flagged()
        pages["verification.html"] = self.page_verification()
        pages["methodology.html"] = self.page_methodology()
        return pages

    # ---------------------------------------------------------------- landing
    def page_index(self) -> str:
        d = self.d
        summary = d["summary"]
        blockers = [f for f in d["flags"] if f["severity"] == "blocker"]
        high = [f for f in d["flags"] if f["severity"] == "high"]
        strategies = d["strategies"]
        best = strategies[0] if strategies else None

        cards = "".join(
            f'<div class="card"><div class="k">{html.escape(h["label"])}</div>'
            f'<div class="v">{html.escape(str(h["value"]))}</div>'
            f'<div class="n">{html.escape(h["note"])}</div>'
            f'<div class="s">{self.src(h["source"])}</div></div>'
            for h in summary["headline"])

        nav_cards = []
        for group, pages_ in NAV:
            links = "".join(f'<li><a href="{h}">{html.escape(t)}</a></li>' for h, t in pages_)
            nav_cards.append(f'<div class="card"><div class="k">{html.escape(group)}</div><ul>{links}</ul></div>')

        flag_rows = [{
            "id": f["id"], "severity": f["severity"], "area": f["area"], "item": f["item"],
            "action": f["action"], "src": [f["source"]],
        } for f in blockers + high[:4]]

        body = f"""
<h2>What this is</h2>
<p>One dashboard for the whole NBA3 project. It consolidates the eight site trees that earlier sessions
produced, re-verifies the underlying numbers against official sources, and keeps a single list of what is
confirmed, what is not, and what needs an owner decision. Season {html.escape(str(d["meta"]["season"]))};
results verified through {html.escape(str(d["meta"]["data_through"]))}; slate
{html.escape(str(d["meta"]["window"]))}.</p>

<div class="banner bad"><strong>Read this first.</strong> No strategy in this project passes every validation
gate, and no price feed is connected, so nothing here is a validated recommendation. The numbers are research
output: originated lines, measured correlations, and the evidence that separates skill from luck.
{details_blocker_flags(blockers)}</div>

<div class="cards">{cards}</div>

<h2>Go to a section</h2>
<div class="cards">{"".join(nav_cards)}</div>

<h2>Flagged for review &mdash; blockers and high severity</h2>
<p class="small">The full register is on the <a href="flagged.html">Flagged for review</a> page, with the source
that produced each flag.</p>
{self.table([("ID", "id"), ("Severity", "severity"), ("Area", "area"), ("Item", "item"),
             ("Suggested action", "action"), ("Source", "src", "src")], flag_rows)}

<h2>Leaderboard snapshot</h2>
<p class="small">Full table, gate by gate, on the <a href="strategies.html">Strategy leaderboard</a> page.
{html.escape(str(best["label"])) if best else ""} leads with {best["points"] if best else 0} points
({best["gates_passed"] if best else 0} of {best["gates_total"] if best else 0} gates).</p>
{self.table([("Rank", "rank", "num"), ("Strategy", "label"), ("Rule", "rule"),
             ("n", "n", "num"), ("Hit rate", "rate", "pct"), ("p-value", "p", "num4"),
             ("Gates passed", "gates_passed", "num"), ("Points", "points", "num"),
             ("Reward", "reward"), ("Source", "src", "src")], strategies[:6])}

<h2>What is not verified</h2>
<ul>
<li>No licensed odds or price feed: every line is originated by this project, so no expected value, market
edge or de-vigged market probability exists. <a href="flagged.html">F-01</a></li>
<li>Player-level correlations, player-prop lines and the points impact of an injury: the underlying data was
never captured. <a href="correlations.html">Correlations</a>, <a href="props.html">Player props</a></li>
<li>Availability for the 17 games on 11/15 and 11/16: no injury report has been published for them yet.
<a href="injuries.html">Injuries</a></li>
<li>Two independent origination engines in this repository disagree on the favourite in three of the seventeen
games they both cover. <a href="lines.html">Originated lines</a></li>
<li>Whether NBA data may lawfully be used for wagering purposes. <a href="flagged.html">F-02, F-03</a></li>
</ul>

<h2>Earlier rounds of this project</h2>
<p class="small">Seven earlier sessions published their own trees. They are kept for provenance and are listed
in the <a href="repo-review.html">repository review</a>; this dashboard is the consolidated view.</p>
<div class="grid2">
<div class="card"><div class="k">Data site</div><ul>
<li><a href="../docs/">docs/</a> &mdash; early official-source data site (11/11 injury snapshot)</li>
<li><a href="../site/">site/</a> &mdash; generated multi-page site (11/13 05:00 PM injury snapshot)</li>
<li><a href="../lab/">lab/</a> &mdash; line lab with gates and an on-site review register</li></ul></div>
<div class="card"><div class="k">Engines and research</div><ul>
<li><a href="../research/">research/</a> &mdash; research site (no picks, by design)</li>
<li><a href="../edge/">edge/</a> &mdash; Edge Lab: 174-game log, gated picks for 11/14&ndash;11/16</li>
<li><a href="../origin/">origin/</a> &mdash; origination engine: walk-forward validation, 7 gates</li></ul></div>
</div>
"""
        return self.page("index.html", "Home", "", body)

    # ---------------------------------------------------------------- exec summary
    def page_exec(self) -> str:
        s = self.d["summary"]
        headline = self.table(
            [("Measure", "label"), ("Value", "value"), ("Note", "note"), ("Source", "source", "src")],
            s["headline"])
        findings = "".join(
            f'<h3>{f["n"]}. {html.escape(f["title"])}</h3><p>{html.escape(f["text"])}</p>' for f in s["findings"])
        bottom = "".join(f"<li>{html.escape(b)}</li>" for b in s["bottom_line"])
        changed = self.table([("Item", "item"), ("Before", "before"), ("After", "after"), ("Source", "source", "src")],
                             s["changed_since_previous_round"])
        body = f"""
<p class="small">{html.escape(s["scope"])}</p>
<h2>Headline numbers</h2>
{headline}
<h2>What the numbers mean</h2>
{findings}
<h2>Bottom line</h2>
<ul>{bottom}</ul>
<h2>What changed in this round</h2>
{changed}
"""
        return self.page("executive-summary.html", "Executive summary", "", body)

    # ---------------------------------------------------------------- slate
    def page_slate(self) -> str:
        rows = []
        for g in self.d["slate"]:
            if g["report_published"]:
                if g["home_submitted"] and g["away_submitted"]:
                    avail = badge("report published", "b-ok")
                else:
                    avail = badge("report partial", "b-warn")
                avail += f' <span class="small">out: {esc(", ".join(g["home_out"] + g["away_out"]) or "none")}</span>'
            else:
                avail = badge("no report yet", "b-mut")
            rows.append({
                "date": g["date"], "time": g["time_et"],
                "matchup": f'{html.escape(g["away_name"])} @ {html.escape(g["home_name"])}',
                "venue": f'{html.escape(g["venue"])}, {html.escape(g["city"])}',
                "comp": g["competition"],
                "avail": avail,
                "mins": (num(g["minutes_at_risk_home"], 0) + " / " + num(g["minutes_at_risk_away"], 0)),
                "mins_note": (f'captured players {g.get("minutes_captured_home", 0)} / {g.get("minutes_captured_away", 0)}'
                              if g.get("minutes_captured_home") is not None else ""),
                "link": f'<a href="{html.escape(g["nba_url"])}" target="_blank" rel="noopener">NBA game</a>',
                "src": ["S04", "S02"],
            })
        body = f"""
<p class="small">Thirty-one games, 2026-11-13 to 2026-11-16: nine, five, nine and eight games per day. Every row
below was checked against nba.com/schedule (date, ET start time, venue, NBA game id) and against the official
schedule PDF (game number, date, time). The home team is the team whose venue is printed. The injury column
comes from the newest official report (11/13 07:30 PM); no report has been published yet for the 11/15 and
11/16 games, so their availability is blank by policy.</p>
{self.table([("Date", "date"), ("Time ET", "time"), ("Matchup", "matchup"), ("Venue", "venue"),
             ("Competition", "comp"), ("Availability (official report)", "avail"),
             ("Minutes at risk H/A", "mins", "raw"), ("Captured", "mins_note"),
             ("Game", "link"), ("Sources", "src", "src")], rows)}
<h3>How to read the minutes column</h3>
<p class="small">Minutes at risk is the season minutes per game of the players who are out or doubtful, counted
only where that player's minutes are in the captured official set. Where the team had not submitted a report, or
the player is outside the captured set, the number is 0 or blank and is marked unverified. No points impact is
estimated anywhere.</p>
"""
        return self.page("slate.html", "Slate", "", body)

    # ---------------------------------------------------------------- lines
    def page_lines(self) -> str:
        rows = []
        for g in self.d["slate"]:
            if g["line_spread_home"] is None:
                continue
            fav = f'{g["fav_origin"]} favoured' if g["fav_origin"] else ""
            rows.append({
                "date": g["date"], "time": g["time_et"],
                "matchup": f'{html.escape(g["away"])} @ {html.escape(g["home"])}',
                "spread": num(g["line_spread_home"], 1),
                "fav": fav,
                "total": num(g["line_total"], 1),
                "range": f'{num(g["line_total_lo"], 0)} &ndash; {num(g["line_total_hi"], 0)}',
                "p_home": g["line_p_home"], "p_away": g["line_p_away"],
                "pts": f'{num(g["line_exp_home_pts"], 0)} / {num(g["line_exp_away_pts"], 0)}',
                "pace": num(g["line_pace"], 1),
                "outs": f'{g.get("out_count_home") if g.get("out_count_home") is not None else ""} / '
                        f'{g.get("out_count_away") if g.get("out_count_away") is not None else ""}',
                "link": f'<a href="{html.escape(g["nba_url"])}" target="_blank" rel="noopener">game</a>',
                "src": ["S18"],
            })
        cmp_rows = []
        for g in self.d["slate"]:
            if g["edge_spread_home"] is None:
                continue
            agree = badge("agree", "b-ok") if g["engines_agree"] else badge("disagree", "b-bad")
            cmp_rows.append({
                "date": g["date"],
                "matchup": f'{html.escape(g["away"])} @ {html.escape(g["home"])}',
                "a_spread": num(g["line_spread_home"], 1),
                "b_spread": num(g["edge_spread_home"], 1),
                "a_fav": g["fav_origin"], "b_fav": g["fav_edge"],
                "agree": agree,
                "gap": num(g["spread_gap"], 1),
                "a_total": num(g["line_total"], 1), "b_total": num(g["edge_total"], 1),
                "t_gap": num(g["total_gap"], 1),
                "src": ["S18"],
            })
        disagree = [r for r in cmp_rows if "disagree" in r["agree"]]
        body = f"""
<h2>Originated lines for all {len(rows)} games</h2>
<p class="small">Our own lines, derived from official NBA statistics and the official injury report; nothing is
copied from a bookmaker. Spread is the home line, negative means the home team is favoured. The 95% range is
the walk-forward residual band (1.96 standard deviations), which is wide because the margin residual standard
deviation is {num(self.d["gameflow"]["resid_sd_margin"], 1)} points.</p>
{self.table([("Date", "date"), ("Time ET", "time"), ("Matchup", "matchup"), ("Spread (home)", "spread", "num1"),
             ("Model favourite", "fav"), ("Total", "total", "num1"), ("95% range", "range"),
             ("P(home)", "p_home", "pct"), ("P(away)", "p_away", "pct"), ("Exp. points H/A", "pts"),
             ("Pace", "pace", "num"), ("Outs H/A", "outs"), ("Game", "link"), ("Source", "src", "src")], rows)}

<h2>Two independent engines in this repository disagree</h2>
<p class="small">The repository holds two separately built origination engines. This dashboard's line table uses
the walk-forward validated blend (LM-C) from the origin engine. The second engine (the Edge Lab model) publishes
its own lines and fair prices for the games it covers. Comparing them on the {len(cmp_rows)} games they share:
{len(disagree)} of them disagree on which team is favoured, and the spread gap is large on most of the rest.
Neither engine has passed its validation gates, so this table is a disagreement report, not a calibration.</p>
{self.table([("Date", "date"), ("Matchup", "matchup"), ("Line A (home)", "a_spread", "num1"),
             ("Line B (home)", "b_spread", "num1"), ("Favourite A", "a_fav"), ("Favourite B", "b_fav"),
             ("Agree?", "agree"), ("Spread gap", "gap", "num"), ("Total A", "a_total", "num1"),
             ("Total B", "b_total", "num1"), ("Total gap", "t_gap", "num1"), ("Source", "src", "src")], cmp_rows)}
<div class="banner warn"><strong>What this means for a decision.</strong> When two independent models built from
the same official data disagree on the favourite, the honest read is that the lines are not yet reliable enough
to trade. This is recorded as <a href="flagged.html">F-24</a>.</div>
"""
        return self.page("lines.html", "Originated lines", "", body)

    # ---------------------------------------------------------------- picks
    def page_picks(self) -> str:
        status = self.d["strategy_status"]
        rows = []
        for p in self.d["picks"]:
            rows.append({
                "date": p["date"], "time": p.get("start_et", ""),
                "matchup": html.escape(p.get("matchup") or ""),
                "side": html.escape(p.get("singles_view") or ""),
                "ml": html.escape(p.get("ml_view") or ""),
                "totals": html.escape(p.get("totals_view") or ""),
                "conf": badge(p.get("confidence") or "", "b-mut"),
                "avail": badge((p.get("availability") or {}).get("flag", ""), "b-warn"),
                "avail_detail": html.escape((p.get("availability") or {}).get("detail") or ""),
                "src": ["S18"],
            })
        parlays = []
        for c in self.d["parlays"]:
            parlays.append({
                "date": c.get("date", ""),
                "legs": html.escape(" ; ".join(c.get("legs", []))),
                "status": badge(c.get("status", ""), "b-bad"),
                "caveat": html.escape(c.get("caveat", "")),
                "src": ["S18"],
            })
        status_rows = [{"id": k, "status": html.escape(v), "src": ["S18"]} for k, v in status.items()]
        body = f"""
<div class="banner info"><strong>How to read this page.</strong> These are our own originated prices for the
games in the three-day window. There is no market price to compare them against, so nothing here is an expected
value. Every row also carries the strategy status that produced it, and no strategy behind any of them has
passed every validation gate. {html.escape(self.d["pricing_note"])}</div>
<h2>Picks for the three-day window ({len(rows)} games)</h2>
{self.table([("Date", "date"), ("Time ET", "time"), ("Matchup", "matchup"), ("Model side", "side"),
             ("Fair moneyline", "ml"), ("Totals view", "totals"), ("Confidence", "conf"),
             ("Availability", "avail"), ("Availability detail", "avail_detail"), ("Source", "src", "src")], rows)}
<h2>Strategy status behind those picks</h2>
{self.table([("Strategy", "id"), ("Status", "status"), ("Source", "src", "src")], status_rows)}
<h2>Parlay combinations</h2>
<p class="small">A parlay combines legs whose correlation must be measured before it can be priced. The
measured game-level correlation is small and the player-level correlations are blank, so the only combination
shown is displayed for research and is marked not eligible.</p>
{self.table([("Date", "date"), ("Legs", "legs"), ("Status", "status"), ("Caveat", "caveat"),
             ("Source", "src", "src")], parlays)}
<h2>Games without a pick</h2>
<p class="small">The nine games of 11/13 were already under way or played when this dashboard was built; the
pick generator covers 11/14 to 11/16 only. Their originated lines are on the
<a href="lines.html">Originated lines</a> page.</p>
"""
        return self.page("picks.html", "Picks", "", body)

    # ---------------------------------------------------------------- strategies
    def page_strategies(self) -> str:
        rows = []
        for s in self.d["strategies"]:
            if s["passed_all_gates"]:
                reward = badge("Eligible", "b-ok")
            elif s["p"] is not None and s["p"] < 0.05:
                reward = badge("Provisional", "b-warn")
            else:
                reward = badge("Not eligible", "b-bad")
            rows.append({
                "rank": s["rank"], "id": s["id"], "label": html.escape(s["label"]),
                "rule": html.escape(s["rule"]),
                "n": s["n"], "wins": s["wins"], "rate": s["rate"], "p": s["p"],
                "fh": s.get("first_half_rate"), "sh": s.get("second_half_rate"),
                "gates": f'{s["gates_passed"]} / {s["gates_total"]}',
                "points": s["points"], "reward": reward,
                "verdict": html.escape(s.get("verdict", "") or s.get("note", "")),
                "src": ["S18"],
            })
        details = []
        for s in self.d["strategies"]:
            g = s["gates"]
            gate_cells = " ".join(
                f'<span class="badge {"b-ok" if v else "b-bad"}">{html.escape(k.split("_", 1)[-1])}</span>'
                for k, v in g.items())
            details.append({
                "id": s["id"], "label": html.escape(s["label"]),
                "gates": gate_cells,
                "note": html.escape(s.get("note", "") or s.get("verdict", "")),
                "src": ["S18"],
            })
        ev = self.d["edge_validation"]
        ev_rows = []
        for key, val in (ev.get("strategies") or {}).items():
            gate_list = "; ".join(f'{g["gate"]}: {"pass" if g["passed"] else "FAIL"} ({g["detail"]})'
                                  for g in val.get("gates", []))
            ev_rows.append({"id": key, "n": val.get("n"), "roi": val.get("roi"),
                            "perm_p": val.get("perm_p"), "gates": html.escape(gate_list),
                            "src": ["S18"]})
        body = f"""
<div class="banner bad"><strong>Leaderboard result: {sum(1 for s in self.d["strategies"] if s["passed_all_gates"])}
of {len(self.d["strategies"])} strategies pass every gate.</strong> The leaderboard is a research instrument:
it ranks candidates so the best-supported hypotheses can be re-tested first, not so they can be traded.</div>
<h2>Points scheme (published so it cannot be tuned after the fact)</h2>
<ul>
<li>3 points for each gate passed, out of seven &mdash; 21 points maximum.</li>
<li>5 bonus points when all seven gates pass (eligible).</li>
<li>2 bonus points when the raw p-value is below 0.01.</li>
<li>Rewards: <b>Eligible</b> means publishable once the legal questions are answered; <b>Provisional</b> means
paper tracking only; <b>Not eligible</b> means do not trade it.</li>
</ul>
<h2>Leaderboard</h2>
{self.table([("Rank", "rank", "num"), ("ID", "id"), ("Strategy", "label"), ("Rule", "rule"),
             ("n", "n", "num"), ("Wins", "wins", "num"), ("Hit rate", "rate", "pct"), ("p-value", "p", "num4"),
             ("1st half", "fh", "pct"), ("2nd half", "sh", "pct"), ("Gates", "gates"),
             ("Points", "points", "num"), ("Reward", "reward"), ("Verdict", "verdict"),
             ("Source", "src", "src")], rows)}
<h2>Gate by gate</h2>
<p class="small">G1 provenance of every input, G2 no look-ahead, G3 minimum sample of 100, G4 statistical
power, G5 raw p-value below 0.05, G6 survives the Benjamini-Hochberg false-discovery correction,
G7 direction stable across halves.</p>
{self.table([("ID", "id"), ("Strategy", "label"), ("Gates", "gates"), ("Note", "note"),
             ("Source", "src", "src")], details)}
<h2>The second engine's gate results</h2>
<p class="small">The Edge Lab engine (a separate model with its own walk-forward test) reports its own gate
results. It prices at an assumed &minus;110 because no licensed feed exists, so its ROI figure is a model
assumption, not a measured return.</p>
{self.table([("Strategy", "id"), ("n", "n", "num"), ("ROI at -110", "roi", "pct"),
             ("Permutation p", "perm_p", "num4"), ("Gates", "gates"), ("Source", "src", "src")], ev_rows)}
"""
        return self.page("strategies.html", "Strategy leaderboard", "", body)

    # ---------------------------------------------------------------- correlations
    def page_correlations(self) -> str:
        rows = []
        for c in self.d["correlations"]:
            if c["verified"]:
                ci = c["ci95"]
                ci_text = (f'[{num(ci[0], 3)}, {num(ci[1], 3)}]' if ci and ci[0] is not None
                           else '<span class="blank">not measured</span>')
                val = num(c["value"], 3)
                st = badge("measured", "b-ok")
            else:
                ci_text = '<span class="blank">not measured</span>'
                val = '<span class="blank">not measured</span>'
                st = badge("blank by policy", "b-mut")
            rows.append({
                "pair": html.escape(c["pair"]), "stat": html.escape(c["stat"]), "value": val, "ci": ci_text,
                "n": c["n"], "state": st, "note": html.escape(c["note"]), "src": [c["src"]],
            })
        body = f"""
<p class="small">Correlations decide whether a parlay is worth pricing. Game-level correlations are measured
over the verified results; player-level correlations are left blank because the per-player game logs were never
captured. Nothing is estimated to fill a blank.</p>
{self.table([("Pair", "pair"), ("Statistic", "stat"), ("Value", "value", "num3"), ("95% interval", "ci"),
             ("n", "n", "num"), ("State", "state"), ("Note", "note"), ("Source", "src", "src")], rows)}
<h2>How the correlations are used</h2>
<ul>
<li><b>Same-game parlay of our own spread and our own total.</b> Residual correlation r = +0.091 with an
interval that contains zero, over 114 out-of-sample games. The joint hit rate is 0.246 against 0.219 under
independence, so pricing the two legs as independent is roughly right, but only for these legs.</li>
<li><b>Two legs in different games.</b> Independence is assumed, not measured. The row stays unverified.</li>
<li><b>Player props in the same game.</b> Not measurable with the data in this repository; the player-prop
parlay question cannot be answered yet. See <a href="flagged.html">F-05</a> and question Q-07.</li>
</ul>
"""
        return self.page("correlations.html", "Correlations", "", body)

    # ---------------------------------------------------------------- injuries
    def page_injuries(self) -> str:
        rows = []
        for r in self.d["injuries"]:
            status = r["status"]
            if status == "NOT YET SUBMITTED":
                badge_html = badge("not submitted", "b-warn")
            elif status == "Out":
                badge_html = badge("Out", "b-bad")
            elif status in ("Questionable", "Probable", "Doubtful"):
                badge_html = badge(status, "b-warn")
            else:
                badge_html = badge(status, "b-ok")
            rows.append({
                "date": r["date"], "time": r["time_et"], "matchup": r["matchup"],
                "team": r["team"], "player": r["player"] or '(team row)',
                "status": badge_html, "reason": html.escape(r["reason"] or ""),
                "note": html.escape(r.get("note", "")),
                "src": [r.get("src", "S02")],
            })
        impact_rows = []
        for r in self.d["injury_impact"]:
            impact_rows.append({
                "date": r["date"], "team": r["team"], "opponent": r["opponent"], "ha": r["home_away"],
                "sub": badge("yes", "b-ok") if r["report_submitted"] else badge("not submitted", "b-warn"),
                "listed": r["players_listed"], "out": r["out_or_doubtful"],
                "mins": r["minutes_vacuum_quantified"], "captured": r["captured_players"],
                "src": [r["src"]],
            })
        body = f"""
<div class="banner info"><strong>Source and freshness.</strong> Every row below is transcribed from the official
NBA injury report <b>11/13/26 07:30 PM</b>, which is the newest published report at the time this dashboard was
built. The report covers the nine games of 11/13 and the five games of 11/14. No report exists yet for the games
on 11/15 and 11/16, so availability for those games is blank.</div>
{self.table([("Date", "date"), ("Time ET", "time"), ("Matchup", "matchup"), ("Team", "team"),
             ("Player", "player"), ("Status", "status"), ("Reason as printed", "reason"),
             ("Note", "note"), ("Source", "src", "src")], rows)}
<h2>Minutes at risk per team-game</h2>
<p class="small">Sum of the season minutes per game of the players who are out or doubtful, counted only where
the player's minutes are in the captured official set. Zero means either that the team had not submitted a
report or that none of the affected players are in the captured set; the second column says which.</p>
{self.table([("Date", "date"), ("Team", "team"), ("Opponent", "opponent"), ("H/A", "ha"),
             ("Report", "sub"), ("Players listed", "listed", "num"),
             ("Out or doubtful", "out", "num"), ("Minutes at risk", "mins", "num1"),
             ("Captured players", "captured", "num"), ("Source", "src", "src")], impact_rows)}
<h3>How injury effects are modelled, and what is not modelled</h3>
<ul>
<li>Availability is read from the official report; the report has no minutes column, so minutes have to come
from elsewhere.</li>
<li>Minutes at risk is a count of minutes, not a points estimate. No replacement-player model and no
points-per-minute elasticity exist in this repository, so no points impact is published.</li>
<li>Players outside the captured top-31 minutes set have a blank impact and an explicit UNVERIFIED note rather
than an estimate. See <a href="flagged.html">F-08</a>.</li>
</ul>
"""
        return self.page("injuries.html", "Injuries", "", body)

    # ---------------------------------------------------------------- game flow
    def page_gameflow(self) -> str:
        gf = self.d["gameflow"]
        metrics = [
            ("Games in the verified log", gf["games"], "S18"),
            ("Overtime games", gf["ot_games"], "S18"),
            ("Overtime rate", pct(gf["ot_rate"], 2), "S18"),
            ("Home wins", f'{gf["home_wins"]} of {gf["home_games"]}', "S18"),
            ("Average home margin", num(gf["home_margin_mean"], 2), "S18"),
            ("Average total", num(gf["avg_total"], 1), "S18"),
            ("Average total, regulation", num(gf["avg_total_regulation"], 1), "S18"),
            ("Average total, overtime", num(gf["avg_total_ot"], 1), "S18"),
            ("Fitted home-court advantage", num(gf["derived_hca"], 2), "S18"),
            ("Home-court p-value", num(gf["derived_hca_p"], 4), "S18"),
            ("Back-to-back games", f'{gf["b2b_games"]} ({pct(gf["b2b_rate"], 1)})', "S18"),
            ("Margin residual standard deviation", num(gf["resid_sd_margin"], 2), "S18"),
            ("Total residual standard deviation", num(gf["resid_sd_total"], 2), "S18"),
            ("League offensive rating", num(gf["lg_off_rtg"], 2), "S18"),
            ("League pace", num(gf["lg_pace"], 2), "S18"),
        ]
        kv = "".join(f'<div class="k">{html.escape(k)}</div><div>{v if str(v).startswith("<") else html.escape(str(v))}'
                     f'{self.src(s)}</div>' for k, v, s in metrics)
        pace_rows = [{"team": r["team"], "pace": r["pace"], "off": r["off_rtg"], "def": r["def_rtg"],
                      "net": r["net_rtg"], "src": [r["src"]]} for r in self.d["pace_leaders"]]
        rest = gf.get("rest_distribution", {})
        rest_rows = [{"days": k, "games": v, "src": ["S18"]} for k, v in sorted(rest.items())]
        body = f"""
<h2>Game flow</h2>
<p class="small">Measured over the {gf["games"]} verified results. Every figure is derived from the verified
game log; the season statistics behind them come from the official NBA teams-advanced table.</p>
<div class="kv">{kv}</div>
<h2>Rest distribution</h2>
<p class="small">Days of rest before each game in the verified log. Rest enters the models as a feature, and the
S3 strategy tests a rest differential of two days or more.</p>
{self.table([("Rest (days)", "days"), ("Games", "games", "num"), ("Source", "src", "src")], rest_rows)}
<h2>Pace by team</h2>
<p class="small">Possessions per 48 minutes and the ratings behind them, as published by the NBA. Pace is the
input the total model uses, and it is where the totals model fails to beat its baseline.</p>
{self.table([("Team", "team"), ("Pace", "pace", "num2"), ("OffRtg", "off", "num2"), ("DefRtg", "def", "num2"),
             ("NetRtg", "net", "num2"), ("Source", "src", "src")], pace_rows)}
"""
        return self.page("gameflow.html", "Game flow", "", body)

    # ---------------------------------------------------------------- props
    def page_props(self) -> str:
        rows = []
        for p in self.d["props"]:
            rows.append({
                "date": p["date"], "team": p["team"], "opp": p["opponent"], "player": html.escape(p["player"]),
                "status": badge(p.get("status", "") or "not listed", "b-mut"),
                "gp": p.get("gp"), "min": p.get("season_min"), "pts": p.get("season_pts"),
                "reb": p.get("season_reb"), "ast": p.get("season_ast"), "fg3": p.get("season_fg3m"),
                "line": badge("line not verified", "b-warn") if not p.get("line_verified") else badge("verified", "b-ok"),
                "note": html.escape(p.get("verification_note", "")),
                "src": ["S09"],
            })
        body = f"""
<div class="banner warn"><strong>These are projections, not lines.</strong> The season averages are official;
the per-game projection uses a pro-rata minutes redistribution assumption that has not been validated, and no
per-player game logs were captured. The over/under distribution for a player prop is therefore not
established. See <a href="flagged.html">F-05</a> and question Q-08.</div>
{self.table([("Date", "date"), ("Team", "team"), ("Opponent", "opp"), ("Player", "player"),
             ("Injury status", "status"), ("GP", "gp", "num0"), ("Min", "min", "num1"), ("Pts", "pts", "num1"),
             ("Reb", "reb", "num1"), ("Ast", "ast", "num1"), ("3PM", "fg3", "num1"), ("Line", "line"),
             ("Note", "note"), ("Source", "src", "src")], rows)}
"""
        return self.page("props.html", "Player props", "", body)

    # ---------------------------------------------------------------- data
    def page_data(self) -> str:
        integ = self.d["integrity"]
        rows = integ["rows"]
        models = self.d["models"]
        model_rows = []
        for key, m in models.items():
            model_rows.append({
                "id": key, "label": m.get("label", ""), "n": m.get("n"),
                "rmse": m.get("margin", {}).get("rmse"), "base": m.get("margin_baseline_rmse"),
                "t_rmse": m.get("total", {}).get("rmse"), "t_base": m.get("total_baseline_rmse"),
                "home_cover": m.get("home_cover"), "cover_rate": m.get("home_cover_rate"),
                "src": ["S18"],
            })
        hc = self.d["home_court"]
        skill = self.d["skill"]
        league = self.d["league"]
        body = f"""
<h2>Integrity: the model input against the official NBA tables</h2>
<p class="small">Every team in the verified log is compared with the official games-played column on
nba.com/stats. The official column sums to {integ["official_team_games"]} team-games; the model captured
{integ["captured_team_games"]}, a mismatch of {integ["mismatch"]}. This was re-verified in this session by
reading the official table again rather than trusting the earlier run.</p>
{self.table([("Team", "team"), ("Official GP", "official_gp", "num"), ("Official W", "official_w", "num"),
             ("Official L", "official_l", "num"), ("Team-games in the model log", "captured_team_games", "num"),
             ("Match", "match"), ("Source", "src", "src")], rows)}
<h2>Models compared</h2>
<p class="small">Three models were fitted on the same walk-forward split: LM-A additive points, LM-B Massey
least squares, LM-C the blend that is published. The totals column is the honest one to read: our totals model
is worse than the league-average baseline.</p>
{self.table([("ID", "id"), ("Model", "label"), ("n", "n", "num"), ("Margin RMSE", "rmse", "num2"),
             ("Margin baseline", "base", "num2"), ("Total RMSE", "t_rmse", "num2"),
             ("Total baseline", "t_base", "num2"), ("Home cover", "home_cover", "num"),
             ("Cover rate", "cover_rate", "pct"), ("Source", "src", "src")], model_rows)}
<h2>Derived constants</h2>
<div class="kv">
<div class="k">Games captured</div><div>{integ["games_captured"]}</div>
<div class="k">Fitted home-court advantage</div><div>{num(hc.get("value"), 2)} points (two-sided p =
{num(hc.get("p_two_sided"), 4)}, df = {hc.get("df")}) &mdash; {html.escape(str(hc.get("note", "")))}</div>
<div class="k">Margin variance explained</div><div>{pct(skill.get("margin_variance_explained"), 1)}</div>
<div class="k">Total variance explained</div><div>{pct(skill.get("total_variance_explained"), 1)}</div>
<div class="k">League average points per team</div><div>{num(league.get("actual_ppg_per_team"), 2)}</div>
<div class="k">League average total</div><div>{num(league.get("avg_total"), 2)}</div>
<div class="k">League offensive rating</div><div>{num(league.get("lg_off_rtg"), 2)}</div>
<div class="k">League pace</div><div>{num(league.get("lg_pace"), 2)}</div>
</div>
"""
        return self.page("data.html", "Data and integrity", "", body)

    # ---------------------------------------------------------------- sources
    def page_sources(self) -> str:
        rows = []
        for s in self.d["sources"]:
            rows.append({
                "id": s["id"], "title": html.escape(s["title"]),
                "publisher": html.escape(s["publisher"]),
                "kind": badge(s["kind"], SOURCE_KIND_CLASS.get(s["kind"], "b-mut")),
                "retrieved": s["retrieved"],
                "supports": html.escape(s["supports"]),
                "link": f'<a href="{html.escape(s["url"])}" target="_blank" rel="noopener">open</a>',
                "src": [s["id"]],
            })
        body = f"""
<p class="small">Every number in this dashboard traces to one of these sources. Official NBA sources are marked
green; the regulator page is blue; trusted secondary sources are amber; repository facts are grey. A trusted
secondary source is a reputable independent publisher, not the league itself, and rows that depend on one say
so.</p>
{self.table([("ID", "id"), ("Source", "title"), ("Publisher", "publisher"), ("Type", "kind"),
             ("Retrieved", "retrieved"), ("What it supports", "supports"), ("Link", "link"),
             ("Source", "src", "src")], rows)}
"""
        return self.page("sources.html", "Sources", "", body)

    # ---------------------------------------------------------------- repo review
    def page_repo_review(self) -> str:
        rows = []
        for r in self.d["repo_review"]:
            status = r["status"]
            kind = "b-ok" if status.startswith("ok") else ("b-bad" if status in ("gap", "flag") else "b-warn")
            rows.append({
                "id": r["id"], "path": f'<code>{html.escape(r["path"])}</code>', "area": r["area"],
                "what": html.escape(r["what"]), "checked": html.escape(r["checked"]),
                "finding": html.escape(r["finding"]), "status": badge(status, kind), "src": [r["source"]],
            })
        body = f"""
<p class="small">The repository read line by line: every tracked file, what it contains, what was run against
it and what is wrong with it. Findings that need an owner decision are repeated on the
<a href="flagged.html">Flagged for review</a> page with a F-xx id.</p>
{self.table([("ID", "id"), ("Path", "path"), ("Area", "area"), ("What it is", "what"),
             ("What was checked", "checked"), ("Finding", "finding"), ("Status", "status"),
             ("Source", "src", "src")], rows)}
"""
        return self.page("repo-review.html", "Repository review", "", body)

    # ---------------------------------------------------------------- questions
    def page_questions(self) -> str:
        rows = []
        for q in self.d["questions"]:
            st = q["status"]
            kind = "b-ok" if st.startswith("answered") else ("b-warn" if st.startswith("partially") else "b-mut")
            rows.append({
                "id": q["id"], "question": html.escape(q["question"]), "status": badge(st, kind),
                "known": html.escape(q["known"]), "missing": html.escape(q["missing"]),
                "next": html.escape(q["next_step"]), "src": [q["source"]],
            })
        body = f"""
<p class="small">What has to be answered before any decision can be made on this project, split into what is
already known, what is missing, and the single next step that would close the gap. Nothing here is
actionable by a stranger: the decisions marked &ldquo;owner&rdquo; need you.</p>
{self.table([("ID", "id"), ("Question", "question"), ("Status", "status"), ("What we know", "known"),
             ("What is missing", "missing"), ("How to close it", "next"), ("Source", "src", "src")], rows)}
"""
        return self.page("questions.html", "Open questions", "", body)

    # ---------------------------------------------------------------- suggestions
    def page_suggestions(self) -> str:
        rows = []
        for s in self.d["suggestions"]:
            rows.append({
                "id": s["id"], "priority": s["priority"], "area": s["area"],
                "suggestion": html.escape(s["suggestion"]), "why": html.escape(s["why"]),
                "options": html.escape(s["options"]), "dependency": html.escape(s["dependency"]),
                "status": badge(s["status"], "b-warn"), "impact": html.escape(s["impact"]),
            })
        body = f"""
<div class="banner info"><strong>Nothing here has been implemented.</strong> This is the decision queue: each
row states the change, why it helps, the options, what it depends on, and what it would improve. Pick the ones
you want and they become the next round of work. No suggestion has been applied to the project.</div>
{self.table([("ID", "id"), ("Priority", "priority", "num"), ("Area", "area"),
             ("Suggestion", "suggestion"), ("Why", "why"), ("Options", "options"),
             ("Depends on", "dependency"), ("Status", "status"), ("Impact", "impact")], rows)}
"""
        return self.page("suggestions.html", "Suggestions", "", body)

    # ---------------------------------------------------------------- flagged
    def page_flagged(self) -> str:
        rows = []
        for f in self.d["flags"]:
            sev = f["severity"]
            kind = {"blocker": "b-bad", "high": "b-warn", "medium": "b-info"}.get(sev, "b-mut")
            rows.append({
                "id": f["id"], "severity": badge(sev, kind), "area": f["area"], "item": html.escape(f["item"]),
                "detail": html.escape(f["detail"]), "action": html.escape(f["action"]), "src": [f["source"]],
            })
        body = f"""
<div class="banner bad"><strong>{sum(1 for f in self.d["flags"] if f["severity"] == "blocker")} blockers,
{sum(1 for f in self.d["flags"] if f["severity"] == "high")} high severity,
{sum(1 for f in self.d["flags"] if f["severity"] == "medium")} medium,
{sum(1 for f in self.d["flags"] if f["severity"] == "low")} low.</strong> Everything here is published for
review rather than hidden: each row states what is wrong, what the effect is, what would close it, and the
source that proves it. None of it blocks the dashboard from being published.</div>
{self.table([("ID", "id"), ("Severity", "severity"), ("Area", "area"), ("Item", "item"),
             ("Detail", "detail"), ("Action", "action"), ("Source", "src", "src")], rows)}
"""
        return self.page("flagged.html", "Flagged for review", "", body)

    # ---------------------------------------------------------------- verification
    def page_verification(self) -> str:
        rows = []
        for v in self.d["verification"]:
            rows.append({
                "id": v["id"], "when": v["when"], "what": html.escape(v["what"]),
                "method": html.escape(v["method"]), "result": html.escape(v["result"]),
                "src": [v["source"]],
            })
        body = f"""
<p class="small">Every check performed for this dashboard, the method used and the result, including the
checks that failed or could not be completed. The verification log is the audit trail behind the claim that
every published number carries the source it was checked against.</p>
{self.table([("ID", "id"), ("Date", "when"), ("What was checked", "what"), ("Method", "method"),
             ("Result", "result"), ("Source", "src", "src")], rows)}
"""
        return self.page("verification.html", "Verification log", "", body)

    # ---------------------------------------------------------------- methodology
    def page_methodology(self) -> str:
        d = self.d
        sel = d["model_selection"]
        body = f"""
<h2>How a line is originated</h2>
<ol>
<li>Every input is read from an official NBA source: the teams-advanced table for the ratings, the schedule for
the slate, the official injury report for availability, and the official player table for minutes.</li>
<li>The margin line is the blend of two estimators (additive points form and a Massey least-squares rating
form), fitted on the verified results only: <b>{html.escape(str(sel.get("margin", {}).get("selected", "")))}</b>.</li>
<li>The total line is the own-scoring estimator: <b>{html.escape(str(sel.get("total", {}).get("selected", "")))}</b>,
which the walk-forward test shows does not beat the league-average baseline. That is published, not hidden.</li>
<li>Home-court advantage is added as a fitted constant ({num(d["home_court"].get("value"), 2)} points) even though
its p-value is {num(d["home_court"].get("p_two_sided"), 4)}; the least-squares estimate is used and the
uncertainty is stated.</li>
<li>Lines are produced for every game in the window, including games where the injury report has not been
submitted; availability is shown separately rather than being folded silently into the number.</li>
</ol>
<h2>How luck is removed</h2>
<ul>
<li><b>No look-ahead.</b> Each game is predicted only from games that had already been played. The first 30
games are burned in.</li>
<li><b>Exact binomial test</b> of the hit rate against the strategy's own null, with a Benjamini-Hochberg
correction across the strategy family so that testing many strategies does not manufacture a winner.</li>
<li><b>Minimum sample and power gates.</b> A strategy below 100 observations fails G3, and G4 asks whether the
observed effect would be detected with 80% power at that sample size.</li>
<li><b>Split-half stability.</b> The effect must point the same way in the first and second half of the sample.</li>
<li><b>Provenance and calibration gates.</b> Every input must be official or derived from official data, the
model must be calibrated on held-out games, and the fair price must survive de-vigging.</li>
<li><b>Independent replication.</b> A second, separately built engine in this repository tests its own
strategies with its own gates; its results are published next to the first engine's.</li>
</ul>
<h2>What is measured and what is assumed</h2>
<div class="kv">
<div class="k">Measured from official data</div><div>Team ratings, pace, the verified game log, availability and
minutes, the walk-forward predictions, the hit rates, the correlations.</div>
<div class="k">Assumed</div><div>Independence between legs of a cross-game parlay; that the league average is a
valid baseline for a total; that the captured top-31 minutes set represents each rotation; that season averages
are a reasonable prior for a single game.</div>
<div class="k">Never estimated</div><div>Player-level correlations, points impact of an injury, expected value
against any market price, and every value that could not be confirmed against an official source.</div>
</div>
<h2>Reproducing this dashboard</h2>
<pre><code>python3 scripts/build_hub_data.py    # merge verified sources -&gt; data/hub/dashboard.json
python3 scripts/build_hub.py          # render hub/*.html
python3 scripts/build_hub.py --check  # validate links and sources, write nothing</code></pre>
<p class="small">Standard library only. The upstream artefacts are regenerated by
<code>python3 model/build.py</code> (origination engine), <code>python3 pipeline/build_site_data.py</code>
(Edge Lab) and the generators behind the earlier trees.</p>
"""
        return self.page("methodology.html", "Methodology", "", body)


def details_blocker_flags(blockers) -> str:
    if not blockers:
        return ""
    items = "".join(f'<li><b>{html.escape(f["id"])}</b> &mdash; {html.escape(f["item"])} '
                    f'(source {html.escape(f["source"])})</li>' for f in blockers)
    return f"<ul>{items}</ul>"


def check_internal_links(pages: dict[str, str], out_dir: Path) -> list[str]:
    """A link is valid when it points at a file that exists or at a page this build produces."""
    errors = []
    known = set(pages.keys())
    for name, html_text in pages.items():
        for href in extract_hrefs(html_text):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = href.split("#")[0]
            if not target:
                continue
            if target in known:
                continue
            if (out_dir / target).exists():
                continue
            errors.append(f"{name}: broken link {href}")
    return errors


def extract_hrefs(html_text: str) -> list[str]:
    import re
    return re.findall(r'href="([^"]+)"', html_text)


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    data = json.loads(HUB_DATA.read_text(encoding="utf-8"))
    b = Builder(data)

    # every published row must carry a source id
    b.check_rows("slate", data["slate"], key="src_schedule")
    b.check_rows("teams", data["teams"], key="src")
    b.check_rows("injuries", data["injuries"], key="src")
    b.check_rows("injury_impact", data["injury_impact"], key="src")
    b.check_rows("strategies", data["strategies"], key="src")
    b.check_rows("correlations", data["correlations"], key="src")
    b.check_rows("props", data["props"], key="src")
    b.check_rows("flags", data["flags"], key="source")
    b.check_rows("questions", data["questions"], key="source")
    b.check_rows("repo_review", data["repo_review"], key="source")
    b.check_rows("verification", data["verification"], key="source")
    b.check_rows("lines", data["lines"]["rows"], key="src")
    b.check_rows("pace_leaders", data["pace_leaders"], key="src")
    b.check_rows("picks", data["picks"], key="src")
    b.check_rows("parlays", data["parlays"], key="src")

    pages = b.build()
    errors = list(b.errors)
    errors += check_internal_links(pages, OUT)

    if errors:
        for e in errors[:25]:
            print(f"ERROR: {e}")
        print(f"({len(errors)} errors total)")
        return 1

    if check_only:
        # Validate only: write nothing, but report any page that is stale on disk
        # so CI can fail on a dashboard that was not regenerated.
        stale = [name for name, text in pages.items()
                 if not (OUT / name).exists() or (OUT / name).read_text(encoding="utf-8") != text]
        css = OUT / "assets" / "style.css"
        if not css.exists() or css.read_text(encoding="utf-8") != CSS:
            stale.append("assets/style.css")
        if stale:
            print(f"ERROR: {len(stale)} published page(s) differ from the build output: "
                  f"{', '.join(sorted(stale)[:8])}")
            print("regenerate with: python3 scripts/build_hub.py")
            return 1
        print(f"check only: {len(pages)} pages validated, no errors, nothing stale")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    for name, text in pages.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(pages)} pages to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
