#!/usr/bin/env python3
"""Minutes-redistribution model (session arena/79341829-nba3).

Explicit minutes redistribution for the window's teams:
  * top-8 minutes shares come from the captured official game books (minutes_shares.json)
    and/or the official per-player minutes snapshot (players_top31 CSV); never invented —
    teams with no share source stay blank and flagged;
  * players designated OUT on the official injury report are removed and their share is
    redistributed PROPORTIONALLY across the remaining available players (replacement
    shares published per player);
  * Doubtful/Questionable/Probable designations are published as risk notes only, without
    any redistribution (the designation itself is the scenario — no inferred probabilities).

Output: data/app/minutes_model.json
Usage:  python3 scripts/minutes_model.py
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
INJ = os.path.join(APP, "official_injuries_2026-11-15_0615AM_79341829.json")
SHARES = os.path.join(APP, "minutes_shares.json")
PLAYERS = os.path.join(APP, "players_top31_2026-11-14c.csv")
SLATE = os.path.join(APP, "official_slate_1115_1118.json")
OUT = os.path.join(APP, "minutes_model.json")

SRC_GAMEBOOK = "https://statsdmz.nba.com/pdfs/20261114/20261114_CHIMIN.pdf"  # pattern label
SRC_PLAYERS = "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"
SRC_INJ = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf"


def main():
    inj = json.load(open(INJ, encoding="utf-8"))
    now = inj["retrieved_stamp"]  # deterministic for CI drift
    shares = json.load(open(SHARES, encoding="utf-8"))
    slate = json.load(open(SLATE, encoding="utf-8"))

    # season per-game minutes from the official players snapshot (top-31 league-wide)
    season_min = {}
    with open(PLAYERS, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            season_min[(r["team"], r["player"])] = {
                "min": float(r["min"]), "pts": float(r["pts"]),
                "reb": float(r["reb"]), "ast": float(r["ast"]),
            }

    out_rows = {}
    risk_rows = {}
    for r in inj["rows"]:
        if not r.get("team"):
            continue
        side = (r.get("matchup"), r["team"])
        if r["status"] == "Out":
            out_rows.setdefault(side, []).append(r)
        elif r["status"] in ("Doubtful", "Questionable", "Probable"):
            risk_rows.setdefault(side, []).append(r)

    teams = sorted({t for g in slate["games"] for t in (g["away"], g["home"])})
    result_teams = {}
    for team in teams:
        # top-8 shares: prefer the 11/14 game-book measurement; else the season snapshot
        gb = shares["teams"].get(f"2026-11-14:{team}")
        roster = {}
        if gb:
            for p in gb["top8"]:
                roster[p["player"]] = {"share": p["share"], "min": p["min"],
                                       "source": gb["source"]}
            src = ("official game book 2026-11-14 (top-8 minutes shares measured from the "
                   "printed box score)")
        else:
            rows = [(p, v) for (t, p), v in season_min.items() if t == team]
            rows.sort(key=lambda kv: -kv[1]["min"])
            total = sum(v["min"] for _, v in rows) or 1.0
            for p, v in rows[:8]:
                roster[p] = {"share": round(v["min"] / total, 4), "min": v["min"],
                             "source": PLAYERS.replace(str(ROOT) + os.sep, "")}
            src = ("official per-player minutes snapshot 2026-11-14 (players page, top-31 "
                   "league-wide — teams outside the top 31 may be incomplete") if rows else None
        outs = []
        for side, rrows in out_rows.items():
            if side[1] == team:
                outs.extend(rrows)
        risks = []
        for side, rrows in risk_rows.items():
            if side[1] == team:
                risks.extend(rrows)

        # explicit redistribution: out players' shares go proportionally to the rest
        norm = {}
        def _norm(n):
            if "," in n:
                last, first = n.split(",", 1)
                return (first.strip() + " " + last.strip()).lower()
            return n.lower()
        out_names = {_norm(r["player"]) for r in outs}
        remaining = {p: v for p, v in roster.items() if _norm(p) not in out_names}
        removed_share = sum(v["share"] for p, v in roster.items() if _norm(p) in out_names)
        remaining_total = sum(v["share"] for v in remaining.values())
        redistribution = []
        for p, v in remaining.items():
            add = removed_share * v["share"] / remaining_total if remaining_total else 0.0
            redistribution.append({
                "player": p,
                "share_with_player_out": round(v["share"], 4),
                "replacement_share_from_out_players": round(add, 4),
                "share_after": round(v["share"] + add, 4),
                "source": v["source"],
            })
        redistribution.sort(key=lambda r: -r["share_after"])
        result_teams[team] = {
            "team": team,
            "share_source": src or "none — blank and flagged (no captured minutes source)",
            "top8_share_available": bool(roster),
            "out_players": [{"player": r["player"], "reason": r["reason"],
                             "source": SRC_INJ} for r in outs],
            "risk_designations": [{"player": r["player"], "status": r["status"],
                                   "reason": r["reason"], "source": SRC_INJ} for r in risks],
            "removed_share": round(removed_share, 4),
            "redistribution": redistribution,
            "top8_share_after": round(sum(r["share_after"] for r in redistribution[:8]), 4)
                                 if redistribution else None,
            "flag": ([] if roster else
                     ["no minutes source for this team — rotation availability left blank"]),
        }

    out = {
        "generated_utc": now,
        "policy": ("top-8 minutes shares + explicit proportional replacement shares when a "
                   "player is out; Doubtful/Questionable/Probable rows are risk notes only "
                   "and never trigger redistribution"),
        "injury_report": {"stamp": inj["report_stamp"], "retrieved": inj["retrieved_stamp"],
                          "source": SRC_INJ},
        "sources": [SRC_PLAYERS, SRC_INJ,
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_DALCLE.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_BKNMEM.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_DETMIA.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_CHIMIN.pdf"],
        "teams": result_teams,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    filled = sum(1 for v in result_teams.values() if v["top8_share_available"])
    print(f"minutes model: {filled}/{len(result_teams)} window teams have a minutes source; "
          f"teams with an OUT designation: "
          f"{sum(1 for v in result_teams.values() if v['out_players'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
