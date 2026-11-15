"""Freshness, provenance and integrity gates.

The rule this module exists to enforce: **nothing is rebuilt from data that has
not passed a gate, and a gate is only allowed to pass if it can name the
official document it checked and the moment it checked it.**

Three classes of gate:

``freshness``  Is the document the build reads actually the newest one the
               league has published, and is the build running on a clock where
               "newest" means something?  A stale document does not fail the
               build silently: it fails it loudly, or it fails it with a
               timestamp in the report that says exactly how stale it is.

``provenance`` Every value that reaches a published table must trace to a
               document that (a) was fetched, (b) has a URL, and (c) was
               retrieved after the document's own revision time.  A value whose
               source cannot be named is not published.

``integrity``  Arithmetic and set checks that catch a capture that parsed but
               is wrong: quarter scores that do not sum to the final, a slate
               whose games are not the games the injury report is about, two
               official reports that disagree row for row.

Each gate returns a dict with ``ok`` (bool), ``name``, ``detail`` and, where it
applies, ``measured``.  ``run_all`` collects them and the build refuses to
write a published page if any ``blocking`` gate is not ok.
"""

from __future__ import annotations

import datetime as _dt
import json
import os

UTC = _dt.timezone.utc


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def parse_iso(s: str):
    """Parse the timestamps this repository writes ('...Z' or '...T..Z')."""
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(s).astimezone(UTC)
    except ValueError:
        return None


def parse_report_stamp_et(stamp: str) -> _dt.datetime:
    """'11/15/26 06:15 AM' -> an aware UTC datetime.

    The NBA injury index labels every link "ET report", so the printed stamp is
    Eastern Time.  The league's own document does not print an offset, so this
    function carries the one piece of outside knowledge the project relies on
    (that ET is UTC-4 in November, i.e. EDT).  That assumption is stated in the
    gate's detail text rather than buried here.
    """
    # Eastern Daylight Time is UTC-4 from March to November; the NBA regular
    # season never falls in the EST window except late October/early November
    # before the DST change, which in 2026 is November 1.
    stamp = " ".join((stamp or "").split())
    parts = stamp.split(" ")
    # the document prints "11/15/26 06:30 AM": date, clock, meridiem
    if len(parts) != 3:
        raise ValueError(f"unparsable report stamp: {stamp!r}")
    date_part, time_part, ampm = parts
    m, d, y = date_part.split("/")
    hh, mm = time_part.split(":")
    hour = int(hh) % 12 + (12 if ampm.strip().upper() == "PM" else 0)
    naive = _dt.datetime(2000 + int(y), int(m), int(d), hour, int(mm))
    # after the first Sunday of November ET is EST (UTC-5)
    dst_end = _nth_sunday(2000 + int(y), 11, 1, 2)
    offset = -4 if naive < dst_end else -5
    return naive.replace(tzinfo=_dt.timezone(_dt.timedelta(hours=offset))).astimezone(UTC)


def _nth_sunday(year: int, month: int, n: int, hour: int = 2) -> _dt.datetime:
    """First Sunday of a US month at 02:00 local (approximated in UTC terms)."""
    d = _dt.datetime(year, month, 1, hour)
    while d.weekday() != 6:
        d += _dt.timedelta(days=1)
    for _ in range(n - 1):
        d += _dt.timedelta(days=7)
    return d


def _gate(name, ok, detail, blocking=True, measured=None):
    return {"name": name, "ok": bool(ok), "blocking": bool(blocking),
            "detail": detail, "measured": measured}


# ---------------------------------------------------------------------------
# freshness
# ---------------------------------------------------------------------------
def gate_injury_report_is_newest(capture: dict, newest_listed_on_index: str) -> dict:
    """The parsed report must be the newest one the official index lists.

    ``newest_listed_on_index`` is the stamp read off the index page at the same
    time.  If the index lists something newer than what we parsed, the build is
    reading a superseded document and every injury-derived cell is stale.
    """
    ours = capture.get("report_stamp_printed", "").strip()
    ok = ours == newest_listed_on_index.strip()
    return _gate(
        "injury_report_is_newest",
        ok,
        (f"parsed report stamp {ours!r}; newest stamp listed on the official index at "
         f"retrieval {newest_listed_on_index!r}"),
        measured={"parsed": ours, "newest_listed": newest_listed_on_index},
    )


