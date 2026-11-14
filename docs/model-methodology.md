# Model methodology

Long-form companion to `methodology.html`. Every number quoted here is produced by
`scripts/model.py` from `scripts/raw_data.py`; nothing is typed by hand into a page.

Regenerate everything with:

```
python3 scripts/model.py        # data/*.json
python3 scripts/build_site.py   # *.html
python3 scripts/validate_site.py
```

---

## 1. What this model is, and what it is not

It is a **line-origination model**. Given published team efficiency ratings, it produces its
own spread, total and win probability for a game, and then compares that number with a live
market snapshot.

It is **not** a betting system. Three things are missing that a betting system requires:
historical closing prices (to measure return), a minutes model (to price props), and
injury adjustment (to price the roster actually fielded). Each is flagged in the UI and on
`review.html`.

## 2. Inputs and tiers

| Input | Source | Tier | Used for |
|---|---|---|---|
| Team ORtg / DRtg / pace / W-L / MOV / SRS | Basketball-Reference `NBA_2027.html` | TRUSTED-2° | every model number |
| Completed game results, 2026-11-01 → 11-12 | Basketball-Reference November game log | TRUSTED-2° | measured constants, correlation, calibration |
| 72-hour slate, game IDs, tip times, venues | nba.com schedule + ESPN events index | OFFICIAL | the slate, and links |
| Spread / total / moneyline, open + current | one provider, via ESPN core odds | MARKET | every edge calculation |
| Player statuses | NBA official injury PDF, 11/13/26 05:00 PM | OFFICIAL | injury exposure, signal rejection |
| Prop lines and two-way prices | ESPN `propBets` for one game | MARKET | quoted and de-vigged only |
| Athlete identities | ESPN per-athlete endpoint | TRUSTED-2° | naming the 5 published prop rows |

The league does not publish team efficiency ratings in a machine-readable form reachable
from this environment, which is why ratings come from a secondary source. That is disclosed
on every page that uses them.

## 3. Measured constants

The first version of this model asserted `sd_margin = 12.4`. That was wrong by about 40%,
and it was wrong in the direction that makes a model overconfident. Every constant below is
now **computed** from the 86-game sample at load time.

| Constant | Value | 95% CI | n |
|---|---|---|---|
| Home margin (mean) | **+1.51** | −2.17 … +5.19 | 86 |
| Margin sd | **17.15** | — | 86 |
| Game total (mean) | **225.98** | 221.98 … 229.97 | 86 |
| Total sd | **18.62** | — | 86 |
| Home win rate | **0.500** (43/86) | — | 86 |

Two things follow immediately, and both are published rather than buried:

1. **The home edge is not established.** The interval spans zero. A 12-day window cannot
   settle a league-wide effect that is a couple of points. The model uses the point estimate
   and discloses the interval; it does not claim home court is worth 1.51 points as fact.
2. **Outcomes are much wider than intuition suggests.** With sd 17.15, a 3-point favourite
   covers barely more than half the time, and a 12-point favourite still loses outright
   roughly one game in four. Narrow sigmas manufacture fake edges.

## 4. The origination model

```
shrunk_net   = net_rating * G / (G + k)                  k = 11.0 (assumed)
pace         = (pace_home + pace_away) / 2
home_pts     = ORtg_home * (DRtg_away / 114.0) * (pace / 100)
away_pts     = ORtg_away * (DRtg_home / 114.0) * (pace / 100)
margin_home  = (home_pts - away_pts) + HCA               HCA = +1.51 (measured)
model_spread = -margin_home                              book convention
model_total  = home_pts + away_pts
```

**Why multiplicative, not additive.** A good offence meeting a weak defence should produce
more points than the same two ratings meeting in the other order. An additive
`net_home − net_away` model cannot express that. The multiplicative form is the standard
log5-style construction.

**Sign convention.** `model_spread_home` is the handicap on the *home* team, matching a book:
`ORL -9.5` means home is favoured by 9.5. Confusing the handicap with the margin was a real
bug in an earlier draft — it produced 49-point "edges". `validate_site.py` now asserts
`model_spread_home == -model_margin_home` on every row, so that bug cannot return silently.

**Shrinkage.** An 11-game sample is not a season. `k = 11` treats each team's observed net
rating as half signal, half league-average prior at that point in the season. `k` is
**assumed, not fitted**; larger `k` pulls every line toward the market.

## 5. Probabilities

Under a normal margin model:

```
P(home win)        = Phi( margin_home / sd_margin )
P(home covers h)   = Phi( (margin_home + h) / sd_margin )
P(over t)          = 1 - Phi( (t - model_total) / sd_total )
```

**Sanity check that caught a bug:** at a pick'em with `h = 0` and `margin_home = 0`, the
cover probability must be 0.50. Any implementation that fails this test is wrong, however
plausible its output looks. The earlier version used `-h` where `+h` belonged and produced
absurd cover probabilities while still "running cleanly".

## 6. De-vigging

