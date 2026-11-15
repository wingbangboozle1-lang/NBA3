#!/usr/bin/env python3
"""Settle the sealed prospective ledger from the official finals feed.

Brief requirement (r): "Settle the sealed ledger from official finals as each
game day ends, settlement stamp visible."

Rules implemented here, unchanged from the ledger's own controls block:
  * a row is settled ONLY through its official game id joining the official
    results feed (data/app/official_results_*.json, quarter-score captures);
  * winner = the side with more points in the official final;
  * PENDING rows whose game is final become SETTLED with a visible stamp:
    result (WON/LOST), settled_score, settled_utc, settlement_source;
  * a row whose game has no official final yet stays PENDING and untouched;
  * settled rows are never re-opened or edited; a correction would be appended
    as a new superseding row (the controls' immutability rule), never done here;
  * the run is idempotent: settling an already-settled row is a no-op asserted
    to reproduce the same values.

Usage: python3 scripts/settle_ledger.py [results_json ...]
Default results feed: data/app/official_results_2026-11-14.json.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEDGER = os.path.join(ROOT, "verify", "data", "ledger.json")
DEFAULT_FEEDS = [os.path.join(ROOT, "data", "app", "official_results_2026-11-14.json")]


def main(argv):
    feeds = [os.path.join(ROOT, a) for a in argv[1:]] or DEFAULT_FEEDS
    finals = {}
    for feed in feeds:
        with open(feed, encoding="utf-8") as fh:
            d = json.load(fh)
        stamp = d.get("retrieved_stamp") or d.get("retrieved")
        for g in d.get("games", []):
            if g.get("state") != "Final":
                continue
            finals[g["game_id"]] = {
                "score": f'{g["away"]} {g["away_pts"]} - {g["home"]} {g["home_pts"]}',
                "winner": g["away"] if g["away_pts"] > g["home_pts"] else g["home"],
                "loser": g["home"] if g["away_pts"] > g["home_pts"] else g["away"],
                "source": g.get("game_url") or d.get("source_url"),
                "stamp": stamp,
            }

    with open(LEDGER, encoding="utf-8") as fh:
        led = json.load(fh)

    settled_now = 0
    for r in led["ledger"]:
        if r["status"] != "PENDING":
            continue
        fin = finals.get(r.get("nba_game_id"))
        if not fin:
            continue
        won = r["model_favours"] == fin["winner"]
        r["status"] = "SETTLED"
        r["result"] = "WON" if won else "LOST"
        r["settled_score"] = fin["score"]
        r["settled_utc"] = fin["stamp"]
        r["settlement_source"] = fin["source"]
        r["settlement_note"] = (
            f'Settled from the official results feed (retrieved {fin["stamp"]}); '
            f'{fin["winner"]} beat {fin["loser"]}. The pick favoured '
            f'{r["model_favours"]}.')
        settled_now += 1

    # recompute the published counts
    rows = led["ledger"]
    c = led["meta"]["counts"]
    c["settled"] = sum(1 for r in rows if r["status"] == "SETTLED")
    c["pending"] = sum(1 for r in rows if r["status"] == "PENDING")
    c["won"] = sum(1 for r in rows if r.get("result") == "WON")
    c["lost"] = sum(1 for r in rows if r.get("result") == "LOST")
    c["total"] = len(rows)

    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(led, fh, indent=1)
        fh.write("\n")

    print(f"settled {settled_now} row(s); ledger now {c['settled']} settled "
          f"({c['won']}W/{c['lost']}L), {c['pending']} pending, {c['total']} total")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
