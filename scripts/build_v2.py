#!/usr/bin/env python3
"""Render the v2 site: separate ``projection`` and ``bet`` surfaces.

The brief is emphatic that the two must never be mixed, so they are two
different pages with two different visual languages:

``v2/projection.html``
    Anything that may be shown without a claim of value: originated lines, the
    two estimators and the gap between them, rest and travel, injury context.
    Every price here is labelled as ours.

``v2/bet.html``
    The gated surface.  A rule appears here only if every statistical gate
    passes.  On this build the page's honest content is a table of rules and
    why each one fails, because none passes -- which is the correct output of a
    gate set that is actually being applied.

Nothing in the projection page links to a bet, and nothing in the bet page
repeats a projection as if it were a wager.

Standard library only.  Fails (non-zero exit) on a broken internal link, a
missing source link on a table row, or an ``http://`` URL.
"""

import html
import json
import os
import sys
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "v2", "build.json")
OUT = os.path.join(ROOT, "v2")

ERRORS = []


def err(msg):
    ERRORS.append(msg)


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def num(v, nd=2, blank="—"):
    if v is None or v == "":
        return blank
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return esc(v)


def pct(v, nd=1):
    if v is None:
        return "—"
    return f"{float(v) * 100:.{nd}f}%"


def ml(v):
    if v is None:
        return "—"
    return f"{int(round(float(v))):+d}"


def link(url, label=None):
    if not url:
        return '<span class="unverified">UNVERIFIED — no source link</span>'
    return (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(label or url)}</a>')


def table(headers, rows, table_id=None, require_source=True):
    out = ['<div class="table-wrap"><table>']
    if table_id:
        out.append(f'<caption id="{esc(table_id)}">{esc("")}</caption>')
    out.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>")
    for i, r in enumerate(rows):
        if require_source and 'href="https://' not in " ".join(str(c) for c in r):
            err(f"table '{table_id or headers[0]}' row {i}: no https source link")
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def callout(title, body, kind=""):
    cls = f"callout {kind}".strip()
    return f'<div class="{cls}"><p><strong>{title}</strong> {body}</p></div>'


def kv(pairs):
    return table(["Item", "Value"], [[k, v] for k, v in pairs], require_source=False)


# ---------------------------------------------------------------------------
NAV = [
    ("Start", [("Overview", "index.html"), ("Method", "method.html")]),
    ("Projection (safe to publish)", [
        ("Originated lines", "projection.html"),
        ("Game context: rest, travel, injuries", "context.html"),
    ]),
    ("Bet (gated)", [("Gated board", "bet.html")]),
    ("Audit", [
        ("Source & freshness gates", "gates.html"),
        ("Strategy leaderboard", "leaderboard.html"),
        ("Sealed ledger", "ledger.html"),
        ("Correlations", "correlations.html"),
        ("Flagged for review", "flagged.html"),
    ]),
]


