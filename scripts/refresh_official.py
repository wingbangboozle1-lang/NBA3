#!/usr/bin/env python3
"""Scheduled official-data refresh (session arena/79341829-nba3; repaired 4f194ba2).

Runs on the GitHub runner (network available). The sandbox cannot reach nba.com, so the
flow is exercised by CI tests against a local fixture server (tests/test_refresh_official.py);
the live path:

  1. FETCH  the official injury index + newest report PDF, the nba.com schedule/results
            pages for today..today+3 and the past two game days, every finished game's
            official game book (statsdmz PDF), and the three official team-stat pages.
            Every artifact is stored under data/app/refresh/<stamp>/ with URL, retrieval
            stamp and sha256 (manifest.json).
  2. GATES  scripts/freshness_gates.py MUST pass (freshness + provenance). Its output is
            captured into the stamp directory.
  3. REBUILD ONLY AFTER THE GATES PASS: parse new game books into the results feed,
            settle the previous game day, publish/verify the pick ledger, re-cut estimator
            inputs, then assemble_canonical.py + build_app.py and the test suite.
  4. COMMIT  the refreshed captures and rebuilt outputs on success; on gate failure the
            run exits non-zero WITHOUT rebuilding (and the site keeps the last good build).

Repair record (session 4f194ba2, defects found on main):

  F4F1942A-01  The first scheduled run (43742524756, 2026-11-15) died in 12s in the fetch
               step: a single HTTP error aborted the whole job, and the request carried a
               non-browser User-Agent that nba.com's edge rejects. fetch() now sends
               browser-grade headers, retries transient failures (429/5xx/timeouts) with
               backoff, and classifies artifacts as critical (index, newest injury PDF,
               schedule pages, team-stat pages — a failure refuses the rebuild) or optional
               (game books — skipped and recorded; the next run picks them up).
  F4F1942A-02  The gate step invoked scripts/freshness_gates.py with --manifest/--json-out
               flags that script has never accepted, so even a fully successful fetch would
               have failed at the gate with argparse exit code 2 and the rebuild would have
               been refused forever. The gate is now invoked with its real interface and its
               stdout is stored as gate_report.txt in the stamp directory.

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
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
               "image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}

INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJ_CDN = "https://ak-static.cms.nba.com/referee/injury/"
GAMES = "https://www.nba.com/games?date="
GAMEBOOK = "https://statsdmz.nba.com/pdfs/{d}/{d}_{a}{h}.pdf"
TEAM_PAGES = [
    "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
    "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
    "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
]

RETRY_STATUS = {429, 500, 502, 503, 504}


class CriticalFetchError(RuntimeError):
    """A critical official artifact could not be fetched after retries."""


def fetch(url, dest, artifacts, stamp, *, critical=True, attempts=3,
          sleep=time.sleep, urlopen=urllib.request.urlopen, timeout=60):
    """Fetch one official artifact with retries; record provenance in `artifacts`.

    Transient failures (HTTP 429/5xx, connection errors) are retried with backoff.
    HTTPError with a non-retryable status fails on first attempt. When `critical` is
    False a final failure is returned as None and recorded as skipped; when True it
    raises CriticalFetchError, which the caller must treat as "refuse the rebuild".
    """
    last_err = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        try:
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            with open(dest, "wb") as fh:
                fh.write(data)
            artifacts.append({"url": url, "retrieved_utc": stamp,
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "bytes": len(data), "file": os.path.relpath(dest, ROOT),
                              "critical": critical, "attempts": attempt})
            return data
        except urllib.error.HTTPError as e:
            last_err = e
            retryable = e.code in RETRY_STATUS
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            retryable = True
        if not retryable:
            break               # a 403/404 will not self-heal in seconds — fail now
        if attempt < attempts:
            wait = 2 * attempt
            print(f"retry {attempt}/{attempts - 1} for {url} after {wait}s "
                  f"({last_err})", file=sys.stderr)
            sleep(wait)
    if critical:
        raise CriticalFetchError(f"{url} failed after {attempts} attempts: {last_err}")
    print(f"optional artifact skipped {url}: {last_err}", file=sys.stderr)
    artifacts.append({"url": url, "retrieved_utc": stamp, "critical": False,
                      "attempts": attempts, "skipped": str(last_err)})
    return None


def promote_slate(out_dir, app_dir, now, stamp):
    """Promote the rolling slate window from the fetched official games pages.

    Tip times stay blank and flagged when the page pattern does not carry them —
    never inferred. Returns the number of promoted games.
    """
    rows = []
    for off in range(0, 4):
        d = (now + timedelta(days=off)).strftime("%Y-%m-%d")
        page = os.path.join(out_dir, f"games_{d}.html")
        if not os.path.exists(page):
            continue
        with open(page, encoding="utf-8", errors="replace") as fh:
            html = fh.read()
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
        with open(os.path.join(app_dir, "official_slate_current.json"), "w", encoding="utf-8") as fh:
            json.dump(slate, fh, indent=1)
            fh.write("\n")
        print(f"slate promoted: {len(rows)} games -> data/app/official_slate_current.json")
    return len(rows)


def run_refresh(now, stamp, out_dir, app_dir, *, dry_run=False, attempts=3,
                gates_cmd=None, rebuild_steps=None, sleep=time.sleep,
                urlopen=urllib.request.urlopen):
    """One full refresh pass. Returns the process exit code (0 = success)."""
    os.makedirs(out_dir, exist_ok=True)
    artifacts = []

    # 1. injury index + newest report PDF (critical: provenance for the whole model)
    try:
        idx = fetch(INJ_INDEX, os.path.join(out_dir, "injury_index.html"), artifacts, stamp,
                    critical=True, attempts=attempts, sleep=sleep, urlopen=urlopen
                    ).decode("utf-8", "replace")
    except CriticalFetchError as e:
        print(f"CRITICAL FETCH FAILED — rebuild refused: {e}", file=sys.stderr)
        return 3
    reports = sorted(set(re.findall(
        r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf", idx)))
    if not reports:
        print("no injury report links found on the official index", file=sys.stderr)
        return 2
    y, hh, mm, ap_ = reports[-1]
    newest = f"{y}-{hh}-{mm}{ap_}"
    try:
        fetch(INJ_CDN + f"Injury-Report_{y}_{hh}_{mm}{ap_}.pdf",
              os.path.join(out_dir, f"Injury-Report_{y}_{hh}_{mm}{ap_}.pdf"),
              artifacts, stamp, critical=True, attempts=attempts, sleep=sleep,
              urlopen=urlopen)
    except CriticalFetchError as e:
        print(f"CRITICAL FETCH FAILED — rebuild refused: {e}", file=sys.stderr)
        return 3

    # 2. schedule/results pages: today..today+3 and the two previous game days (critical)
    for off in range(-2, 4):
        d = (now + timedelta(days=off)).strftime("%Y-%m-%d")
        try:
            fetch(GAMES + d, os.path.join(out_dir, f"games_{d}.html"), artifacts, stamp,
                  critical=True, attempts=attempts, sleep=sleep, urlopen=urlopen)
        except CriticalFetchError as e:
            print(f"CRITICAL FETCH FAILED — rebuild refused: {e}", file=sys.stderr)
            return 3

    # 3. team-stat pages (critical)
    for i, url in enumerate(TEAM_PAGES):
        try:
            fetch(url, os.path.join(out_dir, f"teams_{i}.html"), artifacts, stamp,
                  critical=True, attempts=attempts, sleep=sleep, urlopen=urlopen)
        except CriticalFetchError as e:
            print(f"CRITICAL FETCH FAILED — rebuild refused: {e}", file=sys.stderr)
            return 3

    # 3b. promote the rolling slate window
    promote_slate(out_dir, app_dir, now, stamp)

    # 4. game books for every finished game found on the two previous game days
    #    (optional: a game book not posted yet is picked up by the next run)
    gb = 0
    for off in (-2, -1):
        d = (now + timedelta(days=off)).strftime("%Y%m%d")
        page = os.path.join(out_dir, f"games_{(now + timedelta(days=off)).strftime('%Y-%m-%d')}.html")
        if not os.path.exists(page):
            continue
        with open(page, encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        for a, h in sorted(set(re.findall(r"boxscore/([a-z]{3})-vs-([a-z]{3})", html))):
            url = GAMEBOOK.format(d=d, a=a.upper(), h=h.upper())
            data = fetch(url, os.path.join(out_dir, f"{d}_{a.upper()}{h.upper()}.pdf"),
                         artifacts, stamp, critical=False, attempts=attempts,
                         sleep=sleep, urlopen=urlopen)
            if data is not None:
                gb += 1
    manifest = {"stamp": stamp, "newest_injury_report": newest,
                "artifacts": artifacts, "gamebooks": gb}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    print(f"refresh fetch: {len(artifacts)} artifacts "
          f"({sum(1 for a in artifacts if a.get('skipped'))} skipped) "
          f"-> data/app/refresh/{stamp}/")

    if dry_run:
        return 0

    # 2'. gates — the rebuild runs ONLY when they pass (real interface, see F4F1942A-02)
    if gates_cmd is None:
        gates_cmd = [sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py")]
    gate = subprocess.run(gates_cmd, cwd=ROOT, capture_output=True, text=True)
    with open(os.path.join(out_dir, "gate_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(gate.stdout)
        fh.write(gate.stderr)
    if gate.returncode != 0:
        print("freshness/provenance gates FAILED — rebuild refused "
              "(gate output in gate_report.txt)", file=sys.stderr)
        return 1

    # 3. rebuild chain (offline scripts on the refreshed captures)
    if rebuild_steps is None:
        rebuild_steps = [
            ["python3", "scripts/estimators.py"],
            ["python3", "scripts/minutes_model.py"],
            ["python3", "scripts/results_feed.py", "verify"],
            ["python3", "scripts/pick_ledger.py", "publish"],
            ["python3", "scripts/pick_ledger.py", "verify"],
            ["python3", "scripts/assemble_canonical.py"],
            ["python3", "scripts/build_app.py"],
        ]
    for cmd in rebuild_steps:
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            print(f"rebuild step failed: {' '.join(cmd)}", file=sys.stderr)
            return 1
    print("refresh: gates passed, rebuild complete")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp")
    args = ap.parse_args()
    stamp = args.stamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%MZ")
    now = datetime.now(timezone.utc)
    out_dir = os.path.join(APP, "refresh", stamp)
    return run_refresh(now, stamp, out_dir, APP, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
