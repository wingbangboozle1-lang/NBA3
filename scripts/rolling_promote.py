#!/usr/bin/env python3
"""Parse and safely promote an official NBA.com rolling schedule capture.

The NBA games page contains a server-rendered ``__NEXT_DATA__`` payload with the selected
calendar date, the official daily game count, and the page's complete ``gameCardFeed``. The
promoter uses those structured values (not every incidental ``/game/`` anchor in the page;
NBA.com pages can contain unrelated game links). A daily page is accepted only when its
selected date, advertised count, and unique game cards agree. Any mismatch fails closed.

This module is shared by refresh_preflight.py and refresh_official.py so the preview checked
by the gate is byte-for-byte based on the same parsing rules as the staged promotion.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

TEAM_CODES = {
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
}
GAME_ID_RE = re.compile(r"^\d{10}$")
GAME_LINK_RE = re.compile(
    r"/game/([a-z]{3})-vs-([a-z]{3})-(\d{10})(?:/|[\"?#])", re.IGNORECASE
)


class SchedulePageError(ValueError):
    """Raised when an official schedule page is not a complete, parseable daily feed."""


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._active = False
        self._found = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self._active = True
            self._found += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._active:
            self._active = False

    def handle_data(self, data: str) -> None:
        if self._active:
            self._chunks.append(data)


def _next_data(html: str) -> dict[str, Any]:
    parser = _NextDataParser()
    parser.feed(html)
    parser.close()
    if parser._found != 1:
        raise SchedulePageError(
            f"expected one __NEXT_DATA__ script, found {parser._found}"
        )
    try:
        payload = json.loads("".join(parser._chunks))
    except json.JSONDecodeError as exc:
        raise SchedulePageError(f"invalid __NEXT_DATA__ JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SchedulePageError("__NEXT_DATA__ root is not an object")
    props = payload.get("props")
    page_props = props.get("pageProps") if isinstance(props, dict) else None
    if not isinstance(page_props, dict):
        raise SchedulePageError("NBA.com page has no structured pageProps object")
    return page_props


def parse_schedule_page(html: str, day: str, source_url: str) -> dict[str, Any]:
    """Validate one official daily schedule page and return its complete game-card rows."""
    try:
        requested = date.fromisoformat(day)
    except (TypeError, ValueError) as exc:
        raise SchedulePageError(f"invalid requested Eastern schedule date {day!r}") from exc

    page = _next_data(html)
    if page.get("selectedDate") != requested.isoformat():
        raise SchedulePageError(
            f"page selectedDate {page.get('selectedDate')!r} does not match {day}"
        )

    annual = page.get("allGamesInCurrentYear")
    year_counts = annual.get(str(requested.year)) if isinstance(annual, dict) else None
    expected_raw = year_counts.get(day) if isinstance(year_counts, dict) else None
    if isinstance(expected_raw, bool) or not isinstance(expected_raw, (int, str)):
        raise SchedulePageError(f"official daily game count is missing for {day}")
    try:
        expected_count = int(expected_raw)
    except (TypeError, ValueError) as exc:
        raise SchedulePageError(f"official daily game count is not an integer for {day}") from exc
    if expected_count < 0:
        raise SchedulePageError(f"official daily game count is negative for {day}")

    feed = page.get("gameCardFeed")
    if not isinstance(feed, dict):
        raise SchedulePageError(f"official gameCardFeed is missing for {day}")
    if feed.get("nextPageToken") not in (None, ""):
        raise SchedulePageError(f"official gameCardFeed is paginated; {day} is incomplete")
    modules = feed.get("modules")
    if not isinstance(modules, list):
        raise SchedulePageError(f"official gameCardFeed modules are missing for {day}")

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for module_index, module in enumerate(modules):
        if not isinstance(module, dict) or not isinstance(module.get("cards"), list):
            raise SchedulePageError(f"invalid schedule module {module_index} on {day}")
        for card_index, card in enumerate(module["cards"]):
            card_data = card.get("cardData") if isinstance(card, dict) else None
            if not isinstance(card_data, dict):
                raise SchedulePageError(
                    f"invalid game card {module_index}:{card_index} on {day}"
                )
            game_id = card_data.get("gameId")
            if not isinstance(game_id, str) or not GAME_ID_RE.fullmatch(game_id):
                raise SchedulePageError(
                    f"invalid official game id {game_id!r} on {day}"
                )
            if game_id in seen_ids:
                raise SchedulePageError(f"duplicate official game card {game_id} on {day}")
            seen_ids.add(game_id)

            away_data = card_data.get("awayTeam")
            home_data = card_data.get("homeTeam")
            away = away_data.get("teamTricode") if isinstance(away_data, dict) else None
            home = home_data.get("teamTricode") if isinstance(home_data, dict) else None
            if away not in TEAM_CODES or home not in TEAM_CODES or away == home:
                raise SchedulePageError(
                    f"invalid official matchup {away!r} @ {home!r} on {day} ({game_id})"
                )

            # Retain only a clearly scheduled tip-time label. NBA.com uses the same field
            # for live clocks and final statuses; those are intentionally left blank here.
            status = card_data.get("gameStatusText")
            time_et = (status if isinstance(status, str)
                       and re.fullmatch(r"\d{1,2}:\d{2}\s+[ap]m\s+ET", status, re.I)
                       else None)
            rows.append({
                "date": day,
                "time_et": time_et,
                "away": away,
                "home": home,
                "game_id": game_id,
                "away_record": None,
                "home_record": None,
                "game_url": (f"https://www.nba.com/game/{away.lower()}-vs-"
                             f"{home.lower()}-{game_id}"),
                "source": source_url,
            })

    if len(rows) != expected_count:
        raise SchedulePageError(
            f"official daily count says {expected_count} game(s), "
            f"but {len(rows)} unique game card(s) were parsed for {day}"
        )

    # The official Next payload provides the cards; matching anchors establish that NBA.com
    # links those card IDs to the same away/home sides. Ignore unrelated game links on the
    # page (e.g. recaps) that are not part of this selected-date feed.
    links: dict[str, tuple[str, str]] = {}
    for match in GAME_LINK_RE.finditer(html):
        away, home, game_id = match.groups()
        pair = (away.upper(), home.upper())
        if game_id in links and links[game_id] != pair:
            raise SchedulePageError(f"conflicting official game links for {game_id} on {day}")
        links[game_id] = pair
    for row in rows:
        if row["game_id"] in links and links[row["game_id"]] != (row["away"], row["home"]):
            raise SchedulePageError(
                f"official game link and game card disagree for {row['game_id']} on {day}"
            )

    return {"date": day, "expected_count": expected_count, "games": rows}


def build_rolling_slate(page_html: Mapping[str, str], start: date, *, stamp: str,
                        games_url_prefix: str, days: int = 4) -> dict[str, Any]:
    """Build a rolling slate only when each official daily page is complete.

    Returns a result object with a ``slate`` (None on failure), ``errors``, and a daily
    count audit. The expected horizon is start through start + days - 1, inclusive.
    """
    if days < 1:
        raise ValueError("days must be positive")
    if not isinstance(stamp, str) or not stamp:
        raise ValueError("retrieval stamp is required")

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    counts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        html = page_html.get(day)
        if not isinstance(html, str) or not html:
            errors.append(f"missing official schedule page for {day}")
            counts.append({"date": day, "expected": None, "parsed": 0, "complete": False})
            continue
        source_url = games_url_prefix + day
        try:
            parsed = parse_schedule_page(html, day, source_url)
        except SchedulePageError as exc:
            errors.append(f"{day}: {exc}")
            counts.append({"date": day, "expected": None, "parsed": 0, "complete": False})
            continue

        day_teams: set[str] = set()
        for row in parsed["games"]:
            game_id = row["game_id"]
            if game_id in seen_ids:
                errors.append(f"duplicate game id across rolling dates: {game_id}")
            seen_ids.add(game_id)
            for team in (row["away"], row["home"]):
                if team in day_teams:
                    errors.append(f"team {team} appears in multiple games on {day}")
                day_teams.add(team)
            rows.append(row)
        counts.append({"date": day, "expected": parsed["expected_count"],
                       "parsed": len(parsed["games"]), "complete": True})

    rows.sort(key=lambda row: (row["date"], row["game_id"]))
    slate: dict[str, Any] | None = None
    if not errors:
        end = start + timedelta(days=days - 1)
        slate = {
            "source_url": games_url_prefix + start.isoformat(),
            "source_urls": [games_url_prefix + (start + timedelta(days=i)).isoformat()
                            for i in range(days)],
            "source_label": ("official NBA.com selected-date gameCardFeed; every daily card "
                             "count matched the official calendar count"),
            "retrieved_on": stamp[:10],
            "retrieved_utc": stamp,
            "window": {"from": start.isoformat(), "to": end.isoformat()},
            "count": len(rows),
            "daily_counts": counts,
            "games": rows,
            "notes": ["rows are parsed from official selected-date game cards; scheduled "
                      "tip-time labels are retained, while live/final statuses are blank"],
        }
    return {"slate": slate, "games": rows, "errors": errors, "daily_counts": counts}


def staged_slate_matches(staged: Any, expected: dict[str, Any], stamp: str) -> tuple[bool, str]:
    """Require the pre-gate staged JSON to equal the independently rebuilt slate."""
    if not isinstance(staged, dict):
        return False, "staged rolling slate is missing or is not a JSON object"
    if staged.get("retrieved_utc") != stamp:
        return False, "staged slate retrieval stamp does not match the current run"
    for key in ("source_url", "source_urls", "window", "count", "daily_counts"):
        if staged.get(key) != expected.get(key):
            return False, f"staged slate {key} does not match the current official capture"
    staged_games = staged.get("games")
    expected_games = expected.get("games")
    if not isinstance(staged_games, list) or staged_games != expected_games:
        return False, "staged game rows do not exactly match current official game cards"
    return True, "staged slate exactly matches the complete official four-day page captures"


def write_json_atomic(path: Path | str, payload: dict[str, Any]) -> None:
    """Atomically write one JSON file in its destination directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp",
                                     dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def promote_slate(staged_path: Path | str, target_path: Path | str) -> None:
    """Atomically promote an already-gated staged slate to the published path."""
    staged = Path(staged_path)
    payload = json.loads(staged.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        raise SchedulePageError("staged slate is not a valid object with game rows")
    write_json_atomic(target_path, payload)