def layout(title, category, body, subtitle="", active=""):
    nav = []
    for cat, items in NAV:
        ls = []
        for label, href in items:
            cls = ' class="active"' if href == active else ""
            ls.append(f'<a href="{href}"{cls}>{esc(label)}</a>')
        nav.append(f'<div class="nav-group"><span class="nav-cat">{esc(cat)}</span>'
                   f'<span class="nav-links">{" ".join(ls)}</span></div>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — NBA3 v2</title>
<meta name="description" content="NBA3 v2: two independent estimators, gated strategies, pre-registered and hashed, settled from official finals.">
<link rel="stylesheet" href="../app/assets/app.css">
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="../index.html"><span class="brand-mark">NBA3</span> v2 pipeline</a>
    <div class="stamp">Published surface: <strong>{esc(category)}</strong></div>
  </div>
</header>
<nav class="site-nav"><div class="wrap">{"".join(nav)}</div></nav>
<main class="wrap">
  <div class="page-head">
    <div class="crumb">{esc(category)}</div>
    <h1>{esc(title)}</h1>
    {f'<p class="lead">{subtitle}</p>' if subtitle else ''}
  </div>
{body}
</main>
<footer class="site-footer"><div class="wrap">
<p><strong>NBA3 v2</strong> — research, not betting advice. Every table row links to its official
source. Values that could not be confirmed are left blank and listed on the
<a href="flagged.html">flagged page</a>. The v1 dashboard is at
<a href="../index.html">the root index</a>.</p>
</div></footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
def page_index(d):
    g = d["gates"]
    b = d["board"]
    n_bet = len([e for e in b if e["verdict"]["may_be_a_bet"]])
    n_proj = len([e for e in b if e["verdict"]["may_publish_as_projection"]])
    leak = d["leakage_audit"]
    body = []
    body.append(f"""
<p>This is the second pipeline. It exists because the first one had a single model and a single
number, and a single number cannot tell you whether it is right or whether it is lucky. Here there
are <strong>two independent estimators</strong>, the gap between them is the headline, and the blend
is published underneath.</p>

{callout("Where the numbers stand.",
         f"{g['passed']} of {g['total']} source and freshness gates pass. "
         f"{len(b)} strategies are registered and backtested. "
         f"<strong>{n_proj}</strong> may be published as a projection and "
         f"<strong>{n_bet}</strong> may be offered as a bet.", "")}

<h2>The two estimators</h2>
<p>They are independent in the way that matters: different inputs, different arithmetic, no shared
quantity. If both read the same rating they would agree by construction and the disagreement — the
thing this pipeline is for — would always be zero.</p>
""")
    body.append(table(
        ["Estimator", "What it reads", "Out-of-sample margin RMSE", "Status", "Source"],
        [
            ["<strong>A</strong> result-based",
             "final margins only (ridge least squares on the game log)",
             num(d["error_summary"]["a_margin_rmse"]),
             '<span class="chip chip-ok">clean</span> fitted only on games strictly before each forecast',
             link("https://www.nba.com/schedule")],
            ["<strong>B</strong> efficiency-based",
             "official team advanced + opponent pages: possessions, points per possession, pace",
             num(d["error_summary"]["b_margin_rmse"]),
             '<span class="chip chip-warn">contaminated</span> single dated snapshot, see FV2-06',
             link("https://www.nba.com/stats/teams/advanced")],
        ],
        table_id="estimators"))

    body.append(callout(
        "Why B's number is not a result.",
        f"B is fitted on one team-statistics snapshot dated {esc(leak['snapshot_date'])} and used to "
        f"price all {leak['forecasts_before_snapshot']} games played before that date, so its error "
        f"carries information from the future. It cannot be quoted as an out-of-sample figure and "
        f"no rule that reads B is ranked. The fix is a per-date statistics history; until then A at "
        f"{num(d['error_summary']['a_margin_rmse'])} points is the only honest accuracy claim on "
        f"this site.", "warn"))

    body.append(f"""
<h2>Home-court advantage is pinned, not fitted</h2>
<p>The brief asks for HCA pinned to the measured home-win rate. That is what happens: a free
regression coefficient is not used anywhere.</p>
""")
    hc = d["home_court"]
    body.append(kv([
        ["Games measured", esc(hc["n_games"])],
        ["Home wins", esc(hc["home_wins"])],
        ["Measured home-win rate", pct(hc["home_win_rate"], 3)],
        ["Margin standard deviation", num(hc["margin_sd"])],
        ["<strong>HCA points</strong>", f"<strong>{num(hc['hca_points'])}</strong>"],
        ["Derivation", esc(hc["method"])],
        ["Caveat", esc(hc["note"])],
        ["Source", link("https://www.nba.com/schedule")],
    ]))

    body.append(f"""
<h2>The five numbers that matter</h2>
""")
    body.append(table(
        ["What", "Value", "Read it as"],
        [
            ["Home-court advantage", f"{num(hc['hca_points'])} pts",
             "pinned to the measured rate; not a fitted coefficient"],
            ["Margin error, estimator A", f"{num(d['error_summary']['a_margin_rmse'])} pts",
             "genuine out-of-sample; this is the unit the disagreement is measured against"],
            ["Total error, estimator B", f"{num(d['error_summary']['b_total_rmse'])} pts",
             "does not beat a constant league-average total — published worse, not hidden"],
            ["Best published edge over a coin", f"{num(max(x['scored'].get('edge_pp') or -99 for x in b))} pp",
             f"the board's luck threshold is {num(d['luck_threshold']['threshold_pp'])} pp"],
            ["Strategies that may be a bet", str(n_bet),
             "zero, because no licensed market price is connected to this repository"],
        ],
        table_id="five-numbers", require_source=False))
    return "\n".join(body)


def page_projection(d):
    body = [f"""
<p>Lines <strong>originated by this project</strong> for the
{esc(d['slate'][0]['date'])} → {esc(d['slate'][-1]['date'])} window. No licensed odds feed is
connected, so these are not market prices and no claim of value is made.</p>

{callout("Read the disagreement column first.",
         "The gap between the two estimators is the confidence signal. A small gap means two very "
         "different methods arrived at the same place; a large one means the game is a genuine "
         "argument between a result-based and an efficiency-based view of the same teams.", "")}
"""]
    rows = []
    for s in d["slate"]:
        dis = (s["disagreement"] or {}).get("spread") or {}
        line = s["originated_line"]
        inj = s.get("injury_status") or {}
        n_out = sum(1 for st in (inj.get("away") or {}).values() if st == "Out") + \
                sum(1 for st in (inj.get("home") or {}).values() if st == "Out")
        filed = ("both filed" if inj.get("away_team_filed") and inj.get("home_team_filed")
                 else ("home only" if inj.get("home_team_filed") else
                       ("away only" if inj.get("away_team_filed") else "neither filed")))
        rows.append([
            esc(s["date"]), esc(s["tip_note"] or "—"),
            f'<a id="{esc(s["game_id"])}"></a>{esc(s["away"])} @ {esc(s["home"])}',
            num((s["estimator_a"] or {}).get("margin")),
            num((s["estimator_b"] or {}).get("margin")),
            f'<strong>{num(dis.get("gap_points"))}</strong>',
            esc(s["agreement_label"]),
            f'{num(line["margin"])} / {num(line["total"])}',
            ml((s["probs"] or {}).get("home_fair_american")),
            ml((s["probs"] or {}).get("away_fair_american")),
            f'{esc(n_out)} out · {esc(filed)}',
            link(s["source_url"]),
        ])
    body.append(table(
        ["Date", "Tip (ET)", "Game", "A margin", "B margin", "Gap (pts)", "Agreement",
         "Our line (spread / total)", "Home ML", "Away ML", "Injuries", "Source"], rows,
        table_id="projection-lines"))

    body.append(callout(
        "What is <em>not</em> on this page.",
        "No stake, no unit, no expected profit, and no bet. This page is the projection surface: "
        "it says what the models think, not what anyone should do about it. The gated surface is "
        '<a href="bet.html">separate</a> and is deliberately empty.', "warn"))
    return "\n".join(body)


def page_context(d):
    body = ["""
<p>Rest, back-to-back, three-in-four and travel, computed from the official game log and a sourced
arena-coordinate table. None of it reads a model output.</p>
"""]
    rows = []
    for s in d["slate"]:
        for side in ("away", "home"):
            t = s["rest_travel"][side]
            rows.append([
                esc(s["date"]),
                f'{esc(s["away"])} @ {esc(s["home"])}',
                esc(side),
                esc(t["team"]),
                num(t["rest_days"], 0),
                "yes" if t["back_to_back"] else "no",
                esc(t["games_in_4_nights"]),
                "yes" if t["three_in_four"] else "no",
                num(t["travel_km"], 0),
                esc(t["previous_venue_team"] or "—"),
                link(s["source_url"]),
            ])
    body.append(table(
        ["Date", "Game", "Side", "Team", "Rest (days)", "B2B", "Games in 4",
         "3-in-4", "Travel (km)", "Last venue", "Source"], rows, table_id="rest-travel"))

    body.append(callout(
        "Travel is a lower bound.",
        "Distances are great-circle between arena coordinates from a secondary source (Wikipedia), "
        "not route mileage and not flight time. A zero means the team plays at home. The arena table "
        'is tiered SECONDARY, and the <a href="gates.html">source register</a> says so.', "warn"))

    body.append("""
<h2>Injuries, as filed</h2>
<p>The newest report the official index lists is the one parsed. Statuses are reproduced exactly;
a player the league lists as Out is Out here, and a team the league has not yet had file shows as
not filed rather than as having no injuries.</p>
""")
    rows = []
    for s in d["slate"]:
        inj = s.get("injury_status") or {}
        for side in ("away", "home"):
            team = s[side]
            statuses = inj.get(side) or {}
            filed = inj.get(f"{side}_team_filed")
            ordered = sorted(statuses.items(), key=lambda kv: (kv[1] != "Out", kv[0]))
            txt = "; ".join(f"{p} <em>{st}</em>" for p, st in ordered) or "—"
            rows.append([
                esc(s["date"]), f'{esc(s["away"])} @ {esc(s["home"])}', esc(team),
                ("filed" if filed else '<span class="unverified">NOT YET SUBMITTED</span>'),
                txt or "—",
                link(s["source_url"]),
            ])
    body.append(table(["Date", "Game", "Team", "Filed?", "Players listed", "Source"], rows,
                      table_id="injury-status"))

    body.append(callout(
        "The report revision time is on the page, not in a footnote.",
        f"File parsed: <code>{esc(d['inputs']['injury_report_file'])}</code>, revised "
        f"{esc(d['inputs'].get('injury_report_revision') or '—')}, retrieved "
        f"{esc(d['inputs']['injury_report_retrieved_utc'])}. "
        f"{esc(d['inputs']['injury_rows_unattributed'])} rows in the document carry no team in the "
        f"source and are refused rather than guessed at.", ""))
    return "\n".join(body)


def page_bet(d):
    body = [f"""
<p>This is the gated surface. A strategy appears as a bet only if it passes every gate: sufficient
sample, adequate power, exact-binomial significance, false-discovery control across the whole board,
half-to-half stability, an edge that clears the price actually paid, an edge above the board-wide
luck threshold, a pre-registration hash recorded before the first bet, and a real market price.</p>

{callout("There are no bets on this page, and that is the correct result.",
         "No licensed market price is connected to this repository, so the final gate fails for "
         "every rule by construction. Every edge on the board is measured against the project's own "
         "originated line and an assumed -110, which can tell you whether our own line is biased but "
         "cannot tell you whether a bookmaker would have paid.", "warn")}
"""]
    rows = []
    for e in d["board"]:
        v = e["verdict"]
        rows.append([
            f'<a href="leaderboard.html#{esc(e["rule"]["strategy_id"])}">{esc(e["rule"]["strategy_id"])}</a>',
            esc(e["rule"]["name"]),
            esc(e["rule"]["market"]),
            "yes" if v["may_be_a_bet"] else "<strong>no</strong>",
            "yes" if v["may_publish_as_projection"] else "no",
            esc(v["tier"]),
            esc(", ".join(v["failing"]) or "—"),
            link(e["rule"]["source_urls"][0]),
        ])
    body.append(table(["ID", "Rule", "Market", "May be a bet", "May be published", "Tier",
                       "Failing gates", "Source"], rows, table_id="bet-board"))
    return "\n".join(body)


def page_leaderboard(d):
    body = [f"""
<p>Every registered rule, scored on the walk-forward backtest, read against the gate set. The board
includes the exact mirror of every one-sided rule, so a rule cannot look skilful merely because its
sign happened to be right, and a null control that must show nothing.</p>

{callout("The luck threshold.",
         f"The best edge the same board would show if every rule had exactly zero skill, at the "
         f"95th percentile, is <strong>{num(d['luck_threshold']['threshold_pp'])} percentage "
         f"points</strong> (median {num(d['luck_threshold']['median_best_pp'])} pp), from "
         f"{d['luck_threshold']['iterations']:,} simulations over "
         f"{d['luck_threshold']['rules']} rules, seed {d['luck_threshold']['seed']}. A rule below it "
         f"has demonstrated that it was the luckiest of the board, not that it works.", "")}
"""]
    rows = []
    for e in d["board"]:
        s = e["scored"]
        rows.append([
            f'<a id="{esc(e["rule"]["strategy_id"])}">{esc(e["rule"]["strategy_id"])}</a>',
            esc(e["rule"]["name"]),
            esc(s.get("n")),
            pct(s.get("rate")),
            f'{num(s.get("rate_ci95", [None, None])[0] * 100 if s.get("rate_ci95") and s.get("rate_ci95")[0] is not None else None)}–'
            f'{num(s.get("rate_ci95", [None, None])[1] * 100 if s.get("rate_ci95") and s.get("rate_ci95")[1] is not None else None)}%',
            num(s.get("edge_pp")),
            num(s.get("edge_vs_breakeven_pp")),
            f'{num(s.get("p_two_sided_vs_coin"), 4)}' if s.get("p_two_sided_vs_coin") is not None else "—",
            num(e.get("q_value"), 4),
            ("<span class=\"chip chip-warn\">contaminated</span>"
             if e.get("contaminated") else "clean"),
            esc(e["verdict"]["tier"]),
            link(e["rule"]["source_urls"][0]),
        ])
    body.append(table(
        ["ID", "Rule", "n", "Hit rate", "95% CI", "Edge vs coin (pp)", "Edge vs price (pp)",
         "Exact p", "BH q", "Sample", "Tier", "Source"], rows, table_id="leaderboard"))

    body.append("""
<h2>Why so many rules have no sample</h2>
<p>Three reasons, and none of them is fixed by lowering a threshold after seeing the result:</p>
<ul>
<li><strong>No player data.</strong> The three prop rules need per-player game logs for a season.
Only two teams' top-8 minutes were captured and no logs exist, so the rules are registered and
BLOCKED, not quietly deleted.</li>
<li><strong>The signal never fires.</strong> The disagreement rules (S11, S12) need the estimators to
differ by more than their combined error. Across 131 walk-forward games they never did — the two
methods agree far more often than that, which is itself a finding about the models.</li>
<li><strong>Cross-game dependence is unmeasurable</strong> here, so the two-game parlay has no price
and cannot be graded.</li>
</ul>
""")
    body.append(callout(
        "The null control did its job.",
        "N01 is a coin flip. It returned a hit rate indistinguishable from chance, as it must. If it "
        "had shown an edge, the measurement would have been broken rather than the market.", ""))
    return "\n".join(body)


def page_ledger(d):
    counts = d["ledger_counts"]
    body = [f"""
<p>Every graded pick is sealed with a SHA-256 hash computed from the pick as issued, and the hash is
stored before the result. Recomputing it after settlement must reproduce it; if it does not, the
pick was edited.</p>
"""]
    body.append(kv([
        ["Rows sealed", esc(counts["n"])],
        ["Hashes that recompute exactly", esc(counts["all_hashes_match"])],
        ["Rows recorded as published before tip", esc(counts["published_before_tip"])],
        ["Pre-registration file", link("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/v2/registrations.json")],
    ]))
    body.append(callout(
        "Be precise about what is proved here.",
        f"All {counts['n']} rows recompute, so no pick has been altered since it was written. What is "
        f"<strong>not</strong> yet proved is that the picks existed before the games: these rows are "
        f"settled retroactively against already-played finals, and the ledger honestly records that "
        f"zero rows were published before tip. A live slate will produce the first forward-dated "
        f"rows.", "warn"))

    rows = []
    for r in d["ledger"][:60]:
        p = r["pick"]
        rows.append([
            esc(r["strategy_id"]), esc(p.get("date")), esc(p.get("game_id")),
            esc(p.get("side")), num(p.get("line")), ml(p.get("price_american")),
            f'<code>{esc(r["pick_sha256"][:16])}…</code>',
            esc(r["settlement"]),
            link(r["settlement_source"], "official final"),
        ])
    body.append(f'<h2>Most recent 60 of {counts["n"]} rows</h2>')
    body.append(table(["Strategy", "Date", "Game", "Side", "Line", "Price", "Pick hash",
                       "Settled", "Source"], rows, table_id="ledger"))
    return "\n".join(body)


def page_correlations(d):
    body = ["""
<p>Parlays are priced twice: the naive product, which assumes the legs are independent, and the
copula price at the measured correlation. Both are always printed. Where a correlation cannot be
measured, only the naive product is shown and it is labelled as an assumption.</p>
"""]
    rows = []
    for c in d["correlations"]:
        ci = c.get("ci95") or [None, None]
        rows.append([
            esc(c["pair"]),
            esc(c["stat"]),
            num(c["value"], 4),
            f'{num(ci[0], 4)} to {num(ci[1], 4)}',
            esc(c["n"]),
            esc(c["used_for"]),
            link(c["source_url"]),
        ])
    body.append(table(["Pair", "Statistic", "Value", "95% CI", "n", "What it is for", "Source"],
                      rows, table_id="correlations"))

    body.append("<h2>What cannot be measured here</h2>")
    body.append(table(["Pair", "Why not"],
                      [[esc(u["pair"]), esc(u["why"])] for u in d["correlations_unmeasurable"]],
                      table_id="unmeasurable", require_source=False))
    body.append(callout(
        "A correlation inside its own confidence interval of zero is not zero.",
        "It is 'not distinguishable from zero at this n', which is a weaker and more accurate "
        "statement. The parlay prices use the point estimate and say so.", "warn"))

    body.append("<h2>Worked parlay prices for the window</h2>")
    rows = []
    for r in d["parlays"]["rows"]:
        s = r["sgp"]
        rows.append([
            esc(r["date"]),
            f'<a href="projection.html#{esc(r["game_id"])}">{esc(r["game_id"])}</a>',
            pct(s.get("p_side"), 2),
            pct(s.get("p_total"), 2),
            num(s.get("naive_product"), 4),
            num(s.get("copula_price"), 4) if s.get("copula_price") is not None else "—",
            esc(s.get("dependence_ratio")),
            link(r["source_url"]),
        ])
    body.append(table(["Date", "Game", "Side leg", "Total leg", "Naive product",
                       "Measured-rho price", "Dependence ratio", "Source"], rows,
                      table_id="parlay-prices"))
    return "\n".join(body)


def page_gates(d):
    g = d["gates"]
    body = [f"""
<p>Nothing is published until the inputs pass. {g['passed']} of {g['total']} gates pass, evaluated
A blocking failure stops the build before any model runs, so a failing gate means no model output
was produced at all.</p>
<p class="note">The gate evaluation time is deliberately <strong>not</strong> printed here. It is the
only field in the build that changes between two runs on identical inputs, and a page that prints it
cannot be reproduced byte for byte — which would defeat the drift check that exists to catch a real
input change. The time is in <code>data/v2/build.json</code> under
<code>gates.evaluated_at_utc</code> for anyone who needs it.</p>
"""]
    rows = []
    for x in g["gates"]:
        rows.append([
            ('<span class="chip chip-ok">pass</span>' if x["ok"]
             else '<span class="chip chip-bad">FAIL</span>'),
            esc(x["name"]),
            ("blocking" if x["blocking"] else "warning"),
            esc(x["detail"]),
            link("https://official.nba.com/nba-injury-report-2026-27-season/")
            if "injury" in x["name"] else link("https://www.nba.com/schedule"),
        ])
    body.append(table(["Result", "Gate", "Kind", "What it measured", "Source"], rows,
                      table_id="gates"))

    body.append("<h2>What the freshness gate caught</h2>")
    body.append(f"""
<p>The 6:15 AM injury report was captured, parsed and ready to price the slate. While the build was
running, the official index started listing a <strong>6:30 AM</strong> report. The gate refused the
build, the newer document was captured, and the rebuild reads it by name — not "whichever file is
newest", which would let an old report ride a new timestamp.</p>
<p>The difference between the two revisions was a single spelling correction: the league fixed
"Embid" to "Embiid". <strong>Zero status changes.</strong> That distinction is published rather than
flattened, because a diff that reads a typo fix as one player vanishing and another appearing
invents two roster events out of a proofreading pass.</p>
""")
    body.append(kv([
        ["File parsed", esc(d["inputs"]["injury_report_file"])],
        ["Revised", esc(d["inputs"].get("injury_report_revision") or "—")],
        ["Retrieved", esc(d["inputs"]["injury_report_retrieved_utc"])],
        ["Status changes vs previous", esc(d["inputs"]["injury_delta_vs_0615"]["counts"]["changed"])],
        ["Spelling corrections", esc(d["inputs"]["injury_delta_vs_0615"]["counts"]["spelling_corrections"])],
        ["Rows parsed", esc(d["inputs"]["injury_rows_parsed"])],
        ["Rows the document leaves undated", esc(d["inputs"]["injury_date_recovery"]["rows_still_undated"])],
    ]))
    return "\n".join(body)


def page_method(d):
    marks = [esc(os.path.basename(s)) for s in sorted(
        __import__("glob").glob(os.path.join(ROOT, "pipeline", "v2", "*.py")))]
    body = [f"""
<p>Two independent estimators, disagreement published as the headline, blend underneath. This page
says how each piece works and, where a piece does not work, that it does not.</p>

<h2>Estimator A — result-based</h2>
<p>Ridge least squares on final margins, one team strength per team, with the home-court term
subtracted before the fit so it cannot be re-estimated inside it. Every forecast is made from games
dated strictly before the game being priced, and the home-court pin is recomputed from history at
each date too, so neither the ratings nor the pin see the future.</p>

<h2>Estimator B — efficiency-based</h2>
<p>Possessions times points per possession, from the official team advanced and opponent pages.
Never looks at a final margin, which is what makes it a genuinely different method rather than a
re-parameterisation of A.</p>

<pre>points per possession  = (points per game x games) / possessions
expected possessions   = (pace_home + pace_away) / 2
total                  = possessions x (ppp_home + ppp_away)
margin                 = possessions x (ppp_home - ppp_away) + hca_points</pre>

<p>The total is built that way on purpose. A total computed as the average of two team scoring
averages double-counts pace and cannot be corrected afterwards; the possession form at least has the
right units. It still does not beat a constant league total out of sample, and the site says so on
the page where the totals appear.</p>

<h2>Disagreement</h2>
<p>The headline number is the gap between the estimators in points, and beside it the same gap
divided by their combined error. Three points of disagreement when each method is typically wrong by
fifteen is nothing; three points when each is wrong by four is a real fight. Only the second
statement is worth acting on, so the label is computed from the ratio and the raw gap is never shown
alone.</p>

<h2>Gates</h2>
<p>Eleven gates per rule: provenance, look-ahead, sample, power, exact-binomial significance,
Benjamini-Hochberg control across the board, half-to-half stability, economics against the price
actually paid, the board-wide luck threshold, pre-registration, and whether a real market price
exists. The last one fails for everything, which is the honest state of a repository with no odds
feed.</p>

<h2>Ledger</h2>
<p>Each pick is hashed with SHA-256 over its canonical JSON before settlement; the hash is stored
and recomputed after. The strategy's own registration — signal, thresholds, universe, settlement
rule — is hashed the same way and frozen in <code>data/v2/registrations.json</code> on the first
build, so a rule cannot be re-stamped forward to stay ahead of a bet.</p>

<h2>Modules</h2>
<p>{", ".join(f"<code>{m}</code>" for m in marks)}</p>

<h2>Reproducibility</h2>
<p>The build is seeded and byte-identical across runs; a test asserts it. Two things had to be
pinned for that to be true — the publication timestamp to the minute, and the registration stamps to
a file written once.</p>

<h2>Known broken</h2>
<ul>
<li>The totals model does not beat a constant. Published as worse, not shrunk into looking fine.</li>
<li>Estimator B's backtest is contaminated by its single dated snapshot (FV2-06).</li>
<li>Player props and four of the nine correlation cells need per-player game logs that do not exist
in this repository.</li>
<li>The travel term is a great-circle lower bound from a secondary source, not route mileage.</li>
<li>No market price, so no rule can be shown to have value.</li>
</ul>
"""]
    return "\n".join(body)


def page_flagged(d):
    body = ["""
<p>Everything that could not be verified or that is known to be wrong. Nothing here blocks the site
from building; all of it blocks a claim.</p>
"""]
    rows = []
    for f in d["flags"]:
        rows.append([
            esc(f["id"]),
            ('<span class="chip chip-bad">' + esc(f["severity"]) + "</span>"),
            esc(f["flag"]),
            esc(f["detail"]),
            esc(f["fix"]),
            link("https://github.com/wingbangboozle1-lang/NBA3"),
        ])
    body.append(table(["ID", "Severity", "Flag", "Detail", "Fix", "Source"], rows,
                      table_id="flags"))

    body.append("<h2>Unattributed injury rows</h2>")
    body.append(f"""
<p>{esc(d['inputs']['injury_rows_unattributed'])} rows in the newest report sit on page fragments
where the league's own document prints no team, and are refused rather than assigned. They are
counted here so the omission is visible.</p>
""")
    return "\n".join(body)


PAGES = [
    ("index.html", "Overview", "Two estimators, published disagreement, gated strategies.", page_index),
    ("method.html", "Method", "How the pipeline works, and what is broken.", page_method),
    ("projection.html", "Projection", "Originated lines for the window. Safe to publish.", page_projection),
    ("context.html", "Context", "Rest, travel and injuries.", page_context),
    ("bet.html", "Bet", "The gated surface. Empty, correctly.", page_bet),
    ("leaderboard.html", "Audit", "Every rule against every gate.", page_leaderboard),
    ("ledger.html", "Audit", "Sealed picks and their hashes.", page_ledger),
    ("correlations.html", "Audit", "Measured dependence and parlay prices.", page_correlations),
    ("gates.html", "Audit", "Source and freshness gates.", page_gates),
    ("flagged.html", "Audit", "Known wrong and unverified.", page_flagged),
]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])


