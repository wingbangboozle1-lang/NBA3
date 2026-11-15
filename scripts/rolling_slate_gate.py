#!/usr/bin/env python3
"""Rolling-slate freshness and provenance gate (session arena/9866a950-nba3).

The brief: "Extend the scheduled job to refresh the official schedule, standings,
team statistics and injury report for each rolling slate, then rebuild only after
freshness and provenance gates pass."

This module IS that gate.  It runs offline and deterministically against the
committed artefacts, and answers three questions:

  PROVENANCE  -- does every input the engine reads (snapshot manifest blocks)
                 exist, carry its official source URL and its retrieval stamp,
                 and does the results log end the day before the priced window?
  FRESHNESS   -- does the manifest window start today (the rolling slate), and
                 does the newest captured injury report cover the window's first
                 date?  A window that starts in the past is a stale snapshot.
  COVERAGE    -- does the slate cover every date of the window with at least one
                 game, and does every window date have an availability state?

Modes (via the GATE_EVENT environment variable, set by the workflow):
  * pull_request  -> report only, exit 0 (a PR branch legitimately carries a
                     snapshot from the day it was cut)
  * anything else -> enforce: any freshness or provenance failure exits non-zero,
                     which stops the build BEFORE the site is rebuilt and
                     deployed, so stale data is never republished.

Run:  python3 scripts/rolling_slate_gate.py
"""
import csv
import datetime
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
ORIGIN = os.path.join(ROOT, "data", "origin")

MANIFEST = os.path.join(APP, "snapshot_manifest.json")
REQUIRED_BLOCKS = ("slate", "ratings", "injuries", "players", "results_log")


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parses(path):
    """True when the artefact parses as whatever it claims to be."""
    try:
        if path.endswith(".json"):
            jload(path)
        else:                                   # csv and friends
            with open(path, newline="", encoding="utf-8") as fh:
                next(csv.reader(fh))
        return True
    except Exception:
        return False


