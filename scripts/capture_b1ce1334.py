#!/usr/bin/env python3
"""Session b1ce1334 — 2026-11-19 official capture: injury-report transcripts, consecutive-report diff,
per-game finals and rolling-slate checks.

Inputs (all committed, all transcribed from official pages; see data/rounds/2026-11-19/manifest.json):
  data/rounds/2026-11-19/raw/injury_2026-11-19_*_raw.md   verbatim text of each official injury PDF
  data/rounds/2026-11-19/results_2026-11-18.json           official final scores (nba.com schedule page)
  data/rounds/2026-11-19/slate_2026-11-19_22.json          official schedule (nba.com game-listing pages)

Outputs (deterministic, recomputed by --check):
  data/rounds/2026-11-19/injury_parsed.json   machine-read rows + the lines that could NOT be read
  data/rounds/2026-11-19/injury_delta.json    consecutive-revision diff (status changes, adds, removes)

Rule: a line that is not a clean 7-column player/team row is kept verbatim in `unparsed` and is never
given a value. Nothing is inferred (no team from memory, no status from a neighbouring row).

Usage:
  python3 scripts/capture_b1ce1334.py           # write outputs
  python3 scripts/capture_b1ce1334.py --check   # recompute in memory, compare, verify checksums (exit 1 on drift)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "rounds" / "2026-11-19"
RAW = DIR / "raw"
MANIFEST = DIR / "manifest.json"
PARSED = DIR / "injury_parsed.json"
DELTA = DIR / "injury_delta.json"
RESULTS = DIR / "results_2026-11-18.json"
SLATE = DIR / "slate_2026-11-19_22.json"

STATUSES = {"Out", "Questionable", "Doubtful", "Probable", "Available"}
NYS = "NOT YET SUBMITTED"
REVISIONS = ["1200AM", "1215AM", "1230AM"]  # consecutive official reports, ET


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_transcript(text):
    """Return player_rows, team_rows, unparsed (list of {line_no, text, reason})."""
    player_rows, team_rows, unparsed = [], [], []
    report_title = None
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^\*\*Injury Report: (.+?)\*\*$", s)
        if m:
            report_title = m.group(1)
            continue
        if re.match(r"^(\*\*\*|\* \* \*|---)$", s) or s.startswith("| ---") or s.startswith("| Game Date"):
            continue
        if not s.startswith("|"):
            unparsed.append({"line_no": no, "text": s, "reason": "not a table row"})
            continue
        cells = _cells(s)
        if len(cells) != 7:
            unparsed.append({"line_no": no, "text": s, "reason": f"{len(cells)} cells, expected 7 (layout-broken)"})
            continue
        date, time, matchup, team, player, status, reason = cells
        if player and status in STATUSES:
            player_rows.append({
                "report": report_title, "line_no": no,
                "game_date": date or None, "game_time": time or None,
                "matchup": matchup or None,
                "team": team or None,
                "team_attribution": "printed" if team else "UNATTRIBUTED (blank team cell)",
                "player": player, "status": status, "reason": reason,
            })
        elif reason == NYS and team:
            team_rows.append({
                "report": report_title, "line_no": no,
                "game_date": date or None, "game_time": time or None,
                "matchup": matchup or None, "team": team, "reason": NYS,
            })
        elif not player and not reason:
            unparsed.append({"line_no": no, "text": s, "reason": "blank team and player cells"})
        else:
            unparsed.append({"line_no": no, "text": s, "reason": "7 cells but status not in the known set or player blank"})
    return {"report_title": report_title, "player_rows": player_rows,
            "team_rows": team_rows, "unparsed": unparsed}


def _key_player(r):
    return (r["matchup"] or "UNATTRIBUTED", r["team"] or "UNATTRIBUTED", r["player"])


def _key_team(r):
    return (r["matchup"] or "UNATTRIBUTED", r["team"])


def diff_pair(prev, cur):
    """Status changes between two consecutive parsed revisions (only cleanly parsed rows are compared)."""
    pp = {_key_player(r): r for r in prev["player_rows"]}
    cp = {_key_player(r): r for r in cur["player_rows"]}
    changes, added, removed = [], [], []
    for k in sorted(set(pp) & set(cp)):
        a, b = pp[k], cp[k]
        if a["status"] != b["status"] or a["reason"] != b["reason"]:
            changes.append({"matchup": k[0], "team": k[1], "player": k[2],
                            "from": {"status": a["status"], "reason": a["reason"]},
                            "to": {"status": b["status"], "reason": b["reason"]}})
    for k in sorted(set(cp) - set(pp)):
        added.append({"matchup": k[0], "team": k[1], "player": k[2],
                      "status": cp[k]["status"], "reason": cp[k]["reason"]})
    for k in sorted(set(pp) - set(cp)):
        removed.append({"matchup": k[0], "team": k[1], "player": k[2],
                        "status": pp[k]["status"], "reason": pp[k]["reason"]})
    ptm = {_key_team(r): r for r in prev["team_rows"]}
    ctm = {_key_team(r): r for r in cur["team_rows"]}
    team_changes = []
    for k in sorted(set(ptm) ^ set(ctm)):
        team_changes.append({"matchup": k[0], "team": k[1],
                             "in": "later" if k in ctm else "earlier",
                             "reason": NYS})
    return {"status_changes": changes, "added_player_rows": added,
            "removed_player_rows": removed, "team_submission_changes": team_changes}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_outputs():
    parsed = {}
    for rev in REVISIONS:
        path = RAW / f"injury_2026-11-19_{rev}_raw.md"
        parsed[rev] = parse_transcript(path.read_text(encoding="utf-8"))
    out = {
        "schema": "b1ce1334.injury_parsed.v1",
        "note": "Machine-read from the verbatim transcripts. `unparsed` lines are NOT given values.",
        "revisions": {rev: {"report_title": p["report_title"],
                            "raw_sha256": sha256(RAW / f"injury_2026-11-19_{rev}_raw.md"),
                            "player_rows": p["player_rows"],
                            "team_rows": p["team_rows"],
                            "unparsed": p["unparsed"],
                            "counts": {"player_rows": len(p["player_rows"]),
                                       "team_rows": len(p["team_rows"]),
                                       "unparsed": len(p["unparsed"])}}
                      for rev, p in parsed.items()},
    }
    deltas = []
    for prev_rev, cur_rev in zip(REVISIONS, REVISIONS[1:]):
        d = diff_pair(parsed[prev_rev], parsed[cur_rev])
        # verbatim line diff as the independent second method (counts only)
        a = (RAW / f"injury_2026-11-19_{prev_rev}_raw.md").read_text(encoding="utf-8").splitlines()
        b = (RAW / f"injury_2026-11-19_{cur_rev}_raw.md").read_text(encoding="utf-8").splitlines()
        import difflib
        sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
        differing = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
        deltas.append({"from": prev_rev, "to": cur_rev, **d,
                       "verbatim_lines_differing": differing,
                       "verbatim_lines_total_from": len(a), "verbatim_lines_total_to": len(b)})
    out_delta = {
        "schema": "b1ce1334.injury_delta.v1",
        "note": ("Consecutive official revisions of the 11/19 report. Status changes are computed only on "
                 "cleanly parsed player rows; `verbatim_lines_differing` is an independent line-level count "
                 "that also covers rows the parser could not read."),
        "pairs": deltas,
    }
    return out, out_delta


def _fail(msg):
    print(f"CHECK FAILED: {msg}", file=sys.stderr)
    return False


def check_inputs():
    ok = True
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for rel, want in man["sha256"].items():
        p = ROOT / rel
        if not p.exists():
            ok &= _fail(f"missing file {rel}")
            continue
        if sha256(p) != want:
            ok &= _fail(f"sha256 drift in {rel}")
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    games = res["games"]
    if len(games) != 12:
        ok &= _fail(f"expected 12 finals for 2026-11-18, found {len(games)}")
    ids = [g["game_id"] for g in games]
    if len(set(ids)) != len(ids):
        ok &= _fail("duplicate game_id in results")
    for g in games:
        if not isinstance(g.get("away_score"), int) or not isinstance(g.get("home_score"), int):
            ok &= _fail(f"{g['game_id']}: score missing")
        if g.get("status") != "Final":
            ok &= _fail(f"{g['game_id']}: not Final")
        if g.get("quarter_scores") not in (None, "UNVERIFIED"):
            ok &= _fail(f"{g['game_id']}: quarter scores must be blank or UNVERIFIED")
    sl = json.loads(SLATE.read_text(encoding="utf-8"))
    sids = [g["game_id"] for d in sl["days"] for g in d["games"]]
    if len(set(sids)) != len(sids):
        ok &= _fail("duplicate game_id in slate")
    for d in sl["days"]:
        if d.get("printed_game_count") is not None and d["printed_game_count"] != len(d["games"]):
            ok &= _fail(f"{d['date']}: printed count {d['printed_game_count']} != listed {len(d['games'])}")
    return ok


def cross_check_pdf_vs_slate(parsed_1200):
    """PDF matchups (e.g. 'CHA@ATL') must appear in the nba.com slate with the same away@home pair."""
    sl = json.loads(SLATE.read_text(encoding="utf-8"))
    pairs = {f"{g['away']}@{g['home']}" for d in sl["days"] for g in d["games"]}
    pdf = {r["matchup"] for r in parsed_1200["player_rows"] + parsed_1200["team_rows"] if r["matchup"]}
    missing_from_slate = sorted(m for m in pdf if m not in pairs)
    return {"pdf_matchups": sorted(pdf), "not_in_slate": missing_from_slate}


def main(argv):
    out, out_delta = build_outputs()
    if "--check" in argv:
        ok = check_inputs()
        existing_p = json.loads(PARSED.read_text(encoding="utf-8"))
        existing_d = json.loads(DELTA.read_text(encoding="utf-8"))
        if existing_p != out:
            ok &= _fail("injury_parsed.json does not match the transcripts")
        if existing_d != out_delta:
            ok &= _fail("injury_delta.json does not match the transcripts")
        xc = cross_check_pdf_vs_slate(parse_transcript((RAW / "injury_2026-11-19_1200AM_raw.md").read_text(encoding="utf-8")))
        if xc["not_in_slate"]:
            ok &= _fail(f"PDF matchups not in slate: {xc['not_in_slate']}")
        print(f"b1ce1334 capture check: {'PASS' if ok else 'FAIL'}; "
              f"pdf matchups {len(xc['pdf_matchups'])}, all in nba.com slate: {not xc['not_in_slate']}")
        return 0 if ok else 1
    PARSED.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    DELTA.write_text(json.dumps(out_delta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {PARSED.relative_to(ROOT)} and {DELTA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
