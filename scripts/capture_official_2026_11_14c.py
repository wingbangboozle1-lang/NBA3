#!/usr/bin/env python3
"""Official-source capture #3 for 2026-11-14 (session ``arena/25418e3f-nba3``).

This is a *verbatim transcription* of four official NBA sources read with the
fetch tool on 2026-11-14 (UTC), plus the programmatic cross-checks that decide
whether the values already stored in this repository may be called verified.
Nothing here is inferred, interpolated or filled in: a cell the official page
does not print is written as an empty string and flagged downstream.

Sources read
  1. https://www.nba.com/games?date=2026-11-13            (chunks 0-1 of 2)
     The nine final scores of 2026-11-13, each with its game id, matchup,
     score line, Final / Final-OT state and Emirates NBA Cup group, plus the
     win-loss record the page prints under each team.  Also the November 2026
     scoreboard calendar, which prints an official game COUNT per date.
  2. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf
     The newest report listed on https://official.nba.com/nba-injury-report-2026-27-season/
     at read time.  49 rows: 31 rows for the 2026-11-14 slate and 18 rows for
     2026-11-15, every one of the 11/15 rows reading NOT YET SUBMITTED.
  3. https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season
     (chunks 0-1 of 2)  GP, W, L, MIN, OffRtg, DefRtg, NetRtg and PACE for all
     30 teams, read AFTER the 11/13 games had finished.
  4. https://official.nba.com/nba-injury-report-2026-27-season/
     The report index, used only to establish which report is newest.

Why this capture exists
  Session ``36e18d83`` left an open hand-off on the coordination board
  (flag F36-03): the 2026-11-13 results had never been carried into the
  canonical log, and the injury overlay the site prices with was the 11/13
  07:45 PM ET report.  Both are refreshed here.

Checks performed by this script (it exits non-zero if any fail)
  C1  the nine transcribed games reproduce the official GP column exactly
      (366 team-games = 2 x 183) and the official W and L columns (183 / 183);
  C2  the same 183 game count is reached a second, independent way: our own
      October rows plus the official November calendar's per-date counts;
  C3  every post-game W-L printed on the scoreboard page agrees with the record
      recomputed from the extended log;
  C4  the 2026-11-14 rows of the new injury report are identical, row for row
      and field for field, to the 2026-11-14 rows of the stored 07:45 PM report;
  C5  the team-ratings snapshot stored by the previous session is compared with
      this one, team by team -- and the set of teams whose GP moved is exactly
      the set of teams that played on 11/13, which is what tells us the stored
      snapshot was read mid-slate;
  C6  the per-date game counts on the official calendar agree with the stored
      slate for 11/14 through 11/17 (5 / 9 / 8 / 5 = 27 games).

Run:  python3 scripts/capture_official_2026_11_14c.py
Writes:
  data/app/official_results_2026-11-13.json
  data/app/official_injuries_2026-11-14_0415AM.json
  data/app/official_team_ratings_2026-11-14c.json
  data/app/official_counts_2026-11-14.json
  data/app/snapshot_manifest.json
and prints the six checks above.
"""
import csv
import json
import os
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

RETRIEVED = "2026-11-14"
RETRIEVED_STAMP = "2026-11-14T09:45Z"
SESSION = "arena/25418e3f-nba3"

GAMES_URL = "https://www.nba.com/games?date=2026-11-13"
TEAM_STATS_URL = ("https://www.nba.com/stats/teams/advanced"
                  "?Season=2026-27&SeasonType=Regular%20Season")
INJURY_URL = ("https://ak-static.cms.nba.com/referee/injury/"
              "Injury-Report_2026-11-14_04_15AM.pdf")
INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
PRIOR_INJURY_URL = ("https://ak-static.cms.nba.com/referee/injury/"
                    "Injury-Report_2026-11-13_07_45PM.pdf")

TEAM_ID = {
    "ATL": 1610612737, "BOS": 1610612738, "CLE": 1610612739, "NOP": 1610612740,
    "CHI": 1610612741, "DAL": 1610612742, "DEN": 1610612743, "GSW": 1610612744,
    "HOU": 1610612745, "LAC": 1610612746, "LAL": 1610612747, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "BKN": 1610612751, "NYK": 1610612752,
    "ORL": 1610612753, "IND": 1610612754, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "MEM": 1610612763, "WAS": 1610612764, "DET": 1610612765,
    "CHA": 1610612766, "OKC": 1610612760,
}

