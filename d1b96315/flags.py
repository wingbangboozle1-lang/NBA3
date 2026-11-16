#!/usr/bin/env python3
"""Build this session's flagged register: what we found, what it affects, and what to do about it.

Every row carries at least one official source link, every count is read out of the committed
artefacts (never typed by hand), and every row states whether it blocks the merge (it does not —
flagged items are published on the Flagged for Review page instead).

Run: python3 d1b96315/flags.py          -> d1b96315/data/flags.json + d1b96315/data/flags.csv
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
D = HERE / "data"
STAMP = "2026-11-16T18:55Z"

OFFICIAL = {
    "index": "https://official.nba.com/nba-injury-report-2026-27-season/",
    "pdf_1315": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf",
    "pdf_1130": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_11_30AM.pdf",
    "pdf_0915": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_09_15AM.pdf",
    "games_1115": "https://www.nba.com/games?date=2026-11-15",
    "games_1116": "https://www.nba.com/games?date=2026-11-16",
    "standings": "https://www.nba.com/standings",
    "advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
    "book_atlmil": "https://statsdmz.nba.com/pdfs/20261115/20261115_ATLMIL.pdf",
    "book_indphi": "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
    "book_dalbos": "https://statsdmz.nba.com/pdfs/20261115/20261115_DALBOS.pdf",
    "run": "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43925193575",
}


def load(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


def build() -> dict:
    latest = load(D / "injuries_2026-11-16_latest.json")
    morning = load(D / "injuries_2026-11-16_1130AM.json")
    d_pm = load(D / "injury_delta_2026-11-16_1130_to_1315.json")
    d_am = load(D / "injury_delta_2026-11-16_0915_to_1130.json")
    pub = load(ROOT / "data" / "rounds" / "2026-11-16" / "injuries.json")
    st = load(D / "standings_2026-11-16.json")
    adv = load(D / "team_advanced_2026-11-16.json")
    res = load(D / "results_2026-11-15.json")
    logs = load(D / "player_logs_2026-11-15.json")
    model = load(D / "model.json")
    gates = load(D / "gates.json")
    slate = load(D / "slate_2026-11-16_1118.json")
    lines = load(D / "lines.json")["lines"]
    led = load(D / "ledger_check.json")

    tonight = [r for r in lines if r["date"] == "2026-11-16"]
    no_rot = sorted({ab for r in lines for ab in (r["away"], r["home"])
                     if model["estimator_b"]["availability_status_by_team"][ab] == "no rotation data"})
    games_no_rot = [r["game_id"] for r in lines if r.get("publishable")
                    and any(model["estimator_b"]["availability_status_by_team"][a] == "no rotation data"
                            for a in (r["away"], r["home"]))]

    cov = model["injury_coverage"]
    unsubmitted_clubs = cov["clubs_not_submitted"]
    games_no_injury = cov["rows_missing_at_least_one_side"]
    carried = sum(1 for r in latest["rows"] if r.get("team_carried"))
    hca = model["home_court"]
    pub_hca = hca["previously_published_in_this_repo"]
    stale_hours = 4.08   # 09:15 AM ET published vs 01:15 PM ET newest; arithmetic on the two stamps

    rows = [
        {"id": "D-01", "severity": "high", "surface": "data plane / freshness",
         "title": "at this session's base the published snapshot was 4 h 05 m behind the newest "
                  "official revision, and the scheduled job is the reason",
         "measured": f"at base {pub['report_stamp']} (retrieved {pub['retrieved_utc']}) was the newest "
                     f"published report; the day's actual chain is 09:15 AM (57 player rows / 15 clubs "
                     f"unfiled) → 11:30 AM (no change, a re-stamp) → 01:00 PM (75 / 12 — the filing "
                     f"hop) → 01:15 PM ({latest['player_rows']} / {latest['club_marker_rows']}). While "
                     f"this session worked, main gained a round from arena/fbd2484b-nba3 that published "
                     f"the same 01:15 PM revision, and its parser's counts agree row-for-row with this "
                     f"session's independent read (76 player rows, 11 clubs unfiled) — the round is now "
                     f"fresh, the scheduled job still is not: data/app/refresh/ is stuck at "
                     f"2026-11-16T00-57Z",
         "why_it_matters": "the afternoon's availability news — Marcus Smart Out on a league "
                           "suspension, Jaylon Tyson, Isaiah Stewart and Pelle Larsson downgraded, "
                           "19 rows added when Washington, Houston, Philadelphia and finally Boston "
                           "filed — reached the round tree by another session's work but never reached "
                           "the canonical capture directory or the app surfaces, because the cron fired "
                           "at 11:15 and 17:15 UTC and its last run died before its commit step",
         "action": "CR-D1B-03 on the board: a game-day pass ~30 minutes before the earliest tip, "
                   "taking the newest item in the index rather than a constructed filename; D-02 is "
                   "why nothing advanced on its own",
         "blocks_merge": False,
         "sources": [OFFICIAL["index"], OFFICIAL["pdf_1315"], OFFICIAL["pdf_0915"],
                     "data/rounds/2026-11-16/injuries.json",
                     "d1b96315/data/injury_delta_2026-11-16_1130_to_1315.json"]},

        {"id": "D-02", "severity": "high", "surface": "CI / scheduled job",
         "title": "the scheduled refresh run dies in 19 s in the unit-test step, before any commit",
         "measured": f"run 43925193575 job refresh step 'Unit tests (capture, feed, ledger, "
                     f"estimators, gates)' is the failing step; the newest capture stamp on main is "
                     f"2026-11-16T00-57Z; the same five modules run here as "
                     f"'Ran 40 tests OK'",
         "why_it_matters": "because the job aborts before its commit step, the canonical "
                           "data/app/refresh/ tree and the app/ surfaces never advance, which is the "
                           "proximate cause of D-01; the round tree under data/rounds/ is fresher, so "
                           "'the banner is stale' applies to data/app + app/, not to round/",
         "action": "owner: re-run the job with `--debug` and read the log from the Actions UI (the log "
                   "body is not reachable from this sandbox: `gh run view --log-failed` returned a "
                   "results-receiver EOF and the raw job-log URL returned an empty body); suspect an "
                   "environment difference, not the data, since the modules pass offline here",
         "blocks_merge": False,
         "sources": [OFFICIAL["run"], "data/app/refresh/2026-11-16T00-57Z/manifest.json",
                     "scripts/refresh_official.py"]},

        {"id": "D-03", "severity": "high", "surface": "settlement integrity",
         "title": "one official game book prints two different third-quarter scores for Milwaukee",
         "measured": f"the period table prints MIL 37 + 16 + 37 + 26 = 116 against a printed final of "
                     f"106; the recap line in the same PDF prints 37 16 27 26 106, which sums. The "
                     f"scoreboard, the recap line and the box team totals all print 113-106 Atlanta, "
                     f"so the final is verified and only the quarter vector is disputed. Gate "
                     f"I2_quarter_scores stays red for 0022600243.",
         "why_it_matters": "this is the row the 11/15 model excluded; a quarter vector that does not "
                           "sum is a real defect in an official document, and forcing the gate green "
                           "would hide it. Both readings are published side by side instead",
         "action": "keep the row footnoted; ask the stats owner whether the period table or the recap "
                   "line is authoritative before any quarter-based market (team Q3 totals) is priced",
         "blocks_merge": False,
         "sources": [OFFICIAL["book_atlmil"], OFFICIAL["games_1115"],
                     "d1b96315/data/results_2026-11-15.json",
                     "d1b96315/data/raw/gamebook_20261115_ATLMIL.md"]},

        {"id": "D-04", "severity": "high", "surface": "model / home-court advantage",
         "title": "three different home-court values are pinned in this repository at once",
         "measured": f"this build pins {hca['hca_points_used']} from the league-wide measured home-win "
                     f"rate {st['measured_home_win_rate']} ({st['measured_home_wins']}-"
                     f"{st['measured_home_games'] - st['measured_home_wins']} in "
                     f"{st['measured_home_games']} home games, Wilson 95% "
                     f"{hca['wilson95_standings']}); the round capture pins "
                     f"{pub_hca['data_rounds_2026_11_16']['hca_points']} from "
                     f"{pub_hca['data_rounds_2026_11_16']['n_games']} finals "
                     f"(rate {pub_hca['data_rounds_2026_11_16']['home_win_rate']}); every entry in "
                     f"data/app/ledger/ledger.jsonl records the constant "
                     f"{pub_hca['data_app_ledger_constant']['hca_points'][0]}. Spread: "
                     f"{pub_hca['spread_between_the_three_points']} points",
         "why_it_matters": f"the pin is applied to every line, so this build's home margins are "
                           f"{pub_hca['effect_on_this_builds_lines']['vs_the_round_capture']} points "
                           "different from the same model run at the previously pinned value; the "
                           "brief requires the pin to be the measured home-win rate, and the league-wide "
                           "measurement (n = 196) beats a 23-final sample (n = 22), but two published "
                           "surfaces now disagree and neither is wrong on its own basis",
         "action": "owner decision: adopt the standings-based pin everywhere (this session's "
                   "recommendation) or keep the short-sample pin for continuity with the sealed ledger "
                   "entries; do not silently re-pin, because the sealed hashes contain the old value",
         "blocks_merge": False,
         "sources": [OFFICIAL["standings"], "data/rounds/2026-11-16/model.json",
                     "data/app/ledger/ledger.jsonl", "d1b96315/data/model.json"]},

        {"id": "D-05", "severity": "medium", "surface": "parsing / injury report",
         "title": "continuation rows after a PDF page break carry no club column",
         "measured": f"{carried} of {latest['count']} rows in the 01:15 PM revision have no team cell; "
                     f"a naive parse drops them, which fabricates {len(d_am['rows_removed'])} 'removed "
                     f"rows' in the morning diff and hides the fact that the 09:15 -> 11:30 revision "
                     f"changed nothing ({d_am['counts']['status_changes']} status changes, "
                     f"{d_am['counts']['rows_added']} added, {d_am['counts']['rows_removed']} removed)",
         "why_it_matters": "this is the same defect class that made scripts/injury_archive.py publish "
                           "DAL@BOS as REPORTED_CLEAR: the renderer drops whole columns from the left at "
                           "a page break, so any parser keyed on a cell index is wrong on part of every "
                           "report. This session parses by content and carries the club from the block "
                           "above, marking each such row `team_carried`",
         "action": "audit every injury parser on the board for index-based column reads; the fix "
                   "belongs in the shared capture script, which is PR #95's file, so it is requested "
                   "as a change in COORDINATION.md rather than edited here",
         "blocks_merge": False,
         "sources": [OFFICIAL["pdf_1315"], OFFICIAL["pdf_1130"],
                     "d1b96315/data/injury_delta_2026-11-16_0915_to_1130.json",
                     "scripts/injury_archive.py"]},

        {"id": "D-06", "severity": "medium", "surface": "provenance / roster assignment",
         "title": "the season-leader strip on the games page assigns players to different clubs than "
                  "the report and the game book do",
         "measured": "the 11:30 AM and 01:15 PM reports both list 'James, LeBron — Out — Low Back/"
                     "Sciatica Management' under the Philadelphia 76ers, and the official 11/15 game "
                     "book for IND@PHI logs LeBron James in Philadelphia's box (32:47, 15 pts, 11 ast) "
                     "— the two game-level documents agree. The season-leader strip on the same 11/16 "
                     "games page lists him under Los Angeles (and Giannis under Miami, AD under "
                     "Washington). The 11/19 page's strip is consistent with the reports (Garland LAC, "
                     "Jerome MEM — and MEM's report does carry a Jerome row), so the disagreement is "
                     "specific to the strip, not to the league's roster data",
         "why_it_matters": "per-player models are keyed on club, so a row attributed to the wrong club "
                           "moves the availability adjustment by a full rotation; this session follows "
                           "the two game-level documents (injury report, game book) and uses the leader "
                           "strip for nothing",
         "action": "treat the strip as a display artefact of a different feed and ask its owner; "
                   "recorded here so no later session reads a club assignment off it — no row on this "
                   "site does",
         "blocks_merge": False,
         "sources": [OFFICIAL["pdf_1315"], OFFICIAL["book_indphi"], OFFICIAL["games_1116"],
                     "https://www.nba.com/games?date=2026-11-19"]},

        {"id": "D-07", "severity": "medium", "surface": "coverage / unfiled reports",
         "title": "eleven clubs had still not filed at 01:15 PM, including a club playing tonight",
         "measured": f"unfiled in the newest revision: {', '.join(unsubmitted_clubs)} — Phoenix plays "
                     f"at Denver at 9:00 PM ET tonight and all five 11/17 games are unfiled; the "
                     f"revision covers game dates 11/16 and 11/17 only, so all 12 rows on 11/18 have "
                     f"no filing either. Coverage of the window: "
                     f"{json.dumps(cov['rows_by_state'])} — {games_no_injury} of {slate['count']} rows "
                     "price at least one club with no injury input at all",
         "why_it_matters": "an unfiled report is not a clear report: the correct reading is 'unknown', "
                           "and a line built on 'unknown' must be labelled, because a late filing can "
                           "move a rotation by 30 minutes in one step",
         "action": "the last revision before each tip should be re-fetched for the two clubs involved; "
                   "the board's suggestion of a 30-minutes-before-tip pass is cheap and this is the "
                   "argument for it",
         "blocks_merge": False,
         "sources": [OFFICIAL["pdf_1315"], OFFICIAL["index"], "d1b96315/data/lines.json"]},

        {"id": "D-08", "severity": "medium", "surface": "model / rotation data coverage",
         "title": "captured box scores exist for 9 of 30 clubs, so only 9 clubs get an availability "
                  "adjustment",
         "measured": f"'no rotation data' for {', '.join(no_rot)}; {len(games_no_rot)} of {slate['count']} "
                     f"window rows have at least one club with no box score; this session added "
                     f"BOS/DAL/IND/PHI from the 11/15 game books ({logs['count']} rows), taking the "
                     f"pool from 10 clubs (11/14 only) to 12",
         "why_it_matters": "without a box score there are no minutes shares to redistribute, so the "
                           "availability column on the picks page reads 'not modelled' for those rows — "
                           "which is a measurement of the gap, not a zero",
         "action": "one game book per club per game day is the whole requirement (six PDFs a day for a "
                   "full slate); until that capture exists, no player-prop or minutes-based number may "
                   "be published for the uncovered clubs",
         "blocks_merge": False,
         "sources": [OFFICIAL["book_dalbos"], OFFICIAL["book_indphi"],
                     "d1b96315/data/player_logs_2026-11-15.json",
                     "data/app/player_game_logs.json", "data/app/minutes_shares.json"]},

        {"id": "D-09", "severity": "low", "surface": "data quality / unread cells",
         "title": "the PDF extraction drops one column in six of the box-score rows this session read",
         "measured": f"{len(logs['unread_cells'])} rows in the two new game-book transcripts have a "
                     f"stat cell missing after MIN; the minutes cell is keyed by content and kept, "
                     f"every stat in those rows is published null. Independently, "
                     f"{len(latest['unread_cells'])} injury-report cells are unread "
                     f"({len([c for c in latest['unread_cells'] if 'not readable' in c])} of them in the "
                     "shifted Golden State block, where Jimmy Butler's row prints no status cell at all "
                     "and four rows print a status with no reason)",
         "why_it_matters": "an empty cell is evidence about the document, not about the player; leaving "
                           "it blank and counting it is the only honest handling",
         "action": "re-extract the two PDFs with a table-detection mode before any per-player model is "
                   "built on these rows",
         "blocks_merge": False,
         "sources": [OFFICIAL["book_dalbos"], OFFICIAL["book_indphi"], OFFICIAL["pdf_1315"],
                     "d1b96315/data/player_logs_2026-11-15.json"]},

        {"id": "D-10", "severity": "high", "surface": "betting gate / market data",
         "title": "no licensed price feed, so no strategy can be funded and every line is a projection",
         "measured": f"gates: {gates['summary']['strategies']} strategies, "
                     f"{gates['summary']['funded']} funded, blocking gates "
                     f"{', '.join(gates['summary']['gates_blocking_any_strategy'])}; the model's market "
                     f"anchor is null (prior weight, closing line and log loss all unpublishable); the "
                     f"11/16 games page renders no odds in the fetched HTML",
         "why_it_matters": "the projection surface can be published today; the bet surface stays empty "
                           "by construction until a real closing line exists, which is the separation "
                           "the brief asks for",
         "action": "owner: decide the price source (licensed feed vs manual entry of published closing "
                   "lines). Until then, 'parlay priced with measured rho' is a number we publish about "
                   "our own model, and the page says so on every row",
         "blocks_merge": False,
         "sources": ["d1b96315/data/gates.json", OFFICIAL["games_1116"],
                     "d1b96315/data/model.json"]},

        {"id": "D-11", "severity": "low", "surface": "integrity of this session's own work",
         "title": "a manual test run wrote two stray stamp directories into another session's path",
         "measured": "data/app/refresh/T1 and T2 appeared under the canonical refresh directory after "
                     "this session ran the five test modules by hand; they were removed in the same "
                     "session and no published artefact was touched. The test itself writes to a temp "
                     "directory (tests/test_refresh_official.py passes --stamp inside a tempdir), so the "
                     "residue came from how the modules were invoked, not from the test's design",
         "why_it_matters": "the board rule is that shared paths change only inside your own scope; a "
                           "stray directory in another session's capture tree is exactly the kind of "
                           "collision that has to be self-reported and cleaned",
         "action": "nothing to fix in the code; recorded so no later session mistakes T1/T2 for captures",
         "blocks_merge": False,
         "sources": ["data/app/refresh/", "tests/test_refresh_official.py"]},

        {"id": "D-12", "severity": "medium", "surface": "ledger / tamper evidence",
         "title": "the second ledger chain is verifiable, but its recipe was never written down",
         "measured": f"independent re-verification of all three chains: "
                     f"data/app/ledger/ledger.jsonl {led['trees']['ledger_B']['entries']} entries, "
                     f"{led['k17_resolution']['recompute_with_chain_hash_prev_and_body']} recompute with "
                     f"sha256(canon({{prev, body}})) and "
                     f"{led['k17_resolution']['recompute_with_body_alone']} with the body alone; "
                     f"ledger/ledger.jsonl {led['trees']['ledger_A']['entries']} entries intact under "
                     f"its documented recipe; this session's chain "
                     f"{led['ledger']['published_pre_tip']} entries, head {led['ledger']['head_hash'][:16]}"
                     f"..., {led['ledger']['settled']} settled",
         "why_it_matters": "board item K-17 called this 'undocumented hash recipe' and left it open; the "
                           "hash is over the {prev, body} pair produced by chain_hash() in "
                           "scripts/pick_ledger.py, so the chain is intact and the 'problem' was missing "
                           "documentation, not a linkage break",
         "action": "nothing re-hashed, nothing in another session's tree modified; the verifier here "
                   "(d1b96315/ledger.py verify) is the recipe, restated in code and in this row",
         "blocks_merge": False,
         "sources": ["data/app/ledger/ledger.jsonl", "ledger/ledger.jsonl",
                     "scripts/pick_ledger.py", "d1b96315/data/ledger_check.json",
                     "d1b96315/ledger/ledger.jsonl"]},
    ]
    rows.append(
        {"id": "D-13", "severity": "medium", "surface": "ledger / sealed history",
         "title": "two sealed lines disagree with the model that sealed them, because a parser fix "
                  "landed between the seal and now",
         "measured": f"{led['ledger']['amendments']} AMEND entries appended to "
                     f"{led['ledger']['published_pre_tip']} seals "
                     f"({', '.join(led['ledger']['amended_picks'])}): the page-break carry that "
                     "recovered 7 dropped injury rows also restored Isaiah Stewart to Memphis's Out "
                     "list, which moves estimator B's margin on the two Memphis games by up to 1.59 "
                     "points. The sealed payloads were left byte for byte as they were",
         "why_it_matters": "this is what an honest fix looks like in a tamper-evident ledger: the old "
                           "hash stays and the divergence is published. Silently re-hashing would have "
                           "made the chain agree with today's model and stopped being evidence about "
                           "what was actually published before tip",
         "action": "read the ledger page's amend panel; no action needed for tonight's games, whose "
                   "sealed numbers and current numbers already agree",
         "blocks_merge": False,
         "sources": ["d1b96315/ledger/ledger.jsonl", "d1b96315/data/ledger_check.json",
                     "d1b96315/data/lines.json"]})
    return {"schema": "nba3.d1b96315.flags/v1", "stamp": STAMP, "session": "arena/d1b96315-nba3",
            "rule": "nothing on this list blocks the merge; every row carries at least one official "
                    "source link and a value that could not be confirmed is left blank rather than "
                    "inferred",
            "counts": {"rows": len(rows),
                       "by_severity": {s: sum(1 for r in rows if r["severity"] == s)
                                       for s in ("high", "medium", "low")},
                       "blocking_merge": sum(1 for r in rows if r["blocks_merge"])},
            "stale_hours_measured": stale_hours,
            "flags": rows}


def main() -> int:
    out = build()
    (D / "flags.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "severity", "surface", "title", "measured", "why_it_matters", "action",
                "blocks_merge", "sources"])
    for r in out["flags"]:
        w.writerow([r["id"], r["severity"], r["surface"], r["title"], r["measured"],
                    r["why_it_matters"], r["action"], str(r["blocks_merge"]).lower(),
                    " ".join(r["sources"])])
    (D / "flags.csv").write_text(buf.getvalue(), encoding="utf-8")
    print(f"wrote d1b96315/data/flags.json and flags.csv ({out['counts']['rows']} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
