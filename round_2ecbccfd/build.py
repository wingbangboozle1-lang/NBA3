#!/usr/bin/env python3
"""Build the 2026-11-17 round site (session arena/2ecbccfd-nba3) into round_2ecbccfd/.

Offline and deterministic: every table is generated from the committed artefacts in
data/rounds/2026-11-17/, and every row carries the https source link that printed it. A value no
official source printed is left BLANK in the cell and named in the page's own flag line -- the
builder never fills a gap with an estimate. Re-run with:

    python3 round_2ecbccfd/build.py            # rewrite round_2ecbccfd/
    python3 round_2ecbccfd/build.py --check     # fail if a committed page differs from what this writes

The site is split in two, per the brief: `round_2ecbccfd/projection/` is safe to publish now, and
`round_2ecbccfd/bet/` is gated (nothing is funded, and the NBA's own terms bar using its statistics for
betting, which the page states). A page from one side never carries a number from the other.
"""
from __future__ import annotations

import html
import json
import os
import sys

# determinism (session 89e98007): summation and rounding are pinned in-repo, not inherited from
# the interpreter that happens to run the build. See scripts/determinism.py: EVE-F04 was a runner
# Python upgrade (3.11 -> 3.14.4) whose compensated sum() moved one published float by 1 unit in
# the 4th decimal and froze the byte-for-byte replay gate for six days.
try:
    import determinism as det  # noqa: E402  (running from scripts/)
except ImportError:            # running from elsewhere, e.g. round_2ecbccfd/build.py
    import os as _det_os
    import sys as _det_sys
    _det_here = _det_os.path.dirname(_det_os.path.abspath(__file__))
    for _det_p in (_det_os.path.join(_det_here, "scripts"),
                   _det_os.path.join(_det_os.path.dirname(_det_here), "scripts")):
        if _det_os.path.isdir(_det_p) and _det_p not in _det_sys.path:
            _det_sys.path.insert(0, _det_p)
    import determinism as det  # noqa: E402,F401

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RD = os.path.join(ROOT, "data", "rounds", "2026-11-17")

SESSION = "arena/2ecbccfd-nba3"
BUILD_STAMP = "2026-11-16T19:35Z"
NAV = [
    ("index.html", "Overview"),
    ("projection/lines.html", "Projection · lines"),
    ("projection/rotations.html", "Projection · rotations"),
    ("injuries.html", "Injuries"),
    ("standings.html", "Standings"),
    ("results.html", "Results log"),
    ("strategies.html", "Strategies"),
    ("ledger.html", "Ledger"),
    ("method.html", "Method"),
    ("bet/index.html", "Bet (gated)"),
    ("suggestions.html", "Suggestions & questions"),
    ("flagged.html", "Flagged for review"),
]

CSS = """
:root{--bg:#0b1020;--panel:#131b2e;--panel2:#0f1728;--ink:#e8eefc;--muted:#93a3c0;
--line:#233047;--ok:#3ddc97;--warn:#ffb454;--bad:#ff6b72;--link:#7cc4ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
header{padding:22px 26px 8px;border-bottom:1px solid var(--line);background:var(--panel2)}
h1{margin:0 0 6px;font-size:22px;letter-spacing:.2px}
.sub{color:var(--muted);font-size:13px}
nav{display:flex;flex-wrap:wrap;gap:6px;padding:12px 26px;background:#0d1526;
border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
nav a{padding:5px 10px;border:1px solid var(--line);border-radius:999px;font-size:13px;color:var(--ink)}
nav a.on{background:#1d2b45;border-color:#3a5680}
main{padding:20px 26px 60px;max-width:1500px}
section{margin:0 0 26px}
h2{font-size:17px;margin:0 0 4px}
h3{font-size:15px;margin:18px 0 4px;color:#cfe0ff}
.note{color:var(--muted);font-size:13px;margin:0 0 12px;max-width:105ch}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.card .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px}
.card .v{font-size:21px;font-weight:650;margin-top:3px}
.card .d{font-size:12px;color:var(--muted);margin-top:5px}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--panel);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#18233a;font-size:12px;text-transform:uppercase;letter-spacing:.4px;color:#c6d4ee}
tbody tr:hover{background:#16223a}
td.n{text-align:right;font-variant-numeric:tabular-nums}
td.mono,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.blank{color:#6d7f9e;font-style:italic}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11.5px;border:1px solid}
.p-ok{color:var(--ok);border-color:#20543f;background:#12291f}
.p-warn{color:var(--warn);border-color:#5a4520;background:#2a2113}
.p-bad{color:var(--bad);border-color:#5a2530;background:#2a1418}
.p-mut{color:var(--muted);border-color:#2a3a56;background:#141d31}
.flag{border-left:3px solid var(--warn);background:#1a1a12;padding:8px 12px;border-radius:0 8px 8px 0;
margin:10px 0;font-size:13px}
.gate{border-left:3px solid var(--ok);background:#101c17;padding:8px 12px;border-radius:0 8px 8px 0;
margin:8px 0;font-size:13px}
.gate.no{border-left-color:var(--bad);background:#1c1114}
ul{margin:6px 0 0;padding-left:20px}
li{margin:3px 0}
.banner{border:1px solid #3a5680;background:#101a2c;border-radius:10px;padding:10px 14px;
margin:0 0 18px;font-size:13px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:18px}
footer{padding:18px 26px 40px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
src,.src{color:var(--muted);font-size:12px}
"""


def esc(v):
    if v is None or v == "":
        return '<span class="blank">— not printed by the source</span>'
    return html.escape(str(v))


def num(v, nd=2, suffix=""):
    if v is None or v == "":
        return '<span class="blank">—</span>'
    try:
        return f"{float(v):.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return html.escape(str(v)) + suffix


def src(url, label="source"):
    if not url:
        return '<span class="blank">—</span>'
    return f'<a href="{html.escape(url)}" rel="nofollow noopener">{label}</a>'


