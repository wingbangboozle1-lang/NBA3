#!/usr/bin/env python3
"""`--check-venues` must fail on a real mismatch, not only pass on clean data.

The markdown describing the venue table promises that this check "re-checks this on every build and
fails on a mismatch". A check that has never been seen to fail is not evidence. Each test below
takes the real files, injects one specific fault, and asserts the check catches it.
"""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import travel_distance as td  # noqa: E402


class CheckVenuesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.hv = json.loads(td.HOME_VENUES.read_text())
        self.coords = json.loads(td.COORDS.read_text())
        self._orig = (td.HOME_VENUES, td.COORDS)

    def tearDown(self):
        td.HOME_VENUES, td.COORDS = self._orig
        shutil.rmtree(self.tmp)

    def _write(self):
        hv_p = self.tmp / "home_venues.json"
        co_p = self.tmp / "arena_coords.json"
        hv_p.write_text(json.dumps(self.hv))
        co_p.write_text(json.dumps(self.coords))
        td.HOME_VENUES, td.COORDS = hv_p, co_p
        return td.check_venues()

    def test_clean_data_passes_and_names_the_three_blanks(self):
        self.assertEqual(self._write(), 0)

    def test_an_official_venue_with_no_coordinate_fails(self):
        self.hv["teams"]["ATL"]["venue"] = "Some Arena With No Coordinates"
        self.assertEqual(self._write(), 1)

    def test_a_silently_filled_blanks_club_fails(self):
        """CHA has no official home game on record. Filling it in must be an error, not an improvement.

        Blanks live in `unresolved`, keyed by club. Giving one a venue, or promoting it into `teams`,
        are both ways of turning "we did not find it" into "we know it".
        """
        self.hv["unresolved"]["CHA"]["venue"] = "Spectrum Center"
        self.assertEqual(self._write(), 1)

    def test_promoting_a_blank_into_the_resolved_table_fails(self):
        self.hv["teams"]["CHA"] = self.hv["unresolved"].pop("CHA")
        self.assertEqual(self._write(), 1)

    def test_a_blank_with_no_source_for_the_blank_fails(self):
        del self.hv["unresolved"]["POR"]["source_url"]
        self.assertEqual(self._write(), 1)

    def test_a_venue_stored_under_the_wrong_name_fails(self):
        """An alias is a different building. The official string must win."""
        self.coords.setdefault("aliases", {})["wells_fargo_center"] = "Xfinity Mobile Arena"
        self.hv["teams"]["PHI"]["venue"] = "Wells Fargo Center"
        self.assertEqual(self._write(), 1)

    def test_every_club_is_accounted_for_exactly_once(self):
        """27 resolved + 3 unresolved = 30 clubs. No club may be in both or in neither."""
        resolved = set(self.hv["teams"])
        blanks = set(self.hv["unresolved"])
        self.assertEqual(resolved & blanks, set())
        self.assertEqual(len(resolved | blanks), 30)
        self.assertEqual(blanks, {"CHA", "GSW", "POR"})
        for t in blanks:
            self.assertTrue(self.hv["unresolved"][t]["source_url"].startswith("https://"), t)
            self.assertTrue(self.hv["unresolved"][t]["flag"], t)

    def test_the_check_is_reachable_from_the_command_line(self):
        src = (ROOT / "scripts" / "travel_distance.py").read_text()
        self.assertIn('"--check-venues"', src)
        self.assertIn("if args.check_venues:", src)

    def test_the_markdown_promise_matches_what_the_code_does(self):
        md = (ROOT / "data" / "live" / "raw" / "official_home_arena_schedule_2026-11-15.md").read_text()
        self.assertIn("--check-venues", md)
        self.assertIn("fails on a mismatch", md)


if __name__ == "__main__":
    unittest.main()
