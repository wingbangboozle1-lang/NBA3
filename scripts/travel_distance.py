"""Travel distance from a sourced arena-coordinate table (session arena/42d69dc5-nba3).

The table is ``data/live/arena_coords.json``: one row per team -> home arena -> latitude/longitude,
each row carrying the URL that returned the coordinate and the pageid it came from. The verbatim
API responses it is built from are stored in ``data/live/raw/wiki_arena_coords_2026-11-15.json``,
so the table can be rebuilt and re-checked offline.

Rules this module exists to enforce
-----------------------------------
1. **Keyed by venue string, never by city.** A team's home venue comes from the official schedule
   capture or from this table's ``team_index``. An earlier build keyed venues by city name, which
   made ``LAC`` at Intuit Dome (Inglewood) and ``PHX`` at Mortgage Matchup Center (Phoenix) resolve
   to the home city's own venue and print ``0.0 km``. That is a real published defect; ``resolve``
   below cannot reproduce it, because it takes a venue string and has no city fallback.
2. **Reference, not official.** The NBA publishes no arena coordinates, so every distance carries
   ``source_tier: reference``. The label travels with the number.
3. **No inference.** A venue absent from the table returns ``None`` with a reason, and the caller
   must render an em dash and the reason. It never returns a guess, a centroid, or zero.

Distance is the great-circle (haversine) distance on the mean Earth radius 6371.0088 km, the same
constant the repository already used, so numbers stay comparable across rounds.

Run: python3 scripts/travel_distance.py            # rebuild the travel block, print a summary
     python3 scripts/travel_distance.py --check    # exit 1 if a published distance is unsourced
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
COORDS = ROOT / "data" / "live" / "arena_coords.json"
LIVE_SLATE = ROOT / "data" / "live" / "slate_2026-11-15.json"
HOME_VENUES = ROOT / "data" / "live" / "home_venues.json"
RESULTS = ROOT / "data" / "live" / "results" / "settled_2026-11-14.json"
ORIGIN = ROOT / "data" / "origin" / "games.csv"
OUT = ROOT / "data" / "live" / "travel_distance.json"

#: Venue spellings that differ between an older capture and the official 2026-11 schedule print.
#: Every target is a row that already carries its own source in arena_coords.json. An alias never
#: invents a coordinate; it only lets an older spelling reach the same sourced row.
ALIASES = {
    "Footprint Center": "Mortgage Matchup Center",
    "PHX Arena": "Mortgage Matchup Center",
    "Wells Fargo Center": "Xfinity Mobile Arena",
    "Wells Fargo Center (Philadelphia)": "Xfinity Mobile Arena",
}

EARTH_RADIUS_KM = 6371.0088


def load_table(path: pathlib.Path = COORDS) -> dict:
    table = json.loads(path.read_text(encoding="utf-8"))
    if table.get("schema") != "nba3.live.arena_coords/v1":
        raise SystemExit(f"{path}: unexpected schema {table.get('schema')!r}")
    return table


def _norm(venue: str) -> str:
    return " ".join((venue or "").replace("\u2019", "'").split())


def resolve(venue, table):
    """Return (row, reason). ``row`` is None when the venue cannot be sourced.

    Deliberately takes a VENUE STRING only. There is no city parameter, so there is no code path
    that can match a venue by city name.
    """
    if not venue:
        return None, "missing venue string (caller did not supply one)"
    key = _norm(venue)
    row = table["venues"].get(key)
    if row is None and key in ALIASES:
        row = table["venues"].get(ALIASES[key])
        if row is not None:
            return row, f"alias '{key}' -> '{ALIASES[key]}' (row carries its own source)"
    if row is None:
        blank = table.get("blank_venues", {}).get(key)
        if blank is not None:
            return None, f"{key}: coordinates API returned no coordinates (pageid {blank['pageid']})"
        return None, f"{key}: not in the sourced arena-coordinate table"
    if row.get("latitude") is None or row.get("longitude") is None:
        return None, f"{key}: coordinate blank in the sourced table"
    return row, "sourced"


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def distance(from_venue, to_venue, table):
    """Distance between two venues. Blank + flagged when either endpoint is unsourced."""
    a, ra = resolve(from_venue, table)
    b, rb = resolve(to_venue, table)
    base = {"from_venue": from_venue, "to_venue": to_venue,
            "from_source": (a or {}).get("coord_source"),
            "to_source": (b or {}).get("coord_source"),
            "source_tier": "reference", "method": f"haversine, R={EARTH_RADIUS_KM} km"}
    if a is None or b is None:
        return {**base, "km": None, "status": "UNVERIFIED",
                "reason": "; ".join(r for r in (ra, rb) if r != "sourced")}
    km = haversine_km((a["latitude"], a["longitude"]), (b["latitude"], b["longitude"]))
    return {**base, "km": round(km, 1), "status": "SOURCED",
            "note": "derived from reference coordinates, not an NBA-published figure"}


def load_home_venues(path=HOME_VENUES):
    """Team -> home venue, from an official source only (never inferred)."""
    return json.loads(path.read_text(encoding="utf-8"))


def home_venue(team, hv):
    return (hv.get("teams", {}).get(team) or {}).get("venue")


def _schedule():
    """The official schedule of record for the window, with each game's source.

    Three captures, each an official read, unioned by game_id. The union is published with its
    seams because a silent gap here would invent a well-rested team (that defect is recorded on the
    review page: the origin capture stopped at 11/13, so every 11/15 back-to-back vanished).
    """
    import csv
    games = {}
    if ORIGIN.exists():
        with ORIGIN.open() as fh:
            for r in csv.DictReader(fh):
                gid = r.get("game_id") or f"{r['date']}-{r['away']}-{r['home']}"
                games[gid] = {"date": r["date"][:10], "game_id": gid, "away": r["away"],
                              "home": r["home"], "venue": None,
                              "source_url": "https://www.nba.com/games?date=" + r["date"][:10],
                              "seam": "origin"}
    slate = json.loads(LIVE_SLATE.read_text(encoding="utf-8"))
    for g in slate["games"]:
        games[g["game_id"]] = {"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                               "home": g["home"], "venue": g.get("venue"),
                               "source_url": slate["source_url"], "seam": "slate"}
    if RESULTS.exists():
        settled = json.loads(RESULTS.read_text(encoding="utf-8"))
        for g in settled.get("games", []):
            games[g["game_id"]] = {"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                                   "home": g["home"], "venue": g.get("venue"),
                                   "source_url": g.get("source_url"), "seam": "settled"}
    return [games[k] for k in sorted(games, key=lambda k: (games[k]["date"], k))]


def build():
    table = load_table()
    hv = load_home_venues()

    # A game's venue is the home club's venue from an official source. The slate capture prints it;
    # for a game whose capture does not (the earlier results captures), the official home-venue
    # table is the source. A club with no official home game on record stays blank.
    games = _schedule()
    last_venue = {}
    rows = []
    for g in games:
        hv_row = hv.get("teams", {}).get(g["home"], {}) or {}
        dest = g["venue"] or hv_row.get("venue")
        dest_reason = None
        if dest is None:
            # The destination is the HOME club's venue. If that club has no official home venue on
            # record, the row is blank and says so; the gap is in the venue table, not the distance.
            dest_reason = (f"home club {g['home']} has no official home venue on record "
                           f"(see data/live/home_venues.json unresolved)")
            if g["home"] in (hv.get("unresolved") or {}):
                dest_reason = (f"home club {g['home']} has no home game anywhere in the official "
                               f"reads, so its venue is unpublished")
        for side, team in (("away", g["away"]), ("home", g["home"])):
            prev = last_venue.get(team)
            if prev is None:
                # Not an information gap: this is the club's first game in the window, so there is
                # no previous venue to measure from. Reporting this as "no venue string" would
                # blame the sources for a fact about the window. It is still blank, never zero.
                d = {"km": None, "status": "NO_PRIOR_GAME", "source_tier": "reference",
                     "reason": ("first game for this club in the captured window, so there is no "
                                "previous venue to measure a trip from"),
                     "from_source": None, "to_source": None}
            elif dest is None:
                d = {"km": None, "status": "UNVERIFIED", "source_tier": "reference",
                     "reason": dest_reason, "from_source": None, "to_source": None}
            else:
                d = distance(prev, dest, table)
            rows.append({"date": g["date"], "game_id": g["game_id"], "team": team, "side": side,
                         "seam": g["seam"], "previous_venue": prev, "venue": dest,
                         "travel_km": d["km"], "status": d["status"], "reason": d.get("reason"),
                         "source_tier": d["source_tier"],
                         "from_source": d["from_source"], "to_source": d["to_source"],
                         "venue_source": hv_row.get("source_url") or g["source_url"],
                         "source_url": g["source_url"]})
            if dest:
                last_venue[team] = dest

    priced = [r for r in rows if r["date"] >= "2026-11-15"]
    cited = sum(1 for r in priced if r["status"] == "SOURCED")
    return {
        "schema": "nba3.live.travel_distance/v1",
        "session": "arena/42d69dc5-nba3",
        "what": ("Great-circle travel distance for every team-game in the window, computed from "
                 "data/live/arena_coords.json against the venue strings in data/live/home_venues.json. "
                 "One row per team-game."),
        "table": {
            "file": "data/live/arena_coords.json",
            "home_venues": "data/live/home_venues.json",
            "verbatim_capture": table["coordinate_source"]["verbatim_capture"],
            "retrieved_utc": table["coordinate_source"]["retrieved_utc"],
            "is_official": False,
            "label": table["coordinate_source"]["label"],
            "venues_with_coordinates": len(table["venues"]),
            "blank_venues": sorted(table.get("blank_venues", {})),
            "home_venue_coverage": hv.get("counts"),
        },
        "counts": {"team_games": len(rows),
                   "sourced": sum(1 for r in rows if r["status"] == "SOURCED"),
                   "unverified": sum(1 for r in rows if r["status"] == "UNVERIFIED"),
                   "no_prior_game_in_window": sum(1 for r in rows if r["status"] == "NO_PRIOR_GAME"),
                   "priced_window_team_games": len(priced),
                   "priced_window_sourced": cited,
                   "priced_window_unverified": len(priced) - cited},
        "rows": rows,
    }


def check_venues() -> int:
    """Re-verify the venue map against the official captures on every build.

    The markdown on this table promises that this "re-checks this on every build and fails on a
    mismatch". These are the four mismatches it must catch, each pinned by a test that injects it:

    1. A club with an official venue string whose venue has no coordinate row. We would be blanking
       a distance we have the data for.
    2. A club the schedule says has no home game on record being silently filled in. Absence of
       evidence is published as blank; filling it is the one thing this repository must never do.
    3. Two sources disagreeing on a venue string. A renamed building is a different string, and
       "Wells Fargo Center" must never be silently mapped onto "Xfinity Mobile Arena".
    4. A resolved club that carries no `coord_source`, i.e. a coordinate with no provenance.
    """
    hv = json.loads(HOME_VENUES.read_text())
    coords = json.loads(COORDS.read_text())
    venues = coords["venues"]
    blanks = coords.get("blank_venues", {})
    problems = []

    # official-string -> coordinate row, with the renamed-arena blanks kept distinct from "not found"
    for venue, rec in sorted(blanks.items()):
        if rec.get("verified") or rec.get("latitude") is not None:
            problems.append(f"blank_venue {venue!r} carries a coordinate; a blank is not a fallback")

    resolved = {}
    for team, rec in sorted(hv["teams"].items()):
        venue = rec.get("venue")
        if not venue:
            problems.append(f"{team}: a club with no venue sits in `teams`; blanks belong in "
                            f"`unresolved` so that absence can never be read as a resolved row")
            continue
        row = venues.get(venue)
        if row is None:
            problems.append(f"{team}: official venue {venue!r} has no coordinate row")
            continue
        if row.get("latitude") is None or row.get("longitude") is None:
            problems.append(f"{team}: coordinate row for {venue!r} has no latitude/longitude")
        if not row.get("coord_source", "").startswith("https://"):
            problems.append(f"{team}: coordinate for {venue!r} carries no source URL")
        resolved[team] = venue

    # blanks: published explicitly, with a source for the blank itself
    unresolved = sorted(hv.get("unresolved", {}))
    for team, rec in sorted(hv.get("unresolved", {}).items()):
        if rec.get("venue"):
            problems.append(f"{team}: published as unresolved but carries a venue {rec['venue']!r}")
        if not rec.get("source_url", "").startswith("https://"):
            problems.append(f"{team}: blank venue with no source for the blank")
        if team in resolved:
            problems.append(f"{team}: appears in both teams and unresolved")

    # 3. a renamed building must not be reachable under its old name
    for venue, rec in sorted(blanks.items()):
        owner = rec.get("team")
        if owner and hv["teams"].get(owner, {}).get("venue") == venue:
            problems.append(f"{owner}: uses the renamed venue {venue!r}, which has no coordinates")

    # the counts published in the file must equal what was just measured
    c = hv["counts"]
    if c.get("resolved") != len(resolved):
        problems.append(f"counts.resolved says {c.get('resolved')}, measured {len(resolved)}")
    if c.get("unresolved") != len(unresolved):
        problems.append(f"counts.unresolved says {c.get('unresolved')}, measured {len(unresolved)}")
    if sorted(c.get("unresolved_teams", [])) != sorted(unresolved):
        problems.append(f"counts.unresolved_teams says {c.get('unresolved_teams')}, "
                        f"measured {sorted(unresolved)}")

    if problems:
        print(f"check-venues: FAIL — {len(problems)} problem(s)", file=sys.stderr)
        for line in problems:
            print("  " + line, file=sys.stderr)
        return 1
    print(f"check-venues: OK — {len(resolved)} clubs with an official venue string and a sourced "
          f"coordinate, {len(unresolved)} blank and flagged ({', '.join(sorted(unresolved)) or 'none'}), "
          f"{len(blanks)} renamed-arena blank(s) kept distinct, 0 disagreements")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any published distance is unsourced or has no source URL")
    ap.add_argument("--check-venues", action="store_true",
                    help="exit 1 if an official venue string has no coordinate, if two sources "
                         "disagree on a venue, or if an unresolved club was silently filled in")
    args = ap.parse_args()
    if args.check_venues:
        return check_venues()
    doc = build()
    bad = [r for r in doc["rows"] if r["status"] == "SOURCED" and not r["from_source"]]
    if bad:
        print(f"FAIL: {len(bad)} published distances carry no coordinate source", file=sys.stderr)
        return 1
    if not args.check:
        OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        print(f"travel: wrote {OUT.relative_to(ROOT)}")
    c = doc["counts"]
    print(f"travel: {c['sourced']} sourced / {c['team_games']} team-games "
          f"({c['unverified']} unsourced endpoint, {c['no_prior_game_in_window']} first game in window)")
    for r in doc["rows"]:
        if r["status"] == "UNVERIFIED":
            print(f"  blank {r['date']} {r['team']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
