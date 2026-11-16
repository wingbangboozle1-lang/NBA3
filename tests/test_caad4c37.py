"""Offline replay checks for session arena/caad4c37-nba3.

Everything here runs without network: the scripts parse transcriptions that are already committed,
so a failure means a committed artefact really changed.

Run: python3 -m unittest tests/test_caad4c37.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "data" / "arena_caad4c37"
OUT = ROOT / "arena_caad4c37"


def _json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


class TestResultFeedQuarters(unittest.TestCase):
    def setUp(self):
        import quarters_caad4c37 as q
        self.q = q
        self.feed = _json(DATA / "result_feed_quarters.json")

    def test_artefact_reproduces_from_committed_transcriptions(self):
        self.assertEqual(self.feed, self.q.build())

    def test_one_row_per_game_and_all_four_fields_present(self):
        for g in self.feed["games"]:
            for field in ("date", "away", "home", "away_pts", "home_pts"):
                self.assertIn(field, g, f"{g.get('date')} missing {field}")
            self.assertIn("away_quarters", g)
            self.assertIn("home_quarters", g)
        self.assertEqual(self.feed["counts"]["games"], 14)

    def test_no_quarter_value_is_inferred(self):
        """A quarter list is either None or a printed row that sums to the printed final."""
        for g in self.feed["games"]:
            for side in ("away_quarters", "home_quarters"):
                qs = g[side]
                if qs is None:
                    continue
                self.assertTrue(all(isinstance(x, int) for x in qs), f"{g['date']} {side}")
                self.assertTrue(len(qs) in (4, 5), f"{g['date']} {side} length {len(qs)}")

    def test_accepted_readings_always_sum_to_the_final_of_record(self):
        for g in self.feed["games"]:
            pts = {"away_quarters": g["away_pts"], "home_quarters": g["home_pts"]}
            for side, qs in (("away_quarters", g["away_quarters"]),
                             ("home_quarters", g["home_quarters"])):
                if qs is None:
                    self.assertIn(f"{side.split('_')[0]}_quarters_note", g,
                                  f"{g['date']} {side} is blank with no reason recorded")
                    continue
                self.assertEqual(sum(qs), pts[side],
                                 f"{g['date']} {side} {qs} does not sum to {pts[side]}")

    def test_every_row_links_an_official_game_book_and_scoreboard(self):
        for g in self.feed["games"]:
            self.assertIn("statsdmz.nba.com/pdfs/", g["gamebook_source"], g["date"])
            self.assertTrue(g["scoreboard_source"].startswith("https://www.nba.com/games?date="),
                            g["date"])

    def test_known_blank_team_sides_are_exactly_three(self):
        blanks = [(g["date"], side.split("_")[0])
                  for g in self.feed["games"]
                  for side in ("away_quarters", "home_quarters") if g[side] is None]
        self.assertEqual(sorted(blanks),
                         [("2026-11-13", "away"), ("2026-11-13", "away"), ("2026-11-13", "home")])
        self.assertEqual(self.feed["counts"]["partial"], 3)

    def test_parser_rejects_a_row_that_fails_its_own_arithmetic(self):
        readings = self.q.parse_periods("| SCORE BY PERIOD | 1 | 2 | 3 | 4 | FINAL |\n"
                                        "| MAGIC | 33 | 30 | 32 | 33 | 107 |")
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]["status"], "sum_mismatch")
        self.assertEqual(self.q.choose(readings, "ORL", 107)["verified"], False)

    def test_parser_accepts_a_consistent_row_with_an_ot_column(self):
        readings = self.q.parse_periods("| SCORE BY PERIOD | 1 | 2 | 3 | 4 | OT1 | FINAL |\n"
                                        "| Hawks | 24 | 29 | 30 | 27 | 7 | 117 |")
        self.assertEqual(readings[0]["quarters"], [24, 29, 30, 27, 7])
        self.assertEqual(self.q.choose(readings, "ATL", 117)["quarters"], [24, 29, 30, 27, 7])


class TestInjuryArchive(unittest.TestCase):
    def setUp(self):
        import capture_caad4c37 as c
        self.c = c
        self.index = _json(DATA / "injuries" / "archive_index.json")
        self.deltas = _json(DATA / "injuries" / "deltas.json")

    def test_artefacts_reproduce_from_committed_reports(self):
        built_index, built_deltas = self.c.build()
        self.assertEqual(self.index, built_index)
        self.assertEqual(self.deltas, built_deltas)

    def test_every_stored_report_carries_both_timestamps(self):
        for f in self.index["files"]:
            self.assertTrue(f["revision_time_et"].startswith("11/15/26"), f["stamp"])
            self.assertTrue(f["retrieved_utc"].endswith("Z"), f["stamp"])
            self.assertTrue(f["source_url"].startswith(
                "https://ak-static.cms.nba.com/referee/injury/Injury-Report_"), f["stamp"])

    def test_newest_stored_report_is_the_newest_on_the_official_index(self):
        self.assertEqual(self.index["newest_known_on_index"]["stamp"], "2026-11-15_09_00PM")
        self.assertEqual(self.index["files"][-1]["stamp"], "2026-11-15_09_00PM")

    def test_consecutive_pair_is_really_consecutive_and_shows_no_change(self):
        cons = [d for d in self.deltas["deltas"] if d["consecutive"]]
        self.assertEqual(len(cons), 1)
        d = cons[0]
        self.assertEqual((d["from_stamp"], d["to_stamp"]),
                         ("2026-11-15_08_45PM", "2026-11-15_09_00PM"))
        c = d["counts"]
        self.assertEqual((c["status_changes"], c["reason_changes"], c["added"], c["removed"]),
                         (0, 0, 0, 0))

    def test_gap_delta_to_the_published_baseline_is_recorded_not_hidden(self):
        gap = [d for d in self.deltas["deltas"] if not d["consecutive"]]
        self.assertEqual(len(gap), 1)
        d = gap[0]
        self.assertEqual(d["from_stamp"], "2026-11-15_06_15AM")
        self.assertEqual(d["counts"]["status_changes"], 21)
        self.assertIn("gap_note", d)
        self.assertEqual(d["slate_coverage"]["game_dates_added"], [])

    def test_player_matching_is_not_fuzzy(self):
        """'Embid' vs 'Embiid' must appear as a remove plus an add, never a silent merge."""
        gap = [d for d in self.deltas["deltas"] if not d["consecutive"]][0]
        removed = {r["player"] for r in gap["removed"]}
        added = {r["player"] for r in gap["added"]}
        self.assertIn("Embid, Joel", removed)
        self.assertIn("Embiid, Joel", added)
        self.assertEqual(self.c.norm_name("Embid, Joel"), "embid joel")
        self.assertEqual(self.c.norm_name("Embiid, Joel"), "embiid joel")
        self.assertNotEqual(self.c.norm_name("Embid, Joel"), self.c.norm_name("Embiid, Joel"))


class TestSite(unittest.TestCase):
    def test_pages_exist_and_are_non_trivial(self):
        for name in ("index.html", "requirements.html", "result-feed.html", "injuries.html",
                     "flagged.html", "questions.html", "suggestions.html", "sources.html"):
            p = OUT / name
            self.assertTrue(p.exists(), name)
            self.assertGreater(p.stat().st_size, 2000, name)

    def test_stylesheet_exists_and_is_linked(self):
        self.assertTrue((OUT / "assets" / "site.css").exists())
        for p in OUT.glob("*.html"):
            self.assertIn('href="assets/site.css"', p.read_text(encoding="utf-8"), p.name)

    def test_no_unresolved_conflict_markers(self):
        for p in OUT.rglob("*"):
            if p.is_file():
                self.assertNotIn("<<<<<<<", p.read_text(encoding="utf-8", errors="ignore"), p)

    def test_every_data_row_ends_in_an_official_link_or_an_unverified_marker(self):
        import re
        for p in sorted(OUT.glob("*.html")):
            text = p.read_text(encoding="utf-8")
            body_html = re.sub(r'<table data-process-table="1">.*?</table>', "", text, flags=re.S)
            for m in re.finditer(r"<tbody>(.*?)</tbody>", body_html, re.S):
                for i, row in enumerate(re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S), 1):
                    cells = re.findall(r"<td>(.*?)</td>", row, re.S)
                    if not cells:
                        continue
                    last = cells[-1]
                    self.assertTrue(
                        ("nba.com" in last and "href" in last) or 'class="blank"' in last,
                        f"{p.name}: row {i} ends with neither an official link nor an "
                        f"unverified marker")

    def test_no_wall_clock_written_into_the_pages(self):
        """The build must be reproducible, so no generation timestamp may be embedded."""
        import re
        for p in sorted(OUT.glob("*.html")):
            text = p.read_text(encoding="utf-8")
            for m in re.findall(r"generated (?:at|on) \d{4}-\d{2}-\d{2}", text):
                self.fail(f"{p.name}: embeds a wall clock ({m})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
