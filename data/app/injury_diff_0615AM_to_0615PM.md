# Injury report diff: 11/15/26 06:15 AM ET → 06:15 PM ET (session arena/8d1535bc-nba3, U1)

Official sources (listed on the NBA's official index). The 06:15 PM PDF was read by this session; the 06:15 AM PDF was transcribed earlier by session `arena/bb0c83a4-nba3` and was not re-fetched here:

- 06:15 PM ET: https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15PM.pdf
- 06:15 AM ET: https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-15_06_15AM.pdf
- Index: https://official.nba.com/nba-injury-report-2026-27-season/ (lists 11/15 reports through **6:15 p.m ET**, the newest at capture time)

Transcripts: `data/app/official_injuries_2026-11-15_0615PM_raw.md` (new, verbatim, 3 fetch chunks), `data/app/official_injuries_2026-11-15_0615AM_raw.md` (earlier session).

## Status changes (same player name in both reports)

| Player | Team | 06:15 AM | 06:15 PM | PM reason | Team cell in PDF |
|---|---|---|---|---|---|
| Adams, Steven | Houston Rockets | Probable | Available | Injury/Illness - Right Soleus Strain | printed |
| Barnes, Scottie | Toronto Raptors | Questionable | Available | Injury/Illness - Left Groin Strain | printed |
| Carrington, Bub | Washington Wizards | Questionable | Available | Injury/Illness - Chest / Sternum Contusion | printed |
| Carter, Devin | Boston Celtics | Questionable | Available | G League - Two-Way | printed |
| Cenac Jr., Christopher | Boston Celtics | Questionable | Available | G League - On Assignment | printed |
| James, Bronny | Los Angeles Lakers | Questionable | Available | Injury/Illness - Illness | printed |
| Johnson, Tre | Washington Wizards | Questionable | Out | Injury/Illness - Low Back Soreness | printed |
| Landale, Jock | Atlanta Hawks | Available | Out | Injury/Illness - Right Hip Inflammation | printed |
| McConnell, T.J. | Indiana Pacers | Probable | Available | Injury/Illness - Right Hamstring Strain | printed |
| Mitchell, Dillon | not printed | Questionable | Available | G League - Two-Way | blank in PDF (not attributed) |
| Murray, Keegan | Sacramento Kings | Questionable | Available | - | printed |
| Nembhard, Andrew | Indiana Pacers | Questionable | Out | Injury/Illness - Left Hip Soreness / Tightness | printed |
| Nesmith, Aaron | Indiana Pacers | Questionable | Available | Injury/Illness - Left Hand Sprain | printed |
| Okpara, Felix | not printed | Questionable | Out | G League - Two-Way | blank in PDF (not attributed) |
| Sarr, Alex | not printed | Questionable | Available | Injury/Illness - Illness | blank in PDF (not attributed) |
| Sexton, Collin | not printed | Questionable | Available | Injury/Illness - Right Orbital Laceration | blank in PDF (not attributed) |
| Thiero, Adou | not printed | Questionable | Available | Injury/Illness - Left Ankle Sprain | blank in PDF (not attributed) |
| Williams, Amari | not printed | Questionable | Available | G League - Two-Way | blank in PDF (not attributed) |
| Wilson, Jalen | Atlanta Hawks | Doubtful | Out | G League - Two-Way | printed |

## Reason-only changes

| Player | Team | 06:15 AM reason | 06:15 PM reason |
|---|---|---|---|
| Dieng, Ousmane | Milwaukee Bucks | Injury/Illness - Left Finger Sprain | Injury/Illness - Left Finger Fracture |
| Landale, Jock | Atlanta Hawks | Injury/Illness - Face Mask | Injury/Illness - Right Hip Inflammation |
| Murray, Keegan | Sacramento Kings | Injury/Illness - Illness | - |
| Sorber, Thomas | Oklahoma City Thunder | Injury/Illness -  Right Knee Surgery | Injury/Illness - Right Knee Surgery |

## Printed-spelling change

- `Embid, Joel` (06:15 AM, as printed) → `Embiid, Joel` (06:15 PM, as printed). Treated as a removed + added pair by exact name; the PDF printed the correction, not this session.

## Rows newly printed in 06:15 PM

- 65 players appear in the 06:15 PM report but not in 06:15 AM by exact name. Example checked by hand: the 06:15 AM report prints Dallas Mavericks as `NOT YET SUBMITTED` for the 06:00 (ET) DAL@BOS game; the 06:15 PM report lists its players. Full list: `data/app/injury_diff_0615AM_to_0615PM.json`.
- 1 player removed (the spelling change above).

## Irregularities (flagged)

1. **Team not printed on continuation rows.** The PDF's merged cells leave Team blank on some rows (e.g. Sexton, Collin; Thiero, Adou; Okpara, Felix; Curry, Stephen; Moody, Moses; Porzingis, Kristaps; Santos, Gui; Williams, Brandon). These are left with team `null` and are NOT attributed to a team in this file. 15 rows in the 06:15 PM report have a blank team cell in the PDF; they are marked `carried_forward` in the JSON, and where the parser had a team from an earlier row on the same page it is used only for that field's attribution flag, never for the printed-team column.
2. **Ambiguous name.** `Penda, Noah` is printed twice (ORL@BOS, and a Boston line marked `NOT YET SUBMITTED`). Excluded from the diff.
3. **Unattributed PDF fragment.** One 06:15 PM line reads `Fracture` with no player or team (text-extraction fragment of a reason cell). Kept in the JSON under `unattributed_lines`; not assigned.
4. **Transcript artefact in an earlier capture.** The 06:15 AM raw transcript contains `<!-- CHUNK 1 -->` inside the reason cell of Sorber, Thomas. The comparison strips it; the earlier file was not edited.
5. **Not a revision timeline.** Only two reports (06:15 AM and 06:15 PM) are diffed here. Reports between them (06:30 AM … 05:45 PM on the index) were not captured in this round.
6. **Retrieval time.** The PM PDF was read on the sandbox clock at about 23:3x UTC on 2026-11-15 (about 6:3x PM ET). The published report stamp is 06:15 PM ET.

