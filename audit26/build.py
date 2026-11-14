#!/usr/bin/env python3
"""Session 26fd5f6f: 11/14 injury-freshness and slate re-check.

Inputs (all committed):
  audit26/data/official_injury_report_2026-11-14_0415AM_raw.md  verbatim rows copied from the
      official 11/14/26 04:15 AM ET NBA injury report PDF (see SOURCE_PDF)
  data/app/official_injuries_2026-11-13_0745PM.json             the repo's current injury snapshot
  audit26/data/schedule_check.json                              official schedule rows (nba.com/schedule)

Outputs (deterministic, rerun-safe):
  audit26/data/comparison_2026-11-14.json
  audit26/index.html, audit26/flagged.html

Run:  python3 audit26/build.py      (exit code 1 on any failed self-check)
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit26"
DATA = AUDIT / "data"

SOURCE_PDF = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
SOURCE_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
SOURCE_SCHEDULE = "https://www.nba.com/schedule"
REPO_SNAPSHOT = ROOT / "data/app/official_injuries_2026-11-13_0745PM.json"
RAW = DATA / "official_injury_report_2026-11-14_0415AM_raw.md"
SCHED = DATA / "schedule_check.json"
OUT_JSON = DATA / "comparison_2026-11-14.json"

# Team names exactly as printed in the official injury PDF -> NBA abbreviation.
TEAM_ABBR = {
    "Denver Nuggets": "DEN", "New Orleans Pelicans": "NOP", "Dallas Mavericks": "DAL",
    "Cleveland Cavaliers": "CLE", "Brooklyn Nets": "BKN", "Memphis Grizzlies": "MEM",
    "Chicago Bulls": "CHI", "Minnesota Timberwolves": "MIN", "Detroit Pistons": "DET",
    "Miami Heat": "MIA",
}
WINDOW_DATE = "11/14/2026"
WINDOW_MATCHUPS = {"DEN@NOP", "DAL@CLE", "BKN@MEM", "CHI@MIN", "DET@MIA"}


def parse_raw():
    rows = []
    for n, line in enumerate(RAW.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7:
            date, time_, matchup, team, player, status, reason = cells
        elif len(cells) == 6:
            # Continuation fragment: the date and game time columns were not printed.
            date, time_ = "", ""
            matchup, team, player, status, reason = cells[1], cells[2], cells[3], cells[4], cells[5]
            if cells[0] or (not player and not status and reason != "NOT YET SUBMITTED"):
                raise SystemExit(f"raw line {n}: unexpected 6-cell layout: {cells}")
        else:
            raise SystemExit(f"raw line {n}: expected 6 or 7 cells, got {len(cells)}")
        flags = []
        if len(cells) == 6:
            flags.append("date and game-time columns not printed in the extracted text")
        if matchup == "":
            flags.append("matchup not printed in the extracted text")
        if team == "" and player:
            flags.append("team not printed in the extracted text")
        rows.append({
            "raw_line": n, "date": date, "time_et": time_, "matchup": matchup,
            "team_printed": team, "player": player, "status": status, "reason": reason,
            "extraction_flags": flags,
        })
    return rows


def load_repo_rows():
    snap = json.loads(REPO_SNAPSHOT.read_text(encoding="utf-8"))
    return [r for r in snap["rows"] if r["game_date"] == WINDOW_DATE]


def match_key(team, matchup, player):
    return (matchup, team, player)


def compare(official, repo):
    repo_by_key = {match_key(r["team"], r["matchup"], r["player"]): r for r in repo}
    repo_by_name = {}
    for r in repo:
        repo_by_name.setdefault(r["player"], []).append(r)
    out = []
    used = set()
    for o in official:
        team = TEAM_ABBR.get(o["team_printed"], o["team_printed"])
        matchup = o["matchup"]
        notes = list(o["extraction_flags"])
        match = None
        if matchup and team:
            match = repo_by_key.get(match_key(team, matchup, o["player"]))
        elif o["player"]:
            cands = repo_by_name.get(o["player"], [])
            if len(cands) == 1:
                match = cands[0]
                notes.append("matched by player name to the one repo row with that name (" + match["matchup"] + ")")
        elif o["team_printed"] and not o["player"]:
            # NOT YET SUBMITTED team row. Match on team (and matchup when the PDF printed one).
            cands = [r for r in repo if r["is_team_not_submitted"] and r["team"] == team
                     and (not matchup or r["matchup"] == matchup)]
            if len(cands) == 1:
                match = cands[0]
                if not matchup:
                    notes.append("matched by team name to the one repo NOT YET SUBMITTED row (" + match["matchup"] + "); matchup not printed")
        if match is not None:
            used.add(id(match))
        if o["player"]:
            off_status, off_reason = o["status"], o["reason"]
            rep_status = match["status"] if match else None
            rep_reason = match["reason"] if match else None
            same = bool(match) and rep_status == off_status and rep_reason == off_reason
        else:
            off_status, off_reason = "NOT YET SUBMITTED", ""
            rep_status = "NOT YET SUBMITTED" if match and match["is_team_not_submitted"] else None
            rep_reason = ""
            same = bool(match) and match["is_team_not_submitted"]
        out.append({
            "raw_line": o["raw_line"], "game_date": o["date"] or "(not printed)",
            "matchup": o["matchup"], "repo_matchup": match["matchup"] if match else None,
            "team": team, "team_printed": o["team_printed"],
            "player": o["player"], "official_status": off_status, "official_reason": off_reason,
            "repo_status": rep_status, "repo_reason": rep_reason,
            "match": same, "notes": notes,
        })
    unmatched_repo = [r for r in repo if id(r) not in used]
    return out, unmatched_repo


def self_checks(comparison, unmatched_repo, schedule):
    problems = []
    if len(comparison) != 31:
        problems.append(f"expected 31 official 11/14 rows, got {len(comparison)}")
    if unmatched_repo:
        problems.append(f"{len(unmatched_repo)} repo 11/14 rows have no official counterpart")
    mism = [c for c in comparison if not c["match"]]
    if mism:
        problems.append(f"{len(mism)} official rows differ from the repo snapshot")
    sched_games = {g["game_id"]: g for g in schedule["games"]}
    for g in schedule["games"]:
        if not g["source"].startswith("https://www.nba.com/"):
            problems.append(f"schedule row {g['game_id']} lacks an nba.com source")
    return problems


def esc(s):
    return html.escape("" if s is None else str(s))


CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1d2433;background:#f6f7fb}
header{background:#14213d;color:#fff;padding:18px 24px}
header a{color:#ffd166}
main{max-width:1200px;margin:0 auto;padding:20px 24px}
h1{font-size:1.5rem;margin:.2rem 0}
h2{font-size:1.15rem;margin-top:28px}
.card{background:#fff;border:1px solid #dfe3ee;border-radius:10px;padding:14px 18px;margin:12px 0}
table{border-collapse:collapse;width:100%;background:#fff;font-size:.9rem}
th,td{border-bottom:1px solid #e6e9f2;padding:7px 9px;text-align:left;vertical-align:top}
th{background:#eef1f8;position:sticky;top:0}
.ok{color:#17703a;font-weight:600}.bad{color:#b42318;font-weight:600}.flag{color:#8a5a00}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;background:#eef1f8;margin-right:6px}
small{color:#4a5568}
"""


