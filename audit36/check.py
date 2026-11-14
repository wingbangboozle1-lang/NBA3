#!/usr/bin/env python3
"""Session 36e18d83 — independent verification checks.

Compares the freshly transcribed official pages (audit36/data/official_refetch_2026-11-14.json)
against everything the repository publishes, and independently recomputes the numbers that
session e40cd215 published about its own engine (engine_agreement block in
data/integration/model.json) instead of trusting that summary.

Exit status 1 if any of:
  - an official-slate value disagrees with the stored slate or the published lines;
  - a team-statistics field disagrees for a team that did NOT play on 2026-11-13;
  - an injury spot-check status disagrees with the stored 07:30 PM snapshot;
  - a recomputed engine claim disagrees with the published summary block.

Expected drift (teams that DID play on 2026-11-13) is reported, not failed.
"""
from __future__ import annotations
import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = json.load(open(ROOT / "audit36/data/official_refetch_2026-11-14.json"))
OUT = ROOT / "audit36/data/results_2026-11-14.json"

results = {"meta": REF["meta"], "checks": {}}
failures = []


def fail(msg):
    failures.append(msg)


# ---------------------------------------------------------------- 1. slate
model = json.load(open(ROOT / "data/integration/model.json"))
stored_slate = json.load(open(ROOT / "data/app/official_slate.json"))["games"]
by_gid_stored = {g["game_id"]: g for g in stored_slate}
by_gid_model = {l["gid"]: l for l in model["lines"]}

slate_rows = []
for g in REF["slate_refetch"]["games"]:
    st = by_gid_stored.get(g["gid"])
    md = by_gid_model.get(g["gid"])
    ok_stored = bool(st) and (st["date"], st["time_et"], st["away"], st["home"]) == (g["date"], g["time_et"], g["away"], g["home"])
    ok_model = bool(md) and (md["date"], md["time_et"], md["away"], md["home"]) == (g["date"], g["time_et"], g["away"], g["home"])
    if not ok_stored:
        fail(f"slate {g['gid']}: stored official_slate.json disagrees with fresh official page")
    if not ok_model:
        fail(f"slate {g['gid']}: published originated line disagrees with fresh official page")
    slate_rows.append({"gid": g["gid"], "game": f"{g['away']}@{g['home']}", "date": g["date"], "time_et": g["time_et"],
                       "matches_stored_slate": ok_stored, "matches_published_line": ok_model,
                       "source_url": g["url"]})

n_141516 = len(REF["slate_refetch"]["games"])
n_lines = len(model["lines"])
if n_lines != n_141516:
    fail(f"published line count {n_lines} != official window count {n_141516}")
results["checks"]["slate"] = {
    "rows": slate_rows,
    "summary": {"official_window_games": n_141516, "published_lines": n_lines,
                "mismatches_stored": 0 if not any(not r["matches_stored_slate"] for r in slate_rows) else "see rows",
                "mismatches_published": 0 if not any(not r["matches_published_line"] for r in slate_rows) else "see rows"},
    "source_url": REF["slate_refetch"]["source_url"],
}

# ------------------------------------------------------- 2. team statistics
stored_ratings = {t["team"]: t for t in json.load(open(ROOT / "data/app/official_team_ratings_2026-11-14.json"))["teams"]}
played = set(REF["team_stats_refetch"]["teams_that_played_2026-11-13"])
FIELDS = REF["team_stats_refetch"]["fields"]
rat_rows = []
match_all = drift = mismatch_unexpected = 0
for t in REF["team_stats_refetch"]["teams"]:
    st = stored_ratings.get(t["team"])
    diffs = [f for f in FIELDS if st is None or st[f] != t[f]]
    ok = not diffs
    if ok:
        match_all += 1
    elif t["team"] in played:
        drift += 1
    else:
        mismatch_unexpected += 1
        fail(f"team stats {t['team']}: fields {diffs} changed for a team that did NOT play on 2026-11-13")
    rat_rows.append({"team": t["team"], "match": ok, "changed_fields": ",".join(diffs) if diffs else "—",
                     "played_2026-11-13": t["team"] in played,
                     "explanation": "expected drift — team played on 2026-11-13 after the stored capture"
                                    if diffs and t["team"] in played else ("—" if ok else "UNEXPECTED — flag"),
                     "source_url": REF["team_stats_refetch"]["source_url"]})
