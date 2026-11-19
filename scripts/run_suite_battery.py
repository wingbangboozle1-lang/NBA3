#!/usr/bin/env python3
"""Run the refresh job's unit-test suites and make a runner-only failure self-reporting.

Why this exists (evidence, not theory): the scheduled `official data refresh` job has been red
since 2026-11-16 and its first failing step is the unit-test step (runs 43982186917, 44143781953,
44203349676, 44249179843, 44300142112, 44364543697, 44424736929 — step 4 FAIL, every later step
SKIPPED). The same suites pass on the identical commit in a clean clone in a sandbox, so the red is
a property of the runner environment, not of the committed data. The step that fails says only
"at least one unittest suite failed", and the Actions log body is not retrievable from every
environment (the results-receiver endpoint fails from this one), so three sessions could not name
the failing suite.

This script removes that dependency on log access:

  * it runs each suite as its own subprocess under a chosen interpreter, so a per-suite result
    cannot be lost in a merged stream;
  * it prints one `PASS|FAIL <suite> (Ran N tests)` line per suite and the interpreter banner, so
    the difference between "the committed tree is broken" and "this interpreter disagrees" is
    visible in the annotations alone;
  * on failure it writes the failing suite's tail as a `::error::` annotation. Annotation bodies
    come back from `GET /repos/{owner}/{repo}/check-runs/{id}/annotations`, which IS reachable from
    environments that cannot download a log archive;
  * `--report-only` never fails the job (used by the pages parity check while the cause is open);
    without it the exit code is 1 if any suite failed, which is what the refresh gate needs.

The suite list defaults to exactly the list `.github/workflows/refresh.yml` steps over, and
tests/test_refresh_diagnostic.py pins that they stay equal — a silently diverging list is how this
job lost its coverage in the first place.

Run: python3 scripts/run_suite_battery.py [--python /usr/bin/python3] [--report-only]
         [--json-out path.json] [--suite test_x.py ...]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "refresh.yml")

# How each suite is invoked. `discover` is what the workflow used; the module path is used for the
# one suite the workflow runs as a file (its helpers import `scripts/` via a path insert that
# assumes tests/ is a package path, and `discover` changes that).
SUITES = [
    ("test_*1115*.py", "discover"),
    ("test_results_feed.py", "discover"),
    ("test_pick_ledger.py", "discover"),
    ("test_freshness_gates.py", "discover"),
    ("test_refresh_official.py", "module"),
    ("test_results_feed_rows.py", "discover"),
    ("test_gamecard_feed.py", "discover"),
    ("test_standings_feed.py", "discover"),
    ("test_round_2ecbccfd.py", "discover"),
]

TAIL_LINES = 40          # enough for a traceback + the assertion message, small enough to annotate
MAX_ANNOTATION = 5000    # GitHub truncates long annotation bodies; keep the useful part


def workflow_suite_list() -> list[tuple[str, str]] | None:
    """Read an inline suite loop out of refresh.yml, if one still exists.

    The workflow used to carry the list inline; it now calls this script, so the loop is gone and
    the answer is None. tests/test_refresh_diagnostic.py pins that it stays gone — an inline loop
    reappearing would silently fork the list in two places, which is how this job's coverage and
    its diagnostics drifted apart once already.
    """
    with open(WORKFLOW, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"for suite in (.*?);\s*do", text, re.S)
    if not m:
        return None
    body = " ".join(part.strip() for part in m.group(1).replace("\\\n", " ").split())
    names = [tok.strip('"') for tok in re.findall(r'"([^"]+)"', body)]
    out: list[tuple[str, str]] = []
    for name in names:
        mode = "module" if name == "test_refresh_official.py" else "discover"
        out.append((name, mode))
    return out


def suite_command(exe: str, pattern: str, mode: str) -> list[str]:
    """The argv for one suite. Kept separate from run_suite so a test can pin its shape.

    A module is named with its DOTTED path (`tests.test_x`), never with a file path. `python -m
    unittest path/to/test_x.py` was deprecated in 3.11 and is gone from newer interpreters, where
    the argument is then read as a module name and unittest reports a loader failure instead of a
    result -- which is how the scheduled refresh lost its unit-test gate: the job's own test step
    used the path form (and the file it names, tests/test_refresh_official.py) and on the runner's
    /usr/bin/python3 3.12.3 that step reported FAIL for the whole suite while every sandbox on 3.11
    reported OK. The discover form takes a filename pattern and is stable across the versions.
    """
    if mode == "module":
        return [exe, "-m", "unittest", f"tests.{pattern[:-3]}", "-v"]
    return [exe, "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"]


def run_suite(exe: str, pattern: str, mode: str) -> subprocess.CompletedProcess:
    return subprocess.run(suite_command(exe, pattern, mode), cwd=ROOT,
                          capture_output=True, text=True)


def log_file_name(pattern: str) -> str:
    """A safe file name for a suite's log, keeping the same characters the workflow used."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", pattern) + ".log"


