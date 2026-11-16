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
