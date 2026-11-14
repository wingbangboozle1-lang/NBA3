#!/usr/bin/env python3
"""Regenerate the shared data layer from verified official inputs.

Reads  data/origin/model_output.json (model/build.py output), data/origin/
       schedule_upcoming.csv, data/origin/injuries.csv.
Writes data/schedule.json, data/injuries.json, data/injuries_2026-11-13_0730PM.csv,
       data/lines.json, data/props.json, data/picks.json (empty by design).

Policy: nothing is inferred. Market prices, venues and bet picks are not captured
from an official source, so those fields are null and no bet is published.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
ORIGIN = os.path.join(DATA, "origin")

M = json.load(open(os.path.join(ORIGIN, "model_output.json"), encoding="utf-8"))
TEAM_FULL = {t: v["name"] for t, v in M["team_ratings"].items()}
REPORT_URL = M["sources"]["injury"]
REPORT_STAMP = "11/13/26 07:30 PM ET"
SCHEDULE_URL = M["sources"]["schedule"]
UNPUBLISHED = ("NOT YET PUBLISHED", "NOT YET SUBMITTED")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


upcoming = read_csv(os.path.join(ORIGIN, "schedule_upcoming.csv"))
injuries = read_csv(os.path.join(ORIGIN, "injuries.csv"))
line_by_gid = {l["gid"]: l for l in M["lines"]}

# ------------------------------------------------------- official status overlay
# data/origin/injuries.csv is the 05:15 PM extract (session e22a2831), but this script
# stamps its output as the 07:30 PM report.  Every named row's status, printed name and
# (when the content differs) reason are therefore overlaid from the official 07:30 PM
# transcript at verify/data/official_injury_report_2026-11-13_0730PM.txt, fetched from
# https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf by
# session arena/9456a8ab-nba3 and cross-checked 117/117 on status, team and matchup
# against data/app/official_injuries_2026-11-13_0730PM.json.  Without this overlay the
# output mislabelled nine statuses as 07:30 PM values (rows INJ-010, INJ-011, INJ-013,
# INJ-014, INJ-022, INJ-024, INJ-033, INJ-034, INJ-042) - fixed by session 9456a8ab.
_TRANSCRIPT = os.path.join(ROOT, "verify", "data",
                           "official_injury_report_2026-11-13_0730PM.txt")


def _nm(s):
    return re.sub(r"[^a-z]", "", s.lower())


def _flat(s):
    return re.sub(r"\s", "", s).lower()


official_by_nm = {}
official_by_game = {}
for _line in open(_TRANSCRIPT, encoding="utf-8"):
    if not _line.startswith("| 11/1"):
        continue
    _p = [x.strip() for x in _line.strip().strip("|").split("|")]
    if len(_p) < 7 or not _p[4]:
        continue
    _row = {
        "game_date": dt.datetime.strptime(_p[0], "%m/%d/%Y").date().isoformat(),
        "matchup": _p[2], "player": _p[4], "status": _p[5], "reason": _p[6],
    }
    official_by_nm[_nm(_row["player"])] = _row
    official_by_game.setdefault((_row["game_date"], _row["matchup"]), []).append(_row)

# ---------------------------------------------------------------- schedule
schedule_games = []
for i, r in enumerate(upcoming, start=1):
    slug = "{}-vs-{}".format(r["away"].lower(), r["home"].lower())
    schedule_games.append({
        "game_no": i, "date": r["date"],
        "day": dt.date.fromisoformat(r["date"]).strftime("%a.") , "team_1": TEAM_FULL[r["away"]],
        "team_2": TEAM_FULL[r["home"]], "away_abbr": r["away"], "home_abbr": r["home"],
        "tip_et": r["time_et"], "nba_game_id": r["game_id"],
        "nba_url": "https://www.nba.com/game/{}-{}".format(slug, r["game_id"]),
        "venue": None, "national_tv": None, "hash_col": "",
        "orientation": "Confirmed from the official NBA schedule page: {}@{} (away@home), game ID {}."
                       .format(r["away"], r["home"], r["game_id"]),
        "source_url": SCHEDULE_URL,
    })
write_json(os.path.join(DATA, "schedule.json"), {
    "window": {"from": min(r["date"] for r in upcoming), "to": max(r["date"] for r in upcoming),
               "basis": "Official NBA schedule read 2026-11-14 (Nov 14-17)."},
    "source_title": "NBA.com - NBA schedule",
    "source_url": SCHEDULE_URL,
    "release_page": SCHEDULE_URL,
    "times_note": "Tip times are ET as printed on nba.com/schedule. Venue and TV are null: "
                  "not captured in the verified extract.",
    "games": schedule_games,
})

# ---------------------------------------------------------------- injuries
inj_json, inj_csv = [], []
for n, r in enumerate(injuries, start=1):
    unpub = r["status"] in UNPUBLISHED
    team = TEAM_FULL.get(r["team"], r["team"])
    player = r["player"]
    if player and "," not in player and " " in player:
        first, last = player.split(" ", 1)
        player_fmt = "{}, {}".format(last, first)          # match the official "Last, First" style
    else:
        player_fmt = player
    # overlay from the official 07:30 PM transcript (see block above)
    status_out, reason_out = r["status"], r["reason"]
    if player_fmt:
        hit = official_by_nm.get(_nm(player_fmt))
        if hit is None:
            _toks = player.split()
            _surname = None
            if _toks:
                _i = len(_toks) - 1
                while _i > 0 and _toks[_i].rstrip(".").lower() in ("jr", "sr", "ii", "iii", "iv", "v"):
                    _i -= 1
                _surname = _toks[_i]
            if _surname:
                _cands = [c for c in official_by_game.get((r["game_date"], r["matchup"]), [])
                          if _surname in c["player"].replace(",", " ").split()]
                if len(_cands) == 1:
                    hit = _cands[0]
        if hit:
            player_fmt = hit["player"]
            status_out = hit["status"]
            if _flat(hit["reason"]) != _flat(r["reason"]):
                reason_out = hit["reason"]                 # content differs: official wins
    inj_json.append({
        "id": "INJ-{:03d}".format(n), "game_date": r["game_date"],
        "game_time_et": "",                                  # not captured in the verified extract
        "matchup": r["matchup"], "team": team, "player": player_fmt or None,
        "reason_as_printed": reason_out, "status_as_printed": status_out,
        "attribution": "S" if unpub else "R",
        "schedule_source": SCHEDULE_URL if unpub else None,
        "report_stamp": REPORT_STAMP, "report_source": REPORT_URL,
        "flag": "FA-FA03: official report not yet published; availability UNVERIFIED" if unpub else "",
        "ids_note": "Team and matchup from the official NBA schedule; availability not verified." if unpub else "",
    })
    inj_csv.append({
        "row_type": "player" if player else "team", "game_date": r["game_date"],
        "matchup": r["matchup"], "team": team, "player": player_fmt,
        "status": status_out, "reason": reason_out,
        "availability_verified": "no" if unpub else "yes",
        "source_url": SCHEDULE_URL if unpub else REPORT_URL,
    })
write_json(os.path.join(DATA, "injuries.json"), inj_json)
write_csv(os.path.join(DATA, "injuries_2026-11-13_0730PM.csv"),
          ["row_type", "game_date", "matchup", "team", "player", "status", "reason",
           "availability_verified", "source_url"], inj_csv)

# ---------------------------------------------------------------- lines
out_lines = []
for r in upcoming:
    L = line_by_gid.get(r["game_id"])
    if L is None:
        continue
    slug = "{}-vs-{}".format(r["away"].lower(), r["home"].lower())
    out_lines.append({
        "date": r["date"], "time_et": r["time_et"], "away": r["away"], "home": r["home"],
        "away_name": TEAM_FULL[r["away"]], "home_name": TEAM_FULL[r["home"]],
        "nba_game_id": r["game_id"],
        "nba_url": "https://www.nba.com/game/{}-{}".format(slug, r["game_id"]),
        "model_spread_home": round(L["orig_spread_home"], 2),
        "model_margin_home": round(L["exp_margin"], 2),
        "model_home_pts": round(L["exp_home_pts"], 1),
        "model_away_pts": round(L["exp_away_pts"], 1),
        "model_total": round(L["orig_total"], 1),
        "exp_pace": round(L["pace"], 2),
        "home_net_rtg": M["team_ratings"][r["home"]]["net_rtg"],
        "away_net_rtg": M["team_ratings"][r["away"]]["net_rtg"],
        "p_home_ml": round(L["p_home_win"], 4),
        "p_away_ml": round(1 - L["p_home_win"], 4),
        "market_basis": "UNVERIFIED - no market price captured",
        "home_rest_days": L["home_rest_days"], "away_rest_days": L["away_rest_days"],
        "home_back_to_back": L["home_back_to_back"], "away_back_to_back": L["away_back_to_back"],
        "injury_report_submitted_home": L["injury_report_submitted_home"],
        "injury_report_submitted_away": L["injury_report_submitted_away"],
        "source": "nba_stats_team_advanced + nba_schedule + injury_report",
        "basis": "DERIVED",
        "note": "Model line from the walk-forward-validated pipeline. No market price is "
                "captured, so no price comparison or bet is published.",
    })
write_json(os.path.join(DATA, "lines.json"), out_lines)

# ---------------------------------------------------------------- picks
# Deliberately empty: 0 of 8 strategies pass the validation gates and no market
# price exists, so no bet can be published.
write_json(os.path.join(DATA, "picks.json"), [])

# ---------------------------------------------------------------- props
out_props = []
for p in M["player_props"]:
    out_props.append({
        "player": p["player"], "team": p["team"], "opponent": p["opponent"],
        "game_date": p["date"], "stat": "Points", "line": None,
        "over_odds": None, "under_odds": None, "model_p_over": None, "edge": None,
        "season_avg": p["season_pts"], "season_min": p["season_min"],
        "projected_min": round(p["projected_min"], 1), "model_projection": round(p["proj_pts"], 2),
        "availability": p["status"],
        "basis": "DERIVED",
        "source": p["source_player"],
        "status": "MODEL PROJECTION ONLY - no official prop line captured; no over/under "
                  "probability is published.",
        "verification_note": p["verification_note"],
    })
write_json(os.path.join(DATA, "props.json"), out_props)

print("shared: schedule={} injuries={} lines={} picks=0 props={}".format(
    len(schedule_games), len(inj_json), len(out_lines), len(out_props)))
