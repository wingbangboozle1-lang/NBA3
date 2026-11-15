#!/usr/bin/env python3
"""Official capture for the 2026-11-15 game day (session ``arena/bb0c83a4-nba3``).

Four official pages were read with the Arena fetch tool on 2026-11-15 between
11:20Z and 11:40Z (06:20-06:40 AM ET) and are transcribed here verbatim. This
module rebuilds every artefact from those transcriptions **offline**, so CI can
replay it with no network and the committed JSON cannot drift from the text.

What was read
-------------
1. https://official.nba.com/nba-injury-report-2026-27-season/
   The report index. Its page text listed the November 15 reports from
   12:00 a.m. ET through **6:00 a.m. ET**, and no later slot. Reports are
   stated by the page to be "updated on a continual basis throughout the day".

2. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf
   Parsed twice by the fetch tool (chunk 0 and chunk 1). Between the two reads
   the index advanced to 6:15 a.m. ET, and this file was fetched successfully,
   so **6:15 AM ET is the newest report that exists at capture time**. Its
   verbatim transcription is
   ``data/app/official_injuries_2026-11-15_0615AM_raw.md``.
   The 6:00 AM read of the same report was compared row for row before 6:15
   was adopted; the two agree on every row they both print.

3. https://www.nba.com/schedule?date=2026-11-15
   chunks 0, 1 and 2 (of 9) and https://www.nba.com/schedule?date=2026-11-17
   chunk 1, which re-render the whole Week 4 / Week 5 block. This session takes
   every game from 2026-11-15 through 2026-11-18 inclusive -- today plus the
   maximum three-day forward window the brief asks for.
   The five 2026-11-14 games are **Final** on the page with printed scores, so
   they are results, not an upcoming slate, and are carried into the results
   log instead of the priced window.

4. https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season
   chunks 0 and 1 of 2. GP, W, L, MIN, OffRtg, DefRtg, NetRtg and PACE for all
   30 teams, read at 11:35Z on 2026-11-15 (after the 11/14 slate completed).

5. https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC
   chunks 2, 3, 4 and 5 of 9 -- the top 31 players by minutes per game, which is
   the same Top-31 cut the previous captures used, so the two are comparable.

THE TRANSCRIPTION RULES, and why they matter
--------------------------------------------
The PDF is printed as six page blocks and the text extraction breaks a table
row across a page boundary in several places. A row whose cells are blank at
the start of a block belongs to the matchup, team and game date printed most
recently above it **in the same report**. Carrying those cells forward is not
an inference: it is how the printed table is to be read. Every row therefore
records ``cell_provenance`` so a reviewer can see exactly which cells were
printed on the row itself and which were carried.

A team that withheld its filing prints one row with the literal string
``NOT YET SUBMITTED`` in the *Reason* column, no player name, and no status.
That is an official statement that the team has not filed, so it is stored as
its own row with ``is_team_not_submitted = True`` and is never read as
"nobody is out".

A team that filed but named no player simply prints **no row at all**. It
cannot be distinguished from a team whose block fell off the rendered page.
There is one such case in this report (the New York Knicks, NYK@TOR) and it is
flagged, not filled in. See ``filed_but_no_rows`` below and flag
``F-BB-02`` in the dashboard.

Run:  python3 scripts/capture_official_2026_11_15.py
Writes (all under data/app/):
  official_injuries_2026-11-15_0615AM.json
  official_slate_1115_1118.json
  official_team_ratings_2026-11-15.json
  official_results_2026-11-14.json
  players_top31_2026-11-15.csv
  official_capture_2026-11-15.json      (the run's own cross-check report)
"""
import csv
import json
import os
import re
from collections import defaultdict, OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

RETRIEVED_ON = "2026-11-15"
RETRIEVED_STAMP = "2026-11-15T11:40Z"       # 06:40 AM ET

INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJURY_URL = ("https://ak-static.cms.nba.com/referee/injury/"
              "Injury-Report_2026-11-15_06_15AM.pdf")
INJURY_RAW = os.path.join(APP, "official_injuries_2026-11-15_0615AM_raw.md")
SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-15"
TEAM_STATS_URL = ("https://www.nba.com/stats/teams/advanced"
                  "?Season=2026-27&SeasonType=Regular%20Season")
PLAYERS_URL = ("https://www.nba.com/stats/players/traditional"
               "?Season=2026-27&SeasonType=Regular%20Season&PerPage=100"
               "&SortColumn=MIN&SortDirection=DESC")
SCOREBOARD_1114 = "https://www.nba.com/games?date=2026-11-14"

# 5.15.2 of the CBA text is not quoted here; the index page states the filing
# rule verbatim, and that exact wording is the only one this project relies on.
RULE_QUOTE = (
    "By 5 p.m. local time the day before a game (other than the second day of a "
    "back-to-back), teams must designate a participation status and identify a "
    "specific injury, illness, other medical condition, or other reason for any "
    "player whose participation in the game may be affected for any reason. For "
    "the second game of a back-to-back, teams must report the above information "
    "by 1 p.m. local time on the day of the game.")
RULE_QUOTE_2 = (
    "In addition, teams are required to submit a game-day injury report between "
    "11 a.m. and 1 p.m. local time (and between 8 and 10 a.m. for tip-offs 5 "
    "p.m. or earlier) on game days (besides the second game of a back-to-back).")

