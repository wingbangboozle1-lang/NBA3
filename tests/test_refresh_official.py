"""Offline tests for scripts/refresh_official.py (session arena/81800928-nba3).

No network: the fetcher is replaced by a fake that serves fixtures or raises.
Run: python3 -m unittest tests/test_refresh_official.py
"""
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import refresh_official as ro  # noqa: E402


def index_html(*names):
    return "".join(
        f'<a href="https://ak-static.cms.nba.com/referee/injury/{n}">x</a>' for n in names)


class NewestReportTests(unittest.TestCase):
    def test_midnight_is_not_the_newest_over_one_pm(self):
        # The old string sort picked 12_00AM over 01_00PM (because "12" > "01").
        html = index_html("Injury-Report_2026-11-15_12_00AM.pdf",
                          "Injury-Report_2026-11-15_01_00PM.pdf")
        self.assertEqual(ro.newest_report(html), ("2026-11-15", "01", "00", "PM"))

    def test_twelve_thirty_pm_is_older_than_one_pm(self):
        html = index_html("Injury-Report_2026-11-15_12_30PM.pdf",
                          "Injury-Report_2026-11-15_01_00PM.pdf")
        self.assertEqual(ro.newest_report(html), ("2026-11-15", "01", "00", "PM"))

    def test_later_date_wins_regardless_of_clock(self):
        html = index_html("Injury-Report_2026-11-15_11_45AM.pdf",
                          "Injury-Report_2026-11-16_12_00AM.pdf")
        self.assertEqual(ro.newest_report(html)[0], "2026-11-16")

    def test_no_links_returns_none(self):
        self.assertIsNone(ro.newest_report("<html>nothing</html>"))

    def test_report_time_is_12_hour_aware(self):
        self.assertEqual(ro.report_time("2026-11-15", "12", "00", "AM").hour, 0)
        self.assertEqual(ro.report_time("2026-11-15", "12", "15", "PM").hour, 12)
        self.assertEqual(ro.report_time("2026-11-15", "01", "00", "PM").hour, 13)


class EasternDateTests(unittest.TestCase):
    def test_utc_early_morning_is_previous_eastern_day(self):
        # 02:00 UTC on 11/15 is 21:00 EST on 11/14 (US DST ended 2026-11-01).
        now = datetime(2026, 11, 15, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(ro.et_today(now).isoformat(), "2026-11-14")

    def test_evening_utc_is_same_eastern_day(self):
        now = datetime(2026, 11, 15, 23, 15, tzinfo=timezone.utc)
        self.assertEqual(ro.et_today(now).isoformat(), "2026-11-15")


class FetcherTests(unittest.TestCase):
    def test_failed_url_is_recorded_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("2026-11-15T00-00Z")
            err = urllib.error.HTTPError("https://x", 403, "Forbidden", {}, None)
            with mock.patch.object(ro.urllib.request, "urlopen", side_effect=err), \
                    mock.patch.object(ro.time, "sleep"):
                out = f.get("https://x", os.path.join(td, "a.html"), required=True,
                            label="test")
            self.assertIsNone(out)
            self.assertEqual(len(f.errors), 1)
            self.assertTrue(f.errors[0]["required"])
            self.assertEqual(f.errors[0]["attempts"], ro.RETRIES)
            self.assertIn("403", f.errors[0]["error"])
            self.assertEqual(f.artifacts, [])

    def test_success_records_sha_and_retrieval_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("2026-11-15T00-00Z")
            resp = mock.MagicMock()
            resp.read.return_value = b"hello"
            resp.__enter__.return_value = resp
            with mock.patch.object(ro.urllib.request, "urlopen", return_value=resp):
                data = f.get("https://x", os.path.join(td, "a.html"))
            self.assertEqual(data, b"hello")
            art = f.artifacts[0]
            self.assertEqual(art["retrieved_utc"], "2026-11-15T00-00Z")
            self.assertEqual(len(art["sha256"]), 64)
            self.assertEqual(f.errors, [])

    def test_retry_then_success(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("s")
            ok = mock.MagicMock()
            ok.read.return_value = b"ok"
            ok.__enter__.return_value = ok
            side = [OSError("reset"), ok]
            with mock.patch.object(ro.urllib.request, "urlopen", side_effect=side), \
                    mock.patch.object(ro.time, "sleep"):
                self.assertEqual(f.get("https://x", os.path.join(td, "b")), b"ok")
            self.assertEqual(f.errors, [])


class MainFlowTests(unittest.TestCase):
    """main() with the network replaced: a dead injury index must stop before any rebuild."""

    def test_dead_injury_index_returns_2_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ro, "APP", td), \
                    mock.patch.object(ro.Fetcher, "get", lambda self, *a, **k: (
                        self.errors.append({"url": a[0], "label": k.get("label"),
                                            "required": True, "error": "boom",
                                            "attempts": 3}) or None)), \
                    mock.patch.object(ro.subprocess, "run") as run, \
                    mock.patch.object(ro.sys, "argv", ["refresh_official.py",
                                                       "--stamp", "T1"]):
                code = ro.main()
            self.assertEqual(code, 2)
            run.assert_not_called()
            import json
            with open(os.path.join(td, "refresh", "T1", "manifest.json")) as fh:
                man = json.load(fh)
            self.assertEqual(man["errors"][0]["label"], "injury index")

    def test_required_failure_after_index_refuses_rebuild(self):
        """Index works, newest PDF fails: exit 2, gates and rebuild are never run."""
        index = index_html("Injury-Report_2026-11-15_01_00PM.pdf").encode()

        def fake_get(self, url, dest, required=False, label=None):
            if url == ro.INJ_INDEX:
                self.artifacts.append({"url": url})
                return index
            self.errors.append({"url": url, "label": label, "required": required,
                                "error": "403", "attempts": 3})
            return None

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ro, "APP", td), \
                    mock.patch.object(ro.Fetcher, "get", fake_get), \
                    mock.patch.object(ro.subprocess, "run") as run, \
                    mock.patch.object(ro.sys, "argv", ["refresh_official.py",
                                                       "--stamp", "T2"]):
                code = ro.main()
            self.assertEqual(code, 2)
            run.assert_not_called()


class GateCallTests(unittest.TestCase):
    def test_freshness_gate_accepts_the_arguments_we_pass(self):
        # Regression: the refresh used to pass --manifest/--json-out, which the gate rejects.
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py"),
                            "--help"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("--manifest", r.stdout)


if __name__ == "__main__":
    unittest.main()
