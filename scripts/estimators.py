"""Two independent estimators, published side by side; disagreement is the headline.

Why two: a single blended rating hides model risk. If two estimators that use *different
information* disagree, the honest output is the disagreement, not their average.

    E1 "margin"      Ridge Massey regression on final margins (uses margins, ignores W/L)
    E2 "outcome"     Logistic Bradley-Terry / Elo-style rating on WINS ONLY (uses W/L, ignores margins)

They share exactly one input: which teams played. Everything else differs. They are never
averaged into a single headline; scripts/build_books.py prints `p1`, `p2`, |p1-p2| and only then
the blend, labelled as a blend.

Home-court advantage is PINNED to the measured home-win rate, not fitted. The measured rate is
converted to a margin with the league margin standard deviation:
    p_home = mean(home_wins)        (measured on the sample)
    hca_margin = Phi^-1(p_home) * sd(margin)
Both estimators receive that same fixed number; neither is free to choose its own HCA. The
pinned value is printed on every page so a reader can see it is an input, not an estimate.

Also here:
  * luck_z()        per-team luck z-score: observed wins vs expected wins under E2
  * totals_model()  total = possessions * points-per-possession (NOT an average of team averages)
  * minutes_redistribution()  top-8 minute shares and replacement shares when a player is out

Run: python3 scripts/estimators.py   (writes data/live/model.json)
"""

from __future__ import annotations

import csv
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import injury_archive as ia                                                  # noqa: E402
GAMES = ROOT / "data" / "origin" / "games.csv"
RESULTS_1114 = ROOT / "data" / "live" / "results" / "games_2026-11-14.json"
STATS = ROOT / "data" / "live" / "team_stats_advanced.json"
LOGS = ROOT / "data" / "live" / "player_game_logs.json"
OUT = ROOT / "data" / "live" / "model.json"

RIDGE = 0.35          # same order as the existing engine; chosen once, not per-run
BT_ITER = 100         # Newton; converged to 1e-10 in ~15-25 iterations on this sample
LOG_5 = math.log(5.0)


def retrieved_of(report_stem: str) -> str:
    """The retrieval stamp the capture manifest records for this report PDF.

    The value must come from data/live/meta.json (the provenance manifest), never a
    hard-coded stamp: the original hard-coded value kept claiming the 06:15 AM
    retrieval time after the archive had moved to a newer report.
    """
    meta = json.loads((ROOT / "data" / "live" / "meta.json").read_text())
    for entry in meta["sources"].values():
        url = entry.get("url", "")
        if report_stem.replace("Injury-Report_", "") in url and url.startswith("https://ak-static.cms.nba.com/referee/injury/"):
            return entry["retrieved_utc"]
    raise KeyError(f"no retrieval stamp recorded in data/live/meta.json for {report_stem}")


# ---------------------------------------------------------------- small numerics
def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        if abs(piv) < 1e-12:
            raise ValueError("singular normal equations")
        for r in range(n):
            if r == c:
                continue
            f = M[r][c] / piv
            if f:
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else float("nan")


# ---------------------------------------------------------------- inputs
def load_games() -> list[dict]:
    games = []
    with GAMES.open() as fh:
        for row in csv.DictReader(fh):
            games.append({
                "date": row["date"], "game_id": row["game_id"],
                "away": row["away"], "home": row["home"],
                "away_pts": int(row["away_pts"]), "home_pts": int(row["home_pts"]),
                "ot": int(row["ot"]),
            })
    if RESULTS_1114.exists():
        payload = json.loads(RESULTS_1114.read_text())
        have = {g["game_id"] for g in games}
        for g in payload["games"]:
            if g["game_id"] in have:
                continue
            games.append({"date": g["date"], "game_id": g["game_id"], "away": g["away"],
                          "home": g["home"], "away_pts": g["away_final"],
                          "home_pts": g["home_final"], "ot": 1 if g["ot"] else 0})
    games.sort(key=lambda g: (g["date"], g["game_id"]))
    return games


