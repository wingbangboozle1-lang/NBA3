# Executive summary — NBA Edge Lab

**As of:** 2026-11-15 11:40 UTC (06:40 AM ET) · **Session:** `arena/bb0c83a4-nba3`
**Live site:** https://wingbangboozle1-lang.github.io/NBA3/
**Full dashboard:** `/app/` · **Flags:** `/app/flagged.html` · **Questions:** `/app/questions.html` · **Suggestions:** `/app/suggestions.html`

---

## The one-paragraph version

The system now originates its own spread and total for every game in a rolling
four-day window, prices picks into those lines, ranks 15 strategy candidates on a
validated leaderboard, and publishes measured correlations. **Zero of the 15
strategies pass the validation gates**, and that is the correct, honest result —
the best-looking rule posts an 11.3-point edge when the fair-line null routinely
produces a 28.3-point edge on a board this size. What the system has actually
achieved is something more valuable than a winning record: it can now be trusted
to tell you when it has *not* found an edge, and it publishes the reason. The
binding constraint is no longer the model. It is that **there is no licensed
market line anywhere in the chain**, so nothing here has yet been compared to a
price a human could actually bet.

---

## 1. What was verified this round, from official sources only

Every number below was read off an `nba.com`, `cdn.nba.com`, `ak-static.cms.nba.com`
or `official.nba.com` page and is stored in the repository so it can be re-checked
without the network.

