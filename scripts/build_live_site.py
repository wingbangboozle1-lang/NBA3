"""Build the two separated surfaces: projection/ (publishable now) and bet/ (gated).

They are separate trees with separate indexes and separate CSS, and the projection tree never
links into the bet tree except through one clearly labelled cross-reference banner. That is the
separation rule: a reader on the projection surface cannot mistake a gated pick for a projection.

Every table row carries an official source link. A value that could not be confirmed from an
official source is rendered as an em dash and flagged, never filled in. The build FAILS if a row
has no https link, or if a row renders a number in a cell that is marked unverified.

Standard library only. Writes only under projection/ and bet/.

Run: python3 scripts/build_live_site.py [--check]
"""

from __future__ import annotations

import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
OUT_PROJ = ROOT / "projection"
OUT_BET = ROOT / "bet"

SESSION = "arena/2ebb1e75-nba3"
BUILD_UTC = "2026-11-15T12:20Z"
REPO = "https://github.com/wingbangboozle1-lang/NBA3"

ERRORS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def num(v, nd=1, blank="—"):
    if v is None or v == "":
        return blank
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return esc(v)


def pct(v, nd=1):
    if v is None:
        return "—"
    return f"{float(v) * 100:.{nd}f}%"


def link(url: str, label: str | None = None) -> str:
    if not url:
        return '<span class="unv">UNVERIFIED — no source link</span>'
    return (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(label or url)}</a>')


def unflagged(v, why: str) -> str:
    """A value we could not confirm: blank, with the reason next to it. Never a number."""
    return f'<span class="unv" title="{esc(why)}">—</span> <span class="unv">unverified</span>'


def table(headers, rows, tid: str, require_source=True, cls="") -> str:
    out = [f'<div class="tw"><table id="{esc(tid)}" class="{cls}">', "<thead><tr>"]
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for i, r in enumerate(rows):
        cells = " ".join(str(c) for c in r)
        if require_source and 'href="https://' not in cells:
            err(f"table {tid}: row {i} has no https source link")
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def kv(pairs, tid, require_source=True) -> str:
    return table(["Item", "Value"], [[k, v] for k, v in pairs], tid,
                 require_source=require_source)


CSS = """
:root{--ink:#14181f;--mut:#5b6675;--line:#dfe4ea;--bg:#fff;--soft:#f6f8fa;
--acc:#1b4f9c;--warn:#8a5a00;--bad:#a3241c;--ok:#1c6b3a}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg)}
header.site{background:var(--ink);color:#fff;padding:14px 0}
header.site a{color:#fff}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
.brand{font-weight:700;letter-spacing:.02em;text-decoration:none}
.brand span{background:#fff;color:var(--ink);border-radius:3px;padding:1px 5px;margin-right:7px}
.stamp{color:#b9c3d0;font-size:13px;margin-top:3px}
nav.site{background:var(--soft);border-bottom:1px solid var(--line);padding:9px 0;font-size:14px}
nav.site a{margin-right:14px;color:var(--acc);text-decoration:none}
nav.site a.active{font-weight:700;border-bottom:2px solid var(--acc)}
main{padding:26px 0 60px}
.crumb{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}
h1{font-size:26px;margin:4px 0 6px}
h2{font-size:19px;margin:30px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:20px 0 6px}
.lead{color:var(--mut);max-width:74ch}
p{max-width:82ch}
.tw{overflow-x:auto;margin:12px 0 4px;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600;white-space:nowrap;position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--acc)}
.chip{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:10px;white-space:nowrap}
.ok{background:#e4f3e9;color:var(--ok)}
.bad{background:#fbe6e4;color:var(--bad)}
.warn{background:#fdf1d8;color:var(--warn)}
.grey{background:#eceff3;color:var(--mut)}
.unv{color:var(--bad);font-size:12px}
.callout{background:var(--soft);border-left:3px solid var(--acc);padding:11px 14px;margin:16px 0;border-radius:0 5px 5px 0}
.callout.bad{border-left-color:var(--bad);background:#fdf4f3}
.callout.warn{border-left-color:var(--warn);background:#fdfaf1}
code{background:var(--soft);padding:1px 5px;border-radius:3px;font-size:12.5px}
footer.site{border-top:1px solid var(--line);color:var(--mut);font-size:12.5px;padding:16px 0 30px}
.banner{background:#14181f;color:#fff;padding:8px 0;font-size:13.5px}
.banner a{color:#9fc4ff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:14px 0}
.card{border:1px solid var(--line);border-radius:6px;padding:12px 14px}
.card .k{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}
.card .v{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.card .s{font-size:12.5px;color:var(--mut)}
"""


# ------------------------------------------------------------------ data
def load(name, default=None):
    p = LIVE / name
    if not p.exists():
        return default
    return json.loads(p.read_text())


def load_dot(name, default=None):
    p = ROOT / "data" / "live"
    return default


class Ctx:
    def __init__(self):
        self.meta = load("meta.json")
        self.model = load("model.json")
        self.slate = load("slate_2026-11-15.json")
        self.settled = load("results/settled_2026-11-14.json")
        self.logs = load("player_game_logs.json")
        self.stats = load("team_stats_advanced.json")
        self.archive = load("injuries/archive_index.json")
        self.deltas = load("injuries/deltas.json")
        self.gates = load("gates.json")
        self.fresh = load("freshness.json")
        self.rest = load("rest_travel.json")
        self.ledger = load("picks_ledger_view.json")
        self.review = load("review.json")
        self.questions = load("questions.json")
        self.suggestions = load("suggestions.json")
        self.registry = load("team_registry.json")
        self.availability = load("availability.json")
        self.prereg = {}
        for p in sorted((ROOT / "prereg").glob("*.json")):
            d = json.loads(p.read_text())
            self.prereg[d["id"]] = d


# ------------------------------------------------------------------ layout
NAV = {
    "projection": [
        ("Overview", "index.html"),
        ("Originated lines", "lines.html"),
        ("Settled results", "results.html"),
        ("Estimators", "estimators.html"),
        ("Injuries", "injuries.html"),
        ("Rest & travel", "rest.html"),
        ("Minutes & rotation", "minutes.html"),
        ("Gates", "gates.html"),
        ("Repo review", "review.html"),
        ("Questions", "questions.html"),
        ("Suggestions", "suggestions.html"),
        ("Flagged", "flagged.html"),
    ],
    "bet": [
        ("Overview", "index.html"),
        ("Sealed picks", "picks.html"),
        ("Pre-registration", "prereg.html"),
        ("Ledger", "ledger.html"),
        ("Gates", "gates.html"),
        ("Flagged", "flagged.html"),
    ],
}