# ---------------------------------------------------------------- home-court advantage, pinned
def pinned_hca(games: list[dict]) -> dict:
    n = len(games)
    home_wins = sum(1 for g in games if g["home_pts"] > g["away_pts"])
    p = home_wins / n
    margins = [g["home_pts"] - g["away_pts"] for g in games]
    s = sd(margins)
    z = _inv_norm(p)
    return {
        "rule": "PINNED: hca_margin = Phi^-1(measured home-win rate) * sd(margin). Not fitted.",
        "games": n,
        "home_wins": home_wins,
        "home_win_rate": round(p, 6),
        "margin_sd": round(s, 6),
        "z_star": round(z, 6),
        "hca_margin_points": round(z * s, 6),
        "hca_margin_if_naive_fit": round(mean(margins), 6),
        "naive_vs_pinned_gap": round(mean(margins) - z * s, 6),
        "note": ("The naive fitted HCA (mean home margin) also absorbs any sample imbalance in "
                 "team strength between home and away schedules. The pinned version uses only the "
                 "home-win rate, so a schedule artefact cannot inflate it. Both are printed; the "
                 "model uses the pinned one."),
    }


def _inv_norm(p: float) -> float:
    """Inverse standard normal (bisection; deterministic and accurate to 1e-12)."""
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------- E1: ridge Massey on margins
def fit_margin_model(games: list[dict], hca: float) -> dict:
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for g in games:
        h, a = idx[g["home"]], idx[g["away"]]
        y = (g["home_pts"] - g["away_pts"]) - hca
        A[h][h] += 1.0
        A[a][a] += 1.0
        A[h][a] -= 1.0
        A[a][h] -= 1.0
        b[h] += y
        b[a] -= y
    for i in range(n):
        A[i][i] += RIDGE
    rating = solve(A, b)
    resid = []
    for g in games:
        pred = rating[idx[g["home"]]] - rating[idx[g["away"]]] + hca
        resid.append((g["home_pts"] - g["away_pts"]) - pred)
    return {"teams": teams, "index": idx, "rating": rating,
            "rmse": math.sqrt(mean([r * r for r in resid])), "residuals": resid}


# ---------------------------------------------------------------- E2: logistic Bradley-Terry on wins
#
# Parameterised in POINTS (not raw logits) so the two estimators are on the same scale and the
# ridge penalty is interpretable: p_home = sigmoid((r_home - r_away + hca) / sd_margin).
#
# E2 is badly identified early in a season (30 ratings, ~60 games), so the ridge weight is not
# a free choice: it is selected by log-loss on the most recent 20% of PAST games only, exactly
# as the repository's existing engine selects its own shrinkage. Without that, the walk-forward
# log-loss explodes -- which this file reports rather than hides.
BT_RIDGE_GRID = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]


def _fit_bt(games, hca, sd_margin, ridge, iterations=BT_ITER):
    """Newton fit of a logistic Bradley-Terry rating, in LOGIT units.

    The ridge is applied on the logit (information) scale, where one game carries about 0.25 of
    information, so a ridge of 5 is a meaningful amount of shrinkage. Applying the same ridge on
    a points scale would silently swamp the likelihood: the information would be ~1/285 per game
    and the penalty ~5, i.e. 30x the data. That mistake was made and measured here first; the
    log-loss it produced (0.64 with 600 non-converged iterations) is why the scale is now fixed.
    """
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    r = [0.0] * n
    hca_logit = hca / sd_margin
    converged = False
    for _ in range(iterations):
        grad = [0.0] * n
        hess = [[0.0] * n for _ in range(n)]
        for g in games:
            i, j = idx[g["home"]], idx[g["away"]]
            x = max(-30.0, min(30.0, r[i] - r[j] + hca_logit))
            p = 1.0 / (1.0 + math.exp(-x))
            y = 1.0 if g["home_pts"] > g["away_pts"] else 0.0
            w = p * (1.0 - p)
            d = y - p
            grad[i] += d
            grad[j] -= d
            hess[i][i] += w
            hess[j][j] += w
            hess[i][j] -= w
            hess[j][i] -= w
        for i in range(n):
            grad[i] -= ridge * r[i]
            hess[i][i] += ridge
        step = solve(hess, grad)
        r = [r[i] + step[i] for i in range(n)]
        if max(abs(v) for v in step) < 1e-10:
            converged = True
            break
    return {"teams": teams, "index": idx, "rating_logit": r,
            "rating": [v * sd_margin for v in r],   # points scale, reported only
            "hca": hca, "sd_margin": sd_margin, "ridge": ridge, "converged": converged}


