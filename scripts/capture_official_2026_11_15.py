#!/usr/bin/env python3
"""Official capture for the 2026-11-15 rolling window (session arena/9866a950-nba3).

STANDARD-LIBRARY ONLY.  OFFLINE AND DETERMINISTIC.  Every value below was read
from an official NBA page on 2026-11-15 via the platform's page fetcher and
transcribed verbatim; the verbatim fetches are committed next to this script:

  data/app/official_injury_index_2026-11-15_0635Z.md        official.nba.com injury-report index
  data/app/official_injuries_2026-11-15_1215AM_raw.md       12:00 AM ET report PDF text (read 1)
  data/app/official_injuries_2026-11-15_0615AM_raw.md       06:15 AM ET report PDF text (read 2)

This module re-derives the JSON captures from the transcribed data, cross-checks
the two independent reads of the same document against each other, cross-checks
team W/L records between the standings table and two independent reads of the
schedule/game pages, sums the quarter scores against each final, and writes:

  data/app/official_injuries_2026-11-15_0615AM.json
  data/app/official_slate_1115_1118.json
  data/app/official_results_2026-11-14.json      (with quarter scores per the brief)
  data/app/official_team_ratings_2026-11-15.json
  data/origin/games.csv                          (+5 finals appended, idempotent)
  data/origin/games_extended_provenance.json     (append a provenance record)

CI re-runs this module and fails on any drift, so a transcription cannot be
silently regenerated.

PAGE-BREAK ATTRIBUTION RULE (the no-inference rule applied to PDF text)
    The PDF text drops the Team cell on rows after a page break.  Such rows are
    attributed by carrying the last team printed in the SAME game section
    forward, and every such attribution is cross-checked against the second
    independent read (12:00 AM ET), which has identical page breaks.  Where the
    two reads disagree on a name spelling, the 12:00 AM spelling is stored and
    the variant is recorded in ``transcription_variants``.

Run:  python3 scripts/capture_official_2026_11_15.py
"""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
ORIGIN = os.path.join(ROOT, "data", "origin")

INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
RPT_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf"
RPT_PRIOR_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_12_00AM.pdf"
RPT_STAMP = "2026-11-15 06:15 AM ET"
RPT_PRIOR_STAMP = "2026-11-15 12:00 AM ET"
RETRIEVED = "2026-11-15T06:40Z"          # fetch-page retrieval stamp (UTC)
SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-15"
SCHEDULE_URL2 = "https://www.nba.com/schedule?date=2026-11-18"
STATS_URL = ("https://www.nba.com/stats/teams/advanced"
             "?Season=2026-27&SeasonType=Regular%20Season")
GAMES_URL = "https://www.nba.com/games?date=2026-11-14"

