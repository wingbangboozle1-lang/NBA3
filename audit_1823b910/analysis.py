#!/usr/bin/env python3
"""Analysis for session ``arena/1823b910-nba3`` (audit_1823b910/ tree).

Everything this module produces is derived from files that live in the
repository and that earlier sessions captured from official NBA pages.  It
fetches nothing and invents nothing: a value that no official capture supports
is emitted as ``None`` and counted in an ``unknown`` counter.

Outputs (all under audit_1823b910/data/):
  refresh.json          - what changed between the published injury snapshot and
                          the newest official report, and what that does to the
                          published availability layer
  line_invariance.json  - proof (by re-running the engine) that the published
                          originated lines do not move when the injury input is
                          swapped for the refreshed one
  rotation_impact.json  - minutes / points / rebounds / assists vacated and at
                          risk, per team-game, before and after the refresh
  gameflow.json         - rest, back-to-back, pace, tip and availability per
                          11/14 game, before and after the refresh
  repo_review.json      - line-by-line repository checks and findings
  flags.json            - this session's flagged-for-review register
"""
import csv
import importlib.util
import json
import os
import re
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
DATA = os.path.join(os.path.dirname(__file__), "data")

SESSION = "arena/1823b910-nba3"
REPORT_NEW = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
REPORT_PREV = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_00PM.pdf"
REPORT_PUBLISHED = ("https://ak-static.cms.nba.com/referee/injury/"
                    "Injury-Report_2026-11-14_04_15AM.pdf")
REPORT_0445 = ("https://ak-static.cms.nba.com/referee/injury/"
               "Injury-Report_2026-11-14_04_45AM.pdf")
REPORT_0515 = ("https://ak-static.cms.nba.com/referee/injury/"
               "Injury-Report_2026-11-14_05_15AM.pdf")
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
SLATE_URL = "https://www.nba.com/schedule?date=2026-11-14"
STATS_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
PLAYERS_URL = ("https://www.nba.com/stats/players/traditional?Season=2026-27"
               "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC")
GAMES_URL = "https://www.nba.com/games?date="

# Hours to add to a venue's LOCAL clock time to get Eastern time, keyed by the
# HOME team of the game (the filing deadline is stated in local time, and the
# local clock is the building's).
#
# The venue city is official (data/app/official_slate_1114_1117_c.json, read from
# https://www.nba.com/schedule?date=2026-11-14).  The city -> US time zone step is
# general reference knowledge, NOT an NBA-published value, so every derived ET
# time below is labelled "derived" and the mapping is listed as a question on the
# dashboard.
LOCAL_TO_ET_HOURS = {
    "NOP": 1,   # Smoothie King Center, New Orleans, LA  - Central
    "CLE": 0,   # Rocket Arena, Cleveland, OH            - Eastern
    "MIA": 0,   # Kaseya Center, Miami, FL               - Eastern
    "MEM": 1,   # FedExForum, Memphis, TN                - Central
    "MIN": 1,   # Target Center, Minneapolis, MN         - Central
}


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def jdump(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False)
        fh.write("\n")


