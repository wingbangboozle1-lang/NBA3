# Open Questions — information needed before decisions can responsibly be made

Purpose (per project brief): a clear list of questions, information, and answers that must be
addressed before any decision can reasonably be made, based on information we **have** and
**do not** have. Each item names what is missing and a concrete way to discover it.

| # | Question / decision | What we HAVE | What we LACK | How to discover it | Blocks |
|---|---|---|---|---|---|
| Q1 | May we redistribute source data (results, injuries, ratings) on a public site? | Source URLs; standard site terms not yet reviewed for redistribution rights | Legal review of [NBA.com terms](https://www.nba.com/termsofuse), [NBA.com/Stats terms](https://www.nba.com/stats/help/terms), Sports-Reference terms | Legal/owner review of each site's terms of use; prefer linking over copying where required | Publishing any data-heavy page publicly (currently mitigated by linking + attribution) |
| Q2 | Is STRAT1/STRAT2 edge real **vs the market** (not just vs our own line)? | ROI vs own line at assumed −110; permutation tests | **Market odds feed** (closing/opening lines) or a manually recorded daily line file | Connect a licensed feed (e.g., sportradar-type), or record lines daily by hand into `data/raw/odds/` | Any real-money strategy decision; CLV tracking |
| Q3 | Are picks for Nov 15–16 final? | Schedule; 11/14 early injury submissions | Official injury reports for 11/15 & 11/16 (published day-before ~5 PM ET) | Re-pull [official report index](https://official.nba.com/) daily after ~5 PM ET and regenerate | Final bet decisions on those dates |
| Q4 | How much do injured players affect rotation minutes and production? | Official Out/Doubtful/Questionable lists; team per-game stats | Player-level minutes, usage, on/off impact data | Basketball-Reference game logs per player; or NBA.com/Stats player dashboards; or a licensing feed | Quantitative injury adjustment of lines; real player-props model |
| Q5 | Do STRAT1/STRAT2 pass the ≥100-bet sample gate? | 85 and 68 rated bets (this season) | Game-level history from earlier seasons | 2025-26 (and earlier) game results — Basketball-Reference monthly pages or a bulk dataset | Promoting strategies from "provisional" to "eligible" |
| Q6 | How should NBA Cup games be modeled (motivation, rotations)? | Cup flags in our game log (31 games flagged) | Evidence on Cup-specific rotation/scoring effects | Collect Cup vs non-Cup splits over the season; flag for review | Whether Cup games deserve a separate line adjustment |
| Q7 | What is the bankroll, risk policy, and jurisdiction for any real use? | Nothing on record | Owner's risk tolerance, bankroll size, legal jurisdiction | Direct input from the owner (see Suggestions page intake) | Any staking plan, bet sizing, or site disclaimers |
| Q8 | When should picks be finalized relative to lineup announcements? | Report timing (~5 PM ET day before); our flags | The owner's decision deadline (e.g., bet at open vs near tip) | Owner decision; then automate regeneration at that time | Pick-release schedule |
| Q9 | Can the totals model be fixed? (currently fails gates) | RMSE 19.3 ≈ naive; no pace data | Possessions/pace per team-game | Basketball-Reference per-poss data or NBA.com/Stats team dashboards | STRAT3 eligibility |
| Q10 | Is this season's extreme variance (blowout rate 25.3%, home win 51.1%) real or noise? | 174-game sample showing it | Longer window / prior seasons for comparison | Extend dataset (same as Q5); monitor weekly | Model recalibration choices (slope shrinkage, HCA) |

**Standing rule:** no value is inferred to fill these gaps. Where a decision needs missing
information, the item stays flagged rather than guessed.
