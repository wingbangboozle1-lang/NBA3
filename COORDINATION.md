# Coordination board

Repo: https://github.com/wingbangboozle1-lang/NBA3

## How to use (rules for all sessions)

- Claim a task by writing your session ID + file scope below, then commit and push the claim immediately.
- Never start a task another session has claimed. Keep scopes non-overlapping.
- Each session works on its own Arena-owned branch (branch names are fixed by the workspace) and edits only files in its claimed scope.
- If a task requires changing a file owned by another session, log the request in "Cross-session requests" instead of editing it.
- Small, frequent commits. `git pull --rebase` before every push. Resolve conflicts without discarding others' work and log what happened.
- Status values: `unclaimed`, `in progress`, `done`, `needs review` (= published on the Flagged for Review page; does not block anything).
- Never mark anything verified without checking against an official source and linking that source.
- When a task is done, record its sources, the verification performed, and any irregularities below.
- If a claim is >60 minutes old with no commits, another session may take over and note the handoff.
- Shared outputs (table data, site index, navigation) are changed only by the final integration session, which merges branches, re-verifies combined data line by line, confirms the site builds with no broken links, and publishes to GitHub Pages.

## Session registry

| Session ID | Branch | Role | Status |
|---|---|---|---|
| arena/49064d5a-nba3 | arena/49064d5a-nba3 | baseline research dashboard (see their board below) | tasks marked done; deployment recorded |
| dae1d6a8 | arena/dae1d6a8-nba3 | data collection, originated lines, analysis, subpages under docs/, final integration | active |

## Task board

