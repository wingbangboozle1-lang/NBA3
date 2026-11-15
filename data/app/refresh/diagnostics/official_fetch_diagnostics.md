# Official-source reachability on the GitHub Actions runner

Recorded live by the diagnose-official-fetch workflow. `OK` means the
payload check passed (JSON parsed / PDF magic present / HTML markers found).

| Test | Result | Status | Note |
|---|---|---|---|
| `A1_injury_index_browser` | OK | 200 | all markers found |
| `A2_injury_index_plain` | FAIL | 403 | HTTPError 403 Forbidden |
| `B1_injury_pdf_1115_0615AM` | OK | 200 |  |
| `B2_injury_pdf_1115_0500PM` | OK | 200 |  |
| `B3_injury_pdf_1114_0415AM` | OK | 200 |  |
| `C1_games_2026-11-15` | OK | 200 | all markers found |
| `C2_games_2026-11-16` | OK | 200 | all markers found |
| `C3_schedule_2026-11-15` | FAIL | 200 | markers missing: /game/ |
| `C4_games_2026-11-14` | OK | 200 | all markers found |
| `D1_team_traditional` | OK | 200 |  |
| `D2_team_opponent` | OK | 200 |  |
| `D3_team_advanced` | OK | 200 |  |
| `E1_scheduleLeagueV2` | FAIL | 403 | HTTPError 403 Forbidden |
| `E2_todaysScoreboard` | FAIL | 403 | HTTPError 403 Forbidden |
| `F1_liveData_scoreboard_20261115` | FAIL | 403 | HTTPError 403 Forbidden |
| `F2_liveData_scoreboard_20261114` | FAIL | 403 | HTTPError 403 Forbidden |
| `F3_liveData_boxscore_0022600001` | FAIL | 403 | HTTPError 403 Forbidden |
| `G1_standingsv3_headers` | FAIL | - | TimeoutError: The read operation timed out |
| `G2_standingsv3_plain` | FAIL | - | TimeoutError: The read operation timed out |
| `G3_teamstats_traditional_headers` | FAIL | - | TimeoutError: The read operation timed out |
| `G4_teamstats_traditional_plain` | FAIL | - | TimeoutError: The read operation timed out |
| `G3_teamstats_advanced_headers` | FAIL | - | TimeoutError: The read operation timed out |
| `G4_teamstats_advanced_plain` | FAIL | - | TimeoutError: The read operation timed out |
| `G3_teamstats_opponent_headers` | FAIL | - | TimeoutError: The read operation timed out |
| `G4_teamstats_opponent_plain` | FAIL | - | TimeoutError: The read operation timed out |
| `H1_gamebook_DENNOP` | OK | 200 |  |
| `H1_gamebook_DALCLE` | OK | 200 |  |

12/27 tests OK.
