# NBA3 — NBA Line-Origination & Betting-Strategy Research

Research project: **originate NBA lines, generate picks automatically for every slate up to 3 days ahead, validate strategies with gates that separate skill from luck** — built exclusively on **official NBA sources**, with every table row linked to the source it came from and every unconfirmable value left **blank + flagged** (never inferred).

> Research & paper-trading only. Not betting advice.

## Quick start

```bash
python3 scripts/generate_picks.py   # derive lines, picks, correlations from data/*.json
python3 scripts/build_site.py       # render the GitHub Pages dashboard into docs/
python3 scripts/verify.py           # offline verification (exit 0 = pass)
```

## What's inside

| Path | What it is |
|---|---|
| `COORDINATION.md` | Multi-session task board (T01–T15), claims, conflicts, integration record |
| `data/` | Verified inputs + generated outputs: slate (31 games, Nov 13–16), injuries (official 05:00 PM report), teams (all 30), players, strategies + gates, picks, correlations, flagged, questions/suggestions, sources registry |
| `docs/` | **GitHub Pages site** (dashboard): slate & picks, strategies & gates, leaderboard, injury impact, game flow, analysis, repo review, flagged, questions, suggestions, sources — plus the long-form research write-ups (`REPO_REVIEW.md`, `RESEARCH_LOG.md`, `STRATEGIES.md`, `PICKS_PIPELINE.md`, `INJURY_GAMEFLOW.md`, `EXEC_SUMMARY.md`, `QUESTIONS.md`, `SUGGESTIONS.md`, `FLAGGED.md`) |
| `scripts/` | `generate_picks.py` (auto pick pipeline), `build_site.py` (JSON → HTML), `verify.py` (source-link / blank-flag / link-integrity checks) |

## Data rules (enforced by `scripts/verify.py`)

1. **Official sources only** — `nba.com`, `cdn.nba.com`, `ak-static.cms.nba.com`, `official.nba.com`, `pr.nba.com`, `statsdmz.nba.com` (allowlist check on every URL).
2. **Every table row links its source** — schedule rows → schedule PDF + live schedule page; injury rows → report PDF; pick rows → schedule + both teams' stats + injury + preview (six links per pick).
3. **Blank + flagged, never inferred** — nulls require an adjacent flag/note; picks whose injury input doesn't exist yet are `PROVISIONAL` and never scored.
4. **Pre-registered model** — parameters (HCA, rest/injury weights) are declared assumptions, flagged, and only editable pre-settlement with a logged revision.

## Verification

`python3 scripts/verify.py` → checks URL allowlist (394 URLs), blank+flag policy, full slate↔pick coverage, release-gate consistency, per-row source links and internal links across all 12 site pages.

## Repository history

The repository began as a single 6-byte `README.md` (full audit: [docs/REPO_REVIEW.md](docs/REPO_REVIEW.md), flagged fl-01). No LICENSE and no CI yet — both are reviewer decisions open in [docs/QUESTIONS.md](docs/QUESTIONS.md) (Q-07, Q-08).
