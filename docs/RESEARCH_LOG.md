# Research Log (T03) — official sources, fetches, dead ends

**Session:** d01ae7e2 · **Data cut:** 2026-11-13 18:28 ET (23:30 UTC) · Registry: `data/sources.json`

Only NBA-official properties were used: `nba.com`, `www.nba.com`, `cdn.nba.com`, `ak-static.cms.nba.com`, `official.nba.com`, `pr.nba.com`, `statsdmz.nba.com`.

## Chronological log

| # | Source | What was verified | Outcome |
|---|---|---|---|
| 1 | `cdn.nba.com/…/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf` (chunks 0,1,2,12) | Full 11/13–11/16 slate: game numbers 34–42, 231–252; local+ET times; national TV; Cup `C` flags; legend (C/A/B/D/E); "AS OF AUGUST 13, 2026 \| SUBJECT TO CHANGE" header; prior-game dates for rest computation; **`R` flag undefined in legend (fl-04)**; **`at`-column formatting breaks from row 215+ (fl-10)** | ✅ primary schedule source, cross-checked |
| 2 | `www.nba.com/schedule` (chunks 0–2) | Game IDs `0022600034–0022600252`, venues (31), broadcasters incl. NBA TV/Prime/Peacock, Cup group labels, preview slugs (away-vs-home order), team records; **odds only behind client-side toggle (fl-16)**; **DET@MIA TV blank in PDF but NBA TV here (fl-09)** | ✅ live cross-check of every slate row |
| 3 | `ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf` | Latest report at cut. All 9 × 11/13 games fully transcribed; 11/14 partial (DAL/BKN/DET submitted; **DEN, NOP, CLE, MEM, CHI, MIN, MIA = NOT YET SUBMITTED**); 11/15–16 absent (**fl-06**) | ✅ primary injury source |
| 4 | Same path `_04_15PM`, `_01_15PM`, `_01_00PM` | Supersession history; Dejounte Murray Doubtful→Out between 01:15 and 04:15 stamps — proves freshness matters (G4) | ✅ superseded |
| 5 | `www.nba.com/stats/teams/traditional?Season=2026-27…` (5 chunks) | **All 30 teams**: GP, W, L, WIN%, PTS, +/- per game → OPPG = PTS − margin (arithmetic; direct OPPG confirmed on 6 team pages, MIL rounding diff → fl-08) | ✅ team-strength source |
| 6 | Team pages/rosters × 21 (`nba.com/team|stats/team|/roster` for NYK, WAS, IND, MIL, ORL, CLE, GSW, POR, UTA, OKC, NOP, MEM, HOU, SAC, LAC, SAS, …) | Season PPG/GP per player (injury production-at-risk), team PPG/OPPG headers, home/road splits for 5 teams (fl-03 workaround; HCA sample too small → hca-01) | ✅ partially complete → fl-13/Q-02/SG-02 |
| 7 | Player pages: Brunson, Towns, Wembanyama, Giannis, SGA, Sengun, Morant, Trae Young | Season PPG + **Last 5 Games** logs → prop lines + correlation inputs; **`/player/1629027/shai-gilgeous-alexander` renders Trae Young (fl-11)** | ✅ |
| 8 | `nba.com/game/nyk-vs-ind-0022600034`, `den-vs-nop-0022600231`, `ind-vs-phi-0022600236`, `cle-vs-nyk-0022600218`, `chi-vs-nyk-0022600177` | Preview/game pages render; completed game 11/11 linescore CLE 115–107 NYK (quarters, lead changes 3, times tied 6, officials, attendance) → game-flow worked example | ✅ |
| 9 | `ak-static.cms.nba.com/…/NBA-Player-Participation-Policy.pdf` (chunk 0) | Star-player rules: ≤1 star out per game, national-TV/Cup availability, B2B restrictions (age 35+ or >34k minutes), no shutdowns, fines regime | ✅ policy context |
| 10 | `official.nba.com/rulebook/` | Official rules index (Rules 1–14) for game-flow/OT context | ✅ |
| 11 | `official.nba.com/nba-official-relaunch/` | Documented injury cadence 1:30/5:30/8:30 p.m. ET → **mismatch with observed stamps (fl-05)** | ✅ flagged |
| 12 | `www.nba.com/stats/player/1628973/gamelog` | Returns "No data available" server-side → full-season logs unavailable; Last-5 tables used instead (limits correlation n → Q-06/Q-12) | ⚠ dead end |
| 13 | `cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json` | HTTP 500 (twice) | ⚠ do not retry (fl-12) |
| 14 | `stats.nba.com/stats/leaguestandingsv3…` | Fetch failed/blocked | ⚠ do not retry (fl-12) |
| 15 | `official.nba.com/injury-report/` | HTTP 404 → real path is `ak-static.cms.nba.com/referee/injury/` | ⚠ corrected (fl-14) |
| 16 | `www.nba.com/standings` | Page renders tiebreak text only, **no team rows** (JS) → records harvested from game pages + league table instead (fl-03) | ⚠ workaround applied |

## Verification cross-checks performed

- **Slate rows:** PDF row ↔ schedule page row ↔ game-preview URL slug — all 31 games agree on teams/order/time (venue check for the 8 rows where the PDF drops `at`, fl-10).
- **Records:** schedule-page records ↔ league-stats table ↔ game-page records — e.g. NYK 6-5, IND 4-8, MIL 1-11, SAS 10-2, UTA 1-11 all agree across ≥2 official surfaces.
- **OPPG derivation:** `PTS − margin` validated against direct team-page OPPG for NYK (103.5), WAS (115.8), IND (114.0), ORL (114.0), CLE (114.3) — exact; MIL off by 0.1 (fl-08).
- **Injury supersession:** 4 same-day report stamps compared; latest (05:00 PM) used for all status values.

## What was deliberately not collected

- Market odds (no authorized source — CLV blocked, Q-04/fl-16).
- Full-season game logs (endpoint dead — n stays 5 for player correlations, Q-12).
- 25 team home/road split pages for league HCA (queued as SG-03/Q-03, reviewer decision).
- Remaining roster PPGs for 13 OUT players (fl-13/Q-02/SG-02).
