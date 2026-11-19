#!/usr/bin/env python3
"""Promote the 2026-11-19 official reads into the canonical artefacts (session arena/915d2e99-nba3).

Offline, deterministic and replayable: `--check` re-parses the verbatim transcripts committed under
`data/rounds/2026-11-19/raw915/` and fails if any promoted artefact drifts from them. Nothing here
reaches the network, and nothing that is not printed in a transcript is written.

What it writes:

  data/app/official_slate_current.json      the rolling window the site prices and the ledger
                                            publishes from — 2026-11-19 .. 2026-11-21 (today plus
                                            two days; the brief caps advance picks at three days),
                                            one row per game with tip time and both records as the
                                            official date page printed them.

  data/app/official_results_2026-11-17.json one row per game, schema nba3.official_results/v1, the
  data/app/official_results_2026-11-18.json   shape scripts/results_feed.py `ingest --rows` reads.

  data/rounds/2026-11-19/915d2e99_manifest.json
                                            sha256 + bytes + retrieval window + source URL per
                                            transcript, the same shape the 2026-11-17 round used.

Verification rules enforced here, each of which REFUSES to write rather than repairing:
  * the number of parsed cards must equal the count the page's own month strip printed;
  * the two tricodes in a card's URL must match the two team names in the card, mapped through
    data/live/team_registry.json (the registry the site already uses);
  * a game-day final must be printed identically on TWO official pages when a second read exists
    (11/18: the date page and the game page's day list; 11/17: the date page card and the same
    page's recap-slug line). One-sided rows are published with `verification` naming the single
    read, and the score is still official — the difference is recorded, not hidden;
  * quarter scores are NOT captured in these transcripts, so no row carries `away_q`/`home_q`:
    scripts/results_feed.py then marks the row "quarter scores not captured — blank, flagged"
    rather than inventing them, which is the no-inference rule the project runs on.

Run:  python3 scripts/roll_915d2e99.py          # write
      python3 scripts/roll_915d2e99.py --check   # fail on drift
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "data", "rounds", "2026-11-19", "raw915")
APP = os.path.join(ROOT, "data", "app")
RD = os.path.join(ROOT, "data", "rounds", "2026-11-19")
REGISTRY = os.path.join(ROOT, "data", "live", "team_registry.json")
MANIFEST = os.path.join(RD, "915d2e99_manifest.json")
SLATE_OUT = os.path.join(APP, "official_slate_current.json")
RESULTS_OUT = {day: os.path.join(APP, f"official_results_{day}.json")
               for day in ("2026-11-16", "2026-11-17", "2026-11-18")}

SESSION = "arena/915d2e99-nba3"
# Retrieved 2026-11-19 between 05:57Z and 06:03Z UTC; the window is stated because the fetch tool
# returns no per-call stamp (the same limit b1ce1334 recorded for its capture).
RETRIEVED_WINDOW = "2026-11-19T05:57Z..2026-11-19T06:04Z"

# The count each page's own month strip printed (see the "Month strip printed" line in each
# transcript). This is an independent check on the card parse, taken from the same official page.
STRIP_COUNT = {"2026-11-16": 8, "2026-11-17": 5, "2026-11-18": 12, "2026-11-19": 4,
               "2026-11-20": 9, "2026-11-21": 6}
SLATE_DAYS = ("2026-11-19", "2026-11-20", "2026-11-21")
FINAL_DAYS = ("2026-11-16", "2026-11-17", "2026-11-18")
# 2026-11-16 was read through a chunk boundary: the page prints 8 games, the retrieval delivered 6
# complete cards. The day is published INCOMPLETE on purpose — the two rows that were not read are
# named here so the artefact says so, and their sealed picks stay unsettled. No score is guessed to
# close the day.
PARTIAL_DAYS = {
    "2026-11-16": {
        "printed_game_count": 8,
        "cards_captured": 6,
        "missing_game_ids": ["0022600250", "0022600252"],
        "why": ("the official date page was returned in 2 chunks and the retrieval of chunk 1 "
                "failed, so the last cards of the page are not in the transcript; the ids missing "
                "are identified two independent ways that agree: the 6 cards present are "
                "0022600245-49 and 0022600251, and the sealed ledger carries 0022600245-52 for "
                "2026-11-16"),
        "consequence": ("6 of 8 finals are published and settled; 0022600250 and 0022600252 have no "
                        "verified final, so their two sealed picks remain PUBLISHED_PRE_TIP and are "
                        "listed on the Flagged for Review page"),
    }
}

GAME_LINK = re.compile(r"\]\(https://www\.nba\.com/game/([a-z]{3})-vs-([a-z]{3})-(\d{10})\)\s*$")
TIP_RE = re.compile(r"^(\d{1,2}:\d{2}\s+[AP]M\s+ET)$")
REC_RE = re.compile(r"^(\d+-\d+)(?:\s+\((\d+-\d+)\))?$")
SCORE_RE = re.compile(r"^(\d{1,3})$")
# The recap links the same page prints name both clubs and both scores, winner first:
# game-recap-timberwolves-106-trail-blazers-105-nov-17. Names may contain hyphens ("trail-blazers"),
# so a name is any run of lowercase letters, spaces and hyphens that is followed by -<score>-.
RECAP_RE = re.compile(r"game-recap-([a-z0-9][a-z0-9 -]*?)-(\d{1,3})-([a-z0-9][a-z0-9 -]*?)-"
                      r"(\d{1,3})(?:-nov-\d{2})?\)?")
FINAL_TOKENS = ("Final/OT", "Final")


def load_registry() -> dict[str, str]:
    """printed team name -> tricode, from data/live/team_registry.json's official full names.

    The date page prints a short name that is not always the last token of the full name: POR's card
    says "Trail Blazers" while the registry says "Portland Trail Blazers". So the join accepts any
    trailing one- or two-word suffix of the official full name, and refuses to build the map if any
    such suffix would point at two clubs. The result is asserted to cover all 30 teams, so the join
    cannot silently fold two clubs into one code or leave a club unreachable.
    """
    teams = json.load(open(REGISTRY, encoding="utf-8"))["teams"]
    nick: dict[str, str] = {}
    for code, v in teams.items():
        words = v["full_name"].split()
        for n in (1, 2):
            if len(words) < n:
                continue
            key = " ".join(words[-n:])
            if key in nick and nick[key] != code:
                raise SystemExit(f"team registry: {key!r} maps to both {nick[key]} and {code}")
            nick[key] = code
    covered = {nick[v["full_name"].split()[-1]] for v in teams.values()}
    if covered != set(teams):
        raise SystemExit("team registry: the nickname join does not reach every club in the registry")
    return nick


def card_blocks(text: str) -> list[tuple[str, str, str, str, str]]:
    """(block_text, away_code, home_code, game_id, line) for every card whose block starts at col 0.

    Sub-links under a card ("- [Watch](…?watchFullGame)", "- [Box score](…/box-score#box-score)")
    are excluded twice over: a block only opens on a line starting with "[" at column 0, and the
    closing pattern requires the URL to end with the 10-digit game id.
    """
    out, buf = [], []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("["):
            buf = [line]
        elif buf:
            buf.append(line)
        else:
            continue
        m = GAME_LINK.search(line)
        if m and buf:
            out.append((" ".join(buf), m.group(1).upper(), m.group(2).upper(), m.group(3), line))
            buf = []
    return out


def tokens_of(block: str) -> list[str]:
    """The card's own token stream: the markdown '\\\\' separators the page renders between values.

    The card's closing `](https://www.nba.com/game/…)` is the link target, not a value, and the last
    VALUE sits immediately before it — so it is cut off first, otherwise "5-10](url)" is neither a
    record nor a score and the row loses a printed value for a parsing reason rather than a data one.
    """
    block = re.sub(r"\]\(https?://[^)]+\)\s*$", "", block)
    parts = re.split(r"\\\\", block)
    keep = []
    for p in parts:
        t = p.strip()
        if not t or t.startswith("![") or t.startswith("Emirates NBA Cup"):
            continue
        t = re.sub(r"^\[", "", t)
        keep.append(t)
    return keep


def parse_card(block: str, away: str, home: str, gid: str, date: str,
               name_by_full: dict[str, str]) -> dict:
    """One card block -> a row. Raises on anything that does not read cleanly; nothing is guessed."""
    toks = tokens_of(block)
    names = [t for t in toks if t in name_by_full]   # only official registry names are trusted
    tip = next((m.group(1) for t in toks if (m := TIP_RE.match(t))), None)
    recs = [m.groups() for t in toks if (m := REC_RE.match(t))]
    row: dict = {"date": date, "game_id": gid, "away": away, "home": home,
                 "time_et": tip, "game_url": f"https://www.nba.com/game/{away.lower()}"
                                              f"-vs-{home.lower()}-{gid}",
                 "source": f"https://www.nba.com/games?date={date}"}
    # records, in card order: away first, home second. Cup group records ride along.
    if len(recs) >= 2:
        row["away_record"], row["home_record"] = recs[0][0], recs[1][0]
        if recs[0][1] and recs[1][1]:
            row["away_cup_record"], row["home_cup_record"] = recs[0][1], recs[1][1]
    else:
        row["away_record"] = row["home_record"] = None
        row["flags"] = row.get("flags", []) + ["records not parsed from the card"]
    # a printed group label is copied verbatim; it changes what a "win" is worth
    grp = re.search(r"(East|West) Group ([A-C])", block)
    if grp:
        row["cup_group"] = f"{grp.group(1)} Group {grp.group(2)}"
    # team names, used to prove the URL tricodes match the card
    if len(names) == 2:
        row["away_name"], row["home_name"] = names
        for code, nm in ((away, names[0]), (home, names[1])):
            want = name_by_full[nm]
            if want != code:
                raise ValueError(f"{gid}: card name {nm!r} maps to {want} in the registry, "
                                 f"the URL says {code}")
    elif len(names) > 2:
        raise ValueError(f"{gid}: more than two registry nicknames in one card: {names}")
    else:
        raise ValueError(f"{gid}: expected 2 team names in the card, found {names}")
    # Result, if the card prints one. The two layouts this file reads place the numbers
    # differently -- the date page prints `away_pts Final home_pts`, a game page's day list prints
    # `Final` first and then each score right after its own team -- so the rule is the one both
    # share: a card that carries a state token carries EXACTLY two bare integers, in away-then-home
    # order, and they must not be a record (records are matched as `\d+-\d+` and dropped here).
    state = next((t for t in toks if t in FINAL_TOKENS), None)
    scores = [t for t in toks if SCORE_RE.match(t)]
    if state is not None:
        if len(scores) != 2:
            raise ValueError(f"{gid}: card prints {state!r} but {len(scores)} bare scores "
                             f"({scores}); refusing to assign a score to a side")
        row["status"] = state
        row["away_pts"], row["home_pts"] = int(scores[0]), int(scores[1])
        row["ot"] = 1 if state == "Final/OT" else 0
    elif scores:
        raise ValueError(f"{gid}: card prints scores {scores} without a Final state token")
    return row


def recap_scores(text: str) -> dict[tuple[int, int], str]:
    """{score pair -> slug} from the page's own recap links — a second read of both scores.

    A recap slug names the WINNER first (game-recap-timberwolves-106-trail-blazers-105-nov-17 for a
    card that prints POR 105 / MIN 106), so the pair is keyed sorted on both sides: the check being
    made is "these two clubs, these two numbers, same pairing", not the order a headline chose.
    """
    out: dict[tuple[int, int], str] = {}
    for m in RECAP_RE.finditer(text):
        key = tuple(sorted((int(m.group(2)), int(m.group(4)))))
        out[key] = m.group(0).rstrip(")")
    return out


def finals_from(text: str, date: str, names: dict[str, str]) -> dict[str, dict]:
    rows = {}
    for block, away, home, gid, _line in card_blocks(text):
        r = parse_card(block, away, home, gid, date, names)
        if "status" not in r:
            continue
        if gid in rows:
            raise ValueError(f"{gid}: appears twice on the {date} page")
        rows[gid] = r
    return rows


def check_counts(date: str, rows: dict[str, dict]) -> None:
    want = PARTIAL_DAYS.get(date, {}).get("cards_captured", STRIP_COUNT[date])
    declared = PARTIAL_DAYS.get(date, {}).get("printed_game_count")
    if declared is not None and STRIP_COUNT.get(date) != declared:
        raise SystemExit(f"{date}: PARTIAL_DAYS declares {declared} printed games but the strip "
                         f"note says {STRIP_COUNT.get(date)}")
    if len(rows) != want:
        raise SystemExit(f"{date}: parsed {len(rows)} cards but the page's month strip printed "
                         f"{want} GAMES — refusing to publish a partial day")


def build_slate(names: dict[str, str]) -> dict:
    games = []
    for day in SLATE_DAYS:
        text = open(os.path.join(RAW, f"games_{day}.md"), encoding="utf-8").read()
        cards = {}
        for block, away, home, gid, _line in card_blocks(text):
            row = parse_card(block, away, home, gid, day, names)
            if "status" in row:
                raise SystemExit(f"{gid}: a {day} card prints a final score; the slate must be open")
            cards[gid] = row
        if len(cards) != STRIP_COUNT[day]:
            raise SystemExit(f"{day}: slate parsed {len(cards)} cards, strip printed "
                             f"{STRIP_COUNT[day]} GAMES")
        games.extend(cards.values())
    games.sort(key=lambda r: (r["date"], r["time_et"] or "", r["game_id"]))
    return {"source_url": "https://www.nba.com/games?date=2026-11-19",
            "source_label": (f"official date pages for the rolling window, read {RETRIEVED_WINDOW} "
                             f"UTC and promoted by scripts/roll_915d2e99.py from the game cards on "
                             f"each page (verbatim transcripts under data/rounds/2026-11-19/raw915/)"),
            "retrieved_on": "2026-11-19", "retrieved_utc": "2026-11-19T06:04Z",
            "window": {"from": SLATE_DAYS[0], "to": SLATE_DAYS[-1]},
            "count": len(games), "games": games, "excluded": [],
            # provenance of the PROMOTION (not of the read): which script wrote this file, and which
            # manifest carries the transcript hashes it was parsed from.
            # tests/test_refresh_official.py dispatches on `promoted_by` so a slate promoted from a
            # round transcript is re-checked with that round's own tooling instead of against
            # data/app/refresh/ (which holds only CI captures).
            "promoted_by": "scripts/roll_915d2e99.py",
            "round_manifest": os.path.relpath(MANIFEST, ROOT).replace(os.sep, "/"),
            "captured_by": SESSION,
            "notes": [
                "the window is today plus two days (2026-11-19..2026-11-21): the brief caps "
                "advance picks at three days, and 2026-11-22 was not re-read this round — "
                "b1ce1334's capture prints 7 games there and is the only read of it",
                "tip times and both records are what the date page printed at read time; a record "
                "is a snapshot, not a live value",
                "11/20 rows are Emirates NBA Cup group games (game ids 0022600043-51, which is why "
                "the ids look out of sequence); the printed group and the Cup record are carried "
                "on the row so a reader can price a Cup game as what it is",
                "a game id that appears on more than one date page is excluded and recorded; none "
                "was this round (every id parsed exactly once)",
                "quarter scores for the two finished days are NOT captured by this round, so the "
                "results rows carry them blank and flagged rather than inferred",
            ]}


def build_results(day: str, names: dict[str, str]) -> dict:
    text = open(os.path.join(RAW, f"games_{day}.md"), encoding="utf-8").read()
    rows = finals_from(text, day, names)
    check_counts(day, rows)
    second: dict[str, dict] = {}
    if day == "2026-11-18":
        cross = open(os.path.join(RAW, "crossread_2026-11-18_gamelist.md"), encoding="utf-8").read()
        second = finals_from(cross, day, names)
    recaps = recap_scores(text)
    games = []
    for gid in sorted(rows):
        r = rows[gid]
        reads = [f"card on https://www.nba.com/games?date={day}"]
        if gid in second:
            s = second[gid]
            if (s["away_pts"], s["home_pts"], s["away"], s["home"]) != \
               (r["away_pts"], r["home_pts"], r["away"], r["home"]):
                raise SystemExit(f"{gid}: the two official pages disagree "
                                 f"({r['away']} {r['away_pts']}-{r['home']} {r['home_pts']} vs "
                                 f"{s['away']} {s['away_pts']}-{s['home']} {s['home_pts']}); "
                                 "both reads are withheld rather than adjudicated")
            reads.append("day list on the game's own official page "
                         "(https://www.nba.com/game/mem-vs-cle-0022600258)")
        else:
            key = (min(r["away_pts"], r["home_pts"]), max(r["away_pts"], r["home_pts"]))
            if key in recaps:
                reads.append(f"recap link printed on the same page names both scores: {recaps[key]}")
        games.append({
            "date": day, "game_id": gid, "away": r["away"], "home": r["home"],
            "away_name": r["away_name"], "home_name": r["home_name"],
            "away_pts": r["away_pts"], "home_pts": r["home_pts"], "ot": r["ot"],
            "state": r["status"], "tip_et": None, "venue": None, "city": None,
            "game_url": r["game_url"], "linescore_source": None, "gamebook": None,
            "source": f"https://www.nba.com/games?date={day}",
            "quarters_captured": False,
            "read_note": ("one official read" if len(reads) == 1 else
                          f"{len(reads)} official reads agreeing"),
            "cross_checks": {"reads": reads, "read_count": len(reads)},
        })
    return {"schema": "nba3.official_results/v1",
            "source_url": f"https://www.nba.com/games?date={day}",
            "source_label": (f"official scoreboard page for {day}, read {RETRIEVED_WINDOW} UTC by "
                             f"session {SESSION}; every final is cross-read as named per row. "
                             "Quarter scores were not read this round: the rows carry no away_q/"
                             "home_q, so scripts/results_feed.py marks each one 'quarter scores not "
                             "captured — blank, flagged' and settlement rests on the printed final "
                             "alone. No quarter value is inferred. This page prints the record "
                             "either side of the score, not the periods; the game-page day list and "
                             "the recap slugs are what a second read is available from here."),
            "retrieved_on": "2026-11-19", "retrieved_stamp": "2026-11-19T06:04Z",
            "retrieval": {"tool": "Arena fetch tool (markdown render of the official page)",
                          "window_utc": RETRIEVED_WINDOW},
            "count": len(games), "games": games,
            "day_complete": day not in PARTIAL_DAYS,
            **({"partial_day": PARTIAL_DAYS[day]} if day in PARTIAL_DAYS else {})}


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build_manifest() -> dict:
    artefacts = []
    for name in sorted(os.listdir(RAW)):
        if not name.endswith(".md"):
            continue
        p = os.path.join(RAW, name)
        artefacts.append({"file": f"data/rounds/2026-11-19/raw915/{name}",
                          "kind": "official-page transcript (verbatim excerpt)",
                          "bytes": os.path.getsize(p), "sha256": sha256(p),
                          "retrieved_utc": RETRIEVED_WINDOW,
                          "source_url": re.search(r"^Source: (\S+)", open(p, encoding="utf-8").read(),
                                                  re.M).group(1)})
    derived = [(SLATE_OUT, "derived artefact (written by scripts/roll_915d2e99.py)")]
    for day in FINAL_DAYS:
        derived.append((RESULTS_OUT[day],
                        f"derived official results capture for {day} "
                        f"(written by scripts/roll_915d2e99.py)"))
    for p, kind in derived:
        rel = os.path.relpath(p, ROOT)
        doc = json.load(open(p, encoding="utf-8"))
        artefacts.append({"file": rel, "kind": kind, "bytes": os.path.getsize(p),
                          "sha256": sha256(p),
                          "retrieved_utc": doc.get("retrieved_utc"),
                          "source_url": doc.get("source_url"),
                          "games": doc.get("count"),
                          "window": doc.get("window")})
    return {"schema": "nba3.rounds.manifest/v1", "round": "2026-11-19", "session": SESSION,
             "written_utc": RETRIEVED_WINDOW.split("..")[-1] if ".." in RETRIEVED_WINDOW
                            else RETRIEVED_WINDOW,
             "written_note": ("stamped from the read window rather than a wall clock so a re-run of "
                              "this script is byte-stable; each transcript header carries its own "
                              "retrieval line"),
             "shape_note": ("transcript manifest in the shape data/rounds/2026-11-17/manifest.json "
                            "uses: url, retrieval stamp, sha256 and bytes per artefact"),
             "artefacts": sorted(artefacts, key=lambda a: a["file"])}


def render(obj) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def everything() -> dict[str, str]:
    names = load_registry()
    blobs = {SLATE_OUT: render(build_slate(names))}
    for day in FINAL_DAYS:
        blobs[RESULTS_OUT[day]] = render(build_results(day, names))
    return blobs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if a committed artefact drifts")
    ap.add_argument("--summary", action="store_true", help="print the parse summary and exit")
    args = ap.parse_args(argv)
    blobs = everything()
    if args.summary:
        slate = json.loads(blobs[SLATE_OUT])
        print(f"slate {slate['window']['from']}..{slate['window']['to']}: {slate['count']} games")
        for day in FINAL_DAYS:
            res = json.loads(blobs[RESULTS_OUT[day]])
            two = sum(1 for g in res["games"] if g["cross_checks"]["read_count"] >= 2)
            print(f"results {day}: {res['count']} finals, {two} with a second official read, "
                  f"quarters captured: {any('away_q' in g for g in res['games'])}")
        return 0
    if args.check:
        bad = []
        for path, blob in blobs.items():
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != blob:
                bad.append(os.path.relpath(path, ROOT))
        if bad:
            print(f"DRIFT: {', '.join(bad)} do not match a re-parse of the committed transcripts; "
                  "run python3 scripts/roll_915d2e99.py and commit", file=sys.stderr)
            return 1
        man = json.loads(open(MANIFEST, encoding="utf-8").read())
        for a in man["artefacts"]:
            if a["kind"].startswith("transcript") or "transcript" in a["kind"]:
                p = os.path.join(ROOT, a["file"])
                if sha256(p) != a["sha256"]:
                    print(f"DRIFT: transcript {a['file']} changed after its sha256 was recorded",
                          file=sys.stderr)
                    return 1
        print("roll: committed artefacts re-parse byte-identical from the transcripts")
        return 0
    for path, blob in blobs.items():
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(blob)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        fh.write(render(build_manifest()))
    print(f"wrote {os.path.relpath(MANIFEST, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
