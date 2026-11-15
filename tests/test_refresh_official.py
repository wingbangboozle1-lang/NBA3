"""CI tests for the scheduled official-data refresh (session 4f194ba2).

The scheduled job runs on the GitHub runner, where network to nba.com exists but the
sandbox has none. These tests therefore run the real fetch/gate/rebuild flow against a
local HTTP fixture server that mimics the official pages (injury index, injury PDF,
games pages, team-stat pages, game books), exercising:

  - provenance: every artifact recorded with URL, retrieval stamp and sha256;
  - slate promotion from the fetched games pages (blank tip times, never inferred);
  - critical vs optional artifacts: a critical failure refuses the rebuild (exit != 0)
    and the gates/rebuild steps are never started; an optional (game book) failure is
    skipped and recorded;
  - retry semantics: transient failures retried with backoff, hard 4xx not;
  - gate wiring: refresh_official calls freshness_gates.py with its REAL interface
    (defect F4F1942A-02) and a failing gate refuses the rebuild;
  - the fixture pages mirror the URL shapes of official.nba.com / nba.com / statsdmz.nba.com.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import refresh_official as ro  # noqa: E402

PDF_BYTES = b"%PDF-1.4\n% fake official report for replay tests\n"

INDEX_HTML = """
<html><body><ul>
<li><a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf">11/14 1:30 PM</a></li>
<li><a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_01_30PM.pdf">11/15 1:30 PM</a></li>
</ul></body></html>
"""

GAMES_UPCOMING = """
<html><body>
<a href="/game/bos-vs-nyc-0022600301/boxscore">BOS @ NYC</a>
<a href="/game/det-vs-sas-0022600302/boxscore">DET @ SAS</a>
</body></html>
"""

GAMES_PAST = """
<html><body>
<a href="/game/ind-vs-phi-0022600236/boxscore">IND @ PHI</a>
<a href="/boxscore/ind-vs-phi">box score IND @ PHI</a>
</body></html>
"""

TEAM_HTML = "<html><body>official team statistics table</body></html>"


def _routes(fn):
    """Route decorator: map (path-prefix) -> (status, body, content_type)."""
    return fn


class _FixtureServer:
    """Local server mimicking the official URL shapes, with per-path overrides."""

    def __init__(self):
        self.overrides = {}          # path -> (status, body)
        self.hits = []               # requested paths

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.ref.hits.append(self.path)
                path_only = self.path.split("?", 1)[0]
                override = self.server.ref.overrides.get(path_only)
                if override is not None:
                    status, body = override
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(body if isinstance(body, bytes) else body.encode())
                    return
                path = self.path
                if path.startswith("/referee/injury/") and path.endswith(".pdf"):
                    body, ctype = PDF_BYTES, "application/pdf"
                elif path.startswith("/nba-injury-report"):
                    body, ctype = INDEX_HTML, "text/html"
                elif path.startswith("/games"):
                    # past days carry a boxscore link; upcoming days do not
                    body, ctype = GAMES_PAST, "text/html"
                elif path.startswith("/stats/teams/"):
                    body, ctype = TEAM_HTML, "text/html"
                elif path.startswith("/pdfs/"):
                    body, ctype = PDF_BYTES, "application/pdf"
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(body if isinstance(body, bytes) else body.encode())

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.ref = self
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def url(self, official_url):
        return official_url.replace("https://official.nba.com", self.base
                                    ).replace("https://ak-static.cms.nba.com", self.base
                                              ).replace("https://www.nba.com", self.base
                                                        ).replace("https://statsdmz.nba.com", self.base)

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class _LocalOpen:
    """urlopen stand-in that rewrites official URLs onto the fixture server."""

    def __init__(self, server):
        self.server = server
        self.calls = []

    def __call__(self, req, timeout=60):
        url = self.server.url(req.full_url)
        self.calls.append(url)
        return urllib.request.urlopen(url, timeout=timeout)


class TestRefreshOfficial(unittest.TestCase):
    def setUp(self):
        self.srv = _FixtureServer()
        self.open = _LocalOpen(self.srv)
        self.tmp = tempfile.mkdtemp()
        self.out_dir = os.path.join(self.tmp, "refresh", "2026-11-15T23-59Z")
        self.now = datetime(2026, 11, 15, 23, 59, tzinfo=timezone.utc)
        self.stamp = "2026-11-15T23-59Z"

    def tearDown(self):
        self.srv.stop()

    def _run(self, **kw):
        defaults = dict(dry_run=True, attempts=3, sleep=lambda s: None,
                        urlopen=self.open, gates_cmd=["true"], rebuild_steps=[])
        defaults.update(kw)
        return ro.run_refresh(self.now, self.stamp, self.out_dir, self.tmp, **defaults)

    def _manifest(self):
        return json.load(open(os.path.join(self.out_dir, "manifest.json")))

    def test_full_pass_records_provenance_and_promotes_slate(self):
        rc = self._run()
        self.assertEqual(rc, 0)
        m = self._manifest()
        self.assertEqual(m["newest_injury_report"], "2026-11-15-01-30PM")
        self.assertEqual(m["gamebooks"], 2)          # two past days x 1 boxscore link
        artifacts = {a["url"]: a for a in m["artifacts"]}
        # every critical artifact carries a sha256 and its real retrieval stamp
        for url, a in artifacts.items():
            if not a.get("skipped"):
                self.assertEqual(len(a["sha256"]), 64, url)
                self.assertEqual(a["retrieved_utc"], self.stamp)
        self.assertIn("https://official.nba.com/nba-injury-report-2026-27-season/", artifacts)
        self.assertEqual(artifacts["https://official.nba.com/nba-injury-report-2026-27-season/"]["critical"], True)
        # the promoted slate keeps tip times blank and flags it — never inferred
        slate = json.load(open(os.path.join(self.tmp, "official_slate_current.json")))
        self.assertEqual(slate["count"], 4)          # 4 upcoming days x 1 game in the fixture
        self.assertEqual({g["time_et"] for g in slate["games"]}, {None})
        self.assertIn("blank and flagged, never inferred", slate["notes"][0])
        self.assertTrue(all(g["source"].startswith("https://www.nba.com/games?date=")
                            for g in slate["games"]))
        # the fetched PDF is stored verbatim and byte-identical
        with open(os.path.join(self.out_dir, "Injury-Report_2026-11-15_01_30PM.pdf"), "rb") as fh:
            self.assertEqual(fh.read(), PDF_BYTES)

    def test_critical_failure_refuses_gates_and_rebuild(self):
        self.srv.overrides["/stats/teams/traditional"] = (403, "Forbidden")
        started = []
        rc = self._run(dry_run=False,
                       gates_cmd=["python3", "-c", "started.append('gates')"],
                       rebuild_steps=[["python3", "-c", "started.append('rebuild')"]])
        self.assertEqual(rc, 3)                      # refused before any rebuild
        self.assertEqual(started, [])                # gates never even started
        self.assertFalse(os.path.exists(os.path.join(self.out_dir, "manifest.json")))

    def test_optional_gamebook_failure_is_skipped_and_recorded(self):
        self.srv.overrides["/pdfs/20261114/20261114_INDPHI.pdf"] = (404, "no game book yet")
        rc = self._run()
        self.assertEqual(rc, 0)
        m = self._manifest()
        self.assertEqual(m["gamebooks"], 1)          # the other day's game book made it
        skipped = [a for a in m["artifacts"] if a.get("skipped")]
        self.assertEqual(len(skipped), 1)
        self.assertIn("20261114_INDPHI.pdf", skipped[0]["url"])
        self.assertEqual(skipped[0]["critical"], False)

    def test_gate_failure_refuses_rebuild_but_keeps_captures(self):
        rc = self._run(dry_run=False,
                       gates_cmd=["python3", "-c", "raise SystemExit(1)"],
                       rebuild_steps=[["python3", "-c", "raise AssertionError('must not run')"]])
        self.assertEqual(rc, 1)
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "gate_report.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "manifest.json")))

    def test_transient_failure_is_retried_then_succeeds(self):
        tries = {"n": 0}

        def flaky(req, timeout=60):
            tries["n"] += 1
            if tries["n"] < 3:
                raise urllib.error.URLError("transient network error")
            return urllib.request.urlopen(self.srv.url(req.full_url), timeout=timeout)

        sleeps = []
        rc = ro.run_refresh(self.now, self.stamp, self.out_dir, self.tmp,
                            dry_run=True, attempts=3, sleep=sleeps.append,
                            urlopen=flaky, gates_cmd=["true"], rebuild_steps=[])
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(tries["n"], 3)
        self.assertTrue(sleeps)                      # backoff actually applied

    def test_hard_403_is_not_retried_and_critical_raises(self):
        calls = []

        def forbidden(req, timeout=60):
            calls.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

        sleeps = []
        with self.assertRaises(ro.CriticalFetchError):
            ro.fetch("https://www.nba.com/games?date=2026-11-15", "/dev/null", [],
                     self.stamp, critical=True, attempts=3, sleep=sleeps.append,
                     urlopen=forbidden)
        self.assertEqual(len(calls), 1)              # no pointless retries on a hard 4xx
        self.assertEqual(sleeps, [])

    def test_exhausted_transient_retries_record_skip_for_optional(self):
        calls = []

        def down(req, timeout=60):
            calls.append(req.full_url)
            raise urllib.error.URLError("down")

        art = []
        out = ro.fetch("https://statsdmz.nba.com/pdfs/1.pdf", "/dev/null", art,
                       self.stamp, critical=False, attempts=2, sleep=lambda s: None,
                       urlopen=down)
        self.assertIsNone(out)
        self.assertEqual(len(calls), 2)
        self.assertTrue(art[0]["skipped"])

    def test_gate_wiring_matches_freshness_gates_real_interface(self):
        """The gate command refresh_official runs must be accepted by freshness_gates.py.

        Guards defect F4F1942A-02: the previous version passed --manifest/--json-out,
        which argparse rejects — the rebuild could never have started.
        """
        import subprocess
        gates_cmd = [sys.executable, os.path.join(ROOT, "scripts", "freshness_gates.py")]
        r = subprocess.run(gates_cmd + ["--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        rc = self._run(dry_run=False, gates_cmd=gates_cmd, rebuild_steps=[])
        self.assertEqual(rc, 0)                      # the repo's own gates pass; rebuild list empty
        self.assertIn("gates passed",
                      open(os.path.join(self.out_dir, "gate_report.txt")).read())


if __name__ == "__main__":
    unittest.main()
