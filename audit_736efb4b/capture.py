#!/usr/bin/env python3
"""Transcribe the verbatim 11/14/26 01:30 PM ET official NBA injury report extraction into rows.

Input : audit_736efb4b/data/official_injury_report_2026-11-14_0130PM_raw.md  (verbatim fetch output)
Output: audit_736efb4b/data/official_injury_report_2026-11-14_0130PM.json

Rules (the project's no-inference rule):
  * a cell is copied only when it is printed in the raw line; a blank cell stays blank;
  * a row whose team, matchup or game date is not printed keeps that field blank and carries a flag;
  * a raw line that cannot be parsed unambiguously is NOT transcribed; it is listed under `unparsed_lines`.
Run:  python3 audit_736efb4b/capture.py
"""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "official_injury_report_2026-11-14_0130PM_raw.md"
OUT = HERE / "data" / "official_injury_report_2026-11-14_0130PM.json"
SOURCE_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"

STATUSES = {"Out", "Questionable", "Doubtful", "Probable", "Available"}
NYS = "NOT YET SUBMITTED"
# The 30 NBA team names, as printed on nba.com/schedule and the official injury report.
TEAM_NAMES = {
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls",
    "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", "Detroit Pistons",
    "Golden State Warriors", "Houston Rockets", "Indiana Pacers", "LA Clippers",
    "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat", "Milwaukee Bucks",
    "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks", "Oklahoma City Thunder",
    "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
    "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards",
}
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")
MATCHUP_RE = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")
GARBLED = "NOT YET SUBMITTED NOT YET SUBMITTED"


def parse_line(line):
    """Return (record_dict, None) or (None, reason). Blank cells are kept as ''."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    rec = {"game_date": "", "game_time_et": "", "matchup": "", "team_name": "",
           "player": "", "status": "", "reason": "", "row_kind": ""}
    if GARBLED in line:
        return None, "garbled cell (two NOT YET SUBMITTED on one line; team names merged)"
    if NYS in cells:
        idx = cells.index(NYS)
        rest = [c for i, c in enumerate(cells) if i != idx]
        rec["status"] = NYS
        rec["row_kind"] = "not_yet_submitted"
    else:
        status_idx = [i for i, c in enumerate(cells) if c in STATUSES]
        if len(status_idx) != 1:
            return None, f"cannot locate a single status cell in {cells}"
        s = status_idx[0]
        if s < 1:
            return None, "status cell has no player cell before it"
        rec["status"] = cells[s]
        rec["reason"] = cells[s + 1] if s + 1 < len(cells) else ""
        rec["player"] = cells[s - 1]
        rest = [c for i, c in enumerate(cells) if i not in (s - 1, s, s + 1)]
        rec["row_kind"] = "player"
    for c in rest:
        if c == "":
            continue
        if DATE_RE.match(c):
            rec["game_date"] = c
        elif TIME_RE.match(c):
            rec["game_time_et"] = c
        elif MATCHUP_RE.match(c):
            rec["matchup"] = c
        elif c in TEAM_NAMES:
            rec["team_name"] = c
        else:
            return None, f"unrecognised cell {c!r}"
    return rec, None


def flags_for(rec):
    f = []
    if rec["row_kind"] == "player" and not rec["team_name"]:
        f.append("team not printed on this row (cell blank in extraction)")
    if not rec["game_date"]:
        f.append("game date not printed on this row")
    if not rec["matchup"]:
        f.append("matchup not printed on this row")
    if not rec["game_time_et"]:
        f.append("game time not printed on this row")
    if rec["row_kind"] == "not_yet_submitted" and not rec["team_name"]:
        f.append("team not printed on this row")
    return f


def main():
    raw_lines = RAW.read_text(encoding="utf-8").splitlines()
    rows, unparsed, skipped = [], [], []
    data_lines = 0
    for n, line in enumerate(raw_lines, 1):
        if not line.startswith("|"):
            continue
        if line.startswith("| Game Date") or line.startswith("| ---") or "| Management |" in line:
            skipped.append({"raw_line": n, "reason": "table header or separator"})
            continue
        if re.fullmatch(r"\|\s*\|\s*\|\s*\|\s*\|\s*Management\s*\|\s*\|\s*\|", line):
            skipped.append({"raw_line": n, "reason": "table header"})
            continue
        data_lines += 1
        rec, why = parse_line(line)
        if rec is None:
            unparsed.append({"raw_line": n, "raw": line, "reason": why})
            continue
        rec["raw_line"] = n
        rec["flags"] = flags_for(rec)
        rec["source_url"] = SOURCE_URL
        rec["report_stamp"] = "11/14/26 01:30 PM ET"
        rows.append(rec)

    # Independent cross-check on the raw text (does not use parse_line): count status words and NYS.
    raw_text = "\n".join(l for l in raw_lines if l.startswith("|"))
    raw_status_counts = Counter(w for w in STATUSES for _ in re.findall(rf"\| {w} \|", raw_text))
    raw_nys = len(re.findall(re.escape(NYS), raw_text))
    parsed_status_counts = Counter(r["status"] for r in rows if r["row_kind"] == "player")
    parsed_nys = sum(1 for r in rows if r["row_kind"] == "not_yet_submitted")
    garbled_nys = raw_nys - parsed_nys - sum(1 for u in unparsed if GARBLED.split()[0] in u["raw"])
    checks = {
        "data_lines_seen": data_lines,
        "rows_transcribed": len(rows),
        "lines_not_transcribed": len(unparsed),
        "status_counts_parsed": dict(parsed_status_counts),
        "status_counts_raw_text": {k: raw_status_counts[k] for k in sorted(STATUSES) if raw_status_counts[k]},
        "player_rows_parsed": sum(parsed_status_counts.values()),
        "not_yet_submitted_rows_parsed": parsed_nys,
        "not_yet_submitted_occurrences_in_raw": raw_nys,
        "not_yet_submitted_on_garbled_line": raw_nys - parsed_nys,
    }
    checks["status_counts_match_raw"] = all(
        parsed_status_counts.get(k, 0) == raw_status_counts.get(k, 0) for k in STATUSES)
    checks["team_names_all_in_official_list"] = all(
        (r["team_name"] == "" or r["team_name"] in TEAM_NAMES) for r in rows)
    doc = {
        "schema": "audit_736efb4b/official_injury_report/v1",
        "source_url": SOURCE_URL,
        "index_url": INDEX_URL,
        "report_stamp": "11/14/26 01:30 PM ET",
        "retrieved_on": "2026-11-14",
        "raw_file": "audit_736efb4b/data/official_injury_report_2026-11-14_0130PM_raw.md",
        "newer_probe": {"url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_45PM.pdf",
                        "result": "AccessDenied (not published at read time)"},
        "checks": checks,
        "rows": rows,
        "unparsed_lines": unparsed,
        "skipped_header_lines": skipped,
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1))
    print("unparsed:", [u["raw_line"] for u in unparsed])


if __name__ == "__main__":
    main()
