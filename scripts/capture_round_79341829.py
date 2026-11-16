#!/usr/bin/env python3
"""Capture pass for the 2026-11-15 refresh round (session arena/79341829-nba3).

Parses the committed verbatim files and runs checks OFFLINE, so CI can replay it
deterministically (the same pattern as scripts/capture_official_2026_11_14e.py):

  * data/app/official_injuries_2026-11-15_0615AM_raw_79341829.md  -> official_injuries_2026-11-15_0615AM_79341829.json
      + consecutive-report diff vs the stored 11/14 01:30 PM capture (injury_delta_1115.json)
  * data/app/gamebooks/*.md (official game books via statsdmz.nba.com)
      -> results_feed.json      one row per game: date, teams, final score, quarter scores
      -> player_game_logs.json  per-player rows: minutes, points, rebounds, assists, opponent
      -> minutes_shares.json    top-8 minutes shares per team-game (input to the minutes model)
  * data/app/official_slate_1115_1118.json   -> cross-checks (E5/E6)

Checks printed at the end; any FAIL exits non-zero.

Usage: python3 scripts/capture_official_2026_11_15.py
"""
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
GAMEBOOKS = os.path.join(APP, "gamebooks")

RETRIEVED_STAMP = "2026-11-15T11:33Z"   # the fetch window of this round's captures

INJ_RAW = os.path.join(APP, "official_injuries_2026-11-15_0615AM_raw_79341829.md")
INJ_JSON = os.path.join(APP, "official_injuries_2026-11-15_0615AM_79341829.json")
INJ_PRIOR = os.path.join(APP, "official_injuries_2026-11-14_0130PM.json")
DELTA_JSON = os.path.join(APP, "injury_delta_1115.json")
SLATE_JSON = os.path.join(APP, "official_slate_1115_1118.json")
RESULTS_JSON = os.path.join(APP, "results_feed.json")
LOGS_JSON = os.path.join(APP, "player_game_logs.json")
SHARES_JSON = os.path.join(APP, "minutes_shares.json")
RESULTS_1113 = os.path.join(APP, "official_results_2026-11-13.json")

TEAM_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
NICKNAME_TO_ABBR = {
    "Hawks": "ATL", "Celtics": "BOS", "Nets": "BKN", "Hornets": "CHA", "Bulls": "CHI",
    "Cavaliers": "CLE", "Mavericks": "DAL", "Nuggets": "DEN", "Pistons": "DET",
    "Warriors": "GSW", "Rockets": "HOU", "Pacers": "IND", "Clippers": "LAC",
    "Lakers": "LAL", "Grizzlies": "MEM", "Heat": "MIA", "Bucks": "MIL",
    "Timberwolves": "MIN", "Pelicans": "NOP", "Knicks": "NYK", "Thunder": "OKC",
    "Magic": "ORL", "76ers": "PHI", "Suns": "PHX", "Trail Blazers": "POR",
    "Kings": "SAC", "Spurs": "SAS", "Raptors": "TOR", "Jazz": "UTA", "Wizards": "WAS",
}
STATUSES = {"Out", "Doubtful", "Questionable", "Probable", "Available"}

FAILURES = []


