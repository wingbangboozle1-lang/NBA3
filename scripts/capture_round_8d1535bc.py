#!/usr/bin/env python3
"""Parse two verbatim official NBA injury-report transcripts and diff them (session arena/8d1535bc-nba3, U1).

Inputs (committed verbatim transcriptions, no network):
  data/app/official_injuries_2026-11-15_0615AM_raw.md   (official PDF 11/15/26 06:15 AM ET)
  data/app/official_injuries_2026-11-15_0615PM_raw.md   (official PDF 11/15/26 06:15 PM ET)

Outputs:
  data/app/official_injuries_2026-11-15_0615PM.json      parsed rows of the 06:15 PM report
  data/app/injury_diff_0615AM_to_0615PM.json             status / reason / presence changes

Attribution rule: the PDF's merged cells leave Team and Matchup blank on continuation rows. A blank
Team/Matchup is filled from the previous row ONLY for the record's `team_attribution` field, which is
set to "carried_forward" so it can be audited. A player is compared across reports by exact printed
name; a name that appears more than once in one report is reported as ambiguous and not diffed.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AM = os.path.join(ROOT, "data/app/official_injuries_2026-11-15_0615AM_raw.md")
PM = os.path.join(ROOT, "data/app/official_injuries_2026-11-15_0615PM_raw.md")
OUT_PM = os.path.join(ROOT, "data/app/official_injuries_2026-11-15_0615PM.json")
OUT_DIFF = os.path.join(ROOT, "data/app/injury_diff_0615AM_to_0615PM.json")

STATUSES = {"Out", "Questionable", "Doubtful", "Probable", "Available"}
TEAMS = {
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls",
    "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", "Detroit Pistons",
    "Golden State Warriors", "Houston Rockets", "Indiana Pacers", "LA Clippers", "Los Angeles Lakers",
    "Memphis Grizzlies", "Miami Heat", "Milwaukee Bucks", "Minnesota Timberwolves",
    "New Orleans Pelicans", "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
    "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers", "Sacramento Kings",
    "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards",
}
MATCHUP = re.compile(r"^[A-Z]{2,4}@[A-Z]{2,4}$")
TIME = re.compile(r"^\d{2}:\d{2} \(ET\)$")
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
NOT_SUBMITTED = "NOT YET SUBMITTED"


def parse(path, label):
    """Return (records, unattributed_lines, header_stamps)."""
    records, unattributed, stamps = [], [], []
    team = matchup = gtime = None
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    line_no = 0
    for raw in lines:
        line_no += 1
        m = re.match(r"^\*\*Injury Report: (.+?)\*\*$", raw)
        if m:
            stamps.append(m.group(1))
            team = matchup = gtime = None  # a new page restarts the merged-cell context
            continue
        if not raw.startswith("|") or re.match(r"^\|\s*-", raw):
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if cells and cells[0] == "Game Date":
            continue
        si = next((i for i, c in enumerate(cells) if c in STATUSES or c == NOT_SUBMITTED), None)
        if si is None:
            unattributed.append({"line": line_no, "text": raw})
            continue
        # matchup / time / date / team columns come before the player cell
        row_team = next((c for c in cells[:si] if c in TEAMS), None)
        row_matchup = next((c for c in cells[:si] if MATCHUP.match(c)), None)
        row_time = next((c for c in cells[:si] if TIME.match(c)), None)
        if row_matchup:
            matchup = row_matchup
        if row_time:
            gtime = row_time
        explicit_team = row_team is not None
        if row_team:
            team = row_team
        # the player cell is the one just before the status, or the first 'Last, First' cell
        if si == 0:
            name = None
        else:
            name = cells[si - 1] if ", " in cells[si - 1] else next(
                (c for c in cells[:si] if ", " in c and c not in TEAMS), None)
        if cells[si] == NOT_SUBMITTED:
            records.append({
                "report": label, "line": line_no, "kind": "not_submitted",
                "team": team if row_team is None else row_team,
                "team_attribution": "explicit" if explicit_team else "carried_forward",
                "matchup": matchup, "game_time": gtime, "player": None,
                "status": None, "reason": NOT_SUBMITTED,
            })
            continue
        status = cells[si]
        # the 06:15 AM transcript carries a stray "<!-- CHUNK 1 -->" token inside one reason cell
        # (a copy artefact of an earlier session's capture, flagged); strip it for comparison only.
        cells = [re.sub(r"<!--.*?-->", "", c).strip() for c in cells]
        reason = " | ".join(c for c in cells[si + 1:] if c) or None
        if name is None:
            unattributed.append({"line": line_no, "text": raw})
            continue
        records.append({
            "report": label, "line": line_no, "kind": "player",
            "team": team, "team_attribution": "explicit" if explicit_team else "carried_forward",
            "matchup": matchup, "game_time": gtime, "player": name,
            "status": status, "reason": reason,
        })
    return records, unattributed, stamps


def by_player(records):
    counts = {}
    for r in records:
        if r["kind"] == "player":
            counts[r["player"]] = counts.get(r["player"], 0) + 1
    return counts


def diff(am, pm):
    am_counts, pm_counts = by_player(am), by_player(pm)
    am_map = {r["player"]: r for r in am if r["kind"] == "player" and am_counts[r["player"]] == 1}
    pm_map = {r["player"]: r for r in pm if r["kind"] == "player" and pm_counts[r["player"]] == 1}
    ambiguous = sorted({p for p, n in list(am_counts.items()) + list(pm_counts.items()) if n > 1})
    changes = {"status": [], "reason": [], "added": [], "removed": []}
    for name in sorted(set(am_map) | set(pm_map)):
        a, p = am_map.get(name), pm_map.get(name)
        if a and not p:
            changes["removed"].append({"player": name, "team": a["team"], "am_status": a["status"], "am_reason": a["reason"]})
        elif p and not a:
            changes["added"].append({"player": name, "team": p["team"], "pm_status": p["status"], "pm_reason": p["reason"]})
        else:
            if a["status"] != p["status"]:
                changes["status"].append({"player": name, "team": p["team"], "am_status": a["status"],
                                          "pm_status": p["status"], "pm_reason": p["reason"],
                                          "team_attribution": p["team_attribution"]})
            if a["reason"] != p["reason"]:
                changes["reason"].append({"player": name, "team": p["team"], "am_reason": a["reason"],
                                          "pm_reason": p["reason"]})
    return {"changes": changes, "ambiguous_names_not_diffed": ambiguous,
            "counts": {k: len(v) for k, v in changes.items()}}


def main():
    am, am_un, am_stamps = parse(AM, "06:15 AM ET")
    pm, pm_un, pm_stamps = parse(PM, "06:15 PM ET")
    summary = {
        "am_player_rows": sum(r["kind"] == "player" for r in am),
        "pm_player_rows": sum(r["kind"] == "player" for r in pm),
        "am_not_submitted": sum(r["kind"] == "not_submitted" for r in am),
        "pm_not_submitted": sum(r["kind"] == "not_submitted" for r in pm),
        "am_unattributed_lines": len(am_un),
        "pm_unattributed_lines": len(pm_un),
        "pm_carried_forward_team_rows": sum(r["team_attribution"] == "carried_forward" for r in pm),
    }
    out_pm = {
        "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15PM.pdf",
        "index_url": "https://official.nba.com/nba-injury-report-2026-27-season/",
        "report_stamp": "2026-11-15 06:15 PM ET",
        "transcript": "data/app/official_injuries_2026-11-15_0615PM_raw.md",
        "page_headers_seen": len(pm_stamps),
        "summary": summary,
        "rows": pm,
        "unattributed_lines": pm_un,
    }
    diff_out = {
        "from": "data/app/official_injuries_2026-11-15_0615AM_raw.md (06:15 AM ET)",
        "to": "data/app/official_injuries_2026-11-15_0615PM_raw.md (06:15 PM ET)",
        "summary": summary,
        **diff(am, pm),
        "rule": "Compared by exact printed player name; names printed more than once in a report are excluded and listed.",
    }
    with open(OUT_PM, "w", encoding="utf-8") as fh:
        json.dump(out_pm, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(OUT_DIFF, "w", encoding="utf-8") as fh:
        json.dump(diff_out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    json.dump(summary, sys.stdout, indent=2)
    print()
    print("changes:", diff_out["counts"])


if __name__ == "__main__":
    main()
