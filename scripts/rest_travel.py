"""Rest, back-to-back, 3-in-4 and travel distance, computed from the official schedule.

Rest is arithmetic on the official schedule dates -- no estimation.

Travel distance is NOT computed here as a fact: the brief asks for it to come from a sourced
arena-coordinate table, and no coordinate was read from an official NBA source in this session.
So this file:
  * discovers candidate venue coordinates only from an explicitly supplied coordinate file,
  * records every venue it cannot source in `data/live/arena_coords.json` with `latitude: null`,
  * and reports travel as UNVERIFIED (blank) for those venues rather than guessing.

Session arena/42d69dc5-nba3 added the sourced table (data/live/arena_coords.json, built from
verbatim MediaWiki coordinates API captures) plus scripts/travel_distance.py, so travel is now
computed for real. This script reads that block instead of pairing venues by CITY:

  * the destination venue is the HOME CLUB'S venue string from data/live/home_venues.json (an
    official source) — never a city;
  * the departure venue is the venue of that team's previous game, carried forward;
  * an endpoint with no sourced coordinate stays blank and flagged.

That matters: the previous version keyed venues by city, so LAC at Intuit Dome (Inglewood) and PHX
at Mortgage Matchup Center (Phoenix) resolved to the home city's own building and printed 0.0 km.
The defect is recorded on the projection review page. tests/test_travel_distance.py pins it.

Run: python3 scripts/rest_travel.py
"""

from __future__ import annotations

import datetime as dt
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SLATE = ROOT / "data" / "live" / "slate_2026-11-15.json"
GAMES = ROOT / "data" / "origin" / "games.csv"
SETTLED = ROOT / "data" / "live" / "results" / "settled_2026-11-14.json"
SCHEDULE = ROOT / "data" / "live" / "schedule_of_record.json"
COORDS = ROOT / "data" / "live" / "arena_coords.json"
TRAVEL = ROOT / "data" / "live" / "travel_distance.json"
OUT = ROOT / "data" / "live" / "rest_travel.json"


def load_schedule() -> tuple[list[dict], list[dict]]:
    """Build the schedule of record from three official captures, and return it with provenance.

    No single capture covers the window: the origin results capture stops at 2026-11-13, the
    11/14 feed covers that date, and the slate capture covers 11/15-11/17. Rest can only be
    computed across all three, so they are unioned -- with the seam recorded, because a union of
    captures is exactly the place where a silent gap would create a fake "well rested" team.
    """
    import csv
    sources, rows = [], []
    with GAMES.open() as fh:
        for r in csv.DictReader(fh):
            rows.append({"date": r["date"][:10], "home": r["home"], "away": r["away"],
                         "seam": "origin"})
    sources.append({"seam": "origin", "file": str(GAMES.relative_to(ROOT)),
                    "what": "in-repo official results capture", "dates": "2026-10-20..2026-11-13",
                    "rows": len(rows)})

    n0 = len(rows)
    settled = json.loads(SETTLED.read_text())
    for g in settled["games"]:
        rows.append({"date": g["date"], "home": g["home"], "away": g["away"], "seam": "settled"})
    sources.append({"seam": "settled", "file": str(SETTLED.relative_to(ROOT)),
                    "what": "11/14 finals verified against two official reads",
                    "dates": "2026-11-14", "rows": len(rows) - n0,
                    "source_urls": [settled["games"][0]["source_url"]]})

    n1 = len(rows)
    slate = json.loads(SLATE.read_text())
    seen = {(r["date"], r["home"], r["away"]) for r in rows}
    for g in slate["games"]:
        if (g["date"], g["home"], g["away"]) not in seen:
            rows.append({"date": g["date"], "home": g["home"], "away": g["away"], "seam": "slate"})
    sources.append({"seam": "slate", "file": str(SLATE.relative_to(ROOT)),
                    "what": "upcoming slate", "dates": f"2026-11-15..2026-11-17",
                    "rows": len(rows) - n1, "source_url": slate["source_url"]})

    dates = sorted({r["date"] for r in rows})
    coverage = {"first": dates[0], "last": dates[-1], "dates": len(dates),
                "gaps": []}
    # a missing date is not a problem by itself (the NBA has idle days), but a date with fewer
    # than 2 games inside a busy stretch is worth surfacing.
    return rows, {"sources": sources, "coverage": coverage}


def venue_key(city: str) -> str:
    """Deprecated: kept only so an old caller fails loudly instead of pairing by city.

    Venue lookup now goes through the official venue string (data/live/home_venues.json ->
    data/live/arena_coords.json). See scripts/travel_distance.py.
    """
    raise RuntimeError(
        "venue lookup by city is disabled: it paired LAC@Intuit Dome and PHX@Mortgage Matchup "
        "Center with the home city's own venue and printed 0.0 km. Use "
        "travel_distance.resolve(venue_string) instead.")


