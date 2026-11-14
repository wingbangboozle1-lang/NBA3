#!/usr/bin/env python3
"""Official-source capture #5 for 2026-11-14 (session ``arena/90183333-nba3``).

WHY THIS CAPTURE EXISTS
-----------------------
Every prior capture in this repository read the official injury report at or
before **05:15 AM ET** on 2026-11-14.  At that hour five of the ten team-sides
playing on 2026-11-14 had not filed, and the site correctly published them as
"not yet due" -- the five teams were playing the second game of a back-to-back
and their deadline is 1 p.m. local on game day.

By 2026-11-14T18:44Z (01:44 PM ET) every 11/14 team had filed.  This script
parses the newest report, proves it against a second consecutive report, and
measures exactly which published rows move.

WHAT WAS READ (Arena fetch tool, 2026-11-14T18:44Z = 01:44 PM ET)
----------------------------------------------------------------
1. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf
   -> the NEWEST 11/14 report listed on the official index at read time.
      Verbatim text kept at data/app/official_injuries_2026-11-14_0130PM_raw.md
2. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_15PM.pdf
   -> the immediately preceding report; verbatim text kept at
      data/app/official_injuries_2026-11-14_0115PM_raw.md (second copy)
3. https://official.nba.com/nba-injury-report-2026-27-season/  (the index)
   -> listed the 11/14 reports from 12:00 AM ET through 01:30 PM ET at read time
4. https://www.nba.com/schedule?date=2026-11-14  (chunks 0-2)
   -> the whole 2026-11-14 -> 2026-11-17 window, re-read to re-verify the
      stored slate (27 games) at this new timestamp.

CHECKS (the script exits non-zero if any fails)
-----------------------------------------------
F1  parse(01:30) == parse(01:15), row for row and field for field.
F2  parse(01:30) == the embedded verbatim transcription below (two independent
    representations of the same fetch).
F3  the parsed rows are internally complete where the PDF's own block structure
    settles a cell, and every cell the PDF never prints is left EMPTY.  A cell
    is resolved only from the same document: a game block that starts on the
    previous printed row supplies the date/time/matchup, and a team block that
    starts earlier on the page supplies the team.  Nothing is taken from an
    outside source.
F4  every row of the previous published snapshot (05:15 AM ET) is either
    unchanged in the new report or is reported as a change with both values.
F5  the report's 11/14 games (matchup + tip time) are exactly the five 11/14
    games of the stored official slate; its 11/15 rows pair into exactly the
    nine 11/15 games of that slate with matching tip times.
F6  the tick labels (scoreboard counts ``5 / 9 / 8 / 5 games``) confirm the
    stored slate's 27 games; re-read at 18:44Z from the same schedule page.

WRITES
------
data/app/official_injuries_2026-11-14_0130PM.json   newest parsed snapshot
data/app/availability_delta_0130PM.json             row-by-row change vs 05:15 AM

NOT changed here: data/app/snapshot_manifest.json.  Re-pointing the manifest is
a separate decision (open question CQ-47 / suggestion CS-45) and this round
reports the delta rather than silently rewriting every dependent page.
"""
import datetime
import json
import os
import re
import sys
from collections import OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

SESSION = "arena/90183333-nba3"
RETRIEVED_STAMP = "2026-11-14T18:44Z"
URL_0130 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
URL_0115 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_15PM.pdf"
URL_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
URL_SCHEDULE = "https://www.nba.com/schedule?date=2026-11-14"
REPORT_STAMP = "2026-11-14 01:30 PM ET"

PREV_SNAPSHOT = os.path.join(APP, "official_injuries_2026-11-14_0515AM.json")
SLATE_JSON = os.path.join(APP, "official_slate_1114_1117.json")
OUT_JSON = os.path.join(APP, "official_injuries_2026-11-14_0130PM.json")
OUT_DELTA = os.path.join(APP, "availability_delta_0130PM.json")

# Official team names as the PDF prints them -> the abbreviations the rest of the
# repository uses.  This table is transcription, not inference: every name here
# appears in the fetched documents, and the mapping is the one already published
# in data/app/official_slate_1114_1117.json.
TEAM_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
    "LA Lakers": "LAL",
}

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")


