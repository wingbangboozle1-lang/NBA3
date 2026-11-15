"""Parse an official NBA gamebook PDF transcription into player game logs.

Why this file exists: the transcription step is human, so the parser does not trust it.

A player row is ACCEPTED only if it satisfies all of:
  1. PTS == 2*FG + 3P + FT        (the gamebook's own scoring identity)
  2. TOT == OR + DR               (total rebounds identity)
  3. FGM <= FGA, 3PM <= 3PA, FTM <= FTA, 3PM <= FGM
  4. the row's *shape* is a gamebook player row: at most three non-empty cells before MIN
     (jersey, name, position), at most one jersey number, one name cell, one position code.

Rule 4 is what catches a misaligned PDF extraction: when the extraction inserts an extra
column, the stat slice shifts and a row can still satisfy rule 1 by coincidence (Buddy Hield's
row in the CHI@MIN extraction does). A row that fails any rule is dropped and counted; it is
never repaired, re-aligned, guessed or inferred.

Team-total rows (MIN 240:00) and DNP/DND/NWT rows are recognised structurally and excluded
from the player list; the totals are used only to cross-check the parsed sum.

Import-only: no writes at import time, so CI can call it offline.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

STAT_COLS = 16   # FG FGA 3P 3PA FT FTA OR DR TOT A PF ST TO BS +/- PTS


@dataclass
class GameLog:
    game_id: str
    date: str
    team: str
    opponent: str
    location: str            # "home" or "away"
    player: str
    jersey: str
    position: str
    min_seconds: int
    fgm: int
    fga: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int
    oreb: int
    dreb: int
    reb: int
    ast: int
    stl: int
    blk: int
    tov: int
    pf: int
    plus_minus: int
    pts: int
    source_url: str

    def as_row(self) -> dict:
        return {
            "game_id": self.game_id, "date": self.date, "team": self.team,
            "opponent": self.opponent, "location": self.location,
            "player": self.player, "jersey": self.jersey, "position": self.position,
            "min": round(self.min_seconds / 60.0, 2), "min_raw": mmss(self.min_seconds),
            "pts": self.pts, "reb": self.reb, "ast": self.ast, "stl": self.stl,
            "blk": self.blk, "tov": self.tov, "pf": self.pf,
            "fgm": self.fgm, "fga": self.fga, "fg3m": self.fg3m, "fg3a": self.fg3a,
            "ftm": self.ftm, "fta": self.fta,
            "oreb": self.oreb, "dreb": self.dreb, "plus_minus": self.plus_minus,
            "source_url": self.source_url,
        }


@dataclass
class ParsedGame:
    accepted: list = field(default_factory=list)
    rejected: list = field(default_factory=list)      # (team_tag, line)
    team_totals: dict = field(default_factory=dict)   # team_tag -> printed total PTS (or None)
    periods: dict = field(default_factory=dict)       # team_label -> [q1, q2, q3, q4, final]
    warnings: list = field(default_factory=list)

    def points_by_team(self) -> dict:
        out: dict[str, int] = {}
        for g in self.accepted:
            out[g.team] = out.get(g.team, 0) + g.pts
        return out

    def reconcile(self) -> dict:
        """Compare the parsed player total to the printed team total, per team."""
        pts = self.points_by_team()
        res = {}
        for team, printed in self.team_totals.items():
            res[team] = {"parsed": pts.get(team), "printed": printed,
                         "match": printed is not None and pts.get(team) == printed}
        return res


def mmss(total_seconds: int) -> str:
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def _seconds(text: str) -> int | None:
    m = re.fullmatch(r"(\d+):(\d{2})", text.strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_gamebook(text: str, *, game_id: str, date: str, away: str, home: str,
                   away_team: str, home_team: str, source_url: str) -> ParsedGame:
    out = ParsedGame()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)   # provenance notes are not table data
    saw_visitor_header = "VISITOR:" in text.upper()
    block = None
    in_periods = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.startswith("|"):
            continue
        header = line.upper()
        if "VISITOR:" in header or "HOME:" in header:
            loc = "away" if "VISITOR:" in header else "home"
            block = (away, away_team, loc) if loc == "away" else (home, home_team, loc)
            in_periods = False
            continue
        if "SCORE BY PERIOD" in header:
            in_periods = True
            block = None
            continue

        cells = _cells(line)
        if not cells or all(not c for c in cells):
            continue
        if re.fullmatch(r"[-| ]+", line.strip("|")):
            continue
        upper = [c.upper() for c in cells if c]
        if "PLAYER" in upper or ("POS" in upper and "MIN" in upper):
            continue
        if upper and upper[0] == "TEAM":
            continue

        if in_periods:
            nums = [int(c) for c in cells if re.fullmatch(r"\d+", c)]
            if nums:
                label = next((c for c in cells if c and not re.fullmatch(r"\d+", c)), "")
                out.periods[label] = nums
            continue

        if block is None:
            if not saw_visitor_header:
                # This extraction drops the 'VISITOR: ...' header line, so the first table on the
                # page is the visitor (gamebooks always print the visitor first). The caller must
                # still confirm the parsed PTS sum equals the printed team total before use.
                block = (away, away_team, "away")
                out.warnings.append("no VISITOR header; first table treated as the away team")
            else:
                continue

        min_idx = next((i for i, c in enumerate(cells)
                        if re.fullmatch(r"(\d{1,2}:\d{2}|240:00)", c)), None)
        if min_idx is None:
            joined = " ".join(cells).upper()
            if any(k in joined for k in ("DNP", "DND", "NWT")):
                continue
            out.rejected.append((block[0], line))
            continue

        tail = cells[min_idx + 1:]
        nums: list[int] = []
        for c in tail:                     # one extraction emits an empty cell mid-slice
            if c == "":
                continue
            if re.fullmatch(r"-?\d+", c):
                nums.append(int(c))
            else:
                break

        if cells[min_idx] == "240:00":
            out.team_totals[block[0]] = nums[-1] if len(nums) >= STAT_COLS else None
            continue
        if len(nums) < STAT_COLS:
            out.rejected.append((block[0], line))
            continue

        (fgm, fga, fg3m, fg3a, ftm, fta, oreb, dreb, reb, ast, pf, stl, tov, blk,
         plus_minus, pts) = nums[:STAT_COLS]

        if pts != 2 * fgm + fg3m + ftm or reb != oreb + dreb:
            out.rejected.append((block[0], line))
            continue
        if not (fgm <= fga and fg3m <= fg3a and ftm <= fta and fg3m <= fgm):
            out.rejected.append((block[0], line))
            continue

        lead = [c for c in cells[:min_idx] if c]
        if len(lead) > 3:                  # shape rule: jersey, name, position at most
            out.rejected.append((block[0], line))
            continue
        ints = [c for c in lead if re.fullmatch(r"\d+", c)]
        pos_cells = [c for c in lead if c.upper() in ("F", "C", "G")]
        names = [c for c in lead if c and c not in ints and c not in pos_cells]
        if len(ints) > 1 or len(pos_cells) > 1 or len(names) > 1:
            out.rejected.append((block[0], line))
            continue
        jersey = ints[0] if ints else ""
        player = names[0] if names else ""
        position = pos_cells[0] if pos_cells else ""
        if not player or not re.search(r"[A-Za-z]", player):
            out.rejected.append((block[0], line))
            continue

        abbr, _team_name, loc = block
        out.accepted.append(GameLog(
            game_id=game_id, date=date, team=abbr,
            opponent=home if loc == "away" else away, location=loc,
            player=player, jersey=jersey, position=position,
            min_seconds=_seconds(cells[min_idx]),
            fgm=fgm, fga=fga, fg3m=fg3m, fg3a=fg3a, ftm=ftm, fta=fta,
            oreb=oreb, dreb=dreb, reb=reb, ast=ast, stl=stl, blk=blk, tov=tov, pf=pf,
            plus_minus=plus_minus, pts=pts, source_url=source_url))
    return out


def summarise(parsed: ParsedGame) -> dict:
    return {
        "accepted_rows": len(parsed.accepted),
        "rejected_rows": len(parsed.rejected),
        "accepted_by_team": dict(sorted(Counter(g.team for g in parsed.accepted).items())),
        "rejected_by_team": dict(sorted(Counter(t for t, _ in parsed.rejected).items())),
        "rejected_detail": [{"team": t, "line": l[:160]} for t, l in parsed.rejected],
        "team_reconciliation": parsed.reconcile(),
        "periods": parsed.periods,
        "warnings": parsed.warnings,
    }
