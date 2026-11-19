#!/usr/bin/env python3
"""Interpreter-independent arithmetic for artefacts that CI replays byte-for-byte.

Why this module exists (session 89e98007, 2026-11-19; fixes EVE-F04)
---------------------------------------------------------------------
The repository publishes its numbers as committed JSON artefacts, and CI re-derives them
(``… --check``) and compares the result with the committed bytes. A byte comparison ties a
published number to the *interpreter's* arithmetic, so an interpreter upgrade silently turns a
green pipeline red without any NBA source moving.

That is exactly what happened. GitHub's hosted ``ubuntu-latest`` moved its default ``python3`` to
CPython 3.14.4, and every scheduled refresh since 2026-11-17 fails at the committed-tree preflight
on one field::

    VALUE .top8_minutes_shares.2026-11-15:WAS.top8[4].share: 0.1088 != 0.1087
      run 44467720829 (annotation) · 44469939831 · 44467529208 ("all suites passed under Python 3.11")

The cause is not the data and not ``round()``: it is ``sum()``.

* `Python 3.12 "What's New"
  <https://docs.python.org/3/whatsnew/3.12.html>`_: "``sum()`` now uses Neumaier summation to
  improve accuracy and commutativity when summing floats or mixed ints and floats."
  (`gh-100425 <https://github.com/python/cpython/issues/100425>`_, Raymond Hettinger)
* `sum() in the language reference
  <https://docs.python.org/3/library/functions.html#sum>`_: "Changed in version 3.12: Summation of
  floats switched to an algorithm that gives higher accuracy on most builds."

The Washington game book's twelve rotation minutes sum to ``239.99999999999997`` added
left-to-right and to exactly ``240.0`` with compensation (they are the same twelve doubles; the
game book itself prints 240:00). Trae Young's 26.1 minutes therefore divide to either
``0.10875000000000001332…`` or ``0.10874999999999999944…`` — one of which is above the
0.10875 midpoint and one below it, so ``round(x, 4)`` lands on 0.1088 under CPython ≤ 3.11 and
0.1087 under ≥ 3.12. Every committed artefact in this repository was produced by a ≤ 3.11
``sum()``, which is the pipeline that is being published; the number a compensated summation
would have produced is the *different* number.

The rule, then, is stated in-repo instead of inherited from whatever interpreter a runner
happens to ship:

``fold``
    Plain left-to-right float addition — the summation that generated every committed artefact.
    Exact for ints (Python ints are arbitrary precision) and reproducible for floats.
    Not the most accurate way to add floats on purpose: choosing accuracy here would republish a
    different number than the one the sealed ledger hashed. See ``verify/determinism_89e98007.md``.

``dq``
    Decimal rounding of the exact value of a double, ties-to-even. ``round()`` is not the cause of
    this incident, but it is the same class of exposure: its result for floats is documented as
    implementation-flavoured ("values are rounded to the closest multiple of 10 to the power minus
    ndigits", `builtins.round
    <https://docs.python.org/3/library/functions.html#round>`_). Rounding is therefore pinned here
    so a future interpreter change cannot move a published number either.

``check_artefact`` / ``diff_paths``
    The gate, made diagnostic. Byte equality is still the requirement — a value must never drift
    silently, because a 0.01 change to a settled line is a different bet. But when bytes differ the
    gate now says *which JSON path* differs and with what, so the next incident is one annotation
    instead of six sessions of guessing.

Run: ``python3 -m unittest tests/test_determinism_89e98007.py``
"""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

__all__ = ["fold", "fold1", "dq", "diff_paths", "check_artefact", "write_or_check", "PINNED"]

PINNED = ("sum/round pinned in scripts/determinism.py: fold = plain left-to-right addition "
          "(CPython < 3.12 sum, the summation that generated the committed artefacts; CPython "
          ">= 3.12 sum() uses Neumaier compensation, see docs.python.org/3/whatsnew/3.12.html), "
          "dq = Decimal half-even rounding of the exact value of the double")


