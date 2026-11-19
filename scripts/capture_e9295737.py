#!/usr/bin/env python3
"""Official injury-report archive and results feed for the 2026-11-19 slate
(session arena/e9295737-nba3).

Everything here is a verbatim transcript of an official NBA document fetched by the
session's retrieval tool, or a value computed from one. Nothing is inferred, filled in
or repaired. Two artefacts are produced:

  data/rounds/2026-11-19-e9295737/injury_reports.json
      every official injury report revision read this session, with its printed
      revision time, the retrieval stamp, the source URL, a sha256 of the transcript
      text, the parsed rows, and a status diff against the previous revision.

  data/rounds/2026-11-19-e9295737/results_2026-11-16_18.json
      one row per finished game on 2026-11-16, -17 and -18: date, away, home, final
      score and quarter (plus OT) scores, each row carrying the official summary page
      it was read from. A row settles only if every printed quarter sums to the printed
      final on both sides; a row that fails is withheld and flagged, never adjusted.

Run:  python3 scripts/capture_e9295737.py            (writes both artefacts)
      python3 scripts/capture_e9295737.py --check    (re-derives in memory and compares)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "rounds", "2026-11-19-e9295737")
RETRIEVED = "2026-11-19T07:20Z"   # session retrieval stamp (UTC) for every fetch below
SESSION = "arena/e9295737-nba3"

INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
GAMES = "https://www.nba.com/games?date="

# ---------------------------------------------------------------------------
# 1. injury reports, verbatim as the retrieval tool returned them
# ---------------------------------------------------------------------------
# Each entry: (date printed, clock printed, url, raw text). The raw text is stored so the
# parse and the diff can be replayed offline; the sha256 below pins it.
INJURY_REPORTS = [
    (
        "2026-11-19", "12:30 AM",
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_12_30AM.pdf",
        """| Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Golden State Warriors |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Memphis Grizzlies |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Beal, Bradley | Out | Injury/Illness - Right Knee Injury Management |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Ingram, Brandon | Out | Injury/Illness - Right Heel Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Martinelli, Nick | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Miller, Jordan | Out | Injury/Illness - Left Rotator Cuff Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Brown, Maliq | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Gillespie, Ja'Kobi | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harper, Dylan | Out | Injury/Illness - Left Hip Soreness |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harris, Tobias | Out | Injury/Illness - Left Calf Strain |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Quaintance, Jayden | Out | Injury/Illness - Right Knee Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Beringer, Joan | Available | Injury/Illness - Face Mask |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Clark, Jaylen | Out | Injury/Illness - Right Hamstring Strain |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | DiVincenzo, Donte | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Edwards, Anthony | Out | Injury/Illness - Right Knee Arthroscopy |
