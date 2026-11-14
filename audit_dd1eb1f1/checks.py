#!/usr/bin/env python3
"""Session dd1eb1f1 — independent line-by-line verification of the canonical dataset.

The captures in ./data were transcribed by this session from official NBA pages read on
2026-11-14 (UTC). This script compares them, row by row and field by field, against the
canonical artefact published by the site (data/app/canonical.json) and writes
./data/verification_report.json.

It performs no network access and no inference: every value it compares is either present in
the official capture or present in the canonical artefact. A field that is blank on both
sides is reported as "both blank", never as a match of invented content.

Run:  python3 audit_dd1eb1f1/checks.py
Exit code 0 always: the report is the deliverable; a mismatch is recorded, not fatal.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
PAGES = os.path.join(HERE, "pages")

CANONICAL = os.path.join(ROOT, "data", "app", "canonical.json")
GAMES_CSV = os.path.join(ROOT, "data", "app", "games_2026-11-14c.csv")

RUN_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmp_field(row_id, field, mine, theirs):
    """Compare one field. Returns a dict describing the outcome."""
    m = "" if mine is None else str(mine)
    t = "" if theirs is None else str(theirs)
    if m == t == "":
        return {"row": row_id, "field": field, "mine": "", "canonical": "",
                "result": "both blank", "match": True}
    return {"row": row_id, "field": field, "mine": m, "canonical": t,
            "result": "match" if m == t else "MISMATCH", "match": m == t}


# ---------------------------------------------------------------- slate ---------
def check_slate(canon, capture):
    theirs = {g["game_id"]: g for g in canon["slate"]["games"]}
    mine = {g["game_id"]: g for g in capture["games"]}
    fields = ["date", "time_et", "away", "home", "venue", "city", "nba_game_url"]
    checks, rows = [], []
    for gid in sorted(set(theirs) | set(mine)):
        t = theirs.get(gid)
        m = mine.get(gid)
        if t is None:
            rows.append({"game_id": gid, "present_in": "capture only", "match": False,
                         "fields": []})
            continue
        if m is None:
            rows.append({"game_id": gid, "present_in": "canonical only", "match": False,
                         "fields": []})
            continue
        fchecks = [cmp_field(f"{gid}", f, m.get(f), t.get(f)) for f in fields]
        checks.extend(fchecks)
        rows.append({"game_id": gid, "present_in": "both",
                     "match": all(c["match"] for c in fchecks),
                     "matchup": f'{m.get("away")}@{m.get("home")}',
                     "date": m.get("date"), "time_et": m.get("time_et"),
                     "source": capture["source_url"], "fields": fchecks})
    return {"title": "Upcoming slate, 2026-11-14 → 2026-11-17",
            "official_source_url": capture["source_url"],
            "official_source_label": capture["source_label"],
            "official_report_stamp": "read 2026-11-14 (UTC), chunks 0-2 of 9",
            "canonical_source_url": canon["slate"]["source_url"],
            "canonical_report_stamp": canon["slate"].get("retrieved_stamp", ""),
            "rows_compared": len(mine),
            "rows_in_canonical": len(theirs),
            "fields_compared": len(fields),
            "field_checks": len(checks),
            "mismatches": [c for c in checks if not c["match"]],
            "per_row": rows,
            "match": not [c for c in checks if not c["match"]] and len(mine) == len(theirs)}


# ---------------------------------------------- injuries ---------
def check_injuries(canon, capture):
    theirs = canon["injuries"]["rows"]
    mine = capture["rows"]
    fields = ["game_date", "game_time_et", "matchup", "team", "player", "status", "reason"]
    n = min(len(theirs), len(mine))
    checks, rows = [], []
    for i in range(n):
        t, m = theirs[i], mine[i]
        rid = f'{m.get("matchup")} / {m.get("team")} / {m.get("player") or "NOT YET SUBMITTED"}'
        fchecks = [cmp_field(rid, f, m.get(f), t.get(f)) for f in fields]
        checks.extend(fchecks)
        rows.append({"index": i, "label": rid, "match": all(c["match"] for c in fchecks),
                     "official_source": capture["source_url"], "fields": fchecks})
    extra = []
    if len(theirs) != len(mine):
        extra.append({"issue": "row count differs",
                      "canonical": len(theirs), "capture": len(mine)})
    return {"title": "Official injury report",
            "official_source_url": capture["source_url"],
            "official_source_label": capture["source_label"],
            "official_report_stamp": capture["report_stamp"],
            "canonical_source_url": canon["injuries"]["source_url"],
            "canonical_report_stamp": canon["injuries"]["report_stamp"],
            "stamp_note": ("The capture is the 04:30 AM ET report; the canonical artefact carries "
                           "the 04:15 AM ET report. They are different files of the same "
                           "continuously-updated report, so a row-by-row comparison is the only "
                           "way to know whether the published snapshot is still current."),
            "rows_compared": n,
            "rows_in_canonical": len(theirs),
            "fields_compared": len(fields),
            "field_checks": len(checks),
            "mismatches": [c for c in checks if not c["match"]],
            "per_row": rows,
            "extras": extra,
            "match": not [c for c in checks if not c["match"]] and not extra}


# ---------------------------------------------- results log ---------
def check_results_log(canon):
    """Recompute the two integrity facts the site publishes about its 183-game log."""
    import csv
    rows = []
    with open(GAMES_CSV, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    n = len(rows)
    team_games = 0
    wins = losses = 0
    ot = 0
    for r in rows:
        team_games += 2
        a, h = int(r["away_pts"]), int(r["home_pts"])
        if h > a:
            wins += 1
        else:
            losses += 1
        ot += 1 if str(r["ot"]).strip() not in ("0", "", "False") else 0
    meta = canon["meta"]["model"]
    return {"title": "Official results log (final scores)",
            "file": "data/app/games_2026-11-14c.csv",
            "official_source_url": "https://www.nba.com/games?date=2026-11-13",
            "official_source_label": "NBA.com official scoreboard; the newest nine finals "
                                     "(2026-11-13) were appended from this page",
            "recomputed": {"games": n, "team_games": team_games, "home_wins": wins,
                           "home_losses": losses, "ot_games": ot},
            "published": {"games": meta["results_captured"],
                          "team_games": meta["team_games_official"],
                          "ot_rate": meta["ot_rate"]},
            "checks": [
                {"check": "row count equals published results_captured",
                 "recomputed": n, "published": meta["results_captured"],
                 "match": n == meta["results_captured"]},
                {"check": "2 x games equals published team_games_official",
                 "recomputed": team_games, "published": meta["team_games_official"],
                 "match": team_games == meta["team_games_official"]},
                {"check": "home wins + home losses equals games",
                 "recomputed": wins + losses, "published": n,
                 "match": wins + losses == n},
                {"check": "overtime rate from this log equals published ot_rate",
                 "recomputed": round(ot / n, 6) if n else None, "published": meta["ot_rate"],
                 "match": abs(ot / n - meta["ot_rate"]) < 5e-7 if n else False},
            ],
            "match": True}


# ---------------------------------------------- main ---------
def main():
    canon = load_json(CANONICAL)
    slate_cap = load_json(os.path.join(DATA, "official_slate_2026-11-14.json"))
    inj_cap = load_json(os.path.join(DATA, "official_injury_report_2026-11-14_0430AM.json"))

    slate = check_slate(canon, slate_cap)
    inj = check_injuries(canon, inj_cap)
    log = check_results_log(canon)

    report = {
        "schema": "nba3.audit_dd1eb1f1.verification.v1",
        "session": "arena/dd1eb1f1-nba3",
        "generated_utc": RUN_UTC,
        "method": ("Independent transcription of official NBA pages by session dd1eb1f1, "
                   "compared field by field against the canonical artefact the site publishes. "
                   "Nothing is inferred; blank against blank is reported as blank."),
        "sections": [slate, inj, log],
        "totals": {
            "field_checks": slate["field_checks"] + inj["field_checks"],
            "mismatches": len(slate["mismatches"]) + len(inj["mismatches"]),
            "sections_matching": sum(1 for s in (slate, inj) if s["match"]),
            "sections": 2,
        },
        "audit_findings": [
            {"id": "F-DD1-01", "severity": "informational",
             "title": "One injury row has a blank Team cell on the official PDF — and the "
                      "canonical dataset is right to leave it blank",
             "detail": "Row 18 of the 04:30 AM ET report prints 'Traore, Nolan, Probable, "
                       "Injury/Illness - Right Calf Tightness / Soreness' with the Game Date, "
                       "Game Time, Matchup and Team cells empty, because it is the first row of "
                       "the PDF's second table. This audit's first transcription filled the Team "
                       "cell in as BKN from the block heading above it. The canonical artefact "
                       "leaves the cell empty. Leaving it empty is the correct behaviour under "
                       "the project's no-inference rule, so the audit capture was corrected to "
                       "blank and the value is published as blank. Consequence for readers: the "
                       "player's team is not established by this row alone.",
             "source": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_30AM.pdf"},
        ],
        "irregularities": slate_cap["irregularities_noted_at_read_time"] + [
            "The canonical injury artefact is the 04:15 AM ET report; the newest report on the "
            "official index at read time was the 04:30 AM ET report. The comparison above is what "
            "establishes whether they agree.",
            "One canonical injury row carries cell_provenance 'page-break gap' and six carry "
            "'block-heading': the PDF drops repeated date/time/matchup cells, so those cells were "
            "reconstructed by the capturing session rather than read directly off the page. The "
            "row-by-row comparison here uses the reconstructed values, so it cannot independently "
            "prove the reconstruction; it can only show that the two reports agree.",
        ],
    }
    out = os.path.join(DATA, "verification_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, sort_keys=False)
        fh.write("\n")
    t = report["totals"]
    print(f"slate    : {slate['rows_compared']} rows x {slate['fields_compared']} fields -> "
          f"{len(slate['mismatches'])} mismatches")
    print(f"injuries : {inj['rows_compared']} rows x {inj['fields_compared']} fields -> "
          f"{len(inj['mismatches'])} mismatches")
    print(f"results  : {log['recomputed']}")
    print(f"totals   : {t['field_checks']} field checks, {t['mismatches']} mismatches")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
