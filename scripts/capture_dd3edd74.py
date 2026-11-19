#!/usr/bin/env python3
"""Per-game official finals for 2026-11-16, 2026-11-17 and 2026-11-18 (session arena/dd3edd74-nba3, task D2).

Provenance: every value below was read by the session from the official nba.com date page
https://www.nba.com/games?date=<DATE> (the page's score table, one block per game) on
2026-11-19 (UTC). The fetch tool returns page text, not a file, so the transcription is stored
here verbatim and re-checked offline by `--check`. The recap-video URL printed on each game
block is stored as a second read: its slug repeats the two final scores, and `--check` requires
them to agree with the score table.

Quarter scores are NOT captured for these games (a game page read costs ~3 chunks each, and the
date pages do not print a period table). They are stored as null and flagged, never estimated.

Run:   python3 scripts/capture_dd3edd74.py            (writes the artefact)
       python3 scripts/capture_dd3edd74.py --check    (re-verifies the committed artefact)
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "data", "rounds", "2026-11-19-dd3edd74")
OUT = os.path.join(OUT_DIR, "results_2026-11-16_18.json")
# The cross-check is pinned to the FROZEN 2026-11-15..18 window the capture was verified against,
# not the rolling canonical slate: the canonical file legitimately advances each round (it held
# 2026-11-19..21 after the 915d2e99 promotion, which made this historical re-check fail). The
# frozen copy is the byte-exact `data/app/official_slate_current.json` of commit 454a7ee, kept
# beside the capture so the verification stays replayable forever. (integration, f69a11c4 G3)
SLATE = os.path.join(ROOT, "data", "rounds", "2026-11-19-dd3edd74", "slate_reference_1115_1118.json")
B1CE = os.path.join(ROOT, "data", "rounds", "2026-11-19", "results_2026-11-18.json")

# Count printed in the calendar cell of each date on the official date page (e.g. "16<br>8<br>GAMES").
CALENDAR_COUNT = {"2026-11-16": 8, "2026-11-17": 5, "2026-11-18": 12}

# (game_id, date, away, away_pts, home, home_pts, status, recap_video_slug or None)
# Team order = away first, as in the official game URL slug (e.g. orl-vs-bos) and the score table.
READ = [
    ("0022600245", "2026-11-16", "ORL", 115, "BOS", 105, "Final", "game-recap-magic-115-celtics-105-nov-16"),
    ("0022600246", "2026-11-16", "CHI", 115, "CLE", 126, "Final", "game-recap-cavaliers-126-bulls-115-nov-16"),
    ("0022600247", "2026-11-16", "MEM", 136, "WAS", 120, "Final", "game-recap-grizzlies-136-wizards-120-nov-16"),
    ("0022600248", "2026-11-16", "PHI", 135, "BKN", 123, "Final", "game-recap-76ers-135-nets-123-nov-16"),
    ("0022600249", "2026-11-16", "HOU", 110, "MIA", 128, "Final", "game-recap-heat-128-rockets-110-nov-16"),
    ("0022600250", "2026-11-16", "POR", 98, "MIN", 106, "Final", "game-recap-timberwolves-106-trail-blazers-98-nov-16"),
    ("0022600251", "2026-11-16", "GSW", 94, "NOP", 115, "Final", "game-recap-pelicans-115-warriors-94-nov-16"),
    ("0022600252", "2026-11-16", "PHX", 117, "DEN", 105, "Final", "game-recap-suns-117-nuggets-105-nov-16"),
    ("0022600253", "2026-11-17", "NYK", 111, "TOR", 102, "Final", "game-recap-knicks-111-raptors-102-nov-17"),
    ("0022600254", "2026-11-17", "POR", 105, "MIN", 106, "Final", "game-recap-timberwolves-106-trail-blazers-105-nov-17"),
    ("0022600255", "2026-11-17", "DET", 105, "SAS", 93, "Final", "game-recap-pistons-105-spurs-93-nov-17"),
    ("0022600256", "2026-11-17", "CHA", 114, "LAL", 118, "Final/OT", "game-recap-lakers-118-hornets-114-nov-17"),
    ("0022600257", "2026-11-17", "UTA", 132, "LAC", 107, "Final", "game-recap-jazz-132-clippers-107-nov-17"),
    ("0022600258", "2026-11-18", "MEM", 124, "CLE", 121, "Final", "game-recap-grizzlies-124-cavaliers-121-nov-18"),
    ("0022600259", "2026-11-18", "HOU", 119, "IND", 104, "Final", "game-recap-rockets-119-pacers-104"),
    ("0022600260", "2026-11-18", "MIL", 130, "MIA", 137, "Final", "game-recap-heat-137-bucks-130-nov-18"),
    ("0022600261", "2026-11-18", "PHI", 121, "ORL", 116, "Final", "game-recap-76ers-121-magic-116"),
    ("0022600262", "2026-11-18", "CHI", 137, "BKN", 107, "Final", "game-recap-bulls-137-nets-107"),
    ("0022600263", "2026-11-18", "WAS", 103, "TOR", 99, "Final", "game-recap-wizards-103-raptors-99-nov-18"),
    ("0022600264", "2026-11-18", "DET", 122, "NOP", 109, "Final", "game-recap-pistons-122-pelicans-109-nov-18"),
    ("0022600265", "2026-11-18", "ATL", 117, "OKC", 112, "Final", "game-recap-hawks-117-thunder-112-nov-18"),
    ("0022600266", "2026-11-18", "BOS", 101, "DEN", 105, "Final", "game-recap-nuggets-105-celtics-101-nov-18"),
    ("0022600267", "2026-11-18", "GSW", 94, "DAL", 116, "Final", "game-recap-mavericks-116-warriors-94-nov-18"),
    ("0022600268", "2026-11-18", "UTA", 109, "LAL", 97, "Final", None),  # recap line not printed in the read
    ("0022600269", "2026-11-18", "PHX", 128, "SAC", 107, "Final", "game-recap-suns-128-kings-107-nov-18"),
]

SCHEMA = "dd3edd74.results.v1"


def game_url(away, home, gid):
    return f"https://www.nba.com/game/{away.lower()}-vs-{home.lower()}-{gid}"


def date_url(date):
    return f"https://www.nba.com/games?date={date}"


def recap_url(slug):
    return f"https://www.nba.com/watch/video/{slug}" if slug else None


def build_rows():
    rows = []
    for gid, date, away, apts, home, hpts, status, slug in READ:
        winner = away if apts > hpts else home
        rows.append({
            "date": date,
            "game_id": gid,
            "away": away,
            "home": home,
            "away_pts": apts,
            "home_pts": hpts,
            "final_score": f"{away} {apts} - {home} {hpts}",
            "winner": winner,
            "status": status,
            "quarter_scores": None,
            "quarter_scores_flag": "UNVERIFIED: not read from an official page for this game (no period table on the date page)",
            "settled": True,
            "settlement_stamp": (f"settled {date} final from the official date page; quarter scores not captured"
                                 + (" (overtime game: the OT period is not itemised)" if status == "Final/OT" else "")),
            "sources": [date_url(date), game_url(away, home, gid)] + ([recap_url(slug)] if slug else []),
            "recap_read": ("recap video slug repeats the two final scores" if slug
                           else "recap line not printed in the read; score table only"),
        })
    return rows


def payload():
    rows = build_rows()
    return {
        "schema": SCHEMA,
        "what": "One row per game: date, teams, final score, quarter scores (null where not captured), "
                "for the official games 2026-11-16, 2026-11-17 and 2026-11-18 (ET dates).",
        "retrieved_utc_window": "2026-11-19T06:55Z to 2026-11-19T07:40Z (session clock; the fetch tool returns no per-call stamp)",
        "primary_source": {"name": "NBA.com Games & Scores (date page)", "urls": [date_url(d) for d in CALENDAR_COUNT]},
        "settlement_rule": ("A game is settled only when its final score is read from the official date page. "
                            "Quarter scores are stored only when read from an official page; otherwise they are null, "
                            "flagged, and the settlement stamp says so. Nothing is estimated or repaired by hand."),
        "counts": {d: sum(1 for r in rows if r["date"] == d) for d in CALENDAR_COUNT},
        "games": rows,
    }


def checks(data):
    """Return a list of (name, passed, detail). Pure function of the artefact and the cross-check files."""
    out = []
    games = data["games"]
    for d, n in CALENDAR_COUNT.items():
        got = sum(1 for g in games if g["date"] == d)
        out.append((f"count {d} == calendar {n}", got == n, f"{got}"))
    out.append(("game ids unique", len({g['game_id'] for g in games}) == len(games), ""))
    with open(SLATE, encoding="utf-8") as fh:
        slate = json.load(fh)["games"]
    by_id = {s["game_id"]: s for s in slate if s["date"] in CALENDAR_COUNT}
    bad = []
    for g in games:
        s = by_id.get(g["game_id"])
        if not s or (s["date"], s["away"], s["home"]) != (g["date"], g["away"], g["home"]):
            bad.append(g["game_id"])
    out.append(("every game matches the committed official slate (date, away, home)", not bad, ",".join(bad)))
    bad = []
    for g in games:
        slug = next((r for r in g["sources"] if "/watch/video/" in r), None)
        if not slug:
            continue
        nums = [int(x) for x in re.findall(r"-(\d{2,3})(?=-|$)", slug.rsplit("/", 1)[-1])]
        if nums[:2] != [max(g["away_pts"], g["home_pts"]), min(g["away_pts"], g["home_pts"])]:
            bad.append(g["game_id"])
    out.append(("recap slugs repeat the score table (winner score first)", not bad, ",".join(bad)))
    with open(B1CE, encoding="utf-8") as fh:
        b = json.load(fh)["games"]
    bmap = {x["game_id"]: x for x in b}
    diffs = []
    for g in games:
        if g["date"] != "2026-11-18":
            continue
        x = bmap.get(g["game_id"])
        if not x or (x["away"], x["away_score"], x["home"], x["home_score"]) != (g["away"], g["away_pts"], g["home"], g["home_pts"]):
            diffs.append(g["game_id"])
    out.append(("11/18 finals agree with the independent b1ce1334 capture (12/12)", not diffs and
                sum(1 for g in games if g["date"] == "2026-11-18") == 12, ",".join(diffs)))
    out.append(("no quarter value is filled in (all null)", all(g["quarter_scores"] is None for g in games), ""))
    out.append(("every row cites an https official URL", all(all(u.startswith("https://www.nba.com/") for u in g["sources"])
                                                             for g in games), ""))
    out.append(("OT game is labelled Final/OT", any(g["status"] == "Final/OT" for g in games), ""))
    return out


def main(argv):
    if "--check" in argv:
        data = json.load(open(OUT, encoding="utf-8"))
        # The artefact must equal what this script would write (no hand edits).
        same = data == payload()
        res = checks(data)
        for name, ok, detail in res:
            print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
        print(f"artefact equals script output: {same}")
        return 0 if same and all(ok for _, ok, _ in res) else 1
    os.makedirs(OUT_DIR, exist_ok=True)
    data = payload()
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    res = checks(data)
    for name, ok, detail in res:
        print(("PASS " if ok else "FAIL ") + name)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(data['games'])} games")
    return 0 if all(ok for _, ok, _ in res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
