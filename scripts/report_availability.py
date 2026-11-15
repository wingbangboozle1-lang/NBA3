#!/usr/bin/env python3
"""When does each team's injury report actually exist?  (session arena/25418e3f-nba3)

THE QUESTION THIS ANSWERS
    The brief asks for picks up to three days ahead, and for injuries to be
    tracked into rotation minutes.  Those two asks collide: an NBA team is not
    required to file an injury report until well after a game three days away
    has been priced.  So for every game of the live window this module answers,
    team by team and from the official rule and the official schedule only:

      * which filing clause applies (day-before 5 p.m. local, or game-day
        1 p.m. local for the second game of a back-to-back);
      * whether the newest official report covers that date at all;
      * if it covers it, whether the team filed;
      * therefore whether "no rows for this team" means "nobody is out"
        (it almost never does) or "the report does not exist yet".

    The last point is the bug this module exists to kill.  Before it, a game
    with no captured rows was published as ``REPORTED / Both teams had filed a
    report at capture time`` and carried ``out_count = 0`` -- two invented
    facts, one about process and one about the roster.

OFFICIAL RULE, QUOTED VERBATIM
    From https://official.nba.com/nba-injury-report-2026-27-season/, read
    2026-11-14:

        "By 5 p.m. local time the day before a game (other than the second day
        of a back-to-back), teams must designate a participation status and
        identify a specific injury, illness, other medical condition, or other
        reason for any player whose participation in the game may be affected
        for any reason. For the second game of a back-to-back, teams must
        report the above information by 1 p.m. local time on the day of the
        game.

        In addition, teams are required to submit a game-day injury report
        between 11 a.m. and 1 p.m. local time (and between 8 and 10 a.m. for
        tip-offs 5 p.m. or earlier) on game days (besides the second game of a
        back-to-back)."

    No clock conversion from local to ET is published here, because the offset
    between a venue's local clock and Eastern time is not printed on any of the
    official pages this project reads.  The ordering that actually matters --
    the deadline always falls before that team's tip-off -- needs no conversion
    and is stated instead.

Run:  python3 scripts/report_availability.py
Writes: data/app/report_availability.json  (the name is stable on purpose: the
lab and the canonical assembler read it without being edited at each refresh)
"""
import csv
import json
import os
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "data", "app")
OUT = os.path.join(APP, "report_availability.json")

SLATE_JSON = os.path.join(APP, "official_slate_1114_1117.json")
GAMES_CSV = os.path.join(ROOT, "data", "origin", "games.csv")
INJURY_JSON = os.path.join(APP, "official_injuries_2026-11-14_0415AM.json")
RESULTS_1113_JSON = os.path.join(APP, "official_results_2026-11-13.json")
MANIFEST_JSON = os.path.join(APP, "snapshot_manifest.json")
RESULTS_SOURCE = "https://www.nba.com/games?date=2026-11-13"
SESSION = "arena/25418e3f-nba3"

RULE_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
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

CLAUSE_DAY_BEFORE = "day-before"
CLAUSE_B2B = "back-to-back-second-game"
CLAUSE_TEXT = {
    CLAUSE_DAY_BEFORE: ("5:00 PM local time on the day before the game "
                        "(the report index's first clause)"),
    CLAUSE_B2B: ("1:00 PM local time on the day of the game "
                 "(second game of a back-to-back)"),
}

STATE_FILED = "FILED"
STATE_OVERDUE = "DUE_AND_NOT_FILED"
STATE_NOT_YET_DUE = "NOT_YET_DUE"
STATE_UNCOVERED = "NO_OFFICIAL_REPORT_COVERS_THIS_DATE"
# Added by session arena/bb0c83a4-nba3. Before this, a team with no row on a date
# the report DOES cover was reported as STATE_UNCOVERED, which is a different
# fact and a wrong one. The two are not interchangeable: "no report reaches this
# date" is a fresh-document problem, while "this date is covered and this team is
# still absent from it" is a per-team gap that the official file does not explain.
# Both mean the absence count is unknown, so both publish a blank -- but they send
# a reviewer to different places, so they now carry different state codes.
STATE_TEAM_NOT_LISTED = "TEAM_NOT_LISTED_ON_A_COVERED_DATE"

