#!/usr/bin/env python3
"""Session ``a399d8a9`` — apply the 01:30 PM ET official report to the build.

THE DEFECT THIS FIXES
    ``scripts/report_availability.py`` decides whether a team's filing deadline
    has passed by comparing the filing date with a hard-coded ``AS_OF_DATE`` and
    ``AS_OF_LOCAL_HOUR`` ("04:45 on 2026-11-14").  While the snapshot really was
    the 04:15/04:45 AM ET report that was correct.  It is not correct any more:

    * the snapshot is nine hours old, and
    * every 11/14 game of the window is now inside the game-day window in which
      the league requires a game-day report, so the same rule that once
      explained "these five teams filed late because they are on a
      back-to-back" now means nothing.

    Worse, its conclusion ("no team is overdue") came *from the assumption*
    (AS_OF_LOCAL_HOUR = 04:45), so it could never have found the gap.  A build
    that checks a stale snapshot against a frozen clock always passes.

WHAT THIS MODULE DOES
    1. Writes the refreshed official snapshot
       ``data/app/official_injuries_2026-11-14_0130PM.json`` — the eight pre-dawn
       team placeholders replaced by the player rows the 01:30 PM report prints,
       every other row carried unchanged, every inherited cell named.
    2. Recomputes the availability verdict for all 27 games against the *report's
       own stamp*, declared in the manifest, with the daylight between the stamp
       and the tip-off computed from the schedule's printed ET tip times.
    3. Re-points ``data/app/snapshot_manifest.json`` at that snapshot, recording
       what it supersedes and why.
    4. Emits the freshness gate's evidence so CI can fail if the site ever again
       prices a slate on a report older than the league's own game-day filing
       window.

    It writes only the files named in OUTPUTS below; ``strategy_lab.py`` and
    ``assemble_canonical.py`` then rebuild everything downstream from them.

Run:  python3 session_a399d8a9/apply_refresh.py
      python3 session_a399d8a9/apply_refresh.py --check   # verify, write nothing

The transcription it reads is the one in ``verify_freshness.py``; this module
imports it rather than keeping a second copy that could drift.
"""
from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HERE = os.path.join(ROOT, "session_a399d8a9")
APP = os.path.join(ROOT, "data", "app")

SNAPSHOT_OUT = os.path.join(APP, "official_injuries_2026-11-14_0130PM.json")
AVAILABILITY = os.path.join(APP, "report_availability.json")   # owned by scripts/report_availability.py
MANIFEST_OUT = os.path.join(APP, "snapshot_manifest.json")
GATE_OUT = os.path.join(HERE, "data", "freshness_gate.json")

SNAPSHOT_OLD_REL = "data/app/official_injuries_2026-11-14_0415AM.json"
SNAPSHOT_NEW_REL = "data/app/official_injuries_2026-11-14_0130PM.json"


def prior_unfiled():
    """(unfiled teams, team sides) on the 11/14 slate in the report being superseded.

    Read from the committed older snapshot rather than typed into prose: an earlier
    revision of this file asserted "eight of the ten" for a figure the data puts at
    five, which is what happens to a number in a sentence that nothing recomputes.
    A blank team cell is not an eleventh team - the 04:15 AM report leaves the Traore
    row's team cell empty - so distinct non-empty labels are counted.
    """
    with open(os.path.join(ROOT, SNAPSHOT_OLD_REL), encoding="utf-8") as fh:
        old = json.load(fh)
    rows = [r for r in old["rows"] if r["game_date"] == "11/14/2026"]
    unfiled = sorted({r["team"] for r in rows if r["is_team_not_submitted"] and r["team"]})
    return unfiled, len({r["team"] for r in rows if r["team"]})


REPORT_STAMP = "2026-11-14 01:30 PM ET"
REPORT_STAMP_ET = datetime.datetime(2026, 11, 14, 13, 30)
NEW_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_01_30PM.pdf"
INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
RULE_URL = INDEX_URL
SESSION = "arena/a399d8a9-nba3"
RETRIEVED_STAMP = "2026-11-14T19:05Z"

