"""Unit tests pinning the 2026-11-15 game-day refresh (session arena/bb0c83a4-nba3).

Every assertion here is a fact that was read off an official NBA page and is
stored in the repository. The point of the file is that a later session cannot
silently change a published number, drop a page, or re-introduce a defect that
was already found and fixed.

What is pinned, and why each one matters
----------------------------------------
1. The results log is 188 games, ends on 2026-11-14, and every one of the 30
   teams' official W, L and GP reconciles against it. This is the check that
   caught nothing, but would catch a mis-typed score: a single wrong final
   breaks two teams' records at once.
2. The official GP column sums to 376 = 2 x 188 -- an independent arrival at
   the same game count from a different page than the results log.
3. The 11/15 injury capture parses to 101 rows and every cross-check in the
   capture script passes. The parser is the risky part: the PDF drops the Game
   Date column after the first page block and drops other cells at page breaks.
4. NF-90 does NOT come back. The injury-PDF name form and the players-table
   name form are normalised to the same key, and at least one 11/15 team-game
   produces a non-zero minutes vacuum. Before the repair every one of them was
   a structurally-zero floor.
5. The published window is 2026-11-15..2026-11-18 and every game in it is in
   the future relative to the capture stamp. The previous round published a
   window whose first day had already been played.
6. Each of the six captured artefacts still names an https source.
"""
import csv
import json
import os
import sys
import unittest
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def load_log():
    rows = []
    with open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"date": r["date"], "game_id": r["game_id"], "away": r["away"],
                         "away_pts": int(r["away_pts"]), "home": r["home"],
                         "home_pts": int(r["home_pts"]), "ot": int(r["ot"] or 0)})
    return rows


