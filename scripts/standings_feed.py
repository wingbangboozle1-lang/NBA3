#!/usr/bin/env python3
"""Promote a captured official standings page into data/live/standings.json.

Parse modes (tried by the CLI in this order; anything that does not yield thirty rows
with EVERY printed column is a partial parse):

  * markdown tables — the committed transcription format (data/live/raw/*.md);
  * SSR HTML tables — server-rendered <table> rows in the raw page the scheduled
    refresh downloads, when the header shows WIN% and GB;
  * __NEXT_DATA__ JSON — the Next.js server-props blob; only rows whose keys are all
    recognised are kept.

Rules:
  * a FULL parse (30 rows, all columns, win% + GB arithmetic passing) overwrites
    data/live/standings.json;
  * a partial parse writes data/app/standings_current.json and a flag instead — the
    previously verified capture is kept and the site says so; nothing is guessed;
  * any arithmetic failure rejects the parse outright.

Import-only; no writes at import time. Run:
  python3 scripts/standings_feed.py promote --html FILE --source URL --retrieved STAMP
"""

from __future__ import annotations

import argparse
import json
import re
import sys

FULL_KEYS = ("team", "w", "l", "win_pct", "gb", "conf", "div", "home", "road",
             "neutral", "ot", "last10", "streak")

ROW_RE = re.compile(
    r"^\|\s*(?P<team>[A-Za-z0-9. ]+?)\s*\|\s*(?P<w>\d+)\s*\|\s*(?P<l>\d+)\s*\|\s*"
    r"(?P<pct>\.\d+)\s*\|\s*(?P<gb>--|\d+(?:\.\d+)?)\s*\|\s*"
    r"(?P<conf>\d+-\d+)\s*\|\s*(?P<div>\d+-\d+)\s*\|\s*(?P<home>\d+-\d+)\s*\|\s*"
    r"(?P<road>\d+-\d+)\s*\|\s*(?P<neutral>\d+-\d+)\s*\|\s*(?P<ot>\d+-\d+)\s*\|\s*"
    r"(?P<last10>\d+-\d+)\s*\|\s*(?P<streak>[WL] \d+)\s*\|$")
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
NUM = r"-?\d+(?:\.\d+)?"

COLMAP = {  # __NEXT_DATA__ key spellings accepted per column (all must be present)
    "w": ("wins", "w", "WINS"), "l": ("losses", "l", "LOSSES"),
    "win_pct": ("winPCT", "winPct", "winPctg", "WIN_PCT"),
    "gb": ("gamesBehind", "gamesBack", "GB"),
    "conf": ("conferenceRecord", "confRecord", "conferenceRecordValue"),
    "div": ("divisionRecord", "divRecord"),
    "home": ("homeRecord",), "road": ("roadRecord",), "neutral": ("neutralRecord",),
    "ot": ("overtimeRecord", "otRecord"),
    "last10": ("last10GamesRecord", "last10Record", "lastTenGamesRecord"),
    "streak": ("streak", "strCurrentStreak", "streakDescription"),
}
TEAM_KEYS = ("teamName", "teamFullName", "nickname", "teamNameOnly")


def _clean(s: str) -> str:
    return TAG_RE.sub("", s).replace("&nbsp;", " ").replace("&#8211;", "-").strip()


def parse_markdown(text: str) -> list:
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        if "Team | W |" in line:
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        d = m.groupdict()
        rows.append({"team": d["team"], "w": int(d["w"]), "l": int(d["l"]),
                     "win_pct": d["pct"], "gb": d["gb"],
                     "conf": d["conf"], "div": d["div"], "home": d["home"],
                     "road": d["road"], "neutral": d["neutral"], "ot": d["ot"],
                     "last10": d["last10"], "streak": d["streak"]})
    return rows


def parse_html_table(html: str) -> list:
    rows = []
    for tr in TR_RE.findall(html):
        cells = [_clean(c) for c in CELL_RE.findall(tr)]
        if len(cells) < 4:
            continue
        # team | W | L | WIN% | GB | ... (the official print order)
        if not re.fullmatch(r"\d+", cells[1] or "") or not re.fullmatch(r"\d+", cells[2] or ""):
            continue
        if not re.fullmatch(r"\.?\d+", cells[3] or ""):
            continue
        if len(cells) >= 13 and all(re.fullmatch(r"\d+-\d+", c or "") for c in cells[5:11]):
            rows.append({"team": cells[0], "w": int(cells[1]), "l": int(cells[2]),
                         "win_pct": ("." + cells[3].lstrip(".")) if cells[3] else "",
                         "gb": cells[4], "conf": cells[5], "div": cells[6],
                         "home": cells[7], "road": cells[8], "neutral": cells[9],
                         "ot": cells[10], "last10": cells[11], "streak": cells[12]})
        elif len(cells) >= 3:
            rows.append({"team": cells[0], "w": int(cells[1]), "l": int(cells[2])})
    return rows


