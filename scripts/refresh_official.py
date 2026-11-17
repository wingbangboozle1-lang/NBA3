#!/usr/bin/env python3
"""Scheduled official-data refresh (session arena/79341829-nba3; repaired in arena/81800928-nba3).

Runs on the GitHub runner (network available). The sandbox in this session cannot reach
nba.com, so this job is exercised by CI tests against committed fixtures; the live path:

  1. FETCH  the official injury index + newest report PDF, the nba.com schedule/results
            pages for today..today+3 and the past two game days, every finished game's
            official game book (statsdmz PDF), the three official team-stat pages and the
            official standings page. Every artifact is stored under data/app/refresh/<stamp>/ with URL, retrieval
            stamp and sha256 (manifest.json). Every URL is attempted with retries; a URL
            that still fails is recorded in manifest["errors"] and never aborts the run.
  1b.PROMOTE the standings page through scripts/standings_feed.py (strict: only a full
            30-team parse with all printed columns overwrites data/live/standings.json;
            a partial parse is recorded in the manifest and keeps the verified capture).
  2. GATES  scripts/freshness_gates.py MUST pass (freshness + provenance).
  3. REBUILD ONLY AFTER THE GATES PASS: ingest the game-card finals from the fetched
            games pages into the results feed (arithmetic-checked), settle every finished
            game day and the sealed pick ledger, publish/verify the pick ledger,
            re-cut estimator inputs, then assemble_canonical.py + build_app.py.
  4. COMMIT  the refreshed captures and rebuilt outputs on success; on any failure the
            run exits non-zero WITHOUT rebuilding (and the site keeps the last good build).

Dates are Eastern (the NBA schedule's day), not UTC. Injury reports are ordered by their
real clock time, not by sorting the filename strings.

Usage: python3 scripts/refresh_official.py [--dry-run] [--stamp 2026-11-15T12-00Z]
       python3 scripts/refresh_official.py --promote-only data/app/refresh/<stamp>   (offline)
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

UA = {"User-Agent": "Mozilla/5.0 (NBA3 official-data refresh; research pipeline)"}
INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJ_CDN = "https://ak-static.cms.nba.com/referee/injury/"
GAMES = "https://www.nba.com/games?date="
STANDINGS_URL = "https://www.nba.com/standings"
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


def all_report_stamps(index_html):
    """Every report link on the official index, ordered oldest to newest by real time."""
    return sorted(set(REPORT_RE.findall(index_html)), key=lambda t: report_time(*t))


def et_today(now_utc):
    return now_utc.astimezone(ET).date()


def utc_timestamp(now=None):
    """Return an explicit, second-resolution UTC timestamp for retrieval provenance."""
    instant = now or datetime.now(timezone.utc)
    return instant.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# A game CARD on an official games page: the anchor's href and its data-content, which reads
# "AWAY @ HOME, YYYY-MM-DD" (checked on the committed 2026-11-16T00-57Z captures, see
# tests/test_refresh_official.py). Links that sit inside editorial modules on the same page
# (e.g. a newsletter article that links a finished game) are NOT cards and are ignored.
CARD_RE = re.compile(
    r'<a href="/game/([a-z]{3})-vs-([a-z]{3})-(\d{10})"[^>]*?'
    r'data-content="([A-Z]{3}) @ ([A-Z]{3}), (\d{4}-\d{2}-\d{2})"')
SLATE_SOURCE_LABEL = ("official schedule pages for the rolling window, promoted by "
                      "scripts/refresh_official.py from the game cards on each page")


def promote_slate_rows(pages, games_url=GAMES):
    """Return (rows, excluded) for {iso_date: games_page_html}.

    A row is a card on its OWN date's page (card date == page date). The teams in the href
    must equal the teams in the card. A game id that still lands on more than one date is
    excluded and recorded with its dates; it is never assigned to a date by guess.
    """
    found = {}          # game_id -> {"dates": set, "away": str, "home": str}
    excluded = set()    # (game_id, date, reason, detail) tuples, de-duplicated
    for d in sorted(pages):
        for a, h, gid, ca, ch, cd in CARD_RE.findall(pages[d]):
            if cd != d:
                continue                       # a card for another date: not this page's slate
            if (a.upper(), h.upper()) != (ca, ch):
                excluded.add((gid, d, "href teams differ from card teams",
                              f"href {a.upper()}-vs-{h.upper()} / card {ca} @ {ch}"))
                continue
            entry = found.setdefault(gid, {"dates": set(), "away": ca, "home": ch})
            if (entry["away"], entry["home"]) != (ca, ch):
                excluded.add((gid, d, "conflicting teams for one game id",
                              f"{entry['away']} @ {entry['home']} vs {ca} @ {ch}"))
                continue
            entry["dates"].add(d)
    rows = []
    for gid, e in found.items():
        if len(e["dates"]) > 1:
            excluded.add((gid, ",".join(sorted(e["dates"])), "game id on more than one date page",
                          f"{e['away']} @ {e['home']}"))
            continue
        d = next(iter(e["dates"]))
        rows.append({"date": d, "time_et": None, "away": e["away"], "home": e["home"],
                     "game_id": gid, "away_record": None, "home_record": None,
                     "game_url": f"https://www.nba.com/game/{e['away'].lower()}-vs-"
                                 f"{e['home'].lower()}-{gid}",
                     "source": games_url + d})
    rows.sort(key=lambda r: (r["date"], r["game_id"]))
    excluded_rows = [{"game_id": g, "date": dt, "reason": why, "detail": det}
                     for (g, dt, why, det) in sorted(excluded)]
    return rows, excluded_rows


def write_slate(rows, retrieved_utc, excluded):
    slate = {"source_url": GAMES + rows[0]["date"], "source_label": SLATE_SOURCE_LABEL,
             "retrieved_on": retrieved_utc[:10], "retrieved_utc": retrieved_utc,
             "window": {"from": rows[0]["date"], "to": rows[-1]["date"]},
             "count": len(rows), "games": rows, "excluded": excluded,
             "notes": ["tip times are blank where the page pattern did not carry them — "
                       "blank and flagged, never inferred",
                       "a game id that appears on more than one date page is listed in "
                       "'excluded' and is not in 'games'"]}
    with open(os.path.join(APP, "official_slate_current.json"), "w", encoding="utf-8") as fh:
        json.dump(slate, fh, indent=1)
        fh.write("\n")
    return slate


def promote_only(refresh_dir):
    """Offline re-promotion of the slate from a committed capture directory (no network)."""
    out_dir = os.path.abspath(refresh_dir)
    with open(os.path.join(out_dir, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    today = datetime.strptime(man["today_et"], "%Y-%m-%d").date()
    pages = {}
    for off in range(0, 4):
        d = (today + timedelta(days=off)).isoformat()
        page = os.path.join(out_dir, f"games_{d}.html")
        if os.path.exists(page):
            pages[d] = open(page, encoding="utf-8", errors="replace").read()
    rows, excluded = promote_slate_rows(pages)
    if not rows:
        print("promote-only: no game cards found; nothing written", file=sys.stderr)
        return 1
    slate = write_slate(rows, man.get("retrieved_utc", man["stamp"]), excluded)
    print(f"promote-only: {len(rows)} games, {len(excluded)} excluded -> "
          f"data/app/official_slate_current.json (window {slate['window']['from']}"
          f"..{slate['window']['to']})")
    return 0


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
                retrieved_utc = utc_timestamp()
                with open(dest, "wb") as fh:
                    fh.write(data)
                self.artifacts.append({
                    "url": url, "retrieved_utc": retrieved_utc,
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


def archive_injury_reports(index_html, out_dir, manifest, fetcher):
    """Archive every newly listed official injury report and record its retrieval provenance.

    The PDF bytes are retained in this refresh capture; the long-lived archive stores the
    verbatim pdftotext output plus the PDF URL, byte count, SHA-256 and retrieval timestamp.
    """
    retrieved_utc = manifest.get("retrieved_utc")
    if not retrieved_utc:
        raise ValueError("refresh manifest is missing retrieved_utc; refusing to archive PDFs")

    arc_dir = os.path.join(APP, "injury_reports_archive")
    os.makedirs(arc_dir, exist_ok=True)
    arc_index_path = os.path.join(arc_dir, "index.json")
    if os.path.exists(arc_index_path):
        with open(arc_index_path, encoding="utf-8") as fh:
            arc = json.load(fh)
    else:
        arc = {"schema": "nba3.app.injury_archive/v1", "storage_rule": (
            "Every report the official index lists is stored as verbatim extracted text "
            "(pdftotext -layout of the official PDF) with the PDF URL, its sha256 at retrieval "
            "and the retrieval stamp. The PDF bytes themselves stay on the official CDN; the "
            "sha256 pins what was read and the URL serves the bytes for manual re-verification."),
            "reports": {}}
    reports = arc.setdefault("reports", {})
    for y, hh, mm, ap in all_report_stamps(index_html):
        report_stamp = f"{y}-{hh}-{mm}{ap}"
        if report_stamp in reports:
            continue
        pdf_name = f"Injury-Report_{y}_{hh}_{mm}{ap}.pdf"
        pdf_path = os.path.join(out_dir, pdf_name)
        pdf_url = INJ_CDN + pdf_name
        artifact = next((item for item in reversed(fetcher.artifacts)
                         if item.get("url") == pdf_url), None)
        if artifact is not None and os.path.isfile(pdf_path):
            with open(pdf_path, "rb") as fh:
                pdf_bytes = fh.read()
        else:
            pdf_bytes = fetcher.get(pdf_url, pdf_path, required=False,
                                    label=f"injury report {report_stamp}")
            artifact = next((item for item in reversed(fetcher.artifacts)
                             if item.get("url") == pdf_url), None)
        if pdf_bytes is None:
            continue
        report_retrieved_utc = ((artifact or {}).get("retrieved_utc") or retrieved_utc)
        txt_path = os.path.join(arc_dir, f"{y}-{hh}-{mm}{ap}.txt")
        result = subprocess.run(["pdftotext", "-layout", pdf_path, txt_path],
                                capture_output=True, text=True)
        if result.returncode != 0:
            fetcher.errors.append({"url": pdf_url,
                                   "label": f"injury report {report_stamp} text extraction",
                                   "required": False,
                                   "error": f"pdftotext failed: {result.stderr.strip()[:200]}",
                                   "attempts": 1})
            continue
        reports[report_stamp] = {
            "report_stamp_et": f"{y}-{hh}:{mm} {ap}M ET",
            "pdf_url": pdf_url,
            "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "pdf_bytes": len(pdf_bytes),
            "text_file": os.path.relpath(txt_path, ROOT),
            "retrieved_utc": report_retrieved_utc,
        }
    with open(arc_index_path, "w", encoding="utf-8") as fh:
        json.dump(arc, fh, indent=1)
        fh.write("\n")
    print(f"injury archive: {len(reports)} reports indexed "
          f"-> data/app/injury_reports_archive/")
    return arc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp")
    ap.add_argument("--promote-only", metavar="REFRESH_DIR",
                    help="offline: re-promote data/app/official_slate_current.json from a "
                         "committed capture directory (no network)")
    args = ap.parse_args()
    if args.promote_only:
        return promote_only(args.promote_only)
    now = datetime.now(timezone.utc)
    stamp = args.stamp or now.strftime("%Y-%m-%dT%H-%MZ")
    retrieved_utc = utc_timestamp(now)
    out_dir = os.path.join(APP, "refresh", stamp)
    os.makedirs(out_dir, exist_ok=True)
    f = Fetcher(retrieved_utc)
    today_et = et_today(now)
    manifest = {"stamp": stamp, "retrieved_utc": retrieved_utc,
                "today_et": today_et.isoformat(), "newest_injury_report": None,
                "artifacts": f.artifacts, "errors": f.errors, "gamebooks": 0}

    def report_required_failures():
        """Write actionable errors; refresh.yml turns them into annotations on failure.

        These are ordinary stderr messages on purpose. Unit tests exercise the failure
        branches with mocked sources, and GitHub interprets a printed ``::error::`` there
        as a real failed-run annotation even when the test itself passes.
        """
        for error in f.errors:
            if error.get("required"):
                print(f"ERROR: required source failed [{error.get('label')}]: "
                      f"{error.get('error')} ({error.get('url')})", file=sys.stderr)

    def finish():
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=1)
            fh.write("\n")
        print(f"refresh fetch: {len(f.artifacts)} artifacts, {len(f.errors)} failed "
              f"-> data/app/refresh/{stamp}/")

    def fail_fetch(code, message):
        finish()
        print(f"ERROR: {message}", file=sys.stderr)
        report_required_failures()
        return code

    # 1. injury index + newest report PDF (required: the rebuild cannot run without it)
    idx_bytes = f.get(INJ_INDEX, os.path.join(out_dir, "injury_index.html"), required=True,
                      label="injury index")
    if idx_bytes is None:
        return fail_fetch(2, "official injury index could not be fetched")
    newest = newest_report(idx_bytes.decode("utf-8", "replace"))
    if newest is None:
        f.errors.append({"url": INJ_INDEX, "label": "injury index", "required": True,
                         "error": "no injury report links found on the official index",
                         "attempts": 1})
        return fail_fetch(2, "official injury index contains no parseable report links")
    y, hh, mm, ap_ = newest
    manifest["newest_injury_report"] = f"{y}-{hh}-{mm}{ap_}"
    pdf_name = f"Injury-Report_{y}_{hh}_{mm}{ap_}.pdf"
    if f.get(INJ_CDN + pdf_name, os.path.join(out_dir, pdf_name), required=True,
             label="newest injury report PDF") is None:
        return fail_fetch(2, "newest official injury report PDF could not be fetched")

    # 1b. standings page (required: the brief's refresh set; promotion is best-effort below)
    f.get(STANDINGS_URL, os.path.join(out_dir, "standings.html"), required=True,
          label="standings page")

    # 1b. archive every newly listed report; the PDF hash and retrieval time are retained
    # alongside verbatim extracted text for later re-verification and status diffs.
    archive_injury_reports(idx_bytes.decode("utf-8", "replace"), out_dir, manifest, f)

    # 2. schedule/results pages: today..today+3 and the two previous game days (Eastern dates)
    for off in range(-2, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        f.get(GAMES + d, os.path.join(out_dir, f"games_{d}.html"),
              required=(off == 0), label=f"games page {d}")

    # 3. team-stat pages (required: the model's team inputs)
    for i, url in enumerate(TEAM_PAGES):
        f.get(url, os.path.join(out_dir, f"teams_{i}.html"), required=True,
              label=f"team stats page {i}")

    # 3c. standings promotion (strict; a partial or failed parse is recorded and the
    #     previously verified capture is kept — never overwritten by a guess)
    manifest["standings_promotion"] = {"state": "not attempted"}
    st_path = os.path.join(out_dir, "standings.html")
    if os.path.exists(st_path):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "standings_feed.py"),
                            "promote", "--html", st_path, "--source", STANDINGS_URL,
                            "--retrieved", manifest["retrieved_utc"],
                            "--out", os.path.join(ROOT, "data", "live", "standings.json"),
                            "--partial-out", os.path.join(APP, "standings_current.json")],
                           cwd=ROOT, capture_output=True, text=True)
        manifest["standings_promotion"] = {
            "state": "promoted" if r.returncode == 0 and "full" in r.stdout else
                     ("partial" if r.returncode == 0 else "failed"),
            "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        print(f"standings promotion: {manifest['standings_promotion']['state']}")

    # 3b. promote the schedule window from the fetched games pages (game links are the
    #     parseable part of the scoreboard HTML; tip times stay blank and flagged when the
    #     page pattern does not carry them — never inferred)
    pages = {}
    for off in range(0, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        page = os.path.join(out_dir, f"games_{d}.html")
        if os.path.exists(page):
            pages[d] = open(page, encoding="utf-8", errors="replace").read()
    rows, excluded = promote_slate_rows(pages)
    manifest["slate_excluded"] = excluded
    if rows:
        write_slate(rows, manifest["retrieved_utc"], excluded)
        print(f"slate promoted: {len(rows)} games, {len(excluded)} excluded "
              f"-> data/app/official_slate_current.json")

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
    finish()

    if f.errors and any(e["required"] for e in f.errors):
        print("ERROR: required official sources failed — rebuild refused; last good build kept",
              file=sys.stderr)
        report_required_failures()
        return 1
    if args.dry_run:
        return 0

    # 5. gates — the rebuild runs ONLY when they pass
    # freshness_gates.py takes no manifest argument: it checks the committed captures in
    # data/live (see the module docstring). Its own exit code decides; it also writes
    # data/live/freshness.json, which is the published gate report.
    gate = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py")],
                          cwd=ROOT)
    if gate.returncode != 0:
        print("ERROR: freshness/provenance gates FAILED — rebuild refused", file=sys.stderr)
        try:
            rep = json.load(open(os.path.join(ROOT, "data", "live", "freshness.json"),
                                 encoding="utf-8"))
            failed = [g.get("id", "?") for g in rep.get("gates", []) if not g.get("passed")]
            print(f"ERROR: freshness gates failed: {', '.join(failed) or 'unknown'} "
                  "(see data/live/freshness.json for each measured value)", file=sys.stderr)
        except Exception:
            print("ERROR: freshness gates failed (freshness.json unreadable)", file=sys.stderr)
        return 1

    # 6. rebuild chain (offline scripts on the refreshed captures)
    steps = [
        # keep the official per-game results feed current and settle each finished game
        # day from verified finals (the brief: settle as soon as the game day ends);
        # ingest refuses rows whose period scores do not sum to the printed final
        ["python3", "scripts/results_feed.py", "ingest", "--capture-dir", out_dir],
        ["python3", "scripts/results_feed.py", "verify"],
        ["python3", "scripts/results_feed.py", "settle", "--all-done"],
        ["python3", "scripts/pick_ledger.py", "settle"],
        ["python3", "scripts/estimators.py"],
        # the window the pick ledger publishes from (data/app/estimators.json) is written by
        # this script; the line above writes data/live/model.json only. Missing from the chain
        # until session c449d46a, so a scheduled run published from a stale window.
        ["python3", "scripts/estimators_round_79341829.py"],
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
            print(f"ERROR: rebuild step failed (exit {r.returncode}): {' '.join(cmd)}",
                  file=sys.stderr)
            return 1
    print("refresh: gates passed, rebuild complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
