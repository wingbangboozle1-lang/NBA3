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
import re
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


SLATE = os.path.join(ROOT, "data", "app", "official_slate_current.json")
ET = ZoneInfo("America/New_York")


_TIP_SUFFIX_RE = re.compile(r"\s*(?:ET|EDT|EST)\s*$", re.I)


def _tip_as_et(tip_str, game_day):
    """'1:00 PM' (or the official page's '8:00 PM ET') on game_day -> aware datetime.

    None is returned only when there is no printed tip at all, or it does not read as a clock time:
    an absent tip means the pre-tip gate cannot be checked, so the pick is not published.

    The trailing zone token matters. nba.com's game card prints the tip as "8:00 PM ET", and the
    promoted slate keeps the value exactly as the page renders it, so a parser that accepted only
    "%I:%M %p" turned a VERIFIED tip into "tip time not verified" — which on 2026-11-19 refused to
    seal all four of the day's games into the ledger before tip-off while publishing the 15 later
    ones. Tolerating the zone suffix (and EDT/EST, which the same page uses across the DST boundary)
    is a parsing fix, not a data change: the tip time written to the entry is still the page's
    string, and the ET interpretation is unchanged because the page's ET is the same zone as ET
    here.
    """
    if not tip_str:
        return None
    txt = _TIP_SUFFIX_RE.sub("", tip_str.strip()).strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.combine(game_day, datetime.strptime(txt, fmt).time(), tzinfo=ET)
        except ValueError:
            continue
    return None


def publish(now_utc=None, est_path=None, slate_path=None):
    """Append PUBLISHED_PRE_TIP entries that are still provably before tip.

    Gates (session c449d46a; each skip is printed with its reason, nothing is inferred):
      * the game's ET date must be today or later (a game dated before today has tipped);
      * a game dated today needs a verified tip time that is still in the future;
      * a game dated later than today is before tip by the calendar;
      * one entry per game id: the window is de-duplicated within the run as well as
        against the chain (the earlier version checked only the chain, so one game id that
        appeared on four dates was appended four times);
      * the (date, game_id) pair must be on the official promoted slate.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    now = now_utc.strftime("%Y-%m-%dT%H:%MZ")
    today_et = now_utc.astimezone(ET).date()
    est = json.load(open(est_path or EST, encoding="utf-8"))
    slate = json.load(open(slate_path or SLATE, encoding="utf-8"))
    on_slate = {(g["date"], g["game_id"]) for g in slate["games"]}
    entries = read_entries()
    already = {e["body"]["pick_id"] for e in entries}
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    n = 0
    skipped = []
    for row in est["window"]:
        pick_id = f"{row['game_id']}-side-proj"
        day = datetime.strptime(row["date"], "%Y-%m-%d").date()
        if pick_id in already:
            skipped.append((pick_id, "already in the chain"))
            continue
        if (row["date"], row["game_id"]) not in on_slate:
            skipped.append((pick_id, "not on the official slate for this date"))
            continue
        if day < today_et:
            skipped.append((pick_id, f"game day {row['date']} is before today (ET) {today_et}: "
                                     "already tipped, cannot publish pre-tip"))
            continue
        if day == today_et:
            tip = _tip_as_et(row.get("tip_et"), day)
            if tip is None:
                skipped.append((pick_id, "tip time not verified for a game today: not published"))
                continue
            if now_utc.astimezone(ET) >= tip:
                skipped.append((pick_id, f"tip {row['tip_et']} ET already passed"))
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
        already.add(pick_id)
        n += 1
    write_entries(entries)
    for pid, why in skipped:
        print(f"skip {pid}: {why}")
    print(f"publish: {n} new entries; {len(skipped)} skipped; {len(entries)} total in the chain")
    return 0


def settle():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    feed = json.load(open(FEED, encoding="utf-8"))
    final = {(g["date"], g["away"], g["home"]): g for g in feed["games"]
             if g.get("settled") and g.get("verified")}
    entries = read_entries()
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    # One settlement per pick, ever. The chain is append-only and each published entry keeps the state
    # it was written with, so without this gate every re-run re-settles whatever earlier runs had
    # already settled. It did: on 2026-11-19 two `settle` calls appended 58 entries for 33 picks and
    # the 2026-11-15 nine were stamped three times. Nothing downstream double-counts (open picks and
    # settled picks are both keyed by pick_id), but the entry count is the audit's evidence that each
    # settled pick was stamped once, and a leaderboard counting entries instead of ids would overstate
    # settled games by 2x-3x on the older days. publish() has had an "already in the chain" gate since
    # c449d46a; settle() is now held to the same rule.
    settled_ids = {e["body"]["pick_id"] for e in entries if e["body"]["state"] == "SETTLED"}
    claimed = set()
    n = 0
    skipped = 0
    for e in entries:
        b = e["body"]
        if b["state"] != "PUBLISHED_PRE_TIP":
            continue
        if b["pick_id"] in settled_ids or b["pick_id"] in claimed:
            skipped += 1
            continue
        claimed.add(b["pick_id"])
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
    note = f"; {skipped} already settled and skipped" if skipped else ""
    print(f"settle: {n} settlement entries appended{note}; {len(entries)} total in the chain")
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
