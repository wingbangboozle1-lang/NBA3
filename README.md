# NBA3 / NBA Edge Lab

Research repository for NBA line origination, strategy evaluation, injuries, game flow, and decision support. The repository contains **multiple independently built analysis/site workstreams**. They are not a single reconciled model. This overview intentionally does not endorse any line, pick, market edge, correlation, ROI, or leaderboard result.

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
- Local tests/builds validate selected code, data shape, source-link presence and internal links. They do **not** prove that every historical row matches an official NBA primary record, that sources are licensed, or that a model predicts profitably. A mechanical repository-wide HTML scan (session 2e50a71a) counted 1,521 table-body rows; 423 lacked a direct official NBA/Ksa link (389 excluding the archived `research-dashboard.html`). A second, independent scan on 2026-11-14 (`scripts/scan_table_sources.py`) counted 2,091 rows in 89 files, 369 without a direct official-host link; the canonical pages contribute 0 and the remainder sit in the earlier sub-sites. Neither scan is a manual classification of whether every row is factual, but both confirm the strict source-per-row requirement is met on the canonical pages and is still open across the earlier sub-sites; see [R-13](review.html) and the [Flagged for review](app/flagged.html) page.
- The 2026–27 NBA Terms and use of NBA-derived statistics, distribution to others, and Dutch regulatory obligations remain review items. This repository is not legal advice.

**Primary dashboard:** https://wingbangboozle1-lang.github.io/NBA3/<br>
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

## Rebuild and verification commands

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
```

GitHub Pages combines static site folders in `.github/workflows/pages.yml`. Static publication is not a live feed or automated daily data refresh.
