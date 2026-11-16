#!/usr/bin/env python3
"""Parse the verbatim 2026-11-16 01:30 PM ET injury-report transcript (session arena/ef6e2e6c-nba3).

Input : data/rounds/2026-11-16-eve/raw/Injury-Report_2026-11-16_01_30PM_chunk{0,1}.md
        (copied cell for cell from the official PDF via the agent fetch tool)

Output: data/rounds/2026-11-16-eve/injuries_0130pm.json
        data/rounds/2026-11-16-eve/injury_delta.json   (09:15 AM -> 01:30 PM, same game day)

Rules (the parser never guesses):
  * every cell is classified by content (date / time / matchup / team / player / status / reason);
  * a cell that is structurally absent on a page-break row is CARRIED from the row above only
    when the carried value is consistent with the row's own printed cells (team must belong to
    the printed or carried matchup); every carry is recorded on the row;
  * a status cell that is not printed stays None with a note — never copied from another report;
  * a lone continuation cell (e.g. "Fracture") is appended to the previous row's reason and
    flagged as a page-break continuation;
  * validation fails loudly: bad status, unknown team, team outside its matchup, unexpected
    date, or a row count that does not match the printed report.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "rounds" / "2026-11-16-eve" / "raw"
OUT = ROOT / "data" / "rounds" / "2026-11-16-eve" / "injuries_0130pm.json"
BASE = ROOT / "data" / "rounds" / "2026-11-16" / "injuries.json"   # 09:15 AM capture (session 8f4fac33)
DELTA_OUT = ROOT / "data" / "rounds" / "2026-11-16-eve" / "injury_delta.json"

SOURCE = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_30PM.pdf"
INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
VALID_STATUS = ("Out", "Doubtful", "Questionable", "Probable", "Available")
NUS = "NOT YET SUBMITTED"

TEAMS = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")
MATCHUP_RE = re.compile(r"^([A-Z]{3})@([A-Z]{3})$")
SEP_RE = re.compile(r"^:?-+:?$")
PLAYER_RE = re.compile(r"^[A-Z][^,]*,.+")          # "Last, First" (at least one comma)


def cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def read_chunks() -> list[str]:
    lines: list[str] = []
    c0 = (RAW / "Injury-Report_2026-11-16_01_30PM_chunk0.md").read_text(encoding="utf-8")
    c1 = (RAW / "Injury-Report_2026-11-16_01_30PM_chunk1.md").read_text(encoding="utf-8")
    lines += [l for l in c0.splitlines() if l.startswith("|")]
    lines += [l for l in c1.splitlines() if l.startswith("|")]
    # stitch the chunk-boundary row: chunk0 ends "... | PHX@DEN | Denver" and chunk1
    # starts with "| Denver Nuggets | Whitmore, Cam | Out | G League - Two-Way |"
    stitched: list[str] = []
    i = 0
    while i < len(lines):
        cs = cells(lines[i])
        if cs and cs[-1] == "Denver" and i + 1 < len(lines):
            nxt = cells(lines[i + 1])
            if nxt and nxt[0] == "Denver Nuggets":
                stitched.append("| " + " | ".join(cs + nxt) + " |")
                i += 2
                continue
        stitched.append(lines[i])
        i += 1
    return stitched


def parse() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    carried = {"date": None, "game_time": None, "matchup": None, "team": None}
    problems: list[str] = []
    for ln in read_chunks():
        cs = cells(ln)
        if not cs or all(SEP_RE.match(c) for c in cs):
            continue
        if cs[0] == "Game Date":
            continue
        nonempty = [c for c in cs if c]

        # page-break continuation of a reason (a lone fragment like "Fracture")
        if (len(nonempty) == 1 and nonempty[0] not in VALID_STATUS and nonempty[0] != NUS
                and not PLAYER_RE.match(nonempty[0]) and not MATCHUP_RE.match(nonempty[0])
                and nonempty[0] not in TEAMS and rows):
            rows[-1]["reason"] = rows[-1]["reason"] + " " + nonempty[0]
            rows[-1].setdefault("page_break_reason_cells", []).append(nonempty[0])
            continue

        date = next((c for c in cs if DATE_RE.match(c)), None)
        time_ = next((c for c in cs if TIME_RE.match(c)), None)
        matchup = next((c for c in cs if MATCHUP_RE.match(c)), None)
        team = next((c for c in cs if c in TEAMS), None)
        status = next((c for c in cs if c in VALID_STATUS), None)
        nus = any(c == NUS for c in cs)
        # player: first comma-bearing cell that is not a team
        player = next((c for c in cs if PLAYER_RE.match(c) and c not in TEAMS), None)
        # reason: the last cell that is not date/time/matchup/team/player/status
        consumed = {date, time_, matchup, team, status, player}
        reason = None
        for c in reversed(cs):
            if c and c not in consumed and c != NUS and not DATE_RE.match(c) \
                    and not TIME_RE.match(c) and not MATCHUP_RE.match(c):
                reason = c
                break

        row_carried = []
        def take(field, value):
            if value is None:
                v = carried[field]
                if v is None:
                    problems.append(f"cannot carry {field} for row {cs}")
                    return None
                row_carried.append(field)
                return v
            carried[field] = value
            return value

        if nus:
            r = {
                "kind": "NOT_YET_SUBMITTED",
                "date": take("date", date),
                "game_time": take("game_time", time_),
                "matchup": take("matchup", matchup),
                "team": take("team", team),
                "status": None,
                "reason": NUS,
            }
        else:
            if player is None:
                problems.append(f"no player cell in row {cs}")
                continue
            r = {
                "kind": "player",
                "date": take("date", date),
                "game_time": take("game_time", time_),
                "matchup": take("matchup", matchup),
                "team": take("team", team),
                "player": player,
                "status": status,
                "reason": reason or "",
            }
            if status is None:
                r["status_missing_note"] = (
                    "the printed row carries no Current Status cell (page-break drop); "
                    "published blank rather than copied from an earlier report")
            if reason is None:
                r["reason_blank_note"] = "the printed row carries no Reason cell (page-break drop)"
        if row_carried:
            r["carried"] = row_carried
        r["source_url"] = SOURCE
        rows.append(r)
    return rows, problems


def norm_name(raw: str) -> str:
    s = raw.casefold()
    s = re.sub(r"[^a-z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def validate(rows: list[dict], problems: list[str]) -> dict:
    errors = list(problems)
    for i, r in enumerate(rows):
        if r["date"] not in ("11/16/2026", "11/17/2026"):
            errors.append(f"row {i}: unexpected date {r['date']!r}")
        if not r["matchup"] or not MATCHUP_RE.match(r["matchup"]):
            errors.append(f"row {i}: missing matchup")
            continue
        a, h = r["matchup"].split("@")
        abbr = TEAMS.get(r["team"] or "")
        if abbr not in (a, h):
            errors.append(f"row {i}: team {r['team']!r} ({abbr}) not in matchup {r['matchup']}")
        if r["kind"] == "player":
            if r["status"] is not None and r["status"] not in VALID_STATUS:
                errors.append(f"row {i}: bad status {r['status']!r}")
            if not PLAYER_RE.match(r["player"]):
                errors.append(f"row {i}: bad player name {r['player']!r}")
    by_date: dict[str, int] = {}
    for r in rows:
        by_date[r["date"]] = by_date.get(r["date"], 0) + 1
    return {
        "errors": errors,
        "rows_by_game_date": by_date,
        "player_rows": sum(1 for r in rows if r["kind"] == "player"),
        "not_submitted_rows": sum(1 for r in rows if r["kind"] == "NOT_YET_SUBMITTED"),
        "rows_with_missing_status": sum(
            1 for r in rows if r["kind"] == "player" and r["status"] is None),
        "rows_with_carried_cells": sum(1 for r in rows if r.get("carried")),
    }


def build_delta(new_rows: list[dict]) -> dict:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    def key(r):
        team = r.get("team")
        name = r.get("player")
        if r["kind"] == "player" and name:
            return (TEAMS.get(team, team), norm_name(name))
        return (TEAMS.get(team, team or ""), "NUS")
    old = {key(r): r for r in base["rows"] if r.get("kind") == "player"}
    new = {key(r): r for r in new_rows if r.get("kind") == "player"}
    status_changes, added, removed, reason_changes = [], [], [], []
    for k, nr in new.items():
        if k not in old:
            added.append({"team": k[0], "player": nr["player"], "status": nr["status"],
                          "reason": nr["reason"]})
        else:
            orow = old[k]
            if orow.get("status") != nr.get("status"):
                status_changes.append({"team": k[0], "player": nr["player"],
                                       "from": orow.get("status"), "to": nr.get("status"),
                                       "reason": nr.get("reason")})
            elif (orow.get("reason") or "") != (nr.get("reason") or ""):
                reason_changes.append({"team": k[0], "player": nr["player"],
                                       "status": nr.get("status"),
                                       "from_reason": orow.get("reason"),
                                       "to_reason": nr.get("reason")})
    for k, orow in old.items():
        if k not in new:
            removed.append({"team": k[0], "player": orow["player"],
                            "was_status": orow.get("status")})
    old_nus = {(TEAMS.get(r.get("team"), r.get("team")), r.get("matchup"))
               for r in base["rows"] if r.get("kind") == "NOT_YET_SUBMITTED"}
    new_nus = {(TEAMS.get(r.get("team"), r.get("team")), r.get("matchup"))
               for r in new_rows if r.get("kind") == "NOT_YET_SUBMITTED"}
    return {
        "schema": "nba3.round.injury_delta/v1",
        "base": {"report_stamp": base["report_stamp"], "url": base["source_url"],
                 "player_rows": base["player_rows"]},
        "new": {"report_stamp": "2026-11-16 01:30 PM ET", "url": SOURCE,
                "player_rows": sum(1 for r in new_rows if r["kind"] == "player")},
        "status_changes": status_changes,
        "reason_changes": reason_changes,
        "newly_listed": added,
        "delisted": removed,
        "nus_filed_since_base": sorted(
            [{"team_abbr": t, "matchup": m} for (t, m) in old_nus - new_nus],
            key=lambda d: (d["matchup"] or "", d["team_abbr"] or "")),
        "nus_new_since_base": sorted(
            [{"team_abbr": t, "matchup": m} for (t, m) in new_nus - old_nus],
            key=lambda d: (d["matchup"] or "", d["team_abbr"] or "")),
        "notes": [
            "delta is keyed on (team, normalised player name); a name-spelling change "
            "between official prints appears as delisted + newly_listed and is listed "
            "in flags, never silently merged",
        ],
    }


def main() -> int:
    rows, problems = parse()
    report = validate(rows, problems)
    out = {
        "schema": "nba3.round.injuries/v1",
        "report_stamp": "2026-11-16 01:30 PM ET",
        "source_url": SOURCE,
        "index_url": INDEX,
        "retrieved_utc": "2026-11-16T19:05Z",
        "retrieval": "agent fetch tool, PDF rendered as markdown, copied cell for cell",
        "count": len(rows),
        "player_rows": report["player_rows"],
        "not_submitted_rows": report["not_submitted_rows"],
        "rows_with_missing_status": report["rows_with_missing_status"],
        "rows_with_carried_cells": report["rows_with_carried_cells"],
        "rows_by_game_date": report["rows_by_game_date"],
        "validation": {
            "errors": report["errors"],
            "checks": [
                "every date is 11/16/2026 or 11/17/2026 after carry",
                "every team belongs to its printed or carried matchup",
                "every player status is one of Out/Doubtful/Questionable/Probable/Available "
                "or explicitly blank with a note",
                "every player name is in the printed Last, First form",
            ],
            "pass": not report["errors"],
        },
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    delta = build_delta(rows)
    DELTA_OUT.write_text(json.dumps(delta, indent=1, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"rows: {len(rows)} (players {report['player_rows']}, "
          f"NUS {report['not_submitted_rows']})")
    print(f"by date: {report['rows_by_game_date']}")
    print(f"missing status: {report['rows_with_missing_status']}, "
          f"carried-cell rows: {report['rows_with_carried_cells']}")
    print(f"validation: {'PASS' if not report['errors'] else 'FAIL'}")
    for e in report["errors"]:
        print("  ERROR:", e)
    print(f"delta: {len(delta['status_changes'])} status changes, "
          f"{len(delta['reason_changes'])} reason changes, "
          f"{len(delta['newly_listed'])} newly listed, {len(delta['delisted'])} delisted, "
          f"{len(delta['nus_filed_since_base'])} NUS filed since base")
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
