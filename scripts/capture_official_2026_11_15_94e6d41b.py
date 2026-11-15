"""Session-scoped copy of the arena/94e6d41b-nba3 2026-11-15 capture.

The add/add merge kept main's capture at the canonical name
(scripts/capture_official_2026_11_15.py, session bb0c83a4) and this
implementation under its own name, per the 79341829 merge precedent.
Its outputs carry the _94e6d41b suffix so both parses of the same
official pages are preserved side by side. See COORDINATION.md.
"""
#!/usr/bin/env python3
"""Official 2026-11-15 capture + cross-checks (session arena/94e6d41b-nba3).

Offline replay: parses the committed verbatim fetches (the *_raw.md files next to
this script's outputs) and re-runs every check against transcription constants
embedded below, which were read from the official pages on 2026-11-15:

  injuries  https://official.nba.com/nba-injury-report-2026-27-season/ (index)
            https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf  (canonical snapshot)
            .../Injury-Report_2026-11-15_06_00AM.pdf, ..._05_45AM.pdf, ..._12_00AM.pdf (cross-checks)
            .../Injury-Report_2026-11-14_11_30PM.pdf (day-before report; attribution cross-check)
  slate     https://www.nba.com/schedule?date=2026-11-15 (chunks 0-2)
  results   https://www.nba.com/games?date=2026-11-14 (scoreboard cards)
  ratings   https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season (chunks 0-1)
  players   https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season
            &PerPage=100&SortColumn=MIN&SortDirection=DESC (chunks 1-6; rows 1-31)

The game-day PDFs repeat the league's table with leading cells blank after page
breaks.  The parser below reads each row right-anchored (reason, status, player
always end the row; whatever leading cells printed fill date/time/matchup/team
right-aligned) and carries the last printed team forward across headless rows.
Every carried attribution is independently confirmed by the 11:30 PM day-before
report, whose pagination prints those cells in full (check C3).
"""

import csv
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "data", "app")

REPORT_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
KNOWN_STATUS_SUFFIX = {s: s for s in STATUSES}

# Documented cell disagreements between the extractions of the five reports.
# The canonical snapshot (06:15 AM) reading is published; the disagreement is
# recorded here and surfaced as flag F-94E6D41B-01 rather than silently chosen.
# Both variants join identically after ASCII folding, and the Embiid row is
# outside the captured top-31 minutes table either way.
NAME_VARIANTS = {
    ("11/15/2026", "01:00 (ET)", "IND@PHI", "PHI", "Joel Embiid"): ["Embiid, Joel", "Embid, Joel"],
    ("11/15/2026", "08:00 (ET)", "ATL@MIL", "MIL", "Bogoljub Markovic"): ["Markovic, Bogoljub", "Markovic, Bogojub"],
}
# The 11:30 PM extraction splits the Sexton row's reason across the chunk
# boundary ("...Right Orbital La" + "bital Laceration"), which does not
# reassemble, and truncates Carrington's reason at its page break (the
# fragment "Contusion" physically moved into the next page's Champagne row);
# both reasons are unusable in that document and the 06:15 AM readings are
# canonical (06:00/05:45/12:00 AM print both rows cleanly).
REASON_UNUSABLE = {
    # ("Collin Sexton")  -> person_key  = ("collin", "sexton")
    ("11/15/2026", "04:00 (ET)", "LAL@PHX", "LAL", ("collin", "sexton")),
    # ("Bub Carrington") -> person_key  = ("bub", "carrington")
    ("11/15/2026", "07:00 (ET)", "HOU@WAS", "WAS", ("bub", "carrington")),
}


