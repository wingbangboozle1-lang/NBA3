# Coordination board

Shared task board for all agent sessions working in this repository. Every session must
claim a task (session ID + file scope) and push that claim **before** starting work. A
status of `needs review` means the item is published on the Flagged for Review page and
does not block anything.

Session IDs are the Arena branch names, because the workspace binds each session to a
fixed branch.

> **Correction notice (2026-11-13).** An earlier revision of this board marked T1–T12
> `done` before the work existed, and its verification log described artefacts that were
> not in the repository (a `data/raw/` directory, "31 games across 4 slates", a
> `scripts/build_all.py`). Those rows were inaccurate. The table below records the status
> that is true as of each commit, and the log now describes only artefacts that exist.

## Task board

| # | Task | Status | Owner (session ID) | File scope | Last update |
|---|---|---|---|---|---|
| T1 | Coordination board + repo review (line-by-line audit of prior work) | done | `arena/5697caaf-nba3` | `COORDINATION.md`, `docs/repo-review.md` | 2026-11-13 |
| T2 | Official-source data collection (team ratings, schedule, market prices, injury reports, prop inventory) | done | `arena/5697caaf-nba3` | `scripts/raw_data.py` | 2026-11-13 |
| T3 | Line-origination model + slate signals (single bets, 3-day horizon) | done | `arena/5697caaf-nba3` | `scripts/model.py`, `data/lines.json`, `data/picks.json` | 2026-11-13 |
| T4 | Player props + correlation measurement | **partial** — props priced and de-vigged, but **no prop model**; player-level correlations unmeasured | `arena/5697caaf-nba3` | `data/props.json`, `data/correlation.json` | 2026-11-13 |
| T5 | Strategy registry, validation gates, luck-removal scoring, leaderboard | done | `arena/5697caaf-nba3` | `data/strategies.json` | 2026-11-13 |
| T6 | Injury / rotation / game-flow analysis from the official report | done (statuses); minutes analysis **not possible** | `arena/5697caaf-nba3` | `data/injuries.json` | 2026-11-13 |
| T7 | Decision questions register (known / unknown / how to discover) | done | `arena/5697caaf-nba3` | `questions.html` | 2026-11-13 |
| T8 | Suggestions queue with review-and-choose workflow | done | `arena/5697caaf-nba3` | `suggestions.html` | 2026-11-13 |
| T9 | Flagged for Review page | done | `arena/5697caaf-nba3` | `review.html` | 2026-11-13 |
| T10 | Executive summary | done | `arena/5697caaf-nba3` | `index.html`, `docs/executive-summary.md` | 2026-11-13 |
| T11 | Pages build, validation gate, deploy verification | **in progress** — validator passes locally; CI deploy not yet observed | `arena/5697caaf-nba3` | `.github/workflows/pages.yml`, `scripts/validate_site.py` | 2026-11-13 |
| T12 | PR to `main` + merge + deploy confirmation | **open** — will be marked done only after the run is observed green | `arena/5697caaf-nba3` | `COORDINATION.md` | 2026-11-13 |

**Open claims:** T11 and T12, both held by `arena/5697caaf-nba3`.

### What T4 and T6 deliberately did not do

- **No prop model.** A prop probability needs a minutes distribution. No minutes source was
  retrieved, so `model_p_over` is `null` on every prop row and the UI says "no model". This is
  a gap, not an omission to be patched with a guess.
- **No player-level correlations.** Points-vs-rebounds, player-vs-teammate and minutes-vs-prop
  need per-player game logs. The three correlations that *could* be computed from game totals
  are published with n and 95% CIs; the rest are blank and listed as IR-09.
- **No minutes projection.** The official report gives a status per player, not a forecast.
  `availability_drag` is an ordinal exposure score and is labelled as unitless.

### File ownership map (non-overlapping scopes)

| Path | Owner session | Notes |
|---|---|---|
| `COORDINATION.md` | `arena/5697caaf-nba3` | Integration log. Other sessions append a row, do not rewrite. |
| `scripts/**`, `data/**` | `arena/5697caaf-nba3` | Source snapshot + model + generator. |
| `*.html` | `arena/5697caaf-nba3` | **Generated** by `scripts/build_site.py`. Never hand-edit. |
| `.github/workflows/pages.yml` | `arena/5697caaf-nba3` | Build + deploy gate. |
| `docs/**` | `arena/5697caaf-nba3` | Long-form documentation. |

