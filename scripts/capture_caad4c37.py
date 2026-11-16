"""Official injury-report archive: one stored file per report version, each carrying its
revision time and its retrieval time, and consecutive versions diffed to surface status changes
(session arena/caad4c37-nba3).

Why this file exists
--------------------
The brief asks to "store every injury PDF with its timestamp and diff consecutive reports to
detect status changes". When this session started, the newest injury report committed anywhere on
`main` was the **2026-11-15 06:15 AM ET** report in `data/live/injuries/`, but the official index
listed 11/15 reports through **09:00 PM ET**. So the stored chain stopped roughly fifteen hours
short of the newest official version.

This session therefore fetched and stored:
  * 11/15 08:45 PM ET  (immediate predecessor of the newest)
  * 11/15 09:00 PM ET  (newest listed on the official index at read time)

and diffs them against each other (a consecutive pair, 15 minutes apart) and against the
already-committed 06:15 AM ET report (the published baseline), so the change over the whole
evening is visible rather than assumed.

Rules this script follows
-------------------------
* It reads only files committed to the repo. No network.
* Player identity is matched on a normalised name key ONLY when the names are identical after
  case/accents/punctuation folding. 'Embid' vs 'Embiid' is therefore reported as a remove plus an
  add - which is what the official PDFs print - not silently merged. (Same rule the repository
  already uses in scripts/injury_archive.py.)
* Continuation rows print a blank Team cell. Where this session attributed a team it used the
  team section the row sits in and says so in the file header; the diff keys on player name so a
  differing attribution can never masquerade as a status change.
* A row is never repaired, re-aligned or filled in.

Run:  python3 scripts/capture_caad4c37.py            (writes index + deltas)
      python3 scripts/capture_caad4c37.py --check     (rebuild in memory, diff, exit 1 on drift)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
SESSION = "arena/caad4c37-nba3"
BUILD_UTC = "2026-11-16T02:24Z"

MINE = ROOT / "data" / "arena_caad4c37" / "injuries"
COMMITTED = ROOT / "data" / "live" / "injuries"

OUT_INDEX = MINE / "archive_index.json"
OUT_DELTAS = MINE / "deltas.json"

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
SOURCE = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{stamp}.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"

# stamp, file, how it is stored, who captured it, when it was retrieved
REPORTS = [
    {
        "stamp": "2026-11-15_06_15AM",
        "header": "Injury Report: 11/15/26 06:15 AM",
        "retrieved_utc": "2026-11-15T11:33Z",
        "captured_by": "arena/2ebb1e75-nba3",
        "path": COMMITTED / "Injury-Report_2026-11-15_06_15AM.md",
        "format": "markdown_table",
        "role": "newest report committed on main before this session (published baseline)",
    },
    {
        "stamp": "2026-11-15_08_45PM",
        "header": "Injury Report: 11/15/26 08:45 PM",
        "retrieved_utc": "2026-11-16T02:24Z",
        "captured_by": SESSION,
        "path": MINE / "Injury-Report_2026-11-15_08_45PM.md",
        "format": "pipe_rows",
        "role": "captured by this session",
    },
    {
        "stamp": "2026-11-15_09_00PM",
        "header": "Injury Report: 11/15/26 09:00 PM",
        "retrieved_utc": "2026-11-16T02:14Z",
        "captured_by": SESSION,
        "path": MINE / "Injury-Report_2026-11-15_09_00PM.md",
        "format": "markdown_table",
        "role": "newest report listed on the official index at read time",
    },
]


def norm_name(raw: str) -> str:
    """Case/accent/punctuation fold. Deliberately conservative - see module docstring."""
    s = unicodedata.normalize("NFKD", raw)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"[^a-z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _make_row(team: str, player: str, status: str, reason: str) -> dict:
    if "NOT YET SUBMITTED" in f"{player} {status} {reason}".upper():
        return {"kind": "team", "team": team or "UNATTRIBUTED", "player": "",
                "status": "NOT YET SUBMITTED", "reason": "", "key": ""}
    return {"kind": "player", "team": team or "UNATTRIBUTED", "player": player,
            "status": status, "reason": reason, "key": norm_name(player)}


def parse_markdown_table(text: str) -> list[dict]:
    """Seven-column markdown rows, as the PDF extraction prints them."""
    rows: list[dict] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        if any(c in ("Game Date", "Player Name", "Current Status") for c in cells):
            continue
        if "NOT YET SUBMITTED" in line.upper():
            team = next((c for c in cells if c and "NOT YET" not in c.upper()), "")
            rows.append(_make_row(team, "", "NOT YET SUBMITTED", ""))
            continue
        idx = next((i for i, c in enumerate(cells) if c in STATUSES), None)
        if idx is None:
            continue
        player = cells[idx - 1] if idx >= 1 else ""
        team = cells[idx - 2] if idx >= 2 else ""
        reason = cells[idx + 1] if idx + 1 < len(cells) else ""
        if not player:
            continue
        rows.append(_make_row(team, player, cells[idx], reason))
    return rows


def parse_pipe_rows(text: str) -> list[dict]:
    """This session's compact storage form: 'Team | Player | Status | Reason'."""
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-") or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4:
            continue
        team, player, status, reason = parts
        if "(team row)" in player:
            rows.append(_make_row(team, "", "NOT YET SUBMITTED", ""))
            continue
        if status not in STATUSES:
            continue
        rows.append(_make_row(team, player, status, reason))
    return rows


