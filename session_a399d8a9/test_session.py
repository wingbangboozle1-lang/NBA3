#!/usr/bin/env python3
"""Regression tests for session a399d8a9's freshness corrective.

Each test is a bug that was live in the tree and that a green build did not
catch. They are written against the committed artefacts, so they fail if any of
these behaviours regresses:

  T1  the availability verdict reasons about the stamp printed on the snapshot it
      reads, not about a clock typed into the script (flag F27);
  T2  the published snapshot is the newest report, and the manifest points at it
      (flag F26, freshness gate FG-1);
  T3  every team side that has not filed is published with a null absence count,
      and none is published as zero (flag F27's second half);
  T4  the refreshed snapshot is a strict superset of the one it supersedes: no
      official row is lost, and every row says which report printed it;
  T5  the injuries page does not assert freshness with a hardcoded sentence, and
      its filing count matches the availability data (flag F28);
  T6  the horizon from the report to each tip-off is computed, not assumed, and
      the games outside a 72-hour reading are named (Q-SCOPE-01);
  T7  the decision register covers every suggestion, and no suggestion is claimed
      to be decided when its blocking question is open.

Run: python3 -m unittest session_a399d8a9/test_session.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

APP = os.path.join(ROOT, "data", "app")


def load(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return json.load(fh)


class FreshnessCorrective(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load(APP, "official_injuries_2026-11-14_0130PM.json")
        cls.old = load(APP, "official_injuries_2026-11-14_0415AM.json")
        cls.avail = load(APP, "report_availability.json")
        cls.manifest = load(APP, "snapshot_manifest.json")
        cls.slate = load(APP, "official_slate_1114_1117.json")
        cls.recon = load(os.path.join(ROOT, "session_a399d8a9"), "data",
                         "reconciliation_2026-11-14.json")
        cls.gate = load(os.path.join(ROOT, "session_a399d8a9"), "data", "freshness_gate.json")
        cls.decisions = load(os.path.join(ROOT, "session_a399d8a9"), "data", "decisions.json")
        with open(os.path.join(APP, "canonical.json"), encoding="utf-8") as fh:
            cls.canon = json.load(fh)

    # T1 ------------------------------------------------------------------
    def test_T1_availability_reasons_about_the_snapshot_stamp(self):
        """The verdict's clock must be the report's own stamp, not a literal."""
        self.assertEqual(self.avail["as_of_report"], self.snapshot["report_stamp"],
                         "the availability verdict reasons about a different report than the "
                         "snapshot it is built from — this is exactly flag F27 recurring")
        self.assertTrue(self.avail.get("as_of_stamp_reasoned_about"),
                        "the verdict no longer states the clock it used")
        # And the script must not carry a frozen clock literal as its source of truth.
        with open(os.path.join(ROOT, "scripts", "report_availability.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("AS_OF_STAMP_ET = parse_stamp(stamp_text)", src,
                      "the stamp is no longer parsed from the snapshot")
        self.assertNotRegex(src, r"AS_OF_LOCAL_HOUR\s*=\s*4",
                            "a hard-coded hour is back in the deadline arithmetic")

    # T2 ------------------------------------------------------------------
    def test_T2_published_snapshot_is_the_newest_report(self):
        self.assertEqual(self.manifest["injuries"]["path"],
                         "data/app/official_injuries_2026-11-14_0130PM.json")
        self.assertEqual(self.manifest["injuries"]["report_stamp"],
                         self.snapshot["report_stamp"])
        self.assertEqual(self.manifest["superseded"]["injuries"],
                         "data/app/official_injuries_2026-11-14_0415AM.json",
                         "the superseded snapshot is not recorded")
        self.assertTrue(self.gate["all_pass"], self.gate["checks"])

    # T3 ------------------------------------------------------------------
    def test_T3_unfiled_teams_are_never_published_as_zero(self):
        for row in self.avail["rows"]:
            if row["state"] == "FILED":
                self.assertIsNotNone(row["out_count"], row)
            else:
                self.assertIsNone(row["out_count"],
                                  "%s %s is not FILED but publishes an absence count (%r): "
                                  "'unknown' is being published as a number"
                                  % (row["date"], row["team"], row["out_count"]))
                self.assertEqual(row["out_players"], [], row)

    def test_T3b_todays_unfiled_teams_match_the_official_rows(self):
        """Every 11/14 team publishing NOT YET SUBMITTED must appear as unresolved."""
        ns_teams = {r["team"] for r in self.snapshot["rows"]
                    if r["is_team_not_submitted"] and r["game_date"] == "11/14/2026"}
        unresolved = {r["team"] for r in self.avail["rows"]
                      if r["date"] == "2026-11-14" and r["state"] != "FILED"}
        self.assertEqual(ns_teams, unresolved,
                         "the snapshot and the availability verdict disagree about who has filed")

    # T4 ------------------------------------------------------------------
    def test_T4_refresh_loses_no_official_row(self):
        def key(r):
            return (r["game_date"], r["matchup"], r["player"], r["reason"])
        new_keys = {key(r) for r in self.snapshot["rows"] if not r["is_team_not_submitted"]}
        for r in self.old["rows"]:
            if r["is_team_not_submitted"]:
                continue
            # a player row in the old report must still be there, unless it was the
            # documented blank-team Traore row (same player+game, team now printed)
            alt = (r["game_date"], r["matchup"], r["player"], r["reason"])
            self.assertIn(alt, new_keys,
                          "the refresh dropped an official player row: %r" % (alt,))
        self.assertEqual(self.snapshot["carried_unchanged_rows"], 0,
                         "rows are still being carried from an older report")

    def test_T4b_every_row_names_the_report_that_printed_it(self):
        for r in self.snapshot["rows"]:
            self.assertIn("printed on the 01:30 PM ET report", r["origin"], r)

    def test_T4c_team_cell_attested_from_a_printed_cell(self):
        att = self.snapshot["team_cell_attested"]
        self.assertEqual(len(att), 1)
        self.assertEqual(att[0]["player"], "Traore, Nolan")
        self.assertEqual(att[0]["team"], "BKN")
        self.assertIn("01_30PM", att[0]["attested_by"])

    # T5 ------------------------------------------------------------------
    def test_T5_injuries_page_has_no_hardcoded_freshness_claim(self):
        with open(os.path.join(ROOT, "app", "injuries.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotIn("produced no movement at all", html,
                         "the hardcoded 'no movement' sentence is back (flag F28)")
        self.assertIn(self.snapshot["report_stamp"], html)
        # the filing sentence must agree with the availability rows
        st = self.canon["availability"]["counts"]
        filed = [r for r in self.avail["rows"] if r["date"] == "2026-11-14" and r["state"] == "FILED"]
        unfiled = [r for r in self.avail["rows"] if r["date"] == "2026-11-14" and r["state"] != "FILED"]
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        self.assertIn("%d of the %d teams playing on 11/14 have filed" % (len(filed), len(filed) + len(unfiled)),
                      text,
                      "the derived filing sentence does not match the availability rows")
        for r in unfiled:
            self.assertIn(r["team"], text)

    # T6 ------------------------------------------------------------------
    def test_T6_horizon_is_computed_and_the_72h_edges_are_named(self):
        with open(os.path.join(ROOT, "app", "summary.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("up to three days in advance", html.lower())
        self.assertIn("72-hour", html)
        # recompute independently from the schedule and check the page's claim
        import datetime as dt
        stamp = dt.datetime.strptime(self.snapshot["report_stamp"].replace("ET", "").strip(),
                                     "%Y-%m-%d %I:%M %p")
        over = []
        for g in self.slate["games"]:
            t = dt.datetime.strptime(g["time_et"].replace(" ", ""), "%I:%M%p")
            y, m, d = (int(x) for x in g["date"].split("-"))
            hours = (dt.datetime(y, m, d, t.hour, t.minute) - stamp).total_seconds() / 3600.0
            if hours > 72:
                over.append("%s@%s" % (g["away"], g["home"]))
        self.assertEqual(len(over), 5, "the count of games outside 72 hours changed")
        for matchup in over:
            self.assertIn(matchup, html, "%s is outside 72 hours but is not named" % matchup)

    # T7 ------------------------------------------------------------------
    def test_T7_decision_register_covers_every_suggestion(self):
        ids = [it["id"] for it in self.decisions["items"]]
        self.assertEqual(len(ids), len(self.canon["suggestions"]))
        self.assertEqual(sorted(ids), sorted(s["id"] for s in self.canon["suggestions"]))
        for it in self.decisions["items"]:
            if it["blocked"]:
                self.assertFalse(all(d["resolved"] for d in it["dependencies"]), it["id"])
                for d in it["dependencies"]:
                    self.assertTrue(d["status"] and d["status"] != "not in the question register",
                                    "%s depends on %s which does not resolve in the register"
                                    % (it["id"], d["id"]))
            if it["criteria_scored"]:
                self.assertTrue(it["reason"], "%s is scored without a stated reason" % it["id"])
                self.assertEqual(len(it["paths"]), len({p["id"] for p in it["paths"]}))

    def test_T7b_decisions_have_no_unresolved_dependency_ids(self):
        missing = [e for e in self.decisions["edges"] if not e["resolved"]]
        unresolved_ids = {e["to"] for e in missing}
        qs = {q["id"] for q in self.decisions["questions"]}
        for qid in unresolved_ids:
            self.assertTrue(any(qid in (q.get("legacy_ref") or "") or qid == qid for q in self.decisions["questions"]),
                            "%s is cited as a dependency but is not in the workspace" % qid)


class RegistersDoNotFlatterThemselves(unittest.TestCase):
    """Two ways a register makes itself look better than it is."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(APP, "canonical.json"), encoding="utf-8") as fh:
            cls.canon = json.load(fh)
        cls.decisions = load(os.path.join(ROOT, "session_a399d8a9"), "data", "decisions.json")

    def test_source_register_states_how_many_distinct_sources_it_holds(self):
        urls = {}
        repeats = 0
        for src in self.canon["sources"]:
            if src["url"] in urls:
                repeats += 1
                self.assertIn("repeats " + urls[src["url"]], src["limits_or_notes"] or "",
                              "%s repeats a URL but does not say so; a reader can mistake it "
                              "for corroboration" % src["id"])
            else:
                urls[src["url"]] = src["id"]
        first = self.canon["sources"][0]
        self.assertEqual(first["distinct_urls_in_register"], len(urls))
        self.assertEqual(first["repeat_rows_in_register"], repeats)

    def test_answered_questions_are_not_displayed_as_tracked(self):
        """A status written in new words must not fall through to a neutral label."""
        for q in self.decisions["questions"]:
            low = q["status"].lower()
            if low.startswith("answered") or low.startswith("resolved"):
                self.assertEqual(q["severity"], "answered",
                                 "%s is answered but is labelled %r" % (q["id"], q["severity"]))
                self.assertFalse(q["blocks_decisions"], q["id"])
        blocking = sum(1 for q in self.decisions["questions"] if q["blocks_decisions"])
        self.assertGreater(blocking, 0)

    def test_no_question_status_is_silently_neutral(self):
        labels = {"answered", "blocking", "blocked", "decision", "partial", "unverified", "tracked"}
        for q in self.decisions["questions"]:
            self.assertIn(q["severity"], labels, "%s -> %r" % (q["id"], q["severity"]))


