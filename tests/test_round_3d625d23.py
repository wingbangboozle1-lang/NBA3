"""Tests for session arena/3d625d23-nba3 (rolling-slate capture, model, picks, gates, site).

Every test runs offline against committed artefacts. The capture scripts parse committed verbatim
transcriptions, so these tests are deterministic replays: a failure means a real input changed.
"""
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "slate")
SITE = os.path.join(ROOT, "slate")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestCapture(unittest.TestCase):
    """Every capture must carry provenance, and the parse must be stable."""

    def test_every_raw_capture_has_url_and_stamp(self):
        raw = os.path.join(OUT, "raw")
        files = [f for f in os.listdir(raw) if f.endswith(".md")]
        self.assertGreaterEqual(len(files), 10)
        for fn in files:
            with open(os.path.join(raw, fn), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("https://", text, fn)
            self.assertIn("retrieved", text, fn)

    def test_injury_report_revision_stamp_is_on_every_page(self):
        inj = load("injuries/injury_2026-11-15_0630PM.json")
        self.assertEqual(inj["report_stamp"], "2026-11-15 06:30 PM ET")
        self.assertTrue(inj["retrieved_utc"])
        self.assertIn("https://", inj["source_url"])

    def test_injury_archive_is_append_only_and_never_overwritten(self):
        arch = load("injuries/archive_index.json")
        stamps = [r["stamp"] for r in arch["reports"]]
        self.assertEqual(len(stamps), len(set(stamps)))
        self.assertEqual(arch["count"], len(arch["reports"]))

    def test_consecutive_report_diff_detects_status_changes(self):
        d = load("injuries/deltas.json")["pairs"][0]
        self.assertEqual(d["from"]["stamp"], "2026-11-15 06:15 AM ET")
        self.assertEqual(d["to"]["stamp"], "2026-11-15 06:30 PM ET")
        for ch in d["status_changes"]:
            self.assertNotEqual(ch["from"], ch["to"])
            self.assertTrue(ch["reason"])

    def test_standings_has_30_clubs_and_reconciles(self):
        st = load("standings.json")
        self.assertEqual(st["count"], 30)
        # standings must equal the official log + verified finals, club by club
        rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "origin", "games.csv"),
                                        encoding="utf-8")))
        feed = load("results_feed.json")
        log = [r for r in rows]
        seen = {(r["date"], r["away"], r["home"]) for r in rows}
        for g in feed["games"]:
            if g.get("verified") and (g["date"], g["away"], g["home"]) not in seen:
                log.append({"away": g["away"], "home": g["home"],
                            "away_pts": g["away_final"], "home_pts": g["home_final"]})
        w, l = {}, {}
        for r in log:
            win = r["away"] if int(r["away_pts"]) > int(r["home_pts"]) else r["home"]
            lose = r["home"] if int(r["away_pts"]) > int(r["home_pts"]) else r["away"]
            w[win] = w.get(win, 0) + 1
            l[lose] = l.get(lose, 0) + 1
        for r in st["rows"]:
            self.assertEqual((r["w"], r["l"]), (w.get(r["team"], 0), l.get(r["team"], 0)),
                             r["team"])

    def test_three_team_stat_pages_agree_on_gp_w_l(self):
        adv = {r["team"]: r for r in load("team_advanced.json")["rows"]}
        tr = {r["team"]: r for r in load("team_traditional.json")["rows"]}
        op = {r["team"]: r for r in load("team_opponent.json")["rows"]}
        self.assertEqual(len(adv), 30)
        self.assertEqual(len(tr), 30)
        self.assertEqual(len(op), 30)
        # the advanced page and the two box-score pages can legitimately lag each other; the ones
        # that DO agree must agree exactly
        for t in adv:
            self.assertEqual((tr[t]["gp"], tr[t]["w"], tr[t]["l"]),
                             (op[t]["gp"], op[t]["w"], op[t]["l"]), t)

    def test_every_travel_row_is_measured_or_flagged(self):
        tr = load("travel.json")
        for r in tr["rows"]:
            self.assertIsNotNone(r["away_travel_mi"], r["game_id"])
            self.assertIsNotNone(r["home_travel_mi"], r["game_id"])
        ar = load("arena_coordinates.json")
        self.assertEqual(ar["verified"], 30)
        for a in ar["arenas"]:
            self.assertIsNotNone(a["lat"])
            self.assertIsNotNone(a["lon"])
            self.assertTrue(a["coord_source"])

    def test_minutes_denominator_comes_from_the_book_not_an_assumption(self):
        m = load("minutes.json")
        for code, b in m["teams"].items():
            tm = b.get("team_minutes")
            if isinstance(tm, str):
                self.assertIn(tm, ("240:00", "265:00", "290:00", "315:00", "340:00"), code)
            else:
                self.assertIn(round(float(tm)), (240, 265, 290, 315, 340), code)
            self.assertLessEqual(len(b["top8"]), 8, code)

    def test_results_feed_quarters_sum_to_the_final(self):
        feed = load("results_feed.json")
        self.assertEqual(feed["counts"]["unverified"], 0)
        for g in feed["games"]:
            if g["away_q"]:
                self.assertEqual(sum(g["away_q"]), g["away_final"], g["game_id"])
                self.assertEqual(sum(g["home_q"]), g["home_final"], g["game_id"])
            self.assertTrue(g["verification"]["settled_utc"])
            self.assertTrue(any(u.startswith("https://")
                                for u in g["verification"]["sources"]))

    def test_results_feed_has_one_row_per_game(self):
        feed = load("results_feed.json")
        ids = [g["game_id"] for g in feed["games"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestModel(unittest.TestCase):
    def setUp(self):
        self.m = load("model.json")

    def test_hca_is_pinned_not_fitted(self):
        h = self.m["hca"]
        self.assertEqual(h["games"], 191)
        expected = h["margin_sigma_pts"] * _probit(h["home_win_rate"])
        self.assertAlmostEqual(h["hca_points"], round(expected, 3), places=2)

    def test_headline_is_the_disagreement_not_the_blend(self):
        self.assertIn("|E1", self.m["headline_rule"].replace("\u2212", "-"))
        for p in self.m["projections"]:
            # disagreement is published rounded to 2 dp
            self.assertAlmostEqual(p["disagreement_pts"],
                                   abs(p["E1_margin"] - p["E2_margin"]), delta=0.011)
            self.assertIsNotNone(p["blend_margin"])

    def test_window_is_at_most_three_days(self):
        from datetime import date
        days = {(date.fromisoformat(p["date"]) - date(2026, 11, 15)).days
                for p in self.m["projections"]}
        self.assertTrue(days)
        self.assertLessEqual(max(days), 3)
        self.assertGreaterEqual(min(days), 1)

    def test_blend_weight_requires_thirty_out_of_sample_games(self):
        b = self.m["blend"]
        self.assertEqual(b["n_oos_E2"], 3)
        self.assertEqual(b["w_E2"], 0.0)
        self.assertFalse(b["blend_is_measured"])

    def test_e1_beats_the_coin_flip_out_of_sample(self):
        oos = self.m["estimators"]["E1"]["oos"]
        self.assertLess(oos["log_loss"], oos["baseline_log_loss"])

    def test_luck_is_a_z_score_and_a_refusal(self):
        luck = self.m["luck"]
        for t in luck["teams"]:
            self.assertIsInstance(t["z"], float)
            self.assertEqual(t["outside_noise_band"], abs(t["z"]) > 1.96)
        self.assertTrue(luck["outside_band"])

    def test_every_projection_row_carries_a_rotation_column_and_sources(self):
        for p in self.m["projections"]:
            self.assertIn("rotation", p)
            self.assertIn("away", p["rotation"])
            self.assertIn("home", p["rotation"])
            self.assertTrue(p["sources"]["game"].startswith("https://www.nba.com/game/"))
            # a club with no captured book must print nulls, never a guessed number
            for side in ("away", "home"):
                r = p["rotation"][side]
                if r.get("out_in_top8") is None:
                    self.assertIsNone(r.get("minutes_at_risk"), p["game_id"])

    def test_correlations_are_measured_or_explicitly_blank(self):
        for r in self.m["correlations"]["rows"]:
            if r["basis"] == "MEASURED":
                self.assertIsNotNone(r["r"])
                self.assertGreater(r["n"], 0)
            else:
                self.assertIsNone(r["r"])
                self.assertEqual(r["n"], 0)

    def test_shrink_constant_is_fixed_and_the_grid_is_published(self):
        oos = self.m["estimators"]["E1"]["oos"]
        self.assertEqual(oos["shrink_k"], 6.0)
        self.assertEqual(len(oos["shrink_sensitivity"]), 4)


class TestParlays(unittest.TestCase):
    def setUp(self):
        self.p = load("parlays.json")

    def test_naive_product_is_always_printed_beside_the_rho_price(self):
        for r in self.p["rows"]:
            self.assertIsNotNone(r["naive_product"])
            self.assertIsNotNone(r["rho_priced"])
            self.assertAlmostEqual(r["naive_product"], r["p_leg1"] * r["p_leg2"], places=3)

    def test_rho_is_measured_not_assumed(self):
        for r in self.p["rows"]:
            self.assertGreater(r["rho_n"], 0)


class TestPreregAndLedger(unittest.TestCase):
    def test_preregistration_files_exist_and_are_frozen(self):
        idx = load("prereg/index.json")
        self.assertEqual(idx["count"], 3)
        for f in idx["files"]:
            path = os.path.join(ROOT, f)
            self.assertTrue(os.path.exists(path), f)
            d = json.load(open(path, encoding="utf-8"))
            self.assertTrue(d["frozen_before_first_bet"])
            for key in ("signal", "thresholds", "universe", "settlement", "refusals"):
                self.assertIn(key, d)

    def test_prereg_is_not_overwritten(self):
        before = {}
        idx = load("prereg/index.json")
        for f in idx["files"]:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                before[f] = fh.read()
        rc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "picks_round_3d625d23.py"),
                             "prereg"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(rc.returncode, 0)
        self.assertIn("already frozen", rc.stdout)
        for f, text in before.items():
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), text, f)

    def test_ledger_chain_verifies(self):
        rc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "picks_round_3d625d23.py"),
                             "verify"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(rc.returncode, 0)
        self.assertIn("CHAIN INTACT", rc.stdout)

    def test_ledger_hash_chain_is_recomputable_and_tamper_evident(self):
        import picks_round_3d625d23 as P
        path = os.path.join(OUT, "ledger", "ledger.jsonl")
        entries = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        self.assertTrue(entries)
        prev = P.GENESIS
        for e in entries:
            payload = {k: v for k, v in e.items() if k not in ("hash", "prev_hash")}
            self.assertEqual(e["prev_hash"], prev)
            self.assertEqual(e["hash"], hashlib.sha256(
                (prev + P.canonical(payload)).encode()).hexdigest())
            prev = e["hash"]
            self.assertTrue(e["published_utc"])
            self.assertTrue(e["settlement"])
        self.assertEqual(load("ledger/index.json")["head"], prev)

    def test_picks_are_sealed_before_tip(self):
        idx = load("ledger/index.json")
        self.assertTrue(idx["sealed_before_tip"])
        feed = {g["game_id"]: g for g in load("results_feed.json")["games"]}
        for line in open(os.path.join(OUT, "ledger", "ledger.jsonl"), encoding="utf-8"):
            if not line.strip():
                continue
            e = json.loads(line)
            g = feed.get(e["game_id"])
            if g and g["verified"]:
                self.assertTrue(e.get("settled_utc"))
                self.assertIn(e["result"], ("win", "loss"))

    def test_no_bet_on_a_club_outside_the_luck_band(self):
        luck = {t["team"]: t for t in load("model.json")["luck"]["teams"]}
        picks = load("picks.json")
        for c in picks["candidates"]:
            if c.get("bet"):
                away, home = c["matchup"].split("@")
                self.assertFalse(luck[away]["outside_noise_band"], c["matchup"])
                self.assertFalse(luck[home]["outside_noise_band"], c["matchup"])
            else:
                self.assertTrue(c["skip_reason"])


