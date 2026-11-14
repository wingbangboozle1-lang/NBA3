"""Session 53653a5c: regression tests for scripts/injury_delta_0415am.py (pins the verified counts)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InjuryDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((ROOT / "data/app/injury_delta_0415am.json").read_text(encoding="utf-8"))

    def test_counts_pinned(self):
        self.assertEqual(self.d["summary"]["attributed_11_14_rows_in_raw"], 17)
        self.assertEqual(self.d["summary"]["counts"].get("same"), 17)
        self.assertIsNone(self.d["summary"]["counts"].get("status_changed"))
        self.assertIsNone(self.d["summary"]["counts"].get("reason_changed"))
        self.assertEqual(self.d["summary"]["counts"].get("not_attributed_in_raw"), 11)

    def test_fragments_never_counted(self):
        self.assertTrue(all(f["result"] == "unverified_fragment" for f in self.d["unverified_fragments"]))
        compared = {(c["team"], c["player"]) for c in self.d["comparisons"]}
        for f in self.d["unverified_fragments"]:
            if "player" in f:
                self.assertNotIn((None, f["player"]), compared)

    def test_raw_source_is_official_host(self):
        self.assertTrue(self.d["raw_source_url"].startswith("https://ak-static.cms.nba.com/"))
        self.assertTrue(self.d["index_url"].startswith("https://official.nba.com/"))


if __name__ == "__main__":
    unittest.main()
