#!/usr/bin/env python3
"""Scheduled official-data capture, preflight, and gated publication.

The GitHub runner fetches the official injury index/newest PDF, the NBA selected-date game
pages for the previous two result dates and the four-date rolling slate (today through +3),
official standings and three team-stat pages. Each response is kept under
``data/app/refresh/<stamp>/`` with a per-response UTC retrieval time, run stamp, byte count,
SHA-256, and source URL in ``manifest.json``.

Before any published file is promoted, ``refresh_preflight.py`` validates that exact capture:
source integrity, the newest indexed injury PDF, all four schedule pages, a complete daily
schedule feed, and current-run parsed 30-team standings and statistics. It then runs the
existing committed-snapshot gate to a report inside the capture directory (not data/live).
Only after both gate sets pass may the slate be promoted and the rebuild chain start. The
workflow archives raw captures/gate reports separately; it commits publication outputs only
when the entire fetch, gate, rebuild, and test chain succeeds.

The standings/team-stat parser contract is intentionally fail-closed. The saved NBA stats
page shells do not themselves prove 30 current team rows; no old snapshot is silently reused.
Dates are Eastern, and injury reports are ordered by their actual 12-hour clock time.

Usage: python3 scripts/refresh_official.py [--dry-run] [--stamp 2026-11-16T14-00-00Z]
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

import rolling_promote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
ET = ZoneInfo("America/New_York")

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
STANDINGS_PAGE = "https://www.nba.com/standings"
RETRIES = 3
RETRY_SLEEP_S = 5

REPORT_RE = re.compile(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf")
RUN_STAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T(?:\d{2}-\d{2}(?:-\d{2})?|\d{2}:\d{2}(?::\d{2})?)Z$"
)


def valid_run_stamp(value):
    """Accept only safe, timestamp-shaped run-directory names."""
    if not isinstance(value, str) or not RUN_STAMP_RE.fullmatch(value):
        return False
    formats = ("%Y-%m-%dT%H-%MZ", "%Y-%m-%dT%H-%M-%SZ",
               "%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ")
    for fmt in formats:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def report_time(y, hh, mm, ap):
    """Real clock time of an injury-report filename part set (12-hour clock aware).

    12:00 AM is midnight (hour 0), 12:xx PM is noon (hour 12), 1:00 PM is 13:00.
    """
    hour_12, minute = int(hh), int(mm)
    if not 1 <= hour_12 <= 12 or not 0 <= minute <= 59 or ap not in {"AM", "PM"}:
        raise ValueError("invalid report time in official index")
    hour = hour_12 % 12 + (12 if ap == "PM" else 0)
    return datetime.strptime(f"{y} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")


def newest_report(index_html):
    """Return (sort_key, y, hh, mm, ap) of the newest report link on the official index.

    Ordering is by real time. The previous code sorted the raw string tuples, which put
    "12_00AM" after "01_00PM" on the same date. Returns None if the index lists no reports.
    """
    found = set(REPORT_RE.findall(index_html))
    if not found:
        return None
    try:
        best = max(found, key=lambda t: report_time(*t))
    except ValueError:
        # A malformed report link makes the index's chronology ambiguous; do not fall back
        # to an older report that happens to parse.
        return None
    return best


def et_today(now_utc):
    return now_utc.astimezone(ET).date()


def schedule_fetch_plan(today_et):
    """Return the two prior result days and all four required rolling slate days."""
    return [((today_et + timedelta(days=off)).isoformat(), 0 <= off <= 3)
            for off in range(-2, 4)]


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
                if not data:
                    raise ValueError("empty response body is not a valid capture")
                with open(dest, "wb") as fh:
                    fh.write(data)
                retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                self.artifacts.append({
                    "url": url, "retrieved_utc": retrieved, "run_stamp": self.stamp,
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
    stamp = args.stamp or now.strftime("%Y-%m-%dT%H-%M-%SZ")
    if not valid_run_stamp(stamp):
        print("invalid refresh stamp; expected a safe UTC timestamp such as "
              "2026-11-16T14-00-00Z", file=sys.stderr)
        return 2
    out_dir = os.path.join(APP, "refresh", stamp)
    try:
        # Captures are immutable: retries/reruns must not silently overwrite an older
        # manifest or replace files that a previous gate report already attested.
        os.makedirs(out_dir)
    except FileExistsError:
        print(f"refresh capture already exists; refusing to overwrite: {out_dir}",
              file=sys.stderr)
        return 2
    f = Fetcher(stamp)
    today_et = et_today(now)
    manifest = {"stamp": stamp, "started_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "finished_utc": None, "today_et": today_et.isoformat(),
                "newest_injury_report": None, "artifacts": f.artifacts,
                "errors": f.errors, "gamebooks": 0}

    def finish(code):
        manifest["finished_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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

    # 2. schedule/results pages: today..today+3 are all required; the previous two
    # Eastern game days are optional inputs for verified-result discovery only.
    for d, required in schedule_fetch_plan(today_et):
        f.get(GAMES + d, os.path.join(out_dir, f"games_{d}.html"),
              required=required, label=f"games page {d}")

    # 3. refresh the official standings page and all three official team-stat pages.
    # The raw HTML is provenance evidence; the rebuild gate separately requires parsed
    # current-run inputs tied to these exact artifact hashes.
    f.get(STANDINGS_PAGE, os.path.join(out_dir, "standings.html"), required=True,
          label="official standings page")
    for i, url in enumerate(TEAM_PAGES):
        f.get(url, os.path.join(out_dir, f"teams_{i}.html"), required=True,
              label=f"team stats page {i}")

    # 3b. Parse the structured NBA selected-date feed. The official per-day calendar count
    # must match the card rows for every date; incidental recap/game links are ignored.
    schedule_pages = {}
    for offset in range(4):
        day = (today_et + timedelta(days=offset)).isoformat()
        page = os.path.join(out_dir, f"games_{day}.html")
        if os.path.isfile(page):
            with open(page, encoding="utf-8", errors="replace") as handle:
                schedule_pages[day] = handle.read()
    slate_result = rolling_promote.build_rolling_slate(
        schedule_pages, today_et, stamp=stamp, games_url_prefix=GAMES, days=4)
    if slate_result["slate"] is not None:
        staged_path = os.path.join(out_dir, "promoted_slate.json")
        rolling_promote.write_json_atomic(staged_path, slate_result["slate"])
        print(f"complete slate staged: {slate_result['slate']['count']} games -> "
              f"data/app/refresh/{stamp}/promoted_slate.json; daily counts: "
              f"{slate_result['daily_counts']}")
    else:
        print("rolling slate not staged; official schedule completeness failed: "
              + "; ".join(slate_result["errors"][:8]), file=sys.stderr)

    # 4. game books for every finished game found on the two previous Eastern game days
    gb = 0
    for off in (-2, -1):
        day = today_et + timedelta(days=off)
        page = os.path.join(out_dir, f"games_{day.isoformat()}.html")
        if not os.path.exists(page):
            continue
        with open(page, encoding="utf-8", errors="replace") as handle:
            html = handle.read()
        for a, h in sorted(set(re.findall(r"boxscore/([a-z]{3})-vs-([a-z]{3})", html))):
            url = GAMEBOOK.format(d=day.strftime("%Y%m%d"), a=a.upper(), h=h.upper())
            dest = os.path.join(out_dir, f"{day.strftime('%Y%m%d')}_{a.upper()}{h.upper()}.pdf")
            if f.get(url, dest, required=False, label=f"game book {a.upper()}{h.upper()}") is not None:
                gb += 1
    manifest["gamebooks"] = gb
    finish(0)  # persist the complete manifest before the gates read it

    # 5. Gate the NEW capture first. freshness_gates.py alone is insufficient here: it
    # checks the last published data/live snapshot, not these files. This preflight verifies
    # each artifact's bytes/hash/source, the newest injury PDF vs the official index, all
    # four upcoming schedule dates, and current-run parsed standings/stat snapshots.
    preflight_report = os.path.join(out_dir, "provenance_gates.json")
    preflight = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "refresh_preflight.py"),
         "--stamp", stamp, "--json-out", preflight_report], cwd=ROOT)
    if preflight.returncode != 0:
        print("new-capture freshness/provenance gates FAILED — no slate promotion or rebuild",
              file=sys.stderr)
        return 1
    if not os.path.isfile(preflight_report):
        print("new-capture gate returned success without writing its report — rebuild refused",
              file=sys.stderr)
        return 1

    # The committed-snapshot gate is still an additional check. Direct its report into the
    # run directory so even a failed check cannot overwrite data/live/freshness.json.
    published_gate_report = os.path.join(out_dir, "published_snapshot_gates.json")
    gate = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py"),
         "--json-out", published_gate_report], cwd=ROOT)
    if gate.returncode != 0:
        print("published-snapshot freshness gates FAILED — no promotion or rebuild", file=sys.stderr)
        return 1
    if not os.path.isfile(published_gate_report):
        print("published-snapshot gate returned success without its report — rebuild refused",
              file=sys.stderr)
        return 1

    if args.dry_run:
        # fetch + both gate reports only; no public snapshot, model, page, ledger or commit
        return 0

    # 6. Promote only after both gate sets pass. The staged slate stays inside the immutable
    # refresh directory if either gate fails.
    staged_slate = os.path.join(out_dir, "promoted_slate.json")
    if not os.path.isfile(staged_slate):
        print("fresh gate passed but staged slate is missing — rebuild refused", file=sys.stderr)
        return 1
    rolling_promote.promote_slate(
        staged_slate, os.path.join(APP, "official_slate_current.json"))

    # 7. rebuild chain (offline scripts on the refreshed captures)
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
