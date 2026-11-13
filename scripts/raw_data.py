"""
RAW SOURCE DATA — transcribed from verified official / trusted secondary sources.

Every record in this module is a verbatim transcription. Nothing here is
estimated, inferred, or imputed. Each block carries:
  source_url  : the exact page the value was read from
  retrieved   : UTC timestamp of the retrieval in this session
  tier        : OFFICIAL (NBA-operated) | TRUSTED-2 (reputable secondary)

Downstream code (model.py, build_site.py) is allowed to do arithmetic on these
values but is never allowed to invent a value that is absent here. Missing
values stay missing and are surfaced by validate_site.py.

Season: 2026-27, in progress. Snapshot date 2026-11-13.
"""

RETRIEVED_UTC = "2026-11-13T22:30Z"

SOURCES = {
    "bbr_advanced": {
        "url": "https://www.basketball-reference.com/leagues/NBA_2027.html",
        "label": "Basketball-Reference — 2026-27 NBA Season Summary, Advanced Stats table",
        "tier": "TRUSTED-2",
        "what": "Team ORtg / DRtg / NRtg / Pace / MOV / SRS / Pythagorean W-L for all 30 teams",
        "note": "Not an NBA-operated source. Values are opponent-unknown per-100-possession ratings.",
    },
    "bbr_schedule": {
        "url": "https://www.basketball-reference.com/leagues/NBA_2027_games-november.html",
        "label": "Basketball-Reference — 2026-27 Schedule and Results (November)",
        "tier": "TRUSTED-2",
        "what": "Final scores of every completed game 2026-11-01 .. 2026-11-12",
        "note": "Individual box-score links per row are preserved for audit.",
    },
    "nba_schedule": {
        "url": "https://www.nba.com/schedule",
        "label": "NBA.com — official schedule",
        "tier": "OFFICIAL",
        "what": "Fixture list, tip-off times (ET), venues, NBA Cup group tags, game IDs",
        "note": "Tip-off times are ET as published by the league.",
    },
    "espn_odds": {
        "url": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{event_id}/competitions/{event_id}/odds",
        "label": "ESPN core odds endpoint (provider: DraftKings, id 100)",
        "tier": "TRUSTED-2",
        "what": "Consensus-listed spread, total, moneylines; both OPEN and CURRENT per game",
        "note": "Single-book (DraftKings) price snapshot relayed by ESPN. Not a market-wide consensus and not an NBA source.",
    },
    "nba_injury": {
        "url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf",
        "label": "NBA Official — Injury Report, 11/13/26 05:00 PM (PDF)",
        "tier": "OFFICIAL",
        "what": "Game, team, player, participation status (Out/Doubtful/Questionable/Probable/Available), reason",
        "note": "Timestamped snapshot issued by the league. Superseded by later same-day reports.",
    },
    "nba_injury_index": {
        "url": "https://official.nba.com/nba-injury-report-2026-27-season/",
        "label": "NBA Official — Injury Report index, 2026-27 season",
        "tier": "OFFICIAL",
        "what": "Filing rules (5 p.m. local the day before; 1 p.m. for 2nd of back-to-back) and the index of every dated report",
        "note": "Establishes the reporting obligation, not any player's health.",
    },
}

