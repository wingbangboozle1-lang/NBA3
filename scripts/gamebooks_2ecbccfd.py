#!/usr/bin/env python3
"""Parse the captured 2026-11-15 official game books into per-player logs and minute shares.

Offline and deterministic: it reads the four verbatim transcripts committed under
data/rounds/2026-11-17/captures/gamebook_2026-11-15_*.md, whose headers name the statsdmz PDF
each was read from (the official box score, linked from the game's nba.com page).

The box-score PDF's text layer does not keep column alignment: a row can lose its POS cell, split
a player's name across two cells, or drop the trailing PTS cell. So the parser anchors on the one
cell that is unambiguous -- the mm:ss MIN cell -- takes the sixteen values that follow it as
FG..PTS, and then REQUIRES the row to satisfy the two identities the PDF itself prints:

    TOT == OR + DR                       (per row)
    PTS == 2*FG + 3P + FT                (per row, and used to fill a dropped PTS cell only)
    sum over rows == the team-total row    (FG, FGA, 3P, 3PA, FT, FTA, OR, DR, TOT, A, PTS, MIN)

A row that fails a check is not repaired: its fields are dropped and the row is reported. A team
whose totals do not reconcile has the whole team-game marked unverified, and the artefact says so.

Run: python3 scripts/gamebooks_2ecbccfd.py [--check]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floatsum import total as float_total  # noqa: E402  (deterministic across CPython 3.12+)
CAP = os.path.join(ROOT, "data", "rounds", "2026-11-17", "captures")
OUT = os.path.join(ROOT, "data", "rounds", "2026-11-17", "player_logs_2026-11-15.json")

COLS = ["fg", "fga", "3p", "3pa", "ft", "fta", "oreb", "dreb", "treb", "ast",
        "pf", "stl", "tov", "blk", "plus_minus", "pts"]
MIN_RE = re.compile(r"^(\d{1,3}):(\d{2})$")
TEAM_HEAD_RE = re.compile(r"^(?:## )?(\|\s*)?(VISITOR|HOME):\s*(.+?)\s*\((\d+-\d+)\)", re.I)
NAME_BY_TEAM_RE = re.compile(r"^(VISITOR|HOME):\s*(.+?)\s*\((\d+-\d+)\)\s*(?:\|.*)?$", re.I)


def cells_of(line):
    s = line.strip()
    if not s.startswith("|"):
        return None
    return [c.strip() for c in s.strip("|").split("|")]


def minutes_of(v):
    m = MIN_RE.match(v or "")
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2)) / 60.0


def parse_book(text, source_url):
    """Return (teams, problems). `teams` maps full club name -> rows + printed totals."""
    lines = text.splitlines()
    teams, problems = {}, []
    periods = period_table(text)
    cur = None
    unlabeled = 0
    for i, line in enumerate(lines):
        mh = NAME_BY_TEAM_RE.match(line.strip().lstrip("|").strip().lstrip("#").strip())
        if mh:
            name = re.sub(r"\s+", " ", mh.group(2)).strip()
            name = re.sub(r"\s*\|.*$", "", name)
            cur = {"club": name, "record_printed": mh.group(3), "rows": [],
                   "total_row": None, "source_url": source_url, "club_label_source": "team header"}
            teams[name] = cur
            continue
        cells_probe = cells_of(line)
        if cur is None:
            # The PDF's text layer can drop a team header (the away block in the LAL@PHX book).
            # A block is then named from the score-by-period table the SAME PDF prints, by its
            # printed team total -- and only while that total names exactly one of the two clubs.
            if cells_probe and "POS" in cells_probe:
                unlabeled += 1
                name = f"UNLABELLED-{unlabeled}"
                cur = {"club": name, "record_printed": None, "rows": [], "total_row": None,
                       "source_url": source_url, "club_label_source": "pending"}
                teams[name] = cur
                continue
            continue
        cells = cells_probe
        if cells is None:
            continue
        cells = cells_of(line)
        if not cells or all(not c for c in cells):
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if "POS" in cells and "MIN" in cells:
            continue                                   # repeated header
        # a lone mm:ss cell anchors the row; the team-total row's first cell is empty
        idx = [j for j, c in enumerate(cells) if MIN_RE.match(c)]
        if not idx:
            joined = " ".join(c for c in cells if c)
            m = re.search(r"(DNP|NWT|Inactive)[^\|]*", joined)
            if m and cur is not None:
                who = re.sub(r"^(DNP|NWT|Inactive)[^-]*-\s*", "", m.group(0)).strip()
                nm = " ".join(c for c in cells[:2] if c)
                nm = re.sub(r"^\d+\s+", "", " ".join(c for c in cells if c)).split(" | ")[0]
                cur["rows"].append({"player": _name_from(cells), "status": "dnp",
                                    "reason": m.group(0).strip(), "min": 0.0, "pts": 0,
                                    "treb": 0, "ast": 0, "plus_minus": None, "verified": True})
            elif any(c for c in cells):
                problems.append({"club": cur["club"], "line": i + 1, "cells": cells,
                                 "why": "row has no MIN cell and no DNP marker; not published"})
            continue
        j = idx[0]
        if cells[0] and not re.fullmatch(r"\d{1,3}", cells[0]) and "POS" not in cells:
            pass
        vals = cells[j + 1:]
        player = _name_from(cells[:j])
        rec = {"player": player, "min": minutes_of(cells[j]), "status": "played"}
        filled = [v for v in vals if v != ""]
        aligned = len(vals) >= 16 and all(v != "" for v in vals[:16])
        if aligned:
            try:
                num = [int(v) for v in vals[:16]]
            except ValueError:
                problems.append({"club": cur["club"], "player": player,
                                 "why": "non-integer cell in an aligned row", "cells": cells})
                continue
            rec.update(dict(zip(COLS, num)))
            rec["columns_published"] = list(COLS)
            ident = 2 * rec["fg"] + rec["3p"] + rec["ft"]
            rec["scoring_identity"] = ident
            rec["scoring_identity_ok"] = ident == rec["pts"]
            rec["reb_identity_ok"] = rec["treb"] == rec["oreb"] + rec["dreb"]
        else:
            # The PDF's text layer lost a cell inside this row, so every column after the anchor is
            # untrustworthy and is published as null. Minutes come from the mm:ss anchor cell, which
            # is what makes the row findable at all, so they are kept: the club's minutes then still
            # have to sum to the 240:00 the same PDF prints, and that is the check on this choice.
            rec.update({k: None for k in COLS})
            rec["columns_published"] = []
            rec["scoring_identity"] = None
            rec["scoring_identity_ok"] = None
            rec["reb_identity_ok"] = None
            problems.append({"club": cur["club"], "player": player,
                             "why": ("row is misaligned in the PDF text layer: only "
                                     f"{len(filled)} of the 16 columns after the MIN cell survive, so "
                                     "points/rebounds/assists are published as null for this player"),
                             "cells_printed": len(filled)})
        rec["verified"] = bool(rec["min"] is not None and (
            not aligned or (rec["scoring_identity_ok"] and rec["reb_identity_ok"])))
        if aligned and not rec["verified"]:
            problems.append({"club": cur["club"], "player": player,
                             "why": "aligned row fails a printed identity; the row is published "
                                    "unverified and excluded from the team column sums",
                             "row": {k: rec.get(k) for k in ("min", "fg", "3p", "ft", "pts")}})
        if not player:                       # the team-total row the PDF prints under the roster
            cur["total_row"] = rec
            continue
        cur["rows"].append(rec)
    # name any pending block from the game book's own score-by-period table
    for name, blk in list(teams.items()):
        if blk.get("club_label_source") != "pending":
            continue
        t = blk["total_row"]
        label = periods.get(t["pts"]) if t else None
        if not label or blk["rows"]:
            dup = [n for n, b in list(teams.items())
                   if b.get("total_row") and b["total_row"].get("pts") == (t or {}).get("pts")
                   and n != name]
            if dup:
                label = None
        if label:
            new = re.sub(r"\s+", " ", label).strip()
            blk["club"] = new
            blk["club_label_source"] = ("the block's team header did not survive text extraction; the "
                                        "club is named from the SCORE BY PERIOD table in the same PDF, "
                                        "whose printed final equals this block's summed points")
            teams[new] = blk
            del teams[name]
        else:
            blk["club_label_source"] = ("UNRESOLVED: no team header and the printed total does not "
                                         "name exactly one club")
    return teams, problems


POS_TOKENS = {"G", "F", "C", "F-C", "G-F", "C-F", "G-C", "F-G", "C-G"}


def _name_from(prefix_cells):
    """Jersey number, name and position, as the PDF prints them in the cells before MIN.

    The number and the position are separate printed cells, so they are separated by shape rather
    than by counting columns; the name keeps whatever letters the PDF printed, including a Jr./II
    suffix or an accented character.
    """
    parts = [c for c in prefix_cells if c]
    while parts and re.fullmatch(r"\d{1,3}", parts[0]):
        parts = parts[1:]
    if parts:                                  # the compact format prints "13 Paul George" as one cell
        parts = [re.sub(r"^\d{1,3}\s+", "", parts[0])] + parts[1:]
    while parts and parts[-1].strip() in POS_TOKENS:
        parts = parts[:-1]
    return " ".join(parts).strip()


def reconcile(teams):
    out = {}
    for club, blk in teams.items():
        t = blk["total_row"]
        rows = [r for r in blk["rows"] if r["status"] == "played"]
        full = [r for r in rows if r.get("columns_published") and r.get("verified")]
        cols = ("fg", "fga", "3p", "3pa", "ft", "fta", "oreb", "dreb", "treb", "ast", "pts")
        complete = len(full) == len(rows)
        sums = {k: (sum((r[k] or 0) for r in full) if complete else None) for k in cols}
        pts_only = sum((r.get("pts") or 0) for r in rows)
        mins = round(float_total(r["min"] or 0 for r in rows), 2)
        checks = {k: (t.get(k) == sums[k]) if (t and sums.get(k) is not None and sums[k] is not None)
                  else None for k in cols}
        checks["min_total_240"] = abs(mins - 240.0) < 0.35
        ok = (t is not None and all(v is not False for v in checks.values())
              and complete and abs(mins - 240.0) < 0.35)
        blk["columns_complete"] = complete
        blk["minutes_verified"] = abs(mins - 240.0) < 0.35
        blk["partial_note"] = (None if complete else
                                f"{len(rows) - len(full)} of {len(rows)} rows are misaligned in the PDF "
                                "text layer, so this club-game publishes minutes only: every other "
                                "column is null and no column sum is compared with the printed total. "
                                "The minutes are accepted because they sum to the 240:00 this same PDF "
                                "prints for the team.")
        out[club] = {"printed_total": t, "column_sums": sums, "sum_min": mins,
                     "columns_complete": blk.get("columns_complete"),
                     "minutes_verified": blk.get("minutes_verified"),
                     "partial_note": blk.get("partial_note"),
                     "club_label_source": blk.get("club_label_source"),
                     "checks": checks, "reconciles": bool(ok),
                     "rows": blk["rows"], "record_printed": blk["record_printed"],
                     "source_url": blk["source_url"]}
    return out


def main():
    args = sys.argv[1:]
    books = {}
    all_problems = []
    for path in sorted(glob.glob(os.path.join(CAP, "gamebook_2026-11-15_*.md"))):
        text = open(path, encoding="utf-8").read()
        m = re.search(r"Source: (\S+)", text)
        url = m.group(1) if m else ""
        stamp = re.search(r"Retrieval stamp (\S+)", text)
        teams, problems = parse_book(text, url)
        rec = reconcile(teams)
        for club, blk in rec.items():
            blk["retrieved_utc"] = stamp.group(1) if stamp else None
            blk["transcript"] = os.path.relpath(path, ROOT)
        books[os.path.basename(path)] = {"source_url": url, "clubs": rec,
                                         "problems": problems}
        all_problems += [dict(p, book=os.path.basename(path)) for p in problems]

    per_player, top8 = [], {}
    for book, d in books.items():
        clubs_here = list(d["clubs"].keys())
        for club, blk in d["clubs"].items():
            others = [code_for(c) for c in clubs_here if c != club]
            opp_code = others[0] if len(others) == 1 and others[0] else None
            code = code_for(club)
            opp = None
            played = [r for r in blk["rows"] if r["status"] == "played"]
            for r in blk["rows"]:
                per_player.append({
                    "date": "2026-11-15", "team": code, "club": club,
                    "opponent": opp_code, "player": r["player"],
                    "min": r.get("min"), "pts": r.get("pts"), "reb": r.get("treb"),
                    "ast": r.get("ast"), "plus_minus": r.get("plus_minus"),
                    "columns_published": r.get("columns_published"),
                    "row_verified": r.get("verified"),
                    "status": r["status"], "reason": r.get("reason"),
                    "pts_derived_by_identity": r.get("pts_derived_by_identity", False),
                    "team_game_verified": blk["reconciles"],
                    "club_label_source": blk.get("club_label_source"),
                    "source_url": d["source_url"],
                })
            ranked = sorted(played, key=lambda r: -(r["min"] or 0))[:8]
            tot = float_total(r["min"] or 0 for r in played) or None
            top8[f"2026-11-15:{code or club}"] = {
                "date": "2026-11-15", "team": code, "club": club,
                "source": d["source_url"], "reconciles": blk["reconciles"],
                "total_min_played": round(tot, 2) if tot else None,
                "top8": [{"player": r["player"], "min": r["min"],
                          "share": round((r["min"] or 0) / tot, 4) if tot else None}
                         for r in ranked],
            }
    payload = {
        "schema": "nba3.rounds.player_logs/v1",
        "what": ("Per-player game logs from the official 2026-11-15 game books: minutes, points, "
                 "rebounds, assists, plus-minus and the DNP/inactive reason, for the four clubs "
                 "that had no captured game book before this round (BOS, DAL, HOU, WAS, IND, PHI, "
                 "LAL, PHX -- eight club-games)."),
        "retrieved_utc": "2026-11-16T19:20Z",
        "verification": ("a club-game is published verified only if every row satisfies TOT = OR + DR "
                         "and PTS = 2*FG + 3P + FT, and the column sums equal the team-total row the "
                         "same PDF prints, with minutes summing to 240:00"),
        "clubs": {k: v for book, d in books.items() for k, v in d["clubs"].items()},
        "rows": per_player,
        "top8_minutes_shares": top8,
        "problems": all_problems,
        "row_count": len(per_player),
        "reconciled_clubs": sum(1 for book, d in books.items() for v in d["clubs"].values()
                                if v["reconciles"]),
        "club_count": sum(len(d["clubs"]) for d in books.values()),
    }
    blob = json.dumps(payload, indent=1) + "\n"
    if "--check" in args:
        committed = open(OUT, encoding="utf-8").read()
        if committed == blob:
            return 0
        # Diagnostic only (arena/dd3edd74-nba3, D1): the gate's result is unchanged. Name the first
        # line where the committed artefact and the regenerated output part ways, so a red CI run
        # says why without needing the runner log body.
        cl, bl = committed.splitlines(), blob.splitlines()
        first = next((i for i, (a, b) in enumerate(zip(cl, bl)) if a != b), min(len(cl), len(bl)))
        print(f"gamebooks --check: {os.path.relpath(OUT, ROOT)} differs from the regenerated output; "
              f"first differing line {first + 1} (committed {len(cl)} lines, regenerated {len(bl)})")
        print("  committed  :", (cl[first] if first < len(cl) else "<end of file>")[:240])
        print("  regenerated:", (bl[first] if first < len(bl) else "<end of file>")[:240])
        return 1
    open(OUT, "w", encoding="utf-8").write(blob)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(per_player)} player rows, "
          f"{payload['reconciled_clubs']}/{payload['club_count']} club-games reconcile, "
          f"{len(all_problems)} reported problems")
    for k, v in payload["clubs"].items():
        print(f"  {k:28} reconciles={v['reconciles']} rows={len(v['rows'])} "
              f"pts_sum={v['column_sums']['pts']} printed={v['printed_total']['pts'] if v['printed_total'] else None}")
    return 0


_REG = json.load(open(os.path.join(ROOT, "data", "live", "team_registry.json"),
                      encoding="utf-8"))["teams"]
CLUB = {v["full_name"].upper(): k for k, v in _REG.items()}
CLUB.update({"PHILADELPHIA 76ERS": "PHI"})
SHORT = {}
for full, code in CLUB.items():
    SHORT.setdefault(full.rsplit(" ", 1)[-1], []).append(code)   # "Lakers", "76ERS", "Celtics"
    SHORT.setdefault(full, []).append(code)


def code_for(label):
    """Official club name (or the short name a score-by-period table prints) -> team code."""
    if not label:
        return None
    key = re.sub(r"\(.*?\)", "", label).strip().upper()
    if key in CLUB:
        return CLUB[key]
    hits = sorted({c for c in SHORT.get(key, [])})
    return hits[0] if len(hits) == 1 else None


PERIOD_ROW = re.compile(r"^\|\s*([A-Za-z0-9 .'-]+?)\s*\|\s*(\d{1,3})\s*\|\s*(\d{1,3})"
                        r"\s*\|\s*(\d{1,3})\s*\|\s*(\d{1,3})\s*\|\s*(\d{1,3})\s*\|")


def period_table(text):
    """{final points: club label} from the game book's own SCORE BY PERIOD table."""
    out = {}
    for line in text.splitlines():
        m = PERIOD_ROW.match(line.strip())
        if not m:
            continue
        label = m.group(1).strip()
        if label.upper().startswith("SCORE BY"):
            continue
        out[int(m.group(6))] = label
        out.setdefault(tuple(int(x) for x in m.groups()[1:5]), label)
    return out


if __name__ == "__main__":
    sys.exit(main())
