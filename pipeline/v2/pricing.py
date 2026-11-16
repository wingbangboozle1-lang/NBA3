"""Line origination and parlay pricing.

Two rules govern this module.

**Every parlay price is printed twice.**  Once as the naive product of the leg
probabilities, which is what a person would compute on a napkin and which is
wrong whenever the legs are not independent, and once from the measured
dependence.  When the measured dependence does not exist the naive product is
printed alone and labelled as unmeasured -- it is never silently presented as if
the legs were independent.

**The dependence is measured, never assumed.**  A same-game side-and-total
parlay is priced with the Gaussian copula at the measured r of the final margin
against the final total.  A correlation that is inside its own confidence
interval of zero is reported as "not distinguishable from zero at this n", which
is a different statement from "zero" and is what the page prints.

Player props get no price at all: with no per-player game logs there is no rho,
and inventing one would be the single least defensible number on the site.
"""

from __future__ import annotations

from . import stats as S

DEFAULT_PRICE = -110


def fair_line(margin, total, margin_sd, total_sd):
    """The originated line, with the error bars that make it interpretable.

    A point estimate on its own invites over-reading.  The 80% interval is the
    honest unit for a line: it says where the game actually lands four times out
    of five, given the model.
    """
    return {
        "margin": round(margin, 2) if margin is not None else None,
        "total": round(total, 2) if total is not None else None,
        "margin_sd": round(margin_sd, 3) if margin_sd else None,
        "total_sd": round(total_sd, 3) if total_sd else None,
        "margin_80pct": ([round(margin - 1.2816 * margin_sd, 2),
                          round(margin + 1.2816 * margin_sd, 2)]
                         if margin is not None and margin_sd else None),
        "total_80pct": ([round(total - 1.2816 * total_sd, 2),
                         round(total + 1.2816 * total_sd, 2)]
                        if total is not None and total_sd else None),
        "note": ("originated by this project from the official team pages; there is no "
                 "market line to compare against in this repository"),
    }


def side_probs(margin, sd):
    """P(home wins) and the cover probability, from the model's own margin."""
    if margin is None or not sd:
        return None
    p_home = S.norm_cdf(margin / sd)
    return {"home_win": round(p_home, 6), "away_win": round(1 - p_home, 6),
            "home_fair_american": S.american_from_prob(p_home),
            "away_fair_american": S.american_from_prob(1 - p_home)}


def total_probs(total, sd):
    if total is None or not sd:
        return None
    return {"total_point_estimate": round(total, 2), "total_sd": round(sd, 3)}


def sgp_price(p_side, p_total, rho, p_side_ci=None, rho_n=None, rho_ci=None):
    """Same-game parlay: naive product beside the measured-dependence price.

    ``rho`` is the measured Pearson r between the two legs' underlying
    quantities.  The copula price uses the equicorrelated Gaussian copula, which
    is the standard construction and is exact for this two-leg case up to
    quadrature error.

    ``independent_if_rho_unmeasurable`` is False when rho came back None: the
    naive product is then printed as "naive, legs assumed independent" and the
    caller must not quote it as the price.
    """
    out = {
        "legs": 2,
        "p_side": round(p_side, 6) if p_side is not None else None,
        "p_total": round(p_total, 6) if p_total is not None else None,
        "naive_product": round(p_side * p_total, 6) if (p_side is not None and p_total is not None) else None,
        "rho": rho,
        "rho_n": rho_n,
        "rho_ci95": rho_ci,
        "rho_measurable": rho is not None,
    }
    if p_side is None or p_total is None:
        out["priced"] = False
        out["reason"] = "a leg probability is missing"
        return out
    if rho is None:
        out["priced"] = False
        out["copula_price"] = None
        out["reason"] = ("no measured correlation between these two legs, so the naive product "
                         "is the only number available and it assumes independence")
        return out
    price = S.parlay_price([p_side, p_total], rho, rho_method="measured Pearson r")
    if price.get("with_rho") is None:
        out["priced"] = False
        out["copula_price"] = None
        out["reason"] = price.get("reason", "copula undefined at this rho")
        return out
    joint = price["with_rho"]
    out["priced"] = True
    out["copula_price"] = round(joint, 6)
    out["dependence_ratio"] = round(joint / (p_side * p_total), 6)
    out["difference_pp"] = round((joint - p_side * p_total) * 100, 4)
    out["note"] = ("the copula price is the one to quote; the naive product is printed beside "
                   "it because the brief requires both")
    if rho_ci and rho_ci[0] is not None and rho_ci[0] <= 0 <= rho_ci[1]:
        out["rho_note"] = ("the measured r is inside its own 95% interval of zero at this n; "
                           "treat the correction as a direction, not a magnitude")
    return out


def cross_game_price(p_a, p_b, assumed_independent=True):
    """Two legs in different games.  Independence is an assumption, and it says so."""
    naive = p_a * p_b if (p_a is not None and p_b is not None) else None
    return {
        "legs": 2,
        "p_a": round(p_a, 6) if p_a is not None else None,
        "p_b": round(p_b, 6) if p_b is not None else None,
        "naive_product": round(naive, 6) if naive is not None else None,
        "copula_price": None,
        "rho": None,
        "rho_measurable": False,
        "priced": False,
        "assumption": ("legs in different games are assumed independent; across-game dependence "
                       "is not measurable from this repository and no number is quoted as if it were"),
    }


def parlay_table(rows):
    """Aggregate a list of priced parlays for the page."""
    priced = [r for r in rows if r.get("priced")]
    return {
        "n": len(rows),
        "n_priced_with_measured_rho": len(priced),
        "n_naive_only": len(rows) - len(priced),
        "mean_dependence_ratio": (round(sum(r["dependence_ratio"] for r in priced) / len(priced), 6)
                                  if priced else None),
        "note": ("a dependence ratio below 1 means the naive product overstates the parlay and "
                 "the bookmaker's product price would be too generous"),
    }
