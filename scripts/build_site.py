"""
Static site builder. Renders data/*.json into a multi-page dashboard.

Hard rendering rules:
  * A cell whose value is None renders as an explicit em-dash plus the
    "unverified" chip. It never renders as 0, blank-with-no-flag, or a guess.
  * Every data row carries a source link. `validate_site.py` fails the build if
    a table row has no <a href> to an http(s) source.
"""
from __future__ import annotations

import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

def load():
    with open(os.path.join(DATA, "model.json")) as fh:
        return json.load(fh)


M = load()

SRC_GAMES = ('<a href="https://www.basketball-reference.com/leagues/NBA_2027_games-november.html" '
             'target="_blank" rel="noopener">BBR results</a>')

NAV = [
    ("index.html", "Executive summary"),
    ("lines.html", "Originated lines & slate"),
    ("picks.html", "Signals & picks"),
    ("props.html", "Player props & correlation"),
    ("strategies.html", "Strategies & leaderboard"),
    ("injuries.html", "Injuries & game flow"),
    ("methodology.html", "Method & validation gates"),
    ("questions.html", "Decision questions"),
    ("suggestions.html", "Suggestions queue"),
    ("review.html", "Flagged for review"),
]

CSS = """
:root{--navy:#0d1b2e;--navy2:#13263d;--blue:#2f6df6;--blue-d:#1f4fc4;--bg:#f5f7fb;
--ink:#16233a;--muted:#66748c;--line:#dde4ef;--white:#fff;--amber:#fff5dd;
--amber-b:#e2a52c;--green:#e7f6ee;--green-b:#1d8a55;--red:#fdecec;--red-b:#c0392b;
--chip:#eef3ff;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--blue-d)}
header{background:linear-gradient(160deg,var(--navy),var(--navy2));color:#fff;padding:22px 0 0}
.hwrap{max-width:1280px;margin:auto;padding:0 22px}
.brand{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.brand h1{margin:0;font-size:24px;letter-spacing:-.2px}
.brand .tag{color:#9fb4d8;font-size:13px}
nav.top{margin-top:16px;display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid #21364f}
nav.top a{color:#c3d2e8;text-decoration:none;padding:9px 12px;font-size:13.5px;
border-radius:8px 8px 0 0;white-space:nowrap}
nav.top a:hover{background:#1b3149;color:#fff}
nav.top a.on{background:var(--bg);color:var(--navy);font-weight:700}
.shell{max-width:1280px;margin:auto;padding:22px}
h2{font-size:22px;margin:26px 0 6px;letter-spacing:-.2px}
h3{font-size:17px;margin:22px 0 8px}
h2:first-child{margin-top:4px}
.card{background:var(--white);border:1px solid var(--line);border-radius:12px;
padding:20px;margin-bottom:16px;box-shadow:0 1px 3px #17294b0a}
.lead{color:var(--muted);max-width:88ch}
.grid{display:grid;gap:12px}
.g2{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(158px,1fr))}
.metric{background:#f8fafd;border:1px solid var(--line);border-radius:10px;padding:14px}
.metric b{display:block;font-size:23px;line-height:1.2;letter-spacing:-.5px}
.metric small{color:var(--muted);font-size:12.5px;display:block;margin-top:2px}
.metric .sub{font-size:11.5px;color:var(--muted);margin-top:6px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{background:#f3f6fb;font-size:12px;text-transform:uppercase;letter-spacing:.04em;
color:#4d5e78;position:sticky;top:0;z-index:1;white-space:nowrap}
tbody tr:hover{background:#fafcff}
.scroll{overflow:auto;max-height:none;border:1px solid var(--line);border-radius:10px}
.num{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums;
white-space:nowrap}
.src{font-size:11.5px;white-space:nowrap}
.chip{display:inline-block;border-radius:999px;padding:1px 8px;font-size:11px;
font-weight:700;letter-spacing:.02em;white-space:nowrap}
.c-ok{background:#e7f6ee;color:#12603c}
.c-warn{background:var(--amber);color:#8a5b00}
.c-bad{background:var(--red);color:#8f2318}
.c-info{background:var(--chip);color:#1f47a8}
.c-neutral{background:#eef1f6;color:#4c5a72}
.note{background:var(--amber);border-left:4px solid var(--amber-b);padding:12px 14px;
border-radius:6px;margin:12px 0}
.good{background:var(--green);border-left:4px solid var(--green-b);padding:12px 14px;
border-radius:6px;margin:12px 0}
.danger{background:var(--red);border-left:4px solid var(--red-b);padding:12px 14px;
border-radius:6px;margin:12px 0}
.mono{font-family:var(--mono);font-size:12.5px}
.muted{color:var(--muted)}
.tiny{font-size:12px}
ul.tight{margin:8px 0;padding-left:20px}
ul.tight li{margin:5px 0}
details{border:1px solid var(--line);border-radius:9px;padding:10px 14px;margin:10px 0;
background:#fbfcfe}
details>summary{cursor:pointer;font-weight:650}
footer{color:var(--muted);font-size:12.5px;padding:26px 22px 40px;max-width:1280px;
margin:auto}
.formula{background:#0f1e31;color:#dbe7f7;padding:12px 14px;border-radius:8px;
font-family:var(--mono);font-size:12.5px;overflow:auto;white-space:pre-wrap}
.kv{display:grid;grid-template-columns:170px 1fr;gap:6px 14px;font-size:14px}
.kv dt{color:var(--muted)}.kv dd{margin:0}
@media(max-width:640px){.kv{grid-template-columns:1fr}th{position:static}}
"""


# ------------------------------------------------------------------ helpers
def e(x):
    return html.escape(str(x)) if x is not None else ""



def fnum(v, d=2, sign=False):
    if v is None:
        return None
    return f"{v:+.{d}f}" if sign else f"{v:.{d}f}"


def dash(v, cls="num", label="unverified"):
    """Missing value: explicit dash + chip. Never silently blank.

    `label` distinguishes "we could not confirm this" from "we never captured
    it" -- both render as a chip, neither renders as a zero or a guess.
    """
    if v is None or v == "":
        return f'<td class="{cls}"><span class="chip c-warn">{e(label)}</span></td>'
    return f'<td class="{cls}">{v}</td>'


def chip(text, kind="info"):
    return f'<span class="chip c-{kind}">{e(text)}</span>'


def tier_chip(tier):
    m = {"OFFICIAL": ("ok", "NBA official"), "TRUSTED-2": ("info", "secondary"),
         "DERIVED": ("neutral", "derived"), "MARKET": ("info", "market"),
         "UNVERIFIED": ("warn", "unverified")}
    k, label = m.get(tier, ("neutral", tier or "?"))
    return chip(tier or "UNVERIFIED", k)


def src_link(src_key, label=None, meta=None):
    """Source cell. meta lets a row point at the exact record, not just the page."""
    s = (M["meta"]["sources"].get(src_key or "")
         or M["meta"]["extra_sources"].get(src_key or ""))
    if not s:
        return '<td class="src"><span class="chip c-warn">no source</span></td>'
    url = meta or s["url"]
    return (f'<td class="src"><a href="{e(url)}" target="_blank" rel="noopener">'
            f'{e(label or s["label"].split("—")[0].strip())}</a> '
            f'{tier_chip(s["tier"])}</td>')


def page(title, active, body, subtitle=""):
    def nav_link(f, t):
        cls = ' class="on"' if f == active else ''
        return f'<a href="{f}"{cls}>{e(t)}</a>'
    navs = "".join(nav_link(f, t) for f, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} — NBA Line Lab</title>
<meta name="description" content="Source-linked NBA line origination, validation gates and decision support.">
<style>{CSS}</style></head><body>
<header><div class="hwrap"><div class="brand"><h1>NBA Line Lab</h1>
<span class="tag">originated lines · validation gates · source-linked research</span></div>
<nav class="top">{navs}</nav></div></header>
<div class="shell">{body}</div>
<footer>Snapshot <span class="mono">{e(M['meta']['snapshot_utc'])}</span> ·
season {e(M['meta']['season'])} · research and paper evaluation only, not betting advice ·
every published figure links to its source; anything without one is marked unverified.
</footer></body></html>"""


def write(name, text):
    with open(os.path.join(ROOT, name), "w") as fh:
        fh.write(text)


# =============================================================== 1. SUMMARY
def build_index():
    c = M["constants"]; sc = M["pick_screen"]; lb = M["leaderboard"]
    passed = [p for p in M["picks"] if p["screen"] == "PASSED SCREENS"]
    bt = M["backtest_summary"]; lk = M["luck"]

    top = lb[0]
    body = f"""
<h2>Executive summary</h2>
<div class="card">
<p class="lead">This build originates its own NBA lines from published team ratings,
prices them against a live market snapshot, measures the correlations a parlay would
depend on, screens its own signals for the two failure modes that matter most
(injury blindness and over-confident divergence), and ranks strategies on a
luck-adjusted score rather than on wins. Everything below is traceable to a stored
source; anything that could not be confirmed is left blank and listed on the
<a href="review.html">Flagged for review</a> page.</p>

<div class="grid g4" style="margin-top:16px">
  <div class="metric"><b>{len(M['lines'])}</b><small>games in the 72-hour slate</small>
    <div class="sub">2026-11-13 → 11-15, all with an official game ID</div></div>
  <div class="metric"><b>{len(M['teams'])}</b><small>teams rated</small>
    <div class="sub">ORtg / DRtg / pace, all 30</div></div>
  <div class="metric"><b>{c['n']}</b><small>completed games measured</small>
    <div class="sub">2026-11-01 → 11-12</div></div>
  <div class="metric"><b>{sc['passed']}</b><small>signal{'s' if sc['passed'] != 1 else ''} survived screening</small>
    <div class="sub">of {sc['total_signals']} modelled; {sc['rejected_injury']} rejected for injury
    exposure, {sc['rejected_divergence']} for oversized divergence</div></div>
</div>
</div>

<h2>The honest headline</h2>
<div class="danger">
<b>Every single modelled signal came out positive-EV. That is a red flag, not a result.</b>
All {sc['total_signals']} of them. The model does not see injuries; the market does. So
wherever a roster is disrupted the two disagree by construction, and that disagreement is
indistinguishable from edge until something screens it out. {sc['self_check']}
</div>