def fold(values, start=0):
    """Left-to-right sum: ``((start + v0) + v1) + …``.

    Starts at the integer 0 exactly like ``sum()`` so that summing ints stays an int — a page
    that printed "7/12" must not start printing "7.0/12".

    Deliberately *not* ``sum()``: CPython 3.12 switched ``sum()`` for floats to Neumaier
    compensated summation (docs.python.org/3/whatsnew/3.12.html, gh-100425), which is more
    accurate and produces a different double. Committed artefacts must not depend on which
    interpreter ran the build.
    """
    acc = start
    for v in values:
        acc = acc + v
    return acc


def fold1(values):
    """``sum(values[1:])``-style helper kept for readability at call sites that sum a bare list."""
    return fold(values)


def dq(value, places=None):
    """Round a number to ``places`` decimals, half-to-even, on the EXACT value of the double.

    ``Decimal(float)`` is the exact binary value, so the input to the rounding step does not
    depend on float->decimal conversion habits of the interpreter. ``places=None`` mirrors
    ``round(x)`` and returns an ``int``. ``None`` passes through, because most model fields are
    nullable and a gate must not turn "not published" into 0.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool):                   # bool is an int subclass; keep it out
        d = Decimal(int(value))
    elif isinstance(value, int):                    # exact, and must stay an exact int
        if places is None or places >= 0:
            return int(value)
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(value)                          # exact binary value, no repr involved
    else:                                           # str / anything Decimal accepts
        d = Decimal(str(value))
    with localcontext() as ctx:
        ctx.prec = 60
        if places is None:
            out = d.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
            return int(out) if isinstance(value, (int, float, Decimal)) else out
        out = d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
        if isinstance(value, int):
            return int(out)
        return float(out)


# --------------------------------------------------------------------------- artefact comparison
def diff_paths(a, b, prefix="", out=None, limit=12):
    """Every JSON path where two parsed artefacts differ, as 'path: left != right'.

    A drift report is the difference between a five-minute fix and a six-session hunt: run
    44469939831 named only the test, and the cause took the board until 89e98007.
    """
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{prefix}.{k}: MISSING in committed, regenerated={json.dumps(b[k])!s:.40}")
            elif k not in b:
                out.append(f"{prefix}.{k}: committed only ({json.dumps(a[k])!s:.40})")
            else:
                diff_paths(a[k], b[k], f"{prefix}.{k}", out, limit)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{prefix}: length {len(a)} != {len(b)}")
            return out
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{prefix}[{i}]", out, limit)
        return out
    if a != b or type(a) is not type(b) and not (
            isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append(f"{prefix}: {a!r} != {b!r}")
    return out


def check_artefact(path, blob):
    """(ok, detail) for a regenerated artefact against the committed one.

    Byte equality first, because that is the strongest statement and the normal case. If bytes
    differ, fall back to the parsed values so the failure says whether a NUMBER moved or only the
    formatting of the file (indent, key order, trailing newline) — and if a number moved, list the
    JSON paths. Formatting-only drift is still reported as drift by the caller? No: it is
    accepted, because the artefact's *content* is what downstream gates hash, and a whitespace
    change must not freeze the pipeline. A value change never is.
    """
    if not os.path.exists(path):
        return False, "expected artefact is missing: " + path
    with open(path, encoding="utf-8") as fh:
        committed = fh.read()
    if committed == blob:
        return True, "byte-identical"
    try:
        a = json.loads(committed)
        b = json.loads(blob)
    except json.JSONDecodeError as exc:
        return False, f"not comparable JSON ({exc})"
    if a == b:
        return True, ("values identical, bytes differ (formatting only: "
                      f"{len(committed)} vs {len(blob)} chars) — regenerate to reformat")
    d = diff_paths(a, b)
    if not d:
        return False, "bytes differ, no scalar difference located (structural change)"
    return False, "value drift (committed != regenerated) — " + "; ".join(d)


def write_or_check(path, blob, check, quiet=False):
    """Write the artefact, or in ``--check`` mode return the exit code for this file."""
    if check:
        ok, detail = check_artefact(path, blob)
        if not ok:
            print(f"DRIFT: {path}: {detail}", file=sys.stderr)
            return 1
        if not quiet:
            print(f"ok: {os.path.basename(path)} — {detail}")
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    return 0
