"""Tests for the 11/14/26 01:30 PM ET injury-freshness audit (session 736efb4b).

Run: python3 -m unittest discover -s audit_736efb4b -p 'test_*.py'
"""
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CAP = json.loads((HERE / "data" / "official_injury_report_2026-11-14_0130PM.json").read_text(encoding="utf-8"))
DELTA = json.loads((HERE / "data" / "delta_1330PM_vs_canonical.json").read_text(encoding="utf-8"))
RAW_LINES = (HERE / "data" / "official_injury_report_2026-11-14_0130PM_raw.md").read_text(encoding="utf-8").splitlines()
OFFICIAL = ("nba.com",)
DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")
TIME_RE = re.compile(r"\d{2}:\d{2} \(ET\)")


class Tables(HTMLParser):
    """Collects the cells of every tbody row and every href on a generated page."""

    def __init__(self):
        super().__init__()
        self.rows, self.hrefs, self.ids = [], [], set()
        self.in_tbody = False
        self.row = None
        self.cell_hrefs = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "tbody":
            self.in_tbody = True
        if tag == "tr" and self.in_tbody:
            self.row = []
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            if self.row is not None:
                self.row.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "tbody":
            self.in_tbody = False


def parse(name):
    p = Tables()
    p.feed((HERE / name).read_text(encoding="utf-8"))
    return p


class CaptureTests(unittest.TestCase):
    def test_counts_match_the_published_totals(self):
        c = CAP["checks"]
        self.assertEqual(c["data_lines_seen"], 68)
        self.assertEqual(c["rows_transcribed"], 67)
        self.assertEqual(c["lines_not_transcribed"], 1)
        self.assertEqual(c["player_rows_parsed"], 50)
        self.assertEqual(c["not_yet_submitted_rows_parsed"], 17)
        self.assertEqual(c["not_yet_submitted_on_garbled_line"], 2)
        self.assertEqual(c["not_yet_submitted_occurrences_in_raw"], 19)

    def test_status_counts_equal_raw_text_counts(self):
        self.assertTrue(CAP["checks"]["status_counts_match_raw"])
        self.assertEqual(CAP["checks"]["status_counts_parsed"],
                         {"Out": 31, "Probable": 6, "Doubtful": 2, "Available": 4, "Questionable": 7})

    def test_every_printed_value_is_in_its_raw_line(self):
        for r in CAP["rows"]:
            raw = RAW_LINES[r["raw_line"] - 1]
            for field in ("player", "status", "reason", "team_name", "matchup", "game_time_et", "game_date"):
                if r[field]:
                    self.assertIn(r[field], raw, f"line {r['raw_line']}: {field}={r[field]!r} not in raw")

    def test_blank_is_blank_when_the_raw_line_prints_nothing(self):
        # A blank date, time or matchup must not be filled in: the raw line must not print one either.
        for r in CAP["rows"]:
            raw = RAW_LINES[r["raw_line"] - 1]
            if not r["game_date"]:
                self.assertIsNone(DATE_RE.search(raw), f"line {r['raw_line']} prints a date that was not kept")
            if not r["game_time_et"]:
                self.assertIsNone(TIME_RE.search(raw), f"line {r['raw_line']} prints a time that was not kept")
            if not r["team_name"]:
                self.assertFalse(any(t in raw for t in ("Nets", "Nuggets", "Pelicans", "Mavericks", "Cavaliers",
                                                        "Grizzlies", "Bulls", "Timberwolves", "Pistons", "Heat",
                                                        "Pacers", "76ers", "Lakers", "Suns", "Hornets", "Clippers",
                                                        "Spurs", "Jazz", "Celtics", "Knicks", "Raptors", "Rockets",
                                                        "Wizards", "Hawks", "Bucks", "Thunder", "Kings")),
                                 f"line {r['raw_line']} prints a team that was not kept")

    def test_flagged_team_blank_rows_are_exactly_the_rows_without_a_team(self):
        blank = [r for r in CAP["rows"] if r["row_kind"] == "player" and not r["team_name"]]
        self.assertEqual(len(blank), 13)
        for r in blank:
            self.assertIn("team not printed on this row (cell blank in extraction)", r["flags"])

    def test_unparsed_line_is_the_garbled_one_and_is_not_transcribed(self):
        self.assertEqual(len(CAP["unparsed_lines"]), 1)
        self.assertIn("Milwaukee Bucks Oklahoma City Thunder", CAP["unparsed_lines"][0]["raw"])
        self.assertFalse(any(r["raw_line"] == CAP["unparsed_lines"][0]["raw_line"] for r in CAP["rows"]))

    def test_source_is_the_official_nba_pdf(self):
        self.assertEqual(urlparse(CAP["source_url"]).hostname, "ak-static.cms.nba.com")
        self.assertTrue(CAP["source_url"].endswith("Injury-Report_2026-11-14_01_30PM.pdf"))