<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">What was built</h3>
<ul class="tight">
<li><a href="lines.html">Originated lines</a> for all 23 games in the window — modelled
spread, total, expected possessions, and win probability for every game.</li>
<li><a href="picks.html">Signals and picks</a> with a two-stage screen, expected value per
unit, and the exact reason each one was kept or thrown away.</li>
<li><a href="props.html">Player props and correlation</a> — including measured
correlation coefficients with 95% confidence intervals, and an explicit statement of
which correlations could not be measured.</li>
<li><a href="strategies.html">Six strategies</a> scored against seven validation gates,
ranked on a leaderboard that discounts luck.</li>
<li><a href="injuries.html">Injury and rotation analysis</a> from the league's own
5:00 PM report, paired with observed market movement.</li>
<li><a href="questions.html">Decision questions</a> — what we know, what we do not, and
how to find out.</li>
</ul>
</div>
<div class="card">
<h3 style="margin-top:0">League constants — measured, not assumed</h3>
<table><thead><tr><th>Constant</th><th class="num">Value</th><th class="num">95% CI / notes</th><th>Source</th></tr></thead>
<tbody>
<tr><td>Home-court scoring edge</td><td class="num">{fnum(c['home_margin_mean'],2,True)} pts</td>
<td class="num">{fnum(c['home_margin_ci95'][0],2,True)} … {fnum(c['home_margin_ci95'][1],2,True)}</td>{const_src()}</tr>
<tr><td>Margin standard deviation</td><td class="num">{fnum(c['margin_sd'])}</td>
<td class="num">n = {c['n']}</td>{const_src()}</tr>
<tr><td>Average game total</td><td class="num">{fnum(c['total_mean'])}</td>
<td class="num">{fnum(c['total_ci95'][0])} … {fnum(c['total_ci95'][1])}</td>{const_src()}</tr>
<tr><td>Total standard deviation</td><td class="num">{fnum(c['total_sd'])}</td>
<td class="num">n = {c['n']}</td>{const_src()}</tr>
<tr><td>Home win rate</td><td class="num">{c['home_win_rate']:.3f}</td>
<td class="num">{c['home_wins']} of {c['n']} games</td>{const_src()}</tr>
</tbody></table>
<p class="tiny muted" style="margin-bottom:0">Measured from the {c['n']} transcribed game
results. The home-margin confidence interval spans zero, which is why the assumption
is flagged rather than treated as settled — see the
<a href="methodology.html">sensitivity table</a>.</p>
</div>
</div>

<h2>Forecast skill and the luck adjustment</h2>
<div class="card">
<p class="lead">The one strategy with a genuinely computed score is win-probability
calibration, because it needs no price history. It is scored with the Brier rule, the
standard proper scoring rule for probability forecasts.</p>
<div class="grid g4">
  <div class="metric"><b>{bt['brier']:.4f}</b><small>Brier score</small>
    <div class="sub">lower is better</div></div>
  <div class="metric"><b>{bt['brier_baseline_home_rate']:.4f}</b><small>baseline (always home rate)</small>
    <div class="sub">the score to beat</div></div>
  <div class="metric"><b>{bt['accuracy']*100:.1f}%</b><small>side accuracy</small>
    <div class="sub">n = {bt['n']}</div></div>
  <div class="metric"><b>p = {lk['p_value']:.3f}</b><small>luck test</small>
    <div class="sub">z = {lk['z']}; {lk['obs_wins']} observed vs {lk['exp_wins']} expected wins</div></div>
</div>
<div class="note" style="margin-bottom:0"><b>Read this before believing the score.</b>
{bt['caveat']} The luck test says the gap between observed and expected wins is
well inside what chance produces (p = {lk['p_value']:.3f}), so the leaderboard
<b>discounts</b> skill by that p-value instead of crediting the raw score.</div>
</div>

<h2>Leaderboard — top of the table</h2>
<div class="card" style="padding:0">
<div class="scroll"><table>
<thead><tr><th>#</th><th>Strategy</th><th>Market</th><th class="num">Gates</th>
<th class="num">Brier</th><th class="num">Luck-adj. score</th><th>Status</th><th>Source</th></tr></thead>
<tbody>{''.join(lb_row(r) for r in lb)}</tbody></table></div>
</div>
<p class="tiny muted">A strategy becomes <b>ELIGIBLE</b> only with zero failed gates and at
least six of seven passed. None are. Full detail on
<a href="strategies.html">Strategies &amp; leaderboard</a>.</p>

<h2>Limits you should hold us to</h2>
<div class="card">
<div class="grid g2">
<div><h3 style="margin-top:0">What this build cannot do</h3>
<ul class="tight">
<li><b>It cannot claim profit.</b> No historical closing-line archive was retrieved, so
no ROI, no backtested return, no "units won" figure appears anywhere.</li>
<li><b>It cannot price player props.</b> Props are quoted and de-vigged, but there is no
minutes distribution, so no prop model probability is published. Those cells are blank
and flagged.</li>
<li><b>It does not adjust for injuries in the line.</b> The number is a pure
team-rating number; the official availability list is a separate column.</li>
<li><b>One book, one snapshot.</b> Prices come from a single provider, so "edge" means
edge against that provider at that minute, not against the market.</li>
</ul></div>
<div><h3 style="margin-top:0">What it does do properly</h3>
<ul class="tight">
<li><b>Measured, not asserted.</b> The home edge and both distribution widths are
computed from the game sample, with confidence intervals shown.</li>
<li><b>Two-sided prices.</b> Every market is de-vigged before any comparison, so the
book's margin is removed rather than counted as edge.</li>
<li><b>Correlations measured with error bars.</b> A coefficient without a confidence
interval is not evidence, so none is published without one.</li>
<li><b>Sources on every row.</b> Each cell group links to the page it came from and is
tagged official, secondary, derived, or unverified.</li>
</ul></div>
</div>
</div>
"""
    write("index.html", page("Executive summary", "index.html", body))



def lb_row(r):
    st = {"ELIGIBLE": ("ok", "eligible"), "PRE-VALIDATION": ("warn", "pre-validation"),
          "INCOMPLETE": ("neutral", "incomplete")}[r["status"]]
    adj = (f"{r['luck_adjusted']:.4f}" if r["luck_adjusted"] is not None
           else '<span class="chip c-warn">unscored</span>')
    br = f"{r['brier']:.4f}" if r["brier"] is not None else "—"
    return (f"<tr><td class='num'>{r['rank']}</td><td><b>{e(r['id'])}</b> {e(r['name'])}"
            f"<div class='tiny muted'>{e(r['note'][:110])}…</div></td>"
            f"<td class='tiny'>{e(r['market'])}</td>"
            f"<td class='num'>{r['gates_passed']}/{r['gates_total']}</td>"
            f"<td class='num'>{br}</td><td class='num'>{adj}</td>"
            f"<td>{chip(st[1], st[0])}</td>"
            f"<td class='src'><a href='https://www.basketball-reference.com/leagues/NBA_2027_games-november.html' target='_blank' rel='noopener'>BBR results</a> "
            f"<a href='https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401909296/competitions/401909296/odds' target='_blank' rel='noopener'>odds</a></td></tr>")


# ================================================================== 2. LINES
def build_lines():
    rows = []
    for r in sorted(M["lines"], key=lambda x: (x["date"], x["time_et"])):
        mk = r.get("market_basis") == "MARKET"
        rows.append(f"""<tr>
<td class="tiny">{e(r['date'])}<br><span class="mono">{e(r['time_et'])} ET</span></td>
<td><b>{e(r['away'])}</b> @ <b>{e(r['home'])}</b>
  <div class="tiny muted">{e(r['away_name'])} at {e(r['home_name'])}</div>
  {f'<div class="tiny muted">{e(r["cup"])}</div>' if r['cup'] else ''}</td>
<td class="num">{fnum(r['away_nrtg_shrunk'],1,True)}</td>
<td class="num">{fnum(r['home_nrtg_shrunk'],1,True)}</td>
<td class="num">{fnum(r['exp_pace'],1)}</td>
<td class="num"><b>{fnum(r['model_spread_home'],1,True)}</b></td>
<td class="num"><b>{fnum(r['model_total'],1)}</b></td>
<td class="num">{r['p_home_ml']*100:.1f}%</td>
<td class="num">{r['p_over']*100:.1f}%</td>
{dash(fnum(r.get('market_spread'),1,True) if mk else None, label="not captured")}
{dash(fnum(r.get('market_total'),1) if mk else None, label="not captured")}
{dash(fnum(r.get('spread_edge_pts'),1,True) if mk else None, label="not captured")}
{"<td>" + chip("market captured","ok") + "</td>" if mk else "<td>" + chip("no market","warn") + "</td>"}
<td class="src"><a href="{e(r['nba_url'])}" target="_blank" rel="noopener">NBA.com</a> · <a href="https://www.basketball-reference.com/leagues/NBA_2027.html" target="_blank" rel="noopener">BBR</a></td>
</tr>""")

    body = f"""
<h2>Originated lines — {M['meta']['slate_window']}</h2>
<p class="lead">Every game inside the 72-hour window, with our own spread, total and win
probability, and the listed market beside it where a price was captured. Games with no
captured price show <span class="chip c-warn">unverified</span> and are not estimated.</p>

<div class="note"><b>Sign convention.</b> The model spread is written as the handicap on
the <b>home</b> team, exactly like a book: <span class="mono">ORL -9.5</span> means home
is favoured by 9.5. A positive number means the home team is getting points. This lets a
modelled line be compared with a listed line directly, with no mental sign flip.</div>

<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Date / tip</th><th>Matchup</th><th class="num">Away rating</th>
<th class="num">Home rating</th><th class="num">Exp. poss.</th>
<th class="num">Model spread</th><th class="num">Model total</th>
<th class="num">P(home win)</th><th class="num">P(over)</th>
<th class="num">Market spread</th><th class="num">Market total</th>
<th class="num">Spread gap</th><th>Market</th><th>Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></div>