TEAM_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU",
    "Indiana Pacers": "IND", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
TEAM_ABBR = set(TEAM_NAME_TO_ABBR.values())

VALID_STATUS = ("Out", "Doubtful", "Questionable", "Probable", "Available")


# ==========================================================================
# 1. Slate -- 2026-11-15 .. 2026-11-18, transcribed from nba.com/schedule
#    (date, time_et, away, home, game_id, venue, city, competition)
# ==========================================================================
SLATE = [
    # Sunday, November 15 -- "9 Games"
    ("2026-11-15", "1:00 PM", "IND", "PHI", "0022600236", "Xfinity Mobile Arena", "Philadelphia, PA", ""),
    ("2026-11-15", "4:00 PM", "LAL", "PHX", "0022600237", "Mortgage Matchup Center", "Phoenix, AZ", ""),
    ("2026-11-15", "4:30 PM", "CHA", "LAC", "0022600238", "Intuit Dome", "Inglewood, CA", ""),
    ("2026-11-15", "5:00 PM", "SAS", "UTA", "0022600239", "Delta Center", "Salt Lake City, UT", ""),
    ("2026-11-15", "6:00 PM", "DAL", "BOS", "0022600240", "TD Garden", "Boston, MA", ""),
    ("2026-11-15", "6:00 PM", "NYK", "TOR", "0022600241", "Scotiabank Arena", "Toronto, ON", ""),
    ("2026-11-15", "7:00 PM", "HOU", "WAS", "0022600242", "Capital One Arena", "Washington, DC", ""),
    ("2026-11-15", "8:00 PM", "ATL", "MIL", "0022600243", "Fiserv Forum", "Milwaukee, WI", ""),
    ("2026-11-15", "9:00 PM", "OKC", "SAC", "0022600244", "Golden 1 Center", "Sacramento, CA", ""),
    # Monday, November 16 -- "8 Games"
    ("2026-11-16", "7:00 PM", "ORL", "BOS", "0022600245", "TD Garden", "Boston, MA", ""),
    ("2026-11-16", "7:00 PM", "CHI", "CLE", "0022600246", "Rocket Arena", "Cleveland, OH", ""),
    ("2026-11-16", "7:00 PM", "MEM", "WAS", "0022600247", "Capital One Arena", "Washington, DC", ""),
    ("2026-11-16", "7:30 PM", "PHI", "BKN", "0022600248", "Barclays Center", "Brooklyn, NY", ""),
    ("2026-11-16", "7:30 PM", "HOU", "MIA", "0022600249", "Kaseya Center", "Miami, FL", ""),
    ("2026-11-16", "8:00 PM", "POR", "MIN", "0022600250", "Target Center", "Minneapolis, MN", ""),
    ("2026-11-16", "8:00 PM", "GSW", "NOP", "0022600251", "Smoothie King Center", "New Orleans, LA", ""),
    ("2026-11-16", "9:00 PM", "PHX", "DEN", "0022600252", "Ball Arena", "Denver, CO", ""),
    # Tuesday, November 17 -- "5 Games"
    ("2026-11-17", "7:30 PM", "NYK", "TOR", "0022600253", "Scotiabank Arena", "Toronto, ON", ""),
    ("2026-11-17", "8:00 PM", "POR", "MIN", "0022600254", "Target Center", "Minneapolis, MN", ""),
    ("2026-11-17", "8:00 PM", "DET", "SAS", "0022600255", "Frost Bank Center", "San Antonio, TX", ""),
    ("2026-11-17", "10:30 PM", "UTA", "LAC", "0022600257", "Intuit Dome", "Inglewood, CA", ""),
    ("2026-11-17", "11:00 PM", "CHA", "LAL", "0022600256", "Crypto.com Arena", "Los Angeles, CA", ""),
    # Wednesday, November 18 -- the page heading reads "12 Games". Seven cards
    # were rendered inside the chunk window this session read; the five that
    # follow (game ids 0022600270 and later belong to 11/19, so the missing
    # ids are 0022600258-0022600269 minus those listed) are NOT transcribed
    # here and are left out rather than guessed. Flag F-BB-03.
    ("2026-11-18", "7:00 PM", "MEM", "CLE", "0022600258", "Rocket Arena", "Cleveland, OH", ""),
    ("2026-11-18", "7:00 PM", "HOU", "IND", "0022600259", "Gainbridge Fieldhouse", "Indianapolis, IN", ""),
    ("2026-11-18", "7:00 PM", "MIL", "MIA", "0022600260", "Kaseya Center", "Miami, FL", ""),
    ("2026-11-18", "7:00 PM", "PHI", "ORL", "0022600261", "Kia Center", "Orlando, FL", ""),
    ("2026-11-18", "7:30 PM", "CHI", "BKN", "0022600262", "Barclays Center", "Brooklyn, NY", ""),
    ("2026-11-18", "7:30 PM", "WAS", "TOR", "0022600263", "Scotiabank Arena", "Toronto, ON", ""),
    ("2026-11-18", "8:00 PM", "DET", "NOP", "0022600264", "Smoothie King Center", "New Orleans, LA", ""),
    ("2026-11-18", "8:00 PM", "ATL", "OKC", "0022600265", "Paycom Center", "Oklahoma City, OK", ""),
    ("2026-11-18", "8:00 PM", "GSW", "DAL", "0022600267", "American Airlines Center", "Dallas, TX", ""),
    ("2026-11-18", "9:30 PM", "BOS", "DEN", "0022600266", "Ball Arena", "Denver, CO", ""),
    ("2026-11-18", "10:00 PM", "UTA", "LAL", "0022600268", "Crypto.com Arena", "Los Angeles, CA", ""),
    ("2026-11-18", "10:00 PM", "PHX", "SAC", "0022600269", "Golden 1 Center", "Sacramento, CA", ""),
]

