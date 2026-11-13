# COORDINATION.md — Shared Task Board

This file is the shared coordination board for all agent sessions working on this repository.
**Read it before starting work.** Claim a task by writing your session ID and file scope in the
board, then commit and push that claim immediately. Never start a task another session has claimed.

## Rules
- Each session works on its own branch/worktree (`session-<id>/<task>`) and edits only files in
  its claimed scope. Keep scopes non-overlapping.
- If a task requires changing a file owned by another session, log the request in
  **Cross-session requests** below instead of editing it.
- `git pull --rebase` before every push. Small, frequent commits.
- Statuses: `unclaimed` → `in progress` → `needs review` / `done`.
  - `needs review` = published on the site's **Flagged for Review** page; does not block anything.
- A claim older than 60 minutes with no new commits may be taken over by any other session; log
  the handoff in **Handoff / incident log**.
- Never mark anything verified without checking it against an official source, and link that source.
- On finishing a task: record its sources, the verification performed, and any irregularities in
  this file, then mark it `done`.
- Shared outputs (site index/navigation, merged table data) change only in the **final integration
  session**, once all other tasks are done.
- Merge conflicts: stop, resolve without discarding the other session's work, and log what happened.

## Session registry
| Session ID | Branch | Status | Last activity (UTC) |
|---|---|---|---|
| `arena/49064d5a-nba3` | `arena/49064d5a-nba3` | completed round 1 (merged via PR #1, #2) | 2026-11-13 |
| `arena-0a016df8` | `arena/0a016df8-nba3` | active | 2026-11-13 |

> Platform note: sessions are pinned by their platform to one assigned branch (branch
> creation/switching is not permitted). Assigned branches play the role of
> `session-<id>/<task>` branches; per-task file scopes are listed in the board.

## Task board
| ID | Task | Status | Owner | Files (scope) | Notes |
|---|---|---|---|---|---|
| R1 | Baseline repository review and coordination setup | done | arena/49064d5a-nba3 | `COORDINATION.md` | Round 1; see completed-task records |
| R2 | Official-source strategy research framework dashboard | done | arena/49064d5a-nba3 | `index.html`, `README.md` | Hypotheses only, no fabricated data; see records |
| R3 | Dashboard / GitHub Pages site and validation workflow | done | arena/49064d5a-nba3 | `index.html`, `README.md`, `.github/workflows/pages.yml` | Deployed via PR #1/#2; see records |
| T1 | Repo scaffolding & coordination board round 2 (merged both boards) | done | arena-0a016df8 | `README.md`, `COORDINATION.md`, `.gitignore` | Merged R1–R3 records with round-2 board |
| T2 | Data collection: schedule/results, injuries, standings (2026-27 + 2025-26 base) | in progress | arena-0a016df8 | `data/**` | Official sources only; unverified values left blank & flagged |
| T3 | Methodology, line origination model, validation gates, correlation analysis | in progress | arena-0a016df8 | `pipeline/**`, `docs/methodology.md`, `data/model/**` | Model outputs labeled as originated, not sourced facts |
| T4 | Picks generation for every slate ≤3 days ahead (singles, parlays, prop combos) | in progress | arena-0a016df8 | `data/picks/**` | Generated with T3 model from T2 data |
| T5 | Injury/rotation-minutes impact & game-flow analysis | in progress | arena-0a016df8 | `docs/injuries_gameflow.md`, `data/injuries/**` | NBA official injury report as source |
| T6 | Executive summary, open questions, improvement suggestions | in progress | arena-0a016df8 | `docs/executive_summary.md`, `docs/open_questions.md`, `docs/suggestions.md` | Open questions = info needed before decisions |
| T7 | Site build: subpages for all tables/analysis (clean dashboard) | in progress | arena-0a016df8 | `site/**` | Root `index.html` untouched until T9 integration |
| T8 | Line-by-line verification pass + Flagged-for-Review dataset | in progress | arena-0a016df8 | `docs/verification_log.md`, `data/verification_flags.json` | Every table row gets a source link; blanks = unverified |
| T9 | Integration: re-verify combined data, link check, PR to main, merge, Pages publish | unclaimed | — | shared outputs (root `index.html`, `data/picks/site-data.json`), PR | Gated on T2–T8 done; preserves R2 dashboard as a subpage |

## Cross-session requests
- **arena-0a016df8 → arena/49064d5a-nba3 (T9 integration):** root `index.html` (owned by R2/R3,
  session completed) will be replaced by a landing-page dashboard as the **final integration
  step**; the R2 dashboard content will be preserved verbatim as `research-dashboard.html` and
  linked from the new index. No R2 content is discarded. Logged per the shared-outputs rule.

## Handoff / incident log
- 2026-11-13 — **Add/add merge conflict** between `arena/49064d5a-nba3` (merged to main first)
  and `arena-0a016df8` on `COORDINATION.md` and `README.md`. Resolved by `arena-0a016df8` by
  merging both boards and both READMEs into single combined documents; no work from either
  session was discarded. Both sessions had created a board independently before either was pushed.

## Completed-task records

### R1 — Baseline repository review and coordination setup (arena/49064d5a-nba3)
- Sources: [NBA Stats glossary](https://www.nba.com/stats/help/glossary); [NBA Official injury report index](https://official.nba.com/nba-injury-report-2025-26-season/); [example timestamped NBA injury PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-11_05_00PM.pdf).
- Verification: repo inventory check; no model claims made.
- Irregularities: initial repo contained only a six-byte README; no data feeds, licensing, or
  jurisdiction information present.

### R2/R3 — Research framework dashboard + Pages deployment (arena/49064d5a-nba3)
- Sources: NBA.com/Stats glossary; official.nba.com injury report index (links embedded in `index.html`).
- Verification: Python HTMLParser checked 8 section IDs and 14 links; no broken in-page anchors;
  `git diff --check` passed; CI validates the same on every deploy.
- Deployment: PR [#1](https://github.com/wingbangboozle1-lang/NBA3/pull/1) merged (commit `ce3273e`);
  PR [#2](https://github.com/wingbangboozle1-lang/NBA3/pull/2) merged (commit `dbb8575`); GitHub Actions
  run [43519089153](https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43519089153) completed
  successfully (static validation + Pages deploy).
- Irregularities flagged (still open, carried into T8): missing licensed historical/statistical,
  schedule, odds/props, rotation, and settlement data feeds; licensing, jurisdiction, and
  bankroll/risk policy unknown; no measured correlation or validation evidence at that time.

### T1 — Repo scaffolding & coordination board round 2 (arena-0a016df8)
- Sources: n/a (repo-internal).
- Verification: n/a (no external claims).
- Irregularities: repo contained only `README.md` with the literal text `# NBA3` at branch time;
  add/add conflict with R1 board resolved as logged above.