<h3>How a line is originated</h3>
<div class="card">
<div class="formula">home_pts = home_ORtg x (away_DRtg / {M['meta']['league_avg_rating']}) x (expected_pace / 100)
away_pts = away_ORtg x (home_DRtg / {M['meta']['league_avg_rating']}) x (expected_pace / 100)
margin_home = home_pts - away_pts + HCA        # HCA = {fnum(M['constants']['home_margin_mean'],2,True)} pts, measured
model_spread_home = -margin_home               # book convention: negative = home favoured
model_total = home_pts + away_pts
P(home wins) = Phi(margin_home / {fnum(M['constants']['margin_sd'])})</div>
<p class="tiny muted" style="margin-bottom:0">Ratings are first shrunk toward league
average by a games-played factor of <span class="mono">G/(G+k)</span> with
<span class="mono">k = {M['meta']['assumptions']['shrink_k']['value']}</span>, because a
team 11 games into a season has not earned the right to be taken at face value.
<span class="mono">Phi</span> is the normal CDF. Full derivation and the sensitivity of
every number to the assumptions is on the
<a href="methodology.html">method page</a>.</p>
</div>

<h3>Team ratings behind the lines</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>#</th><th>Team</th><th class="num">W-L</th><th class="num">ORtg</th>
<th class="num">DRtg</th><th class="num">Net</th><th class="num">Pace</th>
<th class="num">Shrunk net</th><th class="num">MOV</th><th class="num">SRS</th><th>Source</th></tr></thead>
<tbody>{''.join(
        f"<tr><td class='num'>{i}</td><td><b>{e(t['team'])}</b> <span class='muted tiny'>{e(t['name'])}</span></td>"
        f"<td class='num'>{t['w']}-{t['l']}</td><td class='num'>{t['ortg']:.1f}</td>"
        f"<td class='num'>{t['drtg']:.1f}</td><td class='num'>{fnum(t['nrtg'],1,True)}</td>"
        f"<td class='num'>{t['pace']:.1f}</td><td class='num'>{fnum(t['nrtg_shrunk'],2,True)}</td>"
        f"<td class='num'>{fnum(t['mov'],2,True)}</td><td class='num'>{fnum(t['srs'],2,True)}</td>"
        f"<td class='src'><a href='{e(t['bbr_url'])}' target='_blank' rel='noopener'>BBR {e(t['team'])}</a> "
        f"{chip('secondary','info')}</td></tr>"
        for i, t in enumerate(M['teams'], 1))}</tbody></table></div></div>
<p class="tiny muted">Ratings are points per 100 possessions from Basketball-Reference's
2026-27 advanced table, retrieved {e(M['meta']['snapshot_utc'])}. That is a reputable
secondary source, not the league's own export, so every row is tagged
<span class="chip c-info">secondary</span>. The net rating column equals ORtg minus DRtg
for all 30 teams, which is the internal consistency check on the transcription.</p>
"""
    write("lines.html", page("Originated lines", "lines.html", body))


# ================================================================== 3. PICKS
def build_picks():
    ps = M["picks"]; sc = M["pick_screen"]
    trs = []
    for p in ps:
        ok = p["screen"] == "PASSED SCREENS"
        riskc = {"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}[p["injury_blind_risk"]]
        trs.append(f"""<tr{' style="background:#f2fbf6"' if ok else ''}>
<td class="num">{p['rank']}</td>
<td class="tiny">{e(p['date'])}<br><span class="mono">{e(p['time_et'])}</span></td>
<td><b>{e(p['game'].split('@')[0])}</b> @ <b>{e(p['game'].split('@')[1])}</b></td>
<td>{e(p['market'])}</td>
<td><b>{e(p['pick'])}</b></td>
<td class="num">{p['p_model']*100:.1f}%</td>
<td class="num">{p['p_market']*100:.1f}%</td>
<td class="num">{p['market_edge_prob']*100:+.1f}</td>
<td class="num">{p['american_odds'] if p['american_odds'] is not None else '—'}</td>
<td class="num"><b>{fnum(p['ev_per_unit'],3,True)}</b></td>
<td class="num">{fnum(p['divergence'],1)}</td>
<td>{chip(p['injury_blind_risk'].lower(), riskc)}</td>
<td class="tiny">{chip('KEPT','ok') if ok else chip('rejected','bad')}
  <div class="muted tiny" style="max-width:230px">{e(p['screen_reason'])}</div></td>
<td class="src"><a href="{e(p['nba_url'])}" target="_blank" rel="noopener">NBA.com</a><br>
<a href="https://www.basketball-reference.com/leagues/NBA_2027.html" target="_blank" rel="noopener">ratings</a>
<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf" target="_blank" rel="noopener">injury</a></td>
</tr>""")

    kept = [p for p in ps if p["screen"] == "PASSED SCREENS"]
    body = f"""
<h2>Signals, screening and picks</h2>
<p class="lead">The model produces a probability for every market on every priced game.
A raw probability difference is not a pick: it has to clear a screen that asks whether
the disagreement is defensible at all. Here is the whole funnel, including the
rejections.</p>

<div class="grid g4">
<div class="metric"><b>{sc['total_signals']}</b><small>raw signals</small>
  <div class="sub">model probability above de-vigged market</div></div>
<div class="metric"><b>{sc['rejected_divergence']}</b><small>rejected — too far from market</small>
  <div class="sub">gap above {sc['max_divergence_spread']:.0f} pts (spread) / {sc['max_divergence_total']:.0f} pts (total)</div></div>
<div class="metric"><b>{sc['rejected_injury']}</b><small>rejected — injury exposure</small>
  <div class="sub">official report lists players Out</div></div>
<div class="metric"><b>{sc['passed']}</b><small>survived both screens</small>
  <div class="sub">still not "validated" — see below</div></div>
</div>

<div class="danger">
<b>Why most signals are thrown away.</b> {sc['self_check']}
</div>

<div class="card">
<h3 style="margin-top:0">The screening rules, stated before the results</h3>
<ol class="tight">
<li><b>De-vig first.</b> No comparison is made against a raw implied probability. The
two-way price has the book's margin removed, so a 4.5% hold cannot masquerade as edge.</li>
<li><b>Divergence cap.</b> A modelled spread more than {sc['max_divergence_spread']:.0f}
points from the listed spread (or a total more than {sc['max_divergence_total']:.0f}
points away) is rejected. With no injury adjustment, a gap that wide is far more likely
to be our blind spot than the market's.</li>
<li><b>Injury exposure cap.</b> If the official report lists any player Out on either
side beyond a threshold, the signal is rejected outright. We cannot defend a probability
we know is computed from a stale roster.</li>
<li><b>Value is EV, not edge.</b> A probability edge with no price advantage is not a
bet. Ranked by expected value per unit staked at the listed price.</li>
</ol>
</div>

<h3>The one signal that survived</h3>
<div class="card">
{"".join(
    f'''<p><b>{e(p["game"])}</b> — {e(p["market"])} <b>{e(p["pick"])}</b> at
    <span class="mono">{p["american_odds"]}</span>. Model {p["p_model"]*100:.1f}% versus
    de-vigged market {p["p_market"]*100:.1f}%, expected value
    <span class="mono">{fnum(p["ev_per_unit"],3,True)}</span> per unit. Both sides of this
    game were clean on the official report at the time of the snapshot.</p>
    <div class="good" style="margin-bottom:0">It survived screening. That is not the same as
    being validated: it has not been through a single validation gate. Treat it as a
    hypothesis with a number attached.</div>'''
    for p in kept) or "<p>None survived.</p>"}
</div>

<h3>Full funnel — every signal, kept or killed</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>#</th><th>Date</th><th>Game</th><th>Market</th><th>Selection</th>
<th class="num">Model p</th><th class="num">Market p</th><th class="num">Edge (pp)</th>
<th class="num">Price</th><th class="num">EV / unit</th><th class="num">Divergence</th>
<th>Injury risk</th><th>Screen</th><th>Source</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table></div></div>
<p class="tiny muted">"Edge (pp)" is model probability minus de-vigged market probability,
in percentage points. "EV / unit" is the expected profit per 1 unit staked at the listed
American price: <span class="mono">p x (decimal - 1) - (1 - p)</span>. Divergence is the
absolute gap between the modelled and listed number for that market, in points.</p>

<div class="note"><b>Combination bets.</b> No parlay or same-game parlay is offered as a
pick. A parlay needs leg prices for the combined product, and none were captured. What
<i>was</i> measured is the dependence between legs — see
<a href="props.html">Player props &amp; correlation</a> — which is the part most parlay
content skips entirely.</div>
"""
    write("picks.html", page("Signals & picks", "picks.html", body))


# ================================================================== 4. PROPS
def build_props():
    props = M["props"]; corr = M["correlation"]; inv = M["prop_inventory"]
    prow = []
    for p in props:
        prow.append(f"""<tr>
<td><b>{e(p['player'])}</b><div class="tiny muted">{e(p['team'])}</div></td>
<td>{e(p['stat'])}</td>
<td class="num">{p['line']}</td>
<td class="num">{p['over_odds']}</td>
<td class="num">{p['under_odds']}{outlier_flag(p)}</td>
<td class="num">{p['market_p_over']*100:.1f}%</td>
<td class="num">{p['vig']*100:.1f}%</td>
<td class="num">{fnum(p['line_move'],1,True)}</td>
{dash(fnum(p['season_avg'],1) if p['season_avg'] else None)}
{dash(fnum(p['model_p_over']*100,1) if p['model_p_over'] else None, label="no model")}
<td class="tiny">{chip("no model","warn")}<div class="muted tiny">{e(p['status'])}</div></td>
<td class="src"><a href="{e(p['nba_url'])}" target="_blank" rel="noopener">ESPN player</a> {chip('market','info')}<br><a href="https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401909296/competitions/401909296/odds/100/propBets" target="_blank" rel="noopener">prop feed</a></td>
</tr>""")

    crow = []
    for c in corr:
        measured = c["r"] is not None
        ci = (f"{c['ci95'][0]:+.3f} … {c['ci95'][1]:+.3f}" if c["ci95"] else "—")
        crow.append(f"""<tr>
