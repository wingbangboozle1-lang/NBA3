"""Rotation availability per team-side of every slate game, as its own published column.

Three states, and the third is the important one:

  ANNOUNCED      the official report names at least one player Out/Doubtful for that team in that
                 game, with the player names and the report's own timestamp.
  REPORTED_CLEAR the official report carries a row for that team and that matchup, and no player
                 is Out/Doubtful. This is a statement about the report, NOT a statement that
                 everyone will play: the report only lists players the club has submitted.
  NOT_SUBMITTED  the report's team row says the club has not yet submitted. Nothing is known.

`INJURY REPORT: NOT YET SUBMITTED` rows in the official PDF are exactly the case the brief says
must be blank rather than inferred. They are published as UNKNOWN, never as "healthy".

Run: python3 scripts/availability.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import injury_archive as ia                                                  # noqa: E402

INJ = ROOT / "data" / "live" / "injuries"
SLATE = ROOT / "data" / "live" / "slate_2026-11-15.json"
REGISTRY = ROOT / "data" / "live" / "team_registry.json"
OUT = ROOT / "data" / "live" / "availability.json"


def latest() -> pathlib.Path:
    # timestamp order, not lexical: '12_00AM' sorts lexically after '06_45PM' but is 19h older
    return max(INJ.glob("Injury-Report_*.md"), key=ia.report_stamp_key)


def build() -> dict:
    path = latest()
    rep = ia.parse(path)
    slate = json.loads(SLATE.read_text())
    registry = json.loads(REGISTRY.read_text())
    code_of_full = {v["full_name"]: k for k, v in registry["teams"].items()}
    full_of_code = {k: v["full_name"] for k, v in registry["teams"].items()}

    # team rows: which clubs have submitted at all, keyed by matchup string
    submitted = {}
    for tr in rep["team_rows"]:
        key = (tr.get("matchup") or "").replace(" ", "")
        submitted.setdefault(key, {"not_yet": [], "rows": 0})
        submitted[key]["rows"] += 1
        if tr.get("kind") == "NOT_YET_SUBMITTED":
            submitted[key]["not_yet"].append(tr.get("team") or "UNKNOWN")

    out_by_matchup_team: dict[tuple, list[dict]] = {}
    for row in rep["player_rows"]:
        if row["team"] == "UNATTRIBUTED":
            continue
        if row["status"] in ("Out", "Doubtful", "Questionable"):
            k = (row["matchup"].replace(" ", ""), row["team"])
            out_by_matchup_team.setdefault(k, []).append(
                {"player": row["player"], "status": row["status"], "reason": row.get("reason", "")})

    sides = []
    for g in slate["games"]:
        mk = f"{g['away']}@{g['home']}"
        for code, side, full in ((g["away"], "away", g["away_name"]),
                                 (g["home"], "home", g["home_name"])):
            listed = out_by_matchup_team.get((mk, full), [])
            not_yet = full in submitted.get(mk, {}).get("not_yet", [])
            hard = [p for p in listed if p["status"] in ("Out", "Doubtful")]
            q = [p for p in listed if p["status"] == "Questionable"]
            if not_yet:
                state, why = "NOT_SUBMITTED", ("the official report's team row says the club has not "
                                               "yet submitted for this game")
            elif hard:
                state, why = "ANNOUNCED", f"{len(hard)} player(s) listed Out or Doubtful"
            elif q:
                state, why = "ANNOUNCED", f"{len(q)} player(s) listed Questionable, none Out"
            else:
                state, why = "REPORTED_CLEAR", ("a row exists for this team and matchup with no "
                                                "Out/Doubtful/Questionable player")
            sides.append({
                "game_id": g["game_id"], "date": g["date"], "tip_et": g["tip_et"],
                "matchup": mk, "team": code, "team_name": full, "side": side,
                "availability": state, "why": why,
                "out_or_doubtful": hard, "questionable": q,
                "count_out_or_doubtful": len(hard), "count_questionable": len(q),
                "report_file": path.name, "report_stamp": rep["report_stamp"],
                "report_header": rep["report_header"], "source_url": rep["source_url"],
                "registry_url": registry["teams"].get(code, {}).get("source_url", ""),
                "rule": ("ANNOUNCED = at least one Out/Doubtful/Questionable player named for this "
                         "team in this game. REPORTED_CLEAR = a team row exists with no such player. "
                         "NOT_SUBMITTED = the report itself says the club has not submitted, so "
                         "nothing about availability is known and none is inferred."),
            })

    counts = {}
    for s in sides:
        counts[s["availability"]] = counts.get(s["availability"], 0) + 1
    return {
        "schema": "nba3.live.availability/v1",
        "session": "arena/2ebb1e75-nba3",
        "report": {"file": path.name, "stamp": rep["report_stamp"],
                   "header": rep["report_header"], "source_url": rep["source_url"],
                   "retrieved_utc": "2026-11-15T11:33Z",
                   "note": ("Revision time is the report's own header. Retrieval time is when this "
                            "session fetched the PDF. Both are shown on the Injuries page.")},
        "counts": {"team_sides": len(sides), "by_state": counts,
                   "games_with_an_announced_absence":
                       len({s["game_id"] for s in sides if s["availability"] == "ANNOUNCED"}),
                   "games_with_a_not_submitted_side":
                       len({s["game_id"] for s in sides if s["availability"] == "NOT_SUBMITTED"})},
        "sides": sides,
    }


def main() -> None:
    payload = build()
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"{payload['counts']['team_sides']} team-sides: {payload['counts']['by_state']}")
    print(f"games with an announced absence: {payload['counts']['games_with_an_announced_absence']}; "
          f"games with a not-submitted side: {payload['counts']['games_with_a_not_submitted_side']}")
    for s in payload["sides"]:
        if s["availability"] == "ANNOUNCED":
            print(f"  {s['date']} {s['matchup']} {s['team']}: "
                  f"{[p['player'] + ' ' + p['status'] for p in s['out_or_doubtful'] + s['questionable']]}")


if __name__ == "__main__":
    main()