# Two matchups repeat inside the window: POR@MIN on 11/16 and 11/17, and
# NYK@TOR on 11/15 and 11/17. Both were re-read on
# https://www.nba.com/schedule?date=2026-11-17 and print twice with different
# game ids, so they are not transcription duplicates. Recorded, not corrected.
REPEATED_MATCHUPS = [("POR@MIN", ["2026-11-16", "2026-11-17"]),
                     ("NYK@TOR", ["2026-11-15", "2026-11-17"])]

# 2026-11-14 finals, from https://www.nba.com/schedule?date=2026-11-15
# ("Final" cards). (date, gid, away, away_pts, home, home_pts, ot)
# Overtime is 0 for all five: the cards print no OT marker next to the scores.
RESULTS_1114 = [
    ("2026-11-14", "0022600231", "DEN", 116, "NOP", 108, 0),
    ("2026-11-14", "0022600232", "DAL", 117, "CLE", 127, 0),
    ("2026-11-14", "0022600233", "DET", 117, "MIA", 137, 0),
    ("2026-11-14", "0022600234", "BKN", 110, "MEM", 129, 0),
    ("2026-11-14", "0022600235", "CHI", 117, "MIN", 106, 0),
]

# ==========================================================================
# 2. Team advanced statistics, 30 rows, read 2026-11-15T11:35Z.
#    (abbr, gp, w, l, min, off_rtg, def_rtg, net_rtg, pace, team_url)
# ==========================================================================
RATINGS = [
    ("LAL", 13, 11, 2, 624.0, 121.6, 113.6, 8.0, 100.50, "https://www.nba.com/stats/team/1610612747/traditional"),
    ("SAS", 13, 11, 2, 629.0, 119.6, 106.6, 13.0, 98.94, "https://www.nba.com/stats/team/1610612759/traditional"),
    ("BOS", 12, 10, 2, 581.0, 117.4, 105.6, 11.7, 96.62, "https://www.nba.com/stats/team/1610612738/traditional"),
    ("HOU", 13, 10, 3, 624.0, 119.3, 110.2, 9.1, 97.42, "https://www.nba.com/stats/team/1610612745/traditional"),
    ("PHI", 13, 10, 3, 624.0, 111.0, 109.5, 1.5, 100.04, "https://www.nba.com/stats/team/1610612755/traditional"),
    ("MEM", 13, 9, 4, 629.0, 119.0, 110.4, 8.5, 100.46, "https://www.nba.com/stats/team/1610612763/traditional"),
    ("MIN", 13, 9, 4, 629.0, 116.0, 104.5, 11.5, 101.27, "https://www.nba.com/stats/team/1610612750/traditional"),
    ("POR", 12, 9, 3, 576.0, 118.8, 111.1, 7.7, 100.67, "https://www.nba.com/stats/team/1610612757/traditional"),
    ("DET", 12, 8, 4, 586.0, 114.1, 109.2, 4.9, 99.48, "https://www.nba.com/stats/team/1610612765/traditional"),
    ("GSW", 13, 8, 5, 629.0, 116.1, 112.0, 4.1, 99.66, "https://www.nba.com/stats/team/1610612744/traditional"),
    ("OKC", 13, 8, 5, 624.0, 112.7, 109.0, 3.7, 98.58, "https://www.nba.com/stats/team/1610612760/traditional"),
    ("ATL", 13, 7, 6, 629.0, 113.3, 111.9, 1.4, 103.55, "https://www.nba.com/stats/team/1610612737/traditional"),
    ("CLE", 14, 7, 7, 677.0, 116.9, 115.4, 1.6, 99.72, "https://www.nba.com/stats/team/1610612739/traditional"),
    ("DAL", 13, 7, 6, 624.0, 112.8, 112.8, 0.0, 100.54, "https://www.nba.com/stats/team/1610612742/traditional"),
    ("DEN", 11, 7, 4, 533.0, 116.0, 114.7, 1.3, 97.67, "https://www.nba.com/stats/team/1610612743/traditional"),
    ("MIA", 13, 7, 6, 629.0, 114.7, 116.2, -1.5, 102.49, "https://www.nba.com/stats/team/1610612748/traditional"),
    ("NYK", 12, 6, 6, 576.0, 114.5, 108.6, 5.9, 95.63, "https://www.nba.com/stats/team/1610612752/traditional"),
    ("IND", 13, 5, 8, 624.0, 110.1, 111.7, -1.5, 101.15, "https://www.nba.com/stats/team/1610612754/traditional"),
    ("ORL", 12, 5, 7, 581.0, 109.7, 113.4, -3.7, 98.23, "https://www.nba.com/stats/team/1610612753/traditional"),
    ("PHX", 11, 5, 6, 528.0, 113.8, 117.6, -3.8, 98.45, "https://www.nba.com/stats/team/1610612756/traditional"),
    ("TOR", 12, 5, 7, 576.0, 114.5, 112.8, 1.7, 99.88, "https://www.nba.com/stats/team/1610612761/traditional"),
    ("CHA", 12, 4, 8, 576.0, 101.9, 113.1, -11.2, 96.83, "https://www.nba.com/stats/team/1610612766/traditional"),
    ("NOP", 14, 4, 10, 687.0, 111.3, 120.0, -8.6, 101.83, "https://www.nba.com/stats/team/1610612740/traditional"),
    ("WAS", 13, 4, 9, 634.0, 108.7, 114.3, -5.5, 99.63, "https://www.nba.com/stats/team/1610612764/traditional"),
    ("BKN", 12, 3, 9, 581.0, 109.8, 116.0, -6.2, 99.47, "https://www.nba.com/stats/team/1610612751/traditional"),
    ("CHI", 12, 3, 9, 581.0, 109.4, 120.3, -10.9, 103.81, "https://www.nba.com/stats/team/1610612741/traditional"),
    ("LAC", 11, 3, 8, 533.0, 110.7, 115.8, -5.1, 100.55, "https://www.nba.com/stats/team/1610612746/traditional"),
    ("MIL", 13, 1, 12, 624.0, 105.7, 120.0, -14.2, 100.31, "https://www.nba.com/stats/team/1610612749/traditional"),
    ("SAC", 12, 1, 11, 576.0, 107.3, 119.5, -12.2, 101.00, "https://www.nba.com/stats/team/1610612758/traditional"),
    ("UTA", 13, 1, 12, 634.0, 105.0, 116.4, -11.3, 100.50, "https://www.nba.com/stats/team/1610612762/traditional"),
]

