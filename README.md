# NBA3 / NBA Edge Lab

Research repository for NBA line origination, strategy evaluation, injuries, game flow, and decision support. The repository contains **multiple independently built analysis/site workstreams**. They are not a single reconciled model. This overview intentionally does not endorse any line, pick, market edge, correlation, ROI, or leaderboard result.

## Current status — read before using an output

- Experimental line, pick, prop, correlation, backtest, and injury-analysis artifacts exist under `lab/`, `edge/`, `origin/`, `data/`, and related sub-sites. Their snapshots, inputs, assumptions, samples, and gate statuses differ.
- Some artifacts identify Basketball-Reference and ESPN data among their inputs. The repository does not establish the necessary license or rights for use of those data in the intended product. NBA Terms of Use also include restrictions on NBA Statistics. Obtain qualified legal advice and written permission/provider terms before using or distributing these outputs.
- Some pages contain betting prices and “positive EV” labels. These are experimental derived outputs, not official NBA facts, proven edges, or betting advice. Do not act on them.
- Dates and injury reports are static snapshots. The NBA describes its schedule as subject to change and its injury reports as continually updated. There is no verified always-current production feed in this static Pages site.
- Local tests/builds validate selected code, data shape, source-link presence and internal links. They do **not** prove that every historical row matches an official NBA primary record, that sources are licensed, or that a model predicts profitably. A mechanical repository-wide HTML scan counted 1,521 table-body rows; 423 lacked a direct official NBA/Ksa link (389 excluding the archived `research-dashboard.html`). This is not a manual classification of whether every row is factual, but confirms the strict source-per-row requirement is not yet satisfied across all sub-sites; see [R-13](review.html).
- The 2026–27 NBA Terms and use of NBA-derived statistics, distribution to others, and Dutch regulatory obligations remain review items. This repository is not legal advice.

**Primary dashboard:** https://wingbangboozle1-lang.github.io/NBA3/ (root landing) · **current numbers in one place:** https://wingbangboozle1-lang.github.io/NBA3/dash/<br>
**Flagged for Review:** https://wingbangboozle1-lang.github.io/NBA3/review.html<br>
**Repository audit log:** [`COORDINATION.md`](COORDINATION.md)

## Pages and workstreams

| URL path | Contents | Caution |
|---|---|---|
| `/` | Executive summary, readiness, categories, questions, suggestions and official-source references | Cross-workstream overview, not a canonical model |
| `/review.html` | Source-linked inconsistencies, legal/data-rights questions, freshness and validation limits | Resolve before relying on outputs |
| `/site/` | Data dashboard, schedule/injury tables, sources and review material | Its files and ID namespace are distinct from the other dashboards |
| `/docs/` | Documentation tables, questions, validation framework and suggestions | Uses separate dated data snapshots |
| `/research/` | Research and requirements tables, source register, flags and questions | Build checks cover this site’s configured data and link rules, not the truth of every source value |
| `/lab/` | Experimental line origination, picks, player props and strategy tests | Not a vetted betting system; some outputs carry market/EV labels |
| `/edge/` | Independent line, pick, strategy, injury and game-flow dashboard | Separate pipeline and assumptions; not reconciled with `/lab/` or `/origin/` |
| `/dash/` | **Unified dashboard (integration round, session e40cd215)**: originated lines for the live 72-hour window, out-of-sample strategy leaderboard, 9 validation gates, measured correlations, injury/rotation register, game flow, cross-engine reconciliation, verification log, questions, suggestions and flagged items | Generated from `data/integration/model.json` by `integrate/engine.py` + `integrate/build_site.py`; byte-deterministic; `integrate/check.py` gates it |
| `/origin/` | Independent lines, correlation, props, injury analysis and walk-forward outputs | Separate dataset/model; not reconciled with `/edge/` |

Treat these as independent work products. Do not compare metrics across them without aligning source data, snapshots, dates, definitions, evaluation splits, odds, settlement, and statistical methods.

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
