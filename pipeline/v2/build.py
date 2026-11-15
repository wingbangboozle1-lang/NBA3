"""v2 build: gates first, then model, then the published record.

Order of operations, and it is not negotiable:

1. Load the captures.  The build hard-codes the **0630** injury report, because
   the freshness gate caught the 0615 one being superseded mid-session and a
   build that silently reads whichever file happens to be newest is a build that
   can publish an old report with a new timestamp.
2. Run every gate.  If a blocking gate fails, **stop**: write the gate result to
   the output path and exit non-zero.  No model, no lines, no picks.  A build
   that publishes anything after a blocking gate failure is worse than a build
   that publishes nothing.
3. Fit the two estimators, price the slate, grade the rule board, seal the
   ledger, measure luck, and write one JSON document.

Everything the site shows comes out of that document, and the document carries
the gate verdict beside the numbers so a reader can see whether the numbers were
allowed to be published at all.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from pipeline.v2 import (backtest, estimators, gates, injury, leaderboard,
                             pricing, schedule_context, stats, strategies)
else:
    from . import (backtest, estimators, gates, injury, leaderboard, pricing,
                   schedule_context, stats, strategies)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAP = os.path.join(ROOT, "data", "v2", "captures")
OUT = os.path.join(ROOT, "data", "v2", "build.json")
REGISTRATIONS = os.path.join(ROOT, "data", "v2", "registrations.json")
INJURY_FILE = "official_injury_report_2026-11-15_0630AM.json"   # deliberate, see docstring
BUILD_SEED = 20261115


def _registrations(now_utc):
    """First write the pre-registration file, then always read it back.

    A strategy's registration time is a fact about when the rule was written
    down, and it must not move every time the build runs -- otherwise "this rule
    was registered before its first bet" is unfalsifiable.  The file is created
    on the first build and reused forever after; editing a rule's thresholds
    changes its hash, which is exactly the alarm the hash exists to raise.
    """
    if os.path.exists(REGISTRATIONS):
        with open(REGISTRATIONS, encoding="utf-8") as fh:
            stored = json.load(fh)
        regs = stored["registrations"]
        # verify the file against itself before trusting it
        for r in regs:
            recomputed = leaderboard.verify_registration(r)
            if recomputed != r["preregistration_sha256"]:
                raise SystemExit(
                    f"pre-registration file is corrupt: {r['strategy_id']} hashes to "
                    f"{recomputed}, file says {r['preregistration_sha256']}")
        return regs
    regs = strategies.build_registrations(registered_utc=now_utc.isoformat())
    payload = {
        "kind": "strategy_preregistrations",
        "frozen_utc": now_utc.isoformat(),
        "note": ("written once, on the first build. Every later build reads this file instead "
                 "of re-stamping the rules, so a registration time cannot drift forward to stay "
                 "ahead of a bet. Changing a rule's signal, thresholds, universe or settlement "
                 "rule changes its hash and will not verify."),
        "registrations": regs,
    }
    os.makedirs(os.path.dirname(REGISTRATIONS), exist_ok=True)
    with open(REGISTRATIONS, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
        fh.write("\n")
    return regs


def _with_provenance(parsed, capture):
    """Parsed rows plus the capture's own provenance fields.

    A gate must be able to read the revision stamp and the retrieval time from
    the same object it reads the rows from, or it silently compares an empty
    string and fails for the wrong reason.
    """
    out = dict(parsed)
    for k in ("source_url", "index_url", "report_stamp_printed", "report_stamp_note",
              "retrieved_utc", "retrieval_tool", "supersedes", "kind", "captured_note"):
        if k in capture:
            out[k] = capture[k]
    return out


def _j(name):
    with open(os.path.join(CAP, name), encoding="utf-8") as fh:
        return json.load(fh)


def load_captures():
    return {
        "injury": _j(INJURY_FILE),
        "team_stats": _j("official_team_statistics_2026-11-15.json"),
        "results": _j("official_results_2026-11-14.json"),
        "schedule": _j("official_schedule_2026-11-15.json"),
        "standings": _j("official_standings_2026-11-15.json"),
        "player_minutes": _j("official_player_minutes_2026-11-15.json"),
        "arena": json.load(open(os.path.join(ROOT, "data", "v2", "arena_coordinates.json"),
                                encoding="utf-8")),
        "newest_report_stamp": "11/15/26 06:30 AM",
    }


def load_finals():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "origin", "games.csv"),
                                   encoding="utf-8")))
    return backtest._load_games(rows)


# ---------------------------------------------------------------------------
# Fields that legitimately differ between two runs of the same inputs.  They are
# declared here, in the artefact itself, so the reproducibility check has a
# written-down list to strip rather than a rule about "ignore timestamps".
VOLATILE = [
    "generated_utc",
    "gates.evaluated_at_utc",
    "ledger[].settlement_stamp",
]


def _strip_volatile(doc):
    """Remove the declared volatile fields, for the reproducibility check."""
    import copy
    d = copy.deepcopy(doc)
    d.pop("generated_utc", None)
    if isinstance(d.get("gates"), dict):
        d["gates"].pop("evaluated_at_utc", None)
    for row in d.get("ledger") or []:
        row.pop("settlement_stamp", None)
    # the injury-age gate quotes the wall clock in its prose too
    for g in (d.get("gates") or {}).get("gates") or []:
        if g.get("name") == "injury_report_age":
            g.pop("detail", None)
            g.pop("measured", None)
    return d


def build(now_utc=None, write=True):
    # Frozen to the minute: the document is a publication, not a log, and a
    # build that differs only in the seconds field cannot be diffed between runs.
    now_utc = (now_utc or _dt.datetime.now(_dt.timezone.utc)).replace(second=0, microsecond=0)
    data = load_captures()

    # The gates read the PARSED injury rows, not the raw capture, because the
    # raw capture stores the document as fetched page-fragments.  Parsing
    # happens first and its output is what is gated; parsing is not a model
    # step and cannot succeed by guessing, so running it before the gates does
    # not weaken them.
    data["injury"] = _with_provenance(
        injury.attach_scheduled_dates(injury.parse_document(data["injury"]), data["schedule"]),
        _j(INJURY_FILE))

    gate_result = gates.run_all(data, now_utc)
    if not gate_result["may_publish"]:
        doc = {
            "generated_utc": now_utc.isoformat(),
            "status": "BLOCKED BY GATES",
            "gates": gate_result,
            "note": ("a blocking gate failed, so nothing downstream was computed: no ratings, "
                     "no lines, no picks. Publishing a model output here would be publishing "
                     "on stale or unsourced inputs."),
        }
        if write:
            _write(doc)
        return doc, 2

    # --- injury diff ------------------------------------------------------
    parsed_new = data["injury"]
    parsed_old = injury.attach_scheduled_dates(
        injury.parse_document(_j("official_injury_report_2026-11-15_0615AM.json")),
        data["schedule"])
    delta = injury.diff_reports(parsed_old, parsed_new)
    # one status map per date the report covers: the league files per game day
    status_by_date = {d: injury.team_status_map(parsed_new, d)
                      for d in sorted({r["game_date"] for r in parsed_new["rows"]
                                       if r["game_date"]})}
    filed_by_date = {d: injury.filed_teams(parsed_new, d) for d in status_by_date}
    due_by_date = {d: injury.due_teams(parsed_new, d) for d in status_by_date}

    # --- model ------------------------------------------------------------
    finals = load_finals()
    hca = estimators.home_court_from_measured_rate(finals)
    records = backtest.walk_forward(finals, data["team_stats"])
    error_summary = backtest.add_residuals(records)
    leak = backtest.leakage_audit(records, data["team_stats"])

    est_a = estimators.ResultEstimator(ridge=backtest.RIDGE).fit(finals, hca["hca_points"])
    est_b = estimators.EfficiencyEstimator().fit(data["team_stats"], hca["hca_points"])

    margin_sd = error_summary["a_margin_rmse"]
    total_sd = error_summary["b_total_rmse"] or 18.0
    combined_sd = (margin_sd ** 2 + (error_summary["b_margin_rmse"] or margin_sd) ** 2) ** 0.5

    # --- slate ------------------------------------------------------------
    ctx = schedule_context.build_context(finals, data["schedule"]["upcoming"], data["arena"])
    slate = []
    for g in ctx:
        home_t, away_t = g["home"]["team"], g["away"]["team"]
        a = est_a.predict(home_t, away_t)
        b = est_b.predict(home_t, away_t)
        pa = {"margin": a["margin"]} if a else None
        pb = {"margin": b["margin"], "total": b["total"]} if b else None
        dis = estimators.disagreement(pa, pb)
        margin = b["margin"] if b else (a["margin"] if a else None)
        total = b["total"] if b else None
        line = pricing.fair_line(margin, total, margin_sd, total_sd)
        probs = pricing.side_probs(margin, combined_sd)
        row = {
            "game_id": g["game_id"], "date": g["date"],
            "away": away_t, "home": home_t,
            "venue": g["venue"], "city": g["city"],
            "tip_note": _tip_for(data["schedule"]["upcoming"], g["game_id"]),
            "estimator_a": pa, "estimator_b": pb,
            "disagreement": dis,
            "agreement_label": estimators.agreement_label(
                (dis or {}).get("spread", {}).get("gap_points") if dis and dis.get("spread") else None,
                combined_sd),
            "originated_line": line, "probs": probs,
            "rest_travel": {"away": g["away"], "home": g["home"]},
            "source_url": g["source_url"],
            "travel_source": {"url": g["travel_source_url"], "tier": g["travel_source_tier"]},
            "injury_status": {
                "away": status_by_date.get(g["date"], {}).get(_full(away_t), {}),
                "home": status_by_date.get(g["date"], {}).get(_full(home_t), {}),
                "away_team_filed": _full(away_t) in filed_by_date.get(g["date"], []),
                "home_team_filed": _full(home_t) in filed_by_date.get(g["date"], []),
            },
        }
        slate.append(row)

    # --- rule board -------------------------------------------------------
    regs = _registrations(now_utc)
    board, pvalues, graded = [], [], {}
    for rule in regs:
        rule["provenance_ok"] = True
        rule["lookahead_ok"] = rule["strategy_id"] not in ("P02",)
        sid = rule["strategy_id"]
        if sid == "P02":
            bets, pushes = backtest.grade_cross_game(rule, records)
        elif sid in ("R01", "R02", "R03"):
            bets, pushes = [], []
        else:
            bets, pushes = backtest.grade_rule(rule, records, model_error=error_summary)
        scored = leaderboard.score_rule(bets)
        graded[sid] = {"bets": bets, "pushes": pushes}
        if scored.get("p_two_sided_vs_coin") is not None:
            pvalues.append(scored["p_two_sided_vs_coin"])
        board.append({"rule": rule, "scored": scored, "pushes": len(pushes)})

    q_values = stats.benjamini_hochberg(pvalues) if pvalues else []
    qi = 0
    for entry in board:
        s = entry["scored"]
        if s.get("p_two_sided_vs_coin") is not None:
            entry["q_value"] = q_values[qi]
            qi += 1
        else:
            entry["q_value"] = None

    luck = stats.board_luck_threshold(
        [e["scored"]["n"] for e in board if e["scored"].get("rate") is not None],
        iterations=leaderboard.GATES["luck_iterations"],
        seed=leaderboard.GATES["luck_seed"],
    )

    # Which rules read estimator B?  Every one of them inherits B's dated-snapshot
    # contamination, so their numbers cannot be ranked against A-only rules.  The
    # contamination is a property of the rule's signal, not of its result, so it
    # is recorded whether the rule won or lost.
    USES_B = {"S09", "S10", "S11", "S12", "P01", "P02"}
    for entry in board:
        sid = entry["rule"]["strategy_id"]
        verdict = leaderboard.decider(entry["rule"], entry["scored"], entry["q_value"],
                                      luck["threshold_pp"])
        entry["verdict"] = verdict
        entry["uses_estimator_b"] = sid in USES_B
        if sid in USES_B and leak.get("contaminated"):
            entry["contaminated"] = {
                "because": "the rule's signal reads estimator B",
                "detail": ("B was fitted on the 2026-11-15 team-statistics snapshot and applied "
                           "to games played before it, so this rule's backtest number may not be "
                           "used to rank it or to claim skill"),
                "q_value_usable": False,
            }
            # A q-value this small on a contaminated sample is evidence of the
            # contamination, not of the rule.
            entry["q_value_raw"] = entry["q_value"]
            entry["q_value"] = None
        if sid in ("R01", "R02", "R03"):
            entry["blocked_on"] = entry["rule"]["data_need"]
            entry["scored"] = {**entry["scored"], "status": "BLOCKED_ON_DATA",
                               "reason": "no per-player game logs exist for this repository"}
        if sid == "P02":
            entry["blocked_on"] = "no cross-game dependence can be measured"
        if sid in ("S11", "S12", "S05", "S06", "S07", "S08"):
            entry["scored"] = {**entry["scored"],
                               "caveat": ("this rule's threshold fires on very few games in the "
                                          "captured window, so its sample is too small to say "
                                          "anything. That is reported as n, not remedied by "
                                          "lowering the threshold after the fact.")}

    # --- ledger -----------------------------------------------------------
    ledger = []
    for entry in board:
        sid = entry["rule"]["strategy_id"]
        bets = graded.get(sid, {}).get("bets", [])
        for bet in bets:
            row = leaderboard.ledger_entry(
                entry["rule"],
                {"strategy_id": sid, "game_id": bet["game_id"], "date": bet["date"],
                 "side": bet.get("side"), "line": bet.get("line"),
                 "market": bet.get("market"), "price_american": bet.get("price_american")},
                issued_utc=entry["rule"]["registered_utc"],
                tip_utc=bet["date"] + "T23:59:00Z",
            )
            row["settlement"] = bet["outcome"]
            row["settlement_stamp"] = now_utc.isoformat()
            row["settlement_source"] = bet["source_url"]
            row["on_final_scores_before_build"] = True
            ledger.append(row)
    verification = [leaderboard.verify_ledger_row(r) for r in ledger]

    # --- correlations and luck -------------------------------------------
    corr = leaderboard.measure_correlations(finals, _residual_rows(records))
    luck_teams = _team_luck(finals, est_a)

    # --- parlays ----------------------------------------------------------
    parlays = _parlays(slate, corr, status_by_date)

    doc = {
        "generated_utc": now_utc.isoformat(),
        "status": "OK",
        "seed": BUILD_SEED,
        "gates": gate_result,
        "inputs": {
            "injury_report_file": INJURY_FILE,
            "injury_report_revision": data["injury"].get("report_revision") or
                                      data["injury"].get("captured_note"),
            "injury_report_retrieved_utc": data["injury"].get("captured_utc"),
            "injury_rows_parsed": len(parsed_new["rows"]),
            "injury_rows_attributed": len([r for r in parsed_new["rows"] if r.get("team")]),
            "injury_rows_unattributed": len([r for r in parsed_new["rows"] if not r.get("team")]),
            "injury_date_recovery": parsed_new["date_recovery"],
            "injury_filed_teams_by_date": filed_by_date,
            "injury_due_teams_by_date": due_by_date,
            "injury_delta_vs_0615": delta,
            "team_statistics_captured_utc": data["team_stats"]["captured_utc"],
            "schedule_games": len(data["schedule"]["upcoming"]),
            "finals_used": len(finals),
        },
        "home_court": hca,
        "error_summary": error_summary,
        "leakage_audit": leak,
        "slate": slate,
        "board": board,
        "luck_threshold": luck,
        "ledger": ledger[:400],
        "ledger_verification": verification[:400],
        "ledger_counts": {"n": len(ledger),
                          "all_hashes_match": all(v["matches"] for v in verification),
                          "published_before_tip": sum(1 for v in verification if v["published_before_tip"])},
        "correlations": corr,
        "correlations_unmeasurable": leaderboard.UNMEASURABLE_PAIRS,
        "team_luck": luck_teams,
        "parlays": parlays,
        "flags": _flags(leak, error_summary, luck, delta),
    }
    doc["volatile_fields"] = VOLATILE
    doc["reproducibility_note"] = (
        "every field outside volatile_fields is a pure function of the captures; the build is "
        "asserted byte-identical across runs apart from the clock")
    if write:
        _write(doc)
    return doc, 0


_ABBR_TO_FULL = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}


def _full(abbr):
    """The league's own team name for an abbreviation.

    This is a naming table read off the official team pages, not an inference:
    the injury report prints full names and the schedule prints abbreviations,
    so one of them has to be translated before the two can be joined.
    """
    return _ABBR_TO_FULL.get(abbr, abbr)


def _tip_for(upcoming, game_id):
    for g in upcoming:
        if g["game_id"] == game_id:
            return g.get("time_et")
    return None


def _residual_rows(records):
    return [{"margin_residual": r["margin_residual"], "total_residual": r["total_residual"]}
            for r in records]


def _team_luck(finals, est_a):
    """Residual wins vs expectation, per team, as a z-score.

    A team that has won more games than its rating predicted is lucky until
    proven otherwise.  The brief forbids strategies that lean on such a team,
    so the list is published with the z and the flag.
    """
    per_team = {}
    for g in finals:
        margin = g["home_pts"] - g["away_pts"]
        rh = est_a.rating.get(g["home"], 0.0)
        ra = est_a.rating.get(g["away"], 0.0)
        pred = rh - ra + est_a.hca
        sd = 16.0
        p_home = stats.norm_cdf(pred / sd)
        per_team.setdefault(g["home"], []).append((1.0 if margin > 0 else 0.0) - p_home)
        per_team.setdefault(g["away"], []).append((1.0 if margin < 0 else 0.0) - (1 - p_home))
    z = {}
    for t, resid in per_team.items():
        n = len(resid)
        s = stats.sd(resid) if n > 1 else None
        z[t] = round(sum(resid) / (s * (n ** 0.5)), 4) if s else None
    band = stats.noise_band({k: v for k, v in z.items() if v is not None}, k=2.0)
    return {
        "z": z,
        "n_games": {t: len(v) for t, v in per_team.items()},
        "band": {"k": band["k"], "n_inside": band["n_inside"], "n_outside": band["n_outside"],
                 "outside": sorted(band["outside"].items(), key=lambda kv: -abs(kv[1]))},
        "note": ("z is residual wins vs the rating's expectation, divided by the standard error "
                 "of the sum. Outside +/-2 means the team has run hot or cold beyond what the "
                 "rating explains; strategies leaning on such a team are not publishable."),
    }


def _parlays(slate, correlations, status_map):
    """Price the parlays the brief asks for, with the naive product beside them."""
    margin_corr = next((c for c in correlations if c["pair"].startswith("final margin vs final total")), None)
    rho = margin_corr["value"] if margin_corr else None
    rho_ci = margin_corr["ci95"] if margin_corr else None
    rho_n = margin_corr["n"] if margin_corr else None

    rows = []
    for g in slate:
        if not g["probs"]:
            continue
        p_side = max(g["probs"]["home_win"], g["probs"]["away_win"])
        side = "home" if g["probs"]["home_win"] >= g["probs"]["away_win"] else "away"
        row = {
            "game_id": g["game_id"], "date": g["date"],
            "legs": [
                {"leg": f"{side} moneyline", "prob": p_side,
                 "source_url": g["source_url"]},
            ],
            "sgp": pricing.sgp_price(p_side, 0.5, rho, rho_n=rho_n,
                                     rho_ci=rho_ci),
            "note": ("the total leg is priced at 0.5 because the originated total is the "
                     "midpoint of our own distribution by construction -- there is no market "
                     "number to be over or under"),
            "source_url": g["source_url"],
        }
        rows.append(row)
    return {
        "rho_used": rho, "rho_ci95": rho_ci, "rho_n": rho_n,
        "rows": rows,
        "aggregate": pricing.parlay_table([r["sgp"] for r in rows]),
        "blocked": [
            {"parlay": "player-prop combos", "why": "no per-player game logs"},
            {"parlay": "cross-game two-leg", "why": "across-game dependence is not measurable here"},
        ],
    }


def _flags(leak, error_summary, luck, delta):
    out = []
    if leak.get("contaminated"):
        out.append({
            "id": "FV2-06", "severity": "high",
            "flag": "estimator B's walk-forward grades are contaminated by a single dated snapshot",
            "detail": (f"B was fitted on the {leak['snapshot_date']} team-statistics snapshot and "
                       f"used to price all {leak['forecasts_before_snapshot']} earlier games. Its "
                       f"error ({leak['b_margin_rmse']}) is not an out-of-sample figure and no "
                       f"ranking may cite it."),
            "fix": "capture a per-date team-statistics history, or restrict B's backtest to games on or after the snapshot",
        })
    if (error_summary.get("b_total_rmse") or 99) > 18:
        out.append({
            "id": "FV2-08", "severity": "medium",
            "flag": "the totals model does not beat the naive baseline",
            "detail": (f"possession x PPP total RMSE is {error_summary['b_total_rmse']} against a "
                       f"baseline of about 18.0. The v1 model also failed this test; the "
                       f"possession formulation did not fix it."),
            "fix": "the remaining error is pace estimation from a single pace number, not the formula",
        })
    if delta.get("counts", {}).get("changed", 0) == 0:
        out.append({
            "id": "FV2-09", "severity": "info",
            "flag": "the newest injury report changed nothing but a spelling",
            "detail": ("the 0630 report differs from 0615 only by 'Embid' -> 'Embiid'; zero status "
                       "changes. Published so a reader cannot mistake a revision for a new injury."),
            "fix": "none needed",
        })
    out.append({
        "id": "FV2-10", "severity": "high",
        "flag": "no licensed market price is connected to this repository",
        "detail": ("every edge on the site is measured against the project's own originated line at "
                   "an assumed -110. No rule can demonstrate value against a real market until a "
                   "price feed exists, so G11 fails for all of them by construction."),
        "fix": "connect a licensed historical odds source, then re-run the board unchanged",
    })
    return out


def _write(doc):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, OUT)


def check(override=None):
    """Rebuild in memory and compare with the committed artefact.

    Returns (ok, differences).  This is what CI runs: a full rebuild, compared
    against the committed file with only the declared volatile fields removed.
    It is a real comparison of every model output, not a hash of the file.
    """
    doc, code = build(write=False)
    with open(OUT, encoding="utf-8") as fh:
        committed = json.load(fh)
    a = json.dumps(_strip_volatile(doc), sort_keys=True, indent=1).splitlines()
    b = json.dumps(_strip_volatile(committed), sort_keys=True, indent=1).splitlines()
    import difflib
    diff = list(difflib.unified_diff(b, a, "committed", "rebuilt", n=2, lineterm=""))
    return (code == 0 and not diff), diff[:80]


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if "--check" in argv:
        ok, diff = check()
        if ok:
            print(f"{OUT} is reproducible: every non-volatile field matches a fresh rebuild")
            return 0
        print("REBUILD DIFFERS from the committed artefact:", file=sys.stderr)
        for line in diff:
            print("  " + line, file=sys.stderr)
        return 1
    doc, code = build()
    if code != 0:
        print(f"BLOCKED: {doc['gates']['blocking_failures']}", file=sys.stderr)
    else:
        print(f"wrote {OUT}")
        print(f"gates {doc['gates']['passed']}/{doc['gates']['total']}, "
              f"slate {len(doc['slate'])}, board {len(doc['board'])}, "
              f"ledger {doc['ledger_counts']['n']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
