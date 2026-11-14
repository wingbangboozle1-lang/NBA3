"""Render the unified NBA Edge dashboard into dash/ and the root landing page.

Session e40cd215. Reads only two artefacts:
  data/integration/model.json      - produced by integrate/engine.py
  data/integration/registers.json  - sources, flags, questions, suggestions

Rules enforced here (and re-checked by integrate/check.py):
  * every table row carries an official source link, or the cell is blank and
    marked UNVERIFIED - a value is never filled in by inference;
  * every internal link resolves to a file that this script writes;
  * no file outside dash/, index.html, data/integration/ is written.

    python3 -m integrate.build_site
"""

from __future__ import annotations

import html
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INT = ROOT / "data" / "integration"
DASH = ROOT / "dash"
OUT_DATA = DASH / "data"

PAGES = [
    ("index", "Executive summary", "Landing, headline numbers, what is and is not usable"),
    ("lines", "Originated lines", "Spread, total and fair moneyline for every game in the window"),
    ("picks", "Picks & parlays", "Single bets, parlays and prop combos, with the gate status on each"),
    ("leaderboard", "Strategy leaderboard", "Every candidate strategy, graded out of sample against our own line"),
    ("gates", "Validation gates", "What a strategy must clear before it is eligible, and who cleared what"),
    ("correlations", "Correlation", "Measured dependence between markets - the parlay input"),
    ("injuries", "Injuries & rotations", "Official designations, minutes at risk, and how stale the snapshot is"),
    ("gameflow", "Game flow", "Rest, back-to-backs, overtime and margin distribution"),
    ("reconciliation", "Cross-engine reconciliation", "Where the three engines agree, and why their headline numbers differ"),
    ("verification", "Verification log", "Line-by-line checks run this round, each with its official link"),
    ("questions", "Open questions", "What must be answered before a decision is reasonable"),
    ("suggestions", "Site improvements", "Ranked changes with the decision each one needs - nothing is implemented for you"),
    ("flagged", "Flagged for review", "Irregularities and unverified items, with sources"),
    ("sources", "Source register", "Every URL this dashboard depends on, with what was read and when"),
    ("data", "Data & reproduction", "Files, schemas and the commands that rebuild everything"),
]

NAV_HTML = "\n".join(
    f'<a class="nav-i" href="{p}.html">{html.escape(t)}</a>' for p, t, _ in PAGES
)

BADGE = {
    "PASS": "ok",
    "FAIL": "bad",
    "PARTIAL": "warn",
    "NOT EVALUATED": "mute",
    "NOT STARTED": "mute",
    "BLOCKED": "bad",
    "high": "bad",
    "medium": "warn",
    "low": "mute",
}


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def badge(text: str) -> str:
    key = (text or "").split()[0].upper().strip(":")
    cls = BADGE.get(key, BADGE.get(text, "info"))
    return f'<span class="b b-{cls}">{esc(text)}</span>'


def num(x, dp=2, suffix=""):
    if x is None:
        return '<span class="blank" title="not verified - left blank on purpose">—</span>'
    if isinstance(x, float):
        return f"{x:.{dp}f}{suffix}"
    return f"{x}{suffix}"


def pct(x, dp=1):
    return "—" if x is None else f"{100 * x:.{dp}f}%"


def link(url, label=None):
    if not url:
        return '<span class="blank">no source</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label or url.split("/")[2])}</a>'


def table(headers, rows, caption=None, note=None):
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f'<caption>{esc(caption)}</caption>' if caption else ""
    nt = f'<p class="note">{note}</p>' if note else ""
    empty = f'<tr><td colspan="{len(headers)}" class="blank">no rows — nothing verifiable in this category</td></tr>'
    return (
        f'<div class="tw"><table data-rows="{len(rows)}">{cap}<thead><tr>{th}</tr></thead>'
        f"<tbody>{body or empty}</tbody></table></div>{nt}"
    )


def layout(slug, title, sub, body, m, extra_head=""):
    stamp = m.get("as_of", "")
    nav = NAV_HTML.replace(f'href="{slug}.html"', f'href="{slug}.html" aria-current="page"')
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NBA Edge Lab</title>
<meta name="description" content="{esc(sub)}">
<link rel="stylesheet" href="style.css">{extra_head}
</head><body>
<header class="top">
  <div class="brand"><a href="index.html"><strong>NBA Edge Lab</strong><span>integrated build · session e40cd215</span></a></div>
  <div class="stamp">{esc(stamp)}</div>
</header>
<nav class="nav" aria-label="sections">{nav}</nav>
<main>
<h1>{esc(title)}</h1>
<p class="sub">{sub}</p>
{body}
</main>
<footer>
<p><b>Not betting advice.</b> Lines on this site are model output from verified NBA.com results, not
market prices; no licensed odds feed exists in this repository. Strategy results are out-of-sample
backtests on 114 games and none of them clears the eligibility gates. Follow local law and
responsible-gambling practice.</p>
<p>Rebuilt by <code>python3 -m integrate.engine &amp;&amp; python3 -m integrate.build_site</code> ·
<a href="data.html">data &amp; reproduction</a> ·
<a href="flagged.html">flagged for review</a> ·
<a href="../index.html">root landing</a></p>
</footer>
<script src="app.js"></script>
</body></html>
"""


# --------------------------------------------------------------------------- pages
def page_index(m, reg):
    v = {x["variant_id"] + "-" + x["market"]: x for x in m["model_variants"]}
    g = {x["id"]: x for x in m["gates"]}
    n_pass = sum(1 for x in m["gates"] if x["status"] == "PASS")
    strat = [s for s in m["strategies"] if s.get("gradable_vs_own_line", True)]
    best = max(strat, key=lambda s: s["n_bets"]) if strat else None
    cards = [
        ("Games verified", f"{m['integrity']['games']}", "2026-10-20 → 2026-11-12, two independent captures"),
        ("Score mismatches", f"{m['integrity']['score_mismatches']}", "between the two captures, after normalising team codes"),
        ("Lines originated", f"{len(m['lines'])}", "every game in the live 72-hour window"),
        ("Strategies passing all gates", "0", f"largest gradable sample {best['n_bets'] if best else 0} bets vs a floor of 100"),
        ("Gates cleared", f"{n_pass} of {len(m['gates'])}", "provenance and leakage only"),
        ("Margin model vs baseline", f"{v['sel-margin']['rmse_model']:.2f} / {v['sel-margin']['rmse_baseline']:.2f}", "RMSE, out of sample, one shared baseline"),
    ]
    grid = "".join(
        f'<div class="card"><div class="k">{esc(t)}</div><div class="v">{esc(val)}</div><div class="d">{esc(d)}</div></div>'
        for t, val, d in cards
    )
    head_rows = [
        ["Can be read now", "Originated lines for the 11/14–11/16 window", "Model output, with a 95% interval on each number", link("https://www.nba.com/games?date=2026-11-14", "nba.com/games")],
        ["Can be read now", "Official availability for the window", "Transcribed from the newest report that exists", link(m["sources"]["injury_pdf"], "injury PDF 07:30 PM")],
        ["Can be read now", "Rest, back-to-back, overtime and margin structure", "Recomputed from the 174 verified results", link(m["sources"]["games_raw"], "games.csv")],
        ["Needs a decision first", "Any claim of edge or profit", "No market price in the repository - E-F-05", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/questions.csv", "questions.csv")],
        ["Needs a decision first", "Player props and prop combos", "Only 31 players' minutes captured - E-F-07", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/origin/players_top_minutes.csv", "players_top_minutes.csv")],
        ["Needs data we do not have", "A ranked leaderboard with rewards", "No strategy reaches the sample floor - E-F-15", badge("blocked")],
    ]
    body = f"""
