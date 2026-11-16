#!/usr/bin/env python3
"""Capture the 2026-11-16 official injury reports and diff consecutive filings.

Offline and byte-reproducible (session arena/4c69ab99-nba3). Inputs are the committed
verbatim transcripts written from the official PDFs:

  data/app/official_injuries_2026-11-16_0145PM_raw.md   newest report on the official
      index at read time (the 11/16 entry ran 12:00 AM through 1:45 PM ET)
  data/app/official_injuries_2026-11-16_0130PM_raw.md   its consecutive predecessor
      (the diff base: two filings 15 minutes apart)

Outputs:
  data/app/official_injuries_2026-11-16_0145PM.json (parsed rows, provenance, quirks)
  data/app/injury_delta_1116.json (status-change diff vs BOTH prior reports: the
  consecutive 01:30 PM filing and the previous archived report of 2026-11-15 06:15 AM ET)

Nothing is inferred or repaired: a row the PDF extraction shifts columns on is kept in
`extraction_quirks` verbatim rather than guessed into shape; a name that changes spelling
between two filings is shown as removed + added with both spellings kept.

Run: python3 scripts/capture_2026_11_16_4c69ab99.py
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from capture_round_79341829 import parse_injury_raw  # noqa: E402  (shared row parser)

APP = os.path.join(ROOT, "data", "app")
RAW_NEW = os.path.join(APP, "official_injuries_2026-11-16_0145PM_raw.md")
RAW_CONSEC = os.path.join(APP, "official_injuries_2026-11-16_0130PM_raw.md")
PRIOR_JSON = os.path.join(APP, "official_injuries_2026-11-15_0615AM.json")
OUT_JSON = os.path.join(APP, "official_injuries_2026-11-16_0145PM.json")
OUT_DELTA = os.path.join(APP, "injury_delta_1116.json")

RETRIEVED_WINDOW = "2026-11-16T18:22Z..2026-11-16T19:25Z"
URL_NEW = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_45PM.pdf"
URL_CONSEC = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_30PM.pdf"
INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"


def quirks(path, parsed_rows):
    """Table lines that carry a player name but did not parse into a row.

    The PDF extraction shifts columns on some multi-player-per-page rows (a status cell
    lands in the reason column or vanishes). Those lines are kept verbatim here — the
    parser never repairs or guesses them.
    """
    seen = {(r.get("player"), r.get("status"), r.get("reason")) for r in parsed_rows}
    out = []
    for line in open(path, encoding="utf-8"):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not any("," in c for c in cells):
            continue
        # a row the parser accepted has a recognised status cell; anything else is a quirk
        status_like = {"Out", "Questionable", "Doubtful", "Probable", "Available",
                       "NOT YET SUBMITTED"}
        if any(c in status_like for c in cells):
            continue
        out.append(line.rstrip("\n"))
    return out


def diff(new_rows, prior_rows, prior_label, prior_url, prior_stamp):
    prior_players = {(r.get("game_date"), r.get("team"), r.get("player")): r
                     for r in prior_rows if not r.get("is_team_not_submitted") and r.get("player")}
    new_players = {(r.get("game_date"), r.get("team"), r.get("player")): r
                   for r in new_rows if not r["is_team_not_submitted"] and r.get("player")}
    added = [{"key": k, "status": new_players[k].get("status"),
              "reason": new_players[k].get("reason")} for k in sorted(new_players)
             if k not in prior_players]
    removed = [{"key": k, "status": prior_players[k].get("status"),
                "reason": prior_players[k].get("reason")} for k in sorted(prior_players)
               if k not in new_players]
    changed = [{"key": k, "from": prior_players[k].get("status"),
                "to": new_players[k].get("status"), "reason": new_players[k].get("reason")}
               for k in sorted(new_players)
               if k in prior_players and prior_players[k].get("status") != new_players[k].get("status")]
    prior_sides = {}
    for r in prior_rows:
        prior_sides[(r.get("game_date"), r.get("matchup"), r.get("team"))] = (
            "NOT_YET_SUBMITTED" if r.get("is_team_not_submitted") else "ROWS")
    new_sides = {}
    for r in new_rows:
        new_sides[(r.get("game_date"), r.get("matchup"), r.get("team"))] = (
            "NOT_YET_SUBMITTED" if r["is_team_not_submitted"] else "ROWS")
    side_changes = [{"key": k, "from": prior_sides.get(k), "to": new_sides.get(k)}
                    for k in sorted(set(prior_sides) | set(new_sides))
                    if prior_sides.get(k) != new_sides.get(k)]
    return {
        "prior_label": prior_label,
        "prior_report": prior_url,
        "prior_report_stamp": prior_stamp,
        "new_report": URL_NEW,
        "new_report_stamp": "2026-11-16 01:45 PM ET",
        "player_rows_added": added,
        "player_rows_removed": removed,
        "status_changes": changed,
        "team_side_changes": side_changes,
    }


def main():
    new_rows = parse_injury_raw(RAW_NEW)
    consec_rows = parse_injury_raw(RAW_CONSEC)
    prior = json.load(open(PRIOR_JSON, encoding="utf-8")) if os.path.exists(PRIOR_JSON) else {}

    player_rows = [r for r in new_rows if not r["is_team_not_submitted"]]
    nys = [r for r in new_rows if r["is_team_not_submitted"]]
    doc = {
        "source_url": URL_NEW,
        "index_url": INDEX,
        "source_label": ("NBA official injury report PDF, 11/16/26 01:45 PM ET — the newest "
                         "report listed on the official index at read time (the 11/16 index "
                         "entry ran 12:00 AM through 1:45 PM ET)."),
        "report_stamp": "2026-11-16 01:45 PM ET",
        "report_revision_time": "2026-11-16 01:45 PM ET",
        "retrieved_on": "2026-11-16",
        "retrieved_stamp": RETRIEVED_WINDOW,
        "retrieval": ("fetch_page, PDF text extraction, 2 chunks joined at the printed page "
                      "break; the fetch tool does not return a per-fetch timestamp"),
        "raw_file": "data/app/official_injuries_2026-11-16_0145PM_raw.md",
        "raw_sha256": hashlib.sha256(open(RAW_NEW, "rb").read()).hexdigest(),
        "count": len(new_rows),
        "player_rows": len(player_rows),
        "not_submitted_rows": len(nys),
        "rows": new_rows,
        "extraction_quirks": quirks(RAW_NEW, new_rows),
        "extraction_quirks_note": ("verbatim table lines that the PDF extraction shifted "
                                   "columns on — kept exactly as printed, never repaired"),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")

    d_consec = diff(new_rows, consec_rows, "consecutive predecessor (15 minutes earlier)",
                    URL_CONSEC, "2026-11-16 01:30 PM ET")
    d_prior = diff(new_rows, prior.get("rows", []),
                   "previous archived report (2026-11-15 06:15 AM ET)",
                   prior.get("source_url"), prior.get("report_stamp"))
    delta = {
        "new_report": URL_NEW,
        "new_report_stamp": "2026-11-16 01:45 PM ET",
        "retrieved_stamp": RETRIEVED_WINDOW,
        "diff_consecutive": d_consec,
        "diff_previous_archived": d_prior,
        "notes": [
            ("Consecutive filings 15 minutes apart (01:30 PM -> 01:45 PM): player rows are "
             "compared on (game date, team, player)."),
            ("The 01:45 PM filing prints 'Mathurin, Bennedict' where the 01:30 PM filing "
             "prints 'Mathurin, Benedict' (New Orleans). Both spellings are kept exactly as "
             "printed by each official document; the diff shows one removed and one added — "
             "nothing is reconciled."),
        ],
        "sources": [URL_NEW, URL_CONSEC,
                    prior.get("source_url"), INDEX],
    }
    with open(OUT_DELTA, "w", encoding="utf-8") as fh:
        json.dump(delta, fh, indent=1)
        fh.write("\n")

    print(f"injuries 2026-11-16 01:45 PM: {len(player_rows)} player rows, "
          f"{len(nys)} NOT YET SUBMITTED sides, {len(doc['extraction_quirks'])} extraction quirk line(s)")
    print(f"diff vs consecutive 01:30 PM: +{len(d_consec['player_rows_added'])} "
          f"-{len(d_consec['player_rows_removed'])} changed {len(d_consec['status_changes'])}; "
          f"vs 11/15 06:15 AM: +{len(d_prior['player_rows_added'])} "
          f"-{len(d_prior['player_rows_removed'])} changed {len(d_prior['status_changes'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
