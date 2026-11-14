#!/usr/bin/env python3
"""What did the 2026-11-14 refresh actually change?  (session arena/25418e3f-nba3)

Compares the published artefact BEFORE the refresh
(``data/app/lab_snapshot_2026-11-14T0105Z.json``, the previous session's lab output
kept verbatim for exactly this purpose) with the artefact AFTER it (``data/app/lab.json``),
and writes a field-by-field delta:

  * every originated line: spread, total and P(home win), old vs new and the movement;
  * every strategy on the leaderboard: n, hit rate, edge, p, tier;
  * the headline accuracy numbers and the luck threshold;
  * the availability flag each game carried then and carries now.

This is deliberately a *diff of published artefacts*, not a re-derivation: it can
therefore be checked by anyone with the two files, and it cannot disagree with what
the site shows.  Each row is linked to the official page the changed input came from.

Run:  python3 scripts/snapshot_delta.py
Writes: data/app/snapshot_delta.json
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
OLD = os.path.join(APP, "lab_snapshot_2026-11-14T0105Z.json")
NEW = os.path.join(APP, "lab.json")
MANIFEST = os.path.join(APP, "snapshot_manifest.json")
OUT = os.path.join(APP, "snapshot_delta.json")


def load(path, *, wrap=False):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return d["lab"] if wrap else d


def r6(v):
    return None if v is None else round(float(v), 4)


def main():
    old = load(OLD, wrap=True)
    new = load(NEW)
    man = load(MANIFEST) if os.path.exists(MANIFEST) else {}
    src_results = man.get("results_log", {}).get("source_url", "https://www.nba.com/games?date=")
    src_stats = (man.get("ratings") or {}).get("source_url",
                                               "https://www.nba.com/stats/teams/advanced")
    src_injury = (man.get("injuries") or {}).get("source_url", "")
    src_rule = "https://official.nba.com/nba-injury-report-2026-27-season/"

    old_lines = {l["game_id"]: l for l in old["lines"]}
    lines = []
    for l in new["lines"]:
        o = old_lines.get(l["game_id"])
        if o is None:
            continue
        d_spread = (l["orig_spread_home"] or 0) - (o["orig_spread_home"] or 0)
        d_total = (l["orig_total"] or 0) - (o["orig_total"] or 0)
        d_p = (l["p_home_win"] or 0) - (o["p_home_win"] or 0)
        lines.append({
            "date": l["date"], "matchup": f"{l['away']}@{l['home']}", "game_id": l["game_id"],
            "spread_before": r6(o["orig_spread_home"]), "spread_after": r6(l["orig_spread_home"]),
            "spread_move": r6(d_spread),
            "total_before": r6(o["orig_total"]), "total_after": r6(l["orig_total"]),
            "total_move": r6(d_total),
            "p_home_before": r6(o["p_home_win"]), "p_home_after": r6(l["p_home_win"]),
            "p_home_move": r6(d_p),
            "outs_before_home": o.get("out_count_home"), "outs_after_home": l.get("out_count_home"),
            "outs_before_away": o.get("out_count_away"), "outs_after_away": l.get("out_count_away"),
            "drivers": [d for d in (
                "results log extended to 2026-11-13 (ratings refit)"
                if abs(d_spread) > 1e-9 else None,
                "official team advanced statistics re-read after the 11/13 games (pace inputs)"
                if abs(d_total) > 1e-9 else None,
                "availability state recomputed against the 2026-11-14 report and the filing rule"
                if (o.get("out_count_home"), o.get("out_count_away"))
                != (l.get("out_count_home"), l.get("out_count_away")) else None,
            ) if d],
            "sources": [src_results, src_stats] + ([src_injury] if src_injury else []),
            "game_url": l["nba_game_url"],
        })
    lines.sort(key=lambda x: (x["date"], x["matchup"]))

    old_strats = {s["id"]: s for s in old["strategies"]}
    strats = []
    for s in new["strategies"]:
        o = old_strats.get(s["id"])
        if o is None:
            continue
        strats.append({
            "id": s["id"], "name": s["name"],
            "n_before": o["n"], "n_after": s["n"],
            "rate_before": r6(o["rate"]), "rate_after": r6(s["rate"]),
            "edge_before_pp": r6(o["edge_pp"]), "edge_after_pp": r6(s["edge_pp"]),
            "p_after": r6(s["p_two_sided"]),
            "tier_before": o.get("tier"), "tier_after": s.get("tier"),
            "verdict_after": s.get("verdict"),
            "sources": [src_results],
        })
    strats.sort(key=lambda x: x["id"])

    def head(block, keys):
        return {k: {"before": r6(old[block].get(k)), "after": r6(new[block].get(k))}
                for k in keys}

    headline = {
        "accuracy": head("residuals", ("n", "margin_rmse", "margin_baseline_rmse",
                                       "total_rmse", "total_baseline_rmse", "margin_bias",
                                       "total_bias", "home_win_rate", "ot_rate", "avg_total",
                                       "brier")),
        "luck_test": {k: {"before": r6(old["luck_test"].get(k)),
                          "after": r6(new["luck_test"].get(k))}
                      for k in ("threshold_pp", "median_pp", "max_pp", "rules", "iterations")},
    }

    old_picks = {p["game_id"]: p for p in old["picks"]}
    flags = []
    for p in new["picks"]:
        o = old_picks.get(p["game_id"])
        if o is None or o.get("availability_flag") == p["availability_flag"]:
            continue
        flags.append({
            "date": p["date"], "matchup": f"{p['away']}@{p['home']}", "game_id": p["game_id"],
            "flag_before": o["availability_flag"], "flag_after": p["availability_flag"],
            "detail_before": o["availability_detail"], "detail_after": p["availability_detail"],
            "sources": [src_injury, src_rule, p["nba_game_url"]],
        })
    flags.sort(key=lambda x: (x["date"], x["matchup"]))

    moved = [l for l in lines if abs(l["spread_move"]) > 0.005 or abs(l["total_move"]) > 0.005]
    out = {
        "schema": "nba3.snapshot_delta/v1",
        "session": "arena/25418e3f-nba3",
        "built_on": "2026-11-14",
        "before_file": "data/app/lab_snapshot_2026-11-14T0105Z.json",
        "after_file": "data/app/lab.json",
        "before_inputs": {
            "results_log_games": old["meta"]["games_captured"],
            "ratings_retrieved_stamp": "2026-11-14T01:05Z (read while the 11/13 slate was live)",
            "injury_report": "2026-11-13 07:45 PM ET",
        },
        "after_inputs": {
            "results_log_games": new["meta"]["games_captured"],
            "ratings_retrieved_stamp": (man.get("ratings") or {}).get("retrieved_stamp"),
            "injury_report": (man.get("injuries") or {}).get("report_stamp"),
        },
        "counts": {
            "lines_compared": len(lines),
            "lines_moved": len(moved),
            "median_abs_spread_move": r6(sorted(abs(l["spread_move"]) for l in lines)[len(lines) // 2]),
            "max_abs_spread_move": r6(max(abs(l["spread_move"]) for l in lines)),
            "median_abs_total_move": r6(sorted(abs(l["total_move"]) for l in lines)[len(lines) // 2]),
            "max_abs_total_move": r6(max(abs(l["total_move"]) for l in lines)),
            "availability_flags_changed": len(flags),
            "strategies_compared": len(strats),
            "strategies_whose_n_changed": sum(1 for x in strats if x["n_before"] != x["n_after"]),
        },
        "headline": headline,
        "lines": lines,
        "availability_flag_changes": flags,
        "strategies": strats,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    c = out["counts"]
    print("wrote", os.path.relpath(OUT, ROOT))
    print(f"  {c['lines_compared']} lines compared, {c['lines_moved']} moved; "
          f"median |spread move| {c['median_abs_spread_move']}, "
          f"max {c['max_abs_spread_move']}; median |total move| {c['median_abs_total_move']}, "
          f"max {c['max_abs_total_move']}")
    print(f"  availability flags changed on {c['availability_flags_changed']} of "
          f"{len(new['picks'])} games")
    print(f"  walk-forward n {headline['accuracy']['n']['before']} -> "
          f"{headline['accuracy']['n']['after']}; margin RMSE "
          f"{headline['accuracy']['margin_rmse']['before']} -> "
          f"{headline['accuracy']['margin_rmse']['after']} "
          f"(baseline {headline['accuracy']['margin_baseline_rmse']['before']} -> "
          f"{headline['accuracy']['margin_baseline_rmse']['after']})")
    print(f"  luck threshold {headline['luck_test']['threshold_pp']['before']} pp -> "
          f"{headline['luck_test']['threshold_pp']['after']} pp; funded strategies before "
          f"{sum(1 for x in old['strategies'] if x['tier'] == 'T1')}, after "
          f"{sum(1 for x in new['strategies'] if x['tier'] == 'T1')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