# ==========================================================================
# 3. Players traditional, top 31 by MIN (per game), read 2026-11-15T11:40Z.
#    (rank, player, team, age, gp, w, l, min, pts, reb, ast)
#    Only the fields this project uses are carried. Columns printed on the
#    official page and not used here (FG splits, STL, BLK, PF, +/-, etc.) are
#    deliberately not transcribed, to keep every published number checkable.
# ==========================================================================
PLAYERS = [
    (1, "Luka Doncic", "LAL", 27, 11, 9, 2, 35.9, 38.6, 7.5, 7.6),
    (2, "Anthony Edwards", "MIN", 25, 4, 3, 1, 33.7, 33.3, 4.8, 3.5),
    (3, "Shai Gilgeous-Alexander", "OKC", 28, 13, 8, 5, 33.2, 30.5, 4.2, 4.5),
    (4, "Giannis Antetokounmpo", "MIA", 31, 13, 7, 6, 32.4, 28.9, 12.5, 5.2),
    (5, "Victor Wembanyama", "SAS", 22, 13, 11, 2, 29.3, 28.8, 11.7, 3.1),
    (6, "Stephen Curry", "GSW", 38, 10, 7, 3, 26.3, 27.8, 3.7, 3.9),
    (7, "Tyrese Maxey", "PHI", 26, 13, 10, 3, 36.2, 26.7, 3.4, 5.5),
    (8, "Jalen Brunson", "NYK", 30, 12, 6, 6, 33.8, 26.6, 2.9, 5.7),
    (9, "Jayson Tatum", "BOS", 28, 11, 9, 2, 34.0, 26.3, 6.1, 7.5),
    (10, "Jamal Murray", "DEN", 29, 11, 7, 4, 36.5, 25.9, 5.2, 6.2),
    (11, "Cade Cunningham", "DET", 25, 12, 8, 4, 34.7, 25.7, 5.2, 7.9),
    (12, "Anthony Davis", "WAS", 33, 11, 4, 7, 34.1, 25.6, 10.5, 2.0),
    (13, "Devin Booker", "PHX", 30, 11, 5, 6, 34.0, 25.5, 2.5, 5.0),
    (14, "Darius Acuff Jr.", "SAC", 19, 12, 1, 11, 37.2, 25.4, 3.8, 7.2),
    (15, "Ty Jerome", "MEM", 29, 11, 7, 4, 30.5, 25.4, 3.4, 5.3),
    (16, "Austin Reaves", "LAL", 28, 12, 10, 2, 35.3, 24.7, 3.3, 4.7),
    (17, "Paolo Banchero", "ORL", 24, 2, 0, 2, 33.8, 24.5, 6.5, 7.5),
    (18, "Franz Wagner", "ORL", 25, 12, 5, 7, 36.8, 24.4, 6.8, 8.3),
    (19, "Cooper Flagg", "DAL", 19, 12, 7, 5, 33.9, 24.1, 7.0, 6.4),
    (20, "Deni Avdija", "POR", 25, 12, 9, 3, 32.7, 23.9, 6.1, 6.3),
    (21, "Nikola Jokic", "DEN", 31, 11, 7, 4, 36.4, 23.7, 10.5, 9.1),
    (22, "Scottie Barnes", "TOR", 25, 8, 4, 4, 33.3, 23.5, 7.6, 5.1),
    (23, "Alperen Sengun", "HOU", 24, 11, 9, 2, 35.2, 23.1, 9.6, 7.6),
    (24, "Donovan Mitchell", "CLE", 30, 13, 6, 7, 33.0, 23.0, 4.9, 5.6),
    (25, "Kyrie Irving", "DAL", 34, 11, 7, 4, 30.8, 22.7, 3.5, 4.4),
    (26, "Pascal Siakam", "IND", 32, 12, 5, 7, 32.1, 22.4, 6.6, 4.2),
    (27, "Paul George", "BOS", 36, 10, 9, 1, 30.1, 22.0, 5.2, 3.8),
    (28, "Zion Williamson", "NOP", 26, 13, 4, 9, 32.6, 21.9, 5.2, 2.7),
    (29, "Tyrese Haliburton", "IND", 26, 4, 2, 2, 33.0, 21.8, 4.5, 9.5),
    (30, "Tyler Herro", "MIL", 26, 12, 1, 11, 31.3, 21.6, 4.1, 4.3),
    (31, "Michael Porter Jr.", "BKN", 28, 11, 3, 8, 32.7, 21.5, 6.5, 3.0),
]


