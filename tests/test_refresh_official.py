"""Offline tests for scripts/refresh_official.py (session arena/81800928-nba3).

No network: the fetcher is replaced by a fake that serves fixtures or raises.
Run: python3 -m unittest tests/test_refresh_official.py
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import refresh_official as ro  # noqa: E402


def index_html(*names):
    return "".join(
        f'<a href="https://ak-static.cms.nba.com/referee/injury/{n}">x</a>' for n in names)


class NewestReportTests(unittest.TestCase):
    def test_midnight_is_not_the_newest_over_one_pm(self):
        # The old string sort picked 12_00AM over 01_00PM (because "12" > "01").
        html = index_html("Injury-Report_2026-11-15_12_00AM.pdf",
                          "Injury-Report_2026-11-15_01_00PM.pdf")
        self.assertEqual(ro.newest_report(html), ("2026-11-15", "01", "00", "PM"))

    def test_twelve_thirty_pm_is_older_than_one_pm(self):
        html = index_html("Injury-Report_2026-11-15_12_30PM.pdf",
                          "Injury-Report_2026-11-15_01_00PM.pdf")
        self.assertEqual(ro.newest_report(html), ("2026-11-15", "01", "00", "PM"))

    def test_later_date_wins_regardless_of_clock(self):
        html = index_html("Injury-Report_2026-11-15_11_45AM.pdf",
                          "Injury-Report_2026-11-16_12_00AM.pdf")
        self.assertEqual(ro.newest_report(html)[0], "2026-11-16")

    def test_no_links_returns_none(self):
        self.assertIsNone(ro.newest_report("<html>nothing</html>"))

    def test_report_time_is_12_hour_aware(self):
        self.assertEqual(ro.report_time("2026-11-15", "12", "00", "AM").hour, 0)
        self.assertEqual(ro.report_time("2026-11-15", "12", "15", "PM").hour, 12)
        self.assertEqual(ro.report_time("2026-11-15", "01", "00", "PM").hour, 13)


class EasternDateTests(unittest.TestCase):
    def test_utc_early_morning_is_previous_eastern_day(self):
        # 02:00 UTC on 11/15 is 21:00 EST on 11/14 (US DST ended 2026-11-01).
        now = datetime(2026, 11, 15, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(ro.et_today(now).isoformat(), "2026-11-14")

    def test_evening_utc_is_same_eastern_day(self):
        now = datetime(2026, 11, 15, 23, 15, tzinfo=timezone.utc)
        self.assertEqual(ro.et_today(now).isoformat(), "2026-11-15")


class FetcherTests(unittest.TestCase):
    def test_failed_url_is_recorded_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("2026-11-15T00-00Z")
            err = urllib.error.HTTPError("https://x", 403, "Forbidden", {}, None)
            with mock.patch.object(ro.urllib.request, "urlopen", side_effect=err), \
                    mock.patch.object(ro.time, "sleep"):
                out = f.get("https://x", os.path.join(td, "a.html"), required=True,
                            label="test")
            self.assertIsNone(out)
            self.assertEqual(len(f.errors), 1)
            self.assertTrue(f.errors[0]["required"])
            self.assertEqual(f.errors[0]["attempts"], ro.RETRIES)
            self.assertIn("403", f.errors[0]["error"])
            self.assertEqual(f.artifacts, [])

    def test_success_records_sha_and_retrieval_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("2026-11-15T00-00Z")
            resp = mock.MagicMock()
            resp.read.return_value = b"hello"
            resp.__enter__.return_value = resp
            with mock.patch.object(ro.urllib.request, "urlopen", return_value=resp):
                data = f.get("https://x", os.path.join(td, "a.html"))
            self.assertEqual(data, b"hello")
            art = f.artifacts[0]
            self.assertEqual(art["retrieved_utc"], "2026-11-15T00-00Z")
            self.assertEqual(len(art["sha256"]), 64)
            self.assertEqual(f.errors, [])

    def test_retry_then_success(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("s")
            ok = mock.MagicMock()
            ok.read.return_value = b"ok"
            ok.__enter__.return_value = ok
            side = [OSError("reset"), ok]
            with mock.patch.object(ro.urllib.request, "urlopen", side_effect=side), \
                    mock.patch.object(ro.time, "sleep"):
                self.assertEqual(f.get("https://x", os.path.join(td, "b")), b"ok")
            self.assertEqual(f.errors, [])


class MainFlowTests(unittest.TestCase):
    """main() with the network replaced: a dead injury index must stop before any rebuild."""

    def test_dead_injury_index_returns_2_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ro, "APP", td), \
                    mock.patch.object(ro.Fetcher, "get", lambda self, *a, **k: (
                        self.errors.append({"url": a[0], "label": k.get("label"),
                                            "required": True, "error": "boom",
                                            "attempts": 3}) or None)), \
                    mock.patch.object(ro.subprocess, "run") as run, \
                    mock.patch.object(ro.sys, "argv", ["refresh_official.py",
                                                       "--stamp", "T1"]):
                code = ro.main()
            self.assertEqual(code, 2)
            run.assert_not_called()
            import json
            with open(os.path.join(td, "refresh", "T1", "manifest.json")) as fh:
                man = json.load(fh)
            self.assertEqual(man["errors"][0]["label"], "injury index")

    def test_required_failure_after_index_refuses_rebuild(self):
        """Index works, newest PDF fails: exit 2, gates and rebuild are never run."""
        index = index_html("Injury-Report_2026-11-15_01_00PM.pdf").encode()

        def fake_get(self, url, dest, required=False, label=None):
            if url == ro.INJ_INDEX:
                self.artifacts.append({"url": url})
                return index
            self.errors.append({"url": url, "label": label, "required": required,
                                "error": "403", "attempts": 3})
            return None

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ro, "APP", td), \
                    mock.patch.object(ro.Fetcher, "get", fake_get), \
                    mock.patch.object(ro.subprocess, "run") as run, \
                    mock.patch.object(ro.sys, "argv", ["refresh_official.py",
                                                       "--stamp", "T2"]):
                code = ro.main()
            self.assertEqual(code, 2)
            run.assert_not_called()


def _card(away, home, gid, day):
    # the shape of a real game card on an official games page (checked on the committed captures)
    return (f'<a href="/game/{away.lower()}-vs-{home.lower()}-{gid}" data-track="click" '
            f'data-type="card" data-content="{away} @ {home}, {day}" class="GameCard">x</a>')


class SlatePromotionTests(unittest.TestCase):
    """Session c449d46a: the slate comes from game CARDS on each date's own page only."""

    def test_editorial_link_is_not_a_game(self):
        # A newsletter embed on a date page links a game with a trailing slash, no card.
        pages = {"2026-11-16": _card("ATL", "MIL", "0022600001", "2026-11-16")
                 + '<a href="https://www.nba.com/game/dal-vs-cle-0022600232/">story</a>'}
        rows, excluded = ro.promote_slate_rows(pages)
        self.assertEqual([r["game_id"] for r in rows], ["0022600001"])
        self.assertEqual(excluded, [])

    def test_card_for_another_date_is_ignored(self):
        pages = {"2026-11-16": _card("DAL", "CLE", "0022600232", "2026-11-14")}
        rows, _ = ro.promote_slate_rows(pages)
        self.assertEqual(rows, [])

    def test_game_card_on_two_date_pages_is_excluded_not_guessed(self):
        pages = {"2026-11-16": _card("ATL", "MIL", "0022600002", "2026-11-16"),
                 "2026-11-17": _card("ATL", "MIL", "0022600002", "2026-11-17")}
        rows, excluded = ro.promote_slate_rows(pages)
        # each card matches its own page date, so this is the two-date case
        self.assertEqual(rows, [])
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["reason"], "game id on more than one date page")

    def test_href_teams_must_match_card_teams(self):
        html = ('<a href="/game/atl-vs-mil-0022600003" data-content="ATL @ BOS, 2026-11-16">x</a>')
        rows, excluded = ro.promote_slate_rows({"2026-11-16": html})
        self.assertEqual(rows, [])
        self.assertEqual(excluded[0]["reason"], "href teams differ from card teams")

    def test_rows_are_sorted_and_carry_the_card_urls(self):
        pages = {"2026-11-16": _card("NYK", "IND", "0022600005", "2026-11-16")
                 + _card("ATL", "MIL", "0022600004", "2026-11-16")}
        rows, _ = ro.promote_slate_rows(pages)
        self.assertEqual([r["game_id"] for r in rows], ["0022600004", "0022600005"])
        self.assertEqual(rows[0]["game_url"], "https://www.nba.com/game/atl-vs-mil-0022600004")
        self.assertEqual(rows[0]["source"], "https://www.nba.com/games?date=2026-11-16")


