# COORDINATION

Multi-session coordination for the NBA3 line-origination and strategy system.

**Rules.** Claim a file scope before editing it. Never edit another session's claimed files —
log a change request here instead. Pull with `--rebase` before every push. Commit small and
often. A claim older than 60 minutes is stale and may be taken over; log the handoff.

---

## Sessions

| Branch | Owner | Scope | Status |
|---|---|---|---|
| `arena/e22a2831-nba3` | `e22a2831` | Full build: data capture, model, docs, site, Pages | **active** — see task board |

No other session has claimed a scope in this repository. If you are starting a new session,
append a row before editing anything.

## File scope ownership

| Path | Owner | Notes |
|---|---|---|
| `data/raw/**` | `e22a2831` | Raw snapshots of official pages |
| `data/processed/**` | `e22a2831` | games.csv, teams_advanced.csv, players_top_minutes.csv, injuries.csv, schedule_upcoming.csv, model_output.json |
| `model/**` | `e22a2831` | nbastats.py, build.py, build_docs.py |
| `docs/**` | `e22a2831` | Generated from model_output.json — edit the generator, not the output |
| `site/**` | `e22a2831` | build_site.py plus generated HTML |
| `COORDINATION.md` | `e22a2831` | This file |
| `README.md` | `e22a2831` | |

> `docs/**` and `site/**` are **generated**. Do not hand-edit `.html` or the docs `.md`
> files — change `model/build_docs.py` or `site/build_site.py` and re-run, or the two will
> drift apart.

---

## Task board

Legend: `todo` · `in-progress` · `done` · `blocked`

| ID | Task | Owner | Status | Notes |
|---|---|---|---|---|
| T1 | Create directory scaffold and this file | `e22a2831` | `done` | commit `4fcea12` |
| T2 | Capture official results, 20 Oct – 12 Nov | `e22a2831` | `done` | 174 games in `data/processed/games.csv`; reconciles to 348 team-games, 0 mismatch |
| T3 | Capture official team advanced stats (all 30) | `e22a2831` | `done` | `data/processed/teams_advanced.csv` |
| T4 | Capture official player stats | `e22a2831` | `done` | Top 31 by minutes only — **see T4b** |
| T5 | Capture official injury report | `e22a2831` | `done` | PDF 2026-11-13 17:15; 13–14 Nov rows |
| T6 | Capture upcoming schedule (D+0 … D+3) | `e22a2831` | `done` | 31 games, 13–16 Nov, with game IDs and tip times |
| T7 | Build rating engines | `e22a2831` | `done` | Additive, Massey, blend; pure Python, no third-party deps |
| T8 | Walk-forward backtest | `e22a2831` | `done` | 60-game burn-in, 114 graded out-of-sample games |
| T9 | Originate lines for every upcoming game | `e22a2831` | `done` | Published line = LM-C (validated); efficiency model shown as cross-check only |
| T10 | Define and run validation gates | `e22a2831` | `done` | 7 gates; 8 strategies; **0 pass** |
| T11 | Compute correlations | `e22a2831` | `done` | Spread/total residual r = +0.091; player-level **blocked** |
| T12 | Track injury → rotation minutes → production | `e22a2831` | `done` | Quantified for captured players, blank + flagged for the rest |
| T13 | Game-flow analysis | `e22a2831` | `done` | Pace, rest, OT, home court |
| T14 | Executive summary | `e22a2831` | `done` | `docs/executive-summary.md` + site landing page |
| T15 | Site-improvement suggestions section | `e22a2831` | `done` | `site/suggestions.html`, 5 problem areas × 2–3 options each |
| T16 | Open questions section | `e22a2831` | `done` | `site/questions.html`; 4 decisions need a human |
| T17 | Flagged-for-Review page | `e22a2831` | `done` | 16 items with sources |
| T18 | GitHub Pages site (landing + 10 subpages) | `e22a2831` | `done` | Dashboard UI, every row carries a source link |
| T19 | PR to `main`, merge, confirm Pages deploy | `e22a2831` | `in-progress` | See Integration log below |
| T4b | **Widen player capture beyond top 31** | unclaimed | `todo` | Blocks T20; see change request CR-1 |
| T20 | Per-player game logs → prop distributions | unclaimed | `blocked` | Blocked by T4b |
| T21 | Daily refresh via GitHub Actions | unclaimed | `todo` | Suggestion C1; not implemented |

---

## Change requests (cross-session)

| ID | From | To | Request | Status |
|---|---|---|---|---|
| CR-1 | `e22a2831` | any future session | Capture the full 465-row official player minutes table (9 chunks) so injured players outside the top 31 have official minutes. Until then every injury minutes-vacuum figure is a floor. | open |
| CR-2 | `e22a2831` | any future session | Capture `nba.com/stats/players/boxscores` by date to unblock player-prop distributions and player-level correlations. ~4,000 rows for the season to date; chunk across sessions. | open |
| CR-3 | `e22a2831` | reviewer | Decide whether sportsbook prices may be used for *comparison* (not copying). Without this, no strategy can be scored on profit — only on self-consistency against our own line. | open |
| CR-4 | `e22a2831` | any future session | Do **not** regenerate `docs/` or `site/` by hand. Both derive from `data/processed/model_output.json`; re-run `python3 model/build.py` then `python3 model/build_docs.py` and `python3 site/build_site.py`. | standing |

---

## Handoff log

| Time (UTC) | From | To | What |
|---|---|---|---|
| 2026-11-13 22:00 | — | `e22a2831` | Session started; scaffold created at commit `4fcea12` |
| 2026-11-13 23:05 | `e22a2831` | — | Data, model, docs and site complete. Proceeding to PR → merge → Pages. |

---

## Known environment constraints

Recorded so a future session does not waste time rediscovering them.

- **No outbound network from the shell.** `curl`/`wget` fail (TLS exit 35). Use the
  `fetch_page` / `web_search` tools for all external data.
- **No third-party Python packages.** `numpy`, `scipy` and `pandas` are unavailable. `model/`
  is pure standard library; `model/nbastats.py` implements OLS, Pearson r with Fisher
  intervals, exact binomial, Student-t via the incomplete beta function, and
  Benjamini-Hochberg from first principles.
- **JSON API endpoints are blocked** (HTTP 500): `cdn.nba.com/static/json/...`,
  `data.nba.net/prod/v1/...`, `stats.nba.com/stats/scoreboardv3`. Use `www.nba.com` HTML
  pages and the official `ak-static.cms.nba.com` injury PDFs instead.
- **`www.nba.com/standings` returns no data** (client-rendered). Use
  `/stats/teams/advanced` for records.
- **`/games?date=` pages truncate at chunk boundaries.** A slate is not complete until the
  last chunk is read — 1 chunk for ≤4 games, 2 for 7–11, 3 for 14–15.

---

## Integration log

| Item | Result |
|---|---|
| Line-by-line re-verification | Every one of the 174 results reconciles to official GP **and** official W-L for all 30 teams |
| Broken-link check | All internal links resolve; 91 distinct external links, all `nba.com`; game-URL pattern spot-checked live on 4 URLs |
| Unverified values | Left blank with an UNVERIFIED badge and collected on the Flagged for Review page |
| Flagged items | 16, published — they do **not** block the merge |
| PR | _recorded below after opening_ |
| Merge | _recorded below_ |
| Pages deploy | _recorded below_ |
