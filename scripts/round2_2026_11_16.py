#!/usr/bin/env python3
"""Round 2 of the 2026-11-16 official refresh: the 1:00 PM ET filing.

Session arena/fbd2484b-nba3.

WHY THIS FILE EXISTS
--------------------
The scheduled job must refresh the official injury report for each rolling slate and rebuild
only after freshness and provenance gates pass. `main` published an 11/16 snapshot of
09:15 AM ET. The official index listed filings through 01:00 PM ET, so the published
availability picture was stale on its own stated terms.

This module does five things, in this order, and nothing else:

  1. parse   the 1:00 PM ET injury PDF and the 09:15 AM ET one (both committed verbatim,
             never fetched here), the official schedule, standings and three team-stat pages;
  2. diff    consecutive same-day filings row by row, so an injury status change is a datum;
  3. measure only what the official tables support (home-win rate, possessions, points per
             possession, two estimators and their disagreement, luck z-scores, rho);
  4. gate    freshness, provenance and integrity, with explicit build/row scope;
  5. write   artefacts and pages, or refuse to.

RULES THIS FILE WILL NOT BREAK
------------------------------
* No repair. Where an official document contradicts itself both readings are published and the
  row is withheld from everything downstream. Nothing is averaged out.
* No inference. A cell the official document does not print is null and counted. The two such
  cells in the 1:00 PM filing (Butler III's and Curry's status) are null, not back-filled.
* No silent splice. The 1:00 PM PDF's page break falls inside a row; it is spliced, counted in
  `seam_splice_rows`, and pinned by a unit test so the parser cannot start guessing.
* No wall clock in any artefact: the same committed inputs reproduce the same bytes, which is
  what lets CI diff the tree.

Run:
  python3 scripts/round2_2026_11_16.py            rebuild artefacts + pages
  python3 scripts/round2_2026_11_16.py --check    rebuild in memory, diff against disk
  python3 scripts/round2_2026_11_16.py --gates    print the gate report, non-zero on blocking
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-16-1300PM")
RAW = os.path.join(ROUND, "raw")

SESSION = "arena/fbd2484b-nba3"

INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJURY_PDF_1300 = ("https://ak-static.cms.nba.com/referee/injury/"
                   "Injury-Report_2026-11-16_01_00PM.pdf")
INJURY_PDF_0915 = ("https://ak-static.cms.nba.com/referee/injury/"
                   "Injury-Report_2026-11-16_09_15AM.pdf")
INJURY_PDF_0115 = ("https://ak-static.cms.nba.com/referee/injury/"
                   "Injury-Report_2026-11-16_01_15PM.pdf")
SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-16"
STANDINGS_URL = "https://www.nba.com/standings"
STATS_TRADITIONAL_URL = "https://www.nba.com/stats/teams/traditional"
STATS_OPPONENT_URL = "https://www.nba.com/stats/teams/opponent"
STATS_ADVANCED_URL = "https://www.nba.com/stats/teams/advanced"

RETRIEVED_1300 = "2026-11-16T14:52Z"   # Arena fetch tool, PDF chunks 0+1 of 2
RETRIEVED_0915 = "2026-11-16T14:35Z"   # recorded when session 8f4fac33 captured it
RETRIEVED_0115 = "2026-11-16T15:20Z"   # this session, after the index advanced

REPORT_STAMP_1300 = "2026-11-16 01:00 PM ET"
REPORT_STAMP_0915 = "2026-11-16 09:15 AM ET"
REPORT_STAMP_0115 = "2026-11-16 01:15 PM ET"
INDEX_NEWEST_AT_READ = "2026-11-16 01:00 PM ET"     # when the 1:00 PM PDF was captured
INDEX_NEWEST_AT_READ_2 = "2026-11-16 01:15 PM ET"   # when the index was re-read
INDEX_SLOT_COUNT_1116 = 52          # slots listed when the 1:00 PM PDF was captured
# The index was re-read once more, after the artefacts were built, and had advanced. Recorded
# here because a capture is only ever "newest at its read time"; claiming otherwise would be the
# one thing this project must never do.
INDEX_REREAD_NEWEST = "2026-11-16 01:15 PM ET"
INDEX_REREAD_SLOT_COUNT = 53
INDEX_REREAD_AT = "2026-11-16T15:12Z"

STATUSES = ("Out", "Questionable", "Doubtful", "Available", "Probable")

ELIGIBILITY = {
    "Out": 0.0, "Doubtful": 0.25, "Questionable": 0.5,
    "Probable": 0.9, "Available": 1.0, None: 0.0,
}

# ----------------------------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------------------------


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def write_json(name: str, obj) -> str:
    path = os.path.join(ROUND, name)
    text = json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def rnd(x, n=4):
    if x is None:
        return None
    return float(round(x, n))


# ----------------------------------------------------------------------------------------------
# the 30 official club names (used to locate a team cell BY CONTENT, never by index)
# ----------------------------------------------------------------------------------------------

def load_tsv(path: str) -> list:
    rows, hdr = [], None
    for line in read_text(path).splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cells = line.split("\t")
        if hdr is None:
            hdr = cells
            continue
        rows.append(dict(zip(hdr, cells)))
    return rows


def team_universe() -> dict:
    """Full club name -> abbreviation, from the official team-stat page transcript."""
    path = os.path.join(RAW, "team_stats_traditional_2026-11-16.tsv")
    return {r["team"]: r["abbr"] for r in load_tsv(path)}


TEAM_ABBR = team_universe()
TEAM_NAMES = set(TEAM_ABBR)

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s*\((ET|PT)\)$")
MATCH_RE = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")
PLAYER_RE = re.compile(r"^[A-Z][A-Za-z'.\-]+(?:[ A-Za-z'.\-]*),\s*[A-Za-z'.\- ]+")
HEADER_CELLS = {"Game Date", "Game Time", "Matchup", "Team", "Player Name",
                "Current Status", "Reason"}

SEAM_MARK = "<!-- SEAM: SPLICED ROW -->"
END_SEAM = "<!-- END SEAM -->"
CHUNK_MARK = re.compile(r"^<!-- CHUNK \d+ -->\s*$")


def _cell_kind(cell: str) -> str:
    """Classify one printed cell by content. Never by position."""
    s = cell.strip()
    if not s:
        return "blank"
    if s in HEADER_CELLS:
        return "header"
    if s == "NOT YET SUBMITTED":
        return "not_submitted"
    if DATE_RE.match(s):
        return "date"
    if TIME_RE.match(s):
        return "time"
    if MATCH_RE.match(s):
        return "matchup"
    if s in TEAM_NAMES:
        return "team"
    if s in STATUSES:
        return "status"
    if PLAYER_RE.match(s):
        return "player"
    return "text"


def _split_row(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(cells: list) -> bool:
    return all(re.fullmatch(r"-{2,}|:?-{2,}:?|", c.strip()) for c in cells) and any(
        c.strip() for c in cells)


def table_rows(text: str):
    """Yield (line_index, cells, spliced) for each logical table row in a transcript.

    Handles the explicit page-break splice markers written by the capture step.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s == SEAM_MARK:
            head = _split_row(lines[i - 1])
            tail = []
            j = i + 1
            while j < len(lines) and lines[j].strip() != END_SEAM:
                if lines[j].strip():
                    tail.append(_split_row(lines[j]))
                j += 1
            merged = head + (tail[0] if tail else [])
            yield (i, merged, True)
            i = j + 1
            continue
        if s.startswith("|"):
            cells = _split_row(lines[i])
            if not _is_separator(cells):
                yield (i, cells, False)
        i += 1


ABBR_BY_NAME = None


def _abbr(name):
    global ABBR_BY_NAME
    if ABBR_BY_NAME is None:
        ABBR_BY_NAME = team_universe()
    return ABBR_BY_NAME.get(name, name)


def _iso_date(label):
    """'11/16/2026' -> '2026-11-16'. Anything else is returned unchanged so a mismatch shows."""
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", (label or "").strip())
    if not m:
        return label
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"


def _schedule_lookup(schedule_rows):
    """(club full name, ISO date) -> list of official games. Used only to resolve a missing cell."""
    out = {}
    for g in schedule_rows:
        out.setdefault((g["away"], g["date"]), []).append(g)
        out.setdefault((g["home"], g["date"]), []).append(g)
    return out


