"""Tests for session 9c30f2ae's official captures (offline; no network).

The point of these tests is the brief's verification rule: publish only what an official document
prints, leave the rest blank, and flag it. Every test below either (a) checks a count against the
verbatim transcript on disk, or (b) plants an error to prove the check would catch it.
"""
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import capture_9c30f2ae as C  # noqa: E402

RD = os.path.join(ROOT, "data", "rounds", "2026-11-19-9c30f2ae")


def load(name):
    with open(os.path.join(RD, name), encoding="utf-8") as fh:
        return json.load(fh)


class InjuryParseTests(unittest.TestCase):
    def test_not_yet_submitted_count_matches_the_transcript(self):
        # the raw transcript prints the phrase 15 times; the artefact must agree, because a parser that
        # loses empty cells shifts the phrase into the status column and undercounts (that bug was real:
        # the first version of this parser published 0).
        with open(C.INJ_130, encoding="utf-8") as fh:
            raw = fh.read()
        d = C.parse_injury(C.INJ_130)
        self.assertEqual(sum(1 for r in d[0] if r["not_yet_submitted"]),
                         raw.count("NOT YET SUBMITTED"))

    def test_empty_leading_cells_are_preserved(self):
        # a page-break row keeps its empty cells: the club stays in the team column
        rows, _, _ = C.parse_injury(C.INJ_130)
        kuminga = [r for r in rows if r["player"] == "Kuminga, Jonathan"]
        self.assertEqual(len(kuminga), 1)
        self.assertIsNone(kuminga[0]["team"])
        self.assertEqual(kuminga[0]["status"], "Questionable")
        self.assertFalse(kuminga[0]["attributed"])

    def test_every_printed_row_is_accounted_for(self):
        rows, unread, _ = C.parse_injury(C.INJ_130)
        self.assertEqual(unread, [], "no line should be silently dropped")
        self.assertEqual(len(rows), 44)

    def test_a_row_is_never_attributed_by_its_neighbours(self):
        rows, _, _ = C.parse_injury(C.INJ_130)
        for r in rows:
            if r["team"] is None:
                self.assertFalse(r["attributed"])
        self.assertEqual([r["player"] for r in rows if not r["attributed"]],
                         ["Kuminga, Jonathan", "Pullin, Zyon"])

    def test_blank_status_stays_blank(self):
        # rows printed with a club and no status at all must not inherit one
        rows, _, _ = C.parse_injury(C.INJ_130)
        blanks = [r for r in rows if r["team"] and not r["status"]]
        for r in blanks:
            self.assertIsNone(r["status"])
            self.assertFalse(r["not_yet_submitted"])


class ManifestTests(unittest.TestCase):
    def test_the_capture_reproduces_byte_for_byte(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "capture_9c30f2ae.py"),
                            "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_input_has_a_url_and_a_sha256(self):
        man = load("manifest.json")
        self.assertGreaterEqual(len(man["inputs"]), 5)
        for item in man["inputs"]:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            path = os.path.join(ROOT, item["path"])
            self.assertTrue(os.path.exists(path), item["path"])
            self.assertEqual(C.sha256(path), item["sha256"], item["path"])

    def test_the_index_states_the_filing_rules(self):
        with open(C.INJ_INDEX, encoding="utf-8") as fh:
            text = " ".join(fh.read().split())      # the transcript wraps long lines
        self.assertIn("By 5 p.m. local time the day before a game", text)
        self.assertIn("1 p.m. local time on the day of the game", text)
        self.assertIn("continual basis throughout the day", text)

    def test_all_eight_revisions_are_named_on_the_index(self):
        with open(C.INJ_INDEX, encoding="utf-8") as fh:
            text = fh.read()
        for hhmm in ("12_00AM", "12_15AM", "12_30AM", "12_45AM", "01_00AM", "01_15AM", "01_30AM",
                     "01_45AM"):
            self.assertIn(hhmm, text)


