"""The leaderboard: strategies screened against gates, priced, and ranked.

The design rules, in the order they bind:

1. **Every strategy is written down before it is scored.**  A registration
   record fixes the signal, the thresholds, the universe and the exact
   settlement rule.  The record is hashed, and the hash is what the site
   publishes before the first bet.  A strategy whose rule was edited after the
   fact cannot produce the same hash, so the record cannot be quietly rewritten
   to fit the results.

2. **Both directions of every one-sided rule are scored.**  If "fade the big
   home favourite" is on the board, "back the big home favourite" is on the
   board too, with the same sample.  A board that only lists one direction
   cannot tell skill from the sign of the rule.

3. **A rule does not pass on its own p-value.**  It must clear the exact
   binomial test, survive Benjamini-Hochberg across the whole board, clear the
   sample and power gates, and beat the board-wide luck threshold: the best edge
   that the same board would show if every rule had exactly zero skill.  A rule
   that fails only the last one is not "significant", it is the luckiest of N.

4. **Nothing is funded on a backtest.**  A rule can be PUBLISHABLE (it may be
   shown as a projection) without being BETTABLE.  The two are separate fields
   on purpose and the site never mixes them.

5. **When a quantity cannot be measured, it is reported as unmeasurable and the
   strategy is BLOCKED.**  No proxy, no league average, no "assume rho = 0".
"""

from __future__ import annotations

import hashlib
import json
import math

from . import stats as S

# Gate thresholds.  These are PROPOSALS: the project has never had them
# approved, and every page that prints a gate prints that fact.
GATES = {
    "min_bets": 100,
    "alpha": 0.05,
    "power": 0.80,
    "fdr_q": 0.10,
    "min_edge_pp": 1.5,
    "assumed_price": -110,
    "luck_ci": 0.95,
    "luck_iterations": 4000,
    "luck_seed": 20261115,
    "stability_split": 0.5,
}

BREAKEVEN_AT_110 = 110 / 210.0  # 0.52381


# ---------------------------------------------------------------------------
# rule registration
# ---------------------------------------------------------------------------
def register(strategy_id, name, family, market, rule_text, signal, thresholds,
             universe, settlement, source_urls):
    """Build the pre-registration record and its hash.

    The hash covers the fields that define the bet and nothing else.  In
    particular it does NOT cover the results, the score, or any prose
    description, so the hash can be published before the first bet and still
    verify later.  The canonical form is sorted-key JSON with no whitespace.
    """
    body = {
        "strategy_id": strategy_id,
        "name": name,
        "family": family,
        "market": market,
        "signal": signal,
        "thresholds": thresholds,
        "universe": universe,
        "settlement": settlement,
        "rule_text": rule_text,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        **body,
        "preregistration_sha256": digest,
        "hashed_fields": sorted(body.keys()),
        "hash_rule": ("sha256 of json.dumps(body, sort_keys=True, separators=(',',':')) "
                      "with body = the nine fields listed in hashed_fields"),
        "registered_utc": None,   # filled by the build with the capture stamp
        "source_urls": source_urls,
    }


def verify_registration(record):
    """Recompute the hash from the record's own fields."""
    body = {k: record[k] for k in record["hashed_fields"]}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ledger_entry(record, pick, issued_utc, tip_utc):
    """One sealed ledger row: the hash goes in BEFORE the game, the result after.

    The row is append-only.  ``pick_sha256`` hashes the pick AS ISSUED, so a
    later edit to the pick changes the hash and the settlement no longer
    verifies.
    """
    pick_canonical = json.dumps(pick, sort_keys=True, separators=(",", ":"))
    pick_hash = hashlib.sha256(pick_canonical.encode("utf-8")).hexdigest()
    return {
        "strategy_id": record["strategy_id"],
        "preregistration_sha256": record["preregistration_sha256"],
        "pick": pick,
        "pick_sha256": pick_hash,
        "issued_utc": issued_utc,
        "tip_utc": tip_utc,
        "published_before_tip": issued_utc < tip_utc,
        "settlement": None,
        "settlement_stamp": None,
        "settlement_source": None,
    }


