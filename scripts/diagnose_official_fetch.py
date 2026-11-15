#!/usr/bin/env python3
"""Runner-side official-source reachability diagnostics (session arena/43d54bfe-nba3).

The workspace sandbox cannot reach *.nba.com hosts (proxy allowlist), so whether the
scheduled refresh can actually fetch each official source is only observable on a GitHub
Actions runner. This script fetches every candidate official endpoint the rolling refresh
depends on, records the exact result (HTTP status / exception / payload check) into
data/app/refresh/diagnostics/, and ALWAYS exits 0 — it is an experiment, not a gate.

Tested classes:
  A  official.nba.com injury-report index (HTML, lists report PDF links)
  B  ak-static.cms.nba.com injury-report PDFs (%PDF magic required)
  C  www.nba.com games/schedule pages (server-rendered game links)
  D  www.nba.com/stats team pages (traditional / opponent / advanced)
  E  cdn.nba.com static JSON (scheduleLeagueV2, todaysScoreboard)
  F  cdn.nba.com liveData JSON (scoreboard by date, box score by game id)
  G  stats.nba.com API (standings, team traditional/opponent/advanced) with the
     Referer/Origin header set nba.com pages themselves use, and without
  H  statsdmz.nba.com official game books (known 11/14 PDFs from the committed manifest)

Output: data/app/refresh/diagnostics/official_fetch_diagnostics.json (+ .md table).
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "data", "app", "refresh", "diagnostics")

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
NBA_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}
PLAIN_HEADERS = {"User-Agent": "python-urllib/NBA3-official-refresh"}

LEAGUE_DASH = ("https://stats.nba.com/stats/leaguedashteamstats?"
               "MeasureType={mt}&PerMode=PerGame&PlusMinus=N&PaceAdjust=N&Rank=N"
               "&Season=2026-27&SeasonType=Regular+Season&LeagueID=00&Month=0&PORound=0")


def fetch(name: str, url: str, headers: dict, expect: str = "html",
          markers: list[str] | None = None, timeout: int = 45) -> dict:
    rec = {"id": name, "url": url, "expect": expect, "ok": False}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            rec["status"] = resp.status
            rec["bytes"] = len(body)
            rec["content_type"] = resp.headers.get("Content-Type", "")
        head = body[:4096]
        if expect == "pdf":
            rec["pdf_magic"] = body[:5] == b"%PDF-"
            rec["ok"] = rec["pdf_magic"]
        elif expect == "json":
            try:
                obj = json.loads(body.decode("utf-8", "replace"))
                rec["json_ok"] = True
                rec["json_keys"] = sorted(obj.keys())[:12]
                rec["ok"] = True
            except ValueError as e:
                rec["json_error"] = str(e)[:200]
        else:  # html
            text = body.decode("utf-8", "replace")
            rec["markers"] = {m: (m in text) for m in (markers or [])}
            rec["ok"] = all(rec["markers"].values())
            rec["bytes"] = len(body)
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["error"] = f"HTTPError {e.code} {e.reason}"
        try:
            rec["error_body_head"] = e.read(300).decode("utf-8", "replace")
        except Exception:
            pass
    except Exception as e:  # noqa: BLE001 — diagnostics record everything
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    tests: list[tuple] = []

    # A — injury report index (two header variants)
    INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
    tests.append(("A1_injury_index_browser", INJ_INDEX, NBA_HEADERS, "html",
                  ["Injury-Report_"]))
    tests.append(("A2_injury_index_plain", INJ_INDEX, PLAIN_HEADERS, "html",
                  ["Injury-Report_"]))

    # B — injury report PDFs (one known-committed capture + two candidate recent filings)
    for label, pdf in [
        ("B1_injury_pdf_1115_0615AM",
         "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf"),
        ("B2_injury_pdf_1115_0500PM",
         "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_05_00PM.pdf"),
        ("B3_injury_pdf_1114_0415AM",
         "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"),
    ]:
        tests.append((label, pdf, NBA_HEADERS, "pdf", None))

    # C — nba.com schedule/games pages the slate promotion parses
    for label, url in [
        ("C1_games_2026-11-15", "https://www.nba.com/games?date=2026-11-15"),
        ("C2_games_2026-11-16", "https://www.nba.com/games?date=2026-11-16"),
        ("C3_schedule_2026-11-15", "https://www.nba.com/schedule?date=2026-11-15"),
        ("C4_games_2026-11-14", "https://www.nba.com/games?date=2026-11-14"),
    ]:
        tests.append((label, url, NBA_HEADERS, "html", ["/game/"]))

    # D — nba.com team-stat pages (the three pages the model re-cuts)
    SEASON = "Season=2026-27&SeasonType=Regular%20Season"
    for label, page in [
        ("D1_team_traditional", f"https://www.nba.com/stats/teams/traditional?{SEASON}"),
        ("D2_team_opponent", f"https://www.nba.com/stats/teams/opponent?{SEASON}"),
        ("D3_team_advanced", f"https://www.nba.com/stats/teams/advanced?{SEASON}"),
    ]:
        tests.append((label, page, NBA_HEADERS, "html", None))

    # E/F — cdn.nba.com machine-readable official JSON
    tests.append(("E1_scheduleLeagueV2",
                  "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
                  NBA_HEADERS, "json", None))
    tests.append(("E2_todaysScoreboard",
                  "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json",
                  NBA_HEADERS, "json", None))
    tests.append(("F1_liveData_scoreboard_20261115",
                  "https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_20261115.json",
                  NBA_HEADERS, "json", None))
    tests.append(("F2_liveData_scoreboard_20261114",
                  "https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_20261114.json",
                  NBA_HEADERS, "json", None))
    tests.append(("F3_liveData_boxscore_0022600001",
                  "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022600001.json",
                  NBA_HEADERS, "json", None))

    # G — stats.nba.com API (standings + the three team-stat tables), headers on/off
    tests.append(("G1_standingsv3_headers",
                  "https://stats.nba.com/stats/leaguestandingsv3?Season=2026-27"
                  "&LeagueID=00&SeasonType=Regular%20Season&SeasonYear=2026-27",
                  NBA_HEADERS, "json", None))
    tests.append(("G2_standingsv3_plain",
                  "https://stats.nba.com/stats/leaguestandingsv3?Season=2026-27"
                  "&LeagueID=00&SeasonType=Regular%20Season&SeasonYear=2026-27",
                  PLAIN_HEADERS, "json", None))
    for mt in ("Traditional", "Advanced", "Opponent"):
        tests.append((f"G3_teamstats_{mt.lower()}_headers", LEAGUE_DASH.format(mt=mt),
                      NBA_HEADERS, "json", None))
        tests.append((f"G4_teamstats_{mt.lower()}_plain", LEAGUE_DASH.format(mt=mt),
                      PLAIN_HEADERS, "json", None))

    # H — official game books (known 11/14 files from the committed manifest)
    for gb in ("DENNOP", "DALCLE"):
        tests.append((f"H1_gamebook_{gb}",
                      f"https://statsdmz.nba.com/pdfs/20261114/20261114_{gb}.pdf",
                      NBA_HEADERS, "pdf", None))

    results = []
    for label, url, headers, expect, markers in tests:
        rec = fetch(label, url, headers, expect, markers)
        results.append(rec)
        print(f"[{'OK' if rec.get('ok') else 'FAIL'}] {label}: "
              f"{rec.get('status', '-')} {rec.get('error', '')}")
        time.sleep(0.5)

    n_ok = sum(1 for r in results if r.get("ok"))
    report = {"generated_by": "scripts/diagnose_official_fetch.py (session arena/43d54bfe-nba3)",
              "tests": results, "n_ok": n_ok, "n_tests": len(results)}
    with open(os.path.join(OUT_DIR, "official_fetch_diagnostics.json"), "w",
              encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(OUT_DIR, "official_fetch_diagnostics.md"), "w",
              encoding="utf-8") as fh:
        fh.write("# Official-source reachability on the GitHub Actions runner\n\n")
        fh.write("Recorded live by the diagnose-official-fetch workflow. `OK` means the\n"
                 "payload check passed (JSON parsed / PDF magic present / HTML markers found).\n\n")
        fh.write("| Test | Result | Status | Note |\n|---|---|---|---|\n")
        for r in results:
            note = r.get("error") or ""
            if r.get("expect") == "json" and r.get("json_ok"):
                note = f"json keys: {', '.join(r.get('json_keys', [])[:6])}"
            if r.get("expect") == "html" and r.get("markers"):
                bad = [m for m, ok in r["markers"].items() if not ok]
                note = ("markers missing: " + ", ".join(bad)) if bad else note or "all markers found"
            fh.write(f"| `{r['id']}` | {'OK' if r.get('ok') else 'FAIL'} | "
                     f"{r.get('status', '-')} | {note[:120]} |\n")
        fh.write(f"\n{n_ok}/{len(results)} tests OK.\n")
    print(f"diagnostics written: {n_ok}/{len(results)} OK")
    return 0  # always — this is an experiment, not a gate


if __name__ == "__main__":
    sys.exit(main())

# trigger test: session 43d54bfe
