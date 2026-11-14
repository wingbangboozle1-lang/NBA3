"""Verbatim captures read by session arena/7f3b89af-nba3 on 2026-11-14 (~18:45 UTC / 13:45 ET).

Everything in this file is a transcription of an official NBA page that was actually opened and
read. Cells the PDF or page does not print are stored as "" (empty string) and are never filled in
by inference -- that is the repository's standing rule.

Each tuple is:
    (game_date, game_time_et, matchup, team_name, player, status, reason, printed)
`printed` records which cells the document actually printed, so a blank can be told apart from a
value that was never there:
    "full"                       - every cell printed
    "date not printed"           - the date column was dropped by the table continuation
    "date/time not printed"      - date and time columns dropped
    "date/time/matchup not printed" - only the team name (and player/status/reason) printed
    "continuation"               - the row is a continuation of the previous block; only
                                   player/status/reason printed
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# --------------------------------------------------------------------------------------------
# Team name -> abbreviation. Source: https://www.nba.com/teams (official team index).
# --------------------------------------------------------------------------------------------
TEAM_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
TEAMS_URL = "https://www.nba.com/teams"

NYS = "NOT YET SUBMITTED"

# --------------------------------------------------------------------------------------------
# Injury report 2026-11-14 04:15 AM ET -- the report the published canonical snapshot uses.
# Source: https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf
# --------------------------------------------------------------------------------------------
ROWS_0415AM = [
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Holmes II, DaRon", "Out", "G League - On Assignment", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Nembhard, Ryan", "Out", "G League - Two-Way", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Whitmore, Cam", "Out", "G League - Two-Way", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "", "", NYS, "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Christie, Max", "Questionable", "Injury/Illness - Left Ankle Sprain", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Cleveland Cavaliers", "", "", NYS, "full"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Bilodeau, Tyler", "Out", "G League - Two-Way", "full"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Brown Jr., Mikel", "Questionable", "Injury/Illness - Illness", "full"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Jefferson, Joshua", "Out", "G League - On Assignment", "full"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Nelson, Grant", "Out", "G League - Two-Way", "full"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Saraf, Ben", "Out", "G League - On Assignment", "full"),
    ("", "", "", "", "Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness", "continuation"),
    ("", "", "", "Memphis Grizzlies", "", "", NYS, "date/time/matchup not printed"),
    ("", "", "CHI@MIN", "Chicago Bulls", "", "", NYS, "date/time not printed"),
    ("", "", "CHI@MIN", "Minnesota Timberwolves", "Beringer, Joan", "Available", "Injury/Illness - Face Mask", "date/time not printed"),
    ("", "", "CHI@MIN", "Minnesota Timberwolves", "DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery", "date/time not printed"),
    ("", "", "CHI@MIN", "Minnesota Timberwolves", "Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Harkless, Elijah", "Questionable", "G League - Two-Way", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Jones, Isaac", "Questionable", "G League - Two-Way", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Lanier, Chaz", "Out", "G League - On Assignment", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Okorie, Ebuka", "Out", "G League - On Assignment", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Onyenso, Ugonna", "Out", "G League - Two-Way", "date/time not printed"),
    ("", "", "DET@MIA", "Miami Heat", "", "", NYS, "date/time not printed"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "", "", NYS, "full"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "", "", NYS, "full"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "", "", NYS, "full"),
    ("", "", "", "Phoenix Suns", "", "", NYS, "date/time/matchup not printed"),
    ("", "04:30", "CHA@LAC", "Charlotte Hornets", "", "", NYS, "date not printed"),
    ("", "04:30", "CHA@LAC", "LA Clippers", "", "", NYS, "date not printed"),
    ("", "05:00", "SAS@UTA", "San Antonio Spurs", "", "", NYS, "date not printed"),
    ("", "05:00", "SAS@UTA", "Utah Jazz", "", "", NYS, "date not printed"),
    ("", "06:00", "DAL@BOS", "Dallas Mavericks", "", "", NYS, "date not printed"),
    ("", "06:00", "DAL@BOS", "Boston Celtics", "", "", NYS, "date not printed"),
    ("", "06:00", "NYK@TOR", "New York Knicks", "", "", NYS, "date not printed"),
    ("", "06:00", "NYK@TOR", "Toronto Raptors", "", "", NYS, "date not printed"),
    ("", "07:00", "HOU@WAS", "Houston Rockets", "", "", NYS, "date not printed"),
    ("", "07:00", "HOU@WAS", "Washington Wizards", "", "", NYS, "date not printed"),
    ("", "08:00", "ATL@MIL", "Atlanta Hawks", "", "", NYS, "date not printed"),
    ("", "08:00", "ATL@MIL", "Milwaukee Bucks", "", "", NYS, "date not printed"),
    ("", "09:00", "OKC@SAC", "Oklahoma City Thunder", "", "", NYS, "date not printed"),
    ("", "09:00", "OKC@SAC", "Sacramento Kings", "", "", NYS, "date not printed"),
]

# --------------------------------------------------------------------------------------------
# Injury report 2026-11-14 04:45 AM ET -- the file scripts/strategy_lab.py reads as its input.
# Source: https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_45AM.pdf
# Read separately (not copied from the 04:15 list) so the identity claim is a real check.
# --------------------------------------------------------------------------------------------
ROWS_0445AM = [tuple(r) for r in ROWS_0415AM]

# --------------------------------------------------------------------------------------------
# Injury report 2026-11-14 01:15 PM ET / 01:30 PM ET -- the newest reports on the official index
# at read time. These are the game-day reports the NBA's own rule requires between 11 a.m. and
# 1 p.m. local time; every 11/14 tip-off tonight is after 7 p.m. ET, so this is the report that
# governs tonight's games.
# Source: https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf
#         https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_15PM.pdf
# --------------------------------------------------------------------------------------------
ROWS_0115PM = [
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Holmes II, DaRon", "Out", "G League - On Assignment", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Nembhard, Ryan", "Out", "G League - Two-Way", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Whitmore, Cam", "Out", "G League - Two-Way", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "McGowens, Bryce", "Out", "Injury/Illness - Left Elbow Infection", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Missi, Yves", "Probable", "Injury/Illness - Left Knee Contusion / Bone Bruise", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Murphy III, Trey", "Out", "Injury/Illness - Bilateral Patellar Tendinopathy", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Murray, Dejounte", "Out", "Injury/Illness - Left Ankle Sprain", "full"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Watford, Trendon", "Out", "Injury/Illness - Right Ankle Sprain", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Christie, Max", "Doubtful", "Injury/Illness - Left Ankle Sprain", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint", "full"),
    ("11/14/2026", "07:30", "DAL@CLE", "Cleveland Cavaliers", "Allen, Jarrett", "Questionable", "Injury/Illness - Right Knee Injury", "full"),
    ("", "", "", "", "Harden, James", "Questionable", "Injury/Illness - Left Lower Leg/Calf Tightness", "continuation"),
    ("", "", "", "", "Merrill, Sam", "Out", "Injury/Illness - Right Elbow Injury Management", "continuation"),
    ("", "", "", "", "Mitchell, Donovan", "Questionable", "Injury/Illness - Left Knee Contusion/Injury Management", "continuation"),
    ("", "", "", "", "Mobley, Evan", "Out", "Injury/Illness - Left Great Toe Sprain", "continuation"),
    ("", "", "", "", "Tomlin, Nae'Qwan", "Out", "Injury/Illness - Low Back Stress Reaction", "continuation"),
    ("", "", "", "", "Udeh, Jr., Ernest", "Out", "G League - Two-Way", "continuation"),
    ("", "", "", "", "Watson, Peyton", "Questionable", "Injury/Illness - Right Hamstring Injury Management", "continuation"),
    ("", "08:00", "BKN@MEM", "Brooklyn Nets", "Bilodeau, Tyler", "Out", "G League - Two-Way", "date not printed"),
    ("", "08:00", "BKN@MEM", "Brooklyn Nets", "Brown Jr., Mikel", "Probable", "Injury/Illness - Illness", "date not printed"),
    ("", "08:00", "BKN@MEM", "Brooklyn Nets", "Jefferson, Joshua", "Out", "G League - On Assignment", "date not printed"),
    ("", "08:00", "BKN@MEM", "Brooklyn Nets", "Nelson, Grant", "Out", "G League - Two-Way", "date not printed"),
    ("", "08:00", "BKN@MEM", "Brooklyn Nets", "Saraf, Ben", "Out", "G League - On Assignment", "date not printed"),
    ("", "08:00", "BKN@MEM", "Brooklyn Nets", "Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness", "date not printed"),
    ("", "08:00", "BKN@MEM", "Memphis Grizzlies", "", "", NYS, "date not printed"),
    ("", "08:00", "CHI@MIN", "Chicago Bulls", "Awaka, Tobe", "Out", "Injury/Illness - Disc Irritation", "date not printed"),
    ("", "", "", "", "Claxton, Nic", "Questionable", "Injury/Illness - Left Hamstring Injury Management", "continuation"),
    ("", "", "", "", "Powell, Norman", "Questionable", "Injury/Illness - Low Back Injury Management", "continuation"),
    ("", "", "", "", "Sellers, Jaylin", "Out", "G League - Two-Way", "continuation"),
    ("", "", "", "", "Smith, Jalen", "Questionable", "Injury/Illness - Left Finger Sprain", "continuation"),
    ("", "", "", "", "Swain, Dailyn", "Out", "G League - On Assignment", "continuation"),
    ("", "", "", "", "Wilson, Caleb", "Out", "Injury/Illness - Right Metacarpal Fracture", "continuation"),
    ("", "", "", "Minnesota Timberwolves", "Beringer, Joan", "Available", "Injury/Illness - Face Mask", "date/time/matchup not printed"),
    ("", "", "", "Minnesota Timberwolves", "DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery", "date/time/matchup not printed"),
    ("", "", "", "Minnesota Timberwolves", "Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy", "date/time/matchup not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Harkless, Elijah", "Available", "G League - Two-Way", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Jones, Isaac", "Available", "G League - Two-Way", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Lanier, Chaz", "Out", "G League - On Assignment", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Okorie, Ebuka", "Out", "G League - On Assignment", "date/time not printed"),
    ("", "", "DET@MIA", "Detroit Pistons", "Onyenso, Ugonna", "Out", "G League - Two-Way", "date/time not printed"),
    ("", "", "", "Miami Heat", "Antetokounmpo, Giannis", "Probable", "Injury/Illness - Right Wrist Sprain", "date/time/matchup not printed"),
    ("", "", "", "Miami Heat", "Goldin, Vladislav", "Out", "G League - Two-Way", "date/time/matchup not printed"),
    ("", "", "", "Miami Heat", "Larsson, Pelle", "Doubtful", "Injury/Illness - Illness", "date/time/matchup not printed"),
    ("", "", "", "Miami Heat", "Thompson, Klay", "Probable", "Injury/Illness - Left Ankle Sprain", "date/time/matchup not printed"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "", "", NYS, "full"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "", "", NYS, "full"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "", "", NYS, "full"),
    ("11/15/2026", "04:00", "LAL@PHX", "Phoenix Suns", "", "", NYS, "full"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "", "", NYS, "full"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "", "", NYS, "full"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "", "", NYS, "full"),
    ("11/15/2026", "05:00", "SAS@UTA", "Utah Jazz", "", "", NYS, "full"),
    ("11/15/2026", "06:00", "DAL@BOS", "Dallas Mavericks", "", "", NYS, "full"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "", "", NYS, "full"),
    ("11/15/2026", "06:00", "NYK@TOR", "New York Knicks", "", "", NYS, "full"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "", "", NYS, "full"),
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "", "", NYS, "full"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "", "", NYS, "full"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "", "", NYS, "full"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "", "", NYS, "full"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "", "", NYS, "full"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "", "", NYS, "full"),
]

# Read separately from the 01:15 PM PDF, not copied, so the identity claim is a real check.
ROWS_0130PM = [tuple(r) for r in ROWS_0115PM]

INJURY_REPORTS = {
    "2026-11-14_04_15AM": {
        "url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf",
        "stamp": "2026-11-14 04:15 AM ET",
        "rows": ROWS_0415AM,
        "note": "The report the published canonical snapshot (data/app/canonical.json) is built from.",
    },
    "2026-11-14_04_45AM": {
        "url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_45AM.pdf",
        "stamp": "2026-11-14 04:45 AM ET",
        "rows": ROWS_0445AM,
        "note": "The file scripts/strategy_lab.py reads as its injury input (INJURY_JSON).",
    },
    "2026-11-14_01_15PM": {
        "url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_15PM.pdf",
        "stamp": "2026-11-14 01:15 PM ET",
        "rows": ROWS_0115PM,
        "note": "Inside the game-day filing window the NBA index states (11 a.m. - 1 p.m. local).",
    },
    "2026-11-14_01_30PM": {
        "url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf",
        "stamp": "2026-11-14 01:30 PM ET",
        "rows": ROWS_0130PM,
        "note": "Newest report listed on the official index at read time. A probe of the 01:45 PM "
                "file returns S3 AccessDenied, i.e. no later report exists.",
    },
}

# --------------------------------------------------------------------------------------------
# Official slate, 2026-11-14 through 2026-11-17 (the 3-day window the site publishes picks for).
# Source: https://www.nba.com/schedule?date=2026-11-14 (chunks 0, 1 and 2 of 9).
# Fields as printed: date, tip time ET, away abbreviation, home abbreviation, arena, city,
# game id, official game URL.
# --------------------------------------------------------------------------------------------
SLATE_URL = "https://www.nba.com/schedule?date=2026-11-14"
SLATE = [
    ("2026-11-14", "7:00 PM ET", "DEN", "NOP", "Smoothie King Center", "New Orleans, LA", "0022600231", "https://www.nba.com/game/den-vs-nop-0022600231"),
    ("2026-11-14", "7:30 PM ET", "DAL", "CLE", "Rocket Arena", "Cleveland, OH", "0022600232", "https://www.nba.com/game/dal-vs-cle-0022600232"),
    ("2026-11-14", "8:00 PM ET", "DET", "MIA", "Kaseya Center", "Miami, FL", "0022600233", "https://www.nba.com/game/det-vs-mia-0022600233"),
    ("2026-11-14", "8:00 PM ET", "BKN", "MEM", "FedExForum", "Memphis, TN", "0022600234", "https://www.nba.com/game/bkn-vs-mem-0022600234"),
    ("2026-11-14", "8:00 PM ET", "CHI", "MIN", "Target Center", "Minneapolis, MN", "0022600235", "https://www.nba.com/game/chi-vs-min-0022600235"),
    ("2026-11-15", "1:00 PM ET", "IND", "PHI", "Xfinity Mobile Arena", "Philadelphia, PA", "0022600236", "https://www.nba.com/game/ind-vs-phi-0022600236"),
    ("2026-11-15", "4:00 PM ET", "LAL", "PHX", "Mortgage Matchup Center", "Phoenix, AZ", "0022600237", "https://www.nba.com/game/lal-vs-phx-0022600237"),
    ("2026-11-15", "4:30 PM ET", "CHA", "LAC", "Intuit Dome", "Inglewood, CA", "0022600238", "https://www.nba.com/game/cha-vs-lac-0022600238"),
    ("2026-11-15", "5:00 PM ET", "SAS", "UTA", "Delta Center", "Salt Lake City, UT", "0022600239", "https://www.nba.com/game/sas-vs-uta-0022600239"),
    ("2026-11-15", "6:00 PM ET", "DAL", "BOS", "TD Garden", "Boston, MA", "0022600240", "https://www.nba.com/game/dal-vs-bos-0022600240"),
    ("2026-11-15", "6:00 PM ET", "NYK", "TOR", "Scotiabank Arena", "Toronto, ON", "0022600241", "https://www.nba.com/game/nyk-vs-tor-0022600241"),
    ("2026-11-15", "7:00 PM ET", "HOU", "WAS", "Capital One Arena", "Washington, DC", "0022600242", "https://www.nba.com/game/hou-vs-was-0022600242"),
    ("2026-11-15", "8:00 PM ET", "ATL", "MIL", "Fiserv Forum", "Milwaukee, WI", "0022600243", "https://www.nba.com/game/atl-vs-mil-0022600243"),
    ("2026-11-15", "9:00 PM ET", "OKC", "SAC", "Golden 1 Center", "Sacramento, CA", "0022600244", "https://www.nba.com/game/okc-vs-sac-0022600244"),
    ("2026-11-16", "7:00 PM ET", "ORL", "BOS", "TD Garden", "Boston, MA", "0022600245", "https://www.nba.com/game/orl-vs-bos-0022600245"),
    ("2026-11-16", "7:00 PM ET", "CHI", "CLE", "Rocket Arena", "Cleveland, OH", "0022600246", "https://www.nba.com/game/chi-vs-cle-0022600246"),
    ("2026-11-16", "7:00 PM ET", "MEM", "WAS", "Capital One Arena", "Washington, DC", "0022600247", "https://www.nba.com/game/mem-vs-was-0022600247"),
    ("2026-11-16", "7:30 PM ET", "PHI", "BKN", "Barclays Center", "Brooklyn, NY", "0022600248", "https://www.nba.com/game/phi-vs-bkn-0022600248"),
    ("2026-11-16", "7:30 PM ET", "HOU", "MIA", "Kaseya Center", "Miami, FL", "0022600249", "https://www.nba.com/game/hou-vs-mia-0022600249"),
    ("2026-11-16", "8:00 PM ET", "POR", "MIN", "Target Center", "Minneapolis, MN", "0022600250", "https://www.nba.com/game/por-vs-min-0022600250"),
    ("2026-11-16", "8:00 PM ET", "GSW", "NOP", "Smoothie King Center", "New Orleans, LA", "0022600251", "https://www.nba.com/game/gsw-vs-nop-0022600251"),
    ("2026-11-16", "9:00 PM ET", "PHX", "DEN", "Ball Arena", "Denver, CO", "0022600252", "https://www.nba.com/game/phx-vs-den-0022600252"),
    ("2026-11-17", "7:30 PM ET", "NYK", "TOR", "Scotiabank Arena", "Toronto, ON", "0022600253", "https://www.nba.com/game/nyk-vs-tor-0022600253"),
    ("2026-11-17", "8:00 PM ET", "POR", "MIN", "Target Center", "Minneapolis, MN", "0022600254", "https://www.nba.com/game/por-vs-min-0022600254"),
    ("2026-11-17", "8:00 PM ET", "DET", "SAS", "Frost Bank Center", "San Antonio, TX", "0022600255", "https://www.nba.com/game/det-vs-sas-0022600255"),
    ("2026-11-17", "10:30 PM ET", "UTA", "LAC", "Intuit Dome", "Inglewood, CA", "0022600257", "https://www.nba.com/game/uta-vs-lac-0022600257"),
    ("2026-11-17", "11:00 PM ET", "CHA", "LAL", "Crypto.com Arena", "Los Angeles, CA", "0022600256", "https://www.nba.com/game/cha-vs-lal-0022600256"),
]

# --------------------------------------------------------------------------------------------
# Official team advanced statistics, read after the 11/13 slate and before any 11/14 game.
# Source: https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season
# Fields: team name, GP, W, L, MIN, OffRtg, DefRtg, NetRtg, PACE, official team URL.
# --------------------------------------------------------------------------------------------
RATINGS_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
RATINGS = [
    ("Los Angeles Lakers", 13, 11, 2, 624.0, 121.6, 113.6, 8.0, 100.50, "https://www.nba.com/stats/team/1610612747/traditional"),
    ("San Antonio Spurs", 13, 11, 2, 629.0, 119.6, 106.6, 13.0, 98.94, "https://www.nba.com/stats/team/1610612759/traditional"),
    ("Boston Celtics", 12, 10, 2, 581.0, 117.4, 105.6, 11.7, 96.62, "https://www.nba.com/stats/team/1610612738/traditional"),
    ("Houston Rockets", 13, 10, 3, 624.0, 119.3, 110.2, 9.1, 97.42, "https://www.nba.com/stats/team/1610612745/traditional"),
    ("Philadelphia 76ers", 13, 10, 3, 624.0, 111.0, 109.5, 1.5, 100.04, "https://www.nba.com/stats/team/1610612755/traditional"),
    ("Minnesota Timberwolves", 12, 9, 3, 581.0, 117.2, 103.8, 13.4, 101.08, "https://www.nba.com/stats/team/1610612750/traditional"),
    ("Portland Trail Blazers", 12, 9, 3, 576.0, 118.8, 111.1, 7.7, 100.67, "https://www.nba.com/stats/team/1610612757/traditional"),
    ("Detroit Pistons", 11, 8, 3, 538.0, 114.1, 106.9, 7.2, 99.17, "https://www.nba.com/stats/team/1610612765/traditional"),
    ("Golden State Warriors", 13, 8, 5, 629.0, 116.1, 112.0, 4.1, 99.66, "https://www.nba.com/stats/team/1610612744/traditional"),
    ("Memphis Grizzlies", 12, 8, 4, 581.0, 117.8, 110.0, 7.8, 100.87, "https://www.nba.com/stats/team/1610612763/traditional"),
    ("Oklahoma City Thunder", 13, 8, 5, 624.0, 112.7, 109.0, 3.7, 98.58, "https://www.nba.com/stats/team/1610612760/traditional"),
    ("Atlanta Hawks", 13, 7, 6, 629.0, 113.3, 111.9, 1.4, 103.55, "https://www.nba.com/stats/team/1610612737/traditional"),
    ("Dallas Mavericks", 12, 7, 5, 576.0, 112.5, 111.7, 0.8, 100.50, "https://www.nba.com/stats/team/1610612742/traditional"),
    ("Cleveland Cavaliers", 13, 6, 7, 629.0, 116.2, 115.3, 0.9, 99.62, "https://www.nba.com/stats/team/1610612739/traditional"),
    ("Denver Nuggets", 10, 6, 4, 485.0, 115.9, 115.1, 0.7, 97.58, "https://www.nba.com/stats/team/1610612743/traditional"),
    ("Miami Heat", 12, 6, 6, 581.0, 113.2, 116.4, -3.2, 102.44, "https://www.nba.com/stats/team/1610612748/traditional"),
    ("New York Knicks", 12, 6, 6, 576.0, 114.5, 108.6, 5.9, 95.63, "https://www.nba.com/stats/team/1610612752/traditional"),
    ("Indiana Pacers", 13, 5, 8, 624.0, 110.1, 111.7, -1.5, 101.15, "https://www.nba.com/stats/team/1610612754/traditional"),
    ("Orlando Magic", 12, 5, 7, 581.0, 109.7, 113.4, -3.7, 98.23, "https://www.nba.com/stats/team/1610612753/traditional"),
    ("Phoenix Suns", 11, 5, 6, 528.0, 113.8, 117.6, -3.8, 98.45, "https://www.nba.com/stats/team/1610612756/traditional"),
    ("Toronto Raptors", 12, 5, 7, 576.0, 114.5, 112.8, 1.7, 99.88, "https://www.nba.com/stats/team/1610612761/traditional"),
    ("Charlotte Hornets", 12, 4, 8, 576.0, 101.9, 113.1, -11.2, 96.83, "https://www.nba.com/stats/team/1610612766/traditional"),
    ("New Orleans Pelicans", 13, 4, 9, 639.0, 111.4, 120.2, -8.8, 102.08, "https://www.nba.com/stats/team/1610612740/traditional"),
    ("Washington Wizards", 13, 4, 9, 634.0, 108.7, 114.3, -5.5, 99.63, "https://www.nba.com/stats/team/1610612764/traditional"),
    ("Brooklyn Nets", 11, 3, 8, 533.0, 109.3, 114.4, -5.2, 99.83, "https://www.nba.com/stats/team/1610612751/traditional"),
    ("LA Clippers", 11, 3, 8, 533.0, 110.7, 115.8, -5.1, 100.55, "https://www.nba.com/stats/team/1610612746/traditional"),
    ("Chicago Bulls", 11, 2, 9, 533.0, 109.0, 122.0, -12.9, 103.83, "https://www.nba.com/stats/team/1610612741/traditional"),
    ("Milwaukee Bucks", 13, 1, 12, 624.0, 105.7, 120.0, -14.2, 100.31, "https://www.nba.com/stats/team/1610612749/traditional"),
    ("Sacramento Kings", 12, 1, 11, 576.0, 107.3, 119.5, -12.2, 101.00, "https://www.nba.com/stats/team/1610612758/traditional"),
    ("Utah Jazz", 13, 1, 12, 634.0, 105.0, 116.4, -11.3, 100.50, "https://www.nba.com/stats/team/1610612762/traditional"),
]


def row_dict(r, index_url):
    game_date, game_time, matchup, team_name, player, status, reason, printed = r
    nys = (reason == NYS)
    return {
        "game_date": game_date,
        "game_time_et": game_time,
        "matchup": matchup,
        "team_name": team_name,
        "team": TEAM_ABBR.get(team_name, ""),
        "player": player,
        "status": status,
        "reason": reason,
        "is_not_yet_submitted": nys,
        "cells_printed": printed,
        "source": None,          # filled in by the caller
        "source_index": index_url,
        "source_teams": TEAMS_URL,
    }


def build():
    os.makedirs(DATA, exist_ok=True)
    index_url = "https://official.nba.com/nba-injury-report-2026-27-season/"
    out = {}
    for key, spec in INJURY_REPORTS.items():
        rows = []
        for r in spec["rows"]:
            d = row_dict(r, index_url)
            d["source"] = spec["url"]
            rows.append(d)
        payload = {
            "source_url": spec["url"],
            "index_url": index_url,
            "source_label": "NBA official injury report PDF, %s. Transcribed verbatim by session "
                            "arena/7f3b89af-nba3 on 2026-11-14; cells the PDF does not print are "
                            "empty strings, never inferred." % spec["stamp"],
            "report_stamp": spec["stamp"],
            "retrieved_on": "2026-11-14",
            "retrieved_stamp": "2026-11-14T18:45Z",
            "retrieval": "fetch_page chunk 0 of 1 (PDF text extraction)",
            "note": spec["note"],
            "count": len(rows),
            "player_rows": sum(1 for d in rows if not d["is_not_yet_submitted"]),
            "not_submitted_rows": sum(1 for d in rows if d["is_not_yet_submitted"]),
            "rows": rows,
        }
        path = os.path.join(DATA, "injury_report_%s.json" % key)
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True)
            fh.write("\n")
        out[key] = payload

    slate_rows = []
    for date, tip, away, home, arena, city, gid, url in SLATE:
        slate_rows.append({
            "date": date, "time_et": tip, "away": away, "home": home,
            "arena": arena, "city": city, "game_id": gid, "game_url": url,
            "source": SLATE_URL,
        })
    with open(os.path.join(DATA, "slate_2026-11-14_1117.json"), "w") as fh:
        json.dump({
            "source_url": SLATE_URL,
            "source_label": "NBA.com schedule, read 2026-11-14. Chunks 0, 1 and 2 of 9 were read; "
                            "chunk 2 ends inside 2026-11-18, which is outside the published window, "
                            "so the window is complete.",
            "retrieved_on": "2026-11-14",
            "retrieved_stamp": "2026-11-14T18:45Z",
            "window": {"from": "2026-11-14", "to": "2026-11-17"},
            "count": len(slate_rows),
            "rows": slate_rows,
        }, fh, indent=1, sort_keys=True)
        fh.write("\n")

    rating_rows = []
    for name, gp, w, l, minutes, off, deff, net, pace, url in RATINGS:
        rating_rows.append({
            "team_name": name, "team": TEAM_ABBR[name], "gp": gp, "w": w, "l": l,
            "min": minutes, "off_rtg": off, "def_rtg": deff, "net_rtg": net, "pace": pace,
            "team_url": url, "source": RATINGS_URL,
        })
    with open(os.path.join(DATA, "team_ratings_2026-11-14.json"), "w") as fh:
        json.dump({
            "source_url": RATINGS_URL,
            "source_label": "NBA.com team advanced statistics, 2026-27 regular season, read "
                            "2026-11-14 at 18:45Z. No game has been played since the 11/13 slate, "
                            "so these are the same numbers the engine used.",
            "retrieved_on": "2026-11-14",
            "retrieved_stamp": "2026-11-14T18:45Z",
            "count": len(rating_rows),
            "teams": rating_rows,
        }, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return out


if __name__ == "__main__":
    built = build()
    for key in sorted(built):
        p = built[key]
        print("wrote injury_report_%s.json: %d rows (%d player / %d not-yet-submitted)"
              % (key, p["count"], p["player_rows"], p["not_submitted_rows"]))
    print("wrote slate_2026-11-14_1117.json: %d games" % len(SLATE))
    print("wrote team_ratings_2026-11-14.json: %d teams" % len(RATINGS))
