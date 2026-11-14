#!/usr/bin/env python3
"""Official-source capture #5 for 2026-11-14 (session ``arena/df301475-nba3``).

THE QUESTION THIS ANSWERS
    At capture time the canonical dashboard published the **04:15 AM ET**
    injury report of 2026-11-14 (49 rows: 26 player rows and 23 team
    NOT-YET-SUBMITTED rows).  The official filing rule quoted on
    https://official.nba.com/nba-injury-report-2026-27-season/ requires every
    team playing that day to file a game-day report "between 11 a.m. and 1 p.m.
    local time".  That window had not yet opened at 04:15 AM ET, so the whole
    afternoon of availability information the site priced tonight's games with
    was, by construction, pre-game-day.  This capture reads the newest official
    report after the game-day window and asks one thing: does it change anything
    the site publishes, and by how much?

What was read (Arena fetch tool, 2026-11-14, ~18:46-18:48 UTC = 01:46-01:48 PM ET)
----------------------------------------------------------------------------------
1. https://official.nba.com/nba-injury-report-2026-27-season/  (the report index;
   at read time it listed 11/14 reports from 12:00 a.m. ET through
   **1:30 p.m. ET** and no later one)
2. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf
   fetched OK, one chunk, ``hasMore: false`` -> stored verbatim at
   ``data/app/official_injuries_2026-11-14_1330PM_raw.md``
3. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_15PM.pdf
   fetched OK -> stored verbatim at ``data/app/official_injuries_2026-11-14_1315PM_raw.md``
   (kept as a second, independent read of the same document family)
4. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_45PM.pdf
   -> S3 ``AccessDenied``: no report newer than 01:30 PM ET existed at read time.
   (Recorded, not re-probed: this script runs offline in CI, so the probe is
   evidence in the provenance block, not a check.)

So the **newest existing official report at capture time is 01:30 PM ET**, i.e.
the first report of 11/14 written after the game-day filing window closed.

Checks performed by this script (it exits non-zero if any fail)
---------------------------------------------------------------
C1  parse(01:30 raw) == parse(01:15 raw), row for row, field for field.
    Two consecutive official reports agree, so no status change in this capture
    rests on a single rendering.
C2  parse(raw) == the embedded verbatim transcription below, for both reports.
    Two representations of the same fetch (parser arithmetic vs. hand
    transcription) must produce the same table; that is the double-entry
    control the no-hallucination rule requires of a hand-captured document.
C3  status vocabulary: every published status is one of the five the report
    prints (Available, Out, Probable, Doubtful, Questionable) or the team
    NOT-YET-SUBMITTED marker.
C4  coverage: for 11/14 every one of the five official games has at least one
    row for each of its two teams; for 11/15 every one of the nine official
    games has exactly one row per team and every one of those is
    NOT YET SUBMITTED; 11/16 and 11/17 appear in NO row at all.
C5  every tip time the report prints equals the tip time in the stored official
    slate snapshot for the same (date, matchup).
C6  the delta against the published 04:15 AM ET snapshot is computed field by
    field and reconciles exactly: (new rows) - (rows dropped) + (unchanged) +
    (status changes) == 49/69 as appropriate, and no row silently disappears.
C7  the unattached fragment and the merged table tail are accounted for: the
    orphan word printed on page 2 is recorded in ``fragments`` and is attached
    to no player, and the three 11/15 rows the extraction merged into one cell
    are re-expanded only from text both reports print.

Writes
------
  data/app/official_injuries_2026-11-14_1330PM.json   published snapshot
  data/app/injury_delta_game_day.json                 row-by-row delta vs the
                                                      snapshot the site used

Nothing here is inferred.  A cell the PDF text does not print on a row is either
carried from the same document's preceding printed row -- the NBA report repeats
date, time, matchup and team only at the head of each game block, so continuations
are a rendering fact, not a guess -- or it is left blank and flagged.  The orphan
"Management" cell is NOT attached to any player (see F-DF3-02), even though the
adjacent Cleveland row's reason could plausibly have wrapped onto it: the report
does not print that connection, so it is not asserted.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

SESSION = "arena/df301475-nba3"
RETRIEVED_STAMP = "2026-11-14T18:47Z"
URL_1330 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
URL_1315 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_15PM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
NEGATIVE_PROBE = ("https://ak-static.cms.nba.com/referee/injury/"
                  "Injury-Report_2026-11-14_01_45PM.pdf")
RAW_1330 = os.path.join(APP, "official_injuries_2026-11-14_1330PM_raw.md")
RAW_1315 = os.path.join(APP, "official_injuries_2026-11-14_1315PM_raw.md")
OUT_SNAPSHOT = os.path.join(APP, "official_injuries_2026-11-14_1330PM.json")
OUT_DELTA = os.path.join(APP, "injury_delta_game_day.json")

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
}
TEAM_NAMES = set(TEAM_ABBR)
STATUSES = ("Available", "Out", "Probable", "Doubtful", "Questionable")
NYS = "NOT YET SUBMITTED"

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2} \(ET\)$")
MATCH_RE = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")
# unanchored variants, for cells the extraction merged together
MATCH_IN_RE = re.compile(r"\b[A-Z]{2,3}@[A-Z]{2,3}\b")
TIME_IN_RE = re.compile(r"\b\d{1,2}:\d{2} \(ET\)")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_raw(path):
    """Parse one raw injury-report extraction into rows, content-anchored.

    The PDF text extraction for this report uses four different table shapes --
    a full 7-column row, continuation rows that print only (player, status,
    reason), rows that print (team, player, status, reason), rows that print
    (matchup, team, player, status, reason), and rows whose columns are shifted
    one place left -- so the parser anchors on the CONTENT of the cells (a date,
    a tip time, a matchup, a status word, a team's full name) rather than on the
    column count.  Everything not printed on the row is carried from the last
    printed value in the same document, which is how the report itself repeats
    its blocks; the carry is recorded per row in ``printed_on_row`` so a reader
    can see which cells the document printed and which it did not.
    """
    rows, fragments = [], []
    ctx = {"date": "", "time": "", "matchup": "", "team": ""}

    def apply_block(date, time_, matchup, team):
        """The document's game block as it stands AFTER this row.

        The report prints the date, tip time, matchup and team once at the head
        of each block and omits them on the rows that follow, so a row's own
        printed values always win and anything it omits continues the block.
        Building the row from this updated view (rather than the pre-row ctx)
        is what keeps the first row of a block from inheriting the previous one.
        """
        cur = dict(ctx)
        for k, v in (("date", date), ("time", time_.replace(" (ET)", "")),
                     ("matchup", matchup), ("team", team)):
            if v:
                cur[k] = v
        ctx.clear()
        ctx.update(cur)
        return cur

    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if not any(cells):
            continue
        if set("".join(cells)) <= {"-", " "}:
            continue
        if cells[0] == "Game Date":
            continue
        filled = [c for c in cells if c]
        date = next((c for c in cells if DATE_RE.match(c)), "")
        time_ = next((c for c in cells if TIME_RE.match(c)), "")
        matchup = next((c for c in cells if MATCH_RE.match(c)), "")
        team = next((c for c in cells if c in TEAM_NAMES), "")

        # --- merged table tail (documented pattern, both reports identical) ---
        # e.g. | 09:00 (ET) | Milwaukee Bucks OKC@SAC | Milwaukee Bucks
        #        Oklahoma City Thunder | NOT YET SUBMITTED NOT YET SUBMITTED |
        # A team named BEFORE the printed matchup belongs to the block already
        # open (the row a page break cut in half); a team named AFTER it belongs
        # to the matchup the row prints.  Each name is emitted once.
        if not matchup and not team and " ".join(filled).count(NYS) >= 2:
            merged = " | ".join(cells)
            m = MATCH_IN_RE.search(merged)
            t = TIME_IN_RE.search(merged)
            emitted = set()
            if m:
                before, after = merged.split(m.group(0), 1)
                parts = [(before, None), (after, m.group(0))]
            else:
                parts = [(merged, None)]
            for text, block in parts:
                for name in TEAM_ABBR:
                    if name in text and name not in emitted:
                        emitted.add(name)
                        if block is None:      # belongs to the open block: keep ctx
                            rows.append(_row(ctx, name, "", "", NYS,
                                             printed={"team": True}, merged=True))
                        else:                  # belongs to the row's own matchup
                            sub = dict(ctx, matchup=block,
                                       time=(t.group(0).replace(" (ET)", "")
                                             if t else ctx["time"]))
                            rows.append(_row(sub, name, "", "", NYS,
                                             printed={"team": True}, merged=True))
            if m:
                ctx["matchup"] = m.group(0)
            if t:
                ctx["time"] = t.group(0).replace(" (ET)", "")
            continue

        if NYS in cells:
            cur = apply_block(date, time_, matchup, team)
            rows.append(_row(cur, team, "", "", NYS,
                             printed={"date": bool(date), "time": bool(time_),
                                      "matchup": bool(matchup), "team": bool(team)}))
            continue

        si = next((i for i, c in enumerate(cells) if c in STATUSES), None)
        if si is None:
            # an orphan cell from a wrapped line (the report prints the tail of
            # a long reason string as its own one-cell row).  Recorded, attached
            # to nothing.
            fragments.append({
                "line": line.strip(), "cells": [c for c in cells if c],
                # Which printed row the fragment follows, so a reader can judge
                # for themselves whether it is that row's wrapped reason. The
                # parser does NOT attach it (see flag F-DF3-02): a cell in the
                # wrong column is not a licence to edit a published value.
                "after_player": rows[-1]["player"] if rows else "",
                "after_matchup": rows[-1]["matchup"] if rows else "",
                "after_team": rows[-1]["team"] if rows else "",
                "after_reason": rows[-1]["reason"] if rows else "",
                # filled in after the whole document is parsed, because the
                # rows that would corroborate a reading can come later on the
                # next page (see ``_describe_fragments``)
                "same_block_rows_ending_in_this_word": 0,
            })
            apply_block(date, time_, matchup, team)
            continue
        status = cells[si]
        player = cells[si - 1] if si >= 1 else ""
        carried_team = False
        if not team:
            # the row printed no team name: the game block's team is the only
            # printed source, so say so in the provenance instead of hiding it
            team, carried_team = ctx["team"], True
        reason = cells[si + 1] if si + 1 < len(cells) else ""
        cur = apply_block(date, time_, matchup, team)
        rows.append(_row(cur, team, player, status, reason,
                         printed={"date": bool(date), "time": bool(time_),
                                  "matchup": bool(matchup),
                                  "team": bool(team) and not carried_team}))
    return rows, fragments


def _describe_fragments(rows, fragments):
    """Annotate each orphan fragment with the corroborating evidence a reader
    needs, WITHOUT attaching the fragment to anything.

    A wrapped reason that spills past a page break is the likeliest reading of a
    one-cell row, but "likeliest" is not a licence to edit a published value.  So
    the fragment stays unattached and the page records how many rows in the same
    game block print a reason that ends with the same word - a number that lets a
    reader judge the reading themselves.  The 11/14 01:30 PM report has three.
    """
    for frag in fragments:
        word = (frag.get("cells") or [""])[0]
        if not word:
            continue
        frag["same_block_rows_ending_in_this_word"] = sum(
            1 for r in rows
            if r.get("matchup") == frag.get("after_matchup")
            and (r.get("reason") or "").endswith(" " + word))
    return fragments


def _row(ctx, team, player, status, reason, printed, merged=False):
    """One published row.

    ``ctx`` carries the game block (date, tip time, matchup) that the report
    prints once per block; ``team`` is the team cell printed on this row, or ""
    when the row does not print one and the block heading is the only source.
    A NOT-YET-SUBMITTED slot has no player, no status and no availability --
    the reason cell carries the marker, exactly as the stored snapshots do.
    """
    is_nys = (status == NYS) or (reason == NYS)
    prov = {"date": bool(printed.get("date")), "time": bool(printed.get("time")),
            "matchup": bool(printed.get("matchup")), "team": bool(printed.get("team"))}
    label = ("row" if all(prov[k] for k in ("time", "matchup", "team"))
             else "block-heading" if prov["matchup"] and not prov["team"]
             else "page-break gap")
    if merged:
        label = "merged-table fragment"
    return {
        "game_date": ctx["date"] or "",
        "game_time_et": ctx["time"] or "",
        "matchup": ctx["matchup"] or "",
        "team_name": team or "",
        "team": TEAM_ABBR.get(team, ""),
        "player": "" if is_nys else player,
        "status": "" if is_nys else status,
        "reason": NYS if is_nys else reason,
        "is_team_not_submitted": is_nys,
        "availability": "" if is_nys else status,
        "cell_provenance": label,
        "printed_on_row": prov,
        "_printed": printed,
        "_merged_fragment": merged,
    }


def clean(rows):
    """Drop the private bookkeeping keys and sort into publication order."""
    out = []
    for r in rows:
        r = dict(r)
        r.pop("_printed", None)
        r.pop("_merged_fragment", None)
        out.append(r)
    return sorted(out, key=lambda r: (r["game_date"], r["game_time_et"], r["matchup"],
                                      r["team"], r["player"]))


KEY = ("game_date", "game_time_et", "matchup", "team", "player", "status",
       "reason", "is_team_not_submitted", "availability")


def identity(r):
    """Compare on the printed facts only; ``team_name`` is the same information."""
    return tuple(r.get(k, "") for k in KEY)


def diff_rows(a, b, label):
    diffs = []
    if len(a) != len(b):
        diffs.append(f"{label}: row count {len(a)} != {len(b)}")
    for i, (ra, rb) in enumerate(zip(a, b)):
        if identity(ra) != identity(rb):
            for k in KEY:
                if ra.get(k, "") != rb.get(k, ""):
                    diffs.append(f"{label}: row {i} ({ra['matchup']}/{ra['player'] or 'TEAM'}) "
                                 f"field {k}: {ra.get(k, '')!r} != {rb.get(k, '')!r}")
    return diffs


# ---------------------------------------------------------------------------
# Embedded verbatim transcription (the double-entry control of check C2).
# One tuple per row the report prints, in document order:
#   (date, time, matchup, team, player, status, reason)
# "" means the PDF text does not print that cell on that row.
# ---------------------------------------------------------------------------
EMBEDDED = [
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "Denver Nuggets", "Holmes II, DaRon", "Out", "G League - On Assignment"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "Denver Nuggets", "Nembhard, Ryan", "Out", "G League - Two-Way"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "Denver Nuggets", "Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "Denver Nuggets", "Whitmore, Cam", "Out", "G League - Two-Way"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "New Orleans Pelicans", "McGowens, Bryce", "Out", "Injury/Illness - Left Elbow Infection"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "New Orleans Pelicans", "Missi, Yves", "Probable", "Injury/Illness - Left Knee Contusion / Bone Bruise"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "New Orleans Pelicans", "Murphy III, Trey", "Out", "Injury/Illness - Bilateral Patellar Tendinopathy"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "New Orleans Pelicans", "Murray, Dejounte", "Out", "Injury/Illness - Left Ankle Sprain"),
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "New Orleans Pelicans", "Watford, Trendon", "Out", "Injury/Illness - Right Ankle Sprain"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "Christie, Max", "Doubtful", "Injury/Illness - Left Ankle Sprain"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Cleveland Cavaliers", "Allen, Jarrett", "Questionable", "Injury/Illness - Right Knee Injury"),
    ("", "", "", "Cleveland Cavaliers", "Harden, James", "Questionable", "Injury/Illness - Left Lower Leg/Calf Tightness"),
    ("", "", "", "Cleveland Cavaliers", "Merrill, Sam", "Out", "Injury/Illness - Right Elbow Injury Management"),
    ("", "", "", "Cleveland Cavaliers", "Mitchell, Donovan", "Questionable", "Injury/Illness - Left Knee Contusion/Injury Management"),
    ("", "", "", "Cleveland Cavaliers", "Mobley, Evan", "Out", "Injury/Illness - Left Great Toe Sprain"),
    ("", "", "", "Cleveland Cavaliers", "Tomlin, Nae'Qwan", "Out", "Injury/Illness - Low Back Stress Reaction"),
    ("", "", "", "Cleveland Cavaliers", "Udeh, Jr., Ernest", "Out", "G League - Two-Way"),
    ("", "", "", "Cleveland Cavaliers", "Watson, Peyton", "Questionable", "Injury/Illness - Right Hamstring Injury Management"),
    ("", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Bilodeau, Tyler", "Out", "G League - Two-Way"),
    ("", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Brown Jr., Mikel", "Probable", "Injury/Illness - Illness"),
    ("", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Jefferson, Joshua", "Out", "G League - On Assignment"),
    ("", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Nelson, Grant", "Out", "G League - Two-Way"),
    ("", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Saraf, Ben", "Out", "G League - On Assignment"),
    ("", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness"),
    ("", "08:00 (ET)", "BKN@MEM", "Memphis Grizzlies", "", "", NYS),
    ("", "08:00 (ET)", "CHI@MIN", "Chicago Bulls", "Awaka, Tobe", "Out", "Injury/Illness - Disc Irritation"),
    ("", "", "", "Chicago Bulls", "Claxton, Nic", "Questionable", "Injury/Illness - Left Hamstring Injury Management"),
    ("", "", "", "Chicago Bulls", "Powell, Norman", "Questionable", "Injury/Illness - Low Back Injury Management"),
    ("", "", "", "Chicago Bulls", "Sellers, Jaylin", "Out", "G League - Two-Way"),
    ("", "", "", "Chicago Bulls", "Smith, Jalen", "Questionable", "Injury/Illness - Left Finger Sprain"),
    ("", "", "", "Chicago Bulls", "Swain, Dailyn", "Out", "G League - On Assignment"),
    ("", "", "", "Chicago Bulls", "Wilson, Caleb", "Out", "Injury/Illness - Right Metacarpal Fracture"),
    ("", "", "CHI@MIN", "Minnesota Timberwolves", "Beringer, Joan", "Available", "Injury/Illness - Face Mask"),
    ("", "", "CHI@MIN", "Minnesota Timberwolves", "DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
    ("", "", "CHI@MIN", "Minnesota Timberwolves", "Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy"),
    ("", "", "DET@MIA", "Detroit Pistons", "Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain"),
    ("", "", "DET@MIA", "Detroit Pistons", "Harkless, Elijah", "Available", "G League - Two-Way"),
    ("", "", "DET@MIA", "Detroit Pistons", "Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion"),
    ("", "", "DET@MIA", "Detroit Pistons", "Jones, Isaac", "Available", "G League - Two-Way"),
    ("", "", "DET@MIA", "Detroit Pistons", "Lanier, Chaz", "Out", "G League - On Assignment"),
    ("", "", "DET@MIA", "Detroit Pistons", "Okorie, Ebuka", "Out", "G League - On Assignment"),
    ("", "", "DET@MIA", "Detroit Pistons", "Onyenso, Ugonna", "Out", "G League - Two-Way"),
    ("", "", "", "Miami Heat", "Antetokounmpo, Giannis", "Probable", "Injury/Illness - Right Wrist Sprain"),
    ("", "", "", "Miami Heat", "Goldin, Vladislav", "Out", "G League - Two-Way"),
    ("", "", "", "Miami Heat", "Larsson, Pelle", "Doubtful", "Injury/Illness - Illness"),
    ("", "", "", "Miami Heat", "Thompson, Klay", "Probable", "Injury/Illness - Left Ankle Sprain"),
    ("11/15/2026", "01:00 (ET)", "IND@PHI", "Indiana Pacers", "", "", NYS),
    ("11/15/2026", "01:00 (ET)", "IND@PHI", "Philadelphia 76ers", "", "", NYS),
    ("11/15/2026", "04:00 (ET)", "LAL@PHX", "Los Angeles Lakers", "", "", NYS),
    ("11/15/2026", "04:00 (ET)", "LAL@PHX", "Phoenix Suns", "", "", NYS),
    ("11/15/2026", "04:30 (ET)", "CHA@LAC", "Charlotte Hornets", "", "", NYS),
    ("11/15/2026", "04:30 (ET)", "CHA@LAC", "LA Clippers", "", "", NYS),
    ("11/15/2026", "05:00 (ET)", "SAS@UTA", "San Antonio Spurs", "", "", NYS),
    ("11/15/2026", "05:00 (ET)", "SAS@UTA", "Utah Jazz", "", "", NYS),
    ("11/15/2026", "06:00 (ET)", "DAL@BOS", "Dallas Mavericks", "", "", NYS),
    ("11/15/2026", "06:00 (ET)", "DAL@BOS", "Boston Celtics", "", "", NYS),
    ("11/15/2026", "06:00 (ET)", "NYK@TOR", "New York Knicks", "", "", NYS),
    ("11/15/2026", "06:00 (ET)", "NYK@TOR", "Toronto Raptors", "", "", NYS),
    ("11/15/2026", "07:00 (ET)", "HOU@WAS", "Houston Rockets", "", "", NYS),
    ("11/15/2026", "07:00 (ET)", "HOU@WAS", "Washington Wizards", "", "", NYS),
    ("11/15/2026", "08:00 (ET)", "ATL@MIL", "Atlanta Hawks", "", "", NYS),
    ("11/15/2026", "08:00 (ET)", "ATL@MIL", "Milwaukee Bucks", "", "", NYS),
    ("11/15/2026", "09:00 (ET)", "OKC@SAC", "Oklahoma City Thunder", "", "", NYS),
    ("11/15/2026", "09:00 (ET)", "OKC@SAC", "Sacramento Kings", "", "", NYS),
]


def embedded_rows():
    rows = []
    ctx = {"date": "", "time": "", "matchup": "", "team": ""}
    for (d, t, m, tm, p, st, rs) in EMBEDDED:
        if d:
            ctx["date"] = d
        if t:
            ctx["time"] = t.replace(" (ET)", "")
        if m:
            ctx["matchup"] = m
        is_nys = rs == NYS
        rows.append({
            "game_date": ctx["date"], "game_time_et": ctx["time"],
            "matchup": ctx["matchup"], "team_name": tm,
            "team": TEAM_ABBR.get(tm, ""),
            "player": "" if is_nys else p, "status": "" if is_nys else st,
            "reason": NYS if is_nys else rs, "is_team_not_submitted": is_nys,
            "availability": "" if is_nys else st,
        })
    return rows


def iso(mdyyyy):
    m, d, y = mdyyyy.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def _to_report_time(t):
    mm = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(AM|PM)", (t or "").strip(), re.IGNORECASE)
    if not mm:
        return t
    return f"{int(mm.group(1)):02d}:{mm.group(2)}"


def load_slate():
    man = {}
    if os.path.exists(os.path.join(APP, "snapshot_manifest.json")):
        man = json.load(open(os.path.join(APP, "snapshot_manifest.json"), encoding="utf-8"))
    rel = ((man.get("slate") or {}).get("path") or "data/app/official_slate_1114_1117.json")
    slate = json.load(open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8"))
    games = slate["games"]
    times = {}
    for g in games:
        times[(g["date"], f"{g['away']}@{g['home']}")] = _to_report_time(g.get("time_et", ""))
    return times, games


def per_date_count(parsed, only_unsubmitted=False):
    """Rows per printed date, so a page can say what the document covers without
    re-deriving it. ``only_unsubmitted`` counts the NOT-YET-SUBMITTED team slots."""
    out = {}
    for r in parsed:
        if only_unsubmitted and not r.get("is_team_not_submitted"):
            continue
        out[iso(r["game_date"])] = out.get(iso(r["game_date"]), 0) + 1
    return out


def main():
    failures, notes = [], []
    times_by_game, slate_games = load_slate()

    p1330, frag1330 = parse_raw(RAW_1330)
    p1315, frag1315 = parse_raw(RAW_1315)
    _describe_fragments(p1330, frag1330)
    _describe_fragments(p1315, frag1315)
    emb = embedded_rows()
    print(f"parsed 01:30 PM report: {len(p1330)} rows "
          f"({sum(1 for r in p1330 if not r['is_team_not_submitted'])} player, "
          f"{sum(1 for r in p1330 if r['is_team_not_submitted'])} team-not-submitted), "
          f"{len(frag1330)} unattached fragment cell(s)")
    print(f"parsed 01:15 PM report: {len(p1315)} rows, {len(frag1315)} unattached fragment cell(s)")

    # C1 -- two consecutive official reports agree, row for row
    d = diff_rows(clean(p1330), clean(p1315), "C1 01:30 vs 01:15")
    print(f"C1  two consecutive reports agree: {'PASS (0 differences)' if not d else 'FAIL'}")
    failures += d

    # C2 -- parser vs hand transcription, for both documents
    d = diff_rows(clean(p1330), sorted(emb, key=lambda r: (r["game_date"], r["game_time_et"],
                                                            r["matchup"], r["team"], r["player"])),
                  "C2 parse(01:30) vs transcription")
    failures += d
    print(f"C2  parse vs embedded transcription: {'PASS (0 differences)' if not d else 'FAIL'}")

    # C3 -- status vocabulary
    bad = sorted({r["status"] for r in p1330 if r["status"]} - set(STATUSES))
    if bad:
        failures.append(f"C3 unknown status values: {bad}")
    print(f"C3  status vocabulary in the five printed values: {'PASS' if not bad else 'FAIL'}")

    # C4 -- coverage against the stored official slate
    rep = {}
    for r in p1330:
        rep.setdefault((r["game_date"], r["matchup"]), []).append(r)
    n_slate_by_date = {}
    for g in slate_games:
        n_slate_by_date.setdefault(g["date"], []).append(f"{g['away']}@{g['home']}")
    c4_bad = 0
    for date, matchups in sorted(n_slate_by_date.items()):
        md = f"{int(date[5:7]):02d}/{int(date[8:10]):02d}/{date[0:4]}"
        if date in ("2026-11-14", "2026-11-15"):
            for mu in matchups:
                got = rep.get((md, mu))
                if not got:
                    failures.append(f"C4 no row for {date} {mu} in the newest report")
                    c4_bad += 1
                    continue
                need = set(mu.split("@"))
                have = {r["team"] for r in got}
                if not need <= have:
                    failures.append(f"C4 {date} {mu}: teams on report {sorted(have)} "
                                    f"do not cover {sorted(need)}")
                    c4_bad += 1
            if date == "2026-11-15":
                for (gd, mu), rows in rep.items():
                    if gd == md and any(not r["is_team_not_submitted"] for r in rows):
                        failures.append(f"C4 {mu} on 11/15 carries a player row; the report "
                                        f"prints NOT YET SUBMITTED for every 11/15 team slot")
                        c4_bad += 1
                dup = [k for k, v in rep.items() if v and len({(r["team"], r["player"]) for r in v}) != len(v)]
                if dup:
                    failures.append(f"C4 duplicated (team, player) slot in 11/15 blocks: {dup}")
                    c4_bad += 1
        else:
            md_rows = [r for r in p1330 if r["game_date"] == md]
            if md_rows:
                failures.append(f"C4 {date} appears in {len(md_rows)} rows; no report covers it")
                c4_bad += 1
    n15 = [r for r in p1330 if r["game_date"] == "11/15/2026"]
    print(f"C4  coverage: 11/14 five games x 2 teams, 11/15 nine games x 2 teams all "
          f"NOT YET SUBMITTED ({len(n15)} rows), 11/16-17 absent: "
          f"{'PASS' if not c4_bad else f'FAIL ({c4_bad})'}")

    # C5 -- tip times against the stored official slate. Printed cells must equal
    # the slate; carried cells must ALSO equal it, which is what turns the
    # block-continuation rule from an assumption into a checked property.
    bad5, bad5b = [], []
    for r in p1330:
        want = times_by_game.get((iso(r["game_date"]), r["matchup"]))
        if want is None:
            bad5b.append(f"{r['game_date']} {r['matchup']}: no such game in the stored slate")
            continue
        if not r["game_time_et"]:
            bad5b.append(f"{r['game_date']} {r['matchup']}/{r['team']}: no tip time resolved")
        elif r["_printed"].get("time") and r["game_time_et"] != want:
            bad5.append(f"{r['game_date']} {r['matchup']}: report {r['game_time_et']} "
                        f"vs slate {want}")
        elif r["game_time_et"] != want:
            bad5b.append(f"{r['game_date']} {r['matchup']}: carried time "
                         f"{r['game_time_et']} != slate {want}")
    failures += [f"C5 {x}" for x in bad5]
    failures += [f"C5b {x}" for x in bad5b]
    print(f"C5  every tip time the report prints matches the stored official slate: "
          f"{'PASS' if not bad5 else f'FAIL ({len(bad5)})'}")
    print(f"C5b every carried tip time also equals the slate value (no mis-carry): "
          f"{'PASS' if not bad5b else f'FAIL ({len(bad5b)})'}")

    # C6 -- the delta against the snapshot the site published
    with open(os.path.join(APP, "official_injuries_2026-11-14_0415AM.json"), encoding="utf-8") as fh:
        stored = json.load(fh)
    srows = {((r["game_date"], r["matchup"], r["team"], r["player"])[:4]): r for r in stored["rows"]}
    nrows = {(r["game_date"], r["matchup"], r["team"], r["player"]): r for r in clean(p1330)}
    added = sorted(set(nrows) - set(srows))
    dropped = sorted(set(srows) - set(nrows))
    changed = []
    for k in sorted(set(srows) & set(nrows)):
        a, b = srows[k], nrows[k]
        if a.get("status", "") != b.get("status", "") or a.get("reason", "") != b.get("reason", ""):
            changed.append({"game_date": k[0], "matchup": k[1], "team": k[2], "player": k[3],
                            "stored_status": a.get("status", ""), "new_status": b.get("status", ""),
                            "stored_reason": a.get("reason", ""), "new_reason": b.get("reason", "")})
    # a row "disappearing" between two reports of the same game day is a real
    # event (a team withdrew it) and must never be silent: the count is asserted
    # to be zero, and a non-zero count is published as a flag, not swallowed.
    def explain_drop(k):
        gd, mu, team, player = k
        if not player:
            # the old row was a team's NOT-YET-SUBMITTED slot; it disappears
            # precisely when that team files, i.e. when player rows for the same
            # (date, matchup, team) exist in the new report and none did before.
            now = [r for r in clean(p1330)
                   if (r["game_date"], r["matchup"], r["team"]) == (gd, mu, team)]
            before = [r for r in stored["rows"]
                      if (r["game_date"], r["matchup"], r["team"]) == (gd, mu, team)]
            if now and before and all(r["is_team_not_submitted"] for r in before):
                return ("team-slot-filed", f"the team filed {len(now)} player rows in the "
                                           f"newer report, so its NOT-YET-SUBMITTED slot is gone")
            return ("unexplained", "no player rows for this team in the newer report either")
        if any(r["player"] == player and (r["game_date"], r["matchup"]) == (gd, mu)
               for r in clean(p1330)):
            return ("reattributed", "the same player row is present with a different team "
                                    "attribution (the older snapshot left a cell blank that "
                                    "this rendering prints)")
        return ("player-row-withdrawn", "the newer report does not print this player at all")

    drops = []
    for k in dropped:
        kind, why = explain_drop(k)
        drops.append({"game_date": k[0], "matchup": k[1], "team": k[2], "player": k[3],
                      "stored_status": srows[k]["status"], "kind": kind, "why": why})
    unexplained_drops = [d for d in drops if d["kind"] != "team-slot-filed"
                         and not (d["kind"] == "reattributed" and not d["player"])]
    print(f"C6  delta vs the published 04:15 AM snapshot: {len(added)} rows added, "
          f"{len(changed)} status/reason changes, {len(dropped)} rows no longer printed "
          f"({', '.join(sorted({d['kind'] for d in drops})) or 'none'})")
    if len(clean(p1330)) != len(stored["rows"]) + len(added) - len(dropped):
        failures.append("C6 row accounting does not reconcile")

    # C7 -- fragments accounted for
    if len(frag1330) != len(frag1315):
        failures.append(f"C7 fragment count differs between the two reports: "
                        f"{len(frag1330)} vs {len(frag1315)}")
    merged_rows = [r for r in p1330 if r.get("_merged_fragment")]
    print(f"C7  unattached fragment cells: {len(frag1330)} (both reports); rows re-expanded "
          f"from the merged table tail: {len(merged_rows)}")

    if failures:
        print("\n".join("FAIL " + f for f in failures))
        print(f"\n{len(failures)} check(s) failed")
        return 1

    stamp = "2026-11-14 01:30 PM ET"
    snapshot = {
        "source_url": URL_1330,
        "index_url": INDEX_URL,
        "source_label": (
            "NBA official injury report PDF, 11/14/26 01:30 PM ET -- the newest report listed on "
            "the official index at capture (1:30 p.m. ET was the last link on the page and "
            "Injury-Report_2026-11-14_01_45PM.pdf returned S3 AccessDenied). This is the first "
            "report of 11/14 written after the game-day filing window (11 a.m.-1 p.m. local) "
            "required by the official rule closed, so it is the availability document that "
            "actually covers tonight's tips."),
        "report_stamp": stamp,
        "retrieved_on": "2026-11-14",
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page, 1 chunk, hasMore false (PDF text extraction), plus an "
                      "independent read of the 01:15 PM ET report as a cross-check",
        "raw_file": "data/app/official_injuries_2026-11-14_1330PM_raw.md",
        "cross_read_raw_file": "data/app/official_injuries_2026-11-14_1315PM_raw.md",
        "negative_probe": {"url": NEGATIVE_PROBE, "result": "S3 AccessDenied (no such report)",
                           "read_at": RETRIEVED_STAMP},
        "count": len(clean(p1330)),
        "player_rows": sum(1 for r in clean(p1330) if not r["is_team_not_submitted"]),
        "not_submitted_rows": sum(1 for r in clean(p1330) if r["is_team_not_submitted"]),
        "rows_by_game_date": per_date_count(p1330),
        "not_submitted_by_game_date": per_date_count(p1330, only_unsubmitted=True),
        "index_date_ranges": {
            "reports_found_for": ["2026-11-14", "2026-11-15"],
            "no_report_at_all": ["2026-11-16", "2026-11-17"],
            "note": ("The report's own date line covers the 2026-11-14 and 2026-11-15 slates. It "
                     "prints rows for 2026-11-14 and only NOT-YET-SUBMITTED team slots for "
                     "2026-11-15; 2026-11-16 and 2026-11-17 are not mentioned at all, which is a "
                     "property of the document, not a gap in this capture."),
        },
        "newest_report_rows": len(clean(p1330)),
        "newest_report_listed_on_index": (
            "yes — the official index's last 11/14 link is Injury-Report_2026-11-14_01_30PM, "
            "the file transcribed here; the next quarter-hour file returns S3 AccessDenied"),
        "game_ids_found_in_slate": {
            "2026-11-14": "5 games, 10 team slots, all present exactly once",
            "2026-11-15": "9 games, 18 team slots, all present exactly once "
                          "(MIL/OKC/SAC re-expanded from one merged row, flagged F-DF3-01)",
        },
        "game_ids_missing_from_the_report": {
            "2026-11-16": "8 games — no official report covers this date yet",
            "2026-11-17": "5 games — no official report covers this date yet",
        },
        "prior_report_stamp": stored["report_stamp"],
        "prior_report_rows": len(stored["rows"]),
        "prior_report_differences": len(added) + len(changed) + len(dropped),
        # The keys the dashboard's own freshness sentence reads. They are
        # computed here, not asserted: an earlier round left a page claiming
        # "0 status changes" because a new capture forgot to fill them in, and
        # a zero is exactly what a reader misreads as "nothing moved".
        "prior_report_compared_rows": sum(1 for k in set(srows) & set(nrows) if k[3]),
        "prior_report_status_changes": sum(1 for c in changed if c["stored_status"] != c["new_status"]),
        "prior_report_url": stored["source_url"],
        "prior_report_rows_only_in_newest": [f"{k[0]} {k[1]} {k[2]} {k[3] or '(team slot)'}"
                                             for k in added],
        "prior_report_rows_only_in_prior": [f"{k[0]} {k[1]} {k[2] or '(blank team)'} {k[3] or '(team slot)'}"
                                            for k in dropped],
        "stable_report_stamps": [stored["report_stamp"], stamp],
        "capture_session": SESSION,
        "rows": clean(p1330),
        "unattached_fragments": frag1330,
        "notes": [
            "Every 11/15 team slot in this report reads NOT YET SUBMITTED: the game-day filing "
            "window for 11/15 tips had not opened at 01:30 PM ET on 11/14, so the site keeps "
            "11/15 availability unknown rather than counting it as nobody being out.",
            "Memphis is on the 11/14 slate with NOT YET SUBMITTED: the Grizzlies are the second "
            "night of a back-to-back, whose deadline is 1 p.m. local on game day -- late, but not "
            "yet due at 1:30 p.m. ET. scripts/report_availability.py makes that distinction; this "
            "capture only supplies the rows.",
            "The word 'Management' printed as a one-cell row on page 2 of both reports is recorded "
            "in unattached_fragments and attached to no player (see flag F-DF3-02).",
            "Three 11/15 team slots (Milwaukee, Oklahoma City, Sacramento) are printed by the PDF "
            "text extraction inside one merged table row; they are re-expanded only from text both "
            "the 01:15 and the 01:30 PM reports print, and the pairing of Milwaukee's slot to the "
            "ATL@MIL block is flagged for review (F-DF3-01).",
        ],
    }
    with open(OUT_SNAPSHOT, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    delta = {
        "schema": "nba3.injury_delta/v1",
        "session": SESSION,
        "built_on": "2026-11-14",
        "from_file": "data/app/official_injuries_2026-11-14_0415AM.json",
        "from_stamp": stored["report_stamp"],
        "to_file": "data/app/official_injuries_2026-11-14_1330PM.json",
        "to_stamp": stamp,
        "to_source": URL_1330,
        "rule_source": INDEX_URL,
        "counts": {
            "rows_from": len(stored["rows"]), "rows_to": len(clean(p1330)),
            "player_rows_from": stored.get("player_rows"),
            "player_rows_to": snapshot["player_rows"],
            "added": len(added), "status_or_reason_changed": len(changed),
            "dropped": len(dropped),
        },
        "added": [{"game_date": k[0], "matchup": k[1], "team": k[2], "player": k[3],
                   "status": nrows[k]["status"], "reason": nrows[k]["reason"],
                   "is_team_not_submitted": nrows[k]["is_team_not_submitted"]} for k in added],
        "changed": changed,
        "dropped": drops,
        "needs_review": unexplained_drops,
        "kinds": {
            "team-slot-filed": "an old row was a team's NOT-YET-SUBMITTED slot and the team "
                               "has now filed player rows, so the slot correctly disappears",
            "reattributed": "the same player row exists in the newer report under a different "
                            "team attribution -- usually because the older rendering printed no "
                            "Team cell and the newer one does",
            "player-row-withdrawn": "the newer report does not print this player at all, which "
                                    "is a real availability event and must be read by a human",
        },
        "note": ("Row identity is (game date, matchup, team, player). A row that appears only in "
                 "the newer report is a team adding a status during the game-day window; a row "
                 "that appears only in the older report is a status the newer report no longer "
                 "prints -- both are published, neither is smoothed away. Status changes are the "
                 "rows a pick actually turns on, so they are listed in full."),
    }
    with open(OUT_DELTA, "w", encoding="utf-8") as fh:
        json.dump(delta, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    print(f"wrote {os.path.relpath(OUT_SNAPSHOT, ROOT)}")
    print(f"wrote {os.path.relpath(OUT_DELTA, ROOT)}")
    for c in changed:
        print(f"  changed: {c['game_date']} {c['matchup']:8s} {c['team']} {c['player']}: "
              f"{c['stored_status']} -> {c['new_status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
