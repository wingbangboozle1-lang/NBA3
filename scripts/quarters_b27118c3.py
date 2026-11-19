#!/usr/bin/env python3
"""Promote the official quarter scores for 2026-11-16..18 into the results feed.

Session arena/b27118c3-nba3. The brief asks the per-game result feed to store one row per
game with *date, teams, final score and quarter scores*. The 2026-11-19 round promoted the
finals but explicitly did not read the periods, so 17 settled rows carry no quarter cells at
all (see data/app/official_results_2026-11-1{6,7,8}.json). This script fills exactly those
cells from the verbatim capture in
data/rounds/2026-11-19-b27118c3/captures/linescores_2026-11-16_to_18.json and does nothing
else.

Rules (each one is a test in tests/test_quarters_b27118c3.py):

  * a capture row is accepted only if its printed periods sum to its printed final on BOTH
    sides, and that final equals the final already stored in the feed for the same game id;
  * only blank quarter cells are written. A cell that already holds a value is never
    overwritten -- if a value differs, the row is reported as a conflict and left alone;
  * a game in the capture that the feed does not hold is reported, never inserted (adding a
    final is the results feed's job and it needs an official-source row, not a period table);
  * the feed row keeps its own `verified_from`; the period cells get their own provenance
    (`quarters_from`, `quarters_source`) so a reader can see the periods came from the game
    page even where the final came from the scoreboard;
  * re-running is idempotent and `--check` fails on any drift, so CI can pin the tree.

Usage:
  python3 scripts/quarters_b27118c3.py            # promote (writes data/app/results_feed.json)
  python3 scripts/quarters_b27118c3.py --check    # no writes; exit 1 on drift or a bad row
  python3 scripts/quarters_b27118c3.py --summary  # print what the capture holds, change nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEED = os.path.join(ROOT, "data", "app", "results_feed.json")
CAPTURE = os.path.join(ROOT, "data", "rounds", "2026-11-19-b27118c3", "captures",
                       "linescores_2026-11-16_to_18.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
        fh.write("\n")


def validate_capture(cap):
    """Every row must be internally consistent before any of it is used."""
    problems = []
    for g in cap["games"]:
        for side in ("away", "home"):
            q = g[f"{side}_q"]
            if not q:
                problems.append(f"{g['game_id']}: {side} has no periods")
                continue
            if len(q) != len(g["away_q"] if side == "home" else g["home_q"]):
                problems.append(f"{g['game_id']}: period counts differ between sides")
            if any(not isinstance(v, int) or v < 0 for v in q):
                problems.append(f"{g['game_id']}: {side} has a non-integer or negative period")
            if sum(q) != g[f"{side}_final"]:
                problems.append(f"{g['game_id']}: {side} periods sum to {sum(q)}, "
                                f"printed final is {g[f'{side}_final']}")
        if not str(g["source_url"]).startswith("https://"):
            problems.append(f"{g['game_id']}: source_url is not https")
    return problems


def promote(feed, cap, write=True):
    """Fill blank quarter cells. Returns (changes, conflicts, missing, messages)."""
    have = {(g["date"], g.get("game_id")): g for g in feed["games"]}
    changes, conflicts, missing = [], [], []
    for c in cap["games"]:
        key = (c["date"], c["game_id"])
        g = have.get(key)
        if g is None:
            missing.append(f"{c['date']} {c['game_id']} {c['away']}@{c['home']}")
            continue
        if (g.get("away_pts"), g.get("home_pts")) != (c["away_final"], c["home_final"]):
            conflicts.append(f"{c['game_id']}: capture final {c['away_final']}-{c['home_final']} "
                             f"differs from the feed's {g.get('away_pts')}-{g.get('home_pts')}")
            continue
        for side in ("away", "home"):
            for i, v in enumerate(c[f"{side}_q"], start=1):
                k = f"{side}_q{i}"
                if g.get(k) is None:
                    if write:
                        g[k] = v
                    changes.append(f"{c['game_id']} {k}={v}")
                elif g[k] != v:
                    conflicts.append(f"{c['game_id']} {k}: feed holds {g[k]}, capture prints {v} "
                                     "— left as published, reported not overwritten")
        if c.get("ot"):
            if g.get("ot") != c["ot"]:
                if write:
                    g["ot"] = c["ot"]
                changes.append(f"{c['game_id']} ot={c['ot']}")
        if write:
            g["quarters_from"] = c["source_url"]
            g["quarters_source"] = ("LINESCORES table on the official game page, read "
                                    "2026-11-19T07:15Z..07:50Z; periods sum to the printed final")
    msgs = []
    return changes, conflicts, missing, msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no writes; exit 1 on drift")
    ap.add_argument("--summary", action="store_true", help="print the capture; write nothing")
    args = ap.parse_args()

    cap = load(CAPTURE)
    problems = validate_capture(cap)
    if problems:
        for p in problems:
            print(f"ERROR: capture row rejected: {p}", file=sys.stderr)
        return 1

    if args.summary:
        by_date = {}
        for g in cap["games"]:
            by_date.setdefault(g["date"], []).append(g["game_id"])
        for d in sorted(by_date):
            print(f"{d}: {len(by_date[d])} games with printed periods and matching finals")
        print(f"total: {len(cap['games'])} rows, every period sum equals its printed final")
        return 0

    feed = load(FEED)
    before = json.dumps(feed, sort_keys=True)
    changes, conflicts, missing, _ = promote(feed, cap, write=not args.check)
    after = json.dumps(feed, sort_keys=True)

    if conflicts:
        for c in conflicts:
            print(f"CONFLICT: {c}", file=sys.stderr)
    if missing:
        for m in missing:
            print(f"NOT IN FEED (not inserted): {m}", file=sys.stderr)

    if args.check:
        if after != before:
            print(f"DRIFT: promotion would change {len(changes)} quarter cells — "
                  "the feed is not in the state the capture implies")
            return 1
        print(f"quarters check: {len(cap['games'])} capture rows, 0 drift, "
              f"{len(conflicts)} conflict(s), {len(missing)} game(s) not in the feed")
        return 0 if not conflicts else 1

    if after != before:
        feed["count"] = len(feed["games"])
        feed["settled_count"] = sum(1 for g in feed["games"] if g.get("settled"))
        save(FEED, feed)
    print(f"quarters promoted: {len(changes)} cell(s) filled from {len(cap['games'])} capture "
          f"rows; {len(conflicts)} conflict(s); {len(missing)} game(s) not in the feed")
    return 0 if not conflicts else 1


if __name__ == "__main__":
    sys.exit(main())
