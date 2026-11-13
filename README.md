# NBA Edge Lab

Research dashboard for NBA slates, injury snapshots, strategy hypotheses and validation gates. Built from official sources. Blank values are unverified and flagged. Nothing is inferred.

**Status:** No originated lines, picks, or correlation values are published. Every strategy is blocked by the validation gates because no authorised historical data or prices are reachable from this environment.

## Layout

- `data/` – CSV registers: slates, injuries, strategies, gates, correlations, game flow, sources, questions, suggestions, repo review, requirements, flags.
- `pipeline/` – standard-library Python only:
  - `build_site.py` writes the generated pages to the repository root from `data/`.
  - `verify.py` checks data rules and the built site (source links, internal links, blank-cell flags).
  - `gates.py` and `rotation.py` hold the validation and minutes helpers.
  - `tests/` holds unit tests.

- `COORDINATION.md` – shared task board and verification log.

## Run

```
python3 -m unittest discover -s pipeline/tests
python3 pipeline/build_site.py
python3 pipeline/verify.py
```

Deployment: GitHub Pages serves the branch root of `main` (legacy source). `.github/workflows/pages.yml` runs the unit tests, rebuilds the pages, runs `verify.py`, and fails if the committed pages differ from a fresh build.

## Limits

- Injury data: one official snapshot (11/13/26 11:00 AM ET), transcribed from PDF text. Team and matchup cells missing in the PDF are blank.
- Schedule: Nov 13–16, 2026 (ET), 31 games.
- No licence is declared on this repository, so no reuse is granted (flag F18). See the Flagged for Review page.