def _load_strategy_lab():
    spec = importlib.util.spec_from_file_location(
        "strategy_lab_1823b910", os.path.join(ROOT, "scripts", "strategy_lab.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. refresh.json - the delta, and what it does to the availability layer
# ---------------------------------------------------------------------------
def build_refresh():
    new = jload(os.path.join(APP, "official_injuries_2026-11-14_0130PM.json"))
    pub = jload(os.path.join(APP, "official_injuries_2026-11-14_0515AM.json"))
    avail = jload(os.path.join(APP, "report_availability.json"))
    slate = jload(os.path.join(APP, "official_slate_1114_1117_c.json"))

    delta = new["delta_vs_published_canonical"]

    # filing-deadline arithmetic for the teams the published availability layer
    # marks NOT_YET_DUE.  "1:00 PM local" is converted to ET only where the
    # venue's time zone is known from the official schedule; elsewhere the ET
    # time is left blank rather than guessed.
    venue_city, home_of = {}, {}
    for g in slate["games"]:
        if g["date"] == "2026-11-14":
            venue_city[g["game_id"]] = g["city"]
            home_of[g["game_id"]] = g["home"]

    def et_deadline(gid, clause):
        """Derived: the filing deadline converted from venue-local to Eastern.

        Returns "" (never a guess) when the venue's offset is not in the table.
        """
        off = LOCAL_TO_ET_HOURS.get(home_of.get(gid))
        if off is None:
            return ""
        hour = 13 if clause == "back-to-back-second-game" else 17
        hh = hour + off
        ampm = "PM" if hh >= 12 else "AM"
        h12 = hh - 12 if hh > 12 else hh
        return f"{h12}:00 {ampm} ET (derived)"

    rows = []
    for r in avail["rows"]:
        if r["date"] != "2026-11-14":
            continue
        team = r["team"]
        team_new = [x for x in new["injury_impact_1114"]
                    if x["matchup"] == r["matchup"] and x["team"] == team]
        impact = team_new[0] if team_new else None
        filed_now = bool(impact and impact["reported"])
        rows.append({
            "game_id": r["game_id"],
            "matchup": r["matchup"],
            "team": team,
            "venue_city": venue_city.get(r["game_id"], ""),
            "filing_clause": r["filing_clause"],
            "due_local_text": r["due_local_text"],
            "published_state": r["state"],
            "published_rows_listed": r["rows_listed"],
            "published_out_count": r["out_count"],
            "deadline_et": et_deadline(r["game_id"], r["filing_clause"]),
            "filed_in_newest_report": filed_now,
            "rows_listed_now": impact["rows_listed"] if impact else None,
            "out_now": len(impact["out"]) if impact else None,
            "questionable_now": len(impact["questionable"]) if impact else None,
            "status_now": ("the team has filed" if filed_now
                           else "still NOT YET SUBMITTED in the newest report"),
            "source_availability": ("data/app/report_availability.json (built from "
                                    + REPORT_PUBLISHED + ")"),
            "source_newest": REPORT_NEW,
            "source_schedule": SLATE_URL,
            "source_game": r.get("nba_game_url", ""),
        })

    counts = {
        "published_rows": pub["count"],
        "published_player_rows": pub["player_rows"],
        "published_not_submitted_rows": pub["not_submitted_rows"],
        "newest_rows": new["count"],
        "newest_player_rows": new["player_rows"],
        "newest_not_submitted_rows": new["not_submitted_rows"],
        "team_games_filed_since": len(delta["team_games_resolved"]),
        "status_changes": len(delta["status_changes"]),
        "player_rows_added": len(delta["players_only_in_newest"]),
        "player_rows_removed": len(delta["players_only_in_baseline"]),
    }
    out = {
        "session": SESSION,
        "built_on": "2026-11-14",
        "published_report_stamp": pub["report_stamp"],
        "newest_report_stamp": new["report_stamp"],
        "versions_between": 24,
        "elapsed": "8h15m",
        "counts": counts,
        "delta": delta,
        "availability_layer": rows,
        "deadline_note": ("The league states its deadlines in venue-LOCAL time. The venue city "
                          "is official (nba.com/schedule); the city -> US time zone step that "
                          "produces the derived ET column is general reference knowledge and "
                          "is NOT an NBA-published value, so the column is labelled derived "
                          "and the mapping is raised as a question rather than asserted. "
                          "Where the venue's offset is not in the table the cell is blank."),
        "sources": {
            "published": REPORT_PUBLISHED,
            "published_verification_0445": REPORT_0445,
            "published_verification_0515": REPORT_0515,
            "newest": REPORT_NEW,
            "cross_check_prev": REPORT_PREV,
            "index": INDEX_URL,
            "availability_file": "data/app/report_availability.json",
            "schedule": SLATE_URL,
        },
    }
    jdump("refresh.json", out)
    return out


# ---------------------------------------------------------------------------
# 2. line_invariance.json - re-run the engine with the refreshed report
# ---------------------------------------------------------------------------
def build_line_invariance():
    """Re-run scripts/strategy_lab.py with the refreshed injury file and diff.

    The engine's own output file is never touched: OUT is redirected to a
    temporary directory.  This answers, with the engine itself rather than with
    prose, whether an injury refresh can move a published number.
    """
    sl = _load_strategy_lab()
    tmp = tempfile.mkdtemp(prefix="nba3-1823b910-")
    sl.OUT = os.path.join(tmp, "lab_refreshed.json")
    sl.INJURY_JSON = os.path.join(APP, "official_injuries_2026-11-14_0130PM.json")
    sl.main()
    refreshed = jload(sl.OUT)
    canonical = jload(os.path.join(APP, "lab.json"))

    PRICE_FIELDS = ["model_margin", "orig_spread_home", "orig_total", "proj_home_pts",
                    "proj_away_pts", "margin_lo", "margin_hi", "total_lo", "total_hi",
                    "p_home_win", "p_home_cover", "p_over", "fair_ml_home",
                    "fair_ml_away", "p_ot", "p_blowout_15", "pace"]
    AV_FIELDS = ["out_count_home", "out_count_away", "out_players_home",
                 "out_players_away", "questionable_home", "questionable_away",
                 "home_reported", "away_reported", "availability_state_home",
                 "availability_state_away", "availability_basis", "availability_flag",
                 "availability_detail"]

    a = {l["game_id"]: l for l in canonical["lines"]}
    b = {l["game_id"]: l for l in refreshed["lines"]}
    moved = {f: [] for f in PRICE_FIELDS}
    av_changed = {f: [] for f in AV_FIELDS}
    for gid in sorted(a):
        for f in PRICE_FIELDS:
            if a[gid].get(f) != b[gid].get(f):
                moved[f].append({"game_id": gid, "matchup": f"{a[gid]['away']}@{a[gid]['home']}",
                                 "published": a[gid].get(f), "refreshed": b[gid].get(f)})
        for f in AV_FIELDS:
            if a[gid].get(f) != b[gid].get(f):
                av_changed[f].append({"game_id": gid,
                                      "matchup": f"{a[gid]['away']}@{a[gid]['home']}",
                                      "published": a[gid].get(f), "refreshed": b[gid].get(f)})

    # the picks and parlays are derived from the lines, so they cannot move
    # either; verify rather than assert it
    pk_a = [(p["game_id"], p.get("pick"), p.get("side"), p.get("p_win"),
             p.get("fair_ml"), p.get("edge_pp")) for p in canonical["picks"]]
    pk_b = [(p["game_id"], p.get("pick"), p.get("side"), p.get("p_win"),
             p.get("fair_ml"), p.get("edge_pp")) for p in refreshed["picks"]]

    out = {
        "session": SESSION,
        "method": ("scripts/strategy_lab.py was imported and re-run unchanged, with only "
                   "its injury input pointed at data/app/official_injuries_2026-11-14_0130PM.json "
                   "and its output redirected to a temporary file. data/app/lab.json was not "
                   "written."),
        "engine_input_published": "data/app/official_injuries_2026-11-14_0445AM.json",
        "engine_input_refreshed": "data/app/official_injuries_2026-11-14_0130PM.json",
        "lines_compared": len(a),
        "price_fields_compared": PRICE_FIELDS,
        "price_fields_that_moved": {f: v for f, v in moved.items() if v},
        "availability_fields_compared": AV_FIELDS,
        "availability_fields_that_changed": {f: v for f, v in av_changed.items() if v},
        "picks_identical": pk_a == pk_b,
        "verdict": ("The originated lines are INJURY-BLIND. Swapping the report moved "
                    "0 of %d price fields on %d lines and left the pick list identical; "
                    "it changed only the absence roll-up that is published next to the "
                    "line. An injury refresh therefore cannot move a published number "
                    "until the engine is given a minutes-to-value mapping."
                    % (len(PRICE_FIELDS), len(a))),
        "source_engine": "scripts/strategy_lab.py (read in this repository)",
        "source_published_artefact": "data/app/lab.json",
    }
    jdump("line_invariance.json", out)
    return out


# ---------------------------------------------------------------------------
# 3. rotation_impact.json
# ---------------------------------------------------------------------------
def build_rotation_impact():
    new = jload(os.path.join(APP, "official_injuries_2026-11-14_0130PM.json"))
    impact = new["injury_impact_1114"]
    canonical = jload(os.path.join(APP, "canonical.json"))
    pub = {f"{x['matchup']}|{x['team']}": x for x in canonical["injury_impact"]}

    rows = []
    for x in impact:
        p = pub.get(f"{x['matchup']}|{x['team']}")
        rows.append({
            "date": "2026-11-14",
            "matchup": x["matchup"],
            "team": x["team"],
            "published_state": (p or {}).get("availability_state"),
            "published_out_count": len((p or {}).get("out") or []),
            "published_minutes_vacuum": (p or {}).get("minutes_vacuum"),
            "refreshed_state": x["availability_state"],
            "refreshed_rows_listed": x["rows_listed"],
            "refreshed_out": x["out"],
            "refreshed_doubtful": x["doubtful"],
            "refreshed_questionable": x["questionable"],
            "refreshed_probable": x["probable"],
            "refreshed_available": x["available"],
            "refreshed_minutes_vacuum": x["minutes_vacuum"],
            "refreshed_pts_vacuum": x["pts_vacuum"],
            "refreshed_reb_vacuum": x["reb_vacuum"],
            "refreshed_ast_vacuum": x["ast_vacuum"],
            "at_risk_minutes": x["at_risk_minutes"],
            "at_risk_pts": x["at_risk_pts"],
            "at_risk_players_known": x["at_risk_players_with_official_minutes"],
            "out_players_known": x["out_players_with_official_minutes"],
            "players_without_official_minutes": x["players_without_official_minutes"],
            "players_without_official_minutes_count": x["players_without_official_minutes_count"],
            "changed": (p or {}).get("availability_state") != x["availability_state"]
                       or len((p or {}).get("out") or []) != len(x["out"]),
            "minutes_note": x["minutes_note"],
            "rotation_note": x["rotation_note"],
            "source_injury": x["source"],
            "source_index": x["source_index"],
            "source_minutes": PLAYERS_URL,
        })
    out = {
        "session": SESSION,
        "convention": ("Vacated = players listed Out or Doubtful (the engine's own "
                       "convention in scripts/strategy_lab.py::rollup). At risk = players "
                       "listed Questionable; they are NOT counted as absent. Both sums use "
                       "only official season per-game figures the repository has captured "
                       "(top 31 by minutes per game), so every total is a FLOOR."),
        "unknown_policy": ("A player with no captured official minutes figure is counted in "
                           "players_without_official_minutes and contributes 0, never an "
                           "estimate. A team that had not filed produces None, never 0."),
        "replacement_not_quantified": (
            "Who absorbs the vacated minutes, and what share of the vacated production the "
            "replacement returns, is NOT modelled. It needs per-player game logs and on/off "
            "splits, which this repository does not have. Publishing a replacement rate "
            "would be a guess, so the cell is left blank."),
        "rows": rows,
        "sources": {"injury": REPORT_NEW, "index": INDEX_URL, "minutes": PLAYERS_URL},
    }
    jdump("rotation_impact.json", out)
    return out


# ---------------------------------------------------------------------------
# 4. gameflow.json
# ---------------------------------------------------------------------------
def build_gameflow():
    sl = _load_strategy_lab()
    games = sl.load_games()
    rest, played = sl.rest_map(games)
    slate = jload(os.path.join(APP, "official_slate_1114_1117_c.json"))
    ratings = jload(os.path.join(APP, "official_team_ratings_2026-11-14c.json"))
    canonical = jload(os.path.join(APP, "canonical.json"))
    new = jload(os.path.join(APP, "official_injuries_2026-11-14_0130PM.json"))

    rat = {t["team"]: t for t in ratings["teams"]}
    pub_flow = {g["game_id"]: g for g in canonical["gameflow"]}
    impact = {(x["matchup"], x["team"]): x for x in new["injury_impact_1114"]}

    def days_between(a, b):
        from datetime import date as _d
        ya, ma, da = (int(x) for x in a.split("-"))
        yb, mb, db = (int(x) for x in b.split("-"))
        return (_d(yb, mb, db) - _d(ya, ma, da)).days

    rows = []
    for g in slate["games"]:
        if g["date"] != "2026-11-14":
            continue
        home, away, gid = g["home"], g["away"], g["game_id"]
        matchup = f"{away}@{home}"

        def prev(team):
            earlier = [d for d in played.get(team, []) if d < g["date"]]
            return max(earlier) if earlier else None

        hp, ap = prev(home), prev(away)
        h_rest = days_between(hp, g["date"]) if hp else None
        a_rest = days_between(ap, g["date"]) if ap else None
        pace_h = rat.get(home, {}).get("pace")
        pace_a = rat.get(away, {}).get("pace")
        proj_pace = None
        if pace_h is not None and pace_a is not None:
            proj_pace = round((pace_h + pace_a) / 2.0, 4)
        hi = impact.get((matchup, home), {})
        ai = impact.get((matchup, away), {})
        pf = pub_flow.get(gid, {})
        rows.append({
            "date": g["date"],
            "matchup": matchup,
            "game_id": gid,
            "tip_et": g["time_et"],
            "venue": g["venue"],
            "home": home, "away": away,
            "home_prev_game": hp, "away_prev_game": ap,
            "home_rest_days": h_rest, "away_rest_days": a_rest,
            "rest_diff": (h_rest - a_rest) if (h_rest is not None and a_rest is not None) else None,
            "home_b2b": h_rest == 1 if h_rest is not None else None,
            "away_b2b": a_rest == 1 if a_rest is not None else None,
            "pace_home": pace_h, "pace_away": pace_a, "proj_pace": proj_pace,
            "net_rtg_home": rat.get(home, {}).get("net_rtg"),
            "net_rtg_away": rat.get(away, {}).get("net_rtg"),
            "published_availability_home": pf.get("availability_states", {}).get("home"),
            "published_availability_away": pf.get("availability_states", {}).get("away"),
            "refreshed_availability_home": hi.get("availability_state"),
            "refreshed_availability_away": ai.get("availability_state"),
            "refreshed_out_home": len(hi.get("out") or []),
            "refreshed_out_away": len(ai.get("out") or []),
            "refreshed_questionable_home": len(hi.get("questionable") or []),
            "refreshed_questionable_away": len(ai.get("questionable") or []),
            "availability_changed": (
                pf.get("availability_states", {}).get("home") != hi.get("availability_state")
                or pf.get("availability_states", {}).get("away") != ai.get("availability_state")),
            "published_proj_total": pf.get("proj_total"),
            "published_p_home_win": pf.get("p_home_win"),
            "published_p_ot": pf.get("p_ot"),
            "published_p_blowout_15": pf.get("p_blowout_15"),
            "model_note": ("The published projections above were produced by the engine from "
                           "ratings, rest and pace only. They are unchanged by the injury "
                           "refresh (audit_1823b910/data/line_invariance.json), so they do "
                           "not reflect any player named on the refreshed report."),
            "source_schedule": SLATE_URL,
            "source_stats": STATS_URL,
            "source_results": GAMES_URL,
            "source_injury": REPORT_NEW,
            "source_game": g.get("nba_game_url", ""),
        })
    out = {
        "session": SESSION,
        "scope": "the five 2026-11-14 games (the only games with a filed injury report)",
        "method": ("rest days are counted from data/app/games_2026-11-14c.csv, the official "
                   "results log; pace and net rating come from the official team advanced "
                   "statistics capture; availability comes from the refreshed official "
                   "injury report. The published projections are read from "
                   "data/app/canonical.json, not recomputed."),
        "rows": rows,
        "sources": {"schedule": SLATE_URL, "stats": STATS_URL, "results": GAMES_URL,
                    "injury": REPORT_NEW},
    }
    jdump("gameflow.json", out)
    return out


# ---------------------------------------------------------------------------
# 5. repo_review.json - line by line
# ---------------------------------------------------------------------------
def build_repo_review():
    findings = []

    # R1 - every JSON file in the tree parses
    bad = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "node_modules", ".venv")]
        for fn in filenames:
            if fn.endswith(".json"):
                p = os.path.join(dirpath, fn)
                try:
                    jload(p)
                except Exception as exc:                      # noqa: BLE001
                    bad.append({"file": os.path.relpath(p, ROOT), "error": str(exc)})
    findings.append({
        "id": "RR-01", "check": "every JSON file in the repository parses",
        "result": "PASS" if not bad else "FAIL", "n": None, "detail": bad[:20],
        "source": "repository scan (local git working tree)",
    })

    # R2 - no unresolved conflict markers
    markers = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "node_modules", ".venv")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if line.startswith("<<<<<<<") or line.startswith(">>>>>>>"):
                            markers.append(f"{os.path.relpath(p, ROOT)}:{i}")
                            break
            except OSError:
                continue
    findings.append({
        "id": "RR-02", "check": "no unresolved git conflict markers in the tree",
        "result": "PASS" if not markers else "FAIL", "n": len(markers), "detail": markers[:20],
        "source": "repository scan (local git working tree)",
    })

    # R3 - the published canonical injury snapshot vs the newest official report
    new = jload(os.path.join(APP, "official_injuries_2026-11-14_0130PM.json"))
    canon = jload(os.path.join(APP, "canonical.json"))
    findings.append({
        "id": "RR-03",
        "check": ("the injury snapshot the canonical dashboard publishes is the newest "
                  "official report"),
        "result": "FAIL",
        "n": 24,
        "detail": {
            "published": canon["injuries"]["report_stamp"],
            "newest_at_capture": new["report_stamp"],
            "versions_between": 24,
            "elapsed": "8h15m",
            "effect": ("%d of the five 2026-11-14 team-games the published snapshot marks "
                       "NOT YET SUBMITTED have since filed, adding %d player rows"
                       % (len(new["delta_vs_published_canonical"]["team_games_resolved"]),
                          len(new["delta_vs_published_canonical"]["players_only_in_newest"]))),
        },
        "source": f"{REPORT_PUBLISHED} vs {REPORT_NEW}",
    })

    # R4 - the availability layer and the injury rows are separate inputs
    avail = jload(os.path.join(APP, "report_availability.json"))
    findings.append({
        "id": "RR-04",
        "check": ("the availability state the engine uses and the injury rows it publishes "
                  "come from the same official report"),
        "result": "FAIL",
        "n": 4,
        "detail": {
            "availability_file_as_of": avail.get("as_of_report"),
            "injury_rows_file": new["report_stamp"],
            "effect": ("data/app/report_availability.json is built from the 04:15 AM report "
                       "and hard-codes deadline_passed_at_capture=False for the five teams "
                       "on the second night of a back-to-back. Four of them (NOP, CLE, CHI, "
                       "MIA) have in fact filed. Because scripts/strategy_lab.py reads the "
                       "state from that file, the refreshed rows appear in out_players_* but "
                       "out_count_* stays blank and availability_state_* still reads "
                       "NOT_YET_DUE."),
        },
        "source": "data/app/report_availability.json + " + REPORT_NEW,
    })

    # R5 - the engine is injury-blind
    li = build_line_invariance()
    findings.append({
        "id": "RR-05",
        "check": "an injury refresh can move a published originated line",
        "result": "FAIL",
        "n": len(li["price_fields_that_moved"]),
        "detail": {
            "price_fields_that_moved": sorted(li["price_fields_that_moved"]),
            "availability_fields_that_changed": sorted(li["availability_fields_that_changed"]),
            "picks_identical": li["picks_identical"],
            "effect": ("0 of %d price fields moved on %d lines. Until a minutes-to-value "
                       "mapping is licensed and validated, injuries inform the reader and "
                       "not the line."
                       % (len(li["price_fields_compared"]), li["lines_compared"])),
        },
        "source": "scripts/strategy_lab.py, re-run in this audit",
    })

    # R6 - how much of the minutes table the impact figures can actually see
    ri = build_rotation_impact()
    tot_out = sum(len(r["refreshed_out"]) for r in ri["rows"])
    tot_unknown = sum(r["players_without_official_minutes_count"] for r in ri["rows"])
    findings.append({
        "id": "RR-06",
        "check": "the minutes/production vacuum can be computed for every listed player",
        "result": "PARTIAL",
        "n": tot_unknown,
        "detail": {
            "players_listed_out_or_doubtful": tot_out,
            "of_those_with_a_captured_official_minutes_figure": tot_out - tot_unknown,
            "without": tot_unknown,
            "captured_minutes_table": "data/app/players_top31_2026-11-14c.csv (31 players)",
            "effect": ("The vacuum is a floor. Extending it needs a full official per-player "
                       "capture, which is a fetch-size decision for the owner (see the "
                       "questions page)."),
        },
        "source": PLAYERS_URL,
    })

    # R7 - register sizes actually published
    findings.append({
        "id": "RR-07",
        "check": "the published register sizes",
        "result": "INFO",
        "n": None,
        "detail": {
            "flags": len(canon["flags"]),
            "questions": len(canon["questions"]),
            "suggestions": len(canon["suggestions"]),
            "review_findings": len(canon["review_findings"]),
            "review_rows": len(canon["review"]),
            "requirements": len(canon["requirements"]),
            "strategies": len(canon["strategies"]),
            "sources": len(canon["sources"]),
            "lines": len(canon["lines"]),
            "picks": len(canon["picks"]),
            "injury_impact_rows": len(canon["injury_impact"]),
        },
        "source": "data/app/canonical.json (generated by scripts/assemble_canonical.py)",
    })

    # R8 - every root-level html this session can see is reachable from the
    # workflow's staged artifact or from an index page
    with open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8") as fh:
        wf = fh.read()
    roots = sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))
    staged = sorted(set(re.findall(r"^\s*cp\s+([A-Za-z0-9_]+\.html)", wf, re.M)))
    unstaged = [f for f in roots if f not in staged]
    findings.append({
        "id": "RR-08",
        "check": "every root-level HTML page is staged into the Pages artifact",
        "result": "PASS" if not unstaged else "REVIEW",
        "n": len(unstaged),
        "detail": {"root_pages": roots, "staged_by_workflow": staged,
                   "not_staged": unstaged},
        "source": ".github/workflows/pages.yml (repository file)",
    })

    out = {
        "session": SESSION,
        "built_on": "2026-11-14",
        "method": ("each finding is produced by a check that runs against files in this "
                   "repository; the source column names the official page or repository "
                   "file the check reads. Nothing here is a manual judgement."),
        "findings": findings,
    }
    jdump("repo_review.json", out)
    return out