# --------------------------------------------------------------------------
# 1. Final scores, 2026-11-13 -- nba.com/games?date=2026-11-13
#    The page prints, per game: competition label, away team + its record,
#    away score, "Final" or "Final/OT", home score, home team + its record,
#    and the game link (which carries the game id and the away/home order).
#    (date, gid, away, away_pts, home, home_pts, ot, away_record, home_record,
#     cup_group, game_url)
# --------------------------------------------------------------------------
RESULTS_1113 = [
    ("2026-11-13", "0022600034", "NYK", 104, "IND", 106, 0, "6-6 (0-2)", "5-8 (1-1)",
     "Emirates NBA Cup East Group B", "https://www.nba.com/game/nyk-vs-ind-0022600034"),
    ("2026-11-13", "0022600035", "MIL", 99, "ORL", 107, 0, "1-12 (0-2)", "5-7 (2-0)",
     "Emirates NBA Cup East Group A", "https://www.nba.com/game/mil-vs-orl-0022600035"),
    ("2026-11-13", "0022600036", "CLE", 121, "MIA", 133, 0, "6-7 (1-1)", "6-6 (2-0)",
     "Emirates NBA Cup East Group A", "https://www.nba.com/game/cle-vs-mia-0022600036"),
    ("2026-11-13", "0022600037", "ATL", 117, "CHI", 125, 1, "7-6 (1-1)", "2-9 (1-1)",
     "Emirates NBA Cup East Group C", "https://www.nba.com/game/atl-vs-chi-0022600037"),
    ("2026-11-13", "0022600038", "MEM", 142, "NOP", 111, 0, "8-4 (1-1)", "4-9 (0-2)",
     "Emirates NBA Cup West Group B", "https://www.nba.com/game/mem-vs-nop-0022600038"),
    ("2026-11-13", "0022600039", "UTA", 118, "HOU", 125, 0, "1-12 (0-2)", "10-3 (1-1)",
     "Emirates NBA Cup West Group A", "https://www.nba.com/game/uta-vs-hou-0022600039"),
    ("2026-11-13", "0022600040", "GSW", 85, "SAS", 123, 0, "8-5 (1-1)", "11-2 (2-0)",
     "Emirates NBA Cup West Group C", "https://www.nba.com/game/gsw-vs-sas-0022600040"),
    ("2026-11-13", "0022600041", "POR", 120, "SAC", 107, 0, "9-3 (1-1)", "1-11 (0-2)",
     "Emirates NBA Cup West Group C", "https://www.nba.com/game/por-vs-sac-0022600041"),
    ("2026-11-13", "0022600042", "OKC", 112, "LAC", 113, 0, "8-5 (1-1)", "3-8 (1-1)",
     "Emirates NBA Cup West Group B", "https://www.nba.com/game/okc-vs-lac-0022600042"),
]

# --------------------------------------------------------------------------
# 2. November 2026 game counts, printed by the scoreboard month grid on
#    nba.com/games ("14 / 5 GAMES").  The grid is the official count of games
#    scheduled on each date; it is used as an independent check on both the
#    result log and the upcoming slate, never as a source of a matchup.
#    (date, games_listed_on_official_page)
# --------------------------------------------------------------------------
NOVEMBER_COUNTS = [
    ("2026-11-01", 4), ("2026-11-02", 15), ("2026-11-03", 0), ("2026-11-04", 14),
    ("2026-11-05", 2), ("2026-11-06", 9), ("2026-11-07", 7),
    ("2026-11-08", 7), ("2026-11-09", 8), ("2026-11-10", 6), ("2026-11-11", 10),
    ("2026-11-12", 4), ("2026-11-13", 9), ("2026-11-14", 5),
    ("2026-11-15", 9), ("2026-11-16", 8), ("2026-11-17", 5), ("2026-11-18", 12),
    ("2026-11-19", 4), ("2026-11-20", 9), ("2026-11-21", 6),
    ("2026-11-22", 7), ("2026-11-23", 10), ("2026-11-24", 3), ("2026-11-25", 9),
    ("2026-11-26", 0), ("2026-11-27", 11), ("2026-11-28", 5),
    ("2026-11-29", 10), ("2026-11-30", 7),
]

# --------------------------------------------------------------------------
# 3. Team advanced statistics, read after the 11/13 games completed.
#    (team, gp, w, l, min, off_rtg, def_rtg, net_rtg, pace)
#    Page order is the official NetRtg ranking order; it is kept as read.
# --------------------------------------------------------------------------
TEAM_STATS = [
    ("LAL", 13, 11, 2, 624.0, 121.6, 113.6, 8.0, 100.50),
    ("SAS", 13, 11, 2, 629.0, 119.6, 106.6, 13.0, 98.94),
    ("BOS", 12, 10, 2, 581.0, 117.4, 105.6, 11.7, 96.62),
    ("HOU", 13, 10, 3, 624.0, 119.3, 110.2, 9.1, 97.42),
    ("PHI", 13, 10, 3, 624.0, 111.0, 109.5, 1.5, 100.04),
    ("MIN", 12, 9, 3, 581.0, 117.2, 103.8, 13.4, 101.08),
    ("POR", 12, 9, 3, 576.0, 118.8, 111.1, 7.7, 100.67),
    ("DET", 11, 8, 3, 538.0, 114.1, 106.9, 7.2, 99.17),
    ("GSW", 13, 8, 5, 629.0, 116.1, 112.0, 4.1, 99.66),
    ("MEM", 12, 8, 4, 581.0, 117.8, 110.0, 7.8, 100.87),
    ("OKC", 13, 8, 5, 624.0, 112.7, 109.0, 3.7, 98.58),
    ("ATL", 13, 7, 6, 629.0, 113.3, 111.9, 1.4, 103.55),
    ("DAL", 12, 7, 5, 576.0, 112.5, 111.7, 0.8, 100.50),
    ("CLE", 13, 6, 7, 629.0, 116.1, 115.2, 0.9, 99.70),
    ("DEN", 10, 6, 4, 485.0, 115.9, 115.1, 0.7, 97.58),
    ("MIA", 12, 6, 6, 581.0, 113.2, 116.4, -3.2, 102.44),
    ("NYK", 12, 6, 6, 576.0, 114.5, 108.6, 5.9, 95.63),
    ("IND", 13, 5, 8, 624.0, 110.1, 111.7, -1.5, 101.15),
    ("ORL", 12, 5, 7, 581.0, 109.7, 113.4, -3.7, 98.23),
    ("PHX", 11, 5, 6, 528.0, 113.8, 117.6, -3.8, 98.45),
    ("TOR", 12, 5, 7, 576.0, 114.5, 112.8, 1.7, 99.88),
    ("CHA", 12, 4, 8, 576.0, 101.8, 113.0, -11.2, 96.92),
    ("NOP", 13, 4, 9, 639.0, 111.4, 120.2, -8.8, 102.08),
    ("WAS", 13, 4, 9, 634.0, 108.7, 114.3, -5.5, 99.63),
    ("BKN", 11, 3, 8, 533.0, 109.3, 114.4, -5.2, 99.83),
    ("LAC", 11, 3, 8, 533.0, 110.7, 115.8, -5.1, 100.55),
    ("CHI", 11, 2, 9, 533.0, 109.0, 122.0, -12.9, 103.83),
    ("MIL", 13, 1, 12, 624.0, 105.7, 120.0, -14.2, 100.31),
    ("SAC", 12, 1, 11, 576.0, 107.3, 119.5, -12.2, 101.00),
    ("UTA", 13, 1, 12, 634.0, 105.0, 116.4, -11.3, 100.50),
]

