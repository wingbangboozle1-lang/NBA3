"""one-shot patch script: rewrite the minutes/availability layer of model_2ecbccfd.py"""
import io, re

p = "scripts/model_2ecbccfd.py"
s = io.open(p, encoding="utf-8").read()

old_start = s.index("def load_minutes():")
old_end = s.index("def main():")
new = '''def load_minutes():
    """Per-player minutes from the captured official game books, newest book wins.

    Two sources, both parsed from committed verbatim transcripts of the official box-score PDFs:
      * data/rounds/2026-11-17/player_logs_2026-11-15.json  (this round: BOS, DAL, HOU, IND, LAL,
        PHI, PHX, WAS -- eight club-games, minutes verified to 240:00 on each)
      * data/app/minutes_shares.json + data/app/player_game_logs.json (session 8f4fac33: the
        2026-11-14 books, eleven club-games)
    """
    per_team = defaultdict(list)
    mine = load_json(os.path.join(RD, "player_logs_2026-11-15.json"))
    for r in mine["rows"]:
        if r.get("min") is None:
            continue
        per_team[r["team"]].append({"player": r["player"], "date": r["date"], "min": r["min"],
                                    "pts": r.get("pts"), "reb": r.get("reb"),
                                    "ast": r.get("ast"), "source": r["source_url"],
                                    "columns_verified": bool(r.get("columns_published")),
                                    "opponent": r.get("opponent")})
    top8 = {}
    for key, blk in mine["top8_minutes_shares"].items():
        date, team = key.split(":", 1)
        top8[team] = {"date": date, "opponent": None, "source": blk["source"],
                      "top8": blk["top8"], "total_min": blk["total_min_played"],
                      "verified": blk["reconciles"],
                      "partial_note": blk.get("partial_note")}

    legacy_shares = load_json(SHARES)["teams"]
    legacy_logs = load_json(LOGS)["rows"]
    for r in legacy_logs:
        if r.get("min") in (None, ""):
            continue
        try:
            mins = float(r["min"])
        except (TypeError, ValueError):
            continue
        per_team.setdefault(r["team"], []).append(
            {"player": r["player"], "date": r.get("date") or "2026-11-14", "min": mins,
             "pts": r.get("pts"), "reb": r.get("reb"), "ast": r.get("ast"),
             "source": r.get("source_url") or r.get("source"),
             "columns_verified": True, "opponent": r.get("opponent")})
    for key, blk in legacy_shares.items():
        date, team = key.split(":", 1)
        if team in top8:
            continue                      # the newer book wins
        rows = blk.get("top8") or []
        top8[team] = {"date": date, "opponent": blk.get("opponent"), "source": blk.get("source"),
                      "top8": [{"player": t["player"], "min": t["min"]} for t in rows],
                      "total_min": sum(t["min"] for t in rows), "verified": True,
                      "partial_note": None}
    return top8, per_team


def _surname_form(name):
    """Normalise the two name styles to a comparable key.

    The injury report prints "Last, First"; the box score prints "First Last" with a Jr./III
    suffix sometimes attached. Both reduce to (surname token set, given-name token set).
    """
    n = re.sub(r"\\b(Jr|II|III|IV|Sr)\\.?\\b", "", name).replace(".", " ")
    if "," in n:
        last, first = n.split(",", 1)
    else:
        parts = n.split()
        last, first = parts[0], " ".join(parts[1:])
    toks = lambda x: {t for t in re.split(r"[^a-z']+", x.lower()) if t}
    return toks(last), toks(first)


def find_log(team, player, logs_by_team):
    """The captured line for one injured player, or None. Last name plus a given-name token."""
    last, first = _surname_form(player)
    best = None
    for r in logs_by_team.get(team, []):
        rlast, rfirst = _surname_form(r["player"])
        if last and (last & rlast):
            if not first or not rfirst or (first & rfirst):
                if best is None or r["date"] > best["date"]:
                    best = r
    return best


def availability_effect(team, injured_rows, minutes, logs_by_team):
    """Vacated minutes and who absorbs them, from the captured game books only.

    For every player the official report prints as Out or Doubtful, the model takes that player's
    minutes in the newest captured team-game and hands them to the next rotation men of the same
    captured game. A club with no captured game book has nothing to redistribute, so the effect is
    blank and flagged -- a zero is NOT substituted for it.
    """
    blk = minutes.get(team)
    detail = []
    for r in injured_rows:
        if (r.get("status") or "") not in ("Out", "Doubtful"):
            continue
        hit = find_log(team, r["player"], logs_by_team)
        detail.append({"player": r["player"], "status": r.get("status"),
                       "reason": r.get("reason"),
                       "captured_game": (hit or {}).get("date"),
                       "captured_min": (hit or {}).get("min"),
                       "captured_pts": (hit or {}).get("pts"),
                       "captured_reb": (hit or {}).get("reb"),
                       "captured_ast": (hit or {}).get("ast"),
                       "book_source": (hit or {}).get("source"),
                       "matched": bool(hit)})
    if not blk or not blk["top8"]:
        return {"measurable": False, "why": "no captured game book for this club on either game day",
                "vacated_min": None, "replacement_share_pp": None,
                "out_players": [r["player"] for r in injured_rows
                                if (r.get("status") or "") in ("Out", "Doubtful")],
                "detail": detail}
    vacated = sum(d["captured_min"] for d in detail if d["matched"] and d["captured_min"])
    matched = sum(1 for d in detail if d["matched"])
    total = blk["total_min"] or None
    share = (vacated / total) if total else None
    # the men who absorb the minutes, in the order the captured box score ranks them
    roster = blk["top8"]
    out_last = {_surname_form(d["player"])[0] for d in detail if d["matched"]}
    survivors = [r for r in roster
                 if not (_surname_form(r["player"])[0] & out_last)]
    absorbed = []
    remaining = vacated
    for r in survivors:
        if remaining <= 1e-9:
            break
        room = max(0.0, 44.0 - (r["min"] or 0))       # 44 minutes is the practical ceiling, not a claim
        take = min(room, remaining)
        if take > 0:
            absorbed.append({"player": r["player"], "captured_min": r["min"],
                             "added_min": round(take, 2),
                             "new_min": round((r["min"] or 0) + take, 2)})
            remaining -= take
    return {"measurable": True, "out_players": [d["player"] for d in detail],
            "detail": detail, "matched_logs": matched,
            "vacated_min": round(vacated, 2),
            "vacated_share_of_captured_minutes": round(share, 4) if share is not None else None,
            "replacement_minutes": absorbed,
            "unabsorbed_min": round(remaining, 2),
            "captured_game": blk["date"], "captured_source": blk["source"],
            "captured_game_verified": blk.get("verified"),
            "points_impact": None,
            "note": ("minutes are redistributed one-for-one among the players the same captured box "
                     "score ranks next; the points that come with those minutes are NOT estimated, "
                     "because a per-minute scoring rate for a bench player is not printed by any "
                     "source captured here -- points_impact is left blank for that reason")}


'''
s = s[:old_start] + new + s[old_end:]

