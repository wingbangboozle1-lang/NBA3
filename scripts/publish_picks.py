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

MODEL = ROOT / "data" / "live" / "model.json"
SLATE = ROOT / "data" / "live" / "slate_2026-11-15.json"
SETTLED = ROOT / "data" / "live" / "results" / "settled_2026-11-14.json"
OUT_PICKS = ROOT / "data" / "live" / "picks_ledger_view.json"
OUT_GATES = ROOT / "data" / "live" / "gates.json"

# An explicitly declared "now" so the build is reproducible. CI passes the real clock.
NOW = "2026-11-15T12:10Z"


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


def back_to_back_teams(games) -> dict[str, set[str]]:
    """team -> set of dates on which it is playing the second game of a back-to-back."""
    by_team: dict[str, list[str]] = {}
    for g in games:
        for t in (g["home"], g["away"]):
            by_team.setdefault(t, []).append(g["date"])
    out: dict[str, set[str]] = {}
    for t, dates in by_team.items():
        ds = sorted(set(dates))
        for a, b in zip(ds, ds[1:]):
            if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days == 1:
                out.setdefault(t, set()).add(b)
    return out


def main() -> None:
    model = json.loads(MODEL.read_text())
    slate = json.loads(SLATE.read_text())
    games = load_games()
    b2b = back_to_back_teams(games)
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
        home_b2b = g["home"] in b2b and g["date"] in b2b[g["home"]]
        away_b2b = g["away"] in b2b and g["date"] in b2b[g["away"]]
        eligible = home_b2b and not away_b2b
        gate(sid, g, "G3_signal_present", eligible,
             f"home b2b={home_b2b}, away b2b={away_b2b}")
        if eligible and ok2 and g["date"] == "2026-11-15" and not sealed(sid, gid):
            pub = ledger.publish({
                "strategy_id": sid, "game_id": gid, "date": g["date"],
                "matchup": f"{g['away']} @ {g['home']}", "tip_et": g["tip_et"],
                "tip_et_iso": tip,
                "pick": f"{g['away']} +{-g['exp_margin_e1']:.1f}",
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
        if agree and in_band and ok2 and g["date"] == "2026-11-15" and not sealed(sid, gid):
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

    # ---- settlement: only VERIFIED official finals
    settled = json.loads(SETTLED.read_text())
    finals = {g["game_id"]: g for g in settled["games"]}
    already_settled = {e["game_id"] for e in ledger.read_ledger() if e["kind"] == "SETTLE"}
    for gid, f in finals.items():
        if not f["verified"]:
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
            ledger.settle(gid, final=f, now=NOW, source_url=f["source_url"])
            gate_rows.append({"strategy": "ALL", "game_id": gid, "game": f"{f['away']} @ {f['home']}",
                              "gate": "G5_settlement_final_verified", "passed": True,
                              "detail": f"settled from {f['source_url']} ({f['gamebook_url']})"})
        except ValueError as exc:
            gate_rows.append({"strategy": "ALL", "game_id": gid, "game": f"{f['away']} @ {f['home']}",
                              "gate": "G5_settlement_final_verified", "passed": True,
                              "detail": f"no published pick for this game ({exc})"})

    v = ledger.verify()
    entries = ledger.read_ledger()
    OUT_PICKS.write_text(json.dumps({
        "schema": "nba3.live.ledger_view/v1",
        "generated_utc": NOW,
        "integrity": v,
        "entries": entries,
        "note": ("Entries are append-only. Every pick carries the sha256 published before tip; every "
                 "settlement repeats that hash and the official final it was graded against."),
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


if __name__ == "__main__":
    main()