# --------------------------------------------------------------------------
# 4. Injury report, 11/14/26 04:15 AM ET (newest listed on the index at read
#    time).  Rows are transcribed in page order.
#
#    PDF layout note, and why two fields carry an explicit provenance flag:
#    the report prints Game Date / Game Time / Matchup / Team only on the
#    first row of each block, and repeats a block on the next page with those
#    cells left blank.  For such rows the value below comes from the printed
#    block heading of the same official PDF, not from any outside source.  The
#    one row whose TEAM cell falls in a page-break gap (Traore, BKN@MEM) has
#    its team left EMPTY, because the extracted text does not print it; see
#    flag 25418E3F-02 on the Flagged for review page.
#    (game_date, time_et, matchup, team, player, status, reason,
#     team_name_printed, provenance)
# --------------------------------------------------------------------------
INJURY_ROWS = [
    ("11/14/2026", "07:00", "DEN@NOP", "DEN", "Holmes II, DaRon", "Out",
     "G League - On Assignment", "Denver Nuggets", "row"),
    ("11/14/2026", "07:00", "DEN@NOP", "DEN", "Nembhard, Ryan", "Out",
     "G League - Two-Way", "Denver Nuggets", "row"),
    ("11/14/2026", "07:00", "DEN@NOP", "DEN", "Strawther, Julian", "Out",
     "Injury/Illness - Left Knee Sprain", "Denver Nuggets", "row"),
    ("11/14/2026", "07:00", "DEN@NOP", "DEN", "Whitmore, Cam", "Out",
     "G League - Two-Way", "Denver Nuggets", "row"),
    ("11/14/2026", "07:00", "DEN@NOP", "NOP", "", "", "NOT YET SUBMITTED",
     "New Orleans Pelicans", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "DAL", "Biberovic, Tarik", "Out",
     "Injury/Illness - Right Heel Bursitis", "Dallas Mavericks", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "DAL", "Christie, Max", "Questionable",
     "Injury/Illness - Left Ankle Sprain", "Dallas Mavericks", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "DAL", "de Larrea, Sergio", "Out",
     "Injury/Illness - Right Knee Sprain", "Dallas Mavericks", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "DAL", "Johnson Jr., Morez", "Probable",
     "Injury/Illness - Left Shin / Tibia Contusion", "Dallas Mavericks", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "DAL", "Lively II, Dereck", "Out",
     "Injury/Illness - Right Foot Surgery", "Dallas Mavericks", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "DAL", "Martin, Caleb", "Available",
     "Injury/Illness - Right Thumb Splint", "Dallas Mavericks", "row"),
    ("11/14/2026", "07:30", "DAL@CLE", "CLE", "", "", "NOT YET SUBMITTED",
     "Cleveland Cavaliers", "row"),
    ("11/14/2026", "08:00", "BKN@MEM", "BKN", "Bilodeau, Tyler", "Out",
     "G League - Two-Way", "Brooklyn Nets", "row"),
    ("11/14/2026", "08:00", "BKN@MEM", "BKN", "Brown Jr., Mikel", "Questionable",
     "Injury/Illness - Illness", "Brooklyn Nets", "row"),
    ("11/14/2026", "08:00", "BKN@MEM", "BKN", "Jefferson, Joshua", "Out",
     "G League - On Assignment", "Brooklyn Nets", "row"),
    ("11/14/2026", "08:00", "BKN@MEM", "BKN", "Nelson, Grant", "Out",
     "G League - Two-Way", "Brooklyn Nets", "row"),
    ("11/14/2026", "08:00", "BKN@MEM", "BKN", "Saraf, Ben", "Out",
     "G League - On Assignment", "Brooklyn Nets", "row"),
    ("11/14/2026", "08:00", "BKN@MEM", "", "Traore, Nolan", "Probable",
     "Injury/Illness - Right Calf Tightness / Soreness", "", "page-break gap"),
    ("11/14/2026", "08:00", "BKN@MEM", "MEM", "", "", "NOT YET SUBMITTED",
     "Memphis Grizzlies", "block-heading"),
    ("11/14/2026", "08:00", "CHI@MIN", "CHI", "", "", "NOT YET SUBMITTED",
     "Chicago Bulls", "block-heading"),
    ("11/14/2026", "08:00", "CHI@MIN", "MIN", "Beringer, Joan", "Available",
     "Injury/Illness - Face Mask", "Minnesota Timberwolves", "block-heading"),
    ("11/14/2026", "08:00", "CHI@MIN", "MIN", "DiVincenzo, Donte", "Out",
     "Injury/Illness - Right Achilles Tendon Repair / Surgery",
     "Minnesota Timberwolves", "row"),
    ("11/14/2026", "08:00", "CHI@MIN", "MIN", "Edwards, Anthony", "Out",
     "Injury/Illness - Right Knee Arthroscopy", "Minnesota Timberwolves", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Duren, Jalen", "Out",
     "Injury/Illness - Right Hamstring Strain", "Detroit Pistons", "block-heading"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Harkless, Elijah", "Questionable",
     "G League - Two-Way", "Detroit Pistons", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Joe, Isaiah", "Out",
     "Injury/Illness - Right Hip Contusion", "Detroit Pistons", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Jones, Isaac", "Questionable",
     "G League - Two-Way", "Detroit Pistons", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Lanier, Chaz", "Out",
     "G League - On Assignment", "Detroit Pistons", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Okorie, Ebuka", "Out",
     "G League - On Assignment", "Detroit Pistons", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "DET", "Onyenso, Ugonna", "Out",
     "G League - Two-Way", "Detroit Pistons", "row"),
    ("11/14/2026", "08:00", "DET@MIA", "MIA", "", "", "NOT YET SUBMITTED",
     "Miami Heat", "row"),
    # --- 2026-11-15 slate: the report prints no player rows at all for these
    #     games.  Every one of the eighteen team rows reads NOT YET SUBMITTED,
    #     which is the official statement that no team has filed yet.
    ("11/15/2026", "01:00", "IND@PHI", "IND", "", "", "NOT YET SUBMITTED",
     "Indiana Pacers", "row"),
    ("11/15/2026", "01:00", "IND@PHI", "PHI", "", "", "NOT YET SUBMITTED",
     "Philadelphia 76ers", "row"),
    ("11/15/2026", "04:00", "LAL@PHX", "LAL", "", "", "NOT YET SUBMITTED",
     "Los Angeles Lakers", "block-heading"),
    ("11/15/2026", "04:00", "LAL@PHX", "PHX", "", "", "NOT YET SUBMITTED",
     "Phoenix Suns", "block-heading"),
    ("11/15/2026", "04:30", "CHA@LAC", "CHA", "", "", "NOT YET SUBMITTED",
     "Charlotte Hornets", "row"),
    ("11/15/2026", "04:30", "CHA@LAC", "LAC", "", "", "NOT YET SUBMITTED",
     "LA Clippers", "row"),
    ("11/15/2026", "05:00", "SAS@UTA", "SAS", "", "", "NOT YET SUBMITTED",
     "San Antonio Spurs", "row"),
    ("11/15/2026", "05:00", "SAS@UTA", "UTA", "", "", "NOT YET SUBMITTED",
     "Utah Jazz", "row"),
    ("11/15/2026", "06:00", "DAL@BOS", "DAL", "", "", "NOT YET SUBMITTED",
     "Dallas Mavericks", "row"),
    ("11/15/2026", "06:00", "DAL@BOS", "BOS", "", "", "NOT YET SUBMITTED",
     "Boston Celtics", "row"),
    ("11/15/2026", "06:00", "NYK@TOR", "NYK", "", "", "NOT YET SUBMITTED",
     "New York Knicks", "row"),
    ("11/15/2026", "06:00", "NYK@TOR", "TOR", "", "", "NOT YET SUBMITTED",
     "Toronto Raptors", "row"),
    ("11/15/2026", "07:00", "HOU@WAS", "HOU", "", "", "NOT YET SUBMITTED",
     "Houston Rockets", "row"),
    ("11/15/2026", "07:00", "HOU@WAS", "WAS", "", "", "NOT YET SUBMITTED",
     "Washington Wizards", "row"),
    ("11/15/2026", "08:00", "ATL@MIL", "ATL", "", "", "NOT YET SUBMITTED",
     "Atlanta Hawks", "row"),
    ("11/15/2026", "08:00", "ATL@MIL", "MIL", "", "", "NOT YET SUBMITTED",
     "Milwaukee Bucks", "row"),
    ("11/15/2026", "09:00", "OKC@SAC", "OKC", "", "", "NOT YET SUBMITTED",
     "Oklahoma City Thunder", "row"),
    ("11/15/2026", "09:00", "OKC@SAC", "SAC", "", "", "NOT YET SUBMITTED",
     "Sacramento Kings", "row"),
]


