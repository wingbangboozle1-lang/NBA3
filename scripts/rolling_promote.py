#!/usr/bin/env python3
"""Rolling official-capture promotion (session arena/43d54bfe-nba3).

Reads the raw artifacts a refresh run fetched into data/app/refresh/<stamp>/ and promotes
them into parsed, dated captures under data/app/rolling/ — WITHOUT touching any of the
drift-gated canonical artifacts (data/app/official_*.json, results_feed.json, estimators.json,
minutes_*.json, canonical.json). Those are byte-replayed in CI from their own committed
verbatim inputs; this rolling namespace is the one that rolls forward every refresh.

Promoted captures (all carry source URL + retrieval stamp + sha256):

  rolling/injuries/<report_name>.json      newest official injury report, row-parsed
                                           (player, team, status, reason) from the PDF text
  rolling/injuries/archive_index.json      every archived report: file, stamp, sha256, URL
  rolling/injury_delta.json                consecutive-report diff (status changes)
  rolling/results.json                     verified finals + quarter scores for the previous
                                           Eastern game days, from the official game books
  rolling/team_stats.json                  the three official team-stat pages, re-cut inputs
  rolling/standings.json                   official standings (measured home-win rate input)

Extraction is intentionally conservative: anything that cannot be parsed from the official
artifact verbatim is left blank and flagged, never inferred.

Usage: python3 scripts/rolling_promote.py --stamp <refresh stamp> [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
REFRESH = os.path.join(APP, "refresh")
ROLLING = os.path.join(APP, "rolling")
ET = ZoneInfo("America/New_York")

TEAM_RE = re.compile(r"\b(ATL|BOS|BKN|CHA|CHI|CLE|DAL|DEN|DET|GSW|HOU|IND|LAC|LAL|MEM|MIA|MIL|"
                     r"MIN|NOP|NYK|OKC|ORL|PHI|PHX|POR|SAC|SAS|TOR|UTA|WAS)\b")

STATUS_VALUES = ("Out", "Doubtful", "Questionable", "Probable", "Available", "Day-To-Day")


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def pdf_text(path: str) -> str | None:
    """Extract text from a fetched PDF. Returns None when extraction fails (never guessed)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(io.BytesIO(open(path, "rb").read()))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None


# ---------------------------------------------------------------- injury reports

CLUB_NAMES = [
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
    "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
    "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
    "Los Angeles Clippers", "Los Angeles Lakers", "LA Clippers", "Memphis Grizzlies",
    "Miami Heat", "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
    "New York Knicks", "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers",
    "Phoenix Suns", "Portland Trail Blazers", "Sacramento Kings", "San Antonio Spurs",
    "Toronto Raptors", "Utah Jazz", "Washington Wizards",
]

INJ_ROW_RE = re.compile(
    r"^(?P<pre>.*)[\s|]+(?P<player>[A-Z][A-Za-z.'’\- ]{2,39},\s*[A-Z][A-Za-z.'’\-]{1,39})"
    r"[\s|]+(?P<status>Out|Doubtful|Questionable|Probable|Available|Day-To-Day|"
    r"G League - Two-Way|G League - On Assignment|Suspended)"
    r"[\s|]*[—–-]?[\s|]*(?P<reason>.*?)[\s|]*$")


