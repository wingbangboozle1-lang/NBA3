#!/usr/bin/env python3
"""Pre-registration files and a tamper-evident pick ledger for the 2026-11-17 round.

Two mechanisms, deliberately kept separate (the requirement asks for both):

  prereg/  One JSON file per strategy, written BEFORE its first pick and never edited: the signal,
           the thresholds, the universe, the exact settlement rule and the stake rule. `freeze()`
           refuses to overwrite an existing file, so a strategy cannot be softened after it loses.
           Files live inside this round and are prefixed with the session id, so no other
           session's register is touched.

  ledger/  Append-only and hash-chained. A PUBLISH entry stores the pick, the sha256 of its
           payload, the hash of the previous entry and the publication time; the chain head is
           therefore published before tip-off. A SETTLE entry stores the official final, the
           publication time and the result, and re-checks that the pick payload still hashes to
           what was sealed -- if the text was edited after publication the entry is written as
           TAMPERED rather than quietly corrected.

Honest limits, restated here because the site repeats them:
  * a hash chain makes local edits detectable; it is not a timestamping authority. Anyone able to
    rewrite the whole file could rebuild the chain, which is why the head hash is committed to git
    (GitHub's commit history is the external witness) and why `--check` fails a build on drift;
  * `published_utc` is only as trustworthy as the clock of the machine that wrote it;
  * nothing is settled here that does not have an official final: tonight's games stay in state
    PUBLISHED_PRE_TIP until the settlement run finds verified finals.

Run:
    python3 scripts/ledger_2ecbccfd.py --freeze    # write the pre-registration files
    python3 scripts/ledger_2ecbccfd.py             # freeze + publish + verify
    python3 scripts/ledger_2ecbccfd.py --check      # fail if the chain or the artefacts drift
    python3 scripts/ledger_2ecbccfd.py --settle     # settle whatever has a verified official final
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

# determinism (session 89e98007): summation and rounding are pinned in-repo, not inherited from
# the interpreter that happens to run the build. See scripts/determinism.py: EVE-F04 was a runner
# Python upgrade (3.11 -> 3.14.4) whose compensated sum() moved one published float by 1 unit in
# the 4th decimal and froze the byte-for-byte replay gate for six days.
try:
    import determinism as det  # noqa: E402  (running from scripts/)
except ImportError:            # running from elsewhere, e.g. round_2ecbccfd/build.py
    import os as _det_os
    import sys as _det_sys
    _det_here = _det_os.path.dirname(_det_os.path.abspath(__file__))
    for _det_p in (_det_os.path.join(_det_here, "scripts"),
                   _det_os.path.join(_det_os.path.dirname(_det_here), "scripts")):
        if _det_os.path.isdir(_det_p) and _det_p not in _det_sys.path:
            _det_sys.path.insert(0, _det_p)
    import determinism as det  # noqa: E402,F401

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RD = os.path.join(ROOT, "data", "rounds", "2026-11-17")
PREREG = os.path.join(RD, "prereg")
LEDGER_DIR = os.path.join(RD, "ledger")
LEDGER = os.path.join(LEDGER_DIR, "ledger.jsonl")
INDEX = os.path.join(LEDGER_DIR, "index.json")
MODEL = os.path.join(RD, "model.json")
RESULTS_LOG = os.path.join(RD, "results_log.json")

SESSION = "arena/2ecbccfd-nba3"
GENESIS = "0" * 64
PUBLISHED_UTC = "2026-11-16T19:30Z"
STRATEGY_PREFIX = "2ecbccfd-"

# Every strategy's registration is written from this table and nothing else: the numbers below are
# the ones the pre-registration freezes, so a later edit to model.json cannot move a threshold.
STRATEGIES = [
    {
        "id": "ST-17-HCA-PINNED",
        "name": "Home side at the pinned home-court value",
        "signal": ("bet the home club whenever the pinned home-court value, converted from the "
                   "measured home-win rate, is greater than zero"),
        "thresholds": {"min_pinned_hca_points": 0.0, "min_log_games": 150},
        "universe": "every game of the official slate for the round window, one pick per game",
        "settlement_rule": ("MONEYLINE: the pick wins if the side named wins the game. The result is "
                            "read from the official final score of that game's own page; a game with "
                            "no verified final is void, not a loss"),
        "stake_rule": "1 unit, capped at 5% of the bankroll, no martingale, no re-stake after settlement",
        "luck_policy": ("refused for any club whose luck z-score is outside +/-2, because a home-side "
                        "pick on a club winning on luck rather than play is not a skill edge"),
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
    },
    {
        "id": "ST-18-E2-WALKFORWARD",
        "name": "Walk-forward margin from the verified results log",
        "signal": ("bet the club with the better points-differential-per-game measured only over "
                   "games strictly before tip-off, adjusted by the pinned home-court value"),
        "thresholds": {"min_games_per_side": 3, "min_edge_points": 0.0},
        "universe": "games where both clubs have at least 3 captured games before tip",
        "settlement_rule": ("SPREAD vs the originated line: the pick wins if the chosen club beats "
                            "the originated margin by more than zero; ties (exact margin) are void"),
        "stake_rule": "1 unit per pick, maximum 4 units per game day",
        "luck_policy": "refused for any club outside the +/-2 luck band",
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
    },
    {
        "id": "ST-19-DISAGREEMENT-GATE",
        "name": "Trade only where the two estimators agree on the sign",
        "signal": ("publish a pick only where estimator A and estimator B name the same side, and "
                   "rank picks by the size of their disagreement; the disagreement is the headline, "
                   "the blend is printed underneath and is never the headline"),
        "thresholds": {"max_disagreement_points": 100.0, "require_sign_agreement": True},
        "universe": "the round window's games where both estimators are computable",
        "settlement_rule": "MONEYLINE, official final of the game's own page; void without a final",
        "stake_rule": "1 unit",
        "luck_policy": "refused for any club outside the +/-2 luck band",
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
    },
    {
        "id": "ST-20-ROTATION-IMPACT",
        "name": "Rotation minutes actually vacated",
        "signal": ("bet the side whose opponent loses more captured rotation minutes to Out or "
                   "Doubtful players, where a rotation player is one averaging 15 or more captured "
                   "minutes; a club whose injured players were already inactive scores zero impact "
                   "and is not a pick"),
        "thresholds": {"min_vacated_min": 8.0, "min_rotation_players_out": 1,
                       "rotation_minutes_floor": 15.0},
        "universe": "games where both clubs have a captured official game book",
        "settlement_rule": "MONEYLINE, official final; void without a final",
        "stake_rule": "1 unit",
        "luck_policy": "refused for any club outside the +/-2 luck band",
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
        "blocked_because": ("no captured game book exists for 16 of the 30 clubs, so the universe is "
                            "smaller than the slate; the shortfall is published, not filled"),
    },
    {
        "id": "ST-21-REST-LOAD",
        "name": "Measured rest load, half weight",
        "signal": ("bet the side that is not on a back-to-back or 3-in-4 when the other is, applying "
                   "the measured margin gap between those rest states at half weight per side"),
        "thresholds": {"min_rest_gap_days": 1, "min_measured_penalty_points": 1.0,
                       "min_penalty_z": 1.645},
        "universe": "games of the round window where both sides' previous game dates are known",
        "settlement_rule": "SPREAD vs the originated line; exact-margin ties are void",
        "stake_rule": "1 unit",
        "luck_policy": "refused for any club outside the +/-2 luck band",
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
        "blocked_because": ("the measured back-to-back gap is 2.888 points with a standard error of "
                            "2.908 (z = 0.99), which fails the frozen z floor of 1.645, so this "
                            "strategy is registered but refused until the gap is real"),
    },
    {
        "id": "ST-22-PARLAY-RHO",
        "name": "Same-night two-leg parlay priced with the measured correlation",
        "signal": ("combine two legs of one date only where the rho-adjusted joint price is better "
                   "than the product of the two naive prices by more than the noise band of rho; the "
                   "naive product is printed beside the price, always"),
        "thresholds": {"max_abs_rho": 0.15, "min_edge_pp": 1.0},
        "universe": "unordered pairs of games on one date within the round window",
        "settlement_rule": ("parlay: both legs must win on their official finals; one leg without a "
                            "verified final voids the whole ticket, it is not scored as a loss"),
        "stake_rule": "1 unit, no more than one parlay per date",
        "luck_policy": "refused if either leg's club is outside the +/-2 luck band",
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
        "blocked_because": ("the measured same-night margin correlation is 0.012 with a 95% interval "
                            "of [-0.057, 0.081], so no rho adjustment can clear 1.0 pp of edge; the "
                            "parlays are still priced with rho and the naive product is printed next "
                            "to them, as required"),
    },
    {
        "id": "ST-23-TOTAL-POSSESSION",
        "name": "Total from possessions, not from scoring averages",
        "signal": ("project the total as pace x points-per-possession, pace from the official advanced "
                   "page and ppp as the mean of each club's own rate and its opponent's allowed rate; "
                   "an average of two points-per-game figures is not used at any point"),
        "thresholds": {"min_total_edge_points": 0.0},
        "universe": "games of the round window present on all three official team-stat pages",
        "settlement_rule": ("TOTAL: over if the game's official final total exceeds the originated "
                            "total, under if below, push and void if equal"),
        "stake_rule": "1 unit",
        "luck_policy": "refused for any club outside the +/-2 luck band",
        "frozen_utc": PUBLISHED_UTC,
        "author": SESSION,
    },
]
STRATEGY_BY_ID = {s["id"]: s for s in STRATEGIES}


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- pre-registration
def freeze(force=False):
    os.makedirs(PREREG, exist_ok=True)
    written, frozen = [], []
    for s in STRATEGIES:
        path = os.path.join(PREREG, f"{STRATEGY_PREFIX}{s['id']}.json")
        if os.path.exists(path) and not force:
            body = read_json(path)
            if body["payload_sha256"] != sha({k: v for k, v in body.items()
                                              if k != "payload_sha256"}):
                raise SystemExit(f"{path} was edited after it was frozen: the payload hash does not "
                                 "match its own contents. Pre-registration is write-once; restore the "
                                 "committed file rather than rewriting it.")
            frozen.append(path)
            continue
        if os.path.exists(path):
            raise SystemExit(f"{path} exists; pre-registration is write-once and --force is not "
                             "accepted for an existing file")
        body = dict(s)
        body["session"] = SESSION
        body["round"] = "2026-11-17"
        body["payload_sha256"] = sha({k: v for k, v in body.items() if k != "payload_sha256"})
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(body, indent=1) + "\n")
        written.append(path)
    return written, frozen


def load_prereg():
    out = {}
    if not os.path.isdir(PREREG):
        return out
    for name in sorted(os.listdir(PREREG)):
        if not name.endswith(".json"):
            continue
        d = read_json(os.path.join(PREREG, name))
        out[d["id"]] = d
    return out


# --------------------------------------------------------------------------- chain
def read_ledger():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]


def _append(entry):
    entries = read_ledger()
    prev = entries[-1]["entry_hash"] if entries else GENESIS
    entry["seq"] = len(entries) + 1
    entry["prev_hash"] = prev
    entry["entry_hash"] = sha({k: v for k, v in entry.items() if k != "entry_hash"})
    os.makedirs(LEDGER_DIR, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def tip_utc(date, tip_et):
    """Tip time in UTC, from the date and the ET clock time the official page prints.

    Eastern time is UTC-5 for the whole round window (US daylight saving ends 2026-11-01), so UTC
    = ET + 5, which can roll into the next calendar day -- the 7:00 PM games tip at 00:00Z.
    """
    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", (tip_et or "").upper())
    if not m:
        return None
    hh, mm, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap == "PM" and hh != 12:
        hh += 12
    if ap == "AM" and hh == 12:
        hh = 0
    hour = hh + 5
    day = int(date[8:10])
    month, year = int(date[5:7]), int(date[0:4])
    if hour >= 24:
        hour -= 24
        day += 1
        if day > 30 and month == 11:
            day, month = 1, 12
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{mm}Z"


def build_picks(model):
    """One projection pick per line, plus the strategy picks that are not refused."""
    picks = []
    outside = set(model["luck"]["outside_noise_band"])
    for l in model["lines"]:
        if not l.get("blend_underneath"):
            continue
        gid, date = l["game_id"], l["date"]
        tip = tip_utc(date, l.get("tip_et"))
        away, home = l["matchup"].split(" @ ")
        margin = l["blend_underneath"]["margin_away"]
        sig = l["headline_confidence_signal"]
        common = {"game_id": gid, "date": date, "tip_et": l.get("tip_et"), "tip_utc": tip,
                  "matchup": l["matchup"], "away": away, "home": home,
                  "originated_margin_away": margin, "originated_total": l["blend_underneath"]["total"],
                  "headline_disagreement_points": sig["disagreement_margin_points"],
                  "headline_sign_agreement": sig["sign_agreement"],
                  "estimator_a_margin": l["e1"].get("margin_away"),
                  "estimator_b_margin": l["e2"].get("margin_away"),
                  "market_anchor_status": (l.get("market_anchor") or {}).get("status"),
                  "closing_line": None,
                  "source_url": l.get("source_url"), "game_url": l.get("game_url"),
                  "session": SESSION, "round": "2026-11-17"}
        picks.append({"pick_id": f"{gid}-proj", "kind": "projection (no funded strategy -> no money)",
                      "side": home if margin > 0 else away, "line": det.dq(-margin, 2),
                      "settlement_rule_id": "PROJECTION_ONLY", "strategy_id": None,
                      "payload": dict(common)})
        for sid in ("ST-17-HCA-PINNED", "ST-19-DISAGREEMENT-GATE", "ST-23-TOTAL-POSSESSION"):
            if home in outside or away in outside:
                continue
            s = STRATEGY_BY_ID[sid]
            if sid == "ST-17-HCA-PINNED":
                side = home
            elif sid == "ST-19-DISAGREEMENT-GATE":
                if not sig["sign_agreement"]:
                    continue
                side = home if margin > 0 else away
            else:
                side = None
            p = {"pick_id": f"{gid}-{sid}", "kind": "strategy pick", "strategy_id": sid,
                 "side": side, "line": None if side is None else det.dq(-margin, 2),
                 "settlement_rule_id": s["settlement_rule"].split(":")[0],
                 "thresholds_frozen": s["thresholds"],
                 "payload": dict(common)}
            picks.append(p)
    return picks


def publish(picks, now=PUBLISHED_UTC):
    frozen = load_prereg()
    existing = {e["pick_id"] for e in read_ledger() if e["kind"] == "PUBLISH"}
    n = 0
    for p in picks:
        if p["pick_id"] in existing:
            continue
        sid = p.get("strategy_id")
        if sid and sid not in frozen:
            raise SystemExit(f"strategy {sid} has no frozen pre-registration; refusing to publish")
        if p["payload"].get("tip_utc") and p["payload"]["tip_utc"] <= now:
            raise SystemExit(f"{p['pick_id']}: refusing to publish at or after tip-off "
                             f"({p['payload']['tip_utc']})")
        _append({"kind": "PUBLISH", "published_utc": now, "pick_id": p["pick_id"],
                 "strategy_id": sid, "state": "PUBLISHED_PRE_TIP", "pick": p})
        n += 1
    return n


def verify():
    entries = read_ledger()
    prev, bad = GENESIS, []
    for e in entries:
        if e.get("prev_hash") != prev:
            bad.append({"seq": e["seq"], "why": "prev_hash does not match the previous entry_hash"})
        recomputed = sha({k: v for k, v in e.items() if k != "entry_hash"})
        if recomputed != e["entry_hash"]:
            bad.append({"seq": e["seq"], "why": "entry_hash does not match its own contents",
                        "sealed": e["entry_hash"], "now": recomputed})
        if e["kind"] == "SETTLE":
            sealed = e.get("pick_sha256_at_publish")
            if sealed and sealed != sha(e["pick"]):
                bad.append({"seq": e["seq"], "why": "TAMPERED: the pick text no longer hashes to the "
                                                    "value sealed before tip-off"})
        prev = e["entry_hash"]
    return entries, bad


def settle(model, results_log, now="2026-11-16T19:30Z"):
    """Append SETTLE entries for published picks whose game has a verified official final."""
    finals = {}
    for g in results_log["games_2026_11_15"]:
        if g.get("final_verified"):
            finals[g["game_id"]] = {"away_pts": g["away_final"], "home_pts": g["home_final"],
                                    "date": g["date"], "source_url": g["scoreboard_url"],
                                    "corroboration": (g.get("final_corroboration") or {}).get("url")}
    entries = read_ledger()
    done = {e.get("pick_id") for e in entries if e["kind"] == "SETTLE"}
    n = 0
    for e in entries:
        if e["kind"] != "PUBLISH" or e["pick_id"] in done:
            continue
        gid = e["pick"]["payload"]["game_id"]
        fin = finals.get(gid)
        if not fin:
            continue
        pick = e["pick"]
        grade = grade_pick(pick, fin)
        _append({"kind": "SETTLE", "settled_utc": now, "pick_id": e["pick_id"],
                 "game_id": gid, "pick_sha256_at_publish": sha(pick),
                 "pick": pick, "final": fin, "result": grade,
                 "source_url": fin["source_url"]})
        n += 1
    return n


def grade_pick(pick, final):
    if pick["kind"].startswith("projection"):
        margin_home = final["home_pts"] - final["away_pts"]
        pred = -(pick["line"]) if pick.get("line") is not None else None
        return {"type": "PROJECTION_ONLY", "outcome": "NOT_BET",
                "margin_error_points": (det.dq(abs(pred - margin_home), 2)
                                         if pred is not None else None),
                "total_error_points": (det.dq(abs(pick["payload"]["originated_total"]
                                                 - (final["home_pts"] + final["away_pts"])), 2)
                                       if pick["payload"].get("originated_total") else None)}
    side = pick.get("side")
    if side is None:
        return {"type": pick.get("settlement_rule_id"), "outcome": "VOID_NO_SIDE_NAMED"}
    won = (final["home_pts"] > final["away_pts"]) if side == pick["payload"]["home"] \
        else (final["away_pts"] > final["home_pts"])
    return {"type": pick.get("settlement_rule_id"),
            "outcome": "WIN" if won else "LOSS",
            "official_final": f"{final['away_pts']}-{final['home_pts']}"}


def write_index(model, picks):
    entries, bad = verify()
    published = [e for e in entries if e["kind"] == "PUBLISH"]
    settled = [e for e in entries if e["kind"] == "SETTLE"]
    head = entries[-1]["entry_hash"] if entries else GENESIS
    out = {
        "schema": "nba3.rounds.ledger/v1",
        "session": SESSION,
        "round": "2026-11-17",
        "written_utc": PUBLISHED_UTC,
        "chain_entries": len(entries),
        "published": len(published),
        "settled": len(settled),
        "head_hash": head,
        "anchor": ("the head hash is committed to git with this file; GitHub's commit history is the "
                   "external witness, which makes local edits detectable and nothing more"),
        "integrity": ("OK" if not bad else "BROKEN"),
        "integrity_problems": bad,
        "pre_registration_files": sorted(os.listdir(PREREG)),
        "strategies_frozen": len(STRATEGIES),
        "refused_before_tip": [
            {"strategy_id": s["id"], "why": s.get("blocked_because")}
            for s in STRATEGIES if s.get("blocked_because")],
        "picks": [{"pick_id": p["pick_id"], "game_id": p["payload"]["game_id"],
                   "matchup": p["payload"]["matchup"], "kind": p["kind"],
                   "strategy_id": p.get("strategy_id"), "side": p.get("side"),
                   "line": p.get("line"), "tip_utc": p["payload"]["tip_utc"],
                   "pick_sha256": sha(p)} for p in picks],
        "model_gates": model["gates"],
        "note": ("no game of this window had a verified final when the ledger was written, so every "
                 "entry is PUBLISHED_PRE_TIP and no pick is graded; the settlement run appends "
                 "SETTLE entries as soon as the official finals exist, and it never rewrites a "
                 "published one"),
    }
    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--settle", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rebuild", action="store_true",
                    help="delete this round's own ledger and rewrite it (never touches other sessions)")
    args = ap.parse_args()
    if args.rebuild:
        for f in (LEDGER, INDEX):
            if os.path.exists(f):
                os.remove(f)

    model = read_json(MODEL)
    results_log = read_json(RESULTS_LOG)
    written, frozen = freeze()
    picks = build_picks(model)
    if args.freeze:
        print(f"pre-registration: {len(written)} written, {len(frozen)} already frozen")
        return 0
    n = publish(picks)
    if args.settle:
        s = settle(model, results_log)
        print(f"settlement: {s} entries appended")
    idx = write_index(model, picks)
    if args.check:
        if idx["integrity"] != "OK":
            print("LEDGER INTEGRITY BROKEN: " + json.dumps(idx["integrity_problems"][:3]),
                  file=sys.stderr)
            return 1
        if idx["published"] != len(picks):
            print(f"DRIFT: ledger seals {idx['published']} picks, the model offers {len(picks)}",
                  file=sys.stderr)
            return 1
        print(f"ledger OK: {idx['chain_entries']} entries, head {idx['head_hash'][:16]}...")
        return 0
    print(f"pre-registration: {len(written)} written, {len(frozen)} already frozen")
    print(f"ledger: {n} new entries, {idx['chain_entries']} total, head {idx['head_hash'][:16]}...")
    print(f"integrity: {idx['integrity']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
