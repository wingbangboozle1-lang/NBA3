# COORDINATION — NBA3 shared task board

> Multi-session task board. Claim a task by writing your session ID + file scope below,
> commit and push the claim immediately, then work only inside your scope.
> Statuses: `unclaimed` · `in progress` · `needs review` · `done`
> `needs review` = published on the **Flagged for Review** page and does not block anything.

## Sessions

| Session ID | Branch | Started (UTC) | Focus | Status |
|---|---|---|---|---|
| `e22a2831` | `arena/e22a2831-nba3` | 2026-11-13 | Repo review + official data collection + model/strategies + site build + integration | in progress |

## Task board

| # | Task | Status | Owner | Files in scope | Notes / sources | Updated (UTC) |
|---|---|---|---|---|---|---|
| T1 | Create `COORDINATION.md` task board | done | `e22a2831` | `COORDINATION.md` | n/a — new repo scaffold | 2026-11-13 |
| T2 | Repo review, line by line, with source links | done | `e22a2831` | `docs/repo-review.md` | repo contained only `README.md` at `6c3004d` | 2026-11-13 |
| T3 | Collect official team data (records, ratings, pace, opp stats) | done | `e22a2831` | `data/raw/*.txt`, `data/processed/teams.json` | www.nba.com/stats | 2026-11-13 |
| T4 | Collect official game results 2026-27 season to date | done | `e22a2831` | `data/processed/games.csv` | www.nba.com/games?date=… | 2026-11-13 |
| T5 | Collect upcoming slates (D+0 … D+3) | done | `e22a2831` | `data/processed/schedule_upcoming.json` | www.nba.com/schedule | 2026-11-13 |
| T6 | Collect official NBA injury report | done | `e22a2831` | `data/raw/injury/*.txt`, `data/processed/injuries.json` | ak-static.cms.nba.com official PDF | 2026-11-13 |
| T7 | Collect official player data for prop markets | done | `e22a2831` | `data/processed/players.json` | www.nba.com/stats/players/… | 2026-11-13 |
| T8 | Build model that originates its own lines (spread/total/player props) | done | `e22a2831` | `model/*.py`, `data/processed/model_lines.json` | derived from T3–T7 | 2026-11-13 |
| T9 | Strategy research + validation gates + leaderboard | done | `e22a2831` | `docs/strategies.md`, `data/processed/strategies.json` | backtest on T4 | 2026-11-13 |
| T10 | Correlation analysis (empirical where possible, flagged where not) | done | `e22a2831` | `docs/correlations.md`, `data/processed/correlations.json` | derived from T4 | 2026-11-13 |
| T11 | Injury → rotation minutes / production impact + game flow analysis | done | `e22a2831` | `docs/injury-impact.md`, `docs/game-flow.md` | T6 + T7 | 2026-11-13 |
| T12 | Executive summary | done | `e22a2831` | `docs/executive-summary.md` | — | 2026-11-13 |
| T13 | Suggestions section (decision paths) | done | `e22a2831` | `docs/suggestions.md` | — | 2026-11-13 |
| T14 | Open questions / missing information register | done | `e22a2831` | `docs/open-questions.md` | — | 2026-11-13 |
| T15 | Static site build (landing + subpages, tables w/ source links) | done | `e22a2831` | `site/**` | — | 2026-11-13 |
| T16 | Flagged for Review page | done | `e22a2831` | `site/flagged.html` | — | 2026-11-13 |
| T17 | Final integration, link check, Pages deploy, PR + merge | done | `e22a2831` | `site/**`, `COORDINATION.md` | — | 2026-11-13 |

## Scope rules (from the operator brief)

- Each session works on its own branch and edits **only** files in its claimed scope.
- Shared outputs (`data/processed/*` table data, `site/index.html`, `site/partials/nav.html`) are
  changed only by the final integration session.
- To change a file owned by another session: log a request in the **Change requests** section below;
  do not edit it.
- `git pull --rebase` before every push. Small, frequent commits.
- Never mark anything verified without checking it against an official source, and link that source.
- If a claim is >60 min old with no commits, another session may take it over and note the handoff.

## Change requests (cross-session)

_None logged._

## Handoff log

| When (UTC) | From → To | Task | Note |
|---|---|---|---|
| — | — | — | — |

## Integration log

| When (UTC) | What | Result | Link |
|---|---|---|---|
|  |  |  |  |
