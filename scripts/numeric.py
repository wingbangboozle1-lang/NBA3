#!/usr/bin/env python3
"""Interpreter-independent float arithmetic for artefacts that CI byte-compares.

Why this module exists
-----------------------
CPython 3.12 changed ``sum()`` for floats: it now uses Neumaier compensated
summation (gh-100425) instead of the naive left-to-right accumulation of 3.11
and earlier. For most inputs the two agree to the last bit, but not always, and
when they do not, every downstream ``round()`` can land on the other side of a
decimal tie. That is not a cosmetic difference for this repository: three
committed artefacts regenerate with different bytes on a newer interpreter,
which made the byte-identity drift gates fail, which made the scheduled
refresh's unit-test gate red, which stopped the refresh job *before* it
fetched any official source. Measured on this repository:

    Python 3.11  sum([...minutes...]) = 239.99999999999997
    Python 3.12+ sum([...minutes...]) = 240.0
    -> 26.1 / that total -> 0.10875000000000001 -> round(..., 4) = 0.1088
    -> 26.1 / 240.0                -> 0.10875           -> round(..., 4) = 0.1087

The fix is not "pin the interpreter". The fix is to stop letting the
interpreter's summation algorithm leak into a published number:

* ``fsum`` -- ``math.fsum`` is the correctly-rounded (exact) sum, and has
  returned bit-identical results on every CPython since 3.6. It is therefore a
  property of the data, not of the interpreter.
* ``rnd``  -- rounding is done with ``decimal.Decimal`` in an explicitly named
  rounding mode, so a published ratio is a function of the number and the
  stated precision, not of how ``round()`` happens to treat a tie. The
  ``Decimal`` is built from the float's shortest round-trip repr, which is
  itself specified and stable across versions.

Together these make a committed artefact a function of its inputs alone. The
regression test ``tests/test_numeric.py`` pins that property by recomputing the
affected artefacts with ``builtins.sum`` replaced by the pre-3.12 naive
algorithm and asserting the bytes do not move.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_EVEN

__all__ = ["fsum", "rnd", "rnd_decimal", "naive_sum"]


def fsum(values) -> float:
    """Exactly-rounded sum of an iterable of floats.

    ``math.fsum`` keeps the running total in extended precision and rounds once
    at the end, so the result is the correctly-rounded true sum. It is
    identical on every CPython >= 3.6, unlike the built-in ``sum``.
    """
    return math.fsum(values)


def rnd_decimal(value, places: int) -> Decimal:
    """Round ``value`` to ``places`` decimals, ROUND_HALF_EVEN, as a Decimal.

    ROUND_HALF_EVEN is the rule the built-in ``round()`` documents, stated
    explicitly so the result does not depend on how a particular interpreter
    version implements it. (CPython 3.12 corrected a double-rounding bug in
    ``round()`` -- gh-99954 -- so a value built on 3.11 and one built on 3.12+
    could differ in the last published digit. Stating the rule removes the
    interpreter from the definition of a published number entirely.)

    The ``Decimal`` is built from the float's shortest round-trip repr, which
    is itself specified and stable across versions, so the decimal input is
    exactly the double that was computed.
    """
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-int(places))
    return Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_EVEN)


def rnd(value, places=None):
    """Round ``value`` with an explicit rounding mode.

    ``places=None`` mirrors ``round(x)`` and returns an int; an explicit
    ``places`` mirrors ``round(x, n)``, returning an int for an int input and a
    float for a float input, so the JSON serialisation keeps its shape.
    ``None`` passes through, so a missing measurement stays missing instead of
    becoming a zero.
    """
    if value is None:
        return None
    if places is None:
        return int(rnd_decimal(value, 0))
    if isinstance(value, int) and not isinstance(value, bool):
        quantum = Decimal(1).scaleb(-int(places))
        return int(Decimal(value).quantize(quantum, rounding=ROUND_HALF_EVEN))
    return float(rnd_decimal(value, places))


def naive_sum(values):
    """The pre-3.12 ``sum()`` for floats: naive left-to-right accumulation.

    Only used by the regression test, to prove that a committed artefact does
    not move when the interpreter's summation algorithm changes.
    """
    total = 0
    for v in values:
        total += v
    return total