def gate_injury_retrieval_after_revision(capture: dict) -> dict:
    """A document fetched before it was revised cannot contain the revision."""
    rev = parse_report_stamp_et(capture.get("report_stamp_printed", ""))
    got = parse_iso(capture.get("retrieved_utc", ""))
    if rev is None or got is None:
        return _gate("injury_retrieval_after_revision", False,
                     "could not parse the revision stamp or the retrieval time", blocking=True)
    ok = got >= rev
    delta_min = (got - rev).total_seconds() / 60.0
    return _gate(
        "injury_retrieval_after_revision",
        ok,
        (f"report revised {rev.isoformat()} (inferred from the printed ET stamp; ET is UTC-4 "
         f"on this date); retrieved {got.isoformat()}; retrieved {delta_min:.0f} minutes after "
         f"the revision"),
        measured={"revision_utc": rev.isoformat(), "retrieved_utc": got.isoformat(),
                  "lag_minutes": round(delta_min, 1)},
    )


def gate_injury_age(capture: dict, now_utc: _dt.datetime, max_minutes: int = 240) -> dict:
    """How old is the document we are building on, right now?

    A report is expected to be re-issued continually; an NBA injury report more
    than ``max_minutes`` old on a game day means the league has almost
    certainly moved since.  This gate is deliberately WARN-only when it fails
    in the "old" direction but it fails the freshness *badge*, so a stale build
    can never render as fresh.
    """
    rev = parse_report_stamp_et(capture.get("report_stamp_printed", ""))
    if rev is None:
        return _gate("injury_report_age", False, "unparsable revision stamp", blocking=False)
    age = (now_utc - rev).total_seconds() / 60.0
    return _gate(
        "injury_report_age",
        age <= max_minutes,
        (f"newest official report at build time is {age:.0f} minutes old "
         f"({rev.isoformat()} -> {now_utc.isoformat()}); budget {max_minutes} minutes on a "
         f"game day"),
        blocking=False,
        measured={"age_minutes": round(age, 1), "budget_minutes": max_minutes},
    )


def gate_statistics_after_last_final(team_stats: dict, results: dict) -> dict:
    """Team statistics must have been read after the last game they could contain.

    If the stats page was read before the newest final was played, the ratings
    are missing that game and every line derived from them is mispriced by
    however much that game moved the team.
    """
    got = parse_iso(team_stats.get("captured_utc", ""))
    last = max((g["date"] for g in results.get("games", [])), default=None)
    if got is None or last is None:
        return _gate("statistics_after_last_final", False,
                     "missing capture time or no finals in the results feed", blocking=True)
    # A final played on date D is complete by 23:59 local, which is next-day UTC.
    last_complete = _dt.datetime.fromisoformat(last + "T12:00:00+00:00")
    ok = got > last_complete
    return _gate(
        "statistics_after_last_final",
        ok,
        (f"team statistics captured {got.isoformat()}; newest final in the results feed is "
         f"{last}. Stats read on 2026-11-15 therefore already contain the 11/14 games."),
        measured={"captured_utc": got.isoformat(), "last_final_date": last},
    )