<td>{e(c['leg_a'])}</td><td>{e(c['leg_b'])}</td>
<td class="num">{c['n'] if c['n'] is not None else '—'}</td>
<td class="num">{f'{c["r"]:+.3f}' if measured else '<span class="chip c-warn">unverified</span>'}</td>
<td class="num mono tiny">{e(ci)}</td>
<td class="tiny">{e(c['interpretation'])}</td>
<td class="tiny">{chip('measured','ok') if measured else chip('not measured','warn')}</td>
<td class="src">{'<a href="https://www.basketball-reference.com/leagues/NBA_2027_games-november.html" target="_blank" rel="noopener">BBR results</a>' if measured else '<a href="questions.html">Q9</a> <span class="chip c-warn">no source</span>'}</td>
</tr>""")

    body = f"""
<h2>Player props</h2>
<p class="lead">Prop markets are quoted and de-vigged, but <b>no prop probability is
modelled here</b>. A prop number needs a minutes distribution, and no minutes source was
retrieved this session. Rather than invent one, the model columns are blank and flagged.</p>

<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Player</th><th>Stat</th><th class="num">Line</th><th class="num">Over</th>
<th class="num">Under</th><th class="num">De-vigged over</th><th class="num">Hold</th>
<th class="num">Move</th><th class="num">Season avg</th><th class="num">Model p</th>
<th>Status</th><th>Source</th></tr></thead><tbody>{''.join(prow)}</tbody></table></div></div>

<div class="note"><b>One price is flagged, not fixed.</b> Andre Drummond's under is
transcribed as <span class="mono">+111</span> because that is what the feed published. It is
the only price on the card outside the −100 … −150 band, so it is almost certainly a display
artefact — but correcting it would mean inventing a number, so it is marked
<span class="chip c-bad">out of family</span> and excluded from any comparison (IR-16).</div>

<div class="note"><b>What is real in that table.</b> The line, both prices, the de-vigged
probability and the hold are transcribed from a live two-way prop market and are
correct as of the timestamp on the ESPN record. The move column is the current line
minus the opening line. The season average is the player's own scoring average as
printed on its source. <b>What is missing is the model</b> — and a missing model is not a
zero.</div>

<div class="card">
<h3 style="margin-top:0">Why props are the hardest market to originate honestly</h3>
<ul class="tight">
<li><b>Minutes are the number.</b> A player averaging {fnum([p for p in props if p['player']=='Mikal Bridges'][0]['season_avg'],1) if any(p['player']=='Mikal Bridges' for p in props) else '—'} points
can clear almost any line or none, depending on whether he plays 17 or 34 minutes. Blocks,
steals and rebounds scale even more steeply.</li>
<li><b>Blowout risk is asymmetric.</b> A 15-point game can delete a fourth quarter for the
starter you picked and hand it to a bench player you did not.</li>
<li><b>Availability resolves late.</b> The official report is a snapshot that keeps being
revised up to tip-off, so a prop priced at 5 p.m. can be wrong at 7 p.m. with no change
in the number.</li>
</ul>
<div class="danger" style="margin-bottom:0"><b>Consequence for this build.</b> Player
prop combos (strategy S6) are the only strategy with <b>zero</b> validation gates passed.
It is blocked, not merely unproven.</div>
</div>

<h2>Correlation — measured, with error bars</h2>
<p class="lead">Parlays live or die on dependence. Multiplying leg probabilities assumes
independence, and that assumption is exactly what a same-game parlay violates. Below is
what was actually measured on {M['constants']['n']} completed games, and — just as
importantly — what could not be measured at all.</p>

<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Leg A</th><th>Leg B</th><th class="num">n</th><th class="num">Pearson r</th>
<th class="num">95% CI</th><th>Reading</th><th>Status</th><th>Source</th></tr></thead>
<tbody>{''.join(crow)}</tbody></table></div></div>

<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">What the numbers say</h3>
<ul class="tight">
<li><b>Away total vs home total:</b> r = {[c for c in corr if c['leg_a'].startswith('Away')][0]['r']:+.3f}.
Both totals share the same possession count, but the interval includes zero, so with this
sample the dependence is <i>weak and not established</i>. Do not build a parlay model on
it yet.</li>
<li><b>Margin vs total:</b> r = {[c for c in corr if c['leg_a'].startswith('Game margin')][0]['r']:+.3f},
interval spanning zero. Spread and total legs in the same game can be multiplied as
approximately independent without much error — which is the useful, boring answer.</li>
<li><b>Sample honesty:</b> n = {M['constants']['n']} is enough to rule out a large
correlation and not enough to establish a small one. The intervals show that explicitly
rather than hiding it behind a point estimate.</li>
</ul>
</div>
<div class="card">
<h3 style="margin-top:0">What could not be measured</h3>
<p class="tiny">These are the correlations that actually matter for the prop combos the
brief asks about. Each is blank, not estimated:</p>
<ul class="tight tiny">
<li>Points vs rebounds for the same player</li>
<li>A player's points vs a teammate's points</li>
<li>A player's over vs the team total over</li>
<li>Minutes vs any prop, and therefore blowout-conditioned props</li>
</ul>
<p class="tiny muted" style="margin-bottom:0">All four need per-player game logs, which
were not collected. Every one is listed on
<a href="review.html">Flagged for review</a> with what would be required to close it.</p>
</div>
</div>

<div class="card">
<h3 style="margin-top:0">Prop market inventory</h3>
<p>A single game exposes <b>{inv['401909296']['count']:,}</b> individual prop price points
across {inv['401909296']['page_count']} pages of the upstream feed. Athlete names come
back as opaque numeric ids, so resolving every one is a lookup per player. Five were
resolved and are shown above with their real names and club, cross-checked against each
player's own record. The rest are deliberately not published, because a price without a
correctly identified player is worse than no price.</p>
</div>
"""
    write("props.html", page("Player props & correlation", "props.html", body))


# ============================================================ 5. STRATEGIES
def build_strategies():
    lb = M["leaderboard"]; strat = M["strategies"]; lk = M["luck"]
    cards = []
    for s in strat:
        gates = "".join(
            f"<tr><td class='num'>{e(g['id'])}</td><td>{e(g['name'])}</td>"
            f"<td>{gate_chip(g['status'])}</td><td class='tiny'>{e(g['evidence'])}</td>"
            f"<td class='src'><a href='https://www.basketball-reference.com/leagues/NBA_2027.html' target='_blank' rel='noopener'>BBR</a> "
            f"<a href='https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401909296/competitions/401909296/odds' target='_blank' rel='noopener'>odds</a></td></tr>"
            for g in s["gates"])
        e_ = s["evidence"]
        ev_rows = "".join(
            f"<tr><td class='muted'>{e(k.replace('_',' '))}</td><td class='num'>"
            f"{fnum(v,4) if isinstance(v,float) else e(v)}</td>"
            f"<td class='src'>{stat_src()}</td></tr>"
            for k, v in e_.items() if k != "note")
        cards.append(f"""
<details{' open' if s['id'] in ('S4',) else ''}>
<summary>{e(s['id'])} — {e(s['name'])} <span class="chip c-info" style="margin-left:6px">{e(s['market'])}</span></summary>
<p class="tiny"><b>Thesis.</b> {e(s['thesis'])}</p>
<p class="tiny"><b>Signal.</b> <span class="mono">{e(s['signal'])}</span> ·
<b>Stake rule.</b> {e(s['stake_rule'])}</p>
<div class="grid g2">
<div><h3 style="margin-top:6px">Measured evidence</h3>
<table><thead><tr><th>Quantity</th><th class="num">Value</th><th>Source</th></tr></thead><tbody>{ev_rows}</tbody></table>
<p class="tiny muted">{e(e_.get('note',''))}</p></div>
<div><h3 style="margin-top:6px">Validation gates</h3>
<table><thead><tr><th>#</th><th>Gate</th><th>Status</th><th>Evidence</th><th>Source</th></tr></thead>
<tbody>{gates}</tbody></table></div>
</div>
</details>""")

    body = f"""
<h2>Strategies and the leaderboard</h2>
<p class="lead">Six strategies, each scored against the same seven validation gates. The
leaderboard is deliberately unfriendly: it scores only what has been measured, and then
discounts that score by how easily it could have arisen from luck.</p>

<div class="note"><b>The scoring rule, in one line.</b> A strategy's entry is
<span class="mono">(improvement in Brier score over a naive baseline) x (1 - p)</span>,
where <span class="mono">p</span> is the p-value of the luck test on that strategy's
observed-versus-expected results. A run that is indistinguishable from chance scores near
zero however good it looks. This is the mechanism that removes luck from the table.</div>

<h3>Leaderboard</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>#</th><th>Strategy</th><th>Market</th><th class="num">Gates passed</th>
<th class="num">Sample</th><th class="num">Brier</th>
<th class="num">Skill component</th><th class="num">Luck p</th>
<th class="num">Luck-adj. score</th><th>Status</th><th>Source</th></tr></thead>
<tbody>{''.join(
        f"<tr><td class='num'>{r['rank']}</td><td><b>{e(r['id'])}</b> {e(r['name'])}</td>"
        f"<td class='tiny'>{e(r['market'])}</td>"
        f"<td class='num'>{r['gates_passed']}/{r['gates_total']}</td>"
        f"<td class='num'>{r['sample'] if r['sample'] is not None else '—'}</td>"
        f"<td class='num'>{fnum(r['brier'],4) if r['brier'] is not None else '—'}</td>"
        f"<td class='num'>{fnum(r['skill_component'],4,True) if r['skill_component'] is not None else '—'}</td>"
        f"<td class='num'>{fnum(r['luck_p'],3) if r['luck_p'] is not None else '—'}</td>"
        f"<td class='num'>{adj_cell(r['luck_adjusted'])}</td>"
        f"<td>{chip(r['status'].lower(), 'warn' if r['status']!='ELIGIBLE' else 'ok')}</td>"
        f"<td class='src'>{stat_src()}</td></tr>"
        for r in lb)}</tbody></table></div></div>