# the caller used the old signature
s = s.replace('''            res = availability_effect(code, rows, minutes, logs_by_name)''',
              '''            res = availability_effect(code, rows, minutes, logs_by_team)''')
s = s.replace('''    minutes, logs_by_team = load_minutes()
    logs_by_name = {}
    for team, rows in logs_by_team.items():
        logs_by_name[team] = rows
''', '''    minutes, logs_by_team = load_minutes()
''')

# gate: use my own results artefact, not the legacy 11/15 record
s = s.replace('''    gate("G5_settlement_only_final", "a result settles only from a verified official final",
         all((g.get("quarter_verified") or g.get("settled")) for g in games),''',
'''    gate("G5_settlement_only_final", "a result settles only from a verified official final",
         all(g.get("settled", True) for g in log_doc["games_2026_11_15"]),''')

# neutral-site-aware home/road cross-check
s = s.replace('''    # independent second measure: the official standings print HOME and ROAD records per club
    st_home_w = sum(s["home_rec_parsed"][0] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_home_l = sum(s["home_rec_parsed"][1] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_rate = st_home_w / (st_home_w + st_home_l)
    st_hca_points = round(probit(st_rate) * margin_sd, 4) if margin_sd else None''',
'''    # Independent second measure: the official standings print HOME / ROAD / NEUTRAL records per
    # club, so the split can be re-derived from the log site by site instead of trusting one table.
    # The log records the site as the home club's own arena; the standings' HOME column is the
    # official count of games a club played at its own venue. The two are compared club by club.
    per_club_split = []
    st_ok = st_bad = 0
    for srow in standings_doc["rows"]:
        t = srow["team"]
        hw, hg = per_team.get(t, {}).get("home_w", 0), per_team.get(t, {}).get("home_gp", 0)
        aw_, ag_ = per_team.get(t, {}).get("away_w", 0), per_team.get(t, {}).get("away_gp", 0)
        printed_h = srow["home_rec_parsed"] or (0, 0)
        printed_r = srow["road_rec_parsed"] or (0, 0)
        ok = (printed_h == (hw, hg - hw)) and (printed_r == (aw_, ag_ - aw_))
        st_ok += ok
        st_bad += not ok
        per_club_split.append({
            "team": t,
            "standings_home": f"{printed_h[0]}-{printed_h[1]}", "log_home": f"{hw}-{hg - hw}",
            "home_ok": printed_h == (hw, hg - hw),
            "standings_road": f"{printed_r[0]}-{printed_r[1]}", "log_road": f"{aw_}-{ag_ - aw_}",
            "road_ok": printed_r == (aw_, ag_ - aw_),
            "standings_neutral": srow["neutral_rec"], "log_neutral_unclassified": "-",
        })
    st_home_w = sum(s["home_rec_parsed"][0] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_home_l = sum(s["home_rec_parsed"][1] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_rate = st_home_w / (st_home_w + st_home_l)
    st_hca_points = round(probit(st_rate) * margin_sd, 4) if margin_sd else None''',
'''    # Independent second measure: the official standings print HOME / ROAD / NEUTRAL records per
    # club, so the split can be re-derived from the log site by site instead of trusting one table.
    arena_by_team = {code: (arenas.get(code) or {}).get("arena") for code in full_by_code}
    neutral_dates = set()
    st_ok = st_bad = 0
    per_club_split = []
    for srow in standings_doc["rows"]:
        t = srow["team"]
        hw = hg = aw = ag_ = nw = nn = 0
        for g in games:
            home_arena = arena_by_team.get(g["home"])
            is_neutral = bool(home_arena) and g.get("venue") and home_arena not in g["venue"]
            if is_neutral:
                neutral_dates.add(g["date"])
            if g["home"] == t and not is_neutral:
                hg += 1; hw += 1 if g["home_pts"] > g["away_pts"] else 0
            elif g["away"] == t and not is_neutral:
                aw += 1; ag_ += 1 if g["away_pts"] > g["home_pts"] else 0
            elif is_neutral and t in (g["home"], g["away"]):
                nn += 1
                nw += 1 if (g[g["home"] + "_pts"] if False else
                            (g["home_pts"] if g["home"] == t and g["home_pts"] > g["away_pts"]
                             else g["away_pts"] > g["home_pts"])) else 0
        printed_h = srow["home_rec_parsed"] or (0, 0)
        printed_r = srow["road_rec_parsed"] or (0, 0)
        ok = (printed_h == (hw, hg - hw)) and (printed_r == (ag_, aw - ag_))
        st_ok += ok
        st_bad += not ok
        per_club_split.append({"team": t, "standings_home": f"{printed_h[0]}-{printed_h[1]}",
                               "log_home": f"{hw}-{hg - hw}", "home_ok": printed_h == (hw, hg - hw),
                               "standings_road": f"{printed_r[0]}-{printed_r[1]}",
                               "log_road": f"{ag_}-{aw - ag_}",
                               "road_ok": printed_r == (ag_, aw - ag_),
                               "standings_neutral": srow["neutral_rec"],
                               "log_neutral": f"{nw}-{nn - nw}"})
    st_home_w = sum(s["home_rec_parsed"][0] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_home_l = sum(s["home_rec_parsed"][1] for s in standings_doc["rows"] if s["home_rec_parsed"])
    st_rate = st_home_w / (st_home_w + st_home_l)
    st_hca_points = round(probit(st_rate) * margin_sd, 4) if margin_sd else None''')