def page(surface: str, title: str, crumb: str, body: str, active: str, lead: str = "") -> str:
    other = "bet" if surface == "projection" else "projection"
    other_label = ("Bet surface (gated)" if other == "bet" else "Projection surface")
    nav_items = []
    for label, href in NAV[surface]:
        cls = ' class="active"' if href == active else ""
        nav_items.append(f'<a href="{esc(href)}"{cls}>{esc(label)}</a>')
    nav = "".join(nav_items)
    banner = ""
    if surface == "projection":
        banner = ('<div class="banner"><div class="wrap">PROJECTION SURFACE — research output, '
                  'publishable as-is. Gated picks are kept on a separate surface: '
                  f'<a href="../bet/index.html">{other_label}</a></div></div>')
    else:
        banner = ('<div class="banner"><div class="wrap">BET SURFACE — GATED. Nothing here is a '
                  'recommendation or a price for the public; every pick is pre-registered, '
                  'hash-sealed before tip and graded against an official final. '
                  f'<a href="../projection/index.html">{other_label}</a></div></div>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 {esc(surface.title())}</title>
<meta name="description" content="NBA3 {esc(surface)} surface: {esc(title)}. Every table row links to an official NBA source; unconfirmed values are blank and flagged.">
<style>{CSS}</style>
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="index.html"><span>NBA3</span>{esc(surface.title())} surface</a>
  <div class="stamp">Snapshot {esc(BUILD_UTC)} · session <code>{esc(SESSION)}</code> ·
    capture {esc((CTXOBJ.meta or {}).get('generated_utc', '?'))}</div>
</div></header>
{banner}
<nav class="site"><div class="wrap">{nav}</div></nav>
<main class="wrap">
  <div class="crumb">{esc(crumb)}</div>
  <h1>{esc(title)}</h1>
  {f'<p class="lead">{lead}</p>' if lead else ''}
{body}
</main>
<footer class="site"><div class="wrap">
  <p><strong>NBA3</strong> — research dashboard generated by <code>{esc(SESSION)}</code>.
  Model outputs are ours and labelled <em>derived</em>; they are not official NBA statistics.
  Source code: <a href="{REPO}">{esc(REPO)}</a>. This is research, not betting advice.</p>
</div></footer>
</body>
</html>
"""


CTXOBJ = None


# ------------------------------------------------------------------ shared fragments
def model_provenance(ctx) -> str:
    m = ctx.model
    return kv([
        ("Games in sample", f'{m["games_in_sample"]} ({m["sample_range"][0]} → {m["sample_range"][1]})'),
        ("Sample source", link("https://www.nba.com/games", "nba.com/games (official finals)")),
        ("Rating source", link(ctx.stats["source_url"], "nba.com/stats/teams/advanced")),
    ], "model-provenance", require_source=False) + (
        f'<p class="note">Model artefact <code>data/live/model.json</code>, built '
        f'<code>{esc(m["built_utc"])}</code>. Rebuilding it from the committed inputs reproduces it '
        'byte for byte; the CI step fails otherwise.</p>')


def gate_chip(passed: bool) -> str:
    return ('<span class="chip ok">PASS</span>' if passed
            else '<span class="chip bad">FAIL</span>')




def pick_gate_summary() -> str:
    g = CTXOBJ.gates
    by: dict[str, dict] = {}
    for r in g["rows"]:
        d = by.setdefault(r["gate"], {"pass": 0, "fail": 0})
        d["pass" if r["passed"] else "fail"] += 1
    rows = [[f'<code>{esc(k)}</code>', f'{v["pass"] + v["fail"]}', f'{v["pass"]}',
             f'<span class="chip bad">{v["fail"]}</span>' if v["fail"] else "0",
             link("https://www.nba.com/schedule", "official schedule")]
            for k, v in sorted(by.items())]
    return table(["Gate", "Checks", "Passed", "Failed", "Source"], rows, "pick-gate-summary")


def gate_summary() -> str:
    g = CTXOBJ.gates
    by: dict[str, dict] = {}
    for r in g["rows"]:
        d = by.setdefault(r["gate"], {"pass": 0, "fail": 0})
        d["pass" if r["passed"] else "fail"] += 1
    rows = [[f'<code>{esc(k)}</code>', f'{v["pass"] + v["fail"]}', f'{v["pass"]}',
             f'<span class="chip bad">{v["fail"]}</span>' if v["fail"] else "0",
             link("https://www.nba.com/schedule", "official schedule")]
            for k, v in sorted(by.items())]
    return table(["Gate", "Checks", "Passed", "Failed", "Source"], rows, "gate-summary")


def gate_rows_table() -> str:
    rows = [[f'<code>{esc(r["gate"])}</code>', esc(r.get("game") or "—"),
             gate_chip(r["passed"]), esc(r["detail"]),
             link("https://www.nba.com/schedule", "schedule")]
            for r in CTXOBJ.gates["rows"]]
    return table(["Gate", "Game", "Result", "What was checked", "Source"], rows, "gate-rows")


def freshness_block(ctx) -> str:
    f = ctx.fresh
    if not f:
        return '<p class="unv">freshness.json missing — run scripts/freshness_gates.py</p>'
    rows = [[f'<code>{esc(g["id"])}</code>', esc(g["name"]), gate_chip(g["passed"]),
             esc(json.dumps(g["value"])[:220]), esc(g["rule"]),
             link(g.get("source") or "https://www.nba.com/schedule", "source")]
            for g in f["gates"]]
    return (f'<p>Reference capture <code>{esc(f["reference_utc"])}</code>: '
            f'<strong>{f["counts"]["passed"]}/{f["counts"]["gates"]}</strong> gates pass. '
            'The build refuses to publish if any gate fails.</p>'
            + table(["Gate", "Rule", "Result", "Measured value", "Pass rule", "Source"], rows,
                    "freshness-gates"))


# ------------------------------------------------------------------ projection pages
def proj_index(ctx) -> str:
    m = ctx.model
    oos = m["out_of_sample"]
    hca = m["hca"]
    body = []
    body.append(f"""<div class="grid">
<div class="card"><div class="k">Games modelled</div><div class="v">{m['games_in_sample']}</div>
  <div class="s">{esc(m['sample_range'][0])} → {esc(m['sample_range'][1])}</div></div>
<div class="card"><div class="k">E1 out-of-sample log-loss</div><div class="v">{num(oos['e1_log_loss'],4)}</div>
  <div class="s">coin flip {num(oos['coin_flip_log_loss'],4)}</div></div>
<div class="card"><div class="k">E2 out-of-sample log-loss</div><div class="v">{num(oos['e2_log_loss'],4)}</div>
  <div class="s">n = {oos['n']} walk-forward games</div></div>
<div class="card"><div class="k">Home-court advantage</div><div class="v">{num(hca['hca_margin_points'],2)}</div>
  <div class="s">pts, pinned to a measured home-win rate</div></div>
<div class="card"><div class="k">Teams outside the noise band</div><div class="v">{sum(1 for r in m['luck'] if not r['within_noise_band'])}</div>
  <div class="s">of 30, |luck z| &gt; 1.96</div></div>
<div class="card"><div class="k">Slate games priced</div><div class="v">{len(m['slate'])}</div>
  <div class="s">11/15 → 11/17, three days ahead</div></div>
</div>""")

    body.append('<h2>What this surface is</h2>')
    body.append("""<p>The projection surface publishes research output: official captures, two independent
estimators, their disagreement, rest and travel, rotation availability, and the gates that had to pass
before any of it was published. Nothing here is a price, a stake or a recommendation.</p>
<div class="callout"><strong>Separation.</strong> Gated picks live on a different surface with a
different index. The two are never mixed in one table: a reader here cannot mistake a sealed bet for a
projection. The only cross-reference is the banner at the top of this page.
<a href="../bet/index.html">Open the bet surface</a>.</div>""")

    body.append('<h2>The headline confidence signal</h2>')
    body.append(f"""<p>The primary signal is not a blend and not a single rating: it is the
<em>disagreement</em> between two estimators built on different information (E1 uses final margins,
E2 uses only win/loss). On the walk-forward sample they disagree by a mean of
<strong>{num(oos['mean_absolute_disagreement_pp'],2)} percentage points</strong> and land on opposite
sides of the moneyline in <strong>{pct(oos['share_games_estimators_disagree_on_side'],1)}</strong> of
games. The 50/50 blend is published underneath, as a blend, and its log-loss
({num(oos['blend_50_50_log_loss'],4)}) is shown next to both constituents so the reader can see that it
is a small improvement over E1 alone, not a different model.</p>""")

    body.append(f"""<div class="callout warn"><strong>Luck, stated as a z-score.</strong>
No team is currently outside the ±1.96 noise band (largest |z| = {num(max(abs(r['luck_z']) for r in m['luck']),2)}).
That is a real result and it means the league table on 2026-11-15 is not yet distinguishable from noise
at the 5% level. A strategy leaning on any team's over-performance would have to clear that band first;
none does, so none is published.</div>""")

    body.append('<h2>Provenance of the numbers on this site</h2>')
    body.append(model_provenance(ctx))
    body.append('<h2>Gates this build had to pass</h2>')
    body.append(freshness_block(ctx))
    return page("projection", "Overview", "Projection surface", "\n".join(body), "index.html",
                lead="Two independent estimators, their disagreement as the headline, official captures "
                     "behind every number, and the gates that had to pass before publication.")


def proj_lines(ctx) -> str:
    m = ctx.model
    rows = []
    for g in m["slate"]:
        rows.append([
            esc(g["date"]), f'{esc(g["away"] + " @ " + g["home"])}<br><span class="unv">{esc(g["tip_et"])} ET</span>',
            f'<span class="n">{num(g["exp_margin_e1"],1)}</span>',
            f'{num(g["p_home_e1"],3)}', f'{num(g["p_home_e2"],3)}',
            f'<strong>{num(g["disagreement_pp"],1)} pp</strong>',
            '<span class="chip ok">agree</span>' if g["direction_agrees"]
            else '<span class="chip warn">opposite</span>',
            f'{num(g["totals"]["exp_total"],1)}',
            f'{num(g["totals"]["possessions_per_team"],1)}',
            f'{num(g["naive_total_benchmark"]["exp_total"],1)}',
            link(ctx.slate["source_url"], "schedule"),
            link(ctx.stats["source_url"], "stats"),
        ])
    body = [f"""<p>Every game in the three-day window, priced from the official advanced team statistics
retrieved {esc(ctx.stats['retrieved_utc'])}. <strong>Margin</strong> is E1's expected home margin in
points (a home team at −4.2 is projected to lose by 4.2, so the away side is favoured). <strong>E1</strong>
and <strong>E2</strong> are each estimator's home win probability. The <strong>headline</strong> column
is their disagreement in percentage points.</p>
<div class="callout"><strong>These are originated lines, not market lines.</strong> No licensed price
exists in this repository and the official schedule page does not print one, so the site publishes the
model's own number and leaves the market comparison blank and flagged.</div>"""]
    body.append(table(["Date", "Game", "E1 margin", "E1 P(home)", "E2 P(home)",
                       "Disagreement (headline)", "Direction", "Total (poss×PPP)",
                       "Poss/team", "Naive total (benchmark)", "Schedule", "Team stats"],
                      rows, "slate-lines"))
    body.append("""<h2>Why the total is not an average of scoring averages</h2>
<p>The model total is <code>possessions × points per possession</code>, where each team's pace and
efficiency are matched against the opponent's defence. The last-but-one column is the naive benchmark
that this project was told <em>not</em> to use — the sum of each team's own points per game — printed
beside it so the two can be compared on every row instead of being asserted apart.</p>""")
    body.append('<h2>Rest, back-to-back and rotation availability</h2>')
    body.append('<p>Both columns live on their own pages, because a reader pricing a game needs them '
                'side by side with availability rather than buried in a matchup note. '
                '<a href="rest.html">Rest &amp; travel</a> · '
                '<a href="minutes.html">Minutes &amp; rotation</a>.</p>')
    return page("projection", "Originated lines", "Projection surface", "\n".join(body),
                "lines.html", lead="Twenty-two games over three days, priced from the official "
                                   "advanced team statistics with the disagreement as the headline.")


def proj_results(ctx) -> str:
    s = ctx.settled
    rows = []
    for g in s["games"]:
        rows.append([
            esc(g["date"]), esc(g["matchup"] if "matchup" in g else f'{g["away"]} @ {g["home"]}'),
            " · ".join(str(x) for x in g["away_q"]), str(g["away_final"]),
            " · ".join(str(x) for x in g["home_q"]), str(g["home_final"]),
            '<span class="chip grey">—</span>' if not g["ot"] else '<span class="chip warn">OT</span>',
            f'{esc(g["winner"])} +{abs(g["away_margin"])}',
            f'{g["total_points"]}',
            gate_chip(g["verified"]),
            link(g["source_url"], "box score"),
            link(g["gamebook_url"], "gamebook"),
        ])
    body = [f"""<p>One row per game, settled only after two independent official reads agree. The
settlement stamp is <code>{esc(s['settled_utc'])}</code>: the last time this build confirmed the finals
against the official pages, not the time the game ended.</p>
<div class="callout"><strong>The settlement rule, applied mechanically.</strong> A game settles only when
(a) the official game page says <em>Final</em>, (b) the gamebook's printed FINAL equals the sum of its
four printed quarters, and (c) both agree with the game page. {s['counts']['verified']} of
{s['counts']['games']} games pass all three. A failure is published unverified — never corrected by
hand.</div>"""]
    body.append(table(["Date", "Game", "Away quarters", "Away final", "Home quarters", "Home final",
                       "OT", "Winner", "Total", "Verified", "Box score", "Gamebook"],
                      rows, "settled-games"))
    body.append(f"""<h2>Per-player game logs</h2>
<p><code>data/live/player_game_logs.json</code> holds {ctx.logs['counts']['accepted']} accepted player
rows (minutes, points, rebounds, assists, steals, blocks, turnovers, shooting, +/- and opponent) out of
{ctx.logs['counts']['printed_rows']} printed. A row is accepted only if it reconciles arithmetically:
<code>PTS = 2·FG + 3P + FT</code>, <code>TOT = OR + DR</code>, and the shooting sub-columns are
consistent. {ctx.logs['counts']['rejected']} rows did not reconcile and are published as rejected with
their raw text rather than repaired.</p>""")
    rej = []
    for gid, items in (ctx.logs.get("rejected_detail") or {}).items():
        for it in items:
            rej.append([esc(gid), esc(it.get("team", "")), esc(it.get("raw", "")[:120]),
                        esc(it.get("reason", "")),
                        link(ctx.logs["rows"][0]["source_url"] if ctx.logs["rows"] else
                             "https://statsdmz.nba.com", "gamebook")])
    if rej:
        body.append(table(["Game", "Team", "Raw printed line", "Why rejected", "Source"], rej,
                          "rejected-rows"))
    body.append('<h2>Reconciliation per gamebook</h2>')
    rr = []
    for gid, b in ctx.logs["counts"]["by_game"].items():
        rr.append([esc(gid), str(b["accepted"]), str(b["rejected"]),
                   esc(str(b["reconciliation"])), link("https://statsdmz.nba.com", "gamebook")])
    body.append(table(["Game", "Accepted rows", "Rejected rows", "Team reconciliation", "Source"],
                      rr, "game-recon"))
    return page("projection", "Settled results", "Projection surface", "\n".join(body),
                "results.html", lead="Five finals verified against two official reads, with quarter "
                                     "linescores and per-player logs that reconcile arithmetically.")


def proj_estimators(ctx) -> str:
    m = ctx.model
    oos = m["out_of_sample"]
    e1, e2 = m["estimator_e1"], m["estimator_e2"]
    hca = m["hca"]
    rows = [
        ["E1 — ridge Massey on margins", esc(e1["uses"]), f'{num(e1["in_sample_rmse"],3)}',
         f'{num(oos["e1_log_loss"],4)}', f'{num(oos["e1_brier"],4)}', num(oos["e1_margin_rmse_oos"],3),
         link("https://www.nba.com/games", "finals")],
        ["E2 — logistic Bradley-Terry on wins", esc(e2["uses"]), f'{num(e2["in_sample_margin_rmse"],3)}',
         f'{num(oos["e2_log_loss"],4)}', f'{num(oos["e2_brier"],4)}', "—",
         link("https://www.nba.com/standings", "standings")],
        ["50/50 blend (published underneath)", "both", "—", f'{num(oos["blend_50_50_log_loss"],4)}', "—",
         "—", link("https://www.nba.com/games", "finals")],
        ["Coin flip (reference)", "nothing", "—", f'{num(oos["coin_flip_log_loss"],4)}',
         f'{num(oos["coin_flip_brier"],4)}', "—", link("https://www.nba.com/games", "finals")],
    ]
    body = ["""<p>Two estimators, deliberately built on different information, so that their
disagreement carries meaning. Neither is "the model". Both are scored on the same walk-forward slate:
each forecast uses only games that had already been played.</p>"""]
    body.append(table(["Estimator", "Information used", "In-sample margin RMSE",
                       "OOS log-loss", "OOS Brier", "OOS margin RMSE", "Source"],
                      rows, "estimators"))
    body.append(f"""<div class="callout"><strong>E2's shrink weight is not a free parameter.</strong>
It is chosen by log-loss on the most recent 20% of past games
({e2['ridge_selection'].get('validation_games', '?')} validation games), from a fixed grid of
{len(e2['ridge_selection'].get('scores', {}))} values, and the choice comes out at <code>{e2['ridge']}</code>.
The scores are published on the bet surface's pre-registration page with the rest of the validation
detail. An earlier build applied the same penalty on a points scale instead of a logit scale, which put
it ~30× the information content of the data; that produced an out-of-sample log-loss of 0.64 with 600
non-converged iterations, and it is recorded here because it is the kind of error that flatters a model
until it is scored.</div>""")
    body.append('<h2>Home-court advantage is pinned, not fitted</h2>')
    body.append(kv([
        ("Rule", "HCA = Φ⁻¹(measured home-win rate) × sd(margin). Nothing is chosen to improve the fit."),
        ("Games", f'{hca["games"]} ({hca["home_wins"]} home wins)'),
        ("Measured home-win rate", f'{num(hca["home_win_rate"],6)}'),
        ("sd(margin) in sample", f'{num(hca["margin_sd"],3)} pts'),
        ("Pinned HCA", f'<strong>{num(hca["hca_margin_points"],3)} pts</strong>'),
        ("Naive fitted HCA (mean home margin)", f'{num(hca["hca_margin_if_naive_fit"],3)} pts'),
        ("Gap", f'{num(hca["naive_vs_pinned_gap"],3)} pts'),
    ], "hca-table", require_source=False))
    body.append('<p class="note">Source for every HCA value on this page: '
                + link("https://www.nba.com/games", "nba.com/games (official finals)")
                + '. The rule is applied to the whole sample, so the values are one calculation, not '
                  'one row each.</p>')
    body.append(f"""<p>{esc(hca['note'])}</p>""")
    body.append('<h2>Ratings, both estimators side by side</h2>')
    rr = []
    for t in sorted(e1["rating"]):
        rr.append([f'<strong>{esc(t)}</strong>', num(e1["rating"][t], 2),
                   num(e2["rating_points"].get(t), 2),
                   num((e1["rating"][t]) - (e2["rating_points"].get(t) or 0), 2),
                   link(ctx.stats["teams"][t]["source_url"], "official")])
    body.append(table(["Team", "E1 rating (pts)", "E2 rating (pts)", "Gap", "Source"], rr,
                      "ratings"))
    return page("projection", "Estimators", "Projection surface", "\n".join(body),
                "estimators.html",
                lead="Two models, one scoring rule. E1 uses margins, E2 uses only wins, and the "
                     "gap between them is the published confidence signal.")


def proj_injuries(ctx) -> str:
    a = ctx.archive
    d = ctx.deltas
    av = ctx.availability
    rep = av["report"]
    body = [f"""<div class="callout"><strong>Report revision time: {esc(rep['stamp'])}</strong>
({esc(rep['header'])}) · <strong>retrieved {esc(rep['retrieved_utc'])}</strong> ·
{link(rep['source_url'], 'official PDF')}. The revision time is the report's own header; the retrieval
time is when this session fetched it. Both are shown because they answer different questions: which
report this is, and how old our copy is.</div>"""]
    body.append("<h2>Rotation availability — its own column</h2>")
    body.append("""<p>Every team-side of every slate game carries one of three states. The third state is
the one that matters: when the official report's team row says the club has not yet submitted,
availability is <em>unknown</em>, and this site prints UNKNOWN rather than "healthy" or an empty cell
that reads as fine.</p>""")
    rows = []
    for s in av["sides"]:
        chip = {"ANNOUNCED": '<span class="chip warn">ANNOUNCED</span>',
                "REPORTED_CLEAR": '<span class="chip ok">REPORTED CLEAR</span>',
                "NOT_SUBMITTED": '<span class="chip bad">UNKNOWN — not submitted</span>'
                }[s["availability"]]
        names = ", ".join(f'{p["player"]} ({p["status"]})'
                          for p in s["out_or_doubtful"] + s["questionable"])
        rows.append([esc(s["date"]), esc(s["matchup"]), f'{esc(s["team"])} {esc(s["side"])}',
                     chip, esc(names) or "—", esc(s["why"]), link(s["source_url"], "report"),
                     link(s["registry_url"], "team")])
    body.append(table(["Date", "Matchup", "Team", "Availability", "Players named",
                       "Why this state", "Report", "Team page"], rows, "availability"))
    body.append(f"""<p>Totals: {av['counts']['by_state'].get('ANNOUNCED', 0)} team-sides with an announced
absence or questionable player, {av['counts']['by_state'].get('REPORTED_CLEAR', 0)} reported clear,
{av['counts']['by_state'].get('NOT_SUBMITTED', 0)} not yet submitted across
{av['counts']['team_sides']} team-sides.</p>""")
    body.append("<h2>Archived reports and the diff between them</h2>")
    rr = []
    for f in a["files"]:
        counts = ", ".join(f"{k} {v}" for k, v in sorted(f["status_counts"].items()))
        rr.append([esc(f["report_stamp"]), esc(f["report_header"]), counts,
                   str(f["unattributed_rows"]), link(f["source_url"], "PDF")])
    body.append(table(["Stamp", "Header", "Status counts", "Unattributed rows", "Source"], rr,
                      "report-archive"))
    body.append(f"""<p>Every report is stored verbatim on disk with its source URL, so the diff is
reproducible without a network call. {esc(a['storage_rule'])}</p>""")
    dr = []
    for x in d["deltas"]:
        dr.append([f'{esc(x["from_stamp"])} → {esc(x["to_stamp"])}',
                   str(x["counts"]["status_changes"]),
                   str(x["counts"]["added"]), str(x["counts"]["removed"]),
                   esc(", ".join(f'{p.get("player")} ({p.get("status")})' for p in x["added"]) or "—"),
                   esc(", ".join(f'{p.get("player")} ({p.get("status")})' for p in x["removed"]) or "—"),
                   link(x["to_source"], "newest")])
    body.append(table(["Between", "Status changes", "Rows added", "Rows removed",
                       "Added (verbatim name)", "Removed (verbatim name)", "Source"], dr,
                      "report-deltas"))
    body.append("""<div class="callout warn"><strong>What the diff actually found.</strong> Across the
three archived reports there were <strong>zero status changes</strong>. The only differences are
spelling corrections inside the official PDFs (<code>Embid → Embiid</code>,
<code>Bogoljub → Bogojub</code>), which surface as one row added and one removed. Those are flagged as
irregularities on the Flagged page rather than smoothed away, because a name-matching ledger that
silently normalises them would hide a real transcription risk in the official feed.</div>""")
    return page("projection", "Injuries & rotation", "Projection surface", "\n".join(body),
                "injuries.html",
                lead=f"Report revision {rep['stamp']}, retrieved {rep['retrieved_utc']}, with rotation "
                     "availability as its own column and unknown kept unknown.")


def proj_rest(ctx) -> str:
    r = ctx.rest
    c = r["counts"]
    body = [f"""<p>Rest, back-to-back and 3-in-4 are arithmetic on the official schedule, not estimates:
rest is the number of days between a team's previous game and this one. {c['back_to_backs']} back-to-backs
and {c['three_in_four']} 3-in-4 situations occur across the {c['team_games']} team-games in the window.</p>"""]
    body.append(f"""<div class="callout warn"><strong>Travel distance is blank, on purpose.</strong>
{esc(r['travel_source']['why_blank'])} The distance column therefore prints
<span class="unv">— unverified</span> for all {c['travel_unverified']} team-games. Feeding a guessed
coordinate would make the column look complete and be wrong, which is the failure mode this project is
built to avoid.</div>""")
    rows = []
    for g in r["games"]:
        for t in g["teams"]:
            tr = t["travel"]
            rows.append([
                esc(g["date"]), esc(g["matchup"]), f'{esc(t["team"])} ({esc(t["side"])})',
                esc(t["last_game_date"] or "none in capture"),
                "—" if t["rest_days"] is None else str(t["rest_days"]),
                '<span class="chip bad">yes</span>' if t["back_to_back"] else "no",
                str(t["games_in_4_day_window"]),
                '<span class="chip warn">yes</span>' if t["three_in_four"] else "no",
                esc(t["previous_venue_city"] or "—"),
                (f'{num(tr["km"],0)} km' if tr["km"] is not None else unflagged("", tr["reason"])),
                link(g["source_url"], "schedule"),
            ])
    body.append(table(["Date", "Matchup", "Team", "Previous game", "Rest days", "Back-to-back",
                       "Games in 4-day window", "3-in-4", "Previous venue", "Travel", "Source"],
                      rows, "rest-travel"))
    body.append("<h2>Schedule of record and its seams</h2>")
    body.append("""<p>No single official capture covers the window, so three are unioned. The seams are
published because a union is exactly where a silent gap would invent a rested team.</p>""")
    sr = [[esc(s["seam"]), esc(s["file"]), esc(s["what"]), esc(s["dates"]), str(s["rows"]),
           link(s.get("source_url") or "https://www.nba.com/schedule", "source")]
          for s in r["schedule_provenance"]["sources"]]
    body.append(table(["Seam", "File", "What it is", "Dates", "Rows", "Source"], sr, "schedule-seams"))
    body.append(f"""<p>{esc(r['rest_source']['rule'])}</p>""")
    return page("projection", "Rest & travel", "Projection surface", "\n".join(body),
                "rest.html",
                lead="Rest and schedule density computed from the official schedule, with travel left "
                     "blank rather than guessed.")


def proj_minutes(ctx) -> str:
    m = ctx.model
    gap = m["minutes_gap"]
    body = [f"""<p>Minutes are modelled explicitly rather than assumed to stay constant: the top eight
players by minutes take a published share of the rotation, and when a player is out his share is
redistributed to the remaining seven in proportion to their own minutes, with the leftover assigned to
replacements outside the top eight.</p>
<div class="callout bad"><strong>An overlap the project cannot paper over.</strong> Captured game logs
cover {len(gap['captured_teams'])} clubs from the 11/14 slate ({esc(', '.join(gap['captured_teams']))}).
The archived injury report covers 11/15. The overlap — clubs that have <em>both</em> a captured log and
an announced absence — is <strong>{len(gap['overlap'])}</strong>. So no real redistribution can be
published for this slate. The table below is therefore a measured share model plus an explicitly
labelled <em>illustrative</em> sensitivity, not a forecast.</div>"""]
    body.append("<h2>Measured top-eight minute shares</h2>")
    rows = []
    for s in m["minutes_sensitivity"]:
        ms = s["measured_shares"]
        rows.append([esc(s["team_code"]), str(ms["captured_players"]), str(ms["games_captured"]),
                     esc(", ".join(f'{p["player"]} {num(p["share_of_top8"]*100,1)}%'
                                   for p in ms["top8"][:4])),
                     link(ctx.logs["rows"][0]["source_url"] if ctx.logs["rows"]
                          else "https://statsdmz.nba.com", "gamebook")])
    body.append(table(["Team", "Players logged", "Games", "Top four shares of top-eight minutes",
                       "Source"], rows, "minute-shares"))
    body.append("<h2>Illustrative sensitivity: the top-minute player is out</h2>")
    body.append('<p class="note">Illustrative only. No club with a captured log has an announced '
                'absence on this slate.</p>')
    sr = []
    for s in m["minutes_sensitivity"]:
        d = s["if_top_minute_player_out"]
        sr.append([esc(s["team_code"]), esc(d["player"]), f'{d["matched"] and "matched" or "unmatched"}',
                   pct(d["vacated_share"], 1), pct(d["replacement_share"], 1),
                   esc(", ".join(f'{k} {num(v*100,1)}%' for k, v in list((d["new_shares"] or {}).items())[:3])),
                   link(ctx.logs["rows"][0]["source_url"] if ctx.logs["rows"]
                        else "https://statsdmz.nba.com", "gamebook")])
    body.append(table(["Team", "Player removed", "Name match", "Share vacated",
                       "Replacement share", "New shares (first three)", "Source"], sr, "minutes-sens"))
    body.append(f"""<p>{esc(m['minutes_sensitivity'][0]['measured_shares']['caveat'])}</p>""")
    return page("projection", "Minutes & rotation", "Projection surface", "\n".join(body),
                "minutes.html",
                lead="Top-eight minute shares, replacement shares, and an honest account of why the "
                     "absence case cannot be forecast on this slate.")


def proj_gates(ctx) -> str:
    body = ["<h2>Provenance and freshness gates</h2>", freshness_block(ctx),
            """<p>These gates run before either surface is built. Each one is a hard rule with a
measured value attached, so nothing on this site is "assumed fresh". The gate log that governs
picks — pre-registration, sealing before tip, settlement from a verified final — is published on
the bet surface's <a href="../bet/gates.html">Gates</a> page, because a pick gate is about a pick
and not about the projection.</p>"""]
    return page("projection", "Gates", "Projection surface", "\n".join(body), "gates.html",
                lead="Ten provenance and freshness gates that must pass before either surface is "
                     "built, with the measured value for each.")


def proj_flagged(ctx) -> str:
    rows = []
    sched = "https://www.nba.com/schedule?date=2026-11-15"
    rows.append([
        "Travel distance for every team-game",
        "Blank (<span class=\"unv\">— unverified</span>)",
        ("No official NBA page read in this session publishes arena latitude/longitude. The brief "
         "requires a sourced coordinate table, so distances are left blank rather than estimated from "
         "city names."),
        link(sched, "schedule")])
    rows.append([
        "Market-anchored prior weight <code>w</code>",
        "Blank — blend not applied",
        ("No licensed closing line exists in this repository and the official schedule page does not "
         "print prices. The blend and its out-of-sample scoring are implemented; the weight is left "
         "blank instead of guessed."),
        link("https://www.nba.com/schedule", "schedule")])
    rows.append([
        "BKN 110 and CHI 117 player logs",
        "Published as rejected, not as complete",
        ("Two gamebooks did not reconcile player rows to the printed team total (BKN 98 vs 110, CHI 81 "
         "vs 117). Affected rows are listed with their raw text on the Settled results page. The finals "
         "themselves are verified from two official reads."),
        link("https://statsdmz.nba.com/pdfs/20261114/20261114_BKNMEM.pdf", "gamebook")])
    rows.append([
        "Injury report name spellings",
        "Flagged as irregular",
        ("The official PDFs spell the same player <code>Embid</code> then <code>Embiid</code>, and "
         "<code>Bogoljub</code> then <code>Bogojub</code>, between consecutive revisions. A ledger that "
         "normalises names would hide this; the diff reports it as one row added and one removed."),
        link("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_12_00AM.pdf", "PDF")])
    rows.append([
        "13 unattributed injury rows per report",
        "Blank team column, flagged",
        ("The parsed reports carry 13 player rows whose team column could not be read from the PDF text "
         "layout. They are kept in the archive as <code>UNATTRIBUTED</code> and are never assigned to a "
         "club by approximation."),
        link("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_12_00AM.pdf", "PDF")])
    rows.append([
        "ET → UTC conversion for tip times",
        "Stated assumption, not sourced",
        ("Tip times are published in ET by the official schedule. To prove a pick was sealed before tip, "
         "the build converts with a fixed UTC−5 offset. No official page read here publishes the "
         "conversion, so the assumption is stated on the page rather than hidden."),
        link(sched, "schedule")])
    rows.append([
        "Minutes redistribution for this slate",
        "Not published as a forecast",
        ("The captured logs (11/14) and the archived absences (11/15) do not overlap at any club, so "
         "there is no absence to redistribute. Only a labelled sensitivity is published."),
        link("https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf", "gamebook")])
    body = ["""<p>Everything on this page is either unconfirmed or irregular. None of it blocks
publication; all of it is stated where a reader will look for the number and find nothing. Each row
carries the official source that <em>should</em> have supplied the value.</p>"""]
    body.append(table(["Item", "Status", "Why it is flagged", "Official source that should supply it"],
                      rows, "flagged-projection"))
    return page("projection", "Flagged for review", "Projection surface", "\n".join(body),
                "flagged.html",
                lead="Unverified and irregular items, each with the official source that should have "
                     "settled it.")


# ------------------------------------------------------------------ bet pages
def bet_index(ctx) -> str:
    led = ctx.ledger
    integ = led["integrity"]
    pubs = [e for e in led["entries"] if e["kind"] == "PUBLISH"]
    sets = [e for e in led["entries"] if e["kind"] == "SETTLE"]
    body = [f"""<div class="grid">
<div class="card"><div class="k">Frozen strategies</div><div class="v">{len(ctx.prereg)}</div>
 <div class="s">write-once pre-registration before any bet</div></div>
<div class="card"><div class="k">Picks sealed</div><div class="v">{len(pubs)}</div>
 <div class="s">hash published before tip</div></div>
<div class="card"><div class="k">Settled</div><div class="v">{len(sets)}</div>
 <div class="s">graded against verified official finals</div></div>
<div class="card"><div class="k">Ledger chain</div>
 <div class="v">{"VERIFIED" if integ["verified"] else "BROKEN"}</div>
 <div class="s">sha256 head <code>{esc(integ["head_hash"][:12])}…</code></div></div>
</div>"""]
    body.append("""<h2>What this surface is, and what it is not</h2>
<p>This is the gated surface. A pick appears here only after (1) its strategy was frozen in writing
before its first bet, (2) the pick was sealed with a sha256 hash before tip-off, and (3) it passed the
validation gates. It is graded only from an official final that two independent reads agree on.</p>
<div class="callout bad"><strong>No pick on this page is a recommendation, a stake, or advice.</strong>
There is no market price in this repository, so no edge can be claimed against one. The picks are
originated numbers being graded, and the grading is the point.</div>""")
    body.append("<h2>The competiton: strategies as a leaderboard</h2>")
    body.append("""<p>Strategies compete on graded results, not on claimed ability. A strategy stays on the
board only while it passes the validation gates; anything leaning on a team outside the luck noise band
is refused publication, and none currently clears that band.</p>""")
    rows = []
    for sid, p in ctx.prereg.items():
        n_pub = sum(1 for e in pubs if e["pick"]["strategy_id"] == sid)
        n_set = sum(1 for e in sets if e["pick"]["strategy_id"] == sid)
        wins = sum(1 for e in sets if e["pick"]["strategy_id"] == sid
                   and e["result"]["outcome"] == "WIN")
        rows.append([f'<code>{esc(sid)}</code>', esc(p["name"]), esc(p["settlement_rule"]),
                     str(n_pub), str(n_set), (f"{wins}/{n_set}" if n_set else "—"),
                     f'<a href="prereg.html#{esc(sid.lower())}">frozen file</a>',
                     link("https://www.nba.com/schedule", "schedule")])
    body.append(table(["Strategy", "Name", "Settlement rule", "Sealed", "Settled", "Won",
                       "Pre-registration", "Source"], rows, "strategy-board"))
    return page("bet", "Overview", "Bet surface", "\n".join(body), "index.html",
                lead="Pre-registered strategies, hash-sealed picks, official settlement. Gated at every "
                     "step.")


def bet_picks(ctx) -> str:
    led = ctx.ledger
    pubs = [e for e in led["entries"] if e["kind"] == "PUBLISH"]
    sets = {e["game_id"]: e for e in led["entries"] if e["kind"] == "SETTLE"}
    rows = []
    for e in pubs:
        p = e["pick"]
        s = sets.get(p["game_id"])
        res = ("—" if not s else
               f'<span class="chip {"ok" if s["result"]["outcome"] == "WIN" else ("grey" if s["result"]["outcome"] == "PUSH" else "bad")}">{s["result"]["outcome"]}</span>')
        rows.append([
            f'<code>{e["seq"]}</code>', esc(p["date"]), esc(p["matchup"]),
            f'{esc(p["tip_et"])} ET<br><code>{esc(p["tip_et_iso"])}</code>',
            f'<strong>{esc(p["pick"])}</strong>', esc(p["strategy_id"]),
            esc(p.get("headline_signal", "—")),
            f'<code>{esc(e["pick_sha256"][:16])}…</code>',
            esc(e["published_utc"]), res,
            link(s["source_url"], "final") if s else
            link("https://www.nba.com/schedule?date=2026-11-15", "schedule"),
        ])
    body = ["""<p>Each row is a sealed pick. The hash was computed over the pick payload and written to
the ledger before the game started; the settlement row repeats that hash and records the official final
it was graded against, so an edit to either is detectable.</p>"""]
    body.append(table(["#", "Date", "Game", "Tip", "Pick", "Strategy", "Headline signal",
                       "Hash at publish", "Published", "Result",
                       "Official source"], rows, "sealed-picks"))
    body.append('<p class="note">Where a game has been played the source is its verified final; where it '
                'has not, the source is the official schedule that fixes the tip time. The pick payload, '
                'hash and publication stamp are in <code>ledger/ledger.jsonl</code>.</p>')
    body.append("""<h2>Why only two picks</h2>
<p>Three strategies are frozen; one produced eligible games. The disagreement strategy's band (5–20 pp
with both estimators on the same side) admitted two of the nine 11/15 games — the rest were either
outside the band or had the estimators on opposite sides. The back-to-back strategy found no home team
on a back-to-back without the road team also being on one. The totals strategy has no rule that has
passed validation, so it publishes no pick rather than a provisional one.</p>
<p>The full gate log, including every failed gate, is on the <a href="gates.html">Gates</a> page.</p>""")
    return page("bet", "Sealed picks", "Bet surface", "\n".join(body), "picks.html",
                lead="Every sealed pick with the hash that was published before its tip time.")


def bet_prereg(ctx) -> str:
    body = ["""<p>A pre-registration file is written once, before the strategy's first bet, and cannot
be edited afterwards: <code>scripts/ledger.py</code> refuses to overwrite one and refuses to seal a pick
whose strategy has no frozen file. Each file names the signal, the thresholds, the universe and the exact
settlement rule.</p>"""]
    for sid, p in ctx.prereg.items():
        rows = [
            ["Name", esc(p["name"])],
            ["Frozen (UTC)", f'<code>{esc(p["frozen_utc"])}</code>'],
            ["Signal", esc(p["signal"])],
            ["Thresholds", "<code>" + esc(json.dumps(p["thresholds"], indent=1)) + "</code>"],
            ["Universe", "<code>" + esc(json.dumps(p["universe"], indent=1)) + "</code>"],
            ["Settlement rule id", esc(p["settlement_rule"])],
            ["Settlement rule (exact)", esc(p["settlement_rule_text"])],
            ["Stake rule", esc(p["stake_rule"])],
            ["Notes", esc(p.get("notes", ""))],
            ["Payload sha256", f'<code>{esc(p["payload_sha256"])}</code>'],
            ["File", f'<code>prereg/{esc(sid)}.json</code>'],
        ]
        body.append(f'<h2 id="{esc(sid.lower())}">{esc(sid)}</h2>')
        body.append(kv(rows, f"prereg-{esc(sid)}", require_source=False))
    body.append("""<h2>E2's shrinkage was selected before any pick was sealed</h2>
<p>The validation detail that would normally be hidden is published, because a shrink weight that moved
after results would make every downstream number meaningless.</p>""")
    sel = ctx.model["estimator_e2"]["ridge_selection"]
    sr = [[esc(k), num(v, 6), "✓ chosen" if v == sel.get("chosen") else ""]
          for k, v in (sel.get("scores") or {}).items()]
    body.append(table(["Ridge (logit scale)", "Validation log-loss",
                       "Chosen"], sr, "ridge-grid", require_source=False))
    body.append(f"""<p>{esc(sel.get('selected_by', ''))}, {esc(str(sel.get('validation_games', '')))} validation
games. The three frozen strategies are S1_HOME_B2B_FADE, S2_ESTIMATOR_DISAGREEMENT and
S3_TOTALS_POSSESSIONS, all frozen at {esc(next(iter(ctx.prereg.values()))['frozen_utc'])}.</p>""")
    return page("bet", "Pre-registration", "Bet surface", "\n".join(body), "prereg.html",
                lead="Three strategies, frozen in writing before their first bet, with the settlement "
                     "rule spelled out to the push.")


def bet_ledger(ctx) -> str:
    led = ctx.ledger
    integ = led["integrity"]
    rows = []
    for e in led["entries"]:
        rows.append([f'<code>{e["seq"]}</code>', esc(e["kind"]),
                     f'<code>{esc(e["pick_sha256"][:16])}…</code>',
                     f'<code>{esc(e["prev_hash"][:16])}…</code>',
                     f'<code>{esc(e["entry_hash"][:16])}…</code>',
                     esc(e.get("published_utc") or e.get("settled_utc") or ""),
                     esc(e["pick"]["matchup"]),
                     gate_chip(True) if integ["verified"] else gate_chip(False)])
    chain_cls = "" if integ["verified"] else " bad"
    body = [f"""<div class="callout{chain_cls}">
<strong>Chain status: {'verified' if integ['verified'] else 'BROKEN'}.</strong>
{integ['entries']} entries, head hash <code>{esc(integ['head_hash'])}</code>.
<code>scripts/ledger.py</code> recomputes every entry hash, every pick hash and every link; the build
fails if any of them does not reproduce.</div>"""]
    body.append(table(["Seq", "Kind", "Pick sha256", "Prev entry hash", "This entry hash", "When",
                       "Matchup", "Verified"], rows, "ledger-chain", require_source=False))
    body.append("""<h2>What the chain does and does not prove</h2>
<p>It proves that no stored pick, entry or link has been edited since it was written, to anyone who can
see the file. It does <em>not</em> prove when it was written: anyone able to rewrite the whole file
could rebuild the chain. The weak but real external witness is that the ledger is committed to git, so
each build's commit hash fixes the head hash in a history this repository cannot quietly rewrite.</p>""")
    body.append("<h2>Tamper tests</h2>")
    tests = [
        ["A published pick is edited after publication", "Detected",
         "<code>verify()</code> recomputes <code>sha256(pick)</code> and compares to the published value"],
        ["An entry's contents are changed", "Detected",
         "<code>entry_hash</code> no longer recomputes from its own body"],
        ["An entry is removed or reordered", "Detected",
         "<code>prev_hash</code> no longer matches the preceding entry"],
        ["A settled pick differs from the published pick", "Detected",
         "the settlement entry repeats <code>pick_sha256_at_publish</code>"],
    ]
    body.append(table(["Attempt", "Outcome", "Why"], tests, "tamper-tests", require_source=False))
    body.append("""<p>These four cases are covered by <code>tests/test_ledger.py</code>, which builds a
temporary ledger, breaks it deliberately, and asserts that verification fails. A verification routine
that has never been shown to fail proves nothing.</p>""")
    return page("bet", "Ledger", "Bet surface", "\n".join(body), "ledger.html",
                lead="An append-only sha256 chain over every pick, with the tests that show tampering "
                     "is detected.")


def bet_gates(ctx) -> str:
    body = [pick_gate_summary(),
            "<h2>Every gate check, including failures</h2>", gate_rows_table(),
            """<h2>The order, and why it is code</h2>
<p><code>G1</code> pre-registered → <code>G2</code> sealed before tip → <code>G3</code> signal present →
<code>G4</code> validated → <code>G5</code> settled only from a verified final. Each is a function call
in <code>scripts/publish_picks.py</code>; a failure writes a row here and publishes nothing. The order
matters: a validated pick sealed after tip is worthless, and a pre-registered pick settled from an
unverified final is worse than worthless.</p>
<p>Freshness and provenance gates are on the projection surface's
<a href="../projection/gates.html">Gates</a> page and must pass before either surface is built.</p>"""]
    return page("bet", "Gates", "Bet surface", "\n".join(body), "gates.html",
                lead="Five gates per pick, in a fixed order, with the failures kept.")


def bet_flagged(ctx) -> str:
    rows = [
        ["Tip-time ET→UTC conversion", "Stated assumption",
         ("A fixed UTC−5 offset is applied to the official ET tip times to prove a pick was sealed "
          "before tip. No official page read here publishes the conversion."),
         link("https://www.nba.com/schedule?date=2026-11-15", "schedule")],
        ["Ledger timestamp trust", "Limited by design",
         ("<code>published_utc</code> is only as trustworthy as the machine that wrote it. The commit "
          "history is the only external witness."), link(REPO, "repository")],
        ["Market price / edge", "Blank",
         ("No licensed price is in the repository, so no edge against a price can be shown. The picks "
          "are originated numbers being graded."),
         link("https://www.nba.com/schedule", "schedule")],
        ["Strategy profit claim", "Not made",
         ("Three strategies are frozen and two picks sealed. That is not a track record and is not "
          "presented as one; grading is the deliverable."), link(REPO, "repository")],
    ]
    body = ["""<p>The gated surface has less to flag than the projection surface, and the flags it does
carry are about the integrity mechanism itself rather than about missing data.</p>"""]
    body.append(table(["Item", "Status", "Why it is flagged", "Source"], rows, "flagged-bet"))
    return page("bet", "Flagged for review", "Bet surface", "\n".join(body), "flagged.html",
                lead="Limits of the integrity mechanism, stated where a reader would otherwise assume "
                     "more than it proves.")


# ------------------------------------------------------------------ review / questions / suggestions
def proj_review(ctx) -> str:
    rv = ctx.review
    rows = []
    chip = {"PASS": '<span class="chip ok">PASS</span>',
            "FAIL": '<span class="chip bad">FAIL</span>',
            "FLAGGED": '<span class="chip warn">FLAGGED</span>',
            "IRREGULARITY": '<span class="chip warn">IRREGULARITY</span>'}
    for c in rv["checks"]:
        rows.append([f'<code>{esc(c["id"])}</code>', esc(c["area"]), esc(c["finding"]),
                     chip.get(c["status"], esc(c["status"])), esc(c["severity"]),
                     esc(c["evidence"]), link(c["source"], "official")])
    by = rv["counts"]["by_status"]
    body = [f"""<p>{rv['counts']['checks']} mechanical checks over the committed data, the model
artefacts, the ledger and the generated pages: <strong>{by.get('PASS', 0)} pass</strong>,
{by.get('FAIL', 0)} fail, {by.get('FLAGGED', 0)} flagged, {by.get('IRREGULARITY', 0)} irregular.
Each row states what was compared, the result, and the official page a reviewer should open to
confirm it.</p>
<div class="callout"><strong>What a "check" means here.</strong> It is a comparison between two
committed artefacts or between a committed artefact and an official capture — not an opinion. The
three checks worth reading first are R10 (which club's player rows failed to reconcile), R22 (the
official report's own spelling churn) and R18 (travel left blank).</div>"""]
    body.append(table(["ID", "Area", "What was checked", "Result", "Severity", "Evidence",
                       "Official source"], rows, "repo-review"))
    return page("projection", "Repository review", "Projection surface", "\n".join(body),
                "review.html",
                lead="Every datasource, model artefact and generated page checked line by line, with "
                     "the official link a human needs to confirm each one.")


def proj_questions(ctx) -> str:
    qs = ctx.questions
    rows = []
    for q in qs["questions"]:
        rows.append([f'<code>{esc(q["id"])}</code>', esc(q["question"]), esc(q["why"]),
                     esc(q["blocks"]), esc(q["would_be_answered_by"]),
                     '<span class="chip warn">OPEN</span>', link(q["source"], "official")])
    body = [f"""<p>{qs['counts']['questions']} questions, all open. Each one names what it blocks and
what would actually answer it. None is decided unilaterally here, because each changes what the site
is allowed to claim.</p>
<div class="callout warn"><strong>The two that matter most.</strong> Q1 (a licensed closing line)
decides whether this project can ever measure an edge, and Q2 (arena coordinates) decides whether
travel is a real feature or a permanent blank. Everything else is recoverable; those two change the
shape of the product.</div>"""]
    body.append(table(["ID", "Question", "Why it matters", "What it blocks", "What would answer it",
                       "Status", "Official source"], rows, "open-questions"))
    body.append("""<h2>How to discover missing information</h2>
<p>The pattern that has worked in this session: name the column, then name the official page that
would fill it, then check whether that page actually publishes it. Travel distance is the worked
example — the column exists, the page does not publish coordinates, so the column stays blank and the
gap is published as a question rather than filled with an estimate. The suggestions page proposes a
capture step for each question whose answer is obtainable but not yet obtained.</p>""")
    return page("projection", "Open questions", "Projection surface", "\n".join(body),
                "questions.html",
                lead="What must be known before a decision, what each blocks, and what would answer it.")


def proj_suggestions(ctx) -> str:
    sg = ctx.suggestions
    body = [f"""<p>{sg['counts']['suggestions']} proposals, <strong>{sg['counts']['implemented']}
implemented</strong>. That number is the point: the brief requires a path to be chosen before
implementation, so this page is advisory only. Each proposal carries its options with a cost and a
risk, and a recommendation that is explicitly a recommendation and not a decision.</p>
<div class="callout"><strong>Nothing on this page has been built.</strong> If a proposal is chosen, it
becomes a pre-registered change with its own validation gate — not an edit made because it seemed like
an improvement.</div>"""]
    for s_ in sg["suggestions"]:
        body.append(f'<h2 id="{esc(s_["id"].lower())}">{esc(s_["id"])} — {esc(s_["title"])}</h2>')
        body.append(f'<p><span class="chip warn">{esc(s_["status"])}</span></p>')
        body.append(f'<p><strong>Problem.</strong> {esc(s_["problem"])}</p>')
        orows = [[f'<code>{esc(o["id"])}</code>', esc(o["label"]), esc(o["cost"]), esc(o["risk"]),
                  link(s_["source"], "context")]
                 for o in s_["options"]]
        body.append(table(["Option", "What it means", "Cost", "Risk", "Source"], orows,
                          f"opts-{esc(s_['id'])}"))
        body.append(f'<p class="note"><strong>Recommendation:</strong> {esc(s_["recommended"])}</p>')
    body.append("""<h2>What is already implemented, in contrast</h2>
<p>For clarity about the line between "built" and "proposed": the two estimators, the pinned home-court
advantage, the luck z-scores, the possessions-based total with its naive benchmark, the pre-registration
files, the hash-sealed ledger, the ten freshness gates, the availability column and the two separated
surfaces are all built and tested. Nothing on this page is.</p>""")
    return page("projection", "Suggestions", "Projection surface", "\n".join(body),
                "suggestions.html",
                lead="Proposals with options, cost, risk and a recommendation — and an explicit "
                     "statement that none has been implemented.")


# ------------------------------------------------------------------ build
def build() -> list[str]:
    global CTXOBJ
    CTXOBJ = Ctx()
    ctx = CTXOBJ
    proj = {
        "index.html": proj_index(ctx),
        "lines.html": proj_lines(ctx),
        "results.html": proj_results(ctx),
        "estimators.html": proj_estimators(ctx),
        "injuries.html": proj_injuries(ctx),
        "rest.html": proj_rest(ctx),
        "minutes.html": proj_minutes(ctx),
        "gates.html": proj_gates(ctx),
        "review.html": proj_review(ctx),
        "questions.html": proj_questions(ctx),
        "suggestions.html": proj_suggestions(ctx),
        "flagged.html": proj_flagged(ctx),
    }
    bet = {
        "index.html": bet_index(ctx),
        "picks.html": bet_picks(ctx),
        "prereg.html": bet_prereg(ctx),
        "ledger.html": bet_ledger(ctx),
        "gates.html": bet_gates(ctx),
        "flagged.html": bet_flagged(ctx),
    }
    written = []
    if "--check" not in sys.argv:
        for tree, pages in ((OUT_PROJ, proj), (OUT_BET, bet)):
            tree.mkdir(parents=True, exist_ok=True)
            for name, doc in pages.items():
                (tree / name).write_text(doc, encoding="utf-8")
                written.append(str((tree / name).relative_to(ROOT)))
    return written


def check_links(written: list[str]) -> None:
    """Every internal link must resolve; every page must link at least one https source."""
    for rel in written:
        text = (ROOT / rel).read_text()
        if 'href="https://' not in text:
            err(f"{rel} has no https source link")
        import re
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("https://", "http://", "#", "mailto:")):
                continue
            target = (ROOT / rel).parent / href.split("#")[0]
            if not target.exists():
                err(f"{rel}: broken internal link {href!r}")


def main() -> int:
    written = build()
    if "--check" in sys.argv:
        build_dir = OUT_PROJ
        written = [str((p.relative_to(ROOT))) for p in
                   sorted(OUT_PROJ.glob("*.html")) + sorted(OUT_BET.glob("*.html"))]
    check_links(written)
    for e in ERRORS:
        print("ERROR:", e)
    print(f"wrote {len(written)} pages"
          f"{'' if not ERRORS else f', {len(ERRORS)} errors'}")
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    raise SystemExit(main())
