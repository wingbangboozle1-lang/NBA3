#!/usr/bin/env python3
"""Tests for the standings promotion parser (session arena/4054e125-nba3)."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import standings_feed  # noqa: E402

RAW = os.path.join(ROOT, "data", "live", "raw", "standings_2026-11-16.md")


class StandingsFeedTest(unittest.TestCase):
    def test_markdown_mode_parses_the_committed_capture(self):
        rows = standings_feed.parse_markdown(open(RAW, encoding="utf-8").read())
        self.assertEqual(len(rows), 30)
        ok, problems = standings_feed.rows_pass(rows, require_full=True)
        self.assertTrue(ok, problems)
        self.assertEqual({r["team"] for r in rows} & {"Boston Celtics", "Utah Jazz"},
                         {"Boston Celtics", "Utah Jazz"})
        cel = next(r for r in rows if r["team"] == "Boston Celtics")
        self.assertEqual((cel["w"], cel["l"], cel["gb"]), (11, 2, "--"))
        # the cross-check table in the same file must NOT parse as standings rows
        # (its rows have only two numeric columns)

    def test_rows_pass_rejects_win_pct_mismatch(self):
        rows = standings_feed.parse_markdown(open(RAW, encoding="utf-8").read())
        rows[0]["win_pct"] = ".111"
        ok, problems = standings_feed.rows_pass(rows, require_full=True)
        self.assertFalse(ok)
        self.assertTrue(any("win%" in p for p in problems))

    def test_html_table_mode(self):
        html = "<table><tr><th>Team</th><th>W</th><th>L</th><th>WIN%</th><th>GB</th>" \
               "<th>CONF</th><th>DIV</th><th>HOME</th><th>ROAD</th><th>Neutral</th>" \
               "<th>OT</th><th>LAST10</th><th>STREAK</th></tr>"
        for i in range(30):
            html += ("<tr><td>Team %d</td><td>%d</td><td>1</td><td>.500</td><td>1</td>"
                     "<td>1-1</td><td>0-0</td><td>1-0</td><td>0-1</td><td>0-0</td>"
                     "<td>0-0</td><td>1-0</td><td>W 1</td></tr>") % (i, 1)
        html += "</table>"
        rows = standings_feed.parse_html_table(html)
        self.assertEqual(len(rows), 30)
        ok, problems = standings_feed.rows_pass(rows, require_full=True)
        self.assertTrue(ok, problems)

    def test_next_data_mode(self):
        import json as _json
        blob = {"props": {"pageProps": {"standings": [
            {"teamName": f"Club {i}", "wins": 2, "losses": 2, "winPCT": 0.5,
             "gamesBehind": "--", "conferenceRecord": "2-2", "divisionRecord": "1-0",
             "homeRecord": "1-1", "roadRecord": "1-1", "neutralRecord": "0-0",
             "overtimeRecord": "0-0", "last10GamesRecord": "2-2", "streak": "W 1"}
            for i in range(30)]}}}
        html = ('<script id="__NEXT_DATA__" type="application/json">'
                + _json.dumps(blob) + "</script>")
        rows = standings_feed.parse_next_data(html)
        self.assertEqual(len(rows), 30)
        ok, problems = standings_feed.rows_pass(rows, require_full=True)
        self.assertTrue(ok, problems)

    def test_next_data_missing_columns_is_partial(self):
        import json as _json
        blob = {"props": {"pageProps": {"standings": [
            {"teamName": f"Club {i}", "wins": 2, "losses": 2} for i in range(30)]}}}
        html = ('<script id="__NEXT_DATA__" type="application/json">'
                + _json.dumps(blob) + "</script>")
        rows = standings_feed.parse_next_data(html)
        self.assertEqual(len(rows), 30)
        full = all(all(k in r for k in standings_feed.FULL_KEYS) for r in rows)
        self.assertFalse(full)


if __name__ == "__main__":
    unittest.main()