class CommittedCaptureSlateTests(unittest.TestCase):
    """The committed 2026-11-16T00-57Z capture reproduces the verified 34-game slate."""

    CAPTURE = os.path.join(ROOT, "data", "app", "refresh", "2026-11-16T00-57Z")

    def _pages(self):
        pages = {}
        for d in ("2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18"):
            with open(os.path.join(self.CAPTURE, f"games_{d}.html"), encoding="utf-8",
                      errors="replace") as fh:
                pages[d] = fh.read()
        return pages

    def test_capture_gives_the_verified_34_games_and_no_phantom_rows(self):
        if not os.path.isdir(self.CAPTURE):
            self.skipTest("committed capture not present")
        rows, excluded = ro.promote_slate_rows(self._pages())
        got = {(r["date"], r["game_id"], r["away"], r["home"]) for r in rows}
        self.assertEqual(len(rows), 34)
        self.assertEqual(excluded, [])
        self.assertFalse(any(r["game_id"] == "0022600232" for r in rows))
        verified = json.load(open(os.path.join(ROOT, "data", "app", "official_slate_1115_1118.json"),
                                  encoding="utf-8"))["games"]
        want = {(g["date"], g["game_id"], g["away"], g["home"]) for g in verified}
        self.assertEqual(got, want)

    def test_published_slate_matches_the_promotion(self):
        # Roll-safe (session arena/4c69ab99-nba3): the published slate must equal the
        # promotion of the NEWEST committed capture, not of any one frozen capture. The
        # scheduled refresh rolls the window forward every run; pinning the published file
        # to the 2026-11-16T00-57Z capture made every later run fail this test after its
        # fetch step had already rolled the window (run 43925193575 failed exactly here).
        path = os.path.join(ROOT, "data", "app", "official_slate_current.json")
        published = json.load(open(path, encoding="utf-8"))
        refresh_root = os.path.join(ROOT, "data", "app", "refresh")
        manifests = []
        if os.path.isdir(refresh_root):
            for name in os.listdir(refresh_root):
                mp = os.path.join(refresh_root, name, "manifest.json")
                if os.path.exists(mp):
                    manifests.append((json.load(open(mp, encoding="utf-8")), name))
        rows = []
        if manifests:
            man, name = max(manifests, key=lambda t: t[0].get("stamp", ""))
            base = os.path.join(refresh_root, name)
            today = datetime.strptime(man["today_et"], "%Y-%m-%d").date()
            pages = {}
            for off in range(0, 4):
                d = (today + timedelta(days=off)).isoformat()
                page = os.path.join(base, f"games_{d}.html")
                if os.path.exists(page):
                    pages[d] = open(page, encoding="utf-8", errors="replace").read()
            rows, _ = ro.promote_slate_rows(pages)
        if rows:
            self.assertEqual(published["games"], rows,
                             "the published slate is not the promotion of the newest "
                             "committed capture")
        self.assertEqual(published["count"], len(published["games"]))
        self.assertEqual(len({g["game_id"] for g in published["games"]}), published["count"])


