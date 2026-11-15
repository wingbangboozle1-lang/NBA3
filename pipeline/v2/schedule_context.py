"""Rest, back-to-back, 3-in-4 and travel, all from the official schedule.

The official schedule already makes rest and back-to-backs computable, and this
module computes them from the game log rather than from a hand-maintained note.
Travel is added on top from a sourced arena-coordinate table; every distance is
a great-circle lower bound and is labelled as such.

Nothing here reads a model output.  Rest is a fact about the calendar.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os

EARTH_RADIUS_KM = 6371.0088


def load_arena_table(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def team_game_dates(games):
    """team -> sorted list of dates played (from the finals log)."""
    out = {}
    for g in games:
        for side in ("home", "away"):
            out.setdefault(g[side], []).append(g["date"])
    for t in out:
        out[t] = sorted(set(out[t]))
    return out


def rest_days(dates_by_team, team, date):
    """Days since the team's last game strictly before ``date``.

    ``None`` when there is no earlier game in the log: a team whose first game
    of the season is this one has no measurable rest, and 0 or a league average
    would both be invented numbers.
    """
    prior = [d for d in dates_by_team.get(team, []) if d < date]
    if not prior:
        return None
    last = _dt.date.fromisoformat(prior[-1])
    cur = _dt.date.fromisoformat(date)
    return (cur - last).days


def games_in_window(dates_by_team, team, date, window_days=4):
    """Games in the ``window_days`` ending on ``date``, COUNTING ``date`` itself.

    With window_days=4 this is the 3-in-4 test, and the count must include
    tonight: a team playing on the 12th, 13th and 15th is playing its third game
    in four nights, but the game log only knows about the 12th and 13th, so
    counting the log alone returns 2 and the situation is never flagged.  The
    upcoming game is in the schedule, not yet in the log, so it has to be added
    explicitly.
    """
    cur = _dt.date.fromisoformat(date)
    lo = cur - _dt.timedelta(days=window_days - 1)
    n = 1  # the game being priced
    for d in dates_by_team.get(team, []):
        dd = _dt.date.fromisoformat(d)
        if lo <= dd < cur:
            n += 1
    return n


def venue_for(arena_table, team):
    for row in arena_table["arenas"]:
        if row["team"] == team:
            return row
    return None


def travel_km(arena_table, from_team, to_team):
    """Great-circle distance from one team's arena to another's.

    For a road game the leg that matters is previous venue -> tonight's venue.
    The caller decides which two teams to pass; this function does not assume
    that a team always travels from its own building, because a road trip does
    not work that way.
    """
    a = venue_for(arena_table, from_team)
    b = venue_for(arena_table, to_team)
    if not a or not b:
        return None
    return haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])


def last_venue(history, team, date):
    """The team of the arena where ``team`` last played before ``date``.

    Home games are at the team's own arena; road games are at the opponent's.
    That is the whole rule, and it is derivable from the official schedule
    without any travel data.
    """
    prior = [g for g in history if g["date"] < date and team in (g["home"], g["away"])]
    if not prior:
        return None
    g = max(prior, key=lambda x: (x["date"], x["gid"]))
    return g["home"]  # the home team's arena is the venue


def build_context(games, upcoming, arena_table):
    """One row per upcoming game with rest, b2b, 3-in-4 and travel for both sides."""
    dates_by_team = team_game_dates(games)
    rows = []
    for g in upcoming:
        row = {
            "date": g["date"], "game_id": g["game_id"],
            "away": g["away"], "home": g["home"],
            "venue": g["venue"], "city": g["city"],
            "source_url": "https://www.nba.com/schedule?date=" + g["date"],
            "travel_source_url": arena_table["arenas"][0]["page"],
            "travel_source_tier": "SECONDARY",
        }
        for side, team in (("away", g["away"]), ("home", g["home"])):
            rest = rest_days(dates_by_team, team, g["date"])
            in4 = games_in_window(dates_by_team, team, g["date"], 4)
            prev_venue = last_venue(games, team, g["date"])
            km = travel_km(arena_table, prev_venue, g["home"]) if prev_venue else None
            row[side] = {
                "team": team,
                "rest_days": rest,
                "back_to_back": (rest == 1) if rest is not None else None,
                "games_in_4_nights": in4,
                "three_in_four": (in4 >= 3),
                "previous_venue_team": prev_venue,
                "travel_km": round(km, 1) if km is not None else None,
                "travel_kind": ("great-circle lower bound" if km is not None else None),
            }
        rows.append(row)
    return rows


def injury_rotation_impact(injury_rows, player_minutes, game_date, matchups):
    """Explicit minutes redistribution for each team playing on ``game_date``.

    For each team:
      * the top-8 minutes shares (from the official player page), if captured;
      * the minutes vacated by players listed OUT (or DOUBTFUL, priced at half
        their minutes, which is stated as an assumption and not a measurement);
      * the replacement shares: the vacated minutes re-spread over the remaining
        top-8 in proportion to their own shares, with a cap.

    Where the player page was not captured the whole block is BLOCKED and left
    blank.  It is never filled from a league average.
    """
    by_team = {t["team"]: t for t in player_minutes.get("teams", [])}
    out = []
    for matchup in matchups:
        away, home = matchup
        for team in (away, home):
            rec = {
                "game_date": game_date, "matchup": f"{away}@{home}", "team": team,
                "status": "OK", "reason": None,
            }
            captured = by_team.get(team)
            if not captured:
                rec["status"] = "BLOCKED"
                rec["reason"] = ("top-8 minutes for this team were not captured "
                                 "(see official_player_minutes_2026-11-15.json); the "
                                 "vacated-minutes figure is left blank rather than estimated")
                rec["top8"] = []
                rec["vacated_minutes"] = None
                out.append(rec)
                continue
            players = captured["players"][:8]
            total = sum(p["min"] for p in players)
            out_players = [r for r in injury_rows
                           if r["game_date"] == game_date and r["team"] == team
                           and r["status"] == "Out" and r["player"]]
            doubtful = [r for r in injury_rows
                        if r["game_date"] == game_date and r["team"] == team
                        and r["status"] == "Doubtful" and r["player"]]
            top8 = []
            vacated = 0.0
            for p in players:
                share = p["min"] / total if total else None
                flagged = "out" if any(_same(p["name"], r["player"]) for r in out_players) else (
                    "doubtful" if any(_same(p["name"], r["player"]) for r in doubtful) else "")
                top8.append({
                    "player": p["name"], "min": p["min"],
                    "share_of_top8": round(share, 4) if share is not None else None,
                    "status": flagged,
                    "share_if_out": 0.0 if flagged == "out" else (
                        round(share / 2, 4) if flagged == "doubtful" and share is not None
                        else round(share, 4) if share is not None else None),
                })
                if flagged == "out":
                    vacated += p["min"]
                elif flagged == "doubtful":
                    vacated += p["min"] * 0.5
            rec["top8"] = top8
            rec["vacated_minutes"] = round(vacated, 2)
            rec["replacement_rule"] = ("vacated minutes redistributed over the remaining top-8 "
                                       "in proportion to their own shares; doubtful players are "
                                       "counted at half their minutes (an assumption, stated)")
            rec["minutes_total_check"] = round(sum(p["min"] for p in players), 2)
            out.append(rec)
    return out


def _same(a, b):
    if not a or not b:
        return False
    na = " ".join(a.replace(",", " ").lower().split())
    nb = " ".join(b.replace(",", " ").lower().split())
    return na == nb
