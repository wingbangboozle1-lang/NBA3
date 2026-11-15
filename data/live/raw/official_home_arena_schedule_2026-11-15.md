# Official home-arena strings, transcribed verbatim from nba.com/schedule

Session `arena/42d69dc5-nba3`. Read 2026-11-15 by fetching
https://www.nba.com/schedule?date=2026-11-18 (chunks 0, 1, 2 and 3 of 8 — one read of that page
renders the whole 11/15-11/22 block).

**Rule applied.** A line is copied only when the official page prints it as the game's venue,
directly under the two team names. Nothing is inferred, normalised, re-spelled or taken from memory.

**Why the file exists.** The repository's own official captures
(`data/live/slate_2026-11-15.json`, `data/app/official_slate_*.json`) contain a venue string for
home games only, and they cover 24 clubs. `data/live/arena_coords.json` resolves a venue *string* to
a coordinate and deliberately has **no city fallback** (a city fallback is exactly the defect that
printed 0.0 km for LAC at Intuit Dome and PHX at Mortgage Matchup Center in an earlier build; it is
recorded on the projection review page). So each club needs an official venue string, and this page
is where the strings for the six clubs missing from the captures come from.

| Official game url | Away | Home | Venue (verbatim) | City (verbatim) | Read from chunk |
|---|---|---|---|---|---|
| https://www.nba.com/game/ind-vs-phi-0022600236 | IND | PHI | Xfinity Mobile Arena | Philadelphia, PA | 0 |
| https://www.nba.com/game/lal-vs-phx-0022600237 | LAL | PHX | Mortgage Matchup Center | Phoenix, AZ | 0 |
| https://www.nba.com/game/cha-vs-lac-0022600238 | CHA | LAC | Intuit Dome | Inglewood, CA | 0 |
| https://www.nba.com/game/sas-vs-uta-0022600239 | SAS | UTA | Delta Center | Salt Lake City, UT | 0 |
| https://www.nba.com/game/dal-vs-bos-0022600240 | DAL | BOS | TD Garden | Boston, MA | 0 |
| https://www.nba.com/game/nyk-vs-tor-0022600241 | NYK | TOR | Scotiabank Arena | Toronto, ON | 0 |
| https://www.nba.com/game/hou-vs-was-0022600242 | HOU | WAS | Capital One Arena | Washington, DC | 0 |
| https://www.nba.com/game/atl-vs-mil-0022600243 | ATL | MIL | Fiserv Forum | Milwaukee, WI | 0 |
| https://www.nba.com/game/okc-vs-sac-0022600244 | OKC | SAC | Golden 1 Center | Sacramento, CA | 0 |
| https://www.nba.com/game/orl-vs-bos-0022600245 | ORL | BOS | TD Garden | Boston, MA | 0 |
| https://www.nba.com/game/chi-vs-cle-0022600246 | CHI | CLE | Rocket Arena | Cleveland, OH | 0 |
| https://www.nba.com/game/mem-vs-was-0022600247 | MEM | WAS | Capital One Arena | Washington, DC | 1 |
| https://www.nba.com/game/phi-vs-bkn-0022600248 | PHI | BKN | Barclays Center | Brooklyn, NY | 1 |
| https://www.nba.com/game/hou-vs-mia-0022600249 | HOU | MIA | Kaseya Center | Miami, FL | 1 |
| https://www.nba.com/game/por-vs-min-0022600250 | POR | MIN | Target Center | Minneapolis, MN | 1 |
| https://www.nba.com/game/gsw-vs-nop-0022600251 | GSW | NOP | Smoothie King Center | New Orleans, LA | 1 |
| https://www.nba.com/game/phx-vs-den-0022600252 | PHX | DEN | Ball Arena | Denver, CO | 1 |
| https://www.nba.com/game/nyk-vs-tor-0022600253 | NYK | TOR | Scotiabank Arena | Toronto, ON | 1 |
| https://www.nba.com/game/por-vs-min-0022600254 | POR | MIN | Target Center | Minneapolis, MN | 1 |
| https://www.nba.com/game/det-vs-sas-0022600255 | DET | SAS | Frost Bank Center | San Antonio, TX | 1 |
| https://www.nba.com/game/uta-vs-lac-0022600257 | UTA | LAC | Intuit Dome | Inglewood, CA | 1 |
| https://www.nba.com/game/cha-vs-lal-0022600256 | CHA | LAL | Crypto.com Arena | Los Angeles, CA | 1 |
| https://www.nba.com/game/mem-vs-cle-0022600258 | MEM | CLE | Rocket Arena | Cleveland, OH | 2 |
| https://www.nba.com/game/hou-vs-ind-0022600259 | HOU | IND | Gainbridge Fieldhouse | Indianapolis, IN | 2 |
| https://www.nba.com/game/mil-vs-mia-0022600260 | MIL | MIA | Kaseya Center | Miami, FL | 2 |
| https://www.nba.com/game/phi-vs-orl-0022600261 | PHI | ORL | Kia Center | Orlando, FL | 2 |
| https://www.nba.com/game/chi-vs-bkn-0022600262 | CHI | BKN | Barclays Center | Brooklyn, NY | 2 |
| https://www.nba.com/game/was-vs-tor-0022600263 | WAS | TOR | Scotiabank Arena | Toronto, ON | 2 |
| https://www.nba.com/game/det-vs-nop-0022600264 | DET | NOP | Smoothie King Center | New Orleans, LA | 2 |
| https://www.nba.com/game/atl-vs-okc-0022600265 | ATL | OKC | Paycom Center | Oklahoma City, OK | 2 |
| https://www.nba.com/game/gsw-vs-dal-0022600267 | GSW | DAL | American Airlines Center | Dallas, TX | 2 |
| https://www.nba.com/game/bos-vs-den-0022600266 | BOS | DEN | Ball Arena | Denver, CO | 2 |
| https://www.nba.com/game/uta-vs-lal-0022600268 | UTA | LAL | Crypto.com Arena | Los Angeles, CA | 2 |
| https://www.nba.com/game/phx-vs-sac-0022600269 | PHX | SAC | Golden 1 Center | Sacramento, CA | 2 |
| https://www.nba.com/game/gsw-vs-mem-0022600270 | GSW | MEM | FedExForum | Memphis, TN | 2 |
| https://www.nba.com/game/por-vs-mil-0022600271 | POR | MIL | Fiserv Forum | Milwaukee, WI | 2 |
| https://www.nba.com/game/nyk-vs-min-0022600272 | NYK | MIN | Target Center | Minneapolis, MN | 2 |
| https://www.nba.com/game/lac-vs-sas-0022600273 | LAC | SAS | Frost Bank Center | San Antonio, TX | 2 |
| https://www.nba.com/game/cha-vs-atl-0022600043 | CHA | ATL | State Farm Arena | Atlanta, GA | 2 |
| https://www.nba.com/game/orl-vs-bkn-0022600044 | ORL | BKN | Barclays Center | Brooklyn, NY | 2 |
| https://www.nba.com/game/ind-vs-cle-0022600045 | IND | CLE | Rocket Arena | Cleveland, OH | 2 |
| https://www.nba.com/game/tor-vs-det-0022600046 | TOR | DET | Little Caesars Arena | Detroit, MI | 3 |
| https://www.nba.com/game/was-vs-chi-0022600047 | WAS | CHI | United Center | Chicago, IL | 3 |
| https://www.nba.com/game/nop-vs-okc-0022600048 | NOP | OKC | Paycom Center | Oklahoma City, OK | 3 |
| https://www.nba.com/game/phx-vs-uta-0022600049 | PHX | UTA | Delta Center | Salt Lake City, UT | 3 |
| https://www.nba.com/game/hou-vs-den-0022600050 | HOU | DEN | Ball Arena | Denver, CO | 3 |
| https://www.nba.com/game/sac-vs-lal-0022600051 | SAC | LAL | Crypto.com Arena | Los Angeles, CA | 3 |
| https://www.nba.com/game/mil-vs-phi-0022600274 | MIL | PHI | Xfinity Mobile Arena | Philadelphia, PA | 3 |
| https://www.nba.com/game/por-vs-nyk-0022600275 | POR | NYK | Madison Square Garden | New York, NY | 3 |
| https://www.nba.com/game/lac-vs-dal-0022600276 | LAC | DAL | American Airlines Center | Dallas, TX | 3 |
| https://www.nba.com/game/mem-vs-min-0022600277 | MEM | MIN | Target Center | Minneapolis, MN | 3 |
| https://www.nba.com/game/nop-vs-sas-0022600278 | NOP | SAS | Frost Bank Center | San Antonio, TX | 3 |
| https://www.nba.com/game/bos-vs-sac-0022600279 | BOS | SAC | Golden 1 Center | Sacramento, CA | 3 |
| https://www.nba.com/game/det-vs-atl-0022600280 | DET | ATL | State Farm Arena | Atlanta, GA | 3 |
| https://www.nba.com/game/okc-vs-mia-0022600281 | OKC | MIA | Kaseya Center | Miami, FL | 3 |
| https://www.nba.com/game/orl-vs-was-0022600282 | ORL | WAS | Capital One Arena | Washington, DC | 3 |