def today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def main():
    failures, warnings, notes = [], [], []
    event = os.environ.get("GATE_EVENT", "push")
    enforce = event != "pull_request"

    man = jload(MANIFEST)
    win = man.get("window") or {}
    w_from = win.get("from") or ""
    w_to = win.get("to") or ""
    notes.append(f"manifest window {w_from}..{w_to} (written_on {man.get('written_on')})")

    # ---- provenance: every block exists and carries its source + stamp ----
    for block in REQUIRED_BLOCKS:
        info = man.get(block) or {}
        rel = info.get("path") or ""
        path = os.path.join(ROOT, rel) if rel else ""
        if not rel or not os.path.exists(path):
            failures.append(f"provenance: manifest block '{block}' names a missing file ({rel or 'none'})")
            continue
        if not info.get("source_url"):
            failures.append(f"provenance: manifest block '{block}' has no source_url")
        if not (info.get("retrieved_stamp") or info.get("captured_by")
                or info.get("provenance")):
            failures.append(f"provenance: manifest block '{block}' has no retrieval stamp")
        if not parses(path):
            failures.append(f"provenance: manifest block '{block}' file does not parse")

    # ---- provenance: the results log ends the day before the window ----
    log_rel = (man.get("results_log") or {}).get("path") or ""
    log_path = os.path.join(ROOT, log_rel)
    last_date = None
    n_rows = 0
    if os.path.exists(log_path):
        with open(log_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        n_rows = len(rows)
        if rows:
            last_date = max(r["date"] for r in rows)
    day_before = (datetime.date.fromisoformat(w_from) - datetime.timedelta(days=1)).isoformat() \
        if w_from else None
    if last_date is None:
        failures.append("freshness: the results log is empty or missing")
    elif w_from and last_date < day_before:
        failures.append(f"freshness: the results log ends {last_date}, before {day_before} "
                        f"(the day before the priced window opens)")
    else:
        notes.append(f"results log: {n_rows} games, last {last_date}")

    # ---- freshness: the window must start today on an enforcing run ------
    t = today().isoformat()
    if w_from != t:
        msg = (f"freshness: the manifest window starts {w_from}, not today ({t}); "
               f"the rolling slate has moved and the captures are stale")
        if enforce:
            failures.append(msg)
        else:
            warnings.append(msg)
    else:
        notes.append(f"freshness: the manifest window starts today ({t})")

    # ---- freshness: the newest injury report covers the window's first date
    inj_rel = (man.get("injuries") or {}).get("path") or ""
    if os.path.exists(os.path.join(ROOT, inj_rel)):
        inj = jload(os.path.join(ROOT, inj_rel))
        stamps = {r.get("game_date") for r in inj.get("rows", [])}
        first_us = "/".join([w_from[5:7], w_from[8:10], w_from[0:4]]) if w_from else ""
        if first_us and first_us not in stamps:
            failures.append(f"freshness: the newest injury report ({inj.get('report_stamp')}) "
                            f"has no rows for the window's first date {first_us}")
        else:
            notes.append(f"injury overlay: {inj.get('report_stamp')} covers {first_us} "
                         f"({inj.get('count')} rows)")

    # ---- coverage: every window date on the slate; availability for all sides
    slate_rel = (man.get("slate") or {}).get("path") or ""
    if os.path.exists(os.path.join(ROOT, slate_rel)):
        slate = jload(os.path.join(ROOT, slate_rel))
        dates = {g["date"] for g in slate.get("games", [])}
        want = set()
        if w_from and w_to:
            d = datetime.date.fromisoformat(w_from)
            end = datetime.date.fromisoformat(w_to)
            while d <= end:
                want.add(d.isoformat())
                d += datetime.timedelta(days=1)
        missing = sorted(want - dates)
        if missing:
            failures.append(f"coverage: the slate is missing window dates {missing}")
        else:
            notes.append(f"coverage: slate covers all {len(want)} window dates "
                         f"({len(slate.get('games', []))} games)")

    # ---- availability register agrees with the manifest's injury file ------
    av_rel = ((man.get("availability") or {}).get("path")
              or "data/app/report_availability.json")
    if os.path.exists(os.path.join(ROOT, av_rel)) and os.path.exists(os.path.join(ROOT, inj_rel)):
        av = jload(os.path.join(ROOT, av_rel))
        inj = jload(os.path.join(ROOT, inj_rel))
        if av.get("as_of_report") != inj.get("report_stamp"):
            failures.append("coverage: report_availability.json was built against "
                            f"'{av.get('as_of_report')}' but the manifest's injury file is "
                            f"'{inj.get('report_stamp')}' -- regenerate the register")
        else:
            notes.append(f"availability register as of {av.get('as_of_report')}")
        allowed = {"FILED", "DUE_AND_NOT_FILED", "NOT_YET_DUE",
                   "NO_OFFICIAL_REPORT_COVERS_THIS_DATE",
                   "REPORT_COVERS_DATE_TEAM_NOT_LISTED"}
        for r in av.get("rows", []):
            if r.get("state") not in allowed:
                failures.append(f"coverage: availability row for {r.get('team')} on "
                                f"{r.get('date')} has unknown state {r.get('state')!r}")
                break

    # ---- report ----------------------------------------------------------
    print("Rolling-slate freshness and provenance gate "
          f"(event={event}, enforce={enforce})")
    for n in notes:
        print(f"  ok      {n}")
    for w in warnings:
        print(f"  warn    {w}")
    for f in failures:
        print(f"  FAIL    {f}")
    if failures and enforce:
        print("Rebuild refused: refresh the official captures and repoint "
              "data/app/snapshot_manifest.json before publishing.")
        return 1
    if failures:
        print("PR run: failures reported but not enforced (the branch carries the "
              "snapshot it was cut with). They will be enforced on merge.")
        return 0
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
