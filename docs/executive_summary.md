# Executive Summary — NBA3 Line Origination Project

**Date:** 2026-11-13 · **Prepared by:** session `arena-0a016df8` · **Live site:** https://wingbangboozle1-lang.github.io/NBA3/

## What this project is
A complete, reproducible pipeline that **originates our own NBA lines** (spreads, totals, fair
moneylines, win probabilities) for every game in the next 3 days, **validates betting strategies
through explicit gates designed to remove luck**, **measures correlations** for parlay risk, and
publishes everything on a verified, source-linked dashboard. It also tracks injuries from the
official NBA injury report and analyzes game flow.

## What was built
1. **Verified dataset** — 174 regular-season games (2026-27 through Nov 12), reconciled
   30/30 against an independent ratings table; 22 upcoming games (Nov 13–16) with times;
   the official NBA injury report (11/13, 5:00 PM ET) encoded in full; 2025-26 final team
   ratings as the model prior.
2. **Line origination engine** — two independent models (last-season prior + in-season Elo)
   blended, with expanding-window recalibration; slate-safe (no same-day leakage).
3. **Validation gates** — sample size, calibration (Brier), walk-forward ROI at −110,
   permutation tests (2,000 shuffles), drawdown, and correlation caps.
4. **Picks for the 3-day window** — 22 games, each with strategy-eligibility status and
   availability flags; 1 research-only parlay combo; 10 players / 30 originated prop markets.
5. **Dashboard** — landing page + 11 subpages; every factual row carries a source link;
   unverified values are blank and published on the Flagged for Review page.

## Headline results
| Item | Result | Status |
|---|---|---|
| Data integrity | 174 games; 30/30 records reconcile; 1 corrupted fetch caught & re-verified | Verified |
| Win-probability calibration | Brier 0.2001 (baseline 0.25) | Good |
| STRAT1 (high-conviction spread singles) | n=85, ROI +48.2% @ −110, perm p<0.0005 | **Provisional** — passes all gates except minimum sample (needs ≥100 bets) |
| STRAT2 (moneyline band) | n=68, ROI +23.5%, perm p=0.011 | **Provisional** — same caveat |
| STRAT3 (totals) | n=14, ROI −4.6% | **Not eligible** — failed |
| STRAT4 (2-leg parlays) | n=15, ROI +14.6% | **Not eligible** — failed |
| Same-game margin↔total correlation | −0.018 (noisy) | Measured, low confidence |

## The honest caveats (read before acting)
- **No licensed odds feed is connected.** ROI is measured against *our own* line at an assumed
  −110. This proves model skill; it does **not** prove market-beating profit. Closing-line
  value is unmeasurable until a feed exists.
- Injury reports for Nov 15–16 were **not yet published** at generation time; picks for those
  days carry "report pending" flags and must be re-checked after reports drop (~5 PM ET the
  day before).
- Player props are a **prototype** with no validated backtest.
- No player-level impact data (on/off, usage) exists in this project, so injuries trigger
  **flags**, never silent numeric adjustments.

## What we recommend next (highest value first)
1. **Connect a licensed odds feed** (or a manually recorded daily closing-line file) → unlocks
   CLV tracking and true market validation. *(Blocked by Q1/Q2 — see Open Questions.)*
2. **Load 2025-26 game-level history** → pushes STRAT1/STRAT2 past the sample gate or correctly
   kills them.
3. **Add possessions/pace data** → rebuild the totals model (STRAT3 failed with the current one).
4. **Regenerate picks daily after the injury report drops** (automation ready; needs scheduling).
5. **Review the Open Questions page** — ten decisions cannot be made responsibly until listed
   information exists.