class FinalsIngestTests(unittest.TestCase):
    """Game-card finals ingestion (merged implementation: scripts/gamecard_feed.py).

    The official games page embeds a card-feed JSON with the final score and the
    per-period scores; results_feed.py ingest --capture-dir parses those cards into the
    per-game result feed so it stays current with no manual input. Rows failing the
    period-sum identity are RECORDED and rejected — never repaired (no-inference rule).
    """

    APP = os.path.join(ROOT, "data", "app")
    GAMES_1114 = os.path.join(APP, "refresh", "2026-11-16T00-57Z", "games_2026-11-14.html")
    GAMES_1115 = os.path.join(APP, "refresh", "2026-11-16T00-57Z", "games_2026-11-15.html")

    def test_committed_11_14_page_matches_the_feed_rows(self):
        import gamecard_feed
        if not os.path.exists(self.GAMES_1114):
            self.skipTest("committed capture not present")
        html = open(self.GAMES_1114, encoding="utf-8", errors="replace").read()
        rows, rejected = gamecard_feed.finished_rows(gamecard_feed.parse_games_page(html))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rejected, [])
        feed = json.load(open(os.path.join(self.APP, "results_feed.json"), encoding="utf-8"))
        by_key = {(g["date"], g["away"], g["home"]): g for g in feed["games"]}
        for r in rows:
            f = by_key[(r["date"], r["away"], r["home"])]
            self.assertEqual((r["away_pts"], r["home_pts"]),
                             (f["away_pts"], f["home_pts"]))
            self.assertEqual(r["away_q"], [f[f"away_q{i + 1}"] for i in range(len(r["away_q"]))])

    def test_in_progress_game_is_never_returned(self):
        import gamecard_feed
        if not os.path.exists(self.GAMES_1115):
            self.skipTest("committed capture not present")
        html = open(self.GAMES_1115, encoding="utf-8", errors="replace").read()
        rows, _ = gamecard_feed.finished_rows(gamecard_feed.parse_games_page(html))
        # 0022600241 (NYK @ TOR) was Q3 1:27 when this page was captured
        self.assertNotIn("0022600241", {r["game_id"] for r in rows})

    def test_period_sum_mismatch_is_rejected_never_fixed(self):
        import gamecard_feed
        bad = {"gameId": "0022600902", "gameStatusText": "Final",
               "awayTeam": {"teamTricode": "ATL", "score": 113,
                            "periods": [{"period": 1, "score": 18}, {"period": 2, "score": 37},
                                        {"period": 3, "score": 32}, {"period": 4, "score": 26}]},
               "homeTeam": {"teamTricode": "MIL", "score": 106,
                            "periods": [{"period": 1, "score": 37}, {"period": 2, "score": 16},
                                        {"period": 3, "score": 37}, {"period": 4, "score": 26}]}}
        rows, rejected = gamecard_feed.finished_rows([bad])
        self.assertEqual(rows, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("do not equal", rejected[0]["reason"])


class GateCallTests(unittest.TestCase):
    def test_freshness_gate_accepts_the_arguments_we_pass(self):
        # Regression: the refresh used to pass --manifest/--json-out, which the gate rejects.
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py"),
                            "--help"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("--manifest", r.stdout)


if __name__ == "__main__":
    unittest.main()
