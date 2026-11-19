"""Session arena/e9295737-nba3: injury archive, consecutive-report diff, official results.

The artefacts under data/rounds/2026-11-19-e9295737/ are reproducible from the committed
verbatim transcripts by scripts/capture_e9295737.py. These tests hold that reproduction,
the settlement arithmetic, the banner provenance fields, and the one cross-session check
that exists: the 12:30 AM rows were parsed independently by session b1ce1334 and the two
parses must agree.
"""
import importlib.util
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "rounds", "2026-11-19-e9295737")
SCRIPT = os.path.join(ROOT, "scripts", "capture_e9295737.py")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
_spec = importlib.util.spec_from_file_location("capture_e9295737", SCRIPT)
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


class ReproducibilityTests(unittest.TestCase):
    def test_committed_artefacts_reproduce(self):
        r = subprocess.run([sys.executable, SCRIPT, "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ok injury_reports.json", r.stdout)
        self.assertIn("ok results_2026-11-16_18.json", r.stdout)


class InjuryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.a = load("injury_reports.json")

    def test_banner_carries_the_printed_revision_and_the_retrieval_time(self):
        b = self.a["banner"]
        self.assertEqual(b["revision_time_et"], "2026-11-19 01:45 AM")
        self.assertEqual(b["retrieval_time_utc"], "2026-11-19T07:20Z")
        self.assertTrue(b["source_url"].startswith("https://ak-static.cms.nba.com/referee/injury/"))

    def test_every_revision_is_oldest_first_and_hashed(self):
        revs = self.a["revisions_oldest_first"]
        self.assertEqual([r["revision_clock_et"] for r in revs],
                         ["12:30 AM", "12:45 AM", "01:30 AM", "01:45 AM"])
        for r in revs:
            with self.subTest(rev=r["revision_printed"]):
                self.assertEqual(len(r["transcript_sha256"]), 64)
                self.assertTrue(r["source_url"].endswith(".pdf"))
                self.assertEqual(r["retrieved_utc"], "2026-11-19T07:20Z")

    def test_transcript_hash_pins_the_stored_transcript(self):
        for r in self.a["revisions_oldest_first"]:
            with self.subTest(rev=r["revision_printed"]):
                self.assertEqual(cap.sha256(r["transcript"]), r["transcript_sha256"])

    def test_player_rows_are_23_in_every_revision(self):
        for r in self.a["revisions_oldest_first"]:
            with self.subTest(rev=r["revision_printed"]):
                self.assertEqual(r["player_rows"], 23)
                self.assertEqual(len(r["rows"]), 23)

    def test_placeholder_rows_never_become_player_rows(self):
        for r in self.a["revisions_oldest_first"]:
            for row in r["rows"]:
                with self.subTest(rev=r["revision_printed"], player=row["player"]):
                    self.assertNotIn("NOT YET SUBMITTED", row["player"])
                    self.assertIsNotNone(row["status"])

    def test_diff_against_the_previous_revision_is_recorded(self):
        revs = self.a["revisions_oldest_first"]
        self.assertIsNone(revs[0]["diff_from_previous"], "the first revision has no predecessor")
        for r in revs[1:]:
            with self.subTest(rev=r["revision_printed"]):
                d = r["diff_from_previous"]
                # verified finding: no player changed status between 12:30 and 01:45 AM
                self.assertEqual(d["changes"], [])
                self.assertEqual(d["added"], [])
                self.assertEqual(d["removed"], [])
                self.assertEqual(d["unchanged_count"], 23)

    def test_the_1230_garbled_table_is_recorded_as_a_structure_problem(self):
        first = self.a["revisions_oldest_first"][0]
        joined = " ".join(" ".join(p["cells"]) for p in first["parsed_problems"])
        # the 12:30 AM text layer merged three teams into one cell
        self.assertIn("Brooklyn Nets TOR@DET", joined+" ")
        # ...and the 12:45 AM revision dropped that merge
        second = self.a["revisions_oldest_first"][1]
        joined2 = " ".join(" ".join(p["cells"]) for p in second["parsed_problems"])
        self.assertNotIn("Brooklyn Nets TOR@DET", joined2)

    def test_cross_session_agreement_on_the_1230_am_report(self):
        """b1ce1334 parsed the same 12:30 AM PDF independently; both parses must agree."""
        path = os.path.join(ROOT, "data", "rounds", "2026-11-19", "injury_parsed.json")
        if not os.path.exists(path):
            self.skipTest("the earlier session's parse is not present")
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)["revisions"]["1230AM"]["player_rows"]
        new = self.a["revisions_oldest_first"][0]["rows"]
        triples = lambda rows: {(r["player"], r["status"], r["reason"]) for r in rows}
        self.assertEqual(triples(old), triples(new))
        attrib = lambda rows: {(r["player"], r["matchup"], r["team"]) for r in rows}
        self.assertEqual(attrib(old), attrib(new))


