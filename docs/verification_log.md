# Verification Log (line-by-line)

Rule: every factual value published anywhere carries a link to its source; anything not
confirmable from a cited source is left blank and published on the Flagged for Review page.

## Data verified
| Item | Rows | Method | Source |
|---|---|---|---|
| 2026-27 game results (Oct 20 – Nov 12) | 174 | Manually transcribed from monthly schedule pages; per-team records reconciled 30/30 vs independent ratings table | [BBR Oct](https://www.basketball-reference.com/leagues/NBA_2027_games-october.html) · [BBR Nov](https://www.basketball-reference.com/leagues/NBA_2027_games-november.html) · [BBR ratings](https://www.basketball-reference.com/leagues/NBA_2027_ratings.html) |
| Nov 6 slate re-verification (incl. TOR@MIL) | 9 | Daily boxscores page; quarter scores captured | [BBR boxscores Nov 6](https://www.basketball-reference.com/boxscores/?month=11&day=6&year=2026) |
| Upcoming schedule Nov 13–16 | 22 | Same monthly schedule pages (rows with empty scores = unplayed) | [BBR Nov](https://www.basketball-reference.com/leagues/NBA_2027_games-november.html) |
| Team ratings (2026-27 as-of; 2025-26 final) | 30+30 | Transcribed from ratings tables; W/L used as reconciliation target | [2027 ratings](https://www.basketball-reference.com/leagues/NBA_2027_ratings.html) · [2026 ratings](https://www.basketball-reference.com/leagues/NBA_2026_ratings.html) |
| Injury report (11/13 5:00 PM ET) | 60+ entries | Transcribed from the official PDF (2 pages) | [Official PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf) |
| Player season averages (props, top 25) | 15 used | Transcribed from per-game table | [BBR per game](https://www.basketball-reference.com/leagues/NBA_2027_per_game.html) |

## Irregularities found & handled
1. **Corrupted fetch row (Nov 6 TOR@MIL):** the monthly page's score cells were dropped at a
   content-chunk boundary; an initial value was inferred — **flagged immediately**, then the
   game was re-verified from the daily boxscores page (TOR 121 @ MIL 107 confirmed). Stored
   note marks the verification event.
2. **OT vs note conflation:** early quick-stats script counted "NBA Cup" notes as OT, showing
   16.7% OT. Root-caused and fixed in `pipeline/build_data.py`; true OT rate is 9/174 = 5.2%.
3. **ROI accounting bug:** original backtest subtracted winning stakes twice, showing −30%
   ROI on a 76% win-rate strategy (mathematically impossible). Fixed; audit trail in git.
4. **Same-day leakage:** initial walk-forward updated Elo after every game; games within a
   slate are simultaneous. Fixed to date-batch updates; results re-verified.
5. **Unofficial-source date labels:** some aggregator pages label Nov 12 games as "Nov 13"
   (timezone/caching). Basketball-Reference per-day boxscore links were used as tiebreaker.
6. **Team abbreviation drift:** official injury PDF uses BKN; BBR uses BRK (also CHO/CHA,
   PHO/PHA). Normalized with a note in the injury JSON.

## Unverified / blank by rule (see Flagged for Review page)
- Market odds, closing lines, CLV — **no feed** (blank).
- Player rotation minutes & on/off impact — **no data** (blank).
- Injury reports for Nov 15–16 — **not yet published** (blank, flagged pending).
- Nov 14 team submissions marked "NOT YET SUBMITTED" in the official report (left as-is).
- Model outputs are labeled as originated everywhere; they are never mixed into sourced columns.
