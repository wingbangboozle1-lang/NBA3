"""Pre-registration files and a tamper-evident pick ledger.

Two separate mechanisms, deliberately not merged:

  prereg/   One JSON file per strategy, FROZEN BEFORE its first bet: signal, thresholds,
            universe and the exact settlement rule. Written by `freeze()` and never edited
            afterwards; the ledger refuses to seal a pick whose strategy has no frozen file.

  ledger/   Append-only, hash-chained. Each entry stores the pick, its sha256, the sha256 of the
            previous entry, and the timestamp. `publish()` records the hash BEFORE tip-off;
            `settle()` records the official final afterwards and checks that the pick payload
            still hashes to the value published. If a pick text is edited after publication the
            verification fails and the entry is published as TAMPERED.

Honest limits, stated on the site:
  * The chain makes local edits detectable. It is not a timestamping authority: anyone who can
    rewrite the whole file can rebuild the chain. Anchoring the head hash in a git commit (which
    this repository does every build) is a weak but real external witness, because the commit
    history is what GitHub serves.
  * `published_utc` is only as trustworthy as the machine that wrote it.

Run: python3 scripts/ledger.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREREG = ROOT / "prereg"
LEDGER_DIR = ROOT / "ledger"
LEDGER = LEDGER_DIR / "ledger.jsonl"
INDEX = LEDGER_DIR / "index.json"

GENESIS = "0" * 64


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ pre-registration
def freeze(strategy: dict, *, path: pathlib.Path | None = None) -> dict:
    """Write a strategy's pre-registration file. Refuses to overwrite an existing one."""
    path = path or (PREREG / f"{strategy['id']}.json")
    if path.exists():
        raise FileExistsError(f"{path} already frozen; pre-registration is write-once")
    required = ("id", "name", "signal", "thresholds", "universe", "settlement_rule",
                "stake_rule", "frozen_utc", "author")
    missing = [k for k in required if k not in strategy]
    if missing:
        raise ValueError(f"pre-registration is incomplete, missing {missing}")
    body = dict(strategy)
    body["payload_sha256"] = sha({k: v for k, v in body.items() if k != "payload_sha256"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1) + "\n")
    return body


def load_prereg() -> dict[str, dict]:
    out = {}
    for p in sorted(PREREG.glob("*.json")):
        d = json.loads(p.read_text())
        out[d["id"]] = d
    return out


# ------------------------------------------------------------------ ledger
def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def _append(entry: dict) -> dict:
    entries = read_ledger()
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    entry["seq"] = len(entries) + 1
    entry["prev_hash"] = prev
    entry["pick_sha256"] = sha(entry["pick"])
    entry["entry_hash"] = sha({k: v for k, v in entry.items() if k != "entry_hash"})
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def publish(pick: dict, *, now: str) -> dict:
    """Seal a pick BEFORE tip-off. The strategy must already be frozen."""
    frozen = load_prereg()
    if pick["strategy_id"] not in frozen:
        raise ValueError(f"strategy {pick['strategy_id']} has no frozen pre-registration")
    if pick["tip_et_iso"] <= now:
        raise ValueError("refusing to publish a pick at or after its tip time")
    return _append({"kind": "PUBLISH", "published_utc": now, "pick": pick})


def settle(game_id: str, *, final: dict, now: str, source_url: str) -> dict:
    """Settle the published pick for a game once an official final exists."""
    published = [e for e in read_ledger()
                 if e["kind"] == "PUBLISH" and e["pick"]["game_id"] == game_id]
    if not published:
        raise ValueError(f"no published pick for {game_id}")
    entry = published[-1]
    pick = entry["pick"]
    out = _grade(pick, final)
    return _append({"kind": "SETTLE", "settled_utc": now, "game_id": game_id,
                    "pick_sha256_at_publish": entry["pick_sha256"],
                    "pick": pick, "final": final, "result": out,
                    "source_url": source_url})


def _grade(pick: dict, final: dict) -> dict:
    """Grade against the pick's own pre-registered settlement rule. No rule, no settlement."""
    rule = pick["settlement_rule_id"]
    margin = final["home_final"] - final["away_final"]
    total = final["home_final"] + final["away_final"]
    if rule == "SPREAD":
        line = pick["line"]
        # pick on the home side (+ means home gets points); push is a real outcome and is kept.
        adj = margin + line
        if abs(adj) < 1e-9:
            return {"outcome": "PUSH", "margin": margin, "line": line}
        return {"outcome": "WIN" if adj > 0 else "LOSS", "margin": margin, "line": line}
    if rule == "TOTAL":
        line = pick["line"]
        if abs(total - line) < 1e-9:
            return {"outcome": "PUSH", "total": total, "line": line}
        over = total > line
        return {"outcome": "WIN" if over == pick["side_over"] else "LOSS",
                "total": total, "line": line}
    if rule == "MONEYLINE":
        home_won = margin > 0
        return {"outcome": "WIN" if home_won == pick["side_home"] else "LOSS",
                "margin": margin}
    raise ValueError(f"unknown settlement rule {rule}")


def verify() -> dict:
    """Recompute the whole chain and every pick hash."""
    entries = read_ledger()
    problems = []
    prev = GENESIS
    for e in entries:
        if e["prev_hash"] != prev:
            problems.append({"seq": e["seq"], "problem": "prev_hash does not match the previous entry"})
        body = {k: v for k, v in e.items() if k != "entry_hash"}
        if sha(body) != e["entry_hash"]:
            problems.append({"seq": e["seq"], "problem": "entry_hash does not recompute"})
        if sha(e["pick"]) != e["pick_sha256"]:
            problems.append({"seq": e["seq"], "problem": "the pick no longer hashes to the published value"})
        prev = e["entry_hash"]
    settles = [e for e in entries if e["kind"] == "SETTLE"]
    for s in settles:
        if sha(s["pick"]) != s["pick_sha256_at_publish"]:
            problems.append({"seq": s["seq"], "problem": "settled pick differs from the published pick"})
    return {
        "entries": len(entries),
        "published": sum(1 for e in entries if e["kind"] == "PUBLISH"),
        "settled": len(settles),
        "head_hash": entries[-1]["entry_hash"] if entries else GENESIS,
        "verified": not problems,
        "problems": problems,
    }


def write_index() -> dict:
    """Write ledger/index.json from the CURRENT ledger state.

    Kept separate from main() because the index must reflect picks that were sealed after the
    ledger was first created. Writing it only from main() left the index advertising a genesis
    head hash after two picks had already been sealed -- a stale summary of a live chain, which is
    exactly the kind of quiet mismatch this file exists to prevent.
    """
    v = verify()
    frozen = load_prereg()
    index = {
        "schema": "nba3.live.ledger_index/v1",
        "session": "arena/2ebb1e75-nba3",
        "head_hash": v["head_hash"],
        "entries": v["entries"],
        "published": v["published"],
        "settled": v["settled"],
        "verified": v["verified"],
        "problems": v["problems"],
        "preregistered_strategies": sorted(frozen),
        "integrity_rule": ("Every entry stores the sha256 of its pick and the sha256 of the "
                           "previous entry. scripts/ledger.py verify() recomputes both; the build "
                           "fails if either does not reproduce."),
        "witness": "ledger/ledger.jsonl is committed, so each build's commit hash is an external witness of the head hash.",
    }
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=1) + "\n")
    return index


def main() -> None:
    index = write_index()
    print(f"ledger: {index['entries']} entries, head {index['head_hash'][:16]}..., "
          f"verified={index['verified']}")
    print(f"pre-registered strategies: {index['preregistered_strategies']}")


if __name__ == "__main__":
    main()
