"""Tests for session b1ce1334: 11/19 official capture (injury transcripts, diff, finals, slate) and subsite."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import capture_b1ce1334 as cap  # noqa: E402
import build_b1ce1334 as site  # noqa: E402


class InjuryTranscriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.delta = cap.build_outputs()
        cls.rev = cls.out["revisions"]

    def test_counts_per_revision_are_pinned_to_the_transcript(self):
        self.assertEqual(self.rev["1200AM"]["counts"], {"player_rows": 23, "team_rows": 8, "unparsed": 13})
        self.assertEqual(self.rev["1215AM"]["counts"], {"player_rows": 23, "team_rows": 8, "unparsed": 13})
        self.assertEqual(self.rev["1230AM"]["counts"], {"player_rows": 23, "team_rows": 8, "unparsed": 11})

    def test_teamless_rows_stay_unattributed(self):
        rows = {r["player"]: r for r in self.rev["1230AM"]["player_rows"]}
        self.assertIsNone(rows["Kuminga, Jonathan"]["team"])
        self.assertTrue(rows["Kuminga, Jonathan"]["team_attribution"].startswith("UNATTRIBUTED"))
        self.assertTrue(rows["Pullin, Zyon"]["team_attribution"].startswith("UNATTRIBUTED"))

    def test_layout_broken_lines_get_no_status(self):
        for rev in ("1200AM", "1215AM", "1230AM"):
            for u in self.rev[rev]["unparsed"]:
                self.assertIn("reason", u)
                self.assertNotIn("status", u)

    def test_consecutive_revisions_show_no_cleanly_parsed_status_change(self):
        for pair in self.delta["pairs"]:
            self.assertEqual(pair["status_changes"], [], pair["from"] + "->" + pair["to"])
            self.assertEqual(pair["added_player_rows"], [])
            self.assertEqual(pair["removed_player_rows"], [])

    def test_verbatim_diff_is_nonzero_only_in_layout_and_titles(self):
        # 12:00->12:15 differs only in the title timestamps and the separator style; 12:15->12:30 also in the broken block.
        d = {p["from"] + ">" + p["to"]: p for p in self.delta["pairs"]}
        self.assertEqual(d["1200AM>1215AM"]["verbatim_lines_differing"], 5)
        self.assertEqual(d["1215AM>1230AM"]["verbatim_lines_differing"], 17)

    def test_diff_detects_synthetic_status_change_and_add_remove(self):
        prev = {"player_rows": [
            {"matchup": "A@B", "team": "T1", "player": "X", "status": "Questionable", "reason": "r1"},
            {"matchup": "A@B", "team": "T1", "player": "Y", "status": "Out", "reason": "r2"}],
            "team_rows": []}
        cur = {"player_rows": [
            {"matchup": "A@B", "team": "T1", "player": "X", "status": "Out", "reason": "r1"},
            {"matchup": "A@B", "team": "T1", "player": "Z", "status": "Available", "reason": "r3"}],
            "team_rows": []}
        d = cap.diff_pair(prev, cur)
        self.assertEqual([c["player"] for c in d["status_changes"]], ["X"])
        self.assertEqual(d["status_changes"][0]["from"]["status"], "Questionable")
        self.assertEqual(d["status_changes"][0]["to"]["status"], "Out")
        self.assertEqual([a["player"] for a in d["added_player_rows"]], ["Z"])
        self.assertEqual([r["player"] for r in d["removed_player_rows"]], ["Y"])

    def test_parser_refuses_to_guess_a_status(self):
        text = "| 11/19/2026 | 08:00 (ET) | A@B | Team | Doe, J | Maybe | Reason |\n"
        p = cap.parse_transcript(text)
        self.assertEqual(p["player_rows"], [])
        self.assertEqual(len(p["unparsed"]), 1)

    def test_inputs_and_checksums_pass(self):
        self.assertTrue(cap.check_inputs())

    def test_pdf_matchups_all_appear_in_the_official_slate(self):
        xc = cap.cross_check_pdf_vs_slate(cap.parse_transcript(
            (ROOT / "data/rounds/2026-11-19/raw/injury_2026-11-19_1200AM_raw.md").read_text(encoding="utf-8")))
        self.assertEqual(xc["not_in_slate"], [])
        self.assertIn("CHA@ATL", xc["pdf_matchups"])


class ResultsAndSlateTests(unittest.TestCase):
    def setUp(self):
        self.res = json.loads((ROOT / "data/rounds/2026-11-19/results_2026-11-18.json").read_text(encoding="utf-8"))
        self.slate = json.loads((ROOT / "data/rounds/2026-11-19/slate_2026-11-19_22.json").read_text(encoding="utf-8"))

    def test_twelve_final_games_with_scores_and_unverified_quarters(self):
        games = self.res["games"]
        self.assertEqual(len(games), 12)
        for g in games:
            self.assertEqual(g["status"], "Final")
            self.assertIsInstance(g["away_score"], int)
            self.assertIsInstance(g["home_score"], int)
            self.assertEqual(g["quarter_scores"], "UNVERIFIED")
            self.assertTrue(g["source_urls"])

    def test_winner_matches_score(self):
        for g in self.res["games"]:
            w = g["away"] if g["away_score"] > g["home_score"] else g["home"]
            self.assertEqual(g["winner"], w, g["game_id"])

    def test_game_ids_are_unique_and_slate_has_26_games(self):
        ids = [g["game_id"] for d in self.slate["days"] for g in d["games"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 26)

    def test_printed_day_count_matches_listed_games(self):
        for d in self.slate["days"]:
            if d["printed_game_count"] is not None:
                self.assertEqual(d["printed_game_count"], len(d["games"]), d["date"])


class SubsiteTests(unittest.TestCase):
    def test_every_table_row_has_an_official_link_and_no_broken_internal_links(self):
        pages = site.build()
        self.assertTrue(site.check_site(pages))

    def test_committed_pages_match_the_build(self):
        pages = site.build()
        for name, text in pages.items():
            self.assertEqual((ROOT / "b1ce1334" / f"{name}.html").read_text(encoding="utf-8"), text, name)

    def test_injuries_banner_shows_revision_and_retrieval_time(self):
        text = (ROOT / "b1ce1334" / "injuries.html").read_text(encoding="utf-8")
        self.assertIn("12:30 AM", text)
        self.assertIn("Retrieved:", text)
        self.assertIn("2026-11-19T05:44:01Z", text)


if __name__ == "__main__":
    unittest.main()
