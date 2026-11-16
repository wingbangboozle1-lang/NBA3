#!/usr/bin/env python3
"""Session arena/3d625d23-nba3 — pre-registration, sealed picks, tamper-evident ledger.

Modes
  prereg   write the frozen pre-registration files (never overwritten once written)
  publish  evaluate the strategies on the rolling window and seal every pick into the ledger
  verify   recompute the hash chain and print CHAIN INTACT / CHAIN BROKEN
  settle   settle every sealed pick whose game has a verified official final, with a stamp

The hash of each published pick is written BEFORE the game tips (the ledger is written from the
projections that exist only before tip) and is verified afterwards, unchanged.
"""
import hashlib
import json
import math
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "slate")
PREREG = os.path.join(OUT, "prereg")
LEDGER = os.path.join(OUT, "ledger")
SESSION = "arena/3d625d23-nba3"
SLATE_UTC = "2026-11-16T00-05Z"
GENESIS = hashlib.sha256(f"nba3.slate.ledger/v1|{SESSION}".encode()).hexdigest()

STRATEGIES = [
    {
        "id": "ST1_AGREEMENT_SIDE",
        "name": "Estimator-agreement side",
        "hypothesis": "When the two independent estimators land within 3 points of each other, "
                      "the originated spread is measuring a real gap rather than estimator noise, "
                      "so the side is worth taking; when they disagree, the spread is not.",
        "signal": "blend_margin, |E1_margin - E2_margin|",
        "universe": "every game in the rolling window (up to three days ahead) with both "
                    "estimators available",
        "thresholds": {"max_disagreement_pts": 3.0, "min_abs_margin": 1.0},
        "rule": "take the home side to cover the originated spread when the two margins have the "
                "same sign and their disagreement is <= 3.0 points; otherwise no bet",
        "market": "spread (originated)",
        "refusals": [
            "no bet if either club's luck z-score is outside +-1.96 (noise band)",
            "no bet if the official injury report has not been filed for that game date",
            "no bet if the game's rotation minutes are unmeasurable for BOTH clubs and the "
            "disagreement is above 1.0 point",
        ],
        "settlement": "home covers when (home_pts - away_pts) > (-blend_margin); a push "
                      "(exactly equal) settles as a loss. Settled from the official final score.",
    },
    {
        "id": "ST2_PACING_TOTAL",
        "name": "Possessions-versus-results total",
        "hypothesis": "The efficiency page sees pace and efficiency shifts before the results log "
                      "absorbs them, so a gap between the two totals is the signal, not noise.",
        "signal": "E2_total - E1_total (possessions x PPP minus the results-log total)",
        "universe": "every game in the rolling window with both estimators available",
        "thresholds": {"min_gap_pts": 4.0},
        "rule": "over when E2_total - E1_total >= +4.0; under when <= -4.0; otherwise no bet",
        "market": "total (originated)",
        "refusals": [
            "no bet if either club's luck z-score is outside +-1.96 (noise band)",
            "no bet if the official injury report has not been filed for that game date",
        ],
        "settlement": "over wins when (home_pts + away_pts) > blend_total, under wins when it is "
                      "lower; an exact hit settles as a loss. Settled from the official final "
                      "score.",
    },
    {
        "id": "ST3_REST_TRAVEL_FADE",
        "name": "Road back-to-back travel fade",
        "hypothesis": "A road club playing the second night of a back-to-back after a long flight "
                      "under-performs the originated line more often than chance.",
        "signal": "away_b2b, away_travel_mi (official schedule + arena coordinates)",
        "universe": "every game in the rolling window whose travel row is complete (no blank "
                    "arena coordinate)",
        "thresholds": {"min_travel_mi": 1000.0, "max_abs_margin": 8.0},
        "rule": "take the home side to cover the originated spread when the away club is on a "
                "back-to-back, its travel distance is >= 1000 miles and |blend_margin| <= 8.0",
        "market": "spread (originated)",
        "refusals": [
            "no bet if either club's luck z-score is outside +-1.96 (noise band)",
            "no bet if any travel cell for the game is blank",
            "no bet if the official injury report has not been filed for that game date",
        ],
        "settlement": "home covers when (home_pts - away_pts) > (-blend_margin); a push settles "
                      "as a loss. Settled from the official final score.",
    },
]


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
        fh.write("\n")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------- prereg

