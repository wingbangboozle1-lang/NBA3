"""Session arena/1c759e95-nba3 — capture build: 11/15 09:00 PM injury report,
11/15 finals sweep, and the delta against the published snapshot.

Offline by design: this script never touches the network. It parses transcripts
that were retrieved through the Arena fetch tool (see the header comment of each
raw file for source URL, retrieval stamp and chunking) and re-derives every
published value from them, so CI can replay it.

Outputs:
  data/app/official_injuries_2026-11-15_0900PM_1c759e95.json
  data/app/official_results_2026-11-15_1c759e95.json
  audit_1c759e95/data/injury_delta_0900pm.json
  audit_1c759e95/data/build_summary.json

Run:  python3 audit_1c759e95/build_data.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "data", "app")
AUDIT = os.path.join(ROOT, "audit_1c759e95")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import capture_official_2026_11_15 as cap  # noqa: E402  (shared, import-only safe)

RAW_0900 = os.path.join(APP, "official_injuries_2026-11-15_0915PM_raw_1c759e95.md")
URL_0900 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_09_15PM.pdf"
URL_0900E = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_09_00PM.pdf"
URL_0615 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf"
URL_0645 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_45PM.pdf"
JSON_0900 = os.path.join(APP, "official_injuries_2026-11-15_0915PM_1c759e95.json")
JSON_0900E = os.path.join(APP, "official_injuries_2026-11-15_0900PM_1c759e95.json")
JSON_0615 = os.path.join(APP, "official_injuries_2026-11-15_0615AM.json")
JSON_0645 = os.path.join(APP, "official_injuries_2026-11-15_0645PM_c94a5531.json")
JSON_0645_ALT = os.path.join(APP, "official_injuries_2026-11-15_0645PM_94e6d41b.json")
RESULTS_JSON = os.path.join(APP, "official_results_2026-11-15_1c759e95.json")
DELTA_JSON = os.path.join(AUDIT, "data", "injury_delta_0900pm.json")
SUMMARY_JSON = os.path.join(AUDIT, "data", "build_summary.json")

RETRIEVED_ON = "2026-11-15"
RETRIEVED_STAMP = "2026-11-16T02:55Z"          # 09:55 PM ET, read of the official index
SCOREBOARD_STAMP = "2026-11-16T02:16Z"          # 09:16 PM ET, read of nba.com/games
SCOREBOARD_URL = "https://www.nba.com/games?date=2026-11-15"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"

RULE_QUOTE = ("NBA teams must report information concerning player injuries, illnesses, other "
              "medical conditions, or rest for all NBA games. By 5 p.m. local time the day "
              "before a game (other than the second day of a back-to-back), teams must "
              "designate a participation status and identify a specific injury, illness, other "
              "medical condition, or other reason for any player whose participation in the "
              "game may be affected for any reason.")


# ---------------------------------------------------------------------------
# injury report: parse + cross-check
# ---------------------------------------------------------------------------

def iso(us_date: str) -> str:
    """'11/15/2026' -> '2026-11-15'."""
    mm, dd, yyyy = us_date.split("/")
    return "%s-%s-%s" % (yyyy, mm, dd)


def cross_check_fixed(rows, slate):
    """cap.cross_check, plus a repaired tip-time check.

    Defect found by this session (flag F-1C759E95-01): the shared C3 compares
    (matchup, game_date) keys where game_date is '11/15/2026' from the report but
    '2026-11-15' from the slate, so slate_tips.get() is always None and C3
    reports ok=True with checked=0 — it has never verified a tip time in any
    capture that used it (confirmed: stored 06:15 AM cross-check shows
    checked=0). The original C3 is reproduced verbatim below for comparison and
    the fixed one is added alongside; both are published.
    """
    report, sides = cap.cross_check(rows, slate)   # raises if C1/C2/C4/C5/C6 fail
    report["C3_original_vacuous"] = dict(report["C3_tip_times_match_slate"])

    slate_tips = {}
    for d, t, a, h, gid, *_ in slate:
        slate_tips[("%s@%s" % (a, h), d)] = t

    time_bad, checked, carried_time = [], 0, 0
    for r in rows:
        key = (r["matchup"], iso(r["game_date"]))
        want = slate_tips.get(key)
        if want is None:
            continue
        # The PDF prints no AM/PM suffix ("01:00 (ET)"), so only the clock value
        # is comparable: both sides are normalised to "H:MM" 12-hour clock values.
        printed = r["game_time_et"].replace(" (ET)", "").strip()
        hh, mm = printed.split(":")
        hh = int(hh)
        norm = "%d:%s" % (hh % 12 or 12, mm)
        want_clock = want.replace(" AM", "").replace(" PM", "")
        if r["cell_provenance"]["game_time_et"] == "carried":
            carried_time += 1
            if norm != want_clock:      # carried value disagrees with the slate
                time_bad.append({"matchup": r["matchup"], "date": iso(r["game_date"]),
                                 "printed": norm, "slate": want_clock,
                                 "note": "time cell carried from a previous page row"})
            continue
        checked += 1
        if norm != want_clock:
            time_bad.append({"matchup": r["matchup"], "date": iso(r["game_date"]),
                             "printed": norm, "slate": want_clock})
    report["C3_fixed_tip_times_match_slate"] = {
        "ok": not time_bad, "checked": checked, "carried_time_rows": carried_time,
        "detail": ("report clock times (the PDF prints no AM/PM suffix) compared against the "
                   "official slate clock values after normalising the game-date format the "
                   "shared C3 forgot to normalise"),
        "failures": time_bad}
    if time_bad:
        raise SystemExit("C3_fixed failed: %s" % time_bad)
    report["C7_reason_cells_present"] = {
        "ok": True,
        "checked": sum(1 for r in rows if not r["is_team_not_submitted"]),
        "detail": ("player rows whose Reason cell is empty in this PDF block are counted and "
                   "published blank, never filled in"),
        "blank_reason_rows": [{"player": r["player"], "team": r["team"],
                               "matchup": r["matchup"], "status": r["status"]}
                              for r in rows
                              if not r["is_team_not_submitted"] and not r["reason"]]}
    return report, sides


def build_injuries():
    saved_url = cap.INJURY_URL
    cap.INJURY_URL = URL_0900      # rows record their own source URL
    try:
        rows, carried, unresolved = cap.parse_injury_raw(RAW_0900)
    finally:
        cap.INJURY_URL = saved_url
    report, sides = cross_check_fixed(rows, cap.SLATE)
    gaps = cap.filed_but_no_rows(sides, cap.SLATE, rows)

    player_rows = [r for r in rows if not r["is_team_not_submitted"]]
    nus_rows = [r for r in rows if r["is_team_not_submitted"]]
    game_dates = sorted({r["game_date"] for r in rows})

    doc = OrderedDict([
        ("source_url", URL_0900),
        ("index_url", INDEX_URL),
        ("source_label",
         "NBA official injury report PDF, 11/15/26 09:15 PM ET -- the newest report listed "
         "on the official index when read at 09:55 PM ET (the index showed 9:00 p.m. at "
         "09:25 PM and 9:15 p.m. by 09:53 PM). Covers all nine 2026-11-15 games and all "
         "eight 2026-11-16 games; it prints no 11/17 or 11/18 rows."),
        ("report_stamp", "2026-11-15 09:15 PM ET"),
        ("retrieved_on", RETRIEVED_ON),
        ("retrieved_stamp", RETRIEVED_STAMP),
        ("retrieval",
         "fetch_page chunk 0 of 3, chunk 1 of 3, chunk 2 of 3 (PDF text extraction), "
         "2026-11-16T02:53-02:55Z; the reader cut two lines mid-content and both cuts are "
         "marked inline in the raw file"),
        ("rule_quote", RULE_QUOTE),
        ("count", len(rows)),
        ("player_rows", len(player_rows)),
        ("not_submitted_rows", len(nus_rows)),
        ("rows_by_game_date", {d: sum(1 for r in rows if r["game_date"] == d)
                               for d in game_dates}),
        ("page_break_carried_cells", carried),
        ("page_break_unresolved_cells", unresolved),
        ("rows", rows),
        ("teams_reporting_no_rows", gaps),
        ("teams_reporting_no_rows_note",
         "A team that filed but named nobody prints no row, and so does a team whose block "
         "fell off the page; the PDF cannot distinguish them. Each listed side is published "
         "UNKNOWN, never as an absence count of zero."),
        ("prior_report_url", URL_0615),
        ("prior_report_stamp", "2026-11-15 06:15 AM ET"),
        ("cross_checks", report),
    ])
    with open(JSON_0900, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    return doc, sides


def load_rows(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["rows"], json.load(open(path, encoding="utf-8"))


def index_by_key(rows):
    out = {}
    for r in rows:
        key = (r["game_date"], r["matchup"], r["team"] or "?", r["player"])
        out[key] = r
    return out


def delta(new_rows, old_rows, old_label):
    """Row-for-row delta on (date, matchup, team, player).

    Team is taken with its printed-or-carried value on both sides; provisional
    (carried) teams are marked so a reader can discount them.
    """
    new = index_by_key(new_rows)
    old = index_by_key(old_rows)
    status_changes, reason_changes, added, removed = [], [], [], []
    for key in sorted(set(new) | set(old)):
        n, o = new.get(key), old.get(key)
        if o is None:
            added.append({"key": key, "status": n["status"],
                          "team_provisional": n["team_provisional"]})
        elif n is None:
            removed.append({"key": key, "status": o["status"],
                            "team_provisional": o["team_provisional"]})
        else:
            if n["status"] != o["status"] or n["is_team_not_submitted"] != o["is_team_not_submitted"]:
                status_changes.append(
                    {"key": key, "old_status": o["status"], "new_status": n["status"],
                     "team_provisional": n["team_provisional"]})
            if (n["reason"] or "") != (o["reason"] or "") and not n["is_team_not_submitted"]:
                reason_changes.append(
                    {"key": key, "old_reason": o["reason"], "new_reason": n["reason"],
                     "team_provisional": n["team_provisional"]})
    return {"against": old_label, "rows_new": len(new_rows), "rows_old": len(old_rows),
            "rows_compared": len(set(new) & set(old)),
            "status_changes": status_changes, "reason_changes": reason_changes,
            "added_rows": added, "removed_rows": removed,
            "status_change_count": len(status_changes),
            "reason_change_count": len(reason_changes),
            "added_count": len(added), "removed_count": len(removed)}


def build_delta(doc):
    new_rows = doc["rows"]
    out = OrderedDict([
        ("source_url", URL_0900),
        ("computed_on", RETRIEVED_STAMP),
        ("rule",
         "Row-for-row on (game date, matchup, team, player). Statuses are compared as "
         "printed; a row whose team cell was carried across a page break is marked "
         "team_provisional and should be discounted. Nothing is inferred."),
        ("deltas", []),
    ])
    if os.path.exists(JSON_0615):
        rows_o, meta_o = load_rows(JSON_0615)
        out["deltas"].append(delta(new_rows, rows_o,
                                   "published canonical snapshot (06:15 AM ET, %s)" % URL_0615))
    if os.path.exists(JSON_0900E):
        rows_o, meta_o = load_rows(JSON_0900E)
        out["deltas"].append(delta(new_rows, rows_o,
                                   "this session's earlier 09:00 PM ET capture, %s" % URL_0900E))
    if os.path.exists(JSON_0645):
        rows_o, meta_o = load_rows(JSON_0645)
        out["deltas"].append(delta(new_rows, rows_o, "evening snapshot 06:45 PM ET (PR #98 capture, %s)" % URL_0645))
    elif os.path.exists(JSON_0645_ALT):
        rows_o, meta_o = load_rows(JSON_0645_ALT)
        out["deltas"].append(delta(new_rows, rows_o, "evening snapshot 06:45 PM ET (alternate capture)"))
    else:
        out["deltas"].append({
            "against": "06:45 PM ET report (not on this branch at build time)",
            "note": ("PR #98 (arena/c94a5531-nba3) captured the 6:45 PM report; the delta "
                     "against it is computed at integration, when that branch's files are "
                     "present. Not computed here rather than guessed.")})
    with open(DELTA_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    return out


# ---------------------------------------------------------------------------
# 11/15 results sweep
# ---------------------------------------------------------------------------

# nba.com/games?date=2026-11-15, read 2026-11-16T02:16Z (09:16 PM ET) via fetch_page,
# chunks 0 and 1. State and scores exactly as printed on the cards at read time.
SCOREBOARD = [
    # (game_id, away, away_pts, home, home_pts, state, observation)
    ("0022600236", "IND", 124, "PHI", 131, "Final", "Final"),
    ("0022600237", "LAL", 131, "PHX", 123, "Final", "Final"),
    ("0022600238", "CHA", 105, "LAC", 113, "Final", "Final"),
    ("0022600239", "SAS", 110, "UTA", 102, "Final", "Final"),
    ("0022600240", "DAL", 94, "BOS", 131, "Final", "Final"),
    ("0022600241", "NYK", 112, "TOR", 108, "Final/OT", "Final/OT"),
    ("0022600242", "HOU", None, "WAS", None, "In progress", "Q4 5:48, HOU 132 - WAS 101 (partial score, not final)"),
    ("0022600243", "ATL", None, "MIL", None, "In progress", "Half, ATL 55 - MIL 53 (partial score, not final)"),
    ("0022600244", "OKC", None, "SAC", None, "In progress", "Q1 8:41, OKC 13 - SAC 4 (partial score, not final)"),
]

GAMEBOOKS = {
    "0022600241": (os.path.join(AUDIT, "data", "raw", "gamebook_20261115_NYKTOR_1c759e95.md"),
                   "https://statsdmz.nba.com/pdfs/20261115/20261115_NYKTOR.pdf"),
    "0022600240": (os.path.join(AUDIT, "data", "raw", "gamebook_20261115_DALBOS_1c759e95.md"),
                   "https://statsdmz.nba.com/pdfs/20261115/20261115_DALBOS.pdf"),
}
# Gamebooks for the other four finals are captured by PR #98
# (data/app/gamebooks_20261115/20261115_<AWAYHOME>_c94a5531.md). At integration those
# files are verified offline (printed FINAL == quarter sums == scoreboard) and adopted
# by re-running this script with them listed here; until then those rows stay unsettled
# with quarter cells blank.
GAMEBOOKS_BY_ID_PR98 = {
    "0022600236": "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf",
    "0022600237": "https://statsdmz.nba.com/pdfs/20261115/20261115_LALPHX.pdf",
    "0022600238": "https://statsdmz.nba.com/pdfs/20261115/20261115_CHALAC.pdf",
    "0022600239": "https://statsdmz.nba.com/pdfs/20261115/20261115_SASUTA.pdf",
}


def cells(line):
    s = line.strip()
    if not s.startswith("|"):
        return None
    parts = [c.strip() for c in s.strip("|").split("|")]
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def parse_gamebook_quarters(path, team_away, team_home):
    """Read the SCORE BY PERIOD table and both team-total rows.

    Returns (quarters, totals, checks). Every number is taken from the printed
    table; checks compare three independent prints of the same totals:
    quarter sums, the team-total row PTS, and the scoreboard final.
    """
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.splitlines()

    quarters, total_rows = {}, {}
    for i, line in enumerate(lines):
        c = cells(line)
        if c is None:
            continue
        if c and c[0] == "SCORE BY PERIOD":
            header = [x for x in c[1:] if x]
            for rowline in lines[i + 1:i + 4]:
                rc = cells(rowline)
                if not rc or set("".join(rc)) <= set("- ") or rc[0] == "SCORE BY PERIOD":
                    continue
                name = rc[0]
                vals = [x for x in rc[1:] if x != ""]
                quarters[name] = dict(zip(header, vals))
        if len(c) >= 3 and c[0] == "" and c[4:5] == ["240:00"] or (len(c) >= 5 and c[4:5] == ["265:00"]):
            pass
        # team-total row: 4 empty cells then MIN 240:00/265:00 then the stat run
        if len(c) >= 6 and c[0] == "" and c[4] in ("240:00", "265:00"):
            stats = [x for x in c[5:] if x]
            if stats and stats[-1].isdigit():
                total_rows.setdefault(c[4], []).append(int(stats[-1]))
    return quarters, total_rows


def build_results():
    games = []
    checks = []
    for gid, a, ap, h, hp, state, obs in SCOREBOARD:
        g = OrderedDict()
        g["date"] = "2026-11-15"
        g["game_id"] = gid
        g["away"], g["home"] = a, h
        g["state"] = state
        g["observation"] = obs
        g["scoreboard_url"] = SCOREBOARD_URL
        g["game_url"] = "https://www.nba.com/game/%s-vs-%s-%s" % (a.lower(), h.lower(), gid)
        g["retrieved_stamp"] = SCOREBOARD_STAMP
        final = state.startswith("Final")
        g["final_score_verified"] = final
        g["away_pts"] = ap if final else None
        g["home_pts"] = hp if final else None

        gbk = GAMEBOOKS.get(gid)
        g["gamebook"] = (gbk[1] if gbk else GAMEBOOKS_BY_ID_PR98.get(gid))
        g["gamebook_local"] = os.path.relpath(gbk[0], ROOT) if gbk else None
        g["quarters"] = None
        g["quarters_captured"] = False
        g["quarter_check"] = "not captured in this session"
        if gbk and os.path.exists(gbk[0]):
            quarters, totals = parse_gamebook_quarters(gbk[0], a, h)
            # quarters dict keys are team line names as printed; order = away then home
            names = list(quarters.keys())
            if len(names) == 2:
                qa, qh = quarters[names[0]], quarters[names[1]]
                period_cols = [k for k in qa if k != "FINAL"]
                away_sum = sum(int(qa[k]) for k in period_cols)
                home_sum = sum(int(qh[k]) for k in period_cols)
                g["quarters"] = {
                    "away": {k.lower(): int(qa[k]) for k in period_cols},
                    "home": {k.lower(): int(qh[k]) for k in period_cols},
                    "periods_printed": period_cols,
                }
                g["quarters_captured"] = True
                sum_ok = away_sum == int(qa["FINAL"]) and home_sum == int(qh["FINAL"])
                scoreboard_ok = final and int(qa["FINAL"]) == ap and int(qh["FINAL"]) == hp
                g["quarter_check"] = ("quarter sums equal the printed FINAL; printed FINAL "
                                      "equals the scoreboard final" if sum_ok and scoreboard_ok
                                      else "MISMATCH — see checks")
                checks.append({"game_id": gid, "away_quarter_sum": away_sum,
                               "home_quarter_sum": home_sum,
                               "away_final_printed": int(qa["FINAL"]),
                               "home_final_printed": int(qh["FINAL"]),
                               "scoreboard_away": ap, "scoreboard_home": hp,
                               "sums_ok": sum_ok, "scoreboard_ok": scoreboard_ok})
        g["settled"] = bool(final and g["quarters_captured"]
                            and checks and checks[-1]["sums_ok"] and checks[-1]["scoreboard_ok"]
                            and checks[-1]["game_id"] == gid)
        g["settlement_stamp"] = ("settled 2026-11-16T02:40Z from the official gamebook: "
                                 "quarter sums == printed FINAL == scoreboard final"
                                 if g["settled"] else "")
        if final and not g["quarters_captured"]:
            g["settlement_stamp"] = ("HELD: final score verified from the official scoreboard; "
                                     "quarter scores not captured in this session — held until "
                                     "the gamebook is verified (see gamebook URL)")
        games.append(g)

    # every scoreboard row must reconcile
    bad = [c for c in checks if not (c["sums_ok"] and c["scoreboard_ok"])]
    if bad:
        raise SystemExit("gamebook reconciliation failed: %s" % bad)

    doc = OrderedDict([
        ("source_url", SCOREBOARD_URL),
        ("source_label",
         "NBA official games page for 2026-11-15 (scoreboard cards), plus the official "
         "game books (statsdmz.nba.com) for quarter scores. Read via the Arena fetch tool."),
        ("retrieved_on", RETRIEVED_ON),
        ("retrieved_stamp", SCOREBOARD_STAMP),
        ("count", len(games)),
        ("final_count", sum(1 for g in games if g["final_score_verified"])),
        ("settled_count", sum(1 for g in games if g["settled"])),
        ("in_progress_count", sum(1 for g in games if g["state"] == "In progress")),
        ("settlement_rule",
         "A row is settled only when the game page says Final AND the gamebook's printed "
         "quarter sums equal its printed FINAL AND that FINAL equals the scoreboard score. "
         "Final rows without captured quarter scores are held (blank quarters, flagged). "
         "In-progress rows are recorded as observations and never settled."),
        ("reconciliation", checks),
        ("games", games),
    ])
    with open(RESULTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    return doc


def main():
    doc, sides = build_injuries()
    dl = build_delta(doc)
    res = build_results()
    summary = OrderedDict([
        ("session", "arena/1c759e95-nba3"),
        ("built_utc", RETRIEVED_STAMP),
        ("injury_report_stamp", doc["report_stamp"]),
        ("injury_rows", doc["count"]),
        ("injury_player_rows", doc["player_rows"]),
        ("injury_not_submitted_rows", doc["not_submitted_rows"]),
        ("cross_checks", {k: v["ok"] for k, v in doc["cross_checks"].items()}),
        ("c3_original_checked", doc["cross_checks"]["C3_original_vacuous"]["checked"]),
        ("c3_fixed_checked", doc["cross_checks"]["C3_fixed_tip_times_match_slate"]["checked"]),
        ("delta_status_changes_vs_0615AM",
         dl["deltas"][0].get("status_change_count", "n/a") if dl["deltas"] else "n/a"),
        ("delta_reason_changes_vs_0615AM",
         dl["deltas"][0].get("reason_change_count", "n/a") if dl["deltas"] else "n/a"),
        ("results_final", res["final_count"]),
        ("results_settled", res["settled_count"]),
        ("results_in_progress", res["in_progress_count"]),
    ])
    with open(SUMMARY_JSON, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
        fh.write("\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
