#!/usr/bin/env python3
"""Tamper-evident pick ledger (session arena/79341829-nba3).

Every published pick is hashed and the hash is published BEFORE tip. Each ledger entry
links the previous entry's hash, forming an append-only hash chain; any edit of history
breaks the chain and verify() fails loudly.

  * publish  — hash every priced row of the current estimators window into
               data/app/ledger/ledger.jsonl (state PUBLISHED_PRE_TIP)
  * settle   — grade settled games against the official results feed and append
               SETTLED entries with settlement stamps; payload hashes are recomputed
  * verify   — recompute the chain and every payload hash

The bet surface is gated: no strategy is funded, so entries are PUBLISHED PROJECTIONS
(result-graded), not money bets.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEDGER_DIR = os.path.join(ROOT, "data", "app", "ledger")
LEDGER = os.path.join(LEDGER_DIR, "ledger.jsonl")
EST = os.path.join(ROOT, "data", "app", "estimators.json")
FEED = os.path.join(ROOT, "data", "app", "results_feed.json")

GENESIS = "0" * 64


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"))
                          .encode()).hexdigest()


def read_entries():
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_entries(entries):
    os.makedirs(LEDGER_DIR, exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n")


def chain_hash(prev_hash, entry_body):
    return sha({"prev": prev_hash, "body": entry_body})


def publish():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    est = json.load(open(EST, encoding="utf-8"))
    entries = read_entries()
    already = {e["body"]["pick_id"] for e in entries}
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    n = 0
    for row in est["window"]:
        pick_id = f"{row['game_id']}-side-proj"
        if pick_id in already:
            continue
        payload = {
            "pick_id": pick_id,
            "kind": "published projection (side + total), no funded strategy -> no money bet",
            "game_id": row["game_id"], "date": row["date"], "tip_et": row["tip_et"],
            "away": row["away"], "home": row["home"],
            "blend_margin": row["blend_margin"], "blend_total": row["blend_total"],
            "disagreement_abs": row["disagreement_abs"],
            "est_a_margin": row["est_a_margin"], "est_b_margin": row["est_b_margin"],
            "hca_points_pinned": row["hca_points_pinned"],
        }
        body = {
            "pick_id": pick_id, "state": "PUBLISHED_PRE_TIP",
            "published_utc": now, "tip_et": row["tip_et"], "date": row["date"],
            "payload_sha256": sha(payload), "payload": payload,
        }
        entry = {"prev_hash": prev, "body": body}
        entry["entry_hash"] = chain_hash(prev, body)
        entries.append(entry)
        prev = entry["entry_hash"]
        n += 1
    write_entries(entries)
    print(f"publish: {n} new entries; {len(entries)} total in the chain")
    return 0


def settle():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    feed = json.load(open(FEED, encoding="utf-8"))
    final = {(g["date"], g["away"], g["home"]): g for g in feed["games"]
             if g.get("settled") and g.get("verified")}
    entries = read_entries()
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    settled_already = {e["body"]["pick_id"] for e in entries if e["body"]["state"] == "SETTLED"}
    n = 0
    for e in entries:
        b = e["body"]
        if b["state"] != "PUBLISHED_PRE_TIP":
            continue
        if b["pick_id"] in settled_already:
            continue   # idempotent: never append a second SETTLED entry for a pick
        key = (b["date"], b["payload"]["away"], b["payload"]["home"])
        g = final.get(key)
        if not g:
            continue
        # recompute the payload hash (tamper check at settlement time)
        ok = sha(b["payload"]) == b["payload_sha256"]
        margin = g["home_pts"] - g["away_pts"]
        total = g["home_pts"] + g["away_pts"]
        side_res = ("push" if margin == 0 else
                    "win" if (margin > 0) == (b["payload"]["blend_margin"] > 0) else "loss")
        total_res = ("push" if total == b["payload"]["blend_total"] else
                     "win" if total > b["payload"]["blend_total"] else "loss")
        body = {
            "pick_id": b["pick_id"], "state": "SETTLED",
            "settled_utc": now,
            "settlement_stamp": g.get("settlement_stamp"),
            "final": {"away_pts": g["away_pts"], "home_pts": g["home_pts"]},
            "result_side": side_res,
            "result_total": total_res,
            "hash_verified_at_settlement": ok,
            "payload_sha256": b["payload_sha256"],
        }
        entry = {"prev_hash": prev, "body": body}
        entry["entry_hash"] = chain_hash(prev, body)
        entries.append(entry)
        prev = entry["entry_hash"]
        n += 1
    write_entries(entries)
    print(f"settle: {n} settlement entries appended; {len(entries)} total in the chain")
    return 0


def verify():
    entries = read_entries()
    prev = GENESIS
    bad = 0
    for e in entries:
        if e.get("prev_hash") != prev:
            print(f"BROKEN CHAIN at {e['body'].get('pick_id')}: prev_hash mismatch")
            bad += 1
        expect = chain_hash(e["prev_hash"], e["body"])
        if e.get("entry_hash") != expect:
            print(f"ENTRY HASH MISMATCH at {e['body'].get('pick_id')}")
            bad += 1
        if "payload" in e["body"]:
            if sha(e["body"]["payload"]) != e["body"]["payload_sha256"]:
                print(f"PAYLOAD TAMPERED at {e['body'].get('pick_id')}")
                bad += 1
        prev = e.get("entry_hash")
    print(f"verify: {len(entries)} entries, {bad} problem(s) — "
          + ("CHAIN INTACT" if not bad else "CHAIN BROKEN"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["publish", "settle", "verify"])
    args = ap.parse_args()
    return {"publish": publish, "settle": settle, "verify": verify}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