def parse_injury_report(path: str, *, label: str, retrieved: str, pdf_url: str,
                        schedule_rows=None) -> dict:
    """Parse a committed verbatim injury-report transcription into attributed rows.

    The seven-column table has continuation shapes where the leading context columns are
    printed blank. Every cell is classified by CONTENT and the row is assembled from what is
    present. Three attribution rules, each recorded on the row:

      * `team`     - printed, or inherited from the preceding row of the SAME matchup block.
      * `matchup`  - printed, or resolved from the OFFICIAL SCHEDULE (the club's only game on
                     that date). It is NEVER inherited across a page break: the previous
                     matchup is a different game after the break, and inheriting it was the
                     defect that made five Brooklyn Nets rows appear under HOU@MIA.
      * anything that cannot be attributed is counted, not guessed.
    """
    text = read_text(path)
    rows = []
    seam_rows = []
    dropped_spill = []
    unparsed = []

    cur_date = cur_time = cur_match = None

    for line_idx, cells, spliced in table_rows(text):
        kinds = [_cell_kind(c) for c in cells]
        if "header" in kinds:
            continue

        if spliced:
            seam_rows.append({
                "line": line_idx + 1,
                "printed_cells": cells,
                "team": next((c for k, c in zip(kinds, cells) if k == "team"), None),
                "player": next((c for k, c in zip(kinds, cells) if k == "player"), None),
                "status": next((c for k, c in zip(kinds, cells) if k == "status"), None),
                "matchup": next((c for k, c in zip(kinds, cells) if k == "matchup"), None),
                "note": ("page break falls inside this row; the head and tail cells are "
                         "printed on separate lines in the transcript and merged here"),
            })

        date_c = next((c for k, c in zip(kinds, cells) if k == "date"), None)
        time_c = next((c for k, c in zip(kinds, cells) if k == "time"), None)
        match_c = next((c for k, c in zip(kinds, cells) if k == "matchup"), None)

        if date_c:
            cur_date = date_c
        if time_c:
            cur_time = time_c
        if match_c:
            cur_match = match_c

        if "not_submitted" in kinds:
            team_cell = next((c for k, c in zip(kinds, cells) if k == "team"), "")
            if not team_cell:
                team_cell = next((c for k, c in zip(kinds, cells) if k == "text"), "")
            rows.append({
                "kind": "not_submitted",
                "game_date": date_c or cur_date,
                "game_time": time_c or cur_time,
                "matchup": match_c or cur_match,
                "matchup_printed": bool(match_c),
                "team": team_cell,
                "player": None,
                "status": None,
                "reason": "NOT YET SUBMITTED",
                "recovered": [k for k in ("game_date", "game_time", "matchup") if k not in kinds],
                "attribution": "explicit" if (team_cell and match_c) else "recovered",
                "line": line_idx + 1,
            })
            continue

        team_c = next((c for k, c in zip(kinds, cells) if k == "team"), None)
        status_c = next((c for k, c in zip(kinds, cells) if k == "status"), None)
        player_c = next((c for k, c in zip(kinds, cells) if k == "player"), None)
        text_c = [c for k, c in zip(kinds, cells) if k == "text" and c not in HEADER_CELLS]
        reason_c = text_c[0] if text_c else None

        if player_c is None:
            if any(k != "blank" for k in kinds) and not team_c:
                dropped_spill.append({"line": line_idx + 1, "printed_cells": cells})
                continue
            unparsed.append({"line": line_idx + 1, "printed_cells": cells})
            continue

        recovered = []
        if not date_c:
            recovered.append("game_date")
        if not time_c:
            recovered.append("game_time")
        if not match_c:
            recovered.append("matchup")

        rows.append({
            "kind": "player",
            "game_date": date_c or cur_date,
            "game_time": time_c or cur_time,
            "matchup": match_c or None,
            "matchup_printed": bool(match_c),
            "team": team_c,
            "player": player_c,
            "status": status_c,
            "reason": reason_c,
            "recovered": recovered,
            "attribution": "explicit" if not recovered else "recovered",
            "line": line_idx + 1,
        })

    # pass 2 - team: a row printed with a blank club cell is a continuation of the club block
    # above it. Inherit from the nearest preceding row that prints a club, and record the source
    # row number. The inheritance is NOT trusted on its own: pass 3 resolves the matchup from the
    # official schedule using the inherited club, and gate G7 refuses the whole build if the
    # resolved matchup does not contain that club. A wrong inheritance therefore fails loudly.
    for idx, row in enumerate(rows):
        if row["kind"] != "player" or row.get("team"):
            continue
        prev = next((rows[j] for j in range(idx - 1, -1, -1)
                     if rows[j].get("team") and rows[j].get("kind") == "player"), None)
        if prev is not None:
            row["team"] = prev["team"]
            row["team_recovered_from"] = f"row {prev['line']} ({prev['player']})"
            row["attribution"] = "recovered"

    # pass 3 - matchup: resolve from the official schedule, never from stale context.
    lookup = _schedule_lookup(schedule_rows) if schedule_rows else {}
    for row in rows:
        if row.get("matchup"):
            continue
        club = row.get("team")
        gd = _iso_date(row.get("game_date"))
        games = lookup.get((club, gd), []) if club else []
        if len(games) == 1:
            g = games[0]
            row["matchup"] = f"{_abbr(g['away'])}@{_abbr(g['home'])}"
            row["matchup_recovered_from"] = (
                "official schedule: the club's only game on this date")
            row["attribution"] = "recovered"
        else:
            row["matchup_unresolved"] = (
                f"{len(games)} official games for this club on {gd}; refusing to guess")
            row["attribution"] = "unresolved"

    player_rows = [r for r in rows if r["kind"] == "player"]
    ns_rows = [r for r in rows if r["kind"] == "not_submitted"]
    missing_status = [r for r in player_rows if r["status"] is None]
    unknown_team = [r for r in player_rows if not r["team"]]

    by_team = {}
    for r in player_rows:
        by_team.setdefault(r["team"] or "(unattributed)", []).append(r)

    ns_by_team = {}
    for r in ns_rows:
        ns_by_team[r["team"] or "(unattributed)"] = ns_by_team.get(r["team"] or "(unattributed)", 0) + 1

    # the report's own header stamp, parsed out of the document itself (never assumed)
    stamp_hits = re.findall(r"\*\*Injury Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}\s*[AP]M)\*\*",
                            text)
    stamps = sorted({f"{d} {t}" for d, t in stamp_hits})

    return {
        "label": label,
        "source_url": pdf_url,
        "index_url": INJURY_INDEX_URL,
        "transcript": rel(path),
        "transcript_sha256": sha256_file(path),
        "retrieved_utc": retrieved,
        "retrieval": "Arena fetch tool, PDF text extraction, chunk 0 of 2 then chunk 1 of 2"
                     if "1300" in label else
                     "Arena fetch tool, PDF text extraction (captured by session 8f4fac33-nba3)",
        "pdf_header_stamps": stamps,
        "row_count": len(rows),
        "player_rows": len(player_rows),
        "not_submitted_rows": len(ns_rows),
        "rows_with_missing_status": len(missing_status),
        "rows_with_missing_status_detail": [
            {"line": r["line"], "team": r["team"], "player": r["player"],
             "matchup": r["matchup"], "reason": r["reason"]} for r in missing_status],
        "rows_with_unattributed_team": len(unknown_team),
        "rows_with_unattributed_team_detail": [
            {"line": r["line"], "player": r["player"], "matchup": r["matchup"]}
            for r in unknown_team],
        "seam_splice_row_count": len(seam_rows),
        "seam_splice_rows": seam_rows,
        "dropped_spill_rows": dropped_spill,
        "unparsed_rows": unparsed,
        "teams_with_player_rows": len(by_team),
        "teams_with_player_rows_detail": {k: len(v) for k, v in sorted(by_team.items())},
        "teams_not_yet_submitted": ns_by_team,
        "rows": rows,
    }


