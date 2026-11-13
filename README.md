# NBA3 / NBA Edge Lab

Research-first NBA line-origination project: official-source data, validation gates, injury workflow, open decision questions, and items flagged for review.

## View

- **Root dashboard (research framework):** [`index.html`](index.html) — served by GitHub Pages from `main`.
- **Data site (tables with source links):** [`docs/index.html`](docs/index.html) — landing page, executive summary, Injuries, Upcoming slate, Rules, Strategies, Questions, Suggestions, Sources, Flagged for Review. Every table row links to an official source.

The workflow in `.github/workflows/pages.yml` deploys the repository from `main`.

## What is here

| Path | Purpose |
|---|---|
| `index.html` | Research dashboard (framework, gates, questions, suggestions, flags). |
| `docs/` | Data site. Tables are built from `docs/data/data.json`. |
| `docs/data/data.json` | Single data file: sources, injury rows, upcoming slate, rule extracts, questions, gates, suggestions, flags. |
| `tools/validate_gates.py` | Stdlib statistics: exact binomial test, Wilson interval, Benjamini–Hochberg, Pearson r, parlay dependence ratio, gate checks. Thresholds are proposals. |
| `tools/check_site.py` | Checks that every data row has a resolving `https://` source, every internal link exists, and renderer hooks are valid. |
| `tests/test_validate_gates.py` | Unit tests for the statistics module. |
| `COORDINATION.md` | Shared task board for parallel sessions. |

## Checks

```bash
python3 -m unittest tests/test_validate_gates.py   # statistics tests
python3 tools/check_site.py                         # data + link check
```

## Important limits

This repository does not contain a licensed odds feed, historical results, injury ingestion, or validated picks. No betting lines, correlations, player projections, or performance claims are shown. Candidate strategies are hypotheses. All validation gates are blocked until verified inputs exist. Check the **Flagged for review** and **Open questions** sections before any decision.

Nothing in this repository is betting advice. Follow local law and responsible-gambling practice.

## Sources

Official sources used are listed on the Sources page of the data site (`docs/sources.html`) and in the root dashboard's source section.
