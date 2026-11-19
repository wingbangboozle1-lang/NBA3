# Official NBA Injury Report revisions — 2026-11-19 (fetch tool parsed-text transcripts)

Revision chain captured this round (all four fetched 2026-11-19 ~07:40–07:45 UTC via fetch tool):

| Revision (ET) | Source URL | Player rows (verbatim) | Row-set sha256 (of rows block) |
|---|---|---|---|
| 12:45 AM | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_12_45AM.pdf | (captured by session de0caf5d — see their round tree; not re-fetched here) | n/a (not re-fetched) |
| 01:00 AM | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_00AM.pdf | 93-row block (30 rows with columns + 15-row first page) | rows identical to 01:45 block below |
| 01:15 AM | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_15AM.pdf | identical to 01:00 AM | rows identical to 01:45 block below |
| 01:30 AM | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_30AM.pdf | identical to 01:00 AM | rows identical to 01:45 block below |
| 01:45 AM | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_45AM.pdf | identical to 01:00 AM (verbatim below) | sha256 computed over rows block by capture script |

## Consecutive-revision diff (CR-DE0-02)

| Pair | Added rows | Removed rows | Status changes | Notes |
|---|---|---|---|---|
| 01:00 → 01:15 | 0 | 0 | 0 | no change |
| 01:15 → 01:30 | 0 | 0 | 0 | no change |
| 01:30 → 01:45 | 0 | 0 | 0 | no change |

All four revisions submitted identical player rows for the 11/19 slate. Teams GSW, MEM, MIL (11/19 games) and all nine 11/20 games remain NOT YET SUBMITTED in every revision.

NOTE (extraction defect, persistent across all four revisions — flags F-DE0-04/F-DE0-05):
the Kuminga, Jonathan and Pullin, Zyon rows carry no Game Date/Matchup/Team cells in the
report's own layout. Both players were RESOLVED to the Minnesota Timberwolves from official
game books `20261116_PORMIN` and `20261117_PORMIN` (roster + DND/inactive lines, both at
https://statsdmz.nba.com/pdfs/2026111{6,7}/…), which supersede any GSW attribution.

## Verbatim rows — 01:45 AM revision (identical row set in 01:00/01:15/01:30)

**Injury Report: 11/19/26 01:45 AM**

| Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Golden State Warriors |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | GSW@MEM | Memphis Grizzlies |  |  | NOT YET SUBMITTED |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Beal, Bradley | Out | Injury/Illness - Right Knee Injury Management |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Ingram, Brandon | Out | Injury/Illness - Right Heel Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Martinelli, Nick | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | LA Clippers | Miller, Jordan | Out | Injury/Illness - Left Rotator Cuff Surgery |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Brown, Maliq | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Gillespie, Ja'Kobi | Out | G League - Two-Way |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harper, Dylan | Out | Injury/Illness - Left Hip Soreness |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Harris, Tobias | Out | Injury/Illness - Left Calf Strain |
| 11/19/2026 | 08:00 (ET) | LAC@SAS | San Antonio Spurs | Quaintance, Jayden | Out | Injury/Illness - Right Knee Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Beringer, Joan | Available | Injury/Illness - Face Mask |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Clark, Jaylen | Out | Injury/Illness - Right Hamstring Strain |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | DiVincenzo, Donte | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery |
| 11/19/2026 | 08:00 (ET) | NYK@MIN | Minnesota Timberwolves | Edwards, Anthony | Out | Injury/Illness - Right Knee Arthroscopy |

|  |  |  |  | Kuminga, Jonathan | Questionable | Injury/Illness - Right Shoulder Contusion |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | Pullin, Zyon | Questionable | Injury/Illness - Right Quadriceps Contusion |
|  |  | POR@MIL | Portland Trail Blazers | Avdija, Deni | Questionable | Injury/Illness - Left Foot Inflammation / Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Camara, Toumani | Questionable | Injury/Illness - Abdominal Soreness |
|  |  | POR@MIL | Portland Trail Blazers | Carlson, Branden | Available | Injury/Illness - Face Mask |
|  |  | POR@MIL | Portland Trail Blazers | Krejci, Vit | Out | Injury/Illness - Left Ankle Fracture |
|  |  | POR@MIL | Portland Trail Blazers | Morant, Ja | Out | Injury/Illness - Left Hamstring Strain |
|  |  | POR@MIL | Portland Trail Blazers | Sharpe, Shaedon | Out | Injury/Illness - Right Meniscus Surgery |
|  |  | POR@MIL | Portland Trail Blazers | Williams III, Robert | Out | Rest |
|  |  | POR@MIL | Portland Trail Blazers | Youngblood, Chris | Out | Injury/Illness - Right Heel Contusion / Bone Bruise |
|  |  | POR@MIL | Milwaukee Bucks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Charlotte Hornets |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:00 (ET) | CHA@ATL | Atlanta Hawks |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Indiana Pacers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | IND@CLE | Cleveland Cavaliers |  |  | NOT YET SUBMITTED |
| 11/20/2026 | 07:30 (ET) | ORL@BKN | Orlando Magic |  |  | NOT YET SUBMITTED |

|  | Brooklyn Nets | NOT YET SUBMITTED |
| --- | --- | --- |
|  | TOR@DET | Toronto Raptors |
|  | Detroit Pistons | NOT YET SUBMITTED |
| 08:00 (ET) | NOP@OKC | New Orleans Pelicans |
|  | Oklahoma City Thunder | NOT YET SUBMITTED |
|  | WAS@CHI | Washington Wizards |
|  | Chicago Bulls | NOT YET SUBMITTED |
| 09:30 (ET) | PHX@UTA | Phoenix Suns |
|  | Utah Jazz | NOT YET SUBMITTED |
| 10:00 (ET) | HOU@DEN | Houston Rockets |
|  | Denver Nuggets | NOT YET SUBMITTED |
|  | SAC@LAL | Sacramento Kings |
|  | Los Angeles Lakers | NOT YET SUBMITTED |
