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

## Session 9ed6085f — claim for this round (branch `arena/9ed6085f-nba3`)

Session ID: `9ed6085f` (branch `arena/9ed6085f-nba3`, based on `origin/main` @ `dbb8575`).
Constraint noted: this workspace is bound to one branch, so the `session-<id>/<task>` branch-per-task scheme is not used. Scopes below are therefore enforced within this single branch and recorded here instead.
Prior session `49064d5a` work (merged PRs #1 and #2) is preserved; its `index.html` is superseded by the generated multi-page site (see log).

| Task | Status | Owner | File scope |
|---|---|---|---|
| T1 Repository review, line by line, with official links and irregularities | done | 9ed6085f | data/repo_review.csv (R01-R17) |
| T2 Official source registry and retrieval log | done | 9ed6085f | data/sources.csv (S01-S19) |
| T3 Requirements, questions and answers, suggestions queue | done (suggestions awaiting owner review) | 9ed6085f | data/requirements.csv (RQ01-RQ23), data/questions.csv (18), data/suggestions.csv (SG-01-SG-14) |
| T4 Upcoming slates (Nov 13-16, 2026, ET) from the official NBA schedule | done | 9ed6085f | data/slates.csv (31 games) |
| T5 Official injury snapshot, rotation method, game-flow factors | done (snapshot re-verified; newer report not transcribed, F01) | 9ed6085f | data/injuries_2026-11-13_1100AM.csv (98 rows), data/gameflow.csv, pipeline/rotation.py |
| T6 Strategies, validation gates, correlations (leaderboard empty; all blocked) | done (blocked by data) | 9ed6085f | data/strategies.csv (11), data/gates.csv (11), data/correlations.csv (8, blank), pipeline/gates.py |
| T7 Site generator, verification checker, Pages workflow | done (narrowed; see note) | 9ed6085f | pipeline/build_site.py, pipeline/verify.py, pipeline/tests/, .github/workflows/pages.yml (now checks only), index.html (generated dashboard), root *.html and style.css (generated), .nojekyll, .gitignore, README.md |
| T8 Executive summary and Flagged-for-Review register | done (25 flags) | 9ed6085f | data/flags.csv, generated site pages |
| T9 PR, merge, Pages deploy verification, log | in progress (PR #7 open; merge with main recorded below) | 9ed6085f | COORDINATION.md; PR and merge result recorded below |

### T7 scope note (narrowed)

T7 originally covered the prior session's `index.html` and `pages.yml`. In this round:
- `pages.yml` was replaced. It now runs the unit tests, rebuilds the pages, runs verify.py, and fails if the committed pages are stale. It has no deploy job.
- Pages is published from `main /` (legacy source). Switching it to GitHub Actions failed: `gh api -X PUT repos/.../pages -f build_type=workflow` returned 403 (Resource not accessible by integration). Actions permissions also returned 403. The session token cannot change Pages settings, so the generated pages are committed at the repository root.
- Because the legacy source serves the whole repository, the prior exposure (R06) remains until the owner switches the source (F19, Q-REPO-02). The workflow no longer uploads the repository itself.
- `index.html` is now the generated dashboard. The prior dashboard content is superseded, and its injury link (2025-26 slug, F06) is removed.
- Owner choice on the Pages source and the site suggestions is SG-08.

### Verification log (this round)

- Injury snapshot 11/13/26 11:00 AM ET: re-read PDF chunks 0 and 1 of 2. Every row was compared with the PDF text by hand (visual comparison, not an automated diff). No mismatch was found other than the reason fixed below. The Simmons, Ben reason was joined across the chunk break ("Right Achille" + "s Tendon Repair / Surgery"). Team and matchup cells absent in the PDF text are blank with flags (F02, F03, F04, F07, F10, F11). F10 was added to 10 rows with no game date, to meet the flag rule.
- Schedule nba.com/schedule: chunks 0 to 2 of 9 read. Nov 13 = 9 games, Nov 14 = 5, Nov 15 = 9, Nov 16 = 8 (31). Every game ID, preview URL, venue and city in data/slates.csv matches the page. S05 partial-read flag closed.
- Terms of Use: s.19 read (New York law; New York County courts). Page last updated July 13, 2026. F23 closed.
- NIST: 7.2.4, 7.2.7.1 and 1.3.3.4 read directly. The DOI cited in an earlier draft was not read on any page and has been removed. No NIST permutation page was located; permutation is not cited as a method on the site.
- CSV integrity: 3 malformed rows fixed (unquoted commas in R16, SG-10, and strategies ST04/ST08). questions.csv, requirements.csv, sources.csv and gates.csv rewritten with csv.writer.
- Unit tests: 29 tests pass (gates, rotation, verify rules).
- verify.py: passes on the built site. It checks every table row for an allowed-host source link, every internal link, and every blank cell for an unverified marker.

### Irregularities found this round (all on flags.csv; none blocks merge)

- F01 newer injury reports exist for 11/13; only the 11:00 AM report is transcribed.
- F02/F03/F04/F07/F10/F11 PDF extraction gaps (team, matchup, time, reason, Miami row on DET@MIA).
- F12 NBA Terms s.9 and s.1 against publishing NBA content and gambling-related use.
- F13 Dutch promotion rules (Art. 1 of the Wet op de kansspelen) against publishing picks.
- F16 minimum online age not verified; not published.
- F18 no licence; F19 Pages source change; F25 unmerged arena branches.

Integration: this session is the only writer for shared outputs (site and index/navigation). No other session has an open claim on these files.


### Integration with main (this session, 9ed6085f)

- `main` moved from `dbb8575` to `df712ec` during this session (PRs #3, #4, #5, #6 from other sessions). PR #7 conflicted, so `origin/main` was merged into `arena/9ed6085f-nba3` and both sides were kept.
- Conflicts resolved: `index.html` kept as main's dashboard, with one navigation link added to `research/`. `.gitignore` kept as main's. `README.md` and `COORDINATION.md` kept as main's, with this session's section appended. `.github/workflows/pages.yml` kept every step of main's workflow, added the research build and verify steps, added a pull-request trigger (checks only, no deploy), and restricted the deploy job to pushes to `main`.
- Research site location: `research/` (not the repository root and not `site/`, which main's arena/7c532e8c build owns). Published at `/research/`.
- Pages source remains `main /` (legacy). The source switch to GitHub Actions returned 403 for this session, as it did for f879620b (T10 log), so the existing `/docs/`, `/site/` and root pages keep serving from `main /`.

### Cross-session irregularities found in this integration (logged for the owners; not edited here)

- **For arena/7c532e8c (owns `data/injuries.json`):** the Miami Heat rows in the 5:00 PM report (Antetokounmpo, Larsson, Thompson, Goldin) carry `matchup: CLE@MIA`. The PDF text shows no matchup cell on those rows; the matchup is blank in the PDF extraction. The value appears to come from the row position above, which the rule against inference forbids. A DET@MIA row also carries an empty player name. Owner action: blank the matchup, or source it from the schedule with a note.
- **For arena/7c532e8c:** the 5:00 PM report's Miami and team-status rows should be checked for the same blank-matchup issue. This session compared 9 player rows with the PDF text (Suggs, Antetokounmpo, Larsson, Thompson, Dia, Murray, Curry, Porzingis, Achiuwa). Their statuses and reasons matched. Other rows were not compared.
- **For arena/9ed6085f (this session):** the 11:00 AM file had "Suggs, Jalan" for "Suggs, Jalen". Fixed.

### Verification (integration, this session)

- `python3 -m unittest tests/test_validate_gates.py` (f879620b): OK.
- `python3 tools/check_site.py` (f879620b): PASS (10 pages, 77 injury rows, 24 slate rows, 10 rule rows, 9 sources).
- `python3 scripts/build_site.py` (arena/7c532e8c): validated 117 injury rows, 31 games, 11 sources; checked 553 links across 12 pages; no drift in `site/`.
- `python3 -m unittest discover -s pipeline/tests` (9ed6085f): OK (29 tests).
- `python3 pipeline/build_site.py && python3 pipeline/verify.py` (9ed6085f): VERIFY OK.
- Root `index.html` in-page and local link check: 17 links, 0 broken.
