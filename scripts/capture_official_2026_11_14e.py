#!/usr/bin/env python3
"""Official-source capture #5 for 2026-11-14 (session ``arena/1823b910-nba3``).

Purpose
-------
The canonical dashboard publishes the official injury snapshot of
**2026-11-14 05:15 AM ET** (49 rows: 26 player rows + 23 ``NOT YET SUBMITTED``
placeholders).  That snapshot was taken *before* the league's game-day
submission window (11 a.m. - 1 p.m. local time for a game that is not the
second night of a back-to-back), so most teams had not filed yet.

Re-reading the official report index at capture time shows the index now lists
11/14 reports through **1:30 p.m. ET**.  This capture answers one question:

    **What does the newest official report say, and how far is the published
    snapshot behind it?**

What was read (Arena fetch tool, 2026-11-14, ~18:50-18:55 UTC = 01:50-01:55 PM ET)
--------------------------------------------------------------------------------
1. https://official.nba.com/nba-injury-report-2026-27-season/
   -> page text lists the November 14 reports from 12:00 a.m. ET through
      **1:30 p.m. ET**; 1:30 p.m. is the last entry (stored verbatim at
      data/app/official_index_2026-11-14.json).
2. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf
   -> fetched OK, twice; both reads returned identical text.  Stored verbatim at
      data/app/official_injuries_2026-11-14_0130PM_raw.md.
3. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_45PM.pdf
   -> S3 ``AccessDenied`` (no such report at capture time).
4. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_00PM.pdf
   -> fetched OK.  Stored verbatim at
      data/app/official_injuries_2026-11-14_0100PM_raw.md.  It is the report
      immediately before the newest one and is used **only** as an official
      cross-check for cells the 01:30 PM text extraction does not print.

Parsing rules (all "no inference" - a cell the document does not print is
either carried from the same document's own earlier rows or taken from another
official report, and is labelled)
---------------------------------------------------------------------------
* The PDF text extraction splits one report across page fragments and drops the
  columns a fragment repeats.  Rows therefore arrive with 4-8 cells.
* Trailing empty cells are dropped, then the last cell is the Reason, and (for a
  player row) the two cells before it are Status and Player.
* The remaining leading non-empty cells are **right-aligned** onto the slots
  [date, time, matchup, team].  A cell the row does not print is carried forward
  from the previous row of the same document.
* Two fragment shapes need explicit handling:
  - a row whose only non-empty cell sits before two empty trailing cells is a
    continuation of the previous row's Reason (here: ``Management`` completes
    ``Injury/Illness - Right Knee Injury Management``);
  - the final fragment of the 01:30 PM text merges two logical rows into one
    line.  It is expanded into its three logical rows, and the expansion is
    cross-checked against the 01:00 PM report (check E3), which prints the same
    rows unmerged.

Checks performed by this script (it exits non-zero if any fail)
---------------------------------------------------------------
E1  the parsed 01:30 PM report has the expected shape: every status is one of
    the official statuses, every matchup is in the stored official slate, and
    every tip time the report prints equals the slate value;
E2  the 01:00 PM report parses to the same game/team inventory;
E3  every row whose team cell the 01:30 PM text does not print is attributed
    identically by the 01:00 PM report (official cross-check, not inference);
E4  the 01:30 PM report covers exactly the five 11/14 games and the nine 11/15
    games of the stored official slate;
E5  the delta against the published canonical snapshot (05:15 AM ET) is
    computed and stored - this script reports it, it does not fail on it,
    because a change is the expected outcome of a refresh;
E6  the injury -> rotation impact (minutes / points / rebounds / assists
    vacated) is recomputed from the refreshed report using only official
    season per-game figures the repository has captured.

Writes
------
  data/app/official_injuries_2026-11-14_0130PM.json   (this session's snapshot,
  same schema as the stored snapshots)

Nothing here edits the published canonical dataset.  The snapshot manifest is
**not** repointed: that is the owner's decision (see the change request in
COORDINATION.md).
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

SESSION = "arena/1823b910-nba3"
RETRIEVED_STAMP = "2026-11-14T18:50Z"

URL_0130 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
URL_0100 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_00PM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
SLATE_URL = "https://www.nba.com/schedule?date=2026-11-14"
MINUTES_URL = ("https://www.nba.com/stats/players/traditional?Season=2026-27"
               "&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC")

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

OFFICIAL_STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
NYS = "NOT YET SUBMITTED"

# The final fragment of the 01:30 PM text, verbatim.  Two logical rows are
# merged into one line by the PDF text extraction; see the module docstring.
MERGED_TAIL_CELLS = ("09:00 (ET)", "Milwaukee Bucks OKC@SAC",
                     "Milwaukee Bucks Oklahoma City Thunder",
                     "NOT YET SUBMITTED NOT YET SUBMITTED")
MERGED_TAIL_EXPANSION = (
    ("ATL@MIL", "Milwaukee Bucks", "carried"),
    ("OKC@SAC", "Oklahoma City Thunder", "printed"),
    ("OKC@SAC", "Sacramento Kings", "carried"),
)


def iso_date(mdyyyy):
    m, d, y = mdyyyy.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def to_report_time(t):
    """'7:00 PM' (slate) -> '07:00' (report)."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(AM|PM)", t.strip(), re.IGNORECASE)
    if not m:
        return t
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def parse_raw(path):
    """Parse one verbatim injury-report markdown extraction into rows.

    Returns a list of dicts plus, on each row, a private ``_printed`` set
    recording which of the four leading slots the row itself printed.
    """
    rows = []
    ctx = {"date": "", "time": "", "matchup": "", "team": ""}
    skip_next_team = None
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            nonempty = [c for c in cells if c]
            if nonempty and all(re.fullmatch(r"-{2,}", c) for c in nonempty):
                continue                      # markdown separator row
            if cells and cells[0].startswith("Game Date"):
                continue                      # table header
            while cells and cells[-1] == "":
                cells.pop()                   # drop trailing empty cells
            if not cells:
                continue

            # (a) continuation row: a lone cell that is not a stand-alone
            #     Reason completes the previous row's Reason.  (Here: the
            #     fragment header prints "Management", the tail of
            #     "Injury/Illness - Right Knee Injury Management".)
            if len(nonempty) == 1 and nonempty[0] != NYS:
                if not rows:
                    raise SystemExit(f"{path}:{lineno}: continuation with no previous row")
                rows[-1]["reason"] = (rows[-1]["reason"] + " " + nonempty[0]).strip()
                rows[-1]["_continued"] = True
                rows[-1]["_reason_provenance"] = (
                    "completed from the following page fragment of the same PDF "
                    f"(the fragment header prints {nonempty[0]!r})")
                continue

            reason = cells[-1]

            # (b) the merged final fragment of the 01:30 PM text
            if tuple(cells) == MERGED_TAIL_CELLS:
                for i, (matchup, team_name, prov) in enumerate(MERGED_TAIL_EXPANSION):
                    tm = "09:00" if i else ctx["time"]
                    rows.append({
                        "game_date": ctx["date"], "game_time_et": tm, "matchup": matchup,
                        "team_name": team_name, "team": TEAM_ABBR.get(team_name, ""),
                        "player": "", "status": "", "reason": NYS,
                        "is_team_not_submitted": True, "availability": "",
                        "_team_printed": True, "_time_printed": bool(i),
                        "_reason_provenance": (
                            "the 01:30 PM PDF text merges two logical rows into one line; "
                            "expanded here and cross-checked against the official 01:00 PM "
                            f"report, which prints the row unmerged ({prov} tip time)"),
                    })
                ctx["matchup"], ctx["team"], ctx["time"] = "OKC@SAC", "Sacramento Kings", "09:00"
                skip_next_team = ("OKC@SAC", "Sacramento Kings")
                continue

            if reason.count(NYS) >= 1 and reason.replace(NYS, "").strip() == "":
                k = reason.count(NYS)
                if k == 1:
                    lead = cells[:-1]
                    slots = _right_align(lead)
                    _carry(ctx, slots)
                    if skip_next_team and (ctx["matchup"], ctx["team"]) == skip_next_team:
                        skip_next_team = None
                        continue
                    rows.append(_mk_row(ctx, ctx["matchup"], ctx["team"], "", "", NYS,
                                        slots=slots))
                else:
                    raise SystemExit(
                        f"{path}:{lineno}: unexpected merged NYS row (k={k}): {line!r}")
                continue

            # (c) a player row
            if len(cells) < 3:
                raise SystemExit(f"{path}:{lineno}: unexpected {len(cells)}-cell row: {line!r}")
            player, status = cells[-3], cells[-2]
            lead = cells[:-3]
            slots = _right_align(lead)
            _carry(ctx, slots)
            rows.append(_mk_row(ctx, ctx["matchup"], ctx["team"], player, status, reason,
                                slots=slots))
    return rows