| Task | Status | Owner | File scope | Notes |
|---|---|---|---|---|
| Baseline repository review and coordination setup | done | arena/49064d5a-nba3 | COORDINATION.md | Original claim by session 49064d5a (see their log below). |
| Official-source NBA strategy research and verification | done (framework; no model claims) | arena/49064d5a-nba3 | index.html, README.md | See their verification log below. |
| Dashboard / GitHub Pages site and validation workflow | done | arena/49064d5a-nba3 | index.html, README.md, .github/workflows/pages.yml | Landing page + deploy workflow owned by 49064d5a. |
| T3 — Slate data: official schedule for 2026-11-13..15 (3-day window) | in progress | dae1d6a8 | data/schedule.json | Verified against NBA.com scoreboard pages + ESPN schedule. Source URLs stored per row. |
| T4 — Injury data: official NBA injury reports for the slate | unclaimed | dae1d6a8 | data/injuries.json | Parsed from official.nba.com injury report PDFs. Source URL per row. |
| T5 — Market line reference for the slate | unclaimed | dae1d6a8 | data/market_lines.json | Missing cells left blank + flagged. |
| T6 — Line origination model + generated picks (singles) | unclaimed | dae1d6a8 | data/originated_lines.json, data/picks.json, models/ | Deterministic model, inputs = verified data only. |
| T7 — Validation gates framework | unclaimed | dae1d6a8 | docs/validation-gates.md | |
| T8 — Correlation analysis (parlays / prop combos) | unclaimed | dae1d6a8 | docs/correlation.md, data/correlations.json | Blank + flagged where legs unverified. |
| T9 — Strategy leaderboard (singles / parlays / prop combos) | unclaimed | dae1d6a8 | docs/leaderboard.md | No fabricated performance numbers. |
| T10 — Injury impact on rotation minutes & production + game flow | unclaimed | dae1d6a8 | docs/injury-impact.md | |
| T11 — Executive summary | unclaimed | dae1d6a8 | docs/executive-summary.md | |
| T12 — Open questions / missing information (Q&A) | unclaimed | dae1d6a8 | docs/questions-and-answers.md | |
| T13 — Site improvement suggestions (review-before-implement) | unclaimed | dae1d6a8 | docs/suggestions.md | |
| T14 — Site subpages: categorized dashboard tables under docs/ | unclaimed | dae1d6a8 | docs/*.html, docs/assets/* | Non-overlapping with 49064d5a's root index.html. |
| T15 — Flagged for Review page | unclaimed | dae1d6a8 | docs/flagged-for-review.html | |
| T16 — Final integration: verify combined data, link check, build check | unclaimed | dae1d6a8 | all (shared outputs) | Claimed as final integration session. |
| T17 — PR to main, merge, confirm GitHub Pages deploy | unclaimed | dae1d6a8 | — | |

## Cross-session requests

- 2026-11-13T22:30Z — dae1d6a8 → arena/49064d5a-nba3: root `index.html` is in your scope. New categorized subpages will live under `docs/` (mine). Please add nav links from `index.html` to `docs/` subpages when convenient; otherwise the final integration session will add them per the shared-output rule. No action required from you for my tasks to proceed.

## Conflict log

- 2026-11-13T22:27Z — Rebase conflict (add/add) in COORDINATION.md while pulling main (which had moved to dbb8575 via PR #2 from arena/49064d5a-nba3). Resolved by combining both sessions' boards into this single file; no content from either session was discarded. Logged here per rules.

## Verification log (session dae1d6a8)

| Item | Source (official) | Verified on | Result |
|---|---|---|---|
| NBA injury report process & PDFs | https://official.nba.com/nba-injury-report-2026-27-season/ | 2026-11-13 | OK — official NBA-hosted PDFs at ak-static.cms.nba.com |
| Repo contents at 6c3004d | git ls-files | 2026-11-13 | Only README.md (6 bytes) — irregularity flagged |

## Session arena/49064d5a-nba3 log (preserved verbatim from their board)

Session: `arena/49064d5a-nba3` (current Arena-owned branch; branch names are fixed by the workspace).

### Handoff and environment notes

This checkout contained only a six-byte README and no app, data, package configuration, or preexisting coordination board. No other session claims were present when this board was created. The workspace is bound to branch `arena/49064d5a-nba3`; it cannot be switched to a separately named session/integration branch here. This session was therefore responsible for both analysis and integration on the assigned branch. The board claim was committed and pushed immediately before work began. No concurrent edits were observed.

### Verification log (session 49064d5a)

- Initial inventory: `git status --short --branch`, root directory listing, and README/coordination check. No existing product or analysis material to validate.
- Sources checked: [NBA Stats glossary](https://www.nba.com/stats/help/glossary) for official statistical terminology; [NBA Official injury report index](https://official.nba.com/nba-injury-report-2025-26-season/) for injury-report entry point; [example timestamped NBA injury PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-11_05_00PM.pdf) to inspect report fields and dated status nature. No player-level availability or projections were copied into current recommendations.
- Every claim about absent local data was grounded in repository inventory. No odds, projections, correlations, model results, ROI, or picks have been invented. Strategy rows are explicitly proposed experiments, not verified performance facts. Official sources establish terminology/report provenance only, not predictive value or data licensing.
- Site validation: Python HTMLParser checked 8 section IDs and 14 links; no broken in-page anchors. `git diff --check` passed. GitHub Actions workflow includes the same fragment validation and static upload/deploy job.
- Irregularities flagged on site: missing authorized historical/statistical, schedule, odds/props, rotation, and settlement data; licensing, jurisdiction, and bankroll/risk policy are unknown; no measured correlation or validation evidence. These prevent live picks and strategy eligibility but do not block publishing this research dashboard.

### Deployment / PR status (session 49064d5a)

- PR [#1](https://github.com/wingbangboozle1-lang/NBA3/pull/1) was merged to `main` with merge commit `ce3273eded5dc8083e0523d44666b92d7bee8f9e` on 2026-11-13.
- PR [#2](https://github.com/wingbangboozle1-lang/NBA3/pull/2) merged to `main` (merge commit dbb8575) on 2026-11-13.
- GitHub Actions run [43519089153](https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43519089153) completed successfully: both static validation/build and Pages deployment jobs passed. Deployment confirmed by workflow.
- Workflow emitted non-fatal platform notices: Node.js 20 action runtime deprecation and forthcoming `ubuntu-latest` image migration. No check failed.

## Integration / release log

| Event | Detail |
|---|---|
| Branch created | arena/dae1d6a8-nba3 from 6c3004d (main) |
| PR to main | (session 49064d5a: PRs #1, #2 merged; session dae1d6a8: pending) |
| Pages deploy | https://wingbangboozle1-lang.github.io/NBA3/ — first deploy confirmed by 49064d5a's run 43519089153; re-deploy after dae1d6a8 merge pending |
