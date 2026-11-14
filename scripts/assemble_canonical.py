#!/usr/bin/env python3
"""Assemble the canonical dataset used by the NBA3 site.

Inputs (all already verified against official sources by earlier sessions or
by this session -- see data/app/official_*.json and docs/verification_log.md):

  data/app/official_slate_1114_1117.json              official schedule, 2026-11-14 read
  data/app/official_team_ratings_2026-11-14b.json     official team advanced stats
  data/app/official_injuries_2026-11-13_0745PM.json   official injury report PDF
  data/app/lab.json                                   session 8d3d0271 line-origination
                                                      and strategy-lab output
  data/app/official_team_ratings_2026-11-14.json     official team advanced stats
  data/app/official_injuries_2026-11-13_0730PM.json  official injury report PDF
  data/origin/model_output.json                       originated lines, backtest, gates
  data/picks/picks_2026-11-14_to_16.json              3-day pick window
  data/flags.csv, data/flags.json                     flags (two namespaces)
  data/questions.csv, data/questions.json             questions (two namespaces)
  data/suggestions.csv, data/suggestions.json         suggestions (two namespaces)
  data/sources.csv, data/sources.json                 source register (two namespaces)
  data/repo_review.csv, data/repo_review.json         repo review (two namespaces)
  data/requirements.csv                               brief requirement coverage
  data/gameflow.csv, data/gates.csv, data/strategies.csv

Output: data/app/canonical.json -- one file, one namespace, every row carrying
its source URL.  Run:  python3 scripts/assemble_canonical.py
"""
import csv
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
OUT = os.path.join(APP, "canonical.json")

BUILD_UTC = "2026-11-14T09:45Z"
SESSION = ("arena/25418e3f-nba3 (official refresh 2026-11-14: 183-game result log, newest "
           "injury report, post-slate team ratings, availability timeline) on top of "
           "arena/8d3d0271-nba3 (engine, gates, leaderboard)")
REPO_URL = "https://github.com/wingbangboozle1-lang/NBA3"
PAGES_DOCS = ("https://docs.github.com/en/pages/getting-started-with-github-pages/"
              "configuring-a-publishing-source-for-your-github-pages-site")
NIST_PROP = "https://www.itl.nist.gov/div898/handbook/prc/section2/prc24.htm"

# Non-official team abbreviations used by one earlier pipeline, mapped to the
# official NBA abbreviations used by nba.com/schedule.
ALIAS = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX", "GS": "GSW", "WSH": "WAS",
         "UTAH": "UTA", "NO": "NOP", "NY": "NYK", "LA": "LAC", "SA": "SAS"}

# Sources for the earlier sessions' items that were recorded without a link.
FLAG_FALLBACK = {
    "7C-F-03": ["https://www.nba.com/termsofuse"],
    "7C-F-06": ["https://www.nba.com/stats/players/boxscores"],
    "7C-F-14": [REPO_URL],
    "7C-F-15": [PAGES_DOCS],
}
QUESTION_FALLBACK = {
    "Q-07": ["https://kansspelautoriteit.nl/online-kansspel-aanbieden",
             "https://www.nba.com/termsofuse"],
    "Q-09": ["https://www.nba.com/stats/players/traditional"],
    "Q-10": [NIST_PROP],
    "Q-11": ["https://kansspelautoriteit.nl/belangrijkste-regels-voor-kansspelreclame"],
    "Q-12": ["https://www.nba.com/stats/players/boxscores"],
    "Q-14": [REPO_URL],
}
SUGGESTION_FALLBACK = {
    "SG-04": [NIST_PROP],
    "SG-05": ["https://www.nba.com/games?date="],
    "SG-07": [REPO_URL + "/actions"],
    "SG-08": [REPO_URL],
}


