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
  3. REBUILD ONLY AFTER THE GATES PASS: re-cut the results feed from the committed
            captures (including the finals just ingested), verify + settle the feed for
            today and the two previous game days, publish/settle/verify the pick ledger,
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


# A game CARD on an official games page: the anchor's href and its data-content, which reads
# "AWAY @ HOME, YYYY-MM-DD" (checked on the committed 2026-11-16T00-57Z captures, see
# tests/test_refresh_official.py). Links that sit inside editorial modules on the same page
# (e.g. a newsletter article that links a finished game) are NOT cards and are ignored.
CARD_RE = re.compile(
    r'<a href="/game/([a-z]{3})-vs-([a-z]{3})-(\d{10})"[^>]*?'
    r'data-content="([A-Z]{3}) @ ([A-Z]{3}), (\d{4}-\d{2}-\d{2})"')
SLATE_SOURCE_LABEL = ("official schedule pages for the rolling window, promoted by "
                      "scripts/refresh_official.py from the game cards on each page")

FINALS_AUTO = os.path.join(APP, "finals_auto.json")

# Each official games page embeds one JSON object per game (Next.js page state) carrying the
# final score and the per-period scores, e.g. "homeTeam":{"teamId":...,"wins":4,"losses":10,
# "score":108,...,"teamTricode":"NOP",...,"periods":[{"period":1,"score":23},...]}.
# The object is bounded by the next "gameId": occurrence on the page. Extraction is by
# brace-matched blocks (periods and teamLeader nest braces, so a lazy regex would cut early).
GAME_ID_RE = re.compile(r'"gameId":"(\d{10})"')
TEAM_BLOCK_RE = re.compile(r'"(awayTeam|homeTeam)":\{')
TRICODE_RE = re.compile(r'"teamTricode":"([A-Z]{3})"')
SCORE_RE = re.compile(r'"score":(\d+)')
RECORD_RE = re.compile(r'"wins":(\d+),"losses":(\d+)')
PERIODS_RE = re.compile(r'\{"period":(\d+),"score":(\d+)\}')
STATUS_RE = re.compile(r'"gameStatusText":"([^"]*)"')