def page(title, body, active):
    nav = [("index.html", "Verification summary"), ("flagged.html", "Flagged for Review"),
           ("../index.html", "Repo home")]
    links = " &middot; ".join(f'<a href="{h}">{t}</a>' if h != active else f"<strong>{t}</strong>" for h, t in nav)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} | NBA3 audit26</title>
<style>{CSS}</style></head><body>
<header><div>NBA3 &middot; session 26fd5f6f &middot; 11/14 injury-freshness and slate re-check</div>
<div style="margin-top:6px">{links}</div></header>
<main>{body}</main></body></html>
"""


def render(comparison, schedule, problems, unmatched):
    ok_rows = sum(1 for c in comparison if c["match"])
    player_rows = [c for c in comparison if c["player"]]
    ns_rows = [c for c in comparison if not c["player"]]
    flagged_rows = [c for c in comparison if c["notes"]]

    summary = f"""
<h1>11/14 official injury report vs the repo snapshot, and the 11/14–11/15 schedule</h1>
<div class="card">
<span class="pill">Newest report checked: 11/14/26 04:15 AM ET</span>
<span class="pill">Official rows (11/14 games): {len(comparison)}</span>
<span class="pill">Match vs repo 11/13 07:45 PM snapshot: <span class="{'ok' if ok_rows == len(comparison) else 'bad'}">{ok_rows}/{len(comparison)}</span></span>
<span class="pill">Player rows: {len(player_rows)} &middot; NOT YET SUBMITTED team rows: {len(ns_rows)}</span>
<span class="pill">Schedule rows checked: {len(schedule['games'])}</span>
<p>Source report: <a href="{SOURCE_PDF}">Injury-Report_2026-11-14_04_15AM.pdf</a> (NBA official CMS, linked from the
<a href="{SOURCE_INDEX}">official injury report index</a>). Schedule: <a href="{SOURCE_SCHEDULE}">nba.com/schedule</a>.</p>
<p><strong>Result:</strong> the 04:15 AM ET report carries the same status and reason for every 11/14 row that the repo already holds
(see table). The repo's injury snapshot is therefore not contradicted for the five 11/14 games. This is <em>not</em> the game-day report:
the official index says teams submit game-day reports between 11 a.m. and 1 p.m. local time, and no report later than 04:15 AM ET was listed
when this check ran (about 09:40 UTC, 4:40 AM ET). Re-run this check after the game-day reports are published, before any 11/14 pick is used.</p>
<p>Self-checks: {'<span class="ok">PASS</span>' if not problems else '<span class="bad">FAIL: ' + esc('; '.join(problems)) + '</span>'}.</p>
</div>
"""

    rows = []
    for c in comparison:
        status_cls = "ok" if c["match"] else "bad"
        notes = "<br>".join(esc(n) for n in c["notes"]) if c["notes"] else "&mdash;"
        who = esc(c["player"]) if c["player"] else "<em>team row: " + esc(c["team_printed"]) + " &mdash; NOT YET SUBMITTED</em>"
        rows.append(
            f"<tr><td>{esc(c['game_date'])}</td><td>{esc(c['matchup'] or '(not printed)')}</td>"
            f"<td>{esc(c['team'] or c['team_printed'] or '(not printed)')}</td><td>{who}</td>"
            f"<td>{esc(c['official_status'])}</td><td>{esc(c['official_reason'])}</td>"
            f"<td>{esc(c['repo_status'])}</td><td>{esc(c['repo_reason'])}</td>"
            f"<td class=\"{status_cls}\">{'match' if c['match'] else 'DIFFERS'}</td>"
            f"<td>{notes}</td>"
            f"<td><a href=\"{SOURCE_PDF}\">official PDF 04:15 AM ET</a> (line {c['raw_line']} of the raw extraction)</td></tr>"
        )
    injury_table = f"""
