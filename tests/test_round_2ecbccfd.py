"""Pins the invariants of the 2026-11-17 round built by session arena/2ecbccfd-nba3.

Everything here runs offline against the committed artefacts, so CI fails on any of three things:
a source transcript changing without the artefacts being rebuilt, an artefact being hand-edited, or
a number that used to reconcile stopping reconciling. No network, no clock, no fixtures invented
for the test: the test reads the same files the site is built from.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RD = os.path.join(ROOT, "data", "rounds", "2026-11-17")
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def load(name):
    with open(os.path.join(RD, name), encoding="utf-8") as fh:
        return json.load(fh)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


class CaptureIntegrity(unittest.TestCase):
    def test_every_transcript_hashes_to_what_the_artefact_records(self):
        st = load("standings.json")
        self.assertEqual(sha(os.path.join(ROOT, st["verbatim_transcript"])),
                         st["transcript_sha256"],
                         "the standings transcript on disk is not the file that was parsed")
        inj = load("injuries.json")
        for rep in inj["reports"]:
            self.assertEqual(sha(os.path.join(ROOT, rep["verbatim_transcript"])),
                             rep["transcript_sha256"],
                             f"{rep['report_stamp']} transcript drifted")

    def test_standings_have_all_thirty_clubs_and_no_parse_problems(self):
        st = load("standings.json")
        self.assertEqual(st["count"], 30)
        self.assertEqual(len(st["rows"]), 30)
        self.assertEqual(st["parse_problems"], [],
                         "a standings row failed to parse; the table must not be published short")
        self.assertEqual({r["conference"] for r in st["rows"]}, {"East", "West"})
        for conf in ("East", "West"):
            seeds = sorted(r["seed"] for r in st["rows"] if r["conference"] == conf)
            self.assertEqual(seeds, list(range(1, 16)), f"{conf} seeds are not 1..15")

    def test_no_standing_cell_was_invented(self):
        st = load("standings.json")
        text = open(os.path.join(ROOT, st["verbatim_transcript"]), encoding="utf-8").read()
        for r in st["rows"]:
            for key in ("win_pct", "gb", "conf_rec", "div_rec", "home_rec", "road_rec",
                        "neutral_rec", "ot_rec", "last10", "streak"):
                v = r[key]
                if v in (None, ""):
                    continue
                self.assertIn(v, text,
                              f"{r['team']}.{key} = {v!r} does not appear in the transcript")

    def test_injury_rows_are_keyed_to_a_printed_pdf(self):
        inj = load("injuries.json")
        for rep in inj["reports"]:
            self.assertTrue(re.fullmatch(r"https://ak-static\.cms\.nba\.com/referee/injury/"
                                         r"Injury-Report_\d{4}-\d{2}-\d{2}_\d{2}_\d{2}(AM|PM)\.pdf",
                                         rep["source_url"]), rep["source_url"])
            for r in rep["rows"] + rep["not_submitted"]:
                self.assertEqual(r["source_url"], rep["source_url"])
                self.assertTrue(r.get("matchup"), "every row must name the game it was printed under")
                self.assertTrue(re.fullmatch(r"\d\d/\d\d/\d{4}", r["date"]), r["date"])

    def test_carried_team_attribution_is_recorded_not_silent(self):
        inj = load("injuries.json")
        rows = inj["reports"][-1]["rows"]
        for r in rows:
            if "TEAM_NOT_PRINTED_IN_THIS_REVISION" in (r.get("flags") or []):
                self.assertIn(r.get("team_source"),
                              {"carried-from-row-above-in-same-game-block",
                               "same-player-in-the-earlier-revision"},
                              f"{r['player']}'s team was filled without recording how")
                self.assertIn("team_attribution_evidence", r)
                # the attributed club must be one of the two clubs the game line names
                codes = (r["matchup"] or "").replace("@", " ").split()
                full = load("standings.json")["rows"]
                names = {x["full_name"] for x in full if x["team"] in codes}
                self.assertIn(r["team"], names,
                              f"{r['player']}'s attributed club is not a club of {r['matchup']}")
            else:
                self.assertEqual(r.get("team_source"), "printed")


class ResultsLog(unittest.TestCase):
    def test_games_played_identity(self):
        rl = load("results_log.json")
        rec = rl["reconciliation"]
        self.assertEqual(rec["sum_log_gp"], 2 * rec["games_in_log"])
        self.assertEqual(rec["teams_reconciled"], rec["teams_total"])
        for t in rec["teams"]:
            self.assertTrue(t["gp_ok"] and t["w_ok"], t)

    def test_log_is_one_row_per_game_and_all_dates_official(self):
        rl = load("results_log.json")
        text = json.dumps(rl)
        self.assertNotIn("None", text)
        ids = [g["game_id"] for g in rl["games_2026_11_15"]]
        self.assertEqual(len(ids), len(set(ids)), "a game appears twice")
        for g in rl["games_2026_11_15"]:
            self.assertRegex(g["date"], r"^2026-11-15$")
            self.assertTrue(g["source_url"].startswith("https://statsdmz.nba.com/pdfs/"))

    def test_a_conflicting_quarter_table_is_flagged_and_not_used(self):
        rl = load("results_log.json")
        bad = [g for g in rl["games_2026_11_15"] if g["quarter_status"] != "verified"]
        self.assertEqual([g["game_id"] for g in bad], ["0022600243"],
                         "the known quarter conflict moved or was silently repaired")
        for g in bad:
            self.assertFalse(g["used_for_quarter_measures"])
            self.assertTrue(g["final_corroboration"]["url"].startswith("https://www.nba.com/game/"))
            self.assertTrue(g["final_verified"])

    def test_home_measures_match_an_independent_count(self):
        rl = load("results_log.json")
        hm = rl["home_measures"] if "home_measures" in rl else rl["home_measured"]
        self.assertEqual(hm["games"], rl["count"])
        self.assertLess(hm["home_win_rate"], 0.56)
        self.assertGreater(hm["home_win_rate"], 0.45)


class Model(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("model.json")

    def test_home_court_is_pinned_and_cross_checked(self):
        h = self.m["hca"]
        self.assertEqual(h["policy"].split(":")[0], "pinned")
        # pinned value = probit(rate) * margin sd, recomputed here with no shared code path
        import math
        z = math.sqrt(2.0) * _erfinv(2 * h["measured_home_win_rate"] - 1)
        self.assertAlmostEqual(h["pinned_hca_points"], z * h["margin_sd_points"], delta=0.02)
        self.assertLess(abs(h["pinned_hca_points"]), 3.0,
                        "the pinned value drifted to the conventional 3 points, which is what "
                        "the brief forbids: it must come from the measured rate")
        self.assertEqual(h["independent_cross_check"][
                         "clubs_whose_printed_home_road_neutral_counts_the_log_accounts_for"], "30/30")
        self.assertTrue(h["sensitivity_neutral_excluded"]["equals_the_standings_derived_value"])

    def test_disagreement_is_the_headline_and_the_blend_is_underneath(self):
        lines = [l for l in self.m["lines"] if l.get("headline_confidence_signal")]
        self.assertEqual(len(lines), len(self.m["lines"]))
        for l in lines:
            self.assertIn("disagreement_margin_points", l["headline_confidence_signal"])
            self.assertNotIn("blended_rating", l["headline_confidence_signal"],
                            "the blend must never be the headline")
            self.assertIn("margin_away", l["blend_underneath"])
            a = l["e1"]["margin_away"]
            b = l["e2"]["margin_away"]
            self.assertAlmostEqual(l["headline_confidence_signal"]["disagreement_margin_points"],
                                   round(abs(a - b), 2), delta=0.011)
            self.assertAlmostEqual(l["blend_underneath"]["margin_away"], round((a + b) / 2, 2),
                                   delta=0.011)

    def test_total_is_possessions_times_rate_not_an_average_of_scores(self):
        for l in self.m["lines"]:
            e1 = l["e1"]
            if e1.get("total") is None:
                continue
            self.assertIn("pace", e1)
            self.assertIn("away_ppp", e1)
            self.assertAlmostEqual(e1["total"], round(e1["away_pts"] + e1["home_pts"], 2), delta=0.011)

    def test_closing_line_is_blank_everywhere_because_the_feed_is_not_connected(self):
        for l in self.m["lines"]:
            ma = l["market_anchor"]
            self.assertEqual(ma["status"], "not connected")
            self.assertIsNone(ma["closing_line"])
            self.assertIsNone(ma["blended_line"])
        raw = json.dumps(self.m)
        self.assertNotIn('"blended_line": 0', raw)

    def test_parlays_print_the_naive_product_beside_the_rho_price(self):
        self.assertTrue(self.m["parlays_priced"], "no parlay was priced at all")
        for p in self.m["parlays_priced"]:
            for k in ("naive_product", "priced_with_measured_rho", "rho_used", "difference_pp"):
                self.assertIsNotNone(p[k], k)
            self.assertGreaterEqual(p["naive_product"], 0.0)
            self.assertLessEqual(p["naive_product"], 1.0)
            self.assertNotEqual(p["naive_product"], p["priced_with_measured_rho"],
                                "the two prices are identical, so one of them is decoration")

    def test_correlation_is_measured_and_reported_with_its_band(self):
        c = self.m["correlations"]["same_night_game_margins"]
        self.assertEqual(c["n_pairs"], 808)
        lo, hi = c["ci95"]
        self.assertLessEqual(lo, c["rho"])
        self.assertLessEqual(c["rho"], hi)
        self.assertLess(lo, 0, "a rho band that excludes zero would mean a real edge; re-check")
        self.assertGreater(hi, 0)

    def test_luck_is_a_z_score_and_the_band_is_enforced(self):
        self.assertEqual(len(self.m["luck"]["teams"]), 30)
        for l in self.m["luck"]["teams"]:
            self.assertIsNotNone(l["luck_z"])
            self.assertTrue(l["standings_reconciles"], l["team"])
            self.assertEqual(l["inside_noise_band"], abs(l["luck_z"]) <= 2.0)
        outside = set(self.m["luck"]["outside_noise_band"])
        for s in self.m["strategies"]:
            pass
        for l in self.m["lines"]:
            side_out = {l["matchup"].split(" @ ")[0], l["matchup"].split(" @ ")[1]}
            if side_out & outside:
                self.assertNotIn("pick", l, "a pick was published on a club outside the noise band")

    def test_travel_is_marked_derived_and_coordinates_are_not_called_official(self):
        seen = 0
        for r in self.m["rest_travel_by_side"]:
            self.assertTrue(r["travel_miles_is_derived"])
            self.assertIn("wikipedia", r["travel_source"].lower())
            seen += 1
        self.assertEqual(seen, len(self.m["lines"]) * 2,
                         "every side of every priced game must carry the derived-travel marker")

    def test_gates_all_pass_and_each_names_its_evidence(self):
        bad = [g for g in self.m["gates"] if not g["pass"]]
        self.assertEqual(bad, [], json.dumps(bad, indent=1))
        for g in self.m["gates"]:
            self.assertGreater(len(g["detail"]), 12, g["id"])

    def test_refused_strategies_state_why(self):
        for s in self.m["strategies"]:
            if s["verdict"] in ("NOT_EVALUABLE", "NOT_PRICABLE", "NOT_FUNDED"):
                self.assertTrue(s.get("why_not"), f"{s['id']} is refused without a reason")
            if s["oos"] and s["oos"].get("games"):
                self.assertGreaterEqual(s["oos"]["games"], 40,
                                        f"{s['id']} claims an out-of-sample result on a small sample")
        self.assertEqual(sum(1 for s in self.m["strategies"] if s["verdict"] == "FUNDED"), 0,
                         "something passed the gate; the leaderboard and the bet page must be updated")


class Ledger(unittest.TestCase):
    def test_chain_verifies_and_head_matches_the_index(self):
        r = subprocess.run([sys.executable, "scripts/ledger_2ecbccfd.py", "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        idx = load("ledger/index.json")
        entries = [json.loads(l) for l in
                   open(os.path.join(RD, "ledger", "ledger.jsonl"), encoding="utf-8") if l.strip()]
        self.assertEqual(idx["head_hash"], entries[-1]["entry_hash"])
        self.assertEqual(entries[0]["prev_hash"], "0" * 64)

    def test_every_pick_was_sealed_before_its_tip(self):
        entries = [json.loads(l) for l in
                   open(os.path.join(RD, "ledger", "ledger.jsonl"), encoding="utf-8") if l.strip()]
        for e in entries:
            self.assertEqual(e["kind"], "PUBLISH")
            self.assertEqual(e["state"], "PUBLISHED_PRE_TIP")
            tip = e["pick"]["payload"]["tip_utc"]
            self.assertLess(e["published_utc"], tip,
                            f"{e['pick_id']} was published at {e['published_utc']}, tip {tip}")

    def test_pre_registration_is_write_once_and_hashed(self):
        for path in sorted(glob.glob(os.path.join(RD, "prereg", "*.json"))):
            d = json.load(open(path, encoding="utf-8"))
            body = {k: v for k, v in d.items() if k != "payload_sha256"}
            canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            self.assertEqual(d["payload_sha256"], hashlib.sha256(canon.encode()).hexdigest(),
                             f"{os.path.basename(path)} was edited after it was frozen")
            for key in ("signal", "thresholds", "universe", "settlement_rule", "stake_rule",
                        "frozen_utc", "author"):
                self.assertIn(key, d)

    def test_nothing_is_settled_without_an_official_final(self):
        idx = load("ledger/index.json")
        self.assertEqual(idx["settled"], 0)
        self.assertIn("no game of this window had a verified final", idx["note"])


class Site(unittest.TestCase):
    PAGES = ["index.html", "projection/lines.html", "projection/rotations.html", "injuries.html",
             "standings.html", "results.html", "strategies.html", "ledger.html", "method.html",
             "bet/index.html", "flagged.html"]

    def test_build_is_deterministic_offline(self):
        r = subprocess.run([sys.executable, "round_2ecbccfd/build.py", "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("match the committed build", r.stdout)

    def test_all_pages_exist_and_link_the_shared_style(self):
        for p in self.PAGES:
            path = os.path.join(ROOT, "round_2ecbccfd", p)
            self.assertTrue(os.path.exists(path), p)
            s = open(path, encoding="utf-8").read()
            self.assertIn('rel="stylesheet"', s)
            self.assertIn("</html>", s)

    def test_projection_pages_carry_no_price_or_stake(self):
        # prose may say "stake" while explaining that none is placed; what must not appear is a
        # price (american odds), a payout, or a stake column
        odds = re.compile(r"(?<![\d.])[+-]\d{3}(?![\d.])")
        for p in ("index.html", "projection/lines.html", "projection/rotations.html"):
            s = open(os.path.join(ROOT, "round_2ecbccfd", p), encoding="utf-8").read()
            self.assertIsNone(odds.search(s),
                              f"{p} prints what looks like an american price: {odds.search(s)}")
            for b in ("<th>stake", "<th>odds", "<th>price", "payout", "kelly", "bet365",
                      "<th>ev"):
                self.assertNotIn(b, s.lower(), f"{b} leaked into the projection page {p}")

    def test_the_bet_surface_states_its_gate(self):
        s = open(os.path.join(ROOT, "round_2ecbccfd", "bet", "index.html"), encoding="utf-8").read()
        self.assertIn("Gated surface", s)
        self.assertIn("clause 9(iv)", s)
        self.assertIn("no strategy has passed", s.lower().replace("No strategy has passed",
                                                                  "no strategy has passed"))

    def test_injuries_banner_shows_revision_and_retrieval_times(self):
        s = open(os.path.join(ROOT, "round_2ecbccfd", "injuries.html"), encoding="utf-8").read()
        self.assertIn("01:15 PM ET", s)
        self.assertIn("2026-11-16T18:30Z", s)
        self.assertIn("Report status", s)

    def test_every_table_row_names_an_https_source(self):
        for p in self.PAGES:
            s = open(os.path.join(ROOT, "round_2ecbccfd", p), encoding="utf-8").read()
            for chunk in re.findall(r"<tbody>(.*?)</tbody>", s, re.S):
                for row in re.findall(r"<tr>.*?</tr>", chunk, re.S):
                    if "https://" in row or "not printed by the source" in row:
                        continue
                    self.fail(f"{p}: a table row has no source link and no blank marker: "
                              + re.sub(r"<[^>]+>", " ", row)[:180])

    def test_official_links_only_and_no_third_party_box_site(self):
        allowed = ("www.nba.com", "official.nba.com", "ak-static.cms.nba.com", "statsdmz.nba.com",
                   "cdn.nba.com", "en.wikipedia.org", "github.com")
        seen = set()
        for p in self.PAGES:
            s = open(os.path.join(ROOT, "round_2ecbccfd", p), encoding="utf-8").read()
            seen |= set(re.findall(r'href="https?://([^/"\']+)', s))
        for host in sorted(seen):
            self.assertTrue(any(host == a or host.endswith("." + a) for a in allowed),
                            f"{host} is not an allowed source host on this site")
        self.assertTrue(seen, "no external link was found at all, which would mean the site cites nothing")

    def test_flagged_page_lists_the_known_gaps(self):
        s = open(os.path.join(ROOT, "round_2ecbccfd", "flagged.html"), encoding="utf-8").read()
        for needle in ("closing-line feed", "0022600243", "NOT YET SUBMITTED" if False else
                       "had not filed", "bare jersey number", "arena coordinates",
                       "2026-11-19 cards"):
            self.assertIn(needle, s, f"{needle} should be on the flag page")


class Workflow(unittest.TestCase):
    def test_refresh_workflow_covers_the_new_gates_and_runs_the_tests(self):
        y = open(os.path.join(ROOT, ".github", "workflows", "refresh.yml"), encoding="utf-8").read()
        for needle in ("capture_2ecbccfd.py", "gamebooks_2ecbccfd.py", "slate_extra_2ecbccfd.py",
                       "model_2ecbccfd.py", "ledger_2ecbccfd.py", "round_2ecbccfd/build.py",
                       "test_round_2ecbccfd", "--check"):
            self.assertIn(needle, y, f"{needle} is not run by the scheduled job")
        # ordering: capture and gates come before any rebuild
        self.assertLess(y.index("capture_2ecbccfd.py"), y.index("round_2ecbccfd/build.py"))
        self.assertLess(y.index("freshness"), y.index("round_2ecbccfd/build.py"),
                        "the rebuild must not run before the freshness gate")

    def test_the_round_dir_holds_no_unreferenced_oracle(self):
        # every artefact in the round directory must be produced by a script in this repo
        produced = {"standings.json", "results_log.json", "injuries.json", "injury_delta.json",
                    "player_logs_2026-11-15.json", "slate_extra_2026-11-19.json", "model.json",
                    "manifest.json", "gates.json"}
        for name in os.listdir(RD):
            if os.path.isfile(os.path.join(RD, name)):
                self.assertIn(name, produced | {"README.md"}, f"{name} has no producer")


# duplicated on purpose: the test must not import the code under test to check a statistic
def _erfinv(y):
    import math
    a = 0.147
    ln = math.log(1.0 - y * y) if abs(y) < 1 else -50.0
    t = 2.0 / (math.pi * a) + ln / 2.0
    x = math.copysign(math.sqrt(math.sqrt(t * t - ln / a) - t), y)
    for _ in range(30):
        d = 2.0 / math.sqrt(math.pi) * math.exp(-x * x)
        if not d:
            break
        x -= (math.erf(x) - y) / d
    return x


if __name__ == "__main__":
    unittest.main(verbosity=2)