class ResultsFeedTests(unittest.TestCase):
    def setUp(self):
        self.r = load("results_2026-11-16_18.json")

    def test_one_row_per_game_and_none_withheld(self):
        self.assertEqual(self.r["count"], 25)
        self.assertEqual(self.r["settled_count"], 25)
        self.assertEqual(self.r["withheld"], [])
        ids = [g["game_id"] for g in self.r["games"]]
        self.assertEqual(len(ids), len(set(ids)), "a game may appear only once")

    def test_every_quarter_sum_equals_the_printed_final(self):
        for g in self.r["games"]:
            with self.subTest(game=g["game_id"]):
                self.assertEqual(sum(g["away_quarters"]), g["away_pts"])
                self.assertEqual(sum(g["home_quarters"]), g["home_pts"])
                self.assertEqual(len(g["away_quarters"]), len(g["home_quarters"]))
                self.assertTrue(all(g["checks"].values()))
                self.assertTrue(g["settled"])

    def test_period_counts_match_the_game_id_date(self):
        per_day = {}
        for g in self.r["games"]:
            per_day.setdefault(g["date"], []).append(g)
        self.assertEqual({d: len(v) for d, v in per_day.items()},
                         {"2026-11-16": 8, "2026-11-17": 5, "2026-11-18": 12})

    def test_the_overtime_game_carries_five_periods(self):
        ot = [g for g in self.r["games"] if g["ot"]]
        self.assertEqual([g["game_id"] for g in ot], ["0022600256"])
        self.assertEqual(ot[0]["away_quarters"], [34, 32, 28, 17, 3])
        self.assertEqual(ot[0]["home_quarters"], [30, 29, 22, 30, 7])

    def test_every_row_cites_an_official_nba_page(self):
        for g in self.r["games"]:
            with self.subTest(game=g["game_id"]):
                self.assertTrue(g["source_page"].startswith("https://www.nba.com/game/"))
                self.assertIn(f"-{g['game_id']}", g["source_page"])
                self.assertEqual(g["source_games_list"],
                                 f"https://www.nba.com/games?date={g['date']}")

    def test_winner_is_the_higher_final(self):
        for g in self.r["games"]:
            with self.subTest(game=g["game_id"]):
                expected = g["away"] if g["away_pts"] > g["home_pts"] else g["home"]
                self.assertEqual(g["winner"], expected)

    def test_settlement_rule_is_printed_with_the_feed(self):
        self.assertIn("sum to the final score", self.r["settlement_rule"])
        self.assertIn("withheld", self.r["settlement_rule"])


class ParserUnitTests(unittest.TestCase):
    def test_a_failing_quarter_sum_is_withheld_not_repaired(self):
        orig = cap.RESULTS
        try:
            cap.RESULTS = [("2026-11-16", "0022600245", "ORL", "BOS",
                            [20, 30, 25, 40], [17, 24, 36, 28], 999, 105)]
            out = cap.build_results()
            self.assertEqual(out["settled_count"], 0)
            self.assertEqual(out["withheld_count"], 1)
            self.assertFalse(out["withheld"][0]["settled"])
            self.assertFalse(out["withheld"][0]["checks"]["away_quarters_sum_equals_final"])
        finally:
            cap.RESULTS = orig

    def test_unknown_status_is_nulled_and_reported(self):
        text = ("| 11/19/2026 | 08:00 (ET) | AAA@BBB | Some Team | Doe, John | Hurt | Injury |")
        rows, problems = cap.parse_report(text, "https://x", "2026-11-19 01:45 AM")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["status"])
        self.assertTrue(any("not a league designation" in p["why"] for p in problems))

    def test_placeholder_rows_are_not_players(self):
        text = "| 11/19/2026 | 08:00 (ET) | GSW@MEM | Golden State Warriors |  |  | NOT YET SUBMITTED |"
        rows, problems = cap.parse_report(text, "https://x", "r")
        self.assertEqual(rows, [])
        self.assertTrue(problems)

    def test_diff_reports_flags_a_status_change(self):
        prev = [{"player": "A, B", "status": "Out", "reason": "x", "team": "T", "matchup": "M@N"},
                {"player": "C, D", "status": "Questionable", "reason": "y", "team": "T", "matchup": "M@N"}]
        cur = [{"player": "A, B", "status": "Available", "reason": "x", "team": "T", "matchup": "M@N"}]
        d = cap.diff_reports(prev, cur)
        self.assertEqual(len(d["changes"]), 1)
        self.assertEqual(d["changes"][0]["from"], "Out")
        self.assertEqual(d["changes"][0]["to"], "Available")
        self.assertEqual([r["player"] for r in d["removed"]], ["C, D"])


if __name__ == "__main__":
    unittest.main()


