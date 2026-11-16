"""Offline tests for the official NBA.com rolling-schedule parser and promoter."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rolling_promote as rolling  # noqa: E402


def page(day, cards, announced=None, *, selected_date=None, next_page=None):
    if announced is None:
        announced = len(cards)
    payload = {
        "props": {"pageProps": {
            "selectedDate": selected_date or day,
            "allGamesInCurrentYear": {day[:4]: {day: announced}},
            "gameCardFeed": {
                "nextPageToken": next_page,
                "modules": [{"cards": [{"cardData": card} for card in cards]}],
            },
        }},
    }
    links = "".join(
        f'<a href="/game/{c["awayTeam"]["teamTricode"].lower()}-vs-'
        f'{c["homeTeam"]["teamTricode"].lower()}-{c["gameId"]}/">game</a>'
        for c in cards
    )
    return f'<html>{links}<script id="__NEXT_DATA__">{json.dumps(payload)}</script></html>'


def card(game_id="0022600300", away="ATL", home="BOS", status="7:00 pm ET"):
    return {
        "gameId": game_id,
        "gameStatusText": status,
        "awayTeam": {"teamTricode": away},
        "homeTeam": {"teamTricode": home},
    }


class RollingScheduleParserTests(unittest.TestCase):
    def test_daily_feed_count_and_selected_date_are_verified(self):
        day = "2026-11-16"
        parsed = rolling.parse_schedule_page(
            page(day, [card()], announced=1), day, "https://www.nba.com/games?date=" + day)
        self.assertEqual(parsed["expected_count"], 1)
        self.assertEqual(parsed["games"][0]["game_id"], "0022600300")
        self.assertEqual(parsed["games"][0]["time_et"], "7:00 pm ET")

        with self.assertRaisesRegex(rolling.SchedulePageError, "selectedDate"):
            rolling.parse_schedule_page(
                page(day, [card()], selected_date="2026-11-17"), day,
                "https://www.nba.com/games?date=" + day)

    def test_incomplete_cards_fail_against_official_calendar_count(self):
        day = "2026-11-16"
        with self.assertRaisesRegex(rolling.SchedulePageError, "official daily count says 2"):
            rolling.parse_schedule_page(
                page(day, [card()], announced=2), day,
                "https://www.nba.com/games?date=" + day)

    def test_paginated_feed_fails_closed(self):
        day = "2026-11-16"
        with self.assertRaisesRegex(rolling.SchedulePageError, "paginated"):
            rolling.parse_schedule_page(
                page(day, [card()], next_page="another-page"), day,
                "https://www.nba.com/games?date=" + day)

    def test_duplicate_game_and_invalid_team_are_rejected(self):
        day = "2026-11-16"
        with self.assertRaisesRegex(rolling.SchedulePageError, "duplicate official game card"):
            rolling.parse_schedule_page(
                page(day, [card(), card()]), day,
                "https://www.nba.com/games?date=" + day)
        with self.assertRaisesRegex(rolling.SchedulePageError, "invalid official matchup"):
            rolling.parse_schedule_page(
                page(day, [card(away="XXX")]), day,
                "https://www.nba.com/games?date=" + day)

    def test_incidental_game_links_do_not_enter_selected_date_slate(self):
        day = "2026-11-16"
        html = page(day, [card()]) + '<a href="/game/nyk-vs-tor-0022600232/">recap</a>'
        result = rolling.build_rolling_slate(
            {day: html}, date.fromisoformat(day), stamp="2026-11-16T14-00Z",
            games_url_prefix="https://www.nba.com/games?date=", days=1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["slate"]["count"], 1)
        self.assertEqual([g["game_id"] for g in result["games"]], ["0022600300"])

    def test_saved_official_november_16_to_18_pages_have_complete_card_counts(self):
        # These are immutable, previously captured official NBA.com responses. This test
        # exercises the parser against their embedded gameCardFeed, not a live fetch.
        capture_dir = ROOT / "data" / "app" / "refresh" / "2026-11-16T00-57Z"
        dates = ("2026-11-16", "2026-11-17", "2026-11-18")
        pages = {day: (capture_dir / f"games_{day}.html").read_text(encoding="utf-8")
                 for day in dates}
        result = rolling.build_rolling_slate(
            pages, date.fromisoformat(dates[0]), stamp="2026-11-16T00-57Z",
            games_url_prefix="https://www.nba.com/games?date=", days=3)
        self.assertEqual(result["errors"], [])
        self.assertEqual([row["expected"] for row in result["daily_counts"]], [8, 5, 12])
        self.assertEqual([row["parsed"] for row in result["daily_counts"]], [8, 5, 12])
        self.assertEqual(result["slate"]["count"], 25)

    def test_promote_writes_only_the_gated_staged_payload(self):
        day = "2026-11-16"
        result = rolling.build_rolling_slate(
            {day: page(day, [card()])}, date.fromisoformat(day),
            stamp="2026-11-16T14-00Z", games_url_prefix="https://www.nba.com/games?date=", days=1)
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "staged.json"
            target = Path(tmp) / "published.json"
            rolling.write_json_atomic(staged, result["slate"])
            self.assertFalse(target.exists())
            rolling.promote_slate(staged, target)
            self.assertEqual(json.loads(target.read_text()), result["slate"])


if __name__ == "__main__":
    unittest.main()