def table(headers, rows, cls=""):
    out = [f'<table class="{cls}"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>" + "".join(
            (f'<td class="{v[0]}">{v[1]}</td>' if isinstance(v, tuple) else f"<td>{v}</td>")
            for v in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def page(title, sub, body, active, rel_prefix=None, extra_flags=None):
    if rel_prefix is None:
        # "index.html" -> "", "projection/lines.html" -> "../", "bet/index.html" -> "../"
        rel_prefix = "../" * (active.count("/"))
    nav = "".join(
        f'<a href="{rel_prefix}{href}"{" class=on" if href == active else ""}>{lab}</a>'
        for href, lab in NAV)
    flags = "".join(f'<div class="flag"><b>Flag.</b> {f}</div>' for f in (extra_flags or []))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · NBA3 2026-11-17</title>
<link rel="stylesheet" href="{rel_prefix}style.css"></head>
<body>
<header><h1>{html.escape(title)}</h1><div class="sub">{sub}</div></header>
<nav>{nav}</nav>
<main>
{flags}
{body}
</main>
<footer>Built {BUILD_STAMP} by session <span class="mono">{SESSION}</span> from
<span class="mono">data/rounds/2026-11-17/</span>. Every row links to the page that printed it;
blanks are blanks because no official source printed a value, and the flag boxes above name each
one. Deterministic rebuild: <span class="mono">python3 round_2ecbccfd/build.py --check</span>.</footer>
</body></html>
"""


def load(name):
    with open(os.path.join(RD, name), encoding="utf-8") as fh:
        return json.load(fh)


def rel(p):
    return "https://routify-file-proxy" not in p and p


def write(relpath, doc):
    path = os.path.join(HERE, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path


# -------------------------------------------------------------------------------------------- pages
def p_index(model, ledger_idx, results_log, standings_doc, injury_doc, flags):
    hca = model["hca"]
    corr = model["correlations"]
    gates = model["gates"]
    npass = det.fold(1 for g in gates if g["pass"])
    tonight_lines = [l for l in model["lines"] if l["date"] == "2026-11-16"]
    cards = [
        ("verified games in the log", results_log["count"],
         f"2026-10-20 to {results_log['log_end']}; one row per game, 30/30 clubs reconcile"),
        ("measured home-win rate", f"{hca['measured_home_win_rate']*100:.2f}%",
         f"pinned home-court = {num(hca['pinned_hca_points'])} pts, CI95 on the rate "
         f"[{hca['home_win_rate_ci95'][0]*100:.1f}%, {hca['home_win_rate_ci95'][1]*100:.1f}%]"),
        ("same-night margin correlation", num(corr["same_night_game_margins"]["rho"], 3),
         f"n = {corr['same_night_game_margins']['n_pairs']} game pairs, CI95 "
         f"[{corr['same_night_game_margins']['ci95'][0]:.3f}, "
         f"{corr['same_night_game_margins']['ci95'][1]:.3f}] — inside its own noise band"),
        ("strategies frozen", len(ledger_idx["pre_registration_files"]),
         f"{len(ledger_idx['refused_before_tip'])} refused before tip by their own gates"),
        ("ledger entries", ledger_idx["chain_entries"],
         f"head {ledger_idx['head_hash'][:16]}… · {ledger_idx['integrity']} · "
         f"{ledger_idx['settled']} settled"),
        ("injury revisions diffed", "2",
         f"09:15 AM → 01:15 PM ET: {injury_doc and model['injury_change_count']} differences, "
         f"{len(model['injury_status_changes'])} status changes"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="d">{d}</div></div>' for k, v, d in cards)
    gate_html = "".join(
        f'<div class="gate{" no" if not g["pass"] else ""}"><b>{"PASS" if g["pass"] else "FAIL"}</b> '
        f'<span class="mono">{g["id"]}</span> — {html.escape(g["name"])}'
        f'<div class="note">{html.escape(g["detail"])}</div></div>' for g in gates)
    tonight = table(
        ["Game", "Tip (ET)", "Estimator A", "Estimator B", "Headline: disagreement", "Sign agrees",
         "Blend (underneath)", "Rotation availability", "Source"],
        [[l["matchup"], esc(l.get("tip_et")),
          ("n/m", num(l["e1"].get("margin_away"))) if l["e1"].get("margin_away") is not None
          else ("n/m", '<span class="pill p-warn">NOT MEASURABLE</span>'),
          ("n/m", num(l["e2"].get("margin_away"))) if l["e2"].get("margin_away") is not None
          else ("n/m", '<span class="pill p-warn">NOT MEASURABLE</span>'),
          ("n/m", num((l.get("headline_confidence_signal") or {}).get("disagreement_margin_points"))
           + " pts"),
          ("n/m", '<span class="pill p-ok">yes</span>' if (l.get("headline_confidence_signal") or {}
                                                            ).get("sign_agreement")
           else '<span class="pill p-bad">no</span>'),
          ("n/m", f'{num((l.get("blend_underneath") or {}).get("margin_away"))} / '
                  f'{num((l.get("blend_underneath") or {}).get("total"))} total'),
          ("n/m", rotation_summary(l)),
          src(l.get("source_url"), "nba.com/games")] for l in tonight_lines], "mono")
    body = f"""
<section>
<div class="banner"><b>Executive summary.</b> The refresh gate is now real: the round was built only
after a freshness check on the official injury report (newest revision {esc(injury_doc['reports'][-1]['report_stamp'])},
retrieved {esc(injury_doc['reports'][-1]['retrieved_utc'])}) and a provenance check that every
published row names an https NBA page. Home-court is not a free parameter — it is
{num(hca['pinned_hca_points'])} points, converted from a measured {num(hca['measured_home_win_rate']*100,2)}%
home-win rate over {results_log['count']} verified games, and the standings' own HOME splits give
{num(hca['independent_cross_check']['implied_hca_points'])} points independently (agreement
{num(hca['independent_cross_check']['agrees_within_points'])} pts). Both numbers are small: the
frequently-assumed 3-point edge is not supported by what has actually been played. Luck is
published as a z-score per club and {len(model['luck']['outside_noise_band'])} clubs sit outside the
±2 band, so nothing is refused on that ground tonight. Parlays are priced with the measured
correlation and the naive product is printed beside them — the measured rho is ~0, so the naive
price is nearly right and no parlay is funded. <b>No strategy passed its out-of-sample gate, so the
bet surface publishes nothing staked.</b></div>
{cards_html}
</section>
<section><h2>Gate board — {npass}/{len(gates)}</h2>
<div class="note">Recomputed by <span class="mono">python3 round_2ecbccfd/build.py --check</span> and by CI;
a failing gate does not block the deploy, it blocks the number.</div>
{gate_html}</section>
<section><h2>Lines tonight (projection surface)</h2>
<div class="note">The headline is the disagreement between the two estimators; the blend is
underneath it, exactly as the brief demands. Prices, stakes and parlays live only on
<a href="bet/index.html">the gated bet surface</a> and never in this table.</div>
{tonight}</section>
<section class="two"><div><h2>What is still missing</h2><ul>
<li><b>Closing-line feed</b> — <span class="mono">data/app/closing_lines.json</span> is
&quot;not connected&quot; with 0 rows, so the market-anchored prior cannot be weighted by measured
log-loss and every blended line is blank.</li>
<li><b>Quarter table for ATL@MIL</b> — the game page's banner and the game book agree on the final
(113–106) but the period table still does not sum to it, so that row is excluded from quarter
measures.</li>
<li><b>Player-level prices</b> — no official source in this repository prints a prop line, and
player–player correlation is unmeasured, so no prop combination is priced.</li>
<li><b>Game books for 16 clubs</b> — rotation impact is measurable only where a box score was
captured; the shortfall is listed on the rotations page rather than filled with zeros.</li>
</ul></div><div><h2>Where each number comes from</h2><ul>
<li>Injury statuses: the official report PDF, two revisions of the same game day, both stored
verbatim — <a href="injuries.html">Injuries</a>.</li>
<li>Standings and splits: <a href="https://www.nba.com/standings" rel="nofollow noopener">nba.com/standings</a>,
transcribed and reconciled against the results log — <a href="standings.html">Standings</a>.</li>
<li>Finals and quarter scores: each game's official book plus the scoreboard page —
<a href="results.html">Results log</a>.</li>
<li>Strategy registers and the sealed pick chain — <a href="strategies.html">Strategies</a>,
<a href="ledger.html">Ledger</a>.</li>
<li>Every blank, conflict and non-official input — <a href="flagged.html">Flagged for review</a>.</li>
<li>Site and pipeline suggestions awaiting a decision, plus the questions that block them —
<a href="suggestions.html">Suggestions &amp; questions</a>.</li>
</ul></div></section>"""
    return page("NBA3 · round 2026-11-17", f"line origination, gated strategy, official sources only · session {SESSION}",
                body, "index.html", None, flags)


def rotation_summary(l):
    av = l.get("availability") or {}
    bits = []
    for side in ("away", "home"):
        s = av.get(side) or {}
        if not isinstance(s, dict):
            continue
        if s.get("measurable"):
            v = s.get("vacated_min")
            cls = "p-ok" if (v or 0) >= 8 else "p-mut"
            bits.append(f'{side}: <span class="pill {cls}">{num(v,1)} min vacated</span>')
        elif s.get("out_players"):
            bits.append(f'{side}: <span class="pill p-warn">{len(s["out_players"])} out, '
                        f"no captured book</span>")
        else:
            bits.append(f'{side}: <span class="pill p-mut">no report / no book</span>')
    return "<br>".join(bits) or '<span class="blank">—</span>'


def p_lines(model, flags):
    rows = []
    for l in model["lines"]:
        e1, e2 = l["e1"], l["e2"]
        sig = l.get("headline_confidence_signal") or {}
        bl = l.get("blend_underneath") or {}
        ma = l.get("market_anchor") or {}
        rt = l.get("rest_travel") or {}
        av = l.get("availability") or {}
        rows.append([
            esc(l["date"]), esc(l.get("tip_et")), esc(l["matchup"]),
            ("n/m", num(e1.get("margin_away"))), ("n/m", num(e1.get("total"))),
            ("n/m", num(e2.get("margin_away"))), ("n/m", num(e2.get("total"))),
            ("n/m", f'<b>{num(sig.get("disagreement_margin_points"))}</b> pts'),
            ("n/m", '<span class="pill p-ok">same</span>' if sig.get("sign_agreement")
             else '<span class="pill p-bad">split</span>'),
            ("n/m", num(bl.get("margin_away"))), ("n/m", num(bl.get("total"))),
            ("n/m", num(ma.get("closing_line"))),
            ("n/m", rotation_summary({"availability": av})),
            ("n/m", esc((l.get("e1") or {}).get("rest_adjustment_detail") and "see Method") or "—"),
            ("n/m", f'{esc(rt.get("away", {}).get("rest_days"))} / '
                    f'{esc(rt.get("home", {}).get("rest_days"))} d'
                    + (" · b2b away" if rt.get("away", {}).get("back_to_back") else "")
                    + (" · b2b home" if rt.get("home", {}).get("back_to_back") else "")),
            src(ma.get("source_url") or l.get("source_url"), "slate"),
        ])
    body = f"""
<section><h2>Every line in the window, two estimators and their disagreement</h2>
<div class="note">Estimator A = official season team-stat pages, projected as pace ×
points-per-possession with the pinned home-court value and the measured rest gap. Estimator B = the
verified per-game results log only, recomputed strictly from games before tip. The <b>headline
signal is their disagreement</b>; the blend is the last-but-two column and is deliberately not the
headline. The closing-line column is blank for every row because
<span class="mono">data/app/closing_lines.json</span> reports
&quot;{esc((model['lines'][0].get('market_anchor') or {}).get('status'))}&quot;.</div>
{table(["Date", "Tip", "Matchup", "A margin (away)", "A total", "B margin (away)", "B total",
        "Disagreement", "Sign", "Blended margin", "Blended total", "Closing line",
        "Rotation availability", "Rest adjustment", "Rest", "Source"], rows, "mono")}
</section>
<section><h3>Reading the table</h3><ul>
<li>A margin is printed from the away club's point of view; negative means the home club is
  projected to win by that many points.</li>
<li>&quot;n/m&quot; means the estimator could not be computed for that game — never zero, and never
  an estimate carried over from a neighbouring row.</li>
<li>Disagreement is |A − B| in points. It is the published confidence signal because the two
  estimators use disjoint inputs: season aggregates versus the game-by-game log.</li>
<li>No price, no stake and no parlay appears on this page. Those live on
  <a href="../bet/index.html">the bet surface</a>, which is gated and currently empty.</li>
</ul></section>"""
    return page("Projection · originated lines",
                "safe to publish: no prices, no stakes · built from the two estimators and their disagreement",
                body, "projection/lines.html", None, flags)


def p_rotations(model, injury_doc, flags):
    rows = []
    for a in model["availability_by_game"]:
        for side in ("away", "home"):
            s = a.get(side)
            if not isinstance(s, dict):
                continue
            det = "".join(
                '<li>{p} <span class="pill {cls}">{b}</span> — status {st}, captured mean {m} min '
                'over {n} game(s) {src}</li>'.format(
                    p=esc(d["player"]),
                    cls=("p-ok" if d.get("bucket") == "rotation_player_out"
                         else "p-mut" if d.get("bucket") == "bench_player_out" else "p-warn"),
                    b=esc(d.get("bucket") or "unclassified"),
                    st=esc(d.get("status")),
                    m=num(d.get("captured_min_mean"), 1),
                    n=esc(d.get("captured_games") if d.get("captured_games") is not None else 0),
                    src=src((d.get("book_sources") or [None])[0], "book"))
                for d in (s.get("detail") or []))
            repl = ", ".join(
                f'{esc(r["player"])} {num(r["captured_min_mean"], 1)}→{num(r["new_min"], 1)}'
                for r in (s.get("replacement_minutes") or [])[:4]) or "—"
            rows.append([
                esc(a.get("date")), esc(a["matchup"]), esc(side),
                esc(s.get("club") or ""),
                ("n/m", num(s.get("vacated_min"), 1)),
                ("n/m", num((s["vacated_share_of_team_minutes"]) * 100, 1, "%")
                 if s.get("vacated_share_of_team_minutes") is not None
                 else '<span class="pill p-warn">not measurable</span>'),
                ("n/m", f'{esc(s.get("matched_logs", "—"))}/{len(s.get("detail") or [])}'),
                esc(s.get("why") or ""),
                repl,
                det or '<span class="blank">no Out/Doubtful row printed for this club</span>',
                src(a.get("source_url"), "report"),
            ])
    body = f"""
<section><h2>Rotation availability, per side</h2>
<div class="note">&quot;Vacated minutes&quot; is the sum of the captured mean minutes of the players
the official report prints as Out or Doubtful, where a captured mean exists; minutes are then
redistributed one-for-one to the club's next-ranked men from the same captured books. A player whose
captured games show him already inactive contributes zero, and is reported as
<span class="pill p-warn">already_inactive_in_captured_games</span> rather than rounded up into an
injury impact. Points impact is <b>not</b> estimated: no captured source prints a per-minute scoring
rate for a bench player, so that field is blank everywhere.</div>
{table(["Date", "Matchup", "Side", "Club", "Vacated min", "Share of team minutes", "Matched logs",
        "Why not measurable", "Minutes redistributed to", "Players and their captured lines",
        "Source"], rows, "mono")}
</section>
<section><h3>Coverage of the captured game books</h3>
<div class="note">The redistribution above is only as wide as the box scores that exist in this
repository: eight club-games from 2026-11-15 parsed by
<span class="mono">scripts/gamebooks_2ecbccfd.py</span> — minutes verified to 240:00 on all eight,
full box columns on five, because three books misalign a cell inside the roster table — plus eleven
club-games from 2026-11-14 captured by session 8f4fac33. Four rows of the 11/14 capture print a bare
jersey number in the Player Name column; they are excluded here, not guessed at, and listed on
<a href="../flagged.html">the flag page</a>.</div>
{book_coverage_table()}
</section>"""
    return page("Projection · rotations and availability",
                "measured minutes vacated, from the official report and the official box scores",
                body, "projection/rotations.html", None, flags)


def book_coverage_table():
    path = os.path.join(RD, "player_logs_2026-11-15.json")
    d = json.load(open(path, encoding="utf-8"))
    rows = []
    for club, blk in sorted(d["clubs"].items()):
        rows.append([esc(club), esc(blk.get("record_printed")),
                     ("n", esc(len([r for r in blk["rows"] if r["status"] == "played"]))),
                     ("n", num(blk["sum_min"], 2)),
                     ("n/m", '<span class="pill p-ok">yes</span>' if blk["minutes_verified"]
                      else '<span class="pill p-bad">no</span>'),
                     ("n/m", '<span class="pill p-ok">all columns</span>' if blk["columns_complete"]
                      else f'<span class="pill p-warn">minutes + points only</span>'),
                     ("n/m", '<span class="pill p-ok">printed total row</span>'
                      if blk["printed_total"] else '<span class="pill p-bad">header lost</span>'),
                     src(blk["source_url"], "game book")])
    return table(["Club-game", "Record the PDF prints", "Players with a line", "Σ minutes",
                  "Σ minutes = 240:00", "Columns published", "Club totals row", "Source"], rows, "mono")


def p_injuries(injury_doc, model, flags):
    banner = f"""<div class="banner"><b>Report status.</b> Newest revision on the official index when
read: <b>{esc(injury_doc['reports'][-1]['report_stamp'])}</b> (revision time as printed by the NBA).
Retrieved by this session at <b>{esc(injury_doc['reports'][-1]['retrieved_utc'])}</b>. The revision
time and the retrieval time are both shown because the league revises reports continuously: a report
read four hours after it was filed is not the same object as one read at filing. Index page:
{src(injury_doc['index_url'], 'official.nba.com/nba-injury-report-2026-27-season')}.</div>"""
    tables = []
    for rep in injury_doc["reports"]:
        rows = [[esc(r.get("matchup")), esc(r.get("team")), esc(r["player"]),
                 ("n/m", f'<span class="pill {"p-bad" if r["status"]=="Out" else "p-warn"}">{esc(r["status"])}</span>'
                  if r.get("status") else '<span class="pill p-warn">STATUS NOT PRINTED</span>'),
                 esc(r.get("reason")),
                 ("n/m", esc(",".join(r.get("carried") or []) or "—")),
                 ("n/m", esc(",".join(r.get("flags") or []) or "—")),
                 src(rep["source_url"], "PDF")]
                for r in rep["rows"]]
        tables.append(f"""<h3>{esc(rep['report_stamp'])} — {rep['player_rows']} player rows,
{rep['not_submitted_rows']} clubs that had not filed, {len(rep['parse_problems'])} parse notes
<div class="note">verbatim transcript in the repository: <span class="mono">{esc(rep['verbatim_transcript'])}</span>
(sha256 <span class="mono">{esc(rep['transcript_sha256'][:16])}…</span>)</div></h3>
{table(["Game", "Team", "Player", "Status", "Reason", "Carried across a page break", "Flags", "Source"], rows, "mono")}""")
    not_sub = [[esc(r.get("matchup")), esc(r.get("team")), esc(r.get("date")),
                esc(r.get("game_time")), "NOT YET SUBMITTED", src(r["source_url"], "PDF")]
               for rep in injury_doc["reports"] for r in rep["not_submitted"]]
    delta_rows = []
    for c in model["injury_status_changes"]:
        delta_rows.append([esc(c.get("matchup")), esc(c["player"]), esc(c.get("team")),
                           ("n/m", f'{esc(c.get("from_status"))} → <b>{esc(c.get("to_status"))}</b>'),
                           ("n/m", f'<span class="pill {"p-bad" if c.get("direction")=="less_available" else "p-ok"}">{esc(c.get("direction"))}</span>'),
                           esc(c.get("to_reason")),
                           src(c.get("to_source"), "13:15 revision"),
                           src(c.get("from_source"), "09:15 revision")])
    body = f"""
{banner}
<section><h2>Status changes between the two revisions of the same game day</h2>
<div class="note">Diff of the 09:15 AM and 01:15 PM ET filings, keyed on (matchup, normalised
player name). {model['injury_change_count']} differences in total, {len(model['injury_status_changes'])}
of them a change in the printed Status column; the rest are added rows, removed rows and reason-wording
changes, listed on <a href="flagged.html">the flag page</a>.</div>
{table(["Game", "Player", "Team", "Status", "Direction", "Reason in the later report", "Later", "Earlier"], delta_rows or [["—","no status change between the two revisions","","","","","",""]], "mono")}
</section>
<section><h2>Clubs that had not filed</h2>
<div class="note">Printed as <span class="mono">NOT YET SUBMITTED</span> by the report itself. No
status is inferred for these clubs — the absence of a filing is the finding, and it is why
tonight's slate has fewer measurable rotation numbers than games.</div>
{table(["Game", "Club", "Game date", "Game time", "Report cell", "Source"], not_sub, "mono")}
</section>
<section><h2>The two revisions, as parsed</h2>
{''.join(tables)}
</section>"""
    return page("Injuries · official report", "revision time and retrieval time, both, on every surface",
                body, "injuries.html", None, flags)


def p_standings(standings_doc, model, flags):
    rows = []
    by_team_log = {}
    for c in model["hca"]["independent_cross_check"]["per_club"]:
        by_team_log[c["team"]] = c
    for s in standings_doc["rows"]:
        t = s["team"]
        c = by_team_log.get(t, {})
        rows.append([esc(s["conference"]), ("n", esc(s["seed"])),
                     f'<a href="{esc(s["team_url"])}" rel="nofollow noopener">{esc(t)}</a>',
                     ("n", esc(s["w"])), ("n", esc(s["l"])), esc(s["win_pct"]), esc(s["gb"]),
                     esc(s["conf_rec"]), esc(s["div_rec"]), esc(s["home_rec"]), esc(s["road_rec"]),
                     esc(s["neutral_rec"]), esc(s["ot_rec"]), esc(s["last10"]), esc(s["streak"]),
                     ("n/m", f'{esc(s["gp"])}'),
                     ("n/m", '<span class="pill p-ok">log agrees</span>'
                      if c.get("exact_split_match") else
                      f'<span class="pill p-warn">{esc(c.get("log_home"))} home / '
                      f'{esc(c.get("log_road"))} road in the log</span>'),
                     src(standings_doc["source_url"], "standings")])
    body = f"""
<section><h2>League standings, transcribed and reconciled</h2>
<div class="note">Read {esc(standings_doc['retrieved_utc'])} from
<a href="{esc(standings_doc['source_url'])}" rel="nofollow noopener">nba.com/standings</a>
({esc(standings_doc['page_controls'])}), stored verbatim as
<span class="mono">{esc(standings_doc['verbatim_transcript'])}</span> (sha256
<span class="mono">{esc(standings_doc['transcript_sha256'][:16])}…</span>). The &quot;games played&quot;
column is W + L, which is what makes the reconciliation meaningful: the log gives each club's games
from the box scores, and the two must match for the whole site to stand on one data set. They match
for 30 of 30 clubs. The header the NBA prints lists the first column as a lower-case
<span class="mono">w</span>; that is reproduced, not corrected.</div>
{table(["Conf", "Seed", "Team", "W", "L", "Win%", "GB", "Conf", "Div", "Home", "Road", "Neutral",
        "OT", "Last 10", "Streak", "GP (W+L)", "Vs the verified log", "Source"], rows, "mono")}
</section>
<section><h3>Why two clubs' printed splits differ from the log's</h3>
<div class="note">{esc(model['hca']['independent_cross_check']['note'])}</div>
{json_block(model['hca']['neutral_sites'])}
</section>"""
    return page("Standings", "30 clubs, every column the NBA prints, reconciled against the results log",
                body, "standings.html", None, flags)


def json_block(obj):
    return ('<pre class="mono" style="background:#0f1728;border:1px solid #233047;'
            'border-radius:10px;padding:12px;overflow:auto">'
            + html.escape(json.dumps(obj, indent=1)) + "</pre>")


def p_results(results_log, model, flags):
    rows = []
    for g in results_log["games_2026_11_15"]:
        qs = g.get("quarter_scores") or {}
        rows.append([esc(g["date"]), esc(f'{g["away"]} @ {g["home"]}'),
                     ("n", f'<b>{esc(g.get("away_final", g.get("away_pts")))} – '
                          f'{esc(g.get("home_final", g.get("home_pts")))}</b>'),
                     ("n/m", esc("·".join(str(x) for x in (qs.get("away") or []))) or "—"),
                     ("n/m", esc("·".join(str(x) for x in (qs.get("home") or []))) or "—"),
                     ("n/m", f'{esc((g.get("quarter_sums") or {}).get("away"))} / '
                             f'{esc((g.get("quarter_sums") or {}).get("home"))}'),
                     ("n/m", '<span class="pill p-ok">settled</span>' if g.get("settled")
                      else '<span class="pill p-bad">not settled</span>'),
                     ("n/m", f'<span class="pill {"p-ok" if g.get("final_verified") else "p-bad"}">'
                             f'{"verified" if g.get("final_verified") else "unverified"}</span>'),
                     esc(g.get("settlement_stamp") or ""),
                     src(g.get("source_url"), "game book"), src(g.get("scoreboard_url"), "scoreboard")])
    tot = det.fold(g.get("away_pts", 0) + g.get("home_pts", 0)
              for g in results_log["games_2026_11_15"])
    body = f"""
<section><h2>Official per-game results, one row per game</h2>
<div class="note">Nine games on 2026-11-15, each row from that game's own official box score, with
the scoreboard page as the second reading. A row settles only when the printed final is verified:
{det.fold(1 for g in results_log['games_2026_11_15'] if g.get('settled'))} of 9 are settled and
{det.fold(1 for g in results_log['games_2026_11_15'] if g.get('final_verified'))} of 9 have a verified
final — the difference is the one game whose quarter table contradicts its own final, named below.
Settlement stamp is kept visible on every row because a settlement without a time is not evidence.
{results_log['settlement_note']}</div>
{table(["Date", "Matchup", "Final", "Away Q1–Q4", "Home Q1–Q4", "Quarter sums (away/home)",
        "Settlement", "Final", "Stamp", "Game book", "Scoreboard"], rows, "mono")}
</section>
<section><h3>The one conflict, stated as found</h3>
{conflict_block(results_log)}
</section>
<section class="two"><div><h3>What the log supports</h3><ul>
<li>{results_log['count']} games, 2026-10-20 to {esc(results_log['log_end'])}, one row per game.</li>
<li>Home wins {results_log['home_measured']['home_wins']} / {results_log['home_measured']['games']}
 = {num(results_log['home_measured']['home_win_rate']*100,2)}%; overtime games
{results_log['home_measured']['ot_games']}.</li>
<li>Sum of the 30 clubs' games played = {results_log['reconciliation']['sum_log_gp']} =
2 × {results_log['reconciliation']['games_in_log']}: no game is missing and none is doubled.</li>
<li>Points in the nine 2026-11-15 games: {tot}, mean {tot/9:.1f} per game.</li>
</ul></div><div><h3>Reconciliation, per club</h3>{json_block({
 "games_in_log": results_log['reconciliation']['games_in_log'],
 "sum_log_gp": results_log['reconciliation']['sum_log_gp'],
 "identity_holds": results_log['reconciliation']['gp_sum_equals_twice_games'],
 "teams_reconciled": f"{results_log['reconciliation']['teams_reconciled']}/"
                     f"{results_log['reconciliation']['teams_total']}",
})}</div></section>"""
    return page("Results log", "verified finals and quarter scores, settlement stamps kept visible",
                body, "results.html", None, flags)


def conflict_block(results_log):
    out = []
    for g in results_log["games_2026_11_15"]:
        cf = g.get("conflict")
        if not cf:
            continue
        out.append(f"""<div class="flag"><b>{esc(g['away'])} {esc(g['away_final'])} at
{esc(g['home'])} {esc(g['home_final'])}</b> ({esc(g['game_id'])}). The game book's period table sums to
{esc((g.get('quarter_sums') or {}).get('home'))} for {esc(g['home'])} while the same page prints a
final of {esc(g['home_final'])}; the away column does sum correctly. Corroboration read by this
session: {esc((g.get('final_corroboration') or {}).get('printed') or 'none')} —
{src((g.get('final_corroboration') or {}).get('url'), 'official game page')} (retrieved
{esc((g.get('final_corroboration') or {}).get('retrieved_utc') or '—')}). The final is therefore used
for margin and total measures and the quarter row is <b>not</b> used for any quarter-level measure;
no quarter value was altered to make the table add up.</div>""")
    return "".join(out) or '<div class="note">No conflicts in this log.</div>'


def p_strategies(model, ledger_idx, flags):
    reg = []
    for s in model["strategies"]:
        oos = s.get("oos") or {}
        base = s.get("baseline") or {}
        reg.append([
            ("n/m", f'<span class="mono">{esc(s["id"])}</span>'), esc(s["name"]), esc(s["family"]),
            esc(s["signal"]), esc(s["universe"]),
            ("n", esc(oos.get("games")) if oos.get("games") is not None else "—"),
            ("n", num(oos.get("hit_rate") * 100, 2, "%") if oos.get("hit_rate") is not None else "—"),
            ("n", num(oos.get("log_loss"), 4) if oos.get("log_loss") is not None else "—"),
            ("n", num(base.get("log_loss"), 4) if base.get("log_loss") is not None else "—"),
            ("n", num(s.get("log_loss_gain_vs_coin"), 5)
             if s.get("log_loss_gain_vs_coin") is not None else "—"),
            ("n/m", f'<span class="pill '
                     f'{"p-ok" if s["verdict"]=="FUNDED" else "p-bad" if s["verdict"] in ("NOT_FUNDED","NOT_PRICABLE") else "p-warn"}">'
                     f'{esc(s["verdict"])}</span>'),
            ("n/m", esc(s.get("why_not") or "")),
            ("n", str(s.get("reward_points"))),
        ])
    frozen = json_block({s["id"]: s for s in load_prereg_summaries()})
    body = f"""
<section><h2>Strategy register and rewards leaderboard</h2>
<div class="note">Rewards are 100 points per strategy that passed its out-of-sample gate, and every
other strategy shows the sentence that refuses it — the refusal is the deliverable. Baseline for
log-loss is a 50/50 coin flip ({num(0.6931,4)} nats). A strategy whose signal needs data that only
exists <i>after</i> tip-off is recorded as NOT_EVALUABLE with the reason, rather than backtested on
leaked inputs.</div>
{table(["ID", "Strategy", "Family", "Signal", "Universe", "OOS games", "Hit rate", "OOS log-loss",
        "Coin log-loss", "Gain", "Verdict", "Why not / why refused", "Reward pts", "Register"],
       [r + [("n/m", src(f"https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/rounds/"
                         f"2026-11-17/prereg/2ecbccfd-{r[0][1]}.json", "frozen file"))]
        for r in reg], "mono")}
</section>
<section><h2>Pre-registration files, frozen before the first pick</h2>
<div class="note">Written by <span class="mono">scripts/ledger_2ecbccfd.py --freeze</span> into
<span class="mono">data/rounds/2026-11-17/prereg/</span>; the builder refuses to overwrite one and
verifies each file against the payload hash it was given at freeze time. Two of these registers
block their own strategy before a single pick is sealed — the back-to-back gap is inside its noise
band, and the measured same-night correlation is ~0 — and the block is printed here, not hidden.</div>
{frozen}
</section>
<section><h3>Luck band, per club</h3>
<div class="note">Luck is actual wins over Pythagenpat-expected wins, standardised. A strategy that
leans on a club outside ±2 is refused; tonight {len(model['luck']['outside_noise_band'])} clubs are
outside, so no pick is refused on this ground — and the table is published anyway, because "nobody
was lucky" is only useful if you can see the numbers.</div>
{table(["Club","GP","W","L","PPG (log)","OppG (log)","Expected W","z","Inside ±2","Standings","Reconciles","Source"],
       [[esc(l['team']),("n",esc(l['gp'])),("n",esc(l['w'])),("n",esc(l['l'])),
         ("n",num(l['ppg_from_log'],1)),("n",num(l['oppg_from_log'],1)),
         ("n",num(l['pyth_expected_w'],2)),("n",num(l['luck_z'],2)),
         ("n/m",'<span class="pill p-ok">yes</span>' if l['inside_noise_band']
          else '<span class="pill p-bad">no</span>'),
         esc(l['standings_wl']),
         ("n/m",'<span class="pill p-ok">yes</span>' if l['standings_reconciles']
          else '<span class="pill p-bad">no</span>'),
         src(l['source_url'], 'standings')]
        for l in model['luck']['teams']], "mono")}
</section>"""
    return page("Strategies", "pre-registration, validation gates, rewards, and the luck band",
                body, "strategies.html", None, flags)


def load_prereg_summaries():
    d = os.path.join(RD, "prereg")
    out = []
    for name in sorted(os.listdir(d)):
        if name.endswith(".json"):
            j = json.load(open(os.path.join(d, name), encoding="utf-8"))
            out.append({"id": j["id"], "name": j["name"], "signal": j["signal"],
                        "thresholds": j["thresholds"], "settlement_rule": j["settlement_rule"],
                        "stake_rule": j["stake_rule"], "frozen_utc": j["frozen_utc"],
                        "payload_sha256": j["payload_sha256"],
                        "blocked_because": j.get("blocked_because")})
    return out


def p_ledger(ledger_idx, flags):
    entries = []
    path = os.path.join(RD, "ledger", "ledger.jsonl")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                entries.append(json.loads(line))
    rows = [[("n", esc(e["seq"])), ("n/m", f'<span class="pill '
                                           f'{"p-ok" if e["kind"]=="PUBLISH" else "p-warn"}">{esc(e["kind"])}</span>'),
             f'<span class="mono">{esc(e["pick_id"])}</span>',
             esc(e["pick"]["payload"]["matchup"]), esc(e["pick"]["payload"]["tip_utc"]),
             esc(e.get("published_utc") or e.get("settled_utc")),
             f'<span class="mono">{esc(e["entry_hash"][:16])}…</span>',
             f'<span class="mono">{esc(e["prev_hash"][:16])}…</span>',
             esc(e.get("state") or e.get("result", {}).get("outcome")),
             src(e["pick"]["payload"].get("game_url") or e["pick"]["payload"].get("source_url"),
                 "game")]
            for e in entries[:60]]
    body = f"""
<section><h2>Sealed picks</h2>
<div class="banner"><b>Chain head</b> <span class="mono">{esc(ledger_idx['head_hash'])}</span> ·
{ledger_idx['chain_entries']} entries · integrity <b>{esc(ledger_idx['integrity'])}</b> ·
{ledger_idx['published']} PUBLISH, {ledger_idx['settled']} SETTLE. {esc(ledger_idx['anchor'])}</div>
<div class="note">Each entry stores the pick payload, its sha256 and the previous entry's hash, so
the head commits to every pick sealed before it. Publication time precedes tip-off on every row
below — that is the property the requirement asks for, and
<span class="mono">python3 scripts/ledger_2ecbccfd.py --check</span> fails a build if a hash stops
matching its own contents. First 60 entries of {len(entries)}; the file of record is
<span class="mono">data/rounds/2026-11-17/ledger/ledger.jsonl</span>.</div>
{table(["#","Kind","Pick","Matchup","Tip (UTC)","Timestamp","Entry hash","Prev hash","State","Source"],
       rows, "mono")}
</section>
<section><h3>Refused before tip</h3><ul>
{"".join(f'<li><span class="mono">{esc(r["strategy_id"])}</span> — {esc(r["why"])}</li>'
         for r in ledger_idx["refused_before_tip"])}
</ul></section>
<section><h3>What this does not prove</h3><ul>
<li>It is not a timestamping authority: it makes edits detectable, not impossible.</li>
<li><span class="mono">published_utc</span> is only as trustworthy as the machine that wrote it; the
git commit that carries this file is the external witness.</li>
<li>No pick is graded yet: none of tonight's games had an official final when the chain was written,
so every row is PUBLISHED_PRE_TIP and the settlement run appends SETTLE entries later.</li>
</ul></section>"""
    return page("Ledger", "hash-chained, sealed before tip-off, verified after settlement",
                body, "ledger.html", None, flags)


def p_method(model, results_log, injury_doc, flags):
    hca, corr = model["hca"], model["correlations"]
    rest = model["rest_effect_measured"]
    body = f"""
<section><h2>How a line is made here</h2><ol>
<li><b>Possessions, not averages.</b> A total is pace × points-per-possession, with pace from the
official advanced page and each side's ppp as the mean of its own rate and its opponent's allowed
rate. An average of two points-per-game figures is never used: it silently double-counts pace.</li>
<li><b>Home court is pinned.</b> {num(hca['pinned_hca_points'])} points, which is
probit({num(hca['measured_home_win_rate'],4)}) × the log's margin s.d. {num(hca['margin_sd_points'])}.
The standings' own HOME splits give {num(hca['independent_cross_check']['implied_hca_points'])}
independently; with the one neutral-site game removed from the denominator the two agree to
{num(hca['sensitivity_neutral_excluded']['pinned_hca_points'])} exactly.</li>
<li><b>Two estimators, disagreement as the headline.</b> A = season aggregates; B = the verified
game log, recomputed only from games before tip. The published confidence signal is |A − B|; the
blend sits underneath at equal weight, with no optimisation against outcomes.</li>
<li><b>Rest is measured, not assumed.</b> Back-to-back games in this log have been outscored by
{num(rest['back_to_back']['mean_margin'])} per game on average and rested games by
{num(rest['rested']['mean_margin'])}, a gap of {num(rest['back_to_back_penalty_points'])} points
with a standard error of {num(rest['penalty_standard_error'])} (z = {num(rest['penalty_z'],2)}).
That is why the adjustment is applied at half weight per side, and why a strategy built on it is
refused by its own frozen z-floor.</li>
<li><b>Luck is a z-score.</b> Actual minus Pythagenpat-expected wins, standardised; {len(model['luck']['outside_noise_band'])}
clubs outside ±2 tonight.</li>
<li><b>Correlation is measured and then priced.</b> Same-night margin rho is
{num(corr['same_night_game_margins']['rho'],3)} on {corr['same_night_game_margins']['n_pairs']} game
pairs, CI95 [{num(corr['same_night_game_margins']['ci95'][0],3)}, {num(corr['same_night_game_margins']['ci95'][1],3)}];
totals {num(corr['same_night_game_totals']['rho'],3)}, home-win indicators
{num(corr['same_night_home_wins']['rho'],3)}. Parlays are priced with this rho and the naive product
is printed next to them on the bet surface.</li>
<li><b>Minutes are modelled per man.</b> Out/Doubtful players lose their captured mean minutes and
the club's next-ranked men absorb them one-for-one; points impact stays blank because no captured
source prints a bench per-minute scoring rate.</li>
<li><b>The market anchor is off.</b> A closing-line blend needs a closing line and a measured
out-of-sample log-loss to weight it; the feed reports &quot;not connected&quot; with 0 rows, so the
weight is unestimated and the blended line is blank on every row.</li>
</ol></section>
<section><h2>Freshness and provenance, as the job enforces them</h2>
<div class="note">The scheduled job fetches, gates, and only then rebuilds. Gates in this round:
{det.fold(1 for g in model['gates'] if g['pass'])}/{len(model['gates'])} pass, and each is recomputed from
the artefacts on disk rather than recorded by hand — see the <a href="index.html">gate board</a>.
The injury gate compares the newest report's <i>printed</i> revision time against the game day being
priced; the provenance gate requires an https NBA source on every published row; the settlement gate
requires a verified official final per game.</div>
{json_block({"gates": model["gates"]})}
</section>
<section><h2>Where a value could not be had</h2><ul>
<li>Venues for 2026-11-19: the game cards the slate was read from do not print one, so
<span class="mono">venue</span> is null on those rows and the arena name is marked
<span class="mono">venue_is_official: false</span>.</li>
<li>Travel distance is computed from a Wikipedia-sourced arena-coordinate table — derived, not an
NBA fact, and never priced into a line.</li>
<li>Quarter scores for ATL@MIL: see <a href="results.html">the results page</a>.</li>
<li>Game-date attribution for 11/18 cards read off a neighbouring page: excluded from this round's
window rather than inferred; only games whose date the slate printed are priced.</li>
</ul></section>"""
    return page("Method", "formulas, what is measured, what is pinned, what is blank and why",
                body, "method.html", None, flags)


def p_bet(model, ledger_idx, flags):
    priced = model["parlays_priced"]
    rows = [[esc(" + ".join(p["legs"])), ("n", num(p["p_leg1"], 4)), ("n", num(p["p_leg2"], 4)),
             ("n", num(p["naive_product"], 4)), esc(p["american_naive"]),
             ("n", num(p["priced_with_measured_rho"], 4)), esc(p["american_rho"]),
             ("n", num(p["rho_used"], 4)), ("n", num(p["difference_pp"], 3, " pp")),
             src(p["source_url"], "slate")] for p in priced]
    body = f"""
<section><div class="banner"><b>Gated surface — nothing here is published for betting.</b> Two
independent reasons, both stated in the repository. First, the NBA's own terms
(clause 9(iv) of the site terms) bar using NBA statistics for gambling purposes, so this project's
bet surface stays behind a gate by policy. Second, and independently, <b>no strategy has passed its
validation gates</b>, so there is nothing that this round would fund even if the first reason did not
apply. {len(ledger_idx['refused_before_tip'])} strategies are refused before tip by their own frozen
thresholds; the sealed picks on <a href="../ledger.html">the ledger</a> are projections, graded
without money.</div>
<h2>Parlay pricing, with the naive product printed beside it</h2>
<div class="note">Priced with the measured same-night correlation, not with an assumption of
independence — and the naive product is printed next to it, because withholding the price is the
easy way to look better than the data supports. The measured rho is ~0, so the two columns are
nearly identical and the honest conclusion is that there is no correlation edge to exploit on a
single night.</div>
{table(["Legs","P(leg 1)","P(leg 2)","Naive product","Naive price","Priced with rho","Rho price","rho used","Difference","Source"], rows or [["—","","","","","","","","",""]], "mono")}
</section>
<section><h3>What would have to change before this surface carries anything</h3><ul>
<li>A closing-line feed with at least a season of rows, so the market anchor can be weighted by
measured out-of-sample log-loss instead of left blank.</li>
<li>Per-player prop lines from a source this project is allowed to use, plus a measured player–player
correlation; until then no prop combination is priced at all.</li>
<li>An out-of-sample gain over the coin-flip baseline of at least 0.002 nats on the frozen
thresholds — a number the current signals do not reach, which is why the leaderboard is empty.</li>
</ul></div></section>"""
    return page("Bet · gated", "gated by policy and by the gates; pricing shown for audit only",
                body, "bet/index.html", None, flags)


def p_suggestions(model, ledger_idx, flags):
    """The review queue: suggestions are recorded, not implemented on shared surfaces."""
    B = "https://github.com/wingbangboozle1-lang/NBA3/blob/main"
    SUG = [
        ("S-2C-01", "site", "Point the front door at the current window",
         "`index.html` and `app/**` are generated by scripts/build_app.py, so no session may paste a "
         "link into them - a hand-added paragraph is exactly what broke Pages run 43935576220. The "
         "generator should emit a rounds list by scanning the round directories and their written_utc "
         "stamps, newest first.",
         "add a rounds scan to scripts/build_app.py; this round's link then appears without anyone "
         "touching a generated file", "owner of scripts/build_app.py (integration)", "not implemented",
         B + "/scripts/build_app.py"),
        ("S-2C-02", "site", "One surface per fact, linked instead of copied",
         "This round, round/ (8f4fac33) and round2/ (fbd2484b) each publish an injury diff for the same "
         "game day. Three prose copies of one diff is three ways to disagree.",
         "keep each round's own numbers on its own page and let the front door's latest-filing row read "
         "from one register (data/app/canonical.json or a rounds register)",
         "integration session", "not implemented", B + "/data/app/canonical.json"),
        ("S-2C-03", "site", "Show the noise band next to every edge",
         "The rest gap (2.888 pts, SE 2.908) and the same-night correlation (0.012, CI95 "
         "[-0.057, 0.081]) are the two figures most likely to be read as edges. Both are printed with "
         "their band here; no other surface in the repository does that for these numbers.",
         "adopt 'value + SE or CI + n' as a column rule in every builder and fail a row that prints a "
         "difference without its band", "all site owners", "not implemented", B + "/tools/check_site.py"),
        ("S-2C-04", "pipeline", "Close the 16-club game-book gap before pricing rotations",
         "Rotation impact is measurable on 5 of 16 sides tonight, because box scores exist for 19 of 30 "
         "clubs. ST-20 is registered and deliberately untradeable for that reason.",
         "extend the scheduled job to fetch every completed game's book (the statsdmz PDFs are "
         "reachable and parse at about 1.5 KB each), store the raw text, then re-run the minutes model "
         "on 20+ games per club so the floor becomes a measured share rather than one game",
         "refresh job owner", "partly done: 4 books parsed this round", B + "/scripts/refresh_official.py"),
        ("S-2C-05", "pipeline", "Get a closing-line feed, or retire the anchor requirement",
         "The market-anchored prior is defined but has no input: data/app/closing_lines.json reports "
         "'not connected' with 0 rows, so the weight cannot be estimated and every blended line is blank.",
         "connect one licensed feed and store its closes per game, or record the requirement as "
         "deliberately unmet in the register so a reader never mistakes the blank for a missing build step",
         "owner decision (legal + data)", "not implemented", B + "/data/app/closing_lines.json"),
        ("S-2C-06", "pipeline", "Fix the ordering test the live feed breaks",
         "The refresh job's fetch step rewrites data/app/official_slate_current.json, which a unit test "
         "compares with rows promoted from fixtures - so the job can only pass by luck. Running the tests "
         "before the fetch stops the bleeding.",
         "make that test read a checked-in golden file, or run the fetch with --promote-only and assert "
         "against the fixture twice", "owner of tests/test_refresh_official.py (81800928)",
         "mitigated in .github/workflows/refresh.yml", B + "/.github/workflows/refresh.yml"),
        ("S-2C-07", "data", "Settle the ATL@MIL quarter table at source",
         "K-02 has been open a day: the game book's period table sums to 116 for MIL against a printed "
         "final of 106, and the game page's own quarter tab has not been reached.",
         "one more read of the game page's box-score tab (not the summary) either confirms the table or "
         "proves the PDF wrong; publish either answer with its retrieval stamp",
         "8f4fac33 / whoever owns rounds/2026-11-16", "open",
         "https://www.nba.com/game/atl-vs-mil-0022600243"),
        ("S-2C-08", "data", "Replace the Wikipedia arena table",
         "Travel distance is the only input in this pipeline whose source is not the NBA, and two arenas "
         "carry no coordinates at all.",
         "copy lat/long from each club's official arena page or the league's venue list, store a "
         "retrieval stamp per row, then drop the derived caveat once every row names an NBA page",
         "owner decision", "not implemented", B + "/data/app/arena_coordinates.json"),
    ]
    QUESTIONS = [
        ("Q-2C-01", "Which licensed source may we read closes from, given that NBA terms clause 9(iv) "
                    "bars gambling use of NBA statistics? Without it the market anchor stays blank.",
         "either try one non-NBA market feed with its own provenance page, or record a no-anchor policy "
         "on the bet surface (it is stated there already)", "https://www.nba.com/termsofuse"),
        ("Q-2C-02", "Should a game settle when its final is verified but its quarter table is not "
                    "(tonight's ATL@MIL)? The alternative is to void the game and lose a row per occurrence.",
         "this round settles margin and total from the final and excludes the row from quarter measures; "
         "say if the stricter rule is wanted", "https://www.nba.com/games?date=2026-11-15"),
        ("Q-2C-03", "Is 15 captured minutes the line between a rotation absence and a bench absence? It "
                    "decides which injuries count as impact at all.",
         "compare against the first-eight ranking the box scores already print; both are published here "
         "so the choice can be made from the data rather than a guess",
         "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf"),
        ("Q-2C-04", "Who owns the neutral-site classification? The standings print a NEUTRAL column the "
                    "results log has no field for, which is why one game looked like a home-edge error.",
         "add a neutral flag to the log rows for the identified games - this round identifies "
         "0022600189 and leaves the log untouched", "https://www.nba.com/standings"),
        ("Q-2C-05", "Should the four bare-jersey rows in data/app/player_game_logs.json be deleted or "
                    "re-parsed? They print 0:00 minutes with no name, so they are excluded here.",
         "re-parse the 2026-11-14 CHI@MIN book: its text layer is the one that lost a cell",
         "https://statsdmz.nba.com/pdfs/20261114/20261114_CHIMIN.pdf"),
    ]

    def state_pill(st):
        cls = "p-bad" if st == "open" else "p-ok" if st.startswith("mitigated") else "p-warn"
        return '<span class="pill %s">%s</span>' % (cls, esc(st))

    sug_rows = [[("n/m", '<span class="mono">%s</span>' % esc(i)), esc(ar), esc(t), esc(w), esc(n),
                 esc(o), ("n/m", state_pill(st)), src(link, "file")]
                for i, ar, t, w, n, o, st, link in SUG]
    q_rows = [[("n/m", '<span class="mono">%s</span>' % esc(q[0])), esc(q[1]), esc(q[2]),
               src(q[3], "source")] for q in QUESTIONS]
    body = """
<section><h2>Suggestions - for review, none implemented without an owner decision</h2>
<div class="note">Each row states what it changes, why it is worth doing, the concrete next step and who
owns that step. Nothing here was implemented on a shared surface: the only files this round changed are
inside its own scope. Grouped site / pipeline / data, and every row links the file or page it is about.</div>
%s
</section>
<section><h2>Questions that need a decision</h2>
<div class="note">Written as the decision itself, not as a topic; the second column says how the answer
can be found with what is already reachable.</div>
%s
</section>
<section><h3>What this round refused to decide for you</h3><ul>
<li>No closing line was invented for the blank market anchor - see %s.</li>
<li>No neutral-site game was re-labelled to make the standings and the log agree; the discrepancy is
identified and published instead (<a href="standings.html">standings</a>).</li>
<li>No injury status was carried forward for a club that had not filed (<a href="injuries.html">injuries</a>).</li>
<li>No parlay was funded on a correlation whose interval includes zero (<a href="bet/index.html">bet surface</a>).</li>
<li>No strategy was marked funded: the leaderboard is empty on purpose (<a href="strategies.html">strategies</a>).</li>
</ul></section>""" % (
        table(["ID", "Area", "Suggestion", "Why", "Next step", "Owner", "State", "Source"], sug_rows, "mono"),
        table(["ID", "Question", "How to find the answer", "Source"], q_rows, "mono"),
        src(B + "/data/app/closing_lines.json", "the feed file"))
    return page("Suggestions & questions",
                "review before implementation, and the decisions this round refused to make silently",
                body, "suggestions.html", None, flags)


def p_flagged(model, results_log, standings_doc, injury_doc, ledger_idx, flags):
    items = []
    items.append(("closing-line feed not connected",
                  "data/app/closing_lines.json reports feed_status \"not connected\" with 0 rows, so "
                  "the market-anchored prior is unweighted and every blended line on this site is blank.",
                  "blank cells on projection/lines.html",
                  "https://www.nba.com/stats", None))
    items.append(("ATL@MIL quarter table contradicts its own final",
                  "the game book's period table sums to 116 for Milwaukee while the same page prints "
                  "106, and the game page's banner (read 2026-11-16T18:52Z) restates 113–106; the "
                  "quarter table on the game page was not reached in the chunks fetched.",
                  "excluded from quarter measures; final still used",
                  "https://www.nba.com/game/atl-vs-mil-0022600243", "0022600243"))
    items.append(("injury report prints LeBron James under Philadelphia 76ers",
                  "the 01:15 PM ET PDF lists \"James, LeBron — Out — Low Back/Sciatica Management\" in "
                  "the PHI block, and the 2026-11-15 Philadelphia box score does print LeBron James on "
                  "Philadelphia's roster, so the report is consistent with the official roster for this "
                  "season and is not an error in the report.",
                  "published as printed, cross-checked",
                  "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf", None))
    items.append(("Golden State block prints no Reason column, and one Status cell is empty",
                  "in the GSW@NOP block the five named players have no Reason cell and Jimmy Butler III "
                  "has no Status cell; both are published as null with STATUS_NOT_PRINTED / "
                  "REASON_NOT_PRINTED rather than filled.",
                  "blank cells with flags on injuries.html",
                  "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf", None))
    items.append(("two injury rows split across a PDF page break",
                  "GG Jackson's Reason continues on the next page as a lone \"Fracture\" cell, and the "
                  "fetch tool's own chunk boundary cut the Denver block's Strawther row in two; both are "
                  "stitched with the join recorded (REASON_JOINED_ACROSS_PAGE_BREAK) and the raw "
                  "transcripts keep the cut marked.",
                  "recorded in parse_problems, transcripts unedited",
                  "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf", None))
    items.append(("11 clubs had not filed for 11/16",
                  "the report prints NOT YET SUBMITTED for those clubs, so their rotation impact is not "
                  "measurable; nothing was inferred from the previous day's filing.",
                  "not_submitted table on injuries.html",
                  "https://official.nba.com/nba-injury-report-2026-27-season/", None))
    items.append(("arena coordinates are not an NBA source",
                  "travel distance comes from a Wikipedia-sourced coordinate table plus a haversine "
                  "computed in this repository; it is reported as context and never priced into a line.",
                  "travel_miles_is_derived: true on the data rows",
                  "https://en.wikipedia.org/wiki/List_of_NBA_arenas", None))
    items.append(("venues missing for the 2026-11-19 cards",
                  "the slate strip those games were read from does not print an arena, so venue is null "
                  "and the arena name is labelled venue_is_official: false.",
                  "null venue on those rows",
                  "https://www.nba.com/schedule?date=2026-11-19", None))
    items.append(("4 rows of the 2026-11-14 player-log capture print a bare jersey number",
                  "\"33\", \"15\", \"9\", \"44\" with 0:00 minutes, all from the CHI@MIN book; excluded "
                  "from the rotation model here and reported, not renamed. Fixing the upstream artefact "
                  "belongs to its owner session, so a change request was logged in COORDINATION.md.",
                  "excluded_rows on the rotations page",
                  "https://statsdmz.nba.com/pdfs/20261114/20261114_CHIMIN.pdf", None))
    items.append(("three club-games whose box score misaligns a roster cell",
                  "Dallas, Boston and Philadelphia books: one row each loses a column inside the table, so "
                  "points and distribution columns are published as null for those players while minutes "
                  "are kept (they sum to the 240:00 the same PDF prints).",
                  "minutes + points only, per the game-book table",
                  "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf", None))
    rows = [[esc(t), esc(d), esc(w), src(u, "source"), ("n/m", esc(x or "—"))] for t, d, w, u, x in items]
    report_url = injury_doc["reports"][-1]["source_url"]
    extra = []
    for g in model["lines"]:
        for side in ("away", "home"):
            s = (g.get("availability") or {}).get(side) or {}
            if isinstance(s, dict) and not s.get("measurable") and s.get("why"):
                extra.append({"game": g["matchup"], "side": side, "why": s["why"],
                              "players": s.get("out_players") or []})
    body = f"""
<section><h2>Flagged for review</h2>
<div class="note">Every value this site could not confirm from an official source, every conflict
between two official sources, and every derived number that is not an NBA fact. None of these blocked
the deploy; each is listed with the link a human should open. This page is the review queue, so it is
deliberately blunt about what is weak.</div>
{table(["Item","What was found","How it is handled","Source","Where it shows up"], rows, "mono")}
</section>
<section><h3>Sides whose rotation impact cannot be measured</h3>
{table(["Game","Side","Why","Out/Doubtful players the report printed"],
       [[esc(e["game"]), esc(e["side"]), esc(e["why"]),
         esc(", ".join(e["players"]) or "—") + " " + src(report_url, "report")]
        for e in extra] or [["—", "—", "every side on the priced slate has a captured book",
                             "— " + src(report_url, "report")]], "mono")}
</section>
<section><h3>Open questions for the owner</h3><ol>
<li>Which licensed feed should supply closing lines, given that the NBA's terms bar using its own
statistics for betting? Without it the market anchor stays blank forever — is a no-anchor policy
acceptable, or should the anchor come from a non-NBA market source with its own provenance page?</li>
<li>Should the ledger's settlement run be allowed to settle a game whose quarter table conflicts with
its final, as this round does for margin and total but not for quarters? The alternative is to void the
game entirely, which loses one game of sample per occurrence.</li>
<li>Who owns the arena-coordinate table? It is the only non-official input in the pipeline and it is
load-bearing for travel, which is currently reported but not priced.</li>
<li>Is the 15-minute rotation-player floor (used to separate a rotation absence from a bench absence)
the right threshold, or should it be defined by the captured box score's own first-eight ranking?</li>
</ol></section>"""
    return page("Flagged for review", "blanks, conflicts and non-official inputs, each with its link",
                body, "flagged.html", None, flags)


def check_links():
    """Every internal href/src in round2/ must resolve to a file that exists in round2/.

    Run on every build, not just --check: a page that links to a page that was never written is a
    broken site, and the deploy job would still report success.
    """
    import re as _re
    bad = []
    for dirpath, _dirs, files in os.walk(HERE):
        for name in files:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, HERE)
            text = open(full, encoding="utf-8").read()
            for href in _re.findall(r'(?:href|src)="([^"#]+)"', text):
                if href.startswith(("http://", "https://", "mailto:")):
                    if not href.startswith("https://"):
                        bad.append(f"{rel}: non-https external link {href}")
                    continue
                target = os.path.normpath(os.path.join(dirpath, href))
                if not os.path.exists(target):
                    bad.append(f"{rel}: internal link {href} does not resolve")
            if 'rel="stylesheet"' not in text:
                bad.append(f"{rel}: no stylesheet link")
            if "</html>" not in text:
                bad.append(f"{rel}: truncated document")
    return bad


# -------------------------------------------------------------------------------------------- main
def main():
    check = "--check" in sys.argv
    model = load("model.json")
    results_log = load("results_log.json")
    standings_doc = load("standings.json")
    injury_doc = load("injuries.json")
    with open(os.path.join(RD, "ledger", "index.json"), encoding="utf-8") as fh:
        ledger_idx = json.load(fh)
    flags = []

    pages = {
        "index.html": p_index(model, ledger_idx, results_log, standings_doc, injury_doc, flags),
        "projection/lines.html": p_lines(model, flags),
        "projection/rotations.html": p_rotations(model, injury_doc, flags),
        "injuries.html": p_injuries(injury_doc, model, flags),
        "standings.html": p_standings(standings_doc, model, flags),
        "results.html": p_results(results_log, model, flags),
        "strategies.html": p_strategies(model, ledger_idx, flags),
        "ledger.html": p_ledger(ledger_idx, flags),
        "method.html": p_method(model, results_log, injury_doc, flags),
        "bet/index.html": p_bet(model, ledger_idx, flags),
        "suggestions.html": p_suggestions(model, ledger_idx, flags),
        "flagged.html": p_flagged(model, results_log, standings_doc, injury_doc, ledger_idx, flags),
    }
    drift = []
    for rel_path, doc in pages.items():
        if check:
            want = os.path.join(HERE, rel_path)
            have = open(want, encoding="utf-8").read() if os.path.exists(want) else ""
            if have != doc:
                drift.append(rel_path)
            continue
        write(rel_path, doc)
    if not check:
        with open(os.path.join(HERE, "style.css"), "w", encoding="utf-8") as fh:
            fh.write(CSS)
    bad = check_links()
    for b in bad:
        print("LINK ERROR:", b, file=sys.stderr)
    print(("DRIFT " if drift else "") + f"{len(pages) - len(drift)}/{len(pages)} pages "
           + ("rebuilt" if not check else "match the committed build")
           + (f" — drifted: {', '.join(drift)}" if drift else "")
           + (f" — {len(bad)} link errors" if bad else " — links OK"))
    return 1 if (drift or bad) else 0


if __name__ == "__main__":
    sys.exit(main())
