#!/usr/bin/env python3
"""Session arena/3d625d23-nba3 — rolling-slate refresh driver with a rebuild gate.

The point of this script is the ORDER: refresh → prove freshness and provenance → rebuild.
If any gate fails the rebuild step is refused and the exit code is non-zero, so the site keeps
the last good build instead of publishing on top of a capture that did not verify.

Sources in the rolling set (each with its own freshness SLA, in hours):

  schedule          official schedule, per slate date       24h
  standings         official standings page                 24h   <- added by this round
  team_traditional  official team stats, traditional        24h   <- added by this round
  team_opponent     official team stats, opponent           24h   <- added by this round
  team_advanced     official team stats, advanced           24h
  injury_report     newest filed official injury PDF         6h
  results           official per-game final + quarter scores 6h
  game_books        official game book PDFs (minutes)       72h

Usage
  python3 scripts/refresh_round_3d625d23.py            # refresh report + gates, no rebuild
  python3 scripts/refresh_round_3d625d23.py --rebuild  # ...and rebuild only if all gates pass
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "slate")
SESSION = "arena/3d625d23-nba3"
# the newest official source read in this round; every artefact is stamped with it rather than
# with a wall clock, so rebuilding from committed inputs is reproducible
SLATE_UTC = "2026-11-16T00-05Z"

# url, cadence_hours, where the capture lives, what it feeds
SOURCES = [
    {"id": "schedule", "label": "Official schedule, per slate date",
     "url": "https://www.nba.com/schedule", "cadence_h": 24,
     "captures": ["raw/slate_2026-11-16_1118.md"], "feeds": "slate.json, travel.json"},
    {"id": "standings", "label": "Official standings",
     "url": "https://www.nba.com/standings", "cadence_h": 24,
     "captures": ["raw/standings_2026-11-15.md"], "feeds": "standings.json"},
    {"id": "team_traditional", "label": "Official team stats — traditional",
     "url": "https://www.nba.com/stats/teams/traditional", "cadence_h": 24,
     "captures": ["raw/team_traditional_2026-11-15.md"], "feeds": "team_traditional.json"},
    {"id": "team_opponent", "label": "Official team stats — opponent",
     "url": "https://www.nba.com/stats/teams/opponent", "cadence_h": 24,
     "captures": ["raw/team_opponent_2026-11-15.md"], "feeds": "team_opponent.json"},
    {"id": "team_advanced", "label": "Official team stats — advanced",
     "url": "https://www.nba.com/stats/teams/advanced", "cadence_h": 24,
     "captures": ["raw/team_advanced_2026-11-15.md"], "feeds": "team_advanced.json"},
    {"id": "injury_report", "label": "Newest filed official injury report (PDF)",
     "url": "https://official.nba.com/nba-injury-report-2025-26-season/", "cadence_h": 6,
     "captures": ["raw/injury_2026-11-15_0630PM.md"], "feeds": "injuries/*, rotation column"},
    {"id": "results", "label": "Official per-game final + quarter scores",
     "url": "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf", "cadence_h": 6,
     "captures": ["raw/gamebook_20261115_INDPHI.md", "raw/gamebook_20261115_LALPHX.md",
                  "raw/gamebook_20261115_CHALAC.md"],
     "feeds": "results_feed.json, settlement"},
    {"id": "game_books", "label": "Official game book PDFs (rotation minutes)",
     "url": "https://statsdmz.nba.com/pdfs/20261113/20261113_GSWSAS.pdf", "cadence_h": 72,
     "captures": ["raw/gamebook_20261113_GSWSAS.md", "raw/gamebook_20261113_UTAHOU.md",
                  "raw/gamebook_20261112_CHAPHX.md", "raw/gamebook_20261112_DETWAS.md",
                  "raw/gamebook_20261113_MILORL.md", "raw/gamebook_20261113_PORSAC.md"],
     "feeds": "minutes.json, player_game_logs.json"},
]


def run(cmd):
    """Run a step and return (rc, combined output). Never raises on a non-zero exit."""
    p = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def capture_state(src):
    files = []
    for rel in src["captures"]:
        path = os.path.join(OUT, rel)
        if not os.path.exists(path):
            files.append({"file": rel, "present": False})
            continue
        text = open(path, encoding="utf-8").read()
        stamp = None
        for line in text.splitlines():
            if "retrieved" in line.lower() and "20" in line:
                stamp = line.strip()[:200]
                break
        files.append({"file": rel, "present": True, "source_url_in_file": "https://" in text,
                      "stamp_line": stamp, "bytes": len(text)})
    return files


def iso_hours(a, b):
    fa = datetime.strptime(a, "%Y-%m-%dT%H-%MZ").replace(tzinfo=timezone.utc)
    fb = datetime.strptime(b, "%Y-%m-%dT%H-%MZ").replace(tzinfo=timezone.utc)
    return (fb - fa).total_seconds() / 3600.0


def main():
    rebuild = "--rebuild" in sys.argv
    now = os.environ.get("NBA3_NOW_UTC", SLATE_UTC)

    rows = []
    for s in SOURCES:
        files = capture_state(s)
        newest = None
        for f in files:
            sl = f.get("stamp_line") or ""
            # stamps in this tree look like  "retrieved 2026-11-16T00-05Z"
            for tok in sl.replace(",", " ").split():
                if tok.endswith("Z") and tok[:4].isdigit() and "-" in tok:
                    newest = tok if newest is None else max(newest, tok)
        if newest:
            age = iso_hours(newest, now)
            fresh = age <= s["cadence_h"]
        else:
            age, fresh = None, False
        rows.append({"id": s["id"], "label": s["label"], "url": s["url"],
                     "cadence_h": s["cadence_h"], "feeds": s["feeds"],
                     "newest_capture_utc": newest, "age_h": round(age, 2) if age is not None else None,
                     "fresh": fresh, "files": files})

    steps = []
    rc_cap, out_cap = run(["scripts/capture_round_3d625d23.py"])
    steps.append({"step": "capture replay", "command": "scripts/capture_round_3d625d23.py",
                  "rc": rc_cap, "output": out_cap})
    rc_gate, out_gate = run(["scripts/gates_round_3d625d23.py"])
    steps.append({"step": "gates", "command": "scripts/gates_round_3d625d23.py",
                  "rc": rc_gate, "output": out_gate})

    gates = {}
    gp = os.path.join(OUT, "gates.json")
    if os.path.exists(gp):
        gates = json.load(open(gp, encoding="utf-8"))

    rebuilt = []
    if rebuild:
        if rc_gate != 0:
            steps.append({"step": "rebuild REFUSED", "command": "-", "rc": 1,
                          "output": "freshness/provenance gates failed; the last good build is "
                                    "left in place"})
        else:
            for cmd in (["scripts/round_3d625d23.py"],
                        ["scripts/picks_round_3d625d23.py", "prereg"],
                        ["scripts/picks_round_3d625d23.py", "publish"],
                        ["scripts/picks_round_3d625d23.py", "settle"],
                        ["scripts/picks_round_3d625d23.py", "verify"],
                        ["scripts/build_slate_site.py"]):
                rc, out = run(cmd)
                steps.append({"step": cmd[0], "command": " ".join(cmd), "rc": rc, "output": out})
                rebuilt.append({"command": " ".join(cmd), "rc": rc})

    report = {"schema": "nba3.slate.refresh/v1", "session": SESSION, "evaluated_utc": now,
              "rule": "refresh -> prove freshness and provenance -> rebuild; a failed gate "
                      "refuses the rebuild and leaves the last good build published",
              "sources": rows,
              "counts": {"sources": len(rows), "fresh": sum(1 for r in rows if r["fresh"]),
                         "stale": sum(1 for r in rows if not r["fresh"])},
              "gates": gates.get("counts", {}),
              "gates_all_passed": bool(gates.get("all_passed")),
              "rebuild_requested": rebuild,
              "rebuild_steps": rebuilt,
              "steps": steps}
    with open(os.path.join(OUT, "refresh_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")

    for r in rows:
        state = "FRESH" if r["fresh"] else "STALE"
        age = f"{r['age_h']}h" if r["age_h"] is not None else "no stamp"
        print(f"  {state:5}  {r['id']:16} {age:>8} / {r['cadence_h']}h   {r['label']}")
    print(f"{report['counts']['fresh']}/{report['counts']['sources']} sources fresh, "
          f"{report['gates'].get('passed', 0)}/{report['gates'].get('gates', 0)} gates passed")
    for s in steps:
        if s["rc"] != 0:
            print(f"  FAILED {s['step']}: {s['output'][:300]}")
    return 0 if rc_gate == 0 and rc_cap == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
