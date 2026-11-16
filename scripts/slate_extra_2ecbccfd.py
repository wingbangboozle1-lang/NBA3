#!/usr/bin/env python3
"""Turn the 2026-11-19 slate transcript into a machine-readable window extension.

Offline and deterministic: it parses the verbatim transcript committed at
data/rounds/2026-11-17/captures/slate_2026-11-19_raw.md, whose header names the official page it
was read from. A card that does not print a venue gets venue = null; the arena name is then taken
from the sourced arena-coordinate table and marked as derived, never as an NBA-published value.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TXT = os.path.join(ROOT, "data", "rounds", "2026-11-17", "captures", "slate_2026-11-19_raw.md")
OUT = os.path.join(ROOT, "data", "rounds", "2026-11-17", "slate_extra_2026-11-19.json")
CARD = re.compile(r"\[(\d{1,2}:\d{2} PM ET) \.\.\. (.+?) \.\.\. (\d+-\d+) \.\.\. (.+?) \.\.\. "
                  r"(\d+-\d+)\]\(https://www\.nba\.com/game/([a-z]{3})-vs-([a-z]{3})-(\d{10})\)")
REG = json.load(open(os.path.join(ROOT, "data", "live", "team_registry.json"), encoding="utf-8"))["teams"]
CODE_BY_ID = {str(v["nba_team_id"]): k for k, v in REG.items()}
FULL_BY_CODE = {k: v["full_name"] for k, v in REG.items()}
NAME_TO_CODE = {v: k for k, v in FULL_BY_CODE.items()}


def main():
    text = open(TXT, encoding="utf-8").read()
    games, problems = [], []
    for m in CARD.finditer(text):
        tip, away_name, away_rec, home_name, home_rec, a, h, gid = m.groups()
        away, home = NAME_TO_CODE.get(away_name), NAME_TO_CODE.get(home_name)
        if not away or not home:
            problems.append({"line": m.group(0)[:120], "why": "club name not in the official registry"})
            continue
        if away.lower() != a or home.lower() != h:
            problems.append({"line": m.group(0)[:120],
                             "why": f"card teams {away}/{home} differ from the game link {a}/{h}"})
            continue
        games.append({"date": "2026-11-19", "tip_et": tip, "away": away, "home": home,
                      "away_record": away_rec, "home_record": home_rec, "game_id": gid,
                      "game_url": f"https://www.nba.com/game/{a}-vs-{h}-{gid}",
                      "venue": None,
                      "venue_derived": FULL_BY_CODE[home] and home,
                      "source_url": "https://www.nba.com/game/atl-vs-mil-0022600243",
                      "retrieved_utc": "2026-11-16T18:52Z"})
    arenas = json.load(open(os.path.join(ROOT, "data", "app", "arena_coordinates.json"),
                            encoding="utf-8"))["arenas"]
    arena_by_team = {r.get("team"): r for r in arenas}
    for g in games:
        a = arena_by_team.get(g["home"]) or {}
        g["venue"] = None
        g["venue_from_coordinate_table"] = a.get("arena")
        g["venue_is_official"] = False
        g.pop("venue_derived", None)
    games.sort(key=lambda g: (g["date"], g["game_id"]))
    blob = json.dumps({"schema": "nba3.rounds.slate_extra/v1",
                       "source_url": "https://www.nba.com/game/atl-vs-mil-0022600243",
                       "corroborating_url": "https://www.nba.com/schedule?date=2026-11-19",
                       "retrieved_utc": "2026-11-16T18:52Z",
                       "date": "2026-11-19", "count": len(games),
                       "verbatim_transcript": os.path.relpath(TXT, ROOT),
                       "problems": problems, "games": games}, indent=1) + "\n"
    if "--check" in sys.argv:
        return 0 if open(OUT, encoding="utf-8").read() == blob else 1
    open(OUT, "w", encoding="utf-8").write(blob)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(games)} games, {len(problems)} problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
