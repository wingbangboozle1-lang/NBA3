"""Tests that verify.py rejects bad inputs (it must not pass by accident)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify  # noqa: E402


class UrlRuleTests(unittest.TestCase):
    def test_official_https_accepted(self):
        self.assertIsNone(verify.url_problem("https://www.nba.com/schedule"))
        self.assertIsNone(verify.url_problem("https://ak-static.cms.nba.com/referee/injury/x.pdf"))

    def test_blank_rejected(self):
        self.assertEqual(verify.url_problem(""), "missing")

    def test_http_rejected(self):
        self.assertIn("not https", verify.url_problem("http://www.nba.com/schedule"))

    def test_unofficial_host_rejected(self):
        self.assertIn("allow-list", verify.url_problem("https://prod.kansspelautoriteit.hosted-temp.com/x"))


class SiteParserTests(unittest.TestCase):
    def _parse(self, body):
        p = verify.SiteParser()
        p.feed(body)
        return p

    def test_row_without_link_is_detected(self):
        p = self._parse("<table><thead><tr><th>a</th></tr></thead><tbody>"
                        "<tr><td>x</td></tr><tr><td><a href='https://www.nba.com/schedule'>S</a></td></tr>"
                        "</tbody></table>")
        self.assertEqual(len(p.rows), 2)
        self.assertEqual([bool(r["links"]) for r in p.rows], [False, True])

    def test_blank_cells_counted(self):
        p = self._parse("<table><tbody><tr><td class=\"blank\">&mdash; <span class=\"flag\">unverified</span></td></tr></tbody></table>")
        self.assertEqual(p.blank_cells, 1)


if __name__ == "__main__":
    unittest.main()
