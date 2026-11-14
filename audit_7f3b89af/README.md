# Independent audit — session `arena/7f3b89af-nba3`

Official NBA pages re-read on **2026-11-14 at 18:45 UTC** and compared, cell by cell, with what the
NBA3 dashboard already publishes.

This tree adds pages to the site. It does **not** change the canonical dataset, the canonical pages,
or any other session's files. Where it finds a difference it publishes it, with the page that proves
it, and leaves the decision to the owner.

## What it found

| ID | Item | Severity |
|---|---|---|
| F-7F3-01 | The published injury snapshot is nine hours behind the newest official report (04:15 AM ET published; 01:30 PM ET is newest) | high |
| F-7F3-02 | Three of tonight's five games had no team report at all when the site was built; all three filed by 01:30 PM ET, adding 24 player rows | high |
| F-7F3-03 | 47 canonical injury cells carry a date or time the injury PDF never prints. Values are correct (all re-checked against the schedule); the row-level source link points at the wrong page | medium |
| F-7F3-04 | The official schedule prints POR@MIN twice and NYK@TOR twice inside the window, and two 11/17 game ids out of chronological order | low |
| F-7F3-05 | Two teams' official advanced-statistics cells moved after the published capture (CLE, CHA). Net rating unchanged, so no spread or total moves | low |
| F-7F3-06 | One line of the 01:30 PM PDF prints two rows jammed together. Session 736efb4b left it unparsed; this tree split it and marked both rows `garbled`. Row counts therefore differ (67 vs 69) with no disagreement about the document | low |

The measured analysis on the Analysis page answers a question the site had not asked: **does the
originated line price rest?** Answer — no, but the signal it leaves is not yet usable: the line's
error carries +2.44 points of home margin per extra rest day (r = 0.142, permutation p = 0.097, BH
q = 0.244 over five tests), and adding a rest term walk-forward made the line **worse** by 0.33
points of RMSE. Verdict: do not add it on this evidence; re-test at roughly 389 out-of-sample games.

The Brief-coverage page maps all 21 requirements in the owner's brief to what exists, with the
counts read from the published dataset at build time.

## Files

| Path | What it is |
|---|---|
| `capture.py` | Verbatim transcriptions of the four injury reports, the 27-game slate and the 30 team ratings, as source code. This is the step that cannot be automated: the pages were read by a person and typed in. |
| `data/*.json` | Generated from `capture.py`. Cells the official page does not print are empty strings, never inferred. |
| `checks.py` | The 15 checks, including a cross-session comparison against `audit_736efb4b`, which transcribed the same 01:30 PM PDF independently on the same day. Writes `data/verification_report.json`. |
| `analysis.py` | The rest analysis. Seeded (20261114), 20,000 permutations. Writes `data/analysis.json`. |
| `build.py` | Generates `pages/*.html` and enforces both page rules. |
| `test_audit.py` | 26 tests; run by CI. |
| `pages/*.html` | The published pages. Generated — do not edit by hand. |
| `assets/audit.css` | Only the classes the shared stylesheet does not define. |

## Reproduce

```sh
python3 audit_7f3b89af/capture.py     # writes data/ from the transcribed tuples
python3 audit_7f3b89af/checks.py      # 15 checks -> data/verification_report.json
python3 audit_7f3b89af/analysis.py    # rest analysis -> data/analysis.json
python3 audit_7f3b89af/build.py       # -> pages/
python3 -m unittest discover -s audit_7f3b89af -p 'test_*.py'
```

CI runs steps 2–5 on every push and fails on drift.

## Official sources read

- Injury report index: <https://official.nba.com/nba-injury-report-2026-27-season/>
- Reports: 04:15 AM, 04:45 AM, 01:15 PM, [01:30 PM](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf) ET (the 01:45 PM file returns `AccessDenied`, which is how the CDN answers for a report that does not exist)
- Schedule: <https://www.nba.com/schedule?date=2026-11-14> (chunks 0–2 of 9)
- Team advanced statistics: <https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season>
- Team index for name → abbreviation: <https://www.nba.com/teams>

## Rules this tree follows

1. A cell the official page does not print is published empty, and the fact that it is empty is
   recorded (`cells_printed`).
2. Every table row links to the page it came from. The build fails otherwise.
3. Nothing is corrected in another session's file. Differences become flags with a suggested owner
   action.