# ---------------------------------------------------------------------------
# 1. TEAM RATINGS — Basketball-Reference advanced table, 2026-27, read 2026-11-13
#    Columns: W, L, PW, PL, MOV, SOS, SRS, ORtg, DRtg, NRtg, Pace
#    Verified internally: NRtg == ORtg - DRtg for all 30 rows; SRS == MOV + SOS.
# ---------------------------------------------------------------------------
TEAM_RATINGS = {
    #            W,  L,  PW, PL,   MOV,    SOS,   SRS,  ORtg,  DRtg,  NRtg,  Pace
    "MIN": dict(w=9,  l=3,  pw=10, pl=2,  mov=13.42,  sos=-0.17, srs=13.25,  ortg=118.1, drtg=104.8, nrtg=13.3,  pace=100.2),
    "BOS": dict(w=10, l=2,  pw=10, pl=2,  mov=11.17,  sos=-5.39, srs=5.77,   ortg=119.2, drtg=107.6, nrtg=11.6,  pace=95.0),
    "SAS": dict(w=10, l=2,  pw=10, pl=2,  mov=11.17,  sos=0.18,  srs=11.35,  ortg=120.0, drtg=108.8, nrtg=11.2,  pace=98.4),
    "HOU": dict(w=9,  l=3,  pw=9,  pl=3,  mov=8.92,   sos=3.93,  srs=12.85,  ortg=119.3, drtg=110.1, nrtg=9.2,   pace=96.7),
    "LAL": dict(w=11, l=2,  pw=9,  pl=4,  mov=7.92,   sos=0.36,  srs=8.28,   ortg=122.7, drtg=114.7, nrtg=8.0,   pace=99.6),
    "GSW": dict(w=8,  l=4,  pw=9,  pl=3,  mov=7.83,   sos=2.71,  srs=10.55,  ortg=120.4, drtg=112.5, nrtg=7.9,   pace=98.3),
    "DET": dict(w=8,  l=3,  pw=8,  pl=3,  mov=7.73,   sos=-3.95, srs=3.78,   ortg=115.6, drtg=107.9, nrtg=7.7,   pace=98.1),
    "POR": dict(w=8,  l=3,  pw=8,  pl=3,  mov=7.27,   sos=3.34,  srs=10.62,  ortg=120.4, drtg=113.1, nrtg=7.3,   pace=99.3),
    "NYK": dict(w=6,  l=5,  pw=8,  pl=3,  mov=6.82,   sos=-4.31, srs=2.51,   ortg=116.2, drtg=109.0, nrtg=7.2,   pace=94.9),
    "MEM": dict(w=7,  l=4,  pw=7,  pl=4,  mov=6.00,   sos=-1.39, srs=4.61,   ortg=117.8, drtg=111.8, nrtg=6.0,   pace=99.1),
    "OKC": dict(w=8,  l=4,  pw=8,  pl=4,  mov=4.17,   sos=3.98,  srs=8.14,   ortg=112.9, drtg=108.6, nrtg=4.3,   pace=98.4),
    "CLE": dict(w=6,  l=6,  pw=7,  pl=5,  mov=2.08,   sos=-0.99, srs=1.10,   ortg=116.5, drtg=114.4, nrtg=2.1,   pace=99.1),
    "ATL": dict(w=7,  l=5,  pw=7,  pl=5,  mov=2.08,   sos=-2.27, srs=-0.19,  ortg=115.3, drtg=113.3, nrtg=2.0,   pace=102.5),
    "PHI": dict(w=10, l=3,  pw=7,  pl=6,  mov=1.77,   sos=-3.20, srs=-1.43,  ortg=112.0, drtg=110.2, nrtg=1.8,   pace=99.2),
    "TOR": dict(w=5,  l=7,  pw=7,  pl=5,  mov=1.42,   sos=-1.39, srs=0.03,   ortg=115.3, drtg=113.9, nrtg=1.4,   pace=99.1),
    "DEN": dict(w=6,  l=4,  pw=5,  pl=5,  mov=1.20,   sos=2.65,  srs=3.85,   ortg=117.6, drtg=116.4, nrtg=1.2,   pace=96.3),
    "DAL": dict(w=7,  l=5,  pw=6,  pl=6,  mov=1.00,   sos=2.45,  srs=3.45,   ortg=113.7, drtg=112.7, nrtg=1.0,   pace=99.6),
    "IND": dict(w=4,  l=8,  pw=5,  pl=7,  mov=-2.42,  sos=-3.03, srs=-5.44,  ortg=111.4, drtg=113.8, nrtg=-2.4,  pace=100.2),
    "MIA": dict(w=5,  l=6,  pw=4,  pl=7,  mov=-4.27,  sos=-0.01, srs=-4.29,  ortg=111.8, drtg=115.9, nrtg=-4.1,  pace=102.6),
    "PHO": dict(w=5,  l=6,  pw=4,  pl=7,  mov=-4.36,  sos=5.21,  srs=0.84,   ortg=113.7, drtg=118.2, nrtg=-4.5,  pace=98.3),
    "BRK": dict(w=3,  l=8,  pw=4,  pl=7,  mov=-5.09,  sos=-2.59, srs=-7.68,  ortg=110.1, drtg=115.2, nrtg=-5.1,  pace=99.1),
    "ORL": dict(w=4,  l=7,  pw=4,  pl=7,  mov=-5.55,  sos=0.52,  srs=-5.03,  ortg=109.7, drtg=115.3, nrtg=-5.6,  pace=98.0),
    "WAS": dict(w=4,  l=9,  pw=4,  pl=9,  mov=-5.77,  sos=-3.73, srs=-9.50,  ortg=110.0, drtg=115.8, nrtg=-5.8,  pace=98.4),
    "LAC": dict(w=2,  l=8,  pw=3,  pl=7,  mov=-5.90,  sos=2.76,  srs=-3.14,  ortg=111.2, drtg=117.1, nrtg=-5.9,  pace=99.8),
    "NOP": dict(w=4,  l=8,  pw=4,  pl=8,  mov=-7.33,  sos=-0.49, srs=-7.82,  ortg=113.4, drtg=120.5, nrtg=-7.1,  pace=100.5),
    "UTA": dict(w=1,  l=11, pw=2,  pl=10, mov=-11.50, sos=3.55,  srs=-7.95,  ortg=105.2, drtg=116.5, nrtg=-11.3, pace=99.6),
    "CHO": dict(w=4,  l=8,  pw=2,  pl=10, mov=-11.00, sos=-2.08, srs=-13.08, ortg=103.2, drtg=114.8, nrtg=-11.6, pace=95.5),
    "SAC": dict(w=1,  l=10, pw=2,  pl=9,  mov=-12.73, sos=3.09,  srs=-9.64,  ortg=107.7, drtg=120.3, nrtg=-12.6, pace=100.5),
    "MIL": dict(w=1,  l=11, pw=2,  pl=10, mov=-14.58, sos=1.50,  srs=-13.09, ortg=108.1, drtg=122.9, nrtg=-14.8, pace=98.8),
    "CHI": dict(w=1,  l=9,  pw=1,  pl=9,  mov=-15.50, sos=0.25,  srs=-15.25, ortg=109.8, drtg=124.9, nrtg=-15.1, pace=103.1),
}

