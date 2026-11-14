"""Data-level unit tests pinning the refreshed 183-game artifacts.

Session 25418e3f's capture script (scripts/capture_official_2026_11_14c.py)
runs its cross-checks at build time. These tests pin the COMMITTED artifacts to
the same invariants in unit-test form, so a silent edit to any of them fails
fast and locally (session arena/8e199e09-nba3):

  * league arithmetic: sum(GP)/2 == 183 == number of rows in the results log;
  * full record reconciliation: every team's official W and L equals the
    wins/losses counted over the whole results log;
  * the nine official 2026-11-13 finals appear in the results log with
    identical scores and overtime state;
  * the 04:15 AM report's 11/14 rows are field-for-field identical to the
    stored 07:45 PM snapshot's 11/14 rows (the C4 invariant of the capture);
  * the provenance file records the exact 174 -> 183 extension.
"""
import csv
import json
import os
import unittest
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def load_log():
    rows = []
    with open(os.path.join(ROOT, "data", "origin", "games.csv"),
              encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"date": r["date"], "game_id": r["game_id"],
                         "away": r["away"], "away_pts": int(r["away_pts"]),
                         "home": r["home"], "home_pts": int(r["home_pts"]),
                         "ot": int(r["ot"] or 0)})
    return rows


class LeagueArithmetic(unittest.TestCase):
    def test_gp_sum_matches_log_length(self):
        ratings = load("data", "app", "official_team_ratings_2026-11-14c.json")
        log = load_log()
        self.assertEqual(len(ratings["teams"]), 30)
        self.assertEqual(sum(t["gp"] for t in ratings["teams"]) / 2.0, 183.0)
        self.assertEqual(len(log), 183)
        self.assertEqual(max(g["date"] for g in log), "2026-11-13")


class RecordReconciliation(unittest.TestCase):
    def test_every_team_record_matches_the_log(self):
        ratings = load("data", "app", "official_team_ratings_2026-11-14c.json")
        wins, losses, played = defaultdict(int), defaultdict(int), defaultdict(int)
        for g in load_log():
            played[g["away"]] += 1
            played[g["home"]] += 1
            if g["away_pts"] > g["home_pts"]:
                wins[g["away"]] += 1
                losses[g["home"]] += 1
            else:
                wins[g["home"]] += 1
                losses[g["away"]] += 1
        for t in ratings["teams"]:
            self.assertEqual((t["w"], t["l"], t["gp"]),
                             (wins[t["team"]], losses[t["team"]], played[t["team"]]),
                             f"team {t['team']} disagrees with the results log")


class FinalsPinned(unittest.TestCase):
    def test_nine_1113_finals_match_the_log(self):
        finals = load("data", "app", "official_results_2026-11-13.json")["games"]
        self.assertEqual(len(finals), 9)
        by_gid = {g["game_id"]: g for g in load_log()}
        for f in finals:
            g = by_gid.get(f["game_id"])
            self.assertIsNotNone(g, f"{f['game_id']} missing from the log")
            self.assertEqual((g["date"], g["away"], g["away_pts"],
                              g["home"], g["home_pts"]),
                             (f["date"], f["away"], f["away_pts"],
                              f["home"], f["home_pts"]),
                             f"{f['game_id']} disagrees with the log")
            self.assertEqual(bool(g["ot"]), bool(f["ot"]))


class InjuryReportPinned(unittest.TestCase):
    def test_0415am_rows_equal_0745pm_rows_on_the_1114_slate(self):
        fresh = load("data", "app", "official_injuries_2026-11-14_0415AM.json")
        stored = load("data", "app", "official_injuries_2026-11-13_0745PM.json")

        def key(r):
            # The 04:15 AM page prints an empty team cell on one row (the
            # documented irregularity F26-01: Traore, Nolan), so the join key is
            # date + matchup + player and the team name is compared only where
            # the fresh row actually printed one.
            return (r["game_date"], r["matchup"], r["player"])

        fresh_1114 = [r for r in fresh["rows"] if r["game_date"] == "11/14/2026"]
        stored_1114 = {}
        for r in stored["rows"]:
            if r["game_date"] == "11/14/2026":
                stored_1114.setdefault(key(r), []).append(r)
        self.assertEqual(len(fresh_1114), len(stored_1114),
                         "the two snapshots carry a different number of 11/14 rows")
        for r in fresh_1114:
            cands = stored_1114.get(key(r))
            self.assertTrue(cands, f"04:15 AM row {key(r)} missing from the stored snapshot")
            match = None
            for c in cands:
                if not r["team_name"] or c["team_name"] == r["team_name"]:
                    match = c
                    break
            self.assertIsNotNone(match, f"no stored row matches {key(r)}")
            self.assertEqual((match["status"], match["reason"],
                              match["is_team_not_submitted"]),
                             (r["status"], r["reason"], r["is_team_not_submitted"]),
                             f"row {key(r)} changed between 07:45 PM and 04:15 AM")
            if r["team_name"]:
                self.assertEqual(match["team_name"], r["team_name"], key(r))

    def test_provenance_records_the_exact_extension(self):
        p = load("data", "origin", "games_extended_provenance.json")
        self.assertEqual((p["games_before"], p["games_after"]), (174, 183))
        self.assertEqual(p["rows_added"], 9)


if __name__ == "__main__":
    unittest.main()
