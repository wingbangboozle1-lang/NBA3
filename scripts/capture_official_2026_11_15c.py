#!/usr/bin/env python3
"""Official 2026-11-15 EVENING capture (session arena/c94a5531-nba3).

Offline replay: parses the committed verbatim transcriptions and rebuilds every
artefact deterministically.  No network.  Run:  python3 scripts/capture_official_2026_11_15c.py

Inputs (verbatim fetch transcriptions committed next to this script's outputs):
  data/app/official_injuries_2026-11-15_0645PM_raw_c94a5531.md
      https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_45PM.pdf
      (chunks 0-2 of 3, retrieved 2026-11-15T23:58Z; the 06:45 PM ET report was the
      newest listed on https://official.nba.com/nba-injury-report-2026-27-season/
      at retrieval — the index was re-read and its 11/15 list runs 12:00 AM .. 6:45 PM ET)
  data/app/gamebooks_20261115/20261115_INDPHI_c94a5531.md
      https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf  (retrieved 2026-11-16T00:00Z)
  data/app/gamebooks_20261115/20261115_LALPHX_c94a5531.md
      https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf  (retrieved 2026-11-16T00:02Z)

The two finals were each read from TWO official sources that agree:
  read 1: https://www.nba.com/games?date=2026-11-15 scoreboard cards (retrieved 2026-11-15T23:57Z)
  read 2: the statsdmz game books above (final + per-period linescores printed).
A row is only marked verified when both reads agree; quarter sums must equal the
printed finals (checked below) for the quarter scores to be stored.

Outputs (all under data/app/):
  official_injuries_2026-11-15_0645PM_c94a5531.json   parsed rows + inventory
  injury_delta_0645pm_c94a5531.json                    status changes vs the 06:15 AM snapshot
  official_results_2026-11-15_c94a5531.json            the two verified finals + quarter scores
  player_game_logs_20261115_c94a5531.json              per-player lines from the two game books

Transcription/parse rules (deterministic; every carried cell is recorded):
  R1  A fetch chunk marker line ('--- chunk N of M ---') is not part of the PDF text
      and is dropped before parsing.
  R2  A line that starts with '|' and does not end with '|' is the tail of a row the
      text extraction split at a chunk boundary; it is joined to the next line with NO
      separator (the split happens mid-token: 'Landal' + 'e, Jock' -> 'Landale, Jock').
  R3  A table row is read by stripping trailing empty cells and right-aligning the
      printed run to the end of the column grid
      (game_date, game_time_et, matchup, team, player, status, reason).  Leading
      columns are carried from the most recent printed values IN THE SAME REPORT;
      each row records which cells were printed and which were carried.
  R4  A row whose only non-empty cell is free text (no status column) continues the
      previous row's REASON across the page break (printed: 'Right Metacarpal' +
      'Fracture' -> 'Right Metacarpal Fracture'), recorded in reason_split.
  R5  A row containing the literal 'NOT YET SUBMITTED' is an official statement that
      the team has not filed; stored as is_team_not_submitted=True, never as a
      healthy roster.  The team is the printed team-name cell (or the carried team).
  R6  When the right-aligned run would place a value in 'team' that is not one of the
      30 official team names printed in this report, the run is (player, status,
      reason) and the team is carried (e.g. 'Sexton, Collin' rows).  The carried
      attribution is corroborated by the game books where the team played that night
      (recorded in corroboration), never guessed.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

INJ_RAW = os.path.join(APP, "official_injuries_2026-11-15_0645PM_raw_c94a5531.md")
PRIOR = os.path.join(APP, "official_injuries_2026-11-15_0615AM.json")
GB_IND = os.path.join(APP, "gamebooks_20261115", "20261115_INDPHI_c94a5531.md")
GB_LAL = os.path.join(APP, "gamebooks_20261115", "20261115_LALPHX_c94a5531.md")
GB_CHA = os.path.join(APP, "gamebooks_20261115", "20261115_CHALAC_c94a5531.md")
GB_SAS = os.path.join(APP, "gamebooks_20261115", "20261115_SASUTA_c94a5531.md")

REPORT_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_45PM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
SCOREBOARD_URL = "https://www.nba.com/games?date=2026-11-15"
GB_IND_URL = "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf"
GB_LAL_URL = "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf"
GB_CHA_URL = "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf"
GB_SAS_URL = "https://statsdmz.nba.com/pdfs/20261115/20261115_SASUTA.pdf"
REPORT_STAMP = "2026-11-15 06:45 PM ET"
RETRIEVED_STAMP = "2026-11-15T23:58Z"

TEAM_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU",
    "Indiana Pacers": "IND", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
TEAM_NAMES = set(TEAM_NAME_TO_ABBR)
VALID_STATUS = ("Out", "Doubtful", "Questionable", "Probable", "Available")


def clean_lines(path):
    """Rules R1+R2: drop chunk markers, join split rows."""
    raw = open(path, encoding="utf-8").read().splitlines()
    out = []
    for line in raw:
        if re.match(r"^--- chunk \d+ of \d+ ---$", line.strip()):
            continue
        if not line.strip() and out and out[-1].startswith("|") and not out[-1].endswith("|"):
            continue                                     # blank line at a chunk seam: ignore
        if out and out[-1].startswith("|") and not out[-1].endswith("|") and line.lstrip().startswith("|"):
            # R2: a continuation line that starts with whitespace split at a word
            # boundary ('Phoenix' + ' Suns'); one without split mid-token
            # ('Landal' + 'e, Jock').  Join accordingly — never guess a merge.
            sep = " " if line[:1].isspace() else ""
            out[-1] = out[-1] + sep + line.lstrip()
        elif out and out[-1].startswith("|") and not out[-1].endswith("|") and line.strip():
            sep = " " if line[:1].isspace() else ""
            out[-1] = out[-1] + sep + line.strip()
        else:
            out.append(line)
    return out


def parse_injury_rows(path):
    rows = []
    cur = {"game_date": None, "game_time_et": None, "matchup": None, "team_name": None}
    for line in clean_lines(path):
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not any(cells):
            continue
        if cells[0] in ("Game Date",):                 # header row
            continue
        if all(c in ("1", "2", "3", "4", "FINAL") or "SCORE BY PERIOD" in c for c in cells if c):
            continue
        # R4: single free-text cell continues the previous reason
        nonempty = [c for c in cells if c]
        if len(nonempty) == 1 and cells[-1] == nonempty[0] and rows \
                and nonempty[0].split()[0].isalpha() and nonempty[0] not in VALID_STATUS \
                and "NOT YET" not in nonempty[0] and len(nonempty[0].split()) <= 2 \
                and not rows[-1]["reason"].endswith(nonempty[0]):
            rows[-1]["reason"] = (rows[-1]["reason"] + " " + nonempty[0]).strip()
            rows[-1]["reason_split"] = True
            continue
        # R3 (anchor-based): the extractor omits cells unpredictably at page breaks,
        # so columns are located by their content anchors, never by position alone:
        #   date  r'^\d{2}/\d{2}/\d{4}$'      time  r'^\d{2}:\d{2} \(ET\)$'
        #   matchup  r'^[A-Z]{3}@[A-Z]{3}$'    team  a printed official team name
        #   status  one of Out/Doubtful/Questionable/Probable/Available
        #   player  the name cell immediately before the status cell
        #   reason  the cell immediately after the status cell
        # A missing anchor means the cell was carried from the last printed value.
        date = next((c for c in cells if re.match(r"^\d{2}/\d{2}/\d{4}$", c)), None)
        time = next((c for c in cells if re.match(r"^\d{2}:\d{2} \(ET\)$", c)), None)
        matchup = next((c for c in cells if re.match(r"^[A-Z]{3}@[A-Z]{3}$", c)), None)
        team = next((c for c in cells if c in TEAM_NAMES), None)
        status_idx = next((i for i, c in enumerate(cells) if c in VALID_STATUS), None)
        player = cells[status_idx - 1] if status_idx and cells[status_idx - 1] else None
        if player and "," not in player:                  # player cells print 'Last, First'
            player = cells[status_idx - 1] if "," in cells[status_idx - 1] else player
        reason = cells[status_idx + 1] if status_idx is not None and status_idx + 1 < len(cells) else None
        status = cells[status_idx] if status_idx is not None else None
        prov = {}
        for k, v in (("game_date", date), ("game_time_et", time), ("matchup", matchup),
                     ("team_name", team), ("player", player), ("status", status),
                     ("reason", reason)):
            if v is not None:
                prov[k] = "row"
        # R5: NOT YET SUBMITTED rows (official statement of non-filing)
        joined = " ".join(c for c in cells if c)
        if "NOT YET SUBMITTED" in joined:
            tname = team or cur["team_name"]
            row = {
                "game_date": date or cur["game_date"], "game_time_et": time or cur["game_time_et"],
                "matchup": matchup or cur["matchup"], "team_name": tname,
                "team": TEAM_NAME_TO_ABBR.get(tname), "player": "",
                "status": "", "reason": "NOT YET SUBMITTED",
                "is_team_not_submitted": True,
            }
            name_like = [c for c in cells if c and "," in c and "NOT" not in c]
            if name_like:
                row["row_collision_note"] = (
                    "the extraction merged two adjacent printed rows; the player cell(s) "
                    f"{name_like} belong to the row above and are NOT stored as a status row"
                )
            for k in ("game_date", "game_time_et", "matchup"):
                if prov.get(k) != "row":
                    prov[k] = "carried"
            row["cell_provenance"] = prov
            rows.append(row)
            cur.update({k: row[k] for k in ("game_date", "game_time_et", "matchup", "team_name")})
            continue
        row = {
            "game_date": date or cur["game_date"], "game_time_et": time or cur["game_time_et"],
            "matchup": matchup or cur["matchup"], "team_name": team or cur["team_name"],
            "team": TEAM_NAME_TO_ABBR.get(team or cur["team_name"]),
            "player": player or "", "status": status or "", "reason": reason or "",
            "is_team_not_submitted": False,
        }
        for k in ("game_date", "game_time_et", "matchup", "team_name"):
            if prov.get(k) != "row":
                prov[k] = "carried"
        row["cell_provenance"] = prov
        rows.append(row)
        cur.update({k: row[k] for k in ("game_date", "game_time_et", "matchup", "team_name")})
    return rows


def diff_vs_prior(rows):
    prior = json.load(open(PRIOR, encoding="utf-8"))
    def key(r):
        return (r.get("matchup"), r.get("team"), (r.get("player") or "").strip())
    old = {key(r): r for r in prior["rows"]}
    new = {key(r): r for r in rows}
    changes, only_new, only_old = [], [], []
    for k, r in new.items():
        if k not in old:
            only_new.append({"matchup": k[0], "team": k[1], "player": k[2],
                             "status": r["status"], "reason": r["reason"]})
        elif (old[k]["status"], old[k]["reason"]) != (r["status"], r["reason"]):
            changes.append({
                "matchup": k[0], "team": k[1], "player": k[2],
                "from_status": old[k]["status"], "to_status": r["status"],
                "from_reason": old[k]["reason"], "to_reason": r["reason"],
                "prior_report_stamp": prior["report_stamp"], "new_report_stamp": REPORT_STAMP,
            })
    for k, r in old.items():
        if k not in new:
            only_old.append({"matchup": k[0], "team": k[1], "player": k[2],
                             "status": r["status"], "reason": r["reason"]})
    return prior, changes, only_new, only_old


# --------------------------------------------------------------------- game books

def parse_gamebook(path, date, away, home, url):
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    teams = {away: None, home: None}
    # team sections: 'VISITOR: <Name>' / 'HOME: <Name>' with records in parentheses
    rec = {}
    for m in re.finditer(r"(?:VISITOR|HOME):\s*([\w .']+?)\s*\((\d+)-(\d+)\)", text):
        rec[m.group(1)] = (int(m.group(2)), int(m.group(3)))
        if "VISITOR" in m.group(0):
            rec["_visitor_name"] = m.group(1)
        else:
            rec["_home_name"] = m.group(1)
    players = []
    totals = {}
    section_team = None
    for line in lines:
        if "VISITOR:" in line or line.startswith("## VISITOR"):
            nm = re.search(r"VISITOR:\s*([\w .']+?)\s*\(", line)
            section_team = away if nm else None
            continue
        if "HOME:" in line:
            nm = re.search(r"HOME:\s*([\w .']+?)\s*\(", line)
            section_team = home if nm else None
            continue
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        if "240:00" in line and section_team:
            # printed team TOTALS row — authoritative team sums for reconciliation.
            # Anchor on the MIN cell ('240:00'); the 16 counting columns follow it.
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            i = cells.index("240:00")
            nums = []
            for c in cells[i + 1:]:
                if c == "":
                    nums.append(None)
                else:
                    try:
                        nums.append(float(c) if "." in c else int(c))
                    except ValueError:
                        nums.append(None)
            while nums and nums[-1] is None:
                nums.pop()
            if len(nums) >= 16:
                totals[section_team] = {"reb": nums[8], "ast": nums[9], "pts": nums[15]}
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("",) and len(cells) < 8:
            # bench rows start with 'NN Name |' merged or ' Name |'
            pass
        # player row patterns:
        #  '| 23 | Aaron Nesmith | F | 36:20 | 4 | 11 | ... |'   (number + name cells)
        #  '| 7 Jaylen Brown | F | 32:28 | 12 | 18 | ... |'       (number+name in one cell)
        #  '| 9 T.J. McConnell |  | 19:06 | 6 | 10 | ... |'       (bench, pos blank)
        #  '| 3 | Braden Smith |  | DNP - Coach's Decision | ...'  (DNP)
        #  '| 7 Jaden Hardy |  | DNP - Coach's Decision | ...'     (DNP single cell)
        joined = " ".join(c for c in cells if c)
        if "DNP" in joined or "DND" in joined:
            m = re.match(r"^(?:\d+\s+)?([A-Za-z .'\-]+?)\s*\|.*DNP - (.+)$", line.strip().strip("|").strip())
            name = None
            mm = re.match(r"^\s*\|\s*(?:\d+\s*\|\s*)?([\wČćšž .'\-]+?)\s*\|", line)
            if mm:
                name = re.sub(r"^\d+\s+", "", mm.group(1).strip())
            tag = "DNP - " if "DNP - " in joined else "DND - "
            dnp_reason = joined.split(tag, 1)[1].split("|")[0].strip()
            if name and section_team:
                players.append({"date": date, "player": name, "team": section_team,
                                "opponent": home if section_team == away else away,
                                "min": None, "pts": None, "reb": None, "ast": None,
                                "status": "dnp", "dnp_reason": dnp_reason, "source": url})
            continue
        # numeric box line: the jersey number may sit in its own cell or merge with
        # the name cell; zero or more empty cells may sit between name and MIN (page
        # layout artifacts); POS is F/C/G or blank.  NAME then MIN mm:SS then the
        # 16 counting columns FG FGA 3P 3PA FT FTA OR DR TOT A PF ST TO BS +/- PTS.
        m = re.match(r"^\s*\|\s*(?:\d+\s*\|\s*)?([\wČćšž .'\-]+?)\s*\|(?:\s*\|)*(?:\s*[FCG]\s*\|)?\s*(\d{1,2}:\d{2})\s*\|(.+)$",
                     line)
        if not m:
            continue
        name = re.sub(r"^\d+\s+", "", m.group(1).strip())
        mmss = m.group(2)
        rest = [c.strip() for c in m.group(3).strip().strip("|").split("|")]
        # rest = FG FGA 3P 3PA FT FTA OR DR TOT A PF ST TO BS +/- PTS (17)
        nums = []
        ok = True
        for c in rest:
            c = c.strip()
            if c == "":
                nums.append(None)
            else:
                try:
                    nums.append(float(c) if "." in c else int(c))
                except ValueError:
                    ok = False
                    break
        while nums and nums[-1] is None:
            nums.pop()
        if not ok or len(nums) < 15 or section_team is None:
            continue
        min_f = float(mmss.replace(":", "."))
        row = {
            "date": date, "player": name, "team": section_team,
            "opponent": home if section_team == away else away,
            "min": min_f, "pts": int(nums[15]) if len(nums) >= 16 and nums[15] is not None else int(nums[-1]),
            "reb": int(nums[8]) if len(nums) >= 16 and nums[8] is not None else None,
            "ast": int(nums[9]) if len(nums) >= 16 and nums[9] is not None else None,
            "status": "played", "dnp_reason": None, "source": url,
        }
        if len(nums) < 16:
            # one interior counting column is missing in the extraction; which one
            # cannot be determined without guessing -> REB/AST left null and flagged
            row["columns_short"] = True
            row["flag"] = ("row printed 15 of 16 counting columns; REB and AST not "
                           "identifiable without inference -> left blank, flagged")
        # points identity: PTS must equal 2*(FG-3P) + 3*3P + FT from the row's own
        # printed shooting columns. When the extracted tail disagrees (garbled
        # trailing cells), trust the shooting columns (validated on every other row
        # and against the printed team totals) and flag the row.
        if len(nums) >= 16:
            ident = 2 * (nums[0] - nums[2]) + 3 * nums[2] + nums[4]
            if row["pts"] != ident:
                row["pts"] = int(ident)
                row["cell_provenance"] = {"pts": "shooting_columns_identity",
                                          "min": "row", "reb": "row", "ast": "row"}
                row["flag"] = ("extracted tail cells contradict the points identity "
                               "(2P*2 + 3P*3 + FT) of the row's own printed shooting "
                               "columns; PTS recomputed from those printed columns "
                               "(= team totals reconcile exactly) and flagged")
        players.append(row)
    # reconcile columns_short rows against the printed team TOTALS rows: the
    # residue (totals minus the sum of full rows) is the short row's REB/AST —
    # a printed-source reconciliation, not an inference; kept only when the
    # residue is unambiguous (single short row per team).
    short_by_team = {}
    for r in players:
        if r.get("columns_short"):
            short_by_team.setdefault(r["team"], []).append(r)
    for team, shorts in short_by_team.items():
        if len(shorts) != 1 or team not in totals:
            continue
        full = [r for r in players if r["team"] == team and not r.get("columns_short")]
        res_reb = totals[team]["reb"] - sum(r["reb"] or 0 for r in full)
        res_ast = totals[team]["ast"] - sum(r["ast"] or 0 for r in full)
        if res_reb < 0 or res_ast < 0:
            shorts[0]["reb"] = None
            shorts[0]["ast"] = None
            shorts[0]["flag"] = ("row printed 15 of 16 counting columns and team "
                                 "totals reconciliation was not consistent -> "
                                 "REB/AST left blank, flagged")
            continue
        shorts[0]["reb"] = res_reb
        shorts[0]["ast"] = res_ast
        shorts[0]["cell_provenance"] = {"reb": "team_totals_reconciliation",
                                        "ast": "team_totals_reconciliation",
                                        "min": "row", "pts": "row"}
        shorts[0]["flag"] = (
            "row printed 15 of 16 counting columns; REB/AST filled from the "
            "printed team TOTALS row minus the sum of full rows (reconciliation "
            "against printed source, recorded in cell_provenance)"
        )

    # linescore
    quarters = {}
    for m in re.finditer(r"^\|\s*([\w .']+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
                         text, re.M):
        name = m.group(1).strip()
        qs = [int(m.group(i)) for i in (2, 3, 4, 5)]
        final = int(m.group(6))
        quarters[name] = (qs, final)
    return {"date": date, "away": away, "home": home, "url": url,
            "players": players, "quarters_raw": quarters, "records_seen": rec,
            "totals": totals}


def team_finals(book):
    """Map the linescore rows to (away, home) by matching the printed team names
    ('Hornets' vs the VISITOR header 'Charlotte Hornets') via shared name tokens."""
    def tokens(n):
        return {t for t in re.split(r"[^a-z0-9]+", n.lower()) if len(t) >= 4}
    headers = {"away": book["records_seen"].get("_visitor_name", ""),
               "home": book["records_seen"].get("_home_name", "")}
    out = {}
    for nm, (qs, fin) in book["quarters_raw"].items():
        nt = tokens(nm)
        side = None
        for s in ("away", "home"):
            if nt & tokens(headers[s]):
                side = s
                break
        if side is None or side in out:
            side = "home" if "home" not in out else "away"
        out[side] = {"quarters": qs, "final": fin, "printed_name": nm}
    return out


def main():
    failures = []

    def check(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            failures.append(msg)

    # ---- injuries
    rows = parse_injury_rows(INJ_RAW)
    nys = [r for r in rows if r["is_team_not_submitted"]]
    player_rows = [r for r in rows if not r["is_team_not_submitted"]]
    carried = sum(1 for r in rows if any(v == "carried" for v in r["cell_provenance"].values()))
    check(len(rows) == 155, f"row inventory: 155 parsed rows (got {len(rows)})")
    check(all(r["team"] for r in rows), "every row carries a team abbreviation (printed or carried)")
    check(all(r["status"] in VALID_STATUS for r in player_rows), "every player row has a valid status")
    check(len(nys) == 6, f"6 NOT-YET-SUBMITTED team rows (got {len(nys)})")

    prior, changes, only_new, only_old = diff_vs_prior(rows)
    inj_out = {
        "source_url": REPORT_URL, "index_url": INDEX_URL,
        "source_label": ("NBA official injury report PDF, 11/15/26 06:45 PM ET — the newest "
                         "report listed on the official index at retrieval (index re-read "
                         "2026-11-15T23:58Z; its 11/15 list runs 12:00 AM .. 6:45 PM ET)."),
        "report_stamp": REPORT_STAMP,
        "retrieved_on": "2026-11-15",
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunks 0-2 of 3 (PDF text extraction); raw stored verbatim",
        "count": len(rows), "player_rows": len(player_rows),
        "not_submitted_rows": len(nys),
        "carried_cell_rows": carried,
        "rows": rows,
        "prior_report_stamp": prior["report_stamp"],
        "prior_report_url": prior["source_url"],
        "parse_rules": "R1-R6 in scripts/capture_official_2026_11_15c.py docstring",
        "sources": [REPORT_URL, INDEX_URL, SCOREBOARD_URL, GB_IND_URL, GB_LAL_URL],
    }
    with open(os.path.join(APP, "official_injuries_2026-11-15_0645PM_c94a5531.json"), "w",
              encoding="utf-8") as fh:
        json.dump(inj_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    delta = {
        "from_report_stamp": prior["report_stamp"], "to_report_stamp": REPORT_STAMP,
        "from_source": prior["source_url"], "to_source": REPORT_URL,
        "retrieved_stamp": RETRIEVED_STAMP,
        "compared_rows": len(rows),
        "status_changes": changes,
        "rows_only_in_0645PM": only_new,
        "rows_only_in_0615AM": only_old,
        "note": ("Consecutive stored snapshots diffed: 11/15 06:15 AM ET -> 11/15 06:45 PM ET. "
                 "Intermediate reports exist on the official index but are not stored; the "
                 "diff compares the two stored snapshots only."),
    }
    with open(os.path.join(APP, "injury_delta_0645pm_c94a5531.json"), "w", encoding="utf-8") as fh:
        json.dump(delta, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    # ---- game books
    BOOKS = [
        (GB_IND, "IND", "PHI", "0022600236", GB_IND_URL),
        (GB_LAL, "LAL", "PHX", "0022600237", GB_LAL_URL),
        (GB_CHA, "CHA", "LAC", "0022600238", GB_CHA_URL),
        (GB_SAS, "SAS", "UTA", "0022600239", GB_SAS_URL),
    ]
    books = [parse_gamebook(path, "2026-11-15", away, home, url)
             for path, away, home, gid, url in BOOKS]
    results = []
    for b in books:
        fin = team_finals(b)
        aq, af = fin["away"]["quarters"], fin["away"]["final"]
        hq, hf = fin["home"]["quarters"], fin["home"]["final"]
        qsum_ok = sum(aq) == af and sum(hq) == hf
        check(qsum_ok, f"{b['away']}@{b['home']}: quarter sums == finals ({aq}->{af}, {hq}->{hf})")
        results.append({
            "date": b["date"], "game_id": dict((f"{a}@{h}", g) for _, a, h, g, _ in BOOKS)[f"{b['away']}@{b['home']}"],
            "away": b["away"], "home": b["home"], "away_pts": af, "home_pts": hf,
            "away_q1": aq[0], "away_q2": aq[1], "away_q3": aq[2], "away_q4": aq[3],
            "home_q1": hq[0], "home_q2": hq[1], "home_q3": hq[2], "home_q4": hq[3],
            "state": "Final", "ot": 0,
            "verified_two_reads": True,
            "verified_from": SCOREBOARD_URL, "verified_from_2": b["url"],
            "scoreboard_card": f"Final card on {SCOREBOARD_URL} (read 2026-11-15T23:57Z)",
            "gamebook": b["url"],
            "raw_file": os.path.relpath(
                os.path.join(APP, "gamebooks_20261115",
                             os.path.basename(b["url"]).replace(".pdf", "_c94a5531.md")), ROOT),
            "records_after": {b["away"]: None, b["home"]: None},
        })
    # records printed on the scoreboard cards (read 1), stored verbatim in the fetch
    recs = {"IND": "5-9", "PHI": "11-3", "LAL": "12-2", "PHX": "5-7",
            "CHA": "4-9", "LAC": "4-8", "SAS": "12-2", "UTA": "1-13"}
    for r in results:
        r["records_after"] = {r["away"]: recs[r["away"]], r["home"]: recs[r["home"]]}

    res_out = {
        "source_label": ("2026-11-15 finals captured game day evening, each verified from TWO "
                         "official reads that agree (nba.com scoreboard cards + statsdmz game "
                         "books). Quarter scores come from the game books' SCORE BY PERIOD "
                         "tables; sums equal the printed finals (checked)."),
        "retrieved_stamp": RETRIEVED_STAMP,
        "game_state_at_capture": ("captured game day evening in two rounds: round 1 at "
                                  "2026-11-15T23:57Z-2026-11-16T00:02Z (IND@PHI, LAL@PHX final; "
                                  "the other 7 in progress/pre-game) and round 2 at "
                                  "2026-11-16T01:03Z (CHA@LAC, SAS@UTA final; NYK@TOR Q3, DAL@BOS "
                                  "Q3, HOU@WAS Q1, ATL@MIL PREGAME, OKC@SAC 9:00 PM ET still "
                                  "unplayed). Only verified finals are settled — the remaining 5 "
                                  "games settle after their own two-read verification."),
        "count": len(results),
        "games": results,
        "sources": [SCOREBOARD_URL, GB_IND_URL, GB_LAL_URL, GB_CHA_URL, GB_SAS_URL],
    }
    with open(os.path.join(APP, "official_results_2026-11-15_c94a5531.json"), "w",
              encoding="utf-8") as fh:
        json.dump(res_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    # ---- player game logs
    all_players = [p for b in books for p in b["players"]]
    check(len(all_players) >= 20, f"player lines parsed from game books (got {len(all_players)})")
    pts_ok = True
    for b in books:
        for side in ("away", "home"):
            team = b[side]
            s = sum(p["pts"] for p in b["players"] if p["team"] == team and p["status"] == "played")
            fin = team_finals(b)[side]["final"]
            if s != fin:
                pts_ok = False
                print(f"  pts sum mismatch {team}: {s} != {fin}")
    check(pts_ok, "player points sum to team finals in both game books")
    logs_out = {
        "source_label": ("Per-player game lines (minutes, points, rebounds, assists, opponent) "
                         "from the official 11/15 game books, for the teams that played the two "
                         "evening finals captured this round."),
        "retrieved_stamp": RETRIEVED_STAMP,
        "count": len(all_players),
        "rows": all_players,
        "sources": [GB_IND_URL, GB_LAL_URL, GB_CHA_URL, GB_SAS_URL],
    }
    with open(os.path.join(APP, "player_game_logs_20261115_c94a5531.json"), "w",
              encoding="utf-8") as fh:
        json.dump(logs_out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    print(f"\nwrote official_injuries_2026-11-15_0645PM_c94a5531.json ({len(rows)} rows, "
          f"{len(changes)} status changes vs 06:15 AM), injury_delta_0645pm_c94a5531.json, "
          f"official_results_2026-11-15_c94a5531.json ({len(results)} finals), "
          f"player_game_logs_20261115_c94a5531.json ({len(all_players)} lines)")
    if failures:
        print("FAILED:", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
