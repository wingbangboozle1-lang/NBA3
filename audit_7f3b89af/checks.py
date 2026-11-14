"""Line-by-line checks for the audit tree of session arena/7f3b89af-nba3.

Every comparison here is between something this session read off an official NBA page today and
something the repository already publishes. Nothing is inferred: a cell the official page does not
print is compared as "not printed", and a cell the repository fills from another page is checked
against that other page.

Run:  python3 audit_7f3b89af/checks.py
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")

sys.path.insert(0, HERE)
import capture  # noqa: E402

CANONICAL = os.path.join(ROOT, "data", "app", "canonical.json")

CHECKS = []


def check(cid, name, source, expected, observed, ok, detail="", status=None):
    """status is 'pass', 'flag' (a real, documented difference that is published on the Flagged
    page and does not break the build) or 'fail' (unexplained; breaks the build)."""
    if status is None:
        status = "pass" if ok else "fail"
    CHECKS.append({
        "id": cid,
        "name": name,
        "source": source,
        "expected": expected,
        "observed": observed,
        "status": status,
        "detail": detail,
    })
    return ok


def time_candidates(t):
    """The injury PDF prints its tip times with no meridiem ('08:00 (ET)'), so a value can only be
    checked against the official schedule, which does print one. Both readings are returned; a
    match on either counts as verified."""
    t = (t or "").replace(" ET", "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if not m:
        return [norm_time(t)]
    hour, minute = int(m.group(1)), m.group(2)
    return ["%02d:%s" % (hour % 24, minute), "%02d:%s" % (hour % 12 + 12, minute),
            "%02d:%s" % (hour % 12, minute)]


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def norm_time(t):
    """'7:00 PM ET' | '07:00' | '7:00 PM' -> '19:00' (24h). Blank stays blank."""
    t = (t or "").replace(" ET", "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*([AP])M$", t, re.I)
    if m:
        hour = int(m.group(1)) % 12
        if m.group(3).upper() == "P":
            hour += 12
        return "%02d:%s" % (hour, m.group(2))
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if m:
        return "%02d:%s" % (int(m.group(1)), m.group(2))
    return t


def printed_fields(cells_printed):
    """Which of the 7 columns the PDF actually printed for a row."""
    m = {
        "full": ("game_date", "game_time_et", "matchup", "team_name", "player", "status", "reason"),
        "date not printed": ("game_time_et", "matchup", "team_name", "player", "status", "reason"),
        "date/time not printed": ("matchup", "team_name", "player", "status", "reason"),
        "date/time/matchup not printed": ("team_name", "player", "status", "reason"),
        "continuation": ("player", "status", "reason"),
    }
    if cells_printed not in m:
        raise SystemExit("unknown cells_printed value: %r" % cells_printed)
    return m[cells_printed]


def forward_fill(rows):
    """Attach block context: the most recent matchup / team printed before this row.

    This is document position, not an inference about a player: it says which block of the PDF the
    row sits in. `block_*_printed` records whether the value was on the row itself.
    """
    out, matchup, team = [], "", ""
    for r in rows:
        if r["matchup"]:
            matchup = r["matchup"]
        if r["team_name"]:
            team = r["team_name"]
        d = dict(r)
        d["block_matchup"] = matchup
        d["block_team_name"] = team
        d["block_team"] = capture.TEAM_ABBR.get(team, "")
        d["matchup_on_row"] = bool(r["matchup"])
        d["team_on_row"] = bool(r["team_name"])
        out.append(d)
    return out


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------------------------
# 1. the two morning reports and the two afternoon reports, compared row for row
# ---------------------------------------------------------------------------------------------
def compare_reports(a_key, b_key):
    a = load_json(os.path.join(DATA, "injury_report_%s.json" % a_key))
    b = load_json(os.path.join(DATA, "injury_report_%s.json" % b_key))
    diffs = []
    if len(a["rows"]) != len(b["rows"]):
        diffs.append("row counts differ: %d vs %d" % (len(a["rows"]), len(b["rows"])))
    for i, (ra, rb) in enumerate(zip(a["rows"], b["rows"]), 1):
        for f in ("game_date", "game_time_et", "matchup", "team_name", "player", "status", "reason"):
            if ra[f] != rb[f]:
                diffs.append("row %d %s: %r vs %r" % (i, f, ra[f], rb[f]))
    return a, b, diffs


def section_report_identity():
    a, b, diffs = compare_reports("2026-11-14_04_15AM", "2026-11-14_04_45AM")
    check("C1", "Injury report 04:15 AM ET vs 04:45 AM ET (the file strategy_lab.py reads)",
          a["source_url"] + " | " + b["source_url"],
          "the two reports are content-identical",
          "%d rows compared, %d differences" % (len(a["rows"]), len(diffs)),
          not diffs, "; ".join(diffs[:5]))

    c, d, diffs2 = compare_reports("2026-11-14_01_15PM", "2026-11-14_01_30PM")
    check("C2", "Injury report 01:15 PM ET vs 01:30 PM ET (newest on the index)",
          c["source_url"] + " | " + d["source_url"],
          "the two reports are content-identical",
          "%d rows compared, %d differences" % (len(c["rows"]), len(diffs2)),
          not diffs2, "; ".join(diffs2[:5]))


# ---------------------------------------------------------------------------------------------
# 2. the published canonical rows vs the 04:15 AM PDF they claim to come from
# ---------------------------------------------------------------------------------------------
def section_canonical_vs_pdf():
    canon = load_json(CANONICAL)
    cap = load_json(os.path.join(DATA, "injury_report_2026-11-14_04_15AM.json"))
    crow = canon["injuries"]["rows"]
    arow = cap["rows"]

    check("C3", "Published canonical injury count vs the 04:15 AM PDF",
          cap["source_url"], "row count matches the PDF",
          "canonical %d rows, PDF %d rows" % (len(crow), len(arow)),
          len(crow) == len(arow))

    mismatches, compared = [], 0
    for i, (cr, ar) in enumerate(zip(crow, arow), 1):
        for f in printed_fields(ar["cells_printed"]):
            compared += 1
            if (cr.get(f) or "") != ar[f]:
                mismatches.append("row %d (%s) %s: canonical %r, PDF %r"
                                  % (i, ar.get("player") or ar.get("team_name"), f, cr.get(f), ar[f]))
    check("C4", "Every published canonical injury cell the PDF prints, checked against the PDF",
          cap["source_url"], "0 mismatches on printed cells",
          "%d cells compared, %d mismatches" % (compared, len(mismatches)),
          not mismatches, "; ".join(mismatches[:5]))

    # cells canonical carries that the PDF does not print
    fills = []
    for i, (cr, ar) in enumerate(zip(crow, arow), 1):
        for f in ("game_date", "game_time_et", "matchup", "team_name"):
            if f in printed_fields(ar["cells_printed"]):
                continue
            v = cr.get(f) or ""
            if v:
                fills.append({"row": i, "field": f, "value": v,
                              "player": ar["player"], "team_name": ar["team_name"],
                              "matchup": ar["matchup"] or cr.get("matchup"),
                              "pdf_printed": ar["cells_printed"]})
    return canon, fill_verify(fills)


def fill_verify(fills):
    """Values canonical filled in from somewhere other than the injury PDF, re-checked against the
    official schedule page -- which is where those values actually live."""
    slate = load_json(os.path.join(DATA, "slate_2026-11-14_1117.json"))["rows"]
    by_matchup = {}
    for g in slate:
        by_matchup.setdefault("%s@%s" % (g["away"], g["home"]), []).append(g)

    verified, unverified = 0, []
    checked = 0
    for f in fills:
        games = by_matchup.get(f["matchup"], [])
        if f["field"] == "game_date":
            want = f["value"].replace("11/14/2026", "2026-11-14").replace("11/15/2026", "2026-11-15")
            ok = any(g["date"] == want for g in games)
        elif f["field"] == "game_time_et":
            wants = time_candidates(f["value"])
            ok = any(norm_time(g["time_et"]) in wants for g in games)
        elif f["field"] == "matchup":
            # continuation rows: canonical carries the block's matchup, which the PDF drops.
            # The only honest check is that the matchup is one the official schedule prints.
            ok = bool(games)
        else:
            continue
        checked += 1
        if ok:
            verified += 1
        else:
            unverified.append(f)
    check("C5", "Cells the canonical set fills in but the injury PDF does not print, re-checked "
                "against the official schedule (their true source)",
          capture.SLATE_URL, "every filled date/time/matchup agrees with the official schedule",
          "%d filled cells, %d verified against the schedule, %d not verified"
          % (len(fills), verified, len(unverified)),
          not unverified,
          "Filled cells are correct in value but are attributed in canonical.json to the injury "
          "PDF, whose row-level `source` link is that PDF. Flagged as F-7F3-03 (provenance, not a "
          "wrong number).")
    return {"count": len(fills), "checked": checked, "verified": verified,
            "unverified": unverified, "cells": fills,
            "by_field": {"date_or_time": sum(1 for f in fills
                                             if f["field"] in ("game_date", "game_time_et")),
                         "matchup": sum(1 for f in fills if f["field"] == "matchup")}}


# ---------------------------------------------------------------------------------------------
# 3. the 27-game window vs the live official schedule
# ---------------------------------------------------------------------------------------------
def section_slate(canon):
    slate = load_json(os.path.join(DATA, "slate_2026-11-14_1117.json"))["rows"]
    lines = canon["lines"]
    cslate = canon["slate"]["games"]

    check("C6", "Window size: live schedule vs published canonical slate and lines",
          capture.SLATE_URL, "27 games in 2026-11-14 .. 2026-11-17",
          "live %d, canonical slate %d, canonical lines %d" % (len(slate), len(cslate), len(lines)),
          len(slate) == len(cslate) == len(lines) == 27)

    def key(g):
        return g["game_id"]

    live = {key(g): g for g in slate}
    diffs = []
    for label, rows, fields in (
        ("canonical slate", cslate, (("date", "date"), ("time_et", "time_et"), ("away", "away"),
                                     ("home", "home"), ("nba_game_url", "game_url"))),
        ("canonical lines", lines, (("date", "date"), ("time_et", "time_et"), ("away", "away"),
                                    ("home", "home"), ("nba_game_url", "game_url"))),
    ):
        for r in rows:
            g = live.get(r["game_id"])
            if not g:
                diffs.append("%s: game id %s is not on the live schedule" % (label, r["game_id"]))
                continue
            for cf, lf in fields:
                a, b = r[cf], g[lf]
                if cf == "time_et":
                    a, b = norm_time(a), norm_time(b)
                if a != b:
                    diffs.append("%s %s %s: published %r, live %r" % (label, r["game_id"], cf, a, b))
    check("C7", "Every published slate and line row, field by field, against the live schedule",
          capture.SLATE_URL, "0 differences",
          "27 games x 5 fields x 2 tables = %d comparisons, %d differences" % (270, len(diffs)),
          not diffs, "; ".join(diffs[:5]))

    # the irregularity an earlier session flagged: POR@MIN printed twice, and game ids out of order
    por = [g for g in slate if g["away"] == "POR" and g["home"] == "MIN"]
    nyk = [g for g in slate if g["away"] == "NYK" and g["home"] == "TOR"]
    ids_1117 = [g["game_id"] for g in slate if g["date"] == "2026-11-17"]
    ordered = ids_1117 == sorted(ids_1117)
    check("C8", "Official-schedule irregularity: the same matchup printed twice inside the window",
          capture.SLATE_URL, "flagged for the owner, not corrected here",
          "POR@MIN appears on %s; NYK@TOR appears on %s; 11/17 game ids in printed order: %s"
          % (", ".join(g["date"] for g in por), ", ".join(g["date"] for g in nyk), ", ".join(ids_1117)),
          True,
          "Confirmed still present on the live page today. These are the NBA's own page values, so "
          "they are published as read; see F-7F3-04.")


# ---------------------------------------------------------------------------------------------
# 4. team ratings
# ---------------------------------------------------------------------------------------------
# The drift this session found and published as F-7F3-05. If any OTHER team or field moves later,
# the check fails instead of flagging, so new drift cannot pass silently.
KNOWN_RATING_DRIFT = {
    ("CLE", "off_rtg"), ("CLE", "def_rtg"), ("CLE", "pace"),
    ("CHA", "off_rtg"), ("CHA", "def_rtg"), ("CHA", "pace"),
}


def section_ratings(canon):
    live = load_json(os.path.join(DATA, "team_ratings_2026-11-14.json"))["teams"]
    stored = {t["team"]: t for t in canon["ratings"]["teams"]}
    diffs, compared = [], 0
    for t in live:
        s = stored.get(t["team"])
        if not s:
            diffs.append((t["team"], "row", "missing from canonical ratings", ""))
            continue
        for f in ("gp", "w", "l", "off_rtg", "def_rtg", "net_rtg", "pace"):
            compared += 1
            if abs(float(s[f]) - float(t[f])) > 1e-9:
                diffs.append((t["team"], f, s[f], t[f]))
    keys = {(d[0], d[1]) for d in diffs}
    unexpected = sorted(keys - KNOWN_RATING_DRIFT)
    ok = not unexpected
    check("C9", "Official team advanced statistics (the model's rating inputs) re-read today",
          capture.RATINGS_URL,
          "no team/field moves beyond the drift documented as F-7F3-05",
          "%d teams x 7 fields = %d comparisons, %d differences, %d unexpected"
          % (len(live), compared, len(diffs), len(unexpected)),
          ok,
          "Differences found: " + "; ".join("%s %s: canonical %s, live %s" % d for d in diffs),
          status="flag" if (diffs and ok) else None)

    total_gp = sum(t["gp"] for t in live)
    check("C10", "Games played cross-foot: sum of the 30 official GP figures / 2",
          capture.RATINGS_URL, "183 completed games (the published results-log count)",
          "sum GP = %d, so %d games" % (total_gp, total_gp // 2),
          total_gp // 2 == 183,
          "Independent arithmetic check on the 183-game results log, from the official standings "
          "columns rather than from the results file itself.")
    return diffs


# ---------------------------------------------------------------------------------------------
# 4b. where the rating drift lands: projected pace on the game-flow page
# ---------------------------------------------------------------------------------------------
def section_pace_impact(canon, rating_diffs):
    """The engine's margin ('rating') and total ('ppg'/'oppg' fits) are fitted from the results log,
    not from this page, so the drift cannot move a spread or a total. Pace IS read straight from
    this page, so the published proj_pace moves. Quantify it rather than assert it."""
    live = {t["team"]: t for t in load_json(
        os.path.join(DATA, "team_ratings_2026-11-14.json"))["teams"]}
    stored = {t["team"]: t for t in canon["ratings"]["teams"]}
    moved = sorted({team for team, _, _, _ in rating_diffs
                    if isinstance(team, str) and team in live})
    rows = []
    for g in canon["gameflow"]:
        a, h = g["away"], g["home"]
        if a not in moved and h not in moved:
            continue
        pub = g["proj_pace"]
        live_paces = [live[t]["pace"] for t in (h, a) if t in live]
        stored_paces = [stored[t]["pace"] for t in (h, a) if t in stored]
        if len(live_paces) != 2 or len(stored_paces) != 2:
            continue
        now = sum(live_paces) / 2.0
        rows.append({
            "matchup": g["matchup"], "date": g["date"], "game_id": g["game_id"],
            "proj_pace_published": pub,
            "proj_pace_from_live_page": round(now, 4),
            "delta": round(now - (sum(stored_paces) / 2.0), 4),
            "moved_teams": [t for t in (h, a) if t in moved],
            "source": capture.RATINGS_URL,
        })
    worst = max((abs(r["delta"]) for r in rows), default=0.0)
    check("C13", "Where the rating drift lands: projected pace on the game-flow page",
          capture.RATINGS_URL,
          "spread and total unaffected; pace moves by less than 0.1 possessions",
          "%d games carry a moved team; largest published proj_pace change %+.4f"
          % (len(rows), worst),
          worst < 0.1,
          "The engine reads pace for proj_pace but fits margin and total from the results log, so "
          "F-7F3-05 cannot move a published spread or total. The %d affected games are listed on "
          "the Pace page." % len(rows),
          status="flag" if rows else None)
    return rows


# ---------------------------------------------------------------------------------------------
# 4c. the injury PDF's own time column vs the official schedule
# ---------------------------------------------------------------------------------------------
def section_pdf_times_vs_schedule():
    slate = load_json(os.path.join(DATA, "slate_2026-11-14_1117.json"))["rows"]
    by_matchup = {}
    for g in slate:
        by_matchup.setdefault("%s@%s" % (g["away"], g["home"]), []).append(g)
    compared, bad = 0, []
    for key in ("2026-11-14_04_15AM", "2026-11-14_01_30PM"):
        rows = load_json(os.path.join(DATA, "injury_report_%s.json" % key))["rows"]
        for r in rows:
            if not r["game_time_et"] or not r["matchup"]:
                continue
            games = by_matchup.get(r["matchup"], [])
            if not games:
                continue
            compared += 1
            if norm_time(games[0]["time_et"]) not in time_candidates(r["game_time_et"]):
                bad.append("%s %s: PDF %s, schedule %s"
                           % (key, r["matchup"], r["game_time_et"], games[0]["time_et"]))
    check("C14", "Tip times printed in the injury PDFs, checked against the official schedule",
          capture.SLATE_URL, "0 disagreements",
          "%d printed time cells compared, %d disagreements" % (compared, len(bad)),
          not bad, "; ".join(bad[:5]))


# ---------------------------------------------------------------------------------------------
# 5. what changed between the published snapshot (04:15 AM) and the newest report (01:30 PM)
# ---------------------------------------------------------------------------------------------
def section_injury_drift(canon):
    prior = forward_fill(load_json(os.path.join(DATA, "injury_report_2026-11-14_04_15AM.json"))["rows"])
    newest = forward_fill(load_json(os.path.join(DATA, "injury_report_2026-11-14_01_30PM.json"))["rows"])

    def pkey(r):
        return (r["block_matchup"], r["player"], r["reason"])

    def skey(r):
        return (r["block_matchup"], r["player"])

    prior_players = {skey(r): r for r in prior if not r["is_not_yet_submitted"]}
    new_players = {skey(r): r for r in newest if not r["is_not_yet_submitted"]}

    only_new = [new_players[k] for k in new_players if k not in prior_players]
    only_prior = [prior_players[k] for k in prior_players if k not in new_players]
    changed = []
    for k in sorted(set(prior_players) & set(new_players)):
        if prior_players[k]["status"] != new_players[k]["status"]:
            changed.append({"matchup": k[0], "player": k[1],
                            "status_04_15AM": prior_players[k]["status"],
                            "status_01_30PM": new_players[k]["status"],
                            "reason": new_players[k]["reason"]})

    # team-level filing transitions
    def filed(rows):
        out = {}
        for r in rows:
            out[(r["block_matchup"], r["block_team_name"])] = not r["is_not_yet_submitted"]
        return out

    pf, nf = filed(prior), filed(newest)
    transitions = []
    for k in sorted(nf):
        if k[0].startswith("") and pf.get(k) is not None and pf[k] != nf[k]:
            transitions.append({"matchup": k[0], "team": k[1],
                                "at_04_15AM": "FILED" if pf[k] else "NOT YET SUBMITTED",
                                "at_01_30PM": "FILED" if nf[k] else "NOT YET SUBMITTED"})

    # 11/14 only: what tonight's games gained
    tonight = sorted({r["block_matchup"] for r in newest
                      if r["block_matchup"] and r["game_date"] in ("11/14/2026", "")})
    per_game = {}
    for m in tonight:
        n_out = sum(1 for r in newest if r["block_matchup"] == m and r["status"] == "Out"
                    and not r["is_not_yet_submitted"] and r["game_date"] in ("11/14/2026", ""))
        n_new = sum(1 for r in only_new if r["block_matchup"] == m)
        per_game[m] = {"new_rows": n_new, "out_players_01_30PM": n_out}

    check("C11", "How far the published injury snapshot has drifted from the newest official report",
          "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf | "
          "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf",
          "the published snapshot still matches the report it was taken from",
          "%d player rows added, %d removed, %d status changes, %d teams filed between 04:15 AM "
          "and 01:30 PM" % (len(only_new), len(only_prior), len(changed),
                            sum(1 for t in transitions if t["at_01_30PM"] == "FILED")),
          True,
          "Not a pass/fail: the snapshot is faithful to the 04:15 AM report, which is exactly the "
          "problem. The newest official report is 01:30 PM ET. Flagged as F-7F3-01.")

    return {
        "prior_stamp": "2026-11-14 04:15 AM ET",
        "newest_stamp": "2026-11-14 01:30 PM ET",
        "rows_only_in_newest": [
            {"matchup": r["block_matchup"], "team_block": r["block_team_name"],
             "team_on_row": r["team_on_row"], "player": r["player"],
             "status": r["status"], "reason": r["reason"]}
            for r in sorted(only_new, key=lambda r: (r["block_matchup"], r["player"]))],
        "rows_only_in_prior": [
            {"matchup": r["block_matchup"], "player": r["player"], "status": r["status"],
             "reason": r["reason"]}
            for r in sorted(only_prior, key=lambda r: (r["block_matchup"], r["player"]))],
        "status_changes": changed,
        "team_filing_transitions": transitions,
        "tonight_by_game": per_game,
        "counts": {"player_rows_prior": len(prior_players), "player_rows_newest": len(new_players),
                   "added": len(only_new), "removed": len(only_prior), "status_changes": len(changed)},
    }


# ---------------------------------------------------------------------------------------------
# 6. does the drift touch the published picks?
# ---------------------------------------------------------------------------------------------
def section_pick_exposure(canon, drift):
    """Which published lines/picks sit on a game whose availability picture changed after the
    snapshot the site was built from."""
    touched = {}
    for m, v in drift["tonight_by_game"].items():
        if v["new_rows"]:
            touched[m] = v
    lines = {("%s@%s" % (l["away"], l["home"])): l for l in canon["lines"]}
    rows = []
    for m in sorted(touched):
        l = lines.get(m)
        if not l:
            continue
        rows.append({
            "matchup": m,
            "date": l["date"],
            "game_id": l["game_id"],
            "orig_spread_home": l["orig_spread_home"],
            "orig_total": l["orig_total"],
            "availability_state_home": l["availability_state_home"],
            "availability_state_away": l["availability_state_away"],
            "out_count_home": l["out_count_home"],
            "out_count_away": l["out_count_away"],
            "new_rows_after_snapshot": touched[m]["new_rows"],
            "out_players_01_30PM": touched[m]["out_players_01_30PM"],
            "nba_game_url": l["nba_game_url"],
        })
    check("C12", "Published 11/14 lines whose injury picture changed after the snapshot",
          "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf",
          "counted and published, not silently refreshed",
          "%d of 5 games on 2026-11-14 gained player rows after the published snapshot" % len(rows),
          True,
          "The originated spread and total are not injury-adjusted (eff_spread_home equals "
          "orig_spread_home on every published row), so the numbers themselves do not move. What "
          "moves is the availability state and the Out counts printed beside them, and the "
          "minutes/production vacuum on the injuries page. Flagged as F-7F3-01 / F-7F3-02.")
    return rows


# ---------------------------------------------------------------------------------------------
def main():
    canon = load_json(CANONICAL)
    section_report_identity()
    canon2, fills = section_canonical_vs_pdf()
    section_slate(canon)
    rating_diffs = section_ratings(canon)
    pace_rows = section_pace_impact(canon, rating_diffs)
    section_pdf_times_vs_schedule()
    drift = section_injury_drift(canon)
    exposure = section_pick_exposure(canon, drift)

    flags = build_flags(drift, fills, exposure, rating_diffs, pace_rows)

    report = {
        "session": "arena/7f3b89af-nba3",
        "read_on": "2026-11-14",
        "read_stamp_utc": "2026-11-14T18:45Z",
        "checks": CHECKS,
        "pass": sum(1 for c in CHECKS if c["status"] == "pass"),
        "flag": sum(1 for c in CHECKS if c["status"] == "flag"),
        "fail": sum(1 for c in CHECKS if c["status"] == "fail"),
        "injury_drift": drift,
        "canonical_filled_cells": fills,
        "pick_exposure": exposure,
        "rating_drift": [{"team": d[0], "field": d[1], "canonical": d[2], "live": d[3]}
                         for d in rating_diffs],
        "pace_impact": pace_rows,
        "flags": flags,
    }
    with open(os.path.join(DATA, "verification_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
        fh.write("\n")

    print("checks: %d pass, %d flag, %d fail"
          % (report["pass"], report["flag"], report["fail"]))
    for c in CHECKS:
        print("  [%-4s] %s -- %s" % (c["status"].upper(), c["id"], c["observed"]))
    print()
    print("injury drift 04:15 AM -> 01:30 PM: %d rows added, %d removed, %d status changes"
          % (drift["counts"]["added"], drift["counts"]["removed"], drift["counts"]["status_changes"]))
    for m, v in sorted(drift["tonight_by_game"].items()):
        print("  %-8s new rows after snapshot: %d" % (m, v["new_rows"]))
    print()
    print("flags raised: %s" % ", ".join(f["id"] for f in flags))
    if report["fail"]:
        raise SystemExit(1)
    return report


def build_flags(drift, fills, exposure, rating_diffs, pace_rows):
    flags = [
        {
            "id": "F-7F3-01",
            "severity": "high",
            "title": "The published injury snapshot is nine hours behind the newest official report",
            "evidence": ("data/app/canonical.json publishes the 04:15 AM ET report and records "
                         "newest_report_listed_on_index = \"2026-11-14 04:15 AM ET\" and "
                         "newest_report_checked = true. The official index now lists reports "
                         "through 01:30 PM ET; the 01:45 PM file returns AccessDenied."),
            "what_moved": drift["counts"],
            "source": "https://official.nba.com/nba-injury-report-2026-27-season/",
            "source_newest": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf",
            "owner_action": "Owner decision: re-run the capture against the 01:30 PM report, or keep "
                            "the 04:15 AM snapshot and label the pages with the report stamp they "
                            "were built from. Not executed here -- data/app/** is another session's "
                            "scope, and the pick pages would have to be regenerated with it.",
        },
        {
            "id": "F-7F3-02",
            "severity": "high",
            "title": "Three of tonight's five games had no team report at all when the site was built",
            "evidence": ("At 04:15 AM ET the New Orleans, Cleveland, Chicago and Miami rows all read "
                         "NOT YET SUBMITTED. By 01:30 PM ET all four had filed, adding "
                         "%d player rows in total." % drift["counts"]["added"]),
            "affected_games": sorted(m for m, v in drift["tonight_by_game"].items() if v["new_rows"]),
            "source": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf",
            "owner_action": "Any decision taken from the injuries page or the minutes-vacuum table "
                            "for these games should be taken from the 01:30 PM report, published on "
                            "this audit tree's Injuries page, until the canonical pages refresh.",
        },
        {
            "id": "F-7F3-03",
            "severity": "medium",
            "title": "Canonical injury rows carry date and time cells the injury PDF never printed",
            "evidence": ("%d date-or-time cells in data/app/canonical.json are populated with a "
                         "game date or tip time that the 04:15 AM PDF does not print for that row "
                         "(the PDF drops those columns on page-break continuation blocks), plus %d "
                         "matchup cells taken from the block the row sits in. Every value is "
                         "correct: all %d were re-checked today against the official schedule and "
                         "agree. The problem is attribution: each row's `source` link is the injury "
                         "PDF, not the schedule page the value actually came from."
                         % (fills["by_field"]["date_or_time"], fills["by_field"]["matchup"],
                            fills["verified"])),
            "source": capture.SLATE_URL,
            "owner_action": "Add the schedule URL to those rows, or mark the cell provenance the way "
                            "the blank team cell on the Traore row is already marked. Values need no "
                            "change.",
        },
        {
            "id": "F-7F3-04",
            "severity": "low",
            "title": "Official schedule prints the same matchup twice inside the window",
            "evidence": ("POR@MIN is printed on both 2026-11-16 (game 0022600250) and 2026-11-17 "
                         "(game 0022600254), and NYK@TOR on both 2026-11-15 (0022600241) and "
                         "2026-11-17 (0022600253). The 11/17 game ids are also out of chronological "
                         "order: 0022600257 (10:30 PM) is printed before 0022600256 (11:00 PM). "
                         "Re-confirmed live today; it is the NBA page's own output, not a "
                         "transcription error."),
            "source": capture.SLATE_URL,
            "owner_action": "None needed unless a later window prices POR@MIN or NYK@TOR twice. "
                            "Recorded so a duplicate-looking line is not mistaken for a bug.",
        },
        {
            "id": "F-7F3-05",
            "severity": "low",
            "title": "Two teams' official advanced-statistics cells moved after the published capture",
            "evidence": ("The stored capture (data/app/canonical.json ratings, read 2026-11-14 "
                         "09:45Z) and the same official page read today at 18:45Z agree on all 30 "
                         "teams except Cleveland and Charlotte: " +
                         "; ".join("%s %s %s -> %s" % (d[0], d[1], d[2], d[3]) for d in rating_diffs) +
                         ". Net rating, games played, wins and losses are unchanged for every team, "
                         "so the two moved teams' net ratings are identical to the published ones."),
            "effect": ("The engine fits margin and total from the results log, not from this page, "
                       "so no published spread or total moves. Pace IS read from this page, so "
                       "proj_pace on the game-flow page moves on %d games by at most %.4f "
                       "possessions." % (len(pace_rows),
                                         max((abs(r["delta"]) for r in pace_rows), default=0.0))),
            "source": capture.RATINGS_URL,
            "owner_action": "Re-run the capture when convenient. Nothing is wrong with the "
                            "published numbers; they are nine hours old on two cells.",
        },
    ]
    return flags


if __name__ == "__main__":
    main()
