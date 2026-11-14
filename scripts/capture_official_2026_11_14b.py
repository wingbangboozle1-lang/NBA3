#!/usr/bin/env python3
"""Official-source capture for session ``arena/8d3d0271-nba3`` (2026-11-14, 01:05Z).

Three official pages were read with the fetch tool on 2026-11-14 (UTC) and are
transcribed here *verbatim*, with no inference and no filling-in:

  1. NBA schedule page -- https://www.nba.com/schedule?date=2026-11-14
     chunks 0, 1 and 2 of 9.  It prints Week 4 (Nov 9-15) and Week 5
     (Nov 16-22).  This session takes every game from 2026-11-14 through
     2026-11-17 inclusive -- today plus the maximum three-day forward window
     the brief asks for -- with its official game id, tip time (ET), venue,
     city and, where the page prints one, the competition label.
     Games on 2026-11-13 are **excluded**: the page showed NYK@IND and
     MIL@ORL as "LIVE 2nd Qtr" when it was read, so they are in progress and
     are not an upcoming slate.

  2. NBA team advanced statistics --
     https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season
     chunks 0 and 1 of 2.  GP, W, L, MIN, OffRtg, DefRtg, NetRtg and PACE
     for all 30 teams.

  3. NBA official injury report PDF --
     https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_45PM.pdf
     chunks 0 and 1 of 2.  This is the newest report listed on
     https://official.nba.com/nba-injury-report-2026-27-season/ at read time;
     no 2026-11-14 report had been published yet.

Rows whose PDF text cell was empty (a team row that prints "NOT YET
SUBMITTED" in the status column) are kept, with an empty player name, because
"a team has not filed" is itself a published official fact and matters for
every downstream number.  Nothing is inferred from them.

Run:  python3 scripts/capture_official_2026_11_14b.py
Writes: data/app/official_slate_1114_1117.json
        data/app/official_team_ratings_2026-11-14b.json
        data/app/official_injuries_2026-11-13_0745PM.json
and prints a cross-check against the values earlier sessions stored.
"""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-14"
TEAM_STATS_URL = ("https://www.nba.com/stats/teams/advanced"
                  "?Season=2026-27&SeasonType=Regular%20Season")
INJURY_URL = ("https://ak-static.cms.nba.com/referee/injury/"
              "Injury-Report_2026-11-13_07_45PM.pdf")
INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
RETRIEVED = "2026-11-14"
RETRIEVED_STAMP = "2026-11-14T01:05Z"