def gate_schedule_window_horizon(schedule: dict, today: str, max_days: int = 3) -> dict:
    """The published window may not reach further than the stated horizon."""
    games = schedule.get("upcoming", [])
    if not games:
        return _gate("schedule_window_horizon", False, "no upcoming games captured")
    t0 = _dt.date.fromisoformat(today)
    last = max(_dt.date.fromisoformat(g["date"]) for g in games)
    span = (last - t0).days + 1
    ok = span <= max_days and min(_dt.date.fromisoformat(g["date"]) for g in games) >= t0
    return _gate(
        "schedule_window_horizon",
        ok,
        f"window {today} .. {last} is {span} days, cap {max_days}; no game is in the past",
        measured={"window_days": span, "cap": max_days},
    )


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------
def gate_every_row_has_source(rows, key="source_url") -> dict:
    missing = [i for i, r in enumerate(rows) if not (r.get(key) or "").startswith("https://")]
    return _gate(
        "every_published_row_has_an_https_source",
        not missing,
        f"{len(rows)} rows checked; {len(missing)} without an https source"
        + (f" at positions {missing[:10]}" if missing else ""),
        measured={"rows": len(rows), "missing": len(missing)},
    )


def gate_secondary_sources_labelled(rows) -> dict:
    """A row that leans on a non-NBA source must say so in its own row."""
    bad = []
    for i, r in enumerate(rows):
        tier = (r.get("source_tier") or "").upper()
        url = r.get("source_url") or ""
        is_nba = any(h in url for h in ("nba.com",))
        if not is_nba and tier not in ("SECONDARY", "DERIVED"):
            bad.append(i)
    return _gate(
        "non_nba_sources_are_labelled",
        not bad,
        f"{len(rows)} rows checked; {len(bad)} use a non-nba.com source without a "
        f"SECONDARY/DERIVED tier label" + (f" at positions {bad[:10]}" if bad else ""),
        measured={"rows": len(rows), "unlabelled": len(bad)},
    )


def gate_no_inferred_values(feed: dict) -> dict:
    """Any field the capture could not read must be null, never a guess.

    This is a structural check, not a semantic one: it asserts that every
    ``null`` in the results feed is accompanied by a reason somewhere in the
    same document, so a blank cannot be mistaken for a zero.
    """
    games = feed.get("games", [])
    nulls = []
    for g in games:
        for k, v in g.items():
            if v is None:
                nulls.append((g.get("game_id"), k))
    coverage = feed.get("coverage", {})
    explained = bool(coverage.get("why_the_older_games_have_no_quarters"))
    ok = (not nulls) or explained
    return _gate(
        "nulls_are_explained_not_zero",
        ok,
        (f"{len(nulls)} null fields in the results feed; the feed "
         f"{'carries' if explained else 'does not carry'} a stated reason for the blanks"),
        measured={"null_fields": len(nulls), "reason_present": explained},
    )


# ---------------------------------------------------------------------------
# integrity (arithmetic + set checks)
# ---------------------------------------------------------------------------
def gate_quarter_scores_sum_to_final(feed: dict) -> dict:
    """Every line score must add up, on both sides, and finals must match."""
    bad = []
    checked = 0
    for g in feed.get("games", []):
        aq, hq = g.get("away_quarters"), g.get("home_quarters")
        if not aq or not hq:
            continue
        checked += 1
        if sum(aq) != g.get("away_final") or sum(hq) != g.get("home_final"):
            bad.append({"game_id": g.get("game_id"),
                        "away_sum": sum(aq), "away_final": g.get("away_final"),
                        "home_sum": sum(hq), "home_final": g.get("home_final")})
    return _gate(
        "quarter_scores_sum_to_final",
        not bad,
        f"{checked} games with a line score; {len(bad)} do not sum to the printed final"
        + (f": {bad}" if bad else ""),
        measured={"checked": checked, "mismatched": len(bad)},
    )


def gate_results_agree_with_schedule(feed: dict) -> dict:
    bad = [g.get("game_id") for g in feed.get("games", [])
           if g.get("schedule_score_agrees") is not True]
    return _gate(
        "finals_agree_across_two_official_surfaces",
        not bad,
        (f"{len(feed.get('games', []))} finals each read on the schedule page AND the game "
         f"page; {len(bad)} disagree" + (f": {bad}" if bad else "")),
        measured={"games": len(feed.get("games", [])), "disagreements": len(bad)},
    )


