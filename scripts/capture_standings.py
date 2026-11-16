#!/usr/bin/env python3
"""Build data/live/standings.json from the committed official-standings capture.

Input:  data/live/raw/standings_2026-11-16.md  (verbatim transcription of
        https://www.nba.com/standings, plus a cross-check table of the team records
        printed on the official game cards read the same day)
Output: data/live/standings.json

Every row carries the official source URL. The parser runs arithmetic checks and
REFUSES to write standings.json when a check fails (exit non-zero, nothing published):
  * exactly 30 teams, 15 per conference, no duplicate names;
  * WIN% equals W/(W+L) at three decimals;
  * GB equals the games-behind formula against the conference leader;
  * HOME+ROAD+Neutral splits sum to W+L; DIV <= CONF <= W+L; OT and LAST10 sane;
  * every team's record on the game-card cross-check table equals its W-L.

Deterministic: no wall clock. The retrieval stamp is carried in the capture file and
copied into the output. Run: python3 scripts/capture_standings.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "live" / "raw" / "standings_2026-11-16.md"
OUT = ROOT / "data" / "live" / "standings.json"

SOURCE = "https://www.nba.com/standings"
ROW_RE = re.compile(
    r"^\|\s*(?P<team>[A-Za-z0-9. ]+?)\s*\|\s*(?P<w>\d+)\s*\|\s*(?P<l>\d+)\s*\|\s*"
    r"(?P<pct>\.\d+)\s*\|\s*(?P<gb>--|\d+(?:\.\d+)?)\s*\|\s*"
    r"(?P<conf>\d+-\d+)\s*\|\s*(?P<div>\d+-\d+)\s*\|\s*(?P<home>\d+-\d+)\s*\|\s*"
    r"(?P<road>\d+-\d+)\s*\|\s*(?P<neutral>\d+-\d+)\s*\|\s*(?P<ot>\d+-\d+)\s*\|\s*"
    r"(?P<last10>\d+-\d+)\s*\|\s*(?P<streak>[WL] \d+)\s*\|$")
XREF_RE = re.compile(r"^\|\s*(?P<team>[A-Za-z0-9. ]+?)\s*\|\s*(?P<rec>\d+-\d+)\s*\|")


def parse_capture(text: str):
    tables = {}
    current = None
    xref = {}
    section = None
    for line in text.splitlines():
        if line.startswith("## Eastern Conference"):
            current, section = "East", "standings"
        elif line.startswith("## Western Conference"):
            current, section = "West", "standings"
        elif line.startswith("## Cross-check"):
            section = "xref"
        elif section == "standings" and line.startswith("|") and not set(line) <= set("|- "):
            if "Team | W |" in line or "---" in line:
                continue
            m = ROW_RE.match(line)
            if not m:
                continue
            row = {k: (v if k in ("team", "gb", "streak") else
                       int(v) if re.fullmatch(r"\d+", v) else v)
                   for k, v in m.groupdict().items()}
            tables.setdefault(current, []).append(row)
        elif section == "xref" and line.startswith("|") and not set(line) <= set("|- "):
            if "Team | Record" in line or "---" in line:
                continue
            m = XREF_RE.match(line)
            if m:
                xref[m.group("team")] = m.group("rec")
    return tables, xref


def split(s):
    a, b = s.split("-")
    return int(a), int(b)


def check(tables, xref):
    problems = []
    seen = set()
    total = sum(len(v) for v in tables.values())
    if total != 30:
        problems.append(f"expected 30 teams, parsed {total}")
    for conf, rows in tables.items():
        if len(rows) != 15:
            problems.append(f"{conf}: expected 15 rows, parsed {len(rows)}")
        if not rows:
            continue
        leader = rows[0]
        lw, ll = leader["w"], leader["l"]
        for r in rows:
            name = r["team"]
            if name in seen:
                problems.append(f"duplicate team row: {name}")
            seen.add(name)
            gp = r["w"] + r["l"]
            if gp == 0:
                problems.append(f"{name}: zero games")
                continue
            want_pct = round(r["w"] / gp, 3)
            if abs(float(r["pct"]) - want_pct) > 0.0011:
                problems.append(f"{name}: WIN% {r['pct']} != {want_pct:.3f}")
            if r is not leader:
                want_gb = ((lw - ll) - (r["w"] - r["l"])) / 2
                if r["gb"] == "--":
                    if want_gb != 0:
                        problems.append(f"{name}: GB '--' but the formula gives {want_gb:g}")
                elif abs(float(r["gb"]) - want_gb) > 0.01:
                    problems.append(f"{name}: GB {r['gb']} != {want_gb:g}")
            elif r["gb"] != "--":
                problems.append(f"{name}: conference leader should print GB '--'")
            hw, hl = split(r["home"]); rw, rl = split(r["road"]); nw, nl = split(r["neutral"])
            if (hw + rw + nw, hl + rl + nl) != (r["w"], r["l"]):
                problems.append(f"{name}: HOME+ROAD+Neutral != W-L")
            cw, cl = split(r["conf"]); dw, dl = split(r["div"])
            if dw + dl > cw + cl or cw + cl > gp:
                problems.append(f"{name}: DIV/CONF splits exceed games played")
            otw, otl = split(r["ot"])
            if otw + otl > gp:
                problems.append(f"{name}: OT games exceed games played")
            l10w, l10l = split(r["last10"])
            if l10w + l10l != min(10, gp):
                problems.append(f"{name}: LAST10 {r['last10']} not min(10, {gp})")
            if not re.fullmatch(r"[WL] \d+", r["streak"]):
                problems.append(f"{name}: unparsable streak {r['streak']}")
            x = xref.get(name)
            if x is None:
                problems.append(f"{name}: missing from the game-card cross-check table")
            elif x != f"{r['w']}-{r['l']}":
                problems.append(f"{name}: game-card record {x} != standings {r['w']}-{r['l']}")
    return problems


def main():
    text = RAW.read_text(encoding="utf-8")
    m = re.search(r"Retrieved \(agent fetch tool\): (\d{4}-\d{2}-\d{2}) between (\d{2}:\d{2}Z)",
                  text)
    retrieved = f"{m.group(1)}T{m.group(2)}" if m else ""
    stamp_note = m.group(0) if m else ""
    tables, xref = parse_capture(text)
    problems = check(tables, xref)
    if problems:
        for p in problems:
            print(f"CHECK FAILED: {p}", file=sys.stderr)
        print("standings.json NOT written", file=sys.stderr)
        return 1
    teams = {}
    for conf, rows in tables.items():
        for i, r in enumerate(rows, start=1):
            teams[r["team"]] = {
                "conference": conf, "rank": i,
                "w": r["w"], "l": r["l"], "win_pct": r["pct"], "gb": r["gb"],
                "conf_record": r["conf"], "div_record": r["div"],
                "home_record": r["home"], "road_record": r["road"],
                "neutral_record": r["neutral"], "ot_record": r["ot"],
                "last10": r["last10"], "streak": r["streak"],
            }
    doc = {
        "schema": "nba3.live.standings/v1",
        "source_url": SOURCE,
        "retrieved_utc": retrieved,
        "retrieval_note": stamp_note,
        "capture_file": str(RAW.relative_to(ROOT)),
        "what": ("Official 2026-27 regular-season standings, overall, by conference: "
                 "W, L, WIN%, GB, CONF, DIV, HOME, ROAD, Neutral, OT, LAST10, STREAK. "
                 "Transcribed from the official standings page and cross-checked team by "
                 "team against the team records printed on the official game cards read "
                 "the same day."),
        "counts": {"teams": len(teams), "east": len(tables.get("East", [])),
                   "west": len(tables.get("West", [])),
                   "game_card_cross_check_rows": len(xref)},
        "checks": {
            "teams_30_unique": True,
            "win_pct_arithmetic": "W/(W+L) at 3dp for every team",
            "gb_games_behind_formula": "GB = ((W1-L1)-(Wi-Li))/2 vs the conference leader",
            "home_road_neutral_sum_to_record": True,
            "div_subset_conf_subset_gp": True,
            "last10_equals_min_10_gp": True,
            "game_card_records_equal_standings": f"{len(xref)} of 30 teams cross-checked",
        },
        "teams": teams,
    }
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"standings.json written: {len(teams)} teams, 0 check failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
