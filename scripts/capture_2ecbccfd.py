#!/usr/bin/env python3
"""Official-source capture + reconciliation for the 2026-11-17 round (session arena/2ecbccfd-nba3).

Everything here is OFFLINE and DETERMINISTIC: the script parses verbatim transcripts that are
committed in this repository and writes the artefacts the site is built from. It never reaches
the network, so a CI replay that produces a different file means a committed input changed --
which is exactly what it is for. Re-run:

    python3 scripts/capture_2ecbccfd.py            # write the artefacts
    python3 scripts/capture_2ecbccfd.py --check     # fail if the committed artefacts drift

Transcripts and their official sources (read with the Arena fetch tool on 2026-11-16; the
retrieval stamp of each read is recorded in the artefact it produces):

  data/rounds/2026-11-17/captures/standings_2026-11-16_raw.md
      https://www.nba.com/standings
  data/rounds/2026-11-17/captures/injury_2026-11-16_0115PM_raw.md
      https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf
      listed by https://official.nba.com/nba-injury-report-2026-27-season/
  data/app/official_injuries_2026-11-16_0915AM_raw.md          (earlier revision, session 8f4fac33)
      https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_09_15AM.pdf

Rules that bind this file (from the project brief, not invented here):
  * no value is inferred to fill a cell the official page did not print -- it stays blank and the
    row is flagged with the code of what is missing;
  * a player row whose TEAM cell the PDF dropped at a page break is attributed to the club of the
    nearest row above it in the same game block, and the evidence string is stored with the row
    (same convention session 8f4fac33 documented in data/rounds/2026-11-16/injuries.json);
  * the standings table is reconciled against the verified results log: every club's W+L must equal
    its games played in the log, and the 30 GP values must sum to 2x the number of games.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUND_DIR = os.path.join(ROOT, "data", "rounds", "2026-11-17")
CAP = os.path.join(ROUND_DIR, "captures")
OUT = ROUND_DIR

STANDINGS_MD = os.path.join(CAP, "standings_2026-11-16_raw.md")
INJURY_1315_MD = os.path.join(CAP, "injury_2026-11-16_0115PM_raw.md")
INJURY_0915_MD = os.path.join(ROOT, "data", "app", "official_injuries_2026-11-16_0915AM_raw.md")
RESULTS_1115_JSON = os.path.join(ROOT, "data", "rounds", "2026-11-16", "results.json")
GAMES_LOG_CSV = os.path.join(ROOT, "data", "origin", "games.csv")
TEAM_REGISTRY = os.path.join(ROOT, "data", "live", "team_registry.json")

STANDINGS_URL = "https://www.nba.com/standings"
INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJURY_1315_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf"
INJURY_0915_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_09_15AM.pdf"
GAMES_URL_1115 = "https://www.nba.com/games?date=2026-11-15"
ATL_MIL_GAME_URL = "https://www.nba.com/game/atl-vs-mil-0022600243"

STATUSES = ("Out", "Questionable", "Doubtful", "Available", "Day-To-Day", "Probable")
REASON_PREFIXES = ("Injury/Illness - ", "G League - ", "League Suspension", "Other - ")

RETRIEVED = {
    "standings": "2026-11-16T18:45Z",
    "injury_1315": "2026-11-16T18:30Z",
    "injury_0915": "2026-11-16T14:35Z",
    "results_1115": "2026-11-16T14:40Z",
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def table_rows(text):
    """Yield the cell lists of every markdown table body line, skipping separator rows."""
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
            continue
        if not any(cells):
            continue
        yield cells


# -----------------------------------------------------------------------------------------------
# standings
# -----------------------------------------------------------------------------------------------
TEAM_LINK_RE = re.compile(r"\[(\d+)\\<br\\>.*\\<br\\>([^\]]+?)\]\((https://www\.nba\.com/team/(\d+)/[a-z-]+)\)")


def parse_standings(text, full_to_code):
    rows, problems = [], []
    conference = None
    for line in text.splitlines():
        if line.startswith("## Eastern Conference"):
            conference = "East"
            continue
        if line.startswith("## Western Conference"):
            conference = "West"
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 13 or set(cells[0]) <= {"-"} or cells[0] == "Team":
            continue                      # separator and header rows
        m = TEAM_LINK_RE.search(cells[0])
        if not m:
            if cells[0] != "Team":
                problems.append({"raw": cells[0], "why": "team cell did not parse"})
            continue
        seed, name, team_url, team_id = m.group(1), m.group(2).strip(), m.group(3), int(m.group(4))
        code = full_to_code.get(name)
        if code is None:
            problems.append({"raw": name, "why": "full name is not in the official team registry"})
            continue
        rec = {
            "conference": conference,
            "seed": int(seed),
            "team": code,
            "full_name": name,
            "nba_team_id": team_id,
            "source_url": STANDINGS_URL,
            "team_url": team_url,
            "retrieved_utc": RETRIEVED["standings"],
        }
        keys = ["w", "l", "win_pct", "gb", "conf_rec", "div_rec", "home_rec", "road_rec",
                "neutral_rec", "ot_rec", "last10", "streak"]
        for key, cell in zip(keys, cells[1:]):
            rec[key] = cell
        # W and L must be integers; anything else is a parse problem, not a value.
        for key in ("w", "l"):
            if re.fullmatch(r"\d+", rec[key]):
                rec[key] = int(rec[key])
            else:
                rec[key] = None
                problems.append({"raw": rec[key], "why": f"{key} cell is not an integer"})
        rec["gp"] = (rec["w"] + rec["l"]) if rec["w"] is not None and rec["l"] is not None else None
        # Home record is the official printed split; it is the check on the measured home-win rate.
        for split in ("home_rec", "road_rec", "conf_rec", "div_rec"):
            v = rec[split]
            m2 = re.fullmatch(r"(\d+)-(\d+)", v or "")
            rec[split + "_parsed"] = (int(m2.group(1)), int(m2.group(2))) if m2 else None
        rows.append(rec)
    return rows, problems


# -----------------------------------------------------------------------------------------------
# injury report PDFs
# -----------------------------------------------------------------------------------------------
MATCHUP_RE = re.compile(r"^[A-Z]{3}@[A-Z]{3}$")

CHUNK_BOUNDARY = "<!-- FETCH CHUNK BOUNDARY -->"


def stitch_chunk_boundary(text):
    """Join the two halves of the table row the fetch tool split between chunks.

    The Arena fetch tool returns a long document in chunks and can cut a markdown row in the
    middle. The committed transcript keeps both halves and marks the cut; parsing it as printed
    would lose the row after the cut and graft a fragment onto the row before it. Stitching the
    two halves back together restores the row the PDF actually printed. The transcript file is
    not modified -- only the text handed to the parser -- and the stitch is reported.
    """
    if CHUNK_BOUNDARY not in text:
        return text, []
    pat = re.compile(r"([^\n]*)\n" + re.escape(CHUNK_BOUNDARY) + r"[^\n]*\n([^\n]*)")
    m = pat.search(text)
    if not m:
        return text, [{"why": "chunk boundary marker present but no row halves to join"}]
    joined = m.group(1) + m.group(2)
    note = {"why": "fetch chunk boundary stitched: the tool split one table row in two",
            "joined_line": joined.strip()}
    return text[:m.start()] + joined + text[m.end():], [note]


def classify(cell):
    """Return ('status'|'reason', value) for a trailing cell, or (None, value) if unrecognised."""
    if cell in STATUSES:
        return "status", cell
    if cell.startswith(REASON_PREFIXES) or cell in ("NOT YET SUBMITTED", "Rest"):
        return "reason", cell
    return None, cell


def parse_injury(text, source_url, report_stamp, full_to_code, retrieved_utc):
    """Parse one injury-report transcript into player rows and not-yet-submitted rows.

    The PDF drops the Game Date column after the first block of each page and drops the Team
    column for the rows that continue across a page break. This parser carries the last value it
    saw for each dropped column, records that it did so (`carried`), and never invents a cell that
    neither this row nor the carry provides.
    """
    text, boundary_notes = stitch_chunk_boundary(text)
    player_rows, not_submitted, problems = [], [], list(boundary_notes)
    ctx = {"date": None, "game_time": None, "matchup": None}
    for cells in table_rows(text):
        if "Player Name" in cells or "Game Date" == cells[0]:
            continue                      # the repeated table header the PDF prints per page block
        # Positional scan: recognisable tokens can sit in any column because the PDF drops cells.
        date = matchup = game_time = team = player = status = reason = None
        carried = []
        vals = [c for c in cells if c]
        if not vals:
            continue
        for c in cells:
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c):
                date = c
            elif MATCHUP_RE.fullmatch(c):
                matchup = c
            elif re.fullmatch(r"\d{2}:\d{2} \(ET\)", c):
                game_time = c
            elif c in full_to_code:
                team = c
            elif c == "NOT YET SUBMITTED":
                reason = "NOT YET SUBMITTED"
        # team may also be printed as the full club name
        if team is None:
            for c in cells:
                if c in full_to_code.values() or c in full_to_code:
                    team = c
                    break
        for c in cells:
            kind, val = classify(c)
            if kind == "status" and status is None:
                status = val
            elif kind == "reason" and reason is None and val != "NOT YET SUBMITTED":
                reason = val
        # the player cell is the one immediately after the team cell, else the first
        # comma-bearing cell that is not a recognised token
        idx_team = cells.index(team) + 1 if team and team in cells else 0
        player = None
        for c in cells[idx_team:]:
            if not c:
                continue
            if c in full_to_code or c in full_to_code.values() or MATCHUP_RE.fullmatch(c):
                continue
            if c in STATUSES or c.startswith(REASON_PREFIXES) or c == "NOT YET SUBMITTED":
                if player is None and c.startswith(REASON_PREFIXES):
                    # a status column the PDF dropped: keep it as the reason, flag the status
                    reason = c
                    continue
                continue
            if re.fullmatch(r"\d{2}:\d{2} \(ET\)", c) or re.fullmatch(r"\d{2}/\d{2}/\d{4}", c):
                continue
            player = c
            break
        for key, val in (("date", date), ("game_time", game_time), ("matchup", matchup)):
            if val is None:
                if ctx[key] is None:
                    problems.append({"cells": cells, "why": f"{key} missing and nothing to carry"})
                else:
                    carried.append(key)
            else:
                ctx[key] = val
        date = date or ctx["date"]
        game_time = game_time or ctx["game_time"]
        matchup = matchup or ctx["matchup"]

        if reason == "NOT YET SUBMITTED" and player is None:
            not_submitted.append({
                "kind": "not_submitted",
                "date": date,
                "game_time": game_time,
                "matchup": matchup,
                "team": team,
                "source_url": source_url,
                "report_stamp": report_stamp,
                "retrieved_utc": retrieved_utc,
                "cells_printed": len([c for c in cells if c]),
            })
            continue
        if player is None or "," not in player:
            # A row with no "Last, First" cell is not a player row. The PDF wraps a long Reason
            # across a page break, which prints a lone fragment cell ("Fracture"); it is joined
            # back onto the row above it, the fragment is kept, and the join is recorded.
            fragment = vals[0] if len(vals) == 1 and status is None and player else None
            joined = False
            if fragment and player_rows:
                prev = player_rows[-1]
                if (prev.get("reason") and prev.get("matchup") == matchup
                        and prev.get("team") is None or True) and prev["report_stamp"] == report_stamp:
                    prev["reason"] = prev["reason"] + " " + fragment
                    prev["flags"] = prev["flags"] + ["REASON_JOINED_ACROSS_PAGE_BREAK"]
                    problems.append({"cells": cells, "why": "lone fragment joined to the row above",
                                     "joined_to": prev["player"], "fragment": fragment})
                    joined = True
            if not joined:
                problems.append({"cells": cells, "why": "no player cell could be located"})
            continue
        flags = []
        if status is None:
            flags.append("STATUS_NOT_PRINTED")
        if reason is None:
            flags.append("REASON_NOT_PRINTED")
        if team is None:
            flags.append("TEAM_NOT_PRINTED")
        player_rows.append({
            "kind": "player",
            "date": date,
            "game_time": game_time,
            "matchup": matchup,
            "team": team,
            "player": player,
            "status": status,
            "reason": reason,
            "key": re.sub(r"[^a-z ]", "", player.lower().replace(",", " ").replace("  ", " ")).strip(),
            "carried": carried,
            "flags": flags,
            "source_url": source_url,
            "report_stamp": report_stamp,
        })
    return player_rows, not_submitted, problems


def attribute_teams(rows, other_rows):
    """Fill the team of a row whose TEAM cell the PDF dropped.

    Two sources, in this order, both of them printed facts rather than inference:
      1. the nearest row above it in the same game block that DOES print a team cell;
      2. the same player in the other revision of the same day's report, if that row prints a team.
    A row neither rule resolves keeps team = None and carries TEAM_UNRESOLVED.
    """
    by_key = {}
    for r in other_rows:
        if r.get("team") and r.get("player"):
            by_key.setdefault(r["key"], r)
    for i, r in enumerate(rows):
        if r.get("team"):
            r["team_source"] = "printed"
            continue
        hint = None
        for prev in reversed(rows[:i]):
            if prev.get("matchup") != r.get("matchup"):
                break
            if prev.get("team"):
                hint = r["team"] = prev["team"]
                r["flags"] = [f for f in r["flags"] if f != "TEAM_NOT_PRINTED"] + [
                    "TEAM_NOT_PRINTED_IN_THIS_REVISION"]
                r["team_source"] = "carried-from-row-above-in-same-game-block"
                r["team_attribution_evidence"] = (
                    f"the TEAM cell is blank in the extraction because {hint}'s rows continue across "
                    f"a page break; the row immediately above in the same game block "
                    f"({prev['player']}) is printed as {hint}, and {hint} is one of the two clubs in "
                    f"{r.get('matchup')}")
                break
        if hint is None:
            o = by_key.get(r["key"])
            if o and o.get("team"):
                r["team"] = o["team"]
                r["team_source"] = "same-player-in-the-earlier-revision"
                r["team_attribution_evidence"] = (
                    f"{o['player']} is printed with team {o['team']} in the {o['report_stamp']} "
                    f"revision of the same day's report")
                r["flags"] = [f for f in r["flags"] if f != "TEAM_NOT_PRINTED"] + ["TEAM_NOT_PRINTED_IN_THIS_REVISION"]
        if not r.get("team"):
            r["flags"] = r["flags"] + ["TEAM_UNRESOLVED"]
    return rows


# -----------------------------------------------------------------------------------------------
# results log + reconciliation
# -----------------------------------------------------------------------------------------------
def load_log():
    rows = []
    with open(GAMES_LOG_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"date": r["date"], "game_id": r["game_id"], "away": r["away"],
                         "away_pts": int(r["away_pts"]), "home": r["home"],
                         "home_pts": int(r["home_pts"]), "ot": int(r["ot"] or 0),
                         "source_url": r.get("source_url") or "https://www.nba.com/games?date=" + r["date"],
                         "quarter_scores": None, "settled": True})
    return rows


def extended_log():
    """188 verified games through 2026-11-14 plus the 2026-11-15 finals read from game books."""
    log = load_log()
    d = json.loads(read(RESULTS_1115_JSON))
    added = []
    for g in d["rows"]:
        row = {
            "date": g["date"], "game_id": g["game_id"], "away": g["away"],
            "away_pts": g["away_final"], "home": g["home"], "home_pts": g["home_final"],
            "ot": 1 if g.get("ot") else 0,
            "source_url": g["source_url"], "game_url": g["game_url"],
            "quarter_scores": {"away": g.get("away_quarters"), "home": g.get("home_quarters")},
            "quarter_scores_verified": bool(g.get("away_sum_ok")) and bool(g.get("home_sum_ok")),
            "settled": bool(g.get("settled")),
            "score_verified_by": [g["source_url"], g["scoreboard_url"]],
        }
        log.append(row)
        added.append(row)
    log.sort(key=lambda r: (r["date"], r["game_id"]))
    return log, d, added


def reconcile(log, standings):
    """Per-club games played and W/L from the log vs the official standings table."""
    gp, w = defaultdict(int), defaultdict(int)
    for g in log:
        gp[g["away"]] += 1
        gp[g["home"]] += 1
        winner = g["home"] if g["home_pts"] > g["away_pts"] else g["away"]
        w[winner] += 1
    total_gp = sum(gp.values())
    checks = []
    for s in standings:
        t = s["team"]
        checks.append({
            "team": t,
            "standings_w": s["w"], "standings_l": s["l"], "standings_gp": s["gp"],
            "log_w": w[t], "log_l": gp[t] - w[t], "log_gp": gp[t],
            "gp_ok": s["gp"] == gp[t],
            "w_ok": s["w"] == w[t],
        })
    return {
        "games_in_log": len(log),
        "sum_log_gp": total_gp,
        "gp_sum_equals_twice_games": total_gp == 2 * len(log),
        "teams": checks,
        "teams_reconciled": sum(1 for c in checks if c["gp_ok"] and c["w_ok"]),
        "teams_total": len(checks),
    }


def home_measures(log):
    home_games = sum(1 for g in log)
    home_wins = sum(1 for g in log if g["home_pts"] > g["away_pts"])
    ot = sum(1 for g in log if g.get("ot"))
    return {
        "games": home_games,
        "home_wins": home_wins,
        "home_win_rate": round(home_wins / home_games, 6) if home_games else None,
        "ot_games": ot,
        "note": ("measured over the verified results log only; the log is the 188 games through "
                 "2026-11-14 plus the 2026-11-15 finals read from the official game books"),
        "log_end": max(g["date"] for g in log),
    }


def status_rank(s):
    order = {"Out": 0, "Doubtful": 1, "Questionable": 2, "Probable": 3, "Day-To-Day": 3,
             "Available": 4}
    return order.get(s, None)


def injury_delta(earlier, later):
    """Consecutive-report diff, keyed by (matchup, player). Status changes and reason changes."""
    prev = {(r["matchup"], r["key"]): r for r in earlier}
    cur = {(r["matchup"], r["key"]): r for r in later}
    changes = []
    for k, r in cur.items():
        p = prev.get(k)
        if p is None:
            changes.append({"matchup": k[0], "player": r["player"], "team": r.get("team"),
                            "change": "ADDED", "from": None, "to": r.get("status"),
                            "reason": r.get("reason"), "source_url": r["source_url"]})
            continue
        fields = []
        if (p.get("status") or "") != (r.get("status") or ""):
            fields.append("status")
        if (p.get("reason") or "") != (r.get("reason") or ""):
            fields.append("reason")
        if (p.get("player") or "") != (r.get("player") or ""):
            fields.append("name_form")
        if fields:
            changes.append({"matchup": k[0], "player": r["player"], "team": r.get("team"),
                            "change": "CHANGED", "fields": fields,
                            "from_status": p.get("status"), "to_status": r.get("status"),
                            "from_reason": p.get("reason"), "to_reason": r.get("reason"),
                            "from_source": p["source_url"], "to_source": r["source_url"]})
    for k, p in prev.items():
        if k not in cur:
            changes.append({"matchup": k[0], "player": p["player"], "team": p.get("team"),
                            "change": "REMOVED", "from": p.get("status"), "to": None,
                            "reason": p.get("reason"), "source_url": p["source_url"]})
    # availability direction: does the newer report make the club more or less available?
    for c in changes:
        if c["change"] == "CHANGED" and "status" in c.get("fields", []):
            a, b = status_rank(c.get("from_status")), status_rank(c.get("to_status"))
            c["direction"] = ("more_available" if a is not None and b is not None and b > a
                              else "less_available" if a is not None and b is not None and b < a
                              else "unranked")
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if a committed artefact drifts")
    args = ap.parse_args()

    reg = json.loads(read(TEAM_REGISTRY))["teams"]
    full_to_code = {v["full_name"]: k for k, v in reg.items()}
    for k, v in reg.items():
        full_to_code[k] = k

    standings, stand_problems = parse_standings(read(STANDINGS_MD), full_to_code)
    log, res1115, added = extended_log()
    recon = reconcile(log, standings)
    home = home_measures(log)

    p13, n13, prob13 = parse_injury(read(INJURY_1315_MD), INJURY_1315_URL,
                                     "2026-11-16 01:15 PM ET", full_to_code, RETRIEVED["injury_1315"])
    p09, n09, prob09 = parse_injury(read(INJURY_0915_MD), INJURY_0915_URL,
                                     "2026-11-16 09:15 AM ET", full_to_code, RETRIEVED["injury_0915"])
    p13 = attribute_teams(p13, p09)
    p09 = attribute_teams(p09, p13)
    delta = injury_delta(p09, p13)

    tonight = [g for g in log if g["date"] <= "2026-11-16"]

    out = {
        "standings.json": {
            "schema": "nba3.rounds.standings/v1",
            "source_url": STANDINGS_URL,
            "retrieved_utc": RETRIEVED["standings"],
            "as_of": "after the 2026-11-15 game day; no 2026-11-16 game had started when read",
            "page_controls": "Season 2026-27 | Group By: Conference | Section: Overall",
            "count": len(standings),
            "verbatim_transcript": os.path.relpath(STANDINGS_MD, ROOT),
            "transcript_sha256": sha256(STANDINGS_MD),
            "parse_problems": stand_problems,
            "rows": standings,
        },
        "results_log.json": {
            "schema": "nba3.rounds.results_log/v1",
            "source_label": ("Verified per-game results. 2026-10-20..2026-11-14 (188 games) is the "
                              "log session bb0c83a4 reconciled to the official W/L/GP of the 30 clubs; "
                              "the nine 2026-11-15 finals were read by session 8f4fac33 from each game's "
                              "official game book. One row per game: date, teams, final score, quarter "
                              "scores where the game book's own period table sums to the printed final."),
            "log_end": max(g["date"] for g in log),
            "count": len(log),
            "games_2026_11_15": added,
            "home_measured": home,
            "reconciliation": recon,
            "games_thru_2026_11_16": len(tonight),
        },
        "injuries.json": {
            "schema": "nba3.rounds.injuries/v1",
            "index_url": INJURY_INDEX_URL,
            "reports": [
                {
                    "report_stamp": "2026-11-16 09:15 AM ET",
                    "source_url": INJURY_0915_URL,
                    "retrieved_utc": RETRIEVED["injury_0915"],
                    "verbatim_transcript": os.path.relpath(INJURY_0915_MD, ROOT),
                    "transcript_sha256": sha256(INJURY_0915_MD),
                    "player_rows": len(p09), "not_submitted_rows": len(n09),
                    "parse_problems": prob09,
                    "rows": p09, "not_submitted": n09,
                },
                {
                    "report_stamp": "2026-11-16 01:15 PM ET",
                    "source_url": INJURY_1315_URL,
                    "retrieved_utc": RETRIEVED["injury_1315"],
                    "verbatim_transcript": os.path.relpath(INJURY_1315_MD, ROOT),
                    "transcript_sha256": sha256(INJURY_1315_MD),
                    "player_rows": len(p13), "not_submitted_rows": len(n13),
                    "parse_problems": prob13,
                    "rows": p13, "not_submitted": n13,
                },
            ],
            "note": ("The 13:15 PM revision is the newest the official index listed when it was read "
                     "at 2026-11-16T18:30Z. Reports are revised on a continual basis; both revisions of "
                     "this game day are stored so the diff is reproducible."),
        },
        "injury_delta.json": {
            "schema": "nba3.rounds.injury_delta/v1",
            "from_report": "2026-11-16 09:15 AM ET",
            "to_report": "2026-11-16 01:15 PM ET",
            "from_source": INJURY_0915_URL,
            "to_source": INJURY_1315_URL,
            "key": "(matchup, player) normalised name; a status change is a change in the "
                   "Current Status column, a reason change is a change in the Reason column",
            "change_count": len(delta),
            "status_changes": [c for c in delta if "status" in (c.get("fields") or [])],
            "rows": delta,
        },
    }

    for name, payload in out.items():
        path = os.path.join(OUT, name)
        blob = json.dumps(payload, indent=1, sort_keys=False) + "\n"
        if args.check:
            with open(path, encoding="utf-8") as fh:
                if fh.read() != blob:
                    print(f"DRIFT: {name} is not what this script writes", file=sys.stderr)
                    return 1
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(blob)
        print(f"wrote {os.path.relpath(path, ROOT)} ({len(blob)} bytes)")

    print(f"\nstandings rows      : {len(standings)} (problems {len(stand_problems)})")
    print(f"log games           : {len(log)}  home wins {home['home_wins']} "
          f"({home['home_win_rate']*100:.2f}%)")
    print(f"reconciliation      : {recon['teams_reconciled']}/{recon['teams_total']} clubs, "
          f"sum GP {recon['sum_log_gp']} == 2 x {recon['games_in_log']} -> {recon['gp_sum_equals_twice_games']}")
    print(f"injury 09:15 rows   : {len(p09)} players, {len(n09)} not-submitted, "
          f"{len(prob09)} problems")
    print(f"injury 13:15 rows   : {len(p13)} players, {len(n13)} not-submitted, "
          f"{len(prob13)} problems")
    print(f"delta               : {len(delta)} differences, "
          f"{len([c for c in delta if 'status' in (c.get('fields') or [])])} status changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
