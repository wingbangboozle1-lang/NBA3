"""Tests for round 2026-11-19-93becd26 (session arena/93becd26-nba3).

Pinned facts here come from the committed official captures (injury report PDFs and
box-score game books) under data/rounds/2026-11-19-93becd26/captures/. Nothing is
asserted that is not printed in those captures or in a source they link.
"""
import hashlib
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUND = os.path.join(ROOT, "data", "rounds", "2026-11-19-93becd26")
CAP = os.path.join(ROUND, "captures")
SCRIPT = os.path.join(ROOT, "scripts", "capture_93becd26.py")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import capture_93becd26 as cap93  # noqa: E402


def load(name):
    with open(os.path.join(ROUND, name), encoding="utf-8") as fh:
        return json.load(fh)


class CaptureCheckTests(unittest.TestCase):
    def test_check_mode_is_byte_stable(self):
        files = cap93.render()
        for name, blob in files.items():
            path = os.path.join(ROUND, name)
            self.assertTrue(os.path.exists(path), f"missing {name}")
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), blob, f"drift in {name}")

    def test_check_mode_exits_zero(self):
        r = subprocess.run([sys.executable, SCRIPT, "--check"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ManifestTests(unittest.TestCase):
    def test_every_capture_hash_matches(self):
        man = load("manifest.json")
        self.assertEqual(man["round"], "2026-11-19-93becd26")
        self.assertEqual(len(man["files"]), 9)
        for name, meta in man["files"].items():
            with open(os.path.join(CAP, name), "rb") as fh:
                data = fh.read()
            self.assertEqual(hashlib.sha256(data).hexdigest(), meta["sha256"], name)
            self.assertEqual(len(data), meta["bytes"], name)
            self.assertTrue(str(meta["source_url"]).startswith("https://"), name)

    def test_report_and_index_sources(self):
        man = load("manifest.json")
        self.assertIn("Injury-Report_2026-11-19_03_00AM.pdf", man["files"][cap93.INJ_CURRENT]["source_url"])
        self.assertIn("Injury-Report_2026-11-19_02_45AM.pdf", man["files"][cap93.INJ_PREVIOUS]["source_url"])


class InjuryParseTests(unittest.TestCase):
    def setUp(self):
        self.parsed = load("injury_parsed.json")

    def test_revisions_and_counts(self):
        cur, prev = self.parsed["current"], self.parsed["previous"]
        self.assertEqual(cur["revision"], "11/19/26 03:00 AM")
        self.assertEqual(prev["revision"], "11/19/26 02:45 AM")
        self.assertEqual(len(cur["players"]), 23)
        self.assertEqual(len(prev["players"]), 23)

    def test_consecutive_diff_identical(self):
        d = self.parsed["delta"]
        self.assertEqual(d["from_revision"], "11/19/26 02:45 AM")
        self.assertEqual(d["to_revision"], "11/19/26 03:00 AM")
        self.assertTrue(d["identical"])
        self.assertEqual(d["added"], [])
        self.assertEqual(d["removed"], [])
        self.assertEqual(d["changed"], [])

    def test_blank_team_rows_recorded_as_printed(self):
        blanks = [r for r in self.parsed["current"]["players"] if not r["team_printed"]]
        self.assertEqual([r["player"] for r in blanks],
                         ["Kuminga, Jonathan", "Pullin, Zyon"])

    def test_layout_shifted_rows_not_realigned(self):
        shifted = self.parsed["current"]["shifted_rows"]
        self.assertGreaterEqual(len(shifted), 10)
        self.assertTrue(any("NOT YET SUBMITTED" in r["c2"] for r in shifted))


class PlayerLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load("player_logs_injury_2026-11-19.json")

    def test_counts(self):
        self.assertEqual(self.p["counts"], {
            "report_player_rows": 23, "team_printed": 21, "team_blank_on_report": 2,
            "log_played": 6, "log_dnd": 2, "log_inactive": 15, "unmatched": 0})
        self.assertEqual(self.p["problems"], [])

    def test_every_row_has_report_source(self):
        for r in self.p["rows"]:
            self.assertTrue(r["sources"]["injury_report"].startswith("https://"), r["player"])
            self.assertTrue(r["player"])

    def test_every_row_with_a_log_has_gamebook_source(self):
        for r in self.p["rows"]:
            if r["game_log"]:
                self.assertTrue(r["game_log"]["gamebook_url"].startswith("https://"), r["player"])
                self.assertTrue(r["game_log"]["game_url"].startswith("https://"), r["player"])
            else:
                self.assertTrue(r["flags"], r["player"])

    def test_played_rows_pinned_from_official_game_books(self):
        pinned = {
            "Martinelli, Nick": ("LAC", "UTA", "04:22", 0, 1, 0),
            "Harper, Dylan": ("SAS", "DET", "34:32", 20, 4, 2),
            "Beringer, Joan": ("MIN", "POR", "25:30", 3, 13, 0),
            "Camara, Toumani": ("POR", "MIN", "32:53", 10, 8, 1),
            "Carlson, Branden": ("POR", "MIN", "14:24", 6, 1, 0),
            "Williams III, Robert": ("POR", "MIN", "15:34", 6, 8, 4),
        }
        got = {r["player"]: r for r in self.p["rows"] if r["game_log"]
               and r["game_log"]["kind"] == "played"}
        self.assertEqual(set(got), set(pinned))
        for player, (team, opp, mmss, pts, reb, ast) in pinned.items():
            lg = got[player]["game_log"]
            self.assertEqual(got[player]["team"], team, player)
            self.assertEqual(lg["opponent"], opp, player)
            self.assertEqual(lg["min_mmss"], mmss, player)
            self.assertEqual((lg["pts"], lg["reb"], lg["ast"]), (pts, reb, ast), player)
            self.assertTrue(lg["scoring_identity_ok"], player)
            self.assertTrue(lg["reb_identity_ok"], player)

    def test_blank_team_rows_come_from_gamebook_with_flag(self):
        for name in ("Kuminga, Jonathan", "Pullin, Zyon"):
            row = next(r for r in self.p["rows"] if r["player"] == name)
            self.assertEqual(row["team"], "MIN", name)
            self.assertEqual(row["team_source"], "gamebook", name)
            self.assertTrue(any(f.startswith("F-93-01") for f in row["flags"]), name)

    def test_krejci_diacritic_flag(self):
        row = next(r for r in self.p["rows"] if r["player"] == "Krejci, Vit")
        self.assertTrue(any("F-93-06" in f for f in row["flags"]))
        self.assertEqual(row["game_log"]["kind"], "inactive")

    def test_reason_equality_checked_where_both_print(self):
        for r in self.p["rows"]:
            if r["match"] and r["match"]["reason_checked"]:
                self.assertEqual(
                    cap93.norm_reason(r["game_log"]["printed_reason"]),
                    cap93.norm_reason(r["report"]["reason"]), r["player"])

    def test_report_status_is_for_todays_game_not_the_log(self):
        # statuses in the report are for the 11/19 game; logs are the 11/17 game.
        # The two page-break rows print no game date (blank as printed).
        for r in self.p["rows"]:
            # section-2 rows print no Game Date cell (blank as printed, never filled)
            self.assertIn(r["report"]["game_date"], ("11/19/2026", ""), r["player"])
            if r["game_log"]:
                self.assertEqual(r["game_log"]["date"], "2026-11-17", r["player"])

    def test_no_played_row_without_flags_is_unsourced(self):
        for r in self.p["rows"]:
            if r["game_log"] and r["game_log"]["kind"] == "played":
                self.assertIn("gamebook_url", r["game_log"])


class GamesAndScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load("player_logs_injury_2026-11-19.json")
        cls.sched = json.load(open(os.path.join(CAP, "schedule_2026-11-18_finals.json"),
                                   encoding="utf-8"))

    def test_three_games_all_minutes_reconcile(self):
        self.assertEqual(len(self.p["games"]), 3)
        for g in self.p["games"]:
            self.assertEqual(g["header_date_printed"],
                             "Tuesday, November 17, 2026", g["gamebook_url"])
            for code, t in g["teams"].items():
                self.assertTrue(t["minutes_ok"], f"{g['game_id']} {code}")
                self.assertEqual(t["total_pts"], g["periods"][code]["final"], code)
                for q in g["periods"][code]["quarters"]:
                    self.assertIsInstance(q, int)

    def test_finals_crosscheck_matches_merged_official_capture(self):
        self.assertEqual(len(self.p["finals_crosscheck_vs_merged_capture"]), 3)
        for x in self.p["finals_crosscheck_vs_merged_capture"]:
            self.assertTrue(x["match"], x)

    def test_schedule_absence_proof(self):
        self.assertTrue(self.p["recent_game_selection"]["schedule_absent_check_ok"])
        self.assertEqual(len(self.sched["rows"]), 12)
        absent = {"LA Clippers", "San Antonio Spurs", "Minnesota Timberwolves",
                  "Portland Trail Blazers"}
        for r in self.sched["rows"]:
            self.assertNotIn(r["away"], absent)
            self.assertNotIn(r["home"], absent)
        for r in self.sched["rows"]:
            self.assertTrue(r["game_url"].startswith("https://www.nba.com/game/"))

    def test_delta_and_report_urls(self):
        self.assertTrue(self.p["consecutive_diff"]["identical"])
        self.assertIn("03_00AM", self.p["report_url"])
        self.assertIn("02_45AM", self.p["previous_report_url"])


if __name__ == "__main__":
    unittest.main()
