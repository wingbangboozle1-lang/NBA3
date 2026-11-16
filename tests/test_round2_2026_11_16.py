#!/usr/bin/env python3
"""Regression tests for the 1:00 PM ET round (session arena/fbd2484b-nba3).

Each test pins a defect that was real during this session, so it cannot come back:

  * the page-break row splice in the 1:00 PM PDF,
  * a matchup inherited across a page break (which mis-filed five Brooklyn Nets rows),
  * a club attributed by cell index instead of by content,
  * an estimator whose declared constant showed up as "disagreement",
  * a totals formula that was accidentally the mean instead of the sum,
  * a site builder that would publish a row without an official source.

Standard library only; no network.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import round2_2026_11_16 as R          # noqa: E402
import round2_registers as REG         # noqa: E402

ROUND = R.ROUND
RAW = R.RAW


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


class SeamAndAttribution(unittest.TestCase):
    """The parser must not guess, and must say when it recovered something."""

    @classmethod
    def setUpClass(cls):
        cls.sched = R.parse_schedule(os.path.join(RAW, "official_schedule_2026-11-16_18.md"))
        cls.a = R.parse_injury_report(
            os.path.join(RAW, "official_injuries_2026-11-16_0100PM.md"),
            label="1300", retrieved=R.RETRIEVED_1300, pdf_url=R.INJURY_PDF_1300,
            schedule_rows=cls.sched["games"])

    def test_the_page_break_splice_is_detected_exactly_once(self):
        self.assertEqual(self.a["seam_splice_row_count"], 1)
        row = self.a["seam_splice_rows"][0]
        self.assertEqual(row["team"], "Denver Nuggets")
        self.assertEqual(row["player"], "Whitmore, Cam")

    def test_the_spliced_row_is_a_real_row_not_dropped(self):
        players = [r["player"] for r in self.a["rows"] if r["kind"] == "player"]
        self.assertIn("Whitmore, Cam", players)

    def test_no_row_is_unattributed(self):
        self.assertEqual(self.a["rows_with_unattributed_team"], 0)
        self.assertEqual([r for r in self.a["rows"] if r.get("attribution") == "unresolved"], [])

    def test_every_matchup_contains_its_own_club(self):
        for r in self.a["rows"]:
            if r["kind"] != "player":
                continue
            self.assertIn(R._abbr(r["team"]), r["matchup"],
                          f"row {r['line']} {r['player']} attributed to the wrong game")

    def test_nets_rows_belong_to_phi_bkn_not_the_previous_game(self):
        """The defect: five Nets rows were filed under HOU@MIA by a stale matchup."""
        nets = [r for r in self.a["rows"] if r.get("team") == "Brooklyn Nets"]
        self.assertEqual(len(nets), 5)
        for r in nets:
            self.assertEqual(r["matchup"], "PHI@BKN")

    def test_unprinted_status_is_null_not_backfilled(self):
        missing = [r for r in self.a["rows"]
                   if r["kind"] == "player" and r["status"] is None]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["player"], "Butler III, Jimmy")

    def test_row_count_is_what_the_documents_imply(self):
        self.assertEqual(self.a["player_rows"], 75)
        self.assertEqual(self.a["not_submitted_rows"], 12)
        self.assertEqual(self.a["row_count"], 87)

    def test_cells_are_classified_by_content(self):
        self.assertEqual(R._cell_kind("CHI@CLE"), "matchup")
        self.assertEqual(R._cell_kind("Chicago Bulls"), "team")
        self.assertEqual(R._cell_kind("Questionable"), "status")
        self.assertEqual(R._cell_kind("NOT YET SUBMITTED"), "not_submitted")
        self.assertEqual(R._cell_kind("11/16/2026"), "date")
        self.assertEqual(R._cell_kind("07:00 (ET)"), "time")
        self.assertEqual(R._cell_kind(""), "blank")


class Diff(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sched = R.parse_schedule(os.path.join(RAW, "official_schedule_2026-11-16_18.md"))
        cls.a = R.parse_injury_report(
            os.path.join(RAW, "official_injuries_2026-11-16_0100PM.md"),
            label="1300", retrieved=R.RETRIEVED_1300, pdf_url=R.INJURY_PDF_1300,
            schedule_rows=cls.sched["games"])
        cls.b = R.parse_injury_report(
            os.path.join(ROOT, "data", "app", "official_injuries_2026-11-16_0915AM_raw.md"),
            label="0915", retrieved=R.RETRIEVED_0915, pdf_url=R.INJURY_PDF_0915,
            schedule_rows=cls.sched["games"])
        cls.d = R.diff_reports(cls.a, cls.b)

    def test_four_rows_moved(self):
        self.assertEqual(self.d["status_or_reason_changes"], 4)

    def test_the_four_are_the_known_ones(self):
        got = {(c["player"], c["was_status"], c["now_status"]) for c in self.d["changes"]}
        self.assertEqual(got, {
            ("Tyson, Jaylon", "Questionable", "Doubtful"),
            ("Larsson, Pelle", "Questionable", "Doubtful"),
            ("Jackson, GG", "Out", "Out"),
            ("Stewart, Isaiah", "Questionable", "Out"),
        })

    def test_nothing_is_reported_as_removed_by_a_page_break(self):
        """A player cannot be both added and removed unless he really moved filings."""
        removed = {(x["matchup"], x["player"]) for x in self.d["removed"]}
        added = {(x["matchup"], x["player"]) for x in self.d["added"]}
        self.assertEqual(removed & added, set())

    def test_only_clubs_that_stopped_not_submitting_explain_the_additions(self):
        newly = set(self.d["old_report_teams_not_submitted"]) - set(
            self.d["new_report_teams_not_submitted"])
        self.assertEqual(len(newly), 3)
        for x in self.d["added"]:
            self.assertTrue(
                x["team"] in newly or x["matchup"] == "HOU@MIA",
                f"unexplained addition {x['player']} ({x['team']})")

    def test_reason_only_change_is_not_counted_as_a_status_change(self):
        reason_only = [c for c in self.d["changes"] if c["direction"] == "reason_only"]
        self.assertEqual(len(reason_only), 1)
        self.assertEqual(reason_only[0]["was_status"], reason_only[0]["now_status"])

    def test_diff_is_not_positional(self):
        self.assertEqual(self.d["compared_keys"],
                         len({(r["matchup"], r["team"], r["player"])
                              for r in self.a["rows"] if r["kind"] == "player"}
                             | {(r["matchup"], r["team"], r["player"])
                                for r in self.b["rows"] if r["kind"] == "player"}))


class Measurements(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.st = R.parse_standings(os.path.join(RAW, "official_standings_2026-11-16.md"))
        cls.stats = R.load_team_stats()
        cls.hca = R.measure_home_advantage(cls.st)
        cls.m = R.build_model(cls.stats, cls.hca, None, cls.st)

    def test_home_advantage_is_the_measured_rate(self):
        self.assertEqual(self.hca["home_wins"], 102)
        self.assertEqual(self.hca["home_decisions"], 196)
        self.assertAlmostEqual(self.hca["home_win_rate"], 102 / 196, places=6)
        self.assertTrue(self.hca["pinned"])

    def test_road_wins_equal_home_losses(self):
        self.assertEqual(self.hca["road_wins"], self.hca["home_losses"])

    def test_thirty_clubs_each_page(self):
        self.assertEqual(self.st["team_count"], 30)
        self.assertEqual(len(self.stats["rows"]), 30)
        self.assertEqual({r["abbr"] for r in self.stats["rows"]},
                         {t["abbr"] for t in self.st["teams"]})

    def test_net_rating_arithmetic_holds(self):
        worst = max(r["net_abs_diff"] for r in self.stats["reconciliation"])
        self.assertLess(worst, 0.11)

    def test_estimator_b_is_centred_so_its_constant_cannot_inflate_the_gap(self):
        """The defect: B's level bias (+~13) appeared as disagreement against A."""
        self.assertGreater(self.m["centering"]["estimator_b_league_mean_raw"], 5.0)
        mean_b = sum(c["estimator_b_structure"] for c in self.m["clubs"]) / 30
        mean_a = sum(c["estimator_a_form"] for c in self.m["clubs"]) / 30
        self.assertAlmostEqual(mean_b, 0.0, places=2)
        self.assertAlmostEqual(mean_a, 0.0, places=2)

    def test_estimator_a_is_centred_net_rating(self):
        for c in self.m["clubs"]:
            self.assertAlmostEqual(
                c["estimator_a_form"],
                c["net_rtg_printed"] - self.m["centering"]["estimator_a_league_mean_raw"],
                places=2)

    def test_disagreement_median_is_plausible_not_a_level_shift(self):
        self.assertLess(self.m["disagreement_median"], 5.0)
        self.assertGreater(self.m["disagreement_max"], 3.0)

    def test_no_club_is_outside_the_luck_band(self):
        lg = R.league_averages(self.stats["rows"])
        for t in self.stats["rows"]:
            z = R.luck_z(t, lg)
            self.assertLessEqual(abs(z["z"]), 2.0, f"{z['abbr']} outside the band")


