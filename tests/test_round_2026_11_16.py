"""Tests for the 2026-11-16 refresh + two-estimator round (session arena/8f4fac33-nba3).

These tests exist because every bug this round hit was a UNIT or ACCOUNTING bug, not a
modelling disagreement -- and each one printed a number that looked plausible:

  * a team-name/abbreviation map that was inverted, so estimator B silently produced nothing;
  * per-game points divided by season possessions, which priced a game at 1554 points;
  * points-per-100 divided by 100 twice, which priced it at 111;
  * the MEAN of the two teams' scoring rates instead of their SUM, which priced it at half;
  * a Gauss-Hermite quadrature that forgot the phi(x) weight, so every parlay printed 0.0;
  * a "P(over)" clamped at 1.0, printing a leg that could never lose;
  * a binomial z-score whose variance collapsed for strong teams, labelling seven of them
    outliers on one game each.

Each test below pins the invariant that would have caught one of those, so a replay fails loudly
instead of publishing a wrong number. Nothing here needs the network.
"""

import json
import math
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import refresh_2026_11_16 as R          # noqa: E402
import round_model_2026_11_16 as M      # noqa: E402

ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-16")


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestRefreshCapture(unittest.TestCase):
    """The capture layer: every parsed value must trace to the document it came from."""

    @classmethod
    def setUpClass(cls):
        cls.slate = R.parse_schedule()
        cls.inj, cls.delta = R.parse_injuries()
        cls.res = R.parse_gamebooks()
        cls.ts = R.parse_team_stats()

    def test_slate_is_the_three_day_window(self):
        self.assertEqual(sorted(self.slate["count_by_date"]),
                         ["2026-11-16", "2026-11-17", "2026-11-18"])
        self.assertEqual(self.slate["count"], 25)
        self.assertEqual(self.slate["count_by_date"],
                         {"2026-11-16": 8, "2026-11-17": 5, "2026-11-18": 12})

    def test_no_duplicate_game_ids(self):
        self.assertEqual(self.slate["duplicate_game_ids"], [])

    def test_every_slate_row_has_an_https_source(self):
        for g in self.slate["games"]:
            self.assertTrue(g["source_url"].startswith("https://"))
            self.assertRegex(g["game_id"], r"^0022600\d{3}$")
            self.assertIn(g["game_id"], g["game_url"])

    def test_injury_report_row_counts(self):
        # 56 cleanly parsed player rows + 1 rescued row whose STATUS cell the PDF does not print,
        # + 15 team-level NOT YET SUBMITTED placeholders
        self.assertEqual(self.inj["player_rows"], 57)
        self.assertEqual(self.inj["rows_with_missing_status"], 1)
        self.assertEqual(self.inj["not_submitted_rows"], 15)
        self.assertEqual(self.inj["count"], 72)

    def test_missing_status_is_null_not_inferred(self):
        (row,) = self.inj["rows_with_missing_status_detail"]
        self.assertEqual(row["player"], "Butler III, Jimmy")
        self.assertIsNone(row["status"],
                          "the one row with no printed STATUS must stay null; copying a status "
                          "from the previous report would be an inference")

    def test_the_missing_status_row_is_published_not_dropped(self):
        """The parser's unparseable bucket used to swallow this row entirely, which hid a real
        injury listing. It must now reach the table with a null status and its raw cells."""
        (rescued,) = self.inj["rows_rescued_from_unparseable"]
        self.assertEqual(rescued["player"], "Butler III, Jimmy")
        self.assertEqual(rescued["team"], "Golden State Warriors")
        self.assertEqual(len(rescued["raw_cells"]), 6)
        self.assertTrue(rescued["status_missing_note"])

    def test_every_not_yet_submitted_placeholder_keeps_its_team(self):
        """4 of the 15 placeholders arrive with the team cell shifted one column left; reading a
        fixed index lost the club name on exactly those rows."""
        self.assertEqual(self.inj["not_submitted_rows_without_team_cell"], 0)
        self.assertEqual(len(self.inj["teams_not_yet_submitted"]), 15)
        for team, n in self.inj["teams_not_yet_submitted"].items():
            self.assertEqual(n, 1, team)
            self.assertTrue(team.strip(), "a placeholder with no club name is unusable")

    def test_page_break_fills_are_recorded_not_silent(self):
        # every carried cell must name the field and the value that was carried
        for fill in self.inj["page_break_fills"]:
            self.assertIn(fill["field"], ("date", "game_time", "matchup", "team"))
            self.assertTrue(fill["value"])
        self.assertGreater(len(self.inj["page_break_fills"]), 0)

    def test_no_player_row_left_without_a_team(self):
        bad = [r for r in self.inj["rows"] if r.get("team") in (None, "", "UNATTRIBUTED")]
        self.assertEqual(bad, [])
        # and the attribution that closed the gap must be recorded, not silent
        self.assertTrue(all(r.get("team_attribution_evidence")
                            for r in self.inj["rows"] if r.get("team_attributed")))

    def test_injury_delta_is_a_same_game_day_diff(self):
        """The lead diff must compare two filings that describe the SAME games. Comparing the
        11/15 filing with the 11/16 filing produces slate turnover dressed up as injury news."""
        self.assertEqual(self.delta["prior_report"]["stamp"], "2026-11-16 12:00 AM ET")
        self.assertEqual(self.delta["current_report"]["stamp"], "2026-11-16 09:15 AM ET")
        self.assertGreaterEqual(len(self.delta["shared_matchups"]), 7)
        for c in self.delta["status_changes"]:
            self.assertNotEqual(c["from"], c["to"])

    def test_the_measured_zero_is_represented_as_zero(self):
        """57 players are listed on both filings with identical status strings, the rescued
        Butler row among them. The delta must say so explicitly rather than leaving an empty
        table that could be read as a parsing failure."""
        self.assertEqual(self.delta["status_change_count"], len(self.delta["status_changes"]))
        self.assertEqual(self.delta["unchanged_count"], 57)
        self.assertEqual(self.delta["newly_listed_count"], 0)
        self.assertEqual(self.delta["delisted_count"], 0)

    def test_turnover_is_reported_separately_and_labelled(self):
        self.assertGreater(self.delta["turnover_added_count"], 0)
        self.assertGreater(self.delta["turnover_removed_count"], 0)
        self.assertIn("NOT injury news", self.delta["caveat"])

    def test_phi_bkn_is_called_out_as_incomparable(self):
        """Both clubs were NOT YET SUBMITTED in the midnight filing, so that game cannot appear in
        a status diff and the page must say why rather than silently omitting it."""
        self.assertNotIn("PHI@BKN", self.delta["shared_matchups"])

    def test_results_cover_the_whole_game_day(self):
        self.assertEqual(self.res["count"], 9)
        self.assertEqual(self.res["rows"][0]["date"], "2026-11-15")

    def test_every_result_row_names_its_own_gamebook(self):
        """The gamebook URL carries the date and the two abbreviations, not the 10-digit id."""
        for r in self.res["rows"]:
            self.assertTrue(r["gamebook"].startswith("https://statsdmz.nba.com/pdfs/20261115/"))
            stem = r["gamebook"].rsplit("/", 1)[-1]
            self.assertEqual(stem, f"20261115_{r['away']}{r['home']}.pdf")
            self.assertIn(r["game_id"], r["game_url"])

    def test_blank_team_cells_are_attributed_with_evidence_or_left_blank(self):
        attributed = self.inj["team_cells_attributed"]
        for row in attributed:
            self.assertTrue(row["evidence"])
            self.assertTrue(row["team"])
        blank = [r for r in self.inj["rows"] if r.get("team") == "UNATTRIBUTED"]
        self.assertEqual(blank, [], "every row is attributable from the printed row above it")
        self.assertGreaterEqual(len(attributed), 5)

    def test_the_atl_mil_contradiction_is_caught_not_repaired(self):
        row = next(r for r in self.res["rows"] if r["game_id"] == "0022600243")
        self.assertFalse(row["settled"])
        self.assertIsNotNone(row["conflict"])
        self.assertEqual(row["conflict"]["period_table"], [37, 16, 37, 26])
        self.assertEqual(row["conflict"]["recap_line"], [37, 16, 27, 26])
        self.assertEqual(row["conflict"]["quarters_differing"], [3])
        self.assertIsNone(row["settlement_stamp"])
        # the arithmetic that fails is printed with the row
        self.assertIn("116", row["settlement_blocked_because"])

    def test_a_truncated_recap_is_not_a_contradiction(self):
        row = next(r for r in self.res["rows"] if r["game_id"] == "0022600241")
        self.assertTrue(row["recap_truncated"])
        self.assertTrue(row["settled"])
        self.assertEqual(row["conflict"]["quarters_differing"], [])

    def test_settlement_counts_are_internally_consistent(self):
        settled = sum(1 for r in self.res["rows"] if r["settled"])
        self.assertEqual(self.res["settled_count"], settled)
        self.assertEqual(self.res["settled_count"] + self.res["blocked_count"], 9)

    def test_team_stat_pages_parse_30_teams_and_pass_their_own_identities(self):
        self.assertEqual(self.ts["count"], 30)
        for name, check in self.ts["check_summary"].items():
            self.assertEqual(check["status"], "PASS", f"{name}: {check}")

    def test_pace_is_a_per_game_possession_count(self):
        """POSS/GP must reproduce the printed PACE. This is the check whose absence let a
        per-48 misinterpretation put 1554 points on a game."""
        for row in self.ts["teams"]:
            a = row["advanced"]
            self.assertAlmostEqual(a["POSS"] / a["GP"], a["PACE"], delta=2.5,
                                   msg=f"{row['team_abbr']}: POSS/GP {a['POSS']/a['GP']:.2f} "
                                       f"vs PACE {a['PACE']}")

    def test_every_team_row_resolves_to_an_abbreviation(self):
        for row in self.ts["teams"]:
            self.assertRegex(row["team_abbr"], r"^[A-Z]{3}$", row["team_name"])