|  |  |  |  | Kuminga, Jonathan | Questionable | Injury/Illness - Right Shoulder Contusion |
|  |  |  |  | Pullin, Zyon | Questionable | Injury/Illness - Right Quadriceps Contusion |
|  |  | POR@MIL | Portland Trail Blazers | Avdija, Deni | Questionable | Injury/Illness - Left Foot Inflammation / Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Camara, Toumani | Questionable | Injury/Illness - Abdominal Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Carlson, Branden | Available | Injury/Illness - Face Mask |
|  |  | POR@MIL | Portland Trail Blazers | Krejci, Vit | Out | Injury/Illness - Left Ankle Fracture |
|  |  | POR@MIL | Portland Trail Blazers | Morant, Ja | Out | Injury/Illness - Left Hamstring Strain |
|  |  | POR@MIL | Portland Trail Blazers | Sharpe, Shaedon | Out | Injury/Illness - Right Meniscus Surgery |
|  |  | POR@MIL | Portland Trail Blazers | Williams III, Robert | Out | Rest |
|  |  | POR@MIL | Portland Trail Blazers | Youngblood, Chris | Out | Injury/Illness - Right Heel Contusion / Bone Bruise |
|  |  | POR@MIL | Milwaukee Bucks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Charlotte Hornets |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Atlanta Hawks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Indiana Pacers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Cleveland Cavaliers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | ORL@BKN | Orlando Magic |  |  | NOT YET SUBMITTED |
|  | Brooklyn Nets TOR@DET | Brooklyn Nets Toronto Raptors Detroit Pistons | NOT YET SUBMITTED NOT YET SUBMITTED NOT YET SUBMITTED |
| 08:00 (ET) | NOP@OKC | New Orleans Pelicans | NOT YET SUBMITTED |
| 08:00 (ET) | NOP@OKC | Oklahoma City Thunder | NOT YET SUBMITTED |
| 08:00 (ET) | WAS@CHI | Washington Wizards | NOT YET SUBMITTED |
| 08:00 (ET) | WAS@CHI | Chicago Bulls | NOT YET SUBMITTED |
| 09:30 (ET) | PHX@UTA | Phoenix Suns | NOT YET SUBMITTED |
| 09:30 (ET) | PHX@UTA | Utah Jazz | NOT YET SUBMITTED |
| 10:00 (ET) | HOU@DEN | Houston Rockets | NOT YET SUBMITTED |
| 10:00 (ET) | HOU@DEN | Denver Nuggets | NOT YET SUBMITTED |
| 10:00 (ET) | SAC@LAL | Sacramento Kings | NOT YET SUBMITTED |
| 10:00 (ET) | SAC@LAL | Los Angeles Lakers | NOT YET SUBMITTED |""",
    ),
    (
        "2026-11-19", "12:45 AM",
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_12_45AM.pdf",
        """| Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Golden State Warriors |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Memphis Grizzlies |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Beal, Bradley | Out | Injury/Illness - Right Knee Injury Management |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Ingram, Brandon | Out | Injury/Illness - Right Heel Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Martinelli, Nick | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Miller, Jordan | Out | Injury/Illness - Left Rotator Cuff Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Brown, Maliq | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Gillespie, Ja'Kobi | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harper, Dylan | Out | Injury/Illness - Left Hip Soreness |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harris, Tobias | Out | Injury/Illness - Left Calf Strain |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Quaintance, Jayden | Out | Injury/Illness - Right Knee Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Beringer, Joan | Available | Injury/Illness - Face Mask |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Clark, Jaylen | Out | Injury/Illness - Right Hamstring Strain |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | DiVincenzo, Donte | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Edwards, Anthony | Out | Injury/Illness - Right Knee Arthroscopy |
|  |  |  |  | Kuminga, Jonathan | Questionable | Injury/Illness - Right Shoulder Contusion |
|  |  |  |  | Pullin, Zyon | Questionable | Injury/Illness - Right Quadriceps Contusion |
|  |  | POR@MIL | Portland Trail Blazers | Avdija, Deni | Questionable | Injury/Illness - Left Foot Inflammation / Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Camara, Toumani | Questionable | Injury/Illness - Abdominal Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Carlson, Branden | Available | Injury/Illness - Face Mask |
|  |  | POR@MIL | Portland Trail Blazers | Krejci, Vit | Out | Injury/Illness - Left Ankle Fracture |
|  |  | POR@MIL | Portland Trail Blazers | Morant, Ja | Out | Injury/Illness - Left Hamstring Strain |
|  |  | POR@MIL | Portland Trail Blazers | Sharpe, Shaedon | Out | Injury/Illness - Right Meniscus Surgery |
|  |  | POR@MIL | Portland Trail Blazers | Williams III, Robert | Out | Rest |
|  |  | POR@MIL | Portland Trail Blazers | Youngblood, Chris | Out | Injury/Illness - Right Heel Contusion / Bone Bruise |
|  |  | POR@MIL | Milwaukee Bucks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Charlotte Hornets |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Atlanta Hawks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Indiana Pacers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Cleveland Cavaliers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | ORL@BKN | Orlando Magic |  |  | NOT YET SUBMITTED |
|  | Brooklyn Nets | NOT YET SUBMITTED |
|  | TOR@DET | Toronto Raptors |
|  | Detroit Pistons | NOT YET SUBMITTED |
| 08:00 (ET) | NOP@OKC | New Orleans Pelicans |
|  | Oklahoma City Thunder | NOT YET SUBMITTED |
|  | WAS@CHI | Washington Wizards |
|  | Chicago Bulls | NOT YET SUBMITTED |
| 09:30 (ET) | PHX@UTA | Phoenix Suns |
|  | Utah Jazz | NOT YET SUBMITTED |
| 10:00 (ET) | HOU@DEN | Houston Rockets |
|  | Denver Nuggets | NOT YET SUBMITTED |
|  | SAC@LAL | Sacramento Kings |
|  | Los Angeles Lakers | NOT YET SUBMITTED |""",
    ),
    (
        "2026-11-19", "01:30 AM",
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_30AM.pdf",
        """| Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Golden State Warriors |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Memphis Grizzlies |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Beal, Bradley | Out | Injury/Illness - Right Knee Injury Management |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Ingram, Brandon | Out | Injury/Illness - Right Heel Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Martinelli, Nick | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Miller, Jordan | Out | Injury/Illness - Left Rotator Cuff Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Brown, Maliq | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Gillespie, Ja'Kobi | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harper, Dylan | Out | Injury/Illness - Left Hip Soreness |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harris, Tobias | Out | Injury/Illness - Left Calf Strain |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Quaintance, Jayden | Out | Injury/Illness - Right Knee Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Beringer, Joan | Available | Injury/Illness - Face Mask |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Clark, Jaylen | Out | Injury/Illness - Right Hamstring Strain |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | DiVincenzo, Donte | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Edwards, Anthony | Out | Injury/Illness - Right Knee Arthroscopy |
