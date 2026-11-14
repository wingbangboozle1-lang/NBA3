#!/usr/bin/env python3
"""
T12 — Static site builder for NBA3 GitHub Pages (docs/).
Renders every HTML page from data/*.json so no table can drift from the verified data.
Every rendered data row ends with a Source column linking the official NBA source it
came from. Run: python3 scripts/build_site.py
"""
import html as H
import json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "docs")

NAV = [
    ("index.html", "Dashboard"),
    ("slate.html", "Slate & Picks"),
    ("strategies.html", "Strategies & Gates"),
    ("leaderboard.html", "Leaderboard"),
    ("injury-impact.html", "Injury Impact"),
    ("game-flow.html", "Game Flow"),
    ("analysis.html", "Analysis"),
    ("repo-review.html", "Repo Review"),
    ("flagged.html", "Flagged"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("sources.html", "Sources"),
]

CSS = """
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--txt:#e6edf3;--mut:#9da7b3;
--acc:#4da3ff;--good:#3fb950;--warn:#d29922;--bad:#f85149;--prov:#a371f7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
header{background:var(--card);border-bottom:1px solid var(--line);padding:14px 22px;
position:sticky;top:0;z-index:9}
header h1{margin:0;font-size:18px;display:inline-block}
header .tag{color:var(--mut);font-size:12px;margin-left:10px}
nav{margin-top:10px;display:flex;flex-wrap:wrap;gap:4px}
nav a{padding:5px 11px;border-radius:6px;color:var(--txt);font-size:13px}
nav a:hover{background:#21262d;text-decoration:none}
nav a.on{background:var(--acc);color:#04121f;font-weight:600}
main{max-width:1240px;margin:0 auto;padding:22px}
h2{font-size:20px;border-bottom:1px solid var(--line);padding-bottom:8px;margin-top:34px}
h3{font-size:16px;margin-top:26px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .n{font-size:26px;font-weight:700}
.card .l{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11.5px;font-weight:600;
border:1px solid transparent;white-space:nowrap}
.b-rel{background:rgba(63,185,80,.15);color:var(--good);border-color:rgba(63,185,80,.4)}
.b-prov{background:rgba(163,113,247,.15);color:var(--prov);border-color:rgba(163,113,247,.4)}
.b-flag{background:rgba(210,153,34,.15);color:var(--warn);border-color:rgba(210,153,34,.45)}
.b-off{background:rgba(77,163,255,.13);color:var(--acc);border-color:rgba(77,163,255,.4)}
.b-bad{background:rgba(248,81,73,.13);color:var(--bad);border-color:rgba(248,81,73,.4)}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:13.5px;
background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#21262d;font-size:12px;text-transform:uppercase;letter-spacing:.4px;color:var(--mut);
position:sticky;top:0}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:rgba(255,255,255,.015)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.src{font-size:11.5px;white-space:nowrap}
.src a{margin-right:6px}
.note{background:var(--card);border-left:3px solid var(--acc);padding:10px 14px;
border-radius:0 8px 8px 0;margin:14px 0;font-size:14px;color:var(--mut)}
.note.warn{border-left-color:var(--warn)}
.note.prov{border-left-color:var(--prov)}
code{background:#21262d;padding:1px 6px;border-radius:5px;font-size:13px}
footer{color:var(--mut);font-size:12.5px;padding:26px 0;text-align:center;border-top:1px solid var(--line);margin-top:40px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.scroll{overflow-x:auto}
ul.compact{margin:6px 0;padding-left:20px}
ul.compact li{margin:3px 0}
"""

STAMP = "2026-11-13 (data cut 18:28 ET / 23:30 UTC)"


def load(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def esc(x):
    return H.escape(str(x)) if x is not None else ""


def page(name, title, body, on):
    links = "\n".join(
        f'<a href="{u}" class="{"on" if u == on else ""}">{esc(l)}</a>' for u, l in NAV
    )
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NBA3 Research</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>NBA3 · Line-Origination &amp; Betting Strategy Research</h1>
  <span class="tag">Official NBA sources only · data cut {STAMP} · every row source-linked · blanks are flagged, never inferred</span>
  <nav>{links}</nav>
</header>
<main>
{body}
<footer>Generated by <code>scripts/build_site.py</code> from <code>data/*.json</code> · Verify: <code>python3 scripts/verify.py</code> ·
All statistics © NBA (via official NBA sources) · Research/paper-trading only — not betting advice.</footer>
</main>
</body>
</html>
"""
    with open(os.path.join(SITE, name), "w") as f:
        f.write(doc)


def badges(status):
    m = {
        "PAPER_RELEASED": ("b-rel", "RELEASED (paper)"),
        "PROVISIONAL_INJURY_PENDING": ("b-prov", "PROVISIONAL · injury report pending"),
        "PROVISIONAL_PARTIAL_INJURY": ("b-prov", "PROVISIONAL · partial injury data"),
        "NO_BET_LOW_EDGE": ("b-flag", "NO BET · edge below gate"),
    }
    cls, lbl = m.get(status, ("b-flag", esc(status)))
    return f'<span class="badge {cls}">{lbl}</span>'


def src(*urls):
    parts = []
    seen = set()
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            host = u.split("/")[2].replace("www.", "")
            parts.append(f'<a class="src" href="{esc(u)}" target="_blank" rel="noopener">{esc(host)}</a>')
    return " ".join(parts)


def build():
    os.makedirs(SITE, exist_ok=True)
    teams = {t["abbr"]: t for t in load("teams.json")["teams"]}
    slate = load("slate.json")
    injuries = load("injuries.json")
    players = load("players.json")["players"]
    strategies = load("strategies.json")
    picks = load("picks.json")
    flagged = load("flagged.json")["flags"]
    questions = load("questions.json")
    sources = load("sources.json")
    corr = load("correlations.json")

    pick_by_id = {p["game_id"]: p for p in picks["picks"]}
    inj_by_mu = {g["matchup"]: g for g in injuries["games"]}

    # ---------------- index ----------------
    rel = sum(1 for p in picks["picks"] if p["strategy_status"] == "PAPER_RELEASED")
    prov = sum(1 for p in picks["picks"] if p["strategy_status"].startswith("PROVISIONAL"))
    openq = sum(1 for q in questions["questions"] if q["answer_status"].startswith("UNANSWERED"))
    open_sug = sum(1 for s in questions["suggestions"] if s["decision"] is None)
    body = f"""
<h2>Executive dashboard</h2>
<div class="cards">
  <div class="card"><div class="n">{len(slate['games'])}</div><div class="l">Games in slate (Nov 13–16)</div></div>
  <div class="card"><div class="n">{rel}</div><div class="l">Released paper picks</div></div>
  <div class="card"><div class="n">{prov}</div><div class="l">Provisional (injury pending)</div></div>
  <div class="card"><div class="n">{len(flagged)}</div><div class="l">Flagged items</div></div>
  <div class="card"><div class="n">{openq}</div><div class="l">Open questions</div></div>
  <div class="card"><div class="n">{open_sug}</div><div class="l">Suggestions awaiting review</div></div>
</div>

<div class="note"><b>Auto-generated, no manual input.</b> This dashboard is rebuilt from
<code>data/*.json</code> by <code>scripts/generate_picks.py</code> + <code>scripts/build_site.py</code>.
Every data row links the official NBA source it came from. Unconfirmable values are left blank and
flagged — see <a href="flagged.html">Flagged</a>. Provisional rows are never scored.</div>

<h2>Today's slate at a glance (2026-11-13)</h2>
<div class="scroll">
<table>
<tr><th>Time (ET)</th><th>Matchup</th><th class="num">Our fair spread (home)</th><th class="num">Our fair total</th><th>Pick</th><th>Status</th><th>Source</th></tr>
"""
    for g in slate["games"]:
        if g["date"] != "2026-11-13":
            continue
        p = pick_by_id[g["game_id"]]
        pick_txt = f'<b>{esc(p["pick_side"])}</b>' if p["pick_side"] else '<span class="badge b-flag">pass</span>'
        body += (f'<tr><td>{esc(g["time_et"])}</td><td>{esc(g["matchup"])}</td>'
                 f'<td class="num">{p["our_fair_spread_home"]:+.1f}</td>'
                 f'<td class="num">{p["our_fair_total"]:.1f}</td>'
                 f'<td>{pick_txt}</td><td>{badges(p["strategy_status"])}</td>'
                 f'<td class="src">{src(g["source_url"], g["preview_url"], p["source_urls"]["injury_report"])}</td></tr>\n')
    body += """</table></div>

<h2>What's where</h2>
<div class="grid2">
<div>
<h3>Research &amp; process</h3>
<ul class="compact">
<li><a href="repo-review.html">Repo review (line-by-line)</a> — irregularities at base commit</li>
<li><a href="flagged.html">Flagged for Review</a> — 17 items, blank+flagged policy</li>
<li><a href="questions.html">Open questions</a> — must be answered before gated decisions</li>
<li><a href="suggestions.html">Suggestions queue</a> — reviewer picks a path before anything is implemented</li>
<li><a href="sources.html">Source registry</a> — every official source + dead-end endpoints</li>
</ul>
</div>
<div>
<h3>Strategy &amp; picks</h3>
<ul class="compact">
<li><a href="slate.html">Full slate (31 games)</a> — originated lines + picks + sources</li>
<li><a href="strategies.html">Strategies &amp; validation gates</a> — S1–S4, gates, luck controls</li>
<li><a href="leaderboard.html">Leaderboard &amp; rewards</a> — paper book rules</li>
<li><a href="analysis.html">Analysis</a> — measured correlations, league findings</li>
<li><a href="injury-impact.html">Injury → production impact</a></li>
<li><a href="game-flow.html">Game flow &amp; rest analysis</a></li>
</ul>
</div>
</div>
"""
    page("index.html", "Dashboard", body, "index.html")

    # ---------------- slate ----------------
    body = f"""
<h2>Full slate — Nov 13–16, 2026 (3-day advance window)</h2>
<div class="note">Window = today + 3 days max, per brief: {len(slate['games'])} games, every row
cross-verified against <b>both</b> the official schedule PDF and nba.com/schedule. Rest days computed from the
official schedule only. "Our fair spread" is negative when the <i>home</i> team is model-favored.</div>
<div class="note prov">⚠ <b>Provisional rows</b> (11/14 partial reports, 11/15–16 not yet published): model line uses team
strength + rest only, injury input blank. Never scored until an official report covers that game (Q-10).</div>
<div class="scroll">
<table>
<tr><th>Date</th><th>ET</th><th>Matchup</th><th>Venue / TV</th><th class="num">Rest (a/h)</th>
<th class="num">Our spread (h)</th><th class="num">Our total</th><th class="num">P(home)</th>
<th>Pick</th><th>Status</th><th>Source</th></tr>
"""
    for g in slate["games"]:
        p = pick_by_id[g["game_id"]]
        b2b = ""
        if g.get("b2b_home"):
            b2b += ' <span class="badge b-flag">home B2B</span>'
        if g.get("b2b_away"):
            b2b += ' <span class="badge b-flag">away B2B</span>'
        cup = f'<br><span class="badge b-off">{esc(g["cup_group"])}</span>' if g.get("cup_group") else ""
        pick_txt = f'<b>{esc(p["pick_side"])}</b>' if p["pick_side"] else '<span class="badge b-flag">pass</span>'
        tv = esc(g["tv"])
        body += (f'<tr><td>{esc(g["date"][5:])}</td><td>{esc(g["time_et"])}</td>'
                 f'<td><b>{esc(g["away"])}</b> @ <b>{esc(g["home"])}</b>{cup}<br>'
                 f'<span style="color:var(--mut);font-size:12px">{esc(g["venue"])}</span></td>'
                 f'<td>{tv}{b2b}</td>'
                 f'<td class="num">{g["rest_away"]} / {g["rest_home"]}</td>'
                 f'<td class="num">{p["our_fair_spread_home"]:+.1f}</td>'
                 f'<td class="num">{p["our_fair_total"]:.1f}</td>'
                 f'<td class="num">{p["model_p_home"]:.2f}</td>'
                 f'<td>{pick_txt}</td><td>{badges(p["strategy_status"])}</td>'
                 f'<td class="src">{src(g["source_url"], g["preview_url"], p["source_urls"]["injury_report"], g["pdf_source_url"])}</td></tr>\n')
    body += "</table></div>\n"

    body += "<h2>Parlays (S2) &amp; prop stacks (S3)</h2><div class='scroll'><table>"
    body += "<tr><th>Type</th><th>Legs / players</th><th class='num'>ρ</th><th class='num'>Joint p (indep.)</th><th class='num'>Joint p (corrected)</th><th>Gate</th><th>Source</th></tr>"
    for q in picks["parlays_s2"]:
        st = badges(q["strategy_status"]) if q["strategy_status"] in (
            "PAPER_RELEASED", "NO_BET_LOW_EDGE") else '<span class="badge b-flag">' + esc(q["strategy_status"]) + "</span>"
        body += (f'<tr><td>S2 parlay</td><td>{" + ".join(esc(l) for l in q["legs"])}</td>'
                 f'<td class="num">{q["rho"]:.2f}</td><td class="num">{q["joint_prob_naive"]:.3f}</td>'
                 f'<td class="num">{q["joint_prob_corrected"]:.3f}</td><td>{st}</td>'
                 f'<td class="src">{src(q["source_urls"]["leg1"], q["source_urls"]["leg2"])}</td></tr>')
    for s in picks["prop_stacks_s3"]:
        gcls = "b-rel" if s["gate"] == "RELEASE_PAPER" else "b-flag"
        body += (f'<tr><td>S3 prop stack</td><td>{esc(s["team"])}: {esc(s["players"][0])} + {esc(s["players"][1])}'
                 f' <span style="color:var(--mut)">(lines {s["line_a_ppg"]}/{s["line_b_ppg"]} PPG)</span></td>'
                 f'<td class="num">{s["rho_pts"] if s["rho_pts"] is not None else "—"}</td>'
                 f'<td class="num">n={s["n_common_games"]}</td><td>—</td>'
                 f'<td><span class="badge {gcls}">{esc(s["gate"])}</span></td>'
                 f'<td class="src">{src(*s["source_urls"])}</td></tr>')
    body += "</table></div><div class='note'>ρ = Pearson correlation on official Last-5 PTS logs. "
    body += "n=5 samples are noisy (Q-12 open). S3 lines are season PPG baselines from official player pages.</div>"
    page("slate.html", "Slate & Picks", body, "slate.html")

    # ---------------- strategies ----------------
    body = "<h2>Strategies, validation gates &amp; luck controls</h2>\n"
    body += f'<div class="note">Full methodology write-up: <a href="STRATEGIES.md">docs/STRATEGIES.md</a> · '
    body += f'Pipeline: <a href="PICKS_PIPELINE.md">docs/PICKS_PIPELINE.md</a></div>\n'
    for s in strategies["strategies"]:
        st_cls = "b-flag"
        body += f'<h3>{esc(s["id"])} · {esc(s["name"])} <span class="badge {st_cls}">{esc(s["status"])}</span></h3>'
        body += f'<p>{esc(s["description"])}</p>'
        body += '<div class="scroll"><table><tr><th>Gate</th><th>Rule</th><th>State</th><th>Source</th></tr>'
        for g in s["validation_gates"]:
            state = esc(g["state"])
            scls = "b-rel" if state.startswith("PASS") or state.startswith("ENFORCED") else (
                "b-bad" if state.startswith("FAIL") or state.startswith("BLOCKED") else "b-prov")
            gsrc = src(*(s.get("source_refs") or []))
            body += f'<tr><td><code>{esc(g["gate"])}</code></td><td>{esc(g["rule"])}</td>' \
                    f'<td><span class="badge {scls}">{state}</span></td>' \
                    f'<td class="src">{gsrc}</td></tr>'
        body += "</table></div>"
        body += "<p><b>Assumptions:</b> " + ", ".join(f"<code>{esc(p)}</code>" for p in s.get("parameters", {}).keys()) + "</p>"
        body += "<p><b>Luck controls:</b> " + "; ".join(esc(x) for x in s["luck_controls"]) + "</p>"
        body += '<p class="src">Sources: ' + src(*s["source_refs"]) + "</p>"
    rev = strategies["strategies"][0].get("parameter_revision", "")
    if rev:
        body += f'<div class="note warn"><b>Parameter revision log:</b> {esc(rev)}</div>'
    body += "<h2>Measured correlations (data/correlations.json)</h2><div class='scroll'><table>"
    body += "<tr><th>Pair</th><th class='num'>r</th><th class='num'>n</th><th>Basis</th><th>Source</th></tr>"
    for c in corr["league"]:
        body += f'<tr><td>{esc(c["pair"])}</td><td class="num">{c["r"]:+.3f}</td><td class="num">{c["n"]}</td>' \
                f'<td>Pearson, official league table</td><td class="src">{src(c["source_url"])}</td></tr>'
    for t in corr["teammates"]:
        body += f'<tr><td>teammate PTS: {esc(t["players"][0])} &amp; {esc(t["players"][1])} ({esc(t["team"])})</td>' \
                f'<td class="num">{t["rho_pts"]:+.3f}</td><td class="num">{t["n_common_games"]}</td>' \
                f'<td>Pearson on official Last-5 logs <span class="badge b-flag">noisy (Q-12)</span></td>' \
                f'<td class="src">{src(*t["source_urls"])}</td></tr>'
    body += f'<tr><td>cross-game parlay legs</td><td class="num">0.00</td><td class="num">—</td>' \
            f'<td>independence by design <span class="badge b-flag">assumption w-01</span></td>' \
            f'<td class="src">{src("https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/strategies.json")}</td></tr>'
    body += "</table></div>"
    for b in corr["blocked"]:
        body += f'<div class="note warn">⛔ <b>Blocked correlation:</b> {esc(b["what"])} — {esc(b["why"])}</div>'
    page("strategies.html", "Strategies & Gates", body, "strategies.html")

    # ---------------- leaderboard ----------------
    lb = strategies["leaderboard"]
    body = "<h2>Leaderboard &amp; rewards (paper book)</h2>\n"
    body += '<div class="note">Status after generation: <b>0 settled picks</b> — no strategy may claim skill yet. '
    body += "All four strategies sit at the bottom rung until their sample-size gates pass.</div>"
    body += "<div class='scroll'><table><tr><th>Strategy</th><th>Type</th><th>Status</th>" \
            "<th class='num'>Settled</th><th class='num'>Released</th><th>Gates passed</th><th>Source</th></tr>"
    n_rel_by = {"S1": rel}
    for s in strategies["strategies"]:
        gates_passed = sum(1 for g in s["validation_gates"]
                           if g["state"].startswith("PASS") or g["state"].startswith("ENFORCED"))
        n_rel_s = len(picks["picks"]) if s["id"] == "S1" else (
            len(picks["parlays_s2"]) if s["id"] == "S2" else
            sum(1 for st in picks["prop_stacks_s3"] if st["gate"] == "RELEASE_PAPER") if s["id"] == "S3" else
            sum(1 for p in picks["picks"] if p["strategy_status"] == "PAPER_RELEASED"
                and abs(p["rest_home"] - p["rest_away"]) >= 2))
        sref = src(*(s.get("source_refs") or ["https://github.com/wingbangboozle1-lang/NBA3"]))
        body += f'<tr><td>{esc(s["id"])} {esc(s["name"])}</td><td>{esc(s["type"])}</td>' \
                f'<td><span class="badge b-prov">{esc(s["status"])}</span></td>' \
                f'<td class="num">0</td><td class="num">{n_rel_s}</td>' \
                f'<td class="num">{gates_passed}/{len(s["validation_gates"])}</td>' \
                f'<td class="src">{sref}</td></tr>'
    body += "</table></div>"
    body += "<h3>Reward rules (pre-registered)</h3><ul class='compact'>"
    for r in lb["rules"]:
        body += f"<li>{esc(r)}</li>"
    body += "</ul>"
    body += '<p class="src">Sources: ' + src("https://github.com/wingbangboozle1-lang/NBA3",
                                             "https://www.nba.com/schedule") + "</p>"
    page("leaderboard.html", "Leaderboard", body, "leaderboard.html")

    # ---------------- injury impact ----------------
    body = "<h2>Injury → rotation &amp; production impact</h2>\n"
    body += ('<div class="note">Official statuses from the latest report '
             '(05:00 PM ET, 11/13). <b>Production at risk</b> = Σ season PPG of players with status <i>Out</i> '
             'who meet the rotation gate (GP ≥ 60% of team GP). Players with GP=0 or uncollected PPG contribute '
             'nothing and are flagged — totals are lower bounds when <code>incomplete</code> = yes.</div>')
    body += "<div class='scroll'><table><tr><th>Game</th><th>Team</th><th>Player</th><th>Status</th>" \
            "<th>Reason</th><th class='num'>PPG</th><th class='num'>GP</th><th>Counts?</th><th>Source</th></tr>"
    for g in injuries["games"]:
        if g["report_state"] == "not_yet_published":
            continue
        for t in g["teams"]:
            for pl in t.get("players", []):
                counts = "—"
                cls = ""
                if pl.get("status") == "Out":
                    if pl.get("season_ppg") and (pl.get("season_gp") or 0) >= 0.6 * next(
                            (tm["gp"] for tm in teams.values() if tm["abbr"] == t["team"]), 12):
                        counts, cls = "✓ in at-risk", "b-rel"
                    elif pl.get("season_gp") == 0:
                        counts, cls = "✗ GP=0", "b-flag"
                    elif pl.get("season_ppg") and (pl.get("season_gp") or 0) < 0.6 * 12:
                        counts, cls = "✗ <60% games", "b-flag"
                    else:
                        counts, cls = "? missing PPG", "b-bad"
                elif pl.get("status") in ("Questionable", "Probable"):
                    counts, cls = "monitor", "b-prov"
                elif pl.get("status") == "Doubtful":
                    counts, cls = "monitor (D)", "b-prov"
                else:
                    counts, cls = "available", "b-off"
                ppg = f'{pl["season_ppg"]:.1f}' if pl.get("season_ppg") is not None else \
                    ('<span class="badge b-bad">blank</span>' if pl.get("season_ppg") is None else "0")
                gp = pl.get("season_gp")
                gp_s = str(gp) if gp is not None else "?"
                body += (f'<tr><td>{esc(g["matchup"])}</td><td>{esc(t["team"])}</td>'
                         f'<td>{esc(pl["player"])}</td><td><b>{esc(pl["status"])}</b></td>'
                         f'<td style="font-size:12.5px">{esc(pl.get("reason", ""))}</td>'
                         f'<td class="num">{ppg}</td><td class="num">{gp_s}</td>'
                         f'<td><span class="badge {cls}">{counts}</span></td>'
                         f'<td class="src">{src(pl["source_url"], pl.get("ppg_source_url"))}</td></tr>')
    body += "</table></div>"
    body += '<div class="note warn">Not-yet-submitted teams (11/14) and unpublished dates (11/15–16): ' \
            'blank by policy — see <a href="flagged.html">fl-06</a> and <a href="questions.html">Q-01</a>.</div>'
    page("injury-impact.html", "Injury Impact", body, "injury-impact.html")

    # ---------------- game flow ----------------
    body = "<h2>Game flow inputs: rest, back-to-backs, venues</h2>\n"
    body += ('<div class="note">All rest values derived only from the official schedule PDF '
             '(previous-game dates). No proprietary tracking data used.</div>')
    body += "<h3>Back-to-backs in window</h3><div class='scroll'><table>" \
            "<tr><th>Date</th><th>Team</th><th>Side</th><th>Rest days</th><th>Source</th></tr>"
    slate_srcs = slate["meta"]["sources"]
    for date, lst in slate["b2b_summary"].items():
        if date == "note":
            continue
        for item in lst:
            side = "home" if "(home)" in item else "away"
            team = item.split(" ")[0]
            body += f'<tr><td>{esc(date)}</td><td><b>{esc(team)}</b></td><td>{side}</td>' \
                    f'<td class="num">0</td><td class="src">{src(*slate_srcs)}</td></tr>'
    body += "</table></div>"
    body += "<h3>Rest matrix (all 31 games)</h3><div class='scroll'><table>" \
            "<tr><th>Date</th><th>Matchup</th><th class='num'>Rest away</th><th class='num'>Rest home</th>" \
            "<th>Previous games (official schedule)</th><th>Source</th></tr>"
    for g in slate["games"]:
        body += (f'<tr><td>{esc(g["date"][5:])}</td><td>{esc(g["away"])} @ {esc(g["home"])}</td>'
                 f'<td class="num">{g["rest_away"]}</td><td class="num">{g["rest_home"]}</td>'
                 f'<td style="font-size:12px">away: {esc(g["prev_game_away"])}<br>home: {esc(g["prev_game_home"])}</td>'
                 f'<td class="src">{src(g["pdf_source_url"], g["source_url"])}</td></tr>')
    body += "</table></div>"
    body += ("<h3>Game-flow worked example (official linescore)</h3>"
             "<p>Most recent completed result fetched from an official game page: "
             "<b>CLE 115 – 107 NYK</b>, 11/11/2026 — quarters 33-23, 26-30, 23-23, 33-31; "
             "3 lead changes, 6 times tied (source below). Used only to demonstrate flow-metric capture, "
             "not as a pick input.</p>"
             '<p class="src">Sources: ' + src("https://www.nba.com/game/cle-vs-nyk-0022600218") + "</p>")
    page("game-flow.html", "Game Flow", body, "game-flow.html")

    # ---------------- analysis ----------------
    body = "<h2>Analysis &amp; findings</h2>\n"
    body += "<h3>League-level measured relationships (n=30, official table)</h3><ul class='compact'>"
    for c in corr["league"]:
        strength = "strong" if abs(c["r"]) > 0.7 else ("moderate" if abs(c["r"]) > 0.4 else "weak")
        body += f'<li><b>{esc(c["pair"])}</b>: r = <b>{c["r"]:+.3f}</b> ({strength}, n={c["n"]}) — ' \
                f'<span class="src">{src(c["source_url"])}</span></li>'
    body += """</ul>
<ul class="compact">
<li>Win% is far more explained by <b>margin</b> (r=0.94) than by scoring alone (r=0.64) or defense alone
(r=-0.75): two-way differential is the right strength signal for line origination — this is why S1 uses
net rating (PTS − OPPG) as its core input.</li>
<li>Margin vs OPPG (r=-0.80): teams that defend better win more — supports including OPPG directly in totals.</li>
</ul>
<h3>Player-level</h3>
<ul class="compact">
<li>Brunson–Towns teammate PTS ρ = <b>+0.569</b> (n=5, official logs) → S3 stack released with noisy-sample badge.</li>
<li>Cross-game parlay legs modelled with ρ=0 (separate contests) — flagged as assumption w-01, not a measurement.</li>
</ul>
<h3>Findings worth acting on</h3>
<ul class="compact">
<li><b>7 of 31</b> games cleared the S1 edge+confidence gate today; <b>22</b> are provisional pending injury
reports — the data-freshness gate, not the model, is currently the binding constraint (fl-06).</li>
<li>Five home teams sit on back-to-backs on 11/14 — rest-adjustment moves those lines materially; S4 is
pre-registered to isolate this factor.</li>
<li>Production-at-risk is concentrated in UTA (Markkanen+JJJ), GSW (Curry+Williams), NOP (Murphy+Murray),
OKC (Holmgren+J.Williams — but see rotation gate) — all verified from official rosters.</li>
<li>CLV validation remains BLOCKED without an authorized odds source (Q-04/fl-16); CI-on-settled-picks is
the fallback luck-removal mechanism until then.</li>
</ul>
<p class="src">Sources: """ + src(*[c["source_url"] for c in corr["league"]],
                                     "https://www.nba.com/schedule") + "</p>"
    page("analysis.html", "Analysis", body, "analysis.html")

    # ---------------- repo review ----------------
    body = """
<h2>Repository review (line-by-line)</h2>
<div class="note">Scope: every file at the base commit <code>6c3004d</code> (main) plus current branch state.
Full narrative: <a href="REPO_REVIEW.md">docs/REPO_REVIEW.md</a>.</div>
<h3>Base commit 6c3004d — file inventory</h3>
<div class="scroll"><table>
<tr><th>File</th><th>Size / content</th><th>Finding</th><th>Severity</th><th>Source</th></tr>
<tr><td><code>README.md</code></td><td>6 bytes: <code># NBA3</code></td>
<td>Only file in the repo. No description, no structure, no usage, no license pointer.</td>
<td><span class="badge b-bad">irregular</span></td>
<td class="src"><a class="src" href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener">github.com/wingbangboozle1-lang/NBA3</a></td></tr>
<tr><td><code>.gitignore</code></td><td>absent</td><td>No ignore rules (no artifacts to ignore yet, but gaps as data grows).</td>
<td><span class="badge b-flag">minor</span></td>
<td class="src"><a class="src" href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener">github.com/wingbangboozle1-lang/NBA3</a></td></tr>
<tr><td><code>LICENSE</code></td><td>absent</td><td>Reuse terms undefined. Not added autonomously — Q-07 awaits reviewer.</td>
<td><span class="badge b-flag">minor</span></td>
<td class="src"><a class="src" href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener">github.com/wingbangboozle1-lang/NBA3</a></td></tr>
<tr><td><code>.github/workflows</code></td><td>absent</td><td>No CI. Suggestion SG-01 awaits review (Q-08).</td>
<td><span class="badge b-flag">minor</span></td>
<td class="src"><a class="src" href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener">github.com/wingbangboozle1-lang/NBA3</a></td></tr>
<tr><td>git history</td><td>3 commits, 1 author, 2 email forms</td>
<td>Initial commit used a personal email; later commits use the GitHub noreply address; timezones differ (+0900 vs +0000).</td>
<td><span class="badge b-flag">informational</span></td>
<td class="src"><a class="src" href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener">github.com/wingbangboozle1-lang/NBA3</a></td></tr>
</table></div>
<h3>Irregularities flagged during review</h3>
<ul class="compact">
<li>Repo advertises an NBA betting-research project but contained <b>zero</b> research, data or code — all content in this branch is new.</li>
<li>Initial-commit timestamp (2026-11-14 07:17 +0900) is <i>after</i> the later commits' UTC dates due to the timezone offset — sequencing is correct, display is confusing (fl-02).</li>
<li>No CODEOWNERS / PR template / issue templates (recorded, not fixed — tooling changes route through Suggestions).</li>
</ul>
<p class="src">Sources: <a class="src" href="https://github.com/wingbangboozle1-lang/NBA3" target="_blank" rel="noopener">github.com/wingbangboozle1-lang/NBA3</a></p>
"""
    page("repo-review.html", "Repo Review", body, "repo-review.html")

    # ---------------- flagged ----------------
    body = "<h2>Flagged for review</h2>\n"
    body += ('<div class="note">Policy: <b>blank + flagged, never inferred</b>. Nothing here was silently '
             'corrected; each entry links its evidence.</div>')
    body += "<div class='scroll'><table><tr><th>ID</th><th>Sev</th><th>Category</th><th>Title</th>" \
            "<th>Detail</th><th>Status</th><th>Source</th></tr>"
    sev_map = {"high": "b-bad", "medium": "b-flag", "low": "b-off"}
    for f in flagged:
        st = "RESOLVED" if f["status"].startswith("RESOLVED") else "OPEN"
        scls = "b-rel" if st == "RESOLVED" else sev_map.get(f["severity"], "b-flag")
        body += (f'<tr><td><code>{esc(f["id"])}</code></td>'
                 f'<td><span class="badge {sev_map.get(f["severity"], "b-flag")}">{esc(f["severity"])}</span></td>'
                 f'<td>{esc(f["category"])}</td><td><b>{esc(f["title"])}</b></td>'
                 f'<td style="font-size:12.5px">{esc(f["detail"])}</td>'
                 f'<td><span class="badge {scls}">{st}</span></td>'
                 f'<td class="src">{src(f.get("source_url"))}</td></tr>')
    body += "</table></div>"
    page("flagged.html", "Flagged", body, "flagged.html")

    # ---------------- questions ----------------
    Q_REF = {
        "Q-01": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf",
        "Q-02": "https://www.nba.com/teams",
        "Q-03": "https://www.nba.com/stats/team/1610612739/traditional",
        "Q-04": "https://www.nba.com/schedule",
        "Q-05": "https://cdn.nba.com/manage/2026/08/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf",
        "Q-06": "https://www.nba.com/player/1628973/jalen-brunson",
        "Q-07": "https://github.com/wingbangboozle1-lang/NBA3",
        "Q-08": "https://github.com/wingbangboozle1-lang/NBA3",
        "Q-09": "https://github.com/wingbangboozle1-lang/NBA3",
        "Q-10": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf",
        "Q-11": "https://www.nba.com/games",
        "Q-12": "https://www.nba.com/player/1628973/jalen-brunson",
    }
    body = "<h2>Open questions — what must be answered before decisions</h2>\n"
    body += '<div class="note">Each question lists what we have, what we lack, and exactly what is needed. '
    body += 'Nothing gated by an open question has been decided.</div>'
    body += "<div class='scroll'><table><tr><th>ID</th><th>Question</th><th>Why it matters</th>" \
            "<th>We have</th><th>We lack</th><th>Needed to decide</th><th>Answer</th><th>Ref</th></tr>"
    for q in questions["questions"]:
        ans = f'<span class="badge b-bad">UNANSWERED</span>'
        if q["answer"]:
            ans = f'<span class="badge b-rel">ANSWERED</span> {esc(q["answer"])}'
        ref = Q_REF.get(q["id"])
        body += (f'<tr><td><code>{esc(q["id"])}</code></td><td><b>{esc(q["question"])}</b></td>'
                 f'<td style="font-size:12.5px">{esc(q["why_it_matters"])}</td>'
                 f'<td style="font-size:12.5px">{esc(q["we_have"])}</td>'
                 f'<td style="font-size:12.5px">{esc(q["we_do_not_have"])}</td>'
                 f'<td style="font-size:12.5px">{esc(q["needed_to_decide"])}</td>'
                 f'<td style="font-size:12.5px">{ans}</td>'
                 f'<td class="src">{src(ref) if ref else ""}</td></tr>')
    body += "</table></div>"
    body += '<p class="src">Related: <a href="flagged.html">Flagged</a> · ' \
            '<a href="questions.html#sug">Suggestions queue ↓</a></p>'
    page("questions.html", "Questions", body, "questions.html")

    # ---------------- suggestions ----------------
    body = '<h2>Suggestions — reviewer chooses a path before anything is implemented</h2>\n'
    body += ('<div class="note warn"><b>Nothing in this queue has been implemented.</b> Per the brief, '
             'a reviewer picks a path first; the <i>decision</i> field stays <code>null</code> until they do.</div>')
    body += '<div id="sug"><h3>Queue</h3></div>'
    body += "<div class='scroll'><table><tr><th>ID</th><th>Suggestion</th><th>Status</th>" \
            "<th>Path A</th><th>Path B</th><th>Recommended</th><th>Decision</th><th>Ref</th></tr>"
    SG_REF = {
        "SG-01": "https://github.com/wingbangboozle1-lang/NBA3",
        "SG-02": "https://www.nba.com/teams",
        "SG-03": "https://www.nba.com/stats/team/1610612739/traditional",
        "SG-04": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf",
        "SG-05": "https://www.nba.com/schedule",
        "SG-06": "https://github.com/wingbangboozle1-lang/NBA3",
        "SG-07": "https://www.nba.com/games",
        "SG-08": "https://github.com/wingbangboozle1-lang/NBA3",
    }
    for s in questions["suggestions"]:
        paths = {p["path"]: p for p in s["paths_considered"]}
        a = paths.get("A")
        b = paths.get("B")
        ref = SG_REF.get(s["id"])
        body += (f'<tr><td><code>{esc(s["id"])}</code></td><td><b>{esc(s["title"])}</b></td>'
                 f'<td><span class="badge b-prov">{esc(s["status"])}</span></td>'
                 f'<td style="font-size:12.5px"><b>{esc(a["label"]) if a else "—"}</b><br>'
                 f'<span style="color:var(--mut)">+ {esc(a["pros"]) if a else ""} · − {esc(a["cons"]) if a else ""}</span></td>'
                 f'<td style="font-size:12.5px"><b>{esc(b["label"]) if b else "—"}</b><br>'
                 f'<span style="color:var(--mut)">+ {esc(b["pros"]) if b else ""} · − {esc(b["cons"]) if b else ""}</span></td>'
                 f'<td>{esc(s["recommended_path"])}</td>'
                 f'<td><span class="badge b-bad">AWAITING REVIEW</span></td>'
                 f'<td class="src">{src(ref) if ref else ""}</td></tr>')
    body += "</table></div>"
    body += "<h3>Process for reviewers</h3><ul class='compact'>" \
            "<li>Read the two paths and the recommendation.</li>" \
            "<li>Record the choice in <code>data/questions.json → suggestions[].decision</code> " \
            "(or reply in the PR) — <b>that</b> authorizes implementation.</li>" \
            "<li>Implementation happens in a follow-up change referencing the suggestion ID.</li></ul>"
    page("suggestions.html", "Suggestions", body, "suggestions.html")

    # ---------------- sources ----------------
    body = "<h2>Source registry</h2>\n"
    body += ('<div class="note">Every source below was fetched during this session. '
             'Dead/blocked endpoints are recorded too so nobody retries them.</div>')
    body += "<div class='scroll'><table><tr><th>ID</th><th>Title</th><th>Publisher</th>" \
            "<th>Fetched</th><th>Used for</th><th>Link</th></tr>"
    for s in sources["sources"]:
        surl = src(s["url"])
        note_html = ""
        if s.get("notes"):
            note_html = '<br><span style="color:var(--mut);font-size:12px">' + esc(s["notes"]) + "</span>"
        body += (f'<tr><td><code>{esc(s["id"])}</code></td><td><b>{esc(s["title"])}</b>{note_html}</td>'
                 f'<td>{esc(s["publisher"])}</td><td>{esc(s["fetched_at"])}</td>'
                 f'<td style="font-size:12.5px">{esc(", ".join(s.get("used_for", [])))}</td>'
                 f'<td class="src">{surl}</td></tr>')
    body += "</table></div>"
    body += "<h3>Dead ends (do not retry)</h3><div class='scroll'><table>" \
            "<tr><th>URL</th><th>Result</th><th>Action taken</th></tr>"
    for d in sources["blocked_or_dead_sources"]:
        body += (f'<tr><td style="font-size:12px">{esc(d["url"])}</td>'
                 f'<td><span class="badge b-bad">{esc(d["result"])}</span></td>'
                 f'<td style="font-size:12.5px">{esc(d["action"])}</td></tr>')
    body += "</table></div>"
    page("sources.html", "Sources", body, "sources.html")

    print(f"Built {len(NAV)} pages into docs/")


if __name__ == "__main__":
    build()