def _brace_block(seg, start):
    """Return the {...} block beginning at seg[start] == '{' (brace-counted, string-safe)."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(seg)):
        c = seg[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return seg[start:i + 1]
    return None


def parse_finals_from_games_html(html, page_date, games_url):
    """Finished games on an official games page, read from the page's own JSON.

    Returns rows shaped like the finals capture files (data/app/finals_*.json) so the
    feed writer treats them identically. A game is included only when its status text
    starts with FINAL — an in-progress or scheduled game is never treated as final.
    """
    cards = {}
    for a, h, gid, ca, ch, cd in CARD_RE.findall(html):
        if cd == page_date:
            cards[gid] = (ca, ch)
    rows = []
    ids = [(m.group(1), m.start()) for m in GAME_ID_RE.finditer(html)]
    for n, (gid, pos) in enumerate(ids):
        end = ids[n + 1][1] if n + 1 < len(ids) else len(html)
        seg = html[pos:end]
        st = STATUS_RE.search(seg[:4000])
        status = st.group(1) if st else ""
        if not status.upper().startswith("FINAL"):
            continue
        teams = {}
        for m in TEAM_BLOCK_RE.finditer(seg):
            block = _brace_block(seg, m.end() - 1)
            if not block:
                continue
            tri = TRICODE_RE.search(block)
            sc = SCORE_RE.search(block)
            rec = RECORD_RE.search(block)
            if not (tri and sc):
                continue
            teams[m.group(1)] = {
                "tricode": tri.group(1),
                "score": int(sc.group(1)),
                "record": (int(rec.group(1)), int(rec.group(2))) if rec else None,
                "periods": {int(p): int(s) for p, s in PERIODS_RE.findall(block)},
            }
        if set(teams) != {"awayTeam", "homeTeam"}:
            continue
        away, home = teams["awayTeam"], teams["homeTeam"]
        if gid in cards and (away["tricode"], home["tricode"]) != cards[gid]:
            print(f"ingest: skip {gid}: card teams {cards[gid]} differ from the JSON teams "
                  f"{(away['tricode'], home['tricode'])}", file=sys.stderr)
            continue
        if "OT" in status.upper().replace("FINAL", ""):
            state = "Final/2OT" if "2OT" in status.upper() else "Final/OT"
        else:
            state = "Final"
        rows.append({
            "date": page_date,
            "game_id": gid,
            "away": away["tricode"],
            "home": home["tricode"],
            "away_final": away["score"],
            "home_final": home["score"],
            "away_periods": [away["periods"].get(i) for i in (1, 2, 3, 4)],
            "home_periods": [home["periods"].get(i) for i in (1, 2, 3, 4)],
            "away_ot1": away["periods"].get(5),
            "home_ot1": home["periods"].get(5),
            "away_ot2": away["periods"].get(6),
            "home_ot2": home["periods"].get(6),
            "state": state,
            "state_text_raw": status,
            "quarter_conflict": False,
            "checks": ("final score and per-period scores read from the official games page's "
                       "own JSON; period sums vs the printed final checked by "
                       "scripts/results_feed.py verify"),
            "gamebook": None,
            "game_page": f"https://www.nba.com/game/{away['tricode'].lower()}-vs-"
                         f"{home['tricode'].lower()}-{gid}",
            "games_page": games_url,
            "away_record_after": list(away["record"]) if away["record"] else None,
            "home_record_after": list(home["record"]) if home["record"] else None,
        })
    return rows


def ingest_finals(pages, out_path=None, standings_path=None):
    """Merge finished games from {iso_date: games_page_html} into data/app/finals_auto.json.

    Idempotent and append-only by game_id: a game already recorded is never edited, so a
    later capture cannot silently change a row that the feed has already settled on.
    standings_path (default data/app/standings_latest.json) receives the derived standings
    snapshot; tests pass a temp path so they never write into data/app.
    """
    out_path = out_path or FINALS_AUTO
    doc = {"schema": "nba3/finals-auto/v1",
           "source_label": ("finished games read from the official nba.com games pages' own "
                            "JSON (final score + per-period scores), ingested by "
                            "scripts/refresh_official.py"),
           "games": []}
    if os.path.exists(out_path):
        doc = json.load(open(out_path, encoding="utf-8"))
    by_id = {g["game_id"]: g for g in doc["games"]}
    added = 0
    for d in sorted(pages):
        for r in parse_finals_from_games_html(pages[d], d, GAMES + d):
            if r["game_id"] in by_id:
                continue
            by_id[r["game_id"]] = r
            added += 1
    doc["games"] = [by_id[k] for k in sorted(by_id)]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(f"ingest finals: {added} new game(s); {len(doc['games'])} in {os.path.relpath(out_path, ROOT)}")
    derive_standings(doc, out_path=standings_path)
    return added


def derive_standings(finals_doc, out_path=None):
    """Standings snapshot derived from the official games pages' own records.

    Each ingested game row carries the post-game W-L the official games page printed for
    both teams (away_record_after / home_record_after). The latest record per team — by
    game date, then game id — is the standings snapshot; it is re-derived every run so the
    scheduled job keeps standings current with no manual input. Provenance: the games
    pages listed in finals_auto.json. Cross-checkable against the official standings page
    (data/app/standings_2026-11-16.json is the direct standings-page capture)."""
    out_path = out_path or os.path.join(APP, "standings_latest.json")
    latest = {}
    for g in sorted(finals_doc["games"], key=lambda g: (g["date"], g["game_id"])):
        for side, tri, rec in (("away", g["away"], g.get("away_record_after")),
                               ("home", g["home"], g.get("home_record_after"))):
            if rec:
                latest[tri] = {"team": tri, "w": rec[0], "l": rec[1],
                               "as_of_game": f"{g['date']} {g['game_id']}",
                               "source": g.get("games_page"),
                               "game_page": g.get("game_page")}
    if not latest:
        return
    doc = {
        "schema": "nba3/standings-derived/v1",
        "source_label": ("standings snapshot derived from the post-game W-L records printed "
                         "on the official nba.com games pages (scripts/refresh_official.py)"),
        "count": len(latest),
        "teams": [latest[k] for k in sorted(latest)],
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(f"standings derived for {len(latest)} teams -> {os.path.relpath(out_path, ROOT)}")


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


def write_slate(rows, stamp, excluded):
    slate = {"source_url": GAMES + rows[0]["date"], "source_label": SLATE_SOURCE_LABEL,
             "retrieved_on": stamp[:10], "retrieved_utc": stamp,
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
    slate = write_slate(rows, man["stamp"], excluded)
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
    ap.add_argument("--promote-only", metavar="REFRESH_DIR",
                    help="offline: re-promote data/app/official_slate_current.json from a "
                         "committed capture directory (no network)")
    args = ap.parse_args()
    if args.promote_only:
        return promote_only(args.promote_only)
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
    pages = {}
    for off in range(0, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        page = os.path.join(out_dir, f"games_{d}.html")
        if os.path.exists(page):
            pages[d] = open(page, encoding="utf-8", errors="replace").read()
    rows, excluded = promote_slate_rows(pages)
    manifest["slate_excluded"] = excluded
    if rows:
        write_slate(rows, stamp, excluded)
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

    # 4b. ingest every finished game from the fetched games pages into
    #     data/app/finals_auto.json (idempotent, append-only by game_id). The feed writer
    #     (scripts/capture_round_79341829.py) merges this file, so the results feed stays
    #     current without manual input: date, teams, final score, quarter scores per game.
    pages_all = {}
    for off in range(-2, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        page = os.path.join(out_dir, f"games_{d}.html")
        if os.path.exists(page):
            pages_all[d] = open(page, encoding="utf-8", errors="replace").read()
    if not args.dry_run:
        ingest_finals(pages_all)
    else:
        print("dry-run: finals not ingested")
    finish(0)

    if f.errors and any(e["required"] for e in f.errors):
        print("required official sources failed — rebuild refused; last good build kept",
              file=sys.stderr)
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
        print("freshness/provenance gates FAILED — rebuild refused", file=sys.stderr)
        return 1

    # 6. rebuild chain (offline scripts on the refreshed captures)
    #    Settlement is part of the chain (brief: "Settle the sealed ledger from official
    #    finals as soon as each game day ends"): the feed's settled rows come from verified
    #    finals only, and pick_ledger settle appends SETTLED entries for published picks
    #    whose finals are verified. settle is idempotent — a row already stamped is skipped.
    settle_days = [today_et.isoformat(),
                   (today_et - timedelta(days=1)).isoformat(),
                   (today_et - timedelta(days=2)).isoformat()]
    steps = [
        ["python3", "scripts/capture_round_79341829.py"],
        ["python3", "scripts/results_feed.py", "verify"],
        ["python3", "scripts/results_feed.py", "settle", "--date", settle_days[0]],
        ["python3", "scripts/results_feed.py", "settle", "--date", settle_days[1]],
        ["python3", "scripts/results_feed.py", "settle", "--date", settle_days[2]],
        ["python3", "scripts/estimators.py"],
        # the window the pick ledger publishes from (data/app/estimators.json) is written by
        # this script; the line above writes data/live/model.json only. Missing from the chain
        # until session c449d46a, so a scheduled run published from a stale window.
        ["python3", "scripts/estimators_round_79341829.py"],
        ["python3", "scripts/minutes_model.py"],
        ["python3", "scripts/pick_ledger.py", "publish"],
        ["python3", "scripts/pick_ledger.py", "settle"],
        ["python3", "scripts/pick_ledger.py", "verify"],
        ["python3", "scripts/preregister.py", "verify"],
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