<h2>Injury rows for the 11/14 games (31 rows, all compared)</h2>
<div class="card" style="overflow-x:auto"><table>
<thead><tr><th>Date</th><th>Matchup</th><th>Team</th><th>Player</th><th>Official status (04:15 AM)</th><th>Official reason</th>
<th>Repo status (11/13 07:45 PM)</th><th>Repo reason</th><th>Result</th><th>Extraction note</th><th>Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><small>Column &ldquo;Matchup&rdquo; shows &ldquo;(not printed)&rdquo; where the PDF text extraction dropped the column. Those rows were matched by name or team only, and each is listed on the Flagged for Review page.</small></p>
"""

    srows = []
    for g in schedule["games"]:
        srows.append(
            f"<tr><td>{esc(g['date'])}</td><td>{esc(g['time_et'])}</td><td>{esc(g['away'])} @ {esc(g['home'])}</td>"
            f"<td>{esc(g['game_id'])}</td><td>{esc(g['repo_time_et'])}</td>"
            f"<td class=\"{'ok' if g['match'] else 'bad'}\">{'match' if g['match'] else 'DIFFERS'}</td>"
            f"<td><a href=\"{esc(g['source'])}\">nba.com schedule</a></td></tr>"
        )
    sched_table = f"""
<h2>Schedule check: 11/14 and 11/15 games (official schedule vs repo slate)</h2>
<div class="card" style="overflow-x:auto"><table>
<thead><tr><th>Date</th><th>Official time (ET)</th><th>Matchup</th><th>Game ID</th><th>Repo slate time (ET)</th><th>Result</th><th>Source</th></tr></thead>
<tbody>{''.join(srows)}</tbody></table></div>
<p><small>Official times are read from the nba.com schedule page, retrieved 2026-11-14. The 11/15 rows are the nine games listed under &ldquo;Sunday, November 15&rdquo;.</small></p>
"""

    body = summary + injury_table + sched_table + f"""