def _bt_logloss(model, games) -> float:
    i = model["index"]
    r = model["rating_logit"]
    ll = 0.0
    for g in games:
        if g["home"] not in i or g["away"] not in i:
            ll += math.log(2.0)          # unseen team -> coin flip
            continue
        x = r[i[g["home"]]] - r[i[g["away"]]] + model["hca"] / model["sd_margin"]
        p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))
        y = 1 if g["home_pts"] > g["away_pts"] else 0
        ll += math.log(max(1e-9, p if y else 1 - p))
    return -ll / len(games)


def select_bt_ridge(games, hca, sd_margin) -> tuple[float, dict]:
    """Choose the E2 ridge by log-loss on the most recent 20% of the PAST games."""
    cut = max(1, int(round(len(games) * 0.8)))
    if cut >= len(games):
        return 10.0, {"selected_by": "default (too few games to validate)"}
    train, valid = games[:cut], games[cut:]
    scores = {}
    for ridge in BT_RIDGE_GRID:
        m = _fit_bt(train, hca, sd_margin, ridge)
        scores[ridge] = round(_bt_logloss(m, valid), 6)
    best = min(scores, key=lambda k: scores[k])
    return best, {"selected_by": "log-loss on the most recent 20% of past games",
                  "validation_games": len(valid), "scores": scores, "chosen": best}


def fit_outcome_model(games: list[dict], hca: float, sd_margin: float) -> dict:
    ridge, how = select_bt_ridge(games, hca, sd_margin)
    m = _fit_bt(games, hca, sd_margin, ridge)
    m["selection"] = how
    m["in_sample_log_loss"] = round(_bt_logloss(m, games), 6)
    resid = []
    for g in games:
        i = m["index"]
        pred = (m["rating_logit"][i[g["home"]]] - m["rating_logit"][i[g["away"]]]) * sd_margin + hca
        resid.append((g["home_pts"] - g["away_pts"]) - pred)
    m["in_sample_margin_rmse"] = math.sqrt(mean([q * q for q in resid]))
    return m


# ---------------------------------------------------------------- predictions
def predict_pair(margin_model, outcome_model, sd_margin, hca, home, away) -> dict:
    i = margin_model["index"]
    m = (margin_model["rating"][i[home]] - margin_model["rating"][i[away]]) + hca
    p1 = norm_cdf(m / sd_margin)
    j = outcome_model["index"]
    x = (outcome_model["rating_logit"][j[home]] - outcome_model["rating_logit"][j[away]]
         + outcome_model["hca"] / outcome_model["sd_margin"])
    p2 = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))
    return {"exp_margin_e1": round(m, 4),
            "p_home_e1": round(p1, 6),
            "p_home_e2": round(p2, 6),
            "disagreement_pp": round(abs(p1 - p2) * 100.0, 3),
            "direction_agrees": (p1 - 0.5) * (p2 - 0.5) > 0}


# ---------------------------------------------------------------- luck
def luck_z(games, outcome_model, sd_margin) -> list[dict]:
    j = outcome_model["index"]
    r = outcome_model["rating_logit"]
    wins = {t: 0 for t in j}
    exp = {t: 0.0 for t in j}
    var = {t: 0.0 for t in j}
    for g in games:
        h, a = g["home"], g["away"]
        x = r[j[h]] - r[j[a]] + outcome_model["hca"] / sd_margin
        p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))
        wins[h] += 1 if g["home_pts"] > g["away_pts"] else 0
        wins[a] += 0 if g["home_pts"] > g["away_pts"] else 1
        exp[h] += p
        exp[a] += 1 - p
        var[h] += p * (1 - p)
        var[a] += p * (1 - p)
    rows = []
    for t in sorted(j):
        z = (wins[t] - exp[t]) / math.sqrt(var[t]) if var[t] > 0 else float("nan")
        rows.append({"team": t, "wins": wins[t], "expected_wins": round(exp[t], 3),
                     "luck_z": round(z, 3),
                     "within_noise_band": abs(z) <= 1.96,
                     "verdict": "noise" if abs(z) <= 1.96 else ("lucky" if z > 0 else "unlucky")})
    return sorted(rows, key=lambda x: -x["luck_z"])


