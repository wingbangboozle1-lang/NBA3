# COORDINATION.md — Shared Task Board

## Session registry

| Session ID | Branch | Role | Status |
|---|---|---|---|
| d01ae7e2 | `arena/d01ae7e2-nba3` | Primary dev + final integration session | active |

## Task board

Status values: `unclaimed` | `in progress` | `done` | `needs review`
(`needs review` = item is published on the Flagged for Review page; it does not block anything.)

| ID | Task | Status | Owner | Files touched |
|---|---|---|---|---|
| T01 | Repo review, line-by-line README/structure audit, flag irregularities | done | d01ae7e2 | `README.md`, `docs/REPO_REVIEW.md`, `docs/repo-review.html` |
| T02 | Create COORDINATION.md task board (this file) and claim all tasks | done | d01ae7e2 | `COORDINATION.md` |
| T03 | Research: official NBA sources (rules, injuries, schedule, stats) with verified links | done | d01ae7e2 | `data/sources.json`, `docs/RESEARCH_LOG.md` |
| T04 | Strategy design: single bet, parlays, player-prop combos + validation gates + correlation methodology | done | d01ae7e2 | `docs/STRATEGIES.md`, `data/strategies.json`, `data/correlations.json` |
| T05 | Data: upcoming slate (≤3 days), official injury reports, game-flow inputs — every row source-linked | done | d01ae7e2 | `data/slate.json` (31 games), `data/injuries.json`, `data/teams.json`, `data/players.json` |
| T06 | Pick generation system design + leaderboard/rewards rules (no manual input) | done | d01ae7e2 | `docs/PICKS_PIPELINE.md`, `scripts/generate_picks.py`, `data/picks.json` |
| T07 | Analysis: injury → rotation minutes → production impact; game flow analysis | done | d01ae7e2 | `docs/INJURY_GAMEFLOW.md`, `docs/injury-impact.html`, `docs/game-flow.html` |
| T08 | Executive summary | done | d01ae7e2 | `docs/EXEC_SUMMARY.md` |
| T09 | Open questions / missing information register (Q&A before decisions) | done | d01ae7e2 | `docs/QUESTIONS.md`, `data/questions.json`, `docs/questions.html` |
| T10 | Suggestions section (review queue for site improvements, choose path before implementing) | done | d01ae7e2 | `docs/SUGGESTIONS.md`, suggestions inside `data/questions.json`, `docs/suggestions.html` |
| T11 | Flagged for Review page: unverified values + irregularities with source links | done | d01ae7e2 | `data/flagged.json`, `docs/FLAGGED.md`, `docs/flagged.html` |
| T12 | Site: GitHub Pages — landing page + category subpages, dashboard UI, tables | done | d01ae7e2 | `docs/index.html` + 11 subpages, `scripts/build_site.py` |
| T13 | Verification pass: line-by-line, every table row has official source link; blanks for unconfirmed | done | d01ae7e2 | `scripts/verify.py` (all `data/*.json`, `docs/*.html`) |
| T14 | Final integration: merge, re-verify combined data, link check, build check | done | d01ae7e2 | full re-run of generate → build → verify after merge |
| T15 | GitHub Pages enable + deploy verification; PR to main, merge, record results here | in progress | d01ae7e2 | `COORDINATION.md` (this record), Pages settings |

## Conflict log

| Date | Session | Event |
|---|---|---|
| 2026-11-13 | d01ae7e2 | Session start. Repo contained only `README.md` (6 bytes: `# NBA3`). Created this task board, claimed T01–T03. |
| 2026-11-13 | d01ae7e2 | No other sessions active in registry; claimed T04–T15 (all remaining tasks) to avoid duplicate work. Single-session integration flow: this session performs dev + final integration + PR. |
| 2026-11-13 | d01ae7e2 | Path correction (not a conflict): T04/T10 deliverables for suggestions live in `data/questions.json → suggestions` (single review register) rather than a separate `data/suggestions.json`. Board updated to reflect actual paths. |

## Task completion log

| Date | Session | Task | Outcome |
|---|---|---|---|
| 2026-11-13 | d01ae7e2 | T02 | Sources: none (process task). Verification: board created and pushed (commit `65b21b2`). Irregularities: none. |
| 2026-11-13 | d01ae7e2 | T01 | Repo audit complete: base commit = 6-byte README only; 2 repo irregularities + 15 data-source irregularities documented (fl-01…fl-16, hca-01, w-01); LICENSE/CI left as reviewer decisions (Q-07/Q-08). |
| 2026-11-13 | d01ae7e2 | T03 | 16 official sources fetched + 5 dead ends recorded; cross-verified slate (PDF ↔ live page ↔ preview slacks), records (3 surfaces), OPPG derivation (6 direct checks). |
| 2026-11-13 | d01ae7e2 | T04 | 4 strategies with 17 gates; correlations computed from official data (win%↔margin r=0.935 n=30; Brunson–Towns ρ=0.569 n=5); CLV gate BLOCKED (no odds source, Q-04). |
| 2026-11-13 | d01ae7e2 | T05 | 31 games (Nov 13–16 = today + 3d) fully source-linked; full 05:00 PM injury report transcribed (111 player rows); 30-team stats; blanks flagged (13 missing PPGs → fl-13). |
| 2026-11-13 | d01ae7e2 | T06 | `generate_picks.py` deterministic, no manual input: 7 released, 2 provisional statuses (22 rows), 2 passes, 1 parlay, 1 prop stack; 2 pre-settlement parameter revisions logged (rev-A/rev-B). |
| 2026-11-13 | d01ae7e2 | T07 | Production-at-risk per game with rotation gate; 5-team B2B cluster on 11/14; minutes modelling explicitly NOT done (no official MPG source — documented). |
| 2026-11-13 | d01ae7e2 | T08–T11 | Exec summary,12-question register (10 open), 8 suggestions (all awaiting review), 17 flagged items published. |
| 2026-11-13 | d01ae7e2 | T12–T13 | 12-page dashboard generated from JSON; `verify.py` passes clean: 395 URLs allowlisted, 0 failures, 0 warnings. |
| 2026-11-13 | d01ae7e2 | T14 | Full pipeline re-run (generate → build → verify) after all inputs unified: PASS. |

## Integration record (T15)

_Filled in after PR creation, merge and Pages deployment. See rows appended below._

## Verification instructions (for reviewers)

```bash
python3 scripts/generate_picks.py && python3 scripts/build_site.py && python3 scripts/verify.py
```
Expected: `All verification checks passed.` (exit 0). Every pick row carries 6 source links;
every HTML table row carries an inline official-source link; nulls require an adjacent flag.