def jload(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def cload(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def blank(v):
    return v is None or str(v).strip() == ""


# ---------------------------------------------------------------- sources
def build_sources():
    """Merge the two source registers and add the pages read on 2026-11-14."""
    out = []
    n = 0

    def add(publisher, title, url, official_status, used_for, retrieval, retrieved,
            verification, limits, legacy=None):
        nonlocal n
        n += 1
        out.append({
            "id": f"SRC-{n:02d}", "publisher": publisher, "title": title, "url": url,
            "official_status": official_status, "used_for": used_for,
            "retrieval_method": retrieval, "retrieved_on": retrieved,
            "verification_result": verification, "limits_or_notes": limits,
            "legacy_ref": legacy or "",
        })

    for r in cload("data", "sources.csv"):
        add(r["publisher"], r["title"], r["url"], r["official_status"], r["used_for"],
            r["retrieval_method"], r["retrieved_on"], r["verification_result"],
            r["limits_or_notes"], r["source_id"])
    for r in jload("data", "sources.json"):
        add(r.get("publisher", ""), r["title"], r["url"], r.get("publisher", ""),
            r.get("checked", ""), "fetch_page", r.get("retrieved", ""),
            r.get("result", ""), r.get("limit", ""), r["id"])

    # Sources read by this integration session (2026-11-14).
    add("NBA (official)", "NBA Schedule — Week 4 (Nov 13-15) and Week 5 (Nov 16-22)",
        "https://www.nba.com/schedule?date=2026-11-14", "Official (NBA)",
        "Every game of the 2026-11-13 .. 2026-11-16 window: game id, tip time (ET), venue, city, competition label",
        "fetch_page, chunks 0-2 of 9", "2026-11-14",
        "Read. 31 games transcribed. Cross-checked against data/slates.csv (captured 2026-11-13): 31/31 agree on date, tip time, teams and game id.",
        "Tip times are as printed on the page (ET). Games can be rescheduled; re-read before publishing a new slate.")
    add("NBA (official)", "NBA Stats — Teams Advanced (Regular Season 2026-27)",
        "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
        "Official (NBA)", "GP, W, L, MIN, OffRtg, DefRtg, NetRtg, PACE for all 30 teams",
        "fetch_page, chunks 0-1 of 2", "2026-11-14",
        "Read. 30 teams transcribed. Cross-checked against data/origin/teams_advanced.csv: 210/210 field comparisons agree.",
        "Values change as games are played; this snapshot is dated 2026-11-14.")
    add("NBA (official)", "NBA official injury report PDF — 11/13/26 07:30 PM ET",
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf",
        "Official (NBA)", "Newest injury snapshot: 117 player rows + 5 team report statuses for 2026-11-13 and 2026-11-14",
        "fetch_page, chunks 0-1 of 2 (PDF text extraction)", "2026-11-14",
        "Read. Compared with the 11/13 05:15 PM snapshot stored in data/origin/injuries.csv: 9 status changes, Denver's report newly present.",
        "PDF text extraction drops some spaces inside reason text; spacing corroborated against the 05:15 PM report where the same player appears.")
    add("NBA (official)", "NBA Injury Report — 2026-27 season index",
        "https://official.nba.com/nba-injury-report-2026-27-season/", "Official (NBA)",
        "Confirms which reports exist; the 07:30 PM 11/13 report is the newest one listed",
        "fetch_page, chunks 0-1 of 2", "2026-11-14",
        "Read. The index lists 11/13 reports from 12:00 a.m. to 07:30 p.m. ET. No 11/14 report is listed yet.",
        "No report exists yet for the 2026-11-15 and 2026-11-16 games; teams report by 5 p.m. local time the day before a game.")
    # Sources read by the 2026-11-14 refresh (session arena/25418e3f-nba3).
    add("NBA (official)", "NBA Games & Scores — 2026-11-13 (final scoreboard + November calendar)",
        "https://www.nba.com/games?date=2026-11-13", "Official (NBA)",
        "The nine final scores of 2026-11-13 (game id, matchup, score, Final / Final-OT state, "
        "Cup group, post-game W-L per team) and the official game count printed under every date "
        "of the November 2026 calendar",
        "fetch_page, chunks 0-1 of 2", "2026-11-14",
        "Read. 9 games transcribed. Cross-checked three ways: the official GP column (30 teams, "
        "sum 366 = 2 x 183), the official W and L columns (183 and 183), and the 18 post-game "
        "records printed on the same scoreboard page. All three reconcile with the extended log.",
        "Read after all nine games had finished, so 'Final' is settled state, not a live score. "
        "The calendar counts games, it does not name them.")
    add("NBA (official)", "NBA Stats — Teams Advanced (Regular Season 2026-27), re-read after the 11/13 slate",
        "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
        "Official (NBA)", "GP, W, L, MIN, OffRtg, DefRtg, NetRtg, PACE for all 30 teams, post-slate",
        "fetch_page, chunks 0-1 of 2", "2026-11-14",
        "Read. Compared with the snapshot stored by the previous session: 18 of 30 teams gained a "
        "game, and those 18 are exactly the 18 teams that played on 11/13, which is what shows the "
        "stored snapshot had been read mid-slate. 123 of the 240 stored fields differ.",
        "A rolling snapshot; any page read during a live slate is stale for the teams playing.")
    add("NBA (official)", "NBA official injury report PDF — 11/14/26 04:15 AM ET",
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf",
        "Official (NBA)",
        "Newest report at read time: 31 rows for the 2026-11-14 slate and 18 team rows for "
        "2026-11-15, every one of the 11/15 rows reading NOT YET SUBMITTED",
        "fetch_page, chunk 0 of 1 (PDF text extraction, two printed pages)", "2026-11-14",
        "Read. 49 rows. Compared row for row with the 11/13 07:45 PM ET report on the 2026-11-14 "
        "slate: 31 rows in common, 0 status changes, 0 rows added or dropped.",
        "Prints no rows at all for 2026-11-16 or 2026-11-17: those dates are outside every "
        "published report, which is not the same as nobody being out.")
    add("NBA (official)", "NBA Injury Report — 2026-27 season index (filing rule and report list)",
        "https://official.nba.com/nba-injury-report-2026-27-season/", "Official (NBA)",
        "The filing rule quoted verbatim on the Report-availability page (5 p.m. local the day "
        "before; 1 p.m. local on game day for the second game of a back-to-back) and which "
        "timestamped reports exist",
        "fetch_page", "2026-11-14",
        "Read. Index lists 11/14 reports from 12:00 a.m. to 04:15 a.m. ET; 04:15 a.m. is the "
        "newest, and it is the file captured above.",
        "The index lists reports by publication time; it does not state when each team's "
        "deadline falls. That is derived from the rule text and the official schedule.")
    add("GitHub (repository API)", "wingbangboozle1-lang/NBA3 — repository, Pages and PR facts",
        "https://github.com/wingbangboozle1-lang/NBA3", "Platform (GitHub)",
        "Repository review: Pages build type and source, branches, pull requests, licences",
        "gh api (authenticated)", "2026-11-14",
        "Verified against API output at retrieval time.",
        "Repository facts change; re-check before relying on them.")
    return out



# Findings published by the 2026-11-14 integration review of session arena/2e50a71a
# (root review.html, R-01 - R-13).  They are merged here so that the canonical
# Flagged for Review page carries every finding, with the original IDs kept.
REVIEW_FINDINGS = [
    ("R-01", "Critical", "Multiple independent model products report different samples, estimates, correlations and strategy statuses; none is designated as the reconciled source of truth.",
     "Do not combine or rank these results. Select one pipeline, define its data contract, and reproduce every result from identical timestamped inputs before publishing a canonical leaderboard.",
     ["https://www.nba.com/stats/help/glossary"],
     "Handled in this session: the canonical pages are built from one dataset (data/app/canonical.json) and from the official-sourced /origin/ pipeline only; the other workstreams are linked as snapshots and are not mixed in."),
    ("R-02", "Critical", "Several model inputs name secondary sources, including Basketball-Reference and ESPN, rather than showing an authorized official/licensed data chain. Rights and exact source snapshots are not demonstrated here.",
     "Source provenance is not proof of permission. Pause public derivative-use claims pending review of contracts/terms, versioned raw files, retrieval timestamps and redistribution rights.",
     ["https://www.nba.com/termsofuse"],
     "Open. The canonical pages use official NBA inputs only; the Basketball-Reference/ESPN inputs remain in the /edge/ and /lab/ snapshots and are not published on the canonical pages."),
    ("R-03", "Critical", "Some published artifacts include betting prices and labels such as \u201cPOSITIVE EV,\u201d even though the repository does not establish a licensed market-data source or common settlement specification.",
     "These are model outputs, not verified value. The source and rights must be established, odds timestamps and settlement rules recorded, vig/execution assumptions checked, and validation independently reproduced.",
     ["https://www.nba.com/termsofuse"],
     "Open. The canonical pages publish no market price and no EV label; the /edge/ and /lab/ snapshots still do and remain flagged."),
    ("R-04", "High", "README has contradictory statements: it says no lines, correlations, picks or performance claims are shown, but elsewhere describes those outputs and separate sections document them.",
     "Replace with one versioned, consistent status report. Keep every experimental output clearly distinguished from an official fact and from a validated recommendation.",
     ["https://www.nba.com/termsofuse"],
     "Handled in this session: the README now has one canonical section that states exactly what is published, what is derived and what is unverified."),
    ("R-05", "High", "Injury data are snapshots with different timestamps across sites; the official injury index says reports are updated continually. A past PDF is not a current slate feed.",
     "Store immutable report versions and timestamps; re-fetch the latest official report for every run; show staleness and suppress outputs if required inputs are missing. Do not infer minutes from status.",
     ["https://official.nba.com/nba-injury-report-2026-27-season/"],
     "Handled in this session for the canonical pages (one snapshot, 11/13/26 07:30 PM ET, with the diff against the previous snapshot published). The earlier sub-sites still carry older snapshots."),
    ("R-06", "High", "Upcoming slates and picks are fixed November 2026 files; the official schedule document is explicitly subject to change. No automated current-feed refresh is demonstrated by the static Pages site.",
     "Use request-time schedule retrieval and a bounded 72-hour window; persist source time/version; suppress the slate on feed failure, schedule changes or stale snapshots.",
     ["https://cdn.nba.com/manage/2026/08/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf"],
     "Open. The published window is a dated snapshot with its source and retrieval time shown on every page; a request-time feed is proposed as a site improvement (CS-33)."),
    ("R-07", "High", "Correlation outputs are not a shared, reconciled measurement. Different artifacts use different sample sizes, data sources, markets and possibly definitions.",
     "Keep values separate and unendorsed until pair definitions, sample construction, time windows, uncertainty, multiple-testing handling and source rights are harmonized and independently reproduced.",
     ["https://www.nba.com/stats/help/glossary"],
     "Handled in this session for the canonical pages: one correlation table, from one pipeline, with sample size, interval and status per row. The other artifacts remain unendorsed snapshots."),
    ("R-08", "High", "Passing local checks is not a line-by-line verification of every claim. Existing validators focus on specific generated sites/data schemas; they do not verify external truth, licensing, model quality or current URLs.",
     "Maintain site-specific tests, add scheduled source freshness checks and human review of changed source content; state exactly what each check proves.",
     ["https://www.nba.com/termsofuse"],
     "Partly handled in this session: the canonical build states what it proves (row-level source link, link integrity, official-value cross-check) and the repository-wide screen is reproducible (scripts/scan_table_sources.py). External truth, licensing and model quality remain outside the build's scope."),
    ("R-09", "High", "NBA's Terms of Use text includes restrictions on NBA Statistics in connection with gambling activity and on certain regularly updated comprehensive-statistics databases without express prior consent.",
     "This is not a legal determination about the project. Obtain current terms review and written permissions/contract advice before using NBA-sourced statistics in any gambling-related service.",
     ["https://www.nba.com/termsofuse"],
     "Open. Legal review is an owner decision; the canonical pages publish no betting recommendation and link the terms."),
    ("R-10", "High", "The intended product audience, offering model and compliance scope in the Netherlands are not defined.",
     "Get qualified Dutch counsel's assessment before deciding whether to offer information, picks or betting-related services to others; do not treat this page as legal advice.",
     ["https://kansspelautoriteit.nl/online-kansspel-aanbieden"],
     "Open. Tracked as an open question with the official regulator source."),
    ("R-11", "Medium", "Different sub-sites contain distinct inventories, ID namespaces and dates; the root dashboard previously said outputs did not exist, although they are present elsewhere.",
     "Use the root dashboard as the overview; label each sub-site's provenance and snapshot; reconcile IDs and remove obsolete contradictory summaries only after review.",
     ["https://www.nba.com/news/2026-27-nba-regular-season-schedule"],
     "Handled in this session: one canonical dashboard with one ID namespace; the earlier sub-sites are kept, labelled as snapshots and linked from the landing page."),
    ("R-12", "Medium", "The user's \u201cremove luck\u201d goal is not literally achievable; predictive evaluation can separate signal from outcome noise only probabilistically.",
     "Use proper probability scores, calibration, walk-forward evaluation, uncertainty intervals, pre-registration and prospective shadow results. Never claim luck-free outcomes.",
     ["https://www.nba.com/stats/help/glossary"],
     "Addressed in the canonical Method page: luck is kept out of the evaluation, not out of the outcome."),
    ("R-13", "High", "A mechanical scan across the repository's HTML files found table-body rows that lack a direct official NBA/Ksa link. Earlier measurement by session 2e50a71a: 1,521 rows scanned, 423 without a direct official link (389 excluding the archived research-dashboard.html). Second independent scan on 2026-11-14 (scripts/scan_table_sources.py): 2,111 rows in 90 files, 369 without a direct official-host link.",
     "This is a conservative automated screen, not a manual judgment that each row needs NBA evidence. For any row whose value cannot be confirmed from an official/authorized source, leave the value blank, label it unverified, and add an appropriate source before reuse. A full page-by-page source correction of the earlier sub-sites remains outstanding.",
     ["https://www.nba.com/stats/help/glossary"],
     "Open for the earlier sub-sites (lab 184, origin 73, site 29, edge 10, docs 5 rows without a direct official link; the archived root dashboard 34). The canonical pages contribute 0."),
]

# ---------------------------------------------------------------- flags
def build_flags():
    out = []
    n = 0

    def add(area, item, why, action, sources, status, severity, legacy="", found=""):
        nonlocal n
        n += 1
        out.append({
            "id": f"NF-{n:02d}", "area": area, "item": item, "why": why,
            "action_needed": action, "sources": sources, "status": status,
            "severity": severity, "legacy_ref": legacy, "found_on": found,
        })

    for r in cload("data", "flags.csv"):
        sev = "medium"
        if r["area"] in ("Legal", "Data"):
            sev = "high"
        add(r["area"], r["item"], r["why_flagged"], r["action_needed"], [r["source_url"]],
            r["status"], sev, r["flag_id"], "2026-11-13")
    site_sources = {s["id"]: s["url"] for s in jload("data", "sources.json")}
    for r in jload("data", "flags.json"):
        sev = "high" if r.get("type") == "Blocker" else "medium"
        add(r.get("type", "Irregularity"), r["item"], r["why"], r["action"],
            [site_sources[i] for i in r.get("sources", []) if i in site_sources]
            or FLAG_FALLBACK.get(r["id"], []),
            r.get("status", "Open — owner review"), sev, r["id"], "2026-11-13")

    # Flags found by this integration session (2026-11-14).
    add("Deployment", "GitHub Pages is still served from the legacy 'main /' source",
        "gh api reports build_type=legacy with source branch main, path /. The whole public repository is therefore published, including raw JSON and CSVs. The Actions workflow also runs and uploads an artifact, but the published site is the branch build.",
        "Set Pages source to GitHub Actions (owner/admin token required; previous sessions got HTTP 403) so only the reviewed artifact is published.",
        ["https://github.com/wingbangboozle1-lang/NBA3"],
        "Open — owner action", "medium", "", "2026-11-14")
    add("Site", "Seven separate dashboards were published from earlier sessions",
        "The repository contained /docs/, /site/, /lab/, /research/, /edge/ and /origin/ dashboards plus a root dashboard. They use different ID namespaces and some publish the same facts with different injury snapshots, which makes the site confusing and easy to misread.",
        "This session publishes one canonical dashboard at the root with category sub-pages; the earlier dashboards are kept and linked as 'earlier snapshots' for audit. Owner to decide whether to retire any.",
        ["https://github.com/wingbangboozle1-lang/NBA3"],
        "Resolved in this session (canonical site published); owner to confirm retirement of the older snapshots", "medium", "", "2026-11-14")
    add("Data", "Two official injury snapshots are stored with different timestamps",
        "data/injuries.json holds the 11/13 05:00 PM report (117 rows) while data/origin/injuries.csv holds the 11/13 05:15 PM report (118 rows) and data/app holds the 11/13 07:30 PM report (122 rows). A reader could easily compare a 7:30 PM status with a 5:00 PM status and read it as a contradiction.",
        "The canonical site publishes only the 07:30 PM report and lists the status changes against the 05:15 PM snapshot. The older files are kept as history and labelled with their stamps.",
        ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf"],
        "Open — owner review", "medium", "", "2026-11-14")
    add("Data", "No official injury report exists yet for the 2026-11-15 and 2026-11-16 games",
        "The newest report listed on the official index (11/13 07:30 PM ET) covers the 11/13 and 11/14 games only. Five teams had not submitted their report for the 11/14 game at that time.",
        "Re-read the official index before publishing lines for 11/15-11/16, or publish those games with an explicit 'no official report yet' marker.",
        ["https://official.nba.com/nba-injury-report-2026-27-season/"],
        "Open — recurs every slate", "high", "", "2026-11-14")
    add("Data", "Player abbreviations in one earlier pipeline are not NBA abbreviations",
        "data/picks/picks_2026-11-14_to_16.json prints 'BRK @ MEM'; the official NBA abbreviation is BKN (Brooklyn Nets). The same file also carries a generated timestamp and an availability flag computed from the 11/13 report.",
        "The canonical site uses the official abbreviation from the official schedule; the earlier file is left as an audit snapshot and the defect is recorded here.",
        ["https://www.nba.com/schedule?date=2026-11-14"],
        "Open — owner review", "low", "", "2026-11-14")
    add("Verification", "First manual transcription of the official team stats page produced 8 misread values",
        "An independent manual transcription of nba.com/stats/teams/advanced on 2026-11-14 differed from the stored values for MIA, TOR, CHA, NOP and UTA. A second read of the same page confirmed the stored values and the first read was wrong. The automated cross-check caught all eight.",
        "Keep the automated cross-check (scripts/capture_official_2026_11_14.py) in the build so that every official capture is compared with the stored values before publication.",
        ["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"],
        "Resolved in this session (cross-check added to the build)", "medium", "", "2026-11-14")
    return out


# ---------------------------------------------------------------- questions
def build_questions():
    out = []
    n = 0

    def add(category, question, status, known, missing, next_step, sources, owner, legacy=""):
        nonlocal n
        n += 1
        out.append({
            "id": f"CQ-{n:02d}", "category": category, "question": question,
            "status": status, "known": known, "missing": missing,
            "next_step": next_step, "sources": sources, "owner": owner,
            "legacy_ref": legacy,
        })

    for r in cload("data", "questions.csv"):
        add(r["category"], r["question"], r["status"], r["current_answer_or_knowledge"],
            r["missing_information"], r["discovery_step"], [r["evidence_url"]],
            r["decision_owner"], r["q_id"])
    for r in jload("data", "questions.json"):
        add(r.get("category", "General"), r["q"], r["status"], r["known"], r["missing"],
            r.get("next", ""), [s["url"] for s in jload("data", "sources.json")
                                if s["id"] in r.get("src", [])]
            or QUESTION_FALLBACK.get(r["id"], []),
            "Owner", r["id"])
    add("Data", "Do you want the site to publish model-derived numbers that no official source confirms?",
        "Answered (policy applied)", "The brief requires a source link on every row and blanks for anything not confirmable from an official source. Model outputs (spread, total, probability) are by definition ours, not official.",
        "Explicit owner confirmation of the display policy for derived values (currently: shown in a 'Derived' column with the model method link and never presented as an official fact).",
        "Review the Derived columns on the Lines and Picks pages and say whether they should be hidden until a licensed market feed exists.",
        ["https://github.com/wingbangboozle1-lang/NBA3"], "Owner")
    add("Legal", "Will the project be used commercially in the Netherlands, and by whom?",
        "Answered (no) — awaiting counsel", "No operator, licence or customer base is described in the repository.",
        "Operator entity, Ksa licence status, customer geography, age verification, responsible-gambling controls.",
        "Counsel review against the Ksa licensing page and the Wet op de kansspelen before any betting-related feature is published.",
        ["https://kansspelautoriteit.nl/online-kansspel-aanbieden",
         "https://wetten.overheid.nl/BWBR0002469/2025-02-12/0"], "Owner")
    add("Strategy", "What sample size and decision rule should gate a strategy as deployable?",
        "Answered (proposed, not approved)", "The gate set in this repository proposes n >= 100 out-of-sample games, raw p < 0.05, Benjamini-Hochberg FDR 0.05 and a stable split-half direction. Thresholds are proposals, not owner decisions.",
        "Owner approval of the thresholds, the loss function and the prize structure of the leaderboard.",
        "Approve or amend the gate thresholds on the Strategies page; the leaderboard ranks by them.",
        ["https://www.itl.nist.gov/div898/handbook/prc/section2/prc24.htm"], "Owner")
    return out


# ---------------------------------------------------------------- suggestions
def build_suggestions():
    out = []
    n = 0

    def add(area, suggestion, why, options, recommended, dependency, decision, sources, legacy=""):
        nonlocal n
        n += 1
        out.append({
            "id": f"CS-{n:02d}", "area": area, "suggestion": suggestion, "why": why,
            "options": options, "recommended_option": recommended,
            "dependency": dependency, "decision": decision, "sources": sources,
            "legacy_ref": legacy,
        })

    for r in cload("data", "suggestions.csv"):
        add(r["area"], r["suggestion"], r["why"], r["options"], r["recommended_option"],
            r["dependency"], r["decision"], [r["evidence_url"]], r["sug_id"])
    for r in jload("data", "suggestions.json"):
        add(r.get("area", "Site"), r.get("suggestion", r.get("title", "")), r.get("why", ""),
            r.get("options", ""), r.get("recommended", ""), r.get("depends", ""),
            "Awaiting owner review",
            [s["url"] for s in jload("data", "sources.json") if s["id"] in r.get("src", [])]
            or SUGGESTION_FALLBACK.get(r["id"], []),
            r["id"])
    # Site-improvement suggestions raised by this session (nothing implemented).
    add("Site", "Retire or clearly mark the six earlier dashboards",
        "The earlier /docs/, /site/, /lab/, /research/, /edge/ and /origin/ dashboards duplicate facts under different ID namespaces and different injury snapshots. A reader can easily compare a 5:00 PM status with a 7:30 PM status and think the site contradicts itself.",
        "A: keep all six as linked 'earlier snapshots' (current); B: keep only /origin/ and /edge/ because they carry the model and the gates; C: move all of them to an archive branch and keep only the canonical site live.",
        "A for now — nothing is deleted without an owner decision; B is the cleanest long-term state.",
        "None — this is a publishing decision, not a code dependency.",
        "Awaiting owner review",
        ["https://github.com/wingbangboozle1-lang/NBA3/branches"])
    add("Site", "Switch GitHub Pages from the legacy 'main /' source to the Actions workflow",
        "With the legacy source the whole public repository is published, including raw JSON/CSV data files. That widens the surface of the NBA-derived content that the Terms-of-Use flag concerns.",
        "A: keep legacy source (current); B: switch to GitHub Actions so only the curated artifact is published.",
        "B — it publishes only the reviewed pages and removes the raw data files from the public surface.",
        "Requires a repository admin token with Pages administration rights.",
        "Awaiting owner review",
        ["https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site"])
    add("Site", "Add a single 'as of' timestamp and data-freshness badge on every page",
        "Official sources move during a slate (injury reports every 15 minutes, tip times can change, stats pages update after games). A reader cannot currently tell how old a page is.",
        "A: keep the current per-table source stamps only; B: add one global snapshot stamp plus a per-table freshness badge.",
        "B — already implemented in this session for the canonical pages.",
        "None",
        "Implemented in this session (open for owner confirmation)",
        ["https://official.nba.com/nba-injury-report-2026-27-season/"])
    add("Decision support", "Turn the leaderboard into a scored competition with an explicit prize rule",
        "The brief asks for a leaderboard competition with rewards for the best strategies. The repository has gates and a ranking, but no reward rule, no capital base and no drawdown limit.",
        "A: keep gates only (current); B: add a paper-trading prize rule with a fixed stake and a published drawdown stop.",
        "B, once the legal and data questions (CQ pages) are answered.",
        "CQ legal answers; a licensed or owner-captured price source for scoring.",
        "Awaiting owner review",
        ["https://github.com/wingbangboozle1-lang/NBA3"])
    add("Model", "Add possession-level inputs (four factors) to the total model",
        "The total model does not beat a naive league-average baseline out of sample (RMSE 20.35 vs 19.56), so every total-based strategy rests on a model with no demonstrated skill.",
        "A: keep the total model as published with the caveat; B: add offensive/defensive ratings and pace matchup before publishing total-based strategies.",
        "B — the model is already written for it and the inputs are official NBA stats.",
        "Official team ratings (already captured) and player box scores.",
        "Awaiting owner review",
        ["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"])
    return out


# ---------------------------------------------------------------- repo review
def build_review():
    out = []
    n = 0

    def add(area, item, finding, status, action, sources, legacy="", found=""):
        nonlocal n
        n += 1
        out.append({
            "id": f"CR-{n:02d}", "area": area, "item_reviewed": item, "finding": finding,
            "status": status, "recommended_action": action, "sources": sources,
            "legacy_ref": legacy, "found_on": found,
        })

    for r in cload("data", "repo_review.csv"):
        add(r["area"], r["item_reviewed"], r["finding"], r["status"],
            r["recommended_action"], [r["evidence_url"]], r["item_id"], "2026-11-13")
    for r in jload("data", "repo_review.json"):
        add("Repository", r["item"], r["obs"], r["status"], "See the linked item.",
            [r["src"]], r["id"], "2026-11-13")
    add("Deployment", "GitHub Pages configuration",
        "gh api repos/wingbangboozle1-lang/NBA3/pages returns build_type=legacy, source branch main, path /. The Actions workflow runs and uploads an artifact, but the published site is the branch build of the whole repository.",
        "Irregularity — flagged",
        "Switch the Pages source to GitHub Actions (needs an admin token; earlier attempts returned HTTP 403).",
        ["https://github.com/wingbangboozle1-lang/NBA3"], "", "2026-11-14")
    add("Site", "Published information architecture",
        "Six earlier dashboards (docs, site, lab, research, edge, origin) plus the root dashboard were all reachable from the landing page, with overlapping content under five different ID namespaces.",
        "Irregularity — handled in this session",
        "One canonical dashboard at the root with category sub-pages; earlier dashboards retained and linked as audit snapshots.",
        ["https://github.com/wingbangboozle1-lang/NBA3"], "", "2026-11-14")
    add("Data", "Official schedule cross-check",
        "The 31 games of the 2026-11-13..16 window were re-read from nba.com/schedule on 2026-11-14 and compared with data/slates.csv captured on 2026-11-13: 31/31 agree on date, tip time, teams and NBA game id.",
        "Verified",
        "None. Re-run scripts/capture_official_2026_11_14.py before publishing a new slate.",
        ["https://www.nba.com/schedule?date=2026-11-14"], "", "2026-11-14")
    add("Data", "Official team statistics cross-check",
        "All 30 teams were re-read from nba.com/stats/teams/advanced on 2026-11-14 and compared with data/origin/teams_advanced.csv: 210/210 field comparisons (GP, W, L, OffRtg, DefRtg, NetRtg, PACE) agree.",
        "Verified",
        "None. Re-run the capture script; it fails loudly on any mismatch.",
        ["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"], "", "2026-11-14")
    add("Data", "Official injury report cross-check",
        "The 11/13 07:30 PM report was read and compared with the stored 11/13 05:15 PM snapshot: 9 status changes (e.g. T.J. McConnell Probable -> Available, Klay Thompson Probable -> Out), 1 team report newly present (Denver for the 11/14 game), and 5 team reports still marked NOT YET SUBMITTED.",
        "Verified",
        "None. The canonical site publishes the 07:30 PM snapshot only.",
        ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_30PM.pdf"], "", "2026-11-14")
    # ---- session arena/8d3d0271-nba3 (2026-11-14) ----
    add("Data", "Official capture re-read: schedule",
        "The 27 games of the 2026-11-14..17 window were transcribed from nba.com/schedule on "
        "2026-11-14 and compared with the previous session's 11/13-11/16 capture: 22 games appear "
        "in both and 88 of 88 field comparisons (date, tip time, away, home) agree, 0 differ. The "
        "2026-11-13 games were live on the page at read time and were excluded from the priced "
        "window.",
        "Verified",
        "None. Re-run scripts/capture_official_2026_11_14b.py before publishing a new slate.",
        ["https://www.nba.com/schedule?date=2026-11-14"], "", "2026-11-14")
    add("Data", "Official capture re-read: team statistics",
        "All 30 teams were re-read from nba.com/stats/teams/advanced on 2026-11-14 and compared "
        "with data/origin/teams_advanced.csv: 240 of 240 field comparisons (GP, W, L, MIN, OffRtg, "
        "DefRtg, NetRtg, PACE) agree.",
        "Verified",
        "None.",
        ["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"],
        "", "2026-11-14")
    add("Data", "Official capture re-read: injury report",
        "The 11/13/26 07:45 PM report was transcribed: 122 rows (117 player rows, 5 team "
        "'NOT YET SUBMITTED' rows). Three official reports were then compared with each other — "
        "07:30 PM vs 07:45 PM: 0 status changes; 07:45 PM vs the newest report listed on the "
        "official index, 08:30 PM: 122 rows each and 0 differences. Three consecutive official "
        "reports agreeing on every row is evidence the transcription is stable, not merely "
        "unchallenged. The index publishes a report every 15 minutes, so this cross-check is now "
        "part of the build and fails it if a future report disagrees.",
        "Verified",
        "None. The canonical site publishes the 07:45 PM snapshot, stamps it with the newest "
        "report it was checked against, and cites the index for freshness.",
        ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_07_45PM.pdf",
         "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_08_30PM.pdf",
         "https://official.nba.com/nba-injury-report-2026-27-season/"], "", "2026-11-14")
    add("Repository", "Integrity scan of the data files",
        "All 79 JSON files in the working tree were parsed with a strict loader: 0 parse failures. "
        "The tree holds 120 HTML pages across 10 published site directories and 40 Python scripts, "
        "6.8 MB in total.",
        "Verified",
        "Consolidate the site trees (suggestion CS-35).",
        ["https://github.com/wingbangboozle1-lang/NBA3"], "", "2026-11-14")
    add("Model", "Defects found and fixed in the strategy engine during this build",
        "Four defects were found by reading the engine's own output rather than trusting it: "
        "(1) two-leg parlays were being scored against a 50% fair-line rate instead of 25%, which "
        "put a losing same-game parlay at the top of the first draft of the leaderboard; "
        "(2) the permutation test shuffled win flags within a date, which cannot change the total "
        "and so returned p=1.000 for every rule — it was replaced with a whole-board Monte Carlo "
        "against the fair-line null; (3) the 'high-octane' threshold used the median of the whole "
        "sample's projections, which is look-ahead — it now uses only prior projections; "
        "(4) an under-regularised Massey model printed a 28-point spread, so ridge and totals "
        "shrinkage are now chosen by validating on the most recent 20% of past games.",
        "Irregularity — found and fixed in this session",
        "Keep publishing defects found this way. A leaderboard whose top row is a bug is worse "
        "than no leaderboard.",
        ["https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/strategy_lab.py"],
        "", "2026-11-14")
    add("Model", "A signal that turned out to be the model's own error",
        "'Fade the highest projected totals' posted 69.7% on 66 out-of-sample games (p=0.0019, "
        "q=0.016) before the totals model was regularised. After shrinkage toward the league mean "
        "it fell to 65.5% on 29 games (p=0.136). The apparent edge was our own miscalibration, not "
        "a property of NBA games. Published as flag NF-50 rather than as a finding.",
        "Irregularity — flagged",
        "Treat any bias found against our own line as a model defect to repair until a licensed "
        "price feed makes an external comparison possible (question CQ-40).",
        ["https://www.nba.com/games?date="], "", "2026-11-14")
    add("Data", "data/raw/results_2026-27_october.csv and _november.csv",
        "The header comment documents an 8-column format (date, start_ET, away_team, away_pts, "
        "home_team, home_pts, OT, note) but every data row carries 5 fields, and the source named "
        "in the header is Basketball-Reference, which is not an official NBA property. The values "
        "themselves agree with the official capture, so this is a citation and schema defect, not "
        "a data error. First recorded by session e40cd215 as E-F-02; re-checked this session and "
        "still present.",
        "Irregularity — flagged",
        "Rewrite the header to match the rows, or retire the files in favour of "
        "data/origin/games.csv, which is the official-sourced capture.",
        ["https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/raw/results_2026-27_october.csv"],
        "E-F-02", "2026-11-14")
    add("Reporting", "Brief-coverage register was publishing stale statuses",
        "data/requirements.csv still reported 'Originate own NBA lines: Not started', 'Picks: "
        "blocked, no picks' and 'Correlations: blocked, no values' — statuses written by an earlier "
        "session before those outputs existed. Published as-is, the page would have told the owner "
        "the project had produced nothing.",
        "Irregularity — handled in this session",
        "The register was rewritten against the current build: what exists, what is measured, what "
        "is blocked, and the source for each claim.",
        ["https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/requirements.csv"],
        "", "2026-11-14")
    add("Site", "Superseded season links still in the published source register",
        "Two entries in the source register point at the 2025-26 NBA injury index "
        "(official.nba.com/nba-injury-report-2025-26-season/). Both are marked superseded and are "
        "kept deliberately as provenance for an earlier session's defect, but they appear in the "
        "same table as live sources.",
        "Irregularity — flagged",
        "Move superseded entries to a separate 'prior-season / historical' section of the register "
        "so a reader cannot mistake them for current sources.",
        ["https://official.nba.com/nba-injury-report-2026-27-season/"], "", "2026-11-14")
    add("CI", "Workflow coverage",
        "The workflow ran unit tests, the docs checker, the research pipeline, the edge checker and the site builders, and deployed successfully. It did not cover the canonical dataset assembled in this session.",
        "Irregularity — handled in this session",
        "Add the canonical capture/assembly/build steps and their drift checks to the workflow.",
        ["https://github.com/wingbangboozle1-lang/NBA3/actions"], "", "2026-11-14")
    add("CI", "Unresolved merge conflict committed in the workflow file",
        "The base commit this branch started from (4e9dec4) contained literal '<<<<<<< HEAD', "
        "'=======' and '>>>>>>> origin/main' conflict markers inside "
        ".github/workflows/pages.yml, between session e40cd215's integration steps and the "
        "canonical capture steps. A workflow file with conflict markers is not valid YAML, so "
        "every CI run on that commit would have failed at parse time. main resolved it later; "
        "this session rebases onto that resolution and re-applies its own steps on top, so both "
        "sides' steps are present and no marker remains.",
        "Irregularity — found and repaired in this session",
        "Treat a committed conflict marker as a build failure: add a CI step that greps the tree "
        "for '^<<<<<<<' and exits non-zero. It is a one-line check that would have caught this.",
        ["https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/pages.yml"],
        "", "2026-11-14")
    add("Data", "Injury capture miscounted the teams that had not filed",
        "scripts/capture_official_2026_11_14b.py set is_team_not_submitted by testing the "
        "Current Status column only. The official PDF prints 'NOT YET SUBMITTED' in the Reason "
        "column with Current Status blank, so all five such rows were counted as player rows: the "
        "published totals read 122 player rows and 0 not-submitted rows instead of 117 and 5. The "
        "counter is now computed from both columns, and the page states the split explicitly. The "
        "row-level cross-checks were never affected — they normalise both columns before "
        "comparing — which is why the defect only surfaced when the summary fields were read "
        "against the PDF rather than trusted.",
        "Irregularity — found and fixed in this session",
        "None. Keep publishing counts derived from the source columns rather than from a single "
        "assumed one.",
        ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_08_30PM.pdf"],
        "", "2026-11-14")
    add("Cross-session", "An engine swap tripped another session's CI drift gate",
        "integrate/engine.py (session e40cd215) derives its cross-engine reconciliation from the "
        "lines published in app/, so replacing the app/ engine changed its output and its "
        "'git diff --exit-code -- data/integration/model.json' drift gate failed on this branch's "
        "first CI run. The engine is deterministic (verified byte-identical across runs), so the "
        "correct fix is to commit the regenerated artefact: data/integration/model.json, "
        "dash/data/model.json and dash/reconciliation.html. The comparison still reads 22 of 22 "
        "games agreeing on the favoured side; only the gaps moved (median 2.39 -> 1.77, max "
        "4.76 -> 4.44, sd of app/ spreads 10.81 -> 8.81). Their gate did its job — it caught that "
        "an upstream input changed. Those three files are e40cd215's scope and their session is "
        "closed; they were regenerated rather than left failing, and the deviation is logged.",
        "Irregularity — repaired, scope deviation disclosed",
        "Session e40cd215: confirm the regenerated reconciliation, or make the comparison read "
        "from a pinned snapshot of app/ so an engine swap elsewhere cannot move it. Logged as "
        "CR-8D-06. Alternative considered and rejected: weakening the drift gate.",
        ["https://github.com/wingbangboozle1-lang/NBA3"], "", "2026-11-14")
    add("Cross-session", "Rebuilding the canonical engine invalidated another session's audit",
        "Session 36e18d83's audit36/check.py recomputes an 'engine agreement' block comparing the "
        "dash/ engine against the app/ engine and compares the result against values hard-coded in "
        "its own committed results file. This session replaced the app/ engine, so the recomputed "
        "figures moved (sd of app spreads 10.81 -> 8.81, median absolute gap 2.39 -> 1.78) and the "
        "check now reports one failure. The engines still agree on the favoured side in 22 of 22 "
        "games, so this is a stale expectation, not a new disagreement. audit36/ is that session's "
        "file scope and was not edited; its modified results file was reverted.",
        "Irregularity — flagged, change request logged",
        "Owner of audit36/: re-run the audit and re-publish the engine_agreement block against the "
        "current app/ engine, or read the expectation from the build output instead of hard-coding "
        "it. Logged as CR-8D-04. The audit36 step is not in the CI workflow, so CI is unaffected.",
        ["https://github.com/wingbangboozle1-lang/NBA3"], "", "2026-11-14")
    return out


# ---------------------------------------------------------------- strategies
GATE_TEXT = {
    "G1": "Every input has an official or reproducible source",
    "G2": "No look-ahead (all features exist at tip-off)",
    "G3": "Sample size n >= 100 out-of-sample games",
    "G4": "Effect is powered at the observed rate",
    "G5": "Raw p < 0.05 (exact binomial against 50%)",
    "G6": "Survives Benjamini-Hochberg FDR 0.05",
    "G7": "Direction stable in both halves of the sample",
}


def build_strategies():
    out = []
    mo = jload("data", "origin", "model_output.json")
    for s in mo["strategies"]:
        gates = s.get("gates", {})
        rows = []
        for key, val in gates.items():
            gid = key.split("_")[0]
            if isinstance(val, bool):
                rows.append({"gate": gid, "name": GATE_TEXT.get(gid, key), "passed": val,
                             "value": "pass" if val else "fail"})
            else:
                rows.append({"gate": gid, "name": GATE_TEXT.get(gid, key), "passed": False,
                             "value": f"n needed {val}"})
        out.append({
            "id": f"ST-{s['id']}", "family": "Originated-line strategy",
            "name": s["label"], "rule": s["rule"], "market": "Single bet / parlay against our own line",
            "n": s["n"], "wins": s["wins"], "rate": s["rate"], "p": s["p"],
            "verdict": s["verdict"], "passed_all_gates": s["passed_all_gates"],
            "gates": rows, "note": s.get("note", ""),
            "source": "https://www.nba.com/games?date=",
            "source_label": "174 official final scores captured from nba.com/games; walk-forward backtest in model/build.py",
            "legacy_ref": f"origin/{s['id']}",
        })
    picks = jload("data", "picks", "picks_2026-11-14_to_16.json")
    edge_status = picks.get("strategy_status", {})
    for sid, label in (("STRAT1", "Model side vs published spread (single bet)"),
                       ("STRAT2", "Model side vs published total (single bet)"),
                       ("STRAT3", "Totals fade strategy"),
                       ("STRAT4", "Same-game parlay")):
        out.append({
            "id": sid, "family": "Published-line strategy", "name": label,
            "rule": "See edge/picks.html and edge/strategies.html for the full rule and gate output.",
            "market": "Single bet / parlay", "n": None, "wins": None, "rate": None, "p": None,
            "verdict": edge_status.get(sid, ""), "passed_all_gates": False,
            "gates": [], "note": "Gate detail is published in the edge snapshot (earlier session).",
            "source": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/edge/data/validation-report.json",
            "source_label": "edge/ validation report (earlier session)",
            "legacy_ref": sid,
        })
    for r in cload("data", "strategies.csv"):
        out.append({
            "id": r["strategy_id"], "family": r["family"], "name": r["name"],
            "rule": r["hypothesis_to_test"], "market": r["family"],
            "n": None, "wins": None, "rate": None, "p": None,
            "verdict": r["gate_status"], "passed_all_gates": False,
            "gates": [], "note": r["blocking_reason"], "required_inputs": r["required_inputs"],
            "source": r["source_url"], "source_label": r["official_source_for_inputs"],
            "legacy_ref": r["strategy_id"],
        })
    return out


def build_gates():
    out = []
    n = 0
    for r in cload("data", "gates.csv"):
        n += 1
        out.append({
            "id": f"CG-{n:02d}", "name": r["gate_name"], "checks": r["what_is_checked"],
            "threshold": r["proposed_threshold"], "threshold_status": r["threshold_status"],
            "status": r["current_status"], "reason": r["reason"], "notes": r["notes"],
            "source": r["method_reference_url"],
            "legacy_ref": r["gate_id"],
        })
    mo = jload("data", "origin", "model_output.json")
    s5 = next(s for s in mo["strategies"] if s["id"] == "S5")
    for key, val in s5["gates"].items():
        gid = key.split("_")[0]
        n += 1
        out.append({
            "id": f"CG-{n:02d}", "name": GATE_TEXT.get(gid, key),
            "checks": GATE_TEXT.get(gid, key),
            "threshold": ("all inputs official or reproducible", "no look-ahead",
                          "n >= 100", "n needed for the observed effect",
                          "raw p < 0.05", "Benjamini-Hochberg FDR 0.05",
                          "direction stable in both halves")[int(gid[1]) - 1],
            "threshold_status": "Proposal (owner approval pending)",
            "status": "Measured" if isinstance(val, bool) else "Measured",
            "reason": "", "notes": ("pass" if val is True else
                                    ("fail" if val is False else f"n needed {val}")),
            "source": "https://github.com/wingbangboozle1-lang/NBA3/blob/main/model/build.py",
            "legacy_ref": gid,
        })
    return out


# ---------------------------------------------------------------- main
# Registers contributed by this session.  IDs continue the canonical NF-/
# CQ-/CS- namespaces used by session `arena/2b9f1ae1-nba3`.
SESSION_FLAGS = [
    ("NF-49", "Model", "high",
     "Our originated totals model is WORSE out of sample than a constant league-average total "
     "(RMSE 19.64 vs 19.46 on 131 walk-forward games). The published totals are shrunk toward "
     "the league mean by a weight chosen from past data only.",
     "Treat every originated total as weakly informative. Do not build a totals strategy on it "
     "until the model beats the constant.",
     ["https://www.nba.com/games?date="]),
    ("NF-50", "Strategies", "high",
     "A 'fade the highest projected totals' signal that looked strong before the totals model was "
     "regularised (n=66, 69.7%, p=0.0019 in the first draft of this board) fell to n=29, 65.5%, "
     "p=0.136 once the model was shrunk toward the league mean. The earlier signal was "
     "miscalibration, not edge.",
     "Any strategy that rests on our totals model must be re-scored after the model is fixed. "
     "A bias against our own line is a defect to repair, not an edge to bet.",
     ["https://www.nba.com/games?date="]),
    ("NF-51", "Strategies", "high",
     "No strategy on the board clears the luck threshold. Under the fair-line null, a board of "
     "this size produces a best-looking edge of 31.3 percentage points or more 5% of the time; "
     "the largest edge any rule actually posted is 18.0 pp.",
     "Do not fund anything on this board. The leaderboard is a screening tool, not a result.",
     ["https://www.nba.com/games?date="]),
    ("NF-52", "Injuries", "medium",
     "Only the top 31 players by minutes were captured from the official players table, so the "
     "minutes and production vacated by any other injured player are unknown. Every published "
     "minutes vacuum is therefore a FLOOR.",
     "Capture the full official minutes table, then recompute. Until then no injury number here "
     "is complete.",
     ["https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"]),
    ("NF-53", "Injuries", "medium",
     "Five of the ten teams playing on 2026-11-14 had NOT YET SUBMITTED a report in the newest "
     "official file (11/13/26 07:45 PM ET), and no report at all exists yet for 11/15, 11/16 or "
     "11/17.",
     "Re-read the official index before acting on any game later than 11/14. Those games cannot "
     "be treated as final.",
     ["https://official.nba.com/nba-injury-report-2026-27-season/"]),
    ("NF-54", "Slate", "low",
     "The 2026-11-13 games were LIVE on the official schedule page when it was read, so they were "
     "excluded from the priced window. Earlier sessions priced them.",
     "Use this page for the 11/14-11/17 window; earlier snapshots cover 11/13-11/16 and are kept "
     "as history.",
     ["https://www.nba.com/schedule?date=2026-11-14"]),
    ("NF-55", "Strategies", "high",
     "Every ROI figure in this repository is measured against our own originated line at an "
     "assumed -110 price. No licensed odds feed is connected, so no ROI here is an economic "
     "result and none should be read as profit.",
     "Connect a licensed, timestamped price feed, or stop publishing ROI.",
     ["https://www.nba.com/schedule"]),
]

SESSION_QUESTIONS = [
    ("CQ-36", "Leaderboard",
     "What does winning the leaderboard actually pay?",
     "Open - owner decision",
     "The board ranks rules by a composite skill score and assigns reward tiers T1-T5 with a "
     "stake allocation (full unit / quarter unit / paper only / none). No money is attached.",
     "Whether this is a prize contest, a pool, or internal scoring. Dutch rules treat these "
     "differently (Q-LEG-01, Q-LEG-02).",
     "Decide the competition format first; the reward schedule follows from it.",
     ["https://kansspelautoriteit.nl/online-kansspel-aanbieden"], "Owner"),
    ("CQ-37", "Leaderboard",
     "Who may add a strategy to the board, and how is it registered before it is scored?",
     "Open - owner decision",
     "Any rule can be scored. Nothing stops a rule being written after the results are known, "
     "which is how a backtest invents an edge.",
     "A pre-registration step: rule text, selection predicate and freeze date hashed before the "
     "first forecast is graded (gate G10 idea).",
     "Approve a pre-registration rule and add it as a gate; until then treat every strategy here "
     "as retrospective.",
     ["https://github.com/wingbangboozle1-lang/NBA3"], "Owner"),
    ("CQ-38", "Gates",
     "Is 100 graded out-of-sample forecasts the right minimum sample?",
     "Open - owner decision",
     "Gate G3 uses n >= 100. With ~1,230 NBA games a season and rules that fire on a subset, "
     "100 takes one to three seasons for the narrower rules.",
     "The cost of waiting versus the cost of acting on noise. 100 is a convention, not a "
     "measurement.",
     "Approve, raise or lower the number; the board re-scores automatically.",
     ["https://www.nba.com/games?date="], "Owner"),
    ("CQ-39", "Data",
     "May per-player game logs be captured and stored?",
     "Open - owner decision",
     "Without them every player-level correlation is blank and no prop combo can be priced. Four "
     "combos on the board are blocked on this alone.",
     "Storage, volume (~4,000 rows a season) and the reproduction terms in NBA s.1 and s.9.",
     "Decide, then capture nba.com/stats/players/boxscores by date and re-run the lab.",
     ["https://www.nba.com/stats/players/boxscores",
      "https://www.nba.com/termsofuse"], "Owner"),
    ("CQ-40", "Gates",
     "Should a detected bias against our own line be reported as an edge or as a model defect?",
     "Answered (defect) - owner confirmation requested",
     "Our margin model is unbiased (+0.01 points) but the totals model runs about 1.5 points hot. "
     "A rule that fades our own high totals therefore 'wins' against us.",
     "Nothing external. Beating our own line is not beating a market.",
     "Confirm the policy: a bias found against our own line is published as a model defect to "
     "fix, never as a betting edge.",
     ["https://www.nba.com/games?date="], "Owner"),
]

SESSION_SUGGESTIONS = [
    ("CS-31", "Leaderboard",
     "Pre-register every strategy before it is scored",
     "A rule written after seeing the results will always look good. Right now nothing stops it.",
     "A: keep scoring retrospectively but stamp every row 'retrospective'; B: hash the rule text "
     "and freeze it before the first graded forecast; C: both - stamp now, freeze from next "
     "season.",
     "C", "CQ-37",
     ["https://github.com/wingbangboozle1-lang/NBA3"]),
    ("CS-32", "Leaderboard",
     "Publish the luck threshold next to every leaderboard",
     "A per-rule p-value cannot tell you that a board of 15 rules throws up one 20-point edge by "
     "chance. The whole-board simulation can.",
     "A: show only per-rule p-values (current default elsewhere in the repo); B: show the "
     "whole-board luck threshold and require a rule to beat it (this board); C: hide the board "
     "until a rule beats it.",
     "B", "NF-51",
     ["https://www.nba.com/games?date="]),
    ("CS-33", "Model",
     "Fix the totals model before publishing another totals strategy",
     "It is beaten by a constant. Every totals rule on the board is measuring the model's error, "
     "not the game.",
     "A: keep publishing totals lines with the shrinkage and a warning; B: drop totals lines "
     "until the model beats the constant; C: rebuild the totals model on possessions and "
     "four factors, which needs data we do not have yet.",
     "A now, C when the data exists", "NF-49",
     ["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"]),
    ("CS-34", "Data",
     "Capture the full official minutes table, not the top 31",
     "Every injury number on the site is a floor because most injured players are outside the "
     "captured table.",
     "A: capture all rows on the official players page; B: capture only players who appear on an "
     "injury report; C: leave it and keep the floors flagged.",
     "A", "NF-52",
     ["https://www.nba.com/stats/players/traditional?Season=2026-27&SeasonType=Regular%20Season"]),
    ("CS-35", "Site",
     "Name one canonical dashboard and archive the rest",
     "Eight dashboards are live on this Pages site with five incompatible ID namespaces. A reader "
     "cannot tell which numbers are current.",
     "A: keep all eight and label each with its snapshot time; B: promote one, move the rest "
     "under /archive/ with a banner; C: delete the redundant ones.",
     "B", "NF-44",
     ["https://github.com/wingbangboozle1-lang/NBA3"]),
    ("CS-36", "Picks",
     "Stop calling our own fair prices 'picks'",
     "A pick implies a bet against a price. We have no price. The page is a set of fair numbers "
     "against our own line.",
     "A: rename the page to 'Originated prices for the window' and drop the word pick; B: keep "
     "'picks' but print the fair-price caveat on every row; C: remove the page until a price feed "
     "is connected.",
     "A", "NF-55",
     ["https://www.nba.com/schedule"]),
    ("CS-37", "Slate",
     "Regenerate the window automatically instead of transcribing it by hand",
     "Three sessions have hand-transcribed the same schedule page. It is slow and it is where "
     "every transcription error so far has come from.",
     "A: keep manual transcription with a cross-check (current); B: add a scheduled job that "
     "re-reads the official pages and opens a pull request on any difference; C: manual, but only "
     "on a fixed daily cadence.",
     "B", "NF-54",
     ["https://www.nba.com/schedule?date=2026-11-14"]),
    ("CS-38", "Compliance",
     "Resolve the legal questions before anything is staked",
     "NBA Terms s.9 restricts gambling use of its statistics and Dutch law requires a licence to "
     "offer online betting. The reward schedule depends on which applies.",
     "A: internal scoring only, no prizes, no money; B: obtain a licence; C: stop publishing "
     "selections publicly.",
     "A pending counsel", "CQ-36",
     ["https://www.nba.com/termsofuse",
      "https://kansspelautoriteit.nl/online-kansspel-aanbieden"]),
]

GATE_DEFS = [
    ("CG-19", "G1", "Every input has an official or reproducible source",
     "Every row traces to an official page or to code in this repository",
     "Zero unsourced rows", "Design rule (proposed)"),
    ("CG-20", "G2", "No look-ahead",
     "Ratings, shrinkage and thresholds refit from games with a strictly earlier date",
     "Zero features stamped at or after tip-off", "Design rule (proposed)"),
    ("CG-21", "G3", "Minimum out-of-sample sample",
     "Enough graded forecasts before any verdict", "n >= 100", "Proposed (owner approval needed)"),
    ("CG-22", "G4", "Statistical power",
     "The observed effect is large enough that the sample can detect it",
     "Required n at 80% power <= observed n", "Proposed (owner approval needed)"),
    ("CG-23", "G5", "Distinguishable from luck",
     "Exact two-sided binomial test against the fair-line rate for that market",
     "p < 0.05", "Proposed (owner approval needed)"),
    ("CG-24", "G6", "Multiple testing",
     "Benjamini-Hochberg across every scored rule on the board",
     "q <= 0.05", "Proposed (owner approval needed)"),
    ("CG-25", "G7", "Stability",
     "Direction holds in the first half and the second half of the sample",
     "Both halves on the same side of the fair-line rate", "Proposed (owner approval needed)"),
    ("CG-26", "G8", "Economic test at an assumed price",
     "Date-block bootstrap of return at an assumed -110 per leg",
     "95% interval excludes zero", "Proposed (owner approval needed) - see NF-55"),
    ("CG-27", "G9", "Beats the whole-board luck threshold",
     "Monte Carlo: largest edge across the board simulated under the fair-line null",
     "Edge >= 95th percentile of the null maximum", "Proposed (owner approval needed)"),
]


def build_lab_gates():
    out = []
    for gid, short, name, checks, threshold, status in GATE_DEFS:
        out.append({
            "id": gid, "gate": short, "name": name, "checks": checks,
            "threshold": threshold, "threshold_status": status,
            "status": "Measured on every scored rule", "reason": "", "notes": "",
            "source": "https://github.com/wingbangboozle1-lang/NBA3",
        })
    return out


SESSION_FLAGS += [
    ("NF-56", "Availability", "high",
     "Before this round the picks page published 'REPORTED — Both teams had filed a report at "
     "capture time' and an absence count of 0 for both sides on 22 of the 27 games in the window "
     "(every game on 2026-11-15, 11-16 and 11-17). No official report covered those dates: the "
     "newest report prints NOT YET SUBMITTED for all 18 teams on 11/15 and nothing at all for "
     "11/16 and 11/17. Root cause: 'submitted' was inferred from the absence of a NOT-YET-SUBMITTED "
     "row, so an empty row set read as a clean bill of health.",
     "Fixed in this round: availability is a four-state value (FILED / DUE_AND_NOT_FILED / "
     "NOT_YET_DUE / NO_OFFICIAL_REPORT_COVERS_THIS_DATE) decided from the official filing rule, "
     "and an absence count is published only for a team that is on the report. Owner decision "
     "still owed: whether a pre-deadline line should be re-priced automatically at the deadline "
     "(CQ-41).",
     ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf",
      "https://official.nba.com/nba-injury-report-2026-27-season/"]),
    ("NF-57", "Inputs", "high",
     "The team-ratings snapshot the window was priced with was read at 2026-11-14T01:05Z, i.e. "
     "while the 11/13 slate was still live. 18 of 30 teams were one game stale — and those 18 are "
     "exactly the 18 teams playing that night, so the staleness was not random. 123 of the 240 "
     "stored stat fields differ from the post-slate re-read, and the canonical results log was "
     "missing all nine 11/13 finals.",
     "Refreshed here: log extended to 183 games, ratings re-read after the slate, every line "
     "re-originated. All 27 lines moved (median |spread move| 1.11 points, max 4.89). Standing "
     "rule proposed: never capture team stats during a live slate; capture after the last final.",
     ["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season",
      "https://www.nba.com/games?date=2026-11-13"]),
    ("NF-58", "Data log", "medium",
     "Flag F36-03 handed off 'extend data/origin/games.csv (to 184 games)'. The log now holds 183 "
     "games, not 184. Three independent official readings agree on 183: the GP column of the "
     "official team statistics (366 team-games), the W and L columns (183 wins, 183 losses), and "
     "the official November calendar's per-date counts added to our own October rows (88 + 95).",
     "Recorded so a later session does not 'repair' the log to 184 to match the note. The "
     "off-by-one was in the hand-off text, not in the data.",
     ["https://www.nba.com/games?date=2026-11-13",
      "https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"]),
    ("NF-59", "Capture fidelity", "medium",
     "One injury row of the 11/14 04:15 AM report — Traore, Nolan (Probable, right calf) on the "
     "BKN@MEM block — sits at a page-break gap where the PDF text carries no Team cell. The team "
     "is left BLANK in the capture rather than attributed, so that Probable is not attached to any "
     "team in the availability join.",
     "Needs a second read of the PDF table, or a check against the official team roster page, "
     "before the row is attributed. It changes no line either way: a Probable is not an absence.",
     ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"]),
    ("NF-60", "Model", "high",
     "After the refresh the totals model still loses to a constant out of sample: RMSE 19.449 vs "
     "19.386 on 140 walk-forward games (the margin model wins: 15.945 vs 16.921). Every originated "
     "total is therefore weaker than the originated spread, and every totals rule on the board "
     "inherits that.",
     "Keep the totals published with this caveat on the page. Do not fund a totals strategy on a "
     "model that loses to the league mean.",
     ["https://www.nba.com/games?date="]),
    ("NF-61", "Process", "medium",
     "Nothing in the repository re-pulls the official pages on a schedule. The published window is "
     "correct as of one timestamp (2026-11-14 09:45Z) and drifts silently after it — including "
     "through the 1 p.m. local game-day deadline that would settle five of tonight's games.",
     "Decide a re-capture cadence (CQ-41) and put the snapshot age in the header of every page. "
     "Until then every page states its as-of time, and the freshness page lists what will change it.",
     ["https://official.nba.com/nba-injury-report-2026-27-season/"]),
    ("NF-62", "Parlays", "high",
     "assemble_canonical.py published 'parlay_leg_candidate = True' for all 27 games as a literal, "
     "regardless of availability — so a game with no injury report at all was flagged as a valid "
     "parlay leg. Nothing else in the pipeline consulted that field, which is why it survived.",
     "Fixed here: a game is a parlay-leg candidate only when both sides appear as filed on the "
     "newest official report. On the current snapshot that is zero games, which agrees with the "
     "leaderboard result (no funded strategy) and with the same page's own warning.",
     ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"]),
]

SESSION_QUESTIONS += [
    ("CQ-41", "Freshness", "Should a line that is priced before a filing deadline be re-priced "
     "automatically when the deadline passes, or held and marked stale?", "Open - owner decision",
     "Known: the deadline for every team-game in the window is computable from the official rule "
     "and the official schedule, and scripts/report_availability.py already publishes it per game. "
     "Five of tonight's ten team-sides settle at 1 p.m. local today. Known: nothing re-pulls today.",
     "Missing: whether an automatic re-price is wanted (it changes published numbers without a "
     "human in the loop) or whether the site should only show the age and let the reader decide.",
     "Pick one: (a) re-pull and re-price on the deadline, (b) re-pull and publish as a shadow line "
     "next to the original, (c) leave as it is. (b) keeps an audit trail and is what the leaderboard "
     "would need anyway to score strategies fairly.",
     ["https://official.nba.com/nba-injury-report-2026-27-season/"], "Owner"),
    ("CQ-42", "Data", "Should there be one canonical result log for the whole repository?",
     "Open - owner decision",
     "Known: data/origin/games.csv now holds 183 verified games (through 2026-11-13); "
     "final/data/games.csv still holds 174 (through 2026-11-12) and the /dashboard/ tree is built "
     "from it, so two pages on the live site describe two different seasons-to-date.",
     "Missing: a decision on which log is canonical, and whether the older trees are re-cut or "
     "labelled as dated snapshots.",
     "Either point every tree at data/origin/games.csv and re-run their builders, or add a "
     "'snapshot of 2026-11-13' banner to the trees that keep their own copy. Re-cutting is the "
     "cleaner option; it also re-opens their own verification numbers.",
     ["https://www.nba.com/games?date=2026-11-13"], "Owner"),
    ("CQ-43", "Method", "Is a venue time-zone table acceptable as an input?", "Open - owner decision",
     "Known: the official rule states deadlines in LOCAL time; the official schedule prints tip "
     "times in ET. The offset between the two is not printed on any official page this project reads, "
     "so 're-price at 13:00 local' is shown as local and the ET equivalent is left blank.",
     "Missing: permission to use a published time-zone reference (which would let the site print "
     "'1:00 p.m. local = 2:00 p.m. ET' and rank tonight's games by when each becomes priceable).",
     "Either accept an external time-zone source and record it in the source register, or keep the "
     "blank and accept that the ordering, not the clock time, is what the site can promise.",
     ["https://official.nba.com/nba-injury-report-2026-27-season/"], "Owner"),
    ("CQ-44", "Availability", "Does a game with an unresolved side belong in a parlay at all?",
     "Open - owner decision",
     "Known: same-game parlays on the site are priced with a measured dependence ratio of 0.942 "
     "whose interval includes 1.0, so independence is not established; and 22 of 27 games have no "
     "usable availability. The flag that said every game was a valid leg is now derived from "
     "availability instead of being a literal.",
     "Missing: the owner's policy on leg eligibility — zero legs is a defensible answer for tonight, "
     "but not for a whole slate.",
     "Choose a rule: exclude any leg whose team has not filed; or allow pre-deadline legs and mark "
     "them; or gate legs on strategy funding instead of availability. The first is the strictest and "
     "the easiest to defend.",
     ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"], "Owner"),
    ("CQ-45", "Injuries", "How should a Probable or Available-with-injury row affect a line?",
     "Open - owner decision",
     "Known: the engine counts Out and Doubtful as absences and treats Questionable as 'listed but "
     "not counted'; Probable and Available (9 rows on the 11/14 slate, e.g. Caleb Martin with a "
     "thumb splint, Nolan Traore with a calf) currently have no effect at all.",
     "Missing: a measured minute-donation model for game-time decisions, which needs per-player game "
     "logs this repository does not have.",
     "Either state on the page that Probable/Available rows are ignored and why, or capture player "
     "game logs and measure how minutes actually shift for splint/mask cases. The first costs nothing.",
     ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"], "Owner"),
]

SESSION_SUGGESTIONS += [
    ("CS-39", "Decision support",
     "Put a 're-price at' column on the picks table, driven by the availability artefact that now "
     "exists (data/app/report_availability.json).",
     "The single most actionable fact about a pre-deadline game is when it stops being pre-deadline. "
     "It is already computed and is only shown on the freshness page today.",
     "A: add the column to the picks table; B: add a countdown to the header of each date group; "
     "C: leave it on the freshness page only.",
     "A — one column, no new data, and it makes the PARTIAL_REPORT chips self-explanatory.",
     "None; the data is in the build already.",
     ["https://official.nba.com/nba-injury-report-2026-27-season/"]),
    ("CS-40", "Site architecture",
     "Let the twelve site trees share one availability renderer instead of each deciding what 'no "
     "rows captured' means.",
     "The defect behind NF-56 was possible because each tree re-implemented the same judgement. A fix "
     "applied to the canonical pages leaves the same wrong reading live in the other trees.",
     "A: extract one module that every tree calls; B: freeze the older trees as dated snapshots with "
     "a banner; C: delete the older trees from the Pages artifact.",
     "B now, A when the site is consolidated. Freezing with a banner costs nothing and stops a "
     "reader treating an old tree as current.",
     "Owner decision on consolidation (CQ-42 is the same fork in the road).",
     ["https://github.com/wingbangboozle1-lang/NBA3"]),
    ("CS-41", "Trust",
     "Print the snapshot age on every page: which capture timestamp the page was built from, and how "
     "many hours ago.",
     "Every number on the site is correct as of a moment that is now hours old, and only the "
     "verification page says so. A reader who lands on the lines page has no signal that the "
     "availability picture may already have moved.",
     "A: age string in the page header; B: colour the header grey when the snapshot is older than "
     "the next deadline; C: nothing.",
     "B — it is the same data the freshness page already has, and it makes staleness impossible to "
     "miss rather than merely documented.",
     "None.",
     ["https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"]),
    ("CS-42", "Decision discipline",
     "Render the unfunded state of the leaderboard into the picks page itself: no funded strategy "
     "means no game in the window is a selection, and the page should say that in its first line.",
     "The picks page currently leads with 27 priced games and buries 'nothing here is a bet' in a "
     "callout below. The honest headline is that the board has funded no rule, so the prices are "
     "research output, not a slip.",
     "A: lead with the funded-strategy count and gate the table behind it; B: keep the layout and "
     "strengthen the warning; C: split research prices from actionable picks into two pages.",
     "A — one line at the top, no new page, and it matches what the leaderboard page already says.",
     "None.",
     ["https://www.nba.com/games?date="]),
    ("CS-43", "Verification",
     "Promote the official per-date game count into every capture script as a standing check.",
     "This session caught nothing wrong with it — but only because it ran the check: the scoreboard "
     "calendar prints a game count per date, so '5 / 9 / 8 / 5 games' confirms a 27-game slate "
     "without reading a single matchup row. It is a free tripwire for a truncated capture.",
     "A: add the count check to each capture script; B: keep it in this session's capture only; "
     "C: build one shared capture module for all trees.",
     "A now, C when the trees are consolidated.",
     "None.",
     ["https://www.nba.com/games?date=2026-11-13"]),
]


def build_session_flags():
    out = []
    for fid, area, sev, item, action, sources in SESSION_FLAGS:
        out.append({
            "id": fid, "area": area, "item": item, "why": "", "action_needed": action,
            "sources": sources, "status": "Open - owner review", "severity": sev,
            "legacy_ref": "", "found_on": "2026-11-14",
        })
    return out


def build_round44_flags():
    """Flags 44-F-01..03 from session 44e0c051 (commit b769edd). They were first hand-added to
    canonical.json; they now live in data/app/flags_44e0c051.json so this assembler reproduces them.
    Loaded verbatim; nothing is recomputed."""
    with open(os.path.join(APP, "flags_44e0c051.json"), encoding="utf-8") as fh:
        return json.load(fh)


def build_session_questions():
    out = []
    for qid, cat, q, status, known, missing, nxt, sources, owner in SESSION_QUESTIONS:
        out.append({
            "id": qid, "category": cat, "question": q, "status": status,
            "known": known, "missing": missing, "next_step": nxt,
            "sources": sources, "owner": owner, "legacy_ref": "",
        })
    return out


def build_session_suggestions():
    out = []
    for sid, area, sug, why, options, rec, dep, sources in SESSION_SUGGESTIONS:
        out.append({
            "id": sid, "area": area, "suggestion": sug, "why": why, "options": options,
            "recommended_option": rec, "dependency": dep, "decision": "Awaiting owner review",
            "sources": sources, "legacy_ref": "",
        })
    return out


def main():
    # Official captures: this session's (2026-11-14, 01:05Z) plus the previous
    # session's, which is kept because the earlier pages and the repo review
    # cite it and because the two agree on every overlapping field.
    # The snapshot manifest (written by scripts/capture_official_2026_11_14c.py)
    # names which official captures the canonical build reads, so a refresh is a
    # data change and not an edit here.  Defaults reproduce the pre-manifest files.
    manifest = {}
    if os.path.exists(os.path.join(APP, "snapshot_manifest.json")):
        manifest = jload("data", "app", "snapshot_manifest.json")

    def resolved(block, fallback):
        rel = ((manifest.get(block) or {}).get("path") or "").strip()
        return jload(*(rel.split("/"))) if rel else jload(*fallback.split("/"))

    slate = resolved("slate", "data/app/official_slate_1114_1117.json")
    prior_slate = jload("data", "app", "official_slate.json")
    ratings = resolved("ratings", "data/app/official_team_ratings_2026-11-14b.json")
    injuries = resolved("injuries", "data/app/official_injuries_2026-11-13_0745PM.json")
    lab = jload("data", "app", "lab.json")
    mo = jload("data", "origin", "model_output.json")

    def optional(name):
        path = os.path.join(APP, name)
        return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None

    availability = optional("report_availability.json")
    delta = optional("snapshot_delta.json")
    results_1113 = optional("official_results_2026-11-13.json")
    counts = optional("official_counts_2026-11-14.json")
    log_provenance = None
    prov_path = os.path.join(ROOT, "data", "origin", "games_extended_provenance.json")
    if os.path.exists(prov_path):
        log_provenance = json.load(open(prov_path, encoding="utf-8"))
    superseded_ratings = superseded_injuries = None
    if manifest.get("superseded"):
        try:
            superseded_ratings = jload(*(manifest["superseded"]["ratings"].split("/")))
            superseded_injuries = jload(*(manifest["superseded"]["injuries"].split("/")))
        except (OSError, KeyError):
            pass

    prior_games = {g["game_id"]: g for g in prior_slate["games"]}
    by_gid = {g["game_id"]: g for g in slate["games"]}

    # ---- team names for the schedule rows ------------------------------
    name_of = {}
    for g in prior_slate["games"]:
        name_of[g["away"]] = g.get("away_name", g["away"])
        name_of[g["home"]] = g.get("home_name", g["home"])

    # ---- originated lines ----------------------------------------------
    lines = []
    for l in lab["lines"]:
        g = by_gid.get(l["game_id"]) or prior_games.get(l["game_id"]) or {}
        lines.append({
            "date": l["date"], "time_et": l["time_et"], "away": l["away"], "home": l["home"],
            "away_name": name_of.get(l["away"], l["away"]),
            "home_name": name_of.get(l["home"], l["home"]),
            "game_id": l["game_id"], "nba_game_url": l["nba_game_url"],
            "competition": l.get("competition") or g.get("competition", ""),
            "exp_margin": l["model_margin"], "exp_total": l["orig_total"],
            "exp_home_pts": l["proj_home_pts"], "exp_away_pts": l["proj_away_pts"],
            "orig_spread_home": l["orig_spread_home"], "orig_total": l["orig_total"],
            "eff_spread_home": l["orig_spread_home"], "eff_total": l["orig_total"],
            "total_lo": l["total_lo"], "total_hi": l["total_hi"],
            "margin_lo": l["margin_lo"], "margin_hi": l["margin_hi"],
            "p_home_win": l["p_home_win"], "p_ot": l["p_ot"],
            "p_blowout_15": l.get("p_blowout_15"),
            "pace": l["pace"], "out_count_home": l["out_count_home"],
            "out_count_away": l["out_count_away"],
            "availability_state_home": l.get("availability_state_home"),
            "availability_state_away": l.get("availability_state_away"),
            "availability_basis": l.get("availability_basis", ""),
            "reprice_after_home": l.get("reprice_after_home", ""),
            "reprice_after_away": l.get("reprice_after_away", ""),
            "out_players_home": l["out_players_home"],
            "out_players_away": l["out_players_away"],
            "fair_ml_home": l["fair_ml_home"], "fair_ml_away": l["fair_ml_away"],
            "home_reported": l.get("home_reported"), "away_reported": l.get("away_reported"),
            "source": l["source"],
            "source_label": "Official schedule + our walk-forward engine (scripts/strategy_lab.py)",
            "game_source": l["nba_game_url"],
            "note": l.get("note", ""),
        })

    # ---- selections for the window --------------------------------------
    pick_rows = []
    for p in lab["picks"]:
        pick_rows.append({
            "date": p["date"], "time_et": p["time_et"], "away": p["away"], "home": p["home"],
            "matchup": f"{p['away']} @ {p['home']}",
            "game_id": p["game_id"],
            "origin_spread": f"{p['home']} {p['orig_spread_home']:+.1f}",
            "origin_total": p["orig_total"],
            "fair_ml_home": p["fair_ml_home"], "fair_ml_away": p["fair_ml_away"],
            "model_p_home": p["p_home_win"], "confidence": "",
            "availability_flag": p["availability_flag"],
            "availability_detail": p["availability_detail"],
            "availability_states": p.get("availability_states", {}),
            "availability_basis": p.get("availability_basis", ""),
            "singles_view": p["side_lean"], "totals_view": p["totals_lean"],
            # Was a literal True for every game, which made a game with no injury
            # report at all a valid parlay leg (flag NF-62).  Now derived: a leg
            # needs both sides present on the newest official report.
            "parlay_leg_candidate": (p["availability_flag"] == "REPORTED"),
            "model_margin": p["model_margin_home"], "model_total": p["orig_total"],
            "nba_game_url": p["nba_game_url"],
            "source": p["source"],
            "source_label": "Official schedule + our originated line (scripts/strategy_lab.py); no market price is used",
            "abbreviation_corrected": True,
            "strategy_status": {},
            "pricing_note": p["pricing_note"],
            "strategy_selections": p.get("strategy_selections", []),
        })

    # ---- recompute the log's own integrity against the official GP column ----
    with open(os.path.join(ROOT, "data", "origin", "games.csv"), encoding="utf-8") as fh:
        _log_rows = list(csv.DictReader(fh))
    _gp = {}
    for _r in _log_rows:
        _gp[_r["away"]] = _gp.get(_r["away"], 0) + 1
        _gp[_r["home"]] = _gp.get(_r["home"], 0) + 1
    _bad = [f"{t}: log {own} vs official {off}" for t, off in
            ((x["team"], x["gp"]) for x in ratings["teams"])
            if _gp.get(t, 0) != off for own in [_gp.get(t, 0)]]
    log_integrity = {
        "games": len(_log_rows),
        "team_games": 2 * len(_log_rows),
        "mismatch": len(_bad),
        "detail": _bad[:10],
        "last_date": max(r["date"] for r in _log_rows) if _log_rows else None,
        "source": ((manifest.get("results_log") or {}).get("source_url")
                   or "https://www.nba.com/games?date="),
    }

    canonical = {
        "meta": {
            "title": "NBA3 — NBA Edge Lab",
            "built_utc": BUILD_UTC,
            "session": SESSION,
            "window": slate["window"],
            "as_of_note": ("Official pages were re-read on 2026-11-14 (UTC) at 09:45Z: newest "
                           "injury report 11/14 04:15 AM ET, team statistics read after the 11/13 "
                           "slate, results log through 2026-11-13 (183 games). Injury, tip-time and "
                           "stat values move during a slate; re-read the official pages before "
                           "acting. See the Report-availability page for which numbers are already "
                           "stale and when each one settles."),
            "model": {
                "results_captured": lab["meta"]["games_captured"],
                # Recomputed here, from the log and the official GP column, rather than
                # copied from an earlier session's integrity block (which described the
                # 174-game log).  See check C1 of scripts/capture_official_2026_11_14c.py.
                "team_games_official": log_integrity["team_games"],
                "mismatch": log_integrity["mismatch"],
                "mismatch_detail": log_integrity["detail"],
                "official_gp_source": ((manifest.get("ratings") or {}).get("source_url")
                                       or "https://www.nba.com/stats/teams/advanced"),
                "legacy_team_games_official": mo["integrity"]["team_games_official"],
                "legacy_mismatch": mo["integrity"]["mismatch"],
                "oos_games": lab["residuals"]["n"],
                "burn_in": lab["meta"]["burn_in"],
                "margin_rmse": lab["residuals"]["margin_rmse"],
                "margin_baseline_rmse": lab["residuals"]["margin_baseline_rmse"],
                "total_rmse": lab["residuals"]["total_rmse"],
                "total_baseline_rmse": lab["residuals"]["total_baseline_rmse"],
                "margin_bias": lab["residuals"]["margin_bias"],
                "total_bias": lab["residuals"]["total_bias"],
                "brier": lab["residuals"]["brier"],
                "brier_baseline": lab["residuals"]["brier_baseline"],
                "margin_sd": lab["residuals"]["margin_sd"],
                "total_sd": lab["residuals"]["total_sd"],
                "home_win_rate": lab["residuals"]["home_win_rate"],
                "ot_rate": lab["residuals"]["ot_rate"],
                "avg_total": lab["residuals"]["avg_total"],
            },
            "engine": {
                "name": "Walk-forward Massey margin model + shrunk scoring-environment totals model",
                "code": "scripts/strategy_lab.py",
                "shrinkage": ("Ridge penalty and totals-shrinkage weight chosen by validating on "
                              "the most recent 20% of PAST games only (select_hyperparameters)."),
                "determinism": f"Seeded (seed {lab['meta']['seed']}); two consecutive runs produce "
                               "byte-identical output, which is what makes the CI drift gate mean "
                               "anything.",
            },
        },
        "lab": lab,
        "slate": slate,
        "prior_slate": prior_slate,
        "availability": availability,
        "snapshot_delta": delta,
        "results_1113": results_1113,
        "official_counts": counts,
        "log_provenance": log_provenance,
        "manifest": manifest or None,
        "superseded": {"ratings": superseded_ratings, "injuries": superseded_injuries},
        "lines": lines,
        "picks": pick_rows,
        "props": lab["props"],
        "parlays": lab["parlays"],
        "injuries": injuries,
        "injury_impact": lab["injury_impact"],
        "ratings": ratings,
        "gameflow": lab["gameflow"],
        "correlations": lab["correlations"],
        "strategies": lab["strategies"],
        "prop_combos": lab["prop_combos"],
        "luck_test": lab["luck_test"],
        "residuals": lab["residuals"],
        "oos_sample": lab["oos_sample"],
        "gates": build_gates() + build_lab_gates(),
        "sources": build_sources(),
        "flags": build_flags() + build_session_flags() + build_round44_flags(),
        "review_findings": [
            {"id": rid, "severity": severity, "finding": item, "next_action": action,
             "sources": sources, "handling": status, "legacy_ref": rid, "found_on": "2026-11-14"}
            for (rid, severity, item, action, sources, status) in REVIEW_FINDINGS
        ],
        "questions": build_questions() + build_session_questions(),
        "suggestions": build_suggestions() + build_session_suggestions(),
        "review": build_review(),
        "requirements": cload("data", "requirements.csv"),
        "gameflow_factors": cload("data", "gameflow.csv"),
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(canonical, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    for k, v in canonical.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} rows")
        elif isinstance(v, dict):
            print(f"  {k}: {len(v)} keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