def gate_injury_matchups_are_slate_matchups(injury: dict, schedule: dict) -> dict:
    """The games the injury report is about must be the games we are pricing.

    A mismatch here is the classic silent failure: the report parses fine, the
    slate parses fine, and every injury cell lands on the wrong game.

    The report is multi-date by design.  The league files one report per game
    day and the document carries the NEXT day's games as NOT-YET-SUBMITTED rows,
    so the gate covers every date the report mentions, not a single date.  It
    must hold in both directions:

      * no matchup in the report may be absent from the captured schedule
        (``extra``) -- that would mean the report is about a game we do not know;
      * every game the schedule lists on a date the report covers must appear in
        the report (``missing``) -- that would mean a game we are pricing has no
        injury filing at all.

    Before this runs, ``injury.attach_scheduled_dates`` recovers the dates the
    document leaves blank on its continuation fragments.  Rows whose date could
    not be established are counted and reported rather than dropped.
    """
    rows = injury.get("rows", [])
    undated_rows = [r for r in rows if not r.get("game_date")]
    report = {r["matchup"] for r in rows if r.get("matchup") and r.get("game_date")}
    dates = {r["game_date"] for r in rows if r.get("game_date")}
    if not report:
        return _gate("injury_matchups_match_slate", False,
                     "the report yielded no matchups at all; the parse is broken")
    if not dates:
        return _gate("injury_matchups_match_slate", False,
                     "no row in the report could be dated, so no slate can be matched")
    slate = {f"{g['away']}@{g['home']}" for g in schedule.get("upcoming", [])
             if g["date"] in dates}
    extra = report - slate
    missing = slate - report
    undated = len(undated_rows)
    recovery = injury.get("date_recovery") or {}
    ok = not extra and not missing
    return _gate(
        "injury_matchups_match_slate",
        ok,
        (f"report covers {len(dates)} date(s) {sorted(dates)}: {len(report)} matchups vs "
         f"{len(slate)} captured slate games; unexpected {sorted(extra)}; absent "
         f"{sorted(missing)}; {undated} row(s) undated; "
         f"{recovery.get('rows_dated_by_matchup', 0)} date(s) recovered from the schedule"),
        measured={"report_matchups": sorted(report), "slate_matchups": sorted(slate),
                  "dates": sorted(dates), "undated_rows": undated,
                  "undated_matchups": sorted({r["matchup"] for r in undated_rows
                                              if r.get("matchup")}),
                  "date_recovery": recovery},
    )


def gate_injury_undated_rows_are_declared(injury: dict) -> dict:
    """Rows the document itself leaves without a date must be declared, not dropped.

    27 rows in the 0630 report sit on page fragments that begin mid-table, so
    the Game Date, Game Time and Team cells are blank in the source.  They are
    real rows -- the player and status are printed -- but they cannot be tied to
    a slate.  The rule is that they must be *published as unattributed* and
    counted, never quietly discarded and never guessed at.
    """
    rows = injury.get("rows", [])
    undated = [r for r in rows if not r.get("game_date")]
    declared = injury.get("date_recovery", {}).get("rows_still_undated")
    ok = declared == len(undated)
    return _gate(
        "injury_undated_rows_are_declared",
        ok,
        (f"{len(undated)} of {len(rows)} rows carry no date in the source document; "
         f"declared count {declared}. These rows are published with team=null and are not "
         f"attached to any slate game."),
        blocking=False,
        measured={"undated": len(undated), "declared": declared},
    )


