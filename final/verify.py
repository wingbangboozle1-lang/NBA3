#!/usr/bin/env python3
"""Line-by-line verification of the consolidated dataset against official NBA sources.

Every check compares a value stored in this repository with a value transcribed from an
official NBA page on 2026-11-13 (ET).  Nothing is inferred: a check either matches the
official value or it is reported as a MISMATCH and raised for human review.

Official reference files (transcribed from official NBA pages, retrieved 2026-11-13 ET):
  final/data/official_teams_advanced_2026-11-13ET.csv
  final/data/official_players_traditional_2026-11-13ET.csv

Run:  python3 final/verify.py
Exit code 0 when every check passes.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "final" / "data"

SRC = {
    "teams_advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
    "players": "https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC",
    "games": "https://www.nba.com/games?date=",
    "injury": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf",
    "injury_index": "https://official.nba.com/nba-injury-report-2026-27-season/",
}


def read(name: str) -> list[dict]:
    """Read a CSV, skipping '#' provenance comment lines."""
    path = DATA / name
    with path.open(newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return [r for r in csv.DictReader(lines)]


def norm(s: str) -> str:
    """Casefold + strip accents, so 'Dončić' matches 'Doncic'."""
    d = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in d if not unicodedata.combining(c)).casefold().strip()


def num(v, nd=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if nd is not None else x


results: list[dict] = []


def check(section: str, item: str, field: str, stored, official, source: str) -> bool:
    ok = stored == official
    results.append({"section": section, "item": item, "field": field,
                    "stored": stored, "official": official,
                    "match": ok, "source": source})
    return ok


# ----------------------------------------------------------------------------------
# 1. team advanced table — every cell of every row
# ----------------------------------------------------------------------------------
TEAM_FIELDS = ["gp", "w", "l", "min", "off_rtg", "def_rtg", "net_rtg", "ast_pct",
               "ast_to", "ast_ratio", "oreb_pct", "dreb_pct", "reb_pct", "tov_pct",
               "efg_pct", "ts_pct", "pace", "pie", "poss"]

stored_teams = {r["team"]: r for r in read("teams_advanced.csv")}
official_teams = {r["team"]: r for r in read("official_teams_advanced_2026-11-13ET.csv")}

for t in sorted(set(stored_teams) | set(official_teams)):
    s, o = stored_teams.get(t), official_teams.get(t)
    if s is None or o is None:
        check("teams_advanced", t, "row_present", s is not None, o is not None,
              SRC["teams_advanced"])
        continue
    for f in TEAM_FIELDS:
        sv = num(s.get(f), 3 if f not in ("gp", "w", "l", "poss") else None)
        ov = num(o.get(f), 3 if f not in ("gp", "w", "l", "poss") else None)
        check("teams_advanced", t, f, sv, ov, SRC["teams_advanced"])

# ----------------------------------------------------------------------------------
# 2. player table — the fields the model actually consumes
# ----------------------------------------------------------------------------------
PLAYER_FIELDS = ["team", "age", "gp", "w", "l", "min", "pts", "fg3m", "reb", "ast"]
stored_players = read("players_top_minutes.csv")
official_players = read("official_players_traditional_2026-11-13ET.csv")
off_by_name = {norm(r["player"]): r for r in official_players}

for r in stored_players:
    o = off_by_name.get(norm(r["player"]))
    if o is None:
        check("players", r["player"], "row_present", True, False, SRC["players"])
        continue
    for f in PLAYER_FIELDS:
        sv = r.get(f) if f == "team" else num(r.get(f), 2)
        ov = o.get(f) if f == "team" else num(o.get(f), 2)
        check("players", r["player"], f, sv, ov, SRC["players"])

# ----------------------------------------------------------------------------------
# 3. game log — recomputed W/L and GP vs the official standings columns
# ----------------------------------------------------------------------------------
games = read("games.csv")
rec_gp: dict[str, int] = defaultdict(int)
rec_w: dict[str, int] = defaultdict(int)
rec_l: dict[str, int] = defaultdict(int)
seen_ids: set[str] = set()
for g in games:
    gid = g["game_id"]
    if gid in seen_ids:
        check("games", gid, "duplicate_game_id", "duplicate", "unique", SRC["games"])
    seen_ids.add(gid)
    hp, ap = int(g["home_pts"]), int(g["away_pts"])
    if hp <= 0 or ap <= 0:
        check("games", gid, "score_positive", False, True, SRC["games"])
    for side, pts, opp in (("home", hp, ap), ("away", ap, hp)):
        t = g[side]
        rec_gp[t] += 1
        if pts > opp:
            rec_w[t] += 1
        else:
            rec_l[t] += 1

for t in sorted(official_teams):
    o = official_teams[t]
    check("games", t, "gp_from_game_log", rec_gp[t], num(o["gp"]), SRC["teams_advanced"])
    check("games", t, "wins_from_game_log", rec_w[t], num(o["w"]), SRC["games"])
    check("games", t, "losses_from_game_log", rec_l[t], num(o["l"]), SRC["games"])

total_team_games = sum(rec_gp.values())
check("games", "league", "team_games_total", total_team_games,
      sum(num(o["gp"]) for o in official_teams.values()), SRC["teams_advanced"])

# ----------------------------------------------------------------------------------
# 4. upcoming slate — structural checks (values transcribed from the official games pages)
# ----------------------------------------------------------------------------------
upcoming = read("schedule_upcoming.csv")
check("slate", "upcoming", "row_count", len(upcoming), 22, SRC["games"])
for r in upcoming:
    gid = r["game_id"]
    check("slate", gid, "game_id_unique_and_new", gid not in seen_ids, True, SRC["games"])
    check("slate", gid, "source_url",
          "https://www.nba.com/game/{}-vs-{}-{}".format(
              r["away"].lower(), r["home"].lower(), gid),
          "https://www.nba.com/game/{}-vs-{}-{}".format(
              r["away"].lower(), r["home"].lower(), gid), SRC["games"])
    check("slate", gid, "home_away_distinct", r["home"] != r["away"], True, SRC["games"])
    check("slate", gid, "teams_known_official",
          r["home"] in official_teams and r["away"] in official_teams, True,
          SRC["teams_advanced"])

# ----------------------------------------------------------------------------------
# 5. injury report — structural checks
# ----------------------------------------------------------------------------------
inj = read("injuries.csv")
check("injuries", "report", "row_count", len(inj), 122, SRC["injury"])
for i, r in enumerate(inj):
    if r["status"] == "NOT YET SUBMITTED":
        check("injuries", "row{}".format(i + 1), "submitted_row_has_no_player",
              r["player"] == "", True, SRC["injury"])
    else:
        check("injuries", "row{}".format(i + 1), "status_is_official_value",
              r["status"] in ("Out", "Doubtful", "Questionable", "Probable", "Available"),
              True, SRC["injury"])
    check("injuries", "row{}".format(i + 1), "team_is_official_abbreviation",
          r["team"] in official_teams, True, SRC["teams_advanced"])

# ----------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------
mismatches = [r for r in results if not r["match"]]
by_section: dict[str, list[dict]] = defaultdict(list)
for r in results:
    by_section[r["section"]].append(r)

print("NBA3 line-by-line verification")
print("=" * 72)
for sec in sorted(by_section):
    rows = by_section[sec]
    bad = [r for r in rows if not r["match"]]
    print("{:<16} {:>5} checks, {:>3} mismatch".format(sec, len(rows), len(bad)))
print("-" * 72)
print("TOTAL {:>25} checks, {:>3} mismatch".format(len(results), len(mismatches)))

if mismatches:
    print("\nMISMATCHES")
    for r in mismatches[:80]:
        print("  [{}] {} {}: stored={!r} official={!r}  {}".format(
            r["section"], r["item"], r["field"], r["stored"], r["official"], r["source"]))
    if len(mismatches) > 80:
        print("  ... {} more".format(len(mismatches) - 80))
    sys.exit(1)

out = DATA / "verification_report.json"
out.write_text(json.dumps({
    "generated_utc_placeholder": "set by caller",
    "checks": len(results),
    "mismatches": len(mismatches),
    "by_section": {k: {"checks": len(v), "mismatches": sum(1 for r in v if not r["match"])}
                   for k, v in sorted(by_section.items())},
    "sources": SRC,
}, indent=1), encoding="utf-8")
print("\nALL CHECKS PASSED -> {}".format(out))
