#!/usr/bin/env python3
"""Fail-closed validation of one scheduled NBA source capture.

This gate is deliberately separate from freshness_gates.py: that command replays the
last published snapshot in data/live, while this module validates the *new* capture under
 data/app/refresh/<stamp> before any published slate or model output is changed.

The raw-source checks are reproducible from the manifest and files. The standings and
team-stat checks require parser outputs tied to the exact raw-source hashes. A fetched page
shell is not a model input. Until a parser emits those current-run snapshots, this gate
refuses the rebuild rather than silently reusing the previous day's values.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import rolling_promote

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "data" / "app"
REFRESH = APP / "refresh"

INJ_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJ_CDN = "https://ak-static.cms.nba.com/referee/injury/"
GAMES = "https://www.nba.com/games?date="
STANDINGS = "https://www.nba.com/standings"
TEAM_PAGES = {
    "traditional": "https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season",
    "opponent": "https://www.nba.com/stats/teams/opponent?Season=2026-27&SeasonType=Regular%20Season",
    "advanced": "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
}
TEAM_CODES = rolling_promote.TEAM_CODES
REPORT_RE = re.compile(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf")


def _parse_stamp(value: str) -> datetime | None:
    """Parse the scheduled job's filename stamp and ISO retrieval stamps."""
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%dT%H-%M-%SZ", "%Y-%m-%dT%H-%MZ",
                "%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _is_official_https(url: str) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    return parsed.scheme == "https" and (host == "nba.com" or host.endswith(".nba.com"))


def _report_clock(parts: tuple[str, str, str, str]) -> datetime:
    day, hh, mm, ap = parts
    hour_12, minute = int(hh), int(mm)
    if not 1 <= hour_12 <= 12 or not 0 <= minute <= 59:
        raise ValueError("invalid 12-hour report time")
    hour = hour_12 % 12 + (12 if ap == "PM" else 0)
    return datetime.strptime(f"{day} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")