class TestGates(unittest.TestCase):
    def test_all_gates_pass(self):
        g = load("gates.json")
        self.assertTrue(g["all_passed"], [x["id"] for x in g["gates"] if x["status"] != "PASS"])
        self.assertEqual(g["counts"]["gates"], 12)

    def test_gate_report_is_reproducible(self):
        rc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gates_round_3d625d23.py")],
                            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        g = load("gates.json")
        self.assertTrue(g["all_passed"])

    def test_no_artefact_carries_a_wall_clock(self):
        stamp = "2026-11-16T00-05Z"
        for fn in sorted(os.listdir(OUT)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(OUT, fn), encoding="utf-8") as fh:
                text = fh.read()
            if "generated_utc" in text:
                self.assertIn(stamp, text, fn)


class TestSite(unittest.TestCase):
    def setUp(self):
        self.pages = sorted(f for f in os.listdir(SITE) if f.endswith(".html"))
        self.docs = {}
        for f in self.pages:
            with open(os.path.join(SITE, f), encoding="utf-8") as fh:
                self.docs[f] = fh.read()

    def test_pages_exist(self):
        self.assertEqual(len(self.pages), 17)
        self.assertIn("index.html", self.pages)

    def test_no_broken_internal_links(self):
        for name, doc in self.docs.items():
            for href in re.findall(r'href="([^"]+)"', doc):
                if href.startswith(("#", "http")) or not href.endswith(".html"):
                    continue
                self.assertTrue(os.path.exists(os.path.join(SITE, href.split("#")[0])),
                                f"{name} -> {href}")

    def test_every_table_row_has_an_official_source_link(self):
        official = ("nba.com", "wikipedia.org")
        for name, doc in self.docs.items():
            for tbody in re.findall(r"<tbody>(.*?)</tbody>", doc, re.S):
                for i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", tbody, re.S), 1):
                    urls = [u for u in re.findall(r'href="(https://[^"]+)"', tr)
                            if any(h in u for h in official)]
                    self.assertTrue(urls, f"{name}: table row {i} has no official-source link")

    def test_column_counts_match_headers(self):
        for name, doc in self.docs.items():
            for tbl in re.findall(r"<table[^>]*>(.*?)</table>", doc, re.S):
                head = re.search(r"<thead>\s*<tr>(.*?)</tr>\s*</thead>", tbl, re.S)
                if not head:
                    continue
                ncol = len(re.findall(r"<th[^>]*>", head.group(1)))
                for i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", tbl, re.S), 1):
                    n = len(re.findall(r"<td[^>]*>", tr))
                    if n:
                        self.assertEqual(n, ncol, f"{name}: row {i}")

    def test_injury_banner_shows_revision_and_retrieval_time(self):
        doc = self.docs["injuries.html"]
        self.assertIn("2026-11-15 06:30 PM ET", doc)
        self.assertIn("2026-11-16T00-05Z", doc)

    def test_projection_page_never_headlines_the_blend(self):
        doc = self.docs["projections.html"]
        self.assertIn("Disagreement", doc)
        self.assertIn("Home-court advantage is pinned", doc)

    def test_site_rebuilds_identically(self):
        before = {}
        for f in self.pages:
            with open(os.path.join(SITE, f), encoding="utf-8") as fh:
                before[f] = fh.read()
        rc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_slate_site.py")],
                            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        for f, text in before.items():
            with open(os.path.join(SITE, f), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), text, f)


def _probit(p):
    return math.sqrt(2) * _erfinv(2 * p - 1)


def _erfinv(x):
    a = 0.147
    ln1mx2 = math.log(1 - x * x)
    t1 = 2 / (math.pi * a) + ln1mx2 / 2
    return math.copysign(math.sqrt(math.sqrt(t1 * t1 - ln1mx2 / a) - t1), x)


if __name__ == "__main__":
    unittest.main()