## Coverage, stated exactly

Clubs whose home venue appears in this read **and** was missing from the in-repo captures:
ATL (State Farm Arena, game 0022600043), BOS (TD Garden, games 0022600240 / 0022600245),
DET (Little Caesars Arena, game 0022600046), NYK (Madison Square Garden, game 0022600275).

Clubs with **no home game anywhere in this read or in the in-repo captures**:

| Team | Status | Consequence |
|---|---|---|
| CHA | unverified home venue | CHA's home venue is not published anywhere in this repository. Every travel row that would need it is blank and flagged; no coordinate is guessed. |
| GSW | unverified home venue | same |
| POR | unverified home venue | same |

No other gap: the remaining 27 clubs each have an official venue string, sourced from this read or
from the in-repo official captures, and the two sources agree character for character on every club
that appears in both (`scripts/travel_distance.py --check-venues` re-checks this on every build and
fails on a mismatch).

## What this read also caught, recorded rather than fixed here

The same page shows the **11/15 slate as it actually finished**, e.g. `ind-vs-phi-0022600236`
Final 124-131 and a live 4th-quarter scoreboard for the rest. Two things follow, and both are on the
review page rather than silently applied:

1. The published 11/15 picks were sealed before tip (the ledger chain verifies), so the settlement
   path can now be exercised against a real final — but only from **two agreeing official reads**.
   This read is one; the second is the official game book
   (`https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf`), which is not captured yet.
2. A slate the site still labels "upcoming" was already final at read time. That is a freshness
   fact, not an error in the model: the page was built from the 11:44Z capture and the games tipped
   after it. It is why the refresh job is scheduled rather than manual.

## Sources

- https://www.nba.com/schedule?date=2026-11-18 — chunks 0-3 of 8; every venue line above is copied
  from these chunks, and each row's game URL is the link the page itself prints.
- https://www.nba.com/schedule?date=2026-11-15 — the source of the repository's
  `data/live/slate_2026-11-15.json` capture, used for the disagreement check.
