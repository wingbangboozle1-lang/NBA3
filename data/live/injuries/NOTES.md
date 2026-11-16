# Injury-report archive — how these files were produced, and what is verbatim

## Files

| File | Official source | Retrieved (UTC) | Pages in extraction |
|---|---|---|---|
| `Injury-Report_2026-11-15_06_00AM.md` | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_00AM.pdf | 2026-11-15T11:40Z | 6 |
| `Injury-Report_2026-11-15_06_15AM.md` | https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf | 2026-11-15T11:33Z | 6 |

The [official index](https://official.nba.com/nba-injury-report-2026-27-season/) listed the
11/15 reports from 12:00 a.m. ET through 6:15 a.m. ET at read time; 6:15 a.m. ET is the newest
that existed.

## What is verbatim and what is normalised

* Every **player name, status and reason string is verbatim** from the PDF extraction.
* Every **game date, game time, matchup and team value that appears** in the files is verbatim.
* **One normalisation:** the PDF's page-break continuation rows come out of the extractor with
  fewer than seven cells (e.g. `| Collin Sexton ... |` style rows, 5 or 6 cells). Leading empty
  cells were added so every row has the same seven columns. No empty cell was filled with a
  guessed value — in particular, the **Team** cell of a continuation row is left as the extractor
  produced it, and the parser treats a missing Team as `UNATTRIBUTED`.
* Nothing is inferred: a row with no team is *not* attributed to the team above it. Earlier
  sessions on this repository did carry the team forward; that is a different, weaker rule and it
  is flagged on the Injuries page as a known difference.

## Known extraction artifacts (both files)

1. Player-name spelling differs between consecutive reports: the official [06:00 AM PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_00AM.pdf)
   says `Embiid, Joel`, while the official [06:15 AM PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf)
   says `Embid, Joel`. The [12:00 AM PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_12_00AM.pdf)
   says `Embiid, Joel`. The diff treats these as **the same player** only when the normalised
   key (lowercase, punctuation stripped) matches; otherwise it reports an add + a remove and says
   so. The measured diff reports both cases separately.
2. Team cell dropped on some rows (`Sexton, Collin`, `Thiero, Adou`, `Simmons, Ben`), so those
   players are `UNATTRIBUTED`.
3. `NOT YET SUBMITTED` team rows have no player, status or reason; they are counted as team-level
   rows, not player rows.

## Why these two reports

The brief asks for consecutive reports to be stored and diffed so status changes are visible.
06:00 and 06:15 are consecutive official versions of the same document, 15 minutes apart, and
both cover the same 11/15 slate — so any difference between them is a real status change, not a
slate change. `scripts/injury_archive.py` performs the diff and CI re-runs it offline.
