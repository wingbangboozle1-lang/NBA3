# Coordination board

Session: `arena/49064d5a-nba3` (current Arena-owned branch; branch names are fixed by the workspace).

| Task | Status | Owner | File scope |
|---|---|---|---|
| Baseline repository review and coordination setup | done | arena/49064d5a-nba3 | COORDINATION.md |
| Official-source NBA strategy research and verification | done (framework; no model claims) | arena/49064d5a-nba3 | index.html, README.md |
| Dashboard / GitHub Pages site and validation workflow | done (deployment pending repository settings) | arena/49064d5a-nba3 | index.html, README.md, .github/workflows/pages.yml |

## Handoff and environment notes

This checkout contained only a six-byte README and no app, data, package configuration, or preexisting coordination board. No other session claims were present when this board was created. The workspace is bound to branch `arena/49064d5a-nba3`; it cannot be switched to a separately named session/integration branch here. This session was therefore responsible for both analysis and integration on the assigned branch. The board claim was committed and pushed immediately before work began. No concurrent edits were observed.

## Verification log

- Initial inventory: `git status --short --branch`, root directory listing, and README/coordination check. No existing product or analysis material to validate.
- Sources checked: [NBA Stats glossary](https://www.nba.com/stats/help/glossary) for official statistical terminology; [NBA Official injury report index](https://official.nba.com/nba-injury-report-2025-26-season/) for injury-report entry point; [example timestamped NBA injury PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-11_05_00PM.pdf) to inspect report fields and dated status nature. No player-level availability or projections were copied into current recommendations.
- Every claim about absent local data was grounded in repository inventory. No odds, projections, correlations, model results, ROI, or picks have been invented. Strategy rows are explicitly proposed experiments, not verified performance facts. Official sources establish terminology/report provenance only, not predictive value or data licensing.
- Site validation: Python HTMLParser checked 8 section IDs and 14 links; no broken in-page anchors. `git diff --check` passed. GitHub Pages workflow includes the same fragment validation and static upload/deploy job; actual deployment still requires repository Pages/actions settings and a merge to `main`.
- Irregularities flagged on site: missing authorized historical/statistical, schedule, odds/props, rotation, and settlement data; licensing, jurisdiction, and bankroll/risk policy are unknown; no measured correlation or validation evidence. These prevent live picks and strategy eligibility but do not block publishing this research dashboard.

## Deployment / PR status

- PR [#1](https://github.com/wingbangboozle1-lang/NBA3/pull/1) was merged to `main` with merge commit `ce3273eded5dc8083e0523d44666b92d7bee8f9e` on 2026-11-13.
- GitHub Actions run [43519089153](https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43519089153) completed successfully: both static validation/build and Pages deployment jobs passed. A separate Pages deployment run also showed success. Deployment confirmed by workflow; site URL is the repository GitHub Pages URL (repository custom Pages URL is not inferred here).
- Workflow emitted non-fatal platform notices: Node.js 20 action runtime deprecation and forthcoming `ubuntu-latest` image migration. No check failed.

---

## Session arena/7c532e8c-nba3 (current) — claims

Session ID: `arena/7c532e8c-nba3`. Branch naming: the workspace fixes the branch to `arena/7c532e8c-nba3`; the `session-<id>/<task>` naming in the brief cannot be used here (Arena policy: work only on the assigned branch). Non-overlapping file scopes are kept per task inside this one branch. The prior session's board above is preserved as history; this session extends (does not overwrite) its published site.

| Task | Status | Owner | File scope |
|---|---|---|---|
| T1 Repo review & irregularities | done (needs owner review of flags) | arena/7c532e8c-nba3 | data/flags.json, data/repo_review.json |
| T2 Official source register & link verification | done | arena/7c532e8c-nba3 | data/sources.json |
| T3 Official 3-day slate (11/13–11/16/2026) | done (subject to change; re-pull at query time) | arena/7c532e8c-nba3 | data/schedule.json |
| T4 Official injury report transcription (11/13/26 5:00 PM) | done (117 rows; 18 unattributed left blank) | arena/7c532e8c-nba3 | data/injuries.json |
| T5 Strategy candidates, validation gates, correlation | done as framework (all blocked; no values) | arena/7c532e8c-nba3 | data/strategies.json, data/validation_gates.json |
| T6 Questions & suggestions queue | done (awaiting owner decisions) | arena/7c532e8c-nba3 | data/questions.json, data/suggestions.json |
| T7 Site build (landing + category subpages) | done (scripts/build_site.py; site/ generated) | arena/7c532e8c-nba3 | scripts/build_site.py, site/, README.md, .github/workflows/pages.yml; root index.html removed (superseded) |
| T8 Integration: build, link check, PR, merge, Pages verification | in progress (final) | arena/7c532e8c-nba3 | COORDINATION.md, PR |

Claimed at: 2026-11-13 (UTC). No other session claims were present on `origin/main` at claim time (`dbb8575`).

### Sources used (this session)

Official sources, all checked on 2026-11-13 (see the live Sources page for limits):
- [NBA.com stats glossary](https://www.nba.com/stats/help/glossary): first chunk of 10 read.
- [NBA Official injury report, 2026-27 index](https://official.nba.com/nba-injury-report-2026-27-season/): reporting deadlines read.
- [Injury report PDF, 11/13/26 05:00 PM](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf): both chunks read; 117 rows transcribed.
- [2026-27 schedule by date (PDF)](https://cdn.nba.com/manage/2026/08/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf): 'as of Aug 13, 2026, subject to change'; 31 games for 11/13–11/16 read.
- [NBA schedule release page](https://www.nba.com/news/2026-27-schedule-team-by-team-index): PDF links and release context.
- [NBA.com Terms of Use](https://www.nba.com/termsofuse): §1 and §8–§11 read (3 of 10 chunks).
- [Kansspelautoriteit homepage](https://kansspelautoriteit.nl/) and [online kansspel aanbieden](https://kansspelautoriteit.nl/online-kansspel-aanbieden): art. 31a Koa licence requirement read (Dutch).
- Prior version checked: [2025-26 injury index](https://official.nba.com/nba-injury-report-2025-26-season/) still resolves but is superseded.

Failed or not used: [NBA CDN live scoreboard JSON](https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json) returned HTTP 500 (not used). The NBA schedule news article appeared only as a search snippet (not used as evidence).

### Verification performed

- Injury rows: transcribed from the PDF text; each row carries its report link. Attribution codes R/S/U/T are kept on each row (table on the Injury tracker page). Team-level 'NOT YET SUBMITTED' rows are marked T.
- Game-flow counts: recomputed independently from the injury rows (R/S/T attribution, matched on date and team). Results matched the recount for all 21 teams with rows on 11/13–11/14.
- Schedule: 31 games (11/13: 9; 11/14: 5; 11/15: 9; 11/16: 8) transcribed from the PDF. Home/away confirmed only where the injury report labels the matchup (11/13 and 11/14). Other dates keep the printed order (F-10).
- Build: `python3 scripts/build_site.py` validated 117 injury rows, 31 games and 11 sources, and checked 553 links across 12 pages (0 broken). The build fails if a row has no official link and no flag.
- Repository review: origin/main read (dbb8575); the repo has no LICENSE file, no data, and no model code at baseline.

### Irregularities and flags (see the Flagged for Review page)

- **Blockers:** F-01 (NBA Terms §9 bars gambling use of NBA statistics), F-02 (Dutch Koa licence requirement for online sports-betting offers), F-03 (no licensed odds data, so no lines or picks).
- **Irregularities:** F-07 (prior dashboard linked the 2025-26 injury index; current season is 2026-27), F-08 (18 injury rows without team/matchup text; 19 schedule-linked), F-09 (schedule 'subject to change'), F-11 (schedule marker legend unknown), F-12 (CDN scoreboard JSON HTTP 500), F-14 (branch naming in the brief conflicts with Arena branch policy), F-15 (two Pages deploy mechanisms; now a single workflow deploy), F-17 ('NOT YET SUBMITTED' team rows).
- No picks, lines, correlation values, ROI, or minutes effects were published. Nothing was inferred to fill a blank.

### Coordination notes

- Only this session worked on the branch. Other sessions' claims were not present on `origin/main` at claim time.
- The prior session's board and published site (PR #1, #2) are preserved as history; this session replaces the single-page dashboard with the generated multi-page site.
- Post-merge: GitHub Pages must use the workflow build (site/). The Pages build_type is switched from legacy to workflow in T8.

## Integration / PR status (T8)

- Branch: `arena/7c532e8c-nba3`. Pull request and merge: recorded in the PR section below once executed.
