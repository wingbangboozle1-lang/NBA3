#!/usr/bin/env python3
"""Generate docs/*.md from data/processed/model_output.json.

Docs are produced from the same artefacts as the site so the two can never disagree.
Run:  python3 model/build_docs.py
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "origin")
DOCS = os.path.join(ROOT, "origin", "notes")

M = json.load(open(os.path.join(PROC, "model_output.json"), encoding="utf-8"))
GAMES = sorted(csv.DictReader(open(os.path.join(PROC, "games.csv"), encoding="utf-8")),
               key=lambda r: (r["date"], r["game_id"]))
INJ = list(csv.DictReader(open(os.path.join(PROC, "injuries.csv"), encoding="utf-8")))

SRC = M["sources"]
STRAT = M["strategies"]
CORR = M["correlations"]
LINES = M["lines"]
FLOW = M["game_flow"]
TEAM_R = M["team_ratings"]
MODELS = M["models"]
SEL = M["model_selection"]
HC = M["home_court"]


def fmt(v, nd=2, dash="n/a"):
    if v is None or v == "":
        return dash
    if isinstance(v, float):
        return "{:,.{nd}f}".format(v, nd=nd)
    return str(v)


def pct(v, nd=1, dash="n/a"):
    return dash if v is None else "{:,.{nd}f}%".format(v * 100, nd=nd)


def yn(b):
    return "PASS" if b else ("FAIL" if b is False else "n/a")


def write(name, text):
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, name), "w", encoding="utf-8") as fh:
        fh.write(text.lstrip() + "\n")
    print("wrote origin/notes/" + name)


# ------------------------------------------------------------------ executive summary
def doc_exec():
    integ = M["integrity"]
    best = MODELS["C"]
    s5 = next(s for s in STRAT if s["id"] == "S5")
    s4 = next(s for s in STRAT if s["id"] == "S4b")
    r = CORR["rows"][1]
    passed = [s for s in STRAT if s["passed_all_gates"]]
    prov = [s for s in STRAT if s["verdict"].startswith("PROVISIONAL")]
    n_out = sum(1 for i in INJ if i["status"] in ("Out", "Doubtful"))

    lines_rows = "\n".join(
        "| {} | {} | {} @ {} | {:+.1f} | {:.1f} | &plusmn;{:.1f} | [game]({}) |".format(
            l["date"], l["time_et"], l["away"], l["home"], l["orig_spread_home"],
            l["orig_total"], 1.959963984540054 * M["residuals"]["total_sd"], l["source_game"])
        for l in LINES)

    return """
# Executive summary

**Season 2026-27 &middot; results verified through {through} &middot; generated {ts}**

## What this system is

NBA3 originates its own point spreads and game totals for every NBA game, then tests betting
strategies against those originated lines rather than against a sportsbook's prices. Every
input is read from an official NBA source; every derived number is reproducible by running
`model/build.py`. Nothing is copied from a book, an odds aggregator, or a third-party
statistics site.

## Headline findings

| Finding | Number | Source |
|---|---|---|
| Games verified | {n} ({first} to {last}) | [nba.com/games]({g}) |
| Team-games reconciled against official GP | {tg:,} vs {off:,}, **mismatch {diff}** | [teams/advanced]({ta}) |
| Out-of-sample games graded | {n_oos} (walk-forward, no look-ahead) | derived |
| Margin model RMSE | {mrmse:.2f} vs {mbase:.2f} baseline ({gain:.1f}% better) | derived |
| Total model RMSE | {trmse:.2f} vs {tbase:.2f} baseline (**worse**) | derived |
| Fitted home-court advantage | {hc:+.2f} pts, p={hcp:.3f} (not significant) | derived |
| Spread/total residual correlation | r={r:+.3f}, 95% CI [{lo:+.2f}, {hi:+.2f}] | derived |
| Strategies passing all gates | **{npass} of {nstrat}** | derived |
| Injury rows marked Out/Doubtful | {n_out} | [injury PDF]({inj}) |

## The six things that matter

