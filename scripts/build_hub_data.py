#!/usr/bin/env python3
"""Build data/hub/dashboard.json — the single consolidated data set for the NBA3 dashboard.

Inputs (all already verified by the sessions that produced them):
  data/hub/slate.tsv          31 games, official sources (nba.com/schedule + official schedule PDF)
  data/hub/teams_official.tsv 30 teams, official NBA.com teams-advanced table
  data/hub/injuries.tsv       122 rows, official NBA injury report 11/13/26 07:30 PM
  data/hub/*.json             sources, flags, questions, suggestions, repo review, verification, summary
  data/origin/model_output.json  origination engine (lines, strategies, correlations, game flow, props)
  data/model/lines_2026-27.json  second independent engine (lines + fair prices, 22 games)
  data/picks/picks_2026-11-14_to_16.json  picks for the 3-day window (22 games)
  data/model/validation_report.json  gate results of the second engine

Nothing is invented here: this script only merges, joins and computes arithmetic that is
reproducible from the inputs.  Every row keeps the source id it was verified against.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "data" / "hub"

INJURY_SRC = "S02"   # official injury report 11/13/26 07:30 PM
SCHEDULE_SRC = "S04"  # nba.com/schedule
TEAM_SRC = "S06"     # nba.com/stats/teams/advanced
MODEL_SRC = "S18"    # derived from the repository artefacts


def read_tsv(path: Path) -> list[dict]:
    """Read a TSV.  Missing trailing fields are empty strings, never None."""
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return [{k: ("" if v is None else v) for k, v in r.items()} for r in rows]


def read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def fnum(value, digits=1, blank=""):
    """Format a number.  None -> blank (never a guess)."""
    if value is None or value == "":
        return blank
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return blank


def pct(value, digits=1):
    if value is None or value == "":
        return ""
    return f"{float(value) * 100:.{digits}f}%"


def main() -> None:
    slate = read_tsv(HUB / "slate.tsv")
    teams = read_tsv(HUB / "teams_official.tsv")
    injuries = read_tsv(HUB / "injuries.tsv")

    sources = read_json(HUB / "sources.json")
    flags = read_json(HUB / "flags.json")
    questions = read_json(HUB / "questions.json")
    suggestions = read_json(HUB / "suggestions.json")
    repo_review = read_json(HUB / "repo_review.json")
    verification = read_json(HUB / "verification.json")
    summary = read_json(HUB / "summary.json")

    model = read_json(ROOT / "data" / "origin" / "model_output.json")
    edge_lines = read_json(ROOT / "data" / "model" / "lines_2026-27.json")
    edge_picks = read_json(ROOT / "data" / "picks" / "picks_2026-11-14_to_16.json")
    edge_validation = read_json(ROOT / "data" / "model" / "validation_report.json")

    # ---------------------------------------------------------------- indexes
    origin_lines = {(l["date"], l["away"], l["home"]): l for l in model["lines"]}
    edge_line_by = {(l["date"], l["away"], l["home"]): l for l in edge_lines}
    picks_by = {}
    for p in edge_picks.get("picks", []):
        matchup = p["matchup"].replace(" @ ", "@")
        away, home = matchup.split("@")
        picks_by[(p["date"], away.strip(), home.strip())] = p

    team_name = {t["team"]: t["name"] for t in model.get("team_ratings", {}).values()}
    name_to_abbr = {v: k for k, v in team_name.items()}

    # injuries, indexed by (date, team abbreviation)
    inj_by_team: dict[tuple[str, str], list[dict]] = {}
    unknown_teams = set()
    for row in injuries:
        row = dict(row)
        row["src"] = INJURY_SRC
        abbr = name_to_abbr.get(row["team"])
        if abbr is None:
            unknown_teams.add(row["team"])
        row["team_abbr"] = abbr or ""
        inj_by_team.setdefault((row["date"], abbr or row["team"]), []).append(row)
    if unknown_teams:
        raise SystemExit(f"injury team names not found in the official team table: {sorted(unknown_teams)}")

    impact_by_key = {}
    for r in model.get("injury_impact", []):
        impact_by_key[(r["date"], r["team"])] = r

    # ---------------------------------------------------------------- slate rows
    slate_rows = []
    for g in slate:
        key = (g["date"], g["away"], g["home"])
        line = origin_lines.get(key)
        eline = edge_line_by.get(key)
        pick = picks_by.get(key)
        home_rows = inj_by_team.get((g["date"], g["home"]), [])
        away_rows = inj_by_team.get((g["date"], g["away"]), [])

        def status_list(rows, statuses):
            return [r["player"] for r in rows if r["status"] in statuses]

        def submitted(rows):
            return any(r["status"] == "NOT YET SUBMITTED" for r in rows)

        row = {
            "date": g["date"],
            "time_et": g["time_et"],
            "away": g["away"],
            "away_name": team_name.get(g["away"], g["away"]),
            "home": g["home"],
            "home_name": team_name.get(g["home"], g["home"]),
            "venue": g["venue"],
            "city": g["city"],
            "game_id": g["game_id"],
            "sched_game_no": g["sched_game_no"],
            "competition": g["competition"],
            "nba_url": g["nba_url"],
            "src_schedule": SCHEDULE_SRC,
            "src_injury": INJURY_SRC,
            "src_model": MODEL_SRC,
            # availability from the newest official report
            "report_published": bool(home_rows or away_rows),
            "home_submitted": None if not (home_rows or away_rows) else (not submitted(home_rows)),
            "away_submitted": None if not (home_rows or away_rows) else (not submitted(away_rows)),
            "home_out": status_list(home_rows, ("Out",)),
            "home_doubtful": status_list(home_rows, ("Doubtful", "Questionable", "Probable")),
            "away_out": status_list(away_rows, ("Out",)),
            "away_doubtful": status_list(away_rows, ("Doubtful", "Questionable", "Probable")),
            "minutes_at_risk_home": None,
            "minutes_at_risk_away": None,
        }
        impact_h = impact_by_key.get((g["date"], g["home"]))
        impact_a = impact_by_key.get((g["date"], g["away"]))
        if impact_h:
            row["minutes_at_risk_home"] = impact_h.get("minutes_vacuum_quantified")
            row["minutes_captured_home"] = impact_h.get("captured_players")
        if impact_a:
            row["minutes_at_risk_away"] = impact_a.get("minutes_vacuum_quantified")
            row["minutes_captured_away"] = impact_a.get("captured_players")

        # originated line (primary engine)
        if line:
            row["line_spread_home"] = line["orig_spread_home"]
            row["line_total"] = line["orig_total"]
            row["line_total_lo"] = line["total_lo"]
            row["line_total_hi"] = line["total_hi"]
            row["line_p_home"] = line["p_home_win"]
            row["line_p_away"] = 1.0 - line["p_home_win"]
            row["line_exp_home_pts"] = line["exp_home_pts"]
            row["line_exp_away_pts"] = line["exp_away_pts"]
            row["line_pace"] = line["pace"]
        else:
            row["line_spread_home"] = None
            row["line_total"] = None
            row["line_total_lo"] = None
            row["line_total_hi"] = None
            row["line_p_home"] = None
            row["line_p_away"] = None
            row["line_exp_home_pts"] = None
            row["line_exp_away_pts"] = None
            row["line_pace"] = None

        # second, independent engine
        if eline:
            row["edge_spread_home"] = eline["origin_spread_home"]
            row["edge_total"] = eline["origin_total"]
            row["edge_fair_ml_home"] = eline["fair_ml_home"]
            row["edge_fair_ml_away"] = eline["fair_ml_away"]
            row["edge_p_home"] = eline["model_p_home"]
        else:
            row["edge_spread_home"] = None
            row["edge_total"] = None
            row["edge_fair_ml_home"] = None
            row["edge_fair_ml_away"] = None
            row["edge_p_home"] = None

        # Agreement between the two engines.
        #
        # The two engines publish a spread field with the SAME NAME but OPPOSITE sign
        # conventions, so they must be normalised before they are compared:
        #   origin (data/origin/model_output.json, model/build.py):
        #       orig_spread_home = -m_primary  -> a sportsbook-style LINE,
        #       negative = home favoured.
        #   edge (data/model/lines_2026-27.json, pipeline/run_model.py):
        #       origin_spread_home = predC     -> a projected HOME MARGIN,
        #       positive = home favoured.
        # Both are converted here to a single "home margin" scale
        # (positive = home is favoured) before the favourite is read off.
        if row["line_spread_home"] is not None:
            row["fav_origin"] = (row["home"] if row["line_spread_home"] < 0 else row["away"])
        else:
            row["fav_origin"] = None
        if row["line_spread_home"] is not None and row["edge_spread_home"] is not None:
            home_margin_origin = -row["line_spread_home"]
            home_margin_edge = row["edge_spread_home"]
            fav_edge = row["home"] if home_margin_edge > 0 else row["away"]
            row["fav_edge"] = fav_edge
            row["engines_agree"] = row["fav_origin"] == fav_edge
            row["spread_gap"] = abs(home_margin_origin - home_margin_edge)
            row["total_gap"] = abs((row["line_total"] or 0) - (row["edge_total"] or 0))
        else:
            row["fav_edge"] = None
            row["engines_agree"] = None
            row["spread_gap"] = None
            row["total_gap"] = None

        if pick:
            row["pick_side"] = pick.get("singles_view", "")
            row["pick_ml"] = pick.get("ml_view", "")
            row["pick_totals"] = pick.get("totals_view", "")
            row["pick_confidence"] = pick.get("confidence", "")
            row["pick_availability_flag"] = pick.get("availability", {}).get("flag", "")
            row["pick_availability_detail"] = pick.get("availability", {}).get("detail", "")
        else:
            row["pick_side"] = ""
            row["pick_ml"] = ""
            row["pick_totals"] = ""
            row["pick_confidence"] = ""
            row["pick_availability_flag"] = ""
            row["pick_availability_detail"] = ""
        slate_rows.append(row)

    # ---------------------------------------------------------------- strategies
    strategies = []
    for s in model["strategies"]:
        gates = s.get("gates", {})
        passed = sum(1 for v in gates.values() if v is True)
        total = len(gates)
        points = 3 * passed + (5 if passed == total and total else 0) + (2 if s["p"] is not None and s["p"] < 0.01 else 0)
        if passed == total:
            reward = "Eligible — publishable, subject to legal sign-off"
        elif s["p"] is not None and s["p"] < 0.05:
            reward = "Provisional — paper tracking only, not eligible"
        else:
            reward = "Not eligible — do not trade"
        strategies.append({
            "id": s["id"],
            "label": s["label"],
            "rule": s["rule"],
            "n": s["n"],
            "wins": s["wins"],
            "rate": s["rate"],
            "p": s["p"],
            "first_half_rate": s.get("first_half_rate"),
            "second_half_rate": s.get("second_half_rate"),
            "gates": gates,
            "gates_passed": passed,
            "gates_total": total,
            "passed_all_gates": s.get("passed_all_gates"),
            "points": points,
            "reward": reward,
            "verdict": s.get("verdict", ""),
            "note": s.get("note", ""),
            "src": MODEL_SRC,
        })
    strategies.sort(key=lambda x: (-x["points"], -(x["p"] if x["p"] is not None else 1)))
    for rank, s in enumerate(strategies, 1):
        s["rank"] = rank

    # ---------------------------------------------------------------- correlations
    correlations = []
    for r in model["correlations"]["rows"]:
        correlations.append({
            "pair": r["pair"],
            "stat": r["stat"],
            "value": r["value"],
            "ci95": r["ci95"],
            "n": r["n"],
            "verified": r["verified"],
            "note": r["note"],
            "src": ("S20" if r.get("source") == "https://www.nba.com/games?date=" else MODEL_SRC),
        })

    # ---------------------------------------------------------------- injury impact
    injury_impact = []
    for r in model.get("injury_impact", []):
        injury_impact.append({
            "date": r["date"],
            "team": r["team"],
            "opponent": r["opponent"],
            "home_away": r["home_away"],
            "report_submitted": r.get("report_submitted"),
            "players_listed": r.get("players_listed"),
            "out_or_doubtful": r.get("out_or_doubtful"),
            "minutes_vacuum_quantified": r.get("minutes_vacuum_quantified"),
            "minutes_vacuum_unquantified": r.get("minutes_vacuum_unquantified"),
            "captured_players": r.get("captured_players"),
            "details": r.get("details", []),
            "src": INJURY_SRC,
        })

    # ---------------------------------------------------------------- props
    props = []
    for r in model.get("player_props", []):
        props.append({
            "date": r["date"],
            "team": r["team"],
            "opponent": r["opponent"],
            "player": r["player"],
            "gp": r.get("gp"),
            "status": r.get("status"),
            "season_min": r.get("season_min"),
            "season_pts": r.get("season_pts"),
            "season_reb": r.get("season_reb"),
            "season_ast": r.get("season_ast"),
            "season_fg3m": r.get("season_fg3m"),
            "avail_weight": r.get("avail_weight"),
            "line_verified": r.get("line_verified"),
            "verification_note": r.get("verification_note", ""),
            "src_player": r.get("source_player", ""),
            "src_injury": r.get("source_injury", ""),
            "src": ["S09", "S02"],
        })

    # ---------------------------------------------------------------- game flow
    gf = model.get("game_flow", {})
    gameflow = {
        "games": gf.get("games"),
        "ot_games": gf.get("ot_games"),
        "ot_rate": gf.get("ot_rate"),
        "home_wins": gf.get("home_wins"),
        "home_games": gf.get("home_games"),
        "home_margin_mean": gf.get("home_margin_mean"),
        "avg_total": gf.get("avg_total"),
        "avg_total_regulation": gf.get("avg_total_regulation"),
        "avg_total_ot": gf.get("avg_total_ot"),
        "derived_hca": gf.get("derived_hca"),
        "derived_hca_p": gf.get("derived_hca_p"),
        "derived_hca_df": gf.get("derived_hca_df"),
        "resid_sd_margin": gf.get("resid_sd_margin"),
        "resid_sd_total": gf.get("resid_sd_total"),
        "lg_off_rtg": gf.get("lg_off_rtg"),
        "lg_pace": gf.get("lg_pace"),
        "b2b_games": gf.get("b2b_games"),
        "b2b_rate": gf.get("b2b_rate"),
        "rest_distribution": gf.get("rest_distribution", {}),
        "src": MODEL_SRC,
    }

    pace_leaders = []
    for t in gf.get("pace_leaders", []):
        pace_leaders.append({
            "team": t["team"],
            "pace": t["pace"],
            "off_rtg": t["off_rtg"],
            "def_rtg": t["def_rtg"],
            "net_rtg": t["net_rtg"],
            "src": TEAM_SRC,
        })
    pace_leaders.sort(key=lambda x: -(x["pace"] or 0))

    # ---------------------------------------------------------------- model integrity
    integrity = model.get("integrity", {})
    official_gp_total = sum(int(t["gp"]) for t in teams)
    integrity_rows = []
    for r in teams:
        captured = integrity.get("per_team_mismatch", {}).get(r["team"])
        integrity_rows.append({
            "team": r["team"],
            "name": team_name.get(r["team"], r["team"]),
            "official_gp": int(r["gp"]),
            "official_w": int(r["w"]),
            "official_l": int(r["l"]),
            "captured_team_games": captured,
            "match": "yes" if captured == int(r["gp"]) else "NO",
            "src": TEAM_SRC,
        })
    integrity_rows.sort(key=lambda x: x["team"])

    # ---------------------------------------------------------------- dashboard
    dashboard = {
        "meta": {
            "title": "NBA3 - NBA line origination, validation and review dashboard",
            "generated": summary["generated"],
            "scope": summary["scope"],
            "session": "arena/99eabb04-nba3",
            "window": "2026-11-13 to 2026-11-16 (31 games, three-day maximum)",
            "model_generated": model.get("generated_utc"),
            "data_through": model.get("data_through"),
            "season": model.get("season"),
        },
        "sources": sources,
        "summary": summary,
        "slate": slate_rows,
        "teams": [dict(t, src=TEAM_SRC) for t in teams],
        "integrity": {
            "official_team_games": official_gp_total,
            "captured_team_games": integrity.get("team_games_captured"),
            "mismatch": integrity.get("mismatch"),
            "games_captured": integrity.get("games_captured"),
            "rows": integrity_rows,
            "src": TEAM_SRC,
        },
        "lines": {
            "rows": [
                {
                    "date": l["date"], "away": l["away"], "home": l["home"], "time_et": l["time_et"],
                    "competition": l["competition"],
                    "spread_home": l["orig_spread_home"],
                    "total": l["orig_total"],
                    "total_lo": l["total_lo"], "total_hi": l["total_hi"],
                    "exp_home_pts": l["exp_home_pts"], "exp_away_pts": l["exp_away_pts"],
                    "p_home": l["p_home_win"], "p_away": 1.0 - l["p_home_win"],
                    "pace": l["pace"],
                    "out_home": l.get("out_count_home"), "out_away": l.get("out_count_away"),
                    "nba_url": l.get("source_game", ""),
                    "src": MODEL_SRC,
                }
                for l in model["lines"]
            ],
        },
        "strategies": strategies,
        "correlations": correlations,
        "gameflow": gameflow,
        "pace_leaders": pace_leaders,
        "injuries": [dict(r, src=INJURY_SRC) for r in injuries],
        "injury_impact": injury_impact,
        "props": props,
        "picks": [dict(p, src=MODEL_SRC) for p in edge_picks.get("picks", [])],
        "parlays": [dict(p, src=MODEL_SRC) for p in edge_picks.get("parlay_combos", [])],
        "strategy_status": edge_picks.get("strategy_status", {}),
        "pricing_note": edge_picks.get("pricing_note", ""),
        "edge_validation": edge_validation,
        "models": model.get("models", {}),
        "model_selection": model.get("model_selection", {}),
        "home_court": model.get("home_court", {}),
        "skill": model.get("skill", {}),
        "league": model.get("league", {}),
        "flags": flags,
        "questions": questions,
        "suggestions": suggestions,
        "repo_review": repo_review,
        "verification": verification,
    }
    out = HUB / "dashboard.json"
    out.write_text(json.dumps(dashboard, indent=1, default=str), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: "
          f"{len(slate_rows)} slate rows, {len(injuries)} injury rows, {len(strategies)} strategies, "
          f"{len(correlations)} correlations, {len(props)} prop rows, {len(flags)} flags, "
          f"{len(questions)} questions, {len(suggestions)} suggestions, {len(repo_review)} review rows, "
          f"{len(verification)} verification rows")


if __name__ == "__main__":
    main()
