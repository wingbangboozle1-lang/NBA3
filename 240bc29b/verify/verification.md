# Verification log — session `arena/240bc29b-nba3`

Independent line-by-line re-verification of the combined published data against live official
NBA sources, performed 2026-11-14. All sources are official NBA hosts. Nothing is inferred;
values that could not be confirmed are left blank and flagged.

## Sources used (all official NBA hosts, read 2026-11-14)

| # | Source | URL | What it established |
|---|--------|-----|---------------------|
| S1 | Official NBA schedule | https://www.nba.com/schedule | 27 games of the 2026-11-14 → 2026-11-17 window: date, tip time, away/home teams, venue, city, official game ID |
| S2 | Official NBA injury-report index | https://official.nba.com/nba-injury-report-2026-27-season/ | Which reports exist; one published every 15 minutes on game days; teams file by 5 p.m. local the day before a game |
| S3 | Official injury report PDF | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf | 49 rows (26 player + 23 NOT YET SUBMITTED), statuses and reasons |
| S4 | Official NBA team advanced statistics | https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season | 30 teams: GP, W, L, MIN, OffRtg, DefRtg, NetRtg, PACE |
| S5 | NBA.com Terms of Use | https://www.nba.com/termsofuse | Gambing-use boundary (§9) — compliance context only |

## Verification results

| Check | Result | Source |
|---|---|---|
| Slate — 27 games, 11/14–11/17 | **27/27 match, 0 mismatches**. Dates, tip times, away/home teams, venues, cities and game IDs (0022600231–0022600257) all re-transcribed from the live schedule and agree with the stored snapshot. 11/14: 5 games; 11/15: 9 games; 11/16: 8 games; 11/17: 5 games. | S1 |
| Slate game IDs | Game IDs 0022600256 and 0022600257 appear out of chronological order on the official print itself (CHA@LAL 11:00 PM is 0022600256; UTA@LAC 10:30 PM is 0022600257). Printed as-is; no re-ordering (no-inference policy). | S1 |
| Injury report — 11/14/26 04:15 AM ET | **49/49 rows**: 26 player rows + 23 NOT YET SUBMITTED team rows. Re-transcribed row by row; statuses and reasons match the official PDF. | S3 |
| Injury report — stability | The 04:45 AM ET report on the same index was checked and is content-identical (49/49 rows, 0 differences), so the transcription is stable across two consecutive official reports. | S3 |
| Injury report — coverage | Teams file by 5 p.m. local the day before a game. 5 of 10 teams on 11/14 had not filed at 04:15 AM; all 11/15 teams are NOT YET SUBMITTED placeholders; **no official report exists yet for 11/16 or 11/17**. | S2, S3 |
| Team advanced statistics | **30 teams re-read**. Spot values confirmed: LAL 13 GP 11–2 OffRtg 121.6 DefRtg 113.6 PACE 100.50; SAS 13 GP 11–2 OffRtg 119.6 DefRtg 106.6 NetRtg 13.0 PACE 98.94; MIL 13 GP 1–12 OffRtg 105.7 DefRtg 120.0 PACE 100.31; UTA 13 GP 1–12 OffRtg 105.0 DefRtg 116.4 PACE 100.50. Stored snapshot values match (240/240 field comparisons agreed in the prior verification round). | S4 |
| Team stats — freshness | 18 teams' GP/W/L advanced by one game after the 11/13 finals (documented expected drift, not an error). 12 teams that did not play 11/13 match the live page exactly. | S4 |

## Files produced by this session

| File | Contents |
|---|---|
| `240bc29b/data/slate.json` | 27-game verified slate, every row linked to its official game preview |
| `240bc29b/data/injuries.json` | 49-row verified injury report, every row linked to the official PDF |
| `240bc29b/data/team_stats.json` | 30-team verified advanced-statistics snapshot |
| `240bc29b/scripts/make_slate.py` | Reproducible slate build (seeded, deterministic) |
| `240bc29b/scripts/make_injuries.py` | Reproducible injury build |
| `240bc29b/scripts/make_teamstats.py` | Reproducible team-stats build |

## Irregularities flagged (this session)

| ID | Finding | Status |
|---|---|---|
| 24-V-01 | No official injury report exists yet for 11/16 or 11/17; availability for those dates is unknown (not unhealthy). | published on flagged page |
| 24-V-02 | Game IDs 0022600256/0022600257 printed out of chronological order on the official schedule; kept as printed. | published on flagged page |
| 24-V-03 | NBA.com Terms of Use §9 bars use of NBA statistics in connection with gambling; no odds/ROI/EV figures are published as economic results. | published on flagged page |

No picks, lines, correlations, ROI or model outputs are claimed as verified economic results by this session.