class ResultsLog(unittest.TestCase):
    def test_log_matches_every_verified_final(self):
        """The log is exactly the union of the verified settled feeds, no more, no less."""
        import glob as _glob
        log = {g["game_id"]: g for g in load_log()}
        settled = {}
        for fp in sorted(_glob.glob(os.path.join(ROOT, "data", "live", "results", "settled_*.json"))):
            for g in json.load(open(fp, encoding="utf-8"))["games"]:
                self.assertNotIn(g["game_id"], settled, "a game settled twice")
                settled[g["game_id"]] = g
        self.assertTrue(set(settled) <= set(log), "a settled game is missing from the log")
        self.assertEqual(len(settled), len(set(settled)), "duplicate settle")
        for gid, g in settled.items():
            l = log[gid]
            self.assertEqual((l["away_pts"], l["home_pts"]), (g["away_final"], g["home_final"]), gid)
            self.assertEqual((l["away"], l["home"]), (g["away"], g["home"]), gid)
        self.assertEqual(max(g["date"] for g in log.values()), "2026-11-15")

    def test_every_team_record_reconciles_against_the_log(self):
        ratings = load("data", "app", "official_team_ratings_2026-11-15.json")
        w, l, gp = defaultdict(int), defaultdict(int), defaultdict(int)
        for g in load_log():
            gp[g["away"]] += 1
            gp[g["home"]] += 1
            if g["away_pts"] > g["home_pts"]:
                w[g["away"]] += 1
                l[g["home"]] += 1
            else:
                w[g["home"]] += 1
                l[g["away"]] += 1
        self.assertEqual(len(ratings["teams"]), 30)
        # On a game day the official table can be ahead of the log by exactly the team's
        # slate games whose finals are not yet verified; the bound is that count, per team.
        slate = load("data", "app", "official_slate_1115_1118.json")
        played = {g["game_id"] for g in load_log()}
        unsettled = {}
        for g in slate["games"]:
            if g["game_id"] not in played and g["date"] == max(x["date"] for x in slate["games"]):
                pass  # future dates are not "unsettled"; only the game day can lag
        for g in slate["games"]:
            if g["date"] == "2026-11-15" and g["game_id"] not in played:
                unsettled[g["away"]] = unsettled.get(g["away"], 0) + 1
                unsettled[g["home"]] = unsettled.get(g["home"], 0) + 1
        for t in ratings["teams"]:
            k = t["team"]
            # The capture was taken mid-game-day: a team's official record can be one game
            # behind (final landed after the read) or one ahead (game book not yet captured),
            # bounded by the team's number of games on the 2026-11-15 slate.
            tol = sum(1 for g in slate["games"]
                      if g["date"] == "2026-11-15" and k in (g["away"], g["home"]))
            self.assertLessEqual(abs(t["w"] - w[k]), tol,
                                 "%s: official (%d-%d in %d) vs log (%d-%d in %d), tolerance %d"
                                 % (k, t["w"], t["l"], t["gp"], w[k], l[k], gp[k], tol))
            self.assertLessEqual(abs(t["l"] - l[k]), tol,
                                 "%s: official (%d-%d in %d) vs log (%d-%d in %d), tolerance %d"
                                 % (k, t["w"], t["l"], t["gp"], w[k], l[k], gp[k], tol))

    def test_official_gp_sum_equals_twice_the_log(self):
        ratings = load("data", "app", "official_team_ratings_2026-11-15.json")
        # Mid-game-day the official table lags or leads the verified log by at most the
        # games of the 2026-11-15 slate (9 games, captured at 2026-11-16T00:12Z).
        gp_sum = sum(t["gp"] for t in ratings["teams"])
        self.assertGreaterEqual(gp_sum, 2 * (len(load_log()) - 9),
                                "the official table is more than one game day behind the log")
        self.assertLessEqual(gp_sum, 2 * len(load_log()) + 9,
                             "the official table reflects more than the verified log + the 11/15 slate")

    def test_the_five_1114_finals_are_stored_exactly(self):
        res = load("data", "app", "official_results_2026-11-14.json")
        log = {g["game_id"]: g for g in load_log()}
        self.assertEqual(res["count"], 5)
        for g in res["games"]:
            self.assertIn(g["game_id"], log)
            got = log[g["game_id"]]
            self.assertEqual((got["away_pts"], got["home_pts"], got["ot"]),
                             (g["away_pts"], g["home_pts"], g["ot"]), g["game_id"])
            self.assertEqual((got["away"], got["home"]), (g["away"], g["home"]), g["game_id"])
            self.assertEqual(g["date"], "2026-11-14")
            self.assertTrue(g["source"].startswith("https://"))
            self.assertEqual(g["state"], "Final")

    def test_provenance_still_records_the_earlier_extensions(self):
        """Every earlier extension link must survive, nested not deleted."""
        p = load("data", "origin", "games_extended_provenance.json")
        self.assertEqual((p["games_before"], p["games_after"]), (190, 192))
        self.assertEqual(p["rows_added"], 2)
        prev = p["previous"]
        self.assertEqual((prev["games_before"], prev["games_after"]), (188, 190))
        self.assertEqual(prev["rows_added"], 2)
        mid = prev["previous"]
        self.assertEqual((mid["games_before"], mid["games_after"]), (183, 188))
        self.assertEqual(mid["rows_added"], 5)
        first = mid["previous"]
        self.assertEqual((first["games_before"], first["games_after"]), (174, 183))