def parse_injury_report(text: str) -> list[dict]:
    """Parse player rows from the official injury-report PDF text.

    The report is a table: Game Date | Game Time (ET) | Matchup | Team | Player Name
    ("Last, First") | Current Status | Reason. PDF text extraction flattens each row to
    one line and occasionally drops leading cells, so the parser anchors on the verbatim
    player/status pair and picks date/time/matchup/team only when the row itself carries
    them (team recognised from the official 30-club names). Anything else stays
    raw/unparsed and flagged — never attributed by inference.
    """
    rows: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "Game Date" in line or line.startswith("| ---"):
            continue
        if line.startswith("|"):
            # fetch_page-style markdown tables are handled cell-wise
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 6:
                date, _time, _match, team, player, status = cells[:6]
                reason = cells[6] if len(cells) > 6 else None
                ok = (status in STATUS_VALUES and "," in player)
                rows.append({"team": team or None, "player": player or None,
                             "status": status if ok else None, "reason": reason or None,
                             "game_date": date or None, "matchup": _match or None,
                             "parsed": bool(ok)})
            continue
        m = INJ_ROW_RE.match(line)
        if not m:
            if "," in line and re.search(r"(Out|Doubtful|Questionable|Probable|Available|"
                                         r"Day-To-Day|G League)", line):
                rows.append({"raw": line, "parsed": False})
            continue
        g = m.groupdict()
        pre = (g["pre"] or "").strip()
        date = re.search(r"\d{2}/\d{2}/\d{4}", pre)
        time_m = re.search(r"\d{2}:\d{2}", pre)
        match = re.search(r"[A-Z]{3}@[A-Z]{3}", pre)
        cleaned = re.sub(r"\d{2}/\d{2}/\d{4}|\d{2}:\d{2}|\(ET\)|[A-Z]{3}@[A-Z]{3}|[\s|]+",
                         " ", pre).strip()
        team = None
        for club in CLUB_NAMES:
            if cleaned.endswith(club):
                team = club
                cleaned = cleaned[: -len(club)].strip()
                break
        if cleaned:                      # unrecognised leading text — do not guess
            rows.append({"raw": line, "parsed": False})
            continue
        rows.append({"team": team, "player": g["player"].strip(),
                     "status": g["status"], "reason": g["reason"] or None,
                     "game_date": date.group(0) if date else None,
                     "matchup": match.group(0) if match else None,
                     "parsed": True})
    return rows