# GitHub truncates an annotation body (the observed cut landed at 563 characters), so a long
# traceback tail never survives the trip. Every annotation this script emits is capped short and
# the material is split across three of them instead of one.
ANNOTATION_MAX = 380


def escape_annotation(line: str) -> str:
    """Percent-encode what GitHub's workflow-command parser would otherwise drop.

    A raw LF splits the command from its payload (the payload becomes a plain log line) and a raw
    CR corrupts it; a bare % starts an escape sequence. Observed limit: run 44616982969's annotation
    was cut at 563 characters by the API, so the payload is capped here as well.
    """
    safe = line.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    return safe[:ANNOTATION_MAX]


def annotate(line: str, level: str = "error") -> None:
    """Emit a GitHub workflow command (an annotation, retrievable without log access)."""
    cmd = {"error": "::error::", "warning": "::warning::", "notice": "::notice::"}[level]
    print(f"{cmd}{escape_annotation(line)}")


def summarize(proc: subprocess.CompletedProcess) -> tuple[int, int]:
    """(returncode, tests-ran count), with a zero-test run promoted to a failure.

    A suite that loads nothing prints "Ran 0 tests" and exits 0 in some interpreters -- which is
    indistinguishable from a green step. The refresh gate exists to catch exactly that, so rc 0 +
    ran 0 is reported as rc 5 here.
    """
    text = (proc.stderr or "") + (proc.stdout or "")
    m = re.search(r"^Ran (\d+) tests?", text, re.M)
    ran = int(m.group(1)) if m else 0
    rc = proc.returncode
    if rc == 0 and ran == 0:
        rc = 5
    return rc, ran


def failed_test_ids(text: str) -> list[str]:
    """The `FAIL: <id>` / `ERROR: <id>` unittest lines, in order, deduplicated."""
    ids: list[str] = []
    for m in re.finditer(r"^(?:FAIL|ERROR): (\S+)(?: \(([^)]+)\))?", text, re.M):
        name, holder = m.group(1), (m.group(2) or "").strip()
        ids.append(f"{name} ({holder})" if holder else name)
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def loader_failure(text: str) -> str:
    """If unittest could not even load a test, say which error it raised.

    This is the shape of the red this script was written for: run 44617192915's annotation showed
    `test_published_slate_matches_the_promotion (unittest.loader._FailedTest...)`, i.e. a LOADER
    failure on the runner's interpreter rather than an assertion on the data. A loader error names
    the interpreter's import mechanism, so the message has to survive the trip.
    """
    m = re.search(r"unittest\.loader\._FailedTest", text)
    if not m:
        return ""
    block = re.search(r"(?:FAIL|ERROR): .*?\n-+\n(.*?)(?:\n-{3,}|\nRan \d)", text, re.S)
    detail = " | ".join(ln.strip() for ln in (block.group(1) if block else "").splitlines()
                        if ln.strip())
    return detail


