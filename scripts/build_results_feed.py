"""Build the official per-game result feed and the per-player game logs.

One row per game: date, teams, final score, quarter scores. A row is settled only after both
official reads agree:
  * the official game page shows 'Final' (or 'Final/OT'), and
  * the gamebook PDF's printed FINAL equals the sum of its four printed quarters, and equals the
    final score on the game page.
Any row that fails is written with verified=false and the reason, never corrected by hand.

Player logs come from the same gamebooks. scripts/parse_gamebook.py accepts a player row only if
it reconciles arithmetically; rejected rows are published as rejected, with the raw line.

Outputs (per --day, default 2026-11-14 — the default run stays byte-identical):
  data/live/results/settled_<day>.json         one row per settled game, with the stamp
  data/live/player_game_logs[[_<day>]].json    per-player logs (minutes, pts, reb, ast, opponent)

Days are added by capture (a raw gamebook transcription in data/live/raw/ plus a feed row in
data/live/results/games_<day>.json) and registered in DAYS below — never by editing values.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_gamebook import parse_gamebook, summarise   # noqa: E402

RAW = ROOT / "data" / "live" / "raw"
FEED = ROOT / "data" / "live" / "results" / "games_2026-11-14.json"
OUT_SETTLED = ROOT / "data" / "live" / "results" / "settled_2026-11-14.json"
OUT_LOGS = ROOT / "data" / "live" / "player_game_logs.json"

BOOKS = {
    "0022600231": ("20261114_DENNOP", "DEN", "NOP", "Denver Nuggets", "New Orleans Pelicans"),
    "0022600232": ("20261114_DALCLE", "DAL", "CLE", "Dallas Mavericks", "Cleveland Cavaliers"),
    "0022600233": ("20261114_DETMIA", "DET", "MIA", "Detroit Pistons", "Miami Heat"),
    "0022600234": ("20261114_BKNMEM", "BKN", "MEM", "Brooklyn Nets", "Memphis Grizzlies"),
    "0022600235": ("20261114_CHIMIN", "CHI", "MIN", "Chicago Bulls", "Minnesota Timberwolves"),
}

BOOKS_20261115 = {
    "0022600236": ("20261115_INDPHI", "IND", "PHI", "Indiana Pacers", "Philadelphia 76ers"),
    "0022600237": ("20261115_LALPHX", "LAL", "PHX", "Los Angeles Lakers", "Phoenix Suns"),
}

# Per-day wiring. settled_utc is the stamp of the build that last confirmed the finals against
# the official pages; it moves only when official values are re-read (never the wall clock).
DAYS = {
    "2026-11-14": {
        "books": BOOKS,
        "feed": FEED,
        "settled": OUT_SETTLED,
        "logs": OUT_LOGS,
        "settled_utc": "2026-11-15T11:52Z",
    },
    "2026-11-15": {
        "books": BOOKS_20261115,
        "feed": ROOT / "data" / "live" / "results" / "games_2026-11-15.json",
        "settled": ROOT / "data" / "live" / "results" / "settled_2026-11-15.json",
        "logs": ROOT / "data" / "live" / "player_game_logs_2026-11-15.json",
        "settled_utc": "2026-11-15T23:59Z",
    },
}


def settle(feed_game: dict, books: dict | None = None) -> dict:
    name = (books or BOOKS)[feed_game["game_id"]][0]
    path = RAW / f"gamebook_{name}.md"
    text = path.read_text(encoding="utf-8")
    away, home = feed_game["away"], feed_game["home"]
    away_name, home_name = feed_game["away_name"], feed_game["home_name"]
    parsed = parse_gamebook(text, game_id=feed_game["game_id"], date=feed_game["date"],
                            away=away, home=home, away_team=away_name, home_team=home_name,
                            source_url=feed_game["gamebook_url"])
    periods = parsed.periods
    # Map the printed period labels to away/home. Labels are the team city/name, not the abbrev,
    # so match on the first token of each full team name, case-insensitively.
    def find(label_hint: str):
        for label, nums in periods.items():
            if label.lower().startswith(label_hint.lower()[:4]):
                return nums
        return None

    away_periods = find(away_name.split()[-1]) or find(away_name.split()[0])
    home_periods = find(home_name.split()[-1]) or find(home_name.split()[0])
    reasons = []
    verified = True

    if feed_game["status"] not in ("Final", "Final/OT"):
        verified = False
        reasons.append(f"game page status is {feed_game['status']!r}, not Final")
    if not away_periods or not home_periods:
        verified = False
        reasons.append("gamebook period table not readable")
    else:
        if away_periods[:4] != feed_game["away_q"]:
            verified = False
            reasons.append(f"away quarters {away_periods[:4]} != game page {feed_game['away_q']}")
        if home_periods[:4] != feed_game["home_q"]:
            verified = False
            reasons.append(f"home quarters {home_periods[:4]} != game page {feed_game['home_q']}")
        if sum(away_periods[:4]) != away_periods[4]:
            verified = False
            reasons.append("away quarters do not sum to the printed FINAL")
        if sum(home_periods[:4]) != home_periods[4]:
            verified = False
            reasons.append("home quarters do not sum to the printed FINAL")
        if away_periods[4] != feed_game["away_final"]:
            verified = False
            reasons.append("printed away FINAL != game page final")
        if home_periods[4] != feed_game["home_final"]:
            verified = False
            reasons.append("printed home FINAL != game page final")

    return {
        "game_id": feed_game["game_id"], "date": feed_game["date"],
        "tip_et": feed_game["tip_et"], "away": away, "home": home,
        "away_name": away_name, "home_name": home_name,
        "venue": feed_game["venue"], "city": feed_game["city"],
        "status": feed_game["status"],
        "away_q": feed_game["away_q"], "home_q": feed_game["home_q"],
        "away_final": feed_game["away_final"], "home_final": feed_game["home_final"],
        "away_margin": feed_game["away_final"] - feed_game["home_final"],
        "total_points": feed_game["away_final"] + feed_game["home_final"],
        "ot": feed_game["ot"],
        "winner": away if feed_game["away_final"] > feed_game["home_final"] else home,
        "attendance": feed_game["attendance"],
        "verified": verified,
        "verification": {
            "rule": ("settled only when the game page says Final AND the gamebook's printed FINAL "
                     "equals the sum of its four printed quarters AND both agree with the game page"),
            "failures": reasons,
            "game_page": feed_game["source_url"],
            "gamebook": feed_game["gamebook_url"],
        },
        "source_url": feed_game["source_url"],
        "gamebook_url": feed_game["gamebook_url"],
        "retrieved_utc": feed_game["retrieved_utc"],
    }


def main(day: str = "2026-11-14") -> None:
    cfg = DAYS[day]
    feed = json.loads(cfg["feed"].read_text())
    settled = [settle(g, cfg["books"]) for g in feed["games"]]
    settled.sort(key=lambda g: g["game_id"])

    all_rows, per_book = [], {}
    d8 = day.replace("-", "")
    for gid, (name, away, home, away_name, home_name) in cfg["books"].items():
        path = RAW / f"gamebook_{name}.md"
        parsed = parse_gamebook(path.read_text(encoding="utf-8"),
                                game_id=gid, date=day, away=away, home=home,
                                away_team=away_name, home_team=home_name,
                                source_url=f"https://statsdmz.nba.com/pdfs/{d8}/{name}.pdf")
        s = summarise(parsed)
        per_book[gid] = s
        all_rows.extend(r.as_row() for r in parsed.accepted)

    payload_settled = {
        "schema": "nba3.live.settled_feed/v1",
        "session": "arena/2ebb1e75-nba3",
        "game_date": day,
        "settled_utc": cfg["settled_utc"],
        "settlement_stamp_note": ("The stamp is the time this build last confirmed the finals "
                                  "against the official pages. It moves only when the official "
                                  "values are re-read."),
        "one_row_per_game": True,
        "counts": {"games": len(settled),
                   "verified": sum(1 for g in settled if g["verified"]),
                   "unverified": sum(1 for g in settled if not g["verified"])},
        "games": settled,
    }
    cfg["settled"].write_text(json.dumps(payload_settled, indent=1) + "\n")

    payload_logs = {
        "schema": "nba3.live.player_logs/v1",
        "session": "arena/2ebb1e75-nba3",
        "game_date": day,
        "what": ("Per-player game logs (minutes, points, rebounds, assists, steals, blocks, "
                 "turnovers, shooting, and the opponent) for every player whose row reconciled "
                 "arithmetically in the official gamebook."),
        "acceptance_rule": ("a player row is accepted only if PTS == 2*FG + 3P + FT, "
                            "TOT == OR + DR, FGM<=FGA, 3PM<=3PA, FTM<=FTA, 3PM<=FGM, and the row "
                            "has gamebook shape (at most three non-empty cells before MIN)."),
        "counts": {
            "printed_rows": sum(s["accepted_rows"] + s["rejected_rows"] for s in per_book.values()),
            "accepted": len(all_rows),
            "rejected": sum(s["rejected_rows"] for s in per_book.values()),
            "by_game": {gid: {"accepted": s["accepted_rows"], "rejected": s["rejected_rows"],
                              "reconciliation": s["team_reconciliation"]}
                        for gid, s in per_book.items()},
        },
        "rejected_detail": {gid: s["rejected_detail"] for gid, s in per_book.items()
                            if s["rejected_detail"]},
        "rows": sorted(all_rows, key=lambda r: (r["game_id"], r["team"], -r["min"])),
    }
    cfg["logs"].write_text(json.dumps(payload_logs, indent=1) + "\n")

    print(f"settled {payload_settled['counts']['games']} games "
          f"({payload_settled['counts']['verified']} verified)")
    for g in settled:
        print(f"  {g['game_id']} {g['away']}{g['away_q']}={g['away_final']} "
              f"{g['home']}{g['home_q']}={g['home_final']} verified={g['verified']} "
              f"{g['verification']['failures'] or ''}")
    print(f"player logs: {len(all_rows)} accepted, "
          f"{payload_logs['counts']['rejected']} rejected of {payload_logs['counts']['printed_rows']}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-11-14", choices=sorted(DAYS))
    main(ap.parse_args().day)
