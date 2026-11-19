# Round 2026-11-19-93becd26 — one game log per player on the official injury report

Session `arena/93becd26-nba3`. Published at `93becd26/` on the Pages site
(<https://wingbangboozle1-lang.github.io/NBA3/93becd26/>) via the append-only step in
`.github/workflows/pages.yml`.

## What this round produces

One row for every player listed on the newest official NBA injury report at capture
(11/19/26 02:15 AM ET revision), each paired with that player's most recent completed
game log — date, opponent, minutes, points, rebounds, assists, or the DND/inactive reason
exactly as the official box-score game book prints it.

## Captures (verbatim, sha256 in `manifest.json`)

| File | Source |
|---|---|
| `captures/injury_report_2026-11-19_0215AM.md` | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_02_15AM.pdf |
| `captures/injury_report_2026-11-19_0200AM.md` | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_02_00AM.pdf |
| `captures/gamebook_2026-11-17_PORMIN.md` | https://statsdmz.nba.com/pdfs/20261117/20261117_PORMIN.pdf |
| `captures/gamebook_2026-11-17_DETSAS.md` | https://statsdmz.nba.com/pdfs/20261117/20261117_DETSAS.pdf |
| `captures/gamebook_2026-11-17_UTALAC.md` | https://statsdmz.nba.com/pdfs/20261117/20261117_UTALAC.pdf |
| `captures/schedule_2026-11-18_finals.json` | https://www.nba.com/schedule?date=2026-11-18 (absence proof: none of LAC/SAS/MIN/POR played 11/18) |

## Generated (deterministic; `--check` byte-compares)

- `manifest.json` — sha256, byte size, official URL per capture.
- `injury_parsed.json` — both revisions parsed row-for-row (including the page-broken
  sections, recorded as printed) + the consecutive 02:00 → 02:15 diff.
- `player_logs_injury_2026-11-19.json` — 23 rows (21 team-printed, 2 blank-team
  F-93-01), logs: 6 played, 2 DND, 15 inactive, 0 unmatched, 0 problems.

## How to re-check

```sh
python3 scripts/capture_93becd26.py --check   # JSONs vs committed captures
python3 scripts/build_93becd26.py --check     # site pages vs JSONs
python3 -m unittest tests/test_93becd26.py -v
```

## Flagged for review

`93becd26/flagged.html` (F-93-01..F-93-09). Nothing is inferred: cells that no official
source prints stay blank and flagged.
