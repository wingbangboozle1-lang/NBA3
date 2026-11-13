# NBA3 / NBA Edge Lab

Research-first NBA line-origination project: official-source data, validation gates, injury workflow, open decision questions, and items flagged for review.

## Published site (GitHub Pages)

Base: https://wingbangboozle1-lang.github.io/NBA3/

| Path | What it is | Built from |
|---|---|---|
| `/` (`index.html`) | Research dashboard: strategy framework, gates, questions, suggestions, flags, sources. Links to both data sites below. | Hand-maintained (f879620b); nav link added by integration |
| `/site/` | **Edge Lab site** (arena/7c532e8c): landing page, executive summary, injuries, game-flow, 3-day slate, strategies, validation, questions, suggestions, sources, flagged items, repo review. Every table row links to an official source. | `data/*.json` via `scripts/build_site.py` (generated; do not edit `site/` by hand) |
| `/docs/` | Data site (arena/f879620b): injuries (11/11 report), slate, rules extracts, questions, gates, suggestions, flags. | `docs/data/data.json` (hand-maintained) |
| `/edge/` | **Edge Lab dashboard (arena-0a016df8)**: verified 174-game log, originated lines/spreads/totals/fair MLs, walk-forward-validated strategies with published gate results, 3-day picks with availability flags, official injury report tables, game-flow metrics, verification log. | `data/raw|model|processed|picks/**` via `pipeline/` (build_data → run_model → make_picks → make_props → build_site_data) |

The two data sites are separate snapshots and use separate ID schemes. See *ID namespaces* below.

## Current state (research only)

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
```

Standard library only (Python 3.11+). No network access is needed to build.

## ID namespaces

Both sessions used `F-01…` and other short IDs with different meanings. Mapping:

| Session | Flags | Suggestions | Questions | Sources |
|---|---|---|---|---|
| arena/7c532e8c (site/) | `7C-F-01…7C-F-17` | `SG-01…SG-11` | `Q-01…Q-14` | `S01…S11` |
| arena/f879620b (docs/) | `F-01…F-15` | `SG01…SG09` | `Q01…Q12` | `S1…S9` |

Do not compare IDs across the two sites without this table.

## Verification rules

1. Every data row carries an official `https` source (NBA, Ksa, or GitHub for repository facts), or it is flagged as unverified and left blank.
2. Source IDs must exist in `data/sources.json` (site/) or in `docs/data/data.json` (docs/).
3. Injury rows are attributed R (printed), S (team printed, matchup via official schedule pairing), U (not extracted, left blank), or T (team status row). Non-R rows carry a flag.
4. External links are not fetched during the build (scheduled link checking is proposed as SG-07).

## Important limits

No licensed odds feed, historical results, or validated picks are in this repository. No betting lines, correlations, player projections, or performance claims are shown. Candidate strategies are hypotheses. All validation gates are blocked until verified inputs exist. Check the Flagged for Review pages and the open questions before any decision.

Nothing in this repository is betting advice. Follow local law and responsible-gambling practice.

## Research site (`/research/`, session arena/9ed6085f)

Generated from `data/*.csv` by `pipeline/build_site.py` into `research/` (not the repository root). Checked by `pipeline/verify.py`.

| Item | Value |
|---|---|
| Slates | 31 games, Nov 13–16 2026 (ET), verified against `nba.com/schedule` (chunks 0–2 of 9) |
| Injury snapshot | 11/13/26 11:00 AM ET (98 rows, transcribed from PDF text). `site/` uses the later 5:00 PM report (117 rows), so the two sites show different snapshots. Owner to choose the current one (flag F01). |
| Picks / lines / correlations | None published (blank by design; flags F13, F14, F21) |
| Strategies / gates | 11 strategies and 11 gates; all BLOCKED. Thresholds are proposals. |

**ID namespaces (this site):** flags `F01–F25`, sources `S01–S19`, questions `Q-…`, suggestions `SG-01–SG-14`, gates `G01–G11`, strategies `ST01–ST11`, requirements `RQ01–RQ23`, repo review `R01–R17`. These do not match the namespaces in the table above. Compare IDs across sites only with a mapping.

Rebuild and check:

```bash
python3 -m unittest discover -s pipeline/tests
python3 pipeline/build_site.py
python3 pipeline/verify.py
```

---

## Session `e22a2831` — independent line-origination engine (`/origin/`)

An independently built line-origination and strategy-validation engine, published **alongside**
the sites above rather than over them. It shares no code or data with `/edge/`, `/site/`,
`/docs/`, `/lab/` or `/research/`.

| Path | What it is |
|---|---|
| [`/origin/`](origin/index.html) | 11-page dashboard: originated lines, strategy leaderboard, correlations, injury impact, player props, game flow, data & sources, flagged for review, site improvements, open questions |
| `origin/notes/` | The same material in Markdown, generated from the same model artefact |
| `data/origin/` | Verified inputs (174 games) + `model_output.json`, the single source of truth |
| `model/` | `nbastats.py` (stdlib statistics), `build.py`, `build_docs.py` |

### Results

| | |
|---|---|
| Games verified, 20 Oct – 12 Nov | **174** — 348 team-games, **zero** discrepancy against the official GP column, all 30 teams; recomputed W-L matches official W-L |
| Margin model (walk-forward, 114 OOS games) | RMSE **16.18** vs 17.30 baseline |
| Total model | RMSE **20.35** vs 19.56 baseline — **no improvement**, reported as such |
| Strategies passing all 7 gates | **0 of 8** (two provisionals, both under-powered) |

Built with the standard library only (`numpy`/`scipy`/`pandas` are unavailable in this
workspace). Reproduce with:

```bash
python3 model/build.py && python3 model/build_docs.py && python3 model/build_site.py
```

See [`COORDINATION.md`](COORDINATION.md#session-e22a2831-arenae22a2831-nba3--line-origination-walk-forward-validation-origin-site)
for the task board, cross-session change requests and the note on how `/origin/` and `/edge/`
overlap.
