# NBA3 / NBA Edge Lab

Research repository for NBA line origination, strategy evaluation, injuries, game flow, and decision support. The repository contains **multiple independently built analysis/site workstreams**. They are not a single reconciled model. This overview intentionally does not endorse any line, pick, market edge, correlation, ROI, or leaderboard result.

## Final integration status (2026-11-14, session arena/3bf92fcc-nba3)

A cross-site **[consolidated executive summary](executive-summary.html)** is served at `/NBA3/executive-summary.html`
alongside the canonical dashboard below. It re-verified, line by line, on 2026-11-14:

- **Injury report**: 117/117 rows match the [official 11/13/26 5:00 PM ET PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf). The carried-forward "Miami CLE@MIA" irregularity is **resolved** — the PDF prints CLE@MIA in the Cleveland section; the Miami rows are correctly attributed "team printed, matchup paired via official schedule". The newer [7:30 PM ET report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf) (captured by session 2b9f1ae1) supersedes it for pick availability.
- **Slate**: 31/31 games (11/13–16) match the [live official schedule](https://www.nba.com/schedule) (dates, matchups, tip times; 0 mismatches across three independent captures).
- **Picks**: all 22 pick games for 11/14–16 are inside the verified slate, re-checked against the FX-corrected pick file (spread labels 22/22 correct after the fix).
- **All CI checks green**: unit tests (13 + 29 + 16 verify tests), every site builder, drift checks, and 553+ internal links.
- Model headline numbers re-computed from raw out-of-sample rows (origin margin RMSE 16.1786 vs 17.3003 baseline; totals 20.3459 vs 19.5605 — total model is worse than baseline and is reported as such). STRAT1/STRAT2 ROI carries the moneyline caveat added by the FX fixes (−110 is not obtainable on moneyline sides; treat ROI as an arithmetic artefact until a price feed exists).

## Canonical dashboard (published 2026-11-14)

`https://wingbangboozle1-lang.github.io/NBA3/` is now **one dashboard with category sub-pages**, generated from a
single dataset (`data/app/canonical.json`). Every table row links to its source; anything that could not be
confirmed against an official source is left blank and listed on the **Flagged for review** page.

| Page | What it holds | Built from |
|---|---|---|
| `/` | Landing page: status cards, category navigation, highest-severity flags, links to the earlier snapshots | `scripts/build_app.py` |
| `/app/summary.html` | Executive summary — what was verified, model results, limits | `data/app/canonical.json` |
| `/app/methodology.html` | Method, the seven validation gates, how luck is kept out of the score, legal boundary | same |
| `/app/lines.html` | Originated spread + total for all 31 games of the 2026-11-13 → 2026-11-16 window | `data/origin/model_output.json` + official schedule |
| `/app/picks.html` | Picks for the next three days (22 games), availability flags, **no market price** | `data/picks/picks_2026-11-14_to_16.json` |
| `/app/props.html` | Player-prop projections (explicitly without a distribution) | `data/origin/model_output.json` |
| `/app/strategies.html` | Strategy leaderboard, gate-by-gate results, untestable candidates | `data/origin/model_output.json` |
| `/app/correlations.html` | Measured correlations + intervals, and the pairs left blank | same |
| `/app/injuries.html` | Official injury report, status changes vs the previous snapshot, minutes vacuum | `data/app/official_injuries_2026-11-13_0730PM.json` |
| `/app/gameflow.html` | Pace, rest, overtime, home court, and the factors still blocked | `data/origin/model_output.json` |
| `/app/questions.html` | Open questions: known / missing / how to discover | merged from the earlier sessions |
| `/app/suggestions.html` | Site-improvement suggestions with options and a recommendation (nothing implemented without a decision) | merged from the earlier sessions |
| `/app/verification.html` | Verification log | this session |
| `/app/sources.html` | Source register | merged |
| `/app/review.html` | Repository review, line by line | merged |
| `/app/flagged.html` | Flagged for review — every unverified value and irregularity, with source links | merged |
| `/review.html` | Cross-workstream audit by the 2026-11-14 integration session (R-01 – R-13) | hand-maintained |
| `/hub/` | **Consolidated dashboard (session 99eabb04)**: 18 pages — landing, executive summary, slate, originated lines, picks, strategy leaderboard, correlations, injuries, game flow, player props, data and integrity, sources, repository review, questions, suggestions, flagged for review, verification log, methodology. One identifier namespace, one set of numbers, every published row linked to its source. | `data/hub/**` via `scripts/build_hub_data.py` + `scripts/build_hub.py` (generated; do not edit `hub/` by hand) |
| `/executive-summary.html` | **Cross-site consolidated executive summary** (arena/3bf92fcc-nba3): verified data foundation, model results, gates, measured correlations, picks window, compliance flags, owner decisions — every number linked to its source; reconciled with the FX corrections. | Hand-maintained; verification performed 2026-11-14 |

### What was re-verified for this dashboard (2026-11-14)

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
python3 scripts/capture_official_2026_11_14.py   # official capture + cross-check against stored values
python3 scripts/assemble_canonical.py            # merge into data/app/canonical.json
python3 scripts/build_app.py                     # render app/ + index.html, check links and sources
python3 scripts/scan_table_sources.py            # repository-wide source-per-row screen
```

`scripts/build_app.py` fails the build if a table row has no `https` source link, if a link is broken or if
an in-page anchor does not resolve. `scripts/capture_official_2026_11_14.py` prints a verification report
comparing the official pages read on 2026-11-14 with the values already stored in the repository.

## Current status — read before using an output

- Experimental line, pick, prop, correlation, backtest, and injury-analysis artifacts exist under `lab/`, `edge/`, `origin/`, `data/`, and related sub-sites. Their snapshots, inputs, assumptions, samples, and gate statuses differ.
- Some artifacts identify Basketball-Reference and ESPN data among their inputs. The repository does not establish the necessary license or rights for use of those data in the intended product. NBA Terms of Use also include restrictions on NBA Statistics. Obtain qualified legal advice and written permission/provider terms before using or distributing these outputs.
- Some pages contain betting prices and “positive EV” labels. These are experimental derived outputs, not official NBA facts, proven edges, or betting advice. Do not act on them.
- Dates and injury reports are static snapshots. The NBA describes its schedule as subject to change and its injury reports as continually updated. There is no verified always-current production feed in this static Pages site.
- Local tests/builds validate selected code, data shape, source-link presence and internal links. They do **not** prove that every historical row matches an official NBA primary record, that sources are licensed, or that a model predicts profitably. A mechanical repository-wide HTML scan (session 2e50a71a) counted 1,521 table-body rows; 423 lacked a direct official NBA/Ksa link (389 excluding the archived `research-dashboard.html`). A second, independent scan on 2026-11-14 (`scripts/scan_table_sources.py`) counted 2,111 rows in 90 files, 369 without a direct official-host link; the canonical pages contribute 0 and the remainder sit in the earlier sub-sites. Neither scan is a manual classification of whether every row is factual, but both confirm the strict source-per-row requirement is met on the canonical pages and is still open across the earlier sub-sites; see [R-13](review.html) and the [Flagged for review](app/flagged.html) page.
- The 2026–27 NBA Terms and use of NBA-derived statistics, distribution to others, and Dutch regulatory obligations remain review items. This repository is not legal advice.
- **Update (session `99eabb04` round):** a consolidated dashboard at `/hub/` publishes the whole project in one
  place with one identifier namespace: the 31-game slate re-verified against nba.com/schedule and the official
  schedule PDF, the official 30-team table, the newest official injury report (11/13 07:30 PM), the originated
  lines, the 8-strategy leaderboard against 7 gates, the measured correlations, game flow, player props, picks
  for the three-day window, and the review pages (repository review, questions, suggestions, flagged,
  verification). Still true: **no strategy passes every gate (0 of 8)** and **no licensed odds feed is connected**.
  The repository's two origination engines publish a spread field with opposite sign conventions, so any
  cross-engine number has to be normalised before it is read (`F-24`).

**Primary dashboard:** https://wingbangboozle1-lang.github.io/NBA3/ (root landing) · **current numbers in one place:** https://wingbangboozle1-lang.github.io/NBA3/dash/<br>
**Flagged for Review:** https://wingbangboozle1-lang.github.io/NBA3/review.html<br>
**Repository audit log:** [`COORDINATION.md`](COORDINATION.md)

## Pages and workstreams

| URL path | Contents | Caution |
|---|---|---|
| `/` | Executive summary, readiness, categories, questions, suggestions and official-source references | Cross-workstream overview, not a canonical model |
| `/app/*` | Canonical dataset pages: executive summary, method, originated lines, picks, player props, strategies and gates, correlations, injuries and rotation, game flow, open questions, suggestions, verification log, source register, repository review, flagged for review | Derived values are labelled; official rows carry their source |
| `/review.html` | Source-linked inconsistencies, legal/data-rights questions, freshness and validation limits | Resolve before relying on outputs |
| `/site/` | Data dashboard, schedule/injury tables, sources and review material | Its files and ID namespace are distinct from the other dashboards |
| `/docs/` | Documentation tables, questions, validation framework and suggestions | Uses separate dated data snapshots |
| `/research/` | Research and requirements tables, source register, flags and questions | Build checks cover this site’s configured data and link rules, not the truth of every source value |
| `/lab/` | Experimental line origination, picks, player props and strategy tests | Not a vetted betting system; some outputs carry market/EV labels |
| `/edge/` | Independent line, pick, strategy, injury and game-flow dashboard | Separate pipeline and assumptions; not reconciled with `/lab/` or `/origin/` |
| `/dash/` | **Unified dashboard (integration round, session e40cd215)**: originated lines for the live 72-hour window, out-of-sample strategy leaderboard, 9 validation gates, measured correlations, injury/rotation register, game flow, cross-engine reconciliation, verification log, questions, suggestions and flagged items | Generated from `data/integration/model.json` by `integrate/engine.py` + `integrate/build_site.py`; byte-deterministic; `integrate/check.py` gates it |
| `/origin/` | Independent lines, correlation, props, injury analysis and walk-forward outputs | Separate dataset/model; not reconciled with `/edge/` |
| `/hub/` | **Consolidated dashboard (session 99eabb04)**: 18 pages over one identifier namespace — slate, originated lines, picks, 8-strategy leaderboard against 7 gates, correlations, injuries and minutes at risk, game flow, player props, data integrity, sources, repository review, questions, suggestions, flagged for review, verification log, methodology | Generated from `data/hub/dashboard.json` by `scripts/build_hub.py`; the build fails on an unsourced row, a non-https source or a broken link |

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