def _manifest_report_name(value: str) -> str | None:
    """Convert the existing manifest value (YYYY-MM-DD-HH-MMAM) to the PDF basename."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})(AM|PM)", value)
    if not match:
        return None
    day, hh, mm, ap = match.groups()
    return f"Injury-Report_{day}_{hh}_{mm}{ap}.pdf"


def _numeric(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _current_structured_snapshot(path: Path, *, stamp: str, source_url: str,
                                 source_sha256: str | dict[str, str], kind: str) -> tuple[bool, str]:
    """Check parser output is tied to this run and is a usable 30-team input.

    Contract:
      * standings: {retrieved_utc, source_url, source_sha256,
                    rows:[{team, w, l}, ...]}
      * team stats: {retrieved_utc, pages:{traditional/opponent/advanced: {
          source_url, source_sha256, columns:[...], rows:[[TEAM, ...], ...]}}

    Parsed rows must carry numeric values and the columns required by the downstream
    models. A fetched page shell or a parser note containing just its URL is not an input.
    """
    if not path.is_file():
        return False, f"missing parsed current-run {kind} input: {path.name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot read parsed {kind} input: {exc}"
    if not isinstance(payload, dict):
        return False, f"parsed {kind} input is not a JSON object"
    if payload.get("retrieved_utc") != stamp:
        return False, f"{kind} parser stamp {payload.get('retrieved_utc')!r} does not equal {stamp!r}"

    if kind == "standings":
        if payload.get("source_url") != source_url or payload.get("source_sha256") != source_sha256:
            return False, "standings parser provenance does not match this run's official page hash"
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return False, "standings parser rows are missing or not a list"
        teams = {row.get("team") for row in rows
                 if isinstance(row, dict) and isinstance(row.get("team"), str)}
        if len(rows) != 30 or teams != TEAM_CODES:
            return False, f"standings parser has {len(rows)} rows / {len(teams)} unique known teams; expected 30"
        for row in rows:
            if not isinstance(row, dict) or not _numeric(row.get("w")) or not _numeric(row.get("l")):
                return False, "standings parser has a row without numeric official W/L values"
            if float(row["w"]) < 0 or float(row["l"]) < 0:
                return False, "standings parser has a negative official W/L value"
        return True, "30 numeric official standings rows are tied to this capture's URL and SHA-256"

    pages = payload.get("pages")
    if not isinstance(pages, dict):
        return False, "team-stat parser has no pages object"
    required_columns = {
        "traditional": {"team", "gp", "w", "l", "pts"},
        "opponent": {"team", "gp", "w", "l", "opp_pts"},
        "advanced": {"team", "gp", "w", "l", "off_rtg", "def_rtg", "net_rtg", "pace", "poss"},
    }
    for name, url in TEAM_PAGES.items():
        page = pages.get(name)
        if not isinstance(page, dict):
            return False, f"team-stat parser missing {name} page"
        if page.get("source_url") != url:
            return False, f"team-stat parser {name} URL does not match the official URL"
        if page.get("source_sha256") != source_sha256.get(name):
            return False, f"team-stat parser {name} hash does not match this run's official page"
        columns = page.get("columns")
        if (not isinstance(columns, list) or not columns
                or any(not isinstance(column, str) or not column.strip() for column in columns)):
            return False, f"team-stat parser {name} has invalid column headings"
        normalized_columns = [column.strip().lower() for column in columns]
        if len(set(normalized_columns)) != len(normalized_columns):
            return False, f"team-stat parser {name} has duplicate column headings"
        missing_columns = required_columns[name] - set(normalized_columns)
        if missing_columns:
            return False, f"team-stat parser {name} lacks required columns: {sorted(missing_columns)}"
        rows = page.get("rows")
        if not isinstance(rows, list):
            return False, f"team-stat parser {name} rows are missing or not a list"
        teams = {row[0] for row in rows
                 if isinstance(row, list) and row and isinstance(row[0], str)}
        if len(rows) != 30 or teams != TEAM_CODES:
            return False, f"team-stat parser {name} has {len(rows)} rows / {len(teams)} known teams; expected 30"
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns) or row[0] not in TEAM_CODES:
                return False, f"team-stat parser {name} has a malformed row or column count"
            if any(not _numeric(value) for value in row[1:]):
                return False, f"team-stat parser {name} has a blank or non-numeric statistic"
    return True, "traditional, opponent and advanced inputs each contain 30 numeric teams tied to this run's hashes"


def validate(stamp: str, *, root: Path | None = None, app: Path | None = None) -> dict:
    """Validate a fetched refresh directory without changing published files."""
    root = Path(root or ROOT).resolve()
    app = Path(app or (root / "data" / "app")).resolve()
    refresh_root = (app / "refresh").resolve()
    report = {"schema": "nba3.refresh-preflight/v1", "stamp": stamp,
              "evaluated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
              "gates": [], "pass": False}

    def add(gate_id: str, passed: bool, detail: str) -> None:
        report["gates"].append({"id": gate_id, "passed": bool(passed), "detail": detail})

    stamp_time = _parse_stamp(stamp)
    if stamp_time is None or not isinstance(stamp, str):
        add("P1_manifest", False, "requested run stamp is invalid")
        for gate_id in ("P2_integrity", "P3_sources", "P4_injury_current", "P5_slate", "P6_standings", "P7_team_stats"):
            add(gate_id, False, "cannot validate with an invalid requested run stamp")
        return report
    out_dir = (refresh_root / stamp).resolve()
    if not _inside(out_dir, refresh_root):
        add("P1_manifest", False, "requested run directory escapes the refresh root")
        for gate_id in ("P2_integrity", "P3_sources", "P4_injury_current", "P5_slate", "P6_standings", "P7_team_stats"):
            add(gate_id, False, "cannot validate an unsafe run directory")
        return report
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        add("P1_manifest", False, f"missing refresh manifest: {manifest_path}")
        for gate_id in ("P2_integrity", "P3_sources", "P4_injury_current", "P5_slate", "P6_standings", "P7_team_stats"):
            add(gate_id, False, "cannot validate without the manifest")
        return report

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add("P1_manifest", False, f"invalid refresh manifest: {exc}")
        for gate_id in ("P2_integrity", "P3_sources", "P4_injury_current", "P5_slate", "P6_standings", "P7_team_stats"):
            add(gate_id, False, "cannot validate without a valid manifest")
        return report
    if not isinstance(manifest, dict):
        add("P1_manifest", False, "refresh manifest root is not a JSON object")
        for gate_id in ("P2_integrity", "P3_sources", "P4_injury_current", "P5_slate", "P6_standings", "P7_team_stats"):
            add(gate_id, False, "cannot validate without a JSON object manifest")
        return report

    manifest_time = _parse_stamp(manifest.get("stamp", ""))
    started_time = _parse_stamp(manifest.get("started_utc", ""))
    finished_time = _parse_stamp(manifest.get("finished_utc", ""))
    today_raw = manifest.get("today_et", "")
    try:
        today = date.fromisoformat(today_raw)
    except (TypeError, ValueError):
        today = None
    manifest_ok = (manifest.get("stamp") == stamp and manifest_time == stamp_time
                   and started_time is not None and finished_time is not None
                   and started_time <= finished_time and today is not None)
    add("P1_manifest", manifest_ok,
        "run stamp, UTC fetch interval and Eastern game date are valid" if manifest_ok else
        "manifest stamp, fetch interval or Eastern date is missing, invalid, or inconsistent")
    if not manifest_ok:
        for gate_id in ("P2_integrity", "P3_sources", "P4_injury_current", "P5_slate", "P6_standings", "P7_team_stats"):
            add(gate_id, False, "manifest timestamp or Eastern date is invalid")
        return report

    artifacts = manifest.get("artifacts", [])
    integrity_errors: list[str] = []
    if not isinstance(artifacts, list):
        integrity_errors.append("manifest artifacts is not a list")
        artifacts = []
    by_url: dict[str, dict] = {}
    resolved: dict[str, Path] = {}
    seen_urls: set[str] = set()
    seen_paths: set[Path] = set()
    for art in artifacts:
        if not isinstance(art, dict):
            integrity_errors.append("artifact entry is not an object")
            continue
        url = art.get("url", "")
        if not _is_official_https(url):
            integrity_errors.append(f"non-official or non-https URL: {url or '<blank>'}")
        if isinstance(url, str) and url in seen_urls:
            integrity_errors.append(f"duplicate artifact URL: {url}")
        if isinstance(url, str):
            seen_urls.add(url)
        retrieved = _parse_stamp(art.get("retrieved_utc", ""))
        if (art.get("run_stamp") != stamp or retrieved is None
                or retrieved < started_time or retrieved > finished_time):
            integrity_errors.append(f"{url or art.get('file', '?')}: retrieval time is outside this run")
        rel = art.get("file", "")
        try:
            path = (root / rel).resolve() if isinstance(rel, str) else root / "__invalid__"
        except (OSError, RuntimeError, ValueError):
            integrity_errors.append(f"{url or '?'}: unsafe or invalid relative file path")
            continue
        if not rel or not _inside(path, root):
            integrity_errors.append(f"{url or '?'}: unsafe or missing relative file path")
            continue
        if path in seen_paths:
            integrity_errors.append(f"duplicate artifact file path: {rel}")
        seen_paths.add(path)
        if not path.is_file():
            integrity_errors.append(f"{url or rel}: captured file is missing")
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            integrity_errors.append(f"{url or rel}: cannot read captured file: {exc}")
            continue
        if not data:
            integrity_errors.append(f"{url or rel}: captured file is empty")
        if art.get("bytes") != len(data):
            integrity_errors.append(f"{url or rel}: byte count does not match the file")
        digest = hashlib.sha256(data).hexdigest()
        if art.get("sha256") != digest:
            integrity_errors.append(f"{url or rel}: SHA-256 does not match the file")
        if isinstance(url, str) and url:
            by_url[url] = art
            resolved[url] = path
    add("P2_integrity", not integrity_errors,
        f"{len(artifacts)} captured artifact(s) checked by official URL, run stamp, UTC retrieval interval, bytes and SHA-256"
        + ("; " + "; ".join(integrity_errors[:5]) if integrity_errors else ""))

    expected_urls = {"injury index": INJ_INDEX, "standings": STANDINGS,
                     **{f"team stats {name}": url for name, url in TEAM_PAGES.items()}}
    for offset in range(4):
        expected_day = (today + timedelta(days=offset)).isoformat()
        expected_urls[f"schedule {expected_day}"] = GAMES + expected_day
    missing_sources = [label for label, url in expected_urls.items() if url not in by_url]
    manifest_errors = manifest.get("errors", [])
    if not isinstance(manifest_errors, list):
        manifest_errors = []
        missing_sources.append("manifest errors field is not a list")
    required_errors = [e for e in manifest_errors
                       if isinstance(e, dict) and e.get("required") is True]
    if required_errors:
        missing_sources.extend(f"required fetch failed: {e.get('label') or e.get('url')}"
                               for e in required_errors)
    add("P3_sources", not missing_sources,
        "required official injury index, standings, three team-stat pages and all four rolling schedule dates are present"
        if not missing_sources else "missing or failed: " + "; ".join(missing_sources[:12]))

    # Exact official-index newest-report check; filenames are ordered by real 12-hour time.
    inj_ok = False
    inj_detail = "official injury index or newest PDF is missing"
    index_path = resolved.get(INJ_INDEX)
    newest_value = manifest.get("newest_injury_report", "")
    expected_pdf = _manifest_report_name(newest_value)
    if index_path and expected_pdf:
        index_text = index_path.read_text(encoding="utf-8", errors="replace")
        reports = set(REPORT_RE.findall(index_text))
        try:
            newest_parts = max(reports, key=_report_clock) if reports else None
        except ValueError:
            newest_parts = None
            inj_detail = "official injury index contains a filename with an invalid date or clock time"
        newest_name = (f"Injury-Report_{newest_parts[0]}_{newest_parts[1]}_"
                       f"{newest_parts[2]}{newest_parts[3]}.pdf") if newest_parts else None
        pdf_url = INJ_CDN + expected_pdf
        pdf_path = resolved.get(pdf_url)
        pdf_magic_ok = bool(pdf_path and pdf_path.read_bytes().startswith(b"%PDF-"))
        inj_ok = bool(newest_name == expected_pdf and pdf_path and pdf_magic_ok)
        if newest_parts is not None:
            inj_detail = (f"index newest={newest_name or 'unreadable'}, manifest={expected_pdf}, "
                          f"newest PDF captured with %PDF signature={pdf_magic_ok}")
    add("P4_injury_current", inj_ok, inj_detail)

    # Parse the selected-date gameCardFeed and cross-check each day's card count against
    # NBA.com's own season calendar. The staged file must be exactly these rows; a lone
    # game link or a complete-looking URL set is not enough to call a slate complete.
    schedule_pages: dict[str, str] = {}
    for offset in range(4):
        day = (today + timedelta(days=offset)).isoformat()
        path = resolved.get(GAMES + day)
        if path is not None:
            try:
                schedule_pages[day] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    slate_result = rolling_promote.build_rolling_slate(
        schedule_pages, today, stamp=stamp, games_url_prefix=GAMES, days=4)
    slate = slate_result["slate"]
    preview = (slate if slate is not None else {
        "source_url": GAMES + today.isoformat(),
        "window": {"from": today.isoformat(),
                   "to": (today + timedelta(days=3)).isoformat()},
        "count": len(slate_result["games"]),
        "daily_counts": slate_result["daily_counts"],
        "games": slate_result["games"],
    })
    staged_path = out_dir / "promoted_slate.json"
    staged_ok = False
    staged_detail = "staged rolling slate is missing"
    if slate is not None and staged_path.is_file():
        try:
            staged_payload = json.loads(staged_path.read_text(encoding="utf-8"))
            staged_ok, staged_detail = rolling_promote.staged_slate_matches(
                staged_payload, slate, stamp)
        except (OSError, json.JSONDecodeError) as exc:
            staged_detail = f"staged rolling slate is unreadable: {exc}"
    slate_ok = slate is not None and not slate_result["errors"] and staged_ok
    count_detail = ", ".join(
        f"{item['date']}={item['parsed']}/{item['expected']}"
        if item["complete"] else f"{item['date']}=incomplete"
        for item in slate_result["daily_counts"])
    slate_issues = slate_result["errors"][:5]
    if not staged_ok:
        slate_issues.append(staged_detail)
    detail = f"{len(slate_result['games'])} game(s); daily parsed/official counts: {count_detail}"
    if slate_issues:
        detail += "; " + "; ".join(slate_issues)
    add("P5_slate", slate_ok, detail)
    report["slate_preview"] = preview

    standings_art = by_url.get(STANDINGS)
    standings_ok, standings_detail = _current_structured_snapshot(
        out_dir / "derived" / "official_standings.json", stamp=stamp, source_url=STANDINGS,
        source_sha256=standings_art.get("sha256", "") if standings_art else "", kind="standings")
    add("P6_standings", bool(standings_art and standings_ok), standings_detail)

    stats_hashes = {name: by_url.get(url, {}).get("sha256", "") for name, url in TEAM_PAGES.items()}
    stats_ok, stats_detail = _current_structured_snapshot(
        out_dir / "derived" / "official_team_stats.json", stamp=stamp, source_url="",
        source_sha256=stats_hashes, kind="team stats")
    add("P7_team_stats", all(stats_hashes.values()) and stats_ok, stats_detail)

    report["pass"] = all(g["passed"] for g in report["gates"])
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    if (Path(args.stamp).name != args.stamp or _parse_stamp(args.stamp) is None):
        parser.error("--stamp must be a valid timestamp and a single safe path component")
    result = validate(args.stamp)
    output = Path(args.json_out) if args.json_out else REFRESH / args.stamp / "provenance_gates.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    for gate in result["gates"]:
        print(f"{'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['detail']}")
    print(f"REFRESH PREFLIGHT {'PASS' if result['pass'] else 'FAIL — rebuild refused'}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