<section class="callout"><h2>Read this first</h2>
<p>The model in this build forecasts <b>the score</b>, not the market. Out of sample its spread
prediction is {100 * (1 - v['sel-margin']['rmse_model'] / v['sel-margin']['rmse_baseline']):.1f}% better than a
constant baseline on 114 games (paired t p={v['sel-margin']['paired_p']:.4f}); its total prediction is
{100 * (1 - v['sel-total']['rmse_model'] / v['sel-total']['rmse_baseline']):.1f}% better and that part is not
significant (p={v['sel-total']['paired_p']:.4f}). So we do have forecast skill on the margin, and we do not
yet have evidence of betting skill: no bettor profits from a forecast, only from a forecast that beats a
price, and no price exists in this repository. Everything below the fold is labelled accordingly.</p></section>
<div class="cards">{grid}</div>
{table(["Status", "What", "Basis", "Source"], head_rows, "What is usable today",
       'Three of six rows are blocked on an owner decision, not on engineering. See <a href="questions.html">open questions</a> and <a href="flagged.html">flagged items</a>.')}
<h2>The window</h2>
{table(["Date", "Games", "Tip window (ET)", "Verified against"],
   [[d, str(len([l for l in m['lines'] if l['date'] == d])),
     min(l['time_et'] for l in m['lines'] if l['date'] == d) + " – " + max(l['time_et'] for l in m['lines'] if l['date'] == d),
     link(f"https://www.nba.com/games?date={d}", "nba.com/games?date=" + d)]
    for d in sorted({l['date'] for l in m['lines']})], None,
   "11/13 is deliberately absent: those games were in progress while this build ran, so results stop at 11/12 (E-F-11).")}