LEAGUE_AVG = dict(age=26.7, ortg=114.0, drtg=114.0, pace=98.9)

TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BRK": "Brooklyn Nets",
    "CHI": "Chicago Bulls", "CHO": "Charlotte Hornets", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

# ---------------------------------------------------------------------------
# 2. COMPLETED GAMES 2026-11-01 .. 2026-11-12
#    Transcribed from the Basketball-Reference November results table.
#    Each row: (date, away, away_pts, home, home_pts, overtime_flag)
# ---------------------------------------------------------------------------
COMPLETED_GAMES = [
    ("2026-11-01", "BOS", 108, "ORL", 97,  ""),
    ("2026-11-01", "BRK", 98,  "IND", 90,  ""),
    ("2026-11-01", "LAC", 112, "GSW", 124, ""),
    ("2026-11-01", "TOR", 125, "LAL", 131, ""),

    ("2026-11-02", "OKC", 117, "CLE", 112, ""),
    ("2026-11-02", "DET", 124, "CHO", 91,  ""),
    ("2026-11-02", "ATL", 108, "IND", 104, ""),
    ("2026-11-02", "BRK", 90,  "NYK", 103, ""),
    ("2026-11-02", "WAS", 103, "ORL", 94,  ""),
    ("2026-11-02", "CHI", 107, "PHI", 126, ""),
    ("2026-11-02", "SAC", 115, "DAL", 100, ""),
    ("2026-11-02", "NOP", 135, "MEM", 134, "OT"),
    ("2026-11-02", "MIL", 100, "MIN", 112, ""),
    ("2026-11-02", "BOS", 93,  "HOU", 109, ""),
    ("2026-11-02", "UTA", 97,  "SAS", 119, ""),
    ("2026-11-02", "POR", 118, "DEN", 110, ""),
    ("2026-11-02", "PHO", 113, "GSW", 116, ""),
    ("2026-11-02", "TOR", 125, "LAC", 118, ""),
    ("2026-11-02", "MIA", 117, "LAL", 138, ""),

    ("2026-11-04", "PHI", 112, "DET", 106, ""),
    ("2026-11-04", "ATL", 120, "WAS", 105, ""),
    ("2026-11-04", "MIL", 102, "BOS", 109, ""),
    ("2026-11-04", "CHO", 104, "BRK", 114, ""),
    ("2026-11-04", "CHI", 105, "NYK", 135, ""),
    ("2026-11-04", "IND", 107, "MEM", 103, ""),
    ("2026-11-04", "UTA", 113, "NOP", 120, "OT"),
    ("2026-11-04", "CLE", 116, "OKC", 124, ""),
    ("2026-11-04", "MIN", 117, "HOU", 107, ""),
    ("2026-11-04", "TOR", 109, "DEN", 128, ""),
    ("2026-11-04", "POR", 132, "PHO", 119, ""),
    ("2026-11-04", "DAL", 111, "SAS", 112, ""),
    ("2026-11-04", "LAL", 116, "SAC", 103, ""),
    ("2026-11-04", "MIA", 117, "LAC", 116, "OT"),

    ("2026-11-05", "ORL", 104, "PHO", 117, ""),
    ("2026-11-05", "MIA", 100, "GSW", 120, ""),

    ("2026-11-06", "WAS", 132, "ATL", 139, ""),
    ("2026-11-06", "BOS", 119, "CHO", 80,  ""),
    ("2026-11-06", "PHI", 95,  "CLE", 119, ""),
    ("2026-11-06", "UTA", 100, "DAL", 112, ""),
    ("2026-11-06", "OKC", 128, "MEM", 97,  ""),
    ("2026-11-06", "TOR", 121, "MIL", 107, ""),
    ("2026-11-06", "MIN", 115, "NOP", 109, ""),
    ("2026-11-06", "POR", 118, "LAL", 124, ""),
    ("2026-11-06", "SAS", 124, "SAC", 109, ""),

    ("2026-11-07", "DEN", 114, "IND", 102, ""),
    ("2026-11-07", "BRK", 121, "ATL", 124, ""),
    ("2026-11-07", "NYK", 109, "CLE", 97,  ""),
    ("2026-11-07", "WAS", 75,  "OKC", 114, ""),
    ("2026-11-07", "ORL", 119, "GSW", 126, "OT"),
    ("2026-11-07", "HOU", 99,  "PHO", 102, ""),
    ("2026-11-07", "SAS", 125, "POR", 103, ""),

    ("2026-11-08", "PHI", 127, "CHI", 121, ""),
    ("2026-11-08", "LAL", 121, "DET", 116, ""),
    ("2026-11-08", "UTA", 100, "MIN", 115, ""),
    ("2026-11-08", "BRK", 93,  "DAL", 130, ""),
    ("2026-11-08", "BOS", 117, "MIL", 97,  ""),
    ("2026-11-08", "NOP", 123, "LAC", 139, ""),
    ("2026-11-08", "MIA", 114, "SAC", 108, ""),

    ("2026-11-09", "LAL", 124, "ATL", 114, ""),
    ("2026-11-09", "CLE", 112, "CHO", 124, ""),
    ("2026-11-09", "WAS", 111, "DET", 122, ""),
    ("2026-11-09", "MEM", 118, "TOR", 102, ""),
    ("2026-11-09", "IND", 122, "DAL", 125, ""),
    ("2026-11-09", "DEN", 100, "HOU", 110, ""),
    ("2026-11-09", "SAS", 122, "PHO", 96,  ""),
    ("2026-11-09", "NOP", 87,  "GSW", 138, ""),

    ("2026-11-10", "MIL", 85,  "NYK", 117, ""),
    ("2026-11-10", "BOS", 123, "PHI", 101, ""),
    ("2026-11-10", "LAC", 110, "PHO", 133, ""),
    ("2026-11-10", "MIA", 115, "UTA", 109, ""),
    ("2026-11-10", "ORL", 107, "SAC", 100, ""),
    ("2026-11-10", "OKC", 103, "POR", 123, ""),

    ("2026-11-11", "WAS", 101, "IND", 114, ""),
    ("2026-11-11", "CLE", 115, "NYK", 107, ""),
    ("2026-11-11", "BOS", 98,  "TOR", 93,  ""),
    ("2026-11-11", "SAS", 124, "CHI", 119, ""),
    ("2026-11-11", "DEN", 123, "MEM", 118, ""),
    ("2026-11-11", "LAL", 123, "MIL", 112, ""),
    ("2026-11-11", "BRK", 145, "NOP", 111, ""),
    ("2026-11-11", "ORL", 123, "UTA", 108, ""),
    ("2026-11-11", "GSW", 108, "HOU", 115, ""),
    ("2026-11-11", "OKC", 108, "POR", 118, ""),

    ("2026-11-12", "TOR", 112, "PHI", 123, ""),
    ("2026-11-12", "DET", 144, "WAS", 140, "2OT"),
    ("2026-11-12", "DAL", 94,  "MIN", 133, ""),
    ("2026-11-12", "CHO", 96,  "PHO", 101, ""),
]

