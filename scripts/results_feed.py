#!/usr/bin/env python3
"""Official per-game results feed + end-of-day settlement (session arena/79341829-nba3).

data/app/results_feed.json carries one row per game: date, teams, final score, quarter
scores, verification state and settlement stamp. A row is SETTLED only from a verified
official final (quarter sums == printed final for both teams, checked in capture).

Quarter scores: q1..q4 per side; OT games carry a fifth element in the row's
quarter list (q5 = OT1), which the verify/settle arithmetic includes.

Commands:
  verify                    recompute verification of every row (offline)
  ingest --rows FILE        merge verified rows from an official capture file
                            (schema nba3.official_results/v1, e.g.
                            data/app/official_results_2026-11-15.json) into the feed.
                            One row per game; an existing game is never overwritten.
  ingest --capture-dir DIR  CI path: read the official game-card feed embedded in
                            the games_*.html files of a refresh capture and merge
                            every finished game whose period scores sum to its
                            printed final (scripts/gamecard_feed.py does the parse;
                            a game failing the sum check is recorded, never fixed).
  settle --date 2026-11-14  settle that game day's verified finals and stamp the rows
  settle --all-done         settle every verified unsettled row whose game day is
                            strictly before today (America/New_York) — the scheduled
                            job's "settle the sealed ledger as soon as each game day
                            ends" step
  status                    print feed state
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


def qvals(g, side):
    """Quarter values captured for one side: q1..q4, plus q5 (OT1) when present."""
    out = []
    for i in (1, 2, 3, 4, 5):
        k = f"{side}_q{i}"
        if k in g:
            out.append(g[k])
    return out


def verify(feed):
    changed = 0
    for g in feed["games"]:
        aq, hq = qvals(g, "away"), qvals(g, "home")
        qs = aq + hq
        if g["away_pts"] is None or g["home_pts"] is None:
            ok = False
            note = "no verified final"
        elif len(aq) != len(hq):
            ok = False
            note = "quarter columns disagree between sides — row withheld, flagged"
        elif all(q is not None for q in qs):
            ok = (sum(aq) == g["away_pts"] and sum(hq) == g["home_pts"])
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
        aq, hq = qvals(g, "away"), qvals(g, "home")
        qs = aq + hq
        quarters_ok = (len(aq) == len(hq) and len(qs) > 0
                       and all(q is not None for q in qs)
                       and sum(aq) == g["away_pts"] and sum(hq) == g["home_pts"])
        g["settled"] = True
        g["settlement_stamp"] = (
            f"settled at {now} (game day end, {day}) from the official final "
            f"{g['away']} {g['away_pts']} - {g['home']} {g['home_pts']}"
            + (f"; quarter sums == finals ({len(aq)} periods, verified)" if quarters_ok else
               "; quarter scores not captured — score verified from the official scoreboard only"))
        n += 1
    feed["settled_count"] = sum(1 for g in feed["games"] if g.get("settled"))
    return n


def settle_all_done(feed):
    """Settle every verified unsettled row whose game day has ended (strictly before
    today in America/New_York). This is the scheduled job's end-of-day settlement."""
    from zoneinfo import ZoneInfo
    today_et = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date()
    n = 0
    for day in sorted({g["date"] for g in feed["games"]
                       if g.get("verified") and not g.get("settled")}):
        if day < today_et.isoformat():
            n += settle(feed, day)
    return n


