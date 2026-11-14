"""Regression tests for the game-day refresh round (session arena/df301475-nba3).

Three of these fail against the code as it stood on 2026-11-14 before the fix,
which is the point of writing them:

* ``test_comma_form_matches_first_last_form`` pins the injury-to-rotations join
  (flag F-DF3-03).  The official injury report prints ``Edwards, Anthony``; the
  official statistics table prints ``Anthony Edwards``.  The old index built
  ``(first_token, last_token)`` for BOTH conventions, so no player could ever
  match and every published "minutes vacated" figure was 0.0 or blank.
* ``test_team_guard`` pins the other half of the same fix: a name match whose
  team codes disagree is not allowed, because shared surnames are common in the
  league (the 11/14 report lists ``Murray, Dejounte`` on New Orleans while the
  minutes table holds ``Jamal Murray`` on Denver).
* ``test_mirror_pairs_are_measured`` pins the audit that the leaderboard's
  "a mirror is one finding, not two" sentence rests on.
"""

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import strategy_lab as lab  # noqa: E402


def jload(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


class NameMatching(unittest.TestCase):
    def test_comma_form_matches_first_last_form(self):
        self.assertEqual(lab.player_key("Edwards, Anthony"), lab.player_key("Anthony Edwards"))
        self.assertEqual(lab.player_key("Murphy III, Trey"), lab.player_key("Trey Murphy III"))
        self.assertEqual(lab.player_key("Holmes II, DaRon"), lab.player_key("DaRon Holmes II"))
        self.assertEqual(lab.player_key("Udeh, Jr., Ernest"), lab.player_key("Ernest Udeh Jr."))
        self.assertEqual(lab.player_key("Brown Jr., Mikel"), lab.player_key("Mikel Brown Jr."))

    def test_different_players_do_not_match(self):
        self.assertNotEqual(lab.player_key("Murray, Dejounte"), lab.player_key("Jamal Murray"))
        self.assertNotEqual(lab.player_key("Edwards, Anthony"), lab.player_key("Justin Edwards"))

    def test_rollup_on_the_stored_captures_finds_edwards(self):
        """The published figure, re-derived from the two official inputs."""
        minutes = {}
        path = os.path.join(ROOT, "data", "app", "players_top31_2026-11-14c.csv")
        with open(path, encoding="utf-8") as fh:
            header = fh.readline().strip().split(",")
            for line in fh:
                cells = line.strip().split(",")
                if len(cells) != len(header):
                    continue
                rec = dict(zip(header, cells))
                minutes[lab.player_key(rec["player"])] = rec
        self.assertIn(lab.player_key("Edwards, Anthony"), minutes)
        self.assertEqual(float(minutes[lab.player_key("Edwards, Anthony")]["min"]), 33.7)

    def test_published_impact_row_agrees_with_this_derivation(self):
        doc = jload("data", "app", "lab.json")
        rows = [r for r in doc["injury_impact"]
                if r["date"] == "2026-11-14" and r["team"] == "MIN"]
        self.assertEqual(len(rows), 1)
        self.assertIn("Edwards, Anthony", rows[0]["out"])
        # 33.7 minutes and 33.3 points, from the official minutes table; the
        # second Out name (DiVincenzo) is outside the captured table and is
        # counted as unquantified rather than assumed to be worth zero.
        self.assertAlmostEqual(rows[0]["minutes_vacuum"], 33.7, places=1)
        self.assertAlmostEqual(rows[0]["pts_vacuum"], 33.3, places=1)
        self.assertEqual(rows[0]["players_without_official_minutes"], 1)

    def test_no_filed_row_silently_reports_zero_when_a_name_is_in_the_table(self):
        """If a listed player IS in the minutes table, the vacuum cannot be 0.0."""
        doc = jload("data", "app", "lab.json")
        keys = set()
        with open(os.path.join(ROOT, "data", "app", "players_top31_2026-11-14c.csv"),
                  encoding="utf-8") as fh:
            header = fh.readline().strip().split(",")
            for line in fh:
                cells = line.strip().split(",")
                if len(cells) == len(header):
                    keys.add(lab.player_key(dict(zip(header, cells))["player"]))
        bad = []
        for r in doc["injury_impact"]:
            matched = [n for n in (r["out"] + r["questionable"])
                       if lab.player_key(n) in keys]
            if matched and not r["out"]:
                continue
            if any(lab.player_key(n) in keys for n in r["out"]) and not r["minutes_vacuum"]:
                bad.append(r["team"])
        self.assertEqual(bad, [], f"teams with a table-listed Out player and no vacuum: {bad}")


class MirrorAudit(unittest.TestCase):
    def test_every_declared_pair_is_measured(self):
        doc = jload("data", "app", "lab.json")
        audit = doc["mirror_audit"]
        self.assertEqual(audit["checked"], len(lab.MIRROR_PAIRS))
        self.assertEqual(audit["detail"], [], "a declared mirror pair is not a real mirror")
        self.assertEqual(audit["identical_selection"], audit["checked"])
        self.assertEqual(audit["complementary_outcomes"], audit["checked"])

    def test_mirror_hit_rates_are_complementary(self):
        doc = jload("data", "app", "lab.json")
        by_id = {s["id"]: s for s in doc["strategies"]}
        for a, b in lab.MIRROR_PAIRS:
            self.assertIn(a, by_id)
            self.assertIn(b, by_id)
            ra, rb = by_id[a], by_id[b]
            self.assertEqual(ra["n"], rb["n"], f"{a}/{b} selected different numbers of games")
            self.assertEqual(ra["wins"] + rb["wins"], ra["n"], f"{a}/{b} are not exact complements")
            self.assertAlmostEqual(ra["rate"] + rb["rate"], 1.0, places=9,
                                   msg=f"{a}/{b} rates do not sum to one")
            self.assertEqual(ra["mirror_of"], b)
            self.assertEqual(rb["mirror_of"], a)


class GameDayCapture(unittest.TestCase):
    """The newest official report, checked against the one it supersedes."""

    @classmethod
    def setUpClass(cls):
        cls.snap = jload("data", "app", "official_injuries_2026-11-14_1330PM.json")
        cls.delta = jload("data", "app", "injury_delta_game_day.json")
        cls.man = jload("data", "app", "snapshot_manifest.json")

    def test_manifest_names_the_game_day_report(self):
        self.assertEqual(self.man["injuries"]["path"],
                         "data/app/official_injuries_2026-11-14_1330PM.json")
        self.assertEqual(self.snap["report_stamp"], "2026-11-14 01:30 PM ET")

    def test_row_counts_are_the_captured_ones(self):
        self.assertEqual(self.snap["count"], 69)
        self.assertEqual(self.snap["player_rows"], 50)
        self.assertEqual(self.snap["not_submitted_rows"], 19)
        self.assertEqual(self.snap["rows_by_game_date"],
                         {"2026-11-14": 51, "2026-11-15": 18})

    def test_delta_reconciles(self):
        c = self.delta["counts"]
        self.assertEqual(c["rows_to"] - c["rows_from"], c["added"] - c["dropped"])
        self.assertEqual(len(self.delta["added"]), c["added"])
        self.assertEqual(len(self.delta["dropped"]), c["dropped"])
        self.assertEqual(len(self.delta["changed"]), c["status_or_reason_changed"])

    def test_every_player_row_is_team_consistent_with_the_slate(self):
        """A row's team code must be one of the two teams of its slate game."""
        slate = jload(*self.man["slate"]["path"].split("/"))
        by_key = {(g["date"], f"{g['away']}@{g['home']}"): (g["away"], g["home"])
                  for g in slate["games"]}
        unknown = []
        for r in self.snap["rows"]:
            from datetime import datetime
            date = datetime.strptime(r["game_date"], "%m/%d/%Y").strftime("%Y-%m-%d")
            teams = by_key.get((date, r["matchup"]))
            if teams is None:
                unknown.append((date, r["matchup"]))
                continue
            self.assertIn(r["team"], teams, f"row {r['player']} filed under {r['team']}")
        self.assertEqual(unknown, [], "printed a game the stored official slate does not list")

    def test_unattached_fragments_are_published_not_absorbed(self):
        self.assertEqual(len(self.snap["unattached_fragments"]), 1)
        self.assertEqual(self.snap["unattached_fragments"][0]["cells"], ["Management"])
        # Allen's reason is exactly what his printed row carries: the lone
        # "Management" cell below the page break was NOT appended to it, even
        # though three sibling rows in the same Cleveland block print reasons
        # that end with that word (Merrill, Mitchell, Watson) - see F-DF3-02.
        by_player = {r["player"]: r for r in self.snap["rows"] if r["player"]}
        self.assertEqual(by_player["Allen, Jarrett"]["reason"],
                         "Injury/Illness - Right Knee Injury")
        self.assertEqual(by_player["Merrill, Sam"]["reason"],
                         "Injury/Illness - Right Elbow Injury Management")
        # the corroborating count the flag cites, measured by the capture itself
        self.assertEqual(self.snap["unattached_fragments"][0]
                         ["same_block_rows_ending_in_this_word"], 3)
        self.assertEqual(self.snap["unattached_fragments"][0]["after_player"], "Allen, Jarrett")

    def test_status_changes_match_the_two_documents(self):
        moves = {(c["team"], c["player"], c["stored_status"], c["new_status"])
                 for c in self.delta["changed"]}
        self.assertIn(("DAL", "Christie, Max", "Questionable", "Doubtful"), moves)
        self.assertIn(("BKN", "Brown Jr., Mikel", "Questionable", "Probable"), moves)
        self.assertEqual(len(moves), 4)


class AvailabilityStates(unittest.TestCase):
    def test_states_are_the_new_derivation(self):
        doc = jload("data", "app", "report_availability.json")
        c = doc["counts"]
        self.assertEqual(c["filed"], 9)
        self.assertEqual(c["due_and_not_filed"], 0)
        self.assertEqual(c["not_yet_due"], 19)
        self.assertEqual(c["no_report_covers_date"], 26)
        corr = doc["b2b_correspondence_1114"]
        self.assertTrue(corr["every_unfiled_side_is_explained_by_the_back_to_back_clause"])
        self.assertEqual(corr["teams_that_have_not"], ["MEM"])

    def test_as_of_clock_comes_from_the_report_not_a_constant(self):
        import report_availability as ra
        self.assertTrue(ra.set_as_of("2026-11-14 01:30 PM ET"))
        self.assertEqual((ra.AS_OF_DATE, ra.AS_OF_LOCAL_HOUR), ("2026-11-14", 13.5))
        self.assertFalse(ra.set_as_of("not a stamp"))


class LiveWindow(unittest.TestCase):
    def test_every_priced_game_is_in_the_three_day_window(self):
        doc = jload("data", "app", "lab.json")
        dates = {l["date"] for l in doc["lines"]}
        self.assertTrue(dates <= {"2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17"})
        self.assertEqual(len(doc["lines"]), 27)

    def test_no_strategy_is_funded(self):
        doc = jload("data", "app", "lab.json")
        funded = [s for s in doc["strategies"] if s.get("funded")]
        self.assertEqual(funded, [])
        for s in doc["strategies"]:
            if s["id"] == "ST-NUL":
                continue
            self.assertLess(abs(s.get("edge_pp") or 0.0), doc["luck_test"]["threshold_pp"],
                            f"{s['id']} clears the luck threshold; the headline is stale")


if __name__ == "__main__":
    unittest.main(verbosity=2)