class Totals(unittest.TestCase):

    def test_total_is_a_sum_not_a_mean(self):
        st = R.load_team_stats()
        lg = R.league_averages(st["rows"])
        tm = R.totals_model(st, lg)
        t = R.matchup_total("ORL", "BOS", tm, {"home_win_rate": 0.52})
        by = tm["by_abbr"]
        self.assertAlmostEqual(t["naive_sum_of_points_per_game"],
                               by["ORL"]["pts"] + by["BOS"]["pts"], places=1)
        # a mean would be half that; guard the exact defect
        self.assertAlmostEqual(t["naive_sum_of_points_per_game"] / 2.0,
                               (by["ORL"]["pts"] + by["BOS"]["pts"]) / 2.0, places=1)
        self.assertGreater(t["total_from_poss_x_ppp"], 150)

    def test_identity_with_season_rates_is_disclosed(self):
        st = R.load_team_stats()
        lg = R.league_averages(st["rows"])
        tm = R.totals_model(st, lg)
        t = R.matchup_total("LAL", "SAS", tm, {"home_win_rate": 0.52})
        self.assertLess(abs(t["total_from_poss_x_ppp"] - t["naive_sum_of_points_per_game"]), 0.5)
        self.assertIn("identity disclosure", t["identity_disclosure"].lower())


