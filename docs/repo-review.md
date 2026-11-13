# Repository review — line-by-line audit of prior work

Reviewed 2026-11-13 against `main` at `6c3004d3`, which contained work from an earlier,
already-closed session (`arena/49064d5a-nba3`, PRs #1 and #2).

---

## 1. What was in the repository before this session

| Path | Size | Content |
|---|---|---|
| `README.md` | 6 bytes | Empty placeholder. |
| `index.html` | ~19 KB | A single-page dashboard shell: navigation, styling, section framework. |
| `COORDINATION.md` | — | Task board. |
| `.github/workflows/pages.yml` | — | Pages deploy with a light in-page link check. |

## 2. Findings, in severity order

### F1 — The site asserted that no data existed. That was false. (corrected)

The prior `index.html` stated that no schedule, no injury data and no odds were available.
All three were in fact retrievable:

- the official schedule, with `002…` game IDs, tip times and venues;
- the official dated injury PDF behind `official.nba.com`;
- public two-way prices with open and current numbers.

**Action:** collected all three, and recorded the correction as `IR-03` on the review page
rather than silently replacing the claim. A previous claim that "there is no data" is itself
a factual error worth keeping on the record.

### F2 — The injury link pointed at the wrong season. (corrected)

The prior build linked the **2025-26** injury-report index while the live season is
**2026-27**. A dead or stale official link is worse than no link, because it looks
authoritative.

**Action:** corrected to the 2026-27 index, and the specific dated PDF
(`Injury-Report_2026-11-13_05_00PM.pdf`) is linked from every injury row. Logged as `IR-02`.
`validate_site.py` now fails the build if the stale 2025-26 path reappears anywhere.

### F3 — The deploy gate could not fail on the things that matter. (replaced)

The prior workflow checked only in-page `#anchor` links on `index.html`. It would have
happily deployed a page with a dead internal link to another page, a table row with no
source, a missing value rendered as `0`, or a probability outside `(0,1)`.

**Action:** `scripts/validate_site.py` now gates the deploy on:

- every internal link resolving across all 10 pages;
- every **data** row (any `<tr>` containing a `<td>`) carrying an `http(s)` source link —
  header rows are correctly exempt;
- an "unverified" chip never coexisting with a number in the same cell;
- `model_spread_home == -model_margin_home` on every row (this is the regression test for the
  sign bug found in F5);
- win probabilities summing to 1, over/under summing to 1, all probabilities in `(0,1)`;
- correlation coefficients published only with `n ≥ 3`;
- no prop model probability without a model;
- no pick that "passed screening" while carrying high injury risk;
- statistic ranges (`margin_sd`, `total_sd`, `home_margin_mean`) inside sane bounds;
- stale-content detection for the previous build's claims.

CI additionally **regenerates** the data and HTML and fails if the output differs from the
commit, so a hand-edited page cannot reach production.

### F4 — The board marked tasks done before the work existed. (corrected)

`COORDINATION.md` listed T1–T12 as `done`, and its verification log described a `data/raw/`
directory, "31 games across 4 slates" and a `scripts/build_all.py` — **none of which existed
in the repository**. Its IR numbering also disagreed with the review page.

This matters more than tidiness: a board that reports completion is the artefact another
session trusts before deciding what to do. False completion is how duplicated and conflicting
work starts.

**Action:** the board was rewritten against the actual repository state. T4 and T6 are now
correctly `partial`; T11 and T12 are `in progress` / `open` until the CI run is observed
green. A correction notice sits at the top of the file.

### F5 — Sign-convention bugs, found by cross-checking against a known-sane baseline

Two errors, both of which produced *plausible-looking* output and neither of which raised an
exception:

1. **Market transcription.** Several away/home moneylines and spread signs were transposed
   relative to the provider's own details string. Caught by re-parsing each row's details
   string (`"ORL -9.5"`) and comparing favourite and line against the parsed fields. The first
   *checker* was itself inverted; after fixing the checker, all 9 rows reconciled.
2. **Cover probability.** The model used the listed handicap where the margin belonged,
   producing cover probabilities off by tens of points. Caught by testing a pick'em, where the
   answer must be 0.50.

**Lesson recorded in the repo:** cross-check a formula's *direction* against a case whose
answer is known before trusting its output, and make the invariant a build-time assertion
rather than a memory.

Also found: text-replace patching of a dict literal in `raw_data.py` silently **duplicated**
the `MARKET` block. Fixed, and the region was re-read with `grep -n` afterwards.

## 3. What was kept from the prior work

- **The visual language.** The navy header, card layout and table styling were sound and are
  preserved; the prior session's CSS was a reasonable starting point and rewriting it would
  have been churn.
- **The multi-section dashboard shape.** Retained, extended to ten pages so that research,
  picks, method and the review register have distinct, separately-linkable homes.
- **The Pages workflow structure.** Retained; the validation step is what changed.

Nothing was force-pushed and no prior session's work was reverted. The earlier PRs (#1, #2)
remain merged in history.

## 4. What prior work got right (worth stating)

- The decision to keep the site as static HTML with no build toolchain means the deploy is
  trivially auditable and cannot rot from a dependency upgrade.
- The review-page concept — a labelled home for everything unverified — was correct and is
  now the primary honesty mechanism (`review.html`, IR-01 … IR-15).
- Framing the work as research rather than advice was correct, and is now enforced by the
  validator rather than by convention.

## 5. Current state after this session

| Layer | Status |
|---|---|
| Source snapshot | Complete, with URL + tier + timestamp per block. 30 team ratings, 86 results, 23-game slate, 9 market snapshots, 75 injury statuses. |
| Arithmetic integrity | All 30 teams satisfy `NetRtg = ORtg − DRtg` and `SRS = MOV + SOS`; subset records never exceed season records. |
| Model | Measured constants, disclosed assumptions, sensitivity table, one documented bug class now regression-tested. |
| Site | 10 generated pages, every data row sourced, build gate green. |
| Strategies | Pre-validation by design. No strategy eligible. |
| Deploy | Pending CI observation. |
