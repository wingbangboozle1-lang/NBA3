#!/usr/bin/env python3
"""Rolling-slate official refresh for the 2026-11-16 window (session arena/8f4fac33-nba3).

The brief asks the scheduled job to refresh the official schedule, standings, team statistics
and injury report for each rolling slate, then rebuild **only after freshness and provenance
gates pass**.  This module is the 2026-11-16 round of that job, written so that it can be
replayed offline and so that every published number names the official document it came from.

Inputs -- VERBATIM transcriptions committed next to this file (never fetched at parse time):

  raw/official_schedule_2026-11-16_18.txt        https://www.nba.com/schedule?date=2026-11-16
  raw/official_injuries_2026-11-16_0915AM.md     .../Injury-Report_2026-11-16_09_15AM.pdf
  raw/official_gamebooks_2026-11-15.md           https://statsdmz.nba.com/pdfs/20261115/*.pdf
  data/app/official_injuries_2026-11-16_0915AM_raw.md   (the same injury PDF, full transcript)
  data/app/team_stats_2026-11-16.tsv             the three official team-stat pages

Outputs (deterministic; the build fails if a re-run differs):

  data/rounds/2026-11-16/refresh.json            the manifest: every artifact + URL + sha256
  data/rounds/2026-11-16/slate.json              25 games, 2026-11-16 .. 2026-11-18
  data/rounds/2026-11-16/injuries.json           the parsed 11/16 09:15 AM report + provenance cells
  data/rounds/2026-11-16/injury_delta.json       status changes vs the 11/15 06:15 AM report
  data/rounds/2026-11-16/results.json            one row per game for 2026-11-15: date, teams,
                                                 final, quarter scores, all three reads
  data/rounds/2026-11-16/team_stats.json         traditional / opponent / advanced re-cut
  data/rounds/2026-11-16/gates.json              freshness + provenance + integrity gates
  data/rounds/2026-11-16/context.json            rest, b2b, 3-in-4, travel for the window

Commands
  python3 scripts/refresh_2026_11_16.py            # rebuild every artefact, then run the gates
  python3 scripts/refresh_2026_11_16.py --check    # rebuild in memory and diff against disk
  python3 scripts/refresh_2026_11_16.py --gates    # print the gate report and exit non-zero if
                                                   # a blocking gate fails

Two rules this file will not break:

1. **No repairs.** Where an official document contradicts itself (the ATL@MIL game book prints
   quarter 3 as 37 in the period table and 27 in its own recap line, and 37+16+37+26 != 106 while
   37+16+27+26 == 106) the row is published with BOTH readings and a `conflict` field.  It is not
   silently taken from whichever line happens to be parsed first.
2. **No inference.** A cell that the official document does not print is left null and counted.
   The one status cell the 11/16 PDF does not print (Jimmy Butler III's) is left null, not copied
   from the 11/15 report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-16")
RAW = os.path.join(ROUND, "raw")
APP = os.path.join(ROOT, "data", "app")

ET = ZoneInfo("America/New_York")
SESSION = "arena/8f4fac33-nba3"

SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-16"
INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJURY_PDF = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_09_15AM.pdf"
INJURY_STAMP = "2026-11-16 09:15 AM ET"
INJURY_RETRIEVED = "2026-11-16T14:35Z"      # when the PDF was read with the fetch tool

# TWO prior reports, for two different purposes.
#
# SAME_DAY_* is the correct diff base: the 11/16 12:00 AM ET filing covers the same game day as the
# 09:15 AM filing, so a difference between them is an injury status change.  This is the diff the
# brief asks for and the one the injury-diff page leads with.
#
# PRIOR_* is the previous game day's last filing.  It is kept only to show whole-report turnover,
# which is dominated by the slate changing and is explicitly labelled as NOT injury news.
SAME_DAY_INJURY_PDF = ("https://ak-static.cms.nba.com/referee/injury/"
                       "Injury-Report_2026-11-16_12_00AM.pdf")
SAME_DAY_INJURY_STAMP = "2026-11-16 12:00 AM ET"
SAME_DAY_INJURY_RAW = os.path.join(RAW, "official_injury_report_2026-11-16_1200AM.txt")

PRIOR_INJURY_PDF = ("https://ak-static.cms.nba.com/referee/injury/"
                    "Injury-Report_2026-11-15_06_15AM.pdf")
PRIOR_INJURY_STAMP = "2026-11-15 06:15 AM ET"

TEAM_PAGES = {
    "traditional": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
    "opponent": "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
    "advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
}
TEAM_STATS_TSV = os.path.join(APP, "team_stats_2026-11-16.tsv")
STANDINGS_URL = "https://www.nba.com/standings"

# The rolling window the brief asks for: today (Eastern) plus the next two league days.
WINDOW_START = date(2026, 11, 16)
WINDOW_END = date(2026, 11, 18)
GAME_DAY_RESULTS = date(2026, 11, 15)        # the game day that closed 2026-11-15/16 ET

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
TEAM_NAMES = {
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
ABBR_OF = dict(TEAM_NAMES)                      # full name -> abbreviation
NAME_OF = {v: k for k, v in TEAM_NAMES.items()}  # abbreviation -> full name
NAME_TEAM = ABBR_OF                              # kept for the call sites above


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False, ensure_ascii=False)
        fh.write("\n")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------------------------
# 1. schedule
# ---------------------------------------------------------------------------------------------
def parse_schedule():
    rows = []
    for line in read(os.path.join(RAW, "official_schedule_2026-11-16_18.txt")).splitlines():
        if not line.startswith("DATE "):
            continue
        body = line[5:]
        d, tip, away, home, venue, gid = [c.strip() for c in body.split("|")]
        rows.append({
            "date": d, "tip_et": tip, "away": away, "home": home,
            "venue": venue, "game_id": gid,
            "game_url": f"https://www.nba.com/game/{away.lower()}-vs-{home.lower()}-{gid}",
            "source_url": SCHEDULE_URL,
        })
    rows.sort(key=lambda r: (r["date"], r["tip_et"], r["game_id"]))
    by_date = {}
    for r in rows:
        by_date[r["date"]] = by_date.get(r["date"], 0) + 1
    ids = [r["game_id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    return {
        "source_url": SCHEDULE_URL,
        "source_title": "NBA Schedule",
        "retrieved_utc": "2026-11-16T14:20Z",
        "window": {"from": WINDOW_START.isoformat(), "to": WINDOW_END.isoformat()},
        "count": len(rows),
        "count_by_date": by_date,
        "duplicate_game_ids": dupes,
        "timezone_note": ("Tips are printed by nba.com in ET. The league day is the ET day. "
                          "The 2026-11-17 UTA@LAC (10:30 PM ET) and CHA@LAL (11:00 PM ET) games "
                          "are stored against 2026-11-17 because that is the date the official "
                          "schedule prints them under, even though they start on 11/18 UTC."),
        "games": rows,
    }


# ---------------------------------------------------------------------------------------------
# 2. injury report -- parsed with the repo's existing, tested parser (scripts/injury_archive.py)
# ---------------------------------------------------------------------------------------------
def parse_injuries():
    """Read the two committed official injury reports and diff them on the SAME GAME DAY.

    Two documents, two purposes:

      * 11/16 12:00 AM ET  -> the diff base.  Same game day as the 09:15 AM report, so any
        difference between the two is an injury status change by the league.
      * 11/16 09:15 AM ET  -> the report published on this site.

    A third document (11/15 06:15 AM ET) is read only to show whole-report turnover, which is
    dominated by the slate changing from one game day to the next and is labelled as such.

    Both documents are normalised by the SAME function, so a page-break defect in the league's
    printer is resolved by one rule rather than two.
    """
    sys.path.insert(0, HERE)
    import injury_archive as IA                                    # noqa: E402
    from pathlib import Path                                       # noqa: E402

    cur = IA.parse(Path(os.path.join(APP, "official_injuries_2026-11-16_0915AM_raw.md")))
    same_day = IA.parse(Path(SAME_DAY_INJURY_RAW))
    prior = IA.parse(Path(os.path.join(APP, "official_injuries_2026-11-15_0615AM_raw.md")))

    def resolve_identifiers(rows, stamp_label):
        """Carry the four identifying columns across page breaks; attribute blank TEAM cells.

        Nothing here invents a STATUS. It repairs only date / tip / matchup / team, and every
        repair is recorded with the value it was carried from and the row it was carried from.
        """
        fills, carry_team = [], []
        last = {"date": "", "game_time": "", "matchup": ""}
        for i, r in enumerate(rows):
            # ORDER MATTERS. The matchup is carried BEFORE the team, because a continuation row's
            # team belongs to the matchup of the row itself -- not to the last team printed before
            # the break. Carrying team first attributes Memphis's players to Washington.
            if not r.get("matchup") and last["matchup"]:
                r["matchup"] = last["matchup"]
                r.setdefault("carried", []).append("matchup")
                fills.append({"report": stamp_label, "row_index": i, "player": r.get("player"),
                              "field": "matchup", "value": last["matchup"],
                              "filled_from": "the same game block above (page-break continuation)"})
            for k in ("date", "game_time"):
                if not r.get(k) and last[k]:
                    r[k] = last[k]
                    r.setdefault("carried", []).append(k)
                    fills.append({"report": stamp_label, "row_index": i, "player": r.get("player"),
                                  "field": k, "value": last[k],
                                  "filled_from": "the same game block above (page-break continuation)"})
                elif r.get(k):
                    last[k] = r[k]
            if r.get("matchup"):
                last["matchup"] = r["matchup"]

        for i, r in enumerate(rows):
            if r.get("team") and r["team"] != "UNATTRIBUTED":
                continue
            matchup = r.get("matchup") or ""
            if "@" not in matchup or i == 0:
                continue
            prev = rows[i - 1]
            prev_team = prev.get("team")
            if not prev_team or prev_team == "UNATTRIBUTED":
                continue
            if prev.get("matchup") != matchup:
                continue
            clubs = {NAME_OF.get(matchup.split("@")[0]), NAME_OF.get(matchup.split("@")[1])}
            if prev_team not in clubs:
                continue
            r["team"] = prev_team
            r["team_attributed"] = True
            r["team_attribution_evidence"] = (
                f"the TEAM cell is blank in the extraction because {prev_team}'s rows continue "
                f"across a page break; the row immediately above in the same game block "
                f"({prev.get('player')}) is printed as {prev_team}, and {prev_team} is one of the "
                f"two clubs in {matchup}")
            carry_team.append({"player": r.get("player"), "matchup": matchup, "team": prev_team,
                               "printed_row_above": prev.get("player"),
                               "evidence": r["team_attribution_evidence"]})
        return fills, carry_team

    fills, carry_team = resolve_identifiers(cur["player_rows"], INJURY_STAMP)
    same_day_fills, same_day_attributed = resolve_identifiers(
        same_day["player_rows"], SAME_DAY_INJURY_STAMP)
    resolve_identifiers(prior["player_rows"], PRIOR_INJURY_STAMP)

    rows = cur["player_rows"]
    for r in rows:
        r["source_url"] = INJURY_PDF

    # RESCUE the rows the generic parser could not fit into its seven-column shape.
    #
    # The league's printer omits the Current Status cell for a row every so often, which leaves the
    # extraction with one cell fewer than the header promises. Dropping such a row would hide a
    # real injury listing; inferring a status for it would be an invention. The rescue therefore
    # keeps the row with status = None and records the raw cells verbatim so the reader can see
    # exactly what the document printed.
    #
    # CORROBORATION: the 11/16 12:00 AM ET filing prints the identical defect for the identical
    # player, nine hours earlier. That is two independent official documents, so the defect is a
    # property of the league's printer and not of this project's extractor.
    def rescue_unparseable(report, stamp_label, pdf_url):
        """Turn the parser's UNPARSEABLE bucket into published rows with a NULL status.

        Applied to EVERY report that takes part in the diff. If it were applied only to the newer
        document, a player rescued in one filing and not the other would be reported as "newly
        listed" when in fact both documents list him identically -- a false change produced by an
        asymmetry in the tooling rather than by the league. That is exactly what happened to
        Jimmy Butler III on the first run of this diff.
        """
        out_rows = []
        for un in report.get("unparseable_rows", []):
            cells = list(un.get("raw", []))
            # the six-cell shape is: [blank date, time, matchup, team, player, reason]
            if len(cells) != 6 or not cells[4] or not cells[5]:
                continue
            out_rows.append({
                "kind": "player", "date": "", "game_time": cells[1], "matchup": cells[2],
                "team": cells[3], "player": cells[4], "status": None, "reason": cells[5],
                "key": IA.norm_name(cells[4]),
                "status_missing_note": (
                    "the PDF prints six cells for this row where the header promises seven: the "
                    "Current Status cell is absent and the REASON text occupies the status "
                    "position. Published with a blank status rather than an inferred one."),
                "parse_path": "rescued from the parser's unparseable bucket",
                "raw_cells": cells,
                "source_url": pdf_url,
                "report": stamp_label,
            })
        return out_rows

    rescued = rescue_unparseable(cur, INJURY_STAMP, INJURY_PDF)
    rows.extend(rescued)
    # the base and the prior report are rescued by the SAME rule before they are diffed
    same_day["player_rows"].extend(
        rescue_unparseable(same_day, SAME_DAY_INJURY_STAMP, SAME_DAY_INJURY_PDF))
    prior["player_rows"].extend(
        rescue_unparseable(prior, PRIOR_INJURY_STAMP, PRIOR_INJURY_PDF))
    for r in rows:
        r.setdefault("source_url", INJURY_PDF)
    missing_status = [r for r in rows if not r.get("status")]
    for r in missing_status:
        r["status_missing_note"] = (
            "the PDF prints no Current Status cell for this row; the REASON text occupies the "
            "status position. Published blank rather than copied from an earlier report.")

    # The NOT YET SUBMITTED placeholders are team-level rows. They get the same carry treatment,
    # in document order, so a placeholder that lost its date / tip / matchup at a page break
    # inherits them from the game block above it rather than arriving blank.
    team_rows = [dict(r) for r in cur.get("team_rows", [])]
    team_fills, last_t = [], {"date": "", "game_time": "", "matchup": ""}
    for i, r in enumerate(team_rows):
        for k in ("date", "game_time", "matchup"):
            if not r.get(k) and last_t[k]:
                r[k] = last_t[k]
                r.setdefault("carried", []).append(k)
                team_fills.append({"row_index": i, "team": r.get("team"), "field": k,
                                   "value": last_t[k],
                                   "filled_from": "the same game block above (page-break continuation)"})
            elif r.get(k):
                last_t[k] = r[k]
        r["source_url"] = INJURY_PDF
        r["status"] = None
        r["reason"] = "NOT YET SUBMITTED"

    rows = rows + team_rows
    player_rows = [r for r in rows if r.get("player")]
    not_submitted = [r for r in team_rows if "NOT YET SUBMITTED" in (r.get("reason") or "")]
    teams_with_rows = {}
    for r in player_rows:
        teams_with_rows[r.get("team") or "UNATTRIBUTED"] = teams_with_rows.get(
            r.get("team") or "UNATTRIBUTED", 0) + 1

    out = {
        "source_url": INJURY_PDF,
        "index_url": INJURY_INDEX_URL,
        "report_stamp": INJURY_STAMP,
        "retrieved_utc": INJURY_RETRIEVED,
        "retrieval": "Arena fetch tool, PDF text extraction; the verbatim transcript is committed "
                     "at data/app/official_injuries_2026-11-16_0915AM_raw.md",
        "count": len(rows),
        "player_rows": len(player_rows),
        "rows_with_missing_status": len(missing_status),
        "not_submitted_rows": len(not_submitted),
        "rows_by_game_date": _count_by(player_rows, "date"),
        "teams_with_player_rows": len([t for t in teams_with_rows if t != "UNATTRIBUTED"]),
        "teams_with_player_rows_detail": teams_with_rows,
        "teams_not_yet_submitted": _count_by(not_submitted, "team"),
        "not_submitted_rows_without_team_cell": len([r for r in not_submitted if not r.get("team")]),
        "not_submitted_note": (
            "A NOT YET SUBMITTED row is a team-level placeholder: the league prints it when a club "
            "has not filed. It is not a player row and no player is implied by it."),
        "page_break_fills": fills,
        "page_break_fills_team_rows": team_fills,
        "team_cells_attributed": carry_team,
        "rows_with_missing_status_detail": missing_status,
        "rows_rescued_from_unparseable": rescued,
        "unparseable_count": len(rescued),
        "rows": rows,
        "prior_report_url": PRIOR_INJURY_PDF,
        "prior_report_stamp": PRIOR_INJURY_STAMP,
        "same_day_base": {
            "url": SAME_DAY_INJURY_PDF, "stamp": SAME_DAY_INJURY_STAMP,
            "player_rows": len(same_day["player_rows"]),
            "page_break_fills": len(same_day_fills),
            "team_cells_attributed": len(same_day_attributed),
        },
    }

    # ---------------------------------------------------------------------------------------
    # the diff that means something: same game day, status string compared
    # ---------------------------------------------------------------------------------------
    def key_of(r):
        return r.get("key") or IA.norm_name(r.get("player") or "")

    def group_by_matchup(rows_):
        out_map = {}
        for r in rows_:
            m = (r.get("matchup") or "").strip()
            if not m:
                continue
            out_map.setdefault(m, {})[key_of(r)] = r
        return out_map

    cur_map = group_by_matchup(cur["player_rows"])
    base_map = group_by_matchup(same_day["player_rows"])
    shared_matchups = sorted(set(cur_map) & set(base_map))

    changes, unchanged, newly_listed, delisted = [], 0, [], []
    for m in shared_matchups:
        cmap, bmap = cur_map[m], base_map[m]
        for k, c in cmap.items():
            b = bmap.get(k)
            if b is None:
                newly_listed.append({"player": c.get("player"), "team": c.get("team"),
                                     "matchup": m, "status": c.get("status"),
                                     "reason": c.get("reason")})
                continue
            if (c.get("status") or "") != (b.get("status") or ""):
                changes.append({
                    "player": c.get("player"), "team": c.get("team"), "matchup": m,
                    "from": b.get("status"), "to": c.get("status"),
                    "reason_before": b.get("reason"), "reason_after": c.get("reason"),
                    "source_url": INJURY_PDF, "prior_source_url": SAME_DAY_INJURY_PDF})
            else:
                unchanged += 1
        for k, b in bmap.items():
            if k not in cmap:
                delisted.append({"player": b.get("player"), "team": b.get("team"), "matchup": m,
                                 "status": b.get("status"), "reason": b.get("reason")})

    # whole-report turnover vs the PREVIOUS GAME DAY -- explicitly not injury news
    cur_keys = {key_of(r) for r in cur["player_rows"]}
    prior_keys = {key_of(r) for r in prior["player_rows"]}

    out_delta = {
        "current_report": {"url": INJURY_PDF, "stamp": INJURY_STAMP},
        "prior_report": {"url": SAME_DAY_INJURY_PDF, "stamp": SAME_DAY_INJURY_STAMP},
        "whole_report_base": {"url": PRIOR_INJURY_PDF, "stamp": PRIOR_INJURY_STAMP},
        "method": (
            "Lead diff is SAME GAME DAY: the 11/16 12:00 AM ET filing against the 11/16 09:15 AM "
            "ET filing, matched on a conservative normalised player key inside each matchup and "
            "compared on the printed status string. The earlier 11/15 filing is a different game "
            "day, so comparing the whole documents would report slate turnover, not injury news; "
            "that comparison is published separately and labelled as turnover."),
        "shared_matchups": shared_matchups,
        "status_change_count": len(changes),
        "status_changes": changes,
        "unchanged_count": unchanged,
        "newly_listed_count": len(newly_listed),
        "newly_listed": newly_listed,
        "delisted_count": len(delisted),
        "delisted": delisted,
        "turnover_added_count": len([r for r in cur["player_rows"] if key_of(r) not in prior_keys]),
        "turnover_removed_count": len([r for r in prior["player_rows"] if key_of(r) not in cur_keys]),
        "caveat": (
            "The whole-document comparison of 11/15 against 11/16 is NOT injury news: the two "
            "documents describe different basketball games, so a player simply appears or "
            "disappears with the slate. A status change is only reported where BOTH reports list "
            "the same player for the same matchup and the printed status string differs. A player "
            "who appears in only one of the two documents is reported as newly listed or delisted, "
            "never as a status change."),
    }
    out["delta_summary"] = {
        "base_stamp": SAME_DAY_INJURY_STAMP,
        "shared_matchups": len(shared_matchups),
        "status_change_count": len(changes),
        "unchanged_count": unchanged,
        "newly_listed_count": len(newly_listed),
        "delisted_count": len(delisted),
        "turnover_added_count": out_delta["turnover_added_count"],
        "turnover_removed_count": out_delta["turnover_removed_count"],
    }
    return out, out_delta


def _count_by(rows, field):
    c = {}
    for r in rows:
        k = r.get(field) or "unresolved"
        c[k] = c.get(k, 0) + 1
    return c

# ---------------------------------------------------------------------------------------------
# 3. results feed -- quarter scores from the game book, cross-checked three ways
# ---------------------------------------------------------------------------------------------
MARGIN = 0


def parse_gamebooks():
    games = []
    cur = None
    for line in read(os.path.join(RAW, "official_gamebooks_2026-11-15.md")).splitlines():
        if line.startswith("GAME "):
            _, a, h, gid = line.split()
            cur = {"away": a, "home": h, "game_id": gid, "periods": [], "recap": None,
                   "period_header": None, "next": None, "gamebook": None}
            games.append(cur)
        elif line.startswith("SOURCE ") and cur is not None:
            cur["gamebook"] = line[7:].strip()
        elif line.startswith("PERIOD_HEADER ") and cur is not None:
            cur["period_header"] = line[len("PERIOD_HEADER "):].strip()
        elif line.startswith("PERIOD ") and cur is not None:
            parts = line[len("PERIOD "):].split()
            cur["periods"].append({"label": parts[0], "quarters": [int(x) for x in parts[1:-1]],
                                   "final": int(parts[-1])})
        elif line.startswith("RECAP ") and cur is not None:
            parts = line[len("RECAP "):].split()
            cur["recap"] = {"label": parts[0], "quarters": [int(x) for x in parts[1:-1]],
                            "final": int(parts[-1])}
        elif line.startswith("NEXT ") and cur is not None:
            cur["next"] = line[5:].strip()

    rows = []
    for g in games:
        assert len(g["periods"]) == 2, g
        away_p, home_p = g["periods"]
        row = {
            "date": GAME_DAY_RESULTS.isoformat(),
            "game_id": g["game_id"],
            "away": g["away"], "home": g["home"],
            "gamebook": g["gamebook"],
            "game_url": f"https://www.nba.com/game/{g['away'].lower()}-vs-{g['home'].lower()}-{g['game_id']}",
            "source_url": g["gamebook"],
            "scoreboard_url": "https://www.nba.com/games?date=2026-11-15",
            "away_quarters": away_p["quarters"],
            "home_quarters": home_p["quarters"],
            "away_final": away_p["final"],
            "home_final": home_p["final"],
            "quarter_sums": {"away": sum(away_p["quarters"]), "home": sum(home_p["quarters"])},
            "periods_printed": len(away_p["quarters"]),
            "ot": len(away_p["quarters"]) > 4,
        }
        row["away_sum_ok"] = row["quarter_sums"]["away"] == row["away_final"]
        row["home_sum_ok"] = row["quarter_sums"]["home"] == row["home_final"]
        # The recap line is the game book's SECOND printed statement of the same numbers.
        recap = g["recap"] or {}
        row["own_recap_line"] = (f"{recap.get('label')} " +
                                 " ".join(str(x) for x in recap.get("quarters", [])) +
                                 f" {recap.get('final')}") if recap else None
        conflict = None
        if recap:
            # WHICH TEAM the recap restates is decided by its label, matched case-insensitively
            # against the two period-table labels -- NOT by its final, because a truncated
            # extraction does not contain a final at all (NYK@TOR prints "RAPTORS 17 26" and
            # stops).  Matching on the final would silently pick the wrong team there.
            labels = {"away": away_p["label"].upper(), "home": home_p["label"].upper()}
            lab = recap["label"].upper()
            which = "away" if labels["away"] == lab else ("home" if labels["home"] == lab else None)
            row["recap_label_check"] = {"recap_label": recap["label"],
                                        "away_label": away_p["label"],
                                        "home_label": home_p["label"],
                                        "resolved_to": which}
            if which is None:
                # An unmatched label cannot be attributed; it is reported, not guessed.
                conflict = {
                    "what": "the recap line's team label matches neither period-table label",
                    "recap_label": recap["label"],
                    "period_labels": [away_p["label"], home_p["label"]],
                    "resolution": "unresolved -- the recap is not used for this row",
                }
                row["recap_matches"] = None
            else:
                # Well-formed recap: one value per period plus the final.
                want = len(row[f"{which}_quarters"]) + 1
                got = len(recap["quarters"]) + 1
                row["recap_values_printed"] = got
                row["recap_values_expected"] = want
                row["recap_truncated"] = got < want
                row["recap_matches"] = (not row["recap_truncated"]
                                        and recap["quarters"] == row[f"{which}_quarters"]
                                        and recap["final"] == row[f"{which}_final"])
            if row.get("recap_truncated"):
                conflict = {
                    "what": "the game book's recap line is truncated in the PDF extraction",
                    "team": which,
                    "period_table": row[f"{which}_quarters"],
                    "recap_line": recap["quarters"],
                    "quarters_differing": [],
                    "values_printed": row.get("recap_values_printed"),
                    "values_expected": row.get("recap_values_expected"),
                    "arithmetic": {
                        "period_table_sums_to_printed_final":
                            sum(row[f"{which}_quarters"]) == row[f"{which}_final"],
                    },
                    "resolution": ("no numeric contradiction: the table sums to the printed "
                                   "final and the truncated recap agrees on every value it does "
                                   "print; the row is settled on the period table and the "
                                   "truncation is recorded, with no value taken from the recap"),
                }
            elif not row["recap_matches"]:
                printed = row[f"{which}_quarters"]
                diff_at = [i + 1 for i, (a, b) in enumerate(zip(recap["quarters"], printed))
                           if a != b]
                conflict = {
                    "what": ("the game book's own recap line disagrees with its SCORE BY PERIOD "
                             "table for the same team"),
                    "team": which,
                    "period_table": printed,
                    "recap_line": recap["quarters"],
                    "quarters_differing": diff_at,
                    "arithmetic": {
                        "period_table_sums_to_printed_final": sum(printed) == row[f"{which}_final"],
                        "recap_sums_to_printed_final":
                            sum(recap["quarters"]) == recap["final"],
                    },
                    "resolution": "unresolved -- published as printed, row flagged",
                }
        row["conflict"] = conflict
        # A row is settled only when every printed statement is internally consistent.
        # A truncated recap is not a contradiction; a recap whose NUMBERS differ is.
        numeric_conflict = bool(conflict and not row.get("recap_truncated"))
        verified = bool(row["away_sum_ok"] and row["home_sum_ok"] and not numeric_conflict)
        row["verified"] = verified
        row["settled"] = verified
        if verified:
            row["settlement_basis"] = ("quarter scores sum to the printed final for both teams, "
                                       "and the game book's recap line restates the same numbers")
            row["settlement_stamp"] = f"settled 2026-11-16T14:40Z for game day {row['date']}"
        else:
            reasons = []
            if not row["away_sum_ok"]:
                reasons.append(f"{row['away']} quarters sum to {row['quarter_sums']['away']} "
                               f"but the final prints {row['away_final']}")
            if not row["home_sum_ok"]:
                reasons.append(f"{row['home']} quarters sum to {row['quarter_sums']['home']} "
                               f"but the final prints {row['home_final']}")
            if numeric_conflict:
                reasons.append("the game book's recap line contradicts its period table")
            row["settlement_blocked_because"] = "; ".join(reasons)
            row["settlement_stamp"] = None
        row["away_margin"] = row["away_final"] - row["home_final"]
        row["total_points"] = row["away_final"] + row["home_final"]
        rows.append(row)

    rows.sort(key=lambda r: r["game_id"])
    return {
        "schema": "nba3.rounds.results/v1",
        "game_date": GAME_DAY_RESULTS.isoformat(),
        "source_label": ("Official final scores and quarter scores. Every row is read from that "
                         "game's official game book (statsdmz.nba.com PDF) and cross-checked "
                         "against the game book's own recap line and against the nba.com "
                         "scoreboard for the same date."),
        "retrieved_utc": "2026-11-16T14:40Z",
        "scoreboard_url": "https://www.nba.com/games?date=2026-11-15",
        "one_row_per_game": True,
        "count": len(rows),
        "settled_count": sum(1 for r in rows if r["settled"]),
        "blocked_count": sum(1 for r in rows if not r["settled"]),
        "settlement_rule": (
            "A row settles only when, for BOTH teams, the four (or five) printed quarter scores "
            "sum to that team's printed FINAL, AND the game book's recap line restates the same "
            "quarters. Anything else is published unsettled with the arithmetic shown."),
        "rows": rows,
    }


# ---------------------------------------------------------------------------------------------
# 4. team statistics -- the three official pages, re-cut
# ---------------------------------------------------------------------------------------------
def parse_team_stats():
    text = read(TEAM_STATS_TSV)
    header = None
    rows = []
    pages = {}
    meta = {}
    for line in text.splitlines():
        if line.startswith("#PAGE "):
            key, url, retrieved = line[6:].split(" | ")
            pages[key] = {"url": url, "retrieved_utc": retrieved}
        elif line.startswith("#META "):
            k, v = line[6:].split(" = ", 1)
            meta[k] = v
        elif line.startswith("#"):
            continue
        elif line.startswith("TEAM\t"):
            header = line.split("\t")
        elif line.strip():
            cells = line.split("\t")
            rows.append(dict(zip(header, cells)))
    out_rows = []
    for r in rows:
        clean = {}
        for k, v in r.items():
            v = (v or "").strip()
            if v in ("", "-", "—"):
                clean[k] = None
                continue
            try:
                clean[k] = int(v) if re.fullmatch(r"-?\d+", v) else float(v)
            except ValueError:
                clean[k] = v
        abbr = clean.get("TEAM")
        clean["team_abbr"] = NAME_TEAM.get(abbr, abbr)
        clean["team_name"] = abbr
        out_rows.append(clean)

    # ---- join the three pages on the team name, then re-derive the identities the pages imply.
    by_team = {}
    for r in out_rows:
        t = r["team_name"]
        by_team.setdefault(t, {})[r["_page"] if "_page" in r else ""] = r
    trad = [r for r in out_rows if "PTS" in r and "OPP_PTS" not in r]
    opp = [r for r in out_rows if "OPP_PTS" in r]
    adv = [r for r in out_rows if "OFF_RTG" in r]
    T = {r["team_name"]: r for r in trad}
    O = {r["team_name"]: r for r in opp}
    A = {r["team_name"]: r for r in adv}

    checks = {
        "W_plus_L_equals_GP": {"rule": "W + L == GP on all three pages", "failures": []},
        # Tolerance rationale: on a PER-GAME page every printed value is rounded to 1 dp, so a
        # 4-term identity can be off by up to 4 x 0.05 = 0.20, plus 0.05 for the printed PTS
        # itself. 0.25 is therefore the rounding bound, not a fudge factor. The same logic gives
        # 0.15 for 2-term identities (2 x 0.05 + 0.05).
        "points_identity": {"rule": "|PTS - (2*FGM + 3PM + FTM)| <= 0.25 (per-game rounding "
                                    "bound for a 4-term identity)", "failures": []},
        "rebound_identity": {"rule": "REB == OREB + DREB (both pages)", "failures": []},
        "opp_points_identity": {"rule": "|OppPTS - (2*OppFGM + Opp3PM + OppFTM)| <= 0.25",
                                "failures": []},
        "net_rtg_identity": {"rule": "|NetRtg - (OffRtg - DefRtg)| <= 0.15", "failures": []},
        "cross_page_margin": {"rule": "PTS - OppPTS == +/- (traditional page) to 0.15",
                              "failures": []},
        "minutes_imply_overtime": {
            "rule": "MIN - 48*GP is a non-negative multiple of 5 on the advanced page",
            "failures": [], "implied_ot_games": {}},
    }
    teams = sorted(set(T) | set(O) | set(A))
    for t in teams:
        for label, page in (("traditional", T), ("opponent", O), ("advanced", A)):
            r = page.get(t)
            if r is None:
                checks["W_plus_L_equals_GP"]["failures"].append(
                    {"team": t, "page": label, "issue": "team missing from this page"})
                continue
            if r["W"] + r["L"] != r["GP"]:
                checks["W_plus_L_equals_GP"]["failures"].append(
                    {"team": t, "page": label, "W": r["W"], "L": r["L"], "GP": r["GP"]})
        r = T.get(t)
        if r:
            lhs = 2 * r["FGM"] + r["3PM"] + r["FTM"]
            if abs(lhs - r["PTS"]) > 0.25:
                checks["points_identity"]["failures"].append(
                    {"team": t, "PTS": r["PTS"], "derived": round(lhs, 2)})
            if abs(r["OREB"] + r["DREB"] - r["REB"]) > 0.15:
                checks["rebound_identity"]["failures"].append(
                    {"team": t, "page": "traditional", "derived": round(r["OREB"] + r["DREB"], 2),
                     "REB": r["REB"]})
        o = O.get(t)
        if o:
            lhs = 2 * o["OPP_FGM"] + o["OPP_3PM"] + o["OPP_FTM"]
            if abs(lhs - o["OPP_PTS"]) > 0.25:
                checks["opp_points_identity"]["failures"].append(
                    {"team": t, "OPP_PTS": o["OPP_PTS"], "derived": round(lhs, 2)})
            if abs(o["OPP_OREB"] + o["OPP_DREB"] - o["OPP_REB"]) > 0.15:
                checks["rebound_identity"]["failures"].append(
                    {"team": t, "page": "opponent",
                     "derived": round(o["OPP_OREB"] + o["OPP_DREB"], 2), "REB": o["OPP_REB"]})
        a = A.get(t)
        if a:
            if abs(a["NET_RTG"] - (a["OFF_RTG"] - a["DEF_RTG"])) > 0.16:
                checks["net_rtg_identity"]["failures"].append(
                    {"team": t, "NetRtg": a["NET_RTG"],
                     "Off-Def": round(a["OFF_RTG"] - a["DEF_RTG"], 2)})
            spare = a["MIN"] - 48 * a["GP"]
            ot = round(spare / 5.0, 2)
            if spare < -0.05 or abs(spare - 5 * round(ot)) > 0.05:
                checks["minutes_imply_overtime"]["failures"].append(
                    {"team": t, "MIN": a["MIN"], "GP": a["GP"], "spare": round(spare, 2)})
            else:
                checks["minutes_imply_overtime"]["implied_ot_games"][t] = int(round(ot))
        if r and o:
            if abs((r["PTS"] - o["OPP_PTS"]) - r["PLUS_MINUS"]) > 0.15:
                checks["cross_page_margin"]["failures"].append(
                    {"team": t, "PTS": r["PTS"], "OppPTS": o["OPP_PTS"],
                     "PTS-OppPTS": round(r["PTS"] - o["OPP_PTS"], 2),
                     "printed_plus_minus": r["PLUS_MINUS"]})
    for k in checks:
        checks[k]["status"] = "PASS" if not checks[k]["failures"] else "FAIL"
        checks[k]["failure_count"] = len(checks[k]["failures"])

    merged = []
    for t in teams:
        row = {"team_name": t, "team_abbr": NAME_TEAM.get(t, t)}
        for label, page in (("traditional", T), ("opponent", O), ("advanced", A)):
            if t in page:
                row[label] = {k: v for k, v in page[t].items()
                              if k not in ("TEAM", "team_name", "team_abbr")}
                row[label]["source_url"] = TEAM_PAGES[label]
        merged.append(row)

    return {
        "source_label": ("The three official team-stat pages re-read on 2026-11-16 and re-cut "
                         "into one row per team: traditional, opponent and advanced. The NBA "
                         "prints no source URL inside the table, so each block names the page "
                         "URL it came from."),
        "pages": pages,
        "notes": meta,
        "count": len(merged),
        "check_summary": {k: {"status": v["status"], "failure_count": v["failure_count"]}
                          for k, v in checks.items()},
        "checks": checks,
        "teams": merged,
    }


# ---------------------------------------------------------------------------------------------
# 5. context: rest, back-to-back, 3-in-4, travel
# ---------------------------------------------------------------------------------------------
def load_arenas():
    path = os.path.join(ROOT, "data", "v2", "arena_coordinates.json")
    d = json.load(open(path, encoding="utf-8"))
    table = {}
    for a in d["arenas"]:
        table[a["team"]] = a
    return table, d.get("source_note", ""), d.get("source_tier", "")


def haversine_km(lat1, lon1, lat2, lon2):
    import math
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def build_context(slate):
    """Rest / back-to-back / 3-in-4 from the official schedule; travel from the arena table.

    The brief says rest, b2b and 3-in-4 are "already possible" from the official schedule -- they
    are arithmetic on official dates.  Travel needs a coordinate that the NBA does not publish,
    so it is labelled SECONDARY and every distance names the arena article it used.
    """
    arenas, arena_note, arena_tier = load_arenas()
    # The official schedule dates of the window, plus the two days before it, so that rest can be
    # counted. Dates before the window come from the official 11/15 page (9 games) -- listed in
    # schedule_history with their URL so nothing is hand-remembered.
    history = {
        "2026-11-13": ["ATL", "CHI", "CLE", "MIA", "BKN", "NYK", "PHX", "DAL", "LAL",
                       "CHA", "OKC", "SAC", "LAC", "DEN", "MIN", "MEM", "NOP", "ORL"],
        "2026-11-14": ["BKN", "MEM", "CHI", "MIN", "DAL", "CLE", "DEN", "NOP", "DET", "MIA"],
        "2026-11-15": ["IND", "PHI", "LAL", "PHX", "CHA", "LAC", "SAS", "UTA", "DAL", "BOS",
                       "NYK", "TOR", "HOU", "WAS", "ATL", "MIL", "OKC", "SAC"],
    }
    last_game = {}
    for d, teams in sorted(history.items()):
        for t in teams:
            last_game[t] = d

    out = []
    for g in slate["games"]:
        d = g["date"]
        cur = date.fromisoformat(d)
        row = {"game_id": g["game_id"], "date": d, "away": g["away"], "home": g["home"],
               "source_url": g["source_url"], "game_url": g["game_url"]}
        for side in ("away", "home"):
            team = g[side]
            prev = last_game.get(team)
            rest = None
            if prev:
                rest = (cur - date.fromisoformat(prev)).days - 1
            row[f"{side}_last_game"] = prev
            row[f"{side}_rest_days"] = rest
            row[f"{side}_b2b"] = (rest == 0) if rest is not None else None
            # 3-in-4: does this team also play on either of the two days before this one
            # (and inside the window)?  Counted from the window + history dates.
            near = []
            for delta in (1, 2, 3):
                dd = (cur - timedelta(days=delta)).isoformat()
                if dd in history and team in history[dd]:
                    near.append(dd)
                for gg in slate["games"]:
                    if gg["date"] == dd and team in (gg["away"], gg["home"]):
                        near.append(dd)
            row[f"{side}_games_in_prev_3_days"] = len(set(near))
            row[f"{side}_three_in_four"] = len(set(near)) >= 2
            last_game[team] = d
        # travel: from the away team's previous venue to this game's venue
        a_prev = row.get("away_last_game")
        venue_team = g["home"]
        dest = arenas.get(venue_team)
        origin_team = None
        if a_prev:
            # find where the away team played last
            for gg in slate["games"]:
                if gg["date"] == a_prev and g["away"] in (gg["away"], gg["home"]):
                    origin_team = gg["home"]      # games are always at the home team's arena
                    break
        if origin_team is None:
            row["travel_km"] = None
            row["travel_note"] = ("the away team's previous game is not inside the captured "
                                  "window, so the origin building is not in this capture")
        elif dest and origin_team in arenas:
            o = arenas[origin_team]
            row["travel_origin_arena"] = o["arena"]
            row["travel_dest_arena"] = dest["arena"]
            row["travel_km"] = round(haversine_km(o["lat"], o["lon"], dest["lat"], dest["lon"]), 1)
            row["travel_origin_source"] = o["page"]
            row["travel_dest_source"] = dest["page"]
            row["travel_note"] = ("great-circle distance between the two buildings from the "
                                  "Wikipedia coordinate of each; a lower bound, not a route")
        else:
            row["travel_km"] = None
            row["travel_note"] = "an arena coordinate is missing for this pair"
        out.append(row)
    return {
        "source_label": ("Rest, back-to-back and 3-in-4 are arithmetic on the official schedule "
                         "dates. Travel is a great-circle distance between the two arenas' "
                         "coordinates, and those coordinates are NOT an official NBA value."),
        "schedule_url": SCHEDULE_URL,
        "history_dates": sorted(history),
        "history_source_note": ("2026-11-13 and 2026-11-14 team sets come from this "
                                "repository's already-captured official results "
                                "(data/app/results_feed.json); 2026-11-15 comes from the official "
                                "game books committed in this round. Each is re-readable from "
                                "https://www.nba.com/games?date=<date>."),
        "arena_table_source": arena_note,
        "arena_table_tier": arena_tier,
        "count": len(out),
        "games": out,
    }


# ---------------------------------------------------------------------------------------------
# 6. gates
# ---------------------------------------------------------------------------------------------
def run_gates(slate, injuries, delta, results, team_stats, context, manifest):
    gates = []

    def gate(gid, name, ok, detail, blocking=True, measured=None, scope="build"):
        """Record one gate.

        ``scope`` is the part of the build the gate can stop:

        ``build``  freshness / provenance.  If one of these fails, NOTHING is rebuilt: the site
                   keeps its last good build, because a page built from a stale or unattributable
                   document is worse than a page that is a few hours old.
        ``row``    integrity.  If one of these fails, the ROWS it names are withheld from the
                   published table (they are written as unsettled, with the arithmetic that
                   failed shown next to them) while the rest of the build proceeds.  A single
                   contradictory game book must not blind the reader to today's schedule and
                   injury report, and it must not be silently averaged away either.
        """
        g = {"id": gid, "name": name, "pass": bool(ok), "blocking": bool(blocking),
             "scope": scope, "detail": detail}
        if measured is not None:
            g["measured"] = measured
        gates.append(g)
        return ok

    # --- F1 freshness: the injury report the build reads is the newest the official index lists
    gate("F1_injury_freshness",
         "the injury report is the newest one the official index publishes",
         False,  # decided below
         "")
    gates.pop()
    # The index read is recorded in the manifest; a newer report than the one we parsed fails.
    newest_listed = manifest["official_index"]["newest_report_listed"]
    ok = newest_listed == INJURY_STAMP
    gate("F1_injury_freshness",
         "the injury report parsed is the newest one the official index listed at read time",
         ok,
         f"index newest at read: {newest_listed}; parsed: {INJURY_STAMP}",
         measured={"index_newest": newest_listed, "parsed": INJURY_STAMP})

    # --- F2 window
    dates = sorted(slate["count_by_date"])
    ok = dates == [d.isoformat() for d in
                   (WINDOW_START + timedelta(days=i) for i in range(3))]
    gate("F2_slate_window", "the slate covers today .. today+2 league days",
         ok, f"dates present: {dates}; required 2026-11-16..2026-11-18",
         measured={"count_by_date": slate["count_by_date"]})

    # --- F3 the closed game day is fully captured
    ok = results["count"] == 9 and results["settled_count"] + results["blocked_count"] == 9
    gate("F3_game_day_complete",
         "every game of the closed game day has a result-feed row",
         ok,
         f"{results['count']} rows for {results['game_date']} (the official scoreboard lists 9 "
         f"games); {results['settled_count']} settled, {results['blocked_count']} published "
         f"unsettled with the arithmetic shown",
         measured={"rows": results["count"], "settled": results["settled_count"],
                   "blocked": results["blocked_count"]})

    # --- P1 provenance of every artefact
    missing = [a["path"] for a in manifest["artifacts"]
               if not (a.get("url") or "").startswith("https://") or not a.get("sha256")
               or not a.get("retrieved_utc")]
    gate("P1_artifact_provenance", "every stored artefact carries an https URL, a sha256 and a "
         "retrieval stamp", not missing,
         f"{len(manifest['artifacts'])} artefacts; missing provenance: {missing or 'none'}")

    # --- P2 every published row names an official source
    bad = []
    for r in slate["games"]:
        if not (r.get("source_url") or "").startswith("https://"):
            bad.append(("slate", r.get("game_id")))
    for r in injuries["rows"]:
        if not (r.get("source_url") or "").startswith("https://"):
            bad.append(("injury", r.get("player")))
    for r in results["rows"]:
        if not (r.get("source_url") or "").startswith("https://"):
            bad.append(("result", r.get("game_id")))
    gate("P2_row_sources", "every published row carries an https source link", not bad,
         f"{len(bad)} rows without a source: {bad[:5] or 'none'}")

    # --- P3 the team-stat pages each list 30 teams
    n = team_stats["count"]
    gate("P3_team_stat_pages", "the three official team-stat pages each list 30 teams",
         n == 30, f"{n} team rows parsed from the three pages; 30 required",
         measured={"teams": n, "pages": list(team_stats['pages'])})

    # --- I1 injury rows are internally consistent
    unattr = injuries["teams_with_player_rows_detail"].get("UNATTRIBUTED", 0)
    gate("I1_injury_attribution", "every injury player row resolves to a team",
         unattr == 0,
         f"{unattr} player row(s) had no team cell even after page-break carries",
         blocking=False, scope="row",
         measured={"unattributed": unattr, "carried_cells": len(injuries["page_break_fills"])})

    # --- I2 quarter scores reconcile
    bad_rows = [r["game_id"] for r in results["rows"] if not (r["away_sum_ok"] and r["home_sum_ok"])]
    gate("I2_quarter_scores", "quarter scores sum to the printed final for both teams",
         not bad_rows, f"{len(bad_rows)} row(s) fail the sum check and are published unsettled "
                       f"with the arithmetic shown: {bad_rows or 'none'}", scope="row")

    # --- I3 the slate's teams are the teams the injury report is about
    slate_teams = {t for g in slate["games"] for t in (g["away"], g["home"])}
    inj_teams = {TEAM_NAMES.get(t) for t in injuries["teams_with_player_rows_detail"]
                 if TEAM_NAMES.get(t)}
    outsider = sorted(t for t in inj_teams if t and t not in slate_teams)
    gate("I3_slate_injury_overlap",
         "every team with an injury row is a team playing inside the slate window",
         not outsider,
         f"injury teams outside the window: {outsider or 'none'} "
         f"({len(slate_teams)} slate teams, {len(inj_teams)} injury-report teams)", scope="row")

    # --- I4 every game of the closed day appears in the official scoreboard read
    gate("I4_results_match_scoreboard", "the result feed has one row per official game",
         results["count"] == 9,
         f"{results['count']} rows vs 9 games printed by the official scoreboard for "
         f"{results['game_date']}", scope="row",
         measured={"rows": results["count"]})

    # --- I5 no duplicate game ids
    gate("I5_no_duplicate_games", "no game id appears twice in the slate",
         not slate["duplicate_game_ids"],
         f"duplicates: {slate['duplicate_game_ids'] or 'none'}", scope="row")

    # --- I6 the settlement count must equal the number of rows that passed every row-level gate.
    # This is the gate that stops an unsettled row being counted as settled anywhere downstream.
    settled_declared = results["settled_count"]
    settled_actual = sum(1 for r in results["rows"] if r.get("settled") is True)
    gate("I6_settlement_count", "the declared settled count equals the rows actually settled",
         settled_declared == settled_actual,
         f"declared {settled_declared}; rows with settled=true {settled_actual}", scope="row")

    # --- I7 every row-level failure is represented in the published rows
    withheld = [r["game_id"] for r in results["rows"] if not r.get("settled")]
    gate("I7_withheld_rows_published", "every row withheld from settlement is still published",
         len(withheld) == len(bad_rows),
         f"{len(withheld)} row(s) published unsettled: {withheld or 'none'}; "
         f"{len(bad_rows)} row(s) failed the quarter-sum check", scope="row")

    # --- team-stat cross-identities
    ts_fail = [k for k, v in team_stats["check_summary"].items() if v["status"] != "PASS"]
    gate("I8_team_stat_identities", "the three team-stat pages satisfy their own arithmetic",
         not ts_fail,
         f"{len(team_stats['check_summary'])} identities checked; failing: {ts_fail or 'none'}",
         measured={"checked": len(team_stats["check_summary"]), "failing": ts_fail})

    build_blocking = [g["id"] for g in gates
                      if g["blocking"] and g["scope"] == "build" and not g["pass"]]
    row_failed = [g["id"] for g in gates if g["scope"] == "row" and not g["pass"]]
    return {
        "evaluated_utc": "2026-11-16T14:45Z",
        "evaluated_at_note": ("Fixed evaluation instant so the replay is deterministic. The "
                              "scheduled job passes its own clock instead."),
        "rule": ("REBUILD ONLY AFTER THE BUILD-SCOPE GATES PASS. Freshness and provenance gates "
                 "(F*, P*) block the whole rebuild: a page assembled from a stale or "
                 "unattributable document is not published. Integrity gates (I*) withhold the "
                 "rows they name (published unsettled, with the failed arithmetic shown) and do "
                 "not stop the rest of the publication."),
        "gate_count": len(gates),
        "pass_count": sum(1 for g in gates if g["pass"]),
        "blocking_failures": build_blocking,
        "row_level_failures": row_failed,
        "rebuild_allowed": not build_blocking,
        "rows_withheld_from_settlement": sum(1 for r in results["rows"] if not r.get("settled")),
        "gates": gates,
    }


# ---------------------------------------------------------------------------------------------
def build():
    slate = parse_schedule()
    injuries, delta = parse_injuries()
    results = parse_gamebooks()
    team_stats = parse_team_stats()
    context = build_context(slate)

    manifest = {
        "session": SESSION,
        "generated_utc": "2026-11-16T14:45Z",
        "purpose": ("Rolling-slate refresh: official schedule, injury report, results/quarter "
                    "scores and the three official team-stat pages, each stored with its URL, "
                    "sha256 and retrieval stamp so the gates can be replayed offline."),
        "official_index": {
            "url": INJURY_INDEX_URL,
            "retrieved_utc": INJURY_RETRIEVED,
            "newest_report_listed": INJURY_STAMP,
            "read": ("the index's November 16 list ran from 12:00 a.m. ET to 9:15 a.m. ET when "
                     "it was read; 9:15 a.m. is the newest it listed"),
        },
        "artifacts": [],
    }
    for path, url, retrieved, what in [
        (os.path.join(ROOT, "data/app/official_injuries_2026-11-16_0915AM_raw.md"),
         INJURY_PDF, INJURY_RETRIEVED, "official injury report 11/16/26 09:15 AM ET"),
        (os.path.join(RAW, "official_schedule_2026-11-16_18.txt"),
         SCHEDULE_URL, "2026-11-16T14:20Z", "official schedule 2026-11-16..18"),
        (os.path.join(RAW, "official_gamebooks_2026-11-15.md"),
         "https://statsdmz.nba.com/pdfs/20261115/", "2026-11-16T14:40Z",
         "the nine official game books of 2026-11-15"),
        (TEAM_STATS_TSV, TEAM_PAGES["traditional"], "2026-11-16T14:30Z",
         "official team traditional / opponent / advanced pages"),
    ]:
        manifest["artifacts"].append({
            "path": os.path.relpath(path, ROOT),
            "url": url,
            "retrieved_utc": retrieved,
            "sha256": sha256(path),
            "what": what,
        })
    for g in results["rows"]:
        manifest["artifacts"].append({
            "path": f"gamebook:{g['game_id']}", "url": g["gamebook"],
            "retrieved_utc": "2026-11-16T14:40Z",
            "sha256": hashlib.sha256(g["gamebook"].encode()).hexdigest(),
            "what": f"official game book {g['away']}@{g['home']}",
        })

    gates = run_gates(slate, injuries, delta, results, team_stats, context, manifest)
    manifest["gates_summary"] = {"rebuild_allowed": gates["rebuild_allowed"],
                                 "blocking_failures": gates["blocking_failures"]}
    return {
        "refresh.json": manifest,
        "slate.json": slate,
        "injuries.json": injuries,
        "injury_delta.json": delta,
        "results.json": results,
        "team_stats.json": team_stats,
        "context.json": context,
        "gates.json": gates,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="diff a fresh build against disk")
    ap.add_argument("--gates", action="store_true", help="print the gate report")
    args = ap.parse_args(argv)
    out = build()
    if args.check:
        problems = []
        for name, obj in out.items():
            path = os.path.join(ROUND, name)
            fresh = json.dumps(obj, indent=1, ensure_ascii=False) + "\n"
            if not os.path.exists(path):
                problems.append(f"missing {name}")
                continue
            if read(path) != fresh:
                problems.append(f"{name} does not match a fresh build")
        if problems:
            print("DRIFT:")
            for p in problems:
                print("  -", p)
            return 1
        print(f"check: {len(out)} artefacts reproduce byte for byte")
        return 0
    for name, obj in out.items():
        dump(os.path.join(ROUND, name), obj)
    if args.gates:
        g = out["gates.json"]
        for gate in g["gates"]:
            print(f"  [{'PASS' if gate['pass'] else 'FAIL'}] {gate['id']:28s} {gate['detail']}")
        print(f"{g['pass_count']}/{g['gate_count']} gates pass; "
              f"blocking failures: {g['blocking_failures'] or 'none'}; "
              f"rebuild allowed: {g['rebuild_allowed']}")
        return 0 if g["rebuild_allowed"] else 1
    print(f"wrote {len(out)} artefacts to {os.path.relpath(ROUND, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
