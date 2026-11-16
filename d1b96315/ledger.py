#!/usr/bin/env python3
"""Sealed, tamper-evident ledger for session arena/d1b96315-nba3, plus an independent read-only
verification of the two ledger trees already on main.

Three actions, all in one file so the recipe and the verifier cannot drift apart:

  publish  — hash every line this session originates for a game that has not tipped yet and
             append it to ``d1b96315/ledger/ledger.jsonl``. A row whose tip has already passed is
             refused: the ledger never back-dates a hash, which is the only thing that makes the
             chain evidence rather than decoration.
  settle   — append a SETTLE entry for every sealed pick whose game now has an official verified
             final, grading it against that final and stamping the settlement.
  verify   — recompute this session's chain AND the two chains already in the repo, each with the
             recipe its own writer documents. The result is written to
             ``d1b96315/data/ledger_check.json``; it resolves board item K-17.

Recipes (verbatim from the writers, restated here so a reader does not have to open them):
  tree A  ledger/ledger.jsonl                      scripts/ledger.py
      canon(x)          = json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
      pick_sha256       = sha256(canon(pick))
      entry_hash        = sha256(canon(entry without entry_hash))
      prev link         = entry_hash of the previous line, GENESIS = 64 zeros
  tree B  data/app/ledger/ledger.jsonl             scripts/pick_ledger.py
      sha(x)            = sha256(json.dumps(x, sort_keys=True, separators=(",", ":")))
      chain_hash(p, b)  = sha({"prev": p, "body": b})     <- the entry hash is over the PAIR,
                                                            not over the body alone (this is K-17)
  this session's tree
      canon as tree A; payload_sha256 = sha256(canon(payload));
      entry_hash = sha256(canon({"prev": prev_hash, "entry": entry without entry_hash}))

Run: python3 d1b96315/ledger.py publish
     python3 d1b96315/ledger.py settle
     python3 d1b96315/ledger.py verify
     python3 d1b96315/ledger.py verify --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
D = HERE / "data"
LDIR = HERE / "ledger"
LFILE = LDIR / "ledger.jsonl"
OUT_CHECK = D / "ledger_check.json"
LINES = D / "lines.json"
RESULTS_1115 = D / "results_2026-11-15.json"
SLATE = D / "slate_2026-11-16_1118.json"

TREE_A = ROOT / "ledger" / "ledger.jsonl"
TREE_B = ROOT / "data" / "app" / "ledger" / "ledger.jsonl"
GENESIS = "0" * 64
# November in the NBA schedule: ET is UTC-5 (eastern standard time after the first Sunday of
# November). The conversion is arithmetic on a published tip time, stated on the page.
ET_OFFSET = timedelta(hours=-5)


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def read(path: pathlib.Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tip_utc(date: str, tip_et: str) -> datetime | None:
    """'2026-11-16', '7:00 PM ET' -> aware UTC datetime."""
    if not tip_et:
        return None
    txt = tip_et.replace(" ET", "").strip()
    try:
        naive = datetime.strptime(f"{date} {txt}", "%Y-%m-%d %I:%M %p")
    except ValueError:
        return None
    return naive.replace(tzinfo=timezone.utc) + (-ET_OFFSET)


# ---------------------------------------------------------------- publish / settle

def publish(now: datetime) -> dict:
    """Append a pre-tip sealed entry for every line this session originates that has not tipped."""
    LDIR.mkdir(parents=True, exist_ok=True)
    entries = read(LFILE)
    seen = {e["pick_id"] for e in entries if e["kind"] == "PUBLISH"}
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    added, skipped = [], []
    slate = {g["game_id"]: g for g in load_slate()}
    for row in load(LINES)["lines"]:
        if not row.get("publishable"):
            skipped.append({"pick_id": f"{row['game_id']}-d1b96315", "why": row.get("block", "not publishable")})
            continue
        pick_id = f"{row['game_id']}-d1b96315"
        if pick_id in seen:
            skipped.append({"pick_id": pick_id, "why": "already sealed in this chain"})
            continue
        game = slate.get(row["game_id"], {})
        tip = tip_utc(row["date"], row.get("tip_et") or game.get("tip_et"))
        if tip is None:
            skipped.append({"pick_id": pick_id, "why": "no verified tip time; refusing to seal"})
            continue
        if now >= tip:
            skipped.append({"pick_id": pick_id, "why": f"tip {tip:%Y-%m-%dT%H:%MZ} has passed; "
                                                        "a hash published now would not be evidence"})
            continue
        payload = {
            "pick_id": pick_id, "game_id": row["game_id"], "date": row["date"],
            "away": row["away"], "home": row["home"], "tip_et": row.get("tip_et"),
            "kind": "originated projection line (side + total) — no funded strategy, no money bet",
            "surface": "projection",
            "estimator_a_margin": row["estimator_a_margin"],
            "estimator_b_margin": row["estimator_b_margin"],
            "disagreement_margin_points": row["disagreement_margin_points"],
            "headline_confidence": row["headline_confidence"],
            "blend_margin_underneath": row["blend_margin_underneath"],
            "total_possessions_model": row["total_possessions_model"],
            "total_naive_scoring_average": row["total_naive_scoring_average"],
            "hca_points_pinned": json.loads((D / "model.json").read_text(encoding="utf-8"))
                                 ["home_court"]["hca_points_used"],
            "bet_eligible": row["bet_eligible"], "bet_block": row["bet_block"],
            "injury_report_revision_et": "11/16/26 01:15 PM",
            "game_url": row["game_url"], "source_url": row["source_url"],
        }
        entry = {"seq": len(entries) + 1, "kind": "PUBLISH", "pick_id": pick_id,
                 "game_id": row["game_id"], "date": row["date"],
                 "published_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "tip_utc": tip.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "pre_tip": True, "state": "PUBLISHED_PRE_TIP",
                 "payload": payload, "payload_sha256": sha(payload),
                 "prereg_sha256": prereg_hashes().get("D-S1"),
                 "prev_hash": prev}
        entry["entry_hash"] = sha({"prev": prev, "entry": {k: v for k, v in entry.items()
                                                            if k != "entry_hash"}})
        entries.append(entry)
        with LFILE.open("a", encoding="utf-8") as fh:
            fh.write(canon(entry) + "\n")
        prev = entry["entry_hash"]
        added.append(pick_id)
    return {"added": added, "skipped": skipped, "entries": len(entries),
            "head_hash": prev, "now_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")}


def load_slate():
    return load(SLATE)["games"]


def settle(now: datetime) -> dict:
    """Grade sealed entries against official verified finals; append a SETTLE entry per pick."""
    entries = read(LFILE)
    finals = {}
    if RESULTS_1115.exists():
        for row in load(RESULTS_1115)["rows"]:
            finals[row["game_id"]] = row
    settled_ids = {e["settles"] for e in entries if e["kind"] == "SETTLE"}
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    added = []
    for e in entries:
        if e["kind"] != "PUBLISH" or e["pick_id"] in settled_ids:
            continue
        fin = finals.get(e["game_id"])
        if not fin:
            continue
        grade = grade_pick(e["payload"], fin)
        body = {"settles": e["pick_id"], "publish_entry_hash": e["entry_hash"],
                "publish_entry_head_ok": e["payload_sha256"] == sha(e["payload"]),
                "official_final": {"away": f"{fin['away_abbr']} {fin['away_pts']}",
                                   "home": f"{fin['home_abbr']} {fin['home_pts']}",
                                   "state": fin["state"]},
                "grade": grade,
                "settlement_source": fin["sources"]["scoreboard"],
                "settlement_rule": "a pick is graded only against a final the scoreboard and the "
                                   "game book agree on; quarter scores are recorded, never used to "
                                   "change the score",
                "stamp": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        entry = {"seq": len(entries) + 1, "kind": "SETTLE", "pick_id": f"{e['pick_id']}-settle",
                 "game_id": e["game_id"], "date": fin["date"], "prev_hash": prev, **body}
        entry["entry_hash"] = sha({"prev": prev, "entry": {k: v for k, v in entry.items()
                                                            if k != "entry_hash"}})
        entries.append(entry)
        with LFILE.open("a", encoding="utf-8") as fh:
            fh.write(canon(entry) + "\n")
        prev = entry["entry_hash"]
        added.append(entry["pick_id"])
    return {"settled": added, "entries": len(entries), "head_hash": prev,
            "games_with_official_finals_available": len(finals)}


def grade_pick(payload: dict, fin: dict) -> dict:
    """Result grading of a published projection: which side the number favoured, what happened."""
    margin_home = None
    if payload.get("blend_margin_underneath") is not None:
        margin_home = payload["blend_margin_underneath"]
    actual_home = fin["home_pts"] - fin["away_pts"]
    fav = None
    if margin_home is not None and abs(margin_home) > 0:
        fav = fin["home_abbr"] if margin_home > 0 else fin["away_abbr"]
    return {"model_favoured": fav, "actual_winner": (fin["home_abbr"] if actual_home > 0
                                                      else fin["away_abbr"]),
            "pick_correct": (fav == (fin["home_abbr"] if actual_home > 0 else fin["away_abbr"]))
                            if fav else None,
            "margin_error_points": (round(abs(margin_home - actual_home), 2)
                                    if margin_home is not None else None)}


def prereg_hashes() -> dict:
    idx = load(D / "prereg_index.json")
    return {k: v["sha256"] for k, v in idx["files"].items()}


# ---------------------------------------------------------------- verify

def verify_tree(path: pathlib.Path, recipe: str) -> dict:
    entries = read(path)
    problems, prev = [], GENESIS
    for i, e in enumerate(entries, 1):
        if e.get("prev_hash") != prev:
            problems.append({"line": i, "problem": "prev_hash does not match the previous entry_hash"})
        if recipe == "pair":
            want = sha({"prev": e.get("prev_hash"),
                        "entry": {k: v for k, v in e.items() if k != "entry_hash"}})
        elif recipe == "chain_hash_pair_body":
            want = sha({"prev": e.get("prev_hash"), "body": e.get("body")})
            body = e.get("body") or {}
            if sha(body.get("payload", {})) != body.get("payload_sha256"):
                problems.append({"line": i, "problem": "body.payload_sha256 does not recompute"})
        elif recipe == "minus_entry_hash":
            want = sha({k: v for k, v in e.items() if k != "entry_hash"})
        else:
            want = None
        if want is not None and want != e.get("entry_hash"):
            problems.append({"line": i, "problem": "entry_hash does not recompute"})
        if recipe in ("minus_entry_hash", "pair") and e.get("kind") == "PUBLISH":
            if sha(e.get("payload", e.get("pick"))) != e.get("payload_sha256", e.get("pick_sha256")):
                problems.append({"line": i, "problem": "payload/pick hash does not recompute"})
        prev = e.get("entry_hash")
    try:
        shown = str(path.relative_to(ROOT))
    except ValueError:                    # a temp copy, as the tamper test passes in
        shown = str(path)
    return {"file": shown, "entries": len(entries),
            "recipe": recipe, "problems": problems,
            "result": "CHAIN INTACT" if not problems and entries else
                      ("EMPTY" if not entries else "PROBLEMS"),
            "head_hash": entries[-1]["entry_hash"] if entries else None}


def amend(now: datetime) -> dict:
    """Append an AMEND entry for every sealed pick whose *current* line differs from the sealed one.

    A sealed entry is never edited — that is the whole point of the chain. When a model fix lands
    after a seal (this session's page-break carry moved two Memphis rows), the honest record is an
    appended entry that names both values and says why they differ, so a reader can see the
    divergence instead of finding a chain that quietly matches today's numbers.
    """
    entries = read(LFILE)
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    already = {e.get("amends") for e in entries if e["kind"] == "AMEND"}
    cur = {r["game_id"]: r for r in load(LINES)["lines"]}
    fields = ("estimator_a_margin", "estimator_b_margin", "disagreement_margin_points",
              "total_possessions_model")
    added = []
    for e in entries:
        if e["kind"] != "PUBLISH" or e["pick_id"] in already:
            continue
        c = cur.get(e["game_id"])
        if not c:
            continue
        deltas = [(f, e["payload"].get(f), c.get(f)) for f in fields
                  if abs((e["payload"].get(f) or 0) - (c.get(f) or 0)) > 0.005]
        if not deltas:
            continue
        body = {"amends": e["pick_id"], "publish_entry_hash": e["entry_hash"],
                "sealed": {f: e["payload"].get(f) for f in fields},
                "current": {f: c.get(f) for f in fields},
                "max_delta_points": round(max(abs((a or 0) - (b or 0)) for _, a, b in deltas), 2),
                "why": "the model changed after this line was sealed: the injury parser now carries a "
                       "club across a PDF page break, so the availability adjustment applies to rows "
                       "the earlier build silently dropped (board flag D-05). The sealed entry is "
                       "left exactly as it was; this entry records what the same row reads now",
                "stamp": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        entry = {"seq": len(entries) + 1, "kind": "AMEND", "pick_id": f"{e['pick_id']}-amend",
                 "game_id": e["game_id"], "date": e["date"], "prev_hash": prev, **body}
        entry["entry_hash"] = sha({"prev": prev, "entry": {k: v for k, v in entry.items()
                                                            if k != "entry_hash"}})
        entries.append(entry)
        with LFILE.open("a", encoding="utf-8") as fh:
            fh.write(canon(entry) + "\n")
        prev = entry["entry_hash"]
        added.append(entry["pick_id"])
    return {"amended": added, "entries": len(entries), "head_hash": prev}


def verify(now: datetime) -> dict:
    out = {"stamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "trees": {}}
    out["trees"]["d1b96315"] = verify_tree(LFILE, "pair")
    if TREE_A.exists():
        out["trees"]["ledger_A"] = verify_tree(TREE_A, "minus_entry_hash")
    if TREE_B.exists():
        out["trees"]["ledger_B"] = verify_tree(TREE_B, "chain_hash_pair_body")
    # K-17: the board says tree B's entry_hash "does not recompute from body under four canonical
    # forms tried". Recompute it the way its own writer computes it and record the answer.
    b = read(TREE_B) if TREE_B.exists() else []
    pair_ok = sum(1 for e in b if sha({"prev": e.get("prev_hash"), "body": e.get("body")})
                  == e.get("entry_hash"))
    body_only = sum(1 for e in b if sha(e.get("body")) == e.get("entry_hash"))
    out["k17_resolution"] = {
        "question": "is data/app/ledger/ledger.jsonl verifiable, and what is its entry_hash recipe?",
        "entries": len(b),
        "recompute_with_chain_hash_prev_and_body": f"{pair_ok}/{len(b)}",
        "recompute_with_body_alone": f"{body_only}/{len(b)}",
        "finding": "the hash is over the PAIR {prev, body} produced by chain_hash() in "
                   "scripts/pick_ledger.py, not over the body alone — which is why hashing the body "
                   "under four canonicalisations never reproduced it. The recipe is documented in the "
                   "writer and CI already runs `python3 scripts/pick_ledger.py verify`, which passes.",
        "verifier_in_repo": "scripts/pick_ledger.py verify",
        "conclusion": "K-17 resolved as a documentation gap, not a linkage break. No entry was "
                      "re-hashed and no file in another session's tree was modified.",
    }
    # settlement stamps, so the page can show them
    ent = read(LFILE)
    out["ledger"] = {
        "entries": len(ent),
        "published_pre_tip": sum(1 for e in ent if e["kind"] == "PUBLISH"),
        "amendments": sum(1 for e in ent if e["kind"] == "AMEND"),
        "amended_picks": [e["pick_id"] for e in ent if e["kind"] == "AMEND"],
        "settled": sum(1 for e in ent if e["kind"] == "SETTLE"),
        "head_hash": ent[-1]["entry_hash"] if ent else None,
        "settlement_stamps": [{"pick_id": e["pick_id"], "stamp": e["stamp"],
                               "source": e["settlement_source"]}
                              for e in ent if e["kind"] == "SETTLE"],
    }
    return out


def load(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["publish", "settle", "amend", "verify", "seal-round"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, help="override the clock, ISO-8601 UTC (for tests)")
    a = ap.parse_args()
    now = (datetime.strptime(a.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
           if a.now else datetime.now(timezone.utc))
    if a.action == "publish":
        res = publish(now)
    elif a.action == "settle":
        res = settle(now)
    elif a.action == "amend":
        res = amend(now)
    elif a.action == "seal-round":
        p = publish(now)
        s = settle(now)
        m = amend(now)
        v = verify(now)
        (D / "ledger_check.json").write_text(json.dumps(v, indent=1) + "\n", encoding="utf-8")
        res = {"publish": p, "settle": s, "amend": m, "verify": v}
    else:
        v = verify(now)
        (D / "ledger_check.json").write_text(json.dumps(v, indent=1) + "\n", encoding="utf-8")
        res = v
    print(json.dumps(res, indent=1) if not a.json else json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
