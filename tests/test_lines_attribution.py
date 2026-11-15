"""Guards for the originated-lines table: every priced row must cite a page that
actually lists it, and every availability note must state the fact it reports.

Both were wrong on the live site on 2026-11-15 and neither was caught by any gate,
because a source link is only checked for being https:// and resolvable-looking, and
a chip's text is only checked for being present. These tests read the built artefacts,
so they run after scripts/assemble_canonical.py and scripts/build_app.py.
"""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL = os.path.join(ROOT, "data", "app", "canonical.json")
LINES_HTML = os.path.join(ROOT, "app", "lines.html")


def _canonical():
    with open(CANONICAL, encoding="utf-8") as fh:
        return json.load(fh)


def _cells(row):
    return [re.sub(r"<[^>]+>", "", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]


class TestLineAttribution(unittest.TestCase):
    """A row that cites the wrong date's schedule page is a wrong source, not a
    formatting quirk. F-7F3-03 records 47 cells already suffering this."""

    @classmethod
    def setUpClass(cls):
        cls.c = _canonical()
        cls.lines = cls.c["lines"]

    def test_there_is_a_window_to_check(self):
        self.assertGreater(len(self.lines), 0)

    def test_the_schedule_source_names_a_date_inside_its_own_window(self):
        """The schedule page is addressed by date. A line for 2026-11-17 that cites
        schedule?date=2026-11-14 points at a page that does not list it."""
        for line in self.lines:
            with self.subTest(game_id=line["game_id"]):
                m = re.search(r"schedule\?date=(\d{4}-\d{2}-\d{2})", line["source"])
                self.assertIsNotNone(m, f"{line['game_id']} cites no dated schedule page")
                cited = m.group(1)
                self.assertEqual(
                    cited,
                    self.c["slate"]["window"]["from"],
                    f"{line['game_id']} is on {line['date']} but cites the schedule "
                    f"page for {cited}; the window starts "
                    f"{self.c['slate']['window']['from']}")

    def test_every_line_cites_the_same_window_start(self):
        cited = {re.search(r"schedule\?date=(\d{4}-\d{2}-\d{2})", l["source"]).group(1)
                 for l in self.lines}
        self.assertEqual(len(cited), 1, f"mixed schedule dates across lines: {sorted(cited)}")

    def test_a_line_never_cites_a_page_older_than_the_line_itself(self):
        for line in self.lines:
            m = re.search(r"schedule\?date=(\d{4}-\d{2}-\d{2})", line["source"])
            if m:
                self.assertLessEqual(m.group(1), line["date"],
                                     f"{line['game_id']}: source predates its own date")


class TestAvailabilityNotes(unittest.TestCase):
    """Three distinct facts, three distinct labels. The first cut collapsed them all
    into "one side not on the report", which told a reader that 2026-11-16 had no
    official report when every one of those 16 sides is named on the 11/15 06:15 AM
    report reading NOT YET SUBMITTED."""

    STATES_ONE_CHIP = {
        "NO_OFFICIAL_REPORT_COVERS_THIS_DATE": "no official report covers this date",
        "NOT_YET_DUE": "not yet due",
        "TEAM_NOT_LISTED_ON_A_COVERED_DATE": "listed on no report despite a covered date",
    }

    @classmethod
    def setUpClass(cls):
        with open(LINES_HTML, encoding="utf-8") as fh:
            cls.html = fh.read()
        cls.c = _canonical()

    def _rows(self):
        rows = {}
        for m in re.finditer(r"<tr>.*?</tr>", self.html, re.S):
            cells = _cells(m.group(0))
            if len(cells) > 11 and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0]):
                rows[(cells[0], cells[2])] = cells
        return rows

    def test_every_line_renders(self):
        self.assertEqual(len(self._rows()), len(self.c["lines"]))

    def test_notes_match_the_state_they_report(self):
        for line in self.c["lines"]:
            st_a, st_h = (line.get("availability_state_away"),
                          line.get("availability_state_home"))
            key = (line["date"], f"{line['away']} @ {line['home']}")
            with self.subTest(game=key):
                cell = self._rows()[key][11]
                if st_a == st_h:
                    expected = self.STATES_ONE_CHIP.get(st_a)
                    if expected is None:
                        self.assertNotIn("not yet due", cell)
                        self.assertNotIn("no official report", cell)
                        self.assertNotIn("listed on no report", cell)
                    else:
                        self.assertIn(expected, cell,
                                      f"state {st_a} must print {expected!r}, got {cell!r}")
                else:
                    missing = "away" if st_a in self.STATES_ONE_CHIP else "home"
                    self.assertIn(f"{missing}: ", cell,
                                  f"differing per-side states must name the {missing} "
                                  f"side, got {cell!r}")

    def test_notes_are_separated_from_the_counts(self):
        """The live page rendered "4 one side not on the reportno report for this
        date" -- two inline chips with no whitespace between them."""
        for line in self.c["lines"]:
            key = (line["date"], f"{line['away']} @ {line['home']}")
            cell = self._rows()[key][11]
            # The defect was two adjacent inline chips with no whitespace between
            # them, so the second note's first letter touched the first note's last.
            self.assertNotRegex(cell, r"report(no|one|not yet|listed)",
                                f"two notes ran together: {cell!r}")
            self.assertNotRegex(cell, r"\)\(|\d[A-Za-z]",
                                f"a note ran into the counts: {cell!r}")

    def test_a_blank_count_is_the_same_character_everywhere(self):
        """The rest of the column writes the em dash literally, so a hand-written
        &mdash; entity here would be a second convention for the same fact."""
        for line in self.c["lines"]:
            key = (line["date"], f"{line['away']} @ {line['home']}")
            cell = self._rows()[key][11]
            self.assertNotIn("&", cell, f"an entity leaked into the cell: {cell!r}")

    def test_a_filed_side_with_nobody_out_prints_zero_not_a_dash(self):
        """Boston on 2026-11-15 has a filed report with no players out. That is a
        fact, and it must not be published as missing data."""
        found = False
        for line in self.c["lines"]:
            if line.get("availability_state_home") == "FILED" and line.get("out_count_home") == 0:
                key = (line["date"], f"{line['away']} @ {line['home']}")
                self.assertTrue(self._rows()[key][11].strip().endswith("0")
                                or " / 0" in self._rows()[key][11],
                                "a filed, empty report must print 0")
                found = True
        self.assertTrue(found, "expected at least one filed side with zero players out")


if __name__ == "__main__":
    unittest.main()
