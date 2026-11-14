# Strategies & Validation Gates (T04)

**Author:** session d01ae7e2 · **Date:** 2026-11-13 · **Data:** official NBA sources only (registry: `data/sources.json`) · Machine-readable: `data/strategies.json`, `data/correlations.json`

## Design principles

1. **Pre-registration.** Every strategy, parameter, gate and reward rule is written down *before* any pick settles. Parameter changes are only legal pre-settlement and must be appended to the revision log (two revisions already recorded — see below). Post-settlement edits are forbidden.
2. **Blank + flagged, never inferred.** A strategy that cannot compute its input for a game releases a `PROVISIONAL` row (or passes). It never guesses.
3. **Luck removal, not luck denial.** We cannot make variance disappear; we (a) score only after settlement, (b) require sample-size + confidence-interval gates before any skill claim, (c) measure correlations instead of assuming independence, (d) keep flat unit stakes, (e) pre-register so no survivorship editing is possible.
4. **Selective betting.** A strategy only releases a pick when its edge gate passes; everything else is a recorded `NO BET`. Selectivity is itself the skill surface being measured.

---

## S1 — Edge Single (moneyline/spread)

**Type:** single bet, one game, one unit flat.
**Model (v1):**

```
net(team)        = PPG − OPPG                        # both official columns
fair_margin_home = 0.5*(net_home − net_away) + HCA
                 + rest_adj(home) − rest_adj(away)
                 + clip(INJ_WEIGHT*(out_ppg_away − out_ppg_home), ±INJ_CAP)
fair_total       = 0.5*(PPG_home + OPPG_away + PPG_away + OPPG_home)
                 − clip(INJ_WEIGHT*out_ppg_home, 0, INJ_CAP)
                 − clip(INJ_WEIGHT*out_ppg_away, 0, INJ_CAP)
P(home)          = Φ(fair_margin / σ),  σ = 11.3
```

`out_ppg` = Σ season PPG of players whose official status is **Out** *and* who meet the **rotation gate** (GP ≥ 60% of team GP). Players with GP = 0 contribute 0 (their absence is already in the season baseline); players whose PPG was not collected make the input explicitly *incomplete* (row flagged), never estimated.

**Parameters (all assumptions, flagged `hca-01` / `w-01`):** HCA = 2.5 pts · B2B penalty = −1.5 pts · rest bonus {2d: +0.5, 3d: +0.5, 4d+: +0.75} · INJ_WEIGHT = 0.35 · INJ_CAP = 10 pts · edge threshold = 3.0 pts · confidence cutoff = 0.60.

**Release gate (all must hold):**

| Gate | Rule |
|---|---|
| G1 sample | ≥ 30 settled picks before any skill claim |
| G2 win-rate CI | Wilson 90% CI must exclude break-even before "skill-positive" label |
| G3 edge persistence | mean \|our line − baseline\| stays ≥ 2.0 pts (model not collapsing) |
| G4 freshness | injury report < 6 h old for game-day rows; otherwise PROVISIONAL |
| G5 completeness | every pick row carries 6 source links (schedule, PDF, both team stats, injury, preview) |

**Luck controls:** flat 1-unit stakes · settled-only scoring · no-cherry-pick ledger (every eligible game gets a released-or-pass row) · CI required for claims.

**Revision log (both pre-settlement, 0 settled picks):**
- *rev-A*: INJ_WEIGHT 0.6 → 0.35 and INJ_CAP=10 added after a sanity check produced implausible margins (SAS −18.7 vs GSW).
- *rev-B*: rotation gate added (OUT players only count when GP ≥ 60% of team GP) after detecting double-counting — e.g. OKC missing Holmgren/J.Williams (GP 3/12 each) is already reflected in OKC's 8-4 baseline; counting them again flipped LAC into favor.

---

## S2 — Correlated Double (2-leg parlay)

Pairs the two strongest same-day S1 releases (different games). Legs must each pass S1's release gate.

**Joint probability** is computed with the measured/declared correlation, never naive independence:

```
p(A∩B) = pA + pB − pA·pB − ρ·min(pA,pB)·(1−max(pA,pB))     # bounded to [max(0,pA+pB−1), min(pA,pB)]
```

Cross-game legs use **ρ = 0 by design** (separate contests) — this is a *declared assumption*, recorded in `data/correlations.json`, not a measurement. Same-game legs would require a measured ρ; with no same-game multi-bet released in v1, the capability is documented but unused.