class ResultTests(unittest.TestCase):
    def test_twelve_games_and_every_quarter_sum_reconciles(self):
        d = load("results_2026-11-18.json")
        self.assertEqual(d["game_count"], 12)
        self.assertEqual(d["problems"], [])
        for g in d["games"]:
            self.assertTrue(g["quarter_sums_equal_final"], g["game_id"])
            self.assertEqual(sum(q["pts"] for q in g["away_q"]), g["away_pts"])
            self.assertEqual(sum(q["pts"] for q in g["home_q"]), g["home_pts"])

    def test_a_planted_bad_quarter_is_caught(self):
        d = load("results_2026-11-18.json")
        g = json.loads(json.dumps(d["games"][0]))
        g["away_q"][0]["pts"] += 1
        self.assertNotEqual(sum(q["pts"] for q in g["away_q"]), g["away_pts"])

    def test_the_finals_match_the_independent_capture_already_on_main(self):
        # b1ce1334 captured the same 12 finals from the schedule page without quarter scores.
        other = os.path.join(ROOT, "data", "rounds", "2026-11-19", "results_2026-11-18.json")
        if not os.path.exists(other):
            self.skipTest("b1ce1334's capture is not on this branch")
        mine = {g["game_id"]: (g["away"], g["away_pts"], g["home"], g["home_pts"])
                for g in load("results_2026-11-18.json")["games"]}
        with open(other, encoding="utf-8") as fh:
            theirs = {g["game_id"]: (g["away"], g["away_score"], g["home"], g["home_score"])
                      for g in json.load(fh)["games"]}
        self.assertEqual(mine, theirs)

    def test_every_row_carries_its_own_game_page_url(self):
        for g in load("results_2026-11-18.json")["games"]:
            self.assertIn(g["game_id"], g["source_url"])
            self.assertTrue(g["source_url"].startswith("https://www.nba.com/game/"))


class StandingsTests(unittest.TestCase):
    def _st(self):
        with open(os.path.join(RD, "standings_2026-11-19.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_thirty_clubs_and_the_wins_equal_the_losses(self):
        d = self._st()
        self.assertEqual(len(d["teams"]), 30)
        c = d["checks"]
        self.assertEqual(c["total_w"], c["total_l"])
        self.assertTrue(c["home_plus_road_w_equals_total"])
        self.assertTrue(c["home_games_equal_road_games"])

    def test_every_row_reconciles_gp(self):
        for t in self._st()["teams"]:
            self.assertEqual(t["gp"], t["w"] + t["l"], t["team"])

    def test_home_court_is_measured_not_fitted(self):
        d = self._st()["home_court_measured"]
        self.assertEqual(d["home_wins"], 111)
        self.assertEqual(d["home_games"], 221)
        self.assertAlmostEqual(d["home_win_rate"], round(111 / 221, 6))

    def test_neutral_games_are_excluded_from_both_rates(self):
        c = self._st()["checks"]
        self.assertGreater(c["neutral_w"], 0, "the 2026-27 schedule has neutral-site Cup games")
        self.assertEqual(c["home_w"] + c["road_w"] + c["neutral_w"], c["total_w"])


class TeamStatsTests(unittest.TestCase):
    def _adv(self):
        with open(os.path.join(RD, "team_stats_advanced_2026-11-19.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_thirty_clubs_unique(self):
        d = self._adv()
        self.assertEqual(d["rows_read_in_full"] + d["rows_partial"], 30)
        self.assertEqual(d["duplicate_clubs"], [])
        self.assertEqual(len({r["team"] for r in d["rows"]}), 30)

    def test_every_row_satisfies_w_plus_l_equals_gp(self):
        d = self._adv()
        self.assertEqual(d["failures"], [])
        for r in d["rows"]:
            if r["complete"]:
                self.assertEqual(int(r["w"] + r["l"]), int(r["gp"]), r["team"])

    def test_the_partial_row_is_published_partial_and_not_filled(self):
        d = self._adv()
        self.assertEqual(d["rows_partial"], 1)
        part = [r for r in d["rows"] if not r["complete"]][0]
        self.assertEqual(part["team"], "Dallas Mavericks")
        self.assertIsNone(part["ast_ratio"], "an unread cell must not be filled")
        self.assertIsNone(part["poss"])


if __name__ == "__main__":
    unittest.main()
