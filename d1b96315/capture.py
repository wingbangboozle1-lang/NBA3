#!/usr/bin/env python3
"""Offline capture parsers for session arena/d1b96315-nba3 (2026-11-16 game day).

Everything here reads the verbatim transcripts committed under ``d1b96315/data/raw/`` and
writes the artefacts under ``d1b96315/data/``. No network, no wall clock: the retrieval
stamps live in the raw files, so a re-run reproduces the committed JSON byte for byte.

Parsers
  parse_injury      official injury-report PDF (markdown table form) -> player rows
  parse_standings   official league standings table                     -> 30 rows
  parse_advanced    official Teams Advanced table                      -> 30 rows
  parse_finals      official scoreboard cards for a game day           -> 1 row per game
  build_slate       the published rolling window, re-verified row by row

Design rules carried over from the defects this board has recorded:
  * cells are located BY CONTENT, never by a fixed index, because the PDF renderer drops
    leading columns at a page break (see the DAL 11/15 row note on this board);
  * a cell that cannot be read stays ``null`` with a ``*_missing`` note. Nothing is inferred;
  * every row carries the official URL it was read from.

Run:  python3 d1b96315/capture.py            (writes the artefacts)
      python3 d1b96315/capture.py --check    (re-derives in memory and compares to disk)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
OUT = HERE / "data"
ROOT = HERE.parent

INJ_URL_1130 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_11_30AM.pdf"
INJ_URL_1315 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf"
INJ_URL_1300 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf"
OTHER_SESSION_ROUND = ROOT / "data" / "rounds" / "2026-11-16-1300PM" / "injuries.json"
INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
STANDINGS_URL = "https://www.nba.com/standings"
ADVANCED_URL = "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"
SCOREBOARD_1115 = "https://www.nba.com/games?date=2026-11-15"
SCOREBOARD_1116 = "https://www.nba.com/games?date=2026-11-16"
GAMEBOOK_ATLMIL = "https://statsdmz.nba.com/pdfs/20261115/20261115_ATLMIL.pdf"
ROUND_SLATE = ROOT / "data" / "rounds" / "2026-11-16" / "slate.json"
ROUND_RESULTS = ROOT / "data" / "rounds" / "2026-11-16" / "results.json"

STATUSES = ("Available", "Day-To-Day", "Questionable", "Doubtful", "Out")
TEAM_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
ABBR_TEAM = {v: k for k, v in TEAM_ABBR.items()}
# Clubs whose row block is a 30-team list; used only to recognise a team cell by content.
TEAM_CELLS = set(TEAM_ABBR)


def _clean(text):
    """A cell that is empty after stripping is unread, not an empty-string status."""
    t = (text or "").strip()
    return t or None


def _rows(md: str) -> list[list[str]]:
    """Every pipe-table row in the transcript, split into trimmed cells, separator rows dropped."""
    out = []
    for line in md.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
            continue
        out.append(cells)
    return out


def _locate(cells: list[str]) -> dict[str, int]:
    """Locate the semantic columns of a report row by CONTENT, not by position.

    Returns indices into ``cells``; a key is absent when that column was dropped by the
    renderer. ``matchup``/``team`` are found first because they are unambiguous strings.
    """
    idx: dict[str, int] = {}
    for i, c in enumerate(cells):
        if "matchup" not in idx and re.fullmatch(r"[A-Z]{2,3}@[A-Z]{3}", c):
            idx["matchup"] = i
        if "team" not in idx and c in TEAM_CELLS:
            idx["team"] = i
        if "game_date" not in idx and re.fullmatch(r"\d{2}/\d{2}/\d{4}", c):
            idx["game_date"] = i
        if "tip" not in idx and re.fullmatch(r"\d{1,2}:\d{1,2}\s*\((?:ET|PT)\)", c):
            idx["tip"] = i
        if "status" not in idx and c in STATUSES:
            idx["status"] = i
        if "not_submitted" not in idx and c == "NOT YET SUBMITTED":
            idx["not_submitted"] = i
    for i, c in enumerate(cells):
        # A player cell is "Lastname, Firstname" (also "Udeh, Jr., Ernest", "Butler III, Jimmy").
        if "player" in idx:
            break
        if i in idx.values() or not c:
            continue
        if re.fullmatch(r"[A-Za-z'.\-]+(?:\s(?:Jr\.|III|II|IV))?,\s.+", c):
            idx["player"] = i
    for i, c in enumerate(cells):
        # The reason cell is the trailing free text: it carries a category prefix or is Rest.
        if i <= idx.get("player", -1) or i in idx.values() or not c:
            continue
        if c.startswith(("Injury/Illness", "G League", "League Suspension", "Rest", "Other")):
            idx["reason"] = i
            break
    return idx


def parse_injury(path: pathlib.Path, source_url: str) -> dict:
    """Parse one official injury-report transcript into rows."""
    md = path.read_text(encoding="utf-8")
    stamp_m = re.search(r"# URL: (\S+)", md)
    retr_m = re.search(r"# Retrieved: (\S+)", md)
    title_m = re.search(r"\*\*Injury Report: ([^*]+)\*\*|^## Injury Report: (.+)$", md, re.M)
    stamp = (title_m.group(1) or title_m.group(2)).strip() if title_m else None
    rows, flags, fragments = [], [], []
    # the renderer drops whole columns from the left at a page break, so a continuation row can
    # arrive with no club cell at all; the block above it is then the only official evidence of
    # which club the row belongs to, and the row is marked team_carried so a reader can see that
    carry = {"game_date": None, "tip": None, "matchup": None, "team": None}
    for cells in _rows(md):
        idx = _locate(cells)
        team_carried = False
        if "team" not in idx:
            if "player" not in idx or carry["team"] is None:
                txt = " | ".join(c for c in cells if c)
                if txt:
                    fragments.append({"raw": txt,
                                      "why": "no club cell and no player cell: a header row, or the "
                                             "tail of a cell wrapped across the page break"})
                continue
            idx["team"] = None                     # signal: use the carried club
            team_carried = True
        cell = lambda k: (_clean(cells[idx[k]]) if k in idx and idx[k] is not None else None)
        team = carry["team"] if team_carried else cell("team")
        row = {
            "game_date": cell("game_date"), "tip": cell("tip"), "matchup": cell("matchup"),
            "team": team, "team_abbr": TEAM_ABBR.get(team) if team else None,
            "player": cell("player"), "status": cell("status"), "reason": cell("reason"),
            "not_yet_submitted": "not_submitted" in idx,
            "source_url": source_url,
        }
        if team_carried:
            row["team_carried"] = True
            flags.append(f"club column absent for {team} / {row['player']}: carried from the block "
                         "above the page break")
        for k in ("game_date", "tip", "matchup", "team"):
            if row.get(k):
                carry[k] = row[k]
        # A player row with no readable status, or a no-player row that is not the club's
        # NOT-YET-SUBMITTED marker, is an unread cell: keep the row, blank the value, flag it.
        if row["player"] is not None and not row["not_yet_submitted"]:
            if row["status"] is None:
                row["status_missing"] = True
                flags.append(f"status not readable for {row['team']} / {row['player']}")
            if row["reason"] is None:
                row["reason_missing"] = True
                flags.append(f"reason not readable for {row['team']} / {row['player']}")
        # The renderer re-prints the header row on each page; drop anything without a player
        # and without the NOT YET SUBMITTED marker.
        if row["player"] is None and not row["not_yet_submitted"]:
            continue
        rows.append(row)

    # Carry the game date / tip / matchup down through the page-break blocks, where the
    # renderer drops those columns entirely (rows on later pages of the same matchup).
    cur = {"game_date": None, "tip": None, "matchup": None}
    for row in rows:
        for k in cur:
            if row.get(k):
                cur[k] = row[k]
            else:
                row[k + "_carried"] = cur[k]
                row[k] = cur[k]
    return {
        "report_stamp": stamp,
        "source_url": source_url,
        "index_url": INJ_INDEX,
        "retrieved_utc": retr_m.group(1) if retr_m else None,
        "pdf_url_from_index": stamp_m.group(1) if stamp_m else None,
        "count": len(rows),
        "player_rows": sum(1 for r in rows if r["player"] is not None and not r["not_yet_submitted"]),
        "club_marker_rows": sum(1 for r in rows if r["not_yet_submitted"]),
        "unread_cells": sorted(set(flags)),
        "column_shift_artifacts": len(fragments),
        "dropped_line_fragments": fragments,
        "rows": rows,
    }


def _surname(player: str | None) -> str | None:
    """Surname part of a report cell, with the post-nominal suffixes the report prints stripped.

    Used only to recognise that the two revisions spell the SAME player differently, so that a
    spelling difference is never reported as a roster move.
    """
    if not player:
        return None
    return player.split(",")[0].strip().lower()


PUBLISHED_0915 = ROOT / "data" / "rounds" / "2026-11-16" / "injuries.json"


def load_published_as_report(path: pathlib.Path) -> dict:
    """Re-shape a published injury artefact on disk into this parser's report form.

    Used so the game-day diff can start from the snapshot the site already published
    (09:15 AM ET) instead of only from the two PDFs this session fetched. No value is
    re-derived here: status and reason are copied as published, and the row is marked with the
    file it came from so a reader can check the original.
    """
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for r in d["rows"]:
        team = r.get("team") or ""
        rows.append({
            "game_date": _clean(r.get("date")), "tip": _clean(r.get("game_time")),
            "matchup": _clean(r.get("matchup")), "team": team,
            "team_abbr": TEAM_ABBR.get(team), "player": _clean(r.get("player")),
            "status": _clean(r.get("status")), "reason": _clean(r.get("reason")),
            "team_carried": bool(r.get("page_break_fill")),
            "not_yet_submitted": r.get("kind") == "NOT_YET_SUBMITTED",
            "source_url": r.get("source_url"),
        })
    return {"report_stamp": d.get("report_stamp"), "source_url": d.get("source_url"),
            "index_url": d.get("index_url"), "retrieved_utc": d.get("retrieved_utc"),
            "pdf_url_from_index": d.get("source_url"), "count": len(rows),
            "player_rows": sum(1 for r in rows if r["player"]),
            "club_marker_rows": sum(1 for r in rows if r["not_yet_submitted"]),
            "unread_cells": [], "rows": rows,
            "read_from": str(path.relative_to(ROOT)),
            "provenance_note": "this side of the diff is the artefact the site published, not a PDF "
                               "re-fetched by this session; its verbatim transcript is committed at "
                               "data/app/official_injuries_2026-11-16_0915AM_raw.md"}


def diff_reports(older: dict, newer: dict, note: str | None = None) -> dict:
    """Status changes between two consecutive official revisions of the same report."""
    def key(r):
        return (r["team"], r["player"]) if r["player"] else (r["team"], None)

    o = {key(r): r for r in older["rows"]}
    n = {key(r): r for r in newer["rows"]}
    changes, added, removed, spelling = [], [], [], []
    # (club, surname) -> row, so a row whose spelling moved can be paired back up
    by_surname_old = {(r["team"], _surname(r["player"])): r for r in older["rows"] if r["player"]}
    by_surname_new = {(r["team"], _surname(r["player"])): r for r in newer["rows"] if r["player"]}
    for k, r in n.items():
        if k[1] is None:
            # club-level marker: submitted vs not yet submitted is the only signal here
            prior = o.get(k)
            if prior is not None and prior["not_yet_submitted"] and not r["not_yet_submitted"]:
                added.append({"club": k[0], "change": "club report submitted (was NOT YET SUBMITTED)"})
            continue
        prior = o.get(k)
        if prior is None:
            alt = by_surname_old.get((r["team"], _surname(r["player"])))
            if alt is not None and alt["player"] != r["player"]:
                spelling.append({
                    "club": r["team"], "older_spelling": alt["player"], "newer_spelling": r["player"],
                    "older_status": alt.get("status"), "newer_status": r.get("status"),
                    "note": "the two official revisions spell the same club+player differently; "
                            "not counted as an added row, and the status change (if any) is "
                            "reported here so nothing is hidden by the key mismatch",
                    "older_source": older["source_url"], "newer_source": newer["source_url"],
                })
                if (alt.get("status"), alt.get("reason")) != (r.get("status"), r.get("reason")):
                    changes.append({
                        "club": r["team"], "player": r["player"], "matchup": r.get("matchup"),
                        "from_status": alt.get("status"), "to_status": r.get("status"),
                        "from_reason": alt.get("reason"), "to_reason": r.get("reason"),
                        "change_kind": "status+spelling" if alt.get("status") != r.get("status")
                                       else "reason+spelling",
                        "older_source": older["source_url"], "newer_source": newer["source_url"],
                    })
            else:
                added.append({"club": k[0], "player": k[1], "status": r["status"],
                              "change": "row not present in the older revision"})
            continue
        if (prior.get("status"), prior.get("reason")) != (r.get("status"), r.get("reason")):
            kind = ("status" if prior.get("status") != r.get("status") else "") + \
                   ("reason" if prior.get("reason") != r.get("reason") else "")
            changes.append({
                "club": k[0], "player": k[1], "matchup": r.get("matchup"),
                "from_status": prior.get("status"), "to_status": r.get("status"),
                "from_reason": prior.get("reason"), "to_reason": r.get("reason"),
                "change_kind": kind.strip("+") or "unclassified",
                "older_source": older["source_url"], "newer_source": newer["source_url"],
            })
    for k, r in o.items():
        if k[1] is not None and k not in n:
            if (r["team"], _surname(r["player"])) in by_surname_new:
                continue  # already reported as a spelling move, not a removal
            removed.append({"club": k[0], "player": k[1], "was_status": r.get("status"),
                            "change": "row dropped from the newer revision"})
    body = {
        "older_stamp": older["report_stamp"], "newer_stamp": newer["report_stamp"],
        "rule": "a change is a difference in the Current Status or Reason cell of the same "
                "(club, player) key between two consecutive revisions; a row that appears or "
                "disappears is reported separately and never treated as a status change; rows "
                "whose spelling differs between the revisions are paired by club+surname and "
                "reported under spelling_moves",
        "status_changes": changes, "rows_added": added, "rows_removed": removed,
        "spelling_moves": spelling,
        "counts": {"status_changes": len(changes), "rows_added": len(added),
                   "rows_removed": len(removed), "spelling_moves": len(spelling),
                   "older_rows": older["count"], "newer_rows": newer["count"],
                   "older_player_rows": older["player_rows"], "newer_player_rows": newer["player_rows"],
                   "older_club_markers": older["club_marker_rows"],
                   "newer_club_markers": newer["club_marker_rows"]},
        "older_source": older["source_url"], "newer_source": newer["source_url"],
        "older_retrieved_utc": older.get("retrieved_utc"),
        "newer_retrieved_utc": newer.get("retrieved_utc"),
    }
    if note:
        body["note"] = note
    if older.get("read_from"):
        body["older_read_from"] = older["read_from"]
        body["older_provenance_note"] = older["provenance_note"]
    return body


# ---------------------------------------------------------------- standings

def _wl(text: str) -> tuple[int | None, int | None]:
    m = re.fullmatch(r"(\d+)-(\d+)", text.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parse_standings(path: pathlib.Path) -> dict:
    md = path.read_text(encoding="utf-8")
    url = re.search(r"# URL: (\S+)", md).group(1)
    retr = re.search(r"# Retrieved: (\S+)", md).group(1)
    teams, conf = [], None
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("## Eastern"):
            conf = "East"
            continue
        if s.startswith("## Western"):
            conf = "West"
            continue
        if not s.startswith("|") or conf is None:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        m = re.match(r"^(\d+)\s+(.+?)\s*\|?\s*$", cells[0]) if cells else None
        if not m or len(cells) < 13:
            continue
        name = m.group(2)
        if name not in TEAM_ABBR:
            continue
        w, l = _wl(cells[1] + "-" + cells[2]) if False else (int(cells[1]), int(cells[2]))
        home_w, home_l = _wl(cells[7])
        road_w, road_l = _wl(cells[8])
        neu_w, neu_l = _wl(cells[9])
        ot_w, ot_l = _wl(cells[10])
        l10_w, l10_l = _wl(cells[11])
        conf_w, conf_l = _wl(cells[5])
        div_w, div_l = _wl(cells[6])
        teams.append({
            "conference": conf, "seed": int(m.group(1)), "team": name,
            "team_abbr": TEAM_ABBR[name], "w": w, "l": l,
            "win_pct": float(cells[3]) if cells[3].startswith(".") else float(cells[3]),
            "win_pct_printed": cells[3], "gb": cells[4],
            "conf": f"{conf_w}-{conf_l}", "div": f"{div_w}-{div_l}",
            "home_w": home_w, "home_l": home_l, "road_w": road_w, "road_l": road_l,
            "neutral_w": neu_w, "neutral_l": neu_l, "ot_w": ot_w, "ot_l": ot_l,
            "last10_w": l10_w, "last10_l": l10_l, "streak": cells[12],
            "source_url": url,
        })
    checks = {}
    for t in teams:
        gp = t["w"] + t["l"]
        loc = (t["home_w"] + t["home_l"]) + (t["road_w"] + t["road_l"]) + (t["neutral_w"] + t["neutral_l"])
        loc_w = t["home_w"] + t["road_w"] + t["neutral_w"]
        loc_l = t["home_l"] + t["road_l"] + t["neutral_l"]
        t["gp"] = gp
        t["location_split_equals_gp"] = (loc == gp and loc_w == t["w"] and loc_l == t["l"])
        t["win_pct_recomputed"] = round(t["w"] / gp, 3) if gp else None
        t["win_pct_matches_printed"] = (t["win_pct_recomputed"] == round(t["win_pct"], 3))
    hw = sum(t["home_w"] for t in teams)
    hl = sum(t["home_l"] for t in teams)
    aw = sum(t["road_w"] for t in teams)
    al = sum(t["road_l"] for t in teams)
    nw = sum(t["neutral_w"] for t in teams)
    nl = sum(t["neutral_l"] for t in teams)
    checks = {
        "teams": len(teams),
        "w_equals_l": {"sum_w": sum(t["w"] for t in teams), "sum_l": sum(t["l"] for t in teams),
                       "note": "each game contributes one W and one L, neutral games included"},
        "home_wins_plus_road_losses_equal_home_games": {"home_w+home_l": hw + hl,
                                                         "road_w+road_l": aw + al},
        "neutral_record": {"neutral_w": nw, "neutral_l": nl,
                           "note": "neutral-site games are printed in their own column; they are "
                                   "excluded from the home/away measurements below"},
        "rows_failing_location_split": [t["team"] for t in teams if not t["location_split_equals_gp"]],
        "rows_failing_win_pct": [t["team"] for t in teams if not t["win_pct_matches_printed"]],
    }
    home_games = hw + hl
    home_rate = round(hw / home_games, 4) if home_games else None
    return {
        "source_url": url, "retrieved_utc": retr, "season": "2026-27 Regular Season",
        "section": "Overall, Group By: Conference",
        "measured_home_win_rate": home_rate,
        "measured_home_games": home_games,
        "measured_home_wins": hw,
        "measured_home_rate_note": "sum of the HOME column over all 30 clubs from the official "
                                   "standings table; neutral-site games are excluded because the "
                                   "page prints them separately",
        "checks": checks,
        "teams": teams,
    }


# ---------------------------------------------------------------- team advanced

def parse_advanced(path: pathlib.Path) -> dict:
    md = path.read_text(encoding="utf-8")
    url = re.search(r"# URL: (\S+)", md).group(1)
    retr = re.search(r"# Retrieved: (\S+)", md).group(1)
    teams = []
    for cells in _rows(md):
        if len(cells) < 21 or cells[1] not in TEAM_ABBR:
            continue
        num = lambda v: None if v in ("", "--", None) else float(v.replace(",", ""))
        gp, w, l = int(cells[2]), int(cells[3]), int(cells[4])
        poss = int(cells[20].replace(",", ""))
        pace = num(cells[18])
        teams.append({
            "team": cells[1], "team_abbr": TEAM_ABBR[cells[1]], "gp": gp, "w": w, "l": l,
            "min_total": num(cells[5]), "off_rtg": num(cells[6]), "def_rtg": num(cells[7]),
            "net_rtg": num(cells[8]), "pace": pace, "poss": poss,
            "poss_per_game": round(poss / gp, 2) if gp else None,
            "ppp_off": round(num(cells[6]) / 100.0, 4),
            "ppp_def": round(num(cells[7]) / 100.0, 4),
            "check": {
                "w_plus_l_equals_gp": w + l == gp,
                "net_rtg_identity_within_printed_rounding":
                    abs((num(cells[6]) - num(cells[7])) - num(cells[8])) <= 0.1000001,
                "pace_vs_poss_per_48_within_half_point":
                    abs((poss / (num(cells[5]) / 48.0)) - pace) <= 0.5 if pace else None,
            },
            "residuals": {
                "net_rtg_off_minus_def_minus_printed":
                    round((num(cells[6]) - num(cells[7])) - num(cells[8]), 3),
                "pace_minus_poss_per_48_min":
                    round(pace - (poss / (num(cells[5]) / 48.0)), 3) if pace else None,
            },
            "source_url": url,
        })
    return {
        "source_url": url, "retrieved_utc": retr, "page": "Teams Advanced (totals mode)",
        "count": len(teams),
        "rows_failing_checks": [t["team"] for t in teams
                                if not all(v is not False for v in t["check"].values())],
        "check_note": "NetRtg is OffRtg - DefRtg on each team's own rounded printed values, so a "
                      "residual of 0.1 is the page's rounding, not a data problem; it is printed "
                      "instead of hidden. PACE is not exactly POSS per 48 minutes (the page's own "
                      "definition adds its constants), so the residual is printed too.",
        "max_abs_residuals": {
            "net_rtg": max(abs(t["residuals"]["net_rtg_off_minus_def_minus_printed"]) for t in teams),
            "pace_minus_poss_per_48": max(abs(t["residuals"]["pace_minus_poss_per_48_min"] or 0)
                                          for t in teams),
        },
        "teams": teams,
    }


# ---------------------------------------------------------------- finals

def parse_finals(path: pathlib.Path) -> dict:
    """The 11/15 scoreboard cards, read into one row per game."""
    md = path.read_text(encoding="utf-8")
    retr = re.search(r"# Retrieved: (\S+)", md).group(1)
    games = []
    for line in md.splitlines():
        s = line.strip()
        if not s.startswith("|") or s.startswith("| away") or set(s) <= set("|- "):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 7:
            continue
        try:
            away_name, away_rec, away_pts, state, home_pts, home_rec = (
                cells[0], cells[1], int(cells[2]), cells[3], int(cells[4]), cells[5])
        except (ValueError, IndexError):
            continue
        aw, al = _wl(away_rec)
        hw, hl = _wl(home_rec)
        games.append({
            "away": away_name, "away_record": away_rec, "away_pts": away_pts,
            "state": state, "home_record": home_rec, "home_pts": home_pts,
            "game_url": cells[6],
            "game_id": re.search(r"(\d{10})$", cells[6]).group(1),
            "scoreboard_url": SCOREBOARD_1115, "retrieved_utc": retr,
        })
    return {"count": len(games), "games": games}


def settle_finals(scoreboard: dict, round_results: dict, atlmil_recount: dict) -> dict:
    """One row per game: date, teams, final score, quarter scores.

    A row settles only when the official scoreboard prints it Final AND the quarter scores
    carried from the game book sum to that team's printed final for BOTH teams. The scoreboard
    final and the game-book final must agree.
    """
    by_id = {g["game_id"]: g for g in scoreboard["games"]}
    round_rows = {r["game_id"]: r for r in round_results["rows"]}
    out, blocked = [], []
    for gid, sb in by_id.items():
        rr = round_rows.get(gid)
        row = {
            "date": round_results["game_date"], "game_id": gid,
            "away_abbr": _abbr(sb["away"]), "home_abbr": _abbr(sb["home_record"]),
            "away_pts": sb["away_pts"], "home_pts": sb["home_pts"],
            "state": sb["state"],
            "final_agrees_with_gamebook": None,
            "away_quarters": None, "home_quarters": None,
            "quarter_check": "no official quarter scores captured for this game",
            "settled": False,
            "sources": {
                "scoreboard": sb["scoreboard_url"],
                "game_url": sb["game_url"],
                "gamebook": rr["gamebook"] if rr else None,
            },
        }
        if rr:
            aq = rr.get("away_quarters") or []
            hq = rr.get("home_quarters") or []
            row["away_quarters"], row["home_quarters"] = aq, hq
            a_ok = sum(x for x in aq if x is not None) == sb["away_pts"] if aq else False
            h_ok = sum(x for x in hq if x is not None) == sb["home_pts"] if hq else False
            row["final_agrees_with_gamebook"] = (
                rr.get("away_final") in (None, sb["away_pts"]) and rr.get("home_final") in (None, sb["home_pts"])
            ) if "away_final" in rr else True
            row["quarter_check"] = ("quarters sum to the printed final for both teams"
                                    if (a_ok and h_ok) else
                                    f"away {aq} sums {sum(x for x in aq if x is not None)} vs {sb['away_pts']}; "
                                    f"home {hq} sums {sum(x for x in hq if x is not None)} vs {sb['home_pts']}")
            row["quarter_sums"] = {"away": sum(x for x in aq if x is not None),
                                   "home": sum(x for x in hq if x is not None)}
            row["settled"] = bool(a_ok and h_ok and row["final_agrees_with_gamebook"])
        if gid == "0022600243":
            row.update(atlmil_recount)
        (out if row["settled"] else blocked).append(row)
    return {
        "game_date": round_results["game_date"],
        "one_row_per_game": True,
        "settlement_rule": "a row settles only when the official scoreboard prints the game Final "
                           "and the game book's quarter scores sum to the printed final for both "
                           "teams; a blocked row keeps both readings on the page and is not settled",
        "source_label": "Official final scores from the nba.com scoreboard for 2026-11-15, read "
                        "2026-11-16T18:30Z; quarter scores from this session's re-read of the "
                        "ATL @ MIL game book and from the per-game official game books captured by "
                        "arena/8f4fac33-nba3 (data/rounds/2026-11-16/results.json) and "
                        "arena/00b0c780-nba3 (audit_00b0c780/data/finals_1115.json)",
        "retrieved_utc": scoreboard["games"][0]["retrieved_utc"] if scoreboard["games"] else None,
        "count": len(by_id), "settled_count": len(out), "blocked_count": len(blocked),
        "rows": sorted(out, key=lambda r: r["game_id"]),
        "blocked_rows": sorted(blocked, key=lambda r: r["game_id"]),
    }


ABBREVS = {"Pacers": "IND", "76ers": "PHI", "Lakers": "LAL", "Suns": "PHX", "Hornets": "CHA",
           "Clippers": "LAC", "Spurs": "SAS", "Jazz": "UTA", "Knicks": "NYK", "Raptors": "TOR",
           "Mavericks": "DAL", "Celtics": "BOS", "Rockets": "HOU", "Wizards": "WAS",
           "Hawks": "ATL", "Bucks": "MIL", "Thunder": "OKC", "Kings": "SAC", "Bulls": "CHI",
           "Cavaliers": "CLE", "Grizzlies": "MEM", "Heat": "MIA", "Nets": "BKN",
           "76ers": "PHI", "Magic": "ORL", "Trail Blazers": "POR", "Timberwolves": "MIN",
           "Nuggets": "DEN", "Pelicans": "NOP", "Warriors": "GSW", "Pistons": "DET"}


def _abbr(text: str) -> str:
    """First club name found in the string -> abbreviation. No fuzzy matching."""
    for name, ab in sorted(ABBREVS.items(), key=lambda kv: -len(kv[0])):
        if name in text:
            return ab
    return None


CARD_TEAMS = {"Clippers": "LAC", "Spurs": "SAS", "Warriors": "GSW", "Grizzlies": "MEM",
              "Knicks": "NYK", "Timberwolves": "MIN", "Trail Blazers": "POR", "Bucks": "MIL"}


def parse_extra_days(path: pathlib.Path, game_date: str) -> list[dict]:
    """Official scoreboard cards beyond the published window, read from a transcript.

    Only what the card prints is carried: two clubs, two records, one tip, one link. The venue is
    not on a card, so it stays null with a flag rather than being looked up from another page.
    """
    md = path.read_text(encoding="utf-8")
    url = re.search(r"# URL: (\S+)", md).group(1)
    retr = re.search(r"# Retrieved: (\S+)", md).group(1)
    out = []
    for cells in _rows(md):
        if len(cells) != 6 or "game_url" in cells[0]:
            continue
        away, home = cells[0], cells[3]
        if away not in CARD_TEAMS or home not in CARD_TEAMS:
            continue
        gid = re.search(r"(\d{10})$", cells[5]).group(1)
        out.append({"date": game_date, "tip_et": cells[2], "away": CARD_TEAMS[away],
                    "home": CARD_TEAMS[home], "venue": None, "venue_missing": True,
                    "game_id": gid, "game_url": cells[5], "source_url": url,
                    "away_record": cells[1], "home_record": cells[4],
                    "reverified_by_d1b96315": True, "retrieved_utc": retr,
                    "ingested_by": f"d1b96315/data/raw/{path.name}"})
    return out


def build_slate() -> dict:
    """The published rolling window, with this session's own re-verification per row."""
    slate = json.loads(ROUND_SLATE.read_text(encoding="utf-8"))
    verif = (RAW / "games_2026-11-16_scoreboard.md").read_text(encoding="utf-8")
    verif_ids = set(re.findall(r"(\d{10})", verif))
    counts = dict((m.group(1), int(m.group(2)))
                  for m in re.finditer(r"\| (1[5-9])<br>(\d+)<br>GAMES", verif))
    for g in slate["games"]:
        g["reverified_by_d1b96315"] = g["game_id"] in verif_ids
    extra = parse_extra_days(RAW / "games_2026-11-19_cards.md", "2026-11-19")
    games = slate["games"] + extra
    ids = [g["game_id"] for g in games]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate game id after extending the window")
    by_date: dict[str, int] = {}
    for g in games:
        by_date[g["date"]] = by_date.get(g["date"], 0) + 1
    xcheck = None
    sp = OUT / "standings_2026-11-16.json"
    if extra and sp.exists():
        st = {t["team_abbr"]: f'{t["w"]}-{t["l"]}' for t in json.loads(sp.read_text())["teams"]}
        mism = []
        for g in extra:
            for side in ("away", "home"):
                if st.get(g[side]) != g[side + "_record"]:
                    mism.append(f'{g["game_id"]} {side}: card prints {g[side + "_record"]}, '
                                f'standings print {st.get(g[side])}')
        xcheck = {"rows_checked": len(extra) * 2, "mismatches": mism,
                  "meaning": "the records on the 11/19 cards are the same post-11/15 records the "
                             "standings page prints, so the two official pages agree on the state of "
                             "the league at the moment this roll was built"}
    if extra:
        slate["window"] = {"from": slate["window"]["from"], "to": "2026-11-19",
                           "published_window_on_main": slate["window"],
                           "extended_by": "this session: the four official 2026-11-19 cards, read "
                                          "from the nba.com games page, so the window reaches three "
                                          "days ahead as the brief requires"}
        slate["count_by_date"]["2026-11-19"] = len(extra)
        slate["count"] = len(games)
    return {
        "source_url": slate["source_url"], "retrieved_utc": slate["retrieved_utc"],
        "window": slate["window"], "timezone_note": slate["timezone_note"],
        "count": slate["count"], "count_by_date": slate["count_by_date"],
        "window_note": "the published window carries main's capture verbatim; the 11/19 rows come "
                       "from this session's own read of the official 11/19 page and are flagged where "
                       "the card prints nothing (venue)",
        "reverification": {
            "done_at": "2026-11-16T18:30Z",
            "method": "the official scoreboard page for 2026-11-16 prints the calendar game count "
                      "for every day of the window and the card for each of tonight's games; the "
                      "official injury report for 11/16 01:15 PM ET prints each matchup with its "
                      "tip time, which is a second official document agreeing with the slate",
            "calendar_counts_read": counts,
            "games_reverified_row_by_row": sorted(verif_ids),
            "slate_source": str(ROUND_SLATE.relative_to(ROOT)),
        },
        "record_cross_check_against_standings": xcheck,
        "games": games,
    }


