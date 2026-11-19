#!/usr/bin/env python3
"""Official team-stat capture for the 2026-11-19 round (session arena/b27118c3-nba3).

The brief asks for the three official team-stat pages to be re-read every round. This file holds
the numbers exactly as the pages printed them, plus the arithmetic that has to hold if a digit was
mistyped. Nothing here is computed into a stored field: every stored value is a printed value, and
the checks below only *compare* printed values against each other.

Read (fetch_page, 2026-11-19, UTC):
  advanced    https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season
              (30 rows, printed "30 Rows ... of 1"; returned in two chunks)
  traditional https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season
  opponent    https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season

Chunk-boundary reads: the rendered tables split rows across page chunks, so LAL/PHI (traditional)
were re-read on the same page filtered by TeamID:
  https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season&TeamID=1610612747
  https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season&TeamID=1610612755
  https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season&TeamID=1610612759
Each single-team row printed the same 26 fields in the same order as the full table, and the SAS
row agrees field-for-field with the fragment of it that survives in the full-table chunk.

Run:  python3 scripts/team_stats_b27118c3.py            # validate + write captures + promote advanced
      python3 scripts/team_stats_b27118c3.py --check    # validate + diff against committed files
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUND = ROOT / "data" / "rounds" / "2026-11-19-b27118c3"
CAPTURES = ROUND / "captures"
ROUND_JSON = ROUND / "team_stats_2026-11-19.json"
LIVE = ROOT / "data" / "live" / "team_stats_advanced.json"

RETRIEVED_UTC = "2026-11-19T08:20Z"
URL_ADV = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
URL_TRAD = "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"
URL_OPP = "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season"

# Field order, copied from the printed header of each page.
ADV_FIELDS = ["gp", "w", "l", "min", "off_rtg", "def_rtg", "net_rtg", "ast_pct", "ast_to",
              "ast_ratio", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct", "efg_pct", "ts_pct",
              "pace", "pie", "poss"]
TRAD_FIELDS = ["gp", "w", "l", "win_pct", "min", "pts", "fgm", "fga", "fg_pct", "fg3m", "fg3a",
               "fg3_pct", "ftm", "fta", "ft_pct", "oreb", "dreb", "reb", "ast", "tov", "stl",
               "blk", "blka", "pf", "pfd", "plus_minus"]
OPP_FIELDS = ["gp", "w", "l", "min", "opp_fgm", "opp_fga", "opp_fg_pct", "opp_fg3m", "opp_fg3a",
              "opp_fg3_pct", "opp_ftm", "opp_fta", "opp_ft_pct", "opp_oreb", "opp_dreb",
              "opp_reb", "opp_ast", "opp_tov", "opp_stl", "opp_blk", "opp_blka", "opp_pf",
              "opp_pfd", "opp_pts", "plus_minus"]

# ---------------------------------------------------------------------------------------------
# ADVANCED — 30 rows, every value printed by the page.
ADV = """\
LAL 16 13 3 773.0 119.8 113.2 6.7 58.8 1.46 17.3 33.6 65.0 49.8 16.5 57.2 61.5 100.35 53.0 1614
PHI 16 13 3 768.0 114.5 111.8 2.7 64.7 2.08 18.7 28.4 72.0 50.3 12.6 53.4 57.7 99.88 51.4 1600
HOU 16 12 4 768.0 121.1 112.1 9.0 65.4 1.89 19.4 36.7 68.7 53.2 15.0 55.6 59.7 97.41 55.3 1558
SAS 15 12 3 725.0 118.1 107.0 11.1 65.6 2.23 19.4 33.5 71.3 52.5 12.6 53.0 57.1 98.35 56.0 1487
BOS 15 11 4 725.0 117.0 106.0 11.0 66.7 1.85 19.1 32.9 67.7 50.3 14.9 54.6 57.9 96.76 54.7 1460
MEM 15 11 4 725.0 120.6 111.9 8.7 67.6 1.82 19.8 34.2 69.8 52.7 15.7 56.9 61.1 100.27 54.3 1516
MIN 15 11 4 725.0 114.5 104.0 10.5 60.0 1.58 17.5 34.7 69.3 52.5 15.8 54.8 57.4 101.23 55.0 1528
DET 14 10 4 682.0 114.9 108.9 6.0 67.9 1.97 19.6 30.0 66.6 48.6 14.2 54.5 58.4 98.78 54.2 1406
ATL 15 9 6 725.0 112.8 110.8 1.9 71.1 2.03 20.2 32.8 69.6 49.9 14.6 52.8 55.7 103.71 49.0 1566
MIA 15 9 6 725.0 116.9 116.7 0.3 70.3 2.06 20.0 30.8 68.3 49.4 14.0 55.4 59.1 102.19 50.8 1546
OKC 15 9 6 720.0 113.0 108.7 4.4 55.5 1.73 16.8 31.6 68.9 50.9 13.5 52.2 55.9 99.17 53.5 1488
POR 14 9 5 672.0 116.2 110.2 6.0 63.8 1.55 17.8 33.0 70.1 51.9 16.1 54.8 59.2 100.71 52.5 1410
CLE 16 8 8 773.0 117.5 115.5 2.0 64.7 1.99 19.3 30.9 68.7 50.4 13.7 55.8 59.1 100.01 51.0 1610
DAL 15 8 7 720.0 112.3 113.4 -1.1 65.5 1.64 18.6 33.1 65.9 49.5 16.3 53.6 57.3 99.97 49.4 1501
DEN 13 8 5 629.0 114.3 113.8 0.5 64.9 1.89 19.1 30.4 66.8 49.4 14.2 54.3 58.6 98.02 52.5 1287
GSW 15 8 7 725.0 113.4 112.8 0.6 70.5 1.70 19.1 32.7 67.9 50.3 16.2 53.9 58.1 99.41 50.3 1503
NYK 14 8 6 677.0 114.8 109.0 5.8 68.6 1.83 18.9 37.1 72.2 54.5 15.2 52.4 56.3 94.87 53.6 1342
PHX 14 7 7 672.0 115.6 116.8 -1.2 65.8 1.94 19.6 30.5 63.1 46.8 14.4 55.4 58.4 98.89 49.4 1382
ORL 14 6 8 677.0 111.3 114.0 -2.7 68.5 1.65 19.1 30.7 70.6 50.5 16.4 53.9 57.4 97.84 48.5 1375
IND 15 5 10 720.0 110.7 113.6 -2.9 67.2 1.92 19.7 24.4 68.1 46.8 14.3 53.9 57.4 100.90 49.4 1511
NOP 16 5 11 783.0 111.7 118.9 -7.1 60.7 1.54 17.1 30.1 68.5 48.9 15.3 51.8 57.5 101.30 46.4 1652
TOR 15 5 10 725.0 113.7 113.1 0.5 67.6 2.07 19.3 34.3 66.4 49.0 13.7 52.0 55.1 98.09 48.4 1478
WAS 16 5 11 778.0 109.9 117.1 -7.1 60.1 1.62 17.1 29.2 65.6 47.9 14.6 51.7 56.3 99.46 46.3 1612
CHA 14 4 10 677.0 103.1 113.7 -10.6 62.6 1.14 15.9 36.2 72.8 53.4 19.9 48.6 52.5 96.43 43.5 1360
CHI 14 4 10 677.0 111.1 119.1 -8.0 67.9 1.61 18.7 31.6 64.6 48.0 16.5 52.7 56.8 103.80 46.2 1464
LAC 13 4 9 629.0 111.4 117.0 -5.6 68.5 1.55 19.0 29.2 65.9 47.6 17.2 54.9 58.8 99.74 47.4 1306
BKN 14 3 11 677.0 110.5 119.0 -8.4 64.6 1.39 17.4 31.9 68.0 49.6 17.5 53.5 57.5 99.51 45.2 1404
UTA 16 3 13 778.0 107.0 114.5 -7.5 65.0 1.48 17.8 29.0 69.7 49.2 16.7 52.4 56.2 100.16 47.2 1626
MIL 15 1 14 720.0 106.7 119.7 -13.0 65.1 1.46 17.4 31.1 64.5 47.6 16.8 51.4 54.7 101.00 42.4 1515
SAC 14 1 13 672.0 106.9 120.4 -13.5 64.8 1.47 18.2 28.4 69.3 48.0 17.2 52.8 56.3 100.93 42.5 1411
"""

# TRADITIONAL — 30 rows. LAL, PHI and SAS re-read on the TeamID-filtered page (see header).
TRAD = """\
LAL 16 13 3 .813 48.3 120.9 41.6 85.1 48.9 14.1 37.6 37.5 23.6 30.0 78.8 12.0 29.4 41.4 24.4 16.7 10.8 5.8 4.2 22.9 24.0 6.4
PHI 16 13 3 .813 48.0 114.5 40.6 87.4 46.4 12.3 34.5 35.5 21.1 26.6 79.3 10.1 32.7 42.8 26.3 12.6 8.1 4.4 5.7 20.6 21.3 2.9
SAS 15 12 3 .800 48.3 117.1 42.4 91.3 46.4 12.1 36.0 33.5 20.2 25.2 80.2 13.1 35.1 48.2 27.8 12.5 8.3 6.9 4.7 19.1 20.8 11.2
HOU 16 12 4 .750 48.0 117.9 42.1 87.6 48.1 13.1 34.4 38.2 20.5 25.4 80.8 13.9 31.8 45.7 27.6 14.6 7.6 5.6 4.7 19.9 21.6 8.7
BOS 15 11 4 .733 48.3 113.9 40.2 88.6 45.4 16.4 43.9 37.3 17.1 22.0 77.6 13.5 31.5 45.0 26.8 14.5 8.5 4.7 4.3 21.9 21.4 10.5
MEM 15 11 4 .733 48.3 121.9 42.8 89.0 48.1 15.6 39.4 39.6 20.7 24.5 84.5 12.2 34.3 46.5 28.9 15.9 6.7 5.1 6.9 23.3 21.8 9.0
MIN 15 11 4 .733 48.3 116.7 42.3 90.1 47.0 14.1 38.2 37.0 17.9 26.3 67.8 13.5 35.1 48.6 25.4 16.1 8.9 5.1 6.4 22.1 23.3 10.6
DET 14 10 4 .714 48.7 115.4 41.2 87.8 46.9 13.2 35.6 37.1 19.7 24.9 79.3 12.0 31.9 43.9 28.0 14.2 9.3 6.1 5.7 23.5 21.9 6.4
POR 14 9 5 .643 48.0 117.0 39.4 86.2 45.7 15.6 43.4 36.0 22.5 28.8 78.2 11.7 33.0 44.7 25.1 16.2 7.1 5.3 4.4 22.8 24.1 6.0
DEN 13 8 5 .615 48.4 113.2 41.0 85.0 48.2 10.4 30.9 33.6 20.8 26.1 79.6 10.3 31.7 42.0 26.6 14.1 8.8 4.4 4.4 18.8 23.2 0.9
ATL 15 9 6 .600 48.3 117.7 43.5 96.6 45.1 14.9 43.5 34.3 15.7 20.7 75.9 13.9 31.3 45.2 30.9 15.3 10.3 3.9 6.1 21.8 19.3 1.9
MIA 15 9 6 .600 48.3 120.5 42.1 89.0 47.3 14.3 40.7 35.2 21.9 29.5 74.4 10.7 31.5 42.2 29.6 14.4 7.9 5.7 4.9 21.3 25.4 0.7
OKC 15 9 6 .600 48.0 112.1 41.8 90.5 46.2 10.8 31.6 34.2 17.7 22.2 79.9 11.1 34.8 45.9 23.2 13.4 8.2 5.4 5.1 18.9 21.1 4.4
NYK 14 8 6 .571 48.4 110.0 38.9 88.0 44.2 14.5 40.3 36.0 17.8 22.1 80.3 13.5 34.0 47.5 26.6 14.6 7.2 4.1 6.0 20.6 21.2 6.1
DAL 15 8 7 .533 48.0 112.3 40.7 88.0 46.3 12.9 37.9 34.1 17.9 22.8 78.7 12.5 30.7 43.2 26.7 16.3 8.7 5.7 4.9 21.7 20.5 -0.9
GSW 15 8 7 .533 48.3 113.7 39.1 86.9 44.9 15.5 41.7 37.3 20.0 24.9 80.4 12.6 31.7 44.3 27.5 16.2 8.4 5.6 5.7 21.9 22.2 0.9
CLE 16 8 8 .500 48.3 118.3 42.5 89.6 47.4 15.1 41.1 36.7 18.2 23.8 76.4 11.6 34.3 45.9 27.5 13.8 7.5 5.2 3.8 21.9 20.1 1.9
PHX 14 7 7 .500 48.0 114.1 42.0 88.4 47.5 13.9 37.4 37.1 16.2 21.2 76.4 11.1 29.1 40.2 27.6 14.2 8.0 4.1 4.7 21.4 19.2 -1.6
ORL 14 6 8 .429 48.4 109.4 39.0 85.4 45.7 14.1 40.3 35.1 17.2 22.4 77.0 10.8 31.9 42.7 26.7 16.1 7.4 4.2 4.9 22.3 22.6 -3.4
IND 15 5 10 .333 48.0 111.5 41.1 87.1 47.2 11.7 36.0 32.6 17.7 23.1 76.6 9.5 31.7 41.2 27.6 14.4 7.6 4.3 4.3 20.1 22.5 -3.3
TOR 15 5 10 .333 48.3 112.0 41.2 90.8 45.4 12.1 35.9 33.6 17.5 24.7 71.1 13.2 27.4 40.6 27.9 13.5 9.7 4.4 5.5 25.0 22.9 0.0
NOP 16 5 11 .313 48.9 115.4 39.9 86.6 46.1 9.9 29.4 33.6 25.6 31.3 81.8 11.1 30.7 41.8 24.3 15.8 9.7 5.1 5.7 24.3 23.9 -7.4
WAS 16 5 11 .313 48.6 110.8 39.6 86.6 45.7 10.4 32.6 31.8 21.1 26.6 79.5 10.9 31.4 42.3 23.8 14.7 7.5 5.6 3.6 20.3 21.5 -7.2
LAC 13 4 9 .308 48.4 111.9 39.1 84.3 46.4 14.4 36.8 39.0 19.4 24.6 78.8 10.1 29.4 39.5 26.8 17.2 9.5 4.5 4.4 21.5 21.0 -5.8
CHA 14 4 10 .286 48.4 100.1 35.1 87.0 40.4 14.3 45.4 31.4 15.6 18.9 82.6 14.9 31.9 46.9 22.0 19.4 7.1 4.6 4.5 21.1 21.4 -10.3
CHI 14 4 10 .286 48.4 116.2 40.9 90.1 45.4 13.2 41.3 32.0 21.1 27.7 76.3 12.9 31.1 43.9 27.8 17.2 8.4 5.6 4.8 23.4 22.6 -8.4
BKN 14 3 11 .214 48.4 110.9 37.7 84.0 44.9 14.5 40.0 36.3 20.9 28.0 74.7 11.4 29.9 41.3 24.4 17.5 8.3 4.9 4.7 25.6 24.1 -8.4
UTA 16 3 13 .188 48.6 108.8 38.6 86.2 44.8 13.0 36.9 35.3 18.5 24.1 76.7 11.4 33.0 44.4 25.1 16.9 7.0 5.8 5.2 23.1 22.7 -7.3
SAC 14 1 13 .071 48.0 107.7 39.2 86.1 45.6 12.5 36.4 34.4 16.8 21.9 76.5 9.9 29.9 39.7 25.4 17.4 7.9 3.4 5.2 22.5 19.4 -14.0
MIL 15 1 14 .067 48.0 107.7 38.1 88.7 42.9 14.9 43.8 34.1 16.7 22.3 74.6 13.5 31.5 45.1 24.8 16.9 7.1 4.6 5.5 23.4 19.9 -13.1
"""

# OPPONENT — 30 rows.
OPP = """\
LAL 16 13 3 48.3 39.1 85.6 45.7 15.1 41.5 36.4 21.1 27.6 76.2 13.1 28.9 41.9 27.4 18.8 9.5 4.2 5.8 24.0 22.9 114.4 -6.4
PHI 16 13 3 48.0 40.6 87.3 46.5 12.5 36.1 34.6 17.9 24.3 74.0 10.9 34.1 44.9 25.8 14.3 6.6 5.7 4.4 21.3 20.6 111.6 -2.9
HOU 16 12 4 48.0 40.3 87.8 45.9 12.7 38.9 32.6 16.0 21.8 73.4 11.9 28.1 39.9 24.1 14.5 8.7 4.7 5.6 21.6 19.9 109.2 -8.7
SAS 15 12 3 48.3 39.3 89.3 44.0 12.3 32.9 37.4 15.0 18.7 80.4 11.1 31.6 42.7 25.4 14.3 6.7 4.7 6.9 20.8 19.1 105.9 -11.2
BOS 15 11 4 48.3 35.9 84.6 42.4 13.9 41.6 33.5 17.7 23.0 77.1 12.5 30.7 43.3 25.2 16.7 7.2 4.3 4.7 21.4 21.9 103.4 -10.5
MEM 15 11 4 48.3 40.7 90.0 45.3 12.5 37.4 33.3 18.9 24.7 76.8 12.5 28.7 41.2 25.2 13.9 7.8 6.9 5.1 21.9 23.4 112.9 -9.0
MIN 15 11 4 48.3 38.5 89.9 42.8 11.8 36.3 32.5 17.3 22.5 76.9 12.4 31.5 43.9 24.5 16.7 7.8 6.4 5.1 23.3 22.1 106.1 -10.6
DET 14 10 4 48.7 38.4 87.0 44.1 11.9 36.1 32.8 20.4 26.0 78.3 13.0 32.0 45.0 23.6 17.4 7.6 5.7 6.1 21.9 23.5 108.9 -6.4
ATL 15 9 6 48.3 42.1 87.4 48.1 12.3 36.1 34.1 19.3 24.9 77.7 11.1 34.8 45.9 27.9 18.6 9.6 6.1 3.9 19.3 21.8 115.8 -1.9
MIA 15 9 6 48.3 42.7 89.5 47.8 15.3 40.5 37.9 19.1 24.6 77.5 12.1 33.1 45.3 29.1 16.6 7.9 4.9 5.7 25.4 21.3 119.9 -0.7
OKC 15 9 6 48.0 37.7 89.6 42.1 15.1 44.0 34.4 17.1 21.3 80.6 12.1 31.7 43.9 25.2 14.8 6.6 5.1 5.4 21.1 18.9 107.7 -4.4
POR 14 9 5 48.0 38.3 86.7 44.2 11.8 35.6 33.1 22.6 28.1 80.5 11.4 31.1 42.5 23.2 14.4 8.6 4.4 5.3 24.1 22.8 111.0 -6.0
CLE 16 8 8 48.3 41.6 91.4 45.5 14.0 40.0 35.0 19.2 24.1 79.5 12.1 31.8 43.9 27.6 12.9 7.3 3.8 5.2 20.1 21.9 116.3 -1.9
DAL 15 8 7 48.0 41.8 89.1 46.9 12.7 37.9 33.4 16.9 22.9 73.8 12.6 31.0 43.6 27.7 15.8 8.7 4.9 5.7 20.5 21.7 113.2 0.9
DEN 13 8 5 48.4 41.5 90.6 45.8 14.0 39.4 35.5 15.3 19.7 77.7 13.7 30.7 44.4 27.5 14.7 7.4 4.4 4.4 23.2 18.8 112.2 -0.9
GSW 15 8 7 48.3 40.7 88.4 46.1 13.3 38.1 34.8 18.1 23.1 78.1 12.5 31.2 43.7 27.6 16.2 9.0 5.7 5.6 22.2 21.9 112.8 -0.9
NYK 14 8 6 48.4 37.5 85.8 43.7 13.4 39.1 34.4 15.4 21.8 70.8 10.5 29.8 40.3 25.1 12.9 6.5 6.0 4.1 21.2 20.6 103.9 -6.1
PHX 14 7 7 48.0 40.6 86.6 46.9 14.1 38.1 37.0 20.5 26.5 77.4 13.4 31.6 45.1 26.0 17.1 7.7 4.7 4.1 19.2 21.4 115.7 1.6
ORL 14 6 8 48.4 39.8 85.4 46.6 14.1 37.1 37.9 19.1 25.3 75.7 10.0 31.2 41.2 27.1 14.7 9.2 4.9 4.2 22.6 22.3 112.8 3.4
IND 15 5 10 48.0 41.1 89.3 46.1 14.5 38.9 37.2 18.1 23.3 77.7 11.6 35.1 46.7 26.5 15.1 8.3 4.3 4.3 22.5 20.1 114.8 3.3
NOP 16 5 11 48.9 42.3 86.9 48.6 13.6 38.4 35.3 24.8 30.7 80.7 11.4 33.3 44.7 28.8 15.8 7.9 5.7 5.1 24.0 24.3 122.8 7.4
TOR 15 5 10 48.3 38.4 80.7 47.6 12.5 34.2 36.6 22.7 28.0 81.0 10.9 32.0 42.9 25.5 18.3 7.5 5.5 4.4 22.9 25.0 112.0 0.0
WAS 16 5 11 48.6 43.6 93.8 46.4 12.7 37.9 33.5 18.1 21.6 83.8 14.1 33.6 47.7 29.3 13.7 8.8 3.6 5.6 21.5 20.3 117.9 7.2
CHA 14 4 10 48.4 39.4 83.6 47.1 14.7 36.7 40.1 17.0 22.5 75.6 9.4 30.7 40.1 26.0 14.1 9.1 4.5 4.6 21.4 21.1 110.4 10.3
CHI 14 4 10 48.4 45.1 93.9 48.1 13.5 37.5 36.0 20.8 27.4 75.8 13.7 32.7 46.4 29.2 15.4 9.9 4.8 5.6 22.6 23.4 124.6 8.4
LAC 13 4 9 48.4 43.1 87.7 49.1 13.6 36.3 37.5 17.9 24.2 74.2 11.8 32.2 43.9 27.3 16.1 8.8 4.4 4.5 21.0 21.5 117.7 5.8
BKN 14 3 11 48.4 40.9 85.9 47.7 14.6 39.8 36.6 22.8 28.6 79.8 11.4 30.4 41.9 27.8 15.9 8.5 4.7 4.9 24.1 25.6 119.2 8.4
UTA 16 3 13 48.6 39.2 87.4 44.8 12.3 35.4 34.8 25.3 30.9 82.0 11.3 33.6 44.9 23.0 13.9 9.3 5.2 5.8 22.7 23.1 116.0 7.3
MIL 15 1 14 48.0 42.4 91.6 46.3 15.1 42.3 35.7 20.9 26.9 77.9 14.3 33.9 48.1 27.9 13.8 9.7 5.5 4.6 19.9 23.4 120.9 13.1
SAC 14 1 13 48.0 42.6 85.4 49.9 13.8 36.9 37.4 22.6 28.4 79.6 10.1 33.1 43.2 26.6 14.4 9.2 5.2 3.4 19.5 22.6 121.7 14.0
"""


def _cells(line: str) -> list[str]:
    return line.split()


def table(block: str, fields: list[str]) -> dict[str, dict]:
    out = {}
    for line in block.strip().splitlines():
        if not line.strip():
            continue
        cells = _cells(line.strip())
        assert len(cells) == len(fields) + 1, (cells[0], len(cells), len(fields) + 1)
        row = {"team": cells[0]}
        for name, raw in zip(fields, cells[1:]):
            if name in ("win_pct",):
                row[name] = float(raw)
            elif "." in raw:
                row[name] = float(raw)
            else:
                row[name] = int(raw.replace(",", ""))
        out[cells[0]] = row
    return out


def build() -> dict:
    adv = table(ADV, ADV_FIELDS)
    trad = table(TRAD, TRAD_FIELDS)
    opp = table(OPP, OPP_FIELDS)
    checks: list[dict] = []

    def chk(name, rule, failures):
        checks.append({"check": name, "rule": rule, "failures": failures,
                       "status": "PASS" if not failures else "FAIL"})

    teams = sorted(set(adv) | set(trad) | set(opp))
    chk("thirty_teams_each_page", "each page prints 30 rows and the same 30 clubs",
        [] if (len(adv) == len(trad) == len(opp) == 30 and set(adv) == set(trad) == set(opp))
        else [f"advanced {len(adv)}, traditional {len(trad)}, opponent {len(opp)}"])

    chk("net_rtg_equals_off_minus_def",
        "|NetRtg - (OffRtg - DefRtg)| <= 0.15 (all printed to 1 dp)",
        [f"{t}: {r['net_rtg']} vs {r['off_rtg'] - r['def_rtg']:.1f}"
         for t, r in adv.items() if abs(r["net_rtg"] - (r["off_rtg"] - r["def_rtg"])) > 0.15])

    chk("min_equals_48gp_plus_5_per_ot",
        "MIN - 48*GP is a non-negative multiple of 5 (one OT period = 5 minutes)",
        [f"{t}: min {r['min']} gp {r['gp']}"
         for t, r in adv.items()
         if (r["min"] - 48 * r["gp"]) < 0 or abs((r["min"] - 48 * r["gp"]) % 5) > 1e-9])

    chk("same_record_on_three_pages", "GP/W/L identical on all three pages",
        [f"{t}: adv {adv[t]['gp']}-{adv[t]['w']}-{adv[t]['l']}, "
         f"trad {trad[t]['gp']}-{trad[t]['w']}-{trad[t]['l']}, "
         f"opp {opp[t]['gp']}-{opp[t]['w']}-{opp[t]['l']}"
         for t in teams
         if not (adv[t]["gp"] == trad[t]["gp"] == opp[t]["gp"]
                 and adv[t]["w"] == trad[t]["w"] == opp[t]["w"]
                 and adv[t]["l"] == trad[t]["l"] == opp[t]["l"])])

    # OT games extend MIN past 48 per game, so the rate columns are per 48 minutes. Compare the
    # printed per-game points *per 48 minutes* against OffRtg x Pace, which is what the page's own
    # per-48 mode prints. Not doing this is how a 3-OT club looks "wrong" when it is right.
    chk("pts_per48_tracks_off_rtg_times_pace",
        "|PTS*48/MinPerGame - OffRtg*Pace/100| <= 0.5 points per 48 minutes",
        [f"{t}: {trad[t]['pts'] * 48 / (trad[t]['min']):.2f} vs "
         f"{adv[t]['off_rtg'] * adv[t]['pace'] / 100:.2f}"
         for t in teams
         if abs(trad[t]["pts"] * 48 / trad[t]["min"]
                - adv[t]["off_rtg"] * adv[t]["pace"] / 100) > 0.5])

    chk("opp_pts_per48_tracks_def_rtg_times_pace",
        "|OppPTS*48/MinPerGame - DefRtg*Pace/100| <= 0.5 points per 48 minutes",
        [f"{t}: {opp[t]['opp_pts'] * 48 / trad[t]['min']:.2f} vs "
         f"{adv[t]['def_rtg'] * adv[t]['pace'] / 100:.2f}"
         for t in teams
         if abs(opp[t]["opp_pts"] * 48 / trad[t]["min"]
                - adv[t]["def_rtg"] * adv[t]["pace"] / 100) > 0.5])

    # Pace x possessions per game must reproduce the printed season possession total.
    chk("poss_equals_pace_times_gp", "|POSS - Pace*GP/48 * 48| (pace is per 48 min) within 3%",
        [f"{t}: poss {adv[t]['poss']} vs {adv[t]['pace'] * adv[t]['gp']:.0f}"
         for t in teams
         if abs(adv[t]["poss"] - adv[t]["pace"] * adv[t]["gp"]) > 0.03 * adv[t]["poss"]])

    # PTS - OppPTS vs NetRtg: both sides are printed per game and NetRtg is per 100 possessions,
    # so three independently rounded numbers stack. 1.0 is the widest honest band.
    chk("margin_from_pts", "|(PTS - OppPTS) - NetRtg| <= 1.0 (three independently rounded prints)",
        [f"{t}: {trad[t]['pts'] - opp[t]['opp_pts']:.1f} vs net {adv[t]['net_rtg']}"
         for t in teams if abs((trad[t]["pts"] - opp[t]["opp_pts"]) - adv[t]["net_rtg"]) > 1.0])

    chk("win_pct_matches_record", "|WIN% - W/(W+L)| <= 0.0006 (printed to 3 dp)",
        [f"{t}: {trad[t]['win_pct']} vs {trad[t]['w'] / (trad[t]['w'] + trad[t]['l']):.3f}"
         for t in teams
         if abs(trad[t]["win_pct"] - trad[t]["w"] / (trad[t]["w"] + trad[t]["l"])) > 0.0006])

    return {
        "schema": "nba3.round.team_stats/v1",
        "session": "arena/b27118c3-nba3",
        "round": "2026-11-19",
        "retrieved_utc": RETRIEVED_UTC,
        "season": "2026-27 Regular Season, no filters, per-game mode (the page default)",
        "mode_note": ("These are the per-game columns the pages print by default; `poss` is the "
                      "printed season possession total, not a derived value."),
        "sources": {"advanced": URL_ADV, "traditional": URL_TRAD, "opponent": URL_OPP},
        "fields": {"advanced": ADV_FIELDS, "traditional": TRAD_FIELDS, "opponent": OPP_FIELDS},
        "counts": {"advanced": len(adv), "traditional": len(trad), "opponent": len(opp)},
        "checks": checks,
        "teams": {
            t: {
                "abbr": t,
                "gp": adv[t]["gp"], "w": adv[t]["w"], "l": adv[t]["l"],
                "advanced": adv[t], "traditional": trad[t], "opponent": opp[t],
            } for t in teams
        },
    }


def advanced_live(doc: dict) -> dict:
    """The live advanced file, same schema and field names as the 2026-11-15 promotion."""
    teams = {}
    ot_games = {}
    for t in sorted(doc["teams"]):
        a = doc["teams"][t]["advanced"]
        ot = int(round((a["min"] - 48 * a["gp"]) / 5.0))
        if ot:
            ot_games[t] = ot
        teams[t] = {
            "team": t, "gp": a["gp"], "w": a["w"], "l": a["l"], "min": a["min"],
            "off_rtg": a["off_rtg"], "def_rtg": a["def_rtg"], "net_rtg": a["net_rtg"],
            "ast_pct": a["ast_pct"], "ast_to": a["ast_to"], "ast_ratio": a["ast_ratio"],
            "oreb_pct": a["oreb_pct"], "dreb_pct": a["dreb_pct"], "reb_pct": a["reb_pct"],
            "tov_pct": a["tov_pct"], "efg_pct": a["efg_pct"], "ts_pct": a["ts_pct"],
            "pace": a["pace"], "pie": a["pie"], "poss": a["poss"],
            "source_url": "https://www.nba.com/stats/team/%s/traditional" % TEAM_IDS[t],
        }
    return {
        "schema": "nba3.live.team_stats/v1",
        "source_url": URL_ADV,
        "retrieved_utc": RETRIEVED_UTC,
        "chunks": ("full page, 30 rows, read in 2 chunks; every row is the printed row, promoted "
                   "by scripts/team_stats_b27118c3.py from "
                   "data/rounds/2026-11-19-b27118c3/team_stats_2026-11-19.json"),
        "columns": ADV_FIELDS,
        "consistency_checks": {
            "net_rtg_equals_off_minus_def": {
                "rule": "|NetRtg-(OffRtg-DefRtg)| <= 0.15 (both printed to 1 dp)",
                "failures": doc["checks"][1]["failures"],
                "status": doc["checks"][1]["status"],
            },
            "min_equals_48gp_plus_5_per_ot": {
                "rule": "MIN - 48*GP is a non-negative multiple of 5 (one OT period = 5 minutes)",
                "failures": doc["checks"][2]["failures"],
                "status": doc["checks"][2]["status"],
                "implied_ot_games_by_team": ot_games,
            },
            "pts_opp_pts_cross_page": {
                "rule": "printed PTS/OppPTS on the traditional and opponent pages reproduce "
                        "OffRtg and DefRtg at the printed pace (<=1.5 pts per game)",
                "failures": doc["checks"][4]["failures"] + doc["checks"][5]["failures"],
                "status": "PASS" if (doc["checks"][4]["status"] == doc["checks"][5]["status"] == "PASS")
                else "FAIL",
            },
        },
        "as_of": "2026-11-18 games (the pages were read 2026-11-19 before any 11/19 tip)",
        "teams": teams,
    }


TEAM_IDS = {
    "ATL": "1610612737", "BOS": "1610612738", "BKN": "1610612751", "CHA": "1610612766",
    "CHI": "1610612741", "CLE": "1610612739", "DAL": "1610612742", "DEN": "1610612743",
    "DET": "1610612765", "GSW": "1610612744", "HOU": "1610612745", "IND": "1610612754",
    "LAC": "1610612746", "LAL": "1610612747", "MEM": "1610612763", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "NOP": "1610612740", "NYK": "1610612752",
    "OKC": "1610612760", "ORL": "1610612753", "PHI": "1610612755", "PHX": "1610612756",
    "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759", "TOR": "1610612761",
    "UTA": "1610612762", "WAS": "1610612764",
}


def tsv(block: str, fields: list[str], url: str, note: str) -> str:
    head = [f"# source: {url}",
            "# season 2026-27 regular season, no filters, per-game mode, 30 rows",
            f"# read {RETRIEVED_UTC} by session arena/b27118c3-nba3 via the NBA.com stats page",
            f"# note: {note}",
            "# " + "\t".join(["team"] + fields)]
    return "\n".join(head + block.strip().splitlines()) + "\n"


def write_all(doc: dict) -> None:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    (CAPTURES / "team_stats_advanced_2026-11-19.tsv").write_text(
        tsv(ADV, ADV_FIELDS, URL_ADV,
            "all 30 rows printed on the page; nothing computed into this file"), "utf-8")
    (CAPTURES / "team_stats_traditional_2026-11-19.tsv").write_text(
        tsv(TRAD, TRAD_FIELDS, URL_TRAD,
            "all 30 rows; LAL/PHI/SAS also re-read on the TeamID-filtered page after the full "
            "table split across two chunks, and the SAS row agrees with the surviving fragment"),
        "utf-8")
    (CAPTURES / "team_stats_opponent_2026-11-19.tsv").write_text(
        tsv(OPP, OPP_FIELDS, URL_OPP,
            "all 30 rows printed on the page; nothing computed into this file"), "utf-8")
    ROUND_JSON.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n", "utf-8")
    LIVE.write_text(json.dumps(advanced_live(doc), indent=1, sort_keys=False) + "\n", "utf-8")


def check(doc: dict) -> int:
    bad = [c for c in doc["checks"] if c["status"] != "PASS"]
    for c in doc["checks"]:
        print(f"{c['status']:4} {c['check']}")
        for f in c["failures"][:5]:
            print("      ", f)
    if not ROUND_JSON.exists():
        print("missing", ROUND_JSON)
        return 1
    committed = json.loads(ROUND_JSON.read_text())
    same_round = json.dumps(committed["teams"], sort_keys=True) == json.dumps(doc["teams"], sort_keys=True)
    same_live = (LIVE.exists() and json.dumps(json.loads(LIVE.read_text())["teams"], sort_keys=True)
                 == json.dumps(advanced_live(doc)["teams"], sort_keys=True))
    print(f"round artefact matches the transcribed tables: {same_round}")
    print(f"live advanced file matches the round artefact : {same_live}")
    return 0 if (not bad and same_round and same_live) else 1


if __name__ == "__main__":
    doc = build()
    if "--check" in sys.argv:
        sys.exit(check(doc))
    failing = [c for c in doc["checks"] if c["status"] != "PASS"]
    if failing:
        for c in failing:
            print("FAIL", c["check"], c["failures"][:5])
        sys.exit("refusing to write a capture whose arithmetic does not hold")
    write_all(doc)
    for c in doc["checks"]:
        print(f"{c['status']:4} {c['check']}")
    print(f"wrote {len(doc['teams'])} clubs -> {ROUND_JSON.relative_to(ROOT)}, "
          f"{CAPTURES.relative_to(ROOT)}/team_stats_*_2026-11-19.tsv, {LIVE.relative_to(ROOT)}")
