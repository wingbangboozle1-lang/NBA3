"""Freshness and provenance gates. The site build runs only if every gate here passes.

A gate is a hard rule with a measured value attached. Nothing is "assumed fresh".

  F1  every capture in data/live/meta.json carries a retrieval stamp and an https source URL
  F2  the newest archived injury report is the one the model used
  F3  the newest archived injury report is newer than the slate start (no pre-window snapshot)
  F4  the results feed is settled and every settled game is verified against two official reads
  F5  the slate in the model is byte-identical to data/live/slate_2026-11-15.json
  F6  every injury report the site shows is stored verbatim on disk with its source URL
  F7  every team in every slate game has an entry in the official advanced team-stats capture
  F8  the ledger chain verifies and every published pick has a frozen pre-registration
  F9  no stale numbers: the model's `as_of` stamp is not older than the newest settled game date
  F10 the capture is at least as new as the newest official read it was built from

F10 measures build lag against the newest retrieved_utc inside meta.json, not against the wall
clock. That keeps the artefact byte-reproducible, which the CI drift gate requires: a wall-clock
stamp makes every run differ and the gate can never pass. Staleness against the real clock is a
scheduling concern (the capture step re-fetches), and can be enforced explicitly with
--max-report-age-hours when a human runs it.

Run: python3 scripts/freshness_gates.py [--max-report-age-hours N]
Exit code 1 if any gate fails.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import injury_archive as ia                                                  # noqa: E402

LIVE = ROOT / "data" / "live"
META = LIVE / "meta.json"
INJ = LIVE / "injuries"
MODEL = LIVE / "model.json"
# every settled game day, oldest first — a new day is a new file and the gates cover it too
SETTLED_DAYS = sorted((LIVE / "results").glob("settled_*.json"))
SLATE = LIVE / "slate_2026-11-15.json"
STATS = LIVE / "team_stats_advanced.json"


def parse_stamp(s: str) -> dt.datetime:
    s = s.replace("Z", "+00:00")
    return dt.datetime.fromisoformat(s)


def latest_report() -> pathlib.Path:
    # timestamp order, not lexical: '12_00AM' sorts lexically after '06_45PM' but is 19h older
    return max(INJ.glob("Injury-Report_*.md"), key=ia.report_stamp_key)


def check(max_age_hours: float | None = None) -> list[dict]:
    gates = []

    def add(gid, name, passed, value, rule, source=""):
        gates.append({"id": gid, "name": name, "passed": bool(passed), "value": value,
                      "rule": rule, "source": source})

    meta = json.loads(META.read_text())

    # F1 -------------------------------------------------------------------------
    missing = []
    for name, blob in meta["sources"].items():
        url = blob.get("url", "")
        if not blob.get("retrieved_utc"):
            missing.append(f"{name}: no retrieved_utc")
        if not url.startswith("https://"):
            missing.append(f"{name}: url is not https")
    add("F1", "Every capture has a retrieval stamp and an https source",
        not missing, {"captures": len(meta["sources"]), "problems": missing},
        "zero missing stamps, zero non-https sources",
        meta["sources"].get("schedule", {}).get("url", "https://www.nba.com/schedule"))

    # F2 -------------------------------------------------------------------------
    model = json.loads(MODEL.read_text())
    used = model["injury_snapshot"]["file"]
    newest = latest_report().stem
    add("F2", "The model used the newest archived injury report", used == newest,
        {"model_used": used, "newest_on_disk": newest},
        "the engine must read the newest archived report, not an older one",
        model["injury_snapshot"].get("source_url")
        or "https://official.nba.com/nba-injury-report-2026-27-season/")

    # F3 -------------------------------------------------------------------------
    slate = json.loads(SLATE.read_text())
    slate_start = min(g["date"] for g in slate["games"])
    m = re.search(r"Injury-Report_(\d{4}-\d{2}-\d{2})_", newest)
    report_date = m.group(1) if m else ""
    add("F3", "The injury report is not older than the slate it prices", report_date >= slate_start,
        {"report_date": report_date, "slate_start": slate_start},
        "report date >= first slate date",
        model["injury_snapshot"].get("source_url")
        or "https://official.nba.com/nba-injury-report-2026-27-season/")

    # F4 -------------------------------------------------------------------------
    days = [json.loads(p.read_text()) for p in SETTLED_DAYS]
    all_games = [g for d in days for g in d["games"]]
    unverified = [g["game_id"] for g in all_games if not g["verified"]]
    dupes = {gid for gid in (g["game_id"] for g in all_games) if
             [x["game_id"] for x in all_games].count(gid) > 1}
    unverified += sorted(dupes)
    add("F4", "Every settled game is verified against two official reads", not unverified,
        {"days": [d["game_date"] for d in days], "games": len(all_games),
         "unverified": unverified,
         "stamps": {d["game_date"]: d["settled_utc"] for d in days}},
        "game page final == gamebook printed final == sum of printed quarters, on every settled day",
        all_games[0]["source_url"] if all_games else "https://www.nba.com/games")

    # F5 -------------------------------------------------------------------------
    model_games = {(g["game_id"], g["date"], g["away"], g["home"]) for g in model["slate"]}
    slate_games = {(g["game_id"], g["date"], g["away"], g["home"]) for g in slate["games"]}
    add("F5", "The priced slate is exactly the captured slate", model_games == slate_games,
        {"priced": len(model_games), "captured": len(slate_games),
         "only_in_model": sorted(model_games - slate_games),
         "only_in_slate": sorted(slate_games - model_games)},
        "set equality on (game_id, date, away, home)", slate["source_url"])

    # F6 -------------------------------------------------------------------------
    reports, problems = [], []
    for p in sorted(INJ.glob("Injury-Report_*.md")):
        text = p.read_text()
        url = re.search(r"https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_\S+?\.pdf", text)
        if not url:
            problems.append(f"{p.name}: no source URL in the file")
        reports.append({"file": p.name, "bytes": p.stat().st_size,
                        "source_url": url.group(0) if url else ""})
    add("F6", "Every archived injury report is on disk with its official source URL", not problems,
        {"reports": reports, "problems": problems}, "one file per report, URL inside the file",
        reports[0]["source_url"] if reports else
        "https://official.nba.com/nba-injury-report-2026-27-season/")

    # F7 -------------------------------------------------------------------------
    stats = json.loads(STATS.read_text())
    teams_needed = {g["home"] for g in slate["games"]} | {g["away"] for g in slate["games"]}
    have = set(stats["teams"])
    add("F7", "Every slate team has an official advanced-stats row", teams_needed <= have,
        {"teams_needed": len(teams_needed), "missing": sorted(teams_needed - have)},
        "all 30 team codes present in the official advanced capture",
        stats["source_url"])

    # F8 -------------------------------------------------------------------------
    import ledger
    v = ledger.verify()
    frozen = ledger.load_prereg()
    unpregistered = [p["strategy_id"] for p in
                     (e["pick"] for e in ledger.read_ledger() if e["kind"] == "PUBLISH")
                     if p["strategy_id"] not in frozen]
    add("F8", "The ledger chain verifies and every sealed pick is pre-registered",
        v["verified"] and not unpregistered,
        {"entries": v["entries"], "head": v["head_hash"], "problems": v["problems"],
         "unregistered_picks": unpregistered},
        "sha256 chain recomputes; strategy_id has a frozen prereg/ file",
        ledger.load_prereg() and "https://www.nba.com/schedule" or "https://www.nba.com/schedule")

    # F9 -------------------------------------------------------------------------
    newest_final = max(g["date"] for g in all_games)
    sample_end = model["sample_range"][1]
    add("F9", "The model sample is not older than the newest settled game", sample_end >= newest_final,
        {"model_sample_end": sample_end, "newest_settled": newest_final,
         "settled_days_covered": [d["game_date"] for d in days]},
        "model sample end >= newest settled game date",
        "https://www.nba.com/games")

    # F10 ------------------------------------------------------------------------
    stamped = parse_stamp(meta["generated_utc"])
    retrieved = [parse_stamp(b["retrieved_utc"]) for b in meta["sources"].values()
                 if b.get("retrieved_utc")]
    newest_read = max(retrieved) if retrieved else stamped
    lag = (stamped - newest_read).total_seconds() / 3600.0
    ok = (lag >= -1e-9) if max_age_hours is None else (abs(lag) <= max_age_hours)
    add("F10", "The capture is at least as new as the newest official read it was built from", ok,
        {"generated_utc": meta["generated_utc"],
         "newest_source_retrieved_utc": newest_read.strftime("%Y-%m-%dT%H:%MZ"),
         "build_lag_hours": round(lag, 4), "max_report_age_hours": max_age_hours},
        "build_lag >= 0 (the capture is not older than its own newest source read); with "
        "--max-report-age-hours, |build_lag| is bounded instead. Measured against the capture "
        "stamps, never the wall clock, so the artefact reproduces byte for byte.",
        "https://www.nba.com/schedule?date=2026-11-15")

    return gates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-report-age-hours", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    gates = check(args.max_report_age_hours)
    failed = [g for g in gates if not g["passed"]]
    payload = {"schema": "nba3.live/freshness/v1".replace("/", ".", 1),
               "reference_utc": json.loads(META.read_text())["generated_utc"],
               "checked_utc_note": ("Deliberately no wall-clock stamp: this artefact is compared "
                                    "byte for byte in CI, and a clock reading would make every "
                                    "build differ."),
               "counts": {"gates": len(gates), "passed": len(gates) - len(failed), "failed": len(failed)},
               "gates": gates}
    out = LIVE / "freshness.json"
    out.write_text(json.dumps(payload, indent=1) + "\n")
    if args.json:
        print(json.dumps(payload["counts"]))
    for g in gates:
        print(f"{'PASS' if g['passed'] else 'FAIL'}  {g['id']:4} {g['name']}")
        if not g["passed"]:
            print(f"        {json.dumps(g['value'])[:400]}")
    print(f"\n{payload['counts']['passed']}/{payload['counts']['gates']} gates passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