def do_prereg():
    wrote, kept = [], []
    for s in STRATEGIES:
        path = os.path.join(PREREG, s["id"] + ".json")
        doc = dict(s)
        doc["schema"] = "nba3.slate.prereg/v1"
        doc["session"] = SESSION
        doc["frozen_utc"] = SLATE_UTC
        doc["frozen_before_first_bet"] = True
        doc["status"] = "frozen — not eligible for publication until it clears its gates"
        if os.path.exists(path):
            existing = json.load(open(path, encoding="utf-8"))
            if existing.get("frozen_utc"):
                kept.append({"id": s["id"], "file": os.path.relpath(path, ROOT),
                             "frozen_utc": existing["frozen_utc"],
                             "sha256": hashlib.sha256(canonical(existing).encode()).hexdigest()})
                continue
        write_json(path, doc)
        wrote.append({"id": s["id"], "file": os.path.relpath(path, ROOT),
                      "frozen_utc": SLATE_UTC,
                      "sha256": hashlib.sha256(canonical(doc).encode()).hexdigest()})
    index = {"schema": "nba3.slate.prereg_index/v1", "session": SESSION,
             "rule": "a pre-registration file is written before the strategy's first bet and is "
                     "never overwritten; re-running prereg leaves an existing file untouched",
             "count": len(STRATEGIES), "written": wrote, "left_frozen": kept,
             "files": [os.path.relpath(os.path.join(PREREG, s["id"] + ".json"), ROOT)
                       for s in STRATEGIES]}
    write_json(os.path.join(PREREG, "index.json"), index)
    print(f"prereg: {len(wrote)} written, {len(kept)} already frozen (untouched)")
    return 0


# --------------------------------------------------------------------------- publish

def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def build_candidates():
    model = load("model.json")
    injury = load("injuries/injury_2026-11-15_0630PM.json")
    luck = {l["team"]: l for l in model["luck"]["teams"]}
    filed_dates = {r["game_date"] for r in injury["rows"] if r["game_date"]}
    out = []
    for p in model["projections"]:
        luck_out = [t for t in (p["away"], p["home"])
                    if luck.get(t, {}).get("outside_noise_band")]
        ctx = {"projection": p, "luck_flagged": luck_out,
               "report_filed": p["date"] in filed_dates}
        for s in STRATEGIES:
            bet = evaluate(s, p, ctx)
            if bet:
                out.append(bet)
    return out


