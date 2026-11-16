#!/usr/bin/env python3
"""Store an official NBA injury-report PDF as a timestamped, parse-READY capture.

Why this exists (session arena/4a59430d-nba3): the brief requires every injury PDF to be
STORED with a timestamp and consecutive reports to be diffed. The scheduled refresh already
stores the PDF bytes with the retrieval stamp and sha256 in its run manifest, but a captured
PDF was never turned into anything a parser could read, so a new report could not enter the
diff until a human transcribed it by hand.

What this tool does:
  * writes the PDF's own text layer to disk verbatim, one file per report, with a header that
    records the official URL, the retrieval stamp and the report's own printed stamp;
  * counts the official designations it can see in that text (Out / Doubtful / Questionable /
    Probable / Available and NOT YET SUBMITTED), which are unambiguous in the stream;
  * DOES NOT rebuild the report's table rows. Measured on the committed 2026-11-15 07:45 PM
    report: the PDF's text layer prints one token per line, splits player cells across page
    breaks ("… G League - Two- Way Cenac | Jr., Christopher …") and repeats its page header
    inside a team's block, so player↔team attribution from this stream is not reliable — 66
    tokens in that report could not be anchored to a row without guessing. The row table is
    therefore left to the human/tool verbatim transcription that data/live/injuries/*.md
    already uses, and this file states plainly that the rows are NOT machine-parsed here.

This keeps the pipeline honest: a PDF is never lost (it is stored with provenance the moment
the job runs), and the gap between "stored" and "parsed into the diff" is printed instead of
papered over.

Usage:
  python3 scripts/injury_pdf_to_md.py <pdf> -o <out.md> [--retrieved STAMP] [--source-url URL]
  python3 scripts/injury_pdf_to_md.py --selftest
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
STAMP_RE = re.compile(r"Injury\s+Report:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})\s*(AM|PM)",
                      re.I)


def pdf_text(path: pathlib.Path) -> str:
    """The PDF's own text layer, pages joined in order. Empty string when unreadable."""
    try:
        from pypdf import PdfReader
    except Exception:                              # environment without the extractor
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def report_stamp(text: str) -> str:
    m = STAMP_RE.search(" ".join(text.split()))
    return f"{m.group(1)} {m.group(2)} {m.group(3).upper()}" if m else ""


def designation_counts(text: str) -> dict:
    """Counts of the official designations printed in the text layer.

    A status word is counted only when it is printed as its own token, which is how the PDF
    renders the Current Status column; it is never counted inside a reason string such as
    'Right Foot Injury Management'.
    """
    toks = text.split()
    out = {s: 0 for s in STATUSES}
    out["NOT YET SUBMITTED"] = 0
    for i, t in enumerate(toks):
        if t in STATUSES and (i == 0 or toks[i - 1] not in ("-", "/")):
            out[t] += 1
    joined = " ".join(toks)
    out["NOT YET SUBMITTED"] = len(re.findall(r"\bNOT\s+YET\s+SUBMITTED\b", joined))
    out["player_rows_visible"] = len(re.findall(r"\b[A-Z][a-z]+(?:\s(?:Jr\.|Sr\.|III|II|IV))?,\s+"
                                                r"[A-Z][A-Za-z'.-]+", " ".join(toks)))
    return out


def render(pdf_name: str, text: str, source_url: str, retrieved: str, counts: dict) -> str:
    sep = chr(10)
    stamp = report_stamp(text)
    head = [
        f"<!-- injury-report PDF stored by scripts/injury_pdf_to_md.py ({pdf_name})",
        f"     official source: {source_url}",
        f"     retrieved: {retrieved}",
        f"     report stamp as printed in the document: {stamp or 'not printed'}",
        "     STATUS: captured, not machine-parsed into the consecutive-report diff. The PDF's",
        "     text layer prints one token per line and breaks player cells across page breaks,",
        "     so rows are not rebuilt from it here (see the module docstring). The designation",
        "     counts below are what the stream states unambiguously.",
        "-->",
        "",
        f"**Injury Report: {stamp or 'stamp not printed'}**",
        "",
        "| Designation | Count in the stored text layer |",
        "| --- | --- |",
    ]
    body = [f"| {k} | {v} |" for k, v in counts.items()]
    tail = ["", "---", "", "## Raw text layer, exactly as extracted", "", "```text",
            text.strip() or "(the text layer was empty — see the stored PDF bytes)", "```", ""]
    return sep.join(head + body + tail)


def selftest() -> int:
    """The parsing rules this module relies on, exercised on a fixture-shaped stream."""
    text = ("Injury\nReport:\n11/15/26\n07:45\nPM\nPage\n1\nof\n10\n"
            "Game\nDate\nGame\nTime\nMatchup\nTeam\nPlayer\nName\nCurrent\nStatus\nReason\n"
            "11/15/2026\n01:00\n(ET)\nIND@PHI\nIndiana\nPacers\nFurphy,\nJohnny\nOut\n"
            "Injury/Illness\n-\nRight\nACL\nRepair\n/\nSurgery\nHaliburton,\nTyrese\n"
            "Questionable\nInjury/Illness\n-\nLeft\nHamstring\nStrain\n")
    assert report_stamp(text) == "11/15/26 07:45 PM", report_stamp(text)
    c = designation_counts(text)
    assert c["Out"] == 1 and c["Questionable"] == 1, c
    assert c["Available"] == 0, c
    assert c["player_rows_visible"] == 2, c
    assert c["NOT YET SUBMITTED"] == 0, c
    md = render("Injury-Report_2026-11-15_07_45PM.pdf", text, "https://x/y.pdf", "T0", c)
    assert "| Out | 1 |" in md and "not machine-parsed" in md
    assert "Injury/Illness\n-\nRight" in md or "Injury/Illness" in md   # raw text preserved
    print("selftest ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--retrieved", default="")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.pdf:
        print("usage: injury_pdf_to_md.py <pdf> -o <out.md>", file=sys.stderr)
        return 2
    pdf = pathlib.Path(args.pdf)
    text = pdf_text(pdf)
    if not text:
        print(f"injury store: no text layer readable from {pdf.name} "
              "(pypdf missing or the PDF is image-only) — the PDF bytes remain the capture",
              file=sys.stderr)
        return 1
    counts = designation_counts(text)
    md = render(pdf.name, text,
                args.source_url or f"https://ak-static.cms.nba.com/referee/injury/{pdf.name}",
                args.retrieved or "unknown", counts)
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md)
    print(f"injury store: wrote {args.out or 'stdout'} — stamp {counts and report_stamp(text)!r}, "
          f"designations " + ", ".join(f"{k}={v}" for k, v in counts.items()), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
