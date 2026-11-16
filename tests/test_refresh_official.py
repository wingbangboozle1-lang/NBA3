"""Offline tests for scripts/refresh_official.py (session arena/7082931c-nba3).

No network: the fetcher is replaced by a fake that serves fixtures or raises.
Run: python3 -m unittest tests/test_refresh_official.py
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
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

    def test_malformed_report_clock_fails_closed(self):
        html = index_html("Injury-Report_2026-11-15_13_00PM.pdf",
                          "Injury-Report_2026-11-15_01_00PM.pdf")
        self.assertIsNone(ro.newest_report(html))

    def test_report_time_is_12_hour_aware(self):
        self.assertEqual(ro.report_time("2026-11-15", "12", "00", "AM").hour, 0)
        self.assertEqual(ro.report_time("2026-11-15", "12", "15", "PM").hour, 12)
        self.assertEqual(ro.report_time("2026-11-15", "01", "00", "PM").hour, 13)


class RunStampTests(unittest.TestCase):
    def test_valid_safe_timestamp_formats(self):
        for stamp in ("2026-11-16T14-00Z", "2026-11-16T14-00-00Z",
                      "2026-11-16T14:00Z", "2026-11-16T14:00:00Z"):
            with self.subTest(stamp=stamp):
                self.assertTrue(ro.valid_run_stamp(stamp))

    def test_invalid_or_path_traversing_stamps_are_rejected(self):
        for stamp in ("T1", "2026-02-30T14-00Z", "../2026-11-16T14-00Z",
                      "/tmp/2026-11-16T14-00Z", "2026-11-16T14-00Z/extra"):
            with self.subTest(stamp=stamp):
                self.assertFalse(ro.valid_run_stamp(stamp))


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
            self.assertEqual(art["run_stamp"], "2026-11-15T00-00Z")
            self.assertTrue(art["retrieved_utc"].endswith("Z"))
            self.assertIsNotNone(datetime.fromisoformat(art["retrieved_utc"].replace("Z", "+00:00")))
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

    def test_empty_200_is_not_recorded_as_a_capture(self):
        with tempfile.TemporaryDirectory() as td:
            f = ro.Fetcher("s")
            empty = mock.MagicMock()
            empty.read.return_value = b""
            empty.__enter__.return_value = empty
            with mock.patch.object(ro.urllib.request, "urlopen", return_value=empty), \
                    mock.patch.object(ro.time, "sleep"):
                result = f.get("https://www.nba.com/standings", os.path.join(td, "empty.html"),
                               required=True, label="standings")
            self.assertIsNone(result)
            self.assertEqual(f.artifacts, [])
            self.assertEqual(f.errors[0]["label"], "standings")
            self.assertIn("empty response", f.errors[0]["error"])


class RollingFetchPlanTests(unittest.TestCase):
    def test_every_day_today_through_three_days_ahead_is_required(self):
        from datetime import date
        plan = ro.schedule_fetch_plan(date(2026, 11, 16))
        required = [day for day, is_required in plan if is_required]
        self.assertEqual(required, ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"])
        self.assertEqual([day for day, is_required in plan if not is_required],
                         ["2026-11-14", "2026-11-15"])


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
                                                       "--stamp", "2026-11-16T14-00-00Z"]):
                code = ro.main()
            self.assertEqual(code, 2)
            run.assert_not_called()
            import json
            with open(os.path.join(td, "refresh", "2026-11-16T14-00-00Z", "manifest.json")) as fh:
                man = json.load(fh)
            self.assertEqual(man["errors"][0]["label"], "injury index")

    def test_invalid_stamp_is_rejected_before_creating_a_capture_directory(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(ro, "APP", td), \
                    mock.patch.object(ro.sys, "argv", ["refresh_official.py", "--stamp", "../escape"]):
                code = ro.main()
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(os.path.join(td, "refresh")))

    def test_existing_capture_directory_is_not_overwritten(self):
        stamp = "2026-11-16T14-00-00Z"
        with tempfile.TemporaryDirectory() as td:
            out_dir = os.path.join(td, "refresh", stamp)
            os.makedirs(out_dir)
            manifest = os.path.join(out_dir, "manifest.json")
            with open(manifest, "wb") as handle:
                handle.write(b"previous immutable manifest")
            with mock.patch.object(ro, "APP", td), \
                    mock.patch.object(ro.Fetcher, "get") as get, \
                    mock.patch.object(ro.sys, "argv", ["refresh_official.py", "--stamp", stamp]):
                code = ro.main()
            self.assertEqual(code, 2)
            get.assert_not_called()
            with open(manifest, "rb") as handle:
                self.assertEqual(handle.read(), b"previous immutable manifest")

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
                                                       "--stamp", "2026-11-16T14-00-00Z"]):
                code = ro.main()
            self.assertEqual(code, 2)
            run.assert_not_called()


class GateCallTests(unittest.TestCase):
    def test_freshness_gate_accepts_the_arguments_we_pass(self):
        # The refresh's run-local report path is accepted; no nonexistent --manifest option is passed.
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py"),
                            "--help"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("--manifest", r.stdout)
        self.assertIn("--json-out", r.stdout)

    def test_gate_can_write_run_local_report_without_mutating_live_snapshot(self):
        import subprocess
        live_report = os.path.join(ROOT, "data", "live", "freshness.json")
        with open(live_report, "rb") as handle:
            before = handle.read()
        with tempfile.TemporaryDirectory() as td:
            output = os.path.join(td, "published_snapshot_gates.json")
            result = subprocess.run(
                [sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py"),
                 "--json-out", output], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with open(output, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["counts"]["failed"], 0)
            with open(live_report, "rb") as handle:
                self.assertEqual(handle.read(), before)


class PromotionOrderTests(unittest.TestCase):
    def _run_main(self, returncodes, *, wrap_promote=None, report_calls=None):
        temp = tempfile.TemporaryDirectory()
        app = temp.name
        today = date(2026, 11, 16)
        staged_slate = {
            "source_url": ro.GAMES + today.isoformat(),
            "source_urls": [ro.GAMES + (today + timedelta(days=i)).isoformat()
                            for i in range(4)],
            "source_label": "synthetic test slate",
            "retrieved_on": "2026-11-16",
            "retrieved_utc": "2026-11-16T14-00-00Z",
            "window": {"from": "2026-11-16", "to": "2026-11-19"},
            "count": 0,
            "daily_counts": [],
            "games": [],
            "notes": [],
        }
        daily_counts = [
            {"date": (today + timedelta(days=i)).isoformat(),
             "expected": 0, "parsed": 0, "complete": True}
            for i in range(4)
        ]
        stage_result = {"slate": staged_slate, "games": [], "errors": [],
                        "daily_counts": daily_counts}
        data = index_html("Injury-Report_2026-11-16_12_00PM.pdf").encode()
        target = os.path.join(app, "official_slate_current.json")
        with open(target, "wb") as handle:
            handle.write(b"last-good-slate\n")
        with open(target, "rb") as handle:
            original = handle.read()

        def fake_get(fetcher, url, dest, required=False, label=None):
            if url == ro.INJ_INDEX:
                body = data
            elif url == ro.INJ_CDN + "Injury-Report_2026-11-16_12_00PM.pdf":
                body = b"%PDF-1.4\nsynthetic report"
            else:
                body = b"<html>synthetic official source</html>"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(body)
            fetcher.artifacts.append({
                "url": url, "retrieved_utc": "2026-11-16T14:00:00Z",
                "run_stamp": fetcher.stamp,
                "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                "file": os.path.relpath(dest, ro.ROOT),
            })
            return body

        run_results = iter(SimpleNamespace(returncode=code) for code in returncodes)
        run_index = 0

        def fake_run(command, cwd=None):
            nonlocal run_index
            current_index = run_index
            run_index += 1
            result = next(run_results)
            should_write_report = report_calls is None or current_index in report_calls
            if result.returncode == 0 and "--json-out" in command and should_write_report:
                output = command[command.index("--json-out") + 1]
                os.makedirs(os.path.dirname(output), exist_ok=True)
                with open(output, "w", encoding="utf-8") as handle:
                    json.dump({"pass": True}, handle)
            return result

        with mock.patch.object(ro, "APP", app), \
                mock.patch.object(ro, "et_today", return_value=today), \
                mock.patch.object(ro.Fetcher, "get", fake_get), \
                mock.patch.object(ro.rolling_promote, "build_rolling_slate", return_value=stage_result), \
                mock.patch.object(ro.subprocess, "run", side_effect=fake_run) as run, \
                mock.patch.object(ro.sys, "argv", ["refresh_official.py", "--stamp",
                                                    "2026-11-16T14-00-00Z"]):
            real_promote = ro.rolling_promote.promote_slate
            if wrap_promote:
                def call_wrapper(staged, published):
                    return wrap_promote(run, real_promote, staged, published)
                with mock.patch.object(ro.rolling_promote, "promote_slate",
                                       side_effect=call_wrapper) as promote_mock:
                    code = ro.main()
            else:
                with mock.patch.object(ro.rolling_promote, "promote_slate",
                                       wraps=real_promote) as promote_mock:
                    code = ro.main()
        with open(target, "rb") as handle:
            current = handle.read()
        return temp, code, original, current, run, promote_mock, staged_slate

    def test_new_capture_gate_failure_does_not_promote_or_rebuild(self):
        temp, code, original, current, run, promote, _ = self._run_main([1])
        try:
            self.assertEqual(code, 1)
            self.assertEqual(current, original)
            promote.assert_not_called()
            self.assertEqual(run.call_count, 1)  # current-capture gate only
        finally:
            temp.cleanup()

    def test_successful_preflight_without_report_fails_closed(self):
        temp, code, original, current, run, promote, _ = self._run_main([0], report_calls=set())
        try:
            self.assertEqual(code, 1)
            self.assertEqual(current, original)
            promote.assert_not_called()
            self.assertEqual(run.call_count, 1)
        finally:
            temp.cleanup()

    def test_successful_published_gate_without_report_fails_closed(self):
        temp, code, original, current, run, promote, _ = self._run_main(
            [0, 0], report_calls={0})
        try:
            self.assertEqual(code, 1)
            self.assertEqual(current, original)
            promote.assert_not_called()
            self.assertEqual(run.call_count, 2)
        finally:
            temp.cleanup()

    def test_published_snapshot_gate_failure_does_not_promote_or_rebuild(self):
        temp, code, original, current, run, promote, _ = self._run_main([0, 1])
        try:
            self.assertEqual(code, 1)
            self.assertEqual(current, original)
            promote.assert_not_called()
            self.assertEqual(run.call_count, 2)
            self.assertIn("--json-out", run.call_args_list[1].args[0])
        finally:
            temp.cleanup()

    def test_slate_promotion_and_rebuild_follow_both_gates(self):
        promotion_calls = []

        def assert_gates_preceded_slate(run, original_promote, staged, target):
            self.assertEqual(run.call_count, 2)
            promotion_calls.append(True)
            return original_promote(staged, target)

        temp, code, original, current, run, promote, slate = self._run_main(
            [0, 0] + [0] * 7, wrap_promote=assert_gates_preceded_slate)
        try:
            self.assertEqual(code, 0)
            self.assertEqual(run.call_count, 9)  # 2 gates followed by the 7 rebuild steps
            self.assertEqual(promotion_calls, [True])
            self.assertEqual(promote.call_count, 1)
            self.assertNotEqual(current, original)
            self.assertIn(b'"count": 0', current)
            self.assertEqual(run.call_args_list[0].args[0][1],
                             os.path.join(ro.ROOT, "scripts", "refresh_preflight.py"))
            self.assertIn("--json-out", run.call_args_list[1].args[0])
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
