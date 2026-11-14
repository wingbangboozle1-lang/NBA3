#!/usr/bin/env python3
"""
T06 — Auto pick-generation pipeline for NBA3.
Reads ONLY from d01ae7e2/data/*.json (all official-source-verified upstream).
Writes d01ae7e2/data/picks.json and d01ae7e2/data/correlations.json.
No manual input: regenerate with `python3 d01ae7e2/scripts/generate_picks.py`.

Model (v1, fully documented in d01ae7e2/docs/PICKS_PIPELINE.md):
  fair_margin_home = 0.5*(net_home - net_away) + HCA + rest_adj_home - rest_adj_away
                     + 0.6*(out_ppg_away - out_ppg_home)
  fair_total       = 0.5*(pts_home + oppg_away + pts_away + oppg_home) + total_inj_adj
  net = PPG - OPPG (official columns). Parameters are pre-registered in strategies.json.
Every output row carries source_urls for its inputs. Provisional rows (injury report
not published) are labelled and never eligible for scoring.
"""
import json, math, os, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

HCA = 2.5                 # assumption hca-01
B2B_PENALTY = -1.5        # assumption w-01
INJ_WEIGHT = 0.35         # assumption w-01 (rev A: 0.6 -> 0.35 pre-settlement, see below)
INJ_CAP = 10.0            # assumption w-01 cap: per-team max margin hit from OUT production
EDGE_THRESHOLD = 3.0      # S1 gate parameter
CONF_CUTOFF = 0.60        # S1 gate parameter
REST_BONUS = {0: 0.0, 1: 0.0, 2: 0.5, 3: 0.5, 4: 0.75}  # assumption w-01
PARAM_REVISION = ("rev-A 2026-11-13 pre-settlement: INJ_WEIGHT 0.6->0.35 with INJ_CAP=10 after "
                  "sanity check produced implausible margins (e.g. SAS -18.7 vs GSW). "
                  "rev-B 2026-11-13 pre-settlement: OUT players count only if GP >= 60% of team GP "
                  "(rotation gate) to avoid double-counting absences already in baseline stats. "
                  "Zero settled picks existed at revision time; recorded in strategies.json.")