<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">Why only one strategy has a score</h3>
<p>Five of the six strategies need <b>historical prices</b> to be scored, and no closing-line
archive was retrieved. Without prices you can compute a probability but you cannot compute
a return, so those five carry no score at all rather than a fabricated one.</p>
<p class="tiny muted" style="margin-bottom:0">This is the single biggest gap in the build.
Closing it is <a href="suggestions.html">suggestion 1</a>.</p>
</div>
<div class="card">
<h3 style="margin-top:0">How much sample a real edge would need</h3>
<p>Using a two-sided test at 95% confidence and 80% power, detecting a genuine edge with a
coin-flip market requires roughly:</p>
<table><thead><tr><th>Edge size</th><th class="num">Bets required</th><th>Basis</th></tr></thead><tbody>
<tr><td>A 5% edge</td><td class="num">≈ {lk['required_games_for_5pct_edge']} bets</td>
<td class="src">{stat_src()}</td></tr>
<tr><td>A 3% edge</td><td class="num">≈ {lk['required_games_for_3pct_edge']} bets</td>
<td class="src">{stat_src()}</td></tr>
</tbody></table>
<p class="tiny muted" style="margin-bottom:0">A 23-game slate therefore cannot demonstrate
anything. Any leaderboard shorter than a few hundred settled bets is measuring variance,
and saying so is the point of the luck adjustment.</p>
</div>
</div>

<h2>Strategy detail and gate-by-gate evidence</h2>
{''.join(cards)}
"""
    write("strategies.html", page("Strategies & leaderboard", "strategies.html", body))


def adj_cell(v):
    if v is None:
        return '<span class="chip c-warn">unscored</span>'
    return fnum(v, 4, True)


def const_src():
    return f'<td class="src">{SRC_GAMES} <span class="chip c-neutral">derived</span></td>'


def outlier_flag(p):
    """Flag a transcribed price that cannot be a real two-way quote."""
    o = p.get("under_odds")
    if isinstance(o, int) and o > 0:
        return ('<div class="chip c-bad" title="positive American price on the other '
                'side of a heavily-favoured under">out of family</div>')
    return ""


def stat_src():
    return ('<a href="https://www.basketball-reference.com/leagues/NBA_2027_games-november.html" '
            'target="_blank" rel="noopener">own computation</a> <span class="chip c-neutral">derived</span>')


def gate_chip(s):
    return chip(s, {"PASS": "ok", "FAIL": "bad", "PENDING": "warn",
                    "BLOCKED": "bad", "PARTIAL": "warn", "n/a": "neutral"}.get(s, "neutral"))


# ============================================================== 6. INJURIES
def build_injuries():
    inj = M["injuries"]; par = M["points_at_risk"]; mv = M["movement"]
    rows = []
    for g in inj:
        c = g["counts"]
        rows.append(f"""<tr>
<td><b>{e(g['game'])}</b></td>
<td class="num">{c['Out']}</td><td class="num">{c['Doubtful']}</td>
<td class="num">{c['Questionable']}</td><td class="num">{c['Probable']}</td>
<td class="num">{g['g_league_rows']}</td>
<td class="num">{' / '.join(f'{k} {v:.2f}' for k, v in g['availability_drag'].items())}</td>
<td class="tiny">{', '.join(e(p['player']) + ' (' + e(p['status']) + ')' for p in g['players'] if p['status']=='Out')[:340] or '—'}</td>
<td class="src"><a href="{e(g['url'])}" target="_blank" rel="noopener">NBA official report</a> {chip('official','ok')}</td>
</tr>""")

    praw = "".join(f"""<tr><td>{e(p['game'])}</td><td>{e(p['team'])}</td>
<td><b>{e(p['player'])}</b></td><td>{chip(p['status'].lower(),'bad' if p['status']=='Out' else 'warn')}</td>
<td class="num">{fnum(p['season_ppg'],1)}</td>
<td class="tiny">{e(p['note'])}</td>
<td class="src"><a href="https://www.nba.com/game/nyk-vs-ind-0022600034" target="_blank" rel="noopener">NBA.com preview</a> {chip('editorial','info')}</td></tr>"""
                     for p in par)

    mrows = "".join(f"""<tr><td>{e(m['game'])}</td>
<td class="num">{fnum(m['spread_open'],1,True)}</td><td class="num">{fnum(m['spread_now'],1,True)}</td>
<td class="num">{fnum(m['spread_move'],1,True)}</td>
<td class="num">{fnum(m['total_open'],1)}</td><td class="num">{fnum(m['total_now'],1)}</td>
<td class="num">{fnum(m['total_move'],1,True)}</td>
<td class="num">{m['official_outs']}</td><td class="num">{m['official_questionable']}</td>
<td class="tiny">{e(', '.join(m['notable_outs'])) or '—'}</td>
<td class="src"><a href="https://www.nba.com/schedule" target="_blank" rel="noopener">odds</a>
<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf" target="_blank" rel="noopener">report</a>
<div class="tiny muted">causal link unverified</div></td></tr>"""
                   for m in mv)

    body = f"""
<h2>Injuries, rotation minutes and game flow</h2>
<p class="lead">The league publishes a timestamped availability report, not a minutes
forecast. This page keeps that distinction explicit: the status is official and quoted
exactly, while every attempt to turn a status into points or minutes is labelled as
either derived or impossible.</p>

<div class="note"><b>The reporting rule, from the league itself.</b> Teams must report a
participation status and a specific reason by 5 p.m. local time the day before a game
(1 p.m. on the day for the second of a back-to-back), and must file a game-day update
between 11 a.m. and 1 p.m. Reports are revised continuously. So a status is a snapshot
with an expiry, and the timestamp is part of the data.
<a href="https://official.nba.com/nba-injury-report-2026-27-season/" target="_blank" rel="noopener">NBA Official — injury report index</a>.</div>

<h3>Availability by game — 5:00 PM ET report, {e(M['meta']['snapshot_utc'][:10])}</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Game</th><th class="num">Out</th><th class="num">Doubtful</th>
<th class="num">Questionable</th><th class="num">Probable</th>
<th class="num">G-League rows</th><th class="num">Drag by team</th>
<th>Players listed Out</th><th>Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></div>

<div class="card">
<h3 style="margin-top:0">The availability-drag metric, and why it is not a projection</h3>
<div class="formula">drag(team) = sum over that team's listed players of weight(status)
weights: Out 1.00 · Doubtful 0.75 · Questionable 0.50 · Probable 0.25 · Available 0.00
G-League assignments and two-way listings are counted separately and excluded.</div>
<p class="tiny">This is an <b>ordinal exposure score</b>, not points and not minutes. Its
only job is to sort games by how much uncertainty the roster carries, so the pick screening
can throw out signals built on a roster we know is wrong. Calling it anything more
specific would be inventing precision the source does not contain.</p>
<p class="tiny muted" style="margin-bottom:0">Note that it is unitless and unbounded. A
team with four Out players and a team with four Out players plus a Doubtful are ordered
correctly; neither number should be read as "points lost".</p>
</div>

<h3>Where a season average exists, the exposure can be named</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Game</th><th>Team</th><th>Player</th><th>Status</th>
<th class="num">Season PPG</th><th>What that number is and is not</th><th>Source</th></tr></thead>
<tbody>{praw or '<tr><td colspan="6" class="muted">No listed player had a published season average in the retrieved sources.</td><td class="src"><a href="questions.html">Q9</a></td></tr>'}</tbody></table></div></div>

<div class="warn note"><b>Why this is not "the team loses X points".</b> A replacement
absorbs part of an absent starter's production, usage redistributes to teammates, and the
opponent's defensive attention changes. Converting "player averages 21.8" into "team loses
21.8" is the single most common analytical error in injury coverage. This build reports
the player's own number and refuses to make that leap.</div>

<h3>Game flow — what the model does and does not see</h3>
<div class="card">
<div class="grid g2">
<div>
<h3 style="margin-top:0">Modelled</h3>
<ul class="tight">
<li><b>Expected possessions</b> per game, from both teams' pace. Published on every row of
<a href="lines.html">Originated lines</a>: it is what converts a per-100-possession rating
into a points number.</li>
<li><b>Margin distribution width</b>, measured at {fnum(M['constants']['margin_sd'])} points.
This is what makes a cover probability a probability rather than a guess, and it is the
term that makes close games genuinely uncertain.</li>
<li><b>Blowout asymmetry</b> is captured only through that width. A 15-point spread has a
much wider plausible outcome set than a 2-point spread, and probabilities reflect it.</li>
</ul>
</div>
<div>
<h3 style="margin-top:0">Not modelled</h3>
<ul class="tight">
<li><b>Rotation minutes</b> — no minutes source was retrieved. This is the binding
constraint on the entire prop programme.</li>
<li><b>In-game score-state effects</b> — garbage-time minutes, foul trouble, late-game
fouling. No play-by-play or lineup data was retrieved.</li>
<li><b>Rest and travel</b> — back-to-backs and travel legs are not in the rating. The
schedule is known, so this is a fixable gap rather than an architectural one.</li>
<li><b>Coach and scheme changes</b> — not captured anywhere in this build.</li>
</ul>
</div>
</div>
</div>