class SlateTests(unittest.TestCase):
    def setUp(self):
        self.s = load("slate_2026-11-19_21.json")

    def test_three_dates_at_most_three_days_ahead(self):
        dates = sorted(self.s["count_by_date"])
        self.assertEqual(dates, ["2026-11-19", "2026-11-20", "2026-11-21"])
        self.assertEqual(self.s["horizon_days"], 3)

    def test_counts_match_the_games_page_calendar_cells(self):
        self.assertEqual(self.s["count_by_date"], self.s["calendar_cell_counts"])
        self.assertEqual(self.s["count"], 19)
        self.assertEqual(self.s["count_by_date"],
                         {"2026-11-19": 4, "2026-11-20": 9, "2026-11-21": 6})

    def test_no_duplicate_game(self):
        ids = [g["game_id"] for g in self.s["games"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_row_cites_an_official_game_page(self):
        for g in self.s["games"]:
            with self.subTest(game=g["game_id"]):
                self.assertEqual(
                    g["source_url"],
                    f"https://www.nba.com/game/{g['away'].lower()}-vs-{g['home'].lower()}-{g['game_id']}")
                self.assertEqual(g["source_games_list"], f"https://www.nba.com/games?date={g['date']}")

    def test_agrees_with_the_independent_capture(self):
        """b1ce1334 captured the same three dates independently at 05:44-05:50Z."""
        path = os.path.join(ROOT, "data", "rounds", "2026-11-19", "slate_2026-11-19_22.json")
        if not os.path.exists(path):
            self.skipTest("the earlier session's slate capture is not present")
        with open(path, encoding="utf-8") as fh:
            other = json.load(fh)
        rows = []
        for day in other["days"]:
            for g in day["games"]:
                g = dict(g)
                g.setdefault("date", day["date"])
                rows.append(g)
        theirs = {(r["date"], r["game_id"]): r for r in rows
                  if r["date"] in ("2026-11-19", "2026-11-20", "2026-11-21")}
        mine = {(r["date"], r["game_id"]): r for r in self.s["games"]}
        self.assertEqual(set(theirs), set(mine), "the two captures must cover the same games")
        for k in mine:
            with self.subTest(game=k):
                self.assertEqual(mine[k]["away"], theirs[k]["away"])
                self.assertEqual(mine[k]["home"], theirs[k]["home"])
                self.assertEqual(mine[k]["tip_et"].replace(" ", ""),
                                 theirs[k]["tip_et"].replace(" ", ""))

    def test_nba_cup_labels_are_recorded_only_where_printed(self):
        cup = [g for g in self.s["games"] if g["cup_group_printed"]]
        self.assertEqual(len(cup), 9)
        self.assertTrue(all(g["date"] == "2026-11-20" for g in cup))
        self.assertEqual({g["cup_group_printed"] for g in cup},
                         {"East Group A", "East Group B", "East Group C",
                          "West Group A", "West Group B", "West Group C"})


class CrossSessionCouplingTests(unittest.TestCase):
    """The float-sum fix (E1) changed what other sessions' scripts need at import time.

    gamebooks_2ecbccfd.py now imports floatsum from its own directory. Any test that copies
    that script into a scratch tree must copy the module too, or --check dies at import and
    the failure looks like a data mismatch. This is exactly the regression the rebase onto
    main surfaced after dd3edd74's diagnostic tests landed.
    """

    def test_every_script_importing_floatsum_ships_it(self):
        scripts_dir = os.path.join(ROOT, "scripts")
        importers = []
        for name in sorted(os.listdir(scripts_dir)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(scripts_dir, name), encoding="utf-8") as fh:
                if "from floatsum import" in fh.read():
                    importers.append(name)
        self.assertTrue(importers, "at least one script should use the deterministic sum")
        self.assertTrue(os.path.exists(os.path.join(scripts_dir, "floatsum.py")))
        for name in importers:
            with self.subTest(script=name):
                # the module must be importable by a script that inserts its own dir on sys.path
                self.assertTrue(os.path.exists(os.path.join(scripts_dir, "floatsum.py")))

    def test_dd3edd74_scratch_tree_copies_floatsum(self):
        path = os.path.join(ROOT, "tests", "test_dd3edd74.py")
        if not os.path.exists(path):
            self.skipTest("dd3edd74's test is not present")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"floatsum.py"', src,
                      "the scratch-tree test must copy floatsum.py or --check cannot import")

    def test_floatsum_is_deliberately_the_naive_311_sum(self):
        """floatsum pins CPython <=3.11 semantics, not maximal accuracy.

        That distinction matters: the module exists to reproduce artefacts that were
        published by the naive algorithm, so a case where naive and compensated summation
        disagree must return the NAIVE answer. 0.1 added ten times left-to-right gives
        0.9999999999999999, whereas 3.12's compensated builtin sum() gives 1.0.
        """
        from floatsum import total
        vals = [36.0, 35.0, 34.0, 33.0, 32.0, 31.0, 30.0, 29.0, 28.0, 27.0, 26.0, 25.0]
        self.assertEqual(total(vals), 366.0)
        self.assertEqual(total([0.1] * 10), 0.9999999999999999)
        # integers stay exact, so counts are unaffected
        self.assertEqual(total([1, 2, 3]), 6)
        self.assertIsInstance(total([1, 2, 3]), int)
        # None entries are skipped rather than treated as zero-valued floats
        self.assertEqual(total([1, None, 2]), 3)
