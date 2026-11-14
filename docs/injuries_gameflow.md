# Injuries, Rotation Minutes & Game-Flow Analysis

**Injury source (official):** [NBA Injury Report 11/13/26 5:00 PM ET](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf) · **Results source:** [Basketball-Reference 2026-27 schedule](https://www.basketball-reference.com/leagues/NBA_2027_games-november.html) (retrieved 2026-11-13)

## 1. How injuries affect rotation minutes & production (what we can and cannot say)
**We can verify (official report):** who is Out / Doubtful / Questionable per game, with reasons.

**We cannot yet quantify (flagged, not guessed):** the minutes/production redistribution to
remaining rotation players. That requires player-level minutes, usage and on/off data that this
project does not hold (Open Question Q4). Therefore lines are **not** numerically adjusted for
injuries; affected games are **flagged** and picks are held pending lineups.

### Availability picture for the 3-day window (official report only)
| Game (date) | Notable availability (official report) | Impact flag |
|---|---|---|
| MIL@ORL (11/13) | ORL: Banchero **Out** (R high ankle sprain), Isaac Out, Suggs Q, da Silva Q; (Banchero played only 2 games this season per BBR) | High |
| NYK@IND (11/13) | IND: Haliburton **Out** (L hamstring strain), Sheppard Out, Furphy Out; McConnell Probable, Nesmith Q | High |
| CLE@MIA (11/13) | CLE: **Mobley Out** (L great toe sprain), Merrill Out; MIA: Antetokounmpo Available (wrist), Thompson Probable | High |
| MEM@NOP (11/13) | NOP: Murphy III Out, Murray Out, Missi Out, Mathurin Q; MEM: Edey Out, Pippen Jr. Out, Post Out (concussion) | High |
| UTA@HOU (11/13) | UTA: **Markkanen Out** (R hand fracture), Jackson Jr. Out (MCL), Nurkic Out; HOU: Adams Out, Capela Out, Smart Out (suspension) | High |
| GSW@SAS (11/13) | GSW: **Curry Out** (R oblique tear), Butler III Out, Moody Out, Porzingis Out; SAS: Fox Q, Vassell Q, Harris Out | High |
| POR@SAC (11/13) | POR: **Morant Out** (L hamstring), Sharpe Out, Krejci Out; SAC: Simmons Out, Achiuwa Out | High |
| OKC@LAC (11/13) | OKC: **Holmgren Out** (knee recovery), Wallace Out, J. Williams Out, Jaylin Williams Out; LAC: Beal Out, B. Ingram Out | High |
| DEN@NOP (11/14) | Both teams NOT YET SUBMITTED at report time | Pending |
| DAL@CLE (11/14) | DAL: Lively II Out, Biberovic Out, Christie Q, Martin Available; CLE NOT YET SUBMITTED | Pending |
| BKN@MEM (11/14) | BRK: six G League/illness entries; MEM NOT YET SUBMITTED | Pending |
| CHI@MIN (11/14) | Both NOT YET SUBMITTED | Pending |
| DET@MIA (11/14) | DET: **Duren Out** (R hamstring), Joe Out; MIA NOT YET SUBMITTED | Pending |
| Nov 15–16 games | Reports not yet published (day-before ~5 PM ET) | Pending |

## 2. Game-flow analysis (from the verified 174-game log)
| Metric (2026-27 through 11/12) | Value | Note |
|---|---|---|
| Average total | 226.8 pts (sd 19.2) | Computed from log |
| Home win rate | 51.1% | Computed |
| Average home margin | +1.62 | Low vs typical NBA home edge (~+2.4 historically) — monitored |
| OT rate | 9/174 = 5.2% | Normal range |
| Blowout rate (≥20-pt margin) | 25.3% | **High** vs typical seasons — season is unusually variance-heavy |
| Back-to-back win rate | 29/61 = 47.5% | vs 50.9% on 3+ days rest; small sample (n=61), not significant |
| Scoring by quarter (Nov 6, 9-game sample) | Q1 57.6 · Q2 58.8 · Q3 53.6 · Q4 57.7 | Q3 dip consistent with halftime adjustments; single-day sample, illustrative only |

### What this means for lines
- **High-variance season:** bigger errors possible on any single originated line; the
  calibration layer partially absorbs this. Treat LOW-confidence lines (<4-pt edges) as
  coin-flips.
- **B2B effect:** −3.6 pp win-rate dip observed but not statistically significant — no
  numeric adjustment; noted per pick (rest data is in the pipeline for future models).
- **Totals:** totals strategy failed validation this week (n=14) — the game-flow table is
  context, not a betting signal.

## 3. Rotation-minute tracking — how this becomes possible (proposal)
1. Ingest per-player game logs (minutes per game) — Basketball-Reference player pages (Q4).
2. Compute each injured player's season minutes share and the team's observed minutes
   redistribution in games they missed (this season already supplies such games for
   Banchero, Haliburton, Curry, Morant, Holmgren, Markkanen…).
3. Translate minutes shifts into team scoring/margin deltas with regression — then, and only
   then, apply numeric injury adjustments to originated lines.
4. Gate the injury-adjusted model separately (same gates as strategies).