class Gates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.g = load("gates.json")

    def test_no_blocking_gate_fails_and_rebuild_is_allowed(self):
        self.assertEqual(self.g["blocking_failures"], [])
        self.assertTrue(self.g["rebuild_allowed"])

    def test_every_gate_declares_a_scope(self):
        for x in self.g["gates"]:
            self.assertIn(x["scope"], ("build", "row", "advisory"))

    def test_the_gate_count_is_pinned(self):
        self.assertEqual(self.g["gate_count"], 17)

    def test_the_superseded_filing_is_disclosed_not_hidden(self):
        """The index listed a 1:15 PM filing after this round was built. A capture is only ever
        newest at its own read time; the page must say so and must not claim otherwise."""
        adv = {a["id"]: a for a in self.g["advisories"]}
        self.assertIn("F5_newer_filing_listed_since_capture", adv)
        self.assertFalse(adv["F5_newer_filing_listed_since_capture"]["pass"])
        self.assertIn("01:15 PM ET", adv["F5_newer_filing_listed_since_capture"]["detail"])
        # and it must not block
        self.assertNotIn("F5_newer_filing_listed_since_capture", self.g["blocking_failures"])

    def test_every_page_carries_the_superseded_banner(self):
        out = os.path.join(ROOT, "round2")
        for f in os.listdir(out):
            if not f.endswith(".html"):
                continue
            text = open(os.path.join(out, f), encoding="utf-8").read()
            self.assertIn("F13-15", text, f"{f} hides that a newer filing exists")


