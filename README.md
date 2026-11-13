# NBA3

Research dashboard for NBA signal generation and validation.

**Live site:** https://wingbangboozle1-lang.github.io/NBA3/ (GitHub Pages, served from `docs/`)

## What is here

| Path | Purpose |
|---|---|
| `docs/` | Static dashboard (GitHub Pages source). Every table is built from `docs/data/data.json`. |
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

## Status

- No betting lines, odds, player box scores or minutes are verified yet, so no strategies are validated, no correlations are computed and no picks are generated. See the Questions page.
- Nothing on this site is betting advice.