# ---------------------------------------------------------------------------
# 3. UPCOMING SLATE — NBA.com official schedule, games 2026-11-13 .. 2026-11-15
#    (72-hour window from snapshot). event_id is the ESPN event id used for the
#    odds lookup; nba_game_id is the league's own id (NBA.com/game/<slug>-<id>).
# ---------------------------------------------------------------------------
UPCOMING_GAMES = [
    # date,        time_et,  away,  home,  nba_game_id,   espn_event_id, nba_cup_group
    ("2026-11-13", "19:00", "NYK", "IND", "0022600034", "401909296", "East Group B"),
    ("2026-11-13", "19:00", "MIL", "ORL", "0022600035", "401909297", "East Group A"),
    ("2026-11-13", "20:00", "CLE", "MIA", "0022600036", "401909298", "East Group B"),
    ("2026-11-13", "20:00", "ATL", "CHI", "0022600037", "401909299", "East Group C"),
    ("2026-11-13", "20:00", "MEM", "NOP", "0022600038", "401909300", "West Group B"),
    ("2026-11-13", "20:30", "UTA", "HOU", "0022600039", "401909301", "West Group A"),
    ("2026-11-13", "21:30", "GSW", "SAS", "0022600040", "401909302", "West Group C"),
    ("2026-11-13", "22:00", "POR", "SAC", "0022600041", "401909303", "West Group C"),
    ("2026-11-13", "22:30", "OKC", "LAC", "0022600042", "401909304", "West Group B"),

    ("2026-11-14", "19:00", "DEN", "NOP", "0022600231", "401909980", ""),
    ("2026-11-14", "19:30", "DAL", "CLE", "0022600232", "401909981", ""),
    ("2026-11-14", "20:00", "BKN", "MEM", "0022600234", "401909983", ""),
    ("2026-11-14", "20:00", "DET", "MIA", "0022600233", "401909982", ""),
    ("2026-11-14", "20:00", "CHI", "MIN", "0022600235", "401909984", ""),

    ("2026-11-15", "13:00", "IND", "PHI", "0022600236", "401909985", ""),
    ("2026-11-15", "16:00", "LAL", "PHO", "0022600237", "401909986", ""),
    ("2026-11-15", "16:30", "CHA", "LAC", "0022600238", "401909987", ""),
    ("2026-11-15", "17:00", "SAS", "UTA", "0022600239", "401909988", ""),
    ("2026-11-15", "18:00", "DAL", "BOS", "0022600240", "401909989", ""),
    ("2026-11-15", "18:00", "NYK", "TOR", "0022600241", "401909990", ""),
    ("2026-11-15", "19:00", "HOU", "WAS", "0022600242", "401909991", ""),
    ("2026-11-15", "20:00", "ATL", "MIL", "0022600243", "401909992", ""),
    ("2026-11-15", "21:00", "OKC", "SAC", "0022600244", "401909993", ""),
]

