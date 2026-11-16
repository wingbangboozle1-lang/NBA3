#!/usr/bin/env python3
"""Extend the per-game results feed with the 2026-11-15 verified finals (session
arena/c94a5531-nba3).  Two roles:

1. Library: scripts/capture_round_79341829.py calls build_feed_doc() during its
   offline CI replay so the replayed feed byte-matches the committed feed
   (the CI drift gate compares data/app/results_feed.json after the replay).
2. CLI:  python3 scripts/extend_results_feed_2026_11_15c.py  — idempotent in-place
   extension of data/app/results_feed.json (rows keyed by (date, away, home)).

Input:  data/app/official_results_2026-11-15_c94a5531.json  (capture output: two
        finals verified from two agreeing official reads, quarter sums == finals).
Rows are added UNSETTLED and settled once via scripts/results_feed.py settle.
Settlement stamps are never recomputed: they are preserved across re-captures
from the existing feed and, failing that, from the settlement stamp recorded in
the tamper-evident pick ledger's SETTLED entries.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
SRC = os.path.join(APP, "official_results_2026-11-15_c94a5531.json")
FEED = os.path.join(APP, "results_feed.json")
LEDGER = os.path.join(APP, "ledger", "ledger.jsonl")

NEW_SOURCES = [
    "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
    "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
    "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf",
    "https://statsdmz.nba.com/pdfs/20261115/20261115_SASUTA.pdf",
    "https://www.nba.com/games?date=2026-11-15",
]

SOURCE_LABEL = (
    "Official per-game results feed. 2026-11-14 rows come from the official game "
    "books (statsdmz.nba.com PDFs linked from each nba.com game page); 2026-11-13 "
    "rows come from the stored official scoreboard capture (data/app/official_results_2026-11-13.json); "
    "2026-11-15 rows come from the game-day evening capture (game books + scoreboard "
    "cards agreeing, data/app/official_results_2026-11-15_c94a5531.json). "
    "One row per game: date, teams, final score, quarter scores."
)

# C3 flag amendment: the previous wording ("Rows without captured quarter scores
# stay unsettled and flagged") contradicted settle() behavior — the 2026-11-13
# rows settled without quarters and carry a flag in the settlement stamp. The
# rule below describes what the pipeline actually does.
SETTLEMENT_RULE = (
    "A row is settled only when the game state is Final AND verified from an "
    "official source; when quarter scores are captured they must sum to the "
    "printed final for both teams (checked offline). Rows without captured "
    "quarter scores settle from the verified final alone and carry the flag "
    "'quarter scores not captured' in the settlement stamp. (Wording amended "
    "2026-11-15 by arena/c94a5531-nba3 after flagging that the previous text "
    "contradicted settle() behavior on the 2026-11-13 rows.)"
)


def _key(g):
    return (g["date"], g["away"], g["home"])


def stamps_from_ledger():
    """Settlement stamps recorded in the pick ledger's SETTLED entries, keyed by
    (date, away, home) via each settled pick's published pre-tip entry."""
    if not os.path.exists(LEDGER):
        return {}
    entries = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    picks = {}
    for e in entries:
        b = e["body"]
        if b.get("state") == "PUBLISHED_PRE_TIP":
            picks[b["pick_id"]] = (b["date"], b["payload"]["away"], b["payload"]["home"])
    out = {}
    for e in entries:
        b = e["body"]
        if b.get("state") == "SETTLED" and b.get("settlement_stamp"):
            k = picks.get(b["pick_id"])
            if k:
                out[k] = b["settlement_stamp"]
    return out


def rows_1115():
    """The two verified-final rows from the capture output (quarter sums checked)."""
    res = json.load(open(SRC, encoding="utf-8"))
    rows = []
    for g in res["games"]:
        qs = [g[f"{s}_q{i}"] for s in ("away", "home") for i in (1, 2, 3, 4)]
        if not (sum(qs[:4]) == g["away_pts"] and sum(qs[4:]) == g["home_pts"]):
            raise SystemExit(f"REFUSING {_key(g)}: quarter sums != final")
        rows.append({
            "date": g["date"], "away": g["away"], "home": g["home"],
            "away_pts": g["away_pts"], "home_pts": g["home_pts"],
            "away_q1": g["away_q1"], "away_q2": g["away_q2"],
            "away_q3": g["away_q3"], "away_q4": g["away_q4"],
            "home_q1": g["home_q1"], "home_q2": g["home_q2"],
            "home_q3": g["home_q3"], "home_q4": g["home_q4"],
            "state": "Final",
            "verified": True,
            "verified_from": g["verified_from"],
            "quarter_check": "quarter sums equal the final",
            "gamebook": g["gamebook"],
            "raw_file": g["raw_file"],
            "settled": False,
            "settlement_stamp": None,
        })
    return rows, res["retrieved_stamp"]


def build_feed_doc(feed_rows, prev_feed=None, base_sources=None):
    """Assemble the full feed document: base rows + the 11/15 evening rows, sorted
    by (date, away, home), metadata applied, settlement stamps preserved from
    prev_feed (or the pick ledger) — never recomputed. Rows the capture does not
    regenerate (e.g. promoted later by the scheduled refresh) are carried through
    verbatim so the CI replay stays byte-stable as live rows accumulate."""
    rows, retrieved_stamp = rows_1115()
    have = {_key(g) for g in feed_rows}
    for r in rows:
        if _key(r) not in have:
            feed_rows.append(r)
    if prev_feed:
        for g in prev_feed.get("games", []):
            if _key(g) not in have and _key(g) not in {_key(r) for r in rows}:
                feed_rows.append(g)   # carry-through of live/promoted rows
    feed_rows.sort(key=_key)

    prev_stamps = {}
    if prev_feed:
        for g in prev_feed.get("games", []):
            if g.get("settled"):
                prev_stamps[_key(g)] = g.get("settlement_stamp")
    prev_stamps.update({k: v for k, v in stamps_from_ledger().items()
                        if k not in prev_stamps})
    for r in feed_rows:
        k = _key(r)
        if k in prev_stamps:
            r["settled"] = True
            r["settlement_stamp"] = prev_stamps[k]

    # sources: the base capture's list first (stable replay order), then the
    # evening capture's sources appended once
    sources = list(base_sources or (prev_feed or {}).get("sources", []))
    for u in NEW_SOURCES:
        if u not in sources:
            sources.append(u)
    return {
        "source_label": SOURCE_LABEL,
        "retrieved_stamp": retrieved_stamp,
        "settlement_rule": SETTLEMENT_RULE,
        "count": len(feed_rows),
        "settled_count": sum(1 for r in feed_rows if r.get("settled")),
        "games": feed_rows,
        "sources": sources,
    }


def main():
    feed = json.load(open(FEED, encoding="utf-8"))
    doc = build_feed_doc(feed["games"], prev_feed=feed)
    with open(FEED, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(f"results_feed: {doc['count']} rows, {doc['settled_count']} settled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