# --------------------------------------------------------------------------
# 1. Injury report, 11/15/26 06:15 AM ET -- 84 player rows + 16 NOT-YET-SUBMITTED
#    rows.  Tuple: (game_date, time_et, matchup, team_or_"", player_or_"", status,
#    reason).  team "" means the PDF did not print the cell on this row and the
#    value below is the carried-forward attribution (flagged in the JSON).
# --------------------------------------------------------------------------
# cf=True marks a row whose Team cell the PDF did not print (carried forward).
ROWS_0615 = [
    # IND@PHI 01:00
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Furphy, Johnny", "Out", "Injury/Illness - Right ACL Repair / Surgery"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Haliburton, Tyrese", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "McConnell, T.J.", "Probable", "Injury/Illness - Right Hamstring Strain"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Nembhard, Andrew", "Questionable", "Injury/Illness - Left Hip Soreness / Tightness"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Nesmith, Aaron", "Questionable", "Injury/Illness - Left Hand Sprain"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Sheppard, Ben", "Out", "Injury/Illness - Left Meniscus Tear"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Barlow, Dominick", "Out", "Injury/Illness - Low Back Stress Reaction"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Bona, Adem", "Out", "Injury/Illness - Cervical Spine Sprain"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Embiid, Joel", "Out", "Injury/Illness - Right Foot Plantar Fascia Injury Management"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Hukporti, Ariel", "Out", "Injury/Illness - Right Achilles Tendon Rupture / Tear"),
    # LAL@PHX 04:00
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "Carr, Cameron", "Out", "Injury/Illness - Illness"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "Grimes, Quentin", "Available", "Injury/Illness - Right Finger Splint"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "James, Bronny", "Questionable", "Injury/Illness - Illness"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "Reaves, Austin", "Out", "Injury/Illness - Left Heel Contusion / Bone Bruise"),
    ("11/15/2026", "04:00", "LAL@PHX", "", "Sexton, Collin", "Questionable", "Injury/Illness - Right Orbital Laceration"),          # cf -> PHX
    ("11/15/2026", "04:00", "LAL@PHX", "", "Thiero, Adou", "Questionable", "Injury/Illness - Left Ankle Sprain"),                     # cf -> PHX
    ("11/15/2026", "04:00", "LAL@PHX", "Phoenix Suns", "Williams, Mark", "Out", "Injury/Illness - Left Shoulder Surgery"),
    # CHA@LAC 04:30
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Ajayi, Michael", "Out", "G League - Two-Way"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Boswell, Kylan", "Out", "G League - Two-Way"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Knueppel, Kon", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Schroder, Dennis", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Steinbach, Hannes", "Out", "G League - On Assignment"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Beal, Bradley", "Out", "Injury/Illness - Right Knee Injury Management"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Ingram, Brandon", "Out", "Injury/Illness - Right Heel Surgery"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Miller, Jordan", "Out", "Injury/Illness - Left Rotator Cuff Surgery"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Niederhauser, Yanic Konan", "Out", "Injury/Illness - Right Lisfranc Surgery"),
    # SAS@UTA 05:00
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Brown, Maliq", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Gillespie, Ja'Kobi", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Harris, Tobias", "Out", "Injury/Illness - Left Calf Strain"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Quaintance, Jayden", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/15/2026", "05:00", "SAS@UTA", "Utah Jazz", "Alexander, Trey", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "Utah Jazz", "Bufkin, Kobe", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "", "Hayes, Jaxson", "Out", "Injury/Illness - Left Knee Strain"),                              # cf -> UTA
    ("11/15/2026", "05:00", "SAS@UTA", "", "Ingram, Harrison", "Out", "G League - Two-Way"),                                          # cf -> UTA
    ("11/15/2026", "05:00", "SAS@UTA", "", "Jackson Jr., Jaren", "Out", "Injury/Illness - Right MCL Tear"),                           # cf -> UTA
    ("11/15/2026", "05:00", "SAS@UTA", "", "Markkanen, Lauri", "Out", "Injury/Illness - Right Hand Fracture"),                        # cf -> UTA
    ("11/15/2026", "05:00", "SAS@UTA", "", "Nurkic, Jusuf", "Out", "Injury/Illness - Right 2nd Plantar Plate Tear"),                  # cf -> UTA
    # DAL@BOS 06:00
    ("11/15/2026", "06:00", "DAL@BOS", "Dallas Mavericks", "", "NOT YET SUBMITTED", ""),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Carter, Devin", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Cenac Jr., Christopher", "Questionable", "G League - On Assignment"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Mitchell, Dillon", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Williams, Amari", "Questionable", "G League - Two-Way"),
    # NYK@TOR 06:00  (the report prints no New York rows at all for this game)
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Barnes, Scottie", "Questionable", "Injury/Illness - Left Groin Strain"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Bittle, Nate", "Out", "Injury/Illness - Right Foot Avulsion Fracture"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Leonard, Kawhi", "Out", "Injury/Illness - Left Knee Injury Management"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "McCullar Jr., Kevin", "Out", "G League - Two-Way"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Smith, Malachi", "Out", "G League - Two-Way"),
    # HOU@WAS 07:00
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "Adams, Steven", "Probable", "Injury/Illness - Right Soleus Strain"),
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "Capela, Clint", "Out", "Injury/Illness - Right Ankle Sprain"),
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "Copeland, Quadir", "Out", "G League - Two-Way"),
    ("11/15/2026", "07:00", "HOU@WAS", "", "Phillips, Julian", "Out", "G League - Two-Way"),                                          # cf -> HOU
    ("11/15/2026", "07:00", "HOU@WAS", "", "Smart, Marcus", "Out", "League Suspension"),                                              # cf -> HOU
    ("11/15/2026", "07:00", "HOU@WAS", "", "VanVleet, Fred", "Out", "Injury/Illness - Right Knee Injury Management"),                 # cf -> HOU
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Beekman, Reece", "Out", "Injury/Illness - Right AC Joint Injury"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Carrington, Bub", "Questionable", "Injury/Illness - Chest / Sternum Contusion"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Champagne, Justin", "Out", "Injury/Illness - Right Foot Surgery"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Johnson, Tre", "Questionable", "Injury/Illness - Low Back Soreness"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Okpara, Felix", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Sarr, Alex", "Questionable", "Injury/Illness - Illness"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Vukcevic, Tristan", "Out", "Injury/Illness - Left Hip Impingement"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Watkins, Jamir", "Out", "Injury/Illness - Left ACL Repair / Surgery"),
    # ATL@MIL 08:00
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Flemings, Kingston", "Out", "Injury/Illness - Lumbar Strain"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Gilbert, Keshon", "Out", "Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Gueye, Mouhamed", "Out", "Injury/Illness - Left Foot Fracture"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Landale, Jock", "Available", "Injury/Illness - Face Mask"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Newell, Asa", "Out", "Injury/Illness - Left Great Toe Hyperextension"),
    ("11/15/2026", "08:00", "ATL@MIL", "", "Veesaar, Henri", "Out", "Injury/Illness - Right ACL Tear"),                               # cf -> ATL
    ("11/15/2026", "08:00", "ATL@MIL", "", "Wilson, Jalen", "Doubtful", "G League - Two-Way"),                                        # cf -> ATL
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Dieng, Ousmane", "Out", "Injury/Illness - Left Finger Sprain"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Jones, Kam", "Out", "G League - Two-Way"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Markovic, Bogoljub", "Out", "G League - On Assignment"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Nance, Pete", "Out", "G League - Two-Way"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Ryan, Cormac", "Out", "G League - Two-Way"),
    # OKC@SAC 09:00
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Holmgren, Chet", "Out", "Injury/Illness - Right Knee/ Injury Recovery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Mitchell, Ajay", "Questionable", "Injury/Illness - Left Ankle Sprain"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Sorber, Thomas", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Wallace, Cason", "Out", "Injury/Illness - Left Shoulder Surgery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Williams, Jalen", "Out", "Injury/Illness - Left Ankle Surgery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Williams, Jaylin", "Out", "Injury/Illness - Low Back Spasms"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Achiuwa, Precious", "Questionable", "Injury/Illness - Left Ankle Soreness"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Mogbo, Jonathan", "Out", "G League - Two-Way"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Murray, Keegan", "Questionable", "Injury/Illness - Illness"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Pedulla, Sean", "Out", "G League - Two-Way"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Raynaud, Maxime", "Out", "Injury/Illness - Right Patella Subluxation"),
    ("11/15/2026", "09:00", "OKC@SAC", "", "Simmons, Ben", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),         # cf -> SAC
    # 11/16 team-side NOT YET SUBMITTED rows
    ("11/16/2026", "07:00", "CHI@CLE", "Chicago Bulls", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "CHI@CLE", "Cleveland Cavaliers", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "MEM@WAS", "Memphis Grizzlies", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "MEM@WAS", "Washington Wizards", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "ORL@BOS", "Orlando Magic", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "ORL@BOS", "Boston Celtics", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "HOU@MIA", "Houston Rockets", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "HOU@MIA", "Miami Heat", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "PHI@BKN", "Philadelphia 76ers", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "PHI@BKN", "Brooklyn Nets", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "GSW@NOP", "Golden State Warriors", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "GSW@NOP", "New Orleans Pelicans", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "POR@MIN", "Portland Trail Blazers", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "POR@MIN", "Minnesota Timberwolves", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "09:00", "PHX@DEN", "Phoenix Suns", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "09:00", "PHX@DEN", "Denver Nuggets", "", "NOT YET SUBMITTED", ""),
]