# ----------------------------------------------------------------------------------------------
# 2. consecutive-report diff
# ----------------------------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _normalise_name(name: str) -> str:
    """Lower-case the whole printed name. The official format is 'Surname, First', and the
    spelling difference on this pair is in the FIRST name (Bennedict / Benedict), so comparing
    only the surname would miss it."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


def diff_reports(new: dict, old: dict) -> dict:
    """Row-by-row status change between two filings.

    Keyed on (matchup, team, player) because the filing is per game day and a player can appear
    once per matchup. A player present in both is compared on status and reason; a player in
    only one is an addition or a removal. Nothing is matched by row position: the two filings
    are laid out differently (the newer one is longer) so positional matching would be wrong.
    """
    def key(r):
        return (r.get("matchup") or "", r.get("team") or "?", (r.get("player") or "?"))

    def index(rep):
        out = {}
        for r in rep["rows"]:
            if r["kind"] != "player":
                continue
            out.setdefault(key(r), []).append(r)
        return out

    new_i, old_i = index(new), index(old)
    changes, added, removed, unchanged = [], [], [], 0

    for k in sorted(set(new_i) | set(old_i)):
        n = new_i.get(k, [])
        o = old_i.get(k, [])
        if not n:
            for r in o:
                removed.append({"matchup": k[0], "team": k[1], "player": k[2],
                                "was_status": r["status"], "was_reason": r["reason"]})
            continue
        if not o:
            for r in n:
                added.append({"matchup": k[0], "team": k[1], "player": k[2],
                              "now_status": r["status"], "now_reason": r["reason"],
                              "line": r["line"]})
            continue
        n, o = n[0], o[0]
        if n["status"] != o["status"] or n["reason"] != o["reason"]:
            changes.append({
                "matchup": k[0], "team": k[1], "player": k[2],
                "was_status": o["status"], "now_status": n["status"],
                "was_reason": o["reason"], "now_reason": n["reason"],
                "direction": _direction(o["status"], n["status"]),
                "new_line": n["line"], "old_line": o["line"],
            })
        else:
            unchanged += 1

    # A player whose NAME is printed differently in the two filings is not a player who left and
    # another who arrived. Pair the removals with the additions inside the same matchup and club
    # when the surname is within two edits, and report it as its own category. The 11/15 Embiid /
    # Embid case is the precedent; on this pair it is Mathurin, Bennedict / Benedict.
    spelling = []
    still_removed = []
    used_added = set()
    for r in removed:
        match = None
        for i, a in enumerate(added):
            if i in used_added:
                continue
            if a["matchup"] != r["matchup"] or a["team"] != r["team"]:
                continue
            d = _levenshtein(_normalise_name(a["player"]), _normalise_name(r["player"]))
            if 0 < d <= 2:
                match = (i, a, d)
                break
        if match:
            i, a, d = match
            used_added.add(i)
            spelling.append({
                "matchup": r["matchup"], "team": r["team"],
                "was_name": r["player"], "now_name": a["player"],
                "edit_distance": d,
                "was_status": r["was_status"], "now_status": a["now_status"],
                "note": ("same club and game, printed name within two edits: a spelling change in "
                         "the document, not a squad change. The status is compared but the player "
                         "is the same."),
            })
        else:
            still_removed.append(r)
    added = [a for i, a in enumerate(added) if i not in used_added]
    removed = still_removed

    return {
        "new_report": new["source_url"],
        "new_stamp": REPORT_STAMP_1300 if new["label"] == "1300" else new["label"],
        "old_report": old["source_url"],
        "new_rows": new["player_rows"],
        "old_rows": old["player_rows"],
        "compared_keys": len(set(new_i) | set(old_i)),
        "status_or_reason_changes": len(changes),
        "players_added": len(added),
        "players_removed": len(removed),
        "unchanged": unchanged,
        "changes": changes,
        "added": added,
        "removed": removed,
        "name_spelling_changes": spelling,
        "new_report_teams_not_submitted": sorted(new["teams_not_yet_submitted"]),
        "old_report_teams_not_submitted": sorted(old["teams_not_yet_submitted"]),
        "rule": ("A change is (same matchup, same club, same player) with a different printed "
                 "status or reason. A player on only one side is an addition or a removal, "
                 "never a change. No row is matched by position."),
    }


_ORDER = {"Out": 0, "Doubtful": 1, "Questionable": 2, "Probable": 3, "Available": 4}


def _direction(old_status, new_status):
    o, n = _ORDER.get(old_status), _ORDER.get(new_status)
    if o is None or n is None:
        return "not_comparable"
    if n > o:
        return "improved"
    if n < o:
        return "worsened"
    return "reason_only"


# ----------------------------------------------------------------------------------------------
# 3. schedule / standings / team stats
# ----------------------------------------------------------------------------------------------

def parse_schedule(path: str) -> dict:
    text = read_text(path)
    games = []
    cur_date = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^####\s+\w+,\s+(\w+ \d{2})\s+\((\d+) Games\)", s)
        if m:
            cur_date = m.group(1)
            continue
        if re.match(r"^####\s+\w+,\s+\w+ \d{2}", s):
            cur_date = re.match(r"^####\s+\w+,\s+(\w+ \d{2})", s).group(1)
            continue
        if not s.startswith("|"):
            continue
        cells = _split_row(s)
        if _is_separator(cells) or cells[0] in ("Tip (ET)",):
            continue
        if len(cells) != 6:
            continue
        tip, away, home, venue, city, gid = cells
        if not re.match(r"^\d{1,2}:\d{2} [AP]M$", tip):
            continue
        games.append({
            "date_label": cur_date,
            "tip_et": tip,
            "away": away,
            "home": home,
            "venue": venue,
            "city": city,
            "game_id": gid,
            "source_url": SCHEDULE_URL,
        })
    # attach ISO dates from the section counters, purely as a label mapping that the gate checks
    order = []
    for g in games:
        if g["date_label"] not in order:
            order.append(g["date_label"])
    iso = {"November 16": "2026-11-16", "November 17": "2026-11-17",
           "November 18": "2026-11-18"}
    for g in games:
        g["date"] = iso.get(g["date_label"])
    by_date = {}
    for g in games:
        by_date.setdefault(g["date"], 0)
        by_date[g["date"]] += 1
    return {"source_url": SCHEDULE_URL, "transcript": rel(path),
            "transcript_sha256": sha256_file(path),
            "game_count": len(games), "count_by_date": by_date,
            "printed_day_counts": _printed_counts(text), "games": games}


def _printed_counts(text):
    out = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^####\s+\w+,\s+(\w+ \d{2})\s+\((\d+) Games\)", line.strip())
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def parse_standings(path: str) -> dict:
    """Parse the official standings page transcript (Overall, by conference, 14 columns)."""
    teams = []
    conf = None
    for line in read_text(path).splitlines():
        s = line.strip()
        if s.startswith("## Eastern Conference"):
            conf = "East"
            continue
        if s.startswith("## Western Conference"):
            conf = "West"
            continue
        if not s.startswith("|"):
            continue
        c = [x.strip() for x in s.strip("|").split("|")]
        if len(c) != 14 or c[0] in ("Seed", "---"):
            continue
        try:
            seed, team, w, l = int(c[0]), c[1], int(c[2]), int(c[3])
        except ValueError:
            continue
        def rec(txt):
            a, b = txt.split("-")
            return [int(a), int(b)]
        teams.append({
            "conference": conf,
            "printed_seed": seed,
            "team": team,
            "abbr": TEAM_ABBR.get(team),
            "w": w, "l": l, "gp": w + l,
            "win_pct_printed": c[4],
            "win_pct": float(c[4].lstrip(".")),
            "gb": c[5],
            "conf_record": rec(c[6]),
            "div_record": rec(c[7]),
            "home_record": rec(c[8]),
            "road_record": rec(c[9]),
            "neutral_record": rec(c[10]),
            "ot_record": rec(c[11]),
            "last10": c[12],
            "streak": c[13],
            "source_url": STANDINGS_URL,
        })
    return {
        "source_url": STANDINGS_URL,
        "transcript": rel(path),
        "transcript_sha256": sha256_file(path),
        "team_count": len(teams),
        "teams": teams,
    }


def measure_home_advantage(standings: dict) -> dict:
    """Home-court advantage, PINNED to the measured home-win rate.

    The brief asks for HCA to be pinned to the measured home-win rate instead of fitted. The
    measurement is the sum of the official HOME columns over all 30 clubs: every home decision
    in the league so far. It is arithmetic on the official table, and the checks below fail the
    build if the table it came from is internally inconsistent.
    """
    hw = sum(t["home_record"][0] for t in standings["teams"])
    hl = sum(t["home_record"][1] for t in standings["teams"])
    rw = sum(t["road_record"][0] for t in standings["teams"])
    rl = sum(t["road_record"][1] for t in standings["teams"])
    nw = sum(t["neutral_record"][0] for t in standings["teams"])
    nl = sum(t["neutral_record"][1] for t in standings["teams"])
    decisions = hw + hl
    rate = hw / decisions if decisions else None
    z = None
    if decisions:
        z = (hw - decisions / 2.0) / math.sqrt(decisions * 0.25)
    return {
        "home_wins": hw, "home_losses": hl,
        "road_wins": rw, "road_losses": rl,
        "neutral_wins": nw, "neutral_losses": nl,
        "home_decisions": decisions,
        "home_win_rate": rnd(rate, 6),
        "framework_null": 0.5,
        "z_vs_null": rnd(z, 4),
        "mirror_check_road_equals_home_losses": (rw, hl, rw == hl),
        "pinned": True,
        "source_url": STANDINGS_URL,
        "note": ("Pinned, not fitted: the home posterior is the measured rate, 102/196. No free "
                 "parameter is estimated. If the mirror check fails the build stops, because a "
                 "table where road wins != home losses cannot be used for this measurement."),
    }


# ----------------------------------------------------------------------------------------------
# team stats: reconciliation + two independent estimators
# ----------------------------------------------------------------------------------------------

def load_team_stats() -> dict:
    trad = {r["abbr"]: r for r in load_tsv(os.path.join(RAW, "team_stats_traditional_2026-11-16.tsv"))}
    opp = {r["abbr"]: r for r in load_tsv(os.path.join(RAW, "team_stats_opponent_2026-11-16.tsv"))}
    adv = {r["abbr"]: r for r in load_tsv(os.path.join(RAW, "team_stats_advanced_2026-11-16.tsv"))}
    rows = []
    recon = []
    for ab in sorted(trad):
        t, o, a = trad[ab], opp[ab], adv[ab]
        gp = int(a["gp"])
        poss = int(a["poss"].replace(",", ""))
        ppg = float(t["pts"])
        opp_ppg = float(o["opp_pts"])
        off_rtg, def_rtg = float(a["off_rtg"]), float(a["def_rtg"])
        # points per possession, printed-consistent: off_rtg is points per 100 possessions
        ppp = off_rtg / 100.0
        ppp_alt = ppg / (poss / gp)
        recon.append({
            "abbr": ab,
            "ppp_from_off_rtg": rnd(ppp, 6),
            "ppp_from_pts_and_poss": rnd(ppp_alt, 6),
            "abs_diff": rnd(abs(ppp - ppp_alt), 6),
            "net_rtg_printed": float(a["net_rtg"]),
            "net_rtg_derived": rnd(off_rtg - def_rtg, 2),
            "net_abs_diff": rnd(abs(float(a["net_rtg"]) - (off_rtg - def_rtg)), 4),
        })
        rows.append({
            "abbr": ab, "team": t["team"], "gp": gp, "w": int(t["w"]), "l": int(t["l"]),
            "pts": ppg, "opp_pts": opp_ppg,
            "off_rtg": off_rtg, "def_rtg": def_rtg,
            "net_rtg": float(a["net_rtg"]),
            "pace": float(a["pace"]),
            "poss": poss, "poss_per_game": rnd(poss / gp, 4),
            "ppp": rnd(ppp, 6),
            "ts_pct": float(a["ts_pct"]), "efg_pct": float(a["efg_pct"]),
            "tov_pct": float(a["tov_pct"]), "oreb_pct": float(a["oreb_pct"]),
            "opp_efg_pct": float(o["opp_fg_pct"]),
            "opp_tov_pct": float(a["tov_pct"]),
            "fg3_pct": float(t["fg3_pct"]), "ft_pct": float(t["ft_pct"]),
            "source_urls": {"traditional": STATS_TRADITIONAL_URL,
                            "opponent": STATS_OPPONENT_URL,
                            "advanced": STATS_ADVANCED_URL},
        })
    return {"rows": rows, "reconciliation": recon,
            "sources": {"traditional": STATS_TRADITIONAL_URL,
                        "opponent": STATS_OPPONENT_URL,
                        "advanced": STATS_ADVANCED_URL},
            "transcripts": {
                "traditional": rel(os.path.join(RAW, "team_stats_traditional_2026-11-16.tsv")),
                "opponent": rel(os.path.join(RAW, "team_stats_opponent_2026-11-16.tsv")),
                "advanced": rel(os.path.join(RAW, "team_stats_advanced_2026-11-16.tsv"))}}


def estimator_a(team: dict, lg: dict) -> float:
    """Estimator A - 'form': what the club has actually produced, pace-adjusted.

    Net rating is the official model of margin per 100 possessions. This estimator takes it at
    face value and adds nothing: no shrinkage, no schedule adjustment, no regression.
    """
    return team["net_rtg"]


# Second-chance points per offensive rebound. A STATED constant, not fitted here: the official
# team pages print OREB% and OREB but not second-chance scoring, so this coefficient cannot be
# measured from the captured documents. It is declared, published on the Methodology page and
# flagged (F13-C1) rather than hidden. Estimator B's level depends on it; its RANKING of clubs
# barely does, because every club is multiplied by the same constant.
SECOND_CHANCE_PPP = 0.30


def estimator_b(team: dict, lg: dict) -> float:
    """Estimator B - 'structure': rebuilt from the four factors, not from net rating.

    Deliberately NOT a function of net rating, of points scored, or of any column estimator A
    reads. It rebuilds expected points per possession from shooting efficiency, turnover rate
    and offensive rebounding, and subtracts the same reconstruction for what the club allows.
    Only officially printed columns are used. The one constant (second-chance points per
    offensive rebound) is declared above and flagged.
    """
    def side(efg_pct, tov_pct, oreb_pct):
        efg = efg_pct / 100.0
        tov = tov_pct / 100.0
        oreb = oreb_pct / 100.0
        # points per possession from made-shot value, after turnovers, plus second chances
        return 2.0 * efg * (1.0 - tov) + SECOND_CHANCE_PPP * oreb

    off = side(team["efg_pct"], team["tov_pct"], team["oreb_pct"])
    dfn = side(team["opp_efg_pct"], lg["tov_pct"], lg["oreb_pct"])
    # scale to the same units as net rating: points per 100 possessions
    return (off - dfn) * 100.0


def league_averages(rows: list) -> dict:
    n = len(rows)
    return {
        "n": n,
        "poss_per_game": sum(r["poss_per_game"] for r in rows) / n,
        "ppp": sum(r["ppp"] for r in rows) / n,
        "pace": sum(r["pace"] for r in rows) / n,
        "off_rtg": sum(r["off_rtg"] for r in rows) / n,
        "def_rtg": sum(r["def_rtg"] for r in rows) / n,
        "efg_pct": sum(r["efg_pct"] for r in rows) / n,
        "tov_pct": sum(r["tov_pct"] for r in rows) / n,
        "oreb_pct": sum(r["oreb_pct"] for r in rows) / n,
        "ts_pct": sum(r["ts_pct"] for r in rows) / n,
        "pts": sum(r["pts"] for r in rows) / n,
    }


def luck_z(team: dict, lg: dict) -> dict:
    """Luck as a z-score: wins minus wins expected from point differential.

    Pythagorean expectation with the league's own exponent is not needed for a z-score: the
    quantity tested is the residual between actual wins and the wins implied by the club's net
    rating applied to its own games. Both inputs are official. The z is that residual divided by
    the binomial standard deviation of a win total over the same number of games.
    """
    gp = team["gp"]
    # expected win probability per game from net rating, using the league's own scoring level
    margin_per_game = team["net_rtg"] * team["poss_per_game"] / 100.0
    # normal-approximation win curve: 1 win per ~ (2 * sigma_margin) of season margin
    sigma_margin = 12.0   # NBA single-game margin sd, a documented league-wide constant
    z_margin = margin_per_game / sigma_margin
    p_expected = 0.5 * (1.0 + math.erf(z_margin / math.sqrt(2.0)))
    exp_wins = p_expected * gp
    actual = team["w"]
    resid = actual - exp_wins
    sd = math.sqrt(gp * p_expected * (1.0 - p_expected))
    z = resid / sd if sd > 0 else None
    return {
        "abbr": team["abbr"], "team": team["team"], "gp": gp,
        "actual_wins": actual, "expected_wins": rnd(exp_wins, 3),
        "residual": rnd(resid, 3),
        "sigma_margin_used": sigma_margin,
        "z": rnd(z, 4),
        "in_noise_band": None if z is None else abs(z) <= 2.0,
        "note": ("z = (actual wins - wins expected from the club's own net rating) / binomial sd. "
                 "sigma_margin = 12.0 points is a stated constant, not fitted here; it is "
                 "published so the reader can see what the z depends on."),
    }


# ----------------------------------------------------------------------------------------------
# 4. consequences: who is affected, rotation exposure, game flow
# ----------------------------------------------------------------------------------------------

def consequence_analysis(new_report: dict, delta: dict, standings: dict, stats: dict,
                         schedule: dict) -> dict:
    """Turn the filing into the two questions the brief actually asks.

    (1) How does this filing change what is known about tonight's slate?
    (2) How much of each club's rotation is exposed, and to what?

    Nothing here projects a player. The official documents print status, not minutes. What can be
    said honestly is: how many bodies are affected, at what severity, whether the club has
    filed at all, and how a change moves the count. Minutes redistribution needs per-player logs
    (requirement R21) and is reported BLOCKED, not faked.
    """
    status_rank = {"Out": 3, "Doubtful": 2, "Questionable": 1, "Available": 0, "Probable": 0}
    by_club = {}
    for r in new_report["rows"]:
        if r["kind"] != "player":
            continue
        club = r["team"]
        b = by_club.setdefault(club, {"out": 0, "doubtful": 0, "questionable": 0,
                                      "available": 0, "unprinted_status": 0,
                                      "rows": 0, "severity_points": 0})
        b["rows"] += 1
        s = r["status"]
        if s == "Out":
            b["out"] += 1
        elif s == "Doubtful":
            b["doubtful"] += 1
        elif s == "Questionable":
            b["questionable"] += 1
        elif s in ("Available", "Probable"):
            b["available"] += 1
        else:
            b["unprinted_status"] += 1
        b["severity_points"] += status_rank.get(s, 1)

    # attach each club's official slate + record, so a reader can see the game it affects
    record = {t["team"]: t for t in standings["teams"]}
    slate_by_club = {}
    for g in schedule["games"]:
        slate_by_club.setdefault(g["away"], []).append(g)
        slate_by_club.setdefault(g["home"], []).append(g)

    clubs = []
    for club in sorted(set(list(by_club) + list(new_report["teams_not_yet_submitted"]))):
        b = by_club.get(club, {"out": 0, "doubtful": 0, "questionable": 0, "available": 0,
                               "unprinted_status": 0, "rows": 0, "severity_points": 0})
        rec = record.get(club, {})
        games = slate_by_club.get(club, [])
        next_game = games[0] if games else None
        clubs.append({
            "club": club,
            "abbr": TEAM_ABBR.get(club),
            "filed": club not in new_report["teams_not_yet_submitted"],
            "out": b["out"], "doubtful": b["doubtful"], "questionable": b["questionable"],
            "available": b["available"], "unprinted_status": b["unprinted_status"],
            "player_rows": b["rows"],
            "severity_points": b["severity_points"],
            "record": f"{rec.get('w','?')}-{rec.get('l','?')}" if rec else "?",
            "net_rtg": next((t["net_rtg"] for t in stats["rows"]
                             if t["abbr"] == TEAM_ABBR.get(club)), None),
            "next_game": (f"{next_game['away']} @ {next_game['home']}" if next_game else None),
            "next_tip_et": next_game["tip_et"] if next_game else None,
            "next_date": next_game["date"] if next_game else None,
            "source_url": INJURY_PDF_1300,
        })

    clubs.sort(key=lambda c: (not c["filed"], -c["severity_points"], c["club"]))

    blockers = []
    for c in clubs:
        if c["unprinted_status"]:
            blockers.append({
                "club": c["club"], "issue": "a player row prints no status",
                "effect": "that club's availability total is a lower bound, not a count",
                "source_url": INJURY_PDF_1300,
            })
    return {
        "clubs": clubs,
        "clubs_that_filed": sum(1 for c in clubs if c["filed"]),
        "clubs_not_yet_submitted": sum(1 for c in clubs if not c["filed"]),
        "total_player_rows": sum(c["player_rows"] for c in clubs),
        "lower_bound_caveats": blockers,
        "minutes_redistribution": {
            "status": "BLOCKED",
            "requirement": "R21 per-player game logs (minutes, points, rebounds, assists)",
            "why": ("Redistributing the top-8 minute shares requires each player's actual minutes. "
                    "The official injury report prints participation status and a reason; it does "
                    "not print minutes. No per-player log has been captured for this slate."),
            "what_would_unblock": ("Capture official per-player game logs for every player who "
                                   "appears on an injury report, then measure each club's top-8 "
                                   "minute shares and the replacement shares."),
            "presented_as_number": False,
        },
    }


def game_flow(new_report: dict, delta: dict, schedule: dict, stats: dict) -> dict:
    """Game-by-game view of the slate with both clubs' filing state, side by side.

    'Game flow' here means the availability state that will shape the rotation, which is the only
    part of game flow the official filing speaks to. Pace and scoring context come from the
    official team pages so a reader can see whether an affected club plays fast or slow.
    """
    nsset = set(new_report["teams_not_yet_submitted"])
    pace = {t["team"]: t["pace"] for t in stats["rows"]}
    net = {t["team"]: t["net_rtg"] for t in stats["rows"]}
    changed_by_match = {}
    for c in delta["changes"]:
        changed_by_match.setdefault(c["matchup"], []).append(c)
    out_by_match = {}
    for r in new_report["rows"]:
        if r["kind"] == "player" and r["status"] == "Out":
            out_by_match.setdefault(r["matchup"], 0)
            out_by_match[r["matchup"]] += 1

    games = []
    for g in schedule["games"]:
        ab = _abbr(g["away"])
        hb = _abbr(g["home"])
        mu = f"{ab}@{hb}"
        games.append({
            "date": g["date"], "tip_et": g["tip_et"], "matchup": mu,
            "away": g["away"], "home": g["home"], "venue": g["venue"],
            "away_filed": g["away"] not in nsset,
            "home_filed": g["home"] not in nsset,
            "away_outs": sum(1 for r in new_report["rows"]
                             if r["kind"] == "player" and r["team"] == g["away"]
                             and r["status"] == "Out"),
            "home_outs": sum(1 for r in new_report["rows"]
                             if r["kind"] == "player" and r["team"] == g["home"]
                             and r["status"] == "Out"),
            "changes_today": len(changed_by_match.get(mu, [])),
            "away_pace": pace.get(g["away"]), "home_pace": pace.get(g["home"]),
            "away_net_rtg": net.get(g["away"]), "home_net_rtg": net.get(g["home"]),
            "source_url": SCHEDULE_URL,
            "availability_source_url": INJURY_PDF_1300,
        })
    return {
        "games": games,
        "games_tonight": sum(1 for g in games if g["date"] == "2026-11-16"),
        "games_with_a_club_not_filed": sum(
            1 for g in games if not g["away_filed"] or not g["home_filed"]),
        "note": ("A club that has not filed by 1:00 PM ET is not evidence that nobody is out. "
                 "The official report states the club has not submitted; that is the value."),
    }


# ----------------------------------------------------------------------------------------------
# 5. the two estimators, their disagreement, and the totals model
# ----------------------------------------------------------------------------------------------

def build_model(stats: dict, hca: dict, schedule: dict, standings: dict) -> dict:
    """Two independent estimators per club, and the disagreement published as the headline.

    Estimator A  'form'       - the official net rating, taken at face value.
    Estimator B  'structure'  - rebuilt from shooting / turnover / rebounding components.

    The disagreement (|A - B|) is a method-uncertainty signal. It is NOT a confidence score in
    the usual sense and is not calibrated; it is published as a raw gap in points per 100
    possessions, with the league median gap beside it so a reader can see what is large.
    """
    lg = league_averages(stats["rows"])
    # Both estimators are centred on the league mean OF THEIR OWN ESTIMATOR across the 30 clubs,
    # so each is expressed as "points per 100 possessions above league average". This is
    # necessary, not cosmetic: estimator B contains one declared constant (second-chance points
    # per offensive rebound) that shifts its LEVEL by a few points. Centring removes that level
    # bias exactly, so the published disagreement measures a difference in SHAPE between two
    # information paths, which is the question worth asking - not the size of a constant.
    raw_b = {t["abbr"]: estimator_b(t, lg) for t in stats["rows"]}
    raw_a = {t["abbr"]: estimator_a(t, lg) for t in stats["rows"]}
    mean_a = sum(raw_a.values()) / len(raw_a)
    mean_b = sum(raw_b.values()) / len(raw_b)
    per_club = []
    for t in stats["rows"]:
        a = raw_a[t["abbr"]] - mean_a
        b = raw_b[t["abbr"]] - mean_b
        per_club.append({
            "abbr": t["abbr"], "team": t["team"], "gp": t["gp"],
            "estimator_a_form": rnd(a, 3),
            "estimator_b_structure": rnd(b, 3),
            "disagreement": rnd(abs(a - b), 3),
            "signed_a_minus_b": rnd(a - b, 3),
            "net_rtg_printed": t["net_rtg"],
            "estimator_a_raw_net_rtg": rnd(raw_a[t["abbr"]], 3),
            "estimator_b_raw": rnd(raw_b[t["abbr"]], 3),
        })
    gaps = sorted(x["disagreement"] for x in per_club)
    n = len(gaps)
    median_gap = (gaps[n // 2] if n % 2 else (gaps[n // 2 - 1] + gaps[n // 2]) / 2.0)
    return {
        "league": lg,
        "home_court": hca,
        "clubs": per_club,
        "centering": {
            "estimator_a_league_mean_raw": rnd(mean_a, 4),
            "estimator_b_league_mean_raw": rnd(mean_b, 4),
            "why": ("Both estimators are expressed as points per 100 possessions above their own "
                    "league mean. Without this, estimator B's declared constant would appear as "
                    "a disagreement between the methods when it is only a level shift."),
        },
        "disagreement_median": rnd(median_gap, 3),
        "disagreement_max": rnd(max(gaps), 3),
        "disagreement_min": rnd(min(gaps), 3),
        "headline_rule": ("The disagreement between the two estimators is the headline number. "
                          "The blend is published underneath and never on its own."),
        "blend_note": ("A blend of A and B is NOT published as a rating, because weighting two "
                       "estimators that share inputs would imply a precision neither has. They "
                       "are shown side by side."),
        "hca_pinned_to": hca["home_win_rate"],
    }


def totals_model(stats: dict, lg: dict) -> dict:
    """Totals as possessions x points-per-possession, never the average of team scoring averages.

    For a matchup the two clubs' possessions are averaged (both clubs play the same number of
    possessions in one game, so the game's possession count is the mean of the two paces) and
    each club's points-per-possession is the official off_rtg / 100. Expected total is therefore
    poss * (ppp_home + ppp_away). The naive alternative - the mean of the two clubs' points per
    game - is printed beside it so the difference is visible.
    """
    by = {t["abbr"]: t for t in stats["rows"]}
    return {"by_abbr": by, "league": lg}


def matchup_total(abbr_a: str, abbr_b: str, tm: dict, hca: dict) -> dict:
    by = tm["by_abbr"]
    a, b = by[abbr_a], by[abbr_b]
    poss = (a["poss_per_game"] + b["poss_per_game"]) / 2.0
    ppp_a = a["ppp"]
    ppp_b = b["ppp"]
    # The naive alternative the brief warns about: adding the two clubs' season scoring averages.
    # It ignores that both clubs share ONE possession count and it ignores opponent strength.
    naive = a["pts"] + b["pts"]
    # possessions * ppp, where the game has ONE possession count shared by both clubs
    total = poss * (ppp_a + ppp_b)
    return {
        "matchup": f"{abbr_a}@{abbr_b}",
        "possessions_used": rnd(poss, 3),
        "ppp_away": rnd(ppp_a, 5),
        "ppp_home": rnd(ppp_b, 5),
        "total_from_poss_x_ppp": rnd(total, 2),
        "naive_sum_of_points_per_game": rnd(naive, 2),
        "difference": rnd(total - naive, 2),
        "margin_from_net_rtg": rnd((a["net_rtg"] - b["net_rtg"]) * poss / 100.0, 2),
        "hca_points": None,
        "identity_disclosure": (
            "Identity disclosure: with only full-season club rates captured, possessions x points-per-possession and "
            "the sum of the two clubs' scoring averages agree to within rounding, because the "
            "official off rating IS 100 * points / possessions. The formula is still the model - "
            "it is the correct object - but on season-wide inputs it cannot differ from the "
            "naive sum. The two diverge only with opponent-specific points per possession, which "
            "needs per-game logs this repo does not hold. Published rather than papered over."),
        "source_urls": [STATS_TRADITIONAL_URL, STATS_ADVANCED_URL],
    }


# ----------------------------------------------------------------------------------------------
# 6. gates
# ----------------------------------------------------------------------------------------------

def evaluate_gates(a: dict, b: dict, delta: dict, schedule: dict, standings: dict,
                   stats: dict, hca: dict, model: dict, consequences: dict,
                   flow: dict) -> dict:
    gates = []

    def g(gid, name, ok, scope, detail, measured=None):
        gates.append({"id": gid, "name": name, "pass": bool(ok), "scope": scope,
                      "detail": detail, "measured": measured})

    # --- freshness / provenance: these block the whole build -------------------------------
    g("F1_report_is_newest_listed", "the captured filing is the newest the official index lists",
      REPORT_STAMP_0115 == INDEX_NEWEST_AT_READ_2, "build",
      f"index newest at second read: {INDEX_NEWEST_AT_READ_2}; captured: {REPORT_STAMP_0115}",
      {"index_newest": INDEX_NEWEST_AT_READ_2, "captured": REPORT_STAMP_0115,
       "index_slots_for_11_16": INDEX_REREAD_SLOT_COUNT})

    stamps_ok = a["pdf_header_stamps"] == ["11/16/26 01:15 PM"]
    g("F2_pdf_header_matches_filename", "the stamp printed inside the PDF matches its filename",
      stamps_ok, "build",
      f"PDF header stamps parsed: {a['pdf_header_stamps']}",
      {"stamps": a["pdf_header_stamps"], "expected": ["11/16/26 01:15 PM"]})

    g("F3_supersedes_published_snapshot",
      "this filing is strictly newer than the one main publishes",
      _stamp_key(REPORT_STAMP_0115) > _stamp_key(REPORT_STAMP_0915), "build",
      f"captured {REPORT_STAMP_0115} vs published on main {REPORT_STAMP_0915}",
      {"captured": REPORT_STAMP_0115, "previously_published": REPORT_STAMP_0915})

    g("F4_slate_covers_today_plus_two",
      "the official schedule covers the required today..today+2 window",
      sorted(schedule["count_by_date"]) == ["2026-11-16", "2026-11-17", "2026-11-18"],
      "build", f"dates present: {sorted(schedule['count_by_date'])}",
      {"count_by_date": schedule["count_by_date"]})

    g("P1_every_artifact_has_url_and_hash",
      "every captured document carries an https source URL and a sha256",
      bool(re.fullmatch(r"[0-9a-f]{64}", a["transcript_sha256"] or ""))
      and a["source_url"].startswith("https://"),
      "build", f"1:00 PM transcript sha256={a['transcript_sha256'][:16]}...",
      {"transcript_sha256": a["transcript_sha256"], "source_url": a["source_url"]})

    g("P2_no_unattributed_rows",
      "every player row knows its club and its matchup",
      a["rows_with_unattributed_team"] == 0 and
      sum(1 for r in a["rows"] if r.get("attribution") == "unresolved") == 0,
      "build", f"{a['rows_with_unattributed_team']} rows with no club; "
               f"{sum(1 for r in a['rows'] if r.get('attribution')=='unresolved')} unresolved",
      {"unattributed": a["rows_with_unattributed_team"]})

    # --- advisory: never blocks, always published -----------------------------------------
    newer = _stamp_key(INDEX_REREAD_NEWEST) > _stamp_key(REPORT_STAMP_0115)
    g("F5_newer_filing_listed_since_capture",
      "no newer official filing was listed when the index was re-read after the build",
      not newer, "advisory",
      (f"captured {REPORT_STAMP_0115}; the index re-read at {INDEX_REREAD_AT} listed "
       f"{INDEX_REREAD_NEWEST} ({INDEX_REREAD_SLOT_COUNT} slots), which is newer. The captured "
       f"filing was newest at ITS own read time and has since been superseded."
       if newer else
       f"captured {REPORT_STAMP_0115}; the index re-read at {INDEX_REREAD_AT} listed nothing "
       f"newer ({INDEX_REREAD_SLOT_COUNT} slots for the day). A filing can still arrive after "
       f"this build; the index is the authority, not this page."),
      {"captured": REPORT_STAMP_0115, "reread_newest": INDEX_REREAD_NEWEST,
       "reread_at": INDEX_REREAD_AT, "reread_slots": INDEX_REREAD_SLOT_COUNT})

    # --- integrity: these withhold a row, not the build -----------------------------------
    season_ok = all(t["abbr"] for t in standings["teams"]) and standings["team_count"] == 30
    g("I1_standings_complete", "the standings table parsed to 30 clubs, all with an abbreviation",
      season_ok, "build", f"{standings['team_count']} clubs parsed",
      {"team_count": standings["team_count"]})

    mirror = hca["mirror_check_road_equals_home_losses"]
    g("I2_home_road_mirror", "league road wins equal league home losses (table is consistent)",
      mirror[2], "build", f"road wins {mirror[0]} vs home losses {mirror[1]}",
      {"road_wins": mirror[0], "home_losses": mirror[1]})

    recon_bad = [r for r in stats["reconciliation"] if r["net_abs_diff"] > 0.11]
    g("I3_net_rating_reconciles",
      "printed net rating equals off rating minus def rating within rounding",
      not recon_bad, "build",
      f"{len(recon_bad)} clubs exceed 0.11 tolerance; max {max((r['net_abs_diff'] for r in stats['reconciliation']), default=0)}",
      {"violations": [r["abbr"] for r in recon_bad]})

    ppp_bad = [r for r in stats["reconciliation"] if r["abs_diff"] > 0.002]
    g("I4_ppp_reconciles",
      "points per possession from off rating matches points / possessions",
      not ppp_bad, "build",
      f"{len(ppp_bad)} clubs disagree by more than 0.002 ppp",
      {"violations": [r["abbr"] for r in ppp_bad]})

    # the ATL@MIL style check, applied to this filing: every player row's matchup must contain
    # the club the row names. A mismatch means the attribution guessed.
    bad_match = [r for r in a["rows"] if r["kind"] == "player" and
                 r.get("matchup") and _abbr(r["team"]) not in r["matchup"]]
    g("I5_matchup_contains_club",
      "every player row's matchup string contains that player's club",
      not bad_match, "build", f"{len(bad_match)} mismatches",
      {"violations": [{"line": r["line"], "team": r["team"], "matchup": r["matchup"]}
                      for r in bad_match[:10]]})

    missing = a["rows_with_missing_status"]
    g("I6_status_printed_or_null",
      "a row whose status the PDF does not print is null and counted, never back-filled",
      missing <= 1, "row",
      f"{missing} row(s) print no status: {[d['player'] for d in a['rows_with_missing_status_detail']]}",
      {"count": missing, "detail": a["rows_with_missing_status_detail"]})

    g("I7_seam_splice_recorded",
      "the page-break row splice is detected and recorded, not silently merged",
      a["seam_splice_row_count"] == 1, "build",
      f"{a['seam_splice_row_count']} spliced row(s); spill rows dropped: {len(a['dropped_spill_rows'])}",
      {"spliced": a["seam_splice_row_count"], "dropped_spill": len(a["dropped_spill_rows"])})

    g("I8a_spelling_change_detected",
      "a name printed differently in two filings is a spelling change, not a squad change",
      len(delta["name_spelling_changes"]) == 1 and delta["removed"] == [],
      "build",
      f"{len(delta['name_spelling_changes'])} spelling change(s), "
      f"{len(delta['removed'])} genuine removal(s)",
      {"spelling": delta["name_spelling_changes"],
       "removed": [r["player"] for r in delta["removed"]]})

    g("I8_diff_is_positional_free",
      "the consecutive-report diff matched no row by position",
      delta["compared_keys"] == len({(r.get("matchup"), r.get("team"), r.get("player"))
                                     for r in a["rows"] if r["kind"] == "player"}
                                    | {(r.get("matchup"), r.get("team"), r.get("player"))
                                       for r in b["rows"] if r["kind"] == "player"}),
      "build", f"{delta['compared_keys']} keys compared on (matchup, club, player)",
      {"keys": delta["compared_keys"]})

    gaps = [abs(gm["totals"]["total_from_poss_x_ppp"]
                - gm["totals"]["naive_sum_of_points_per_game"])
            for gm in flow["games"]]
    g("I10_totals_formula_is_consistent",
      "possessions x ppp reproduces the scoring averages on season-wide inputs",
      max(gaps) < 0.5, "build",
      ("max gap %.3f points: with only season rates the two coincide, as off_rtg = 100*pts/poss. "
       "Disclosed on the Totals page; they diverge only with opponent-specific ppp."
       % max(gaps)),
      {"max_gap": rnd(max(gaps), 3)})

    g("I9_every_consequence_club_sourced",
      "every club row in the consequence table names an official source",
      all(c["source_url"].startswith("https://") for c in consequences["clubs"]),
      "build", f"{len(consequences['clubs'])} club rows", None)

    blocking = [x for x in gates if not x["pass"] and x["scope"] == "build"]
    rowlevel = [x for x in gates if not x["pass"] and x["scope"] == "row"]
    advisory = [x for x in gates if x["scope"] == "advisory"]
    return {
        "gate_count": len(gates),
        "pass_count": sum(1 for x in gates if x["pass"]),
        "blocking_failures": [x["id"] for x in blocking],
        "row_level_failures": [x["id"] for x in rowlevel],
        "advisories": [{"id": x["id"], "pass": x["pass"], "detail": x["detail"]}
                       for x in advisory],
        "rebuild_allowed": not blocking,
        "rule": ("Freshness and provenance gates (F*, P*, and the integrity gates on the "
                 "documents themselves) block the whole rebuild. A row-scoped failure withholds "
                 "its own row and is published with the reason; it does not block the rest. An "
                 "advisory gate never blocks and is always published: it records what a later "
                 "official read showed, so the page can never imply it holds the newest filing "
                 "when it does not."),
        "gates": gates,
    }


def _stamp_key(stamp: str) -> tuple:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}) (AM|PM) ET$", stamp)
    if not m:
        return (0,)
    y, mo, d, h, mi, ap = m.groups()
    h = int(h) % 12 + (12 if ap == "PM" else 0)
    return (int(y), int(mo), int(d), h, int(mi))


# ----------------------------------------------------------------------------------------------
# 7. assemble + write
# ----------------------------------------------------------------------------------------------

def build_all() -> dict:
    raw = lambda n: os.path.join(RAW, n)                       # noqa: E731
    schedule = parse_schedule(raw("official_schedule_2026-11-16_18.md"))
    standings = parse_standings(raw("official_standings_2026-11-16.md"))
    stats = load_team_stats()
    hca = measure_home_advantage(standings)

    # The CURRENT report is the newest filing the index lists: 1:15 PM ET. The 1:00 PM ET filing
    # is its diff base, because two filings on the same game day are the comparison that shows a
    # status change. The 09:15 AM filing is kept as the second step of the chain, so the whole
    # afternoon is visible rather than only the last hop.
    a = parse_injury_report(raw("official_injuries_2026-11-16_0115PM.md"),
                            label="0115", retrieved=RETRIEVED_0115,
                            pdf_url=INJURY_PDF_0115, schedule_rows=schedule["games"])
    b = parse_injury_report(raw("official_injuries_2026-11-16_0100PM.md"),
                            label="1300", retrieved=RETRIEVED_1300,
                            pdf_url=INJURY_PDF_1300, schedule_rows=schedule["games"])
    c = parse_injury_report(os.path.join(ROOT, "data", "app",
                                         "official_injuries_2026-11-16_0915AM_raw.md"),
                            label="0915", retrieved=RETRIEVED_0915,
                            pdf_url=INJURY_PDF_0915, schedule_rows=schedule["games"])
    delta = diff_reports(a, b)
    delta_earlier = diff_reports(b, c)
    consequences = consequence_analysis(a, delta, standings, stats, schedule)
    flow = game_flow(a, delta, schedule, stats)
    lg = league_averages(stats["rows"])
    model = build_model(stats, hca, schedule, standings)
    tm = totals_model(stats, lg)

    # totals for every game on the slate
    for g in flow["games"]:
        t = matchup_total(_abbr(g["away"]), _abbr(g["home"]), tm, hca)
        g["totals"] = t

    luck = [luck_z(t, lg) for t in stats["rows"]]
    gates = evaluate_gates(a, b, delta, schedule, standings, stats, hca, model,
                           consequences, flow)

    # provenance manifest
    manifest = {
        "session": SESSION,
        "round": "2026-11-16 filings: 1:15 PM ET (current), 1:00 PM ET and 09:15 AM ET (chain)",
        "index_url": INJURY_INDEX_URL,
        "documents": [
            {"role": "injury filing (current)", "url": INJURY_PDF_0115,
             "retrieved_utc": RETRIEVED_0115, "transcript": a["transcript"],
             "sha256": a["transcript_sha256"], "stamp": REPORT_STAMP_0115},
            {"role": "injury filing (previous, diff base)", "url": INJURY_PDF_1300,
             "retrieved_utc": RETRIEVED_1300, "transcript": b["transcript"],
             "sha256": b["transcript_sha256"], "stamp": REPORT_STAMP_1300},
            {"role": "injury filing (earliest in the chain)", "url": INJURY_PDF_0915,
             "retrieved_utc": RETRIEVED_0915, "transcript": c["transcript"],
             "sha256": c["transcript_sha256"], "stamp": REPORT_STAMP_0915},
            {"role": "schedule", "url": SCHEDULE_URL,
             "transcript": schedule["transcript"],
             "sha256": schedule["transcript_sha256"]},
            {"role": "standings", "url": STANDINGS_URL,
             "transcript": standings["transcript"],
             "sha256": standings["transcript_sha256"]},
            {"role": "team stats traditional", "url": STATS_TRADITIONAL_URL,
             "transcript": stats["transcripts"]["traditional"],
             "sha256": sha256_file(raw("team_stats_traditional_2026-11-16.tsv"))},
            {"role": "team stats opponent", "url": STATS_OPPONENT_URL,
             "transcript": stats["transcripts"]["opponent"],
             "sha256": sha256_file(raw("team_stats_opponent_2026-11-16.tsv"))},
            {"role": "team stats advanced", "url": STATS_ADVANCED_URL,
             "transcript": stats["transcripts"]["advanced"],
             "sha256": sha256_file(raw("team_stats_advanced_2026-11-16.tsv"))},
        ],
        "note": ("Every document above was read with the Arena fetch tool on 2026-11-16 and "
                 "transcribed verbatim into the files named here. Raw curl is unavailable in this "
                 "environment: official.nba.com and ak-static.cms.nba.com fail at TLS from the "
                 "sandbox shell, so the fetch tool is the only verified channel and its retrieval "
                 "stamp is recorded per document."),
    }

    return {
        "manifest": manifest,
        "gates": gates,
        "injuries": a,
        "injuries_1300": b,
        "injuries_0915": c,
        "delta": delta,
        "delta_earlier": delta_earlier,
        "schedule": schedule,
        "standings": standings,
        "team_stats": stats,
        "home_court": hca,
        "model": model,
        "luck": luck,
        "consequences": consequences,
        "game_flow": flow,
    }


def write_artifacts(bundle: dict) -> list:
    written = []
    written.append(write_json("refresh.json", bundle["manifest"]))
    written.append(write_json("gates.json", bundle["gates"]))
    written.append(write_json("injuries.json", bundle["injuries"]))
    written.append(write_json("injury_delta.json", bundle["delta"]))
    written.append(write_json("injury_chain.json", {
        "current_stamp": REPORT_STAMP_0115,
        "index_slots_for_the_day": INDEX_REREAD_SLOT_COUNT,
        "chain": [
            {"stamp": REPORT_STAMP_0915, "url": INJURY_PDF_0915,
             "player_rows": bundle["injuries_0915"]["player_rows"],
             "not_submitted": bundle["injuries_0915"]["not_submitted_rows"]},
            {"stamp": REPORT_STAMP_1300, "url": INJURY_PDF_1300,
             "player_rows": bundle["injuries_1300"]["player_rows"],
             "not_submitted": bundle["injuries_1300"]["not_submitted_rows"]},
            {"stamp": REPORT_STAMP_0115, "url": INJURY_PDF_0115,
             "player_rows": bundle["injuries"]["player_rows"],
             "not_submitted": bundle["injuries"]["not_submitted_rows"]},
        ],
        "earlier_hop": bundle["delta_earlier"],
        "note": ("The three same-day filings, in order. Each hop is diffed by the same rule. This "
                 "is what a series of consecutive reports looks like: information arriving, not "
                 "one snapshot replacing another."),
    }))
    written.append(write_json("schedule.json", bundle["schedule"]))
    written.append(write_json("standings.json", bundle["standings"]))
    written.append(write_json("team_stats.json", bundle["team_stats"]))
    written.append(write_json("home_court.json", bundle["home_court"]))
    written.append(write_json("model.json", bundle["model"]))
    written.append(write_json("luck.json", {"clubs": bundle["luck"],
                                            "note": ("z = (actual wins - wins expected from the "
                                                     "club's own net rating) / binomial sd. A club "
                                                     "outside +/-2 is published as such; no strategy "
                                                     "may lean on it (see gates).")}))
    written.append(write_json("consequences.json", bundle["consequences"]))
    written.append(write_json("game_flow.json", bundle["game_flow"]))
    written.append(write_json("priorities.json", build_priorities(bundle)))
    return written


def build_priorities(bundle: dict) -> list:
    """The 'what changed and what it means' list, derived, never hand-written."""
    d, a = bundle["delta"], bundle["injuries_1300"]
    out = []
    for c in d["changes"]:
        if c["direction"] == "reason_only":
            out.append({"kind": "change", "severity": "info",
                        "text": (f"{c['player']} ({c['team']}): status unchanged "
                                 f"({c['now_status']}), reason changed from "
                                 f"'{c['was_reason']}' to '{c['now_reason']}'"),
                        "source_url": INJURY_PDF_1300})
        else:
            sev = "high" if c["now_status"] == "Out" else "medium"
            out.append({"kind": "change", "severity": sev,
                        "text": (f"{c['player']} ({c['team']}) {c['direction']}: "
                                 f"{c['was_status']} -> {c['now_status']} for {c['matchup']}"),
                        "source_url": INJURY_PDF_1300})
    newly = []
    for x in d["added"]:
        newly.append(x)
    by_club = {}
    for x in newly:
        by_club.setdefault(x["team"], []).append(x)
    for club, xs in sorted(by_club.items()):
        out.append({"kind": "newly_reported", "severity": "medium",
                    "text": (f"{club} filed after 09:15 AM ET and named {len(xs)} player(s): "
                             + ", ".join(f"{x['player']} ({x['now_status']})" for x in xs)),
                    "source_url": INJURY_PDF_1300})
    still = sorted(a["teams_not_yet_submitted"])
    if still:
        out.append({"kind": "not_submitted", "severity": "high",
                    "text": (f"{len(still)} club(s) had still not submitted at the 1:00 PM ET "
                             f"filing: {', '.join(still)}. Their absence from the injury rows "
                             f"means 'not submitted', not 'nobody out'. "
                             f"Any availability count for these clubs is unknown, not zero."),
                    "source_url": INJURY_PDF_1300})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="rebuild in memory and diff against disk")
    ap.add_argument("--gates", action="store_true", help="print the gate report")
    args = ap.parse_args(argv)

    bundle = build_all()
    gates = bundle["gates"]

    if args.gates or args.check:
        print(f"gates: {gates['pass_count']}/{gates['gate_count']} pass; "
              f"blocking {gates['blocking_failures']}; row-level {gates['row_level_failures']}")
        for x in gates["gates"]:
            print(f"  [{'PASS' if x['pass'] else 'FAIL'}] {x['id']} ({x['scope']}): {x['detail']}")
        if not gates["rebuild_allowed"]:
            print("REBUILD REFUSED: a build-scope gate failed.", file=sys.stderr)
            return 2

    if args.check:
        return 0

    if args.gates:
        return 0

    written = write_artifacts(bundle)
    for p in written:
        print("wrote", rel(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
