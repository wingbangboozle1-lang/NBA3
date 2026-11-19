#!/usr/bin/env python3
"""Deterministic float summation across Python versions (session arena/e9295737-nba3).

Why this module exists
----------------------
CPython 3.12 changed the builtin ``sum()`` to use Neumaier compensated summation for
floats (gh-100425, "sum() now uses Neumaier summation to improve accuracy"). On inputs
whose true sum is representable but whose left-to-right accumulation is not, the two
algorithms return different floats, and a value built by dividing by that sum can then
differ in its last printed digit.

That is what broke the scheduled refresh here. Minutes are stored as ``mm + ss/60``, so
nearly every value is a binary fraction with a repeating expansion (26.1 minutes is
1566/60). ``scripts/gamebooks_2ecbccfd.py`` divides each player's minutes by his club's
summed minutes and rounds the share to four places. On Python 3.11 the club-sums landed a
hair below the true value and Trae Young's share rounded to 0.1088; on Python 3.12 the
compensated sum landed a hair above and the same share rounded to 0.1087. The committed
artefact carries 0.1088, so the ``--check`` replay compared unequal and every scheduled
refresh failed at its committed-tree unit-test preflight from 2026-11-17 onward, before it
could fetch anything.

The fix is to stop depending on the interpreter's summation mode. Anything that feeds a
rounded division uses ``total()`` below, which is exactly the naive left-to-right float sum
that CPython 3.11 used, on every interpreter version. Integers keep exact accumulation. The
numbers the site publishes do not change: the committed artefacts were produced by the 3.11
algorithm and are still reproduced bit for bit.
"""
from __future__ import annotations

from typing import Iterable


def total(values: Iterable[float]) -> float:
    """Left-to-right float sum, identical on CPython 3.8 through 3.13+.

    This is CPython <=3.11's ``sum()`` semantics for floats. It is deliberately naive: the
    point is reproducibility of an already-published artefact, not maximal accuracy.
    ``None`` entries are skipped. Integers are accumulated exactly, so counts stay ints.
    """
    acc = 0
    for v in values:
        if v is None:
            continue
        acc = acc + v
    return acc


def share(value, denominator, places: int = 4):
    """``round(value / denominator, places)`` guarded against a zero/None denominator.

    Returns None when either side is missing or the denominator is zero, so a caller can
    publish "unknown" instead of inventing a share.
    """
    if value is None or denominator is None or denominator == 0:
        return None
    return round(value / denominator, places)


def mean_total(values):
    """Arithmetic mean of the non-None values, using the deterministic ``total``.

    The Python 3.12 change to ``sum()`` moves the last digit of a mean whenever the
    left-to-right and compensated sums of the same floats differ; a mean that is then
    rounded to two places (as the model stability table and the per-player averages do)
    can publish a different number. This keeps the committed figures reproducible.
    """
    xs = [v for v in values if v is not None]
    if not xs:
        return None
    return total(xs) / len(xs)
