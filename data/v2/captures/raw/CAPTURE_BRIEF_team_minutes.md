# Capture brief — per-team top-8 minutes (v2 pipeline, session arena/5a67ab8c-nba3)

## What to do

For each of the 30 NBA teams listed below, fetch ONE url and write the result to
`data/v2/captures/raw/team_minutes_<TEAM>.json`.

Replace `{TEAM_ID}` in the template with the id given in the table. The url is:

```
https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=12&TeamID={TEAM_ID}&SortColumn=MIN&SortDirection=DESC
```

Read the page by calling the fetch tool with `chunkIndex: 2` FIRST. On that page
shape chunk 2 contains the player table. If chunk 2 does not contain the table,
read chunks 1, 3 and 4 until you find it. Do not read more chunks than you need.

## Output format (exact)

```json
{
  "kind": "team_player_minutes",
  "team": "IND",
  "team_id": "1610612754",
  "source_url": "<the exact url you fetched>",
  "retrieved_utc": "<write the value of `date -u +%Y-%m-%dT%H:%MZ` you ran immediately before fetching>",
  "rows_returned": 16,
  "players": [
    {"name": "Pascal Siakam", "gp": 12, "min": 32.1, "pts": 22.4, "reb": 6.6, "ast": 4.2}
  ],
  "raw_chunk_text": "<the exact table text of the chunk you parsed, verbatim, as a single string>"
}
```

`rows_returned` is the row count the page itself prints ("16 Rows"). `players`
holds the **top 8 rows by minutes, in the order the page prints them**.

## Hard rules — a violation invalidates the whole capture

1. **Never invent, infer, estimate, interpolate or fill a value.** Copy digits
   exactly as printed. If a column shows `-` or is blank, use `null`.
2. **Never compute a column.** Do not sum or average anything.
3. **`reb` is the REB column, not OREB + DREB.** Copy the printed REB cell.
4. If a player row is split across a chunk boundary so that a field is not
   readable, record the player with the fields you did read and `null` for the
   rest, and add `"notes": "row split across chunk boundary"` to that player.
5. If the page does not load, or the row count is 0, write the file with
   `"players": []` and `"error": "<what happened>"`. Do not substitute another
   source. Do not use basketball-reference, ESPN or any other site.
6. The only permitted source is the nba.com url above. Nothing else.
7. Do not edit any file other than `data/v2/captures/raw/team_minutes_<TEAM>.json`.

## Teams and ids

| TEAM | TEAM_ID |
|---|---|
| ATL | 1610612737 |
| BOS | 1610612738 |
| BKN | 1610612751 |
| CHA | 1610612766 |
| CHI | 1610612741 |
| CLE | 1610612739 |
| DAL | 1610612742 |
| DEN | 1610612743 |
| DET | 1610612765 |
| GSW | 1610612744 |
| HOU | 1610612745 |
| IND | 1610612754 |
| LAC | 1610612746 |
| LAL | 1610612747 |
| MEM | 1610612763 |
| MIA | 1610612748 |
| MIL | 1610612749 |
| MIN | 1610612750 |
| NOP | 1610612740 |
| NYK | 1610612752 |
| OKC | 1610612760 |
| ORL | 1610612753 |
| PHI | 1610612755 |
| PHX | 1610612756 |
| POR | 1610612757 |
| SAC | 1610612758 |
| SAS | 1610612759 |
| TOR | 1610612761 |
| UTA | 1610612762 |
| WAS | 1610612764 |

## Reference — a verified example of the exact page shape

This is the real IND chunk-2 text captured by the lead session at 11:52Z. Use it
to recognise the table; do not copy it as another team's data.

```
| 1 | [Pascal Siakam](https://www.nba.com/stats/player/1627783/) | [IND](https://www.nba.com/stats/team/1610612754) | 32 | 12 | 5 | 7 | 32.1 | 22.4 | [8.1](...) | [16.1](...) | 50.3 | [1.8](...) | [4.9](...) | 35.6 | 4.5 | 6.3 | 71.1 | 1.3 | 5.3 | 6.6 | 4.2 | 2.2 | 0.9 | 0.1 | 2.8 | 37.4 | 40.3 | 2.0 | 0.0 | -0.7 |
```

Column order: `# | Player | Team | Age | GP | W | L | MIN | PTS | FGM | FGA | FG% | 3PM | 3PA | 3P% | FTM | FTA | FT% | OREB | DREB | REB | AST | TOV | STL | BLK | PF | TFP | HSFP | DD2 | TD3 | +/-`.

So for that row: name `Pascal Siakam`, GP 12, MIN 32.1, PTS 22.4, REB 6.6, AST 4.2.

(Ignore the `(...)` — the real cells are markdown links whose anchor text is the
number. Read the anchor text.)