# --------------------------------------------------------------------------
# 1. Schedule -- official page, window 2026-11-14 .. 2026-11-17 (27 games)
#    (date, time_et, away, home, gid, venue, city, competition, broadcast)
# --------------------------------------------------------------------------
SLATE = [
    # Saturday, November 14 -- 5 games (page heading: "Saturday, November 14 / 5 Games")
    ("2026-11-14", "7:00 PM", "DEN", "NOP", "0022600231", "Smoothie King Center", "New Orleans, LA", "", "LEAGUE PASS"),
    ("2026-11-14", "7:30 PM", "DAL", "CLE", "0022600232", "Rocket Arena", "Cleveland, OH", "", "LEAGUE PASS"),
    ("2026-11-14", "8:00 PM", "DET", "MIA", "0022600233", "Kaseya Center", "Miami, FL", "", "NBA TV"),
    ("2026-11-14", "8:00 PM", "BKN", "MEM", "0022600234", "FedExForum", "Memphis, TN", "", "LEAGUE PASS"),
    ("2026-11-14", "8:00 PM", "CHI", "MIN", "0022600235", "Target Center", "Minneapolis, MN", "", "LEAGUE PASS"),
    # Sunday, November 15 -- 9 games
    ("2026-11-15", "1:00 PM", "IND", "PHI", "0022600236", "Xfinity Mobile Arena", "Philadelphia, PA", "", "LEAGUE PASS"),
    ("2026-11-15", "4:00 PM", "LAL", "PHX", "0022600237", "Mortgage Matchup Center", "Phoenix, AZ", "", "LEAGUE PASS"),
    ("2026-11-15", "4:30 PM", "CHA", "LAC", "0022600238", "Intuit Dome", "Inglewood, CA", "", "LEAGUE PASS"),
    ("2026-11-15", "5:00 PM", "SAS", "UTA", "0022600239", "Delta Center", "Salt Lake City, UT", "", "LEAGUE PASS"),
    ("2026-11-15", "6:00 PM", "DAL", "BOS", "0022600240", "TD Garden", "Boston, MA", "", "LEAGUE PASS"),
    ("2026-11-15", "6:00 PM", "NYK", "TOR", "0022600241", "Scotiabank Arena", "Toronto, ON", "", "LEAGUE PASS"),
    ("2026-11-15", "7:00 PM", "HOU", "WAS", "0022600242", "Capital One Arena", "Washington, DC", "", "MNMT/Monumental+"),
    ("2026-11-15", "8:00 PM", "ATL", "MIL", "0022600243", "Fiserv Forum", "Milwaukee, WI", "", "LEAGUE PASS"),
    ("2026-11-15", "9:00 PM", "OKC", "SAC", "0022600244", "Golden 1 Center", "Sacramento, CA", "", "LEAGUE PASS"),
    # Monday, November 16 -- 8 games
    ("2026-11-16", "7:00 PM", "ORL", "BOS", "0022600245", "TD Garden", "Boston, MA", "", "Peacock / NBC Sports Network"),
    ("2026-11-16", "7:00 PM", "CHI", "CLE", "0022600246", "Rocket Arena", "Cleveland, OH", "", "LEAGUE PASS"),
    ("2026-11-16", "7:00 PM", "MEM", "WAS", "0022600247", "Capital One Arena", "Washington, DC", "", "MNMT/Monumental+"),
    ("2026-11-16", "7:30 PM", "PHI", "BKN", "0022600248", "Barclays Center", "Brooklyn, NY", "", "LEAGUE PASS"),
    ("2026-11-16", "7:30 PM", "HOU", "MIA", "0022600249", "Kaseya Center", "Miami, FL", "", "LEAGUE PASS"),
    ("2026-11-16", "8:00 PM", "POR", "MIN", "0022600250", "Target Center", "Minneapolis, MN", "", "LEAGUE PASS"),
    ("2026-11-16", "8:00 PM", "GSW", "NOP", "0022600251", "Smoothie King Center", "New Orleans, LA", "", "LEAGUE PASS"),
    ("2026-11-16", "9:00 PM", "PHX", "DEN", "0022600252", "Ball Arena", "Denver, CO", "", "LEAGUE PASS"),
    # Tuesday, November 17 -- 5 games
    ("2026-11-17", "7:30 PM", "NYK", "TOR", "0022600253", "Scotiabank Arena", "Toronto, ON", "", "LEAGUE PASS"),
    ("2026-11-17", "8:00 PM", "POR", "MIN", "0022600254", "Target Center", "Minneapolis, MN", "", "LEAGUE PASS"),
    ("2026-11-17", "8:00 PM", "DET", "SAS", "0022600255", "Frost Bank Center", "San Antonio, TX", "", "Peacock / NBC"),
    ("2026-11-17", "10:30 PM", "UTA", "LAC", "0022600257", "Intuit Dome", "Inglewood, CA", "", "LEAGUE PASS"),
    ("2026-11-17", "11:00 PM", "CHA", "LAL", "0022600256", "Crypto.com Arena", "Los Angeles, CA", "", "Peacock"),
]