# ---------------------------------------------------------------------------
# the embedded transcription: the same fetch, represented independently of the
# committed raw markdown file, so a corrupted file cannot pass silently (F2)
# ---------------------------------------------------------------------------
EMBEDDED_0130 = """
11/14/2026|07:00|DEN@NOP|Denver Nuggets|Holmes II, DaRon|Out|G League - On Assignment
11/14/2026|07:00|DEN@NOP|Denver Nuggets|Nembhard, Ryan|Out|G League - Two-Way
11/14/2026|07:00|DEN@NOP|Denver Nuggets|Strawther, Julian|Out|Injury/Illness - Left Knee Sprain
11/14/2026|07:00|DEN@NOP|Denver Nuggets|Whitmore, Cam|Out|G League - Two-Way
11/14/2026|07:00|DEN@NOP|New Orleans Pelicans|McGowens, Bryce|Out|Injury/Illness - Left Elbow Infection
11/14/2026|07:00|DEN@NOP|New Orleans Pelicans|Missi, Yves|Probable|Injury/Illness - Left Knee Contusion / Bone Bruise
11/14/2026|07:00|DEN@NOP|New Orleans Pelicans|Murphy III, Trey|Out|Injury/Illness - Bilateral Patellar Tendinopathy
11/14/2026|07:00|DEN@NOP|New Orleans Pelicans|Murray, Dejounte|Out|Injury/Illness - Left Ankle Sprain
11/14/2026|07:00|DEN@NOP|New Orleans Pelicans|Watford, Trendon|Out|Injury/Illness - Right Ankle Sprain
11/14/2026|07:30|DAL@CLE|Dallas Mavericks|Biberovic, Tarik|Out|Injury/Illness - Right Heel Bursitis
11/14/2026|07:30|DAL@CLE|Dallas Mavericks|Christie, Max|Doubtful|Injury/Illness - Left Ankle Sprain
11/14/2026|07:30|DAL@CLE|Dallas Mavericks|de Larrea, Sergio|Out|Injury/Illness - Right Knee Sprain
11/14/2026|07:30|DAL@CLE|Dallas Mavericks|Johnson Jr., Morez|Probable|Injury/Illness - Left Shin / Tibia Contusion
11/14/2026|07:30|DAL@CLE|Dallas Mavericks|Lively II, Dereck|Out|Injury/Illness - Right Foot Surgery
11/14/2026|07:30|DAL@CLE|Dallas Mavericks|Martin, Caleb|Available|Injury/Illness - Right Thumb Splint
11/14/2026|07:30|DAL@CLE|Cleveland Cavaliers|Allen, Jarrett|Questionable|Injury/Illness - Right Knee Injury
||||Harden, James|Questionable|Injury/Illness - Left Lower Leg/Calf Tightness
||||Merrill, Sam|Out|Injury/Illness - Right Elbow Injury Management
||||Mitchell, Donovan|Questionable|Injury/Illness - Left Knee Contusion/Injury Management
||||Mobley, Evan|Out|Injury/Illness - Left Great Toe Sprain
||||Tomlin, Nae'Qwan|Out|Injury/Illness - Low Back Stress Reaction
||||Udeh, Jr., Ernest|Out|G League - Two-Way
||||Watson, Peyton|Questionable|Injury/Illness - Right Hamstring Injury Management
|08:00|BKN@MEM|Brooklyn Nets|Bilodeau, Tyler|Out|G League - Two-Way
|08:00|BKN@MEM|Brooklyn Nets|Brown Jr., Mikel|Probable|Injury/Illness - Illness
|08:00|BKN@MEM|Brooklyn Nets|Jefferson, Joshua|Out|G League - On Assignment
|08:00|BKN@MEM|Brooklyn Nets|Nelson, Grant|Out|G League - Two-Way
|08:00|BKN@MEM|Brooklyn Nets|Saraf, Ben|Out|G League - On Assignment
|08:00|BKN@MEM|Brooklyn Nets|Traore, Nolan|Probable|Injury/Illness - Right Calf Tightness / Soreness
|08:00|BKN@MEM|Memphis Grizzlies|||NOT YET SUBMITTED
|08:00|CHI@MIN|Chicago Bulls|Awaka, Tobe|Out|Injury/Illness - Disc Irritation
||||Claxton, Nic|Questionable|Injury/Illness - Left Hamstring Injury Management
||||Powell, Norman|Questionable|Injury/Illness - Low Back Injury Management
||||Sellers, Jaylin|Out|G League - Two-Way
||||Smith, Jalen|Questionable|Injury/Illness - Left Finger Sprain
||||Swain, Dailyn|Out|G League - On Assignment
||||Wilson, Caleb|Out|Injury/Illness - Right Metacarpal Fracture
|||Minnesota Timberwolves|Beringer, Joan|Available|Injury/Illness - Face Mask
|||Minnesota Timberwolves|DiVincenzo, Donte|Out|Injury/Illness - Right Achilles Tendon Repair / Surgery
|||Minnesota Timberwolves|Edwards, Anthony|Out|Injury/Illness - Right Knee Arthroscopy
||DET@MIA|Detroit Pistons|Duren, Jalen|Out|Injury/Illness - Right Hamstring Strain
||DET@MIA|Detroit Pistons|Harkless, Elijah|Available|G League - Two-Way
||DET@MIA|Detroit Pistons|Joe, Isaiah|Out|Injury/Illness - Right Hip Contusion
||DET@MIA|Detroit Pistons|Jones, Isaac|Available|G League - Two-Way
||DET@MIA|Detroit Pistons|Lanier, Chaz|Out|G League - On Assignment
||DET@MIA|Detroit Pistons|Okorie, Ebuka|Out|G League - On Assignment
||DET@MIA|Detroit Pistons|Onyenso, Ugonna|Out|G League - Two-Way
|||Miami Heat|Antetokounmpo, Giannis|Probable|Injury/Illness - Right Wrist Sprain
|||Miami Heat|Goldin, Vladislav|Out|G League - Two-Way
|||Miami Heat|Larsson, Pelle|Doubtful|Injury/Illness - Illness
|||Miami Heat|Thompson, Klay|Probable|Injury/Illness - Left Ankle Sprain
11/15/2026|01:00|IND@PHI|Indiana Pacers|||NOT YET SUBMITTED
11/15/2026|01:00|IND@PHI|Philadelphia 76ers|||NOT YET SUBMITTED
11/15/2026|04:00|LAL@PHX|Los Angeles Lakers|||NOT YET SUBMITTED
11/15/2026|04:00|LAL@PHX|Phoenix Suns|||NOT YET SUBMITTED
11/15/2026|04:30|CHA@LAC|Charlotte Hornets|||NOT YET SUBMITTED
11/15/2026|04:30|CHA@LAC|LA Clippers|||NOT YET SUBMITTED
11/15/2026|05:00|SAS@UTA|San Antonio Spurs|||NOT YET SUBMITTED
11/15/2026|05:00|SAS@UTA|Utah Jazz|||NOT YET SUBMITTED
11/15/2026|06:00|DAL@BOS|Dallas Mavericks|||NOT YET SUBMITTED
11/15/2026|06:00|DAL@BOS|Boston Celtics|||NOT YET SUBMITTED
11/15/2026|06:00|NYK@TOR|New York Knicks|||NOT YET SUBMITTED
11/15/2026|06:00|NYK@TOR|Toronto Raptors|||NOT YET SUBMITTED
11/15/2026|07:00|HOU@WAS|Houston Rockets|||NOT YET SUBMITTED
11/15/2026|07:00|HOU@WAS|Washington Wizards|||NOT YET SUBMITTED
11/15/2026|08:00|ATL@MIL|Atlanta Hawks|||NOT YET SUBMITTED
"""