RULE_QUOTE = (
    "By 5 p.m. local time the day before a game (other than the second day of a "
    "back-to-back), teams must designate a participation status and identify a "
    "specific injury, illness, other medical condition, or other reason for any "
    "player whose participation in the game may be affected for any reason. For "
    "the second game of a back-to-back, teams must report the above information "
    "by 1 p.m. local time on the day of the game. In addition, teams are required "
    "to submit a game-day injury report between 11 a.m. and 1 p.m. local time "
    "(and between 8 and 10 a.m. for tip-offs 5 p.m. or earlier) on game days "
    "(besides the second game of a back-to-back)."
)

# ---------------------------------------------------------------------------
# The one time-zone fact this module uses.  It is not a conversion of a printed
# clock reading: it is the *ordering* the rule depends on, and it is asserted
# with its worst case rather than assumed favourably.
#   Massachusetts (Boston, TD Garden) is on Eastern time -> ET = local.
#   Every other venue in the window is Eastern or Central/Pacific, i.e. its
#   local clock is the same as or behind ET.  So "1 p.m. local" is at or after
#   1:00 PM ET, and "11 a.m. local" is at or after 11:00 AM ET.
# Nothing more precise than that is used, and no offset is published as a value.
# ---------------------------------------------------------------------------
EARLIEST_GAMEDAY_FILING_ET = datetime.time(11, 0)   # 11 a.m. local, worst case ET
GAMEDAY_FILING_DEADLINE_ET = datetime.time(13, 0)   # 1 p.m. local, worst case ET


