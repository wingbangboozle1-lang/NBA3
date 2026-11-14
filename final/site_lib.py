"""Shared rendering helpers for the consolidated NBA3 dashboard (standard library only)."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard"  # published under /dashboard/ so it never collides
                          # with the canonical root dashboard owned by session
                          # arena/a459dadf-nba3

TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors", "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764,
}

REPO_URL = "https://github.com/wingbangboozle1-lang/NBA3"

NAV = [
    ("Overview", [("index.html", "Home"),
                  ("executive-summary.html", "Executive summary")]),
    ("Lines & output", [("methodology.html", "Methodology"),
                        ("lines.html", "Originated lines"),
                        ("projections.html", "Slate projections")]),
    ("Strategies", [("strategies.html", "Leaderboard"),
                    ("validation.html", "Validation gates"),
                    ("correlations.html", "Correlations")]),
    ("Game context", [("injuries.html", "Injuries & rotation"),
                      ("gameflow.html", "Game flow"),
                      ("data.html", "Data & team ratings")]),
    ("Decisions", [("questions.html", "Questions"),
                   ("suggestions.html", "Suggestions")]),
    ("Governance", [("flagged.html", "Flagged for Review"),
                    ("repo-review.html", "Repo review"),
                    ("sources.html", "Sources"),
                    ("archives.html", "Archives")]),
]

CSS = """
:root{
  --navy:#0e1a30; --navy2:#16264a; --blue:#2f6bff; --blue-d:#1e4fd0;
  --bg:#f3f6fb; --panel:#ffffff; --ink:#17223a; --muted:#63718c;
  --line:#e0e7f1; --amber:#fff6e0; --amber-l:#e8a417; --red:#fdecec; --red-l:#c0392b;
  --green:#e6f6ef; --green-l:#167a55; --grey:#eef2f8;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--blue-d)}
h1,h2,h3{line-height:1.25;margin:0 0 .5em}
code{background:var(--grey);padding:1px 5px;border-radius:4px;font-size:13px}
header.top{background:linear-gradient(135deg,var(--navy),var(--navy2));color:#fff;
  padding:22px 26px}
header.top .brand{font-weight:800;font-size:20px;letter-spacing:.2px}
header.top .sub{color:#a9bcdd;font-size:13px;margin-top:2px}
.shell{display:grid;grid-template-columns:238px minmax(0,1fr);gap:0;max-width:1500px;margin:auto}
nav.side{background:var(--panel);border-right:1px solid var(--line);padding:16px 12px;
  position:sticky;top:0;height:100vh;overflow:auto}
nav.side .grp{font-size:11px;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);
  font-weight:700;margin:16px 8px 6px}
nav.side .grp:first-child{margin-top:4px}
nav.side a{display:block;padding:7px 10px;border-radius:7px;color:var(--ink);
  text-decoration:none;font-size:14px}
nav.side a:hover{background:#eaf0ff;color:var(--blue-d)}
nav.side a.on{background:var(--navy);color:#fff;font-weight:600}
main{padding:24px 28px 60px;min-width:0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:20px 22px;margin-bottom:18px;box-shadow:0 1px 2px rgba(16,40,80,.04)}
.card>h2:first-child{margin-top:0}
h1.page{font-size:26px;margin:0 0 4px}
p.lede{color:var(--muted);margin:0 0 18px;max-width:900px}
.grid{display:grid;gap:14px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi b{display:block;font-size:24px;line-height:1.2}
.kpi small{color:var(--muted);font-size:12px}
.tile{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;text-decoration:none;color:var(--ink)}
.tile:hover{border-color:var(--blue);box-shadow:0 2px 10px rgba(47,107,255,.12)}
.tile b{display:block;margin-bottom:3px}
.tile span{color:var(--muted);font-size:13px}
.note{border-left:4px solid var(--blue);background:#eef4ff;padding:12px 14px;border-radius:6px}
.warn{border-left:4px solid var(--amber-l);background:var(--amber);padding:12px 14px;border-radius:6px}
.stop{border-left:4px solid var(--red-l);background:var(--red);padding:12px 14px;border-radius:6px}
.ok{border-left:4px solid var(--green-l);background:var(--green);padding:12px 14px;border-radius:6px}
.tw{overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f6f9fd;font-size:12px;text-transform:uppercase;letter-spacing:.05em;
  color:#47536b;position:sticky;top:0}
tbody tr:hover{background:#fafcff}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
th.n{text-align:right}
.b{display:inline-block;font-size:11px;font-weight:700;padding:2px 7px;border-radius:999px;
  white-space:nowrap;background:var(--grey);color:#4a5871}
.b.ok{background:var(--green);color:var(--green-l)}
.b.warn{background:var(--amber);color:#8a5d00}
.b.bad{background:var(--red);color:var(--red-l)}
.b.blue{background:#e6eeff;color:var(--blue-d)}
.unv{color:#9aa6bb;font-style:italic}
.src{font-size:12px}
.mut{color:var(--muted)}
footer.foot{color:var(--muted);font-size:12.5px;padding:8px 0 0;max-width:1000px}
.attrib{background:var(--navy);color:#cfe0ff;font-size:12.5px;padding:12px 28px}
.attrib a{color:#9dc0ff}
@media(max-width:1000px){
  .shell{grid-template-columns:1fr}
  nav.side{position:static;height:auto;border-right:none;border-bottom:1px solid var(--line)}
  .g4,.g3,.g2{grid-template-columns:1fr}
  main{padding:18px 14px 40px}
}
"""

JS = """
(function(){
  var boxes = document.querySelectorAll('[data-filter]');
  boxes.forEach(function(inp){
    inp.addEventListener('input', function(){
      var q = inp.value.toLowerCase();
      var target = document.getElementById(inp.getAttribute('data-filter'));
      if(!target) return;
      target.querySelectorAll('tbody tr').forEach(function(tr){
        tr.style.display = tr.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
      });
    });
  });
})();
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def team_url(abbr: str) -> str:
    return "https://www.nba.com/stats/team/{}/traditional".format(TEAM_IDS.get(abbr, ""))


def game_url(away: str, home: str, gid: str) -> str:
    return "https://www.nba.com/game/{}-vs-{}-{}".format(away.lower(), home.lower(), gid)


def src(url: str, label: str = "source") -> str:
    """Render a source link cell. Always emitted; never omitted."""
    if not url:
        return '<span class="src unv">no official source</span>'
    return '<a class="src" href="{}" target="_blank" rel="noopener">{} &#8599;</a>'.format(
        esc(url), esc(label))


def blank(note: str = "unverified") -> str:
    return '<span class="unv">&mdash;</span> <span class="b warn">{}</span>'.format(esc(note))


def badge(text: str, kind: str = "") -> str:
    return '<span class="b {}">{}</span>'.format(kind, esc(text))


def fmt(v, nd=1, dash="—"):
    if v is None:
        return dash
    try:
        return "{:,.{nd}f}".format(float(v), nd=nd)
    except (TypeError, ValueError):
        return dash


def table(headers, rows, table_id=None, filter_box=False):
    """headers: list of (label, is_numeric). rows: list of list of cell HTML."""
    th = "".join('<th class="{}">{}</th>'.format("n" if num else "", esc(lab))
                 for lab, num in headers)
    body = "".join("<tr>" + "".join("<td>{}</td>".format(c) for c in r) + "</tr>"
                   for r in rows)
    out = ""
    if filter_box and table_id:
        out += ('<div style="margin-bottom:8px"><input class="src" data-filter="{}" '
                'placeholder="Filter rows&hellip;" style="padding:6px 10px;'
                'border:1px solid var(--line);border-radius:6px;min-width:240px"></div>'
                .format(table_id))
    out += ('<div class="tw"><table id="{}"><thead><tr>{}</tr></thead>'
            '<tbody>{}</tbody></table></div>'.format(table_id or "", th, body))
    if not rows:
        out += '<p class="mut">No rows.</p>'
    return out


def page(title: str, active: str, body: str, subtitle: str = "",
         wide: bool = False) -> str:
    nav_html = []
    for group, items in NAV:
        nav_html.append('<div class="grp">{}</div>'.format(esc(group)))
        for href, label in items:
            cls = "on" if href == active else ""
            nav_html.append('<a class="{}" href="{}">{}</a>'.format(cls, href, esc(label)))
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="NBA3 line-origination research dashboard: {t}">
<title>{t} &middot; NBA3</title>
<style>{css}</style></head><body>
<header class="top"><div class="brand">NBA3 &mdash; Line Origination &amp; Strategy Lab</div>
<div class="sub">2026-27 season &middot; data through 2026-11-12 &middot; slate 2026-11-14 to 2026-11-16 (ET)</div></header>
<div class="shell">
<nav class="side" aria-label="Sections">{nav}</nav>
<main>
<h1 class="page">{t}</h1>
{sub}
{body}
<footer class="foot">
Research output only. Nothing on this site is betting advice, a wager recommendation, or a
guarantee of profit. No market prices are held, so no expected value or return is stated.
All statistics are attributed to <a href="https://www.nba.com/stats" target="_blank"
rel="noopener">NBA.com</a> per section 9(i) of the
<a href="https://www.nba.com/termsofuse" target="_blank" rel="noopener">NBA.com Terms of Use</a>.
Source repository: <a href="{repo}" target="_blank" rel="noopener">wingbangboozle1-lang/NBA3</a> &middot;
<a href="{repo}/blob/main/COORDINATION.md" target="_blank" rel="noopener">coordination board</a>.
</footer>
</main></div>
<div class="attrib">Statistical data sourced from NBA.com. Reproduced for private,
non-commercial research. NBA.com Terms of Use section 9 restricts the use of NBA Statistics
in connection with any gambling activity, including legal gambling activity &mdash; see
<a href="flagged.html">Flagged for Review</a>.</div>
<script>{js}</script>
</body></html>
""".format(t=esc(title), css=CSS, nav="".join(nav_html), body=body,
           sub=('<p class="lede">{}</p>'.format(esc(subtitle)) if subtitle else ""),
           repo=REPO_URL, js=JS)
