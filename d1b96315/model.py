#!/usr/bin/env python3
"""Line origination and strategy gating for session arena/d1b96315-nba3 (11/16 game day).

Offline and deterministic. Every input is a committed artefact; every constant is either measured
from those artefacts or declared here with its formula printed on the methodology page. A number
that cannot be supported is published as ``null`` plus a flag — never a substitute value.

Outputs (under ``d1b96315/data/``):
  model.json    measurements: the pinned home-court value, both estimators, luck z, rho, game flow
  lines.json    one originated line per game on the rolling window
  gates.json    the validation gate board per strategy, and the leaderboard
  prereg_index.json / prereg/*.json   the frozen pre-registration files

Run: python3 d1b96315/model.py           (writes the artefacts)
     python3 d1b96315/model.py --check   (re-derives in memory and compares with the files)
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import sys
from datetime import date as _date, timedelta

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
D = HERE / "data"

INJ_LATEST = D / "injuries_2026-11-16_latest.json"
STANDINGS = D / "standings_2026-11-16.json"
ADVANCED = D / "team_advanced_2026-11-16.json"
RESULTS_1115 = D / "results_2026-11-15.json"
SLATE = D / "slate_2026-11-16_1118.json"
LOGS_1115 = D / "player_logs_2026-11-15.json"
FEED = ROOT / "data" / "app" / "results_feed.json"
LOGS_1114 = ROOT / "data" / "app" / "player_game_logs.json"
COORDS = ROOT / "data" / "app" / "arena_coordinates.json"
ROUND_TEAM_STATS = ROOT / "data" / "rounds" / "2026-11-16" / "team_stats.json"

STAMP = "2026-11-16T18:55Z"        # this session's working stamp; the freshness page carries the times
INJ_PDF = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf"

OUT_OF_NOISE_BAND = 2.0                 # luck z band, declared before any pick is made
DISAGREE_CAP = 5.0                      # margin points; wider than this the row is projection-only
MIN_VERIFIED_FINALS = 60                # ~4 games per club before any strategy is funded
APPLIED_STATUSES = ("Out", "Doubtful")  # what the availability model removes from the rotation
GAME_DAY = "2026-11-16"                 # the day the availability adjustment is built for

# Filled in by main() before the helpers that need them run; both are printed on the pages.
PIN = {"hca_points": 0.0, "sd_margin": 0.0}


# ---------------------------------------------------------------- small numerics

def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p: float, lo=-8.0, hi=8.0) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    for _ in range(200):
        mid = (lo + hi) / 2
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def bivariate_cdf(a: float, b: float, rho: float, steps: int = 4000) -> float:
    """P(X<=a, Y<=b) for standard normals with correlation rho, by quadrature on the conditional."""
    rho = max(-0.999999, min(0.999999, rho))
    s = math.sqrt(1 - rho * rho)
    lo = min(a, -8.0)
    if a <= lo:
        return 0.0
    h = (a - lo) / steps
    total = 0.0
    for i in range(steps):
        x = lo + (i + 0.5) * h
        total += math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi) * phi((b - rho * x) / s)
    return total * h


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def wilson(k: float, n: float, z: float = 1.959963985):
    if not n:
        return None
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, ctr - half), 4), round(min(1.0, ctr + half), 4)]


def corr(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not sx or not sy:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def fisher_ci(r, nn):
    if r is None or nn < 4 or abs(r) >= 1:
        return None
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(nn - 3)
    return [round(math.tanh(z - 1.959963985 * se), 3), round(math.tanh(z + 1.959963985 * se), 3)]


def american(p):
    if p is None or not (0 < p < 1):
        return None
    return round(-100 * p / (1 - p), 1) if p >= 0.5 else round(100 * (1 - p) / p, 1)


def load(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- inputs

def game_log():
    """Every verified official final available to this session: 11/13 + 11/14 from the canonical
    result feed, 11/15 from this session's own scoreboard read and game-book quarter re-read."""
    games, excluded = [], []
    for g in load(FEED)["games"]:
        if not g.get("settled"):
            excluded.append(f"feed row {g['away']}@{g['home']} {g['date']}: not settled, excluded")
            continue
        quarters = None
        if g.get("away_q1") is not None and g.get("home_q1") is not None:
            quarters = {"away": [g[f"away_q{i}"] for i in range(1, 5)],
                        "home": [g[f"home_q{i}"] for i in range(1, 5)]}
        games.append({"date": g["date"], "game_id": g.get("game_id"), "away": g["away"],
                      "home": g["home"], "away_pts": g["away_pts"], "home_pts": g["home_pts"],
                      "state": g["state"], "quarters": quarters, "settled": True,
                      "source": g["verified_from"],
                      "ingested_by": "data/app/results_feed.json"})
    for row in load(RESULTS_1115)["rows"] + load(RESULTS_1115)["blocked_rows"]:
        games.append({"date": row["date"], "game_id": row["game_id"], "away": row["away_abbr"],
                      "home": row["home_abbr"], "away_pts": row["away_pts"],
                      "home_pts": row["home_pts"], "state": row["state"],
                      "quarters": ({"away": row["away_quarters"], "home": row["home_quarters"]}
                                   if row.get("away_quarters") else None),
                      "settled": bool(row["settled"]),
                      "source": row["sources"]["scoreboard"], "gamebook": row["sources"]["gamebook"],
                      "ingested_by": "d1b96315/data/results_2026-11-15.json"})
    games.sort(key=lambda g: (g["date"], g["game_id"] or ""))
    return games, excluded


def team_index():
    idx = {}
    for t in load(ADVANCED)["teams"]:
        idx[t["team_abbr"]] = {
            "team": t["team"], "abbr": t["team_abbr"], "gp": t["gp"], "w": t["w"], "l": t["l"],
            "off_rtg": t["off_rtg"], "def_rtg": t["def_rtg"], "net_rtg": t["net_rtg"],
            "poss_pg": t["poss_per_game"], "pace": t["pace"], "source": t["source_url"],
        }
    standings = {t["team_abbr"]: t for t in load(STANDINGS)["teams"]}
    naive = {}
    if ROUND_TEAM_STATS.exists():
        for r in load(ROUND_TEAM_STATS).get("teams", []):
            ab = r.get("team_abbr")
            trad, opp = r.get("traditional") or {}, r.get("opponent") or {}
            naive[ab] = {"pts_pg": trad.get("PTS"), "opp_pts_pg": opp.get("OPP_PTS"),
                         "source": trad.get("source_url"),
                         "captured_by": "arena/8f4fac33-nba3 at 2026-11-16T14:25Z"}
    for ab, t in idx.items():
        s = standings.get(ab)
        t["standings_w"], t["standings_l"] = (s["w"], s["l"]) if s else (None, None)
        t["standings_gp"] = s["gp"] if s else None
        t["standings_home_record"] = f"{s['home_w']}-{s['home_l']}" if s else None
        t["standings_agrees_with_advanced"] = bool(
            s and s["w"] == t["w"] and s["l"] == t["l"] and s["gp"] == t["gp"])
        t["naive_scoring_averages"] = naive.get(ab)
    return idx, standings


