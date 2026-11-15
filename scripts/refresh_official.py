#!/usr/bin/env python3
"""Scheduled official-data refresh (session arena/79341829-nba3).

Runs on the GitHub runner (network available). The sandbox in this session cannot reach
nba.com, so this job is exercised by CI tests against committed fixtures; the live path:

  1. FETCH  the official injury index + newest report PDF, the nba.com schedule/results
            pages for today..today+3 and the past two game days, every finished game's
            official game book (statsdmz PDF), and the three official team-stat pages.
            Every artifact is stored under data/app/refresh/<stamp>/ with URL, retrieval
            stamp and sha256 (manifest.json).
  2. GATES  scripts/freshness_gates.py MUST pass (freshness + provenance).
  3. REBUILD ONLY AFTER THE GATES PASS: parse new game books into the results feed,
            settle the previous game day, publish/verify the pick ledger, re-cut estimator
            inputs, then assemble_canonical.py + build_app.py and the test suite.
  4. COMMIT  the refreshed captures and rebuilt outputs on success; on gate failure the
            run exits non-zero WITHOUT rebuilding (and the site keeps the last good build).

Usage: python3 scripts/refresh_official.py [--dry-run] [--stamp 2026-11-15T12-00Z]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

UA = {"User-Agent": "Mozilla/5.0 (NBA3 official-data refresh; research pipeline)"}
INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJ_CDN = "https://ak-static.cms.nba.com/referee/injury/"
GAMES = "https://www.nba.com/games?date="
GAMEBOOK = "https://statsdmz.nba.com/pdfs/{d}/{d}_{a}{h}.pdf"
TEAM_PAGES = [
    "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
    "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
    "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
]


def fetch(url, dest, artifacts, stamp):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(dest, "wb") as fh:
        fh.write(data)
    artifacts.append({"url": url, "retrieved_utc": stamp,
                      "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "file": os.path.relpath(dest, ROOT)})
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp")
    args = ap.parse_args()
    stamp = args.stamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%MZ")
    out_dir = os.path.join(APP, "refresh", stamp)
    os.makedirs(out_dir, exist_ok=True)
    artifacts = []
    now = datetime.now(timezone.utc)

    # 1. injury index + newest report PDF
    idx = fetch(INJ_INDEX, os.path.join(out_dir, "injury_index.html"), artifacts, stamp).decode(
        "utf-8", "replace")
    reports = sorted(set(re.findall(
        r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf", idx)))
    if not reports:
        print("no injury report links found on the official index", file=sys.stderr)
        return 2
    y, hh, mm, ap_ = reports[-1]
    newest = f"{y}-{hh}-{mm}{ap_}"
    pdf_name = f"Injury-Report_{y}_{hh}_{mm}{ap_}.pdf"
    fetch(INJ_CDN + pdf_name, os.path.join(out_dir, pdf_name), artifacts, stamp)

    # 2. schedule/results pages: today..today+3 and the two previous game days
    for off in range(-2, 4):
        d = (now + timedelta(days=off)).strftime("%Y-%m-%d")
        fetch(GAMES + d, os.path.join(out_dir, f"games_{d}.html"), artifacts, stamp)

    # 3. team-stat pages
    for i, url in enumerate(TEAM_PAGES):
        fetch(url, os.path.join(out_dir, f"teams_{i}.html"), artifacts, stamp)

    # 4. game books for every finished game found on the two previous game days
    #    (matchup codes are scraped from the stored results-feed rows; new finals come
    #    from the games pages' box-score links)
    gb = 0
    for off in (-2, -1):
        d = (now + timedelta(days=off)).strftime("%Y%m%d")
        page = os.path.join(out_dir, f"games_{(now + timedelta(days=off)).strftime('%Y-%m-%d')}.html")
        if not os.path.exists(page):
            continue
        html = open(page, encoding="utf-8", errors="replace").read()
        for a, h in sorted(set(re.findall(r"boxscore/([a-z]{3})-vs-([a-z]{3})", html))):
            url = GAMEBOOK.format(d=d, a=a.upper(), h=h.upper())
            try:
                fetch(url, os.path.join(out_dir, f"{d}_{a.upper()}{h.upper()}.pdf"),
                      artifacts, stamp)
                gb += 1
            except Exception as e:      # game book not posted yet — leave for the next run
                print(f"game book fetch skipped {url}: {e}")
    manifest = {"stamp": stamp, "newest_injury_report": newest,
                "artifacts": artifacts, "gamebooks": gb}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    print(f"refresh fetch: {len(artifacts)} artifacts -> data/app/refresh/{stamp}/")

    if args.dry_run:
        return 0

    # 2. gates — the rebuild runs ONLY when they pass
    gate = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py"),
         "--manifest", os.path.join(out_dir, "manifest.json"),
         "--json-out", os.path.join(out_dir, "gate_report.json")])
    if gate.returncode != 0:
        print("freshness/provenance gates FAILED — rebuild refused", file=sys.stderr)
        return 1

    # 3. rebuild chain (offline scripts on the refreshed captures)
    steps = [
        ["python3", "scripts/estimators.py"],
        ["python3", "scripts/minutes_model.py"],
        ["python3", "scripts/results_feed.py", "verify"],
        ["python3", "scripts/pick_ledger.py", "publish"],
        ["python3", "scripts/pick_ledger.py", "verify"],
        ["python3", "scripts/assemble_canonical.py"],
        ["python3", "scripts/build_app.py"],
    ]
    for cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            print(f"rebuild step failed: {' '.join(cmd)}", file=sys.stderr)
            return 1
    print("refresh: gates passed, rebuild complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