class DeltaTests(unittest.TestCase):
    def test_outcomes_add_up(self):
        s = DELTA["summary"]
        self.assertEqual(s["unchanged"] + s["status_changed"], DELTA["counts"]["player_rows_in_canonical"])
        self.assertEqual(s["unchanged"] + s["status_changed"] + s["new_in_1330_report"],
                         DELTA["counts"]["player_rows_in_1330_report"])
        self.assertEqual(len(DELTA["canonical_players_not_in_1330"]), 0)

    def test_status_changes_are_the_four_expected_players(self):
        changed = sorted((o["player"], o["status_canonical"], o["status_1330"])
                         for o in DELTA["player_outcomes"] if o["outcome"] == "status_changed")
        self.assertEqual(changed, [
            ("Brown Jr., Mikel", "Questionable", "Probable"),
            ("Christie, Max", "Questionable", "Doubtful"),
            ("Harkless, Elijah", "Questionable", "Available"),
            ("Jones, Isaac", "Questionable", "Available"),
        ])

    def test_no_duplicate_player_names(self):
        self.assertEqual(DELTA["duplicate_player_names_canonical"], [])
        self.assertEqual(DELTA["duplicate_player_names_1330"], [])

    def test_a_team_with_a_blank_matchup_is_not_attributed_to_a_game_outside_the_slate(self):
        for o in DELTA["team_not_yet_submitted_outcomes"]:
            self.assertIn(o["outcome"], {"team_now_reporting_players", "team_players_printed_matchup_blank",
                                         "still_not_yet_submitted", "still_not_yet_submitted_matchup_blank",
                                         "unverified_garbled_line_only", "not_matched_in_1330_report"})


class PageTests(unittest.TestCase):
    def check_page(self, name):
        p = parse(name)
        ids = p.ids
        for h in p.hrefs:
            if h.startswith("#"):
                self.assertIn(h[1:], ids, f"{name}: broken anchor {h}")
            elif not h.startswith(("http://", "https://", "mailto:")):
                self.assertTrue((HERE / h.split("#")[0]).exists() or (HERE.parent / h.split("#")[0]).exists(),
                                f"{name}: broken relative link {h}")
        return p

    def test_index_links_resolve(self):
        self.check_page("index.html")

    def test_flagged_links_resolve(self):
        self.check_page("flagged.html")

    def test_every_table_row_has_an_official_source_link(self):
        for name in ("index.html", "flagged.html"):
            p = parse(name)
            self.assertGreater(len(p.rows), 0, name)
            for i, row in enumerate(p.rows, 1):
                sources = [h for h in row if urlparse(h).scheme == "https"
                           and any(urlparse(h).hostname == d or urlparse(h).hostname.endswith("." + d)
                                   for d in OFFICIAL)]
                self.assertTrue(sources, f"{name}: table row {i} has no official-source link")

    def test_flags_page_lists_all_ten_ids(self):
        text = (HERE / "flagged.html").read_text(encoding="utf-8")
        for n in range(1, 11):
            self.assertIn(f"F736-{n:02d}", text)

    def test_index_states_the_no_re_run_limit(self):
        text = (HERE / "index.html").read_text(encoding="utf-8")
        self.assertIn("does not re-run the model", text)


if __name__ == "__main__":
    unittest.main()
