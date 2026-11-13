# Strategies and validation gates

## The gates

| Gate | Requirement | Why |
|---|---|---|
| G1 provenance | Every input is an official NBA figure or arithmetic on one | Blocks anything trained on a number we cannot source |
| G2 no look-ahead | Every prediction uses only games played strictly before it | A model that has seen the future always looks good |
| G3 sample size | At least 100 graded bets | Below 100 a 55% hit rate is inseparable from noise at 80% power |
| G4 power | Report the n the observed effect would need | Shows the shortfall in the same units as G3 |
| G5 significance | Two-sided p < 0.05 against the **correct** null | Exact binomial. For parlays the null is the independence-implied joint rate, not 0.50 |
| G6 multiple testing | Survives Benjamini-Hochberg at FDR 0.05 | Eight candidates were searched; the bar rises accordingly |
| G7 stability | Direction of the edge holds in both halves | An effect in only one half is usually a calendar artefact |

## Leaderboard

| ID | Strategy | Bets | Wins | Hit rate | p | Null | Split-half | G3 | G5 | G6 | G7 | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S5 | Fade totals of 235+ | 24 | 21 | 87.5% | 0.0003 | 0.500 | 0.800 / 1.000 | FAIL | PASS | PASS | PASS | PROVISIONAL - signal present, sample under-powered |
| S4b | Back road favourites of 8+ | 28 | 20 | 71.4% | 0.0357 | 0.500 | 0.688 / 0.750 | FAIL | PASS | FAIL | PASS | PROVISIONAL - signal present, sample under-powered |
| S4 | Fade home favourites of 8+ | 36 | 21 | 58.3% | 0.4050 | 0.500 | 0.550 / 0.625 | FAIL | FAIL | FAIL | PASS | INCONCLUSIVE - sample too small |
| S5b | Back totals of 218 or fewer | 11 | 6 | 54.5% | 1.0000 | 0.500 | 0.667 / 0.400 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE - sample too small |
| S3 | Rest differential >= 2 days | 17 | 9 | 52.9% | 1.0000 | 0.500 | 0.444 / 0.625 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE - sample too small |
| S1 | Originated spread - home side | 114 | 58 | 50.9% | 0.9254 | 0.500 | 0.508 / 0.509 | PASS | FAIL | FAIL | PASS | FAILED - no evidence of edge |
| S2 | Originated total - over | 114 | 49 | 43.0% | 0.1598 | 0.500 | 0.443 / 0.415 | PASS | FAIL | FAIL | PASS | FAILED - no evidence of edge |
| S6 | Same-game parlay: home cover AND over | 114 | 28 | 24.6% | 0.4966 | 0.219 | 0.262 / 0.226 | PASS | FAIL | FAIL | PASS | FAILED - no evidence of edge |

## Rules

- **S5** — When our originated total is 235 or more, take the under.
- **S4b** — When our originated spread has the away team favoured by 8 or more, take the away side.
- **S4** — When our originated spread has the home team favoured by 8 or more, take the away side.
- **S5b** — When our originated total is 218 or less, take the over.
- **S3** — When one team has at least two more days of rest than the other, take that team against our originated spread.
- **S1** — Take the home side against our own originated spread in every rated game (self-consistency test).
- **S2** — Take the over against our own originated total in every rated game (self-consistency test).
- **S6** — Two-leg correlated parlay built on our own originated spread and total.

## Reading the result honestly

**Nothing passes.** That is the finding, and it is the most useful thing on this page.

- **S5 — fade our own totals of 235+.** 21 of 24 unders went under (p=0.0003). The
  threshold was pre-specified at 235 before the backtest ran, which is the right discipline, but
  24 bets is roughly a fifth of what the gate demands; 56 bets would be needed to call
  the observed effect at 80% power. The result is also exactly what regression to the mean
  produces when a model is built from noisy season averages.
- **S4b — back road favourites of 8+.** 20 of 28 covers (p=0.0357), but it does not
  survive Benjamini-Hochberg correction across the eight candidates (G6), so it is not treated
  as established.

Neither should be traded. Both should be re-run automatically once the season supplies the
sample they need; the pipeline does this with no code changes.

## Rewards and the leaderboard

The brief asks for a leaderboard with rewards for the best strategies. Nothing clears the gates,
so no reward is payable on this evidence. The options for turning this into a genuine
competition — open contribution with automatic grading, a wider internal candidate set, or a
shadow paper-trading leaderboard — are set out in [Site Improvements](suggestions.md#d-make-the-leaderboard-a-genuine-competition).