results["checks"]["team_stats"] = {
    "rows": rat_rows,
    "summary": {"teams": len(rat_rows), "fields_per_team": len(FIELDS),
                "all_fields_match": match_all, "expected_drift_only": drift,
                "unexpected_mismatch": mismatch_unexpected,
                "note": "stored snapshot captured before the 2026-11-13 games; drift on playing teams is ageing, not error"},
    "source_url": REF["team_stats_refetch"]["source_url"],
}

# ------------------------------------------------------------- 3. injuries
stored_inj = json.load(open(ROOT / "data/app/official_injuries_2026-11-13_0730PM.json"))
inj_index = {(r["matchup"], r["player"]): r["status"] for r in stored_inj["rows"] if r.get("player")}
spot_rows = []
status_mismatch = not_in_stored = 0
for r in REF["injury_spot_check"]["rows"]:
    key = (r["matchup"], r["player"])
    st = inj_index.get(key)
    if st is None:
        not_in_stored += 1
        spot_rows.append({"matchup": r["matchup"], "player": r["player"], "status_0800pm": r["status"],
                          "status_0730pm_stored": "—", "match": None,
                          "note": "not present in the stored 07:30 PM snapshot", "flag": True})
        fail(f"injury {key}: not found in stored 07:30 PM snapshot (newest stored report)")
    elif st != r["status"]:
        status_mismatch += 1
        spot_rows.append({"matchup": r["matchup"], "player": r["player"], "status_0800pm": r["status"],
                          "status_0730pm_stored": st, "match": False, "note": "STATUS DISAGREES", "flag": True})
        fail(f"injury {key}: 08:00 PM prints '{r['status']}' but stored 07:30 PM snapshot holds '{st}'")
    else:
        spot_rows.append({"matchup": r["matchup"], "player": r["player"], "status_0800pm": r["status"],
                          "status_0730pm_stored": st, "match": True, "note": "—", "flag": False})
matched = sum(1 for r in spot_rows if r["match"])
NAME2ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM", "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
# The stored snapshot records the not-yet-submitted TEAM in its own 'team' field;
# it must not be inferred from the matchup's home side (CHI@MIN is the counter-example).
nys_stored = sorted(NAME2ABBR[r["team"]] for r in stored_inj["rows"] if r["row_type"] == "team_report_status")
nys_fresh = sorted(REF["injury_spot_check"]["not_yet_submitted_2026-11-14"])
if nys_stored != nys_fresh:
    fail(f"NOT YET SUBMITTED set differs: stored {nys_stored} vs fresh {nys_fresh}")
results["checks"]["injuries"] = {
    "rows": spot_rows,
    "summary": {"spot_rows": len(spot_rows), "matched": matched, "status_mismatch": status_mismatch,
                "not_in_stored": not_in_stored,
                "newest_report_listed_on_index": REF["injury_index"]["newest_report_listed"],
                "newest_stored_snapshot": stored_inj["report_stamp"],
                "not_yet_submitted_2026-11-14_stored": nys_stored,
                "not_yet_submitted_2026-11-14_fresh": nys_fresh},
    "source_url": REF["injury_spot_check"]["source_url"],
    "index_source_url": REF["injury_index"]["source_url"],
}

# ------------------------------------------- 4. engine claims, recomputed
lines = model["lines"]
canon = {c["game_id"]: c for c in json.load(open(ROOT / "data/app/canonical.json"))["lines"]}
agree = gap_sum = 0
gaps = []
mine, theirs = [], []
for l in lines:
    c = canon.get(l["gid"])
    if c is None:
        fail(f"engine agreement: {l['gid']} missing from canonical lines")
        continue
    fav_dash = "away" if l["pred_margin_home"] < 0 else "home"
    fav_app = "away" if c["exp_margin"] < 0 else "home"
    agree += fav_dash == fav_app
    gaps.append(abs(l["orig_spread_home"] - c["orig_spread_home"]))
    mine.append(l["orig_spread_home"])
    theirs.append(c["orig_spread_home"])
sd_actual = None
try:
    margins = []
    with open(ROOT / "data/origin/games.csv") as fh:
        for row in csv.DictReader(fh):
            margins.append(int(row["home_pts"]) - int(row["away_pts"]))
    sd_actual = statistics.stdev(margins)
except Exception as exc:  # pragma: no cover
    fail(f"could not recompute sd of actual margins: {exc}")

