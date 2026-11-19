# Runner probe — committed-tree preflight replayed on the runner's default python3

Session 89e98007. Run 44478152590, commit 78422bd12f6b5a6a6d2598988f03eefdc48a61b9. Read-only.

```
PY=3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]
EXEC=/usr/bin/python3
UTC=2026-11-19T07:15:07Z
--- inputs the artefacts derive from (a source movement shows here, not as a rounding story) ---
SHA data/live/team_registry.json=150154023aca74d3
SHA data/rounds/2026-11-17/captures/gamebook_2026-11-15_DALBOS.md=4a0e62f734dc596a
SHA data/rounds/2026-11-17/captures/gamebook_2026-11-15_HOUWAS.md=a9e49f488d548293
SHA data/rounds/2026-11-17/captures/gamebook_2026-11-15_INDPHI.md=d312c1b865bc07cb
SHA data/rounds/2026-11-17/captures/gamebook_2026-11-15_LALPHX.md=054ceb431e3433d8
SHA data/rounds/2026-11-17/player_logs_2026-11-15.json=193eef131f4f00eb
--- the field that moved, recomputed from the transcripts on THIS interpreter ---
FIELD_player=Trae Young
COMMITTED_share=0.1088
FIELD_minutes=Trae Young = 26.10000000000000142108547152020037174224853515625
SUM fold (CPython <= 3.11 sum)=239.999999999999971578290569595992565155029296875 -> share 0.1088
SUM fsum (CPython >= 3.12 sum)=240 -> share 0.1087
VERDICT=the committed artefact is the pre-3.12 fold; a compensated sum would repaint it 0.1088 -> 0.1087; det.fold pins the published rule so any interpreter reproduces the bytes
--- every committed-tree gate the refresh replays ---
CHECK scripts/capture_2ecbccfd.py=rc=0 standings rows      : 30 (problems 0) | log games           : 197  home wins 102 (51.78%) | reconciliation      : 30/30 clubs, sum GP 394 == 2 x 197 -> True | i
CHECK scripts/gamebooks_2ecbccfd.py=rc=0 
CHECK scripts/slate_extra_2ecbccfd.py=rc=0 
CHECK scripts/model_2ecbccfd.py=rc=0 model.json matches the committed artefact
CHECK scripts/ledger_2ecbccfd.py=rc=0 ledger OK: 114 entries, head b87ddff22b1fee1b...
CHECK round_2ecbccfd/build.py=rc=0 12/12 pages match the committed build — links OK
GIT_DIRTY_files_after_replay=1
PROBE RESULT=PASS
probe rc=0
--- the refresh workflow's exact committed-tree suite loop ---
SUITE test_*1115*.py rc=0 Ran 33 tests in 0.196s OK 
SUITE test_results_feed.py rc=0 Ran 3 tests in 0.003s OK 
SUITE test_pick_ledger.py rc=0 Ran 12 tests in 0.025s OK 
SUITE test_freshness_gates.py rc=0 Ran 5 tests in 0.010s OK 
SUITE test_refresh_official.py rc=0 Ran 28 tests in 0.194s OK 
SUITE test_results_feed_rows.py rc=0 Ran 7 tests in 0.003s OK 
SUITE test_gamecard_feed.py rc=0 Ran 5 tests in 0.007s OK 
SUITE test_standings_feed.py rc=0 Ran 5 tests in 0.004s OK 
SUITE test_round_2ecbccfd.py rc=0 Ran 38 tests in 0.118s OK 
SUITE_LOOP_FAIL=0
--- this session's determinism suite ---
DETERMINISM rc=1 Ran 1 test in 0.000s FAILED (errors=1) 
ERROR: tests/test_determinism_89e98007 (unittest.loader._FailedTest.tests/test_determinism_89e98007)
--- nothing in the tree may change by replaying the build ---
 M data/app/minutes_shares.json
?? data/rounds/2026-11-19-89e98007/
DIRTY=2
```
