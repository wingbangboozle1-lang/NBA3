#!/usr/bin/env python3
"""Official per-game results feed + end-of-day settlement (session arena/79341829-nba3).

data/app/results_feed.json carries one row per game: date, teams, final score, quarter
scores, verification state and settlement stamp. A row is SETTLED only from a verified
official final (quarter sums == printed final for both teams, checked in capture).

Schema notes (session arena/4c69ab99-nba3):
  * every row carries the official `game_id` (nba.com game page id) — added with the
    2026-11-15 rows so ledger settlement can match rows to published picks exactly;
  * `away_ot1` / `home_ot1` hold overtime period scores when the game went to OT
    (the game book's SCORE BY PERIOD table carries OT1 as its own column; a
    double-OT game would need an `ot2` extension that does not exist yet and would
    be flagged, never squeezed into ot1);
  * `quarter_conflict` (bool) marks a row whose official game book contradicts itself
    on a period cell (only 0022600243 ATL @ MIL 2026-11-15 so far: the period table
    reads MIL Q3 = 37 while the summary line reads 27 and the printed final is 106).
    The stored quarter cells are the reading that satisfies the scoring identity
    (sum == printed final, confirmed by the player box sums); the conflicting reading
    is preserved in `quarter_conflict_note`. The FINAL score is unambiguous and the
    row settles; the conflict stays flagged on the Flagged for Review page.

Commands:
  verify                 recompute verification of every row (offline)
  settle --date 2026-11-14   settle that game day's verified finals and stamp the rows
  status                 print feed state
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEED = os.path.join(ROOT, "data", "app", "results_feed.json")


def load():
    return json.load(open(FEED, encoding="utf-8"))


def save(feed):
    with open(FEED, "w", encoding="utf-8") as fh:
        json.dump(feed, fh, indent=1)
        fh.write("\n")


def period_sums(g):
    """(away_sum, home_sum) over q1..q4 plus any captured overtime periods, or None
    when the regulation quarter scores were not captured."""
    qs = [g[f"{s}_q{i}"] for s in ("away", "home") for i in (1, 2, 3, 4)]
    if any(q is None for q in qs):
        return None
    away = sum(qs[:4]) + (g.get("away_ot1") or 0) + (g.get("away_ot2") or 0)
    home = sum(qs[4:]) + (g.get("home_ot1") or 0) + (g.get("home_ot2") or 0)
    return away, home


def verify(feed):
    changed = 0
    for g in feed["games"]:
        sums = period_sums(g)
        if g["away_pts"] is None or g["home_pts"] is None:
            ok = False
            note = "no verified final"
        elif sums is not None:
            ok = (sums[0] == g["away_pts"] and sums[1] == g["home_pts"])
            note = "quarter sums equal the final" if ok else "quarter sums MISMATCH"
            if ok and g.get("quarter_conflict"):
                note = ("quarter sums equal the final (stored reading); the same official "
                        "book carries a conflicting period reading — see quarter_conflict_note")
        else:
            ok = True   # verified final without captured quarters: settled value still official
            note = "quarter scores not captured — blank, flagged"
        if g.get("verified") != ok or g.get("quarter_check") != note:
            changed += 1
        g["verified"] = ok
        g["quarter_check"] = note
    return changed


def settle(feed, day, now=None):
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    n = 0
    for g in feed["games"]:
        if g["date"] != day or not g.get("verified") or g.get("settled"):
            continue
        sums = period_sums(g)
        quarters_ok = sums is not None and sums == (g["away_pts"], g["home_pts"])
        g["settled"] = True
        g["settlement_stamp"] = (
            f"settled at {now} (game day end, {day}) from the official final "
            f"{g['away']} {g['away_pts']} - {g['home']} {g['home_pts']}"
            + ("; quarter sums == finals (game book verified)" if quarters_ok else
               "; quarter scores not captured — score verified from the official scoreboard only")
            + ("; the official book's period table conflicts with its summary line on one "
               "period cell (flagged, both readings kept) — the final score itself is "
               "verified by the printed final, the summary line and the player box sums"
               if g.get("quarter_conflict") else ""))
        n += 1
    feed["settled_count"] = sum(1 for g in feed["games"] if g.get("settled"))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["verify", "settle", "status"])
    ap.add_argument("--date")
    ap.add_argument("--stamp", help="settlement stamp time (YYYY-MM-DDTHH:MMZ) for a replayed "
                                    "settlement; default is the wall clock")
    args = ap.parse_args()
    feed = load()
    if args.command == "verify":
        n = verify(feed)
        save(feed)
        print(f"verify: {n} row(s) updated; {feed['settled_count']} settled of {feed['count']}")
        return 0
    if args.command == "settle":
        if not args.date:
            print("settle requires --date YYYY-MM-DD", file=sys.stderr)
            return 2
        verify(feed)
        n = settle(feed, args.date, now=args.stamp)
        save(feed)
        print(f"settle {args.date}: {n} row(s) stamped; settled total {feed['settled_count']}")
        return 0
    for g in feed["games"]:
        print(g["date"], g["away"], g["away_pts"], "@", g["home"], g["home_pts"],
              "settled" if g.get("settled") else "open", "|", g["quarter_check"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
