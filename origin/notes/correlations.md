# Correlations

Correlation decides whether a same-game parlay is fairly priced. If two legs are positively
correlated the joint probability exceeds the product of the legs, and a book pricing the parlay
as independent is giving value away — and vice versa.

## Measured

| Pair | Statistic | Value | 95% CI | n | Interpretation |
|---|---|---|---|---|---|
| Home points vs away points (same game) | Pearson r | +0.128 | [-0.02, +0.27] | 174 | Computed from the 174 verified final scores. |
| Originated-spread residual vs originated-total residual | Pearson r | +0.091 | [-0.09, +0.27] | 114 | Residuals are out-of-sample (walk-forward). This is the key input for same-game parlays that combine a side with a total. |
| Cover (vs our spread) AND over (vs our total) | phi (binary) | +0.109 | — | 114 | Joint hit rate 0.246 vs 0.219 under independence. |
| Player A points vs Player B points, same team, same game (PTS-PTS) | Pearson r | *blank — UNVERIFIED* | — | — | Requires per-player game logs, which were not captured. Left blank by policy. |
| Player points vs player rebounds, same player, same game | Pearson r | *blank — UNVERIFIED* | — | — | Requires per-player game logs. Left blank by policy. |
| Player points vs player assists, same player, same game (combo SGP) | Pearson r | *blank — UNVERIFIED* | — | — | Requires per-player game logs. Left blank by policy. |
| Two legs in different games (cross-game parlay) | Pearson r | +0.000 | — | None | Not measured on this sample. Independence is an ASSUMPTION, not a verified result; treat as unverified. |

## Same-game parlay: our spread + our total

| Quantity | Value |
|---|---|
| Leg 1 hit rate (home cover vs our spread) | 50.9% |
| Leg 2 hit rate (over vs our total) | 43.0% |
| Independence-implied joint rate | 21.9% |
| **Observed joint rate** | **24.6%** |
| Gap | +2.7% |

Under independence both legs would land 21.9% of the time. In 114 out-of-sample games they
actually landed 24.6% of the time. The gap points towards *positive* correlation, but the
residual correlation itself (r=+0.091) has a 95% interval containing zero, so this is
suggestive, not established.

## What we could not measure

The player-prop correlations that drive most same-game parlays are blank in the table above.
Computing them requires per-player game logs, which were not captured in this session. They were
left blank and flagged rather than filled with plausible numbers, because a fabricated
correlation is worse than no correlation: it gets priced into parlays.

Cross-game parlay independence is likewise an **assumption**, not a measurement. 114 games do
not support a reliable estimate of the correlation between two games on the same night.

