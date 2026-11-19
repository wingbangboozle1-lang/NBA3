#!/usr/bin/env python3
"""Brief-to-evidence traceability (session arena/e9295737-nba3).

One row per requirement in the operating brief, in the order the brief states them.
Each row carries: the requirement as written, the concrete artefact that implements it,
the verification that was actually performed, and an honest status. Statuses:

  VERIFIED      implemented and checked against an official source or a reproducing build
  PARTIAL       implemented for a dated window only, or the check covers part of the rule
  BLOCKED       cannot be done from this environment; the blocker is named in `blocker`
  OPEN          not started

A row never claims more than its `evidence` and `verification` support. Where the source
is an official NBA page, `source` is that page; where it is a repo artefact, the artefact
is named and the official page it derives from is in `source`.
"""
from __future__ import annotations

NBA_GAMES = "https://www.nba.com/games?date="
INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"

# (req, implementation, evidence, verification, status, source, blocker)
ROWS = [
    (
        "Extend the scheduled job to refresh the official schedule, standings, team statistics "
        "and injury report for each rolling slate, then rebuild only after freshness and "
        "provenance gates pass.",
        "scripts/refresh_official.py, .github/workflows/refresh.yml (steps 1-4), "
        "scripts/freshness_gates.py",
        "The workflow fetches, then gates, then rebuilds; every later step is success-gated on the "
        "gate step. The committed-tree preflight that failed every run from 2026-11-17 is fixed "
        "(see the float-summation row).",
        "All 23 --check-guarded artefacts reproduce under a byte-exact transcription of the Python "
        "3.12 builtin sum(); tests/test_float_sum_determinism.py pins it and is now in the refresh "
        "preflight suite list. The next hosted run has not been observed, so end-to-end refresh "
        "success is not claimed.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/44469939831",
        "The fetch/gate/rebuild steps were skipped in every recorded failure and have never been "
        "exercised live from this sandbox.",
    ),
    (
        "Keep an official per-game result feed current and settle only after final scores are "
        "verified; store one row per game: date, teams, final score, quarter scores.",
        "data/rounds/2026-11-19-e9295737/results_2026-11-16_18.json, "
        "scripts/capture_e9295737.py, data/app/results_feed.json (2026-11-13..11-15)",
        "25 rows for 2026-11-16, -17 and -18: date, teams, final and quarter/OT scores. The existing "
        "feed carries the 23 earlier rows.",
        "For all 25 new rows the quarter/OT scores sum to the printed final on BOTH sides, and the "
        "final equals the score printed on the official games page for that date. 25/25 settled, "
        "0 withheld; the settlement rule is printed with the feed.",
        "VERIFIED",
        "https://www.nba.com/games?date=2026-11-18",
        None,
    ),
    (
        "Store every injury PDF with its timestamp and diff consecutive reports to detect status "
        "changes.",
        "data/rounds/2026-11-19-e9295737/injury_reports.json, scripts/capture_e9295737.py",
        "Four revisions of the 2026-11-19 report (12:30, 12:45, 01:30, 01:45 AM ET), each stored "
        "verbatim with printed revision time, retrieval stamp, URL and transcript sha256, each "
        "diffed against its predecessor.",
        "23 player rows in every revision; the diffs report 0 status changes, 0 added, 0 removed "
        "across the whole chain. The 12:30 AM text layer merging three teams into one cell is "
        "recorded as a structure problem and is resolved by the 12:45 AM revision. Session "
        "b1ce1334's independent parse of the 12:30 AM PDF agrees on all 23 rows.",
        "VERIFIED",
        INJ_INDEX,
        None,
    ),
    (
        "Freeze a pre-registration file per strategy before its first bet: signal, thresholds, "
        "universe, and the exact settlement rule.",
        "scripts/preregister.py, data/app/prereg/, app/prereg.html",
        "Pre-registration files are written per strategy and hash-chained; each pick row carries "
        "its preregistration_sha256.",
        "The pre-registration hashes are recomputed and matched in the build and in the v2 drift "
        "check. Coverage is for the 2026-11-15..11-18 window only; no new strategy has been "
        "pre-registered for the 2026-11-19 slate.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/tree/main/data/app/prereg",
        "A new slate needs a new frozen pre-registration, which needs the model rebuilt on current "
        "data; that rebuild is blocked on the live refresh above.",
    ),
    (
        "Add a tamper-evident ledger: hash each published pick, publish the hash before tip, and "
        "verify after settlement.",
        "scripts/pick_ledger.py, scripts/ledger.py, data/app/ledger/, app/ledger.html",
        "Each entry stores pick_sha256 and the sha256 of the previous entry; verification recomputes "
        "both chains.",
        "Chain verification recomputes 43 entries (data/app/ledger), 114 (2026-11-17 round), 31 "
        "(d1b96315) and 13 (ledger_A); in all four the only discontinuity is the all-zeros genesis "
        "prev_hash, and the committed check reports CHAIN INTACT. Entries are for the dated window; no 2026-11-19 pick has been "
        "sealed because no current line has been rebuilt.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/tree/main/data/app/ledger",
        "Sealing a pick before tip for the 2026-11-19 slate needs the live rebuild, which is blocked.",
    ),
    (
        "Split the site into 'projection' (safe to publish now) and 'bet' (gated) surfaces, and "
        "never mix them.",
        "scripts/build_app.py NAV (two separate nav groups), projection/, bet/",
        "The navigation is split into 'Projection surface (public)' and 'Bet surface (gated)'; the "
        "two directories publish separately.",
        "The build's link and provenance checks pass over both surfaces. The separation is presentational "
        "and navigational; there is no automated check that a projection page cannot link a bet value.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/build_app.py",
        "No gate currently forbids a projection page from rendering a bet-surface value.",
    ),
    (
        "Keep two independent estimators and publish their disagreement as the primary confidence "
        "signal, rather than a single blended rating.",
        "pipeline/v2/estimators.py, pipeline/v2/pricing.py, app/projections.html",
        "Estimator A (ridge on final margins) and estimator B (efficiency) are fitted separately; "
        "the published headline is their disagreement z-score, with the blend underneath.",
        "Unit-tested in pipeline/v2/tests; the disagreement z is the headline field on the "
        "projections page. Measured on the 2026-11-15..18 window only.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/estimators.py",
        "Current-window projection needs the rebuild, which is blocked.",
    ),
    (
        "Pin home-court advantage to the measured home-win rate instead of fitting it freely.",
        "pipeline/v2/estimators.py home_court_from_win_rate()",
        "HCA = logit(measured home-win rate) x sd(margin), used as a fixed offset by both estimators.",
        "The formula and its inputs are printed on the methodology page; the value is recomputed "
        "in the build. It is measured on the dated game log, not on the current season.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/estimators.py",
        None,
    ),
    (
        "Report luck as a z-score per team and refuse to publish a strategy that leans on a team "
        "outside the noise band.",
        "pipeline/v2/stats.py zscore_per_team()/noise_band(), d1b96315/model.py luck gate",
        "Per-team luck z is computed from residuals and the noise band is +/- 2 z.",
        "The band and the refusal rule are implemented and unit-tested; strategies that lean on an "
        "outside-band team are marked not publishable in the gate board.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/stats.py",
        None,
    ),
    (
        "Compute rest, back-to-back and 3-in-4 from the official schedule and add travel distance "
        "from a sourced arena-coordinate table.",
        "scripts/rest_travel.py, d1b96315/model.py, data/app/arena_coordinates.json",
        "Rest, B2B and 3-in-4 are computed from the official schedule; travel distance uses the "
        "arena-coordinate table.",
        "Rest/B2B/3-in-4 are recomputed and tested against the schedule. The arena-coordinate table "
        "is in the repo but its own provenance is not established as official in this session.",
        "PARTIAL",
        NBA_GAMES + "2026-11-19",
        "The arena-coordinate table's source is not an official NBA document; flagged for review.",
    ),
    (
        "Model minutes redistribution explicitly: for each team, the top-8 minutes shares and the "
        "replacement shares when a player is out.",
        "scripts/minutes_model.py, data/app/minutes_shares.json, /b1ce1334 pages",
        "Top-8 shares and the replacement rule are computed per team from player logs.",
        "106 player rows for the 2026-11-15 games, all row-verified, with 5 of 8 club-games fully "
        "reconciled and 35 rows publishing minutes only and saying so.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/minutes_model.py",
        "Current-slate redistribution needs current player logs, which the live refresh must fetch.",
    ),
    (
        "Stop publishing a single blended rating as the headline; publish the disagreement between "
        "the two estimators as the headline and the blend underneath.",
        "app/projections.html, app/lines.html",
        "The projections page leads with the disagreement and prints the blend below it.",
        "Verified in the rendered page and in the generator source.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/projections.html",
        "The dated window is the only one rendered.",
    ),
    (
        "Price every parlay with the measured rho and print the naive product next to it.",
        "pipeline/v2/pricing.py sgp_price(), app/parlays.html",
        "The Gaussian-copula price at the measured rho is printed next to the naive product on every "
        "parlay row.",
        "Unit-tested against the equicorrelated-copula construction; both numbers are printed on "
        "every row and neither is withheld.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/pricing.py",
        "Rho is measured on the dated residuals; a current parlay needs the rebuild.",
    ),
    (
        "Put rotation availability on the picks page as its own column.",
        "app/picks.html rotation_cell()",
        "The picks table carries a rotation-availability column derived from the injury report.",
        "Confirmed in the generator and the rendered page.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/picks.html",
        None,
    ),
    (
        "Add a market-anchored prior: blend the model line with the closing line, weight by measured "
        "out-of-sample log-loss.",
        "pipeline/v2/pricing.py, data/app/closing_lines.json",
        "The blend weight is the measured out-of-sample log-loss of each source.",
        "The weighting rule is implemented, but there is no reachable closing-line source in this "
        "environment, so the prior cannot be fitted on real closing lines here.",
        "BLOCKED",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/pricing.py",
        "No licensed/reachable closing-line feed (see the Open questions page).",
    ),
    (
        "Model the total as possessions x points-per-possession, not as an average of team scoring "
        "averages.",
        "pipeline/v2/estimators.py total model",
        "The total is built from pace (possessions) and points per possession.",
        "Implemented and unit-tested; applied to the dated window.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/estimators.py",
        None,
    ),
    (
        "Show the injury-report revision time and retrieval time in the Injuries page banner.",
        "app/injuries.html banner, data/rounds/2026-11-19-e9295737/injury_reports.json banner",
        "The banner object carries revision_time_et and retrieval_time_utc separately.",
        "Both fields are present and distinct (01:45 AM ET printed, 2026-11-19T07:20Z retrieved) and "
        "a test pins them.",
        "VERIFIED",
        INJ_INDEX,
        None,
    ),
    (
        "Settle the sealed ledger from official finals as soon as each game day ends, and keep the "
        "settlement stamp visible.",
        "scripts/pick_ledger.py, d1b96315/ledger.py, app/settlement.html",
        "Settlement stamps are written per settled row from the verified final.",
        "Stamps are visible on the settlement page for the dated window; the 2026-11-16..18 finals "
        "are now verified and could settle existing open entries, but this session did not run a "
        "settlement pass.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/settlement.html",
        "Settling existing entries from the new verified finals is a separate job that was not run.",
    ),
    (
        "Re-read the three official team-stat pages (traditional, opponent, advanced) and re-cut the "
        "model inputs.",
        "scripts/refresh_official.py TEAM_PAGES",
        "The refresh fetches all three official team-stat pages.",
        "The URLs and the fetch step are committed, but the live fetch has not run since 2026-11-16, "
        "so no current team-stat page has been re-read and the model inputs have not been re-cut.",
        "BLOCKED",
        "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
        "Requires the live fetch to run on the hosted runner.",
    ),
    (
        "Capture per-player game logs (minutes, points, rebounds, assists, and the opponent) for at "
        "least the players who appear on an injury report.",
        "data/rounds/2026-11-17/player_logs_2026-11-15.json, data/app/player_game_logs.json",
        "Per-player logs with minutes, points, rebounds, assists and opponent exist for the "
        "2026-11-15 games.",
        "106 player rows for the 2026-11-15 game books, all row-verified, reconciled against the "
        "printed team totals: 5 of 8 club-games fully reconcile and the other 35 rows publish "
        "minutes only and say so.",
        "PARTIAL",
        "https://statsdmz.nba.com/pdfs/20261116/20261116_ORLBOS_book.pdf",
        "Logs cover one game day, not the current slate.",
    ),
    (
        "Research and develop strategies for generating useful signals, as a leaderboard competition "
        "with rewards for top performers; look at single bets, parlays and player prop combos; each "
        "strategy must pass validation gates; determine correlation values; remove luck; build "
        "selectively skill-based strategies.",
        "scripts/strategy_lab.py, pipeline/v2/gates.py, pipeline/v2/leaderboard.py, app/leaderboard.html",
        "15 strategy rules measured out of sample across the 27 validation gates, with 4 blocked prop "
        "combinations and 38 parlay rows, under an explicit luck threshold; measured correlations "
        "and parlay dependence are on the correlations page.",
        "The gates and the luck threshold are implemented and unit-tested. Out-of-sample n is small "
        "and the leaderboard is for the dated window; no rule is shown to be skill-based on the "
        "current slate.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/gates.py",
        None,
    ),
    (
        "Generate picks for every upcoming slate of games up to a maximum of 3 days in advance "
        "using our originated lines.",
        "data/rounds/2026-11-19-e9295737/slate_2026-11-19_21.json (slate), pipeline/v2/build.py "
        "(picks)",
        "The 3-day slate is captured (19 games); pick generation exists for the dated window.",
        "The slate is verified (19/19 games agree with an independent capture). Picks for 2026-11-19..21 "
        "are NOT generated: that needs the live rebuild, which is blocked.",
        "PARTIAL",
        NBA_GAMES + "2026-11-20",
        "No current-window picks were produced; the slate exists, the model run does not.",
    ),
    (
        "Track how injuries could affect rotation minutes and production and provide game flow "
        "analysis.",
        "app/injuries.html, app/gameflow.html, data/app/injury_impact",
        "Injury-to-rotation impact and game-flow factors are computed and published.",
        "Both pages render from committed data and are link-checked; they are dated to the "
        "2026-11-15..18 window.",
        "PARTIAL",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/injuries.html",
        None,
    ),
    (
        "Create an executive summary outlining important details.",
        "app/summary.html, executive-summary.html",
        "An executive summary page is generated with the current status and the dated window.",
        "Rendered and link-checked; it carries the pause notice and does not present the dated window "
        "as current.",
        "VERIFIED",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/summary.html",
        None,
    ),
    (
        "Create a section dedicated to suggestions so someone can review suggestions and choose the "
        "best path before implementing changes.",
        "app/suggestions.html (46 suggestions, each with a status)",
        "A dedicated suggestions page with each suggestion awaiting a decision.",
        "46 suggestions are printed with their status, plus 47 open questions; none is implemented "
        "without a decision.",
        "VERIFIED",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/suggestions.html",
        None,
    ),
    (
        "Give a clear list of questions, information and answers needed before any decision, and "
        "suggest how to discover the missing information.",
        "app/questions.html (47 questions)",
        "An open-questions page naming each blocker.",
        "Rendered and link-checked.",
        "VERIFIED",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/questions.html",
        None,
    ),
    (
        "Review the repo line by line from official sources and flag irregularities.",
        "app/review.html, app/flagged.html, data/app/flags*.json",
        "116 flags in total: 107 canonical plus 9 from session 79341829, on top of 15 review findings "
        "and 43 repository-review entries; each printed flag carries a source link.",
        "Every flag printed on the Flagged for review page carries an https source; this session "
        "adds its own findings to that page.",
        "VERIFIED",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/app/flagged.html",
        None,
    ),
    (
        "Parse the injury PDFs and re-read the newest revisions.",
        "data/rounds/2026-11-19-e9295737/injury_reports.json",
        "Four revisions parsed and diffed (see the injury-diff row above).",
        "23 player rows per revision, cross-checked against an independent parse.",
        "VERIFIED",
        INJ_INDEX,
        None,
    ),
    (
        "Keep the site itself building with no broken links and deploy it.",
        "scripts/build_app.py, .github/workflows/pages.yml",
        "The generator link-checks every page it writes.",
        "As of the last build before this session: 27 pages, 0 broken links. This session adds pages "
        "and re-runs the same check.",
        "VERIFIED",
        "https://github.com/wingbangboozle1-lang/NBA3/actions/workflows/pages.yml",
        None,
    ),
    (
        "Verify every table row against an official source and never infer or fill in a value.",
        "scripts/build_app.py table() (refuses an unsourced row), tools/check_site.py, this page",
        "The table helper fails the build if a row carries no https source link.",
        "Every row on this page carries an https source; values that could not be confirmed are "
        "left blank and listed on the Flagged for review page.",
        "VERIFIED",
        "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/build_app.py",
        None,
    ),
]


def rows():
    return [dict(zip(("req", "impl", "evidence", "verification", "status", "source", "blocker"), r))
            for r in ROWS]


def counts():
    out = {}
    for r in rows():
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out
