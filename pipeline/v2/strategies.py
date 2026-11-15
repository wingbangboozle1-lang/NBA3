"""The strategy board, written down as pre-registrations.

Fifteen rules: twelve single bets (six one-sided rules and their mirrors), one
same-game parlay, one cross-game parlay, one null control.  Each carries the
four things the brief demands are frozen before the first bet -- signal,
thresholds, universe, exact settlement -- plus the mirror where one exists.

**The market-anchored prior is stated, not applied.**  The brief asks the model
line to be blended with the closing line, weighted by measured out-of-sample
log-loss.  The first half of that sentence is computable here and the second
half is not: there is no closing line in this repository and no licensed odds
feed, so there is nothing to blend with and no out-of-sample log-loss against a
market to weight by.  Rather than invent a weight, the blend is defined and
left at ``w_market = None`` with the reason, and every price on the site is the
market-free price.  When a price feed is connected the same function fills the
weight in from data.
"""

from __future__ import annotations

from .leaderboard import register

ASSUMED_PRICE = -110

# Honest provenance line reused on every rule: the backtest is against OUR OWN
# originated line, not against a book.
PROV = ("Backtested against the project's own originated line, settled from the official "
        "final. No market price is involved, so the number measures whether our own line is "
        "biased in a way the rule can exploit -- not whether a bookmaker would have paid.")
SRC_SCHEDULE = "https://www.nba.com/schedule"
SRC_GAME = "https://www.nba.com/game/"


def _universe(live_window=True):
    return {
        "games": ("every regular-season game in the official log with a final score, in "
                  "date order, from 2026-10-20"),
        "excluded": "no game is excluded; the backtest uses all 183 finals captured",
        "live_window": ("the same rule is applied to the 22 upcoming games on "
                        "2026-11-15..2026-11-17 to produce projections") if live_window else "",
    }


def _settlement(kind):
    return {
        "moneyline": ("the side named wins the game outright in the official final score. "
                      "A game that goes to overtime settles on the final including overtime."),
        "spread": ("the named side covers the number originated by this project, measured "
                   "against the official final margin. A push is not a win and not a loss; "
                   "pushes are excluded from the hit rate and counted separately."),
        "total": ("the combined official final score is over or under the number originated "
                  "by this project. Pushes excluded and counted separately."),
        "sgp": ("both legs settle on the SAME official final: the side against our margin "
                "and the total against our total. The parlay wins only if both win."),
        "cross": ("both legs settle on their own official finals; the parlay wins only if "
                  "both legs win."),
        "null": ("the control fires on a fixed coin flip independent of any team, pitched at "
                 "the same assumed price. It MUST show no edge; if it shows one the "
                 "measurement, not the market, is broken."),
    }[kind]


RULES = []


def _add(sid, name, family, market, rule_text, signal, thresholds, settlement_kind,
         mirror_of=None, direction=None, data_need=None):
    RULES.append({
        "strategy_id": sid, "name": name, "family": family, "market": market,
        "rule_text": rule_text, "signal": signal, "thresholds": thresholds,
        "universe": _universe(), "settlement": _settlement(settlement_kind),
        "mirror_of": mirror_of, "direction": direction,
        "data_need": data_need,
        "provenance_note": PROV,
        "source_urls": [SRC_SCHEDULE],
    })


# --- single bets: three one-sided ideas and their exact mirrors ---------------
_add("S01", "Fade the big home favourite", "single", "spread",
     "When estimator A's margin puts the home side at 7 points or more, take the AWAY side "
     "against our own line.",
     "estimator A expected margin (home - away) >= +7.0",
     {"min_abs_margin": 7.0}, "spread", direction="away")

_add("S02", "Back the big home favourite", "single", "spread",
     "Exact mirror of S01: when A's margin puts the home side at 7 or more, take the HOME side "
     "against our own line. This exists so the sign of S01 cannot be mistaken for skill.",
     "estimator A expected margin (home - away) >= +7.0",
     {"min_abs_margin": 7.0}, "spread", mirror_of="S01", direction="home")

_add("S03", "Under a high total", "single", "total",
     "When our originated total is 235 or higher, take the UNDER.",
     "originated total >= 235.0", {"min_total": 235.0}, "total", direction="under")

_add("S04", "Over a high total", "single", "total",
     "Exact mirror of S03: when our originated total is 235 or higher, take the OVER.",
     "originated total >= 235.0", {"min_total": 235.0}, "total", mirror_of="S03",
     direction="over")

_add("S05", "Rested home team vs a back-to-back road team", "single", "spread",
     "When the home team has 2 or more rest days and the road team played the night before, "
     "take the HOME side against our own line.",
     "rest_days(home) >= 2 AND rest_days(away) == 1",
     {"home_rest_min": 2, "away_rest_exact": 1}, "spread", direction="home")

_add("S06", "Fade the rested home team", "single", "spread",
     "Exact mirror of S05.",
     "rest_days(home) >= 2 AND rest_days(away) == 1",
     {"home_rest_min": 2, "away_rest_exact": 1}, "spread", mirror_of="S05",
     direction="away")

_add("S07", "Back the home team on a back-to-back", "single", "spread",
     "When the home team played the night before, take the HOME side.",
     "rest_days(home) == 1", {"home_rest_exact": 1}, "spread", direction="home")

_add("S08", "Fade the home team on a back-to-back", "single", "spread",
     "Exact mirror of S07.",
     "rest_days(home) == 1", {"home_rest_exact": 1}, "spread", mirror_of="S07",
     direction="away")

