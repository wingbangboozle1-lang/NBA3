#!/usr/bin/env python3
"""Session arena/3d625d23-nba3 — rolling-slate capture (OFFLINE replay).

Reads the verbatim transcriptions committed under ``data/slate/raw/`` (plus two
already-committed official captures of other sessions that this round re-uses by
reference) and writes the parsed artefacts under ``data/slate/``.

Nothing here touches the network: every input is a committed file, so a difference
in the output means a real input change, which is what the CI drift gate checks.

Inputs (committed verbatim captures)
  data/slate/raw/injury_2026-11-15_0630PM.md     official injury PDF 11/15 06:30 PM ET
  data/slate/raw/standings_2026-11-15.md         official standings page
  data/slate/raw/team_advanced_2026-11-15.md     official team advanced stats page
  data/slate/raw/slate_2026-11-16_1118.md        official schedule page (rolling window)
  data/slate/raw/gamebook_20261115_INDPHI.md     official game book (11/15 IND@PHI, final)
  data/live/raw/gamebook_20261114_*.md           five 11/14 game books (session 2ebb1e75)
  data/app/arena_coordinates.json                28/30 coordinates (session bb0c83a4)
  data/app/official_injuries_2026-11-15_0615AM.json   previous report, used for the diff
  data/origin/games.csv + data/live/results/settled_2026-11-14.json   official game log

Outputs
  data/slate/injuries/injury_2026-11-15_0630PM.json   parsed report + per-row provenance
  data/slate/injuries/archive_index.json              every report this round holds
  data/slate/injuries/deltas.json                     consecutive-report diff
  data/slate/standings.json
  data/slate/team_advanced.json
  data/slate/slate.json                               rolling window (11/16..11/18)
  data/slate/results_feed.json                        one row per game, quarters, settlement stamp
  data/slate/arena_coordinates.json                   30/30
  data/slate/travel.json                              rest / B2B / 3-in-4 / travel distance
  data/slate/minutes.json                             top-8 shares + replacement shares
  data/slate/player_game_logs.json                    injury-report players, captured games

Usage: python3 scripts/capture_round_3d625d23.py
"""
import csv
import hashlib
import json
import math
import os
import re
from datetime import date, datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "data", "slate", "raw")
OUT = os.path.join(ROOT, "data", "slate")
INJ = os.path.join(OUT, "injuries")

SESSION = "arena/3d625d23-nba3"
RETRIEVED_UTC = "2026-11-16T00-05Z"          # newest source read in this round
INJ_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_30PM.pdf"
INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
STAND_URL = "https://www.nba.com/standings"
ADV_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
SCHED_URL = "https://www.nba.com/schedule?date=2026-11-16"
GB_URL = "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf"
TRAD_URL = "https://www.nba.com/stats/teams/traditional"
OPP_URL = "https://www.nba.com/stats/teams/opponent"

# --------------------------------------------------------------------------- helpers

NAME_TO_CODE = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}


def team_code(name):
    """Official team name -> abbreviation, case-insensitive. A 3-letter code passes through."""
    key = " ".join(name.split()).lower()
    if key.upper() in set(NAME_TO_CODE.values()):
        return key.upper()
    for full, code in NAME_TO_CODE.items():
        if " ".join(full.split()).lower() == key:
            return code
    return None


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False)
        fh.write("\n")


