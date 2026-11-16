"""Official per-game result feed with quarter scores (session arena/caad4c37-nba3).

The brief asks the result feed to store one row per game: date, teams, final score, quarter
scores. On `main` when this session started, `data/app/results_feed.json` carried 14 settled
games and every `*_q1..*_q4` field was null with the note "quarter scores not captured - blank,
flagged". The official game books published by the NBA at statsdmz.nba.com print a
"SCORE BY PERIOD" block, so the field is obtainable from an official source.

This script reads ONLY files that are already committed to the repository:

  * data/arena_caad4c37/quarters/*.md   - this session's verbatim excerpts of the 2026-11-13
                                          game books (header + SCORE BY PERIOD + team totals)
  * data/app/gamebooks/*.md             - the 2026-11-14 full game-book transcriptions already
                                          committed by session arena/79341829-nba3 (read-only
                                          here; this session does not own or edit them)
  * data/app/results_feed.json          - the date, teams and final scores of record

It never fetches the network and never infers a value. A quarter score is written only when an
official source printed it; otherwise the field is null and the game is flagged.

Run:  python3 scripts/quarters_caad4c37.py            (writes the artefact)
      python3 scripts/quarters_caad4c37.py --check     (rebuild in memory, diff, exit 1 on drift)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pinned so an offline CI replay reproduces the artefact byte for byte. The retrieval
# timestamps that matter are the per-file stamps written inside the transcriptions.
BUILD_UTC = "2026-11-16T02:19Z"
SESSION = "arena/caad4c37-nba3"

EXCERPTS = ROOT / "data" / "arena_caad4c37" / "quarters"
COMMITTED_GAMEBOOKS = ROOT / "data" / "app" / "gamebooks"
FEED = ROOT / "data" / "app" / "results_feed.json"
OUT = ROOT / "data" / "arena_caad4c37" / "result_feed_quarters.json"

GAMEBOOK_URL = "https://statsdmz.nba.com/pdfs/{d}/{d}_{away}{home}.pdf"
SCOREBOARD_URL = "https://www.nba.com/games?date={date}"

# Team nickname as printed by the official game book -> standard 3-letter code.
NICKNAMES = {
    "hawks": "ATL", "nets": "BKN", "celtics": "BOS", "hornets": "CHA", "bulls": "CHI",
    "cavaliers": "CLE", "mavericks": "DAL", "nuggets": "DEN", "pistons": "DET",
    "warriors": "GSW", "rockets": "HOU", "pacers": "IND", "clippers": "LAC",
    "lakers": "LAL", "grizzlies": "MEM", "heat": "MIA", "bucks": "MIL",
    "timberwolves": "MIN", "pelicans": "NOP", "knicks": "NYK", "thunder": "OKC",
    "magic": "ORL", "76ers": "PHI", "suns": "PHX", "trail blazers": "POR",
    "kings": "SAC", "spurs": "SAS", "raptors": "TOR", "jazz": "UTA",
    "wizards": "WAS",
}

# A line-score text line, e.g. "GRIZZLIES 38 33 32 26 129" or "HEAT 29 25 38 41 133".
TEXT_LINE = re.compile(r"^([A-Za-z0-9'\. ]+?)\s+((?:\d{1,3}\s+){3,5}\d{1,3})$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _ints(values: list[str]) -> list[int] | None:
    out = []
    for v in values:
        if not re.fullmatch(r"\d{1,3}", v):
            return None
        out.append(int(v))
    return out


def _team(cell: str) -> str | None:
    return NICKNAMES.get(re.sub(r"\s+", " ", cell).strip().casefold().strip("."))


def parse_periods(text: str) -> list[dict]:
    """Return every period reading printed in `text`, each with its provenance.

    A reading is (team, q1..q4, optional ot columns, final, where). It is accepted only when the
    quarter columns sum to the final column printed on the same row - that is the game book's own
    arithmetic, and it is what makes a corrupted extraction detectable rather than usable.
    """
    readings: list[dict] = []
    lines = text.splitlines()

    for i, line in enumerate(lines):
        # (a) markdown rows inside a block whose header mentions SCORE BY PERIOD
        if line.lstrip().startswith("|") and "SCORE BY PERIOD" in line:
            for nxt in lines[i + 1: i + 8]:
                if not nxt.lstrip().startswith("|"):
                    break
                cells = _cells(nxt)
                if len(cells) < 5 or set(cells[0]) <= set("-: "):
                    continue
                team = _team(cells[0])
                if team is None:
                    continue
                nums = _ints([c for c in cells[1:] if c != ""])
                if not nums or len(nums) not in (5, 6):
                    readings.append({"team": team, "status": "unparseable",
                                     "raw": nxt.strip(), "where": "table"})
                    continue
                final, quarters = nums[-1], nums[:-1]
                ok = sum(quarters) == final
                readings.append({"team": team, "quarters": quarters, "final": final,
                                 "status": "ok" if ok else "sum_mismatch",
                                 "raw": nxt.strip(), "where": "table"})

        # (b) standalone line-score text lines, e.g. "HEAT 29 25 38 41 133"
        m = TEXT_LINE.match(line.strip())
        if m:
            team = _team(m.group(1))
            nums = _ints(m.group(2).split())
            if team is None or nums is None or len(nums) not in (5, 6):
                continue
            final, quarters = nums[-1], nums[:-1]
            ok = sum(quarters) == final
            readings.append({"team": team, "quarters": quarters, "final": final,
                             "status": "ok" if ok else "sum_mismatch",
                             "raw": line.strip(), "where": "text_line"})
    return readings


def choose(readings: list[dict], team: str, final_pts: int) -> dict:
    """Pick the reading for `team`, recording every disagreement rather than hiding it."""
    mine = [r for r in readings if r.get("team") == team]
    good = [r for r in mine if r.get("status") == "ok"]
    agree_final = [r for r in good if r["final"] == final_pts]

    if not mine:
        return {"quarters": None, "verified": False, "reason": "no period row printed for this team",
                "conflict": False}
    if not good:
        return {"quarters": None, "verified": False,
                "reason": "period row printed but its own columns do not sum to its final (corrupt extraction)",
                "conflict": False, "raw": [r["raw"] for r in mine]}

    if agree_final:
        distinct = {tuple(r["quarters"]) for r in agree_final}
        if len(distinct) == 1:
            r = agree_final[0]
            return {"quarters": list(r["quarters"]), "verified": True, "conflict": False,
                    "where": r["where"], "raw": [x["raw"] for x in agree_final]}
        # Two official readings, both internally consistent and both matching the final.
        return {"quarters": None, "verified": False, "conflict": True,
                "reason": "two internally-consistent official readings disagree",
                "raw": [r["raw"] for r in agree_final]}

    # Readings exist and are internally consistent, but none matches the final of record.
    return {"quarters": None, "verified": False, "conflict": True,
            "reason": "official period reading does not sum to the final score of record",
            "raw": [r["raw"] for r in good]}


def build() -> dict:
    feed = json.loads(FEED.read_text())
    sources = sorted(
        [p for p in EXCERPTS.glob("*.md")] + [p for p in COMMITTED_GAMEBOOKS.glob("*.md")]
    )

    games = []
    for g in feed["games"]:
        date = g["date"]
        d = date.replace("-", "")
        away, home = g["away"], g["home"]
        url = GAMEBOOK_URL.format(d=d, away=away, home=home)
        files = [p for p in sources if d in p.name and f"{away}{home}" in p.name]
        if not files:
            files = [p for p in sources if d in p.name]
        text = "\n".join(p.read_text(encoding="utf-8") for p in files)
        readings = parse_periods(text)

        a = choose(readings, away, g["away_pts"])
        h = choose(readings, home, g["home_pts"])

        state = "both" if (a["verified"] and h["verified"]) else (
            "partial" if (a["verified"] or h["verified"]) else "none")

        row = {
            "date": date,
            "away": away,
            "home": home,
            "away_pts": g["away_pts"],
            "home_pts": g["home_pts"],
            "state": g["state"],
            "away_quarters": a["quarters"],
            "home_quarters": h["quarters"],
            "quarters_verified": state,
            "gamebook_source": url,
            "scoreboard_source": SCOREBOARD_URL.format(date=date),
            "transcription_files": [str(p.relative_to(ROOT)) for p in files],
        }
        for side, res in (("away", a), ("home", h)):
            if not res["verified"]:
                row[f"{side}_quarters_note"] = res["reason"]
            if res.get("conflict"):
                row[f"{side}_quarters_conflict_raw"] = res.get("raw", [])
        games.append(row)

    games.sort(key=lambda r: (r["date"], r["away"], r["home"]))
    counts = {
        "games": len(games),
        "both_teams_verified": sum(1 for r in games if r["quarters_verified"] == "both"),
        "partial": sum(1 for r in games if r["quarters_verified"] == "partial"),
        "none": sum(1 for r in games if r["quarters_verified"] == "none"),
        "quarter_cells_written": sum(
            (4 if r["away_quarters"] else 0) + (4 if r["home_quarters"] else 0) for r in games),
        "quarter_cells_possible": 8 * len(games),
    }

    return {
        "schema": "nba3.arena_caad4c37.result_feed_quarters/v1",
        "session": SESSION,
        "built_utc": BUILD_UTC,
        "rule": ("One row per game: date, teams, final score, quarter scores. A quarter score is "
                 "written only where an official NBA game book printed it and the printed quarters "
                 "sum to the printed final. Anything else stays null and is flagged; nothing is "
                 "inferred from a total, a possession count or another game."),
        "inputs": {
            "finals_of_record": str(FEED.relative_to(ROOT)),
            "game_books_this_session": str(EXCERPTS.relative_to(ROOT)),
            "game_books_committed_earlier": str(COMMITTED_GAMEBOOKS.relative_to(ROOT)),
            "index": "https://www.nba.com/games?date=2026-11-13",
        },
        "counts": counts,
        "games": games,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="rebuild in memory and fail if the committed artefact differs")
    args = ap.parse_args()

    data = build()
    if args.check:
        committed = json.loads(OUT.read_text())
        if committed != data:
            print("result_feed_quarters.json does not reproduce from the committed transcriptions",
                  file=sys.stderr)
            print(json.dumps({"counts_committed": committed.get("counts"),
                              "counts_rebuilt": data.get("counts")}, indent=1), file=sys.stderr)
            return 1
        print(f"OK: {OUT.relative_to(ROOT)} reproduces "
              f"({data['counts']['both_teams_verified']}/{data['counts']['games']} games fully "
              f"quarter-verified)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    c = data["counts"]
    print(f"wrote {OUT.relative_to(ROOT)}: {c['games']} games, "
          f"{c['both_teams_verified']} both-teams verified, {c['partial']} partial, {c['none']} none, "
          f"{c['quarter_cells_written']}/{c['quarter_cells_possible']} quarter cells written")
    for r in data["games"]:
        if r["quarters_verified"] != "both":
            print(f"  flagged {r['date']} {r['away']}@{r['home']}: {r['quarters_verified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