# ==========================================================================
# parsing
# ==========================================================================
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")


def parse_injury_raw(path=INJURY_RAW):
    """Turn the verbatim transcription into rows, carrying truncated cells.

    Returns ``(rows, carried, unresolved)``.

    THE HARD PART, stated plainly. The PDF is one continuous table ordered by
    game date, then tip time, then matchup, then team (each team's players are
    printed alphabetically). The text extraction drops cells: from the second
    page block onward the ``Game Date`` column is not printed at all, and at a
    few page boundaries the ``Game Time``, ``Matchup`` and ``Team`` cells of the
    first rows of the next page are missing too.

    Row ORDER, however, is preserved. So a row's missing cells are read from
    the most recently printed cells above it in the same report. That is how
    the printed table is meant to be read, and the ordering it produces is
    self-consistent: the team groups come out in the same alphabetical order
    the league prints them in, and the dates only advance at the explicit
    11/16 rows.

    Every row therefore records ``cell_provenance`` per cell: ``row`` when the
    cell was printed on that line, ``carried`` when it was taken from above.
    ``team_provisional`` is True whenever the TEAM cell was carried, so a
    reviewer can find every row whose team attribution does not come from the
    row itself. Those rows are published on the Flagged page (flag F-BB-02) and
    are excluded from the per-team absence sums, which keeps every sum a floor.

    ``unresolved`` lists carried cells with no earlier value to inherit from.
    Those are published blank.
    """
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)

    rows = []
    context = {"game_date": "", "game_time_et": "", "matchup": "", "team_name": ""}
    carried = defaultdict(int)
    unresolved = []

    def cells_of(line):
        s = line.strip()
        if not s.startswith("|"):
            return None
        parts = [c.strip() for c in s.strip("|").split("|")]
        while parts and parts[-1] == "":
            parts.pop()                       # trailing rule artefact
        return parts

    for raw_line in text.splitlines():
        cells = cells_of(raw_line)
        if cells is None or not cells:
            continue
        if set("".join(cells)) <= set("- "):
            continue                                           # separator
        if any("Injury Report" in c for c in cells):
            continue                                           # PDF header
        if any(c in ("Game Date", "Current Status") for c in cells):
            continue                                           # column header

        # --- classify every cell by CONTENT, never by position ------------
        # The printed column layout shifts between page blocks (the Game Date
        # column disappears after block 1, and some page boundaries drop the
        # time/matchup cells too), so position is not a reliable key. Every
        # value that appears in this table has an unambiguous shape:
        #   date 11/15/2026 | time 01:00 (ET) | matchup IND@PHI
        #   team  a name in TEAM_NAME_TO_ABBR   | status one of VALID_STATUS
        #   player "Last, First"  | reason "Injury/Illness - ..." etc.
        found = {"game_date": "", "game_time_et": "", "matchup": "",
                 "team_name": "", "status": "", "player": "", "reason": ""}
        is_nus = False
        leftovers = []
        for c in cells:
            if not c:
                continue
            if c.upper().startswith("NOT YET SUBMITTED"):
                is_nus = True
            elif DATE_RE.match(c) and not found["game_date"]:
                found["game_date"] = c
            elif TIME_RE.match(c) and not found["game_time_et"]:
                found["game_time_et"] = c
            elif re.match(r"^[A-Z]{2,3}@[A-Z]{2,3}$", c) and not found["matchup"]:
                found["matchup"] = c
            elif c in TEAM_NAME_TO_ABBR and not found["team_name"]:
                found["team_name"] = c
            elif c in VALID_STATUS and not found["status"]:
                found["status"] = c
            else:
                leftovers.append(c)
        # Among the leftovers the printed order is player, then reason.
        if leftovers:
            found["player"] = leftovers[0]
            if len(leftovers) > 1:
                found["reason"] = " | ".join(leftovers[1:])

        prov = {}
        for key in ("game_date", "game_time_et", "matchup", "team_name"):
            val = found[key]
            if val:
                context[key] = val
                prov[key] = "row"
            elif context[key]:
                prov[key] = "carried"
                carried[key] += 1
            else:
                prov[key] = "blank"
                unresolved.append({"line": raw_line.strip(), "cell": key,
                                   "player": found["player"]})

        team_abbr = TEAM_NAME_TO_ABBR.get(context["team_name"], "")
        if context["team_name"] and not team_abbr:
            raise SystemExit("unmapped team name in injury report: %r"
                             % context["team_name"])

        rows.append(OrderedDict([
            ("game_date", context["game_date"]),
            ("game_time_et", context["game_time_et"]),
            ("matchup", context["matchup"]),
            ("team_name", context["team_name"]),
            ("team", team_abbr),
            ("player", found["player"]),
            ("status", "" if is_nus else found["status"]),
            ("reason", "" if is_nus else found["reason"]),
            ("is_team_not_submitted", is_nus),
            ("cell_provenance", prov),
            ("team_provisional", prov["team_name"] != "row"),
            ("matchup_provisional", prov["matchup"] != "row"),
            ("source", INJURY_URL),
        ]))
    return rows, dict(carried), unresolved


