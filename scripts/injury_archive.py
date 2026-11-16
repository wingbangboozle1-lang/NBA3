"""Archive official injury reports and diff consecutive versions.

Each archived file is a verbatim transcription of one official PDF. This module:
  * parses the seven-column rows,
  * classifies each row (player row / team-level 'NOT YET SUBMITTED' row),
  * diffs two consecutive reports and reports STATUS CHANGES, ADDED and REMOVED rows,
  * never fills a blank Team cell with a guess (it emits UNATTRIBUTED and says so).

Output: data/live/injuries/archive_index.json and data/live/injuries/deltas.json
Run:    python3 scripts/injury_archive.py
"""

from __future__ import annotations

import json
import pathlib
import re
import unicodedata

from freshness_gates import report_datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "live" / "injuries"
OUT_INDEX = DIR / "archive_index.json"
OUT_DELTAS = DIR / "deltas.json"

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
PAGE_HEADER = re.compile(r"\*\*Injury Report: (\d\d/\d\d/\d\d) (\d\d:\d\d [AP]M)\*\*")
SOURCE = ("https://ak-static.cms.nba.com/referee/injury/Injury-Report_{stamp}.pdf")


def norm_name(raw: str) -> str:
    """Key used to match a player across reports: casefold, strip accents and punctuation.

    Deliberately conservative: it only merges spellings that differ by case/accents/punctuation.
    'Embid' vs 'Embiid' (a one-letter vowel difference in the official PDFs) does NOT merge --
    the diff reports that pair as a remove + an add, which is what it is.
    """
    s = unicodedata.normalize("NFKD", raw)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"[^a-z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"Injury-Report_(\d{4}-\d{2}-\d{2}_\d{2}_\d{2}[AP]M)\.pdf", text)
    stamp = m.group(1) if m else path.stem.replace("Injury-Report_", "")
    header = PAGE_HEADER.search(text)
    rows, team_rows = [], []
    for line in text.splitlines():
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].upper().startswith("GAME DATE") or cells[0].upper() == "GAME DATE":
            continue
        if all(c == "" for c in cells):
            continue
        # Team-level row: matchup + team, player blank, status 'NOT YET SUBMITTED'
        if "NOT YET SUBMITTED" in " ".join(cells).upper():
            # The team cell's INDEX MOVES. On a full row it is cells[3]; on a page-break
            # continuation the league's printer has dropped a leading cell and it is cells[2].
            # Reading only cells[3:5] therefore threw away the team name on exactly the rows the
            # page break damaged -- which is how 4 of the 15 placeholders arrived blank. The cell
            # is located by content instead: the first cell that is not a date, a time, a matchup
            # or the placeholder itself.
            date = next((c for c in cells if re.match(r"\d\d/\d\d/\d{4}$", c)), "")
            game_time = next((c for c in cells if re.match(r"\d\d:\d\d \(ET\)", c)), "")
            matchup = next((c for c in cells if "@" in c), "")
            team = next((c for c in cells
                         if c and not re.match(r"\d\d/\d\d/\d{4}$", c)
                         and not re.match(r"\d\d:\d\d \(ET\)", c)
                         and "@" not in c
                         and "NOT YET SUBMITTED" not in c.upper()), "")
            team_rows.append({"date": date, "game_time": game_time,
                              "matchup": matchup, "team": team,
                              "kind": "NOT_YET_SUBMITTED"})
            continue
        # Player row. The extractor drops leading cells on page-break continuation rows, so the
        # row is aligned on the STATUS cell (one of five official statuses) rather than on index:
        #   [date] [time] [matchup] [team] | PLAYER | STATUS | REASON
        status_idx = next((i for i, c in enumerate(cells) if c in STATUSES), None)
        if status_idx is None or status_idx == 0:
            rows.append({"raw": cells, "kind": "UNPARSEABLE"})
            continue
        player = cells[status_idx - 1]
        reason = cells[status_idx + 1] if status_idx + 1 < len(cells) else ""
        before = [c for c in cells[:status_idx - 1]]
        # Right-align the leading cells against the (date, time, matchup, team) block. The
        # extractor drops the date cell on continuation rows, so a short leading block is the
        # TAIL of the block, not the head: padding on the false side would shift the matchup
        # into the date column and silently lose the team.
        padded = [""] * (4 - len(before)) + before
        date, game_time, matchup, team = padded[:4]
        if not re.match(r"\d\d/\d\d/\d{4}", date):
            date = ""
        if not re.match(r"\d\d:\d\d \(ET\)", game_time):
            game_time = ""
        if "@" not in matchup:
            matchup = ""
        if not player or not re.search(r"[A-Za-z]", player):
            rows.append({"raw": cells, "kind": "UNPARSEABLE"})
            continue
        status = cells[status_idx]
        rows.append({
            "kind": "player",
            "date": date, "game_time": game_time, "matchup": matchup,
            "team": team or "UNATTRIBUTED",
            "player": player, "status": status, "reason": reason,
            "key": norm_name(player),
        })
    return {
        "file": path.name,
        "report_stamp": stamp,
        "report_header": header.group(0).strip("*") if header else None,
        "source_url": SOURCE.format(stamp=stamp),
        "player_rows": [r for r in rows if r.get("kind") == "player"],
        "unparseable_rows": [r for r in rows if r.get("kind") != "player"],
        "team_rows": team_rows,
    }