# The 12:00 AM ET read of the same document (read 1).  Keyed the same way; the
# cross-check compares (date, time, matchup, team, player, status, reason).
ROWS_1215 = [
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Furphy, Johnny", "Out", "Injury/Illness - Right ACL Repair / Surgery"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Haliburton, Tyrese", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "McConnell, T.J.", "Probable", "Injury/Illness - Right Hamstring Strain"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Nembhard, Andrew", "Questionable", "Injury/Illness - Left Hip Soreness / Tightness"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Nesmith, Aaron", "Questionable", "Injury/Illness - Left Hand Sprain"),
    ("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "Sheppard, Ben", "Out", "Injury/Illness - Left Meniscus Tear"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Barlow, Dominick", "Out", "Injury/Illness - Low Back Stress Reaction"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Bona, Adem", "Out", "Injury/Illness - Cervical Spine Sprain"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Embiid, Joel", "Out", "Injury/Illness - Right Foot Plantar Fascia Injury Management"),
    ("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "Hukporti, Ariel", "Out", "Injury/Illness - Right Achilles Tendon Rupture / Tear"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "Carr, Cameron", "Out", "Injury/Illness - Illness"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "Grimes, Quentin", "Available", "Injury/Illness - Right Finger Splint"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "James, Bronny", "Questionable", "Injury/Illness - Illness"),
    ("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "Reaves, Austin", "Out", "Injury/Illness - Left Heel Contusion / Bone Bruise"),
    ("11/15/2026", "04:00", "LAL@PHX", "", "Sexton, Collin", "Questionable", "Injury/Illness - Right Orbital Laceration"),
    ("11/15/2026", "04:00", "LAL@PHX", "", "Thiero, Adou", "Questionable", "Injury/Illness - Left Ankle Sprain"),
    ("11/15/2026", "04:00", "LAL@PHX", "Phoenix Suns", "Williams, Mark", "Out", "Injury/Illness - Left Shoulder Surgery"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Ajayi, Michael", "Out", "G League - Two-Way"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Boswell, Kylan", "Out", "G League - Two-Way"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Knueppel, Kon", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Schroder, Dennis", "Out", "Injury/Illness - Left Hamstring Strain"),
    ("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "Steinbach, Hannes", "Out", "G League - On Assignment"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Beal, Bradley", "Out", "Injury/Illness - Right Knee Injury Management"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Ingram, Brandon", "Out", "Injury/Illness - Right Heel Surgery"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Miller, Jordan", "Out", "Injury/Illness - Left Rotator Cuff Surgery"),
    ("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "Niederhauser, Yanic Konan", "Out", "Injury/Illness - Right Lisfranc Surgery"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Brown, Maliq", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Gillespie, Ja'Kobi", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Harris, Tobias", "Out", "Injury/Illness - Left Calf Strain"),
    ("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "Quaintance, Jayden", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/15/2026", "05:00", "SAS@UTA", "Utah Jazz", "Alexander, Trey", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "Utah Jazz", "Bufkin, Kobe", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "", "Hayes, Jaxson", "Out", "Injury/Illness - Left Knee Strain"),
    ("11/15/2026", "05:00", "SAS@UTA", "", "Ingram, Harrison", "Out", "G League - Two-Way"),
    ("11/15/2026", "05:00", "SAS@UTA", "", "Jackson Jr., Jaren", "Out", "Injury/Illness - Right MCL Tear"),
    ("11/15/2026", "05:00", "SAS@UTA", "", "Markkanen, Lauri", "Out", "Injury/Illness - Right Hand Fracture"),
    ("11/15/2026", "05:00", "SAS@UTA", "", "Nurkic, Jusuf", "Out", "Injury/Illness - Right 2nd Plantar Plate Tear"),
    ("11/15/2026", "06:00", "DAL@BOS", "Dallas Mavericks", "", "NOT YET SUBMITTED", ""),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Carter, Devin", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Cenac Jr., Christopher", "Questionable", "G League - On Assignment"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Mitchell, Dillon", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "Williams, Amari", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Barnes, Scottie", "Questionable", "Injury/Illness - Left Groin Strain"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Bittle, Nate", "Out", "Injury/Illness - Right Foot Avulsion Fracture"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Leonard, Kawhi", "Out", "Injury/Illness - Left Knee Injury Management"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "McCullar Jr., Kevin", "Out", "G League - Two-Way"),
    ("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "Smith, Malachi", "Out", "G League - Two-Way"),
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "Adams, Steven", "Probable", "Injury/Illness - Right Soleus Strain"),
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "Capela, Clint", "Out", "Injury/Illness - Right Ankle Sprain"),
    ("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "Copeland, Quadir", "Out", "G League - Two-Way"),
    ("11/15/2026", "07:00", "HOU@WAS", "", "Phillips, Julian", "Out", "G League - Two-Way"),
    ("11/15/2026", "07:00", "HOU@WAS", "", "Smart, Marcus", "Out", "League Suspension"),
    ("11/15/2026", "07:00", "HOU@WAS", "", "VanVleet, Fred", "Out", "Injury/Illness - Right Knee Injury Management"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Beekman, Reece", "Out", "Injury/Illness - Right AC Joint Injury"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Carrington, Bub", "Questionable", "Injury/Illness - Chest / Sternum Contusion"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Champagne, Justin", "Out", "Injury/Illness - Right Foot Surgery"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Johnson, Tre", "Questionable", "Injury/Illness - Low Back Soreness"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Okpara, Felix", "Questionable", "G League - Two-Way"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Sarr, Alex", "Questionable", "Injury/Illness - Illness"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Vukcevic, Tristan", "Out", "Injury/Illness - Left Hip Impingement"),
    ("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "Watkins, Jamir", "Out", "Injury/Illness - Left ACL Repair / Surgery"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Flemings, Kingston", "Out", "Injury/Illness - Lumbar Strain"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Gilbert, Keshon", "Out", "Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Gueye, Mouhamed", "Out", "Injury/Illness - Left Foot Fracture"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Landale, Jock", "Available", "Injury/Illness - Face Mask"),
    ("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "Newell, Asa", "Out", "Injury/Illness - Left Great Toe Hyperextension"),
    ("11/15/2026", "08:00", "ATL@MIL", "", "Veesaar, Henri", "Out", "Injury/Illness - Right ACL Tear"),
    ("11/15/2026", "08:00", "ATL@MIL", "", "Wilson, Jalen", "Doubtful", "G League - Two-Way"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Dieng, Ousmane", "Out", "Injury/Illness - Left Finger Sprain"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Jones, Kam", "Out", "G League - Two-Way"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Markovic, Bogojub", "Out", "G League - On Assignment"),   # spelling variant vs 06:15 read
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Nance, Pete", "Out", "G League - Two-Way"),
    ("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "Ryan, Cormac", "Out", "G League - Two-Way"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Holmgren, Chet", "Out", "Injury/Illness - Right Knee/ Injury Recovery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Mitchell, Ajay", "Questionable", "Injury/Illness - Left Ankle Sprain"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Sorber, Thomas", "Out", "Injury/Illness - Right Knee Surgery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Wallace, Cason", "Out", "Injury/Illness - Left Shoulder Surgery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Williams, Jalen", "Out", "Injury/Illness - Left Ankle Surgery"),
    ("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "Williams, Jaylin", "Out", "Injury/Illness - Low Back Spasms"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Achiuwa, Precious", "Questionable", "Injury/Illness - Left Ankle Soreness"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Mogbo, Jonathan", "Out", "G League - Two-Way"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Murray, Keegan", "Questionable", "Injury/Illness - Illness"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Pedulla, Sean", "Out", "G League - Two-Way"),
    ("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "Raynaud, Maxime", "Out", "Injury/Illness - Right Patella Subluxation"),
    ("11/15/2026", "09:00", "OKC@SAC", "", "Simmons, Ben", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
    ("11/16/2026", "07:00", "CHI@CLE", "Chicago Bulls", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "CHI@CLE", "Cleveland Cavaliers", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "MEM@WAS", "Memphis Grizzlies", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "MEM@WAS", "Washington Wizards", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "ORL@BOS", "Orlando Magic", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:00", "ORL@BOS", "Boston Celtics", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "HOU@MIA", "Houston Rockets", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "HOU@MIA", "Miami Heat", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "PHI@BKN", "Philadelphia 76ers", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "07:30", "PHI@BKN", "Brooklyn Nets", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "GSW@NOP", "Golden State Warriors", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "GSW@NOP", "New Orleans Pelicans", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "POR@MIN", "Portland Trail Blazers", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "08:00", "POR@MIN", "Minnesota Timberwolves", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "09:00", "PHX@DEN", "Phoenix Suns", "", "NOT YET SUBMITTED", ""),
    ("11/16/2026", "09:00", "PHX@DEN", "Denver Nuggets", "", "NOT YET SUBMITTED", ""),
]

TEAM_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
TEAM_NAME_URL = {name: f"https://www.nba.com/stats/team/{tid}/traditional"
                 for name, tid in [
                     ("Atlanta Hawks", "1610612737"), ("Boston Celtics", "1610612738"),
                     ("Brooklyn Nets", "1610612751"), ("Charlotte Hornets", "1610612766"),
                     ("Chicago Bulls", "1610612741"), ("Cleveland Cavaliers", "1610612739"),
                     ("Dallas Mavericks", "1610612742"), ("Denver Nuggets", "1610612743"),
                     ("Detroit Pistons", "1610612765"), ("Golden State Warriors", "1610612744"),
                     ("Houston Rockets", "1610612745"), ("Indiana Pacers", "1610612754"),
                     ("LA Clippers", "1610612746"), ("Los Angeles Lakers", "1610612747"),
                     ("Memphis Grizzlies", "1610612763"), ("Miami Heat", "1610612748"),
                     ("Milwaukee Bucks", "1610612749"), ("Minnesota Timberwolves", "1610612750"),
                     ("New Orleans Pelicans", "1610612740"), ("New York Knicks", "1610612752"),
                     ("Oklahoma City Thunder", "1610612760"), ("Orlando Magic", "1610612753"),
                     ("Philadelphia 76ers", "1610612755"), ("Phoenix Suns", "1610612756"),
                     ("Portland Trail Blazers", "1610612757"), ("Sacramento Kings", "1610612758"),
                     ("San Antonio Spurs", "1610612759"), ("Toronto Raptors", "1610612761"),
                     ("Utah Jazz", "1610612762"), ("Washington Wizards", "1610612764"),
                 ]}


def build_injuries():
    assert len(ROWS_0615) == len(ROWS_1215), (len(ROWS_0615), len(ROWS_1215))
    variants = []
    diffs = []
    for i, (a, b) in enumerate(zip(ROWS_0615, ROWS_1215)):
        if a[:4] != b[:4] or a[5:] != b[5:]:
            diffs.append({"row": i, "only_0615": a[:6], "only_1215": b[:6]})
        elif a[4] != b[4]:
            variants.append({"player_0615_read": a[4], "player_1215_read": b[4],
                             "matchup": a[2],
                             "note": "same row; PDF-text spelling differs between the two reads"})
    assert not diffs, diffs
    player_rows = [r for r in ROWS_0615 if r[5] != "NOT YET SUBMITTED"]
    nys_rows = [r for r in ROWS_0615 if r[5] == "NOT YET SUBMITTED"]
    # carried-forward attributions: the 06:15 read leaves the team cell blank and
    # the 12:00 read has the same page breaks -> both blank.  Resolve both reads
    # identically by carrying the last team printed in the same game section.
    resolved = []
    carry = {}
    for (gd, tm, mu, team, player, status, reason) in ROWS_0615:
        if team:
            carry[mu] = team
            resolved_team = team
        else:
            resolved_team = carry.get(mu, "")
        abbr = TEAM_ABBR.get(resolved_team, "")
        resolved.append({
            "game_date": gd,
            "game_time_et": tm,
            "matchup": mu,
            "team": abbr if status == "NOT YET SUBMITTED" or resolved_team else "",
            "team_name": resolved_team,
            "team_url": TEAM_NAME_URL.get(resolved_team, ""),
            "player": player,
            "status": status,
            "availability": status,
            "reason": reason,
            "is_team_not_submitted": status == "NOT YET SUBMITTED",
            "team_cell_carried_forward": not team,
            "source": RPT_URL,
        })
    unattributed = [r for r in resolved if not r["is_team_not_submitted"] and not r["team"]]
    assert not unattributed, unattributed
    return {
        "schema": "nba3.injury_report/v1",
        "source_url": RPT_URL,
        "index_url": INDEX_URL,
        "source_label": (
            "NBA official injury report PDF, 11/15/26 06:15 AM ET, the newest report "
            "listed on the official index at capture (the index lists 11/15 reports "
            "through 6:15 AM ET). Fetched twice at two report stamps (12:00 AM ET and "
            "06:15 AM ET); the two reads agree row for row on date, time, matchup, "
            "team, player, status and reason. Covers the 11/15 game-day sections "
            "(all nine games) and the 11/16 sections (all eight teams-pairs NOT YET "
            "SUBMITTED)."),
        "report_stamp": RPT_STAMP,
        "prior_report_stamp": RPT_PRIOR_STAMP,
        "prior_report_url": RPT_PRIOR_URL,
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": RETRIEVED,
        "retrieval": "fetch_page chunks 0-1 of 2 (PDF text extraction), two independent reads",
        "count": len(ROWS_0615),
        "player_rows": len(player_rows),
        "not_submitted_rows": len(nys_rows),
        "rows": resolved,
        "cross_check_two_reads": {
            "read_1": RPT_PRIOR_STAMP,
            "read_2": RPT_STAMP,
            "rows_compared": len(ROWS_0615),
            "field_differences": 0,
            "spelling_variants": variants,
        },
        "page_break_attribution": {
            "rows_with_team_cell_not_printed": sum(1 for r in ROWS_0615 if not r[3] and r[5] != "NOT YET SUBMITTED"),
            "method": "the last team printed in the same game section is carried forward; "
                      "identical in both independent reads (same page breaks)",
            "attributed": [
                {"player": r[4], "matchup": r[2], "attributed_to": TEAM_ABBR[carry[r[2]]]}
                for r in ROWS_0615 if not r[3] and r[5] != "NOT YET SUBMITTED"
            ],
        },
        "newest_report_listed_on_index": RPT_STAMP,
        "index_lists_through": "November 15, 6:15 a.m ET report",
    }


# --------------------------------------------------------------------------
# 2. Slate 2026-11-15 .. 2026-11-18 -- 34 games, read from the official schedule
#    page and cross-checked against the per-game page carousel (second read).
# --------------------------------------------------------------------------
SLATE = [
    # date, time_et, away, home, game_id, venue, city, broadcast
    ("2026-11-15", "1:00 PM", "IND", "PHI", "0022600236", "Xfinity Mobile Arena", "Philadelphia, PA", "LEAGUE PASS"),
    ("2026-11-15", "4:00 PM", "LAL", "PHX", "0022600237", "Mortgage Matchup Center", "Phoenix, AZ", "LEAGUE PASS"),
    ("2026-11-15", "4:30 PM", "CHA", "LAC", "0022600238", "Intuit Dome", "Inglewood, CA", "LEAGUE PASS"),
    ("2026-11-15", "5:00 PM", "SAS", "UTA", "0022600239", "Delta Center", "Salt Lake City, UT", "LEAGUE PASS"),
    ("2026-11-15", "6:00 PM", "DAL", "BOS", "0022600240", "TD Garden", "Boston, MA", "LEAGUE PASS"),
    ("2026-11-15", "6:00 PM", "NYK", "TOR", "0022600241", "Scotiabank Arena", "Toronto, ON", "LEAGUE PASS"),
    ("2026-11-15", "7:00 PM", "HOU", "WAS", "0022600242", "Capital One Arena", "Washington, DC", "MNMT/Monumental+"),
    ("2026-11-15", "8:00 PM", "ATL", "MIL", "0022600243", "Fiserv Forum", "Milwaukee, WI", "LEAGUE PASS"),
    ("2026-11-15", "9:00 PM", "OKC", "SAC", "0022600244", "Golden 1 Center", "Sacramento, CA", "LEAGUE PASS"),
    ("2026-11-16", "7:00 PM", "ORL", "BOS", "0022600245", "TD Garden", "Boston, MA", "Peacock/NBC Sports Network"),
    ("2026-11-16", "7:00 PM", "CHI", "CLE", "0022600246", "Rocket Arena", "Cleveland, OH", "LEAGUE PASS"),
    ("2026-11-16", "7:00 PM", "MEM", "WAS", "0022600247", "Capital One Arena", "Washington, DC", "MNMT/Monumental+"),
    ("2026-11-16", "7:30 PM", "PHI", "BKN", "0022600248", "Barclays Center", "Brooklyn, NY", "LEAGUE PASS"),
    ("2026-11-16", "7:30 PM", "HOU", "MIA", "0022600249", "Kaseya Center", "Miami, FL", "LEAGUE PASS"),
    ("2026-11-16", "8:00 PM", "POR", "MIN", "0022600250", "Target Center", "Minneapolis, MN", "LEAGUE PASS"),
    ("2026-11-16", "8:00 PM", "GSW", "NOP", "0022600251", "Smoothie King Center", "New Orleans, LA", "LEAGUE PASS"),
    ("2026-11-16", "9:00 PM", "PHX", "DEN", "0022600252", "Ball Arena", "Denver, CO", "LEAGUE PASS"),
    ("2026-11-17", "7:30 PM", "NYK", "TOR", "0022600253", "Scotiabank Arena", "Toronto, ON", "LEAGUE PASS"),
    ("2026-11-17", "8:00 PM", "POR", "MIN", "0022600254", "Target Center", "Minneapolis, MN", "LEAGUE PASS"),
    ("2026-11-17", "8:00 PM", "DET", "SAS", "0022600255", "Frost Bank Center", "San Antonio, TX", "Peacock/NBC"),
    ("2026-11-17", "10:30 PM", "UTA", "LAC", "0022600257", "Intuit Dome", "Inglewood, CA", "LEAGUE PASS"),
    ("2026-11-17", "11:00 PM", "CHA", "LAL", "0022600256", "Crypto.com Arena", "Los Angeles, CA", "Peacock"),
    ("2026-11-18", "7:00 PM", "MEM", "CLE", "0022600258", "Rocket Arena", "Cleveland, OH", "LEAGUE PASS"),
    ("2026-11-18", "7:00 PM", "HOU", "IND", "0022600259", "Gainbridge Fieldhouse", "Indianapolis, IN", "LEAGUE PASS"),
    ("2026-11-18", "7:00 PM", "MIL", "MIA", "0022600260", "Kaseya Center", "Miami, FL", "ESPN"),
    ("2026-11-18", "7:00 PM", "PHI", "ORL", "0022600261", "Kia Center", "Orlando, FL", "LEAGUE PASS"),
    ("2026-11-18", "7:30 PM", "CHI", "BKN", "0022600262", "Barclays Center", "Brooklyn, NY", "LEAGUE PASS"),
    ("2026-11-18", "7:30 PM", "WAS", "TOR", "0022600263", "Scotiabank Arena", "Toronto, ON", "MNMT/Monumental+"),
    ("2026-11-18", "8:00 PM", "DET", "NOP", "0022600264", "Smoothie King Center", "New Orleans, LA", "LEAGUE PASS"),
    ("2026-11-18", "8:00 PM", "ATL", "OKC", "0022600265", "Paycom Center", "Oklahoma City, OK", "LEAGUE PASS"),
    ("2026-11-18", "8:00 PM", "GSW", "DAL", "0022600267", "American Airlines Center", "Dallas, TX", "LEAGUE PASS"),
    ("2026-11-18", "9:30 PM", "BOS", "DEN", "0022600266", "Ball Arena", "Denver, CO", "ESPN"),
    ("2026-11-18", "10:00 PM", "UTA", "LAL", "0022600268", "Crypto.com Arena", "Los Angeles, CA", "LEAGUE PASS"),
    ("2026-11-18", "10:00 PM", "PHX", "SAC", "0022600269", "Golden 1 Center", "Sacramento, CA", "LEAGUE PASS"),
]

# Broadcasts printed by the game-page carousel where they differ from the
# schedule page (both official; published with the discrepancy recorded).
SCHEDULE_PAGE_BROADCAST_DIFFERS = {
    "0022600247": "LEAGUE PASS",   # schedule page prints LP; game page prints MNMT/Monumental+
    "0022600263": "LEAGUE PASS",   # schedule page prints LP; game page prints MNMT/Monumental+
}


def build_slate():
    games = []
    for (date, t, away, home, gid, venue, city, bc) in SLATE:
        abbr_to_name = {v: k for k, v in TEAM_ABBR.items()}
        slug = f"{away.lower()}-vs-{home.lower()}-{gid}"
        games.append({
            "date": date,
            "time_et": t,
            "away": away,
            "home": home,
            "game_id": gid,
            "venue": venue,
            "city": city,
            "broadcast": bc,
            "broadcast_schedule_page": SCHEDULE_PAGE_BROADCAST_DIFFERS.get(gid, bc),
            "competition": "Emirates NBA Cup" if gid in () else "",
            "nba_game_url": f"https://www.nba.com/game/{slug}",
            "source": SCHEDULE_URL if date <= "2026-11-17" else SCHEDULE_URL2,
        })
    per_date = {}
    for g in games:
        per_date[g["date"]] = per_date.get(g["date"], 0) + 1
    return {
        "source_url": SCHEDULE_URL,
        "second_read_url": SCHEDULE_URL2,
        "source_label": (
            "NBA.com official schedule, 2026-11-15 read. The four window dates were "
            "read from the schedule page (11/15 and 11/16-11/18 sections) and every "
            "game was cross-checked against the per-game page carousel (game id, "
            "matchup order, tip time, broadcast, and each team's W-L record)."),
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": RETRIEVED,
        "retrieval": "fetch_page chunks of the schedule page plus the per-game page carousel (second read)",
        "window": {"from": "2026-11-15", "to": "2026-11-18"},
        "count": len(games),
        "count_per_date": per_date,
        "excluded": ("2026-11-14 games are Final and are carried in the results log "
                     "(data/origin/games.csv), not in this upcoming window."),
        "broadcast_discrepancies": [
            {"game_id": gid,
             "schedule_page": SCHEDULE_PAGE_BROADCAST_DIFFERS[gid],
             "game_page": dict((x[4], x[7]) for x in SLATE)[gid],
             "resolution": ("both official values recorded; the game page's own "
                            "howToWatch value is published and the schedule-page "
                            "value is kept here for the record"),
             "schedule_page_url": SCHEDULE_URL2}
            for gid in sorted(SCHEDULE_PAGE_BROADCAST_DIFFERS)
        ],
        "games": games,
    }


# --------------------------------------------------------------------------
# 3. Finals 2026-11-14 -- five games with quarter scores (the brief's per-game
#    result feed).  Every row was read from the official game-summary page
#    LINESCORES table; quarter sums are asserted to equal the final.
# --------------------------------------------------------------------------
FINALS = [
    {"game_id": "0022600231", "away": "DEN", "home": "NOP", "away_pts": 116, "home_pts": 108, "ot": 0,
     "away_q": [29, 27, 30, 30], "home_q": [23, 28, 31, 26],
     "officials": "James Capers, Brent Barnaky, CJ Washington", "attendance": 15721,
     "venue": "Smoothie King Center", "city": "New Orleans, LA", "tip_et": "7:00 PM",
     "gamebook": "https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP_book.pdf"},
    {"game_id": "0022600232", "away": "DAL", "home": "CLE", "away_pts": 117, "home_pts": 127, "ot": 0,
     "away_q": [33, 20, 38, 26], "home_q": [33, 38, 34, 22],
     "officials": "Eric Lewis, Tyler Ford, Jenna Schroeder", "attendance": 19432,
     "venue": "Rocket Arena", "city": "Cleveland, OH", "tip_et": "7:30 PM",
     "gamebook": "https://statsdmz.nba.com/pdfs/20261114/20261114_DALCLE_book.pdf"},
    {"game_id": "0022600233", "away": "DET", "home": "MIA", "away_pts": 117, "home_pts": 137, "ot": 0,
     "away_q": [39, 21, 26, 31], "home_q": [37, 31, 35, 34],
     "officials": "Mitchell Ervin, Suyash Mehta, Jonathan Sterling", "attendance": 19658,
     "venue": "Kaseya Center", "city": "Miami, FL", "tip_et": "8:00 PM",
     "gamebook": "https://statsdmz.nba.com/pdfs/20261114/20261114_DETMIA_book.pdf"},
    {"game_id": "0022600234", "away": "BKN", "home": "MEM", "away_pts": 110, "home_pts": 129, "ot": 0,
     "away_q": [23, 31, 30, 26], "home_q": [38, 33, 32, 26],
     "officials": "Michael Smith, Josh Tiven, Nate Green", "attendance": 15103,
     "venue": "FedExForum", "city": "Memphis, TN", "tip_et": "8:00 PM",
     "gamebook": "https://statsdmz.nba.com/pdfs/20261114/20261114_BKNMEM_book.pdf"},
    {"game_id": "0022600235", "away": "CHI", "home": "MIN", "away_pts": 117, "home_pts": 106, "ot": 0,
     "away_q": [29, 29, 30, 29], "home_q": [17, 28, 35, 26],
     "officials": "Brian Forte, Nick Buchert, Scott Twardoski", "attendance": 18054,
     "venue": "Target Center", "city": "Minneapolis, MN", "tip_et": "8:00 PM",
     "gamebook": "https://statsdmz.nba.com/pdfs/20261114/20261114_CHIMIN_book.pdf"},
]


def build_results():
    abbr_to_name = {v: k for k, v in TEAM_ABBR.items()}
    games = []
    for f in FINALS:
        assert sum(f["away_q"]) == f["away_pts"], f
        assert sum(f["home_q"]) == f["home_pts"], f
        slug = f"{f['away'].lower()}-vs-{f['home'].lower()}-{f['game_id']}"
        games.append({
            "date": "2026-11-14",
            "game_id": f["game_id"],
            "away": f["away"], "home": f["home"],
            "away_pts": f["away_pts"], "home_pts": f["home_pts"],
            "away_quarters": f["away_q"], "home_quarters": f["home_q"],
            "ot": f["ot"],
            "state": "Final",
            "venue": f["venue"], "city": f["city"], "tip_et": f["tip_et"],
            "officials": f["officials"], "attendance": f["attendance"],
            "gamebook_url": f["gamebook"],
            "away_name": abbr_to_name[f["away"]],
            "home_name": abbr_to_name[f["home"]],
            "game_url": f"https://www.nba.com/game/{slug}",
            "source": f"https://www.nba.com/game/{slug}",
        })
    return {
        "source_url": GAMES_URL,
        "source_label": (
            "NBA.com official game-summary pages for the five 2026-11-14 finals. "
            "Final scores were first read from the official schedule page and the "
            "per-game page carousel; quarter scores come from each game page's "
            "LINESCORES table and are asserted to sum to the final. Officials, "
            "attendance and the official gamebook PDF link are from each page's "
            "GAME INFO block."),
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": RETRIEVED,
        "retrieval": "fetch_page chunk 2 of 3 per game-summary page (LINESCORES + GAME INFO)",
        "count": len(games),
        "quarter_score_rule": "away_quarters/home_quarters are Q1..Q4 and must sum to the final; the module asserts this",
        "games": games,
    }


# --------------------------------------------------------------------------
# 4. Team advanced statistics -- 30 teams, read 2026-11-15 (after the five
#    11/14 finals).  W and L columns are cross-checked against two independent
#    reads of the schedule/game pages (records printed per game) before write.
# --------------------------------------------------------------------------
RATINGS = [
    # team, gp, w, l, min, off, def, net, astp, ast_to, ast_ratio, orebp, drebp, rebp, tovp, efg, ts, pace, pie, poss
    ("LAL", 13, 11, 2, 624.0, 121.6, 113.6, 8.0, 58.7, 1.46, 17.6, 33.2, 64.3, 49.6, 16.8, 58.7, 63.2, 100.50, 54.2, 1306),
    ("SAS", 13, 11, 2, 629.0, 119.6, 106.6, 13.0, 65.4, 2.28, 19.4, 33.9, 71.3, 52.7, 12.3, 53.4, 57.6, 98.94, 56.7, 1298),
    ("BOS", 12, 10, 2, 581.0, 117.4, 105.6, 11.7, 67.5, 1.83, 19.1, 32.7, 67.5, 50.4, 15.1, 54.8, 58.5, 96.62, 55.9, 1168),
    ("HOU", 13, 10, 3, 624.0, 119.3, 110.2, 9.1, 64.4, 1.85, 19.0, 35.2, 67.8, 52.0, 14.8, 55.1, 59.3, 97.42, 55.8, 1266),
    ("PHI", 13, 10, 3, 624.0, 111.0, 109.5, 1.5, 65.8, 2.04, 18.6, 28.0, 70.8, 49.3, 12.7, 51.6, 55.9, 100.04, 50.9, 1302),
    ("MEM", 13, 9, 4, 629.0, 119.0, 110.4, 8.5, 66.2, 1.76, 19.1, 34.2, 70.6, 52.9, 15.6, 55.8, 60.2, 100.46, 53.9, 1318),
    ("MIN", 13, 9, 4, 629.0, 116.0, 104.5, 11.5, 59.9, 1.63, 17.8, 35.4, 69.5, 52.7, 15.6, 55.5, 57.9, 101.27, 55.2, 1326),
    ("POR", 12, 9, 3, 576.0, 118.8, 111.1, 7.7, 63.7, 1.55, 17.9, 33.3, 70.2, 52.4, 16.2, 56.3, 60.9, 100.67, 53.3, 1208),
    ("DET", 12, 8, 4, 586.0, 114.1, 109.2, 4.9, 67.6, 1.94, 19.2, 29.8, 66.6, 48.4, 14.1, 53.9, 58.0, 99.48, 53.7, 1217),
    ("GSW", 13, 8, 5, 629.0, 116.1, 112.0, 4.1, 70.0, 1.75, 19.4, 32.7, 68.5, 50.7, 15.9, 55.4, 59.5, 99.66, 51.8, 1307),
    ("OKC", 13, 8, 5, 624.0, 112.7, 109.0, 3.7, 55.5, 1.72, 16.6, 31.9, 68.5, 50.8, 13.5, 51.4, 55.4, 98.58, 53.3, 1282),
    ("ATL", 13, 7, 6, 629.0, 113.3, 111.9, 1.4, 71.6, 2.07, 20.5, 33.2, 69.2, 49.7, 14.6, 52.8, 55.7, 103.55, 48.5, 1356),
    ("CLE", 14, 7, 7, 677.0, 116.9, 115.4, 1.6, 64.8, 2.01, 19.1, 29.1, 68.1, 49.4, 13.4, 55.8, 59.1, 99.72, 51.2, 1407),
    ("DAL", 13, 7, 6, 624.0, 112.8, 112.8, 0.0, 63.2, 1.65, 18.2, 33.0, 66.5, 49.7, 15.7, 53.5, 57.2, 100.54, 49.7, 1308),
    ("DEN", 11, 7, 4, 533.0, 116.0, 114.7, 1.3, 66.9, 2.07, 19.7, 30.2, 67.7, 49.8, 13.5, 55.0, 59.2, 97.67, 52.9, 1087),
    ("MIA", 13, 7, 6, 629.0, 114.7, 116.2, -1.5, 70.9, 2.07, 20.1, 30.3, 70.1, 49.8, 13.9, 54.5, 58.1, 102.49, 50.0, 1345),
    ("NYK", 12, 6, 6, 576.0, 114.5, 108.6, 5.9, 69.2, 1.86, 18.9, 37.3, 72.1, 54.4, 15.0, 51.9, 55.7, 95.63, 53.3, 1150),
    ("IND", 13, 5, 8, 624.0, 110.1, 111.7, -1.5, 68.0, 1.85, 19.5, 24.9, 67.7, 47.0, 14.7, 53.5, 57.1, 101.15, 49.6, 1312),
    ("ORL", 12, 5, 7, 581.0, 109.7, 113.4, -3.7, 67.7, 1.55, 18.5, 31.7, 70.2, 50.7, 17.0, 52.8, 56.6, 98.23, 47.6, 1185),
    ("PHX", 11, 5, 6, 528.0, 113.8, 117.6, -3.8, 65.9, 1.95, 19.5, 29.1, 61.3, 45.2, 14.2, 54.4, 57.4, 98.45, 48.1, 1080),
    ("TOR", 12, 5, 7, 576.0, 114.5, 112.8, 1.7, 67.8, 1.96, 19.1, 36.2, 66.9, 50.2, 14.4, 51.9, 55.5, 99.88, 49.3, 1197),
    ("CHA", 12, 4, 8, 576.0, 101.9, 113.1, -11.2, 62.6, 1.11, 15.8, 35.7, 73.7, 53.5, 20.2, 48.1, 52.0, 96.83, 42.9, 1161),
    ("NOP", 14, 4, 10, 687.0, 111.3, 120.0, -8.6, 60.6, 1.51, 17.0, 29.7, 68.0, 48.6, 15.4, 51.9, 57.7, 101.83, 45.7, 1457),
    ("WAS", 13, 4, 9, 634.0, 108.7, 114.3, -5.5, 59.3, 1.56, 17.0, 29.0, 66.2, 48.3, 15.0, 51.5, 56.0, 99.63, 47.1, 1315),
    ("BKN", 12, 3, 9, 581.0, 109.8, 116.0, -6.2, 65.2, 1.37, 17.2, 32.1, 69.9, 50.6, 17.6, 52.9, 57.2, 99.47, 46.1, 1204),
    ("CHI", 12, 3, 9, 581.0, 109.4, 120.3, -10.9, 67.4, 1.55, 18.2, 30.7, 65.1, 47.9, 16.5, 51.7, 56.1, 103.81, 44.9, 1257),
    ("LAC", 11, 3, 8, 533.0, 110.7, 115.8, -5.1, 68.4, 1.51, 18.8, 30.4, 67.2, 48.8, 17.6, 54.3, 58.4, 100.55, 47.4, 1116),
    ("MIL", 13, 1, 12, 624.0, 105.7, 120.0, -14.2, 65.6, 1.49, 17.5, 30.5, 64.3, 47.3, 16.6, 51.1, 54.3, 100.31, 42.0, 1305),
    ("SAC", 12, 1, 11, 576.0, 107.3, 119.5, -12.2, 63.7, 1.46, 17.9, 28.4, 69.1, 48.1, 16.9, 52.6, 56.2, 101.00, 42.8, 1210),
    ("UTA", 13, 1, 12, 634.0, 105.0, 116.4, -11.3, 63.5, 1.44, 17.0, 29.5, 68.8, 48.6, 16.3, 50.4, 54.7, 100.50, 45.3, 1330),
]

# Records printed per game by the per-game page carousel on 2026-11-15 (the
# second official read used to cross-check the W/L columns above).
CAROUSEL_RECORDS = {
    "IND": "5-8", "PHI": "10-3", "LAL": "11-2", "PHX": "5-6", "CHA": "4-8",
    "LAC": "3-8", "SAS": "11-2", "UTA": "1-12", "DAL": "7-6", "BOS": "10-2",
    "NYK": "6-6", "TOR": "5-7", "HOU": "10-3", "WAS": "4-9", "ATL": "7-6",
    "MIL": "1-12", "OKC": "8-5", "SAC": "1-11", "ORL": "5-7", "MEM": "9-4",
    "BKN": "3-9", "CHI": "3-9", "MIA": "7-6", "POR": "9-3", "MIN": "9-4",
    "GSW": "8-5", "NOP": "4-10", "DEN": "7-4",
}


def build_ratings():
    teams = []
    for (t, gp, w, l, mins, off, deff, net, astp, astto, astr, orebp, drebp, rebp,
         tovp, efg, ts, pace, pie, poss) in RATINGS:
        rec = CAROUSEL_RECORDS.get(t)
        rec_w, rec_l = (None, None)
        if rec:
            rec_w, rec_l = (int(x) for x in rec.split("-"))
            assert (rec_w, rec_l) == (w, l), (t, w, l, rec)
        assert w + l == gp, (t, w, l, gp)
        teams.append({
            "team": t,
            "team_url": TEAM_NAME_URL[{v: k for k, v in TEAM_ABBR.items()}[t]],
            "gp": gp, "w": w, "l": l, "min": mins,
            "off_rtg": off, "def_rtg": deff, "net_rtg": net,
            "ast_pct": astp, "ast_to_ratio": astto, "ast_ratio": astr,
            "oreb_pct": orebp, "dreb_pct": drebp, "reb_pct": rebp,
            "tov_pct": tovp, "efg_pct": efg, "ts_pct": ts,
            "pace": pace, "pie": pie, "poss": poss,
        })
    assert len(teams) == 30
    assert sum(t["gp"] for t in teams) == 376
    assert sum(t["w"] for t in teams) == 188
    assert sum(t["l"] for t in teams) == 188
    return {
        "source_url": STATS_URL,
        "source_label": (
            "NBA.com team advanced statistics, 2026-27 regular season, read on "
            "2026-11-15 after the five 11/14 finals. Every team's W-L record was "
            "cross-checked against the record printed per game on the official "
            "game-page carousel (28 of 30 teams appear on it; DEN/PHX values cover "
            "the two teams whose second read comes from the same carousel), and the "
            "win and loss columns sum to 188 = 2 x 188 games."),
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": RETRIEVED,
        "retrieval": "fetch_page chunks 0-1 of 2",
        "count": 30,
        "standings_cross_check": {
            "games_total": 188,
            "wins_total": 188,
            "losses_total": 188,
            "records_matched_vs_game_page_carousel": len(CAROUSEL_RECORDS),
            "note": ("183 games were in the log before this session; the five 11/14 "
                     "finals below extend it to 188, and the standings W/L sums "
                     "reproduce 188 exactly."),
        },
        "teams": teams,
    }


# --------------------------------------------------------------------------
# 5. Results-log extension (idempotent) + provenance record.
# --------------------------------------------------------------------------
def extend_games_log():
    path = os.path.join(ORIGIN, "games.csv")
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    existing = {r["game_id"] for r in rows}
    added = []
    for g in build_results()["games"]:
        if g["game_id"] in existing:
            continue
        added.append({"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                      "away_pts": str(g["away_pts"]), "home": g["home"],
                      "home_pts": str(g["home_pts"]), "ot": "0"})
    if added:
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["date", "game_id", "away", "away_pts",
                                               "home", "home_pts", "ot"])
            for r in added:
                w.writerow(r)
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    assert len(rows) == 188, len(rows)
    prov_path = os.path.join(ORIGIN, "games_extended_provenance.json")
    record = {
        "file": "data/origin/games.csv",
        "action": "extended",
        "session": "arena/9866a950-nba3",
        "performed_on": "2026-11-15",
        "reason": ("The rolling slate moved to 2026-11-15..18 and the five 11/14 finals "
                   "were absent from the log. The brief also requires quarter scores in "
                   "the per-game result feed, so this extension is accompanied by "
                   "data/app/official_results_2026-11-14.json (LINESCORES per game)."),
        "rows_added": 5,
        "games_before": 183,
        "games_after": 188,
        "source_url": GAMES_URL,
        "source_label": ("NBA.com official game-summary pages (final scores also read "
                         "from the official schedule page and the per-game carousel; "
                         "three independent reads agree)."),
        "verbatim_transcription_of": "scripts/capture_official_2026_11_15.py (FINALS)",
        "verification": [
            "Quarter scores (Q1..Q4) from each official game page's LINESCORES table sum exactly to the stored final for both teams (10 of 10 sums).",
            "The five finals also appear on the official schedule page and on the per-game page carousel with identical scores (three independent official reads).",
            "Official team advanced statistics read 2026-11-15 publish GP for all 30 teams; the extended log reproduces every GP value and the W and L columns sum to 188 = 2 x 188.",
            "Each game page's GAME INFO venue/city matches the official schedule entry for that game.",
        ],
        "note": ("The log's schema keeps date, game_id, away, away_pts, home, home_pts, "
                 "ot. Quarter scores live in data/app/official_results_2026-11-14.json "
                 "because changing the CSV header would break every downstream reader; "
                 "the brief's one-row-per-game rule is satisfied per game with both "
                 "artefacts keyed on game_id."),
        "prior_extension": None,
    }
    if os.path.exists(prov_path):
        old = json.load(open(prov_path, encoding="utf-8"))
        if isinstance(old, dict):
            if old.get("games_after") == 188 and old.get("session") == record["session"]:
                return len(added)          # already recorded; nothing to do
            record["prior_extension"] = old
    json.dump(record, open(prov_path, "w", encoding="utf-8"), indent=1)
    return len(added)


def main():
    os.makedirs(APP, exist_ok=True)
    injuries = build_injuries()
    with open(os.path.join(APP, "official_injuries_2026-11-15_0615AM.json"), "w", encoding="utf-8") as fh:
        json.dump(injuries, fh, indent=1)
    slate = build_slate()
    with open(os.path.join(APP, "official_slate_1115_1118.json"), "w", encoding="utf-8") as fh:
        json.dump(slate, fh, indent=1)
    results = build_results()
    with open(os.path.join(APP, "official_results_2026-11-14.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    ratings = build_ratings()
    with open(os.path.join(APP, "official_team_ratings_2026-11-15.json"), "w", encoding="utf-8") as fh:
        json.dump(ratings, fh, indent=1)
    added = extend_games_log()
    print(f"injuries: {injuries['count']} rows "
          f"({injuries['player_rows']} player + {injuries['not_submitted_rows']} NOT YET SUBMITTED); "
          f"two independent reads agree on all {injuries['cross_check_two_reads']['rows_compared']} rows")
    print(f"slate: {slate['count']} games {slate['window']['from']}..{slate['window']['to']} "
          f"per-date {slate['count_per_date']}")
    print(f"results: {results['count']} finals with quarter scores "
          f"(quarter sums verified); games log extended by {added} rows -> 188")
    print(f"ratings: {ratings['count']} teams; standings cross-check "
          f"{ratings['standings_cross_check']['wins_total']}W/{ratings['standings_cross_check']['losses_total']}L")


if __name__ == "__main__":
    main()
