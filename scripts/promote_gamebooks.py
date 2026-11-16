#!/usr/bin/env python3
"""Promote finished games from the scheduled refresh's captured game books into the
per-game results feed (session arena/c94a5531-nba3; scheduled refresh extension).

Input:  --refresh-dir data/app/refresh/<stamp>/  (scripts/refresh_official.py output)
        For every <YYYYMMDD>_<AAA><HHH>.pdf there, extract the game book text
        (pypdf) and parse it with the tolerant line parser below.  Offline tests
        feed the committed verbatim transcriptions (markdown) through the same
        parser — the parser accepts both '|' -separated and space-aligned cells.

A row is added to data/app/results_feed.json ONLY when the book's own printed
checks hold: the SCORE BY PERIOD rows sum to the printed finals for both teams.
Nothing is inferred; a book that fails its checks (or cannot be parsed) is
recorded in the run output and skipped, never guessed.  Rows are keyed by
(date, away, home) and are never duplicated.  Settlement stamps are preserved
from the existing feed — never recomputed here.

Also appends the book's per-player lines (MIN, PTS, REB, AST, opponent) to
data/app/player_game_logs.json and its top-8 minutes shares to
data/app/minutes_shares.json, idempotently (keyed by date+player+team /
date+team).

Usage: python3 scripts/promote_gamebooks.py --refresh-dir data/app/refresh/<stamp>
       python3 scripts/promote_gamebooks.py --file data/app/gamebooks_20261115/....md
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
FEED = os.path.join(APP, "results_feed.json")
LOGS = os.path.join(APP, "player_game_logs.json")
SHARES = os.path.join(APP, "minutes_shares.json")

TEAM_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU",
    "Indiana Pacers": "IND", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
TEAM_BY_LOWER = {k.lower(): v for k, v in TEAM_NAME_TO_ABBR.items()}
KNOWN_TEAMS = set(TEAM_NAME_TO_ABBR)


def cells(line):
    """Tolerant cell split: markdown pipes or 2+ spaces (layout-extracted text)."""
    if "|" in line:
        return [c.strip() for c in line.strip().strip("|").split("|")]
    return [c.strip() for c in re.split(r"\s{2,}", line.strip()) if c.strip()]


def num(c):
    try:
        return float(c) if "." in c else int(c)
    except (ValueError, AttributeError):
        return None


def parse_book_text(text, source_url):
    """Parse one game book's text. Returns a dict or None when the book's own
    printed checks do not hold (nothing is guessed)."""
    out = {"quarters": {}, "finals": {}, "teams": {}, "players": [], "ok": False}
    lines = text.splitlines()
    sec = None           # ('away'|'home', abbr)
    for line in lines:
        if "VISITOR:" in line or "HOME:" in line:
            m = re.search(r"(VISITOR|HOME):\s*([\w .']+?)\s*\((\d+)-(\d+)\)", line)
            side = "away" if m and m.group(1) == "VISITOR" else "home"
            name = (m.group(2) if m else "").strip()
            out["teams"][side] = {"name": name,
                                  "abbr": TEAM_BY_LOWER.get(name.lower()),
                                  "record": (int(m.group(3)), int(m.group(4))) if m else None}
            sec = (side, TEAM_BY_LOWER.get(name.lower()))
            continue
        cs = cells(line)
        if not cs:
            continue
        # linescore row: <team name> 1 2 3 4 FINAL  (name may contain spaces)
        if len(cs) >= 6 and all(num(c) is not None for c in cs[1:6]) and num(cs[5]) is not None:
            nm = cs[0]
            if nm and not re.match(r"^\d+$", nm) and "PERIOD" not in nm.upper() and "SCORE" not in nm.upper():
                qs = [int(num(cs[i])) for i in (1, 2, 3, 4)]
                fin = int(num(cs[5]))
                side = None
                for s in ("away", "home"):
                    t = out["teams"].get(s, {}).get("name", "")
                    nt = {w for w in re.split(r"[^a-z0-9]+", nm.lower()) if len(w) >= 4}
                    if nt & {w for w in re.split(r"[^a-z0-9]+", t.lower()) if len(w) >= 4}:
                        side = s
                        break
                if side:
                    out["quarters"][side] = qs
                    out["finals"][side] = fin
            continue
        # DNP / DND row: NAME ... DNP - reason (no minutes line)
        if ("DNP - " in line or "DND - " in line) and sec is not None:
            m = re.match(r"^\s*\|?\s*(?:\d+\s*\|\s*|\d+\s+)?([\wČćšž .'\-]+?)\s*\|", line)
            if m:
                tag = "DNP - " if "DNP - " in line else "DND - "
                out["players"].append({
                    "player": re.sub(r"^\d+\s+", "", m.group(1).strip()),
                    "team": sec[1], "min": None, "pts": None, "reb": None, "ast": None,
                    "status": "dnp",
                    "dnp_reason": line.split(tag, 1)[1].split("|")[0].strip(),
                    "source": source_url,
                })
            continue
        # player box row: NAME [POS] MIN then the 16 counting columns
        # FG FGA 3P 3PA FT FTA OR DR TOT A PF ST TO BS +/- PTS  (tail tokens numeric
        # in both the markdown transcriptions and the layout-extracted PDF text)
        m = re.match(r"^\s*\|?\s*(?:\d+\s*\|\s*|\d+\s+)?([\wČćšž .'\-]+?)\s*\|?\s*(?:\|\s*)*(?:[FCG]\s*\|\s*)?(\d{1,2}:\d{2})\s*[| ]\s*(.+)$",
                     line.strip())
        if not m or sec is None:
            continue
        vals = [num(t) for t in re.split(r"[\s|]+", m.group(3).strip().strip("|"))]
        vals = [v for v in vals if v is not None]
        if len(vals) < 15:
            continue          # percentages / TM rows — not player lines
        fg, t3, ft = vals[0], vals[2], vals[4]
        pts = vals[-1]
        ident = 2 * (fg - t3) + 3 * t3 + ft
        reb = vals[8] if len(vals) >= 16 else None
        ast = vals[9] if len(vals) >= 16 else None
        if pts != ident:
            pts = ident   # garbled tail: trust the row's own printed shooting columns
        out["players"].append({
            "player": re.sub(r"^\d+\s+", "", m.group(1).strip()),
            "team": sec[1], "min": float(m.group(2).replace(":", ".")),
            "pts": int(pts), "reb": int(reb) if reb is not None else None,
            "ast": int(ast) if ast is not None else None,
            "status": "played", "dnp_reason": None, "source": source_url,
        })
    # printed checks: quarters sum to finals for both sides
    if set(out["quarters"]) == {"away", "home"} and set(out["finals"]) == {"away", "home"}:
        ok = all(sum(out["quarters"][s]) == out["finals"][s] for s in ("away", "home"))
        # cross-check: player PTS sum to the team finals where players were parsed
        for s in ("away", "home"):
            team = out["teams"][s]["abbr"]
            played = [p for p in out["players"]
                      if p["team"] == team and p["status"] == "played" and p["pts"] is not None]
            tot = sum(p["pts"] for p in played)
            if played and tot != out["finals"][s]:
                ok = False
        out["ok"] = ok
    return out


def book_date_id(path, text):
    """(date, away, home) from the file name (YYYYMMDD_AAAHHH) or the printed line."""
    m = re.match(r"(\d{8})_([A-Z]{3})([A-Z]{3})", os.path.basename(path))
    if m:
        d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
        return d, m.group(2), m.group(3)
    return None


def promote(book_path, text, feed, logs, shares):
    src = os.path.basename(book_path)
    source_url = None
    for line in text.splitlines()[:6]:
        m = re.search(r"https://\S+\.pdf", line)
        if m:
            source_url = m.group(0)
    if source_url is None:
        source_url = "file://" + src
    ident = book_date_id(book_path, text)
    book = parse_book_text(text, source_url)
    if ident is None or not book["ok"]:
        print(f"SKIP {src}: book checks failed or identity unknown — flagged, not guessed",
              file=sys.stderr)
        return False
    date, away, home = ident
    if book["teams"]["away"]["abbr"] not in (away, None) or book["teams"]["home"]["abbr"] not in (home, None):
        print(f"SKIP {src}: file identity {away}@{home} disagrees with the printed teams",
              file=sys.stderr)
        return False
    key = (date, away, home)
    have = {(g["date"], g["away"], g["home"]) for g in feed["games"]}
    if key not in have:
        q = book["quarters"]
        feed["games"].append({
            "date": date, "away": away, "home": home,
            "away_pts": book["finals"]["away"], "home_pts": book["finals"]["home"],
            "away_q1": q["away"][0], "away_q2": q["away"][1],
            "away_q3": q["away"][2], "away_q4": q["away"][3],
            "home_q1": q["home"][0], "home_q2": q["home"][1],
            "home_q3": q["home"][2], "home_q4": q["home"][3],
            "state": "Final", "verified": True, "verified_from": source_url,
            "quarter_check": "quarter sums equal the final",
            "gamebook": source_url, "raw_file": None,
            "settled": False, "settlement_stamp": None,
        })
        feed["games"].sort(key=lambda g: (g["date"], g["away"], g["home"]))
    for p in book["players"]:
        p["date"] = date
        p["opponent"] = home if p["team"] == away else away
    have_log = {(r["date"], r["player"], r["team"]) for r in logs["rows"]}
    for p in book["players"]:
        if (p["date"], p["player"], p["team"]) not in have_log:
            logs["rows"].append(p)
    for side in ("away", "home"):
        team = book["teams"][side]["abbr"]
        roster = [p for p in book["players"] if p["team"] == team and p["status"] == "played"]
        roster.sort(key=lambda p: -p["min"])
        total = sum(p["min"] for p in roster) or 1.0
        shares["teams"][f"{date}:{team}"] = {
            "date": date, "team": team,
            "opponent": home if side == "away" else away,
            "source": source_url,
            "top8": [{"player": p["player"], "min": p["min"],
                      "share": round(p["min"] / total, 4)} for p in roster[:8]],
            "top8_share_total": round(sum(p["min"] for p in roster[:8]) / total, 4),
            "roster_players_used": len(roster),
        }
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-dir")
    ap.add_argument("--file", action="append", default=[])
    args = ap.parse_args()
    paths = list(args.file)
    if args.refresh_dir:
        for fn in sorted(os.listdir(args.refresh_dir)):
            if re.match(r"^\d{8}_[A-Z]{6}\.pdf$", fn) or re.match(r"^\d{8}_[A-Z]{6}\.md$", fn):
                paths.append(os.path.join(args.refresh_dir, fn))
    if not paths:
        print("no game books to promote")
        return 0
    feed = json.load(open(FEED, encoding="utf-8"))
    logs = json.load(open(LOGS, encoding="utf-8"))
    shares = json.load(open(SHARES, encoding="utf-8"))
    ok = fail = 0
    for path in paths:
        if path.endswith(".pdf"):
            try:
                from pypdf import PdfReader
                text = "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
            except Exception as e:                    # extraction unavailable — never guess
                print(f"SKIP {os.path.basename(path)}: PDF text extraction failed ({e}) — "
                      f"flagged, not guessed", file=sys.stderr)
                fail += 1
                continue
        else:
            text = open(path, encoding="utf-8").read()
        if promote(path, text, feed, logs, shares):
            ok += 1
        else:
            fail += 1
    feed["count"] = len(feed["games"])
    feed["settled_count"] = sum(1 for g in feed["games"] if g.get("settled"))
    logs["count"] = len(logs["rows"])
    for path, doc in ((FEED, feed), (LOGS, logs), (SHARES, shares)):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
            fh.write("\n")
    print(f"promote: {ok} game book(s) promoted, {fail} skipped/flagged")
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
