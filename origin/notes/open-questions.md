# Open questions: what we have, what we don't, what's blocked

## We have this, verified

| Asset | Detail |
|---|---|
| Every final score, 20 Oct – 12 Nov | 174 games, each read off nba.com/games for its own date |
| Official team efficiency and pace, all 30 teams | OffRtg, DefRtg, NetRtg, Pace, four factors, GP, W-L |
| Season per-game player production | Top 31 players by minutes |
| Official injury report, 13–14 Nov | Player, team, status, reason |
| Upcoming schedule | 31 games across three slates with game IDs, tip times, Cup groups |
| A working sourced line-origination model | Margin RMSE 16.18 vs 17.30 baseline |
| A validation harness with seven gates | Walk-forward, exact binomial, Benjamini-Hochberg |

## We need this, and here is how to get it

| Missing | What it blocks | How to get it | Priority |
|---|---|---|---|
| Per-player game logs | Player-prop pricing and every player-level correlation; four correlation cells are blank because of it | Scrape nba.com/stats/players/boxscores by date — see [suggestion A2](suggestions.md#a-capture-per-player-game-logs) | **high** |
| More graded games | No strategy reaches the 100-bet gate; only 114 out-of-sample games exist | Wait, then re-run the identical pipeline after another 150–200 games. No code changes needed | **high** |
| Possession-level team inputs per game | The total model loses to a naive baseline | Capture boxscores-advanced per date — [suggestion E3](suggestions.md#e-widen-and-harden-the-data-capture) | **high** |
| Injury report at tip-off, not 17:15 | 5 team reports read "NOT YET SUBMITTED" | Schedule a second pull 90 minutes before first tip — [suggestion E2](suggestions.md#e-widen-and-harden-the-data-capture) | medium |
| A decision on whether sportsbook prices may be used at all | Without a market price there is no such thing as an edge, only self-consistency | **Reviewer decision** | **high** |
| A decision on bankroll and staking | Determines whether a 53% strategy is worth running | **Reviewer decision**; a flat-stake default can be assumed and documented | medium |
| Confirmation that the unexpected rosters are correct | Giannis on Miami, Anthony Davis on Washington, Paul George on Boston, LaMelo Ball on Minnesota. If the source pages are wrong the ratings inherit the error | Spot-check against official team roster pages | medium |
| Whether overtime counts for totals | Our totals are regulation equivalents, biased low by about 1.4 points | **Reviewer decision**; both conventions are defensible but must be consistent | low |

## Decisions that need a human

1. **May we look at sportsbook prices at all?** Not to copy them — the brief rules that out —
   but to *compare*. Without a market price there is no such thing as an edge, only
   self-consistency. Every strategy here is graded against our own line, which is honest but is
   not the same as being profitable.
2. **Do we want the leaderboard open to outside contributors?** A competition with rewards
   implies yes, which implies a sandboxed runner. See [suggestion D](suggestions.md#d-make-the-leaderboard-a-genuine-competition).
3. **How should a "reward" be defined?** Raw hit rate, return on a flat stake, or risk-adjusted
   return? The gates currently test hit rate only.
4. **What is the stake?** Nothing is deployable on the current evidence, but the harness needs a
   staking rule before it can report anything a reviewer would act on.

Until question 1 is answered, the most accurate description of this system is: **a verified,
self-consistent line-origination engine with an unproven strategy layer.** That is a real
achievement, and it is not yet a betting system.

