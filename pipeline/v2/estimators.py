"""Two independent estimators, and the disagreement between them.

The brief asks for two independent estimators whose disagreement is published
as the headline confidence signal, with the blend underneath it, instead of one
blended rating presented as if it were a single truth.  That is what this
module does.

Why two, and why these two
--------------------------
They are independent in the way that matters: **different inputs, different
maths, and no shared quantity**.  If both read the same rating they would agree
by construction and the disagreement would always be zero, which is the failure
mode that makes a single blended rating look eerily confident.

``A`` -- result-based (Massey / ridge least squares)
    Inputs: final margins only.  Fits a team strength per team plus a
    home-court term from the game log.  Knows nothing about shooting, pace or
    schedule.

``B`` -- efficiency-based (four factors off the official team pages)
    Inputs: the official team advanced page (OffRtg, DefRtg, Pace) and the
    official opponent page (Opp PTS, and the opponent shooting the advanced
    page does not carry).  To stay independent of the margin fit it computes a
    possession-and-efficiency margin:

        expected margin = (OffRtg_home - DefRtg_away) * poss / 100
                        - (OffRtg_away - DefRtg_home) * poss / 100

    with home-court advantage PINNED to the measured home-win rate rather than
    fitted (see ``home_court_from_measured_rate``).  It never looks at a final
    margin.

The total is modelled the way the brief asks: possessions x points per
possession, not as the average of two team scoring averages.

    expected_total = poss * (PPP_home + PPP_away)
    PPP_i          = points per possession, from the team's own Pts and Poss

This is why the totals model no longer needs to be shrunk toward a constant to
behave: it is built on the identity between scoring and possessions instead of
being a regression on scoring averages that double-counts pace.
"""

from __future__ import annotations

import math

from . import stats as S


# ---------------------------------------------------------------------------
# home-court advantage, pinned rather than fitted
# ---------------------------------------------------------------------------
def home_court_from_measured_rate(games):
    """Home-court advantage from the measured home-win rate, not a free fit.

    The brief is explicit: pin HCA to the measured home-win rate instead of
    letting a regression choose it.  Fitting it freely lets the model buy
    accuracy by inflating one coefficient on 100-ish games, and the coefficient
    is then not identifiable from the thing it claims to measure.

    The pin is done on the *logit* scale, because that is the scale on which a
    win rate maps to a margin without assuming a distribution:

        p_home = measured home-win rate
        logit(p_home) = log(p/(1-p))
        z = logit(p_home)                    -> a standard-normal margin offset
        HCA_points = z * sd(margin)          -> points

    ``sd(margin)`` is measured from the same games.  The returned value is a
    single number with its own provenance, and it is used by the efficiency
    estimator unchanged.  It is NOT re-estimated per fit, which is what "free"
    would mean.
    """
    n = len(games)
    if n == 0:
        return None
    home_wins = sum(1 for g in games if g["home_pts"] > g["away_pts"])
    p = home_wins / n
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    s = S.sd(margins)
    # clamp so a small sample cannot produce an infinite logit
    p = min(max(p, 0.5 / n), 1 - 0.5 / n)
    z = math.log(p / (1 - p))
    return {
        "n_games": n,
        "home_wins": home_wins,
        "home_win_rate": p,
        "margin_sd": s,
        "hca_points": z * s,
        "method": "logit(p_home) * sd(margin); pinned, not fitted",
        "note": ("The pin is exact on the win rate and assumes only that the margin "
                 "distribution is roughly normal. It is stated as a derivation, not a fact."),
    }


# ---------------------------------------------------------------------------
# estimator A: result-based
# ---------------------------------------------------------------------------
class ResultEstimator:
    """Ridge least squares on final margins.  Team strength + home court."""

    name = "A: result-based (ridge margin fit)"
    code = "pipeline/v2/estimators.py:ResultEstimator"

    def __init__(self, ridge=8.0):
        self.ridge = ridge
        self.rating = {}
        self.hca = 0.0
        self.base_margin = 0.0
        self.fitted_on = 0
        self.teams = []

    def fit(self, games, hca_pinned):
        """``hca_pinned`` is the measured rate.  It is used as a fixed offset,
        which is what makes this estimator's home-court term the SAME number the
        efficiency estimator uses.  The two are therefore independent in their
        team strengths but agree on the one quantity that has an external
        measurement."""
        self.teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
        idx = {t: i for i, t in enumerate(self.teams)}
        p = len(self.teams)
        X, y = [], []
        for g in games:
            row = [0.0] * p
            row[idx[g["home"]]] = 1.0
            row[idx[g["away"]]] = -1.0
            X.append(row)
            # subtract the pinned home-court term so it is not re-fitted here
            y.append(float(g["home_pts"] - g["away_pts"]) - hca_pinned)
        coef = _ridge_solve(X, y, self.ridge)
        self.rating = {t: coef[idx[t]] for t in self.teams}
        self.hca = hca_pinned
        self.base_margin = S.mean([g["home_pts"] - g["away_pts"] for g in games])
        self.fitted_on = len(games)
        return self

    def predict(self, home, away):
        rh, ra = self.rating.get(home), self.rating.get(away)
        if rh is None or ra is None:
            return None
        return {"margin": rh - ra + self.hca, "team_home": rh, "team_away": ra}