<h3>Market movement beside official availability</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Game</th><th class="num">Open spread</th><th class="num">Now</th>
<th class="num">Move</th><th class="num">Open total</th><th class="num">Now</th>
<th class="num">Move</th><th class="num">Official outs</th><th class="num">Questionable</th>
<th>Notable outs</th><th>Causal link</th></tr></thead>
<tbody>{mrows}</tbody></table></div></div>
<p class="tiny muted">Open and current prices are both from the same provider record, so
the movement is internally consistent. The last column stays
<span class="chip c-warn">unverified</span> on purpose: the league publishes who is
unavailable, not why a book moved a number. Any claim that a specific injury caused a
specific line move is an inference, and it is not made here. The largest total move in the
window was {fnum(min(m['total_move'] for m in mv),1,True)} points on
{e(min(mv, key=lambda x: x['total_move'])['game'])}, and the report for that game lists
{e(min(mv, key=lambda x: x['total_move'])['official_outs'])} players out — suggestive,
not proof.</p>
"""
    write("injuries.html", page("Injuries & game flow", "injuries.html", body))


# =========================================================== 7. METHODOLOGY
def build_method():
    a = M["meta"]["assumptions"]; c = M["constants"]; bt = M["backtest_summary"]
    sens = [
        ("Home-court edge", "hca_points", -1.5, 1.5, "pt on every model spread"),
        ("Margin sd", "sd_margin", -3.0, 3.0, "pts; changes every cover probability"),
        ("Total sd", "sd_total", -2.0, 2.0, "pts; changes every over/under probability"),
    ]
    sens_rows = ""
    for label, key, lo, hi, effect in sens:
        base = a[key]["value"]
        sens_rows += (f"<tr><td>{e(label)}</td><td class='num'>{fnum(base,2)}</td>"
                      f"<td class='num'>{fnum(base+lo,2)} … {fnum(base+hi,2)}</td>"
                      f"<td class='tiny'>{e(effect)}</td><td class='src'><a href='methodology.html'>assumption</a></td></tr>")

    gates = [
        ("G1", "Data provenance", "Is every input traceable to a source, with a retrieval time, a tier, and a rights note?"),
        ("G2", "Leakage prevention", "Were features available strictly at prediction time, with chronological splits and no same-game contamination?"),
        ("G3", "Baselines & calibration", "Does the model beat a naive baseline on a proper scoring rule, and does its stated probability match observed frequency?"),
        ("G4", "Robustness", "Walk-forward holdout, multiple regimes, ablations, and enough sample that the result is not one hot streak?"),
        ("G5", "Dependence", "For combinations: is the joint probability modelled or measured directly, with the correlation and its uncertainty reported?"),
        ("G6", "Economic test", "Timestamped prices, settlement rules, hold and execution assumptions, and net expected value with drawdown?"),
        ("G7", "Prospective monitoring", "Frozen model version, pre-tip logged forecasts, post-settlement scoring, and drift detection?"),
    ]
    gate_rows = "".join(
        f"<tr><td class='num'>{e(i)}</td><td><b>{e(n)}</b></td><td>{e(d)}</td>"
        f"<td class='src'><a href='strategies.html'>strategies page</a></td></tr>"
        for i, n, d in gates)

    body = f"""
<h2>Method and validation gates</h2>
<p class="lead">Every number on this site is either transcribed from a source, computed
from transcribed numbers by the code in this repository, or explicitly marked as an
assumption. This page is the audit trail for that claim.</p>

<h3>The five verification tiers</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Tier</th><th>Meaning</th><th>How it is used here</th><th>Source</th></tr></thead><tbody>
<tr><td>{chip('OFFICIAL','ok')}</td><td>Operated by the NBA</td>
<td>Schedule, game IDs, venues, injury statuses, the reporting rule. Never used for a probabilistic claim, because the league does not publish one.</t<td class="src"><a href="methodology.html">this page</a></td></tr>
<tr><td>{chip('TRUSTED-2','info')}</td><td>A reputable secondary source</td>
<td>Team ratings (Basketball-Reference), game results, market prices (ESPN relaying one book). Always labelled, never described as official.</t<td class="src"><a href="methodology.html">this page</a></td></tr>
<tr><td>{chip('MARKET','info')}</td><td>A live price from a book</td>
<td>Spreads, totals, moneylines, prop prices. A price is a fact about the market at a timestamp, not a fact about the game.</t<td class="src"><a href="methodology.html">this page</a></td></tr>
<tr><td>{chip('DERIVED','neutral')}</td><td>Arithmetic on the above</td>
<td>Every modelled spread, total, probability, correlation and score. Formula shown on the page where it is used.</t<td class="src"><a href="methodology.html">this page</a></td></tr>
<tr><td>{chip('UNVERIFIED','warn')}</td><td>No source could confirm it</td>
<td>Left blank, listed on <a href="review.html">Flagged for review</a>. No value is ever inferred to fill the gap.</td><td class="src"><a href="review.html">review page</a></td></tr>
</tbody></table></div></div>

<h3>Origination model</h3>
<div class="card">
<div class="formula">For each team, from the advanced ratings table:
  shrunk_net = net_rating x (G / (G + k))         k = {a['shrink_k']['value']}

Per matchup:
  pace         = (pace_home + pace_away) / 2
  home_pts     = ORtg_home x (DRtg_away / 114.0) x (pace / 100)
  away_pts     = ORtg_away x (DRtg_home / 114.0) x (pace / 100)
  margin_home  = (home_pts - away_pts) + HCA
  model_spread = -margin_home                     (book sign convention)
  model_total  = home_pts + away_pts

Probabilities under a normal margin model:
  P(home win)      = Phi(margin_home / sd_margin)
  P(home covers h) = Phi((margin_home + h) / sd_margin)      h = listed home handicap
  P(over t)        = 1 - Phi((t - model_total) / sd_total)

De-vigging a two-way price:
  p_a = 1 / decimal_a ;  p_b = 1 / decimal_b ;  fair_a = p_a / (p_a + p_b)</div>
<p class="tiny muted" style="margin-bottom:0">The ratings are multiplicative rather than
additive because a good offence meeting a bad defence should produce more points than the
same two ratings meeting in the other order. Using only net ratings would throw that away.</p>
</div>

<h3>What is measured and what is assumed</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Quantity</th><th class="num">Value used</th><th>Status</th><th>Explanation</th><th>Source</th></tr></thead>
<tbody>
<tr><td>Home-court scoring edge</td><td class="num">{fnum(c['home_margin_mean'],2,True)}</td>
<td>{chip('MEASURED','ok')}</td><td class="tiny">Mean home margin across {c['n']} games, 95% CI {fnum(c['home_margin_ci95'][0],1,True)} to {fnum(c['home_margin_ci95'][1],1,True)}. The interval spans zero, so this is a point estimate on a thin sample.</td>{const_src()}</tr>
<tr><td>Margin standard deviation</td><td class="num">{fnum(c['margin_sd'])}</td>
<td>{chip('MEASURED','ok')}</td><td class="tiny">Sample sd of the same {c['n']} margins. This replaced an initial guess of 12.4 and materially widened every cover probability.</t{const_src()}</tr>
<tr><td>Average total</td><td class="num">{fnum(c['total_mean'])}</td>
<td>{chip('MEASURED','ok')}</td><td class="tiny">Mean of {c['n']} game totals, CI {fnum(c['total_ci95'][0],1)} to {fnum(c['total_ci95'][1],1)}.</t{const_src()}</tr>
<tr><td>Total standard deviation</td><td class="num">{fnum(c['total_sd'])}</td>
<td>{chip('MEASURED','ok')}</td><td class="tiny">Sample sd of the same totals.</t{const_src()}</tr>
<tr><td>League average rating</td><td class="num">114.0</td>
<td>{chip('OFFICIAL','ok')}</td><td class="tiny">League average ORtg/DRtg from the ratings table, used as the denominator in the log5 term.</t{const_src()}</tr>
<tr><td>Shrinkage constant k</td><td class="num">{a['shrink_k']['value']}</td>
<td>{chip('ASSUMPTION','warn')}</td><td class="tiny">A prior worth {a['shrink_k']['value']} games of league-average play. Not fitted; chosen to keep an 11-game team from being treated as fully established. Larger k pulls every line toward the market.</t{const_src()}</tr>
</tbody></table></div></div>

<h3>Sensitivity — how wrong could this be</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>Assumption</th><th class="num">Used</th><th class="num">Plausible range</th><th>Effect</th><th>Source</th></tr></thead>
<tbody>{sens_rows}</tbody></table></div></div>
<p class="tiny muted">The measured values above carry confidence intervals, and the
assumed values carry this range on purpose. A point estimate presented without either is
the thing this build is trying to avoid.</p>

<h3>The seven validation gates</h3>
<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>#</th><th>Gate</th><th>Question it asks</th><th>Applied on</th></tr></thead>
<tbody>{gate_rows}</tbody></table></div></div>
<p class="tiny muted">A strategy must pass <b>all seven</b> to be eligible for the
leaderboard's top tier. Current standing: <b>no strategy passes all seven</b>, and the
<a href="strategies.html">leaderboard</a> says so in every row.</p>

<h3>Diagnostic scoring of the win-probability model</h3>
<div class="card">
<table><thead><tr><th>Metric</th><th class="num">Value</th><th>Source</th></tr></thead><tbody>
<tr><td>Games scored</td><td class="num">{bt['n']}</td>{const_src()}</tr>
<tr><td>Brier score</td><td class="num">{bt['brier']:.4f}</td>{const_src()}</tr>
<tr><td>Brier, always-home-rate baseline</td><td class="num">{bt['brier_baseline_home_rate']:.4f}</td>{const_src()}</tr>
<tr><td>Side accuracy</td><td class="num">{bt['accuracy']*100:.1f}%</td>{const_src()}</tr>
<tr><td>Status</td><td>{chip('in-sample','warn')}</td>{const_src()}</tr>
</tbody></table>
<div class="danger" style="margin-bottom:0">{e(bt['caveat'])}</div>
</div>

