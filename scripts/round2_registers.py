#!/usr/bin/env python3
"""The four hand-verified registers for the 1:00 PM ET round (session arena/fbd2484b-nba3).

Every string in here is a claim. Each claim names the file or official document that supports
it, and tests/test_round2_2026_11_16.py asserts that the named artefact really does contain the
thing the claim says it contains. So a register entry cannot drift away from the artefact.

Nothing in this file is generated. It is written once, checked against the artefacts, and then
frozen; if an artefact changes, the test fails and the register has to be re-read.
"""

SESSION = "arena/fbd2484b-nba3"

# ----------------------------------------------------------------------------------------------
# REQUIREMENTS - one row per requirement in the brief, verdict read from the artefact named.
# verdict values: met | met_partly | blocked | not_met
# ----------------------------------------------------------------------------------------------

REQUIREMENTS = [
    # (id, requirement, verdict, evidence, artefact, contains, source_url)
    ("R01", "Scheduled job refreshes official schedule, standings, team statistics and injury report per rolling slate",
     "met", "scheduled job fetches all four document classes and gates the rebuild on freshness",
     ".github/workflows/refresh.yml", "refresh_official.py",
     "https://official.nba.com/nba-injury-report-2026-27-season/"),
    ("R02", "Rebuild only after freshness and provenance gates pass",
     "met", "18 gates with explicit build / row / advisory scope; rebuild_allowed is False if any build-scope gate fails",
     "data/rounds/2026-11-16-1300PM/gates.json", '"rebuild_allowed": true',
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("R03", "Official per-game result feed: one row per game with date, teams, final score, quarter scores",
     "blocked", "no 2026-11-16 game has been played at capture time, so no result row exists for it; the 11/15 feed exists and is unchanged by this round",
     "data/rounds/2026-11-16/gates.json", '"F3_game_day_complete"',
     "https://www.nba.com/games?date=2026-11-16"),
    ("R04", "Settle only after final scores are verified",
     "met", "the prior round withholds ATL@MIL rather than repairing its quarter arithmetic; unchanged here",
     "data/rounds/2026-11-16/flags.csv", "ATL @ MIL",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_ATLMIL.pdf"),
    ("R05", "Store every injury PDF with a timestamp and diff consecutive reports to detect status changes",
     "met", "three same-day filings (09:15 AM, 01:00 PM, 01:15 PM ET) are stored verbatim with sha256 and retrieval stamps, and each consecutive pair is diffed: 4 rows moved in the first hop, 1 addition and 1 spelling change in the second",
     "data/rounds/2026-11-16-1300PM/injury_chain.json", '"current_stamp"',
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf"),
    ("R06", "Pre-register a strategy file before its first bet (signal, thresholds, universe, settlement rule)",
     "met_partly", "three pre-registration files exist and are frozen before any bet; no strategy has been funded, so the mechanism is implemented and unused",
     "prereg/S2_ESTIMATOR_DISAGREEMENT.json", "settlement",
     "https://www.nba.com/stats/help/glossary"),
    ("R07", "Tamper-evident ledger: hash each published pick, publish the hash before tip, verify after settlement",
     "met_partly", "11 PUBLISH entries with recomputable prev_hash/entry_hash/pick_sha256 chains; nothing settled this round because no 11/16 game is final",
     "ledger/ledger.jsonl", '"kind": "PUBLISH"',
     "https://www.nba.com/schedule?date=2026-11-15"),
    ("R08", "Two surfaces: projection (safe to publish now) vs bet (gated), never mixed",
     "met", "separate output trees with a gate that refuses to write a bet row without a passing strategy",
     "projection/index.html", "projection",
     "https://www.nba.com/stats/teams/advanced"),
    ("R09", "Two independent estimators; publish their disagreement as the primary signal",
     "met", "estimator A is official net rating; estimator B is rebuilt from shooting/turnover/rebounding and shares no input with A; both are centred on their own league mean; the gap is the headline",
     "data/rounds/2026-11-16-1300PM/model.json", '"disagreement_median"',
     "https://www.nba.com/stats/teams/advanced"),
    ("R10", "Pin home-court advantage to the measured home-win rate instead of fitting it",
     "met", "102 home wins in 196 home decisions = 0.520408, computed from the official HOME column of all 30 clubs; no parameter estimated",
     "data/rounds/2026-11-16-1300PM/home_court.json", '"home_win_rate": 0.520408',
     "https://www.nba.com/standings"),
    ("R11", "Report luck as a z-score per team and refuse a strategy leaning on a team outside the noise band",
     "met", "z published per club; the largest absolute z in the league is 1.66, so no club is outside +/-2 and no exclusion is triggered this round",
     "data/rounds/2026-11-16-1300PM/luck.json", '"in_noise_band"',
     "https://www.nba.com/standings"),
    ("R12", "Rest, back-to-back and 3-in-4 from the official schedule, plus travel distance from a sourced arena table",
     "met_partly", "rest/B2B/3-in-4 are computable from the captured 25-game schedule; travel distance exists but its coordinates come from Wikipedia, not an official NBA source (flagged)",
     "data/live/rest_travel.json", "travel",
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("R13", "Model minutes redistribution explicitly: top-8 minute shares and replacement shares when a player is out",
     "blocked", "needs per-player minutes for the clubs on this slate; the official injury report prints status only. Reported as BLOCKED with the unblocking step, not estimated",
     "data/rounds/2026-11-16-1300PM/consequences.json", '"status": "BLOCKED"',
     "https://www.nba.com/stats/players/traditional"),
    ("R14", "Price every parlay with the measured rho and print the naive product beside it",
     "blocked", "no rho has been measured for the 11/16 slate, so no parlays are priced; the mechanism and the naive-product column already exist from the prior round",
     "data/correlation.json", '"basis": "MEASURED"',
     "https://www.nba.com/stats/teams/opponent"),
    ("R15", "Rotation availability as its own column on the picks page",
     "met", "availability is a column on the projection picks page, with NOT SUBMITTED as an explicit value rather than an empty cell",
     "projection/index.html", "availability",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf"),
    ("R16", "Market-anchored prior: blend model with closing line weighted by measured out-of-sample log-loss",
     "blocked", "no licensed closing-line feed is connected; the blend field is null and flagged, never guessed",
     "data/app/closing_lines.json", '"feed_status": "not connected"',
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("R17", "Model the total as possessions x points-per-possession, not the average of team scoring averages",
     "met_partly", "the total is possessions x ppp; but on season-wide inputs the official off rating is exactly 100*points/possessions, so the two coincide to within 0.1 points. Disclosed and pinned by gate I10",
     "data/rounds/2026-11-16-1300PM/game_flow.json", '"total_from_poss_x_ppp"',
     "https://www.nba.com/stats/teams/advanced"),
    ("R18", "Show the injury-report revision time and retrieval time in the Injuries page banner",
     "met", "this round's page banner shows the 1:00 PM ET revision and every document's retrieval stamp",
     "data/rounds/2026-11-16-1300PM/refresh.json", '"retrieved_utc"',
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf"),
    ("R19", "Settle the sealed ledger from official finals as soon as each game day ends, keeping the settlement stamp visible",
     "blocked", "the 11/16 game day has not ended at capture time; nothing from 11/16 can be settled yet",
     "ledger/ledger.jsonl", '"prev_hash"',
     "https://www.nba.com/games?date=2026-11-16"),
    ("R20", "Re-read the three official team-stat pages (traditional, opponent, advanced) and re-cut the model inputs",
     "met", "all three pages re-read in full for all 30 clubs; both estimators and every total are re-cut from this capture, and four reconciliation gates check the arithmetic",
     "data/rounds/2026-11-16-1300PM/team_stats.json", '"reconciliation"',
     "https://www.nba.com/stats/teams/traditional"),
    ("R21", "Capture per-player game logs (minutes, points, rebounds, assists, opponent) at least for players on an injury report",
     "blocked", "99 reconciled player rows exist for 11/14 gamebooks only; none of the 11/16 slate's players has a captured log, so the requirement is not met for this slate",
     "data/live/player_game_logs.json", '"printed_rows": 107',
     "https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf"),
    ("R22", "Originate own NBA lines; research signals; single bets, parlays and player prop combos",
     "met_partly", "25 originated lines for 11/16-11/18 from the prior round; 0 published strategies because no club has the four captured games the gate requires; player props blocked on R21",
     "data/rounds/2026-11-16-1300PM/gates.json", '"rebuild_allowed"',
     "https://www.nba.com/stats/teams/advanced"),
    ("R23", "Validation gates; correlation values; remove luck; selectively skill-based strategies",
     "met_partly", "gates run and refuse; luck z published; correlations exist for 86 games from a general-reference schedule source, not an official NBA feed (flagged)",
     "data/correlation.json", '"n": 86',
     "https://www.nba.com/standings"),
    ("R24", "Generate picks for every upcoming slate up to three days ahead using originated lines",
     "met_partly", "the slate covers exactly today..today+2 (25 games) and lines exist for it; picks are withheld because the strategy gate has not passed",
     "data/rounds/2026-11-16-1300PM/schedule.json", '"2026-11-18"',
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("R25", "Track how injuries could affect rotation minutes and production, and provide game flow analysis",
     "met_partly", "per-club availability bands, severity points and a game-by-game flow table with both clubs' filing state are published; minute-level redistribution is blocked (R13)",
     "data/rounds/2026-11-16-1300PM/game_flow.json", '"availability_source_url"',
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf"),
    ("R26", "Create an executive summary outlining important details",
     "met", "a one-page summary leads this round's site with the filing, the changes and the blockers",
     "round2/summary.html", "Executive summary",
     "https://official.nba.com/nba-injury-report-2026-27-season/"),
    ("R27", "Suggestions section, reviewable, choose the path before implementing",
     "met", "eleven suggestions, none implemented, each with the trade-off and what it would take",
     "round2/suggestions.html", "Awaiting a decision",
     "https://www.nba.com/stats/teams/advanced"),
    ("R28", "Clear Q&A register of what is known and unknown, with suggestions to discover missing information",
     "met", "fourteen questions, each marked known / unknown / discoverable, with the document that would answer it",
     "round2/questions.html", "Discoverable",
     "https://official.nba.com/nba-injury-report-2026-27-season/"),
    ("R29", "No manual input from the user; work autonomously start to finish",
     "met", "this session ran end to end without a question to the user",
     "COORDINATION.md", "fbd2484b",
     "https://github.com/wingbangboozle1-lang/NBA3"),
    ("R30", "GitHub Pages live site: clean landing page, category subpages, table format, analysis",
     "met", "the round publishes its own tree with a landing page and category subpages, every table row sourced",
     "round2/index.html", "projection surface",
     "https://wingbangboozle1-lang.github.io/NBA3/round2/"),
    ("R31", "Parallel-session protocol: read and claim in COORDINATION.md, non-overlapping scopes, PR and merge",
     "met", "claim committed and pushed before any work; scope listed; no file owned by another session edited",
     "COORDINATION.md", "fbd2484b",
     "https://github.com/wingbangboozle1-lang/NBA3/blob/main/COORDINATION.md"),
    ("R32", "PR and merge: integrate, re-verify, confirm links, publish to Pages",
     "met", "see the PR and deployment record in COORDINATION.md",
     "COORDINATION.md", "fbd2484b",
     "https://github.com/wingbangboozle1-lang/NBA3/pulls"),
    ("R33", "No hallucinations: verify line by line against official sources and provide links",
     "met", "every published value names its official document; 18 gates check the arithmetic; values the documents do not print are null and flagged",
     "data/rounds/2026-11-16-1300PM/refresh.json", '"sha256"',
     "https://www.nba.com/stats/teams/traditional"),
]

# ----------------------------------------------------------------------------------------------
# QUESTIONS - what has to be answered before a decision can reasonably be made.
# `state` is one of: known | unknown | discoverable
# ----------------------------------------------------------------------------------------------

QUESTIONS = [
    ("Q01", "Is the current filing the last one before tonight's tips?",
     "unknown",
     "No. The index updates every 15 minutes and had already advanced once during this session "
     "(52 → 53 filings for the day). This page states what the 1:15 PM ET filing says and no more.",
     "Re-fetch the index immediately before any bet decision; the chain on the Injuries page is "
     "the record of how fast it moves.",
     "https://official.nba.com/nba-injury-report-2026-27-season/"),
    ("Q02", "What are the closing lines for tonight's games?",
     "unknown",
     "No licensed closing-line feed is connected. Without it the market-anchored prior (R16) "
     "cannot be computed at all, and no bet can be shown to have edge.",
     "A licensed odds feed. Nothing in the official NBA sources prints prices.",
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("Q03", "How many minutes does each affected player actually play, and who replaces them?",
     "discoverable",
     "The official injury report prints participation status, not minutes. Player-level game logs "
     "are published by the NBA per gamebook, and the repo already parses that format for 11/14.",
     "Capture the official gamebooks for the clubs on this slate and parse per-player minutes.",
     "https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf"),
    ("Q04", "Which clubs still have not submitted at tip time, and does that change anything?",
     "discoverable",
     "11 clubs had not submitted at 1:15 PM ET, down from 15 at 09:15 AM and 12 at 1:00 PM: "
     "Boston, Houston, Philadelphia and Washington all filed during the afternoon. Filing is "
     "required between 11 a.m. and 1 p.m. local, so the rest should follow. A club that never "
     "files is a different situation from a club that filed 'nobody out'.",
     "Read the last filing before each tip; the index keeps every version.",
     "https://official.nba.com/nba-injury-report-2026-27-season/"),
    ("Q05", "Is the NBA's own data licence compatible with a wagering product?",
     "unknown",
     "NBA.com Terms of Use restrict commercial use of NBA statistics. Whether an originated-line "
     "product is permitted is a legal question this repo cannot resolve, and it governs the whole "
     "bet surface.",
     "Legal advice. This is a standing blocker on publishing any bet.",
     "https://www.nba.com/termsofuse"),
    ("Q06", "How large is the true home-court effect beyond the 102/196 measured here?",
     "known",
     "0.5204 home-win rate on 196 decisions, z = 0.57 against a 0.5 null. The sample is too small "
     "to distinguish a real small effect from noise, and the round says so rather than claiming one.",
     "Nothing further is needed for this round; the number is pinned to what was measured.",
     "https://www.nba.com/standings"),
    ("Q07", "Does estimator B's declared constant (second-chance points per offensive rebound) matter?",
     "known",
     "It shifts the level, not the ranking, and both estimators are centred on their own league "
     "mean before the disagreement is computed, so the constant cancels out of the published gap.",
     "Nothing; the treatment is disclosed on the Methodology page.",
     "https://www.nba.com/stats/teams/advanced"),
    ("Q08", "Are the correlation values measured from an official source?",
     "unknown",
     "The existing correlations (n=86) come from a general-reference schedule source, not from an "
     "official NBA feed. They are marked and must not be presented as official.",
     "Recapture the same correlations from official gamebooks.",
     "https://www.nba.com/stats/teams/opponent"),
    ("Q09", "Do the three official team-stat pages describe the same games as the standings?",
     "known",
     "Yes: every club's W+L on the traditional page equals its standings games played, and the "
     "league total W equals total L (197 each). Gate I1 and I2 check this on every build.",
     "Nothing; the reconciliation is automated.",
     "https://www.nba.com/stats/teams/traditional"),
    ("Q10", "What is the correct total for a game where the two clubs play at different paces?",
     "known",
     "Both clubs share one possession count in a game, so the game's possessions are the mean of "
     "the two paces. On season-wide inputs this reproduces the sum of scoring averages exactly; "
     "it diverges only with opponent-specific rates.",
     "Opponent-specific points per possession, which needs the per-game logs in Q03.",
     "https://www.nba.com/stats/teams/advanced"),
    ("Q11", "Can a strategy be published before four captured games per club exist?",
     "known",
     "No. The prior round's gate requires four captured games per club and none has them, so 0 of "
     "25 originated lines is publishable. This is the gate working, not a fault.",
     "More captured game days; nothing else.",
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("Q12", "Is travel distance usable as a model input?",
     "unknown",
     "Arena coordinates are sourced from a general-reference article, not the NBA, and two rows "
     "are blank. Distance is therefore indicative only.",
     "Official arena coordinates, or an official document stating them.",
     "https://www.nba.com/schedule?date=2026-11-16"),
    ("Q13", "Which of the two NBA result documents governs when they disagree?",
     "unknown",
     "The ATL@MIL gamebook prints quarter 3 as both 37 and 27. The repo withholds the row. There "
     "is no stated precedence rule between the period table and the recap line.",
     "An official statement of precedence, or a second official document for that game.",
     "https://statsdmz.nba.com/pdfs/20261115/20261115_ATLMIL.pdf"),
    ("Q14", "Does the 1:00 PM filing change any club's availability enough to move a line?",
     "unknown",
     "Three clubs filed for the first time between 09:15 and 1:00 PM (Houston, Philadelphia, "
     "Washington), naming 18 players between them. Whether that moves a price cannot be known "
     "without prices (Q02).",
     "A closing-line feed, then compare the model line with and without those rows.",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf"),
]

# ----------------------------------------------------------------------------------------------
# SUGGESTIONS - changes to the site that would improve decision making. None implemented.
# ----------------------------------------------------------------------------------------------

SUGGESTIONS = [
    ("S01", "Put the filing age next to every number that depends on it",
     "A reader cannot tell whether a projection is 3 minutes or 9 hours old. Showing 'as of the "
     "13:00 ET filing, 4h 12m before tip' beside each affected club makes staleness visible "
     "instead of inferred.",
     "Add one derived column. No new data required.", "high"),
    ("S02", "Show a two-column 'what changed since you last looked' block",
     "The diff exists but is buried in a table. A two-column block - was / now - with only the "
     "rows that moved is what a reader actually needs before a tip.",
     "Reorder an existing page. No new data required.", "high"),
    ("S03", "Replace the single confidence word with the two estimators side by side on every row",
     "A reader still sees one rating on the picks row and has to open another page to see the "
     "disagreement. Printing A, B and the gap on the same row removes a click.",
     "Column change on an existing table.", "high"),
    ("S04", "Mark clubs that have not filed in the same visual language as clubs with nobody out",
     "Today a 'not submitted' club and a 'nobody out' club can look alike at a glance. They are "
     "opposites: one is known, one is unknown.",
     "Style change; the data already distinguishes them.", "high"),
    ("S05", "Publish a standing 'blocked' panel with the exact document that would unblock each item",
     "Nine requirements are blocked. Each needs one specific thing. Listing them with the "
     "document name turns a dead end into a to-do list.",
     "Static page generated from the requirements register.", "medium"),
    ("S06", "Show the arithmetic for the home-court rate directly on the page",
     "102/196 is a claim until a reader can see it counted from the HOME column. Printing the "
     "sum makes the pinning verifiable without trusting the build.",
     "One line of derived text. No new data.", "medium"),
    ("S07", "Give each gate a permanent URL fragment",
     "When a gate fails, the conversation is 'which one' and then a screenshot. A fragment per "
     "gate lets a failure be linked directly.",
     "Anchor ids on the gates page.", "medium"),
    ("S08", "Separate 'unknown' from 'zero' everywhere a count appears",
     "A club with 0 rows because it filed nothing is not a club with 0 players out. The current "
     "table can be misread this way even though the underlying data is right.",
     "Style and wording on existing tables.", "high"),
    ("S09", "Add a per-club filing timeline for today",
     "Status changes are more informative as a sequence than as a diff. Which clubs filed when, "
     "and who moved, is a timeline.",
     "Derived from the archived filings already stored.", "medium"),
    ("S10", "Show which columns came from which official page, inline",
     "Every row cites a source, but not which page each column came from. Inline column-level "
     "attribution would make the reconciliation checkable by eye.",
     "Column header change plus a legend.", "low"),
    ("S11", "Refuse to render a totals number without its identity disclosure",
     "The totals formula and the naive sum agree on season-wide inputs. A reader who does not "
     "know that will over-trust the formula.",
     "Bind the disclosure to the cell rather than the page.", "medium"),
]

# ----------------------------------------------------------------------------------------------
# FLAGS - irregularities. Each names the document that shows it.
# ----------------------------------------------------------------------------------------------

FLAGS = [
    ("F13-01", "The published 11/16 snapshot was behind the official index",
     "main published the 09:15 AM ET filing while the official index already listed later ones. "
     "Nothing was wrong with the snapshot; it was simply no longer the newest official document. "
     "The index then advanced once more while this round was being built, from 52 filings for the "
     "day to 53.",
     "fixed this round: the newer filings are captured, chained and published "
     "(09:15 AM -> 01:00 PM -> 01:15 PM ET), each hop diffed by the same rule",
     "https://official.nba.com/nba-injury-report-2026-27-season/", "resolved"),
    ("F13-02", "The 1:00 PM PDF's page break falls inside a row",
     "Chunk 0 ends mid-row at 'PHX@DEN' and chunk 1 begins 'Denver Nuggets | Whitmore, Cam'. A "
     "parser that trusts line boundaries drops or duplicates that player.",
     "the row is spliced, counted (1) and pinned by a test; 2 non-row spill cells are dropped and counted",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf", "recorded"),
    ("F13-03", "Two players' status cells are blank in the official PDF",
     "Jimmy Butler III prints a reason but no status. Stephen Curry prints 'Out' with no reason. "
     "These are left null and counted, not back-filled from the earlier filing.",
     "1 row has no status and is excluded from status counts; the reason-only row is kept",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf", "recorded"),
    ("F13-04", "Twelve clubs had not submitted at 1:00 PM ET",
     "Boston, Charlotte, Detroit, LA Clippers, LA Lakers, Minnesota, New York, Phoenix, Portland, "
     "San Antonio, Toronto and Utah printed 'NOT YET SUBMITTED'. Their absence from the injury "
     "rows means unknown, not zero.",
     "published as an explicit value on every affected club row and game row",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_00PM.pdf", "withheld"),
    ("F13-05", "The official standings print two clubs at seed 1 in the West",
     "San Antonio and the Lakers are both 12-2 and both numbered 1; no club is numbered 2. The "
     "printed seeds are copied exactly and not renumbered here.",
     "cosmetic; seeding is not used by any model in this round",
     "https://www.nba.com/standings", "recorded"),
    ("F13-06", "The totals formula cannot differ from the naive sum on season-wide inputs",
     "Because the official off rating is exactly 100 * points / possessions, possessions x "
     "points-per-possession reproduces the sum of scoring averages to within 0.1 points. The "
     "formula is still the right object, but it is not yet doing work.",
     "disclosed beside every total and pinned by gate I10 rather than hidden",
     "https://www.nba.com/stats/teams/advanced", "recorded"),
    ("F13-07", "Estimator B contains one constant that the official pages cannot supply",
     "Second-chance points per offensive rebound is not printed by any captured document, so "
     "0.30 is declared. It shifts B's level, which is why both estimators are centred before the "
     "gap is taken.",
     "the constant is published on the Methodology page and is cancelled by centring",
     "https://www.nba.com/stats/teams/advanced", "recorded"),
    ("F13-08", "The home-court measurement is small and the sample is one month",
     "102/196 gives z = 0.57 against a 0.5 null. The brief requires HCA pinned to the measured "
     "rate, so it is, but the measurement cannot yet separate a small real effect from noise.",
     "published with its denominator and z; no claim of significance is made",
     "https://www.nba.com/standings", "needs review"),
    ("F13-09", "The existing correlation values are not from an official NBA source",
     "The 86-game correlations used elsewhere in the site are built on a general-reference "
     "schedule source. They are not suitable for pricing parlays as if official.",
     "flagged; no parlay is priced this round",
     "https://www.nba.com/stats/teams/opponent", "needs review"),
    ("F13-10", "Arena coordinates are not an NBA-published dataset",
     "Travel distance depends on coordinates taken from a general-reference article, with two "
     "rows blank. Any distance figure is indicative only.",
     "flagged; travel is not used as a model input this round",
     "https://www.nba.com/schedule?date=2026-11-16", "needs review"),
    ("F13-11", "The 11/16 slate cannot be settled from anything captured so far",
     "No 2026-11-16 game is final at capture time, so no 11/16 pick can be settled and the ledger "
     "correctly has no 11/16 settlement entry.",
     "nothing to fix; it is a statement about the time of capture",
     "https://www.nba.com/games?date=2026-11-16", "open"),
    ("F13-12", "No per-player minutes exist for any player on this slate",
     "R13 and R21 need per-player logs. The repo holds 99 reconciled rows for 11/14 only. The "
     "injury-to-minutes chain therefore stops at status, and says so.",
     "reported BLOCKED with the exact unblocking step rather than estimated",
     "https://www.nba.com/stats/players/traditional", "open"),
    ("F13-13", "Raw HTTP to the official hosts is blocked in this environment",
     "curl to official.nba.com and ak-static.cms.nba.com fails at TLS from the sandbox. Every "
     "official value in this round was therefore read with the Arena fetch tool, whose retrieval "
     "stamp is recorded per document.",
     "provenance records the retrieval method and time for every document",
     "https://official.nba.com/nba-injury-report-2026-27-season/", "recorded"),
    ("F13-15", "The index advanced while this round was in progress",
     "The index listed 52 filings when the 1:00 PM PDF was captured and 53 when it was re-read "
     "minutes later, the extra one being 1:15 PM ET. A capture is only ever newest at its own "
     "read time.",
     "captured the 1:15 PM filing as well and made it the current one; the advisory gate now "
     "records that no newer filing was listed at the final read, and states that the index, not "
     "this page, remains the authority",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf", "resolved"),
    ("F13-16", "A club printed a player with no matchup cell",
     "At 1:15 PM Boston's row reads '|  |  | Boston Celtics | Queta, Neemias | Questionable | Rest |'. "
     "The club sits in the matchup position and the matchup itself is blank, so the game cannot be "
     "read from that row alone.",
     "resolved from the official schedule (Boston has exactly one game on 11/16, ORL@BOS), recorded "
     "on the row as recovered, and checked by gate I5",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf", "resolved"),
    ("F13-17", "A player's printed name changed between two filings",
     "New Orleans printed 'Mathurin, Bennedict' at 1:00 PM and 'Mathurin, Benedict' at 1:15 PM, one "
     "edit apart, Out both times. Read naively this is one player leaving and another arriving.",
     "detected as a spelling change by name-distance within the same club and game, and reported in "
     "its own category rather than as an addition plus a removal",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_01_15PM.pdf", "resolved"),
    ("F13-14", "An earlier parser draft mis-filed five Brooklyn Nets rows",
     "The 09:15 AM transcript's page break put the Nets block under HOU@MIA. A parser that "
     "inherits the previous matchup assigned them to the wrong game, which made the diff show "
     "them as both added and removed.",
     "fixed: matchup is never inherited across a page break; it is resolved from the official schedule and gated (I5). The defect is published, not quietly repaired",
     "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_09_15AM.pdf", "resolved"),
]
