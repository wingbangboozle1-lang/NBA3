# NBA3 — NBA Edge Lab

A research-first project to **originate our own NBA lines**, validate strategies through gates
that remove luck, quantify correlations for parlays, and generate picks for every upcoming slate
up to 3 days in advance — published on a GitHub Pages dashboard where **every factual table row
links to its source**.

**Live site:** https://wingbangboozle1-lang.github.io/NBA3/

## View

Open [`index.html`](index.html) (landing dashboard), or see the GitHub Pages URL above.
The workflow in `.github/workflows/pages.yml` deploys the static dashboard from `main`.

## What is here
| Path | Contents |
|---|---|
| `COORDINATION.md` | Shared task board for parallel agent sessions (read before working) |
| `index.html` | Landing dashboard (round-2 integration; round-1 framework preserved at `research-dashboard.html`) |
| `site/` | Dashboard subpages: slate picks, originated lines, strategies & gates, correlations, injuries, data tables, suggestions, open questions, flagged for review |
| `data/` | Collected data (schedule, results, injuries) with sources & as-of dates |
| `pipeline/` | Reproducible Python: data build → model → validation → picks |
| `docs/` | Methodology, executive summary, open questions, suggestions, verification log |

## Core principles
1. **No hallucinations** — every factual value carries a link to its source (official NBA.com
   sources preferred; trusted secondary sources labeled as such). Values that cannot be confirmed
   from a cited source are left **blank** and published on the *Flagged for Review* page.
2. **Model outputs are labeled as originated** — our lines/picks are estimates, never presented
   as sourced facts.
3. **Validation gates** — a strategy is only promoted if it passes every gate (sample size,
   calibration, edge, drawdown, correlation caps). Details in `docs/methodology.md`.
4. **Parallel sessions** coordinate via `COORDINATION.md`.

## Important limits

Data is limited to what could be verified from reachable sources during the session — there is
**no licensed odds feed**, no proprietary injury feed beyond the NBA's public injury report PDFs,
and backtest samples are bounded by public game results. Strategies whose gates cannot be
evaluated or passed are published as **experimental / not eligible** rather than as validated
picks. Consult the **Flagged for Review** and **Open questions** pages before any implementation.

## Reproduce
```bash
python3 -m pip install -r requirements.txt
python3 pipeline/build_data.py      # 1. assemble + validate collected data
python3 pipeline/run_model.py       # 2. originate lines + run validation gates
python3 pipeline/make_picks.py      # 3. picks for the next 3 days
python3 pipeline/build_site_data.py # 4. emit JSON for the Pages dashboard
```

## Sources

Official NBA sources (NBA.com, official.nba.com injury reports) and trusted secondary sources
(Basketball-Reference) are linked per-row in the data tables. Sources establish facts only; they
do not establish predictive edge, minutes forecasts, or data redistribution rights.