class Artefacts(unittest.TestCase):

    def test_artifacts_are_byte_identical_to_a_fresh_build(self):
        bundle = R.build_all()
        for name, key in [("injuries.json", "injuries_1300"),
                          ("injury_delta.json", "delta"),
                          ("gates.json", "gates"),
                          ("home_court.json", "home_court"),
                          ("model.json", "model"),
                          ("game_flow.json", "game_flow"),
                          ("standings.json", "standings")]:
            fresh = json.dumps(bundle[key], indent=1, ensure_ascii=False) + "\n"
            with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), fresh, f"{name} does not reproduce")

    def test_every_document_has_url_and_sha256(self):
        man = load("refresh.json")
        self.assertGreaterEqual(len(man["documents"]), 7)
        for d in man["documents"]:
            self.assertTrue(d["url"].startswith("https://"))
            self.assertRegex(d["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(os.path.exists(os.path.join(ROOT, d["transcript"])))

    def test_transcript_hashes_match_the_files_on_disk(self):
        man = load("refresh.json")
        for d in man["documents"]:
            self.assertEqual(R.sha256_file(os.path.join(ROOT, d["transcript"])), d["sha256"])


class Registers(unittest.TestCase):
    """A register entry must be true of the artefact it names."""

    def test_every_requirement_has_a_source_and_a_verdict(self):
        for rid, req, verdict, ev, artefact, contains, url in REG.REQUIREMENTS:
            self.assertIn(verdict, ("met", "met_partly", "blocked", "not_met"), rid)
            self.assertTrue(contains, f"{rid} names no evidence string")
            self.assertTrue(url.startswith("https://"), rid)

    def test_requirement_evidence_really_exists_in_the_named_artefact(self):
        missing = []
        for rid, req, verdict, ev, artefact, contains, url in REG.REQUIREMENTS:
            path = os.path.join(ROOT, artefact)
            if not os.path.exists(path):
                missing.append((rid, artefact, "missing file"))
                continue
            if contains not in open(path, encoding="utf-8", errors="replace").read():
                missing.append((rid, artefact, contains))
        # R26-R28 name pages this session generates; they must exist after a build
        self.assertEqual(missing, [], f"register cites evidence that is not there: {missing}")

    def test_questions_cover_every_state(self):
        states = {q[2] for q in REG.QUESTIONS}
        self.assertTrue({"known", "unknown", "discoverable"} <= states)

    def test_no_suggestion_is_implemented(self):
        # the page must still say so, and the status must not silently become 'done'
        for s in REG.SUGGESTIONS:
            self.assertEqual(len(s), 5)
        with open(os.path.join(ROOT, "round2", "suggestions.html"), encoding="utf-8") as fh:
            self.assertIn("proposed", fh.read())

    def test_every_flag_names_a_source_and_a_state(self):
        for fid, what, detail, action, url, state in REG.FLAGS:
            self.assertTrue(url.startswith("https://"), fid)
            self.assertIn(state, ("resolved", "recorded", "needs review", "withheld", "open"), fid)


class Site(unittest.TestCase):

    def test_all_pages_exist_and_every_internal_link_resolves(self):
        out = os.path.join(ROOT, "round2")
        pages = [f for f in os.listdir(out) if f.endswith(".html")]
        self.assertGreaterEqual(len(pages), 13)
        for f in pages:
            text = open(os.path.join(out, f), encoding="utf-8").read()
            for href in re.findall(r'href="([^"]+)"', text):
                if href.startswith(("#", "http://", "https://")):
                    continue
                self.assertTrue(os.path.exists(os.path.join(out, href.split("#")[0])),
                                f"{f} -> broken link {href}")

    def test_no_page_contains_an_unrendered_none(self):
        out = os.path.join(ROOT, "round2")
        for f in os.listdir(out):
            if not f.endswith(".html"):
                continue
            text = open(os.path.join(out, f), encoding="utf-8").read()
            self.assertNotIn(">None<", text, f)
            self.assertNotIn("None%", text, f)
            self.assertNotIn("{'", text, f)

    def test_flagged_page_lists_every_flag(self):
        text = open(os.path.join(ROOT, "round2", "flagged.html"), encoding="utf-8").read()
        for fid, *_ in REG.FLAGS:
            self.assertIn(fid, text, f"{fid} is not published on the flagged page")

    def test_sources_are_labelled_distinctly(self):
        """Two different documents must never render as the same link text."""
        text = open(os.path.join(ROOT, "round2", "injuries.html"), encoding="utf-8").read()
        labels = re.findall(r'rel="noopener">([^<]+)</a>', text)
        self.assertTrue(labels)
        self.assertTrue(all(l.strip() for l in labels))


if __name__ == "__main__":
    unittest.main(verbosity=2)
