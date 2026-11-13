# NBA3 — NBA line origination and strategy system

A line-origination engine for the 2026-27 NBA season. It originates its own point spreads and
game totals from official NBA data, then tests betting strategies against those originated
lines — not against a sportsbook's prices.

**Live site:** <https://wingbangboozle1-lang.github.io/NBA3/>

## What it does

1. **Originates lines** for every upcoming game up to three days ahead, from official
   efficiency, pace and injury data. No market price is used anywhere in the calculation.
2. **Backtests** those lines walk-forward: 60-game burn-in, then every prediction made using
   only games played strictly before it.
3. **Grades strategies** against seven validation gates designed to strip out luck — sample
   size, statistical power, significance against the correct null, multiple-testing
   correction, and split-half stability.
4. **Measures correlations** for parlay construction, and leaves blank the ones it cannot
   measure rather than inventing them.
5. **Tracks injuries** into rotation minutes and, through minutes, into production — again
   leaving blank what it cannot source.
6. **Publishes** everything to GitHub Pages as a dashboard, with a source link on every row
   and a Flagged for Review page for anything unverified.

## The headline result

| | |
|---|---|
| Games verified | **174** (20 Oct – 12 Nov 2026), reconciling to 348 team-games with **zero** discrepancy |
| Margin model | RMSE **16.18** vs 17.30 for a league-average baseline — a real but modest edge |
| Total model | RMSE **20.35** vs 19.56 baseline — **no** improvement, reported as such |
| Strategies passing all gates | **0 of 8** |

Two strategies show a signal — fading our own totals of 235+ (21/24, p=0.0003) and backing road
favourites of 8+ (20/28, p=0.036) — but both are far below the 100-bet sample floor the gates
require. The honest reading is *under-powered, not disproven*. **Nothing here is deployable
today**, and the site says so on every relevant page.

## Repository layout

```
data/processed/   Verified inputs + model_output.json (the single source of truth)
model/            nbastats.py (pure-stdlib stats), build.py (pipeline), build_docs.py
docs/             Generated Markdown — executive summary, methodology, strategies, …
site/             build_site.py + generated HTML for GitHub Pages
COORDINATION.md   Multi-session task board, file-scope ownership, change requests
```

`docs/` and `site/` are **generated from `data/processed/model_output.json`**. Edit the
generators, not the output, or the two drift apart.

## Running it

```bash
python3 model/build.py        # data -> model_output.json
python3 model/build_docs.py   # model_output.json -> docs/*.md
python3 site/build_site.py    # model_output.json -> site/*.html
```

Pure Python 3.9+, standard library only. No network access is required to rebuild from the
captured data; re-capturing live data requires the `fetch_page` tool (the sandbox shell has no
outbound network).

## Sources

Every number traces to one of these official pages:

- [`nba.com/games?date=`](https://www.nba.com/games) — final scores and game IDs
- [`nba.com/stats/teams/advanced`](https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season) — OffRtg, DefRtg, NetRtg, Pace, GP, W-L
- [`nba.com/stats/players/traditional`](https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season) — season per-game player production
- [Official NBA injury report (PDF)](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_15PM.pdf) — player, team, status, reason
- [`nba.com/schedule`](https://www.nba.com/schedule) — upcoming game IDs, tip times, NBA Cup groups

No sportsbook, odds aggregator or third-party statistics site contributed any value.

## Verification policy

1. A value is only recorded if it was read from an official source, and the source is stored
   alongside it.
2. If a value cannot be confirmed from an official source, the cell is **left blank and marked
   UNVERIFIED**. It is never inferred, estimated, or filled with a plausible number.
3. Nothing is marked verified without a link to the official source that was checked.

Blank and flagged values are collected on the
[Flagged for Review](https://wingbangboozle1-lang.github.io/NBA3/flagged.html) page with their
sources, so a reviewer can see exactly where the boundary between evidence and assumption lies.

## Multi-session work

See [`COORDINATION.md`](COORDINATION.md) for the task board, file-scope ownership, change
requests and the environment constraints (no shell network, no third-party packages, blocked
JSON endpoints) that a new session needs before touching anything.

## Not betting advice

This is a research and engineering project. Nothing in it is betting advice, and the strategy
layer has not passed its own validation gates.
