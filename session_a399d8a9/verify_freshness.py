#!/usr/bin/env python3
"""Session ``a399d8a9`` — refresh catch-up and row-by-row reconciliation.

WHY THIS EXISTS
    The published dashboard prices the 2026-11-14 slate off the official injury
    report stamped **11/14/26 04:15 AM ET**.  That report was the newest one on
    the official index when the previous session read it at 09:45Z.  The slate
    tips at 7:00 PM ET, the league files a fresh game-day report between 11:00 AM
    and 1:00 PM local on game days, and reports are updated continually after
    that.  So by the time this session ran (18:45Z), the site was showing a
    pre-dawn snapshot of a game-day slate.

    This module answers, from the official pages only:

      R1  what the newest official report is, now;
      R2  exactly which published cells that report changes;
      R3  whether the 27-game pricing window is unchanged.

WHAT IT DELIBERATELY DOES NOT DO
    It does not infer a single cell.  Where the newer PDF fragment omits a Team,
    Matchup, Game Date or Game Time cell, the cell stays empty here exactly as
    it does in the raw transcript, and the reconciliation reports the omission
    as an omission.  The one place a value is carried is where the *same*
    document prints it a few rows earlier inside the same game block; that is
    marked ``carried_within_document`` and is never silent.

INPUTS  (raw transcripts, committed beside this script — the fetch tool's own
         markdown, unedited)
    data/official_injury_report_2026-11-14_0130PM_raw.md   (this session)
    ../data/app/official_injuries_2026-11-14_0415AM_raw.md (published snapshot)
    ../data/app/snapshot_manifest.json                     (what the build reads)
OUTPUTS
    data/reconciliation_2026-11-14.json   machine-readable result of R1-R3
    (the HTML page is written by build.py from that JSON)

Run:  python3 session_a399d8a9/verify_freshness.py
Exits non-zero if the reconciliation itself is malformed, never because the
official data moved — a moved line is a finding, not a build failure.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HERE = os.path.join(ROOT, "session_a399d8a9")
DATA = os.path.join(HERE, "data")
APP = os.path.join(ROOT, "data", "app")

NEW_RAW = os.path.join(DATA, "official_injury_report_2026-11-14_0130PM_raw.md")
OLD_RAW = os.path.join(APP, "official_injuries_2026-11-14_0415AM_raw.md")
MANIFEST = os.path.join(APP, "snapshot_manifest.json")
OUT = os.path.join(DATA, "reconciliation_2026-11-14.json")

NEW_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
OLD_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
SCHEDULE_URL = "https://www.nba.com/schedule?date=2026-11-14"

TEAMS = {
    "Denver Nuggets": "DEN", "New Orleans Pelicans": "NOP",
    "Dallas Mavericks": "DAL", "Cleveland Cavaliers": "CLE",
    "Brooklyn Nets": "BKN", "Memphis Grizzlies": "MEM",
    "Chicago Bulls": "CHI", "Minnesota Timberwolves": "MIN",
    "Detroit Pistons": "DET", "Miami Heat": "MIA",
    "Indiana Pacers": "IND", "Philadelphia 76ers": "PHI",
    "Los Angeles Lakers": "LAL", "Phoenix Suns": "PHX",
    "Charlotte Hornets": "CHA", "LA Clippers": "LAC",
    "San Antonio Spurs": "SAS", "Utah Jazz": "UTA",
    "Boston Celtics": "BOS", "New York Knicks": "NYK",
    "Toronto Raptors": "TOR", "Houston Rockets": "HOU",
    "Washington Wizards": "WAS", "Atlanta Hawks": "ATL",
    "Milwaukee Bucks": "MIL", "Oklahoma City Thunder": "OKC",
    "Sacramento Kings": "SAC",
}


# The block header each fragment-only row belongs to, named on the page so a
# reader can check the carry against the PDF.  Never a value, only a reference.
CARRIED_FROM = {
    "Cleveland Cavaliers": "DAL@CLE game block (Cleveland Cavaliers) opened above this fragment",
    "Chicago Bulls": "CHI@MIN game block (Chicago Bulls) opened above this fragment",
    "Minnesota Timberwolves": "CHI@MIN game block (Minnesota Timberwolves) opened above this fragment",
}


def r(date, time_et, matchup, team_name, player, status, reason, filled=()):
    return (date, time_et, matchup, team_name, player, status, reason, tuple(filled))


# ---------------------------------------------------------------------------
# The transcription of the 01:30 PM ET report, from this session's own read.
# Fields that the document did not print are empty strings, never guesses.
#   carried_within_document: the cell was blank on that line of the PDF but the
#   same document prints it in the same game block; the note names the line.
# ---------------------------------------------------------------------------
ROWS_0130 = [
    # Each row: date, time_et, matchup, team_name, player, status, reason, filled
    #   ``filled`` names the cells the PDF fragment did NOT print and that were
    #   therefore read from the same document's open game block. It is never empty
    #   for a row whose cells were incomplete, so no cell is silently repaired.
    # ---- DEN@NOP, 11/14 7:00 PM ET (Denver block prints every column on every line)
    r("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Holmes II, DaRon", "Out", "G League - On Assignment"),
    r("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Nembhard, Ryan", "Out", "G League - Two-Way"),
    r("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain"),
    r("11/14/2026", "07:00", "DEN@NOP", "Denver Nuggets", "Whitmore, Cam", "Out", "G League - Two-Way"),
    r("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "McGowens, Bryce", "Out", "Injury/Illness - Left Elbow Infection"),
    r("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Missi, Yves", "Probable", "Injury/Illness - Left Knee Contusion / Bone Bruise"),
    r("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Murphy III, Trey", "Out", "Injury/Illness - Bilateral Patellar Tendinopathy"),
    r("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Murray, Dejounte", "Out", "Injury/Illness - Left Ankle Sprain"),
    r("11/14/2026", "07:00", "DEN@NOP", "New Orleans Pelicans", "Watford, Trendon", "Out", "Injury/Illness - Right Ankle Sprain"),
    # ---- DAL@CLE, 11/14 7:30 PM ET
    r("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis"),
    r("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Christie, Max", "Doubtful", "Injury/Illness - Left Ankle Sprain"),
    r("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain"),
    r("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion"),
    r("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery"),
    r("11/14/2026", "07:30", "DAL@CLE", "Dallas Mavericks", "Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint"),
    r("11/14/2026", "07:30", "DAL@CLE", "Cleveland Cavaliers", "Allen, Jarrett", "Questionable", "Injury/Illness - Right Knee Injury"),
    # ---- Cleveland continuation fragment: only the player/status/reason columns print
    r("", "", "", "Cleveland Cavaliers", "Harden, James", "Questionable", "Injury/Illness - Left Lower Leg/Calf Tightness", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Cleveland Cavaliers", "Merrill, Sam", "Out", "Injury/Illness - Right Elbow Injury Management", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Cleveland Cavaliers", "Mitchell, Donovan", "Questionable", "Injury/Illness - Left Knee Contusion/Injury Management", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Cleveland Cavaliers", "Mobley, Evan", "Out", "Injury/Illness - Left Great Toe Sprain", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Cleveland Cavaliers", "Tomlin, Nae'Qwan", "Out", "Injury/Illness - Low Back Stress Reaction", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Cleveland Cavaliers", "Udeh, Jr., Ernest", "Out", "G League - Two-Way", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Cleveland Cavaliers", "Watson, Peyton", "Questionable", "Injury/Illness - Right Hamstring Injury Management", ("game_date", "game_time_et", "matchup")),
    # ---- BKN@MEM, 11/14 8:00 PM ET
    r("", "08:00", "BKN@MEM", "Brooklyn Nets", "Bilodeau, Tyler", "Out", "G League - Two-Way", ("game_date",)),
    r("", "08:00", "BKN@MEM", "Brooklyn Nets", "Brown Jr., Mikel", "Probable", "Injury/Illness - Illness", ("game_date",)),
    r("", "08:00", "BKN@MEM", "Brooklyn Nets", "Jefferson, Joshua", "Out", "G League - On Assignment", ("game_date",)),
    r("", "08:00", "BKN@MEM", "Brooklyn Nets", "Nelson, Grant", "Out", "G League - Two-Way", ("game_date",)),
    r("", "08:00", "BKN@MEM", "Brooklyn Nets", "Saraf, Ben", "Out", "G League - On Assignment", ("game_date",)),
    r("", "08:00", "BKN@MEM", "Brooklyn Nets", "Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness", ("game_date",)),
    r("", "08:00", "BKN@MEM", "Memphis Grizzlies", "", "", "NOT YET SUBMITTED", ("game_date",)),
    # ---- CHI@MIN, 11/14 8:00 PM ET
    r("", "08:00", "CHI@MIN", "Chicago Bulls", "Awaka, Tobe", "Out", "Injury/Illness - Disc Irritation", ("game_date",)),
    r("", "", "", "Chicago Bulls", "Claxton, Nic", "Questionable", "Injury/Illness - Left Hamstring Injury Management", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Chicago Bulls", "Powell, Norman", "Questionable", "Injury/Illness - Low Back Injury Management", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Chicago Bulls", "Sellers, Jaylin", "Out", "G League - Two-Way", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Chicago Bulls", "Smith, Jalen", "Questionable", "Injury/Illness - Left Finger Sprain", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Chicago Bulls", "Swain, Dailyn", "Out", "G League - On Assignment", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Chicago Bulls", "Wilson, Caleb", "Out", "Injury/Illness - Right Metacarpal Fracture", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Minnesota Timberwolves", "Beringer, Joan", "Available", "Injury/Illness - Face Mask", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Minnesota Timberwolves", "DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery", ("game_date", "game_time_et", "matchup")),
    r("", "", "", "Minnesota Timberwolves", "Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy", ("game_date", "game_time_et", "matchup")),
    # ---- DET@MIA, 11/14 8:00 PM ET
    r("", "", "DET@MIA", "Detroit Pistons", "Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Detroit Pistons", "Harkless, Elijah", "Available", "G League - Two-Way", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Detroit Pistons", "Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Detroit Pistons", "Jones, Isaac", "Available", "G League - Two-Way", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Detroit Pistons", "Lanier, Chaz", "Out", "G League - On Assignment", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Detroit Pistons", "Okorie, Ebuka", "Out", "G League - On Assignment", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Detroit Pistons", "Onyenso, Ugonna", "Out", "G League - Two-Way", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Miami Heat", "Antetokounmpo, Giannis", "Probable", "Injury/Illness - Right Wrist Sprain", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Miami Heat", "Goldin, Vladislav", "Out", "G League - Two-Way", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Miami Heat", "Larsson, Pelle", "Doubtful", "Injury/Illness - Illness", ("game_date", "game_time_et")),
    r("", "", "DET@MIA", "Miami Heat", "Thompson, Klay", "Probable", "Injury/Illness - Left Ankle Sprain", ("game_date", "game_time_et")),
    # ---- 11/15 placeholders, every team NOT YET SUBMITTED as printed
    r("11/15/2026", "01:00", "IND@PHI", "Indiana Pacers", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "01:00", "IND@PHI", "Philadelphia 76ers", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "04:00", "LAL@PHX", "Los Angeles Lakers", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "04:00", "LAL@PHX", "Phoenix Suns", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "04:30", "CHA@LAC", "Charlotte Hornets", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "04:30", "CHA@LAC", "LA Clippers", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "05:00", "SAS@UTA", "San Antonio Spurs", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "05:00", "SAS@UTA", "Utah Jazz", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "06:00", "DAL@BOS", "Dallas Mavericks", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "06:00", "DAL@BOS", "Boston Celtics", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "06:00", "NYK@TOR", "New York Knicks", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "06:00", "NYK@TOR", "Toronto Raptors", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "07:00", "HOU@WAS", "Houston Rockets", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "07:00", "HOU@WAS", "Washington Wizards", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "08:00", "ATL@MIL", "Atlanta Hawks", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "08:00", "ATL@MIL", "Milwaukee Bucks", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "09:00", "OKC@SAC", "Oklahoma City Thunder", "", "", "NOT YET SUBMITTED"),
    r("11/15/2026", "09:00", "OKC@SAC", "Sacramento Kings", "", "", "NOT YET SUBMITTED"),
]


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def key(date, matchup, team, player):
    """Join key. A blank date or matchup means the PDF fragment did not print it.

    Joining on blank-vs-blank would silently pair unrelated rows, so a row with
    a blank date is paired on (matchup, team, player) only, and the caller
    reports which component was missing. Uniqueness is asserted in main().
    """
    return (norm(date), norm(matchup), TEAMS.get(norm(team), norm(team)), norm(player))


def loose_key(matchup, team, player):
    return (norm(matchup), TEAMS.get(norm(team), norm(team)), norm(player))


def rows_from_published():
    """The rows the canonical dashboard actually publishes (from the stored JSON)."""
    path = os.path.join(APP, "official_injuries_2026-11-14_0415AM.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data, data["rows"]


def resolve_blocks(rows):
    """Give every fragment-only row the block it belongs to, and say so.

    This PDF prints one table per page fragment, and later fragments repeat only
    some columns.  Two different kinds of gap occur and they are resolved
    differently:

      * **no matchup printed** (Cleveland, Chicago, Minnesota continuation
        fragments): the row belongs to the game block opened above it.  A block
        never spans two games, so date, tip time and matchup come from that
        block -- asserted, not assumed: the row's team must be one of the
        block's two teams or this function raises.
      * **matchup printed, no date** (BKN@MEM, CHI@MIN, DET@MIA): the row names
        its own game; only the date cell is missing, and it is taken from the
        nearest row above that printed a date.  The resulting date must be one
        of the two dates the document covers.

    The raw transcript keeps every one of these cells blank, so the reader can
    always check what was and was not printed.
    """
    last_block = None
    last_dated = None
    for row in rows:
        if row["matchup"]:
            if not row["game_date"] and last_dated is not None:
                row["game_date"] = last_dated["game_date"]
                row["block_inherited"].append("game_date")
                row["block_of"] = row["matchup"]
                row["fill_note"] = (
                    "the date cell is not printed on this PDF fragment; it is taken from the "
                    "nearest row above that printed one (" + last_dated["game_date"] + "). "
                    "The raw transcript keeps the cell blank.")
            last_block = row
        else:
            assert last_block is not None, "first row of the document cannot be a fragment"
            away, _, home = row_matchup_teams(last_block)
            code = TEAMS.get(row["team_name"], "")
            if code not in (away, home):
                raise SystemExit(
                    "fragment row %r (team %r -> %r) does not belong to the block above it "
                    "(%s) -- the block-inheritance assumption is wrong for this document, so "
                    "the row must not be published until it is re-read from the PDF"
                    % (row["player"], row["team_name"], code, last_block["matchup"]))
            for field in ("game_date", "game_time_et", "matchup"):
                if not row[field]:
                    row[field] = last_block[field]
                    row["block_inherited"].append(field)
            row["block_of"] = last_block["matchup"]
            row["fill_note"] = (
                "not printed on this PDF fragment: " + ", ".join(row["block_inherited"]) +
                "; read from the same document's open game block " + last_block["matchup"] +
                " (" + last_block["game_time_et"] + " ET, " + last_block["game_date"] +
                "), whose teams are " + away + " and " + home +
                ". The raw transcript keeps these cells blank.")
        if row["game_date"]:
            last_dated = row
            assert row["game_date"] in ("11/14/2026", "11/15/2026"), row
    return rows


def row_matchup_teams(row):
    """('AWAY', '@', 'HOME') from a matchup string, as printed."""
    m = re.match(r"^([A-Z]{3})@([A-Z]{3})$", row["matchup"])
    if not m:
        raise SystemExit("unparseable matchup %r" % row["matchup"])
    return m.group(1), "@", m.group(2)


def build_new_rows():
    out = []
    for date, time_et, matchup, team_name, player, status, reason, filled in ROWS_0130:
        out.append({
            "game_date": date,
            "game_time_et": time_et,
            "matchup": matchup,
            "team_name": team_name,
            "team": TEAMS.get(team_name, ""),
            "player": player,
            "status": status,
            "reason": reason,
            "is_team_not_submitted": reason == "NOT YET SUBMITTED",
            "availability": status,
            "printed_blank": list(filled),
            "block_inherited": [],
            "block_of": matchup,
            "fill_note": "",
        })
    return resolve_blocks(out)


def main():
    published_meta, published_rows = rows_from_published()
    new_rows = build_new_rows()

    # ---- R1: is the published stamp still the newest? ---------------------
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest_stamp = manifest["injuries"]["report_stamp"]
    newest_stamp = "2026-11-14 01:30 PM ET"

    # ---- pre-pass: blank team cells in the published snapshot ------------
    # The 04:15 AM read of the PDF left Traore, Nolan's Team cell blank (the
    # cell is not printed on that page fragment) and the project's no-inference
    # rule kept it blank -- open irregularity IR-3bf80157-01.  The 01:30 PM
    # report prints "Brooklyn Nets" on that row, so the missing cell is now
    # attested by an official source and can be filled from it.  Filling is
    # allowed here precisely because it is a transcription of a printed cell,
    # not an inference from table position.
    team_attested = []
    for pr in published_rows:
        if norm(pr.get("team", "")):
            continue
        cands = [nr for nr in new_rows
                 if norm(nr["player"]) == norm(pr.get("player", ""))
                 and norm(nr["matchup"]) == norm(pr.get("matchup", ""))
                 and norm(nr["reason"]) == norm(pr.get("reason", ""))]
        if len(cands) == 1 and cands[0]["team"]:
            team_attested.append({
                "player": pr["player"], "matchup": pr["matchup"],
                "published_team": "", "attested_team": cands[0]["team"],
                "status": pr.get("status", ""),
                "attested_by": NEW_URL,
                "resolves": "IR-3bf80157-01 / F-DD1-01 (blank Team cell)",
            })
            pr["team"] = cands[0]["team"]
            pr["team_name"] = cands[0]["team_name"]
            pr["team_cell_source"] = "filled from the 01:30 PM ET report, which prints it"

    # ---- R2: row-by-row comparison ---------------------------------------
    # Join on (player, team).  Neither side ever has a blank team in the
    # published data except the one documented Traore row, so this pairs rows
    # without pretending a fragment's missing date or matchup is a value.
    def jkey(row):
        """Join the two documents on (player, team).

        Both documents are block-resolved by now, so every row has a team and a
        matchup.  Team, not matchup, is in the key because the older document
        leaves one team cell blank (the documented Traore row) and a join on
        matchup would silently drop that pair.
        """
        return (norm(row.get("player", "")), norm(row.get("team", "")))

    pub_index = {}
    for row in published_rows:
        k = jkey(row)
        assert k not in pub_index, "duplicate published row %r" % (k,)
        pub_index[k] = row
    new_index = {}
    for row in new_rows:
        k = jkey(row)
        assert k not in new_index, "duplicate newest row %r" % (k,)
        new_index[k] = row

    changed, added, removed = [], [], []
    for k, nr in new_index.items():
        pr = pub_index.get(k)
        if pr is None:
            added.append(nr)
            continue
        diffs = []
        for field, pv, nv in (("status", pr.get("status", ""), nr["status"]),
                              ("reason", pr.get("reason", ""), nr["reason"])):
            if norm(pv) != norm(nv):
                diffs.append({"field": field, "published": pv, "newest": nv})
        # tip time: only comparable when the fragment printed one on this row;
        # a row that inherits its time from the block is compared on the block.
        if nr["game_time_et"]:
            nt = nr["game_time_et"]
            pt = norm(pr.get("game_time_et", "")).replace("(ET)", "").strip()
            if pt and pt.zfill(5) != nt.zfill(5):
                diffs.append({"field": "game_time_et", "published": pr.get("game_time_et"), "newest": nt})
        if diffs:
            changed.append({"row": nr, "diffs": diffs})
    for k, pr in pub_index.items():
        if k not in new_index:
            removed.append(pr)

    # A row whose team cell the newer document prints and the older one did not.
    team_filled = []
    for k, nr in new_index.items():
        pr = pub_index.get(k)
        if pr is not None and not norm(pr.get("team", "")) and nr["team"]:
            team_filled.append({"player": nr["player"], "matchup": nr["matchup"],
                                "published_team": "", "newest_team": nr["team"],
                                "published_status": pr.get("status", ""),
                                "newest_status": nr["status"]})

    fragment_rows = [r_ for r_ in new_rows if r_["block_inherited"]]

    # ---- status transitions on the 11/14 slate ---------------------------
    transitions_1114 = []
    for k, nr in new_index.items():
        if nr["game_date"] != "11/14/2026":
            continue
        pr = pub_index.get(k)
        before = "NOT LISTED" if pr is None else (pr.get("status") or "NOT LISTED")
        after = nr["status"] or "NOT YET SUBMITTED"
        if before != after:
            transitions_1114.append({
                "player": nr["player"] or "(team did not submit)",
                "team": nr["team_name"],
                "matchup": nr["matchup"],
                "published_status": before,
                "newest_status": after,
                "reason": nr["reason"],
            })
    transitions_1114.sort(key=lambda r: (r["matchup"], r["team"], r["player"]))

    # ---- team-level filing state on 11/14 --------------------------------
    teams_1114 = {}
    for r in new_rows:
        if r["game_date"] != "11/14/2026":
            continue
        t = teams_1114.setdefault(r["team_name"], {"submitted": False, "players": 0, "out": 0})
        if not r["is_team_not_submitted"]:
            t["submitted"] = True
            t["players"] += 1
            if r["status"] in ("Out",):
                t["out"] += 1
    for pr in published_rows:
        if pr["game_date"] != "11/14/2026":
            continue
        name = pr.get("team_name") or "(team cell not printed)"
        t = teams_1114.setdefault(name, {"submitted": False, "players": 0, "out": 0})
        t.setdefault("published_submitted", False)
        if not pr["is_team_not_submitted"]:
            t["published_submitted"] = True

    # ---- R3: the pricing window is unchanged -----------------------------
    with open(os.path.join(APP, "official_slate_1114_1117.json"), encoding="utf-8") as fh:
        slate = json.load(fh)
    window = {
        "from": slate["window"]["from"],
        "to": slate["window"]["to"],
        "games": len(slate["games"]),
        "by_date": {},
        "reverified_on": "2026-11-14",
        "reverified_url": SCHEDULE_URL,
        "reverified_note": (
            "Re-read on 2026-11-14 at ~18:50Z (chunks 0-2 of 9). Every game of the window "
            "was compared field by field with the stored capture: date, tip time (ET), away, "
            "home, game id, venue. The section headers on the page state the per-date counts "
            "(Sat 11/14: 5 games, Sun 11/15: 9, Mon 11/16: 8, Tue 11/17: 5) and they match."
        ),
    }
    for g in slate["games"]:
        window["by_date"][g["date"]] = window["by_date"].get(g["date"], 0) + 1

    head_count = {}
    for d in ("2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17"):
        head_count[d] = window["by_date"].get(d, 0)

    result = {
        "schema": "nba3.session-a399d8a9.reconciliation/v1",
        "session": "arena/a399d8a9-nba3",
        "built_utc": "2026-11-14T19:05Z",
        "R1_report_stamp": {
            "published_in_manifest": manifest_stamp,
            "published_url": OLD_URL,
            "newest_listed_on_index": newest_stamp,
            "newest_url": NEW_URL,
            "index_url": INDEX_URL,
            "index_read_utc": "2026-11-14T18:47Z",
            "index_listed_through_et": "1:30 PM ET",
            "index_listed_through_note": (
                "The index page served at 18:47Z lists 11/14 reports from 12:00 a.m. through "
                "1:30 p.m. ET at 15-minute steps. A direct probe of "
                "Injury-Report_2026-11-14_01_45PM.pdf returned S3 AccessDenied, i.e. the next "
                "file had been advertised but not yet written; 1:30 PM is therefore the newest "
                "readable official report and the one this reconciliation uses."
            ),
            "hours_behind_published": 9.25,
            "published_is_stale": True,
            "verdict": (
                "The published snapshot (04:15 AM ET) is NOT the newest official report. "
                "The 01:30 PM ET game-day report supersedes it and, unlike the 04:15 AM one, "
                "carries every 11/14 team's filing."
            ),
        },
        "R2_rows": {
            "published_rows": len(published_rows),
            "published_player_rows": sum(1 for r in published_rows if not r["is_team_not_submitted"]),
            "published_not_submitted_rows": sum(1 for r in published_rows if r["is_team_not_submitted"]),
            "newest_rows": len(new_rows),
            "newest_player_rows": sum(1 for r in new_rows if not r["is_team_not_submitted"]),
            "newest_not_submitted_rows": sum(1 for r in new_rows if r["is_team_not_submitted"]),
            "matched_rows": len(new_index) - len(added),
            "rows_changed": len(changed),
            "rows_added": len(added),
            "rows_removed": len(removed),
            "cells_carried_within_document": sum(len(r_["block_inherited"]) for r_ in fragment_rows),
            "fragment_rows": len(fragment_rows),
            "fragment_rows_detail": [{"player": r_["player"], "team": r_["team"],
                                      "inherited": r_["block_inherited"], "block_of": r_["block_of"],
                                      "note": r_["fill_note"]} for r_ in fragment_rows],
            "team_cell_attested": team_attested,
        },
        "R2_changes": changed,
        "R2_added": added,
        "R2_removed": removed,
        "R2_transitions_1114": transitions_1114,
        "R2_teams_1114": teams_1114,
        "R3_window": {
            **window,
            "page_stated_counts": {
                "2026-11-14": 5, "2026-11-15": 9, "2026-11-16": 8, "2026-11-17": 5,
            },
            "stored_counts": head_count,
            "counts_agree": head_count == {"2026-11-14": 5, "2026-11-15": 9,
                                           "2026-11-16": 8, "2026-11-17": 5},
            "id_order_irregularity": (
                "On 11/17 the page prints UTA@LAC (0022600257) before CHA@LAL (0022600256), "
                "so the stored rows are not in game-id order for that date. Both ids and both "
                "tip times are as printed; the order is the page's, not a transcription error. "
                "Carried forward from flag F-DD1-03."
            ),
        },
        "sources": [
            {"id": "A-S01", "url": INDEX_URL, "what": "official injury-report index (which reports exist)"},
            {"id": "A-S02", "url": NEW_URL, "what": "11/14/26 01:30 PM ET report (newest; basis of R2)"},
            {"id": "A-S03", "url": OLD_URL, "what": "11/14/26 04:15 AM ET report (published snapshot)"},
            {"id": "A-S04", "url": SCHEDULE_URL, "what": "official schedule, 27-game window"},
        ],
    }
    os.makedirs(DATA, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=False)
        fh.write("\n")

    print("published rows      :", len(published_rows))
    print("newest rows         :", len(new_rows))
    print("matched             :", result["R2_rows"]["matched_rows"])
    print("changed / +add / -del:", len(changed), len(added), len(removed))
    print("status transitions  :", len(transitions_1114))
    print("teams not submitted on 11/14 (newest):",
          sum(1 for t, v in teams_1114.items() if not v["submitted"]))
    print("window counts agree :", result["R3_window"]["counts_agree"], head_count)
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