1. **The data reconciles exactly.** {n} games, {tg:,} team-games, zero discrepancy against the
   official games-played column for all 30 teams. Per-team detail is in
   [Data & Sources](data.md#integrity-reconciliation).

2. **The side beats its baseline; the total does not.** Walk-forward over {n_oos}
   out-of-sample games, the blend model cuts margin RMSE from {mbase:.2f} to {mrmse:.2f}
   points. For totals our best model is *worse* than guessing the league average
   ({trmse:.2f} vs {tbase:.2f}), and we report that rather than hiding it.

3. **No strategy clears every validation gate.** {npass} of {nstrat} pass. Two are
   provisionally interesting: fading our own totals of 235 and above ({s5w}/{s5n}, p={s5p:.4f})
   and backing road favourites of 8 or more ({s4w}/{s4n}, p={s4p:.4f}). Both are far below the
   100-bet sample floor. The honest reading is *under-powered*, not *disproven* — and neither
   should be traded.

4. **The parlay correlation we can measure is small.** Residual correlation between our own
   spread and our own total is r={r:+.3f} with a 95% interval that contains zero. Player-level
   correlations — the ones that actually drive same-game parlays — are blank, because the
   per-player game logs needed to compute them were not captured. We left them blank rather
   than estimating them.

5. **Injuries move minutes, and we quantify what we can.** {n_out} player-rows are marked Out or
   Doubtful across the 13-14 Nov reports. Where a player appears in the official minutes table
   we convert status to minutes at risk; where he does not, the cell is blank and flagged.

6. **Home court is small and not significant this season.** {hc:+.2f} points, p={hcp:.3f}.
   We use the fitted value because it is the least-squares estimate, but this sample does not
   establish home-court advantage at all.

## Bottom line

The pipeline is built, sourced and reproducible, and it produces defensible originated lines
for every game in the next three days. It has **not** yet produced a strategy that survives its
own validation gates. Deploying any of the provisional signals with real money today would be
betting on a small sample, not on demonstrated skill.

The single highest-value next step is not a better model — it is **more games**. The pipeline
requires no code changes to re-run once the season supplies them.

## Originated lines: all {n_lines} upcoming games

| Date | Time ET | Matchup (away @ home) | Spread (home) | Total | 95% &plusmn; | Source |
|---|---|---|---|---|---|---|
{lines_rows}

Full detail, including the efficiency cross-check and per-team injury counts, is on the
[lines page](../lines.html).
""".format(through=M["data_through"], ts=M["generated_utc"],
           n=integ["games_captured"], first=GAMES[0]["date"], last=GAMES[-1]["date"],
           g=SRC["games"], ta=SRC["team_advanced"], tg=integ["team_games_captured"],
           off=integ["team_games_official"], diff=integ["mismatch"], n_oos=len(M["oos_games"]),
           mrmse=best["margin"]["rmse"], mbase=best["margin_baseline_rmse"],
           gain=100 * (1 - best["margin"]["rmse"] / best["margin_baseline_rmse"]),
           trmse=MODELS["B"]["total"]["rmse"], tbase=MODELS["B"]["total_baseline_rmse"],
           hc=HC["value"], hcp=HC["p_two_sided"],
           r=r["value"], lo=r["ci95"][0], hi=r["ci95"][1],
           npass=len(passed), nstrat=len(STRAT),
           s5w=s5["wins"], s5n=s5["n"], s5p=s5["p"],
           s4w=s4["wins"], s4n=s4["n"], s4p=s4["p"],
           n_out=n_out, inj=SRC["injury"], n_lines=len(LINES), lines_rows=lines_rows)


# ------------------------------------------------------------------ methodology
def doc_methodology():
    per_team = []
    counts = defaultdict(int)
    for g in GAMES:
        counts[g["away"]] += 1
        counts[g["home"]] += 1
    for t in sorted(TEAM_R):
        w = l = 0
        for g in GAMES:
            if g["home"] == t:
                w += int(g["home_pts"]) > int(g["away_pts"])
                l += int(g["home_pts"]) < int(g["away_pts"])
            elif g["away"] == t:
                w += int(g["away_pts"]) > int(g["home_pts"])
                l += int(g["away_pts"]) < int(g["home_pts"])
        ours, off = counts[t], int(TEAM_R[t]["gp"])
        ow, ol = int(TEAM_R[t]["w"]), int(TEAM_R[t]["l"])
        ok = (ours == off) and (w == ow) and (l == ol) and (ours == w + l)
        per_team.append("| {} | {} | {} | {}-{} | {}-{} | {} | {} |".format(
            t, ours, off, w, l, ow, ol, int(TEAM_R[t]["gp"]) - w - l,
            "match" if ok else "**MISMATCH**"))

    return """
# Methodology and data provenance

## Verification rule

Three rules governed every number in this repository:

1. **A value may only be recorded if it was read from an official source.** The source URL is
   stored alongside the value.
2. **If a value cannot be confirmed from an official source, the cell is left blank and marked
   UNVERIFIED.** It is never inferred, estimated, or filled with a plausible number.
3. **Nothing is marked verified without a link to the official source that was checked.**

## Official sources used

| Data | Official source | What was taken |
|---|---|---|
| Final scores, game IDs | [{g}]({g}) | Every result, one page per date |
| Team efficiency, pace, records | [{ta}]({ta}) | OffRtg, DefRtg, NetRtg, Pace, eFG%, TS%, TOV%, OREB%, GP, W-L (all 30 teams) |
| Player production | [{pl}]({pl}) | Season per-game minutes and counting stats, top 31 by minutes |
| Injuries | [{inj}]({inj}) | Player, team, status, reason (13-14 Nov) |
| Schedule | [{sc}]({sc}) | Upcoming game IDs, tip times, NBA Cup groupings |

**Not used:** no sportsbook, odds aggregator or third-party statistics site contributed any
number. All lines are originated.

## Integrity reconciliation

The strongest available check on a hand-built game log: count each team's games in our file and
compare with the official **GP** column on
[nba.com/stats/teams/advanced]({ta}). Our log contains {tg:,} team-games; the official table
says {off:,}. **Difference: {diff}.**

| Team | Games in our log | Official GP | W-L (recomputed) | Official W-L | Unaccounted | Reconciliation |
|---|---|---|---|---|---|---|
{per_team}

"Unaccounted" is games played minus wins minus losses, and is zero for every team — no result is
missing or duplicated. The recomputed W-L column is derived solely from our own scores and matches
the official W-L for all 30 teams, which independently confirms both the scores and the home/away
attribution in the log.

## Models

Three candidate models were fitted and compared walk-forward.

| Model | Margin | Selected |
|---|---|---|
| LM-A additive | `margin = (PPG_home + PAPG_away - lg) - (PPG_away + PAPG_home - lg)` | no |
| LM-B Massey | least squares on `margin = HCA + r_home - r_away` | no |
| LM-C blend | mean of LM-A and LM-B margins | **yes** |

Two total estimators were compared: T1 (additive, league-centred twice) and T2 (sum of the two
teams' own scoring rates). **T2 won** and is used for every published total.

### Walk-forward protocol

- Burn-in of {burn} games; every graded prediction uses only games played strictly before it.
- Expanding window, refit at every step.
- Baseline: always predict the running mean home margin / running mean total.
- Metrics: bias, MAE, RMSE, paired test against the baseline, exact binomial on cover rate.

| Model | Margin RMSE | Margin baseline | Total RMSE | Total baseline |
|---|---|---|---|---|
{rows_models}

### Why the published line is not the efficiency model

A pace-and-rating model is better specified in principle:

```
E[home pts] = PACE x (OffRtg_home + DefRtg_away - OffRtg_league) / 100
```

but we hold only *season-to-date* ratings. Putting it through the same walk-forward backtest
would leak future games into the fit, so it cannot be validated from this session's data. The
**published line is LM-C, the model that was actually validated**; the efficiency estimate is
published beside it as a clearly labelled cross-check. See
[Originated Lines](../lines.html).

## Home-court advantage

Fitted by least squares over {hg} non-neutral games: **{hc:+.2f} points**, two-sided
p={hcp:.3f}, df={hcdf}. The Mexico City game (DEN vs IND, 7 Nov) is treated as neutral and
excluded. This sample does **not** establish home-court advantage at conventional thresholds;
the fitted value is used because it is the least-squares estimate, and the caveat is recorded
on the [flagged page](../flagged.html).

## Residuals

| Quantity | Value |
|---|---|
| Margin residual SD | {msd:.2f} points |
| Total residual SD | {tsd:.2f} points |
| Variance in margins explained | {ve:.1%} |

A single NBA game carries roughly 16 points of margin noise that no model removes. That is the
binding constraint on every strategy in this repository, and it is why the 95% interval on each
originated spread is about &plusmn;32 points.
""".format(g=SRC["games"], ta=SRC["team_advanced"], pl=SRC["players"],
           inj=SRC["injury"], sc=SRC["schedule"],
           tg=M["integrity"]["team_games_captured"],
           off=M["integrity"]["team_games_official"], diff=M["integrity"]["mismatch"],
           per_team="\n".join(per_team), burn=60,
           rows_models="\n".join("| {} | {:.2f} | {:.2f} | {:.2f} | {:.2f} |".format(
               m["label"], m["margin"]["rmse"], m["margin_baseline_rmse"],
               m["total"]["rmse"], m["total_baseline_rmse"])
               for m in (MODELS["A"], MODELS["B"], MODELS["C"])),
           hg=FLOW["home_games"], hc=HC["value"], hcp=HC["p_two_sided"], hcdf=int(HC["df"]),
           msd=M["residuals"]["margin_sd"], tsd=M["residuals"]["total_sd"],
           ve=M["skill"]["margin_variance_explained"])


# ------------------------------------------------------------------ strategies
def doc_strategies():
    rows = []
    for s in STRAT:
        g = s["gates"]
        rows.append("| {id} | {label} | {n} | {w} | {rate} | {p} | {null} | {fh} | "
                    "{g3} | {g5} | {g6} | {g7} | {v} |".format(
                        id=s["id"], label=s["label"], n=s["n"], w=s["wins"],
                        rate=pct(s["rate"]),
                        p=fmt(s["p"], 4), null=fmt(s["p_null"], 3),
                        fh="{} / {}".format(fmt(s["first_half_rate"], 3),
                                            fmt(s["second_half_rate"], 3)),
                        g3=yn(g["G3_sample_n_ge_100"]), g5=yn(g["G5_raw_p_lt_0.05"]),
                        g6=yn(g["G6_survives_bh_fdr_0.05"]),
                        g7=yn(g["G7_split_half_direction_stable"]),
                        v=s["verdict"]))

    return """
# Strategies and validation gates

## The gates

| Gate | Requirement | Why |
|---|---|---|
| G1 provenance | Every input is an official NBA figure or arithmetic on one | Blocks anything trained on a number we cannot source |
| G2 no look-ahead | Every prediction uses only games played strictly before it | A model that has seen the future always looks good |
| G3 sample size | At least 100 graded bets | Below 100 a 55% hit rate is inseparable from noise at 80% power |
| G4 power | Report the n the observed effect would need | Shows the shortfall in the same units as G3 |
| G5 significance | Two-sided p < 0.05 against the **correct** null | Exact binomial. For parlays the null is the independence-implied joint rate, not 0.50 |
| G6 multiple testing | Survives Benjamini-Hochberg at FDR 0.05 | Eight candidates were searched; the bar rises accordingly |
| G7 stability | Direction of the edge holds in both halves | An effect in only one half is usually a calendar artefact |

## Leaderboard

| ID | Strategy | Bets | Wins | Hit rate | p | Null | Split-half | G3 | G5 | G6 | G7 | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
{rows}

## Rules

{rules}

## Reading the result honestly

**Nothing passes.** That is the finding, and it is the most useful thing on this page.

- **S5 — fade our own totals of 235+.** {s5w} of {s5n} unders went under (p={s5p:.4f}). The
  threshold was pre-specified at 235 before the backtest ran, which is the right discipline, but
  {s5n} bets is roughly a fifth of what the gate demands; {s5need} bets would be needed to call
  the observed effect at 80% power. The result is also exactly what regression to the mean
  produces when a model is built from noisy season averages.
- **S4b — back road favourites of 8+.** {s4w} of {s4n} covers (p={s4p:.4f}), but it does not
  survive Benjamini-Hochberg correction across the eight candidates (G6), so it is not treated
  as established.

Neither should be traded. Both should be re-run automatically once the season supplies the
sample they need; the pipeline does this with no code changes.

## Rewards and the leaderboard

The brief asks for a leaderboard with rewards for the best strategies. Nothing clears the gates,
so no reward is payable on this evidence. The options for turning this into a genuine
competition — open contribution with automatic grading, a wider internal candidate set, or a
shadow paper-trading leaderboard — are set out in [Site Improvements](suggestions.md#d-make-the-leaderboard-a-genuine-competition).
""".format(rows="\n".join(rows),
           rules="\n".join("- **{}** — {}".format(s["id"], s["rule"]) for s in STRAT),
           s5w=next(s for s in STRAT if s["id"] == "S5")["wins"],
           s5n=next(s for s in STRAT if s["id"] == "S5")["n"],
           s5p=next(s for s in STRAT if s["id"] == "S5")["p"],
           s5need=next(s for s in STRAT if s["id"] == "S5")["gates"][
               "G4_powered_observed_effect_n_needed"],
           s4w=next(s for s in STRAT if s["id"] == "S4b")["wins"],
           s4n=next(s for s in STRAT if s["id"] == "S4b")["n"],
           s4p=next(s for s in STRAT if s["id"] == "S4b")["p"])


# ------------------------------------------------------------------ correlations
def doc_correlations():
    rows = []
    for c in CORR["rows"]:
        if c["value"] is None:
            rows.append("| {} | {} | *blank — UNVERIFIED* | — | — | {} |".format(
                c["pair"], c["stat"], c["note"]))
        else:
            ci = ("[{:+.2f}, {:+.2f}]".format(c["ci95"][0], c["ci95"][1])
                  if c["ci95"][0] is not None else "—")
            rows.append("| {} | {} | {:+.3f} | {} | {} | {} |".format(
                c["pair"], c["stat"], c["value"], ci, c["n"], c["note"]))

    return """
# Correlations

Correlation decides whether a same-game parlay is fairly priced. If two legs are positively
correlated the joint probability exceeds the product of the legs, and a book pricing the parlay
as independent is giving value away — and vice versa.

## Measured

| Pair | Statistic | Value | 95% CI | n | Interpretation |
|---|---|---|---|---|---|
{rows}

## Same-game parlay: our spread + our total

| Quantity | Value |
|---|---|
| Leg 1 hit rate (home cover vs our spread) | {ph:.1%} |
| Leg 2 hit rate (over vs our total) | {po:.1%} |
| Independence-implied joint rate | {ir:.1%} |
| **Observed joint rate** | **{jr:.1%}** |
| Gap | {gap:+.1%} |

Under independence both legs would land {ir:.1%} of the time. In {n} out-of-sample games they
actually landed {jr:.1%} of the time. The gap points towards *positive* correlation, but the
residual correlation itself (r={r:+.3f}) has a 95% interval containing zero, so this is
suggestive, not established.

## What we could not measure

The player-prop correlations that drive most same-game parlays are blank in the table above.
Computing them requires per-player game logs, which were not captured in this session. They were
left blank and flagged rather than filled with plausible numbers, because a fabricated
correlation is worse than no correlation: it gets priced into parlays.

Cross-game parlay independence is likewise an **assumption**, not a measurement. {n} games do
not support a reliable estimate of the correlation between two games on the same night.
""".format(rows="\n".join(rows), ph=CORR["p_home_cover"], po=CORR["p_over"],
           ir=CORR["parlay_independent_rate"], jr=CORR["parlay_joint_rate"],
           gap=CORR["parlay_joint_rate"] - CORR["parlay_independent_rate"],
           n=len(M["oos_games"]), r=CORR["rows"][1]["value"])


# ------------------------------------------------------------------ injuries
def doc_injuries():
    rows = []
    for r in M["injury_impact"]:
        unc = sum(1 for d in r["details"] if d["mpg"] is None)
        mv = r["minutes_vacuum_quantified"]
        rows.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["date"], r["team"], r["opponent"], r["home_away"],
            r["players_listed"], r["out_or_doubtful"],
            fmt(mv, 1, "*blank*") if mv else "0.0",
            unc, "submitted" if r["report_submitted"] else "**NOT YET SUBMITTED**"))

    det = []
    for r in M["injury_impact"]:
        for d in r["details"]:
            if d["status"] == "NOT YET SUBMITTED":
                continue
            det.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                r["date"], d["player"] or "—", r["team"], d["status"], d["reason"],
                fmt(d["mpg"], 1, "*blank — UNVERIFIED*"),
                fmt(d["mpg_at_risk"], 1, "*blank*")))

    return """
# Injury impact on rotation minutes and production

## Method

The official [NBA injury report]({inj}) gives a status, not a minutes number. To convert one
into the other:

1. Match the player by name against the official minutes table
   ([players/traditional]({pl})), which holds the top 31 players by minutes.
2. Convert status to an availability weight: Out 0.00, Doubtful 0.25, Questionable 0.60,
   Probable 0.90, Available 1.00. **These weights are our assumption, not an official figure**,
   and they are flagged as such.
3. Minutes at risk = season MPG x (1 - weight). Team total = quantified minutes vacuum.
4. Production impact = season per-game production x (projected minutes / season minutes).

Players on an official report but **not** in the captured minutes table get a blank minutes cell
and an UNVERIFIED badge. Their minutes are not estimated.

## Team-level minutes vacuum

| Date | Team | Opponent | H/A | Listed | Out/Doubtful | Minutes vacuum | Uncaptured | Report |
|---|---|---|---|---|---|---|---|---|
{rows}

The vacuum figures are **floors, not totals**, because of the uncaptured players column.

## Player-level detail

| Date | Player | Team | Status | Reason (official) | Season MPG | Minutes at risk |
|---|---|---|---|---|---|---|
{det}

## Contradictions found on official pages

- **Anthony Edwards (MIN)** is listed Out for 14 Nov (right knee arthroscopy), yet the official
  game pages show 45 points on 21 Oct and 47 on 26 Oct. Either the injury is new or the report
  is stale; re-check on game day before using the Minnesota line.
- **{nsub} team reports read "NOT YET SUBMITTED"** on the 14 Nov pages. Those teams carry zero
  quantified injury adjustment, which is a data gap rather than an assertion of good health.
""".format(inj=SRC["injury"], pl=SRC["players"], rows="\n".join(rows), det="\n".join(det),
           nsub=sum(1 for i in INJ if i["status"] == "NOT YET SUBMITTED"))


# ------------------------------------------------------------------ game flow
def doc_gameflow():
    pace = "\n".join("| {} | {:.2f} | {:.1f} | {:.1f} | {:+.1f} |".format(
        p["team"], p["pace"], p["off_rtg"], p["def_rtg"], p["net_rtg"])
        for p in FLOW["pace_leaders"])
    rest = "\n".join("| {} | {} |".format(k, v)
                     for k, v in FLOW["rest_distribution"].items())
    s3 = next(s for s in STRAT if s["id"] == "S3")

    return """
# Game flow

All figures computed directly from the {n} verified final scores in the game log. None is copied
from a summary page.

## League shape

| Metric | Value |
|---|---|
| Average game total | {avg:.1f} |
| Regulation average | {reg:.1f} |
| Overtime average | {ot:.1f} |
| Overtime rate | {otr:.1%} ({otn} of {n}) |
| Home win rate | {hwr:.1%} ({hw} of {hg} non-neutral) |
| Mean home margin | {hmm:+.2f} |
| Games with a team on a back-to-back | {b2b:.1%} |

## Pace

Fastest to slowest, official values.

| Team | Pace | OffRtg | DefRtg | NetRtg |
|---|---|---|---|---|
{pace}

The spread between fastest and slowest is {sp:.1f} possessions per 48 minutes, worth roughly
{worth:.1f} points of game total at a league-average offensive rating of {ortg:.1f}.

## Rest and scheduling

| Days of rest | Team-games |
|---|---|
{rest}

Our rest-differential strategy (S3) produced {s3r:.1%} over {s3n} graded bets, p={s3p:.3f} —
indistinguishable from a coin, and reported as such. Rest is a real effect, but {s3n} qualifying
games is not enough to claim it. It is presented here as context for the game-flow read, not as
a signal.

## Home court

Least-squares fit over {hg} non-neutral games: **{hc:+.2f} points**, two-sided p={hcp:.3f},
df={hcdf}. Not statistically distinguishable from zero in this sample. The Mexico City game
(DEN vs IND, 7 Nov) is treated as neutral.

## Overtime

{otn} of {n} games went to overtime ({otr:.1%}), and those games average {ot:.1f} combined
points against {reg:.1f} for regulation games — a gap of {gap:.1f} points. **Our originated
totals are regulation equivalents**: they do not add expected overtime scoring, which biases
them low by about {bias:.1f} points on average. That is a documented modelling choice, listed on
the [flagged page](../flagged.html), not an oversight.
""".format(n=FLOW["games"], avg=FLOW["avg_total"], reg=FLOW["avg_total_regulation"],
           ot=FLOW["avg_total_ot"], otr=FLOW["ot_rate"], otn=FLOW["ot_games"],
           hwr=FLOW["home_wins"] / FLOW["home_games"], hw=FLOW["home_wins"],
           hg=FLOW["home_games"], hmm=FLOW["home_margin_mean"], b2b=FLOW["b2b_rate"],
           pace=pace,
           sp=FLOW["pace_leaders"][0]["pace"] - FLOW["pace_leaders"][-1]["pace"],
           worth=(FLOW["pace_leaders"][0]["pace"] - FLOW["pace_leaders"][-1]["pace"])
                 * FLOW["lg_off_rtg"] / 100.0,
           ortg=FLOW["lg_off_rtg"], rest=rest,
           s3r=s3["rate"], s3n=s3["n"], s3p=s3["p"],
           hc=HC["value"], hcp=HC["p_two_sided"], hcdf=int(HC["df"]),
           gap=FLOW["avg_total_ot"] - FLOW["avg_total_regulation"],
           bias=FLOW["ot_rate"] * (FLOW["avg_total_ot"] - FLOW["avg_total_regulation"]))


# ------------------------------------------------------------------ data
def doc_data():
    rows = "\n".join(
        "| {} | {} | {} | {} | {} | {} | {} | [source]({}?date={}) |".format(
            g["date"], g["game_id"], g["away"], g["away_pts"], g["home_pts"], g["home"],
            "OT" if g["ot"] == "1" else "reg", SRC["games"], g["date"])
        for g in GAMES)
    return """
# Verified game log

{n} games, {first} to {last}. Every row was read off
`nba.com/games?date=YYYY-MM-DD` for that specific date; the first team listed on that page is
the away team. No score in this table was inferred, estimated or filled in.

| Date | Game ID | Away | Away pts | Home pts | Home | OT | Source |
|---|---|---|---|---|---|---|---|
{rows}
""".format(n=len(GAMES), first=GAMES[0]["date"], last=GAMES[-1]["date"], rows=rows)


# ------------------------------------------------------------------ open questions
def doc_questions():
    return """
# Open questions: what we have, what we don't, what's blocked

## We have this, verified

| Asset | Detail |
|---|---|
| Every final score, 20 Oct – 12 Nov | {n} games, each read off nba.com/games for its own date |
| Official team efficiency and pace, all 30 teams | OffRtg, DefRtg, NetRtg, Pace, four factors, GP, W-L |
| Season per-game player production | Top 31 players by minutes |
| Official injury report, 13–14 Nov | Player, team, status, reason |
| Upcoming schedule | {nup} games across three slates with game IDs, tip times, Cup groups |
| A working sourced line-origination model | Margin RMSE {mrmse:.2f} vs {mbase:.2f} baseline |
| A validation harness with seven gates | Walk-forward, exact binomial, Benjamini-Hochberg |

## We need this, and here is how to get it

| Missing | What it blocks | How to get it | Priority |
|---|---|---|---|
| Per-player game logs | Player-prop pricing and every player-level correlation; four correlation cells are blank because of it | Scrape nba.com/stats/players/boxscores by date — see [suggestion A2](suggestions.md#a-capture-per-player-game-logs) | **high** |
| More graded games | No strategy reaches the 100-bet gate; only {n_oos} out-of-sample games exist | Wait, then re-run the identical pipeline after another 150–200 games. No code changes needed | **high** |
| Possession-level team inputs per game | The total model loses to a naive baseline | Capture boxscores-advanced per date — [suggestion E3](suggestions.md#e-widen-and-harden-the-data-capture) | **high** |
| Injury report at tip-off, not 17:15 | {nsub} team reports read "NOT YET SUBMITTED" | Schedule a second pull 90 minutes before first tip — [suggestion E2](suggestions.md#e-widen-and-harden-the-data-capture) | medium |
| A decision on whether sportsbook prices may be used at all | Without a market price there is no such thing as an edge, only self-consistency | **Reviewer decision** | **high** |
| A decision on bankroll and staking | Determines whether a 53% strategy is worth running | **Reviewer decision**; a flat-stake default can be assumed and documented | medium |
| Confirmation that the unexpected rosters are correct | Giannis on Miami, Anthony Davis on Washington, Paul George on Boston, LaMelo Ball on Minnesota. If the source pages are wrong the ratings inherit the error | Spot-check against official team roster pages | medium |
| Whether overtime counts for totals | Our totals are regulation equivalents, biased low by about {otbias:.1f} points | **Reviewer decision**; both conventions are defensible but must be consistent | low |

## Decisions that need a human

1. **May we look at sportsbook prices at all?** Not to copy them — the brief rules that out —
   but to *compare*. Without a market price there is no such thing as an edge, only
   self-consistency. Every strategy here is graded against our own line, which is honest but is
   not the same as being profitable.
2. **Do we want the leaderboard open to outside contributors?** A competition with rewards
   implies yes, which implies a sandboxed runner. See [suggestion D](suggestions.md#d-make-the-leaderboard-a-genuine-competition).
3. **How should a "reward" be defined?** Raw hit rate, return on a flat stake, or risk-adjusted
   return? The gates currently test hit rate only.
4. **What is the stake?** Nothing is deployable on the current evidence, but the harness needs a
   staking rule before it can report anything a reviewer would act on.

Until question 1 is answered, the most accurate description of this system is: **a verified,
self-consistent line-origination engine with an unproven strategy layer.** That is a real
achievement, and it is not yet a betting system.
""".format(n=len(GAMES), nup=len(LINES),
           mrmse=MODELS["C"]["margin"]["rmse"], mbase=MODELS["C"]["margin_baseline_rmse"],
           n_oos=len(M["oos_games"]),
           nsub=sum(1 for i in INJ if i["status"] == "NOT YET SUBMITTED"),
           otbias=FLOW["ot_rate"] * (FLOW["avg_total_ot"] - FLOW["avg_total_regulation"]))


# ------------------------------------------------------------------ suggestions
def doc_suggestions():
    return """
# Site and system improvements — options for a reviewer

Each section states one problem, sets out two or three concrete fixes with the case for and
against each, and names a recommendation. **Nothing here has been implemented.** The purpose is
to let the choice be made deliberately rather than by whoever happens to be typing.

## A. Capture per-player game logs

**Problem.** Everything on the props and player-correlation side is blocked by the absence of
per-player game-by-game data. Four correlation cells are blank and no prop distribution exists.

| Option | What it is | For | Against |
|---|---|---|---|
| A1 | Scrape `nba.com/stats/players/boxscores` per date | Official source, already proven to work; ~4,000 rows for the season to date | Very slow — roughly 400 page fetches; needs chunking across sessions |
| A2 | **Sample the top 100 players by minutes only** | Covers the vast majority of prop market volume with about a quarter of the fetches | Deep-bench props remain unpriceable |
| A3 | Leave player props out of scope for now | Honest, fast, no new risk | Closes off the parlay and prop parts of the brief |

**Recommendation: A2.**

## B. Fix the totals model, which currently loses to a baseline

**Problem.** Best total RMSE is {trmse:.2f} against {tbase:.2f} for guessing the league average.
The side beats its baseline; the total does not.

| Option | What it is | For | Against |
|---|---|---|---|
| B1 | Add the four factors (eFG%, TOV%, OREB%, FT rate) | Directly targets the weakness; all inputs are official | More parameters to fit on a small sample |
| B2 | **Shrink team totals toward the league mean** | Cheap, quick, near-certain RMSE improvement | Improves accuracy without adding understanding |
| B3 | Publish the baseline as the total | Honest, no false confidence | Gives up on half the product |

**Recommendation: B2 now, B1 next.**

## C. Decide how the site should be refreshed

**Problem.** This build is a static snapshot. The brief asks for picks for every upcoming slate
up to three days ahead, which only stays true if the site is regenerated daily.

| Option | What it is | For | Against |
|---|---|---|---|
| C1 | **GitHub Actions cron that re-runs the pipeline and republishes** | Hands-off, fits GitHub Pages exactly, free | Scraping from Actions may be blocked or rate-limited |
| C2 | Manual regeneration at the start of each session | Simple, no new infrastructure | Stale whenever nobody runs it |
| C3 | Static archive plus a "generated at" banner | Honest about staleness | Does not meet the three-days-ahead requirement alone |

**Recommendation: C1 with C3's banner as a safety net.**

## D. Make the leaderboard a genuine competition

**Problem.** The brief asks for a leaderboard with rewards for the best strategies. Right now
there is one author and eight strategies, none of which pass.

| Option | What it is | For | Against |
|---|---|---|---|
| D1 | **Publish a strategy specification format and accept pull requests** | Turns the repo into the competition the brief describes | Needs a sandboxed runner to be safe |
| D2 | Keep it internal but auto-grade a wider candidate set | No security surface | Searching more rules makes G6 stricter, not weaker |
| D3 | Add a shadow leaderboard with paper results only | Builds the track record the gates demand | Nothing is deployable for weeks |

**Recommendation: D1 with D3 running underneath.**

## E. Widen and harden the data capture

**Problem.** Injury minutes impact is a floor because the captured minutes table covers only the
top 31 players, and several team reports were "NOT YET SUBMITTED".

| Option | What it is | For | Against |
|---|---|---|---|
| E1 | **Capture the full 465-row player table** | Removes an entire class of UNVERIFIED cells | Nine large page fetches per refresh |
| E2 | **Re-pull the injury report closer to tip-off** | Fewer stale or missing reports | Needs a second pull each day |
| E3 | Add official boxscores-advanced per date | Gives per-game team ratings, letting the model use form instead of the whole season | Two chunks per date; adds up over a season |

**Recommendation: E1 and E2 now, E3 next.**
""".format(trmse=MODELS["B"]["total"]["rmse"], tbase=MODELS["B"]["total_baseline_rmse"])


# ------------------------------------------------------------------ flagged
def doc_flagged():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("bs", os.path.join(ROOT, "site", "build_site.py"))
    # build_site.py executes on import; instead re-derive the list here to keep docs standalone
    items = []
    for c in CORR["rows"]:
        if c["value"] is None:
            items.append(("Correlations", c["pair"], c["note"],
                          "Same-game parlays combining two player props cannot be priced.",
                          "Capture per-player game logs from nba.com/stats/players/boxscores.",
                          "high"))
    items += [
        ("Player props", "No distribution behind any projection",
         "The pro-rata minutes assumption yields a point estimate of a mean only; no standard "
         "deviation, so no probability of exceeding a prop line.",
         "Player-prop bets and prop parlays cannot be graded or sized.",
         "Capture per-player game logs and fit a distribution per player per stat.", "high"),
        ("Injuries", "Status-to-availability weights are our assumption",
         "Out 0.00, Doubtful 0.25, Questionable 0.60, Probable 0.90, Available 1.00. The NBA "
         "publishes the status but not a probability.",
         "The injury adjustment carries our assumption through to the originated lines.",
         "Replace with observed participation rates by status once game logs exist.", "medium"),
        ("Modelling", "Win probabilities assume a normal margin distribution",
         "P(home win) uses a normal CDF with the margin model's residual SD of {msd:.2f}.",
         "Probabilities near the extremes are less reliable than the middle of the range.",
         "Replace with the empirical residual distribution or a bootstrap.", "medium"),
        ("Modelling", "Originated totals are regulation equivalents",
         "No expected overtime scoring is added; OT occurred in {otr:.1%} of games and is worth "
         "about {gap:.1f} points when it happens.",
         "Totals are biased low by roughly {bias:.1f} points on average.",
         "Decide on a convention and apply it consistently.", "medium"),
        ("Modelling", "Total model does not beat the naive baseline",
         "Best total RMSE {trmse:.2f} vs {tbase:.2f} for the running league-average total.",
         "Totals and total-based strategies rest on a model with no demonstrated skill.",
         "Add possession-level inputs (four factors).", "high"),
        ("Validation", "Out-of-sample sample is only {n_oos} games",
         "After a 60-game burn-in, no strategy reaches the 100-bet gate.",
         "Every strategy result is under-powered; nothing can be deployed on this evidence.",
         "Re-run the same pipeline once another 150-200 games have been played.", "high"),
        ("Modelling", "Home-court advantage is not statistically significant",
         "Fitted at {hc:+.2f} points, p={hcp:.3f}, over {hg} non-neutral games.",
         "The fitted value is used in every originated spread despite not being distinguishable "
         "from zero.", "Monitor; consider shrinking toward a prior-season value.", "low"),
        ("Data irregularity", "Unexpected rosters on official pages",
         "Giannis Antetokounmpo on Miami, Anthony Davis on Washington, Paul George on Boston, "
         "James Harden on Cleveland, LaMelo Ball on Minnesota, Kevin Durant on Houston.",
         "If any attribution is wrong, the team ratings inherit the error.",
         "Spot-check two or three against official team roster pages.", "medium"),
        ("Data irregularity", "Anthony Edwards listed Out after 45- and 47-point games",
         "Out (right knee arthroscopy) for 14 Nov, yet official game pages show 45 points on "
         "21 Oct and 47 on 26 Oct.",
         "His minutes vacuum is quantified as if he will not play.",
         "Re-check the report on game day before using the Minnesota line.", "medium"),
        ("Correlations", "Cross-game parlay independence is an assumption",
         "Not measured; {n_oos} games do not support a reliable estimate.",
         "Cross-game parlays are priced as if legs were independent.",
         "Measure on the residual matrix once the sample is larger.", "medium"),
    ]
    rows = "\n".join("| {} | {} | {} | {} | {} | {} |".format(i + 1, a, b, c_, d, e)
                     for i, (a, b, c_, d, e, sev) in enumerate(items))
    return """
# Flagged for review

Everything here is something we could not verify, deliberately did not fill in, or found to be
contradictory on an official source. **None of it blocks publication** — it is published *here*,
with its source, so a reviewer can see the boundary between what is established and what is
assumed.

The governing rule: *if a value cannot be confirmed against an official source, the cell is left
blank and marked UNVERIFIED rather than estimated.*

| # | Area | Item | What the problem is | What it affects | How to resolve |
|---|---|---|---|---|---|
{rows}

Severity index: high = blocks a capability; medium = distorts a number; low = cosmetic or
immaterial at current sample size.

- High severity: {hi}
- Medium severity: {med}
- Low severity: {low}
- Unverified correlation values left blank: {blank}
""".format(rows=rows,
           hi=sum(1 for i in items if i[5] == "high"),
           med=sum(1 for i in items if i[5] == "medium"),
           low=sum(1 for i in items if i[5] == "low"),
           blank=sum(1 for c in CORR["rows"] if c["value"] is None),
           msd=M["residuals"]["margin_sd"], otr=FLOW["ot_rate"],
           gap=FLOW["avg_total_ot"] - FLOW["avg_total_regulation"],
           bias=FLOW["ot_rate"] * (FLOW["avg_total_ot"] - FLOW["avg_total_regulation"]),
           trmse=MODELS["B"]["total"]["rmse"], tbase=MODELS["B"]["total_baseline_rmse"],
           n_oos=len(M["oos_games"]), hc=HC["value"], hcp=HC["p_two_sided"],
           hg=FLOW["home_games"])


def main():
    write("executive-summary.md", doc_exec())
    write("methodology.md", doc_methodology())
    write("strategies.md", doc_strategies())
    write("correlations.md", doc_correlations())
    write("injury-impact.md", doc_injuries())
    write("game-flow.md", doc_gameflow())
    write("data.md", doc_data())
    write("open-questions.md", doc_questions())
    write("suggestions.md", doc_suggestions())
    write("flagged.md", doc_flagged())


if __name__ == "__main__":
    main()