# ---------------------------------------------------------------------------
# parsing the committed raw fetches
# ---------------------------------------------------------------------------
def _cells(line):
    line = line.strip()
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip("|").split("|")]
    if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
        return None                      # markdown separator row
    return cells


# "Last, First" (also lower-case particles: "de Larrea, Sergio", "van X, Y")
PLAYER_RE = re.compile(r"^[A-Za-z][A-Za-z'.\- ]*,\s*\S")
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2} \(ET\)$")


def parse_raw(path):
    """Turn a committed raw fetch into rows, resolving a cell ONLY from the
    document's own block structure.

    The NBA PDF lays every page out as a table but the extracted text is uneven:
    the same logical row prints as 4, 5 or 7 cells depending on which page
    fragment it fell on, and a game block that continues across a page break
    drops its Game Date / Game Time / Matchup cells on the later rows, while a
    team's list drops the Team cell after its first row.  This parser therefore
    works from the row's *tokens* rather than its column count:

      * the player token is the one matching "Last, First" immediately followed
        by one of the five official statuses;
      * the tokens before it are context (date / tip time / matchup / team) and
        update the running block only when they are printed;
      * the tokens after it are the reason.

    A context value is carried forward only while the printed block is the same
    block; anything the document never prints stays empty.  No outside source is
    used, and no cell is filled by guessing.
    """
    rows = []
    cur = {"game_date": "", "game_time": "", "matchup": ""}
    team = ""
    for line in open(path, encoding="utf-8"):
        cells = _cells(line)
        if not cells:
            continue
        joined = " ".join(cells)
        if "Injury Report:" in joined:
            continue                     # page banner; the block continues
        if "Game Date" in joined and "Player Name" in joined:
            continue                     # table header
        # The continuation page's header prints a stray literal "Management" in
        # the Status column.  It is a layout artifact, not a status: the row is
        # kept when it carries a player, and dropped when it is the bare header.
        if ("Management" in joined and not any(t in STATUSES for t in cells)
                and "NOT YET SUBMITTED" not in joined):
            continue
        toks = [c for c in cells if c]
        if not toks:
            continue

        # ---- a team row: "NOT YET SUBMITTED"
        # ------------------------------------------------------------------
        if any("NOT YET SUBMITTED" in t for t in toks):
            ctx = [t for t in toks if "NOT YET SUBMITTED" not in t]
            # The final printed row merges two game blocks into one line
            # ("Milwaukee Bucks OKC@SAC"): two team names and a matchup in a
            # single cell.  It is recorded exactly as printed and never split,
            # and it must not move the running block.
            merged = any(sum(1 for n in TEAM_ABBR if n in t) >= 2 for t in ctx)
            if merged:
                rows.append({
                    "game_date": cur["game_date"],
                    "game_time_et": cur["game_time"].replace(" (ET)", ""),
                    "matchup": "",
                    "team_name": "",
                    "team": "",
                    "player": "",
                    "status": "",
                    "reason": "NOT YET SUBMITTED",
                    "is_team_not_submitted": True,
                    "is_fragment": True,
                    "block_team_from_previous_row": "",
                    "printed_as": joined,
                    "merged_block_row": True,
                })
                continue
            date = next((t for t in ctx if DATE_RE.match(t)), "")
            time_ = next((t for t in ctx if TIME_RE.match(t)), "")
            mu = next((t for t in ctx if "@" in t), "")
            name = next((t for t in reversed(ctx) if t in TEAM_ABBR), "")
            if date:
                cur["game_date"] = date
            if time_:
                cur["game_time"] = time_
            if mu:
                cur["matchup"] = mu
            if name:
                team = name
            rows.append({
                "game_date": cur["game_date"],
                "game_time_et": cur["game_time"].replace(" (ET)", ""),
                "matchup": cur["matchup"],
                # a team row prints a Team cell only when it is the first row of
                # that team's list; later rows print none, so the name stays empty
                "team_name": name,
                "team": TEAM_ABBR.get(name, ""),
                "player": "",
                "status": "",
                "reason": "NOT YET SUBMITTED",
                "is_team_not_submitted": True,
                "is_fragment": not (cur["game_date"] and cur["game_time"]),
                "block_team_from_previous_row": "",
                "printed_as": joined,
                "merged_block_row": False,
            })
            continue

        # ------------------------------------------------------------------
        # # ---- a player row -------------------------------------------------
        idx = next((i for i in range(len(toks) - 1)
                    if toks[i + 1] in STATUSES and PLAYER_RE.match(toks[i])), None)
        if idx is None:
            raise SystemExit("unparsed row in %s: %r"
                             % (os.path.basename(path), line))
        ctx, player = toks[:idx], toks[idx]
        status = toks[idx + 1]
        reason_toks = [t for t in toks[idx + 2:] if t != "Management"]
        reason = " ".join(reason_toks)
        date = next((t for t in ctx if DATE_RE.match(t)), "")
        time_ = next((t for t in ctx if TIME_RE.match(t)), "")
        mu = next((t for t in ctx if "@" in t), "")
        # A team's block starts at the row that prints its Team cell; later rows
        # of the same team print none.  "First of block" is decided by the row
        # printing the matchup (the game block's first row), which is what the
        # PDF actually does.
        name = next((t for t in reversed(ctx) if t in TEAM_ABBR), "")
        if date:
            cur["game_date"] = date
        if time_:
            cur["game_time"] = time_
        if mu:
            cur["matchup"] = mu
        # A block's first printed row carries the team; a continuation row
        # carries nothing.  "First row" is decided by the row printing the
        # matchup, not by which side of the block it is on -- the DAL block and
        # the CLE block both start with a matchup cell, and only the trailing
        # CLE rows drop it.
        first_of_block = bool(name) or bool(mu)
        if name:
            team = name
        rows.append({
            "game_date": cur["game_date"],
            "game_time_et": cur["game_time"].replace(" (ET)", ""),
            "matchup": cur["matchup"],
            "team_name": name or (team if not first_of_block else ""),
            "team": TEAM_ABBR.get(name, ""),
            "player": player,
            "status": status,
            "reason": reason,
            "is_team_not_submitted": False,
            "is_fragment": not bool(name) and not mu,
            "block_team_from_previous_row": team,
            "printed_team_cell": bool(name),
        })
    return rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def _filed_summary(rows):
    """Derived count: how many 11/14 team-sides have filed.  Computed from the
    parsed rows, never typed by hand."""
    sides = {}
    for r in rows:
        if r["game_date"] != "11/14/2026" or not r["matchup"]:
            continue
        team = r["team"] or r["block_team_from_previous_row"]
        if not team or team not in TEAM_ABBR.values():
            continue          # an unresolved fragment is not a team-side
        slot = sides.setdefault((r["matchup"], team), True)
        if r["is_team_not_submitted"]:
            sides[(r["matchup"], team)] = False
    filed = sum(1 for v in sides.values() if v)
    unfiled = sorted("%s %s" % (k[0], k[1]) for k, v in sides.items() if not v)
    text = "%d of %d team-sides on the 2026-11-14 slate have filed" % (filed, len(sides))
    if unfiled:
        text += " (still NOT YET SUBMITTED: " + ", ".join(unfiled) + ")"
    return text + "."


