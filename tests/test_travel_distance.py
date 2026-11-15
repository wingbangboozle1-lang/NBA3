#!/usr/bin/env python3
"""Travel distance from a sourced arena-coordinate table (session arena/42d69dc5-nba3).

These tests pin three things that were wrong or missing before this round:

1. the coordinate table is actually built from the stored verbatim API captures (they can be
   re-derived byte for byte, so the numbers are not typed in by hand and cannot drift silently);
2. venue lookup cannot fall back to a city name. The defect this pins: the earlier build paired
   venues by city, so LAC at Intuit Dome (Inglewood) and PHX at Mortgage Matchup Center (Phoenix)
   resolved to the home city's own building and published 0.0 km;
3. an unsourced endpoint returns blank plus a reason, never a number, never zero.
"""
import json
import math
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import travel_distance as td  # noqa: E402

CAPTURE = ROOT / "data" / "live" / "raw" / "wiki_arena_coords_2026-11-15.json"
COORDS = ROOT / "data" / "live" / "arena_coords.json"
HOME = ROOT / "data" / "live" / "home_venues.json"


def _capture_coords():
    cap = json.loads(CAPTURE.read_text(encoding="utf-8"))
    out = {}
    for r in cap["responses"]:
        for _, pg in r["body"]["query"]["pages"].items():
            if "coordinates" in pg:
                c = pg["coordinates"][0]
                out[pg["title"]] = (c["lat"], c["lon"], pg["pageid"])
    return out


class ArenaTableTest(unittest.TestCase):
    def setUp(self):
        self.table = td.load_table(COORDS)
        self.capture = _capture_coords()

    def test_every_row_reproduces_from_the_stored_api_capture(self):
        """A published coordinate must equal the coordinate the API returned, exactly."""
        for venue, row in self.table["venues"].items():
            self.assertIn(row["title"], self.capture, f"{venue}: title not in the capture")
            lat, lon, pageid = self.capture[row["title"]]
            self.assertEqual(row["latitude"], lat, f"{venue}: latitude drifted from the capture")
            self.assertEqual(row["longitude"], lon, f"{venue}: longitude drifted from the capture")
            self.assertEqual(row["pageid"], pageid, f"{venue}: pageid drifted from the capture")

    def test_every_row_carries_an_https_source_and_is_labelled_reference(self):
        self.assertFalse(self.table["coordinate_source"]["is_official"])
        self.assertIn("REFERENCE, NOT OFFICIAL", self.table["coordinate_source"]["label"])
        for venue, row in self.table["venues"].items():
            self.assertTrue(row["coord_source"].startswith("https://en.wikipedia.org/wiki/"), venue)

    def test_thirty_clubs_and_the_blank_venue_is_recorded_not_filled(self):
        teams = {row["team"] for row in self.table["venues"].values()}
        self.assertEqual(len(teams), 30)
        blank = self.table["blank_venues"]["Wells Fargo Center"]
        self.assertIsNone(blank["latitude"])
        self.assertFalse(blank["verified"])
        # the renamed building is the one the official schedule prints, and it does resolve
        self.assertIn("Xfinity Mobile Arena", self.table["venues"])

    def test_no_city_keys_remain(self):
        """A city name must never be usable as a venue key."""
        for city in ("Inglewood, CA", "Phoenix, AZ", "Los Angeles, CA"):
            row, why = td.resolve(city, self.table)
            self.assertIsNone(row, f"{city} resolved as a venue: {why}")


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.table = td.load_table(COORDS)

    def test_same_venue_is_zero_and_labelled(self):
        d = td.distance("Intuit Dome", "Intuit Dome", self.table)
        self.assertEqual(d["km"], 0.0)
        self.assertEqual(d["source_tier"], "reference")

    def test_the_0km_defect_cannot_recur(self):
        """LAC at Intuit Dome and PHX at Mortgage Matchup Center are ~600 km apart, not 0."""
        d = td.distance("Intuit Dome", "Mortgage Matchup Center", self.table)
        self.assertEqual(d["status"], "SOURCED")
        self.assertGreater(d["km"], 400)
        self.assertLess(d["km"], 900)

    def test_unknown_venue_is_blank_with_a_reason(self):
        d = td.distance("Gainbridge Fieldhouse", "Some Arena That Does Not Exist", self.table)
        self.assertIsNone(d["km"])
        self.assertEqual(d["status"], "UNVERIFIED")
        self.assertIn("not in the sourced arena-coordinate table", d["reason"])

    def test_renamed_building_resolves_through_the_documented_alias(self):
        """'Wells Fargo Center' is a former name of 'Xfinity Mobile Arena'.

        The old title's article returns no coordinates, so the table stores the current name (which
        does) and aliases the old spelling to it. The alias is a documented name change, not an
        inference: the target row carries its own source URL and pageid.
        """
        row, why = td.resolve("Wells Fargo Center", self.table)
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "Xfinity Mobile Arena")
        self.assertTrue(row["coord_source"].startswith("https://en.wikipedia.org/wiki/"))
        self.assertIn("Wells_Fargo_Center", self.table["blank_venues"]["Wells Fargo Center"]["coord_source"])

    def test_a_venue_the_api_answered_with_nothing_stays_blank(self):
        """The exact shape of 'no coordinates returned': blank, flagged, never filled."""
        blank = self.table["blank_venues"]["Wells Fargo Center"]
        self.assertIsNone(blank["latitude"])
        self.assertIsNone(blank["longitude"])
        self.assertFalse(blank["verified"])
        self.assertTrue(blank["flag"])

    def test_alias_reaches_a_sourced_row_only(self):
        row, why = td.resolve("Footprint Center", self.table)
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "Mortgage Matchup Center")
        self.assertIn("carries its own source", why)

    def test_haversine_matches_a_known_distance(self):
        # Boston (TD Garden) to Los Angeles (Crypto.com Arena):
        # published great-circle distance is ~4,170 km; allow 1.5%.
        d = td.distance("TD Garden", "Crypto.com Arena", self.table)
        self.assertLess(abs(d["km"] - 4170) / 4170, 0.015)

    def test_haversine_is_symmetric(self):
        a = td.distance("TD Garden", "Ball Arena", self.table)["km"]
        b = td.distance("Ball Arena", "TD Garden", self.table)["km"]
        self.assertAlmostEqual(a, b, places=6)

    def test_earth_radius_constant_is_documented(self):
        self.assertAlmostEqual(td.EARTH_RADIUS_KM, 6371.0088)