def cross_check(rows, slate):
    """The checks that make the transcription trustworthy. Raises on failure."""
    report = OrderedDict()
    slate_by_matchup = defaultdict(set)
    slate_tips = {}
    for d, t, a, h, gid, *_ in slate:
        slate_by_matchup["%s@%s" % (a, h)].add(d)
        slate_tips[("%s@%s" % (a, h), d)] = t

    # C1 -- every status is one the league publishes
    bad = [r for r in rows if not r["is_team_not_submitted"]
           and r["status"] not in VALID_STATUS]
    report["C1_statuses_valid"] = {
        "ok": not bad, "checked": len(rows),
        "detail": "every player status is one of " + ", ".join(VALID_STATUS),
        "failures": [(r["player"], r["status"]) for r in bad]}

    # C2 -- every matchup on the report is a real game on the official slate
    unknown = sorted({r["matchup"] for r in rows} - set(slate_by_matchup))
    report["C2_matchups_on_slate"] = {
        "ok": not unknown, "checked": len({r["matchup"] for r in rows}),
        "detail": "every matchup printed by the report appears on the official schedule",
        "failures": unknown}

    # C3 -- every printed tip time equals the slate value (ET both sides)
    time_bad = []
    tip_checked = 0
    for r in rows:
        if r["cell_provenance"]["matchup"] != "row":
            continue
        key = (r["matchup"], r["game_date"])
        printed = r["game_time_et"].replace(" (ET)", "").strip()
        want = slate_tips.get(key)
        if want is None:
            continue
        tip_checked += 1
        # report prints 01:00 -> slate prints 1:00 PM; compare on 12h value
        hh, mm = printed.split(":")
        hh = int(hh)
        suffix = "AM" if hh < 12 else "PM"
        hh12 = hh % 12 or 12
        norm = "%d:%s %s" % (hh12, mm, suffix)
        if norm != want:
            time_bad.append((r["matchup"], r["game_date"], printed, want))
    report["C3_tip_times_match_slate"] = {
        "ok": not time_bad, "checked": tip_checked,
        "detail": "tip time printed on the report equals the official schedule tip (both ET)",
        "failures": time_bad}

    # C4 -- every player row is attributed to a team
    no_team = [r["player"] for r in rows
               if not r["is_team_not_submitted"] and not r["team"]]
    report["C4_player_rows_have_team"] = {
        "ok": not no_team, "checked": len(rows),
        "detail": "every named player resolves to an official team abbreviation",
        "failures": no_team}

    # C5 -- the report's dates are a subset of the window's dates
    dates = sorted({r["game_date"] for r in rows})
    report["C5_report_dates"] = {
        "ok": True, "checked": len(dates),
        "detail": "game dates printed by the 06:15 AM report",
        "value": dates}

    # C6 -- which slate team-sides the report actually covers
    covered = {(r["game_date"], r["matchup"], r["team"]) for r in rows if r["team"]}
    nus = {(r["game_date"], r["matchup"], r["team"]) for r in rows
           if r["is_team_not_submitted"]}
    sides = []
    for d, t, a, h, gid, *_ in slate:
        key = d[5:7] + "/" + d[8:10] + "/" + d[0:4]
        for side, team in (("away", a), ("home", h)):
            state = ("NOT_YET_SUBMITTED" if (key, "%s@%s" % (a, h), team) in nus
                     else "ROWS" if (key, "%s@%s" % (a, h), team) in covered
                     else "NO_ROWS")
            sides.append({"date": d, "game_id": gid, "matchup": "%s@%s" % (a, h),
                          "side": side, "team": team, "report_state": state})
    report["C6_slate_coverage"] = {
        "ok": True, "checked": len(sides),
        "detail": "how each of the window's team-sides is represented in the report",
        "counts": {s: sum(1 for x in sides if x["report_state"] == s)
                   for s in ("ROWS", "NOT_YET_SUBMITTED", "NO_ROWS")},
        "rows": sides}

    fails = [k for k, v in report.items() if not v["ok"]]
    if fails:
        raise SystemExit("official capture cross-check failed: %s" % fails)
    return report, sides


