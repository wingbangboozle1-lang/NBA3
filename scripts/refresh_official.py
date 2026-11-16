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
STANDINGS = "https://www.nba.com/standings"
STANDINGS_JSON = os.path.join(APP, "official_standings_current.json")
GAMEBOOKS_DIR = os.path.join(APP, "gamebooks")
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


# --------------------------------------------------------------------- standings (added by
# session arena/4a59430d-nba3: the brief's first requirement asks the scheduled job to refresh
# the official STANDINGS as well as the schedule, team stats and injury report. Before this
# commit no job in the repo captured standings at all — grep 'standings' over scripts/ found
# only a link label and a 'no official standings row' error string.)

STANDINGS_ROW_RE = re.compile(r">([A-Z]{3})\s*(\d{1,2})\s*-\s*(\d{1,2})\s*</[a-z]+>\s*<[^>]*>\s*"
                              r"(\d\.\d{3})\s*<")
STANDINGS_ASOF_RE = re.compile(r"(?:Last Updated|as of|through)\s*[:\-]?\s*"
                               r"([A-Z][a-z]+ \d{1,2}, \d{4})", re.I)
# the two record cells a game page prints per matchup: "AWAY (w-l) @ HOME (w-l)" style, and the
# official game book's own headers "VISITOR: Indiana Pacers (5-9)" / "HOME: ... (11-3)".
BOXSCORE_RECORD_RE = re.compile(r"boxscore/([a-z]{3})-vs-([a-z]{3})-\d{10}['\"][^>]*>\s*"
                                r"[A-Za-z .']+?\s*\((\d{1,2})-(\d{1,2})\)\s*@\s*"
                                r"[A-Za-z .']+?\s*\((\d{1,2})-(\d{1,2})\)")
GAMEBOOK_RECORD_RE = re.compile(r"^\|\s*(VISITOR|HOME):\s*(.+?)\s*\((\d{1,2})-(\d{1,2})\)", re.M)
NICK_TO_ABBR = {
    "Hawks": "ATL", "Celtics": "BOS", "Nets": "BKN", "Hornets": "CHA", "Bulls": "CHI",
    "Cavaliers": "CLE", "Mavericks": "DAL", "Nuggets": "DEN", "Pistons": "DET",
    "Warriors": "GSW", "Rockets": "HOU", "Pacers": "IND", "Clippers": "LAC",
    "Lakers": "LAL", "Grizzlies": "MEM", "Heat": "MIA", "Bucks": "MIL",
    "Timberwolves": "MIN", "Pelicans": "NOP", "Knicks": "NYK", "Thunder": "OKC",
    "Magic": "ORL", "76ers": "PHI", "76ERS": "PHI", "Suns": "PHX",
    "Trail Blazers": "POR", "Kings": "SAC", "Spurs": "SAS", "Raptors": "TOR",
    "Jazz": "UTA", "Wizards": "WAS",
}


def parse_standings_rows(html):
    """Rows from the official standings page HTML, as the page prints them.

    Returns [] when the page ships its table client-side only (it has in every capture so
    far): the caller then records the standings as NOT captured — blank, flagged — rather
    than deriving W-L from another source and calling it the standings page.
    """
    rows = []
    for abbr, w, l, pct in STANDINGS_ROW_RE.findall(html):
        rows.append({"team": abbr, "wins": int(w), "losses": int(l), "win_pct": float(pct),
                     "source_url": STANDINGS})
    return rows


def parse_standings_asof(html):
    m = STANDINGS_ASOF_RE.search(html)
    return m.group(1) if m else None


