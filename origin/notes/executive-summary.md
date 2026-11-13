# Executive summary

**Season 2026-27 &middot; results verified through 2026-11-12 &middot; generated 2026-11-13T23:10:29Z**

## What this system is

NBA3 originates its own point spreads and game totals for every NBA game, then tests betting
strategies against those originated lines rather than against a sportsbook's prices. Every
input is read from an official NBA source; every derived number is reproducible by running
`model/build.py`. Nothing is copied from a book, an odds aggregator, or a third-party
statistics site.

## Headline findings

| Finding | Number | Source |
|---|---|---|
| Games verified | 174 (2026-10-20 to 2026-11-12) | [nba.com/games](https://www.nba.com/games?date=) |
| Team-games reconciled against official GP | 348 vs 348, **mismatch 0** | [teams/advanced](https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season) |
| Out-of-sample games graded | 114 (walk-forward, no look-ahead) | derived |
| Margin model RMSE | 16.18 vs 17.30 baseline (6.5% better) | derived |
| Total model RMSE | 20.35 vs 19.56 baseline (**worse**) | derived |
| Fitted home-court advantage | +1.59 pts, p=0.104 (not significant) | derived |
| Spread/total residual correlation | r=+0.091, 95% CI [-0.09, +0.27] | derived |
| Strategies passing all gates | **0 of 8** | derived |
| Injury rows marked Out/Doubtful | 85 | [injury PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_15PM.pdf) |

## The six things that matter

1. **The data reconciles exactly.** 174 games, 348 team-games, zero discrepancy against the
   official games-played column for all 30 teams. Per-team detail is in
   [Data & Sources](data.md#integrity-reconciliation).

2. **The side beats its baseline; the total does not.** Walk-forward over 114
   out-of-sample games, the blend model cuts margin RMSE from 17.30 to 16.18
   points. For totals our best model is *worse* than guessing the league average
   (20.35 vs 19.56), and we report that rather than hiding it.

3. **No strategy clears every validation gate.** 0 of 8 pass. Two are
   provisionally interesting: fading our own totals of 235 and above (21/24, p=0.0003)
   and backing road favourites of 8 or more (20/28, p=0.0357). Both are far below the
   100-bet sample floor. The honest reading is *under-powered*, not *disproven* — and neither
   should be traded.

4. **The parlay correlation we can measure is small.** Residual correlation between our own
   spread and our own total is r=+0.091 with a 95% interval that contains zero. Player-level
   correlations — the ones that actually drive same-game parlays — are blank, because the
   per-player game logs needed to compute them were not captured. We left them blank rather
   than estimating them.

5. **Injuries move minutes, and we quantify what we can.** 85 player-rows are marked Out or
   Doubtful across the 13-14 Nov reports. Where a player appears in the official minutes table
   we convert status to minutes at risk; where he does not, the cell is blank and flagged.

6. **Home court is small and not significant this season.** +1.59 points, p=0.104.
   We use the fitted value because it is the least-squares estimate, but this sample does not
   establish home-court advantage at all.

## Bottom line

The pipeline is built, sourced and reproducible, and it produces defensible originated lines
for every game in the next three days. It has **not** yet produced a strategy that survives its
own validation gates. Deploying any of the provisional signals with real money today would be
betting on a small sample, not on demonstrated skill.

The single highest-value next step is not a better model — it is **more games**. The pipeline
requires no code changes to re-run once the season supplies them.

## Originated lines: all 31 upcoming games

| Date | Time ET | Matchup (away @ home) | Spread (home) | Total | 95% &plusmn; | Source |
|---|---|---|---|---|---|---|
| 2026-11-13 | 7:00 PM | NYK @ IND | +7.6 | 221.9 | &plusmn;39.9 | [game](https://www.nba.com/game/nyk-vs-ind-0022600034) |
| 2026-11-13 | 7:00 PM | MIL @ ORL | -9.6 | 215.2 | &plusmn;39.9 | [game](https://www.nba.com/game/mil-vs-orl-0022600035) |
| 2026-11-13 | 8:00 PM | CLE @ MIA | +4.9 | 232.1 | &plusmn;39.9 | [game](https://www.nba.com/game/cle-vs-mia-0022600036) |
| 2026-11-13 | 8:00 PM | ATL @ CHI | +15.4 | 231.6 | &plusmn;39.9 | [game](https://www.nba.com/game/atl-vs-chi-0022600037) |
| 2026-11-13 | 8:00 PM | MEM @ NOP | +12.1 | 234.8 | &plusmn;39.9 | [game](https://www.nba.com/game/mem-vs-nop-0022600038) |
| 2026-11-13 | 8:30 PM | UTA @ HOU | -21.4 | 222.0 | &plusmn;39.9 | [game](https://www.nba.com/game/uta-vs-hou-0022600039) |
| 2026-11-13 | 9:30 PM | GSW @ SAS | -3.0 | 238.5 | &plusmn;39.9 | [game](https://www.nba.com/game/gsw-vs-sas-0022600040) |
| 2026-11-13 | 10:00 PM | POR @ SAC | +19.4 | 227.8 | &plusmn;39.9 | [game](https://www.nba.com/game/por-vs-sac-0022600041) |
| 2026-11-13 | 10:30 PM | OKC @ LAC | +10.0 | 223.3 | &plusmn;39.9 | [game](https://www.nba.com/game/okc-vs-lac-0022600042) |
| 2026-11-14 | 7:00 PM | DEN @ NOP | +9.5 | 231.4 | &plusmn;39.9 | [game](https://www.nba.com/game/den-vs-nop-0022600231) |
| 2026-11-14 | 7:30 PM | DAL @ CLE | -0.4 | 229.6 | &plusmn;39.9 | [game](https://www.nba.com/game/dal-vs-cle-0022600232) |
| 2026-11-14 | 8:00 PM | DET @ MIA | +9.2 | 231.3 | &plusmn;39.9 | [game](https://www.nba.com/game/det-vs-mia-0022600233) |
| 2026-11-14 | 8:00 PM | BKN @ MEM | -12.1 | 228.1 | &plusmn;39.9 | [game](https://www.nba.com/game/bkn-vs-mem-0022600234) |
| 2026-11-14 | 8:00 PM | CHI @ MIN | -29.2 | 232.6 | &plusmn;39.9 | [game](https://www.nba.com/game/chi-vs-min-0022600235) |
| 2026-11-15 | 1:00 PM | IND @ PHI | -4.8 | 222.7 | &plusmn;39.9 | [game](https://www.nba.com/game/ind-vs-phi-0022600236) |
| 2026-11-15 | 4:00 PM | LAL @ PHX | +9.5 | 233.9 | &plusmn;39.9 | [game](https://www.nba.com/game/lal-vs-phx-0022600237) |
| 2026-11-15 | 4:30 PM | CHA @ LAC | -8.3 | 210.8 | &plusmn;39.9 | [game](https://www.nba.com/game/cha-vs-lac-0022600238) |
| 2026-11-15 | 5:00 PM | SAS @ UTA | +20.3 | 225.8 | &plusmn;39.9 | [game](https://www.nba.com/game/sas-vs-uta-0022600239) |
| 2026-11-15 | 6:00 PM | NYK @ TOR | +2.8 | 224.5 | &plusmn;39.9 | [game](https://www.nba.com/game/nyk-vs-tor-0022600241) |
| 2026-11-15 | 6:00 PM | DAL @ BOS | -7.4 | 227.4 | &plusmn;39.9 | [game](https://www.nba.com/game/dal-vs-bos-0022600240) |
| 2026-11-15 | 7:00 PM | HOU @ WAS | +17.2 | 225.4 | &plusmn;39.9 | [game](https://www.nba.com/game/hou-vs-was-0022600242) |
| 2026-11-15 | 8:00 PM | ATL @ MIL | +14.1 | 225.0 | &plusmn;39.9 | [game](https://www.nba.com/game/atl-vs-mil-0022600243) |
| 2026-11-15 | 9:00 PM | OKC @ SAC | +16.7 | 219.4 | &plusmn;39.9 | [game](https://www.nba.com/game/okc-vs-sac-0022600244) |
| 2026-11-16 | 7:00 PM | ORL @ BOS | -14.6 | 222.7 | &plusmn;39.9 | [game](https://www.nba.com/game/orl-vs-bos-0022600245) |
| 2026-11-16 | 7:00 PM | MEM @ WAS | +11.7 | 227.9 | &plusmn;39.9 | [game](https://www.nba.com/game/mem-vs-was-0022600247) |
| 2026-11-16 | 7:00 PM | CHI @ CLE | -17.6 | 229.7 | &plusmn;39.9 | [game](https://www.nba.com/game/chi-vs-cle-0022600246) |
| 2026-11-16 | 7:30 PM | HOU @ MIA | +14.0 | 231.1 | &plusmn;39.9 | [game](https://www.nba.com/game/hou-vs-mia-0022600249) |
| 2026-11-16 | 7:30 PM | PHI @ BKN | +5.5 | 221.3 | &plusmn;39.9 | [game](https://www.nba.com/game/phi-vs-bkn-0022600248) |
| 2026-11-16 | 8:00 PM | GSW @ NOP | +15.9 | 236.2 | &plusmn;39.9 | [game](https://www.nba.com/game/gsw-vs-nop-0022600251) |
| 2026-11-16 | 8:00 PM | POR @ MIN | -5.2 | 238.9 | &plusmn;39.9 | [game](https://www.nba.com/game/por-vs-min-0022600250) |
| 2026-11-16 | 9:00 PM | PHX @ DEN | -5.5 | 226.2 | &plusmn;39.9 | [game](https://www.nba.com/game/phx-vs-den-0022600252) |

Full detail, including the efficiency cross-check and per-team injury counts, is on the
[lines page](../lines.html).