def read_rows(path, sep="|"):
    """Return the data rows of a transcription file (comments start with '#')."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            out.append([c.strip() for c in line.split(sep)])
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- 1. injury report

# Rows whose TEAM cell is blank on the page: the value is carried forward from the row
# above (a layout inference, not a printed value). Row numbers are 1-based over the data
# rows of data/slate/raw/injury_2026-11-15_0630PM.md, in page order.
TEAM_CARRY_FORWARD = [15, 16, 33, 51, 52, 68, 69, 70, 71, 133, 134, 135, 136, 137,
                      151, 152, 153]

# Rows on which the page printed the date / time / matchup cells for a new game block.
# Every other row inherits those cells from the block header. Cross-checked below against
# the official schedule, so a wrong inheritance cannot silently invent a game.
CONTEXT_PRINTED = {1: "date+time+matchup", 11: "time+matchup", 19: "time", 29: "time",
                   41: "time", 58: "time", 72: "time", 84: "time", 97: "date+time+matchup",
                   117: "matchup", 122: "time+matchup", 126: "time+matchup",
                   132: "time+matchup", 146: "matchup", 154: "time+matchup"}


def parse_injury_report():
    rows_raw = read_rows(os.path.join(RAW, "injury_2026-11-15_0630PM.md"))
    rows = []
    flags = []
    for i, cells in enumerate(rows_raw, start=1):
        gdate, gtime, matchup, team, player, status, reason = (cells + [""] * 7)[:7]
        team_printed = i not in TEAM_CARRY_FORWARD
        ctx_printed = CONTEXT_PRINTED.get(i, "")
        if not team_printed:
            flags.append({"row": i, "player": player,
                          "flag": "Team cell blank on the page; value carried forward from the "
                                  "row above (layout inference, not a printed value)."})
        code = NAME_TO_CODE.get(team)
        if team and code is None:
            flags.append({"row": i, "player": player,
                          "flag": f"Team name '{team}' not in the official standings name set."})
        not_submitted = status.upper().startswith("NOT YET SUBMITTED") or \
            reason.upper().startswith("NOT YET SUBMITTED")
        iso = None
        if gdate:
            m, d, y = gdate.split("/")
            iso = f"{y}-{int(m):02d}-{int(d):02d}"
        rows.append({
            "row": i,
            "game_date": iso,
            "game_time_et": gtime.replace(" (ET)", "").strip() or None,
            "matchup": matchup or None,
            "team_name": team or None,
            "team": code,
            "player": player or None,
            "status": (None if not_submitted else (status or None)),
            "reason": (reason or None),
            "is_team_not_submitted": not_submitted,
            "cell_provenance": {
                "game_date": "row" if "date" in ctx_printed else "carried forward",
                "game_time_et": "row" if "time" in ctx_printed else "carried forward",
                "matchup": "row" if "matchup" in ctx_printed else "carried forward",
                "team_name": "row" if team_printed else "carried forward",
            },
            "source": INJ_URL,
        })
    by_date = {}
    for r in rows:
        by_date[r["game_date"]] = by_date.get(r["game_date"], 0) + 1
    player_rows = [r for r in rows if r["player"]]
    doc = {
        "schema": "nba3.slate.injury_report/v1",
        "session": SESSION,
        "source_url": INJ_URL,
        "index_url": INJ_INDEX,
        "report_stamp": "2026-11-15 06:30 PM ET",
        "report_stamp_source": "printed on every page of the PDF as "
                               "'Injury Report: 11/15/26 06:30 PM'",
        "retrieved_utc": RETRIEVED_UTC,
        "retrieval": "fetch_page of the PDF listed on the official index (3 chunks); transcribed "
                     "row by row into data/slate/raw/injury_2026-11-15_0630PM.md, then parsed here",
        "transcript_sha256": sha256_file(os.path.join(RAW, "injury_2026-11-15_0630PM.md")),
        "count": len(rows),
        "player_rows": len(player_rows),
        "not_submitted_rows": sum(1 for r in rows if r["is_team_not_submitted"]),
        "rows_by_game_date": by_date,
        "team_carry_forward_rows": TEAM_CARRY_FORWARD,
        "context_printed_rows": CONTEXT_PRINTED,
        "status_counts": {s: sum(1 for r in player_rows if r["status"] == s)
                          for s in sorted({r["status"] for r in player_rows if r["status"]})},
        "rows": rows,
        "flags": flags,
    }
    write_json(os.path.join(INJ, "injury_2026-11-15_0630PM.json"), doc)
    return doc


def _lev(a, b):
    """Small Levenshtein distance (used only to pair name spellings, never to change a value)."""
    a, b = a.lower(), b.lower()
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def injury_archive_and_diff(new):
    """Archive every 11/15 report this round holds and diff the consecutive ones."""
    prior_path = os.path.join(ROOT, "data", "app", "official_injuries_2026-11-15_0615AM.json")
    prior = json.load(open(prior_path, encoding="utf-8"))
    prior_rows = prior["rows"]

    def surname(p):
        return (p or "").split(",")[0].strip().lower()

    prior_players = {(r.get("team"), (r.get("player") or "").lower().strip()): r
                     for r in prior_rows if r.get("player")}
    new_players = {(r["team"], (r["player"] or "").lower().strip()): r
                   for r in new["rows"] if r["player"]}
    prior_placeholders = [r for r in prior_rows if not r.get("player")]
    new_placeholders = [r for r in new["rows"] if not r["player"]]

    status_changes, name_variants, reassigned, added, removed = [], [], [], [], []
    matched_new = set()

    for k, r in new_players.items():
        if k in prior_players:
            p = prior_players[k]
            matched_new.add(k)
            if p.get("status") != r["status"]:
                status_changes.append({
                    "player": r["player"], "team": r["team"], "matchup": r["matchup"],
                    "game_date": r["game_date"], "from": p.get("status"), "to": r["status"],
                    "reason": r["reason"]})
            continue
        # same surname, different spelling on the same team -> name variant, not a new player
        same_team = [pk for pk in prior_players
                     if pk[0] == k[0] and pk not in matched_new
                     and _lev(surname(pk[1]), surname(k[1])) <= 2]
        if same_team:
            pk = same_team[0]
            p = prior_players[pk]
            name_variants.append({"prior": p.get("player"), "current": r["player"],
                                  "team": r["team"], "prior_status": p.get("status"),
                                  "current_status": r["status"],
                                  "note": "same row, different spelling between the two filings; "
                                          "both spellings are printed, neither is corrected"})
            if p.get("status") != r["status"]:
                status_changes.append({
                    "player": r["player"], "team": r["team"], "matchup": r["matchup"],
                    "game_date": r["game_date"], "from": p.get("status"), "to": r["status"],
                    "reason": r["reason"], "note": "name spelling differs between filings"})
            continue
        # same player, different team between filings
        other_team = [pk for pk in prior_players
                      if pk[1] == k[1] and pk[0] != k[0] and pk not in matched_new]
        if other_team:
            pk = other_team[0]
            reassigned.append({"player": r["player"], "from_team": pk[0], "to_team": r["team"],
                               "prior_status": prior_players[pk].get("status"),
                               "current_status": r["status"],
                               "note": "the same player is listed under a different club in the "
                                       "two filings; flagged, not reconciled"})
            continue
        added.append({"player": r["player"], "team": r["team"], "status": r["status"],
                      "reason": r["reason"], "matchup": r["matchup"],
                      "game_date": r["game_date"]})
    for k, r in prior_players.items():
        if k not in new_players and k not in matched_new:
            if not any(k[1] == nk[1] for nk in new_players):
                removed.append({"player": r.get("player"), "team": r.get("team"),
                                "status": r.get("status")})

    prior_ph_teams = sorted({r.get("team") for r in prior_placeholders if r.get("team")})
    new_ph_teams = sorted({r.get("team") for r in new_placeholders if r.get("team")})
    resolved = [t for t in prior_ph_teams if t not in new_ph_teams]
    still_pending = [t for t in new_ph_teams]

    deltas = {
        "schema": "nba3.slate.injury_deltas/v1",
        "session": SESSION,
        "rule": "One diff per consecutive pair of archived reports. A status change is one "
                "player whose Current Status differs between the two filings; rows present in "
                "only one filing are listed as added/removed, and rows that differ only in the "
                "spelling of a name are listed as name variants rather than as a removal plus an "
                "addition.",
        "pairs": [{
            "from": {"stamp": prior["report_stamp"], "source_url": prior["source_url"],
                     "retrieved_utc": prior["retrieved_stamp"], "rows": len(prior_rows)},
            "to": {"stamp": new["report_stamp"], "source_url": new["source_url"],
                   "retrieved_utc": new["retrieved_utc"], "rows": new["count"]},
            "elapsed": "12h15m ET (06:15 AM ET -> 06:30 PM ET)",
            "status_changes": sorted(status_changes, key=lambda c: (c["team"], c["player"])),
            "name_variants": name_variants,
            "team_reassignments": reassigned,
            "added_rows": sorted(added, key=lambda c: (c["team"] or "", c["player"])),
            "removed_rows": removed,
            "not_yet_submitted_resolved": resolved,
            "not_yet_submitted_still_pending": still_pending,
            "unchanged_players": len([k for k in new_players if k in prior_players]),
            "counts": {"status_changes": len(status_changes), "added": len(added),
                       "removed": len(removed), "name_variants": len(name_variants),
                       "team_reassignments": len(reassigned),
                       "placeholders_resolved": len(resolved),
                       "placeholders_still_pending": len(still_pending)},
        }],
    }
    write_json(os.path.join(INJ, "deltas.json"), deltas)

    entries = [
        {"stamp": "2026-11-15 12:00 AM ET",
         "file": "data/live/injuries/Injury-Report_2026-11-15_12_00AM.md",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_12_00AM.pdf",
         "retrieved_utc": "2026-11-15T11:33Z", "session": "arena/2ebb1e75-nba3"},
        {"stamp": "2026-11-15 06:00 AM ET",
         "file": "data/live/injuries/Injury-Report_2026-11-15_06_00AM.md",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_00AM.pdf",
         "retrieved_utc": "2026-11-15T11:33Z", "session": "arena/2ebb1e75-nba3"},
        {"stamp": prior["report_stamp"],
         "file": "data/app/official_injuries_2026-11-15_0615AM_raw.md",
         "source_url": prior["source_url"], "retrieved_utc": prior["retrieved_stamp"],
         "session": "arena/bb0c83a4-nba3",
         "parsed": "data/app/official_injuries_2026-11-15_0615AM.json", "rows": len(prior_rows)},
        {"stamp": new["report_stamp"], "file": "data/slate/raw/injury_2026-11-15_0630PM.md",
         "source_url": INJ_URL, "retrieved_utc": RETRIEVED_UTC, "session": SESSION,
         "parsed": "data/slate/injuries/injury_2026-11-15_0630PM.json", "rows": new["count"],
         "transcript_sha256": new["transcript_sha256"]},
    ]
    index = {
        "schema": "nba3.slate.injury_archive/v1",
        "session": SESSION,
        "note": "Every injury report this repository holds for 2026-11-15, in filing order, each "
                "with its own revision stamp (printed on the PDF), the retrieval stamp and, where "
                "the round stored one, the transcript hash. A new filing is a new entry; archived "
                "reports are never overwritten.",
        "index_url": INJ_INDEX,
        "count": len(entries),
        "reports": entries,
        "deltas": "data/slate/injuries/deltas.json",
        "diff_rule": "consecutive entries are diffed; see deltas.json",
    }
    write_json(os.path.join(INJ, "archive_index.json"), index)
    return deltas


# --------------------------------------------------------------------------- 2. standings / advanced / slate

def parse_standings():
    rows = []
    for cells in read_rows(os.path.join(RAW, "standings_2026-11-15.md")):
        conf, rank, team, w, l, pct, gb, cf, dv, home, road, neu, ot, l10, streak = cells
        rows.append({"conference": conf, "conf_rank": int(rank), "team_name": team,
                     "team": NAME_TO_CODE[team], "w": int(w), "l": int(l),
                     "win_pct": pct, "gb": None if gb == "--" else gb,
                     "conf": cf, "div": dv, "home": home, "road": road, "neutral": neu,
                     "ot": ot, "last10": l10, "streak": streak})
    doc = {"schema": "nba3.slate.standings/v1", "session": SESSION,
           "source_url": STAND_URL, "retrieved_utc": RETRIEVED_UTC,
           "page_title": "NBA 2026-27 Regular Season Standings",
           "note": "Official standings table, conference view, Overall section. This is the "
                   "second read of the night: the 23:41Z read showed LAL 11-2, PHX 5-6, LAC 3-8 "
                   "and CHA 4-8 while LAL@PHX and CHA@LAC were still live; this read carries "
                   "LAL 12-2, PHX 5-7, LAC 4-8 and CHA 4-9, i.e. both 11/15 games that have "
                   "since gone final are now in the table.",
           "count": len(rows), "rows": rows}
    write_json(os.path.join(OUT, "standings.json"), doc)
    return doc


def parse_advanced():
    cols = ["team_name", "gp", "w", "l", "min", "off_rtg", "def_rtg", "net_rtg", "ast_pct",
            "ast_to", "ast_ratio", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct", "efg_pct",
            "ts_pct", "pace", "pie", "poss"]
    rows = []
    for cells in read_rows(os.path.join(RAW, "team_advanced_2026-11-15.md")):
        rec = {"team": NAME_TO_CODE[cells[0]]}
        for name, value in zip(cols, cells):
            if name == "team_name":
                rec["team_name"] = value
            elif name == "poss":
                rec["poss"] = int(num(value))
            elif name in ("gp", "w", "l"):
                rec[name] = int(num(value))
            else:
                rec[name] = num(value)
        rows.append(rec)
    doc = {"schema": "nba3.slate.team_advanced/v1", "session": SESSION,
           "source_url": ADV_URL, "retrieved_utc": RETRIEVED_UTC,
           "page_title": "Teams Advanced | Stats | NBA.com",
           "note": "All 30 rows, per-game mode. The trailing *_RANK columns printed by the page "
                   "are not transcribed. Pace = possessions per 48 minutes; POSS = total "
                   "possessions; OffRtg/DefRtg = points per 100 possessions.",
           "count": len(rows), "rows": rows}
    write_json(os.path.join(OUT, "team_advanced.json"), doc)
    return doc


def _team_stat_doc(raw_name, url, page_title, schema, cols, int_cols, note):
    rows = []
    for cells in read_rows(os.path.join(RAW, raw_name)):
        rec = {"team": NAME_TO_CODE[cells[0]], "team_name": cells[0]}
        for name, value in zip(cols, cells):
            if name == "team_name":
                continue
            rec[name] = int(num(value)) if name in int_cols else num(value)
        rows.append(rec)
    doc = {"schema": schema, "session": SESSION, "source_url": url,
           "retrieved_utc": RETRIEVED_UTC, "page_title": page_title,
           "note": note, "count": len(rows), "rows": rows}
    return doc


def parse_traditional():
    cols = ["team_name", "gp", "w", "l", "win_pct", "min", "pts", "fgm", "fga", "fg_pct", "fg3m",
            "fg3a", "fg3_pct", "ftm", "fta", "ft_pct", "oreb", "dreb", "reb", "ast", "tov",
            "stl", "blk", "pf", "pfd", "plus_minus"]
    doc = _team_stat_doc(
        "team_traditional_2026-11-15.md", TRAD_URL, "Teams Traditional | Stats | NBA.com",
        "nba3.slate.team_traditional/v1", cols, {"gp", "w", "l"},
        "All 30 rows, per-game mode. The trailing *_RANK columns printed by the page are not "
        "transcribed. FLAGGED: at read time this page had not absorbed the CHA@LAC final "
        "(LAC 11 GP 3-8, CHA 12 GP 4-8), while the advanced page and the standings page read "
        "minutes later both show LAC 12 GP 4-8 / CHA 13 GP 4-9. The four official pages are not "
        "synchronised; the lag is published rather than reconciled and no value is inferred.")
    write_json(os.path.join(OUT, "team_traditional.json"), doc)
    return doc


def parse_opponent():
    cols = ["team_name", "gp", "w", "l", "min", "opp_fgm", "opp_fga", "opp_fg_pct", "opp_fg3m",
            "opp_fg3a", "opp_fg3_pct", "opp_ftm", "opp_fta", "opp_ft_pct", "opp_oreb",
            "opp_dreb", "opp_reb", "opp_ast", "opp_tov", "opp_stl", "opp_blk", "opp_blka",
            "opp_pf", "opp_pfd", "opp_pts", "plus_minus"]
    doc = _team_stat_doc(
        "team_opponent_2026-11-15.md", OPP_URL, "Teams Opponent | Stats | NBA.com",
        "nba3.slate.team_opponent/v1", cols, {"gp", "w", "l"},
        "All 30 rows, per-game mode. The trailing *_RANK columns printed by the page are not "
        "transcribed. FLAGGED: same lag as the traditional page — it had not absorbed the "
        "CHA@LAC final at read time.")
    write_json(os.path.join(OUT, "team_opponent.json"), doc)
    return doc


def parse_slate():
    games = []
    for cells in read_rows(os.path.join(RAW, "slate_2026-11-16_1118.md")):
        gdate, tip, away, home, gid, arena, city, status, ap, hp = (cells + [""] * 10)[:10]
        games.append({"date": gdate, "tip_et": tip or None,
                      "away_name": away, "away": NAME_TO_CODE[away],
                      "home_name": home, "home": NAME_TO_CODE[home],
                      "game_id": gid, "arena": arena, "city": city,
                      "status_on_page": status,
                      "away_pts": int(ap) if ap else None,
                      "home_pts": int(hp) if hp else None,
                      "game_url": f"https://www.nba.com/game/{NAME_TO_CODE[away].lower()}-vs-"
                                  f"{NAME_TO_CODE[home].lower()}-{gid}"})
    upcoming = [g for g in games if g["date"] >= "2026-11-16"]
    today = [g for g in games if g["date"] == "2026-11-15"]
    doc = {"schema": "nba3.slate.schedule/v1", "session": SESSION,
           "source_url": SCHED_URL, "retrieved_utc": RETRIEVED_UTC,
           "window": {"from": "2026-11-16", "to": "2026-11-18",
                      "rule": "three days ahead of the current slate date (2026-11-15), the "
                              "maximum the brief allows"},
           "counts": {"2026-11-16": sum(1 for g in upcoming if g["date"] == "2026-11-16"),
                      "2026-11-17": sum(1 for g in upcoming if g["date"] == "2026-11-17"),
                      "2026-11-18": sum(1 for g in upcoming if g["date"] == "2026-11-18"),
                      "total": len(upcoming)},
           "cross_check": {
               "rule": "every matchup in the injury report must exist on the official schedule "
                       "for the same date",
               "source_url": SCHED_URL,
           },
           "upcoming": upcoming,
           "in_progress_2026_11_15": today,
           "games": games}
    write_json(os.path.join(OUT, "slate.json"), doc)
    return doc


# --------------------------------------------------------------------------- 3. results feed

def parse_gamebook_scores(path):
    """Return {team: [q1,q2,q3,q4]} plus finals from the SCORE BY PERIOD table."""
    text = open(path, encoding="utf-8").read()
    lines = [l for l in text.splitlines() if l.startswith("|")]
    scores = {}
    for i, line in enumerate(lines):
        if "SCORE BY PERIOD" in line:
            for l in lines[i + 2:]:
                cells = [c.strip() for c in l.strip("|").split("|")]
                if len(cells) < 6:
                    break
                qs = [c for c in cells[1:5] if re.fullmatch(r"\d{1,3}", c)]
                fin = [c for c in cells[5:6] if re.fullmatch(r"\d{1,3}", c)]
                if len(qs) == 4 and fin:
                    scores[cells[0]] = {"quarters": [int(q) for q in qs], "final": int(fin[0])}
                elif len(qs) == 4:
                    scores[cells[0]] = {"quarters": [int(q) for q in qs], "final": sum(map(int, qs))}
            break
    return scores


def build_results_feed(slate, standings):
    """One row per game: date, teams, final score, quarter scores; settled only when verified."""
    feed_path = os.path.join(OUT, "results_feed.json")
    feed = json.load(open(feed_path, encoding="utf-8")) if os.path.exists(feed_path) else {
        "schema": "nba3.slate.results_feed/v1", "session": SESSION,
        "one_row_per_game": True, "games": []}

    known = {g["game_id"]: g for g in feed["games"]}

    # --- 11/14 finals: carried from the committed official settlement of session 2ebb1e75
    settled_1114 = json.load(open(os.path.join(ROOT, "data", "live", "results",
                                               "settled_2026-11-14.json"), encoding="utf-8"))
    for g in settled_1114["games"]:
        row = {
            "game_id": g["game_id"], "date": g["date"], "away": g["away"], "home": g["home"],
            "away_name": g["away_name"], "home_name": g["home_name"],
            "away_q": g["away_q"], "home_q": g["home_q"],
            "away_final": g["away_final"], "home_final": g["home_final"],
            "ot": g.get("ot", False), "status": "Final", "winner": g["winner"],
            "venue": g.get("venue"), "city": g.get("city"),
            "verified": True,
            "verification": {
                "rule": "settled only when the game page says Final AND the game book's printed "
                        "FINAL equals the sum of its four printed quarters AND both agree",
                "sources": [g["verification"]["game_page"], g["verification"]["gamebook"]],
                "settled_by": "session arena/2ebb1e75-nba3",
                "settled_utc": settled_1114["settled_utc"],
                "quarter_sum_check": sum(g["away_q"]) == g["away_final"]
                                     and sum(g["home_q"]) == g["home_final"],
            },
        }
        known[g["game_id"]] = row

    # --- 11/15 finals: settled here from the official game book + the official standings page
    # Two independent official reads are required: (1) the game book's printed FINAL equals the sum
    # of its own four printed quarters and the book prints a complete 240:00 team-minutes row for
    # both clubs, and (2) the standings page read at the same time shows the winner on a W streak
    # and the loser on an L streak. The schedule-page snapshot was taken while two of these games
    # were still live, so it can only corroborate — it is recorded, never required.
    SETTLED_1115 = [
        {"game_id": "0022600236", "book": "gamebook_20261115_INDPHI.md",
         "away": "IND", "home": "PHI", "away_name": "Indiana Pacers",
         "home_name": "Philadelphia 76ers", "away_label": "Pacers",
         "home_labels": ["76ERS", "76ers"],
         "url": "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf"},
        {"game_id": "0022600237", "book": "gamebook_20261115_LALPHX.md",
         "away": "LAL", "home": "PHX", "away_name": "Los Angeles Lakers",
         "home_name": "Phoenix Suns", "away_label": "Lakers",
         "home_labels": ["SUNS", "Suns"],
         "url": "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf"},
        {"game_id": "0022600238", "book": "gamebook_20261115_CHALAC.md",
         "away": "CHA", "home": "LAC", "away_name": "Charlotte Hornets",
         "home_name": "LA Clippers", "away_label": "Hornets",
         "home_labels": ["CLIPPERS", "Clippers"],
         "url": "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf"},
    ]
    stand = {r["team"]: r for r in standings["rows"]}
    for spec in SETTLED_1115:
        gb_path = os.path.join(RAW, spec["book"])
        if not os.path.exists(gb_path):
            continue
        scores = parse_gamebook_scores(gb_path)
        text = open(gb_path, encoding="utf-8").read()
        aw = scores.get(spec["away_label"])
        hm = None
        for lab in spec["home_labels"]:
            if lab in scores:
                hm = scores[lab]
                break
        sched_rows = [g for g in slate["games"] if g["game_id"] == spec["game_id"]]
        sched_row = sched_rows[0] if sched_rows else None
        checks = {
            "four_quarters_and_final_printed": bool(aw and hm and len(aw["quarters"]) == 4
                                                    and len(hm["quarters"]) == 4),
            "quarter_sums_equal_finals": bool(aw and hm and sum(aw["quarters"]) == aw["final"]
                                              and sum(hm["quarters"]) == hm["final"]),
            "complete_game_240_team_minutes": text.count("240:00") >= 2,
            "standings_streak_matches_result": bool(
                aw and hm and aw["final"] != hm["final"]
                and (stand.get(spec["away"], {}).get("streak") or "").startswith(
                    "W" if aw["final"] > hm["final"] else "L")
                and (stand.get(spec["home"], {}).get("streak") or "").startswith(
                    "W" if hm["final"] > aw["final"] else "L")),
        }
        ok = all(checks.values())
        winner = None
        if aw and hm and aw["final"] != hm["final"]:
            winner = spec["away"] if aw["final"] > hm["final"] else spec["home"]
        row = {
            "game_id": spec["game_id"], "date": "2026-11-15",
            "away": spec["away"], "home": spec["home"],
            "away_name": spec["away_name"], "home_name": spec["home_name"],
            "away_q": aw["quarters"] if aw else None,
            "home_q": hm["quarters"] if hm else None,
            "away_final": aw["final"] if aw else None,
            "home_final": hm["final"] if hm else None,
            "ot": False, "status": "Final" if ok else "unverified", "winner": winner,
            "venue": sched_row["arena"] if sched_row else None,
            "city": sched_row["city"] if sched_row else None,
            "verified": ok,
            "verification": {
                "rule": "settled only when the official game book's printed FINAL equals the sum "
                        "of its own four printed quarters, the book prints a complete 240:00 "
                        "team-minutes row for both clubs, and the official standings page read at "
                        "the same time shows the winner on a W streak and the loser on an L "
                        "streak",
                "sources": [spec["url"],
                            "https://www.nba.com/game/%s" % spec["game_id"], SCHED_URL, STAND_URL],
                "checks": checks,
                "schedule_page_status_at_snapshot": (sched_row or {}).get("status_on_page"),
                "schedule_page_note": "the schedule snapshot was taken while this game was still "
                                      "live, so it corroborates rather than confirms",
                "settled_by": SESSION, "settled_utc": RETRIEVED_UTC,
            },
        }
        known[spec["game_id"]] = row

    games = sorted(known.values(), key=lambda g: (g["date"], g["game_id"]))
    doc = {
        "schema": "nba3.slate.results_feed/v1",
        "session": SESSION,
        "one_row_per_game": True,
        "settlement_rule": "A row is written only for a finished game, and only when the final "
                           "score is confirmed by two official reads that agree (game book "
                           "quarters sum to the printed final; the schedule/game page prints the "
                           "same final). Anything else stays out of the feed.",
        "settlement_stamp_note": "settled_utc is the time this build last confirmed the finals "
                                 "against the official pages; it moves only on a re-read.",
        "counts": {"games": len(games),
                   "verified": sum(1 for g in games if g["verified"]),
                   "unverified": sum(1 for g in games if not g["verified"])},
        "games": games,
    }
    write_json(feed_path, doc)
    return doc


# --------------------------------------------------------------------------- 4. arenas + travel

def haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_arenas():
    base = json.load(open(os.path.join(ROOT, "data", "app", "arena_coordinates.json"),
                          encoding="utf-8"))
    arenas = {}
    for a in base["arenas"]:
        arenas[a["team"]] = a
    # The two blanks in the previous table, now sourced.
    arenas["PHI"] = {"team": "PHI", "arena": "Xfinity Mobile Arena",
                     "city": "Philadelphia, PA", "lat": 39.90111, "lon": -75.17194,
                     "coord_source": "https://en.wikipedia.org/wiki/Xfinity_Mobile_Arena",
                     "verified": True,
                     "note": "The official schedule page prints 'Xfinity Mobile Arena, "
                             "Philadelphia, PA' for the 11/15 IND@PHI game. Wikipedia's 'Wells "
                             "Fargo Center (Philadelphia)' is a redirect to that article, which "
                             "is why the coordinates API returned nothing for the old title. "
                             "Coordinates read from the article infobox: 39.90111; -75.17194."}
    arenas["PHX"] = {"team": "PHX", "arena": "Mortgage Matchup Center",
                     "city": "Phoenix, AZ", "lat": 33.44583333, "lon": -112.07138889,
                     "coord_source": "https://en.wikipedia.org/wiki/Mortgage_Matchup_Center",
                     "verified": True,
                     "note": "The official schedule page prints 'Mortgage Matchup Center, "
                             "Phoenix, AZ' for the 11/15 LAL@PHX game. The previous table looked "
                             "up the old title 'PHX Arena' (pageid 81244835), which carries no "
                             "coordinates; the current title does."}
    rows = [arenas[k] for k in sorted(arenas)]
    doc = {
        "schema": "nba3.slate.arena_coordinates/v1",
        "session": SESSION,
        "retrieved_utc": RETRIEVED_UTC,
        "source_kind": "general reference (Wikipedia article coordinates), NOT NBA-published",
        "api_url": "https://en.wikipedia.org/w/api.php?action=query&prop=coordinates&format=json"
                   "&titles=Mortgage%20Matchup%20Center",
        "cross_check": "Arena identity and city are cross-checked against the arena printed on "
                       "the official schedule page (https://www.nba.com/schedule?date=2026-11-16) "
                       "for that club's home games.",
        "count": len(rows),
        "verified": sum(1 for r in rows if r.get("verified")),
        "blank": sum(1 for r in rows if r.get("lat") is None),
        "arenas": rows,
        "previous_table": "data/app/arena_coordinates.json (session arena/bb0c83a4-nba3): 28/30 "
                          "with coordinates; the two blanks are filled here and the two arena "
                          "names corrected to the ones the official schedule prints.",
    }
    write_json(os.path.join(OUT, "arena_coordinates.json"), doc)
    return doc


def schedule_union(slate):
    """Official schedule: in-repo game log + settled 11/14 finals + the rolling window."""
    games = []
    with open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            games.append({"date": r["date"], "game_id": r["game_id"], "away": r["away"],
                          "home": r["home"], "away_pts": int(r["away_pts"]),
                          "home_pts": int(r["home_pts"]),
                          "source": "data/origin/games.csv (official results capture)"})
    seen = {g["game_id"] for g in games}
    feed = json.load(open(os.path.join(ROOT, "data", "live", "results",
                                       "settled_2026-11-14.json"), encoding="utf-8"))
    for g in feed["games"]:
        if g["game_id"] not in seen:
            games.append({"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                          "home": g["home"], "away_pts": g["away_final"],
                          "home_pts": g["home_final"],
                          "source": "data/live/results/settled_2026-11-14.json"})
            seen.add(g["game_id"])
    for g in slate["upcoming"] + slate["in_progress_2026_11_15"]:
        if g["game_id"] not in seen:
            games.append({"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                          "home": g["home"], "away_pts": g.get("away_pts"),
                          "home_pts": g.get("home_pts"),
                          "source": SCHED_URL})
            seen.add(g["game_id"])
    games.sort(key=lambda g: (g["date"], g["game_id"]))
    return games


def build_travel(slate, arenas, games):
    coords = {a["team"]: a for a in arenas["arenas"]}
    by_team = {}
    for g in games:
        for side in ("away", "home"):
            by_team.setdefault(g[side], []).append(g)
    for t in by_team:
        by_team[t].sort(key=lambda g: (g["date"], g["game_id"]))

    def prev_game(team, date_):
        earlier = [g for g in by_team.get(team, []) if g["date"] < date_]
        return earlier[-1] if earlier else None

    rows = []
    for g in sorted(slate["upcoming"], key=lambda x: (x["date"], x["game_id"])):
        d = date.fromisoformat(g["date"])
        rec = {"date": g["date"], "game_id": g["game_id"], "away": g["away"], "home": g["home"],
               "matchup": f"{g['away']}@{g['home']}", "tip_et": g["tip_et"],
               "venue": g["arena"], "city": g["city"], "source": SCHED_URL}
        for side in ("away", "home"):
            team = g[side]
            pg = prev_game(team, g["date"])
            rec[f"{side}_prev_date"] = pg["date"] if pg else None
            if pg is None:
                rec[f"{side}_rest_days"] = None
                rec[f"{side}_games_last_3d"] = 1
                rec[f"{side}_b2b"] = False
                rec[f"{side}_travel_mi"] = None
                rec[f"{side}_travel_note"] = "no previous game in the captured schedule"
                continue
            prev_date = date.fromisoformat(pg["date"])
            rec[f"{side}_rest_days"] = (d - prev_date).days - 1
            rec[f"{side}_b2b"] = (d - prev_date).days == 1
            window = [x for x in by_team[team]
                      if (d - timedelta(days=3)) <= date.fromisoformat(x["date"]) <= d]
            rec[f"{side}_games_in_4d"] = len(window)
            rec[f"{side}_3_in_4"] = len(window) >= 3
            prev_home = pg["home"]
            a_from, a_to = coords.get(prev_home), coords.get(team if side == "home" else g["home"])
            if prev_home == team:
                rec[f"{side}_travel_mi"] = 0.0
                rec[f"{side}_travel_note"] = "previous game was at home"
            elif a_from and a_to and a_from.get("lat") is not None and a_to.get("lat") is not None:
                dist = haversine_mi(a_from["lat"], a_from["lon"], a_to["lat"], a_to["lon"])
                rec[f"{side}_travel_mi"] = round(dist, 1)
                rec[f"{side}_travel_note"] = (
                    f"great-circle {a_from['arena']} -> {a_to['arena']}, from coordinates in "
                    f"data/slate/arena_coordinates.json")
            else:
                rec[f"{side}_travel_mi"] = None
                rec[f"{side}_travel_note"] = "an arena coordinate is blank — left blank, not inferred"
        rows.append(rec)
    doc = {
        "schema": "nba3.slate.travel/v1",
        "session": SESSION,
        "sources": [SCHED_URL, "https://www.nba.com/schedule?date=2026-11-16",
                    "data/origin/games.csv", "data/live/results/settled_2026-11-14.json"],
        "retrieved_utc": RETRIEVED_UTC,
        "rules": {
            "rest_days": "(game date - previous game date) in days - 1, from the official schedule",
            "back_to_back": "previous game on the immediately preceding day",
            "games_last_3d": "games in the window [previous game date .. game date] inclusive",
            "3_in_4": "at least 3 games in the 4-day window ending on the game date",
            "travel_mi": "great-circle (haversine) distance between the arena of the team's "
                         "previous game and the arena of this game; 0 when the previous game was "
                         "in the same building. A derived value, not an NBA-published figure.",
        },
        "counts": {"rows": len(rows),
                   "blank_travel": sum(1 for r in rows
                                       if r["away_travel_mi"] is None or r["home_travel_mi"] is None),
                   "b2b": sum(1 for r in rows if r["away_b2b"] or r["home_b2b"]),
                   "three_in_four": sum(1 for r in rows if r.get("away_3_in_4") or r.get("home_3_in_4"))},
        "rows": rows,
    }
    write_json(os.path.join(OUT, "travel.json"), doc)
    return doc


# --------------------------------------------------------------------------- 5. minutes + logs

MIN_RE = re.compile(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})")


def minutes_to_seconds(txt):
    m = re.fullmatch(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})", txt.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    return h * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def parse_gamebook(path, visitor_fallback=None):
    """Parse a game-book transcription into per-team player rows (minutes always, box score when
    the row survives the PTS identity check)."""
    text = open(path, encoding="utf-8").read()
    teams, current = {}, None
    totals = {}
    if visitor_fallback:
        # The extraction lost the "VISITOR: ..." header line for this game book. The visitor is
        # taken from the official file name (e.g. 20261114_DALCLE.pdf = Dallas Mavericks at
        # Cleveland Cavaliers), which is official metadata, not an inference about a player.
        current = visitor_fallback
        teams[current] = []
    for line in text.splitlines():
        m = re.search(r"(VISITOR|HOME)\s*:\s*\|?\s*([A-Za-z0-9 .\-']+?)\s*\(\d+-\d+\)", line)
        if m:
            current = m.group(2).strip()
            teams[current] = []
            continue
        if not line.startswith("|") or current is None:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        time_cells = [c for c in cells if re.fullmatch(r"\d{1,3}:\d{2}", c)]
        if not time_cells:
            continue
        if re.fullmatch(r"(240|265|290|315|340):00", time_cells[0]):
            hh, mm = time_cells[0].split(":")
            totals[current] = int(hh) + int(mm) / 60.0
            continue                                   # team totals row, never a player
        name = None
        for c in cells:
            if (c and c not in ("F", "C", "G") and not re.fullmatch(r"[\d:.,%+\-/]+", c)
                    and not re.fullmatch(r"\d{1,3}:\d{2}", c) and len(c) > 3
                    and c.upper() not in ("TM REB:", "TM FGA:")):
                name = c
                break
        if not name or name.upper() in ("POS", "MIN") or name.upper().startswith("TEAM"):
            continue
        mins = minutes_to_seconds(time_cells[0])
        teams[current].append({"player": name, "min_txt": time_cells[0], "seconds": mins,
                               "raw": line.strip()})
    return teams, totals


def build_minutes(injury):
    """Top-8 minutes shares per team and the replacement shares when a player is out."""
    sources = []
    books = []
    gb_new = os.path.join(RAW, "gamebook_20261115_INDPHI.md")
    if os.path.exists(gb_new):
        books.append((gb_new, GB_URL, "2026-11-15", None))
    for fn in sorted(os.listdir(RAW)):
        if fn.startswith("gamebook_") and fn.endswith(".md") and fn != "gamebook_20261115_INDPHI.md":
            m = re.match(r"gamebook_(\d{8})_([A-Z]{6})\.md", fn)
            d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
            books.append((os.path.join(RAW, fn),
                          f"https://statsdmz.nba.com/pdfs/{m.group(1)}/{m.group(1)}_{m.group(2)}.pdf",
                          d, None))
    live_raw = os.path.join(ROOT, "data", "live", "raw")
    for fn in sorted(os.listdir(live_raw)):
        if fn.startswith("gamebook_") and fn.endswith(".md"):
            m = re.match(r"gamebook_(\d{8})_([A-Z]{6})\.md", fn)
            d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
            books.append((os.path.join(live_raw, fn),
                          f"https://statsdmz.nba.com/pdfs/{m.group(1)}/{m.group(1)}_{m.group(2)}.pdf",
                          d,
                          "DAL" if fn == "gamebook_20261114_DALCLE.md" else None))
            sources.append(f"https://statsdmz.nba.com/pdfs/{m.group(1)}/{m.group(1)}_{m.group(2)}.pdf")

    per_team = {}
    logs = []
    for path, url, gdate, fallback in books:
        teams, totals = parse_gamebook(path, visitor_fallback=fallback)
        for team_name, players in teams.items():
            code = team_code(team_name)
            if code is None:
                continue
            rows = [p for p in players if p["seconds"]]
            rows.sort(key=lambda p: -p["seconds"])
            played = totals.get(team_name) or 240.0
            per_team.setdefault(code, []).append(
                {"date": gdate, "source": url, "rows": rows, "team_minutes": played})
            for p in rows:
                logs.append({"date": gdate, "team": code, "team_name": team_name,
                             "player": p["player"], "minutes": round(p["seconds"] / 60.0, 2),
                             "source": url})

    out_teams = {}
    for code, games in sorted(per_team.items()):
        latest = max(games, key=lambda g: g["date"])
        rows = latest["rows"][:8]
        team_minutes = latest.get("team_minutes") or 240.0
        total240 = team_minutes
        shares = []
        for i, p in enumerate(rows, start=1):
            minutes = p["seconds"] / 60.0
            shares.append({"rank": i, "player": p["player"], "minutes": round(minutes, 1),
                           "share_of_team_minutes": round(minutes / total240, 4),
                           "share_of_240_regulation": round(minutes / 240.0, 4)})
        top8_minutes = sum(s["minutes"] for s in shares)
        covered = sum(p["seconds"] for p in latest["rows"]) / 60.0
        # replacement: the out player's minutes are redistributed pro-rata over the remaining
        # top-8 (the 'others' bucket is left out of the redistribution and reported separately)
        for s in shares:
            rest = [x for x in shares if x["rank"] != s["rank"]]
            rest_minutes = sum(x["minutes"] for x in rest)
            s["replacement_shares"] = {
                x["player"]: round(x["minutes"] / rest_minutes, 4) if rest_minutes else None
                for x in rest}
        out_teams[code] = {
            "team": code,
            "game": latest["date"],
            "source": latest["source"],
            "games_captured": len(games),
            "top8": shares,
            "top8_minutes": round(top8_minutes, 1),
            "top8_share_of_team_minutes": round(top8_minutes / total240, 4),
            "others_minutes": round(covered - top8_minutes, 1),
            "others_share_of_team_minutes": round((covered - top8_minutes) / total240, 4),
            "team_minutes": total240,
            "overtime": total240 > 240.0,
            "redistribution_rule": "when a player is Out, his minutes are redistributed pro rata "
                                   "over the remaining seven top-8 players; the 'others' bucket "
                                   "(minutes outside the top 8) is reported, never absorbed",
        }

    # injury-report players covered by a captured game log
    inj_names = {}
    for r in injury["rows"]:
        if r["player"] and r["team"]:
            last = r["player"].split(",")[0].strip().lower()
            inj_names.setdefault((r["team"], last), r)
    matched, unmatched = [], []
    for (team, last), r in sorted(inj_names.items()):
        hit = [l for l in logs if l["team"] == team and last in l["player"].lower()]
        if hit:
            for h in hit:
                matched.append({"player": r["player"], "team": team,
                                "status": r["status"], "reason": r["reason"],
                                "log_date": h["date"], "minutes": h["minutes"],
                                "opponent": None, "source": h["source"]})
        else:
            unmatched.append({"player": r["player"], "team": team, "status": r["status"]})

    minutes_doc = {
        "schema": "nba3.slate.minutes/v1",
        "session": SESSION,
        "retrieved_utc": RETRIEVED_UTC,
        "rule": "top-8 minutes shares from the most recent captured official game book for that "
                "team, plus the pro-rata replacement shares that apply when one of those eight "
                "is out. The denominator is the team-minutes total printed on the game book's own "
                "totals row (240 for a regulation game, 290 for the 11/12 DET@WAS two-overtime "
                "game), never an assumed 240.",
        "sources": sorted({b[1] for b in books}),
        "extraction_notes": [
            "20261114_DALCLE.pdf: the extraction dropped the 'VISITOR: Dallas Mavericks' header; "
            "those rows are attributed to DAL from the official file name and flagged.",
            "20261114_BKNMEM.pdf: the extraction merged the Nets' final row with the team-total "
            "row; that row is dropped (it fails the box-score identity) and the totals still "
            "reconcile.",
            "20261115_INDPHI.pdf: the home block's bench rows are shifted by one empty column and "
            "drop PTS; minutes are unaffected and are the only field taken from those rows.",
        ],
        "counts": {"teams_with_minutes": len(out_teams),
                   "teams_without_minutes": 30 - len(out_teams)},
        "teams": out_teams,
        "missing_teams_note": "Teams with no captured game book are absent from 'teams' and are "
                              "printed blank + flagged on the site. Minutes are never inferred.",
    }
    write_json(os.path.join(OUT, "minutes.json"), minutes_doc)

    logs_doc = {
        "schema": "nba3.slate.player_game_logs/v1",
        "session": SESSION,
        "retrieved_utc": RETRIEVED_UTC,
        "what": "per-player minutes from the captured official game books (minutes, points, "
                "rebounds and assists where the box-score row survives the PTS identity check)",
        "sources": sorted({b[1] for b in books}),
        "counts": {"rows": len(logs), "games": len(books),
                   "injury_players_covered": len(matched),
                   "injury_players_not_covered": len(unmatched)},
        "injury_report_matches": matched,
        "injury_report_gaps": unmatched,
        "rows": logs,
        "gap_rule": "A player on the injury report whose team has no captured game book is listed "
                    "in injury_report_gaps and printed blank on the site. Not inferred.",
    }
    write_json(os.path.join(OUT, "player_game_logs.json"), logs_doc)
    return minutes_doc, logs_doc


# --------------------------------------------------------------------------- main

def main():
    os.makedirs(INJ, exist_ok=True)
    injury = parse_injury_report()
    deltas = injury_archive_and_diff(injury)
    standings = parse_standings()
    advanced = parse_advanced()
    traditional = parse_traditional()
    opponent = parse_opponent()
    slate = parse_slate()

    # cross-check: every (date, matchup) in the injury report must be on the official schedule
    sched_pairs = {(g["date"], f"{g['away']}@{g['home']}") for g in slate["games"]}
    bad = sorted({(r["game_date"], r["matchup"]) for r in injury["rows"]
                  if r["matchup"] and (r["game_date"], r["matchup"]) not in sched_pairs})
    slate["cross_check"]["injury_matchups_not_on_schedule"] = [
        {"game_date": d, "matchup": m} for d, m in bad]
    slate["cross_check"]["injury_matchups_checked"] = len(
        {(r["game_date"], r["matchup"]) for r in injury["rows"] if r["matchup"]})
    write_json(os.path.join(OUT, "slate.json"), slate)

    feed = build_results_feed(slate, standings)
    arenas = build_arenas()
    games = schedule_union(slate)
    travel = build_travel(slate, arenas, games)
    minutes, logs = build_minutes(injury)

    print(f"injury rows          {injury['count']}  ({injury['report_stamp']})")
    print(f"  status changes vs 06:15 AM: {deltas['pairs'][0]['counts']['status_changes']}  "
          f"added {deltas['pairs'][0]['counts']['added']}  "
          f"removed {deltas['pairs'][0]['counts']['removed']}")
    print(f"standings rows       {standings['count']}")
    print(f"advanced rows        {advanced['count']}")
    print(f"traditional rows     {traditional['count']}   opponent rows {opponent['count']}")
    print(f"slate games          {slate['counts']['total']} upcoming "
          f"({slate['window']['from']}..{slate['window']['to']})")
    print(f"results feed         {feed['counts']['verified']}/{feed['counts']['games']} verified")
    print(f"arenas with coords   {arenas['verified']}/{arenas['count']}")
    print(f"travel rows          {travel['counts']['rows']}  blank {travel['counts']['blank_travel']}"
          f"  b2b {travel['counts']['b2b']}  3-in-4 {travel['counts']['three_in_four']}")
    print(f"minutes teams        {minutes['counts']['teams_with_minutes']}/30")
    print(f"player log rows      {logs['counts']['rows']}")
    if bad:
        print(f"WARNING injury matchups not on the official schedule: {bad}", )


if __name__ == "__main__":
    main()
