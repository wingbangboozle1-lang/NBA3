from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.release_audit import (
    _parse_tip,
    _staged_sources,
    audit_pick_horizon,
    parse_table_rows,
    source_class,
)


class SourceClassificationTests(unittest.TestCase):
    def test_official_domains_are_matched_on_domain_boundaries(self):
        self.assertEqual(source_class("https://www.nba.com/schedule"), "nba_official")
        self.assertEqual(source_class("https://ak-static.cms.nba.com/report.pdf"), "nba_official")
        self.assertEqual(source_class("https://kansspelautoriteit.nl/guidance"), "regulator_or_statute")
        self.assertEqual(source_class("https://www.itl.nist.gov/handbook/"), "statistical_authority")
        self.assertEqual(source_class("https://github.com/example/repo"), "repository_evidence")

    def test_similar_or_insecure_hosts_are_not_promoted_to_official(self):
        self.assertEqual(source_class("https://nba.com.evil.example/report"), "other_https")
        self.assertEqual(source_class("https://notnba.com/report"), "other_https")
        self.assertEqual(source_class("http://www.nba.com/schedule"), "non_https")


class RowParserTests(unittest.TestCase):
    def test_links_are_attached_to_their_own_table_row(self):
        html = """<table><tbody>
        <tr><td>Official row</td><td><a href='https://www.nba.com/schedule'>source</a></td></tr>
        <tr><td>Unverified row</td><td>UNVERIFIED</td></tr>
        </tbody></table>"""
        rows = parse_table_rows(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["links"], ["https://www.nba.com/schedule"])
        self.assertEqual(rows[1]["links"], [])
        self.assertIn("UNVERIFIED", " ".join(rows[1]["text"]))

    def test_pages_staging_parser_surfaces_literal_merge_markers(self):
        # The marker text is built from variables so no source line begins with the
        # literal `<<<<<<<` — that keeps the tree-wide conflict-marker CI guard
        # (CR-8D-05) from tripping on this intentional fixture while still exercising
        # the parser against markers at line start in the *simulated* workflow text.
        open_marker = "<" * 7
        close_marker = ">" * 7
        text = (
            "      - name: Stage\n"
            "        run: |\n"
            "          cp index.html _pages/\n"
            "          cp -r dash _pages/dash\n"
            f"{open_marker} HEAD\n"
            "=======\n"
            f"{close_marker} origin/main\n"
        )
        sources, markers = _staged_sources(text)
        self.assertEqual(sources, ["index.html", "dash"])
        self.assertEqual(len(markers), 3)


class PickHorizonTests(unittest.TestCase):
    def _root(self, generation_time: str) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "data" / "app").mkdir(parents=True)
        (root / "data" / "picks").mkdir(parents=True)
        schedule = {
            "source_url": "https://www.nba.com/schedule?date=2026-11-14",
            "games": [{
                "date": "2026-11-16",
                "time_et": "8:00 PM",
                "away": "POR",
                "home": "MIN",
                "game_id": "0022600250",
                "nba_game_url": "https://www.nba.com/game/por-vs-min-0022600250",
            }],
        }
        picks = {
            "generated_on": generation_time,
            "max_lookahead_days": 3,
            "picks": [{"date": "2026-11-16", "matchup": "POR @ MIN"}],
        }
        (root / "data" / "app" / "official_slate.json").write_text(json.dumps(schedule), encoding="utf-8")
        (root / "data" / "picks" / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
        return root

    def test_exactly_72_hours_is_allowed(self):
        # 2026-11-16 8:00 PM Eastern is 2026-11-17 01:00 UTC.
        self.assertEqual(
            _parse_tip("2026-11-16", "8:00 PM").isoformat(),
            "2026-11-17T01:00:00+00:00",
        )
        result = audit_pick_horizon(self._root("2026-11-14T01:00:00Z"))
        self.assertEqual(result["records"][0]["hours_ahead"], 72.0)
        self.assertFalse(any(x["code"] == "PICK_OUTSIDE_MAX_HORIZON" for x in result["issues"]))

    def test_one_second_over_72_hours_is_flagged(self):
        result = audit_pick_horizon(self._root("2026-11-14T00:59:59Z"))
        outside = [x for x in result["issues"] if x["code"] == "PICK_OUTSIDE_MAX_HORIZON"]
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0]["matchup"], "POR @ MIN")
        self.assertGreater(outside[0]["hours_ahead"], 72.0)

    def test_legacy_team_code_is_only_used_for_matching(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "data" / "app").mkdir(parents=True)
        (root / "data" / "picks").mkdir(parents=True)
        schedule = {
            "source_url": "https://www.nba.com/schedule",
            "games": [{"date": "2026-11-14", "time_et": "7:00 PM", "away": "BKN", "home": "MEM",
                       "game_id": "0022600234", "nba_game_url": "https://www.nba.com/game/bkn-vs-mem-0022600234"}],
        }
        picks = {"generated_on": "2026-11-14T00:00:00Z", "picks": [{"date": "2026-11-14", "matchup": "BRK @ MEM"}]}
        (root / "data" / "app" / "official_slate.json").write_text(json.dumps(schedule), encoding="utf-8")
        (root / "data" / "picks" / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
        result = audit_pick_horizon(root)
        self.assertEqual(result["records"][0]["status"], "WITHIN_HORIZON")
        self.assertEqual(result["records"][0]["matchup"], "BKN @ MEM")
        self.assertFalse(any(x["code"] == "PICK_NOT_MATCHED_TO_OFFICIAL_SCHEDULE" for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