A two-way price contains the book's margin. Comparing a model probability with a raw implied
probability counts that margin as edge.

```
dec_i  = american_to_decimal(price_i)
raw_i  = 1 / dec_i
fair_i = raw_i / (raw_a + raw_b)
```

Recomputed holds on the priced markets: 5.9% – 6.1%. Nine games of "edge" that ignore a
5% hold are almost entirely hold.

## 7. Correlations

Parlays assume independence. That assumption is checkable from game totals and is checked:

| Pair | n | r | 95% CI | Reading |
|---|---|---|---|---|
| Away total vs home total | 86 | +0.082 | −0.132 … +0.289 | weak, not established |
| Game margin vs game total | 86 | +0.005 | −0.207 … +0.217 | indistinguishable from zero |
| Own score vs opponent score (pooled within team) | 29 teams | +0.049 | — | mean of per-team r, no pooled CI |

The practical implication is useful and boring: spread and total legs in the same game can
be multiplied as approximately independent without much error, and a correlation claim
without an interval is not evidence.

**Not measured, and therefore blank:** points vs rebounds for a player, player vs teammate,
player over vs team total, minutes vs any prop. All four need per-player game logs.

## 8. Calibration and the luck adjustment

The win-probability model is scored with the Brier rule, the standard proper scoring rule:

```
Brier = mean( (p_i - y_i)^2 )
```

| Metric | Value |
|---|---|
| Brier | 0.1528 |
| Baseline (always predict the home win rate) | 0.2500 |
| Side accuracy | 84.9% (86 games) |
| Status | **in-sample, disclosed** |

The 0.2500 baseline is what a constant 0.5 forecast scores. Beating it means the model
carries information; it does **not** mean the model generalises, because these are the same
games used to fit nothing but were used to *choose* the formulation.

**Luck removal.** Observed wins 43 against 46.2 expected from the model's own probabilities,
z = −0.79, p = 0.4294. The gap is well inside chance. The leaderboard therefore scores skill
as:

```
luck_adjusted = (baseline_Brier - strategy_Brier) * (1 - p)
```

A strategy that looks excellent but is indistinguishable from luck scores near zero. That is
the intended behaviour.

**How much data would settle it.** Two-sided, 95% confidence, 80% power:

| True edge | Bets required |
|---|---|
| 5% | ≈ 778 |
| 3% | ≈ 2,159 |

A 23-game slate cannot demonstrate a 3% edge. Any short leaderboard is measuring variance.

## 9. Signal screening

All 20 modelled signals came out positive-EV against one book. That is a fingerprint of a
blind spot, not a discovery: the model ignores injuries and the market prices them, so the
model systematically disagrees where rosters are disrupted. Two screens are applied before a
signal is published as a candidate:

1. **Divergence cap** — reject if the modelled spread is more than 4 points from the listed
   spread (5 points for totals).
2. **Injury exposure cap** — reject if either side's availability is materially disrupted.

Result: 12 rejected for divergence, 7 for injury exposure, **1 survives**.

| Signal | EV/unit | Divergence | Injury risk | Verdict |
|---|---|---|---|---|
| OKC@LAC Under 222.5 | +0.051 | 2.6 | LOW (0 outs) | survived |
| GSW@SAS GSW ML | +1.266 | 7.5 | HIGH (7 outs) | rejected |
| GSW@SAS Over 217.5 | +0.395 | 12.0 | HIGH (7 outs) | rejected |
| ATL@CHI ATL −7.5 | +0.367 | 8.7 | HIGH (8 outs) | rejected |

Note that the surviving signal has the *smallest* expected value in the set. That is the
correct outcome: the largest "edges" are the least defensible ones.

## 10. Sensitivity

| Assumption | Used | Plausible range | Effect |
|---|---|---|---|
| Home-court edge | +1.51 | 0 … +3.0 | 1 pt on every model spread |
| Margin sd | 17.15 | 14.2 … 20.2 | changes every cover probability |
| Total sd | 18.62 | 16.6 … 20.6 | changes every over/under probability |
| Shrinkage k | 11.0 | 0 … 30 | pulls every line toward or away from the market |

The measured constants carry confidence intervals; the assumed ones carry this range. A point
estimate presented without either is what this build exists to avoid.

## 11. Known limitations

1. **No injury adjustment.** The single largest source of error. Ten games in the window had
   six or more players listed Out.
2. **Opponent-unadjusted ratings.** Ratings are season-long and do not account for strength
   of schedule within the sample.
3. **One book, one snapshot.** No market consensus, no line shopping.
4. **In-sample calibration.** No walk-forward holdout.
5. **No rest / travel / back-to-back term**, although the schedule needed to build one is
   already stored — this is the cheapest available improvement.
6. **Normal margin model.** Real margins are slightly heavier-tailed; probabilities in the
   extreme tails are correspondingly optimistic.
7. **Season is 11 games old** for most teams, so shrinkage dominates the rating.