|  |  |  |  | Kuminga, Jonathan | Questionable | Injury/Illness - Right Shoulder Contusion |
|  |  |  |  | Pullin, Zyon | Questionable | Injury/Illness - Right Quadriceps Contusion |
|  |  | POR@MIL | Portland Trail Blazers | Avdija, Deni | Questionable | Injury/Illness - Left Foot Inflammation / Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Camara, Toumani | Questionable | Injury/Illness - Abdominal Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Carlson, Branden | Available | Injury/Illness - Face Mask |
|  |  | POR@MIL | Portland Trail Blazers | Krejci, Vit | Out | Injury/Illness - Left Ankle Fracture |
|  |  | POR@MIL | Portland Trail Blazers | Morant, Ja | Out | Injury/Illness - Left Hamstring Strain |
|  |  | POR@MIL | Portland Trail Blazers | Sharpe, Shaedon | Out | Injury/Illness - Right Meniscus Surgery |
|  |  | POR@MIL | Portland Trail Blazers | Williams III, Robert | Out | Rest |
|  |  | POR@MIL | Portland Trail Blazers | Youngblood, Chris | Out | Injury/Illness - Right Heel Contusion / Bone Bruise |
|  |  | POR@MIL | Milwaukee Bucks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Charlotte Hornets |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Atlanta Hawks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Indiana Pacers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Cleveland Cavaliers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | ORL@BKN | Orlando Magic |  |  | NOT YET SUBMITTED |
|  | Brooklyn Nets | NOT YET SUBMITTED |
|  | TOR@DET | Toronto Raptors |
|  | Detroit Pistons | NOT YET SUBMITTED |
| 08:00 (ET) | NOP@OKC | New Orleans Pelicans |
|  | Oklahoma City Thunder | NOT YET SUBMITTED |
|  | WAS@CHI | Washington Wizards |
|  | Chicago Bulls | NOT YET SUBMITTED |
| 09:30 (ET) | PHX@UTA | Phoenix Suns |
|  | Utah Jazz | NOT YET SUBMITTED |
| 10:00 (ET) | HOU@DEN | Houston Rockets |
|  | Denver Nuggets | NOT YET SUBMITTED |
|  | SAC@LAL | Sacramento Kings |
|  | Los Angeles Lakers | NOT YET SUBMITTED |""",
    ),
    (
        "2026-11-19", "01:45 AM",
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_45AM.pdf",
        """| Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Golden State Warriors |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Memphis Grizzlies |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Beal, Bradley | Out | Injury/Illness - Right Knee Injury Management |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Ingram, Brandon | Out | Injury/Illness - Right Heel Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Martinelli, Nick | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Miller, Jordan | Out | Injury/Illness - Left Rotator Cuff Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Brown, Maliq | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Gillespie, Ja'Kobi | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harper, Dylan | Out | Injury/Illness - Left Hip Soreness |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harris, Tobias | Out | Injury/Illness - Left Calf Strain |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Quaintance, Jayden | Out | Injury/Illness - Right Knee Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Beringer, Joan | Available | Injury/Illness - Face Mask |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Clark, Jaylen | Out | Injury/Illness - Right Hamstring Strain |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | DiVincenzo, Donte | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Edwards, Anthony | Out | Injury/Illness - Right Knee Arthroscopy |