def main():
    with open(DATA, encoding="utf-8") as fh:
        d = json.load(fh)
    os.makedirs(OUT, exist_ok=True)
    written = []
    for name, cat, sub, fn in PAGES:
        doc = layout(_title(name), cat, fn(d), subtitle=sub, active=name)
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(doc)
        written.append(name)

    # link + anchor check
    ids_by_page = {}
    for name in written:
        p = Links()
        p.feed(open(os.path.join(OUT, name), encoding="utf-8").read())
        ids_by_page[name] = (p.hrefs, p.ids)
    for name, (hrefs, ids) in ids_by_page.items():
        for h in hrefs:
            if h.startswith("http://"):
                err(f"{name}: http:// link {h}")
            elif h.startswith("https://") or h.startswith("../") or h.startswith("mailto:"):
                continue
            elif h.startswith("#"):
                if h[1:] and h[1:] not in ids:
                    err(f"{name}: dead in-page anchor {h}")
            elif h.endswith(".html"):
                target, _, frag = h.partition("#")
                if not os.path.exists(os.path.join(OUT, target)):
                    err(f"{name}: dead link {h}")
                elif frag and target in ids_by_page and frag not in ids_by_page[target][1]:
                    err(f"{name}: dead anchor {h}")

    if ERRORS:
        print(f"v2 site check FAILED with {len(ERRORS)} error(s):", file=sys.stderr)
        for e in ERRORS[:40]:
            print("  " + e, file=sys.stderr)
        return 1
    print(f"wrote {len(written)} v2 pages to v2/")
    return 0


def _title(name):
    for n, _c, _s, _f in PAGES:
        if n == name:
            return {"index.html": "Overview", "method.html": "Method",
                    "projection.html": "Projection", "context.html": "Context",
                    "bet.html": "Bet — gated", "leaderboard.html": "Strategy leaderboard",
                    "ledger.html": "Sealed ledger", "correlations.html": "Correlations",
                    "gates.html": "Gates", "flagged.html": "Flagged"}[name]
    return name


if __name__ == "__main__":
    sys.exit(main())