class HomeVenueTest(unittest.TestCase):
    def setUp(self):
        self.hv = td.load_home_venues(HOME)
        self.table = td.load_table(COORDS)

    def test_each_resolved_home_venue_has_a_coordinate_row(self):
        for team, row in self.hv["teams"].items():
            self.assertIn(row["venue"], self.table["venues"], f"{team}: {row['venue']}")
            self.assertTrue(row["source_url"].startswith("https://www.nba.com/"), team)

    def test_unresolved_clubs_are_published_blank(self):
        self.assertEqual(sorted(self.hv["unresolved"]), ["CHA", "GSW", "POR"])
        for team, row in self.hv["unresolved"].items():
            self.assertIsNone(row["venue"], team)

    def test_counts_match_the_rows(self):
        self.assertEqual(self.hv["counts"]["resolved"], len(self.hv["teams"]))
        self.assertEqual(self.hv["counts"]["resolved"] + self.hv["counts"]["unresolved"], 30)


class BuildTest(unittest.TestCase):
    def test_committed_travel_block_reproduces(self):
        committed = json.loads((ROOT / "data" / "live" / "travel_distance.json").read_text())
        rebuilt = td.build()
        self.assertEqual(committed["counts"], rebuilt["counts"])
        self.assertEqual(len(committed["rows"]), len(rebuilt["rows"]))
        for a, b in zip(committed["rows"], rebuilt["rows"]):
            self.assertEqual((a["date"], a["game_id"], a["team"]), (b["date"], b["game_id"], b["team"]))
            self.assertEqual(a["travel_km"], b["travel_km"], f"{a['game_id']} {a['team']}")

    def test_every_published_distance_has_both_endpoint_sources(self):
        doc = json.loads((ROOT / "data" / "live" / "travel_distance.json").read_text())
        for r in doc["rows"]:
            if r["status"] == "SOURCED":
                self.assertTrue(r["from_source"].startswith("https://"), r["game_id"])
                self.assertTrue(r["to_source"].startswith("https://"), r["game_id"])
                self.assertEqual(r["source_tier"], "reference")
            else:
                self.assertIsNone(r["travel_km"])
                self.assertTrue(r["reason"])

    def test_priced_window_is_fully_sourced(self):
        doc = json.loads((ROOT / "data" / "live" / "travel_distance.json").read_text())
        self.assertEqual(doc["counts"]["priced_window_team_games"], 44)
        self.assertEqual(doc["counts"]["priced_window_unverified"], 0)

    def test_rest_travel_no_longer_keys_on_city(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import rest_travel
        with self.assertRaises(RuntimeError):
            rest_travel.venue_key("phoenix, az")


if __name__ == "__main__":
    unittest.main()
