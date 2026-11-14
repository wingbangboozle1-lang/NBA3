# NBA3 Repository Review (T01)

**Reviewer:** session d01ae7e2 · **Reviewed:** 2026-11-13 · **Base commit:** `6c3004d` (main) · **Current branch:** `arena/d01ae7e2-nba3`

Scope: every file and every commit in the repository, line by line, plus irregularities observed while collecting the official-source data that this project builds on. Each finding links its evidence.

## 1. File inventory at base commit `6c3004d`

Verified with `git ls-tree -r 6c3004d --name-only` and `od -c README.md`.

| File | Bytes | Line-by-line finding | Irregularity | Severity |
|---|---|---|---|---|
| `README.md` | 6 | Single line: `# NBA3` — no trailing newline. No description of purpose, no data sources, no structure map, no usage/verification instructions, no license pointer. | Repository advertises an NBA research project but contains zero research, data or code. | **High** |
| `.gitignore` | — | Absent. | No ignore rules; generated artifacts (`docs/*.html`, `data/*.json`) are currently committed deliberately (they are deliverables), but scratch files have no protection. | Low |
| `LICENSE` | — | Absent. | Reuse/derivative terms undefined. Per the brief this is a reviewer decision — logged as **Q-07**, not fixed autonomously. | Low |
| `.github/` | — | Absent (no workflows, PR/issue templates, CODEOWNERS). | No CI. Verification is local (`scripts/verify.py`); promoting it to CI is logged as suggestion **SG-01** / **Q-08**. | Low |

## 2. Commit history (line-by-line)

`git log --all --date=iso`:

| Commit | Date | Author e-mail | Message | Finding |
|---|---|---|---|---|
| `6c3004d` | 2026-11-14 07:17 +0900 | *(personal gmail)* | Initial commit | Timestamp zone +0900 while later commits are +0000 — sequencing is correct, display is confusing. **fl-02** |
| `65b21b2` | 2026-11-13 22:26 +0000 | `…@users.noreply.github.com` | T02: create COORDINATION.md… | E-mail identity differs from the initial commit. **fl-02** |
| `baf9f5b` | 2026-11-13 23:24 +0000 | `…@users.noreply.github.com` | T02: claim T04-T15… | Clean. |

- One author (`wingbangboozle1-lang`), two e-mail forms, two timezone conventions — recorded, not an integrity problem.
- Branch state: local `main`, local `arena/d01ae7e2-nba3` (working), `origin/main`, `origin/arena/d01ae7e2-nba3`. `origin/HEAD -> origin/main`. No tags.

## 3. Structural irregularities (whole-repo)

1. **No LICENSE / no CI / no .gitignore** — table above; routed to Questions Q-07/Q-08 rather than fixed silently.
2. **No CODEOWNERS / PR template** — review process was undefined; solved process-wise by `COORDINATION.md` (session protocol) rather than tooling.
3. **Deliverables policy**: generated site (`docs/`) and data (`data/`) are committed because GitHub Pages serves `docs/` directly from the branch — this is intentional, documented in `docs/PICKS_PIPELINE.md`.

## 4. Data-source irregularities found during review

These were found while verifying the sources the repo's data depends on (full detail with evidence in `data/flagged.json`, page: [Flagged](flagged.html)):

| ID | Finding | Severity |
|---|---|---|
| fl-03 | `nba.com/standings` returns no table to a non-JS fetch — records harvested from game pages + league stats page instead (both official, cross-checked). | Medium |
| fl-04 | Official schedule PDF uses an **`R` flag** (games 27, 40, 50) that the PDF's own legend does not define (legend defines only C, A, B, D, E). Not inferred. | Medium |
| fl-05 | Documented injury-report cadence (1:30/5:30/8:30 p.m. ET) ≠ observed stamps today (01:00, 01:15, 04:15, 05:00 PM ET). | Medium |
| fl-06 | 11/14 teams partly `NOT YET SUBMITTED`; 11/15–16 reports not published → picks gated provisional. | **High** |
| fl-07 | PDF page-break left a blank team cell (`Williams, Brandon`); attributed to GSW via roster cross-check, recorded as attribution not fact. | Low |
| fl-08 | MIL OPPG 121.3 (direct) vs 121.4 (derived) — 0.1 rounding between two official renderings. | Low |
| fl-09 | DET@MIA TV: PDF blank vs NBA TV on the live page — live page treated as current. | Low |
| fl-10 | Schedule PDF rows 215+ lose the `at` separator; away/home order re-verified for all 31 slate games via preview URL slugs + venues. | Medium |
| fl-11 | `nba.com/player/1629027/shai-gilgeous-alexander` renders **Trae Young** (Washington) — slug/ID mismatch on NBA's own URL space; canonical URL corrected. | Low |
| fl-12 | Live scoreboard JSON → HTTP 500; `stats.nba.com` standings API blocked. Recorded do-not-retry. | Medium |
| fl-14 | `official.nba.com/injury-report/` → 404; real path pattern is `ak-static.cms.nba.com/referee/injury/…`. | Low |
| fl-15 | Schedule PDF is an August snapshot marked *SUBJECT TO CHANGE* — every slate row re-verified against the live page today. | Low |
| fl-16 | Odds are behind a client-side toggle; no market odds captured → CLV gates explicitly **BLOCKED** (Q-04). | Medium |

## 5. What was *not* done (and why)

- No `LICENSE`, no CI workflow, no README rewrite of original content without replacement — the brief requires the reviewer to choose a path before implementation for improvements (Suggestions SG-01, Q-07/Q-08).
- No silent correction of any flagged value — blank + flagged policy applied throughout.

## 6. Evidence commands

```bash
git ls-tree -r 6c3004d --name-only   # -> README.md
wc -c README.md                       # -> 6
git log --all --date=iso --pretty='%h %ad %an <%ae> %s'
git branch -a
```
