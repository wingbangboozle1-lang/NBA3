"""tests for scripts/capture_04a81bce.py — O1-O4 official round capture.

Rules under test (standing brief): never infer; quarter vectors accepted only
when the sum gate passes; every published row carries an official source URL;
injury-report team attribution resolved from official books; model re-cut
outputs exist with the measured home-win rate, luck z, possessions x PPP, and
rest/B2B/3-in-4 + travel rows for the 2026-11-19 slate.
"""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "data" / "rounds" / "2026-11-19-04a81bce"
VERIFIED = ROUND / "verified"

spec = importlib.util.spec_from_file_location(
    "capture_04a81bce", ROOT / "scripts" / "capture_04a81bce.py")
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

# Quarter vectors verified from the official game books (sum == printed final).
EXPECTED_QUARTERS = {
    "20261116_ORLBOS": {"ORL": [20, 30, 25, 40], "BOS": [17, 24, 36, 28]},
    "20261116_MEMWAS": {"MEM": [33, 26, 42, 35], "WAS": [35, 34, 18, 33]},
    "20261116_CHICLE": {"CHI": [31, 17, 31, 36], "CLE": [25, 32, 31, 38]},
    "20261116_HOUMIA": {"HOU": [15, 31, 35, 29], "MIA": [29, 33, 39, 27]},
    "20261116_PHIBKN": {"PHI": None, "BKN": [26, 33, 36, 28]},
    "20261116_GSWNOP": {"GSW": [11, 25, 29, 29], "NOP": [35, 26, 32, 22]},
    "20261116_PORMIN": {"POR": None, "MIN": [26, 33, 28, 19]},
    "20261116_PHXDEN": {"PHX": [20, 36, 34, 27], "DEN": [24, 29, 29, 23]},
    "20261117_NYKTOR": {"NYK": [23, 31, 26, 31], "TOR": [29, 21, 33, 19]},
    "20261117_PORMIN": {"POR": [17, 31, 31, 26], "MIN": [29, 20, 30, 27]},
    "20261117_DETSAS": {"DET": [26, 29, 23, 27], "SAS": [33, 21, 18, 21]},
    "20261117_UTALAC": {"UTA": [35, 23, 30, 44], "LAC": [29, 33, 24, 21]},
    "20261117_CHALAL": {"CHA": [34, 32, 28, 17, 3], "LAL": [30, 29, 22, 30, 7]},
    "20261118_HOUIND": {"HOU": [39, 23, 31, 26], "IND": [28, 18, 30, 28]},
    "20261118_MEMCLE": {"MEM": None, "CLE": [37, 35, 27, 22]},
    "20261118_PHIORL": {"PHI": [27, 37, 28, 29], "ORL": [40, 29, 28, 19]},
    "20261118_MILMIA": {"MIL": [23, 25, 38, 44], "MIA": [34, 40, 38, 25]},
    "20261118_CHIBKN": {"CHI": [37, 39, 35, 26], "BKN": [21, 30, 26, 30]},
    "20261118_WASTOR": {"WAS": [29, 20, 29, 25], "TOR": [23, 24, 32, 20]},
    "20261118_DETNOP": {"DET": [31, 36, 25, 30], "NOP": [31, 29, 26, 23]},
    "20261118_ATLOKC": {"ATL": [31, 33, 19, 34], "OKC": [29, 22, 32, 29]},
    "20261118_BOSDEN": {"BOS": [30, 31, 19, 21], "DEN": [24, 25, 31, 25]},
    "20261118_GSWDAL": {"GSW": [25, 24, 23, 22], "DAL": [35, 27, 30, 24]},
    "20261118_UTALAL": {"UTA": None, "LAL": [34, 20, 22, 21]},
    "20261118_PHXSAC": {"PHX": None, "SAC": [31, 29, 24, 23]},
}

BLANK_FLAGS = {  # teams that must stay blank + flagged, never inferred
    ("20261116_PHIBKN", "PHI"), ("20261116_PORMIN", "POR"),
    ("20261118_MEMCLE", "MEM"), ("20261118_UTALAL", "UTA"),
    ("20261118_PHXSAC", "PHX"),
}