pub = model["engine_agreement"]
recomputed = {
    "games_compared": len(gaps),
    "same_side_favoured": agree,
    "median_abs_gap": round(statistics.median(gaps), 2),
    "max_abs_gap": round(max(gaps), 2),
    # The published dispersion uses the POPULATION standard deviation; reproduced here
    # with the same estimator, plus the sample estimator as a labelled extra.
    "sd_of_dash_spreads_pstdev": round(statistics.pstdev(mine), 2),
    "sd_of_app_spreads_pstdev": round(statistics.pstdev(theirs), 2),
    "sd_of_actual_margins_pstdev": round(statistics.pstdev(margins), 2) if margins else None,
    "sd_of_dash_spreads_sample": round(statistics.stdev(mine), 2) if len(mine) > 1 else None,
    "sd_of_app_spreads_sample": round(statistics.stdev(theirs), 2) if len(theirs) > 1 else None,
    "sd_of_actual_margins_sample": round(sd_actual, 2) if sd_actual else None,
}
claim_ok = (recomputed["same_side_favoured"] == pub["same_side_favoured"]
            and recomputed["games_compared"] == pub["games_compared"]
            and abs(recomputed["median_abs_gap"] - pub["median_abs_gap"]) <= 0.01
            and abs(recomputed["max_abs_gap"] - pub["max_abs_gap"]) <= 0.01
            and abs(recomputed["sd_of_dash_spreads_pstdev"] - pub["dispersion"]["sd_of_my_spreads"]) <= 0.01
            and abs(recomputed["sd_of_app_spreads_pstdev"] - pub["dispersion"]["sd_of_their_spreads"]) <= 0.01
            and abs(recomputed["sd_of_actual_margins_pstdev"] - pub["dispersion"]["sd_of_actual_margins"]) <= 0.01)
if not claim_ok:
    fail("recomputed engine claims disagree with the published engine_agreement block")
results["checks"]["engine_claims"] = {
    "published": {"games_compared": pub["games_compared"], "same_side_favoured": pub["same_side_favoured"], "median_abs_gap": pub["median_abs_gap"],
                  "max_abs_gap": pub["max_abs_gap"],
                  "sd_of_dash_spreads": pub["dispersion"]["sd_of_my_spreads"],
                  "sd_of_app_spreads": pub["dispersion"]["sd_of_their_spreads"],
                  "sd_of_actual_margins": pub["dispersion"]["sd_of_actual_margins"]},
    "recomputed": recomputed, "agree": claim_ok,
    "source_url": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json",
}

# FX-01 independent Monte-Carlo: joint P both legs win, two legs p=0.58, Gaussian copula rho=+0.3
random.seed(2600231)
n = 200_000
z = 0.2027  # Phi^-1(0.5805); published example uses p=0.58 -> Phi^-1(0.58)=0.20189
# Use exact inverse via bisect on the CDF to avoid a hardcoded approximation.
def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
def phi_inv(p):
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if phi(mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2
z = phi_inv(0.58)
rho = 0.3
hits = 0
g1, g2 = math.sqrt(1 + rho), math.sqrt(1 - rho)
for _ in range(n):
    a = random.gauss(0, 1); b = random.gauss(0, 1)
    x = z + (g1 * a + g2 * b) / math.sqrt(2)  # correlated standard normals around threshold z
    y = z + (g1 * a - g2 * b) / math.sqrt(2)
    hits += (x > 0) and (y > 0)
mc = hits / n
fx = 0.3832
fx_ok = abs(mc - fx) < 0.01
if not fx_ok:
    fail(f"FX-01 Monte Carlo {mc:.4f} disagrees with published corrected value {fx}")
results["checks"]["fx01_montecarlo"] = {
    "published_corrected_joint": fx, "montecarlo_n": n, "montecarlo_joint": round(mc, 4),
    "agree": fx_ok,
    "source_url": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/verify/pages/corrections.html",
}

results["checks"]["gates"] = {
    "rows": [{"id": g["id"], "name": g["name"], "status": g["status"], "threshold": g["threshold"],
              "source_url": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json"}
             for g in model["gates"]],
    "summary": {"pass": sum(1 for g in model["gates"] if g["status"] == "PASS"),
                "partial": sum(1 for g in model["gates"] if g["status"] == "PARTIAL"),
                "fail": sum(1 for g in model["gates"] if g["status"] == "FAIL")},
}

results["verdict"] = {
    "failures": failures,
    "ok": not failures,
}
OUT.write_text(json.dumps(results, indent=1))
print(json.dumps(results["verdict"], indent=1))
print("slate:", results["checks"]["slate"]["summary"])
print("team_stats:", results["checks"]["team_stats"]["summary"])
print("injuries:", results["checks"]["injuries"]["summary"])
print("engine_claims recomputed:", recomputed, "agree:", claim_ok)
print("fx01 MC:", round(mc, 4), "vs 0.3832 ->", fx_ok)
sys.exit(0 if not failures else 1)