def load(spec: dict) -> dict:
    text = spec["path"].read_text(encoding="utf-8")
    rows = (parse_markdown_table(text) if spec["format"] == "markdown_table"
            else parse_pipe_rows(text))
    players = [r for r in rows if r["kind"] == "player"]
    teams = [r for r in rows if r["kind"] == "team"]
    return {
        "stamp": spec["stamp"],
        "report_header": spec["header"],
        "revision_time_et": spec["header"].replace("Injury Report: ", ""),
        "retrieved_utc": spec["retrieved_utc"],
        "captured_by": spec["captured_by"],
        "role": spec["role"],
        "source_url": SOURCE.format(stamp=spec["stamp"]),
        "file": str(spec["path"].relative_to(ROOT)),
        "rows_total": len(rows),
        "player_rows": len(players),
        "team_rows_not_yet_submitted": len(teams),
        "unattributed_player_rows": sum(1 for r in players if r["team"] == "UNATTRIBUTED"),
        "status_counts": {s: sum(1 for r in players if r["status"] == s) for s in STATUSES},
        # Which game dates the report actually covers. An evening report can also carry the next
        # day's games, in which case part of an "rows added" count is a slate-coverage change
        # rather than new injuries. Prefer dates found in the rows themselves; a report stored in
        # the compact form declares them on a header line instead.
        "game_dates_covered": _game_dates(text),
        "rows": rows,
    }


def _game_dates(text: str) -> list[str]:
    dates = sorted(set(re.findall(r"\d{2}/\d{2}/\d{4}", text)))
    if dates:
        return dates
    m = re.search(r"Game dates printed in the PDF:\s*(.+)", text)
    if m:
        return sorted(set(re.findall(r"\d{2}/\d{2}/\d{4}", m.group(1))))
    return []


def diff(a: dict, b: dict) -> dict:
    """Diff two parsed reports. Consecutive or not - the caller says which."""
    pa = {r["key"]: r for r in a["rows"] if r["kind"] == "player" and r["key"]}
    pb = {r["key"]: r for r in b["rows"] if r["kind"] == "player" and r["key"]}

    status_changes, reason_changes = [], []
    for k in sorted(set(pa) & set(pb)):
        ra, rb = pa[k], pb[k]
        if ra["status"] != rb["status"]:
            status_changes.append({
                "player": rb["player"], "team": rb["team"],
                "from": ra["status"], "to": rb["status"], "reason": rb["reason"]})
        elif ra["reason"] != rb["reason"]:
            reason_changes.append({
                "player": rb["player"], "team": rb["team"], "status": rb["status"],
                "from_reason": ra["reason"], "to_reason": rb["reason"]})

    added = [{"player": pb[k]["player"], "team": pb[k]["team"], "status": pb[k]["status"],
              "reason": pb[k]["reason"]} for k in sorted(set(pb) - set(pa))]
    removed = [{"player": pa[k]["player"], "team": pa[k]["team"], "status": pa[k]["status"],
                "reason": pa[k]["reason"]} for k in sorted(set(pa) - set(pb))]

    filed_a = {r["team"] for r in a["rows"] if r["kind"] == "team"}
    filed_b = {r["team"] for r in b["rows"] if r["kind"] == "team"}

    return {
        "from_stamp": a["stamp"], "to_stamp": b["stamp"],
        "from_revision_time_et": a["revision_time_et"], "to_revision_time_et": b["revision_time_et"],
        "from_retrieved_utc": a["retrieved_utc"], "to_retrieved_utc": b["retrieved_utc"],
        "from_source": a["source_url"], "to_source": b["source_url"],
        "counts": {
            "player_rows_from": a["player_rows"], "player_rows_to": b["player_rows"],
            "team_rows_from": a["team_rows_not_yet_submitted"],
            "team_rows_to": b["team_rows_not_yet_submitted"],
            "status_changes": len(status_changes), "reason_changes": len(reason_changes),
            "added": len(added), "removed": len(removed),
        },
        "status_changes": status_changes,
        "reason_changes": reason_changes,
        "added": added,
        "removed": removed,
        "team_rows_now_filed": sorted(filed_a - filed_b),
        "team_rows_still_not_submitted": sorted(filed_b),
        "slate_coverage": {
            "game_dates_from": a["game_dates_covered"],
            "game_dates_to": b["game_dates_covered"],
            "game_dates_added": sorted(set(b["game_dates_covered"]) - set(a["game_dates_covered"])),
            "caveat": ("Both reports cover the same game dates, so every added row is a new "
                       "filing, not a new slate."
                       if not (set(b["game_dates_covered"]) - set(a["game_dates_covered"]))
                       else "A game date was added between these two reports, so part of the "
                            "added-row count is the new slate appearing rather than new filings."),
        },
    }