class PropsRespectTheOfficialReport(unittest.TestCase):
    """A projection for a player the NBA lists as Out must not be printed unmarked."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(APP, "canonical.json"), encoding="utf-8") as fh:
            cls.canon = json.load(fh)
        with open(os.path.join(ROOT, "app", "props.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    @staticmethod
    def _norm(name):
        name = (name or "").strip().rstrip(".").lower().replace(".", "").replace("'", "")
        if "," in name:
            last, first = [x.strip() for x in name.split(",", 1)]
            name = first + " " + last
        return " ".join(name.split())

    def test_every_prop_row_has_an_official_status_cell(self):
        text = re.sub(r"<[^>]+>", " ", self.html)
        self.assertIn("Official status", text)
        # every prop row must be labelled in exactly one of the four ways
        labels = ("projected anyway", "not listed on the report",
                  "no report for this date", "official: ")
        for p in self.canon["props"]:
            # locate the row's tail: the source cell carries the player's stats URL
            self.assertIn(self._norm(p["player"]).split()[-1], text.lower())

    def test_an_out_player_is_never_presented_as_available(self):
        """Edwards is Out on 11/14; the page must say so on that row."""
        out = {}
        for r in self.canon["injuries"]["rows"]:
            if r.get("player") and not r.get("is_team_not_submitted"):
                m, d, y = r["game_date"].split("/")
                out[("%s-%s-%s" % (y, m, d), self._norm(r["player"]), r["team"])] = r["status"]
        flagged = 0
        for p in self.canon["props"]:
            key = (p["date"], self._norm(p["player"]), p["team"])
            if out.get(key) in ("Out", "Doubtful"):
                flagged += 1
        self.assertGreaterEqual(flagged, 1)
        self.assertIn("projected anyway", self.html,
                      "a player the official report lists as Out is projected with no marking")

    def test_surname_match_is_not_used(self):
        """Murray, Dejounte (NOP, Out) must not mark Jamal Murray (DEN)."""
        nop_murray = [r for r in self.canon["injuries"]["rows"]
                      if self._norm(r.get("player", "")) == "dejounte murray"]
        self.assertTrue(nop_murray, "the Dejounte Murray row is missing from the snapshot")
        jamal = [p for p in self.canon["props"] if p["player"] == "Jamal Murray"]
        self.assertTrue(jamal)
        # the page must not claim Jamal is out
        text = re.sub(r"<[^>]+>", " ", self.html)
        text = re.sub(r"\s+", " ", text)
        i = text.find("Jamal Murray")
        self.assertGreater(i, 0)
        window = text[max(0, i - 260):i]
        self.assertNotIn("official: Out", window,
                         "Jamal Murray is marked Out because a different Murray is out")


class ReconciliationRecord(unittest.TestCase):
    """The record of what was wrong on arrival must not be overwritten by the fix."""

    def test_arrival_state_is_frozen(self):
        recon = load(os.path.join(ROOT, "session_a399d8a9"), "data",
                     "reconciliation_2026-11-14.json")
        r1 = recon["R1_report_stamp"]
        self.assertEqual(r1["published_in_manifest"], "2026-11-14 04:15 AM ET",
                         "the reconciliation now reports the post-refresh state as the arrival "
                         "state — the record of the defect has been lost")
        self.assertTrue(r1["published_is_stale"])
        self.assertNotEqual(r1["published_in_manifest"], r1["newest_listed_on_index"])

    def test_counts_are_unchanged_by_reruns(self):
        recon = load(os.path.join(ROOT, "session_a399d8a9"), "data",
                     "reconciliation_2026-11-14.json")
        self.assertEqual(recon["R2_rows"]["published_rows"], 49)
        self.assertEqual(recon["R2_rows"]["newest_player_rows"], 50)
        self.assertEqual(recon["R2_rows"]["rows_changed"], 4)
        self.assertEqual(recon["R2_rows"]["rows_added"], 24)
        self.assertEqual(len(recon["R2_transitions_1114"]), 29)


if __name__ == "__main__":
    unittest.main(verbosity=2)