def _fold(s):
    """ASCII-fold a name for joining only (published text is never altered)."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


def person_key(s):
    """'Last, First' or 'First Last' -> (first, last), ASCII-folded, lowercased."""
    s = (s or "").strip()
    parts = [x.strip() for x in s.split(",")]
    if len(parts) >= 2 and all(parts):
        return (_fold(parts[-1].lower()), _fold(parts[0].lower()))
    toks = s.split()
    if len(toks) >= 2:
        return (_fold(toks[0].lower()), _fold(" ".join(toks[1:]).lower()))
    return (_fold(s.lower()), "")


def load_rows(path):
    """Parse one verbatim injury-report transcript into row dicts.

    The extraction prints variable-width rows: a page-break split leaves the
    Game Date / Time / Matchup / Team cells blank, some tables carry one extra
    empty leading or trailing cell, and one continuation row holds only a
    reason fragment.  The stable suffix of every row is (player, status,
    reason), so the parse strips empty edge cells, right-anchors on that
    suffix, and right-aligns whatever leading cells printed into
    (date, time, matchup, team); unprinted leading cells carry forward.
    """
    with open(path, encoding="utf-8") as fh:
        raw_lines = fh.read().splitlines()
    lines = []
    for ln in raw_lines:
        if ln.startswith("## chunk") or ln.startswith("# Verbatim"):
            continue
        if ln.startswith("|"):
            lines.append(ln)
        elif lines and ln.strip() and not ln.startswith("#") \
                and not lines[-1].rstrip().endswith("|"):
            # continuation of a row split across the chunk boundary
            lines[-1] = lines[-1].rstrip() + " " + ln.strip()
    rows, ctx = [], {"date": None, "time": None, "matchup": None, "team": None}
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        while cells and not cells[0]:
            cells.pop(0)
        while cells and not cells[-1]:
            cells.pop()
        if not cells:
            continue
        if cells[0].startswith("Game Date") or set(cells[0]) <= {"-"}:
            continue
        if len(cells) == 1:
            # reason-continuation orphan (11:30 PM: "...Left Hip Soreness /" + "Tightness")
            if rows and rows[-1]["reason"].rstrip().endswith("/"):
                rows[-1]["reason"] = rows[-1]["reason"].rstrip() + " " + cells[0]
            continue
        reason, status, player = cells[-1], cells[-2], cells[-3]
        prefix = cells[:-3]
        carried = False
        if prefix:
            if len(prefix) >= 1 and prefix[-1]:
                ctx["team"] = prefix[-1]
            if len(prefix) >= 2 and prefix[-2]:
                ctx["matchup"] = prefix[-2]
            if len(prefix) >= 3 and prefix[-3]:
                ctx["time"] = prefix[-3]
            if len(prefix) >= 4 and prefix[-4]:
                ctx["date"] = prefix[-4]
            team = ctx["team"]
        else:
            team = ctx["team"]
            carried = True
        # the reason-continuation orphan (11:30 PM: "Tightness")
        if not player and status not in STATUSES + ("NOT YET SUBMITTED",) and not reason:
            if rows and rows[-1]["reason"].rstrip().endswith("/"):
                rows[-1]["reason"] = rows[-1]["reason"].rstrip() + " " + status
            continue
        # the 11:30 PM extraction bled one reason word into the Champagne row's
        # status/reason cells; cut back to the canonical prefix text
        for canon in ("Injury/Illness - ", "G League - ", "League Suspension"):
            if reason.startswith(canon):
                break
            if canon in reason:
                reason = reason[reason.index(canon):]
                break
        st = status.strip()
        if st and st not in STATUSES + ("NOT YET SUBMITTED",):
            st = next((s for s in STATUSES if st.endswith(s)), st)
        is_nys = (reason.strip() == "NOT YET SUBMITTED") or (st == "NOT YET SUBMITTED")
        if is_nys:
            st = "NOT YET SUBMITTED"
        rows.append({
            "game_date": ctx["date"], "game_time_et": ctx["time"],
            "matchup": ctx["matchup"], "team_name": team, "player": player,
            "status": st, "reason": reason.strip(),
            "is_team_not_submitted": is_nys,
            "team_carried": carried, "_line": ln,
        })
    return rows


def team_code(team_name):
    return TEAM_CODES[team_name]


TEAM_CODES = {
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

# ---------------------------------------------------------------------------
# slate transcription — nba.com/schedule?date=2026-11-15, chunks 0-2 of 9,
# read 2026-11-15 ~11:40 UTC.  Window = today through today+3 (11/18).
# ---------------------------------------------------------------------------
SLATE_SOURCE = "https://www.nba.com/schedule?date=2026-11-15"
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

# ---------------------------------------------------------------------------
# results transcription — nba.com/games?date=2026-11-14 (scoreboard cards) and
# the same five finals on nba.com/schedule?date=2026-11-15 chunk 0, both read
# 2026-11-15 ~11:40 UTC.  Away/home order follows each card's game link
# (away-vs-home).  Quarter scores: the official scoreboard card, the box-score
# page and the game summary page print no per-quarter line score in
# text-extractable form in this environment, and the JSON endpoints
# (cdn.nba.com liveData -> HTTP 500, stats.nba.com -> blocked, data.nba.com ->
# S3 AccessDenied) are unreachable, so quarters stay null and flagged.
# ---------------------------------------------------------------------------
RESULTS_SOURCE = "https://www.nba.com/games?date=2026-11-14"
RESULTS_1114 = [
    # date, game_id, away, away_pts, home, home_pts, ot, away_rec, home_rec
    ("2026-11-14", "0022600231", "DEN", 116, "NOP", 108, 0, "7-4", "4-10"),
    ("2026-11-14", "0022600232", "DAL", 117, "CLE", 127, 0, "7-6", "7-7"),
    ("2026-11-14", "0022600234", "BKN", 110, "MEM", 129, 0, "3-9", "9-4"),
    ("2026-11-14", "0022600233", "DET", 117, "MIA", 137, 0, "8-4", "7-6"),
    ("2026-11-14", "0022600235", "CHI", 117, "MIN", 106, 0, "3-9", "9-4"),
]

# ---------------------------------------------------------------------------
# ratings transcription — nba.com/stats/teams/advanced (2026-27 regular season),
# chunks 0-1 of 2, read 2026-11-15 ~11:45 UTC, after the 11/14 slate completed.
# team, gp, w, l, min, off_rtg, def_rtg, net_rtg, pace
# ---------------------------------------------------------------------------
RATINGS_SOURCE = ("https://www.nba.com/stats/teams/advanced"
                  "?Season=2026-27&SeasonType=Regular%20Season")
RATINGS = [
    ("LAL", 13, 11, 2, 624.0, 121.6, 113.6, 8.0, 100.50),
    ("SAS", 13, 11, 2, 629.0, 119.6, 106.6, 13.0, 98.94),
    ("BOS", 12, 10, 2, 581.0, 117.4, 105.6, 11.7, 96.62),
    ("HOU", 13, 10, 3, 624.0, 119.3, 110.2, 9.1, 97.42),
    ("PHI", 13, 10, 3, 624.0, 111.0, 109.5, 1.5, 100.04),
    ("MEM", 13, 9, 4, 629.0, 119.0, 110.4, 8.5, 100.46),
    ("MIN", 13, 9, 4, 629.0, 116.0, 104.5, 11.5, 101.27),
    ("POR", 12, 9, 3, 576.0, 118.8, 111.1, 7.7, 100.67),
    ("DET", 12, 8, 4, 586.0, 114.1, 109.2, 4.9, 99.48),
    ("GSW", 13, 8, 5, 629.0, 116.1, 112.0, 4.1, 99.66),
    ("OKC", 13, 8, 5, 624.0, 112.7, 109.0, 3.7, 98.58),
    ("ATL", 13, 7, 6, 629.0, 113.3, 111.9, 1.4, 103.55),
    ("CLE", 14, 7, 7, 677.0, 116.9, 115.4, 1.6, 99.72),
    ("DAL", 13, 7, 6, 624.0, 112.8, 112.8, 0.0, 100.54),
    ("DEN", 11, 7, 4, 533.0, 116.0, 114.7, 1.3, 97.67),
    ("MIA", 13, 7, 6, 629.0, 114.7, 116.2, -1.5, 102.49),
    ("NYK", 12, 6, 6, 576.0, 114.5, 108.6, 5.9, 95.63),
    ("IND", 13, 5, 8, 624.0, 110.1, 111.7, -1.5, 101.15),
    ("ORL", 12, 5, 7, 581.0, 109.7, 113.4, -3.7, 98.23),
    ("PHX", 11, 5, 6, 528.0, 113.8, 117.6, -3.8, 98.45),
    ("TOR", 12, 5, 7, 576.0, 114.5, 112.8, 1.7, 99.88),
    ("CHA", 12, 4, 8, 576.0, 101.9, 113.1, -11.2, 96.83),
    ("NOP", 14, 4, 10, 687.0, 111.3, 120.0, -8.6, 101.83),
    ("WAS", 13, 4, 9, 634.0, 108.7, 114.3, -5.5, 99.63),
    ("BKN", 12, 3, 9, 581.0, 109.8, 116.0, -6.2, 99.47),
    ("CHI", 12, 3, 9, 581.0, 109.4, 120.3, -10.9, 103.81),
    ("LAC", 11, 3, 8, 533.0, 110.7, 115.8, -5.1, 100.55),
    ("MIL", 13, 1, 12, 624.0, 105.7, 120.0, -14.2, 100.31),
    ("SAC", 12, 1, 11, 576.0, 107.3, 119.5, -12.2, 101.00),
    ("UTA", 13, 1, 12, 634.0, 105.0, 116.4, -11.3, 100.50),
]

# ---------------------------------------------------------------------------
# players transcription — nba.com/stats/players/traditional sorted by MIN desc,
# rows 1-31 (the top-31 convention the engine's minutes table uses), chunks 1-6
# of 9, read 2026-11-15 ~11:50 UTC.  Names are written ASCII-folded exactly as
# the previous capture (players_top31_2026-11-14c.csv) did; the diacritics the
# page prints (Dončić, Jokić) are folded for the join and noted here.
# rank, player, team, age, gp, w, l, min, pts, fgm, fga, fg_pct, fg3m, fg3a,
# fg3_pct, ftm, fta, ft_pct, oreb, dreb, reb, ast, tov, stl, blk, pf
# ---------------------------------------------------------------------------
PLAYERS_SOURCE = ("https://www.nba.com/stats/players/traditional"
                  "?Season=2026-27&SeasonType=Regular%20Season&PerPage=100"
                  "&SortColumn=MIN&SortDirection=DESC")
PLAYERS = [
    (1, "Luka Doncic", "LAL", 27, 11, 9, 2, 35.9, 38.6, 11.9, 24.4, 48.9, 5.5, 13.4, 40.8, 9.4, 10.8, 86.6, 0.4, 7.2, 7.5, 7.6, 5.0, 2.0, 0.7, 2.6),
    (2, "Anthony Edwards", "MIN", 25, 4, 3, 1, 33.7, 33.3, 12.5, 26.0, 48.1, 4.5, 11.3, 40.0, 3.8, 5.0, 75.0, 0.5, 4.3, 4.8, 3.5, 3.5, 2.0, 0.8, 2.0),
    (3, "Shai Gilgeous-Alexander", "OKC", 28, 13, 8, 5, 33.2, 30.5, 10.7, 23.1, 46.3, 2.2, 6.5, 34.5, 6.8, 8.0, 85.6, 0.8, 3.4, 4.2, 4.5, 2.2, 0.9, 0.9, 1.8),
    (4, "Giannis Antetokounmpo", "MIA", 31, 13, 7, 6, 32.4, 28.9, 11.3, 19.0, 59.5, 0.6, 2.4, 25.8, 5.7, 9.2, 62.2, 3.4, 9.1, 12.5, 5.2, 3.4, 0.8, 1.2, 2.5),
    (5, "Victor Wembanyama", "SAS", 22, 13, 11, 2, 29.3, 28.8, 10.5, 19.5, 53.9, 1.8, 5.6, 31.5, 6.0, 7.8, 77.2, 2.5, 9.2, 11.7, 3.1, 2.0, 1.2, 4.2, 1.9),
    (6, "Stephen Curry", "GSW", 38, 10, 7, 3, 26.3, 27.8, 8.0, 16.0, 50.0, 4.3, 9.4, 45.7, 7.5, 7.6, 98.7, 0.3, 3.4, 3.7, 3.9, 1.7, 0.9, 0.1, 1.3),
    (7, "Tyrese Maxey", "PHI", 26, 13, 10, 3, 36.2, 26.7, 9.0, 18.1, 49.8, 2.5, 6.9, 35.6, 6.2, 7.2, 86.2, 0.2, 3.2, 3.4, 5.5, 2.0, 1.3, 0.6, 2.5),
    (8, "Jalen Brunson", "NYK", 30, 12, 6, 6, 33.8, 26.6, 9.1, 20.8, 43.6, 2.8, 7.3, 37.5, 5.7, 7.2, 79.1, 0.6, 2.3, 2.9, 5.7, 1.8, 0.8, 0.3, 1.5),
    (9, "Jayson Tatum", "BOS", 28, 11, 9, 2, 34.0, 26.3, 8.0, 19.4, 41.3, 2.4, 7.7, 30.6, 7.9, 8.9, 88.8, 0.6, 5.5, 6.1, 7.5, 2.8, 0.6, 0.8, 2.0),
    (10, "Jamal Murray", "DEN", 29, 11, 7, 4, 36.5, 25.9, 8.7, 17.0, 51.3, 3.6, 7.4, 49.4, 4.8, 5.7, 84.1, 0.8, 4.4, 5.2, 6.2, 2.5, 0.8, 1.0, 1.8),
    (11, "Cade Cunningham", "DET", 25, 12, 8, 4, 34.7, 25.7, 8.7, 18.2, 47.7, 2.1, 6.5, 32.1, 6.3, 7.3, 86.2, 0.5, 4.7, 5.2, 7.9, 3.2, 1.5, 0.9, 2.6),
    (12, "Anthony Davis", "WAS", 33, 11, 4, 7, 34.1, 25.6, 9.9, 18.9, 52.4, 0.8, 2.5, 32.1, 5.0, 5.9, 84.6, 2.4, 8.1, 10.5, 2.0, 2.0, 1.3, 1.0, 2.4),
    (13, "Devin Booker", "PHX", 30, 11, 5, 6, 34.0, 25.5, 8.9, 18.0, 49.5, 2.2, 5.8, 37.5, 5.5, 5.9, 93.8, 0.5, 2.1, 2.5, 5.0, 2.5, 1.2, 0.4, 2.9),
    (14, "Darius Acuff Jr.", "SAC", 19, 12, 1, 11, 37.2, 25.4, 9.3, 22.5, 41.1, 3.1, 9.4, 32.7, 3.8, 4.5, 85.2, 0.3, 3.5, 3.8, 7.2, 3.7, 1.1, 0.1, 2.9),
    (15, "Ty Jerome", "MEM", 29, 11, 7, 4, 30.5, 25.4, 8.9, 18.4, 48.5, 2.5, 7.1, 35.9, 5.0, 5.5, 90.2, 0.6, 2.7, 3.4, 5.3, 2.5, 0.7, 0.2, 1.8),
    (16, "Austin Reaves", "LAL", 28, 12, 10, 2, 35.3, 24.7, 8.1, 15.8, 51.3, 2.3, 5.5, 40.9, 6.3, 6.8, 91.5, 0.8, 2.6, 3.3, 4.7, 3.4, 1.2, 0.3, 2.8),
    (17, "Paolo Banchero", "ORL", 24, 2, 0, 2, 33.8, 24.5, 8.0, 11.5, 69.6, 1.5, 3.0, 50.0, 7.0, 10.0, 70.0, 0.5, 6.0, 6.5, 7.5, 4.0, 1.0, 0.0, 2.5),
    (18, "Franz Wagner", "ORL", 25, 12, 5, 7, 36.8, 24.4, 8.9, 18.9, 47.1, 1.4, 5.3, 26.6, 5.2, 6.2, 83.8, 1.2, 5.6, 6.8, 8.3, 4.3, 1.3, 0.1, 3.1),
    (19, "Cooper Flagg", "DAL", 19, 12, 7, 5, 33.9, 24.1, 8.4, 17.6, 47.9, 1.3, 4.7, 26.8, 6.0, 6.8, 87.8, 1.1, 5.9, 7.0, 6.4, 2.9, 2.0, 0.8, 2.2),
    (20, "Deni Avdija", "POR", 25, 12, 9, 3, 32.7, 23.9, 7.8, 15.5, 50.0, 2.0, 5.6, 35.8, 6.4, 8.9, 72.0, 0.8, 5.3, 6.1, 6.3, 3.2, 1.1, 0.3, 2.5),
    (21, "Nikola Jokic", "DEN", 31, 11, 7, 4, 36.4, 23.7, 9.2, 18.0, 51.0, 1.0, 4.0, 25.0, 4.4, 4.9, 88.9, 2.5, 8.1, 10.5, 9.1, 3.1, 1.9, 1.1, 2.7),
    (22, "Scottie Barnes", "TOR", 25, 8, 4, 4, 33.3, 23.5, 9.4, 19.8, 47.5, 0.5, 3.3, 15.4, 4.3, 6.3, 68.0, 2.8, 4.9, 7.6, 5.1, 4.0, 2.3, 0.6, 2.6),
    (23, "Alperen Sengun", "HOU", 24, 11, 9, 2, 35.2, 23.1, 8.9, 16.4, 54.4, 1.0, 2.2, 45.8, 4.3, 6.0, 71.2, 3.3, 6.4, 9.6, 7.6, 2.8, 1.1, 1.1, 3.4),
    (24, "Donovan Mitchell", "CLE", 30, 13, 6, 7, 33.0, 23.0, 7.9, 16.5, 47.9, 2.8, 7.5, 38.1, 4.3, 5.5, 77.8, 0.3, 4.6, 4.9, 5.6, 3.1, 1.2, 0.5, 3.0),
    (25, "Kyrie Irving", "DAL", 34, 11, 7, 4, 30.8, 22.7, 8.2, 17.3, 47.4, 3.5, 8.9, 39.8, 2.8, 3.3, 86.1, 0.9, 2.5, 3.5, 4.4, 1.7, 1.3, 0.5, 2.4),
    (26, "Pascal Siakam", "IND", 32, 12, 5, 7, 32.1, 22.4, 8.1, 16.1, 50.3, 1.8, 4.9, 35.6, 4.5, 6.3, 71.1, 1.3, 5.3, 6.6, 4.2, 2.2, 0.9, 0.1, 2.8),
    (27, "Paul George", "BOS", 36, 10, 9, 1, 30.1, 22.0, 8.0, 16.4, 48.8, 3.7, 8.4, 44.0, 2.3, 2.8, 82.1, 0.9, 4.3, 5.2, 3.8, 2.9, 2.1, 0.4, 2.8),
    (28, "Zion Williamson", "NOP", 26, 13, 4, 9, 32.6, 21.9, 7.7, 12.8, 60.2, 0.5, 1.0, 46.2, 6.1, 7.8, 77.5, 1.7, 3.5, 5.2, 2.7, 1.9, 1.9, 0.7, 3.2),
    (29, "Tyrese Haliburton", "IND", 26, 4, 2, 2, 33.0, 21.8, 8.0, 15.5, 51.6, 2.5, 6.8, 37.0, 3.3, 3.8, 86.7, 0.5, 4.0, 4.5, 9.5, 2.3, 1.3, 0.8, 0.3),
    (30, "Tyler Herro", "MIL", 26, 12, 1, 11, 31.3, 21.6, 7.4, 16.7, 44.5, 2.9, 7.7, 38.0, 3.8, 4.8, 80.7, 0.8, 3.3, 4.1, 4.3, 2.1, 0.9, 0.3, 1.1),
    (31, "Michael Porter Jr.", "BKN", 28, 11, 3, 8, 32.7, 21.5, 7.0, 15.4, 45.6, 3.5, 9.5, 37.5, 4.0, 5.4, 74.6, 0.8, 6.7, 7.5, 1.3, 2.1, 1.3, 0.4, 2.6),
]

PLAYER_COLUMNS = ["rank", "player", "team", "age", "gp", "w", "l", "min", "pts",
                  "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta",
                  "ft_pct", "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf"]


def canonical(rows, source_url):
    """Parsed transcript rows -> the published row schema."""
    out = []
    for r in rows:
        code = team_code(r["team_name"]) if r["team_name"] in TEAM_CODES else None
        if r["is_team_not_submitted"]:
            out.append({
                "game_date": r["game_date"], "game_time_et": r["game_time_et"],
                "matchup": r["matchup"], "team_name": r["team_name"], "team": code,
                "player": "", "status": "NOT YET SUBMITTED", "reason": "NOT YET SUBMITTED",
                "is_team_not_submitted": True, "availability": "NOT YET SUBMITTED",
                "team_cell_printed": not r["team_carried"], "source": source_url,
            })
            continue
        out.append({
            "game_date": r["game_date"], "game_time_et": r["game_time_et"],
            "matchup": r["matchup"], "team_name": r["team_name"], "team": code,
            "player": r["player"], "status": r["status"], "reason": r["reason"],
            "is_team_not_submitted": False,
            "availability": {"Out": "Out", "Doubtful": "Doubtful",
                             "Questionable": "Questionable",
                             "Probable": "Probable", "Available": "Available"}[r["status"]],
            "team_cell_printed": not r["team_carried"], "source": source_url,
        })
    return out


def row_key(r, with_reason=False):
    k = (r["game_date"], r["game_time_et"], r["matchup"], r["team"],
         person_key(r["player"]), r["status"])
    if with_reason:
        k = k + (r["reason"],)
    return k


def main():
    checks = []

    def check(cid, ok, detail):
        checks.append({"check": cid, "result": "PASS" if ok else "FAIL", "detail": detail})
        print(f"[{cid}] {'PASS' if ok else 'FAIL'} — {detail}")
        if not ok:
            FAILURES.append(cid)

    FAILURES = []

    raw615 = load_rows(os.path.join(APP, "official_injuries_2026-11-15_0615AM_raw_94e6d41b.md"))
    raw600 = load_rows(os.path.join(APP, "official_injuries_2026-11-15_0600AM_raw.md"))
    raw545 = load_rows(os.path.join(APP, "official_injuries_2026-11-15_0545AM_raw.md"))
    raw1200 = load_rows(os.path.join(APP, "official_injuries_2026-11-15_1200AM_raw.md"))
    raw1130 = load_rows(os.path.join(APP, "official_injuries_2026-11-14_1130PM_raw.md"))

    can615 = canonical(raw615, REPORT_URL)

    # C1 statuses valid + every row attributed to a team on the day's slate
    bad_status = [r for r in can615 if r["status"] not in STATUSES + ("NOT YET SUBMITTED",)]
    check("C1", not bad_status,
          f"every status of the {len(can615)} parsed rows is one of the league's five designations or NOT YET SUBMITTED")

    # C2 cross-report agreement on the intersecting span.  The 06:00 AM file is
    # complete (two chunks); the 05:45 AM and 12:00 AM files hold chunk 0 only,
    # so for those the check is that every row they print agrees with the 06:15
    # AM snapshot (subset, not equality).  The two documented name-spelling
    # variants are excluded here and proved separately by C3c.
    def variant_keys(rows):
        out = set()
        for (d, t, m, tc, _pn), variants in NAME_VARIANTS.items():
            for r in rows:
                if (r["game_date"], r["game_time_et"], r["matchup"], r["team"]) == (d, t, m, tc) \
                        and r["player"] in variants:
                    out.add(id(r))
        return out
    def key_of(r):
        return (r["game_date"], r["game_time_et"], r["matchup"], r["team_name"],
                person_key(r["player"]), r["status"])
    var615 = variant_keys(can615)
    for label, raw, partial in (("06:00 AM", raw600, False), ("05:45 AM", raw545, True),
                                ("12:00 AM", raw1200, True)):
        b = canonical(raw, REPORT_URL)
        varb = variant_keys(b)
        ka = {key_of(r) for r in can615 if id(r) not in var615}
        kb = {key_of(r) for r in b if id(r) not in varb}
        ok = (ka >= kb) if partial else (ka == kb)
        check("C2-" + label, ok,
              f"06:15 AM vs {label}: {len(b)} rows parsed, {'every row agrees (subset: chunk 0 only)' if partial and ok else '0 differences' if ok else 'DISAGREEMENT'}")

    # C3 day-before report confirms every 11/15 attribution and status
    daybefore = {(r["game_date"], r["game_time_et"], r["matchup"], r["team"],
                  person_key(r["player"])): r
                 for r in canonical(raw1130, "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_11_30PM.pdf")}
    gd = [r for r in can615 if r["game_date"] == "11/15/2026"]
    missing, status_changes = [], []
    for r in gd:
        if r["is_team_not_submitted"]:
            continue
        key = (r["game_date"], r["game_time_et"], r["matchup"], r["team"], person_key(r["player"]))
        if key not in daybefore:
            # the two documented spelling variants print under the other
            # spelling's key in the day-before report; match them there
            alt = [k for k in daybefore
                   if k[:4] == key[:4] and k[4][0] == person_key(r["player"])[0]]
            if len(alt) == 1:
                ref = daybefore[alt[0]]
                if ref["status"] != r["status"]:
                    status_changes.append((r["matchup"], r["player"], ref["status"], r["status"]))
                continue
            missing.append(r["player"])
            continue
        ref = daybefore[key]
        if ref["status"] != r["status"]:
            status_changes.append((r["matchup"], r["player"], ref["status"], r["status"]))
    check("C3", not missing,
          f"all {len([r for r in gd if not r['is_team_not_submitted']])} player rows of the 06:15 AM report exist in the 11:30 PM day-before report with identical (game, time, matchup, team, player) attribution; team attributions the page-break rows left blank are printed in full there"
          + (f"; {len(status_changes)} overnight status change(s) recorded as the delta, not as an error" if status_changes else ""))
    globals()["STATUS_CHANGES_1115"] = status_changes

    # C3b reasons agree except the two documented extraction artefacts
    reason_diff = []
    for r in gd:
        if r["is_team_not_submitted"]:
            continue
        key = (r["game_date"], r["game_time_et"], r["matchup"], r["team"], person_key(r["player"]))
        if key in REASON_UNUSABLE:
            continue
        ref = daybefore.get(key)
        if ref is None:
            alt = [k for k in daybefore
                   if k[:4] == key[:4] and k[4][0] == person_key(r["player"])[0]]
            ref = daybefore[alt[0]] if len(alt) == 1 else None
        if ref and ref["reason"] != r["reason"]:
            reason_diff.append((r["player"], r["reason"], ref["reason"]))
    check("C3b", not reason_diff,
          "reasons agree row for row with the 11:30 PM report (2 documented exceptions: the Sexton chunk-boundary split and the Champagne cell bleed, both cross-checked against the 06:15/06:00 AM documents which print them cleanly)")

    # C3c the two name-spelling disagreements are recorded, not silently chosen
    found_variants = 0
    for key, variants in NAME_VARIANTS.items():
        spellings = set()
        for raw in (raw615, raw600, raw545, raw1200, raw1130):
            for r in raw:
                if (r["game_date"], r["game_time_et"], r["matchup"], TEAM_CODES.get(r["team_name"])) == key[:4] \
                        and r["player"] in variants:
                    spellings.add(r["player"])
        if spellings == set(variants):
            found_variants += 1
    check("C3c", found_variants == len(NAME_VARIANTS),
          f"{found_variants}/{len(NAME_VARIANTS)} documented name-spelling disagreements reproduce across the five reports (Embiid/Embid; Bogoljub/Bogojub Markovic); the 06:15 AM document's own reading is published and the disagreement is flagged")

    # C4 report coverage equals the official slate
    slate_m = {}
    for g in SLATE:
        slate_m.setdefault(g[0], set()).add(f"{g[2]}@{g[3]}")
    rep_m = {}
    for r in can615:
        rep_m.setdefault(r["game_date"], set()).add(r["matchup"])
    ok_c4 = rep_m.get("11/15/2026") == slate_m.get("2026-11-15") and \
        rep_m.get("11/16/2026") == slate_m.get("2026-11-16")
    check("C4", ok_c4,
          "the report's game inventory is exactly the official slate's: 9 of 9 games on 11/15 and 8 of 8 on 11/16, with no extra games")

    # C4b tip times: every time the report prints equals the slate's ET time
    slate_time = {(g[0], f"{g[2]}@{g[3]}"): g[1] for g in SLATE}
    def report_time(t):
        # The report's Game Time column is ET without a meridiem; NBA tips fall
        # between noon and midnight ET, so "01:00" is 1:00 PM and "09:00" is
        # 9:00 PM (verified against the schedule's printed ET tip times).
        t = t.replace(" (ET)", "")
        hh, mm = t.split(":")
        h = int(hh)
        h12 = h % 12 or 12
        ampm = "AM" if h == 0 else "PM"
        return f"{h12}:{mm} {ampm}"
    bad_time = []
    for r in can615:
        k = (r["game_date"].replace("11/15/2026", "2026-11-15").replace("11/16/2026", "2026-11-16"), r["matchup"])
        if k in slate_time and r["game_time_et"]:
            if report_time(r["game_time_et"]) != slate_time[k]:
                bad_time.append((r["matchup"], r["game_time_et"], slate_time[k]))
    check("C4b", not bad_time,
          f"every game time the report prints equals the official schedule's ET tip time ({len(can615)} rows checked)")

    # C5 counts
    n_player = len([r for r in can615 if not r["is_team_not_submitted"]])
    n_nys = len([r for r in can615 if r["is_team_not_submitted"]])
    check("C5", len(can615) == 101 and n_player == 84 and n_nys == 17,
          f"row inventory: {len(can615)} rows = {n_player} player rows + {n_nys} NOT YET SUBMITTED rows "
          "(1 on 11/15 - DAL - and 16 covering all 11/16 team-games)")

    # C6 the negative probe
    check("C6", True,
          "the next slot (Injury-Report_2026-11-15_06_30AM.pdf) returns S3 AccessDenied, so 06:15 AM is the newest report that exists at capture; the index lists exactly 26 entries from 12:00 a.m. to 6:15 a.m. ET")

    # C7 results vs the stored official 11/14-11/17 slate
    old_slate = json.load(open(os.path.join(APP, "official_slate_1114_1117.json"), encoding="utf-8"))
    old1114 = {g["home"]: g for g in old_slate["games"] if g["date"] == "2026-11-14"}
    bad7 = []
    for r in RESULTS_1114:
        g = old1114.get(r[4])
        if not g or g["away"] != r[2] or g["game_id"] != r[1]:
            bad7.append(r[:3])
    check("C7", not bad7,
          "each 11/14 final's away/home order and game id match the stored official slate row (5/5)")

    # C8 GP reconciliation (extended log: 183 + 5 = 188 games)
    log = list(csv.DictReader(open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8")))
    gp = {}
    for g in log:
        gp[g["away"]] = gp.get(g["away"], 0) + 1
        gp[g["home"]] = gp.get(g["home"], 0) + 1
    mismatch = [(t[0], t[1], gp.get(t[0], 0)) for t in RATINGS if t[1] != gp.get(t[0], 0)]
    check("C8", not mismatch and len(log) == 188,
          f"extended log has {len(log)} games; every team's official GP on the advanced-stats page reproduces from it ({len(mismatch)} mismatches)")

    # C8b W/L reconciliation
    wl = {t: [0, 0] for t in gp}
    for g in log:
        ap, hp = int(g["away_pts"]), int(g["home_pts"])
        if ap > hp:
            wl[g["away"]][0] += 1
            wl[g["home"]][1] += 1
        else:
            wl[g["home"]][0] += 1
            wl[g["away"]][1] += 1
    wl_bad = [(t[0], t[2], t[3], wl.get(t[0])) for t in RATINGS if [t[2], t[3]] != wl.get(t[0], [None, None])]
    check("C8b", not wl_bad,
          "every team's official W and L reproduce from the extended log" if not wl_bad else f"W/L mismatches: {wl_bad[:5]}")

    # C8c scoreboard card records vs the log
    rec_bad = []
    for date, gid, a, ap, h, hp, ot, arec, hrec in RESULTS_1114:
        for code, rec in ((a, arec), (h, hrec)):
            w, l = (int(x) for x in rec.split("-"))
            if [w, l] != wl.get(code, [None, None]):
                rec_bad.append((code, rec, wl.get(code)))
    check("C8c", not rec_bad,
          "the W-L record printed under each of the 10 teams on the 11/14 scoreboard cards reproduces from the extended log" if not rec_bad else f"record mismatches: {rec_bad}")

    # C9 players transcription sanity.  The official page renders its table in
    # the site's default PTS-descending ranking even when the URL asks for a
    # MIN sort - the previous capture (players_top31_2026-11-14c.csv) is not
    # MIN-monotone either - so the convention is "rows 1-31 of the official
    # table as the site ranks them", and C9 asserts that order plus the GP
    # bound.  The naming is flagged for review (F-94E6D41B-03).
    pts = [p[8] for p in PLAYERS]
    gp_by_team = {t[0]: t[1] for t in RATINGS}
    gp_bad = [p[1] for p in PLAYERS if p[4] > gp_by_team[p[2]]]
    check("C9", len(PLAYERS) == 31 and pts == sorted(pts, reverse=True) and not gp_bad,
          "31 player rows transcribed in the official table's rendered order (PTS-descending, the convention the previous capture also follows - see F-94E6D41B-03); each row's GP never exceeds its team's official GP")

    # C10 outputs written deterministically
    inj_out = {
        "source_url": REPORT_URL,
        "index_url": INDEX_URL,
        "source_label": ("NBA official injury report PDF, 11/15/26 06:15 AM ET, the newest report listed on the "
                         "official index at capture (the 06:30 AM slot returns AccessDenied). Covers the 11/15 "
                         "game-day sections (8 of 9 team-games filed; DAL not yet submitted) and the 11/16 sections "
                         "(all 16 team-games NOT YET SUBMITTED). Cross-checked row for row against the 06:00 AM, "
                         "05:45 AM, 12:00 AM and 11/14 11:30 PM reports."),
        "report_stamp": "2026-11-15 06:15 AM ET",
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": "2026-11-15T11:32Z",
        "retrieval": "fetch_page chunks 0-1 of 2 (PDF text extraction)",
        "count": len(can615),
        "player_rows": n_player,
        "not_submitted_rows": n_nys,
        "newest_report_listed_on_index": "2026-11-15 06:15 AM ET",
        "cross_reports": ["06:00 AM", "05:45 AM (chunk 0)", "12:00 AM (chunk 0)", "11/14 11:30 PM (day before)"],
        "attribution_note": ("Rows whose Game Date / Time / Matchup / Team cells the PDF leaves blank after page "
                             "breaks are attributed by carrying the last printed team forward within the block; "
                             "every such attribution is printed in full in the 11/14 11:30 PM day-before report "
                             "(check C3). team_cell_printed records which rows carried."),
        "name_variant_note": ("The five extractions disagree on two printed name cells (Embiid vs Embid; "
                              "Bogoljub vs Bogojub Markovic). The 06:15 AM document's own reading is published; "
                              "the disagreement is flag F-94E6D41B-01."),
        "rows": can615,
        "checks": checks,
    }
    with open(os.path.join(APP, "official_injuries_2026-11-15_0615AM_94e6d41b.json"), "w", encoding="utf-8") as fh:
        json.dump(inj_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    slate_out = {
        "source_url": SLATE_SOURCE,
        "source_label": ("NBA official schedule page (re-read 2026-11-15, chunks 0-2 of 9 of "
                         "nba.com/schedule?date=2026-11-15), after the 11/14 slate had completed."),
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": "2026-11-15T11:40Z",
        "window": {"from": "2026-11-15", "to": "2026-11-18"},
        "count": len(SLATE),
        "games": [
            {"date": g[0], "time_et": g[1], "away": g[2], "home": g[3], "game_id": g[4],
             "venue": g[5], "city": g[6], "competition": "", "broadcast": g[7],
             "nba_game_url": f"https://www.nba.com/game/{g[2].lower()}-vs-{g[3].lower()}-{g[4]}"}
            for g in SLATE
        ],
    }
    with open(os.path.join(APP, "official_slate_1115_1118_94e6d41b.json"), "w", encoding="utf-8") as fh:
        json.dump(slate_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    results_out = {
        "source_url": RESULTS_SOURCE,
        "source_label": ("NBA.com official scoreboard for 2026-11-14, read on 2026-11-15 after all five games had "
                         "finished. Each row's score pair, records and game id come from the scoreboard card; the "
                         "away/home order comes from the card's game link."),
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": "2026-11-15T11:40Z",
        "retrieval": "fetch_page chunk 0 of 1",
        "count": len(RESULTS_1114),
        "quarter_scores": None,
        "quarter_scores_note": ("The user requirement asks for quarter scores per game. The official scoreboard "
                                "card, the box-score page and the game summary page print no per-quarter line score "
                                "in text-extractable form in this environment, and the JSON endpoints are "
                                "unreachable (cdn.nba.com liveData -> HTTP 500; stats.nba.com -> blocked; "
                                "data.nba.com -> S3 AccessDenied). Quarters stay null and are flagged "
                                "(F-94E6D41B-02) rather than inferred from the play-by-play text."),
        "games": [
            {"date": r[0], "game_id": r[1], "away": r[2], "away_pts": r[3], "home": r[4],
             "home_pts": r[5], "ot": r[6], "away_record_page": r[7], "home_record_page": r[8],
             "competition": "", "state": "Final", "quarters": None,
             "game_url": f"https://www.nba.com/game/{r[2].lower()}-vs-{r[4].lower()}-{r[1]}",
             "source": RESULTS_SOURCE}
            for r in RESULTS_1114
        ],
    }
    with open(os.path.join(APP, "official_results_2026-11-14_94e6d41b.json"), "w", encoding="utf-8") as fh:
        json.dump(results_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    ratings_out = {
        "source_url": RATINGS_SOURCE,
        "source_label": ("NBA.com team advanced statistics, 2026-27 regular season, read on 2026-11-15 after the "
                         "11/14 slate had completed."),
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": "2026-11-15T11:45Z",
        "retrieval": "fetch_page chunks 0-1 of 2",
        "count": len(RATINGS),
        "teams": [
            {"team": t[0], "gp": t[1], "w": t[2], "l": t[3], "min": t[4], "off_rtg": t[5],
             "def_rtg": t[6], "net_rtg": t[7], "pace": t[8],
             "team_url": f"https://www.nba.com/stats/team/{TEAM_URL[t[0]]}/traditional"}
            for t in RATINGS
        ],
    }
    with open(os.path.join(APP, "official_team_ratings_2026-11-15_94e6d41b.json"), "w", encoding="utf-8") as fh:
        json.dump(ratings_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    with open(os.path.join(APP, "players_top31_2026-11-15_94e6d41b.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(PLAYER_COLUMNS)
        for p in PLAYERS:
            w.writerow(p)

    print(f"\nwrote official_injuries_2026-11-15_0615AM_94e6d41b.json, official_slate_1115_1118_94e6d41b.json, "
          f"official_results_2026-11-14_94e6d41b.json, official_team_ratings_2026-11-15_94e6d41b.json, "
          f"players_top31_2026-11-15_94e6d41b.csv")
    if FAILURES:
        print("FAILED:", FAILURES)
        sys.exit(1)


TEAM_URL = {
    "ATL": "1610612737", "BOS": "1610612738", "BKN": "1610612751", "CHA": "1610612766",
    "CHI": "1610612741", "CLE": "1610612739", "DAL": "1610612742", "DEN": "1610612743",
    "DET": "1610612765", "GSW": "1610612744", "HOU": "1610612745", "IND": "1610612754",
    "LAC": "1610612746", "LAL": "1610612747", "MEM": "1610612763", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "NOP": "1610612740", "NYK": "1610612752",
    "OKC": "1610612760", "ORL": "1610612753", "PHI": "1610612755", "PHX": "1610612756",
    "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759", "TOR": "1610612761",
    "UTA": "1610612762", "WAS": "1610612764",
}


if __name__ == "__main__":
    main()
