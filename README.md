# NBA3 / NBA Edge Lab

Research repository for NBA line origination, strategy evaluation, injuries, game flow, and decision
support. The repository contains **multiple independently built analysis/site workstreams**. They are
not a single reconciled model. This overview intentionally does not endorse any line, pick, market
edge, correlation, ROI, or leaderboard result.

## Final integration status (2026-11-14, session arena/3bf92fcc-nba3)

A cross-site **[consolidated executive summary](executive-summary.html)** is served at `/NBA3/executive-summary.html`
alongside the canonical dashboard below. It re-verified, line by line, on 2026-11-14:

- **Injury report**: 117/117 rows match the [official 11/13/26 5:00 PM ET PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf). The carried-forward "Miami CLE@MIA" irregularity is **resolved** — the PDF prints CLE@MIA in the Cleveland section; the Miami rows are correctly attributed "team printed, matchup paired via official schedule". The newer [7:30 PM ET report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf) (captured by session 2b9f1ae1) supersedes it for pick availability.
- **Injury refresh (session `bd90ce16`, this round)**: the canonical report is now the **newest official 11/14/26 04:45 AM ET** report — [PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_45AM.pdf) — 49 rows (26 player + 23 `NOT YET SUBMITTED`), read twice; the prior 04:15 AM report agrees on all 49/49 rows (0 differences). This supersedes the 11/13 07:45 PM snapshot for the live 11/14 window. The results log is refreshed to **183** finals (the nine 11/13 finals appended).
- **Slate**: 31/31 games (11/13–16) match the [live official schedule](https://www.nba.com/schedule) (dates, matchups, tip times; 0 mismatches across three independent captures).
- **Picks**: all 22 pick games for 11/14–16 are inside the verified slate, re-checked against the FX-corrected pick file (spread labels 22/22 correct after the fix).
- **All CI checks green**: unit tests (13 + 29 + 16 verify tests), every site builder, drift checks, and 553+ internal links.
- Model headline numbers re-computed from raw out-of-sample rows (origin margin RMSE 16.1786 vs 17.3003 baseline; totals 20.3459 vs 19.5605 — total model is worse than baseline and is reported as such). STRAT1/STRAT2 ROI carries the moneyline caveat added by the FX fixes (−110 is not obtainable on moneyline sides; treat ROI as an arithmetic artefact until a price feed exists).

## Canonical dashboard (session `arena/8d3d0271-nba3`, published 2026-11-14)

_This section supersedes the generic "Canonical dashboard (published 2026-11-14)" heading that sat here,
which did not say which session built the pages or from what. The current build is this session's._

`https://wingbangboozle1-lang.github.io/NBA3/` is **one dashboard with category sub-pages**, generated
from a single dataset (`data/app/canonical.json`). Every table row links to its source; anything that
could not be confirmed against an official source is left blank and listed on the **Flagged for
review** page.

**The headline result: zero strategies are funded, and nothing on the leaderboard beats the luck
threshold.** A board of 15 rules, simulated under the fair-line null 5,000 times, produces a
best-looking edge of **31.2 percentage points** 5% of the time; the largest edge any real rule posted
is **18.0 pp**. That is the honest state of the project, and it is the first thing the site tells you.

| Page | What it holds | Built from |
|---|---|---|
| `/` | Landing page: status cards, category navigation, highest-severity flags, archive links | `scripts/build_app.py` |
| `/app/summary.html` | Executive summary — what was verified, the headline result, what is missing and what it blocks | `data/app/canonical.json` |
| `/app/methodology.html` | The engine, shrinkage chosen from the past, the nine gates, how luck is removed, legal boundary | same |
| `/app/lines.html` | Originated spread + total for all **27** games of the **2026-11-14 → 2026-11-17** window, with out-of-sample accuracy | `data/app/lab.json` |
| `/app/picks.html` | Our own fair prices for every game in the window — **not bets**, see the caveat on the page | same |
| `/app/parlays.html` | Same-game and cross-game parlay cards, and the four prop combos that cannot be priced | same |
| `/app/props.html` | Player-prop projections, with the market line and probability **left blank** | same |
| `/app/leaderboard.html` | The strategy competition: 15 rules, nine gates, skill score, reward tiers, luck threshold, mirror pairs, null control | same |
| `/app/strategies.html` | The gate rule book and the per-rule gate grid | same |
| `/app/correlations.html` | 4 measured correlations with intervals, and 5 pairs left blank and why | same |
| `/app/injuries.html` | The official report row by row, plus the minutes and production each team's absences vacate | `data/app/official_injuries_2026-11-14_0445AM.json` |
| `/app/gameflow.html` | Rest, back-to-backs, pace, projected totals, overtime and blowout risk per game | `data/app/lab.json` |
| `/app/questions.html` | 40 open questions: known / missing / how to discover | merged from the earlier sessions |
| `/app/suggestions.html` | 38 site-improvement suggestions with options and a recommendation — **nothing implemented without a decision** | merged |
| `/app/verification.html` | Verification log | merged |
| `/app/sources.html` | Source register | merged |
| `/app/review.html` | Repository review, line by line (40 findings) | merged |
| `/app/flagged.html` | Flagged for review — 55 unverified values and irregularities, with source links | merged |
| `/review.html` | Cross-workstream audit (R-01 – R-13) | hand-maintained |
| `/hub/` | **Consolidated dashboard (session 99eabb04)**: 18 pages — landing, executive summary, slate, originated lines, picks, strategy leaderboard, correlations, injuries, game flow, player props, data and integrity, sources, repository review, questions, suggestions, flagged for review, verification log, methodology. One identifier namespace, one set of numbers, every published row linked to its source. | `data/hub/**` via `scripts/build_hub_data.py` + `scripts/build_hub.py` (generated; do not edit `hub/` by hand) |
| `/executive-summary.html` | **Cross-site consolidated executive summary** (arena/3bf92fcc-nba3): verified data foundation, model results, gates, measured correlations, picks window, compliance flags, owner decisions — every number linked to its source; reconciled with the FX corrections. | Hand-maintained; verification performed 2026-11-14 |
| `/site/` | **Edge Lab site** (arena/7c532e8c): landing page, executive summary, injuries, game-flow, 3-day slate, strategies, validation, questions, suggestions, sources, flagged items, repo review. Every table row links to an official source. | `data/*.json` via `scripts/build_site.py` (generated; do not edit `site/` by hand) |
| `/docs/` | Data site (arena/f879620b): injuries (11/11 report), slate, rules extracts, questions, gates, suggestions, flags. | `docs/data/data.json` (hand-maintained) |
| `/edge/` | **Edge Lab dashboard (arena-0a016df8)**: verified 174-game log, originated lines/spreads/totals/fair MLs, walk-forward-validated strategies with published gate results, 3-day picks with availability flags, official injury report tables, game-flow metrics, verification log. | `data/raw|model|processed|picks/**` via `pipeline/` (build_data → run_model → make_picks → make_props → build_site_data) |
| `/dashboard/` | **Verified build (session arena/925439ca-nba3)** — 17 self-contained pages: home, executive summary, methodology, originated lines, slate projections, strategy leaderboard, validation gates, correlations, injuries & rotation, game flow, data & team ratings, questions, suggestions, flagged for review, repo review, sources, archives. Every table row links to the official NBA page it came from, and every stored value is re-checked line by line against the official pages (1,305 checks, 0 mismatches). Independently built; it does not replace `/` + `/app/`, `/dash/`, `/hub/` or `/d01ae7e2/`. | `final/data/*` via `final/build_site.py` (generated; do not edit `dashboard/` by hand) |

### What this session verified, and against what

All official pages below were read on **2026-11-14 at 01:05 UTC** and compared programmatically with
the values earlier sessions had stored. `scripts/capture_official_2026_11_14b.py` prints every
disagreement.

| Check | Result | Source |
|---|---|---|
| Official schedule, 27 games of 2026-11-14 → 2026-11-17 | 22 of them also appear in the previous session's capture; **88/88** field comparisons agree, 0 differ | https://www.nba.com/schedule?date=2026-11-14 |
| Official team advanced statistics, 30 teams × 8 fields | **240/240** field comparisons agree | https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season |
| Official injury report 11/14/26 04:45 AM ET (newest listed) | 49 rows (26 player + 23 `NOT YET SUBMITTED`); 11/14 player rows re-compared 62/62 against the 11/13 07:45 PM snapshot; 5 of 10 11/14 teams had not filed, 18 11/15 placeholders | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_45AM.pdf |
| 183 official final scores | 366 team-games, **0 mismatch** against the official games-played column for all 30 teams | https://www.nba.com/games?date= |
| Every JSON file in the tree parses | 79 files, 0 failures | repository scan |
| Every table row on the canonical pages carries an `https` source link | **0** rows fail; the build exits non-zero otherwise | `scripts/build_app.py` |
| Determinism | `strategy_lab.py` is seeded; two consecutive runs produce byte-identical output, which is what makes the CI drift gate meaningful | `scripts/strategy_lab.py` |

### The engine

A **Massey least-squares margin model** (one rating per team plus a home-court term) and a **totals
model** regressed on the two teams' prior scoring environment. Both are shrunk — a ridge penalty and a
blend weight toward the league mean — and **both shrinkage parameters are chosen by validating on the
most recent 20% of past games only**, never on the games being forecast. Every date is priced with the
engine refitted on strictly earlier dates; games are batched by date so a game cannot see another game
tipped off the same night.

Out-of-sample results on 131 forecasts, scored against a constant baseline:

| Measure | Our model | Baseline | Verdict |
|---|---|---|---|
| Margin RMSE | 15.900 | 16.866 | ours is better |
| Total RMSE | 19.636 | 19.464 | **ours is worse** — published as such |
| Margin bias | +0.006 pts | 0 | unbiased |
| Total bias | −1.465 pts | 0 | our totals run 1.5 points high |
* **31/31** games of the window agree with the schedule snapshot captured on 2026-11-13
  (date, tip time, teams, NBA game id) — source: https://www.nba.com/schedule?date=2026-11-14
* **210/210** team-statistics field comparisons agree with the stored table
  (GP, W, L, OffRtg, DefRtg, NetRtg, PACE) — source:
  https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season
* Newest official injury report read and diffed against the stored earlier snapshot: **9 status changes**,
  Denver's report newly present, **5 teams still NOT YET SUBMITTED**, and **no official report yet for
  2026-11-15/16** — source:
  https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf
* Every table row on the canonical pages carries a direct `https` link to an official host; the build fails
  otherwise. `scripts/scan_table_sources.py` reproduces the repository-wide screen: 2,091 table-body rows in
  89 HTML files, 369 of them without a direct official-host link — 34 of those are the archived
  `research-dashboard.html`, the rest are in the earlier sub-sites (`lab/` 184, `origin/` 73, `site/` 29,
  `edge/` 10, `docs/` 5). The canonical pages contribute **0**.
* A third, independent verification round (session `99eabb04`, published at `/hub/`) re-read the official
  sources and transcribed the newest official injury report itself: **122 rows** (117 player rows across 21
  team-games + 5 `NOT YET SUBMITTED` team rows) from the 11/13/26 07:30 PM report. Cross-checked against the
  earlier session's independent transcription of the 05:15 PM report, **59 of 62 team-games agree exactly**; the
  three differences are all 11/14 games and are explained by the report version (Denver submitted between the
  two reports, Cleveland and Dallas changed submission state). Comparing the 05:00 PM and 07:30 PM official
  reports: 99 rows align, 12 statuses changed, 6 rows are new. One reason string lost at a PDF page break was
  reconstructed from the earlier official report and is flagged in the row itself (F-09, F-23).
* The official GP column of all 30 NBA teams sums to **348 team-games**, equal to the model's captured 348 with
  zero mismatch — the integrity claim was re-derived from the official table rather than trusted.
* The repository's two independent origination engines publish a spread field under almost the same name with
  **opposite sign conventions** — the origin engine stores a sportsbook-style line (negative = home favoured),
  the Edge Lab engine a projected home margin (positive = home favoured). Normalised to one scale they agree on
  the favourite in all **17** games they share, median spread gap 3.1 points. An earlier cut of this dashboard
  reported three favourite disagreements; that was the sign error, not a modelling difference. Published as
  flag **F-24**, verification record **V-21** and repository-review row **R-26**.

### Rebuild

```bash
python3 scripts/capture_official_2026_11_14b.py   # official capture + cross-check vs stored values
python3 scripts/strategy_lab.py                   # engine, gates, leaderboard, correlations -> data/app/lab.json
python3 scripts/assemble_canonical.py             # merge into data/app/canonical.json
python3 scripts/build_app.py                      # render app/ + index.html, check links and sources
```


- **Update (arena-0a016df8 round):** originated lines, win probabilities, correlation measurements and strategy gate results ARE now published on the `/edge/` dashboard — clearly labeled as model outputs, with STRAT3/STRAT4 marked **not eligible** (failed gates) and STRAT1/STRAT2 **provisional** (fail only the minimum-sample gate). ROI is measured against our own line at an assumed −110 because no licensed odds feed exists. Blocking items remain on the [Flagged for Review](site/flagged.html) page (site/) and [edge/flagged.html](edge/flagged.html) (edge/):
  - **7C-F-01**: NBA Terms §9 bars using NBA Statistics for gambling (source: https://www.nba.com/termsofuse).
  - **7C-F-02**: Dutch online sports-betting offers need a Koa licence under art. 31a of the Betting and Gaming Act (source: https://kansspelautoriteit.nl/online-kansspel-aanbieden).
  - **7C-F-03**: no licensed odds data is in the repository.
- The 3-day slate (11/13–11/16/2026) comes from the official schedule PDF, which is labelled "subject to change".
- Injury rows (site/) come from the official 11/13/26 5:00 PM report. The report has no minutes field, so no minutes effect is estimated. The docs/ site uses the earlier 11/11/26 7:00 PM report.

## Repository layout

| Path | Purpose |
|---|---|
| `data/*.json` | Editable content for `site/`: sources (S01–S11), schedule, injuries, flags (7C-F-…), questions, suggestions, strategies, gates, repo review. |
| `scripts/build_site.py` | Validates every row and renders `site/`. Fails on a missing official source, an unflagged blank, or a broken link. |
| `scripts/archive/` | One-shot generators used once to create `data/`. Do not re-run (they overwrite `data/`). |
| `site/` | Generated static site. Do not edit by hand. |
| `docs/`, `docs/data/data.json` | f879620b data site (unchanged by integration). |
| `edge/`, `data/raw|model|processed|picks|injuries`, `pipeline/{build_data,run_model,make_picks,make_props,build_site_data,check_site}.py`, `docs/{methodology,executive_summary,open_questions,suggestions,injuries_gameflow,verification_log}.md` | arena-0a016df8 Edge Lab round: verified data, origination engine, gated picks, dashboard. |
| `final/data/`, `final/verify.py`, `final/build_model.py`, `final/build_site.py`, `final/check_site.py`, `final/site_lib.py` | Consolidated round (arena/925439ca-nba3): verified datasets, 1,305-check verifier, line-origination model, dashboard generator, site checker. |
| `tools/validate_gates.py`, `tools/check_site.py` | Statistics module (Benjamini–Hochberg, Wilson interval, binomial test, etc.) and docs/ data/link checker (f879620b). |
| `tests/test_validate_gates.py` | Unit tests for the statistics module (f879620b). |
| `.github/workflows/pages.yml` | Runs unit tests, `tools/check_site.py`, root link check, `scripts/build_site.py` plus drift check, and deploys `/`, `/docs/`, `/site/` as one artifact. |
| `COORDINATION.md` | Shared task board, claims, verification logs, and PR/deploy status for all sessions. |

## Rebuild and check

```bash
python3 -m unittest tests/test_validate_gates.py   # statistics tests
python3 tools/check_site.py                         # docs/ data + link check
python3 scripts/build_site.py                       # validate data, render site/, check site links
python3 scripts/build_site.py --check               # validate and check links only (no files written)
python3 -m pipeline.run_model                        # arena-0a016df8: re-run origination + validation (data/ → data/model/)
python3 pipeline/build_site_data.py                  # arena-0a016df8: emit edge/data/*.json
python3 pipeline/check_site.py                       # arena-0a016df8: edge/ link & JSON check
python3 final/verify.py                              # consolidated: 1,305 checks vs official pages
python3 final/build_model.py                         # consolidated: walk-forward, gates, lines
python3 final/build_site.py                          # consolidated: render the 17 root pages
python3 final/check_site.py                          # consolidated: links + per-row source check```

`scripts/build_app.py` fails the build if a table row has no `https` source link, if a link is broken,
or if an in-page anchor does not resolve.

## Current status — read before using an output

- **No market price exists anywhere in this repository.** No licensed odds feed is connected. Every
  price shown is *our own fair price against our own originated line*, which makes its expected value
  zero by construction. Nothing here is a bet and no value is claimed.
- **Every ROI figure is measured against our own line at an assumed −110 price.** That is a property
  of our own numbers, not an economic result (flag NF-55).
- The leaderboard's **reward schedule is unapproved**. A "unit" currently means a paper unit, and the
  competition format (prize contest, pool, or internal scoring) is an open owner decision (CQ-36).
- **Zero strategies pass all nine gates**, and none beats the board's luck threshold. A bias found
  against our own line is published as a **model defect to repair**, not as an edge to bet
  (CQ-40, NF-50).
- Experimental line, pick, prop, correlation, backtest and injury artifacts also exist under `lab/`,
  `edge/`, `origin/`, `dash/`, `docs/`, `site/`, `research/` and `verify/`. Their snapshots, inputs,
  assumptions, samples and gate statuses differ and are **not reconciled**.
- Some artifacts identify Basketball-Reference and ESPN data among their inputs. The repository does
  not establish the necessary licence or rights for that use. NBA Terms of Use also restrict NBA
  Statistics. Obtain qualified legal advice and written permission before using or distributing these
  outputs.
- Some pages in the archived sub-sites contain betting prices and "positive EV" labels. Those are
  experimental derived outputs in the earlier snapshots, not official NBA facts, proven edges, or
  betting advice. **The canonical pages publish no market price and no EV label.**
- Dates and injury reports are static snapshots. The NBA describes its schedule as subject to change
  and its injury reports as continually updated. There is no verified always-current production feed
  in this static Pages site.
- Local tests and builds validate code, data shape, source-link presence and internal links. They do
  **not** prove that every historical row matches an official NBA primary record, that sources are
  licensed, or that a model predicts profitably. A repository-wide HTML scan
  (`scripts/scan_table_sources.py`) found rows without a direct official-host link in the earlier
  sub-sites; the canonical pages contribute **0**.
- The 2026–27 NBA Terms, use of NBA-derived statistics, distribution to others, and Dutch regulatory
  obligations remain review items. This repository is not legal advice.
- **Update (session `99eabb04` round):** a consolidated dashboard at `/hub/` publishes the whole project in one
  place with one identifier namespace: the 31-game slate re-verified against nba.com/schedule and the official
  schedule PDF, the official 30-team table, the newest official injury report (11/13 07:30 PM), the originated
  lines, the 8-strategy leaderboard against 7 gates, the measured correlations, game flow, player props, picks
  for the three-day window, and the review pages (repository review, questions, suggestions, flagged,
  verification). Still true: **no strategy passes every gate (0 of 8)** and **no licensed odds feed is connected**.
  The repository's two origination engines publish a spread field with opposite sign conventions, so any
  cross-engine number has to be normalised before it is read (`F-24`).

| Session | Flags | Suggestions | Questions | Sources |
|---|---|---|---|---|
| arena/7c532e8c (site/) | `7C-F-01…7C-F-17` | `SG-01…SG-11` | `Q-01…Q-14` | `S01…S11` |
| arena/f879620b (docs/) | `F-01…F-15` | `SG01…SG09` | `Q01…Q12` | `S1…S9` |
| arena/9ed6085f (research/) | `F01…F25` | `SG-01…SG-14` | `Q-…` | `S01…S19` |
| arena/925439ca (verified build, `/dashboard/`) | `F-01…F-18` | `SG-01…SG-14` | `Q-01…Q-15` | `S-01…S-13` |

Do not compare IDs across sites without this table. The `/dashboard/` build uses its own namespace
and supersedes nothing: it is an independently verified alternative to `/` + `/app/` and `/dash/`.

**Primary dashboard:** https://wingbangboozle1-lang.github.io/NBA3/ (root landing page) · **current numbers in one place:** https://wingbangboozle1-lang.github.io/NBA3/dash/<br>
**Published:** PR [#19](https://github.com/wingbangboozle1-lang/NBA3/pull/19) merged 2026-11-14 (merge commit `3367762`); Pages build `built` for that commit.
**Flagged for Review:** https://wingbangboozle1-lang.github.io/NBA3/app/flagged.html (this session's canonical register) · https://wingbangboozle1-lang.github.io/NBA3/review.html (cross-workstream audit)<br>
**Repository audit log:** [`COORDINATION.md`](COORDINATION.md)

## Pages and workstreams
| URL path | Contents | Caution |
|---|---|---|
| `/` | Canonical landing page: status cards, category navigation, highest-severity flags, archive links | Generated from `data/app/canonical.json` |
| `/app/*` | Canonical dataset pages: executive summary, method, originated lines, prices for the window, parlay and prop combos, player props, strategy leaderboard, validation gates, correlations, injuries and rotation, game flow, open questions, suggestions, verification log, source register, repository review, flagged for review | Derived values are labelled; official rows carry their source |
| `/review.html` | Source-linked inconsistencies, legal/data-rights questions, freshness and validation limits | Resolve before relying on outputs |
| `/site/` | Data dashboard, schedule/injury tables, sources and review material | Its files and ID namespace are distinct from the other dashboards |
| `/docs/` | Documentation tables, questions, validation framework and suggestions | Uses separate dated data snapshots |
| `/research/` | Research and requirements tables, source register, flags and questions | Build checks cover this site’s configured data and link rules, not the truth of every source value |
| `/lab/` | Experimental line origination, picks, player props and strategy tests | Not a vetted betting system; some outputs carry market/EV labels |
| `/edge/` | Independent line, pick, strategy, injury and game-flow dashboard | Separate pipeline and assumptions; not reconciled with `/lab/` or `/origin/` |
| `/dash/` | **Unified dashboard (integration round, session e40cd215)**: originated lines for the live 72-hour window, out-of-sample strategy leaderboard, 9 validation gates, measured correlations, injury/rotation register, game flow, cross-engine reconciliation, verification log, questions, suggestions and flagged items | Generated from `data/integration/model.json` by `integrate/engine.py` + `integrate/build_site.py`; byte-deterministic; `integrate/check.py` gates it |
| `/origin/` | Independent lines, correlation, props, injury analysis and walk-forward outputs | Separate dataset/model; not reconciled with `/edge/` |
| `/hub/` | **Consolidated dashboard (session 99eabb04)**: 18 pages over one identifier namespace — slate, originated lines, picks, 8-strategy leaderboard against 7 gates, correlations, injuries and minutes at risk, game flow, player props, data integrity, sources, repository review, questions, suggestions, flagged for review, verification log, methodology | Generated from `data/hub/dashboard.json` by `scripts/build_hub.py`; the build fails on an unsourced row, a non-https source or a broken link |

| `/dashboard/` | Independently verified build: 17 pages, every table row source-linked, every stored value re-checked against the official pages (1,305 checks, 0 mismatches) | Separate verification pass and dataset; not reconciled with `/`, `/dash/`, `/hub/` or `/edge/`. Five dashboard-family trees now coexist on this site; choosing one canonical is an open owner decision (SG-08 / CR-925439ca-E) |

Treat these as independent work products. Do not compare metrics across them without aligning source data, snapshots, dates, definitions, evaluation splits, odds, settlement, and statistical methods.

### Consolidated dashboard namespace (`/hub/`, session `99eabb04`)

One namespace, used by every page of `/hub/`: flags `F-01…F-24`, questions `Q-01…Q-16`, suggestions
`SG-01…SG-12`, repository review `R-01…R-25`, verification `V-01…V-20`, sources `S01…S20`.
These ids are different from every earlier namespace above and are not interchangeable with them.

## Decision-ready strategy framework

The desired system is feasible only after the dependencies below are resolved. The current repository can support methodology review and reproducibility checks; it cannot presently establish a unified, licensed, current pick feed or a skill-based winner.

1. **Data and rights first:** establish an authorized historical results/player/lineup source and, separately, timestamped licensed odds/prop prices and settlement rules. Store provenance, retrieval time (UTC), version/hash, corrections and missingness.
2. **One canonical source of truth:** select one dataset, one forecast timestamp policy, one model pipeline and one set of market definitions. Reproduce each artifact from a versioned release before merging results.
3. **Singles before combinations:** build calibrated distributions and probabilities for one market at a time. Use opponent/time-aware, leakage-resistant chronological validation and benchmark against simple baselines and an appropriate no-vig market reference where licensed.
4. **Correlation and combos:** calculate matched-sample dependence with uncertainty and conditional context. Evaluate the joint distribution and payout/settlement directly; never multiply marginal probabilities as if independent without testing.
5. **Injuries and game flow:** preserve each official report version; use authorized historical rotations, minutes and lineup outcomes to fit conditional ranges. An injury status alone does not quantify a minutes or production change.
6. **Separate skill from variance:** pre-register metrics, sample floors and gates; report proper scoring/calibration, confidence intervals, multiple-testing control, drawdown and net economics. Freeze model versions and conduct a prospective shadow/paper trial. Luck cannot be removed from individual outcomes.
7. **3-day slate:** refresh the official schedule and latest injury information at request time; emit forecasts only for confirmed games within 72 hours and suppress output on stale/missing data. A static file does not satisfy this operational requirement.
8. **Leaderboard only after gates:** publish strategy ranking only when all candidates share inputs, timestamp cutoffs, settlement rules, costs and validation. Display sample size and uncertainty; do not rank by raw win count.

## Open questions and suggested order

The dashboard links the detailed question and suggestions pages. The blocking unknowns include:

- Does the project have written NBA-statistics permission or a suitable licensed provider agreement? What use, derived output and distribution are covered?
- Which authorized provider supplies historical game/player/rotation outcomes, odds, prop markets, line movement and settlements? What timestamps, history and terms apply?
- Is the product for private research, or will lines/picks be offered to others? What jurisdictions and compliance rules apply? Obtain qualified Dutch counsel’s assessment.
- What is the pre-registered leaderboard objective, baseline, minimum sample, uncertainty threshold, cost model and retirement rule?
- What data can support injury-to-minutes and game-flow scenarios, and how will those ranges be validated?
- What exact schedule/injury freshness SLA and fail-closed behavior support a maximum 72-hour forecast horizon?
- What risk limits, user protections and responsible-gambling policy are appropriate before any product use?

**Suggested sequence (awaiting decision):** (1) legal/data-rights review; (2) choose one canonical authorized source/pipeline; (3) establish immutable timestamped snapshots; (4) independently reconcile the data and existing outputs; (5) pre-register shared gates and conduct prospective paper validation; (6) consider props/parlays only after player opportunity and joint-probability evidence passes. See [Suggestions](docs/suggestions.html) and [Flagged for Review](review.html). These are proposals; no additional product behavior has been approved by this audit.

## Official references reviewed

- [NBA.com Terms of Use](https://www.nba.com/termsofuse) — includes the NBA Statistics section; not a legal determination about this project.
- [NBA Official 2026–27 injury-report index](https://official.nba.com/nba-injury-report-2026-27-season/) — reporting process and dated reports; updates continually, not a minutes forecast.
- [NBA official 2026–27 schedule by date (PDF)](https://cdn.nba.com/manage/2026/08/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf) — marked “subject to change.”
- [NBA 2026–27 schedule release](https://www.nba.com/news/2026-27-nba-regular-season-schedule) — official release and schedule links.
- [NBA Stats glossary](https://www.nba.com/stats/help/glossary) — definitions, not validation or data rights.
- [Kansspelautoriteit: online gambling offerings](https://kansspelautoriteit.nl/online-kansspel-aanbieden) — official Dutch regulator guidance; does not decide this project’s legal classification.

Sources fetched for the 14 November 2026 audit. Check current terms/reports at implementation time; old copies are not live evidence.

## Rebuild and verification commands (unified dashboard)

```bash
python3 -m integrate.engine        # rebuild data/integration/model.json (deterministic)
python3 -m integrate.build_site    # render dash/ (15 pages)
python3 -m integrate.check         # row-source, link, number-consistency and scope gate
```

```bash
python3 scripts/build_hub_data.py   # session 99eabb04: merge verified sources -> data/hub/dashboard.json
python3 scripts/build_hub.py        # session 99eabb04: render hub/ (18 pages)
python3 scripts/build_hub.py --check # session 99eabb04: validate sources + links, write nothing
```

Standard library only. `integrate/engine.py` imports `model/nbastats.py` (session e22a2831) without modifying it.


These commands are for repository/code consistency. Passing them does not verify statistical truth, data licensing, or profitability.

```bash
python3 -m unittest tests/test_validate_gates.py
python3 -m unittest discover -s pipeline/tests
python3 tools/check_site.py
python3 scripts/build_site.py --check
python3 pipeline/verify.py
python3 pipeline/check_site.py
python3 scripts/model.py
python3 scripts/build_lab.py
python3 scripts/validate_site.py
python3 pipeline/build_site.py
python3 pipeline/verify.py
python3 scripts/capture_official_2026_11_14.py
python3 scripts/assemble_canonical.py
python3 scripts/build_app.py
python3 scripts/scan_table_sources.py
python3 scripts/build_hub_data.py
python3 scripts/build_hub.py
python3 scripts/build_hub.py --check
```

GitHub Pages combines static site folders in `.github/workflows/pages.yml`. Static publication is not a live feed or automated daily data refresh.

---

## Session `3655c68d` — verification & decision layer (`/verify/pages/`)

Adds **no new model**. It measures whether the six models already in this repository can be trusted,
and resolves the places where they contradict each other. Published at
[`/verify/pages/`](verify/pages/index.html).

| Path | What it is |
|---|---|
| [`verify/pages/`](verify/pages/index.html) | 13 pages: verification hub, executive summary, contradictions, claim ledger, injury verification, game-log verification, corrections, decisions, questions, suggestions, settlement ledger, sources, flagged for review |
| `verify/data/` | Editable content, plus the verbatim official injury-report transcript used for the line-by-line check |
| `verify/build.py` | Validates every row, runs the numerical self-tests, renders the site, checks links, fails on a missing source |
| `verify/tests/test_verification.py` | 16 regression tests pinning the defects found this session |

### Results

| | |
|---|---|
| 174-game log, two independent captures | **174 / 174 agree** on date, teams, exact score and overtime |
| Injury table vs official NBA PDF | **110 / 110 named players** match, 0 status mismatches |
| Published strategy records re-audited from their own bet logs | **4 / 4 reproduce exactly** |
| Strategies passing every validation gate | **0 of 8** |
| Contradictions found between dashboards | **9** (3 blocking) |
| Claims rechecked | **27** — 20 verified, 4 discrepancies, 3 unverifiable |

### Defects found and fixed

1. **FX-01 — parlay copula returned the marginal.** `parlay_joint()` integrated over the whole real
   line and never applied the first-leg threshold, so it returned the second leg's probability for
   every input. The published "joint win probability" of 0.58 for two 0.58 legs at ρ=+0.3 is the
   Fréchet upper bound and only reachable at ρ=1. Corrected value **0.3832** (fair odds 2.61),
   confirmed against a 200,000-draw Monte Carlo.
2. **FX-02 — every pick card named the wrong side.** Labels were built from `away + '+' + (-home_margin)`,
   which printed the away team as the underdog on all 22 cards, including the 10 where it was the
   favourite. **0 of 22 were correct; now 22 of 22.**
3. **FX-03 — moneyline strategies labelled as spread bets.** STRAT1/STRAT2 settle on the game winner,
   so pricing them at −110 produced an unearnable "+48.24% ROI". Relabelled, with the −110 figure kept
   only as a marked arithmetic artefact.
4. **FX-04/FX-05 —** the correction propagated into `data/model/correlation_report.json` and the picks.
5. **V-F-02 — `pipeline/build_site_data.py` overwrote `site/data/`.** The edge pipeline wrote into
   session 7c532e8c's generated tree. Output moved to `edge/data/`; the affected files were restored.

### Reproduce

```bash
python3 -m unittest verify.tests.test_verification   # 16 tests
python3 verify/build.py                              # validate + render + link check
python3 verify/build.py --check                      # validate only
```

Standard library only. `verify/build.py` refuses to write the site if any self-test fails, any
VERIFIED claim lacks an https source, or a settled ledger row lacks an official settlement source.

---

## Workstream: `d01ae7e2/` — official-slate line origination & gated picks pipeline

Session `d01ae7e2` (branch `arena/d01ae7e2-nba3`) — built entirely on **NBA-official sources only** (`nba.com`, `cdn.nba.com`, `ak-static.cms.nba.com`, `official.nba.com`, `pr.nba.com`, `statsdmz.nba.com`), with a machine-enforced allowlist. Self-contained namespace (coexists with every other workstream):

| Path | Contents |
|---|---|
| `d01ae7e2/data/` | 31-game slate (Nov 13–16 = today + 3-day max window), full official 05:00 PM injury-report transcription, all 30 teams' official stats, player baselines, generated picks + correlations, 17 flagged items, 12-question register, source registry |
| `d01ae7e2/docs/` | 12-page dashboard (landing, slate & picks, strategies & gates, leaderboard, injury impact, game flow, analysis, repo review, flagged, questions, suggestions, sources) + 9 long-form write-ups |
| `d01ae7e2/scripts/` | `generate_picks.py` (deterministic pick generation, no manual input), `build_site.py` (JSON → HTML), `verify.py` (official-domain allowlist, blank+flag policy, per-row source links, pick coverage) |

```bash
python3 d01ae7e2/scripts/generate_picks.py && python3 d01ae7e2/scripts/build_site.py && python3 d01ae7e2/scripts/verify.py
# expected: All verification checks passed.  (scope: this workstream only)
```

Dashboard (after Pages deploy): `https://wingbangboozle1-lang.github.io/NBA3/d01ae7e2/docs/index.html`

Rules enforced in this namespace: every table row links its official NBA source; unconfirmable values are **blank + flagged, never inferred**; model parameters (HCA, rest/injury weights) are declared assumptions with pre-settlement revision logs; provisional picks (injury report not yet published) are never scored. The other workstreams' cautions above apply to them, not to this namespace — and this namespace makes no claim about theirs.

Reviewers: decisions this workstream is waiting on (license, CI, odds source, HCA calibration…) are listed in `d01ae7e2/docs/QUESTIONS.md`; improvement suggestions await path selection in `d01ae7e2/docs/SUGGESTIONS.md` — none have been implemented.