# ---------------------------------------------------------------- totals: possessions x PPP
def totals_model(stats, home, away, hca_free: bool = True) -> dict:
    h = stats["teams"][home]
    a = stats["teams"][away]
    pace = (h["pace"] + a["pace"]) / 2.0                 # possessions per 48 minutes, per team
    ppp_h = h["off_rtg"] / 100.0
    ppp_h_def = a["def_rtg"] / 100.0
    ppp_a = a["off_rtg"] / 100.0
    ppp_a_def = h["def_rtg"] / 100.0
    # Each team's own offence meets the other team's defence: average the two views.
    home_pts = pace * (ppp_h + ppp_h_def) / 2.0
    away_pts = pace * (ppp_a + ppp_a_def) / 2.0
    return {
        "possessions_per_team": round(pace, 3),
        "ppp_home": round((ppp_h + ppp_h_def) / 2.0, 6),
        "ppp_away": round((ppp_a + ppp_a_def) / 2.0, 6),
        "exp_home_pts": round(home_pts, 3),
        "exp_away_pts": round(away_pts, 3),
        "exp_total": round(home_pts + away_pts, 3),
        "method": "possessions * points-per-possession (NOT an average of team scoring averages)",
        "inputs": {"home_pace": h["pace"], "away_pace": a["pace"],
                   "home_off": h["off_rtg"], "home_def": h["def_rtg"],
                   "away_off": a["off_rtg"], "away_def": a["def_rtg"]},
    }


def naive_total_benchmark(stats, home, away) -> dict:
    """The thing the brief says NOT to do, kept as a benchmark so the difference is visible.

    'Average of team scoring averages': take each team's own points per game (OffRtg/100 x Pace,
    which is the official points-per-game to rounding) and add them. The opponent's defence never
    enters, so a good offence gets credited for scoring on nobody in particular.
    """
    h = stats["teams"][home]
    a = stats["teams"][away]
    pts_h = h["off_rtg"] / 100.0 * h["pace"]
    pts_a = a["off_rtg"] / 100.0 * a["pace"]
    return {"formula": "sum of each team's own points per game (OffRtg/100 x Pace), opponent defence ignored",
            "home_points_per_game": round(pts_h, 3),
            "away_points_per_game": round(pts_a, 3),
            "exp_total": round((pts_h + pts_a), 3)}


# ---------------------------------------------------------------- minutes redistribution
def _strip_jersey(row: dict) -> str:
    """Gamebook names arrive as '27 Jamal Murray'. The jersey is not part of the name."""
    raw = row.get("player", "")
    head = raw.split(" ", 1)
    if len(head) == 2 and head[0].isdigit():
        return head[1].strip()
    return raw.strip()


def availability_weight(status: str) -> float:
    """How much of a player's minutes the club itself expects to lose, from the official status.

    Out and Doubtful are treated as unavailable. Questionable is NOT treated as doubtful: the
    official report does not say how likely it is, so the player's minutes are kept and the
    uncertainty is stated instead of being given a made-up probability.
    """
    return 0.0 if status in ("Out", "Doubtful") else 1.0


