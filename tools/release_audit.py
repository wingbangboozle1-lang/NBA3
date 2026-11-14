#!/usr/bin/env python3
"""Independent, offline release audit for the NBA3 static site.

This checker is deliberately separate from the site builders. It does not fetch
or invent sports data. It audits the Pages staging list, captures table-row
citation coverage (row by row, not page by page), checks explicit 72-hour pick
horizons against the checked-in official schedule snapshot, and looks for
workflow merge markers and known weak verification patterns.

Usage:
    python3 tools/release_audit.py                 # print findings, no writes
    python3 tools/release_audit.py --write-report   # write audit/* reports
    python3 tools/release_audit.py --strict         # non-zero on high/critical flags

A passing local audit is not evidence that a link is current, that a model is
predictive, or that any NBA data licence permits the intended use. External
NBA sites are not fetched by this tool.
"""
from __future__ import annotations

import argparse
import ast
import csv
import html
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
NBA_DOMAINS = ("nba.com",)
REGULATOR_DOMAINS = ("kansspelautoriteit.nl", "wetten.overheid.nl", "gokstop.nl")
STATISTICAL_AUTHORITY_DOMAINS = ("nist.gov",)
REPOSITORY_DOMAINS = ("github.com", "raw.githubusercontent.com", "codeload.github.com")
MAX_HORIZON_HOURS = 72.0
EASTERN = ZoneInfo("America/New_York")
# Earlier project files use these legacy tricodes. They are used only to match
# a pick row to the official schedule; the original row is left unchanged.
TEAM_CODE_ALIASES = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}
UNVERIFIED_RE = re.compile(
    r"\b(?:unverified|not verified|not independently verified|not estimated|"
    r"not available|unavailable|not captured|not measured|not established|"
    r"blocked|unable to verify|no official source)\b",
    re.IGNORECASE,
)
MERGE_MARKER_RE = re.compile(r"^(?:<<<<<<<|=======|>>>>>>>)")


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _matches_domain(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def source_class(url: str) -> str:
    """Classify an HTTPS URL without calling the host."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "invalid"
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return "non_https"
    host = parsed.hostname.lower().rstrip(".")
    if _matches_domain(host, NBA_DOMAINS):
        return "nba_official"
    if _matches_domain(host, REGULATOR_DOMAINS):
        return "regulator_or_statute"
    if _matches_domain(host, STATISTICAL_AUTHORITY_DOMAINS):
        return "statistical_authority"
    if host in REPOSITORY_DOMAINS:
        return "repository_evidence"
    return "other_https"


class TableRowParser(HTMLParser):
    """Collect links and visible text separately for each tbody row."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tbody_depth = 0
        self.current: dict[str, Any] | None = None
        self.rows: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tbody":
            self.tbody_depth += 1
        elif tag == "tr" and self.tbody_depth and self.current is None:
            self.current = {"links": [], "text": []}
        elif tag == "a" and self.current is not None:
            href = attrs_dict.get("href")
            if href:
                self.current["links"].append(href)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self.current["text"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.current is not None:
            self.rows.append(self.current)
            self.current = None
        elif tag == "tbody" and self.tbody_depth:
            self.tbody_depth -= 1


def parse_table_rows(text: str) -> list[dict[str, Any]]:
    parser = TableRowParser()
    parser.feed(text)
    parser.close()
    return parser.rows


def _staged_sources(workflow_text: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Read source paths from `cp ... _pages/...` in the Pages staging job."""
    sources: list[str] = []
    for line in workflow_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"cp\s+(?:-r\s+)?([^\s]+)\s+_pages(?:/[^\s]*)?(?:\s|$)", stripped)
        if match:
            src = match.group(1).strip("'\"")
            if src not in sources:
                sources.append(src)
    markers = [
        {"line": n, "text": line.strip()}
        for n, line in enumerate(workflow_text.splitlines(), 1)
        if MERGE_MARKER_RE.match(line.strip())
    ]
    return sources, markers


def _html_paths_for_sources(root: Path, sources: list[str]) -> tuple[list[Path], list[str]]:
    pages: set[Path] = set()
    missing: list[str] = []
    for source in sources:
        path = root / source
        if not path.exists():
            missing.append(source)
        elif path.is_file():
            if path.suffix.lower() == ".html":
                pages.add(path.resolve())
        elif path.is_dir():
            pages.update(p.resolve() for p in path.rglob("*.html") if p.is_file())
    return sorted(pages), missing


def audit_table_rows(root: Path, pages: list[Path]) -> dict[str, Any]:
    row_records: list[dict[str, Any]] = []
    per_file: dict[str, dict[str, int]] = defaultdict(
        lambda: {"rows": 0, "nba_official": 0, "regulator_or_statute": 0,
                 "statistical_authority": 0, "repository_only": 0,
                 "other_https_only": 0, "no_https_source": 0,
                 "no_official_unflagged": 0, "no_official_flagged": 0}
    )
    for page in pages:
        try:
            rows = parse_table_rows(page.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        rel = page.relative_to(root).as_posix()
        for number, row in enumerate(rows, 1):
            text = re.sub(r"\s+", " ", " ".join(row["text"])).strip()
            links = list(dict.fromkeys(row["links"]))
            classes = {source_class(url) for url in links}
            nba_urls = [u for u in links if source_class(u) == "nba_official"]
            authority_urls = [
                u for u in links
                if source_class(u) in {"regulator_or_statute", "statistical_authority"}
            ]
            repo_urls = [u for u in links if source_class(u) == "repository_evidence"]
            other_urls = [u for u in links if source_class(u) == "other_https"]
            has_official = bool(nba_urls or authority_urls)
            marked_unverified = bool(UNVERIFIED_RE.search(text))
            if has_official:
                status = "OFFICIAL_LINK_PRESENT"
            elif marked_unverified:
                status = "NO_OFFICIAL_LINK_FLAGGED"
            else:
                status = "NO_OFFICIAL_LINK_UNFLAGGED"
            record = {
                "file": rel,
                "row_number": number,
                "status": status,
                "has_nba_official_link": bool(nba_urls),
                "has_regulator_or_statistical_authority_link": bool(authority_urls),
                "has_repository_evidence_link": bool(repo_urls),
                "has_other_https_link": bool(other_urls),
                "has_any_https_link": any(c in classes for c in {
                    "nba_official", "regulator_or_statute", "statistical_authority",
                    "repository_evidence", "other_https",
                }),
                "explicit_unverified_marker": marked_unverified,
                "source_urls": " | ".join(links),
                "row_text": text,
            }
            row_records.append(record)
            stats = per_file[rel]
            stats["rows"] += 1
            for category in ("nba_official", "regulator_or_statute", "statistical_authority"):
                if category in classes:
                    stats[category] += 1
            if not has_official and repo_urls:
                stats["repository_only"] += 1
            if not has_official and not repo_urls and other_urls:
                stats["other_https_only"] += 1
            if not record["has_any_https_link"]:
                stats["no_https_source"] += 1
            if not has_official:
                if marked_unverified:
                    stats["no_official_flagged"] += 1
                else:
                    stats["no_official_unflagged"] += 1

    status_counts = Counter(r["status"] for r in row_records)
    return {
        "html_pages_scanned": len(pages),
        "table_body_rows": len(row_records),
        "status_counts": dict(sorted(status_counts.items())),
        "rows_with_nba_official_link": sum(r["has_nba_official_link"] for r in row_records),
        "rows_with_regulator_or_statistical_authority_link": sum(
            r["has_regulator_or_statistical_authority_link"] for r in row_records
        ),
        "rows_with_any_https_link": sum(r["has_any_https_link"] for r in row_records),
        "per_file": dict(sorted(per_file.items())),
        "rows": row_records,
    }


def _normalise_team(code: Any) -> str:
    value = str(code or "").strip().upper()
    return TEAM_CODE_ALIASES.get(value, value)


def _game_key(date: str, away: str, home: str) -> tuple[str, str, str]:
    return date, _normalise_team(away), _normalise_team(home)


def _matchup_teams(record: dict[str, Any]) -> tuple[str, str] | None:
    if record.get("away") and record.get("home"):
        return _normalise_team(record["away"]), _normalise_team(record["home"])
    matchup = str(record.get("matchup") or "")
    matchup = re.split(r"\s+[—–-]\s+", matchup, maxsplit=1)[0]
    match = re.search(r"\b([A-Z]{2,3})\s*@\s*([A-Z]{2,3})\b", matchup.upper())
    if match:
        return _normalise_team(match.group(1)), _normalise_team(match.group(2))
    if record.get("team") and record.get("opponent"):
        return _normalise_team(record["team"]), _normalise_team(record["opponent"])
    return None


def _parse_generation_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _parse_tip(date: str, time_et: str) -> datetime | None:
    cleaned = re.sub(r"\s*\(?ET\)?\s*$", "", str(time_et), flags=re.IGNORECASE).strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            parsed = datetime.strptime(cleaned, fmt).time()
            local = datetime.combine(datetime.strptime(date, "%Y-%m-%d").date(), parsed, tzinfo=EASTERN)
            return local.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def audit_pick_horizon(root: Path, max_hours: float = MAX_HORIZON_HOURS) -> dict[str, Any]:
    schedule_path = root / "data" / "app" / "official_slate.json"
    if not schedule_path.exists():
        return {"status": "UNVERIFIABLE", "reason": "official_slate.json is missing", "records": [], "issues": []}
    schedule_doc = json.loads(schedule_path.read_text(encoding="utf-8"))
    games = schedule_doc.get("games", []) if isinstance(schedule_doc, dict) else []
    by_key = {
        _game_key(str(g.get("date", "")), str(g.get("away", "")), str(g.get("home", ""))): g
        for g in games
    }
    schedule_source = str(schedule_doc.get("source_url", "")) if isinstance(schedule_doc, dict) else ""
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    pick_files = sorted((root / "data" / "picks").glob("*.json"))
    for path in pick_files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = doc.get("picks") or doc.get("props")
        if not isinstance(rows, list):
            continue
        generated_raw = doc.get("generated_on") or doc.get("generated_at") or doc.get("generated_utc")
        generated = _parse_generation_time(generated_raw)
        if generated is None:
            issues.append({
                "code": "PICKS_GENERATION_TIME_MISSING",
                "file": path.relative_to(root).as_posix(),
                "detail": "No timezone-aware generation timestamp; exact 72-hour compliance cannot be established.",
                "official_source_url": schedule_source,
            })
        try:
            declared_days = float(doc.get("max_lookahead_days", 3))
        except (TypeError, ValueError):
            declared_days = 3.0
        allowed_hours = min(max_hours, declared_days * 24.0) if declared_days > 0 else max_hours
        for index, row in enumerate(rows, 1):
            date = str(row.get("date") or "")
            teams = _matchup_teams(row)
            game = by_key.get((date, teams[0], teams[1])) if teams else None
            # Player props may identify team/opponent without home/away order.
            if game is None and teams:
                target = set(teams)
                game = next((g for g in games if str(g.get("date")) == date and
                             {_normalise_team(g.get("away")), _normalise_team(g.get("home"))} == target), None)
            if game is None:
                issues.append({
                    "code": "PICK_NOT_MATCHED_TO_OFFICIAL_SCHEDULE",
                    "file": path.relative_to(root).as_posix(),
                    "row_number": index,
                    "detail": "Pick row could not be matched to an official schedule row; no matchup or time was inferred.",
                    "official_source_url": schedule_source,
                })
                records.append({
                    "file": path.relative_to(root).as_posix(), "row_number": index,
                    "date": date, "matchup": row.get("matchup", ""),
                    "status": "UNMATCHED_OFFICIAL_SCHEDULE", "generation_time_utc": generated_raw or "",
                    "tip_time_et": "", "hours_ahead": "", "source_url": schedule_source,
                })
                continue
            tip = _parse_tip(date, str(game.get("time_et", "")))
            if tip is None:
                issues.append({
                    "code": "OFFICIAL_TIP_TIME_UNPARSEABLE",
                    "file": path.relative_to(root).as_posix(),
                    "row_number": index,
                    "detail": "The schedule time is present but cannot be parsed without guessing.",
                    "official_source_url": str(game.get("nba_game_url") or schedule_source),
                })
                continue
            ahead = (tip - generated).total_seconds() / 3600 if generated else None
            status = "TIMESTAMP_MISSING" if ahead is None else "WITHIN_HORIZON"
            if ahead is not None and ahead > allowed_hours:
                status = "OUTSIDE_HORIZON"
                issue = {
                    "code": "PICK_OUTSIDE_MAX_HORIZON",
                    "file": path.relative_to(root).as_posix(),
                    "row_number": index,
                    "date": date,
                    "matchup": f"{game.get('away', '')} @ {game.get('home', '')}",
                    "tip_time_et": game.get("time_et", ""),
                    "generation_time_utc": generated.isoformat().replace("+00:00", "Z"),
                    "hours_ahead": round(ahead, 4),
                    "excess_minutes": round((ahead - allowed_hours) * 60),
                    "detail": f"Tip-off is {ahead:.2f} hours after generation, beyond the {allowed_hours:g}-hour limit.",
                    "official_source_url": str(game.get("nba_game_url") or schedule_source),
                    "schedule_source_url": schedule_source,
                }
                issues.append(issue)
            records.append({
                "file": path.relative_to(root).as_posix(),
                "row_number": index,
                "date": date,
                "matchup": f"{game.get('away', '')} @ {game.get('home', '')}",
                "generation_time_utc": generated.isoformat().replace("+00:00", "Z") if generated else "",
                "tip_time_et": game.get("time_et", ""),
                "hours_ahead": round(ahead, 4) if ahead is not None else "",
                "allowed_hours": allowed_hours,
                "status": status,
                "source_url": str(game.get("nba_game_url") or schedule_source),
            })
    return {
        "status": "CHECKED" if records else "NO_TIMESTAMPED_PICK_FILES",
        "max_allowed_hours": max_hours,
        "official_schedule_source_url": schedule_source,
        "schedule_rows": len(games),
        "timestamped_pick_rows": sum(bool(r.get("generation_time_utc")) for r in records),
        "records": records,
        "issues": issues,
    }


def _source_gate_audit(root: Path) -> dict[str, Any]:
    check_path = root / "integrate" / "check.py"
    source = check_path.read_text(encoding="utf-8") if check_path.exists() else ""
    page_wide = "'href=\"https://' in blob" in source or "'href=\\\"https://' in blob" in source
    row_scoped = bool(re.search(r"row\s*\[.{0,40}links|row_links|links_by_row|row\.get\(['\"]links", source, re.I))
    scanner_path = root / "scripts" / "scan_table_sources.py"
    scanner = scanner_path.read_text(encoding="utf-8") if scanner_path.exists() else ""
    github_in_official = bool(re.search(r"OFFICIAL_HOSTS\s*=\s*\([^)]*github\.com", scanner, re.S))
    return {
        "checker_file": "integrate/check.py" if check_path.exists() else "",
        "page_wide_source_predicate_detected": page_wide,
        "row_scoped_link_collection_detected": row_scoped,
        "row_level_gate_is_reliable": row_scoped,
        "legacy_scanner_includes_github_in_official_host_list": github_in_official,
    }


def _capture_audit(root: Path) -> dict[str, Any]:
    path = root / "scripts" / "capture_official_2026_11_14.py"
    if not path.exists():
        return {"file": "", "static_transcription_constants": False, "http_client_imports": [], "offline_snapshot_script": False}
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"file": path.relative_to(root).as_posix(), "static_transcription_constants": False, "http_client_imports": [], "offline_snapshot_script": False}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    clients = sorted(imported & {"requests", "urllib", "http", "httpx", "aiohttp", "socket", "ftplib"})
    static_names = {"SLATE", "TEAM_RATINGS", "INJ"}
    assigned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
    static = static_names.issubset(assigned)
    return {
        "file": path.relative_to(root).as_posix(),
        "static_transcription_constants": static,
        "http_client_imports": clients,
        "offline_snapshot_script": static and not clients,
    }


def _revision(root: Path) -> str:
    for ref in ("origin/main", "HEAD"):
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short=12", ref],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return "unknown"


def _workflow_audit(root: Path) -> tuple[dict[str, Any], list[Path]]:
    path = root / ".github" / "workflows" / "pages.yml"
    if not path.exists():
        return ({"file": "", "exists": False, "merge_markers": [], "staged_sources": [],
                 "staged_html_pages": 0, "missing_staged_sources": []}, [])
    text = path.read_text(encoding="utf-8")
    sources, markers = _staged_sources(text)
    pages, missing = _html_paths_for_sources(root, sources)
    return ({
        "file": path.relative_to(root).as_posix(),
        "exists": True,
        "merge_markers": markers,
        "staged_sources": sources,
        "staged_html_pages": len(pages),
        "missing_staged_sources": missing,
    }, pages)


def build_audit(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    workflow, pages = _workflow_audit(root)
    table_audit = audit_table_rows(root, pages)
    pick_audit = audit_pick_horizon(root)
    gate_audit = _source_gate_audit(root)
    capture_audit = _capture_audit(root)
    findings: list[dict[str, Any]] = []
    workflow_url = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/pages.yml"
    check_url = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/integrate/check.py"
    scanner_url = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/scan_table_sources.py"
    capture_url = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/capture_official_2026_11_14.py"
    schedule_url = pick_audit.get("official_schedule_source_url") or "https://www.nba.com/schedule?date=2026-11-14"

    if workflow.get("merge_markers"):
        findings.append({
            "id": "RA-01", "severity": "critical", "status": "open",
            "title": "The checked-in Pages workflow contains unresolved merge-conflict markers.",
            "detail": "The workflow source has literal conflict-marker lines. The staged-page list can still be counted, but this file is not a trustworthy release definition until the markers are removed and GitHub Actions validates the resulting YAML.",
            "evidence": workflow_url,
            "official_source": "https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions",
        })
    if gate_audit["page_wide_source_predicate_detected"] and not gate_audit["row_scoped_link_collection_detected"]:
        missing = table_audit["status_counts"].get("NO_OFFICIAL_LINK_UNFLAGGED", 0)
        findings.append({
            "id": "RA-02", "severity": "high", "status": "open",
            "title": "The unified dashboard's citation check is page-wide, not table-row-wide.",
            "detail": f"`integrate/check.py` looks for an HTTPS link anywhere in a page body for each table; it does not collect links per row. The independent row parser found {missing} staged table rows with no direct NBA, regulator/statute, or statistical-authority link and no explicit unverified marker.",
            "evidence": check_url,
            "official_source": "https://www.nba.com/stats/help/glossary",
        })
    missing_official = (
        table_audit["status_counts"].get("NO_OFFICIAL_LINK_FLAGGED", 0)
        + table_audit["status_counts"].get("NO_OFFICIAL_LINK_UNFLAGGED", 0)
    )
    findings.append({
        "id": "RA-03", "severity": "high" if missing_official else "low", "status": "open" if missing_official else "resolved",
        "title": "Some published table rows have no direct NBA or authority source link.",
        "detail": f"Across {table_audit['html_pages_scanned']} Pages-staged HTML files, {table_audit['table_body_rows']} table-body rows were inspected. {missing_official} rows have no direct NBA, regulator/statute, or statistical-authority link. Repository-code links are classified separately and do not count as NBA data citations.",
        "evidence": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/audit/table-source-audit.csv",
        "official_source": "https://www.nba.com/stats/help/glossary",
    })
    horizon_issues = [x for x in pick_audit.get("issues", []) if x.get("code") == "PICK_OUTSIDE_MAX_HORIZON"]
    if horizon_issues:
        details = "; ".join(
            f"{x['matchup']} {x['date']} {x['tip_time_et']} ET: {x['hours_ahead']:.2f}h (+{x['excess_minutes']} min)"
            for x in horizon_issues
        )
        findings.append({
            "id": "RA-04", "severity": "high", "status": "open",
            "title": f"{len(horizon_issues)} published pick(s) exceed the exact 72-hour horizon.",
            "detail": details + ". Keep only picks whose official tip time is within 72 hours of a timezone-aware generation timestamp, or explicitly define a different date-based policy.",
            "evidence": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/picks/picks_2026-11-14_to_16.json",
            "official_source": schedule_url,
        })
    if capture_audit.get("offline_snapshot_script"):
        findings.append({
            "id": "RA-05", "severity": "high", "status": "open",
            "title": "The canonical 'official capture' CI step is an offline hard-coded transcription check, not a live re-fetch.",
            "detail": "The script contains static schedule, team-statistics, and injury-report constants and has no HTTP client import. Running it in CI checks the committed snapshot against those same constants; it cannot establish that a source is current or independently re-verify the transcription.",
            "evidence": capture_url,
            "official_source": schedule_url,
        })
    model_path = root / "data" / "integration" / "model.json"
    if model_path.exists():
        model = json.loads(model_path.read_text(encoding="utf-8"))
        exact_time_fields = ("generated_utc", "generated_on", "generated_at", "created_at")
        if not any(model.get(k) for k in exact_time_fields):
            findings.append({
                "id": "RA-06", "severity": "medium", "status": "open",
                "title": "The unified line artifact has no exact generation timestamp for a strict 72-hour check.",
                "detail": "The artifact carries a date window and `horizon_days`, but no timezone-aware generation time. The exact tip-time horizon for its lines therefore cannot be reproduced from the artifact alone.",
                "evidence": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/integration/model.json",
                "official_source": schedule_url,
            })
    if gate_audit["legacy_scanner_includes_github_in_official_host_list"]:
        findings.append({
            "id": "RA-07", "severity": "medium", "status": "open",
            "title": "The earlier source scanner treats GitHub repository links as 'official' links.",
            "detail": "GitHub is primary evidence for repository facts and code, but it does not make a row's NBA statistics or injury values official. This audit keeps repository evidence in a separate class.",
            "evidence": scanner_url,
            "official_source": "https://www.nba.com/stats/help/glossary",
        })
    unresolved_horizon_issues = [
        x for x in pick_audit.get("issues", [])
        if x.get("code") != "PICK_OUTSIDE_MAX_HORIZON"
    ]
    if unresolved_horizon_issues:
        # Surface unresolved rows/timestamps as review items rather than silently dropping them.
        counts = Counter(x.get("code", "UNKNOWN") for x in unresolved_horizon_issues)
        findings.append({
            "id": "RA-08", "severity": "medium", "status": "open",
            "title": "Some pick rows cannot be checked against the exact schedule horizon.",
            "detail": "; ".join(f"{code}: {count}" for code, count in sorted(counts.items())),
            "evidence": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/picks/",
            "official_source": schedule_url,
        })

    report = {
        "report_title": "NBA3 release audit",
        "baseline_revision": _revision(root),
        "audit_mode": "offline repository audit; no external NBA pages were fetched by this tool",
        "policy": {
            "max_pick_horizon_hours": MAX_HORIZON_HOURS,
            "source_rule": "Direct HTTPS links to NBA, regulator/statute, or statistical-authority hosts are counted as official sources. GitHub repo links are classified as repository evidence only.",
            "no_inference": "Unmatched schedule rows remain unresolved; no missing matchup, time, value, or source is filled in.",
        },
        "workflow": workflow,
        "table_source_audit": {k: v for k, v in table_audit.items() if k != "rows"},
        "pick_horizon_audit": pick_audit,
        "source_gate_audit": gate_audit,
        "capture_script_audit": capture_audit,
        "findings": findings,
        "sources_manual_review": [
            {"title": "Official NBA schedule", "url": schedule_url, "scope": "game dates, teams, tip times and game IDs in the stored schedule snapshot; not re-fetched in this audit"},
            {"title": "Official NBA injury report index", "url": "https://official.nba.com/nba-injury-report-2026-27-season/", "scope": "report listing and report timestamps; not re-fetched in this audit"},
            {"title": "Official NBA injury-report PDF", "url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf", "scope": "stored injury snapshot; not re-fetched in this audit"},
            {"title": "NBA Stats glossary", "url": "https://www.nba.com/stats/help/glossary", "scope": "official terminology reference, not model validation or data-use permission"},
        ],
    }
    return report, table_audit, pick_audit


def _md_link(url: str, label: str) -> str:
    return f"[{label}]({url})" if url else "—"


def render_markdown(report: dict[str, Any]) -> str:
    table = report["table_source_audit"]
    horizon = report["pick_horizon_audit"]
    workflow = report["workflow"]
    lines = [
        "# NBA3 release audit",
        "",
        f"> **Audit baseline:** `{report.get('baseline_revision', 'unknown')}`. This is an offline, repository-local audit; no NBA page or PDF was fetched by this tool. Links below are supplied for manual review; stored values are not newly verified against a live official source here.",
        "> **Decision status:** Code and data-governance review only. This audit does not establish a profitable strategy or approve a wager.",
        "",
        "## Executive summary",
        "",
        "| Check | Result | Source / evidence |",
        "|---|---|---|",
        f"| Pages workflow conflict markers | {len(workflow.get('merge_markers', []))} | {_md_link('https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/pages.yml', 'workflow source')} |",
        f"| Pages-staged HTML | {table.get('html_pages_scanned', 0)} files | {_md_link('https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/pages.yml', 'staging list')} |",
        f"| HTML table-body rows | {table.get('table_body_rows', 0)} | {_md_link('https://www.nba.com/stats/help/glossary', 'NBA Stats glossary (terminology reference)')} |",
        f"| Rows with direct NBA official link | {table.get('rows_with_nba_official_link', 0)} | {_md_link('https://www.nba.com/schedule?date=2026-11-14', 'NBA schedule (manual review)')} |",
        f"| Rows without NBA/regulator/statistical-authority links | {table.get('status_counts', {}).get('NO_OFFICIAL_LINK_FLAGGED', 0) + table.get('status_counts', {}).get('NO_OFFICIAL_LINK_UNFLAGGED', 0)} | {_md_link('https://github.com/wingbangboozle1-lang/NBA3/blob/main/audit/table-source-audit.csv', 'row-by-row CSV')} |",
        f"| Timestamped picks checked | {horizon.get('timestamped_pick_rows', 0)} | {_md_link(horizon.get('official_schedule_source_url', ''), 'official schedule snapshot')} |",
        f"| 72-hour violations | {sum(x.get('code') == 'PICK_OUTSIDE_MAX_HORIZON' for x in horizon.get('issues', []))} | {_md_link('https://www.nba.com/schedule?date=2026-11-14', 'NBA official schedule')} |",
        "",
        "## Findings",
        "",
        "| ID / severity | Finding | Evidence | Official reference |",
        "|---|---|---|---|",
    ]
    for item in report.get("findings", []):
        finding = f"**{item['title']}**<br>{item['detail']}"
        lines.append(
            f"| {item['id']} / {item['severity']} ({item['status']}) | {finding} | "
            f"{_md_link(item.get('evidence', ''), 'repository evidence')} | "
            f"{_md_link(item.get('official_source', ''), 'official reference')} |"
        )
    lines.extend([
        "",
        "## Per-file source coverage",
        "",
        "A row is counted as directly sourced only when that row itself contains an HTTPS link to an NBA, regulator/statute, or statistical-authority host. Repository-code links are listed separately and are not presented as official NBA data sources.",
        "",
        "| Published HTML file | Rows | NBA links | Regulator/statute links | Statistical authority links | No official link, unflagged | Repository evidence | File evidence |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for name, stats in table.get("per_file", {}).items():
        lines.append(
            f"| `{name}` | {stats['rows']} | {stats['nba_official']} | {stats['regulator_or_statute']} | {stats['statistical_authority']} | {stats['no_official_unflagged']} | {stats['repository_only']} | {_md_link('https://github.com/wingbangboozle1-lang/NBA3/blob/main/' + name, 'source file')} |"
        )
    lines.extend([
        "",
        "## 72-hour horizon details",
        "",
        "Tip times are converted from Eastern Time using the IANA `America/New_York` zone. Rows without a timezone-aware generation timestamp or an exact official-schedule match are left unresolved; no date or time is inferred.",
        "",
        "| File / row | Game | Generation UTC | Official tip time ET | Hours ahead | Result | Official game source |",
        "|---|---|---|---|---:|---|---|",
    ])
    for item in horizon.get("records", []):
        lines.append(
            f"| `{item.get('file', '')}` #{item.get('row_number', '')} | {item.get('matchup', '')} {item.get('date', '')} | {item.get('generation_time_utc', '') or '—'} | {item.get('tip_time_et', '') or '—'} | {item.get('hours_ahead', '') if item.get('hours_ahead', '') != '' else '—'} | {item.get('status', '')} | {_md_link(item.get('source_url', ''), 'NBA game page/schedule')} |"
        )
    lines.extend([
        "",
        "## Verification boundary and reproducibility",
        "",
        "- This audit reads checked-in files only. It does not fetch external sources and cannot prove that a source link is live, that a stored value matches the current official page, that data use is licensed, or that a strategy has skill-based predictive value.",
        "- `python3 tools/release_audit.py --write-report` regenerates this report and `audit/table-source-audit.csv` from the repository contents.",
        "- `python3 -m unittest audit.test_release_audit` runs the parser, host-classification, time-zone, horizon-boundary, and workflow-marker regression tests.",
        "- Official-source manual-review links: " + "; ".join(_md_link(x["url"], x["title"]) for x in report.get("sources_manual_review", [])),
        "",
    ])
    return "\n".join(lines)


def render_html(report: dict[str, Any]) -> str:
    table = report["table_source_audit"]
    horizon = report["pick_horizon_audit"]
    rows = []
    for item in report.get("findings", []):
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(item['id'])}</strong><br>{html.escape(item['severity'])}</td>"
            f"<td><strong>{html.escape(item['title'])}</strong><br>{html.escape(item['detail'])}</td>"
            f"<td><a href=\"{html.escape(item.get('evidence', ''), quote=True)}\">Repository evidence</a></td>"
            f"<td><a href=\"{html.escape(item.get('official_source', ''), quote=True)}\">Official reference</a></td>"
            "</tr>"
        )
    per_file_rows = []
    for name, stats in table.get("per_file", {}).items():
        url = "https://github.com/wingbangboozle1-lang/NBA3/blob/main/" + name
        per_file_rows.append(
            "<tr>"
            f"<td><a href=\"{html.escape(url, quote=True)}\">{html.escape(name)}</a></td>"
            f"<td>{stats['rows']}</td><td>{stats['nba_official']}</td>"
            f"<td>{stats['regulator_or_statute']}</td><td>{stats['statistical_authority']}</td>"
            f"<td>{stats['no_official_unflagged']}</td><td>{stats['repository_only']}</td>"
            f"<td><a href=\"https://www.nba.com/stats/help/glossary\">NBA official terminology</a></td>"
            "</tr>"
        )
    horizon_rows = []
    for item in horizon.get("records", []):
        source = item.get("source_url") or horizon.get("official_schedule_source_url") or "https://www.nba.com/schedule"
        ahead = item.get("hours_ahead", "")
        horizon_rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('file', '')))} #{html.escape(str(item.get('row_number', '')))}</td>"
            f"<td>{html.escape(str(item.get('matchup', '')))}<br>{html.escape(str(item.get('date', '')))}</td>"
            f"<td>{html.escape(str(item.get('generation_time_utc') or '—'))}</td>"
            f"<td>{html.escape(str(item.get('tip_time_et') or '—'))}</td>"
            f"<td>{html.escape(str(ahead if ahead != '' else '—'))}</td>"
            f"<td>{html.escape(str(item.get('status', '')))}</td>"
            f"<td><a href=\"{html.escape(source, quote=True)}\">Official NBA source</a></td>"
            "</tr>"
        )
    source_links = " · ".join(
        f"<a href=\"{html.escape(s['url'], quote=True)}\">{html.escape(s['title'])}</a>"
        for s in report.get("sources_manual_review", [])
    )
    findings_count = len(report.get("findings", []))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NBA3 release audit</title>
<style>
:root{{--bg:#f4f7fb;--panel:#fff;--ink:#152438;--muted:#5c6b7a;--line:#dce4ed;--blue:#1261a0;--red:#a52828;--amber:#8a5400}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}
header{{background:#10283f;color:#fff;padding:28px 4vw}}header h1{{margin:0 0 6px;font-size:1.8rem}}header p{{margin:0;color:#d8e6f2;max-width:1000px}}
main{{max-width:1250px;margin:24px auto;padding:0 18px}}.notice{{background:#fff5dc;border:1px solid #eed28e;border-left:5px solid #bc7b00;border-radius:8px;padding:14px 16px;margin-bottom:18px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:16px 0}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:15px}}.card strong{{display:block;font-size:1.55rem}}.card span{{color:var(--muted);font-size:.9rem}}
section{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0;overflow:auto}}h2{{margin:0 0 12px;font-size:1.25rem}}table{{border-collapse:collapse;width:100%;font-size:.91rem}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:#edf3f8;white-space:nowrap}}a{{color:var(--blue)}}.warn{{color:var(--red);font-weight:700}}footer{{padding:20px 4vw;color:var(--muted);font-size:.9rem}}
</style></head><body>
<header><h1>NBA3 release audit</h1><p>Independent offline review of source coverage, pick timing and release checks. Baseline {html.escape(report.get('baseline_revision', 'unknown'))}; {findings_count} review findings. This is not a validation of predictive skill.</p></header>
<main>
<div class="notice"><strong>Important:</strong> No NBA page or PDF was fetched by this audit tool. The external links are provided for manual review. Values in the repository are not newly verified against a live official source here.</div>
<div class="cards">
<div class="card"><strong>{len(report['workflow'].get('merge_markers', []))}</strong><span>merge-conflict marker lines in Pages workflow</span></div>
<div class="card"><strong>{table.get('html_pages_scanned', 0)}</strong><span>HTML files in the Pages staging commands</span></div>
<div class="card"><strong>{table.get('table_body_rows', 0)}</strong><span>table-body rows parsed individually</span></div>
<div class="card"><strong>{table.get('rows_with_nba_official_link', 0)}</strong><span>rows with a direct NBA-domain source link</span></div>
<div class="card"><strong>{sum(x.get('code') == 'PICK_OUTSIDE_MAX_HORIZON' for x in horizon.get('issues', []))}</strong><span>timestamped picks beyond the strict 72-hour limit</span></div>
</div>
<section><h2>Flagged findings</h2><table><thead><tr><th>ID / severity</th><th>Finding and evidence</th><th>Repository evidence</th><th>Official reference</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>Page-by-page table-source coverage</h2><p>Only links inside the same table row count. GitHub links are repository evidence, not NBA data sources. The full row-level list is <a href="table-source-audit.csv">table-source-audit.csv</a>.</p><table><thead><tr><th>Published HTML file</th><th>Rows</th><th>NBA</th><th>Regulator/statute</th><th>Statistical authority</th><th>No official link, unflagged</th><th>Repo-only citation</th><th>Manual review</th></tr></thead><tbody>{''.join(per_file_rows)}</tbody></table></section>
<section><h2>72-hour pick-horizon check</h2><p>Official Eastern Time tip times are compared with timezone-aware generation timestamps. No schedule match or timestamp is inferred.</p><table><thead><tr><th>Pick row</th><th>Game</th><th>Generated UTC</th><th>Tip ET</th><th>Hours ahead</th><th>Status</th><th>Official source</th></tr></thead><tbody>{''.join(horizon_rows)}</tbody></table></section>
<section><h2>Official references for manual review</h2><p>{source_links}</p><p>Official references define schedule, injury and statistical terminology; they do not prove a model edge or resolve legal/data-rights questions.</p></section>
</main><footer>Reproduce with <code>python3 tools/release_audit.py --write-report</code>. Tests: <code>python3 -m unittest audit.test_release_audit</code>. Standard library only.</footer>
</body></html>"""


def write_report(root: Path, report: dict[str, Any], table_audit: dict[str, Any], pick_audit: dict[str, Any]) -> None:
    out = root / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "release-audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "release-audit.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "release-audit.html").write_text(render_html(report), encoding="utf-8")
    with (out / "table-source-audit.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["file", "row_number", "status", "has_nba_official_link",
                  "has_regulator_or_statistical_authority_link", "has_repository_evidence_link",
                  "has_other_https_link", "has_any_https_link", "explicit_unverified_marker",
                  "source_urls", "row_text"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(table_audit.get("rows", []))
    with (out / "pick-horizon-audit.csv").open("w", encoding="utf-8", newline="") as f:
        records = pick_audit.get("records", [])
        fields = ["file", "row_number", "date", "matchup", "generation_time_utc",
                  "tip_time_et", "hours_ahead", "allowed_hours", "status", "source_url"]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: detected from this script)")
    parser.add_argument("--write-report", action="store_true", help="write JSON, Markdown, HTML, and CSV under audit/")
    parser.add_argument("--strict", action="store_true", help="return exit code 1 when critical/high findings remain")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report, table_audit, pick_audit = build_audit(root)
    print(f"Pages workflow: {len(report['workflow'].get('merge_markers', []))} merge markers; "
          f"{report['workflow'].get('staged_html_pages', 0)} staged HTML files")
    print(f"Table rows: {table_audit['table_body_rows']} across {table_audit['html_pages_scanned']} files; "
          f"{table_audit['rows_with_nba_official_link']} with a direct NBA link; "
          f"{table_audit['status_counts'].get('NO_OFFICIAL_LINK_UNFLAGGED', 0)} without official link and no explicit unverified marker")
    print(f"Pick timing: {len(pick_audit.get('records', []))} rows checked; "
          f"{sum(i.get('code') == 'PICK_OUTSIDE_MAX_HORIZON' for i in pick_audit.get('issues', []))} exceed 72 hours")
    for item in report["findings"]:
        print(f"{item['id']} [{item['severity']}] {item['title']}")
    print("Audit mode: offline; no external NBA pages fetched.")
    if args.write_report:
        write_report(root, report, table_audit, pick_audit)
        print("Wrote audit/release-audit.{json,md,html}, audit/table-source-audit.csv, and audit/pick-horizon-audit.csv")
    if args.strict and any(f["severity"] in {"critical", "high"} and f["status"] == "open" for f in report["findings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