def load(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(D, name), "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def rest_adj(days):
    if days == 0:
        return B2B_PENALTY
    return REST_BONUS.get(min(days, 4), 0.75)


def out_ppg(inj_entry, team_abbr, team_gp):
    """Sum of season PPG for players with status Out who are rotation members.

    Rotation gate: player must have appeared in >=60% of the team's games.
    Rationale: a player who has already missed most of the season has his
    absence reflected in the team's official baseline stats; subtracting his
    PPG again would double-count the injury (rev-A, pre-settlement).
    """
    for t in inj_entry.get("teams", []):
        if t.get("team") == team_abbr:
            total = 0.0
            missing = False
            for p in t.get("players", []):
                if p.get("status") == "Out":
                    if p.get("season_ppg"):
                        if (p.get("season_gp") or 0) >= 0.6 * team_gp:
                            total += p["season_ppg"]
                        elif p.get("season_gp") is None:
                            missing = True  # GP unknown -> rotation gate cannot be applied
                        # else: GP known and <60% -> absence already priced into baseline
                    elif p.get("season_gp") == 0:
                        continue  # GP=0 -> zero current production, verified
                    else:
                        missing = True
            return total, missing
    return 0.0, False


def injury_state(inj_entry):
    states = [t.get("submission", "submitted") for t in inj_entry.get("teams", [])]
    if "NOT YET PUBLISHED" in states:
        return "not_published"
    if "NOT YET SUBMITTED" in states:
        return "partial"
    return "submitted"


def main():
    teams = {t["abbr"]: t for t in load("teams.json")["teams"]}
    slate = load("slate.json")["games"]
    injuries = {g["matchup"]: g for g in load("injuries.json")["games"]}

    picks = []
    for g in slate:
        h, a = teams[g["home"]], teams[g["away"]]
        key = f"{g['away']}@{g['home']}"
        inj = injuries[key]
        state = injury_state(inj)

        net_h = round(h["pts"] - h["oppg"], 4)
        net_a = round(a["pts"] - a["oppg"], 4)

        out_h, miss_h = out_ppg(inj, g["home"], h["gp"])
        out_a, miss_a = out_ppg(inj, g["away"], a["gp"])
        # source_url may sit on the game entry, on team entries, or on player rows
        inj_url = inj.get("source_url") or next(
            (t.get("source_url") for t in inj.get("teams", []) if t.get("source_url")), None)
        if not inj_url:
            for t in inj.get("teams", []):
                for pl in t.get("players", []):
                    if pl.get("source_url"):
                        inj_url = pl["source_url"]
                        break
                if inj_url:
                    break
        if not inj_url:
            # games with zero rows: the report still documents their absence
            inj_url = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf"

        # injury input only applied when report exists for that game
        inj_applied = state == "submitted"
        out_h_eff = out_h if inj_applied else 0.0
        out_a_eff = out_a if inj_applied else 0.0

        inj_margin = INJ_WEIGHT * (out_a_eff - out_h_eff)
        inj_margin = max(-INJ_CAP, min(INJ_CAP, inj_margin))
        margin = (0.5 * (net_h - net_a)
                  + HCA
                  + rest_adj(g["rest_home"])
                  + (-rest_adj(g["rest_away"]))
                  + inj_margin)

        total_base = 0.5 * (h["pts"] + a["oppg"] + a["pts"] + h["oppg"])
        # injuries push scoring down (capped per team)
        total = total_base - min(INJ_WEIGHT * out_h_eff, INJ_CAP) - min(INJ_WEIGHT * out_a_eff, INJ_CAP)

        # spread convention: negative = home team favored (standard). margin is home-perspective,
        # so home spread = -margin (e.g. margin -10.6 => home +10.6, away favored by 10.6)
        spread = round(-margin, 1)
        total_line = round(total, 1)

        # model win probability via normal CDF on margin (sigma=11.3 pts, NBA-typical scale assumption w-01)
        sigma = 11.3
        p_home = 0.5 * (1 + math.erf(margin / (sigma * math.sqrt(2))))
        p_away = 1 - p_home

        edge = abs(margin)
        confident = max(p_home, p_away) >= CONF_CUTOFF and edge >= EDGE_THRESHOLD
        pick_side = g["home"] if p_home >= p_away else g["away"]

        if state == "not_published":
            status = "PROVISIONAL_INJURY_PENDING"
        elif state == "partial":
            status = "PROVISIONAL_PARTIAL_INJURY"
        elif not confident:
            status = "NO_BET_LOW_EDGE"
        else:
            status = "PAPER_RELEASED"

        picks.append({
            "date": g["date"],
            "time_et": g["time_et"],
            "matchup": g["matchup"],
            "game_id": g["game_id"],
            "home": g["home"],
            "away": g["away"],
            "our_fair_spread_home": spread,       # negative = home favored
            "our_fair_total": total_line,
            "model_p_home": round(p_home, 3),
            "model_p_away": round(p_away, 3),
            "edge_vs_baseline_pts": round(edge, 2),
            "pick_side": pick_side if confident else None,
            "pick_type": "spread_home" if confident else None,
            "strategy_status": status,
            "injury_report_state": state,
            "injury_out_ppg_home": out_h_eff if inj_applied else None,
            "injury_out_ppg_away": out_a_eff if inj_applied else None,
            "injury_ppg_incomplete_home": miss_h if inj_applied else None,
            "injury_ppg_incomplete_away": miss_a if inj_applied else None,
            "rest_home": g["rest_home"],
            "rest_away": g["rest_away"],
            "b2b_home": g.get("b2b_home", False),
            "b2b_away": g.get("b2b_away", False),
            "assumptions": ["hca-01", "w-01"],
            "flags": ([f for f in [inj.get("flag_ref") if False else None,
                                   "flag-injury-future" if state == "not_published" else None,
                                   "fl-06" if state == "partial" else None] if f]),
            "source_urls": {
                "schedule": g["source_url"],
                "schedule_pdf": g["pdf_source_url"],
                "home_stats": h["source_url"],
                "away_stats": a["source_url"],
                "injury_report": inj_url,
                "game_preview": g["preview_url"],
            },
            "verified": True,
        })

    # ---- parlays (S2): pair two same-game released picks is impossible (1 pick/game),
    # so S2 pairs the two strongest SAME-DAY released singles (different games -> rho ~ 0,
    # measured/assumed independence flagged). We record candidate doubles with joint prob.
    released = [p for p in picks if p["strategy_status"] == "PAPER_RELEASED"]
    # deterministic pairing: best two edges of the day
    by_date = {}
    for p in released:
        by_date.setdefault(p["date"], []).append(p)
    parlays = []
    for date, ps in sorted(by_date.items()):
        ps_sorted = sorted(ps, key=lambda x: -x["edge_vs_baseline_pts"])
        if len(ps_sorted) >= 2:
            leg1, leg2 = ps_sorted[0], ps_sorted[1]
            p1 = leg1["model_p_home"] if leg1["pick_side"] == leg1["home"] else leg1["model_p_away"]
            p2 = leg2["model_p_home"] if leg2["pick_side"] == leg2["home"] else leg2["model_p_away"]
            # different games -> rho recorded as measured-independent-by-design (flagged in correlations)
            rho = 0.0
            joint = p1 + p2 - p1 * p2 - rho * min(p1, p2) * (1 - max(p1, p2))
            joint = max(min(joint, min(p1, p2)), max(0.0, p1 + p2 - 1))
            parlays.append({
                "date": date,
                "legs": [f"{leg1['matchup']} {leg1['pick_side']}", f"{leg2['matchup']} {leg2['pick_side']}"],
                "p_leg1": p1, "p_leg2": p2, "rho": rho,
                "rho_basis": "cross-game legs: rho=0 by design (separate contests); no measured value available - flagged as assumption w-01 family",
                "joint_prob_naive": round(p1 * p2, 4),
                "joint_prob_corrected": round(joint, 4),
                "strategy_status": "PAPER_RELEASED" if joint >= 0.36 else "NO_BET_LOW_JOINT",
                "source_urls": {"leg1": leg1["source_urls"]["schedule"], "leg2": leg2["source_urls"]["schedule"]},
            })

    # ---- prop stacks (S3): same-team teammates from players.json
    players = load("players.json")["players"]
    by_team = {}
    for p in players:
        if p.get("last5_pts") and len(p["last5_pts"]) >= 5 and p.get("season_ppg"):
            by_team.setdefault(p["team"], []).append(p)

    stacks = []
    for team, plist in sorted(by_team.items()):
        if len(plist) < 2:
            continue
        # pair by overlapping dates
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                A, B = plist[i], plist[j]
                common = [d for d in A.get("last5_dates", []) if d in B.get("last5_dates", [])]
                if len(common) < 5:
                    continue
                xa = [A["last5_pts"][A["last5_dates"].index(d)] for d in common]
                xb = [B["last5_pts"][B["last5_dates"].index(d)] for d in common]
                if len(set(xa)) < 2 or len(set(xb)) < 2:
                    rho = None
                else:
                    rho = round(statistics.correlation(xa, xb), 3)
                # availability gate
                bad = [s for s in (A.get("injury_status_1113", ""), B.get("injury_status_1113", "")) if "Out" in s or "Doubtful" in s]
                gate = "REJECT_OUT_OR_DOUBTFUL" if bad else ("RELEASE_PAPER" if rho is not None and len(common) >= 5 else "SINGLE_ONLY_NO_RHO")
                stacks.append({
                    "team": team,
                    "players": [A["player"], B["player"]],
                    "n_common_games": len(common),
                    "rho_pts": rho,
                    "rho_method": "Pearson on official Last-5 Games PTS over identical dates",
                    "line_a_ppg": A["season_ppg"],
                    "line_b_ppg": B["season_ppg"],
                    "gate": gate,
                    "status_note": "n=5 is noisy (Q-12 open)" if len(common) == 5 else None,
                    "source_urls": [A["source_url"], B["source_url"]],
                })

    out_picks = {
        "meta": {
            "generator": "d01ae7e2/scripts/generate_picks.py",
            "generated_at": "2026-11-13T23:30:00Z",
            "input_files": ["teams.json", "slate.json", "injuries.json", "players.json", "strategies.json"],
            "parameters": {"HCA": HCA, "B2B_PENALTY": B2B_PENALTY, "INJ_WEIGHT": INJ_WEIGHT,
                            "INJ_CAP": INJ_CAP, "EDGE_THRESHOLD": EDGE_THRESHOLD,
                            "CONF_CUTOFF": CONF_CUTOFF, "sigma": 11.3},
            "parameter_revision": PARAM_REVISION,
            "assumption_flags": ["hca-01", "w-01"],
            "scoring_note": "PAPER only. PROVISIONAL rows never scored until injury report exists (Q-10).",
        },
        "picks": picks,
        "parlays_s2": parlays,
        "prop_stacks_s3": stacks,
    }
    save("picks.json", out_picks)

    # ---- correlations.json (T04): league-level + player-level measured values
    win = [t["win_pct"] for t in teams.values()]
    marg = [t["margin_pg"] for t in teams.values()]
    pts = [t["pts"] for t in teams.values()]
    oppg = [t["oppg"] for t in teams.values()]
    lg = load("teams.json")["teams"]
    corr = {
        "meta": {
            "generator": "d01ae7e2/scripts/generate_picks.py",
            "method": "Pearson r; all inputs from official NBA sources (league table + player Last-5 tables)",
            "generated_at": "2026-11-13T23:30:00Z",
            "caveat": "Player-level rhos use n=5 official logs -> noisy; labelled. League-level n=30.",
        },
        "league": [
            {"pair": "win_pct vs margin_pg", "n": 30, "r": round(statistics.correlation(win, marg), 3),
             "source_url": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"},
            {"pair": "win_pct vs pts", "n": 30, "r": round(statistics.correlation(win, pts), 3),
             "source_url": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"},
            {"pair": "win_pct vs oppg", "n": 30, "r": round(statistics.correlation(win, oppg), 3),
             "source_url": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"},
            {"pair": "margin_pg vs oppg", "n": 30, "r": round(statistics.correlation(marg, oppg), 3),
             "source_url": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"},
        ],
        "teammates": [s for s in stacks if s.get("rho_pts") is not None],
        "cross_game_parlay": {"rho": 0.0, "basis": "separate contests; independence by design, flagged assumption", "n": None},
        "blocked": [{"what": "market-odds CLV correlation", "why": "no authorized odds source (Q-04, fl-16)", "status": "BLOCKED"}],
    }
    save("correlations.json", corr)

    n_rel = len(released)
    n_prov = sum(1 for p in picks if p["strategy_status"].startswith("PROVISIONAL"))
    print(f"picks={len(picks)} released={n_rel} provisional={n_prov} "
          f"nobet={sum(1 for p in picks if p['strategy_status']=='NO_BET_LOW_EDGE')} "
          f"parlays={len(parlays)} stacks={len(stacks)}")


if __name__ == "__main__":
    main()
