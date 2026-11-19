#!/usr/bin/env python3
"""Rolling 3-day slate (11/19–11/21) re-read from the official games pages, with cross-checks.

Session de0caf5d, task X3. The 19 rows below were copied from fetch-tool transcripts of
https://www.nba.com/games?date=2026-11-19, ...-20 and ...-21 (each page read to its last chunk).
Each page's game count was compared with the calendar cell on the same page:
11/19 -> 4 games, 11/20 -> 9 games, 11/21 -> 6 games (all matched).

Cross-checks (no value is filled in from another source):
  * injury PDF 12:45 AM ET (injury_2026-11-19_0045AM.json): matchup present? time printed? date printed?
    The PDF prints times without AM/PM ("08:00 (ET)" = the page's 8:00 PM ET); a time match is
    compared on hour:minute only. Rows the PDF text layer does not print are reported as "not_printed".
  * committed 11/19 rows (data/rounds/2026-11-17/slate_extra_2026-11-19.json): game id, away, home, tip.

Run: python3 data/rounds/2026-11-19/build_slate_check.py   (writes slate_check.json)
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "slate_check.json")
RETRIEVED = "2026-11-19T05:47Z (approximate; bash clock read in the same session)"

PAGE = {
    "2026-11-19": "https://www.nba.com/games?date=2026-11-19",
    "2026-11-20": "https://www.nba.com/games?date=2026-11-20",
    "2026-11-21": "https://www.nba.com/games?date=2026-11-21",
}
PAGE_COUNT = {"2026-11-19": 4, "2026-11-20": 9, "2026-11-21": 6}  # calendar cells on the same pages

# (date, tip as printed on page, away, home, game_id, away record as printed, home record as printed)
GAMES = [
    ("2026-11-19", "8:00 PM ET", "GSW", "MEM", "0022600270", "8-7", "11-4"),
    ("2026-11-19", "8:00 PM ET", "POR", "MIL", "0022600271", "9-5", "1-14"),
    ("2026-11-19", "8:00 PM ET", "NYK", "MIN", "0022600272", "8-6", "11-4"),
    ("2026-11-19", "8:00 PM ET", "LAC", "SAS", "0022600273", "4-9", "12-3"),
    ("2026-11-20", "7:00 PM ET", "CHA", "ATL", "0022600043", "4-10 (0-2)", "9-6 (1-1)"),
    ("2026-11-20", "7:30 PM ET", "TOR", "DET", "0022600046", "5-10 (1-1)", "10-4 (1-0)"),
    ("2026-11-20", "7:30 PM ET", "IND", "CLE", "0022600045", "5-10 (1-1)", "8-8 (1-1)"),
    ("2026-11-20", "7:30 PM ET", "ORL", "BKN", "0022600044", "6-8 (2-0)", "3-11 (0-1)"),
    ("2026-11-20", "8:00 PM ET", "NOP", "OKC", "0022600048", "5-11 (0-2)", "9-6 (1-1)"),
    ("2026-11-20", "8:00 PM ET", "WAS", "CHI", "0022600047", "5-11 (1-1)", "4-10 (1-1)"),
    ("2026-11-20", "9:30 PM ET", "PHX", "UTA", "0022600049", "7-7 (0-1)", "2-13 (0-2)"),
    ("2026-11-20", "10:00 PM ET", "HOU", "DEN", "0022600050", "12-4 (1-1)", "8-5 (1-0)"),
    ("2026-11-20", "10:00 PM ET", "SAC", "LAL", "0022600051", "1-13 (0-2)", "13-2 (1-1)"),
    ("2026-11-21", "1:00 PM ET", "MIL", "PHI", "0022600274", "1-14", "13-3"),
    ("2026-11-21", "7:30 PM ET", "POR", "NYK", "0022600275", "9-5", "8-6"),
    ("2026-11-21", "8:00 PM ET", "LAC", "DAL", "0022600276", "4-9", "8-7"),
    ("2026-11-21", "8:00 PM ET", "MEM", "MIN", "0022600277", "11-4", "11-4"),
    ("2026-11-21", "8:00 PM ET", "NOP", "SAS", "0022600278", "5-11", "12-3"),
    ("2026-11-21", "10:00 PM ET", "BOS", "SAC", "0022600279", "11-4", "1-13"),
]


def _h12(tip):
    """'8:00 PM ET' -> '08:00': the 12-hour hh:mm the injury PDF prints (it omits AM/PM)."""
    m = re.match(r"(\d{1,2}):(\d{2}) (AM|PM) ET", tip)
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _iso(us_date):
    """'11/20/2026' (the PDF's format) -> '2026-11-20'."""
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", us_date)
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else us_date


def _pdf_index(injury):
    """matchup -> list of (date, time_hm) actually printed in the newest PDF rows."""
    idx = {}
    for r in injury["rows_newest"]:
        m = r.get("matchup")
        if not m:
            continue
        idx.setdefault(m, set()).add((_iso(r.get("game_date") or ""), (r.get("game_time_et") or "")))
    return idx


def build():
    with open(os.path.join(HERE, "injury_2026-11-19_0045AM.json"), encoding="utf-8") as fh:
        injury = json.load(fh)
    pdf = _pdf_index(injury)
    committed_path = os.path.join(ROOT, "data", "rounds", "2026-11-17", "slate_extra_2026-11-19.json")
    with open(committed_path, encoding="utf-8") as fh:
        committed = {g["game_id"]: g for g in json.load(fh)["games"]}

    rows, flags = [], []
    for date, tip, away, home, gid, arec, hrec in GAMES:
        matchup = f"{away}@{home}"
        page_url = PAGE[date]
        game_url = f"https://www.nba.com/game/{away.lower()}-vs-{home.lower()}-{gid}"
        printed = pdf.get(matchup, set())
        pdf_dates = sorted({d for d, _ in printed if d})
        pdf_times = sorted({t for _, t in printed if t})
        if date == "2026-11-21":
            pdf_status = "not_covered: the 12:45 AM report prints no 11/21 rows"
        elif not printed:
            pdf_status = "matchup_not_printed"
        else:
            if not pdf_times:
                time_ok = "not_printed"
            else:
                time_ok = "match" if _h12(tip) in pdf_times else "mismatch"
            pdf_status = {"date_printed": pdf_dates[0] if pdf_dates else None,
                          "time_printed": pdf_times, "time_check": time_ok}
            if not pdf_dates:
                pdf_status["date_check"] = "not_printed_in_pdf_text"
            elif pdf_dates[0] != date:
                pdf_status["date_check"] = "mismatch"
            else:
                pdf_status["date_check"] = "match"
        c = committed.get(gid)
        if date == "2026-11-19":
            if c is None:
                committed_status = "not_in_committed_slate"
            else:
                same = (c["away"], c["home"], c["date"], c["tip_et"].replace(" ET", "")) == \
                       (away, home, date, tip.replace(" ET", ""))
                committed_status = "match" if same else {
                    "committed": [c["away"], c["home"], c["date"], c["tip_et"]], "page": [away, home, date, tip]}
        else:
            committed_status = ("no game-level committed row in this repo for this date; the per-date count "
                                "is checked below against data/app/official_counts_2026-11-14.json")
        rows.append({
            "date": date,
            "tip_et_as_printed": tip,
            "away": away,
            "home": home,
            "matchup": matchup,
            "game_id": gid,
            "game_url": game_url,
            "source_url": page_url,
            "retrieved_utc": RETRIEVED,
            "records_as_printed": {"away": arec, "home": hrec},
            "injury_pdf_0045AM": pdf_status,
            "committed_slate_check": committed_status,
        })

    counts = {d: sum(1 for r in rows if r["date"] == d) for d in PAGE}
    for d, n in PAGE_COUNT.items():
        if counts[d] != n:
            flags.append(f"{d}: {counts[d]} rows captured vs {n} calendar games")
    with open(os.path.join(ROOT, "data", "app", "official_counts_2026-11-14.json"), encoding="utf-8") as fh:
        prior_counts = {}
        def _walk(o):
            if isinstance(o, dict):
                if "date" in o and "games" in o:
                    prior_counts[o["date"]] = o["games"]
                for v in o.values():
                    _walk(v)
            elif isinstance(o, list):
                for v in o:
                    _walk(v)
        _walk(json.load(fh))
    count_check = {d: {"captured": counts[d], "committed_2026_11_14": prior_counts.get(d),
                       "match": prior_counts.get(d) == counts[d]} for d in PAGE}
    for d in PAGE:
        if not count_check[d]["match"]:
            flags.append(f"{d}: count differs from data/app/official_counts_2026-11-14.json")
    ids = [r["game_id"] for r in rows]
    if len(set(ids)) != len(ids):
        flags.append("duplicate game id in capture")
    flags.append("game ids are not chronological: 11/20 rows carry 0022600043-0022600051 while 11/19 rows "
                 "carry 0022600270-0022600273 and 11/21 rows 0022600274-0022600279. Taken as printed; the "
                 "id is the join key, so the ordering is flagged for review, not corrected.")
    flags.append("The 12:45 AM injury report prints no row dated 11/21, so the 11/21 games are not cross-checked against it.")
    flags.append("POR@MIL 11/19: the PDF text layer prints the matchup without date or time; the time comes "
                 "from the games page only.")
    flags.append("TOR@DET 11/20: the PDF text layer prints the matchup without date/time, and the Toronto row "
                 "has no status cell; not attributable from the PDF text.")
    flags.append("NOP@OKC, WAS@CHI, PHX@UTA, HOU@DEN, SAC@LAL 11/20: the PDF prints the time without a date; "
                 "the 11/20 date comes from the games page only.")
    flags.append("Records are as printed on each page at the retrieval time and are not reconciled with the "
                 "committed 11/16 snapshot (they differ because games were played in between).")
    out = {
        "schema": "nba3.rounds.slate_check/v1",
        "session": "de0caf5d",
        "window": ["2026-11-19", "2026-11-21"],
        "retrieved_utc": RETRIEVED,
        "pages": PAGE,
        "calendar_counts": PAGE_COUNT,
        "captured_counts": counts,
        "count_cross_check": count_check,
        "games": rows,
        "flags": flags,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return out


if __name__ == "__main__":
    o = build()
    print("captured:", o["captured_counts"], "calendar:", o["calendar_counts"])
    print("flags:", len(o["flags"]))
    print("wrote", os.path.relpath(OUT))