def game_records_from_pages(pages):
    """(away_record, home_record) per matchup that a games page prints on its boxscore link.

    These are the records the OFFICIAL schedule/results page shows for that date — the
    standings-adjacent figures the pages themselves carry. Attributed per day, never merged
    across days, so a stale page cannot silently overwrite a fresher number.
    """
    out = []
    for d in sorted(pages):
        for aw, ho, awl, ahl, hwl, hhl in BOXSCORE_RECORD_RE.findall(pages[d]):
            out.append({"date": d, "away": aw.upper(), "home": ho.upper(),
                        "away_wins": int(awl), "away_losses": int(ahl),
                        "home_wins": int(hwl), "home_losses": int(hhl),
                        "source_url": GAMES + d,
                        "measure": "record printed on the official games page for that date"})
    return out


def records_from_gamebooks(gamebook_dir=GAMEBOOKS_DIR):
    """Per-team records exactly as the official game books print their VISITOR/HOME headers.

    A game book header is printed after that game, so a team's record is the standing after
    the games captured so far on that date (the newest captured day per team wins). Only
    teams whose book was actually captured appear; anything else is left blank.
    """
    newest = {}
    out = []
    if not os.path.isdir(gamebook_dir):
        return out
    for name in sorted(os.listdir(gamebook_dir)):
        if not (name.startswith("20") and name.endswith(".md")):
            continue
        path = os.path.join(gamebook_dir, name)
        text = open(path, encoding="utf-8", errors="replace").read()
        day = f"{name[0:4]}-{name[4:6]}-{name[6:8]}"
        for side, team, w, l in GAMEBOOK_RECORD_RE.findall(text):
            abbr = next((a for nick, a in NICK_TO_ABBR.items() if nick in team), None)
            if abbr is None:
                continue
            row = {"team": abbr, "wins": int(w), "losses": int(l), "as_of": day,
                   "printed_as": f"{team} ({w}-{l})",
                   "source_url": f"https://statsdmz.nba.com/pdfs/{day.replace('-', '')}/"
                                 f"{name[:8]}_{name.split('_')[1][:-3]}.pdf",
                   "raw_file": f"data/app/gamebooks/{name}",
                   "measure": ("record printed in the official game book's "
                               f"{side.lower()} header — the game book's own statement of that "
                               "club's standing, cross-checked against the standings page in "
                               "tests/test_refresh_official.py (never assumed pre- or post-game)")}
            out.append(row)
            cur = newest.get(abbr)
            if cur is None or (row["as_of"], row["source_url"]) > (cur["as_of"], cur["source_url"]):
                newest[abbr] = row
    # no derived fields: rank, games back and win pct are only printed when an official
    # source prints them, so they are absent from these rows rather than computed here.
    return sorted(newest.values(), key=lambda r: r["team"])