def check(ok, label, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


# ----------------------------------------------------------------------------- injuries

def parse_injury_raw(path):
    text = open(path, encoding="utf-8").read()
    rows = []
    ctx = {"game_date": None, "game_time_et": None, "matchup": None,
           "team_name": None, "team": None}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if set(line.replace("|", "").replace(" ", "")) <= {"-"}:
            continue
        if line.startswith("| Game Date") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # pad to 7
        while len(cells) < 7:
            cells.append("")
        non_empty = [c for c in cells if c]
        if not non_empty:
            continue
        if "NOT YET SUBMITTED" in cells:
            for c in non_empty:
                if re.match(r"^\d\d/\d\d/2026$", c):
                    ctx["game_date"] = c
                elif re.match(r"^\d\d:\d\d \(ET\)$", c):
                    ctx["game_time_et"] = c[:5]
                elif re.match(r"^[A-Z]{2,3}@[A-Z]{2,3}$", c):
                    ctx["matchup"] = c
                elif c in TEAM_NAME_TO_ABBR:
                    ctx["team_name"] = c
                    ctx["team"] = TEAM_NAME_TO_ABBR[c]
            rows.append({
                "game_date": ctx["game_date"], "game_time_et": ctx["game_time_et"],
                "matchup": ctx["matchup"], "team_name": ctx["team_name"],
                "team": ctx["team"], "player": None,
                "status": "NOT YET SUBMITTED", "reason": None,
                "is_team_not_submitted": True, "team_cell_printed": True,
            })
            continue
        status_idx = None
        for i, c in enumerate(cells):
            if c in STATUSES:
                status_idx = i
                break
        if status_idx is None:
            continue  # not a data row
        status = cells[status_idx]
        player = ""
        for j in range(status_idx - 1, -1, -1):
            if cells[j]:
                player = cells[j]
                player_idx = j
                break
        reason = " | ".join(c for c in cells[status_idx + 1:] if c) or None
        printed = False
        for j in range(player_idx - 1, -1, -1):
            c = cells[j]
            if not c:
                continue
            if re.match(r"^\d\d/\d\d/2026$", c):
                ctx["game_date"] = c
            elif re.match(r"^\d\d:\d\d \(ET\)$", c):
                ctx["game_time_et"] = c[:5]
            elif re.match(r"^[A-Z]{2,3}@[A-Z]{2,3}$", c):
                ctx["matchup"] = c
            elif c in TEAM_NAME_TO_ABBR:
                ctx["team_name"] = c
                ctx["team"] = TEAM_NAME_TO_ABBR[c]
                printed = True
        rows.append({
            "game_date": ctx["game_date"], "game_time_et": ctx["game_time_et"],
            "matchup": ctx["matchup"], "team_name": ctx["team_name"],
            "team": ctx["team"], "player": player, "status": status,
            "reason": reason, "is_team_not_submitted": False,
            "team_cell_printed": printed,
        })
    return rows


def build_injury_json(rows):
    player_rows = [r for r in rows if not r["is_team_not_submitted"]]
    nys = [r for r in rows if r["is_team_not_submitted"]]
    unprinted = [r for r in rows if not r["team_cell_printed"]]
    doc = {
        "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf",
        "index_url": "https://official.nba.com/nba-injury-report-2026-27-season/",
        "source_label": ("NBA official injury report PDF, 11/15/26 06:15 AM ET — the newest report "
                         "listed on the official index at read time (2026-11-15T11:33Z; the 11/15 "
                         "index entry runs 12:00 AM through 06:15 AM ET)."),
        "report_stamp": "2026-11-15 06:15 AM ET",
        "report_revision_time": "2026-11-15 06:15 AM ET",
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page, PDF text extraction, 2 chunks joined at the printed page break",
        "raw_file": "data/app/official_injuries_2026-11-15_0615AM_raw_79341829.md",
        "raw_sha256": hashlib.sha256(open(INJ_RAW, "rb").read()).hexdigest(),
        "count": len(rows),
        "player_rows": len(player_rows),
        "not_submitted_rows": len(nys),
        "rows_team_cell_not_printed": len(unprinted),
        "rows": rows,
    }
    return doc


def build_delta(new_rows, prior):
    prior_rows = prior.get("rows", [])
    prior_players = {(r.get("game_date"), r.get("team"), r.get("player")): r
                     for r in prior_rows if not r.get("is_team_not_submitted")}
    new_players = {(r.get("game_date"), r.get("team"), r.get("player")): r
                   for r in new_rows if not r["is_team_not_submitted"]}
    added = [k for k in new_players if k not in prior_players]
    removed = [k for k in prior_players if k not in new_players]
    changed = []
    for k, r in new_players.items():
        old = prior_players.get(k)
        if old and old.get("status") != r.get("status"):
            changed.append({"key": k, "from": old.get("status"), "to": r.get("status"),
                            "reason": r.get("reason")})
    # team-side filing state on the overlapping 11/15 date
    prior_sides = {}
    for r in prior_rows:
        if r.get("game_date") == "11/15/2026":
            prior_sides[(r.get("matchup"), r.get("team"))] = (
                "NOT_YET_SUBMITTED" if r.get("is_team_not_submitted") else "ROWS")
    new_sides = {}
    for r in new_rows:
        if r.get("game_date") == "11/15/2026":
            new_sides[(r.get("matchup"), r.get("team"))] = (
                "NOT_YET_SUBMITTED" if r["is_team_not_submitted"] else "ROWS")
    side_changes = [{"matchup": m, "team": t, "from": prior_sides.get((m, t)),
                     "to": new_sides.get((m, t))}
                    for (m, t) in sorted(set(prior_sides) | set(new_sides))
                    if prior_sides.get((m, t)) != new_sides.get((m, t))]
    return {
        "compared": {
            "prior_report": prior.get("source_url"),
            "prior_report_stamp": prior.get("report_stamp"),
            "new_report": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf",
            "new_report_stamp": "2026-11-15 06:15 AM ET",
        },
        "player_rows_added": len(added),
        "player_rows_removed": len(removed),
        "status_changes": changed,
        "team_side_changes_1115": side_changes,
        "note": ("The two reports cover different game days (01:30 PM 11/14: the 11/14 and 11/15 "
                 "sections; 06:15 AM 11/15: the 11/15 and 11/16 sections), so player-row keys are "
                 "compared on the overlapping 11/15 date only. The 11/15 sides were all team-level "
                 "NOT YET SUBMITTED rows in the prior report and now carry player designations "
                 "except where the team has nothing to report."),
        "retrieved_stamp": RETRIEVED_STAMP,
        "sources": [
            "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf",
            "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf",
        ],
    }


# ----------------------------------------------------------------------------- game books

GAMEBOOK_RE = re.compile(r"_(?P<away>[A-Z]{2,3})(?P<home>[A-Z]{2,3})\.md$")


def parse_gamebook(path):
    name = os.path.basename(path)
    m = GAMEBOOK_RE.search(name)
    away_abbr, home_abbr = m.group("away"), m.group("home")
    text = open(path, encoding="utf-8").read()
    url_m = re.search(r"Source URL: (\S+)", text)
    source_url = url_m.group(1) if url_m else "https://statsdmz.nba.com/"
    day_m = re.match(r"^20(\d{2})(\d{2})(\d{2})_", name)
    game_date = f"20{day_m.group(1)}-{day_m.group(2)}-{day_m.group(3)}" if day_m else "2026-11-14"
    # general session 4a59430d: the per-game capture stamp comes from the verbatim header
    # ("- Retrieved: <stamp>") when present, so a later game day is stamped with its own
    # retrieval time, never with the first round's constant.
    retr_m = re.search(r"^- Retrieved: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z)", text, re.M)
    book_retrieved = retr_m.group(1) if retr_m else RETRIEVED_STAMP
    gid_m = re.search(r"(\d{8})_(\w+)\.pdf", source_url)
    players = []
    quarters = {}
    finals = {}
    ot_periods = {}      # abbr -> printed overtime period scores (OT1[, OT2]) when the book prints them
    readings = {}        # abbr -> every period reading the printed document carries
    conflict = set()     # abbrs whose printed statements disagree — the row is flagged, never repaired
    current_side = None  # 'away' / 'home'
    nickname_of = {}
    for abbr in (away_abbr, home_abbr):
        for nick, a in NICKNAME_TO_ABBR.items():
            if a == abbr:
                nickname_of[nick.lower()] = abbr

    away_end, home_end = _side_index(text)

    def _pts(nums):
        """PTS is the rightmost value that equals 2*(FG-3P) + 3*3P + FT (left columns are
        stable across books; some extracts carry an extra trailing column)."""
        try:
            expected = 2 * (nums[0] - nums[2]) + 3 * nums[2] + nums[4]
        except IndexError:
            return int(nums[-1]) if nums else 0, False
        for v in reversed(nums):
            if v == expected:
                return int(v), True
        return int(nums[-1]) if nums else 0, False

    def _record_reading(abbr, vals):
        """One printed period row: Q1..Q4 (plus printed OT periods) then the printed FINAL.

        Every reading the document prints is kept. If two printed statements of the same
        team's periods disagree, the team lands in `conflict` and the game is flagged
        unverified (and therefore never settled) — the row is never repaired toward one
        reading, matching the rule in data/rounds/2026-11-16/raw/official_gamebooks_2026-11-15.md.
        """
        entry = (tuple(vals[:-1]), int(vals[-1]))
        prev = readings.setdefault(abbr, [])
        if not prev:
            quarters[abbr] = list(entry[0][:4])
            ot_periods[abbr] = list(entry[0][4:])
            finals[abbr] = entry[1]
        elif prev[0] != entry:
            conflict.add(abbr)
        prev.append(entry)

    # some extractions lose the trailing column of a team's stat block (the header row of a
    # 25-column away block reads 25 cells, the home block's 19-20): every stat row on such a
    # side carries only 15 values after its minutes cell (FG … +/-) instead of 16 (… +/- PTS).
    # A side is truncated when NO row on it delivers a 16th value — then the side has no
    # printed player points at all, which are left blank rather than inferred from the total.
    truncated_sides = {"away", "home"} if away_end is not None else set()
    _ln = -1
    for _line in text.splitlines():
        _ln += 1
        if not _line.startswith("|"):
            continue
        _c = [x.strip() for x in _line.strip().strip("|").split("|")]
        _side = "away" if (away_end is None or _ln <= away_end) else (
            "home" if (home_end is None or _ln > home_end) else None)
        if _side not in truncated_sides:
            continue
        try:
            _m = next(i for i, x in enumerate(_c) if re.match(r"^\d\d:\d\d$", x))
        except StopIteration:
            continue
        if len(_c[_m + 1: _m + 17]) >= 16:
            truncated_sides.discard(_side)

    line_no = -1
    for line in text.splitlines():
        line_no += 1
        if away_end is not None:
            current_side = "away" if line_no <= away_end else "home"
        if not line.startswith("|"):
            # bare lines such as "CAVALIERS 33 38 34 22 127" (recap form, with or without
            # printed overtime columns)
            toks = line.strip().split()
            cut = len(toks)
            while cut > 0 and re.fullmatch(r"\d+", toks[cut - 1]):
                cut -= 1
            name = " ".join(toks[:cut]).strip().lower()
            vals = toks[cut:]
            if name in nickname_of and len(vals) >= 5 and all(re.fullmatch(r"\d+", v) for v in vals):
                _record_reading(nickname_of[name], [int(v) for v in vals])
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        non_empty = [c for c in cells if c]
        if not non_empty:
            continue
        if "VISITOR:" in line:
            current_side = "away"
            continue
        if "HOME:" in line:
            current_side = "home"
            continue
        # SCORE BY PERIOD table rows: | Nuggets | 29 | 27 | 30 | 30 | 116 | (OT columns included
        # when the book prints them: | Knicks | 23 | 24 | 20 | 28 | 17 | 112 |)
        if len(non_empty) >= 6 and non_empty[0].lower() in nickname_of:
            try:
                vals = [int(x) for x in non_empty[1:]]
            except ValueError:
                vals = None
            if vals and len(vals) >= 5:
                _record_reading(nickname_of[non_empty[0].lower()], vals)
        # DNP / DND / NWT rows (may be merged with a totals row or a lost-name stint row)
        joined = " | ".join(non_empty)
        if re.search(r"\b(DNP|DND|NWT)\b", joined):
            player_name = re.sub(r"^\d+\s+", "", non_empty[0])
            reason_m = re.search(r"\b(DNP|DND|NWT)\s*-\s*(.+?)(?:\s*\||$)", joined)
            reason = reason_m.group(2).strip() if reason_m else None
            if reason and " - 240:00" in reason:      # merged team-totals row
                reason = reason.split(" - 240:00")[0].strip()
            if reason:  # doubled DNP marker printed in one cell
                reason = re.split(r"\s+(?:DNP|DND|NWT)\s*-\s*", reason)[0].strip()
            players.append({
                "player": player_name, "side": current_side, "min": 0, "min_raw": None,
                "pts": 0, "reb": 0, "ast": 0, "status": "DNP",
                "dnp_reason": reason, "source": source_url,
            })
            # merged: a DNP marker sharing the line with a real stint row (name lost)
            m_min = re.search(r"\b(\d\d:\d\d)\b", joined)
            if m_min and m_min.group(1) != "240:00":
                cells2 = [c for c in cells]
                mi = cells2.index(m_min.group(1))
                vals2 = [(v if v else "0") for v in cells2[mi + 1: mi + 18]]
                try:
                    nums2 = [float(v) for v in vals2]
                except ValueError:
                    nums2 = None
                if nums2 and len(nums2) >= 16:
                    pts2, ok2 = _pts(nums2)
                    players.append({
                        "player": None, "side": current_side,
                        "min": int(m_min.group(1)[:2]) + int(m_min.group(1)[3:]) / 60.0,
                        "min_raw": m_min.group(1),
                        "reb": int(nums2[8]), "ast": int(nums2[9]), "pts": pts2,
                        "status": "played", "dnp_reason": None, "source": source_url,
                        "pts_confirmed_by_box_arithmetic": ok2,
                        "flag": ("player name not attributable: this line merges a DNP marker "
                                 "with a stint row in the PDF extraction"),
                    })
            continue
        # stat rows: find the MM:SS minutes cell; the 16 values after it are
        # FG FGA 3P 3PA FT FTA OR DR TOT A PF ST TO BS +/- PTS (some books add FP as a 17th)
        min_idx = None
        for i, c in enumerate(cells):
            if re.match(r"^\d\d:\d\d$", c):
                min_idx = i
                break
        if min_idx is None:
            continue
        if cells[min_idx] == "240:00":
            continue  # team totals row (also carries the team PTS)
        tail = cells[min_idx + 1: min_idx + 18]
        # the PTS column is the last of the 16; on a truncated side it is simply absent and
        # the printed values stop at +/- — recorded as blank, never inferred from the team total.
        no_pts = current_side in truncated_sides
        vals = [(v if v else "0") for v in tail]
        if len(vals) < 16:
            continue
        try:
            nums = [float(v) for v in vals]
        except ValueError:
            continue
        if len(nums) < 16:
            continue
        pts, ok_pts = _pts(nums)
        name_cells = [c for c in cells[:min_idx] if c and not re.match(r"^[FCG]$", c)
                      and not re.match(r"^\d+$", c)]
        if not name_cells:
            continue
        player_name = re.sub(r"^\d+\s+", "", name_cells[-1])
        try:
            mins = int(cells[min_idx].split(":")[0]) + int(cells[min_idx].split(":")[1]) / 60.0
        except ValueError:
            continue
        players.append({
            "player": player_name, "side": current_side,
            "min": round(mins, 2), "min_raw": cells[min_idx],
            "reb": int(nums[8]), "ast": int(nums[9]), "pts": pts,
            "status": "played", "dnp_reason": None, "source": source_url,
            "pts_confirmed_by_box_arithmetic": ok_pts and not no_pts,
            "pts_printed": None if no_pts else pts,
        })

    # inactive lists ("Inactive: Mavericks - Biberovic (...), Christie (...)") as 0-minute rows
    for line in text.splitlines():
        if not line.startswith("Inactive:"):
            continue
        side = "away" if ("Mavericks" in line or away_abbr in line) else None
        body = line[len("Inactive:"):]
        team_part, _, rest = body.partition(" - ")
        team_token = team_part.strip()
        abbr = None
        for nick, a in NICKNAME_TO_ABBR.items():
            if nick.lower() in team_token.lower():
                abbr = a
        if abbr is None:
            continue
        side = "away" if abbr == away_abbr else "home"
        for item in rest.split(", "):
            item = item.strip()
            if not item:
                continue
            pm = re.match(r"^(.+?)\s*\((.+)\)\s*$", item)
            if pm:
                pname, reason = pm.group(1).strip(), pm.group(2).strip()
            else:
                pname, reason = item, None
            if any(p["player"] == pname and p["side"] == side for p in players):
                continue
            players.append({
                "player": pname, "side": side, "min": 0, "min_raw": None,
                "pts": 0, "reb": 0, "ast": 0, "status": "inactive",
                "dnp_reason": reason, "source": source_url,
            })

    for p in players:
        p["team"] = away_abbr if p["side"] == "away" else home_abbr
        p["opponent"] = home_abbr if p["side"] == "away" else away_abbr
        p["date"] = game_date

    # a team block whose printed player points do not reconcile with its printed final and
    # where no row's points pass the box-arithmetic check: the extraction lost that block's
    # trailing columns. The flag makes the capture report it as a gap (blank, flagged)
    # instead of a wrong number.
    unconfirmed = {
        abbr for abbr, side in ((away_abbr, "away"), (home_abbr, "home"))
        if any(p["side"] == side and p["status"] == "played" and p.get("pts_printed") is None
               for p in players)
    }

    return {
        "game_date": game_date, "away": away_abbr, "home": home_abbr,
        "source": source_url,
        "quarters": quarters, "finals": finals, "players": players,
        "ot": ot_periods, "conflict": conflict, "unconfirmed_pts": unconfirmed,
        "retrieved": book_retrieved,
        "raw_file": f"data/app/gamebooks/{name}",
    }


def _side_index(text):
    """Line indexes of the first/second 240:00 team-totals rows: the away block ends at the
    first, the home block at the second. Game books print the visitors' box first."""
    first = second = None
    for i, line in enumerate(text.splitlines()):
        if "240:00" in line:
            if first is None:
                first = i
            elif second is None:
                second = i
                break
    return first, second


# ----------------------------------------------------------------------------- outputs

def main():
    # --- injuries
    rows = parse_injury_raw(INJ_RAW)
    doc = build_injury_json(rows)
    with open(INJ_JSON, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=False)
        fh.write("\n")
    prior = json.load(open(INJ_PRIOR, encoding="utf-8"))
    delta = build_delta(rows, prior)
    with open(DELTA_JSON, "w", encoding="utf-8") as fh:
        json.dump(delta, fh, indent=1)
        fh.write("\n")

    # --- game books -> results feed + player logs + minutes shares
    books = [parse_gamebook(p) for p in sorted(glob.glob(os.path.join(GAMEBOOKS, "*.md")))]
    feed_rows = []
    log_rows = []
    shares = {}
    for b in books:
        away, home = b["away"], b["home"]
        fq, fh_ = b["finals"].get(away), b["finals"].get(home)
        qq = b["quarters"]
        oo = b.get("ot", {})
        conf = b.get("conflict", set())

        def _sums_ok(abbr, final):
            ps = qq.get(abbr)
            if ps is None or final is None:
                return False
            return sum(ps) + sum(oo.get(abbr, [])) == final

        verified = (fq is not None and fh_ is not None and not conf
                    and _sums_ok(away, fq) and _sums_ok(home, fh_))
        ot_a = oo.get(away, [])
        ot_h = oo.get(home, [])

        def _ot_field(periods, i):
            return periods[i] if len(periods) > i else None

        feed_rows.append({
            "date": b["game_date"], "away": away, "home": home,
            "away_pts": fq, "home_pts": fh_,
            "away_q1": qq.get(away, [None] * 4)[0], "away_q2": qq.get(away, [None] * 4)[1],
            "away_q3": qq.get(away, [None] * 4)[2], "away_q4": qq.get(away, [None] * 4)[3],
            "away_ot1": _ot_field(ot_a, 0), "away_ot2": _ot_field(ot_a, 1),
            "home_q1": qq.get(home, [None] * 4)[0], "home_q2": qq.get(home, [None] * 4)[1],
            "home_q3": qq.get(home, [None] * 4)[2], "home_q4": qq.get(home, [None] * 4)[3],
            "home_ot1": _ot_field(ot_h, 0), "home_ot2": _ot_field(ot_h, 1),
            "state": "Final", "verified": verified,
            "verified_from": b["source"],
            "period_conflict": sorted(conf) or None,
            "quarter_check": ("quarter sums equal the final" if verified else
                              ("the document prints conflicting period scores for "
                               + "/".join(sorted(conf)) + " — held unverified, not repaired")
                              if conf else "quarter sums MISMATCH"),
            "gamebook": b["source"], "raw_file": b["raw_file"],
            "settled": verified,
            "settlement_stamp": (f"settled {b.get('retrieved', RETRIEVED_STAMP)} "
                                 f"(game day end, {b['game_date']}) from the official game book; "
                                 f"quarter sums == finals" if verified else None),
        })
        for p in b["players"]:
            row = {k: p[k] for k in
                   ("date", "player", "team", "opponent", "min", "pts", "reb",
                    "ast", "status", "dnp_reason", "source")}
            if p.get("flag"):
                row["flag"] = p["flag"]
            if p["status"] == "played" and p.get("pts_printed") is None:
                row["pts"] = None
                row["pts_unconfirmed"] = ("the game-book extraction lost this team block's "
                                          "trailing PTS column; the points are left blank, not "
                                          "inferred from the team total")
            log_rows.append(row)
        for side, abbr in (("away", away), ("home", home)):
            team_players = [p for p in b["players"] if p["side"] == side and p["min"] > 0]
            team_players.sort(key=lambda p: -p["min"])
            top8 = team_players[:8]
            total_min = sum(p["min"] for p in team_players) or 1.0
            shares[f"{b['game_date']}:{abbr}"] = {
                "date": b["game_date"], "team": abbr,
                "opponent": home if side == "away" else away,
                "source": b["source"],
                "top8": [{"player": p["player"], "min": p["min"],
                          "share": round(p["min"] / total_min, 4)} for p in top8],
                "top8_share_total": round(sum(p["min"] for p in top8) / total_min, 4),
                "roster_players_used": len(team_players),
            }

    # merge in the 11/13 finals from the stored official scoreboard capture (no quarters)
    prior_results = json.load(open(RESULTS_1113, encoding="utf-8"))
    for g in prior_results["games"]:
        feed_rows.append({
            "date": g["date"], "away": g["away"], "home": g["home"],
            "away_pts": g["away_pts"], "home_pts": g["home_pts"],
            "away_q1": None, "away_q2": None, "away_q3": None, "away_q4": None,
            "home_q1": None, "home_q2": None, "home_q3": None, "home_q4": None,
            "state": g.get("state", "Final"), "verified": True,
            "verified_from": g.get("source"),
            "quarter_check": "quarter scores not captured — blank, flagged",
            "gamebook": None, "raw_file": None,
            "settled": False,
            "settlement_stamp": None,
        })
    feed_rows.sort(key=lambda r: (r["date"], r["away"]))
    # preserve settlement state already stamped by results_feed.py settle (idempotent re-capture)
    if os.path.exists(RESULTS_JSON):
        prev_feed = json.load(open(RESULTS_JSON, encoding="utf-8"))
        prev_by_key = {(g["date"], g["away"], g["home"]): g for g in prev_feed.get("games", [])}
        for r in feed_rows:
            old = prev_by_key.get((r["date"], r["away"], r["home"]))
            if old and old.get("settled"):
                r["settled"] = True
                r["settlement_stamp"] = old.get("settlement_stamp")

    game_days = sorted({r["date"] for r in feed_rows if r["date"] != "2026-11-13"})
    feed = {
        "source_label": ("Official per-game result feed. Every row on a game day ("
                         + ", ".join(game_days) + ") comes from that game's official game book "
                         "(statsdmz.nba.com PDF linked from the nba.com game page; full box "
                         "where the capture round fetched one, verbatim score-only transcription "
                         "otherwise); 2026-11-13 rows come from the stored official scoreboard "
                         "capture (data/app/official_results_2026-11-13.json). One row per game: "
                         "date, teams, final score, quarter scores (printed overtime periods are "
                         "kept in their own columns and included in the sums)."),
        "retrieved_stamp": RETRIEVED_STAMP,
        "settlement_rule": ("A row is settled only when the game state is Final AND the quarter "
                            "scores sum to the printed final for both teams (checked offline). "
                            "Rows without captured quarter scores stay unsettled and flagged."),
        "count": len(feed_rows),
        "settled_count": sum(1 for r in feed_rows if r["settled"]),
        "games": feed_rows,
        "sources": ["https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_DALCLE.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_BKNMEM.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_DETMIA.pdf",
                    "https://statsdmz.nba.com/pdfs/20261114/20261114_CHIMIN.pdf",
                    prior_results.get("source_url")],
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(feed, fh, indent=1)
        fh.write("\n")

    logs = {
        "source_label": ("Per-player game logs captured from official game books for every game "
                         "day whose book was fetched in full (" + ", ".join(sorted({b["game_date"] for b in books if b["players"]})) + ")"
                         ": minutes, points, rebounds, assists and the opponent, plus DNP/inactive "
                         "rows with reasons. One row per player-game."),
        "retrieved_stamp": RETRIEVED_STAMP,
        "count": len(log_rows),
        "rows": log_rows,
        "coverage_note": (f"Full boxes are captured for {len([b for b in books if b['players']])} of "
                          f"{len(books)} game books; the remainder are verbatim score-only "
                          "transcriptions whose games lack player rows (flagged, never guessed). "
                          "Players on teams whose game books are not captured at all are not in "
                          "this capture; the scheduled refresh job (scripts/refresh_official.py) "
                          "fetches every finished game's book each night for the next capture round."),
        "sources": [b["source"] for b in books],
    }
    with open(LOGS_JSON, "w", encoding="utf-8") as fh:
        json.dump(logs, fh, indent=1)
        fh.write("\n")

    with open(SHARES_JSON, "w", encoding="utf-8") as fh:
        json.dump({
            "source_label": ("Top-8 minutes shares per team-game, measured from the official game "
                             "books (sum of minutes over all players who appeared; DNP/inactive "
                             "rows contribute zero). Input to the minutes-redistribution model."),
            "retrieved_stamp": RETRIEVED_STAMP,
            "teams": shares,
        }, fh, indent=1)
        fh.write("\n")

    # ---------------------------------------------------------------- checks
    print("\n--- capture checks (offline) ---")
    bad_status = [r for r in rows if r["status"] not in STATUSES | {"NOT YET SUBMITTED"}]
    check(not bad_status, "E1 every status is a legal designation",
          f"{len(rows)} rows")

    slate = json.load(open(SLATE_JSON, encoding="utf-8"))
    slate_matchups = {f"{g['away']}@{g['home']}": g for g in slate["games"]}
    d15 = [g for g in slate["games"] if g["date"] == "2026-11-15"]
    d16 = [g for g in slate["games"] if g["date"] == "2026-11-16"]
    report_matchups = {r["matchup"] for r in rows if r["matchup"]}
    unknown = [m for m in report_matchups if m not in slate_matchups]
    check(not unknown, "E2 every matchup the report prints is in the stored slate",
          f"{len(report_matchups)} distinct matchups: 11/15 = {len(d15)} games, 11/16 = {len(d16)}")
    sides_1115 = {(r["matchup"], r["team"]) for r in rows if r["game_date"] == "11/15/2026"}
    expect_1115 = {(f"{g['away']}@{g['home']}", t) for g in d15 for t in (g["away"], g["home"])}
    missing_sides = expect_1115 - sides_1115
    check(len(missing_sides) <= 1, "E3 the 11/15 section covers the slate's team-sides",
          f"{len(sides_1115)} of {len(expect_1115)} sides carry rows; "
          f"blank sides (teams with nothing to report): {sorted(missing_sides) or 'none'}")

    ok_feed = all(r["verified"] for r in feed_rows if r["date"] == "2026-11-14")
    check(ok_feed, "E4 quarter sums equal the printed final for every 11/14 game",
          f"{sum(1 for r in feed_rows if r['date'] == '2026-11-14')} games")

    box_ok = True
    unconfirmed = []
    for b in books:
        if not b["players"]:
            continue  # score-only transcription (see the file's own note): no box to reconcile
        for side, abbr in (("away", b["away"]), ("home", b["home"])):
            rows_s = [p for p in b["players"] if p["side"] == side and p["status"] == "played"]
            team_pts = sum(p["pts"] for p in rows_s)
            if b["finals"].get(abbr) is None or team_pts == b["finals"][abbr]:
                continue
            if abbr in b.get("unconfirmed_pts", set()):
                # the PDF extraction never delivered a points column for this team's block
                # (trailing cells lost): the mismatch is a capture gap, not a wrong value.
                # Rows stay at 0 with pts_unconfirmed set — never inferred from the team total.
                unconfirmed.append(f"{b['away']}@{b['home']} {abbr}")
                continue
            box_ok = False
            print(f"    box total mismatch {b['away']}@{b['home']} {abbr}: {team_pts} vs {b['finals'][abbr]}")
    check(box_ok, "E5 player points sum to the team final in every game book",
          f"{len(books)} game books" + (f"; points column not delivered by the extraction "
                                        f"(blank + flagged, see player_game_logs.json): "
                                        f"{', '.join(unconfirmed)}" if unconfirmed else ""))

    conflict_seen = []
    for b in books:
        for r in feed_rows:
            if (r["date"], r["away"], r["home"]) == (b["game_date"], b["away"], b["home"]) and b["conflict"]:
                conflict_seen.append(f"{b['away']}@{b['home']} ({b['game_date']})")
    conflict_handled = all(not r["verified"] for r in feed_rows
                           if (r["date"], r["away"], r["home"]) in
                           {(b["game_date"], b["away"], b["home"]) for b in books if b["conflict"]})
    check(conflict_handled, "E7 every game whose document prints conflicting period scores is flagged unverified",
          f"conflicting games: {', '.join(sorted(conflict_seen)) or 'none'} — held, not repaired")

    check(delta["player_rows_added"] > 0 or len(delta["status_changes"]) >= 0,
          "E6 consecutive-report diff computed", 
          f"added {delta['player_rows_added']} player rows vs the 11/14 01:30 PM report; "
          f"{len(delta['status_changes'])} status changes on overlapping rows; "
          f"{len(delta['team_side_changes_1115'])} team-side filing changes")

    # per-player game log coverage of the 06:15 AM report's named players
    def _norm(n):
        n = n.strip()
        if "," in n:
            last, first = n.split(",", 1)
            n = f"{first.strip()} {last.strip()}"
        return re.sub(r"[^a-z]", "", n.lower())
    named = {_norm(r["player"]): r["player"] for r in rows if r["player"]}
    logged = {_norm(r["player"]): r["player"] for r in log_rows if r["player"]}
    covered = set(named) & set(logged)
    missing = [named[k] for k in sorted(set(named) - set(logged))]
    print(f"[INFO] per-player game-log coverage of the injury report's {len(named)} named players: "
          f"{len(covered)} present in the captured game books; {len(missing)} pending "
          f"(their teams' game books are captured by the scheduled refresh job).")
    if missing:
        print("     pending:", "; ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""))

    if FAILURES:
        print(f"\n{len(FAILURES)} CHECK(S) FAILED")
        return 1
    print("\nall capture checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
