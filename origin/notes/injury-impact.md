# Injury impact on rotation minutes and production

## Method

The official [NBA injury report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_15PM.pdf) gives a status, not a minutes number. To convert one
into the other:

1. Match the player by name against the official minutes table
   ([players/traditional](https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season&PerPage=100&SortColumn=MIN&SortDirection=DESC)), which holds the top 31 players by minutes.
2. Convert status to an availability weight: Out 0.00, Doubtful 0.25, Questionable 0.60,
   Probable 0.90, Available 1.00. **These weights are our assumption, not an official figure**,
   and they are flagged as such.
3. Minutes at risk = season MPG x (1 - weight). Team total = quantified minutes vacuum.
4. Production impact = season per-game production x (projected minutes / season minutes).

Players on an official report but **not** in the captured minutes table get a blank minutes cell
and an UNVERIFIED badge. Their minutes are not estimated.

## Team-level minutes vacuum

| Date | Team | Opponent | H/A | Listed | Out/Doubtful | Minutes vacuum | Uncaptured | Report |
|---|---|---|---|---|---|---|---|---|
| 2026-11-13 | IND | NYK | home | 5 | 3 | 33.0 | 4 | submitted |
| 2026-11-13 | NYK | IND | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-13 | ORL | MIL | home | 7 | 4 | 33.8 | 6 | submitted |
| 2026-11-13 | MIL | ORL | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-13 | MIA | CLE | home | 4 | 2 | 0.0 | 3 | submitted |
| 2026-11-13 | CLE | MIA | away | 5 | 5 | 0.0 | 5 | submitted |
| 2026-11-13 | CHI | ATL | home | 5 | 3 | 0.0 | 5 | submitted |
| 2026-11-13 | ATL | CHI | away | 8 | 5 | 0.0 | 8 | submitted |
| 2026-11-13 | NOP | MEM | home | 8 | 5 | 0.0 | 8 | submitted |
| 2026-11-13 | MEM | NOP | away | 6 | 6 | 0.0 | 6 | submitted |
| 2026-11-13 | HOU | UTA | home | 5 | 5 | 0.0 | 5 | submitted |
| 2026-11-13 | UTA | HOU | away | 6 | 6 | 0.0 | 6 | submitted |
| 2026-11-13 | SAS | GSW | home | 4 | 2 | 0.0 | 4 | submitted |
| 2026-11-13 | GSW | SAS | away | 6 | 5 | 26.3 | 5 | submitted |
| 2026-11-13 | SAC | POR | home | 6 | 6 | 0.0 | 6 | submitted |
| 2026-11-13 | POR | SAC | away | 4 | 4 | 0.0 | 4 | submitted |
| 2026-11-13 | LAC | OKC | home | 5 | 5 | 0.0 | 5 | submitted |
| 2026-11-13 | OKC | LAC | away | 7 | 5 | 0.0 | 7 | submitted |
| 2026-11-14 | NOP | DEN | home | 0 | 0 | 0.0 | 1 | **NOT YET SUBMITTED** |
| 2026-11-14 | DEN | NOP | away | 0 | 0 | 0.0 | 1 | **NOT YET SUBMITTED** |
| 2026-11-14 | CLE | DAL | home | 1 | 0 | 0.0 | 1 | submitted |
| 2026-11-14 | DAL | CLE | away | 5 | 3 | 0.0 | 5 | submitted |
| 2026-11-14 | MIA | DET | home | 0 | 0 | 0.0 | 1 | **NOT YET SUBMITTED** |
| 2026-11-14 | DET | MIA | away | 7 | 5 | 0.0 | 7 | submitted |
| 2026-11-14 | MEM | BKN | home | 0 | 0 | 0.0 | 1 | **NOT YET SUBMITTED** |
| 2026-11-14 | BKN | MEM | away | 6 | 4 | 0.0 | 6 | submitted |
| 2026-11-14 | MIN | CHI | home | 3 | 2 | 33.7 | 2 | submitted |
| 2026-11-14 | CHI | MIN | away | 0 | 0 | 0.0 | 1 | **NOT YET SUBMITTED** |
| 2026-11-15 | PHI | IND | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | IND | PHI | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | PHX | LAL | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | LAL | PHX | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | LAC | CHA | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | CHA | LAC | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | UTA | SAS | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | SAS | UTA | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | TOR | NYK | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | NYK | TOR | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | BOS | DAL | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | DAL | BOS | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | WAS | HOU | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | HOU | WAS | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | MIL | ATL | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | ATL | MIL | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | SAC | OKC | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-15 | OKC | SAC | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | BOS | ORL | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | ORL | BOS | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | WAS | MEM | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | MEM | WAS | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | CLE | CHI | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | CHI | CLE | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | MIA | HOU | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | HOU | MIA | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | BKN | PHI | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | PHI | BKN | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | NOP | GSW | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | GSW | NOP | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | MIN | POR | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | POR | MIN | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | DEN | PHX | home | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |
| 2026-11-16 | PHX | DEN | away | 0 | 0 | 0.0 | 0 | **NOT YET SUBMITTED** |

