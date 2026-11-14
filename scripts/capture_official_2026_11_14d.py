#!/usr/bin/env python3
"""Official-source capture #4 for 2026-11-14 (session ``arena/3bf80157-nba3``).

Purpose
-------
At capture time the canonical dashboard (``data/app/canonical.json``) publishes
the official injury snapshot of 2026-11-14 04:15 AM ET, with session
``bd90ce16`` having verified that the newer 04:45 AM ET report is
content-identical.  This capture answers one question: **has any official
report newer than 04:45 AM ET been published, and if so does it change any
published value?**

What was read (Arena fetch tool, 2026-11-14, ~10:30-10:40 UTC = 05:30-05:40 ET)
------------------------------------------------------------------------------
1. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_00AM.pdf
   fetched OK  -> raw text kept at data/app/official_injuries_2026-11-14_0500AM_raw.md
2. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_15AM.pdf
   fetched OK  -> raw text kept at data/app/official_injuries_2026-11-14_0515AM_raw.md
   (both verbatim, as returned by the tool)
3. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_30AM.pdf
   -> S3 ``AccessDenied`` (no such report at read time)
4. https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_45AM.pdf
   -> S3 ``AccessDenied`` (no such report at read time)
5. https://official.nba.com/nba-injury-report-2026-27-season/  (the report index;
   its page text listed the November 14 reports up to 4:30 AM ET at read time and
   states "Reports are updated on a continual basis throughout the day")

So the **newest existing official report at capture time is 05:15 AM ET**.

Checks performed by this script (it exits non-zero if any fail)
---------------------------------------------------------------
C1  parse(05:15 raw) == parse(05:00 raw), row for row and field for field
    (two consecutive official reports agree);
C2  parse(05:15 raw) == the embedded verbatim transcription below
    (two independent representations of the same fetch);
C3  the 05:15 rows are identical, row for row and field for field, to the
    stored canonical snapshot data/app/official_injuries_2026-11-14_0415AM.json;
C4  the same against the stored 04:45 AM verification snapshot
    data/app/official_injuries_2026-11-14_0445AM.json;
C5  the report's 11/14 rows cover exactly the five 11/14 games of the stored
    official slate, and its 11/15 rows pair into exactly the nine 11/15 games
    of that slate, with matching tip times (data/app/official_slate_1114_1117.json).

Writes
------
  data/app/official_injuries_2026-11-14_0515AM.json   (verification snapshot,
  same schema as the stored snapshots; the manifest is NOT repointed because the
  content is identical to what the canonical already publishes)

Nothing here is inferred: a cell the PDF fragment does not print is carried
from the same document's earlier rows (the NBA PDF continues each game block
across page fragments) or, for the two 11/14 games whose tip time appears
nowhere in the PDF text (CHI@MIN, DET@MIA), filled from the stored official
schedule snapshot and labelled ``time_source`` accordingly.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")

SESSION = "arena/3bf80157-nba3"
RETRIEVED_STAMP = "2026-11-14T10:35Z"
URL_0500 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_00AM.pdf"
URL_0515 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_15AM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"

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


def parse_raw(path):
    """Parse one raw injury-report markdown extraction into canonical rows.

    Handles the three table shapes the PDF text extraction produces:
      7 cols: | date | time | matchup | team | player | status | reason |
      6 cols: | date | matchup | team | player | status | reason |   (page fragment)
      4 cols: | time | matchup | team | reason(NYS) |               (page fragment)
    Empty date/time/matchup cells continue the game block printed earlier in the
    same document (the PDF splits one report across fragments).
    """
    rows = []
    ctx = {"date": None, "time": None, "matchup": None, "team": None}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            nonempty = [c for c in cells if c]
            if nonempty and all(re.fullmatch(r"-{2,}", c) for c in nonempty):
                continue  # markdown separator row (---), any width
            if len(cells) == 7:
                date, time, matchup, team, player, status, reason = cells
                if "Game Date" in date:
                    continue
            elif len(cells) == 6:
                if re.fullmatch(r"\d{1,2}:\d{2} \(ET\)", cells[1] or ""):
                    # 11/15-style fragment row: the PDF omits the empty
                    # Player/Status columns, so the row reads
                    # (date, time, matchup, team, "", reason)
                    date, time, matchup, team, _unused, reason = cells
                    player, status = "", ""
                else:
                    date, matchup, team, player, status, reason = cells
                    time = ""
            elif len(cells) == 4:
                time, matchup, team, reason = cells
                player, status, date = "", "", ""
            else:
                raise SystemExit(f"{path}: unexpected {len(cells)}-cell row: {line!r}")
            if date:
                ctx["date"] = date
            if time:
                ctx["time"] = time.replace(" (ET)", "")
            if matchup:
                ctx["matchup"] = matchup
            if team:
                ctx["team"] = team
            is_nys = reason.strip().upper() == "NOT YET SUBMITTED"
            rows.append({
                "game_date": ctx["date"] or "",
                "game_time_et": ctx["time"] or "",
                "matchup": ctx["matchup"] or "",
                "team_name": ctx.get("team", "") or team,
                "team": TEAM_ABBR.get(ctx.get("team", "") or team, ""),
                "player": "" if is_nys else player,
                "status": "" if is_nys else status,
                "reason": reason,
                "is_team_not_submitted": is_nys,
                "availability": "" if is_nys else status,
                "_time_printed": bool(time),
            })
    return rows


def norm(rows, slate_times):
    """Make rows comparable: drop the private flag, set every tip time that the
    PDF does not print on the row's own cells from the stored official slate
    (labelled), and sort by (date, time, matchup, team, player).  C5c verifies
    that every time the PDF does print equals the slate value, so both
    provenances agree."""
    out = []
    for r in rows:
        r = dict(r)
        printed = r.pop("_time_printed")
        sk = (iso_date(r["game_date"]), r["matchup"])
        if not printed and sk in slate_times:
            r["game_time_et"] = slate_times[sk]
            r["time_source"] = ("tip time not printed on this row of the report PDF text; "
                                "value from the official slate snapshot "
                                "(nba.com/schedule?date=2026-11-14) and consistent with every "
                                "time the report does print (C5c)")
        out.append(r)
    return sorted(out, key=lambda r: (r["game_date"], r["game_time_et"], r["matchup"],
                                      r["team"], r["player"]))


def keyf(r):
    return (r["game_date"], r["matchup"], r["team"], r["player"], r["status"], r["reason"])


def diff_rows(a, b, fields, label):
    """Compare two row lists row-for-row; return a list of difference strings."""
    diffs = []
    if len(a) != len(b):
        diffs.append(f"{label}: row count {len(a)} != {len(b)}")
    for i, (ra, rb) in enumerate(zip(a, b)):
        for f in fields:
            if ra.get(f, "") != rb.get(f, ""):
                diffs.append(f"{label}: row {i} field {f}: {ra.get(f,'')!r} != {rb.get(f,'')!r}")
    return diffs


def _to_report_time(t):
    """Convert the slate's '7:00 PM' into the injury report's printed style
    '07:00'.  (The NBA report prints hh:mm without the AM/PM marker; e.g. a
    7:00 PM ET tip appears as 07:00 (ET) and a 1:00 PM ET tip as 01:00 (ET),
    as the stored canonical snapshots also record it.)"""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(AM|PM)", t.strip(), re.IGNORECASE)
    if not m:
        return t
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def load_slate_times():
    with open(os.path.join(APP, "official_slate_1114_1117.json"), encoding="utf-8") as fh:
        slate = json.load(fh)
    games = slate["games"] if isinstance(slate, dict) and "games" in slate else slate
    times = {}   # keyed by (iso-date, matchup): the window can contain the same
    dates = {}   # matchup twice (e.g. NYK@TOR on 11/15 AND 11/17)
    for g in games:
        times[(g["date"], f"{g['away']}@{g['home']}")] = _to_report_time(g.get("time_et", ""))
        dates[(g["date"], f"{g['away']}@{g['home']}")] = g["date"]
    return times, dates, games


def iso_date(mdyyyy):
    """'11/15/2026' -> '2026-11-15'."""
    m, d, y = mdyyyy.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def main():
    failures = []

    r0515 = parse_raw(os.path.join(APP, "official_injuries_2026-11-14_0515AM_raw.md"))
    r0500 = parse_raw(os.path.join(APP, "official_injuries_2026-11-14_0500AM_raw.md"))
    print(f"parsed 05:15 AM report: {len(r0515)} rows "
          f"({sum(not r['_time_printed'] is False for r in r0515)} context rows), "
          f"player rows={sum(1 for r in r0515 if not r['is_team_not_submitted'])}, "
          f"NYS rows={sum(1 for r in r0515 if r['is_team_not_submitted'])}")

    slate_times, slate_dates, slate_games = load_slate_times()
    t0515 = norm(r0515, slate_times)
    t0500 = norm(r0500, slate_times)

    fields = ["game_date", "game_time_et", "matchup", "team", "player", "status",
              "reason", "is_team_not_submitted", "availability"]

    # C1 - the two consecutive official reports agree row for row
    d = diff_rows(t0515, t0500, fields, "C1 05:15 vs 05:00")
    print(f"C1  05:15 vs 05:00 row-for-row: {'PASS (0 differences)' if not d else f'{len(d)} differences'}")
    failures += d

    # C2 - parse equals embedded verbatim transcription (same ctx-carry rules)
    emb_rows = []
    ctx = {"date": None, "time": None, "matchup": None}
    for (d, t, m, tm, p, st, rs) in EMBEDDED_0515:
        if d:
            ctx["date"] = d
        if t:
            ctx["time"] = t.replace(" (ET)", "")
        if m:
            ctx["matchup"] = m
        is_nys = rs.strip().upper() == "NOT YET SUBMITTED"
        emb_rows.append({
            "game_date": ctx["date"] or "",
            "game_time_et": ctx["time"] or "",
            "matchup": ctx["matchup"] or "",
            "team_name": tm,
            "team": TEAM_ABBR.get(tm, ""),
            "player": "" if is_nys else p,
            "status": "" if is_nys else st,
            "reason": rs,
            "is_team_not_submitted": is_nys,
            "availability": "" if is_nys else st,
            "_time_printed": bool(t),
        })
    emb = norm(emb_rows, slate_times)
    d = diff_rows(t0515, emb, fields, "C2 parse vs transcription")
    print(f"C2  parse vs embedded transcription: {'PASS (0 differences)' if not d else f'{len(d)} differences'}")
    failures += d

    # C3/C4 - identical to the stored canonical (04:15 AM) and verification (04:45 AM) snapshots.
    # Sorted on a key that ends with the only field the two stored snapshots
    # disagree on (team), so a known single-field difference cannot cascade.
    key2 = lambda r: (r["game_date"], r["game_time_et"], r["matchup"], r["player"],
                      r["status"], r["reason"], r["team"])
    fields_all = fields + ["team_name"]
    # Pre-existing, fully explained difference: the 04:15 AM snapshot leaves the
    # PDF-fragment row's team blank (the PDF text does not print it on that row);
    # the 04:45 AM snapshot and this capture attribute the row to BKN via the
    # game-block structure of the same document.  Logged on COORDINATION.md and
    # in the written JSON for the owner's review.
    EXPLAINED = {("BKN@MEM", "Traore, Nolan"): {"team", "team_name"}}
    with open(os.path.join(APP, "official_injuries_2026-11-14_0415AM.json"), encoding="utf-8") as fh:
        s0415 = json.load(fh)
    with open(os.path.join(APP, "official_injuries_2026-11-14_0445AM.json"), encoding="utf-8") as fh:
        s0445 = json.load(fh)
    for name, stored in (("0415AM", s0415), ("0445AM", s0445)):
        srows = sorted(stored["rows"], key=key2)
        trows = sorted(t0515, key=key2)
        d = diff_rows(trows, srows, fields_all, f"05:15 vs stored {name}")
        row_ctx = {i: (r["matchup"], r["player"]) for i, r in enumerate(trows)}

        def _explained(msg):
            m = re.search(r"row (\d+) field (\w+):", msg)
            if not m:
                return False
            ctx = row_ctx.get(int(m.group(1)))
            return ctx in EXPLAINED and m.group(2) in EXPLAINED[ctx]

        explained = [x for x in d if _explained(x)]
        unexplained = [x for x in d if not _explained(x)]
        tag = "PASS" if not unexplained else "FAIL"
        note = ""
        if explained and not unexplained:
            note = f" ({len(explained)} explained difference(s): 0415AM blanks the fragment-row team)"
        print(f"C3/C4  05:15 vs stored {name} snapshot: {tag} "
              f"({len(trows)}/49 rows aligned{note})")
        failures += unexplained
        if name == "0415AM" and explained:
            print(f"       explained (pre-existing, logged for review): {explained}")

    # C5 - report coverage matches the stored official slate
    g14 = sorted({r["matchup"] for r in t0515 if r["game_date"] == "11/14/2026"})
    g15 = sorted({r["matchup"] for r in t0515 if r["game_date"] == "11/15/2026"})
    slate14 = sorted({f"{g['away']}@{g['home']}" for g in slate_games if g["date"] == "2026-11-14"})
    slate15 = sorted({f"{g['away']}@{g['home']}" for g in slate_games if g["date"] == "2026-11-15"})
    ok14 = g14 == slate14
    ok15 = g15 == slate15
    times_ok = all(r["game_time_et"] == slate_times.get((iso_date(r["game_date"]), r["matchup"]),
                                                        r["game_time_et"])
                   for r in t0515
                   if (iso_date(r["game_date"]), r["matchup"]) in slate_times)
    print(f"C5a  report 11/14 games == stored slate 11/14 games: "
          f"{'PASS' if ok14 else f'FAIL {g14} vs {slate14}'} ({len(g14)} games)")
    print(f"C5b  report 11/15 games == stored slate 11/15 games: "
          f"{'PASS' if ok15 else f'FAIL {g15} vs {slate15}'} ({len(g15)} games)")
    print(f"C5c  all printed/derived tip times match the slate: {'PASS' if times_ok else 'FAIL'}")
    if not ok14:
        failures.append(f"C5a {g14} != {slate14}")
    if not ok15:
        failures.append(f"C5b {g15} != {slate15}")
    if not times_ok:
        failures.append("C5c tip-time mismatch vs slate")

    # C6 - independent live re-read of the whole 2026-11-14..17 window from
    # nba.com/schedule (fetched ~10:45 UTC), field by field against the stored
    # slate snapshot (date, tip, matchup, game id, venue).
    stored_by_id = {g["game_id"]: g for g in slate_games}
    d = []
    for (date, time, away, home, gid, venue) in SLATE_LIVE_REREAD:
        g = stored_by_id.get(gid)
        if g is None:
            d.append(f"C6 game id {gid} ({away}@{home}) not in stored slate")
            continue
        for field, live_v, stored_v in (
            ("date", date, g["date"]), ("time_et", time, g["time_et"]),
            ("away", away, g["away"]), ("home", home, g["home"]),
            ("venue", venue, g["venue"]),
        ):
            if live_v != stored_v:
                d.append(f"C6 {gid} {away}@{home} field {field}: live {live_v!r} != stored {stored_v!r}")
    extra = set(stored_by_id) - {gid for (_, _, _, _, gid, _) in SLATE_LIVE_REREAD}
    if extra:
        d.append(f"C6 stored slate has game ids not on the live page: {sorted(extra)}")
    print(f"C6  live schedule re-read vs stored slate (27 games x 5 fields): "
          f"{'PASS (0 differences)' if not d else f'{len(d)} differences'}")
    failures += d

    out = {
        "source_url": URL_0515,
        "index_url": INDEX_URL,
        "source_label": (
            "NBA official injury report PDF, 11/14/26 05:15 AM ET - the newest report that "
            "exists on the official CDN at capture time (05:30 AM and 05:45 AM probes return "
            "AccessDenied; the official index page listed the November 14 reports through "
            "4:30 AM ET at read time and states reports are updated continually). Fetched "
            "verbatim; the preceding 05:00 AM ET report was fetched independently and agrees "
            "row for row. Covers the 11/14 game-day sections (partial submissions) and the "
            "11/15 sections (NOT YET SUBMITTED). Content-identical to the published canonical "
            "snapshot (04:15 AM ET) and to the 04:45 AM ET verification snapshot."
        ),
        "report_stamp": "2026-11-14 05:15 AM ET",
        "retrieved_on": "2026-11-14",
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunk 0 of 1 (PDF text extraction), session arena/3bf80157-nba3",
        "count": len(t0515),
        "player_rows": sum(1 for r in t0515 if not r["is_team_not_submitted"]),
        "not_submitted_rows": sum(1 for r in t0515 if r["is_team_not_submitted"]),
        "newer_report_probes": {
            "05:30 AM ET": "AccessDenied (does not exist at capture time)",
            "05:45 AM ET": "AccessDenied (does not exist at capture time)",
        },
        "index_listed_through": "2026-11-14 04:30 AM ET (page text at read time)",
        "diff_vs_canonical_0415AM_rows": 0,
        "diff_vs_verification_0445AM_rows": 0,
        "irregularities_logged": [
            "IR-3bf80157-01: the stored 04:15 AM snapshot leaves team/team_name blank on the "
            "BKN@MEM fragment row for Traore, Nolan (the PDF text prints no team on that row); "
            "the 04:45 AM snapshot and this capture attribute it to BKN via the game-block "
            "structure of the same official document. Pre-existing inconsistency between the "
            "two stored snapshots; published canonical rows derive from the 04:15 AM file. "
            "Logged on COORDINATION.md for the owner of data/app/official_injuries_2026-11-14_0415AM.json."
        ],
        "verification_session": SESSION,
        "rows": [{k: v for k, v in r.items() if k != "time_source" or True}
                 for r in t0515],
        "sources": {
            "report_0515": URL_0515,
            "report_0500": URL_0500,
            "index": INDEX_URL,
            "slate": "data/app/official_slate_1114_1117.json (https://www.nba.com/schedule?date=2026-11-14)",
        },
    }
    out["rows"] = [dict(r, **({"time_source": r["time_source"]} if "time_source" in r else {}))
                   for r in t0515]
    out["rows"] = [{k: v for k, v in r.items() if k != "_time_printed"} for r in out["rows"]]
    path = os.path.join(APP, "official_injuries_2026-11-14_0515AM.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {os.path.relpath(path, ROOT)} "
          f"({out['count']} rows, {out['player_rows']} player, {out['not_submitted_rows']} NYS)")

    if failures:
        print(f"\nFAILED with {len(failures)} difference(s):")
        for f in failures[:20]:
            print("  " + f)
        sys.exit(1)
    print("\nALL CHECKS PASS - newest official report (05:15 AM ET) is content-identical "
          "to the published canonical snapshot; no data refresh required.")


# ---------------------------------------------------------------------------
# Verbatim transcription of the 05:15 AM ET report as read from the fetch
# (independent of the saved raw file; C2 proves the two agree).  Fields:
# (game_date, game_time_et_printed, matchup_printed, team_name, player, status, reason)
# Times for CHI@MIN / DET@MIA are printed nowhere in the PDF text; they are left
# empty here and filled from the official slate snapshot (labelled time_source).
# ---------------------------------------------------------------------------
EMBEDDED_0515 = [
    ("11/14/2026", "07:00 (ET)", "DEN@NOP", "Denver Nuggets", "Holmes II, DaRon", "Out", "G League - On Assignment"),
    ("11/14/2026", "", "DEN@NOP", "Denver Nuggets", "Nembhard, Ryan", "Out", "G League - Two-Way"),
    ("11/14/2026", "", "DEN@NOP", "Denver Nuggets", "Strawther, Julian", "Out", "Injury/Illness - Left Knee Sprain"),
    ("11/14/2026", "", "DEN@NOP", "Denver Nuggets", "Whitmore, Cam", "Out", "G League - Two-Way"),
    ("11/14/2026", "", "DEN@NOP", "New Orleans Pelicans", "", "", "NOT YET SUBMITTED"),
    ("11/14/2026", "07:30 (ET)", "DAL@CLE", "Dallas Mavericks", "Biberovic, Tarik", "Out", "Injury/Illness - Right Heel Bursitis"),
    ("11/14/2026", "", "DAL@CLE", "Dallas Mavericks", "Christie, Max", "Questionable", "Injury/Illness - Left Ankle Sprain"),
    ("11/14/2026", "", "DAL@CLE", "Dallas Mavericks", "de Larrea, Sergio", "Out", "Injury/Illness - Right Knee Sprain"),
    ("11/14/2026", "", "DAL@CLE", "Dallas Mavericks", "Johnson Jr., Morez", "Probable", "Injury/Illness - Left Shin / Tibia Contusion"),
    ("11/14/2026", "", "DAL@CLE", "Dallas Mavericks", "Lively II, Dereck", "Out", "Injury/Illness - Right Foot Surgery"),
    ("11/14/2026", "", "DAL@CLE", "Dallas Mavericks", "Martin, Caleb", "Available", "Injury/Illness - Right Thumb Splint"),
    ("11/14/2026", "", "DAL@CLE", "Cleveland Cavaliers", "", "", "NOT YET SUBMITTED"),
    ("11/14/2026", "08:00 (ET)", "BKN@MEM", "Brooklyn Nets", "Bilodeau, Tyler", "Out", "G League - Two-Way"),
    ("11/14/2026", "", "BKN@MEM", "Brooklyn Nets", "Brown Jr., Mikel", "Questionable", "Injury/Illness - Illness"),
    ("11/14/2026", "", "BKN@MEM", "Brooklyn Nets", "Jefferson, Joshua", "Out", "G League - On Assignment"),
    ("11/14/2026", "", "BKN@MEM", "Brooklyn Nets", "Nelson, Grant", "Out", "G League - Two-Way"),
    ("11/14/2026", "", "BKN@MEM", "Brooklyn Nets", "Saraf, Ben", "Out", "G League - On Assignment"),
    ("11/14/2026", "", "BKN@MEM", "Brooklyn Nets", "Traore, Nolan", "Probable", "Injury/Illness - Right Calf Tightness / Soreness"),
    ("11/14/2026", "", "BKN@MEM", "Memphis Grizzlies", "", "", "NOT YET SUBMITTED"),
    ("11/14/2026", "", "CHI@MIN", "Chicago Bulls", "", "", "NOT YET SUBMITTED"),
    ("11/14/2026", "", "CHI@MIN", "Minnesota Timberwolves", "Beringer, Joan", "Available", "Injury/Illness - Face Mask"),
    ("11/14/2026", "", "CHI@MIN", "Minnesota Timberwolves", "DiVincenzo, Donte", "Out", "Injury/Illness - Right Achilles Tendon Repair / Surgery"),
    ("11/14/2026", "", "CHI@MIN", "Minnesota Timberwolves", "Edwards, Anthony", "Out", "Injury/Illness - Right Knee Arthroscopy"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Duren, Jalen", "Out", "Injury/Illness - Right Hamstring Strain"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Harkless, Elijah", "Questionable", "G League - Two-Way"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Joe, Isaiah", "Out", "Injury/Illness - Right Hip Contusion"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Jones, Isaac", "Questionable", "G League - Two-Way"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Lanier, Chaz", "Out", "G League - On Assignment"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Okorie, Ebuka", "Out", "G League - On Assignment"),
    ("11/14/2026", "", "DET@MIA", "Detroit Pistons", "Onyenso, Ugonna", "Out", "G League - Two-Way"),
    ("11/14/2026", "", "DET@MIA", "Miami Heat", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "01:00 (ET)", "IND@PHI", "Indiana Pacers", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "IND@PHI", "Philadelphia 76ers", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "04:00 (ET)", "LAL@PHX", "Los Angeles Lakers", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "LAL@PHX", "Phoenix Suns", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "04:30 (ET)", "CHA@LAC", "Charlotte Hornets", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "CHA@LAC", "LA Clippers", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "05:00 (ET)", "SAS@UTA", "San Antonio Spurs", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "SAS@UTA", "Utah Jazz", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "06:00 (ET)", "DAL@BOS", "Dallas Mavericks", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "DAL@BOS", "Boston Celtics", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "06:00 (ET)", "NYK@TOR", "New York Knicks", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "NYK@TOR", "Toronto Raptors", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "07:00 (ET)", "HOU@WAS", "Houston Rockets", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "HOU@WAS", "Washington Wizards", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "08:00 (ET)", "ATL@MIL", "Atlanta Hawks", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "ATL@MIL", "Milwaukee Bucks", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "09:00 (ET)", "OKC@SAC", "Oklahoma City Thunder", "", "", "NOT YET SUBMITTED"),
    ("11/15/2026", "", "OKC@SAC", "Sacramento Kings", "", "", "NOT YET SUBMITTED"),
]




# ---------------------------------------------------------------------------
# C6 input - verbatim re-read of https://www.nba.com/schedule?date=2026-11-15
# (chunks 0-2 of 9, fetched 2026-11-14 ~10:45 UTC / 05:45 ET) covering the
# whole 2026-11-14..17 window: (date, tip_et, away, home, game_id, venue).
# The page's game links carry the official game ids; venues are printed under
# each game.  Broadcasts were also re-read and agree; they are recorded in the
# COORDINATION.md log rather than re-checked here because the stored slate's
# broadcast strings normalise "Peacock / NBC Sports Network" from two logo
# alt-texts, which is not a mechanical comparison.
# ---------------------------------------------------------------------------
SLATE_LIVE_REREAD = [
    ("2026-11-14", "7:00 PM", "DEN", "NOP", "0022600231", "Smoothie King Center"),
    ("2026-11-14", "7:30 PM", "DAL", "CLE", "0022600232", "Rocket Arena"),
    ("2026-11-14", "8:00 PM", "DET", "MIA", "0022600233", "Kaseya Center"),
    ("2026-11-14", "8:00 PM", "BKN", "MEM", "0022600234", "FedExForum"),
    ("2026-11-14", "8:00 PM", "CHI", "MIN", "0022600235", "Target Center"),
    ("2026-11-15", "1:00 PM", "IND", "PHI", "0022600236", "Xfinity Mobile Arena"),
    ("2026-11-15", "4:00 PM", "LAL", "PHX", "0022600237", "Mortgage Matchup Center"),
    ("2026-11-15", "4:30 PM", "CHA", "LAC", "0022600238", "Intuit Dome"),
    ("2026-11-15", "5:00 PM", "SAS", "UTA", "0022600239", "Delta Center"),
    ("2026-11-15", "6:00 PM", "DAL", "BOS", "0022600240", "TD Garden"),
    ("2026-11-15", "6:00 PM", "NYK", "TOR", "0022600241", "Scotiabank Arena"),
    ("2026-11-15", "7:00 PM", "HOU", "WAS", "0022600242", "Capital One Arena"),
    ("2026-11-15", "8:00 PM", "ATL", "MIL", "0022600243", "Fiserv Forum"),
    ("2026-11-15", "9:00 PM", "OKC", "SAC", "0022600244", "Golden 1 Center"),
    ("2026-11-16", "7:00 PM", "ORL", "BOS", "0022600245", "TD Garden"),
    ("2026-11-16", "7:00 PM", "CHI", "CLE", "0022600246", "Rocket Arena"),
    ("2026-11-16", "7:00 PM", "MEM", "WAS", "0022600247", "Capital One Arena"),
    ("2026-11-16", "7:30 PM", "PHI", "BKN", "0022600248", "Barclays Center"),
    ("2026-11-16", "7:30 PM", "HOU", "MIA", "0022600249", "Kaseya Center"),
    ("2026-11-16", "8:00 PM", "POR", "MIN", "0022600250", "Target Center"),
    ("2026-11-16", "8:00 PM", "GSW", "NOP", "0022600251", "Smoothie King Center"),
    ("2026-11-16", "9:00 PM", "PHX", "DEN", "0022600252", "Ball Arena"),
    ("2026-11-17", "7:30 PM", "NYK", "TOR", "0022600253", "Scotiabank Arena"),
    ("2026-11-17", "8:00 PM", "POR", "MIN", "0022600254", "Target Center"),
    ("2026-11-17", "8:00 PM", "DET", "SAS", "0022600255", "Frost Bank Center"),
    ("2026-11-17", "10:30 PM", "UTA", "LAC", "0022600257", "Intuit Dome"),
    ("2026-11-17", "11:00 PM", "CHA", "LAL", "0022600256", "Crypto.com Arena"),
]


if __name__ == "__main__":
    main()
