#!/usr/bin/env python3
"""Compare the transcribed 11/14/26 01:30 PM ET official injury report with the canonical snapshot.

Inputs : audit_736efb4b/data/official_injury_report_2026-11-14_0130PM.json   (capture.py)
         data/snapshots/canonical_2026-11-14.json -> injuries.rows (frozen
         snapshot as published on 2026-11-14, 04:15 AM ET report)
Output : audit_736efb4b/data/delta_1330PM_vs_canonical.json
Run    : python3 audit_736efb4b/compare.py

A player is matched across the two reports by player name only (the canonical rows carry a team on
most, but not all, player rows; the 1:30 PM report leaves the team blank on several rows).
Each outcome is recorded; nothing is inferred to make a row match.
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NEW = HERE / "data" / "official_injury_report_2026-11-14_0130PM.json"
# Frozen 2026-11-14 snapshot (see audit_736efb4b/build.py): this delta is defined
# against the artefact published that day, not against a later refresh.
CANON = ROOT / "data" / "snapshots" / "canonical_2026-11-14.json"
OUT = HERE / "data" / "delta_1330PM_vs_canonical.json"
NYS = "NOT YET SUBMITTED"


def main():
    new = json.loads(NEW.read_text(encoding="utf-8"))
    canon = json.loads(CANON.read_text(encoding="utf-8"))
    canon_rows = canon["injuries"]["rows"]
    canon_players = [r for r in canon_rows if r["player"]]
    canon_nys = [r for r in canon_rows if not r["player"]]
    new_players = [r for r in new["rows"] if r["row_kind"] == "player"]
    new_nys = [r for r in new["rows"] if r["row_kind"] == "not_yet_submitted"]

    by_name_canon = defaultdict(list)
    for r in canon_players:
        by_name_canon[r["player"]].append(r)
    by_name_new = defaultdict(list)
    for r in new_players:
        by_name_new[r["player"]].append(r)
    dup_canon = sorted(n for n, v in by_name_canon.items() if len(v) > 1)
    dup_new = sorted(n for n, v in by_name_new.items() if len(v) > 1)

    player_outcomes = []
    for r in new_players:
        matches = by_name_canon.get(r["player"], [])
        if not matches:
            outcome = "new_in_1330_report"
            prev = None
        else:
            prev = matches[0]
            if prev["status"] == r["status"] and prev["reason"] == r["reason"]:
                outcome = "unchanged"
            elif prev["status"] != r["status"]:
                outcome = "status_changed"
            else:
                outcome = "reason_changed_status_same"
        player_outcomes.append({
            "player": r["player"],
            "team_name_1330": r["team_name"],
            "team_name_canonical": (prev or {}).get("team_name", ""),
            "matchup_1330": r["matchup"],
            "status_1330": r["status"],
            "reason_1330": r["reason"],
            "status_canonical": (prev or {}).get("status", ""),
            "reason_canonical": (prev or {}).get("reason", ""),
            "outcome": outcome,
            "flags_1330": r["flags"],
            "source_1330": new["source_url"],
            "source_canonical": (prev or {}).get("source", ""),
        })

    canon_only = []
    new_names = set(by_name_new)
    for r in canon_players:
        if r["player"] not in new_names:
            canon_only.append({
                "player": r["player"],
                "team_name_canonical": r["team_name"],
                "status_canonical": r["status"],
                "reason_canonical": r["reason"],
                "outcome": "in_canonical_not_in_1330_report",
                "source_canonical": r["source"],
            })

    # Team-level 'NOT YET SUBMITTED' rows: keyed on (matchup, team). The 1:30 PM report often
    # prints the matchup only on the first row of a block, so a player row with a blank matchup
    # is reported as such instead of being attributed to a game.
    garbled_text = " ".join(u["raw"] for u in new.get("unparsed_lines", []))
    team_outcomes = []
    for r in canon_nys:
        same_game = [p for p in new_players if p["team_name"] == r["team_name"] and p["matchup"] == r["matchup"]]
        blank_matchup = [p for p in new_players if p["team_name"] == r["team_name"] and not p["matchup"]]
        nys_same_game = [n for n in new_nys if n["team_name"] == r["team_name"] and n["matchup"] == r["matchup"]]
        nys_blank = [n for n in new_nys if n["team_name"] == r["team_name"] and not n["matchup"]]
        if same_game:
            outcome = "team_now_reporting_players"
            names = [p["player"] for p in same_game]
        elif blank_matchup:
            outcome = "team_players_printed_matchup_blank"
            names = [p["player"] for p in blank_matchup]
        elif nys_same_game:
            outcome = "still_not_yet_submitted"
            names = []
        elif nys_blank:
            outcome = "still_not_yet_submitted_matchup_blank"
            names = []
        elif r["team_name"] in garbled_text:
            outcome = "unverified_garbled_line_only"
            names = []
        else:
            outcome = "not_matched_in_1330_report"
            names = []
        team_outcomes.append({
            "game_date": r["game_date"],
            "game_time_et": r["game_time_et"],
            "matchup": r["matchup"],
            "team_name": r["team_name"],
            "outcome": outcome,
            "players_printed_1330": names,
            "source_canonical": r["source"],
            "source_1330": new["source_url"],
        })

    summary = defaultdict(int)
    for o in player_outcomes:
        summary[o["outcome"]] += 1
    for o in canon_only:
        summary[o["outcome"]] += 1
    for o in team_outcomes:
        summary["team_" + o["outcome"]] += 1
    doc = {
        "schema": "audit_736efb4b/delta/v1",
        "compared": {
            "new_report": new["source_url"],
            "new_report_stamp": new["report_stamp"],
            "canonical_source_url": canon["injuries"]["source_url"],
            "canonical_report_stamp": canon["injuries"]["report_stamp"],
        },
        "counts": {
            "rows_in_1330_report": len(new["rows"]),
            "player_rows_in_1330_report": len(new_players),
            "not_yet_submitted_rows_in_1330_report": len(new_nys),
            "rows_in_canonical": len(canon_rows),
            "player_rows_in_canonical": len(canon_players),
            "not_yet_submitted_rows_in_canonical": len(canon_nys),
        },
        "summary": dict(sorted(summary.items())),
        "duplicate_player_names_canonical": dup_canon,
        "duplicate_player_names_1330": dup_new,
        "player_outcomes": player_outcomes,
        "canonical_players_not_in_1330": canon_only,
        "team_not_yet_submitted_outcomes": team_outcomes,
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(doc["counts"], indent=1))
    print(json.dumps(doc["summary"], indent=1))
    print("duplicates:", dup_canon, dup_new)


if __name__ == "__main__":
    main()