def haversine_km(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def build() -> dict:
    slate = json.loads(SLATE.read_text())
    schedule, schedule_provenance = load_schedule()
    coords = json.loads(COORDS.read_text()) if COORDS.exists() else {"venues": {}}
    venues = coords.get("venues", {})

    by_team: dict[str, list[dict]] = {}
    for g in schedule:
        by_team.setdefault(g["home"], []).append({"date": g["date"], "venue_city": None,
                                                  "home": g["home"], "away": g["away"]})
        by_team.setdefault(g["away"], []).append({"date": g["date"], "venue_city": None,
                                                  "home": g["home"], "away": g["away"]})
    # venue city = the home team's arena city on that date; taken from the slate capture where
    # available, otherwise left unknown (never inferred from a team code).
    city_of_home = {}
    for g in slate["games"]:
        city_of_home[g["home"]] = g["city"]
    for t, rows in by_team.items():
        for r in rows:
            r["venue_city"] = city_of_home.get(r["home"])

    # ---- travel: read the sourced block, never re-derive it here ------------------
    # data/live/travel_distance.json is built by scripts/travel_distance.py from
    # data/live/arena_coords.json (verbatim coordinate captures) and data/live/home_venues.json
    # (official venue strings). Keying it on game_id + team makes the join exact.
    travel_rows = {}
    if TRAVEL.exists():
        doc = json.loads(TRAVEL.read_text())
        for r in doc["rows"]:
            travel_rows[(r["game_id"], r["team"])] = r
    travel_meta = {"file": str(TRAVEL.relative_to(ROOT)) if TRAVEL.exists() else None,
                   "status": "POPULATED" if travel_rows else "NOT POPULATED",
                   "built_by": "scripts/travel_distance.py",
                   "coordinate_table": "data/live/arena_coords.json",
                   "home_venue_table": "data/live/home_venues.json",
                   "is_official": False,
                   "label": ("Reference coordinates (the NBA publishes none). Every distance is a "
                             "derived great-circle value and is labelled the same way on the site."),
                   "why_blank": ("A distance is blank when either endpoint venue has no sourced "
                                 "coordinate or the club has no official home game on record. "
                                 "Nothing is estimated from a city name.")}

    slate_url = slate["source_url"]
    out_games = []
    for g in slate["games"]:
        d = dt.date.fromisoformat(g["date"])
        rows = []
        for team, side in ((g["away"], "away"), (g["home"], "home")):
            played = sorted({r["date"] for r in by_team.get(team, []) if r["date"] < g["date"]})
            prev = played[-1] if played else None
            rest = (d - dt.date.fromisoformat(prev)).days - 1 if prev else None
            # 4-day window ending on this game's date, INCLUSIVE of the current game:
            # a game on date x counts when 0 <= (d - x) <= 3. "3-in-4" is then count >= 3.
            window = [x for x in played if (d - dt.date.fromisoformat(x)).days <= 3]
            games_in_window = len(window) + 1
            b2b = bool(prev and (d - dt.date.fromisoformat(prev)).days == 1)
            tr = travel_rows.get((g["game_id"], team))
            if tr is None:
                travel = {"km": None, "status": "UNVERIFIED",
                          "reason": "no travel row for this game and team in data/live/travel_distance.json"}
            else:
                travel = {"km": tr["travel_km"], "status": tr["status"],
                          "from": tr["previous_venue"], "to": tr["venue"],
                          "from_source": tr.get("from_source"), "to_source": tr.get("to_source"),
                          "venue_source": tr.get("venue_source"),
                          "source_tier": tr.get("source_tier"),
                          "reason": tr.get("reason")}
            # previous_venue_city is kept for the page that renders it (scripts/build_live_site.py).
            # It is DISPLAY ONLY: no venue, coordinate or distance is resolved from it, because the
            # city-name lookup is exactly what produced the 0.0 km defect now pinned by
            # tests/test_travel_distance.py. The distance itself comes from travel_distance.json.
            prev_city_display = None
            if prev:
                prevs = [r for r in by_team.get(team, []) if r["date"] == prev]
                if prevs:
                    prev_city_display = city_of_home.get(prevs[-1]["home"])
            rows.append({"team": team, "side": side, "last_game_date": prev,
                         "rest_days": rest, "back_to_back": b2b,
                         "games_in_4_day_window": games_in_window,
                         "three_in_four": games_in_window >= 3,
                         "previous_venue_city": prev_city_display,
                         "previous_venue": (tr or {}).get("previous_venue"),
                         "travel": travel})
        out_games.append({"game_id": g["game_id"], "date": g["date"],
                          "matchup": f"{g['away']} @ {g['home']}", "teams": rows,
                          "venue": g["venue"],
                          "source_url": slate_url})

    return {
        "schema": "nba3.live.rest_travel/v1",
        "session": "arena/2ebb1e75-nba3",
        "schedule_provenance": schedule_provenance,
        "rest_source": {"what": "official schedule dates, unioned across three captures",
                        "rule": "rest_days = (game date - previous game date) in days - 1; "
                                "back_to_back = previous game on the immediately preceding day; "
                                "games_in_4_day_window counts the current game plus prior games on "
                                "dates within 3 days; three_in_four = that count >= 3"},
        "travel_source": travel_meta,
        "counts": {
            "games": len(out_games),
            "team_games": sum(len(g["teams"]) for g in out_games),
            "back_to_backs": sum(1 for g in out_games for t in g["teams"] if t["back_to_back"]),
            "three_in_four": sum(1 for g in out_games for t in g["teams"] if t["three_in_four"]),
            "travel_unverified": sum(1 for g in out_games for t in g["teams"]
                                     if t["travel"]["status"] == "UNVERIFIED"),
        },
        "games": out_games,
    }


def main() -> None:
    payload = build()
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    c = payload["counts"]
    print(f"{c['games']} games, {c['team_games']} team-games, "
          f"{c['back_to_backs']} back-to-backs, {c['three_in_four']} 3-in-4, "
          f"{c['travel_unverified']} travel distances unverified")


if __name__ == "__main__":
    main()
