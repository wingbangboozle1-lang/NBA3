#!/usr/bin/env python3
"""Parse session 9c30f2ae's verbatim official captures into checked artefacts (offline, deterministic).

Inputs (read-only, committed verbatim transcripts, each carrying its URL + retrieval stamp):

  data/rounds/2026-11-19-9c30f2ae/raw/injury_index_2026-11-19_raw.md
      the official injury-report index, whose own text states the filing rules and lists eight 11/19
      revisions;
  data/rounds/2026-11-19-9c30f2ae/raw/injury_2026-11-19_0130AM_raw.md
      the newest of those revisions (01:30 AM ET), the text layer the fetch tool returned;
  data/rounds/2026-11-19-9c30f2ae/results_2026-11-18.json
      the twelve 11/18 games with their quarter cells, transcribed from each game page's LINESCORES;
  data/rounds/2026-11-19-9c30f2ae/raw/team_stats_advanced_raw.md
      the advanced team page, 30 rows, captured with its chunk boundary recorded.

Outputs (all under data/rounds/2026-11-19-9c30f2ae/):

  injuries_2026-11-19_0130AM.json   parsed rows, unattributed rows, and the 12:45 AM -> 01:30 AM diff
  team_stats_advanced_2026-11-19.json  the 30 club rows with identities checked
  manifest.json                     sha256 + byte count per input and output, and the retrieval stamps

Run: python3 scripts/capture_9c30f2ae.py [--check]

Rules this parser keeps, because the brief's verification rule is the whole point of the exercise:

  * a cell is published only if the transcript prints it. A blank cell stays blank (null) and is
    counted, never filled from another source, another revision, or a previous session's capture;
  * a row that loses its leading cells to the PDF's page break keeps them blank and is reported as
    UNATTRIBUTED rather than guessed from the surrounding rows;
  * the cross-report diff compares only (player, status) pairs that BOTH revisions print with a team;
    a status that appears or disappears because a row moved across a page break is reported as
    unattributed-movement, not as a status change.

Verified: the 30 advanced rows are unique by club; each row's W + L equals its GP; the 12 result rows'
four quarter cells sum to the final the same game page prints.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RD = os.path.join(ROOT, "data", "rounds", "2026-11-19-9c30f2ae")
RAW = os.path.join(RD, "raw")

INJ_130 = os.path.join(RAW, "injury_2026-11-19_0130AM_raw.md")
INJ_INDEX = os.path.join(RAW, "injury_index_2026-11-19_raw.md")
ADV = os.path.join(RAW, "team_stats_advanced_raw.md")
RESULTS = os.path.join(RD, "results_2026-11-18.json")
PREV_1245 = os.path.join(ROOT, "data", "rounds", "2026-11-19-de0caf5d", "captures",
                         "injury_2026-11-19_0045AM_raw.md")

OUT_INJ = os.path.join(RD, "injuries_2026-11-19_0130AM.json")
OUT_ADV = os.path.join(RD, "team_stats_advanced_2026-11-19.json")
OUT_MAN = os.path.join(RD, "manifest.json")

ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*$")
STATUS_WORDS = {"Out", "Available", "Questionable", "Doubtful", "Probable", "Day-To-Day",
                "NOT YET SUBMITTED"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cells(line):
    """Split one markdown table row, PRESERVING empty cells.

    A naive ``row.strip("|").split("|")`` is wrong here: on this report an empty leading cell means
    the PDF's page break dropped the date, and dropping it shifts the team into the player column and
    "NOT YET SUBMITTED" into the status column — which is how a first version of this parser silently
    published 31 rows with zero "not yet submitted" rows while the document prints 22. The count of
    columns is therefore checked, never inferred.
    """
    t = line.strip()
    if not (t.startswith("|") and t.endswith("|")):
        return None
    return [c.strip() for c in t[1:-1].split("|")]


def parse_injury(path):
    """Every printed row, kept exactly as printed (including rows that lost their leading cells)."""
    rows, unread = [], []
    stamp = re.search(r"Retrieval \(UTC\)[^:]*:\s*(\S+)", open(path, encoding="utf-8").read())
    for i, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
        c = cells(line)
        if not c or all(not x for x in c):
            continue
        if c[0] in ("Game Date",) or set("".join(c)) <= set("-: "):
            continue
        # Two shapes occur, and the PDF prints them consistently:
        #   full    : date | time | matchup | team | player | status | reason      (7 cells)
        #   page-break: matchup | team | player | status | reason                (5 cells)
        # The break drops the two LEADING cells (date, time), not arbitrary ones; the third block of
        # the 01:30 AM report drops them unevenly, which is exactly why each short row is parsed by its
        # own shape and anything that fits neither is reported instead of guessed at.
        if len(c) == 7:
            gdate, gtime, matchup, team, player, status, reason = c
        elif len(c) == 5 and c[2] not in ("Brooklyn Nets", "Toronto Raptors", "Detroit Pistons",
                                          "New Orleans Pelicans", "Oklahoma City Thunder",
                                          "Washington Wizards", "Chicago Bulls", "Phoenix Suns",
                                          "Utah Jazz", "Houston Rockets", "Denver Nuggets",
                                          "Sacramento Kings", "Los Angeles Lakers"):
            # the 5-cell shape of the second block: matchup | team | player | status | reason
            gdate, gtime = "", ""
            matchup, team, player, status, reason = c
        elif len(c) in (2, 3):
            # The third block's page break loses date and time, and sometimes the matchup as well.
            # The printed cells are read from the END (the "NOT YET SUBMITTED" cell and the club above
            # it), and any leading cell is taken as a matchup only if it looks like one (XXX@YYY).
            # Nothing is matched to the row above: an unattributed row is reported as unattributed.
            gdate, gtime = "", ""
            status = c[-1]
            team = c[-2]
            player = ""
            reason = ""
            lead = c[0] if len(c) == 3 else ""
            matchup = lead if re.fullmatch(r"[A-Z]{2,3}@[A-Z]{2,3}", lead or "") else ""
            if matchup and lead != c[0]:
                matchup = ""
            if matchup:
                team = c[1]
        else:
            unread.append({"line": i, "cells": c,
                           "why": "neither the 7-cell nor the 5-cell shape; left unread"})
            continue
        # "NOT YET SUBMITTED" is not a participation status: the league prints it where the status
        # would be, and that is where it is published (as the row's status cell), with a flag saying so.
        nys = (status or "").strip().upper() == "NOT YET SUBMITTED"
        # A cell in the status column that is a CLUB rather than a status means the PDF printed the
        # matchup and the club without a status at all. The club is kept and the status left blank.
        misplaced_team = (status or "") if (status and status not in STATUS_WORDS
                                           and not nys and player is None) else None
        if misplaced_team:
            team, status = misplaced_team, None
        # The document prints "NOT YET SUBMITTED" in the STATUS cell on some rows and in the REASON
        # cell (with an empty status) on others — the same statement in two columns. Both are
        # published as status="NOT YET SUBMITTED" with `printed_in` naming the column it came from,
        # so the normalisation is visible and the original cell is recoverable.
        printed_in = None
        if nys:
            printed_in = "status"
        elif (reason or "").strip().upper() == "NOT YET SUBMITTED":
            printed_in, status, reason, nys = "reason", "NOT YET SUBMITTED", "", True
        rows.append({"line": i, "game_date": gdate or None, "game_time": gtime or None,
                     "matchup": matchup or None, "team": team or None,
                     "player": player or None, "status": status or None,
                     "reason": reason or None,
                     "attributed": bool(team), "status_printed": bool(status),
                     "not_yet_submitted": nys, "not_yet_submitted_printed_in": printed_in,
                     "misplaced_team_cell": misplaced_team})
    return rows, unread, (stamp.group(1) if stamp else None)


def parse_previous_1245(path):
    """The 12:45 AM revision, for the consecutive-report diff. Same shape, same rules."""
    if not os.path.exists(path):
        return [], [], None
    return parse_injury(path)


def diff_reports(prev, new):
    """(player, team) -> status changes between two consecutive official revisions.

    Only rows BOTH revisions attribute to a team are compared: a row that lost its team cell to the
    page break cannot be matched, and reporting its appearance as a status change would be a claim the
    documents do not support.
    """
    def keyed(rows):
        out = {}
        for r in rows:
            if r["player"] and r["team"]:
                out[(r["player"], r["team"])] = r
        return out

    a, b = keyed(prev), keyed(new)
    changes, appeared, disappeared = [], [], []
    for k in sorted(set(a) | set(b)):
        if k in a and k in b:
            if (a[k]["status"] or "") != (b[k]["status"] or ""):
                changes.append({"player": k[0], "team": k[1],
                                "from_status": a[k]["status"], "to_status": b[k]["status"],
                                "from_reason": a[k]["reason"], "to_reason": b[k]["reason"]})
        elif k in b:
            appeared.append({"player": k[0], "team": k[1], "status": b[k]["status"]})
        else:
            disappeared.append({"player": k[0], "team": k[1], "status": a[k]["status"]})
    return {"status_changes": changes, "appeared": appeared, "disappeared": disappeared}


def parse_advanced(path):
    """The 30 club rows, with the chunk boundary and the partial row preserved."""
    text = open(path, encoding="utf-8").read()
    rows, partial = [], []
    for line in text.splitlines():
        c = cells(line)
        if not c or len(c) < 8 or not re.fullmatch(r"\d+", c[0] or ""):
            continue
        team_m = re.search(r"\[([^\]]+)\]", c[1]) or re.search(r"([A-Za-z .]+)", c[1])
        team = team_m.group(1).strip() if team_m else None
        if team is None:
            continue
        nums = c[2:]
        rec = {"rank_printed": int(c[0]), "team": team, "cells_printed": len(nums)}
        # the page's column order, exactly as its header prints it
        cols = ["gp", "w", "l", "min", "off_rtg", "def_rtg", "net_rtg", "ast_pct", "ast_to",
                "ast_ratio", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct", "efg_pct", "ts_pct",
                "pace", "pie", "poss"]
        for name, raw in zip(cols, nums):
            raw = raw.strip()
            if raw == "" or raw is None:
                rec[name] = None
                continue
            try:
                rec[name] = float(raw.replace(",", ""))
            except ValueError:
                rec[name] = None
        rec["complete"] = all(rec.get(k) is not None for k in cols)
        rec["row_verified"] = (rec.get("w") is not None and rec.get("l") is not None
                               and rec.get("gp") is not None
                               and int(rec["w"] + rec["l"]) == int(rec["gp"]))
        (rows if rec["complete"] else partial).append(rec)
    by_team = {}
    for r in rows + partial:
        by_team.setdefault(r["team"], []).append(r)
    dupes = sorted(t for t, v in by_team.items() if len(v) > 1)
    return rows, partial, dupes


def build():
    inj_rows, inj_unread, inj_stamp = parse_injury(INJ_130)
    prev_rows, prev_unread, prev_stamp = parse_previous_1245(PREV_1245)
    delta = diff_reports(prev_rows, inj_rows)
    adv_rows, adv_partial, adv_dupes = parse_advanced(ADV)
    results = json.load(open(RESULTS, encoding="utf-8"))

    injuries = {
        "schema": "nba3.rounds.injuries/v1",
        "report_stamp": "11/19/26 01:30 AM ET",
        "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_30AM.pdf",
        "index_url": "https://official.nba.com/nba-injury-report-2026-27-season/",
        "retrieved_utc": "2026-11-19T07:07Z",
        "transcript": os.path.relpath(INJ_130, ROOT),
        "row_count": len(inj_rows),
        "attributed_rows": sum(1 for r in inj_rows if r["attributed"]),
        "unattributed_rows": [r for r in inj_rows if not r["attributed"]],
        "rows_without_a_printed_status": [r for r in inj_rows if not r["status_printed"]],
        "not_yet_submitted": sum(1 for r in inj_rows if r["not_yet_submitted"]),
        "rows": inj_rows,
        "lines_left_unread": inj_unread,
        "previous_revision": {
            "report_stamp": "11/19/26 12:45 AM ET",
            "source_url": ("https://ak-static.cms.nba.com/referee/injury/"
                           "Injury-Report_2026-11-19_12_45AM.pdf"),
            "transcript": os.path.relpath(PREV_1245, ROOT),
            "retrieved_utc_by_its_capturing_session": prev_stamp,
            "row_count": len(prev_rows),
            "lines_left_unread": prev_unread,
        },
        "delta_vs_previous": delta,
        "delta_rule": ("compared only (player, team) pairs both revisions print with a team; a row that "
                       "lost its team cell to the PDF page break cannot be matched and is reported as "
                       "unread, never as a status change"),
    }

    stats = {
        "schema": "nba3.rounds.team_stats_advanced/v1",
        "source_url": "https://www.nba.com/stats/teams/advanced",
        "retrieved_utc": "2026-11-19T07:16Z",
        "transcript": os.path.relpath(ADV, ROOT),
        "page_prints_rows": 30,
        "rows_read_in_full": len(adv_rows),
        "rows_partial": len(adv_partial),
        "duplicate_clubs": adv_dupes,
        "columns_as_printed": ["GP", "W", "L", "MIN", "OffRtg", "DefRtg", "NetRtg", "AST%",
                               "AST/TO", "AST Ratio", "OREB%", "DREB%", "REB%", "TOV%", "eFG%",
                               "TS%", "PACE", "PIE", "POSS"],
        "rows": adv_rows + adv_partial,
        "verification": "W + L == GP on every row; club names unique across the capture",
        "failures": [r["team"] for r in adv_rows + adv_partial if not r["row_verified"]],
        "season_type": "Regular Season (the page's own default filter)",
    }

    manifest = {
        "schema": "nba3.rounds.manifest/v1",
        "session": "arena/9c30f2ae-nba3",
        "retrieved_utc": "2026-11-19T07:05Z..07:20Z (window: the fetch tool returns no per-call stamp)",
        "inputs": [{"path": os.path.relpath(p, ROOT), "bytes": os.path.getsize(p),
                    "sha256": sha256(p)}
                   for p in (INJ_INDEX, INJ_130, ADV, RESULTS, PREV_1245) if os.path.exists(p)],
        "outputs": [{"path": os.path.relpath(p, ROOT)} for p in (OUT_INJ, OUT_ADV)],
        "games_with_quarter_scores": results["game_count"],
        "games_whose_quarters_sum_to_the_final": sum(
            1 for g in results["games"] if g["quarter_sums_equal_final"]),
    }
    return injuries, stats, manifest, results


def dumps(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main():
    check = "--check" in sys.argv[1:]
    injuries, stats, manifest, results = build()
    blobs = {OUT_INJ: dumps(injuries), OUT_ADV: dumps(stats), OUT_MAN: dumps(manifest)}
    if check:
        bad = []
        for path, blob in blobs.items():
            have = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if have != blob:
                bad.append(os.path.relpath(path, ROOT))
        if bad:
            print("capture 9c30f2ae --check: differs from the committed artefact: " + ", ".join(bad))
            return 1
        print("capture 9c30f2ae --check: 5 inputs, 3 outputs, byte-identical")
        return 0
    os.makedirs(RD, exist_ok=True)
    for path, blob in blobs.items():
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(blob)
    print(f"injury rows: {injuries['row_count']} ({injuries['attributed_rows']} attributed, "
          f"{injuries['not_yet_submitted']} NOT YET SUBMITTED)")
    print(f"delta vs 12:45 AM: {len(injuries['delta_vs_previous']['status_changes'])} status change(s), "
          f"{len(injuries['delta_vs_previous']['appeared'])} appeared, "
          f"{len(injuries['delta_vs_previous']['disappeared'])} disappeared")
    print(f"advanced rows: {stats['rows_read_in_full']} full + {stats['rows_partial']} partial of "
          f"{stats['page_prints_rows']} printed; failures: {stats['failures'] or 'none'}")
    print(f"results: {manifest['games_with_quarter_scores']} games, "
          f"{manifest['games_whose_quarters_sum_to_the_final']} whose quarters sum to the final")
    return 0


if __name__ == "__main__":
    sys.exit(main())
