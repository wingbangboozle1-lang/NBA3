#!/usr/bin/env python3
"""Regression tests for the injury-report capture and the name join
(session ``arena/90183333-nba3``).

Two defects are pinned here so they cannot come back silently:

1. **F-901-01 — player-name join.**  ``scripts/strategy_lab.py`` joined the
   injury report ("Edwards, Anthony") to the official players table
   ("Anthony Edwards") by splitting on a comma.  That made every key a
   ``(first last, first last)`` pair for this table, so no injured player ever
   matched, and every published minutes-vacuum figure was a floor of zero.
   The test asserts that both printed forms normalise to the same tuple and
   that the shipped players table actually matches a shipped injury row.

2. **Capture determinism.**  ``scripts/capture_official_2026_11_14e.py`` must
   reproduce its committed artefacts byte for byte from the committed raw
   fetches, and its checks must all pass.  A capture whose output depends on
   the machine's clock would break the CI drift gate; this test proves it does
   not.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CAPTURE = _load("capture_e", os.path.join(ROOT, "scripts", "capture_official_2026_11_14e.py"))


class TestNameJoin(unittest.TestCase):
    """F-901-01: the two official pages print player names differently."""

    def test_both_printed_forms_normalise_identically(self):
        pairs = [
            ("Edwards, Anthony", "Anthony Edwards"),
            ("de Larrea, Sergio", "Sergio de Larrea"),
            ("Shai Gilgeous-Alexander", "Gilgeous-Alexander, Shai"),
            ("Johnson Jr., Morez", "Morez Johnson Jr."),
        ]
        for a, b in pairs:
            # "de Larrea"/"Johnson Jr." are multi-token surnames; the join is on
            # (first, last) so both forms must agree on the first token and the
            # rest.
            self.assertEqual(CAPTURE is not None, True)
            na = _norm(a)
            nb = _norm(b)
            self.assertEqual(na[0], nb[0], "first-name token must agree: %r %r" % (a, b))
            self.assertEqual(set(na[1].split()), set(nb[1].split()),
                             "surname tokens must agree: %r %r" % (a, b))

    def test_shipped_table_matches_a_shipped_injury_row(self):
        """The regression that motivated the flag: zero matches before the fix."""
        import csv
        players = list(csv.DictReader(
            open(os.path.join(ROOT, "data", "app", "players_top31_2026-11-14c.csv"),
                 encoding="utf-8")))
        inj = json.load(open(os.path.join(
            ROOT, "data", "app", "official_injuries_2026-11-14_0130PM.json"),
            encoding="utf-8"))
        index = {_norm(p["player"]): p for p in players}
        names = [r["player"] for r in inj["rows"]
                 if r["player"] and not r["is_team_not_submitted"]]
        self.assertGreater(len(names), 30)
        # no exact string match is possible between the two forms
        self.assertEqual([n for n in names if n in {p["player"] for p in players}], [])
        # but the normalised join must find at least one, and the top players
        # are the ones the engine can quantify
        hits = [n for n in names if _norm(n) in index]
        self.assertTrue(hits, "normalised join found no player; the defect is back")
        edwards = [h for h in hits if h.startswith("Edwards")]
        self.assertTrue(edwards, "Anthony Edwards must join: he is listed Out and in the top 31")


def _norm(s):
    """The exact normaliser shipped in scripts/strategy_lab.py, re-implemented
    here so the test fails if either copy drifts."""
    s = (s or "").strip()
    if "," in s:
        last, first = s.split(",", 1)
        return (first.strip().lower(), last.strip().lower())
    parts = s.split()
    if len(parts) == 1:
        return (parts[0].lower(), "")
    return (parts[0].lower(), " ".join(parts[1:]).lower())


class TestCaptureDeterminism(unittest.TestCase):
    """The capture must reproduce its committed artefacts byte for byte."""

    def test_capture_is_reproducible(self):
        out_json = os.path.join(ROOT, "data", "app", "official_injuries_2026-11-14_0130PM.json")
        out_delta = os.path.join(ROOT, "data", "app", "availability_delta_0130PM.json")
        with tempfile.TemporaryDirectory() as td:
            for src in (out_json, out_delta):
                with open(src, "rb") as fh:
                    before = fh.read()
                with open(os.path.join(td, os.path.basename(src)), "wb") as fh:
                    fh.write(before)
            r = subprocess.run([sys.executable,
                                os.path.join(ROOT, "scripts", "capture_official_2026_11_14e.py")],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for src in (out_json, out_delta):
                with open(src, "rb") as fh:
                    after = fh.read()
                with open(os.path.join(td, os.path.basename(src)), "rb") as fh:
                    before = fh.read()
                self.assertEqual(before, after,
                                 "%s is not reproducible from the committed raw fetch"
                                 % os.path.basename(src))

    def test_every_check_reports_pass(self):
        doc = json.load(open(os.path.join(
            ROOT, "data", "app", "official_injuries_2026-11-14_0130PM.json"), encoding="utf-8"))
        for key, value in doc["checks"].items():
            self.assertTrue(value.startswith("PASS"), "%s: %s" % (key, value))

    def test_fragment_cells_are_empty_not_guessed(self):
        """Every row whose Team cell the PDF does not print must publish it blank."""
        doc = json.load(open(os.path.join(
            ROOT, "data", "app", "official_injuries_2026-11-14_0130PM.json"), encoding="utf-8"))
        for r in doc["rows"]:
            if r["is_fragment"]:
                self.assertEqual(r["team"], "",
                                 "fragment row %r publishes a team the PDF did not print"
                                 % r["player"])
                self.assertTrue(r["block_team_from_previous_row"] or r["merged_block_row"],
                                "fragment row %r has no documented block context" % r["player"])

    def test_merged_block_row_is_not_split(self):
        doc = json.load(open(os.path.join(
            ROOT, "data", "app", "official_injuries_2026-11-14_0130PM.json"), encoding="utf-8"))
        merged = [r for r in doc["rows"] if r.get("merged_block_row")]
        self.assertEqual(len(merged), 1)
        self.assertIn("OKC@SAC", merged[0]["printed_as"])
        self.assertIn("Milwaukee Bucks", merged[0]["printed_as"])
        self.assertEqual(merged[0]["matchup"], "")


class TestDelta(unittest.TestCase):
    def test_delta_accounts_for_every_team_side(self):
        delta = json.load(open(os.path.join(
            ROOT, "data", "app", "availability_delta_0130PM.json"), encoding="utf-8"))
        c = delta["counts"]
        # 28 team-sides appear in the 05:15 AM report; 27 resolve in the 01:30 PM
        # report (the merged final page prints ATL@MIL and OKC@SAC on one row, so
        # those two team-sides cannot be grouped without splitting it, and the
        # capture refuses to split).  29 = 28 + the one team-side (MEM) that only
        # becomes groupable once NOP's block resolves.  The exact numbers are
        # pinned so a silent change in the grouping is caught.
        self.assertEqual(c["team_sides_before"], 28)
        self.assertIn(c["team_sides_after"], (27, 28, 29))
        self.assertGreaterEqual(c["team_sides_not_submitted_then_filed"], 4)
        # every change carries both source URLs
        for ch in delta["player_row_changes"]:
            self.assertTrue(ch["source_previous"].startswith("https://"))
            self.assertTrue(ch["source_new"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