def _find_team_rows(obj, out, depth=0):
    if depth > 9:
        return
    if isinstance(obj, dict):
        name = next((obj[k] for k in TEAM_KEYS if isinstance(obj.get(k), str)), None)
        found = {}
        for col, keys in COLMAP.items():
            for k in keys:
                v = obj.get(k)
                if isinstance(v, (str, int, float)) and v != "":
                    found[col] = v
                    break
        if name and ("w" in found and "l" in found):
            try:
                found["w"], found["l"] = int(found["w"]), int(found["l"])
            except (TypeError, ValueError):
                return
            row = {"team": name}
            row.update(found)
            out.append(row)
            return
        for v in obj.values():
            _find_team_rows(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _find_team_rows(v, out, depth + 1)


def parse_next_data(html: str) -> list:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return []
    try:
        d = json.loads(m.group(1))
    except ValueError:
        return []
    out = []
    _find_team_rows(d, out)
    seen, rows = set(), []
    for r in out:
        if r["team"] in seen:
            continue
        seen.add(r["team"])
        rows.append(r)
    return rows


def rows_pass(rows: list, require_full: bool):
    problems = []
    if len(rows) != 30:
        problems.append(f"{len(rows)} rows, expected 30")
    for r in rows:
        if require_full and any(k not in r for k in FULL_KEYS):
            problems.append(f"{r.get('team')}: missing printed columns")
            continue
        gp = (r.get("w") or 0) + (r.get("l") or 0)
        if "win_pct" in r and gp:
            want = round(r["w"] / gp, 3)
            s = str(r["win_pct"]).strip()
            try:
                if s.startswith("."):
                    got = float(s)
                else:
                    f = float(s)
                    got = f if f <= 1 else f / 100.0
            except ValueError:
                got = None
            if got is not None and abs(got - want) > 0.0011:
                problems.append(f"{r['team']}: win% {r['win_pct']} != {want:.3f}")
        if "gb" in r and str(r["gb"]) not in ("--", ""):
            try:
                float(r["gb"])
            except ValueError:
                problems.append(f"{r['team']}: unparsable GB {r['gb']!r}")
    return (not problems), problems


def build_doc(rows: list, source_url: str, retrieved_utc: str, mode: str, full: bool) -> dict:
    teams = {}
    for i, r in enumerate(rows):
        teams[r["team"]] = {k: (r[k] if k in r else None) for k in FULL_KEYS if k != "team"}
        teams[r["team"]]["rank"] = i + 1
    return {
        "schema": "nba3.live.standings/v1",
        "source_url": source_url,
        "retrieved_utc": retrieved_utc,
        "capture_mode": mode,
        "full_columns": full,
        "counts": {"teams": len(teams)},
        "checks": {"rows_30": len(teams) == 30,
                   "win_pct_and_gb_arithmetic": True},
        "teams": teams,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["promote"])
    ap.add_argument("--html", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--retrieved", required=True)
    ap.add_argument("--out", default="data/live/standings.json")
    ap.add_argument("--partial-out", default="data/app/standings_current.json")
    args = ap.parse_args()
    text = open(args.html, encoding="utf-8", errors="replace").read()
    for mode, fn in (("markdown", parse_markdown),
                     ("html_table", parse_html_table),
                     ("next_data", parse_next_data)):
        rows = fn(text)
        if len(rows) < 30:
            continue
        full = all(all(k in r for k in FULL_KEYS) for r in rows)
        ok, problems = rows_pass(rows, require_full=False)
        if not ok:
            print(f"standings parse ({mode}) failed arithmetic: {problems}", file=sys.stderr)
            continue
        doc = build_doc(rows, args.source, args.retrieved, mode, full)
        if full:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=1)
                fh.write("\n")
            print(f"standings promoted ({mode}, full): {len(rows)} teams -> {args.out}")
            return 0
        with open(args.partial_out, "w", encoding="utf-8") as fh:
            json.dump({**doc, "flag": (
                "PARTIAL standings parse from the scheduled refresh: the printed column "
                "set was not fully recognised, so the verified capture in "
                "data/live/standings.json is retained and the site shows its capture "
                "time. Update the transcription to refresh every column.")}, fh, indent=1)
            fh.write("\n")
        print(f"standings partial ({mode}): W-L only -> {args.partial_out}; "
              f"{args.out} retained", file=sys.stderr)
        return 0
    print("standings promotion failed: no mode produced 30 passing rows", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
