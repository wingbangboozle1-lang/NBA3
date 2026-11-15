#!/usr/bin/env python3
"""Pre-registration freezer (session arena/79341829-nba3).

Every strategy is frozen BEFORE its first bet: signal, thresholds, universe and an exact
settlement rule are written to data/app/prereg/<strategy_id>.json with a sha256. A frozen
file is never overwritten (freeze refuses); edits require a NEW file version and a note.

  * freeze   — write prereg files for every strategy in data/app/canonical.json
  * verify   — recompute hashes and confirm each frozen file still matches

Commands run offline so CI can replay them deterministically.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANON = os.path.join(ROOT, "data", "app", "canonical.json")
PREREG = os.path.join(ROOT, "data", "app", "prereg")

SETTLEMENT_RULE = (
    "Settle from the OFFICIAL final score only (nba.com scoreboard / official game book; "
    "quarter sums must equal the printed final). A side pick on team T at our originated "
    "line covers when (T score - opponent score + line_for_T) > 0; a total pick wins when "
    "the official combined final crosses our originated total. Games must reach Final; "
    "void otherwise. Pushes settle as void (stake returned, no P&L). No closing line is "
    "used for settlement — our own originated line is the reference, frozen at publication "
    "and hashed in the pick ledger (data/app/ledger/ledger.jsonl)."
)


def freeze():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    canon = json.load(open(CANON, encoding="utf-8"))
    os.makedirs(PREREG, exist_ok=True)
    made = 0
    for s in canon["strategies"]:
        path = os.path.join(PREREG, f"{s['id']}.json")
        if os.path.exists(path):
            print(f"skip {s['id']}: already frozen (never overwritten)")
            continue
        doc = {
            "strategy_id": s["id"],
            "name": s["name"],
            "family": s["family"],
            "signal": s["rule"],
            "thresholds": {
                "expected_edge_pp": s["edge_pp"],
                "hit_rate": s["rate"],
                "top_band_hit_rate": s.get("top_band_hit_rate"),
                "clv_pp": s.get("clv_pp"),
                "sample_n": s.get("n"),
                "gates": s["gates"],
            },
            "universe": (
                "All regular-season games in the stored official log "
                "(data/origin/games.csv, 183 verified finals) for research; the live "
                "universe is the rolling window of official schedule games priced at most "
                "three days ahead (data/app/official_slate_1115_1118.json and successors)."
            ),
            "settlement_rule": SETTLEMENT_RULE,
            "frozen_utc": now,
            "frozen_before_first_bet": True,
            "note": ("No strategy is funded and no money bet has been placed; this file is "
                     "the pre-registration of the research rules (T1 tier) as published on "
                     "the strategy leaderboard."),
            "sources": ["data/app/canonical.json", s.get("source")],
        }
        doc["sha256"] = hashlib.sha256(
            json.dumps({k: v for k, v in doc.items() if k != "sha256"},
                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
            fh.write("\n")
        made += 1
    print(f"freeze: {made} new prereg file(s) written to data/app/prereg/")
    return 0


def verify():
    bad = 0
    if not os.path.isdir(PREREG):
        print("verify: no prereg directory")
        return 1
    for f in sorted(os.listdir(PREREG)):
        if not f.endswith(".json"):
            continue
        doc = json.load(open(os.path.join(PREREG, f), encoding="utf-8"))
        expect = hashlib.sha256(
            json.dumps({k: v for k, v in doc.items() if k != "sha256"},
                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if doc.get("sha256") != expect:
            print(f"PREREG TAMPERED: {f}")
            bad += 1
    print(f"verify: {len(os.listdir(PREREG))} file(s), {bad} problem(s)")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["freeze", "verify"])
    args = ap.parse_args()
    return {"freeze": freeze, "verify": verify}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
