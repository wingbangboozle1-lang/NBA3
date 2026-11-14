#!/usr/bin/env python3
"""Official-source capture for the 2026-11-14 integration session.

This script holds the *manual transcription* of three official pages read on
2026-11-14 (UTC) with the fetch tool, and writes them to ``data/app/`` as the
canonical, reproducible snapshot used by the site builder:

  1. ``data/app/official_slate.json``
     NBA schedule page (https://www.nba.com/schedule?date=2026-11-14),
     chunks 0-2 of 9 -- every game of the 2026-11-13 .. 2026-11-16 window
     with its official game id, tip time (ET), venue, city and competition
     label as printed on the page.
  2. ``data/app/official_team_ratings_2026-11-14.json``
     NBA team advanced statistics (https://www.nba.com/stats/teams/advanced?
     Season=2026-27&SeasonType=Regular%20Season), chunks 0-1 of 2 -- GP, W,
     L, OffRtg, DefRtg, NetRtg and PACE for all 30 teams.
  3. ``data/app/official_injuries_2026-11-13_0730PM.json``
     NBA official injury report PDF
     https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf
     (the newest report listed on
     https://official.nba.com/nba-injury-report-2026-27-season/), chunks 0-1
     of 2.

Nothing in this file is inferred: every value is copied from the official
page text.  Where the PDF text extraction did not print the matchup/team/time
cell on the row itself, the value is taken from the block header that the same
PDF prints for that game/team and the row is marked ``block_header``; rows
that could not be placed in any printed block stay blank and are flagged.

Usage:  python3 scripts/capture_official_2026_11_14.py
It also prints a verification report comparing the transcription with the
values already stored in the repository by earlier sessions.
"""
import csv
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-14"
TEAM_STATS_URL = ("https://www.nba.com/stats/teams/advanced"
                  "?Season=2026-27&SeasonType=Regular%20Season")
INJURY_URL = ("https://ak-static.cms.nba.com/referee/injury/"
              "Injury-Report_2026-11-13_07_30PM.pdf")
INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
RETRIEVED = "2026-11-14"

