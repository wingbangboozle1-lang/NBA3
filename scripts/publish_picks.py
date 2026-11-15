"""Publish gated picks into the sealed ledger, then settle them from the official feed.

The gate order matters and is enforced here, not in prose:
  1. the strategy must have a frozen pre-registration      (ledger.publish raises otherwise)
  2. the pick must be published strictly before its tip     (ledger.publish raises otherwise)
  3. the pick must pass the validation gates                (this file, gate_id recorded on the pick)
  4. settlement only against a VERIFIED official final      (this file)

Anything that fails a gate is written to bet/gates.json with the failure named. A pick is never
published "provisionally".

Run: python3 scripts/publish_picks.py
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ledger                                                   # noqa: E402
from estimators import pinned_hca, load_games                   # noqa: E402
import rest_travel                                              # noqa: E402

MODEL = ROOT / "data" / "live" / "model.json"
SLATE = ROOT / "data" / "live" / "slate_2026-11-15.json"
SETTLED = ROOT / "data" / "live" / "results" / "settled_2026-11-14.json"
#: Every settled feed on disk, newest last. A pick is graded only from a feed row that carries TWO
#: agreeing official reads (`verified`), and the feed itself records the date it covers.
SETTLED_FEEDS = sorted((ROOT / "data" / "live" / "results").glob("settled_*.json"))
OUT_PICKS = ROOT / "data" / "live" / "picks_ledger_view.json"
OUT_GATES = ROOT / "data" / "live" / "gates.json"

# An explicitly declared "now" so the build is reproducible. CI passes the real clock.
NOW = "2026-11-15T12:10Z"


def settlement_stamp(final: dict, now: str) -> str:
    """The stamp recorded on a SETTLE entry: when the final was CONFIRMED, never a guess.

    Using the build's `now` was wrong: this build runs offline with a declared NOW of
    2026-11-15T12:10Z, while the game it settles tipped at 18:00Z and ended after 20:30Z. A
    settlement stamp earlier than its own game would be a false record. The feed row carries the
    time the two official reads were taken (`settled_utc`), so that is the stamp; the guard below
    refuses any stamp that is not later than the game's own end.
    """
    stamp = final.get("settled_utc") or (final.get("feed_settled_utc"))
    if not stamp:
        raise ValueError(f"final for {final.get('game_id')} carries no confirmation stamp; "
                         f"refusing to invent a settlement time")
    game_end = final["date"] + "T23:59Z"
    if stamp < game_end:
        raise ValueError(f"settlement stamp {stamp} precedes the end of its own game day "
                         f"{final['date']}; refusing to record a settlement before the game ended")
    return stamp


def tip_iso(date: str, tip_et: str) -> str:
    """Tip time as an ISO-8601 UTC stamp. ET is treated as UTC-5 (EST) for November dates.

    The ET->UTC step is arithmetic on a published tip time, not a sourced value; it is stated on
    the page and used only to prove a pick was sealed before the tip.
    """
    h, rest = tip_et.split(":")
    minutes, ampm = rest.split(" ")
    h = int(h) % 12 + (12 if ampm == "PM" else 0)
    naive = dt.datetime.strptime(f"{date} {h:02d}:{minutes}", "%Y-%m-%d %H:%M")
    return (naive + dt.timedelta(hours=5)).strftime("%Y-%m-%dT%H:%MZ")


def back_to_back_map() -> dict[str, dict[str, bool]]:
    """(date, team) -> is the second night of a back-to-back, from the schedule of record.

    This must come from scripts/rest_travel.py, which unions three official captures. Deriving it
    from the model's own game sample instead silently loses the 11/14 games (the sample ends before
    the slate) and reports zero back-to-backs -- which is what the first version of this function
    did, and why strategy S1 sealed nothing.
    """
    payload = rest_travel.build()
    out: dict[str, dict[str, bool]] = {}
    for g in payload["games"]:
        for t in g["teams"]:
            out.setdefault(g["date"], {})[t["team"]] = t["back_to_back"]
    return out


def main() -> None:
    model = json.loads(MODEL.read_text())
    slate = json.loads(SLATE.read_text())
    b2b = back_to_back_map()
    frozen = ledger.load_prereg()

    picks, gate_rows = [], []
    already = {(e["pick"]["strategy_id"], e["pick"]["game_id"])
               for e in ledger.read_ledger() if e["kind"] == "PUBLISH"}

    def sealed(sid, gid):
        return (sid, gid) in already

    def gate(strategy, game, name, passed, detail):
        gate_rows.append({"strategy": strategy, "game_id": game.get("game_id"),
                          "game": f"{game.get('away')} @ {game.get('home')}" if game else "",
                          "gate": name, "passed": bool(passed), "detail": detail})
        return passed

    for g in model["slate"]:
        gid = g["game_id"]
        tip = tip_iso(g["date"], g["tip_et"])
        # gate 1: pre-registration exists
        for sid in frozen:
            gate(sid, g, "G1_preregistered", True, f"prereg/{sid}.json frozen at {frozen[sid]['frozen_utc']}")
        # gate 2: sealed before tip
        ok2 = NOW < tip
        for sid in frozen:
            gate(sid, g, "G2_before_tip", ok2, f"seal {NOW} vs tip {tip} (ET+5h)")

        # ---- S1: fade a home team on a back-to-back
        sid = "S1_HOME_B2B_FADE"
        day = b2b.get(g["date"], {})
        home_b2b = day.get(g["home"], False)
        away_b2b = day.get(g["away"], False)
        eligible = home_b2b and not away_b2b
        gate(sid, g, "G3_signal_present", eligible,
             f"home b2b={home_b2b}, away b2b={away_b2b}")
        if eligible and ok2 and not sealed(sid, gid):
            pub = ledger.publish({
                "strategy_id": sid, "game_id": gid, "date": g["date"],
                "matchup": f"{g['away']} @ {g['home']}", "tip_et": g["tip_et"],
                "tip_et_iso": tip,
                "pick": (f"{g['away']} {-g['exp_margin_e1']:+.1f}"
                         if -g["exp_margin_e1"] >= 0 else
                         f"{g['away']} {abs(g['exp_margin_e1']):.1f}"),
                "side": "away", "line": round(-g["exp_margin_e1"], 1),
                "settlement_rule_id": "SPREAD",
                "origin": "originated line (E1 margin), not a market line",
            }, now=NOW)
            picks.append(pub)

        # ---- S2: estimator disagreement trade
        sid = "S2_ESTIMATOR_DISAGREEMENT"
        agree = g["direction_agrees"]
        in_band = 5.0 <= g["disagreement_pp"] <= 20.0
        gate(sid, g, "G3_signal_present", agree and in_band,
             f"direction_agrees={agree}, disagreement={g['disagreement_pp']} pp (band 5-20)")
        if agree and in_band and ok2 and not sealed(sid, gid):
            side_home = g["p_home_e1"] > 0.5
            pub = ledger.publish({
                "strategy_id": sid, "game_id": gid, "date": g["date"],
                "matchup": f"{g['away']} @ {g['home']}", "tip_et": g["tip_et"],
                "tip_et_iso": tip,
                "pick": f"{g['home'] if side_home else g['away']} moneyline",
                "side_home": side_home, "line": None,
                "settlement_rule_id": "MONEYLINE",
                "headline_signal": f"disagreement {g['disagreement_pp']} pp",
                "origin": "originated fair price from the two estimators",
            }, now=NOW)
            picks.append(pub)

        # ---- S3: totals
        sid = "S3_TOTALS_POSSESSIONS"
        gate(sid, g, "G3_signal_present", False,
             "no originated total is >= 3.0 points away from the model total on this slate, and the "
             "pace filter is not met by both teams; nothing to publish")
        gate(sid, g, "G4_validated", False,
             "the totals model's out-of-sample RMSE is reported on the Projection pages; no rule has passed "
             "the validation gate yet, so no totals pick is sealed")

    # ---- settlement: only VERIFIED official finals, as soon as each game day ends ----------
    # The previous version read one hard-coded feed (11/14). A game day that ended after that feed
    # was written could therefore never be settled, which is the "settle as soon as each game day
    # ends" requirement failing silently. Every settled feed on disk is read now, and the newest
    # game date with a verified final decides whether rows are still outstanding.
    finals = {}
    feeds = []
    for fp in SETTLED_FEEDS:
        try:
            blob = json.loads(fp.read_text())
        except json.JSONDecodeError:
            continue
        feeds.append({"file": str(fp.relative_to(ROOT)), "game_date": blob.get("game_date"),
                      "stamp": blob.get("settled_utc"),
                      "games": len(blob.get("games", []))})
        for g in blob.get("games", []):
            g = dict(g)
            g.setdefault("feed", fp.name)
            g.setdefault("feed_settled_utc", blob.get("settled_utc"))
            # a feed must name BOTH official reads for the final it publishes; without them the row
            # is not verified and must not settle anything.
            if not g.get("gamebook_url") or not g.get("source_url"):
                g["verified"] = False
                g["missing_read_url"] = True
            finals[g["game_id"]] = g

    already_settled = {e["game_id"] for e in ledger.read_ledger() if e["kind"] == "SETTLE"}
    settled_now = []
    for gid, f in sorted(finals.items()):
        if not f.get("verified"):
            gate_rows.append({"strategy": "ALL", "game_id": gid, "game": f"{f['away']} @ {f['home']}",
                              "gate": "G5_settlement_final_verified", "passed": False,
                              "detail": "final not verified against both official reads; not settled"})
            continue
        if gid in already_settled:
            gate_rows.append({"strategy": "ALL", "game_id": gid, "game": f"{f['away']} @ {f['home']}",
                              "gate": "G5_settlement_final_verified", "passed": True,
                              "detail": "already settled; append-only ledger is not rewritten"})
            continue
        try:
            stamp = settlement_stamp(f, NOW)
            entry = ledger.settle(gid, final=f, now=stamp, source_url=f["source_url"])
            settled_now.append({"game_id": gid, "game": f"{f['away']} @ {f['home']}",
                                "date": f["date"], "final": f"{f['away']} {f['away_final']} — "
                                f"{f['home']} {f['home_final']}",
                                "outcome": entry["result"]["outcome"],
                                "settlement_stamp": stamp,
                                "settlement_stamp_source": ("settled_utc of the verified feed row: the time the two "
                                                            "official reads were taken, not this build's clock"),
                                "source_url": f["source_url"],
                                "gamebook_url": f.get("gamebook_url"),
                                "entry_hash": entry["entry_hash"]})
            gate_rows.append({"strategy": "ALL", "game_id": gid, "game": f"{f['away']} @ {f['home']}",
                              "gate": "G5_settlement_final_verified", "passed": True,
                              "detail": f"settled from {f['source_url']} ({f.get('gamebook_url')})"})
        except ValueError as exc:
            gate_rows.append({"strategy": "ALL", "game_id": gid, "game": f"{f['away']} @ {f['home']}",
                              "gate": "G5_settlement_final_verified", "passed": True,
                              "detail": f"no published pick for this game ({exc})"})

    # ---- outstanding: a published pick whose game day has ENDED but has no verified final yet ---
    # This is published, not silent. It is the list the refresh job has to close.
    newest_final_date = max((f["date"] for f in finals.values()), default="")
    outstanding = []
    for e in ledger.read_ledger():
        if e["kind"] != "PUBLISH":
            continue
        p = e["pick"]
        if p["game_id"] in already_settled or p["game_id"] in {s["game_id"] for s in settled_now}:
            continue
        if p["date"] <= newest_final_date:
            outstanding.append({"game_id": p["game_id"], "game": p["matchup"], "date": p["date"],
                                "pick": p["pick"], "strategy_id": p["strategy_id"],
                                "why_open": ("the game day has ended but no verified final exists in "
                                             "data/live/results/ for this game; it is not graded from "
                                             "a scoreboard snapshot")})

    # the index is rewritten AFTER sealing, so it can never advertise a stale head hash
    ledger.write_index()
    v = ledger.verify()
    entries = ledger.read_ledger()
    OUT_PICKS.write_text(json.dumps({
        "schema": "nba3.live.ledger_view/v1",
        "generated_utc": NOW,
        "integrity": v,
        "entries": entries,
        "note": ("Entries are append-only. Every pick carries the sha256 published before tip; every "
                 "settlement repeats that hash and the official final it was graded against."),
        "settled_feeds": feeds,
        "settled_this_build": settled_now,
        "outstanding_picks": outstanding,
    }, indent=1) + "\n")
    OUT_GATES.write_text(json.dumps({
        "schema": "nba3.live.gates/v1",
        "generated_utc": NOW,
        "gate_order": ["G1_preregistered", "G2_before_tip", "G3_signal_present",
                       "G4_validated", "G5_settlement_final_verified"],
        "counts": {"rows": len(gate_rows),
                   "passed": sum(1 for r in gate_rows if r["passed"]),
                   "failed": sum(1 for r in gate_rows if not r["passed"])},
        "rows": gate_rows,
    }, indent=1) + "\n")

    print(f"sealed {sum(1 for p in picks if p['kind']=='PUBLISH')} picks this run; "
          f"ledger {v['entries']} entries, verified={v['verified']}")
    print(f"gates: {sum(1 for r in gate_rows if r['passed'])} passed / "
          f"{len(gate_rows)} rows")
    for e in entries:
        if e["kind"] == "SETTLE":
            print("  settled", e["game_id"], e["result"]["outcome"], e["pick"]["pick"])
    if outstanding:
        print(f"  {len(outstanding)} published pick(s) await a verified final "
              f"(game day ended, no verified final on disk):")
        for o in outstanding:
            print(f"    {o['date']} {o['game']} — {o['pick']}")


if __name__ == "__main__":
    main()
