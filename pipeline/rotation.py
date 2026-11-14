"""Rotation-minutes redistribution (hypothesis tool, standard library only).

Given baseline minutes for a team, remove players listed as OUT and spread
their minutes across the remaining players in proportion to baseline minutes,
never exceeding a per-player cap. The caller supplies team_minutes and cap;
no default is used, so no number here is presented as a verified fact.

Official NBA injury rules describe participation status and reason only. They
do not state minutes. Output is therefore a scenario, not a forecast.
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple


def redistribute_minutes(baseline: Dict[str, float], out: Iterable[str],
                         team_minutes: float, cap: float) -> Tuple[Dict[str, float], float]:
    """Return (new_minutes_by_player, residual_minutes).

    Invariant: sum(new_minutes) + residual == team_minutes.
    residual > 0 means every remaining player reached the cap.
    """
    if team_minutes <= 0:
        raise ValueError("team_minutes must be positive")
    if cap <= 0:
        raise ValueError("cap must be positive")
    if any(v < 0 for v in baseline.values()):
        raise ValueError("baseline minutes cannot be negative")
    out_set = set(out)
    unknown = out_set - set(baseline)
    if unknown:
        raise ValueError(f"OUT players not on baseline list: {sorted(unknown)}")

    remaining = {p: m for p, m in baseline.items() if p not in out_set}
    new = dict(remaining)
    pool = team_minutes - sum(new.values())
    if pool < -1e-9:
        raise ValueError("remaining baseline minutes already exceed team_minutes")
    pool = max(pool, 0.0)

    active = {p for p in new if new[p] < cap - 1e-12}
    while pool > 1e-9 and active:
        weights = {p: remaining[p] for p in active}
        total_w = sum(weights.values())
        if total_w <= 0:
            weights = {p: 1.0 for p in active}
            total_w = float(len(active))
        given = 0.0
        for p in list(active):
            share = pool * weights[p] / total_w
            add = min(share, cap - new[p])
            new[p] += add
            given += add
        pool -= given
        active = {p for p in active if new[p] < cap - 1e-12}
        if given <= 1e-12:
            break
    return new, max(pool, 0.0)


if __name__ == "__main__":  # pragma: no cover - manual use only
    print("rotation.py defines redistribute_minutes(); see pipeline/tests.")