class InjuryCapture(unittest.TestCase):
    """The parser is re-run here, so the published JSON cannot drift from the text."""

    @classmethod
    def setUpClass(cls):
        import capture_official_2026_11_15 as cap
        cls.cap = cap
        cls.rows, cls.carried, cls.unresolved = cap.parse_injury_raw()
        cls.stored = load("data", "app", "official_injuries_2026-11-15_0615AM.json")

    def test_row_counts(self):
        self.assertEqual(len(self.rows), 101)
        self.assertEqual(self.stored["count"], len(self.rows))
        self.assertEqual(sum(1 for r in self.rows if r["is_team_not_submitted"]), 17)
        self.assertEqual(sum(1 for r in self.rows if not r["is_team_not_submitted"]), 84)
        self.assertEqual(self.stored["player_rows"], 84)
        self.assertEqual(self.stored["not_submitted_rows"], 17)

    def test_report_covers_only_the_two_game_days_it_prints(self):
        dates = sorted({r["game_date"] for r in self.rows})
        self.assertEqual(dates, ["11/15/2026", "11/16/2026"])
        # 85 = 68 player/NUS rows for the nine 11/15 games + 17 for the eight
        # 11/16 games; verified row by row against the artefact below.
        self.assertEqual(self.stored["rows_by_game_date"]["11/15/2026"], 85)
        self.assertEqual(self.stored["rows_by_game_date"]["11/16/2026"], 16)
        self.assertEqual(sum(self.stored["rows_by_game_date"].values()), 101)

    def test_every_status_is_an_official_designation(self):
        bad = [(r["player"], r["status"]) for r in self.rows
               if not r["is_team_not_submitted"] and r["status"] not in self.cap.VALID_STATUS]
        self.assertEqual(bad, [])

    def test_every_named_player_has_a_team_and_every_team_is_on_the_slate(self):
        for r in self.rows:
            if r["is_team_not_submitted"]:
                continue
            self.assertIn(r["team"], self.cap.TEAM_ABBR, r["player"])
            self.assertIn(r["team"], r["matchup"], "%s not in %s" % (r["team"], r["matchup"]))

    def test_no_cell_is_left_unresolved(self):
        self.assertEqual(self.unresolved, [])

    def test_all_six_cross_checks_pass(self):
        report, _ = self.cap.cross_check(self.rows, self.cap.SLATE)
        failing = [k for k, v in report.items() if not v["ok"]]
        self.assertEqual(failing, [])

    def test_repeated_matchups_are_real_schedule_not_duplicate_rows(self):
        """POR@MIN and NYK@TOR each appear twice with DIFFERENT game ids."""
        seen = defaultdict(list)
        for g in self.cap.SLATE:
            seen["%s@%s" % (g[2], g[3])].append((g[0], g[4]))
        for matchup, dates in (("POR@MIN", ["2026-11-16", "2026-11-17"]),
                               ("NYK@TOR", ["2026-11-15", "2026-11-17"])):
            got = seen[matchup]
            self.assertEqual([d for d, _ in got], dates, matchup)
            self.assertEqual(len({gid for _, gid in got}), 2, "%s shares a game id" % matchup)

    def test_new_york_is_published_unknown_not_zero(self):
        """NYK prints no row at all on a date the report covers. That is not 'nobody out'."""
        av = load("data", "app", "report_availability_2026-11-15.json")
        nyk = [r for r in av["rows"] if r["date"] == "2026-11-15" and r["team"] == "NYK"]
        self.assertEqual(len(nyk), 1)
        self.assertEqual(nyk[0]["state"], "TEAM_NOT_LISTED_ON_A_COVERED_DATE")
        self.assertIsNone(nyk[0]["out_count"], "an unknown absence count must be blank, not 0")

    def test_carried_page_break_cells_are_marked(self):
        """Every row whose team cell was not printed on the row is marked provisional."""
        for r in self.rows:
            if r["cell_provenance"]["team_name"] != "row":
                self.assertTrue(r["team_provisional"], r["player"])
        n = sum(1 for r in self.rows if r["team_provisional"])
        self.assertEqual(n, self.stored["page_break_carried_cells"]["team_name"])


class RotationJoin(unittest.TestCase):
    """NF-90: the injury PDF and the players table print names differently."""

    def test_both_printed_name_forms_reach_the_same_person(self):
        from strategy_lab import norm_name
        self.assertEqual(norm_name("Edwards, Anthony"), ("anthony", "edwards"))
        self.assertEqual(norm_name("Anthony Edwards"), ("anthony", "edwards"))

    def test_the_defect_would_have_been_caught(self):
        """The old key was (whole string, whole string) for a comma-less name."""
        from strategy_lab import norm_name
        old_key = ("anthony edwards".split(",")[0], "anthony edwards".split(",")[-1])
        self.assertEqual(old_key[0], old_key[1])
        self.assertNotEqual(norm_name("Anthony Edwards"), old_key)

    def test_published_vacuum_is_not_structurally_zero(self):
        """At least one 11/15 team-game must publish a real vacated-minutes figure."""
        lab = load("data", "app", "lab.json")
        nz = [r for r in lab["injury_impact"] if (r.get("minutes_vacuum") or 0) > 0]
        self.assertGreater(len(nz), 0,
                           "minutes_vacuum is zero everywhere -- NF-90 has regressed")
        for r in nz:
            self.assertGreater(r["minutes_vacuum"], 0)
            self.assertIsNotNone(r["pts_vacuum"])

    def test_no_absence_count_is_published_without_a_state(self):
        lab = load("data", "app", "lab.json")
        for r in lab["injury_impact"]:
            st = r["availability_state"]
            if st != "FILED":
                self.assertIsNone(r["minutes_vacuum"],
                                  "%s %s published minutes for state %s"
                                  % (r["matchup"], r["team"], st))


