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
| `arena-0a016df8` | `arena/0a016df8-nba3` | active (round 2: data → model → picks → site → integration) | 2026-11-13 |

> Platform note: sessions are pinned by their platform to one assigned branch (branch
> creation/switching is not permitted). Assigned branches play the role of
> `session-<id>/<task>` branches; per-task file scopes are listed in the board.

## Task board
| ID | Task | Status | Owner | Files (scope) | Notes |
|---|---|---|---|---|---|
| R1 | Baseline repository review and coordination setup | done | arena/49064d5a-nba3 | `COORDINATION.md` | Round 1; see completed-task records |
| R2 | Official-source strategy research framework dashboard | done | arena/49064d5a-nba3 | `index.html`, `README.md` | Hypotheses only, no fabricated data; preserved at `research-dashboard.html` |
| R3 | Dashboard / GitHub Pages site and validation workflow | done | arena/49064d5a-nba3 | `index.html`, `README.md`, `.github/workflows/pages.yml` | Deployed via PR #1/#2; see records |
| T1 | Repo scaffolding & coordination board round 2 (merged both boards) | done | arena-0a016df8 | `README.md`, `COORDINATION.md`, `.gitignore` | Merged R1–R3 records with round-2 board |
| T2 | Data collection: schedule/results, injuries, standings (2026-27 + 2025-26 base) | done | arena-0a016df8 | `data/**` | 174 games, 30/30 reconciled; official injury PDF encoded; see records |
| T3 | Methodology, line origination model, validation gates, correlation analysis | done | arena-0a016df8 | `pipeline/**`, `docs/methodology.md`, `data/model/**` | Walk-forward, slate-safe; see records |
| T4 | Picks generation for every slate ≤3 days ahead (singles, parlays, prop combos) | done | arena-0a016df8 | `data/picks/**` | 22 games + 1 research-only parlay + 30 prop markets; gate-enforced |
| T5 | Injury/rotation-minutes impact & game-flow analysis | done | arena-0a016df8 | `docs/injuries_gameflow.md`, `data/injuries/**` | Numeric impact NOT invented (no player data) — flagged |
| T6 | Executive summary, open questions, improvement suggestions | done | arena-0a016df8 | `docs/executive_summary.md`, `docs/open_questions.md`, `docs/suggestions.md` | 10 open questions; suggestion review queue |
| T7 | Site build: subpages for all tables/analysis (clean dashboard) | done | arena-0a016df8 | `site/**` | 12 subpages; per-row source links |
| T8 | Line-by-line verification pass + Flagged-for-Review dataset | done | arena-0a016df8 | `docs/verification_log.md`, `data/verification_flags.json` | 6 irregularities found & documented; blanks left blank |
| T9 | Integration: re-verify combined data, link check, PR to main, merge, Pages publish | done | arena-0a016df8 | root `index.html`, `.github/workflows/pages.yml`, PR | Round-1 dashboard preserved at `research-dashboard.html`; link check green |

## Cross-session requests
- **arena-0a016df8 → arena/49064d5a-nba3 (T9 integration):** root `index.html` (owned by R2/R3,
  session completed) was replaced by a landing-page dashboard as the **final integration step**;
  the R2 dashboard content was preserved verbatim as `research-dashboard.html` and linked from
  the new index. No R2 content was discarded. The workflow gained one extra validation step
  (`pipeline/check_site.py`) while the original R3 validation step was kept unchanged.

## Handoff / incident log
- 2026-11-13 — **Add/add merge conflict** between `arena/49064d5a-nba3` (merged to main first)
  and `arena-0a016df8` on `COORDINATION.md` and `README.md`. Resolved by `arena-0a016df8` by
  merging both boards and both READMEs into single combined documents; no work from either
  session was discarded. Both sessions had created a board independently before either was pushed.
- 2026-11-13 — **Data-integrity catch (T2/T8):** a game row (Nov 6 TOR@MIL) lost its score cells
  to a page-fetch boundary; an inferred value was flagged, then re-verified against the daily
  boxscores page (TOR 121 @ MIL 107). Logged in `docs/verification_log.md`.
- 2026-11-13 — **Pipeline bugs fixed before publication:** OT-vs-note conflation; ROI accounting
  error (double-counted winning stakes); same-day Elo leakage. All documented with audit trail in
  git history and on the site's Flagged for Review page.

## Completed-task records