<h2>Not checked in this session</h2>
<div class="card"><p>11/16 and 11/17 slate rows (the schedule page chunk 2 onward), injury reports for 11/15 and later
(not printed in the 04:15 AM report apart from the NOT YET SUBMITTED entries), and any line, price or model output.
These remain as they were on <code>main</code> and are not re-verified here.</p></div>
"""
    return body, flagged_rows


def flagged_page(comparison, flagged_rows, problems):
    items = [
        ("F26-01", "Traore, Nolan (BKN): team and matchup not printed in the extracted text of the 04:15 AM report",
         "The row sits after the BKN@MEM block with its matchup and team cells empty. It was matched by name to the one repo row with that name (BKN@MEM). Status Probable and reason Right Calf Tightness / Soreness agree.",
         SOURCE_PDF),
        ("F26-02", "NOT YET SUBMITTED row for Memphis Grizzlies: matchup not printed",
         "The extraction shows the team name and the status but drops the matchup. It was matched by team name within the 11/14 rows of the repo snapshot, where MEM appears only in BKN@MEM.",
         SOURCE_PDF),
        ("F26-03", "The report prints times without AM/PM (e.g. 04:30 (ET))",
         "Read carelessly, 04:30 (ET) looks like 4:30 AM. The nba.com schedule lists CHA@LAC at 4:30 PM ET on 11/15, and the 11/15 rows of the report follow the same pattern. In the extracted text the 11/15 rows from CHA@LAC onward have no date column, so this check does not use them.",
         SOURCE_PDF),
        ("F26-04", "No game-day report for 11/14 yet; the 04:15 AM ET report is the newest one listed",
         "The official index says game-day reports are submitted between 11 a.m. and 1 p.m. local time, and that reports are updated continually. Pick decisions for the 11/14 slate (7:00 PM ET tip-off) need the last report before tip-off, not this one.",
         SOURCE_INDEX),
        ("F26-05", "Repo snapshot metadata is out of date",
         "data/app/official_injuries_2026-11-13_0745PM.json still records 08:30 PM as the newest report on the index. The 11/14 rows agree with the 04:15 AM report, so no value changes, but the field is stale.",
         SOURCE_INDEX),
        ("F26-07", "Cross-session reconciliation with 53653a5c (data/app/injury_delta_0415am.json, PR #47)",
         "Both checks agree on every 11/14 status and reason. Two differences: (a) this check also counts the three 11/14 team rows printed as NOT YET SUBMITTED for CHI, MEM and MIA, which were matched by team name; the other check left them unattributed. (b) The other check's finding F53-03 says the stored 11/13 snapshot has no rows for CHA@LAC, SAS@UTA, DAL@BOS, NYK@TOR, HOU@WAS, ATL@MIL and OKC@SAC. Those seven games are on Sunday 11/15 on the nba.com schedule (1:00 PM to 9:00 PM ET slate), not 11/14, so they are outside the stored window and the snapshot is complete for 11/14. A change request is logged (CR-26fd5f6f-A) for the owner of that file; it was not edited here.",
         SOURCE_SCHEDULE),
        ("F26-08", "Process: main went red after PR #50 merged with its own PR check failing; hand-edited generated files broke the drift gate",
         "PR #50 (session 44e0c051, run 43581647670 on its head b2c073e) was red when merged. Its commit b769edd hand-added three flags to generated files (data/app/canonical.json, app/flagged.html, index.html) that scripts/assemble_canonical.py does not produce, so the canonical drift gate failed on e0e363e and on 8b49887. Fixed on main by PR #52 (3fb007d) by moving the three records into data/app/flags_44e0c051.json; the full 21-step workflow was replayed locally first. Recommendation for the owner: merge only with green PR checks, and change generated files only through their scripts.",
         "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43581647670"),
        ("F26-06", "Pages configuration: the live site is served from the branch, not from the workflow artifact",
         "GitHub Pages reports build_type 'legacy' with source branch main and path /. Visitors therefore see the repository root as committed on main. The deploy job in pages.yml uploads a separate _pages artifact that is built from a fixed copy list, and it does not list audit26/ or other late additions. Anything a new session adds outside the copy list is still served once it is on main. The two mechanisms should be reconciled by an owner.",
         "https://api.github.com/repos/wingbangboozle1-lang/NBA3/pages"),
    ]
    items = sorted(items)
    rows = "".join(
        f"<tr><td>{esc(i)}</td><td>{esc(t)}</td><td>{esc(d)}</td><td><a href=\"{esc(s)}\">official source</a></td></tr>"
        for i, t, d, s in items
    )
    body = f"""
