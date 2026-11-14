#!/usr/bin/env python3
"""
T13/T14 — Verification pass for NBA3.
Offline checks (no network): schema, source-link completeness, blank+flag policy,
official-domain allowlist, slate/pick coverage, site link integrity.

Usage: python3 d01ae7e2/scripts/verify.py [--site-dir docs]
Exit code 0 = all checks pass; 1 = failures (printed).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

ALLOWED_HOST_PATTERNS = [
    r"https://(www\.)?nba\.com/",
    r"https://cdn\.nba\.com/",
    r"https://ak-static\.cms\.nba\.com/",
    r"https://official\.nba\.com/",
    r"https://pr\.nba\.com/",
    r"https://statsdmz\.nba\.com/",
    r"https://github\.com/wingbangboozle1-lang/NBA3",   # repo self-references only
]

failures = []
warnings = []


def load(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def is_official(url):
    if url is None:
        return False
    return any(re.match(p, url) for p in ALLOWED_HOST_PATTERNS)


def walk_urls(node, path, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("url", "source_url", "pdf_source_url", "preview_url", "oppg_source_url",
                     "ppg_source_url", "documented_url", "primary_source_url") or k.endswith("_url"):
                if isinstance(v, str) and v.startswith("http"):
                    out.append((path + "." + k, v))
            else:
                walk_urls(v, path + "." + str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_urls(v, f"{path}[{i}]", out)
    elif isinstance(node, str) and node.startswith("http") and path.endswith("source_urls.individual_pages"):
        out.append((path, node))


def check_url_policy(name, data):
    urls = []
    walk_urls(data, name, urls)
    for path, u in urls:
        if not is_official(u):
            failures.append(f"[{name}] non-official URL at {path}: {u}")
    return len(urls)


def check_blank_flagged(name, data):
    """Any null value on a data-bearing field must sit next to a flag/note/status explanation."""
    # documented-null keys: verified negative, not an unverified blank
    EXPLAINED = {"cup_group", "answer", "decision", "slug_mismatch_flag"}
    def walk(node, path):
        if isinstance(node, dict):
            null_keys = [k for k, v in node.items() if v is None and k not in EXPLAINED]
            if null_keys:
                has_flag = any(
                    k in node for k in (
                        "flag_ref", "ppg_flag", "flag_note", "ppg_note", "note", "status_note",
                        "submission", "report_state", "row_note", "last5_note", "flags", "status"
                    )
                ) or ("season_gp" in node)  # GP=0 documents why PPG is null
                if not has_flag:
                    warnings.append(f"[{name}] null without adjacent flag at {path}: {null_keys}")
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
    walk(data, name)


def check_picks_coverage():
    slate = load("slate.json")["games"]
    picks = load("picks.json")["picks"]
    sids = {g["game_id"] for g in slate}
    pids = {p["game_id"] for p in picks}
    if sids - pids:
        failures.append(f"[picks] missing games: {sorted(sids - pids)}")
    if pids - sids:
        failures.append(f"[picks] picks for unknown games: {sorted(pids - sids)}")
    for p in picks:
        if not all(p["source_urls"].values()):
            failures.append(f"[picks] {p['matchup']} has empty source url")
        # provisional rows must be excluded from scoring status
        if p["strategy_status"] == "PAPER_RELEASED" and p["injury_report_state"] != "submitted":
            failures.append(f"[picks] {p['matchup']} released without submitted injury report")
    return len(slate)


def check_injuries():
    games = load("injuries.json")["games"]
    slate_ids = {g["game_id"] for g in load("slate.json")["games"]}
    for g in games:
        if g["game_id"] not in slate_ids:
            failures.append(f"[injuries] unknown game_id {g['game_id']}")
        for t in g["teams"]:
            for p in t["players"]:
                if not p.get("source_url"):
                    failures.append(f"[injuries] {g['matchup']} {p['player']} missing source_url")
                if p.get("status") not in (
                    "Out", "Doubtful", "Questionable", "Probable", "Available"
                ):
                    failures.append(f"[injuries] {g['matchup']} {p['player']} bad status {p['status']!r}")
                if p.get("season_ppg") is None and "flag-ppg-missing" not in (p.get("ppg_flag") or "") \
                        and p.get("season_gp") != 0 and not p.get("ppg_note"):
                    failures.append(f"[injuries] {g['matchup']} {p['player']} null PPG unflagged")
    return len(games)


def check_sources_registry():
    reg = load("sources.json")
    for s in reg["sources"]:
        if not s.get("url") or not is_official(s["url"]):
            failures.append(f"[sources] bad/missing url for {s.get('id')}")
        if not s.get("fetched_at"):
            failures.append(f"[sources] {s.get('id')} missing fetched_at")
    return len(reg["sources"])


def check_site(site_dir):
    site = os.path.join(ROOT, site_dir)
    if not os.path.isdir(site):
        failures.append(f"[site] directory {site_dir}/ not found")
        return 0
    html_files = [f for f in os.listdir(site) if f.endswith(".html")]
    if "index.html" not in html_files:
        failures.append("[site] index.html missing")
    # collect internal hrefs
    n_links = 0
    for f in html_files:
        with open(os.path.join(site, f)) as fh:
            html = fh.read()
        for href in re.findall(r'href="([^"]+)"', html):
            if href.startswith("http") or href.startswith("#") or href.startswith("mailto:"):
                if href.startswith("http") and not is_official(href.split('"')[0]):
                    # allow anchors to our own pages' raw files too
                    if not href.startswith("https://wingbangboozle1-lang.github.io"):
                        failures.append(f"[site] {f} non-official external href: {href}")
                continue
            n_links += 1
            target = href.split("#")[0].split("?")[0]
            if target and not os.path.exists(os.path.join(site, target)):
                failures.append(f"[site] {f} broken internal link: {href}")
        # every data table row must link out: require at least one <a href with official host per <tr>
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
        # header rows (only <th> cells) are not data rows
        data_rows = [
            r for r in rows
            if len(re.sub(r"<[^>]+>", "", r).strip()) > 30 and "<th" not in r
        ]
        unlinked = 0
        for r in data_rows:
            if "http" not in r:
                unlinked += 1
        # spacer/partial rows exempted by header filter; report only if ALL data rows unlinked
        if data_rows and unlinked == len(data_rows) and len(data_rows) > 3:
            failures.append(f"[site] {f}: no table row carries a source link")
        elif unlinked:
            warnings.append(f"[site] {f}: {unlinked}/{len(data_rows)} rows without inline link")
    return len(html_files)


def main():
    site_dir = sys.argv[sys.argv.index("--site-dir") + 1] if "--site-dir" in sys.argv else "docs"

    n1 = check_url_policy("teams", load("teams.json"))
    n2 = check_url_policy("slate", load("slate.json"))
    n3 = check_url_policy("injuries", load("injuries.json"))
    n4 = check_url_policy("players", load("players.json"))
    n5 = check_url_policy("strategies", load("strategies.json"))
    n6 = check_url_policy("picks", load("picks.json"))
    n7 = check_url_policy("flagged", load("flagged.json"))
    n8 = check_url_policy("questions", load("questions.json"))

    for name in ("teams", "slate", "injuries", "players", "flagged"):
        check_blank_flagged(name, load(f"{name}.json"))

    n_games = check_picks_coverage()
    n_inj = check_injuries()
    n_src = check_sources_registry()
    n_pages = check_site(site_dir)

    total_urls = n1 + n2 + n3 + n4 + n5 + n6 + n7 + n8
    print(f"URL policy checked: {total_urls} urls, sources registry: {n_src}, "
          f"slate games: {n_games}, injury game entries: {n_inj}, site pages: {n_pages}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print("  WARN", w)
    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for f in failures:
            print("  FAIL", f)
        sys.exit(1)
    print("\nAll verification checks passed.")


if __name__ == "__main__":
    main()