# NBA.com and Basketball-Reference spell two clubs differently; normalise once.
ALIAS = {"BKN": "BRK", "CHA": "CHO"}

# ---------------------------------------------------------------------------
# 4. MARKET SNAPSHOT — ESPN core odds endpoint, provider DraftKings (id 100).
#    Only the 2026-11-13 slate was captured in full this session.
#    Conventions verified against each event's JSON:
#      cur_spread / open_spread : HOME team handicap (negative = home favoured)
#      away_ml / home_ml        : American moneylines, away listed first
#      *_spread_odds            : American price on that side's spread
#    A game absent from this dict has NO captured market -> render blank + flag.
# ---------------------------------------------------------------------------
MARKET = {
    "401909296": dict(open_spread=-2.5,  cur_spread=8.5,   open_total=233.5, cur_total=219.5,
                      away_ml=-337, home_ml=271,  away_spread_odds=-110, home_spread_odds=-110,
                      over_odds=-107, under_odds=-113),
    "401909297": dict(open_spread=-9.5,  cur_spread=-9.5,  open_total=223.5, cur_total=224.5,
                      away_ml=312,  home_ml=-395, away_spread_odds=-108, home_spread_odds=-112,
                      over_odds=-108, under_odds=-112),
    "401909298": dict(open_spread=-1.5,  cur_spread=-2.5,  open_total=237.5, cur_total=236.5,
                      away_ml=114,  home_ml=-135, away_spread_odds=-112, home_spread_odds=-108,
                      over_odds=-107, under_odds=-113),
    "401909299": dict(open_spread=6.5,   cur_spread=7.5,   open_total=246.5, cur_total=245.5,
                      away_ml=-277, home_ml=227,  away_spread_odds=-103, home_spread_odds=-118,
                      over_odds=-111, under_odds=-108),
    "401909300": dict(open_spread=4.5,   cur_spread=3.5,   open_total=234.5, cur_total=235.5,
                      away_ml=-162, home_ml=136,  away_spread_odds=-108, home_spread_odds=-112,
                      over_odds=-105, under_odds=-115),
    "401909301": dict(open_spread=-17.5, cur_spread=-15.5, open_total=217.5, cur_total=220.5,
                      away_ml=740,  home_ml=-1180, away_spread_odds=-112, home_spread_odds=-108,
                      over_odds=-113, under_odds=-107),
    "401909302": dict(open_spread=-11.5, cur_spread=-12.5, open_total=234.5, cur_total=217.5,
                      away_ml=487,  home_ml=-670, away_spread_odds=-115, home_spread_odds=-105,
                      over_odds=-113, under_odds=-107),
    "401909303": dict(open_spread=10.5,  cur_spread=10.5,  open_total=229.5, cur_total=229.5,
                      away_ml=-468, home_ml=361,  away_spread_odds=-105, home_spread_odds=-115,
                      over_odds=-112, under_odds=-108),
    "401909304": dict(open_spread=7.5,   cur_spread=7.5,   open_total=221.5, cur_total=222.5,
                      away_ml=-283, home_ml=231,  away_spread_odds=-107, home_spread_odds=-112,
                      over_odds=-108, under_odds=-112),
}

# Integrity cross-check: the ESPN `details` string states the favourite and line.
# Transcribed separately so a mismatch with the parsed fields above is detectable.
MARKET_DETAILS_STRING = {
    "401909296": "NY -8.5", "401909297": "ORL -9.5", "401909298": "MIA -2.5",
    "401909299": "ATL -7.5", "401909300": "MEM -3.5", "401909301": "HOU -15.5",
    "401909302": "SA -12.5", "401909303": "POR -10.5", "401909304": "OKC -7.5",
}