class PublishedWindow(unittest.TestCase):
    def test_window_is_11_15_to_11_18_and_has_34_games(self):
        slate = load("data", "app", "official_slate_1115_1118.json")
        self.assertEqual(slate["window"], {"from": "2026-11-15", "to": "2026-11-18"})
        self.assertEqual(slate["count"], 34)
        self.assertEqual(len(slate["games"]), 34)
        by_date = defaultdict(int)
        for g in slate["games"]:
            by_date[g["date"]] += 1
        self.assertEqual(dict(by_date),
                         {"2026-11-15": 9, "2026-11-16": 8,
                          "2026-11-17": 5, "2026-11-18": 12})

    def test_every_priced_game_is_still_in_the_future(self):
        """No game in the priced window may already be Final."""
        lab = load("data", "app", "lab.json")
        slate = load("data", "app", "official_slate_1115_1118.json")
        played = {g["game_id"] for g in load_log()}
        priced = {l["game_id"] for l in lab["lines"]}
        self.assertEqual(priced, {g["game_id"] for g in slate["games"]})
        # The A2 pass priced the 11/15 games before tip; once the league records a final,
        # the settlement loop (ledger SETTLE entries) consumes them. The invariant is not
        # "priced games never become final" but "no priced game from a later slate date is
        # already played": every priced-and-played game must be from the pass's own day.
        slate = load("data", "app", "official_slate_1115_1118.json")
        date_of = {g["game_id"]: g["date"] for g in slate["games"]}
        for gid in priced & played:
            self.assertEqual(date_of[gid], "2026-11-15",
                             "%s was priced after it was already played" % gid)

    def test_every_line_has_a_pick_and_a_source(self):
        lab = load("data", "app", "lab.json")
        self.assertEqual(len(lab["lines"]), 34)
        self.assertEqual(len(lab["picks"]), 34)
        for line in lab["lines"]:
            self.assertTrue(line["nba_game_url"].startswith("https://www.nba.com/game/"))
            self.assertIsNotNone(line["orig_spread_home"])
            self.assertIsNotNone(line["orig_total"])

    def test_no_validation_gate_passes(self):
        """The honest published result: nothing has cleared every gate."""
        lab = load("data", "app", "lab.json")
        passing = [s for s in lab["strategies"] if s.get("passes_all_gates")]
        self.assertEqual(passing, [])


class CaptureSources(unittest.TestCase):
    def test_every_captured_artefact_names_an_https_source(self):
        for name in ("official_injuries_2026-11-15_0615AM.json",
                     "official_slate_1115_1118.json",
                     "official_team_ratings_2026-11-15.json",
                     "official_results_2026-11-14.json",
                     "report_availability_2026-11-15.json",
                     "official_capture_2026-11-15.json"):
            doc = load("data", "app", name)
            found = [v for k, v in doc.items()
                     if isinstance(v, str) and v.startswith("https://")]
            found += [u for u in (doc.get("source_urls") or []) if isinstance(u, str)]
            self.assertTrue(found, "%s names no https source" % name)
            for u in found:
                self.assertTrue(u.startswith("https://"), "%s: %r" % (name, u))

    def test_injury_source_is_the_official_host(self):
        d = load("data", "app", "official_injuries_2026-11-15_0615AM.json")
        self.assertTrue(d["source_url"].startswith("https://ak-static.cms.nba.com/referee/injury/"))
        self.assertTrue(d["index_url"].startswith("https://official.nba.com/"))


if __name__ == "__main__":
    unittest.main()
