"""The ownership gate must be able to see a dot-directory, and must not invent one.

`integrate/check.py` decides whether a changed file is inside a claim by parsing
paths out of COORDINATION.md. It stripped surrounding punctuation with a blanket
`.strip(".,;:()")`, which ate the leading dot of `.github/workflows/pages.yml` and
declared the path as `github/workflows/pages.yml`. Every edit to a dot-directory was
therefore rejected as out of scope no matter what the board said, and the gate could
never be satisfied for a legitimate CI change.

This is the same error class as the trailing-slash bug the gate already had to fix:
prose punctuation is not part of the path, but a leading dot may be.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from integrate.check import _clean_path  # noqa: E402


class TestCleanPath(unittest.TestCase):
    def test_a_dot_directory_keeps_its_dot(self):
        self.assertEqual(_clean_path(".github/workflows/pages.yml"),
                         ".github/workflows/pages.yml")

    def test_trailing_sentence_punctuation_is_stripped(self):
        self.assertEqual(_clean_path("scripts/build_app.py."), "scripts/build_app.py")
        self.assertEqual(_clean_path("app/,"), "app/")

    def test_brackets_and_semicolons_are_stripped_both_ends(self):
        self.assertEqual(_clean_path("(tools/check_site.py)"), "tools/check_site.py")
        self.assertEqual(_clean_path(";data/app/canonical.json:"),
                         "data/app/canonical.json")

    def test_a_relative_dot_segment_is_kept(self):
        # "./x" is a legal way to write a repo-relative path; only the "./" prefix
        # is redundant, and dropping it must not drop the rest.
        self.assertEqual(_clean_path("app/./lines.html"), "app/./lines.html")

    def test_an_empty_token_stays_empty(self):
        self.assertEqual(_clean_path(""), "")
        self.assertEqual(_clean_path("   "), "")

    def test_the_board_really_declares_the_workflow(self):
        """Not a unit test of the parser: proof that the fix is load-bearing."""
        with open(os.path.join(ROOT, "COORDINATION.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(".github/workflows/pages.yml", text,
                      "the claim must name the workflow, or CI edits stay out of scope")
        self.assertIn(_clean_path("`.github/workflows/pages.yml`").strip("`"),
                      [".github/workflows/pages.yml"])


if __name__ == "__main__":
    unittest.main()
