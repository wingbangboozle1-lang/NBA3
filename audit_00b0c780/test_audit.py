"""Offline tests for the 00b0c780 audit tree. No network: every check reads committed files.

Run:  python3 -m unittest discover -s audit_00b0c780 -p 'test_*.py'
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest
from urllib.parse import urlparse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
PAGES = HERE / "pages"
OFFICIAL = ("nba.com", "statsdmz.nba.com", "ak-static.cms.nba.com", "official.nba.com")


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _official(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and any(u.hostname == h or u.hostname.endswith("." + h) for h in OFFICIAL)


def _m(g: dict) -> str:
    return f"{g['away']} @ {g['home']}"


def _json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class FinalsTests(unittest.TestCase):
    def setUp(self):
        self.fin = _json("finals_1115.json")

    def test_nine_games_on_the_2026_11_15_slate(self):
        self.assertEqual(self.fin["counts"]["games"], 9)
        self.assertEqual(sorted(g["game_id"] for g in self.fin["games"]),
                         [f"00226002{n}" for n in range(36, 45)])

    def test_schedule_final_equals_book_final_for_every_game(self):
        for g in self.fin["games"]:
            self.assertTrue(all(g["checks"]["schedule_equals_book_final"].values()), _m(g))

    def test_quarter_sums_recomputed(self):
        for g in self.fin["games"]:
            c = g["checks"]
            if "period_table_vs_summary_conflict" in c:
                t = c["period_table_vs_summary_conflict"]
                self.assertTrue(t["summary_sum_equals_final"], _m(g))
                self.assertFalse(t["table_sum_equals_final"], _m(g))
                self.assertEqual(t["conflicting_periods"], [3])
            else:
                self.assertTrue(all(c["book_sum_equals_printed_final"].values()), _m(g))

    def test_atl_mil_is_the_only_quarter_conflict_and_is_flagged(self):
        conflicts = [g for g in self.fin["games"] if "CONFLICTING" in g["status"]]
        self.assertEqual([_m(g) for g in conflicts], ["ATL @ MIL"])

    def test_ot_game_recorded(self):
        nyk = next(g for g in self.fin["games"] if g["away"] == "NYK")
        self.assertTrue(nyk["checks"]["ot"])
        self.assertEqual(nyk["state_on_schedule"], "Final/OT")
        self.assertEqual(nyk["away_periods_book"][4], 17)
        self.assertEqual(nyk["home_periods_book"][4], 13)

    def test_nothing_on_main_feed_and_pr98_agrees_for_four(self):
        self.assertEqual(self.fin["counts"]["on_main_results_feed"], 0)
        self.assertEqual(self.fin["counts"]["on_pr98_branch"], 4)
        for g in self.fin["games"]:
            if g["on_pr98_branch"]:
                self.assertTrue(g["checks"]["main_or_pr98"]["pr98_periods_equal_book"], _m(g))

    def test_every_game_row_has_an_official_link(self):
        for g in self.fin["games"]:
            self.assertTrue(any(_official(s["url"]) for s in g["sources"]), _m(g))


class InjuryIndexTests(unittest.TestCase):
    def setUp(self):
        self.inj = _json("injury_index_2026-11-16.json")

    def test_listing_is_12am_to_930am_in_fifteen_minute_steps(self):
        reps = self.inj["reports"]
        self.assertEqual(reps[0]["revision_et"], "2026-11-16 12:00 AM ET")
        self.assertEqual(reps[-1]["revision_et"], "2026-11-16 9:30 AM ET")
        self.assertEqual(len(reps), 39)
        self.assertEqual(self.inj["reports_listed_for_2026_11_16"], len(reps))

    def test_every_pdf_url_is_on_the_official_cdn_and_not_fetched(self):
        for r in self.inj["reports"]:
            self.assertTrue(r["pdf_url"].startswith("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-16_"))
            self.assertFalse(r["pdf_fetched_in_this_session"])

    def test_banner_on_main_is_older_than_newest_listed(self):
        self.assertEqual(self.inj["published_on_main"]["banner_revision_time"], "2026-11-15 06:15 AM ET")
        self.assertEqual(len(set(self.inj["published_on_main"]["banner_retrieval_times"])), 2)


class RequirementTests(unittest.TestCase):
    def setUp(self):
        self.req = _json("requirements.json")
        self.statuses = set(self.req["statuses"])

    def test_thirty_items_with_unique_ids_and_known_statuses(self):
        ids = [i["id"] for i in self.req["items"]]
        self.assertEqual(len(ids), 30)
        self.assertEqual(len(set(ids)), 30)
        for it in self.req["items"]:
            self.assertIn(it["status"], self.statuses, it["id"])

    def test_every_evidence_path_exists_and_contains_its_literal_text(self):
        missing, absent = [], []
        for it in self.req["items"]:
            for ev in it["evidence"]:
                p = ROOT / ev["path"]
                if not p.exists():
                    missing.append((it["id"], ev["path"]))
                    continue
                if ev["contains"] is not None:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    if ev["contains"] not in text:
                        absent.append((it["id"], ev["path"], ev["contains"]))
        self.assertEqual(missing, [], "evidence paths that do not exist")
        self.assertEqual(absent, [], "evidence strings not found in their files")

    def test_official_links_are_official(self):
        for it in self.req["items"]:
            for url in it.get("official", []):
                self.assertTrue(_official(url), (it["id"], url))

    def test_every_non_met_item_names_a_gap_and_a_next_step(self):
        for it in self.req["items"]:
            if it["status"] != "Met":
                self.assertTrue(it["gap"] and it["gap"] != "None found at code level.", it["id"])
                self.assertTrue(it["next"], it["id"])


class FlagTests(unittest.TestCase):
    def setUp(self):
        self.flags = _json("flags.json")["items"]

    def test_ids_unique_and_each_has_owner_and_source(self):
        ids = [f["id"] for f in self.flags]
        self.assertEqual(len(ids), len(set(ids)))
        for f in self.flags:
            self.assertTrue(f["owner"], f["id"])
            self.assertTrue(f["sources"], f["id"])
            self.assertIn(f["severity"], ("high", "medium", "low"), f["id"])

    def test_every_flag_source_is_an_https_link(self):
        for f in self.flags:
            for u in f["sources"]:
                self.assertTrue(u.startswith("https://"), (f["id"], u))

    def test_key_irregularities_are_present(self):
        ids = {f["id"] for f in self.flags}
        for required in ("K-01", "K-02", "K-03", "K-04", "K-05", "K-06", "K-07", "K-08"):
            self.assertIn(required, ids)


class DeterminismTests(unittest.TestCase):
    def test_make_data_reproduces_committed_data(self):
        mod = _load_module("make_data", HERE / "make_data.py")
        before = {p.name: p.read_bytes() for p in DATA.glob("*.json")}
        mod.main()
        mod.main_extra()
        after = {p.name: p.read_bytes() for p in DATA.glob("*.json")}
        self.assertEqual(before, after, "make_data.py output drifted from the committed data")

    def test_build_reproduces_committed_pages(self):
        mod = _load_module("build", HERE / "build.py")
        before = {p.name: p.read_bytes() for p in PAGES.glob("*.html")}
        mod.main()
        after = {p.name: p.read_bytes() for p in PAGES.glob("*.html")}
        self.assertEqual(before, after, "build.py output drifted from the committed pages")


class PageLinkTests(unittest.TestCase):
    def test_internal_links_resolve(self):
        import re
        names = {p.name for p in PAGES.glob("*.html")}
        for p in PAGES.glob("*.html"):
            for href in re.findall(r'href="([^"#]+)"', p.read_text(encoding="utf-8")):
                if href.startswith(("http://", "https://")):
                    continue
                self.assertIn(href, names, f"{p.name} links to {href}")


if __name__ == "__main__":
    unittest.main()
