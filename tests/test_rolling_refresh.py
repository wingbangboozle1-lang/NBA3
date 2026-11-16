"""Offline tests for the rolling refresh pipeline (session arena/43d54bfe-nba3).

Everything replays from fixtures generated in-process with pypdf — no network. The
fixtures reproduce the official artifact layouts observed in the committed verbatim
transcriptions (data/app/official_injuries_2026-11-15_0615AM_raw.md and
data/app/gamebooks/*.md).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

import rolling_promote as rp                      # noqa: E402
import rolling_gates as rg                        # noqa: E402


def make_pdf(text: str) -> bytes:
    """Minimal single-page PDF containing `text`, produced with pypdf itself.

    Each line of `text` is drawn on its own line (Tj + T*) so extraction round-trips.
    """
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    lines = [l for l in text.splitlines() or [text]]
    body = ["BT", "/F1 9 Tf", "40 760 Td", "12 TL"]
    for l in lines:
        body.append(f"({esc(l)}) Tj T*")
    body.append("ET")
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = DecodedStreamObject()
    stream.set_data("\n".join(body).encode("latin-1", "replace"))
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    resources = DictionaryObject()
    resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): font})
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    writer.write(buf)
    buf.close()
    return open(buf.name, "rb").read()


GAMEBOOK_TEXT = """Saturday, November 14, 2026 Test Arena
Officials: #19 Test Crew

| VISITOR: Brooklyn Nets (3-9) |  |  |
| 21 Noah Clowney | F | 35:01 | 6 | 14 | 0 | 0 | 2 | 5 | 7 | 3 | 4 | 0 | 2 | 3 | -7 | 15 |
| 30 Julius Randle | F | 31:23 | 8 | 16 | 0 | 0 | 3 | 6 | 4 | 5 | 2 | 3 | 4 | 0 | 0 | -18 | 22 |

| SCORE BY PERIOD | 1 | 2 | 3 | 4 | FINAL |
| Nets | 23 | 31 | 30 | 26 | 110 |
| GRIZZLIES | 38 | 33 | 32 | 26 | 129 |

Biggest Lead: Nets 15, GRIZZLIES 3
"""

GAMEBOOK_OT_TEXT = """| SCORE BY PERIOD | 1 | 2 | 3 | 4 | (OT: 18) | FINAL |
| Bulls | 29 | 29 | 30 | 29 | 10 | 127 |
| MAGIC | 26 | 31 | 29 | 31 | 12 | 129 |
"""


class GameBookParserTests(unittest.TestCase):
    def test_parses_quarters_and_final(self):
        gb = rp.parse_gamebook(GAMEBOOK_TEXT)
        self.assertIsNotNone(gb)
        self.assertEqual(gb["away_q"], [23, 31, 30, 26])
        self.assertEqual(gb["home_q"], [38, 33, 32, 26])
        self.assertEqual(gb["away_final"], 110)
        self.assertEqual(gb["home_final"], 129)
        self.assertEqual(gb["away_name"], "Nets")
        self.assertEqual(gb["home_name"], "GRIZZLIES")

    def test_ot_value_is_kept_and_final_is_last_number(self):
        gb = rp.parse_gamebook(GAMEBOOK_OT_TEXT)
        self.assertIsNotNone(gb)
        self.assertEqual(gb["away_q"], [29, 29, 30, 29])
        self.assertEqual(gb["away_final"], 127)
        self.assertEqual(gb["home_final"], 129)

    def test_returns_none_when_no_score_block(self):
        self.assertIsNone(rp.parse_gamebook("no score by period here\nBulls 1 2 3 4 100\n"))


INJURY_TEXT = """Injury Report: 11/15/26 06:15 AM

| Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason |
11/15/2026 01:00 (ET) IND@PHI Indiana Pacers Furphy, Johnny Out Injury/Illness - Right ACL Repair
11/15/2026 01:00 (ET) IND@PHI Indiana Pacers Haliburton, Tyrese Out Injury/Illness - Left Hamstring Strain
Indiana Pacers McConnell, T.J. Probable Injury/Illness - Right Hamstring Strain
11/15/2026 04:00 (ET) LAL@PHX Los Angeles Lakers Reaves, Austin Out Injury/Illness - Left Heel Contusion
"""


class InjuryParserTests(unittest.TestCase):
    def test_parses_full_rows_with_team_and_matchup(self):
        rows = rp.parse_injury_report(INJURY_TEXT)
        parsed = [r for r in rows if r.get("parsed")]
        self.assertEqual(len(parsed), 4)
        first = parsed[0]
        self.assertEqual(first["player"], "Furphy, Johnny")
        self.assertEqual(first["team"], "Indiana Pacers")
        self.assertEqual(first["status"], "Out")
        self.assertEqual(first["matchup"], "IND@PHI")
        self.assertIn("Right ACL Repair", first["reason"])

    def test_row_missing_leading_cells_stays_flagged_not_inferred(self):
        rows = rp.parse_injury_report(INJURY_TEXT)
        # the McConnell row has no date/time/matchup: name+status parse verbatim, the team
        # is recognised because the line itself carries the club name, and the missing
        # cells stay None
        mc = next(r for r in rows if str(r.get("player", "")).startswith("McConnell"))
        self.assertEqual(mc["status"], "Probable")
        self.assertEqual(mc["team"], "Indiana Pacers")
        self.assertIsNone(mc["matchup"])
        self.assertIsNone(mc["game_date"])
        self.assertTrue(mc.get("parsed"))

    def test_markdown_table_rows_parse(self):
        md = ("| 11/15/2026 | 01:00 (ET) | IND@PHI | Indiana Pacers | Furphy, Johnny | Out "
              "| Injury/Illness - Right ACL Repair / Surgery |")
        rows = rp.parse_injury_report(md)
        self.assertTrue(rows[0]["parsed"])
        self.assertEqual(rows[0]["player"], "Furphy, Johnny")
        self.assertEqual(rows[0]["team"], "Indiana Pacers")

    def test_garbage_rows_stay_unparsed(self):
        rows = rp.parse_injury_report("Some line without a status at all\n")
        self.assertFalse(any(r.get("parsed") for r in rows))


def _write(path, content: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)


class PromoteAndGatesTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="rolling-test-")
        # point the module paths at the temp tree
        self._old = (rp.ROOT, rp.APP, rp.REFRESH, rp.ROLLING, rg.APP, rg.REFRESH, rg.ROLLING)
        rp.APP = os.path.join(self.base, "data", "app")
        rp.REFRESH = os.path.join(rp.APP, "refresh")
        rp.ROLLING = os.path.join(rp.APP, "rolling")
        rg.APP, rg.REFRESH, rg.ROLLING = rp.APP, rp.REFRESH, rp.ROLLING
        self.stamp = "T-TEST"
        self.out_dir = os.path.join(rp.REFRESH, self.stamp)
        os.makedirs(self.out_dir, exist_ok=True)
        man = {"stamp": self.stamp, "today_et": "2026-11-15",
               "newest_injury_report": "2026-11-15-06_15AM",
               "artifacts": [
                   {"url": "https://official.nba.com/nba-injury-report-2026-27-season/",
                    "retrieved_utc": self.stamp, "sha256": "a" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/injury_index.html"},
                   {"url": "https://ak-static.cms.nba.com/referee/injury/"
                           "Injury-Report_2026-11-15-06_15AM.pdf",
                    "retrieved_utc": self.stamp, "sha256": "b" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/Injury-Report_2026-11-15-06_15AM.pdf"},
                   {"url": "https://www.nba.com/games?date=2026-11-15",
                    "retrieved_utc": self.stamp, "sha256": "c" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/games_2026-11-15.html"},
                   {"url": "https://www.nba.com/stats/teams/traditional",
                    "retrieved_utc": self.stamp, "sha256": "d" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/teams_0.html"},
                   {"url": "https://www.nba.com/stats/teams/opponent",
                    "retrieved_utc": self.stamp, "sha256": "e" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/teams_1.html"},
                   {"url": "https://www.nba.com/stats/teams/advanced",
                    "retrieved_utc": self.stamp, "sha256": "f" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/teams_2.html"},
                   {"url": "https://statsdmz.nba.com/pdfs/20261114/20261114_BKNMEM.pdf",
                    "retrieved_utc": self.stamp, "sha256": "1" * 64, "bytes": 10,
                    "file": "data/app/refresh/T-TEST/20261114_BKNMEM.pdf"},
               ],
               "errors": [], "gamebooks": 1}
        with open(os.path.join(self.out_dir, "manifest.json"), "w") as fh:
            json.dump(man, fh)
        _write(os.path.join(self.out_dir, "Injury-Report_2026-11-15-06_15AM.pdf"),
               make_pdf(INJURY_TEXT))
        _write(os.path.join(self.out_dir, "20261114_BKNMEM.pdf"), make_pdf(GAMEBOOK_TEXT))
        # promoted slate covering today..today+3
        slate = {"source_url": "https://www.nba.com/games?date=2026-11-15",
                 "retrieved_utc": self.stamp,
                 "window": {"from": "2026-11-15", "to": "2026-11-18"},
                 "count": 4,
                 "games": [{"date": d, "time_et": None, "away": a, "home": h,
                            "game_id": gid,
                            "game_url": f"https://www.nba.com/game/{a.lower()}-vs-{h.lower()}-{gid}",
                            "source": f"https://www.nba.com/games?date={d}"}
                           for d, a, h, gid in
                           [("2026-11-15", "IND", "PHI", "0022600236"),
                            ("2026-11-16", "ORL", "BOS", "0022600245"),
                            ("2026-11-17", "MIL", "TOR", "0022600250"),
                            ("2026-11-18", "DEN", "LAL", "0022600256")]]}
        with open(os.path.join(rp.APP, "official_slate_current.json"), "w") as fh:
            json.dump(slate, fh)

    def tearDown(self):
        rp.ROOT, rp.APP, rp.REFRESH, rp.ROLLING = self._old[:4]
        rg.APP, rg.REFRESH, rg.ROLLING = self._old[4:]
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)

    def test_pdf_text_extraction_roundtrip(self):
        txt = rp.pdf_text(os.path.join(self.out_dir,
                                       "Injury-Report_2026-11-15-06_15AM.pdf"))
        self.assertIsNotNone(txt)
        self.assertIn("Haliburton, Tyrese", txt)

    def test_promotion_and_gates_end_to_end(self):
        rep = rp.main_with_paths(self.stamp)
        self.assertTrue(rep["injuries"]["promoted"])
        self.assertGreater(rep["results"]["rows"], 0)
        self.assertEqual(rep["results"]["settled"], rep["results"]["rows"])
        # every row carries provenance + settlement stamp
        res = json.load(open(os.path.join(rp.ROLLING, "results.json")))
        for g in res["games"]:
            self.assertIn("https://statsdmz.nba.com/", g["source_url"])
            self.assertIn("settled at", g["settlement_stamp"])
        gates = rg.evaluate(self.stamp)
        self.assertTrue(gates["pass"],
                        "gates failed: " + json.dumps(gates["gates"], indent=1))
        by_id = {g["id"]: g for g in gates["gates"]}
        self.assertTrue(by_id["G2_injury_current"]["pass"])
        self.assertTrue(by_id["G4_results_verified"]["pass"])
        self.assertEqual(by_id["G4_results_verified"]["detail"],
                         "1 official game books fetched, 1 verified (quarter sums == "
                         "final), 0 unparseable, 0 quarter mismatches")

    def test_unparseable_gamebook_fails_g4(self):
        _write(os.path.join(self.out_dir, "20261113_DENNOP.pdf"),
               make_pdf("no score by period in this one\n"))
        rp.main_with_paths(self.stamp)
        gates = rg.evaluate(self.stamp)
        by_id = {g["id"]: g for g in gates["gates"]}
        self.assertFalse(by_id["G4_results_verified"]["pass"])

    def test_missing_slate_days_fail_g3(self):
        rp.main_with_paths(self.stamp)
        slate_path = os.path.join(rp.APP, "official_slate_current.json")
        slate = json.load(open(slate_path))
        slate["games"] = [g for g in slate["games"] if g["date"] == "2026-11-17"]
        slate["window"] = {"from": "2026-11-17", "to": "2026-11-17"}
        with open(slate_path, "w") as fh:
            json.dump(slate, fh)
        gates = rg.evaluate(self.stamp)
        by_id = {g["id"]: g for g in gates["gates"]}
        self.assertFalse(by_id["G3_slate_window"]["pass"])

    def test_injury_delta_diffs_consecutive_reports(self):
        rp.main_with_paths(self.stamp)
        # archive a second report where one player's status changed
        changed = INJURY_TEXT.replace("Haliburton, Tyrese Out",
                                      "Haliburton, Tyrese Questionable")
        new_name = "Injury-Report_2026-11-15-09_00AM.pdf"
        _write(os.path.join(self.out_dir, new_name), make_pdf(changed))
        man_path = os.path.join(self.out_dir, "manifest.json")
        man = json.load(open(man_path))
        man["newest_injury_report"] = "2026-11-15-09_00AM"
        man["artifacts"].append({"url": "https://ak-static.cms.nba.com/referee/injury/"
                                        + new_name, "retrieved_utc": self.stamp,
                                 "sha256": "9" * 64, "bytes": 10,
                                 "file": f"data/app/refresh/{self.stamp}/{new_name}"})
        with open(man_path, "w") as fh:
            json.dump(man, fh)
        rp.main_with_paths(self.stamp)
        delta = json.load(open(os.path.join(rp.ROLLING, "injury_delta.json")))
        self.assertEqual(delta["newest_report"], new_name)
        self.assertIn({"team": "Indiana Pacers", "player": "Haliburton, Tyrese",
                       "was": "Out", "now": "Questionable"}, delta["changes"])


if __name__ == "__main__":
    unittest.main()