def build() -> tuple[dict, dict]:
    reports = [load(s) for s in REPORTS]

    index = {
        "schema": "nba3.arena_caad4c37.injury_archive/v1",
        "session": SESSION,
        "built_utc": BUILD_UTC,
        "storage_rule": ("One stored file per official report version. Each carries BOTH the "
                         "revision time printed inside the PDF and the UTC time the file was "
                         "retrieved, so consecutive versions can be diffed and a stale "
                         "publication can be detected rather than assumed."),
        "index_of_record": INDEX_URL,
        "newest_known_on_index": {
            "stamp": "2026-11-15_09_00PM",
            "checked_utc": "2026-11-16T02:13Z",
            "note": ("The official index listed 11/15 reports from 12:00 AM ET through 09:00 PM "
                     "ET and no later one, and listed no 11/16 reports at that time."),
        },
        "files": [{k: v for k, v in r.items() if k != "rows"} for r in reports],
        "totals": {
            "reports_stored_here": sum(1 for r in reports if r["captured_by"] == SESSION),
            "reports_read_only_from_main": sum(1 for r in reports if r["captured_by"] != SESSION),
        },
    }

    deltas = {
        "schema": "nba3.arena_caad4c37.injury_deltas/v1",
        "session": SESSION,
        "built_utc": BUILD_UTC,
        "match_rule": ("Players are matched on a normalised name key. Names are not fuzzy-merged, "
                       "so a spelling change in the official PDF appears as a remove plus an add."),
        "deltas": [
            dict(diff(reports[0], reports[1]), pair="baseline -> newest-1",
                 consecutive=False,
                 gap_note=("Not consecutive: these are the newest report stored on main before "
                           "this session and the first report this session fetched. The gap is "
                           "reported so the size of the published staleness is measurable; "
                           "intermediate versions were not fetched by this session.")),
            dict(diff(reports[1], reports[2]), pair="newest-1 -> newest",
                 consecutive=True,
                 gap_note=("Consecutive official versions, 15 minutes apart, covering the same "
                           "slate - so any difference here is a real status change, not a slate "
                           "change.")),
        ],
    }
    return index, deltas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    index, deltas = build()
    if args.check:
        for path, fresh in ((OUT_INDEX, index), (OUT_DELTAS, deltas)):
            committed = json.loads(path.read_text())
            if committed != fresh:
                print(f"{path.name} does not reproduce from the committed reports", file=sys.stderr)
                return 1
        print(f"OK: injury archive reproduces ({len(index['files'])} reports, "
              f"{len(deltas['deltas'])} deltas)")
        return 0

    OUT_INDEX.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    OUT_DELTAS.write_text(json.dumps(deltas, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_INDEX.relative_to(ROOT)} and {OUT_DELTAS.relative_to(ROOT)}")
    for r in index["files"]:
        print(f"  {r['stamp']}: {r['rows_total']} rows "
              f"({r['player_rows']} player, {r['team_rows_not_yet_submitted']} team) "
              f"revised {r['revision_time_et']}, retrieved {r['retrieved_utc']}")
    for d in deltas["deltas"]:
        c = d["counts"]
        print(f"  delta {d['pair']}: {c['status_changes']} status, {c['reason_changes']} reason, "
              f"+{c['added']} / -{c['removed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