# ---------------------------------------------------------------------------
# 5. OFFICIAL INJURY REPORT — 11/13/26 05:00 PM ET
#    (game_date, matchup, team, player, status, reason)
# ---------------------------------------------------------------------------
INJURIES = [
    ("2026-11-13", "MIL@ORL", "ORL", "Banchero, Paolo",        "Out",        "Injury/Illness - Right High Ankle Sprain"),
    ("2026-11-13", "MIL@ORL", "ORL", "Cain, Jamal",            "Questionable","Injury/Illness - Left Shoulder Contusion"),
    ("2026-11-13", "MIL@ORL", "ORL", "da Silva, Tristan",      "Questionable","Injury/Illness - Left Calf Strain"),
    ("2026-11-13", "MIL@ORL", "ORL", "Isaac, Jonathan",        "Out",        "Injury/Illness - Left Knee Injury Management"),
    ("2026-11-13", "MIL@ORL", "ORL", "Nelson, Izaiyah",        "Out",        "Injury/Illness - Left Ankle Injury Recovery"),
    ("2026-11-13", "MIL@ORL", "ORL", "Penda, Noah",            "Out",        "Injury/Illness - Right Partially Torn Hamstring"),
    ("2026-11-13", "MIL@ORL", "ORL", "Suggs, Jalen",           "Questionable","Injury/Illness - Right Knee Contusion/Bone Bruise"),

    ("2026-11-13", "NYK@IND", "IND", "Furphy, Johnny",         "Out",        "Injury/Illness - Right ACL Repair/Surgery"),
    ("2026-11-13", "NYK@IND", "IND", "Haliburton, Tyrese",     "Out",        "Injury/Illness - Left Hamstring Strain"),
    ("2026-11-13", "NYK@IND", "IND", "McConnell, T.J.",        "Probable",   "Injury/Illness - Right Hamstring Strain"),
    ("2026-11-13", "NYK@IND", "IND", "Nesmith, Aaron",         "Questionable","Injury/Illness - Right Knee Soreness"),
    ("2026-11-13", "NYK@IND", "IND", "Sheppard, Ben",          "Out",        "Injury/Illness - Left Meniscus Surgery"),

    ("2026-11-13", "ATL@CHI", "ATL", "Dennis, RayJ",           "Questionable","G League - Two-Way"),
    ("2026-11-13", "ATL@CHI", "ATL", "Flemings, Kingston",     "Questionable","Injury/Illness - Lumbar Spasm"),
    ("2026-11-13", "ATL@CHI", "ATL", "Gilbert, Keshon",        "Out",        "Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure"),
    ("2026-11-13", "ATL@CHI", "ATL", "Gueye, Mouhamed",        "Out",        "Injury/Illness - Left Foot Fracture"),
    ("2026-11-13", "ATL@CHI", "ATL", "Landale, Jock",          "Available",  "Injury/Illness - Face Mask"),
    ("2026-11-13", "ATL@CHI", "ATL", "Newell, Asa",            "Out",        "Injury/Illness - Left Great Toe Hyperextension"),
    ("2026-11-13", "ATL@CHI", "ATL", "Veesaar, Henri",         "Out",        "Injury/Illness - Right ACL Tear"),
    ("2026-11-13", "ATL@CHI", "ATL", "Wilson, Jalen",          "Out",        "G League - Two-Way"),
    ("2026-11-13", "ATL@CHI", "CHI", "Awaka, Tobe",            "Out",        "Injury/Illness - Disc Irritation"),
    ("2026-11-13", "ATL@CHI", "CHI", "Powell, Norman",         "Questionable","Injury/Illness - Low Back Spasms"),
    ("2026-11-13", "ATL@CHI", "CHI", "Sellers, Jaylin",        "Out",        "G League - Two-Way"),
    ("2026-11-13", "ATL@CHI", "CHI", "Swain, Dailyn",          "Questionable","Injury/Illness - Right Disc Irritation"),
    ("2026-11-13", "ATL@CHI", "CHI", "Wilson, Caleb",          "Out",        "Injury/Illness - Right Metacarpal Fracture"),

    ("2026-11-13", "CLE@MIA", "CLE", "Diop, Khalifa",          "Out",        "G League - On Assignment"),
    ("2026-11-13", "CLE@MIA", "CLE", "Merrill, Sam",           "Out",        "Injury/Illness - Right Elbow Injury Management"),
    ("2026-11-13", "CLE@MIA", "CLE", "Mobley, Evan",           "Out",        "Injury/Illness - Left Great Toe - Sprain"),
    ("2026-11-13", "CLE@MIA", "CLE", "Tomlin, Nae'Qwan",       "Out",        "Injury/Illness - Low Back Stress Reaction"),
    ("2026-11-13", "CLE@MIA", "MIA", "Udeh, Jr., Ernest",      "Out",        "G League - Two-Way"),
    ("2026-11-13", "CLE@MIA", "MIA", "Antetokounmpo, Giannis", "Available",  "Injury/Illness - Right Wrist Sprain"),
    ("2026-11-13", "CLE@MIA", "MIA", "Goldin, Vladislav",      "Out",        "G League - Two-Way"),
    ("2026-11-13", "CLE@MIA", "MIA", "Larsson, Pelle",         "Doubtful",   "Injury/Illness - Illness"),
    ("2026-11-13", "CLE@MIA", "MIA", "Thompson, Klay",         "Probable",   "Injury/Illness - Left Ankle Soreness"),

    ("2026-11-13", "MEM@NOP", "MEM", "Edey, Zach",             "Out",        "Injury/Illness - Left Ankle Injury Management"),
    ("2026-11-13", "MEM@NOP", "MEM", "Lopez, Karim",           "Out",        "G League - On Assignment"),
    ("2026-11-13", "MEM@NOP", "MEM", "Mashack, Jahmai",        "Out",        "G League - Two-Way"),
    ("2026-11-13", "MEM@NOP", "MEM", "Pippen Jr., Scotty",     "Out",        "Injury/Illness - Lumbar Disc Herniation"),
    ("2026-11-13", "MEM@NOP", "MEM", "Post, Quinten",          "Out",        "Injury/Illness - Concussion Protocol"),
    ("2026-11-13", "MEM@NOP", "MEM", "Saunders, Richie",       "Out",        "Injury/Illness - Right Knee Surgery"),
    ("2026-11-13", "MEM@NOP", "NOP", "Dia, Malik",             "Available",  "G League - Two-Way"),
    ("2026-11-13", "MEM@NOP", "NOP", "Mathurin, Bennedict",    "Questionable","Injury/Illness - Right Thumb Sprain"),
    ("2026-11-13", "MEM@NOP", "NOP", "McGowens, Bryce",        "Out",        "Injury/Illness - Left Elbow Infection"),
    ("2026-11-13", "MEM@NOP", "NOP", "Missi, Yves",            "Out",        "Injury/Illness - Left Knee Contusion / Bone Bruise"),
    ("2026-11-13", "MEM@NOP", "NOP", "Murphy III, Trey",       "Out",        "Injury/Illness - Bilateral Patellar Tendinopathy"),
    ("2026-11-13", "MEM@NOP", "NOP", "Murray, Dejounte",       "Out",        "Injury/Illness - Left Ankle Sprain"),

    ("2026-11-13", "UTA@HOU", "UTA", "Alexander, Trey",        "Out",        "G League - Two-Way"),
    ("2026-11-13", "UTA@HOU", "UTA", "Bufkin, Kobe",           "Out",        "G League - Two-Way"),
    ("2026-11-13", "UTA@HOU", "UTA", "Ingram, Harrison",       "Out",        "G League - Two-Way"),
    ("2026-11-13", "UTA@HOU", "UTA", "Jackson Jr., Jaren",     "Out",        "Injury/Illness - Right MCL Tear"),
    ("2026-11-13", "UTA@HOU", "UTA", "Markkanen, Lauri",       "Out",        "Injury/Illness - Right Hand Fracture"),
    ("2026-11-13", "UTA@HOU", "UTA", "Nurkic, Jusuf",          "Out",        "Injury/Illness - Right 2nd Plantar Plate Tear"),
    ("2026-11-13", "UTA@HOU", "HOU", "Adams, Steven",          "Out",        "Injury/Illness - Right Soleus Strain"),
    ("2026-11-13", "UTA@HOU", "HOU", "Capela, Clint",          "Out",        "Injury/Illness - Right Ankle Sprain"),
    ("2026-11-13", "UTA@HOU", "HOU", "Copeland, Quadir",       "Out",        "G League - Two-Way"),
    ("2026-11-13", "UTA@HOU", "HOU", "Phillips, Julian",       "Out",        "G League - Two-Way"),
    ("2026-11-13", "UTA@HOU", "HOU", "Smart, Marcus",          "Out",        "League Suspension"),

    ("2026-11-13", "GSW@SAS", "GSW", "Bassey, Charles",        "Probable",   "Injury/Illness - Left Toe Soreness"),
    ("2026-11-13", "GSW@SAS", "GSW", "Butler III, Jimmy",      "Out",        "Injury/Illness - Right ACL Repair / Surgery"),
    ("2026-11-13", "GSW@SAS", "GSW", "Curry, Stephen",         "Out",        "Injury/Illness - Right Oblique Tear"),
    ("2026-11-13", "GSW@SAS", "GSW", "Moody, Moses",           "Out",        "Injury/Illness - Left Patellar Tendon Repair / Surgery"),
    ("2026-11-13", "GSW@SAS", "GSW", "Porzingis, Kristaps",    "Out",        "Not With Team"),
    ("2026-11-13", "GSW@SAS", "SAS", "Williams, Brandon",      "Out",        "Injury/Illness - Left Hamstring Strain"),
    ("2026-11-13", "GSW@SAS", "SAS", "Fox, De'Aaron",          "Questionable","Injury/Illness - Left Hip Soreness"),
    ("2026-11-13", "GSW@SAS", "SAS", "Harris, Tobias",         "Out",        "Injury/Illness - Left Calf Strain"),
    ("2026-11-13", "GSW@SAS", "SAS", "Quaintance, Jayden",     "Out",        "Injury/Illness - Right Knee Surgery"),
    ("2026-11-13", "GSW@SAS", "SAS", "Vassell, Devin",         "Questionable","Injury/Illness - Left Adductor Tightness"),

    ("2026-11-13", "POR@SAC", "POR", "Krejci, Vit",            "Out",        "Injury/Illness - Left Ankle Fracture"),
    ("2026-11-13", "POR@SAC", "POR", "Morant, Ja",             "Out",        "Injury/Illness - Left Hamstring Strain"),
    ("2026-11-13", "POR@SAC", "POR", "Sharpe, Shaedon",        "Out",        "Injury/Illness - Right Meniscus Surgery"),
    ("2026-11-13", "POR@SAC", "POR", "Youngblood, Chris",      "Out",        "Injury/Illness - Right Bone Bruise"),
    ("2026-11-13", "POR@SAC", "SAC", "Achiuwa, Precious",      "Out",        "Injury/Illness - Left Ankle Soreness"),
    ("2026-11-13", "POR@SAC", "SAC", "Karaban, Alex",          "Out",        "G League - On Assignment"),
    ("2026-11-13", "POR@SAC", "SAC", "Mogbo, Jonathan",        "Out",        "G League - Two-Way"),
    ("2026-11-13", "POR@SAC", "SAC", "Pedulla, Sean",          "Out",        "G League - Two-Way"),
]

