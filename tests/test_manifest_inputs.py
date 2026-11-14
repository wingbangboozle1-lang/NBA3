"""Every engine must price off the capture the manifest names - one input, one
site (question CQ-47, suggestion CS-45, flag F-DF3-05).

This is the check that a refresh cannot be half-applied. The 2026-11-14 game-day
refresh is the case it exists for: ``scripts/report_availability.py`` carried its
own hard-coded injury path while ``scripts/strategy_lab.py`` resolved the same
input through ``data/app/snapshot_manifest.json``, so repointing the manifest moved
the lines and left the availability state machine reasoning about a superseded
document.  Both modules now resolve through the manifest, and this test fails if
any of the three ever drifts apart again.

The fallback defaults are allowed to disagree (they only apply when no manifest is
present, and each reproduces the file its own module was written against); what
must not disagree is what the modules actually read.
"""

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

MANIFEST_REL = "data/app/snapshot_manifest.json"
BLOCKS = ("slate", "results_log", "counts", "availability", "players", "ratings", "injuries")


def manifest():
    with open(os.path.join(ROOT, MANIFEST_REL), encoding="utf-8") as fh:
        return json.load(fh)


class ManifestInputs(unittest.TestCase):
    def test_every_named_path_exists(self):
        man = manifest()
        for block in BLOCKS:
            rel = ((man.get(block) or {}).get("path") or "").strip()
            self.assertTrue(rel, f"manifest block {block} names no path")
            self.assertTrue(os.path.exists(os.path.join(ROOT, *rel.split("/"))),
                            f"manifest {block}.path does not exist: {rel}")

    def test_superseded_paths_exist_too(self):
        """The superseded artefacts are published, so they must be readable."""
        for block, rel in (manifest().get("superseded") or {}).items():
            if isinstance(rel, str) and rel.startswith("data/"):
                self.assertTrue(os.path.exists(os.path.join(ROOT, *rel.split("/"))),
                                f"superseded[{block}] missing: {rel}")

    def test_injuries_block_names_the_newest_committed_capture(self):
        rel = manifest()["injuries"]["path"]
        self.assertEqual(rel, "data/app/official_injuries_2026-11-14_1330PM.json")
        with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as fh:
            snap = json.load(fh)
        self.assertEqual(snap["report_stamp"], "2026-11-14 01:30 PM ET")
        # the manifest's own provenance must not disagree with the file it names
        self.assertEqual(manifest()["injuries"]["source_url"], snap["source_url"])
        self.assertEqual(manifest()["injuries"]["report_stamp"], snap["report_stamp"])

    def test_strategy_lab_reads_the_manifest_injury_path(self):
        import strategy_lab as lab
        want = os.path.join(ROOT, *manifest()["injuries"]["path"].split("/"))
        self.assertEqual(os.path.abspath(lab.INJURY_JSON), want,
                         "strategy_lab.py resolved a different injury capture than the manifest")
        self.assertEqual(os.path.abspath(lab.SLATE_JSON),
                         os.path.abspath(os.path.join(ROOT, *manifest()["slate"]["path"].split("/"))))

    def test_report_availability_reads_the_manifest_injury_path(self):
        import report_availability as ra
        want = os.path.join(ROOT, *manifest()["injuries"]["path"].split("/"))
        self.assertEqual(os.path.abspath(ra.INJURY_JSON), want,
                         "report_availability.py hard-codes an injury capture; the manifest is "
                         "the only place an input path may be decided (CS-45)")
        self.assertEqual(os.path.abspath(ra.SLATE_JSON),
                         os.path.abspath(os.path.join(ROOT, *manifest()["slate"]["path"].split("/"))))

    def test_the_two_engines_resolve_the_same_file(self):
        import report_availability as ra
        import strategy_lab as lab
        self.assertEqual(os.path.abspath(lab.INJURY_JSON), os.path.abspath(ra.INJURY_JSON),
                         "the lab and the availability state machine would publish different "
                         "availability states for the same game")

    def test_as_of_clock_is_taken_from_the_report_not_a_constant(self):
        import report_availability as ra
        self.assertTrue(ra.set_as_of("2026-11-14 01:30 PM ET"))
        self.assertEqual((ra.AS_OF_DATE, ra.AS_OF_LOCAL_HOUR), ("2026-11-14", 13.5))
        self.assertFalse(ra.set_as_of(""))
        self.assertFalse(ra.set_as_of("yesterday"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
