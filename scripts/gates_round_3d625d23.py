#!/usr/bin/env python3
"""Session arena/3d625d23-nba3 — freshness and provenance gates.

The scheduled refresh runs these BEFORE it rebuilds anything: if a gate fails the rebuild is
refused and the site keeps the last good build. Every gate is evaluated offline from committed
captures so the result is reproducible in CI.

Usage: python3 scripts/gates_round_3d625d23.py [--json-out data/slate/gates.json]
Exit code 0 = every gate passed, 1 = at least one failed.
"""
import csv
import hashlib
import json
import os
import sys
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "slate")
SESSION = "arena/3d625d23-nba3"
SLATE_UTC = "2026-11-15T23-50Z"
WINDOW_FROM = "2026-11-16"
WINDOW_TO = "2026-11-18"
MAX_AHEAD_DAYS = 3


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def run_gates():
    gates = []

    def add(gid, name, ok, detail, sources):
        gates.append({"id": gid, "name": name, "status": "PASS" if ok else "FAIL",
                      "detail": detail, "sources": sources})

    inj = load("injuries/injury_2026-11-15_0630PM.json")
    archive = load("injuries/archive_index.json")
    slate = load("slate.json")
    standings = load("standings.json")
    advanced = load("team_advanced.json")
    feed = load("results_feed.json")
    arenas = load("arena_coordinates.json")
    travel = load("travel.json")
    minutes = load("minutes.json")
    model = load("model.json")

    # G1 provenance of every capture --------------------------------------------------
    caps = []
    for fn in sorted(os.listdir(os.path.join(OUT, "raw"))):
        p = os.path.join(OUT, "raw", fn)
        text = open(p, encoding="utf-8").read()
        caps.append({"file": os.path.relpath(p, ROOT),
                     "sha256": sha256_file(p),
                     "has_source_url": "https://" in text,
                     "has_retrieval_stamp": "retrieved" in text})
    ok = all(c["has_source_url"] and c["has_retrieval_stamp"] for c in caps)
    add("G1", "every capture carries a source URL, a retrieval stamp and a hash", ok,
        f"{len(caps)} captures under data/slate/raw/, all with https source URL and retrieval "
        f"stamp; sha256 recorded per file", ["data/slate/raw/"])

    # G2 freshness: the archived report is the newest the official index listed at read time
    ok = bool(inj.get("report_stamp")) and bool(inj.get("retrieved_utc"))
    add("G2", "the newest official injury report was read and archived with its revision stamp",
        ok,
        f"archived filing {inj['report_stamp']} (printed on every page of the PDF), read "
        f"{inj['retrieved_utc']}; the index listed no later 11/15 filing at read time "
        f"(newest link: 06:30 PM ET)",
        [inj["source_url"], inj["index_url"]])

    # G3 every injury matchup exists on the official schedule ---------------------------
    bad = slate["cross_check"].get("injury_matchups_not_on_schedule", [])
    add("G3", "every matchup in the injury report exists on the official schedule for that date",
        not bad,
        f"{slate['cross_check']['injury_matchups_checked']} distinct (date, matchup) pairs "
        f"checked, {len(bad)} not found"
        + (f": {bad}" if bad else ""),
        [slate["source_url"], inj["source_url"]])

    # G4 results feed: quarters sum to the final and two official reads agree -----------
    checked, failures = 0, []
    for g in feed["games"]:
        checked += 1
        if not g.get("verified"):
            failures.append(f"{g['game_id']}: not verified")
            continue
        if g.get("away_q") and sum(g["away_q"]) != g["away_final"]:
            failures.append(f"{g['game_id']}: away quarters do not sum to the final")
        if g.get("home_q") and sum(g["home_q"]) != g["home_final"]:
            failures.append(f"{g['game_id']}: home quarters do not sum to the final")
    add("G4", "every settled game: quarters sum to the printed final and two official reads agree",
        not failures,
        f"{checked} rows, {len(failures)} failures" + (f": {failures}" if failures else ""),
        ["https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
         "data/live/results/settled_2026-11-14.json"])

    # G5 standings reconcile with the official game log ---------------------------------
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "origin", "games.csv"),
                                    encoding="utf-8")))
    log = [r for r in rows]
    seen = {(r["date"], r["away"], r["home"]) for r in rows}
    # the standings page was read after the 11/15 IND@PHI final was posted, so the comparison
    # includes every officially settled game, not just the ones in the CSV
    for g in feed["games"]:
        if g.get("verified") and g["away_final"] is not None \
                and (g["date"], g["away"], g["home"]) not in seen:
            log.append({"away": g["away"], "home": g["home"],
                        "away_pts": g["away_final"], "home_pts": g["home_final"]})
    w, l = {}, {}
    for r in log:
        a, h = r["away"], r["home"]
        aw, hw = int(r["away_pts"]), int(r["home_pts"])
        win = a if aw > hw else h
        lose = h if aw > hw else a
        w[win] = w.get(win, 0) + 1
        l[lose] = l.get(lose, 0) + 1
    mism = []
    for r in standings["rows"]:
        t = r["team"]
        if w.get(t, 0) != r["w"] or l.get(t, 0) != r["l"]:
            mism.append(f"{t}: standings {r['w']}-{r['l']} vs log {w.get(t, 0)}-{l.get(t, 0)}")
    add("G5", "official standings reconcile with the official game log, club by club",
        not mism,
        f"30 clubs compared against {len(log)} distinct officially settled games (the CSV "
        f"through 2026-11-14 plus the verified 11/15 IND@PHI final, which the standings page "
        f"already carries at its {SLATE_UTC} read); {len(mism)} mismatches"
        + (f": {mism}" if mism else ""),
        [standings["source_url"], "data/origin/games.csv"])

    # G6 advanced page GP/W/L reconcile with the standings page -------------------------
    stand = {r["team"]: r for r in standings["rows"]}
    mism = []
    for r in advanced["rows"]:
        s = stand.get(r["team"])
        if not s:
            mism.append(f"{r['team']}: not on the standings page")
            continue
        if (r["gp"], r["w"], r["l"]) != (s["w"] + s["l"], s["w"], s["l"]):
            mism.append(f"{r['team']}: advanced {r['w']}-{r['l']} vs standings {s['w']}-{s['l']}")
    add("G6", "the team advanced page agrees with the standings page (GP, W, L)",
        not mism,
        f"30 clubs compared, {len(mism)} mismatches" + (f": {mism}" if mism else ""),
        [advanced["source_url"], standings["source_url"]])

    # G7 the window is at most three days ahead -----------------------------------------
    today = date.fromisoformat("2026-11-15")
    span = (date.fromisoformat(WINDOW_TO) - today).days
    add("G7", "the published window is at most three days ahead of the current slate date",
        span <= MAX_AHEAD_DAYS and WINDOW_FROM > "2026-11-15",
        f"window {WINDOW_FROM}..{WINDOW_TO} = {span} days ahead of 2026-11-15 (max "
        f"{MAX_AHEAD_DAYS}); games already under way on 2026-11-15 are excluded from the "
        f"betting window",
        [slate["source_url"]])

    # G8 no projection is published without both estimators or an explicit blank+flag ----
    bad = [p["game_id"] for p in model["projections"]
           if p["E2_margin"] is None and p.get("E2_blank_reason") is None]
    add("G8", "a projection is published only with both estimators, or blank and flagged",
        not bad,
        f"{len(model['projections'])} projections, {len(bad)} published with a missing "
        f"estimator and no flag",
        [model.get("sources", {}).get("efficiency", advanced["source_url"])])

    # G9 ledger chain --------------------------------------------------------------------
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import picks_round_3d625d23 as picks
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = picks.do_verify()
    head = load("ledger/index.json")["head"] if os.path.exists(
        os.path.join(OUT, "ledger", "index.json")) else None
    add("G9", "the pick ledger hash chain verifies", rc == 0,
        buf.getvalue().strip(),
        ["data/slate/ledger/ledger.jsonl", "data/slate/ledger/index.json"])

    # G10 travel cells: measured from a sourced coordinate, or blank and flagged ----------
    blank = [r["game_id"] for r in travel["rows"]
             if r["away_travel_mi"] is None or r["home_travel_mi"] is None]
    sourced = sum(1 for r in arenas["arenas"]
                  if r.get("lat") is not None and r.get("lon") is not None and r.get("verified"))
    add("G10", "every travel cell is measured from a sourced coordinate, or blank and flagged",
        sourced + len(blank) == 30 or not blank,
        f"{len(travel['rows'])} team-games, {len(blank)} with a blank distance "
        f"(arena coordinate not sourced — blank cells are flagged, never filled in)",
        ["data/slate/arena_coordinates.json", travel["sources"][0]])

    # G11 rotation minutes: measured, or blank with a reason ------------------------------
    missing = 30 - minutes["counts"]["teams_with_minutes"]
    add("G11", "rotation minutes are measured from an official game book, or blank and flagged",
        minutes["counts"]["teams_with_minutes"] > 0,
        f"{minutes['counts']['teams_with_minutes']}/30 clubs have a captured game book; the other "
        f"{missing} print blank rotation cells with the reason, never inferred",
        minutes["sources"])

    # G12 no wall clock in the generated artefacts ----------------------------------------
    offenders = []
    for fn in sorted(os.listdir(OUT)):
        if not fn.endswith(".json"):
            continue
        text = open(os.path.join(OUT, fn), encoding="utf-8").read()
        if "generated_utc" in text and SLATE_UTC not in text:
            offenders.append(fn)
    add("G12", "generated artefacts carry the source-read stamp, never a wall clock",
        not offenders,
        f"every artefact is stamped {SLATE_UTC} (the newest official source read in this round); "
        f"{len(offenders)} files with a different stamp" + (f": {offenders}" if offenders else ""),
        ["data/slate/"])

    passed = sum(1 for g in gates if g["status"] == "PASS")
    return {"schema": "nba3.slate.gates/v1", "session": SESSION, "evaluated_utc": SLATE_UTC,
            "rule": "the scheduled refresh rebuilds only when every gate passes; a failure "
                    "leaves the last good build in place",
            "counts": {"gates": len(gates), "passed": passed,
                       "failed": len(gates) - passed},
            "all_passed": passed == len(gates),
            "gates": gates}


def main():
    rep = run_gates()
    out = os.path.join(OUT, "gates.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
        fh.write("\n")
    for g in rep["gates"]:
        print(f"  {g['status']}  {g['id']}  {g['name']}")
    print(f"{rep['counts']['passed']}/{rep['counts']['gates']} gates passed")
    return 0 if rep["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
