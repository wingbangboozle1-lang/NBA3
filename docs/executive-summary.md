# Executive summary

**Snapshot:** 2026-11-13T22:30Z · **Season:** 2026-27 · **Live site:** https://wingbangboozle1-lang.github.io/NBA3/

---

## One paragraph

This build originates its own NBA lines from published team efficiency ratings, prices them
against a live market snapshot, measures the correlations a parlay would depend on, screens
its own signals for the two failure modes that matter most, and ranks six strategies on a
luck-adjusted score rather than on how good they look. **The headline finding is a negative
one, and it is the most useful thing here:** every one of the 20 modelled signals came out
positive-EV against the book, which is not evidence of 20 good bets but of a model that
cannot see injuries while the market can. After screening for that blindness, exactly one
signal survives — and it has the smallest expected value in the set.

## What exists

| Deliverable | Where | State |
|---|---|---|
| 23-game slate with originated spread, total, win probability | `lines.html` | complete; 9 games have a captured market price |
| Signal funnel: 20 raw → 1 screened candidate | `picks.html` | complete, including every rejection and its reason |
| Prop pricing (5 rows) and measured correlation (3 pairs) | `props.html` | **partial** — no prop model, 4 correlations unmeasured |
| 6 strategies × 7 validation gates, luck-adjusted leaderboard | `strategies.html` | complete; **no strategy passes all seven** |
| Official availability, exposure scoring, market movement | `injuries.html` | complete for statuses; no minutes model |
| Method, constants with CIs, sensitivity table, gates | `methodology.html` | complete |
| 10 decision questions (known / missing / how to find out) | `questions.html` | complete |
| 10 suggestions with a review-and-choose queue | `suggestions.html` | complete, nothing auto-applied |
| 15 flagged irregularities with source links | `review.html` | complete |
| Reproducible build + validation gate | `scripts/`, CI | **passes**; CI blocks any unsourced row or broken link |

## The five numbers that matter

| Number | Value | Why it matters |
|---|---|---|
| Measured home-court edge | **+1.51 pts** (CI −2.17 … +5.19) | The interval spans zero. Home court is *not* established by this sample, and the UI says so. |
| Margin sd | **17.15** | The original assumption of 12.4 was 40% too small, which manufactures overconfidence. Now measured. |
| Brier score | **0.1528** vs 0.25 baseline | The model carries real information — but **in-sample**, and the brief's own gate 4 forbids calling that validated. |
| Luck test | **p = 0.4294** | 43 observed wins vs 46.2 expected. Indistinguishable from chance, so the leaderboard discounts skill accordingly. |
| Signals surviving screening | **1 of 20** | The funnel is the product. Nineteen were thrown away, with reasons. |

## What this build refuses to do

These are deliberate omissions, not gaps found late:

- **No profit claim, anywhere.** No historical closing prices were retrieved, so no ROI,
  no "units won", no backtested return appears on any page. Five of six strategies carry no
  score for exactly this reason.
- **No player-prop probabilities.** A prop number needs a minutes distribution; none was
  retrieved. Props are quoted and de-vigged, and the model column reads "no model".
- **No inferred values.** Where a source could not confirm something, the cell is blank with
  a chip and the item is on the review page. Nothing was filled in from a plausible default.
- **No staking advice.** Legal status, jurisdiction and bankroll are all unknown.
- **No causal claim about line movement.** Movement is shown beside official availability
  counts; the causal column stays unverified.

## What to do next

In order, and each one is gated on a decision the build cannot make for itself:

1. **Acquire a closing-line archive** (S-01, blocks Q3/Q5/Q10). This is the only thing that
   converts the site from "model output" into "measured skill". Nothing else is close in
   impact.
2. **Acquire a minutes source** (S-02, Q9). Reopens props — the largest market by volume —
   and the same-game correlations that make combo pricing possible.
3. **Settle the legal and licensing question** (Q1, Q2, IR-15). Determines whether the site
   may present anything as actionable.
4. **Add rest and travel to the rating** (S-03). Cheapest genuine model improvement, because
   the schedule needed is already stored.
5. **Move from one book to a market consensus** (S-04). Until then, "edge" means edge against
   this provider at this minute.

## Honest read on maturity

The data layer is solid: 30 teams' ratings reconcile arithmetically, 86 game results
reconcile with season records, 9 market snapshots agree with the provider's own detail
strings, and 75 injury statuses come from the league's own dated report. The modelling layer
is honest about its limits and is measurable. The **strategies layer is pre-validation and
should be read as a scoring framework with nothing passing through it yet.** Anyone
presenting this as a working betting system would be misrepresenting it.

The one thing to trust most is the part that says no. A build that produced 20 confident
picks from this data would be lying about what it knows; this one produces one and explains
why the other nineteen were discarded.