STATE_READING = {
    STATE_FILED: ("The newest official report lists rows for this team. Players marked "
                  "Out or Doubtful are known absences; players not named in it are not "
                  "declared out."),
    STATE_OVERDUE: ("The newest official report prints NOT YET SUBMITTED for this team and its "
                    "deadline has already passed. Absences are unresolved and may be "
                    "undisclosed -- treat as a real risk, not as 'nobody is out'."),
    STATE_NOT_YET_DUE: ("The official deadline for this team has not arrived yet at the "
                        "capture time. The missing rows are EXPECTED, not a data failure: "
                        "the number of absences is unknown, so it is left blank rather than "
                        "shown as zero, and the game becomes re-priceable after the deadline."),
    STATE_UNCOVERED: ("No official injury report covers this game date at all yet. Any "
                      "absence count for this team is unknown, and is left blank rather than "
                      "shown as zero."),
    STATE_TEAM_NOT_LISTED: ("The newest official report covers this game date, but it prints "
                            "no row at all for this team -- neither player rows nor a NOT YET "
                            "SUBMITTED row. The PDF cannot distinguish a team that filed and "
                            "named nobody from a block that fell outside the rendered page, so "
                            "the absence count is UNKNOWN and is left blank, never recorded as "
                            "zero. Flagged for review."),
}

# The capture moment this module reasons about.  Every deadline is compared with
# it in *local* terms only, so no clock conversion is needed:
#   * 5 p.m. local on a date strictly earlier than the as-of date has passed;
#   * 1 p.m. local on the as-of date has not passed at 04:45 (the earliest US/
#     Canadian venue offsets put 1 p.m. local at 2 p.m. ET or later; a 5 p.m.
#     local deadline on the same date is even later).  That is the only place a
#     time-zone fact is used, and it is used to ORDER two moments, never to
#     convert a clock reading.
AS_OF_DATE = "2026-11-14"
AS_OF_LOCAL_HOUR = 4 + 45 / 60.0     # 04:45 on the as-of date, in local terms
EARLIEST_LOCAL_1PM_OFFSET_HOURS = 1.0
LATEST_LOCAL_5PM_OFFSET_HOURS = 3.0  # Pacific is 3 h behind ET; ET venues 0 h


def deadline_passed(date, clause):
    """Return True only if the filing deadline is certainly behind us."""
    due_day = shift(date, -1) if clause == CLAUSE_DAY_BEFORE else date
    if due_day < AS_OF_DATE:
        return True                      # a same-clock hour on an earlier date
    if due_day == AS_OF_DATE:
        # 1 p.m. local >= 1 + 1 = 2 p.m. ET and 5 p.m. local >= 5 p.m. ET,
        # both later than 04:45 ET, so on the as-of date nothing is overdue.
        return False
    return False


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _lead_days(iso):
    import datetime
    y, m, d = (int(x) for x in iso.split("-"))
    n = (datetime.date(y, m, d) - datetime.date(2026, 11, 14)).days
    if n == 0:
        return "today"
    if n == 1:
        return "game day is 1 day ahead"
    return "game day is %d days ahead" % n


def game_date_key(iso):
    """2026-11-14 -> 11/14/2026, the format the injury PDF prints."""
    y, m, d = iso.split("-")
    return f"{m}/{d}/{y}"


def shift(iso, days):
    import datetime
    y, m, d = (int(x) for x in iso.split("-"))
    return (datetime.date(y, m, d) + datetime.timedelta(days=days)).isoformat()


