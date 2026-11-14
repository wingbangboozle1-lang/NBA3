# Questions, Information & Answers Needed Before Decisions (T09)

**Rule:** a decision gated by an UNANSWERED question does not happen. Machine-readable: `data/questions.json` · Site: [questions.html](questions.html), [suggestions.html](suggestions.html)

## What we HAVE vs what we do NOT have

| Area | We have (verified, official) | We do not have |
|---|---|---|
| Slate | All 31 games Nov 13–16: times, venues, TV, IDs, rest days — dual-source (PDF + live page) | Nothing missing |
| Records/teams | All 30 teams' GP/W-L/PTS/margin from league table; records cross-checked on game pages | Location splits for 25/30 teams; league HCA |
| Injuries | Full 11/13 report (05:00 PM); partial 11/14; supersession history | Reports for 11/14 stragglers, 11/15, 11/16 |
| Players | PPG + Last-5 logs for 8 key players; roster PPGs for 13 teams | 13 OUT-player PPGs (fl-13); full-season logs (endpoint dead) |
| Market | Nothing | **Any odds/CLV data** (Q-04) |
| Results | Completed-game format verified (CLE 115–107 NYK) | Automated grading (Q-11) |
| Repo | Full history reviewed | LICENSE, CI decisions (Q-07/Q-08) |

## Questions register (summary — full table on the site)

| ID | Question | Blocks | Status |
|---|---|---|---|
| **Q-01** | When does the report covering 11/14's NOT YET SUBMITTED teams post, and what's the re-run trigger? | Scoring 11/14 injury-adjusted picks | UNANSWERED (owner: pipeline/SG-04) |
| **Q-02** | Fetch remaining rosters to complete 13 OUT-player PPGs? | Completeness claim on injury analysis | UNANSWERED (owner: reviewer → SG-02) |
| **Q-03** | What HCA constant? Derive from 30 official location splits or accept 2.5-pt assumption? | Calibration of **every** originated line (`hca-01`) | UNANSWERED (owner: reviewer → SG-03) |
| **Q-04** | Authorized market-odds source for CLV? | CLV gate (strongest luck-removal tool) | UNANSWERED (owner: reviewer) |
| **Q-05** | Meaning of schedule PDF `R` flag? | None currently — model ignores it | UNANSWERED (owner: reviewer) |
| **Q-06** | Stay on PPG prop baselines or authorize game-log collection? | S3 prop sharpness | UNANSWERED (owner: reviewer) |
| **Q-07** | Which LICENSE? | Legal clarity | UNANSWERED — deliberately not added |
| **Q-08** | Add CI workflow running verify.py? | Automated row-link enforcement | UNANSWERED → SG-01 |
| **Q-09** | Leaderboard: points-only or unit-scaling paper book? | Reward rule finalization | UNANSWERED (default: unit-scaling, paper) |
| **Q-10** | Publish provisional lines before reports exist? | 3-day auto-generation vs freshness gate | **ANSWERED** — publish labelled provisional, never score until G4 passes (PICKS_PIPELINE.md) |
| **Q-11** | Daily result-grading ingest? | Leaderboard/CI gates need settled results | **ANSWERED (design)** — `grade_picks.py` design recorded; implementation future work |
| **Q-12** | Is n=5 correlation acceptable for v1 gates? | S2/S3 release thresholds | UNANSWERED (default: allowed with noisy badge) |

## Suggestions queue (T10) — reviewer chooses a path BEFORE implementation

**Nothing below has been implemented.** Each needs a `decision` recorded in `data/questions.json`.

| ID | Suggestion | Recommended path | Decision |
|---|---|---|---|
| SG-01 | CI workflow running `verify.py` on push/PR | **A**: add `.github/workflows/verify.yml` | ⏳ awaiting review |
| SG-02 | Complete remaining OUT-player PPGs (8 roster fetches) | **A**: fetch and fill nulls | ⏳ awaiting review |
| SG-03 | League HCA from all 30 official location splits | **A**: fetch 30 team pages, compute | ⏳ awaiting review |
| SG-04 | Auto-refresh picks on injury-report publication | **A**: polite 30-min poll of the filename pattern | ⏳ awaiting review |
| SG-05 | Interactive slate filter (date/TV/Cup/rest) | **A**: client-side JS filter | ⏳ awaiting review |
| SG-06 | "How to verify any row" walkthrough page | **A**: docs + site page, 3 worked examples | ⏳ awaiting review |
| SG-07 | Automated settled-results grading | **A**: `grade_picks.py` from official linescores | ⏳ awaiting review |
| SG-08 | Visual delta (our line vs baseline) in slate table | **B then A**: numeric first | ⏳ awaiting review |

**Process for reviewers:** pick a path → record it in `data/questions.json → suggestions[].decision` (or in the PR) → that authorizes implementation in a follow-up referencing the suggestion ID.
