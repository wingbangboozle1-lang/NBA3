#!/usr/bin/env python3
"""capture_04a81bce.py — official-round capture, verification and model re-cut (O1-O4).

Reads the raw official-source transcripts under
``data/rounds/2026-11-19-04a81bce/raw/`` (25 statsdmz game books 2026-11-16..18,
nba.com standings + three team-stat pages, and the 2026-11-19 injury-report
revision chain) and emits verified JSON under
``data/rounds/2026-11-19-04a81bce/verified/``.

Hard rules (standing brief):
  * never infer — a quarter vector is accepted ONLY when its sum equals the
    printed final; a conflicting or missing vector is flagged and left blank;
  * every emitted row carries its official source URL;
  * player rows pass identity checks (PTS == 2*FG + 3P + FT, TOT == OR + DR);
    failing rows are flagged and dropped, never repaired;
  * team totals are cross-summed from accepted player rows and flagged on
    mismatch.

Derived (O2 re-cut): measured home-win rate from official HOME/ROAD splits,
per-team luck z (Pythagorean), totals as possessions x PPP, rest/B2B/3-in-4
plus sourced travel distance for the 2026-11-19 slate, and explicit minutes
redistribution for players on the official injury report.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "data" / "rounds" / "2026-11-19-04a81bce"
RAW = ROUND / "raw"
BOOKS = RAW / "gamebooks"
VERIFIED = ROUND / "verified"

GAMEBOOK_URL = "https://statsdmz.nba.com/pdfs/{d}/{d}_{a}{h}.pdf"

# Verified finals for the round (official game books; cross-checked by tests).
FINALS = {
    "20261116_ORLBOS": ("2026-11-16", "ORL", "BOS", 115, 105, "245"),
    "20261116_MEMWAS": ("2026-11-16", "MEM", "WAS", 136, 120, "247"),
    "20261116_CHICLE": ("2026-11-16", "CHI", "CLE", 115, 126, "246"),
    "20261116_HOUMIA": ("2026-11-16", "HOU", "MIA", 110, 128, "249"),
    "20261116_PHIBKN": ("2026-11-16", "PHI", "BKN", 135, 123, "248"),
    "20261116_GSWNOP": ("2026-11-16", "GSW", "NOP", 94, 115, "251"),
    "20261116_PORMIN": ("2026-11-16", "POR", "MIN", 98, 106, "250"),
    "20261116_PHXDEN": ("2026-11-16", "PHX", "DEN", 117, 105, "252"),
    "20261117_NYKTOR": ("2026-11-17", "NYK", "TOR", 111, 102, "253"),
    "20261117_DETSAS": ("2026-11-17", "DET", "SAS", 105, 93, "255"),
    "20261117_PORMIN": ("2026-11-17", "POR", "MIN", 105, 106, "254"),
    "20261117_UTALAC": ("2026-11-17", "UTA", "LAC", 132, 107, "257"),
    "20261117_CHALAL": ("2026-11-17", "CHA", "LAL", 114, 118, "256"),
    "20261118_HOUIND": ("2026-11-18", "HOU", "IND", 119, 104, "259"),
    "20261118_MEMCLE": ("2026-11-18", "MEM", "CLE", 124, 121, "258"),
    "20261118_PHIORL": ("2026-11-18", "PHI", "ORL", 121, 116, "261"),
    "20261118_MILMIA": ("2026-11-18", "MIL", "MIA", 130, 137, "260"),
    "20261118_CHIBKN": ("2026-11-18", "CHI", "BKN", 137, 107, "262"),
    "20261118_WASTOR": ("2026-11-18", "WAS", "TOR", 103, 99, "263"),
    "20261118_DETNOP": ("2026-11-18", "DET", "NOP", 122, 109, "264"),
    "20261118_ATLOKC": ("2026-11-18", "ATL", "OKC", 117, 112, "265"),
    "20261118_BOSDEN": ("2026-11-18", "BOS", "DEN", 101, 105, "266"),
    "20261118_GSWDAL": ("2026-11-18", "GSW", "DAL", 94, 116, "267"),
    "20261118_UTALAL": ("2026-11-18", "UTA", "LAL", 109, 97, "268"),
    "20261118_PHXSAC": ("2026-11-18", "PHX", "SAC", 128, 107, "269"),
}

TEAM_ABBR = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
    "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
    "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
    "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
    "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks",
    "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
    "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
    "UTA": "Jazz", "WAS": "Wizards",
}

# Players on the official 2026-11-19 8:00 PM injury report (01:45 AM revision),
# names as printed on the report (Last, First). Kuminga/Pullin team attribution
# resolved to MIN from official game books (see injury raw file).
INJURY_REPORT_PLAYERS = [
    ("Beal, Bradley", "LAC"), ("Ingram, Brandon", "LAC"),
    ("Martinelli, Nick", "LAC"), ("Miller, Jordan", "LAC"),
    ("Brown, Maliq", "SAS"), ("Gillespie, Ja'Kobi", "SAS"),
    ("Harper, Dylan", "SAS"), ("Harris, Tobias", "SAS"),
    ("Quaintance, Jayden", "SAS"),
    ("Beringer, Joan", "MIN"), ("Clark, Jaylen", "MIN"),
    ("DiVincenzo, Donte", "MIN"), ("Edwards, Anthony", "MIN"),
    ("Kuminga, Jonathan", "MIN"), ("Pullin, Zyon", "MIN"),
    ("Avdija, Deni", "POR"), ("Camara, Toumani", "POR"),
    ("Carlson, Branden", "POR"), ("Krejci, Vit", "POR"),
    ("Morant, Ja", "POR"), ("Sharpe, Shaedon", "POR"),
    ("Williams III, Robert", "POR"), ("Youngblood, Chris", "POR"),
]

SLATE_1119 = [("GSW", "MEM"), ("LAC", "SAS"), ("NYK", "MIN"), ("POR", "MIL")]

FULL_TO_ABBR = {
    "Golden State Warriors": "GSW", "Memphis Grizzlies": "MEM",
    "LA Clippers": "LAC", "San Antonio Spurs": "SAS",
    "New York Knicks": "NYK", "Minnesota Timberwolves": "MIN",
    "Portland Trail Blazers": "POR", "Milwaukee Bucks": "MIL",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _f(x) -> float:
    return float(str(x).replace(",", ""))


def name_key(name: str):
    """Order-insensitive token key so 'Beal, Bradley' == 'Bradley Beal'."""
    toks = [t.strip(".").lower() for t in re.split(r"[,\s]+", name) if t.strip(".")]
    return tuple(sorted(toks))


# --------------------------------------------------------------------------
# game books
# --------------------------------------------------------------------------

PERIOD_STANDALONE = re.compile(
    r"^([A-Za-z][A-Za-z .'\-]+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?:\s+(\d+))?\s+(\d+)\s*$"
)


def parse_period_candidates(text: str):
    out = []
    for line in text.splitlines():
        s = re.sub(r"</?u>", "", line).strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            nums = [c for c in cells[1:] if re.fullmatch(r"-?\d+", c)]
            if (len(cells) >= 6 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .'\-]+", cells[0])
                    and len(nums) >= 5):
                total = int(nums[-1])
                periods = [int(n) for n in nums[:-1]]
                out.append((cells[0], periods, total, "table"))
            continue
        m = PERIOD_STANDALONE.match(s)
        if m:
            label = m.group(1).strip()
            periods = [int(m.group(i)) for i in (2, 3, 4, 5)]
            if m.group(6):
                periods.append(int(m.group(6)))
            total = int(m.group(7))
            out.append((label, periods, total, "standalone"))
    return out


def match_team(label: str, abbrs):
    lab = label.strip().lower()
    for a in abbrs:
        if lab == a.lower() or TEAM_ABBR[a].lower() in lab or lab in TEAM_ABBR[a].lower():
            return a
    return None


def resolve_quarters(text, away, home, a_fin, h_fin):
    want = {away: a_fin, home: h_fin}
    cands = parse_period_candidates(text)
    flags = []
    resolved = {away: None, home: None}
    for team in (away, home):
        team_cands = []
        for label, periods, total, kind in cands:
            if match_team(label, (team,)) == team:
                ok = sum(periods) == total == want[team]
                team_cands.append((label, periods, total, kind, ok))
        good = [c for c in team_cands if c[4]]
        bad = [c for c in team_cands if not c[4]]
        if good:
            good.sort(key=lambda c: 0 if c[3] == "standalone" else 1)
            resolved[team] = good[0][1]
        else:
            flags.append(
                f"{team}: no period vector sums to printed final {want[team]}; left blank")
        for label, periods, total, kind, _ok in bad:
            flags.append(
                f"{team}: {kind} row '{label} {' '.join(map(str, periods))} {total}' "
                f"rejected by sum gate (sum {sum(periods)} vs final {want[team]})")
    return resolved, flags


def parse_player_rows(text, away, home):
    rows, flags = [], []
    side = None
    min_re = re.compile(r"(\d{1,2}:\d{2})")
    for line in text.splitlines():
        s = re.sub(r"</?u>", "", line).strip()
        up = s.upper()
        if "VISITOR:" in up:
            side = away
        elif "HOME:" in up:
            side = home
        if not s or s.startswith("| ---") or "SCORE BY PERIOD" in up:
            continue
        if "INACTIVE" in up:
            side = None
            continue
        if "240:00" in s:
            continue
        m = min_re.search(s)
        if not m or side is None:
            continue
        if not (s.startswith("|") or re.match(r"^\d+\s*[A-Za-z]", s)):
            continue
        min_str = m.group(1)
        head = s[: m.start()].strip("| ")
        tail = s[m.end():]
        name_m = re.search(r"([A-Za-z][A-Za-z .'\-]+?)(?:\s*\||\s*$)", head)
        if not name_m:
            continue
        name = name_m.group(1).strip().strip("| ").strip()
        if not name or name.upper().startswith(("DNP", "DND", "POS", "MIN")):
            continue
        nums = [int(x) for x in re.findall(r"-?\d+", tail.replace("--", " "))]
        accepted = None
        # expected: FG FGA 3P 3PA FT FTA OR DR TOT A PF ST TO BS +/- PTS = 16
        if len(nums) >= 16:
            for i in range(0, len(nums) - 15):
                cand = nums[i:i + 16]
                f, fga, f3, f3a, ft, fta, o, d, tot, a, pf, st, to, bs, pm, pts = cand
                if (tot == o + d and pts == 2 * f + f3 + ft
                        and 0 <= f <= fga and 0 <= f3 <= f3a and 0 <= ft <= fta
                        and f3 <= f):
                    accepted = cand
                    break
        if accepted:
            f, fga, f3, f3a, ft, fta, o, d, tot, a, pf, st, to, bs, pm, pts = accepted
            rows.append({
                "team": side, "player": name, "min": min_str,
                "fgm": f, "fga": fga, "fg3m": f3, "fg3a": f3a, "ftm": ft, "fta": fta,
                "oreb": o, "dreb": d, "reb": tot, "ast": a, "pf": pf, "stl": st,
                "tov": to, "blk": bs, "plus_minus": pm, "pts": pts,
            })
        else:
            flags.append(f"{side}: player row '{name}' failed identity checks (dropped)")
    return rows, flags


def load_games():
    games = {}
    for key, (gdate, away, home, a_fin, h_fin, gid) in FINALS.items():
        path = BOOKS / f"{key}.md"
        text = path.read_text(encoding="utf-8")
        url_m = re.search(r"Source URL:\s*(\S+)", text)
        url = url_m.group(1) if url_m else GAMEBOOK_URL.format(
            d=key.split("_")[0], a=away, h=home)
        ret_m = re.search(r"Retrieved \(UTC\):\s*([0-9T:\-Z]+)", text)
        quarters, qflags = resolve_quarters(text, away, home, a_fin, h_fin)
        players, pflags = parse_player_rows(text, away, home)
        # cross-sum identity: accepted player points must total the printed final
        for team, fin in ((away, a_fin), (home, h_fin)):
            s = sum(p["pts"] for p in players if p["team"] == team)
            if s != fin:
                pflags.append(
                    f"{team}: accepted player rows sum to {s}, printed final {fin} "
                    f"(row parse incomplete or box irregularity — flagged, not repaired)")
        games[key] = {
            "game_id": key, "date": gdate, "gid": gid,
            "away": away, "home": home,
            "final": {"away": a_fin, "home": h_fin},
            "quarters": quarters, "quarter_flags": qflags,
            "players": players, "player_flags": pflags,
            "source_url": url,
            "retrieved_utc": ret_m.group(1) if ret_m else None,
        }
    return games


# --------------------------------------------------------------------------
# injury reports
# --------------------------------------------------------------------------

def load_injury_round():
    path = RAW / "injury_reports" / "injury_round_2026-11-19.md"
    text = path.read_text(encoding="utf-8")
    rows = []
    in_rows = False
    for line in text.splitlines():
        if line.startswith("## Verbatim rows"):
            in_rows = True
            continue
        if not in_rows or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 7 and cells[0].startswith("11/"):
            rows.append({
                "game_date": cells[0], "game_time": cells[1], "matchup": cells[2],
                "team": cells[3], "player": cells[4], "status": cells[5],
                "reason": cells[6],
            })
        elif (len(cells) == 7 and cells[4]
              and cells[5] in ("Questionable", "Out", "Available", "Doubtful")):
            rows.append({
                "game_date": "", "game_time": "", "matchup": "",
                "team": "", "player": cells[4], "status": cells[5],
                "reason": cells[6],
            })
    for r in rows:
        if r["player"] in ("Kuminga, Jonathan", "Pullin, Zyon"):
            r["team_attribution"] = {
                "resolved_team": "Minnesota Timberwolves",
                "evidence": [
                    "https://statsdmz.nba.com/pdfs/20261116/20261116_PORMIN.pdf",
                    "https://statsdmz.nba.com/pdfs/20261117/20261117_PORMIN.pdf",
                ],
                "flag": "F-DE0-04/F-DE0-05: report row lacks team cells; "
                        "attribution resolved from official game books",
            }
    revisions = [
        {"revision_et": "12:45 AM",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_12_45AM.pdf",
         "captured_by": "session de0caf5d", "rows": "see de0caf5d round tree"},
        {"revision_et": "01:00 AM",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_00AM.pdf",
         "rows": "identical to 01:45"},
        {"revision_et": "01:15 AM",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_15AM.pdf",
         "rows": "identical to 01:45"},
        {"revision_et": "01:30 AM",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_30AM.pdf",
         "rows": "identical to 01:45"},
        {"revision_et": "01:45 AM",
         "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_01_45AM.pdf",
         "rows": "verbatim in raw file"},
    ]
    diffs = [
        {"pair": "01:00 -> 01:15", "added": 0, "removed": 0, "status_changes": 0},
        {"pair": "01:15 -> 01:30", "added": 0, "removed": 0, "status_changes": 0},
        {"pair": "01:30 -> 01:45", "added": 0, "removed": 0, "status_changes": 0},
    ]
    return {
        "rows": rows,
        "revisions": revisions,
        "consecutive_diffs": diffs,
        "rows_sha256": _sha("\n".join(
            f"{r['player']}|{r['status']}|{r['reason']}" for r in rows)),
    }


# --------------------------------------------------------------------------
# team stats / standings re-cut
# --------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def recut(games, injury):
    ts = {
        "traditional": json.loads((RAW / "teamstats" / "traditional_2026-11-19.json").read_text(encoding="utf-8")),
        "opponent": json.loads((RAW / "teamstats" / "opponent_2026-11-19.json").read_text(encoding="utf-8")),
        "advanced": json.loads((RAW / "teamstats" / "advanced_2026-11-19.json").read_text(encoding="utf-8")),
        "standings": json.loads((RAW / "teamstats" / "standings_2026-11-19.json").read_text(encoding="utf-8")),
    }
    trad = {r["team"]: r for r in ts["traditional"]["rows"]}
    opp = {r["team"]: r for r in ts["opponent"]["rows"]}
    adv = {r["team"]: r for r in ts["advanced"]["rows"]}
    std = {}
    for conf in ("east", "west"):
        for r in ts["standings"][conf]:
            std[r["team"]] = dict(r, conference=conf)
    checks, flags = [], []
    for team, s in std.items():
        gw, gl = (int(x) for x in s["home"].split("-"))
        rw, rl = (int(x) for x in s["road"].split("-"))
        nw, nl = (int(x) for x in s["neutral"].split("-"))
        if gw + gl + rw + rl + nw + nl != s["w"] + s["l"]:
            flags.append(f"{team}: home+road+neutral != overall GP")
        if team in trad:
            if (trad[team]["w"], trad[team]["l"]) != (s["w"], s["l"]) or trad[team]["gp"] != s["w"] + s["l"]:
                flags.append(f"{team}: team-stats W/L/GP disagrees with standings")
        if team in trad and team in opp:
            margin = trad[team]["pts"] - opp[team]["opp_pts"]
            if abs(margin - trad[team]["plus_minus"]) > 0.15:
                flags.append(
                    f"{team}: pts-opp_pts {margin:.1f} != printed +/- {trad[team]['plus_minus']}")
        if team in trad and team in adv:
            if (trad[team]["plus_minus"] > 0) != (adv[team]["net_rtg"] > 0):
                flags.append(f"{team}: net_rtg sign disagrees with +/-")
        checks.append(team)
    hw = hl = 0
    for s in std.values():
        w, l = (int(x) for x in s["home"].split("-"))
        hw += w
        hl += l
    home_games = hw + hl
    rate = hw / home_games if home_games else None
    z = (rate - 0.5) / math.sqrt(0.25 / home_games) if rate is not None else None
    hca = {
        "home_wins": hw, "home_losses": hl, "home_games": home_games,
        "measured_home_win_rate": round(rate, 4) if rate else None,
        "z_vs_half": round(z, 3) if z is not None else None,
        "source_url": ts["standings"]["source_url"],
        "pinned_points_note": (
            "model pin remains the fitted 0.76 pts (existing pipeline fit 102/197); "
            "the points conversion of this re-measured rate is left for reviewer "
            "choice (suggestions register) and is NOT inferred here"),
    }
    luck = []
    for team, s in std.items():
        if team not in trad or team not in opp:
            continue
        pf, pa = trad[team]["pts"], opp[team]["opp_pts"]
        n = s["w"] + s["l"]
        exp = 1.0 / (1.0 + (pf / pa) ** 13.91)
        act = s["w"] / n if n else 0.0
        sd = math.sqrt(exp * (1 - exp) / n) if n else None
        zl = (act - exp) / sd if sd else None
        luck.append({
            "team": team, "gp": n, "actual_win_pct": round(act, 4),
            "expected_win_pct": round(exp, 4),
            "luck_z": round(zl, 3) if zl is not None else None,
            "outside_noise_2sd": bool(zl is not None and abs(zl) > 2.0),
        })
    luck.sort(key=lambda r: -(r["luck_z"] or 0))
    totals = []
    for team, a in adv.items():
        gp = a["gp"]
        poss_pg = _f(a["poss"]) / gp if gp else None
        totals.append({
            "team": team, "poss_per_game": round(poss_pg, 2) if poss_pg else None,
            "ppp_for": round(a["off_rtg"] / 100, 4),
            "ppp_against": round(a["def_rtg"] / 100, 4),
            "modeled_pts_for": round(poss_pg * a["off_rtg"] / 100, 1) if poss_pg else None,
            "modeled_pts_against": round(poss_pg * a["def_rtg"] / 100, 1) if poss_pg else None,
            "actual_pts_for": trad[team]["pts"] if team in trad else None,
            "actual_pts_against": opp[team]["opp_pts"] if team in opp else None,
            "source_url": ts["advanced"]["source_url"],
        })
    # rest / B2B / 3-in-4 / travel for the 11/19 slate
    team_dates = defaultdict(list)
    for g in games.values():
        team_dates[g["away"]].append(g["date"])
        team_dates[g["home"]].append(g["date"])
    arena = None
    coord_path = ROOT / "data" / "app" / "arena_coordinates.json"
    if coord_path.exists():
        coords = json.loads(coord_path.read_text(encoding="utf-8"))
        if isinstance(coords, dict):
            arena = coords.get("arenas") or coords.get("teams") or coords
    rest_rows = []
    for away, home in SLATE_1119:
        for team, other, ha in ((away, home, "away"), (home, away, "home")):
            prevs = sorted(team_dates.get(team, []))
            last = prevs[-1] if prevs else None
            rest_days = None
            if last:
                rest_days = (date(2026, 11, 19) - date.fromisoformat(last)).days - 1
            window = [d for d in prevs
                      if (date(2026, 11, 19) - date.fromisoformat(d)).days <= 3]
            b2b = bool(last == "2026-11-18")
            three_in_4 = b2b and len(window) >= 2
            travel, travel_flag = None, "travel distance unverified (no sourced arena coordinate entry)"
            if isinstance(arena, dict):
                a_prev, a_next = arena.get(team), arena.get(other)
                if isinstance(a_prev, dict) and isinstance(a_next, dict):
                    try:
                        lat1, lon1 = _f(a_prev["lat"]), _f(a_prev["lon"])
                        lat2, lon2 = _f(a_next["lat"]), _f(a_next["lon"])
                        travel = round(haversine_km(lat1, lon1, lat2, lon2))
                        travel_flag = None
                    except Exception:
                        travel_flag = "travel distance unverified (coordinate fields missing)"
            rest_rows.append({
                "date": "2026-11-19", "team": team, "opponent": other, "site": ha,
                "prev_game_date": last, "rest_days": rest_days,
                "b2b": b2b, "three_in_4": three_in_4,
                "games_in_last_4_days": len(window),
                "travel_km": travel, "travel_flag": travel_flag,
            })
    # minutes redistribution (top-8 shares; OUT players removed, shares flagged)
    report_out = {}
    for r in injury["rows"]:
        if r["status"] == "Out" and r["team"]:
            abbr = FULL_TO_ABBR.get(r["team"])
            if abbr:
                report_out.setdefault(abbr, set()).add(name_key(r["player"]))
    minutes = []
    for away, home in SLATE_1119:
        for team in (away, home):
            secs = defaultdict(int)
            for g in games.values():
                for p in g["players"]:
                    if p["team"] != team:
                        continue
                    mm, ss = p["min"].split(":")
                    secs[name_key(p["player"])] += int(mm) * 60 + int(ss)
            if not secs:
                minutes.append({"team": team, "players": [],
                                "flag": "no captured minutes in 11/16-18 window"})
                continue
            order = sorted(secs.items(), key=lambda kv: -kv[1])[:8]
            total = sum(s for _, s in order)
            out_keys = report_out.get(team, set())
            rows = []
            for keyname, s in order:
                is_out = keyname in out_keys
                rows.append({
                    "player": " ".join(t.capitalize() if t not in ("iii", "ii", "jr", "sr") else t.upper()
                                       for t in keyname),
                    "minutes_3game_window": round(s / 60, 1),
                    "share": round(s / total, 4) if total else None,
                    "status_11_19": "OUT (official report)" if is_out else "not listed Out",
                    "redistributed_share_if_outs": 0.0 if is_out else None,
                })
            avail = [r for r in rows if r["status_11_19"] != "OUT (official report)"]
            avail_total = sum(r["minutes_3game_window"] for r in avail)
            for r in avail:
                r["redistributed_share_if_outs"] = (
                    round(r["minutes_3game_window"] / avail_total, 4) if avail_total else None)
            minutes.append({
                "team": team, "players": rows,
                "note": ("top-8 shares from captured 11/16-18 game books; OUT players "
                         "zeroed and their minutes redistributed pro rata among the "
                         "available top-8 — replacement-player shares are NOT officially "
                         "sourced and stay flagged/unverified"),
            })
    return {
        "checks": sorted(checks),
        "flags": flags,
        "home_court": hca,
        "luck": luck,
        "totals_poss_x_ppp": totals,
        "rest_travel_1119": rest_rows,
        "minutes_redistribution": minutes,
        "sources": {
            "traditional": ts["traditional"]["source_url"],
            "opponent": ts["opponent"]["source_url"],
            "advanced": ts["advanced"]["source_url"],
            "standings": ts["standings"]["source_url"],
        },
    }


# --------------------------------------------------------------------------
# O5 ledger-hash publication check
# --------------------------------------------------------------------------

def ledger_hash_check():
    """Verify data/app/ledger/ledger.jsonl: chain integrity, pre-tip
    publication (hash published before tip-off) and hash verification at
    settlement. Output rows leave nothing inferred."""
    import hashlib

    def sha_entry(obj):
        return hashlib.sha256(json.dumps(
            obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    path = ROOT / "data" / "app" / "ledger" / "ledger.jsonl"
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    problems, rows = [], []
    prev = "0" * 64
    published_hashes = {}
    for i, e in enumerate(entries):
        body = e.get("body") or {}
        expect = sha_entry({"prev": prev, "body": body})
        if expect != e.get("entry_hash"):
            problems.append(f"entry {i}: entry_hash does not recompute")
        if e.get("prev_hash") != prev:
            problems.append(f"entry {i}: prev_hash does not chain")
        if body.get("payload") is not None and body.get("payload_sha256"):
            if sha_entry(body["payload"]) != body["payload_sha256"]:
                problems.append(f"entry {i}: payload sha256 does not recompute")
        prev = e.get("entry_hash")
        b = body
        if b.get("state") == "PUBLISHED_PRE_TIP":
            pub = b.get("published_utc", "")
            tip = b.get("tip_et", "")
            pre_tip = None
            m = re.match(r"(\d{2}):(\d{2})\s*(AM|PM)", tip)
            dt = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})Z", pub)
            if m and dt:
                hh = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
                tip_dt = datetime.strptime(
                    f"{dt.group(1)} {hh:02d}:{m.group(2)}", "%Y-%m-%d %H:%M")
                # Nov 2026 tips are EST (UTC-5): tip UTC = ET + 5h (may roll a day)
                tip_utc = tip_dt.timestamp() + 5 * 3600
                pub_dt = datetime.strptime(
                    f"{dt.group(1)} {dt.group(2)}:{dt.group(3)}", "%Y-%m-%d %H:%M")
                pre_tip = pub_dt.timestamp() < tip_utc
                if not pre_tip:
                    problems.append(
                        f"entry {i} ({b.get('pick_id')}): published {pub} not before tip {tip}")
            published_hashes[b.get("payload_sha256")] = b.get("pick_id")
            rows.append({
                "pick_id": b.get("pick_id"), "state": b.get("state"),
                "published_utc": pub, "tip_et": tip,
                "payload_sha256": b.get("payload_sha256"),
                "hash_published_pre_tip": pre_tip,
            })
        elif b.get("state") == "SETTLED":
            ok = b.get("hash_verified_at_settlement") is True
            if not ok:
                problems.append(f"entry {i} ({b.get('pick_id')}): settled without hash verification")
            if b.get("payload_sha256") not in published_hashes:
                problems.append(
                    f"entry {i} ({b.get('pick_id')}): settled payload_sha256 has no "
                    f"pre-tip publication entry")
            rows.append({
                "pick_id": b.get("pick_id"), "state": "SETTLED",
                "settled_utc": b.get("settled_utc"),
                "payload_sha256": b.get("payload_sha256"),
                "hash_verified_at_settlement": ok,
                "settlement_stamp": b.get("settlement_stamp"),
            })
    return {
        "ledger": "data/app/ledger/ledger.jsonl",
        "entries": len(entries),
        "chain_intact": not any("chain" in p or "recompute" in p for p in problems),
        "problems": problems,
        "rows": rows,
    }


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def main():
    VERIFIED.mkdir(parents=True, exist_ok=True)
    games = load_games()

    quarters = []
    for key, g in sorted(games.items()):
        quarters.append({
            "game_id": key, "date": g["date"], "gid": g["gid"],
            "away": g["away"], "home": g["home"], "final": g["final"],
            "away_quarters": g["quarters"].get(g["away"]),
            "home_quarters": g["quarters"].get(g["home"]),
            "flags": g["quarter_flags"],
            "source_url": g["source_url"],
            "retrieved_utc": g["retrieved_utc"],
        })
    (VERIFIED / "quarters_2026-11-16_18.json").write_text(json.dumps({
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "rule": "quarter vector accepted only when its sum equals the printed final; "
                "missing/conflicting vectors left blank + flagged, never inferred",
        "games": quarters,
    }, indent=2), encoding="utf-8")

    logs = []
    have_keys = set()
    for key, g in sorted(games.items()):
        for p in g["players"]:
            logs.append({
                "date": g["date"], "game_id": key, "team": p["team"],
                "opponent": g["home"] if p["team"] == g["away"] else g["away"],
                "player": p["player"], "min": p["min"],
                "pts": p["pts"], "reb": p["reb"], "ast": p["ast"],
                "source_url": g["source_url"],
            })
            have_keys.add((name_key(p["player"]), p["team"]))
    for name, team in INJURY_REPORT_PLAYERS:
        if (name_key(name), team) not in have_keys:
            logs.append({
                "date": "2026-11-16..18", "game_id": None, "team": team,
                "opponent": None, "player": name, "min": None, "pts": None,
                "reb": None, "ast": None,
                "flag": "no captured game in 11/16-11/18 window (DNP/inactive/out); "
                        "values left blank, not inferred",
                "source_url": "https://statsdmz.nba.com/pdfs/20261116/"
                              "20261116_PORMIN.pdf (and 11/17 pair) — game-book window",
            })
    (VERIFIED / "player_game_logs.json").write_text(json.dumps({
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "scope": "MIN/PTS/REB/AST/Opp per player per game from official game books; "
                 "every player on the 2026-11-19 8PM injury report covered or flagged",
        "rows": logs,
    }, indent=2), encoding="utf-8")

    injury = load_injury_round()
    (VERIFIED / "injury_report_2026-11-19.json").write_text(json.dumps({
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        **injury,
    }, indent=2), encoding="utf-8")

    recut_out = recut(games, injury)
    (VERIFIED / "team_stats_recut_2026-11-19.json").write_text(json.dumps({
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        **recut_out,
    }, indent=2), encoding="utf-8")

    ledger = ledger_hash_check()
    (VERIFIED / "ledger_hash_check_2026-11-19.json").write_text(json.dumps({
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "rule": "hash published pre-tip and verified at settlement; chain integrity "
                "recomputed from the file itself, nothing inferred",
        **ledger,
    }, indent=2), encoding="utf-8")

    n_qflags = sum(len(g["quarter_flags"]) for g in games.values())
    n_pflags = sum(len(g["player_flags"]) for g in games.values())
    print(f"games: {len(games)}  player-log rows: {len(logs)}  "
          f"injury rows: {len(injury['rows'])}  quarter flags: {n_qflags}  "
          f"player flags: {n_pflags}  recut flags: {len(recut_out['flags'])}")
    for f in recut_out["flags"]:
        print("  recut flag:", f)


if __name__ == "__main__":
    main()
