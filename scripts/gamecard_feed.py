#!/usr/bin/env python3
"""Parse the official NBA game-card feed embedded in a captured games page.

The official scoreboard page (https://www.nba.com/games?date=YYYY-MM-DD) is a Next.js
app whose server-rendered HTML carries a __NEXT_DATA__ JSON blob. Inside it,
props.pageProps.gameCardFeed.modules[*].cards[*].cardData holds one object per game
with the official state (gameStatusText / gameState), the team tricodes, the printed
score and the period-by-period scores.

This module is deliberately strict (same rule as the rest of the results pipeline):
  * only a card whose status starts with "Final" is eligible;
  * a card is accepted only when its period scores SUM to its printed final for both
    sides — a card that fails the sum check goes to `rejected` with the reason and is
    never repaired or guessed;
  * missing scores/periods reject the card too.

Import-only (no writes, no wall clock), so CI can call it offline. The offline
fixture tests pin the parse against the committed 2026-11-16T00-57Z capture.
"""

from __future__ import annotations

import json
import re

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def parse_games_page(html: str) -> list:
    """Return the list of cardData dicts from one captured games page (may be empty)."""
    m = NEXT_DATA_RE.search(html)
    if not m:
        return []
    try:
        d = json.loads(m.group(1))
    except ValueError:
        return []
    out = []
    try:
        for mod in d["props"]["pageProps"]["gameCardFeed"]["modules"]:
            for card in mod.get("cards", []):
                if isinstance(card, dict) and isinstance(card.get("cardData"), dict):
                    out.append(card["cardData"])
    except (KeyError, TypeError):
        return []
    return out


def _periods(team) -> list:
    return [p.get("score") for p in (team.get("periods") or [])]


def finished_rows(cards: list):
    """Split parsed cards into (rows, rejected) for finished games only.

    Rows match the results-feed ingest schema: date, game_id, away, home, away_pts,
    home_pts, away_q, home_q, state, ot, verified_from.
    """
    rows, rejected = [], []
    for g in cards:
        status = str(g.get("gameStatusText") or "").strip()
        if not status.startswith("Final"):
            continue
        gid = g.get("gameId")
        at, ht = g.get("awayTeam") or {}, g.get("homeTeam") or {}
        aq, hq = _periods(at), _periods(ht)
        ap, hp = at.get("score"), ht.get("score")
        if ap is None or hp is None or not aq or not hq:
            rejected.append({"game_id": gid, "state": status,
                             "reason": "finished card without score or period scores"})
            continue
        if any(q is None for q in aq + hq):
            rejected.append({"game_id": gid, "state": status,
                             "reason": "finished card with a blank period score"})
            continue
        if sum(aq) != ap or sum(hq) != hp:
            rejected.append({
                "game_id": gid, "state": status,
                "reason": f"period sums {sum(aq)}/{sum(hq)} do not equal "
                          f"printed finals {ap}/{hp}"})
            continue
        tip = str(g.get("gameTimeEastern") or "")
        rows.append({
            "date": tip[:10] if len(tip) >= 10 else "",
            "game_id": gid,
            "away": at.get("teamTricode"),
            "home": ht.get("teamTricode"),
            "away_pts": ap,
            "home_pts": hp,
            "away_q": aq,
            "home_q": hq,
            "state": status,
            "ot": 1 if "OT" in status else 0,
            "verified_from": g.get("shareUrl") or "",
            "raw_file": "game-card feed (__NEXT_DATA__)",
        })
    return rows, rejected
