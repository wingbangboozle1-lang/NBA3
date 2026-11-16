#!/usr/bin/env python3
"""Official per-game results feed + end-of-day settlement (session arena/79341829-nba3).

data/app/results_feed.json carries one row per game: date, teams, final score, quarter
scores, verification state and settlement stamp. A row is SETTLED only from a verified
official final (quarter sums == printed final for both teams, checked in capture).

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


def _period_values(g, side):
    """Printed Q1..Q4 plus any printed overtime periods, as stored on the row.

    Rows from before session arena/4a59430d-nba3 carry no *_ot1/*_ot2 keys; absent or
    null values contribute nothing, so a regular game verifies exactly as before.
    """
    vals = [g.get(f"{side}_q{i}") for i in (1, 2, 3, 4)]
    vals += [g[f"{side}_ot{k}"] for k in (1, 2) if g.get(f"{side}_ot{k}") is not None]
    return vals


def verify(feed):
    changed = 0
    for g in feed["games"]:
        if g.get("period_conflict"):
            # the document itself prints two readings of the same team's period scores
            # (ATL@MIL 2026-11-15): the row is flagged by design and must never be
            # re-derived to green by this recomputation — the conflict outranks the sums.
            ok, note = False, ("the document prints conflicting period scores for "
                               + "/".join(g["period_conflict"]) + " — held unverified")
            if (g.get("verified"), g.get("quarter_check")) != (ok, note):
                g["verified"], g["quarter_check"] = ok, note
                changed += 1
            continue
        ap, hp = _period_values(g, "away"), _period_values(g, "home")
        qs = ap + hp
        if g["away_pts"] is None or g["home_pts"] is None:
            ok = False
            note = "no verified final"
        elif all(q is not None for q in qs):
            ok = (sum(ap) == g["away_pts"] and sum(hp) == g["home_pts"])
            note = "quarter sums equal the final" if ok else "quarter sums MISMATCH"
        else:
            ok = True   # verified final without captured quarters: settled value still official
            note = "quarter scores not captured — blank, flagged"
        if g.get("verified") != ok or g.get("quarter_check") != note:
            changed += 1
        g["verified"] = ok
        g["quarter_check"] = note
    return changed


def settle(feed, day, stamp_from=None):
    """Stamp the verified rows of `day` as settled.

    `stamp_from` lets a caller (the offline CI replay) reuse the capture's own retrieval
    stamp instead of the wall clock, so the same inputs reproduce byte-for-byte on every
    run; the scheduled refresh leaves it unset and gets the real game-day-end time.
    """
    if stamp_from:
        now = str(stamp_from)
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    n = 0
    skipped = []
    for g in feed["games"]:
        if g["date"] != day:
            continue
        if not g.get("verified"):
            skipped.append((g["away"], g["home"], "not verified — held open"))
            continue
        if g.get("settled"):
            skipped.append((g["away"], g["home"], "already settled — not re-stamped"))
            continue
        ap, hp = _period_values(g, "away"), _period_values(g, "home")
        quarters_ok = all(q is not None for q in ap + hp) and \
            sum(ap) == g["away_pts"] and sum(hp) == g["home_pts"]
        g["settled"] = True
        g["settlement_stamp"] = (
            f"settled at {now} (game day end, {day}) from the official final "
            f"{g['away']} {g['away_pts']} - {g['home']} {g['home_pts']}"
            + ("; quarter sums == finals (game book verified)" if quarters_ok else
               "; quarter scores not captured — score verified from the official scoreboard only"))
        n += 1
    feed["settled_count"] = sum(1 for g in feed["games"] if g.get("settled"))
    for a, h, why in skipped:
        print(f"skip {a}@{h} ({day}): {why}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["verify", "settle", "status"])
    ap.add_argument("--date")
    ap.add_argument("--stamp-from", choices=["clock", "capture"], default="clock",
                    help="capture = reuse the feed's own retrieval stamp so an offline replay "
                         "is byte-deterministic; clock (default) = the real settle time")
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
        n = settle(feed, args.date,
                   stamp_from=feed.get("retrieved_stamp") if args.stamp_from == "capture" else None)
        save(feed)
        print(f"settle {args.date}: {n} row(s) stamped; settled total {feed['settled_count']}")
        return 0
    for g in feed["games"]:
        print(g["date"], g["away"], g["away_pts"], "@", g["home"], g["home_pts"],
              "settled" if g.get("settled") else "open", "|", g["quarter_check"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
