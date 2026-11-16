#!/usr/bin/env python3
"""Parse the two 11/15 official game books this session transcribed into per-player game logs.

Output: ``d1b96315/data/player_logs_2026-11-15.json`` — one row per player-game with minutes,
points, rebounds, assists and the opponent, exactly as the brief asks, and a flag on every row
whose trailing cell the PDF renderer dropped. Values are never reconstructed: a cell that is not
in the transcript stays ``null`` and is counted in ``unread_cells``.

Run: python3 d1b96315/boxlog.py          (writes the artefact)
     python3 d1b96315/boxlog.py --check  (re-derives and compares with the committed file)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
OUT = HERE / "data"

BOOKS = {
    "gamebook_20261115_DALBOS_box.md": {
        "url": "https://statsdmz.nba.com/pdfs/20261115/20261115_DALBOS.pdf",
        "date": "2026-11-15",
        "teams": {"VISITOR: Dallas Mavericks (7-7)": ("DAL", "BOS"),
                  "HOME: BOSTON CELTICS (11-2)": ("BOS", "DAL")},
    },
    "gamebook_20261115_INDPHI_box.md": {
        "url": "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
        "date": "2026-11-15",
        "teams": {"VISITOR: Indiana Pacers (5-9)": ("IND", "PHI"),
                  "HOME: PHILADELPHIA 76ERS (11-3)": ("PHI", "IND")},
    },
}
# The fourteen printed stat cells that follow MIN, in print order, before +/- and PTS.
TAIL = ["FG", "FGA", "3P", "3PA", "FT", "FTA", "OR", "DR", "TOT", "A", "PF", "ST", "TO", "BS"]
# The brief asks for rebounds and assists by name: REB is the printed TOT cell, AST the A cell.
ALIAS = {"reb": "TOT", "ast": "A"}
MIN_RE = re.compile(r"^(\d{1,3}):(\d{2})$")


def mmss(text: str) -> float | None:
    """'33:51' -> 33.85 minutes (true minutes, not the printed mm.ss decimal)."""
    m = MIN_RE.match(text.strip())
    if not m:
        return None
    return round(int(m.group(1)) + int(m.group(2)) / 60.0, 4)


def parse_book(path: pathlib.Path, meta: dict) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows, unread, totals = [], [], {}
    team = opp = None
    for line in lines:
        s = line.strip()
        head = next((k for k in meta["teams"] if k in s), None)
        if head:
            team, opp = meta["teams"][head]
            continue
        if not s.startswith("|") or team is None:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or all(c and set(c) <= set("-: ") for c in cells):
            continue                                   # markdown separator row
        imin = next((i for i, c in enumerate(cells) if MIN_RE.match(c)), None)
        if imin is None and not any(c.startswith(("DNP", "DND")) for c in cells):
            continue                                   # no MIN cell and not a DNP row
        label_cells = [c for c in (cells[:imin] if imin is not None else cells)
                       if c and not re.fullmatch(r"\d{1,3}", c) and c not in ("F", "G", "C", "POS")]
        label = " ".join(label_cells)
        label = re.sub(r"^\d{1,3}\s+", "", label).strip()      # drop the printed jersey number
        if "240:00" in s:                     # the team totals line of the block being read
            nums = [c for c in cells if c]
            if nums and re.fullmatch(r"\d{2,3}", nums[-1]):
                totals[team] = int(nums[-1])
            continue
        if not label or label.startswith(("SCORE BY", "PLAYER", "#")):
            continue
        after = cells[imin + 1:] if imin is not None else []
        row = {"date": meta["date"], "team": team, "opponent": opp, "player": label,
               "min_printed": cells[imin] if imin is not None else None,
               "min": mmss(cells[imin]) if imin is not None else None, "source": meta["url"]}
        if imin is None:
            dnp0 = next((c for c in cells if c.startswith(("DNP", "DND"))), "")
            row.update({"status": "did not play",
                        "dnp_reason": re.sub(r"^(DNP|DND) - ", "", dnp0),
                        "pts": None, "reb": None, "ast": None, "min": None, "min_printed": None})
            rows.append(row)
            continue
        dnp = next((x for x in ([cells[1] if len(cells) > 1 else ""] + after)
                    if x.startswith(("DNP", "DND"))), None)
        if dnp:
            row.update({"status": "did not play", "dnp_reason": re.sub(r"^(DNP|DND) - ", "", dnp),
                        "pts": None, "reb": None, "ast": None})
            rows.append(row)
            continue
        def emit(values):
            for j, name in enumerate(TAIL):
                row[name.lower()] = values[j] if values else None
            for alias, src in ALIAS.items():
                row[alias] = row[src.lower()] if values else None
            row["plus_minus"] = values[14] if values else None
            row["pts"] = values[15] if values else None
        if len(after) != 16:
            # The renderer dropped a cell somewhere after MIN, and which column it was cannot be
            # read off the transcript. Minutes are keyed by content and stay; every stat cell is
            # left null rather than re-aligned by guesswork.
            emit(None)
            row["unread"] = True
            unread.append(f"{team} {label}: {16 - len(after)} stat cell(s) missing after MIN in the "
                          f"transcript ({len(after)} of 16 present); minutes kept, stats left blank")
        else:
            emit([_num(x) for x in after])
        row["status"] = "played"
        rows.append(row)
    min_sum = {}
    for r in rows:
        if r.get("min") is not None:
            min_sum[r["team"]] = round(min_sum.get(r["team"], 0.0) + r["min"], 2)
    checks = {
        "rows": len(rows),
        "minutes_sum_vs_240": {t: {"parsed": v, "printed": 240.0,
                                   "residual": round(v - 240.0, 2)} for t, v in sorted(min_sum.items())},
        # The printed team total is an identity on the block, not on one player: the residual is
        # reported as the points that must sit in the rows whose PTS cell was dropped.
        "points_identity": {
            t: {"printed_team_total": totals.get(t),
                "sum_of_readable_rows": sum(r["pts"] or 0 for r in rows if r["team"] == t),
                "rows_with_unread_pts": sum(1 for r in rows if r["team"] == t and r.get("unread")),
                "residual_points_in_unread_rows":
                    (totals[t] - sum(r["pts"] or 0 for r in rows if r["team"] == t))
                    if totals.get(t) is not None else None,
                "readable_rows_only_match": totals.get(t) is not None and
                    sum(r["pts"] or 0 for r in rows if r["team"] == t) == totals[t]}
            for t in sorted({r["team"] for r in rows})},
    }
    return {"game_date": meta["date"], "source": meta["url"], "count": len(rows),
            "unread_cells": sorted(set(unread)), "checks": checks, "rows": rows}


def _num(text: str):
    t = (text or "").strip().replace(",", "")
    if t in ("", "--"):
        return None
    return int(t) if re.fullmatch(r"-?\d+", t) else (float(t) if re.fullmatch(r"-?\d+\.\d+", t) else t)


def main(check=False) -> int:
    arts = {}
    for fname, meta in BOOKS.items():
        d = parse_book(RAW / fname, meta)
        d["transcript"] = f"d1b96315/data/raw/{fname}"
        slug = fname.split("_")[2].lower().replace(".md", "")      # dalbos / indphi
        arts[f"player_logs_{meta['date']}_{slug}.json"] = d
    merged_rows, per_book = [], {}
    for name, d in arts.items():
        per_book[name] = {"count": d["count"], "unread_cells": d["unread_cells"], "checks": d["checks"],
                          "source": d["source"]}
        merged_rows += d["rows"]
    out = {
        "schema": "nba3.d1b96315.player-logs/v1",
        "source_label": "Per-player game logs (minutes, points, rebounds, assists, opponent) read "
                        "from the official game books of the 2026-11-15 slate, transcribed by this "
                        "session. Combined with the 2026-11-14 logs already on main "
                        "(data/app/player_game_logs.json) this is the input to the "
                        "minutes-redistribution model.",
        "retrieved_utc": "2026-11-16T18:44Z",
        "books": per_book,
        "count": len(merged_rows),
        "teams": sorted({r["team"] for r in merged_rows}),
        "unread_cells": sorted({c for v in per_book.values() for c in v["unread_cells"]}),
        "rows": merged_rows,
    }
    path = OUT / "player_logs_2026-11-15.json"
    text = json.dumps(out, indent=1) + "\n"
    if check:
        ok = path.exists() and path.read_text(encoding="utf-8") == text
        print("player logs reproducible" if ok else "DRIFT in player_logs_2026-11-15.json")
        return 0 if ok else 1
    path.write_text(text, encoding="utf-8")
    print("wrote d1b96315/data/player_logs_2026-11-15.json")
    for name, v in per_book.items():
        print(" ", name, v["count"], "rows; unread:", v["unread_cells"])
        print("   checks:", json.dumps(v["checks"]["points_identity"]))
        print("   minutes:", json.dumps(v["checks"]["minutes_sum_vs_240"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
