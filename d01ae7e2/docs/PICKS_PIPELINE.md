# Picks Pipeline (T06) — auto-generation, no manual input

**Author:** session d01ae7e2 · **Date:** 2026-11-13 · Machine-readable outputs: `d01ae7e2/data/picks.json`, `d01ae7e2/data/correlations.json`

## Requirement

> "Auto-generated picks for every upcoming slate of games up to a maximum of 3 days in advance using our originated lines with **no manual input**."

## Window definition

Data cut: **2026-11-13 18:28 ET**. Window = today **+ 3 days max advance** → **Nov 13–16, 2026 = 31 games** (9 + 5 + 9 + 8). The window is computed from the clock, not hand-picked; regenerating after midnight re-derives it.

## Pipeline stages (all scripted)

```
d01ae7e2/data/teams.json ─────┐
d01ae7e2/data/slate.json ─────┼──> d01ae7e2/scripts/generate_picks.py ──> d01ae7e2/data/picks.json
d01ae7e2/data/injuries.json ──┤        (fair lines, P(home),      d01ae7e2/data/correlations.json
d01ae7e2/data/players.json ───┘         release gates, S2/S3)
                                        │
d01ae7e2/data/*.json ────────────────> d01ae7e2/scripts/build_site.py ──> docs/*.html
                                        │
all files ──────────────────> d01ae7e2/scripts/verify.py ──> pass/fail (exit code)
```

1. **`python3 d01ae7e2/scripts/generate_picks.py`** — reads only the four verified input files. Deterministic: same inputs → same outputs. Emits for every game:
   - `our_fair_spread_home` (negative = home favored — standard convention), `our_fair_total`, `model_p_home`
   - `pick_side` only when **both** gates pass (edge ≥ 3.0 pts **and** P ≥ 0.60); otherwise `NO_BET_LOW_EDGE`
   - `strategy_status` ∈ {`PAPER_RELEASED`, `PROVISIONAL_INJURY_PENDING`, `PROVISIONAL_PARTIAL_INJURY`, `NO_BET_LOW_EDGE`}
   - six `source_urls` per row: schedule page, schedule PDF, both teams' stats pages, injury report, game preview
2. **S2 parlay stage** — takes the two strongest released legs of each date, computes joint probability with declared ρ, rejects below 0.36 joint.
3. **S3 stack stage** — same-team teammate pairs with n ≥ 5 overlapping official game logs; availability gate against the latest report; auto-rejects Out/Doubtful players.
4. **`python3 d01ae7e2/scripts/build_site.py`** — renders `docs/` from JSON (tables cannot drift from data).
5. **`python3 d01ae7e2/scripts/verify.py`** — offline checks: official-domain allowlist over all 394 URLs, blank+flag policy, pick coverage of the full slate, release-gate consistency, per-row source links in HTML, internal-link integrity.

## Freshness & provisional rules (Q-10 answered)

| Injury report state for game | Model input | Status | Scored? |
|---|---|---|---|
| `submitted` (both teams) | team strength + rest + **verified OUT production** | released or no-bet per gates | yes, once settled |
| `partial` (11/14: 7 teams NOT YET SUBMITTED) | strength + rest only; injury fields blank | `PROVISIONAL_PARTIAL_INJURY` | **no** |
| `not_published` (11/15–16) | strength + rest only; injury fields blank | `PROVISIONAL_INJURY_PENDING` | **no** |

Provisional rows are **published** (the brief requires 3-day-ahead auto-generation) but **never scored**, and they re-generate automatically the moment a covering report appears. This is how the pipeline honors both "no manual input" and "never infer": it emits a labelled line instead of a guessed injury input.

**Re-trigger design:** filename pattern `Injury-Report_YYYY-MM-DD_HH_MMAM|PM.pdf` under
`https://ak-static.cms.nba.com/referee/injury/` is stable (4 stamps observed today). A future cron polling that pattern re-runs stage 1 — queued as suggestion **SG-04** (not implemented: reviewer decision first).

## Result grading (Q-11 answered — design recorded, implementation future)

`d01ae7e2/scripts/grade_picks.py` (designed, not yet written) will, after each slate:

1. Read official game-summary linescores (verified pattern: `nba.com/game/<away>-vs-<home>-<gameid>` returns final score, quarters — proven on `cle-vs-nyk-0022600218`: CLE 115–107 NYK);
2. Settle `PAPER_RELEASED` rows: spread side covers by ≥ 0 → win, else loss; totals likewise;
3. Append to `d01ae7e2/data/results.json` (immutable, weekly freeze);
4. Recompute leaderboard ROI + Wilson CI.

Grading **skips** all PROVISIONAL rows and any game whose official summary is not yet available (also flagged, never guessed).

## Output summary at data cut

| Status | Count | Meaning |
|---|---|---|
| PAPER_RELEASED | 7 | passed edge + confidence + freshness gates |
| PROVISIONAL_PARTIAL_INJURY | 5 | 11/14 games, report incomplete |
| PROVISIONAL_INJURY_PENDING | 17 | 11/15–16 games, report not published |
| NO_BET_LOW_EDGE | 2 | recorded pass (selectivity is intentional) |
| **Total** | **31** | full window covered, 100% source-linked |

S2: 1 parlay released. S3: 1 stack released (Brunson–Towns, ρ=0.569, n=5).

## Reproducibility

```bash
python3 d01ae7e2/scripts/generate_picks.py   # regenerates picks.json + correlations.json
python3 d01ae7e2/scripts/build_site.py       # regenerates docs/*.html
python3 d01ae7e2/scripts/verify.py           # exit 0 = all checks pass
```

No step reads anything outside `d01ae7e2/data/*.json`; no step requires network; no step accepts manual edits (edits belong in the JSON inputs, which are verified first).