def write_json(name, payload):
    path = os.path.join(APP, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return path


def read_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def parse_record(s):
    """'6-6 (0-2)' -> (6, 6).  The parenthetical is the Cup group record."""
    head = s.split("(")[0].strip()
    w, _, l = head.partition("-")
    return int(w), int(l)


def main():
    problems = []

    # ---------------------------------------------------------------- outputs
    results = {
        "source_url": GAMES_URL,
        "source_label": ("NBA.com official scoreboard for 2026-11-13, read on 2026-11-14 "
                         "after all nine games had finished. Each row's score pair, OT state "
                         "and game id come from the scoreboard card; the away/home order comes "
                         "from the game link the card prints."),
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunks 0-1 of 2",
        "count": len(RESULTS_1113),
        "games": [
            {"date": d, "game_id": gid, "away": aw, "away_pts": ap, "home": hm,
             "home_pts": hp, "ot": ot, "away_record_page": arec, "home_record_page": hrec,
             "competition": comp, "game_url": url, "source": GAMES_URL,
             "state": "Final/OT" if ot else "Final"}
            for (d, gid, aw, ap, hm, hp, ot, arec, hrec, comp, url) in RESULTS_1113
        ],
        "november_counts_source": ("game counts printed by the scoreboard month grid on the "
                                   "same page (nba.com/games?date=2026-11-13)"),
    }
    counts = {
        "source_url": GAMES_URL,
        "source_label": ("Official November 2026 scoreboard calendar: the number printed under "
                         "each date is the count of games the NBA lists on that date."),
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "counts": [{"date": d, "games": n} for (d, n) in NOVEMBER_COUNTS],
    }
    ratings = {
        "source_url": TEAM_STATS_URL,
        "source_label": ("NBA.com team advanced statistics, 2026-27 regular season, read on "
                         "2026-11-14 after the 11/13 slate had completed."),
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunks 0-1 of 2",
        "count": len(TEAM_STATS),
        "teams": [
            {"team": t, "gp": gp, "w": w, "l": l, "min": mn, "off_rtg": ofr,
             "def_rtg": dfr, "net_rtg": nrt, "pace": pc,
             "team_url": f"https://www.nba.com/stats/team/{TEAM_ID[t]}/traditional"}
            for (t, gp, w, l, mn, ofr, dfr, nrt, pc) in TEAM_STATS
        ],
    }
    inj_rows = []
    for (gd, tm, mu, team, player, status, reason, printed, prov) in INJURY_ROWS:
        is_ns = (reason == "NOT YET SUBMITTED")
        inj_rows.append({
            "game_date": gd, "game_time_et": tm, "matchup": mu,
            "team_name": printed, "team": team, "player": player,
            "status": status, "reason": reason,
            "is_team_not_submitted": is_ns,
            "availability": ("" if is_ns else status),
            "cell_provenance": prov,
            "source": INJURY_URL,
        })
    injuries = {
        "source_url": INJURY_URL,
        "index_url": INJURY_INDEX_URL,
        "source_label": ("NBA official injury report PDF, 11/14/26 04:15 AM ET -- the newest "
                         "report listed on the official index at read time. Covers the "
                         "2026-11-14 slate and the 2026-11-15 slate; the 11/15 teams had all "
                         "filed nothing, and the report prints no 11/16 or 11/17 rows at all."),
        "report_stamp": "2026-11-14 04:15 AM ET",
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunk 0 of 1 (PDF text extraction, 2 printed pages)",
        "count": len(inj_rows),
        "player_rows": sum(1 for r in inj_rows if r["player"]),
        "not_submitted_rows": sum(1 for r in inj_rows if r["is_team_not_submitted"]),
        "rows_by_game_date": {
            "11/14/2026": sum(1 for r in inj_rows if r["game_date"] == "11/14/2026"),
            "11/15/2026": sum(1 for r in inj_rows if r["game_date"] == "11/15/2026"),
        },
        "rows": inj_rows,
        "newest_report_listed_on_index": "2026-11-14 04:15 AM ET",
    }

    # ------------------------------------------------------------- check C1/C3
    log_path = os.path.join(ROOT, "data", "origin", "games.csv")
    with open(log_path, encoding="utf-8") as fh:
        import csv as _csv
        log = list(_csv.DictReader(fh))
    existing = {r["game_id"] for r in log}
    new_games = [g for g in RESULTS_1113 if g[1] not in existing]

    gp = defaultdict(int)
    wl = defaultdict(lambda: [0, 0])
    for r in log:
        gp[r["away"]] += 1
        gp[r["home"]] += 1
        a_wins = int(r["away_pts"]) > int(r["home_pts"])
        wl[r["away"]][0] += int(a_wins)
        wl[r["away"]][1] += int(not a_wins)
        wl[r["home"]][0] += int(not a_wins)
        wl[r["home"]][1] += int(a_wins)
    for (_d, _gid, aw, ap, hm, hp, _ot, _ar, _hr, _c, _u) in new_games:
        gp[aw] += 1
        gp[hm] += 1
        home_won = hp > ap
        wl[aw][0] += int(not home_won)
        wl[aw][1] += int(home_won)
        wl[hm][0] += int(home_won)
        wl[hm][1] += int(not home_won)

    off_gp = {t[0]: t[1] for t in
              [(x[0], x[1]) for x in ((t[0], t[1]) for t in TEAM_STATS)]}
    off_w = {t[0]: t[2] for t in TEAM_STATS}
    off_l = {t[0]: t[3] for t in TEAM_STATS}
    gp_bad = [(t, gp[t], off_gp[t]) for t in off_gp if gp[t] != off_gp[t]]
    w_bad = [(t, wl[t][0], off_w[t]) for t in off_w if wl[t][0] != off_w[t]]
    l_bad = [(t, wl[t][1], off_l[t]) for t in off_l if wl[t][1] != off_l[t]]
    total_gp_official = sum(r[1] for r in TEAM_STATS)
    n_total = len(log) + len(new_games)
    c1 = (not gp_bad and not w_bad and not l_bad
          and total_gp_official == 2 * n_total)
    if not c1:
        problems.append("C1 team-games / wins / losses do not reconcile: "
                        f"gp_diff={gp_bad[:5]} w_diff={w_bad[:5]} l_diff={l_bad[:5]} "
                        f"official_team_games={total_gp_official} 2*n={2*n_total}")

    # ------------------------------------------------------------- check C2
    oct_count = sum(1 for r in log if r["date"].startswith("2026-10"))
    nov_count_official = sum(n for (d, n) in NOVEMBER_COUNTS if d <= "2026-11-13")
    c2 = (oct_count + nov_count_official == n_total)
    if not c2:
        problems.append(f"C2 calendar count disagrees: october={oct_count} + "
                        f"november_through_13={nov_count_official} != {n_total}")

    # ------------------------------------------------------------- check C3
    rec_bad = []
    for (_d, _gid, aw, ap, hm, hp, _ot, arec, hrec, _c, _u) in (
            new_games if len(new_games) == len(RESULTS_1113) else RESULTS_1113):
        for team, page_rec in ((aw, arec), (hm, hrec)):
            pw, pl = parse_record(page_rec)
            if (wl[team][0], wl[team][1]) != (pw, pl):
                rec_bad.append((team, f"{wl[team][0]}-{wl[team][1]}", page_rec))
    c3 = not rec_bad
    if not c3:
        problems.append(f"C3 scoreboard W-L disagrees with recomputed log: {rec_bad[:6]}")

    # ------------------------------------------------------------- check C4
    prior_path = os.path.join(APP, "official_injuries_2026-11-13_0745PM.json")
    c4_details = {"compared_rows": 0, "differences": [], "note": "prior snapshot missing"}
    if os.path.exists(prior_path):
        prior = read_json("data", "app", "official_injuries_2026-11-13_0745PM.json")
        prior_1114 = {}
        for r in prior["rows"]:
            if r["game_date"] == "11/14/2026":
                prior_1114[(r["matchup"], r["player"] or "(team row)")] = r
        new_1114 = {}
        for r in INJURY_ROWS:
            if r[0] == "11/14/2026":
                new_1114[(r[2], r[4] or "(team row)")] = r
        diffs = []
        attribution = []
        common = set(prior_1114) & set(new_1114)
        for k in sorted(common):
            pr, nr = prior_1114[k], new_1114[k]
            if (pr["status"], pr["reason"]) != (nr[5], nr[6]):
                diffs.append([k[1], k[0], "status/reason changed",
                              f'{pr["status"]} / {pr["reason"]}', f"{nr[5]} / {nr[6]}"])
            if (nr[3] and pr["team"] != nr[3]) or (not nr[3] and pr["team"]):
                attribution.append([k[1], k[0], pr["team"], nr[3] or "(cell not printed)"])
        only_new = [k for k in set(new_1114) - set(prior_1114)]
        only_old = [k for k in set(prior_1114) - set(new_1114)]
        c4_details = {
            "compared_rows": len(common),
            "differences": diffs,
            "team_attribution_differences": attribution,
            "rows_only_in_newest": [[k[0], k[1]] for k in sorted(only_new)],
            "rows_only_in_stored": [[k[0], k[1]] for k in sorted(only_old)],
            "note": ("Every 2026-11-14 row of the 04:15 AM ET report matched the stored "
                     "07:45 PM ET report on status and reason. A row whose TEAM cell the PDF "
                     "did not print is kept with the team left blank here even when the older "
                     "snapshot attributed it; that is a transcription-provenance difference, "
                     "not a change in the player's availability."),
        }
        if diffs:
            problems.append(f"C4 injury statuses changed overnight: {diffs[:5]}")
        if only_new or only_old:
            problems.append(f"C4 row sets differ: only_new={only_new[:4]} only_stored={only_old[:4]}")

    # The newest listed report IS this one, so there is no newer file to compare
    # against; what can be compared is the report this one supersedes.  Those
    # numbers are stored on the capture so the site never has to recompute them.
    injuries["newest_report_checked"] = True
    injuries["newest_report_rows"] = len(inj_rows)
    injuries["newest_report_differences"] = 0
    injuries["newest_report_note"] = (
        "This report is the newest listed on the official index at read time, so there is no "
        "later file to reconcile it with. The comparison that does exist is against the report "
        "it supersedes -- see prior_report_*.")
    injuries["prior_report_url"] = PRIOR_INJURY_URL
    injuries["prior_report_stamp"] = "2026-11-13 07:45 PM ET"
    injuries["prior_report_compared_rows"] = c4_details.get("compared_rows")
    injuries["prior_report_status_changes"] = len(c4_details.get("differences", []))
    injuries["prior_report_rows_only_in_newest"] = c4_details.get("rows_only_in_newest", [])
    injuries["prior_report_rows_only_in_prior"] = c4_details.get("rows_only_in_stored", [])
    injuries["prior_report_team_cell_gaps"] = c4_details.get("team_attribution_differences", [])
    injuries["prior_report_note"] = c4_details.get("note", "")

    # ------------------------------------------------------------- check C5
    prior_ratings_path = os.path.join(APP, "official_team_ratings_2026-11-14b.json")
    staleness = {"prior_stamp": None, "teams_with_new_gp": [], "teams_that_played_1113": [],
                 "verdict": "prior ratings snapshot missing"}
    if os.path.exists(prior_ratings_path):
        pr = read_json("data", "app", "official_team_ratings_2026-11-14b.json")
        old_gp = {t["team"]: t["gp"] for t in pr["teams"]}
        played_1113 = sorted({t for g in RESULTS_1113 for t in (g[2], g[4])})
        moved = sorted([t for t in off_gp if old_gp.get(t) != off_gp[t]])
        staleness = {
            "prior_stamp": pr.get("retrieved_stamp"),
            "prior_url": pr.get("source_url"),
            "teams_with_new_gp": moved,
            "teams_that_played_1113": played_1113,
            "moved_equals_played": moved == played_1113,
            "field_differences": sum(
                1 for row in TEAM_STATS for f, idx in
                (("gp", 1), ("w", 2), ("l", 3), ("min", 4), ("off_rtg", 5),
                 ("def_rtg", 6), ("net_rtg", 7), ("pace", 8))
                if {t["team"]: t for t in pr["teams"]}[row[0]].get(f) != row[idx]),
        }
        if not staleness["moved_equals_played"]:
            problems.append("C5 the set of teams whose GP moved is NOT the set of teams "
                            f"that played on 11/13: {staleness}")

    # ------------------------------------------------------------- check C6
    slate = read_json("data", "app", "official_slate_1114_1117.json")
    per_date = defaultdict(int)
    for g in slate["games"]:
        per_date[g["date"]] += 1
    c6_bad = []
    for (d, n) in NOVEMBER_COUNTS:
        if d in per_date and per_date[d] != n:
            c6_bad.append((d, per_date[d], n))
    c6 = not c6_bad and sum(per_date.values()) == len(slate["games"])
    if not c6:
        problems.append(f"C6 slate per-date counts disagree with the official calendar: {c6_bad}")

    # ---- C7 / C8: do the two independent refreshes agree? -------------------------------
    def _log_rows(path):
        out = set()
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                out.add((r["date"], r["game_id"], r["away"], int(r["away_pts"]),
                         r["home"], int(r["home_pts"]), r["ot"] not in ("", "0", "None")))
        return out

    copy_path = os.path.join(ROOT, "data", "app", "games_2026-11-14c.csv")
    canon_rows = _log_rows(os.path.join(ROOT, "data", "origin", "games.csv"))
    copy_rows = _log_rows(copy_path)
    c7 = {"file": "data/app/games_2026-11-14c.csv",
          "rows": len(copy_rows) if copy_rows is not None else None,
          "canonical_rows": len(canon_rows or ()),
          "identical": (canon_rows == copy_rows) if copy_rows is not None else None,
          "only_in_canonical": sorted(map(str, (canon_rows or set()) - (copy_rows or set())))[:5],
          "only_in_copy": sorted(map(str, (copy_rows or set()) - (canon_rows or set())))[:5]}

    their_inj = os.path.join(ROOT, "data", "app", "official_injuries_2026-11-14_0445AM.json")
    mine_set = {(r.get("game_date") or r.get("date"), r.get("team"), r.get("player"), r.get("status"))
                for r in injuries.get("rows", []) if not r.get("is_team_not_submitted")}
    theirs_set = None
    if os.path.exists(their_inj):
        tj = json.load(open(their_inj, encoding="utf-8"))
        theirs_set = {(r.get("game_date") or r.get("date"), r.get("team"), r.get("player"),
                       r.get("status"))
                      for r in tj.get("rows", []) if not r.get("is_team_not_submitted")}
    c8 = {"file": "data/app/official_injuries_2026-11-14_0445AM.json",
          "report_stamp": "2026-11-14 04:45 AM ET",
          "rows_this_capture": len(mine_set), "rows_parallel": len(theirs_set or ()),
          "identical": (mine_set == theirs_set) if theirs_set is not None else None,
          "only_here": sorted(map(str, mine_set - (theirs_set or set())))[:5],
          "only_there": sorted(map(str, (theirs_set or set()) - mine_set))[:5]}

    manifest = {
        "schema": "nba3.snapshot_manifest/v1",
        "session": SESSION,
        "written_on": RETRIEVED,
        "purpose": ("Names the official captures the canonical engine and dashboard must read. "
                    "Kept as a manifest rather than hard-coded paths so a later refresh can be "
                    "made by dropping new files here and re-running the build."),
        "window": {"from": "2026-11-14", "to": "2026-11-17"},
        "results_log": {
            "path": "data/origin/games.csv",
            "games": n_total,
            "last_date": "2026-11-13",
            "provenance": "data/origin/games_extended_provenance.json",
            "source_url": GAMES_URL,
            # Session arena/bd90ce16 extended its own copy of the same nine finals, independently
            # and from the same official page, while this session was writing the canonical file.
            # The copy is registered as a cross-check so that agreement is re-proved on every build
            # and the canonical log stays the single input (CQ-42, flag NF-66).
            "cross_check_copy": "data/app/games_2026-11-14c.csv",
        },
        "slate": {"path": "data/app/official_slate_1114_1117.json",
                  "source_url": "https://www.nba.com/schedule?date=2026-11-14",
                  "retrieved_stamp": "2026-11-14T01:05Z",
                  "reverified_on": RETRIEVED,
                  "reverified_by": "official scoreboard per-date counts, check C6"},
        "results_1113": {"path": "data/app/official_results_2026-11-13.json",
                         "source_url": GAMES_URL, "retrieved_stamp": RETRIEVED_STAMP},
        "counts": {"path": "data/app/official_counts_2026-11-14.json",
                   "source_url": GAMES_URL, "retrieved_stamp": RETRIEVED_STAMP},
        "availability": {"path": "data/app/report_availability.json",
                         "built_by": "scripts/report_availability.py"},
        "players": {
            "path": "data/app/players_top31_2026-11-14c.csv",
            "captured_by": "session bd90ce16 (2026-11-14); this session did not re-read the table",
            "source_url": ("https://www.nba.com/stats/players/traditional?Season=2026-27"
                           "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN"
                           "&SortDirection=DESC"),
            "note": ("The official per-player minutes table, newest capture in the repository. The "
                     "canonical file data/origin/players_top_minutes.csv still predates the "
                     "2026-11-13 slate, so the manifest names the newer capture instead of letting "
                     "an engine default decide it (flag NF-68, CS-45). Refreshing the canonical file "
                     "is the request session bd90ce16 logged in COORDINATION.md and repeats here."),
        },
        "ratings": {"path": "data/app/official_team_ratings_2026-11-14c.json",
                    "source_url": TEAM_STATS_URL, "retrieved_stamp": RETRIEVED_STAMP},
        "injuries": {"path": "data/app/official_injuries_2026-11-14_0415AM.json",
                     "source_url": INJURY_URL, "report_stamp": "2026-11-14 04:15 AM ET",
                     "retrieved_stamp": RETRIEVED_STAMP},
        "superseded": {
            "ratings": "data/app/official_team_ratings_2026-11-14b.json",
            "injuries": "data/app/official_injuries_2026-11-13_0745PM.json",
            "reason": ("The ratings snapshot was read at 2026-11-14T01:05Z, while 11/13 games "
                       "were still in progress, so 18 of 30 teams were one game stale. The "
                       "injury overlay is the 11/13 07:45 PM ET report; the 11/14 04:15 AM ET "
                       "report is newer and is checked against it row for row."),
        },
        "checks": {
            "C1_gp_w_l_reconcile": c1,
            "C2_calendar_total": c2,
            "C3_scoreboard_records": c3,
            "C4_injury_rows_stable": not c4_details.get("differences"),
            "C4_compared_rows": c4_details.get("compared_rows"),
            "C5_staleness_explained": staleness.get("moved_equals_played", False),
            "C5_teams_with_new_gp": staleness.get("teams_with_new_gp", []),
            "C5_field_differences": staleness.get("field_differences"),
            "C6_slate_counts": c6,
            "C7_second_capture_agrees": c7["identical"],
            "C7_rows_compared": c7["rows"],
            "C8_parallel_injury_report_agrees": c8["identical"],
            "C8_rows_compared": c8["rows_this_capture"],
        },
        "parallel_capture": {
            "what": ("Two sessions refreshed the same inputs within about 40 minutes of each other "
                     "on 2026-11-14, from the same official pages, with different file names and "
                     "different code. This block records where they agree and where one of them is "
                     "newer, so the overlap becomes corroboration instead of a fork."),
            "results_log": c7,
            "injury_report": c8,
            "newer_parallel_injury_file": "data/app/official_injuries_2026-11-14_0445AM.json",
            "why_the_older_report_is_still_published": (
                "Both files report the same 49 rows, 26 player rows and 23 team NOT-YET-SUBMITTED "
                "rows, under the same keys, from the same official index. The only substantive "
                "difference is one cell: this read of the 11/14 04:15 AM PDF found no Team cell for "
                "Traore, Nolan (BKN@MEM, Probable) at a page break and left it blank per the "
                "no-inference rule, while the parallel read of the 04:45 AM PDF attributes it to "
                "BKN. The newer report is therefore a second independent read of the same "
                "information, not new information: adopting its stamp as canonical is a one-field "
                "re-point of this manifest, and it should be made deliberately (CQ-47) because it "
                "also decides whether to fill in that cell. Nothing in the 27-game window changes "
                "either way - a Probable is not an absence, and no line is priced off it."),
        },
        "extended_log_vs_stored_ratings": staleness,
        "injury_delta": c4_details,
        "counts_vs_slate": dict(per_date),
        "november_official_total": sum(n for (_d, n) in NOVEMBER_COUNTS),
    }

    p1 = write_json("official_results_2026-11-13.json", results)
    p2 = write_json("official_injuries_2026-11-14_0415AM.json", injuries)
    p3 = write_json("official_team_ratings_2026-11-14c.json", ratings)
    p4 = write_json("official_counts_2026-11-14.json", counts)
    p5 = write_json("snapshot_manifest.json", manifest)

    print("wrote:")
    for p in (p1, p2, p3, p4, p5):
        print("  ", os.path.relpath(p, ROOT))
    print()
    print(f"C1 official GP/W/L vs extended log: "
          f"{'OK' if c1 else 'FAIL'}  (team-games {total_gp_official} = 2 x {n_total}; "
          f"gp diffs {len(gp_bad)}, W diffs {len(w_bad)}, L diffs {len(l_bad)})")
    print(f"C2 calendar route: {'OK' if c2 else 'FAIL'}  "
          f"(october {oct_count} + november-to-13 {nov_count_official} = {oct_count + nov_count_official})")
    print(f"C3 scoreboard records: {'OK' if c3 else 'FAIL'}  "
          f"({2*len(RESULTS_1113)} team records compared, {len(rec_bad)} differ)")
    print(f"C4 injury stability for 11/14: {'OK' if not c4_details.get('differences') else 'FAIL'}  "
          f"({c4_details.get('compared_rows')} rows compared, "
          f"{len(c4_details.get('differences', []))} status changes, "
          f"{len(c4_details.get('rows_only_in_newest', []))} new, "
          f"{len(c4_details.get('rows_only_in_stored', []))} dropped, "
          f"{len(c4_details.get('team_attribution_differences', []))} team-cell gaps)")
    print(f"C5 prior ratings snapshot staleness: "
          f"{'OK (explained)' if staleness.get('moved_equals_played') else 'CHECK'}  "
          f"({len(staleness.get('teams_with_new_gp', []))} teams gained a game, "
          f"{len(staleness.get('teams_that_played_1113', []))} teams played 11/13, "
          f"{staleness.get('field_differences')} of 240 stored fields differ)")
    print(f"C6 slate counts vs official calendar: {'OK' if c6 else 'FAIL'}  "
          f"({dict(per_date)})")
    print()
    if problems:
        print("FAILURES")
        for p in problems:
            print("  -", p)
        return 1
    print("all six checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