# ---------------------------------------------------------------------------
# 6. PLAYER SEASON AVERAGES carried in NBA.com's own game preview (Field Level
#    Media copy published on nba.com) for NYK@IND, and league leaders table.
#    These are the ONLY player-level rates used; anything else stays blank.
# ---------------------------------------------------------------------------
PLAYER_RATES = {
    "Jalen Brunson":        dict(team="NYK", ppg=26.0, src="nba_game_preview"),
    "Karl-Anthony Towns":   dict(team="NYK", ppg=20.9, rpg=13.5, src="nba_game_preview+bbr_leaders"),
    "OG Anunoby":           dict(team="NYK", ppg=16.5, src="nba_game_preview"),
    "Landry Shamet":        dict(team="NYK", ppg=9.6,  src="nba_game_preview"),
    "Mikal Bridges":        dict(team="NYK", ppg=5.9,  src="nba_game_preview"),
    "Tyrese Haliburton":    dict(team="IND", ppg=21.8, apg=9.5, src="nba_game_preview"),
    "Luka Doncic":          dict(team="LAL", ppg=38.6, src="bbr_leaders"),
    "Nikola Jokic":         dict(team="DEN", apg=9.0,  src="bbr_leaders"),
}

GAME_PREVIEW_SOURCE = {
    "url": "https://www.nba.com/game/nyk-vs-ind-0022600034",
    "label": "NBA.com game preview, NYK vs IND, Nov 13 2026 (Field Level Media)",
    "tier": "OFFICIAL",
    "note": "League-operated page, but the season averages are editorial copy, not a stats export.",
}