class TestGates(unittest.TestCase):
    def test_gate_report_on_disk_has_no_build_blocking_failure(self):
        g = load("gates.json")
        self.assertEqual(g["blocking_failures"], [])
        self.assertTrue(g["rebuild_allowed"])
        # the integrity failure that IS present must be scoped to its row, not to the build
        self.assertIn("I2_quarter_scores", g["row_level_failures"])
        self.assertEqual(g["rows_withheld_from_settlement"], 1)

    def test_freshness_gate_compares_against_the_official_index(self):
        g = load("gates.json")
        f1 = next(x for x in g["gates"] if x["id"] == "F1_injury_freshness")
        self.assertEqual(f1["scope"], "build")
        self.assertEqual(f1["measured"]["index_newest"], f1["measured"]["parsed"])

    def test_every_gate_declares_a_scope(self):
        for gate in load("gates.json")["gates"]:
            self.assertIn(gate["scope"], ("build", "row"), gate["id"])


class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("model.json")

    # ---- estimator B and the team-page join ------------------------------------------------
    def test_estimator_b_has_a_number_for_every_game(self):
        rows = self.m["estimator_b"]["rows"]
        self.assertEqual(len(rows), 25)
        self.assertEqual(sum(1 for r in rows if r.get("available")), 25,
                         "every team plays enough games now; a missing row here means the "
                         "name->abbreviation join broke again")

    def test_margin_b_is_within_a_believable_band(self):
        # a regulation NBA game's expected margin lives inside +/- 25 points; anything outside
        # means a unit or join error, not a strong team
        for r in self.m["estimator_b"]["rows"]:
            self.assertLess(abs(r["margin_home"]), 25, r["game_id"])

    # ---- the total is possessions x points-per-possession ----------------------------------
    def test_totals_land_in_a_realistic_range(self):
        for row in self.m["totals"]["rows"]:
            self.assertTrue(190 <= row["total"] <= 260,
                            f"{row['game_id']}: total {row['total']} is not a basketball score")

    def test_ppp_total_tracks_the_naive_sum_closely(self):
        """The two methods must not disagree wildly: a big gap means a unit error, not insight."""
        for row in self.m["totals"]["rows"]:
            self.assertLess(abs(row["difference"]), 15,
                            f"{row['game_id']}: ppp total differs from the naive sum by "
                            f"{row['difference']}")

    def test_both_totals_are_published_side_by_side(self):
        for ln in self.m["pricing"]["lines"]:
            self.assertIsNotNone(ln["total_ppp"])
            self.assertIsNotNone(ln["total_efficiency"])
            self.assertIsNotNone(ln["total_disagreement"])

    # ---- home court is pinned, not fitted --------------------------------------------------
    def test_home_court_is_the_measured_rate(self):
        hc = self.m["home_court"]
        self.assertTrue(hc["pinned"])
        self.assertAlmostEqual(hc["home_wins"] / hc["games"], hc["home_win_rate"], places=4)
        self.assertAlmostEqual(hc["home_win_rate"], hc["home_wins"] / hc["games"], places=4)

    # ---- two estimators, disagreement as the headline --------------------------------------
    def test_every_line_carries_both_estimators_and_a_confidence_label(self):
        for ln in self.m["pricing"]["lines"]:
            self.assertIsNotNone(ln["margin_a"])
            self.assertIsNotNone(ln["margin_b"])
            self.assertAlmostEqual(ln["disagreement"], abs(ln["margin_a"] - ln["margin_b"]),
                                   places=2)
            self.assertIn(ln["confidence"]["label"], ("high", "medium", "low"))

    def test_the_blend_is_published_under_the_disagreement(self):
        for ln in self.m["pricing"]["lines"]:
            self.assertIn("disagreement", ln["headline"])
            self.assertIsNotNone(ln["blend_margin"])

    def test_estimator_a_beats_the_constant_baseline_out_of_sample(self):
        e = self.m["error_summary"]
        self.assertGreater(e["walk_forward_games"], 0)
        self.assertLess(e["margin_rmse_A"], e["margin_rmse_baseline"])

    # ---- luck ------------------------------------------------------------------------------
    def test_luck_z_uses_a_sane_scale(self):
        """A z of 8 on a one-game sample was the signature of the collapsed binomial variance."""
        for team, row in self.m["luck"]["teams"].items():
            if row["z"] is None:
                continue
            self.assertLess(abs(row["z"]), 4,
                            f"{team}: z={row['z']} on {row['games']} games is not credible")

    def test_a_team_without_a_meaningful_z_cannot_fund_a_strategy(self):
        for s in self.m["strategies"]:
            if s["teams_without_a_meaningful_z"]:
                self.assertFalse(s["published"], s["strategy_id"])

    def test_no_strategy_is_published_while_the_band_is_undecidable(self):
        """At 1-2 captured games per team, no team can be shown inside the band; the honest
        state of the board is 'nothing funded' and the tests pin it rather than let it drift."""
        self.assertEqual(sum(1 for s in self.m["strategies"] if s["published"]), 0)

    # ---- pricing ---------------------------------------------------------------------------
    def test_rho_is_measured_with_an_interval(self):
        p = self.m["pricing"]
        self.assertIsNotNone(p["rho"])
        self.assertEqual(p["rho_n"], 22)
        self.assertEqual(len(p["rho_ci95"]), 2)
        self.assertLess(p["rho_ci95"][0], p["rho"])
        self.assertGreater(p["rho_ci95"][1], p["rho"])

    def test_every_parlay_prints_both_prices(self):
        self.assertEqual(len(self.m["pricing"]["parlays"]), 25)
        for p in self.m["pricing"]["parlays"]:
            self.assertIsNotNone(p["naive_product"])
            self.assertIsNotNone(p["p_joint_with_rho"])
            self.assertIsNotNone(p["american_with_rho"])
            self.assertGreater(p["p_leg_2"], 0.0)
            self.assertLess(p["p_leg_2"], 1.0)

    def test_copula_collapses_to_the_product_when_rho_is_zero(self):
        for p1, p2 in ((0.3, 0.7), (0.6, 0.5), (0.15, 0.9)):
            self.assertAlmostEqual(M.copula_corr(p1, p2, 0.0), p1 * p2, places=6)

    def test_copula_is_monotone_in_rho(self):
        lo = M.copula_corr(0.6, 0.5, -0.5)
        mid = M.copula_corr(0.6, 0.5, 0.0)
        hi = M.copula_corr(0.6, 0.5, 0.5)
        self.assertLess(lo, mid)
        self.assertLess(mid, hi)

    def test_both_same_game_legs_are_dependent_in_the_same_direction(self):
        """rho here is the margin/total correlation; a NEGATIVE rho means 'home covers and over'
        is less likely than the product. The published joint must be on the correct side of the
        naive product given the sign of the measured rho."""
        rho = self.m["pricing"]["rho"]
        for p in self.m["pricing"]["parlays"]:
            if rho < 0:
                self.assertLessEqual(p["p_joint_with_rho"], p["naive_product"] + 1e-9)
            elif rho > 0:
                self.assertGreaterEqual(p["p_joint_with_rho"], p["naive_product"] - 1e-9)

    def test_market_anchor_is_null_not_invented(self):
        mp = self.m["market_prior"]
        self.assertFalse(mp["available"])
        for ln in self.m["pricing"]["lines"]:
            self.assertIsNone(ln["market_anchor"])

    # ---- provenance ------------------------------------------------------------------------
    def test_every_line_names_its_official_game_page(self):
        for ln in self.m["pricing"]["lines"]:
            self.assertTrue(ln["game_url"].startswith("https://www.nba.com/game/"))

    def test_the_unsettled_game_never_enters_the_ratings(self):
        excluded = self.m["input_games"]["excluded_unsettled"]
        self.assertEqual(excluded, ["0022600243"])
        self.assertEqual(self.m["input_games"]["settled_finals_used"], 22)


class TestDeterminism(unittest.TestCase):
    def test_a_second_build_is_byte_identical(self):
        first = M.build()
        second = M.build()
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True),
                         "the model must be deterministic; a diff means unseeded randomness or "
                         "dict-iteration order leaked into a published number")


if __name__ == "__main__":
    unittest.main()
