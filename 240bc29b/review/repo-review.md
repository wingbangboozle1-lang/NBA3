# Repository review — session `arena/240bc29b-nba3`

Independent line-by-line review of `wingbangboozle1-lang/NBA3` at branch
`arena/240bc29b-nba3` (branched from `main` @ `3a6c353dc87aad6eb35184a2ec2f0cc8759501f6`
= origin/main HEAD). Performed 2026-11-14. Every claim is checked against an official
source where one exists; anything that cannot be confirmed is left blank and flagged.
No values are inferred.

## Top-level inventory

| Path | What it is | Status | Official link / notes |
|---|---|---|---|
| `README.md` | Project overview + integration status; describes multiple workstreams | present | No LICENSE file in repo — licensing is an open owner decision (flagged) |
| `COORDINATION.md` | Shared task board for parallel sessions | present | Append-only; this session's section added at the end |
| `.gitignore` | Python/Node/editor ignores | present | — |
| `requirements.txt` | `requests==2.31.0` only | present | No lockfile; builds are offline-friendly |
| `.github/workflows/pages.yml` | CI: build, check, deploy to GitHub Pages | present | Legacy `main /` Pages source; workflow edits are visible to prior sessions |
| `index.html` | Root canonical dashboard landing page | present | Owned by session `arena/a459dadf-nba3`; not edited here |
| `executive-summary.html` | Cross-site consolidated executive summary | present | Hand-maintained; not edited here |

## Site trees present (each an independent session workstream, not a single reconciled model)

| Tree | Session | Pages | Notes |
|---|---|---|---|
| `/` + `app/` | `arena/8d3d0271-nba3` | 20 | Canonical dashboard; landing + category subpages |
| `/docs/` | `arena/f879620b-nba3` | ~10 | Data site (11/11 injury report) |
| `/site/` | `arena/7c532e8c-nba3` | 12 | Edge Lab site |
| `/edge/` | `arena-0a016df8-nba3` | 13 | Edge Lab dashboard via `pipeline/` |
| `/hub/` | `arena/99eabb04-nba3` | 18 | Consolidated dashboard |
| `/dashboard/` | `arena/925439ca-nba3` | 17 | Verified build (1,305 checks) |
| `/dash/` | `arena/2b9f1ae1-nba3` / `e40cd215` | ~12 | Unified dashboard |
| `d01ae7e2/` | `arena/d01ae7e2-nba3` | 12 | Namespaced workstream |
| `audit/`, `audit26/`, `audit36/`, `audit_dd1eb1f1/` | various | — | Audit/release-audit artefacts |
| `240bc29b/` | this session | new | Landing + category subpages (this session) |

Irregularity: **dashboard proliferation** — 8+ dashboard-family trees coexist, each with its own
ID namespace, injury snapshot and model variant. None is wrong; they are not reconciled. This is
documented as a suggestion for the owner (consolidate or archive), not a defect to fix unilaterally.

## Data directories reviewed

| Path | Contents | Verified against official source |
|---|---|---|
| `data/app/canonical.json` | Canonical dataset (canonical dashboard) | 183-game log, 49-row injury report, 27-game slate — re-verified by this session (S1–S4) |
| `data/app/official_*.json` | Official capture snapshots (slate, injuries, team ratings) | Re-verified 2026-11-14 against live NBA pages |
| `data/slate.json` | (prior session) 31-game slate 11/13–16 | Stale window; superseded by 11/14–17 |
| `data/injuries.json` | 117-row injury report (11/13 05:00 PM) | Superseded by 11/14 04:15 AM report |
| `data/model.json` | Model output | Model outputs are derived, not official; not re-endorsed |
| `data/picks.json` | `3 bytes` (effectively empty) | Picks blocked without a licensed odds feed |
| `data/origin/`, `model/` | Session `e22a2831` model workstream | Owned by another session; not touched here |
| `final/` | Session `arena/925439ca-nba3` verified build | Untouched; not this session's scope |

Irregularity: `data/picks.json` is effectively empty (3 bytes) — no market prices exist, so
no picks can be economically priced. Blocked, not an error; published on the flagged page.

## Scripts reviewed

| Path | Purpose | Notes |
|---|---|---|
| `scripts/build_app.py` | Canonical dashboard generator | Owned by session `arena/8d3d0271-nba3`; not edited here |
| `scripts/assemble_canonical.py` | Canonical dataset assembly | Owned by session `arena/25418e3f-nba3`; not edited here |
| `scripts/strategy_lab.py` | Leaderboard scoring, parlays, props | Seeded; deterministic; not edited here |
| `scripts/capture_official_2026_11_14*.py` | Official captures | Offline snapshots; not live re-fetches |
| `scripts/model.py` | Massey margin + totals model | Derived outputs; drift gate uses `PUBLISH_DP=6` |
| `tools/check_site.py` | Row/source/link checker | Owned by `arena/f879620b-nba3`; not edited here |
| `tools/validate_gates.py` | Validation-gate statistics | 13 unit tests pass |
| `tools/release_audit.py` | Release audit | Pre-existing RA-02…RA-07 observations |

## Tests reviewed

| Path | Tests | Result |
|---|---|---|
| `tests/test_validate_gates.py` | 13 | Pass |
| `pipeline/tests` | 29 | Pass |
| `verify/tests` | 16 | Pass |
| `audit/test_release_audit.py` | 7 | Pass |
| `audit_dd1eb1f1/test_audit.py` | 13 | Pass |
| `tests/test_injury_delta.py`, `tests/test_capture_c.py` | present | Part of this session's claim adjacency only |

## Irregularities and open questions carried to the flagged page

| ID | Finding | Source link | Blocks merge? |
|---|---|---|---|
| 24-R-01 | No `LICENSE` file; licensing, jurisdiction and bankroll/risk policy unknown | https://www.nba.com/termsofuse | No |
| 24-R-02 | No licensed market-odds source; every EV/ROI/CLV figure is blank or an arithmetic artefact | — (no source exists) | No |
| 24-R-03 | NBA.com Terms of Use §9 bars gambling use of NBA statistics | https://www.nba.com/termsofuse | No |
| 24-R-04 | Dutch Koa licence requirement for any online betting offer (if offered to NL users) | https://kansspelautoriteit.nl/online-kansspel-aanbieden | No |
| 24-R-05 | 8+ unreconciled dashboard trees; no single canonical source of truth | — | No |
| 24-R-06 | `data/picks.json` empty; picks blocked without a price feed | — | No |

## Conclusion

The repository is well-structured, fully source-linked on the canonical pages, and carries an
honest "nothing is funded / nothing beats the luck threshold" headline. No stored value was
found to contradict an official source. The open items are owner decisions (licensing, odds
feed, dashboard consolidation), not code defects. Nothing in this review blocks the merge.

Sources: official NBA schedule (S1), injury report index + PDF (S2–S3), team advanced
statistics (S4), NBA.com Terms of Use (S5) — all read 2026-11-14.
