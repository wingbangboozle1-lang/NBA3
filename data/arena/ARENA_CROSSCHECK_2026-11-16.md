# Arena identity cross-check — 2026-11-16 (session `arena/ca7b8b4d-nba3`)

Scope: arena **name** only, for the 30 home venues in `data/app/arena_coordinates.json`. Coordinates are not checked here (the NBA does not publish coordinates). Machine-readable version: `nba_arenas_official_2026-11-16.json`.

| Team | Table arena | Official evidence | Status | Source link |
|---|---|---|---|---|
| ATL | State Farm Arena | Team site nav: "State Farm Arena" | Confirmed | https://www.nba.com/hawks/ |
| BKN | Barclays Center | Team site nav: "Barclays Center" | Confirmed | https://www.nba.com/nets |
| CLE | Rocket Arena | Team schedule ticket link slug + repo game book 11/14 DAL@CLE ("Rocket Arena, Cleveland, OH") | Confirmed (weaker: slug and game book) | https://www.nba.com/cavaliers/ |
| IND | Gainbridge Fieldhouse | Team page game listing: "Gainbridge Fieldhouse, Indianapolis, IN" | Confirmed | https://www.nba.com/pacers/ |
| MIL | Fiserv Forum | Team arena page: "Fiserv Forum" | Confirmed | https://www.nba.com/bucks/arena |
| PHI | Wells Fargo Center | Official Sixers arena page unavailable at check time. News reports say the venue became **Xfinity Mobile Arena** (Aug/Sep 2025) | **MISMATCH — flagged** | https://www.delawareonline.com/story/sports/nba/76ers/2025/08/14/wells-fargo-center-xfinity-mobile-arena-south-philadelphia-sixers-flyers/85659394007/ |
| 23 others | (as in table) | Not checked in this session | Unverified | — |

## Irregularities for review

1. **PHI name is probably out of date.** The table says "Wells Fargo Center". News reports from 2025 say it is now Xfinity Mobile Arena. Needs an official Sixers or Comcast source before the table is changed.
2. **`arena_coordinates.json` labels every row `verified: true`.** That label is backed by Wikipedia only, and that file's own notes say the NBA does not publish these coordinates. Read it as "Wikipedia-sourced".
3. **Coordinates remain unverified.** Travel distance stays blank until an accepted coordinate source is chosen. This file does not add any coordinates.
4. **23 arena names still unchecked.** Next step is one official team-page read per team (the team nav or arena page), recorded in the JSON.