# --------------------------------------------------------------------------
# 1. Schedule -- official page, window 2026-11-13 .. 2026-11-16 (31 games)
# --------------------------------------------------------------------------
# (date, time_et, away, home, gid, venue, city, competition, broadcast)
SLATE = [
    ("2026-11-13", "7:00 PM", "NYK", "IND", "0022600034", "Gainbridge Fieldhouse", "Indianapolis, IN", "Emirates NBA Cup - East Group B", "Prime Video"),
    ("2026-11-13", "7:00 PM", "MIL", "ORL", "0022600035", "Kia Center", "Orlando, FL", "Emirates NBA Cup - East Group A", ""),
    ("2026-11-13", "8:00 PM", "CLE", "MIA", "0022600036", "Kaseya Center", "Miami, FL", "Emirates NBA Cup - East Group B", ""),
    ("2026-11-13", "8:00 PM", "ATL", "CHI", "0022600037", "United Center", "Chicago, IL", "Emirates NBA Cup - East Group C", ""),
    ("2026-11-13", "8:00 PM", "MEM", "NOP", "0022600038", "Smoothie King Center", "New Orleans, LA", "Emirates NBA Cup - West Group B", ""),
    ("2026-11-13", "8:30 PM", "UTA", "HOU", "0022600039", "Toyota Center", "Houston, TX", "Emirates NBA Cup - West Group A", ""),
    ("2026-11-13", "9:30 PM", "GSW", "SAS", "0022600040", "Frost Bank Center", "San Antonio, TX", "Emirates NBA Cup - West Group C", ""),
    ("2026-11-13", "10:00 PM", "POR", "SAC", "0022600041", "Golden 1 Center", "Sacramento, CA", "Emirates NBA Cup - West Group C", ""),
    ("2026-11-13", "10:30 PM", "OKC", "LAC", "0022600042", "Intuit Dome", "Inglewood, CA", "Emirates NBA Cup - West Group B", ""),
    ("2026-11-14", "7:00 PM", "DEN", "NOP", "0022600231", "Smoothie King Center", "New Orleans, LA", "", ""),
    ("2026-11-14", "7:30 PM", "DAL", "CLE", "0022600232", "Rocket Arena", "Cleveland, OH", "", ""),
    ("2026-11-14", "8:00 PM", "DET", "MIA", "0022600233", "Kaseya Center", "Miami, FL", "", ""),
    ("2026-11-14", "8:00 PM", "BKN", "MEM", "0022600234", "FedExForum", "Memphis, TN", "", ""),
    ("2026-11-14", "8:00 PM", "CHI", "MIN", "0022600235", "Target Center", "Minneapolis, MN", "", ""),
    ("2026-11-15", "1:00 PM", "IND", "PHI", "0022600236", "Xfinity Mobile Arena", "Philadelphia, PA", "", ""),
    ("2026-11-15", "4:00 PM", "LAL", "PHX", "0022600237", "Mortgage Matchup Center", "Phoenix, AZ", "", ""),
    ("2026-11-15", "4:30 PM", "CHA", "LAC", "0022600238", "Intuit Dome", "Inglewood, CA", "", ""),
    ("2026-11-15", "5:00 PM", "SAS", "UTA", "0022600239", "Delta Center", "Salt Lake City, UT", "", ""),
    ("2026-11-15", "6:00 PM", "DAL", "BOS", "0022600240", "TD Garden", "Boston, MA", "", ""),
    ("2026-11-15", "6:00 PM", "NYK", "TOR", "0022600241", "Scotiabank Arena", "Toronto, ON", "", ""),
    ("2026-11-15", "7:00 PM", "HOU", "WAS", "0022600242", "Capital One Arena", "Washington, DC", "", ""),
    ("2026-11-15", "8:00 PM", "ATL", "MIL", "0022600243", "Fiserv Forum", "Milwaukee, WI", "", ""),
    ("2026-11-15", "9:00 PM", "OKC", "SAC", "0022600244", "Golden 1 Center", "Sacramento, CA", "", ""),
    ("2026-11-16", "7:00 PM", "ORL", "BOS", "0022600245", "TD Garden", "Boston, MA", "", "Peacock / NBC Sports Network"),
    ("2026-11-16", "7:00 PM", "CHI", "CLE", "0022600246", "Rocket Arena", "Cleveland, OH", "", ""),
    ("2026-11-16", "7:00 PM", "MEM", "WAS", "0022600247", "Capital One Arena", "Washington, DC", "", ""),
    ("2026-11-16", "7:30 PM", "PHI", "BKN", "0022600248", "Barclays Center", "Brooklyn, NY", "", ""),
    ("2026-11-16", "7:30 PM", "HOU", "MIA", "0022600249", "Kaseya Center", "Miami, FL", "", ""),
    ("2026-11-16", "8:00 PM", "POR", "MIN", "0022600250", "Target Center", "Minneapolis, MN", "", ""),
    ("2026-11-16", "8:00 PM", "GSW", "NOP", "0022600251", "Smoothie King Center", "New Orleans, LA", "", ""),
    ("2026-11-16", "9:00 PM", "PHX", "DEN", "0022600252", "Ball Arena", "Denver, CO", "", ""),
]

TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

