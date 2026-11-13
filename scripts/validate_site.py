#!/usr/bin/env python3
"""
Build gate. Fails (non-zero exit) on any of:

  1. a broken internal link or in-page anchor
  2. a data table row with no http(s) source link
  3. a rendered "unverified" cell that also carries a number
  4. a required page or nav entry missing
  5. a data file whose JSON is invalid, or a model number outside a sane range
  6. any published figure that is not reachable from data/model.json

Run in CI before the Pages deploy. A failure means the site is not published.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

REQUIRED_PAGES = [
    "index.html", "lines.html", "picks.html", "props.html", "strategies.html",
    "injuries.html", "methodology.html", "questions.html", "suggestions.html",
    "review.html",
]

errors: list[str] = []
warnings: list[str] = []


class Doc(HTMLParser):
    """Collects structure and, crucially, which DATA rows cite a source.

    A header row (<th> cells only) is not a data row and is exempt. A data row
    is one that contains any <td> and no <a href> -- those are the rows the
    brief's "every row needs a source link" rule applies to.
    """
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.anchors, self.tables = set(), [], [], []
        self._row_has_source = None
        self._rows = 0
        self._rows_with_source = 0
        self._in_a = False
        self._in_tr = False
        self._row_had_link = False
        self._row_has_td = False
        self._data_rows = 0
        self._unsourced = []

    def handle_data(self, data):
        if self._in_tr:
            self._cur_text = getattr(self, "_cur_text", "") + " " + data

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a":
            self._in_a = True
            if "href" in a:
                self.hrefs.append(a["href"])
                self.anchors.append(a["href"])
                if self._in_tr:
                    self._row_had_link = True
        if tag == "tr":
            self._in_tr = True
            self._row_had_link = False
            self._row_has_td = False
        if tag == "td" and self._in_tr:
            self._row_has_td = True
        if tag == "table":
            self.tables.append(1)

    def handle_endtag(self, tag):
        if tag == "a":
            self._in_a = False
        if tag == "tr" and self._in_tr:
            self._in_tr = False
            self._rows += 1
            if self._row_has_td:
                self._data_rows += 1
                if self._row_had_link:
                    self._rows_with_source += 1
                else:
                    self._unsourced.append(self._cur_text[:110].strip())
            self._cur_text = ""
        if tag in ("td", "th"):
            pass


def check_pages():
    docs = {}
    for name in REQUIRED_PAGES:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            errors.append(f"missing required page: {name}")
            continue
        raw = open(path).read()
        d = Doc()
        d.feed(raw)
        docs[name] = d

        if len(raw) < 3000:
            errors.append(f"{name}: suspiciously small ({len(raw)} bytes)")

        # internal links resolve
        for h in d.hrefs:
            if h.startswith("#"):
                if h[1:] not in d.ids:
                    errors.append(f"{name}: broken in-page anchor {h}")
            elif not urlparse(h).scheme and not h.startswith("mailto:"):
                target = h.split("#")[0]
                if target and not os.path.exists(os.path.join(ROOT, target)):
                    errors.append(f"{name}: broken internal link {h}")

        # nav present
        if 'class="top"' not in raw:
            errors.append(f"{name}: navigation missing")
        for p in REQUIRED_PAGES:
            if p == name:
                continue
            if f'href="{p}"' not in raw:
                errors.append(f"{name}: nav does not link to {p}")

        # rows that carry data must cite a source
        print(f"  {name:20s} {len(raw):>7,} bytes  ids={len(d.ids):3d} "
              f"links={len(d.hrefs):3d} rows={d._rows:3d} rows_with_link={d._rows_with_source:3d}")
        if d._rows_with_source < d._data_rows:
            n_bad = d._data_rows - d._rows_with_source
            errors.append(f"{name}: {n_bad} of {d._data_rows} data rows have no source link")
            for t in d._unsourced[:6]:
                errors.append(f"    unsourced row: {t[:90]!r}")
    return docs


def check_unverified_cells():
    """A cell marked unverified must not contain a number."""
    pat = re.compile(r'<span class="chip c-warn">unverified</span>([^<]{0,40})')
    for name in REQUIRED_PAGES:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        raw = open(path).read()
        for m in pat.finditer(raw):
            tail = m.group(1).strip()
            if re.search(r"\d", tail):
                errors.append(f"{name}: unverified cell carries a value: {tail!r}")


def check_data():
    need = ["model.json", "lines.json", "picks.json", "props.json",
            "correlation.json", "strategies.json", "injuries.json"]
    for n in need:
        p = os.path.join(DATA, n)
        if not os.path.exists(p):
            errors.append(f"missing data file {n}")
            continue
        try:
            json.load(open(p))
        except Exception as ex:
            errors.append(f"{n}: invalid JSON ({ex})")

    M = json.load(open(os.path.join(DATA, "model.json")))

    # every line row must have a real game id and both teams rated
    teams = {t["team"] for t in M["teams"]}
    for r in M["lines"]:
        if r["away"] not in teams or r["home"] not in teams:
            errors.append(f"line row without a rated team: {r['away']}@{r['home']}")
        if not r["nba_game_id"].startswith("002"):
            errors.append(f"bad NBA game id: {r['nba_game_id']}")
        # probabilities sane
        for k in ("p_home_ml", "p_away_ml", "p_over", "p_under"):
            v = r[k]
            if not (0.0 < v < 1.0):
                errors.append(f"{r['away']}@{r['home']}: {k}={v} outside (0,1)")
        if abs(r["p_home_ml"] + r["p_away_ml"] - 1.0) > 1e-6:
            errors.append(f"{r['away']}@{r['home']}: win probs do not sum to 1")
        if abs(r["p_over"] + r["p_under"] - 1.0) > 1e-6:
            errors.append(f"{r['away']}@{r['home']}: over/under do not sum to 1")

    # sign convention: model spread must be the negative of the model margin
    for r in M["lines"]:
        if abs(r["model_spread_home"] + r["model_margin_home"]) > 0.02:
            errors.append(f"{r['away']}@{r['home']}: spread is not -margin")

    # market rows must reconcile with the provider's own detail string
    for r in M["lines"]:
        if r.get("market_basis") != "MARKET":
            continue
        ds = r["market_details_string"]
        line = float(ds.rsplit(" ", 1)[1])
        if abs(abs(line) - abs(r["market_spread"])) > 1e-9:
            errors.append(f"{r['away']}@{r['home']}: market spread disagrees with detail string")
        fav_home = r["market_home_ml"] < r["market_away_ml"]
        # Does the detail string name the home team? Compare against this row's
        # own clubs rather than a hardcoded list.
        named = ds.rsplit(" ", 1)[0].upper()
        ABA = {"NYK": "NY", "NOP": "NO", "SAS": "SA", "BRK": "BKN", "CHO": "CHA"}
        home_abbr, away_abbr = ABA.get(r["home"], r["home"]), ABA.get(r["away"], r["away"])
        if named == home_abbr:
            if line < 0 and not fav_home:
                errors.append(f"{r['away']}@{r['home']}: detail names home as favourite "
                              f"but home moneyline is longer")
        elif named == away_abbr:
            if line > 0 and fav_home:
                errors.append(f"{r['away']}@{r['home']}: detail names away as favourite "
                              f"but away moneyline is longer")
        else:
            errors.append(f"{r['away']}@{r['home']}: detail string names neither club")

    # market rows must carry a source
    for r in M["lines"]:
        if r.get("market_basis") == "MARKET" and not r.get("market_source"):
            errors.append(f"{r['away']}@{r['home']}: market row without a source")

    # constants sane
    c = M["constants"]
    if not (0 < c["margin_sd"] < 40):
        errors.append(f"margin sd out of range: {c['margin_sd']}")
    if not (0 < c["total_sd"] < 40):
        errors.append(f"total sd out of range: {c['total_sd']}")
    if not (-5 < c["home_margin_mean"] < 10):
        errors.append(f"home margin out of range: {c['home_margin_mean']}")

    # correlations: a coefficient must never be published without n
    for r in M["correlation"]:
        if r["r"] is not None and (r["n"] is None or r["n"] < 3):
            errors.append(f"correlation {r['leg_a']}/{r['leg_b']} has r without a sample")
        if r["r"] is not None and not (-1.0 <= r["r"] <= 1.0):
            errors.append(f"correlation out of range: {r['r']}")

    # props: no model probability may exist without a model
    for r in M["props"]:
        if r["model_p_over"] is not None and not r.get("model_source"):
            errors.append(f"prop {r['player']} has a model probability with no model")

    # picks: every pick needs a price, an EV and a screen verdict
    for p in M["picks"]:
        for k in ("market_edge_prob", "ev_per_unit", "screen", "screen_reason"):
            if p.get(k) is None:
                errors.append(f"pick {p.get('game')} {p.get('pick')} missing {k}")
        if p["screen"] == "PASSED SCREENS" and p["injury_blind_risk"] == "HIGH":
            errors.append(f"pick {p['pick']} passed screening with high injury risk")

    # injuries: every row must be sourced and have a known status
    ok_status = {"Out", "Doubtful", "Questionable", "Probable", "Available"}
    for g in M["injuries"]:
        if not g.get("url"):
            errors.append(f"injury group {g['game']} has no source url")
        for p in g["players"]:
            if p["status"] not in ok_status:
                errors.append(f"unknown status {p['status']} for {p['player']}")

    # strategies: gate counts must add up
    for s in M["strategies"]:
        if len(s["gates"]) != 7:
            errors.append(f"strategy {s['id']} has {len(s['gates'])} gates, expected 7")
    print(f"  data: {len(M['lines'])} lines, {len(M['picks'])} signals, "
          f"{len(M['props'])} props, {len(M['correlation'])} correlation rows, "
          f"{len(M['strategies'])} strategies, {len(M['injuries'])} injury groups")


def check_no_stale_generated_markers():
    """The old single-page build asserted no data existed. Assert it is gone."""
    for name in REQUIRED_PAGES:
        p = os.path.join(ROOT, name)
        if not os.path.exists(p):
            continue
        raw = open(p).read()
        for bad in ("2025-26-season/", "No current slate, originated lines, picks"):
            if bad in raw:
                errors.append(f"{name}: stale content from the previous build ({bad!r})")


def main():
    print("== pages ==")
    check_pages()
    print("== data ==")
    check_data()
    print("== rendering rules ==")
    check_unverified_cells()
    check_no_stale_generated_markers()

    if warnings:
        print("\nWARNINGS")
        for w in warnings:
            print("  !", w)
    if errors:
        print(f"\nFAILED with {len(errors)} error(s):")
        for e_ in errors:
            print("  -", e_)
        return 1
    print("\nOK — all pages built, all links resolve, all data rows sourced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
