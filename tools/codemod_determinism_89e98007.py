#!/usr/bin/env python3
"""Codemod (session 89e98007): pin summation/rounding in the CI-replayed build chain.

Rewrites bare ``sum(…)`` -> ``det.fold(…)`` and bare ``round(…)`` -> ``det.dq(…)`` in the listed
files, using the AST so only real calls are touched (never a string, a comment, a method call or a
keyword argument), and inserts the import preamble once after the module's top-level imports.

Both replacements are value-identical to the CPython <= 3.11 builtins, which is the interpreter
that produced every committed artefact in this repository — see scripts/determinism.py for why the
pinned rule is the naive left-to-right fold and not the more accurate compensated sum that
CPython >= 3.12 introduced.

Every edit is verified against the source text before it is applied (the token at the reported
offset must be exactly the name being replaced), so a bad position — f-strings report odd ones on
some interpreters — aborts the file instead of corrupting it, and the result must still parse.

Run: python3 tools/codemod_determinism_89e98007.py [--dry] [--files a.py b.py]
"""
from __future__ import annotations

import argparse
import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PREAMBLE = '''
# determinism (session 89e98007): summation and rounding are pinned in-repo, not inherited from
# the interpreter that happens to run the build. See scripts/determinism.py: EVE-F04 was a runner
# Python upgrade (3.11 -> 3.14.4) that moved one published float by 1 unit in the 4th decimal and
# froze the byte-for-byte replay gate for six days.
import os as _det_os
import sys as _det_sys
for _det_p in (_os.path.join(_det_os.path.dirname(_det_os.path.abspath(__file__)), "..", "scripts"),
               _det_os.path.join(_det_os.path.dirname(_det_os.path.abspath(__file__)), "scripts")):
    if _det_os.path.isdir(_det_p) and _det_p not in _det_sys.path:
        _det_sys.path.insert(0, _det_p)
import determinism as det  # noqa: E402,F401
'''

DEFAULT = ["scripts/gamebooks_2ecbccfd.py", "scripts/capture_2ecbccfd.py",
           "scripts/slate_extra_2ecbccfd.py", "scripts/model_2ecbccfd.py",
           "scripts/ledger_2ecbccfd.py", "round_2ecbccfd/build.py"]

REN = {"sum": "det.fold", "round": "det.dq"}


def collect(src, tree):
    lines = src.splitlines()
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in REN:
            ln = n.func.lineno
            if ln > len(lines):
                raise SystemExit(f"AST line {ln} beyond EOF")
            seg = lines[ln - 1]
            got = seg[n.func.col_offset:n.func.end_col_offset]
            if got != n.func.id:
                raise SystemExit(f"offset mismatch at line {ln}: found {got!r} expected {n.func.id!r}"
                                 f" in {seg!r} — refusing to guess")
            out.append((ln, n.func.col_offset, n.func.end_col_offset, REN[n.func.id]))
    return out


def patch(rel, dry=False):
    path = os.path.join(ROOT, rel)
    src = open(path, encoding="utf-8").read()
    if "import determinism as det" in src:
        return rel, 0, "already patched"
    tree = ast.parse(src)
    e = collect(src, tree)
    lines = src.splitlines(keepends=True)
    for lineno, c0, c1, new in sorted(e, key=lambda t: (-t[0], -t[1])):
        i = lineno - 1
        lines[i] = lines[i][:c0] + new + lines[i][c1:]
    body = "".join(lines)
    top = ast.parse(body)
    anchor = 0
    for n in top.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n.end_lineno:
            anchor = max(anchor, n.end_lineno)
    pieces = body.splitlines(keepends=True)
    out = "".join(pieces[:anchor]) + PREAMBLE + "".join(pieces[anchor:])
    ast.parse(out)                      # must still be valid python
    if not dry:
        open(path, "w", encoding="utf-8").write(out)
    return rel, len(e), ("ok" if not dry else "would patch")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    bad = 0
    for rel in (a.files or DEFAULT):
        try:
            r, n, msg = patch(rel, a.dry)
        except SystemExit as exc:
            print(f"  REFUSED  {rel}: {exc}")
            bad += 1
            continue
        print(f"  {msg:>12}  {n:>3} call sites  {r}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
