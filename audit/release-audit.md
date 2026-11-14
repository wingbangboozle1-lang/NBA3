# NBA3 release audit

> **Audit baseline:** `c4623a05def6`. This is an offline, repository-local audit; no NBA page or PDF was fetched by this tool. Links below are supplied for manual review; stored values are not newly verified against a live official source here.
> **Decision status:** Code and data-governance review only. This audit does not establish a profitable strategy or approve a wager.

## Executive summary

| Check | Result | Source / evidence |
|---|---|---|
| Pages workflow conflict markers | 0 | [workflow source](https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/pages.yml) |
| Pages-staged HTML | 136 files | [staging list](https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/pages.yml) |
| HTML table-body rows | 3421 | [NBA Stats glossary (terminology reference)](https://www.nba.com/stats/help/glossary) |
| Rows with direct NBA official link | 2083 | [NBA schedule (manual review)](https://www.nba.com/schedule?date=2026-11-14) |
| Rows without NBA/regulator/statistical-authority links | 1221 | [row-by-row CSV](https://github.com/wingbangboozle1-lang/NBA3/blob/main/audit/table-source-audit.csv) |
| Timestamped picks checked | 32 | [official schedule snapshot](https://www.nba.com/schedule?date=2026-11-14) |
| 72-hour violations | 3 | [NBA official schedule](https://www.nba.com/schedule?date=2026-11-14) |

## Findings

| ID / severity | Finding | Evidence | Official reference |
|---|---|---|---|
| RA-02 / high (open) | **The unified dashboard's citation check is page-wide, not table-row-wide.**<br>`integrate/check.py` looks for an HTTPS link anywhere in a page body for each table; it does not collect links per row. The independent row parser found 1085 staged table rows with no direct NBA, regulator/statute, or statistical-authority link and no explicit unverified marker. | [repository evidence](https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/check.py) | [official reference](https://www.nba.com/stats/help/glossary) |
| RA-03 / high (open) | **Some published table rows have no direct NBA or authority source link.**<br>Across 136 Pages-staged HTML files, 3421 table-body rows were inspected. 1221 rows have no direct NBA, regulator/statute, or statistical-authority link. Repository-code links are classified separately and do not count as NBA data citations. | [repository evidence](https://github.com/wingbangboozle1-lang/NBA3/blob/main/audit/table-source-audit.csv) | [official reference](https://www.nba.com/stats/help/glossary) |
| RA-04 / high (open) | **3 published pick(s) exceed the exact 72-hour horizon.**<br>POR @ MIN 2026-11-16 8:00 PM ET: 72.17h (+10 min); GSW @ NOP 2026-11-16 8:00 PM ET: 72.17h (+10 min); PHX @ DEN 2026-11-16 9:00 PM ET: 73.17h (+70 min). Keep only picks whose official tip time is within 72 hours of a timezone-aware generation timestamp, or explicitly define a different date-based policy. | [repository evidence](https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/picks/picks_2026-11-14_to_16.json) | [official reference](https://www.nba.com/schedule?date=2026-11-14) |
| RA-05 / high (open) | **The canonical 'official capture' CI step is an offline hard-coded transcription check, not a live re-fetch.**<br>The script contains static schedule, team-statistics, and injury-report constants and has no HTTP client import. Running it in CI checks the committed snapshot against those same constants; it cannot establish that a source is current or independently re-verify the transcription. | [repository evidence](https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/capture_official_2026_11_14.py) | [official reference](https://www.nba.com/schedule?date=2026-11-14) |
| RA-06 / medium (open) | **The unified line artifact has no exact generation timestamp for a strict 72-hour check.**<br>The artifact carries a date window and `horizon_days`, but no timezone-aware generation time. The exact tip-time horizon for its lines therefore cannot be reproduced from the artifact alone. | [repository evidence](https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json) | [official reference](https://www.nba.com/schedule?date=2026-11-14) |
| RA-07 / medium (open) | **The earlier source scanner treats GitHub repository links as 'official' links.**<br>GitHub is primary evidence for repository facts and code, but it does not make a row's NBA statistics or injury values official. This audit keeps repository evidence in a separate class. | [repository evidence](https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/scan_table_sources.py) | [official reference](https://www.nba.com/stats/help/glossary) |

## Per-file source coverage

A row is counted as directly sourced only when that row itself contains an HTTPS link to an NBA, regulator/statute, or statistical-authority host. Repository-code links are listed separately and are not presented as official NBA data sources.

| Published HTML file | Rows | NBA links | Regulator/statute links | Statistical authority links | No official link, unflagged | Repository evidence | File evidence |
|---|---:|---:|---:|---:|---:|---:|---|
| `app/correlations.html` | 7 | 7 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/correlations.html) |
| `app/flagged.html` | 61 | 47 | 5 | 2 | 7 | 5 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/flagged.html) |
| `app/gameflow.html` | 24 | 21 | 0 | 0 | 3 | 3 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/gameflow.html) |
| `app/injuries.html` | 162 | 162 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/injuries.html) |
| `app/legacy/root-dashboard-2026-11-13.html` | 38 | 4 | 0 | 0 | 25 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/legacy/root-dashboard-2026-11-13.html) |
| `app/lines.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/lines.html) |
| `app/methodology.html` | 18 | 0 | 0 | 4 | 13 | 14 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/methodology.html) |
| `app/picks.html` | 28 | 24 | 0 | 0 | 4 | 4 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/picks.html) |
| `app/props.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/props.html) |
| `app/questions.html` | 35 | 16 | 9 | 5 | 3 | 4 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/questions.html) |
| `app/requirements.html` | 23 | 6 | 2 | 3 | 9 | 11 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/requirements.html) |
| `app/review.html` | 30 | 7 | 0 | 0 | 23 | 21 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/review.html) |
| `app/sources.html` | 35 | 21 | 7 | 4 | 3 | 2 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/sources.html) |
| `app/strategies.html` | 41 | 15 | 1 | 7 | 17 | 18 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/strategies.html) |
| `app/suggestions.html` | 30 | 14 | 4 | 3 | 9 | 9 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/suggestions.html) |
| `app/summary.html` | 11 | 5 | 0 | 0 | 6 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/summary.html) |
| `app/verification.html` | 10 | 9 | 0 | 0 | 1 | 1 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/verification.html) |
| `dash/correlations.html` | 9 | 0 | 0 | 0 | 6 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/correlations.html) |
| `dash/data.html` | 16 | 0 | 0 | 0 | 15 | 8 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/data.html) |
| `dash/flagged.html` | 20 | 6 | 0 | 0 | 11 | 14 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/flagged.html) |
| `dash/gameflow.html` | 34 | 22 | 0 | 0 | 9 | 9 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/gameflow.html) |
| `dash/gates.html` | 15 | 0 | 0 | 0 | 15 | 9 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/gates.html) |
| `dash/index.html` | 11 | 5 | 0 | 0 | 4 | 3 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/index.html) |
| `dash/injuries.html` | 44 | 44 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/injuries.html) |
| `dash/leaderboard.html` | 13 | 0 | 0 | 0 | 13 | 13 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/leaderboard.html) |
| `dash/lines.html` | 22 | 22 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/lines.html) |
| `dash/picks.html` | 45 | 22 | 0 | 0 | 9 | 13 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/picks.html) |
| `dash/questions.html` | 10 | 3 | 1 | 1 | 5 | 5 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/questions.html) |
| `dash/reconciliation.html` | 55 | 22 | 0 | 0 | 33 | 11 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/reconciliation.html) |
| `dash/sources.html` | 20 | 10 | 1 | 1 | 7 | 4 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/sources.html) |
| `dash/suggestions.html` | 14 | 2 | 0 | 0 | 9 | 12 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/suggestions.html) |
| `dash/verification.html` | 14 | 8 | 0 | 0 | 6 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/dash/verification.html) |
| `docs/executive-summary.html` | 5 | 5 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/docs/executive-summary.html) |
| `docs/strategies.html` | 5 | 0 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/docs/strategies.html) |
| `edge/methodology.html` | 10 | 0 | 0 | 0 | 10 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/edge/methodology.html) |
| `executive-summary.html` | 76 | 7 | 1 | 0 | 65 | 27 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/executive-summary.html) |
| `hub/correlations.html` | 7 | 3 | 0 | 0 | 0 | 4 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/correlations.html) |
| `hub/data.html` | 33 | 30 | 0 | 0 | 3 | 3 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/data.html) |
| `hub/executive-summary.html` | 12 | 7 | 0 | 0 | 5 | 5 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/executive-summary.html) |
| `hub/flagged.html` | 24 | 12 | 1 | 0 | 11 | 10 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/flagged.html) |
| `hub/gameflow.html` | 35 | 30 | 0 | 0 | 5 | 5 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/gameflow.html) |
| `hub/index.html` | 13 | 4 | 1 | 0 | 8 | 8 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/index.html) |
| `hub/injuries.html` | 184 | 184 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/injuries.html) |
| `hub/lines.html` | 48 | 31 | 0 | 0 | 17 | 17 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/lines.html) |
| `hub/picks.html` | 27 | 0 | 0 | 0 | 24 | 27 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/picks.html) |
| `hub/props.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/props.html) |
| `hub/questions.html` | 16 | 7 | 0 | 0 | 9 | 9 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/questions.html) |
| `hub/repo-review.html` | 26 | 2 | 0 | 0 | 24 | 22 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/repo-review.html) |
| `hub/slate.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/slate.html) |
| `hub/sources.html` | 20 | 14 | 1 | 0 | 5 | 1 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/sources.html) |
| `hub/strategies.html` | 20 | 0 | 0 | 0 | 20 | 20 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/strategies.html) |
| `hub/suggestions.html` | 12 | 0 | 0 | 0 | 12 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/suggestions.html) |
| `hub/verification.html` | 21 | 12 | 0 | 0 | 8 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/hub/verification.html) |
| `lab/index.html` | 11 | 0 | 0 | 0 | 11 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/index.html) |
| `lab/injuries.html` | 18 | 17 | 0 | 0 | 1 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/injuries.html) |
| `lab/lines.html` | 53 | 23 | 0 | 0 | 30 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/lines.html) |
| `lab/methodology.html` | 26 | 0 | 0 | 0 | 25 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/methodology.html) |
| `lab/picks.html` | 20 | 20 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/picks.html) |
| `lab/props.html` | 12 | 0 | 0 | 0 | 3 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/props.html) |
| `lab/questions.html` | 10 | 10 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/questions.html) |
| `lab/review.html` | 17 | 2 | 0 | 0 | 10 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/review.html) |
| `lab/strategies.html` | 79 | 0 | 0 | 0 | 77 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/strategies.html) |
| `lab/suggestions.html` | 10 | 0 | 0 | 0 | 10 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/lab/suggestions.html) |
| `origin/correlations.html` | 7 | 3 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/correlations.html) |
| `origin/data.html` | 210 | 210 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/data.html) |
| `origin/flagged.html` | 16 | 0 | 0 | 0 | 14 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/flagged.html) |
| `origin/gameflow.html` | 35 | 30 | 0 | 0 | 5 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/gameflow.html) |
| `origin/index.html` | 11 | 6 | 0 | 0 | 5 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/index.html) |
| `origin/injuries.html` | 175 | 175 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/injuries.html) |
| `origin/lines.html` | 61 | 61 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/lines.html) |
| `origin/props.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/props.html) |
| `origin/questions.html` | 15 | 5 | 0 | 0 | 10 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/questions.html) |
| `origin/strategies.html` | 18 | 0 | 0 | 0 | 18 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/strategies.html) |
| `origin/suggestions.html` | 15 | 0 | 0 | 0 | 13 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/origin/suggestions.html) |
| `research/correlations.html` | 8 | 2 | 0 | 6 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/correlations.html) |
| `research/flagged.html` | 25 | 18 | 2 | 2 | 3 | 2 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/flagged.html) |
| `research/gameflow.html` | 7 | 7 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/gameflow.html) |
| `research/gates.html` | 11 | 0 | 0 | 4 | 0 | 7 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/gates.html) |
| `research/injuries.html` | 98 | 98 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/injuries.html) |
| `research/picks.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/picks.html) |
| `research/questions.html` | 18 | 7 | 4 | 3 | 2 | 2 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/questions.html) |
| `research/repo-review.html` | 17 | 4 | 0 | 0 | 13 | 12 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/repo-review.html) |
| `research/requirements.html` | 23 | 6 | 2 | 3 | 9 | 11 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/requirements.html) |
| `research/slates.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/slates.html) |
| `research/sources.html` | 19 | 8 | 5 | 4 | 2 | 1 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/sources.html) |
| `research/strategies.html` | 11 | 7 | 1 | 3 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/strategies.html) |
| `research/suggestions.html` | 14 | 6 | 1 | 2 | 5 | 5 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/research/suggestions.html) |
| `review.html` | 13 | 12 | 1 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/review.html) |
| `site/executive-summary.html` | 5 | 4 | 1 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/executive-summary.html) |
| `site/flagged.html` | 17 | 11 | 2 | 0 | 3 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/flagged.html) |
| `site/game-flow.html` | 28 | 28 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/game-flow.html) |
| `site/injuries.html` | 117 | 117 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/injuries.html) |
| `site/questions.html` | 14 | 6 | 2 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/questions.html) |
| `site/repo-review.html` | 7 | 0 | 0 | 0 | 7 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/repo-review.html) |
| `site/slate.html` | 31 | 31 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/slate.html) |
| `site/sources.html` | 11 | 9 | 2 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/sources.html) |
| `site/strategies.html` | 11 | 4 | 0 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/strategies.html) |
| `site/suggestions.html` | 11 | 5 | 3 | 0 | 3 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/suggestions.html) |
| `site/validation.html` | 10 | 2 | 1 | 0 | 0 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/site/validation.html) |
| `verify/pages/claims.html` | 27 | 3 | 0 | 0 | 21 | 23 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/claims.html) |
| `verify/pages/contradictions.html` | 9 | 2 | 0 | 0 | 7 | 7 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/contradictions.html) |
| `verify/pages/corrections.html` | 10 | 0 | 0 | 0 | 9 | 5 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/corrections.html) |
| `verify/pages/decisions.html` | 19 | 5 | 1 | 0 | 12 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/decisions.html) |
| `verify/pages/executive.html` | 10 | 0 | 0 | 0 | 10 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/executive.html) |
| `verify/pages/flagged.html` | 30 | 3 | 1 | 0 | 23 | 12 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/flagged.html) |
| `verify/pages/index.html` | 14 | 2 | 0 | 0 | 12 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/index.html) |
| `verify/pages/injuries.html` | 15 | 0 | 0 | 0 | 15 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/injuries.html) |
| `verify/pages/ledger.html` | 26 | 10 | 0 | 0 | 16 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/ledger.html) |
| `verify/pages/questions.html` | 14 | 5 | 1 | 0 | 7 | 6 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/questions.html) |
| `verify/pages/results.html` | 174 | 0 | 0 | 0 | 174 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/results.html) |
| `verify/pages/sources.html` | 12 | 9 | 1 | 0 | 2 | 0 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/sources.html) |
| `verify/pages/suggestions.html` | 10 | 1 | 1 | 0 | 7 | 7 | [source file](https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/suggestions.html) |

## 72-hour horizon details

Tip times are converted from Eastern Time using the IANA `America/New_York` zone. Rows without a timezone-aware generation timestamp or an exact official-schedule match are left unresolved; no date or time is inferred.

| File / row | Game | Generation UTC | Official tip time ET | Hours ahead | Result | Official game source |
|---|---|---|---|---:|---|---|
| `data/picks/picks_2026-11-14_to_16.json` #1 | DEN @ NOP 2026-11-14 | 2026-11-14T00:49:56Z | 7:00 PM | 23.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/den-vs-nop-0022600231) |
| `data/picks/picks_2026-11-14_to_16.json` #2 | DAL @ CLE 2026-11-14 | 2026-11-14T00:49:56Z | 7:30 PM | 23.6678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/dal-vs-cle-0022600232) |
| `data/picks/picks_2026-11-14_to_16.json` #3 | BKN @ MEM 2026-11-14 | 2026-11-14T00:49:56Z | 8:00 PM | 24.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/bkn-vs-mem-0022600234) |
| `data/picks/picks_2026-11-14_to_16.json` #4 | DET @ MIA 2026-11-14 | 2026-11-14T00:49:56Z | 8:00 PM | 24.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/det-vs-mia-0022600233) |
| `data/picks/picks_2026-11-14_to_16.json` #5 | CHI @ MIN 2026-11-14 | 2026-11-14T00:49:56Z | 8:00 PM | 24.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/chi-vs-min-0022600235) |
| `data/picks/picks_2026-11-14_to_16.json` #6 | IND @ PHI 2026-11-15 | 2026-11-14T00:49:56Z | 1:00 PM | 41.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/ind-vs-phi-0022600236) |
| `data/picks/picks_2026-11-14_to_16.json` #7 | LAL @ PHX 2026-11-15 | 2026-11-14T00:49:56Z | 4:00 PM | 44.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/lal-vs-phx-0022600237) |
| `data/picks/picks_2026-11-14_to_16.json` #8 | CHA @ LAC 2026-11-15 | 2026-11-14T00:49:56Z | 4:30 PM | 44.6678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/cha-vs-lac-0022600238) |
| `data/picks/picks_2026-11-14_to_16.json` #9 | SAS @ UTA 2026-11-15 | 2026-11-14T00:49:56Z | 5:00 PM | 45.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/sas-vs-uta-0022600239) |
| `data/picks/picks_2026-11-14_to_16.json` #10 | DAL @ BOS 2026-11-15 | 2026-11-14T00:49:56Z | 6:00 PM | 46.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/dal-vs-bos-0022600240) |
| `data/picks/picks_2026-11-14_to_16.json` #11 | NYK @ TOR 2026-11-15 | 2026-11-14T00:49:56Z | 6:00 PM | 46.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/nyk-vs-tor-0022600241) |
| `data/picks/picks_2026-11-14_to_16.json` #12 | HOU @ WAS 2026-11-15 | 2026-11-14T00:49:56Z | 7:00 PM | 47.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/hou-vs-was-0022600242) |
| `data/picks/picks_2026-11-14_to_16.json` #13 | ATL @ MIL 2026-11-15 | 2026-11-14T00:49:56Z | 8:00 PM | 48.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/atl-vs-mil-0022600243) |
| `data/picks/picks_2026-11-14_to_16.json` #14 | OKC @ SAC 2026-11-15 | 2026-11-14T00:49:56Z | 9:00 PM | 49.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/okc-vs-sac-0022600244) |
| `data/picks/picks_2026-11-14_to_16.json` #15 | ORL @ BOS 2026-11-16 | 2026-11-14T00:49:56Z | 7:00 PM | 71.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/orl-vs-bos-0022600245) |
| `data/picks/picks_2026-11-14_to_16.json` #16 | CHI @ CLE 2026-11-16 | 2026-11-14T00:49:56Z | 7:00 PM | 71.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/chi-vs-cle-0022600246) |
| `data/picks/picks_2026-11-14_to_16.json` #17 | MEM @ WAS 2026-11-16 | 2026-11-14T00:49:56Z | 7:00 PM | 71.1678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/mem-vs-was-0022600247) |
| `data/picks/picks_2026-11-14_to_16.json` #18 | PHI @ BKN 2026-11-16 | 2026-11-14T00:49:56Z | 7:30 PM | 71.6678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/phi-vs-bkn-0022600248) |
| `data/picks/picks_2026-11-14_to_16.json` #19 | HOU @ MIA 2026-11-16 | 2026-11-14T00:49:56Z | 7:30 PM | 71.6678 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/hou-vs-mia-0022600249) |
| `data/picks/picks_2026-11-14_to_16.json` #20 | POR @ MIN 2026-11-16 | 2026-11-14T00:49:56Z | 8:00 PM | 72.1678 | OUTSIDE_HORIZON | [NBA game page/schedule](https://www.nba.com/game/por-vs-min-0022600250) |
| `data/picks/picks_2026-11-14_to_16.json` #21 | GSW @ NOP 2026-11-16 | 2026-11-14T00:49:56Z | 8:00 PM | 72.1678 | OUTSIDE_HORIZON | [NBA game page/schedule](https://www.nba.com/game/gsw-vs-nop-0022600251) |
| `data/picks/picks_2026-11-14_to_16.json` #22 | PHX @ DEN 2026-11-16 | 2026-11-14T00:49:56Z | 9:00 PM | 73.1678 | OUTSIDE_HORIZON | [NBA game page/schedule](https://www.nba.com/game/phx-vs-den-0022600252) |
| `data/picks/props_2026-11-14_to_16.json` #1 | LAL @ PHX 2026-11-15 | 2026-11-13T22:43:35Z | 4:00 PM | 46.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/lal-vs-phx-0022600237) |
| `data/picks/props_2026-11-14_to_16.json` #2 | LAL @ PHX 2026-11-15 | 2026-11-13T22:43:35Z | 4:00 PM | 46.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/lal-vs-phx-0022600237) |
| `data/picks/props_2026-11-14_to_16.json` #3 | DAL @ BOS 2026-11-15 | 2026-11-13T22:43:35Z | 6:00 PM | 48.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/dal-vs-bos-0022600240) |
| `data/picks/props_2026-11-14_to_16.json` #4 | DEN @ NOP 2026-11-14 | 2026-11-13T22:43:35Z | 7:00 PM | 25.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/den-vs-nop-0022600231) |
| `data/picks/props_2026-11-14_to_16.json` #5 | DET @ MIA 2026-11-14 | 2026-11-13T22:43:35Z | 8:00 PM | 26.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/det-vs-mia-0022600233) |
| `data/picks/props_2026-11-14_to_16.json` #6 | DET @ MIA 2026-11-14 | 2026-11-13T22:43:35Z | 8:00 PM | 26.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/det-vs-mia-0022600233) |
| `data/picks/props_2026-11-14_to_16.json` #7 | HOU @ WAS 2026-11-15 | 2026-11-13T22:43:35Z | 7:00 PM | 49.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/hou-vs-was-0022600242) |
| `data/picks/props_2026-11-14_to_16.json` #8 | DAL @ BOS 2026-11-15 | 2026-11-13T22:43:35Z | 6:00 PM | 48.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/dal-vs-bos-0022600240) |
| `data/picks/props_2026-11-14_to_16.json` #9 | SAS @ UTA 2026-11-15 | 2026-11-13T22:43:35Z | 5:00 PM | 47.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/sas-vs-uta-0022600239) |
| `data/picks/props_2026-11-14_to_16.json` #10 | IND @ PHI 2026-11-15 | 2026-11-13T22:43:35Z | 1:00 PM | 43.2736 | WITHIN_HORIZON | [NBA game page/schedule](https://www.nba.com/game/ind-vs-phi-0022600236) |

## Verification boundary and reproducibility

- This audit reads checked-in files only. It does not fetch external sources and cannot prove that a source link is live, that a stored value matches the current official page, that data use is licensed, or that a strategy has skill-based predictive value.
- `python3 tools/release_audit.py --write-report` regenerates this report and `audit/table-source-audit.csv` from the repository contents.
- `python3 -m unittest audit.test_release_audit` runs the parser, host-classification, time-zone, horizon-boundary, and workflow-marker regression tests.
- Official-source manual-review links: [Official NBA schedule](https://www.nba.com/schedule?date=2026-11-14); [Official NBA injury report index](https://official.nba.com/nba-injury-report-2026-27-season/); [Official NBA injury-report PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf); [NBA Stats glossary](https://www.nba.com/stats/help/glossary)