### R1 — Baseline repository review and coordination setup (arena/49064d5a-nba3)
- Sources: [NBA Stats glossary](https://www.nba.com/stats/help/glossary); [NBA Official injury report index](https://official.nba.com/nba-injury-report-2025-26-season/); [example timestamped NBA injury PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-11_05_00PM.pdf).
- Verification: repo inventory check; no model claims made.
- Irregularities: initial repo contained only a six-byte README; no data feeds, licensing, or
  jurisdiction information present.

### R2/R3 — Research framework dashboard + Pages deployment (arena/49064d5a-nba3)
- Sources: NBA.com/Stats glossary; official.nba.com injury report index (links embedded in the dashboard).
- Verification: Python HTMLParser checked 8 section IDs and 14 links; no broken in-page anchors;
  `git diff --check` passed; CI validates the same on every deploy.
- Deployment: PR [#1](https://github.com/wingbangboozle1-lang/NBA3/pull/1) merged (commit `ce3273e`);
  PR [#2](https://github.com/wingbangboozle1-lang/NBA3/pull/2) merged (commit `dbb8575`); GitHub Actions
  run [43519089153](https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43519089153) completed
  successfully (static validation + Pages deploy).
- Irregularities flagged (resolved or carried by round 2): missing data feeds → addressed in T2
  (public sources); licensing/jurisdiction unknown → carried as Open Questions Q1/Q7.

### T1 — Repo scaffolding & coordination board round 2 (arena-0a016df8)
- Sources: n/a (repo-internal).
- Verification: n/a (no external claims).
- Irregularities: add/add conflict with the R1 board resolved as logged above.

### T2 — Data collection (arena-0a016df8)
- Sources: [BBR October 2026-27 schedule](https://www.basketball-reference.com/leagues/NBA_2027_games-october.html) ·
  [BBR November](https://www.basketball-reference.com/leagues/NBA_2027_games-november.html) ·
  [BBR ratings 2026-27](https://www.basketball-reference.com/leagues/NBA_2027_ratings.html) ·
  [BBR ratings 2025-26](https://www.basketball-reference.com/leagues/NBA_2026_ratings.html) ·
  [official injury report PDF 11/13/26 5PM ET](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf) ·
  [BBR per-game stats](https://www.basketball-reference.com/leagues/NBA_2027_per_game.html).
- Verification: 174 game rows transcribed; per-team records reconcile 30/30 vs the independent
  ratings table; Nov 6 slate fully re-verified from daily boxscores; injury report transcribed
  from the official PDF; abbreviation drift (BKN/BRK) normalized with a note.
- Irregularities: corrupted fetch row re-verified (see incident log); market odds/CLV not
  collectible (no feed) — left blank and flagged.

### T3 — Model, gates, correlations (arena-0a016df8)
- Sources: data from T2; Elo/MOV methodology is public FiveThirtyEight-style practice (documented in `docs/methodology.md`).
- Verification: walk-forward (burn-in 30, n=138), Brier 0.2001; permutation tests (2,000 shuffles);
  slate-safe updates (no same-day leakage); naive-favorite baseline computed for lift comparison.
- Irregularities: ROI accounting bug and same-day leakage found and fixed pre-publication;
  STRAT3 (totals) and STRAT4 (parlays) FAIL gates and are published as not eligible.

### T4 — Picks (arena-0a016df8)
- Sources: outputs of T2/T3; strategy eligibility enforced from `data/model/validation_report.json`.
- Verification: 22 games covered (Nov 14–16; Nov 13 in flight), availability flags from the
  official report; picks with availability risk are held; parlay combo labeled research-only
  (STRAT4 failed gates); props labeled unvalidated prototype.
- Irregularities: injury reports for 11/15–16 unpublished at generation time — picks flagged pending.

### T5 — Injuries & game flow (arena-0a016df8)
- Sources: official injury report PDF (above); game-flow metrics computed from the verified log.
- Verification: quarter-flow sample (Nov 6) taken from boxscores pages; OT rate corrected to
  5.2% after fixing the OT/note conflation; B2B split reported with sample-size caveat.
- Irregularities: numeric injury impact deliberately NOT produced (no player-level data) — flagged.

### T6 — Exec summary, open questions, suggestions (arena-0a016df8)
- Sources: all of the above.
- Verification: cross-checked numbers against `data/model/validation_report.json`.
- Irregularities: none new; 10 open questions recorded with discovery paths.

### T7/T8 — Site build + verification pass (arena-0a016df8)
- Sources: every table row links its source (site/data.html, site/injuries.html, site/verification.html).
- Verification: `pipeline/check_site.py` — 13 pages, 10 data files, all internal links resolve,
  all JSON parses; live-served smoke test of key URLs (HTTP 200) before PR.
- Irregularities: relative-link bug between `site/` and root pages found by the checker and fixed.

### T9 — Integration & publication (arena-0a016df8)
- Sources: see all above.
- Verification: link check green; round-1 dashboard preserved verbatim at `research-dashboard.html`;
  PR to main merged (see PR link in the board update below); Pages deployment confirmed via Actions.
- Irregularities: none at merge time; flagged items published on the site's Flagged for Review page.
