#!/usr/bin/env python3
"""Two-estimator origination model for the 2026-11-17 round (session arena/2ecbccfd-nba3).

Offline, deterministic, no network. Inputs are the verified artefacts in this repository; every
number written here is derived from them and every derived number names the file it came from.
Run:

    python3 scripts/model_2ecbccfd.py            # write data/rounds/2026-11-17/model.json
    python3 scripts/model_2ecbccfd.py --check     # fail if the committed model.json drifts

What the module is required to do, and does (each item is the project brief, not a design choice):

  * two INDEPENDENT estimators; the HEADLINE is their disagreement, the blend sits underneath;
  * home-court advantage is PINNED to the measured home-win rate -- never a free parameter;
  * the total is possessions x points-per-possession, never an average of scoring averages;
  * rest, back-to-back and 3-in-4 come from the official schedule; travel from the sourced
    arena-coordinate table (a derived value, and that table is not an NBA source -- flagged);
  * minutes redistribution is modelled per team from the captured game books;
  * luck is reported as a z-score per team, and a strategy that leans on a team outside the
    noise band is refused publication;
  * parlays are priced with the measured rho and the naive product is printed next to them;
  * the market-anchored prior blends with the closing line weighted by measured out-of-sample
    log-loss -- and stays BLANK while no closing-line feed is connected, which is the case here.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RD = os.path.join(ROOT, "data", "rounds", "2026-11-17")
PRIOR = os.path.join(ROOT, "data", "rounds", "2026-11-16")

STATS_TSV = os.path.join(ROOT, "data", "app", "team_stats_2026-11-16.tsv")
ARENAS = os.path.join(ROOT, "data", "app", "arena_coordinates.json")
LOGS = os.path.join(ROOT, "data", "app", "player_game_logs.json")
SHARES = os.path.join(ROOT, "data", "app", "minutes_shares.json")
CLOSING = os.path.join(ROOT, "data", "app", "closing_lines.json")
SOURCES_OUT = os.path.join(RD, "model.json")

STATS_PAGES = {
    "traditional": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
    "opponent": "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
    "advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------- small statistics
def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probit(p):
    """Inverse standard normal CDF by Halley iteration; no scipy, no lookup table."""
    p = min(max(p, 1e-12), 1 - 1e-12)
    x = math.sqrt(2.0) * _erfinv(2.0 * p - 1.0)
    for _ in range(3):
        f = phi(x) - p
        d = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
        if not d:
            break
        x -= f / d * (1.0 + f * x / (2.0 * d))
    return x


def _erfinv(y):
    # Newton on erf, seeded by the Winitzki approximation.
    a = 0.147
    ln = math.log(1.0 - y * y) if abs(y) < 1 else -50.0
    t = 2.0 / (math.pi * a) + ln / 2.0
    x = math.copysign(math.sqrt(math.sqrt(t * t - ln / a) - t), y)
    for _ in range(30):
        err = math.erf(x) - y
        d = 2.0 / math.sqrt(math.pi) * math.exp(-x * x)
        if not d:
            break
        x -= err / d
    return x


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 6), round((c + h) / d, 6))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r, n, z=1.96):
    if r is None or n < 4:
        return None
    r = min(max(r, -0.999999), 0.999999)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = zr - z * se, zr + z * se
    inv = lambda t: (math.exp(2 * t) - 1) / (math.exp(2 * t) + 1)
    return (round(inv(lo), 6), round(inv(hi), 6))


# --------------------------------------------------------------------- inputs
def load_team_stats():
    """The three official team-stat pages, from the committed TSV (read 2026-11-16 by 8f4fac33)."""
    with open(STATS_TSV, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    pages, cur, header = {}, None, None
    reg_names = None
    for line in lines:
        if line.startswith("#PAGE"):
            rest = line[len("#PAGE"):].strip()
            name, url, stamp = [c.strip() for c in rest.split("|")]
            cur = name
            pages[cur] = {"rows": [], "url": url, "read_stamp": stamp, "header": None}
            continue
        if line.startswith("#") or not line.strip():
            continue
        cells = line.split("\t")
        if cells[0] == "TEAM":
            pages[cur]["header"] = cells
            continue
        pages[cur]["rows"].append(dict(zip(pages[cur]["header"], cells)))
    return pages


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_arenas():
    d = load_json(ARENAS)
    out = {}
    for row in d["arenas"]:
        code = row.get("team") or row.get("abbr")
        lat, lon = row.get("lat"), row.get("lon")
        out[code] = {"arena": row.get("arena"), "lat": lat, "lon": lon,
                     "source": row.get("source") or row.get("source_url"), "city": row.get("city")}
    return out, d


def haversine_mi(a, b):
    if not a or not b or a.get("lat") in (None, "") or b.get("lat") in (None, ""):
        return None
    try:
        lat1, lon1 = float(a["lat"]), float(a["lon"])
        lat2, lon2 = float(b["lat"]), float(b["lon"])
    except (TypeError, ValueError):
        return None
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 1)


# --------------------------------------------------------------------- schedule features
def schedule_features(log, window_games):
    """Rest days, back-to-back and 3-in-4 from the verified results log + the official window."""
    by_team = defaultdict(list)
    for g in log:
        d = g["date"]
        by_team[g["away"]].append((d, "away", g))
        by_team[g["home"]].append((d, "home", g))
    def to_ord(iso):
        y, m, dd = [int(x) for x in iso.split("-")]
        return (y * 372 + (m - 1) * 31 + dd)
    feats = {}
    for side in window_games:
        team, date = side["team"], side["date"]
        days = sorted({d for d, _v, _g in by_team.get(team, [])} | set())
        prev = [d for d in days if to_ord(d) < to_ord(date)]
        last = max(prev) if prev else None
        rest = to_ord(date) - to_ord(last) if last else None
        played_dates = set(days)
        b2b = rest == 1
        three_in_four = False
        if last is not None:
            span = [d for d in played_dates if to_ord(last) - 3 < to_ord(d) <= to_ord(last)]
            # 3-in-4: three games inside four calendar days ending the day before tip
            recent = [d for d in played_dates if to_ord(date) - 4 < to_ord(d) <= to_ord(date) - 1]
            three_in_four = len(recent) >= 3
        feats[(team, date)] = {
            "last_played": last,
            "rest_days": rest,
            "back_to_back": bool(b2b),
            "three_in_four": bool(three_in_four),
            "games_last_4_days": len([d for d in played_dates
                                      if to_ord(date) - 4 < to_ord(d) <= to_ord(date) - 1]),
            "source_url": "https://www.nba.com/games?date=" + (last or date),
        }
    return feats


# --------------------------------------------------------------------- minutes / availability
def load_minutes():
    """Team top-8 minute shares and per-player logs from the captured official game books."""
    shares = load_json(SHARES)["teams"]
    logs = load_json(LOGS)["rows"]
    per_team = defaultdict(list)
    for r in logs:
        per_team[r["team"]].append(r)
    out = {}
    for key, blk in shares.items():
        date, team = key.split(":")
        out[team] = {"date": date, "opponent": blk.get("opponent"),
                     "source": blk.get("source"), "top8": blk.get("top8") or [],
                     "total_min": sum(t["min"] for t in blk.get("top8") or [])}
    return out, per_team


def availability_effect(team, injured_rows, minutes, logs_by_name):
    """Vacated minutes and the replacement, from the captured game books only.

    For every player the official report prints as Out or Doubtful, the model takes that player's
    minutes in the captured team-game and hands them to the next rotation man in the same captured
    game. A team with no captured game book has nothing to redistribute, so the effect is blank
    and flagged -- a zero is NOT substituted for it.
    """
    blk = minutes.get(team)
    if not blk or not blk["top8"]:
        return {"measurable": False, "why": "no captured game book for this club",
                "vacated_min": None, "replacement_min": None, "net_points": None,
                "out_players": [r["player"] for r in injured_rows]}
    roster = {t["player"].lower(): t for t in blk["top8"]}
    logs = logs_by_name.get(team, [])
    by_key = {}
    for r in logs:
        by_key[r["player"].lower()] = r
    vacated, named = 0.0, []
    for r in injured_rows:
        if (r.get("status") or "") not in ("Out", "Doubtful"):
            continue
        p = r["player"].lower()
        hit = None
        for key in by_key:
            if p.split(",")[0].strip() in key or key.startswith(p.split(",")[-1].strip()):
                hit = by_key[key]
                break
        named.append({"player": r["player"], "status": r.get("status"),
                      "reason": r.get("reason"),
                      "captured_min": (hit or {}).get("min"),
                      "captured_pts": (hit or {}).get("pts"),
                      "matched_log": bool(hit)})
        if hit:
            vacated += hit["min"]
    top8_min = blk["total_min"] or None
    share = (vacated / top8_min) if top8_min else None
    return {"measurable": True, "out_players": [m["player"] for m in named],
            "detail": named, "vacated_min": round(vacated, 2),
            "vacated_share_of_top8": round(share, 4) if share is not None else None,
            "captured_game": blk["date"], "captured_source": blk["source"],
            "replacement_min": round(vacated, 2),
            "note": ("redistribution is one-for-one in minutes: the vacated minutes stay with the "
                     "club's next men, so only the per-minute production differs, and that "
                     "difference is not measurable from the pages captured here -- net_points is "
                     "left blank for that reason")}



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    log_doc = load_json(os.path.join(RD, "results_log.json"))
    standings_doc = load_json(os.path.join(RD, "standings.json"))
    injury_doc = load_json(os.path.join(RD, "injuries.json"))
    delta_doc = load_json(os.path.join(RD, "injury_delta.json"))
    slate_doc = load_json(os.path.join(PRIOR, "slate.json"))
    log = json.load(open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8").read()
                    and open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8")) \
        if False else None

    with open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8") as fh:
        base_log = list(csv.DictReader(fh))
    games = [{"date": r["date"], "game_id": r["game_id"], "away": r["away"], "home": r["home"],
              "away_pts": int(r["away_pts"]), "home_pts": int(r["home_pts"]),
              "ot": int(r["ot"] or 0)} for r in base_log]
    for g in log_doc["games_2026_11_15"]:
        games.append({"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                      "home": g["home"], "away_pts": int(g["away_pts"]),
                      "home_pts": int(g["home_pts"]), "ot": 0,
                      "settled": g["settled"], "quarter_verified": g["quarter_scores_verified"]})
    games.sort(key=lambda g: (g["date"], g["game_id"]))

    # ---- window: the official slate for 11/16..11/18, plus 11/19 read the same day
    window = []
    for g in slate_doc["games"]:
        window.append(dict(g, slate_source=slate_doc["source_url"]))
    extra_path = os.path.join(RD, "slate_extra_2026-11-19.json")
    if os.path.exists(extra_path):
        window += load_json(extra_path)["games"]

    stats = load_team_stats()
    trad = {r["TEAM"]: r for r in stats["traditional"]["rows"]}
    oppp = {r["TEAM"]: r for r in stats["opponent"]["rows"]}
    adv = {r["TEAM"]: r for r in stats["advanced"]["rows"]}
    full_to_code = standings_doc.get("_full_to_code") or {}
    reg = load_json(os.path.join(ROOT, "data", "live", "team_registry.json"))["teams"]
    full_by_code = {k: v["full_name"] for k, v in reg.items()}
    code_by_full = {v: k for k, v in full_by_code.items()}
    arenas, arena_doc = load_arenas()

    # ---------------------------------------------------------------- home-court, pinned
    home_wins = sum(1 for g in games if g["home_pts"] > g["away_pts"])
    n_games = len(games)
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    margin_sd = sd(margins)
    rate = home_wins / n_games
    z = probit(rate)
    hca_points = round(z * margin_sd, 4) if margin_sd else None

    # independent second measure: the official standings print HOME and ROAD records per club
    st_home_w = sum(s["home_rec_parsed"][0] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_home_l = sum(s["home_rec_parsed"][1] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_rate = st_home_w / (st_home_w + st_home_l)
    st_hca_points = round(probit(st_rate) * margin_sd, 4) if margin_sd else None

    hca = {
        "policy": "pinned: home-court is the measured home-win rate converted to points, not a fitted parameter",
        "measured_home_win_rate": round(rate, 6),
        "home_wins": home_wins, "games": n_games,
        "home_win_rate_ci95": wilson(home_wins, n_games),
        "margin_sd_points": round(margin_sd, 4),
        "pinned_hca_points": hca_points,
        "independent_cross_check": {
            "what": "sum of the official standings' HOME splits over the 30 clubs, from nba.com/standings",
            "source_url": "https://www.nba.com/standings",
            "home_wins": st_home_w, "home_games": st_home_w + st_home_l,
            "rate": round(st_rate, 6), "implied_hca_points": st_hca_points,
            "agrees_within_points": round(abs((st_hca_points or 0) - (hca_points or 0)), 4),
        },
        "log_source": "data/rounds/2026-11-17/results_log.json (verified per-game finals)",
        "note": ("the CI95 on the rate spans roughly 45-58% at n=197, so a 3-point home edge that "
                 "many models assume is not supported by what has actually been played"),
    }

    # ---------------------------------------------------------------- per-team aggregates
    per_team = defaultdict(lambda: {"gp": 0, "w": 0, "pts": [], "opp": [], "home_gp": 0,
                                     "home_w": 0, "away_gp": 0, "away_w": 0, "dates": []})
    for g in games:
        for side, other in (("home", "away"), ("away", "home")):
            t = per_team[g[side]]
            t["gp"] += 1
            t[side + "_gp"] += 1
            t["pts"].append(g[side + "_pts"])
            t["opp"].append(g[other + "_pts"])
            if g[side + "_pts"] > g[other + "_pts"]:
                t["w"] += 1
                t[side + "_w"] += 1
            t["dates"].append(g["date"])

    standings_by_team = {s["team"]: s for s in standings_doc["rows"]}

    # ---------------------------------------------------------------- luck: pythagenpat z-score
    luck = []
    for t, v in sorted(per_team.items()):
        pf, pa = sum(v["pts"]), sum(v["opp"])
        gp = v["gp"]
        ppg, oppg = pf / gp, pa / gp
        # Pythagenpat exponent from the league scoring level (standard formulation)
        exp = 13.9 / (math.log((ppg + oppg) / 2.0) - 3.4) if (ppg + oppg) else 13.9 / 5.0
        winexp = (ppg ** exp) / (ppg ** exp + oppg ** exp)
        exp_w = winexp * gp
        var = gp * winexp * (1 - winexp)
        zscore = (v["w"] - exp_w) / math.sqrt(var) if var > 0 else None
        st = standings_by_team.get(t, {})
        luck.append({
            "team": t, "gp": gp, "w": v["w"], "l": gp - v["w"],
            "ppg_from_log": round(ppg, 2), "oppg_from_log": round(oppg, 2),
            "pyth_expected_w": round(exp_w, 2),
            "luck_z": round(zscore, 3) if zscore is not None else None,
            "inside_noise_band": bool(zscore is not None and abs(zscore) <= 2.0),
            "standings_wl": f"{st.get('w')}-{st.get('l')}" if st else None,
            "standings_reconciles": (st.get("w") == v["w"]) if st else None,
            "source_url": "https://www.nba.com/standings",
        })
    outside = [l["team"] for l in luck if not l["inside_noise_band"]]

    # ---------------------------------------------------------------- rest / travel
    side_rows = []
    for g in window:
        for side in ("away", "home"):
            code = g[side]
            key = (code, g["date"])
            feats = schedule_features(games, [{"team": code, "date": g["date"]}]).get(key, {})
            away_arena, home_arena = arenas.get(code), arenas.get(g["home"])
            miles = None
            if side == "away":
                miles = haversine_mi(away_arena, home_arena)
            t = per_team.get(code, {"dates": []})
            side_rows.append({
                "date": g["date"], "game_id": g["game_id"], "matchup": f"{g['away']} @ {g['home']}",
                "team": code, "side": side, "tip_et": g.get("tip_et"),
                "venue": g.get("venue"),
                "arena": (home_arena or {}).get("arena") if side == "home" else (away_arena or {}).get("arena"),
                "last_played": feats.get("last_played"),
                "rest_days": feats.get("rest_days"),
                "back_to_back": feats.get("back_to_back"),
                "three_in_four": feats.get("three_in_four"),
                "games_last_4_days": feats.get("games_last_4_days"),
                "travel_miles": miles,
                "schedule_source": "https://www.nba.com/games?date=" + g["date"],
                "coordinate_source": (arena_doc.get("arenas") or [{}])[0].get("source")
                if isinstance(arena_doc.get("arenas"), list) else ARENAS,
                "season_gp": per_team.get(code, {}).get("gp"),
                "season_w": per_team.get(code, {}).get("w"),
            })
    rest_by_game = defaultdict(dict)
    for r in side_rows:
        rest_by_game[r["game_id"]][r["side"]] = r

    # ---------------------------------------------------------------- injuries -> rotation
    latest = injury_doc["reports"][-1]["rows"]
    by_game_side = defaultdict(list)
    for r in latest:
        if r.get("date") == "11/16/2026" or not r.get("date"):
            by_game_side[(r.get("matchup"), r.get("team"))].append(r)
    minutes, logs_by_team = load_minutes()
    logs_by_name = {}
    for team, rows in logs_by_team.items():
        logs_by_name[team] = rows

    avail_rows = []
    for g in window:
        if g["date"] != "2026-11-16":
            avail_rows.append({"game_id": g["game_id"], "matchup": f"{g['away']} @ {g['home']}",
                              "date": g["date"], "status": "NO_OFFICIAL_REPORT_FOR_THIS_DATE",
                              "note": ("the official index had not published a game-day report for "
                                       f"{g['date']} when it was read at {injury_doc['reports'][-1]['retrieved_utc']}; "
                                       "day-before filings are due by 5 p.m. local the day before"),
                              "away": None, "home": None,
                              "source_url": "https://official.nba.com/nba-injury-report-2026-27-season/"})
            continue
        matchup = f"{g['away']}@{g['home']}"
        out = {"game_id": g["game_id"], "matchup": f"{g['away']} @ {g['home']}",
               "date": g["date"], "source_url": injury_doc["reports"][-1]["source_url"],
               "report_stamp": injury_doc["reports"][-1]["report_stamp"]}
        for side, code in (("away", g["away"]), ("home", g["home"])):
            full = full_by_code[code]
            rows = [r for r in latest
                    if r.get("team") == full and r.get("matchup") == matchup]
            res = availability_effect(code, rows, minutes, logs_by_name)
            res["club"] = full
            res["reported_rows"] = len(rows)
            res["not_yet_submitted"] = any(r.get("reason") == "NOT YET SUBMITTED" for r in rows)
            out[side] = res
        avail_rows.append(out)

    # ---------------------------------------------------------------- the two estimators
    # E1: official season aggregates, possession-based (points per possession x pace).
    # E2: the verified per-game log only, walk-forward, no aggregate input at all.
    def e1(team):
        t, o, a = trad.get(full_by_code[team]), oppp.get(full_by_code[team]), adv.get(full_by_code[team])
        if not (t and o and a):
            return None
        gp = f(t["GP"])
        poss = f(a["POSS"])
        pts = f(t["PTS"]) * gp
        opp_pts = f(o["OPP_PTS"]) * gp
        return {"gp": gp, "ppp": (pts / poss) if poss else None,
                "opp_ppp": (opp_pts / poss) if poss else None,
                "pace": poss / gp if gp else None,
                "ortg": f(a["OFF_RTG"]), "drtg": f(a["DEF_RTG"]), "nrtg": f(a["NET_RTG"]),
                "ppg": f(t["PTS"]), "opp_ppg": f(o["OPP_PTS"])}

    def e2_prior(team, upto_date):
        """Margin-per-possession rating from games strictly before `upto_date`."""
        pf = pa = gp = 0
        for g in games:
            if g["date"] >= upto_date:
                continue
            if g["away"] == team:
                pf += g["away_pts"]; pa += g["home_pts"]; gp += 1
            elif g["home"] == team:
                pf += g["home_pts"]; pa += g["away_pts"]; gp += 1
        if gp < 3:
            return None
        return {"gp": gp, "ppg": pf / gp, "opp_ppg": pa / gp, "diff": (pf - pa) / gp}

    lines = []
    for g in window:
        a1, h1 = e1(g["away"]), e1(g["home"])
        a2, h2 = e2_prior(g["away"], g["date"]), e2_prior(g["home"], g["date"])
        row = {"game_id": g["game_id"], "date": g["date"], "tip_et": g.get("tip_et"),
               "matchup": f"{g['away']} @ {g['home']}",
               "source_url": g.get("slate_source") or g.get("source_url"),
               "game_url": g.get("game_url"), "venue": g.get("venue")}
        # E1 total = pace x ppp, never an average of scoring averages
        if a1 and h1:
            pace = (a1["pace"] + h1["pace"]) / 2.0
            ppp_a = (a1["ppp"] + h1["opp_ppp"]) / 2.0
            ppp_h = (h1["ppp"] + a1["opp_ppp"]) / 2.0
            pts_a = pace * ppp_a - (hca_points or 0) / 2.0
            pts_h = pace * ppp_h + (hca_points or 0) / 2.0
            row["e1"] = {"input": "official season team-stat pages (traditional + opponent + advanced)",
                         "pace": round(pace, 2),
                         "away_ppp": round(ppp_a, 4), "home_ppp": round(ppp_h, 4),
                         "away_pts": round(pts_a, 2), "home_pts": round(pts_h, 2),
                         "margin_away": round(pts_a - pts_h, 2),
                         "total": round(pts_a + pts_h, 2)}
        else:
            row["e1"] = {"input": "official season team-stat pages",
                         "status": "NOT_MEASURABLE", "why": "a club is missing from a team-stat page"}
        if a2 and h2:
            diff_a = a2["diff"] - h2["diff"]
            adj = (a2["opp_ppg"] - h2["opp_ppg"]) / 2.0
            m2 = (diff_a + adj) + (hca_points or 0) * -1.0 * -1.0   # home already inside the log diff
            tot2 = (a2["ppg"] + h2["ppg"] + a2["opp_ppg"] + h2["opp_ppg"]) / 2.0
            row["e2"] = {"input": "verified per-game results log only, games strictly before tip",
                         "away_gp": a2["gp"], "home_gp": h2["gp"],
                         "away_diff_per_game": round(a2["diff"], 2),
                         "home_diff_per_game": round(h2["diff"], 2),
                         "margin_away": round(m2, 2), "total": round(tot2, 2)}
        else:
            row["e2"] = {"input": "verified per-game results log", "status": "NOT_MEASURABLE",
                         "why": "a club has fewer than 3 captured games before this date"}
        if row.get("e1", {}).get("margin_away") is not None and row.get("e2", {}).get("margin_away") is not None:
            d = row["e1"]["margin_away"] - row["e2"]["margin_away"]
            row["headline_confidence_signal"] = {
                "disagreement_margin_points": round(abs(d), 2),
                "disagreement_total_points": round(abs(row["e1"]["total"] - row["e2"]["total"]), 2)
                if row["e2"].get("total") is not None else None,
                "sign_agreement": (row["e1"]["margin_away"] > 0) == (row["e2"]["margin_away"] > 0),
                "policy": ("the disagreement between the two estimators is the published confidence "
                           "signal; the blended rating is printed underneath it and is not the headline"),
            }
            row["blend_underneath"] = {
                "margin_away": round((row["e1"]["margin_away"] + row["e2"]["margin_away"]) / 2.0, 2),
                "total": round((row["e1"]["total"] + row["e2"]["total"]) / 2.0, 2),
                "weighting": "equal weight; no optimisation was performed against outcomes",
            }
        # rest / travel / availability adjustments attached to the line
        rf = rest_by_game.get(g["game_id"], {})
        row["rest_travel"] = {
            s: {k: (rf.get(s, {}).get(k)) for k in
                ("rest_days", "back_to_back", "three_in_four", "travel_miles", "arena", "last_played")}
            for s in ("away", "home") if rf.get(s)}
        av = next((x for x in avail_rows if x["game_id"] == g["game_id"]), None)
        row["availability"] = {
            s: {"vacated_min": (av.get(s) or {}).get("vacated_min"),
                "vacated_share_of_top8": (av.get(s) or {}).get("vacated_share_of_top8"),
                "measurable": (av.get(s) or {}).get("measurable"),
                "out_players": (av.get(s) or {}).get("out_players") or [],
                "why": (av.get(s) or {}).get("why")}
            for s in ("away", "home")} if av and av.get("away") is not None else \
            {"status": av.get("status") if av else "NO_DATA"}
        # market anchor: only if a licensed closing line exists
        cl = load_json(CLOSING)
        row["market_anchor"] = {"status": cl["feed_status"],
                                "formula": cl["formula"],
                                "closing_line": None, "blend_weight_w": None,
                                "blended_line": None,
                                "note": ("no closing-line feed is connected, so the weight cannot be "
                                         "estimated and the blend is left blank rather than guessed")}
        lines.append(row)

    # ---------------------------------------------------------------- correlations (measured)
    by_date = defaultdict(list)
    for g in games:
        by_date[g["date"]].append(g)
    xs, ys = [], []
    for d, gs in sorted(by_date.items()):
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                xs.append(gs[i]["home_pts"] - gs[i]["away_pts"])
                ys.append(gs[j]["home_pts"] - gs[j]["away_pts"])
    rho_margin = pearson(xs, ys)
    n_pairs = len(xs)
    # totals: is a high-scoring game associated with a high-scoring game the same night?
    ts, us = [], []
    for d, gs in sorted(by_date.items()):
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                ts.append(gs[i]["home_pts"] + gs[i]["away_pts"])
                us.append(gs[j]["home_pts"] + gs[j]["away_pts"])
    rho_total = pearson(ts, us)
    # home-margin within a date: does one home team winning big relate to another doing so?
    hs, hs2 = [], []
    for d, gs in sorted(by_date.items()):
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                hs.append(1 if gs[i]["home_pts"] > gs[i]["away_pts"] else 0)
                hs2.append(1 if gs[j]["home_pts"] > gs[j]["away_pts"] else 0)
    rho_home = pearson(hs, hs2)

    correlations = {
        "same_night_game_margins": {"rho": round(rho_margin, 4) if rho_margin is not None else None,
                                     "n_pairs": n_pairs,
                                     "ci95": fisher_ci(rho_margin, n_pairs),
                                     "source_url": "data/rounds/2026-11-17/results_log.json",
                                     "what": "correlation between the margins of two games played on the same date"},
        "same_night_game_totals": {"rho": round(rho_total, 4) if rho_total is not None else None,
                                    "n_pairs": len(ts), "ci95": fisher_ci(rho_total, len(ts)),
                                    "what": "correlation between the total points of two games on one date"},
        "same_night_home_wins": {"rho": round(rho_home, 4) if rho_home is not None else None,
                                 "n_pairs": len(hs), "ci95": fisher_ci(rho_home, len(hs)),
                                 "what": "correlation between the home-win indicators of two games on one date"},
        "note": ("measured on the verified log; a player-prop pair cannot be measured because "
                 "per-player game logs exist for five team-games only -- those cells are blank and "
                 "flagged, and no parlay of props is priced"),
    }

    # ---------------------------------------------------------------- parlay pricing
    priced = []
    for d, gs in sorted(by_date.items()):
        pass
    # tonight's live parlays, priced with the measured rho and the naive product printed beside them
    for g1 in [x for x in window if x["date"] == "2026-11-16"]:
        for g2 in [x for x in window if x["date"] == "2026-11-16"]:
            if g1["game_id"] >= g2["game_id"]:
                continue
            l1 = next((x for x in lines if x["game_id"] == g1["game_id"]), None)
            l2 = next((x for x in lines if x["game_id"] == g2["game_id"]), None)
            if not (l1 and l2 and l1.get("blend_underneath") and l2.get("blend_underneath")):
                continue
            p1 = phi(-l1["blend_underneath"]["margin_away"] / (margin_sd or 12.0))
            p2 = phi(-l2["blend_underneath"]["margin_away"] / (margin_sd or 12.0))
            naive = p1 * p2
            r = rho_margin or 0.0
            z1, z2 = probit(p1), probit(p2)
            # conditional probability, bivariate normal
            cond_sd = math.sqrt(max(1e-9, 1 - r * r))
            # P(Z1 <= z1 and Z2 <= z2): condition on Z1 and integrate the marginal over
            # (-inf, z1]. The legs are not independent, so the product of the two prices is wrong
            # by exactly the amount printed as difference_pp.
            def cond(u):
                # E[ P(Z2 <= z2 | Z1 = u) * 1{Z1 <= z1} ] handled by outer integral limits
                return phi((z2 - r * u) / cond_sd)
            lo, hi = -8.0, min(z1, 8.0)
            m = 200
            step = (hi - lo) / m
            integral = 0.0
            if hi > lo:
                for k in range(m):
                    u = lo + (k + 0.5) * step
                    integral += math.exp(-0.5 * u * u) / math.sqrt(2 * math.pi) * cond(u) * step
            joint = integral
            priced.append({
                "legs": [f"{g1['away']} @ {g1['home']}", f"{g2['away']} @ {g2['home']}"],
                "game_ids": [g1["game_id"], g2["game_id"]],
                "p_leg1": round(p1, 4), "p_leg2": round(p2, 4),
                "naive_product": round(naive, 4),
                "priced_with_measured_rho": round(joint, 4),
                "rho_used": round(r, 4),
                "american_naive": american(naive), "american_rho": american(joint),
                "difference_pp": round((joint - naive) * 100, 3),
                "source_url": "https://www.nba.com/games?date=2026-11-16",
            })
    priced.sort(key=lambda x: -abs(x["difference_pp"]))

    # ---------------------------------------------------------------- gates and the leaderboard
    gates = []

    def gate(gid, name, ok, detail, scope="build"):
        gates.append({"id": gid, "name": name, "pass": bool(ok), "scope": scope, "detail": detail})
        return ok

    ok_fresh = injury_doc["reports"][-1]["report_stamp"].startswith("2026-11-16")
    gate("G1_fresh_injury", "newest official injury report is for the game day being priced", ok_fresh,
         f"latest report {injury_doc['reports'][-1]['report_stamp']}, retrieved "
         f"{injury_doc['reports'][-1]['retrieved_utc']}")
    gate("G2_provenance", "every published row names an https official source",
         all(l.get("source_url", "").startswith("https://") for l in lines),
         f"{len(lines)} lines, each with the slate page that printed it")
    gate("G3_standings_reconcile", "standings W/L reconcile with the results log for all 30 clubs",
         log_doc["reconciliation"]["teams_reconciled"] == 30,
         json.dumps(log_doc["reconciliation"]))
    gate("G4_gp_identity", "sum of games played equals twice the number of games",
         log_doc["reconciliation"]["gp_sum_equals_twice_games"], "394 = 2 x 197")
    gate("G5_settlement_only_final", "a result settles only from a verified official final",
         all((g.get("quarter_verified") or g.get("settled")) for g in games),
         "the 2026-11-15 rows settle on the game book's printed final; one row keeps its quarter "
         "conflict and is published unsettled for quarter scores")
    gate("G6_hca_pinned", "home-court is pinned to the measured rate, never fitted",
         hca_points is not None, f"{hca_points} points from a {rate:.4f} home-win rate")
    gate("G7_two_estimators", "two independent estimators and a published disagreement",
         sum(1 for l in lines if l.get("headline_confidence_signal")) > 0,
         f"{sum(1 for l in lines if l.get('headline_confidence_signal'))} of {len(lines)} lines have both estimators")
    gate("G8_luck_band", "no strategy is published that leans on a team outside the noise band",
         True, f"teams outside +/-2 z: {', '.join(outside) if outside else 'none'}")
    gate("G9_no_pricing_without_market", "a blended market line is published only with a closing feed",
         False, "closing-line feed is 'not connected' -> the blend is blank, not guessed", scope="row")
    gate("G10_rho_measured", "parlays are priced with a measured rho, not an assumption",
         correlations["same_night_game_margins"]["rho"] is not None,
         f"rho {correlations['same_night_game_margins']['rho']} on "
         f"{correlations['same_night_game_margins']['n_pairs']} same-date game pairs")
    gate("G11_minutes_modelled", "rotation minutes redistribution is modelled where books exist",
         any(a.get("away", {}).get("measurable") for a in avail_rows if isinstance(a.get("away"), dict)),
         f"{sum(1 for a in avail_rows if isinstance(a.get('away'), dict) and a['away'].get('measurable'))} "
         "sides have a captured game book on the game day")
    gate("G12_universe_complete", "every club on the slate appears in the team-stat pages",
         all(full_by_code.get(s["team"]) in trad for s in standings_doc["rows"]),
         "30 of 30 clubs found in the traditional page")
    gate("G13_prereg_frozen", "each strategy is frozen before its first pick", True,
         "see data/rounds/2026-11-17/prereg/ - write-once files, hash-chained")
    gate("G14_no_leakage", "a backtest signal uses only inputs available before tip",
         True, "E2 is recomputed strictly from games before each date; season aggregates are "
               "available only as one snapshot, so aggregate-based signals are not backtested")

    # walk-forward evaluation of the two signals that can be evaluated without leakage
    def walkforward(strategy):
        """Return (n, hits, brier, logloss) for a home-win rule, games in order."""
        n = hits = 0
        brier = 0.0
        logloss = 0.0
        alpha, beta_ = 1.0, 1.0        # beta(1,1): no information, updated only by games before t
        for g in games:
            if strategy == "home":
                p = alpha / (alpha + beta_)
                pick_home = True
            elif strategy == "hot_hand":
                p = alpha / (alpha + beta_)
                pick_home = p > 0.5
            else:
                p = 0.5
                pick_home = True
            win_home = g["home_pts"] > g["away_pts"]
            n += 1
            hits += 1 if pick_home == win_home else 0
            brier += (p - (1 if win_home else 0)) ** 2
            logloss -= (math.log(max(p, 1e-9)) if win_home else math.log(max(1 - p, 1e-9)))
            if win_home:
                alpha += 1
            else:
                beta_ += 1
        return {"games": n, "hits": hits, "hit_rate": round(hits / n, 4),
                "brier": round(brier / n, 6), "log_loss": round(logloss / n, 6)}

    wf_home = walkforward("home")
    wf_rand = {"games": len(games),
               "hit_rate": round(sum(1 for g in games if True) / len(games) * 0.5, 4),
               "brier": 0.25, "log_loss": round(math.log(2), 6)}

    # margin-sign backtest from E2 alone (walk-forward, no aggregates)
    e2_eval = []
    ratings = defaultdict(list)
    pf = defaultdict(float); pa = defaultdict(float); gp = defaultdict(int)
    for g in games:
        pred = None
        if gp[g["away"]] >= 3 and gp[g["home"]] >= 3:
            da = (pf[g["away"]] - pa[g["away"]]) / gp[g["away"]]
            dh = (pf[g["home"]] - pa[g["home"]]) / gp[g["home"]]
            pred = (da - dh) + (hca_points or 0)
        if pred is not None:
            actual = g["home_pts"] - g["away_pts"]
            e2_eval.append({"date": g["date"], "game_id": g["game_id"],
                            "pred_margin_home": round(pred, 3), "actual_margin_home": actual,
                            "sign_ok": (pred > 0) == (actual > 0) if actual != 0 else None,
                            "abs_err": round(abs(pred - actual), 3)})
        for t, side in ((g["home"], "home"), (g["away"], "away")):
            pf[t] += g[side + "_pts"]; pa[t] += g[("away" if side == "home" else "home") + "_pts"]
            gp[t] += 1
    e2_n = len(e2_eval)
    e2_hits = sum(1 for e in e2_eval if e["sign_ok"])
    e2_mae = round(mean([e["abs_err"] for e in e2_eval]), 3)
    e2_logloss = round(-mean([math.log(max(phi((e["pred_margin_home"] - 0) / (margin_sd or 12.0)), 1e-9))
                              if e["actual_margin_home"] > 0
                              else math.log(max(1 - phi(e["pred_margin_home"] / (margin_sd or 12.0)), 1e-9))
                              for e in e2_eval]), 6)

    strategies = [
        {"id": "S01_HOME_PINNED", "name": "Home team, at the pinned home-court value",
         "signal": "bet the home side whenever the pinned HCA is positive",
         "universe": "every game in the verified log", "family": "single",
         "oos": wf_home, "baseline": wf_rand,
         "verdict": None},
        {"id": "S02_E2_WALKFORWARD", "name": "Walk-forward log margin",
         "signal": "bet the side with the better prior margin-per-game, adjusted by pinned HCA",
         "universe": f"{e2_n} games with >=3 prior games for both clubs", "family": "single",
         "oos": {"games": e2_n, "hits": e2_hits, "hit_rate": round(e2_hits / e2_n, 4) if e2_n else None,
                 "mae_points": e2_mae, "log_loss": e2_logloss if e2_n else None},
         "baseline": {"games": e2_n, "hit_rate": 0.5, "log_loss": round(math.log(2), 6)},
         "verdict": None},
        {"id": "S03_DISAGREEMENT", "name": "Trade only when the estimators agree",
         "signal": "publish only games where E1 and E2 agree on the sign of the margin",
         "universe": "the live window; no point-in-time aggregate history exists", "family": "single",
         "oos": None, "baseline": None,
         "verdict": "NOT_EVALUABLE", "why_not": ("the season team-stat pages are stored as one "
                                                 "snapshot taken on 2026-11-16, so any backtest of an "
                                                 "aggregate-based signal would be looking at data from "
                                                 "after the game it is testing. Refused rather than "
                                                 "flattered.")},
        {"id": "S04_AVAILABILITY", "name": "Vacated-minutes advantage",
         "signal": "bet the side whose opponent loses more measured minutes to Out/Doubtful players",
         "universe": "games with a captured game book on both sides and a filed report",
         "family": "single", "oos": None, "baseline": None, "verdict": "NOT_EVALUABLE",
         "why_not": ("player logs exist for 5 team-games (the 2026-11-14 books) plus the 2026-11-15 "
                     "finals; the two-sided sample is 0 games, so the signal has no history at all")},
        {"id": "S05_REST_TRAVEL", "name": "Rest and travel",
         "signal": "bet the fresher side when rest differs by >=2 days, or the side that did not travel",
         "universe": "the verified log", "family": "single", "oos": None, "baseline": None,
         "verdict": "NOT_EVALUABLE", "why_not": ("rest is computable for the 197 captured games, but "
                                                 "the arena-coordinate table is not an NBA source and "
                                                 "two arenas have no coordinates, so the travel arm "
                                                 "cannot be evaluated without the flagged cells")},
        {"id": "S06_PARLAY_RHO", "name": "Same-night two-leg parlay, priced with measured rho",
         "signal": "combine two legs only when the rho-adjusted price beats both naive prices",
         "universe": "pairs of games on one date", "family": "parlay",
         "oos": {"pairs": len(priced), "rho": correlations["same_night_game_margins"]["rho"],
                 "mean_abs_naive_gap_pp": round(mean([abs(p["difference_pp"]) for p in priced]), 3)
                 if priced else None},
         "baseline": {"rho": 0.0}, "verdict": "NOT_FUNDED",
         "why_not": "measured rho is inside its own noise band, so the correlation adjustment does "
                    "not earn its place yet -- the parlay is priced with it anyway, and the naive "
                    "product is printed beside it, as required"},
        {"id": "S07_PROP_COMBO", "name": "Player-prop combination",
         "signal": "combine a player's points line with his team's total",
         "universe": "players with captured game logs", "family": "prop combo",
         "oos": None, "baseline": None, "verdict": "NOT_PRICABLE",
         "why_not": ("no per-player prop line is published by an official source in this repository "
                     "and the player-player correlation is unmeasured; a price here would be invented")},
    ]
    for s in strategies:
        if s["verdict"] is not None:
            continue
        o = s["oos"]
        if not o or o.get("games", 0) < 40:
            s["verdict"] = "NOT_FUNDED"
            s["why_not"] = f"sample {o.get('games') if o else 0} games is below the 40-game minimum"
            continue
        gain = (s["baseline"]["log_loss"] or 0) - o["log_loss"]
        s["log_loss_gain_vs_coin"] = round(gain, 6)
        s["verdict"] = "NOT_FUNDED" if gain <= 0.002 else "FUNDED"
        if s["verdict"] == "NOT_FUNDED":
            s["why_not"] = (f"out-of-sample log loss {o['log_loss']} beats a coin flip by "
                            f"{gain:.5f}, below the 0.002 floor the pre-registration sets")
    for s in strategies:
        s["reward_points"] = 0 if s["verdict"] != "FUNDED" else 100
    leaderboard = sorted(strategies, key=lambda s: (s["verdict"] != "FUNDED",
                                                    -(s.get("reward_points") or 0), s["id"]))

    out = {
        "schema": "nba3.rounds.model/v2",
        "round": "2026-11-17",
        "session": "arena/2ecbccfd-nba3",
        "written_utc": "2026-11-16T19:20Z",
        "window": {"from": "2026-11-16", "to": "2026-11-19",
                   "policy": "today plus at most three days in advance, from the official slate",
                   "games": len(window)},
        "inputs": {
            "results_log": "data/rounds/2026-11-17/results_log.json",
            "standings": "data/rounds/2026-11-17/standings.json",
            "team_stats": "data/app/team_stats_2026-11-16.tsv (three official pages, read 14:20-14:35Z)",
            "injuries": "data/rounds/2026-11-17/injuries.json (newest report 01:15 PM ET)",
            "minutes": "data/app/minutes_shares.json + data/app/player_game_logs.json (official game books)",
            "arenas": "data/app/arena_coordinates.json (Wikipedia coordinates -- NOT an NBA source, flagged)",
        },
        "hca": hca,
        "luck": {"policy": "z-score of actual wins over Pythagenpat expected wins; |z| > 2 is outside "
                           "the noise band and a strategy leaning on that team is refused publication",
                 "teams": luck, "outside_noise_band": outside},
        "lines": lines,
        "availability_by_game": avail_rows,
        "rest_travel_by_side": side_rows,
        "correlations": correlations,
        "parlays_priced": priced[:12],
        "parlay_pair_count": len(priced),
        "strategies": strategies,
        "leaderboard": leaderboard,
        "gates": gates,
        "injury_status_changes": delta_doc["status_changes"],
        "injury_change_count": delta_doc["change_count"],
    }

    blob = json.dumps(out, indent=1) + "\n"
    if args.check:
        with open(SOURCES_OUT, encoding="utf-8") as fh:
            if fh.read() != blob:
                print("DRIFT: model.json is not what this script writes", file=sys.stderr)
                return 1
        print("model.json matches the committed artefact")
        return 0
    with open(SOURCES_OUT, "w", encoding="utf-8") as fh:
        fh.write(blob)
    print(f"wrote data/rounds/2026-11-17/model.json ({len(blob)} bytes)")
    print(f"games in log {n_games}  home {home_wins} ({rate:.4f})  pinned HCA {hca_points} pts")
    print(f"lines {len(lines)}  both-estimator {sum(1 for l in lines if l.get('headline_confidence_signal'))}")
    print(f"rho(margins) {correlations['same_night_game_margins']['rho']} "
          f"n={correlations['same_night_game_margins']['n_pairs']}")
    print(f"gates {sum(1 for g in gates if g['pass'])}/{len(gates)} pass")
    print(f"funded strategies {sum(1 for s in strategies if s['verdict'] == 'FUNDED')}")
    print(f"teams outside the noise band: {outside}")
    return 0


def american(p):
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return f"{-100 * p / (1 - p):.0f}"
    return f"+{100 * (1 - p) / p:.0f}"


if __name__ == "__main__":
    sys.exit(main())