def diff(a: dict, b: dict) -> dict:
    ka = {r["key"]: r for r in a["player_rows"]}
    kb = {r["key"]: r for r in b["player_rows"]}
    changes, added, removed = [], [], []
    for key, rb in kb.items():
        ra = ka.get(key)
        if ra is None:
            added.append(rb)
        elif ra["status"] != rb["status"]:
            changes.append({
                "player": rb["player"], "team": rb["team"], "matchup": rb["matchup"],
                "date": rb["date"], "from": ra["status"], "to": rb["status"],
                "reason_from": ra["reason"], "reason_to": rb["reason"],
            })
    for key, ra in ka.items():
        if key not in kb:
            removed.append(ra)
    reasons_changed = [
        {"player": rb["player"], "team": rb["team"], "status": rb["status"],
         "reason_from": ka[k]["reason"], "reason_to": rb["reason"]}
        for k, rb in kb.items()
        if k in ka and ka[k]["reason"] != rb["reason"]
    ]
    team_b = {(r["date"], r["matchup"], r["team"]) for r in b["team_rows"]}
    team_a = {(r["date"], r["matchup"], r["team"]) for r in a["team_rows"]}
    return {
        "from_file": a["file"], "to_file": b["file"],
        "from_stamp": a["report_stamp"], "to_stamp": b["report_stamp"],
        "from_source": a["source_url"], "to_source": b["source_url"],
        "counts": {
            "player_rows_from": len(a["player_rows"]), "player_rows_to": len(b["player_rows"]),
            "team_rows_from": len(a["team_rows"]), "team_rows_to": len(b["team_rows"]),
            "status_changes": len(changes), "added": len(added), "removed": len(removed),
        },
        "status_changes": changes,
        "reason_changes": reasons_changed,
        "added": added,
        "removed": removed,
        "team_rows_now_filed": sorted(f"{d} {m} {t}" for d, m, t in (team_a - team_b)),
        "team_rows_still_not_submitted": sorted(f"{d} {m} {t}" for d, m, t in team_b),
    }


def main() -> None:
    # Chronological order must use the report's real 12-hour clock time; lexical stamp
    # sorting puts 12:00 AM after daytime reports from the same date.
    files = sorted(DIR.glob("Injury-Report_*.md"), key=report_datetime)
    reports = [parse(p) for p in files]
    status_counts = {}
    for r in reports:
        c: dict[str, int] = {}
        for row in r["player_rows"]:
            c[row["status"]] = c.get(row["status"], 0) + 1
        r["status_counts"] = dict(sorted(c.items()))
        r["unattributed_rows"] = sum(1 for x in r["player_rows"] if x["team"] == "UNATTRIBUTED")
        status_counts[r["report_stamp"]] = r["status_counts"]

    deltas = [diff(reports[i], reports[i + 1]) for i in range(len(reports) - 1)]
    index = {
        "schema": "nba3.live.injury_archive/v1",
        "session": "arena/2ebb1e75-nba3",
        "storage_rule": ("One file per official report version, stored verbatim with its report "
                         "timestamp and retrieval time, so consecutive versions can be diffed."),
        "files": [{k: v for k, v in r.items() if k not in ("player_rows", "team_rows")}
                  for r in reports],
        "totals": {"reports": len(reports),
                   "player_rows": sum(len(r["player_rows"]) for r in reports),
                   "status_counts_by_report": status_counts},
    }
    OUT_INDEX.write_text(json.dumps(index, indent=1) + "\n")
    OUT_DELTAS.write_text(json.dumps({"schema": "nba3.live.injury_deltas/v1",
                                      "deltas": deltas}, indent=1) + "\n")
    for d in deltas:
        c = d["counts"]
        print(f"{d['from_stamp']} -> {d['to_stamp']}: {c['status_changes']} status change(s), "
              f"{c['added']} added, {c['removed']} removed, "
              f"{c['player_rows_from']} -> {c['player_rows_to']} player rows")
        for ch in d["status_changes"]:
            print(f"   {ch['player']} ({ch['team']}): {ch['from']} -> {ch['to']}")
        for a in d["added"]:
            print(f"   + {a['player']} ({a['team']}, {a['status']})")
        for r in d["removed"]:
            print(f"   - {r['player']} ({r['team']}, {r['status']})")


if __name__ == "__main__":
    main()
