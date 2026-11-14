# Official capture — NBA injury-report index, read 2026-11-14 (UTC)

Source: <https://official.nba.com/nba-injury-report-2026-27-season/>
Read on: 2026-11-14, ~10:22 UTC and again ~10:40 UTC (both reads returned the same list).
Transcribed by: session `dd1eb1f1` (`arena/dd1eb1f1-nba3`).

## Reporting rule, verbatim from the index page

> NBA teams must report information concerning player injuries, illnesses, other medical conditions, or rest for all NBA games. By 5 p.m. local time the day before a game (other than the second day of a back-to-back), teams must designate a participation status and identify a specific injury, illness, other medical condition, or other reason for any player whose participation in the game may be affected for any reason. For the second game of a back-to-back, teams must report the above information by 1 p.m. local time on the day of the game.
>
> In addition, teams are required to submit a game-day injury report between 11 a.m. and 1 p.m. local time (and between 8 and 10 a.m. for tip-offs 5 p.m. or earlier) on game days (besides the second game of a back-to-back).
>
> Reports are updated on a continual basis throughout the day.

## Newest 2026-11-14 report listed at read time

The index listed 2026-11-14 reports at 15-minute intervals from **12:00 a.m ET** through
**4:30 a.m ET**. The last link printed for November 14 was:

<https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_30AM.pdf>

That PDF was fetched and transcribed in full (49 rows) — see
`official_injury_report_2026-11-14_0430AM.json`.

## Probe for a newer report (negative result, recorded rather than assumed)

`https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_05_30AM.pdf` was requested
at ~10:40 UTC on 2026-11-14 and returned an S3 error object:

```
<Error><Code>AccessDenied</Code><Message>Access Denied</Message>
<RequestId>G8EED6XQ78D37F6E</RequestId> ...
```

i.e. the object does not exist. So at read time **no report newer than 04:30 AM ET had been
published**, and the canonical dataset (which carries the 04:15 AM ET report) is at most 15 minutes
behind the newest official file — and is content-identical to it, as the row-by-row comparison in
`verification_report.json` shows.

## What is NOT in this capture

* No 11/15 or later report is listed for dates after 11/14 on the index at read time; the 11/15 rows
  inside the 04:30 AM report are `NOT YET SUBMITTED` placeholders only.
* `stats.nba.com` endpoints are not reachable from this workspace (recorded by earlier sessions and
  re-confirmed here). Team and player statistics were therefore not re-read by this session; the
  schedule page (`www.nba.com/schedule`) and the injury PDFs (`ak-static.cms.nba.com`) are reachable.