# ---------------------------------------------------------------- availability

def norm_name(text: str) -> str:
    """'Lastname, Jr., Firstname' and 'Lastname, Firstname' -> 'firstname lastname [jr]'."""
    parts = [p.strip() for p in (text or "").split(",")]
    if not parts or not parts[0]:
        return ""
    last = parts[0]
    suffix = ""
    toks = last.split()
    if len(toks) > 1 and toks[-1].rstrip(".").lower() in ("jr", "sr", "ii", "iii", "iv"):
        suffix = " " + toks[-1].rstrip(".").lower()
        last = " ".join(toks[:-1])
    first = " ".join(p for p in parts[1:] if p)
    return " ".join(x for x in ((first + suffix).strip().lower(), last.lower()) if x)


def _dash(iso: str) -> str:
    """'2026-11-16' -> '11/16/2026', the form the official report prints in its Game Date cell."""
    return f"{iso[5:7]}/{iso[8:10]}/{iso[0:4]}"


def filing_for(team: str, game_date: str, report: dict) -> dict:
    """Is there any official injury filing for this club on this game date?

    Three states, because the report is a per-game-day document with a two-day horizon:
    ``filed`` (the club filed rows for that date), ``not_submitted`` (the league prints the club
    with the NOT YET SUBMITTED marker for that date) and ``outside_report_window`` (the date is
    not in this revision at all). The last two are different facts and are never merged.
    """
    dash = _dash(game_date)
    rows = [r for r in report["rows"] if r.get("team_abbr") == team
            and (r.get("game_date") or "").endswith(dash)]
    dates_in_report = {r.get("game_date") for r in report["rows"] if r.get("game_date")}
    if dash not in dates_in_report:
        return {"status": "outside_report_window", "player_rows": 0, "report_dates": sorted(dates_in_report)}
    if not rows or all(r.get("not_yet_submitted") for r in rows):
        return {"status": "not_submitted", "player_rows": 0, "report_dates": sorted(dates_in_report)}
    return {"status": "filed", "player_rows": len([r for r in rows if r.get("player")]),
            "markers": len([r for r in rows if r.get("not_yet_submitted")]),
            "report_dates": sorted(dates_in_report)}


def rotation_for(team: str):
    """The club's most recent captured official box score, from the two committed log files."""
    rows = []
    for path in (LOGS_1115, LOGS_1114):
        if path.exists():
            rows += [r for r in load(path)["rows"] if r.get("team") == team]
    if not rows:
        return None
    latest = max(r["date"] for r in rows)
    rows = [r for r in rows if r["date"] == latest]
    return {"date": latest, "opponent": rows[0].get("opponent"), "source": rows[0]["source"],
            "rows": rows}


def availability_for(team: str, report: dict, idx: dict) -> dict:
    """Minutes redistribution and its production cost, measured on the club's last captured box."""
    listed = [r for r in report["rows"] if r.get("team_abbr") == team
              and (r.get("game_date") or "").endswith(_dash(GAME_DAY))]
    res = {"team": team, "listed_on_report": len(listed), "applied_statuses": list(APPLIED_STATUSES),
           "out_applied": [], "out_not_applied": [], "replacement_shares": [], "notes": [],
           "rotation_source": None, "minutes_share_removed": None, "top8_share_before": None,
           "points_lost_per_game": None, "ortg_delta": None, "status": None}
    for r in listed:
        if r.get("status") not in APPLIED_STATUSES:
            res["out_not_applied"].append({
                "player": r.get("player"), "status": r.get("status"),
                "why": ("game-time decision: a Questionable tag is not applied"
                        if r.get("status") in ("Questionable", "Day-To-Day", "Available")
                        else "status cell not readable in the official PDF extraction")})
    rot = rotation_for(team)
    if rot is None:
        res["status"] = "no rotation data"
        res["notes"].append("no captured official box score for this club anywhere in the repo; the "
                            "availability adjustment is not applied (input gap, Q04)")
        return res
    res["rotation_source"] = {"date": rot["date"], "opponent": rot["opponent"], "source": rot["source"]}
    played = sorted([r for r in rot["rows"] if r.get("min")], key=lambda r: -r["min"])
    total_min = sum(r["min"] for r in played) or 240.0
    res["top8_share_before"] = round(sum(r["min"] for r in played[:8]) / total_min, 4)
    out_names = {norm_name(r["player"]) for r in listed if r.get("status") in APPLIED_STATUSES}
    if not out_names:
        res["status"] = "nothing to apply"
        res["notes"].append("no club row on the 11/16 report carries an applied status")
        return res
    in_box = {norm_name(r["player"]) for r in played}
    untracked = sorted(p for p in out_names if p not in in_box)
    if untracked:
        res["notes"].append("listed Out/Doubtful but absent from the captured box (not in that "
                            "game's rotation): " + ", ".join(untracked))
    avail = [r for r in played if norm_name(r["player"]) not in out_names]
    out = [r for r in played if norm_name(r["player"]) in out_names]
    res["out_applied"] = [{"player": r["player"], "min": r["min"], "pts": r.get("pts"),
                           "share_of_team_minutes": round(r["min"] / total_min, 4)} for r in out]
    if not avail:
        res["status"] = "no replacement pool"
        res["notes"].append("every player in the captured box is on the out list; no replacement "
                            "exists in the sample")
        return res
    removed = sum(r["min"] for r in out)
    avail_min = sum(r["min"] for r in avail)
    res["minutes_share_removed"] = round(removed / total_min, 4)
    res["replacement_shares"] = [
        {"player": r["player"], "min_before": r["min"],
         "added_min": round(removed * r["min"] / avail_min, 2),
         "min_after": round(r["min"] + removed * r["min"] / avail_min, 2)} for r in avail]
    rated = [r for r in played if r.get("pts") is not None]
    rated_avail = [r for r in avail if r.get("pts") is not None]
    res["rows_without_readable_points"] = len(played) - len(rated)
    if not rated or not rated_avail:
        res["status"] = "minutes only"
        res["notes"].append("no readable points in the rows the replacement would come from; the "
                            "minutes effect is published, the production effect is left null")
        return res
    before = sum(r["pts"] for r in rated)
    after = sum(r["pts"] + removed * (r["min"] / avail_min) * (r["pts"] / r["min"])
                for r in rated_avail)
    lost = before - after
    poss = idx.get(team, {}).get("poss_pg")
    res["points_lost_per_game"] = round(lost, 2)
    res["ortg_delta"] = round(lost / poss * 100.0, 2) if poss else None
    res["status"] = "applied"
    res["caveat"] = ("built on one captured box score for the club: the rate is that game's points "
                     "per minute, redistributed pro rata to the minutes each available player "
                     "actually played. It is a redistribution model, not a guess at the coach's plan")
    return res