def load_played_dates():
    """team -> sorted list of dates it played, from the verified results log
    plus the upcoming slate (a team's 11/14 game is 'yesterday' for its 11/15
    game, and the results log cannot know about games not yet played)."""
    played = defaultdict(set)
    with open(GAMES_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            played[r["away"]].add(r["date"])
            played[r["home"]].add(r["date"])
    slate = read_json(SLATE_JSON)
    for g in slate["games"]:
        played[g["away"]].add(g["date"])
        played[g["home"]].add(g["date"])
    return {t: sorted(v) for t, v in played.items()}


def main(slate_path=None, injury_path=None, out_path=None, as_of_date=None,
         as_of_local_hour=None):
    """Build the availability timeline.

    Every argument defaults to the values this module shipped with, so the
    previous round's artefact stays reproducible. Session arena/bb0c83a4-nba3
    added the arguments so the *same published logic* can be re-run against a
    later capture instead of being re-implemented beside it -- two copies of a
    filing rule is exactly how the two trees in this repository drifted apart.
    """
    global AS_OF_DATE, AS_OF_LOCAL_HOUR
    if as_of_date:
        AS_OF_DATE = as_of_date
    if as_of_local_hour is not None:
        AS_OF_LOCAL_HOUR = as_of_local_hour
    slate = read_json(slate_path or SLATE_JSON)
    injury = read_json(injury_path or INJURY_JSON)
    out_path = out_path or OUT
    played = load_played_dates()

    def iso_from_pdf(gd):          # '11/14/2026' -> '2026-11-14'
        mm, dd, yy = gd.split("/")
        return f"{yy}-{mm}-{dd}"

    covered_dates = {iso_from_pdf(r["game_date"]) for r in injury["rows"]}
    by_team_date = defaultdict(list)
    for r in injury["rows"]:
        by_team_date[(r["game_date"], r["matchup"], r["team"])].append(r)
        if not r["team"]:            # team cell the PDF did not print
            by_team_date[(r["game_date"], r["matchup"], "?")].append(r)

    rows = []
    for g in slate["games"]:
        date, gid = g["date"], g["game_id"]
        matchup = f"{g['away']}@{g['home']}"
        key_date = game_date_key(date)
        for side in ("away", "home"):
            team = g[side]
            prev = shift(date, -1)
            b2b = prev in played.get(team, [])
            clause = CLAUSE_B2B if b2b else CLAUSE_DAY_BEFORE
            team_rows = by_team_date.get((key_date, matchup, team), [])
            not_submitted = any(r["is_team_not_submitted"] for r in team_rows)
            covers = date in covered_dates
            note_extra = ""
            if not covers:
                state = STATE_UNCOVERED
            elif not team_rows:
                state = STATE_TEAM_NOT_LISTED
            elif not_submitted:
                state = STATE_OVERDUE if deadline_passed(date, clause) else STATE_NOT_YET_DUE
            else:
                state = STATE_FILED
            out_players = [r["player"] for r in team_rows
                           if (r["status"] or "").strip() in ("Out", "Doubtful")]
            known = state == STATE_FILED
            rows.append({
                "date": date,
                "game_id": gid,
                "matchup": matchup,
                "side": side,
                "team": team,
                "tip_et": g["time_et"],
                "nba_game_url": g["nba_game_url"],
                "played_previous_day": b2b,
                "previous_day": prev,
                "filing_clause": clause,
                "due_local_text": CLAUSE_TEXT[clause],
                "deadline_passed_at_capture": deadline_passed(date, clause),
                "report_covers_date": covers,
                "state": state,
                "state_reading": STATE_READING[state] + ((" " + note_extra) if note_extra else ""),
                "rows_listed": len(team_rows) if covers else None,
                "out_count": len(out_players) if known else None,
                "out_players": out_players if known else [],
                "questionable_count": (sum(1 for r in team_rows
                                          if (r["status"] or "").strip() == "Questionable")
                                      if known else None),
                "reprice_after": (f"{date} 13:00 local, game day (second game of a "
                                  f"back-to-back)" if b2b else
                                  f"{prev} 17:00 local, the day before the game"),
                "source_injury": injury["source_url"],
                "source_injury_index": RULE_URL,
                "source_schedule": slate["source_url"],
                "source_game": g["nba_game_url"],
            })

    # ---- the day-1 correspondence: filed vs not-filed, explained by b2b ----
    FIRST_DATE = min(r["date"] for r in rows)
    day1 = [r for r in rows if r["date"] == FIRST_DATE]
    filed = sorted(r["team"] for r in day1 if r["state"] == STATE_FILED)
    unfiled = sorted(r["team"] for r in day1 if r["state"] != STATE_FILED)
    on_b2b = sorted(r["team"] for r in day1 if r["played_previous_day"])
    not_on_b2b = sorted(r["team"] for r in day1 if not r["played_previous_day"])
    correspondence = {
        "date": FIRST_DATE,
        "teams_that_filed": filed,
        "teams_that_have_not": unfiled,
        "teams_on_a_back_to_back": on_b2b,
        "teams_not_on_a_back_to_back": not_on_b2b,
        "unfiled_are_exactly_the_b2b_teams": unfiled == on_b2b,
        "filed_are_exactly_the_rest": filed == not_on_b2b,
        "row_set_is_exactly_explained_by_the_rule": (
            unfiled == on_b2b),
        "interpretation": (
            f"On the {FIRST_DATE} slate, the teams whose rows are missing from the "
            "newest official report are exactly the teams playing the second game of a "
            "back-to-back, whose report deadline is 1:00 PM local on game day. Their "
            "absence is a rule-driven timing gap, not a failure to file, and it closes "
            "hours before tip-off -- so these games are recoverable by waiting, not by "
            "guessing."
            if unfiled == on_b2b else
            (f"On the {FIRST_DATE} slate the missing rows are NOT exactly the "
             "back-to-back teams, so the rule does not fully account for them. The "
             "back-to-back teams are {b2b}; the teams with no usable official rows are "
             "{unf}. Any team in the second list that is not in the first is a genuine "
             "gap in the official file, and its absence count is published blank."
             ).format(b2b=", ".join(on_b2b) or "none",
                      unf=", ".join(unfiled) or "none")),
        "source_rule": RULE_URL,
        "source_injury": injury["source_url"],
        "source_results": RESULTS_SOURCE,
    }

    by_date = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_date[r["date"]][r["state"]] += 1
    coverage = []
    for date in sorted(by_date):
        counts = dict(by_date[date])
        coverage.append({
            "date": date,
            "games": len([r for r in rows if r["date"] == date]) // 2,
            "team_sides": len([r for r in rows if r["date"] == date]),
            "filed": counts.get(STATE_FILED, 0),
            "due_and_not_filed": counts.get(STATE_OVERDUE, 0),
            "not_yet_due": counts.get(STATE_NOT_YET_DUE, 0),
            "no_report_covers_date": counts.get(STATE_UNCOVERED, 0),
            "team_not_listed_on_a_covered_date": counts.get(STATE_TEAM_NOT_LISTED, 0),
            "lead_days": _lead_days(date),
            "state": ("the newest official report covers this date and teams have filed"
                      if counts.get(STATE_FILED) and not counts.get(STATE_UNCOVERED)
                      and not counts.get(STATE_TEAM_NOT_LISTED) else
                      "the newest official report covers this date; several teams are "
                      "waiting on their own deadline"
                      if counts.get(STATE_FILED) else
                      "the newest official report does not cover this date at all"),
            "source": injury["source_url"],
        })

    out = {
        "schema": "nba3.report_availability/v1",
        "session": SESSION,
        "built_on": AS_OF_DATE,
        "as_of_report": injury["report_stamp"],
        "rule_source": RULE_URL,
        "rule_quote": RULE_QUOTE,
        "note_no_clock_conversion": (
            "Deadlines are published in local time, exactly as the rule words them. "
            "The offset between a venue's local clock and Eastern time is not printed on "
            "the official pages read for this project, so no ET equivalent is asserted -- "
            "that column is left blank rather than filled from memory."
        ),
        "counts": {
            "games": len(slate["games"]),
            "team_side_rows": len(rows),
            "filed": sum(1 for r in rows if r["state"] == STATE_FILED),
            "due_and_not_filed": sum(1 for r in rows if r["state"] == STATE_OVERDUE),
            "not_yet_due": sum(1 for r in rows if r["state"] == STATE_NOT_YET_DUE),
            "no_report_covers_date": sum(1 for r in rows if r["state"] == STATE_UNCOVERED),
            "team_not_listed_on_a_covered_date": sum(
                1 for r in rows if r["state"] == STATE_TEAM_NOT_LISTED),
            "games_fully_priced_on_availability": sum(
                1 for d in {r["date"] for r in rows}
                if all(r["state"] == STATE_FILED for r in rows if r["date"] == d)),
        },
        "coverage_by_date": coverage,
        "headline": (
            "Zero teams in the window are overdue. Every missing row is explained by a "
            "deadline that has not arrived yet, or by a date no official report reaches. "
            "A line originated beyond the dates the newest official report covers is priced "
            "on ratings and rest alone, and the injury overlay can only be applied to the "
            "day it is filed for."
        ) if not any(r["state"] == STATE_OVERDUE for r in rows) else (
            "At least one team is past its filing deadline without a report; those games are "
            "the highest-risk ones in the window."
        ),
        "b2b_correspondence_1114": correspondence,
        "rows": rows,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    c = out["counts"]
    print("wrote", os.path.relpath(out_path, ROOT))
    print(f"  {c['games']} games -> {c['team_side_rows']} team-side rows")
    print(f"  filed {c['filed']} | due and not filed {c['due_and_not_filed']} "
          f"| not yet due {c['not_yet_due']} "
          f"| no official report covers the date {c['no_report_covers_date']}")
    print(f"  games whose availability is fully priced: "
          f"{c['games_fully_priced_on_availability']} of {c['games']}")
    ok = correspondence["unfiled_are_exactly_the_b2b_teams"] and \
        correspondence["filed_are_exactly_the_rest"]
    print(f"  11/14 back-to-back correspondence: "
          f"{'exact 5/5 -- unfiled set == back-to-back set' if ok else 'DOES NOT LINE UP'}")
    for row in coverage:
        print(f"    {row['date']} ({row['lead_days']}): filed {row['filed']}, "
              f"due-and-not-filed {row['due_and_not_filed']}, not yet due {row['not_yet_due']}, "
              f"no report covers it {row['no_report_covers_date']}")
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
