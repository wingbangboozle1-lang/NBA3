"""Parse the archived official injury-report text into rows, and diff two reports.

The NBA injury PDF is a continuation table: the game block runs down the page
and the Team cell is only printed when it changes.  Reading it naively assigns
rows to the wrong team the moment a block crosses a page break.  The parser
below carries the last seen (game, team) FORWARD inside a fragment and RESETS
at every fragment boundary, which is the only safe rule: a fragment boundary in
the PDF is exactly where the table header repeats, and the header repeating is
the league telling you that the context did not carry over.

Anything the parser cannot establish is left as None and reported.  Nothing is
filled in from a roster.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
NOT_SUBMITTED = "NOT YET SUBMITTED"

_ROW = re.compile(r"^\|(.*)\|\s*$")


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(cells) -> bool:
    return all(set(c) <= set("-: ") and c for c in cells) or all(c in ("", "---") for c in cells)


def parse_fragment(fragment: str, carry_team: Optional[str] = None):
    """Parse one PDF fragment into raw rows.

    Returns (rows, notes).  Each row is a dict with the columns the PDF prints
    plus ``team_carried`` telling you whether the Team cell was printed on that
    row or inherited from the row above inside the same fragment.
    """
    rows, notes = [], []
    team = carry_team
    game = None
    tip = None
    game_date = None

    for line in fragment.splitlines():
        line = line.strip()
        if not _ROW.match(line):
            continue
        cells = _cells(line)
        if not cells or _is_separator(cells):
            continue
        # normalise ragged rows: the continuation fragments print 6-8 cells
        joined = " | ".join(cells)
        if joined.startswith("Game Date") or "Player Name" in joined:
            continue

        # detect NOT YET SUBMITTED explicitly, it is a real published state
        if any(c.upper() == NOT_SUBMITTED for c in cells):
            # game date / time / matchup / team
            vals = [c for c in cells]
            gd = vals[0] if vals and re.match(r"\d{2}/\d{2}/\d{4}", vals[0]) else game_date
            gt = vals[1] if len(vals) > 1 and re.match(r"\d{2}:\d{2}", vals[1]) else tip
            mu = next((c for c in vals if "@" in c and len(c) <= 12), game)
            tm = next((c for c in vals if c not in (gd, gt, mu, "", NOT_SUBMITTED)
                       and not re.match(r"^\d", c)), None)
            rows.append({
                "game_date": gd, "game_time_et": gt, "matchup": mu, "team": tm,
                "player": None, "status": NOT_SUBMITTED, "reason": None,
                "team_carried": False,
            })
            game_date, tip, game = gd or game_date, gt or tip, mu or game
            continue

        # a normal row has a status cell; find it
        status_idx = None
        for i, c in enumerate(cells):
            if c in STATUSES:
                status_idx = i
                break
        if status_idx is None:
            # an orphan continuation line: the fetch split a reason across its
            # own chunk boundary.  Kept so _rejoin_orphan_reasons can put the
            # two halves back together, never published as its own row.
            text = " | ".join(c for c in cells if c).strip()
            if text:
                rows.append({"game_date": None, "game_time_et": None, "matchup": None,
                             "team": None, "player": None, "status": None, "reason": None,
                             "_orphan_text": text, "team_carried": False})
                notes.append(f"orphan continuation line captured: {text[:120]}")
            continue

        player = cells[status_idx - 1] if status_idx >= 1 else None
        # the reason is the last real cell; a chunk-seam repair can leave the
        # reason split over two cells, which is joined here (both halves are
        # printed text, nothing is added)
        tail = [c for c in cells[status_idx + 1:] if c]
        reason = " ".join(tail).strip() if tail else None
        left = cells[:status_idx - 1]

        gd = gt = mu = None
        tm = None
        for c in left:
            if re.match(r"^\d{2}/\d{2}/\d{4}$", c):
                gd = c
            elif re.match(r"^\d{2}:\d{2}", c):
                gt = c
            elif "@" in c and len(c) <= 12:
                mu = c
            elif c:
                tm = c

        carried = False
        if tm:
            team = tm
        else:
            carried = True

        game_date = gd or game_date
        tip = gt or tip
        game = mu or game

        rows.append({
            "game_date": game_date, "game_time_et": tip, "matchup": game, "team": team,
            "player": player, "status": cells[status_idx], "reason": reason,
            "team_carried": carried,
        })

    return rows, notes


def _rejoin_orphan_reasons(rows, notes):
    """Reattach a reason torn in half by the fetch's chunk boundary.

    The document prints ``Sorber, Thomas | Out | Injury/Illness - `` at the end
    of one chunk and ``| Right Knee Surgery |`` at the start of the next.  A
    row whose reason ends in a bare ``-`` is therefore joined to the following
    orphan line.  The join is recorded so the published row can be traced back
    to two physical pieces of text.
    """
    joined = []
    i = 0
    while i < len(rows):
        r = dict(rows[i])
        reason = r.get("reason") or ""
        if reason.strip().endswith("-") and i + 1 < len(rows):
            nxt = rows[i + 1]
            if nxt.get("player") is None and nxt.get("_orphan_text"):
                r["reason"] = (reason.rstrip() + " " + nxt["_orphan_text"].strip()).strip()
                r["reason_joined_across_chunk_boundary"] = True
                notes.append(f"reason for {r.get('player')} joined across the chunk boundary")
                i += 1
        joined.append(r)
        i += 1
    return joined


def _join_chunks(chunks):
    """Concatenate the fetched chunks, repairing a row the fetch cut in half.

    If a chunk ends mid-row (its last line is part of a table row and the next
    chunk starts with a table row continuation), the two halves are joined into
    one line.  This is a repair of the TOOL's pagination, not of the league's
    document: the printed cells are untouched, only a line break inserted by the
    fetch is removed.  Every repair is recorded in ``_JOIN_REPAIRS`` so the fact
    is auditable rather than invisible.
    """
    _JOIN_REPAIRS.clear()
    out = []
    for i, chunk in enumerate(chunks):
        if not out:
            out.append(chunk)
            continue
        prev = out[-1]
        prev_tail = prev.rstrip("\n").split("\n")[-1] if prev.strip() else ""
        first = chunk.split("\n", 1)[0]
        # the seam is a torn row when the previous last line is an unterminated
        # table row (ends with a bare hyphen or no closing pipe) and this chunk
        # opens with a pipe
        if (prev_tail.startswith("|") and not prev_tail.rstrip().endswith("|")
                and first.lstrip().startswith("|")):
            head = prev.rstrip("\n")[: -len(prev_tail)]
            out[-1] = head + prev_tail.rstrip() + " " + first.lstrip()
            _JOIN_REPAIRS.append({"seam_after_chunk": i - 1,
                                  "tail": prev_tail[-60:], "head": first[:60]})
            rest = chunk.split("\n", 1)[1] if "\n" in chunk else ""
            out.append(rest)
        else:
            out.append(chunk)
    return "\n".join(out)


_JOIN_REPAIRS = []


def split_fragments(capture: dict):
    """Join the fetched chunks, then split on the PDF's own page breaks.

    Two different boundaries exist and only one of them means anything:

    * the **chunk** boundary is an artefact of how the fetch tool paginated the
      text.  It can land in the middle of a row -- in this document it cuts
      ``Sorber, Thomas | Out | Injury/Illness - `` away from ``Right Knee
      Surgery`` -- and it carries no contextual meaning at all.
    * the ``* * *`` separator is the league's own page break: the table header
      repeats after it, which is the document saying that column context (the
      game and the team) does not carry across.

    So the chunks are concatenated first and the result is split on ``* * *``.
    Getting this the wrong way round silently attributes rows to the previous
    page's team, which is the failure mode this whole module exists to avoid.
    """
    joined = _join_chunks(capture.get("chunks", []))
    parts = re.split(r"^\s*\*\s*\*\s*\*\s*$", joined, flags=re.MULTILINE)
    return [p for p in parts if p.strip()]


def parse_document(capture: dict):
    """Parse every page-fragment of an archived capture.

    Context resets between fragments by design; a row whose team could not be
    established within its own fragment keeps ``team=None`` and is listed in
    ``unattributed`` so the caller can refuse to publish it rather than guess.
    """
    rows, notes = [], []
    for i, frag in enumerate(split_fragments(capture)):
        frag_rows, frag_notes = parse_fragment(frag)
        frag_rows = _rejoin_orphan_reasons(frag_rows, notes)
        for r in frag_rows:
            r["fragment"] = i
            # attribution confidence: was this row's team printed on the row
            # itself (``printed``), inherited from the row above inside the same
            # page fragment (``carried``), or not establishable (``unattributed``)?
            if r.get("_orphan_text"):
                r["attribution"] = "orphan"
            elif r["status"] == NOT_SUBMITTED:
                r["attribution"] = "printed"
            elif r["team"] is None:
                r["attribution"] = "unattributed"
            elif r["team_carried"]:
                r["attribution"] = "carried"
            else:
                r["attribution"] = "printed"
        # a promoted continuation row inherits the team printed above it when the
        # promotion happened at a page break; mark it so nothing downstream can
        # mistake it for a printed team cell
        for r in frag_rows:
            if r.get("_promoted_context"):
                r["attribution"] = "carried_across_page_break"
        rows.extend(frag_rows)
        notes.extend(f"[fragment {i}] {n}" for n in frag_notes)

    # carry the game context across fragments only where the game date/tip/matchup
    # are unambiguous: a fragment that starts mid-block inherits nothing, which is
    # why team_carried is recorded rather than assumed.
    unattributed = [r for r in rows
                    if r["team"] is None and r["status"] not in (NOT_SUBMITTED, None)]
    bad_context = [r for r in rows
                   if r["matchup"] is None and r["status"] not in (NOT_SUBMITTED, None)]
    orphans = [r for r in rows if r.get("_orphan_text")]
    return {
        "rows": rows,
        "notes": notes,
        "unattributed": unattributed,
        "missing_game_context": bad_context,
        "chunk_seam_repairs": [r for r in _JOIN_REPAIRS],
        "counts": {
            "rows": len(rows),
            "player_rows": len([r for r in rows if r["status"] != NOT_SUBMITTED]),
            "not_submitted_rows": len([r for r in rows if r["status"] == NOT_SUBMITTED]),
            "unattributed": len(unattributed),
            "missing_game_context": len(bad_context),
            "teams_carried": len([r for r in rows if r.get("team_carried")]),
            "orphan_lines": len(orphans),
        },
    }


# ---------------------------------------------------------------------------
# diff between two reports
# ---------------------------------------------------------------------------
SEVERITY = {"Out": 4, "Doubtful": 3, "Questionable": 2, "Probable": 1,
            "Available": 0, NOT_SUBMITTED: -1}


def _to_iso_date(s):
    """'11/15/2026' or '2026-11-15' -> '2026-11-15'; None if unparsable."""
    if not s:
        return None
    s = s.strip()
    if len(s) == 10 and s[4] == "-":
        return s
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        m, d, y = (int(x) for x in parts)
    except ValueError:
        return None
    if y < 100:
        y += 2000
    try:
        return _dt.date(y, m, d).isoformat()
    except ValueError:
        return None


def attach_scheduled_dates(parsed: dict, schedule: dict) -> dict:
    """Establish each row's game date, and record HOW it was established.

    The league's own document prints the Game Date, Game Time and Team columns
    only on the first row of each table block; the page fragments that continue
    a table across a page break leave those three cells blank.  The matchup IS
    printed on those rows.  There are therefore three routes to a date, and each
    one is checked before it is used:

    ``printed``
        The date cell is printed on the row.  Used as-is.
    ``carried``
        The date cell is blank and the document is date-ordered, so the most
        recent printed date above the row applies.  **The carry is verified**:
        the row's printed matchup must actually be scheduled on that date in the
        official schedule capture.  A carry that fails the check is not used.
    ``matched``
        The date cell is blank and the carry failed or is unavailable, so the
        printed matchup is looked up in the official schedule.  Used only when
        the matchup occurs on exactly one date in the window.
    ``unknown``
        None of the above.  The row is counted and reported; it is not published
        against any slate.

    A matchup that is scheduled twice inside the three-day window (NYK@TOR is on
    both 11/15 and 11/17, POR@MIN on both 11/16 and 11/17) makes route 3
    ambiguous by construction -- which is exactly why the printed-date carry is
    preferred and why the check exists.

    This is a lookup and a consistency check against official sources.  Nothing
    here infers a date from a model or from the order of the injury list.
    """
    index = {}
    for g in schedule.get("upcoming", []):
        index.setdefault(f"{g['away']}@{g['home']}", set()).add(g["date"])
    ambiguous = {m: sorted(d) for m, d in index.items() if len(d) > 1}

    rows = parsed["rows"]
    counts = {"printed": 0, "carried": 0, "matched": 0, "unknown": 0}
    rejected_carries = []
    last_printed = None

    for r in rows:
        if r.get("game_date"):
            # The document prints MM/DD/YYYY; the schedule capture uses ISO.
            # Both must be in the SAME form before any comparison, or every
            # carry check fails for a reason that has nothing to do with the data.
            raw = r["game_date"]
            iso = _to_iso_date(raw)
            if iso is None:
                r["game_date_raw_printed"] = raw
                r["game_date"] = None
                r["game_date_source"] = "unknown"
                counts["unknown"] += 1
                continue
            if iso != raw:
                r["game_date_raw_printed"] = raw
            r["game_date"] = iso
            r["game_date_source"] = "printed"
            last_printed = iso
            counts["printed"] += 1
            continue

        m = r.get("matchup")
        sched_dates = index.get(m)

        # route 2: carry the printed date above, but only if the schedule agrees
        if last_printed and sched_dates and last_printed in sched_dates:
            r["game_date"] = last_printed
            r["game_date_source"] = "carried"
            counts["carried"] += 1
            continue
        if last_printed and sched_dates and last_printed not in sched_dates:
            rejected_carries.append({
                "matchup": m, "carried_date_would_have_been": last_printed,
                "scheduled_dates": sorted(sched_dates),
                "why_rejected": "the printed matchup is not scheduled on the carried date",
            })

        # route 3: unique matchup lookup
        if sched_dates and len(sched_dates) == 1:
            r["game_date"] = next(iter(sched_dates))
            r["game_date_source"] = "matched"
            counts["matched"] += 1
            continue

        r["game_date_source"] = "unknown"
        counts["unknown"] += 1

    out = dict(parsed)
    out["rows"] = rows
    # carry the capture's provenance fields through, so a gate reading the
    # parsed bundle sees the same revision and retrieval stamps as the capture
    for k in ("source_url", "index_url", "report_stamp_printed", "report_stamp_note",
              "retrieved_utc", "retrieval_tool", "supersedes", "kind"):
        if k in parsed:
            out[k] = parsed[k]
    out["date_recovery"] = {
        "rows_by_source": counts,
        "ambiguous_matchups": ambiguous,
        "rejected_carries": rejected_carries,
        "dates_covered": sorted({r["game_date"] for r in rows if r.get("game_date")}),
        "rows_still_undated": counts["unknown"],
        "method": ("printed date where the document prints one; otherwise the printed date above, "
                   "verified against the official schedule for that matchup; otherwise a unique "
                   "matchup lookup; otherwise undated and refused"),
    }
    return out


def diff_reports(old, new):
    """Row-level status changes between two parsed reports.

    Key is (game_date, matchup, team, player).  A player appearing or
    disappearing is reported as such; it is NOT treated as a status change,
    because a player dropping off the report entirely is how the league says
    "no longer affected", and conflating the two would inflate every delta.
    """
    def index(rep):
        out = {}
        for r in rep.get("rows", []):
            if r["status"] == NOT_SUBMITTED:
                continue
            out[(r["game_date"], r["matchup"], r["team"], r["player"])] = r
        return out

    a, b = index(old), index(new)
    changes, appeared, vanished = [], [], []
    for k in sorted(a.keys() & b.keys(), key=lambda x: tuple("" if v is None else v for v in x)):
        if a[k]["status"] != b[k]["status"]:
            changes.append({
                "game_date": k[0], "matchup": k[1], "team": k[2], "player": k[3],
                "from_status": a[k]["status"], "to_status": b[k]["status"],
                "from_reason": a[k]["reason"], "to_reason": b[k]["reason"],
                "direction": ("worse" if SEVERITY.get(b[k]["status"], 0)
                              > SEVERITY.get(a[k]["status"], 0) else "better"),
            })
    for k in sorted(b.keys() - a.keys()):
        appeared.append({"game_date": k[0], "matchup": k[1], "team": k[2], "player": k[3],
                         "status": b[k]["status"], "reason": b[k]["reason"]})
    for k in sorted(a.keys() - b.keys()):
        vanished.append({"game_date": k[0], "matchup": k[1], "team": k[2], "player": k[3],
                         "was_status": a[k]["status"]})
    # A name that "appears" while a near-identical name on the same team and
    # matchup "vanishes", with the same status and reason, is a spelling
    # correction by the league -- not a roster event.  Collapsing the two into
    # one bucket stops a typo fix from being counted as a status change, which
    # is the difference between an honest delta and a fabricated one.
    corrections, real_appeared = [], []
    vanished_left = list(vanished)
    for a in appeared:
        match = None
        for v in vanished_left:
            if (v["game_date"] == a["game_date"] and v["matchup"] == a["matchup"]
                    and v["team"] == a["team"] and v["was_status"] == a["status"]
                    and _similar(v["player"], a["player"])):
                match = v
                break
        if match:
            corrections.append({
                "type": "spelling_correction",
                "team": a["team"], "matchup": a["matchup"], "game_date": a["game_date"],
                "previous_spelling": match["player"], "corrected_spelling": a["player"],
                "status": a["status"], "reason": a["reason"],
                "note": "status and reason identical; only the printed name changed",
            })
            vanished_left.remove(match)
        else:
            real_appeared.append(a)
    return {
        "changed": changes,
        "appeared": real_appeared,
        "vanished": vanished_left,
        "spelling_corrections": corrections,
        "chunk_seam_repairs": [r for r in _JOIN_REPAIRS],
        "counts": {"changed": len(changes), "appeared": len(real_appeared),
                   "vanished": len(vanished_left),
                   "spelling_corrections": len(corrections)},
    }


def _similar(a: str, b: str) -> bool:
    """Cheap name-similarity: same surname, and given names within 2 edits."""
    if not a or not b:
        return False
    na = " ".join(a.replace(",", " ").lower().split())
    nb = " ".join(b.replace(",", " ").lower().split())
    if na == nb:
        return True
    # the given name must match exactly; the surname may be a typo away
    ga = a.split(",")[-1].strip().lower() if "," in a else ""
    gb = b.split(",")[-1].strip().lower() if "," in b else ""
    if "," in a and "," in b and ga != gb:
        return False
    return _edit_distance(na, nb) <= 2


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def team_status_map(report, game_date):
    """team -> {player: status} for one game date, excluding NOT SUBMITTED rows."""
    out = {}
    for r in report.get("rows", []):
        if r["game_date"] != game_date or r["status"] == NOT_SUBMITTED:
            continue
        if not r["team"]:
            continue
        out.setdefault(r["team"], {})[r["player"]] = r["status"]
    return out


def filed_teams(report, game_date):
    """Teams that filed a real report for a date (excluding NOT YET SUBMITTED)."""
    return sorted(team_status_map(report, game_date).keys())


def due_teams(report, game_date):
    """Teams the league still shows as NOT YET SUBMITTED for a date."""
    return sorted({r["team"] for r in report.get("rows", [])
                   if r["game_date"] == game_date and r["status"] == NOT_SUBMITTED
                   and r["team"]})