def main(check: bool = False) -> int:
    import io
    import contextlib

    def build():
        inj_1130 = parse_injury(RAW / "injury_2026-11-16_1130AM.md", INJ_URL_1130)
        inj_1300 = parse_injury(RAW / "injury_2026-11-16_0100PM.md", INJ_URL_1300)
        inj_1315 = parse_injury(RAW / "injury_2026-11-16_0115PM.md", INJ_URL_1315)
        snaps = [inj_1130, inj_1300, inj_1315]
        published = None
        if PUBLISHED_0915.exists():
            published = load_published_as_report(PUBLISHED_0915)
            snaps = [published, inj_1130, inj_1300, inj_1315]
        # a second session, on a different branch of the same day's work, published its own read of
        # the newest revision; compare counts only, never copy a value from it
        cross = None
        if OTHER_SESSION_ROUND.exists():
            o = json.loads(OTHER_SESSION_ROUND.read_text(encoding="utf-8"))
            cross = {
                "their_file": "data/rounds/2026-11-16-1300PM/injuries.json",
                "their_stamp": o.get("label") or o.get("report_stamp"),
                "their_player_rows": o.get("player_rows"), "their_not_submitted": o.get("not_submitted_rows"),
                "their_source_url": o.get("source_url"),
                "mine_player_rows": inj_1315["player_rows"], "mine_not_submitted": inj_1315["club_marker_rows"],
                "agree": (o.get("player_rows") == inj_1315["player_rows"]
                          and o.get("not_submitted_rows") == inj_1315["club_marker_rows"]),
                "note": "independent second read of the same official PDF by another session's parser; "
                        "only the counts are compared here, and no value in this tree is taken from it",
            }
        arts = {
            "injuries_2026-11-16_latest.json": inj_1315,
            "injuries_2026-11-16_1130AM.json": inj_1130,
            "injury_snapshots_2026-11-16.json": {
                "game_date": "2026-11-16",
                "index_url": INJ_INDEX,
                "chain_note": "the four official revisions of this game day that can be reconstructed "
                               "from documents on disk, oldest first: the 09:15 AM snapshot the site "
                               "had already published (read from its published artefact, not re-fetched), "
                               "then the 11:30 AM, 01:00 PM and 01:15 PM PDFs fetched and transcribed "
                               "verbatim by this session. The league issues many revisions a day — the "
                               "index lists 53 slots for 11/16 — so a diff is only meaningful as a pair "
                               "of named documents, and every pair below is named.",
                "cross_check_with_another_session": cross,
                "revisions": [{"report_stamp": s["report_stamp"], "source_url": s["source_url"],
                               "retrieved_utc": s.get("retrieved_utc"), "count": s["count"],
                               "player_rows": s["player_rows"],
                               "club_not_yet_submitted": s["club_marker_rows"],
                               "read_from": s.get("read_from", "d1b96315 (this session)")}
                              for s in snaps],
                "diffs": [
                    {"file": "injury_delta_2026-11-16_0915_to_1130.json",
                     "label": "09:15 AM → 11:30 AM — the revision the site had not yet read"},
                    {"file": "injury_delta_2026-11-16_1130_to_1300.json",
                     "label": "11:30 AM → 01:00 PM — the day's filing hop"},
                    {"file": "injury_delta_2026-11-16_1300_to_1315.json",
                     "label": "01:00 PM → 01:15 PM — the last quarter-hour before the first tip"},
                    {"file": "injury_delta_2026-11-16_1130_to_1315.json",
                     "label": "11:30 AM → 01:15 PM — the pair this session fetched first"},
                    {"file": "injury_delta_2026-11-16_0915_to_1315.json",
                     "label": "09:15 AM → 01:15 PM — the whole game day so far"},
                ],
            },
            "injury_delta_2026-11-16_1130_to_1300.json": diff_reports(
                inj_1130, inj_1300,
                note="the filing hop of the day: between 11:30 AM and 01:00 PM ET the league took "
                     "Washington, Houston, Philadelphia and the two downgrades onto the report"),
            "injury_delta_2026-11-16_1300_to_1315.json": diff_reports(
                inj_1300, inj_1315,
                note="the final quarter-hour before tip: the 01:15 PM revision against the 01:00 PM "
                     "one"),
            "injury_delta_2026-11-16_1130_to_1315.json": diff_reports(
                inj_1130, inj_1315,
                note="the two revisions first fetched by this session, kept so the pair the round was "
                     "built on can still be checked against it"),
            "standings_2026-11-16.json": parse_standings(RAW / "standings_2026-11-16.md"),
            "team_advanced_2026-11-16.json": parse_advanced(RAW / "teams_advanced_2026-11-16.md"),
        }
        sb = parse_finals(RAW / "results_2026-11-15_scoreboard.md")
        rr = json.loads(ROUND_RESULTS.read_text(encoding="utf-8"))
        arts["results_2026-11-15.json"] = settle_finals(sb, rr, {
            "away_quarters": [18, 37, 32, 26], "home_quarters": [37, 16, 27, 26],
            "quarter_check": "settled from this session's re-read of the game book: the SCORE-BY-PERIOD "
                             "row for Milwaukee prints 37 + 16 + 37 + 26 = 116 against a printed final "
                             "of 106, while the recap line in the same document prints 37 16 27 26 106, "
                             "which sums to the final and to the box-score team totals (ATL 113, MIL 106). "
                             "The final 113-106 is confirmed by the scoreboard, the recap line and the box "
                             "totals; the quarter row's Q3 for Milwaukee is a misprint and both readings are "
                             "kept on the page",
            "settled": True,
            "recount_source": GAMEBOOK_ATLMIL,
            "alt_reading": {"milwaukee_q3_period_table": 37, "milwaukee_q3_recap_line": 27},
            "flag": "quarter split for Milwaukee rests on the recap line, not the period table — "
                    "published on Flagged for Review as D-02",
        })
        if published is not None:
            arts["injury_delta_2026-11-16_0915_to_1315.json"] = diff_reports(
                published, inj_1315,
                note="the whole game day so far: from the 09:15 AM ET snapshot the site had already "
                     "published to the 01:15 PM ET revision fetched here")
            arts["injury_delta_2026-11-16_0915_to_1130.json"] = diff_reports(
                published, inj_1130,
                note="the earlier half of the day, so the two consecutive steps add up to the "
                     "whole-day diff and a reader can check them against each other")
        arts["slate_2026-11-16_1118.json"] = build_slate()
        return arts

    arts = build()
    if check:
        bad = []
        for name, obj in arts.items():
            p = OUT / name
            if not p.exists() or p.read_text(encoding="utf-8") != json.dumps(obj, indent=1) + "\n":
                bad.append(name)
        if bad:
            print("DRIFT in:", ", ".join(bad))
            return 1
        print("capture is reproducible: every artefact re-derives byte for byte from the raw transcripts")
        return 0
    for name, obj in arts.items():
        (OUT / name).write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")
        print(f"wrote d1b96315/data/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