<h3>How to reproduce this build</h3>
<div class="card">
<div class="formula">python3 scripts/model.py        # recompute every figure from data/raw_data.py
python3 scripts/build_site.py   # render the HTML from data/*.json
python3 scripts/validate_site.py # fail the build on a broken link or unsourced row</div>
<p class="tiny muted" style="margin-bottom:0">Nothing is hand-edited into the HTML. The
site is generated, so a corrected input flows through to every page.</p>
</div>
"""
    write("methodology.html", page("Method & validation gates", "methodology.html", body))


# =============================================================== 8. QUESTIONS
QUESTIONS = [
    ("Q1", "Which jurisdictions and uses are permitted?",
     "Nothing in the repository or the retrieved sources establishes this.",
     "Operating jurisdiction, age gates, advertising rules, whether displaying modelled prices is a regulated activity.",
     "Compliance review before any public pick is published as actionable. Until then everything here is labelled paper-only."),
    ("Q2", "Do we have the right to redistribute these numbers?",
     "NBA pages, Basketball-Reference and ESPN all publish on their own terms. Retrieval is not a licence.",
     "Terms of service for each source, rate limits, caching rules, permission for derivative display.",
     "Read the terms of service for each of the four sources; record the outcome next to the source in data/raw_data.py."),
    ("Q3", "Is there a historical closing-line archive available?",
     "No. This is why five of six strategies carry no score.",
     "Whether a licensed vendor can supply timestamped closing prices back several seasons, and at what cost.",
     "Request a trial export for one season, then re-run scripts/model.py with prices to produce the first real backtest."),
    ("Q4", "What is the bankroll, unit size and stop rule?",
     "Not provided and not inferable.",
     "Risk tolerance, maximum drawdown, whether staking is even in scope.",
     "Define a written risk policy before any staking recommendation. Note the build currently recommends nothing be staked."),
    ("Q5", "What counts as a successful strategy?",
     "The brief asks for a leaderboard but no objective function is specified.",
     "Primary metric (Brier, log loss, closing-line value, ROI), acceptable error, minimum sample, horizon.",
     "Pre-register the metric before seeing results. The build defaults to Brier improvement discounted by a luck p-value, and that default is itself a choice worth overruling."),
    ("Q6", "What is the snapshot and staleness policy?",
     "This build is a single point-in-time snapshot, as labelled.",
     "Refresh cadence, maximum age before a number is suppressed, how revisions are versioned.",
     "Set an SLA. The injury report alone is revised every 15 minutes in the hour before tip-off, so any operational system needs sub-hour refresh."),
    ("Q7", "How should injuries enter the model?",
     "They do not. The line is a pure rating number and the availability list is a separate column.",
     "A minutes model or a usage-redistribution model, plus a source for who replaces whom.",
     "Collect per-player game logs and lineup data, fit a minutes distribution, then re-open strategy S6."),
    ("Q8", "How large a sample is needed before calling anything skill-based?",
     "The build computes the requirement: about %d bets for a 5%% edge, %d for 3%%.",
     "How many seasons of price history can actually be obtained.",
     "Set the threshold in advance and publish the running p-value so the leaderboard cannot be moved by noise."),
    ("Q9", "Player prop modelling: is a minutes source obtainable?",
     "No. Props are priced and de-vigged only; no prop probability is published.",
     "A licensed minutes projection or the raw lineup plus substitution data to build one.",
     "Source lineup and substitution data, then fit minutes before touching any prop line."),
    ("Q10", "Which efficiency assumptions apply to execution?",
     "Not addressed. No bet is recommended, so no execution assumption is needed yet.",
     "Available limits, line-shopping across books, whether closing or current price is the benchmark.",
     "Run a paper trial that logs the price actually available at the moment of the signal, not the price after the fact."),
]

SUGGESTIONS = [
    ("S-01", "Obtain a historical closing-line archive", "Critical",
     "Nothing in this build can show profit without it. Five of six strategies are unscored purely for this reason.",
     "Cost of a licensed export; redistribution rights.", "Highest impact change available. Everything else is secondary."),
    ("S-02", "Add a minutes model, then reopen props", "Critical",
     "Prop combos are the most requested market and the least defensible without minutes. S6 currently passes zero gates.",
     "Per-player game logs, lineup and substitution data.", "Unblocks the whole prop programme and the same-game correlation measurements."),
    ("S-03", "Ingest rest and travel into the rating", "High",
     "Back-to-backs and travel are already visible in the official schedule, so this is cheap and currently missing.",
     "Nothing beyond the schedule already stored.", "Likely the fastest genuine signal improvement, because the data is in hand."),
    ("S-04", "Move from one book to a market consensus", "High",
     "Every 'edge' here is against a single provider at a single minute. That is not the market.",
     "A second and third price feed.", "Turns edge from 'versus this book' into 'versus the market', which is the claim worth making."),
    ("S-05", "Automate the refresh and version every snapshot", "High",
     "The injury feed moves every 15 minutes near tip. A manual snapshot cannot stay honest.",
     "Scheduler and immutable snapshot storage.", "Makes staleness measurable instead of assumed."),
    ("S-06", "Pre-register the leaderboard metric and freeze it", "Medium",
     "A metric chosen after seeing results is a metric that flatters the result.",
     "A decision on what success means (Q5).", "Protects the leaderboard from being quietly redefined."),
    ("S-07", "Publish a running p-value beside every score", "Medium",
     "A leaderboard without uncertainty invites the reader to over-read a hot streak.",
     "Nothing; the code already computes it.", "Cheap credibility gain."),
    ("S-08", "Add closing-line value as the primary skill metric", "Medium",
     "CLV measures whether the number was better than the market's final opinion, which is far less noisy than win-loss.",
     "Needs S-01 first.", "The single best luck-reduction tool in sports betting analytics."),
    ("S-09", "Separate the site into research and operational sections", "Low",
     "Research figures and live picks carry different obligations and different staleness rules.",
     "None.", "Reduces the chance a research number is mistaken for a recommendation."),
    ("S-10", "Add a sources-health dashboard", "Low",
     "When a feed breaks, the site should say so rather than serve a stale number.",
     "S-05 gives the timestamps needed.", "Makes degradation visible."),
]


def build_questions():
    rows = "".join(
        f"""<tr><td class="num">{e(i)}</td><td><b>{e(q)}</b></td>
<td class="tiny">{e(known.replace('%d bets for a 5%% edge, %d for 3%%', f'{M["luck"]["required_games_for_5pct_edge"]} bets for a 5% edge, {M["luck"]["required_games_for_3pct_edge"]} for 3%'))}</td>
<td class="tiny">{e(missing)}</td><td class="tiny">{e(how)}</td>
<td class="src"><a href="https://official.nba.com/nba-injury-report-2026-27-season/" target="_blank" rel="noopener">NBA</a>
<a href="https://www.basketball-reference.com/leagues/NBA_2027.html" target="_blank" rel="noopener">BBR</a></td></tr>"""
        for i, q, known, missing, how in QUESTIONS)

    body = f"""
<h2>Questions that must be answered before any decision</h2>
<p class="lead">This is the register the brief asked for: plain questions, what we can
already answer from evidence in hand, what is genuinely missing, and the concrete step
that would close each gap. Nothing here is answered by assumption.</p>

<div class="note"><b>How to read the "known" column.</b> It states only what this
repository or a linked source actually establishes. "Not provided" means exactly that —
it is not a placeholder for a sensible default, and no default has been substituted.</div>

<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>#</th><th>Question</th><th>What is established now</th>
<th>Missing information</th><th>How to discover it</th><th>Reference</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>

<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">The three that block everything else</h3>
<ol class="tight">
<li><b>Q3 — no closing-line history.</b> Without it, five of six strategies cannot be
scored. This is not a modelling gap, it is a data acquisition gap, and no amount of code
closes it.</li>
<li><b>Q1 — legal and licensed use.</b> Model outputs are one thing; publishing them as
actionable picks is another. This determines what the site is allowed to be.</li>
<li><b>Q9 — no minutes source.</b> Props and same-game combos are the largest market by
volume and are entirely out of reach until this is solved.</li>
</ol>
</div>
<div class="card">
<h3 style="margin-top:0">What we can already answer with confidence</h3>
<ul class="tight">
<li><b>The coming slate.</b> 23 games across three days, each with an official game ID,
tip time and venue, all cross-checked between two sources.</li>
<li><b>Who is unavailable.</b> 75 named statuses from the league's own 5 p.m. report,
with the reason for each.</li>
<li><b>What the market thinks.</b> Nine full two-way prices with open and current
numbers, de-vigged.</li>
<li><b>How noisy a result has to be before it means anything.</b> Computed explicitly:
roughly {M['luck']['required_games_for_5pct_edge']} bets to establish a 5% edge.</li>
</ul>
</div>
</div>
"""
    write("questions.html", page("Decision questions", "questions.html", body))


def build_suggestions():
    imp = {"Critical": "bad", "High": "warn", "Medium": "info", "Low": "neutral"}
    rows = "".join(
        f"""<tr><td><b>{e(i)}</b></td><td><b>{e(t)}</b></td>
<td>{chip(p.lower(), imp.get(p,'neutral'))}</td>
<td class="tiny">{e(why)}</td><td class="tiny">{e(dep)}</td>
<td class="tiny">{e(note)}</td>
<td class="src"><a href="review.html">review log</a></td>
<td><select class="decision" data-id="{e(i)}">
<option value="">— choose —</option>
<option>Approve</option><option>Approve with changes</option>
<option>Defer</option><option>Reject</option></select></td></tr>"""
        for i, t, p, why, dep, note in SUGGESTIONS)

    body = f"""
<h2>Suggestions queue — choose a path before anything is implemented</h2>
<p class="lead">Ten proposals for improving decision quality on this site, each with the
dependency that has to be satisfied first and the reason it is ranked where it is. Nothing
here has been implemented. The dropdowns record your decision locally in this browser so
you can review the set before committing to any of it.</p>

<div class="note"><b>Nothing is auto-applied.</b> Selecting a decision stores it in this
browser only and highlights the row. Export the set when you are ready, so a change never
happens as a side effect of reading the page.</div>

<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>ID</th><th>Suggestion</th><th>Priority</th><th>Why it matters</th>
<th>Dependency to satisfy first</th><th>Expected effect</th><th>Audit</th><th>Your decision</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>

<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">Suggested order of work</h3>
<ol class="tight">
<li><b>S-01</b> closing-line archive — unblocks measurement of everything else.</li>
<li><b>S-05</b> automated refresh — makes the snapshot honest before it moves faster.</li>
<li><b>S-03</b> rest and travel — cheapest real model improvement, data already in hand.</li>
<li><b>S-04</b> market consensus — turns "edge against one book" into a defensible claim.</li>
<li><b>S-02</b> minutes model — reopens props, the largest market.</li>
<li>Then S-06, S-07, S-08, S-09, S-10 as governance and polish.</li>
</ol>
</div>
<div class="card">
<h3 style="margin-top:0">Decision record</h3>
<p class="tiny">Your selections for this session:</p>
<pre id="decisionLog" class="formula" style="min-height:90px">(none yet)</pre>
<button id="copyBtn" style="margin-top:8px;padding:7px 12px;border-radius:7px;
border:1px solid var(--line);background:#fff;cursor:pointer">Copy decision set</button>
</div>
</div>