**Gates:** G1 ≥ 20 settled parlays · G2 ρ must exist in `correlations.json` with n ≥ 5 or the parlay is **rejected** · G3 joint-probability method enforced (naive independence prohibited).

**Luck controls:** rejection ledger kept (rejected combos are recorded, not hidden) · flat unit · settled-only scoring.

---

## S3 — Prop Stack (player points combo)

Two **same-team** players' points props stacked (e.g. Brunson 26.0 + Towns 20.9 season-PPG lines).

**Gates:**
- G1 ≥ 15 settled stacks before ranking.
- G2 availability: both players must be `not listed / Probable / Available` in the latest official injury report. `Questionable` → flagged for manual review; `Out`/`Doubtful` → **auto-reject**.
- G3 correlation: teammate ρ must be computed from official **Last 5 Games** tables (Pearson, n ≥ 5); otherwise both legs released only as singles.

**Measured today:** Brunson–Towns teammate PTS ρ = **+0.569** (n = 5, official player pages) → stack released with a `noisy (n=5)` badge — see Q-12 on whether n=5 satisfies the reviewer.

**Luck controls:** availability gate (removes the most common prop-bust cause: injury news) · correlation-estimated joint probability · flat units · settled-only scoring.

---

## S4 — Rest/Fatigue Favourite

Subset of S1 released only when the rest differential is ≥ 2 days (our side rested ≥ 2, opponent on 0–1 including back-to-backs). Uses only schedule-PDF-derived rest values.

**Gates:** G1 ≥ 25 settled picks (larger N because it is a subset) · G2 must beat parent S1's settled ROI before promotion to rank 1 · G3 schedule source = official PDF only.

**Pre-registration:** hypothesis registered *before* any results exist — the 11/14 slate alone contains five home back-to-backs (NOP, CLE, MIA, MEM + CHI away), giving the subset early sample.

---

## Measured correlation values (`data/correlations.json`)

| Pair | r | n | Basis |
|---|---|---|---|
| win% vs margin_pg | **+0.935** | 30 | Official league table — margin is the skill signal |
| win% vs PTS | +0.641 | 30 | Scoring alone explains less than margin |
| win% vs OPPG | **−0.750** | 30 | Defense matters more than scoring alone |
| margin_pg vs OPPG | −0.801 | 30 | Consistency check |
| Brunson–Towns teammate PTS | **+0.569** | 5 | Official Last-5 tables (noisy — Q-12) |
| Cross-game parlay legs | 0.0 (declared) | — | Independence by design; assumption `w-01` |
| Market-odds CLV | **BLOCKED** | — | No authorized odds source (Q-04, fl-16) |

**Why these matter for strategy design:** the league table says two-way differential (net rating) is the right S1 strength input — r = 0.94 with win% vs 0.64 for scoring alone. The teammate ρ = 0.569 says same-game *same-team* legs are meaningfully dependent — treating them as independent (as a naive parlay engine would) would misprice joint probability; S3 therefore always estimates joint probability with ρ.

---

## Leaderboard & rewards (pre-registered)

See `data/strategies.json → leaderboard` and the [Leaderboard page](leaderboard.html). Summary:

- Ranking metric: settled-pick ROI **with Wilson 90% CI shown alongside**; a strategy whose CI contains break-even is displayed as *"not yet distinguished from luck"* — no rank claims without passing that bar.
- Minimum settled gates: S1=30, S2=20, S3=15, S4=25 **and** CI excludes break-even.
- Rewards (paper book, 100 units start): (1) **Weekly crown** = best settled ROI among gate-passers; (2) **Gate Champion** badge = first strategy through all gates; (3) **Unit allocation** = top-ranked strategy gets 2× unit sizing next week (capped at 2% of book), others 1×. Book drops a strategy below 50 units (record retained). Weekly freeze — no retroactive edits. PROVISIONAL rows never scored.

---

## Known limitations (honest list)

1. HCA, rest and injury weights are **assumptions** pending calibration (Q-03, SG-03).
2. CLV gate cannot run without an authorized market-odds source (Q-04) — the strongest luck-removal tool is unavailable; CI-on-settled-picks is the fallback and needs more time to be conclusive.
3. Correlation sample n=5 (Q-12).
4. Injury production-at-risk totals are lower bounds where rosters were not fully collected (fl-13, Q-02).
5. No completed-game grading has run yet (Q-11): everything visible is `PAPER` / `PROVISIONAL`.
