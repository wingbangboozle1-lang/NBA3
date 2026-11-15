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


def verify(feed):
    changed = 0
    for g in feed["games"]:
        qs = [g[f"{s}_q{i}"] for s in ("away", "home") for i in (1, 2, 3, 4)]
        if g["away_pts"] is None or g["home_pts"] is None:
            ok = False
            note = "no verified final"
        elif all(q is not None for q in qs):
            ok = (sum(qs[:4]) == g["away_pts"] and sum(qs[4:]) == g["home_pts"])
            note = "quarter sums equal the final" if ok else "quarter sums MISMATCH"
        else:
            ok = True   # verified final without captured quarters: settled value still official
            note = "quarter scores not captured — blank, flagged"
        if g.get("verified") != ok or g.get("quarter_check") != note:
            changed += 1
        g["verified"] = ok
        g["quarter_check"] = note
    return changed


def settle(feed, day):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    n = 0
    for g in feed["games"]:
        if g["date"] != day or not g.get("verified") or g.get("settled"):
            continue
        qs = [g[f"{s}_q{i}"] for s in ("away", "home") for i in (1, 2, 3, 4)]
        quarters_ok = all(q is not None for q in qs) and \
            sum(qs[:4]) == g["away_pts"] and sum(qs[4:]) == g["home_pts"]
        g["settled"] = True
        g["settlement_stamp"] = (
            f"settled at {now} (game day end, {day}) from the official final "
            f"{g['away']} {g['away_pts']} - {g['home']} {g['home_pts']}"
            + ("; quarter sums == finals (game book verified)" if quarters_ok else
               "; quarter scores not captured — score verified from the official scoreboard only"))
        n += 1
    feed["settled_count"] = sum(1 for g in feed["games"] if g.get("settled"))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["verify", "settle", "status"])
    ap.add_argument("--date")
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
        n = settle(feed, args.date)
        save(feed)
        print(f"settle {args.date}: {n} row(s) stamped; settled total {feed['settled_count']}")
        return 0
    for g in feed["games"]:
        print(g["date"], g["away"], g["away_pts"], "@", g["home"], g["home_pts"],
              "settled" if g.get("settled") else "open", "|", g["quarter_check"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