_add("S09", "Moneyline the model favourite", "single", "moneyline",
     "When the estimators agree on the favourite AND the gap between them is under 20% of "
     "their combined error, take that favourite's moneyline at our fair price.",
     "sign(A margin) == sign(B margin) AND |A - B| < 0.20 * sqrt(e_A^2 + e_B^2)",
     {"max_gap_frac_of_error": 0.20}, "moneyline", direction="favourite")

_add("S10", "Moneyline the model underdog", "single", "moneyline",
     "Exact mirror of S09: take the other side at our fair price.",
     "sign(A margin) == sign(B margin) AND |A - B| < 0.20 * sqrt(e_A^2 + e_B^2)",
     {"max_gap_frac_of_error": 0.20}, "moneyline", mirror_of="S09", direction="underdog")

_add("S11", "Take the side the estimators disagree on", "single", "spread",
     "When the estimators disagree by more than their combined error, back the side "
     "estimator B favours, because B uses possessions and A only sees results.",
     "|A - B| > sqrt(e_A^2 + e_B^2)", {"min_gap_frac_of_error": 1.0}, "spread",
     direction="B")

_add("S12", "Fade the side the estimators disagree on", "single", "spread",
     "Exact mirror of S11: back estimator A's side in the same games.",
     "|A - B| > sqrt(e_A^2 + e_B^2)", {"min_gap_frac_of_error": 1.0}, "spread",
     mirror_of="S11", direction="A")

# --- parlays -----------------------------------------------------------------
_add("P01", "Same-game: model side plus Under", "parlay", "sgp",
     "On games where our total is at the top of the range, take the model-favoured side AND "
     "the Under. Priced twice: naive product and measured rho.",
     "originated total >= 235 AND the estimators agree on the favourite",
     {"min_total": 235.0, "agreement_required": True}, "sgp")

_add("P02", "Cross-game: two independent sides", "parlay", "cross",
     "On nights with two or more games, take the model favourite in the two games furthest "
     "apart on the calendar. Independence across games is a real assumption here, not a "
     "measured one, and the page says so.",
     "at least two games on the date; the two with the largest gap between estimator A and B "
     "in the same direction",
     {"min_games": 2}, "cross")

# --- player props: registered, then BLOCKED on data --------------------------
_add("R01", "Player points over his season average", "prop", "player_points",
     "Take a player's points OVER his own season-to-date average, from the official player "
     "page, whenever he is not on the injury report.",
     "player is not listed Out on the newest official report", {"min_gp": 5}, "total",
     direction="over", data_need="per-player game logs for a season")

_add("R02", "Player points under his season average", "prop", "player_points",
     "Exact mirror of R01.",
     "player is not listed Out on the newest official report", {"min_gp": 5}, "total",
     mirror_of="R01", direction="under", data_need="per-player game logs for a season")

_add("R03", "Two-team player-points combo", "prop", "player_combo",
     "Combine two players' points Overs from two different games on the same night.",
     "both players are not listed Out and both have at least 5 games",
     {"min_gp": 5, "min_games": 2}, "cross", data_need="per-player game logs for a season")

# --- the control -------------------------------------------------------------
_add("N01", "NULL CONTROL: a coin flip", "null", "moneyline",
     "A fixed-seed coin flip decides the side. It has no signal by construction. If it shows "
     "an edge, the measurement is broken, not the market.",
     "random.Random(20261115).random() < 0.5 chooses home, else away",
     {}, "null")


def build_registrations(registered_utc="2026-11-15T12:10Z"):
    out = []
    for r in RULES:
        rec = register(
            r["strategy_id"], r["name"], r["family"], r["market"], r["rule_text"],
            r["signal"], r["thresholds"], r["universe"], r["settlement"], r["source_urls"],
        )
        rec["registered_utc"] = registered_utc
        rec["mirror_of"] = r["mirror_of"]
        rec["direction"] = r["direction"]
        rec["data_need"] = r["data_need"]
        rec["provenance_note"] = r["provenance_note"]
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# market-anchored prior
# ---------------------------------------------------------------------------
def market_anchored_prior(model_margin, closing_margin, w_market):
    """Blend the model line with the closing line, weighted by measured log-loss.

    ``w_market`` must be a measured out-of-sample weight, i.e. the weight that
    minimised log-loss on games that were not used to fit either side.  This
    repository has no closing line and no market log-loss, so the caller passes
    ``closing_margin=None`` and ``w_market=None`` and gets the model line back
    with ``applied: False``.

    The function exists in this shape on purpose: defining the blend and
    refusing to apply it is honest, whereas applying an invented weight would
    not be.
    """
    if closing_margin is None or w_market is None:
        return {
            "model_margin": model_margin,
            "closing_margin": closing_margin,
            "w_market": w_market,
            "blended_margin": model_margin,
            "applied": False,
            "reason": ("no licensed closing line is connected to this repository, so the market "
                       "weight cannot be measured and the blend is not applied"),
        }
    if not (0.0 <= w_market <= 1.0):
        raise ValueError("w_market must be in [0,1]")
    return {
        "model_margin": model_margin,
        "closing_margin": closing_margin,
        "w_market": w_market,
        "blended_margin": w_market * closing_margin + (1 - w_market) * model_margin,
        "applied": True,
        "reason": "w_market measured out of sample",
    }
