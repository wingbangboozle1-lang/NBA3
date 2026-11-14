# Executive Summary (T08)

**Project:** NBA line-origination & betting-strategy research · **Session:** d01ae7e2 · **Data cut:** 2026-11-13 18:28 ET · **Repo:** `wingbangboozle1-lang/NBA3`, branch `arena/d01ae7e2-nba3`

## What was delivered

| # | Deliverable | State |
|---|---|---|
| T01 | **Repo review, line-by-line** — [REPO_REVIEW.md](REPO_REVIEW.md) / [site page](repo-review.html): base repo was a single 6-byte README; irregularities (no LICENSE/CI/gitignore, dual author identities) documented, fixes routed to reviewer decisions | ✅ |
| T03 | **Official-source research** — 16 sources fetched + 5 dead ends recorded ([RESEARCH_LOG.md](RESEARCH_LOG.md), [sources page](sources.html)); only NBA-official domains | ✅ |
| T04 | **Strategies + validation gates** — S1 Edge Single, S2 Correlated Double, S3 Prop Stack, S4 Rest/Fatigue; 17 gates across strategies; correlation values measured from official data; luck-removal controls pre-registered ([STRATEGIES.md](STRATEGIES.md)) | ✅ |
| T05 | **Slate & injury data** — all **31 games** Nov 13–16 (today + 3-day max window), dual-verified schedule; full 05:00 PM injury report transcribed; 30-team official stats; blanks flagged, never inferred | ✅ |
| T06 | **Auto picks pipeline** — `generate_picks.py` → `picks.json` with no manual input; 7 released paper picks, 22 provisional (injury-pending), 2 recorded passes, 1 parlay, 1 prop stack ([PICKS_PIPELINE.md](PICKS_PIPELINE.md)) | ✅ |
| T07 | **Injury → rotation/production + game flow** — rotation-gated production-at-risk (Curry 38.2 GSW-loss night leader with B.Williams; Mobley+Merrill 24.6 CLE; Murphy+Murray 29.0 NOP), rest/B2B matrix for all 31 games ([INJURY_GAMEFLOW.md](INJURY_GAMEFLOW.md)) | ✅ |
| T08 | **This summary** | ✅ |
| T09 | **Questions register** — 12 Q&As; 10 unanswered gate real decisions (CLV source, HCA calibration, license, CI…), 2 answered in-design ([questions page](questions.html)) | ✅ |
| T10 | **Suggestions queue** — 8 suggestions, each with 2 paths + recommendation, **none implemented** — reviewer chooses first ([suggestions page](suggestions.html)) | ✅ |
| T11 | **Flagged for Review** — 18 items, evidence-linked; 6 resolved-by-workaround, 12 open ([flagged page](flagged.html)) | ✅ |
| T12 | **GitHub Pages site** — 12-page dashboard built *from* the JSON by `build_site.py`; every data row source-linked | ✅ |
| T13 | **Verification pass** — `d01ae7e2/scripts/verify.py`: 394 URLs against official-domain allowlist, blank+flag policy, pick coverage, HTML link integrity | ✅ |
| T14 | **Integration** — build + verify re-run after merge inputs unified | ✅ |
| T15 | **Pages deploy + PR + merge + recording** — see COORDINATION.md integration record | see COORDINATION |

## Headline findings

1. **Margin beats everything.** Across all 30 official team rows, win% correlates with point differential at **r = 0.935** vs only 0.641 with scoring alone — two-way differential (net rating) is the correct line-origination core, which is what S1 uses.
2. **The binding constraint today is injury-report freshness, not the model.** 22 of 31 slate rows are provisional because official reports for 11/14 (7 teams) are `NOT YET SUBMITTED` and 11/15–16 do not exist yet. The pipeline publishes labelled provisional lines instead of guessing — the brief's "3-day auto-generation" and "never infer" requirements are satisfied simultaneously.
3. **Verified production at risk, 11/13:** GSW loses **38.2 PPG** (Curry 27.8 + Williams 10.4, both rotation-verified), NOP 29.0 (Murphy + Murray), CLE 24.6 (Mobley + Merrill), UTA 18.0 (Markkanen), MEM 7.6 (Edey). OKC's big names (Holmgren, J.Williams) *fail* the rotation gate — their absence is already inside OKC's 8-4 baseline; counting it again would have flipped the LAC line (caught pre-settlement as rev-B).
4. **Rest is unusually concentrated:** five teams sit on back-to-backs on 11/14 alone — S4 (rest subset strategy) is pre-registered to test exactly that edge.
5. **Two honest model revisions, zero settled picks:** INJ_WEIGHT 0.6→0.35 + cap (implausible −18.7 lines), then the rotation gate (double-counting). Both logged pre-settlement in `strategies.json`.
6. **CLV — the strongest anti-luck gate — is blocked** by the absence of an authorized market-odds source (nba.com odds are client-rendered only). Fallback: Wilson-CI-on-settled-picks; flagged as Q-04 so a reviewer can authorize a source.

## Honest limitations

- HCA (2.5), rest and injury weights are **assumptions** pending calibration (Q-03/SG-03); 13 OUT-player PPGs uncollected (fl-13/Q-02); player correlation n=5 (Q-12); **no completed-game grading has run** — every number visible is PAPER/PROVISIONAL, nothing has been "won".
- This is research and paper-trading only. Not betting advice.

## How to reproduce / verify

```bash
python3 d01ae7e2/scripts/generate_picks.py && python3 d01ae7e2/scripts/build_site.py && python3 d01ae7e2/scripts/verify.py
```
