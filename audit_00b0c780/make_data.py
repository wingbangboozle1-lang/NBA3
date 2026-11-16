#!/usr/bin/env python3
"""Transcribed official values + independent checks for session arena/00b0c780-nba3.

Every number below was read with the fetch tool on 2026-11-16 (retrieval stamp
RETRIEVED) from the official pages named in its `source` field, then copied here
by hand. Nothing is inferred: where a source contradicts itself the row says so.
The arithmetic checks are recomputed by this script, not typed in.

Run:  python3 audit_00b0c780/make_data.py   (writes audit_00b0c780/data/*.json)
No network access is needed to run it; the transcriptions are the input.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"

RETRIEVED = "2026-11-16T14:30Z"
SCHEDULE_URL = "https://www.nba.com/schedule"
GAMEBOOK_BASE = "https://statsdmz.nba.com/pdfs/20261115/"
GAME_PAGE_BASE = "https://www.nba.com/game/"
INJURY_INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
INJURY_PDF_BASE = "https://ak-static.cms.nba.com/referee/injury/"

# ---------------------------------------------------------------- 9 games of 2026-11-15
# schedule: final score and state as printed on nba.com/schedule (away first).
# book: SCORE BY PERIOD rows from the official statsdmz game book (away first).
# book_summary: the one-line period summary printed at the foot of the same book.
GAMES = [
    dict(game_id="0022600236", away="IND", home="PHI", away_name="Indiana Pacers",
         home_name="Philadelphia 76ers", slug="ind-vs-phi", book="20261115_INDPHI",
         schedule=dict(away=124, home=131, state="Final"),
         book_periods=dict(away=[35, 22, 30, 37], home=[29, 29, 39, 34]),
         book_final=dict(away=124, home=131), book_summary=None,
         pr98=dict(away=[35, 22, 30, 37], home=[29, 29, 39, 34])),
    dict(game_id="0022600237", away="LAL", home="PHX", away_name="Los Angeles Lakers",
         home_name="Phoenix Suns", slug="lal-vs-phx", book="20261115_LALPHX",
         schedule=dict(away=131, home=123, state="Final"),
         book_periods=dict(away=[33, 31, 40, 27], home=[24, 30, 26, 43]),
         book_final=dict(away=131, home=123), book_summary=None,
         pr98=dict(away=[33, 31, 40, 27], home=[24, 30, 26, 43])),
    dict(game_id="0022600238", away="CHA", home="LAC", away_name="Charlotte Hornets",
         home_name="LA Clippers", slug="cha-vs-lac", book="20261115_CHALAC",
         schedule=dict(away=105, home=113, state="Final"),
         book_periods=dict(away=[21, 31, 31, 22], home=[22, 29, 33, 29]),
         book_final=dict(away=105, home=113), book_summary=None,
         pr98=dict(away=[21, 31, 31, 22], home=[22, 29, 33, 29])),
    dict(game_id="0022600239", away="SAS", home="UTA", away_name="San Antonio Spurs",
         home_name="Utah Jazz", slug="sas-vs-uta", book="20261115_SASUTA",
         schedule=dict(away=110, home=102, state="Final"),
         book_periods=dict(away=[31, 27, 23, 29], home=[33, 22, 26, 21]),
         book_final=dict(away=110, home=102), book_summary=None,
         pr98=dict(away=[31, 27, 23, 29], home=[33, 22, 26, 21])),
    dict(game_id="0022600240", away="DAL", home="BOS", away_name="Dallas Mavericks",
         home_name="Boston Celtics", slug="dal-vs-bos", book="20261115_DALBOS",
         schedule=dict(away=94, home=131, state="Final"),
         book_periods=dict(away=[9, 28, 34, 23], home=[42, 25, 37, 27]),
         book_final=dict(away=94, home=131), book_summary=None, pr98=None),
    dict(game_id="0022600241", away="NYK", home="TOR", away_name="New York Knicks",
         home_name="Toronto Raptors", slug="nyk-vs-tor", book="20261115_NYKTOR",
         schedule=dict(away=112, home=108, state="Final/OT"),
         book_periods=dict(away=[23, 24, 20, 28, 17], home=[17, 26, 31, 21, 13]),
         book_final=dict(away=112, home=108), book_summary=None, pr98=None),
    dict(game_id="0022600242", away="HOU", home="WAS", away_name="Houston Rockets",
         home_name="Washington Wizards", slug="hou-vs-was", book="20261115_HOUWAS",
         schedule=dict(away=147, home=119, state="Final"),
         book_periods=dict(away=[36, 37, 46, 28], home=[31, 23, 34, 31]),
         book_final=dict(away=147, home=119), book_summary=None, pr98=None),
    # ATL @ MIL: the book's period TABLE prints Q3 = 37 for Milwaukee, but its one-line
    # summary prints Q3 = 27. Only 27 reproduces the printed final of 106.
    dict(game_id="0022600243", away="ATL", home="MIL", away_name="Atlanta Hawks",
         home_name="Milwaukee Bucks", slug="atl-vs-mil", book="20261115_ATLMIL",
         schedule=dict(away=113, home=106, state="Final"),
         book_periods=dict(away=[18, 37, 32, 26], home=[37, 16, 37, 26]),
         book_summary_home=[37, 16, 27, 26],
         book_final=dict(away=113, home=106), book_summary=None, pr98=None),
    dict(game_id="0022600244", away="OKC", home="SAC", away_name="Oklahoma City Thunder",
         home_name="Sacramento Kings", slug="okc-vs-sac", book="20261115_OKCSAC",
         schedule=dict(away=125, home=103, state="Final"),
         book_periods=dict(away=[32, 30, 32, 31], home=[24, 26, 30, 23]),
         book_final=dict(away=125, home=103), book_summary=None, pr98=None),
]


def _sum(xs):
    return sum(xs)


def check_game(g: dict) -> dict:
    """Recompute every arithmetic and cross-source check for one game."""
    out = {"game_id": g["game_id"], "matchup": f'{g["away"]} @ {g["home"]}'}
    per = g["book_periods"]
    # OT columns are the trailing entry when the book has five numbers (4 quarters + OT).
    ot = {side: (len(v) == 5) for side, v in per.items()}
    out["ot"] = ot["away"] or ot["home"]
    tot = {side: _sum(v[:4]) + (v[4] if len(v) == 5 else 0) for side, v in per.items()}
    out["book_sum_equals_printed_final"] = {
        side: tot[side] == g["book_final"][side] for side in ("away", "home")}
    out["schedule_equals_book_final"] = {
        side: g["schedule"][side] == g["book_final"][side] for side in ("away", "home")}
    out["book_final_equals_schedule_final"] = out["schedule_equals_book_final"]
    if "book_summary_home" in g:
        summary = g["book_summary_home"]
        out["period_table_vs_summary_conflict"] = {
            "table_home_periods": per["home"][:4], "summary_home_periods": summary,
            "conflicting_periods": [i + 1 for i in range(4) if per["home"][i] != summary[i]],
            "summary_sum_equals_final": _sum(summary) == g["book_final"]["home"],
            "table_sum_equals_final": _sum(per["home"][:4]) == g["book_final"]["home"],
        }
    if g.get("pr98") is not None:
        out["main_or_pr98"] = {
            "pr98_periods_equal_book": g["pr98"]["away"] == per["away"][:4] and g["pr98"]["home"] == per["home"][:4],
        }
    return out


def settlement_status(g: dict, chk: dict) -> str:
    # The final is confirmed when the schedule agrees with the book's printed FINAL and the
    # quarter sum reproduces it. Where the book's period TABLE conflicts with its own summary
    # line, the summary line is the one that must reproduce the final; the conflict is flagged.
    if "period_table_vs_summary_conflict" in chk:
        summary_ok = chk["period_table_vs_summary_conflict"]["summary_sum_equals_final"]
        finals_ok = summary_ok and all(chk["schedule_equals_book_final"].values())
    else:
        finals_ok = all(chk["book_sum_equals_printed_final"].values()) and all(chk["schedule_equals_book_final"].values())
    if not finals_ok:
        return "NOT VERIFIED - final scores disagree between sources"
    if "period_table_vs_summary_conflict" in chk:
        return "FINAL VERIFIED - quarter split CONFLICTING inside the official book (flag K-02)"
    return "VERIFIED - final and quarter scores agree across both official reads"


def build_finals() -> dict:
    rows = []
    for g in GAMES:
        chk = check_game(g)
        row = {
            "date": "2026-11-15",
            "game_id": g["game_id"],
            "away": g["away"], "home": g["home"],
            "away_name": g["away_name"], "home_name": g["home_name"],
            "state_on_schedule": g["schedule"]["state"],
            "away_final": g["book_final"]["away"], "home_final": g["book_final"]["home"],
            "away_periods_book": g["book_periods"]["away"],
            "home_periods_book": g["book_periods"]["home"],
            "checks": chk,
            "status": settlement_status(g, chk),
            "on_main_results_feed": False,
            "on_pr98_branch": g["pr98"] is not None,
            "sources": [
                {"label": "nba.com schedule (final score, state)", "url": SCHEDULE_URL,
                 "retrieved": RETRIEVED},
                {"label": "nba.com game page", "url": GAME_PAGE_BASE + f'{g["slug"]}-{g["game_id"]}',
                 "retrieved": RETRIEVED},
                {"label": "NBA official game book (statsdmz PDF)", "url": GAMEBOOK_BASE + g["book"] + ".pdf",
                 "retrieved": RETRIEVED},
            ],
        }
        rows.append(row)
    return {
        "schema": "audit_00b0c780/finals_1115/v1",
        "retrieved": RETRIEVED,
        "purpose": ("Independent read of the nine 2026-11-15 finals. Not a settlement: nothing here "
                    "is written to data/live, data/app or ledger/. Settlement stays with the owners "
                    "of PR #98 and the scheduled refresh."),
        "counts": {
            "games": len(rows),
            "verified": sum(1 for r in rows if r["status"].startswith("VERIFIED")),
            "final_verified_quarter_conflict": sum(1 for r in rows if "CONFLICTING" in r["status"]),
            "not_verified": sum(1 for r in rows if r["status"].startswith("NOT")),
            "on_main_results_feed": sum(1 for r in rows if r["on_main_results_feed"]),
            "on_pr98_branch": sum(1 for r in rows if r["on_pr98_branch"]),
        },
        "games": rows,
    }


# ---------------------------------------------------------------- injury index 2026-11-16
def _index_times():
    """Every 15-minute slot from 12:00 AM to 9:30 AM ET. The official index (fetched 2026-11-16) lists 39 of them:
    12:00 AM through 9:30 AM, one link each, and the page states no others."""
    out = []
    for minutes in range(0, 9 * 60 + 31, 15):  # minutes after midnight, 0 .. 570 inclusive = 39 slots
        h24, m = divmod(minutes, 60)
        out.append((h24 % 12 or 12, m, "AM"))
    return out


def build_injury_index() -> dict:
    reports = []
    for hour12, minute, ap in _index_times():
        name = f"Injury-Report_2026-11-16_{hour12:02d}_{minute:02d}{ap}.pdf"
        reports.append({"revision_et": f"2026-11-16 {hour12}:{minute:02d} {ap} ET",
                        "pdf_url": INJURY_PDF_BASE + name,
                        "pdf_listed_on_official_index": True,
                        "pdf_fetched_in_this_session": False})
    return {
        "schema": "audit_00b0c780/injury_index/v1",
        "retrieved": RETRIEVED,
        "source": {"label": "NBA official injury report index (2026-27 season)", "url": INJURY_INDEX_URL},
        "listing_stops_at": "2026-11-16 9:30 AM ET",
        "reports_listed_for_2026_11_16": len(reports),
        "newest_listed": reports[-1]["revision_et"],
        "published_on_main": {
            "banner_revision_time": "2026-11-15 06:15 AM ET",
            "banner_retrieval_times": ["2026-11-15T11:40Z", "2026-11-15T11:33Z"],
            "source": "app/injuries.html lines 36-39 on main",
            "note": "The banner prints two different retrieval stamps (11:40Z and 11:33Z).",
        },
        "gap": ("The newest listed report (9:30 AM ET 11/16) is newer than the banner's revision "
                "time (06:15 AM ET 11/15). The PDFs themselves were NOT captured or parsed here."),
        "reports": reports,
    }


# ---------------------------------------------------------------- ledger picks on 2026-11-15
def build_ledger_check() -> dict:
    """Published 11/15 moneyline picks read against the official finals. Read-only; not a settlement."""
    picks = []
    finals = {g["game_id"]: g for g in GAMES}
    with open(ROOT / "ledger" / "ledger.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            p = row["pick"]
            if p["date"] != "2026-11-15":
                continue
            g = finals[p["game_id"]]
            text = p["pick"]
            if text.endswith("moneyline"):
                team = text.split()[0]
                winner = g["away"] if g["book_final"]["away"] > g["book_final"]["home"] else g["home"]
                outcome = "WIN (official final)" if team == winner else "LOSS (official final)"
            else:
                outcome = "not evaluated (non-moneyline pick)"
            picks.append({
                "seq": row["seq"], "pick_id": p.get("strategy_id"), "game_id": p["game_id"],
                "matchup": p["matchup"], "pick": text, "published_utc": row["published_utc"],
                "tip_et_iso": p["tip_et_iso"], "official_final": f'{g["away"]} {g["book_final"]["away"]} - '
                f'{g["home"]} {g["book_final"]["home"]}', "outcome_if_settled": outcome,
                "entry_hash": row["entry_hash"],
                "published_before_tip": row["published_utc"] < p["tip_et_iso"],
                "sources": [{"label": "nba.com schedule", "url": SCHEDULE_URL, "retrieved": RETRIEVED},
                            {"label": "statsdmz game book", "url": GAMEBOOK_BASE + g["book"] + ".pdf",
                             "retrieved": RETRIEVED}],
            })
    return {
        "schema": "audit_00b0c780/ledger_check_1115/v1",
        "retrieved": RETRIEVED,
        "note": ("Read-only. The sealed ledger (ledger/ledger.jsonl) has 0 settlement entries on main; "
                 "these outcomes are shown for the owner to confirm, not written to the chain."),
        "picks": picks,
    }


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payloads = {
        "finals_1115.json": build_finals(),
        "injury_index_2026-11-16.json": build_injury_index(),
        "ledger_check_1115.json": build_ledger_check(),
    }
    for name, obj in payloads.items():
        (DATA / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", DATA / name)


# ---------------------------------------------------------------- requirement register
# Each row: the brief item, a status drawn from STATUSES, what the repo actually contains
# (evidence paths; `contains` is a literal substring the test checks is present in the file,
# or None for existence only), what is missing, and the next owner action.
STATUSES = [
    "Met", "Met (partly)", "Built, stale", "Built, failing", "Built, negative result",
    "Built, one-day input", "Not met", "Blocked (external)",
]

REQUIREMENTS = [
    dict(id="R01", item="Collect, organise and analyse NBA data", status="Met (partly)",
         evidence=[{"path": "data/app/official_team_stats_2026-11-15.json", "contains": '"traditional"'},
                   {"path": "data/app/player_game_logs.json", "contains": '"coverage_note"'}],
         gap="Standings are not captured by any job (see K-07). Per-player logs cover 11/14 only (K-10).",
         next="Add a standings fetch to the scheduled job; extend game-book capture to every final.",
         official=["https://www.nba.com/stats/teams/traditional?Season=2026-27&SeasonType=Regular%20Season"]),
    dict(id="R02", item="Scheduled job refreshes schedule, standings, team stats and injury report per slate; rebuild only after freshness and provenance gates pass",
         status="Built, failing",
         evidence=[{"path": "scripts/refresh_official.py", "contains": "INJ_INDEX"},
                   {"path": ".github/workflows/refresh.yml", "contains": "scripts/refresh_official.py"},
                   {"path": "scripts/freshness_gates.py", "contains": None}],
         gap=("Run 43864808752 failed at the commit step; run 43815576157 also failed (K-01). Standings missing (K-07). "
              "Published window is one day behind (K-04)."),
         next="Diagnose the commit-step failure from the run log; then rerun the scheduled job.",
         official=["https://official.nba.com/nba-injury-report-2026-27-season/"]),
    dict(id="R03", item="Keep an official per-game result feed current; settle only after final scores are verified; one row per game (date, teams, final, quarter scores)",
         status="Met (partly)",
         evidence=[{"path": "data/app/results_feed.json", "contains": '"settled_count": 14'},
                   {"path": "scripts/build_results_feed.py", "contains": None}],
         gap=("14 settled rows on main, none for 2026-11-15 (K-03). 2026-11-13 rows carry no quarter scores "
              "(see the feed's own quarter_check field)."),
         next="Settle the nine 11/15 finals after both official reads agree (K-02 quarter conflict to be resolved first).",
         official=["https://www.nba.com/schedule", "https://statsdmz.nba.com/pdfs/20261115/20261115_INDPHI.pdf"]),
    dict(id="R04", item="Store every injury PDF with its timestamp and diff consecutive reports to detect status changes",
         status="Met (partly)",
         evidence=[{"path": "scripts/injury_archive.py", "contains": None},
                   {"path": "scripts/injury_delta_0415am.py", "contains": None}],
         gap="Only a selection of reports is stored; the official index lists 39 reports for 11/16 alone (K-12).",
         next="Archive every listed PDF with its revision time and sha256; diff each consecutive pair.",
         official=[INJURY_INDEX_URL]),
    dict(id="R05", item="Freeze a pre-registration file per strategy before its first bet (signal, thresholds, universe, exact settlement rule)",
         status="Met (partly)",
         evidence=[{"path": "scripts/ledger.py", "contains": "already frozen; pre-registration is write-once"},
                   {"path": "prereg/S2_ESTIMATOR_DISAGREEMENT.json", "contains": None}],
         gap="Two pre-registration sets exist (prereg/ with 3 files, data/app/prereg/ with 15). Which one is binding is not stated.",
         next="Name one authoritative prereg directory and point the other at it.",
         official=[]),
    dict(id="R06", item="Tamper-evident ledger: hash each published pick, publish the hash before tip, verify after settlement",
         status="Met (partly)",
         evidence=[{"path": "ledger/ledger.jsonl", "contains": '"kind": "PUBLISH"'},
                   {"path": "ledger/index.json", "contains": '"verified": true'}],
         gap="Publish side works (2026-11-15 entries stamped 12:10Z, before the 18:00Z tip). Zero settlements on main (K-03).",
         next="Settle through the ledger's own settle() once K-02 is resolved.",
         official=["https://www.nba.com/schedule"]),
    dict(id="R07", item="Split the site into 'projection' (safe to publish now) and 'bet' (gated) surfaces, never mixed",
         status="Met (partly)",
         evidence=[{"path": "index.html", "contains": "Bet surface (gated)"},
                   {"path": "projection/index.html", "contains": None},
                   {"path": "bet/index.html", "contains": None}],
         gap="The split is by navigation group. This audit did not verify that a bet-gated number never appears on a projection page.",
         next="Add a build check that scans projection/ for bet-only fields.",
         official=[]),
    dict(id="R08", item="Keep two independent estimators and publish their disagreement as the primary confidence signal",
         status="Met (partly)",
         evidence=[{"path": "scripts/estimators.py", "contains": "disagreement_pp"},
                   {"path": "data/app/estimators.json", "contains": None}],
         gap="The disagreement is carried in picks and the ledger headline, not on the landing page (see R13).",
         next="Show the disagreement as the first number on the projection index.",
         official=[]),
    dict(id="R09", item="Pin home-court advantage to the measured home-win rate instead of fitting it freely",
         status="Met",
         evidence=[{"path": "scripts/estimators.py", "contains": "def pinned_hca"}],
         gap="None found at code level.", next="None.", official=[]),
    dict(id="R10", item="Report luck as a z-score per team; refuse to publish a strategy that leans on a team outside the noise band",
         status="Met (partly)",
         evidence=[{"path": "pipeline/v2/stats.py", "contains": "def noise_band"},
                   {"path": "pipeline/v2/build.py", "contains": "noise_band("}],
         gap=("Z-scores and the band are computed and displayed. No strategy-level refusal rule that uses the band "
              "was found in the code paths read."),
         next="Add an explicit gate: a strategy with a team outside the band is not published.",
         official=[]),
    dict(id="R11", item="Compute rest, back-to-back and 3-in-4 from the official schedule; add travel distance from a sourced arena-coordinate table",
         status="Built, stale",
         evidence=[{"path": "scripts/rest_travel.py", "contains": None},
                   {"path": "data/app/arena_coordinates.json", "contains": "from Wikipedia"}],
         gap="Arena coordinates come from Wikipedia, not an official source (K-06). Two arenas are blank.",
         next="Source coordinates from an official or venue-operator page, or mark distances unverified.",
         official=["https://www.nba.com/schedule"]),
    dict(id="R12", item="Model minutes redistribution: top-8 minutes shares per team and replacement shares when a player is out",
         status="Built, one-day input",
         evidence=[{"path": "scripts/minutes_model.py", "contains": "replacement_share_from_out_players"},
                   {"path": "data/app/minutes_shares.json", "contains": None}],
         gap="Top-8 shares prefer the 2026-11-14 game-book measurement and fall back to a season snapshot where a team is missing (K-09).",
         next="Measure shares over every completed game in the window, not one day.",
         official=["https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf"]),
    dict(id="R13", item="Stop publishing a single blended rating as the headline; headline the estimator disagreement, blend underneath",
         status="Met (partly)",
         evidence=[{"path": "ledger/ledger.jsonl", "contains": '"headline_signal": "disagreement'},
                   {"path": "index.html", "contains": "We originate our own NBA lines"}],
         gap="The landing page headline is the origination sentence and inventory counts, not the disagreement.",
         next="Make the disagreement the landing page's first figure.",
         official=[]),
    dict(id="R14", item="Price every parlay with the measured rho and print the naive product next to it",
         status="Met (partly)",
         evidence=[{"path": "pipeline/v2/pricing.py", "contains": "naive"},
                   {"path": "app/parlays.html", "contains": "Naive product"}],
         gap="The measured rho depends on per-player logs, which exist for 11/14 only (K-10).",
         next="Extend player logs, then re-measure rho.", official=[]),
    dict(id="R15", item="Put rotation availability on the picks page as its own column",
         status="Met",
         evidence=[{"path": "app/picks.html", "contains": "Rotation availability"}],
         gap="None found at page level.", next="None.", official=[]),
    dict(id="R16", item="Market-anchored prior: blend the model line with the closing line, weighted by measured out-of-sample log-loss",
         status="Blocked (external)",
         evidence=[{"path": "pipeline/v2/strategies.py", "contains": "there is no closing line in this repository"}],
         gap="No closing line and no licensed odds feed exist in the repository (K-08).",
         next="Obtain a licensed odds feed or owner-captured closing prices under their terms.", official=[]),
    dict(id="R17", item="Model the total as possessions × points-per-possession, not as an average of team scoring averages",
         status="Built, negative result",
         evidence=[{"path": "pipeline/v2/build.py", "contains": "possession x PPP total RMSE"}],
         gap="The possession formulation does not beat the naive baseline (flag FV2-08, K-11).",
         next="Publish as a negative result; improve pace estimation before any total is priced.", official=[]),
    dict(id="R18", item="Show the injury-report revision time and retrieval time in the Injuries page banner",
         status="Built, stale",
         evidence=[{"path": "app/injuries.html", "contains": "retrieval time"}],
         gap=("The banner shows the 2026-11-15 06:15 AM report while the official index lists reports to 9:30 AM ET "
              "on 11/16 (K-05). It prints two retrieval stamps, 11:40Z and 11:33Z."),
         next="Re-point the banner to the newest listed report; print one retrieval stamp.",
         official=[INJURY_INDEX_URL]),
    dict(id="R19", item="Settle the sealed ledger from official finals as soon as each game day ends; keep the settlement stamp visible",
         status="Not met",
         evidence=[{"path": "app/settlement.html", "contains": "settled at"},
                   {"path": "ledger/index.json", "contains": '"settled": 0'}],
         gap="Nine 11/15 games are Final; the ledger on main has zero settlements (K-03).",
         next="Settle 11/15 (after K-02) and show the stamp on the settlement page.",
         official=["https://www.nba.com/schedule"]),
    dict(id="R20", item="Re-read the three official team-stat pages (traditional, opponent, advanced) and re-cut the model inputs",
         status="Met (partly)",
         evidence=[{"path": "data/app/official_team_stats_2026-11-15.json", "contains": '"advanced"'}],
         gap="The three pages were captured for 2026-11-15; a re-cut of the published model inputs from them was not confirmed.",
         next="Confirm which model run consumes this capture and record it.",
         official=["https://www.nba.com/stats/teams/advanced?Season=2026-27&SeasonType=Regular%20Season"]),
    dict(id="R21", item="Capture per-player game logs (minutes, points, rebounds, assists, opponent) for at least the players on an injury report",
         status="Met (partly)",
         evidence=[{"path": "data/app/player_game_logs.json", "contains": '"count": 173'}],
         gap="173 rows, all from 2026-11-14. Players on teams that did not play 11/14 are absent (K-10).",
         next="Append every completed game's book, as the scheduled job is meant to do.",
         official=["https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf"]),
    dict(id="R22", item="Originate own NBA lines; research strategies; run a leaderboard with rewards; cover single bets, parlays and player-prop combos; validation gates; correlations",
         status="Met (partly)",
         evidence=[{"path": "app/leaderboard.html", "contains": None},
                   {"path": "app/strategies.html", "contains": None},
                   {"path": "app/correlations.html", "contains": None}],
         gap=("Screened board only: no strategy is funded (requirements.csv RQ03/RQ04). Player-prop pricing is absent "
              "without per-player logs (see app/parlays.html)."),
         next="Owner decision on the reward schedule; capture logs before pricing props.", official=[]),
    dict(id="R23", item="Generate picks for every upcoming slate up to three days in advance using the originated lines",
         status="Built, stale",
         evidence=[{"path": "data/app/snapshot_manifest.json", "contains": '"from": "2026-11-15"'}],
         gap="The window starts 2026-11-15, a day already played, while today is 2026-11-16 (K-04).",
         next="Roll the window to 2026-11-16 → 2026-11-19 through the gated refresh.",
         official=["https://www.nba.com/schedule"]),
    dict(id="R24", item="Track how injuries could affect rotation minutes and production; provide game-flow analysis",
         status="Met (partly)",
         evidence=[{"path": "scripts/minutes_model.py", "contains": "top8"},
                   {"path": "app/gameflow.html", "contains": None}],
         gap="Minutes are modelled. Production (points, rebounds, assists) is not modelled from the injury; no code path found.",
         next="Add a production model fitted on the captured logs, or state it as not built.", official=[]),
    dict(id="R25", item="Create an executive summary outlining the important details",
         status="Met (partly)", evidence=[{"path": "app/summary.html", "contains": None}],
         gap="Page present; content not re-read in this audit. The window it summarises is stale (K-04).", next="Refresh with the window; re-read the page.", official=[]),
    dict(id="R26", item="Make suggestions on how to improve the site and create a suggestions section to review before implementing",
         status="Met (partly)", evidence=[{"path": "app/suggestions.html", "contains": None}],
         gap="Page present; content not re-read in this audit.", next="Owner review.", official=[]),
    dict(id="R27", item="A clear list of questions, information and answers that must be addressed before any decision; suggestions to discover missing information",
         status="Met (partly)", evidence=[{"path": "app/questions.html", "contains": None}],
         gap="Page present; content not re-read in this audit.", next="Owner review.", official=[]),
    dict(id="R28", item="Repo review line by line with official links for manual review; flag irregularities",
         status="Met (partly)",
         evidence=[{"path": "app/review.html", "contains": None}, {"path": "app/flagged.html", "contains": None}],
         gap="The existing review was not re-read in full here. This audit adds K-01…K-16.",
         next="Merge this register into the Flagged page at integration.", official=[]),
    dict(id="R29", item="GitHub Pages site: clean landing page and category subpages; every table row links an official source; unverified values blank and flagged",
         status="Met (partly)",
         evidence=[{"path": "index.html", "contains": "Verified official rows"}],
         gap="The landing page is dense (overview, projection, bet, verification and archive groups). Source-link coverage per page was not re-checked in this audit.",
         next="Keep the landing to one screen; enforce the source-link check on every table.",
         official=[]),
    dict(id="R30", item="Parallel sessions coordinate on COORDINATION.md; PR, merge and Pages deploy",
         status="Met (partly)",
         evidence=[{"path": "COORDINATION.md", "contains": "Session `arena/00b0c780-nba3`"}],
         gap="Five PRs are open over shared outputs (K-15). Pages deploy is confirmed only after the merge.",
         next="Integration owner to merge in dependency order.", official=[]),
]

# ---------------------------------------------------------------- flagged-for-review register
FLAGS = [
    dict(id="K-01", severity="high", title="Scheduled refresh failing at the commit step",
         detail=("Recent scheduled `official data refresh` runs failed. Run 43864808752 (about 2 h before this audit, "
                 "19 s) failed at the step 'Commit refreshed captures and rebuilt outputs', read from the GitHub API. "
                 "Run 43815576157 (about 8 h, 18 s) also failed; its failing step was not read. The run log could not "
                 "be fetched with the tools in this session, so the cause is not established. The run before them, "
                 "43776978055, succeeded."),
         sources=["https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43864808752",
                  "https://github.com/wingbangboozle1-lang/NBA3/actions/runs/43815576157",
                  "https://github.com/wingbangboozle1-lang/NBA3/blob/main/.github/workflows/refresh.yml"],
         owner="refresh-job owner; PR #102 (arena/07f22dad-nba3) touches the same area", blocks="publishing a fresh window"),
    dict(id="K-02", severity="medium", title="ATL @ MIL game book contradicts itself on Milwaukee Q3",
         detail=("The period table prints 37 for Milwaukee in Q3; the summary line prints 27. Only 27 reproduces the "
                 "printed FINAL of 106. The final is confirmed by the schedule, the summary line and the sum of the "
                 "Bucks' player points in the same book. The Q3 split is therefore unresolved and must not be "
                 "settled as a quarter-level result until a third read settles it."),
         sources=["https://statsdmz.nba.com/pdfs/20261115/20261115_ATLMIL.pdf", "https://www.nba.com/schedule"],
         owner="results-feed owner; a third official read of the game page LINESCORE", blocks="quarter-level settlement of ATL @ MIL"),
    dict(id="K-03", severity="high", title="Five 11/15 finals are unsettled on main; PR #98 settles four",
         detail=("All nine 2026-11-15 games are Final on the official schedule. Main's result feed has no 11/15 rows and the "
                 "ledger has zero settlements. Open PR #98 (arena/c94a5531-nba3) settles IND@PHI, LAL@PHX, CHA@LAC and "
                 "SAS@UTA; its values match this audit's independent reads exactly. DAL@BOS, NYK@TOR, HOU@WAS, ATL@MIL and "
                 "OKC@SAC are settled nowhere. The two published 11/15 moneyline picks (PHI, HOU) would both settle as wins."),
         sources=["https://www.nba.com/schedule", "https://github.com/wingbangboozle1-lang/NBA3/pull/98"],
         owner="PR #98 owner (c94a5531) or the next refresh", blocks="R19 settlement stamp"),
    dict(id="K-04", severity="high", title="Published window starts on a day already played",
         detail=("The published window is 2026-11-15 → 2026-11-18 (snapshot manifest and landing page). Today is "
                 "2026-11-16 UTC and all nine 11/15 games are Final. The window should roll to 11/16 → 11/19."),
         sources=["https://wingbangboozle1-lang.github.io/NBA3/", "https://www.nba.com/schedule"],
         owner="manifest / integration owner", blocks="R23 window"),
    dict(id="K-05", severity="high", title="Injuries banner is a day behind and prints two retrieval stamps",
         detail=("The banner shows revision 2026-11-15 06:15 AM ET. The official index lists 39 reports for 2026-11-16, "
                 "the newest at 9:30 AM ET. An earlier read of the same index in this session recorded 27 reports to 9:15 AM; "
                 "the page as fetched for this audit lists 39, so the index changed during the session or the earlier count was wrong (recorded, not resolved). "
                 "The banner prints retrieval 2026-11-15T11:40Z in one place and 11:33Z in another."),
         sources=[INJURY_INDEX_URL, "https://wingbangboozle1-lang.github.io/NBA3/app/injuries.html"],
         owner="injury-page owner", blocks="R18"),
    dict(id="K-06", severity="medium", title="Arena coordinates are sourced from Wikipedia, not an official source",
         detail=("data/app/arena_coordinates.json states its source as Wikipedia article coordinates and says the NBA does "
                 "not publish coordinates. The brief requires official sources. Two arenas have no coordinates and are blank. "
                 "Every travel distance inherits this gap."),
         sources=["https://en.wikipedia.org/w/api.php?action=query&prop=coordinates&format=json"],
         owner="rest/travel owner", blocks="R11 travel distance as verified"),
    dict(id="K-07", severity="high", title="Standings are not captured by the scheduled job",
         detail=("scripts/refresh_official.py fetches the injury index, schedule and results pages, game books and the three "
                 "team-stat pages. It has no standings URL (zero matches for 'standings'). The brief requires standings."),
         sources=["https://www.nba.com/standings", "https://github.com/wingbangboozle1-lang/NBA3/blob/main/scripts/refresh_official.py"],
         owner="refresh-job owner", blocks="R01, R02 completeness"),
    dict(id="K-08", severity="high", title="No closing line or odds feed; market-anchored prior cannot be built",
         detail=("pipeline/v2/strategies.py states there is no closing line in the repository and no licensed odds feed. "
                 "The NBA terms restrict gambling use of NBA statistics (flagged on the site as NF-12)."),
         sources=["https://www.nba.com/termsofuse"],
         owner="owner decision on a licensed feed; counsel", blocks="R16"),
    dict(id="K-09", severity="medium", title="Top-8 minute shares measured from a single day",
         detail=("scripts/minutes_model.py prefers top-8 shares measured from the 2026-11-14 game books (five games) "
                 "and falls back to a season snapshot where a team is missing. The measured shares rest on one slate."),
         sources=["https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf"],
         owner="minutes-model owner", blocks="R12 as a rate"),
    dict(id="K-10", severity="high", title="Per-player logs cover one day, not every injury-report player",
         detail=("data/app/player_game_logs.json has 173 rows, all from 2026-11-14 (five games, ten teams). The coverage note "
                 "says players on teams that did not play that day are absent, which is 20 of 30 teams. Props and rho cannot be "
                 "measured for those teams from this capture."),
         sources=["https://statsdmz.nba.com/pdfs/20261114/20261114_DENNOP.pdf"],
         owner="game-log owner", blocks="R14, R21, prop pricing"),
    dict(id="K-11", severity="medium", title="Possession × PPP totals model does not beat the baseline",
         detail=("pipeline/v2/build.py flags FV2-08: the total RMSE does not beat the naive baseline of about 18.0. "
                 "The model is published as a negative result."),
         sources=["https://github.com/wingbangboozle1-lang/NBA3/blob/main/pipeline/v2/build.py"],
         owner="models owner", blocks="R17 as a usable signal"),
    dict(id="K-12", severity="high", title="Not every injury PDF is stored",
         detail=("The official index lists 39 reports for 11/16 alone. The repository stores a selection of 11/13–11/15 "
                 "reports. The brief requires every PDF stored with its timestamp."),
         sources=[INJURY_INDEX_URL],
         owner="injury-archive owner", blocks="R04"),
    dict(id="K-13", severity="medium", title="Two results feeds and two ledgers exist",
         detail=("data/live/results/ and data/app/results_feed.json are separate feeds; ledger/ and data/app/ledger/ are "
                 "separate chains. Two sources of truth invite disagreement."),
         sources=["https://github.com/wingbangboozle1-lang/NBA3/tree/main/data"],
         owner="integration owner", blocks="single settlement record"),
    dict(id="K-14", severity="medium", title="Two pre-registration sets exist",
         detail=("prereg/ holds three strategy files and data/app/prereg/ holds fifteen. The binding set is not named."),
         sources=["https://github.com/wingbangboozle1-lang/NBA3/tree/main/prereg"],
         owner="pre-registration owner", blocks="R05 authority"),
    dict(id="K-15", severity="medium", title="Five open PRs touch shared outputs",
         detail=("Open PRs #94, #95, #96, #98 and #102 change shared files (data/app, app/, pages.yml, COORDINATION.md). "
                 "Merging them in any order risks conflicts."),
         sources=["https://github.com/wingbangboozle1-lang/NBA3/pulls"],
         owner="integration owner", blocks="clean integration"),
    dict(id="K-16", severity="low", title="Landing page leads with counts, not the disagreement headline",
         detail=("The landing page opens with the origination sentence and tile counts. The ledger headline is the "
                 "disagreement, but the page does not show it first (see R13)."),
         sources=["https://wingbangboozle1-lang.github.io/NBA3/"],
         owner="site owner", blocks="R13"),
    dict(id="K-17", severity="high", title="Two ledger trees with different schemas; the second cannot be hash-verified",
         detail=("ledger/ledger.jsonl (11 PUBLISH entries) verifies: every prev_hash, entry_hash and pick_sha256 recomputes. "
                 "data/app/ledger/ledger.jsonl (34 lines, body/entry_hash schema) keeps an unbroken prev_hash link on every line, "
                 "but its entry_hash does not recompute from its body under four canonical forms tried in this audit, so the hash "
                 "recipe is undocumented. The 0022600238-side-proj entry (line 3) is PUBLISHED_PRE_TIP and is not a linkage break. "
                 "The 'CHAIN BROKEN' note on PR #102 was not reproduced as a linkage break; its verifier is not in the repo. "
                 "Do not settle from tree B until its recipe is documented and it is re-verified."),
         sources=["https://github.com/wingbangboozle1-lang/NBA3/pull/102",
                  "https://github.com/wingbangboozle1-lang/NBA3/blob/main/data/app/ledger/ledger.jsonl",
                  "https://github.com/wingbangboozle1-lang/NBA3/blob/main/ledger/ledger.jsonl"],
         owner="ledger owner (session that wrote data/app/ledger)", blocks="R06, R19"),
]


def build_requirements() -> dict:
    return {"schema": "audit_00b0c780/requirements/v1", "retrieved": RETRIEVED,
            "statuses": STATUSES,
            "note": ("Brief items extracted from the task text, in order. Status is what the repository "
                     "shows at this commit; evidence paths are checked by test_audit.py."),
            "items": REQUIREMENTS}


def build_flags() -> dict:
    return {"schema": "audit_00b0c780/flags/v1", "retrieved": RETRIEVED,
            "note": "Irregularities found by this session. None is fixed in place; each has an owner.",
            "items": FLAGS}


def main_extra() -> None:
    for name, obj in (("requirements.json", build_requirements()), ("flags.json", build_flags())):
        (DATA / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", DATA / name)


if __name__ == "__main__":
    main()
    main_extra()
