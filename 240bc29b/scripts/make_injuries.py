#!/usr/bin/env python3
"""Build the verified injury-report dataset from the official NBA injury report PDF.

Source: https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf
(the newest report listed on the official index at read time, 2026-11-14).
Re-transcribed row by row 2026-11-14. 49 rows total: 26 player rows + 23
NOT YET SUBMITTED team rows. Content-identical to the 04:15 AM report checked
against the 04:45 AM report (0 differences). Rows with an empty team cell are
printed empty in the PDF and are kept empty (no inference).
"""
import json
import os

ROWS = [
    # DEN@NOP 7:00 PM
    {"game_date": "11/14/2026", "game_time": "07:00 (ET)", "matchup": "DEN@NOP", "team": "Denver Nuggets", "player": "Holmes II, DaRon", "status": "Out", "reason": "G League - On Assignment"},
    {"game_date": "11/14/2026", "game_time": "07:00 (ET)", "matchup": "DEN@NOP", "team": "Denver Nuggets", "player": "Nembhard, Ryan", "status": "Out", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "07:00 (ET)", "matchup": "DEN@NOP", "team": "Denver Nuggets", "player": "Strawther, Julian", "status": "Out", "reason": "Injury/Illness - Left Knee Sprain"},
    {"game_date": "11/14/2026", "game_time": "07:00 (ET)", "matchup": "DEN@NOP", "team": "Denver Nuggets", "player": "Whitmore, Cam", "status": "Out", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "07:00 (ET)", "matchup": "DEN@NOP", "team": "New Orleans Pelicans", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    # DAL@CLE 7:30 PM
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Dallas Mavericks", "player": "Biberovic, Tarik", "status": "Out", "reason": "Injury/Illness - Right Heel Bursitis"},
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Dallas Mavericks", "player": "Christie, Max", "status": "Questionable", "reason": "Injury/Illness - Left Ankle Sprain"},
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Dallas Mavericks", "player": "de Larrea, Sergio", "status": "Out", "reason": "Injury/Illness - Right Knee Sprain"},
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Dallas Mavericks", "player": "Johnson Jr., Morez", "status": "Probable", "reason": "Injury/Illness - Left Shin / Tibia Contusion"},
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Dallas Mavericks", "player": "Lively II, Dereck", "status": "Out", "reason": "Injury/Illness - Right Foot Surgery"},
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Dallas Mavericks", "player": "Martin, Caleb", "status": "Available", "reason": "Injury/Illness - Right Thumb Splint"},
    {"game_date": "11/14/2026", "game_time": "07:30 (ET)", "matchup": "DAL@CLE", "team": "Cleveland Cavaliers", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    # BKN@MEM 8:00 PM
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "BKN@MEM", "team": "Brooklyn Nets", "player": "Bilodeau, Tyler", "status": "Out", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "BKN@MEM", "team": "Brooklyn Nets", "player": "Brown Jr., Mikel", "status": "Questionable", "reason": "Injury/Illness - Illness"},
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "BKN@MEM", "team": "Brooklyn Nets", "player": "Jefferson, Joshua", "status": "Out", "reason": "G League - On Assignment"},
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "BKN@MEM", "team": "Brooklyn Nets", "player": "Nelson, Grant", "status": "Out", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "BKN@MEM", "team": "Brooklyn Nets", "player": "Saraf, Ben", "status": "Out", "reason": "G League - On Assignment"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "", "team": "", "player": "Traore, Nolan", "status": "Probable", "reason": "Injury/Illness - Right Calf Tightness / Soreness"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "", "team": "Memphis Grizzlies", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    # CHI@MIN 8:00 PM
    {"game_date": "11/14/2026", "game_time": "", "matchup": "CHI@MIN", "team": "Chicago Bulls", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "CHI@MIN", "team": "Minnesota Timberwolves", "player": "Beringer, Joan", "status": "Available", "reason": "Injury/Illness - Face Mask"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "CHI@MIN", "team": "Minnesota Timberwolves", "player": "DiVincenzo, Donte", "status": "Out", "reason": "Injury/Illness - Right Achilles Tendon Repair / Surgery"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "CHI@MIN", "team": "Minnesota Timberwolves", "player": "Edwards, Anthony", "status": "Out", "reason": "Injury/Illness - Right Knee Arthroscopy"},
    # DET@MIA 8:00 PM
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Duren, Jalen", "status": "Out", "reason": "Injury/Illness - Right Hamstring Strain"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Harkless, Elijah", "status": "Questionable", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Joe, Isaiah", "status": "Out", "reason": "Injury/Illness - Right Hip Contusion"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Jones, Isaac", "status": "Questionable", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Lanier, Chaz", "status": "Out", "reason": "G League - On Assignment"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Okorie, Ebuka", "status": "Out", "reason": "G League - On Assignment"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Detroit Pistons", "player": "Onyenso, Ugonna", "status": "Out", "reason": "G League - Two-Way"},
    {"game_date": "11/14/2026", "game_time": "", "matchup": "DET@MIA", "team": "Miami Heat", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    # 11/15 placeholders (all NOT YET SUBMITTED)
    {"game_date": "11/15/2026", "game_time": "01:00 (ET)", "matchup": "IND@PHI", "team": "Indiana Pacers", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "01:00 (ET)", "matchup": "IND@PHI", "team": "Philadelphia 76ers", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "04:00 (ET)", "matchup": "LAL@PHX", "team": "Los Angeles Lakers", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "", "matchup": "", "team": "Phoenix Suns", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "04:30 (ET)", "matchup": "CHA@LAC", "team": "Charlotte Hornets", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "04:30 (ET)", "matchup": "CHA@LAC", "team": "LA Clippers", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "05:00 (ET)", "matchup": "SAS@UTA", "team": "San Antonio Spurs", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "05:00 (ET)", "matchup": "SAS@UTA", "team": "Utah Jazz", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "06:00 (ET)", "matchup": "DAL@BOS", "team": "Dallas Mavericks", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "06:00 (ET)", "matchup": "DAL@BOS", "team": "Boston Celtics", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "06:00 (ET)", "matchup": "NYK@TOR", "team": "New York Knicks", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "06:00 (ET)", "matchup": "NYK@TOR", "team": "Toronto Raptors", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "07:00 (ET)", "matchup": "HOU@WAS", "team": "Houston Rockets", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/15/2026", "game_time": "07:00 (ET)", "matchup": "HOU@WAS", "team": "Washington Wizards", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "ATL@MIL", "team": "Atlanta Hawks", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/14/2026", "game_time": "08:00 (ET)", "matchup": "ATL@MIL", "team": "Milwaukee Bucks", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/14/2026", "game_time": "09:00 (ET)", "matchup": "OKC@SAC", "team": "Oklahoma City Thunder", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
    {"game_date": "11/14/2026", "game_time": "09:00 (ET)", "matchup": "OKC@SAC", "team": "Sacramento Kings", "player": "", "status": "", "reason": "NOT YET SUBMITTED"},
]

for r in ROWS:
    r["source"] = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
    r["source_url"] = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
    r["verified"] = True
    r["verified_against"] = "official NBA injury report PDF 11/14/26 04:15 AM ET (ak-static.cms.nba.com), re-transcribed 2026-11-14"

player_rows = [r for r in ROWS if r["player"]]
not_submitted = [r for r in ROWS if r["reason"] == "NOT YET SUBMITTED"]
out = {
    "report": "11/14/26 04:15 AM ET",
    "source": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf",
    "index": "https://official.nba.com/nba-injury-report-2026-27-season/",
    "total_rows": len(ROWS),
    "player_rows": len(player_rows),
    "not_yet_submitted_rows": len(not_submitted),
    "note": "Teams file by 5 p.m. local time the day before a game; no official report exists yet for 11/16 or 11/17. Blank cells are printed empty in the PDF and are kept empty - no inference.",
    "verified": True,
    "rows": ROWS,
}
os.makedirs("240bc29b/data", exist_ok=True)
with open("240bc29b/data/injuries.json", "w") as f:
    json.dump(out, f, indent=2)
print("wrote 240bc29b/data/injuries.json:",
      len(ROWS), "rows =", len(player_rows), "player +", len(not_submitted), "not-yet-submitted")