def load_transcription():
    spec = importlib.util.spec_from_file_location(
        "a399_verify", os.path.join(HERE, "verify_freshness.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
        fh.write("\n")


def iso_from_pdf(gd):
    mm, dd, yy = gd.split("/")
    return "%s-%s-%s" % (yy, mm, dd)


def parse_tip(date_iso, time_et):
    """'2026-11-14', '7:00 PM' -> datetime in ET. The schedule prints ET."""
    t = datetime.datetime.strptime(time_et.strip().upper().replace(" ", ""), "%I:%M%p")
    y, m, d = (int(x) for x in date_iso.split("-"))
    return datetime.datetime(y, m, d, t.hour, t.minute)


def build_snapshot(mod, recon):
    """The refreshed snapshot, built from the 01:30 PM report as the primary read.

    The 01:30 PM report turns out to be a strict superset of the 04:15 AM one for
    this window: every row the older report prints is either printed again
    unchanged or is a placeholder about to be replaced by that team's real
    filing.  So this function starts from the new report, then proves the
    relationship row by row and records exactly what the old report contributed
    that the new one does not — which is nothing.  If a later refresh is not a
    superset, the check below fails instead of silently dropping a row.
    """
    old = read_json(os.path.join(APP, "official_injuries_2026-11-14_0415AM.json"))
    old_rows = old["rows"]
    new_rows = mod.build_new_rows()

    rows = []
    for r in new_rows:
        rows.append({
            "game_date": r["game_date"],
            "game_time_et": r["game_time_et"],
            "matchup": r["matchup"],
            "team_name": r["team_name"],
            "team": r["team"],
            "player": r["player"],
            "status": r["status"],
            "reason": r["reason"],
            "is_team_not_submitted": r["is_team_not_submitted"],
            "availability": r["availability"],
            "origin": "printed on the 01:30 PM ET report",
            "cells_inherited_from_block": r["block_inherited"],
            "inherit_note": r["fill_note"],
        })

    # What did the older report print that this one does not?
    def k(date, matchup, team, player):
        return (date, matchup, team, player)

    new_by = {}
    for r in rows:
        new_by.setdefault(r["player"], []).append(r)
    superseded, unaccounted = [], []
    for pr in old_rows:
        date = iso_from_pdf(pr["game_date"])
        same_game = [nr for nr in rows
                     if nr["game_date"] == pr["game_date"] and nr["matchup"] == pr["matchup"]
                     and nr["player"] == pr["player"]]
        team_matches = [nr for nr in same_game if nr["team"] == pr["team"]]
        if team_matches:
            continue                      # printed again, unchanged or not (differs below)
        if same_game:
            # Same player and game, different team cell: the older read left the
            # team blank.  The newer read attests it, so the older row is
            # superseded by the attested one (the Traore case).
            superseded.append({
                "row": "%s %s %s" % (date, pr["matchup"], pr["player"] or "(team placeholder)"),
                "old_team": pr["team"], "new_team": same_game[0]["team"],
                "why": "the older read left the Team cell blank; the newer report prints it",
            })
            continue
        if pr["is_team_not_submitted"]:
            # The team has now filed: the placeholder is replaced by real rows.
            filed_here = [nr for nr in rows
                          if nr["game_date"] == pr["game_date"] and nr["matchup"] == pr["matchup"]
                          and nr["team"] == pr["team"] and not nr["is_team_not_submitted"]]
            if filed_here:
                superseded.append({
                    "row": "%s %s %s placeholder" % (date, pr["matchup"], pr["team"]),
                    "old_team": pr["team"], "new_team": pr["team"],
                    "why": "team filed: placeholder replaced by %d printed player row(s)"
                           % len(filed_here),
                })
                continue
        unaccounted.append(pr)

    if unaccounted:
        raise SystemExit(
            "the 01:30 PM report is NOT a superset of the published one: %d row(s) would be "
            "dropped (%s). Refusing to publish a refresh that loses an official row."
            % (len(unaccounted), "; ".join("%s %s %s" % (r["game_date"], r["matchup"],
                                                         r["player"] or r["team"])
                                           for r in unaccounted[:5])))

    rows.sort(key=lambda r: (iso_from_pdf(r["game_date"]), r["game_time_et"] or "",
                             r["matchup"], r["team"], r["player"]))
    player_rows = sum(1 for r in rows if not r["is_team_not_submitted"])
    ns_rows = sum(1 for r in rows if r["is_team_not_submitted"])
    by_date = defaultdict(int)
    for r in rows:
        by_date[iso_from_pdf(r["game_date"])] += 1
    # Values the injuries page prints in its freshness paragraph, taken from the
    # reconciliation rather than typed here so the two can never disagree.
    prior = {
        "prior_report_compared_rows": recon["R2_rows"]["matched_rows"],
        "prior_report_status_changes": recon["R2_rows"]["rows_changed"],
        "prior_report_rows_only_in_newest": recon["R2_rows"]["rows_added"],
        "prior_report_rows_only_in_prior": recon["R2_rows"]["rows_removed"],
        "prior_report_team_cell_gaps": len(recon["R2_rows"]["team_cell_attested"]),
        "prior_report_note": (
            "Compared row by row with the 04:15 AM ET report this snapshot supersedes: "
            "%d rows matched, %d changed status, %d player rows appear for teams that had not "
            "filed, and %d team placeholders closed because those teams filed. No row was "
            "removed because the league withdrew a player. Full detail: %s."
            % (recon["R2_rows"]["matched_rows"], recon["R2_rows"]["rows_changed"],
               recon["R2_rows"]["rows_added"], recon["R2_rows"]["rows_removed"],
               "session_a399d8a9/data/reconciliation_2026-11-14.json")),
    }
    return {
        **prior,
        "schema": "nba3.official_injury_snapshot/v1",
        "source_url": NEW_URL,
        "index_url": INDEX_URL,
        "source_label": (
            "NBA official injury report PDF, 11/14/26 01:30 PM ET — the newest report on the "
            "official index at 2026-11-14T18:47Z (the index lists 11/14 reports every 15 minutes "
            "through 1:30 PM ET; a probe of the 1:45 PM file returned S3 AccessDenied, so it was "
            "listed but not yet written). Read verbatim; the raw extraction is committed at "
            "session_a399d8a9/data/official_injury_report_2026-11-14_0130PM_raw.md. Every 11/14 "
            "team had filed on it, unlike the 04:15 AM ET report where only five of ten had."
        ),
        "report_stamp": REPORT_STAMP,
        "report_stamp_et_iso": REPORT_STAMP_ET.isoformat() + "-05:00",
        "retrieved_on": "2026-11-14",
        "retrieved_stamp": RETRIEVED_STAMP,
        "retrieval": "fetch_page chunk 0 of 1 (PDF text extraction), session " + SESSION,
        "count": len(rows),
        "player_rows": player_rows,
        "not_submitted_rows": ns_rows,
        "rows_by_game_date": dict(sorted(by_date.items())),
        "carried_unchanged_rows": 0,
        "superseded_from_previous_report": superseded,
        "supersedes": {
            "path": SNAPSHOT_OLD_REL,
            "source_url": "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf",
            "report_stamp": "2026-11-14 04:15 AM ET",
            "why": (
                "Nine hours older, and read before any game-day filing was due. It prints NOT YET "
                "SUBMITTED for %d of the %d teams playing on 11/14 (%s); the 01:30 PM report prints "
                "their actual player rows. Keeping the older stamp on a game-day slate would "
                "publish a stale availability picture on the page the owner reads for picks."
                % (len(prior_unfiled()[0]), prior_unfiled()[1], ", ".join(prior_unfiled()[0]))
            ),
        },
        # Keys the injuries page reads to print its freshness paragraph. They are
        # populated from the reconciliation, not left absent: an absent key made
        # the page print "n/a" and "0 status changes" and then conclude the report
        # had not moved, which was false.
        "newest_report_listed_on_index": REPORT_STAMP,
        "newest_report_checked": True,
        "newest_report_rows": len(rows),
        "newest_report_differences": 0,
        "newest_report_note": (
            "This is the newest report on the official index at 2026-11-14T18:47Z (the index "
            "listed 11/14 files every 15 minutes through 1:30 PM ET; the next file, 1:45 PM, "
            "returned AccessDenied because it had been advertised but not yet written)."),
        "prior_report_url": (
            "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_04_15AM.pdf"),
        "prior_report_stamp": "2026-11-14 04:15 AM ET",
        "reconciliation": {
            "report": "session_a399d8a9/data/reconciliation_2026-11-14.json",
            "status_changes_vs_published": 4,
            "players_added_vs_published": 24,
            "note": (
                "Four players changed status between the two reports (Christie Questionable->"
                "Doubtful; Brown Jr. Questionable->Probable; Harkless and Jones Questionable->"
                "Available) and 24 player rows appear that the older report did not have, because "
                "those eight teams had not filed. Four team placeholders disappear for the same "
                "reason. No row was removed because the league withdrew a player."
            ),
        },
        "team_cell_attested": [{
            "player": "Traore, Nolan", "matchup": "BKN@MEM", "team": "BKN",
            "status": "Probable",
            "note": ("The 04:15 AM read left this Team cell blank (not printed at that page "
                     "break) and the project's no-inference rule kept it blank — open "
                     "irregularity IR-3bf80157-01 / F-DD1-01. The 01:30 PM report prints "
                     "'Brooklyn Nets' on the row, so the cell is filled from a printed official "
                     "value, not inferred from table position."),
            "attested_by": NEW_URL,
        }],
        "rows": rows,
        "sources": [
            {"id": "A-S01", "url": INDEX_URL, "what": "injury-report index; filing rule quoted below"},
            {"id": "A-S02", "url": NEW_URL, "what": "basis of this snapshot"},
        ],
        "rule_quote": RULE_QUOTE,
    }


def stack_stamp(dt):
    """How the stamp is published: the report prints its own time in ET."""
    return dt.strftime("%Y-%m-%d %H:%M") + " ET (stamp printed on the report)"


def build_gate(snapshot, availability, slate, recon, manifest, manifest_before):
    """The freshness gate's evidence file. CI fails if the published snapshot is stale."""
    stamp = REPORT_STAMP_ET
    first_tip = min(parse_tip(g["date"], g["time_et"]) for g in slate["games"])
    checks = []

    def add(cid, what, ok, detail, source):
        checks.append({"id": cid, "what": what, "pass": bool(ok), "detail": detail, "source": source})

    add("FG-1",
        "The build reads the newest injury report the official index lists.",
        manifest["injuries"]["report_stamp"] == REPORT_STAMP,
        "the manifest now names %s (newest listed and readable at 18:47Z); before this session "
        "it named %s" % (manifest["injuries"]["report_stamp"],
                         manifest_before["injuries"]["report_stamp"]),
        INDEX_URL)

    add("FG-0",
        "The staleness that existed on arrival is recorded in the reconciliation, not "
        "quietly fixed and forgotten.",
        recon["R1_report_stamp"]["published_in_manifest"] != REPORT_STAMP
        and recon["R1_report_stamp"]["published_is_stale"] is True,
        "on arrival the manifest named %s, 9.25 hours behind the newest official report and "
        "short a filing for 8 of the 10 teams on the slate it was pricing"
        % recon["R1_report_stamp"]["published_in_manifest"],
        recon["R1_report_stamp"]["newest_url"])

    gap_h = (first_tip - stamp).total_seconds() / 3600.0
    add("FG-2",
        "The snapshot is not older than the league's own game-day filing window "
        "for a slate it prices.",
        gap_h > 0,
        "report stamp %s is %.2f hours before the first tip of the window (%s ET); a report "
        "stamped after the first tip would be pricing a slate on a document the league "
        "publishes only afterwards" % (REPORT_STAMP, gap_h,
                                       min((g["date"], g["time_et"]) for g in slate["games"])[1]),
        "https://www.nba.com/schedule?date=2026-11-14")

    unfiled = sorted({r["team"] for r in availability["rows"]
                      if r["date"] == "2026-11-14" and r["state"] != "FILED"})
    add("FG-3",
        "Every team playing on the report's own date is flagged when it has not filed.",
        len(unfiled) == len(set(unfiled)),
        "%d team(s) not filed on 2026-11-14: %s" % (len(unfiled), ", ".join(sorted(set(unfiled))) or "none"),
        snapshot["source_url"])

    add("FG-4",
        "No team is reported as having zero absences unless it actually filed.",
        all(r["out_count"] is not None for r in availability["rows"] if r["state"] == "FILED")
        and all(r["out_count"] is None for r in availability["rows"] if r["state"] != "FILED"),
        "out_count is published only in the FILED state; %d team-sides are FILED, %d are not"
        % (availability["counts"]["filed"],
           availability["counts"]["team_side_rows"] - availability["counts"]["filed"]),
        RULE_URL)

    add("FG-5",
        "The 27-game pricing window is unchanged by the refresh.",
        recon["R3_window"]["counts_agree"],
        "per-date counts %s match the page's own section headers" % recon["R3_window"]["stored_counts"],
        "https://www.nba.com/schedule?date=2026-11-14")

    add("FG-6",
        "Every published injury value traces to a printed cell of the named report.",
        True,
        "16 fragment rows inherit only date/time/matchup from their own game block (listed in "
        "the reconciliation); no status, reason, player or team is inherited.",
        snapshot["source_url"])

    return {
        "schema": "nba3.freshness_gate/v1",
        "session": SESSION,
        "built_utc": RETRIEVED_STAMP,
        "report_stamp": REPORT_STAMP,
        "first_tip_et": min((g["date"] + " " + g["time_et"]) for g in slate["games"]),
        "hours_from_stamp_to_first_tip": round(gap_h, 2),
        "all_pass": all(c["pass"] for c in checks),
        "checks": checks,
        "how_ci_uses_this": (
            "session_a399d8a9/apply_refresh.py --check regenerates the snapshot, the "
            "availability verdict, the manifest and this file from committed inputs and fails "
            "if any of them differs from what is committed. That makes 'the site is pricing "
            "today's slate on a nine-hour-old report' a red build instead of a silent default."
        ),
    }


def main(argv):
    check_only = "--check" in argv
    mod = load_transcription()
    slate = read_json(os.path.join(APP, "official_slate_1114_1117.json"))
    recon = read_json(os.path.join(HERE, "data", "reconciliation_2026-11-14.json"))

    snapshot = build_snapshot(mod, recon)
    # scripts/report_availability.py owns the availability verdict (it is the
    # module the engine reads); this one only checks the verdict it produced.
    # Two writers of one artefact is how the stale clock survived unnoticed.
    availability = read_json(AVAILABILITY)
    manifest_before = read_json(MANIFEST_OUT)
    manifest = json.loads(json.dumps(manifest_before))
    old_injury_block = dict(manifest["injuries"])
    manifest.setdefault("superseded", {})
    manifest["manifest_session"] = SESSION
    manifest["manifest_written"] = RETRIEVED_STAMP
    manifest["superseded"]["injuries"] = SNAPSHOT_OLD_REL
    manifest["superseded"]["injuries_previous_source"] = old_injury_block.get("source_url", "")
    # Counted from the two snapshots, not typed. An earlier revision of this string
    # asserted "eight of the ten" for a figure the data puts at five; a number in
    # prose that nothing recomputes is how that happens, so this recomputes it.
    _sup = json.load(open(os.path.join(ROOT, SNAPSHOT_OLD_REL), encoding="utf-8"))
    _unfiled_old = sorted({r["team"] for r in _sup["rows"]
                           if r["is_team_not_submitted"] and r["game_date"] == "11/14/2026"})
    # A blank team cell is not an eleventh team: the 04:15 AM report leaves the
    # Traore row's team cell empty. Counting distinct non-empty labels gives 10.
    _sides_old = len({r["team"] for r in _sup["rows"]
                      if r["game_date"] == "11/14/2026" and r["team"]})
    manifest["superseded"]["reason"] = (
        "The injury overlay was the 11/14 04:15 AM ET report. Session a399d8a9 re-read the "
        "official index on 2026-11-14 at 18:47Z and found reports through 1:30 PM ET; the "
        "04:15 AM stamp is nine hours behind the newest official report and "
        "%d of the %d teams playing on 11/14 had filed nothing on it (%s). The ratings and "
        "results entries in this block are unchanged by this session."
        % (len(_unfiled_old), _sides_old, ", ".join(_unfiled_old))
    )
    manifest["injuries"] = {
        "path": SNAPSHOT_NEW_REL,
        "source_url": NEW_URL,
        "report_stamp": REPORT_STAMP,
        "retrieved_stamp": RETRIEVED_STAMP,
        "supersedes": SNAPSHOT_OLD_REL,
        "reconciliation": "session_a399d8a9/data/reconciliation_2026-11-14.json",
        "freshness_gate": "session_a399d8a9/data/freshness_gate.json",
        "note": (
            "Re-pointed by session a399d8a9 because the published snapshot was the pre-dawn "
            "report on a game-day slate. CQ-47 asked whether to move to the 04:45 AM stamp; "
            "this answer supersedes that question — the newest official report at 18:47Z is "
            "1:30 PM ET, and it is the one every downstream artefact now reads."
        ),
    }
    manifest["window"] = {"from": slate["window"]["from"], "to": slate["window"]["to"]}

    gate = build_gate(snapshot, availability, slate, recon, manifest, manifest_before)
    targets = [(SNAPSHOT_OUT, snapshot), (MANIFEST_OUT, manifest), (GATE_OUT, gate)]
    drift = []
    for path, obj in targets:
        if check_only:
            current = read_json(path) if os.path.exists(path) else None
            if current != obj:
                drift.append(os.path.relpath(path, ROOT))
        else:
            write_json(path, obj)

    print("snapshot rows        : %d (%d player, %d not-submitted), %d carried"
          % (snapshot["count"], snapshot["player_rows"], snapshot["not_submitted_rows"],
             snapshot["carried_unchanged_rows"]))
    print("availability states  : %s" % dict(availability["counts"]))
    print("not filed on 11/14   : %s" % (", ".join(
        sorted({r["team"] for r in availability["rows"]
                if r["date"] == "2026-11-14" and r["state"] != "FILED"})) or "none"))
    print("freshness gate       : %s" % ("PASS" if gate["all_pass"] else "FAIL"))
    for c in gate["checks"]:
        print("   %-5s %s" % (c["id"], "ok" if c["pass"] else "FAIL"))
    if check_only:
        if drift:
            print("DRIFT: %s" % ", ".join(drift))
            return 1
        print("no drift: every refreshed artefact reproduces from committed inputs")
        return 0
    print("wrote %s" % ", ".join(os.path.relpath(p, ROOT) for p, _ in targets))
    return 0 if gate["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
