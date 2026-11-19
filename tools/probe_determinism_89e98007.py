#!/usr/bin/env python3
"""Determinism probe (session 89e98007, 2026-11-19): print, to stdout, the evidence that settles
why the CI-replayed round artefacts stopped matching their committed bytes.

Run it on any interpreter, including the one that disagrees:

    python3 tools/probe_determinism_89e98007.py

It prints (1) the sha256 of every input the artefacts are derived from — so a data movement is
visible as a different hash rather than being inferred from a changed number; (2) the two candidate
summations of the twelve Washington rotation minutes, and the share each one yields; (3) the rc of
every `--check` gate the refresh workflow replays.

Finding, for the record (verified against CI annotations of runs 44467720829 / 44467529208 /
44469939831 and against the committed artefact):

    committed .top8_minutes_shares["2026-11-15:WAS"].top8[4].share = 0.1088
    runner (Python 3.14.4) regenerated                                = 0.1087

The 12 doubles sum to 239.99999999999997 added left-to-right and to exactly 240.0 with
compensation; 26.1/239.99999999999997 = 0.1087500000000000133… (above the 0.10875 midpoint) while
26.1/240.0 = 0.1087499999999999994… (below it). CPython >= 3.12 sums floats with Neumaier
compensation (https://docs.python.org/3/whatsnew/3.12.html, gh-100425), the artefacts were built
with the pre-3.12 fold, and a byte-for-byte gate cannot survive that. Fix: scripts/determinism.py.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from decimal import Decimal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RD = os.path.join(ROOT, "data", "rounds", "2026-11-17")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

GATES = ["scripts/capture_2ecbccfd.py", "scripts/gamebooks_2ecbccfd.py",
         "scripts/slate_extra_2ecbccfd.py", "scripts/model_2ecbccfd.py",
         "scripts/ledger_2ecbccfd.py", "round_2ecbccfd/build.py"]


def line(k, v=""):
    print(f"{k}={v}" if v != "" else k)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def main():
    line("PY", sys.version.replace("\n", " "))
    line("EXEC", sys.executable)
    line("UTC", __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
         .strftime("%Y-%m-%dT%H:%M:%SZ"))
    print("--- inputs the artefacts derive from (a source movement shows here, not as a rounding story) ---")
    line("SHA data/live/team_registry.json", sha(os.path.join(ROOT, "data", "live", "team_registry.json")))
    for p in sorted(glob.glob(os.path.join(RD, "captures", "gamebook_2026-11-15_*.md"))):
        line("SHA " + os.path.relpath(p, ROOT), sha(p))
    logs = os.path.join(RD, "player_logs_2026-11-15.json")
    line("SHA " + os.path.relpath(logs, ROOT), sha(logs))

    print("--- the field that moved, recomputed from the transcripts on THIS interpreter ---")
    import determinism as det
    with open(logs, encoding="utf-8") as fh:
        doc = json.load(fh)
    blk = doc["clubs"]["WASHINGTON WIZARDS"]
    mins = [r["min"] or 0 for r in blk["rows"] if r["status"] == "played"]
    ent = [v for k, v in doc["top8_minutes_shares"].items() if "WAS" in k][0]
    published = ent["top8"][4]["share"]
    line("FIELD_player", ent["top8"][4]["player"])
    line("COMMITTED_share", repr(published))
    who = ent["top8"][4]["player"]
    x = next(r["min"] or 0 for r in blk["rows"] if r["player"] == who)
    line("FIELD_minutes", f"{who} = {Decimal(x)}")
    for label, tot in (("fold (CPython <= 3.11 sum)", det.fold(mins)),
                       ("fsum (CPython >= 3.12 sum)", math.fsum(mins))):
        line("SUM " + label, f"{Decimal(tot)} -> share {det.dq(x / tot, 4)!r}")
    # Derived, not asserted. The first version of this line stated which rule the artefact was
    # built with; after main@78f513d republished the field it became a confidently wrong
    # sentence ("would repaint it 0.1087 -> 0.1087"), which is exactly how a stale diagnostic
    # misleads the next session. So the verdict names the rule the COMMITTED bytes match and says
    # whether the generator's pinned rule agrees with it.
    shares = {"fold (pre-3.12)": det.dq(x / det.fold(mins), 4),
              "exact sum (fsum)": det.dq(x / math.fsum(mins), 4)}
    agree = [k for k, v in shares.items() if v == published]
    line("VERDICT", f"committed share {published!r} is the {', '.join(agree) or 'NEITHER'} rule's "
                    f"answer; both rules on offer: " + ", ".join(f"{k}={v!r}" for k, v in shares.items())
                    + "; det.sum_ (the repository's ratified rule) pins the arithmetic so any "
                      "interpreter reproduces the bytes")

    print("--- every committed-tree gate the refresh replays ---")
    rc_all = 0
    for g in GATES:
        r = subprocess.run([sys.executable, os.path.join(ROOT, g), "--check"],
                           capture_output=True, text=True, cwd=ROOT)
        rc_all |= r.returncode
        detail = (r.stdout + r.stderr).strip().replace("\n", " | ")[:160]
        line(f"CHECK {g}", f"rc={r.returncode} {detail}")
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT)
    n = len([x for x in dirty.stdout.splitlines() if x.strip()])
    line("GIT_DIRTY_files_after_replay", n)
    line("PROBE RESULT", "PASS" if rc_all == 0 else "FAIL")
    return 0 if rc_all == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
