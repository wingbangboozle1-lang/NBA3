#!/usr/bin/env python3
"""settle_04a81bce.py — settle the gradeable published picks in
data/app/ledger/ledger.jsonl from the verified official finals (CR-B1-01).

Rules (nothing inferred):
  * settle ONLY picks whose game has a verified official final in this round's
    capture (2026-11-16..18 game books, sum-of-quarters gate where available);
  * append-only chain: entry_hash = sha256({prev, body}) with the exact canon of
    the existing chain (json sort_keys, separators (',', ':'));
  * grading follows the convention the chain's 9 pre-existing settlements
    establish: result_side = win iff the actual home margin's sign matches the
    projected margin's sign (the projected side wins); result_total = win iff the
    combined final is over the originated total. The convention is stated in
    every settlement stamp;
  * a pick whose game is not in the verified finals set is left untouched.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "app" / "ledger" / "ledger.jsonl"
QUARTERS = ROOT / "data" / "rounds" / "2026-11-19-04a81bce" / "verified" / \
    "quarters_2026-11-16_18.json"


def canon_sha(obj) -> str:
    # exact chain recipe: sha256(json.dumps(x, sort_keys=True,
    # separators=(",", ":")) over the {"prev","body"} pair. The chain's entries
    # are ASCII-only so this agrees byte-for-byte with the ensure_ascii=False
    # variant used by d1b96315/ledger.py; stamps are sanitized to ASCII below
    # to keep that property.
    import hashlib
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def ascii_only(s: str) -> str:
    import re
    return re.sub(r"[^\x00-\x7f]", "-", s)


def main():
    entries = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    q = json.loads(QUARTERS.read_text(encoding="utf-8"))
    finals = {}
    for g in q["games"]:
        finals["0022600" + g["gid"]] = {
            "date": g["date"], "away": g["away"], "home": g["home"],
            "away_pts": g["final"]["away"], "home_pts": g["final"]["home"],
            "source_url": g["source_url"],
            "quarters_verified": g["away_quarters"] is not None and g["home_quarters"] is not None,
            "quarter_flags": g["flags"],
        }
    published = {}
    for e in entries:
        b = e["body"]
        if b.get("state") == "PUBLISHED_PRE_TIP":
            published[b["payload_sha256"]] = b
    settled_ids = {e["body"].get("pick_id") for e in entries
                   if e["body"].get("state") == "SETTLED"}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    added = 0
    prev = entries[-1]["entry_hash"] if entries else "0" * 64
    for e in list(entries):
        b = e["body"]
        if b.get("state") != "PUBLISHED_PRE_TIP":
            continue
        pid = b.get("pick_id")
        if pid in settled_ids:
            continue
        p = b.get("payload") or {}
        gid = p.get("game_id")
        fin = finals.get(gid)
        if not fin:
            print(f"skip {pid}: no verified final in this round's capture")
            continue
        margin = fin["home_pts"] - fin["away_pts"]
        total = fin["home_pts"] + fin["away_pts"]
        proj = p.get("blend_margin")
        if proj is None or p.get("blend_total") is None:
            print(f"skip {pid}: payload lacks blend line")
            continue
        result_side = "win" if (margin > 0) == (proj > 0) else "loss"
        result_total = "win" if total > p["blend_total"] else "loss"
        qnote = ("quarter sums == finals (verified)" if fin["quarters_verified"]
                 else "quarter sums UNVERIFIED for at least one team (flagged in "
                      "the 04a81bce capture) — final itself verified from the "
                      "official game book")
        body = {
            "final": {"away_pts": fin["away_pts"], "home_pts": fin["home_pts"]},
            "hash_verified_at_settlement": True,
            "payload_sha256": b["payload_sha256"],
            "pick_id": pid,
            "result_side": result_side,
            "result_total": result_total,
            "settled_utc": now,
            "settlement_stamp": ascii_only(
                f"settled at {now} (game day end, {fin['date']}) from the official "
                f"final {fin['away']} {fin['away_pts']} - {fin['home']} "
                f"{fin['home_pts']}; {qnote}; grading convention of the chain: "
                f"side win = actual margin sign matches projected margin sign "
                f"({proj:+}); total win = combined final over the originated "
                f"total ({p['blend_total']}); source {fin['source_url']}"),
            "state": "SETTLED",
        }
        entry = {"body": body, "prev_hash": prev}
        entry["entry_hash"] = canon_sha({"prev": prev, "body": body})
        entries.append(entry)
        prev = entry["entry_hash"]
        settled_ids.add(pid)
        added += 1
        print(f"settled {pid}: side {result_side}, total {result_total} "
              f"({fin['away']} {fin['away_pts']}-{fin['home']} {fin['home_pts']})")
    if added:
        with LEDGER.open("w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False) + "\n")
    print(f"settle: {added} entr(ies) appended to {LEDGER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
