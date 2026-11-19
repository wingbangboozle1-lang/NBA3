#!/usr/bin/env python3
"""Parse the verbatim 11/19/26 injury-report transcripts and diff the two revisions.

Session de0caf5d, task X2. Inputs are the fetch-tool text layers stored under captures/.
Rules (no inference):
  * A row is `complete` only if date, time, matchup, team and (player+status, or a
    NOT YET SUBMITTED team placeholder) are all printed in that row.
  * A row whose matchup/team cells are blank is `attribution_missing`: the player is kept,
    but the game and team are left blank and it is listed in the flags.
  * A row whose cells cannot be mapped positionally without guessing is `unreadable`
    and is listed, not repaired.
  * The diff compares only `complete` rows keyed by (matchup, team, player).

Run:  python3 data/rounds/2026-11-19/parse_injury_reports.py   (writes the JSON, prints a summary)
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, "captures")
OUT = os.path.join(HERE, "injury_2026-11-19_0045AM.json")

REVISIONS = [
    {
        "key": "0030AM",
        "label": "11/19/26 12:30 AM ET",
        "file": "Injury-Report_2026-11-19_12_30AM.pdf",
        "raw": "captures/injury_2026-11-19_0030AM_raw.md",
        "linked_from_index": True,
    },
    {
        "key": "0045AM",
        "label": "11/19/26 12:45 AM ET",
        "file": "Injury-Report_2026-11-19_12_45AM.pdf",
        "raw": "captures/injury_2026-11-19_0045AM_raw.md",
        "linked_from_index": False,
    },
]
SOURCE_BASE = "https://ak-static.cms.nba.com/referee/injury/"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
RETRIEVED = "2026-11-19T05:47Z (approximate; bash clock read in the same session)"

ROW_RE = re.compile(r"^\|(.*)\|\s*$")
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")
MATCH_RE = re.compile(r"^[A-Z]{3}@[A-Z]{3}$")
STATUSES = {"Out", "Questionable", "Doubtful", "Probable", "Available", "NOT YET SUBMITTED"}


def _cells(line):
    m = ROW_RE.match(line.strip())
    if not m:
        return None
    return [c.strip() for c in m.group(1).split("|")]


def _is_separator(cells):
    return all(re.fullmatch(r":?-{3,}:?", c or "-") for c in cells)


def parse_revision(rev):
    path = os.path.join(HERE, rev["raw"])
    with open(path, "rb") as fh:
        raw_bytes = fh.read()
    text = raw_bytes.decode("utf-8")
    rows, problems = [], []
    for lineno, line in enumerate(text.splitlines(), 1):
        cells = _cells(line)
        if cells is None or _is_separator(cells):
            continue
        if cells and cells[0] == "Game Date":
            continue
        rec = {"line": lineno, "raw": line.strip(), "revision": rev["key"]}
        if len(cells) == 7 and DATE_RE.match(cells[0]) and TIME_RE.match(cells[1]) and MATCH_RE.match(cells[2]):
            rec.update(game_date=cells[0], game_time_et=cells[1].split(" ")[0], matchup=cells[2], team=cells[3])
            player, status, reason = cells[4], cells[5], cells[6]
            # NOT YET SUBMITTED team placeholder: no player, status column carries the flag.
            if not player and status == "" and reason == "NOT YET SUBMITTED":
                rec.update(player="", status="NOT YET SUBMITTED", reason="", row_kind="team_placeholder")
            elif player and status in STATUSES:
                rec.update(player=player, status=status, reason=reason, row_kind="player")
            else:
                rec.update(player=player, status=status, reason=reason, row_kind="unreadable")
                problems.append({"revision": rev["key"], "line": lineno, "kind": "unreadable", "raw": line.strip()})
        elif len(cells) == 7 and cells[0] == "" and cells[1] == "" and MATCH_RE.match(cells[2]) and cells[3]:
            # Date and time cells blank in the text layer; matchup and team printed.
            rec.update(game_date="", game_time_et="", matchup=cells[2], team=cells[3])
            player, status, reason = cells[4], cells[5], cells[6]
            if not player and status == "" and reason == "NOT YET SUBMITTED":
                rec.update(player="", status="NOT YET SUBMITTED", reason="", row_kind="team_placeholder",
                           attribution="date_time_blank")
            elif player and status in STATUSES:
                rec.update(player=player, status=status, reason=reason, row_kind="player",
                           attribution="date_time_blank")
            else:
                rec.update(player=player, status=status, reason=reason, row_kind="unreadable")
                problems.append({"revision": rev["key"], "line": lineno, "kind": "unreadable", "raw": line.strip()})
        elif len(cells) == 7 and cells[0] == "" and cells[1] == "" and cells[2] == "" and cells[3] == "" and cells[4]:
            # Player printed but team, matchup, date and time cells are all blank in the text layer.
            player, status, reason = cells[4], cells[5], cells[6]
            rec.update(game_date="", game_time_et="", matchup="", team="", player=player,
                       status=status, reason=reason, row_kind="player" if status in STATUSES else "unreadable",
                       attribution="matchup_and_team_blank")
            if status not in STATUSES:
                problems.append({"revision": rev["key"], "line": lineno, "kind": "unreadable", "raw": line.strip()})
        elif len(cells) == 4 and TIME_RE.match(cells[0]) and MATCH_RE.match(cells[1]) and cells[2] and cells[3] == "NOT YET SUBMITTED":
            # Team placeholder whose date and player cells are absent from the text layer.
            rec.update(game_date="", game_time_et=cells[0].split(" ")[0], matchup=cells[1], team=cells[2],
                       player="", status="NOT YET SUBMITTED", reason="", row_kind="team_placeholder",
                       attribution="date_blank")
        elif len(cells) == 3 and cells[0] == "" and cells[1] and cells[2] == "NOT YET SUBMITTED":
            # Team placeholder whose matchup and date cells are absent (team name is printed).
            rec.update(game_date="", game_time_et="", matchup="", team=cells[1],
                       player="", status="NOT YET SUBMITTED", reason="", row_kind="team_placeholder",
                       attribution="matchup_and_date_blank")
        elif len(cells) == 3 and (cells[0] == "" or TIME_RE.match(cells[0])) and MATCH_RE.match(cells[1]) \
                and cells[2] and cells[2] != "NOT YET SUBMITTED":
            # Matchup and team printed, but the status cell is missing: recorded as unreadable, not guessed.
            rec.update(game_date="", game_time_et=(cells[0].split(" ")[0] if cells[0] else ""),
                       matchup=cells[1], team=cells[2], player="", status="",
                       reason="", row_kind="unreadable", attribution="status_missing")
            problems.append({"revision": rev["key"], "line": lineno, "kind": "status_missing", "raw": line.strip()})
        else:
            # Shapes that do not map to the 7-column layout: keep verbatim, do not repair.
            rec.update(row_kind="unreadable_shape", cells=cells)
            problems.append({"revision": rev["key"], "line": lineno, "kind": "unreadable_shape", "raw": line.strip()})
        rows.append(rec)
    return {
        "revision": rev["key"],
        "label": rev["label"],
        "source_url": SOURCE_BASE + rev["file"],
        "raw_file": rev["raw"],
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "rows": rows,
        "problems": problems,
    }


def _key(r):
    # Keyed when the matchup and team are both printed. A blank date or time cell does not block
    # the key (the matchup and team are still printed); a blank matchup or team does.
    if r.get("row_kind") not in ("player", "team_placeholder"):
        return None
    if not r.get("matchup") or not r.get("team"):
        return None
    return (r["matchup"], r["team"], r.get("player", ""))


def diff(prev, cur):
    pk = {}
    for r in prev["rows"]:
        k = _key(r)
        if k:
            pk.setdefault(k, []).append(r)
    ck = {}
    for r in cur["rows"]:
        k = _key(r)
        if k:
            ck.setdefault(k, []).append(r)
    changes, added, removed, unchanged = [], [], [], 0
    for k in sorted(set(pk) | set(ck)):
        a, b = pk.get(k, []), ck.get(k, [])
        if not a:
            added.append({"matchup": k[0], "team": k[1], "player": k[2], "status": b[0]["status"], "reason": b[0]["reason"]})
        elif not b:
            # Keyed in the previous revision but not keyed in the newest text layer. This is NOT a
            # removal: the newest row is unreadable (e.g. its status or matchup cell is missing).
            removed.append({"matchup": k[0], "team": k[1], "player": k[2], "status": a[0]["status"],
                            "reason": a[0]["reason"],
                            "newest_row_text": [r["raw"] for r in cur["rows"] if r.get("team") == k[1] and r.get("matchup") == k[0]]
                            or ["(no newest row printed with this matchup and team)"]})
        elif len(a) > 1 or len(b) > 1:
            changes.append({"matchup": k[0], "team": k[1], "player": k[2], "kind": "duplicate_key_unresolved"})
        elif (a[0]["status"], a[0]["reason"]) != (b[0]["status"], b[0]["reason"]):
            changes.append({"matchup": k[0], "team": k[1], "player": k[2], "kind": "status_or_reason_change",
                            "from": {"status": a[0]["status"], "reason": a[0]["reason"]},
                            "to": {"status": b[0]["status"], "reason": b[0]["reason"]}})
        else:
            unchanged += 1
    # Rows that were not keyed in either revision are compared as raw text, so a difference
    # in unreadable rows is reported instead of silently ignored.
    unkeyed_prev = sorted(r["raw"] for r in prev["rows"] if _key(r) is None)
    unkeyed_cur = sorted(r["raw"] for r in cur["rows"] if _key(r) is None)
    return {
        "compared_keyed_rows": len(set(pk) & set(ck)) + len(set(pk) ^ set(ck)),
        "unchanged_keyed_rows": unchanged,
        "status_changes": changes,
        "added_keyed_rows": added,
        "unreadable_or_absent_in_newest": removed,
        "note_unreadable_or_absent": ("Not counted as removals. Each entry is a row keyed in the previous revision "
                                      "whose newest text row cannot be keyed (status or matchup cell missing), so "
                                      "it cannot be compared; they are NOT treated as changed or cleared."),
        "unkeyed_rows_prev": len(unkeyed_prev),
        "unkeyed_rows_cur": len(unkeyed_cur),
        "unkeyed_rows_identical_text": unkeyed_prev == unkeyed_cur,
    }


def main():
    parsed = [parse_revision(r) for r in REVISIONS]
    prev, cur = parsed[0], parsed[1]
    cur_meta = next(r for r in REVISIONS if r["key"] == cur["revision"])
    out = {
        "schema": "nba3.rounds.injury_capture/v1",
        "session": "de0caf5d",
        "index_url": INDEX_URL,
        "index_lists_latest": "11/19 12:30 a.m ET report (fetched 2026-11-19T05:47Z)",
        "index_lag_note": ("The 12:45 AM PDF URL resolved on the CDN while the index still listed 12:30 AM; "
                           "the newest revision is therefore taken from the CDN probe, not from the index."),
        "retrieved_utc": RETRIEVED,
        "newest_revision": {
            "label": cur["label"],
            "source_url": cur["source_url"],
            "retrieved_utc": RETRIEVED,
            "raw_file": cur["raw_file"],
            "raw_sha256": cur["raw_sha256"],
            "linked_from_index": cur_meta["linked_from_index"],
            "row_count": len(cur["rows"]),
            "player_rows": sum(1 for r in cur["rows"] if r.get("row_kind") == "player"),
            "team_placeholder_rows": sum(1 for r in cur["rows"] if r.get("row_kind") == "team_placeholder"),
            "unreadable_rows": sum(1 for r in cur["rows"] if r.get("row_kind") in ("unreadable", "unreadable_shape")),
            "attribution_incomplete_rows": sum(1 for r in cur["rows"] if r.get("attribution")),
        },
        "previous_revision": {
            "label": prev["label"],
            "source_url": prev["source_url"],
            "retrieved_utc": RETRIEVED,
            "raw_file": prev["raw_file"],
            "raw_sha256": prev["raw_sha256"],
            "row_count": len(prev["rows"]),
        },
        "consecutive": True,
        "consecutive_note": ("12:30 AM and 12:45 AM are consecutive CDN revisions. No archived revision exists "
                             "between 11/16 01:30 PM ET and 11/19 12:30 AM ET in this repository (the scheduled "
                             "refresh has been red since 11/17), so that interval is a gap, not a diff."),
        "diff_previous_to_newest": diff(prev, cur),
        "problems": {r["revision"]: r["problems"] for r in parsed},
        "rows_newest": cur["rows"],
        "rows_previous": prev["rows"],
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    d = out["diff_previous_to_newest"]
    print(f"newest {cur['label']}: rows={len(cur['rows'])} player={out['newest_revision']['player_rows']} "
          f"placeholder={out['newest_revision']['team_placeholder_rows']} "
          f"unreadable={out['newest_revision']['unreadable_rows']} "
          f"attribution_incomplete={out['newest_revision']['attribution_incomplete_rows']}")
    print(f"diff {prev['label']} -> {cur['label']}: unchanged_keyed={d['unchanged_keyed_rows']} "
          f"status_changes={len(d['status_changes'])} added={len(d['added_keyed_rows'])} "
          f"unreadable_or_absent_in_newest={len(d['unreadable_or_absent_in_newest'])} unkeyed_identical_text={d['unkeyed_rows_identical_text']}")
    print("wrote", os.path.relpath(OUT, os.getcwd()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
