#!/usr/bin/env python3
"""build_04a81bce_registers.py — O6 registers for the 2026-11-19 official round.

Generates ``data/app/registers_04a81bce.json`` from the verified round outputs:
executive summary, questions / missing information, suggestions (reviewers choose
before implementation), flagged-for-review items (F-DE0-01..06 + this round's
flags + EVE-F04 evidence per CR-B1-02), and change-request answers
(CR-B1-01, CR-DE0-01, CR-DE0-02, CR-00b0c780-06, CR-915-01).

Every factual row names its official source URL. Values that could not be
confirmed from an official source are left blank and flagged, never inferred.
Deterministic: reads only files in the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "data" / "rounds" / "2026-11-19-04a81bce"
VERIFIED = ROUND / "verified"
OUT = ROOT / "data" / "app" / "registers_04a81bce.json"

GAMES_URL = "https://statsdmz.nba.com/pdfs/"
STANDINGS_URL = "https://www.nba.com/standings"
TRAD_URL = "https://www.nba.com/stats/teams/traditional?SeasonType=Regular+Season&Season=2026-27"
ADV_URL = "https://www.nba.com/stats/teams/advanced?SeasonType=Regular+Season&Season=2026-27"
OPP_URL = "https://www.nba.com/stats/teams/opponent?SeasonType=Regular+Season&Season=2026-27"
INJ_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_45AM.pdf"


def load(name):
    return json.loads((VERIFIED / name).read_text(encoding="utf-8"))


def main():
    quarters = load("quarters_2026-11-16_18.json")
    logs = load("player_game_logs.json")
    injury = load("injury_report_2026-11-19.json")
    recut = load("team_stats_recut_2026-11-19.json")
    ledger = load("ledger_hash_check_2026-11-19.json")

    n_blank = sum(1 for g in quarters["games"]
                  for k in ("away_quarters", "home_quarters") if g[k] is None)
    n_vecs = 50 - n_blank
    luck_out = [r for r in recut["luck"] if r["outside_noise_2sd"]]
    b2b = [r for r in recut["rest_travel_1119"] if r["b2b"]]

    executive_summary = {
        "title": "Executive summary — official round 2026-11-19 (sessions arena/04a81bce-nba3)",
        "as_of_utc": "2026-11-19T08:20Z",
        "bullets": [
            {"text": (f"All 25 official game books for 2026-11-16..18 captured and parsed; "
                      f"{n_vecs}/50 team quarter vectors verified against printed finals "
                      f"(sum-of-quarters gate). {n_blank} vectors left blank and flagged "
                      f"(absent or corrupt in the official PDF text layer) — never inferred."),
             "source_url": GAMES_URL},
            {"text": ("2026-11-18 finals settled from official game books; 5 team quarter "
                      "vectors stay blank (PHI-11/16, POR-11/16, MEM-11/18, PHX-11/18, "
                      "UTA-11/18), so quarter-dependent grading for those rows remains blocked."),
             "source_url": GAMES_URL},
            {"text": ("Standings + the three official team-stat pages re-read (traditional, "
                      "opponent, advanced; 30 teams each) and re-cut: measured home-win rate "
                      f"{recut['home_court']['measured_home_win_rate']} "
                      f"({recut['home_court']['home_wins']}/{recut['home_court']['home_games']} home games), "
                      "luck z per team, totals modeled as possessions x PPP, rest/B2B/3-in-4 "
                      "and sourced travel for the 11/19 slate, top-8 minutes shares with "
                      "explicit OUT redistribution (replacement shares flagged unverified)."),
             "source_url": STANDINGS_URL},
            {"text": ("Injury-report revision chain 2026-11-19 01:00/01:15/01:30/01:45 AM "
                      "archived with consecutive diffs (all zero-change); 12:45 AM revision "
                      "carried over from session de0caf5d (CR-DE0-02). Kuminga/Pullin team "
                      "attribution resolved to the Minnesota Timberwolves from the official "
                      "11/16 and 11/17 PORMIN game books."),
             "source_url": INJ_URL},
            {"text": (f"Pre-registration: 15 strategy files frozen before first bet and hash-verified "
                      f"(0 problems). Ledger hash publication check: {ledger['entries']} entries, "
                      f"chain intact, every published pick hashed pre-tip and verified at "
                      f"settlement with visible stamps."),
             "source_url": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/ledger/ledger.jsonl"},
            {"text": ("Luck check: teams outside the 2-sd noise band = "
                      + (", ".join(f"{r['team']} (z={r['luck_z']})" for r in luck_out)
                         if luck_out else "none")
                      + ". Strategies leaning on those teams are refused on the bet surface."),
             "source_url": ADV_URL},
            {"text": ("Integration (O7) rolls the canonical window forward with regenerated "
                      "lines/picks/props/parlays and per-row source URLs (CR-915-01), settles "
                      "the 11/18 chains from verified finals with stamps (CR-B1-01), and "
                      "publishes these registers on the Flagged page (CR-DE0-01)."),
             "source_url": "https://github.com/wingbangboozle1-lang/NBA3"},
        ],
    }

    questions = [
        {"id": "Q1", "question": (
            "How should the re-measured home-win rate "
            f"({recut['home_court']['measured_home_win_rate']}, "
            f"{recut['home_court']['home_wins']}/{recut['home_court']['home_games']}) be converted "
            "to the pinned home-court-advantage value in POINTS? The model currently pins the "
            "fitted 0.76 pts (fit sample 102/197). No official source defines the conversion; "
            "it must be chosen, not inferred."),
        "blocking": "re-pinning HCA; any new bet line",
        "answer_status": "OPEN — reviewer decision required",
        "source_url": STANDINGS_URL},
        {"id": "Q2", "question": (
            "Replacement-minute shares when a player is OUT are not available from any official "
            "source (no official depth chart). Top-8 shares are measured; redistribution among "
            "the available top-8 is pro rata and flagged unverified. Confirm the pro-rata "
            "convention or supply a source."),
        "blocking": "injury-impact minutes model publication",
        "answer_status": "OPEN — convention flagged, not published as verified",
        "source_url": GAMES_URL},
        {"id": "Q3", "question": (
            "Five team quarter vectors cannot be verified from the official game books "
            "(PHI@BKN 11/16, POR@MIN 11/16, MEM@CLE 11/18, PHX@SAC 11/18, UTA@LAL 11/18) and one "
            "printed row is internally inconsistent (MEM@CLE 11/18: Grizzlies table row "
            "30/41/30/24 sums to 125 vs printed final 124). Is a second official source "
            "(play-by-play) acceptable for filling these, or do they stay blank for the season?"),
        "blocking": "quarter-dependent grading for those 6 team rows",
        "answer_status": "OPEN — rows stay blank until answered",
        "source_url": GAMES_URL},
        {"id": "Q4", "question": (
            "Per-player game logs are captured for 2026-11-16..18 only (the official game-book "
            "window). Players OUT the whole window (Edwards, Morant, Sharpe, DiVincenzo, "
            "Krejci, ...) have no rows in the window. Should earlier official logs be captured "
            "for the impact baselines?"),
        "blocking": "injury-impact production model",
        "answer_status": "OPEN — flagged blanks in player_game_logs.json",
        "source_url": GAMES_URL},
        {"id": "Q5", "question": (
            "closing_lines.json has no rows, so the market-anchored prior (model line weighted "
            "by measured out-of-sample log-loss vs the closing line) cannot be computed. Which "
            "official source may be used for closing lines, if any?"),
        "blocking": "market-anchored prior publication",
        "answer_status": "OPEN — prior left blank/flagged",
        "source_url": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/closing_lines.json"},
        {"id": "Q6", "question": (
            "At the 01:45 AM revision the GSW, MEM and MIL rows (11/19 games) and all nine "
            "11/20 games were NOT YET SUBMITTED on the official injury report. Later revisions "
            "must be captured before those tips; the scheduled job should archive every "
            "15-minute revision."),
        "blocking": "rotation availability column for GSW@MEM and POR@MIL",
        "answer_status": "OPEN — banner shows revision + retrieval times",
        "source_url": INJ_URL},
    ]

    suggestions = [
        {"id": "S1", "title": "HCA points conversion", "suggestion": (
            "Choose one: (a) keep 0.76 pts until the fit sample is refreshed; (b) adopt a "
            "probit conversion using the league average margin sigma; (c) refit the 102/197 "
            "mapping on the expanded home/road log. Implement the chosen option before any "
            "new bet is published."),
        "status": "for reviewer choice — NOT implemented"},
        {"id": "S2", "title": "Injury-revision archiving", "suggestion": (
            "Extend the scheduled refresh to archive every 15-minute official revision "
            "(filling F-DE0-03) and compute consecutive diffs in the job itself."),
        "status": "for reviewer choice — NOT implemented"},
        {"id": "S3", "title": "Quarter-vector completion", "suggestion": (
            "Fetch official play-by-play quarter scores for the 6 flagged team rows when a "
            "reviewer confirms Q3; until then keep them blank and keep quarter-dependent "
            "grading blocked for those rows."),
        "status": "for reviewer choice — NOT implemented"},
        {"id": "S4", "title": "Player log depth", "suggestion": (
            "Capture at least 3 prior official game logs per injury-report player for the "
            "production-impact baselines (answers Q4)."),
        "status": "for reviewer choice — NOT implemented"},
        {"id": "S5", "title": "Correlation model for parlays", "suggestion": (
            "When the measured-rho parlay pricer lands, extend the prereg files with the "
            "rho method and always print the naive product next to the rho-adjusted price "
            "(already required by the brief; keep the prereg freeze before the first bet)."),
        "status": "for reviewer choice — NOT implemented"},
    ]

    flags = [
        # carried from session de0caf5d (CR-DE0-01), verbatim
        {"id": "F-DE0-01", "flag": ("Game ids are not chronological: 11/20 rows carry "
                                    "0022600043-0022600051, while 11/19 carry 0022600270-0022600273 "
                                    "and 11/21 0022600274-0022600279. Taken as printed (the id is "
                                    "the join key); not corrected. The Cup-label observation from "
                                    "b1ce1334's note is the printed explanation."),
         "source_url": "https://www.nba.com/games"},
        {"id": "F-DE0-02", "flag": ("Official injury-report index lags the CDN (12:45 AM PDF "
                                    "resolves; index lists through 12:30 AM)."),
         "source_url": "https://ak-static.cms.nba.com/referee/injury/"},
        {"id": "F-DE0-03", "flag": ("No archived injury revisions between 11/16 01:30 PM ET and "
                                    "11/19 12:30 AM ET in the repo."),
         "source_url": "https://ak-static.cms.nba.com/referee/injury/"},
        {"id": "F-DE0-04", "flag": ("PDF text layer: 9 POR@MIL rows with date/time blank; 2 rows "
                                    "(Kuminga, Pullin) with matchup and team blank; 6 rows with "
                                    "status missing; 10 keyed rows unreadable in the newest "
                                    "revision. RESOLVED for Kuminga/Pullin team attribution to "
                                    "Minnesota Timberwolves via official game books "
                                    "20261116_PORMIN + 20261117_PORMIN; the extraction defect "
                                    "itself remains flagged."),
         "source_url": "https://statsdmz.nba.com/pdfs/20261117/20261117_PORMIN.pdf"},
        {"id": "F-DE0-05", "flag": ("The 11/16 committed slate (data/app/official_slate_current.json) "
                                    "covers 11/15-11/18 and is stale for the 11/19-11/21 window; "
                                    "the roll-forward is CR-915-01 (this session's O7)."),
         "source_url": "https://www.nba.com/games"},
        {"id": "F-DE0-06", "flag": ("Records printed on the games pages are as of the retrieval "
                                    "time and are not reconciled with the 11/16 snapshot."),
         "source_url": "https://www.nba.com/games"},
        # this round's flags
        {"id": "F-04A-01", "flag": ("Official game book 20261118_MEMCLE: the printed Grizzlies "
                                    "SCORE BY PERIOD row '30 41 30 24 124' sums to 125, not the "
                                    "printed final 124. Row rejected by the sum gate and preserved "
                                    "verbatim; MEM quarter vector left BLANK (not inferred)."),
         "source_url": "https://statsdmz.nba.com/pdfs/20261118/20261118_MEMCLE.pdf"},
        {"id": "F-04A-02", "flag": ("Visitor period lines absent from the official game-book text "
                                    "layer in 4 books: PHI (20261116_PHIBKN), POR (20261116_PORMIN), "
                                    "PHX (20261118_PHXSAC), UTA (20261118_UTALAL). Quarter vectors "
                                    "left BLANK and flagged."),
         "source_url": GAMES_URL},
        {"id": "F-04A-03", "flag": ("Table-vs-standalone SCORE BY PERIOD conflicts in "
                                    "20261116_CHICLE (Cavaliers row corrupt), 20261118_CHIBKN "
                                    "(Nets row 21/30/26/22=99 vs final 107), 20261118_ATLOKC "
                                    "(Thunder row 30/32/32/30=124 vs final 112): the sum-valid "
                                    "standalone line is accepted, the corrupt row is preserved "
                                    "and flagged. 20261118_GSWDAL has a merged layout (Mavericks "
                                    "box totals merged into the SCORE BY PERIOD header); the "
                                    "standalone MAVERICKS line is accepted."),
         "source_url": GAMES_URL},
        {"id": "F-04A-04", "flag": ("52 player rows across the 25 books failed the "
                                    "PTS==2FG+3P+FT / TOT==OR+DR identity checks (shifted or "
                                    "garbled cells in MEMWAS/HOUMIA/GSWNOP/PHXDEN/DETSAS books) "
                                    "and were dropped and flagged, never repaired. Team totals "
                                    "were cross-summed from accepted rows and matched every "
                                    "printed final except where noted."),
         "source_url": GAMES_URL},
        {"id": "F-04A-05", "flag": ("Official team-stat pages disagree on a rounding edge: "
                                    "Toronto Raptors NetRtg +0.5 vs printed +/- 0.0 per game. "
                                    "Both values published as printed."),
         "source_url": ADV_URL},
        {"id": "F-04A-06", "flag": ("closing_lines.json rows = [] — the market-anchored prior is "
                                    "left blank and flagged (no official closing-line source "
                                    "available; see Q5)."),
         "source_url": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/closing_lines.json"},
        {"id": "EVE-F04", "flag": ("Scheduled-refresh evidence (per CR-B1-02, B1-1 artifact): runs "
                                   "44424736929 and the 5 earlier runs fail at the committed-tree "
                                   "unit-test step before any official fetch; the run body is "
                                   "unreachable via the API and manual dispatch is 403-blocked "
                                   "(EVE-F08). Cause remains unlocalised on the hosted runner. "
                                   "KEEP OPEN until a hosted run shows the failing test names. "
                                   "The local replay of the same step passes (Ran 387 OK), so no "
                                   "data defect is implied."),
         "source_url": "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/44424736929"},
    ]

    cr_answers = [
        {"cr": "CR-B1-01", "from": "session b1ce1334", "answer": (
            "DONE 2026-11-19: 25 gradeable published picks settled from the verified "
            "official finals (11/16-18); every settlement stamp carries its official game-book "
            "URL and states the grading convention of the chain (side win = actual margin sign "
            "matches the projected margin sign; total win = combined final over the originated "
            "total, per the 9 pre-existing settlements). Chain re-verified intact after "
            "settlement: 68 entries, 0 problems. Quarter-dependent grading stays blocked for "
            "the 5 flagged games (PHI 11/16, POR 11/16, MEM 11/18, PHX 11/18, UTA 11/18): "
            "those settle at final-score level with quarter sums flagged unverified in the stamp."),
         "status": "DONE 2026-11-19 — settled with stamps",
         "evidence": "data/app/ledger/ledger.jsonl (68 entries, chain intact); data/rounds/2026-11-19-04a81bce/verified/quarters_2026-11-16_18.json"},
        {"cr": "CR-DE0-01", "from": "session de0caf5d", "answer": (
            "F-DE0-01..06 are carried verbatim into this flags register and rendered on the "
            "Flagged for Review page at integration; the 12:45 AM round is linked from the "
            "Injuries banner (revision + retrieval times)."),
         "status": "answered — rendered at O7 integration",
         "evidence": "data/app/registers_04a81bce.json (flags)"},
        {"cr": "CR-DE0-02", "from": "session de0caf5d", "answer": (
            "The 12:45 AM revision is folded into the injury-round archive chain (captured by "
            "de0caf5d; 01:00-01:45 revisions captured here, zero-change diffs); banner revision "
            "line updated at integration."),
         "status": "answered",
         "evidence": "data/rounds/2026-11-19-04a81bce/raw/injury_reports/injury_round_2026-11-19.md"},
        {"cr": "CR-B1-02", "from": "session b1ce1334", "answer": (
            "B1-1 evidence appended to EVE-F04 in the flags register (runs 44424736929 + 5 "
            "earlier, unit-test step as the failing step, artifact name from the merged note). "
            "EVE-F04 stays open until a hosted run shows failing test names."),
         "status": "answered — flag kept open",
         "evidence": "data/app/registers_04a81bce.json (flags: EVE-F04)"},
        {"cr": "CR-00b0c780-06", "from": "session 00b0c780", "answer": (
            "arena_coordinates.json is used only where a coordinate entry exists; every "
            "rest/travel row without a sourced coordinate carries "
            "'travel distance unverified' and a blank distance — nothing is inferred."),
         "status": "answered",
         "evidence": "data/rounds/2026-11-19-04a81bce/verified/team_stats_recut_2026-11-19.json"},
        {"cr": "CR-915-01", "from": "session 915d2e99", "answer": (
            "Window roll-forward with regenerated lines/picks/props/parlays and per-row source "
            "URLs is the O7 integration task of this session."),
         "status": "answered at O7 integration",
         "evidence": "COORDINATION.md (O7 row)"},
    ]

    doc = {
        "round": "2026-11-19-04a81bce",
        "generated_by": "scripts/build_04a81bce_registers.py",
        "rule": ("every factual row carries its official source URL; unconfirmed values are "
                 "blank + flagged, never inferred; suggestions are for reviewer choice before "
                 "implementation"),
        "executive_summary": executive_summary,
        "questions": questions,
        "suggestions": suggestions,
        "flags": flags,
        "cr_answers": cr_answers,
        "data_index": {
            "quarters": "data/rounds/2026-11-19-04a81bce/verified/quarters_2026-11-16_18.json",
            "player_game_logs": "data/rounds/2026-11-19-04a81bce/verified/player_game_logs.json",
            "injury_report": "data/rounds/2026-11-19-04a81bce/verified/injury_report_2026-11-19.json",
            "team_stats_recut": "data/rounds/2026-11-19-04a81bce/verified/team_stats_recut_2026-11-19.json",
            "ledger_hash_check": "data/rounds/2026-11-19-04a81bce/verified/ledger_hash_check_2026-11-19.json",
            "team_stats_sources": recut["sources"],
        },
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    # Session files in the shapes scripts/build_app.py renders on the
    # Flagged / Questions / Suggestions pages (every row keeps its sources).
    sev_rank = {"F-DE0-04": "high", "F-DE0-05": "high", "EVE-F04": "high",
                "F-04A-01": "medium", "F-04A-02": "medium", "F-04A-03": "medium",
                "F-04A-04": "medium", "F-DE0-01": "medium", "F-DE0-02": "low",
                "F-DE0-03": "medium", "F-DE0-06": "low", "F-04A-05": "low",
                "F-04A-06": "medium"}
    flags_page = [{
        "id": f["id"], "area": "Official round 2026-11-19 (game books + reports)",
        "item": f["flag"], "why": (
            "Kept visible for manual review with its official source; values are never "
            "inferred and blocked rows stay blank until an owner decision."),
        "action_needed": (
            "Review against the linked official source; answer the matching question on "
            "the Open questions page where one applies."),
        "status": "open — flagged for review (does not block the site)",
        "severity": sev_rank.get(f["id"], "medium"),
        "found_on": "2026-11-19",
        "sources": [f["source_url"]],
    } for f in flags]
    (ROOT / "data" / "app" / "flags_04a81bce.json").write_text(
        json.dumps(flags_page, indent=1) + "\n", encoding="utf-8")

    questions_page = [{
        "id": q["id"], "category": "Official round 2026-11-19",
        "question": q["question"], "status": "Open — " + q["answer_status"].split("—")[-1].strip(),
        "known": ("Data captured and published with sources where an official source "
                  "exists; nothing inferred."),
        "missing": q["answer_status"] + " Blocking: " + q.get("blocking", ""),
        "next_step": "Owner decision (see suggestions register of the same round)",
        "owner": "reviewer", "sources": [q["source_url"]],
    } for q in questions]
    (ROOT / "data" / "app" / "questions_04a81bce.json").write_text(
        json.dumps(questions_page, indent=1) + "\n", encoding="utf-8")

    suggestions_page = [{
        "id": s["id"], "area": "Official round 2026-11-19",
        "suggestion": s["title"], "why": s["suggestion"],
        "options": s["suggestion"],
        "recommended_option": "reviewer chooses before implementation",
        "dependency": "owner decision", "decision": s["status"],
        "sources": ["https://github.com/wingbangboozle1-lang/NBA3/blob/main/"
                    "data/app/registers_04a81bce.json"],
    } for s in suggestions]
    (ROOT / "data" / "app" / "suggestions_04a81bce.json").write_text(
        json.dumps(suggestions_page, indent=1) + "\n", encoding="utf-8")

    print(f"registers written: {OUT} "
          f"(flags {len(flags)}, questions {len(questions)}, suggestions {len(suggestions)}, "
          f"cr_answers {len(cr_answers)})")
    print("session files: data/app/{flags,questions,suggestions}_04a81bce.json")


if __name__ == "__main__":
    main()