def filed_but_no_rows(sides, slate, rows):
    """A team whose filing deadline has passed but that printed no row at all.

    The report is a live document: a team that has filed but named nobody
    produces no row, and so does a team block that fell off the rendered page.
    The two cannot be told apart from the PDF, so any such side is published as
    UNKNOWN and flagged, never as "nobody is out".
    """
    report_dates = {r["game_date"] for r in rows}
    out = []
    nus = {(r["game_date"], r["matchup"], r["team"]) for r in rows
           if r["is_team_not_submitted"]}
    for s in sides:
        key = s["date"][5:7] + "/" + s["date"][8:10] + "/" + s["date"][0:4]
        if s["report_state"] != "NO_ROWS":
            continue
        if key not in report_dates or key not in {r["game_date"] for r in rows}:
            continue
        if (key, s["matchup"], s["team"]) in nus:
            continue
        # a team is only "expected" to have a row if the other side of its game
        # has one -- i.e. the matchup itself is being reported on.
        other_filed = any(x["matchup"] == s["matchup"] and x["date"] == s["date"]
                          and x["report_state"] == "ROWS" for x in sides)
        out.append({"date": s["date"], "matchup": s["matchup"], "team": s["team"],
                    "other_side_reports_rows": other_filed})
    return out


def main():
    rows, carried, unresolved = parse_injury_raw()
    report, sides = cross_check(rows, SLATE)

    game_dates = sorted({r["game_date"] for r in rows})
    player_rows = [r for r in rows if not r["is_team_not_submitted"]]
    nus_rows = [r for r in rows if r["is_team_not_submitted"]]

    gaps = filed_but_no_rows(sides, SLATE, rows)

    inj = OrderedDict([
        ("source_url", INJURY_URL),
        ("index_url", INDEX_URL),
        ("source_label",
         "NBA official injury report PDF, 11/15/26 06:15 AM ET -- the newest report "
         "listed on the official index at capture time (the index advanced from "
         "6:00 a.m. to 6:15 a.m. ET between this session's two reads of the PDF). "
         "Covers the nine 2026-11-15 games and the eight 2026-11-16 games; it prints "
         "no 11/17 or 11/18 rows at all."),
        ("report_stamp", "2026-11-15 06:15 AM ET"),
        ("retrieved_on", RETRIEVED_ON),
        ("retrieved_stamp", RETRIEVED_STAMP),
        ("retrieval", "fetch_page chunk 0 of 2 and chunk 1 of 2 (PDF text extraction)"),
        ("rule_quote", RULE_QUOTE + " " + RULE_QUOTE_2),
        ("count", len(rows)),
        ("player_rows", len(player_rows)),
        ("not_submitted_rows", len(nus_rows)),
        ("rows_by_game_date", {d: sum(1 for r in rows if r["game_date"] == d)
                               for d in game_dates}),
        ("page_break_carried_cells", carried),
        ("page_break_unresolved_cells", unresolved),
        ("rows", rows),
        ("teams_reporting_no_rows", gaps),
        ("teams_reporting_no_rows_note",
         "A team that filed but named nobody prints no row, and so does a team "
         "whose block fell off the page; the PDF cannot distinguish them. Each "
         "listed side is published UNKNOWN, never as an absence count of zero. "
         "Flag F-BB-02."),
        ("prior_report_url",
         "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"),
        ("prior_report_stamp", "2026-11-14 01:30 PM ET"),
        ("prior_report_note",
         "This is the newest report the previous published dashboard was aware of "
         "(sessions 1823b910 / 965fbd17). The delta against it is published on the "
         "Freshness page; nothing here is back-filled from it."),
        ("cross_checks", report),
    ])
    with open(os.path.join(APP, "official_injuries_2026-11-15_0615AM.json"), "w",
              encoding="utf-8") as fh:
        json.dump(inj, fh, indent=1)
        fh.write("\n")

    # ---- slate -----------------------------------------------------------
    slate_doc = OrderedDict([
        ("source_url", SCHEDULE_URL),
        ("source_label",
         "NBA official schedule page. nba.com/schedule?date=2026-11-15 chunks 0-2 of 9 "
         "and nba.com/schedule?date=2026-11-17 chunk 1, which both render the whole "
         "Week 4 / Week 5 block."),
        ("retrieved_on", RETRIEVED_ON),
        ("retrieved_stamp", RETRIEVED_STAMP),
        ("window", {"from": "2026-11-15", "to": "2026-11-18"}),
        ("count", len(SLATE)),
        ("excluded",
         "The five 2026-11-14 games are Final with printed scores on the page read "
         "for this capture, so they are results (data/app/official_results_2026-11-14.json) "
         "and not part of the upcoming window. The 2026-11-18 heading reads "
         "'12 Games' and all twelve are transcribed."),
        ("repeated_matchups", [{"matchup": m, "dates": d,
                                "note": "re-read on nba.com/schedule?date=2026-11-17 and "
                                        "printed twice with different game ids, so this is "
                                        "the real schedule, not a duplicate row"}
                               for m, d in REPEATED_MATCHUPS]),
        ("games", [OrderedDict([
            ("date", d), ("time_et", t), ("away", a), ("home", h),
            ("game_id", gid), ("venue", v), ("city", c), ("competition", comp),
            ("broadcast", "LEAGUE PASS"),
            ("nba_game_url", "https://www.nba.com/game/%s-vs-%s-%s"
                             % (a.lower(), h.lower(), gid)),
        ]) for (d, t, a, h, gid, v, c, comp) in SLATE]),
    ])
    with open(os.path.join(APP, "official_slate_1115_1118.json"), "w",
              encoding="utf-8") as fh:
        json.dump(slate_doc, fh, indent=1)
        fh.write("\n")

    # ---- results ---------------------------------------------------------
    res = OrderedDict([
        ("source_url", SCOREBOARD_1114),
        ("source_label",
         "NBA official schedule page, 2026-11-14 cards, all five showing 'Final' with "
         "scores (read via nba.com/schedule?date=2026-11-15)."),
        ("retrieved_on", RETRIEVED_ON),
        ("retrieved_stamp", RETRIEVED_STAMP),
        ("count", len(RESULTS_1114)),
        ("games", [OrderedDict([
            ("date", d), ("game_id", gid), ("away", a), ("away_pts", ap),
            ("home", h), ("home_pts", hp), ("ot", ot),
            ("game_url", "https://www.nba.com/game/%s-vs-%s-%s" % (a.lower(), h.lower(), gid)),
            ("source", SCOREBOARD_1114), ("state", "Final"),
        ]) for (d, gid, a, ap, h, hp, ot) in RESULTS_1114]),
    ])
    with open(os.path.join(APP, "official_results_2026-11-14.json"), "w",
              encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
        fh.write("\n")

    # ---- ratings ---------------------------------------------------------
    ratings = OrderedDict([
        ("source_url", TEAM_STATS_URL),
        ("source_label",
         "NBA.com team advanced statistics, 2026-27 regular season, read 2026-11-15 "
         "after the 2026-11-14 slate had completed."),
        ("retrieved_on", RETRIEVED_ON),
        ("retrieved_stamp", "2026-11-15T11:35Z"),
        ("retrieval", "fetch_page chunks 0-1 of 2"),
        ("count", len(RATINGS)),
        ("teams", [OrderedDict([
            ("team", t), ("gp", gp), ("w", w), ("l", l), ("min", mn),
            ("off_rtg", o), ("def_rtg", dr), ("net_rtg", n), ("pace", p),
            ("team_url", u),
        ]) for (t, gp, w, l, mn, o, dr, n, p, u) in RATINGS]),
    ])
    with open(os.path.join(APP, "official_team_ratings_2026-11-15.json"), "w",
              encoding="utf-8") as fh:
        json.dump(ratings, fh, indent=1)
        fh.write("\n")

    # ---- players ---------------------------------------------------------
    cols = ["rank", "player", "team", "age", "gp", "w", "l", "min", "pts", "reb", "ast"]
    with open(os.path.join(APP, "players_top31_2026-11-15.csv"), "w",
              encoding="utf-8", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(cols)
        for row in PLAYERS:
            wr.writerow(row)

    # ---- cross-check the whole capture against the previous one ----------
    prev_log = os.path.join(ROOT, "data", "origin", "games.csv")
    prev_n = None
    if os.path.exists(prev_log):
        with open(prev_log, encoding="utf-8") as fh:
            prev_n = sum(1 for _ in csv.DictReader(fh))
    known = {g[1] for g in RESULTS_1114}
    dupe = sorted(known & {r["game_id"] for r in _read_games(prev_log)}) if prev_log else []

    summary = OrderedDict([
        ("schema", "nba3.official_capture/v1"),
        ("session", "arena/bb0c83a4-nba3"),
        ("written_on", RETRIEVED_ON),
        ("retrieved_stamp", RETRIEVED_STAMP),
        ("source_urls", [INDEX_URL, INJURY_URL, SCHEDULE_URL, TEAM_STATS_URL,
                         PLAYERS_URL, SCOREBOARD_1114]),
        ("injury", {"rows": len(rows), "player_rows": len(player_rows),
                    "not_submitted_rows": len(nus_rows),
                    "rows_by_game_date": inj["rows_by_game_date"],
                    "carried_cells": carried,
                    "unresolved_cells": unresolved,
                    "teams_reporting_no_rows": gaps}),
        ("slate", {"games": len(SLATE),
                   "by_date": {d: sum(1 for g in SLATE if g[0] == d)
                               for d in sorted({g[0] for g in SLATE})}}),
        ("results_1114", {"games": len(RESULTS_1114)}),
        ("ratings", {"teams": len(RATINGS), "gp_sum": sum(r[1] for r in RATINGS),
                     "implied_games": sum(r[1] for r in RATINGS) / 2.0}),
        ("players", {"rows": len(PLAYERS)}),
        ("results_log_before", prev_n),
        ("results_log_expected_after", (prev_n + len(RESULTS_1114)) if prev_n else None),
        ("results_already_in_log", dupe),
        ("cross_checks", report),
    ])
    with open(os.path.join(APP, "official_capture_2026-11-15.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
        fh.write("\n")

    print("injury rows        : %d (%d player, %d not-yet-submitted) across %s"
          % (len(rows), len(player_rows), len(nus_rows), game_dates))
    print("carried cells      : %s" % carried)
    print("unresolved cells   : %d" % len(unresolved))
    print("teams w/ no rows   : %d %s" % (len(gaps), [g["team"] for g in gaps]))
    print("slate games        : %d  %s" % (len(SLATE), summary["slate"]["by_date"]))
    print("results 11/14      : %d" % len(RESULTS_1114))
    print("ratings            : %d teams, sum GP = %d -> %.1f games"
          % (len(RATINGS), summary["ratings"]["gp_sum"],
             summary["ratings"]["implied_games"]))
    print("players            : %d" % len(PLAYERS))
    print("cross-checks       : %s" % {k: v["ok"] for k, v in report.items()})
    print("wrote 6 artefacts to data/app/")


def _read_games(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [{"game_id": r["game_id"]} for r in csv.DictReader(fh)]


if __name__ == "__main__":
    main()
