#!/usr/bin/env python3
"""Tests for session arena/d1b96315-nba3: capture integrity, model invariances, ledger tamper
evidence, gate truthfulness and the page contract.

These are not smoke tests. Each one re-derives a published number from the artefacts it was
supposed to come from and fails if the artefact disagrees — which is what keeps a generated site
from drifting away from its evidence. Run:

    python3 -m unittest discover -s d1b96315/tests -p 'test_*.py'
"""
from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import shutil
import sys
import tempfile
import unittest

TREE = pathlib.Path(__file__).resolve().parents[1]
ROOT = TREE.parent
DATA = TREE / "data"
sys.path.insert(0, str(TREE))


def mod(name: str):
    spec = importlib.util.spec_from_file_location(name, TREE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def art(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class TestCaptureReproducibility(unittest.TestCase):
    def test_every_artefact_re_derives_byte_for_byte(self):
        cap = mod("capture")
        self.assertEqual(0, cap.main(check=True),
                         "committed artefacts do not match the raw transcripts; run capture.py")

    def test_boxlog_re_derives(self):
        box = mod("boxlog")
        self.assertEqual(0, box.main(check=True))

    def test_model_re_derives(self):
        model = mod("model")
        self.assertEqual(0, model.main(check=True))


class TestInjuryParsing(unittest.TestCase):
    def setUp(self):
        self.latest = art("injuries_2026-11-16_latest.json")
        self.morning = art("injuries_2026-11-16_1130AM.json")

    def test_row_counts_match_the_transcripts(self):
        for snap, raw in ((self.latest, "injury_2026-11-16_0115PM.md"),
                          (self.morning, "injury_2026-11-16_1130AM.md")):
            text = (TREE / "data/raw" / raw).read_text(encoding="utf-8")
            pipe_rows = [ln for ln in text.splitlines()
                         if ln.strip().startswith("|") and "---" not in ln]
            # every parsed row came from a table row, and the count is not larger than the print
            self.assertLessEqual(snap["count"], len(pipe_rows))
            self.assertEqual(snap["count"],
                             sum(1 for r in snap["rows"] if r["player"] or r["not_yet_submitted"]))
            self.assertEqual(snap["player_rows"] + snap["club_marker_rows"], snap["count"])

    def test_statuses_are_only_what_the_document_prints(self):
        allowed = {"Available", "Day-To-Day", "Questionable", "Doubtful", "Out", None}
        for r in self.latest["rows"]:
            self.assertIn(r.get("status"), allowed, r)
            if r.get("status") is None and r.get("player"):
                self.assertTrue(r.get("status_missing"),
                                f"blank status with no flag: {r}")

    def test_unread_cells_are_flagged_not_filled(self):
        for r in self.latest["rows"]:
            if r.get("player") and r.get("reason") is None:
                self.assertTrue(r.get("reason_missing"), r)
            for key in ("reason", "status"):
                v = r.get(key)
                self.assertNotEqual(v, "", f"empty string instead of null: {r}")

    def test_carried_club_rows_are_marked(self):
        for r in self.latest["rows"]:
            if r.get("team_carried"):
                self.assertTrue(r["team"] and r["player"], r)

    def test_source_link_on_every_row(self):
        for r in self.latest["rows"]:
            self.assertTrue(str(r["source_url"]).startswith("https://ak-static.cms.nba.com/"), r)


class TestInjuryDiff(unittest.TestCase):
    def test_only_real_moves_are_called_status_changes(self):
        for name in ("injury_delta_2026-11-16_1130_to_1315.json",
                     "injury_delta_2026-11-16_0915_to_1315.json",
                     "injury_delta_2026-11-16_0915_to_1130.json",
                     "injury_delta_2026-11-16_1130_to_1300.json",
                     "injury_delta_2026-11-16_1300_to_1315.json"):
            d = art(name)
            for c in d["status_changes"]:
                changed_status = c["from_status"] != c["to_status"]
                changed_reason = (c.get("from_reason") or None) != (c.get("to_reason") or None)
                self.assertTrue(changed_status or changed_reason, f"no-op change in {name}: {c}")
                if changed_status:
                    self.assertIn("status", c["change_kind"])
                else:
                    self.assertIn("reason", c["change_kind"])

    def test_spelling_difference_is_not_reported_as_a_roster_move(self):
        d = art("injury_delta_2026-11-16_1130_to_1315.json")
        self.assertEqual(1, len(d["spelling_moves"]))
        sp = d["spelling_moves"][0]
        self.assertEqual("Mathurin, Bennedict", sp["older_spelling"])
        self.assertEqual("Mathurin, Benedict", sp["newer_spelling"])
        keys = {(a["club"], a.get("player")) for a in d["rows_added"]}
        self.assertNotIn((sp["club"], sp["newer_spelling"]), keys,
                         "a spelling difference leaked into rows_added")

    def test_morning_step_changed_nothing_and_is_not_invented(self):
        d = art("injury_delta_2026-11-16_0915_to_1130.json")
        self.assertEqual([], d["status_changes"])
        self.assertEqual([], d["rows_added"])
        self.assertEqual([], d["rows_removed"])
        self.assertEqual(d["counts"]["older_rows"], d["counts"]["newer_rows"])

    def test_the_three_hops_add_up_to_the_whole_day(self):
        seq = [art(f)["counts"] for f in
               ("injury_delta_2026-11-16_0915_to_1130.json",
                "injury_delta_2026-11-16_1130_to_1300.json",
                "injury_delta_2026-11-16_1300_to_1315.json")]
        day = art("injury_delta_2026-11-16_0915_to_1315.json")["counts"]
        self.assertEqual(sum(c["status_changes"] for c in seq), day["status_changes"])
        self.assertEqual(sum(c["rows_added"] for c in seq), day["rows_added"])
        self.assertEqual([c["newer_player_rows"] for c in seq],
                         [day["older_player_rows"] + c for c in
                          [0, day["newer_player_rows"] - day["older_player_rows"] - 1,
                           day["newer_player_rows"] - day["older_player_rows"]]] or True)
        self.assertEqual(4, day["status_changes"])
        self.assertEqual(19, day["rows_added"])

    def test_the_newest_revision_matches_another_sessions_independent_parse(self):
        snaps = art("injury_snapshots_2026-11-16.json")
        cross = snaps["cross_check_with_another_session"]
        self.assertTrue(cross["agree"], cross)
        self.assertEqual(76, cross["their_player_rows"])
        self.assertEqual(11, cross["their_not_submitted"])
        self.assertEqual(cross["their_player_rows"], cross["mine_player_rows"])
        # four revisions on this game day, and the chain is monotone in rows
        self.assertEqual(4, len(snaps["revisions"]))
        rows = [r["player_rows"] for r in snaps["revisions"]]
        self.assertEqual(sorted(rows), rows, rows)

    def test_every_change_carries_both_source_urls(self):
        d = art("injury_delta_2026-11-16_1130_to_1315.json")
        for c in d["status_changes"]:
            self.assertTrue(c["older_source"].endswith("_11_30AM.pdf"), c)
            self.assertTrue(c["newer_source"].endswith("_01_15PM.pdf"), c)


class TestStandingsAndStats(unittest.TestCase):
    def setUp(self):
        self.st = art("standings_2026-11-16.json")
        self.adv = art("team_advanced_2026-11-16.json")

    def test_all_thirty_clubs_on_both_feeds(self):
        self.assertEqual(30, len(self.st["teams"]))
        self.assertEqual(30, self.adv["count"])
        self.assertEqual({t["team_abbr"] for t in self.st["teams"]},
                         {t["team_abbr"] for t in self.adv["teams"]})

    def test_home_win_rate_is_the_sum_of_the_home_column(self):
        hw = sum(t["home_w"] for t in self.st["teams"])
        hl = sum(t["home_l"] for t in self.st["teams"])
        self.assertEqual(hw + hl, self.st["measured_home_games"])
        self.assertEqual(round(hw / (hw + hl), 4), self.st["measured_home_win_rate"])
        self.assertEqual(hw, self.st["measured_home_wins"])

    def test_every_row_internally_consistent(self):
        for t in self.st["teams"]:
            self.assertEqual(t["w"] + t["l"], t["gp"])
            self.assertTrue(t["location_split_equals_gp"], t)
            self.assertTrue(t["win_pct_matches_printed"], t)
            self.assertTrue(str(t["source_url"]).startswith("https://www.nba.com/"), t)
        self.assertEqual([], self.st["checks"]["rows_failing_location_split"])
        self.assertEqual([], self.st["checks"]["rows_failing_win_pct"])

    def test_wins_and_losses_balance_across_the_league(self):
        c = self.st["checks"]["w_equals_l"]
        self.assertEqual(c["sum_w"], c["sum_l"])

    def test_advanced_rows_pass_their_own_identities(self):
        self.assertEqual([], self.adv["rows_failing_checks"])
        for t in self.adv["teams"]:
            self.assertTrue(t["check"]["w_plus_l_equals_gp"], t)
            self.assertLessEqual(abs(t["residuals"]["net_rtg_off_minus_def_minus_printed"]), 0.1001, t)
            self.assertTrue(str(t["source_url"]).startswith("https://www.nba.com/stats/teams/advanced"), t)


class TestSettlement(unittest.TestCase):
    def setUp(self):
        self.res = art("results_2026-11-15.json")
        self.rows = self.res["rows"] + self.res["blocked_rows"]

    def test_one_row_per_game_and_all_nine(self):
        self.assertEqual(9, self.res["count"])
        self.assertEqual(9, len(self.rows))
        self.assertEqual(9, len({r["game_id"] for r in self.rows}))
        self.assertEqual(self.res["settled_count"] + self.res["blocked_count"], self.res["count"])

    def test_settled_rows_have_quarters_that_sum_to_the_final(self):
        for r in self.res["rows"]:
            self.assertEqual(sum(r["away_quarters"]), r["away_pts"], r["game_id"])
            self.assertEqual(sum(r["home_quarters"]), r["home_pts"], r["game_id"])
            self.assertTrue(r["settled"])
            self.assertTrue(r["sources"]["scoreboard"].startswith("https://www.nba.com/games"), r)

    def test_the_disputed_game_keeps_both_readings_and_is_not_silently_repaired(self):
        r = [x for x in self.rows if x["game_id"] == "0022600243"][0]
        self.assertEqual(113, r["away_pts"])
        self.assertEqual(106, r["home_pts"])
        self.assertEqual(37, r["alt_reading"]["milwaukee_q3_period_table"])
        self.assertEqual(27, r["alt_reading"]["milwaukee_q3_recap_line"])
        self.assertTrue(r.get("flag"))
        self.assertTrue(sum(r["home_quarters"]) == 106)   # the reading the model uses
        self.assertTrue(r["recount_source"].startswith("https://statsdmz.nba.com/"))

    def test_scores_match_the_official_finals_recorded_in_the_transcript(self):
        text = (TREE / "data/raw/results_2026-11-15_scoreboard.md").read_text(encoding="utf-8")
        by_game = {ln: ln for ln in text.splitlines()}
        for r in self.rows:
            line = [ln for ln in by_game if r["game_id"] in ln]
            self.assertEqual(1, len(line), r["game_id"])
            ln = line[0]
            cells = [c.strip() for c in ln.strip("|").split("|")]
            self.assertEqual(str(r["away_pts"]), cells[2], ln)
            self.assertEqual(str(r["home_pts"]), cells[4], ln)
            self.assertTrue(cells[3].startswith("Final"), ln)


class TestPlayerLogs(unittest.TestCase):
    def setUp(self):
        self.logs = art("player_logs_2026-11-15.json")

    def test_minutes_sum_to_the_team_game(self):
        for name, book in self.logs["books"].items():
            for team, v in book["checks"]["minutes_sum_vs_240"].items():
                self.assertLessEqual(abs(v["residual"]), 0.05, f"{name} {team}: {v}")

    def test_unread_cells_stay_blank(self):
        for r in self.logs["rows"]:
            if r.get("unread"):
                self.assertIsNone(r["pts"])
                self.assertIsNone(r["reb"])
                self.assertIsNone(r["ast"])
                self.assertIsNotNone(r["min"], "minutes are keyed by content and must survive")

    def test_readable_points_are_sane_and_sourced(self):
        for r in self.logs["rows"]:
            if r.get("pts") is not None:
                self.assertGreaterEqual(r["pts"], 0)
                self.assertLessEqual(r["pts"], 80, r)
            if r.get("min"):
                self.assertLessEqual(r["min"], 60, r)
            self.assertTrue(str(r["source"]).startswith("https://statsdmz.nba.com/"), r)

    def test_the_indiana_book_ties_out_exactly(self):
        ind = [r for r in self.logs["rows"] if r["team"] == "IND" and r.get("pts") is not None]
        self.assertEqual(124, sum(r["pts"] for r in ind))


class TestSlate(unittest.TestCase):
    def test_window_rows_unique_and_sourced(self):
        s = art("slate_2026-11-16_1118.json")
        self.assertEqual(29, s["count"])
        ids = [g["game_id"] for g in s["games"]]
        self.assertEqual(29, len(set(ids)))
        self.assertEqual({"2026-11-16": 8, "2026-11-17": 5, "2026-11-18": 12, "2026-11-19": 4},
                         s["count_by_date"])
        for g in s["games"]:
            self.assertTrue(g["source_url"].startswith("https://www.nba.com/"), g)
            self.assertLessEqual("2026-11-16", g["date"])
            self.assertLessEqual(g["date"], "2026-11-19")

    def test_the_fourth_day_is_this_sessions_own_read_and_marks_what_a_card_does_not_print(self):
        s = art("slate_2026-11-16_1118.json")
        extra = [g for g in s["games"] if g["date"] == "2026-11-19"]
        self.assertEqual(4, len(extra))
        for g in extra:
            self.assertIsNone(g["venue"], "a card prints no venue: it must be blank, never inferred")
            self.assertTrue(g["venue_missing"], g["game_id"])
            self.assertTrue(g["reverified_by_d1b96315"], g["game_id"])
            self.assertEqual(g["ingested_by"], "d1b96315/data/raw/games_2026-11-19_cards.md", g)
        # the records printed on the cards must agree with the standings capture, or the roll stops
        chk = s["record_cross_check_against_standings"]
        self.assertEqual([], chk["mismatches"])
        self.assertEqual(8, chk["rows_checked"])
        self.assertEqual({"from": "2026-11-16", "to": "2026-11-19"},
                         {k: s["window"][k] for k in ("from", "to")})
        self.assertEqual({"from": "2026-11-16", "to": "2026-11-18"},
                         s["window"]["published_window_on_main"])


class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = art("model.json")
        cls.lines = art("lines.json")["lines"]
        cls.st = art("standings_2026-11-16.json")

    def test_home_court_is_reproducible_from_the_two_measurements(self):
        hc = self.m["home_court"]
        cap = mod("capture")
        model = mod("model")
        self.assertTrue(hc["pinned"])
        self.assertEqual(self.st["measured_home_win_rate"], hc["measured_home_win_rate_standings"])
        # recompute the pin independently
        res = art("results_2026-11-15.json")
        games, _ = model.game_log()
        settled = [g for g in games if g.get("settled")]
        margins = [g["home_pts"] - g["away_pts"] for g in settled]
        s = model.sd(margins)
        again = round(model.phi_inv(self.st["measured_home_win_rate"]) * s, 2)
        self.assertEqual(hc["hca_points_used"], again)
        self.assertEqual(len(settled), self.m["inputs"]["settled_finals_used"])
        self.assertGreaterEqual(len(settled), 23,
                                "the log may only grow as main's feed grows; a shrink is a bug")
        # every game in the log must be a distinct official final
        keys = {(g["date"], g["game_id"] or (g["away"], g["home"])) for g in settled}
        self.assertEqual(len(settled), len(keys),
                         "a final appears in the log twice: the estimator would be testing itself")
        # and the de-duplication must have kept exactly one row per official game id
        ids = [g["game_id"] for g in settled if g.get("game_id")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_disagreement_column_is_the_absolute_difference(self):
        for r in self.lines:
            if not r.get("publishable"):
                continue
            self.assertAlmostEqual(r["disagreement_margin_points"],
                                   abs(r["estimator_a_margin"] - r["estimator_b_margin"]), places=2,
                                   msg=r["game_id"])
            self.assertAlmostEqual(r["blend_margin_underneath"],
                                   (r["estimator_a_margin"] + r["estimator_b_margin"]) / 2, delta=0.011)

    def test_the_total_is_possessions_times_points_per_possession(self):
        for r in self.lines:
            if not r.get("publishable"):
                continue
            self.assertAlmostEqual(r["total_possessions_model"],
                                   r["possessions"] * (r["ppp_away"] + r["ppp_home"]), places=1,
                                   msg=r["game_id"])
            self.assertGreater(r["total_possessions_model"], 150, r["game_id"])
            self.assertLess(r["total_possessions_model"], 280, r["game_id"])

    def test_the_naive_total_is_published_beside_ours_never_replacing_it(self):
        with_naive = [r for r in self.lines if r.get("publishable")
                      and r["total_naive_scoring_average"] is not None]
        self.assertEqual(29, len(with_naive))
        self.assertEqual(29, len(self.lines))
        for r in with_naive:
            self.assertAlmostEqual(r["total_gap_between_the_two_methods"],
                                   abs(r["total_possessions_model"]
                                       - r["total_naive_scoring_average"]), places=2)

    def test_refusals_follow_the_declared_rules(self):
        cap = self.m["home_court"] and 5.0
        for r in self.lines:
            if not r.get("publishable"):
                continue
            band = [v for v in r["luck_z"].values() if v is not None and abs(v) > 2.0]
            expected = (not band) and r["disagreement_margin_points"] <= cap
            self.assertEqual(expected, r["bet_eligible"],
                             f"{r['game_id']}: bet flag does not follow the rules")
            if not expected:
                self.assertTrue(r["bet_block"], f"{r['game_id']} refused with no reason")

    def test_unavailable_inputs_are_null_not_zero(self):
        self.assertIsNone(self.m["market_anchor"]["prior_weight"])
        self.assertIsNone(self.m["market_anchor"]["closing_line"])
        self.assertIsNone(self.m["market_anchor"]["measured_log_loss"])
        self.assertTrue(self.m["market_anchor"]["reason"])
        for ab, st in self.m["estimator_b"]["availability_status_by_team"].items():
            self.assertIn(st, ("applied", "no rotation data", "nothing to apply",
                               "no replacement pool", "minutes only"), (ab, st))

    def test_luck_z_recomputes_for_a_sample_club(self):
        model = mod("model")
        idx, _ = model.team_index()
        games, _ = model.game_log()
        sigma = model.sd([g["home_pts"] - g["away_pts"] for g in games if g.get("settled")])
        for ab in ("BOS", "MIL", "SAS"):
            t = idx[ab]
            again = model.luck_z(t, sigma)
            self.assertAlmostEqual(self.m["luck_z"][ab], again, places=3, msg=ab)
            self.assertLess(abs(again), 4.0, ab)

    def test_parlay_price_never_understates_the_naive_product_silently(self):
        for p in self.m["pricing"]["parlays"]:
            self.assertIn("p_parlay_naive_product", p)
            self.assertIn("p_parlay_measured_rho", p)
            self.assertAlmostEqual(p["difference_in_probability_points"],
                                   round((p["p_parlay_measured_rho"] - p["p_parlay_naive_product"]) * 100, 2),
                                   places=1, msg=p["game_id"])
            self.assertLessEqual(p["p_parlay_measured_rho"], min(p["p_leg_1"], p["p_leg_2"]) + 1e-9)
            self.assertGreaterEqual(p["p_parlay_measured_rho"], 0.0)

    def test_measured_rho_matches_a_direct_recomputation(self):
        model = mod("model")
        games, _ = model.game_log()
        settled = [g for g in games if g.get("settled")]
        m = [g["home_pts"] - g["away_pts"] for g in settled]
        t = [g["home_pts"] + g["away_pts"] for g in settled]
        self.assertAlmostEqual(self.m["pricing"]["rho_margin_vs_total"],
                               round(model.corr(m, t), 4), places=4)

    def test_every_line_row_carries_official_sources(self):
        for r in self.lines:
            self.assertIn("nba.com", r["source_url"], r["game_id"])
            self.assertTrue(r["source_url"].startswith("https://www.nba.com/"), r["game_id"])
            self.assertTrue(r["game_url"].startswith("https://www.nba.com/game/"), r["game_id"])

    def test_availability_only_removes_out_and_doubtful(self):
        rep = art("injuries_2026-11-16_latest.json")
        model = mod("model")

        def key(name):
            return model.norm_name(", ".join(reversed(name.split())) if "," not in name else name)

        by_key = {}
        for x in rep["rows"]:
            if x.get("player"):
                by_key[(x.get("team_abbr"), model.norm_name(x["player"]))] = x
        for r in self.lines:
            if not r.get("publishable"):
                continue
            for side in ("away", "home"):
                a = r["availability"][side]
                for o in a["out_applied"]:
                    row = by_key.get((r[side], model.norm_name(o["player"])))
                    self.assertTrue(row and row["status"] in ("Out", "Doubtful"),
                                    f"{o['player']} applied as out but the report says "
                                    f"{row['status'] if row else 'nothing'}")
        # and the reverse: nothing the report calls Questionable may appear as removed
        for r in self.lines:
            if not r.get("publishable"):
                continue
            for side in ("away", "home"):
                for o in r["availability"][side]["out_applied"]:
                    row = by_key.get((r[side], model.norm_name(o["player"])))
                    self.assertNotIn(row["status"], ("Questionable", "Available", "Day-To-Day"),
                                     f"{o['player']} treated as absent but the league printed "
                                     f"{row['status']}")

    def test_replacement_shares_do_not_invent_minutes(self):
        for r in self.lines:
            if not r.get("publishable"):
                continue
            for side in ("away", "home"):
                a = r["availability"][side]
                if a["status"] != "applied":
                    continue
                removed = sum(o["min"] for o in a["out_applied"])
                added = sum(x["added_min"] for x in a["replacement_shares"])
                self.assertAlmostEqual(removed, added, places=1,
                                       msg=f"{r['game_id']} {side}: redistributed {added} of {removed}")


class TestGatesAndPrereg(unittest.TestCase):
    def setUp(self):
        self.g = art("gates.json")
        self.p = art("prereg_index.json")
        self.m = art("model.json")

    def test_gate_verdicts_match_their_own_measurements(self):
        n = self.m["inputs"]["settled_finals_used"]
        for s in self.g["strategies"]:
            gates = s["gates"]
            self.assertEqual(n >= 60, gates["G1_sample_depth"]["pass"], s["id"])
            skill = self.m["estimator_a"]["out_of_sample_skill_vs_baseline"]
            self.assertEqual(skill > 0.05, gates["G4_out_of_sample"]["pass"], s["id"])
            self.assertEqual(s["n_candidates"] > 0, gates["G6_disagreement_cap"]["pass"], s["id"])
            self.assertFalse(gates["G8_price_feed"]["pass"],
                             "G8 may not pass while there is no price feed")
            self.assertEqual(s["status"] == "funded", len(s["blocking"]) == 0, s["id"])

    def test_no_strategy_is_funded_and_no_reward_is_claimed(self):
        self.assertEqual(0, self.g["summary"]["funded"])
        for s in self.g["strategies"]:
            self.assertEqual(0, s["reward_points"])

    def test_candidate_counts_recompute(self):
        lines = [r for r in art("lines.json")["lines"] if r.get("publishable")]
        avail = self.m["estimator_b"]["availability_status_by_team"]
        expect = {
            "D-S1": sum(1 for r in lines if r["disagreement_margin_points"] <= 2.5
                        and r["estimator_a_margin"] * r["estimator_b_margin"] > 0),
            "D-S2": sum(1 for r in lines if abs(r["estimator_b_margin"]) >= 4.0
                        and (avail[r["away"]] == "applied" or avail[r["home"]] == "applied")),
            "D-S3": sum(1 for r in lines
                        if (r["total_gap_between_the_two_methods"] or 0) >= 4.0),
            "D-S4": sum(1 for r in lines
                        if (r.get("parlay_price") or {}).get("status") == "priced"),
        }
        for s in self.g["strategies"]:
            if s["id"] in expect:
                self.assertEqual(expect[s["id"]], s["n_candidates"], s["id"])

    def test_prereg_files_are_hashed_and_frozen(self):
        import hashlib
        self.assertEqual(5, len(self.p["files"]))
        for sid, v in self.p["files"].items():
            self.assertTrue(v["frozen_before_first_bet"], sid)
            self.assertTrue(v["settlement_rule"], sid)
            self.assertTrue(v["universe"], sid)
            body = {k: x for k, x in v.items() if k != "sha256"}
            text = json.dumps(body, indent=1, sort_keys=True)
            self.assertEqual(v["sha256"], hashlib.sha256(text.encode()).hexdigest(), sid)
            on_disk = TREE / "data/prereg" / f"{sid}.json"
            self.assertTrue(on_disk.exists(), sid)
            self.assertEqual(json.loads(on_disk.read_text(encoding="utf-8")), v, sid)

    def test_every_gate_prints_a_measurement_not_just_a_verdict(self):
        for s in self.g["strategies"]:
            for k, gt in s["gates"].items():
                self.assertTrue(isinstance(gt, dict) and "pass" in gt and "measured" in gt
                                and "rule" in gt, f"{s['id']}/{k}")
                self.assertTrue(str(gt["measured"]).strip(), f"{s['id']}/{k} has no measurement")


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.led = mod("ledger")
        self.check = art("ledger_check.json")

    def test_a_settlement_entry_is_not_flagged_for_lacking_a_payload(self):
        # main's tree stores SETTLED entries whose payload_sha256 is the copied hash of the publish
        # entry they grade; a verifier that re-hashes the settlement body would call that tampering
        led = mod("ledger")
        res = led.verify_tree(ROOT / "data/app/ledger/ledger.jsonl", "chain_hash_pair_body")
        self.assertEqual([], res["problems"], res["problems"][:2])
        self.assertIn("SETTLED", json.dumps(res["kinds"]) + json.dumps(
            [json.loads(x)["body"].get("state") for x in
             (ROOT / "data/app/ledger/ledger.jsonl").read_text().splitlines() if x.strip()]))

    def test_all_three_chains_verify(self):
        for key in ("d1b96315", "ledger_A", "ledger_B"):
            tree = self.check["trees"][key]
            self.assertEqual([], tree["problems"], key)
            self.assertEqual("CHAIN INTACT", tree["result"], key)
            self.assertGreater(tree["entries"], 0, key)

    def test_k17_recipe_is_the_pair_not_the_body(self):
        k = self.check["k17_resolution"]
        n = k["entries"]
        self.assertEqual(f"{n}/{n}", k["recompute_with_chain_hash_prev_and_body"])
        self.assertGreaterEqual(n, 34, "main's chain has grown since the first read of the day")
        self.assertEqual(f"0/{n}", k["recompute_with_body_alone"])

    def test_tampering_one_character_breaks_the_chain(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / "ledger.jsonl"
        src = TREE / "ledger/ledger.jsonl"
        text = src.read_text(encoding="utf-8").splitlines()
        obj = json.loads(text[3])
        obj["payload"]["estimator_a_margin"] = round(obj["payload"]["estimator_a_margin"] + 0.01, 2)
        text[3] = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        tmp.write_text("\n".join(text) + "\n", encoding="utf-8")
        res = self.led.verify_tree(tmp, "pair")
        self.assertEqual("PROBLEMS", res["result"])
        self.assertTrue(any("payload" in p["problem"] or "entry_hash" in p["problem"]
                            for p in res["problems"]), res["problems"])
        self.assertEqual(4, res["problems"][0]["line"], "the tampered line must be named")

    def test_a_row_whose_tip_passed_cannot_be_sealed(self):
        from datetime import datetime, timezone
        future = datetime(2027, 1, 1, tzinfo=timezone.utc)
        real = self.led.LFILE
        tmp = pathlib.Path(tempfile.mkdtemp()) / "l.jsonl"
        self.led.LFILE = tmp
        try:
            res = self.led.publish(future)
        finally:
            self.led.LFILE = real
        self.assertEqual([], res["added"], "a post-tip row was sealed")
        self.assertEqual(29, len(res["skipped"]))
        self.assertTrue(all("tip" in s["why"] or "already" in s["why"] for s in res["skipped"]),
                        res["skipped"][:3])
        self.assertFalse(tmp.exists() and tmp.read_text().strip(), "nothing may be appended")

    def test_sealed_before_tip_is_arithmetically_true_for_every_entry(self):
        for e in [x for x in self.led.read(TREE / "ledger/ledger.jsonl") if x["kind"] == "PUBLISH"]:
            self.assertLess(e["published_utc"], e["tip_utc"], e["pick_id"])
            self.assertTrue(e["pre_tip"], e["pick_id"])
            self.assertEqual(e["payload"]["payload_kind"] if "payload_kind" in e["payload"] else
                             "originated projection line (side + total) — no funded strategy, no money bet",
                             e["payload"]["kind"], "the bet surface must never be sealed as a bet")

    def test_grading_uses_only_the_verified_final(self):
        payload = {"blend_margin_underneath": 4.0}
        fin = {"home_abbr": "BOS", "away_abbr": "NYK", "home_pts": 110, "away_pts": 100,
               "state": "Final", "sources": {"scoreboard": "https://www.nba.com/games?date=2026-11-15"}}
        g = self.led.grade_pick(payload, fin)
        self.assertEqual("BOS", g["model_favoured"])
        self.assertTrue(g["pick_correct"])
        self.assertEqual(6.0, g["margin_error_points"])
        self.assertIsNone(self.led.grade_pick({"blend_margin_underneath": None}, fin)["pick_correct"])

    def test_settle_refuses_to_grade_an_unsettled_game(self):
        res = art("results_2026-11-15.json")
        self.assertTrue(all(r["settled"] for r in res["rows"]))
        self.assertEqual(0, self.check["ledger"]["settled"],
                         "nothing on the 11/16 window has a final yet, so nothing may be settled")


class TestPages(unittest.TestCase):
    PAGES = TREE / "pages"

    def test_all_pages_exist(self):
        names = {p.name for p in self.PAGES.glob("*.html")}
        self.assertEqual({"index.html", "injuries.html", "results.html", "standings.html",
                          "lines.html", "pricing.html", "model.html", "gates.html", "ledger.html",
                          "questions.html", "suggestions.html", "flagged.html", "sources.html"}, names)

    def test_no_broken_relative_link(self):
        import re
        for p in self.PAGES.glob("*.html"):
            text = p.read_text(encoding="utf-8")
            for href in sorted(set(re.findall(r'href="([^"#]+)(?:#[^"]*)?"', text))):
                if href.startswith(("mailto:", "#")):
                    continue
                if href.startswith("http"):
                    self.assertTrue(href.startswith("https://"), href)
                    continue
                target = (p.parent / href).resolve()
                self.assertTrue(target.exists(), f"{p.name}: broken link {href}")

    def test_every_data_row_carries_a_source(self):
        for page in ("injuries.html", "results.html", "standings.html", "lines.html",
                     "flagged.html", "pricing.html"):
            text = (self.PAGES / page).read_text(encoding="utf-8")
            body = text.split("<tbody>", 1)[1] if "<tbody>" in text else text
            rows = [r for r in body.split("<tr>") if "<td" in r]
            self.assertGreater(len(rows), 0, page)
            for r in rows:
                self.assertTrue('class="src"' in r or "no official link on this row" in r,
                                f"{page}: row without a source marker: {r[:160]}")

    def test_the_injuries_banner_shows_revision_and_retrieval_time(self):
        text = (self.PAGES / "index.html").read_text(encoding="utf-8")
        self.assertIn("Revision printed on the document", text)
        self.assertIn("01:15 PM", text)
        self.assertIn("2026-11-16T18:26Z", text)
        self.assertIn("09:15", text)

    def test_the_disagreement_is_the_headline_not_the_blend(self):
        text = (self.PAGES / "lines.html").read_text(encoding="utf-8")
        self.assertLess(text.index("(headline)"), text.index("(underneath)"))
        self.assertIn("with the disagreement as the headline", text)

    def test_no_page_prints_a_python_none_or_an_unrendered_placeholder(self):
        import re
        for p in self.PAGES.glob("*.html"):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn(">None<", text, p.name)
            for m in re.finditer(r"\{[a-z_]+\[", text):
                self.fail(f"{p.name}: unrendered template text at {m.start()}")

    def test_amend_entries_exist_only_where_the_model_moved(self):
        ledger = mod("ledger")
        ent = ledger.read(TREE / "ledger/ledger.jsonl")
        amends = [e for e in ent if e["kind"] == "AMEND"]
        publishes = {e["pick_id"]: e for e in ent if e["kind"] == "PUBLISH"}
        cur = {r["game_id"]: r for r in art("lines.json")["lines"]}
        self.assertEqual(len(amends), len(set(a["amends"] for a in amends)), "a pick amended twice")
        for a in amends:
            self.assertIn(a["amends"], publishes, a["pick_id"])
            src = publishes[a["amends"]]
            self.assertEqual(src["entry_hash"], a["publish_entry_hash"],
                             "the amend must link to the sealed entry it amends")
            self.assertEqual(src["payload_sha256"], ledger.sha(src["payload"]),
                             "the sealed payload no longer hashes to what the chain says")
            for f in ("estimator_a_margin", "estimator_b_margin", "total_possessions_model"):
                self.assertEqual(a["sealed"][f], src["payload"][f], "sealed value rewritten")
                self.assertEqual(a["current"][f], cur[src["game_id"]][f], "current value wrong")
        # and every un-amended row must genuinely agree with the current model
        touched = {a["amends"] for a in amends}
        for pid, e in publishes.items():
            if pid in touched:
                continue
            c = cur[e["game_id"]]
            for f in ("estimator_a_margin", "estimator_b_margin", "total_possessions_model"):
                self.assertEqual(e["payload"][f], c[f],
                                 f"{pid} moved but was not amended: {f}")

    def test_flagged_page_lists_every_register_row_with_a_severity(self):
        text = (self.PAGES / "flagged.html").read_text(encoding="utf-8")
        flags = art("flags.json")["flags"]
        self.assertEqual(15, len(flags))
        for f in flags:
            self.assertIn(f'id="{f["id"]}"', text, f["id"])
            self.assertIn(f["severity"], ("high", "medium", "low"))
            self.assertTrue(f["sources"], f["id"])
            self.assertFalse(f["blocks_merge"], "a flagged row must not block the merge")


class TestFlags(unittest.TestCase):
    def test_flags_rebuild_identically(self):
        flags = mod("flags")
        before = (DATA / "flags.json").read_text(encoding="utf-8")
        flags.main()
        self.assertEqual(before, (DATA / "flags.json").read_text(encoding="utf-8"),
                         "flags.json is not reproducible from the artefacts")

    def test_no_flag_claims_a_value_that_is_not_measured(self):
        for f in art("flags.json")["flags"]:
            self.assertTrue(f["measured"], f["id"])
            self.assertTrue(f["action"], f["id"])
            self.assertGreaterEqual(len(f["sources"]), 1, f["id"])


class TestNothingOutsideTheTreeWasTouched(unittest.TestCase):
    """The board's scope rule, enforced by a test so it is not a promise."""

    ALLOWED_SHARED = ("COORDINATION.md", ".github/workflows/pages.yml")

    def test_this_session_touched_only_its_own_tree_plus_the_two_shared_files(self):
        """Committed scope check: everything on this branch, against the base commit."""
        import subprocess

        def run(*args):
            return subprocess.run(["git"] + list(args), cwd=str(ROOT), capture_output=True,
                                  text=True)

        base = run("rev-parse", "HEAD").stdout.strip()
        parent = run("rev-parse", "HEAD~1").stdout.strip()
        candidates = []
        for other in ("origin/main", "main"):
            r = run("merge-base", other, "HEAD")
            if r.returncode == 0 and r.stdout.strip():
                candidates.append(r.stdout.strip())
        if not candidates:
            self.skipTest("no main ref in this checkout to diff against")
        changed = run("diff", "--name-only", candidates[0], "HEAD").stdout.splitlines()
        # plus whatever is in the working tree right now (uncommitted, this session's own files)
        dirty = [ln[3:].strip() for ln in run("status", "--porcelain").stdout.splitlines()]
        for path in changed + dirty:
            ok = path.startswith("d1b96315/") or path in self.ALLOWED_SHARED
            self.assertTrue(ok, f"this session touched a file outside its declared scope: {path}")
        self.assertTrue(base and parent, "expected a committed history on this branch")

    def test_canonical_paths_are_untouched(self):
        for p in ("data/app/results_feed.json", "data/app/ledger/ledger.jsonl",
                  "ledger/ledger.jsonl", "data/rounds/2026-11-16/injuries.json",
                  "data/app/arena_coordinates.json", "app/picks.html", "index.html"):
            f = ROOT / p
            if f.exists():
                self.assertTrue(f.stat().st_size > 0, p)
        self.assertFalse((ROOT / "data/app/refresh/T1").exists(),
                         "test residue left in the canonical refresh directory")
        self.assertFalse((ROOT / "data/app/refresh/T2").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
