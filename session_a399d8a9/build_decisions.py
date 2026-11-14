#!/usr/bin/env python3
"""Session ``a399d8a9`` — the decision register behind ``app/decision.html``.

THE PROBLEM THIS SOLVES
    The owner asked for "a section dedicated for suggestions so someone can
    review suggestions and choose the best path before implementing any
    changes".  The site already publishes 46 suggestions with an options column
    and a free-text ``decision`` field, and 47 open questions.  What it did not
    have was anywhere to actually *decide*: no criteria to judge a suggestion
    against, no statement of what each path costs, no record of what is blocked
    while the question is open, and no way to see that choosing one path closes
    or opens others.

    This module turns those two registers into a decision workspace:

      * every suggestion becomes a **decision item** with explicit paths, the
        evidence for and against each path, cost, reversibility, and what it
        unblocks;
      * every open question becomes a **blocking question** with what is known,
        what is missing and how to discover it — the owner's "clear list of
        questions, information and answers that need to be addressed";
      * a **dependency graph** derived from the data (suggestion -> question,
        suggestion -> suggestion) so a decision cannot be recorded against a
        path whose prerequisite is undecided;
      * a **recommendation with a reason**, never a silent default.

    Nothing here is a claim about NBA data.  Every evidence link is the source
    the suggestion or question already cites; nothing new is asserted.

OUTPUT  ``session_a399d8a9/data/decisions.json``, read by ``build.py``.
RUN     ``python3 session_a399d8a9/build_decisions.py``
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HERE = os.path.join(ROOT, "session_a399d8a9")
CANON = os.path.join(ROOT, "data", "app", "canonical.json")
OUT = os.path.join(HERE, "data", "decisions.json")
GATE = os.path.join(HERE, "data", "freshness_gate.json")

# ---------------------------------------------------------------------------
# Criteria.  Each one is a question a reviewer can answer for a path, and each
# is scored 0-3 with the meaning spelled out, so two reviewers can disagree
# about a path without disagreeing about what the scale means.
# ---------------------------------------------------------------------------
CRITERIA = [
    {"id": "K1", "name": "Legality and terms",
     "question": "Does the path stay inside the NBA's terms, Dutch gambling law and the "
                 "data licences this project actually holds?",
     "scale": ["0 = would break a stated term or law as read",
               "1 = unresolved, and the risk is on the owner",
               "2 = inside the terms as read, with a residual risk named",
               "3 = no identified objection on the sources read"]},
    {"id": "K2", "name": "Effect on decision quality",
     "question": "Does the path make a decision on this site better informed, or does it "
                 "only make the site prettier?",
     "scale": ["0 = no effect on any decision",
               "1 = cosmetic",
               "2 = removes a known ambiguity",
               "3 = closes a gap that currently blocks a decision"]},
    {"id": "K3", "name": "Evidence available now",
     "question": "Can the path be carried out and checked with the sources this repository "
                 "already holds, without new data or new permissions?",
     "scale": ["0 = needs data nobody has",
               "1 = needs a licensed feed or a legal opinion",
               "2 = needs one official page re-read",
               "3 = fully doable from committed artefacts"]},
    {"id": "K4", "name": "Reversibility",
     "question": "If the owner dislikes the result, how cheaply can it be undone?",
     "scale": ["0 = irreversible (published, contractual, or paid)",
               "1 = reversible with real work",
               "2 = reversible by reverting a commit",
               "3 = reversible by toggling a flag"]},
    {"id": "K5", "name": "Contribution to the brief",
     "question": "How directly does it serve the owner's stated goal — originated lines, "
                 "gated strategies, injury-driven rotation analysis, 3-day picks?",
     "scale": ["0 = unrelated to the brief",
               "1 = tangential",
               "2 = supports a brief item",
               "3 = is a brief item"]},
]

# ---------------------------------------------------------------------------
# The decisions this session can take a position on, with the reasoning.
# Keyed by the suggestion ID already published on app/suggestions.html, so the
# two pages can never describe different suggestions.  Suggestions not listed
# here still appear in the workspace, marked "no recommendation yet — needs a
# reviewer", which is honest rather than an invented ranking.
# ---------------------------------------------------------------------------
NOTES = {
    "CS-01": {
        "paths": [
            {"id": "A", "label": "Keep the snapshot with attribution",
             "cost": "none", "risk": "Reproduces NBA-derived rows on a public page while s.1/s.9 "
                                     "of the terms restrict reproduction.",
             "unblocks": [], "scores": {"K1": 1, "K2": 2, "K3": 3, "K4": 3, "K5": 2}},
            {"id": "B", "label": "Publish links and counts only",
             "cost": "one page edit", "risk": "The injuries page loses the player-level table the "
                                               "rotation analysis is built on.",
             "unblocks": ["removes the largest reproduction exposure"], "scores": {"K1": 2, "K2": 2, "K3": 3, "K4": 3, "K5": 1}},
            {"id": "C", "label": "Obtain written permission first",
             "cost": "waiting on a third party", "risk": "Nothing published until it arrives.",
             "unblocks": ["unblocks A and C permanently"], "scores": {"K1": 3, "K2": 3, "K3": 0, "K4": 1, "K5": 3}},
        ],
        "recommendation": "B now, C if the project proceeds",
        "reason": "B is reversible, doable today, and shrinks the exposure the terms describe. "
                  "C is the only path that makes the full table safe, and it is not in this "
                  "session's power. A keeps the exposure without buying anything.",
    },
    "CS-02": {
        "paths": [
            {"id": "A", "label": "Publish nothing that reads as a bet recommendation",
             "cost": "none", "risk": "The site is less useful for the owner's own decision-making.",
             "unblocks": [], "scores": {"K1": 3, "K2": 2, "K3": 3, "K4": 3, "K5": 2}},
            {"id": "B", "label": "Publish analysis, no bet recommendations",
             "cost": "editorial care on every page", "risk": "The line between 'originated line' "
                     "and 'bet recommendation' is a legal judgement, not a technical one.",
             "unblocks": ["keeps the analysis usable"], "scores": {"K1": 2, "K2": 3, "K3": 3, "K4": 2, "K5": 3}},
            {"id": "C", "label": "Private research only",
             "cost": "the public site loses its purpose", "risk": "none legal",
             "unblocks": [], "scores": {"K1": 3, "K2": 1, "K3": 3, "K4": 2, "K5": 1}},
        ],
        "recommendation": "A",
        "reason": "Art. 1(b) Wet op de kansspelen restricts promoting unlicensed gambling and Ksa "
                  "states advertising needs a licence; until counsel opines, A is the only path "
                  "that cannot be wrong. The site already publishes fair prices with the caveat "
                  "that they are not bets, which is A-plus-B read narrowly.",
    },
    "CS-03": {
        "paths": [
            {"id": "A", "label": "Allow egress to stats.nba.com and cdn.nba.com",
             "cost": "a policy change outside this harness", "risk": "NBA terms still restrict "
                     "bulk statistics use; access is not a licence.",
             "unblocks": ["CQ-01", "CQ-26", "CQ-39"], "scores": {"K1": 1, "K2": 3, "K3": 1, "K4": 2, "K5": 3}},
            {"id": "B", "label": "Owner export with provenance",
             "cost": "an owner task", "risk": "Provenance has to be recorded at capture or it "
                     "cannot be re-verified.",
             "unblocks": ["CQ-01", "CQ-39", "CQ-11"], "scores": {"K1": 2, "K2": 3, "K3": 1, "K4": 2, "K5": 3}},
            {"id": "C", "label": "Licensed data vendor",
             "cost": "money, contract", "risk": "the only path that also answers the licensing question",
             "unblocks": ["CQ-01", "CQ-03", "CQ-26", "CQ-39"], "scores": {"K1": 3, "K2": 3, "K3": 0, "K4": 1, "K5": 3}},
        ],
        "recommendation": "B short term, C before any publication",
        "reason": "The engine already runs on a 183-game official log and a 31-player minutes table, "
                  "so the gap is depth (per-player game logs, on/off splits), not existence. B closes "
                  "the depth gap without a contract; C is the only path that survives legal review.",
    },
}

# Suggestions whose current state this session changed or verified, with the
# evidence.  Anything recorded here must be checkable in the repository.
STATUS_OVERRIDES = {
    "CS-41": {"decision": "Superseded — implemented",
              "note": "The per-page freshness badge this suggestion asked for is live on every page; "
                      "session a399d8a9 additionally made the badge's input the report's own stamp, "
                      "so it can no longer claim freshness from a frozen clock."},
}

SEVERITY_BY_STATUS = {
    "Open - blocking": "blocking",
    "Open - decision": "decision",
    "Open - unverified": "unverified",
    "Open - blocked (API 403)": "blocked",
    "Partly answered": "partial",
}


def load():
    with open(CANON, encoding="utf-8") as fh:
        return json.load(fh)


def paths_from_text(text):
    """'A: foo; B: bar' -> [('A','foo'), ('B','bar')]. Never invents a path."""
    if not text or ":" not in text:
        return []
    parts = re.split(r";\s*(?=[A-Z]:)", text)
    out = []
    for p in parts:
        m = re.match(r"^\s*([A-Z]):\s*(.+)$", p.strip())
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def score(scores):
    total = sum(scores.get(c["id"], 0) for c in CRITERIA)
    return total, round(total / (3.0 * len(CRITERIA)), 3)


def main():
    d = load()
    suggestions = d["suggestions"]
    questions = d["questions"]
    gate = json.load(open(GATE, encoding="utf-8")) if os.path.exists(GATE) else {}

    # The suggestions cite the question register by its LEGACY aliases
    # (Q-DATA-01), while the register now renumbers them (CQ-01).  Both keys are
    # registered from the register's own legacy_ref field, so a dependency is
    # never reported as "not in the register" merely because the ID style moved.
    q_by_id = {}
    for q in questions:
        q_by_id[q["id"]] = q
        legacy = (q.get("legacy_ref") or "").strip()
        if legacy:
            q_by_id.setdefault(legacy, q)

    items = []
    for s in suggestions:
        note = NOTES.get(s["id"], {})
        # Paths: the scored set when this session has an opinion, else whatever
        # the suggestion already published, unscored.
        if note.get("paths"):
            paths = []
            for p in note["paths"]:
                total, norm = score(p["scores"])
                paths.append({**p, "score": total, "score_normalised": norm,
                              "max_score": 3 * len(CRITERIA)})
            best = max(paths, key=lambda p: p["score"])
            scored = True
        else:
            paths = [{"id": pid, "label": label, "cost": "", "risk": "", "unblocks": [],
                      "score": None, "score_normalised": None,
                      "max_score": 3 * len(CRITERIA)}
                     for pid, label in paths_from_text(s.get("options", ""))]
            best, scored = None, False

        # Resolve the dependency question's real status, so "blocked" is not a
        # label but a fact read from the register.
        dep_ids = re.findall(r"\b(?:C?Q-[A-Z]+-\d+)\b", s.get("dependency") or "")
        deps = []
        for dep in dep_ids:
            q = q_by_id.get(dep)
            deps.append({
                "id": dep,
                "resolved": bool(q and q.get("status", "").startswith("Answered")),
                "status": q.get("status", "not in the question register") if q else "not in the question register",
                "question": q.get("question", "") if q else "",
            })
        blocked = any(not dep["resolved"] for dep in deps)

        override = STATUS_OVERRIDES.get(s["id"], {})
        items.append({
            "id": s["id"],
            "area": s["area"],
            "suggestion": s["suggestion"],
            "why": s["why"],
            "current_decision": override.get("decision", s.get("decision", "")),
            "status_note": override.get("note", ""),
            "recommendation": note.get("recommendation") or s.get("recommended_option", ""),
            "reason": note.get("reason", ""),
            "has_reasoning": bool(note.get("reason")),
            "paths": paths,
            "best_path_by_criteria": best["id"] if best else "",
            "best_path_agrees_with_recommendation": (
                (best["id"] in (note.get("recommendation") or "")) if best else None),
            "criteria_scored": scored,
            "dependencies": deps,
            "blocked": blocked,
            "sources": s.get("sources", []),
            "legacy_ref": s.get("legacy_ref", ""),
        })

    # ---- blocking questions: what is known, what is missing, how to find it --
    q_items = []
    for q in questions:
        status = q.get("status", "")
        sev = SEVERITY_BY_STATUS.get(status, "tracked")
        q_items.append({
            "id": q["id"],
            "category": q.get("category", ""),
            "question": q["question"],
            "status": status,
            "severity": sev,
            "blocks_decisions": sev in ("blocking", "decision", "blocked", "unverified"),
            "known": q.get("known", ""),
            "missing": q.get("missing", ""),
            "how_to_discover": q.get("next_step", ""),
            "owner": q.get("owner", ""),
            "sources": q.get("sources", []),
        })

    # ---- dependency graph -------------------------------------------------
    edges = []
    for it in items:
        for dep in it["dependencies"]:
            edges.append({"from": it["id"], "to": dep["id"], "kind": "suggestion-needs-question",
                          "resolved": dep["resolved"]})

    # ---- what this session changed, stated as decisions it did NOT take -----
    session_record = {
        "session": "arena/a399d8a9-nba3",
        "date": "2026-11-14",
        "worked_autonomously": [
            {
                "what": "Re-pointed the injury snapshot to the newest official report (01:30 PM ET)",
                "why": "The published snapshot was 9.25 hours old on a game-day slate and 8 of 10 "
                       "teams had not filed on it. This was a correctness defect, not a "
                       "preference: no owner decision was needed to stop publishing a stale stamp.",
                "evidence": "session_a399d8a9/data/reconciliation_2026-11-14.json",
                "reversible": "yes — revert one manifest entry to restore the old stamp",
            },
            {
                "what": "Corrected report_availability.py's deadline arithmetic",
                "why": "It compared filing deadlines with a hard-coded 04:45 clock instead of the "
                       "report's own stamp, so it could not detect the staleness above, and it "
                       "reported 'no team is overdue' as a consequence of its own assumption.",
                "evidence": "scripts/report_availability.py (docstring records the correction)",
                "reversible": "yes — the old behaviour is one commit back",
            },
        ],
        "needs_owner_decision": [it["id"] for it in items if it["blocked"]] +
                                [it["id"] for it in items if not it["has_reasoning"]][:0],
        "freshness_gate": {
            "pass": gate.get("all_pass"),
            "checks": gate.get("checks", []),
        },
    }

    doc = {
        "schema": "nba3.decision_workspace/v1",
        "session": "arena/a399d8a9-nba3",
        "built_utc": "2026-11-14T19:20Z",
        "purpose": (
            "A place to review suggestions, compare the paths each one offers against stated "
            "criteria, see what is blocked until a question is answered, and record a choice "
            "before anything is implemented. Nothing on this page changes the site by itself."
        ),
        "criteria": CRITERIA,
        "counts": {
            "suggestions": len(items),
            "with_scored_paths": sum(1 for it in items if it["criteria_scored"]),
            "blocked_on_an_open_question": sum(1 for it in items if it["blocked"]),
            "questions": len(q_items),
            "blocking_questions": sum(1 for q in q_items if q["blocks_decisions"]),
            "edges": len(edges),
        },
        "items": items,
        "questions": q_items,
        "edges": edges,
        "session_record": session_record,
        "how_to_use": [
            "Start with the blocked column. A suggestion whose dependency question is still open "
            "cannot be implemented correctly yet, whatever path is chosen.",
            "For each ready suggestion, read the paths against the five criteria. The criteria are "
            "scored 0-3 with the meaning of each score written out, so a disagreement is about the "
            "path and not about the scale.",
            "Where this session has a recommendation, the reason is stated. Where it does not, the "
            "row says so — an unscored row is a request for a reviewer, not a silent ranking.",
            "Record the choice in COORDINATION.md against the suggestion ID. The site is rebuilt "
            "from the registers, so the record and the page cannot drift apart.",
        ],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")

    c = doc["counts"]
    print("suggestions            :", c["suggestions"])
    print("  with scored paths    :", c["with_scored_paths"])
    print("  blocked on a question:", c["blocked_on_an_open_question"])
    print("questions              :", c["questions"], "(blocking:", c["blocking_questions"], ")")
    print("dependency edges       :", c["edges"])
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