# --------------------------------------------------------------------------
# 2. Team advanced statistics -- official page, all 30 rows
#    (team, gp, w, l, min, off_rtg, def_rtg, net_rtg, pace)
# --------------------------------------------------------------------------
RATINGS = [
    ("LAL", 13, 11, 2, 624.0, 121.6, 113.6, 8.0, 100.50),
    ("BOS", 12, 10, 2, 581.0, 117.4, 105.6, 11.7, 96.62),
    ("PHI", 13, 10, 3, 624.0, 111.0, 109.5, 1.5, 100.04),
    ("SAS", 12, 10, 2, 581.0, 119.3, 108.3, 11.0, 98.97),
    ("HOU", 12, 9, 3, 576.0, 118.5, 109.3, 9.2, 97.42),
    ("MIN", 12, 9, 3, 581.0, 117.2, 103.8, 13.4, 101.08),
    ("DET", 11, 8, 3, 538.0, 114.1, 106.9, 7.2, 99.17),
    ("GSW", 12, 8, 4, 581.0, 118.4, 110.9, 7.5, 99.76),
    ("OKC", 12, 8, 4, 576.0, 112.5, 108.3, 4.2, 98.75),
    ("POR", 11, 8, 3, 528.0, 118.5, 111.4, 7.1, 100.86),
    ("ATL", 12, 7, 5, 576.0, 114.3, 112.2, 2.1, 103.46),
    ("DAL", 12, 7, 5, 576.0, 112.5, 111.7, 0.8, 100.50),
    ("MEM", 11, 7, 4, 533.0, 116.4, 110.6, 5.8, 100.28),
    ("CLE", 12, 6, 6, 581.0, 115.6, 113.6, 2.1, 99.80),
    ("DEN", 10, 6, 4, 485.0, 115.9, 115.1, 0.7, 97.58),
    ("NYK", 11, 6, 5, 528.0, 115.7, 109.0, 6.7, 95.09),
    ("MIA", 11, 5, 6, 533.0, 111.3, 115.9, -4.6, 102.80),
    ("PHX", 11, 5, 6, 528.0, 113.8, 117.6, -3.8, 98.45),
    ("TOR", 12, 5, 7, 576.0, 114.5, 112.8, 1.7, 99.88),
    ("CHA", 12, 4, 8, 576.0, 101.8, 113.0, -11.2, 96.92),
    ("IND", 12, 4, 8, 576.0, 110.6, 112.5, -1.9, 101.13),
    ("NOP", 12, 4, 8, 591.0, 112.1, 119.2, -7.1, 101.64),
    ("ORL", 11, 4, 7, 533.0, 109.7, 114.6, -5.0, 98.25),
    ("WAS", 13, 4, 9, 634.0, 108.7, 114.3, -5.5, 99.63),
    ("BKN", 11, 3, 8, 533.0, 109.3, 114.4, -5.2, 99.83),
    ("LAC", 10, 2, 8, 485.0, 110.0, 115.8, -5.8, 100.95),
    ("CHI", 10, 1, 9, 480.0, 109.2, 124.2, -15.1, 103.75),
    ("MIL", 12, 1, 11, 576.0, 106.2, 120.7, -14.5, 100.50),
    ("SAC", 11, 1, 10, 528.0, 107.2, 119.3, -12.1, 101.23),
    ("UTA", 12, 1, 11, 586.0, 103.8, 115.4, -11.6, 100.75),
]

