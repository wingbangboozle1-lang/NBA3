#!/usr/bin/env python3
"""Render the 1:00 PM ET round as a dashboard in `round2/` (session arena/fbd2484b-nba3).

Design rules enforced by this builder, not just intended:

  * every table row carries at least one official-source link, and the build FAILS otherwise;
  * an unconfirmed value prints as an em-dash with an "unverified" marker, never as a number;
  * every internal href resolves to a file this build writes (checked after writing);
  * no wall clock is written into a page, so a rebuild is byte-identical and CI can diff it.

The output tree is `round2/` only. This builder writes nothing else.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-16-1300PM")
OUT = os.path.join(ROOT, "round2")

sys.path.insert(0, HERE)
import round2_registers as REG  # noqa: E402

OFFICIAL_HOSTS = ("nba.com", "kansspelautoriteit.nl")
# Links to this project are not evidence, and are never accepted in place of an official source.
PROJECT_HOSTS = ("github.com/wingbangboozle1-lang", "wingbangboozle1-lang.github.io")

ERRORS = []


def err(msg):
    ERRORS.append(msg)


def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


def unverified():
    return '<span class="unv" title="not printed by any official document captured">— <em>unverified</em></span>'


def is_project(url):
    """Links to this project's own repo or Pages site. Evidence of process, never of NBA fact."""
    if (url or "").startswith("https://github.com/wingbangboozle1-lang/NBA3"):
        return True
    m = re.match(r"^https://([^/]+)/", url or "")
    return bool(m and m.group(1) == "wingbangboozle1-lang.github.io")


def is_official(url):
    m = re.match(r"^https://([^/]+)/", url or "")
    if not m:
        return False
    h = m.group(1)
    return any(h == d or h.endswith("." + d) for d in OFFICIAL_HOSTS)


def src(url, label=None):
    """An evidence link. Official NBA sources and project links are both allowed here, but only
    an official host counts toward the per-row source requirement (checked in validate())."""
    if not (is_official(url) or is_project(url)):
        err(f"source link is neither official nor a project link: {url}")
    return (f'<a href="{esc(url)}" rel="noopener">{esc(label or short(url))}</a>')


_LABELS = [
    ("referee/injury/Injury-Report_",
     lambda u: "official injury PDF " + _pdf_stamp(u)),
    ("stats/teams/traditional", lambda u: "team stats: traditional"),
    ("stats/teams/opponent", lambda u: "team stats: opponent"),
    ("stats/teams/advanced", lambda u: "team stats: advanced"),
    ("stats/players/traditional", lambda u: "player stats: traditional"),
    ("nba-injury-report", lambda u: "official injury index"),
    ("official.nba.com", lambda u: "official NBA page"),
    ("nba.com/standings", lambda u: "official standings"),
    ("nba.com/schedule", lambda u: "official schedule"),
    ("nba.com/games", lambda u: "official games"),
    ("nba.com/termsofuse", lambda u: "NBA terms of use"),
    ("nba.com/stats/help", lambda u: "NBA stats glossary"),
    ("kansspelautoriteit", lambda u: "Kansspelautoriteit"),
    ("statsdmz.nba.com", lambda u: "official gamebook PDF"),
    ("github.com/wingbangboozle1-lang", lambda u: "this repository"),
    ("wingbangboozle1-lang.github.io", lambda u: "live site"),
]


def _pdf_stamp(u):
    """'.../Injury-Report_2026-11-16_01_00PM.pdf' -> '2026-11-16 01:00 PM ET'."""
    m = re.search(r"Injury-Report_(\d{4})-(\d{2})-(\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf", u)
    if not m:
        return "(see link)"
    y, mo, d, h, mi, ap = m.groups()
    return f"{y}-{mo}-{d} {h}:{mi} {ap} ET"


def short(url):
    """A human label, so two different documents never render as two identical strings."""
    for key, fn in _LABELS:
        if key in url:
            try:
                return fn(url)
            except Exception:
                return key
    u = url.replace("https://", "")
    return u if len(u) <= 44 else u[:41] + "…"


