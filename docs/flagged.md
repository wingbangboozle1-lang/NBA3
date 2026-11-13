# Flagged for review

Everything here is something we could not verify, deliberately did not fill in, or found to be
contradictory on an official source. **None of it blocks publication** — it is published *here*,
with its source, so a reviewer can see the boundary between what is established and what is
assumed.

The governing rule: *if a value cannot be confirmed against an official source, the cell is left
blank and marked UNVERIFIED rather than estimated.*

| # | Area | Item | What the problem is | What it affects | How to resolve |
|---|---|---|---|---|---|
| 1 | Correlations | Player A points vs Player B points, same team, same game (PTS-PTS) | Requires per-player game logs, which were not captured. Left blank by policy. | Same-game parlays combining two player props cannot be priced. | Capture per-player game logs from nba.com/stats/players/boxscores. |
| 2 | Correlations | Player points vs player rebounds, same player, same game | Requires per-player game logs. Left blank by policy. | Same-game parlays combining two player props cannot be priced. | Capture per-player game logs from nba.com/stats/players/boxscores. |
| 3 | Correlations | Player points vs player assists, same player, same game (combo SGP) | Requires per-player game logs. Left blank by policy. | Same-game parlays combining two player props cannot be priced. | Capture per-player game logs from nba.com/stats/players/boxscores. |
| 4 | Player props | No distribution behind any projection | The pro-rata minutes assumption yields a point estimate of a mean only; no standard deviation, so no probability of exceeding a prop line. | Player-prop bets and prop parlays cannot be graded or sized. | Capture per-player game logs and fit a distribution per player per stat. |
| 5 | Injuries | Status-to-availability weights are our assumption | Out 0.00, Doubtful 0.25, Questionable 0.60, Probable 0.90, Available 1.00. The NBA publishes the status but not a probability. | The injury adjustment carries our assumption through to the originated lines. | Replace with observed participation rates by status once game logs exist. |
| 6 | Modelling | Win probabilities assume a normal margin distribution | P(home win) uses a normal CDF with the margin model's residual SD of {msd:.2f}. | Probabilities near the extremes are less reliable than the middle of the range. | Replace with the empirical residual distribution or a bootstrap. |
| 7 | Modelling | Originated totals are regulation equivalents | No expected overtime scoring is added; OT occurred in {otr:.1%} of games and is worth about {gap:.1f} points when it happens. | Totals are biased low by roughly {bias:.1f} points on average. | Decide on a convention and apply it consistently. |
| 8 | Modelling | Total model does not beat the naive baseline | Best total RMSE {trmse:.2f} vs {tbase:.2f} for the running league-average total. | Totals and total-based strategies rest on a model with no demonstrated skill. | Add possession-level inputs (four factors). |
| 9 | Validation | Out-of-sample sample is only {n_oos} games | After a 60-game burn-in, no strategy reaches the 100-bet gate. | Every strategy result is under-powered; nothing can be deployed on this evidence. | Re-run the same pipeline once another 150-200 games have been played. |
| 10 | Modelling | Home-court advantage is not statistically significant | Fitted at {hc:+.2f} points, p={hcp:.3f}, over {hg} non-neutral games. | The fitted value is used in every originated spread despite not being distinguishable from zero. | Monitor; consider shrinking toward a prior-season value. |
| 11 | Data irregularity | Unexpected rosters on official pages | Giannis Antetokounmpo on Miami, Anthony Davis on Washington, Paul George on Boston, James Harden on Cleveland, LaMelo Ball on Minnesota, Kevin Durant on Houston. | If any attribution is wrong, the team ratings inherit the error. | Spot-check two or three against official team roster pages. |
| 12 | Data irregularity | Anthony Edwards listed Out after 45- and 47-point games | Out (right knee arthroscopy) for 14 Nov, yet official game pages show 45 points on 21 Oct and 47 on 26 Oct. | His minutes vacuum is quantified as if he will not play. | Re-check the report on game day before using the Minnesota line. |
| 13 | Correlations | Cross-game parlay independence is an assumption | Not measured; {n_oos} games do not support a reliable estimate. | Cross-game parlays are priced as if legs were independent. | Measure on the residual matrix once the sample is larger. |

Severity index: high = blocks a capability; medium = distorts a number; low = cosmetic or
immaterial at current sample size.

- High severity: 6
- Medium severity: 6
- Low severity: 1
- Unverified correlation values left blank: 3

