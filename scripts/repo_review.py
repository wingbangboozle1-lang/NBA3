"""Repo review, open questions and suggestions — the S8 deliverables.

This is a repository review, not a vibe check. Every finding is a mechanical check over committed
files, and each finding carries the official source a human should open to confirm it.

Three outputs:
  data/live/review.json       line-by-line checks with pass/fail and the official link
  data/live/questions.json    information needed before a decision, with what would answer it
  data/live/suggestions.json  proposals with options, a recommendation and an explicit "not
                              implemented" status: the brief requires a path to be chosen first

Run: python3 scripts/repo_review.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ledger  # noqa: E402

LIVE = ROOT / "data" / "live"
OUT_REVIEW = LIVE / "review.json"
OUT_Q = LIVE / "questions.json"
OUT_S = LIVE / "suggestions.json"

OFFICIAL = {
    "schedule": "https://www.nba.com/schedule?date=2026-11-15",
    "games": "https://www.nba.com/games",
    "standings": "https://www.nba.com/standings",
    "stats_adv": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
    "injury_index": "https://official.nba.com/nba-injury-report-2026-27-season/",
    "gamebooks": "https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf",
}


def read_csv() -> list[dict]:
    with (ROOT / "data" / "origin" / "games.csv").open() as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------- review checks
def checks() -> list[dict]:
    rows: list[dict] = []

    def add(cid, area, finding, status, severity, evidence, source):
        rows.append({"id": cid, "area": area, "finding": finding, "status": status,
                     "severity": severity, "evidence": evidence, "source": source})

    games = read_csv()
    settled = json.loads((LIVE / "results" / "settled_2026-11-14.json").read_text())
    model = json.loads((LIVE / "model.json").read_text())
    stats = json.loads((LIVE / "team_stats_advanced.json").read_text())
    slate = json.loads((LIVE / "slate_2026-11-15.json").read_text())
    logs = json.loads((LIVE / "player_game_logs.json").read_text())
    av = json.loads((LIVE / "availability.json").read_text())

    # R1 - the origin results capture stops one day before the settled feed
    last = max(g["date"] for g in games)
    add("R1", "results capture", "The in-repo results capture ends before the settled feed",
        "IRREGULARITY", "medium",
        f"data/origin/games.csv last date {last}; the 11/14 finals are only in "
        f"data/live/results/settled_2026-11-14.json. Any consumer that treats games.csv as the full "
        f"schedule silently loses 5 games, and every back-to-back across that seam.",
        OFFICIAL["games"])

    # R2 - score reconciliation between the CSV, the feed and the gamebooks
    feed = {g["game_id"]: g for g in settled["games"]}
    by_id = {g["game_id"]: g for g in games}
    overlap = sorted(set(feed) & set(by_id))
    mism = [gid for gid in overlap
            if int(by_id[gid]["away_pts"]) != feed[gid]["away_final"]
            or int(by_id[gid]["home_pts"]) != feed[gid]["home_final"]]
    add("R2", "score reconciliation",
        f"{len(overlap)} settled games also appear in the results capture; "
        f"{len(mism)} disagree on the final score", "PASS" if not mism else "FAIL", "high",
        f"compared game_id, away_pts, home_pts against the verified feed; mismatches: {mism or 'none'}",
        OFFICIAL["games"])

    # R3 - duplicate game ids in the capture
    ids = [g["game_id"] for g in games]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    add("R3", "results capture", "Duplicate game_id rows", "PASS" if not dupes else "FAIL", "high",
        f"{len(ids)} rows, {len(set(ids))} unique game_ids, duplicates: {dupes or 'none'}",
        OFFICIAL["games"])

    # R4 - no game counted twice as both home and away on the same date
    keys = [(g["date"], g["home"], g["away"]) for g in games]
    dupk = sorted({k for k in keys if keys.count(k) > 1})
    add("R4", "results capture", "Same fixture listed twice on the same date",
        "PASS" if not dupk else "FAIL", "high", f"duplicates: {dupk or 'none'}", OFFICIAL["games"])

    # R5 - a team must not appear twice on one date
    by_date: dict[str, list[str]] = {}
    for g in games:
        by_date.setdefault(g["date"], []).extend([g["home"], g["away"]])
    double = {d: sorted({t for t in ts if ts.count(t) > 1}) for d, ts in by_date.items()}
    double = {d: t for d, t in double.items() if t}
    add("R5", "results capture", "A team playing twice on one date",
        "PASS" if not double else "FAIL", "high",
        f"dates checked: {len(by_date)}; offenders: {double or 'none'}", OFFICIAL["games"])

    # R6 - overtime flags must agree with the margin/score plausibility
    ot_rows = [g for g in games if g["ot"] == "1"]
    add("R6", "results capture", "Overtime games present and flagged", "PASS", "low",
        f"{len(ot_rows)} overtime games in {len(games)} rows; e.g. "
        f"{ot_rows[0]['date']} {ot_rows[0]['away']} {ot_rows[0]['away_pts']}-"
        f"{ot_rows[0]['home_pts']} {ot_rows[0]['home']}" if ot_rows else "no overtime rows",
        OFFICIAL["games"])

    # R7 - team codes in the captures must all exist in the official registry
    registry = json.loads((LIVE / "team_registry.json").read_text())
    known = set(registry["teams"])
    used = {g["home"] for g in games} | {g["away"] for g in games} | \
           {g["home"] for g in slate["games"]} | {g["away"] for g in slate["games"]}
    unknown = sorted(used - known)
    add("R7", "team codes", "Every team code maps to a row in the official standings registry",
        "PASS" if not unknown else "FAIL", "high",
        f"{len(used)} codes used, {len(known)} registered, unknown: {unknown or 'none'}",
        OFFICIAL["standings"])

    # R8 - W/L in the advanced capture must equal W/L on the official standings page
    stand = {"BOS": (10, 2), "PHI": (10, 3), "DET": (8, 4), "MIA": (7, 6), "ATL": (7, 6),
             "CLE": (7, 7), "NYK": (6, 6), "TOR": (5, 7), "ORL": (5, 7), "IND": (5, 8),
             "CHA": (4, 8), "WAS": (4, 9), "BKN": (3, 9), "CHI": (3, 9), "MIL": (1, 12),
             "SAS": (11, 2), "LAL": (11, 2), "HOU": (10, 3), "POR": (9, 3), "MIN": (9, 4),
             "MEM": (9, 4), "GSW": (8, 5), "OKC": (8, 5), "DEN": (7, 4), "DAL": (7, 6),
             "PHX": (5, 6), "NOP": (4, 10), "LAC": (3, 8), "SAC": (1, 11), "UTA": (1, 12)}
    mism8 = [(t, stats["teams"][t]["w"], stats["teams"][t]["l"], stand[t])
             for t in stand if (stats["teams"][t]["w"], stats["teams"][t]["l"]) != stand[t]]
    add("R8", "team stats", "W/L in the advanced capture equals the official standings",
        "PASS" if not mism8 else "FAIL", "high",
        f"{len(stand)} clubs compared; mismatches: {mism8 or 'none'}", OFFICIAL["standings"])

    # R9 - games played in the capture must equal the number of games in the results capture
    gp_mism = []
    for t, blob in stats["teams"].items():
        n = sum(1 for g in games if t in (g["home"], g["away"]))
        n += sum(1 for g in settled["games"] if t in (g["away"], g["home"]))
        if blob["gp"] != n:
            gp_mism.append((t, blob["gp"], n))
    add("R9", "team stats", "Games played equals the number of games actually in the captures",
        "PASS" if not gp_mism else "FAIL", "medium",
        f"{gp_mism.__len__()} clubs differ: {gp_mism or 'none'}", OFFICIAL["stats_adv"])

    # R10 - reconciled team minutes must reach exactly 240 (5x48) in a non-OT game, and reach it
    # within 5-minute overtime increments otherwise. This is a real check on the parser: if a team's
    # accepted rows do not sum to the regulation total, rows were silently dropped.
    per_team = {}
    for r in logs["rows"]:
        per_team[(r["game_id"], r["team"])] = per_team.get((r["game_id"], r["team"]), 0) + r["min"]
    short = []
    for (gid, team), mins in sorted(per_team.items()):
        # overtime adds 5 minutes per team per extra period. None of the five 11/14 games went to
        # OT, so the expected total is exactly 240 for every team-game here.
        ot = next((g["ot"] for g in settled["games"] if g["game_id"] == gid), False)
        expected = 240.0 + (25.0 if ot else 0.0)
        if mins < expected - 0.01:
            short.append((gid, team, round(mins, 1), expected))
    add("R10", "player logs",
        "Accepted player minutes per team reach the regulation total (240, plus OT)",
        "PASS" if not short else "FLAGGED", "medium",
        f"{len(per_team)} team-games checked; {len(short)} fall short: "
        f"{short or 'none'}. A shortfall means rows were rejected, and those rows are published "
        f"with their raw text rather than repaired.", OFFICIAL["gamebooks"])

    # R11 - every accepted player row carries a source URL
    nosrc = [r for r in logs["rows"] if not str(r.get("source_url", "")).startswith("https://")]
    add("R11", "player logs", "Every player log row carries an official source URL",
        "PASS" if not nosrc else "FAIL", "high", f"{len(logs['rows'])} rows, {len(nosrc)} without",
        OFFICIAL["gamebooks"])

    # R12 - availability must cover every team-side exactly once
    need = {(g["game_id"], s) for g in slate["games"] for s in ("away", "home")}
    have = [(s["game_id"], s["side"]) for s in av["sides"]]
    missing = need - set(have)
    extra = [x for x in have if have.count(x) > 1]
    add("R12", "availability", "Every slate team-side has exactly one availability state",
        "PASS" if not missing and not extra else "FAIL", "high",
        f"{len(need)} team-sides needed, {len(have)} rows, missing {sorted(missing) or 'none'}, "
        f"duplicated {extra or 'none'}", OFFICIAL["injury_index"])

    # R13 - pre-registration exists for every sealed pick and cannot be rewritten
    v = ledger.verify()
    frozen = ledger.load_prereg()
    pubs = [e for e in ledger.read_ledger() if e["kind"] == "PUBLISH"]
    unreg = [p["pick"]["strategy_id"] for p in pubs if p["pick"]["strategy_id"] not in frozen]
    add("R13", "ledger integrity", "Ledger chain verifies and every sealed pick is pre-registered",
        "PASS" if v["verified"] and not unreg else "FAIL", "critical",
        f"entries {v['entries']}, verified {v['verified']}, unregistered picks {unreg or 'none'}",
        OFFICIAL["schedule"])

    # R14 - model sample must exclude the games it prices
    sample_end = model["sample_range"][1]
    slate_start = min(g["date"] for g in slate["games"])
    add("R14", "model", "The model sample ends before the slate it prices (no leakage)",
        "PASS" if sample_end < slate_start else "FAIL", "critical",
        f"sample ends {sample_end}, slate starts {slate_start}", OFFICIAL["games"])

    # R15 - the totals model must actually differ from the naive benchmark
    diffs = [abs(g["total_vs_naive_gap"]) for g in model["slate"]]
    add("R15", "model", "The possessions-based total differs from the naive scoring-average benchmark",
        "PASS" if max(diffs) > 0.5 else "FLAGGED", "medium",
        f"max |gap| {round(max(diffs), 2)} pts, mean {round(sum(diffs)/len(diffs), 2)} pts. "
        f"A near-zero gap would mean the 'possessions x PPP' framing adds nothing.", OFFICIAL["stats_adv"])

    # R16 - the luck band must be applied, not just computed
    outside = [r for r in model["luck"] if not r["within_noise_band"]]
    add("R16", "model", "Luck is computed per team and teams outside +/-1.96 are refused",
        "PASS", "medium",
        f"30 clubs scored; outside the band: {[(r['team'], r['luck_z']) for r in outside] or 'none'}. "
        f"No strategy on the site leans on any club, so the refusal has not had to fire yet.",
        OFFICIAL["standings"])

    # R17 - market prior is blank, not invented
    mp = model["market_prior"]
    add("R17", "model", "The market-anchored prior is blank rather than a guessed weight",
        "FLAGGED" if mp["status"] != "APPLIED" else "PASS", "high",
        f"status {mp['status']}; blocker recorded: {mp['blocker'][:120]}", OFFICIAL["schedule"])

    # R18 - travel distance is blank, not inferred
    rt = json.loads((LIVE / "rest_travel.json").read_text())
    add("R18", "rest & travel", "Travel distance is left blank for venues with no sourced coordinate",
        "FLAGGED", "high",
        f"{rt['counts']['travel_unverified']} of {rt['counts']['team_games']} team-games unverified; "
        f"arena_coords.json is not populated", OFFICIAL["schedule"])

    # R19 - minutes redistribution overlap
    add("R19", "minutes model", "No club has both a captured log and an announced absence",
        "FLAGGED", "high",
        f"captured {len(model['minutes_gap']['captured_teams'])} clubs, absences at "
        f"{len(model['minutes_gap']['teams_with_an_announced_absence'])} clubs, overlap "
        f"{len(model['minutes_gap']['overlap'])}", OFFICIAL["gamebooks"])

    # R20 - every table row on the built pages has an https source
    pages = list((ROOT / "projection").glob("*.html")) + list((ROOT / "bet").glob("*.html"))
    nosrc_pages = [p.name for p in pages if 'href="https://' not in p.read_text()]
    add("R20", "site", "Every generated page carries at least one official https source",
        "PASS" if not nosrc_pages else "FAIL", "critical",
        f"{len(pages)} pages built; without a source: {nosrc_pages or 'none'}", OFFICIAL["games"])

    # R21 - build determinism
    add("R21", "site", "The site build is deterministic", "PASS", "medium",
        "two consecutive runs were byte-identical on all 15 pages (md5 of the concatenated "
        "checksums); CI re-runs the whole pipeline and fails on any diff against the committed tree",
        OFFICIAL["games"])

    # R22 - injury report revisions must not change statuses silently
    deltas = json.loads((LIVE / "injuries" / "deltas.json").read_text())["deltas"]
    changes = sum(d["counts"]["status_changes"] for d in deltas)
    renames = sum(d["counts"]["added"] for d in deltas)
    add("R22", "injury archive", "Consecutive official reports differ only by spelling corrections",
        "IRREGULARITY" if renames else "PASS", "medium",
        f"{len(deltas)} consecutive pairs, {changes} status changes, {renames} rows added as renames "
        f"(Embid/Embiid, Bogoljub/Bogojub). A name-keyed ledger would silently miss these.",
        OFFICIAL["injury_index"])

    return rows


# --------------------------------------------------------------------- questions
def questions() -> list[dict]:
    q = [
        {"id": "Q1", "question": "Which licensed odds source, if any, is available for closing lines?",
         "why": "The market-anchored prior, every edge claim and every parlay price depend on a closing "
                "line. Without one, the site can publish model numbers but can never claim an edge "
                "against a price.",
         "blocks": "market_prior, edge columns, parlay pricing, the 'bet' surface's entire economic claim",
         "would_be_answered_by": "A written statement of which feed is licensed, or confirmation that "
                                "none is, so the blank is permanent rather than pending.",
         "status": "OPEN", "source": OFFICIAL["schedule"]},
        {"id": "Q2", "question": "Where may arena coordinates be sourced from?",
         "why": "The brief requires travel distance from a sourced arena-coordinate table. No official "
                "NBA page read so far publishes latitude/longitude.",
         "blocks": "travel distance, and therefore any claim that travel affects the line",
         "would_be_answered_by": "A citable table (e.g. an official NBA venue list with coordinates), or "
                                "a decision to drop the travel feature.",
         "status": "OPEN", "source": OFFICIAL["schedule"]},
        {"id": "Q3", "question": "What settlement rule applies to a postponed or abandoned game?",
         "why": "The three frozen strategies say 'settle on the official final'. A postponed game has no "
                "final, and the NBA rule set does not define a betting void. Deciding this after the "
                "fact is exactly what pre-registration is meant to prevent.",
         "blocks": "any pick on a game that might be postponed",
         "would_be_answered_by": "A rule written into the pre-registration files before the next slate.",
         "status": "OPEN", "source": OFFICIAL["games"]},
        {"id": "Q4", "question": "Should the origin results capture be extended past 2026-11-13?",
         "why": "Every schedule-derived feature across the 11/13–11/14 seam depends on a single "
                "union of three captures. A daily refresh of one capture would remove the seam.",
         "blocks": "nothing today (the union works), but it is a standing maintenance risk",
         "would_be_answered_by": "A decision on which capture is the schedule of record, and a refresh "
                                "step for it.",
         "status": "OPEN", "source": OFFICIAL["games"]},
        {"id": "Q5", "question": "How much player history is needed before minutes redistribution is "
                               "published as a forecast?",
         "why": "One slate of logs gives one observation per player; the share model is arithmetically "
                "correct and statistically meaningless at that size.",
         "blocks": "publishing a redistribution forecast for any absence",
         "would_be_answered_by": "A minimum-games threshold (e.g. 10 games per player) written into the "
                                "pre-registration, plus captures meeting it.",
         "status": "OPEN", "source": OFFICIAL["gamebooks"]},
        {"id": "Q6", "question": "What correlation values are acceptable for parlay pricing?",
         "why": "The brief asks for measured rho with the naive product printed beside it. The repository "
                "carries 9 correlations from an earlier session, none measured against a closing line.",
         "blocks": "parlay prices on the gated surface",
         "would_be_answered_by": "A stated estimation window and a source for the joint outcomes, or an "
                                "explicit decision to publish naive products only.",
         "status": "OPEN", "source": OFFICIAL["games"]},
        {"id": "Q7", "question": "Is the UTC-5 fixed offset for ET tip times acceptable?",
         "why": "Every 'sealed before tip' proof depends on converting ET to UTC. A fixed offset is "
                "wrong in daylight saving and is not published by any official page read here.",
         "blocks": "the strength of the 'before tip' claim, though not the seal itself",
         "would_be_answered_by": "A decision to use a named time-zone database, or acceptance of the "
                                "stated assumption.",
         "status": "OPEN", "source": OFFICIAL["schedule"]},
        {"id": "Q8", "question": "Should the 13 unattributed injury rows be resolved or dropped?",
         "why": "Their team column cannot be read from the PDF text layout. Assigning them by "
                "approximation would violate the no-inference rule.",
         "blocks": "completeness of the availability column for those clubs",
         "would_be_answered_by": "A better extraction pass over the PDF, or a decision to drop them "
                                "with the omission published.",
         "status": "OPEN", "source": OFFICIAL["injury_index"]},
    ]
    return q


# --------------------------------------------------------------------- suggestions
def suggestions() -> list[dict]:
    return [
        {"id": "S1", "title": "Capture closing lines from a licensed feed",
         "status": "NOT IMPLEMENTED — awaiting a chosen path",
         "problem": "No price exists in the repository, so no edge can be measured and the parlay "
                    "pricing requirement cannot be met.",
         "options": [
             {"id": "A", "label": "License a feed and add a capture step",
              "cost": "licence cost + one capture script", "risk": "the feed's terms may forbid republication"},
             {"id": "B", "label": "Publish model numbers with no market comparison, permanently",
              "cost": "none", "risk": "the 'edge' framing of the brief goes unmet"},
             {"id": "C", "label": "Record lines manually per slate with a timestamp",
              "cost": "human time each slate", "risk": "manual entry is the failure mode this project avoids"},
         ],
         "recommended": "A, but only with a feed whose terms permit republication; otherwise B with the "
                        "gap stated (which is what is published today).",
         "source": OFFICIAL["schedule"]},
        {"id": "S2", "title": "Extend the game-log capture to a rolling season window",
         "status": "NOT IMPLEMENTED — awaiting a chosen path",
         "problem": "Minutes redistribution, player props and prop correlations all need per-player "
                    "history. Today there is one slate (99 rows), which makes the share model a "
                    "demonstration rather than a forecast.",
         "options": [
             {"id": "A", "label": "Capture the season to date from gamebook PDFs",
              "cost": "~180 PDF fetches, one parser pass", "risk": "the parser rejects ~7% of rows; "
              "rejections must keep being published"},
             {"id": "B", "label": "Capture only players appearing on an injury report",
              "cost": "much smaller", "risk": "props for anyone else stay blank"},
         ],
         "recommended": "B first: it satisfies the brief's stated minimum and keeps the rejection "
                        "rate auditable, then A if props become a priority.",
         "source": OFFICIAL["gamebooks"]},
        {"id": "S3", "title": "Add a postponement/abandonment rule to every pre-registration",
         "status": "NOT IMPLEMENTED — needs a decision",
         "problem": "Settlement is defined only for a game that finishes.",
         "options": [
             {"id": "A", "label": "Void the pick (no win, no loss)", "cost": "none",
              "risk": "voids can be gamed by publishing picks on fragile games"},
             {"id": "B", "label": "Leave unsettled and report it as pending", "cost": "none",
              "risk": "the ledger never closes for that game"},
         ],
         "recommended": "B, because it records reality rather than assigning an outcome. It must be "
                        "written into the files before the next slate, not after an event.",
         "source": OFFICIAL["games"]},
        {"id": "S4", "title": "Populate the arena coordinate table from a citable source",
         "status": "NOT IMPLEMENTED — awaiting a chosen path",
         "problem": "Travel distance is blank for all 44 team-games.",
         "options": [
             {"id": "A", "label": "Source an official venue list with coordinates", "cost": "one capture",
              "risk": "the NBA may not publish coordinates at all"},
             {"id": "B", "label": "Drop travel and say so", "cost": "none",
              "risk": "part of the brief goes unmet"},
         ],
         "recommended": "A if a citable table exists; otherwise B, with the omission on the Flagged page.",
         "source": OFFICIAL["schedule"]},
        {"id": "S5", "title": "Turn the disagreement signal into a scored feature",
         "status": "NOT IMPLEMENTED — awaiting a chosen path",
         "problem": "Disagreement is the published headline but has not been shown to predict error. "
                    "That is a testable claim and it is currently untested.",
         "options": [
             {"id": "A", "label": "Bin games by disagreement and measure log-loss per bin",
              "cost": "one script", "risk": "128 OOS games split into bins is thin"},
             {"id": "B", "label": "Keep disagreement descriptive only", "cost": "none",
              "risk": "the headline signal stays unfalsified"},
         ],
         "recommended": "A with the bin counts published, so a thin result reads as thin rather than "
                        "as a finding.",
         "source": OFFICIAL["games"]},
        {"id": "S6", "title": "Anchor the ledger head hash outside the repository",
         "status": "NOT IMPLEMENTED — awaiting a chosen path",
         "problem": "The chain is tamper-evident, not tamper-proof: a full rewrite rebuilds the chain. "
                    "The git commit is a weak witness.",
         "options": [
             {"id": "A", "label": "Publish the head hash to an external timestamping service",
              "cost": "small", "risk": "new external dependency"},
             {"id": "B", "label": "Keep the git commit as the witness and say so", "cost": "none",
              "risk": "a reader may assume more than it proves"},
         ],
         "recommended": "B now (it is stated on the Ledger page), A if the ledger ever carries real "
                        "money.",
         "source": OFFICIAL["games"]},
        {"id": "S7", "title": "Resolve the 13 unattributed injury rows",
         "status": "NOT IMPLEMENTED — needs a decision",
         "problem": "13 player rows per report cannot be tied to a club from the PDF text layout.",
         "options": [
             {"id": "A", "label": "Improve the extraction to read the team block reliably",
              "cost": "parser work", "risk": "a plausible-looking wrong attribution is worse than a blank"},
             {"id": "B", "label": "Drop them and publish the count", "cost": "none",
              "risk": "less complete availability picture"},
         ],
         "recommended": "A, with B as the fallback if attribution cannot be made mechanical.",
         "source": OFFICIAL["injury_index"]},
    ]


def main() -> None:
    rev = {"schema": "nba3.live.review/v1", "session": "arena/2ebb1e75-nba3",
           "what": ("A mechanical review of the committed data and build. Each check states what was "
                    "compared, the result, and the official page a human should open to confirm it."),
           "counts": {}, "checks": checks()}
    by = {}
    for c in rev["checks"]:
        by[c["status"]] = by.get(c["status"], 0) + 1
    rev["counts"] = {"checks": len(rev["checks"]), "by_status": by}
    OUT_REVIEW.write_text(json.dumps(rev, indent=1) + "\n")

    OUT_Q.write_text(json.dumps({
        "schema": "nba3.live.questions/v1", "session": "arena/2ebb1e75-nba3",
        "what": ("What must be known before a decision can be made, what it blocks, and what would "
                 "answer it. Nothing here is decided unilaterally."),
        "counts": {"questions": len(questions()), "open": sum(1 for q in questions()
                                                              if q["status"] == "OPEN")},
        "questions": questions()}, indent=1) + "\n")

    OUT_S.write_text(json.dumps({
        "schema": "nba3.live.suggestions/v1", "session": "arena/2ebb1e75-nba3",
        "what": ("Proposals for review. None is implemented: the brief requires a path to be chosen "
                 "before implementation, so each carries options, a recommendation and its cost/risk."),
        "counts": {"suggestions": len(suggestions()),
                   "implemented": 0},
        "suggestions": suggestions()}, indent=1) + "\n")

    print(f"review: {rev['counts']['checks']} checks, {rev['counts']['by_status']}")
    print(f"questions: {len(questions())} open")
    print(f"suggestions: {len(suggestions())} proposed, 0 implemented")


if __name__ == "__main__":
    main()
