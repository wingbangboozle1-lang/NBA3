#!/usr/bin/env python3
"""Tests for the two-estimator layer (session arena/79341829-nba3)."""
import json
import math
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import estimators  # noqa: E402

APP = os.path.join(ROOT, "data", "app")


class EstimatorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.est = json.load(open(os.path.join(APP, "estimators.json"), encoding="utf-8"))

    def test_hca_is_pinned_not_free(self):
        h = self.est["hca_measurement"]
        expect = estimators.norm_ppf(h["home_win_rate"]) * h["margin_sd"]
        self.assertAlmostEqual(h["hca_points_pinned"], expect, places=1,
                               msg="HCA must equal probit(home-win rate) * margin SD")
        self.assertEqual(h["games"], 197)

    def test_window_rows_have_both_estimators_and_disagreement(self):
        self.assertEqual(len(self.est["window"]), 34)
        for row in self.est["window"]:
            self.assertIsNotNone(row["est_a_margin"])
            self.assertIsNotNone(row["est_b_margin"])
            self.assertAlmostEqual(row["disagreement_abs"],
                                   abs(row["est_a_margin"] - row["est_b_margin"]), delta=0.11)
            self.assertTrue(row["sources"] and row["sources"][0].startswith("https://"))

    def test_totals_are_possessions_times_ppp(self):
        for row in self.est["window"][:5]:
            ts = json.load(open(os.path.join(APP, "official_team_stats_2026-11-15.json"),
                                encoding="utf-8"))
            cols = ts["pages"]["advanced"]["columns"]
            adv = {r[0]: dict(zip(cols, r)) for r in ts["pages"]["advanced"]["rows"]}
            eff_h = adv[row["home"]]["off_rtg"] * adv[row["away"]]["def_rtg"] / 114.0 if False else None
            # the model total B must equal (eff_h + eff_a) * poss / 100 (recomputed here)
            lg = sum(adv[t]["def_rtg"] for t in adv) / len(adv)
            eff_h = adv[row["home"]]["off_rtg"] * adv[row["away"]]["def_rtg"] / lg
            eff_a = adv[row["away"]]["off_rtg"] * adv[row["home"]]["def_rtg"] / lg
            poss = (adv[row["home"]]["pace"] + adv[row["away"]]["pace"]) / 2
            self.assertAlmostEqual(row["est_b_total"], (eff_h + eff_a) * poss / 100, delta=0.11)

    def test_parlay_prices_print_naive_product_and_rho(self):
        self.assertTrue(self.est["parlay_prices"])
        for p in self.est["parlay_prices"]:
            self.assertIn("rho_measured", p)
            self.assertIn("naive_product", p)
            self.assertIn("joint_price_rho", p)
            self.assertAlmostEqual(p["naive_product"], p["p_side"] * p["p_over"], places=3)

    def test_luck_z_scores_published(self):
        luck = self.est["luck_band"]
        self.assertGreater(len(luck), 25)
        for t, v in luck.items():
            self.assertIn("luck_z", v)
            self.assertEqual(v["outside_noise_band"], abs(v["luck_z"]) > 2.0)

    def test_market_prior_blank_without_feed(self):
        mp = self.est["market_anchored_prior"]
        self.assertEqual(mp["blended_lines"], [])
        self.assertIn("blank", mp["flag"])
        closing = json.load(open(os.path.join(APP, "closing_lines.json"), encoding="utf-8"))
        self.assertEqual(closing["feed_status"], "not connected")

    def test_headline_is_disagreement(self):
        self.assertIsNotNone(self.est["policy"]["disagreement_headline_mean"])
        self.assertEqual(self.est["policy"]["headline"],
                         "the disagreement between the two independent estimators")


class MinutesModelTest(unittest.TestCase):
    def test_redistribution_sums_to_removed_share(self):
        mm = json.load(open(os.path.join(APP, "minutes_model.json"), encoding="utf-8"))
        for team, v in mm["teams"].items():
            if not v["redistribution"]:
                continue
            add_sum = sum(r["replacement_share_from_out_players"] for r in v["redistribution"])
            self.assertAlmostEqual(add_sum, v["removed_share"], places=2,
                                   msg=f"{team}: replacement shares must sum to the removed share")
        self.assertTrue(mm["injury_report"]["source"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