If another session needs a file in one of these scopes, it must log a request here instead
of editing the file.

## Handoff / environment notes

- `2026-11-13`: Checkout at session start contained only `README.md` (6 bytes) on branch
  `arena/5697caaf-nba3`, branched from `6c3004d3`. Two **earlier** PRs from a different,
  already-closed session (`arena/49064d5a-nba3`, PRs #1 and #2) had been merged into `main`.
  This session fast-forwarded onto `origin/main` so its work builds on that site rather than
  discarding it. Nothing was force-pushed and no other session's work was reverted.
- **Branch naming deviation (flagged):** the brief asks for branches named
  `session-<id>/<task>`. The workspace binds this session to the fixed branch
  `arena/5697caaf-nba3` and forbids switching, so all work is committed there. Recorded as
  `IR-01`.
- **Single-session execution:** no other session held a claim during this session (verified
  via `git ls-remote` free of other branches and a board with no open claims). The integration
  duties (T11, T12) are therefore performed by this session, as the brief requires when all
  tasks are done.
- **Network environment:** the sandbox shell has no general egress (only `github.com`,
  `api.github.com`, `registry.npmjs.org`, `pypi.org`, `*.pythonhosted.org`). `urllib`
  connections to ESPN/NBA/Basketball-Reference fail at TLS. All external data was therefore
  retrieved through the agent's page-fetch capability and **transcribed verbatim** into
  `scripts/raw_data.py`, with the source URL and retrieval timestamp beside every block, so
  every number is traceable even though no raw HTML snapshot is committed.
- **No manual user input:** every decision in this build was made autonomously; open questions
  are recorded rather than asked.

## Verification log

Every published row carries a source URL and a verification tier. Tiers:

- **OFFICIAL** — operated by the NBA (`nba.com`, `official.nba.com`, `ak-static.cms.nba.com`).
- **TRUSTED-2°** — reputable secondary (`basketball-reference.com`, `espn.com`). Not the
  league's own number; used only where the official source is not machine-readable, and
  always labelled in the UI.
- **MARKET** — a live price from a book. A fact about the market at a timestamp, not about
  the game.
- **DERIVED** — arithmetic on the above by `scripts/`. Formulas in `docs/model-methodology.md`
  and on `methodology.html`.
- **UNVERIFIED** — no source found; value left blank and listed on `review.html`.

| Date | Task | What was verified | Method / result |
|---|---|---|---|
| 2026-11-13 | T1 | Prior site's claims and links | Read every element of the previous `index.html`. It published no numeric NBA data, and its injury link pointed at the 2025-26 index during the 2026-27 season → `IR-02`. |
| 2026-11-13 | T2 | Team ratings, all 30 teams | `basketball-reference.com/leagues/NBA_2027.html`. Checked `NetRtg == ORtg − DRtg` for all 30 → **0 violations**. Also `SRS == MOV + SOS` for all 30 → **0 violations**. |
| 2026-11-13 | T2 | Completed games sample | 86 games, 2026-11-01 → 11-12. Season W+L sums to 348 (174 games) with W=174 and L=174. No team's subset wins or losses exceed its season total → **0 violations**. |
| 2026-11-13 | T2 | 72-hour slate | 23 games, 2026-11-13 → 11-15, every one with an official `002…` game ID. Game `401909297` resolves to **MIL@ORL**, not ORL@WAS — an earlier note in this session had it wrong; corrected against the odds payload and the fixture list. |
| 2026-11-13 | T2 | Market snapshots | 9 two-way prices. Each row parsed and re-compared against the provider's own details string (favourite, line, both moneylines) → **9/9 consistent**. This check found real sign-transposition errors in the first transcription, which were fixed. |
| 2026-11-13 | T2 | Injury statuses | 75 rows from the timestamped NBA PDF (11/13/26 05:00 PM), via the 2026-27 index. Not the 2025-26 index behind `IR-02`. |
| 2026-11-13 | T2 | Prop athlete identities | 5 athlete IDs resolved through ESPN's per-athlete endpoint: Karl-Anthony Towns, Kelly Oubre Jr., Josh Hart, Mikal Bridges, Andre Drummond. Flagged: Towns/Hart/Bridges/Drummond all resolve to team id 18 (NYK), which is inconsistent with a PHI label on one prop row → `IR-07`. |
| 2026-11-13 | T3 | Model arithmetic | Constants **measured** from the 86-game sample: home margin +1.51 (CI95 −2.17…+5.19), margin sd 17.15, total mean 225.98 (CI 221.98…229.97), total sd 18.62, home win rate 0.500 (43/86). |
| 2026-11-13 | T3 | Sign convention | Cross-checked against a known-sane baseline: a pick'em must give p ≈ 0.50. An earlier version of the pick code used the handicap where the margin belonged and produced 49-point "edges" — caught and fixed. `validate_site.py` now asserts `model_spread_home == -model_margin_home`. |
| 2026-11-13 | T3 | Forecast calibration | Brier 0.1528 vs 0.25 baseline over 86 games. **In-sample, disclosed.** Luck test: 46.2 expected wins vs 43 observed, z = −0.79, p = 0.4294 → indistinguishable from chance. |
| 2026-11-13 | T3 | Signal screening | 20 raw signals, **all** positive-EV against one book. Screens reject 12 for oversize divergence and 7 for injury exposure → 1 survives. The all-positive result is published as evidence of model blindness, not skill. |
| 2026-11-13 | T4 | Correlation | Measured on 86 games with Fisher-z CIs: away-total vs home-total r = 0.082 (−0.132…0.289); margin vs total r = 0.005 (−0.207…0.217); pooled within-team own vs opponent r = 0.049 across 29 teams. Player-level correlations **not measured** → `IR-09`. |
| 2026-11-13 | T5 | Gates | 7 gates × 6 strategies. Best is 2/7. G2 (leakage) and G6 (economic) fail universally because no historical price archive exists. S6 blocked at 0/7. |
| 2026-11-13 | T11 | Site integrity | `scripts/validate_site.py` — HTML parse, internal-link resolution, per-data-row source requirement, unverified-cell-must-not-carry-a-number, statistic range checks, correlation-without-n, prop-probability-without-model, pick-passed-screening-with-high-injury-risk, and stale-content detection. **Passes.** |
| 2026-11-13 | T11 | CI reproducibility | Workflow regenerates `data/` and HTML then fails if the result differs from the commit, so a hand-edited page cannot be deployed. |

## Irregularities and open items

Canonical list is on `review.html` (IR-01 … IR-15). The load-bearing ones:

- `IR-01` branch-naming deviation (workspace constraint) — not blocking.
- `IR-02` prior site linked the 2025-26 injury index during the 2026-27 season — fixed; left on the review page.
- `IR-03` prior site asserted "no data exists" while an official schedule, the official dated injury report and public two-way prices were all retrievable — corrected by collecting them; the correction is logged, not hidden.
- `IR-04` home-court edge is measured but its CI spans zero, and the shrinkage constant `k` is assumed, not fitted — sensitivity disclosed.
- `IR-05` Basketball-Reference and ESPN are not the NBA — labelled TRUSTED-2°.
- `IR-06` one book, one snapshot — "edge" is versus that provider at that minute.
- `IR-07` prop athlete IDs only partly resolved; unresolved names are withheld rather than guessed.
- `IR-08` no prop model — no minutes source.
- `IR-09` four player-level correlations unmeasurable without game logs.
- `IR-11` five of six strategies carry no score — no historical closing prices, therefore no ROI claim anywhere.
- `IR-12` model lines ignore availability; the injury report is used only to *reject* signals.
- `IR-13` market movement is shown beside availability counts but causation stays unverified.
- `IR-14` point-in-time snapshot; superseded within ~15 minutes near tip-off.
- `IR-15` legal / licensing / bankroll policy unknown ⇒ no staking advice.

## Build / deploy record

- Data snapshot: `2026-11-13T22:30Z`.
- Regenerate: `python3 scripts/model.py` → `data/*.json`, then
  `python3 scripts/build_site.py` → `*.html`. Both are stdlib-only and offline.
- Gate: `python3 scripts/validate_site.py` must exit 0. CI runs it before deploying and also
  verifies the committed HTML is byte-identical to a fresh build.
- Deploy: `.github/workflows/pages.yml` on push to `main` → `https://wingbangboozle1-lang.github.io/NBA3/`.
