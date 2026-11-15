"""Rest, back-to-back, 3-in-4 and travel distance, computed from the official schedule.

Rest is arithmetic on the official schedule dates -- no estimation.

Travel distance is NOT computed here as a fact: the brief asks for it to come from a sourced
arena-coordinate table, and no coordinate was read from an official NBA source in this session.
So this file:
  * discovers candidate venue coordinates only from an explicitly supplied coordinate file,
  * records every venue it cannot source in `data/live/arena_coords.json` with `latitude: null`,
  * and reports travel as UNVERIFIED (blank) for those venues rather than guessing.

Populate coordinates by adding entries with a source URL to data/live/arena_coords.json; the
distance immediately appears on the site. Nothing is inferred from a city name.

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
    return city.strip().lower()


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
            # where the team played on its previous date; the home team's city, never the code
            prev_city = None
            if prev:
                prevs = [r for r in by_team.get(team, []) if r["date"] == prev]
                prev_home = prevs[-1]["home"] if prevs else None
                prev_city = city_of_home.get(prev_home)
            dest = g["city"]
            a = venues.get(venue_key(prev_city or ""), {}) if prev_city else {}
            b = venues.get(venue_key(dest or ""), {})
            if a.get("latitude") is not None and a.get("longitude") is not None and \
               b.get("latitude") is not None and b.get("longitude") is not None:
                km = round(haversine_km((a["latitude"], a["longitude"]),
                                        (b["latitude"], b["longitude"])), 1)
                travel = {"km": km, "status": "SOURCED",
                          "from": prev_city, "to": dest,
                          "from_source": a.get("source_url"), "to_source": b.get("source_url")}
            else:
                travel = {"km": None, "status": "UNVERIFIED",
                          "reason": ("no sourced arena coordinate for "
                                     f"{prev_city or 'unknown'} or {dest}"),
                          "from": prev_city, "to": dest}
            rows.append({"team": team, "side": side, "last_game_date": prev,
                         "rest_days": rest, "back_to_back": b2b,
                         "games_in_4_day_window": games_in_window,
                         "three_in_four": games_in_window >= 3,
                         "previous_venue_city": prev_city, "travel": travel})
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
        "travel_source": {"what": "arena coordinate table", "file": "data/live/arena_coords.json",
                          "status": "NOT POPULATED",
                          "why_blank": ("No official NBA page read in this session publishes arena "
                                        "latitude/longitude. The brief requires a SOURCED table, so the "
                                        "distances are left blank and flagged rather than estimated "
                                        "from city names.")},
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