def tail(proc: subprocess.CompletedProcess) -> str:
    """The last TAIL_LINES informative lines: failures/errors first, then the raw tail.

    unittest -v prints one 'ok' line per test, so a plain tail would show nothing but passes for a
    suite whose failure is followed by 30 successes. Pulling the FAIL/ERROR blocks is what makes
    the annotation actionable.
    """
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    lines = [ln for ln in combined.splitlines() if ln.strip()]
    marks = [i for i, ln in enumerate(lines)
             if re.match(r"^\S+ \S+ \.\.\. (FAIL|ERROR)$|^(FAIL|ERROR): \S+", ln)]
    picked: list[str] = []
    if marks:
        start = marks[0]
        picked = lines[start:start + TAIL_LINES * 2]
    else:
        picked = lines[-TAIL_LINES:]
    body = "\n".join(picked)[-MAX_ANNOTATION:]
    if proc.returncode and not body.strip():
        body = f"exit code {proc.returncode}, no output captured"
    return body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--python", default=sys.executable, help="interpreter to run the suites with")
    ap.add_argument("--suite", action="append", default=None,
                    help="override the suite list (repeatable, discover patterns or module files)")
    ap.add_argument("--annotate", action="store_true",
                    help="also emit a summary annotation on success, so a green run is provable "
                         "through the annotations API in environments that cannot read a log body")
    ap.add_argument("--report-only", action="store_true",
                    help="always exit 0; still annotate failures (used while a cause is open)")
    ap.add_argument("--json-out", default=None, help="write a machine-readable summary here")
    ap.add_argument("--log-dir", default=None,
                    help="write each suite's full output into this directory (one file per suite), "
                         "which the workflow uploads as an artifact — the annotation carries the "
                         "short diagnosis, the file carries the whole transcript")
    args = ap.parse_args(argv)

    exe = args.python
    banner = subprocess.run([exe, "-VV"], capture_output=True, text=True).stdout.strip()
    # Deliberately no nested same-quote f-string here: PEP 701 made those legal only in 3.12, and a
    # construct that compiles on one runner interpreter and not the other is the exact class of bug
    # this battery is meant to catch rather than introduce.
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"battery interpreter: {exe} -> {banner}")
    print(f"battery cwd        : {ROOT}")
    print(f"battery date (utc) : {now}")

    suites = ([(s, "module" if s == "test_refresh_official.py" else "discover")
               for s in args.suite] if args.suite else SUITES)

    results, failures = [], []
    for pattern, mode in suites:
        proc = run_suite(exe, pattern, mode)
        rc, count = summarize(proc)
        verdict = "PASS" if rc == 0 else "FAIL"
        line = f"{verdict}  {pattern}  mode={mode}  ran={count}  rc={rc}"
        print(line)
        if args.log_dir:
            os.makedirs(args.log_dir, exist_ok=True)
            dest = os.path.join(args.log_dir, log_file_name(pattern))
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(f"# interpreter: {banner}\n# argv: {' '.join(suite_command(exe, pattern, mode))}\n")
                fh.write(proc.stdout or "")
                fh.write(proc.stderr or "")
        results.append({"suite": pattern, "mode": mode, "returncode": rc,
                        "ran": count, "verdict": verdict})
        if rc != 0:
            failures.append(pattern)
            combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
            ids = failed_test_ids(combined)
            annotate(f"suite {pattern} (mode={mode}) rc={rc} under "
                     f"{banner.splitlines()[0]} -- this tree is green under another interpreter, "
                     f"so the interpreter line is part of the diagnosis")
            if ids:
                annotate(f"{pattern} failing tests: {'; '.join(ids)[:ANNOTATION_MAX]}")
            detail = loader_failure(combined) or tail(proc)
            if detail:
                annotate(f"{pattern} detail: {detail}")
            probe = subprocess.run(
                [exe, "-c", "import sys,unittest;"
                            "print(sys.version_info[:3], unittest.__file__, sys.flags.warndefault)"],
                capture_output=True, text=True)
            annotate(f"{pattern} probe: {(probe.stdout or probe.stderr).strip()}")

    summary = {"interpreter": banner, "results": results,
               "failed_suites": failures, "all_pass": not failures}
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.join(ROOT, args.json_out)) or ROOT, exist_ok=True)
        with open(os.path.join(ROOT, args.json_out), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=1, sort_keys=True)
            fh.write("\n")

    if failures:
        print(f"battery: {len(failures)} of {len(suites)} suites failed: {', '.join(failures)}")
        if args.annotate:
            annotate(f"battery: {len(failures)} of {len(suites)} suites FAILED "
                     f"({', '.join(failures)}) under {banner.splitlines()[0]}", level="warning")
        return 0 if args.report_only else 1
    print(f"battery: {len(suites)} suites, all passed")
    if args.annotate:
        annotate(f"battery: {len(suites)} suites, all passed under {banner.splitlines()[0]}"
                 f" [{', '.join(p for p, _ in suites)}]", level="notice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