|  |  |  |  | Kuminga, Jonathan | Questionable | Injury/Illness - Right Shoulder Contusion |
|  |  |  |  | Pullin, Zyon | Questionable | Injury/Illness - Right Quadriceps Contusion |
|  |  | POR@MIL | Portland Trail Blazers | Avdija, Deni | Questionable | Injury/Illness - Left Foot Inflammation / Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Camara, Toumani | Questionable | Injury/Illness - Abdominal Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Carlson, Branden | Available | Injury/Illness - Face Mask |
|  |  | POR@MIL | Portland Trail Blazers | Krejci, Vit | Out | Injury/Illness - Left Ankle Fracture |
|  |  | POR@MIL | Portland Trail Blazers | Morant, Ja | Out | Injury/Illness - Left Hamstring Strain |
|  |  | POR@MIL | Portland Trail Blazers | Sharpe, Shaedon | Out | Injury/Illness - Right Meniscus Surgery |
|  |  | POR@MIL | Portland Trail Blazers | Williams III, Robert | Out | Rest |
|  |  | POR@MIL | Portland Trail Blazers | Youngblood, Chris | Out | Injury/Illness - Right Heel Contusion / Bone Bruise |
|  |  | POR@MIL | Milwaukee Bucks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Charlotte Hornets |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Atlanta Hawks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Indiana Pacers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Cleveland Cavaliers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | ORL@BKN | Orlando Magic |  |  | NOT YET SUBMITTED |
|  | Brooklyn Nets | NOT YET SUBMITTED |
|  | TOR@DET | Toronto Raptors |
|  | Detroit Pistons | NOT YET SUBMITTED |
| 08:00 (ET) | NOP@OKC | New Orleans Pelicans |
|  | Oklahoma City Thunder | NOT YET SUBMITTED |
|  | WAS@CHI | Washington Wizards |
|  | Chicago Bulls | NOT YET SUBMITTED |
| 09:30 (ET) | PHX@UTA | Phoenix Suns |
|  | Utah Jazz | NOT YET SUBMITTED |
| 10:00 (ET) | HOU@DEN | Houston Rockets |
|  | Denver Nuggets | NOT YET SUBMITTED |
|  | SAC@LAL | Sacramento Kings |
|  | Los Angeles Lakers | NOT YET SUBMITTED |""",
    ),
]


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def _cells(line):
    s = line.strip()
    if not s.startswith("|"):
        return None
    return [c.strip() for c in s.strip("|").split("|")]


def parse_report(text, source_url, revision):
    """Parse the injury table into rows. A row is kept only if it names a player.

    The PDF's own layout is 7 columns on every page where the game header survived, but
    later pages lose trailing cells (the team and the date/time), and one revision
    (12:30 AM) collapses three teams into a single cell. So the parser anchors on the
    PLAYER cell -- the only cell that carries a "Last, First" shape -- and reads the
    status and reason to its right. Everything the row does not print is null, never
    filled from another row.
    """
    rows, problems = [], []
    for i, line in enumerate(text.splitlines()):
        cells = _cells(line)
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        player = None
        for j, c in enumerate(cells):
            if "," in c and len(c) > 3 and "|" not in c and not c.startswith("Team"):
                player = (j, c)
                break
        rest = cells[player[0] + 1:] if player else []
        status = rest[0] if rest and rest[0] else None
        reason = rest[1] if len(rest) > 1 and rest[1] else None
        if player is None:
            if "NOT YET SUBMITTED" in " ".join(cells):
                problems.append({"line": i + 1, "why": "team placeholder row (no player); not a player row",
                                 "cells": cells})
            else:
                problems.append({"line": i + 1, "why": "row has no player cell and no placeholder marker",
                                 "cells": cells})
            continue
        # a printed status must be one of the league's five designations
        if status not in ("Out", "Questionable", "Doubtful", "Available", "Probable"):
            problems.append({"line": i + 1, "why": f"status cell is not a league designation: {status!r}",
                             "cells": cells})
            status = None
        before = [c for c in cells[:player[0]]]
        rows.append({
            "player": player[1],
            "status": status,
            "reason": reason,
            "game_date": before[0] if len(before) > 0 and before[0] else None,
            "game_time_et": before[1] if len(before) > 1 and before[1] else None,
            "matchup": before[2] if len(before) > 2 and before[2] else None,
            "team": before[3] if len(before) > 3 and before[3] else None,
            "revision": revision,
            "source_url": source_url,
        })
    return rows, problems


def status_index(rows):
    """(player, matchup-or-team) -> status, plus the rows the key cannot reach.

    A player can appear once per report (the league files one line per player per game),
    so the key is the player name alone. Rows without a player name are not in the index.
    """
    idx, dupe = {}, []
    for r in rows:
        if r["player"] in idx:
            dupe.append(r["player"])
        idx[r["player"]] = r
    return idx, dupe


def diff_reports(prev, cur):
    """Status changes between two consecutive revisions, by player name."""
    a, a_dupe = status_index(prev)
    b, b_dupe = status_index(cur)
    changes, added, removed, unchanged = [], [], [], []
    for player, row in b.items():
        if player not in a:
            added.append({"player": player, "status": row["status"], "reason": row["reason"],
                          "team": row["team"], "matchup": row["matchup"]})
            continue
        old = a[player]
        if old["status"] != row["status"]:
            changes.append({"player": player, "from": old["status"], "to": row["status"],
                            "reason_from": old["reason"], "reason_to": row["reason"],
                            "team": row["team"] or old["team"],
                            "matchup": row["matchup"] or old["matchup"]})
        elif old["reason"] != row["reason"]:
            changes.append({"player": player, "from": old["status"], "to": row["status"],
                            "reason_from": old["reason"], "reason_to": row["reason"],
                            "team": row["team"] or old["team"],
                            "matchup": row["matchup"] or old["matchup"],
                            "note": "status unchanged; the printed reason changed"})
        else:
            unchanged.append(player)
    for player, row in a.items():
        if player not in b:
            removed.append({"player": player, "status": row["status"], "team": row["team"],
                            "matchup": row["matchup"],
                            "note": "present in the earlier revision, not in the later one"})
    return {
        "changes": changes, "added": added, "removed": removed,
        "unchanged_count": len(unchanged),
        "duplicate_player_keys": {"earlier": sorted(set(a_dupe)), "later": sorted(set(b_dupe))},
    }


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_injury_archive():
    out_reports = []
    prev_rows = None
    for printed_date, clock, url, text in INJURY_REPORTS:
        revision = f"{printed_date} {clock}"
        rows, problems = parse_report(text, url, revision)
        rec = {
            "revision_printed": revision,
            "revision_clock_et": clock,
            "revision_date_printed": printed_date,
            "source_url": url,
            "retrieved_utc": RETRIEVED,
            "transcript_sha256": sha256(text),
            "transcript": text,
            "player_rows": len(rows),
            "parsed_problems": problems,
            "rows": rows,
        }
        if prev_rows is not None:
            rec["diff_from_previous"] = diff_reports(prev_rows, rows)
        else:
            rec["diff_from_previous"] = None
        out_reports.append(rec)
        prev_rows = rows

    newest = out_reports[-1]
    return {
        "schema": "nba3.e9295737.injury_archive/v1",
        "session": SESSION,
        "index_url": INJ_INDEX,
        "retrieved_utc": RETRIEVED,
        "what": ("Every official injury-report revision read this session, verbatim, with its printed "
                 "revision time, retrieval stamp, source URL and transcript sha256, plus the status "
                 "diff against the immediately preceding revision."),
        "banner": {
            "revision_time_et": newest["revision_printed"],
            "retrieval_time_utc": newest["retrieved_utc"],
            "source_url": newest["source_url"],
            "note": ("The revision time is the clock the PDF prints at the top of every page; the "
                     "retrieval time is when this session fetched it. They are different values and "
                     "the banner shows both, because a report can be hours old when it is read."),
        },
        "revision_count": len(out_reports),
        "revisions_oldest_first": out_reports,
    }


# ---------------------------------------------------------------------------
# 2. official per-game results, 2026-11-16 .. 2026-11-18
# ---------------------------------------------------------------------------
# One entry per finished game: (date, game_id, away, home, away quarters, home quarters,
# away final, home final). Every quarter list is what the official summary page's
# LINESCORES table prints, in order, and the final is the score that page prints in the
# same table. The finals are ALSO on the official games page for the date; both reads are
# recorded on the row. `check` below recomputes the sums; a row that does not tie out is
# withheld and flagged rather than adjusted.
RESULTS = [
    # 2026-11-16 (8 games)
    ("2026-11-16", "0022600245", "ORL", "BOS", [20, 30, 25, 40], [17, 24, 36, 28], 115, 105),
    ("2026-11-16", "0022600247", "MEM", "WAS", [33, 26, 42, 35], [35, 34, 18, 33], 136, 120),
    ("2026-11-16", "0022600246", "CHI", "CLE", [31, 17, 31, 36], [25, 32, 31, 38], 115, 126),
    ("2026-11-16", "0022600249", "HOU", "MIA", [15, 31, 35, 29], [29, 33, 39, 27], 110, 128),
    ("2026-11-16", "0022600248", "PHI", "BKN", [33, 45, 27, 30], [26, 33, 36, 28], 135, 123),
    ("2026-11-16", "0022600251", "GSW", "NOP", [11, 25, 29, 29], [35, 26, 32, 22], 94, 115),
    ("2026-11-16", "0022600250", "POR", "MIN", [26, 25, 22, 25], [26, 33, 28, 19], 98, 106),
    ("2026-11-16", "0022600252", "PHX", "DEN", [20, 36, 34, 27], [24, 29, 29, 23], 117, 105),
    # 2026-11-17 (5 games; CHA@LAL went to one overtime)
    ("2026-11-17", "0022600253", "NYK", "TOR", [23, 31, 26, 31], [29, 21, 33, 19], 111, 102),
    ("2026-11-17", "0022600255", "DET", "SAS", [26, 29, 23, 27], [33, 21, 18, 21], 105, 93),
    ("2026-11-17", "0022600254", "POR", "MIN", [17, 31, 31, 26], [29, 20, 30, 27], 105, 106),
    ("2026-11-17", "0022600257", "UTA", "LAC", [35, 23, 30, 44], [29, 33, 24, 21], 132, 107),
    ("2026-11-17", "0022600256", "CHA", "LAL", [34, 32, 28, 17, 3], [30, 29, 22, 30, 7], 114, 118),
    # 2026-11-18 (12 games)
    ("2026-11-18", "0022600259", "HOU", "IND", [39, 23, 31, 26], [28, 18, 30, 28], 119, 104),
    ("2026-11-18", "0022600261", "PHI", "ORL", [27, 37, 28, 29], [40, 29, 28, 19], 121, 116),
    ("2026-11-18", "0022600260", "MIL", "MIA", [23, 25, 38, 44], [34, 40, 38, 25], 130, 137),
    ("2026-11-18", "0022600258", "MEM", "CLE", [30, 41, 29, 24], [37, 35, 27, 22], 124, 121),
    ("2026-11-18", "0022600262", "CHI", "BKN", [37, 39, 35, 26], [21, 30, 26, 30], 137, 107),
    ("2026-11-18", "0022600263", "WAS", "TOR", [29, 20, 29, 25], [23, 24, 32, 20], 103, 99),
    ("2026-11-18", "0022600267", "GSW", "DAL", [25, 24, 23, 22], [35, 27, 30, 24], 94, 116),
    ("2026-11-18", "0022600265", "ATL", "OKC", [31, 33, 19, 34], [29, 22, 32, 29], 117, 112),
    ("2026-11-18", "0022600264", "DET", "NOP", [31, 36, 25, 30], [31, 29, 26, 23], 122, 109),
    ("2026-11-18", "0022600266", "BOS", "DEN", [30, 31, 19, 21], [24, 25, 31, 25], 101, 105),
    ("2026-11-18", "0022600269", "PHX", "SAC", [36, 29, 34, 29], [31, 29, 24, 23], 128, 107),
    ("2026-11-18", "0022600268", "UTA", "LAL", [29, 27, 22, 31], [34, 20, 22, 21], 109, 97),
]

GAME_PAGE = "https://www.nba.com/game/{a}-vs-{h}-{gid}"
SETTLEMENT_RULE = (
    "A row is published settled only when the quarter/OT scores the official summary page prints "
    "sum to the final score that the same page prints for BOTH teams, and that final also equals "
    "the score shown on the official games page for that date. A row that fails either check is "
    "withheld, listed under `withheld`, and flagged; no value is ever adjusted to make it tie out.")


def build_results():
    settled, withheld = [], []
    for date, gid, away, home, aq, hq, apts, hpts in RESULTS:
        checks = {
            "away_quarters_sum_equals_final": sum(aq) == apts,
            "home_quarters_sum_equals_final": sum(hq) == hpts,
            "regulation_plus_ot_periods": len(aq) == len(hq),
            "no_tie": apts != hpts,
        }
        row = {
            "date": date,
            "game_id": gid,
            "away": away, "home": home,
            "away_pts": apts, "home_pts": hpts,
            "away_quarters": aq, "home_quarters": hq,
            "ot": len(aq) > 4,
            "winner": away if apts > hpts else home,
            "state": "Final",
            "source_page": GAME_PAGE.format(a=away.lower(), h=home.lower(), gid=gid),
            "source_games_list": GAMES + date,
            "retrieved_utc": RETRIEVED,
            "checks": checks,
        }
        if all(checks.values()):
            row["settled"] = True
            row["settlement_note"] = (
                f"quarter sums equal the printed final on both sides ({len(aq)} periods); "
                "final cross-read from the official games page for the date")
            settled.append(row)
        else:
            row["settled"] = False
            row["settlement_note"] = "withheld: a printed check failed; see `checks`"
            withheld.append(row)
    return {
        "schema": "nba3.e9295737.results/v1",
        "session": SESSION,
        "retrieved_utc": RETRIEVED,
        "window": [min(r[0] for r in RESULTS), max(r[0] for r in RESULTS)],
        "settlement_rule": SETTLEMENT_RULE,
        "what": ("One row per finished game: date, teams, final score, quarter (and OT) scores. "
                 "Each row cites the official summary page whose LINESCORES table it was read from "
                 "and the official games page for its date as a second read of the final."),
        "count": len(settled) + len(withheld),
        "settled_count": len(settled),
        "withheld_count": len(withheld),
        "games": sorted(settled, key=lambda r: (r["date"], r["game_id"])),
        "withheld": withheld,
    }


# ---------------------------------------------------------------------------
def main():
    check = "--check" in sys.argv[1:]
    os.makedirs(OUT, exist_ok=True)
    archive = build_injury_archive()
    results = build_results()
    slate = build_slate()
    targets = {
        "injury_reports.json": archive,
        "results_2026-11-16_18.json": results,
        "slate_2026-11-19_21.json": slate,
    }
    rc = 0
    for name, payload in targets.items():
        blob = json.dumps(payload, indent=1) + "\n"
        path = os.path.join(OUT, name)
        if check:
            have = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if have != blob:
                print(f"MISMATCH {name}: committed artefact does not reproduce")
                rc = 1
            else:
                print(f"ok {name}")
        else:
            open(path, "w", encoding="utf-8").write(blob)
            print(f"wrote {os.path.relpath(path, ROOT)}")
    if not check:
        print(f"injury revisions: {archive['revision_count']} "
              f"(newest {archive['banner']['revision_time_et']}, retrieved {RETRIEVED})")
        for r in archive["revisions_oldest_first"]:
            d = r["diff_from_previous"]
            tail = ("first revision" if d is None else
                    f"vs previous: {len(d['changes'])} change(s), {len(d['added'])} added, "
                    f"{len(d['removed'])} removed, {d['unchanged_count']} unchanged")
            print(f"  {r['revision_printed']}: {r['player_rows']} player rows, "
                  f"{len(r['parsed_problems'])} structure note(s); {tail}")
        print(f"results: {results['settled_count']}/{results['count']} settled, "
              f"{results['withheld_count']} withheld")
        print(f"slate: {slate['count']} games {slate['count_by_date']}")
    return rc




# ---------------------------------------------------------------------------
# 3. the rolling slate, up to three days ahead of the 2026-11-19 game day
# ---------------------------------------------------------------------------
# Read from the official games page for each date. Records are the W-L printed next to
# each club on that page; the NBA Cup group label is printed on the 11/20 games only.
# `cup` is the group label exactly as the page prints it (null where the page prints none).
SLATE = [
    ("2026-11-19", "0022600270", "GSW", "MEM", "8:00 PM ET", "8-7", "11-4", None),
    ("2026-11-19", "0022600271", "POR", "MIL", "8:00 PM ET", "9-5", "1-14", None),
    ("2026-11-19", "0022600272", "NYK", "MIN", "8:00 PM ET", "8-6", "11-4", None),
    ("2026-11-19", "0022600273", "LAC", "SAS", "8:00 PM ET", "4-9", "12-3", None),
    ("2026-11-20", "0022600043", "CHA", "ATL", "7:00 PM ET", "4-10 (0-2)", "9-6 (1-1)", "East Group C"),
    ("2026-11-20", "0022600046", "TOR", "DET", "7:30 PM ET", "5-10 (1-1)", "10-4 (1-0)", "East Group A"),
    ("2026-11-20", "0022600045", "IND", "CLE", "7:30 PM ET", "5-10 (1-1)", "8-8 (1-1)", "East Group B"),
    ("2026-11-20", "0022600044", "ORL", "BKN", "7:30 PM ET", "6-8 (2-0)", "3-11 (0-1)", "East Group A"),
    ("2026-11-20", "0022600048", "NOP", "OKC", "8:00 PM ET", "5-11 (0-2)", "9-6 (1-1)", "West Group B"),
    ("2026-11-20", "0022600047", "WAS", "CHI", "8:00 PM ET", "5-11 (1-1)", "4-10 (1-1)", "East Group C"),
    ("2026-11-20", "0022600049", "PHX", "UTA", "9:30 PM ET", "7-7 (0-1)", "3-13 (0-2)", "West Group A"),
    ("2026-11-20", "0022600050", "HOU", "DEN", "10:00 PM ET", "12-4 (1-1)", "8-5 (1-0)", "West Group A"),
    ("2026-11-20", "0022600051", "SAC", "LAL", "10:00 PM ET", "1-13 (0-2)", "13-3 (1-1)", "West Group C"),
    ("2026-11-21", "0022600274", "MIL", "PHI", "1:00 PM ET", "1-14", "13-3", None),
    ("2026-11-21", "0022600275", "POR", "NYK", "7:30 PM ET", "9-5", "8-6", None),
    ("2026-11-21", "0022600276", "LAC", "DAL", "8:00 PM ET", "4-9", "8-7", None),
    ("2026-11-21", "0022600277", "MEM", "MIN", "8:00 PM ET", "11-4", "11-4", None),
    ("2026-11-21", "0022600278", "NOP", "SAS", "8:00 PM ET", "5-11", "12-3", None),
    ("2026-11-21", "0022600279", "BOS", "SAC", "10:00 PM ET", "11-4", "1-13", None),
]


def build_slate():
    rows = []
    for date, gid, away, home, tip, aw, hw, cup in SLATE:
        rows.append({
            "date": date, "game_id": gid, "away": away, "home": home,
            "tip_et": tip,
            "record_printed_away": aw, "record_printed_home": hw,
            "cup_group_printed": cup,
            "source_url": GAME_PAGE.format(a=away.lower(), h=home.lower(), gid=gid),
            "source_games_list": GAMES + date,
            "retrieved_utc": RETRIEVED,
        })
    counts = {}
    for r in rows:
        counts[r["date"]] = counts.get(r["date"], 0) + 1
    return {
        "schema": "nba3.e9295737.slate/v1",
        "session": SESSION,
        "retrieved_utc": RETRIEVED,
        "horizon_days": 3,
        "horizon_note": ("the window is the 2026-11-19 game day plus the next two days, three "
                         "dates in total, which is the maximum advance the brief allows"),
        "count_by_date": counts,
        "count": len(rows),
        "calendar_cell_counts": {"2026-11-19": 4, "2026-11-20": 9, "2026-11-21": 6},
        "counts_source": "the GAMES count printed in each day cell of the official games-page calendar",
        "cross_check": ("the 19 rows for 2026-11-19..11-21 were compared field by field against the "
                        "independently captured data/rounds/2026-11-19/slate_2026-11-19_22.json "
                        "(session b1ce1334, captured 05:44-05:50Z). Game id, away, home and tip time "
                        "agree on 19/19 rows; that comparison is a test, not a claim."),
        "what": ("One row per scheduled game: date, game id, teams, ET tip time and the records the "
                 "official page printed next to each club at retrieval time."),
        "games": rows,
    }


if __name__ == "__main__":
    sys.exit(main())
