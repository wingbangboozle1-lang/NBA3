"""The injury archive's consecutive-report chain follows actual report time, not filename order."""
import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import injury_archive  # noqa: E402


class InjuryArchiveOrderingTests(unittest.TestCase):
    def test_captured_spelling_note_matches_official_pdf_transcripts(self):
        report_dir = ROOT / "data" / "live" / "injuries"
        report_0600 = (report_dir / "Injury-Report_2026-11-15_06_00AM.md").read_text()
        report_0615 = (report_dir / "Injury-Report_2026-11-15_06_15AM.md").read_text()
        midnight = (report_dir / "Injury-Report_2026-11-15_12_00AM.md").read_text()
        notes = (report_dir / "NOTES.md").read_text()
        self.assertIn("| Embiid, Joel |", report_0600)
        self.assertIn("| Embid, Joel |", report_0615)
        self.assertIn("| Embiid, Joel |", midnight)
        self.assertIn("06:00 AM PDF", notes)
        self.assertIn("06:15 AM PDF", notes)
        self.assertIn("says `Embiid, Joel`", notes)
        self.assertIn("says `Embid, Joel`", notes)

    def test_live_pages_expose_index_staleness_and_correction_sources(self):
        flagged = (ROOT / "projection" / "flagged.html").read_text()
        injuries = (ROOT / "projection" / "injuries.html").read_text()
        latest_pdf = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_09_30AM.pdf"
        self.assertIn("STALE", flagged)
        self.assertIn("2026-11-16", flagged)
        self.assertIn(latest_pdf, flagged)
        self.assertIn("STALE — injury snapshot is not current", injuries)
        self.assertIn(latest_pdf, injuries)
        self.assertIn("06:00 AM PDF spells Joel Embiid", flagged)

    def test_deltas_are_chronological_across_midnight_filename(self):
        source_dir = ROOT / "data" / "live" / "injuries"
        expected_files = [
            "Injury-Report_2026-11-15_12_00AM.md",
            "Injury-Report_2026-11-15_06_00AM.md",
            "Injury-Report_2026-11-15_06_15AM.md",
        ]
        with tempfile.TemporaryDirectory() as td:
            temp_dir = pathlib.Path(td)
            for filename in expected_files:
                shutil.copyfile(source_dir / filename, temp_dir / filename)
            index_path = temp_dir / "archive_index.json"
            deltas_path = temp_dir / "deltas.json"
            with mock.patch.object(injury_archive, "DIR", temp_dir), \
                    mock.patch.object(injury_archive, "OUT_INDEX", index_path), \
                    mock.patch.object(injury_archive, "OUT_DELTAS", deltas_path), \
                    contextlib.redirect_stdout(io.StringIO()):
                injury_archive.main()
            index = json.loads(index_path.read_text(encoding="utf-8"))
            deltas = json.loads(deltas_path.read_text(encoding="utf-8"))["deltas"]

        self.assertEqual(
            [row["file"] for row in index["files"]],
            expected_files,
        )
        self.assertEqual(
            [(row["from_file"], row["to_file"]) for row in deltas],
            list(zip(expected_files, expected_files[1:])),
        )


if __name__ == "__main__":
    unittest.main()