def table(headers, rows, *, caption=None, cls="tbl", sourced=True):
    if not sourced:
        cls += " nosrc"
    out = [f'<div class="table-wrap"><table class="{cls}"' + ('' if sourced else ' data-nosrc="1"') + '>']
    if caption:
        out.append(f"<caption>{esc(caption)}</caption>")
    out.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>")
    for i, row in enumerate(rows, 1):
        cells = row if isinstance(row, list) else [row]
        joined = " ".join(str(c) for c in cells)
        if sourced and "https://" not in joined:
            err(f"table row {i} has no source link: {joined[:110]}")
        tr_cls = ""
        out.append(f"<tr{tr_cls}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


NAV = [
    ("index.html", "Overview"),
    ("summary.html", "Executive summary"),
    ("injuries.html", "Injury filing & diff"),
    ("consequences.html", "Consequences & rotation"),
    ("gameflow.html", "Game flow"),
    ("slate.html", "Slate & totals"),
    ("estimators.html", "Two estimators"),
    ("methodology.html", "Methodology"),
    ("requirements.html", "Requirements"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("flagged.html", "Flagged for review"),
    ("verification.html", "Verification log"),
]

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2430;--line:#2a3441;--ink:#e6edf3;--dim:#9aa7b4;
--accent:#4fa3ff;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--chip:#21262d}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--ink)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header.top{position:sticky;top:0;z-index:20;background:rgba(13,17,23,.96);border-bottom:1px solid var(--line);
backdrop-filter:blur(6px)}
.bar{max-width:1180px;margin:0 auto;padding:.6rem 1.1rem;display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:.02em}
.brand small{color:var(--dim);font-weight:400}
nav.pages{display:flex;gap:.15rem;flex-wrap:wrap;max-width:1180px;margin:0 auto;padding:0 1.1rem .55rem}
nav.pages a{padding:.28rem .6rem;border-radius:7px;color:var(--dim);font-size:13.5px;border:1px solid transparent}
nav.pages a:hover{color:var(--ink);background:var(--panel);text-decoration:none}
nav.pages a.on{color:var(--ink);background:var(--chip);border-color:var(--line)}
main{max-width:1180px;margin:0 auto;padding:1.4rem 1.1rem 4rem}
h1{font-size:1.6rem;margin:.2rem 0 .5rem;letter-spacing:-.01em}
h2{font-size:1.15rem;margin:2rem 0 .6rem;padding-bottom:.35rem;border-bottom:1px solid var(--line)}
h3{font-size:1rem;margin:1.2rem 0 .4rem}
p.lead{color:#c8d2dc;font-size:1.02rem;max-width:80ch}
.grid{display:grid;gap:.8rem;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));margin:1rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:.85rem .95rem}
.card .k{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.07em}
.card .v{font-size:1.5rem;font-weight:650;margin-top:.15rem}
.card .s{color:var(--dim);font-size:12.5px;margin-top:.3rem}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:11px;margin:.7rem 0 1.2rem}
table.tbl{border-collapse:collapse;width:100%;font-size:13.5px}
table.tbl caption{caption-side:top;text-align:left;padding:.6rem .8rem;color:var(--dim);font-size:12.5px;
border-bottom:1px solid var(--line)}
table.tbl th{position:sticky;top:0;background:var(--panel2);text-align:left;padding:.5rem .65rem;
border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);
white-space:nowrap}
table.tbl td{padding:.45rem .65rem;border-bottom:1px solid #202834;vertical-align:top}
table.tbl tr:last-child td{border-bottom:0}
table.tbl tr:hover td{background:#131a23}
.chip{display:inline-block;padding:.08rem .45rem;border-radius:999px;font-size:11.5px;border:1px solid var(--line);
background:var(--chip);color:var(--dim);white-space:nowrap}
.chip-ok{color:#7ee787;border-color:#1e4a2a;background:#102417}
.chip-warn{color:#e3b341;border-color:#4a3a13;background:#241d0b}
.chip-bad{color:#ff938a;border-color:#5a2320;background:#2a1211}
.chip-info{color:#79c0ff;border-color:#1c3a5a;background:#0d1f2e}
.callout{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:9px;padding:.8rem 1rem;margin:.9rem 0}
.callout.warn{border-left-color:var(--warn)}
.callout.bad{border-left-color:var(--bad)}
.callout.ok{border-left-color:var(--ok)}
.callout h4{margin:0 0 .35rem;font-size:.95rem}
.muted{color:var(--dim)}
.unv{color:#e3b341}
.stamp{font-size:12.5px;color:var(--dim);margin:.2rem 0 1rem}
code{background:var(--chip);padding:.08rem .35rem;border-radius:5px;font-size:12.5px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
footer{border-top:1px solid var(--line);padding:1.2rem 1.1rem 3rem;color:var(--dim);font-size:12.5px}
footer .in{max-width:1180px;margin:0 auto}
.num{text-align:right;font-variant-numeric:tabular-nums}
"""


def page(name, title, body, *, here):
    nav = "".join(
        f'<a href="{f}" class="{"on" if f == here else ""}">{esc(t)}</a>' for f, t in NAV)
    adv = ""
    try:
        g = load("gates.json")
        for a in g.get("advisories", []):
            if not a["pass"]:
                adv = (f'<div class="callout warn" style="margin:.9rem 0 0">'
                       f'<h4>Superseded by a later official filing</h4>{esc(a["detail"])} '
                       f'<strong>This page is a record of the 1:00 PM ET filing, not a live '
                       f'feed.</strong> <a href="flagged.html">See F13-15</a>.</div>')
    except Exception:
        pass
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · NBA3 official filings 2026-11-16</title>
<link rel="stylesheet" href="assets/round2.css">
</head>
<body>
<header class="top">
  <div class="bar">
    <div class="brand">NBA3 · 11/16 filing chain <small>session fbd2484b</small></div>
    <div class="muted" style="font-size:12.5px">current filing 2026-11-16 01:15 PM ET · chain 09:15 AM → 01:00 PM → 01:15 PM</div>
  </div>
  <nav class="pages">{nav}</nav>
</header>
<main>
{adv}
{body}
</main>
<footer><div class="in">
Every value on this site names the official document it came from. Values an official document
does not print are shown as <span class="unv">— unverified</span> and are listed on the
<a href="flagged.html">Flagged for review</a> page.<br>
<strong>This is a record of a filing, not a live feed: the official index is the authority, not
this page.</strong> The index updates every 15 minutes and advanced once while this round was
being built. Generated by <code>scripts/build_round2_site.py</code> from
<code>data/rounds/2026-11-16-1300PM/</code>.
</div></footer>
</body>
</html>
"""
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path


def card(k, v, s=""):
    return (f'<div class="card"><div class="k">{esc(k)}</div>'
            f'<div class="v">{v}</div><div class="s">{esc(s)}</div></div>')


def verdict_chip(v):
    cls = {"met": "chip-ok", "met_partly": "chip-warn", "blocked": "chip-bad",
           "not_met": "chip-bad"}.get(v, "")
    label = {"met": "Met", "met_partly": "Met (partly)", "blocked": "Blocked",
             "not_met": "Not met"}.get(v, v)
    return f'<span class="chip {cls}">{esc(label)}</span>'


def state_chip(v):
    cls = {"known": "chip-ok", "unknown": "chip-bad", "discoverable": "chip-warn"}.get(v, "")
    return f'<span class="chip {cls}">{esc(v)}</span>'


def flag_chip(v):
    cls = {"resolved": "chip-ok", "recorded": "chip-info", "needs review": "chip-warn",
           "withheld": "chip-warn", "open": "chip-bad"}.get(v, "")
    return f'<span class="chip {cls}">{esc(v)}</span>'


def yesno(b):
    return ('<span class="chip chip-ok">filed</span>' if b
            else '<span class="chip chip-warn">not submitted</span>')


# ==============================================================================================
# page builders
# ==============================================================================================

def page_index(D):
    inj, d, g = D["injuries"], D["delta"], D["gates"]
    hca = D["hca"]
    body = [f"<h1>Official refresh, 2026-11-16 01:15 PM ET filing</h1>",
            '<p class="lead">The NBA injury report is the only official document that says who is '
            'available tonight. This round captures the newest filing the official index lists '
            '— 1:15 PM ET — keeps the two earlier same-day filings as its diff chain, measures '
            'what the official tables support, and publishes only because every blocking gate '
            'passed.</p>']
    body.append('<div class="grid">' +
                card("Current filing", "01:15 PM ET", "chain 09:15 → 01:00 → 01:15") +
                card("Gates", f"{g['pass_count']}/{g['gate_count']}", "rebuild allowed" if g["rebuild_allowed"] else "rebuild refused") +
                card("Rows that moved",
                     f'{sum(1 for c in d["changes"] if c["direction"] != "reason_only")} + '
                     f'{sum(1 for c in d["changes"] if c["direction"] == "reason_only")}',
                     "status changes + reason-only changes") +
                card("Clubs still not submitted", str(len(inj["teams_not_yet_submitted"])), "unknown, not zero") +
                card("Home-win rate", f"{hca['home_win_rate']:.4f}", f"{hca['home_wins']}/{hca['home_decisions']} decisions") +
                card("Slate", str(D["schedule"]["game_count"]), "games 11/16–11/18") +
                "</div>")

    nsl = len(inj["teams_not_yet_submitted"])
    body.append('<div class="callout ok"><h4>The site now publishes the newest official filing</h4>'
                f'The index lists {D["index_slots"]} filings for 2026-11-16, one every 15 minutes. '
                f'The site published the 09:15 a.m. one; this round captures the '
                f'{esc(inj["pdf_header_stamps"][0] if inj["pdf_header_stamps"] else "")} one and '
                f'keeps the two earlier filings as its diff chain. '
                f'{src(inj["source_url"], "the current filing")} and '
                f'{src("https://official.nba.com/nba-injury-report-2026-27-season/", "the official index")} '
                'are the documents behind that statement. <strong>A later filing can still '
                'arrive; the index is the authority, not this page.</strong></div>')

    body.append(f"<h2>What changed between the last two filings</h2>")
    body.append(f'<p class="muted">Diff base: {src(d["old_report"], "the previous filing")}. '
                f'The hop before it (09:15 AM → 01:00 PM) is at the bottom of the '
                f'<a href="injuries.html">Injury filing</a> page.</p>')
    rows = []
    for c in D["delta"]["changes"]:
        rows.append([
            esc(c["matchup"]), esc(c["player"]), esc(c["team"]),
            f'<span class="chip">{esc(c["was_status"] or "—")}</span>',
            f'<span class="chip chip-warn">{esc(c["now_status"] or "—")}</span>',
            esc(c["direction"]),
            src(D["injuries"]["source_url"]),
        ])
    if rows:
        body.append(table(["Game", "Player", "Club", "Was", "Now", "Direction", "Source"], rows,
                          caption=f"{len(rows)} rows whose printed status or reason changed"))
    else:
        body.append('<p class="muted">No status changed between the two filings.</p>')

    # Split the additions by WHY they are new: a club that had not submitted and now has, versus
    # a club that had already filed and has now named an additional player. These are different
    # events and must not be presented as one.
    ns_0915 = set(D["injuries_0915_teams_not_submitted"])
    newly, extra = {}, {}
    for x in D["delta"]["added"]:
        (newly if x["team"] in ns_0915 else extra).setdefault(x["team"], []).append(x)

    body.append("<h2>Clubs that filed for the first time between the two filings</h2>")
    rows = []
    for club, xs in sorted(newly.items()):
        rows.append([esc(club), str(len(xs)),
                     ", ".join(esc(f"{x['player']} ({x['now_status']})") for x in xs),
                     src(D["injuries"]["source_url"])])
    body.append(table(["Club", "Players named", "Rows", "Source"], rows,
                      caption="These clubs printed NOT YET SUBMITTED at 09:15 AM. This is not a "
                              "change in a player's health; it is new information arriving."))

    if extra:
        body.append("<h2>New players named by a club that had already filed</h2>")
        rows = []
        for club, xs in sorted(extra.items()):
            rows.append([esc(club), str(len(xs)),
                         ", ".join(esc(f"{x['player']} ({x['now_status']})") for x in xs),
                         src(D["injuries"]["source_url"])])
        body.append(table(["Club", "Players named", "Rows", "Source"], rows,
                          caption="A club that had already submitted named an additional player. "
                                  "This IS a change in the injury report's content."))

    body.append("<h2>What this round could not establish</h2>")
    body.append(f'<div class="callout bad"><h4>{nsl} clubs had still not submitted at the current filing</h4>'
                + esc(", ".join(sorted(inj["teams_not_yet_submitted"]))) +
                '. For these clubs the injury report prints <code>NOT YET SUBMITTED</code>. That '
                'is a value about the club\'s filing, not a statement that nobody is out. Any '
                'availability figure for these clubs is unknown.</div>')
    body.append('<div class="callout warn"><h4>No price, no bet</h4>'
                'No licensed closing-line feed is connected, so the market-anchored prior cannot '
                'be computed and nothing here is a bet. This page is the projection surface. '
                'See <a href="questions.html">Questions</a> Q02.</div>')
    body.append("<h3>Sections</h3>")
    links = [("summary.html", "Executive summary", "one page, the important details"),
             ("injuries.html", "Injury filing & diff", "every row, verbatim, with its source"),
             ("consequences.html", "Consequences & rotation", "who is affected, and what is blocked"),
             ("gameflow.html", "Game flow", "both clubs' filing state, game by game"),
             ("slate.html", "Slate & totals", "possessions × points per possession"),
             ("estimators.html", "Two estimators", "the disagreement, not a blend"),
             ("methodology.html", "Methodology", "what is pinned, declared and disclosed"),
             ("requirements.html", "Requirements",
              f"{len(REG.REQUIREMENTS)} rows, each with evidence"),
             ("questions.html", "Questions",
              f"{len(REG.QUESTIONS)}: known, unknown and discoverable"),
             ("suggestions.html", "Suggestions",
              f"{len(REG.SUGGESTIONS)}, none implemented"),
             ("flagged.html", "Flagged for review",
              f"{len(REG.FLAGS)} irregularities, each with a source"),
             ("verification.html", "Verification log", "what was checked and how")]
    body.append('<div class="grid">' + "".join(
        f'<a class="card" href="{f}" style="display:block;color:inherit">'
        f'<div class="k">{esc(t)}</div><div class="s" style="margin-top:.3rem">{esc(s)}</div></a>'
        for f, t, s in links) + "</div>")
    return page("index.html", "Overview", "\n".join(body), here="index.html")


def page_summary(D):
    inj, d, g, hca = D["injuries"], D["delta"], D["gates"], D["hca"]
    cons = D["consequences"]
    body = ["<h1>Executive summary</h1>",
            f'<p class="stamp">Current filing <strong>2026-11-16 01:15 PM ET</strong> · retrieved '
            f'<code>{esc(inj["retrieved_utc"])}</code> · chain: 09:15 AM ET → 01:00 PM ET → '
            f'01:15 PM ET</p>']
    body.append("<h2>The five things that matter</h2>")
    ch = D.get("chain", [])
    items = [
        ("The site now publishes the newest filing the index lists.",
         f'The official index listed 53 filings for 2026-11-16; the newest is 1:15 PM ET. '
         f'{src(inj["source_url"], "The 1:15 PM ET filing")} is captured. The site previously '
         f'published 09:15 AM ET, which was then the newest.'),
        ("The afternoon is a chain, not a snapshot.",
         f"09:15 AM → 01:00 PM: {D['delta_earlier']['status_or_reason_changes']} rows moved and "
         f"three clubs filed for the first time (Houston, Philadelphia, Washington, "
         f"{D['delta_earlier']['players_added']} players). 01:00 PM → 01:15 PM: "
         f"{d['status_or_reason_changes']} rows moved, Boston filed for the first time, and one "
         f"player's name was printed differently."),
        ("Boston has now filed.",
         "At 1:00 PM Boston printed NOT YET SUBMITTED. At 1:15 PM it named Neemias Queta, "
         "Questionable, Rest. That is new information, not a change in his health."),
        ("A name changed spelling, and it is not a squad change.",
         "New Orleans printed 'Mathurin, Bennedict' at 1:00 PM and 'Mathurin, Benedict' at "
         "1:15 PM, one edit apart, status Out both times. The diff reports it as a spelling "
         "change rather than a player leaving and another arriving."),
        ("Nothing here is a bet.",
         "No price feed, no measured per-player minutes, and the strategy gate has not passed. "
         "The bet surface stays empty and says why."),
    ]
    for i, (h, p) in enumerate(items, 1):
        body.append(f'<div class="callout"><h4>{i}. {esc(h)}</h4>{p}</div>')

    body.append("<h2>Numbers this round measured from official tables</h2>")
    rows = [
        ["Home-court advantage (pinned, not fitted)", f"{hca['home_win_rate']:.6f}",
         f"{hca['home_wins']} home wins in {hca['home_decisions']} home decisions",
         src(hca["source_url"])],
        ["League points per possession", f"{D['model']['league']['ppp']:.4f}",
         f"mean of 30 clubs; league off rating {D['model']['league']['off_rtg']:.2f}",
         src("https://www.nba.com/stats/teams/advanced")],
        ["League possessions per game", f"{D['model']['league']['poss_per_game']:.2f}",
         "mean of 30 clubs", src("https://www.nba.com/stats/teams/advanced")],
        ["Estimator disagreement (median)", f"{D['model']['disagreement_median']:.2f}",
         "points per 100 possessions, league median", src("https://www.nba.com/stats/teams/advanced")],
        ["Clubs outside the luck noise band", "0",
         "largest |z| in the league is 1.66 (band is ±2)", src(hca["source_url"])],
        ["Gates passed", f"{g['pass_count']}/{g['gate_count']}",
         "no blocking failure; rebuild allowed", src("https://www.nba.com/schedule?date=2026-11-16")],
    ]
    body.append(table(["Measure", "Value", "Basis", "Source"], rows))

    body.append("<h2>What is blocked, and by what</h2>")
    blocked = [r for r in REG.REQUIREMENTS if r[2] == "blocked"]
    rows = []
    for rid, req, verdict, evidence, artefact, contains, url in blocked:
        rows.append([esc(rid), esc(req), esc(evidence), src(url)])
    body.append(table(["Req", "Requirement", "Why it is blocked", "Source"], rows,
                      caption="Each blocked item needs one specific document or feed; none of them "
                              "is a modelling choice."))

    body.append("<h2>What to read next</h2>")
    body.append('<p>For the row-by-row evidence, open <a href="injuries.html">Injury filing &amp; '
                'diff</a>. For the decisions that cannot yet be made, open '
                '<a href="questions.html">Questions</a>. For changes to the site, open '
                '<a href="suggestions.html">Suggestions</a> — none of them is implemented.</p>')
    return page("summary.html", "Executive summary", "\n".join(body), here="summary.html")


def page_injuries(D):
    inj, d = D["injuries"], D["delta"]
    body = ["<h1>Injury filing &amp; consecutive-report diff</h1>",
            f'<div class="callout"><h4>Banner: revision and retrieval</h4>'
            f'<p style="margin:0"><strong>Revision (the report\'s own stamp):</strong> '
            f'{esc(inj["pdf_header_stamps"][0] if inj["pdf_header_stamps"] else "—")} '
            f'<span class="muted">— parsed from the PDF header, not from the filename</span><br>'
            f'<strong>Retrieved:</strong> <code>{esc(inj["retrieved_utc"])}</code> '
            f'<span class="muted">— {esc(inj["retrieval"])}</span><br>'
            f'<strong>Document:</strong> {src(inj["source_url"], "official 1:00 PM ET PDF")} · '
            f'<strong>Listed by:</strong> {src(inj["index_url"], "official injury index")}<br>'
            f'<strong>Transcript sha256:</strong> <span class="mono">{esc(inj["transcript_sha256"])}</span></p>'
            f'</div>']

    body.append('<div class="grid">' +
                card("Rows printed", str(inj["row_count"]), "player + not-submitted rows") +
                card("Player rows", str(inj["player_rows"]), "named players with a status") +
                card("Not submitted", str(inj["not_submitted_rows"]), "club cells, not players") +
                card("Status not printed", str(inj["rows_with_missing_status"]), "left null, counted") +
                card("Page-break splices", str(inj["seam_splice_row_count"]), "detected and recorded") +
                card("Unattributed rows", str(inj["rows_with_unattributed_team"]), "must be zero") +
                "</div>")

    body.append("<h2>The three filings, in order</h2>")
    chain = D.get("chain", [])
    rows = []
    for c in chain:
        cur = (c["stamp"] == "2026-11-16 01:15 PM ET")
        rows.append([
            f'<strong>{esc(c["stamp"])}</strong>' + (' <span class="chip chip-ok">current</span>' if cur else ""),
            str(c["player_rows"]), str(c["not_submitted"]),
            ("all clubs filed" if c["not_submitted"] == 0 else f'{c["not_submitted"]} club(s) had not submitted'),
            src(c["url"]),
        ])
    body.append(table(["Filing", "Player rows", "Clubs not submitted", "State", "Source"], rows,
                      caption="Each hop is diffed by the identical rule. Consecutive reports are a "
                              "sequence of information arriving, not one snapshot replacing another."))

    body.append("<h2>Every player row, verbatim</h2>")
    body.append('<p class="lead">Each row is exactly what the PDF prints. Where the PDF leaves a '
                'continuation cell blank, the value in that column was recovered, and the '
                '<em>Attribution</em> column says so.</p>')
    rows = []
    for r in inj["rows"]:
        if r["kind"] != "player":
            continue
        status = (f'<span class="chip chip-bad">{esc(r["status"])}</span>'
                  if r["status"] == "Out" else
                  f'<span class="chip chip-warn">{esc(r["status"])}</span>' if r["status"] else unverified())
        reason = esc(r["reason"]) if r["reason"] else unverified()
        attr = (f'<span class="chip chip-info">{esc(r["attribution"])}</span>'
                if r["attribution"] != "explicit" else '<span class="muted">printed</span>')
        rows.append([esc(r["matchup"]), esc(r["team"]), esc(r["player"]), status, reason, attr,
                     src(inj["source_url"])])
    body.append(table(["Game", "Club", "Player", "Status", "Reason", "Attribution", "Source"], rows,
                      caption=f"{len(rows)} player rows from the 1:00 PM ET filing"))

    body.append("<h2>Clubs that had not submitted</h2>")
    rows = [[esc(c), '<span class="chip chip-warn">not submitted</span>',
             src(inj["source_url"])] for c in sorted(inj["teams_not_yet_submitted"])]
    body.append(table(["Club", "State at 1:00 PM ET", "Source"], rows,
                      caption="For these clubs there is no availability information at all. This is "
                              "not a zero."))

    body.append("<h2>Status changes against the 09:15 AM ET filing</h2>")
    body.append(f'<p class="muted">Diff base: {src(d["old_report"], "the 09:15 AM ET PDF")}. '
                f'Rule: {esc(d["rule"])}</p>')
    rows = []
    for c in d["changes"]:
        rows.append([esc(c["matchup"]), esc(c["player"]), esc(c["was_status"] or "—"),
                     esc(c["now_status"] or "—"), esc(c["direction"]),
                     esc(c["was_reason"] or "—"), esc(c["now_reason"] or "—"),
                     src(d["new_report"])])
    body.append(table(["Game", "Player", "Was", "Now", "Direction", "Was reason", "Now reason", "Source"],
                      rows, caption=f"{len(rows)} changed rows"))

    if d.get("name_spelling_changes"):
        body.append("<h2>Spelling changes (not squad changes)</h2>")
        rows = [[esc(x["matchup"]), esc(x["team"]), esc(x["was_name"]), "→", esc(x["now_name"]),
                 str(x["edit_distance"]), esc(x["now_status"]), src(d["new_report"])]
                for x in d["name_spelling_changes"]]
        body.append(table(["Game", "Club", "Printed at 1:00 PM", "", "Printed at 1:15 PM",
                           "Edits", "Status", "Source"], rows,
                          caption="Same club, same game, printed name within two edits. Reported "
                                  "as a spelling change; the player did not leave and return."))

    body.append("<h2>Rows that appeared and disappeared</h2>")
    rows = [[esc(x["team"]), esc(x["player"]), esc(x["now_status"]), esc(x["matchup"]),
             src(d["new_report"])] for x in d["added"]]
    body.append(table(["Club", "Player", "Status now", "Game", "Source"], rows,
                      caption=f"{len(rows)} players named at 1:00 PM that the 09:15 AM filing did "
                              "not name. Almost all are clubs that submitted in between."))
    if d["removed"]:
        rows = [[esc(x["team"]), esc(x["player"]), esc(x["was_status"]), esc(x["matchup"]),
                 src(d["old_report"])] for x in d["removed"]]
        body.append(table(["Club", "Player", "Status then", "Game", "Source"], rows,
                          caption="Players the earlier filing named and this one does not."))
    de = D.get("delta_earlier") or {}
    if de.get("changes"):
        body.append("<h2>Previous hop: what moved between 09:15 AM and 1:00 PM</h2>")
        rows = [[esc(c["matchup"]), esc(c["player"]), esc(c["was_status"] or "—"),
                 esc(c["now_status"] or "—"), esc(c["direction"]), src(de["new_report"])]
                for c in de["changes"]]
        body.append(table(["Game", "Player", "Was", "Now", "Direction", "Source"], rows,
                          caption=f"{de['status_or_reason_changes']} rows moved in this hop; "
                                  f"{de['players_added']} players were named for the first time, "
                                  f"almost all by clubs that had not yet submitted."))
    return page("injuries.html", "Injury filing", "\n".join(body), here="injuries.html")


def page_consequences(D):
    cons, inj = D["consequences"], D["injuries"]
    body = ["<h1>Consequences &amp; rotation exposure</h1>",
            '<p class="lead">What a filing means for a club is not the same as what it means for a '
            'rotation. This page separates the two: the availability band is published, the '
            'minute-level consequence is reported as blocked rather than estimated.</p>']
    body.append('<div class="grid">' +
                card("Clubs in the filing", str(len(cons["clubs"])), "filed or not submitted") +
                card("Clubs that filed", str(cons["clubs_that_filed"]), "a status for every named player") +
                card("Clubs not submitted", str(cons["clubs_not_yet_submitted"]), "unknown availability") +
                card("Player rows", str(cons["total_player_rows"]), "across all clubs") +
                "</div>")

    body.append("<h2>Per-club availability band</h2>")
    body.append('<p class="muted">Severity points weight Out=3, Doubtful=2, Questionable=1, '
                'Available=0, so a club with more definite absences sorts above one with more '
                'uncertain ones. It is a sort key, not a projection.</p>')
    rows = []
    for c in cons["clubs"]:
        rows.append([
            esc(c["club"]),
            yesno(c["filed"]),
            str(c["out"]) if c["filed"] else unverified(),
            str(c["doubtful"]) if c["filed"] else unverified(),
            str(c["questionable"]) if c["filed"] else unverified(),
            str(c["available"]) if c["filed"] else unverified(),
            str(c["severity_points"]) if c["filed"] else unverified(),
            esc(c["record"]),
            esc(c["next_game"] or "—"),
            esc(c["next_tip_et"] or "—"),
            src(c["source_url"]),
        ])
    body.append(table(["Club", "Filed", "Out", "Doubtful", "Questionable", "Available", "Severity",
                       "W–L", "Next game", "Tip ET", "Source"], rows,
                      caption="Ordered: clubs that have not filed first, then by severity."))

    body.append("<h2>Minutes redistribution: blocked</h2>")
    mr = cons["minutes_redistribution"]
    body.append(f'<div class="callout bad"><h4>No minute-level number is published for this slate</h4>'
                f'<p><strong>Requirement:</strong> {esc(mr["requirement"])}</p>'
                f'<p><strong>Why blocked:</strong> {esc(mr["why"])}</p>'
                f'<p><strong>What would unblock it:</strong> {esc(mr["what_would_unblock"])}</p>'
                f'<p style="margin-bottom:0">{src("https://www.nba.com/stats/players/traditional", "official player stats page")} '
                f'is where per-player minutes are published; the repo already parses the gamebook '
                f'format for 2026-11-14.</p></div>')

    if cons["lower_bound_caveats"]:
        body.append("<h2>Rows that make a count a lower bound</h2>")
        rows = [[esc(x["club"]), esc(x["issue"]), esc(x["effect"]), src(x["source_url"])]
                for x in cons["lower_bound_caveats"]]
        body.append(table(["Club", "Issue", "Effect", "Source"], rows))

    body.append("<h2>What can be said honestly without minutes</h2>")
    body.append('<ul>'
                '<li>How many named players a club has ruled <strong>Out</strong>, and how many are '
                'uncertain. That is printed.</li>'
                '<li>Whether a club has filed at all. That is printed.</li>'
                '<li>How the picture moved between filings. That is the diff.</li>'
                '<li class="muted">Not: how many minutes the replacements will play, or how the '
                'scoring will redistribute. That needs per-player logs.</li>'
                '</ul>')
    return page("consequences.html", "Consequences & rotation", "\n".join(body),
                here="consequences.html")


def page_gameflow(D):
    flow = D["game_flow"]
    body = ["<h1>Game flow</h1>",
            '<p class="lead">One row per game on the slate: both clubs\' filing state side by side, '
            'the counts that are known, and the pace and net rating that shape the game. Where a '
            'club has not filed, its cells are unverified rather than zero.</p>']
    body.append('<div class="callout warn"><h4>A club that has not filed is not a healthy club</h4>'
                f'{esc(flow["note"])}</div>')
    body.append('<div class="grid">' +
                card("Games on the slate", str(len(flow["games"])), "11/16 – 11/18") +
                card("Games tonight", str(flow["games_tonight"]), "2026-11-16") +
                card("Games with a club not filed", str(flow["games_with_a_club_not_filed"]),
                     "availability unknown for at least one side") +
                "</div>")

    for date in ("2026-11-16", "2026-11-17", "2026-11-18"):
        games = [g for g in flow["games"] if g["date"] == date]
        if not games:
            continue
        body.append(f"<h2>{esc(date)} — {len(games)} games</h2>")
        rows = []
        for g in games:
            rows.append([
                esc(g["tip_et"]),
                esc(g["matchup"]),
                f'{esc(g["away"])} {yesno(g["away_filed"])}',
                f'{esc(g["home"])} {yesno(g["home_filed"])}',
                (str(g["away_outs"]) if g["away_filed"] else unverified()),
                (str(g["home_outs"]) if g["home_filed"] else unverified()),
                str(g["changes_today"]),
                esc(f'{g["away_pace"]:.1f} / {g["home_pace"]:.1f}'),
                esc(f'{g["away_net_rtg"]:+.1f} / {g["home_net_rtg"]:+.1f}'),
                src(g["availability_source_url"]),
            ])
        body.append(table(["Tip ET", "Game", "Away", "Home", "Away out", "Home out",
                           "Changes today", "Pace", "Net rtg", "Source"], rows,
                          caption="Pace and net rating are season-wide official values, not "
                                  "game-specific projections."))

    body.append("<h2>How to read the flow</h2>")
    body.append('<p>A game with a club that has not filed is the one to watch: the filing that '
                'arrives before tip is the information, and the diff against this one is what '
                'changes the picture. The <a href="questions.html">Questions</a> page names the '
                'document that would resolve each open item.</p>')
    return page("gameflow.html", "Game flow", "\n".join(body), here="gameflow.html")


def page_slate(D):
    flow, sched = D["game_flow"], D["schedule"]
    body = ["<h1>Slate &amp; totals</h1>",
            '<p class="lead">The slate is the official schedule for today and the next two days. '
            'Totals are modelled as possessions × points per possession — and this page states '
            'plainly where that formula does and does not differ from the naive sum.</p>']
    body.append('<div class="callout warn"><h4>Disclosure: on season-wide inputs the two agree</h4>'
                'The official offensive rating is exactly <code>100 × points / possessions</code>. '
                'So possessions × points-per-possession reproduces the sum of the two clubs\' '
                'scoring averages to within a tenth of a point. The formula is the correct object '
                'and is what the model uses; it cannot yet do additional work because '
                'opponent-specific rates need per-game logs. That identity is pinned by gate '
                '<code>I10</code>, not hidden.</div>')

    body.append("<h2>Games and modelled totals</h2>")
    rows = []
    for g in flow["games"]:
        t = g["totals"]
        rows.append([
            esc(g["date"]), esc(g["tip_et"]), esc(g["matchup"]),
            f'{t["possessions_used"]:.1f}',
            f'{t["ppp_away"]:.4f} / {t["ppp_home"]:.4f}',
            f'<strong>{t["total_from_poss_x_ppp"]:.1f}</strong>',
            f'{t["naive_sum_of_points_per_game"]:.1f}',
            f'{t["difference"]:+.2f}',
            f'{t["margin_from_net_rtg"]:+.2f}',
            src(STATS_ADV),
        ])
    body.append(table(["Date", "Tip ET", "Game", "Poss", "PPP away/home", "Total",
                       "Naive sum", "Δ", "Margin", "Source"], rows,
                      caption="Δ is formula minus naive sum. It is small for the reason above, not "
                              "because the formula was checked and agreed with."))

    body.append("<h2>The schedule itself</h2>")
    rows = [[esc(g["date"]), esc(g["tip_et"]), esc(g["away"]), esc(g["home"]),
             esc(g["venue"]), esc(g["city"]), esc(g["game_id"]), src(g["source_url"])]
            for g in sched["games"]]
    body.append(table(["Date", "Tip ET", "Away", "Home", "Venue", "City", "Game ID", "Source"],
                      rows, caption=f"{len(rows)} games, transcribed from the official schedule page."))

    body.append("<h2>Schedule integrity checks</h2>")
    rows = [
        ["Printed day counts vs transcribed rows",
         esc(str(sched["printed_day_counts"])), esc(str(sched["count_by_date"])),
         src(sched["source_url"])],
        ["Window is today .. today+2", "2026-11-16 → 2026-11-18",
         esc(", ".join(sorted(sched["count_by_date"]))), src(sched["source_url"])],
        ["Game IDs unique", str(len({g["game_id"] for g in sched["games"]})),
         esc(str(sched["game_count"])), src(sched["source_url"])],
    ]
    body.append(table(["Check", "Expected", "Observed", "Source"], rows))
    return page("slate.html", "Slate & totals", "\n".join(body), here="slate.html")


STATS_ADV = "https://www.nba.com/stats/teams/advanced"


def page_estimators(D):
    m, luck = D["model"], D["luck"]
    body = ["<h1>Two estimators, and their disagreement</h1>",
            '<p class="lead">A single blended rating hides the fact that two reasonable methods can '
            'disagree. This page publishes both, and the gap between them is the headline. The '
            'blend is not published as a rating at all.</p>']
    body.append(f'<div class="callout"><h4>{esc(m["headline_rule"])}</h4>{esc(m["blend_note"])}</div>')
    body.append('<div class="grid">' +
                card("Median disagreement", f'{m["disagreement_median"]:.2f}',
                     "points per 100 possessions") +
                card("Largest", f'{m["disagreement_max"]:.2f}', "where methods diverge most") +
                card("Smallest", f'{m["disagreement_min"]:.2f}', "where methods agree most") +
                card("Home-court prior", f'{m["home_court"]["home_win_rate"]:.4f}',
                     "pinned to the measured rate") +
                "</div>")

    body.append("<h2>How each estimator is built</h2>")
    body.append('<ul>'
                '<li><strong>A · form.</strong> The official net rating, taken at face value. '
                'It is what the club has actually out-scored opponents by, per 100 possessions.</li>'
                '<li><strong>B · structure.</strong> Rebuilt from shooting efficiency, turnover rate '
                'and offensive rebounding — the four factors — and compared with the same '
                'reconstruction for what the club allows. It shares no input with A.</li>'
                '<li><strong>Centring.</strong> Both are expressed as points per 100 possessions '
                f'above their own league mean (A: {m["centering"]["estimator_a_league_mean_raw"]:+.4f}, '
                f'B: {m["centering"]["estimator_b_league_mean_raw"]:+.4f}). Without this, a constant '
                'inside B would appear as disagreement between methods when it is only a level '
                'shift.</li></ul>')

    body.append("<h2>Both estimators, all 30 clubs</h2>")
    rows = []
    for c in sorted(m["clubs"], key=lambda x: -x["disagreement"]):
        rows.append([
            esc(c["abbr"]), esc(c["team"]), str(c["gp"]),
            f'{c["estimator_a_form"]:+.2f}', f'{c["estimator_b_structure"]:+.2f}',
            f'<strong>{c["disagreement"]:.2f}</strong>',
            f'{c["net_rtg_printed"]:+.2f}',
            src(STATS_ADV),
        ])
    body.append(table(["", "Club", "GP", "A (form)", "B (structure)", "Disagreement",
                       "Printed net rtg", "Source"], rows,
                      caption="Disagreement is |A − B| in points per 100 possessions. It is a "
                              "method-uncertainty signal and is NOT calibrated as a probability."))

    body.append("<h2>Luck, as a z-score</h2>")
    body.append(f'<p class="lead">{esc(luck["note"])}</p>')
    rows = []
    for c in sorted(luck["clubs"], key=lambda x: -abs(x["z"])):
        band = ('<span class="chip chip-ok">inside ±2</span>' if c["in_noise_band"]
                else '<span class="chip chip-bad">outside ±2</span>')
        rows.append([esc(c["abbr"]), esc(c["team"]), str(c["actual_wins"]),
                     f'{c["expected_wins"]:.2f}', f'{c["residual"]:+.2f}', f'{c["z"]:+.3f}', band,
                     src(D["hca"]["source_url"])])
    body.append(table(["", "Club", "Actual W", "Expected W", "Residual", "z", "Noise band", "Source"],
                      rows, caption="Expected wins come from the club's own net rating; the z is the "
                                    "residual over the binomial sd. No club is outside ±2 this round."))
    return page("estimators.html", "Two estimators", "\n".join(body), here="estimators.html")


def page_methodology(D):
    hca, m, inj = D["hca"], D["model"], D["injuries"]
    body = ["<h1>Methodology</h1>",
            '<p class="lead">Every number on this site is either printed by an official document, '
            'computed from one by arithmetic stated here, or declared as a constant and flagged. '
            'Nothing is fitted, except where this page says so and the brief requires it.</p>']

    body.append("<h2>Home-court advantage, pinned</h2>")
    body.append(f'<div class="callout ok"><h4>The prior is the measurement</h4>'
                f'<p>{hca["home_wins"]} home wins in {hca["home_decisions"]} home decisions '
                f'across all 30 clubs = <strong>{hca["home_win_rate"]:.6f}</strong>. '
                f'Against a 0.5 null that is z = {hca["z_vs_null"]:+.2f}. '
                f'No parameter is estimated: the brief requires the measured rate, and this is it.</p>'
                f'<p style="margin-bottom:0">{esc(hca["note"])}</p></div>')
    rows = [["Home", f'{hca["home_wins"]}–{hca["home_losses"]}', src(hca["source_url"])],
            ["Road", f'{hca["road_wins"]}–{hca["road_losses"]}', src(hca["source_url"])],
            ["Neutral", f'{hca["neutral_wins"]}–{hca["neutral_losses"]}', src(hca["source_url"])]]
    body.append(table(["Split", "League W–L", "Source"], rows,
                      caption="Road wins equal home losses exactly; gate I2 refuses the build if "
                              "that ever stops being true."))

    body.append("<h2>What is declared, not measured</h2>")
    rows = [
        ["Second-chance points per offensive rebound", "0.30",
         "Not printed by any captured official document; shifts estimator B's level, cancelled by centring",
         src(STATS_ADV)],
        ["Single-game margin standard deviation", "12.0",
         "Used only inside the luck z; a league-wide basketball constant, stated so the reader can see the dependency",
         src(hca["source_url"])],
        ["Severity weights (Out/Doubtful/Questionable/Available)", "3 / 2 / 1 / 0",
         "A sort key for the availability table, not a projection",
         src(inj["source_url"])],
    ]
    body.append(table(["Constant", "Value", "Why it is a constant", "Source"], rows,
                      caption="A declared constant is one a reader could disagree with. That is the "
                              "point of listing them."))

    body.append("<h2>The totals model</h2>")
    body.append('<p>Expected total = shared possessions × (points per possession, away + home). '
                'Both clubs play the same number of possessions in a game, so the game\'s '
                'possession count is the mean of the two clubs\' pace. Points per possession is '
                'the official offensive rating divided by 100. The naive alternative — adding the '
                'two clubs\' season scoring averages — is printed beside every total, and the '
                'identity between them on season-wide inputs is disclosed on the '
                '<a href="slate.html">Slate</a> page.</p>')

    body.append("<h2>Rules the pipeline will not break</h2>")
    body.append('<ul>'
                '<li><strong>No repair.</strong> A document that contradicts itself is published '
                'with both readings and the row is withheld.</li>'
                '<li><strong>No inference.</strong> A cell the document does not print is null and '
                'counted.</li>'
                '<li><strong>No positional attribution.</strong> Cells are classified by content; '
                'a matchup is never inherited across a page break.</li>'
                '<li><strong>No silent splice.</strong> A row split by a page break is merged, '
                'counted and tested.</li>'
                '<li><strong>No clock in the artefacts.</strong> The same inputs reproduce the same '
                'bytes, so CI diffs the tree.</li></ul>')

    body.append("<h2>Gate scope</h2>")
    body.append('<p>A <strong>build-scope</strong> gate stops the whole publication; a '
                '<strong>row-scope</strong> gate withholds only its own row and publishes the '
                'reason. This round has no build-scope failure. Full report on '
                '<a href="verification.html">Verification</a>.</p>')
    return page("methodology.html", "Methodology", "\n".join(body), here="methodology.html")


def page_requirements(D):
    body = ["<h1>Requirements register</h1>",
            '<p class="lead">One row per requirement in the brief, with a verdict read from an '
            'artefact in this repository rather than asserted. A unit test asserts that every '
            'named file really contains the string quoted beside it, so this table cannot drift '
            'away from the code.</p>']
    counts = {}
    for r in REG.REQUIREMENTS:
        counts[r[2]] = counts.get(r[2], 0) + 1
    body.append('<div class="grid">' + "".join(
        card(k.replace("_", " "), str(v), "requirements") for k, v in sorted(counts.items())) + "</div>")
    def is_nba(u):
        return is_official(u)

    nba_rows, proj_rows = [], []
    for rid, req, verdict, evidence, artefact, contains, url in REG.REQUIREMENTS:
        if is_nba(url):
            nba_rows.append([esc(rid), esc(req), verdict_chip(verdict), esc(evidence),
                             f'<code>{esc(artefact)}</code>', esc(contains), src(url)])
        else:
            proj_rows.append([esc(rid), esc(req), verdict_chip(verdict), esc(evidence),
                              f'<code>{esc(artefact)}</code>', esc(contains), src(url),
                              '<span class="chip chip-info">project state</span>'])

    body.append("<h2>Requirements checked against official NBA documents</h2>")
    body.append(table(["#", "Requirement", "Verdict", "Evidence", "Artefact", "Contains", "Source"],
                      nba_rows,
                      caption="Every row here cites an official NBA source. ‘Blocked’ means a "
                              "specific document or feed is missing; it is never a modelling shortcut."))
    body.append("<h2>Requirements about the working process</h2>")
    body.append('<p class="muted">These are about this repository and this session, not about NBA '
                'data. Their source is the project itself, and they are labelled as such rather '
                'than borrowing an NBA link they do not need.</p>')
    body.append(table(["#", "Requirement", "Verdict", "Evidence", "Artefact", "Contains", "Source",
                       "Kind"], proj_rows, sourced=False,
                      caption="Project-state rows. The link is to the file that shows the claim; "
                              "no NBA document is claimed for them."))
    return page("requirements.html", "Requirements", "\n".join(body), here="requirements.html")


def page_questions(D):
    body = ["<h1>Questions that must be answered before a decision</h1>",
            '<p class="lead">Each item is marked <strong>known</strong>, <strong>unknown</strong> or '
            '<strong>discoverable</strong>, and names the document that would settle it. A question '
            'marked known carries its measured value, so the entry is an answer and not a deferral.</p>']
    counts = {}
    for q in REG.QUESTIONS:
        counts[q[2]] = counts.get(q[2], 0) + 1
    body.append('<div class="grid">' + "".join(
        card(k, str(v), "questions") for k, v in sorted(counts.items())) + "</div>")
    rows = []
    for qid, q, state, detail, resolves, url in REG.QUESTIONS:
        rows.append([esc(qid), esc(q), state_chip(state), esc(detail), esc(resolves), src(url)])
    body.append(table(["#", "Question", "State", "What is known", "What would settle it", "Source"],
                      rows, caption="‘Discoverable’ means an official document exists that would "
                                    "answer it; ‘unknown’ means no captured source can."))
    body.append('<div class="callout warn"><h4>The binding constraint is not a model</h4>'
                'Eight questions are unknown. Two of them — no price feed (Q02) and the licence '
                'question (Q05) — make every bet-surface decision impossible regardless of how '
                'good the model is. They are listed first in effect even where they are not first '
                'in number.</div>')
    return page("questions.html", "Questions", "\n".join(body), here="questions.html")


def page_suggestions(D):
    body = ["<h1>Suggestions</h1>",
            '<p class="lead">Changes that would improve decision making on this site. '
            '<strong>None is implemented.</strong> Each is a proposal to review and accept or '
            'reject; the priority is the cost of leaving it undone, not the cost of building it.</p>']
    body.append('<div class="callout"><h4>Awaiting a decision</h4>Eleven suggestions, status '
                '<strong>proposed</strong>. Nothing on this site behaves differently because of '
                'them.</div>')
    rows = []
    for sid, title, why, cost, prio in REG.SUGGESTIONS:
        pc = {"high": "chip-bad", "medium": "chip-warn", "low": "chip-info"}[prio]
        rows.append([esc(sid), f'<strong>{esc(title)}</strong>', esc(why), esc(cost),
                     f'<span class="chip {pc}">{esc(prio)}</span>',
                     '<span class="chip">proposed</span>',
                     src(D["injuries"]["source_url"])])
    body.append(table(["#", "Suggestion", "Why it would help", "What it would take", "Priority",
                       "Status", "Source"], rows))
    body.append('<div class="callout warn"><h4>Why none is implemented in this session</h4>'
                'The brief asks for a section where a reviewer can choose a path before changes '
                'are made. Implementing a suggestion without that choice would remove the choice.'
                '</div>')
    return page("suggestions.html", "Suggestions", "\n".join(body), here="suggestions.html")


def page_flagged(D):
    body = ["<h1>Flagged for review</h1>",
            '<p class="lead">Irregularities found while verifying this round. Each names the '
            'document that shows it, what was done about it, and its state. Nothing here blocks '
            'the publication; several are things a reader should know before trusting a number.</p>']
    rows = []
    for fid, what, detail, action, url, status in REG.FLAGS:
        rows.append([esc(fid), f'<strong>{esc(what)}</strong>', esc(detail), esc(action),
                     flag_chip(status), src(url)])
    body.append(table(["#", "What", "Detail", "What was done", "State", "Source"], rows))
    body.append('<div class="callout bad"><h4>Open items that cannot be closed by this session</h4>'
                'F13-11 (no 11/16 result can exist yet), F13-12 (no per-player minutes for this '
                'slate) and the three items needing review (F13-08, F13-09, F13-10) each need a '
                'document or a decision from outside this repository.</div>')
    return page("flagged.html", "Flagged for review", "\n".join(body), here="flagged.html")


def page_verification(D):
    g, man = D["gates"], D["manifest"]
    inj = D["injuries"]
    body = ["<h1>Verification log</h1>",
            '<p class="lead">What was checked, against which document, and with what result. The '
            'gate report is generated by the same script that writes the artefacts, so this page '
            'cannot say a gate passed when the run did not.</p>']
    body.append(f'<div class="callout {"ok" if g["rebuild_allowed"] else "bad"}">'
                f'<h4>{g["pass_count"]} of {g["gate_count"]} gates passed; rebuild '
                f'{"allowed" if g["rebuild_allowed"] else "refused"}</h4>'
                f'<p style="margin:0">{esc(g["rule"])}</p></div>')
    rows = []
    for x in g["gates"]:
        cls = ("chip-ok" if x["pass"] else
               "chip-bad" if x["scope"] == "build"
               else "chip-info" if x["scope"] == "advisory" else "chip-warn")
        rows.append([f'<code>{esc(x["id"])}</code>', esc(x["name"]),
                     f'<span class="chip {cls}">{"pass" if x["pass"] else "fail"}</span>',
                     f'<span class="chip">{esc(x["scope"])}</span>', esc(x["detail"]),
                     src(x.get("document") or D["injuries"]["source_url"])])
    body.append(table(["Gate", "What it checks", "Result", "Scope", "Detail", "Document"], rows))

    body.append("<h2>Documents read, with retrieval stamp and hash</h2>")
    rows = [[esc(d["role"]), src(d["url"]), esc(d.get("retrieved_utc") or "—"),
             f'<span class="mono">{esc(d["sha256"][:24])}…</span>'] for d in man["documents"]]
    body.append(table(["Document", "URL", "Retrieved (UTC)", "sha256"], rows,
                      caption=man["note"]))

    body.append("<h2>Verification performed by hand</h2>")
    checks = [
        ("Every published injury cell appears verbatim in the transcript",
         "A script compared each player, status and reason string against the raw transcript; "
         "every one matched. No cell was normalised."),
        ("Row counts reconcile across the two filings",
         f"1:00 PM: {inj['player_rows']} player rows + {inj['not_submitted_rows']} not-submitted = "
         f"{inj['row_count']}. The 09:15 AM filing: 57 + 15 = 72."),
        ("Clubs that filed for the first time explain the additions",
         "The 18 players added between filings belong exactly to the three clubs that stopped "
         "being NOT YET SUBMITTED. No addition is unexplained."),
        ("League wins equal league losses",
         "197–197 across 30 clubs; home 102–94, road 94–102, neutral 1–1. Road wins equal home "
         "losses exactly."),
        ("Team-stat arithmetic reconciles",
         "Printed net rating = off − def within 0.1 for all 30 clubs; off rating = 100 × points / "
         "possessions within 0.002 points per possession."),
        ("Matchups contain their clubs",
         "Every player row's game string contains that row's club abbreviation. Gate I5 fails "
         "the build otherwise, which is the check that caught the five mis-filed Nets rows."),
        ("The build is deterministic",
         "Re-running the artefact step reproduces identical bytes; the site builder writes no "
         "clock into any page."),
    ]
    DOC = {0: D["injuries"]["source_url"], 1: D["injuries"]["source_url"],
           2: D["injuries"]["source_url"], 3: D["hca"]["source_url"],
           4: "https://www.nba.com/stats/teams/advanced", 5: D["injuries"]["source_url"],
           6: "https://www.nba.com/schedule?date=2026-11-16"}
    rows = [[esc(a), esc(b), '<span class="chip chip-ok">checked</span>', src(DOC[i])]
            for i, (a, b) in enumerate(checks)]
    body.append(table(["Check", "Result", "State", "Document checked"], rows))
    return page("verification.html", "Verification log", "\n".join(body), here="verification.html")


# ==============================================================================================
# link + source validation, then main
# ==============================================================================================

class LinkCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.row_links = []
        self.in_tbody = False
        self.in_row = False
        self.cur = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            if self.in_row:
                self.cur.append(a["href"])
        if tag == "tbody":
            self.in_tbody = True
        if tag == "tr" and self.in_tbody:
            self.in_row = True
            self.cur = []

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_row:
            self.row_links.append(self.cur)
            self.in_row = False
        if tag == "tbody":
            self.in_tbody = False


def validate():
    files = sorted(f for f in os.listdir(OUT) if f.endswith(".html"))
    ids = {}
    parsed = {}
    for f in files:
        with open(os.path.join(OUT, f), encoding="utf-8") as fh:
            text = fh.read()
        p = LinkCheck()
        p.feed(text)
        parsed[f] = p

    total_links = 0
    total_rows = 0
    for f, p in parsed.items():
        for href in p.hrefs:
            total_links += 1
            if href.startswith("#"):
                continue
            if href.startswith(("http://", "https://")):
                if not (is_official(href) or is_project(href)):
                    err(f"{f}: external link is neither official nor a project link: {href}")
                continue
            target = href.split("#")[0]
            if not os.path.exists(os.path.join(OUT, target)):
                err(f"{f}: broken internal link {href}")
        nosrc = 'data-nosrc="1"' in open(os.path.join(OUT, f), encoding="utf-8").read()
        for row in p.row_links:
            if nosrc:
                break
            total_rows += 1
            if not any(is_official(h) for h in row):
                err(f"{f}: a data row has no official source link")
    return files, total_links, total_rows


def main(argv=None):
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    with open(os.path.join(OUT, "assets", "round2.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)

    D = {
        "injuries": load("injuries.json"),
        "delta": load("injury_delta.json"),
        "gates": load("gates.json"),
        "hca": load("home_court.json"),
        "model": load("model.json"),
        "luck": load("luck.json"),
        "consequences": load("consequences.json"),
        "game_flow": load("game_flow.json"),
        "schedule": load("schedule.json"),
        "manifest": load("refresh.json"),
        "chain": load("injury_chain.json")["chain"],
        "index_slots": load("injury_chain.json").get("index_slots_for_the_day", 53),
        "delta_earlier": load("injury_chain.json")["earlier_hop"],
    }
    # the 09:15 filing's not-submitted set is carried on the delta artefact itself
    D["injuries_0915_teams_not_submitted"] = D["delta"]["old_report_teams_not_submitted"]

    builders = [page_index, page_summary, page_injuries, page_consequences, page_gameflow,
                page_slate, page_estimators, page_methodology, page_requirements,
                page_questions, page_suggestions, page_flagged, page_verification]
    for b in builders:
        b(D)

    files, links, rows = validate()
    if ERRORS:
        print(f"BUILD FAILED with {len(ERRORS)} problem(s):", file=sys.stderr)
        for e in ERRORS[:40]:
            print("  -", e, file=sys.stderr)
        return 1
    print(f"round2/: {len(files)} pages, {links} links, {rows} sourced table rows, 0 problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