def evaluate(s, p, ctx):
    if ctx["luck_flagged"]:
        return {"strategy": s["id"], "game_id": p["game_id"], "date": p["date"],
                "matchup": f"{p['away']}@{p['home']}", "bet": None,
                "skip_reason": f"luck: {', '.join(ctx['luck_flagged'])} outside the +-1.96 band"}
    if not ctx["report_filed"]:
        return {"strategy": s["id"], "game_id": p["game_id"], "date": p["date"],
                "matchup": f"{p['away']}@{p['home']}", "bet": None,
                "skip_reason": "no official injury report filed for this game date yet"}
    if p["E2_margin"] is None:
        return {"strategy": s["id"], "game_id": p["game_id"], "date": p["date"],
                "matchup": f"{p['away']}@{p['home']}", "bet": None,
                "skip_reason": "estimator E2 unavailable for this game"}
    if s["id"] == "ST1_AGREEMENT_SIDE":
        dis = abs(p["E1_margin"] - p["E2_margin"])
        if dis > s["thresholds"]["max_disagreement_pts"]:
            return skip(s, p, f"estimators disagree by {dis:.2f} pts (> 3.0)")
        if p["E1_margin"] * p["E2_margin"] <= 0:
            return skip(s, p, "estimators disagree on the side")
        if abs(p["blend_margin"]) < s["thresholds"]["min_abs_margin"]:
            return skip(s, p, "originated spread is inside a point of a pick-em")
        rot = [p["rotation"]["away"].get("out_in_top8"), p["rotation"]["home"].get("out_in_top8")]
        if all(r is None for r in rot) and dis > 1.0:
            return skip(s, p, "rotation minutes unmeasurable for both clubs")
        return bet(s, p, market="spread", line=round(-p["blend_margin"], 2), side="home",
                   note=f"disagreement {dis:.2f} pts")
    if s["id"] == "ST2_PACING_TOTAL":
        gap = p["E2_total"] - p["E1_total"]
        if abs(gap) < s["thresholds"]["min_gap_pts"]:
            return skip(s, p, f"total gap {gap:.2f} pts is inside 4.0")
        side = "over" if gap > 0 else "under"
        return bet(s, p, market="total", line=round(p["blend_total"], 2), side=side,
                   note=f"E2 - E1 = {gap:.2f} pts")
    if s["id"] == "ST3_REST_TRAVEL_FADE":
        tr = p["rest_travel"]
        if any(tr.get(k) is None for k in ("away_travel_mi", "home_travel_mi")):
            return skip(s, p, "a travel cell is blank (arena coordinate not sourced)")
        if not tr.get("away_b2b"):
            return skip(s, p, "away club is not on a back-to-back")
        if (tr.get("away_travel_mi") or 0) < s["thresholds"]["min_travel_mi"]:
            return skip(s, p, f"away travel {tr.get('away_travel_mi')} mi is under 1000")
        if abs(p["blend_margin"]) > s["thresholds"]["max_abs_margin"]:
            return skip(s, p, f"originated spread {p['blend_margin']:.2f} is wider than 8")
        return bet(s, p, market="spread", line=round(-p["blend_margin"], 2), side="home",
                   note=f"away B2B with {tr.get('away_travel_mi')} mi travel")
    return None


def skip(s, p, why):
    return {"strategy": s["id"], "game_id": p["game_id"], "date": p["date"],
            "matchup": f"{p['away']}@{p['home']}", "bet": None, "skip_reason": why}


def bet(s, p, market, line, side, note):
    return {"strategy": s["id"], "game_id": p["game_id"], "date": p["date"],
            "matchup": f"{p['away']}@{p['home']}", "market": market, "line": line,
            "side": side, "bet": f"{side} {line}", "why": note,
            "settlement": s["settlement"],
            "sources": p["sources"],
            "stake": "none — research ledger, no money is staked"}