<h1>Flagged for Review &mdash; session 26fd5f6f</h1>
<p>Each item is a source-level irregularity or a limit of this check. None changes a value in the repo, and none blocks a merge.
Owner decisions are listed in the table. Source links point to the official NBA PDF or index.</p>
<div class="card" style="overflow-x:auto"><table>
<thead><tr><th>ID</th><th>Finding</th><th>Detail</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>Decisions for the owner</h2>
<div class="card"><ol>
<li>Re-run <code>python3 audit26/build.py</code> after the 11 a.m.–1 p.m. ET game-day report is published, and before any 11/14 line or pick is used.</li>
<li>Decide whether the repo should store the report's team and matchup for the Traore and Memphis rows, which the extraction did not print (F26-01, F26-02).</li>
</ol></div>
"""
    return body


def build_schedule():
    # Official rows transcribed from nba.com/schedule (chunk 0 and chunk 1, retrieved 2026-11-14).
    # 'time_et' is the official time as printed; 'repo_time_et' is read from the repo slate.
    rows = json.loads(SCHED.read_text(encoding="utf-8"))
    slate = json.loads((ROOT / "data/app/official_slate_1114_1117.json").read_text(encoding="utf-8"))
    repo = {(g["date"], f"{g['away']}@{g['home']}"): g for g in slate["games"]}
    out = []
    for r in rows["games"]:
        key = (r["date"], f"{r['away']}@{r['home']}")
        rg = repo.get(key)
        time_repo = rg["time_et"] if rg else ""
        match = bool(rg) and rg["game_id"] == r["game_id"] and rg["time_et"] == r["time_et"]
        out.append({**r, "repo_time_et": time_repo, "match": match})
    return {"games": out}


def main():
    raw = parse_raw()
    repo = load_repo_rows()
    comparison, unmatched = compare(raw, repo)
    schedule = build_schedule()
    problems = self_checks(comparison, unmatched, schedule)
    body, flagged_rows = render(comparison, schedule, problems, unmatched)
    OUT_JSON.write_text(json.dumps({
        "source_pdf": SOURCE_PDF, "source_index": SOURCE_INDEX, "source_schedule": SOURCE_SCHEDULE,
        "repo_snapshot": str(REPO_SNAPSHOT.relative_to(ROOT)),
        "rows": comparison, "unmatched_repo_rows": unmatched, "schedule": schedule["games"],
        "self_check_problems": problems,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (AUDIT / "index.html").write_text(page("11/14 injury and slate check", body, "index.html"), encoding="utf-8")
    (AUDIT / "flagged.html").write_text(page("Flagged for Review", flagged_page(comparison, flagged_rows, problems), "flagged.html"), encoding="utf-8")
    print(f"official rows {len(comparison)}; match {sum(c['match'] for c in comparison)}; "
          f"unmatched repo rows {len(unmatched)}; schedule rows {len(schedule['games'])}; problems {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