# --------------------------------------------------------------------------
# 2. Team advanced statistics -- official page, 30 teams
# --------------------------------------------------------------------------
# (team, GP, W, L, MIN, OffRtg, DefRtg, NetRtg, PACE)
TEAM_RATINGS = [
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
# 3. Injury report -- official PDF 2026-11-13 07:30 PM ET
# --------------------------------------------------------------------------
# Each block: (date, time, matchup, team, rows, cell)
#   rows: list of (player, status, reason)
#   cell: "printed"  -> the row itself carried the matchup/team cells
#         "header"   -> the values come from the block header printed in the PDF
#         "not_submitted" -> team row "NOT YET SUBMITTED"
INJ = [
    ("2026-11-13", "07:00 (ET)", "MIL@ORL", "Orlando Magic", [
        ("Banchero, Paolo", "Out", "Injury/Illness - Right High AnkleSprain"),
        ("Cain, Jamal", "Available", "Injury/Illness - Left ShoulderContusion"),
        ("da Silva, Tristan", "Available", "Injury/Illness - Left Calf Strain"),
        ("Isaac, Jonathan", "Out", "Injury/Illness - Left Knee InjuryManagement"),
        ("Nelson, Izaiyah", "Out", "Injury/Illness - Left Ankle InjuryRecovery"),
        ("Penda, Noah", "Out", "Injury/Illness - Right Partially Torn Hamstring"),
        ("Suggs, Jalen", "Available", "Injury/Illness - Right Knee Contusion/Bone Bruise"),
    ], "printed"),
    ("2026-11-13", "07:00 (ET)", "NYK@IND", "Indiana Pacers", [
        ("Furphy, Johnny", "Out", "Injury/Illness - Right ACL Repair/Surgery"),
        ("Haliburton, Tyrese", "Out", "Injury/Illness - Left Hamstring Strain"),
        ("McConnell, T.J.", "Available", "Injury/Illness - Right Hamstring Strain"),
        ("Nesmith, Aaron", "Available", "Injury/Illness - Right Knee Soreness"),
        ("Sheppard, Ben", "Out", "Injury/Illness - Left Meniscus Surgery"),
    ], "printed"),
    ("2026-11-13", "08:00 (ET)", "ATL@CHI", "Atlanta Hawks", [
        ("Dennis, RayJ", "Available", "G League - Two-Way"),
        ("Flemings, Kingston", "Available", "Injury/Illness - Lumbar Spasm"),
        ("Gilbert, Keshon", "Out", "Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure"),
        ("Gueye, Mouhamed", "Out", "Injury/Illness - Left Foot Fracture"),
        ("Landale, Jock", "Available", "Injury/Illness - Face Mask"),
        ("Newell, Asa", "Out", "Injury/Illness - Left Great Toe Hyperextension"),
        ("Veesaar, Henri", "Out", "Injury/Illness - Right ACL Tear"),
        ("Wilson, Jalen", "Out", "G League - Two-Way"),
    ], "printed"),
    ("2026-11-13", "08:00 (ET)", "ATL@CHI", "Chicago Bulls", [
        ("Awaka, Tobe", "Out", "Injury/Illness - Disc Irritation"),
        ("Powell, Norman", "Available", "-"),
        ("Sellers, Jaylin", "Out", "G League - Two-Way"),
        ("Swain, Dailyn", "Out", "Injury/Illness - Right Disc Irritation"),
        ("Wilson, Caleb", "Out", "Injury/Illness - Right Metacarpal Fracture"),
    ], "header"),
    ("2026-11-13", "08:00 (ET)", "CLE@MIA", "Cleveland Cavaliers", [
        ("Diop, Khalifa", "Out", "G League - On Assignment"),
        ("Merrill, Sam", "Out", "Injury/Illness - Right Elbow Injury Management"),
        ("Mobley, Evan", "Out", "Injury/Illness - Left Great Toe - Sprain"),
        ("Tomlin, Nae'Qwan", "Out", "Injury/Illness - Low Back Stress Reaction"),
        ("Udeh, Jr., Ernest", "Out", "G League - Two-Way"),
    ], "printed"),
    ("2026-11-13", "08:00 (ET)", "CLE@MIA", "Miami Heat", [
        ("Antetokounmpo, Giannis", "Available", "Injury/Illness - Right Wrist Sprain"),
        ("Goldin, Vladislav", "Out", "G League - Two-Way"),
        ("Larsson, Pelle", "Out", "Injury/Illness - Illness"),
        ("Thompson, Klay", "Out", "Injury/Illness - Left Ankle Soreness"),
    ], "header"),
    ("2026-11-13", "08:00 (ET)", "MEM@NOP", "Memphis Grizzlies", [
        ("Edey, Zach", "Out", "Injury/Illness - Left Ankle Injury Management"),
        ("Lopez, Karim", "Out", "G League - On Assignment"),
        ("Mashack, Jahmai", "Out", "G League - Two-Way"),
        ("Pippen Jr., Scotty", "Out", "Injury/Illness - Lumbar Disc Herniation"),
        ("Post, Quinten", "Out", "Injury/Illness - Concussion Protocol"),
        ("Saunders, Richie", "Out", "Injury/Illness - Right Knee Surgery"),
    ], "printed"),
    ("2026-11-13", "08:00 (ET)", "MEM@NOP", "New Orleans Pelicans", [
        ("Dia, Malik", "Available", "G League - Two-Way"),
        ("Mathurin, Bennedict", "Available", "Injury/Illness - Right Thumb Sprain"),
        ("McGowens, Bryce", "Out", "Injury/Illness - Left Elbow Infection"),
        ("Missi, Yves", "Out", "Injury/Illness - Left Knee Contusion / Bone Bruise"),
        ("Murphy III, Trey", "Out", "Injury/Illness - Bilateral Patellar Tendinopathy"),
        ("Murray, Dejounte", "Out", "Injury/Illness - Left Ankle Sprain"),
        ("Pierre Jr., Jaron", "Available", "G League - Two-Way"),
        ("Watford, Trendon", "Out", "Injury/Illness - Right Ankle Sprain"),
    ], "printed"),
    ("2026-11-13", "08:30 (ET)", "UTA@HOU", "Utah Jazz", [
        ("Alexander, Trey", "Out", "G League - Two-Way"),
        ("Bufkin, Kobe", "Out", "G League - Two-Way"),
        ("Ingram, Harrison", "Out", "G League - Two-Way"),
        ("Jackson Jr., Jaren", "Out", "Injury/Illness - Right MCL Tear"),
        ("Markkanen, Lauri", "Out", "Injury/Illness - Right Hand Fracture"),
        ("Nurkic, Jusuf", "Out", "Injury/Illness - Right 2nd Plantar Plate Tear"),
    ], "printed"),
    ("2026-11-13", "08:30 (ET)", "UTA@HOU", "Houston Rockets", [
        ("Adams, Steven", "Out", "Injury/Illness - Right Soleus Strain"),
        ("Capela, Clint", "Out", "Injury/Illness - Right Ankle Sprain"),
        ("Copeland, Quadir", "Out", "G League - Two-Way"),
        ("Phillips, Julian", "Out", "Injury/Illness - Right Ankle Sprain"),
        ("Smart, Marcus", "Out", "League Suspension"),
    ], "header"),
    ("2026-11-13", "09:30 (ET)", "GSW@SAS", "Golden State Warriors", [
        ("Bassey, Charles", "Probable", "Injury/Illness - Left Toe Soreness"),
        ("Butler III, Jimmy", "Out", "Injury/Illness - Right ACL Repair / Surgery"),
        ("Curry, Stephen", "Out", "Injury/Illness - Right Oblique Tear"),
        ("Moody, Moses", "Out", "Injury/Illness - Left Patellar Tendon Repair / Surgery"),
        ("Porzingis, Kristaps", "Out", "Not With Team"),
        ("Williams, Brandon", "Out", "Injury/Illness - Left Hamstring Strain"),
    ], "printed"),
    ("2026-11-13", "09:30 (ET)", "GSW@SAS", "San Antonio Spurs", [
        ("Fox, De'Aaron", "Questionable", "Injury/Illness - Left Hip Soreness"),
        ("Harris, Tobias", "Out", "Injury/Illness - Left Calf Strain"),
        ("Quaintance, Jayden", "Out", "Injury/Illness - Right Knee Surgery"),
        ("Vassell, Devin", "Questionable", "Injury/Illness - Left Adductor Tightness"),
    ], "header"),
    ("2026-11-13", "10:00 (ET)", "POR@SAC", "Portland Trail Blazers", [
        ("Krejci, Vit", "Out", "Injury/Illness - Left Ankle Fracture"),
        ("Morant, Ja", "Out", "Injury/Illness - Left Hamstring Strain"),
        ("Sharpe, Shaedon", "Out", "Injury/Illness - Right Meniscus Surgery"),
        ("Youngblood, Chris", "Out", "Injury/Illness - Right Bone Bruise"),
    ], "printed"),
    ("2026-11-13", "10:00 (ET)", "POR@SAC", "Sacramento Kings", [
        ("Achiuwa, Precious", "Out", "Injury/Illness - Left Ankle Soreness"),
        ("Karaban, Alex", "Out", "G League - On Assignment"),
        ("Mogbo, Jonathan", "Out", "G League - Two-Way"),
        ("Pedulla, Sean", "Out", "G League - Two-Way"),
        ("Raynaud, Maxime", "Out", "Injury/Illness - Right Patella Sprain/Subluxation"),
        ("Simmons, Ben", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
    ], "header"),
    ("2026-11-13", "10:30 (ET)", "OKC@LAC", "Oklahoma City Thunder", [
        ("Holmgren, Chet", "Out", "Injury/Illness - Right Knee/ Injury Recovery"),
        ("Mitchell, Ajay", "Questionable", "Injury/Illness - Left Ankle Sprain"),
        ("Sorber, Thomas", "Out", "Injury/Illness - Right Knee Surgery"),
        ("Topic, Nikola", "Available", "-"),
        ("Wallace, Cason", "Out", "Injury/Illness - Right Shoulder Surgery"),
        ("Williams, Jalen", "Out", "Injury/Illness - Left Ankle Surgery"),
        ("Williams, Jaylin", "Out", "Injury/Illness - Low Back Spasms"),
    ], "printed"),
    ("2026-11-13", "10:30 (ET)", "OKC@LAC", "LA Clippers", [
        ("Beal, Bradley", "Out", "Injury/Illness - Right Knee Injury Management"),
        ("Ingram, Brandon", "Out", "Injury/Illness - Right Heel Surgery"),
        ("Martinelli, Nick", "Out", "G League - Two-Way"),
        ("Miller, Jordan", "Out", "Injury/Illness - Left Rotator Cuff Surgery"),
        ("Niederhauser, Yanic Konan", "Out", "Injury/Illness - Right Lisfranc Surgery"),
    ], "header"),
    ("2026-11-14", "07:00 (ET)", "DEN@NOP", "Denver Nuggets", [
        ("Holmes II, DaRon", "Out", "G League - On Assignment"),
        ("Nembhard, Ryan", "Out", "G League - Two-Way"),
        ("Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain"),
        ("Whitmore, Cam", "Out", "G League - Two-Way"),
    ], "printed"),
    ("2026-11-14", "07:00 (ET)", "DEN@NOP", "New Orleans Pelicans", [], "not_submitted"),
    ("2026-11-14", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", [
        ("Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis"),
        ("Christie, Max", "Questionable", "Injury/Illness - Left Ankle Sprain"),
        ("de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain"),
        ("Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion"),
        ("Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery"),
        ("Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint"),
    ], "printed"),
    ("2026-11-14", "07:30 (ET)", "DAL@CLE", "Cleveland Cavaliers", [], "not_submitted"),
    ("2026-11-14", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", [
        ("Bilodeau, Tyler", "Out", "G League - Two-Way"),
        ("Brown Jr., Mikel", "Questionable", "Injury/Illness - Illness"),
        ("Jefferson, Joshua", "Out", "G League - On Assignment"),
        ("Nelson, Grant", "Out", "G League - Two-Way"),
        ("Saraf, Ben", "Out", "G League - On Assignment"),
        ("Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness"),
    ], "printed"),
    ("2026-11-14", "08:00 (ET)", "BKN@MEM", "Memphis Grizzlies", [], "not_submitted"),
    ("2026-11-14", "08:00 (ET)", "CHI@MIN", "Chicago Bulls", [], "not_submitted"),
    ("2026-11-14", "08:00 (ET)", "CHI@MIN", "Minnesota Timberwolves", [
        ("Beringer, Joan", "Available", "Injury/Illness - Face Mask"),
        ("DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
        ("Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy"),
    ], "header"),
    ("2026-11-14", "08:00 (ET)", "DET@MIA", "Detroit Pistons", [
        ("Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain"),
        ("Harkless, Elijah", "Questionable", "G League - Two-Way"),
        ("Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion"),
        ("Jones, Isaac", "Questionable", "G League - Two-Way"),
        ("Lanier, Chaz", "Out", "G League - On Assignment"),
        ("Okorie, Ebuka", "Out", "G League - On Assignment"),
        ("Onyenso, Ugonna", "Out", "G League - Two-Way"),
    ], "printed"),
    ("2026-11-14", "08:00 (ET)", "DET@MIA", "Miami Heat", [], "not_submitted"),
]


def write_json(name, payload):
    path = os.path.join(APP, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {os.path.relpath(path, ROOT)}")


def build_slate():
    games = []
    for (date, tip, away, home, gid, venue, city, comp, tv) in SLATE:
        games.append({
            "date": date,
            "time_et": tip,
            "away": away,
            "home": home,
            "away_name": TEAM_NAMES[away],
            "home_name": TEAM_NAMES[home],
            "game_id": gid,
            "nba_game_url": f"https://www.nba.com/game/{away.lower()}-vs-{home.lower()}-{gid}",
            "venue": venue,
            "city": city,
            "competition": comp,
            "broadcast": tv,
            "source_url": SCHEDULE_URL,
            "source_label": "NBA schedule page (official)",
            "verified_on": RETRIEVED,
            "verification": "Official — read from nba.com/schedule on 2026-11-14",
        })
    return {
        "window": {"from": "2026-11-13", "to": "2026-11-16"},
        "source_url": SCHEDULE_URL,
        "source_label": "NBA.com Schedule",
        "retrieved_on": RETRIEVED,
        "retrieval": "fetch_page chunks 0-2 of 9",
        "count": len(games),
        "games": games,
    }


TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764,
}


def build_ratings():
    rows = []
    for (t, gp, w, l, mn, off, df, net, pace) in TEAM_RATINGS:
        rows.append({
            "team": t, "name": TEAM_NAMES[t], "gp": gp, "w": w, "l": l, "min": mn,
            "off_rtg": off, "def_rtg": df, "net_rtg": net, "pace": pace,
            "source_url": TEAM_STATS_URL,
            "team_url": "https://www.nba.com/stats/team/%d/traditional" % TEAM_IDS[t],
            "verified_on": RETRIEVED,
            "verification": "Official — read from nba.com/stats/teams/advanced on 2026-11-14",
        })
    return {
        "source_url": TEAM_STATS_URL,
        "source_label": "NBA Stats — Teams Advanced (Regular Season 2026-27)",
        "retrieved_on": RETRIEVED,
        "retrieval": "fetch_page chunks 0-1 of 2",
        "count": len(rows),
        "teams": rows,
    }


PRIOR_INJURY_URL = ("https://ak-static.cms.nba.com/referee/injury/"
                     "Injury-Report_2026-11-13_05_15PM.pdf")


def corroborate_reasons(rows):
    """Use the earlier official 07/13 5:15 PM snapshot only to fix PDF
    extraction spacing artifacts (e.g. 'AnkleSprain' -> 'Ankle Sprain').

    Statuses are never taken from the earlier snapshot -- they changed between
    the two official reports and only the 7:30 PM value is published here.
    A reason that differs from the earlier snapshot by more than whitespace is
    left as extracted and flagged.
    """
    path = os.path.join(ROOT, "data", "origin", "injuries.csv")
    if not os.path.exists(path):
        return {"corroborated": 0, "text_differs": []}
    repo = list(csv.DictReader(open(path, encoding="utf-8")))
    repo_map = {}
    for r in repo:
        repo_map[(r["game_date"], r["matchup"], r["player"].split(", ")[-1])] = r
    out = {"corroborated": 0, "text_differs": []}
    for row in rows:
        if row["row_type"] != "player":
            continue
        key = (row["game_date"], row["matchup"], " ".join(reversed(row["player"].split(", "))).lower())
        r = repo_map.get(key)
        if not r:
            continue
        a = " ".join(str(row["reason"]).split())
        b = " ".join(str(r["reason"]).split())
        if a == b and row["reason"] != r["reason"]:
            row["reason"] = r["reason"]
            row["reason_corroboration"] = PRIOR_INJURY_URL
            out["corroborated"] += 1
        elif a != b:
            out["text_differs"].append({
                "player": row["player"], "matchup": row["matchup"],
                "new_7_30pm": row["reason"], "prior_5_15pm": r["reason"],
            })
    return out


def build_injuries():
    rows = []
    n = 0
    for (date, time, matchup, team, players, cell) in INJ:
        if cell == "not_submitted":
            n += 1
            rows.append({
                "id": f"INJ-{n:03d}", "game_date": date, "game_time_et": time,
                "matchup": matchup, "team": team, "player": None, "status": None,
                "reason": "NOT YET SUBMITTED", "row_type": "team_report_status",
                "attribution": "printed", "flag": "NF-11",
            })
            continue
        for (player, status, reason) in players:
            n += 1
            rows.append({
                "id": f"INJ-{n:03d}", "game_date": date, "game_time_et": time,
                "matchup": matchup, "team": team, "player": player, "status": status,
                "reason": reason, "row_type": "player",
                "attribution": "printed" if cell == "printed" else "block_header",
                "flag": "",
            })
    corr = corroborate_reasons(rows)
    return {
        "report_stamp": "11/13/26 07:30 PM ET",
        "source_url": INJURY_URL,
        "source_label": "NBA official injury report PDF (11/13/26 07:30 PM ET)",
        "index_url": INJURY_INDEX_URL,
        "prior_snapshot_url": PRIOR_INJURY_URL,
        "retrieved_on": RETRIEVED,
        "retrieval": "fetch_page chunks 0-1 of 2 (PDF text extraction)",
        "corroboration": corr,
        "count": len(rows),
        "rows": rows,
    }


# ---------------------------------------------------------------- verification
def verify_slate_against_repo(slate):
    """Compare today's official read with the slate stored by earlier sessions."""
    path = os.path.join(ROOT, "data", "slates.csv")
    report = {"checked": 0, "mismatches": [], "missing_in_repo": []}
    if not os.path.exists(path):
        return report
    repo = list(csv.DictReader(open(path, encoding="utf-8")))
    by_id = {r["game_id"]: r for r in repo}
    for g in slate["games"]:
        report["checked"] += 1
        r = by_id.get(g["game_id"])
        if not r:
            report["missing_in_repo"].append(g["game_id"])
            continue
        if r["slate_date"] != g["date"] or r["tip_time_et"] != g["time_et"] \
                or r["away_abbr"] != g["away"] or r["home_abbr"] != g["home"]:
            report["mismatches"].append({
                "game_id": g["game_id"],
                "repo": [r["slate_date"], r["tip_time_et"], r["away_abbr"], r["home_abbr"]],
                "official": [g["date"], g["time_et"], g["away"], g["home"]],
            })
    return report


def verify_ratings_against_repo(ratings):
    path = os.path.join(ROOT, "data", "origin", "teams_advanced.csv")
    report = {"checked": 0, "mismatches": [], "fields": ["gp", "w", "l", "off_rtg", "def_rtg", "net_rtg", "pace"]}
    if not os.path.exists(path):
        return report
    repo = {r["team"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
    for t in ratings["teams"]:
        r = repo.get(t["team"])
        if not r:
            report["mismatches"].append({"team": t["team"], "reason": "not in repo file"})
            continue
        for f in report["fields"]:
            report["checked"] += 1
            a, b = t[f], float(r[f])
            if isinstance(a, float):
                if abs(a - b) > 0.005:
                    report["mismatches"].append({"team": t["team"], "field": f, "official": a, "repo": b})
            elif a != int(b):
                report["mismatches"].append({"team": t["team"], "field": f, "official": a, "repo": int(b)})
    return report


def verify_injuries_against_repo(inj):
    """Diff today's newest report against the 11/13 5:15 PM snapshot in the repo."""
    path = os.path.join(ROOT, "data", "origin", "injuries.csv")
    report = {"repo_rows": 0, "new_rows": 0, "status_changed": [], "only_in_repo": [], "only_in_new": []}
    if not os.path.exists(path):
        return report
    repo = list(csv.DictReader(open(path, encoding="utf-8")))
    report["repo_rows"] = len(repo)
    repo_map = {}
    for r in repo:
        key = (r["game_date"], r["matchup"], " ".join(reversed(r["player"].split(", "))).lower())
        repo_map[key] = r
    new_map = {}
    for r in inj["rows"]:
        if r["row_type"] != "player":
            continue
        key = (r["game_date"], r["matchup"], " ".join(reversed(r["player"].split(", "))).lower())
        new_map[key] = r
        if key in repo_map and repo_map[key]["status"] != r["status"]:
            report["status_changed"].append({
                "player": r["player"], "matchup": r["matchup"],
                "repo_status": repo_map[key]["status"], "new_status": r["status"],
            })
    report["new_rows"] = len(new_map)
    for k, r in repo_map.items():
        if k not in new_map:
            report["only_in_repo"].append(f"{k[1]} {k[2]} ({r['status']})")
    for k, r in new_map.items():
        if k not in repo_map:
            report["only_in_new"].append(f"{k[1]} {k[2]} ({r['status']})")
    return report


def main():
    os.makedirs(APP, exist_ok=True)
    slate = build_slate()
    ratings = build_ratings()
    inj = build_injuries()
    write_json("official_slate.json", slate)
    write_json("official_team_ratings_2026-11-14.json", ratings)
    write_json("official_injuries_2026-11-13_0730PM.json", inj)

    print("\n--- verification report (2026-11-14) ---")
    s = verify_slate_against_repo(slate)
    print(f"slate: {s['checked']} games compared with data/slates.csv; "
          f"{len(s['mismatches'])} mismatches; {len(s['missing_in_repo'])} missing")
    for m in s["mismatches"]:
        print("  MISMATCH", m)
    r = verify_ratings_against_repo(ratings)
    print(f"ratings: {r['checked']} field comparisons with data/origin/teams_advanced.csv; "
          f"{len(r['mismatches'])} mismatches")
    for m in r["mismatches"]:
        print("  MISMATCH", m)
    i = verify_injuries_against_repo(inj)
    print(f"injuries: {i['new_rows']} player rows in the 07:30 PM report vs "
          f"{i['repo_rows']} rows in the 11/13 5:15 PM snapshot; "
          f"{len(i['status_changed'])} status changes")
    for m in i["status_changed"]:
        print("  STATUS CHANGE", m)
    print(f"  only in 5:15 PM snapshot: {len(i['only_in_repo'])}")
    print(f"  only in 7:30 PM report:    {len(i['only_in_new'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