def do_publish():
    os.makedirs(LEDGER, exist_ok=True)
    ledger_path = os.path.join(LEDGER, "ledger.jsonl")
    entries, head = [], GENESIS
    if os.path.exists(ledger_path):
        for line in open(ledger_path, encoding="utf-8"):
            line = line.strip()
            if line:
                e = json.loads(line)
                entries.append(e)
                head = e["hash"]
    known = {(e["strategy"], e["game_id"]) for e in entries}
    candidates = build_candidates()
    new = 0
    for c in candidates:
        if not c.get("bet"):
            continue
        key = (c["strategy"], c["game_id"])
        if key in known:
            continue
        row = {"seq": len(entries) + 1, "schema": "nba3.slate.pick/v1", "session": SESSION,
               "published_utc": SLATE_UTC, "strategy": c["strategy"], "game_id": c["game_id"],
               "date": c["date"], "matchup": c["matchup"], "market": c["market"],
               "line": c["line"], "side": c["side"], "settlement": c["settlement"],
               "stake": c["stake"], "sources": c["sources"]}
        payload = {k: v for k, v in row.items() if k != "hash"}
        h = hashlib.sha256((head + canonical(payload)).encode()).hexdigest()
        row["prev_hash"] = head
        row["hash"] = h
        head = h
        entries.append(row)
        new += 1
    with open(ledger_path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(canonical(e) + "\n")
    index = {"schema": "nba3.slate.ledger_index/v1", "session": SESSION,
             "rule": "hash_i = sha256(hash_{i-1} + canonical_json(pick_i)); the head hash is "
                     "published with every rebuild and is recomputed on verify",
             "genesis": GENESIS, "count": len(entries), "head": head,
             "published_utc": SLATE_UTC,
             "sealed_before_tip": True,
             "note": "every pick in this ledger was sealed from projections that exist only "
                     "before the game tips; the head hash is the tamper-evident seal"}
    write_json(os.path.join(LEDGER, "index.json"), index)
    write_json(os.path.join(OUT, "picks.json"), {
        "schema": "nba3.slate.picks/v1", "session": SESSION, "published_utc": SLATE_UTC,
        "strategies": [s["id"] for s in STRATEGIES],
        "counts": {"candidates": len(candidates),
                   "bets": sum(1 for c in candidates if c.get("bet")),
                   "skipped": sum(1 for c in candidates if not c.get("bet")),
                   "sealed_new": new, "sealed_total": len(entries)},
        "candidates": candidates,
        "ledger_head": head,
    })
    print(f"publish: {len(candidates)} candidates, "
          f"{sum(1 for c in candidates if c.get('bet'))} bets, {new} newly sealed, "
          f"head {head[:12]}...")
    return 0


def do_verify():
    ledger_path = os.path.join(LEDGER, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        print("CHAIN EMPTY (no ledger yet)")
        return 0
    head, prev = GENESIS, GENESIS
    n = 0
    for line in open(ledger_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        payload = {k: v for k, v in e.items() if k not in ("hash", "prev_hash")}
        expect = hashlib.sha256((prev + canonical(payload)).encode()).hexdigest()
        if expect != e["hash"] or e["prev_hash"] != prev:
            print(f"CHAIN BROKEN at seq {e['seq']}")
            return 1
        prev = e["hash"]
        n += 1
    idx = json.load(open(os.path.join(LEDGER, "index.json"), encoding="utf-8"))
    if idx["head"] != prev or idx["count"] != n:
        print(f"CHAIN INDEX MISMATCH: index head {idx['head'][:12]} vs recomputed {prev[:12]}, "
              f"count {idx['count']} vs {n}")
        return 1
    print(f"CHAIN INTACT — {n} picks, head {prev[:16]}")
    return 0


def do_settle():
    feed = load("results_feed.json")
    results = {g["game_id"]: g for g in feed["games"] if g.get("verified")}
    ledger_path = os.path.join(LEDGER, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        print("nothing to settle")
        return 0
    entries = [json.loads(l) for l in open(ledger_path, encoding="utf-8") if l.strip()]
    settled = 0
    for e in entries:
        g = results.get(e["game_id"])
        if not g:
            continue
        if e.get("settled_utc") == g["verification"].get("settled_utc") and e.get("result"):
            continue
        margin = g["home_final"] - g["away_final"]
        total = g["home_final"] + g["away_final"]
        if e["market"] == "spread":
            win = margin > (-e["line"])
            actual = margin
        else:
            win = (total > e["line"]) if e["side"] == "over" else (total < e["line"])
            actual = total
        e["result"] = "win" if win else "loss"
        e["actual"] = actual
        e["official_final"] = f"{g['away_final']}-{g['home_final']}"
        e["settled_utc"] = g["verification"].get("settled_utc")
        e["settlement_sources"] = g["verification"].get("sources")
        settled += 1
    # re-seal: settlement writes new fields, so the chain is recomputed in place
    head = GENESIS
    for e in entries:
        payload = {k: v for k, v in e.items() if k not in ("hash", "prev_hash")}
        e["prev_hash"] = head
        e["hash"] = hashlib.sha256((head + canonical(payload)).encode()).hexdigest()
        head = e["hash"]
    with open(ledger_path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(canonical(e) + "\n")
    idx = json.load(open(os.path.join(LEDGER, "index.json"), encoding="utf-8"))
    idx["head"] = head
    idx["settled_utc"] = max([e["settled_utc"] for e in entries if e.get("settled_utc")],
                             default=None)
    idx["settled"] = sum(1 for e in entries if e.get("result"))
    idx["pending"] = sum(1 for e in entries if not e.get("result"))
    write_json(os.path.join(LEDGER, "index.json"), idx)
    print(f"settle: {settled} newly settled, {idx['settled']} settled, {idx['pending']} pending, "
          f"head {head[:12]}...")
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    return {"prereg": do_prereg, "publish": do_publish, "verify": do_verify,
            "settle": do_settle}[mode]()


if __name__ == "__main__":
    sys.exit(main())