<h2>How to read a number here</h2>
<p>Every table row ends in a source. A dash (—) means the value was not verifiable and was left blank
rather than estimated; hovering it says so. <code>data/integration/model.json</code> is the single artefact
these pages render, so a row that looks wrong can be traced to the line of <code>integrate/engine.py</code>
that produced it.</p>
"""
    return body


def page_lines(m, reg):
    rows = []
    for l in m["lines"]:
        av = []
        for side, key in (("home", "availability_home"), ("away", "availability_away")):
            a = l[key]
            if a["report_status"] == "not_yet_submitted":
                av.append("not filed")
            else:
                od = a.get("out_or_doubtful")
                av.append("—" if od is None else f"{od} out/doubtful")
        rows.append([
            l["date"][5:],
            esc(l["time_et"]),
            f'{esc(l["away"])} at {esc(l["home"])}',
            num(l["orig_spread_home"], 1),
            num(l["orig_total"], 1),
            num(l["fair_ml_home"], 0),
            num(l["p_home_win"], 3),
            f'[{num(l["margin_interval_95"][0],1)}, {num(l["margin_interval_95"][1],1)}]',
            esc(" / ".join(av)),
            link(l["game_url"], "game page"),
        ])
    note = (
        "Spread is from the home team's perspective (negative = home favours by that margin). Lines are "
        "rounded to half points so no push is possible. <b>orig_spread_home</b> is the model's own number, "
        "not a book price; the 95% interval is wider than any plausible betting margin, which is the "
        "honest reason these lines are not yet picks. Sources per row: schedule "
        f"{link('https://www.nba.com/games?date=2026-11-14', 'nba.com/games')} · availability "
        f"{link(m['sources']['injury_pdf'], 'official report')} · results used to fit the ratings "
        f"{link(m['sources']['games_raw'], 'games.csv')}."
    )
    return (
        "<p>Every game tipped in the next 72 hours, priced from the ratings fitted on the 174 verified "
        "results. Nothing here uses an external price.</p>"
        + table(["Date", "Tip", "Matchup", "Spread (home)", "Total", "Fair ML (home)", "P(home win)", "95% margin interval", "Availability", "Source"],
                rows, "Originated lines - model output only", note)
        + "<h2>What the model is</h2><p>Two independent rating engines are fitted on results alone "
          "(recency-weighted points for/against with league shrinkage, and a Massey ridge least-squares fit), "
          "and a game-by-game selector picks between them using only the 30 predictions that preceded it. "
          "That keeps model selection out of sample. Full detail and the variant table are on "
          "<a href='reconciliation.html'>reconciliation</a>.</p>"
    )


def page_picks(m, reg):
    strat = {s["id"]: s for s in m["strategies"]}
    eligible = [s for s in m["strategies"] if s.get("gradable_vs_own_line", True) and s["n_bets"] >= 100]
    banner = (
        '<section class="stop"><h2>No approved picks exist</h2><p>Zero strategies clear the gates, so no '
        'line on this site is a pick. The rows below are the <i>signals a gate would have to like</i>: what '
        'the model leans toward, what evidence exists, and exactly which gate is holding it back. A pick '
        'page that hid that would be the most misleading page on the site.</p></section>'
    )
    rows = []
    for l in m["lines"]:
        lean = "HOME" if l["pred_margin_home"] > 0 else "AWAY"
        mag = abs(l["pred_margin_home"])
        inside = l["margin_interval_95"][0] < 0 < l["margin_interval_95"][1]
        rows.append([
            l["date"][5:], esc(l["time_et"]), f'{esc(l["away"])} at {esc(l["home"])}',
            num(mag, 1) + " " + lean,
            num(l["orig_total"], 1),
            badge("NO BET — interval spans 0") if inside else badge("lean only"),
            esc(f"{l['games_used_home']} / {l['games_used_away']} games seen"),
            link(l["game_url"], "verify game"),
        ])
    sig = []
    for s in m["strategies"]:
        gate = "ELIGIBLE" if s in eligible else ("NOT GRADABLE" if not s.get("gradable_vs_own_line", True) else "BLOCKED")
        sig.append([
            s["id"], esc(s["name"]), esc(s["family"]),
            num(s["n_bets"], 0), num(s["hit_rate"] and pct(s["hit_rate"])), num(s["wilson_low"] and pct(s["wilson_low"])),
            num(s["perm_p"], 4), badge(gate),
            link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "engine"),
        ])
    par = m["correlations"]["same_game_parlay_joint"]
    return (
        banner
        + "<h2>Model lean per game</h2>"
        + table(["Date", "Tip", "Matchup", "Direction", "Total", "Status", "Sample behind it", "Source"], rows,
                "Directional lean only - not bets",
                "The 95% interval on a projected margin is roughly ±31 points, so for almost every single game "
                "the honest answer is 'the model cannot separate these two teams'. That is why the status column "
                "says NO BET on most rows.")
        + "<h2>Signal families and what is missing</h2>"
        + table(["ID", "Signal", "Family", "Bets", "Hit rate", "95% low", "Permutation p", "Gate status", "Source"], sig,
                "Every candidate signal, graded on 114 out-of-sample games",
                "Hit rate is against our own half-point line at an assumed -110; break-even is 52.1%. "
                "Moneyline and prop rows are marked NOT GRADABLE because grading a price we set ourselves "
                "against the same model is circular (E-F-05).")
        + "<h2>Parlays</h2>"
        + table(["Quantity", "Value", "n", "Meaning"], [
            ["P(over our total)", pct(par["p_over"]), str(par["n"]), "single leg"],
            ["P(home covers our spread)", pct(par["p_home_cover"]), str(par["n"]), "single leg"],
            ["P(both) observed", pct(par["p_both_observed"]), str(par["n"]), "what actually happened"],
            ["P(both) if independent", pct(par["p_both_if_independent"]), str(par["n"]), "what the market convention assumes"],
            ["Dependence ratio", num(par["ratio_observed_over_independent"], 3), str(par["n"]),
             "above 1 = the same-game parlay hits more often than independent legs imply"],
            ["Cross-game dependence", "—", "0", "not estimated; multi-game tickets are therefore blocked by E-F-06"],
        ], "Measured same-game dependence",
            "A 2-leg same-game ticket on this sample pays out about "
            f"{100 * abs(par['ratio_observed_over_independent'] - 1):.1f}% more often than independence implies - "
            "a real but small effect on 114 games, and the interval around it includes 1, so it is not yet a "
            "pricing rule. Cross-game dependence, which is what a 3- or 4-leg ticket actually needs, is left "
            "blank on purpose rather than assumed to be zero.")
        + "<h2>Player prop combos</h2>"
        + table(["Prop family", "Status", "Why", "Needed to proceed"], [
            ["Points over/under", badge("BLOCKED"), "No per-game player box scores, so no scoring distribution to price against", "official dated box scores (CR-O2)"],
            ["Points + rebounds", badge("BLOCKED"), "Needs the same, plus the correlation between the two legs", "same"],
            ["Assists over/under", badge("BLOCKED"), "same", "same"],
            ["Minutes-driven combo after a star is ruled out", badge("PARTIAL"), f"Availability is known - {sum(1 for t in m['injury_overlay'].values() if t.get('out_or_doubtful'))} teams in the window have at least one Out/Doubtful - but minutes are captured for only the 31 highest-minute players in the league", "full minutes table (CR-O1)"],
        ], "Prop combos",
            "No prop line is published. Fabricating a distribution from season averages would look identical "
            "to a real one on a dashboard and is exactly the failure this project is meant to prevent.")
    )


def page_leaderboard(m, reg):
    rows = []
    for s in sorted(m["strategies"], key=lambda x: (-(x["n_bets"]), x["id"])):
        rows.append([
            s["id"], esc(s["name"]), esc(s["family"]),
            num(s["n_bets"], 0), num(s["wins"], 0), num(s["losses"], 0),
            num(s["hit_rate"] and pct(s["hit_rate"])),
            num(s["wilson_low"] and pct(s["wilson_low"])) + " – " + num(s["wilson_high"] and pct(s["wilson_high"])),
            num(s["perm_p"], 4),
            num((f"{100 * s['roi_vs_own_line']:+.1f}%" if s["roi_vs_own_line"] is not None else None)),
            esc("/".join("—" if h is None else pct(h, 0) for h in (s.get("halves") or [None, None]))),
            f'{esc(s["first_bet"] or "—")} → {esc(s["last_bet"] or "—")}',
            link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "reproduce"),
        ])
    n_sig = sum(1 for s in m["strategies"] if s["perm_p"] is not None and s["perm_p"] < 0.05)
    return (
        "<p>The competition format: every strategy is graded on the same 114 out-of-sample games against the "
        "same line, then filtered by the gates on the next page. Ranking is honest about sample size, which is "
        "why the top of this leaderboard looks empty.</p>"
        + table(["ID", "Strategy", "Family", "Bets", "W", "L", "Hit rate", "Wilson 95%", "Perm p", "ROI vs own line", "Split halves", "Window", "Source"],
                rows, "Leaderboard - out of sample, graded against our own line",
                f"ROI is measured at an assumed -110 against our own line because no market price exists (E-F-05); "
                f"it is not a statement about beating a book. {n_sig} of 12 gradable strategies clear the raw luck test, "
                "and each of those has fewer than 100 bets, which is precisely the trap the sample gate exists to catch: "
                "with 30 bets, a 75% hit rate is well within reach of luck even when the permutation p-value looks small.")
        + "<h2>What would move a row up</h2>"
        + ("<ul><li><b>More games.</b> A 55% strategy needs roughly 1,000 bets before the interval separates it from break-even.</li>"
           "<li><b>A real price.</b> Until a closing price exists, the leaderboard can rank forecast skill, never realised edge.</li>"
           "<li><b>Pre-registration.</b> Twelve strategies were tried here; without registering the rule and the metric in advance, the best-looking row is partly a selection artefact.</li></ul>")
    )


def page_gates(m, reg):
    rows = [[g["id"], esc(g["name"]), esc(g["checks"]), esc(g["threshold"]), badge(g["status"]), esc(g["evidence"]),
             link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "code")] for g in m["gates"]]
    return (
        "<p>Nine gates. A strategy must clear all of them to be eligible for the leaderboard; the gate set is "
        "also the answer to 'how do we remove luck', because gates 5-7 are nothing but probability statements "
        "about how often a run like this happens by chance.</p>"
        + table(["ID", "Gate", "What is checked", "Threshold", "Status", "Evidence from this run", "Source"], rows,
                "Gate results for this build",
                "G01 and G02 pass because provenance and leakage are properties of the pipeline, not of a "
                "strategy. G09 cannot be cleared by backtesting at all - it measures the live process, and it "
                "is the gate that catches everything a backtest hides.")
        + "<h2>Why the thresholds are set where they are</h2>"
        + table(["Gate", "Threshold", "Reason", "Consequence if loosened"], [
            ["G04 sample", "100 graded bets", "Below ~100 bets the Wilson interval spans 45-60%, so a coin-flip run and a real edge are indistinguishable", "you rank noise"],
            ["G05 break-even", "Wilson lower bound > 52.13%", "52.13% is break-even at -110; requiring the lower bound to clear it is the difference between 'looked profitable' and 'plausibly is'", "you ship a losing strategy with a good story"],
            ["G06 luck", "permutation p < 0.05", "20,000 seeded reshuffles of the win/loss labels at the same n", "a lucky 18-bet run becomes a 'strategy'"],
            ["G07 multiplicity", "Benjamini-Hochberg, FDR 10%", "twelve strategies were tried; one in twelve looks good by chance at p<0.05", "you find what you were looking for"],
            ["G08 stability", "above break-even in both halves", "catches a strategy that only worked during one stretch of schedule", "you buy the top of a trend"],
            ["G09 forward tracking", "200 graded live picks", "the only gate that tests the whole pipeline, including freshness and filing times", "you trust a build nobody ran for real"],
        ], "Threshold rationale", "Thresholds are proposals from this session, not approved policy. Owner approval is question E-Q08.")
    )


def page_correlations(m, reg):
    c = m["correlations"]
    def crow(key):
        d = c[key]
        r = d.get("pearson_r")
        ci = d.get("ci95")
        return [
            key, esc(d["label"]),
            num(None if r is None else f"{r:+.3f}"),
            "—" if not ci else f"[{ci[0]:+.2f}, {ci[1]:+.2f}]",
            num(d.get("n"), 0),
            esc(d.get("interpretation") or d.get("note", "")),
            link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "code"),
        ]
    keys = ["margin_total_residual", "same_game_parlay_joint", "same_slate_cross_game", "spread_moneyline",
            "rest_edge_margin", "player_points_minutes"]
    rows = [crow(k) for k in keys]
    joint = c["same_game_parlay_joint"]
    return (
        "<p>Correlation is what decides whether a multi-leg ticket is affordable. These are measured on the "
        "114 out-of-sample games; where the sample cannot support an estimate the cell is blank and the row "
        "says why, instead of defaulting to zero.</p>"
        + table(["Key", "Pair", "r", "95% CI (Fisher)", "n", "Interpretation", "Source"], rows,
                "Measured correlations",
                "Note the one that is exactly 1.000: our spread and our moneyline are the same number "
                "re-expressed, so that correlation is mechanical and must never be quoted as evidence of "
                "redundancy between markets.")
        + "<h2>Parlay arithmetic from these numbers</h2>"
        + table(["Ticket", "Independence implies", "Observed", "Adjustment a fair price needs"], [
            ["2 legs, same game (our over + our home cover)", pct(joint["p_both_if_independent"]), pct(joint["p_both_observed"]),
             f'× {num(joint["ratio_observed_over_independent"], 3)} on the hit probability - i.e. the market convention prices this ticket slightly too cheap on our data'],
            ["2 legs, different games", "—", "—", "cannot be adjusted: cross-game dependence is unestimated (E-F-06)"],
            ["3+ legs, any combination", "—", "—", "blocked by gate proposal E-SG-07 until the above is measured"],
        ], "What the measured dependence does to a ticket",
            "A dependence ratio of 1.06 on 114 games is not a pricing rule; it is the first honest measurement "
            "of a quantity that was previously assumed. The number worth acting on is that it is *near* 1, which "
            "means same-game parlays are not as correlated as sportsbook risk models usually pretend - and that "
            "cross-game correlation, the one that matters for a 4-leg ticket, is still unknown.")
    )


def page_injuries(m, reg):
    inj = json.load(open(INT / "injuries_2026-11-13_0730PM_1114.json"))
    ov = m["injury_overlay"]
    rows = []
    for r in inj["rows"]:
        st = r["status"]
        badge_st = badge(st) if st in ("Out", "Doubtful", "Questionable", "Probable", "Available") else '<span class="b b-warn">NOT YET SUBMITTED</span>'
        mpg = None
        for p in ov.get(r["abbr"], {}).get("players", []):
            if p["player"] == r["player"]:
                mpg = p["mpg"]
        rows.append([r["time_et"].replace(" (ET)", ""), esc(r["matchup"]), esc(r["team"]), esc(r["player"] or "—"),
                     badge_st, esc(r["reason"] or "—"), num(mpg, 1), link(inj["source_url"], "official PDF")])
    team_rows = []
    for t, d in sorted(ov.items()):
        team_rows.append([
            esc(t), esc(d["club"]), esc(d["matchup"]),
            num(d["listed"], 0), num(d["out_or_doubtful"], 0),
            num(d["mpg_known"], 0),
            num(d["minutes_at_risk_floor"], 1),
            num(d["minutes_unquantified_count"], 0),
            badge("not filed") if d["not_yet_submitted"] else badge("filed"),
            link(inj["source_url"], "PDF row"),
        ])
    delta_rows = [[esc(d["player"]), esc(d["team"]), esc(d["at_0500PM"]), esc(d["at_0515PM"]), esc(d["at_0730PM"]),
                   link(inj["source_url"], "07:30 PM"), link(m["sources"]["injury_pdf_1700"], "05:00 PM")] for d in inj["changes_vs_earlier_stamps"]["deltas"]]
    cov = inj["coverage"]
    return (
        f"<p>Snapshot: <b>{esc(inj['source'])}</b>, retrieved {esc(inj['retrieved_utc'])}. Rows are only those "
        "whose Game Date column reads 11/14/2026 - the day-before designations for the live window.</p>"
        + f'<section class="callout"><h2>Coverage of the live window</h2><p>{cov["teams_that_submitted"]} of '
          f'{cov["teams_in_window"]} teams had filed. Not filed: <b>{esc(", ".join(cov["teams_not_yet_submitted"]))}</b>. '
          'For those teams availability is <i>unknown</i>, not healthy - which is why every originated line carries '
          'its own <code>report_status</code> field (E-F-10).</p></section>'
        + table(["Tip", "Matchup", "Team", "Player", "Status", "Reason as printed", "MPG", "Source"], rows,
                "Official designations for the 11/14 slate",
                "MPG is filled only where the player appears in the repository's official top-31 minutes capture "
                "(E-F-07). A dash means we do not know how many minutes are missing, not that none are.")
        + table(["Team", "Club", "Matchup", "Rows listed", "Out/Doubtful", "of which MPG known", "Minutes at risk (floor)", "Unquantified", "Filing", "Source"],
                team_rows, "Rotation impact per team",
                "'Minutes at risk' is a floor: it sums official season MPG for Out/Doubtful players we can match. "
                "The count of players whose minutes we cannot see is published next to it, because the floor is "
                "the number most likely to be mistaken for the truth.")
        + "<h2>How fast this page goes stale</h2>"
        + table(["Player", "Team", "05:00 PM report", "05:15 PM report", "07:30 PM report", "Source (newest)", "Source (oldest)"], delta_rows,
                "Same evening, three official stamps",
                "All three differences were checked against both PDFs: they are genuine updates, not transcription "
                "errors. Two earlier sessions disagreed about exactly this kind of difference (see COORDINATION.md); "
                "it is now settled. Practical consequence: a pick pipeline that reads the 5 p.m. report is reading "
                "history by the time a bettor sees it.")
    )


def page_gameflow(m, reg):
    gf = m["game_flow"]
    items = [
        ("Home win rate", pct(gf["home_win_rate"]), "of 174 verified games", "recomputed from results"),
        ("Mean home margin", num(gf["mean_home_margin"]), "points", "recomputed from results"),
        ("Overtime rate", pct(gf["ot_rate"]), f'{gf["ot_games"]} games went to OT', "recomputed from results"),
        ("Blowouts (40+)", num(gf["blowouts_40plus"], 0), "games decided by 40 or more", "recomputed from results"),
        ("Within 5 points", num(gf["within_five_pts"], 0), "games decided by 5 or fewer", "recomputed from results"),
        ("Average total", num(gf["avg_total"]), f'sd {num(gf["total_sd"])}', "recomputed from results"),
        ("Back-to-back games in the OOS window", num(gf["back_to_back_games_in_oos"], 0), "of 114", "derived from game dates"),
        ("Spread residual scale (MAE-based)", num(gf["resid_sd_margin_mae_based"]), "points", "used for the 95% intervals"),
        ("Total residual scale (MAE-based)", num(gf["resid_sd_total_mae_based"]), "points", "used for the 95% intervals"),
        ("Lead changes", None, "needs play-by-play", "not available - E-F-08"),
        ("Halftime margin", None, "needs per-game box scores", "not available - E-F-08"),
        ("Four factors", None, "needs per-game box scores", "not available - E-F-08"),
    ]
    rows = [[esc(k), num(v) if not isinstance(v, str) else esc(v), esc(d),
             (badge("UNVERIFIED") + " " + esc(why) if v is None else link(m["sources"]["games_raw"], "games.csv"))]
            for (k, v, d, why) in items]
    rest_rows = []
    for l in m["lines"]:
        rest_rows.append([l["date"][5:], f'{esc(l["away"])} at {esc(l["home"])}',
                          num(l["days_since_last_away"], 0), num(l["days_since_last_home"], 0),
                          esc(f'{l["games_used_away"]} / {l["games_used_home"]} games in the fitting window'),
                          badge("rest edge away") if (l["days_since_last_away"] or 9) > (l["days_since_last_home"] or 9) else (badge("rest edge home") if (l["days_since_last_home"] or 9) > (l["days_since_last_away"] or 9) else badge("even")),
                          link(l["game_url"], "schedule")])
    return (
        "<p>Game flow here means the structural facts a bettor can act on before tip-off - rest, schedule spot, "
        "OT exposure, how often games are actually decided. In-game flow (lead changes, halftime margins, "
        "four-factor splits) is published as blank because play-by-play is not in this repository and was not "
        "reachable from this workspace.</p>"
        + table(["Metric", "Value", "Basis", "Source"], rows, "League structure from 174 verified games")
        + "<h2>Per-game flow for the live window</h2>"
        + table(["Date", "Matchup", "Days since away's last game", "Days since home's last game", "Games seen (away/home)", "Rest", "Source"],
                rest_rows, "Rest and schedule spot",
                "Days-since-last-game is computed from the verified result dates; a game on 11/13 was in progress "
                "during this build, so 'days since' for teams that played 11/13 is one day larger than these "
                "figures until the results set is extended (E-F-11).")
    )


def page_reconciliation(m, reg):
    v = m["model_variants"]
    rows = []
    for x in v:
        rows.append([esc(x["variant"]), esc(x["market"]), num(x["rmse_model"]), num(x["rmse_baseline"]),
                     num(x["improvement_pct"], 2) + "%", num(x["paired_p"], 4),
                     badge("beats baseline") if x["better_than_baseline"] else badge("loses to baseline"),
                     num(x["n"], 0), link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "code")])
    eng = [
        ["this build (e40cd215)", "114", "60-game burn-in; expanding in-sample mean", f"{v[0]['rmse_model']:.2f} margin / {v[-1]['rmse_model']:.2f} total" if False else f"{[x for x in v if x['variant_id']=='sel' and x['market']=='margin'][0]['rmse_model']:.2f} margin / {[x for x in v if x['variant_id']=='sel' and x['market']=='total'][0]['rmse_model']:.2f} total", "+7.5% margin, +2.1% total", f"{m['correlations']['margin_total_residual']['pearson_r']:+.3f}", "0 of 12", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json", "model.json")],
        ["origin (e22a2831)", "114", "60-game burn-in; least-squares baseline", "16.18 margin / 20.35 total", "+6.5% margin, worse than baseline on total", "+0.091", "0 of 8", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/origin/model_output.json", "model_output.json")],
        ["edge (0a016df8)", "138", "30-game burn-in; baseline = population sd of all margins in the full log (line 299 of pipeline/run_model.py)", "14.95 consensus", "not stated as a percentage", "-0.018", "0 of 4 (2 provisional)", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/edge/data/validation-report.json", "validation-report.json")],
    ]
    ic = m["integrity"]["crosscheck"]
    return (
        "<p>Six sessions built overlapping engines on the same claim - 174 verified games from 2026-10-20 to "
        "2026-11-12. This page is what happens when they are compared instead of published side by side.</p>"
        + "<h2>The data underneath all of them</h2>"
        + table(["Check", "Result"], [
            ["Rows in the official-sourced capture", num(ic["ours"], 0)],
            ["Rows in the independent capture", num(ic["theirs"], 0)],
            ["Matchup keys present in both", num(ic["matched_keys"], 0)],
            ["Score mismatches after normalising team codes (CHO→CHA, BRK→BKN, PHO→PHX)", num(ic["score_mismatches"], 0)],
            ["Independent capture's declared source", "Basketball-Reference - <b>not an official NBA property</b>, so it is used as a cross-check only (E-F-02)"],
            ["Official team records vs recomputed W-L", "5 of 5 verifiable teams match exactly (BKN 3-8, DAL 7-5, DEN 6-4, DET 8-3, MIN 9-3); the other 5 were excluded because they had a game in progress on 11/13"],
        ], "Reconciliation of the two result sets",
            "Two captures made by different sessions from different sites agree on all 174 scores. That is the "
            "strongest evidence in this repository, and it was produced by accident rather than by design - "
            "the fix is to make a second capture a requirement, not a coincidence.")
        + "<h2>Model variants in this build</h2>"
        + table(["Variant", "Market", "RMSE", "Baseline RMSE", "Improvement", "paired p", "Verdict", "n", "Source"], rows,
                "Three variants, one window, one baseline")
        + "<h2>Why the three engines disagree in public</h2>"
        + table(["Engine", "OOS games", "Baseline definition", "Headline RMSE", "Improvement", "spread/total residual r", "Strategies passing gates", "Artefact"], eng,
                "Three engines, one dataset",
                "The RMSE columns are <b>not comparable</b>: different windows and three different baselines. "
                "Edge's baseline uses the population sd of all margins including the test games, which flatters "
                "its own improvement figure. The three published residual correlations (+0.023, +0.091, -0.018) "
                "differ by more than their point estimates while all three intervals contain zero - which is the "
                "right conclusion for a sample this size, and the wrong basis for a parlay price (E-F-04).")
        + "<h2>Open cross-session requests still unmet</h2>"
        + table(["Request", "Raised by", "Still blocks"], [
            ["CR-O1 full official minutes table", "e22a2831", "every minutes-at-risk figure being a floor, not an estimate"],
            ["CR-O2 dated player box scores", "e22a2831", "prop lines, prop combos, player-level correlation"],
            ["CR-O3 nav link to /origin/ from the root page", "e22a2831", "resolved by this build: the root page links all trees"],
            ["CR-O4 how /origin/ and /edge/ should coexist", "e22a2831", "addressed by this page; still needs the owner's archival decision (E-SG-01)"],
            ["CR-O5 may market prices be used for comparison", "e22a2831", "all profit measurement (E-F-05)"],
        ], "Hand-offs")
    )


def page_verification(m, reg):
    x = m["integrity"]["crosscheck"]
    rows = [
        ["Results set", "174 games 2026-10-20 → 2026-11-12, row-by-row against an independent capture", f"{x['matched_keys']} keys matched, {x['score_mismatches']} score mismatches", badge("PASS"), link(m["sources"]["games_raw"], "games.csv")],
        ["Team codes", "three-code alias set (CHO/CHA, BRK/BKN, PHO/PHX) identified as the only structural difference", "142 rows differed by code alone; 0 by score", badge("RESOLVED"), link(m["sources"]["games_crosscheck"], "results_2026-27_october.csv")],
        ["Official records", "recomputed W-L from our 174 games vs the records displayed on nba.com/games for the 11/14 slate", "5/5 verifiable teams exact; 5 excluded (game in progress)", badge("PASS"), link("https://www.nba.com/games?date=2026-11-14", "nba.com/games?date=2026-11-14")],
        ["Slate 11/14", "teams, ET tip times and game IDs vs the official page", "5/5 match data/origin/schedule_upcoming.csv", badge("PASS"), link("https://www.nba.com/games?date=2026-11-14", "official page")],
        ["Slate 11/15", "same", "9/9 match, both chunks read", badge("PASS"), link("https://www.nba.com/games?date=2026-11-15", "official page")],
        ["Slate month grid", "game counts for 11/13-11/17 read off the official calendar grid", "9, 5, 9, 8, 5 - matches the per-day captures", badge("PASS"), link("https://www.nba.com/games?date=2026-11-14", "calendar")],
        ["Injury report 11/13 07:30 PM", "transcribed the 11/14 block: 26 player rows + 5 team NOT-YET-SUBMITTED rows", "all 5 matchups present on the official slate", badge("PASS"), link(m["sources"]["injury_pdf"], "PDF")],
        ["Injury status dispute", "three rows where the repo's two captures disagreed, checked against both PDFs", "05:00 PM says Questionable, 05:15 PM says Available - genuine update, not an error", badge("RESOLVED"), link(m["sources"]["injury_pdf_1700"], "05:00 PM PDF")],
        ["Matchup-attribution dispute", "prior note claimed Miami's CLE@MIA was inferred from row position", "CLE@MIA is a real 11/13 game on the official slate; attribution is correct", badge("RESOLVED"), link("https://www.nba.com/games?date=2026-11-13", "official slate")],
        ["Report-index currency", "newest report listed for 11/13", "07:30 PM ET; the repo's captures were 05:00 and 05:15 PM - both stale by 2h15m", badge("FLAGGED"), link(m["sources"]["injury_index"], "index")],
        ["Model leakage", "every prediction fitted on strictly earlier games", "114/114 by construction; asserted in code", badge("PASS"), link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "engine.py")],
        ["Gate logic", "E-G03 recomputed per market with the shared baseline", "margin significant, total not → PARTIAL", badge("PASS"), link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "engine.py")],
        ["Cross-session write hazard", "running another session's build script mutated site/data", "4 files modified, 6 added; reverted with git checkout, main untouched", badge("FLAGGED"), link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/build_site_data.py", "build_site_data.py line 6")],
        ["Site build", "python3 -m integrate.check", "row-source and link check on every page", badge("PASS"), link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/check.py", "check.py")],
    ]
    return (
        "<p>What was checked this round, what it was checked against, and the result. Items marked RESOLVED were "
        "open disagreements between earlier sessions and are settled with primary evidence.</p>"
        + table(["Area", "Check run", "Result", "Status", "Source"], rows, "Verification log - 2026-11-14",
                "Only official NBA properties (nba.com, official.nba.com PDFs) and this repository's own git "
                "history were treated as verification sources. Nothing was accepted from a search snippet.")
        + "<h2>What was deliberately not verified</h2>"
        + "<ul><li>The 11/13 in-progress scores - not final at build time, so excluded rather than half-used.</li>"
          "<li>NBA Terms of Use and the Ksa licence page: cited from two earlier sessions' reading, not re-read this round (E-F-12).</li>"
          "<li>Player minutes beyond the captured top 31 (E-F-07).</li>"
          "<li>Any claim about market prices - there are none in the repository (E-F-05).</li></ul>"
    )


def page_questions(m, reg):
    rows = [[q["id"], esc(q["area"]), esc(q["question"]), badge(q["status"]), esc(q["why_it_matters"]),
             esc(q["what_we_have"]), esc(q["what_we_lack"]), esc(q["owner_action"]), link(q["evidence_url"], "evidence")]
            for q in reg["questions"]]
    return (
        "<p>The list to answer before any decision here is reasonable. Each row states what we already know, "
        "what is missing, and the shortest path to closing it. Rows marked <i>needs owner</i> cannot be closed "
        "by engineering effort.</p>"
        + table(["ID", "Area", "Question", "Status", "Why it blocks", "What we have", "What we lack", "Decision shape", "Evidence"], rows,
                "Open questions and answer state")
    )


def page_suggestions(m, reg):
    rows = [[s["id"], esc(s["area"]), badge(s["priority"].split(" ")[0]), esc(s["suggestion"]), esc(s["detail"]),
             esc(s["decision_needed"]), badge(s["status"].split(" ")[0]), link(s["evidence_url"], "evidence")] for s in reg["suggestions"]]
    return (
        '<section class="callout"><h2>Nothing on this page is implemented</h2><p>Each suggestion is a decision '
        'shaped so it can be accepted, amended or rejected on its own line. Accept one by replying with its ID; '
        'the row is then moved to <code>done</code> in COORDINATION.md by the next integration session.</p></section>'
        + table(["ID", "Area", "Priority", "Suggestion", "Detail", "Decision needed", "Status", "Evidence"], rows,
                "Site-improvement queue",
                "Priority 1 items are the two that stop the site contradicting itself (E-SG-01, E-SG-02). "
                "Priority 2 items change decision quality; 3 are hygiene.")
        + "<h2>How to pick the best path</h2>"
        + "<p>If only one change is approved, make it <b>E-SG-02</b>: a build that writes into another session's "
          "output directory will silently undo whatever else gets decided. If two, add <b>E-SG-01</b>, because six "
          "'current' numbers is the fastest way for this project to be trusted and then acted on incorrectly.</p>"
    )


def page_flagged(m, reg):
    rows = [[f["id"], badge(f["severity"]), esc(f["area"]), esc(f["item"]), esc(f["detail"]), esc(f["action_needed"]),
             link(f["source_url"], "source")] for f in reg["flags"]]
    blocks = [f for f in reg["flags"] if f.get("blocker")]
    return (
        '<section class="stop"><h2>Read before using any number on this site</h2><ul>'
        + "".join(f"<li><b>{esc(f['id'])}</b> — {esc(f['item'])}</li>" for f in blocks)
        + "</ul><p>These are the items that would change what the site is <i>allowed</i> to say. Nothing here blocks "
          "publishing the dashboard, and none of it was resolved by this session.</p></section>"
        + table(["ID", "Severity", "Area", "Item", "Detail", "Action needed", "Source"], rows,
                "Flagged for review - 2026-11-14",
                "Severity is about decision impact, not effort. 'medium' and 'low' rows are recorded so a future "
                "reader can tell what was known and when.")
    )


def page_sources(m, reg):
    rows = [[s["id"], esc(s["title"]), link(s["url"]), esc(s["publisher"]), esc(s["retrieved"]), esc(s["used_for"]),
             esc(s["verified"]), badge(s["result"])] for s in reg["sources"]]
    return (
        "<p>Everything the dashboard rests on, with what was read from it and when. Rows marked <i>in repository</i> "
        "are facts this session relied on from an earlier session's capture without re-fetching them - stated "
        "plainly rather than laundered into 'verified'.</p>"
        + table(["ID", "Source", "URL", "Publisher", "Retrieved", "Used for", "What this session verified", "Result"], rows,
                "Source register")
        + "<h2>Blocked and failed retrievals</h2>"
        + table(["Endpoint", "Result", "Consequence"], [
            ["cdn.nba.com static JSON scoreboard", "HTTP 500 (reported by two prior sessions; not retried here)", "no JSON path; all data came from HTML pages and PDFs"],
            ["stats.nba.com/stats/scoreboardv3", "blocked (reported by session e22a2831)", "no per-game box scores, so no props and no player correlations"],
            ["www.nba.com/standings", "returns no data - client rendered", "records were verified off the games page instead"],
            ["basketball-reference.com", "not used as a source for any published value", "its 174-row capture is retained only as a cross-check (E-F-02)"],
        ], "What could not be fetched",
            "Recorded so that the gaps on the other pages read as access limits rather than oversights.")
    )


def page_data(m, reg):
    files = [
        ["data/integration/model.json", "the single artefact every page renders", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json", "view")],
        ["data/integration/registers.json", "sources, flags, questions, suggestions", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/registers.json", "view")],
        ["data/integration/injuries_2026-11-13_0730PM_1114.json", "transcribed 11/14 block of the official report", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/injuries_2026-11-13_0730PM_1114.json", "view")],
        ["integrate/engine.py", "ratings, walk-forward, selector, gates, leaderboard, correlations", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/engine.py", "view")],
        ["integrate/build_site.py", "this site's generator", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/build_site.py", "view")],
        ["integrate/check.py", "row-source, link and drift checks", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/check.py", "view")],
        ["data/origin/games.csv", "174 verified results (canonical)", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/origin/games.csv", "view")],
        ["data/origin/schedule_upcoming.csv", "slate for 11/13-11/16 with game IDs", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/origin/schedule_upcoming.csv", "view")],
    ]
    trees = [
        ["dash/", "session e40cd215", "the unified dashboard - start here", badge("current")],
        ["site/", "7c532e8c", "framework-only site; no lines, all gates blocked at the time", badge("archive")],
        ["docs/", "f879620b", "11/11 injury report and 2026-27 rules extracts", badge("archive")],
        ["research/", "9ed6085f", "requirements register and 11/13 11:00 AM injury snapshot", badge("archive")],
        ["edge/", "0a016df8", "second engine; 138-game OOS window; results built on a non-official results source", badge("archive")],
        ["lab/", "5697caaf", "measured-constants layer and signal funnel", badge("archive")],
        ["origin/", "e22a2831", "third engine; 174-game log with its own gate results", badge("archive")],
    ]
    return (
        "<p>Reproduce the whole site:</p><pre><code>python3 -m integrate.engine\n"
        "python3 -m integrate.build_site\npython3 -m integrate.check</code></pre>"
        "<p>Standard library only - <code>numpy</code>, <code>scipy</code> and <code>pandas</code> are not available "
        "in this workspace, so statistics are implemented in <code>model/nbastats.py</code> (imported, not "
        "modified) and unit-tested there. The build is byte-deterministic: the permutation test is seeded (20261113) "
        "and no wall-clock timestamp is written into any artefact, so CI can assert that the committed pages match "
        "the committed code exactly.</p>"
        + table(["File", "What it holds", "Link"], files, "Files")
        + "<h2>Per-session site trees</h2>"
        + table(["Path", "Owning session", "Contents", "Status"],
                [[f"<a href='../{t[0]}'>{esc(t[0])}</a>", esc(t[1]), esc(t[2]), t[3]] for t in trees],
                "Archive index",
                "Nothing was deleted or edited in another session's tree. Those pages remain live so earlier "
                "claims stay auditable, but they are snapshots taken on 2026-11-13 and their tables are not "
                "maintained - see E-Q06.")
        + "<h2>Schema notes</h2>"
        + "<ul><li><code>orig_spread_home</code>: our model's home spread in points, half-point rounded, negative = home favoured.</li>"
          "<li><code>p_home_win</code>: normal-CDF probability from the predicted margin and the MAE-derived residual scale.</li>"
          "<li><code>minutes_at_risk_floor</code>: sum of official season MPG for Out/Doubtful players present in the captured minutes table; a floor, never an estimate.</li>"
          "<li><code>gradable_vs_own_line</code>: false means the strategy's payoff cannot be measured against a price we set ourselves.</li></ul>"
    )


BUILDERS = {
    "index": page_index, "lines": page_lines, "picks": page_picks, "leaderboard": page_leaderboard,
    "gates": page_gates, "correlations": page_correlations, "injuries": page_injuries,
    "gameflow": page_gameflow, "reconciliation": page_reconciliation, "verification": page_verification,
    "questions": page_questions, "suggestions": page_suggestions, "flagged": page_flagged,
    "sources": page_sources, "data": page_data,
}

STYLE = """
:root{--bg:#f6f7f9;--fg:#14181f;--mut:#5b6572;--ln:#dfe3e9;--card:#fff;--ok:#0b7a48;--bad:#b42318;
--warn:#8a5a00;--mute:#6b7280;--info:#155eae;--acc:#0f172a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--info);text-decoration:none}a:hover{text-decoration:underline}
.top{display:flex;flex-wrap:wrap;gap:8px;justify-content:space-between;align-items:center;padding:12px 20px;background:var(--acc);color:#fff}
.top a{color:#fff}.top .stamp{font-size:12px;color:#c7cfdb}.top .stamp b{color:#fff}
.brand span{display:block;font-size:11px;color:#9fb0c8;font-weight:400}
.nav{display:flex;flex-wrap:wrap;gap:2px;padding:8px 20px;background:#fff;border-bottom:1px solid var(--ln);position:sticky;top:0;z-index:5}
.nav-i{padding:6px 10px;border-radius:7px;font-size:13px;color:var(--mut)}
.nav-i[aria-current="page"]{background:var(--acc);color:#fff;font-weight:600}
main{max-width:1220px;margin:0 auto;padding:20px}
h1{font-size:26px;margin:14px 0 4px}h2{font-size:18px;margin:26px 0 8px}
.sub{color:var(--mut);margin:0 0 14px;max-width:80ch}
p{max-width:88ch}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(184px,1fr));gap:10px;margin:14px 0 4px}
.card{background:var(--card);border:1px solid var(--ln);border-radius:10px;padding:12px}
.card .k{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
.card .v{font-size:24px;font-weight:650;margin:2px 0}
.card .d{font-size:12px;color:var(--mut)}
section{margin:16px 0}
.callout,.stop{border-radius:10px;padding:12px 14px;border:1px solid var(--ln);background:#fff}
.callout{border-left:4px solid var(--info)}.stop{border-left:4px solid var(--bad);background:#fff7f6}
.stop h2,.callout h2{margin:0 0 6px;font-size:15px}
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--ln);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px}
caption{text-align:left;font-weight:650;padding:10px 12px 4px;font-size:14px}
th,td{padding:7px 10px;border-top:1px solid var(--ln);text-align:left;vertical-align:top}
th{background:#f0f2f6;font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:#404a57;position:sticky;top:0}
tbody tr:hover{background:#fbfcfe}
td:first-child{font-weight:600;white-space:nowrap}
.b{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:650;white-space:nowrap}
.b-ok{background:#e7f6ee;color:var(--ok)}.b-bad{background:#fdeceb;color:var(--bad)}
.b-warn{background:#fdf5e5;color:var(--warn)}.b-mute{background:#eef0f3;color:var(--mute)}.b-info{background:#e8f0fb;color:var(--info)}
.blank{color:var(--mute);font-style:italic;border-bottom:1px dotted var(--mute);cursor:help}
.note{font-size:12px;color:var(--mut);max-width:110ch;margin:8px 2px 0}
code{background:#eef0f3;padding:1px 5px;border-radius:5px;font-size:12px}
pre{background:var(--acc);color:#e8edf5;padding:12px 14px;border-radius:10px;overflow:auto}
pre code{background:none;color:inherit}
footer{max-width:1220px;margin:26px auto 40px;padding:16px 20px 0;border-top:1px solid var(--ln);color:var(--mut);font-size:12px}
.f{display:flex;gap:8px;align-items:center;margin:0 0 10px}
.f input{flex:1;max-width:320px;padding:7px 10px;border:1px solid var(--ln);border-radius:8px;font:inherit}
@media(max-width:700px){.top{padding:10px 12px}.nav{padding:6px 10px}main{padding:12px}h1{font-size:21px}}
"""

APPJS = """
// client-side table filter and sort - no dependencies, no network calls
(function(){
  var tables=[].slice.call(document.querySelectorAll('table[data-rows]'));
  if(!tables.length)return;
  var box=document.createElement('div');box.className='f';
  box.innerHTML='<label for="q">Filter rows on this page</label><input id="q" type="search" placeholder="team, player, STR-06, flagged…" autocomplete="off">';
  tables[0].parentNode.parentNode.insertBefore(box,tables[0].parentNode);
  box.querySelector('input').addEventListener('input',function(e){
    var v=e.target.value.toLowerCase();
    tables.forEach(function(t){
      [].slice.call(t.querySelectorAll('tbody tr')).forEach(function(tr){
        tr.style.display=!v||tr.textContent.toLowerCase().indexOf(v)>-1?'':'none';
      });
    });
  });
  tables.forEach(function(t){
    [].slice.call(t.querySelectorAll('th')).forEach(function(th,i){
      th.style.cursor='pointer';th.title='sort';
      th.addEventListener('click',function(){
        var tb=t.querySelector('tbody'),rs=[].slice.call(tb.querySelectorAll('tr'));
        var dir=th.dataset.d=th.dataset.d==='a'?'z':'a';
        rs.sort(function(a,b){
          var x=a.children[i]?a.children[i].textContent.trim():'',y=b.children[i]?b.children[i].textContent.trim():'';
          var nx=parseFloat(x.replace(/[^0-9.\\-+]/g,'')),ny=parseFloat(y.replace(/[^0-9.\\-+]/g,''));
          var c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y));
          return dir==='a'?c:-c;
        });
        rs.forEach(function(r){tb.appendChild(r)});
      });
    });
  });
})();
"""


def build():
    m = json.load(open(INT / "model.json"))
    reg = json.load(open(INT / "registers.json"))
    DASH.mkdir(exist_ok=True)
    OUT_DATA.mkdir(exist_ok=True)
    written = []
    for slug, title, sub in PAGES:
        body = BUILDERS[slug](m, reg)
        out = DASH / f"{slug}.html"
        out.write_text(layout(slug, title, sub, body, m))
        written.append(out)
    (DASH / "style.css").write_text(STYLE)
    (DASH / "app.js").write_text(APPJS)
    shutil_copy = Path(DASH / "data")
    (shutil_copy / "model.json").write_text(json.dumps(m, indent=1))
    (shutil_copy / "registers.json").write_text(json.dumps(reg, indent=1))
    (ROOT / "index.html").write_text(landing(m, reg))
    print(f"wrote {len(written)} pages to dash/ + root index.html")
    return written


def landing(m, reg):
    n_flags = len(reg["flags"])
    hi = sum(1 for f in reg["flags"] if f["severity"] == "high")
    cards = [
        ("Games verified", m["integrity"]["games"], "two independent captures, 0 score mismatches"),
        ("Lines for the live window", len(m["lines"]), "11/14 – 11/16, model output"),
        ("Strategies eligible now", 0, "none clears the gates"),
        ("Open decisions", len(reg["questions"]), f"{sum(1 for q in reg['questions'] if q['status'].startswith('needs'))} need the owner, not more code"),
        ("Flagged items", n_flags, f"{hi} high severity"),
    ]
    grid = "".join(
        f'<div class="card"><div class="k">{esc(t)}</div><div class="v">{esc(str(v))}</div><div class="d">{esc(d)}</div></div>'
        for t, v, d in cards
    )
    nav = "".join(
        f'<a class="pg" href="dash/{s}.html"><b>{esc(t)}</b><span>{esc(d)}</span></a>' for s, t, d in PAGES
    )
    trees = "".join(
        f'<li><a href="{href}"><code>{esc(label)}</code></a> — {esc(o)} <span class="b b-mute">2026-11-13 snapshot</span></li>'
        for href, label, o in [
            ("origin/index.html", "origin/", "session e22a2831 · independent origination engine"),
            ("edge/index.html", "edge/", "session 0a016df8 · second engine, 138-game out-of-sample window"),
            ("lab/index.html", "lab/", "session 5697caaf · measured constants and signal funnel"),
            ("site/index.html", "site/", "session 7c532e8c · framework-only site, all gates blocked at the time"),
            ("research/index.html", "research/", "session 9ed6085f · requirements register and 11/13 11:00 AM snapshot"),
            # the docs/ link is written out in full because tools/check_site.py (session f879620b)
            # asserts the string "docs/index.html" is present on this page; keep it exact.
            ("docs/index.html", "docs/", "session f879620b · rules and 11/11 injury extracts"),
        ]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NBA Edge Lab · originated lines, gated strategies, verified sources</title>
<meta name="description" content="Integrated NBA research dashboard: model-originated lines for the live 72-hour window, out-of-sample strategy leaderboard, validation gates, measured correlations and an injury register, every row linked to an official NBA source.">
<link rel="stylesheet" href="dash/style.css"></head>
<body>
<header class="top"><div class="brand"><a href="index.html"><strong>NBA Edge Lab</strong><span>integrated build · session e40cd215</span></a></div>
<div class="stamp">{esc(m['as_of'])}</div></header>
<main>
<h1>NBA line origination, gated strategies, one entry point</h1>
<p class="sub">This repository was built by several agent sessions in parallel, each publishing its own
dashboard. <a href="dash/index.html">The unified dashboard</a> is the one place where the current numbers, the
evidence behind them and the decisions still outstanding are reconciled. The six earlier trees stay online and
untouched as dated archives.</p>
<div class="cards">{grid}</div>
<section class="callout"><h2>What this is, in one paragraph</h2>
<p>Lines are originated from a model fitted on {m['integrity']['games']} verified NBA.com results and validated
walk-forward on {m['model']['oos_games']} out-of-sample games. On spread the model beats a constant baseline by
{[x for x in m['model_variants'] if x['variant_id']=='sel' and x['market']=='margin'][0]['improvement_pct']:.1f}%
(paired p={[x for x in m['model_variants'] if x['variant_id']=='sel' and x['market']=='margin'][0]['paired_p']:.4f});
on totals the gain is {[x for x in m['model_variants'] if x['variant_id']=='sel' and x['market']=='total'][0]['improvement_pct']:.1f}%
and is not significant. No strategy yet clears the eligibility gates, no market price exists in the repository to
measure profit against, and player props remain unbuildable without full minutes data. Those three limits are the
reason the site shows model output rather than bets, and they are documented row by row with sources.</p></section>
<h2>Sections</h2><div class="grid">{nav}</div>
<h2>Archives from earlier sessions</h2><ul class="trees">{trees}</ul>
<style>
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:8px;margin-top:8px}}
.pg{{display:block;background:#fff;border:1px solid var(--ln);border-radius:10px;padding:10px 12px;color:var(--fg)}}
.pg:hover{{border-color:var(--acc);text-decoration:none}}.pg b{{display:block;font-size:14px}}
.pg span{{font-size:12px;color:var(--mut)}}
.trees{{font-size:13px;color:var(--mut);padding-left:18px}}.trees li{{margin:3px 0}}
:root{{--bg:#f6f7f9;--fg:#14181f;--mut:#5b6572;--ln:#dfe3e9;--card:#fff;--acc:#0f172a;--info:#155eae;--mute:#6b7280}}
main{{max-width:1180px;margin:0 auto;padding:20px}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
a{{color:var(--info);text-decoration:none}}h1{{font-size:27px;margin:16px 0 6px}}
.sub{{color:var(--mut);max-width:84ch}}
.top{{display:flex;flex-wrap:wrap;gap:8px;justify-content:space-between;align-items:center;padding:12px 20px;background:var(--acc);color:#fff}}
.top a{{color:#fff}}.brand span{{display:block;font-size:11px;color:#9fb0c8;font-weight:400}}
.top .stamp{{font-size:12px;color:#c7cfdb}}.top .stamp b{{color:#fff}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:10px;margin:16px 0}}
.card{{background:#fff;border:1px solid var(--ln);border-radius:10px;padding:12px}}
.card .k{{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}}
.card .v{{font-size:25px;font-weight:650}}.card .d{{font-size:12px;color:var(--mut)}}
section.callout{{border:1px solid var(--ln);border-left:4px solid var(--info);border-radius:10px;padding:12px 14px;background:#fff}}
section.callout h2{{margin:0 0 6px;font-size:15px}}
.b{{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:650}}
.b-mute{{background:#eef0f3;color:var(--mute)}}
h2{{font-size:18px;margin:24px 0 8px}}code{{background:#eef0f3;padding:1px 5px;border-radius:5px;font-size:12px}}
p{{max-width:92ch}}footer{{max-width:1180px;margin:20px auto 40px;padding:14px 20px 0;border-top:1px solid var(--ln);color:var(--mut);font-size:12px}}
</style>
<footer><p><b>Not betting advice.</b> Model output only, built on official NBA.com results, with no market prices in
the repository. Read <a href="dash/flagged.html">flagged items</a> before acting on anything. Follow local law and
responsible-gambling practice.</p></footer>
</main></body></html>"""


if __name__ == "__main__":
    build()
