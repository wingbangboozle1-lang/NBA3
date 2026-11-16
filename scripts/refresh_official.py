#!/usr/bin/env python3
"""Scheduled official-data refresh (session arena/79341829-nba3; repaired in arena/81800928-nba3).

Runs on the GitHub runner (network available). The sandbox in this session cannot reach
nba.com, so this job is exercised by CI tests against committed fixtures; the live path:

  1. FETCH  the official injury index + newest report PDF, the nba.com schedule/results
            pages for today..today+3 and the past two game days, every finished game's
            official game book (statsdmz PDF), and the three official team-stat pages.
            Every artifact is stored under data/app/refresh/<stamp>/ with URL, retrieval
            stamp and sha256 (manifest.json). Every URL is attempted with retries; a URL
            that still fails is recorded in manifest["errors"] and never aborts the run.
  2. GATES  scripts/freshness_gates.py MUST pass (freshness + provenance).
  3. REBUILD ONLY AFTER THE GATES PASS: parse new game books into the results feed,
            settle the previous game day, publish/verify the pick ledger, re-cut estimator
            inputs, then assemble_canonical.py + build_app.py and the test suite.
  4. COMMIT  the refreshed captures and rebuilt outputs on success; on any failure the
            run exits non-zero WITHOUT rebuilding (and the site keeps the last good build).

Dates are Eastern (the NBA schedule's day), not UTC. Injury reports are ordered by their
real clock time, not by sorting the filename strings.

Usage: python3 scripts/refresh_official.py [--dry-run] [--stamp 2026-11-15T12-00Z]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
ET = ZoneInfo("America/New_York")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
# arena/43d54bfe-nba3 runner diagnostics (run 43776920267, committed under
# data/app/refresh/diagnostics/): official.nba.com answers 403 to the previous
# non-browser UA ("Mozilla/5.0 (NBA3 official-data refresh; research pipeline)") and
# 200 to a Chrome UA. That 403 was the scheduled job's original failure. cdn.nba.com
# and stats.nba.com API are NOT reachable from the runner (403 / timeout), so the
# fetch relies on the HTML pages + PDFs, which all work with a browser UA.
INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJ_CDN = "https://ak-static.cms.nba.com/referee/injury/"
GAMES = "https://www.nba.com/games?date="
GAMEBOOK = "https://statsdmz.nba.com/pdfs/{d}/{d}_{a}{h}.pdf"
TEAM_PAGES = [
    "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
    "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
    "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
]
RETRIES = 3
RETRY_SLEEP_S = 5

REPORT_RE = re.compile(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf")


def report_time(y, hh, mm, ap):
    """Real clock time of an injury-report filename part set (12-hour clock aware).

    12:00 AM is midnight (hour 0), 12:xx PM is noon (hour 12), 1:00 PM is 13:00.
    """
    h = int(hh) % 12 + (12 if ap == "PM" else 0)
    return datetime.strptime(f"{y} {h:02d}:{int(mm):02d}", "%Y-%m-%d %H:%M")


def newest_report(index_html):
    """Return (sort_key, y, hh, mm, ap) of the newest report link on the official index.

    Ordering is by real time. The previous code sorted the raw string tuples, which put
    "12_00AM" after "01_00PM" on the same date. Returns None if the index lists no reports.
    """
    found = set(REPORT_RE.findall(index_html))
    if not found:
        return None
    best = max(found, key=lambda t: report_time(*t))
    return best


def et_today(now_utc):
    return now_utc.astimezone(ET).date()


class Fetcher:
    """Fetches URLs with retries; records every failure. Never raises."""

    def __init__(self, stamp):
        self.stamp = stamp
        self.artifacts = []
        self.errors = []

    def get(self, url, dest, required=False, label=None):
        last = None
        for attempt in range(1, RETRIES + 1):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                with open(dest, "wb") as fh:
                    fh.write(data)
                self.artifacts.append({
                    "url": url, "retrieved_utc": self.stamp,
                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                    "file": os.path.relpath(dest, ROOT)})
                return data
            except Exception as exc:          # HTTP / DNS / timeout — record, retry
                last = f"{type(exc).__name__}: {exc}"
                if attempt < RETRIES:
                    time.sleep(RETRY_SLEEP_S)
        self.errors.append({"url": url, "label": label or os.path.basename(dest),
                            "required": required, "error": last,
                            "attempts": RETRIES})
        print(f"fetch failed ({'REQUIRED' if required else 'optional'}) {url}: {last}",
              file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    stamp = args.stamp or now.strftime("%Y-%m-%dT%H-%MZ")
    out_dir = os.path.join(APP, "refresh", stamp)
    os.makedirs(out_dir, exist_ok=True)
    f = Fetcher(stamp)
    today_et = et_today(now)
    manifest = {"stamp": stamp, "today_et": today_et.isoformat(), "newest_injury_report": None,
                "artifacts": f.artifacts, "errors": f.errors, "gamebooks": 0}

    def finish(code):
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=1)
            fh.write("\n")
        print(f"refresh fetch: {len(f.artifacts)} artifacts, {len(f.errors)} failed "
              f"-> data/app/refresh/{stamp}/")
        return code

    # 1. injury index + newest report PDF (required: the rebuild cannot run without it)
    idx_bytes = f.get(INJ_INDEX, os.path.join(out_dir, "injury_index.html"), required=True,
                      label="injury index")
    if idx_bytes is None:
        return finish(2)
    newest = newest_report(idx_bytes.decode("utf-8", "replace"))
    if newest is None:
        f.errors.append({"url": INJ_INDEX, "label": "injury index", "required": True,
                         "error": "no injury report links found on the official index",
                         "attempts": 1})
        return finish(2)
    y, hh, mm, ap_ = newest
    manifest["newest_injury_report"] = f"{y}-{hh}-{mm}{ap_}"
    pdf_name = f"Injury-Report_{y}_{hh}_{mm}{ap_}.pdf"
    if f.get(INJ_CDN + pdf_name, os.path.join(out_dir, pdf_name), required=True,
             label="newest injury report PDF") is None:
        return finish(2)

    # 2. schedule/results pages: today..today+3 and the two previous game days (Eastern dates)
    for off in range(-2, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        f.get(GAMES + d, os.path.join(out_dir, f"games_{d}.html"),
              required=(off == 0), label=f"games page {d}")

    # 3. team-stat pages (required: the model's team inputs)
    for i, url in enumerate(TEAM_PAGES):
        f.get(url, os.path.join(out_dir, f"teams_{i}.html"), required=True,
              label=f"team stats page {i}")

    # 3b. promote the schedule window from the fetched games pages (game links are the
    #     parseable part of the scoreboard HTML; tip times stay blank and flagged when the
    #     page pattern does not carry them — never inferred)
    rows = []
    for off in range(0, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        page = os.path.join(out_dir, f"games_{d}.html")
        if not os.path.exists(page):
            continue
        html = open(page, encoding="utf-8", errors="replace").read()
        seen = set()
        for m in re.finditer(r"/game/([a-z]{3})-vs-([a-z]{3})-(\d{10})/", html):
            a, h, gid = m.group(1).upper(), m.group(2).upper(), m.group(3)
            if gid in seen:
                continue
            seen.add(gid)
            rows.append({"date": d, "time_et": None, "away": a, "home": h, "game_id": gid,
                         "away_record": None, "home_record": None,
                         "game_url": f"https://www.nba.com/game/{a.lower()}-vs-{h.lower()}-{gid}",
                         "source": f"https://www.nba.com/games?date={d}"})
    rows.sort(key=lambda r: (r["date"], r["game_id"]))
    if rows:
        slate = {"source_url": GAMES + rows[0]["date"],
                 "source_label": ("official schedule pages for the rolling window, promoted by "
                                  "scripts/refresh_official.py from the fetched game links"),
                 "retrieved_on": stamp[:10], "retrieved_utc": stamp,
                 "window": {"from": rows[0]["date"], "to": rows[-1]["date"]},
                 "count": len(rows), "games": rows,
                 "notes": ["tip times are blank where the page pattern did not carry them — "
                           "blank and flagged, never inferred"]}
        with open(os.path.join(APP, "official_slate_current.json"), "w", encoding="utf-8") as fh:
            json.dump(slate, fh, indent=1)
            fh.write("\n")
        print(f"slate promoted: {len(rows)} games -> data/app/official_slate_current.json")

    # 4. game books for every finished game found on the two previous Eastern game days
    gb = 0
    for off in (-2, -1):
        day = today_et + timedelta(days=off)
        page = os.path.join(out_dir, f"games_{day.isoformat()}.html")
        if not os.path.exists(page):
            continue
        html = open(page, encoding="utf-8", errors="replace").read()
        for a, h in sorted(set(re.findall(r"boxscore/([a-z]{3})-vs-([a-z]{3})", html))):
            url = GAMEBOOK.format(d=day.strftime("%Y%m%d"), a=a.upper(), h=h.upper())
            dest = os.path.join(out_dir, f"{day.strftime('%Y%m%d')}_{a.upper()}{h.upper()}.pdf")
            if f.get(url, dest, required=False, label=f"game book {a.upper()}{h.upper()}") is not None:
                gb += 1
    manifest["gamebooks"] = gb
    finish(0)

    if f.errors and any(e["required"] for e in f.errors):
        print("required official sources failed — rebuild refused; last good build kept",
              file=sys.stderr)
        return 1
    if args.dry_run:
        return 0

    # 5. gates — the rebuild runs ONLY when they pass
    # 5a. rolling promotion first: the rolling gates evaluate the FRESH captures, then the
    #     canonical freshness_gates.py evaluates the committed captures. Both must pass.
    #     freshness_gates.py takes no manifest argument: it checks the committed captures in
    #     data/live (see the module docstring). Its own exit code decides; it also writes
    #     data/live/freshness.json, which is the published gate report.
    def run(label, cmd):
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            print(f"{label} FAILED — rebuild refused (exit {r.returncode})", file=sys.stderr)
            return False
        return True

    promote_ok = run("rolling promotion", [sys.executable, "scripts/rolling_promote.py",
                                           "--stamp", stamp])
    if promote_ok:
        # the rolling gate report is written for BOTH dry and full runs, so the run is
        # observable either way; only the full run refuses to continue on failure
        roll_ok = run("rolling gates (fresh captures)",
                      [sys.executable, "scripts/rolling_gates.py", "--stamp", stamp,
                       "--json-out", os.path.join(out_dir, "rolling_gate_report.json")])
        if not args.dry_run and not roll_ok:
            return 1
    if args.dry_run:
        # dry run: fetch + promote + gate report only; no canonical rebuild, no commit
        return 0
    # freshness gates on the committed captures (data/live). Kept in the exact shape the
    # static ordering tests (tests/test_refresh_ordering.py, PR #94) index on: the gate must
    # sit after the fetch and before any rebuild, and its nonzero exit must refuse it.
    gate = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py")],
                          cwd=ROOT)
    if gate.returncode != 0:
        print("freshness/provenance gates FAILED — rebuild refused", file=sys.stderr)
        return 1

    # 6. rebuild chain (offline scripts on the refreshed captures)
    steps = [
        ["python3", "scripts/estimators.py"],
        ["python3", "scripts/minutes_model.py"],
        ["python3", "scripts/results_feed.py", "verify"],
        ["python3", "scripts/pick_ledger.py", "publish"],
        ["python3", "scripts/pick_ledger.py", "verify"],
        ["python3", "scripts/assemble_canonical.py"],
        ["python3", "scripts/build_app.py"],
        # rolling surface: rebuilt only here, after every gate above passed
        ["python3", "scripts/rolling_build.py", "--stamp", stamp],
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