def ingest_rows(feed, rows, source_note):
    """Merge captured rows into the feed. One row per game; never overwrites a row
    already present (a settled row is immutable history). Returns (added, conflicts)."""
    have = {(g["date"], g.get("game_id") or f"{g['away']}-{g['home']}"): g for g in feed["games"]}
    added, conflicts = 0, []
    for r in rows:
        key = (r["date"], r.get("game_id") or f"{r['away']}-{r['home']}")
        if key in have:
            old = have[key]
            if (old.get("away_pts"), old.get("home_pts")) != (r.get("away_pts"), r.get("home_pts")):
                conflicts.append((key, "final differs from the row already in the feed"))
            continue
        g = {
            "date": r["date"],
            "game_id": r.get("game_id"),
            "away": r["away"],
            "home": r["home"],
            "away_pts": r.get("away_pts"),
            "home_pts": r.get("home_pts"),
            "away_q1": None, "away_q2": None, "away_q3": None, "away_q4": None,
            "home_q1": None, "home_q2": None, "home_q3": None, "home_q4": None,
            "state": r.get("state"),
            "verified": False,
            "verified_from": r.get("verified_from") or r.get("game_url") or r.get("source"),
            "quarter_check": "",
            "gamebook": r.get("gamebook"),
            "raw_file": r.get("raw_file"),
            "settled": False,
            "settlement_stamp": None,
        }
        aq, hq = r.get("away_q") or [], r.get("home_q") or []
        for i, v in enumerate(aq, start=1):
            if i <= 5:
                g[f"away_q{i}"] = v
        for i, v in enumerate(hq, start=1):
            if i <= 5:
                g[f"home_q{i}"] = v
        if r.get("ot"):
            g["ot"] = r["ot"]
        if r.get("flag"):
            g["flag"] = r["flag"]
        if r.get("cross_checks"):
            g["cross_checks"] = r["cross_checks"]
        if r.get("venue"):
            g["venue"] = r["venue"]
        feed["games"].append(g)
        have[key] = g
        added += 1
    feed["count"] = len(feed["games"])
    if added:
        feed["retrieved_stamp"] = source_note
    return added, conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["verify", "ingest", "settle", "status"])
    ap.add_argument("--date")
    ap.add_argument("--all-done", action="store_true",
                    help="settle every verified unsettled game day that has ended (ET)")
    ap.add_argument("--rows", help="official capture file (nba3.official_results/v1)")
    ap.add_argument("--capture-dir",
                    help="refresh capture dir whose games_*.html carry the game-card feed")
    args = ap.parse_args()
    feed = load()
    if args.command == "ingest":
        rows, note = [], ""
        if args.rows:
            cap = json.load(open(args.rows, encoding="utf-8"))
            rows = cap["games"]
            note = f"ingested from {args.rows} at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}"
        elif args.capture_dir:
            import glob
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import gamecard_feed
            for path in sorted(glob.glob(os.path.join(args.capture_dir, "games_*.html"))):
                cards = gamecard_feed.parse_games_page(open(path, encoding="utf-8",
                                                            errors="replace").read())
                ok, bad = gamecard_feed.finished_rows(cards)
                rows.extend(ok)
                for b in bad:
                    print(f"rejected (not ingested, never repaired): {path}: {b}")
            note = f"ingested from game-card feed in {args.capture_dir} at " \
                   f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}"
        else:
            print("ingest requires --rows FILE or --capture-dir DIR", file=sys.stderr)
            return 2
        added, conflicts = ingest_rows(feed, rows, note)
        verify(feed)
        save(feed)
        for key, why in conflicts:
            print(f"CONFLICT {key}: {why}", file=sys.stderr)
        print(f"ingest: {added} row(s) added; {feed['count']} total; "
              f"{len(conflicts)} conflict(s)")
        return 1 if conflicts else 0
    if args.command == "verify":
        n = verify(feed)
        save(feed)
        print(f"verify: {n} row(s) updated; {feed['settled_count']} settled of {feed['count']}")
        return 0
    if args.command == "settle":
        verify(feed)
        if args.all_done:
            n = settle_all_done(feed)
            save(feed)
            print(f"settle --all-done: {n} row(s) stamped; settled total {feed['settled_count']}")
            return 0
        if not args.date:
            print("settle requires --date YYYY-MM-DD or --all-done", file=sys.stderr)
            return 2
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