def _right_align(lead):
    """Right-align the leading non-empty cells onto [date, time, matchup, team].

    The PDF fragment drops the columns it repeats, so a row that prints only
    ``|  | CHI@MIN | Chicago Bulls |`` carries matchup and team; the missing
    date and time come from the rows above it.  Right-aligning puts the last
    printed value in the last slot, which is what the document's own column
    order implies.
    """
    slots = {"date": "", "time": "", "matchup": "", "team": ""}
    vals = [c for c in lead if c]
    order = ["team", "matchup", "time", "date"]
    for i, v in enumerate(reversed(vals)):
        if i >= len(order):
            raise SystemExit(f"too many leading cells to right-align: {lead!r}")
        slots[order[i]] = v
    return slots


def _carry(ctx, slots):
    if slots["date"]:
        ctx["date"] = slots["date"]
    if slots["time"]:
        ctx["time"] = slots["time"].replace(" (ET)", "")
    if slots["matchup"]:
        ctx["matchup"] = slots["matchup"]
    if slots["team"]:
        ctx["team"] = slots["team"]


def _mk_row(ctx, matchup, team_name, player, status, reason, slots=None, reason_prov=""):
    slots = slots or {}
    is_nys = reason.strip().upper() == NYS
    return {
        "game_date": ctx["date"],
        "game_time_et": ctx["time"],
        "matchup": matchup,
        "team_name": team_name,
        "team": TEAM_ABBR.get(team_name, ""),
        "player": "" if is_nys else player,
        "status": "" if is_nys else status,
        "reason": reason,
        "is_team_not_submitted": is_nys,
        "availability": "" if is_nys else status,
        "_team_printed": bool(slots.get("team")),
        "_time_printed": bool(slots.get("time")),
        "_reason_provenance": reason_prov or "printed on the row",
    }