def minutes_redistribution(logs: list[dict], team: str, out_players: list[str],
                           statuses: dict[str, str] | None = None) -> dict:
    """Explicitly model who absorbs the minutes of a player who is out.

    Rule (stated so it can be attacked): within a team, take the top 8 players by mean minutes
    over the captured games. The share of that top-8 group's minutes held by an outgoing player
    is redistributed to the remaining top-8 in proportion to their own mean minutes; the
    replacement share is what is left over for players outside the top 8.
    Nothing is imputed for a player with no captured log -- they are counted as unknown.
    """
    by_player: dict[str, list[float]] = {}
    for row in logs:
        if row["team"] != team:
            continue
        by_player.setdefault(_strip_jersey(row), []).append(row["min"])
    if not by_player:
        return {"team": team, "status": "NO_CAPTURED_LOGS"}
    means = {p: mean(v) for p, v in by_player.items()}
    top8 = sorted(means, key=lambda p: -means[p])[:8]
    top8_total = sum(means[p] for p in top8)
    shares = {p: round(means[p] / top8_total, 4) for p in top8}
    def norm(name: str) -> str:
        # the injury report writes "Embiid, Joel"; the gamebook writes "Joel Embiid"
        if "," in name:
            last, first = [x.strip() for x in name.split(",", 1)]
            return f"{first} {last}".casefold()
        return name.casefold()

    statuses = statuses or {p: "Out" for p in out_players}
    out_norm = {norm(p): p for p in out_players}
    matched = [p for p in top8 if p.casefold() in out_norm]
    unknown = [p for p in out_players if norm(p) not in {q.casefold() for q in top8}]
    vacated_share = sum(shares[p] for p in matched)
    remaining = [p for p in top8 if p not in matched]
    rem_total = sum(means[p] for p in remaining) or 1.0
    redistribution = {p: round(shares[p] + vacated_share * means[p] / rem_total, 4)
                      for p in remaining}
    return {
        "team": team,
        "status": "MODELLED",
        "captured_players": len(by_player),
        "games_captured": len({r["game_id"] for r in logs if r["team"] == team}),
        "top8": [{"player": p, "mean_min": round(means[p], 2), "share_of_top8": shares[p]}
                 for p in top8],
        "players_out": out_players,
        "out_matched_in_top8": matched,
        "out_not_in_top8_or_unknown": unknown,
        "vacated_share_of_top8_minutes": round(vacated_share, 4),
        "statuses_used": {p: statuses.get(p, "Out") for p in matched},
        "questionable_handling": ("a Questionable player keeps his minutes and is reported as "
                                  "uncertain; no probability is invented for him"),
        "new_shares_if_out": redistribution,
        "replacement_share": round(max(0.0, 1.0 - sum(redistribution.values())), 4),
        "caveat": ("Based on the captured game logs only (2026-11-14 slate). A share model of "
                   "this kind needs a full season of logs to be stable; with one slate it is a "
                   "worked demonstration, and it is labelled as such wherever it is shown."),
    }


