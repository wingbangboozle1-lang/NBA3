# Round 2026-11-19 · session `arena/dd3edd74-nba3` (tasks D1, D2)

Scope: the scheduled-refresh diagnosis (D1) and the official per-game finals for the three most
recent completed game dates (D2). Nothing here is a pick, a line, a model input, or a settlement of
the sealed pick ledger. The canonical site and canonical results feed were **not** edited; see the
change requests in `COORDINATION.md` (CR-DD3-01).

## D2 — official finals, 2026-11-16 → 2026-11-18

Artefact: `results_2026-11-16_18.json` (25 rows, one per game). Written by
`scripts/capture_dd3edd74.py`; re-verified offline with `python3 scripts/capture_dd3edd74.py --check`
and `python3 -m unittest tests/test_dd3edd74.py` (12 tests).

| Date | Games | Source (official) | Quarter scores |
|---|---|---|---|
| 2026-11-16 | 8 | <https://www.nba.com/games?date=2026-11-16> | not captured (flag) |
| 2026-11-17 | 5 | <https://www.nba.com/games?date=2026-11-17> | not captured (flag) |
| 2026-11-18 | 12 | <https://www.nba.com/games?date=2026-11-18> | not captured (flag) |

Checks (all PASS on the committed artefact):

- Game count per date equals the calendar cell printed on each date page (8 / 5 / 12).
- Every game id, date, away and home team matches `data/app/official_slate_current.json`.
- Each game's recap-video link (`nba.com/watch/video/game-recap-…`) repeats the two final scores
  printed in the score table, with the winner's score first (24 of 25 games; the one without is flagged F-DD3-03).
- The 12 games of 11/18 match, score for score, the independent capture already on the board
  (`data/rounds/2026-11-19/results_2026-11-18.json`, `b1ce1334`).
- No quarter value is stored; every `quarter_scores` field is `null` with a flag.

Settlement rule used (stated in the artefact): a game is settled only when its final score is read
from the official date page; quarter scores are stored only when read from an official page.
Settled rows carry a settlement stamp saying quarter scores were not captured.

### Flags for review (published on the Flagged page via the integration owner)

- **F-DD3-01** Quarter scores are not captured for the 25 games (null, not estimated). The date pages
  print no period table; each game page costs about three fetch chunks, so this was not done in this
  round. Next step: read each official game page's linescore (or the statsdmz game book) and fill
  the field only from that read.
- **F-DD3-02** CHA @ LAL on 11/17 is printed `Final/OT` (114–118). The overtime period is not itemised.
- **F-DD3-03** UTA @ LAL on 11/18 (109–97): the recap line was not printed in the read, so this row
  rests on the score table plus the independent 11/18 capture only. The other 24 rows have a recap
  line that repeats the score.
- **F-DD3-04** POR and MIN meet on 11/16 (game `0022600250`, POR 98 – MIN 106) and again on 11/17
  (game `0022600254`, POR 105 – MIN 106). Both are printed on the official pages and both recap lines
  agree. Recorded as printed; flagged only because back-to-back meetings are unusual.
- **F-DD3-05** The fetch tool returns no per-call timestamp. The retrieval window in the artefact is
  bounded by the session clock (2026-11-19 06:55Z–07:40Z UTC) and is labelled approximate.
- **F-DD3-06** This round does not settle the sealed pick ledger. No pick is in scope here.

## D1 — scheduled refresh: what is known about the red runs

**Hosted evidence (GitHub Actions API, read by this session):**

- Latest scheduled run on `main`: run `44469939831`, created 2026-11-19T06:07:59Z, head `5ad832a`,
  conclusion `failure`. Job `refresh` failed at step *Unit tests against the committed tree*; every
  later step after it, including the live fetch, was skipped.
- The run's annotations name the one failing test:
  `test_committed_round_captures_replay_before_the_live_fetch` (`tests.test_refresh_official.WorkflowGateTests`),
  script `gamebooks_2ecbccfd.py`. Its failure body is not in the annotations.
- The run's log artefact `unit-test-logs-44469939831` (10,894 bytes) is listed but its download fails
  from this sandbox (`productionresultssa… EOF`), the same blob-storage failure earlier sessions recorded.

**Reproduction attempts (all green):**

| Setting | Result |
|---|---|
| Local tree at `main` 454a7ee, Python 3.11.2, full unit-suite and the nine-suite loop | 315 tests OK; the three `--check` scripts rc 0 |
| Worktree at the failing commit `5ad832a`, same commands | rc 0; `test_refresh_official.py` 27 tests OK |
| Fresh depth-1 clone of `main` (the runner's checkout depth) | rc 0 |
| `LANG=C LC_ALL=C.ASCII`, `-X utf8=0` | rc 0 |
| `gamebooks --check` under 40 `PYTHONHASHSEED` values | 40/40 rc 0 |
| Python 3.12 (the runner's default `python3`) | **not reproduced**: no 3.12 interpreter could be installed (TLS interception on the GitHub release download) |

**What changed (diagnosability only; no gate weakened, no test skipped, step order unchanged):**

- `scripts/gamebooks_2ecbccfd.py --check`: on a mismatch it prints the first differing line of the
  committed artefact and of the regenerated output. Its exit codes are unchanged (0 pass, 1 fail).
  Verified on a scratch copy with one planted character: rc 1 and the line named.
- `.github/workflows/refresh.yml`, unit step only: on a red suite the assertion text and any `--check`
  reason are also emitted as `::error::` annotations, so the next red run names its cause through the
  API without the blob. Verified by executing the step itself on a full-tree copy: clean rc 0; with
  the planted difference rc 1 and the `why:` annotation printed.

**Still open:** the hosted root cause. The next scheduled run (11:15 UTC or later) will show the
annotated reason if the same check still fails. If the failure moves to another suite, its annotations
show that too. EVE-F04 stays `needs review`.

**Stale data, stated plainly:** the canonical slate on the site covers 11/15–11/18, the canonical
injury snapshot is 11/16, and the canonical results feed ends at 11/15. This round does not refresh
those; it adds the three finals dates as a separate, flagged artefact.
