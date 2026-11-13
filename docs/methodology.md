# Methodology and data provenance

## Verification rule

Three rules governed every number in this repository:

1. **A value may only be recorded if it was read from an official source.** The source URL is
   stored alongside the value.
2. **If a value cannot be confirmed from an official source, the cell is left blank and marked
   UNVERIFIED.** It is never inferred, estimated, or filled with a plausible number.
3. **Nothing is marked verified without a link to the official source that was checked.**

## Official sources used

| Data | Official source | What was taken |
|---|---|---|
| Final scores, game IDs | [https://www.nba.com/games?date=](https://www.nba.com/games?date=) | Every result, one page per date |
| Team efficiency, pace, records | [https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season](https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season) | OffRtg, DefRtg, NetRtg, Pace, eFG%, TS%, TOV%, OREB%, GP, W-L (all 30 teams) |
| Player production | [https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC](https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC) | Season per-game minutes and counting stats, top 31 by minutes |
| Injuries | [https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_15PM.pdf](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_15PM.pdf) | Player, team, status, reason (13-14 Nov) |
| Schedule | [https://www.nba.com/schedule](https://www.nba.com/schedule) | Upcoming game IDs, tip times, NBA Cup groupings |

**Not used:** no sportsbook, odds aggregator or third-party statistics site contributed any
number. All lines are originated.

## Integrity reconciliation

The strongest available check on a hand-built game log: count each team's games in our file and
compare with the official **GP** column on
[nba.com/stats/teams/advanced](https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season). Our log contains 348 team-games; the official table
says 348. **Difference: 0.**

| Team | Games in our log | Official GP | W-L (recomputed) | Official W-L | Unaccounted | Reconciliation |
|---|---|---|---|---|---|---|
| ATL | 12 | 12 | 7-5 | 7-5 | 0 | match |
| BKN | 11 | 11 | 3-8 | 3-8 | 0 | match |
| BOS | 12 | 12 | 10-2 | 10-2 | 0 | match |
| CHA | 12 | 12 | 4-8 | 4-8 | 0 | match |
| CHI | 10 | 10 | 1-9 | 1-9 | 0 | match |
| CLE | 12 | 12 | 6-6 | 6-6 | 0 | match |
| DAL | 12 | 12 | 7-5 | 7-5 | 0 | match |
| DEN | 10 | 10 | 6-4 | 6-4 | 0 | match |
| DET | 11 | 11 | 8-3 | 8-3 | 0 | match |
| GSW | 12 | 12 | 8-4 | 8-4 | 0 | match |
| HOU | 12 | 12 | 9-3 | 9-3 | 0 | match |
| IND | 12 | 12 | 4-8 | 4-8 | 0 | match |
| LAC | 10 | 10 | 2-8 | 2-8 | 0 | match |
| LAL | 13 | 13 | 11-2 | 11-2 | 0 | match |
| MEM | 11 | 11 | 7-4 | 7-4 | 0 | match |
| MIA | 11 | 11 | 5-6 | 5-6 | 0 | match |
| MIL | 12 | 12 | 1-11 | 1-11 | 0 | match |
| MIN | 12 | 12 | 9-3 | 9-3 | 0 | match |
| NOP | 12 | 12 | 4-8 | 4-8 | 0 | match |
| NYK | 11 | 11 | 6-5 | 6-5 | 0 | match |
| OKC | 12 | 12 | 8-4 | 8-4 | 0 | match |
| ORL | 11 | 11 | 4-7 | 4-7 | 0 | match |
| PHI | 13 | 13 | 10-3 | 10-3 | 0 | match |
| PHX | 11 | 11 | 5-6 | 5-6 | 0 | match |
| POR | 11 | 11 | 8-3 | 8-3 | 0 | match |
| SAC | 11 | 11 | 1-10 | 1-10 | 0 | match |
| SAS | 12 | 12 | 10-2 | 10-2 | 0 | match |
| TOR | 12 | 12 | 5-7 | 5-7 | 0 | match |
| UTA | 12 | 12 | 1-11 | 1-11 | 0 | match |
| WAS | 13 | 13 | 4-9 | 4-9 | 0 | match |

"Unaccounted" is games played minus wins minus losses, and is zero for every team — no result is
missing or duplicated. The recomputed W-L column is derived solely from our own scores and matches
the official W-L for all 30 teams, which independently confirms both the scores and the home/away
attribution in the log.

## Models

Three candidate models were fitted and compared walk-forward.

| Model | Margin | Selected |
|---|---|---|
| LM-A additive | `margin = (PPG_home + PAPG_away - lg) - (PPG_away + PAPG_home - lg)` | no |
| LM-B Massey | least squares on `margin = HCA + r_home - r_away` | no |
| LM-C blend | mean of LM-A and LM-B margins | **yes** |

Two total estimators were compared: T1 (additive, league-centred twice) and T2 (sum of the two
teams' own scoring rates). **T2 won** and is used for every published total.

### Walk-forward protocol

- Burn-in of 60 games; every graded prediction uses only games played strictly before it.
- Expanding window, refit at every step.
- Baseline: always predict the running mean home margin / running mean total.
- Metrics: bias, MAE, RMSE, paired test against the baseline, exact binomial on cover rate.

| Model | Margin RMSE | Margin baseline | Total RMSE | Total baseline |
|---|---|---|---|---|
| LM-A additive points model | 16.65 | 17.30 | 21.28 | 19.56 |
| LM-B Massey least-squares margin model | 16.45 | 17.30 | 20.35 | 19.56 |
| LM-C blend (A+B margins, T2 total) | 16.18 | 17.30 | 20.35 | 19.56 |

### Why the published line is not the efficiency model

A pace-and-rating model is better specified in principle:

```
E[home pts] = PACE x (OffRtg_home + DefRtg_away - OffRtg_league) / 100
```

but we hold only *season-to-date* ratings. Putting it through the same walk-forward backtest
would leak future games into the fit, so it cannot be validated from this session's data. The
**published line is LM-C, the model that was actually validated**; the efficiency estimate is
published beside it as a clearly labelled cross-check. See
[Originated Lines](../site/lines.html).

## Home-court advantage

Fitted by least squares over 173 non-neutral games: **+1.59 points**, two-sided
p=0.104, df=172. The Mexico City game (DEN vs IND, 7 Nov) is treated as neutral and
excluded. This sample does **not** establish home-court advantage at conventional thresholds;
the fitted value is used because it is the least-squares estimate, and the caveat is recorded
on the [flagged page](../site/flagged.html).

## Residuals

| Quantity | Value |
|---|---|
| Margin residual SD | 16.18 points |
| Total residual SD | 20.35 points |
| Variance in margins explained | 12.5% |

A single NBA game carries roughly 16 points of margin noise that no model removes. That is the
binding constraint on every strategy in this repository, and it is why the 95% interval on each
originated spread is about &plusmn;32 points.

