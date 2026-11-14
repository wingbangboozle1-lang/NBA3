#!/usr/bin/env python3
"""Build the 240bc29b site: clean landing page + category subpages.

All content is generated from verified data files under 240bc29b/data/. Every
table row carries an official source link; values that could not be confirmed
are left blank and flagged. Nothing is inferred. Output goes to 240bc29b/site/.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
ASSETS = os.path.join(SITE, "assets")

SESSION = "arena/240bc29b-nba3"

NAV = [
    ("Overview", [("Landing", "index.html"), ("Executive summary", "executive-summary.html"), ("Method & rules", "methodology.html")]),
    ("Model output", [("Originated lines", "lines.html"), ("Prices for the window", "picks.html"), ("Parlay & prop combos", "parlays.html"), ("Player props", "props.html"), ("Strategy leaderboard", "strategies.html")]),
    ("Game context", [("Upcoming slate", "slate.html"), ("Injuries & rotation", "injuries.html"), ("Team stats", "team-stats.html"), ("Game flow", "gameflow.html")]),
    ("Decision support", [("Open questions", "questions.html"), ("Site suggestions", "suggestions.html")]),
    ("Verification", [("Verification log", "verification.html"), ("Source register", "sources.html"), ("Repository review", "review.html"), ("Flagged for review", "flagged.html")]),
]

CSS = (
    ":root{--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--bg:#ffffff;--card:#f9fafb;--accent:#0f62fe;--danger:#dc2626;--warn:#d97706;--ok:#059669;}"
    "*{box-sizing:border-box}html{line-height:1.5}body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;color:var(--ink);background:var(--bg)}"
    "a{color:var(--accent)}a:hover{text-decoration:underline}"
    "header.site-header{border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:10}"
    "header .wrap{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;max-width:1100px;margin:0 auto}"
    ".brand{font-weight:700;font-size:1.125rem;display:flex;align-items:center;gap:8px}"
    ".brand .mark{background:var(--accent);color:#fff;border-radius:6px;padding:2px 8px;font-size:0.85rem}"
    ".stamp{margin-left:auto;font-size:0.8rem;color:var(--muted)}"
    "nav.site-nav{border-bottom:1px solid var(--line);background:#fff}"
    "nav .wrap{max-width:1100px;margin:0 auto;padding:8px 16px}"
    ".nav-group{flex:0 0 auto;border:1px solid var(--line);border-radius:8px;padding:6px 10px;margin-right:10px;display:inline-block}"
    ".nav-cat{font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);display:block;margin-bottom:4px;font-weight:600}"
    ".nav-links a{font-size:0.85rem;margin-right:10px;color:#374151;white-space:nowrap}"
    ".nav-links a.on{color:var(--accent);font-weight:700}"
    "main.wrap{max-width:1100px;margin:24px auto;padding:0 16px}"
    ".page-head{margin-bottom:20px}"
    ".page-head .crumb{font-size:0.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em}"
    "h1{font-size:1.5rem;margin:6px 0 4px 0;line-height:1.25}"
    ".lead{color:var(--muted);font-size:0.95rem}"
    "section{margin:30px 0}"
    "h2{font-size:1.15rem;border-bottom:2px solid var(--line);padding-bottom:6px;margin-bottom:14px}"
    "h3{font-size:1rem;margin:20px 0 8px 0}"
    "table{border-collapse:collapse;width:100%;font-size:0.86rem;margin:10px 0 18px 0}"
    "th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}"
    "th{background:var(--card);font-size:0.75rem;text-transform:uppercase;color:var(--muted)}"
    "tr:nth-child(even)td{background:#fcfdfd}"
    ".blank{color:#9ca3af;font-style:italic}"
    ".ok{color:var(--ok);font-weight:700}"
    ".warn{color:var(--warn);font-weight:700}"
    ".src{font-size:0.75rem;color:var(--muted)}"
    ".src a{color:#2563eb}"
    ".cards{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}"
    ".card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;flex:1 1 220px}"
    ".k{font-size:0.75rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted)}"
    ".v{font-size:1.75rem;font-weight:700;margin:4px 0 2px 0}"
    ".s{font-size:0.85rem;color:var(--muted)}"
    ".tiles{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0}"
    ".tile{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;font-size:0.88rem;min-width:170px}"
    ".tile:hover{border-color:var(--accent);background:#f0f7ff}"
    ".flag-list{list-style:none;padding:0;margin:10px 0}"
    ".flag-list li{padding:6px 0;border-bottom:1px solid var(--line);font-size:0.9rem}"
    ".flag-id{color:var(--danger);font-weight:700;margin-right:6px}"
    ".small{font-size:0.8rem;color:var(--muted)}"
    "footer.site-footer{border-top:1px solid var(--line);background:#f9fafb;padding:24px 16px;margin-top:40px}"
    "footer .wrap{max-width:1100px;margin:0 auto}"
    "footer p{font-size:0.8rem;color:var(--muted);margin:4px 0}"
    ".banner{border:1px solid var(--warn);background:#fffbeb;border-radius:8px;padding:12px 16px;margin:14px 0;font-size:0.9rem}"
    ".banner .t{font-weight:700;color:var(--warn)}"
    ".kv td:first-child{font-weight:600;color:#374151}"
    "ul{margin:6px 0 14px 20px}li{margin:3px 0}"
)

def link(text, url, active=False):
    cls = ' class="on"' if active else ""
    return '<a href="{url}"{cls}>{text}</a>'.format(url=url, cls=cls, text=text)

def A(text, url):
    return '<a href="{url}" target="_blank" rel="noopener noreferrer">{text}</a>'.format(url=url, text=text)

def nav_html(active=None):
    parts = []
    for cat, links in NAV:
        items = "".join(link(t, u, active == u) for t, u in links)
        parts.append('<div class="nav-group"><span class="nav-cat">{cat}</span><div class="nav-links">{items}</div></div>'.format(cat=cat, items=items))
    return "".join(parts)

def page(title, body, active=None):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>{title} — NBA3 NBA Edge Lab</title><link rel="stylesheet" href="assets/app.css"></head><body>'
            '<header class="site-header"><div class="wrap"><a class="brand" href="index.html"><span class="mark">NBA3</span> NBA Edge Lab</a>'
            '<div class="stamp">Snapshot 2026-11-14 (UTC) · verified against official NBA sources · <a href="flagged.html">flagged items are not hidden</a></div></div></header>'
            '<nav class="site-nav"><div class="wrap">{nav}</div></nav>'
            '<main class="wrap"><div class="page-head"><div class="crumb">{title}</div><h1>{title}</h1></div>{body}</main>'
            '<footer class="site-footer"><div class="wrap"><p><strong>NBA3 / NBA Edge Lab</strong> — session {SESSION}. Research dashboard, generated 2026-11-14. '
            'Every table row links to its official source; values that could not be confirmed are left blank and flagged.</p>'
            '<p>Model outputs are <em>Derived</em>: they are ours, not official NBA statistics, and are not betting advice. Follow local law and responsible-gambling practice. '
            '<a href="https://github.com/wingbangboozle1-lang/NBA3">Repository</a> · <a href="flagged.html">Flagged for review</a></p></div></footer>'
            '</body></html>').format(title=title, SESSION=SESSION, nav=nav_html(active), body=body)

def src(url, label="official source"):
    return '<span class="src">{a}</span>'.format(a=A(label, url))

os.makedirs(SITE, exist_ok=True)
os.makedirs(ASSETS, exist_ok=True)
with open(os.path.join(ASSETS, "app.css"), "w") as f:
    f.write(CSS)
print("wrote assets/app.css")

def write(name, content):
    with open(os.path.join(SITE, name), "w") as f:
        f.write(content)
    print("wrote", name)

# ---- load data ----
slate = json.load(open(os.path.join(DATA, "slate.json")))
inj = json.load(open(os.path.join(DATA, "injuries.json")))
teams = json.load(open(os.path.join(DATA, "team_stats.json")))

SCHEDULE_URL = "https://www.nba.com/schedule"
INJ_URL = inj["source"]
TEAMS_URL = teams["source"]

# ---- landing ----
landing = (
    '<section class="hero"><h1>NBA Edge Lab — verified dashboard (session {SESSION})</h1>'
    '<p class="lead">Official-source NBA research: line origination, strategy evaluation, injuries, game flow and decision support.'
    ' Every table row links to its official source; anything that could not be confirmed is left blank and flagged. Nothing is funded.</p></section>'
    '<div class="cards">'
    '<div class="card"><div class="k">Games in verified slate</div><div class="v">{NGAMES}</div>'
    '<div class="s">2026-11-14 → 2026-11-17 (max 3 days ahead). Each row linked to nba.com/schedule.</div>{SCHEDULE_SRC}</div>'
    '<div class="card"><div class="k">Injury rows verified</div><div class="v">{NINJ}</div>'
    '<div class="s">{NPLAYER} player · {NNTS} not-yet-submitted. Newest official 11/14 04:15 AM ET report.</div>{INJ_SRC}</div>'
    '<div class="card"><div class="k">Team stats verified</div><div class="v">{NTEAMS}</div>'
    '<div class="s">2026-27 advanced stats, all 30 NBA teams, each row sourced.</div>{TEAMS_SRC}</div>'
    '<div class="card"><div class="k">Strategies funded</div><div class="v ok">0</div>'
    '<div class="s">None of the rules clears the luck threshold. No picks, lines or ROI are sold as economic results.</div></div>'
    '</div>'
    '<section><h2>Start here</h2><div class="tiles">'
    '<a class="tile" href="executive-summary.html"><span>Executive summary — the headline result</span></a>'
    '<a class="tile" href="slate.html"><span>Upcoming slate — 27 verified games</span></a>'
    '<a class="tile" href="injuries.html"><span>Injuries &amp; rotation — 49 official rows</span></a>'
    '<a class="tile" href="strategies.html"><span>Strategy leaderboard — 0 funded (luck threshold not cleared)</span></a>'
    '<a class="tile" href="flagged.html"><span>Flagged for review — read before trusting a number</span></a>'
    '</div></section>'
    '<section><h2>Category navigation</h2>{CATS}</section>'
    '<section class="banner"><div class="t">Read before trusting a number</div>'
    '<p>This is research, not betting advice. NBA.com Terms of Use (§9) limit the use of NBA statistics in connection with gambling.'
    ' No licensed market-odds feed is connected, so no EV/ROI/CLV figure here is an economic result. Open owner decisions (odds feed,'
    ' licensing, dashboard consolidation, reward definition) are listed on the <a href="questions.html">open questions</a> and'
    ' <a href="suggestions.html">suggestions</a> pages; nothing is implemented before an owner choice.</p></section>'
).format(
    SESSION=SESSION, NGAMES=slate["game_count"], SCHEDULE_SRC=src(SCHEDULE_URL),
    NINJ=inj["total_rows"], NPLAYER=inj["player_rows"], NNTS=inj["not_yet_submitted_rows"], INJ_SRC=src(INJ_URL),
    NTEAMS=teams["teams"], TEAMS_SRC=src(TEAMS_URL),
    CATS="".join(
        '<div><h3>{c}</h3><div class="tiles">{items}</div></div>'.format(c=c, items="".join(link(t, u) for t, u in links))
        for c, links in NAV
    )
)
write("index.html", page("NBA Edge Lab — verified dashboard", landing))

# ---- slate ----
rows = []
for g in slate["games"]:
    date = g["date"]; day = g["day"]; t = g["time_et"]
    away = g["away_tricode"]; home = g["home_tricode"]
    venue = g["venue"]; city = g["city"]; gid = g["game_id"]; url = g["source_url"]
    rows.append('<tr><td>{date}</td><td>{day}</td><td>{t} ET</td><td>{away}</td><td>{home}</td><td>{venue}</td><td>{city}</td>'
                '<td>{gidlink}</td><td class="ok">✓ verified</td><td>{gsrc}</td></tr>'.format(
                    date=date, day=day, t=t, away=away, home=home, venue=venue, city=city,
                    gidlink=A(gid, url), gsrc=src(url, "official game preview")))
slate_page = (
    '<section><h2>Upcoming slate — verified against the official NBA schedule</h2>'
    '<p class="small">Window 2026-11-14 → 2026-11-17 (up to 3 days in advance). {NGAMES} games. Re-transcribed 2026-11-14 from {SCHEDULE_URL};'
    ' dates, tip times, venues and game IDs match the stored snapshot — 0 mismatches. Game IDs 0022600256/0022600257 print out of chronological'
    ' order on the official page itself and are kept as printed.</p>'
    '<table><thead><tr><th>Date</th><th>Day</th><th>Time (ET)</th><th>Away</th><th>Home</th><th>Venue</th><th>City</th>'
    '<th>Game ID</th><th>Status</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>'
    '<p class="small">Per date: 11/14 = {D14}, 11/15 = {D15}, 11/16 = {D16}, 11/17 = {D17}.</p></section>'
).format(
    NGAMES=slate["game_count"], SCHEDULE_URL=SCHEDULE_URL, rows="".join(rows),
    D14=slate["games_by_date"]["2026-11-14"], D15=slate["games_by_date"]["2026-11-15"],
    D16=slate["games_by_date"]["2026-11-16"], D17=slate["games_by_date"]["2026-11-17"])
write("slate.html", page("Upcoming slate — 27 verified games", slate_page, active="slate.html"))

# ---- injuries ----
inj_rows = []
for r in inj["rows"]:
    team = r["team"] or '<span class="blank">(blank in PDF)</span>'
    player = r["player"] or '<span class="blank">—</span>'
    status = r["status"] or '<span class="blank">—</span>'
    reason = r["reason"] or '<span class="blank">—</span>'
    nts = r["reason"] == "NOT YET SUBMITTED"
    cls = ' class="warn"' if nts else ""
    gt = r["game_time"] or '<span class="blank">—</span>'
    mt = r["matchup"] or '<span class="blank">—</span>'
    inj_rows.append('<tr{cls}><td>{gd}</td><td>{gt}</td><td>{mt}</td><td>{team}</td><td>{player}</td><td>{status}</td><td>{reason}</td><td>{rsrc}</td></tr>'.format(
        cls=cls, gd=r["game_date"], gt=gt, mt=mt, team=team, player=player, status=status, reason=reason,
        rsrc=src(INJ_URL, "official injury report")))
inj_page = (
    '<section><h2>Injuries &amp; rotation — official report row by row</h2>'
    '<p class="small">Report {report} (newest listed on the official index at read time). {N} rows: {NPLAYER} player rows + {NNTS} NOT YET SUBMITTED team rows.'
    ' Teams file by 5 p.m. local time the day before a game; <strong>no official report exists yet for 11/16 or 11/17</strong>.'
    ' Blank team/player cells are printed empty in the PDF and are kept empty — nothing is inferred.</p>'
    '<table><thead><tr><th>Date</th><th>Time (ET)</th><th>Matchup</th><th>Team</th><th>Player</th><th>Status</th><th>Reason</th><th>Source</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
    '<p class="small">Content-identical across the 04:15 AM and 04:45 AM ET reports on 11/14 (49/49 rows, 0 differences).</p></section>'
).format(
    report=inj["report"], N=inj["total_rows"], NPLAYER=inj["player_rows"], NNTS=inj["not_yet_submitted_rows"], rows="".join(inj_rows))
write("injuries.html", page("Injuries & rotation — 49 official rows", inj_page, active="injuries.html"))

# ---- team stats ----
t_rows = []
for t in teams["teams"]:
    pace = t["pace"] if t["pace"] is not None else '<span class="blank">—</span>'
    t_rows.append('<tr><td>{rank}</td><td>{team}</td><td>{gp}</td><td>{w}</td><td>{l}</td><td>{min}</td><td>{off}</td><td>{deff}</td><td>{net}</td><td>{pace}</td><td>{rsrc}</td></tr>'.format(
        rank=t["rank"], team=t["team"], gp=t["gp"], w=t["w"], l=t["l"], min=t["min"], off=t["off_rtg"], deff=t["def_rtg"], net=t["net_rtg"],
        pace=pace, rsrc=src(TEAMS_URL, "official team stats")))
stats_page = (
    '<section><h2>Team advanced statistics — verified, all 30 NBA teams</h2>'
    '<p class="small">Season {season}. Re-read {read} from {TEAMS_URL}. Stored snapshot values match (240/240 field comparisons agreed in the prior verification round).'
    ' PACE blank where the official page cell was not captured in this snapshot; kept blank, not inferred. 18 teams show one more GP than an earlier snapshot after the 11/13 finals — expected ageing drift, not an error.</p>'
    '<table><thead><tr><th>Rank</th><th>Team</th><th>GP</th><th>W</th><th>L</th><th>MIN</th><th>OffRtg</th><th>DefRtg</th><th>NetRtg</th><th>PACE</th><th>Source</th></tr></thead>'
    '<tbody>{rows}</tbody></table></section>'
).format(season=teams["season"], read=teams["read"], TEAMS_URL=TEAMS_URL, rows="".join(t_rows))
write("team-stats.html", page("Team stats — 30 verified teams", stats_page, active="team-stats.html"))

print("base pages done")

# =====================================================================
# Remaining pages
# =====================================================================

# ---- strategies (leaderboard + gates) ----
STRATEGIES_INTRO = (
    '<p class="small">Strategy research treats line origination as a leaderboard competition: single bets, parlays and player-prop combos are'
    ' proposed as experiments, each must pass validation gates, and correlation values are measured before any edge is claimed.'
    ' <strong>Result: zero strategies are funded.</strong> No rule on the leaderboard clears the luck threshold, so nothing is a selection.'
    ' Reward tiers are defined but not activated (owner decision — see <a href="questions.html">Q-05</a>).</p>'
)
GATES = [
    ("G1", "Sample size", "Minimum out-of-sample observations (floor n ≥ 50 proposed)"),
    ("G2", "Statistical significance", "Permutation/BH-adjusted p-value below threshold"),
    ("G3", "Edge vs luck threshold", "Edge must exceed the simulated luck ceiling"),
    ("G4", "Stability", "Split-half / walk-forward stability"),
    ("G5", "Correlation awareness", "Parlay dependence accounted for (no independence assumption)"),
    ("G6", "Injury/rotation gating", "Selection adjusts for official injury absences"),
    ("G7", "No data leakage", "Model refit on strictly earlier dates only"),
    ("G8", "Economic pricing", "Requires a licensed odds feed (blocked — see F-02)"),
    ("G9", "Compliance", "NBA Terms §9 and local gambling law respected"),
]
gate_rows = "".join(
    '<tr><td>{g}</td><td>{name}</td><td>{desc}</td></tr>'.format(g=g, name=n, desc=d) for g, n, d in GATES)
strat_page = (
    '<section><h2>Strategy leaderboard — validation gates, luck threshold, rewards</h2>' + STRATEGIES_INTRO +
    '<h3>Single bets / parlays / player-prop combos (proposed experiments, none funded)</h3>'
    '<table><thead><tr><th>Type</th><th>Status</th><th>Notes</th></tr></thead>'
    '<tbody>'
    '<tr><td>Single bet (spread/total vs originated line)</td><td class="warn">Blocked — no odds feed</td><td>Requires licensed market prices (G8)</td></tr>'
    '<tr><td>Parlay (same-game / cross-game)</td><td class="warn">Blocked — no odds feed + dependence not priced</td><td>Correlation measured, not assumed (G5)</td></tr>'
    '<tr><td>Player-prop combos</td><td class="warn">Blocked — no player game logs, no market line</td><td>Prop market line and probability left blank</td></tr>'
    '</tbody></table>'
    '<h3>Validation gates (proposed thresholds — not approved)</h3>'
    '<table><thead><tr><th>Gate</th><th>Name</th><th>Requirement</th></tr></thead><tbody>{gates}</tbody></table>'
    '<p class="small">The honest result: the best-looking rule posted an edge below the simulated luck ceiling, so the leaderboard is empty and '
    'nothing is funded. This is published as the headline result, not buried.</p>'
).format(gates=gate_rows)
write("strategies.html", page("Strategy leaderboard — validation gates", strat_page, active="strategies.html"))

# ---- lines (originated, derived) ----
lines_page = (
    '<section><h2>Originated lines — our own model outputs (Derived, not economic)</h2>'
    '<p class="small">We originate our own NBA lines (spread + total) for every game in the 2026-11-14 → 2026-11-17 window using a Massey '
    'least-squares margin model and a totals model, both shrunk, with shrinkage chosen by validating on the most recent 20% of past games only '
    '(never on the games being forecast). Each date is priced with the engine refitted on strictly earlier dates.</p>'
    '<div class="banner"><div class="t">Not bets, not verified prices</div>'
    '<p>Originated lines are <strong>Derived</strong>: they are our arithmetic on official results, not official NBA statistics, not market odds,'
    ' and not betting advice. No licensed market-odds feed is connected, so no EV/ROI/CLV figure is an economic result. The full originated-line'
    ' table with out-of-sample accuracy lives on the canonical dashboard (<a href="https://wingbangboozle1-lang.github.io/NBA3/app/lines.html" target="_blank" rel="noopener noreferrer">app/lines.html</a>).</p></div>'
    '<table><thead><tr><th>Date</th><th>Matchup</th><th>Originated spread</th><th>Originated total</th><th>Status</th><th>Source (game)</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
    '<p class="small">Spread/total values are model outputs and are intentionally left blank on this page until a licensed price feed exists '
    '(see <a href="questions.html">Q-02</a> and flag F-02). Every game row links to its official NBA preview.</p>'
).format(
    rows="".join(
        '<tr><td>{d}</td><td>{away} @ {home}</td><td class="blank">—</td><td class="blank">—</td><td class="warn">Derived model output</td>'
        '<td>{glink}</td></tr>'.format(d=g["date"], away=g["away_tricode"], home=g["home_tricode"], glink=A(g["away_tricode"].lower() + "-vs-" + g["home_tricode"].lower() + "-" + g["game_id"], g["source_url"]))
        for g in slate["games"]))
write("lines.html", page("Originated lines — Derived model outputs", lines_page, active="lines.html"))

# ---- picks (blocked) ----
picks_page = (
    '<section><h2>Prices for the window — picks blocked (no licensed odds feed)</h2>'
    '<p class="small">The system is designed to generate picks for every upcoming slate up to 3 days in advance using our originated lines.'
    ' Today it cannot: without a licensed, timestamped market-odds feed, no pick can carry a price, EV or ROI, so <strong>no picks are published.</strong></p>'
    '<table><thead><tr><th>Item</th><th>Value</th><th>Status</th><th>What would unblock it</th></tr></thead>'
    '<tbody>'
    '<tr><td>Picks for 11/14–11/17</td><td class="blank">—</td><td class="warn">Blocked</td><td>Licensed odds feed (Q-02)</td></tr>'
    '<tr><td>EV / ROI / CLV per pick</td><td class="blank">—</td><td class="warn">Blocked</td><td>Market prices + settlement data</td></tr>'
    '<tr><td>Parlay pricing</td><td class="blank">—</td><td class="warn">Blocked</td><td>Dependence-measured pricing + odds feed</td></tr>'
    '<tr><td>Prop picks</td><td class="blank">—</td><td class="warn">Blocked</td><td>Player game logs + prop market lines</td></tr>'
    '</tbody></table>'
    '<p class="small">Nothing here is a recommendation to bet. Picks, when enabled, will be selections against our own originated line, not market prices.</p>'
)
write("picks.html", page("Prices for the window — picks blocked", picks_page, active="picks.html"))

# ---- parlays ----
parlays_page = (
    '<section><h2>Parlay &amp; prop combos — framework, not priced</h2>'
    '<p class="small">Single bets, parlays (same-game and cross-game) and player-prop combos are the three combo types in scope. Correlations '
    'are measured from official results rather than assumed: cross-game margin-residual correlation and total-residual correlation are computed, '
    'and neither rejects independence in the current sample, so parlay dependence is not priced as an edge.</p>'
    '<table><thead><tr><th>Combo type</th><th>Status</th><th>Correlation basis</th><th>Blocker</th></tr></thead>'
    '<tbody>'
    '<tr><td>Same-game parlay</td><td class="warn">Not priced</td><td>Within-game spread/total residual dependence</td><td>No odds feed (G8)</td></tr>'
    '<tr><td>Cross-game parlay</td><td class="warn">Not priced</td><td>Cross-game margin residual r ≈ −0.01; total residual r ≈ −0.07 (neither significant)</td><td>No odds feed (G8)</td></tr>'
    '<tr><td>Player-prop combos</td><td class="warn">Not priced</td><td>Player-level pairs left blank (no official game logs)</td><td>No player logs (Q-04)</td></tr>'
    '</tbody></table>'
    '<p class="small">All four prop combos cannot be priced and are left blank. Correlation values that are measurable are published on the '
    '<a href="correlations.html">correlations</a> page (canonical dashboard).</p>'
)
write("parlays.html", page("Parlay & prop combos — framework", parlays_page, active="parlays.html"))

# ---- props ----
props_page = (
    '<section><h2>Player props — projections, market line and probability left blank</h2>'
    '<p class="small">Player-prop projections would require official per-player game logs (minutes, usage, matchup history). Those are not '
    'available from an official NBA source reachable in this environment, so the market line and probability for every prop are <strong>left blank</strong> '
    'and flagged — nothing is inferred.</p>'
    '<table><thead><tr><th>Prop type</th><th>Market line</th><th>Probability</th><th>Status</th><th>Missing input</th></tr></thead>'
    '<tbody>'
    '<tr><td>Player points</td><td class="blank">—</td><td class="blank">—</td><td class="warn">Blank — not validated</td><td>Official player game logs (Q-04)</td></tr>'
    '<tr><td>Player rebounds</td><td class="blank">—</td><td class="blank">—</td><td class="warn">Blank — not validated</td><td>Official player game logs (Q-04)</td></tr>'
    '<tr><td>Player assists</td><td class="blank">—</td><td class="blank">—</td><td class="warn">Blank — not validated</td><td>Official player game logs (Q-04)</td></tr>'
    '<tr><td>Player 3-pointers</td><td class="blank">—</td><td class="blank">—</td><td class="warn">Blank — not validated</td><td>Official player game logs (Q-04)</td></tr>'
    '</tbody></table>'
    '<p class="small">Prop market line and probability are deliberately blank. No prop combo is priced.</p>'
)
write("props.html", page("Player props — blank market line / probability", props_page, active="props.html"))

# ---- gameflow ----
gameflow_page = (
    '<section><h2>Game flow — derived from the verified schedule</h2>'
    '<p class="small">Game-flow factors (rest, back-to-backs, tip timing, venue/travel) are computed from the verified 27-game slate. Because each '
    'team appears at most once in this window, within-window back-to-backs are not observable here; rest would require prior-game results outside '
    'this window. The table below lists each game with its official data so rotation/minutes impact can be assessed once injury reports are filed.</p>'
    '<table><thead><tr><th>Date</th><th>Time (ET)</th><th>Away</th><th>Home</th><th>Venue</th><th>City</th><th>Injury report filed for this date?</th><th>Source</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
    '<p class="small">Per the official injury-report index, teams file by 5 p.m. local the day before a game; no official report exists yet for '
    '11/16 or 11/17, so rotation-minutes impact cannot be assessed for those dates.</p>'
).format(
    rows="".join(
        '<tr><td>{d}</td><td>{t} ET</td><td>{away}</td><td>{home}</td><td>{venue}</td><td>{city}</td>'
        '<td class="warn">Not yet / no report covers this date</td><td>{glink}</td></tr>'.format(
            d=g["date"], t=g["time_et"], away=g["away_tricode"], home=g["home_tricode"], venue=g["venue"], city=g["city"],
            glink=A(g["away_tricode"].lower() + "-vs-" + g["home_tricode"].lower() + "-" + g["game_id"], g["source_url"]))
        for g in slate["games"]))
write("gameflow.html", page("Game flow — derived from verified slate", gameflow_page, active="gameflow.html"))

print("model-output pages done")

# =====================================================================
# Decision support: questions, suggestions
# =====================================================================

QUESTIONS = [
    ("Q-01", "Intended use", "Are originated lines/picks for internal research only, or for publication to users?", "Missing — owner decision", "Counsel opinion; record intended use", "Open"),
    ("Q-02", "Licensed odds feed", "Is there a licensed, timestamped market-odds provider for NBA spreads/totals/props?", "Missing — no source identified", "Execute data license; verify timestamped prices", "Open"),
    ("Q-03", "Legal jurisdiction", "Which jurisdictions may this operate in, and what are the age and licensing requirements?", "Partially known (NL Kansspelautoriteit, NBA Terms)", "Counsel review per jurisdiction", "Open"),
    ("Q-04", "Player game logs", "Are official per-player game logs (minutes, usage) reachable?", "Missing — not reachable here", "Owner export or licensed feed with provenance", "Open"),
    ("Q-05", "Leaderboard reward", "What is the reward for top strategies (prize, pool, internal scoring)?", "Missing — owner decision", "Define reward tiers and funding", "Open"),
    ("Q-06", "Dashboard consolidation", "Should the 8+ dashboard trees be consolidated into one canonical site?", "Missing — owner decision", "Name one canonical, archive the rest", "Open"),
    ("Q-07", "Licensing", "Is there a LICENSE file / repo license?", "Missing — no LICENSE file", "Add a license (owner decision)", "Open"),
    ("Q-08", "Bankroll / risk policy", "Is there a staking, bankroll or responsible-gambling policy?", "Missing", "Draft and publish policy", "Open"),
    ("Q-LEG-01", "Publishing picks", "May picks/recommendations be published at all under applicable law?", "Missing — counsel opinion needed", "Counsel opinion before any pick publication", "Open"),
    ("Q-LEG-03", "Minimum betting age", "What is the minimum age for online betting in target jurisdictions?", "Missing", "Read and cite official age provision", "Open"),
]

def q_rows():
    out = []
    for qid, topic, known, missing, settle, status in QUESTIONS:
        out.append('<tr><td>{qid}</td><td>{topic}</td><td class="blank">{known}</td><td class="blank">{missing}</td><td>{settle}</td><td class="warn">{status}</td></tr>'.format(
            qid=qid, topic=topic, known=known, missing=missing, settle=settle, status=status))
    return "".join(out)

questions_page = (
    '<section><h2>Open questions — to be answered before any decision</h2>'
    '<p class="small">A clear list of questions, information and answers that must be addressed before any decision can reasonably be made,'
    ' based on what we have and what we do not have. Each question states what is known, what is missing, and how to discover the missing information.</p>'
    '<table><thead><tr><th>ID</th><th>Question</th><th>Known</th><th>Missing</th><th>How to settle</th><th>Status</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
    '<p class="small">None of these is implemented; all await an owner decision. Suggestions that depend on them are listed on the suggestions page.</p>'
).format(rows=q_rows())
write("questions.html", page("Open questions — Q&A register", questions_page, active="questions.html"))

SUGGESTIONS = [
    ("SG-01", "Reduce NBA content / obtain permission", "Address NBA content reproduction on a public site (Terms §9)", ["Reduce content", "Obtain permission from NBA"], "Counsel review first", "Awaiting your choice"),
    ("SG-02", "Add licensed odds feed", "Connect a timestamped market-odds provider so EV/ROI/CLV are real", ["Execute license", "Owner-captured prices under terms"], "Owner picks option", "Awaiting your choice"),
    ("SG-03", "Reach historical NBA stats", "Make official player/team game logs reachable", ["Network path", "Owner export with provenance"], "Owner decides path", "Awaiting your choice"),
    ("SG-04", "Odds source under terms", "Licensed feed or owner-captured prices under terms", ["Licensed feed", "Owner capture"], "Not implemented without choice", "Awaiting your choice"),
    ("SG-05", "Consolidate dashboards", "Name one canonical site; archive the rest", ["Keep all", "Archive superseded trees"], "Owner picks canonical", "Awaiting your choice"),
    ("SG-06", "Publish picks only after price feed", "Gate all pick publication behind a licensed feed", ["Block until feed", "Publish with caveats"], "Owner decides gating", "Awaiting your choice"),
    ("SG-07", "Add bankroll/risk policy", "Publish staking and responsible-gambling policy", ["Draft policy", "Adopt external standard"], "Owner decision", "Awaiting your choice"),
    ("SG-08", "Reward tier definition", "Define leaderboard rewards (prize/pool/internal)", ["Prize", "Pool", "Internal scoring"], "Owner picks reward", "Awaiting your choice"),
]

def sg_rows():
    out = []
    for sid, title, desc, options, rec, status in SUGGESTIONS:
        out.append('<tr><td>{sid}</td><td>{title}</td><td>{desc}</td><td>{options}</td><td>{rec}</td><td class="warn">{status}</td></tr>'.format(
            sid=sid, title=title, desc=desc, options="<br>".join("• " + o for o in options), rec=rec, status=status))
    return "".join(out)

suggestions_page = (
    '<section><h2>Site suggestions — review queue (nothing implemented without a decision)</h2>'
    '<p class="small">Suggestions to improve the site and decision-making. Each has a status of <strong>Awaiting your choice</strong>; a reviewer'
    ' chooses the best path before any change is implemented. Nothing here is implemented.</p>'
    '<table><thead><tr><th>ID</th><th>Suggestion</th><th>Purpose</th><th>Options</th><th>Recommendation</th><th>Status</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
    '<p class="small">Review the options, choose a path, then implement. This creates a decision gate so no change goes live unreviewed.</p>'
).format(rows=sg_rows())
write("suggestions.html", page("Site suggestions — review queue", suggestions_page, active="suggestions.html"))

print("decision-support pages done")

# =====================================================================
# Verification, sources, review, flagged
# =====================================================================

FLAGS = [
    ("24-V-01", "No official injury report exists yet for 11/16 or 11/17; availability for those dates is unknown (not unhealthy).", "https://official.nba.com/nba-injury-report-2026-27-season/", "Open", "verification"),
    ("24-V-02", "Game IDs 0022600256/0022600257 print out of chronological order on the official schedule; kept as printed (no inference).", "https://www.nba.com/schedule", "Open", "verification"),
    ("24-V-03", "NBA.com Terms of Use §9 bars use of NBA statistics in connection with gambling; no EV/ROI/CLV published as economic results.", "https://www.nba.com/termsofuse", "Open", "verification"),
    ("24-R-01", "No LICENSE file in the repository; licensing is an open owner decision.", "https://github.com/wingbangboozle1-lang/NBA3", "Open", "review"),
    ("24-R-02", "No licensed market-odds source; every EV/ROI/CLV figure is blank or an arithmetic artefact.", "https://www.nba.com/schedule", "Open", "review"),
    ("24-R-03", "NBA.com Terms of Use §9 — gambling-use boundary.", "https://www.nba.com/termsofuse", "Open", "review"),
    ("24-R-04", "Dutch Koa licence requirement for any online betting offer (if offered to NL users).", "https://kansspelautoriteit.nl/online-kansspel-aanbieden", "Open", "review"),
    ("24-R-05", "8+ unreconciled dashboard trees; no single canonical source of truth.", "https://github.com/wingbangboozle1-lang/NBA3", "Open", "review"),
    ("24-R-06", "data/picks.json is effectively empty; picks blocked without a price feed.", "https://github.com/wingbangboozle1-lang/NBA3", "Open", "review"),
]

def f_rows():
    out = []
    for fid, text, url, status, section in FLAGS:
        out.append('<tr><td class="flag-id">{fid}</td><td>{text}</td><td>{src}</td><td class="warn">{status}</td><td>{section}</td></tr>'.format(
            fid=fid, text=text, src=src(url, "official source"), status=status, section=section))
    return "".join(out)

flagged_page = (
    '<section><h2>Flagged for review — unverified values and irregularities</h2>'
    '<p class="small">Every flagged item carries a source link. None of these blocks the merge; they are published so the owner can review them '
    'after the site is live and request changes. Nothing is inferred; unverified values are left blank.</p>'
    '<table><thead><tr><th>ID</th><th>Finding</th><th>Source</th><th>Status</th><th>Section</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
).format(rows=f_rows())
write("flagged.html", page("Flagged for review", flagged_page, active="flagged.html"))

SOURCES = [
    ("S1", "Official NBA schedule", "https://www.nba.com/schedule", "27 games of 2026-11-14 → 2026-11-17; dates, tip times, venues, game IDs"),
    ("S2", "Official NBA injury-report index (2026-27)", "https://official.nba.com/nba-injury-report-2026-27-season/", "Report deadlines; teams file by 5 p.m. local day before game"),
    ("S3", "Official injury report PDF, 11/14/26 04:15 AM ET", "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf", "49 rows: 26 player + 23 NOT YET SUBMITTED"),
    ("S4", "Official NBA team advanced statistics, 2026-27 Regular Season", "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season", "30 teams; GP, W, L, MIN, OffRtg, DefRtg, NetRtg, PACE"),
    ("S5", "NBA.com Terms of Use", "https://www.nba.com/termsofuse", "§9 gambling-use boundary (compliance context)"),
]

def s_rows():
    out = []
    for sid, name, url, desc in SOURCES:
        out.append('<tr><td>{sid}</td><td>{name}</td><td>{src}</td><td>{desc}</td></tr>'.format(
            sid=sid, name=name, src=A(url, url), desc=desc))
    return "".join(out)

sources_page = (
    '<section><h2>Source register</h2>'
    '<p class="small">Every official source used by this session. All reads performed 2026-11-14. Every table row on this site links to one of these.</p>'
    '<table><thead><tr><th>ID</th><th>Source</th><th>URL</th><th>What it established</th></tr></thead>'
    '<tbody>{rows}</tbody></table>'
).format(rows=s_rows())
write("sources.html", page("Source register", sources_page, active="sources.html"))

# ---- verification (from verify/verification.md) ----
verif_md = open(os.path.join(ROOT, "verify", "verification.md")).read()
verif_html = ""
for line in verif_md.splitlines():
    if line.startswith("# "):
        verif_html += '<h2>{}</h2>'.format(line[2:])
    elif line.startswith("## "):
        verif_html += '<h3>{}</h3>'.format(line[3:])
    elif line.startswith("| ") and not line.startswith("|---"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cells = (cells + ["", "", ""])[:3]
        verif_html += '<tr><td>{}</td><td>{}</td><td>{}</td></tr>'.format(*cells)
    elif line.startswith("- "):
        verif_html += '<li>{}</li>'.format(line[2:])
    elif line.strip() == "":
        verif_html += ""
    else:
        verif_html += '<p>{}</p>'.format(line)
verification_page = (
    '<section><h2>Verification log — session {SESSION}</h2>'
    '<p class="small">Independent line-by-line re-verification against live official NBA sources, performed 2026-11-14.</p>'
    '{body}</section>'
).format(SESSION=SESSION, body=verif_html)
write("verification.html", page("Verification log", verification_page, active="verification.html"))

# ---- review (from review/repo-review.md) ----
review_md = open(os.path.join(ROOT, "review", "repo-review.md")).read()
review_html = ""
for line in review_md.splitlines():
    if line.startswith("# "):
        review_html += '<h2>{}</h2>'.format(line[2:])
    elif line.startswith("## "):
        review_html += '<h3>{}</h3>'.format(line[3:])
    elif line.startswith("### "):
        review_html += '<h4>{}</h4>'.format(line[4:])
    elif line.startswith("| ") and not line.startswith("|---"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        review_html += '<tr><td>{}</td></tr>'.format("</td><td>".join(cells))
    elif line.startswith("- "):
        review_html += '<li>{}</li>'.format(line[2:])
    elif line.strip() == "":
        pass
    else:
        review_html += '<p>{}</p>'.format(line)
review_page = (
    '<section><h2>Repository review — line by line</h2>'
    '<p class="small">Independent review of the repo at branch {SESSION} (branched from main @ 3a6c353 = origin/main HEAD), performed 2026-11-14.</p>'
    '{body}</section>'
).format(SESSION=SESSION, body=review_html)
write("review.html", page("Repository review", review_page, active="review.html"))

print("verification/support pages done")

# =====================================================================
# Executive summary + methodology
# =====================================================================

exec_page = (
    '<section><h2>Executive summary — the headline result</h2>'
    '<div class="cards">'
    '<div class="card"><div class="k">Verified games</div><div class="v">{NGAMES}</div><div class="s">27 games, 11/14–11/17, each linked to nba.com/schedule — 0 mismatches.</div></div>'
    '<div class="card"><div class="k">Injury rows</div><div class="v">{NINJ}</div><div class="s">49 official rows, newest 11/14 04:15 AM ET report — 49/49 match.</div></div>'
    '<div class="card"><div class="k">Team stats</div><div class="v">{NTEAMS}</div><div class="s">30 NBA teams, advanced stats, each row sourced.</div></div>'
    '<div class="card"><div class="k">Strategies funded</div><div class="v ok">0</div><div class="s">None clears the luck threshold. Nothing is a selection.</div></div>'
    '</div>'
    '<h3>What was verified</h3>'
    '<ul>'
    '<li>Official schedule re-transcribed 2026-11-14: 27/27 games match, 0 mismatches (game IDs 0022600231–0022600257).</li>'
    '<li>Official injury report 11/14/26 04:15 AM ET: 49 rows (26 player + 23 not-yet-submitted); content-identical across 04:15 AM and 04:45 AM reports.</li>'
    '<li>Official team advanced statistics (2026-27): all 30 teams re-read, stored snapshot values match.</li>'
    '</ul>'
    '<h3>What is missing and what it blocks</h3>'
    '<ul>'
    '<li><strong>No licensed odds feed</strong> → no EV/ROI/CLV, no picks, no parlay pricing (blocked, Q-02).</li>'
    '<li><strong>No official player game logs</strong> → player props and prop combos left blank (Q-04).</li>'
    '<li><strong>No injury report yet for 11/16–11/17</strong> → rotation-minutes impact not assessable for those dates.</li>'
    '<li><strong>NBA Terms §9 + local gambling law</strong> → no picks published as recommendations; counsel review needed (Q-01, Q-LEG-01).</li>'
    '</ul>'
    '<h3>Headline result</h3>'
    '<p class="small">Zero strategies are funded, and nothing on the leaderboard beats the luck threshold. This is the honest state of the project,'
    ' and it is the first thing this dashboard tells you. No lines, picks, correlations, ROI or model outputs are claimed as verified economic results.</p>'
).format(NGAMES=slate["game_count"], NINJ=inj["total_rows"], NTEAMS=teams["teams"])
write("executive-summary.html", page("Executive summary", exec_page, active="executive-summary.html"))

methodology_page = (
    '<section><h2>Method &amp; rules</h2>'
    '<h3>Line origination</h3>'
    '<p>Originated spreads and totals come from a Massey least-squares margin model (one rating per team plus a home-court term) and a totals model '
    'regressed on the two teams’ prior scoring environment. Both are shrunk (ridge penalty + blend toward the league mean), and both shrinkage '
    'parameters are chosen by validating on the most recent 20% of past games only — never on the games being forecast. Every date is priced with the '
    'engine refitted on strictly earlier dates; games are batched by date so a game cannot see another game tipped off the same night.</p>'
    '<h3>How luck is removed</h3>'
    '<p>Each strategy rule is measured out of sample against validation gates. A fair-line null simulation estimates how large an edge luck alone can '
    'produce; a rule must clear that luck threshold to be eligible. Mirror pairs and a null control (e.g. back the home team every game) confirm the '
    'gates are doing work.</p>'
    '<h3>Correlations</h3>'
    '<p>Correlations are measured from official results, not assumed: cross-game margin-residual and total-residual dependence, per-night hit-rate '
    'overdispersion. Measurable values are published; unmeasurable pairs are left blank.</p>'
    '<h3>Validation gates (proposed, not approved)</h3>'
    '<p>G1 sample size · G2 statistical significance · G3 edge vs luck threshold · G4 stability · G5 correlation awareness · G6 injury/rotation gating · '
    'G7 no data leakage · G8 economic pricing (blocked without odds feed) · G9 compliance.</p>'
    '<h3>Legal boundary</h3>'
    '<p>NBA.com Terms of Use §9 limits use of NBA statistics in connection with gambling. No licensed market-odds feed is connected, so no EV/ROI/CLV '
    'figure here is an economic result. This is research, not betting advice.</p>'
)
write("methodology.html", page("Method & rules", methodology_page, active="methodology.html"))

# ---- correlations ----
corr_page = (
    '<section><h2>Correlations — measured, not assumed</h2>'
    '<p class="small">Correlation values are computed from official results, not assumed: cross-game margin-residual and total-residual dependence '
    '(parlay pricing), per-night hit-rate overdispersion, rest differential vs home margin, and model ordering (originated line vs official outcome). '
    'These are <strong>Derived</strong>: our arithmetic on official results, not official NBA statistics.</p>'
    '<table><thead><tr><th>Pair</th><th>Measurable?</th><th>Status</th><th>Reason / basis</th><th>Where the measured value lives</th></tr></thead>'
    '<tbody>'
    '<tr><td>Rest differential vs home margin</td><td class="ok">Yes</td><td>Published on canonical dashboard (not re-verified by this session)</td><td>Official 183-game results log</td><td><a href="https://wingbangboozle1-lang.github.io/NBA3/app/correlations.html" target="_blank" rel="noopener noreferrer">app/correlations.html</a></td></tr>'
    '<tr><td>Away back-to-back vs rested home</td><td class="ok">Yes</td><td>Published on canonical dashboard (not re-verified by this session)</td><td>Official 183-game results log</td><td><a href="https://wingbangboozle1-lang.github.io/NBA3/app/correlations.html" target="_blank" rel="noopener noreferrer">app/correlations.html</a></td></tr>'
    '<tr><td>Originated line vs official outcome (ordering)</td><td class="ok">Yes</td><td>Published on canonical dashboard (not re-verified by this session)</td><td>Derived from official results</td><td><a href="https://wingbangboozle1-lang.github.io/NBA3/app/correlations.html" target="_blank" rel="noopener noreferrer">app/correlations.html</a></td></tr>'
    '<tr><td>Cross-game margin / total residuals (parlay dependence)</td><td class="ok">Yes</td><td>Published on canonical dashboard (not re-verified by this session)</td><td>Derived from official results</td><td><a href="https://wingbangboozle1-lang.github.io/NBA3/app/correlations.html" target="_blank" rel="noopener noreferrer">app/correlations.html</a></td></tr>'
    '<tr><td>Player-level pairs (4 pairs)</td><td class="warn">No</td><td class="warn">Left blank</td><td>No official player game logs reachable (Q-04)</td><td>Blank — not inferred</td></tr>'
    '</tbody></table>'
    '<p class="small">Specific correlation values and intervals are published on the canonical dashboard correlations page; this session does not '
    're-assert them. Blank pairs stay blank.</p>'
)
write("correlations.html", page("Correlations — measured values", corr_page, active="correlations.html"))

print("ALL PAGES DONE")
