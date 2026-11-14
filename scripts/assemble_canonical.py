#!/usr/bin/env python3
"""Assemble the canonical dataset used by the NBA3 site.

Inputs (all already verified against official sources by earlier sessions or
by this session -- see data/app/official_*.json and docs/verification_log.md):

  data/app/official_slate.json                        official schedule, 2026-11-14 read
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

BUILD_UTC = "2026-11-14T02:10Z"
SESSION = "arena/2b9f1ae1-nba3"
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
    ("R-13", "High", "A mechanical scan across the repository's HTML files found table-body rows that lack a direct official NBA/Ksa link. Earlier measurement by session 2e50a71a: 1,521 rows scanned, 423 without a direct official link (389 excluding the archived research-dashboard.html). Second independent scan on 2026-11-14 (scripts/scan_table_sources.py): 2,091 rows in 89 files, 369 without a direct official-host link.",
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
    add("CI", "Workflow coverage",
        "The workflow ran unit tests, the docs checker, the research pipeline, the edge checker and the site builders, and deployed successfully. It did not cover the canonical dataset assembled in this session.",
        "Irregularity — handled in this session",
        "Add the canonical capture/assembly/build steps and their drift checks to the workflow.",
        ["https://github.com/wingbangboozle1-lang/NBA3/actions"], "", "2026-11-14")
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
def main():
    slate = jload("data", "app", "official_slate.json")
    ratings = jload("data", "app", "official_team_ratings_2026-11-14.json")
    injuries = jload("data", "app", "official_injuries_2026-11-13_0730PM.json")
    mo = jload("data", "origin", "model_output.json")
    picks = jload("data", "picks", "picks_2026-11-14_to_16.json")

    by_gid = {g["game_id"]: g for g in slate["games"]}

    # ---- originated lines, joined to the official schedule
    lines = []
    for l in mo["lines"]:
        g = by_gid.get(l["gid"])
        if not g:
            continue
        lines.append({
            "date": l["date"], "time_et": l["time_et"], "away": l["away"], "home": l["home"],
            "away_name": g["away_name"], "home_name": g["home_name"],
            "game_id": l["gid"], "nba_game_url": g["nba_game_url"],
            "competition": g["competition"] or l.get("competition", ""),
            "exp_margin": l["exp_margin"], "exp_total": l["exp_total"],
            "exp_home_pts": l["exp_home_pts"], "exp_away_pts": l["exp_away_pts"],
            "orig_spread_home": l["orig_spread_home"], "orig_total": l["orig_total"],
            "eff_spread_home": l["eff_spread_home"], "eff_total": l["eff_total"],
            "total_lo": l["total_lo"], "total_hi": l["total_hi"],
            "margin_lo": l["margin_lo"], "margin_hi": l["margin_hi"],
            "p_home_win": l["p_home_win"], "p_ot": l["p_ot"],
            "pace": l["pace"], "out_count_home": l["out_count_home"],
            "out_count_away": l["out_count_away"],
            "out_players_home": l.get("out_players_home", []),
            "out_players_away": l.get("out_players_away", []),
            "source": g["source_url"], "source_label": "Official schedule + our walk-forward model (model/build.py)",
            "game_source": g["nba_game_url"],
        })

    # ---- picks for the 3-day window, joined to the official schedule
    pick_rows = []
    aliased = 0
    for p in picks.get("picks", []):
        away, home = [x.strip() for x in p["matchup"].split("@")]
        if away in ALIAS or home in ALIAS:
            aliased += 1
        away, home = ALIAS.get(away, away), ALIAS.get(home, home)
        p = dict(p, matchup=f"{away} @ {home}")
        m = next((l for l in lines if l["away"] == away and l["home"] == home
                  and l["date"] == p["date"]), None)
        pick_rows.append({
            "date": p["date"], "time_et": p.get("start_et", ""), "away": away, "home": home,
            "origin_spread": p.get("origin_spread", ""), "origin_total": p.get("origin_total", ""),
            "fair_ml_home": p.get("fair_ml_home"), "fair_ml_away": p.get("fair_ml_away"),
            "model_p_home": p.get("model_p_home"), "confidence": p.get("confidence", ""),
            "availability_flag": (p.get("availability") or {}).get("flag", ""),
            "availability_detail": (p.get("availability") or {}).get("detail", ""),
            "singles_view": p.get("singles_view", ""),
            "totals_view": p.get("totals_view", ""),
            "parlay_leg_candidate": p.get("parlay_leg_candidate"),
            "model_margin": m["exp_margin"] if m else None,
            "model_total": m["exp_total"] if m else None,
            "nba_game_url": m["nba_game_url"] if m else "",
            "source": (m["source"] if m else "https://www.nba.com/schedule?date=2026-11-14"),
            "source_label": "Official schedule + our originated line (model/build.py); no market price is used",
            "abbreviation_corrected": True,
            "strategy_status": picks.get("strategy_status", {}),
            "pricing_note": picks.get("pricing_note", ""),
        })

    # ---- injury impact rollup (our own model on the official report)
    impact = []
    inj_by_game = {}
    for r in injuries["rows"]:
        key = (r["game_date"], r["matchup"])
        inj_by_game.setdefault(key, []).append(r)
    mpg = {}
    for r in cload("data", "origin", "players_top_minutes.csv"):
        mpg[r["player"].strip().lower()] = float(r["min"])
    for l in lines:
        key = (l["date"], f"{l['away']}@{l['home']}")
        rows = inj_by_game.get(key, [])
        outs = [r for r in rows if r["row_type"] == "player" and r["status"] == "Out"]
        doubtful = [r for r in rows if r["row_type"] == "player"
                    and r["status"] in ("Doubtful", "Questionable", "Probable")]
        not_sub = [r for r in rows if r["row_type"] == "team_report_status"]
        vac = 0.0
        unquant = 0
        for r in outs:
            name = " ".join(reversed(r["player"].split(", "))).strip()
            m = mpg.get(name.lower())
            if m:
                vac += m
            else:
                unquant += 1
        impact.append({
            "date": l["date"], "matchup": f"{l['away']}@{l['home']}",
            "rows_listed": len([r for r in rows if r["row_type"] == "player"]),
            "out": len(outs), "doubtful_or_questionable": len(doubtful),
            "minutes_vacuum": vac if vac else None,
            "minutes_vacuum_unquantified_players": unquant,
            "teams_not_submitted": [r["team"] for r in not_sub],
            "out_players": [r["player"] for r in outs],
            "source": injuries["source_url"],
            "source_label": "Official injury report (11/13/26 07:30 PM ET) + official MPG table",
        })

    canonical = {
        "meta": {
            "title": "NBA3 — NBA Edge Lab",
            "built_utc": BUILD_UTC,
            "session": SESSION,
            "window": slate["window"],
            "as_of_note": "Official pages were read on 2026-11-14 (UTC). Injury, tip-time and stat values move during a slate.",
            "model": {
                "results_captured": mo["integrity"]["games_captured"],
                "team_games_official": mo["integrity"]["team_games_official"],
                "mismatch": mo["integrity"]["mismatch"],
                "oos_games": mo["models"]["A"]["n"],
                "margin_rmse": mo["models"]["A"]["margin"].get("rmse"),
                "margin_baseline_rmse": mo["models"]["A"]["margin_baseline_rmse"],
                "total_rmse": mo["models"]["A"]["total"].get("rmse"),
                "total_baseline_rmse": mo["models"]["A"]["total_baseline_rmse"],
                "home_court": mo["home_court"]["value"],
                "home_court_p": mo["home_court"]["p_two_sided"],
            },
        },
        "slate": slate,
        "lines": lines,
        "picks": pick_rows,
        "props": jload("data", "origin", "model_output.json")["player_props"],
        "injuries": injuries,
        "injury_impact": impact,
        "ratings": ratings,
        "gameflow": mo["game_flow"],
        "correlations": mo["correlations"],
        "strategies": build_strategies(),
        "gates": build_gates(),
        "sources": build_sources(),
        "flags": build_flags(),
        "review_findings": [
            {"id": rid, "severity": severity, "finding": item, "next_action": action,
             "sources": sources, "handling": status, "legacy_ref": rid, "found_on": "2026-11-14"}
            for (rid, severity, item, action, sources, status) in REVIEW_FINDINGS
        ],
        "questions": build_questions(),
        "suggestions": build_suggestions(),
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