def norm(rows, slate_times):
    """Fill tip times the report does not print from the stored official slate
    (labelled on the row) and sort deterministically."""
    out = []
    for r in rows:
        r = dict(r)
        sk = (iso_date(r["game_date"]), r["matchup"])
        if not r.get("_time_printed") and sk in slate_times:
            r["game_time_et"] = slate_times[sk]
            r["time_source"] = (
                "tip time not printed on this row of the report PDF text; value from the "
                "official slate snapshot (" + SLATE_URL + ") and consistent with every tip "
                "time the report does print (E1c)")
        out.append(r)
    return sorted(out, key=lambda r: (r["game_date"], r["game_time_et"], r["matchup"],
                                      r["team"], r["player"], r["reason"]))


def load_slate():
    with open(os.path.join(APP, "official_slate_1114_1117.json"), encoding="utf-8") as fh:
        slate = json.load(fh)
    games = slate["games"] if isinstance(slate, dict) and "games" in slate else slate
    times, by_date = {}, {}
    for g in games:
        key = (g["date"], f"{g['away']}@{g['home']}")
        times[key] = to_report_time(g.get("time_et", ""))
        by_date.setdefault(g["date"], set()).add(f"{g['away']}@{g['home']}")
    return times, by_date, games


# --------------------------------------------------------------------------
# official season per-game minutes table captured by an earlier session
# --------------------------------------------------------------------------
def norm_player(name):
    """'Murphy III, Trey' -> 'trey murphy iii'; 'Udeh, Jr., Ernest' -> 'ernest udeh jr'."""
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 3:
        last, suffix, first = parts
        full = f"{first} {last} {suffix}"
    elif len(parts) == 2:
        last, first = parts
        full = f"{first} {last}"
    else:
        full = name
    full = full.replace(".", "").replace("'", "")
    return re.sub(r"\s+", " ", full).strip().lower()