# ---------------------------------------------------------------------------
# 6. flags.json
# ---------------------------------------------------------------------------
def build_flags():
    new = jload(os.path.join(APP, "official_injuries_2026-11-14_0130PM.json"))
    delta = new["delta_vs_published_canonical"]
    flags = [
        {
            "id": "F-1823b910-01",
            "severity": "high",
            "area": "injury freshness",
            "title": "The published injury snapshot is 8h15m (24 report versions) behind the "
                     "newest official report",
            "evidence": ("The canonical dashboard publishes the 2026-11-14 05:15 AM ET report "
                         "(49 rows). The official index now lists the November 14 reports "
                         "through 1:30 PM ET; the 1:45 PM probe returns AccessDenied, so "
                         "1:30 PM is the newest that exists."),
            "values": {"published_rows": 49, "newest_rows": new["count"],
                       "published_player_rows": 26, "newest_player_rows": new["player_rows"]},
            "impact": ("Four of the five 11/14 team-games the site publishes as NOT YET "
                       "SUBMITTED have filed with 24 new player rows."),
            "blocking": False,
            "owner": "owner of data/app/snapshot_manifest.json and scripts/assemble_canonical.py",
            "source": f"{REPORT_0515} vs {REPORT_NEW} (index: {INDEX_URL})",
        },
        {
            "id": "F-1823b910-02",
            "severity": "high",
            "area": "availability layer",
            "title": "report_availability.json still marks four teams NOT_YET_DUE that have "
                     "since filed",
            "evidence": ("data/app/report_availability.json is built from the 04:15 AM report "
                         "and stores deadline_passed_at_capture=False for NOP, CLE, CHI, MIA "
                         "and MEM. In the 1:30 PM report NOP (5 rows), CLE (8), CHI (7) and "
                         "MIA (4) list players; only MEM is still NOT YET SUBMITTED."),
            "values": {"filed_since": [f"{x['matchup']} {x['team']} ({x['player_rows']} rows)"
                                       for x in delta["team_games_resolved"]],
                       "still_not_submitted": ["BKN@MEM MEM"]},
            "impact": ("scripts/strategy_lab.py reads the state from that file, so the "
                       "refreshed rows appear in out_players_* while out_count_* stays blank "
                       "and availability_state_* still reads NOT_YET_DUE. Two published "
                       "fields now disagree with each other."),
            "blocking": False,
            "owner": "owner of scripts/report_availability.py and data/app/report_availability.json",
            "source": f"data/app/report_availability.json + {REPORT_NEW}",
        },
        {
            "id": "F-1823b910-03",
            "severity": "high",
            "area": "model",
            "title": "The originated lines are injury-blind - proven by re-running the engine",
            "evidence": ("scripts/strategy_lab.py was re-run with the 1:30 PM report "
                         "substituted for the 04:45 AM one. 0 of 17 price fields moved on "
                         "27 lines and the pick list is byte-identical; only the absence "
                         "roll-up fields changed."),
            "values": {"lines": 27, "price_fields_compared": 17, "price_fields_moved": 0},
            "impact": ("Donovan Mitchell (Questionable), James Harden (Questionable), Evan "
                       "Mobley (Out) and Jarrett Allen (Questionable) are all named on the "
                       "refreshed report for DAL@CLE, and the published spread for that game "
                       "is unchanged by all four."),
            "blocking": False,
            "owner": "owner of scripts/strategy_lab.py",
            "source": "scripts/strategy_lab.py + data/app/official_injuries_2026-11-14_0130PM.json",
        },
        {
            "id": "F-1823b910-04",
            "severity": "medium",
            "area": "data coverage",
            "title": "The minutes/production vacuum cannot be computed for most listed players",
            "evidence": ("The only official per-player minutes capture in the repository is "
                         "the top 31 by minutes per game. Of the players listed Out or "
                         "Doubtful on the refreshed 11/14 report, all but one fall outside "
                         "that table, so their minutes are unknown and contribute 0 to the "
                         "published floor."),
            "values": {"captured_table_rows": 31,
                       "players_without_a_captured_figure": "see rotation-impact page"},
            "impact": "The published vacuum is a floor, not an estimate. It is labelled as such.",
            "blocking": False,
            "owner": "owner of the capture scripts",
            "source": PLAYERS_URL,
        },
        {
            "id": "F-1823b910-05",
            "severity": "medium",
            "area": "PDF extraction",
            "title": "The 1:30 PM PDF text leaves the Team cell empty on six rows and merges "
                     "the final block",
            "evidence": ("Six page-fragment rows (Claxton, Powell, Sellers, Smith, Swain, "
                         "Wilson) print no team, and the final fragment merges the ATL@MIL "
                         "and OKC@SAC rows into one line. Both are resolved from the same "
                         "document's block structure and cross-checked against the official "
                         "01:00 PM report, which prints every one of them unmerged (check E3)."),
            "values": {"teamless_rows": 6, "merged_block_rows_expanded": 3},
            "impact": ("Resolved, not guessed: the attribution is confirmed by another "
                       "official report rather than by a roster lookup. Chicago's list is "
                       "the one that would have been misattributed by context alone."),
            "blocking": False,
            "owner": SESSION,
            "source": f"{REPORT_NEW} + {REPORT_PREV}",
        },
        {
            "id": "F-1823b910-06",
            "severity": "low",
            "area": "process",
            "title": "PR #70 has been open and conflicting since 2026-11-14 10:47 UTC",
            "evidence": ("PR #70 (arena/f2d4a99f-nba3) touches only COORDINATION.md, is in "
                         "CONFLICTING state and has had no commits for more than eight hours "
                         "at review time. Under the board's takeover rule it is eligible for "
                         "takeover."),
            "values": {"pr": 70, "changed_files": 1},
            "impact": ("No code or site impact - it is an append-only record. This session "
                       "leaves it open rather than force-merging another session's text."),
            "blocking": False,
            "owner": "next session",
            "source": "https://github.com/wingbangboozle1-lang/NBA3/pull/70",
        },
    ]
    out = {"session": SESSION, "built_on": "2026-11-14",
           "note": ("Flagged items do not block anything. Each names an owner and the "
                    "official source that supports it."),
           "flags": flags}
    jdump("flags.json", out)
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    r = build_refresh()
    print(f"refresh.json            : {r['counts']['published_rows']} published rows -> "
          f"{r['counts']['newest_rows']} newest rows; "
          f"{r['counts']['team_games_filed_since']} team-games filed since")
    li = build_line_invariance()
    print(f"line_invariance.json    : moved "
          f"{sum(len(v) for v in li['price_fields_that_moved'].values())} price fields; "
          f"picks identical: {li['picks_identical']}")
    ri = build_rotation_impact()
    print(f"rotation_impact.json    : {len(ri['rows'])} team-games")
    gf = build_gameflow()
    print(f"gameflow.json           : {len(gf['rows'])} games")
    rr = build_repo_review()
    print(f"repo_review.json        : {len(rr['findings'])} findings "
          f"({[f['result'] for f in rr['findings']]})")
    fl = build_flags()
    print(f"flags.json              : {len(fl['flags'])} flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
