# Coordination board

Session: `arena/49064d5a-nba3` (current Arena-owned branch; branch names are fixed by the workspace).

| Task | Status | Owner | File scope |
|---|---|---|---|
| Baseline repository review and coordination setup | done | arena/49064d5a-nba3 | COORDINATION.md |
| Official-source NBA strategy research and verification | done (framework; no model claims) | arena/49064d5a-nba3 | index.html, README.md |
| Dashboard / GitHub Pages site and validation workflow | done (deployment pending repository settings) | arena/49064d5a-nba3 | index.html, README.md, .github/workflows/pages.yml |

## Handoff and environment notes

This checkout contained only a six-byte README and no app, data, package configuration, or preexisting coordination board. No other session claims were present when this board was created. The workspace is bound to branch `arena/49064d5a-nba3`; it cannot be switched to a separately named session/integration branch here. This session was therefore responsible for both analysis and integration on the assigned branch. The board claim was committed and pushed immediately before work began. No concurrent edits were observed.

## Verification log

- Initial inventory: `git status --short --branch`, root directory listing, and README/coordination check. No existing product or analysis material to validate.
- Sources checked: [NBA Stats glossary](https://www.nba.com/stats/help/glossary) for official statistical terminology; [NBA Official injury report index](https://official.nba.com/nba-injury-report-2025-26-season/) for injury-report entry point; [example timestamped NBA injury PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-11_05_00PM.pdf) to inspect report fields and dated status nature. No player-level availability or projections were copied into current recommendations.
- Every claim about absent local data was grounded in repository inventory. No odds, projections, correlations, model results, ROI, or picks have been invented. Strategy rows are explicitly proposed experiments, not verified performance facts. Official sources establish terminology/report provenance only, not predictive value or data licensing.
- Site validation: Python HTMLParser checked 8 section IDs and 14 links; no broken in-page anchors. `git diff --check` passed. GitHub Pages workflow includes the same fragment validation and static upload/deploy job; actual deployment still requires repository Pages/actions settings and a merge to `main`.
- Irregularities flagged on site: missing authorized historical/statistical, schedule, odds/props, rotation, and settlement data; licensing, jurisdiction, and bankroll/risk policy are unknown; no measured correlation or validation evidence. These prevent live picks and strategy eligibility but do not block publishing this research dashboard.

## Deployment / PR status

- PR [#1](https://github.com/wingbangboozle1-lang/NBA3/pull/1) was merged to `main` with merge commit `ce3273eded5dc8083e0523d44666b92d7bee8f9e` on 2026-11-13.
- GitHub Actions run [43519089153](https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43519089153) completed successfully: both static validation/build and Pages deployment jobs passed. A separate Pages deployment run also showed success. Deployment confirmed by workflow; site URL is the repository GitHub Pages URL (repository custom Pages URL is not inferred here).
- Workflow emitted non-fatal platform notices: Node.js 20 action runtime deprecation and forthcoming `ubuntu-latest` image migration. No check failed.

---

## Session f879620b (`arena/f879620b-nba3`) — data, validation tools, site (`docs/`)

Shared task board for all agent sessions working on `wingbangboozle1-lang/NBA3`.

## Branch rule (read first)

The session branch assigned by Arena is **`arena/f879620b-nba3`** (branched from `main` @ `6c3004d`).
Earlier instructions in the task text suggested `session-<id>/<task>` branches. That conflicts with the
Arena rule that a session works on exactly one branch, so **all work stays on `arena/f879620b-nba3`**.
Each task below is still scoped to its own files so parallel sessions can be merged without overlap.

Session ID for this log: `f879620b` (session-owner: Arena Agent Mode session on `arena/f879620b-nba3`).

## Status legend

- `unclaimed` — nobody is working on it
- `in progress` — claimed; session ID and files listed
- `done` — finished; sources, verification, irregularities recorded below
- `needs review` — published on the **Flagged for Review** page; does not block anything

## Task board

| # | Task | Status | Owner (session) | Files in scope |
|---|------|--------|-----------------|----------------|
| T1 | Repo review: line-by-line check of repo contents, flag irregularities | done | f879620b | `README.md`, `COORDINATION.md`, `docs/flagged.html` |
| T2 | Official-source data capture: injuries (11/11 report), upcoming slate (11/13–11/16), 2026-27 rules | done | f879620b | `docs/data/data.json` |
| T3 | Site: landing, executive summary, category subpages, tables with source links | done | f879620b | `docs/*.html`, `docs/assets/*` |
| T4 | Validation gates + statistics helpers (no strategies validated yet) | done | f879620b | `tools/validate_gates.py`, `tests/test_validate_gates.py` |
| T5 | Site link/source checker | done | f879620b | `tools/check_site.py` |
| T6 | Strategy research (single bets / parlays / props) and correlation values | blocked | — | needs licensed odds + player data (see Questions page) |
| T7 | Injury → rotation minutes / production model | blocked | — | needs historical minutes/box-score data (see Questions page) |
| T8 | Picks generation for 3-day slates using originated lines | blocked | — | needs T6 and T7 |
| T9 | Improvement suggestions (decision page) | done | f879620b | `docs/suggestions.html` (suggestions only; nothing implemented) |
| T10 | Integration: merge, re-verify, build check, PR to `main`, merge, Pages deploy check | done (PR #3 merged; deploy success — see T10 log) | f879620b | `docs/`, `COORDINATION.md`, `README.md` |

## Task logs

### T1 — Repo review
- Repo at start: `README.md` containing only `# NBA3`; no code, no license, no data. Single commit `6c3004d Initial commit`.
- Remote: `origin https://github.com/wingbangboozle1-lang/NBA3.git`. GitHub Pages was already enabled on `main` (path `/`, status `built`).
- Irregularities: see `docs/flagged.html` (F-01 … F-04).
- Sources: repository state (local git); `gh api repos/wingbangboozle1-lang/NBA3/pages`.

### T2 — Official data capture
- Sources read: NBA injury report PDF 11/11/26 07:00 PM (`ak-static.cms.nba.com`), NBA 2026-27 schedule by date PDF (chunks 0, 1, 5, 6), NBA 2026-27 schedule press release (`pr.nba.com`), Official NBA Playing Rules 2026-27 PDF (chunks 0, 2–5).
- Not captured: 11/11 injury report rows after `GSW@HOU` (text truncated in chunk 0); latest 11/13 injury reports (found 01:00 PM, 01:15 PM, 04:15 PM versions — row text too fragmented to transcribe without error); schedule rows after game #245 (11/16).
- Irregularities: F-05 … F-09.

### T3 — Site
- Pages source changed from `main /` to `main /docs` so the site lives in `docs/` and the repo root stays clean. (Logged in `flagged.html` F-03.)

### T4 — Validation gates
- Implemented exact binomial test, Wilson interval, Pearson correlation, Benjamini–Hochberg adjustment, parlay dependence ratio, and gate evaluation. Thresholds are **proposed, not approved** (see Strategies page).
- Verification: `python3 -m unittest tests/test_validate_gates.py` (tests compare against brute-force sums and known values).

### T5 — Link/source checker
- `python3 tools/check_site.py` verifies: every data row has a source ID that resolves to an `https://` URL in `sources`; every internal `href` in `docs/*.html` resolves to a file. External URLs were checked only where fetched during T2 (listed in Sources page).

### T9 — Suggestions
- Suggestions only. No changes implemented. Each has status **Awaiting your choice**.

### T10 — Integration (pending)
- PR: [#3](https://github.com/wingbangboozle1-lang/NBA3/pull/3) `arena/f879620b-nba3` → `main`
- Merge: merge commit `c0cf8bdbfa6ef8fa4fc48bb5f965fc36b283b855`, merged 2026-11-13T22:32:18Z (`gh pr merge 3 --merge`; first attempt blocked by a conflict with `main`, resolved by merging `origin/main` and keeping both sides).
- Checks: `Deploy static dashboard to GitHub Pages` workflow run 43520084766 → success (includes the NBA3 unit tests and `tools/check_site.py`). Pages build run 43520084415 → success. Pages status: `built`.
- Live: root dashboard https://wingbangboozle1-lang.github.io/NBA3/ · data site https://wingbangboozle1-lang.github.io/NBA3/docs/ (checked with fetch: landing, data.json and docs/index.html all served).
- Not done (blocked, unchanged): T6 strategy research and correlation values, T7 injury→rotation model, T8 picks. Each needs a verified odds source and historical player data (Questions Q01, Q03).

## Handoff / conflicts log
- No merge conflicts in this session (single branch).

### T10 — GitHub Pages configuration (logged)
- Attempted `gh api -X PUT repos/wingbangboozle1-lang/NBA3/pages -f source[path]=/docs` → HTTP 403 ("Resource not accessible by integration").
- Pages source therefore remains `main /`. The site lives in `docs/`; root `index.html` redirects to `docs/index.html`. Logged as F-03 for the owner.

## Merge log (integration, session f879620b)
- `main` had moved (PR #1 and #2 from `arena/49064d5a-nba3`). Merged `origin/main` into `arena/f879620b-nba3`; conflicts in `COORDINATION.md`, `README.md`, `index.html` were resolved by keeping both sides. Their index dashboard is kept; a link to `docs/` was added to its navigation. Their Pages workflow is kept and extended to run the NBA3 checks.

---

## Session arena/7c532e8c-nba3 (current) — claims

Session ID: `arena/7c532e8c-nba3`. Branch naming: the workspace fixes the branch to `arena/7c532e8c-nba3`; the `session-<id>/<task>` naming in the brief cannot be used here (Arena policy: work only on the assigned branch). Non-overlapping file scopes are kept per task inside this one branch. The prior session's board above is preserved as history; this session extends (does not overwrite) its published site.

| Task | Status | Owner | File scope |
|---|---|---|---|
| T1 Repo review & irregularities | done (needs owner review of flags) | arena/7c532e8c-nba3 | data/flags.json, data/repo_review.json |
| T2 Official source register & link verification | done | arena/7c532e8c-nba3 | data/sources.json |
| T3 Official 3-day slate (11/13–11/16/2026) | done (subject to change; re-pull at query time) | arena/7c532e8c-nba3 | data/schedule.json |
| T4 Official injury report transcription (11/13/26 5:00 PM) | done (117 rows; 18 unattributed left blank) | arena/7c532e8c-nba3 | data/injuries.json |
| T5 Strategy candidates, validation gates, correlation | done as framework (all blocked; no values) | arena/7c532e8c-nba3 | data/strategies.json, data/validation_gates.json |
| T6 Questions & suggestions queue | done (awaiting owner decisions) | arena/7c532e8c-nba3 | data/questions.json, data/suggestions.json |
| T7 Site build (landing + category subpages) | done (scripts/build_site.py; site/ generated) | arena/7c532e8c-nba3 | scripts/build_site.py, site/, scripts/archive/; root index.html kept (f879620b dashboard; integration added a nav link to site/) |
| T8 Integration: merge origin/main, resolve conflicts, build, link check, PR, merge, Pages verification | in progress (merge commit on this branch; PR and merge result recorded below) | arena/7c532e8c-nba3 | COORDINATION.md, README.md, index.html (nav link only), .github/workflows/pages.yml, PR |

Claimed at: 2026-11-13 (UTC). No other session claims were present on `origin/main` at claim time (`dbb8575`).

### Sources used (this session)

Official sources, all checked on 2026-11-13 (see the live Sources page for limits):
- [NBA.com stats glossary](https://www.nba.com/stats/help/glossary): first chunk of 10 read.
- [NBA Official injury report, 2026-27 index](https://official.nba.com/nba-injury-report-2026-27-season/): reporting deadlines read.
- [Injury report PDF, 11/13/26 05:00 PM](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf): both chunks read; 117 rows transcribed.
- [2026-27 schedule by date (PDF)](https://cdn.nba.com/manage/2026/08/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf): 'as of Aug 13, 2026, subject to change'; 31 games for 11/13–11/16 read.
- [NBA schedule release page](https://www.nba.com/news/2026-27-schedule-team-by-team-index): PDF links and release context.
- [NBA.com Terms of Use](https://www.nba.com/termsofuse): §1 and §8–§11 read (3 of 10 chunks).
- [Kansspelautoriteit homepage](https://kansspelautoriteit.nl/) and [online kansspel aanbieden](https://kansspelautoriteit.nl/online-kansspel-aanbieden): art. 31a Koa licence requirement read (Dutch).
- Prior version checked: [2025-26 injury index](https://official.nba.com/nba-injury-report-2025-26-season/) still resolves but is superseded.

Failed or not used: [NBA CDN live scoreboard JSON](https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json) returned HTTP 500 (not used). The NBA schedule news article appeared only as a search snippet (not used as evidence).

### Verification performed

- Injury rows: transcribed from the PDF text; each row carries its report link. Attribution codes R/S/U/T are kept on each row (table on the Injury tracker page). Team-level 'NOT YET SUBMITTED' rows are marked T.
- Game-flow counts: recomputed independently from the injury rows (R/S/T attribution, matched on date and team). Results matched the recount for all 21 teams with rows on 11/13–11/14.
- Schedule: 31 games (11/13: 9; 11/14: 5; 11/15: 9; 11/16: 8) transcribed from the PDF. Home/away confirmed only where the injury report labels the matchup (11/13 and 11/14). Other dates keep the printed order (7C-F-10).
- Build: `python3 scripts/build_site.py` validated 117 injury rows, 31 games and 11 sources, and checked 553 links across 12 pages (0 broken). The build fails if a row has no official link and no flag.
- Repository review: origin/main read (b2efd23 at integration); at baseline (6c3004d) the repo had no LICENSE file, no data, and no model code.

### Irregularities and flags (see the Flagged for Review page)

- **Blockers:** 7C-F-01 (NBA Terms §9 bars gambling use of NBA statistics), 7C-F-02 (Dutch Koa licence requirement for online sports-betting offers), 7C-F-03 (no licensed odds data, so no lines or picks).
- **Irregularities:** 7C-F-07 (prior dashboard linked the 2025-26 injury index; current season is 2026-27), 7C-F-08 (18 injury rows without team/matchup text; 19 schedule-linked), 7C-F-09 (schedule 'subject to change'), 7C-F-11 (schedule marker legend unknown), 7C-F-12 (CDN scoreboard JSON HTTP 500), 7C-F-14 (branch naming in the brief conflicts with Arena branch policy), 7C-F-15 (two Pages deploy mechanisms; now a single workflow deploy), 7C-F-17 ('NOT YET SUBMITTED' team rows).
- No picks, lines, correlation values, ROI, or minutes effects were published. Nothing was inferred to fill a blank.

### Coordination notes

- Other sessions (f879620b, 49064d5a) published to `origin/main` while this branch was in progress. Their board rows, `docs/`, `tools/`, `tests/`, and their PR #3 and #4 history are preserved unchanged. Integration is a merge of `origin/main` (not a rebase), so their history stays intact.
- The prior session's board and published site (PR #1, #2) are preserved as history; this session replaces the single-page dashboard with the generated multi-page site.
- Shared outputs changed by this integration (T8 only): `pages.yml` (runs both test sets, builds site/, deploys `/`, `/docs/`, `/site/` as one artifact); `README.md` (combined; ID namespace table); `index.html` (one nav link to `site/index.html` added; all other content unchanged); `COORDINATION.md` (appended section only).

## Integration / PR status (T8)

- Branch: `arena/7c532e8c-nba3`. Integration method: merge of `origin/main` (b2efd23) into this branch; conflicts resolved as follows:
  - `COORDINATION.md`: f879620b's board kept unchanged; this section appended.
  - `pages.yml`: merged. Runs f879620b's unit tests and `tools/check_site.py`, the root-index link check, and this site's build with drift check; deploys `/`, `/docs/`, `/site/` as one artifact.
  - `README.md`: combined (both sites described; ID namespace table added).
  - `index.html`: f879620b's dashboard kept; one nav link to `site/index.html` added.
  - `docs/`, `tools/`, `tests/`: untouched.
- Cross-check against f879620b's data (`docs/data/data.json`): the 11/13–11/15 slate (teams and ET tip times) and the 11/16 ORL–BOS game agree with `data/schedule.json` for all rows they list. Their injury data is the 11/11 7:00 PM report, a different snapshot; it is not contradicted by the 11/13 5:00 PM report used here, and both are cited.
- Flag ID collision resolved: this site's flags are `7C-F-01…17`. f879620b's `F-01…F-15` are unchanged (see the README namespace table).
- Local checks at merge time: `python3 scripts/build_site.py` (OK, 553 links, 12 pages); `python3 tools/check_site.py` (PASS, 10 pages); `python3 -m unittest tests/test_validate_gates.py` (13 tests, OK).
- Pull request: https://github.com/wingbangboozle1-lang/NBA3/pull/5 (`arena/7c532e8c-nba3` -> `main`; head 33d09d4).
- Merge result: PR #5 merged with a merge commit (no review; not auto-merge) at 2026-11-13T22:37:15Z, merge commit `bccf9b7` on `main`.
- Deploy: workflow run 43520768394 (`Build and deploy NBA Edge Lab (GitHub Pages)`) on `bccf9b7`: build success, deploy success. Pages API: status `built`, latest build for `bccf9b7`. Public URLs checked with the fetch tool: `/site/` (landing, 31 games, 117 injury rows, 17 flags) and `/` (dashboard) load. The sandbox cannot reach the Pages host directly (curl fails at TLS).
- Pages configuration note: Pages `build_type` is `legacy`, source `main /`. The workflow deploy and the legacy build serve the same committed tree (`/`, `/docs/`, `/site/`). Switching to the workflow build type was not done (f879620b's attempt to change source returned 403). Owner decision: see suggestions.
- Open items, not blocking (unchanged from the verification log): 7 NOT YET SUBMITTED team rows vs 2 attribution-T rows (unreconciled); injury R/S/U rows not re-verified against the PDF; schedule orientation for 11/15 and 11/16 unverified (printed order kept); meaning of the schedule "C" column unknown.

---

## Session `arena/5697caaf-nba3` — line origination + validation, served at `lab/`

Merged into `main` after `arena/7c532e8c-nba3`. **No file from the two earlier sessions was
deleted or reverted.** Where my generator collided with `7c532e8c`'s `scripts/build_site.py`
and its `data/` + `site/` outputs, I moved my whole pipeline into `lab/` rather than
overwriting theirs. Both sites now build and both are in the Pages artifact.

| Task | Status | File scope |
|---|---|---|
| T1 Repo review of prior sessions | done | `docs/repo-review.md` |
| T2 Source capture + verbatim transcription | done | `scripts/raw_data.py` |
| T3 Line-origination model, measured constants, calibration | done | `scripts/model.py`, `lab/data/*.json` |
| T4 Props + correlation | **partial** — props priced/de-vigged; no prop model (no minutes source); 3 game-level correlations measured, 4 player-level ones unmeasured | `lab/props.html` |
| T5 Strategies, 7 gates, luck-adjusted leaderboard | done | `lab/strategies.html` |
| T6 Injuries / availability / market movement | done for statuses; minutes analysis not possible | `lab/injuries.html` |
| T7 Decision questions register | done | `lab/questions.html` |
| T8 Suggestions queue | done | `lab/suggestions.html` |
| T9 Flagged for review (IR-01…IR-17) | done | `lab/review.html` |
| T10 Executive summary | done | `lab/index.html`, `docs/executive-summary.md` |
| T11 Build + validation gate | done — `scripts/validate_site.py` green | `.github/workflows/pages.yml` |
| T12 PR, merge, deploy confirmation | recorded in the log below | this file |

### What this session added that did not exist

- **A measured-constants layer.** Home margin **+1.51** (95% CI −2.17…+5.19), margin sd
  **17.15**, total mean **225.98**, total sd **18.62**, home win rate **0.500** (43/86), all
  computed from 86 transcribed game results. The earlier placeholder `sd_margin = 12.4` was
  40% too small and produced overconfident cover probabilities.
- **Originated lines for all 23 games** in the 72-hour window, not just the priced ones.
- **De-vigging before any comparison**, so a 6% hold cannot present as edge.
- **A signal funnel.** 20 signals were generated; every one was positive-EV against a single
  book. That is published as evidence of a blind spot, not skill: 12 rejected for oversized
  divergence, 7 for injury exposure, **1 survives**.
- **Correlations with confidence intervals**, and an explicit list of the four that could not
  be measured.

### Divergences worth knowing about

- `7c532e8c` and `f879620b` both state the live season as 2026-27 and both record the
  2025-26 injury index as a defect. I found **three remaining 2025-26 links on the merged root
  `index.html`** and corrected them to the 2026-27 index, which I re-fetched and confirmed
  live. Their `data/`/`site/` copies of that URL are deliberate provenance records and were
  left alone.
- Their boards describe validation-gate work as "blocked, no values". This session supplies
  the first actual gate scores (best strategy 2/7, none eligible). The two descriptions are
  consistent: a gate that is *scored* is not a gate that is *passed*.
- No strategy in either session is eligible. Nothing here is a validated system.

## Correction notice — this session's own board

An earlier revision of *this session's* section (superseded by the merge above) marked
T1–T12 `done` before the work existed and described artefacts that were not in the
repository (`data/raw/`, "31 games across 4 slates", `scripts/build_all.py`). Its IR
numbering also disagreed with the review page. The table above records the true state, and
the review page is the canonical list. A board that reports completion is what the next
session trusts before deciding what to do; false completion is how duplicated work starts.

## Verification log — session `arena/5697caaf-nba3`

| Date | Task | What was verified | Method / result |
|---|---|---|---|
| 2026-11-13 | T2 | Team ratings, all 30 | `NetRtg == ORtg − DRtg` for 30/30. `SRS == MOV + SOS` for 30/30. Season W+L = 348 (174 games); W=174, L=174. |
| 2026-11-13 | T2 | 86 completed games (11-01 → 11-12) | No team's subset wins or losses exceed its season total → 0 violations. |
| 2026-11-13 | T2 | 23-game slate | Every row has an official `002…` id. Game `401909297` resolves to **MIL@ORL**; an earlier note in this session had it as ORL@WAS — corrected. |
| 2026-11-13 | T2 | 9 market snapshots | Each re-parsed and compared against the provider's own details string (favourite + line + both moneylines) → 9/9 consistent. This check found real sign transpositions, now fixed. |
| 2026-11-13 | T2 | 75 injury statuses | Official dated PDF (11/13/26 05:00 PM) via the **2026-27** index. |
| 2026-11-13 | T2 | 5 prop athlete identities | ESPN per-athlete endpoint: Towns, Oubre Jr., Hart, Bridges, Drummond. Flagged: four of five resolve to team 18 (NYK) while one prop row is labelled PHI → `lab/review.html` IR-07. |
| 2026-11-13 | T3 | Constants | Measured from 86 games (values above). Published beside the assumptions they replaced. |
| 2026-11-13 | T3 | Sign convention | Tested against a known answer: pick'em must give p = 0.50. An earlier version used the handicap where the margin belonged and produced 49-point "edges" — caught and fixed. `validate_site.py` now asserts `model_spread_home == -model_margin_home` on every row. |
| 2026-11-13 | T3 | Calibration | Brier 0.1528 vs 0.25 baseline. **In-sample, disclosed.** Luck test 43 observed vs 46.2 expected, z = −0.79, p = 0.4294. |
| 2026-11-13 | T4 | Correlation | Away vs home total r = 0.082 (−0.132…0.289); margin vs total r = 0.005 (−0.207…0.217); pooled within-team r = 0.049 (29 teams). Player-level: **not measured**. |
| 2026-11-13 | T5 | Gates | 7 gates × 6 strategies. Best 2/7. G2 and G6 fail universally — no historical price archive. S6 blocked at 0/7. |
| 2026-11-13 | T11 | Build gate | `scripts/validate_site.py`: internal links, per-data-row sources, unverified-cell-cannot-carry-a-number, `spread == −margin`, probability ranges and sums, correlation-without-n, prop-probability-without-model, pick-passed-screening-with-high-injury-risk, IR-citation resolution, stale-content detection. **Passes.** |
| 2026-11-13 | T11 | Third-party systems intact | `python3 tools/check_site.py` (f879620b) still passes: 10 pages, 77 injury rows, 24 slate rows. `scripts/build_site.py` (7c532e8c) still builds `site/` unchanged. |

### Irregularities added by this session

Canonical list is `lab/review.html`, IR-01 … IR-17. New in this session: **IR-16** one prop
price (Drummond under, `+111`) is out of family with the rest of the card and was transcribed
as published rather than normalised; **IR-17** Mikal Bridges' printed 5.9 ppg is implausible
for a starter and uncorroborated, so the average is withheld rather than published.

### Build record

```
python3 scripts/model.py         # -> lab/data/*.json
python3 scripts/build_lab.py     # -> lab/*.html
python3 scripts/validate_site.py # gate; must exit 0
```

Pages artifact layout: `/` (7c532e8c dashboard) · `/docs/` (f879620b data site) ·
`/site/` (7c532e8c generated site) · `/lab/` (this session's line lab).

## Deployment record — session `arena/5697caaf-nba3`

| Item | Result |
|---|---|
| PR | **#8** — https://github.com/wingbangboozle1-lang/NBA3/pull/8 |
| State | **MERGED** 2026-11-13T22:43:46Z |
| Merge commit | `2b9c3dab3f4ce7f48b7e34409e1379a5690986e8` |
| CI run | `Build and deploy NBA Edge Lab (GitHub Pages)` — **completed success** |
| Pages run | `pages-build-deployment` — **completed success** |
| Live check | `/lab/index.html` and `/lab/review.html` fetched and rendering; nav, tables, chips and source links all resolve |

Pages artifact after this merge serves four sites, all verified live:

| Path | Owner session | Content |
|---|---|---|
| `/` | `arena/7c532e8c-nba3` | Research dashboard (2025-26 injury links corrected to 2026-27) |
| `/docs/` | `arena/f879620b-nba3` | Data site and sources |
| `/site/` | `arena/7c532e8c-nba3` | Generated site from `data/*.json` |
| `/lab/` | `arena/5697caaf-nba3` | Line lab: originated lines, screening, gates |

T11 and T12 are now marked **done** — only after the run was observed green and the live URL
was fetched, not when the PR was opened.
