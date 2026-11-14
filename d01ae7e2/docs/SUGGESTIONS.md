# Suggestions for Improvement — Review Queue (T10)

**Rule from the brief:** *"Make suggestions on how to improve the site... create a section dedicated for suggestions so someone can review suggestions and choose the best path before implementing any changes."*

**Status of every item below: NOT IMPLEMENTED — awaiting reviewer decision.** Machine-readable queue with Path A / Path B / pros / cons / recommendation: `d01ae7e2/data/questions.json → suggestions`. Site page: [suggestions.html](suggestions.html).

## How to use this queue

1. Reviewer reads both paths + the pre-recorded recommendation.
2. Records the choice as `decision: "A"` or `"B"` (or `"defer"`) in `d01ae7e2/data/questions.json`, or states it in the PR conversation.
3. Only then does an implementer act, referencing the SG ID in the commit.
4. Items never silently land — this is what keeps "choose the best path before implementing" enforceable.

## Queue

| ID | Suggestion | Recommendation | Blocked-by | Decision |
|---|---|---|---|---|
| SG-01 | CI workflow running `d01ae7e2/scripts/verify.py` on push/PR | Path A (add workflow) | Q-08 | ⏳ awaiting review |
| SG-02 | Fetch remaining rosters → fill 13 null OUT-player PPGs | Path A (fetch ~8 rosters) | Q-02 | ⏳ awaiting review |
| SG-03 | Derive league HCA from all 30 official location-split pages (replaces the 2.5-pt assumption on every line) | Path A (30 fetches) | Q-03 | ⏳ awaiting review |
| SG-04 | Auto-refresh pipeline on injury-report publication (filename-pattern poll → regenerate picks) | Path A (cron/Action, polite interval) | Q-01 | ⏳ awaiting review |
| SG-05 | Interactive slate filter (date / TV / Cup / rest) on the dashboard | Path A (client-side JS) | — | ⏳ awaiting review |
| SG-06 | "How to verify any row" walkthrough (3 worked examples: slate row, injury row, pick row) | Path A (docs + site page) | — | ⏳ awaiting review |
| SG-07 | `d01ae7e2/scripts/grade_picks.py` — ingest official linescores into `results.json`, settle picks, update leaderboard | Path A (scripted grading) | Q-11 | ⏳ awaiting review |
| SG-08 | Visual delta indicator (our line − baseline) in slate table | Path B then A (numeric first) | — | ⏳ awaiting review |

## Candidates explicitly rejected from this queue (documented, not silently dropped)

- *Adding a LICENSE file* → not a suggestion but a **legal decision**: kept as Q-07 only.
- *Market-odds scraping* → not suggested at all: no authorized source exists (Q-04); scraping third-party books would violate the "official sources only" constraint.
- *Inventing injury minutes projections* → rejected against the brief's never-infer rule; see [FLAGGED.md](FLAGGED.md) methodology section.