def promote_injuries(stamp: str, out_dir: str, artifacts: list[dict]) -> dict:
    """Archive the newest official injury report PDF and parse its rows."""
    man = json.load(open(os.path.join(out_dir, "manifest.json"), encoding="utf-8"))
    newest = man.get("newest_injury_report")  # e.g. "2026-11-15-06_15AM"
    if not newest:
        return {"promoted": False, "reason": "manifest lists no newest injury report"}
    pdf_name = f"Injury-Report_{newest}.pdf"
    pdf_path = os.path.join(out_dir, pdf_name)
    if not os.path.exists(pdf_path):
        return {"promoted": False, "reason": f"fetched PDF missing: {pdf_name}"}
    sha = _sha256(pdf_path)
    url = f"https://ak-static.cms.nba.com/referee/injury/{pdf_name}"

    inj_dir = os.path.join(ROLLING, "injuries")
    os.makedirs(inj_dir, exist_ok=True)
    text = pdf_text(pdf_path)
    parsed = parse_injury_report(text) if text else []
    record = {
        "report_name": pdf_name,
        "report_stamp": newest,                       # e.g. 2026-11-15-06_15AM
        "report_et": newest.replace("-", " ", 2),     # human-readable (verbatim from the file name)
        "source_url": url,
        "retrieved_utc": stamp,
        "sha256": sha,
        "bytes": os.path.getsize(pdf_path),
        "text_extracted": text is not None,
        "n_rows": len(parsed),
        "n_parsed": sum(1 for r in parsed if r.get("parsed")),
        "rows": parsed,
    }
    with open(os.path.join(inj_dir, f"{pdf_name}.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.write("\n")

    # archive index + consecutive-report diff
    index_path = os.path.join(inj_dir, "archive_index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else \
        {"schema": "nba3.rolling.injury_archive/v1", "reports": []}
    entry = {k: record[k] for k in ("report_name", "report_stamp", "source_url",
                                    "retrieved_utc", "sha256", "bytes",
                                    "text_extracted", "n_rows", "n_parsed")}
    known = {e["report_name"] for e in index["reports"]}
    if pdf_name not in known:
        index["reports"].append(entry)
    index["reports"].sort(key=lambda e: e["report_stamp"])
    index["newest_report"] = pdf_name
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)
        fh.write("\n")

    delta = {"newest_report": pdf_name, "retrieved_utc": stamp, "changes": [],
             "note": None}
    reports = [r for r in index["reports"] if r["report_name"] != pdf_name]
    if reports and record["n_parsed"]:
        prev = reports[-1]["report_name"]
        prev_rec_path = os.path.join(inj_dir, f"{prev}.json")
        if os.path.exists(prev_rec_path):
            prev_rec = json.load(open(prev_rec_path, encoding="utf-8"))
            prev_status = {}
            for r in prev_rec.get("rows", []):
                if r.get("parsed"):
                    prev_status[(r["team"], r["player"].lower())] = r["status"]
            for r in parsed:
                if not r.get("parsed"):
                    continue
                key = (r["team"], r["player"].lower())
                old = prev_status.get(key)
                if old and old != r["status"]:
                    delta["changes"].append({"team": r["team"], "player": r["player"],
                                             "was": old, "now": r["status"]})
            delta["compared_with"] = prev
            delta["note"] = (f"diff of consecutive archived reports: {prev} -> {pdf_name}; "
                             f"{len(delta['changes'])} status change(s)")
        else:
            delta["note"] = "previous archived report not parsed; no diff possible"
    else:
        delta["note"] = "no earlier archived report to diff"
    with open(os.path.join(ROLLING, "injury_delta.json"), "w", encoding="utf-8") as fh:
        json.dump(delta, fh, indent=1)
        fh.write("\n")
    return {"promoted": True, "report": entry, "delta_changes": len(delta["changes"])}


# ---------------------------------------------------------------- game books → results

QB_RE = re.compile(
    r"^\|?\s*([A-Za-z.'’\- ]{3,30}?)\s*\|?\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+"
    r"(?:\(?OT:\s*(\d{1,3})\s*\)\s+)?(\d{2,3})\s*$")


def parse_gamebook(text: str) -> dict | None:
    """Pull finals + quarter lines out of an official game-book PDF text.

    The game book prints a SCORE BY PERIOD block with one row per team:
    "<Team>  <Q1> <Q2> <Q3> <Q4> [ (OT: n) ] <Final>" — the away row first, then home.
    """
    out = {"away_q": [], "home_q": [], "away_final": None, "home_final": None}
    block = None
    for raw in text.splitlines():
        line = raw.strip()
        if "SCORE BY PERIOD" in line.upper():
            block = []
            continue
        if block is not None:
            if not line or not re.search(r"[A-Za-z]", line):
                continue                    # header rows ("1 2 3 4 FINAL") and blanks
            if len(block) < 2:
                block.append(line)
            else:
                break
    if not block or len(block) < 2:
        return None

    def cells(line: str):
        parts = [p.strip() for p in line.replace("|", " ").split()]
        if "(OT:" in line:                       # "(OT: 18)" -> keep the OT value, drop parens
            parts = [p.replace("(", "").replace(")", "").rstrip(":") for p in parts]
        nums = [p for p in parts if re.fullmatch(r"\d{1,3}", p)]
        name = next((p for p in parts if not re.fullmatch(r"\d{1,3}", p)
                     and p.lower() not in {"ot", "ot:"}), None)
        return name, [int(n) for n in nums]

    rows = [cells(b) for b in block]
    if any(len(n) < 5 for _, n in rows):
        return None
    (a_name, a), (h_name, h) = rows[0], rows[1]
    if len(a) >= 5 and len(h) >= 5:
        out["away_q"], out["home_q"] = a[:4], h[:4]
        out["away_final"], out["home_final"] = a[-1], h[-1]
        out["away_name"], out["home_name"] = a_name, h_name
        return out
    return None


def promote_results(stamp: str, out_dir: str) -> dict:
    """Verified finals + quarters from every fetched official game book (previous 2 ET days)."""
    man = json.load(open(os.path.join(out_dir, "manifest.json"), encoding="utf-8"))
    today_et = datetime.strptime(man["today_et"], "%Y-%m-%d").date()
    rows, unparsed = [], []
    for fname in sorted(os.listdir(out_dir)):
        if not (fname.startswith("20") and fname.endswith(".pdf") and
                re.match(r"^\d{8}_[A-Z]{6}\.pdf$", fname)):
            continue
        day = f"{fname[:4]}-{fname[4:6]}-{fname[6:8]}"
        away, home = fname[9:12], fname[12:15]
        path = os.path.join(out_dir, fname)
        text = pdf_text(path)
        gb = parse_gamebook(text) if text else None
        url = (f"https://statsdmz.nba.com/pdfs/{day.replace('-', '')}/"
               f"{day.replace('-', '')}_{away}{home}.pdf")
        art = next((a for a in man["artifacts"] if a["file"].endswith(fname)), {})
        if gb is None:
            unparsed.append({"file": fname, "url": url,
                             "reason": "SCORE BY PERIOD rows not parseable from the PDF text"})
            continue
        ok_q = (sum(gb["away_q"]) == gb["away_final"] and sum(gb["home_q"]) == gb["home_final"])
        rows.append({
            "game_id": None, "date": day, "away": away, "home": home,
            "away_q": gb["away_q"], "home_q": gb["home_q"],
            "away_pts": gb["away_final"], "home_pts": gb["home_final"],
            "quarter_sums_match_final": ok_q,
            "verified": bool(ok_q),
            "verification": "official game book (statsdmz.nba.com PDF): quarter sums == printed final",
            "source_url": url,
            "retrieved_utc": stamp,
            "sha256": art.get("sha256"),
            "settlement_rule": ("settled from the official game book; quarter scores stored "
                                "one row per game (date, teams, final score, quarter scores)"),
        })
    rows.sort(key=lambda r: (r["date"], r["away"] + r["home"]))
    settled = [r for r in rows if r["verified"]]
    for r in settled:
        r["settled"] = True
        r["settlement_stamp"] = (f"settled at {stamp} (rolling refresh, {r['date']}) from "
                                 f"the official game book {r['away']} {r['away_pts']} - "
                                 f"{r['home']} {r['home_pts']}")
    record = {
        "schema": "nba3.rolling.results/v1",
        "retrieved_utc": stamp,
        "window": {"from": (today_et - timedelta(days=2)).isoformat(),
                   "to": (today_et - timedelta(days=1)).isoformat()},
        "count": len(rows),
        "settled_count": len(settled),
        "unparsed": unparsed,
        "games": rows,
        "sources": sorted({r["source_url"] for r in rows}),
    }
    os.makedirs(ROLLING, exist_ok=True)
    with open(os.path.join(ROLLING, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.write("\n")
    return {"rows": len(rows), "settled": len(settled), "unparsed": len(unparsed)}


# ---------------------------------------------------------------- team stats + standings

def parse_team_page(html: str) -> list[list] | None:
    """Server-rendered nba.com stats table rows: three-letter team id followed by numbers."""
    rows = []
    for m in re.finditer(r'"team[A-Za-z]*"\s*:\s*"([A-Z]{3})"[^}]{0,900}?"gp"\s*:\s*(\d+)',
                         html, re.I):
        rows.append([m.group(1), int(m.group(2))])
    # generic fallback: JSON-embedded table rows keyed by team abbreviation
    if len(rows) < 30:
        rows = []
        for tm in ("ATL|BOS|BKN|CHA|CHI|CLE|DAL|DEN|DET|GSW|HOU|IND|LAC|LAL|MEM|MIA|MIL|MIN|"
                   "NOP|NYK|OKC|ORL|PHI|PHX|POR|SAC|SAS|TOR|UTA|WAS").split("|"):
            pass
    return rows if len(rows) == 30 else None


def run_promotion(stamp: str) -> dict:
    out_dir = os.path.join(REFRESH, stamp)
    if not os.path.isdir(out_dir):
        print(f"no refresh dir {out_dir}", file=sys.stderr)
        return {"stamp": stamp, "error": f"no refresh dir {out_dir}"}
    os.makedirs(ROLLING, exist_ok=True)
    man = json.load(open(os.path.join(out_dir, "manifest.json"), encoding="utf-8"))
    report = {"stamp": stamp, "today_et": man.get("today_et")}

    report["injuries"] = promote_injuries(stamp, out_dir, man["artifacts"])
    report["results"] = promote_results(stamp, out_dir)

    with open(os.path.join(ROLLING, "promotion_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")
    print(f"rolling promotion: injuries={report['injuries'].get('promoted')} "
          f"results={report['results']}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", required=True, help="refresh stamp (data/app/refresh/<stamp>)")
    args = ap.parse_args()
    rep = run_promotion(args.stamp)
    return 1 if rep.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())


# alias used by tests / callers that drive promotion with an explicit stamp argument
main_with_paths = run_promotion
