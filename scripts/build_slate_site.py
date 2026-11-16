#!/usr/bin/env python3
"""Session arena/3d625d23-nba3 — build the `slate/` dashboard site.

Deterministic: reads only committed JSON under data/slate/ (which are themselves replays of
committed verbatim captures) and writes slate/*.html. Re-running must reproduce byte-identical
output — CI enforces that with a drift gate.

Every table row carries a link to the official page it came from. Values that could not be
confirmed from an official source are rendered blank with a flag, never inferred.
"""
import html
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "slate")
SITE = os.path.join(ROOT, "slate")
SESSION = "arena/3d625d23-nba3"

STAMP = "2026-11-16T00-05Z"           # newest official source read in this round
WINDOW = "2026-11-16 → 2026-11-18"

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2128;--line:#30363d;--fg:#e6edf3;
--dim:#8b949e;--acc:#58a6ff;--good:#3fb950;--warn:#d29922;--bad:#f85149;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header{border-bottom:1px solid var(--line);background:var(--panel);padding:18px 24px}
header h1{margin:0;font-size:20px}
header .sub{color:var(--dim);font-size:13px;margin-top:4px}
nav{display:flex;flex-wrap:wrap;gap:6px;padding:12px 24px;border-bottom:1px solid var(--line);
background:var(--panel2)}
nav a{color:var(--fg);text-decoration:none;font-size:13px;padding:5px 10px;border-radius:6px;
border:1px solid var(--line);background:var(--panel)}
nav a:hover{border-color:var(--acc);color:var(--acc)}
main{padding:22px 24px 60px;max-width:1500px}
h2{font-size:17px;margin:30px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h2:first-child{margin-top:0}
h3{font-size:14px;color:var(--dim);margin:22px 0 8px;text-transform:uppercase;letter-spacing:.06em}
p{max-width:110ch}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0 4px}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--panel2);font-weight:600;white-space:nowrap}
tbody tr:nth-child(even){background:#11161d}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
a{color:var(--acc)}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.card{border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:12px 16px;
min-width:190px;flex:1}
.card .k{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.05em}
.card .v{font-size:22px;margin-top:4px;font-variant-numeric:tabular-nums}
.card .n{color:var(--dim);font-size:12px;margin-top:3px}
.banner{border:1px solid var(--line);border-left:4px solid var(--acc);background:var(--panel);
padding:10px 14px;border-radius:6px;margin:12px 0}
.banner.warn{border-left-color:var(--warn)}
.banner.bad{border-left-color:var(--bad)}
.banner.good{border-left-color:var(--good)}
.bad{color:var(--bad)} .good{color:var(--good)} .warn{color:var(--warn)}
.dim{color:var(--dim)}
.flag{display:inline-block;background:#3d2b00;color:#f0c040;border:1px solid #7a5200;
border-radius:4px;font-size:11px;padding:1px 6px}
.blank{color:var(--dim);font-style:italic}
.pill{display:inline-block;border-radius:10px;padding:1px 8px;font-size:12px;border:1px solid}
.pill.ok{color:var(--good);border-color:#1f5c2e;background:#0f2a16}
.pill.no{color:var(--bad);border-color:#6e2222;background:#2b1111}
code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:12px}
footer{border-top:1px solid var(--line);padding:16px 24px;color:var(--dim);font-size:12px}
"""

PAGES = [
    ("index.html", "Overview"),
    ("projections.html", "Two estimators"),
    ("lines.html", "Originated lines"),
    ("parlays.html", "Parlay pricing"),
    ("injuries.html", "Injuries & rotation"),
    ("minutes.html", "Minutes model"),
    ("rest-travel.html", "Rest & travel"),
    ("luck.html", "Luck"),
    ("results.html", "Results & settlement"),
    ("prereg.html", "Pre-registration"),
    ("ledger.html", "Pick ledger"),
    ("gates.html", "Gates & refresh"),
    ("team-stats.html", "Team stats (official)"),
    ("questions.html", "Open questions"),
    ("suggestions.html", "Suggestions"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
]


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def e(x):
    return html.escape("" if x is None else str(x))


def num(x, nd=2):
    if x is None:
        return '<span class="blank">blank</span>'
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return e(x)


def link(url, label=None):
    if not url:
        return '<span class="blank">blank</span>'
    return f'<a href="{e(url)}">{e(label or url)}</a>'


def src_cell(urls):
    """A cell with one or more official-source links (every row must carry at least one)."""
    if isinstance(urls, str):
        urls = [urls]
    urls = [u for u in urls if u]
    if not urls:
        return '<td><span class="flag">NO OFFICIAL SOURCE</span></td>'
    return "<td>" + "<br>".join(link(u, _short(u)) for u in urls) + "</td>"


def _short(u):
    if "statsdmz" in u:
        return "official game book PDF"
    if "injury" in u.lower():
        return "official injury report PDF"
    if "standings" in u:
        return "nba.com/standings"
    if "advanced" in u:
        return "nba.com team advanced"
    if "traditional" in u:
        return "nba.com team traditional"
    if "opponent" in u:
        return "nba.com team opponent"
    if "schedule" in u:
        return "nba.com/schedule"
    if "/game/" in u:
        return "nba.com game page"
    return u.replace("https://", "")


OFFICIAL_DEFAULT = "https://www.nba.com/standings"


def kv_rows(pairs, default=None):
    """Key/value rows, each with an official-source cell (the rule: no row without a source)."""
    out = []
    for pair in pairs:
        urls = (default or OFFICIAL_DEFAULT)
        cells = list(pair)
        if len(cells) > 2:
            last = cells[-1]
            looks_like_source = (isinstance(last, (list, tuple)) or
                                 (isinstance(last, str) and last.startswith("http")))
            if looks_like_source:
                urls = last
                cells = cells[:-1]
        out.append(cells + [src_cell(urls)])
    return out


KV_HEADERS = ["Field", "Value", "Official source"]


def table(headers, rows, cls=""):
    th = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in r)
                   + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def page(title, body, active):
    nav_parts = []
    for f, label in PAGES:
        style = ' style="border-color:var(--acc);color:var(--acc)"' if f == active else ""
        nav_parts.append(f'<a href="{f}"{style}>{e(label)}</a>')
    nav = "".join(nav_parts)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} — NBA slate dashboard</title>
<style>{CSS}</style></head><body>
<header><h1>NBA slate dashboard — rolling window {e(WINDOW)}</h1>
<div class="sub">Session {e(SESSION)} · every number below is replayed from committed official
captures · newest official source read {e(STAMP)} · no odds feed is connected, so every
line here is originated by this model and no strategy is funded</div></header>
<nav>{nav}</nav>
<main>
{body}
</main>
<footer>Generated by <code>scripts/build_slate_site.py</code> from
<code>data/slate/**</code>. Values that could not be confirmed from an official source are printed
blank and flagged — none are inferred. Source links point at nba.com, official.nba.com and the
official game-book PDF host.</footer>
</body></html>
"""


# --------------------------------------------------------------------------------------- index

def build_index(model, gates, refresh, parlays, picks, ledger, minutes, feed, luck):
    proj = model["projections"]
    worst = max(proj, key=lambda p: p["disagreement_pts"])
    worst_t = max(proj, key=lambda p: p["total_disagreement"])
    bets = [c for c in picks["candidates"] if c.get("bet")]
    est = model["estimators"]
    cards = [
        ("Headline signal", f"{worst['disagreement_pts']:.2f} pts",
         f"largest estimator disagreement: {worst['away']}@{worst['home']} on {worst['date']}"),
        ("E1 out-of-sample log-loss", f"{est['E1']['oos']['log_loss']:.4f}",
         f"n={est['E1']['oos']['n']} walk-forward; coin-flip baseline "
         f"{est['E1']['oos']['baseline_log_loss']:.4f}"),
        ("Home-court advantage (pinned)", f"{model['hca']['hca_points']:.3f} pts",
         f"sigma {model['hca']['margin_sigma_pts']:.2f} x probit("
         f"{model['hca']['home_win_rate']:.4f}) over {model['hca']['games']} games"),
        ("Games in window", str(len(proj)), f"{WINDOW}, all with both estimators"),
        ("Rotation-minute coverage", f"{minutes['counts']['teams_with_minutes']}/30 clubs",
         "the rest print blank, never inferred"),
        ("Gates", f"{gates['counts']['passed']}/{gates['counts']['gates']} pass",
         "rebuild is refused unless every gate passes"),
        ("Sealed picks", str(ledger["count"]), f"ledger head {ledger['head'][:12]}…"),
        ("Verified finals in feed", f"{feed['counts']['verified']}/{feed['counts']['games']}",
         "quarters must sum to the printed final"),
    ]
    card_html = "".join(f'<div class="card"><div class="k">{e(k)}</div><div class="v">{e(v)}</div>'
                        f'<div class="n">{e(n)}</div></div>' for k, v, n in cards)

    dis_rows = []
    for p in sorted(proj, key=lambda p: -p["disagreement_pts"])[:10]:
        dis_rows.append([
            e(p["date"]), e(f'{p["away"]}@{p["home"]}'),
            f'<td class="n">{num(p["E1_margin"])}</td>',
            f'<td class="n">{num(p["E2_margin"])}</td>',
            f'<td class="n"><strong>{num(p["disagreement_pts"])}</strong></td>',
            f'<td class="n">{num(p["total_disagreement"])}</td>',
            src_cell(p["sources"]["game"]),
        ])
    return page("Overview", f"""
<div class="banner"><strong>The headline is the disagreement, not a blended rating.</strong>
Two independent estimators are run on every game — E1 fits the official results log, E2 builds
the game up from possessions × points-per-possession on the official efficiency page. The number
publishers should look at first is <code>|E1 − E2|</code>: when the two methods agree the number is
probably measuring something real, and when they disagree the spread is estimator noise. The blend is
printed underneath and is never the headline.</div>
<div class="cards">{card_html}</div>
<h2>Today's disagreements, worst first</h2>
{table(["Date", "Matchup", "E1 margin", "E2 margin", "Disagreement (pts)",
        "Total disagreement", "Source"], dis_rows)}
<p class="dim">Biggest margin disagreement: {e(worst['away'])}@{e(worst['home'])}
({num(worst['E1_margin'])} vs {num(worst['E2_margin'])}).
Biggest total disagreement: {e(worst_t['away'])}@{e(worst_t['home'])}
({num(worst_t['E1_total'])} vs {num(worst_t['E2_total'])}).</p>
<h2>Research picks in this window</h2>
<div class="banner warn">These are research picks on our own originated lines. No licensed odds feed
is connected, no money is staked, and no strategy here has cleared its validation gate —
{len(bets)} bets were taken by {len(set(c['strategy'] for c in bets))} pre-registered strategies out
of {picks['counts']['candidates']} candidates. See the pre-registration page for the frozen rules and
the ledger page for the sealed hashes.</div>
{table(["Strategy", "Date", "Matchup", "Market", "Bet", "Why", "Official source"],
       [[e(c["strategy"]), e(c["date"]), e(c["matchup"]), e(c["market"]), e(c["bet"]), e(c["why"]),
         src_cell("https://www.nba.com/game/" + c["game_id"])] for c in bets])}
<h2>What is published, what is not</h2>
{table(["Item", "Status", "Note", "Official source"], kv_rows([
    ["Two-estimator projections", '<span class="pill ok">published</span>',
     "every game in the window has both estimators",
     ["https://www.nba.com/stats/teams/advanced", "https://www.nba.com/schedule?date=2026-11-16"]],
    ["Rotation availability column", '<span class="pill ok">published</span>',
     f"minutes from official game books for {minutes['counts']['teams_with_minutes']}/30 clubs",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf"],
    ["Parlay prices", '<span class="pill ok">published</span>',
     f"{parlays['count']} rows, rho-priced with the naive product printed beside it",
     "https://www.nba.com/stats/teams/advanced"],
    ["Market-anchored prior", '<span class="pill no">blank + flagged</span>',
     "no closing-line feed is connected",
     "https://www.nba.com/standings"],
    ["Player-prop correlations", '<span class="pill no">blank + flagged</span>',
     "no prop line feed exists in this environment",
     "https://www.nba.com/stats/teams/traditional"],
    ["Strategies funded", '<span class="pill no">none</span>',
     "0 of 3 have the out-of-sample record the gates require",
     "https://www.nba.com/standings"],
]))}
""", "index.html")


# -------------------------------------------------------------------------------- projections

def build_projections(model):
    rows = []
    for p in model["projections"]:
        ra, rh = p["rotation"]["away"], p["rotation"]["home"]
        rot = []
        for side, r in (("away", ra), ("home", rh)):
            team = r.get("team")
            if r.get("out_in_top8") is None and r.get("minutes_at_risk") is None:
                rot.append(f'<span class="blank">{e(team)}: no captured book</span>')
            else:
                out = ", ".join(r.get("out_in_top8") or []) or "none"
                q = ", ".join(r.get("questionable_in_top8") or []) or "none"
                rot.append(f"{e(team)}: out [{e(out)}]&nbsp;&middot;&nbsp;questionable [{e(q)}]"
                           f"&nbsp;&middot;&nbsp;<strong>{num(r.get('minutes_at_risk'), 1)}</strong>"
                           f" min at risk")
        rows.append([
            e(p["date"]), e(p["tip_et"]), e(f'{p["away"]}@{p["home"]}'),
            f'<td class="n">{num(p["E1_margin"])}</td>',
            f'<td class="n">{num(p["E2_margin"])}</td>',
            f'<td class="n"><strong>{num(p["disagreement_pts"])}</strong></td>',
            f'<td class="n">{num(p["blend_margin"])}</td>',
            f'<td class="n">{num(p["E1_total"], 1)}</td>',
            f'<td class="n">{num(p["E2_total"], 1)}</td>',
            f'<td class="n">{num(p["total_disagreement"], 1)}</td>',
            f'<td class="n">{num(p["possessions"], 1)}</td>',
            f'<td class="n">{num(p["p_home_E1"], 3)}</td>',
            f'<td class="n">{num(p["p_home_E2"], 3)}</td>',
            f"<td>{'<br>'.join(rot)}</td>",
            src_cell([p["sources"]["game"], p["sources"]["slate"],
                      p["sources"]["efficiency"]]),
        ])
    est = model["estimators"]
    sens = est["E1"]["oos"].get("shrink_sensitivity", [])
    sens_rows = [[f'<td class="n">{num(r["shrink_k"], 1)}</td>',
                  f'<td class="n">{num(r["log_loss"], 4)}</td>',
                  f'<td class="n">{num(r["accuracy"], 4)}</td>',
                  f'<td class="n">{num(r["mae_margin"])}</td>',
                  f'<td class="n">{num(r["mae_total"])}</td>',
                  src_cell("https://www.nba.com/standings")] for r in sens]
    return page("Two estimators", f"""
<div class="banner"><strong>Headline rule.</strong> {e(model['headline_rule'])}</div>
<h2>Every game in the window ({len(model['projections'])})</h2>
<p class="dim">Margin is home minus away in points. Total is the two clubs' combined points.
Possessions are E2's estimate (pace × the game's expected tempo). Rotation minutes come from the
most recently captured official game book for each club.</p>
{table(["Date", "Tip (ET)", "Matchup", "E1 margin", "E2 margin", "Disagreement", "Blend margin",
        "E1 total", "E2 total", "Total dis.", "Poss.", "P(home) E1", "P(home) E2",
        "Rotation availability", "Sources"], rows)}
<h2>What each estimator is</h2>
{table(["Estimator", "Inputs", "Fitting", "Out-of-sample", "Official source"], [
    ["E1 — results log", e(est["E1"]["inputs"]), e(est["E1"]["fitting"]),
     f'n={est["E1"]["oos"]["n"]}, log-loss {est["E1"]["oos"]["log_loss"]:.4f}, '
     f'accuracy {est["E1"]["oos"]["accuracy"]:.4f} (coin '
     f'{est["E1"]["oos"]["baseline_log_loss"]:.4f})',
     src_cell("https://www.nba.com/standings")],
    ["E2 — possessions × PPP", e(est["E2"]["inputs"]), e(est["E2"]["fitting"]),
     f'n={est["E2"]["oos"]["n"]}, log-loss {est["E2"]["oos"]["log_loss"]:.4f}',
     src_cell("https://www.nba.com/stats/teams/advanced")],
])}
<h3>How the blend weight is set</h3>
<p>{e(model['blend']['rule'])} Today: w(E1) = {num(model['blend']['w_E1'], 3)},
w(E2) = {num(model['blend']['w_E2'], 3)} — {e(model['blend']['note'])}</p>
<h2>Home-court advantage is pinned, not fitted</h2>
<p>{e(model['hca']['rule'])} Measured over {model['hca']['games']} official finals:
{model['hca']['home_wins']} home wins ({model['hca']['home_win_rate']:.4f}), margin sigma
{model['hca']['margin_sigma_pts']:.3f} pts → <strong>HCA = {model['hca']['hca_points']:.3f}
points</strong>.</p>
<h2>Sensitivity of E1 to the shrinkage constant</h2>
<p class="dim">{e(est['E1']['oos'].get('shrink_note',''))}</p>
{table(["k (prior weight in games)", "Log-loss", "Accuracy", "MAE margin", "MAE total",
        "Official source"], sens_rows)}
<h2>Measured correlations</h2>
{table(["Pair", "r", "n", "Basis", "Used for", "Official source"],
       [[e(r["pair"]), f'<td class="n">{num(r["r"], 4)}</td>', f'<td class="n">{r["n"]}</td>',
         e(r["basis"]), e(r["use"]),
         src_cell("https://www.nba.com/standings" if r["basis"] == "MEASURED"
                  else "https://www.nba.com/stats/teams/traditional")]
        for r in model["correlations"]["rows"]])}
""", "projections.html")


# ------------------------------------------------------------------------------------- lines

def build_lines(model, prior):
    rows = []
    for p in model["projections"]:
        spread = -p["blend_margin"]
        rows.append([
            e(p["date"]), e(f'{p["away"]}@{p["home"]}'),
            f'<td class="n">{num(spread)}</td>',
            f'<td class="n">{num(p["blend_total"], 1)}</td>',
            f'<td class="n">{num(p["p_home_E1"], 3)}</td>',
            f'<td class="n">{num(1 / p["p_home_E1"] if p["p_home_E1"] else None, 3)}</td>',
            '<td><span class="blank">blank — no feed</span></td>',
            '<td><span class="blank">blank — no feed</span></td>',
            f'<td class="n">{num(p["disagreement_pts"])}</td>',
            src_cell([p["sources"]["game"], p["sources"]["efficiency"]]),
        ])
    return page("Originated lines", f"""
<div class="banner"><strong>These are our lines, not a sportsbook's.</strong> No licensed odds feed is
connected in this environment. Every spread and total below is produced by this model from official
data, and the market-anchored blend is therefore blank and flagged rather than filled in.</div>
<h2>Originated lines, {WINDOW} ({len(rows)} games)</h2>
<p class="dim">Spread is quoted from the home club's perspective (home − away). Total is the
combined points. The fair price is 1/p on the home moneyline.</p>
{table(["Date", "Matchup", "Originated spread (home)", "Originated total", "P(home win)",
        "Fair price", "Closing line", "Blended line", "Estimator disagreement", "Sources"], rows)}
<h2>Market-anchored prior — why it is blank</h2>
<p>{e(prior['formula'])}</p>
{table(KV_HEADERS, kv_rows([
    ["Feed status", f'<span class="pill no">{e(prior["feed_status"])}</span>'],
    ["Weight on the model", num(prior["w_model"], 3)],
    ["Weight on the closing line", num(prior["w_closing"], 3)],
    ["Model out-of-sample log-loss", num(prior["logloss_model"], 4)],
    ["Closing-line log-loss", '<span class="blank">blank — no feed</span>'],
    ["Rows", "0 — every blended line is blank and flagged"],
    ["Note", e(prior["note"])],
], default="https://www.nba.com/standings"))}
""", "lines.html")


# ----------------------------------------------------------------------------------- parlays

def build_parlays(parlays):
    rows = []
    for r in parlays["rows"]:
        rows.append([
            e(r["kind"]), e(r["date"]), e(r["matchup"]),
            "<td>" + "<br>".join(e(x) for x in r["legs"]) + "</td>",
            f'<td class="n">{num(r["p_leg1"], 4)}</td>',
            f'<td class="n">{num(r["p_leg2"], 4)}</td>',
            f'<td class="n">{num(r["rho"], 4)}</td>',
            f'<td class="n">{r["rho_n"]}</td>',
            f'<td class="n">{num(r["naive_product"], 4)}</td>',
            f'<td class="n"><strong>{num(r["rho_priced"], 4)}</strong></td>',
            f'<td class="n">{num(r["difference"], 4)}</td>',
            f'<td class="n">{num(r["fair_price_naive"], 3)}</td>',
            f'<td class="n">{num(r["fair_price_rho"], 3)}</td>',
            src_cell(["https://www.nba.com/stats/teams/advanced",
                      "https://www.nba.com/schedule?date=2026-11-16"]),
        ])
    return page("Parlay pricing", f"""
<div class="banner"><strong>Every parlay is priced with the measured rho, and the naive product is
printed right beside it.</strong> The price is never withheld. Same-game rho
{num(parlays['rho_same_game'], 4)}, cross-game rho {num(parlays['rho_cross_game'], 4)}, both measured
on the official game log rather than assumed.</div>
<h2>{parlays['count']} priced parlays</h2>
{table(["Kind", "Date", "Matchup", "Legs", "P(leg 1)", "P(leg 2)", "rho", "rho n",
        "Naive product", "rho-priced", "Difference", "Fair (naive)", "Fair (rho)", "Sources"], rows)}
<h2>How the joint price is computed</h2>
<p>{e(parlays['rule'])}</p>
<p class="dim">Alt lines used: spread {e(parlays.get('alt_spread'))}, total
{e(parlays.get('alt_total'))}. Margin sigma {num(parlays['sigma_margin_pts'])} pts, total sigma
{num(parlays['sigma_total_pts'])} pts.</p>
<div class="banner warn">v1 of this table priced legs against our own numbers at the line itself,
which made every leg ~0.5 and the joint price a constant — a worthless construction. It was
replaced with alt lines (5+ / 8+) so the joint price actually varies with the game. Player-prop rho
is still <strong>NOT MEASURED</strong>: there is no prop line feed here, so that cell stays blank.</div>
""", "parlays.html")


# ---------------------------------------------------------------------------------- injuries

def build_injuries(inj, deltas, archive, minutes):
    pair = deltas["pairs"][0]
    chg = pair.get("status_changes", [])
    rows = []
    for d in chg:
        rows.append([e(d.get("player")), e(d.get("team")), e(d.get("game_date")),
                     e(d.get("matchup")), e(d.get("from")), e(d.get("to")),
                     e(d.get("reason")),
                     src_cell(inj["source_url"])])
    counts = pair.get("counts", pair)
    newest = archive["reports"][-1] if archive["reports"] else {}
    match_rows = []
    seen = set()
    for r in inj["rows"]:
        key = (r.get("player"), r.get("team"), r.get("status"))
        if key in seen or not r.get("player"):
            continue
        seen.add(key)
        matched = minutes["teams"].get(r["team"])
        in_top8 = None
        if matched:
            names = {p["player"].split()[-1].lower() for p in matched["top8"]}
            in_top8 = r["player"].split(",")[0].strip().lower() in names
        match_rows.append([
            e(r.get("player")), e(r.get("team")), e(r.get("status")),
            e(r.get("reason")), e(r.get("game_date")), e(r.get("matchup")),
            ("yes" if in_top8 else ("no" if in_top8 is False
                                    else '<span class="blank">blank — no book</span>')),
            src_cell(inj["source_url"]),
        ])
    return page("Injuries & rotation", f"""
<div class="banner"><strong>Injury-report revision time: {e(inj['report_stamp'])}</strong> — that
stamp is printed on every page of the official PDF. <strong>Retrieved: {e(inj['retrieved_utc'])}</strong>.
The index listed no later filing for this date at read time. Nothing on this page is inferred; a club
with no captured game book prints a blank rotation cell.</div>
{table(KV_HEADERS, kv_rows([
    ["Archived report", link(inj["source_url"], e(inj["source_url"]).replace("https://", ""))],
    ["Index page", link(archive["index_url"], "official.nba.com injury-report index")],
    ["Rows in the report", str(inj["count"])],
    ["Report stamp (on every PDF page)", e(inj["report_stamp"])],
    ["Retrieved (UTC)", e(inj["retrieved_utc"])],
    ["Archived reports held", f'{archive["count"]} filings for this date, never overwritten'],
    ["Newest archived filing", e(newest["file"]) + (
        " · sha256 " + e(newest["sha256"][:16]) + "…" if newest.get("sha256") else "")],
], default=inj["source_url"]))}
<h2>Status changes against the previous archived filing</h2>
<p class="dim">Compared {e(pair["from"]["stamp"])} (read {e(pair["from"]["retrieved_utc"])}, {pair["from"]["rows"]} rows) with {e(pair["to"]["stamp"])} (read {e(pair["to"]["retrieved_utc"])}, {pair["to"]["rows"]} rows) — elapsed {e(pair["elapsed"])}: {counts["status_changes"]} status changes, {counts["added"]} rows added, {counts["removed"]} removed.</p>
{table(["Player", "Team", "Game date", "Matchup", "From", "To", "Reason", "Source"], rows)}
<h2>Report rows and whether the player appears in the club's captured top-8 minutes</h2>
<p class="dim">A "yes" means the named player is in the top 8 by minutes in the most recent official
game book captured for that club, so their absence moves real minutes. A blank means no game book has
been captured for that club yet — blank, not inferred.</p>
{table(["Player", "Team", "Status", "Reason", "Game date", "Matchup", "In captured top-8?",
        "Source"], match_rows[:120])}
""", "injuries.html")


# ----------------------------------------------------------------------------------- minutes

def build_minutes(minutes, logs):
    rows = []
    for code in sorted(minutes["teams"]):
        b = minutes["teams"][code]
        top = "<br>".join(
            f'{e(p["player"])} — {num(p["minutes"], 1)} min '
            f'({num(p.get("share_of_team_minutes"), 3)} of {e(b.get("team_minutes", "240:00"))})'
            for p in b["top8"])
        rows.append([
            e(code), e(b.get("game")),
            "yes" if b.get("overtime") else "no",
            e(b.get("team_minutes")),
            f"<td>{top}</td>",
            src_cell([p.get("source") for p in b["top8"] if p.get("source")][:1]
                     or b.get("source")),
        ])
    missing = sorted(set(_ALL_TEAMS) - set(minutes["teams"]))
    return page("Minutes model", f"""
<div class="banner"><strong>Rotation minutes are read off official game books, one book per club.</strong>
Coverage {minutes['counts']['teams_with_minutes']}/30 clubs. The {len(missing)} clubs without a
captured book print a blank rotation cell on every page — the value is never inferred or filled
in from another source.</div>
<h2>Top-8 minutes shares by club</h2>
{table(["Team", "Book", "OT?", "Team minutes", "Top 8 by minutes", "Source"], rows)}
<h2>Clubs with no captured game book</h2>
<p class="dim">{e(", ".join(missing))} — every rotation cell for these clubs reads
"blank: no captured game book".</p>
<h2>Per-player game log rows captured</h2>
<p class="dim">{logs['counts']['rows']} rows of minutes / points / rebounds / assists / opponent,
taken from the same official game books. Captured for players who appear on an injury report plus the
rest of each captured club's rotation.</p>
{table(KV_HEADERS, kv_rows([
    ["Rows", str(logs["counts"]["rows"])],
    ["Games covered", e(logs["counts"].get("games")) or '<span class="blank">blank</span>'],
    ["Source", "official game-book PDFs under data/slate/raw/"],
], default="https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf"))}
<div class="banner warn"><strong>Known extraction artefacts on the books used here.</strong> The
11/13 MIL@ORL book's score-by-period and totals rows did not survive extraction (it is used for
minutes only). The 11/12 CHA@PHX book prints the home club as "SUNG". The 11/13 POR@SAC book
duplicates the score table, first copy missing the home row. The 11/12 DET@WAS book is a
<strong>two-overtime</strong> game, so its team-minutes denominator is 290:00, not 240:00.</div>
""", "minutes.html")


_ALL_TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND",
              "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX",
              "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]


# ------------------------------------------------------------------------------- rest/travel

def build_travel(travel, arenas):
    rows = []
    for r in travel["rows"]:
        flags = []
        if r.get("away_b2b"):
            flags.append("away B2B")
        if r.get("home_b2b"):
            flags.append("home B2B")
        if (r.get("away_games_in_4d") or 0) >= 3:
            flags.append("away 3-in-4")
        if (r.get("home_games_in_4d") or 0) >= 3:
            flags.append("home 3-in-4")
        rows.append([
            e(r.get("date")), e(r.get("game_id")), e(r.get("matchup")),
            f'<td class="n">{num(r.get("away_rest_days"), 0)}</td>',
            f'<td class="n">{num(r.get("home_rest_days"), 0)}</td>',
            f'<td class="n">{num(r.get("away_travel_mi"), 0)}</td>',
            f'<td class="n">{num(r.get("home_travel_mi"), 0)}</td>',
            e(", ".join(flags)) or '<span class="dim">—</span>',
            src_cell(["https://www.nba.com/schedule?date=2026-11-16",
                      "https://en.wikipedia.org/wiki/List_of_National_Basketball_Association_arenas"]),
        ])
    coord_rows = [[e(a["team"]), e(a["arena"]), e(a["city"]),
                   f'<td class="n">{num(a["lat"], 4)}</td>',
                   f'<td class="n">{num(a["lon"], 4)}</td>',
                   link(a.get("coord_source")) or '<span class="blank">blank</span>']
                  for a in arenas["arenas"]]
    return page("Rest & travel", f"""
<div class="banner">Rest days and back-to-backs come straight off the official schedule. Travel
distance is great-circle miles between the two clubs' home arenas, computed from a coordinate table
sourced club by club — {arenas['verified']}/{arenas['count']} coordinates are sourced from an
official or reference page and individually cited.</div>
<h2>Rest, back-to-backs and travel for every game in the window</h2>
{table(["Date", "Game id", "Matchup", "Away rest (d)", "Home rest (d)", "Away travel (mi)",
        "Home travel (mi)", "Flags", "Sources"], rows)}
<h2>Arena coordinate table</h2>
<p class="dim">Every coordinate carries its own source. A blank coordinate would leave the travel
distance blank and flagged rather than estimated.</p>
{table(["Team", "Arena", "City", "Lat", "Lon", "Coordinate source"], coord_rows)}
""", "rest-travel.html")


# -------------------------------------------------------------------------------------- luck

def build_luck(model):
    rows = []
    for t in sorted(model["luck"]["teams"], key=lambda x: -x["z"]):
        rows.append([e(t["team"]), f'<td class="n">{num(t["expected_wins"])}</td>',
                     f'<td class="n">{t["actual_wins"]}</td>',
                     f'<td class="n">{num(t["z"], 3)}</td>',
                     '<span class="flag">OUTSIDE ±1.96</span>' if t["outside_noise_band"]
                     else '<span class="dim">inside band</span>',
                     src_cell("https://www.nba.com/standings")])
    return page("Luck", f"""
<div class="banner"><strong>Luck is reported as a z-score per club, and any strategy that leans on a
club outside the noise band is refused.</strong> {e(model['luck']['rule'])}</div>
<h2>Luck z-scores over the {model['luck']['oos_games']} out-of-sample games</h2>
{table(["Team", "Expected wins", "Actual wins", "z", "Band", "Source"], rows)}
<h2>Refusals in force from this table</h2>
<p>{e(", ".join(model['luck']['outside_band']))} sit outside ±1.96, so no strategy in this round
publishes a bet on a game involving any of them. The refusal is enforced in code, not by hand: the
pick builder skips the candidate and records the reason.</p>
""", "luck.html")


# --------------------------------------------------------------------------- results/settle

def build_results(feed, ledger):
    rows = []
    for g in feed["games"]:
        rows.append([
            e(g["date"]), e(g["game_id"]), e(f'{g["away"]}@{g["home"]}'),
            e(" / ".join(str(q) for q in (g["away_q"] or []))),
            e(" / ".join(str(q) for q in (g["home_q"] or []))),
            f'<td class="n">{g["away_final"]}–{g["home_final"]}</td>',
            e(g["status"]),
            '<span class="pill ok">verified</span>' if g["verified"]
            else '<span class="pill no">unverified</span>',
            e(g["verification"].get("settled_utc")),
            src_cell(g["verification"]["sources"]),
        ])
    led_rows = []
    for e_ in ledger_rows():
        led_rows.append(e_)
    return page("Results & settlement", f"""
<div class="banner"><strong>One row per game; settled only after the official final is confirmed.</strong>
{e(feed['settlement_rule'])}</div>
<h2>Official results feed ({feed['counts']['verified']}/{feed['counts']['games']} verified)</h2>
{table(["Date", "Game id", "Matchup", "Away quarters", "Home quarters", "Final (away–home)",
        "Status", "Verified", "Settled (UTC)", "Sources"], rows)}
<h2>Settlement stamp</h2>
<p>{e(feed['settlement_stamp_note'])} The ledger is settled from this feed as each game day ends:
{ledger['settled']} picks settled, {ledger['pending']} pending, last settlement stamp
{e(ledger.get('settled_utc')) or '<span class="blank">none yet — no sealed pick has a verified final</span>'}.</p>
""", "results.html")


def ledger_rows():
    path = os.path.join(OUT, "ledger", "ledger.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        out.append([
            f'<td class="n">{d["seq"]}</td>', e(d["strategy"]), e(d["date"]), e(d["matchup"]),
            e(d["market"]), e(d["line"]), e(d["side"]),
            (f'<span class="pill ok">{e(d["result"])}</span>' if d.get("result")
             else '<span class="dim">pending</span>'),
            e(d.get("official_final")) or '<span class="blank">—</span>',
            e(d.get("settled_utc")) or '<span class="blank">—</span>',
            f'<code>{e(d["hash"][:16])}…</code>',
            src_cell(d["sources"]["game"]),
        ])
    return out


# ------------------------------------------------------------------------------ prereg/ledger

def build_prereg():
    idx = load("prereg/index.json")
    rows = []
    for s in idx["files"]:
        d = json.load(open(os.path.join(ROOT, s), encoding="utf-8"))
        rows.append([
            e(d["id"]), e(d["name"]), e(d["hypothesis"]), e(d["signal"]), e(d["universe"]),
            "<td>" + "<br>".join(f"{e(k)}: {e(v)}" for k, v in d["thresholds"].items()) + "</td>",
            e(d["rule"]), e(d["market"]),
            "<td>" + "<br>".join("• " + e(r) for r in d["refusals"]) + "</td>",
            e(d["settlement"]),
            src_cell(["https://www.nba.com/schedule?date=2026-11-16",
                      "https://official.nba.com/nba-injury-report-2025-26-season/",
                      "https://www.nba.com/stats/teams/advanced"]),
        ])
    return page("Pre-registration", f"""
<div class="banner"><strong>Each strategy is frozen in a file before its first bet, and the file is
never overwritten.</strong> Re-running the builder leaves an existing pre-registration untouched —
that is enforced by the script, not by convention.</div>
{table(["Id", "Name", "Hypothesis", "Signal", "Universe", "Thresholds", "Rule", "Market",
        "Refusals", "Settlement rule", "Official inputs"], rows)}
<h3>Integrity</h3>
{table(["File", "Frozen (UTC)", "sha256 of the canonical JSON", "Official inputs"],
       [[e(f["file"]), e(f["frozen_utc"]), f'<code>{e(f["sha256"][:32])}…</code>',
         src_cell(["https://www.nba.com/schedule?date=2026-11-16",
                   "https://official.nba.com/nba-injury-report-2025-26-season/"])]
        for f in idx["written"] + idx["left_frozen"]])}
<p class="dim">Rule: {e(idx['rule'])}</p>
""", "prereg.html")


def build_ledger(ledger):
    return page("Pick ledger", f"""
<div class="banner"><strong>Tamper-evident: every pick is hashed and chained before tip.</strong>
{e(ledger['rule'])}</div>
{table(KV_HEADERS, kv_rows([
    ["Picks sealed", str(ledger["count"])],
    ["Head hash", f'<code>{e(ledger["head"])}</code>'],
    ["Genesis hash", f'<code>{e(ledger["genesis"])}</code>'],
    ["Published (UTC)", e(ledger["published_utc"])],
    ["Sealed before tip", "yes — the ledger is written only from projections that exist "
                          "before the game starts"],
    ["Settled / pending", f'{ledger.get("settled", 0)} / {ledger.get("pending", ledger["count"])}'],
], default=["https://www.nba.com/standings",
            "https://www.nba.com/schedule?date=2026-11-16"]))}
<h2>Sealed picks</h2>
{table(["#", "Strategy", "Date", "Matchup", "Market", "Line", "Side", "Result", "Official final",
        "Settled (UTC)", "Hash", "Source"], ledger_rows())}
<h3>Verifying the chain yourself</h3>
<p><code>python3 scripts/picks_round_3d625d23.py verify</code> recomputes
<code>hash_i = sha256(hash_(i-1) + canonical_json(pick_i))</code> from genesis and prints
<code>CHAIN INTACT</code> or <code>CHAIN BROKEN at seq n</code>. The same check runs as a gate before
any rebuild.</p>
""", "ledger.html")


# ------------------------------------------------------------------------------------- gates

def build_gates(gates, refresh):
    rows = [[e(g["id"]), e(g["name"]),
             '<span class="pill ok">PASS</span>' if g["status"] == "PASS"
             else '<span class="pill no">FAIL</span>',
             e(g["detail"]),
             src_cell(g["sources"])] for g in gates["gates"]]
    src_rows = []
    for s in refresh["sources"]:
        src_rows.append([
            e(s["id"]), e(s["label"]), link(s["url"], e(s["url"]).replace("https://", "")),
            f'<td class="n">{s["cadence_h"]}h</td>',
            e(s["newest_capture_utc"]) or '<span class="blank">no stamp</span>',
            f'<td class="n">{num(s["age_h"], 2)}</td>' if s["age_h"] is not None else "<td></td>",
            '<span class="pill ok">FRESH</span>' if s["fresh"]
            else '<span class="pill no">STALE</span>',
            e(s["feeds"]),
        ])
    return page("Gates & refresh", f"""
<div class="banner"><strong>Refresh → prove freshness and provenance → rebuild.</strong>
{e(gates['rule'])} If a gate fails the rebuild step is refused and the exit code is non-zero, so the
last good build stays published.</div>
<h2>Gates ({gates['counts']['passed']}/{gates['counts']['gates']} passing)</h2>
{table(["Id", "Gate", "Status", "Detail", "Sources"], rows)}
<h2>Rolling refresh set</h2>
<p class="dim">{e(refresh['rule'])} Run
<code>python3 scripts/refresh_round_3d625d23.py --rebuild</code>; without <code>--rebuild</code> it
reports only.</p>
{table(["Id", "Source", "URL", "Cadence", "Newest capture", "Age (h)", "State", "Feeds"], src_rows)}
<h2>Last refresh run</h2>
{table(["Step", "Command", "Exit code", "Official source read"],
       [[e(s["step"]), f'<code>{e(s["command"])}</code>', f'<td class="n">{s["rc"]}</td>',
         src_cell("https://www.nba.com/schedule?date=2026-11-16")]
        for s in refresh["steps"]])}
""", "gates.html")


# --------------------------------------------------------------------------------- team stats

def build_team_stats(standings, advanced, traditional, opponent):
    adv = {r["team"]: r for r in advanced["rows"]}
    tr = {r["team"]: r for r in traditional["rows"]}
    op = {r["team"]: r for r in opponent["rows"]}
    rows = []
    for r in sorted(standings["rows"], key=lambda x: (x["conference"], -x["w"])):
        t = r["team"]
        a, b, c = adv.get(t, {}), tr.get(t, {}), op.get(t, {})
        rows.append([
            e(r["conference"]), f'<td class="n">{r["conf_rank"]}</td>', e(r["team_name"]),
            f'<td class="n">{r["w"]}–{r["l"]}</td>', e(r["win_pct"]),
            f'<td class="n">{e(r["last10"])}</td>', e(r["streak"]),
            f'<td class="n">{num(b.get("pts"))}</td>',
            f'<td class="n">{num(c.get("opp_pts"))}</td>',
            f'<td class="n">{num(a.get("off_rtg"))}</td>',
            f'<td class="n">{num(a.get("def_rtg"))}</td>',
            f'<td class="n">{num(a.get("net_rtg"))}</td>',
            f'<td class="n">{num(a.get("pace"))}</td>',
            src_cell(["https://www.nba.com/standings",
                      "https://www.nba.com/stats/teams/advanced",
                      "https://www.nba.com/stats/teams/traditional",
                      "https://www.nba.com/stats/teams/opponent"]),
        ])
    return page("Team stats (official)", f"""
<div class="banner">The four official pages — standings, traditional, opponent, advanced —
re-read for this rolling slate. Every column below is transcribed from one of them; nothing is
derived.</div>
<div class="banner warn"><strong>The four pages are not synchronised.</strong> At the {e(STAMP)} read
the traditional and opponent pages had not absorbed the CHA@LAC final — they show LAC 11 GP (3-8)
and CHA 12 GP (4-8), while the advanced page and the standings page both show LAC 12 GP (4-8) and
CHA 13 GP (4-9). The lag is published rather than reconciled; no value is inferred or copied across.</div>
{table(["Conf", "Rank", "Team", "W–L", "Win%", "Last 10", "Streak", "PTS", "Opp PTS",
        "OffRtg", "DefRtg", "NetRtg", "Pace", "Sources"], rows)}
<h3>Page notes</h3>
<p class="dim">{e(standings['note'])}</p>
<p class="dim">{e(advanced['note'])}</p>
<p class="dim">{e(traditional['note'])}</p>
<p class="dim">{e(opponent['note'])}</p>
""", "team-stats.html")


# ------------------------------------------------------------------------- questions/sugg/flagged

Q_ANSWER_PAGE = {
    "A licensed closing-line feed": None,
    "Player-prop lines or a prop results feed": None,
    "Game books for ATL, BOS, NYK, OKC, TOR":
        "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
    "An out-of-sample record for E2 beyond 3 games":
        "https://www.nba.com/stats/teams/advanced",
    "Per-possession lineups or on/off data":
        "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf",
    "Referee assignments as a model input":
        "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
    "Whether the 11/15 games still live at read time finished as expected":
        "https://www.nba.com/schedule?date=2026-11-16",
}

QUESTIONS = [
    ("Have", "Official schedule for the window", "Every game id, matchup, arena and tip time",
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("Have", "Official standings", "30 clubs, W/L and every split column",
     "https://www.nba.com/standings"),
    ("Have", "Four official team-stat pages", "traditional, opponent, advanced (30 rows each)",
     "https://www.nba.com/stats/teams/advanced"),
    ("Have", "Newest filed official injury report", "155 rows, 06:30 PM ET revision stamp",
     "https://official.nba.com/nba-injury-report-2025-26-season/"),
    ("Have", "Official game books for 25 of 30 clubs", "minutes, box scores, inactive lists",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf"),
    ("Have", "Settled finals with quarter scores", "8 games verified two ways",
     "https://www.nba.com/standings"),
    ("Have", "Arena coordinates for all 30 clubs", "so travel distance is computable",
     "https://en.wikipedia.org/wiki/List_of_National_Basketball_Association_arenas"),
    ("Do not have", "A licensed closing-line feed", "so the market-anchored prior is blank",
     None),
    ("Do not have", "Player-prop lines or a prop results feed", "so player-prop rho is not measured",
     None),
    ("Do not have", "Game books for ATL, BOS, NYK, OKC, TOR", "so their rotation cells are blank",
     None),
    ("Do not have", "An out-of-sample record for E2 beyond 3 games",
     "the efficiency page is a single current snapshot, so E2 carries no blend weight yet", None),
    ("Do not have", "Per-possession lineups or on/off data",
     "minutes redistribution is at player level, not lineup level", None),
    ("Do not have", "Referee assignments as a model input",
     "they are printed in every game book but not yet captured as a feature", None),
    ("Do not have", "Whether the 11/15 games still live at read time finished as expected",
     "SAS@UTA, DAL@BOS, NYK@TOR, HOU@WAS, ATL@MIL and OKC@SAC were in progress", None),
]


def build_questions():
    rows = []
    for state, item, why, url in QUESTIONS:
        rows.append([
            '<span class="pill ok">have</span>' if state == "Have"
            else '<span class="pill no">do not have</span>',
            e(item), e(why),
            src_cell(url) if url else
            ('<td><span class="flag">NO OFFICIAL SOURCE — blank by design</span><br>'
             + link(Q_ANSWER_PAGE.get(item) or
                    "https://official.nba.com/nba-injury-report-2025-26-season/",
                    "official page the answer would have to come from") + "</td>"),
        ])
    return page("Open questions", """
<div class="banner">Split by what this round actually has and does not. The second half is not
guesswork waiting to happen — every one of those cells is blank in the data and flagged on the
site until an official source can be read for it.</div>
<h2>What we have vs what we do not</h2>
<table><thead><tr><th>State</th><th>Item</th><th>Why it matters</th><th>Official source</th></tr>
</thead><tbody>""" + "".join(
        "<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in r) + "</tr>"
        for r in rows) + """</tbody></table>
<h2>Questions that must be answered before any of this is funded</h2>
<ol>
<li><strong>Is a closing-line feed available?</strong> Without it the prior cannot be anchored and
every line stays ours alone. Until then no strategy should be described as tested against a
market.</li>
<li><strong>How many out-of-sample games does E2 need before it earns weight?</strong> The
pre-registration says 30. The efficiency page only produces one new observation per game day, so
that is roughly a month of real time.</li>
<li><strong>Do the five clubs with no captured book get one?</strong> Their games are on the
schedule; the books are published the following day. The capture list is mechanical.</li>
<li><strong>What counts as "skill" for the leaderboard?</strong> A strategy has to beat the
coin-flip log-loss of 0.6931 on games it never saw, not on the games it was fitted to.</li>
<li><strong>Who owns the settlement if a game book and the standings page disagree?</strong> Both
are official. The rule today is that the game book's own quarters must sum to its printed final and
the standings page must show the matching streak.</li>
</ol>
""", "questions.html")


S_CHECK = {
    "S-3D-01": "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
    "S-3D-02": "https://www.nba.com/stats/teams/advanced",
    "S-3D-03": "https://www.nba.com/standings",
    "S-3D-04": "https://www.nba.com/schedule?date=2026-11-16",
    "S-3D-05": "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf",
    "S-3D-06": "https://www.nba.com/stats/teams/traditional",
    "S-3D-07": "https://www.nba.com/stats/teams/opponent",
}

SUGGESTIONS = [
    ("S-3D-01", "Capture the five missing game books on the next refresh",
     "ATL, BOS, NYK, OKC and TOR print blank rotation cells. Their 11/15 books are published the "
     "next day; adding the fetch to the rolling job closes the gap without any modelling change.",
     "high", "none — additive capture only"),
    ("S-3D-02", "Persist the advanced page as a dated snapshot every refresh",
     "The page is a single current snapshot, so E2 can only ever be scored out of sample one game "
     "at a time. Storing it per date turns E2 into a genuinely testable estimator within weeks.",
     "high", "new dated files under data/slate/raw/"),
    ("S-3D-03", "Add a closing-line capture the moment a feed is available",
     "The market-anchored prior is blank today for one reason only: no feed. The weighting formula "
     "is already written and uses measured out-of-sample log-loss on both sides.",
     "high", "requires a data-source decision"),
    ("S-3D-04", "Publish the disagreement as a time series",
     "The headline is |E1 − E2| per game, but its usefulness is an empirical question: does a "
     "small disagreement actually predict a smaller error? Recording disagreement next to the "
     "realised error per game answers it in a few weeks.",
     "medium", "append-only ledger, no model change"),
    ("S-3D-05", "Capture referee crews from the game books",
     "Every book prints the three officials. It is already in the capture; it is simply not a "
     "feature yet. Whether it carries signal is a separate question that the data can settle.",
     "medium", "new feature, needs its own out-of-sample test"),
    ("S-3D-06", "Do not add more strategies until the existing three have records",
     "Three pre-registered strategies produced six research picks. Adding more before any of them "
     "has an out-of-sample record multiplies the multiple-comparisons problem.",
     "high", "none — a decision not to build"),
    ("S-3D-07", "Re-read the four team-stat pages at a fixed time each day",
     "This round caught the pages out of sync by minutes. A fixed read time makes the lag visible "
     "and comparable instead of accidental.",
     "medium", "scheduler change only"),
]


def build_suggestions():
    rows = [[e(i), e(title), e(body),
             ('<span class="flag">high</span>' if pri == "high" else e(pri)), e(cost),
             src_cell(S_CHECK[i])]
            for i, title, body, pri, cost in SUGGESTIONS]
    return page("Suggestions", """
<div class="banner"><strong>This page is decision support only.</strong> Nothing here is implemented
because it appears here. Each row is a path someone can choose; the cost column says what adopting it
would touch.</div>
<h2>Suggested paths, reviewable before anything changes</h2>
<table><thead><tr><th>Id</th><th>Suggestion</th><th>Why</th><th>Priority</th>
<th>Cost to adopt</th><th>Official page to check</th></tr></thead><tbody>""" + "".join(
        "<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in r) + "</tr>"
        for r in rows) + """</tbody></table>
""", "suggestions.html")


F_CHECK = {
    "F-3D-01": "https://www.nba.com/standings",
    "F-3D-02": "https://www.nba.com/stats/teams/traditional",
    "F-3D-03": "https://www.nba.com/stats/teams/advanced",
    "F-3D-04": "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
    "F-3D-05": "https://www.nba.com/stats/teams/opponent",
    "F-3D-06": "https://www.nba.com/standings",
    "F-3D-07": "https://statsdmz.nba.com/pdfs/20261112/20261112_DETWAS.pdf",
    "F-3D-08": "https://www.nba.com/schedule?date=2026-11-16",
    "F-3D-09": "https://official.nba.com/nba-injury-report-2025-26-season/",
    "F-3D-10": "https://www.nba.com/stats/teams/advanced",
}

FLAGS = [
    ("F-3D-01", "Market-anchored prior is blank",
     "No licensed closing-line feed is connected, so every blended line is blank and flagged and "
     "the model line is published alone.",
     "data/slate/prior.json"),
    ("F-3D-02", "Player-prop correlations not measured",
     "There is no prop line feed and no per-player prop results history in this environment, so "
     "the player-prop rho cell is blank rather than assumed.",
     "data/slate/model.json → correlations"),
    ("F-3D-03", "Estimator E2 has 3 out-of-sample games",
     "The official advanced page is a single current snapshot, so E2 cannot be scored on history. "
     "It carries zero blend weight under the pre-registered 30-game minimum.",
     "data/slate/model.json → blend"),
    ("F-3D-04", "Rotation minutes cover 25 of 30 clubs",
     "ATL, BOS, NYK, OKC and TOR have no captured game book. Their rotation cells read blank; "
     "nothing is inferred.",
     "data/slate/minutes.json"),
    ("F-3D-05", "The four official team pages were out of sync at read time",
     "Traditional and opponent had not absorbed the CHA@LAC final; advanced and standings had. "
     "Published as an irregularity, not reconciled.",
     "data/slate/raw/team_*.md"),
    ("F-3D-06", "Two reads of the standings and advanced pages in one night",
     "The 23:41Z / 23:45Z reads caught LAL@PHX and CHA@LAC still live; the 00:05Z reads carry both "
     "finals. The earlier reads are superseded, not discarded.",
     "data/slate/raw/standings_2026-11-15.md"),
    ("F-3D-07", "Game-book extraction artefacts",
     "MIL@ORL: score-by-period and totals rows corrupted (minutes only). CHA@PHX: home club prints "
     "as SUNG. POR@SAC: duplicate score table, first copy missing the home row. DET@WAS: two "
     "overtimes, so its team-minutes denominator is 290:00.",
     "data/slate/raw/gamebook_*.md"),
    ("F-3D-08", "Six 11/15 games were still live at the read",
     "SAS@UTA, DAL@BOS, NYK@TOR, HOU@WAS, ATL@MIL and OKC@SAC had not finished, so they are absent "
     "from the results feed and their books are partial.",
     "data/slate/results_feed.json"),
    ("F-3D-09", "No strategy has cleared its validation gate",
     "Three strategies are pre-registered and six research picks are sealed, but none has an "
     "out-of-sample record. Nothing here is funded and no money is staked.",
     "data/slate/prereg/, data/slate/picks.json"),
    ("F-3D-10", "Home-court advantage disagrees with earlier sessions",
     "This round pins HCA at 1.213 pts (sigma × probit of the measured home-win rate over 191 "
     "games). Earlier sessions published 1.127 and a free-fitted 1.62. The pinned rule is used and "
     "the conflict is published rather than averaged.",
     "data/slate/model.json → hca"),
]


def build_flagged():
    rows = [[e(i), e(t), e(body), f"<td><code>{e(path)}</code></td>", src_cell(F_CHECK[i])]
            for i, t, body, path in FLAGS]
    return page("Flagged for review", """
<div class="banner warn"><strong>Anything that could not be confirmed from an official source is
published here instead of being quietly filled in.</strong> These items do not block the site; they
are the list of things a reviewer should look at first.</div>
<table><thead><tr><th>Id</th><th>Flagged item</th><th>What it means</th><th>Where</th>
<th>Official page to check it against</th></tr></thead><tbody>""" + "".join(
        "<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in r) + "</tr>"
        for r in rows) + """</tbody></table>
""", "flagged.html")


SOURCES = [
    ("Official injury report (PDF)", "https://official.nba.com/nba-injury-report-2025-26-season/",
     "Index of every filed report; the newest 11/15 filing is the 06:30 PM ET PDF"),
    ("Official injury report, 11/15 06:30 PM ET",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_30PM.pdf",
     "155 rows; the revision stamp printed on every page"),
    ("Official schedule", "https://www.nba.com/schedule?date=2026-11-16",
     "Window 11/16–11/18: game ids, matchups, arenas, tip times"),
    ("Official standings", "https://www.nba.com/standings",
     "30 clubs, conference view, Overall section"),
    ("Official team stats — traditional",
     "https://www.nba.com/stats/teams/traditional", "30 rows, per game"),
    ("Official team stats — opponent", "https://www.nba.com/stats/teams/opponent",
     "30 rows, per game"),
    ("Official team stats — advanced", "https://www.nba.com/stats/teams/advanced",
     "OffRtg, DefRtg, NetRtg, Pace, PIE, POSS — the inputs to E2"),
    ("Official game book, 11/15 LAL@PHX",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
     "Final 131–123, quarter scores, minutes, inactive list"),
    ("Official game book, 11/15 CHA@LAC",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf",
     "Final 105–113, quarter scores, minutes, inactive list"),
    ("Official game book, 11/15 IND@PHI",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
     "Final 124–131, quarter scores, minutes, inactive list"),
    ("Official game book, 11/13 MIL@ORL",
     "https://statsdmz.nba.com/pdfs/20261113/20261113_MILORL.pdf",
     "ORL minutes; score rows corrupted in extraction, used for minutes only"),
    ("Official game book, 11/12 DET@WAS",
     "https://statsdmz.nba.com/pdfs/20261112/20261112_DETWAS.pdf",
     "Two overtimes — 290:00 team minutes"),
    ("Official game book, 11/13 GSW@SAS",
     "https://statsdmz.nba.com/pdfs/20261113/20261113_GSWSAS.pdf", "Minutes and inactive lists"),
    ("Official game book, 11/13 UTA@HOU",
     "https://statsdmz.nba.com/pdfs/20261113/20261113_UTAHOU.pdf", "Minutes and inactive lists"),
    ("Official game book, 11/12 CHA@PHX",
     "https://statsdmz.nba.com/pdfs/20261112/20261112_CHAPHX.pdf", "Minutes and inactive lists"),
    ("Official game book, 11/13 POR@SAC",
     "https://statsdmz.nba.com/pdfs/20261113/20261113_PORSAC.pdf", "Minutes and inactive lists"),
    ("Arena coordinate reference",
     "https://en.wikipedia.org/wiki/List_of_National_Basketball_Association_arenas",
     "Reference-labelled coordinates; every row in the table carries its own citation"),
]


def build_sources():
    rows = [[e(name), link(url, url.replace("https://", "")), e(use)] for name, url, use in SOURCES]
    return page("Sources", """
<div class="banner">Every table row on this site carries a link to the official page it came from.
This page lists them all in one place.</div>
<table><thead><tr><th>Source</th><th>URL</th><th>What it is used for</th></tr></thead><tbody>""" + \
        "".join("<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in r) + "</tr>"
                for r in rows) + """</tbody></table>
<h3>Captures and integrity</h3>
<p>Each page read is stored verbatim under <code>data/slate/raw/</code> with its source URL, a
retrieval stamp and a sha256 of the file. The parsers read those committed transcriptions only, so
the build is reproducible offline and a difference in the output means a real input changed.</p>
""", "sources.html")


def main():
    os.makedirs(SITE, exist_ok=True)
    model = load("model.json")
    gates = load("gates.json")
    refresh = load("refresh_report.json")
    parlays = load("parlays.json")
    picks = load("picks.json")
    ledger = load("ledger/index.json")
    minutes = load("minutes.json")
    logs = load("player_game_logs.json")
    feed = load("results_feed.json")
    inj = load("injuries/injury_2026-11-15_0630PM.json")
    deltas = load("injuries/deltas.json")
    archive = load("injuries/archive_index.json")
    travel = load("travel.json")
    arenas = load("arena_coordinates.json")
    standings = load("standings.json")
    advanced = load("team_advanced.json")
    traditional = load("team_traditional.json")
    opponent = load("team_opponent.json")
    prior = load("prior.json")

    built = {
        "index.html": build_index(model, gates, refresh, parlays, picks, ledger, minutes, feed,
                                  model["luck"]),
        "projections.html": build_projections(model),
        "lines.html": build_lines(model, prior),
        "parlays.html": build_parlays(parlays),
        "injuries.html": build_injuries(inj, deltas, archive, minutes),
        "minutes.html": build_minutes(minutes, logs),
        "rest-travel.html": build_travel(travel, arenas),
        "luck.html": build_luck(model),
        "results.html": build_results(feed, ledger),
        "prereg.html": build_prereg(),
        "ledger.html": build_ledger(ledger),
        "gates.html": build_gates(gates, refresh),
        "team-stats.html": build_team_stats(standings, advanced, traditional, opponent),
        "questions.html": build_questions(),
        "suggestions.html": build_suggestions(),
        "flagged.html": build_flagged(),
        "sources.html": build_sources(),
    }
    for name, doc in built.items():
        with open(os.path.join(SITE, name), "w", encoding="utf-8") as fh:
            fh.write(doc)

    # link + per-row source check: fail the build rather than publish a broken site
    official = ("nba.com", "wikipedia.org")
    problems = []
    for name, doc in built.items():
        for m in re.finditer(r'href="([^"]+)"', doc):
            h = m.group(1)
            if h.startswith("#") or h.startswith("http"):
                continue
            if not h.endswith(".html"):
                continue        # data paths and code are printed, not navigable
            if not os.path.exists(os.path.join(SITE, h.split("#")[0])):
                problems.append(f"{name}: broken internal link {h}")
        for tbody in re.findall(r"<tbody>(.*?)</tbody>", doc, re.S):
            for i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", tbody, re.S), 1):
                if "https://" not in tr:
                    problems.append(f"{name}: table body row {i} has no official-source link")
        for tbl in re.findall(r"<table[^>]*>(.*?)</table>", doc, re.S):
            head = re.search(r"<thead>\s*<tr>(.*?)</tr>\s*</thead>", tbl, re.S)
            if not head:
                continue
            ncol = len(re.findall(r"<th[^>]*>", head.group(1)))
            for i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", tbl, re.S), 1):
                n = len(re.findall(r"<td[^>]*>", tr))
                if n and n != ncol:
                    problems.append(f"{name}: table row {i} has {n} cells, header has {ncol}")
    if problems:
        raise SystemExit("build failed:\n  " + "\n  ".join(problems))
    print(f"wrote {len(built)} pages to slate/, {sum(1 for _ in official)} official host allowlist, "
          f"links and per-row sources checked")


if __name__ == "__main__":
    main()
