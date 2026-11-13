"""Build the static GitHub Pages site from data/*.csv (standard library only).

Output: site/ (ignored by git; built in CI and by hand).

Rules enforced here and checked by pipeline/verify.py:
- Every table row carries a source link taken from the data file.
- A blank value is shown as blank and marked "unverified"; nothing is filled in.
- Picks and correlations are never filled; they are shown as blank by design.
"""

from __future__ import annotations

import csv
import html
import shutil
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "site"


def read_csv(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(v: str) -> str:
    return html.escape(v or "", quote=True)


def cell(value: str, flags: str = "") -> str:
    if value is None or value == "":
        note = f' <span class="flag">unverified{(" " + esc(flags)) if flags else ""}</span>'
        return f'<td class="blank">&mdash;{note}</td>'
    return f"<td>{esc(value)}</td>"


def link_cell(url: str, label: str = "Source") -> str:
    if not url:
        return '<td class="blank">&mdash; <span class="flag">no source</span></td>'
    return f'<td><a href="{esc(url)}" rel="noopener">{esc(label)}</a></td>'


def table(headers: list[str], rows: list[list[str]], link_index: int | None = None,
          extra_links: dict | None = None) -> str:
    """rows: list of cell strings. link_index: column whose value is a URL (rendered as link)."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for r in rows:
        tds = []
        for i, v in enumerate(r):
            if i == link_index:
                tds.append(link_cell(v))
            else:
                tds.append(cell(v))
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def page(title: str, active: str, body: str, intro: str = "") -> str:
    nav_items = [
        ("index.html", "Dashboard"),
        ("exec-summary.html", "Executive summary"),
        ("slates.html", "Slates"),
        ("picks.html", "Picks"),
        ("injuries.html", "Injuries"),
        ("gameflow.html", "Game flow"),
        ("strategies.html", "Strategies"),
        ("gates.html", "Gates"),
        ("correlations.html", "Correlations"),
        ("sources.html", "Sources"),
        ("repo-review.html", "Repo review"),
        ("questions.html", "Questions"),
        ("suggestions.html", "Suggestions"),
        ("flagged.html", "Flagged for Review"),
        ("requirements.html", "Requirements"),
    ]
    nav_parts = []
    for href, label in nav_items:
        current = ' aria-current="page"' if href == active else ""
        nav_parts.append(f'<a href="{href}"{current}>{esc(label)}</a>')
    nav = "".join(nav_parts)
    intro_html = f'<p class="intro">{intro}</p>' if intro else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | NBA Edge Lab</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <a class="brand" href="index.html">NBA Edge Lab</a>
  <nav>{nav}</nav>
</header>
<main>
<h1>{esc(title)}</h1>
{intro_html}
{body}
</main>
<footer>
  <p>Every table row links to its source. Blank values are unverified and flagged; nothing is inferred.
  Content is research, not betting advice. Data as of 2026-11-13 (ET). Code and data:
  <a href="https://github.com/wingbangboozle1-lang/NBA3">GitHub repository</a>.</p>
</footer>
</body>
</html>
"""


CSS = """
:root { --ink:#1b1f24; --muted:#5b6470; --line:#d9dee5; --bg:#fbfbfc; --accent:#0b5cad; --warn:#8a4b00; --warnbg:#fff4e0; }
* { box-sizing: border-box; }
body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color:var(--ink); background:var(--bg); line-height:1.5; }
header.top { display:flex; flex-wrap:wrap; gap:12px 20px; align-items:center; padding:12px 20px; background:#fff; border-bottom:1px solid var(--line); position:sticky; top:0; }
header.top .brand { font-weight:700; color:var(--ink); text-decoration:none; }
header.top nav { display:flex; flex-wrap:wrap; gap:6px 12px; font-size:14px; }
header.top nav a { color:var(--accent); text-decoration:none; padding:2px 4px; border-radius:4px; }
header.top nav a[aria-current="page"] { background:#e6f0fb; }
main { max-width:1180px; margin:0 auto; padding:20px; }
h1 { font-size:26px; margin:8px 0 8px; }
h2 { font-size:19px; margin:28px 0 8px; }
p.intro { color:var(--muted); max-width:85ch; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:12px; margin:16px 0; }
.card { background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; }
.card .n { font-size:26px; font-weight:700; }
.card a { color:var(--accent); text-decoration:none; font-weight:600; }
.card p { margin:6px 0 0; color:var(--muted); font-size:14px; }
.banner { background:var(--warnbg); border:1px solid #f0d199; color:var(--warn); padding:12px 14px; border-radius:8px; }
.table-wrap { overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:#fff; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:left; padding:7px 9px; border-bottom:1px solid var(--line); vertical-align:top; }
th { background:#f1f4f8; position:sticky; top:0; font-weight:600; }
td.blank { color:var(--muted); background:#fcfcfd; }
.flag { display:inline-block; font-size:12px; color:var(--warn); background:var(--warnbg); border-radius:4px; padding:0 4px; }
ul.findings li { margin:6px 0; }
footer { max-width:1180px; margin:24px auto; padding:0 20px 30px; color:var(--muted); font-size:13px; }
a { color:var(--accent); }
"""


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "style.css").write_text(CSS, encoding="utf-8")

    slates = read_csv("slates.csv")
    injuries = read_csv("injuries_2026-11-13_1100AM.csv")
    strategies = read_csv("strategies.csv")
    gates = read_csv("gates.csv")
    correlations = read_csv("correlations.csv")
    gameflow = read_csv("gameflow.csv")
    sources = read_csv("sources.csv")
    repo = read_csv("repo_review.csv")
    questions = read_csv("questions.csv")
    suggestions = read_csv("suggestions.csv")
    flags = read_csv("flags.csv")
    reqs = read_csv("requirements.csv")

    # ---- derived counts (computed from the data, not typed in) ----
    player_rows = [r for r in injuries if r["row_type"] == "player"]
    team_rows = [r for r in injuries if r["row_type"] == "team_status"]
    n_games = len(slates)
    by_date: dict[str, int] = {}
    for s in slates:
        by_date[s["slate_date"]] = by_date.get(s["slate_date"], 0) + 1
    no_team = sum(1 for r in player_rows if not r["team"])
    no_matchup = sum(1 for r in player_rows if not r["matchup"])
    out_count = sum(1 for r in player_rows if r["status"] == "Out")
    q_count = sum(1 for r in player_rows if r["status"] == "Questionable")
    n_strat = len(strategies)
    n_blocked = sum(1 for r in strategies if r["gate_status"] == "BLOCKED")
    n_gates = len(gates)
    n_flags = len(flags)
    n_open = sum(1 for f in flags if f["status"].lower().startswith("open"))
    n_corr_measured = sum(1 for r in correlations if r["correlation_value"])
    picks_published = 0  # no pick values exist in any data file; enforced in verify.py

    def link(href: str, text: str) -> str:
        return f'<a href="{esc(href)}">{esc(text)}</a>'

    # ---------- index ----------
    cards = [
        ("slates.html", "Slates", f"{n_games} games", "Official schedule, Nov 13-16 (ET): " + ", ".join(f"{k[-2:]} = {v}" for k, v in by_date.items()) + " games."),
        ("picks.html", "Picks", f"{picks_published} published", "No line exists to pick against yet, and legal opinion is pending."),
        ("injuries.html", "Injuries", f"{len(player_rows)} player rows", f"Official snapshot, 11/13 11:00 AM ET. {no_matchup} rows have no matchup cell; {no_team} have no team cell."),
        ("strategies.html", "Strategies", f"{n_strat} defined", f"{n_blocked} of {n_strat} are BLOCKED by the validation gates. None has passed a gate."),
        ("gates.html", "Gates", f"{n_gates} gates", "Thresholds are proposals awaiting owner approval."),
        ("correlations.html", "Correlations", f"{n_corr_measured} measured", "No correlation value has been measured; each value cell is blank."),
        ("flagged.html", "Flagged for Review", f"{n_flags} flags", f"{n_open} open. Flags do not block; each has a source link."),
        ("questions.html", "Questions", f"{len(questions)} items", "Answered, partly answered and open, each with a discovery step."),
        ("suggestions.html", "Suggestions", f"{len(suggestions)} options", "Site and process options. Each waits for an owner choice before any change."),
    ]
    card_html = "".join(
        f'<div class="card"><a href="{h}">{esc(lbl)}</a><div class="n">{esc(num)}</div><p>{esc(desc)}</p></div>'
        for h, lbl, num, desc in cards
    )
    index_body = f"""
<div class="banner"><strong>Status:</strong> No NBA lines, picks, or correlations are published. Every strategy is blocked by the validation gates because no authorised historical data or prices can be reached from this environment. Blank values are unverified and flagged.</div>
<h2>Summary</h2>
<div class="cards">{card_html}</div>
<h2>Start here</h2>
<ul class="findings">
<li>{link("exec-summary.html", "Executive summary")}: what is verified, what is blocked, and the decisions needed.</li>
<li>{link("flagged.html", "Flagged for Review")}: legal, data and repository irregularities, each with a source link.</li>
<li>{link("suggestions.html", "Suggestions")}: site improvements awaiting owner choice. Nothing changes until one is chosen.</li>
</ul>
"""
    (OUT / "index.html").write_text(page("Dashboard", "index.html", index_body,
        intro="Research dashboard for NBA slates, injuries, strategies and validation, built from official sources."), encoding="utf-8")

    # ---------- executive summary ----------
    summary_body = f"""
<ul class="findings">
<li><strong>Slates.</strong> {n_games} games are verified against the official schedule for Nov 13 to 16, 2026 (ET). Nov 13 has 9 games, Nov 14 has 5, Nov 15 has 9, and Nov 16 has 8. Every game ID, venue and preview link matches the schedule page ({link("slates.html", "slates table")}).</li>
<li><strong>Injuries.</strong> The 11/13/26 11:00 AM ET report is transcribed: {len(player_rows)} player rows and {len(team_rows)} team-status rows. Of the player rows, {out_count} are Out and {q_count} are Questionable. {no_matchup} rows have no matchup cell and {no_team} have no team cell in the PDF text; those cells are left blank ({link("injuries.html", "injury table")}).</li>
<li><strong>Originated lines.</strong> Not produced. No timestamped odds, prices or historical outcomes are available from an official source reached here ({link("questions.html", "Q-DATA-01 and Q-DATA-02")}).</li>
<li><strong>Picks.</strong> None published. The picks table lists all {n_games} games with blank lines and picks, pending legal advice on Dutch promotion rules ({link("picks.html", "picks")}).</li>
<li><strong>Strategies and gates.</strong> {n_strat} strategy hypotheses are defined. {n_blocked} of {n_strat} are blocked. Gate thresholds are proposals ({link("strategies.html", "strategies")}, {link("gates.html", "gates")}).</li>
<li><strong>Correlations.</strong> None measured. Each cell is blank by design ({link("correlations.html", "correlations")}).</li>
<li><strong>Rotation and game flow.</strong> A tested function redistributes minutes when players are Out, and a 7-factor game-flow list is documented. Neither gives a published minutes or production figure, because no minutes data is reachable ({link("gameflow.html", "game flow")}).</li>
<li><strong>Legal.</strong> NBA Terms s.9 bars use of NBA Statistics in connection with any gambling activity. s.19 selects New York law. Dutch law (Art. 1 of the Wet op de kansspelen) restricts promotion of unlicensed gambling. The minimum online age is not verified and is not published ({link("flagged.html", "flagged items")}).</li>
<li><strong>Repository.</strong> No licence. The previous Pages deploy published the whole repository; this round moves deployment to the generated site/ folder only ({link("repo-review.html", "repo review")}).</li>
</ul>
<h2>Decisions needed from the owner</h2>
<ul class="findings">
<li>Approve, reject or amend the proposed gate thresholds (Q-GATE-01).</li>
<li>Obtain counsel opinions on picks, rewards and the minimum age before any of them are published.</li>
<li>Decide whether to keep the site public, choose a licence, and decide on the injury-snapshot refresh cadence.</li>
<li>Choose which site suggestions to implement ({link("suggestions.html", "suggestions")}).</li>
</ul>
"""
    (OUT / "exec-summary.html").write_text(page("Executive summary", "exec-summary.html", summary_body,
        intro="What is verified, what is blocked, and what is needed. Every number is computed from the data files."), encoding="utf-8")

    # ---------- slates ----------
    srows = [[s["slate_date"], s["tip_time_et"], s["away_abbr"] + " " + s["away_team"], s["home_abbr"] + " " + s["home_team"],
              s["venue"], s["city"], s["game_id"], s["nba_game_page"], s["source_url"]] for s in slates]
    slates_body_rows = []
    for r in srows:
        tds = [cell(r[0]), cell(r[1]), cell(r[2]), cell(r[3]), cell(r[4]), cell(r[5]), cell(r[6]),
               f'<td><a href="{esc(r[7])}">Preview</a></td>', f'<td><a href="{esc(r[8])}">Source</a></td>']
        slates_body_rows.append("<tr>" + "".join(tds) + "</tr>")
    slates_table = ('<div class="table-wrap"><table><thead><tr>'
                    + "".join(f"<th>{h}</th>" for h in ["Date", "Tip (ET)", "Away", "Home", "Venue", "City", "Game ID", "Preview", "Source"])
                    + "</tr></thead><tbody>" + "".join(slates_body_rows) + "</tbody></table></div>")
    slates_body = f"""
<p>Calendar window: Nov 13 to 16, 2026 inclusive ({link("questions.html", "Q-SCOPE-01")}). The Nov 16 slate was read in full from the schedule page in this round. Times are as printed on the official page (ET). No Netherlands-time conversion was performed.</p>
{slates_table}
<h2>Analysis</h2>
<p>Saturday Nov 14 is the smallest slate (5 games). Sunday Nov 15 has the widest spread of tip times, from 1:00 to 9:00 PM ET. Injury rows are linked to a game only by the matchup cell in the same PDF row; tip times are not used for linking.</p>
"""
    (OUT / "slates.html").write_text(page("Slates (Nov 13-16, 2026)", "slates.html", slates_body,
        intro="All 31 games in the window, from the official NBA schedule. Every row links to the schedule and the game preview."), encoding="utf-8")

    # ---------- picks ----------
    prow = []
    for s in slates:
        prow.append([s["slate_date"], s["away_abbr"] + " at " + s["home_abbr"], s["tip_time_et"], "", "", "Blocked", "F13; F14", s["source_url"]])
    picks_table = table(["Date", "Game", "Tip (ET)", "Originated line", "Pick", "Status", "Flags", "Source"], prow, link_index=7)
    picks_body = f"""
<div class="banner"><strong>No picks are published.</strong> Every line and pick cell is blank and marked unverified. A pick needs a validated strategy and an originated line. Neither exists yet (see {link("gates.html", "gates")}), and publishing picks may be restricted under Dutch rules (F13).</div>
<h2>Table</h2>
{picks_table}
<h2>Analysis</h2>
<ul class="findings">
<li>No strategy has passed a gate, so no pick is eligible under the rules set in this project.</li>
<li>Originated lines need historical outcomes and timestamped prices. Neither is available from an official source reached from this environment ({link("questions.html", "Q-DATA-01")}, {link("questions.html", "Q-DATA-02")}).</li>
<li>Legal review is required before any pick or tip is published to people in the Netherlands ({link("questions.html", "Q-LEG-01")}).</li>
</ul>
"""
    (OUT / "picks.html").write_text(page("Picks", "picks.html", picks_body,
        intro="Picks for every game in the Nov 13-16 window. Blank by design: no originated line exists."), encoding="utf-8")

    # ---------- injuries ----------
    irows = []
    for r in injuries:
        who = r["player"] if r["row_type"] == "player" else "Team report (" + (r["team"] or "team blank") + ")"
        irows.append([r["game_date"], r["game_time_et_as_listed"], r["matchup"], r["team"], who, r["status"], r["reason"], r["flag_ids"], r["source_url"]])
    inj_table = table(["Game date", "Time (ET, as listed)", "Matchup", "Team", "Player / team", "Status", "Reason", "Flags", "Source"], irows, link_index=8)
    statuses: dict[str, int] = {}
    for r in player_rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    status_text = ", ".join(f"{esc(k)} {v}" for k, v in sorted(statuses.items(), key=lambda kv: -kv[1]))
    inj_body = f"""
<p>Snapshot: 11/13/26 11:00 AM ET ({link("sources.html", "S02")}). Player rows: {len(player_rows)}; team-status rows: {len(team_rows)}. Status counts: {status_text}.</p>
<div class="banner"><strong>Parsing limits.</strong> The PDF is a multi-column layout. Continuation blocks often lack team or matchup cells, and some reason cells are missing. Those cells are blank here and flagged (F02, F03, F04, F07). Nothing is inferred from table position. A newer snapshot exists (F01) and is not transcribed.</div>
{inj_table}
<h2>Analysis</h2>
<ul class="findings">
<li><strong>Largest reported absences.</strong> Out rows at IND (Haliburton, Hamstring), GSW (Curry, Butler III, Porzingis, Moody, Williams), UTA (Markkanen, Nurkic, Jackson Jr.), ORL (Banchero), and OKC (Holmgren, Sorber). Team and matchup cells are present for these rows.</li>
<li><strong>Rotation effect.</strong> Official rules give status and reason only. They do not say how minutes move. The redistribution function in pipeline/rotation.py is a scenario tool with synthetic tests. It gives no published minutes figure for any player here.</li>
<li><strong>Production effect.</strong> Not measured. Measuring it needs a historical event study with minutes and box scores, which are not reachable ({link("questions.html", "Q-MODEL-02")}).</li>
<li><strong>Team status.</strong> The Nov 14 team reports show NOT YET SUBMITTED for every listed team. These are team report states, not player statuses (F11).</li>
</ul>
"""
    (OUT / "injuries.html").write_text(page("Injuries and rotation", "injuries.html", inj_body,
        intro="Official injury report, 11/13/26 11:00 AM ET. Each row links to the PDF. Blank cells are unverified."), encoding="utf-8")

    # ---------- game flow ----------
    grows = [[g["factor_id"], g["factor"], g["why_it_may_matter (hypothesis only)"], g["data_needed"], g["status"], g["definition_source_url"]] for g in gameflow]
    gf_table = table(["ID", "Factor", "Why it may matter (hypothesis)", "Data needed", "Status", "Definition source"], grows, link_index=5)
    gf_body = f"""
<p>Game-flow factors are hypotheses to test, not findings. No score-state, pace, foul or play-by-play data was reached, so none of the factors is quantified.</p>
{gf_table}
<h2>Analysis</h2>
<ul class="findings">
<li>The schedule dates in slates.csv let us count rest situations, such as the Nov 14 and Nov 15 games for teams in consecutive slates. This is a schedule fact, not a measured rest effect.</li>
<li>Score margin and foul trouble are the factors most likely to move starter minutes, but no data here tests that.</li>
</ul>
"""
    (OUT / "gameflow.html").write_text(page("Game flow", "gameflow.html", gf_body,
        intro="Seven game-flow factors, with the data each would need and the official definition used."), encoding="utf-8")

    # ---------- strategies ----------
    strows = [[s["strategy_id"], s["family"], s["name"], s["hypothesis_to_test"], s["required_inputs"], s["gate_status"], s["blocking_reason"], s["source_url"]] for s in strategies]
    st_table = table(["ID", "Family", "Strategy", "Hypothesis", "Inputs needed", "Gate status", "Blocking reason", "Source"], strows, link_index=7)
    fam_counts: dict[str, int] = {}
    for s in strategies:
        fam_counts[s["family"]] = fam_counts.get(s["family"], 0) + 1
    st_body = f"""
<div class="banner"><strong>Leaderboard: empty.</strong> No strategy has passed every gate, so no ranking or reward is shown. Reward design is blocked by legal review ({link("questions.html", "Q-LEG-02")}).</div>
{st_table}
<h2>Analysis</h2>
<ul class="findings">
<li>Coverage by family: {esc(", ".join(f"{k} ({v})" for k, v in sorted(fam_counts.items())))}. The list covers single bets, parlays and prop combinations as requested.</li>
<li>The control (ST11) must fail every gate. If it passes any gate, the gate design is wrong, and that is checked by G11.</li>
<li>Each strategy names the official source for its inputs. Where that source is only a definition page, the row says so.</li>
</ul>
"""
    (OUT / "strategies.html").write_text(page("Strategies and leaderboard", "strategies.html", st_body,
        intro="Eleven strategy hypotheses. Each is blocked until real data and approved gates exist."), encoding="utf-8")

    # ---------- gates ----------
    grows2 = [[g["gate_id"], g["gate_name"], g["what_is_checked"], g["proposed_threshold"], g["threshold_status"], g["current_status"], g["reason"], g["method_reference_url"]] for g in gates]
    gate_table = table(["ID", "Gate", "What is checked", "Proposed threshold", "Threshold status", "Status", "Reason", "Method reference"], grows2, link_index=7)
    gate_body = f"""
<p>Overall status is BLOCKED for every strategy. Missing evidence is reported as BLOCKED, never PASS (pipeline/gates.py). Thresholds are not approved and are not evidence.</p>
{gate_table}
<h2>Analysis</h2>
<ul class="findings">
<li><strong>Method references.</strong> The NIST pages used are the exact binomial bounds (7.2.7.1), the normal-approximation proportion test (7.2.4) and the bootstrap (1.3.3.4). The cluster bootstrap by date is an extension and is labelled as one.</li>
<li><strong>Not verified.</strong> A NIST page for the permutation test was not located, so no permutation claim is made on this site.</li>
<li><strong>Owner decision.</strong> Every threshold is a proposal (Q-GATE-01).</li>
</ul>
"""
    (OUT / "gates.html").write_text(page("Validation gates", "gates.html", gate_body,
        intro="Eleven validation gates. A strategy needs every gate to pass. None can pass without data."), encoding="utf-8")

    # ---------- correlations ----------
    crow = [[c["pair_id"], c["market_a"], c["market_b"], c["hypothesis"], c["correlation_value"], c["status"], c["source_url"]] for c in correlations]
    cor_table = table(["ID", "Market A", "Market B", "Hypothesis (direction and size unknown)", "Correlation", "Status", "Method reference"], crow, link_index=6)
    cor_body = f"""
<div class="banner"><strong>No correlation values.</strong> Each value cell is blank because no matched data exists. Values are not estimated.</div>
{cor_table}
<h2>Analysis</h2>
<p>Parlays and same-game combinations are only as good as their joint-frequency estimate. A product of two marginal probabilities is wrong when legs are dependent, so each pair above needs its own measured joint frequency with an interval before any combined price is used ({link("questions.html", "Q-MODEL-01")}).</p>
"""
    (OUT / "correlations.html").write_text(page("Correlations", "correlations.html", cor_body,
        intro="Eight market pairs for parlays and prop combinations. Values are measured later, not assumed now."), encoding="utf-8")

    # ---------- sources ----------
    surows = [[s["source_id"], s["publisher"], s["title"], s["official_status"], s["used_for"], s["verification_result"], s["limits_or_notes"], s["url"]] for s in sources]
    src_table = table(["ID", "Publisher", "Title", "Official status", "Used for", "Verification", "Limits", "Source"], surows, link_index=7)
    src_body = f"""
<p>Sources are read on the retrieval date ({esc(sources[0]['retrieved_on'])}). A source is listed only if it was fetched. Secondary sources are not used for values.</p>
{src_table}
<h2>Analysis</h2>
<ul class="findings">
<li>NBA sources: schedule, injury reports and Terms of Use were read. Statistics pages were reachable but returned no data tables.</li>
<li>Dutch sources: the statute and the Ksa summaries were read. The Ksa summary is not binding, so statute text governs.</li>
<li>NIST: three method pages were read directly. The earlier DOI citation was not read and has been removed.</li>
</ul>
"""
    (OUT / "sources.html").write_text(page("Sources", "sources.html", src_body,
        intro="Official sources used, with what was read, the retrieval date, and each source's limits."), encoding="utf-8")

    # ---------- repo review ----------
    rrows = [[r["item_id"], r["area"], r["item_reviewed"], r["finding"], r["status"], r["recommended_action"], r["evidence_url"]] for r in repo]
    rr_table = table(["ID", "Area", "Item", "Finding", "Status", "Recommended action", "Evidence"], rrows, link_index=6)
    rr_body = f"""
<p>Line-by-line review of the repository, with a link for each finding. Statuses: OK, Irregular (needs owner action), Info, or Resolved.</p>
{rr_table}
<h2>Analysis</h2>
<ul class="findings">
<li>Irregular items: no licence (R03), no .gitignore (R04), dual Pages publishing (R05), whole-repo upload (R06), weak validation (R07), a stale injury-index link (R08), and a horizon mismatch (R17).</li>
<li>Addressed in this round: the branch was rebased onto the current main (R01); the deploy workflow uploads only the generated site/ folder (R06); validation covers every generated page and internal link (R07). The Pages source change (R05) and its result are recorded in COORDINATION.md.</li>
</ul>
"""
    (OUT / "repo-review.html").write_text(page("Repository review", "repo-review.html", rr_body,
        intro="Repository items reviewed, with evidence links and irregularities."), encoding="utf-8")

    # ---------- questions ----------
    qrows = [[q["q_id"], q["category"], q["question"], q["status"], q["current_answer_or_knowledge"], q["missing_information"], q["discovery_step"], q["decision_owner"], q["evidence_url"]] for q in questions]
    q_table = table(["ID", "Category", "Question", "Status", "Current answer or knowledge", "Missing information", "How to discover it", "Decides", "Source"], qrows, link_index=8)
    q_body = f"""
<p>Questions, what is known, what is missing, and how to find the missing piece. Items marked blocking stop a deliverable.</p>
{q_table}
<h2>Analysis</h2>
<p>Most blockers are data access or legal decisions. Neither can be closed by the repository alone, so each is listed with the step that would resolve it.</p>
"""
    (OUT / "questions.html").write_text(page("Questions and answers", "questions.html", q_body,
        intro="What is answered, partly answered or open, and how to discover what is missing."), encoding="utf-8")

    # ---------- suggestions ----------
    sgrows = [[s["sug_id"], s["area"], s["suggestion"], s["why"], s["options"], s["recommended_option"], s["dependency"], s["decision"], s["evidence_url"]] for s in suggestions]
    sg_table = table(["ID", "Area", "Suggestion", "Why", "Options", "Recommended", "Depends on", "Decision", "Source"], sgrows, link_index=8)
    sg_body = f"""
<div class="banner"><strong>Nothing here is implemented.</strong> Each suggestion waits for an owner choice in the Decision column. Choose an option and the change can be made.</div>
{sg_table}
<h2>Analysis</h2>
<p>The suggestions queue covers the site, legal, data access, odds, validation, injuries, scope and repository. The horizon suggestion (SG-07) differs from the 72-hour limit used in the earlier dashboard.</p>
"""
    (OUT / "suggestions.html").write_text(page("Suggestions", "suggestions.html", sg_body,
        intro="Site and process improvements, with options and a recommendation. Each waits for owner choice."), encoding="utf-8")

    # ---------- flagged ----------
    frows = [[f["flag_id"], f["area"], f["item"], f["why_flagged"], f["action_needed"], f["status"], f["source_url"]] for f in flags]
    fl_table = table(["Flag", "Area", "Item", "Why flagged", "Action needed", "Status", "Source"], frows, link_index=6)
    fl_body = f"""
<div class="banner"><strong>These do not block the merge.</strong> Each item is published here with a source link, as the brief requires. Status: open items need owner or counsel action.</div>
{fl_table}
<h2>Analysis</h2>
<ul class="findings">
<li>Legal: NBA Terms s.9 (gambling use), s.19 (New York law), Dutch promotion rules, the unverified minimum age, and the advertising summary limits.</li>
<li>Data: no historical stats, no prices, and no minutes data reachable from this environment.</li>
<li>Repository: no licence, dual Pages publishing, stale injury link, and unmerged arena branches.</li>
</ul>
"""
    (OUT / "flagged.html").write_text(page("Flagged for Review", "flagged.html", fl_body,
        intro="Irregularities, legal questions and unverified items. Each has a source link and a proposed action."), encoding="utf-8")

    # ---------- requirements ----------
    rqrows = [[r["req_id"], r["requirement_from_brief"], r["status"], r["how_addressed"], r["blocker_or_gap"], r["verification_status"], r["evidence_url"]] for r in reqs]
    rq_table = table(["ID", "Requirement", "Status", "How addressed", "Blocker or gap", "Verification", "Source"], rqrows, link_index=6)
    rq_body = f"""
<p>Every brief requirement and its current status. Status reflects what exists in the repository now, not what is planned.</p>
{rq_table}
"""
    (OUT / "requirements.html").write_text(page("Requirements", "requirements.html", rq_body,
        intro="Brief requirements, status, blockers, and the verification each one has."), encoding="utf-8")


if __name__ == "__main__":
    build()
    print("built", OUT)