def promote_standings(stamp, html=None, game_rows=()):
    """Write data/app/official_standings_current.json from what the capture actually holds."""
    page_rows = parse_standings_rows(html) if html else []
    books = records_from_gamebooks()
    doc = {
        "source_url": STANDINGS,
        "retrieved_utc": stamp,
        "standings_page_as_of": parse_standings_asof(html) if html else None,
        "standings_page_rows": page_rows,
        "game_day_records": sorted(game_rows, key=lambda r: (r["date"], r["away"], r["home"])),
        "newest_record_per_team_from_game_books": books,
        "count_page_rows": len(page_rows),
        "notes": [
            "standings_page_rows is empty when the official page ships its table client-side: "
            "no W-L is then attributed to the standings page (blank + flagged, not inferred)",
            "game_day_records come from the record cells the official games pages print for each "
            "matchup on that date; they are per-day and never merged across days",
            "newest_record_per_team_from_game_books is the record printed in each captured "
            "official game book's VISITOR/HOME header (post-game); standings position, games back "
            "and win pct are left blank because no captured official source prints them here",
            "promoted by scripts/refresh_official.py; a team with no captured book has no row",
        ],
    }
    with open(STANDINGS_JSON, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    return doc


def promote_only(refresh_dir):
    """Offline re-promotion of the slate (and standings) from a committed capture directory."""
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
    standings_page = os.path.join(out_dir, "standings.html")
    html = (open(standings_page, encoding="utf-8", errors="replace").read()
            if os.path.exists(standings_page) else None)
    doc = promote_standings(man["stamp"], html=html, game_rows=game_records_from_pages(pages))
    print(f"promote-only: {len(rows)} games, {len(excluded)} excluded -> "
          f"data/app/official_slate_current.json (window {slate['window']['from']}"
          f"..{slate['window']['to']}); standings: {doc['count_page_rows']} page rows + "
          f"{len(doc['newest_record_per_team_from_game_books'])} game-book records + "
          f"{len(doc['game_day_records'])} game-day record cells -> "
          f"data/app/official_standings_current.json")
    return 0


def pdf_to_gamebook_md(pdf_path, out_dir, source_url, retrieved_utc, linked_from=None):
    """Transcribe a captured game-book PDF into the verbatim text form the capture parser reads.

    The scheduled job stores every game's official result document (the game book PDF) with its
    retrieval timestamp in the refresh directory and manifest; this step renders the same PDF's
    text into data/app/gamebooks/<YYYYMMDD>_<AWAY><HOME>.md so the per-game result feed, the
    player game logs and the minutes shares can be rebuilt from it. Nothing is edited on the
    way: lines are printed as the PDF text layer gives them. The extraction library is optional
    — when it is missing the PDF is left as the only artifact and the caller reports the game
    as 'captured, not yet transcribed' (blank and flagged, never a guessed score).

    Returns the written path, or None when it wrote nothing (file exists, no extractor, or no
    text). An existing file is NEVER overwritten: a verbatim transcription already committed by
    another session stays byte-identical.
    """
    name = os.path.basename(pdf_path)
    m = re.match(r"gamebook_(\d{8})_([A-Z]{3})([A-Z]{3})\.pdf$", name)
    if not m:
        return None
    day, away, home = m.group(1), m.group(2), m.group(3)
    dest = os.path.join(out_dir, f"{day}_{away}{home}.md")
    if os.path.exists(dest):
        return None
    try:
        from pypdf import PdfReader          # wired by .github/workflows/refresh.yml
    except Exception:
        try:
            from PyPDF2 import PdfReader      # older name, same API for extract_text
        except Exception:
            return None
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None
    if not text.strip():
        return None
    os.makedirs(out_dir, exist_ok=True)
    head = [
        "# Verbatim game-book capture - " + away + " @ " + home + ", "
        + day[0:4] + "-" + day[4:6] + "-" + day[6:8] + " (PDF text extraction)",
        "",
        "- Source URL: " + source_url,
    ]
    if linked_from:
        head.append("- Linked from: " + linked_from)
    head.append("- Retrieved: " + retrieved_utc
                + " (scripts/refresh_official.py, scheduled official data refresh)")
    head.append("- PDF: " + os.path.relpath(pdf_path, ROOT))
    head.append("- Fidelity: every line below is the PDF text layer exactly as extracted;"
                " no value is edited, reconciled or supplied. Quarter rows are kept as"
                " printed, including any overtime columns.")
    sep = chr(10)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(sep.join(head) + sep + sep + "---" + sep + sep + text.rstrip(sep) + sep)
    return dest


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
    pdf_dest = os.path.join(out_dir, pdf_name)
    if f.get(INJ_CDN + pdf_name, pdf_dest, required=True,
             label="newest injury report PDF") is None:
        return finish(2)
    # store the report's own text next to the bytes (requirement: every injury PDF is stored
    # WITH a timestamp). The store script records the retrieval stamp, the official URL and
    # the designation counts the text layer states unambiguously; it deliberately does not
    # rebuild the report's table rows from the token stream (see its docstring), which stays
    # the verbatim-transcription path that data/live/injuries/*.md uses.
    store = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "injury_pdf_to_md.py"),
                            pdf_dest, "-o", os.path.join(out_dir, pdf_name.replace(".pdf", ".md")),
                            "--retrieved", stamp, "--source-url", INJ_CDN + pdf_name],
                           cwd=ROOT, capture_output=True, text=True)
    manifest["injury_report_stored_md"] = (pdf_name.replace(".pdf", ".md")
                                          if store.returncode == 0 else None)
    print((store.stderr or "").strip())

    # 2. schedule/results pages: today..today+3 and the two previous game days (Eastern dates)
    for off in range(-2, 4):
        d = (today_et + timedelta(days=off)).isoformat()
        f.get(GAMES + d, os.path.join(out_dir, f"games_{d}.html"),
              required=(off == 0), label=f"games page {d}")

    # 3. team-stat pages (required: the model's team inputs)
    for i, url in enumerate(TEAM_PAGES):
        f.get(url, os.path.join(out_dir, f"teams_{i}.html"), required=True,
              label=f"team stats page {i}")

    # 3a. the official standings page (optional). Optional on purpose: the page has shipped
    #     its table client-side in every capture so far, so it can neither gate a rebuild nor
    #     be reported as a required failure while it yields no parsable rows. What is
    #     captured is stored verbatim and promoted below with its own provenance.
    f.get(STANDINGS, os.path.join(out_dir, "standings.html"), required=False,
          label="standings page")

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
    spage = os.path.join(out_dir, "standings.html")
    doc = promote_standings(stamp,
                            html=(open(spage, encoding="utf-8", errors="replace").read()
                                  if os.path.exists(spage) else None),
                            game_rows=game_records_from_pages(pages))
    print(f"standings promoted: {doc['count_page_rows']} rows from the standings page, "
          f"{len(doc['game_day_records'])} game-day record cells, "
          f"{len(doc['newest_record_per_team_from_game_books'])} game-book records "
          f"-> data/app/official_standings_current.json"
          + ("" if doc["count_page_rows"] else
             " (the standings page printed no parsable rows — recorded as not captured)"))

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
            dest = os.path.join(out_dir, f"gamebook_{day.strftime('%Y%m%d')}_{a.upper()}{h.upper()}.pdf")
            if f.get(url, dest, required=False, label=f"game book {a.upper()}{h.upper()}") is not None:
                gb += 1
                written = pdf_to_gamebook_md(
                    dest, GAMEBOOKS_DIR, url, stamp,
                    linked_from=f"https://www.nba.com/game/{a}-vs-{h}")
                if written:
                    manifest.setdefault("gamebooks_transcribed", []).append(
                        os.path.relpath(written, ROOT))
    manifest["gamebooks"] = gb
    manifest["gamebooks_transcribed"] = manifest.get("gamebooks_transcribed", [])
    if gb and not manifest["gamebooks_transcribed"]:
        print("note: game-book PDFs captured but none newly transcribed "
              "(extractor missing or files already present) — the result feed stays on the "
              "transcriptions already committed", file=sys.stderr)

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
    steps = [
        # the game books that were fetched into data/app/gamebooks/ (plus any committed
        # verbatim transcription) become one result row per game, player logs and
        # minutes shares. PDFs land as binaries and are transcribed by the capture round
        # that owns that directory, so the ingestion step is a replay of committed text.
        ["python3", "scripts/capture_round_79341829.py"],
        ["python3", "scripts/results_feed.py", "verify"],
        # settlement of the two most recent Eastern game days, stamped from the capture so
        # the same inputs reproduce byte for byte (see scripts/results_feed.py --stamp-from).
        *[[ "python3", "scripts/results_feed.py", "settle", "--date", day,
            "--stamp-from", "capture"]
           for day in ((today_et - timedelta(days=1)).isoformat(),
                       (today_et - timedelta(days=2)).isoformat())],
        ["python3", "scripts/pick_ledger.py", "settle"],
        ["python3", "scripts/pick_ledger.py", "verify"],
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
            print(f"rebuild step failed: {' '.join(cmd)}", file=sys.stderr)
            return 1
    print("refresh: gates passed, rebuild complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