# --------------------------------------------------------------------------
# 3. Injury report -- official PDF, 11/13/26 07:45 PM ET (newest listed)
#    (game_date, game_time_et, matchup, team, player, status, reason)
# --------------------------------------------------------------------------
INJ = [
    # ---- 11/13/2026 07:00 (ET) MIL@ORL
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "Banchero, Paolo", "Out", "Injury/Illness - Right High Ankle Sprain"),
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "Cain, Jamal", "Available", "Injury/Illness - Left Shoulder Contusion"),
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "da Silva, Tristan", "Available", "Injury/Illness - Left Calf Strain"),
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "Isaac, Jonathan", "Out", "Injury/Illness - Left Knee Injury Management"),
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "Nelson, Izaiyah", "Out", "Injury/Illness - Left Ankle Injury Recovery"),
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "Penda, Noah", "Out", "Injury/Illness - Right Partially Torn Hamstring"),
    ("11/13/2026", "07:00", "MIL@ORL", "Orlando Magic", "Suggs, Jalen", "Available", "Injury/Illness - Right Knee Contusion/Bone Bruise"),
    # ---- 11/13/2026 07:00 (ET) NYK@IND
    ("11/13/2026", "07:00", "NYK@IND", "Indiana Pacers", "Furphy, Johnny", "Out", "Injury/Illness - Right ACL Repair/Surgery"),
    ("11/13/2026", "07:00", "NYK@IND", "Indiana Pacers", "Haliburton, Tyrese", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/13/2026", "07:00", "NYK@IND", "Indiana Pacers", "McConnell, T.J.", "Available", "Injury/Illness - Right Hamstring Strain"),
    ("11/13/2026", "07:00", "NYK@IND", "Indiana Pacers", "Nesmith, Aaron", "Available", "Injury/Illness - Right Knee Soreness"),
    ("11/13/2026", "07:00", "NYK@IND", "Indiana Pacers", "Sheppard, Ben", "Out", "Injury/Illness - Left Meniscus Surgery"),
    # ---- 11/13/2026 08:00 (ET) ATL@CHI
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Dennis, RayJ", "Available", "G League - Two-Way"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Flemings, Kingston", "Available", "Injury/Illness - Lumbar Spasm"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Gilbert, Keshon", "Out", "Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Gueye, Mouhamed", "Out", "Injury/Illness - Left Foot Fracture"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Landale, Jock", "Available", "Injury/Illness - Face Mask"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Newell, Asa", "Out", "Injury/Illness - Left Great Toe Hyperextension"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Veesaar, Henri", "Out", "Injury/Illness - Right ACL Tear"),
    ("11/13/2026", "08:00", "ATL@CHI", "Atlanta Hawks", "Wilson, Jalen", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:00", "ATL@CHI", "Chicago Bulls", "Awaka, Tobe", "Out", "Injury/Illness - Disc Irritation"),
    ("11/13/2026", "08:00", "ATL@CHI", "Chicago Bulls", "Powell, Norman", "Available", "-"),
    ("11/13/2026", "08:00", "ATL@CHI", "Chicago Bulls", "Sellers, Jaylin", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:00", "ATL@CHI", "Chicago Bulls", "Swain, Dailyn", "Out", "Injury/Illness - Right Disc Irritation"),
    ("11/13/2026", "08:00", "ATL@CHI", "Chicago Bulls", "Wilson, Caleb", "Out", "Injury/Illness - Right Metacarpal Fracture"),
    # ---- 11/13/2026 08:00 (ET) CLE@MIA
    ("11/13/2026", "08:00", "CLE@MIA", "Cleveland Cavaliers", "Diop, Khalifa", "Out", "G League - On Assignment"),
    ("11/13/2026", "08:00", "CLE@MIA", "Cleveland Cavaliers", "Merrill, Sam", "Out", "Injury/Illness - Right Elbow Injury Management"),
    ("11/13/2026", "08:00", "CLE@MIA", "Cleveland Cavaliers", "Mobley, Evan", "Out", "Injury/Illness - Left Great Toe - Sprain"),
    ("11/13/2026", "08:00", "CLE@MIA", "Cleveland Cavaliers", "Tomlin, Nae'Qwan", "Out", "Injury/Illness - Low Back Stress Reaction"),
    ("11/13/2026", "08:00", "CLE@MIA", "Cleveland Cavaliers", "Udeh, Jr., Ernest", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:00", "CLE@MIA", "Miami Heat", "Antetokounmpo, Giannis", "Available", "Injury/Illness - Right Wrist Sprain"),
    ("11/13/2026", "08:00", "CLE@MIA", "Miami Heat", "Goldin, Vladislav", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:00", "CLE@MIA", "Miami Heat", "Larsson, Pelle", "Out", "Injury/Illness - Illness"),
    ("11/13/2026", "08:00", "CLE@MIA", "Miami Heat", "Thompson, Klay", "Out", "Injury/Illness - Left Ankle Soreness"),
    # ---- 11/13/2026 08:00 (ET) MEM@NOP
    ("11/13/2026", "08:00", "MEM@NOP", "Memphis Grizzlies", "Edey, Zach", "Out", "Injury/Illness - Left Ankle Injury Management"),
    ("11/13/2026", "08:00", "MEM@NOP", "Memphis Grizzlies", "Lopez, Karim", "Out", "G League - On Assignment"),
    ("11/13/2026", "08:00", "MEM@NOP", "Memphis Grizzlies", "Mashack, Jahmai", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:00", "MEM@NOP", "Memphis Grizzlies", "Pippen Jr., Scotty", "Out", "Injury/Illness - Lumbar Disc Herniation"),
    ("11/13/2026", "08:00", "MEM@NOP", "Memphis Grizzlies", "Post, Quinten", "Out", "Injury/Illness - Concussion Protocol"),
    ("11/13/2026", "08:00", "MEM@NOP", "Memphis Grizzlies", "Saunders, Richie", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Dia, Malik", "Available", "G League - Two-Way"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Mathurin, Bennedict", "Available", "Injury/Illness - Right Thumb Sprain"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "McGowens, Bryce", "Out", "Injury/Illness - Left Elbow Infection"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Missi, Yves", "Out", "Injury/Illness - Left Knee Contusion / Bone Bruise"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Murphy III, Trey", "Out", "Injury/Illness - Bilateral Patellar Tendinopathy"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Murray, Dejounte", "Out", "Injury/Illness - Left Ankle Sprain"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Pierre Jr., Jaron", "Available", "G League - Two-Way"),
    ("11/13/2026", "08:00", "MEM@NOP", "New Orleans Pelicans", "Watford, Trendon", "Out", "Injury/Illness - Right Ankle Sprain"),
    # ---- 11/13/2026 08:30 (ET) UTA@HOU
    ("11/13/2026", "08:30", "UTA@HOU", "Utah Jazz", "Alexander, Trey", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:30", "UTA@HOU", "Utah Jazz", "Bufkin, Kobe", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:30", "UTA@HOU", "Utah Jazz", "Ingram, Harrison", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:30", "UTA@HOU", "Utah Jazz", "Jackson Jr., Jaren", "Out", "Injury/Illness - Right MCL Tear"),
    ("11/13/2026", "08:30", "UTA@HOU", "Utah Jazz", "Markkanen, Lauri", "Out", "Injury/Illness - Right Hand Fracture"),
    ("11/13/2026", "08:30", "UTA@HOU", "Utah Jazz", "Nurkic, Jusuf", "Out", "Injury/Illness - Right 2nd Plantar Plate Tear"),
    ("11/13/2026", "08:30", "UTA@HOU", "Houston Rockets", "Adams, Steven", "Out", "Injury/Illness - Right Soleus Strain"),
    ("11/13/2026", "08:30", "UTA@HOU", "Houston Rockets", "Capela, Clint", "Out", "Injury/Illness - Right Ankle Sprain"),
    ("11/13/2026", "08:30", "UTA@HOU", "Houston Rockets", "Copeland, Quadir", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:30", "UTA@HOU", "Houston Rockets", "Phillips, Julian", "Out", "G League - Two-Way"),
    ("11/13/2026", "08:30", "UTA@HOU", "Houston Rockets", "Smart, Marcus", "Out", "League Suspension"),
    # ---- 11/13/2026 09:30 (ET) GSW@SAS
    ("11/13/2026", "09:30", "GSW@SAS", "Golden State Warriors", "Bassey, Charles", "Probable", "Injury/Illness - Left Toe Soreness"),
    ("11/13/2026", "09:30", "GSW@SAS", "Golden State Warriors", "Butler III, Jimmy", "Out", "Injury/Illness - Right ACL Repair / Surgery"),
    ("11/13/2026", "09:30", "GSW@SAS", "Golden State Warriors", "Curry, Stephen", "Out", "Injury/Illness - Right Oblique Tear"),
    ("11/13/2026", "09:30", "GSW@SAS", "Golden State Warriors", "Moody, Moses", "Out", "Injury/Illness - Left Patellar Tendon Repair / Surgery"),
    ("11/13/2026", "09:30", "GSW@SAS", "Golden State Warriors", "Porzingis, Kristaps", "Out", "Not With Team"),
    ("11/13/2026", "09:30", "GSW@SAS", "Golden State Warriors", "Williams, Brandon", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/13/2026", "09:30", "GSW@SAS", "San Antonio Spurs", "Fox, De'Aaron", "Questionable", "Injury/Illness - Left Hip Soreness"),
    ("11/13/2026", "09:30", "GSW@SAS", "San Antonio Spurs", "Harris, Tobias", "Out", "Injury/Illness - Left Calf Strain"),
    ("11/13/2026", "09:30", "GSW@SAS", "San Antonio Spurs", "Quaintance, Jayden", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/13/2026", "09:30", "GSW@SAS", "San Antonio Spurs", "Vassell, Devin", "Questionable", "Injury/Illness - Left Adductor Tightness"),
    # ---- 11/13/2026 10:00 (ET) POR@SAC
    ("11/13/2026", "10:00", "POR@SAC", "Portland Trail Blazers", "Krejci, Vit", "Out", "Injury/Illness - Left Ankle Fracture"),
    ("11/13/2026", "10:00", "POR@SAC", "Portland Trail Blazers", "Morant, Ja", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/13/2026", "10:00", "POR@SAC", "Portland Trail Blazers", "Sharpe, Shaedon", "Out", "Injury/Illness - Right Meniscus Surgery"),
    ("11/13/2026", "10:00", "POR@SAC", "Portland Trail Blazers", "Youngblood, Chris", "Out", "Injury/Illness - Right Bone Bruise"),
    ("11/13/2026", "10:00", "POR@SAC", "Sacramento Kings", "Achiuwa, Precious", "Out", "Injury/Illness - Left Ankle Soreness"),
    ("11/13/2026", "10:00", "POR@SAC", "Sacramento Kings", "Karaban, Alex", "Out", "G League - On Assignment"),
    ("11/13/2026", "10:00", "POR@SAC", "Sacramento Kings", "Mogbo, Jonathan", "Out", "G League - Two-Way"),
    ("11/13/2026", "10:00", "POR@SAC", "Sacramento Kings", "Pedulla, Sean", "Out", "G League - Two-Way"),
    ("11/13/2026", "10:00", "POR@SAC", "Sacramento Kings", "Raynaud, Maxime", "Out", "Injury/Illness - Right Patella Subluxation"),
    ("11/13/2026", "10:00", "POR@SAC", "Sacramento Kings", "Simmons, Ben", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
    # ---- 11/13/2026 10:30 (ET) OKC@LAC
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Holmgren, Chet", "Out", "Injury/Illness - Right Knee/ Injury Recovery"),
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Mitchell, Ajay", "Questionable", "Injury/Illness - Left Ankle Sprain"),
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Sorber, Thomas", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Topic, Nikola", "Available", "-"),
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Wallace, Cason", "Out", "Injury/Illness - Left Shoulder Surgery"),
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Williams, Jalen", "Out", "Injury/Illness - Left Ankle Surgery"),
    ("11/13/2026", "10:30", "OKC@LAC", "Oklahoma City Thunder", "Williams, Jaylin", "Out", "Injury/Illness - Low Back Spasms"),
    ("11/13/2026", "10:30", "OKC@LAC", "LA Clippers", "Beal, Bradley", "Out", "Injury/Illness - Right Knee Injury Management"),
    ("11/13/2026", "10:30", "OKC@LAC", "LA Clippers", "Ingram, Brandon", "Out", "Injury/Illness - Right Heel Surgery"),
    ("11/13/2026", "10:30", "OKC@LAC", "LA Clippers", "Martinelli, Nick", "Out", "G League - Two-Way"),
    ("11/13/2026", "10:30", "OKC@LAC", "LA Clippers", "Miller, Jordan", "Out", "Injury/Illness - Left Rotator Cuff Surgery"),
    ("11/13/2026", "10:30", "OKC@LAC", "LA Clippers", "Niederhauser, Yanic Konan", "Out", "Injury/Illness - Right Lisfranc Surgery"),
    # ---- 11/14/2026 07:00 (ET) DEN@NOP
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Holmes II, DaRon", "Out", "G League - On Assignment"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Nembhard, Ryan", "Out", "G League - Two-Way"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain"),
    ("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Whitmore, Cam", "Out", "G League - Two-Way"),
    ("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "", "", "NOT YET SUBMITTED"),
    # ---- 11/14/2026 07:30 (ET) DAL@CLE
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Christie, Max", "Questionable", "Injury/Illness - Left Ankle Sprain"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery"),
    ("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint"),
    ("11/14/2026", "07:30", "DAL@CLE", "Cleveland Cavaliers", "", "", "NOT YET SUBMITTED"),
    # ---- 11/14/2026 08:00 (ET) BKN@MEM
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Bilodeau, Tyler", "Out", "G League - Two-Way"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Brown Jr., Mikel", "Questionable", "Injury/Illness - Illness"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Jefferson, Joshua", "Out", "G League - On Assignment"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Nelson, Grant", "Out", "G League - Two-Way"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Saraf, Ben", "Out", "G League - On Assignment"),
    ("11/14/2026", "08:00", "BKN@MEM", "Brooklyn Nets", "Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness"),
    ("11/14/2026", "08:00", "BKN@MEM", "Memphis Grizzlies", "", "", "NOT YET SUBMITTED"),
    # ---- 11/14/2026 08:00 (ET) CHI@MIN
    ("11/14/2026", "08:00", "CHI@MIN", "Chicago Bulls", "", "", "NOT YET SUBMITTED"),
    ("11/14/2026", "08:00", "CHI@MIN", "Minnesota Timberwolves", "Beringer, Joan", "Available", "Injury/Illness - Face Mask"),
    ("11/14/2026", "08:00", "CHI@MIN", "Minnesota Timberwolves", "DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
    ("11/14/2026", "08:00", "CHI@MIN", "Minnesota Timberwolves", "Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy"),
    # ---- 11/14/2026 08:00 (ET) DET@MIA
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain"),
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Harkless, Elijah", "Questionable", "G League - Two-Way"),
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion"),
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Jones, Isaac", "Questionable", "G League - Two-Way"),
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Lanier, Chaz", "Out", "G League - On Assignment"),
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Okorie, Ebuka", "Out", "G League - On Assignment"),
    ("11/14/2026", "08:00", "DET@MIA", "Detroit Pistons", "Onyenso, Ugonna", "Out", "G League - Two-Way"),
    ("11/14/2026", "08:00", "DET@MIA", "Miami Heat", "", "", "NOT YET SUBMITTED"),
]

# Official NBA team name -> official abbreviation, as used by nba.com/schedule.
TEAM_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU",
    "Indiana Pacers": "IND", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

# Official nba.com/stats team id -> used to build the per-team source link.
TEAM_ID = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764,
}


def write_json(name, payload):
    path = os.path.join(APP, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=False)
        fh.write("\n")
    return path


def build_slate():
    games = []
    for date, time_et, away, home, gid, venue, city, comp, tv in SLATE:
        games.append({
            "date": date,
            "time_et": time_et,
            "away": away,
            "home": home,
            "game_id": gid,
            "venue": venue,
            "city": city,
            "competition": comp,
            "broadcast": tv,
            "nba_game_url": ("https://www.nba.com/game/%s-vs-%s-%s"
                             % (away.lower(), home.lower(), gid)),
        })
    return {
        "source_url": SCHEDULE_URL,
        "source_label": "NBA official schedule page (fetched 2026-11-14, chunks 0-2 of 9)",
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "window": {"from": "2026-11-14", "to": "2026-11-17"},
        "count": len(games),
        "excluded": ("2026-11-13 games were LIVE on the page at read time (NYK@IND and "
                     "MIL@ORL showed 'LIVE 2nd Qtr'), so they are not part of the "
                     "upcoming window and are not priced."),
        "games": games,
    }


def build_ratings():
    teams = []
    for tm, gp, w, l, minutes, off, deff, net, pace in RATINGS:
        teams.append({
            "team": tm, "gp": gp, "w": w, "l": l, "min": minutes,
            "off_rtg": off, "def_rtg": deff, "net_rtg": net, "pace": pace,
            "team_url": "https://www.nba.com/stats/team/%d/traditional" % TEAM_ID[tm],
        })
    return {
        "source_url": TEAM_STATS_URL,
        "source_label": "NBA official team advanced statistics, Regular Season 2026-27",
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "count": len(teams),
        "teams": teams,
    }


def build_injuries():
    rows = []
    for date, time_et, matchup, team, player, status, reason in INJ:
        not_submitted = (status or "").strip().upper() == "NOT YET SUBMITTED"
        rows.append({
            "game_date": date,
            "game_time_et": time_et,
            "matchup": matchup,
            "team_name": team,
            "team": TEAM_ABBR.get(team, ""),
            "player": player,
            "status": status,
            "reason": reason,
            "is_team_not_submitted": not_submitted,
            "availability": ("" if not_submitted else status),
            "source": INJURY_URL,
        })
    return {
        "source_url": INJURY_URL,
        "index_url": INJURY_INDEX_URL,
        "source_label": ("NBA official injury report PDF, 11/13/26 07:45 PM ET "
                         "(newest report listed on the official index at read time)"),
        "report_stamp": "2026-11-13 07:45 PM ET",
        "retrieved_on": RETRIEVED,
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunks 0-1 of 2 (PDF text extraction)",
        "count": len(rows),
        "player_rows": sum(1 for r in rows if not r["is_team_not_submitted"]),
        "not_submitted_rows": sum(1 for r in rows if r["is_team_not_submitted"]),
        "rows": rows,
    }


# --------------------------------------------------------------------------
# Cross-checks against what earlier sessions already stored
# --------------------------------------------------------------------------
def check_ratings(ratings):
    path = os.path.join(ROOT, "data", "origin", "teams_advanced.csv")
    if not os.path.exists(path):
        print("  ratings: data/origin/teams_advanced.csv missing; nothing to compare")
        return
    with open(path, encoding="utf-8") as fh:
        stored = {r["team"]: r for r in csv.DictReader(fh)}
    agree = disagree = 0
    diffs = []
    for t in ratings["teams"]:
        s = stored.get(t["team"])
        if not s:
            diffs.append(f"{t['team']}: not present in stored capture")
            continue
        for key, mine in (("gp", t["gp"]), ("w", t["w"]), ("l", t["l"]),
                          ("min", t["min"]), ("off_rtg", t["off_rtg"]),
                          ("def_rtg", t["def_rtg"]), ("net_rtg", t["net_rtg"]),
                          ("pace", t["pace"])):
            theirs = s[key]
            if float(theirs) == float(mine):
                agree += 1
            else:
                disagree += 1
                diffs.append(f"{t['team']}.{key}: page={mine} stored={theirs}")
    print(f"  ratings: {agree} field comparisons agree, {disagree} differ "
          f"(30 teams x 8 fields)")
    for d in diffs:
        print("    DIFF " + d)


def _iso(value):
    """'11/13/2026' -> '2026-11-13' (the shape earlier sessions stored).

    Accepts either shape so the diff works whichever way round the two
    captures are written.
    """
    s = (value or "").strip()
    if "/" in s:
        mm, dd, yy = s.split("/")
        return f"{yy}-{mm}-{dd}"
    return s


def check_injuries(inj):
    path = os.path.join(APP, "official_injuries_2026-11-13_0730PM.json")
    if not os.path.exists(path):
        print("  injuries: no 07:30 PM snapshot to diff against")
        return
    with open(path, encoding="utf-8") as fh:
        prior = json.load(fh)

    def key_of(date, matchup, team, player, status, reason):
        # Earlier captures store a "NOT YET SUBMITTED" team row with an empty
        # player cell and the phrase in the reason column.  Normalise both sides.
        if (status or "").strip().upper() == "NOT YET SUBMITTED" or \
           (reason or "").strip().upper() == "NOT YET SUBMITTED":
            player, status = "", "NOT YET SUBMITTED"
        return (_iso(date), matchup, team, (player or "").strip())

    prev = {}
    for r in prior.get("rows", []):
        k = key_of(r.get("game_date", ""), r.get("matchup", ""), r.get("team", ""),
                   r.get("player"), r.get("status"), r.get("reason"))
        prev[k] = (r.get("status") or "").strip() or "NOT YET SUBMITTED"
    now = {}
    for r in inj["rows"]:
        k = key_of(r["game_date"], r["matchup"], r["team_name"], r["player"],
                   r["status"], r["reason"])
        now[k] = (r["status"] or "").strip() or "NOT YET SUBMITTED"
    changed = [k for k in now if k in prev and prev[k] != now[k]]
    added = [k for k in now if k not in prev]
    removed = [k for k in prev if k not in now]
    print(f"  injuries: {len(now)} rows now, {len(prev)} rows in the 07:30 PM snapshot; "
          f"{len(changed)} status changes, {len(added)} new keys, {len(removed)} missing keys")
    for k in added[:12]:
        print(f"    NEW     {k[2]} / {k[3]} -> {now[k]}")
    for k in removed[:12]:
        print(f"    MISSING {k[2]} / {k[3]} -> was {prev[k]}")
    for k in changed[:12]:
        print(f"    CHANGED {k[2]} / {k[3]}: {prev[k]} -> {now[k]}")


def check_slate(slate):
    path = os.path.join(APP, "official_slate.json")
    if not os.path.exists(path):
        print("  slate: no earlier official_slate.json to compare")
        return
    with open(path, encoding="utf-8") as fh:
        prior = json.load(fh)
    prev = {g["game_id"]: g for g in prior.get("games", [])}
    overlap = [g for g in slate["games"] if g["game_id"] in prev]
    agree = 0
    diffs = []
    for g in overlap:
        p = prev[g["game_id"]]
        for key in ("date", "time_et", "away", "home"):
            if str(p.get(key, "")).strip() == str(g.get(key, "")).strip():
                agree += 1
            else:
                diffs.append(f"{g['game_id']}.{key}: new={g.get(key)} old={p.get(key)}")
    print(f"  slate: {len(slate['games'])} games in the 11/14-11/17 window; "
          f"{len(overlap)} also appear in the earlier 11/13-11/16 capture; "
          f"{agree} field comparisons agree, {len(diffs)} differ")
    for d in diffs:
        print("    DIFF " + d)


def main():
    if not os.path.isdir(APP):
        os.makedirs(APP)
    slate = build_slate()
    ratings = build_ratings()
    inj = build_injuries()

    p1 = write_json("official_slate_1114_1117.json", slate)
    p2 = write_json("official_team_ratings_2026-11-14b.json", ratings)
    p3 = write_json("official_injuries_2026-11-13_0745PM.json", inj)

    print("Wrote:")
    for p in (p1, p2, p3):
        print("  " + os.path.relpath(p, ROOT))
    print()
    print("Cross-checks against earlier stored captures:")
    check_slate(slate)
    check_ratings(ratings)
    check_injuries(inj)


if __name__ == "__main__":
    main()