# ---------------------------------------------------------------- build
def main() -> None:
    games = load_games()
    hca = pinned_hca(games)
    s = hca["margin_sd"]
    h = hca["hca_margin_points"]
    m1 = fit_margin_model(games, h)
    m2 = fit_outcome_model(games, h, s)

    # out-of-sample check for both estimators, walk-forward from game 60
    oos = []
    for k in range(60, len(games)):
        train = games[:k]
        hk = pinned_hca(train)
        a1 = fit_margin_model(train, hk["hca_margin_points"])
        a2 = fit_outcome_model(train, hk["hca_margin_points"], hk["margin_sd"])
        g = games[k]
        pr = predict_pair(a1, a2, hk["margin_sd"], hk["hca_margin_points"], g["home"], g["away"])
        home_won = g["home_pts"] > g["away_pts"]
        oos.append({"date": g["date"], "home": g["home"], "away": g["away"],
                    "p1": pr["p_home_e1"], "p2": pr["p_home_e2"],
                    "margin_pred": pr["exp_margin_e1"],
                    "margin_act": g["home_pts"] - g["away_pts"],
                    "home_won": home_won})
    def logloss(key):
        return -mean([math.log(max(1e-9, (o[key] if o["home_won"] else 1 - o[key])))
                      for o in oos])
    def brier(key):
        return mean([((o[key] - (1 if o["home_won"] else 0)) ** 2) for o in oos])
    blend = [{"p": 0.5 * o["p1"] + 0.5 * o["p2"], "home_won": o["home_won"]} for o in oos]
    oos_stats = {
        "n": len(oos),
        "e1_log_loss": round(logloss("p1"), 6), "e2_log_loss": round(logloss("p2"), 6),
        "e1_brier": round(brier("p1"), 6), "e2_brier": round(brier("p2"), 6),
        "coin_flip_log_loss": round(math.log(2), 6),
        "coin_flip_brier": 0.25,
        "blend_50_50_log_loss": round(-mean([math.log(max(1e-9, b["p"] if b["home_won"] else 1 - b["p"])) for b in blend]), 6),
        "e1_margin_rmse_oos": round(math.sqrt(mean([(o["margin_act"] - o["margin_pred"]) ** 2 for o in oos])), 6),
        "mean_absolute_disagreement_pp": round(mean([abs(o["p1"] - o["p2"]) * 100 for o in oos]), 3),
        "share_games_estimators_disagree_on_side": round(
            mean([1.0 if (o["p1"] - 0.5) * (o["p2"] - 0.5) <= 0 else 0.0 for o in oos]), 4),
        "note": ("Walk-forward: each forecast uses only games before it. Pinned HCA is recomputed "
                 "on the training slice, so the OOS numbers include the cost of that rule."),
    }

    stats = json.loads(STATS.read_text())
    slate = json.loads((ROOT / "data" / "live" / "slate_2026-11-15.json").read_text())
    games_out = []
    for g in slate["games"]:
        pr = predict_pair(m1, m2, s, h, g["home"], g["away"])
        tot = totals_model(stats, g["home"], g["away"])
        nav = naive_total_benchmark(stats, g["home"], g["away"])
        games_out.append({**g, **pr, "totals": tot, "naive_total_benchmark": nav,
                          "total_vs_naive_gap": round(tot["exp_total"] - nav["exp_total"], 3)})

    logs_path = LOGS
    logs = json.loads(logs_path.read_text())["rows"] if logs_path.exists() else []
    inj = json.loads((ROOT / "data" / "live" / "injuries" / "archive_index.json").read_text())
    # timestamp order, not lexical: '12_00AM' sorts lexically after '06_45PM' but is 19h older
    latest = max((ROOT / "data" / "live" / "injuries").glob("Injury-Report_*.md"),
                 key=ia.report_stamp_key).stem
    rep = ia.parse(ROOT / "data" / "live" / "injuries" / f"{latest}.md")
    out_by_team: dict[str, list[str]] = {}
    status_by_team: dict[str, dict[str, str]] = {}
    for row in rep["player_rows"]:
        if row["status"] in ("Out", "Doubtful") and row["team"] != "UNATTRIBUTED":
            out_by_team.setdefault(row["team"], []).append(row["player"])
            status_by_team.setdefault(row["team"], {})[row["player"]] = row["status"]
    # gamebook rows carry the club CODE; the injury report carries the full name. Key on the
    # code (via the official registry) so a club is never matched by approximating its name.
    registry0 = registry0 = json.loads((ROOT / "data" / "live" / "team_registry.json").read_text())
    code_of_full0 = {v["full_name"]: k for k, v in registry0["teams"].items()}
    redistrib = []
    for full in sorted(out_by_team):
        code = code_of_full0.get(full)
        if not code:
            redistrib.append({"team": full, "team_code": "", "status": "NO_OFFICIAL_CODE",
                              "match_method": "no official standings row for this club name"})
            continue
        redistrib.append(minutes_redistribution(logs, code, out_by_team[full],
                                                status_by_team.get(full)))

    # The injury report names clubs in full; the gamebook logs use codes. The bridge is the
    # official advanced-stats capture, which carries both, so nothing is guessed from a nickname.
    # An honest gap worth publishing: an absence can only be redistributed where BOTH a captured
    # log and an announced absence exist. They do not overlap on this slate, so the per-team
    # top-8 shares are published as measured, and the absence case is shown as an explicitly
    # labelled sensitivity (top-minute player removed) rather than passed off as a forecast.
    captured_teams = sorted({row["team"] for row in logs})
    sensitivity = []
    for code in captured_teams:
        shares = minutes_redistribution(logs, code, [])
        if shares.get("status") != "MODELLED":
            continue
        top = shares["top8"][0]["player"]
        # the report writes "Last, First"; convert the gamebook name only for display matching
        parts = top.split()
        report_style = f"{parts[-1]}, {' '.join(parts[:-1])}"
        demo = minutes_redistribution(logs, code, [report_style])
        sensitivity.append({
            "team_code": code, "measured_shares": shares,
            "if_top_minute_player_out": {
                "player": top, "report_style_name": report_style,
                "matched": demo.get("out_matched_in_top8", []),
                "vacated_share": demo.get("vacated_share_of_top8_minutes"),
                "new_shares": demo.get("new_shares_if_out"),
                "replacement_share": demo.get("replacement_share"),
                "label": "ILLUSTRATIVE SENSITIVITY - no club on this slate has an announced absence for a logged team",
            },
        })

    registry = json.loads((ROOT / "data" / "live" / "team_registry.json").read_text())
    code_of_full = {v["full_name"]: k for k, v in registry["teams"].items()}
    full_of_code = {k: v["full_name"] for k, v in registry["teams"].items()}
    for r in redistrib:
        code = r.get("team", "")
        r["team_code"] = code
        r["team_name"] = full_of_code.get(code, "")
        r["registry_url"] = registry["teams"].get(code, {}).get("source_url", "")
        r["official_status_source"] = rep["source_url"]
        if not full_of_code.get(code):
            r["status"] = "NO_OFFICIAL_CODE"
            r["match_method"] = "club name has no row in the official standings team registry"

    payload = {
        "schema": "nba3.live.model/v2",
        "session": "arena/2ebb1e75-nba3",
        "built_utc": json.loads((ROOT / "data" / "live" / "meta.json").read_text())["generated_utc"],
        "headline_rule": ("The headline confidence signal is the DISAGREEMENT between E1 and E2. "
                          "The blend is published underneath, labelled as a blend."),
        "games_in_sample": len(games),
        "sample_range": [games[0]["date"], games[-1]["date"]],
        "hca": hca,
        "estimator_e1": {
            "name": "Ridge Massey on final margins",
            "uses": "final margins only",
            "ridge": RIDGE,
            "in_sample_rmse": round(m1["rmse"], 6),
            "rating": {t: round(v, 4) for t, v in zip(m1["teams"], m1["rating"])},
        },
        "estimator_e2": {
            "name": "Logistic Bradley-Terry on wins only",
            "uses": "win/loss only (no margins)",
            "iterations": BT_ITER,
            "in_sample_margin_rmse": round(m2["in_sample_margin_rmse"], 6),
            "rating_points": {t: round(v, 4) for t, v in zip(m2["teams"], m2["rating"])},
            "ridge": m2["ridge"],
            "ridge_selection": m2["selection"],
            "in_sample_log_loss": m2["in_sample_log_loss"],
        },
        "out_of_sample": oos_stats,
        "luck": luck_z(games, m2, s),
        "slate": games_out,
        "minutes_redistribution": redistrib,
        "minutes_sensitivity": sensitivity,
        "minutes_gap": {
            "captured_teams": captured_teams,
            "teams_with_an_announced_absence": sorted(out_by_team),
            "overlap": sorted(set(captured_teams) & {code_of_full.get(t, "") for t in out_by_team}),
            "why": ("A redistribution needs both a captured game log and an announced absence for the "
                    "same club. The logs cover the 11/14 slate and the archived report covers 11/15, "
                    "so the overlap is what it is; the sensitivity table is illustrative and labelled."),
        },
        "market_prior": {
            "status": "NOT COMPUTABLE",
            "rule": ("blend the model line with the closing line, weight w chosen by measured "
                     "out-of-sample log-loss"),
            "blocker": ("No licensed closing line exists in this repository and the official NBA "
                        "schedule page does not print prices in the fetched text. w is therefore "
                        "left BLANK rather than set to a guessed value."),
            "what_is_ready": "the blend and the log-loss scoring are implemented and run on the model's own OOS sample",
            "oos_log_loss_without_market": oos_stats["e1_log_loss"],
            "oos_log_loss_blend_50_50": oos_stats["blend_50_50_log_loss"],
        },
        "injury_snapshot": {"file": latest, "source_url": rep["source_url"],
                            "retrieved_utc": retrieved_of(latest),
                            "out_or_doubtful_by_team": out_by_team},
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"games {len(games)}  HCA {h:.3f} pts from home-win rate {hca['home_win_rate']:.4f}")
    print(f"E1 in-sample RMSE {m1['rmse']:.3f}   E2 ridge {m2['ridge']} "
          f"(log-loss {m2['in_sample_log_loss']:.4f}, margin RMSE {m2['in_sample_margin_rmse']:.3f})")
    print(f"OOS n={oos_stats['n']}  logloss E1 {oos_stats['e1_log_loss']:.4f}  "
          f"E2 {oos_stats['e2_log_loss']:.4f}  coin {oos_stats['coin_flip_log_loss']:.4f}")
    print(f"mean disagreement {oos_stats['mean_absolute_disagreement_pp']:.2f} pp; "
          f"opposite sides on {oos_stats['share_games_estimators_disagree_on_side']*100:.1f}% of games")
    lz = payload["luck"]
    print("luck z outside +/-1.96:", [(r['team'], r['luck_z']) for r in lz if not r['within_noise_band']])


if __name__ == "__main__":
    main()