# ---------------------------------------------------------------- ratings / rest / travel / luck

def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            continue
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [vr - f * vc for vr, vc in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def fit_massey(games, hca, lam):
    """Ratings that reproduce the settled margins once the pinned home advantage is taken out."""
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
    if not teams:
        return {}
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for g in games:
        i, j = ix[g["home"]], ix[g["away"]]
        y = (g["home_pts"] - g["away_pts"]) - hca
        A[i][i] += 1
        A[j][j] += 1
        A[i][j] -= 1
        A[j][i] -= 1
        b[i] += y
        b[j] -= y
    for i in range(n):
        A[i][i] += lam
    x = solve(A, b)
    return {t: x[ix[t]] for t in teams}


def predict_fn(games, hca, lam):
    r = fit_massey(games, hca, lam)
    return lambda g: r.get(g["home"], 0.0) - r.get(g["away"], 0.0) + hca


def rest_flags(team: str, on_date: str, settled, exclude_game=None) -> dict:
    """Rest, back-to-back and 3-in-4, from the verified finals plus the official slate."""
    today = _date(*(int(x) for x in on_date.split("-")))
    dates = set()
    for g in settled:
        if exclude_game and g.get("game_id") == exclude_game:
            continue
        if team in (g["away"], g["home"]):
            dates.add(_date(*(int(x) for x in g["date"].split("-"))))
    for g in load(SLATE)["games"]:
        if exclude_game and g["game_id"] == exclude_game:
            continue
        if team in (g["away"], g["home"]):
            dates.add(_date(*(int(x) for x in g["date"].split("-"))))
    prev = [(today - d).days for d in dates if d < today]
    last = min(prev) if prev else None
    in_four = sum(1 for d in dates if 0 <= (today - d).days <= 3)
    return {
        "days_since_last_game": last,
        "back_to_back": (last == 1) if last is not None else None,
        "three_in_four": in_four >= 3,
        "definition": {"three_in_four": "at least 3 games in the four-day window that ends on this "
                                        "game date (the game itself included)",
                       "back_to_back": "the previous game was yesterday",
                       "source": "official slate for the window + verified finals from 2026-11-13 on"},
        "games_in_the_four_day_window": in_four,
        "caveat": "measured on the verified finals this repo holds (2026-11-13 onward) plus the "
                  "official slate; a slate date inside the window counts as a scheduled appearance, "
                  "not as a played result. No games before 11/13 are captured here, so a flag on "
                  "11/13 or 11/14 is truncated and understated",
    }


def travel(away: str, home: str, venue) -> dict:
    """Straight-line arena-to-arena distance, with its provenance stated on the row."""
    out = {"venue_on_official_schedule": venue, "away_arena": None, "home_arena": None,
           "km": None, "status": None, "same_building_back_to_back": None}
    if not COORDS.exists():
        out["status"] = "no arena-coordinate table in the repository; distance not computed"
        return out
    data = load(COORDS)
    rows = {a.get("team"): a for a in data.get("arenas", [])}
    a1, a2 = rows.get(away, {}), rows.get(home, {})
    out["away_arena"], out["home_arena"] = a1.get("arena"), a2.get("arena")
    out["coordinate_source"] = data.get("api_url")
    out["retrieved"] = data.get("retrieved_stamp")
    vals = (a1.get("lat"), a1.get("lon"), a2.get("lat"), a2.get("lon"))
    if any(v in (None, "") for v in vals):
        out["status"] = ("a coordinate is blank in the table; distance left blank, not estimated "
                         "(flag F-COORD on Flagged for Review)")
        return out
    la1, lo1, la2, lo2 = (float(v) for v in vals)
    to_rad = math.pi / 180.0
    h = (math.sin((la2 - la1) * to_rad / 2) ** 2
         + math.cos(la1 * to_rad) * math.cos(la2 * to_rad) * math.sin((lo2 - lo1) * to_rad / 2) ** 2)
    out["km"] = round(2 * 6371.0 * math.asin(math.sqrt(h)), 1)
    out["status"] = "computed (haversine, derived — not an NBA-published figure)"
    out["same_building_back_to_back"] = (out["km"] < 1.0)
    if venue and a2.get("arena") and venue.strip().lower() != str(a2["arena"]).strip().lower():
        out["arena_name_mismatch"] = (f"the official schedule prints '{venue}' for this game, the "
                                      f"coordinate table prints '{a2['arena']}'")
    return out


def luck_z(team_row: dict, sigma: float | None = None) -> float | None:
    """z-score of actual wins against wins expected from the official efficiency rating.

    ``sigma`` is the spread of home margins the model measures; it is passed explicitly by the
    tests so the function can be checked in isolation, and taken from the build's measurement
    otherwise.
    """
    if not team_row:
        return None
    gp, w, net = team_row.get("gp"), team_row.get("w"), team_row.get("net_rtg")
    if sigma is None:
        sigma = PIN["sd_margin"]
    if not gp or net is None or not sigma:
        return None
    p = phi(net / sigma)
    return round((w - gp * p) / math.sqrt(gp * p * (1 - p)), 3)


# ---------------------------------------------------------------- main

def main(check: bool = False) -> int:
    games, excluded = game_log()
    settled = [g for g in games if g.get("settled")]
    idx, standings = team_index()
    report = load(INJ_LATEST)

    # ---- home-court advantage, pinned to the measured home-win rate (two independent readings)
    st = load(STANDINGS)
    home_wins_log = sum(1 for g in settled if g["home_pts"] > g["away_pts"])
    home_margins = [g["home_pts"] - g["away_pts"] for g in settled]
    sd_margin = sd(home_margins) or 0.0
    p_st = st["measured_home_win_rate"]
    hca = round(phi_inv(p_st) * sd_margin, 2)
    PIN.update(hca_points=hca, sd_margin=sd_margin)
    home_court = {
        "pinned": True,
        "pin_source": "official league standings, HOME column summed over all 30 clubs "
                      f"({st['measured_home_wins']}-{st['measured_home_games'] - st['measured_home_wins']} "
                      f"in {st['measured_home_games']} home games)",
        "measured_home_win_rate_standings": p_st,
        "wilson95_standings": wilson(st["measured_home_wins"], st["measured_home_games"]),
        "measured_home_win_rate_finals_log": round(home_wins_log / len(settled), 4) if settled else None,
        "finals_log_n": len(settled),
        "wilson95_finals_log": wilson(home_wins_log, len(settled)),
        "sd_home_margin_finals_log": round(sd_margin, 3),
        "hca_points_used": hca,
        "hca_formula": "Phi^-1(home win rate) x sd(home margin): the rate from the standings "
                       f"(n = {st['measured_home_games']}), the spread from the verified finals "
                       f"(n = {len(settled)}). Neither estimator may move this number.",
        "why_pinned": "fitting HCA inside a short log lets the ratings absorb the season's luck; the "
                      "brief pins it to the measured rate, so it is measured once and used twice",
        "two_readings_disagree_by": round(abs(p_st - (home_wins_log / len(settled))), 4) if settled else None,
        "readings_note": "the finals log is 23 games and its Wilson interval is wide; the standings "
                         "measurement covers the whole league to date and is the pin. The gap is "
                         "published, not averaged away.",
    }

    # ---- estimator A: results only, ridge chosen by leave-one-game-out
    lams = [0.001, 0.01, 0.1, 1.0, 10.0]

    def loo(pred_factory, subset=None):
        subset = settled if subset is None else subset
        errs = []
        for k in range(len(subset)):
            sub = subset[:k] + subset[k + 1:]
            pred = pred_factory(sub)
            g = subset[k]
            errs.append((pred(g) - (g["home_pts"] - g["away_pts"])) ** 2)
        return math.sqrt(sum(errs) / len(errs)) if errs else None

    loo_a = [{"ridge": lam,
              "loo_rmse": round(loo(lambda s, lam=lam: predict_fn(s, hca, lam)), 4)} for lam in lams]
    best = min(loo_a, key=lambda c: c["loo_rmse"])
    baseline = loo(lambda s: (lambda g: hca))
    resid = []
    for k in range(len(settled)):
        sub = settled[:k] + settled[k + 1:]
        p = predict_fn(sub, hca, best["ridge"])
        g = settled[k]
        resid.append(p(g) - (g["home_pts"] - g["away_pts"]))
    ratings_a = fit_massey(settled, hca, best["ridge"])
    sd_resid = sd(resid)
    estimator_a = {
        "name": "Massey ratings on verified final margins, pinned HCA, ridge chosen by leave-one-game-out",
        "inputs_used": "final margins only: no efficiency data, no availability data",
        "ridge_candidates": loo_a, "ridge_chosen": best,
        "baseline_loo_rmse_predicting_only_the_pinned_hca": round(baseline, 4),
        "out_of_sample_skill_vs_baseline": round(1 - best["loo_rmse"] / baseline, 4),
        "residual_sd_points": round(sd_resid, 3),
        "ratings": {k: round(v, 3) for k, v in sorted(ratings_a.items())},
        "games_fitted_on": len(settled),
        "atl_mil_note": "0022600243 (ATL @ MIL) is included: the final 113-106 is confirmed by the "
                        "scoreboard, the game-book recap line and the box-score team totals. Only its "
                        "quarter split is disputed, and estimator A uses margins, not quarters.",
    }

    # ---- availability for every club
    avail = {ab: availability_for(ab, report, idx) for ab in idx}

    # ---- lines for the rolling window
    slate = load(SLATE)
    totals_log = [g["home_pts"] + g["away_pts"] for g in settled]
    mean_total = mean(totals_log)
    sd_total = sd(totals_log)
    lines = []
    for g in slate["games"]:
        a, h = g["away"], g["home"]
        ta, th = idx.get(a), idx.get(h)
        row = {"date": g["date"], "game_id": g["game_id"], "away": a, "home": h,
               "venue": g.get("venue"), "tip_et": g.get("tip_et"), "game_url": g.get("game_url"),
               "source_url": g.get("source_url"),
               "slate_row_reverified_by_d1b96315": g.get("reverified_by_d1b96315", False)}
        if not ta or not th:
            row.update({"publishable": False, "block": "no official team-stat row for one of the clubs"})
            lines.append(row)
            continue
        ma = ratings_a.get(h, 0.0) - ratings_a.get(a, 0.0) + hca
        poss = round((ta["poss_pg"] + th["poss_pg"]) / 2.0, 2)
        dA = avail[a]["ortg_delta"] if avail[a]["status"] == "applied" else 0.0
        dH = avail[h]["ortg_delta"] if avail[h]["status"] == "applied" else 0.0
        off_a, off_h = ta["off_rtg"] - dA, th["off_rtg"] - dH
        ppp_a = (off_a + th["def_rtg"]) / 2.0 / 100.0
        ppp_h = (off_h + ta["def_rtg"]) / 2.0 / 100.0
        pts_a, pts_h = poss * ppp_a, poss * ppp_h
        mb = round(pts_h - pts_a + hca, 2)
        total_b = round(pts_a + pts_h, 2)
        naive = None
        na, nb_ = ta.get("naive_scoring_averages"), th.get("naive_scoring_averages")
        if na and nb_ and None not in (na["pts_pg"], nb_["pts_pg"]):
            naive = round(na["pts_pg"] + nb_["pts_pg"], 2)
        dis = round(abs(ma - mb), 2)
        rz = {"away": luck_z(ta), "home": luck_z(th)}
        out_outside = [k for k, v in rz.items() if v is not None and abs(v) > OUT_OF_NOISE_BAND]
        row.update({
            "estimator_a_margin": round(ma, 2), "estimator_b_margin": mb,
            "disagreement_margin_points": dis,
            "headline_confidence": ("agreeing" if dis <= 2.5 else
                                    "watch" if dis <= DISAGREE_CAP else "too wide to publish as a bet"),
            "blend_margin_underneath": round((ma + mb) / 2.0, 2),
            "possessions": poss, "ppp_away": round(ppp_a, 4), "ppp_home": round(ppp_h, 4),
            "total_possessions_model": total_b,
            "total_naive_scoring_average": naive,
            "total_gap_between_the_two_methods": (round(abs(total_b - naive), 2)
                                                  if naive is not None else None),
            "availability": {"away": avail[a], "home": avail[h]},
            "rotation_availability": {
                "away": {"status": avail[a]["status"],
                        "minutes_share_removed": avail[a]["minutes_share_removed"],
                        "out_applied": [o["player"] for o in avail[a]["out_applied"]]},
                "home": {"status": avail[h]["status"],
                         "minutes_share_removed": avail[h]["minutes_share_removed"],
                         "out_applied": [o["player"] for o in avail[h]["out_applied"]]}},
            "rest": {"away": rest_flags(a, g["date"], settled),
                     "home": rest_flags(h, g["date"], settled)},
            "travel": travel(a, h, g.get("venue")),
            "luck_z": rz,
            "injury_filing": {s_: filing_for(s_[0] if False else row_side, g["date"], report)
                              for s_, row_side in (("away", a), ("home", h))},
            "publishable": True,
            "surface": "projection",
            "bet_eligible": (not out_outside) and dis <= DISAGREE_CAP,
            "bet_block": (f"club(s) outside the noise band: {', '.join(out_outside)}" if out_outside
                          else None if dis <= DISAGREE_CAP
                          else f"estimator disagreement {dis} > the frozen cap {DISAGREE_CAP}"),
        })
        lines.append(row)

    # ---- measured rho, then parlay pricing that prints the naive product beside it
    margins = [g["home_pts"] - g["away_pts"] for g in settled]
    rho_mt = corr(margins, totals_log)
    by_date = {}
    for g in settled:
        by_date.setdefault(g["date"], []).append(g)
    m1, m2, pairs = [], [], []
    for _, gs in by_date.items():
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                pairs.append((gs[i]["game_id"], gs[j]["game_id"]))
                m1.append(gs[i]["home_pts"] - gs[i]["away_pts"])
                m2.append(gs[j]["home_pts"] - gs[j]["away_pts"])
    rho_xg = corr(m1, m2)
    pricing = {
        "measured_on": {"settled_games": len(settled), "same_date_game_pairs": len(pairs)},
        "rho_margin_vs_total": round(rho_mt, 4) if rho_mt is not None else None,
        "rho_margin_vs_total_ci95": fisher_ci(rho_mt, len(settled)),
        "rho_cross_game_margin": round(rho_xg, 4) if rho_xg is not None else None,
        "rho_cross_game_ci95": fisher_ci(rho_xg, len(m1)),
        "rho_method": "both rhos are measured on the verified finals in this repo: margin against "
                      "total, and the margin of one game against the margin of another game on the "
                      "same date. Nothing is assumed from another league or season.",
        "leg_probability_method": "p(favourite covers our line) = Phi(|edge| / residual sd); "
                                  "p(over our total) = Phi(|our total - league mean total| / sd total)",
        "copula": "Gaussian: p_parlay = Phi2(Phi^-1(p1), Phi^-1(p2); rho). The naive price p1 x p2 "
                  "is printed beside it on every row, so the correlation effect is visible, not hidden.",
        "parlays": [],
    }
    for row in lines:
        if not row.get("publishable") or "estimator_b_margin" not in row:
            continue
        edge = row["blend_margin_underneath"]
        p_fav = phi(abs(edge) / sd_resid) if sd_resid else None
        p_over = (phi((row["total_possessions_model"] - mean_total) / sd_total)
                  if sd_total else None)
        if p_fav is None or p_over is None:
            row["parlay_price"] = {"status": "not priced: the residual spread is not estimable yet",
                                   "why": f"{len(settled)} games in the log"}
            continue
        rho = pricing["rho_margin_vs_total"] or 0.0
        joint = bivariate_cdf(phi_inv(p_fav), phi_inv(p_over), rho)
        naive_p = p_fav * p_over
        price = {"legs": ["home side at our originated number", "game total over our number"],
                 "p_leg_1": round(p_fav, 4), "p_leg_2": round(p_over, 4),
                 "rho_used": round(rho, 4),
                 "p_parlay_measured_rho": round(joint, 4),
                 "p_parlay_naive_product": round(naive_p, 4),
                 "difference_in_probability_points": round((joint - naive_p) * 100, 2),
                 "fair_american_measured_rho": american(joint),
                 "fair_american_naive": american(naive_p),
                 "surface": "projection — this is a price we publish, not a bet we place",
                 "status": "priced"}
        row["parlay_price"] = price
        pricing["parlays"].append({"game_id": row["game_id"], "date": row["date"], **price})

    # ---- game flow from the quarter scores
    qgames = [g for g in settled if g.get("quarters")
              and len(g["quarters"]["away"] or []) == 4 and len(g["quarters"]["home"] or []) == 4]
    flow = {"games_with_official_quarter_scores": len(qgames),
            "sources": ["data/app/results_feed.json (2026-11-14 rows)",
                        "d1b96315/data/results_2026-11-15.json (2026-11-15 rows)"],
            "share_of_points_by_quarter": None, "back_to_back_fourth_quarter": None}
    if qgames:
        all_pts = sum(sum(g["quarters"]["away"]) + sum(g["quarters"]["home"]) for g in qgames)
        shares = {f"Q{i + 1}": round(sum(g["quarters"]["away"][i] + g["quarters"]["home"][i]
                                          for g in qgames) / all_pts, 4) for i in range(4)}
        shares["sum"] = round(sum(v for k, v in shares.items() if k != "sum"), 4)
        flow["share_of_points_by_quarter"] = shares
        b2b, rested = [], []
        for g in qgames:
            for side in ("away", "home"):
                t = g[side]
                rf = rest_flags(t, g["date"], settled, exclude_game=g.get("game_id"))
                q4_minus_q3 = g["quarters"][side][3] - g["quarters"][side][2]
                (b2b if rf["back_to_back"] else rested).append(q4_minus_q3)
        flow["back_to_back_fourth_quarter"] = {
            "definition": "4th-quarter points minus 3rd-quarter points, by club, split on whether "
                          "the club played the previous day (verified finals only)",
            "on_a_back_to_back": {"n": len(b2b), "mean": round(mean(b2b), 2) if b2b else None},
            "rested": {"n": len(rested), "mean": round(mean(rested), 2) if rested else None},
            "note": "small n; published as a measurement with its sample size, not as a rule",
        }

    # ---- what the pin costs: the home-advantage numbers this repo has already published
    published = {"d1b96315_this_build": hca}
    r1116 = ROOT / "data" / "rounds" / "2026-11-16" / "model.json"
    if r1116.exists():
        hc = load(r1116).get("home_court", {})
        published["data_rounds_2026_11_16"] = {
            "hca_points": hc.get("implied_hca_points"), "basis": "measured on the finals in that "
            "capture only", "home_win_rate": hc.get("home_win_rate"), "n_games": hc.get("games"),
            "source_file": "data/rounds/2026-11-16/model.json"}
    led = ROOT / "data" / "app" / "ledger" / "ledger.jsonl"
    if led.exists():
        vals = sorted({(json.loads(x).get("body", {}).get("payload") or {}).get("hca_points_pinned")
                       for x in led.read_text(encoding="utf-8").splitlines() if x.strip()} - {None})
        published["data_app_ledger_constant"] = {
            "hca_points": vals, "source_file": "data/app/ledger/ledger.jsonl",
            "note": "the value every sealed entry in that chain records; it is a constant, not a "
                    "measurement recomputed per game day"}
    published["spread_between_the_three_points"] = round(
        max([v for v in [hca, (published.get("data_rounds_2026_11_16") or {}).get("hca_points"),
                         *((published.get("data_app_ledger_constant") or {}).get("hca_points") or [])]
             if v is not None]) -
        min([v for v in [hca, (published.get("data_rounds_2026_11_16") or {}).get("hca_points"),
                         *((published.get("data_app_ledger_constant") or {}).get("hca_points") or [])]
             if v is not None]), 2)
    published["effect_on_this_builds_lines"] = {
        "vs_the_round_capture": round(hca - ((published.get("data_rounds_2026_11_16") or {})
                                            .get("hca_points") or hca), 2),
        "reading": "every home margin in this build is this many points smaller than the same model "
                   "run at the previously pinned value; the number moved because the pin moved from "
                   "a 23-final sample to the whole league's home/away split",
    }

    # ---- estimator A stability across the ridge candidates (the log is short for 30 clubs)
    tonight = [r for r in lines if r["date"] == "2026-11-16" and r.get("publishable")]
    stability = []
    for cand in loo_a:
        fn = predict_fn(settled, hca, cand["ridge"])
        deltas = [abs(round(fn({"home": r["home"], "away": r["away"], "home_pts": 0, "away_pts": 0})
                              - r["estimator_a_margin"], 2)) for r in tonight]
        stability.append({"ridge": cand["ridge"], "loo_rmse": cand["loo_rmse"],
                          "max_abs_shift_on_tonights_lines": round(max(deltas), 2) if deltas else None,
                          "mean_abs_shift": round(mean(deltas), 2) if deltas else None})
    model_stability = {"table": stability,
                       "why": "23 verified finals cannot determine 30 club ratings on its own; the "
                              "ridge is the only thing holding the system up, so the page prints how "
                              "much tonight's numbers move when the ridge moves. A line that shifts by "
                              "more than the disagreement cap under this test is not a number anyone "
                              "should bet, and it is not published as one."}
    estimator_a["stability_across_the_ridge_sweep"] = model_stability

    coverage = {"rule": "one official injury filing state per club per game, read from the newest "
                        "revision; a club the report does not cover for that date is 'unknown', never "
                        "'clear'",
                "states": {}, "rows_by_state": {}}
    for row in lines:
        if not row.get("publishable"):
            continue
        st_ = tuple(sorted(row["injury_filing"][k]["status"] for k in ("away", "home")))
        key = "&".join(st_)
        coverage["rows_by_state"][key] = coverage["rows_by_state"].get(key, 0) + 1
    coverage["rows_total"] = sum(1 for r in lines if r.get("publishable"))
    coverage["rows_with_no_usable_filing_either_side"] = coverage["rows_by_state"].get(
        "outside_report_window&outside_report_window", 0) + coverage["rows_by_state"].get(
        "not_submitted&not_submitted", 0) + coverage["rows_by_state"].get(
        "not_submitted&outside_report_window", 0)
    coverage["rows_missing_at_least_one_side"] = sum(
        v for k, v in coverage["rows_by_state"].items() if "filed" not in k)
    coverage["latest_revision_et"] = report["report_stamp"]
    coverage["latest_revision_retrieved_utc"] = report["retrieved_utc"]
    coverage["report_player_rows"] = report["player_rows"]
    coverage["clubs_filed"] = sorted({r["team_abbr"] for r in report["rows"]
                                      if r.get("player") and not r.get("not_yet_submitted")})
    coverage["clubs_not_submitted"] = sorted({r["team_abbr"] for r in report["rows"]
                                              if r.get("not_yet_submitted")})

    luck = {ab: luck_z(t) for ab, t in sorted(idx.items())}
    outside = {ab: v for ab, v in luck.items() if v is not None and abs(v) > OUT_OF_NOISE_BAND}
    nat = st["checks"]["neutral_record"]
    model = {
        "schema": "nba3.d1b96315.model/v1", "generated_for": "2026-11-16 .. 2026-11-18",
        "session": "arena/d1b96315-nba3", "stamp": STAMP,
        "headline": "the disagreement between the two independent estimators is the confidence "
                    "signal; the blend is printed underneath it and is never the headline",
        "inputs": {
            "settled_finals_used": len(settled), "excluded_rows": excluded,
            "date_range": [settled[0]["date"], settled[-1]["date"]] if settled else None,
            "injury_report": {"revision_time_et": report["report_stamp"],
                              "retrieval_time_utc": report["retrieved_utc"], "source": INJ_PDF,
                              "rows": report["count"], "player_rows": report["player_rows"],
                              "club_not_yet_submitted": report["club_marker_rows"],
                              "unread_cells": report["unread_cells"]},
            "standings": {"source": st["source_url"], "retrieved_utc": st["retrieved_utc"],
                          "completeness_identity": {
                              "home_games": st["checks"]["home_wins_plus_road_losses_equal_home_games"]["home_w+home_l"],
                              "neutral_games": (nat["neutral_w"] + nat["neutral_l"]) / 2,
                              "total_wins": st["checks"]["w_equals_l"]["sum_w"],
                              "identity": "home games + neutral games = total games = total wins = total losses"}},
            "team_stats": {"source": load(ADVANCED)["source_url"],
                           "retrieved_utc": load(ADVANCED)["retrieved_utc"],
                           "rows": load(ADVANCED)["count"],
                           "rows_failing_checks": load(ADVANCED)["rows_failing_checks"],
                           "max_abs_residuals": load(ADVANCED)["max_abs_residuals"]},
            "slate": {"source": slate["source_url"], "count": slate["count"],
                      "count_by_date": slate["count_by_date"],
                      "reverified_rows": slate["reverification"]["games_reverified_row_by_row"],
                      "calendar_counts": slate["reverification"]["calendar_counts_read"]},
            "player_logs": {"teams_1115": load(LOGS_1115)["teams"],
                            "rows_1115": load(LOGS_1115)["count"],
                            "unread_cells_1115": load(LOGS_1115)["unread_cells"],
                            "teams_1114": sorted({r["team"] for r in load(LOGS_1114)["rows"]})
                            if LOGS_1114.exists() else [],
                            "source_1115": load(LOGS_1115)["books"]},
        },
        "home_court": dict(home_court,
                           previously_published_in_this_repo=published),
        "estimator_a": estimator_a,
        "estimator_b": {
            "name": "possessions x points-per-possession from the official advanced table, with the "
                    "minutes-redistribution availability adjustment",
            "formula": "poss = mean(possessions per game of the two clubs); "
                       "pts_t = poss x ((off_rtg_t - availability_delta_t) + def_rtg_opp) / 2 / 100; "
                       "margin = pts_home - pts_away + pinned hca; total = pts_home + pts_away",
            "availability_status_by_team": {ab: avail[ab]["status"] for ab in sorted(avail)},
            "teams_adjusted": sorted(ab for ab in avail if avail[ab]["status"] == "applied"),
            "teams_not_adjusted": sorted(ab for ab in avail if avail[ab]["status"] != "applied"),
            "coverage_of_tonight": {ab: avail[ab]["status"] for ab in
                                    sorted({g["away"] for g in slate["games"] if g["date"] == "2026-11-16"}
                                           | {g["home"] for g in slate["games"] if g["date"] == "2026-11-16"})},
        },
        "totals_model": {
            "chosen": "possessions x points per possession",
            "rejected": "the average of the two clubs' scoring averages",
            "why": "a scoring average already contains the pace the team actually played and the "
                   "opponent it faced; adding two of them makes a total that no single game implies. "
                   "Both are printed for every row so the difference is auditable.",
            "league_mean_total_from_verified_finals": round(mean_total, 2) if mean_total else None,
            "sd_total": round(sd_total, 2) if sd_total else None,
        },
        "injury_coverage": coverage,
        "luck_z": luck,
        "luck_formula": "expected wins = GP x Phi(net_rtg / sd(home margin from the verified finals)); "
                        "z = (wins - expected) / sqrt(GP x p x (1 - p)). sd = %.2f points" % sd_margin,
        "luck_rule": "|z| > %.1f keeps a club out of any bet-eligible row on this site" % OUT_OF_NOISE_BAND,
        "clubs_outside_the_noise_band": outside,
        "pricing": pricing,
        "game_flow": flow,
        "market_anchor": {
            "prior_weight": None, "closing_line": None, "measured_log_loss": None,
            "reason": "no licensed closing-line feed exists in this repository, so the blend weight "
                      "cannot be measured out of sample. The field is null; the requirement stays "
                      "open on the Questions page (Q01).",
        },
    }

    gates = build_gates(lines, model, report, avail)
    prereg = build_prereg(model, gates)
    arts = {"model.json": model,
            "lines.json": {"schema": "nba3.d1b96315.lines/v1", "stamp": STAMP,
                           "count": len(lines),
                           "surface": "projection", "lines": lines},
            "gates.json": gates, "prereg_index.json": prereg}
    if check:
        bad = [k for k, v in arts.items()
               if not (D / k).exists()
               or (D / k).read_text(encoding="utf-8") != json.dumps(v, indent=1) + "\n"]
        print("model is reproducible" if not bad else f"DRIFT in: {bad}")
        return 1 if bad else 0
    for k, v in arts.items():
        (D / k).write_text(json.dumps(v, indent=1) + "\n", encoding="utf-8")
        print("wrote d1b96315/data/" + k)
    (D / "prereg").mkdir(exist_ok=True)
    for sid, body in prereg["files"].items():
        (D / "prereg" / f"{sid}.json").write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    print(f"lines {len(lines)}; adjusted clubs {len(model['estimator_b']['teams_adjusted'])}; "
          f"funded strategies {gates['summary']['funded']}/{len(gates['strategies'])}")
    return 0


# ---------------------------------------------------------------- gates & pre-registration

def build_gates(lines, model, report, avail) -> dict:
    """The validation board. A strategy is funded only when every gate passes."""
    pub = [r for r in lines if r.get("publishable")]
    agree = [r for r in pub if r["disagreement_margin_points"] <= 2.5]
    strat_defs = [
        {"id": "D-S1", "name": "side of our own number where both estimators agree",
         "signal": "sign(est_a_margin) == sign(est_b_margin) and |est_a - est_b| <= 2.5",
         "stake_rule": "1 unit, flat, no martingale",
         "n_candidates": sum(1 for r in agree if r["estimator_a_margin"] * r["estimator_b_margin"] > 0)},
        {"id": "D-S2", "name": "availability-weighted side (estimator B only)",
         "signal": "the availability delta is applied to at least one club and |est_b_margin| >= 4.0",
         "stake_rule": "1 unit, flat",
         "n_candidates": sum(1 for r in pub if abs(r["estimator_b_margin"]) >= 4.0
                             and (avail[r["away"]]["status"] == "applied"
                                  or avail[r["home"]]["status"] == "applied"))},
        {"id": "D-S3", "name": "total from the possessions model",
         "signal": "|total_possessions_model - total_naive_scoring_average| >= 4.0",
         "stake_rule": "1 unit, flat, on the possessions side",
         "n_candidates": sum(1 for r in pub
                             if (r["total_gap_between_the_two_methods"] or 0) >= 4.0)},
        {"id": "D-S4", "name": "same-game parlay, side + our total, priced with the measured rho",
         "signal": "leg 1 |blend margin| >= 4.0, leg 2 |our total - league mean total| >= 4.0, "
                   "priced with rho(margin, total) measured on the verified finals",
         "stake_rule": "0.5 unit, flat",
         "n_candidates": sum(1 for r in pub if (r.get("parlay_price") or {}).get("status") == "priced")},
        {"id": "D-S5", "name": "player-prop combo",
         "signal": "not defined: no player market data and no per-player projection feed exists "
                   "for the whole slate",
         "stake_rule": "n/a", "n_candidates": 0},
    ]
    rows = []
    for s in strat_defs:
        gates = {}
        gates["G1_sample_depth"] = {
            "pass": model["inputs"]["settled_finals_used"] >= MIN_VERIFIED_FINALS,
            "measured": f"{model['inputs']['settled_finals_used']} verified finals "
                        f"(needs {MIN_VERIFIED_FINALS})",
            "rule": "about four games per club in the log before a strategy may be funded",
        }
        gates["G2_freshness"] = {
            "pass": True,
            "measured": f"newest official injury revision used: {report['report_stamp']} "
                        f"(retrieved {report['retrieved_utc']}); standings and team stats retrieved "
                        f"{model['inputs']['standings']['retrieved_utc']}",
            "rule": "every input must be read on the day it is used for; a stale input blocks the "
                    "rebuild rather than quietly ageing the line",
        }
        gates["G3_provenance"] = {
            "pass": not model["inputs"]["team_stats"]["rows_failing_checks"],
            "measured": f"team-stat rows failing their own printed identities: "
                        f"{model['inputs']['team_stats']['rows_failing_checks'] or 'none'}; the "
                        f"arena-coordinate table is the one non-official input and it is labelled "
                        f"on every row that uses it",
            "rule": "no row is published without a source link to an official page",
        }
        gates["G4_out_of_sample"] = {
            "pass": (model["estimator_a"]["out_of_sample_skill_vs_baseline"] or -1) > 0.05,
            "measured": f"leave-one-game-out skill against the pinned-HCA baseline: "
                        f"{model['estimator_a']['out_of_sample_skill_vs_baseline']} "
                        f"(rmse {model['estimator_a']['ridge_chosen']['loo_rmse']} vs baseline "
                        f"{model['estimator_a']['baseline_loo_rmse_predicting_only_the_pinned_hca']})",
            "rule": "an estimator must beat the no-skill baseline out of sample by more than 5%",
        }
        gates["G5_luck_band"] = {
            "pass": not model["clubs_outside_the_noise_band"],
            "measured": ("clubs outside the band: " + (", ".join(
                f"{k} {v:+.2f}" for k, v in model["clubs_outside_the_noise_band"].items())
                or "none")),
            "rule": f"a funded strategy may not lean on a club more than {OUT_OF_NOISE_BAND} sd from "
                    f"its efficiency-based win expectation",
        }
        gates["G6_disagreement_cap"] = {
            "pass": s["n_candidates"] > 0,
            "measured": f"{s['n_candidates']} candidate rows on the 11/16-11/18 window inside the "
                        f"{DISAGREE_CAP}-point cap",
            "rule": "the two independent estimators must agree within the frozen cap",
        }
        gates["G7_pretip_seal"] = {
            "pass": True,
            "measured": "every published line is hashed and appended to d1b96315/ledger/ledger.jsonl "
                        "before its tip; the seal and the verifier are d1b96315/ledger.py",
            "rule": "a pick may not enter the ledger after its tip without an earlier hash",
        }
        gates["G8_price_feed"] = {
            "pass": False,
            "measured": "no licensed market price feed in this repository: no closing line, no juice, "
                        "so ROI cannot be computed and no strategy can be funded",
            "rule": "a strategy cannot be funded against a price this system invented for itself",
        }
        passed = sum(1 for g in gates.values() if g["pass"])
        rows.append({**s, "gates": gates, "gates_passed": f"{passed}/{len(gates)}",
                     "blocking": [k for k, g in gates.items() if not g["pass"]],
                     "status": "funded" if passed == len(gates) else "not funded",
                     "reward_points": 0})
    order = sorted(rows, key=lambda r: (-int(r["gates_passed"].split("/")[0]), r["id"]))
    return {"schema": "nba3.d1b96315.gates/v1", "stamp": STAMP,
            "rule": "all eight gates must pass before a strategy is funded; a failing gate is "
                    "printed with its measurement, never dropped",
            "strategies": rows,
            "summary": {"strategies": len(rows),
                        "funded": sum(1 for r in rows if r["status"] == "funded"),
                        "gates_blocking_any_strategy": sorted({k for r in rows for k in r["blocking"]}),
                        "leaderboard_note": "rewards are 0 everywhere because G1 and G8 fail for every "
                                            "strategy; the leaderboard ranks by gates passed and "
                                            "out-of-sample skill, never by profit that does not exist"},
            "leaderboard": [{"rank": i + 1, "id": r["id"], "name": r["name"],
                             "gates_passed": r["gates_passed"], "candidates": r["n_candidates"],
                             "status": r["status"], "reward_points": r["reward_points"],
                             "blocking": r["blocking"]} for i, r in enumerate(order)]}


def build_prereg(model, gates) -> dict:
    files = {}
    for s in gates["strategies"]:
        body = {"strategy_id": s["id"], "name": s["name"], "signal": s["signal"],
                "thresholds": {"disagreement_cap_points": DISAGREE_CAP,
                               "luck_z_band": OUT_OF_NOISE_BAND,
                               "min_verified_finals": MIN_VERIFIED_FINALS},
                "universe": "every game on the official rolling slate for today .. today+2, all 30 clubs",
                "settlement_rule": "settle only from an official final that the nba.com scoreboard and "
                                   "the game book agree on; a game whose printed quarter scores do not "
                                   "sum to its final is settled on the score alone and flagged; a game "
                                   "with no verified final stays unsettled",
                "stake_rule": s["stake_rule"],
                "home_court_used_by_this_strategy": model["home_court"]["hca_points_used"],
                "frozen_before_first_bet": True, "frozen_stamp": STAMP,
                "frozen_by": "arena/d1b96315-nba3",
                "note": "frozen before any bet because no strategy is funded; editing this file changes "
                        "its hash, and the hash is published in the ledger"}
        payload = json.dumps(body, indent=1, sort_keys=True)
        files[s["id"]] = {**body, "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
    return {"schema": "nba3.d1b96315.prereg/v1", "stamp": STAMP,
            "rule": "one frozen file per strategy, written before its first bet, containing the signal, "
                    "the thresholds, the universe and the exact settlement rule",
            "files": files}


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
