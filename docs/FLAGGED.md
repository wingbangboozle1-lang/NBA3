# Flagged for Review (T11)

**Policy:** *If a value cannot be confirmed from an official source, it is left blank and flagged. Nothing is inferred. Nothing is silently corrected.* Machine-readable with evidence: `data/flagged.json` · Site: [flagged.html](flagged.html)

Legend: 🔴 high · 🟠 medium · 🟢 low · ✅ = resolved-by-workaround (still recorded).

## Repository irregularities

| ID | Finding | Sev | Status |
|---|---|---|---|
| fl-01 | Base commit contained **only a 6-byte `README.md`** (`# NBA3`) — no LICENSE, .gitignore, CI, docs or code. All content is new on this branch. | 🔴 | 🟡 OPEN — LICENSE/CI decisions = Q-07/Q-08 |
| fl-02 | Commit identities differ: initial commit personal e-mail +0900, later commits GitHub noreply +0000. Sequencing correct, display confusing. | 🟢 | 🟡 OPEN (informational) |

## Source & data irregularities

| ID | Finding | Sev | Status |
|---|---|---|---|
| fl-03 | `nba.com/standings` renders **no team rows** to non-JS fetch (tiebreak text only) | 🟠 | ✅ records harvested from game pages + league stats table (both official, cross-checked) |
| fl-04 | Official schedule PDF uses **`R` flag** on games 27/40/50 that the PDF's own legend does **not define** (legend: C/A/B/D/E only). Meaning NOT inferred. | 🟠 | 🟡 OPEN (Q-05); row 40 (GSW@SAS) carries `flag_note` |
| fl-05 | Documented injury cadence (1:30/5:30/8:30 p.m. ET, official.nba.com) **≠ observed stamps today** (01:00, 01:15, 04:15, 05:00 PM ET) | 🟠 | 🟡 OPEN — G4 uses observed stamps |
| fl-06 | **11/14: 7 teams `NOT YET SUBMITTED`; 11/15–16: reports not published** — affected pick rows blank + PROVISIONAL, never scored | 🔴 | 🟡 OPEN (Q-01, SG-04) |
| fl-07 | PDF page-break left **blank team cell** on `Williams, Brandon` row; attributed to GSW via roster cross-check (GSW lists him; SAS roster doesn't) — recorded as attribution, not fact | 🟢 | 🟡 OPEN |
| fl-08 | **MIL OPPG 121.3 direct vs 121.4 derived** (PTS−margin) — 0.1 rounding between two official renderings | 🟢 | 🟡 OPEN — direct value wins |
| fl-09 | **DET@MIA TV**: PDF blank vs **NBA TV** on live page | 🟢 | 🟡 OPEN — live page used for display |
| fl-10 | Schedule PDF rows 215+ **lose the `at` separator** (merged cells); rows 246–253 show no `at` at all | 🟠 | ✅ all 31 slate rows re-verified via preview slugs + venues |
| fl-11 | **`/player/1629027/shai-gilgeous-alexander` renders Trae Young (WAS)** — NBA URL slug/ID mismatch; canonical URL corrected to `/player/1629027/trae-young` | 🟢 | ✅ canonical recorded |
| fl-12 | **Live scoreboard JSON → HTTP 500** (twice); **stats.nba.com standings API blocked** | 🟠 | ✅ do-not-retry; HTML/PDF alternates used |
| fl-13 | **13 OUT players have no collected season PPG** (CHI/MIA/DAL/BKN/DET/ATL/HOU/POR roster gaps) → production-at-risk totals labelled **INCOMPLETE**, never estimated | 🟠 | 🟡 OPEN (Q-02, SG-02) |
| fl-14 | `official.nba.com/injury-report/` → **404**; real path `ak-static.cms.nba.com/referee/injury/…` (pattern confirmed ×4 today) | 🟢 | ✅ corrected in registry |
| fl-15 | Schedule PDF is an **August snapshot, SUBJECT TO CHANGE** | 🟢 | ✅ every slate row re-verified against live page today |
| fl-16 | **Market odds client-rendered only** — no odds captured → CLV gates explicitly **BLOCKED** (not faked) | 🔴 | 🟡 OPEN (Q-04) |

## Model assumptions flagged (not data errors — declared parameters)

| ID | Assumption | Where it shows up | Status |
|---|---|---|---|
| hca-01 | **HCA = 2.5 pts** — no official NBA-published HCA exists; only 5 teams' location splits captured and their tiny sample shows no stable signal | every `our_fair_spread` (all 31 rows tagged `assumptions: [hca-01]`) | 🟡 OPEN (Q-03, SG-03) |
| w-01 | Rest weights (B2B −1.5; 2d +0.5…) and injury weights (0.35, cap 10, rotation gate 0.6) | `picks.json` parameters block; pre-settled revisions rev-A/rev-B logged | 🟡 OPEN — pre-registered |
| w-01× | Cross-game parlay **ρ = 0 declared, not measured** | `correlations.json.cross_game_parlay` | 🟡 OPEN |
| flag-ppg-missing | per-row null PPG with reason | `injuries.json`, `players.json` | 🟡 tied to fl-13 |
| flag-injury-future | rows for 11/15–16: report `NOT YET PUBLISHED` | `injuries.json` (13 games) | 🟡 tied to fl-06 |
| flag-injury-partial | 11/14 rows with `NOT YET SUBMITTED` teams | `injuries.json` (7 teams) | 🟡 tied to fl-06 |

## Verification of this register

`scripts/verify.py` enforces the mechanical part: every null in `data/*.json` must sit next to a flag/note/status explanation (warnings otherwise), every URL must be on the NBA-official allowlist, every pick row must carry six source links, released picks must have a submitted injury report, and every site table row must carry an inline source link.
