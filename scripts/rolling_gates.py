#!/usr/bin/env python3
"""Rolling freshness + provenance gates (session arena/43d54bfe-nba3).

The rebuild runs ONLY after these gates pass. Every gate is evaluated from stored,
committed artifacts (data/app/refresh/<stamp>/manifest.json plus data/app/rolling/), so
tests and CI replay them offline. Dates roll with the manifest's own Eastern-day stamp —
nothing is hard-coded to a capture date.

  G1  provenance: every manifest artifact carries an https source URL, retrieval stamp,
      sha256 and byte count; the required source classes are present (injury index,
      newest injury PDF, at least one games page, the three team-stat pages)
  G2  injury freshness: the archived rolling report is exactly the newest filing the
      official index listed (manifest.newest_injury_report) and its rows parsed
  G3  schedule window: the promoted slate covers today..today+3 Eastern days
  G4  results: every fetched official game book is parsed into a verified row — quarter
      sums equal the printed final for both teams
  G5  completeness: every rolling results row has date, teams, finals and quarters

Usage: python3 scripts/rolling_gates.py --stamp <refresh stamp> [--json-out PATH]
Exit code 1 if any gate fails — the caller must then refuse the rebuild.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
REFRESH = os.path.join(APP, "refresh")
ROLLING = os.path.join(APP, "rolling")

REQUIRED_CLASSES = {
    "injury index": lambda url: "official.nba.com" in url and "injury-report" in url,
    "injury PDF": lambda url: "ak-static.cms.nba.com" in url and "Injury-Report_" in url,
    "games page": lambda url: "nba.com/games?date=" in url,
    "team stats": lambda url: "nba.com/stats/teams/" in url,
}


def evaluate(stamp: str, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    man_path = os.path.join(REFRESH, stamp, "manifest.json")
    report = {"stamp": stamp, "evaluated_utc": now.strftime("%Y-%m-%dT%H:%MZ"), "gates": []}

    def gate(gid, ok, detail, required=True):
        report["gates"].append({"id": gid, "pass": bool(ok), "required": required,
                                "detail": detail})
        return ok

    if not os.path.exists(man_path):
        gate("G1_provenance", False, f"no manifest at {man_path}")
        gate("G2_injury_current", False, "no manifest")
        gate("G3_slate_window", False, "no manifest")
        gate("G4_results_verified", False, "no manifest")
        gate("G5_row_completeness", False, "no manifest")
        report["pass"] = False
        return report

    man = json.load(open(man_path, encoding="utf-8"))
    artifacts = man.get("artifacts", [])

    # G1 — provenance + required source classes
    bad = [a.get("file", "?") for a in artifacts
           if not (str(a.get("url", "")).startswith("https://") and a.get("sha256")
                   and a.get("retrieved_utc") and a.get("bytes"))]
    classes = {c: any(fn(a.get("url", "")) for a in artifacts)
               for c, fn in REQUIRED_CLASSES.items()}
    team_pages = sum(1 for a in artifacts if REQUIRED_CLASSES["team stats"](a.get("url", "")))
    classes_ok = all(classes.values()) and team_pages >= 3
    gate("G1_provenance", not bad and classes_ok,
         f"{len(artifacts)} artifacts with https URL+sha256+stamp+bytes; classes present: "
         f"{classes} (team pages {team_pages}/3)"
         + (f"; missing provenance fields: {bad[:5]}" if bad else ""))

    # G2 — the archived rolling report is the official index's newest filing
    inj_ok = False
    inj_detail = "rolling injury capture missing"
    inj_index = os.path.join(ROLLING, "injuries", "archive_index.json")
    newest = man.get("newest_injury_report")
    if newest and os.path.exists(inj_index):
        idx = json.load(open(inj_index, encoding="utf-8"))
        names = {e["report_name"] for e in idx.get("reports", [])}
        want = f"Injury-Report_{newest}.pdf"
        newest_entry = next((e for e in idx["reports"] if e["report_name"] == want), None)
        if newest_entry:
            inj_ok = newest_entry["sha256"] and newest_entry["text_extracted"] \
                and newest_entry["n_parsed"] > 0
            inj_detail = (f"archived {want} (sha256 {newest_entry['sha256'][:12]}…, "
                          f"{newest_entry['n_parsed']} rows parsed of "
                          f"{newest_entry['n_rows']} report rows)")
        else:
            inj_detail = f"{want} missing from the rolling archive ({len(names)} reports)"
    gate("G2_injury_current", inj_ok, inj_detail)

    # G3 — promoted slate covers today..today+3 Eastern
    today = man.get("today_et")
    slate_ok = False
    slate_detail = "promoted slate missing"
    slate_path = os.path.join(APP, "official_slate_current.json")
    if today and os.path.exists(slate_path):
        slate = json.load(open(slate_path, encoding="utf-8"))
        d0 = datetime.strptime(today, "%Y-%m-%d").date()
        want = [(d0 + timedelta(days=i)).isoformat() for i in range(4)]
        dates = {g["date"] for g in slate.get("games", [])}
        missing = [d for d in want if d not in dates]
        slate_ok = not missing and len(dates) >= 4
        slate_detail = (f"slate window {slate.get('window', {}).get('from')}.."
                        f"{slate.get('window', {}).get('to')} with {slate.get('count')} games; "
                        f"required {want[0]}..{want[-1]}"
                        + (f"; missing days: {missing}" if missing else ""))
    gate("G3_slate_window", slate_ok, slate_detail)

    # G4 — every fetched game book parsed into a verified row
    res_path = os.path.join(ROLLING, "results.json")
    gb_ok = False
    gb_detail = "rolling results capture missing"
    if os.path.exists(res_path):
        res = json.load(open(res_path, encoding="utf-8"))
        fetched_books = [a for a in artifacts
                         if os.path.basename(a.get("file", "")).startswith("20")
                         and a.get("file", "").endswith(".pdf")
                         and "statsdmz" in a.get("url", "")]
        unparsed = res.get("unparsed", [])
        verified = res.get("settled_count", 0)
        bad_q = [g for g in res.get("games", []) if not g.get("quarter_sums_match_final")]
        gb_ok = len(fetched_books) == (len(fetched_books) - len(unparsed)) and not bad_q \
            and verified == len(fetched_books) and verified > 0
        gb_detail = (f"{len(fetched_books)} official game books fetched, {verified} verified "
                     f"(quarter sums == final), {len(unparsed)} unparseable, "
                     f"{len(bad_q)} quarter mismatches")
    gate("G4_results_verified", gb_ok, gb_detail)

    # G5 — row completeness
    comp_ok = False
    comp_detail = "rolling results capture missing"
    if os.path.exists(res_path):
        res = json.load(open(res_path, encoding="utf-8"))
        bad = []
        for g in res.get("games", []):
            for k in ("date", "away", "home", "away_pts", "home_pts",
                      "away_q", "home_q", "source_url", "settlement_stamp"):
                v = g.get(k)
                if v in (None, "", []):
                    bad.append(f"{g.get('date')} {g.get('away')}@{g.get('home')} missing {k}")
        comp_ok = not bad and res.get("count", 0) > 0
        comp_detail = (f"{res.get('count')} rows complete" if not bad
                       else "; ".join(bad[:5]))
    gate("G5_row_completeness", comp_ok, comp_detail)

    report["pass"] = all(g["pass"] for g in report["gates"] if g["required"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--json-out")
    args = ap.parse_args()
    rep = evaluate(args.stamp)
    for g in rep["gates"]:
        print(f"[{'PASS' if g['pass'] else 'FAIL'}] {g['id']}: {g['detail']}")
    print("ROLLING GATES " + ("PASS — rebuild may run" if rep["pass"]
                             else "FAIL — rebuild refused"))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
            fh.write("\n")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