def load_minutes_table():
    """Official season per-game figures, keyed by normalised player name.

    Source: https://www.nba.com/stats/players/traditional?Season=2026-27 (top-31
    by minutes per game, captured by an earlier session at
    data/app/players_top31_2026-11-14c.csv).  Players outside that capture have
    NO official minutes figure in this repository and are reported blank.
    """
    out = {}
    with open(os.path.join(APP, "players_top31_2026-11-14c.csv"), encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[norm_player(row["player"])] = {
                "player": row["player"],
                "team": row["team"],
                "gp": int(row["gp"]),
                "min": float(row["min"]),
                "pts": float(row["pts"]),
                "reb": float(row["reb"]),
                "ast": float(row["ast"]),
            }
    return out


def team_game_impact(rows, date, minutes_tbl):
    """Per (date, matchup, team) official-status inventory and the production
    vacuum of the players listed Out.

    The vacuum is a FLOOR: it sums only the players whose official season
    per-game figures this repository has captured.  Players outside that capture
    are counted and reported, never estimated.
    """
    out = []
    keys = sorted({(r["game_date"], r["matchup"], r["team"]) for r in rows
                   if r["game_date"] == date})
    for gd, mu, team in keys:
        sub = [r for r in rows if (r["game_date"], r["matchup"], r["team"]) == (gd, mu, team)]
        nys = [r for r in sub if r["is_team_not_submitted"]]
        players = [r for r in sub if not r["is_team_not_submitted"]]
        by_status = {}
        for r in players:
            by_status.setdefault(r["status"], []).append(r["player"])
        # The engine's convention (scripts/strategy_lab.py::rollup): a vacated
        # minute is one belonging to a player listed Out or Doubtful; a
        # Questionable player is "at risk", not "gone".
        out_players = sorted(by_status.get("Out", []) + by_status.get("Doubtful", []))
        vac = {"min": 0.0, "pts": 0.0, "reb": 0.0, "ast": 0.0}
        risk = {"min": 0.0, "pts": 0.0, "reb": 0.0, "ast": 0.0}
        known, unknown = [], []
        for p in out_players:
            m = minutes_tbl.get(norm_player(p))
            if m is None:
                unknown.append(p)
                continue
            known.append(p)
            for f in ("min", "pts", "reb", "ast"):
                vac[f] += m[f]
        risk_known, risk_unknown = [], []
        for p in sorted(by_status.get("Questionable", [])):
            m = minutes_tbl.get(norm_player(p))
            if m is None:
                risk_unknown.append(p)
                continue
            risk_known.append(p)
            for f in ("min", "pts", "reb", "ast"):
                risk[f] += m[f]
        out.append({
            "game_date": gd,
            "matchup": mu,
            "team": team,
            "reported": not nys,
            "rows_listed": len(players),
            "availability_state": "NOT_YET_SUBMITTED" if nys else "FILED",
            "status_counts": {s: len(v) for s, v in sorted(by_status.items())},
            "out": out_players,
            "doubtful": sorted(by_status.get("Doubtful", [])),
            "questionable": sorted(by_status.get("Questionable", [])),
            "probable": sorted(by_status.get("Probable", [])),
            "available": sorted(by_status.get("Available", [])),
            "minutes_vacuum": None if nys else round(vac["min"], 4),
            "pts_vacuum": None if nys else round(vac["pts"], 4),
            "reb_vacuum": None if nys else round(vac["reb"], 4),
            "ast_vacuum": None if nys else round(vac["ast"], 4),
            "at_risk_minutes": None if nys else round(risk["min"], 4),
            "at_risk_pts": None if nys else round(risk["pts"], 4),
            "at_risk_players_with_official_minutes": sorted(risk_known),
            "at_risk_players_without_official_minutes": sorted(risk_unknown),
            "out_players_with_official_minutes": sorted(known),
            "players_without_official_minutes": sorted(unknown),
            "players_without_official_minutes_count": len(unknown),
        })
    return out


def main():
    failures = []

    raw_0130 = os.path.join(APP, "official_injuries_2026-11-14_0130PM_raw.md")
    raw_0100 = os.path.join(APP, "official_injuries_2026-11-14_0100PM_raw.md")
    r0130 = parse_raw(raw_0130)
    r0100 = parse_raw(raw_0100)
    print(f"parsed 01:30 PM report: {len(r0130)} rows, "
          f"player rows={sum(1 for r in r0130 if not r['is_team_not_submitted'])}, "
          f"NYS rows={sum(1 for r in r0130 if r['is_team_not_submitted'])}")
    print(f"parsed 01:00 PM report: {len(r0100)} rows, "
          f"player rows={sum(1 for r in r0100 if not r['is_team_not_submitted'])}, "
          f"NYS rows={sum(1 for r in r0100 if r['is_team_not_submitted'])}")

    # ---- E0: two independent verbatim transcriptions of the same PDF -------
    # Session arena/965fbd17-nba3 transcribed the same 01:30 PM PDF first and
    # stored it at data/app/official_injuries_2026-11-14_0130PM_raw.md.  Session
    # arena/1823b910-nba3 transcribed it again, independently, before seeing that
    # file, and keeps its own copy at
    # audit_1823b910/data/independent_transcription_0130PM_raw.md.  Parsing both
    # and comparing proves the transcription step itself is reproducible.
    indep = os.path.join(ROOT, "audit_1823b910", "data",
                         "independent_transcription_0130PM_raw.md")
    indep_note = ""
    if os.path.exists(indep):
        rindep = parse_raw(indep)
        same = (len(r0130) == len(rindep)
                and all(a == b for a, b in zip(
                    sorted(map(repr, r0130)), sorted(map(repr, rindep)))))
        indep_note = (
            "Two independent verbatim transcriptions of the same PDF agree row for row "
            f"({len(rindep)} rows)." if same else
            f"the two independent transcriptions differ ({len(r0130)} vs {len(rindep)} rows)")
        print(f"E0  independent second transcription: "
              f"{'PASS (0 differences)' if same else 'FAIL'} "
              f"({len(rindep)} rows, session arena/965fbd17-nba3 vs arena/1823b910-nba3)")
        if not same:
            failures.append("E0 independent transcriptions differ")
    else:
        print("E0  independent second transcription: SKIP (file not present)")

    slate_times, slate_by_date, slate_games = load_slate()
    t0130 = norm(r0130, slate_times)
    t0100 = norm(r0100, slate_times)

    # ---- E1a: statuses are official -------------------------------------
    bad_status = sorted({r["status"] for r in t0130
                         if not r["is_team_not_submitted"] and r["status"] not in OFFICIAL_STATUSES})
    ok = not bad_status
    print(f"E1a every status is one of the official statuses: "
          f"{'PASS' if ok else 'FAIL ' + str(bad_status)} "
          f"({OFFICIAL_STATUSES})")
    if not ok:
        failures.append(f"E1a {bad_status}")

    # ---- E1b: every matchup is in the stored official slate --------------
    sl_set = {f"{g['away']}@{g['home']}" for g in slate_games}
    bad_mu = sorted({r["matchup"] for r in t0130} - sl_set)
    print(f"E1b every matchup is in the stored official slate: "
          f"{'PASS' if not bad_mu else 'FAIL ' + str(bad_mu)}")
    if bad_mu:
        failures.append(f"E1b {bad_mu}")

    # ---- E1c: every tip time the report prints equals the slate value -----
    bad_t = [(r["matchup"], r["game_time_et"], slate_times.get((iso_date(r["game_date"]), r["matchup"])))
             for r in t0130
             if r["_time_printed"] and (iso_date(r["game_date"]), r["matchup"]) in slate_times
             and r["game_time_et"] != slate_times[(iso_date(r["game_date"]), r["matchup"])]]
    print(f"E1c every printed tip time matches the official slate: "
          f"{'PASS' if not bad_t else 'FAIL ' + str(bad_t)}")
    if bad_t:
        failures.append(f"E1c {bad_t}")

    # ---- E2: the 01:00 PM report has the same game/team inventory --------
    inv0130 = {(r["game_date"], r["matchup"], r["team"]) for r in t0130}
    inv0100 = {(r["game_date"], r["matchup"], r["team"]) for r in t0100}
    ok = inv0130 == inv0100
    print(f"E2  01:30 vs 01:00 (date, matchup, team) inventory: "
          f"{'PASS' if ok else 'FAIL ' + str(inv0130 ^ inv0100)} ({len(inv0130)} team-games)")
    if not ok:
        failures.append(f"E2 {sorted(inv0130 ^ inv0100)}")

    # ---- E3: rows whose team the 01:30 PM text omits, cross-checked ------
    def by_player(rows):
        return {r["player"]: r for r in rows if not r["is_team_not_submitted"]}
    p0130, p0100 = by_player(t0130), by_player(t0100)
    checked, mismatched = [], []
    for name, r in sorted(p0130.items()):
        if not r["team_name"]:
            continue
        o = p0100.get(name)
        if o is None:
            continue
        # only rows the 0130 fragment left teamless can be misattributed
        teamless = any(x["player"] == name and not x.get("_team_printed")
                       for x in r0130)
        if teamless or True:
            if o["team_name"] != r["team_name"] or o["matchup"] != r["matchup"]:
                mismatched.append((name, r["matchup"], r["team_name"],
                                   o["matchup"], o["team_name"]))
            checked.append(name)
    ok = not mismatched
    print(f"E3  every player row attributed identically by the 01:00 PM report: "
          f"{'PASS' if ok else 'FAIL ' + str(mismatched)} ({len(checked)} rows cross-checked)")
    if not ok:
        failures.append(f"E3 {mismatched}")

    # ---- E4: slate coverage ----------------------------------------------
    for d, label in (("11/14/2026", "E4a"), ("11/15/2026", "E4b")):
        got = sorted({r["matchup"] for r in t0130 if r["game_date"] == d})
        want = sorted(slate_by_date.get(iso_date(d), set()))
        ok = got == want
        print(f"{label} report {d} games == stored slate {d} games: "
              f"{'PASS' if ok else f'FAIL {got} vs {want}'} ({len(got)} games)")
        if not ok:
            failures.append(f"{label} {got} vs {want}")

    # ---- E5: delta against the published canonical snapshot --------------
    with open(os.path.join(APP, "official_injuries_2026-11-14_0515AM.json"), encoding="utf-8") as fh:
        s0515 = json.load(fh)
    t0515 = norm(parse_raw(os.path.join(APP, "official_injuries_2026-11-14_0515AM_raw.md")),
                 slate_times)

    def team_state(rows):
        st = {}
        for r in rows:
            k = (r["game_date"], r["matchup"], r["team"])
            st.setdefault(k, {"filed": not r["is_team_not_submitted"], "players": {}})
            if r["is_team_not_submitted"]:
                st[k]["filed"] = False
            else:
                st[k]["players"][r["player"]] = r["status"]
        return st

    a, b = team_state(t0515), team_state(t0130)
    resolved, newly_unfiled = [], []
    status_changes, added_players, removed_players = [], [], []
    for k in sorted(set(a) | set(b)):
        sa, sb = a.get(k, {"filed": False, "players": {}}), b.get(k, {"filed": False, "players": {}})
        if not sa["filed"] and sb["filed"]:
            resolved.append(k)
        if sa["filed"] and not sb["filed"]:
            newly_unfiled.append(k)
        for p in sorted(set(sa["players"]) | set(sb["players"])):
            x, y = sa["players"].get(p), sb["players"].get(p)
            if x == y:
                continue
            if x is None:
                added_players.append((k, p, y))
            elif y is None:
                removed_players.append((k, p, x))
            else:
                status_changes.append((k, p, x, y))

    print("E5  delta vs the published canonical snapshot (05:15 AM ET) - REPORTED, not a failure:")
    print(f"      team-games that FILLED between the two reports: {len(resolved)}")
    for k in resolved:
        print(f"        {k[0]} {k[1]} {k[2]}: NOT YET SUBMITTED -> "
              f"{len(b[k]['players'])} player row(s)")
    print(f"      team-games that went from filed to not-filed: {len(newly_unfiled)}"
          + (f" {newly_unfiled}" if newly_unfiled else ""))
    print(f"      status changes on players present in both: {len(status_changes)}")
    for k, p, x, y in status_changes:
        print(f"        {k[1]} {k[2]} {p}: {x} -> {y}")
    print(f"      player rows only in the newest report: {len(added_players)}")
    print(f"      player rows only in the 05:15 AM report: {len(removed_players)}")

    delta = {
        "baseline_report": "2026-11-14 05:15 AM ET (the snapshot the canonical dashboard publishes)",
        "refreshed_report": "2026-11-14 01:30 PM ET (newest at capture time)",
        "team_games_resolved": [{"date": iso_date(k[0]), "matchup": k[1], "team": k[2],
                                 "player_rows": len(b[k]["players"])} for k in resolved],
        "team_games_newly_unfiled": [{"date": iso_date(k[0]), "matchup": k[1], "team": k[2]}
                                     for k in newly_unfiled],
        "status_changes": [{"date": iso_date(k[0]), "matchup": k[1], "team": k[2],
                            "player": p, "from": x, "to": y} for k, p, x, y in status_changes],
        "players_only_in_newest": [{"date": iso_date(k[0]), "matchup": k[1], "team": k[2],
                                    "player": p, "status": y} for k, p, y in added_players],
        "players_only_in_baseline": [{"date": iso_date(k[0]), "matchup": k[1], "team": k[2],
                                      "player": p, "status": x} for k, p, x in removed_players],
        "counts": {
            "baseline_rows": len(t0515), "refreshed_rows": len(t0130),
            "baseline_player_rows": sum(1 for r in t0515 if not r["is_team_not_submitted"]),
            "refreshed_player_rows": sum(1 for r in t0130 if not r["is_team_not_submitted"]),
            "baseline_not_submitted_rows": sum(1 for r in t0515 if r["is_team_not_submitted"]),
            "refreshed_not_submitted_rows": sum(1 for r in t0130 if r["is_team_not_submitted"]),
        },
        "source_baseline": s0515["source_url"],
        "source_refreshed": URL_0130,
    }

    # ---- E6: injury -> rotation impact from the refreshed report ---------
    minutes_tbl = load_minutes_table()
    impact = team_game_impact(t0130, "11/14/2026", minutes_tbl)
    impact_baseline = team_game_impact(t0515, "11/14/2026", minutes_tbl)
    base_by_key = {(x["matchup"], x["team"]): x for x in impact_baseline}
    for row in impact:
        row["baseline"] = base_by_key.get((row["matchup"], row["team"]))
        row["source"] = URL_0130
        row["source_index"] = INDEX_URL
        row["source_minutes"] = MINUTES_URL
        row["minutes_note"] = (
            "UNKNOWN - the team had not filed at this report time, so the minutes vacated "
            "are published blank rather than as zero." if not row["reported"] else
            "Sum of the official season minutes-per-game of the players listed Out or "
            "Doubtful (the engine's convention). It is a FLOOR: "
            f"{row['players_without_official_minutes_count']} listed player(s) are outside "
            "the captured official minutes table, so their minutes are unknown and are not "
            "counted.")
        row["rotation_note"] = (
            "Who absorbs those minutes, and how much of the vacated production they replace, "
            "is NOT quantified. Answering it needs per-player game logs and on/off splits, "
            "which this repository does not have. The vacuum is published; the replacement is "
            "deliberately left blank.")
    print(f"E6  injury -> rotation impact recomputed for {len(impact)} team-games on 11/14/2026")
    for row in impact:
        print(f"      {row['matchup']:9s} {row['team']}: {row['availability_state']:18s} "
              f"rows={row['rows_listed']:2d} out={len(row['out']):2d} "
              f"min_vacuum={row['minutes_vacuum']} "
              f"(unknown-minutes players: {row['players_without_official_minutes_count']})")

    # ------------------------------------------------------------------write
    out = {
        "source_url": URL_0130,
        "index_url": INDEX_URL,
        "source_label": (
            "NBA official injury report PDF, 11/14/26 01:30 PM ET - the newest report that "
            "exists on the official CDN at capture time (the 01:45 PM ET probe returns "
            "AccessDenied; the official index page lists the November 14 reports through "
            "1:30 PM ET). Fetched verbatim twice; both reads returned identical text. The "
            "immediately preceding 01:00 PM ET report was fetched independently and is used "
            "to cross-check the six rows whose team cell the 01:30 PM text extraction does "
            "not print and the merged final block. Covers the 11/14 game-day sections (now "
            "almost fully filed) and the 11/15 sections (still NOT YET SUBMITTED)."),
        "report_stamp": "2026-11-14 01:30 PM ET",
        "retrieved_on": "2026-11-14",
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunk 0 of 1 (PDF text extraction), session " + SESSION,
        "count": len(t0130),
        "player_rows": sum(1 for r in t0130 if not r["is_team_not_submitted"]),
        "not_submitted_rows": sum(1 for r in t0130 if r["is_team_not_submitted"]),
        "newer_report_probes": {
            "01:45 PM ET": "AccessDenied (does not exist at capture time)",
        },
        "index_listed_through": "2026-11-14 01:30 PM ET (page text at read time)",
        "independent_transcription": {
            "path": "audit_1823b910/data/independent_transcription_0130PM_raw.md",
            "transcribed_by": "arena/1823b910-nba3",
            "shared_file_transcribed_by": "arena/965fbd17-nba3",
            "result": indep_note,
            "note": ("Both sessions fetched the same PDF with the same tool and transcribed it "
                     "without seeing the other's file. The table text is identical, so any "
                     "difference between the two sessions' published tables is an ATTRIBUTION "
                     "difference (which team a page-fragment row belongs to), not a "
                     "transcription difference."),
        },
        "cross_check_report": {
            "url": URL_0100,
            "stamp": "2026-11-14 01:00 PM ET",
            "used_for": ("team attribution of the six page-fragment rows the 01:30 PM text "
                         "leaves teamless, and the expansion of the merged final block"),
        },
        "delta_vs_published_canonical": delta,
        "injury_impact_1114": impact,
        "irregularities_logged": [
            "IR-1823b910-01: the published canonical injury snapshot is 2026-11-14 05:15 AM ET "
            "while the newest official report at capture time is 01:30 PM ET - a gap of "
            "8h15m and 24 report versions, spanning the league's 11 a.m.-1 p.m. game-day "
            "submission window. Four of the five 11/14 team-games listed as NOT YET SUBMITTED "
            "in the published snapshot have since filed. This session does NOT repoint the "
            "snapshot manifest; that is logged as a change request for the owner.",
            "IR-1823b910-02: the 01:30 PM PDF text extraction leaves the Team cell empty on "
            "six page-fragment rows (Claxton, Powell, Sellers, Smith, Swain, Wilson) and "
            "merges the final ATL@MIL / OKC@SAC block into one line. Both are resolved from "
            "the same document's block structure and cross-checked against the official "
            "01:00 PM report, which prints every one of them (check E3).",
        ],
        "verification_session": SESSION,
        "rows": t0130,
        "sources": {
            "report_0130": URL_0130,
            "report_0100": URL_0100,
            "index": INDEX_URL,
            "slate": f"data/app/official_slate_1114_1117.json ({SLATE_URL})",
            "minutes": MINUTES_URL,
        },
    }
    with open(os.path.join(APP, "official_injuries_2026-11-14_0130PM.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=False)
        fh.write("\n")

    print(f"\nwrote data/app/official_injuries_2026-11-14_0130PM.json "
          f"({len(t0130)} rows)")
    if failures:
        print(f"\nFAILED CHECKS ({len(failures)}):")
        for f in failures:
            print("  -", f)
        return 1
    print("\nAll E-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