The vacuum figures are **floors, not totals**, because of the uncaptured players column.

## Player-level detail

| Date | Player | Team | Status | Reason (official) | Season MPG | Minutes at risk |
|---|---|---|---|---|---|---|
| 2026-11-13 | Johnny Furphy | IND | Out | Injury/Illness - Right ACL Repair/Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Tyrese Haliburton | IND | Out | Injury/Illness - Left Hamstring Strain | 33.0 | 33.0 |
| 2026-11-13 | T.J. McConnell | IND | Probable | Injury/Illness - Right Hamstring Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Aaron Nesmith | IND | Questionable | Injury/Illness - Right Knee Soreness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Ben Sheppard | IND | Out | Injury/Illness - Left Meniscus Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Paolo Banchero | ORL | Out | Injury/Illness - Right High Ankle Sprain | 33.8 | 33.8 |
| 2026-11-13 | Jamal Cain | ORL | Available | Injury/Illness - Left Shoulder Contusion | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Tristan da Silva | ORL | Available | Injury/Illness - Left Calf Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jonathan Isaac | ORL | Out | Injury/Illness - Left Knee Injury Management | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Izaiyah Nelson | ORL | Out | Injury/Illness - Left Ankle Injury Recovery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Noah Penda | ORL | Out | Injury/Illness - Right Partially Torn Hamstring | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jalen Suggs | ORL | Available | Injury/Illness - Right Knee Contusion/Bone Bruise | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Giannis Antetokounmpo | MIA | Available | Injury/Illness - Right Wrist Sprain | 32.6 | 0.0 |
| 2026-11-13 | Vladislav Goldin | MIA | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Pelle Larsson | MIA | Doubtful | Injury/Illness - Illness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Klay Thompson | MIA | Probable | Injury/Illness - Left Ankle Soreness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Khalifa Diop | CLE | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Sam Merrill | CLE | Out | Injury/Illness - Right Elbow Injury Management | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Evan Mobley | CLE | Out | Injury/Illness - Left Great Toe - Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Nae'Qwan Tomlin | CLE | Out | Injury/Illness - Low Back Stress Reaction | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Ernest Udeh Jr. | CLE | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Tobe Awaka | CHI | Out | Injury/Illness - Disc Irritation | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Norman Powell | CHI | Questionable | Injury/Illness - Low Back Spasms | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jaylin Sellers | CHI | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Dailyn Swain | CHI | Questionable | Injury/Illness - Right Disc Irritation | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Caleb Wilson | CHI | Out | Injury/Illness - Right Metacarpal Fracture | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | RayJ Dennis | ATL | Questionable | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Kingston Flemings | ATL | Questionable | Injury/Illness - Lumbar Spasm | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Keshon Gilbert | ATL | Out | Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Mouhamed Gueye | ATL | Out | Injury/Illness - Left Foot Fracture | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jock Landale | ATL | Available | Injury/Illness - Face Mask | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Asa Newell | ATL | Out | Injury/Illness - Left Great Toe Hyperextension | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Henri Veesaar | ATL | Out | Injury/Illness - Right ACL Tear | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jalen Wilson | ATL | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Malik Dia | NOP | Available | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Bennedict Mathurin | NOP | Questionable | Injury/Illness - Right Thumb Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Bryce McGowens | NOP | Out | Injury/Illness - Left Elbow Infection | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Yves Missi | NOP | Out | Injury/Illness - Left Knee Contusion / Bone Bruise | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Trey Murphy III | NOP | Out | Injury/Illness - Bilateral Patellar Tendinopathy | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Dejounte Murray | NOP | Out | Injury/Illness - Left Ankle Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jaron Pierre Jr. | NOP | Available | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Trendon Watford | NOP | Out | Injury/Illness - Right Ankle Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Zach Edey | MEM | Out | Injury/Illness - Left Ankle Injury Management | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Karim Lopez | MEM | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jahmai Mashack | MEM | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Scotty Pippen Jr. | MEM | Out | Injury/Illness - Lumbar Disc Herniation | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Quinten Post | MEM | Out | Injury/Illness - Concussion Protocol | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Richie Saunders | MEM | Out | Injury/Illness - Right Knee Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Steven Adams | HOU | Out | Injury/Illness - Right Soleus Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Clint Capela | HOU | Out | Injury/Illness - Right Ankle Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Quadir Copeland | HOU | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Julian Phillips | HOU | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Marcus Smart | HOU | Out | League Suspension | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Trey Alexander | UTA | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Kobe Bufkin | UTA | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Harrison Ingram | UTA | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jaren Jackson Jr. | UTA | Out | Injury/Illness - Right MCL Tear | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Lauri Markkanen | UTA | Out | Injury/Illness - Right Hand Fracture | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jusuf Nurkic | UTA | Out | Injury/Illness - Right 2nd Plantar Plate Tear | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | De'Aaron Fox | SAS | Questionable | Injury/Illness - Left Hip Soreness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Tobias Harris | SAS | Out | Injury/Illness - Left Calf Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jayden Quaintance | SAS | Out | Injury/Illness - Right Knee Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Devin Vassell | SAS | Questionable | Injury/Illness - Left Adductor Tightness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Charles Bassey | GSW | Probable | Injury/Illness - Left Toe Soreness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jimmy Butler III | GSW | Out | Injury/Illness - Right ACL Repair / Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Stephen Curry | GSW | Out | Injury/Illness - Right Oblique Tear | 26.3 | 26.3 |
| 2026-11-13 | Moses Moody | GSW | Out | Injury/Illness - Left Patellar Tendon Repair / Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Kristaps Porzingis | GSW | Out | Not With Team | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Brandon Williams | GSW | Out | Injury/Illness - Left Hamstring Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Precious Achiuwa | SAC | Out | Injury/Illness - Left Ankle Soreness | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Alex Karaban | SAC | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jonathan Mogbo | SAC | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Sean Pedulla | SAC | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Maxime Raynaud | SAC | Out | Injury/Illness - Right Patella Subluxation | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Ben Simmons | SAC | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Vit Krejci | POR | Out | Injury/Illness - Left Ankle Fracture | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Ja Morant | POR | Out | Injury/Illness - Left Hamstring Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Shaedon Sharpe | POR | Out | Injury/Illness - Right Meniscus Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Chris Youngblood | POR | Out | Injury/Illness - Right Bone Bruise | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Bradley Beal | LAC | Out | Injury/Illness - Right Knee Injury Management | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Brandon Ingram | LAC | Out | Injury/Illness - Right Heel Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Nick Martinelli | LAC | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jordan Miller | LAC | Out | Injury/Illness - Left Rotator Cuff Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Yanic Konan Niederhauser | LAC | Out | Injury/Illness - Right Lisfranc Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Chet Holmgren | OKC | Out | Injury/Illness - Right Knee/ Injury Recovery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Ajay Mitchell | OKC | Questionable | Injury/Illness - Left Ankle Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Thomas Sorber | OKC | Out | Injury/Illness - Right Knee Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Nikola Topic | OKC | Available | - | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Cason Wallace | OKC | Out | Injury/Illness - Left Shoulder Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jalen Williams | OKC | Out | Injury/Illness - Left Ankle Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-13 | Jaylin Williams | OKC | Out | Injury/Illness - Low Back Spasms | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Caleb Martin | CLE | Available | Injury/Illness - Right Thumb Splint | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Tarik Biberovic | DAL | Out | Injury/Illness - Right Heel Bursitis | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Max Christie | DAL | Questionable | Injury/Illness - Left Ankle Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Sergio de Larrea | DAL | Out | Injury/Illness - Right Knee Sprain | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Morez Johnson Jr. | DAL | Probable | Injury/Illness - Left Shin / Tibia Contusion | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Dereck Lively II | DAL | Out | Injury/Illness - Right Foot Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Jalen Duren | DET | Out | Injury/Illness - Right Hamstring Strain | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Elijah Harkless | DET | Questionable | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Isaiah Joe | DET | Out | Injury/Illness - Right Hip Contusion | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Isaac Jones | DET | Questionable | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Chaz Lanier | DET | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Ebuka Okorie | DET | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Ugonna Onyenso | DET | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Tyler Bilodeau | BKN | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Mikel Brown Jr. | BKN | Questionable | Injury/Illness - Illness | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Joshua Jefferson | BKN | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Grant Nelson | BKN | Out | G League - Two-Way | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Ben Saraf | BKN | Out | G League - On Assignment | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Nolan Traore | BKN | Probable | Injury/Illness - Right Calf Tightness / Soreness | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Joan Beringer | MIN | Available | Injury/Illness - Face Mask | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Donte DiVincenzo | MIN | Out | Injury/Illness - Right Achilles Tendon Repair / Surgery | *blank — UNVERIFIED* | *blank* |
| 2026-11-14 | Anthony Edwards | MIN | Out | Injury/Illness - Right Knee Arthroscopy | 33.7 | 33.7 |

## Contradictions found on official pages

- **Anthony Edwards (MIN)** is listed Out for 14 Nov (right knee arthroscopy), yet the official
  game pages show 45 points on 21 Oct and 47 on 26 Oct. Either the injury is new or the report
  is stale; re-check on game day before using the Minnesota line.
- **5 team reports read "NOT YET SUBMITTED"** on the 14 Nov pages. Those teams carry zero
  quantified injury adjustment, which is a data gap rather than an assertion of good health.

