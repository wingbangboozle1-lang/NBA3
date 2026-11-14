#!/usr/bin/env python3
"""Session 965fbd17: injury-report delta, official 11/14/26 05:15 AM ET (stored) vs 01:30 PM ET (raw).

Reads the verbatim raw text in data/app/official_injuries_2026-11-14_0130PM_raw.md and compares it with
the 05:15 AM snapshot data/app/official_injuries_2026-11-14_0515AM.json.

Attribution tiers (a row is never counted unless its identity is printed on the row):
  * "attributed"       : game date, matchup and team are all printed on the row (same rule as
                         scripts/injury_delta_0415am.py). Only these rows are counted as same/changed.
  * "matchup_no_date"  : matchup, team and player are printed, but the game-date cell is blank on the row.
                         Listed and compared, NOT counted in the headline summary.
  * "team_no_matchup"  : team and player are printed, matchup and game date are blank on the row (some
                         later tables of the 13:30 report). Compared, NOT counted in the headline summary.
  * "name_only"        : player printed, team and matchup blank on the row (the Cleveland-block rows of the
                         13:30 report). Listed with name-only matches; never counted, never assigned a team.
  * "unverified"       : anything else (fragments, blank rows).

Writes data/app/injury_delta_0130pm.json. Standard library only. Deterministic.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/app/official_injuries_2026-11-14_0130PM_raw.md"
STORED = ROOT / "data/app/official_injuries_2026-11-14_0515AM.json"
OUT = ROOT / "data/app/injury_delta_0130pm.json"

RAW_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
STORED_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"

STATUSES = {"Out", "Questionable", "Probable", "Available", "Doubtful"}
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MATCH_RE = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")
TIME_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")
TIME_BARE_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")
NYS = "NOT YET SUBMITTED"


def load_stored():
    d = json.loads(STORED.read_text(encoding="utf-8"))
    team_code = {}
    players = {}
    nys = {}
    for r in d["rows"]:
        if r.get("team_name") and r.get("team"):
            team_code[r["team_name"]] = r["team"]
        if r.get("is_team_not_submitted"):
            nys[(r["team"], r.get("game_date"))] = r
        elif r.get("player") and r.get("game_date") in ("11/14/2026", "2026-11-14"):
            players[(r["team"], r["player"])] = r
    return d, team_code, players, nys


def parse_raw(team_code):
    """Return list of record dicts, one per table row that holds a player or NYS marker."""
    recs = []
    section_no = 0
    for line_no, line in enumerate(RAW.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("**Injury Report:"):
            section_no += 1
            continue
        if not line.startswith("|"):
            continue
        if set(line.replace("|", "").strip()) <= {"-", " ", ""}:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] in ("Game Date",):
            continue
        if "Management" in cells:
            continue
        date = next((c for c in cells if DATE_RE.match(c)), "")
        matchup = next((c for c in cells if MATCH_RE.match(c)), "")
        time = next((c for c in cells if TIME_RE.match(c)), "")
        is_nys = NYS in cells
        if is_nys:
            before = cells[:cells.index(NYS)]
            names = [c for c in before if c and not DATE_RE.match(c) and not MATCH_RE.match(c) and not TIME_RE.match(c)]
            team_name = names[-1] if names else ""
            recs.append({"line": line_no, "section": section_no, "game_date": date, "matchup": matchup,
                         "time": time, "team_name": team_name, "team": team_code.get(team_name, ""),
                         "player": "", "status": NYS, "reason": "", "nys": True})
            continue
        si = next((i for i, c in enumerate(cells) if c in STATUSES), None)
        if si is None or si < 2:
            if any(NYS in c for c in cells) or any(c.startswith("Milwaukee") or "@" in c and " " in c for c in cells):
                # e.g. the garbled 09:00 (ET) row: two NOT YET SUBMITTED markers in one cell, two team
                # names in another. Kept and listed; never attributed.
                recs.append({"line": line_no, "section": section_no, "game_date": date, "matchup": "",
                             "time": time, "team_name": "", "team": "", "player": "", "status": "",
                             "reason": "", "nys": False, "fragment": True, "raw_cells": cells})
            continue
        status = cells[si]
        player = cells[si - 1]
        team_name = cells[si - 2]
        if team_name in (DATE_RE.pattern, "") or DATE_RE.match(team_name) or MATCH_RE.match(team_name) or TIME_RE.match(team_name):
            team_name = ""
        reason = cells[si + 1] if si + 1 < len(cells) else ""
        recs.append({"line": line_no, "section": section_no, "game_date": date, "matchup": matchup,
                     "time": time, "team_name": team_name, "team": team_code.get(team_name, ""),
                     "player": player, "status": status, "reason": reason, "nys": False})
    return recs


def tier(r):
    if r.get("fragment"):
        return "unattributed_fragment"
    if r["nys"]:
        return "nys_attributed" if (r["team"] and r["matchup"] and r["game_date"]) else "nys_partial"
    if r["player"] and r["team"] and r["matchup"] and r["game_date"]:
        return "attributed"
    if r["player"] and r["team"] and r["matchup"]:
        return "matchup_no_date"
    if r["player"] and r["team"]:
        return "team_no_matchup"
    if r["player"]:
        return "name_only"
    return "unverified"


def main():
    stored, team_code, s_players, s_nys = load_stored()
    recs = parse_raw(team_code)
    for r in recs:
        r["tier"] = tier(r)

    comparisons, name_only = [], []
    seen = set()
    fragments = []
    for r in recs:
        if r["tier"] == "unattributed_fragment":
            fragments.append({"raw_line": r["line"], "section": r["section"], "cells": r["raw_cells"],
                              "result": "unattributed_fragment_not_counted"})
            continue
        if r["tier"] in ("nys_attributed", "nys_partial"):
            raw_date = r["game_date"]
            iso = "/".join([raw_date[6:], raw_date[:2], raw_date[3:5]]) if raw_date else ""
            s = None
            for gd in ("11/14/2026", "11/15/2026", "11/16/2026", "11/17/2026"):
                if (r["team"], gd) in s_nys and (not raw_date or raw_date == gd):
                    s = s_nys[(r["team"], gd)]
                    break
            comparisons.append({"tier": r["tier"], "team": r["team"], "team_name": r["team_name"],
                                "game_date": r["game_date"] or None, "matchup": r["matchup"] or None,
                                "time": r["time"] or None, "player": None, "raw_status": NYS, "raw_reason": "",
                                "stored_status": NYS if s else "(team not in 05:15 stored rows)",
                                "result": ("same" if s else "new_game_row") if r["tier"] == "nys_attributed" else
                                          ("same_not_counted" if s else "new_game_row_not_counted"),
                                "raw_line": r["line"]})
            continue
        if r["tier"] in ("attributed", "matchup_no_date", "team_no_matchup"):
            key = (r["team"], r["player"])
            seen.add(key)
            s = s_players.get(key)
            if s is None:
                result, s_status, s_reason = "new_in_raw", "", ""
            else:
                s_status, s_reason = s["status"], s["reason"]
                if s_status == r["status"] and s_reason == r["reason"]:
                    result = "same"
                elif s_status != r["status"]:
                    result = "status_changed"
                else:
                    result = "reason_changed"
            comparisons.append({"tier": r["tier"], "team": r["team"], "team_name": r["team_name"],
                                "game_date": r["game_date"] or None, "matchup": r["matchup"] or None,
                                "time": r["time"] or None, "player": r["player"],
                                "raw_status": r["status"], "raw_reason": r["reason"],
                                "stored_status": s_status, "stored_reason": s_reason,
                                "result": result, "raw_line": r["line"]})
        elif r["tier"] == "name_only":
            matches = [v for k, v in s_players.items() if k[1] == r["player"]]
            name_only.append({"player": r["player"], "raw_status": r["status"], "raw_reason": r["reason"],
                              "raw_line": r["line"], "section": r["section"],
                              "stored_matches_by_name": [{"team": m["team"], "status": m["status"],
                                                          "reason": m["reason"]} for m in matches],
                              "result": "name_only_not_counted"})

    missing_in_raw = [{"team": k[0], "player": k[1], "stored_status": v["status"], "stored_reason": v["reason"],
                       "result": "not_in_13_30_attributed_rows"}
                      for k, v in s_players.items() if k not in seen]

    counted = [c for c in comparisons if c["tier"] in ("attributed", "nys_attributed")]
    counts_counted = {}
    for c in counted + [m for m in missing_in_raw]:
        counts_counted[c["result"]] = counts_counted.get(c["result"], 0) + 1
    tiers = {}
    for r in recs:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1

    out = {
        "title": "Injury report delta: 11/14/26 05:15 AM ET (stored) vs 11/14/26 01:30 PM ET (official, newest listed)",
        "session": "965fbd17",
        "raw_source_url": RAW_URL,
        "raw_source_file": str(RAW.relative_to(ROOT)),
        "stored_snapshot_file": str(STORED.relative_to(ROOT)),
        "stored_snapshot_source_url": STORED_URL,
        "index_url": INDEX_URL,
        "retrieved_on": "2026-11-14",
        "rule": ("Counted only where the row prints game date, matchup and team (same rule as the 04:15 AM delta). "
                 "Rows that print matchup and team but no game date are listed as matchup_no_date and not counted. "
                 "Rows that print a player but no team or matchup are listed as name_only, with name-only matches, "
                 "and never assigned a team."),
        "summary": {
            "raw_table_rows_parsed": len(recs),
            "tiers": dict(sorted(tiers.items())),
            "stored_11_14_player_rows": len(s_players),
            "stored_11_14_nys_rows": len(s_nys),
            "counted_attributed_result_counts": dict(sorted(counts_counted.items())),
            "name_only_rows_not_counted": len(name_only),
            "unattributed_fragments_not_counted": len(fragments),
        },
        "comparisons": comparisons,
        "missing_in_raw": missing_in_raw,
        "name_only_not_counted": name_only,
        "unattributed_fragments": fragments,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
