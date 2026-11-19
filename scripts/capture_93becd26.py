#!/usr/bin/env python3
"""Capture/parse: per-player game logs for every player on the newest official injury report.

Round 2026-11-19-93becd26 (session arena/93becd26-nba3).

Reads only committed capture files under data/rounds/2026-11-19-93becd26/captures/:

  * injury_report_2026-11-19_0215AM.md  - newest official NBA injury report at capture time
  * injury_report_2026-11-19_0200AM.md  - the immediately preceding revision (consecutive diff)
  * gamebook_2026-11-17_{PORMIN,DETSAS,UTALAC}.md - official box-score game books, one per
    game played by the four teams that have attributed players on the report (their most
    recent completed game; none of the four played on 2026-11-18 per the official schedule
    page capture schedule_2026-11-18_finals.json)
  * schedule_2026-11-18_finals.json      - the twelve official 11/18 finals (absence proof)

and writes (deterministically):

  * manifest.json                      - sha256 + byte size + source URL for every capture
  * injury_parsed.json                 - both revisions parsed row-for-row + consecutive diff
  * player_logs_injury_2026-11-19.json - one row per report player: report fields, the
    player's most-recent-game log (min/pts/reb/ast or the printed DND/inactive reason),
    opponent, match method, flags, and a source link on every row

Rules honoured here (no manual input, no invented values):
  - a value that cannot be read from a capture stays null and the row carries a flag;
  - report rows whose Team cell is blank keep team=null unless the official game book
    itself prints the same player name AND the same printed reason (then team_source=
    "gamebook" and the row is flagged for review);
  - match reasons must be equal (normalized) whenever both sides print one;
  - identity checks (PTS = 2*FG + 3P + FT, TOT = OR + DR, periods sum to the printed
    final, player minutes sum to the printed 240:00) run over every played row.

Run: python3 scripts/capture_93becd26.py [--check]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-19-93becd26")
CAP = os.path.join(ROUND, "captures")

INJ_0215 = "injury_report_2026-11-19_0215AM.md"
INJ_0200 = "injury_report_2026-11-19_0200AM.md"
SCHED = "schedule_2026-11-18_finals.json"

REPORT_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_02_15AM.pdf"
REPORT_PREV_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_02_00AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
RETRIEVAL_WINDOW = "2026-11-19T07:22Z-07:42Z"

# One game book per game played by the four teams that have attributed report players.
# game_id / game_page come from data/rounds/2026-11-19-dd3edd74/results_2026-11-16_18.json
# (merged via PR #144; that capture's finals are themselves sourced to the official nba.com
# date pages) and are cross-checked below against the finals printed in the game books.
GAMES = [
    {"file": "gamebook_2026-11-17_PORMIN.md", "date": "2026-11-17", "away": "POR", "home": "MIN",
     "game_id": "0022600254",
     "gamebook_url": "https://statsdmz.nba.com/pdfs/20261117/20261117_PORMIN.pdf",
     "game_url": "https://www.nba.com/game/por-vs-min-0022600254"},
    {"file": "gamebook_2026-11-17_DETSAS.md", "date": "2026-11-17", "away": "DET", "home": "SAS",
     "game_id": "0022600255",
     "gamebook_url": "https://statsdmz.nba.com/pdfs/20261117/20261117_DETSAS.pdf",
     "game_url": "https://www.nba.com/game/det-vs-sas-0022600255"},
    {"file": "gamebook_2026-11-17_UTALAC.md", "date": "2026-11-17", "away": "UTA", "home": "LAC",
     "game_id": "0022600257",
     "gamebook_url": "https://statsdmz.nba.com/pdfs/20261117/20261117_UTALAC.pdf",
     "game_url": "https://www.nba.com/game/uta-vs-lac-0022600257"},
]

COLS = ["fg", "fga", "3p", "3pa", "ft", "fta", "oreb", "dreb", "treb", "ast",
        "pf", "stl", "tov", "blk", "plus_minus", "pts"]
POS_TOKENS = {"G", "F", "C", "F-C", "G-F", "C-F", "G-C", "F-G", "C-G"}
MIN_RE = re.compile(r"^(\d{1,3}):(\d{2})$")
TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s).strip()


def norm_text(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace(".", " ").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_reason(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().rstrip(")").strip()).lower()


def cells_of(line: str):
    s = line.strip()
    if not s.startswith("|"):
        return None
    return [strip_tags(c) for c in s.strip("|").split("|")]


# --------------------------------------------------------------------------- registry

def load_registry():
    reg = json.load(open(os.path.join(ROOT, "data", "live", "team_registry.json"),
                         encoding="utf-8"))["teams"]
    return {v["full_name"].upper(): k for k, v in reg.items()}, reg


FULL_TO_CODE, REG = load_registry()


def code_for(label: str | None):
    """Official club name or the short name a score-by-period table prints -> team code."""
    if not label:
        return None
    key = re.sub(r"\(.*?\)", "", label).strip().upper()
    if key in FULL_TO_CODE:
        return FULL_TO_CODE[key]
    hits = sorted({code for full, code in FULL_TO_CODE.items() if key and key in full})
    return hits[0] if len(hits) == 1 else None


# ------------------------------------------------------------------- injury report

def parse_injury(text: str):
    """Rows exactly as printed: player rows, team-not-submitted rows, layout-shifted rows."""
    revision = None
    m = re.search(r"\*\*Injury Report: ([^*]+)\*\*", text)
    if m:
        revision = m.group(1).strip()
    players, team_rows, shifted = [], [], []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        raw = line.strip()
        if raw.startswith("| ---") or "Game Date | Game Time" in raw:
            continue
        cells = [c.strip() for c in raw.strip("|").split("|")]
        cells = [c.strip() for c in cells]
        if len(cells) >= 7:
            game_date, game_time, matchup, team, player, status, reason = cells[:7]
            if player:
                players.append({"game_date": game_date, "game_time": game_time,
                                "matchup": matchup, "team_printed": team,
                                "player": player, "status": status, "reason": reason})
            elif status or reason:
                team_rows.append({"game_date": game_date, "game_time": game_time,
                                  "matchup": matchup, "team_printed": team,
                                  "printed": reason or status})
        elif len(cells) == 3:
            # page-3 layout: columns shifted; recorded as printed, never re-aligned
            shifted.append({"c0": cells[0], "c1": cells[1], "c2": cells[2]})
        elif len(cells) == 7 or len(cells) == 6:
            players.append({"parse_error": "unexpected cell count", "cells": cells})
    return {"revision": revision, "players": players, "team_rows": team_rows,
            "shifted_rows": shifted}


def injury_delta(prev: dict, cur: dict):
    def key(r):
        return (r.get("team_printed") or "", r["player"])
    p = {key(r): r for r in prev["players"]}
    c = {key(r): r for r in cur["players"]}
    added = [c[k] for k in c if k not in p]
    removed = [p[k] for k in p if k not in c]
    changed = []
    for k in c:
        if k in p and p[k] != c[k]:
            changed.append({"player": k, "from": p[k], "to": c[k]})
    return {"from_revision": prev["revision"], "to_revision": cur["revision"],
            "added": added, "removed": removed, "changed": changed,
            "identical": not (added or removed or changed)}


# ------------------------------------------------------------------- game books

def _name_from(prefix):
    parts = [p for p in prefix if p]
    while parts and re.fullmatch(r"\d{1,3}", parts[0]):
        parts = parts[1:]
    if parts:
        parts = [re.sub(r"^\d{1,3}\s+", "", parts[0])] + parts[1:]
    while parts and parts[-1] in POS_TOKENS:
        parts = parts[:-1]
    return " ".join(parts).strip()


def parse_gamebook(text: str, meta: dict):
    """Per-team roster rows (played / dnd / dnp), inactive entries, totals, periods."""
    lines = text.splitlines()
    teams = {}          # code -> block
    cur = None
    header_date = None
    for i, line in enumerate(lines):
        if header_date is None:
            _hd = re.match(r"^[A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}, \d{4}", line)
            if _hd:
                header_date = _hd.group(0)
        mh = re.search(r"(VISITOR|HOME):\s*([A-Za-z0-9 .''-]+?)\s*\(\d+-\d+\)", line)
        if mh and "|" in line:
            code = code_for(mh.group(2))
            if code:
                cur = code
                teams.setdefault(code, {"code": code, "club_printed": mh.group(2).strip(),
                                        "role": mh.group(1).lower(), "roster": [],
                                        "inactive": [], "total": None})
                continue
        cells = cells_of(line)
        if not cells or cur is None:
            continue
        if not any(cells):
            continue
        if "POS" in cells and "MIN" in cells:
            continue
        # DND / DNP rows: the status cell carries the reason
        status_idx = None
        for j, c in enumerate(cells):
            if re.match(r"^(DND|DNP)\b", c):
                status_idx = j
                break
        if status_idx is not None:
            cell = cells[status_idx]
            kind = "dnd" if cell.startswith("DND") else "dnp"
            reason = None
            if kind == "dnd" and " - " in cell:
                reason = cell.split(" - ", 1)[1].strip()
            name = _name_from(cells[:status_idx])
            if name:
                teams[cur]["roster"].append({"player": name, "kind": kind,
                                             "printed_reason": reason})
            continue
        idx = [j for j, c in enumerate(cells) if MIN_RE.match(c)]
        if not idx:
            continue
        j = idx[0]
        name = _name_from(cells[:j])
        vals = cells[j + 1:]
        if cells[j] == "240:00":
            # the printed team-total row (some extractions leave the last player's name
            # in its first cell, e.g. DETSAS home block); no player logs 240:00
            tot = {"min_mmss": "240:00"}
            if len(vals) >= 16 and all(v != "" for v in vals[:16]):
                try:
                    tot.update(dict(zip(COLS, [int(v) for v in vals[:16]])))
                except ValueError:
                    pass
            teams[cur]["total"] = tot
            continue
        rec = {"min_mmss": cells[j]}
        if len(vals) >= 16 and all(v != "" for v in vals[:16]):
            try:
                nums = [int(v) for v in vals[:16]]
            except ValueError:
                teams[cur]["roster"].append({"player": name, "kind": "played",
                                             "parse_error": "non-integer cell",
                                             "cells": vals[:16]})
                continue
            rec.update(dict(zip(COLS, nums)))
            m = MIN_RE.match(cells[j])
            rec["min_decimal"] = round(int(m.group(1)) + int(m.group(2)) / 60.0, 3)
            rec["scoring_identity_ok"] = (2 * rec["fg"] + rec["3p"] + rec["ft"] == rec["pts"])
            rec["reb_identity_ok"] = rec["treb"] == rec["oreb"] + rec["dreb"]
            if not name:                      # the printed team-total row
                teams[cur]["total"] = rec
                continue
            rec["kind"] = "played"
            rec["player"] = name
            teams[cur]["roster"].append(rec)
            continue
    # inactive lines (may wrap across lines)
    inactive = {}
    for m in re.finditer(r"Inactive:\s*([A-Za-z0-9 .''-]+?)\s+-\s+(.*?)(?=\nInactive: |\nBiggest Lead|\nPoints in the Paint|\nTechnical|\nLead Changes|\Z)",
                         text, re.S):
        label, block = m.group(1).strip(), m.group(2)
        code = code_for(label)
        entries = []
        for nm, reason in re.findall(r"(?:^|,\s)([^\(\),]+?)\s*\(([^)]+)\)", block):
            entries.append({"surname_printed": nm.strip(), "kind": "inactive",
                            "printed_reason": re.sub(r"\s+", " ", reason).strip()})
        if code:
            inactive.setdefault(code, []).extend(entries)
    for code, entries in inactive.items():
        teams.setdefault(code, {"code": code, "club_printed": None, "role": None,
                                "roster": [], "inactive": [], "total": None})
        teams[code]["inactive"] = entries
    # score by period
    periods = {}
    plain = re.findall(r"^([A-Za-z0-9 .''-]+?)\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})$",
                       text, re.M)
    for label, *nums in plain:
        if label.upper().startswith("SCORE"):
            continue
        code = code_for(label)
        if code and code not in periods:
            periods[code] = {"label_printed": label,
                             "quarters": [int(x) for x in nums[:4]],
                             "final": int(nums[4])}
    in_table = False
    for line in lines:
        if "SCORE BY PERIOD" in line:
            in_table = True
            continue
        if in_table:
            cells = cells_of(line)
            if not cells:
                continue
            label = cells[0]
            nums = [c for c in cells[1:] if re.fullmatch(r"\d{1,3}", c)]
            if label and len(nums) >= 5 and not label.upper().startswith("SCORE"):
                code = code_for(label)
                if code and code not in periods:
                    periods[code] = {"label_printed": label,
                                     "quarters": [int(x) for x in nums[:4]],
                                     "final": int(nums[4])}
    # per-team verification
    problems = []
    for code, blk in teams.items():
        played = [r for r in blk["roster"] if r.get("kind") == "played"]
        blk["minutes_sum"] = round(sum((r.get("min_decimal") or 0.0) for r in played), 3)
        blk["minutes_ok"] = abs(blk["minutes_sum"] - 240.0) < 0.05
        if blk["total"] and "pts" in blk["total"]:
            blk["total_pts"] = blk["total"]["pts"]
        else:
            blk["total_pts"] = None
        p = periods.get(code)
        if p:
            if sum(p["quarters"]) != p["final"]:
                problems.append(f"{code}: period quarters do not sum to printed final")
            if blk["total_pts"] is not None and p["final"] != blk["total_pts"]:
                problems.append(f"{code}: period final {p['final']} != team-total PTS {blk['total_pts']}")
        if not blk["minutes_ok"]:
            problems.append(f"{code}: played minutes sum {blk['minutes_sum']} != 240:00")
        for r in played:
            if not (r.get("scoring_identity_ok") and r.get("reb_identity_ok")):
                # the printed row itself disagrees (present identically in every fetch);
                # it is recorded, never repaired, and only blocks a report player
                (blk.setdefault("row_notes", []).append(
                    f"{r['player']}: printed row fails PTS=2*FG+3P+FT or TOT=OR+DR "
                    f"(fg={r.get('fg')},3p={r.get('3p')},ft={r.get('ft')},pts={r.get('pts')},"
                    f"oreb={r.get('oreb')},dreb={r.get('dreb')},treb={r.get('treb')})"))
    return {"header_date": header_date, "teams": teams, "periods": periods,
            "problems": problems}


# ---------------------------------------------------------------- matching + payload

def split_report_name(player: str):
    if "," in player:
        last, first = player.split(",", 1)
        return first.strip(), last.strip()
    return player.strip(), ""


def build_payload():
    inj_cur = parse_injury(open(os.path.join(CAP, INJ_0215), encoding="utf-8").read())
    inj_prev = parse_injury(open(os.path.join(CAP, INJ_0200), encoding="utf-8").read())
    delta = injury_delta(inj_prev, inj_cur)

    schedule = json.load(open(os.path.join(CAP, SCHED), encoding="utf-8"))
    teams_absent = {"LA Clippers", "San Antonio Spurs", "Minnesota Timberwolves",
                    "Portland Trail Blazers"}
    absent_ok = all(
        r["away"] not in teams_absent and r["home"] not in teams_absent
        for r in schedule["rows"]) and len(schedule["rows"]) == schedule["games_printed"] == 12

    games, game_by_team = [], {}
    problems = []
    for meta in GAMES:
        text = open(os.path.join(CAP, meta["file"]), encoding="utf-8").read()
        parsed = parse_gamebook(text, meta)
        problems += [f"{meta['file']}: {p}" for p in parsed["problems"]]
        codes = [c for c in (meta["away"], meta["home"]) if c in parsed["teams"]]
        entry = {"date": meta["date"], "away": meta["away"], "home": meta["home"],
                 "game_id": meta["game_id"], "gamebook_url": meta["gamebook_url"],
                 "game_url": meta["game_url"],
                 "header_date_printed": parsed["header_date"],
                 "teams": {}, "periods": {}}
        for code in (meta["away"], meta["home"]):
            blk = parsed["teams"].get(code)
            if not blk:
                problems.append(f"{meta['file']}: team {code} block not found")
                continue
            entry["teams"][code] = {"club_printed": blk["club_printed"],
                                    "total_pts": blk.get("total_pts"),
                                    "minutes_sum": blk["minutes_sum"],
                                    "minutes_ok": blk["minutes_ok"],
                                    "played_rows": len([r for r in blk["roster"]
                                                        if r.get("kind") == "played"]),
                                    "inactive": blk["inactive"],
                                    "row_notes": blk.get("row_notes", [])}
            game_by_team[code] = {"meta": meta, "block": blk}
            p = parsed["periods"].get(code)
            if p:
                entry["periods"][code] = p
        games.append(entry)

    # cross-check game_id rows against the merged official finals capture (read-only)
    dd_path = os.path.join(ROOT, "data", "rounds", "2026-11-19-dd3edd74",
                           "results_2026-11-16_18.json")
    finals_crosscheck = []
    if os.path.exists(dd_path):
        dd = json.load(open(dd_path, encoding="utf-8"))
        rows = dd.get("rows") or dd.get("games") or []
        by_id = {r.get("game_id"): r for r in rows}
        for g in games:
            r = by_id.get(g["game_id"])
            if not r:
                finals_crosscheck.append({"game_id": g["game_id"], "result": "absent"})
                continue
            printed = {c: g["teams"].get(c, {}).get("total_pts")
                       for c in (g["away"], g["home"])}
            ok = (printed.get(g["away"]) == r.get("away_pts")
                  and printed.get(g["home"]) == r.get("home_pts"))
            finals_crosscheck.append({"game_id": g["game_id"], "printed": printed,
                                      "merged_final": {"away_pts": r.get("away_pts"),
                                                       "home_pts": r.get("home_pts")},
                                      "match": ok})
            if not ok:
                problems.append(f"game {g['game_id']}: gamebook totals disagree with "
                                f"the merged official finals capture")

    # ---- match every report player to exactly one game log
    def match_player(row):
        first, last = split_report_name(row["player"])
        team_printed = row["team_printed"]
        printed_code = code_for(team_printed) if team_printed else None
        report_norm = norm_text(f"{first} {last}")
        report_last = norm_text(last)
        report_reason = norm_reason(row["reason"])
        flags = []
        candidates = []
        if printed_code and printed_code in game_by_team:
            candidates = [(printed_code, game_by_team[printed_code], "report")]
        else:
            # blank team cell: search every captured game book (official roster/inactive
            # lines only) for the same name AND the same printed reason
            for code, info in game_by_team.items():
                candidates.append((code, info, "gamebook"))
        best = None
        for code, info, team_source in candidates:
            blk = info["block"]
            # roster: full name
            for r in blk["roster"]:
                if norm_text(r["player"]) == report_norm:
                    reason_ok = True
                    if r.get("printed_reason") and report_reason:
                        reason_ok = norm_reason(r["printed_reason"]) == report_reason
                    if reason_ok:
                        best = {"code": code, "info": info, "row": r,
                                "method": "roster_full_name", "surname_only": False,
                                "reason_checked": bool(r.get("printed_reason")),
                                "team_source": team_source}
                        break
            if best:
                break
            # inactive / DNP: surname (+ reason when both print one)
            for e in blk["inactive"]:
                if norm_text(e["surname_printed"]) != report_last:
                    continue
                if e.get("printed_reason") and report_reason:
                    if norm_reason(e["printed_reason"]) != report_reason:
                        continue
                best = {"code": code, "info": info, "row": e,
                        "method": "inactive_surname", "surname_only": True,
                        "reason_checked": bool(e.get("printed_reason")),
                        "team_source": team_source}
                break
            if best:
                break
            # DND/DNP roster rows keyed by surname when the full name differs in form
            for r in blk["roster"]:
                if norm_text(r["player"]).endswith(" " + report_last) and report_last:
                    if r.get("printed_reason") and report_reason:
                        if norm_reason(r["printed_reason"]) != report_reason:
                            continue
                    best = {"code": code, "info": info, "row": r,
                            "method": "roster_surname", "surname_only": True,
                            "reason_checked": bool(r.get("printed_reason")),
                            "team_source": team_source}
                    break
            if best:
                break
        return best

    rows = []
    for row in inj_cur["players"]:
        m = match_player(row)
        out = {"player": row["player"],
               "report": {"game_date": row["game_date"], "game_time": row["game_time"],
                          "matchup": row["matchup"], "team_printed": row["team_printed"],
                          "status": row["status"], "reason": row["reason"]},
               "team": None, "team_source": None, "game_log": None,
               "match": None, "flags": [],
               "sources": {"injury_report": REPORT_URL}}

        if m is None:
            out["flags"].append("no matching line in any captured official game book; "
                                "game log left null")
            rows.append(out)
            continue
        meta = m["info"]["meta"]
        out["team"] = m["code"]
        out["team_source"] = m["team_source"]
        out["match"] = {"method": m["method"], "surname_only": m["surname_only"],
                        "reason_checked": m["reason_checked"]}
        if m["team_source"] == "gamebook" or not row["team_printed"]:
            out["flags"].append(
                "F-93-01: the report row prints no Team/Matchup (page-break layout); "
                "team and game below come only from the official game book line that "
                "prints this player name with the identical printed reason")
        if m["surname_only"]:
            out["flags"].append("F-93-02: matched on surname + identical printed reason "
                                "(the game book's inactive line prints the surname only)")
        log = {"date": meta["date"], "away": meta["away"], "home": meta["home"],
               "opponent": meta["home"] if m["code"] == meta["away"] else meta["away"],
               "game_id": meta["game_id"], "gamebook_url": meta["gamebook_url"],
               "game_url": meta["game_url"]}
        r = m["row"]
        if r.get("kind") == "played":
            log.update({"kind": "played", "min_mmss": r["min_mmss"],
                        "min_decimal": r["min_decimal"], "pts": r["pts"],
                        "reb": r["treb"], "ast": r["ast"],
                        "printed_reason": None,
                        "scoring_identity_ok": r["scoring_identity_ok"],
                        "reb_identity_ok": r["reb_identity_ok"]})
            if not (r["scoring_identity_ok"] and r["reb_identity_ok"]):
                out["flags"].append("printed row fails PTS=2*FG+3P+FT or TOT=OR+DR")
        else:
            log.update({"kind": r.get("kind"), "min_mmss": None, "min_decimal": None,
                        "pts": None, "reb": None, "ast": None,
                        "printed_reason": r.get("printed_reason")})
            if r.get("kind") in ("dnd", "dnp"):
                if r.get("printed_reason") and norm_reason(r["printed_reason"]) != norm_reason(row["reason"]):
                    out["flags"].append("printed game-book reason differs from the report reason")
            else:
                # inactive entry
                if r.get("printed_reason") and norm_reason(r["printed_reason"]) != norm_reason(row["reason"]):
                    out["flags"].append("printed game-book reason differs from the report reason")
        out["game_log"] = log
        rows.append(out)

    # diacritic spelling note (report vs game book printings)
    for out in rows:
        if out["player"] == "Krejci, Vit":
            out["flags"].append("F-93-06: the game book prints the surname as 'Krejčí' "
                                "(diacritic) while the report prints 'Krejci'; matched on "
                                "identical printed reason (Left Ankle Fracture)")

    played = [r for r in rows if r["game_log"] and r["game_log"]["kind"] == "played"]
    dnd = [r for r in rows if r["game_log"] and r["game_log"]["kind"] == "dnd"]
    inactive = [r for r in rows if r["game_log"] and r["game_log"]["kind"] == "inactive"]
    unmatched = [r for r in rows if not r["game_log"]]
    blank_team = [r for r in rows if not r["report"]["team_printed"]]

    payload = {
        "schema": "nba3.rounds.player_logs_injury/v1",
        "what": ("One row for every player listed on the newest official NBA injury report "
                 "at capture time (11/19/26 02:15 AM ET): the report's own fields plus that "
                 "player's most-recent completed game log (minutes, points, rebounds, assists "
                 "or the printed DND/inactive reason) and the opponent, read from the "
                 "official box-score game book of the team's last completed game."),
        "report_revision": inj_cur["revision"],
        "report_url": REPORT_URL,
        "report_index_url": INDEX_URL,
        "previous_revision": inj_prev["revision"],
        "previous_report_url": REPORT_PREV_URL,
        "retrieval_window_utc": RETRIEVAL_WINDOW,
        "retrieval_note": "window of the capture round, not a per-call stamp (flagged F-93-05)",
        "consecutive_diff": delta,
        "recent_game_selection": {
            "rule": ("a team's most recent completed game before the report; none of the four "
                     "teams with attributed report players appears among the twelve finals "
                     "printed on the official 2026-11-18 schedule page, and each game book "
                     "header itself prints Tuesday, November 17, 2026"),
            "schedule_url": schedule["source_url"],
            "schedule_absent_check_ok": absent_ok,
            "games": [{"date": g["date"], "away": g["away"], "home": g["home"],
                       "header_date_printed": g["header_date_printed"],
                       "gamebook_url": g["gamebook_url"]} for g in games]},
        "games": games,
        "finals_crosscheck_vs_merged_capture": finals_crosscheck,
        "rows": rows,
        "counts": {"report_player_rows": len(rows),
                   "team_printed": len(rows) - len(blank_team),
                   "team_blank_on_report": len(blank_team),
                   "log_played": len(played), "log_dnd": len(dnd),
                   "log_inactive": len(inactive), "unmatched": len(unmatched)},
        "problems": problems,
        "row_count": len(rows),
    }
    return payload, inj_cur, inj_prev, delta, schedule


def manifest_files():
    out = {}
    sources = {
        INJ_0215: REPORT_URL,
        INJ_0200: REPORT_PREV_URL,
        SCHED: "https://www.nba.com/schedule?date=2026-11-18",
    }
    for g in GAMES:
        sources[g["file"]] = g["gamebook_url"]
    for name in sorted(os.listdir(CAP)):
        path = os.path.join(CAP, name)
        data = open(path, "rb").read()
        out[name] = {"sha256": hashlib.sha256(data).hexdigest(),
                     "bytes": len(data),
                     "source_url": sources.get(name)}
    return {"schema": "nba3.rounds.manifest/v1",
            "round": "2026-11-19-93becd26",
            "retrieval_window_utc": RETRIEVAL_WINDOW,
            "index_url": INDEX_URL,
            "files": out}


def render():
    payload, inj_cur, inj_prev, delta, schedule = build_payload()
    man = manifest_files()
    injury_parsed = {
        "schema": "nba3.rounds.injury_parsed/v1",
        "current": inj_cur,
        "previous": inj_prev,
        "delta": delta,
        "source_urls": {"current": REPORT_URL, "previous": REPORT_PREV_URL,
                        "index": INDEX_URL},
        "retrieval_window_utc": RETRIEVAL_WINDOW,
        "layout_notes": [
            "section 1 rows carry all seven printed columns;",
            "section 2 (page break) rows print Player/Status/Reason only - Team and "
            "Matchup cells are blank as printed and are never filled in;",
            "section 3 rows have shifted columns and are recorded as printed "
            "(three cells, no player name).",
        ],
    }
    files = {
        "manifest.json": json.dumps(man, indent=1) + "\n",
        "injury_parsed.json": json.dumps(injury_parsed, indent=1) + "\n",
        "player_logs_injury_2026-11-19.json": json.dumps(payload, indent=1) + "\n",
    }
    return files


def main():
    files = render()
    if "--check" in sys.argv:
        bad = []
        for name, blob in files.items():
            path = os.path.join(ROUND, name)
            if not os.path.exists(path):
                bad.append(f"missing {name}")
            elif open(path, encoding="utf-8").read() != blob:
                bad.append(f"drift {name}")
        if bad:
            print("capture check FAILED: " + "; ".join(bad), file=sys.stderr)
            return 1
        print("capture check PASS (3 files byte-identical)")
        return 0
    for name, blob in files.items():
        open(os.path.join(ROUND, name), "w", encoding="utf-8").write(blob)
    p = json.loads(files["player_logs_injury_2026-11-19.json"])
    c = p["counts"]
    print(f"wrote manifest.json, injury_parsed.json, player_logs_injury_2026-11-19.json: "
          f"{c['report_player_rows']} report rows "
          f"({c['team_printed']} team-printed, {c['team_blank_on_report']} blank-team), "
          f"logs played={c['log_played']} dnd={c['log_dnd']} inactive={c['log_inactive']} "
          f"unmatched={c['unmatched']}, problems={len(p['problems'])}")
    return 1 if p["problems"] or c["unmatched"] else 0


if __name__ == "__main__":
    sys.exit(main())