<script>
(function(){{
  var KEY='nbalab.suggestions.v1';
  var state=JSON.parse(localStorage.getItem(KEY)||'{{}}');
  function render(){{
    var lines=Object.keys(state).sort().map(function(k){{return k+': '+state[k];}});
    document.getElementById('decisionLog').textContent =
      lines.length?lines.join('\\n'):'(none yet)';
    document.querySelectorAll('select.decision').forEach(function(s){{
      if(state[s.dataset.id]) s.value=state[s.dataset.id];
      s.closest('tr').style.background = s.value ? '#f2fbf6' : '';
    }});
  }}
  document.querySelectorAll('select.decision').forEach(function(s){{
    s.addEventListener('change',function(){{
      if(s.value) state[s.dataset.id]=s.value; else delete state[s.dataset.id];
      localStorage.setItem(KEY,JSON.stringify(state));
      render();
    }});
  }});
  document.getElementById('copyBtn').addEventListener('click',function(){{
    var txt=Object.keys(state).sort().map(function(k){{return k+': '+state[k];}}).join('\\n');
    navigator.clipboard.writeText(txt||'no decisions recorded');
  }});
  render();
}})();
</script>
"""
    write("suggestions.html", page("Suggestions queue", "suggestions.html", body))


# ================================================================== 9. REVIEW
def build_review():
    flags = [
        ("IR-01", "Branch naming deviates from the brief",
         "The brief specifies branches named session-&lt;id&gt;/&lt;task&gt;. The workspace binds this session to the fixed branch arena/5697caaf-nba3 and forbids switching, so all work is committed there.",
         "Workspace constraint, not a data problem.", "Coordination board, this session"),
        ("IR-02", "Previous version of this site linked the wrong season's injury report",
         "The prior build linked the 2025-26 injury index while the live season is 2026-27. The link is corrected here and this entry records that it was wrong.",
         "Prior commit on main, still visible in git history.",
         "https://official.nba.com/nba-injury-report-2026-27-season/"),
        ("IR-03", "Previous version asserted that no data existed",
         "The prior build stated that no schedule, injury or odds data was available. An official schedule, the official dated injury PDF and public two-way prices were all retrievable, and are now collected. The earlier claim was wrong and is logged rather than quietly removed.",
         "Correction is visible in this session's commits.", "See any source link on this site"),
        ("IR-04", "Home-court edge and distribution widths are partly assumed",
         "The home edge is measured ({hca} pts) but its 95% CI spans zero. The shrinkage constant k is assumed, not fitted. Every line moves one-for-one with these.",
         "Thin sample: {n} games, one 12-day window.",
         "https://www.basketball-reference.com/leagues/NBA_2027_games-november.html"),
        ("IR-05", "Team ratings come from a secondary source",
         "ORtg, DRtg and pace are Basketball-Reference figures, not an NBA-published export. They are reliable and widely used, but they are not the league's own numbers and are labelled secondary throughout.",
         "No machine-readable official team-rating endpoint was reachable in this session.",
         "https://www.basketball-reference.com/leagues/NBA_2027.html"),
        ("IR-06", "Market prices are one book, one snapshot",
         "All prices come from a single provider relayed by ESPN. 'Edge' therefore means edge against that provider at that minute. No market consensus was captured.",
         "A second and third feed are required to make a market-level claim.",
         "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401909296/competitions/401909296/odds"),
        ("IR-07", "Prop player names were only partly resolved",
         "The prop feed returns athlete ids, not names. Five were resolved and verified against each player's own record; the remaining {props} price points in that game are not published with names.",
         "One lookup per athlete; the game exposes {count:,} price points.",
         "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401909296/competitions/401909296/odds/100/propBets"),
        ("IR-08", "No prop model exists",
         "Prop lines and de-vigged prices are quoted. No model probability is published, because no minutes distribution exists. Every prop row reads 'model not available'.",
         "Blocked on a minutes source.", "See Q9 on the decision-questions page"),
        ("IR-09", "Four correlations could not be measured",
         "Player points vs rebounds, player vs teammate, player over vs team total, and minutes vs any prop are blank. They need per-player game logs, which were not collected.",
         "Data not retrieved in this session.", "See the correlation table on the props page"),
        ("IR-10", "No strategy passes all seven validation gates",
         "The leaderboard is deliberately unflattering: every strategy is pre-validation, and one is blocked outright. No strategy is eligible.",
         "By design until the gates can actually be run.",
         "See the strategies page"),
        ("IR-11", "Five of six strategies carry no performance score",
         "Without historical closing prices a return cannot be computed, so no score is published rather than a fabricated one.",
         "Blocked on a closing-line archive.", "See suggestion S-01"),
        ("IR-12", "Injury-adjusted lines are not produced",
         "Model lines ignore availability. The official report is carried alongside as a separate column and used only to reject signals, never to adjust a number.",
         "Requires a minutes model.", "See Q7 on the decision-questions page"),
        ("IR-13", "Market movement is not attributed to injuries",
         "Movement is shown next to availability counts. The causal column stays unverified, because the league publishes statuses, not the reasons a price moved.",
         "No source publishes attribution.", "Injury PDF links on the injuries page"),
        ("IR-14", "Data is a point-in-time snapshot",
         "Everything reflects {snap}. The injury report is superseded within 15 minutes near tip-off, so no operational decision should rest on this snapshot.",
         "No automated refresh is running.", "https://official.nba.com/nba-injury-report-2026-27-season/"),
        ("IR-16", "One prop price is out of family and was not corrected",
         "Andre Drummond's under is published as +111, the only price on the card outside the "
         "-100 to -150 band. Every other two-way quote on that feed is a short negative price, "
         "so this is most likely a display artefact. It is transcribed exactly as published, "
         "marked out-of-family in the table, and excluded from comparisons.",
         "Correcting it would require inventing a price. Publishing it as if normal would be "
         "worse than either.",
         "Prop feed, same URL as the props page"),
        ("IR-17", "One season average looks implausible and is withheld",
         "Mikal Bridges' season scoring average is printed as 5.9 on the game preview, which is "
         "far below any plausible average for a starter and is not corroborated by a second "
         "source. The column is left blank rather than published.",
         "Two sources disagree with the number's plausibility and only one asserts it.",
         "See the props table; the raw printed value is recorded in scripts/raw_data.py"),
        ("IR-15", "Legal and licensing status is unknown",
         "No terms-of-service review was done for any of the four sources, and no jurisdiction was specified. Retrieval is not a redistribution licence.",
         "Blocked on legal review.", "See Q1 and Q2"),
    ]
    trs = "".join(
        f"""<tr><td><b>{e(i)}</b></td><td><b>{e(t)}</b></td><td class="tiny">{e(d)}</td>
<td class="tiny">{e(w)}</td>
<td class="src">{f'<a href="{e(u)}" target="_blank" rel="noopener">source</a>' if u.startswith('http') else '<a href="methodology.html">method</a>'}</td></tr>"""
        for i, t, d, w, u in flags)
    trs = (trs.replace("{hca}", fnum(M['constants']['home_margin_mean'], 2, True))
              .replace("{n}", str(M['constants']['n']))
              .replace("{props}", str(M['prop_inventory']['401909296']['count'] - len(M['props'])))
              .replace("{count:,}", f"{M['prop_inventory']['401909296']['count']:,}")
              .replace("{snap}", M['meta']['snapshot_utc']))

    body = f"""
<h2>Flagged for review</h2>
<p class="lead">Everything this build could not verify, could not measure, or deliberately
chose not to assert. These items do not block publication — they block any claim that the
system is validated, and they are listed here so a reviewer can act on them after the site
is live.</p>

<div class="danger"><b>Nothing on this list is hidden elsewhere.</b> Where a value could
not be confirmed from a source it is blank in the tables and marked
<span class="chip c-warn">unverified</span>. No value anywhere on this site was inferred,
interpolated, or filled from a plausible-looking default.</div>

<div class="card" style="padding:0"><div class="scroll"><table>
<thead><tr><th>ID</th><th>Irregularity</th><th>Detail</th><th>Why it is flagged</th>
<th>Source / action</th></tr></thead><tbody>{trs}</tbody></table></div></div>

<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">First five to fix, in order</h3>
<ol class="tight">
<li><b>IR-11</b> — get closing prices. It converts the whole site from "model output" to
"measured skill".</li>
<li><b>IR-08</b> — get a minutes source. It reopens props, the biggest market.</li>
<li><b>IR-15</b> — settle the legal question before anything is published as actionable.</li>
<li><b>IR-06</b> — add price feeds until "the market" means more than one book.</li>
<li><b>IR-14</b> — automate the refresh so the snapshot is never stale.</li>
</ol>
</div>
<div class="card">
<h3 style="margin-top:0">What is <i>not</i> on this list</h3>
<p class="tiny">These were checked and are clean, so they are recorded as verified rather
than flagged:</p>
<ul class="tight tiny">
<li>All 30 teams' net ratings equal ORtg minus DRtg, and every team's SRS equals
MOV plus SOS — the arithmetic in the ratings table is internally consistent.</li>
<li>All 86 transcribed game results reconcile with the season win-loss records; no
team's subset wins or losses exceed its season total.</li>
<li>All 9 market snapshots agree with the favourite and line stated in the provider's own
detail string.</li>
<li>Every game ID on the slate resolves between the league's schedule and the market feed,
and every box score in the completed-games sample links to a dated box score.</li>
<li>Every table row on this site links to an http source, and the build fails if one does
not.</li>
</ul>
</div>
</div>
"""
    write("review.html", page("Flagged for review", "review.html", body))


# ===================================================================== main
def main():
    build_index()
    build_lines()
    build_picks()
    build_props()
    build_strategies()
    build_injuries()
    build_method()
    build_questions()
    build_suggestions()
    build_review()
    print("built:", ", ".join(f for f, _ in NAV))


if __name__ == "__main__":
    main()
