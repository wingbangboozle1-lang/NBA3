# Injury Impact & Game Flow Analysis (T07)

**Author:** session d01ae7e2 · **Date:** 2026-11-13 · **Primary source:** [Injury Report 11/13/26 05:00 PM](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf) · Data: `d01ae7e2/data/injuries.json` · Site pages: [Injury Impact](injury-impact.html), [Game Flow](game-flow.html)

## Method (no minutes are invented)

1. **Status** comes verbatim from the official report PDF (Out / Doubtful / Questionable / Probable / Available / NOT YET SUBMITTED / NOT YET PUBLISHED). No status is softened or hardened.
2. **Production at risk** = Σ season **PPG** of players with status **Out** who meet the *rotation gate* (GP ≥ 60% of the team's games, from official roster pages). The gate exists because subtracting a player who has already missed most of the season double-counts his absence — his missing production is already inside the team's official baseline (rev-B rationale).
3. **Players with GP = 0** (season hasn't started for them — e.g. Butler, Porzingis, Beal, Ingram, Nurkić) contribute **0** and are shown as such: their absence is a *known state*, not a new production loss.
4. **Players whose PPG was not collected** contribute nothing and the team's total is labelled **INCOMPLETE** (fl-13). Never estimated.
5. **Minutes are not modelled** — official per-game MPG logs were not collected (gamelog endpoint dead); the analysis stays at verified points-production and status, not projected minutes. Where minutes reasoning appears it is qualitative, marked as such.

## Key findings — 11/13 slate (full reports)

| Game | Team | Out production at risk (verified PPG, rotation gate) | Headline |
|---|---|---|---|
| NYK@IND | IND | **Haliburton 21.8** (GP 4 — *fails* rotation gate → excluded from Σ, flagged) | IND's 4-8 baseline already includes his absence; no extra deduction (rot-gate) |
| NYK@IND | NYK | none listed | Fully healthy designation-free report |
| MIL@ORL | ORL | **Banchero 24.5** (GP 2/11 — fails 60% gate → excluded, flagged) + Penda PPG missing | ORL line carries no Banchero deduction; honest but worth reviewer attention |
| CLE@MIA | CLE | **Mobley 16.9 + Merrill 7.7 = 24.6** (both pass gate) | Largest verified single-game deduction of the night |
| UTA@HOU | UTA | **Markkanen 18.0** (GP 8/12 ✓); JJJ 16.3 (GP 4/12 ✗ gate) | UTA production hole concentrated in Markkanen |
| GSW@SAS | GSW | **Curry 27.8 + B.Williams 10.4 = 38.2** (both GP 10 ✓) | Biggest verified loss of the night — drives SAS −14.2 fair line |
| MEM@NOP | NOP | **Murphy 15.6 + Murray 13.4 = 29.0** (both GP 9 ✓); Missi/McGowens/Watford fail gate | NOP defense+scoring hit; MEM side only Edey 7.6 |
| MEM@NOP | MEM | **Edey 7.6** (+ Pippen 6.4 fails gate) | |
| OKC@LAC | OKC | **none pass the gate** (Holmgren/J.Williams GP 3/12, Wallace 3/12) | OKC's 8-4 record already without them — no deduction (this is what rev-B fixed) |
| POR@SAC | POR | **Morant 15.8** — but GP not captured → *cannot apply rotation gate* → flagged missing | Model treats as incomplete, not zero (flagged, not guessed) |
| ATL@CHI, MIA rows, DAL/BKN/DET 11/14 | various | PPG not collected (CHI/MIA/DAL/BKN/DET rosters not fetched) | Totals INCOMPLETE → fl-13, SG-02 |

**Empty submissions:** MIL and NYK have **zero rows** in the official report for their game — recorded as "no reportable designations", never reinterpreted as "healthy" (we don't infer; we report the report's content).

**Status change evidence (why freshness gate G4 matters):** Dejounte Murray moved **Doubtful (01:15 PM) → Out (04:15/05:00 PM)**. A pick generated at 01:15 using that report would mis-price NOP. G4 (<6 h old) plus re-generation on new stamps addresses this; SG-04 automates it.

## Availability watch (not deductions — monitor only)

- **Giannis Antetokounmpo — Available** (right wrist sprain, GP 11, 27.7 PPG) for MIA vs CLE.
- **Klay Thompson — Probable** (ankle); **Pelle Larsson — Doubtful** (illness) — MIA.
- **De'Aaron Fox — Questionable** (hip, 14.2 PPG) and **Devin Vassell — Questionable** (11.9) for SAS vs GSW — if either is later ruled Out, GSW@SAS line must regenerate.
- **Norman Powell — Questionable** (CHI, PPG uncollected); Jalen Suggs / Tristan da Silva / Jamal Cain Q (ORL); Aaron Nesmith Q + T.J. McConnell Probable (IND); Bennedict Mathurin Q (NOP); Max Christie Q / Morez Johnson Jr Probable (DAL 11/14).

## 11/14–16 pipeline states

| Slate | Official report state | Model state |
|---|---|---|
| 11/14 (5 games) | DAL, BKN, DET submitted; **DEN, NOP, CLE, MEM, CHI, MIN, MIA NOT YET SUBMITTED** | `PROVISIONAL_PARTIAL_INJURY` — 5 rows, injury input blank |
| 11/15 (9 games) | No rows exist in any report | `PROVISIONAL_INJURY_PENDING` — 9 rows |
| 11/16 (8 games) | No rows exist in any report | `PROVISIONAL_INJURY_PENDING` — 8 rows |

(11/15–16 totals above include the partially-covered games counted once; full table on the [Injury Impact](injury-impact.html) page.)

## Game-flow analysis inputs (official only)

- **Back-to-backs (from schedule PDF):** 11/14 — NOP, CLE, MIA, MEM home + CHI away (5 teams!); 11/15 — DAL away; 11/16 — BOS, WAS home + PHI, HOU, PHX away. Full rest matrix on the [Game Flow](game-flow.html) page. S4 strategy pre-registered to exploit exactly this factor.
- **Rest edges ≥ 2 days:** ATL arrives in Chicago with 3 days off (last game 11/9) vs CHI on 1; LAL 3 days off vs PHX 2; MIL/CLE/MIA all on short turns — all computed from official previous-game dates, no schedule inference.
- **Worked example of official flow data:** CLE 115–107 NYK (11/11): quarters 33-23 / 26-30 / 23-23 / 33-31, 3 lead changes, 6 times tied, PITP 42–46, fast-break 14–10 — demonstrates the flow metrics available from official game pages; used as a methodology example only, not as a pick input (the game is completed).
- **Cup stakes:** all 9 × 11/13 games are Emirates NBA Cup group play (official labels: East A/B/C, West A/B/C). The Player Participation Policy explicitly requires star availability for In-Season Tournament games ([source](https://ak-static.cms.nba.com/wp-content/uploads/sites/46/2023/09/NBA-Player-Participation-Policy.pdf)) — an upward availability pressure on Cup nights that partially offsets the injury list (e.g. Giannis *Available* rather than rested).

## What this analysis deliberately does not do

- No projected minute splits (would require inference without official MPG logs).
- No "player X returns → +Y points" claims beyond the rotation-gated PPG sums.
- No marking of teams as healthy from absence of report rows.