class Capture04a81bce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cap.main()
        cls.quarters = json.loads(
            (VERIFIED / "quarters_2026-11-16_18.json").read_text(encoding="utf-8"))
        cls.logs = json.loads(
            (VERIFIED / "player_game_logs.json").read_text(encoding="utf-8"))
        cls.injury = json.loads(
            (VERIFIED / "injury_report_2026-11-19.json").read_text(encoding="utf-8"))
        cls.recut = json.loads(
            (VERIFIED / "team_stats_recut_2026-11-19.json").read_text(encoding="utf-8"))
        cls.by_id = {g["game_id"]: g for g in cls.quarters["games"]}

    # ---- O1 quarters ----------------------------------------------------
    def test_all_25_games_present(self):
        self.assertEqual(len(self.quarters["games"]), 25)
        self.assertEqual(set(self.by_id), set(cap.FINALS))

    def test_quarter_vectors_match_verified_and_sum_to_final(self):
        for gid, teams in EXPECTED_QUARTERS.items():
            g = self.by_id[gid]
            for side, key in (("away", "away_quarters"), ("home", "home_quarters")):
                team = g[side]
                want = teams[team]
                got = g[key]
                if want is None:
                    self.assertIsNone(
                        got, f"{gid} {team}: expected blank, got {got}")
                    self.assertTrue(
                        any(team in f for f in g["flags"]),
                        f"{gid} {team}: blank without flag")
                else:
                    self.assertEqual(got, want, f"{gid} {team}")
                    final = g["final"]["away" if side == "away" else "home"]
                    self.assertEqual(sum(got), final, f"{gid} {team} sum gate")

    def test_blank_teams_are_exactly_the_flagged_set(self):
        found = set()
        for g in self.quarters["games"]:
            if g["away_quarters"] is None:
                found.add((g["game_id"], g["away"]))
            if g["home_quarters"] is None:
                found.add((g["game_id"], g["home"]))
        self.assertEqual(found, BLANK_FLAGS)

    def test_corrupt_table_rows_rejected_not_repaired(self):
        # Where a table row fails the sum gate it must be flagged as rejected
        # (never silently repaired); the sum-valid vector stays accepted.
        for gid, team, bad in (
                ("20261118_CHIBKN", "BKN", "21 30 26 22"),
                ("20261118_ATLOKC", "OKC", "30 32 32 30"),
                ("20261118_MEMCLE", "MEM", "30 41 30 24")):
            g = self.by_id[gid]
            self.assertTrue(any(bad in f and "rejected" in f for f in g["flags"]),
                            f"{gid} {team}: corrupt row not flagged")
        for gid, team in (("20261118_CHIBKN", "BKN"), ("20261118_ATLOKC", "OKC"),
                          ("20261116_CHICLE", "CLE")):
            g = self.by_id[gid]
            vec = g["home_quarters"] if g["home"] == team else g["away_quarters"]
            self.assertIsNotNone(vec)
            self.assertEqual(sum(vec), g["final"]["home" if g["home"] == team else "away"])

    def test_every_quarter_row_has_source_url(self):
        for g in self.quarters["games"]:
            self.assertTrue(g["source_url"].startswith("https://statsdmz.nba.com/pdfs/"))

    # ---- O3 player logs -------------------------------------------------
    def test_player_rows_identity(self):
        games = cap.load_games()
        seen = 0
        for g in games.values():
            for p in g["players"]:
                self.assertEqual(p["pts"], 2 * p["fgm"] + p["fg3m"] + p["ftm"],
                                 f"{g['game_id']} {p['player']}")
                self.assertEqual(p["reb"], p["oreb"] + p["dreb"],
                                 f"{g['game_id']} {p['player']}")
                seen += 1
        self.assertGreater(seen, 400)
        for r in self.logs["rows"]:
            self.assertTrue(r["source_url"].startswith("https://"))

    def test_injury_report_players_covered_or_flagged(self):
        covered = {cap.name_key(r["player"]) for r in self.logs["rows"]}
        for name, team in cap.INJURY_REPORT_PLAYERS:
            self.assertIn(cap.name_key(name), covered,
                          f"{name} ({team}) missing from logs")

    def test_players_without_games_left_blank(self):
        blanks = [r for r in self.logs["rows"] if r.get("flag")]
        self.assertTrue(blanks)
        for r in blanks:
            self.assertIsNone(r["pts"])
            self.assertIn("not inferred", r["flag"])

    def test_kuminga_pullin_min_attribution(self):
        rows = [r for r in self.logs["rows"]
                if cap.name_key(r["player"]) in
                (cap.name_key("Kuminga, Jonathan"), cap.name_key("Pullin, Zyon"))]
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r["team"], "MIN")

    # ---- O4 injury report -----------------------------------------------
    def test_injury_rows_and_attribution(self):
        self.assertGreaterEqual(len(self.injury["rows"]), 28)
        attributed = [r for r in self.injury["rows"] if "team_attribution" in r]
        self.assertEqual(len(attributed), 2)
        for r in attributed:
            self.assertEqual(
                r["team_attribution"]["resolved_team"], "Minnesota Timberwolves")
            self.assertEqual(len(r["team_attribution"]["evidence"]), 2)

    def test_consecutive_revisions_zero_diff(self):
        self.assertEqual(len(self.injury["consecutive_diffs"]), 3)
        for d in self.injury["consecutive_diffs"]:
            self.assertEqual((d["added"], d["removed"], d["status_changes"]), (0, 0, 0))
        self.assertEqual(len(self.injury["revisions"]), 5)
        for rev in self.injury["revisions"]:
            self.assertTrue(rev["source_url"].endswith(".pdf"))

    # ---- O2 re-cut ------------------------------------------------------
    def test_recut_covers_all_30_teams(self):
        self.assertEqual(len(self.recut["checks"]), 30)
        self.assertEqual(len(self.recut["luck"]), 30)
        self.assertEqual(len(self.recut["totals_poss_x_ppp"]), 30)

    def test_measured_home_win_rate(self):
        h = self.recut["home_court"]
        self.assertEqual(h["home_games"], h["home_wins"] + h["home_losses"])
        self.assertAlmostEqual(h["measured_home_win_rate"],
                               h["home_wins"] / h["home_games"], places=4)
        self.assertTrue(h["source_url"].startswith("https://www.nba.com/standings"))
        self.assertIn("not inferred", h["pinned_points_note"].lower())

    def test_luck_z_flagged_outside_noise(self):
        for r in self.recut["luck"]:
            self.assertIsNotNone(r["luck_z"])
            if abs(r["luck_z"]) > 2.0:
                self.assertTrue(r["outside_noise_2sd"])

    def test_totals_modeled_as_possessions_times_ppp(self):
        for r in self.recut["totals_poss_x_ppp"]:
            self.assertAlmostEqual(
                r["modeled_pts_for"], r["poss_per_game"] * r["ppp_for"], delta=0.2)
            self.assertIsNotNone(r["actual_pts_for"])

    def test_rest_b2b_travel_rows(self):
        rows = self.recut["rest_travel_1119"]
        self.assertEqual(len(rows), 8)  # 4 games x 2 teams
        for r in rows:
            self.assertIn(r["team"], {t for pair in cap.SLATE_1119 for t in pair})
            self.assertIn(r["site"], ("away", "home"))
            self.assertIn("b2b", r)
            self.assertIn("three_in_4", r)

    def test_minutes_redistribution(self):
        blocks = self.recut["minutes_redistribution"]
        self.assertEqual(len(blocks), 8)
        for b in blocks:
            if b["players"]:
                shares = [p["share"] for p in b["players"]]
                self.assertAlmostEqual(sum(shares), 1.0, places=2)
                self.assertIn("flagged/unverified", b["note"])


if __name__ == "__main__":
    unittest.main()