# ---------------------------------------------------------------------------
# estimator B: efficiency-based
# ---------------------------------------------------------------------------
class EfficiencyEstimator:
    """Possessions x points-per-possession, from the official team pages."""

    name = "B: efficiency-based (possession x PPP)"
    code = "pipeline/v2/estimators.py:EfficiencyEstimator"

    def __init__(self):
        self.team = {}
        self.hca = 0.0

    def fit(self, team_stats, hca_pinned):
        for t in team_stats["teams"]:
            gp = t["gp"]
            if not gp:
                continue
            # points per possession from the printed totals:
            # POSS is the team's possession count to date and PTS is per game,
            # so total points = PTS * GP and PPP = total points / POSS.
            ppp = (t["pts"] * gp) / t["poss"] if t.get("poss") else None
            opp_ppp = (t["opp_pts"] * gp) / t["poss"] if t.get("poss") else None
            self.team[t["team"]] = {
                "ppp": ppp,
                "opp_ppp": opp_ppp,
                "off_rtg": t.get("off_rtg"),
                "def_rtg": t.get("def_rtg"),
                "pace": t.get("pace"),
                "gp": gp,
            }
        self.hca = hca_pinned
        return self

    def pace(self, home, away):
        a, b = self.team.get(home), self.team.get(away)
        if not a or not b:
            return None
        if a["pace"] is None or b["pace"] is None:
            # Dallas' PACE cell was split across the fetch and is null (FV2-04).
            # The league average pace is NOT substituted: the caller gets None
            # and the game is marked unpriced by this estimator.
            return None
        return (a["pace"] + b["pace"]) / 2.0

    def predict(self, home, away):
        h, a = self.team.get(home), self.team.get(away)
        if not h or not a:
            return None
        poss = self.pace(home, away)
        if poss is None or None in (h["ppp"], a["ppp"], h["opp_ppp"], a["opp_ppp"]):
            return None
        # points per possession each side is expected to score against the other
        ppp_home = (h["ppp"] + a["opp_ppp"]) / 2.0
        ppp_away = (a["ppp"] + h["opp_ppp"]) / 2.0
        total = poss * (ppp_home + ppp_away)
        margin = poss * (ppp_home - ppp_away) + self.hca
        return {
            "margin": margin,
            "total": total,
            "possessions": poss,
            "ppp_home": ppp_home,
            "ppp_away": ppp_away,
            "hca_points": self.hca,
        }


def _ridge_solve(X, y, lam):
    """Solve (X'X + lam*I) b = X'y by Gaussian elimination.

    Ridge without an intercept column, which is correct here because every row
    sums to zero across team columns (home +1, away -1) and the home-court
    offset has already been removed from y.
    """
    p = len(X[0])
    A = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for row, target in zip(X, y):
        for i in range(p):
            if row[i] == 0.0:
                continue
            b[i] += row[i] * target
            for j in range(p):
                A[i][j] += row[i] * row[j]
    for i in range(p):
        A[i][i] += lam
    # gaussian elimination with partial pivoting
    n = p
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-12:
            A[piv][col] = 1e-12
        if piv != col:
            A[col], A[piv] = A[piv], A[col]
            b[col], b[piv] = b[piv], b[col]
        pv = A[col][col]
        for r in range(col + 1, n):
            f = A[r][col] / pv
            if f == 0.0:
                continue
            for c in range(col, n):
                A[r][c] -= f * A[col][c]
            b[r] -= f * b[col]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        # left-to-right sum (stats.dsum): the builtin sum() reorders floats on CPython 3.12
        # and moved the published line by one ulp, which moved every pick hash under it.
        s = b[r] - S.dsum(A[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / A[r][r]
    return x


# ---------------------------------------------------------------------------
# disagreement
# ---------------------------------------------------------------------------
def disagreement(pa, pb):
    """The published confidence signal.

    The headline number is the gap between the two estimators.  It is reported
    in points, and also as a fraction of each estimator's own measured error, so
    that "they disagree by 3 points" can be read against "each is typically
    wrong by 16 points".

    The z-form is the one that matters: ``gap / sqrt(e_A^2 + e_B^2)``.  A gap of
    3 points when each estimator errs by 16 is unremarkable; the same gap when
    each errs by 4 would be a real fight between the models.  Publishing the raw
    point gap alone would make every game look contested.
    """
    if not pa or not pb:
        return None
    out = {}
    for k, label in (("margin", "spread"), ("total", "total")):
        a, b = pa.get(k), pb.get(k)
        if a is None or b is None:
            out[label] = None
            continue
        gap = abs(a - b)
        out[label] = {
            "a": round(a, 3),
            "b": round(b, 3),
            "gap_points": round(gap, 3),
            "signed_gap_b_minus_a": round(b - a, 3),
        }
    return out


def agreement_label(gap_points, combined_sd):
    """Plain-language bucket for the gap.  Deliberately conservative."""
    if gap_points is None or not combined_sd:
        return "unknown"
    ratio = gap_points / combined_sd
    if ratio < 0.25:
        return "agree"
    if ratio < 0.5:
        return "minor disagreement"
    if ratio < 1.0:
        return "material disagreement"
    return "estimators conflict"
