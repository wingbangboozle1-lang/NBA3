# Site and system improvements — options for a reviewer

Each section states one problem, sets out two or three concrete fixes with the case for and
against each, and names a recommendation. **Nothing here has been implemented.** The purpose is
to let the choice be made deliberately rather than by whoever happens to be typing.

## A. Capture per-player game logs

**Problem.** Everything on the props and player-correlation side is blocked by the absence of
per-player game-by-game data. Four correlation cells are blank and no prop distribution exists.

| Option | What it is | For | Against |
|---|---|---|---|
| A1 | Scrape `nba.com/stats/players/boxscores` per date | Official source, already proven to work; ~4,000 rows for the season to date | Very slow — roughly 400 page fetches; needs chunking across sessions |
| A2 | **Sample the top 100 players by minutes only** | Covers the vast majority of prop market volume with about a quarter of the fetches | Deep-bench props remain unpriceable |
| A3 | Leave player props out of scope for now | Honest, fast, no new risk | Closes off the parlay and prop parts of the brief |

**Recommendation: A2.**

## B. Fix the totals model, which currently loses to a baseline

**Problem.** Best total RMSE is 20.35 against 19.56 for guessing the league average.
The side beats its baseline; the total does not.

| Option | What it is | For | Against |
|---|---|---|---|
| B1 | Add the four factors (eFG%, TOV%, OREB%, FT rate) | Directly targets the weakness; all inputs are official | More parameters to fit on a small sample |
| B2 | **Shrink team totals toward the league mean** | Cheap, quick, near-certain RMSE improvement | Improves accuracy without adding understanding |
| B3 | Publish the baseline as the total | Honest, no false confidence | Gives up on half the product |

**Recommendation: B2 now, B1 next.**

## C. Decide how the site should be refreshed

**Problem.** This build is a static snapshot. The brief asks for picks for every upcoming slate
up to three days ahead, which only stays true if the site is regenerated daily.

| Option | What it is | For | Against |
|---|---|---|---|
| C1 | **GitHub Actions cron that re-runs the pipeline and republishes** | Hands-off, fits GitHub Pages exactly, free | Scraping from Actions may be blocked or rate-limited |
| C2 | Manual regeneration at the start of each session | Simple, no new infrastructure | Stale whenever nobody runs it |
| C3 | Static archive plus a "generated at" banner | Honest about staleness | Does not meet the three-days-ahead requirement alone |

**Recommendation: C1 with C3's banner as a safety net.**

## D. Make the leaderboard a genuine competition

**Problem.** The brief asks for a leaderboard with rewards for the best strategies. Right now
there is one author and eight strategies, none of which pass.

| Option | What it is | For | Against |
|---|---|---|---|
| D1 | **Publish a strategy specification format and accept pull requests** | Turns the repo into the competition the brief describes | Needs a sandboxed runner to be safe |
| D2 | Keep it internal but auto-grade a wider candidate set | No security surface | Searching more rules makes G6 stricter, not weaker |
| D3 | Add a shadow leaderboard with paper results only | Builds the track record the gates demand | Nothing is deployable for weeks |

**Recommendation: D1 with D3 running underneath.**

## E. Widen and harden the data capture

**Problem.** Injury minutes impact is a floor because the captured minutes table covers only the
top 31 players, and several team reports were "NOT YET SUBMITTED".

| Option | What it is | For | Against |
|---|---|---|---|
| E1 | **Capture the full 465-row player table** | Removes an entire class of UNVERIFIED cells | Nine large page fetches per refresh |
| E2 | **Re-pull the injury report closer to tip-off** | Fewer stale or missing reports | Needs a second pull each day |
| E3 | Add official boxscores-advanced per date | Gives per-game team ratings, letting the model use form instead of the whole season | Two chunks per date; adds up over a season |

**Recommendation: E1 and E2 now, E3 next.**