BBR_LEADERS_SOURCE = {
    "url": "https://www.basketball-reference.com/leagues/NBA_2027_games.html",
    "label": "Basketball-Reference — 2026-27 PPG/RPG/APG leaders strip",
    "tier": "TRUSTED-2",
    "note": "Displayed as Doncic 38.6 PPG, Towns 13.5 RPG, Jokic 9.0 APG on 2026-11-13.",
}

# ---------------------------------------------------------------------------
# 7. PROP MARKET INVENTORY — ESPN core propBets endpoint (DraftKings)
#    Only the aggregate count was machine-readable without per-athlete lookups.
# ---------------------------------------------------------------------------
PROP_INVENTORY = {
    "401909296": dict(count=1170, page_size=25, page_count=47,
                      url="https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401909296/competitions/401909296/odds/100/propBets"),
    "note": "1,170 individual prop price points exposed for NYK@IND. Market type ids observed start at type id 1 = 'Total Points'. Athlete names are returned as opaque ids; name resolution was NOT completed in this session, so no prop price is presented as belonging to a named player.",
}

# ---------------------------------------------------------------------------
# 8. MODEL ASSUMPTIONS (explicitly NOT measured facts)
# ---------------------------------------------------------------------------
ASSUMPTIONS = {
    "hca_points": dict(
        value=2.6,
        label="Home-court advantage, points",
        why="Fixed league-wide constant used to convert neutral ratings into a home/road matchup.",
        status="ASSUMPTION — not estimated from this season's data",
        sensitivity="Every originated spread shifts 1:1 with this constant. See the sensitivity table on methodology.html.",
    ),
    "sd_margin": dict(
        value=12.4,
        label="Standard deviation of game margin, points",
        why="Gaussian margin model for cover probabilities.",
        status="ASSUMPTION — calibrated to a typical NBA margin sd; not re-estimated here",
        sensitivity="Cover probability is highly sensitive near the line; see sensitivity table.",
    ),
    "sd_total": dict(
        value=18.5,
        label="Standard deviation of game total, points",
        why="Gaussian total model for over/under probabilities.",
        status="ASSUMPTION — calibrated to a typical NBA total sd; not re-estimated here",
        sensitivity="Over/under probability moves ~2.7 points of probability per total point near the mean.",
    ),
    "shrink_k": dict(
        value=11.0,
        label="Regression-to-mean constant (games)",
        why="Prior games of league-average performance mixed into each team rating: r_adj = (G*r + k*0)/ (G+k).",
        status="ASSUMPTION — shrinkage constant, not fitted",
        sensitivity="Larger k pulls ratings toward average and toward the market.",
    ),
}
