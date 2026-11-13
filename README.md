# NBA Edge Lab

Research dashboard for NBA line-origination strategies: official schedule and injury data, candidate strategies, validation gates, questions, suggestions, and a **Flagged for Review** page.

**Live site:** https://wingbangboozle1-lang.github.io/NBA3/

## Current state (research only)

- No lines, picks, or correlation values are published. Blocking items are on the [Flagged for Review](site/flagged.html) page:
  - **F-01**: NBA Terms §9 bars using NBA Statistics for gambling (source: https://www.nba.com/termsofuse).
  - **F-02**: Dutch online sports-betting offers need a Koa licence under art. 31a of the Betting and Gaming Act (source: https://kansspelautoriteit.nl/online-kansspel-aanbieden).
  - **F-03**: no licensed odds data is in the repository.
- The 3-day slate (11/13–11/16/2026) comes from the official schedule PDF, which is labelled "subject to change".
- Injury rows come from the official 11/13/26 5:00 PM report. The report has no minutes field, so no minutes effect is estimated.

## Layout

| Path | Purpose |
|---|---|
| `data/*.json` | The only editable content: sources, schedule, injuries, flags, questions, suggestions, strategies, gates, repo review. |
| `scripts/build_site.py` | Validates every row and renders `site/`. Fails on a missing official source, an unflagged blank, or a broken link. |
| `site/` | Generated static site (GitHub Pages artifact). Do not edit by hand. |
| `.github/workflows/pages.yml` | Rebuilds, checks for drift between `site/` and `data/`, and deploys. |
| `COORDINATION.md` | Shared task board, claims, verification log, and PR/deploy status. |

## Rebuild

```bash
python3 scripts/build_site.py          # validate + render site/ + check links
python3 scripts/build_site.py --check  # validate + links only (no files written)
```

Standard library only (Python 3.11+). No network access is needed to build.

## Verification rules

1. Every data row carries an official `https` source (NBA, Ksa, or GitHub for repository facts), or it is flagged as unverified and left blank.
2. Source ids (`S01`…) must exist in `data/sources.json`.
3. Injury rows are attributed R (printed), S (team printed, matchup via official schedule pairing), U (not extracted, left blank), or T (team status row). Non-R rows carry a flag.
4. External links are not fetched during the build (scheduled link checking is proposed as SG-07).

## Sources

See [Sources](site/sources.html). Official pages used: NBA.com stats glossary, NBA Official injury report index (2026-27), the 11/13/26 injury PDF, the 2026-27 schedule PDF, NBA.com Terms of Use, and Kansspelautoriteit pages.
