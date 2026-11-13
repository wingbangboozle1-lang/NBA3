# NBA3 / NBA Edge Lab

Research-first NBA line-origination project: official-source data, validation gates, injury workflow, open decision questions, and items flagged for review.

## Published site (GitHub Pages)

Base: https://wingbangboozle1-lang.github.io/NBA3/

| Path | What it is | Built from |
|---|---|---|
| `/` (`index.html`) | Research dashboard: strategy framework, gates, questions, suggestions, flags, sources. Links to both data sites below. | Hand-maintained (f879620b); nav link added by integration |
| `/site/` | **Edge Lab site** (arena/7c532e8c): landing page, executive summary, injuries, game-flow, 3-day slate, strategies, validation, questions, suggestions, sources, flagged items, repo review. Every table row links to an official source. | `data/*.json` via `scripts/build_site.py` (generated; do not edit `site/` by hand) |
| `/docs/` | Data site (arena/f879620b): injuries (11/11 report), slate, rules extracts, questions, gates, suggestions, flags. | `docs/data/data.json` (hand-maintained) |

The two data sites are separate snapshots and use separate ID schemes. See *ID namespaces* below.

## Current state (research only)

- No lines, picks, or correlation values are published. Blocking items are on the [Flagged for Review](site/flagged.html) page:
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