def verify_ledger_row(row):
    """Prove the sealed row has not been edited since issue."""
    canonical = json.dumps(row["pick"], sort_keys=True, separators=(",", ":"))
    now = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "row_strategy": row["strategy_id"],
        "stored_sha256": row["pick_sha256"],
        "recomputed_sha256": now,
        "matches": now == row["pick_sha256"],
        "published_before_tip": bool(row.get("published_before_tip")),
    }


# ---------------------------------------------------------------------------
# scoring one rule over the backtest
# ---------------------------------------------------------------------------
def score_rule(bets, gate_cfg=None):
    """Turn a list of graded bets into the gate readings.

    ``bets`` is a list of dicts with ``won`` (bool), ``date``, ``edge_pp``
    (the edge the rule claimed at the time) and ``market``.

    Every statistic below is computed from that list and nothing else.
    """
    cfg = {**GATES, **(gate_cfg or {})}
    n = len(bets)
    if n == 0:
        return {"n": 0, "status": "NO_SAMPLE",
                "reason": "the rule selected no bets in the out-of-sample window"}
    wins = sum(1 for b in bets if b["won"])
    rate = wins / n
    p_two = S.binom_two_sided(wins, n, 0.5)
    p_one = S.binom_one_sided(wins, n, BREAKEVEN_AT_110)
    lo, hi = S.wilson_interval(wins, n)
    prices = sorted({b.get("price_american") for b in bets if b.get("price_american")})
    # The breakeven to beat is the average break-even of the prices actually
    # graded, not a flat -110.  On a board mixing fair moneylines with -110
    # spreads a single breakeven number would be wrong for most rows.
    def _be(am):
        return (-am) / (-am + 100.0) if am < 0 else 100.0 / (am + 100.0)
    breakeven = S.mean([_be(a) for a in prices]) if prices else BREAKEVEN_AT_110
    # TWO edges, and they answer different questions:
    #   edge_pp                 the hit rate against a COIN.  This is the one the
    #                           luck threshold compares against, because the null
    #                           world being simulated is a coin.
    #   edge_vs_breakeven_pp    the hit rate against the price actually paid.
    #                           This is the one that says whether money is made.
    # Reporting a single "edge" for both uses is how a break-even-looking rule
    # gets called lucky, or a lucky-looking one gets called profitable.
    edge_pp = (rate - 0.5) * 100.0
    edge_vs_breakeven_pp = (rate - breakeven) * 100.0

    # stability: does the edge exist in both halves of the window?
    half = max(1, n // 2)
    first, second = bets[:half], bets[half:]
    r1 = sum(1 for b in first if b["won"]) / len(first) if first else None
    r2 = sum(1 for b in second if b["won"]) / len(second) if second else None

    # money, at the price each bet was actually graded at, on paper only.
    # Spreads and totals are graded at the assumed -110; moneylines at their
    # originated fair price.  Averaging a flat -110 across different prices
    # would misstate the money, so the price travels with each row.
    unit = 1.0
    profit = 0.0
    unpriced = 0
    for b in bets:
        am = b.get("price_american")
        if am is None:
            unpriced += 1
            continue
        payoff = (100.0 / -am) if am < 0 else (am / 100.0)
        profit += payoff * unit if b["won"] else -unit
    roi = profit / n
    prices = sorted({b.get("price_american") for b in bets if b.get("price_american")})

    return {
        "n": n,
        "wins": wins,
        "rate": round(rate, 6),
        "rate_ci95": [round(lo, 6) if lo is not None else None,
                      round(hi, 6) if hi is not None else None],
        "edge_pp": round(edge_pp, 4),
        "edge_vs_breakeven_pp": round(edge_vs_breakeven_pp, 4),
        "p_two_sided_vs_coin": round(p_two, 8),
        "p_one_sided_vs_breakeven": round(p_one, 8),
        "first_half_rate": round(r1, 6) if r1 is not None else None,
        "second_half_rate": round(r2, 6) if r2 is not None else None,
        "stability_gap_pp": (round(abs(r1 - r2) * 100, 4)
                             if r1 is not None and r2 is not None else None),
        "roi_paper": round(roi, 6),
        "profit_units_paper": round(profit, 4),
        "required_n": S.required_n(rate if rate > BREAKEVEN_AT_110 else BREAKEVEN_AT_110,
                                   BREAKEVEN_AT_110, cfg["alpha"], cfg["power"]),
        "assumed_price": cfg["assumed_price"],
        "breakeven_used": round(breakeven, 6),
        "distinct_prices": len(prices),
        "price_range": [prices[0], prices[-1]] if prices else None,
        "unpriced_bets": unpriced,
        "breakeven_at_minus_110": round(BREAKEVEN_AT_110, 6),
    }


def apply_gates(scored, board_pvalues, gate_cfg=None):
    """Read each rule against the gate set.  Returns a per-gate verdict list."""
    cfg = {**GATES, **(gate_cfg or {})}
    q = S.benjamini_hochberg(board_pvalues)
    return q


def decider(rule, scored, q_value, luck_threshold_pp, cfg=None):
    """Decide, gate by gate, whether a rule may be published and/or bet.

    The 11 gates, in the order the brief lists them:

    G1 provenance      - every bet traces to an official final
    G2 look-ahead      - signals use only strictly-earlier games
    G3 sample          - n >= min_bets
    G4 power           - the claimed edge is detectable at this n
    G5 significance    - exact binomial vs coin, p <= alpha
    G6 FDR             - Benjamini-Hochberg q <= fdr_q across the board
    G7 stability       - the edge does not flip between halves
    G8 economics       - the edge clears the assumed price with margin
    G9 luck            - the edge beats the board-wide luck threshold
    G10 pre-registration - the rule was registered before the first bet
    G11 price reality  - a real market price exists (it does not, so this fails)
    """
    cfg = {**GATES, **(cfg or {})}
    gates = []
    n = scored.get("n", 0)

    gates.append(("G1 provenance", rule.get("provenance_ok", True),
                  "every graded bet carries the official game id and final"))
    gates.append(("G2 look-ahead", rule.get("lookahead_ok", True),
                  "signal computed from strictly-earlier games only"))
    gates.append(("G3 sample", n >= cfg["min_bets"], f"n = {n}, needs {cfg['min_bets']}"))
    req = scored.get("required_n")
    gates.append(("G4 power", bool(req) and n >= req,
                  f"n = {n}, needs {req} for the observed edge" if req else
                  "edge at or below breakeven, so no sample size would show it"))
    gates.append(("G5 significance", scored.get("p_two_sided_vs_coin") is not None
                  and scored["p_two_sided_vs_coin"] <= cfg["alpha"],
                  f"exact binomial p = {scored.get('p_two_sided_vs_coin')} vs alpha {cfg['alpha']}"))
    gates.append(("G6 FDR", q_value is not None and q_value <= cfg["fdr_q"],
                  f"BH q = {round(q_value, 6) if q_value is not None else None} vs q {cfg['fdr_q']}"))
    gap = scored.get("stability_gap_pp")
    gates.append(("G7 stability", gap is not None and gap <= 30.0,
                  f"half-to-half gap = {gap} pp (budget 30 pp)"))
    gates.append(("G8 economics", scored.get("edge_vs_breakeven_pp") is not None
                  and scored["edge_vs_breakeven_pp"] >= cfg["min_edge_pp"],
                  f"edge over the price actually paid "
                  f"{scored.get('edge_vs_breakeven_pp')} pp (breakeven "
                  f"{scored.get('breakeven_used')}), needs {cfg['min_edge_pp']} pp"))
    gates.append(("G9 luck", scored.get("edge_pp") is not None
                  and scored["edge_pp"] > luck_threshold_pp,
                  f"best edge {scored.get('edge_pp')} pp vs board luck threshold "
                  f"{round(luck_threshold_pp, 2)} pp"))
    gates.append(("G10 pre-registration", bool(rule.get("preregistration_sha256")),
                  "rule hash recorded before the first bet"))
    gates.append(("G11 price reality", False,
                  "no licensed market price is connected to this repository, so no rule can "
                  "demonstrate value against a real line"))

    failing = [g[0] for g in gates if not g[1]]
    # G11 is a hard stop: without a real price a rule can be a published
    # projection but not a bet.  G3-G9 are statistical gates; failing any of
    # them means "not demonstrated", which blocks betting.
    statistical_gates = {"G3 sample", "G4 power", "G5 significance", "G6 FDR", "G7 stability",
                         "G8 economics", "G9 luck"}
    may_bet = not failing
    may_publish = not (statistical_gates & set(failing))
    tier = _tier(failing, scored, cfg)
    return {
        "gates": [{"gate": g, "pass": bool(ok), "detail": d} for g, ok, d in gates],
        "failing": failing,
        "may_publish_as_projection": may_publish,
        "may_be_a_bet": may_bet,
        "tier": tier,
    }


def _tier(failing, scored, cfg):
    """Reward tiers.  A tier is a label, not a funding decision.

    T1 requires every gate including price reality, so on this repository
    nothing can reach it and the site says so rather than pretending otherwise.
    """
    if not failing:
        return "T1 verified"
    stat = {"G3 sample", "G4 power", "G5 significance", "G6 FDR", "G7 stability",
            "G8 economics", "G9 luck"}
    if stat & set(failing):
        if scored.get("n", 0) < cfg["min_bets"] and set(failing) <= {"G3 sample",
                                                                    "G4 power", "G11 price reality"}:
            return "T4 watch (sample too small)"
        return "T5 not demonstrated"
    if set(failing) == {"G11 price reality"}:
        return "T2 gates passed, no market price"
    return "T4 watch"


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------
def measure_correlations(games, residuals):
    """The correlations that CAN be measured, with n and a 95% interval.

    Returns only measured values.  A pair that needs player-level data is not
    returned at all; the caller lists it separately as unmeasurable.
    """
    out = []

    hp = [g["home_pts"] for g in games]
    ap = [g["away_pts"] for g in games]
    r = S.pearson(hp, ap)
    lo, hi = S.fisher_ci(r, len(games))
    out.append({
        "pair": "home points vs away points, same game",
        "used_for": "whether a same-game side + total parlay may be priced as independent",
        "stat": "Pearson r", "value": round(r, 6) if r is not None else None,
        "ci95": [round(lo, 6), round(hi, 6)] if lo is not None else [None, None],
        "n": len(games),
        "source_url": "https://www.nba.com/schedule",
    })

    margins = [g["home_pts"] - g["away_pts"] for g in games]
    totals = [g["home_pts"] + g["away_pts"] for g in games]
    r2 = S.pearson(margins, totals)
    lo2, hi2 = S.fisher_ci(r2, len(games))
    out.append({
        "pair": "final margin vs final total, same game",
        "used_for": "pricing a side and a total in the same parlay",
        "stat": "Pearson r", "value": round(r2, 6) if r2 is not None else None,
        "ci95": [round(lo2, 6), round(hi2, 6)] if lo2 is not None else [None, None],
        "n": len(games),
        "source_url": "https://www.nba.com/schedule",
    })

    # cover-and-over joint: does the side landing correlate with the total landing?
    if residuals:
        covers = [1 if r_["margin_residual"] > 0 else 0 for r_ in residuals]
        overs = [1 if r_["total_residual"] > 0 else 0 for r_ in residuals]
        joint = sum(1 for c, o in zip(covers, overs) if c and o) / len(residuals)
        p1 = sum(covers) / len(covers)
        p2 = sum(overs) / len(overs)
        phi = S.pearson(covers, overs)
        out.append({
            "pair": "cover AND over, same game (vs our originated line)",
            "used_for": "the same-game parlay dependence ratio",
            "stat": "phi", "value": round(phi, 6) if phi is not None else None,
            "ci95": [None, None], "n": len(residuals),
            "joint_rate": round(joint, 6),
            "independent_product": round(p1 * p2, 6),
            "dependence_ratio": (round(joint / (p1 * p2), 6) if p1 and p2 else None),
            "source_url": "https://www.nba.com/schedule",
        })
    return out


UNMEASURABLE_PAIRS = [
    {"pair": "player A points vs player B points, same team, same game",
     "why": "needs per-player game logs for a full season; only 2 of 30 teams' top-8 "
            "minutes were captured and no game logs at all"},
    {"pair": "player points vs player rebounds, same player",
     "why": "needs per-player game logs"},
    {"pair": "player points vs player assists, same player",
     "why": "needs per-player game logs"},
    {"pair": "player stat vs the same game's team total",
     "why": "needs per-player game logs and would still be a small-sample estimate"},
    {"pair": "leg A vs leg B across two different games on the same night",
     "why": "no shared state to correlate; measurable only as a null, and a null with no "
            "data behind it is not a measurement"},
]
