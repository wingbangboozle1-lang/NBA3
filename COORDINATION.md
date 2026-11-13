# COORDINATION.md — Shared Task Board

This is the shared task board for all agent sessions working on this repository.
Read this file before starting any work. Claim tasks by editing this file, then
commit and push the claim immediately. Never start a task another session has
claimed. Keep file scopes non-overlapping.

## Session registry

| Session ID | Branch | Role | Status |
|---|---|---|---|
| d01ae7e2 | `arena/d01ae7e2-nba3` | Primary dev + final integration session | active |

> Note: This repository is being worked on from an Arena session bound to branch
> `arena/d01ae7e2-nba3` (branched from `main` @ `6c3004d`). The Arena session
> cannot switch branches, so all work for this session happens on that branch.
> Any additional sessions must use their own `session-<id>/<task>` branches as
> described in the project brief.

## Task board

Status values: `unclaimed` | `in progress` | `done` | `needs review`
(`needs review` = item is published on the Flagged for Review page; it does not block anything.)

| ID | Task | Status | Owner | Files touched |
|---|---|---|---|---|
| T01 | Repo review, line-by-line README/structure audit, flag irregularities | in progress | d01ae7e2 | `README.md`, `docs/REPO_REVIEW.md` |
| T02 | Create COORDINATION.md task board (this file) and claim all tasks | done | d01ae7e2 | `COORDINATION.md` |
| T03 | Research: official NBA sources (rules, injuries, schedule, stats) with verified links | in progress | d01ae7e2 | `data/sources.json`, `docs/RESEARCH_LOG.md` |
| T04 | Strategy design: single bet, parlays, player-prop combos + validation gates + correlation methodology | unclaimed | — | `docs/STRATEGIES.md`, `data/strategies.json` |
| T05 | Data: upcoming slate (≤3 days), official injury reports, game-flow inputs — every row source-linked | unclaimed | — | `data/slate.json`, `data/injuries.json`, `data/games.json` |
| T06 | Pick generation system design + leaderboard/rewards rules (no manual input) | unclaimed | — | `docs/PICKS_PIPELINE.md`, `data/picks.json` |
| T07 | Analysis: injury → rotation minutes → production impact; game flow analysis | unclaimed | — | `docs/INJURY_GAMEFLOW.md` |
| T08 | Executive summary | unclaimed | — | `docs/EXEC_SUMMARY.md` |
| T09 | Open questions / missing information register (Q&A before decisions) | unclaimed | — | `docs/QUESTIONS.md`, `data/questions.json` |
| T10 | Suggestions section (review queue for site improvements, choose path before implementing) | unclaimed | — | `docs/SUGGESTIONS.md`, `data/suggestions.json` |
| T11 | Flagged for Review page: unverified values + irregularities with source links | unclaimed | — | `data/flagged.json`, `docs/FLAGGED.md` |
| T12 | Site: GitHub Pages — landing page + category subpages, dashboard UI, tables | unclaimed | — | `docs/index.html`, `docs/*.html`, `docs/assets/*` |
| T13 | Verification pass: line-by-line, every table row has official source link; blanks for unconfirmed | unclaimed | — | all `data/*.json`, `docs/*.html` |
| T14 | Final integration: merge, re-verify combined data, link check, build check | unclaimed | — | all |
| T15 | GitHub Pages enable + deploy verification; PR to main, merge, record results here | unclaimed | — | `COORDINATION.md`, `.github/workflows/*` |

## Conflict log

| Date | Session | Event |
|---|---|---|
| 2026-11-13 | d01ae7e2 | Session start. Repo contained only `README.md` (6 bytes: `# NBA3`). Created this task board, claimed T01–T03. |

## Task completion log

| Task | Sources used | Verification performed | Irregularities |
|---|---|---|---|
| T02 | — | Board created and pushed | None |

## Integration session record

(To be filled by the final integration session: PR link, merge result, Pages deploy status.)