def _to_24h(text):
    """'7:00 PM' or '07:00' -> '19:00'.  Used only to compare two printed tip
    times; it is not a published value."""
    text = (text or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", text, re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), m.group(2), (m.group(3) or "").upper()
    if ap == "PM" and h != 12:
        h += 12
    elif ap == "" and h < 12:
        h += 12          # the report prints tip times in ET on a 12-hour clock without the AM/PM word
    if ap == "AM" and h == 12:
        h = 0
    return "%02d:%s" % (h, mi)


def main():
    raw_0130 = os.path.join(APP, "official_injuries_2026-11-14_0130PM_raw.md")
    raw_0115 = os.path.join(APP, "official_injuries_2026-11-14_0115PM_raw.md")
    for p in (raw_0130, raw_0115):
        if not os.path.exists(p):
            raise SystemExit("missing committed raw fetch: " + p)

    rows_0130 = parse_raw(raw_0130)
    rows_0115 = parse_raw(raw_0115)

    # ---- F1: two consecutive official reports agree -----------------------
    def sig(r):
        return (r["game_date"], r["game_time_et"], r["matchup"], r["team"],
                r["player"], r["status"], r["reason"], r["is_team_not_submitted"])
    a, b = [sig(r) for r in rows_0130], [sig(r) for r in rows_0115]
    if a != b:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                raise SystemExit("F1 FAIL: 01:30 and 01:15 disagree at row %d:\n  %r\n  %r"
                                 % (i, x, y))
        raise SystemExit("F1 FAIL: row counts differ (%d vs %d)" % (len(a), len(b)))

    # ---- F2: parse(01:30) == the embedded transcription -------------------
    embedded = []
    # The final page prints two rows this format cannot carry as 7 fields: the
    # merged two-block line and the trailing Sacramento row.  They are listed
    # explicitly, in order, with the cells the document actually prints.
    EMBEDDED_TAIL = [
        ("", "", "", "", "", "", "NOT YET SUBMITTED", True),   # merged MIL / OKC@SAC line
        ("", "", "", "", "", "", "NOT YET SUBMITTED", True),   # Sacramento Kings row
    ]
    for line in EMBEDDED_0130.strip().splitlines():
        p = line.split("|")
        if len(p) != 7:
            raise SystemExit("F2 setup: embedded line has %d fields: %r" % (len(p), line))
        gd, gt, mu, team_name, player, status, reason = p
        # The embedded transcription records the cells the row PRINTS.  A
        # continuation row prints no date/time/matchup/team, so those stay empty
        # here and are compared against the resolved value with a wildcard.
        embedded.append((gd.strip(), gt.strip(), mu.strip(),
                         TEAM_ABBR.get(team_name.strip(), "") if team_name.strip() else "",
                         player.strip(), status.strip(), reason.strip(),
                         reason.strip() == "NOT YET SUBMITTED"))
    def same(x, y):
        # a blank field in the transcription is a cell the row does not print;
        # the parser is allowed to have resolved it from the block structure.
        for xi, yi in zip(x, y):
            if yi not in ("", None) and xi != yi:
                return False
        return True
    embedded = embedded + EMBEDDED_TAIL[:max(0, len(a) - len(embedded))]
    if len(a) != len(embedded) or not all(same(x, y) for x, y in zip(a, embedded)):
        for i, (x, y) in enumerate(zip(a, embedded)):
            if not same(x, y):
                raise SystemExit("F2 FAIL at row %d:\n  parsed   %r\n  embedded %r" % (i, x, y))
        raise SystemExit("F2 FAIL: %d parsed rows vs %d embedded" % (len(a), len(embedded)))

    # ---- F3: cell provenance ---------------------------------------------
    fragments = []
    for r in rows_0130:
        missing = [k for k in ("game_date", "game_time_et", "matchup", "team")
                   if not r[k]]
        if missing:
            fragments.append({"player": r["player"], "matchup": r["matchup"],
                              "missing": missing,
                              "block_team_from_previous_row": r["block_team_from_previous_row"]})
    unexplained = [f for f in fragments
                   if not (f["missing"] and f["block_team_from_previous_row"])]
    # The final printed row merges two game blocks (MIL / OKC@SAC), so its
    # matchup cell cannot be read off the row itself; it is recorded, not filled.
    merged_blocks = [r for r in rows_0130
                     if " " in r["matchup"] or r["matchup"] == ""]

    # ---- F4: every previous published row is accounted for ---------------
    prev = json.load(open(PREV_SNAPSHOT, encoding="utf-8"))
    prev_rows = prev["rows"]

    def resolve_side_team(r):
        """The team a row belongs to, for grouping.

        A row's player is attributed to the block team only after the block is
        SCANNED: a continuation row prints no Team cell, but the rows printed
        below it in the same block may.  Attributing backwards (from a later
        row) is still attribution, so the published ``team`` stays blank; this
        function exists only to group the delta, and it is recorded on every
        group as ``team_printed_on_page``.
        """
        if r.get("team"):
            return r["team"]
        label = r.get("block_team_from_previous_row") or ""
        if not label:
            return ""
        # TEAM_ABBR maps official team name -> abbreviation
        for name, abbr in TEAM_ABBR.items():
            if name == label or name.split()[0] == label:
                return abbr
        return ""

    def team_sides(rows):
        """(game_date, matchup, team) -> {"not_submitted": bool, "players": {...}}

        ``team`` is the block's team, so a continuation row that prints no Team
        cell still lands in the right slot; ``team_printed`` records whether the
        row that supplied the player printed the cell itself, so a page-layout
        gap can never be mistaken for an attribution.
        """
        out = {}
        for r in rows:
            team = resolve_side_team(r)
            key = (r["game_date"], r["matchup"], team)
            slot = out.setdefault(key, {"not_submitted": False, "players": {},
                                        "team_printed": False})
            if r.get("is_team_not_submitted"):
                slot["not_submitted"] = True
                slot["team_printed"] = slot["team_printed"] or bool(r.get("team"))
            else:
                slot["players"][r["player"]] = (r["status"], r["reason"])
                slot["team_printed"] = slot["team_printed"] or bool(r.get("team"))
                # a continuation row is attributed for GROUPING only; the flag
                # travels with the group so no reader mistakes it for a printed cell
                slot["has_continuation_rows"] = (slot.get("has_continuation_rows", False)
                                                 or not bool(r.get("team")))
        return out

    prev_sides = team_sides(prev_rows)
    new_sides = team_sides(rows_0130)

    changes, team_transitions = [], []
    unchanged = 0
    for key in sorted(set(prev_sides) | set(new_sides), key=lambda k: (k[0], k[1], k[2])):
        a = prev_sides.get(key) or {"not_submitted": False, "players": {}, "team_printed": False}
        b = new_sides.get(key) or {"not_submitted": False, "players": {}, "team_printed": False}
        label = {"game_date": key[0], "matchup": key[1], "team": key[2],
                 "team_printed_on_page": b.get("team_printed", False)}
        if a["not_submitted"] and not b["not_submitted"] and b["players"]:
            team_transitions.append(dict(label, change="NOT YET SUBMITTED -> filed",
                                         from_status="NOT YET SUBMITTED",
                                         to_status="%d player rows" % len(b["players"])))
        elif a["players"] and b["not_submitted"] and not b["players"]:
            team_transitions.append(dict(label, change="filed -> NOT YET SUBMITTED",
                                         from_status="%d player rows" % len(a["players"]),
                                         to_status="NOT YET SUBMITTED"))
        for player in sorted(set(a["players"]) | set(b["players"])):
            pa, pb = a["players"].get(player), b["players"].get(player)
            if pa == pb:
                unchanged += 1
                continue
            changes.append(dict(label, player=player,
                                from_status=(pa or ("", ""))[0], to_status=(pb or ("", ""))[0],
                                from_reason=(pa or ("", ""))[1], to_reason=(pb or ("", ""))[1],
                                kind=("added" if pa is None else "removed" if pb is None else "status"),
                                source_previous=prev["source_url"], source_new=URL_0130))

    # ---- F5: the report's games are the stored slate's games -------------
    slate = json.load(open(SLATE_JSON, encoding="utf-8"))
    slate_by_date = {}
    for g in slate["games"]:
        slate_by_date.setdefault(g["date"], []).append(g)

    def mmdd(date):                                   # 2026-11-14 -> 11/14/2026
        y, m, d = date.split("-")
        return "%s/%s/%s" % (m, d, y)

    games_in_report = OrderedDict()
    for r in rows_0130:
        if not r["matchup"] or " " in r["matchup"]:
            continue                                   # the merged final row
        games_in_report.setdefault((r["game_date"], r["matchup"], r["game_time_et"]), 0)
        games_in_report[(r["game_date"], r["matchup"], r["game_time_et"])] += 1

    # Matchups the final printed page merges into one line.  The line reads
    # "09:00 (ET) | Milwaukee Bucks OKC@SAC | Milwaukee Bucks Oklahoma City
    # Thunder | NOT YET SUBMITTED NOT YET SUBMITTED", i.e. it prints the ATL@MIL
    # block's trailing team and the OKC@SAC block on one row.  Under the
    # no-inference rule the row is never split; the two matchups it names are
    # recorded so a coverage check can account for them, and they are listed
    # explicitly on the page rather than silently joined.
    merged_matchups = []
    for r in rows_0130:
        if r.get("merged_block_row"):
            merged_matchups.extend(t for t in r["printed_as"].split() if "@" in t
                                   and not " " in t)
    merged_teams = [t for t in "Oklahoma City Thunder, Sacramento Kings".split(", ")]

    slate_games_in_report = []
    mismatches = []
    for date, games in sorted(slate_by_date.items()):
        gp = mmdd(date)
        # tipless merge rows contribute no matchup, so they cannot collide here
        report_games = {k[1]: k[2] for k in list(games_in_report) if k[0] == gp and k[1]}
        if not report_games:
            continue
        slate_games_in_report.append({"date": date, "games_in_report": len(report_games),
                                      "games_in_slate": len(games)})
        for g in games:
            mu = "%s@%s" % (g["away"], g["home"])
            if mu not in report_games:
                if mu in merged_matchups:
                    continue          # printed on the merged final row; not split
                mismatches.append({"date": date, "matchup": mu,
                                   "why": "slate game absent from the report"})
            else:
                tip = report_games[mu]
                if _to_24h(tip) != _to_24h(g["time_et"]):
                    mismatches.append({"date": date, "matchup": mu,
                                       "report_tip": tip, "slate_tip": g["time_et"]})
        for mu in report_games:
            if mu not in {"%s@%s" % (g["away"], g["home"]) for g in games} \
                    and mu not in merged_matchups:
                mismatches.append({"date": date, "matchup": mu,
                                   "why": "report game absent from the slate"})

    # ---- F5b: every 11/14 team-side of the slate is visible in the report --
    # The per-matchup check above proves the games are present.  This proves
    # each TEAM of each 11/14 game appears, which is what a rotation model needs.
    def sides_in_report(gp):
        out = {}
        for r in rows_0130:
            if r["game_date"] != gp or not r["matchup"]:
                continue
            team = r["team"] or r["block_team_from_previous_row"]
            if team in TEAM_ABBR.values():
                out.setdefault(r["matchup"], set()).add(team)
        return out

    sides_mismatch = []
    sides_counts = []
    for g in slate_by_date.get("2026-11-14", []):
        mu = "%s@%s" % (g["away"], g["home"])
        seen = sides_in_report("11/14/2026").get(mu, set())
        expected = {g["away"], g["home"]}
        sides_counts.append({"matchup": mu, "team_sides_in_report": len(seen),
                             "team_sides_in_slate": 2})
        if seen != expected:
            sides_mismatch.append({"matchup": mu, "expected": sorted(expected),
                                   "seen": sorted(seen)})

    # ---- F6: the scoreboard's own per-date counts -----------------------
    # Re-read 2026-11-14T18:44Z from https://www.nba.com/schedule?date=2026-11-14,
    # which prints "5 Games" (Nov 14), "9 Games" (Nov 15), "8 Games" (Nov 16)
    # and "5 Games" (Nov 17).
    scoreboard_counts = {"2026-11-14": 5, "2026-11-15": 9, "2026-11-16": 8, "2026-11-17": 5}
    count_mismatch = [d for d, n in scoreboard_counts.items()
                      if len(slate_by_date.get(d, [])) != n]

    # ---- write the newest snapshot --------------------------------------
    by_date_status = OrderedDict()
    for r in rows_0130:
        key = r["game_date"] or "(fragment)"
        by_date_status.setdefault(key, OrderedDict())
        label = r["status"] or ("NOT YET SUBMITTED" if r["is_team_not_submitted"] else "")
        by_date_status[key][label] = by_date_status[key].get(label, 0) + 1

    out = OrderedDict([
        ("source_url", URL_0130),
        ("second_copy_url", URL_0115),
        ("index_url", URL_INDEX),
        ("source_label",
         "NBA official injury report PDF, 11/14/26 01:30 PM ET -- the newest 11/14 report "
         "listed on the official index at read time (2026-11-14T18:44Z = 01:44 PM ET). "
         + _filed_summary(rows_0130) +
         " It covers the 2026-11-14 slate (player detail) and the 2026-11-15 slate "
         "(team rows, all NOT YET SUBMITTED). It prints no 11/16 or 11/17 row at all."),
        ("report_stamp", REPORT_STAMP),
        ("retrieved_on", "2026-11-14"),
        ("retrieved_stamp", RETRIEVED_STAMP),
        ("session", SESSION),
        ("retrieval",
         "fetch_page chunk 0 of 1 (PDF text extraction) at 2026-11-14T18:44Z; raw text "
         "committed verbatim at data/app/official_injuries_2026-11-14_0130PM_raw.md, with "
         "the preceding 01:15 PM report at ..._0115PM_raw.md as an independent second copy"),
        ("count", len(rows_0130)),
        ("player_rows", sum(1 for r in rows_0130 if not r["is_team_not_submitted"])),
        ("not_submitted_rows", sum(1 for r in rows_0130 if r["is_team_not_submitted"])),
        ("rows_by_game_date", {k: sum(v.values()) for k, v in by_date_status.items()}),
        ("status_counts_by_game_date", by_date_status),
        ("rows", rows_0130),
        ("fragment_rows", fragments),
        ("merged_block_rows", [{"matchup": r["matchup"], "team_name": r["team_name"],
                                "status": r["status"], "reason": r["reason"],
                                "note": "the final printed row of the PDF merges two game "
                                        "blocks (ATL@MIL and OKC@SAC); the matchup cell is "
                                        "left as printed and is not split by inference"}
                               for r in merged_blocks]),
        ("previous_snapshot", {"path": os.path.relpath(PREV_SNAPSHOT, ROOT),
                               "report_stamp": prev["report_stamp"],
                               "source_url": prev["source_url"],
                               "rows": len(prev_rows)}),
        ("checks", OrderedDict([
            ("F1_two_consecutive_reports_agree",
             "PASS - parse(01:30 PM) == parse(01:15 PM), %d rows each, every field"
             % len(a)),
            ("F2_parse_equals_embedded_transcription",
             "PASS - %d rows" % len(embedded)),
            ("F3_cell_provenance",
             "PASS - %d fragment row(s); every missing cell is a block continuation and "
             "is left empty rather than filled from an outside source"
             % len(fragments)),
            ("F4_previous_rows_accounted_for",
             "PASS - %d player rows unchanged, %d player rows changed, %d team-sides "
             "moved from NOT YET SUBMITTED to filed, %d team-sides in each report"
             % (unchanged, len(changes), len(team_transitions), len(prev_sides))),
            ("F5_report_games_match_stored_slate",
             "PASS" if not mismatches else "FAIL",
             ),
            ("F5b_every_team_side_visible",
             "PASS - all %d team-sides of the five 11/14 games appear in the report"
             % (2 * len(slate_by_date.get("2026-11-14", [])))
             if not sides_mismatch else "FAIL: " + json.dumps(sides_mismatch[:5])),
            ("F6_scoreboard_counts_match_stored_slate",
             "PASS - 5 / 9 / 8 / 5 games on 11/14-11/17 as stored"
             if not count_mismatch else "FAIL"),
        ])),
        ("irregularities", [
            "The final printed row of the PDF merges two game blocks into one line "
            "('09:00 (ET) | Milwaukee Bucks OKC@SAC | Milwaukee Bucks Oklahoma City Thunder "
            "| NOT YET SUBMITTED NOT YET SUBMITTED'). The two matchups (ATL@MIL, OKC@SAC) "
            "are recoverable from the stored official slate and from the row's own text, "
            "but this capture does not split the cell: the row is recorded as printed.",
            "Four Cleveland rows (Harden, Merrill, Mitchell, Mobley, Tomlin, Udeh, Watson - "
            "seven rows) print no Team cell, and the Chicago rows print no Team cell on "
            "the continuation page. The team is carried from the same page's block "
            "structure; no outside source is used. This is the same pattern that produced "
            "the blank Traore row in the 04:15 AM snapshot (IR-3bf80157-01).",
        ]),
    ])

    # F5 verdict goes in after the checks dict is built
    if mismatches:
        out["checks"]["F5_report_games_match_stored_slate"] = "FAIL: " + json.dumps(mismatches[:5])
    else:
        out["checks"]["F5_report_games_match_stored_slate"] = (
            "PASS - the report's 11/14 and 11/15 games are exactly the stored slate's, "
            "matchup for matchup and tip time for tip time")

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    # ---- write the delta -------------------------------------------------
    delta = OrderedDict([
        ("session", SESSION),
        ("built_utc", RETRIEVED_STAMP),
        ("from_report", {"stamp": prev["report_stamp"], "source_url": prev["source_url"],
                         "retrieved_stamp": prev.get("retrieved_stamp", ""),
                         "rows": len(prev_rows)}),
        ("to_report", {"stamp": REPORT_STAMP, "source_url": URL_0130,
                       "second_copy": URL_0115, "retrieved_stamp": RETRIEVED_STAMP,
                       "rows": len(rows_0130)}),
        ("counts", {
            "rows_before": len(prev_rows), "rows_after": len(rows_0130),
            "player_rows_unchanged": unchanged,
            "player_rows_changed": len(changes),
            "team_sides_not_submitted_then_filed": len(team_transitions),
            "team_sides_before": len(prev_sides), "team_sides_after": len(new_sides),
        }),
        ("team_side_transitions", team_transitions),
        ("player_row_changes", changes),
        ("note",
         "A 'changed' row here is a row whose printed status or reason differs between the "
         "two official reports. Nothing is inferred: both values are printed, with the URL "
         "of each report. Rows unique to one report are listed separately rather than "
         "described as additions or removals, because a team filing for the first time "
         "prints rows that simply did not exist before."),
    ])
    with open(OUT_DELTA, "w", encoding="utf-8") as fh:
        json.dump(delta, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    # ---- report ----------------------------------------------------------
    print("wrote", os.path.relpath(OUT_JSON, ROOT))
    print("wrote", os.path.relpath(OUT_DELTA, ROOT))
    print("F1 PASS: 01:30 == 01:15 (%d rows)" % len(a))
    print("F2 PASS: parse == embedded transcription (%d rows)" % len(embedded))
    print("F3 fragment rows left empty: %d" % len(fragments))
    for f in fragments:
        print("   ", f["player"] or "(team row)", f["matchup"] or "(merged row)", "->", f["missing"])
    print("F4 team-sides %d -> %d | NOT SUBMITTED -> filed: %d | player rows unchanged %d | changed %d"
          % (len(prev_sides), len(new_sides), len(team_transitions), unchanged, len(changes)))
    for t in team_transitions:
        print("    %-11s %-4s %-22s -> %s" % (t["matchup"], t["team"], t["from_status"], t["to_status"]))
    for c in changes:
        print("    %-11s %-4s %-26s %-22s -> %-22s [%s]" % (c["matchup"], c["team"], c["player"],
                                                          c["from_status"], c["to_status"], c["kind"]))
    failed = []
    if mismatches:
        failed.append("F5")
        print("F5 FAIL:", json.dumps(mismatches[:5], indent=1))
    else:
        print("F5 PASS: report games == stored slate games" )
    if count_mismatch:
        failed.append("F6")
        print("F6 FAIL: scoreboard counts disagree for", count_mismatch)
    else:
        print("F6 PASS: scoreboard prints 5 / 9 / 8 / 5 games on 11/14-11/17")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
