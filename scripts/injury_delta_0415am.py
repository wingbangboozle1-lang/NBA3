#!/usr/bin/env python3
"""Session 53653a5c: injury-report freshness delta.

Compares the NBA official injury report 11/14/26 04:15 AM ET (raw text stored verbatim in
data/app/official_injuries_2026-11-14_0415AM_raw.md) against the stored 11/13/26 07:30 PM ET
snapshot (data/app/official_injuries_2026-11-13_0730PM.json).

Attribution rule (same as the rest of the repo): a row is compared only when the PDF text prints its
game date, matchup and team on that row. Continuation fragments that do not print the date are kept
in the output as UNVERIFIED and are never counted as a match or a change.

Writes data/app/injury_delta_0415am.json. Standard library only. Deterministic.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/app/official_injuries_2026-11-14_0415AM_raw.md"
STORED = ROOT / "data/app/official_injuries_2026-11-13_0730PM.json"
OUT = ROOT / "data/app/injury_delta_0415am.json"

RAW_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
STORED_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf"
STATUSES = {"Out", "Questionable", "Probable", "Available", "Doubtful", "Available"}
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MATCH_RE = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")
NYS = "NOT YET SUBMITTED"


def parse_raw():
    """Return (attributed_rows, unverified_rows) from the stored raw markdown."""
    attributed, unverified = [], []
    section = ""
    for line_no, line in enumerate(RAW.read_text(encoding="utf-8").splitlines(), 1):
        if "Injury Report: " in line:
            section = line.strip("*").strip()
            continue
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "Game Date":
            continue
        date = next((c for c in cells if DATE_RE.match(c)), "")
        matchup = next((c for c in cells if MATCH_RE.match(c)), "")
        is_nys = NYS in cells
        if is_nys:
            # team is the cell immediately before the NYS marker
            before = cells[:cells.index(NYS)]
            names = [c for c in before if c and not DATE_RE.match(c) and not MATCH_RE.match(c)
                     and not re.match(r"^\d\d:\d\d \(ET\)$", c)]
            team = names[-1] if names else ""
            player, status, reason = "", "", NYS
        else:
            # player rows: [..., team, player, status, reason]; find the status cell
            si = next((i for i, c in enumerate(cells) if c in STATUSES), None)
            if si is None or si < 2:
                continue
            status = cells[si]
            player = cells[si - 1]
            team = cells[si - 2]
            reason = cells[si + 1] if si + 1 < len(cells) else ""
        rec = {"line": line_no, "section": section, "game_date": date, "matchup": matchup,
               "team": team, "player": player, "status": status, "reason": reason,
               "nys": is_nys}
        if date and matchup and team and (is_nys or (player and status)):
            attributed.append(rec)
        else:
            unverified.append(rec)
    return attributed, unverified


def stored_index():
    d = json.loads(STORED.read_text(encoding="utf-8"))
    idx = {}
    for r in d["rows"]:
        if r["game_date"] == "2026-11-14" and r["player"] not in (None, "None", ""):
            key = (r["team"], r["player"])
            idx[key] = r
    nys = {}
    for r in d["rows"]:
        if r["game_date"] == "2026-11-14" and r["player"] in (None, "None", ""):
            nys[r["team"]] = r
    return idx, nys, d


def main():
    attributed, unverified = parse_raw()
    s_idx, s_nys, stored = stored_index()

    # Keep only the 11/14 attributed rows (the 11/15 rows are outside the stored window)
    raw_1114 = [r for r in attributed if r["game_date"] == "11/14/2026"]
    comparisons = []
    seen = set()
    for r in raw_1114:
        if r["nys"]:
            s = s_nys.get(r["team"])
            comparisons.append({
                "game_date": "2026-11-14", "matchup": r["matchup"], "team": r["team"],
                "player": "(team not yet submitted)", "raw_status": NYS, "raw_reason": "",
                "stored_status": "NOT YET SUBMITTED" if s else "(team not in stored snapshot)",
                "result": "same" if s else "new_game_row", "raw_line": r["line"],
            })
            continue
        key = (r["team"], r["player"])
        seen.add(key)
        s = s_idx.get(key)
        if s is None:
            result = "new_in_raw"
            s_status, s_reason = "", ""
        else:
            s_status, s_reason = s["status"], s["reason"]
            same = (s_status == r["status"]) and (s_reason == r["reason"])
            result = "same" if same else ("status_changed" if s_status != r["status"] else "reason_changed")
        comparisons.append({
            "game_date": "2026-11-14", "matchup": r["matchup"], "team": r["team"],
            "player": r["player"], "raw_status": r["status"], "raw_reason": r["reason"],
            "stored_status": s_status, "stored_reason": s_reason,
            "result": result, "raw_line": r["line"],
        })
    frag_players = {r["player"] for r in unverified if r["player"]}
    missing_in_raw = [
        {"team": k[0], "player": k[1], "stored_status": v["status"], "stored_reason": v["reason"],
         "result": ("not_attributed_in_raw" if k[1] in frag_players else "missing_in_raw")}
        for k, v in s_idx.items() if k not in seen
    ]
    outside = [r for r in attributed if r["game_date"] != "11/14/2026"]

    # Fragments: report whether their name/status/reason match a stored row. Never counted.
    frag = []
    for r in unverified:
        if r["player"] and r["status"]:
            m = [s for s in stored["rows"] if s["player"] == r["player"]]
            frag.append({"raw_line": r["line"], "section": r["section"], "player": r["player"],
                         "raw_status": r["status"], "raw_reason": r["reason"],
                         "stored_match_count": len(m),
                         "stored_match_same_status": any(s["status"] == r["status"] for s in m),
                         "result": "unverified_fragment"})
        else:
            frag.append({"raw_line": r["line"], "section": r["section"], "team": r["team"],
                         "matchup": r["matchup"], "result": "unverified_fragment"})

    counts = {}
    for c in comparisons + missing_in_raw:
        counts[c["result"]] = counts.get(c["result"], 0) + 1

    out = {
        "title": "Injury report freshness delta: 11/13/26 07:30 PM ET (stored) vs 11/14/26 04:15 AM ET (official)",
        "session": "53653a5c",
        "raw_source_url": RAW_URL,
        "raw_source_file": str(RAW.relative_to(ROOT)),
        "stored_snapshot_file": str(STORED.relative_to(ROOT)),
        "stored_snapshot_source_url": STORED_URL,
        "index_url": INDEX_URL,
        "retrieved_on": "2026-11-14",
        "rule": "Only rows that print game date, matchup and team are compared. Fragments are listed as unverified and are not counted.",
        "summary": {
            "attributed_11_14_rows_in_raw": len(raw_1114),
            "stored_11_14_player_rows": len(s_idx),
            "stored_11_14_nys_rows": len(s_nys),
            "fragments_unverified": len(frag),
            "attributed_rows_outside_11_14_window": len(outside),
            "counts": dict(sorted(counts.items())),
        },
        "comparisons": comparisons,
        "missing_in_raw": missing_in_raw,
        "unverified_fragments": frag,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