| What | Value | Cross-check that also passed | Source |
|---|---|---|---|
| Completed games in the results log | **188** through 2026-11-14 | 30 teams' official GP sum to 376 = 2 × 188, from a *different* page | [stats/teams/advanced](https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season) |
| Team records reconcile | **30 of 30**, 90 comparisons, 0 mismatches | — | [same page](https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season) |
| 11/14 finals added | **5 of 5**, scores and game ids | each read off its own "Final" card | [schedule](https://www.nba.com/schedule?date=2026-11-15) |
| Upcoming window | **34 games**, 11/15–11/18 (9 / 8 / 5 / 12) | two different date URLs render the same week block | [schedule](https://www.nba.com/schedule?date=2026-11-15) |
| Injury report | **101 rows** (84 player + 17 NOT YET SUBMITTED) | 06:00 AM and 06:15 AM reads of the same document agree row for row | [06:15 AM PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf) |
| Injury filing rule | quoted verbatim | publisher's own page text | [report index](https://official.nba.com/nba-injury-report-2026-27-season/) |

51 unit tests pass, plus every suite the repository already had. The build
refuses to publish a table row without an official source link.

## 2. What the model actually does — and how well

The engine is a walk-forward **Massey margin model** with a shrunk scoring model
for totals. Every feature used to price a game comes from games with a strictly
earlier date, re-derived per date from scratch, and `assert_no_lookahead` proves
it on every build.

| Metric | Model | Naive baseline | Verdict |
|---|---|---|---|
| Margin RMSE (145 out-of-sample games) | **15.98** | 16.82 | **beats** the baseline |
| Margin bias | +0.88 pts | — | small, home-side |
| Total RMSE | 19.31 | 19.26 | **does NOT beat** a constant |
| Home-win Brier | **0.2193** | 0.25 | better than a coin |

**Read that second row carefully.** The originated *total* is worse than simply
predicting the league average every night. Any strategy that leans on the totals
model is leaning on nothing. The margin model is real but weak; the totals model
should be treated as a placeholder until it is fixed.

## 3. The leaderboard, and why nothing clears it

Fifteen candidates across singles, same-game parlays, cross-game parlays and
player-prop combos are scored against eight gates. The result:

- **0 of 15** pass every gate.
- The largest edge on the board is **+11.3 points** (ST-05, unders in the
  highest-projected totals, n=31, p=0.28).
- Under the fair-line null, a board this size throws up an edge of **28.3 points**
  or more 5% of the time. Nothing on the board is close.
- Every q-value is 1.00. Nothing survives multiple-testing correction.
- Three pairs of strategies are exact mirror images of each other (ST-01/ST-02,
  ST-03/ST-04, ST-09/ST-10). If one were real, its mirror would be too — and both
  cannot be. They are annotated, not counted twice.

The **luck test** is the mechanism that removes luck from the equation: it asks
what the *best* edge on the board would look like if every line were fair, and
requires the winner to beat that. This is why a 59.4% win rate over 32 bets
correctly ranks as noise rather than skill.

## 4. Correlations — measured, not assumed

| Pair | r | 95% CI | n | Status |
|---|---|---|---|---|
| Home points vs away points (same game) | **0.123** | −0.021 to +0.261 | 188 | verified |
| Originated spread residual vs total residual | 0.033 | −0.131 to +0.195 | 145 | verified |
| Player prop combinations | — | — | — | **BLANK — no licensed player-prop history exists** |

The first row is the number that decides whether a same-game side+total parlay is
fairly priced as independent, and at r≈0.12 with a CI spanning zero it is close
enough that the parlay pages publish both the independent and the measured joint
price. Player-prop correlation **cannot be measured from this repository** and is
left blank rather than estimated — that is the single biggest hole in the
prop-combo strategy family.

## 5. Injuries → rotation → production

The link from an official designation to a number of minutes removed is now
working. It was not before this round: the injury PDF prints `Edwards, Anthony`
and the statistics table prints `Anthony Edwards`, the name join never matched,
and **every published "minutes vacated" figure was a structurally-zero floor no
matter who was out**. That defect (NF-90) is repaired and pinned by tests.

Two 11/15 team-games now publish a real figure:

| Game | Team | Out | Minutes vacated (floor) | Points vacated |
|---|---|---|---|---|
| IND@PHI | IND | 3 | 33.0 | 21.8 |
| LAL@PHX | LAL | 2 | 35.3 | 24.7 |

**Two limits you must hold onto.** First, only the top 31 players by minutes have
a captured per-game line, so any absence outside that set is counted as an
*unknown*, never added to the total — every figure is a floor. Second, **who
absorbs those minutes is not modelled at all**, and publishing a replacement rate
would be a guess. Doing it properly needs per-player game logs and on/off splits,
which the repository does not have.

**Game flow** adds rest differential and projected pace. On 11/15 the spread of
projected pace is narrow and rest differentials are 0–1 days, so neither factor
separates these games — reported as a null result rather than dressed up.

## 6. The binding constraint: no market line

This is the most important sentence in the document. **No licensed odds feed is
connected to this repository.** Therefore:

- There is no market price to compare an originated line against.
- Every "pick" is a selection against *our own* line, and because that line is
  originated to be fair, its expected value is zero **by construction**.
- Every ROI figure is labelled as measured against our own line at an assumed
  −110, which is an arithmetic property of our own numbers, not an economic result.

The backtest can therefore answer one question honestly: *is our own line biased
in a way a simple rule can exploit?* So far the answer is no, which is exactly
what a fair line should produce. Profitability cannot be assessed until a real
price exists to bet into.

## 7. Decisions needed before anything further is built

These block real money and real picks, and none of them is a technical question:

1. **Do you have written permission or a licensed agreement for NBA statistics?**
   [NBA.com Terms of Use](https://www.nba.com/termsofuse) has an NBA Statistics
   section; whether this project's derived output is covered is a legal question
   this repository cannot answer.
2. **Will this be private research or offered to others?** If offered, which
   jurisdictions, and what compliance applies? This determines whether the
   product exists at all.
3. **Which authorized odds source will supply prices, with what timestamps and
   history?** This is the gate on every profitability claim.
4. **What is the pre-registered minimum sample, uncertainty threshold and
   retirement rule** for the leaderboard? Until fixed in advance, any winner is
   selected after the fact.

Forty-seven further questions with their evidence links are on the
[Questions page](https://wingbangboozle1-lang.github.io/NBA3/app/questions.html),
and 46 decision-ready proposals are on the
[Suggestions page](https://wingbangboozle1-lang.github.io/NBA3/app/suggestions.html).
Nothing on the suggestions page has been implemented — each awaits your choice of
path, as you asked.

## 8. Irregularities found this round

Nine, published with sources on the
[Flagged page](https://wingbangboozle1-lang.github.io/NBA3/app/flagged.html). The
three that matter most:

- **F-BB-01** — the site was advertising an already-played slate as "upcoming".
  Fixed by rotating the window; the missing gate that would have caught it is not.
- **F-BB-07** — a stale pull request was silently *deleting* 21,860 lines of
  merged work while GitHub reported it as mergeable. Closed unmerged.
- **F-BB-08** — six historical audit trees were quietly re-auditing a snapshot
  they were not written against, and failing. Fixed by freezing the snapshot they
  audited.

## 9. What would make this genuinely useful

The shortest honest path, in order:

1. **Get a licensed odds source.** Everything about profitability is blocked on it.
2. **Fix the totals model** so it beats a constant, or stop publishing totals.
3. **Acquire per-player game logs** so the rotation model can estimate
   replacement minutes instead of only the vacuum.
4. **Pre-register the leaderboard** — sample size, threshold, retirement rule — and
   then run it prospectively on paper for a full season before risking a dollar.
5. **Add a build gate that fails when the priced window contains a finished game,**
   so last round's staleness cannot recur.

None of steps 1–4 is a coding problem. They are decisions and licences, which is
why they are on the Questions page rather than in a ticket.

---

*Nothing in this document is a prediction of profit. Where a value could not be
confirmed from an official source it is left blank and flagged rather than
estimated, filled in, or inferred.*
