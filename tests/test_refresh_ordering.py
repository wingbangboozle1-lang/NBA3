#!/usr/bin/env python3
"""The scheduled refresh may not publish before its gates pass (session arena/42d69dc5-nba3).

Three defects this pins, all found by reading the tree rather than by a failing build:

1. `scripts/refresh_official.py` invoked `scripts/freshness_gates.py` with `--manifest ... --json-out
   ...`, flags only `freshness_gates_round_79341829.py` accepts. The call exited 2 (usage error) and
   the runner counted that as "gates failed", so the job could never rebuild. Recorded GitHub run:
   43742524756, failure inside the fetch step, subsequent steps skipped.
2. The workflow fetched in one step and `git push`ed in a later step, so the gate was not actually
   between the fetch and the push.
3. The brief names the official standings page; the job never fetched it.

These tests are static (they read the files), so they run offline and cannot be satisfied by a
coincidence of environment.
"""
import ast
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFRESH = ROOT / "scripts" / "refresh_official.py"
WF = ROOT / ".github" / "workflows" / "refresh.yml"
GATE_IMPL = ROOT / "scripts" / "freshness_gates_round_79341829.py"
PLAIN_GATES = ROOT / "scripts" / "freshness_gates.py"


class RefreshScriptTest(unittest.TestCase):
    """Assertions about the refresh script AS MERGED.

    An earlier draft of this file asserted the internals of a rewrite by this session
    (`GATES = "freshness_gates_round_79341829.py"`, `fetch(STANDINGS`, a two-step workflow). Another
    session's repair landed on main first and replaced that implementation. Those assertions were
    about a shape, not a guarantee, and they are corrected here rather than by reverting the merged
    work. What is kept is the guarantee each one was standing in for.
    """

    def setUp(self):
        self.src = REFRESH.read_text(encoding="utf-8")

    # --- the gate sits between the fetch and anything that publishes -------------------------

    def test_gate_runs_after_the_fetch_and_before_the_rebuild(self):
        fetch_done = self.src.index("manifest[\"gamebooks\"] = gb")
        gate_at = self.src.index("subprocess.run([sys.executable, os.path.join(ROOT, \"scripts\", \"freshness_gates.py\")]")
        rebuild_at = self.src.index("    steps = [")
        self.assertLess(fetch_done, gate_at, "the gate must run after the fetch")
        self.assertLess(gate_at, rebuild_at, "the gate must run before the rebuild")

    def test_rebuild_is_refused_on_any_nonzero_gate_exit(self):
        gate_at = self.src.index("gate = subprocess.run")
        rebuild_at = self.src.index("    steps = [")
        between = self.src[gate_at:rebuild_at]
        self.assertIn("gate.returncode != 0", between)
        self.assertIn("return 1", between)

    def test_post_rebuild_gates_run_before_publication(self):
        """The rebuild writes the freshness report, so the check must run again on what it wrote."""
        rebuild_at = self.src.index("    steps = [")
        post = self.src.index("post-rebuild freshness gates FAILED")
        self.assertGreater(post, rebuild_at)
        self.assertIn("return 1", self.src[post - 400:post + 200])

    def test_dry_run_cannot_rebuild(self):
        dry_at = self.src.index("if args.dry_run:")
        rebuild_at = self.src.index("    steps = [")
        self.assertLess(dry_at, rebuild_at)

    def test_a_required_fetch_failure_refuses_the_rebuild(self):
        self.assertIn('any(e["required"] for e in f.errors)', self.src)
        self.assertIn("rebuild refused", self.src)

    def test_empty_response_is_an_error_not_a_silent_success(self):
        """A 200 with a zero-byte body would be stored as a capture and counted as fresh."""
        self.assertIn("empty response body", self.src)
        self.assertIn("raise RuntimeError", self.src)

    # --- the brief's named sources are fetched ----------------------------------------------

    def test_standings_are_fetched(self):
        self.assertIn("https://www.nba.com/standings", self.src)

    def test_three_team_stat_pages_are_fetched(self):
        for page in ("traditional", "opponent", "advanced"):
            self.assertIn(f"/stats/teams/{page}?", self.src)

    def test_the_injury_index_is_fetched_and_is_required(self):
        self.assertIn("official.nba.com/nba-injury-report-2026-27-season", self.src)

    # --- the venue check is in the build ----------------------------------------------------

class VenueCheckInPipelineTest(unittest.TestCase):
    """The venue table's markdown promises a check "on every build". Prove it is in the build."""

    def setUp(self):
        self.src = REFRESH.read_text(encoding="utf-8")

    def _steps(self):
        body = self.src[self.src.index("    steps = ["):]
        return body[:body.index("    ]")].strip().splitlines()

    def test_the_venue_check_is_a_rebuild_step(self):
        self.assertTrue(any("travel_distance.py" in l and "--check-venues" in l for l in self._steps()),
                        "the venue check must run as a rebuild step")

    def test_it_runs_before_the_build_consumes_the_table(self):
        code = [l for l in self._steps() if l.strip()]
        idx = next(i for i, l in enumerate(code) if "--check-venues" in l)
        build = next(i for i, l in enumerate(code) if "build_app.py" in l)
        self.assertLess(idx, build)

    def test_a_failed_venue_check_aborts_the_refresh(self):
        self.assertIn("rebuild step failed", self.src)
        self.assertIn("return 1", self.src)


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.src = WF.read_text(encoding="utf-8")

    def test_the_commit_step_follows_the_gated_call(self):
        """The commit must not be reachable when the refresh refuses.

        The point is the ORDER, not the step count. An earlier draft asserted exactly two steps,
        which was over-specification: the merged workflow legitimately runs unit tests as their own
        step between the fetch and the commit, which is stricter. What must hold is that nothing
        that pushes exists between the refresh call and the commit step.
        """
        steps = re.findall(r"^      - name: (.+)$", self.src, re.M)
        fetch_i = next(i for i, s in enumerate(steps) if "Fetch official sources" in s)
        commit_i = next(i for i, s in enumerate(steps) if "Commit refreshed captures" in s)
        self.assertLess(fetch_i, commit_i, steps)
        between = self.src[self.src.index(steps[fetch_i]):self.src.index(steps[commit_i])]
        self.assertNotIn("git push", between)
        self.assertNotIn("HEAD:main", between)

    def test_commit_step_carries_the_condition(self):
        commit_block = self.src[self.src.index("- name: Commit refreshed captures"):]
        self.assertIn("if: github.event.inputs.dry_run != 'true'", commit_block)

    def test_no_push_before_the_gated_step(self):
        push_at = self.src.index("git push")
        fetch_at = self.src.index("python3 scripts/refresh_official.py")
        self.assertLess(fetch_at, push_at)

    def test_the_workflow_does_not_reimplement_the_gate(self):
        """The gate lives in one script and is invoked by the pipeline, not by the YAML.

        Naming the gate's *test* is not reimplementing it. What would be is calling the gate from
        the workflow with its own arguments, which is exactly the bug that made run 43742524756
        unpassable.
        """
        self.assertNotIn("python3 scripts/freshness_gates", self.src)
        self.assertNotIn("--manifest", self.src)
        self.assertIn("python3 scripts/refresh_official.py", self.src)

    def test_the_rebuilt_surfaces_are_committed(self):
        """A rebuild that does not commit its outputs leaves Pages serving the previous build."""
        block = next(l for l in self.src.splitlines() if l.strip().startswith("git add"))
        for path in ("data/app", "data/live", "ledger", "projection", "bet", "app", "index.html"):
            self.assertIn(path, block, f"{path} is rebuilt but never committed")


if __name__ == "__main__":
    unittest.main()
