"""Offline fail-closed tests for one scheduled refresh capture.

Fixtures are synthetic. They prove provenance and gate behavior only; they are not
published NBA data and do not assert any real-game, standings, or team-stat value.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_preflight as gate  # noqa: E402
import rolling_promote  # noqa: E402


STAMP = "2026-11-16T14-00Z"
RUN_TIME = "2026-11-16T14:00:00Z"


def schedule_html(day, away, home, game_id):
    payload = {
        "props": {"pageProps": {
            "selectedDate": day,
            "allGamesInCurrentYear": {day[:4]: {day: 1}},
            "gameCardFeed": {
                "nextPageToken": None,
                "modules": [{"cards": [{"cardData": {
                    "gameId": game_id,
                    "gameStatusText": "7:00 pm ET",
                    "awayTeam": {"teamTricode": away},
                    "homeTeam": {"teamTricode": home},
                }}]}],
            },
        }},
    }
    link = f'<a href="/game/{away.lower()}-vs-{home.lower()}-{game_id}/">game</a>'
    return f'<html>{link}<script id="__NEXT_DATA__">{json.dumps(payload)}</script></html>'


class RefreshPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = self.root / "data" / "app"
        self.stamp = STAMP
        self.out = self.app / "refresh" / self.stamp
        self.out.mkdir(parents=True)
        self.artifacts = []
        self.schedule_pages = {}

        def capture(url, relative, body):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            self.artifacts.append({
                "url": url,
                "retrieved_utc": RUN_TIME,
                "run_stamp": self.stamp,
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "file": relative,
            })

        injury_name = "Injury-Report_2026-11-16_12_00PM.pdf"
        capture(gate.INJ_INDEX,
                f"data/app/refresh/{self.stamp}/injury_index.html",
                (f'<a href="{gate.INJ_CDN}{injury_name}">latest PDF</a>').encode())
        capture(gate.INJ_CDN + injury_name,
                f"data/app/refresh/{self.stamp}/{injury_name}", b"%PDF-1.4\nsynthetic fixture")

        matchups = [("ATL", "BOS"), ("ATL", "CHI"), ("ATL", "CLE"), ("ATL", "DAL")]
        for offset, (away, home) in enumerate(matchups):
            day = (date(2026, 11, 16).fromordinal(date(2026, 11, 16).toordinal() + offset)).isoformat()
            game_id = f"00226003{offset:02d}"
            html = schedule_html(day, away, home, game_id)
            self.schedule_pages[day] = html
            capture(gate.GAMES + day,
                    f"data/app/refresh/{self.stamp}/games_{day}.html", html.encode())

        capture(gate.STANDINGS,
                f"data/app/refresh/{self.stamp}/standings.html",
                b"<html>Official NBA standings page fixture shell</html>")
        for i, url in enumerate(gate.TEAM_PAGES.values()):
            capture(url, f"data/app/refresh/{self.stamp}/teams_{i}.html",
                    b"<html>Official NBA team stats page fixture shell</html>")

        slate_result = rolling_promote.build_rolling_slate(
            self.schedule_pages, date(2026, 11, 16), stamp=self.stamp,
            games_url_prefix=gate.GAMES, days=4)
        self.assertEqual(slate_result["errors"], [])
        rolling_promote.write_json_atomic(self.out / "promoted_slate.json", slate_result["slate"])

        manifest = {
            "stamp": self.stamp,
            "started_utc": RUN_TIME,
            "finished_utc": RUN_TIME,
            "today_et": "2026-11-16",
            "newest_injury_report": "2026-11-16-12-00PM",
            "artifacts": self.artifacts,
            "errors": [],
            "gamebooks": 0,
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def by_id(self, report):
        return {item["id"]: item for item in report["gates"]}

    def test_capture_integrity_and_complete_daily_schedule_are_checked(self):
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        checks = self.by_id(report)
        for gate_id in ("P1_manifest", "P2_integrity", "P3_sources", "P4_injury_current", "P5_slate"):
            self.assertTrue(checks[gate_id]["passed"], checks[gate_id]["detail"])
        self.assertEqual(report["slate_preview"]["count"], 4)
        self.assertEqual([d["parsed"] for d in report["slate_preview"]["daily_counts"]], [1, 1, 1, 1])
        # Current team-stat/standings shells are not parsed 30-team model inputs.
        self.assertFalse(checks["P6_standings"]["passed"])
        self.assertFalse(checks["P7_team_stats"]["passed"])
        self.assertFalse(report["pass"])

    def test_hash_mismatch_fails_even_when_source_url_is_official(self):
        injury_path = self.out / "Injury-Report_2026-11-16_12_00PM.pdf"
        injury_path.write_bytes(b"%PDF-1.4\nchanged after manifest")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        checks = self.by_id(report)
        self.assertFalse(checks["P2_integrity"]["passed"])
        self.assertFalse(report["pass"])

    def test_malformed_or_escaping_artifact_paths_fail_closed(self):
        manifest_path = self.out / "manifest.json"
        for bad_path in ("../../outside", "bad\x00path"):
            with self.subTest(path=bad_path):
                manifest = json.loads(manifest_path.read_text())
                manifest["artifacts"][0]["file"] = bad_path
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                report = gate.validate(self.stamp, root=self.root, app=self.app)
                self.assertFalse(self.by_id(report)["P2_integrity"]["passed"])
                self.assertFalse(report["pass"])

    def test_malformed_source_url_is_a_failed_gate_not_an_exception(self):
        manifest_path = self.out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"][0]["url"] = "https://[not-a-valid-ipv6-host"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P2_integrity"]["passed"])
        self.assertFalse(report["pass"])

    def test_missing_future_schedule_page_fails_closed(self):
        manifest_path = self.out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        missing_url = gate.GAMES + "2026-11-19"
        manifest["artifacts"] = [a for a in manifest["artifacts"] if a["url"] != missing_url]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (self.out / "games_2026-11-19.html").unlink()
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        checks = self.by_id(report)
        self.assertFalse(checks["P3_sources"]["passed"])
        self.assertFalse(checks["P5_slate"]["passed"])
        self.assertFalse(report["pass"])

    def test_staged_slate_must_equal_current_official_cards(self):
        staged_path = self.out / "promoted_slate.json"
        staged = json.loads(staged_path.read_text())
        staged["games"][0]["home"] = "NYK"
        staged_path.write_text(json.dumps(staged), encoding="utf-8")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P5_slate"]["passed"])
        self.assertFalse(report["pass"])

    def test_index_newest_must_match_the_pdf_named_by_manifest(self):
        manifest_path = self.out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["newest_injury_report"] = "2026-11-16-11-45AM"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P4_injury_current"]["passed"])
        self.assertFalse(report["pass"])

    def test_required_standings_source_is_not_optional(self):
        manifest_path = self.out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"] = [a for a in manifest["artifacts"] if a["url"] != gate.STANDINGS]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (self.out / "standings.html").unlink()
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P3_sources"]["passed"])
        self.assertFalse(report["pass"])

    def test_parsed_standings_must_bind_to_this_runs_raw_page_hash(self):
        manifest = json.loads((self.out / "manifest.json").read_text())
        rows = [{"team": team, "w": 1, "l": 0} for team in sorted(gate.TEAM_CODES)]
        derived = {"retrieved_utc": self.stamp, "source_url": gate.STANDINGS,
                   "source_sha256": "0" * 64, "rows": rows}
        path = self.out / "derived" / "official_standings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(derived), encoding="utf-8")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P6_standings"]["passed"])
        self.assertIn("hash", self.by_id(report)["P6_standings"]["detail"])

    def test_each_team_stats_page_must_bind_to_its_current_raw_hash(self):
        manifest = json.loads((self.out / "manifest.json").read_text())
        hashes = {artifact["url"]: artifact["sha256"] for artifact in manifest["artifacts"]}
        columns = {
            "traditional": ["team", "gp", "w", "l", "pts"],
            "opponent": ["team", "gp", "w", "l", "opp_pts"],
            "advanced": ["team", "gp", "w", "l", "off_rtg", "def_rtg", "net_rtg", "pace", "poss"],
        }
        pages = {}
        for name, url in gate.TEAM_PAGES.items():
            page_columns = columns[name]
            value = 100 if name != "advanced" else 1
            rows = [[team, 1, 1, 0] + [value] * (len(page_columns) - 4)
                    for team in sorted(gate.TEAM_CODES)]
            pages[name] = {"source_url": url,
                           "source_sha256": hashes[url] if name != "opponent" else "0" * 64,
                           "columns": page_columns, "rows": rows}
        derived = {"retrieved_utc": self.stamp, "pages": pages}
        path = self.out / "derived" / "official_team_stats.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(derived), encoding="utf-8")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P7_team_stats"]["passed"])
        self.assertIn("hash", self.by_id(report)["P7_team_stats"]["detail"])

    def test_artifact_retrieval_must_fall_within_the_current_run_interval(self):
        manifest_path = self.out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"][0]["retrieved_utc"] = "2026-11-16T14:00:01Z"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report = gate.validate(self.stamp, root=self.root, app=self.app)
        self.assertFalse(self.by_id(report)["P2_integrity"]["passed"])
        self.assertFalse(report["pass"])


if __name__ == "__main__":
    unittest.main()