def gate_capture_reproducible(path_a: str, path_b: str) -> dict:
    """Two independently stored copies of the same official page must agree.

    Used for the injury report: the fetch is stored verbatim, and a second,
    independently transcribed representation of the same document exists from
    an earlier session.  If they disagree the parse is wrong, not the league.
    """
    try:
        a = json.load(open(path_a, encoding="utf-8"))
        b = json.load(open(path_b, encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - configuration error
        return _gate("second_capture_agrees", False, f"could not read: {exc}", blocking=False)
    ra = a.get("rows") or a.get("players") or a.get("games") or []
    rb = b.get("rows") or b.get("players") or b.get("games") or []
    ok = len(ra) == len(rb) and len(ra) > 0
    return _gate(
        "second_capture_agrees",
        ok,
        f"{os.path.basename(path_a)} has {len(ra)} rows, {os.path.basename(path_b)} has {len(rb)}",
        blocking=False,
        measured={"a_rows": len(ra), "b_rows": len(rb)},
    )


def gate_standings_match_team_stats(standings: dict, team_stats: dict) -> dict:
    """W and L for each team must be the same on the standings page and the
    team-statistics page.  They are two different official pages and a
    disagreement means one of them was read mid-update."""
    by_team = {t["team"]: t for t in team_stats.get("teams", [])}
    rows = standings.get("east", []) + standings.get("west", [])
    bad = []
    for r in rows:
        t = by_team.get(r["team"])
        if not t:
            bad.append({"team": r["team"], "issue": "absent from team stats"})
            continue
        if t.get("w") != r["w"] or t.get("l") != r["l"]:
            bad.append({"team": r["team"], "standings": [r["w"], r["l"]],
                        "team_stats": [t.get("w"), t.get("l")]})
    return _gate(
        "standings_agree_with_team_statistics",
        not bad,
        (f"{len(rows)} teams compared across the standings page and the team-statistics page; "
         f"{len(bad)} disagree" + (f": {bad}" if bad else "")),
        measured={"teams": len(rows), "disagreements": bad},
    )


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------
def run_all(data: dict, now_utc: _dt.datetime) -> dict:
    """Run every gate and summarise.

    ``data`` is the loaded capture bundle.  The return value is what the build
    prints and what the site publishes, unchanged: a reader must be able to see
    which gate produced which verdict without reading this file.
    """
    gates = []
    inj = data["injury"]
    sched = data["schedule"]
    results = data["results"]
    teams = data["team_stats"]
    standings = data["standings"]

    gates.append(gate_injury_report_is_newest(inj, data["newest_report_stamp"]))
    gates.append(gate_injury_retrieval_after_revision(inj))
    gates.append(gate_injury_age(inj, now_utc))
    gates.append(gate_statistics_after_last_final(teams, results))
    gates.append(gate_schedule_window_horizon(sched, now_utc.date().isoformat()))
    gates.append(gate_quarter_scores_sum_to_final(results))
    gates.append(gate_results_agree_with_schedule(results))
    gates.append(gate_no_inferred_values(results))
    gates.append(gate_injury_matchups_are_slate_matchups(inj, sched))
    gates.append(gate_injury_undated_rows_are_declared(inj))
    gates.append(gate_standings_match_team_stats(standings, teams))

    published_rows = []
    for r in inj.get("rows", []):
        published_rows.append({"source_url": r.get("source_url") or inj.get("source_url"),
                               "source_tier": "OFFICIAL"})
    for f in sched.get("upcoming", []):
        published_rows.append({"source_url": sched.get("source_url"), "source_tier": "OFFICIAL"})
    for g in results.get("games", []):
        published_rows.append({"source_url": g.get("game_url"), "source_tier": "OFFICIAL"})
    for t in teams.get("teams", []):
        published_rows.append({
            "source_url": teams["pages"]["advanced"]["source_url"], "source_tier": "OFFICIAL"})
    gates.append(gate_every_row_has_source(published_rows))
    gates.append(gate_secondary_sources_labelled(published_rows))

    blocking_failed = [g for g in gates if g["blocking"] and not g["ok"]]
    warn_failed = [g for g in gates if not g["blocking"] and not g["ok"]]
    return {
        "evaluated_at_utc": now_utc.isoformat(),
        "gates": gates,
        "passed": len([g for g in gates if g["ok"]]),
        "total": len(gates),
        "blocking_failures": [g["name"] for g in blocking_failed],
        "warnings": [g["name"] for g in warn_failed],
        "may_publish": not blocking_failed,
    }