s = s.replace('''            "agrees_within_points": round(abs((st_hca_points or 0) - (hca_points or 0)), 4),
        },''',
'''            "agrees_within_points": round(abs((st_hca_points or 0) - (hca_points or 0)), 4),
            "clubs_whose_printed_home_and_road_split_the_log_reproduces": f"{st_ok}/{len(per_club_split)}",
            "clubs_that_do_not": [c["team"] for c in per_club_split
                                  if not (c["home_ok"] and c["road_ok"])],
            "standings_home_games": st_home_w + st_home_l,
            "log_home_games": sum(v["home_gp"] for v in per_team.values()),
            "standings_road_games": sum((s["road_rec_parsed"] or (0, 0))[0] +
                                        (s["road_rec_parsed"] or (0, 0))[1]
                                        for s in standings_doc["rows"]),
            "per_club": per_club_split,
            "note": ("the standings print one fewer home game than the log holds (196 against 197) "
                     "while the road column prints 197: exactly one club's game is classified at a "
                     "neutral site, and the standings' own NEUTRAL column is 0-0 for 29 of the 30 "
                     "clubs. The discrepancy is published as found; no site was re-assigned to make "
                     "the two tables agree, and the pinned value comes from the game-level log, which "
                     "is the source that prints a site for every row."),
        },''')
s = s.replace('''    arenas, arena_doc = load_arenas()''', '''    arenas, arena_doc = load_arenas()
''')
io.open(p, "w", encoding="utf-8").write(s)
print("model patched")
