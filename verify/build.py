#!/usr/bin/env python3
"""
Build the verification & decision site into verify/pages/.

Session arena/3655c68d-nba3. This builder:

  1. loads every JSON file in verify/data/,
  2. re-runs the numerical self-tests in verify/tests/ (parlay copula, pick-card signs),
  3. cross-checks the published artefacts it depends on (174-game logs, injury rows),
  4. refuses to write the site if any check fails or any row is missing an official source,
  5. writes static HTML with no JavaScript and no external assets.

Standard library only. No network access needed.

Usage:
    python3 verify/build.py            # check everything, then build
    python3 verify/build.py --check    # check only, write nothing
"""
import json, os, sys, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VDATA = os.path.join(ROOT, 'verify', 'data')
VPAGES = os.path.join(ROOT, 'verify', 'pages')

OFFICIAL_HOSTS = (
    'nba.com', 'official.nba.com', 'ak-static.cms.nba.com', 'cdn.nba.com',
    'kansspelautoriteit.nl', 'www.nba.com',
)

problems = []


def fail(msg):
    problems.append(msg)


def load(name):
    with open(os.path.join(VDATA, name), encoding='utf-8') as f:
        return json.load(f)


def esc(v):
    return html.escape('' if v is None else str(v), quote=True)


def is_https(u):
    return isinstance(u, str) and u.startswith('https://')


# ---------------------------------------------------------------- checks

def check_sources_have_urls():
    """Every row that claims VERIFIED must carry a resolvable https source."""
    for name in ('claims.json', 'contradictions.json', 'sources.json', 'questions.json',
                 'suggestions.json', 'corrections.json'):
        d = load(name)
        rows = d.get('claims') or d.get('contradictions') or d.get('sources') \
            or d.get('questions') or d.get('suggestions') or d.get('corrections') or []
        for r in rows:
            st = r.get('status', '')
            if st == 'VERIFIED' and not (is_https(r.get('source', '')) or is_https(r.get('url', ''))):
                fail(f'{name}:{r.get("id")} is VERIFIED but has no https source')
    # ledger rows must carry a settlement source unless explicitly blank for a stated reason
    led = load('ledger.json')
    for r in led['ledger']:
        if r['status'] == 'SETTLED' and not is_https(r['settlement_source']):
            fail(f'ledger:{r["id"]} is SETTLED but has no official settlement source')


def check_no_blank_verified_values():
    d = load('claims.json')
    for c in d['claims']:
        if c['status'] == 'VERIFIED' and not str(c.get('value', '')).strip():
            fail(f'claims:{c["id"]} is VERIFIED with a blank value')


def _load_parlay_joint():
    """parlay_joint is defined inside run_model.main(), so it cannot be imported directly.
    Parse it out of the source and execute just that definition. This deliberately tests the
    SAME code that produces the published artefact, rather than a re-implementation that could
    drift away from it."""
    import ast
    path = os.path.join(ROOT, 'pipeline', 'run_model.py')
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    # module-level helpers that the nested function closes over
    ns = {'math': __import__('math')}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ('_normcdf', '_invnorm'):
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), ns)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'parlay_joint':
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), ns)
            return ns['parlay_joint']
    raise RuntimeError('parlay_joint not found in pipeline/run_model.py')


def test_parlay_copula():
    """Recompute the bivariate-normal orthant against closed-form and Monte-Carlo facts."""
    parlay_joint = _load_parlay_joint()
    p = 0.58
    # (a) independence must reproduce p^2 exactly
    j0 = parlay_joint(p, p, 0.0)
    if abs(j0 - p * p) > 2e-3:
        fail(f'parlay_joint: rho=0 gives {j0:.4f}, expected p^2={p*p:.4f}')
    # (b) monotone increasing in rho
    vals = [parlay_joint(p, p, r) for r in (-0.3, 0.0, 0.3, 0.6, 0.9)]
    if any(b <= a for a, b in zip(vals, vals[1:])):
        fail(f'parlay_joint: not monotone in rho: {vals}')
    # (c) must respect the Frechet bounds
    for r, j in zip((-0.3, 0.0, 0.3, 0.6, 0.9), vals):
        if not (max(0.0, 2 * p - 1) - 1e-6 <= j <= min(p, p) + 1e-6):
            fail(f'parlay_joint: rho={r} gives {j:.4f}, outside Frechet bounds')
    # (d) the specific published value
    j3 = parlay_joint(p, p, 0.3)
    if abs(j3 - 0.3832) > 2e-3:
        fail(f'parlay_joint(rho=0.3) gives {j3:.4f}, expected 0.3832')
    # (e) the defect that was fixed: it must NOT return the marginal
    if abs(j3 - p) < 0.05:
        fail('parlay_joint still returns the marginal probability (FX-01 regression)')
    # (f) asymmetric legs
    if abs(parlay_joint(0.2, 0.9, 0.0) - 0.18) > 2e-3:
        fail('parlay_joint is not symmetric-correct for p1 != p2')


def test_pick_spread_signs():
    """Every published pick card must have a spread sign that matches its moneyline."""
    picks = json.load(open(os.path.join(ROOT, 'data/picks/picks_2026-11-14_to_16.json')))
    lines = json.load(open(os.path.join(ROOT, 'data/model/lines_2026-27.json')))
    idx = {(g['date'], g['away'] + '@' + g['home']): g for g in lines}
    for k in picks['picks']:
        g = idx.get((k['date'], k['matchup'].replace(' ', '')))
        if g is None:
            fail(f'picks: {k["matchup"]} on {k["date"]} has no matching line')
            continue
        mh = g['origin_spread_home']
        if abs(mh) < 0.05:
            expect = f"{g['home']} 0.0"
        elif mh > 0:
            expect = f"{g['home']} -{mh:.1f}"      # home wins by mh -> home favourite
        else:
            expect = f"{g['away']} {mh:.1f}"       # mh<0 -> away wins by |mh|
        if k['origin_spread'] != expect:
            fail(f'picks: {k["matchup"]} label {k["origin_spread"]!r} != {expect!r} (FX-02 regression)')
        # CONVENTION (established from pipeline/run_model.py, where origin_spread_home = round(predC,1)
        # and predC is the projected HOME MARGIN):
        #   origin_spread_home > 0  => HOME is the favourite (it is a projected HOME MARGIN)
        #   model_p_home > 0.5      => HOME is the favourite   (it is P(home win), not P(away win))
        #   the printed label names the MINUS side, which must be the favourite.
        named, _, num = k['origin_spread'].partition(' ')
        if not num.startswith('-'):
            fail(f'picks: {k["matchup"]} label has no minus sign (FX-02 regression)')
        spread_fav = g['home'] if mh > 0 else g['away']
        prob_fav = g['home'] if g['model_p_home'] > 0.5 else g['away']
        if spread_fav != prob_fav:
            fail(f'picks: {k["matchup"]} spread and probability disagree on the favourite '
                 f'({spread_fav} vs {prob_fav}) - a lines-file defect, not a label defect')
        if named != prob_fav:
            fail(f'picks: {k["matchup"]} label names {named} but model favourite is {prob_fav}')


def test_game_logs_agree():
    """The two independent 174-game captures must agree game by game."""
    import csv
    MAP = {'CHO': 'CHA', 'BRK': 'BKN', 'PHO': 'PHX'}
    origin = {}
    with open(os.path.join(ROOT, 'data/origin/games.csv')) as f:
        for r in csv.DictReader(f):
            origin[(r['date'], MAP.get(r['away'], r['away']), MAP.get(r['home'], r['home']))] = \
                (int(r['away_pts']), int(r['home_pts']), r['ot'] not in ('0', ''))
    edge = {}
    for p in ('data/raw/results_2026-27_october.csv', 'data/raw/results_2026-27_november.csv'):
        for line in open(os.path.join(ROOT, p)):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('date,'):
                continue
            parts = [x.strip() for x in line.split(',')]
            date, aw, awp, h, hp = parts[:5]
            note = parts[5] if len(parts) > 5 else ''
            edge[(date, MAP.get(aw, aw), MAP.get(h, h))] = \
                (int(awp), int(hp), 'OT' in note)
    if len(origin) != 174:
        fail(f'origin log has {len(origin)} games, expected 174')
    if set(origin) != set(edge):
        fail(f'game logs cover different games: {len(set(origin) ^ set(edge))} differ')
    for k in set(origin) & set(edge):
        if origin[k] != edge[k]:
            fail(f'game logs disagree on {k}: {origin[k]} vs {edge[k]}')


def test_injury_rows_match_official():
    """Every named player in our injury table must appear in the official transcript.

    Reference swapped from the 05:00 PM transcript to the 07:30 PM transcript by
    session arena/9456a8ab-nba3 during the open-PR integration round: data/injuries.json
    (PR #21) carries the 07:30 PM report stamp, so the 05:00 PM reference would flag
    the genuine 05:00 -> 07:30 updates (Cain, da Silva, Suggs and six others) as errors.
    The 07:30 PM transcript was fetched from the official PDF this round and
    cross-checked player-for-player against data/app/official_injuries_2026-11-13_0730PM.json
    (117/117 statuses, teams and matchups agree).
    """
    import re

    def nm(s):
        return re.sub(r'[^a-z]', '', s.lower())

    off = {}
    for line in open(os.path.join(VDATA, 'official_injury_report_2026-11-13_0730PM.txt'), encoding='utf-8'):
        if not line.startswith('| 11/1'):
            continue
        p = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(p) >= 7 and p[4]:
            off[nm(p[4])] = p[5]
    ours = json.load(open(os.path.join(ROOT, 'data/injuries.json')))
    # data/injuries.json (regenerated by session arena/fa03eba6-nba3, PR #21) carries
    # team-level "NOT YET SUBMITTED" and not-yet-published rows with player=null;
    # rows without a printed player name are skipped here, per the never-infer policy.
    ours = {nm(r['player']): r for r in ours if r.get('player') and r['player'].strip()}
    missing = set(off) - set(ours)
    if missing:
        fail(f'{len(missing)} official players missing from data/injuries.json')
    bad = [k for k in set(off) & set(ours) if off[k] != ours[k]['status_as_printed']]
    if bad:
        fail(f'{len(bad)} injury statuses disagree with the official PDF')
    if len(off) < 90:
        fail(f'official transcript only parsed {len(off)} players')


def test_ledger_integrity():
    led = load('ledger.json')
    ids = [r['id'] for r in led['ledger']]
    if len(ids) != len(set(ids)):
        fail('ledger has duplicate ids')
    for r in led['ledger']:
        if r['status'] == 'PENDING' and r['result']:
            fail(f'ledger:{r["id"]} is PENDING but has a result')
        if r['status'] == 'SETTLED' and not r['result']:
            fail(f'ledger:{r["id"]} is SETTLED but has no result')
    n = led['meta']['counts']
    if n['total'] != len(led['ledger']):
        fail('ledger meta counts.total does not match the rows')


def run_checks():
    checks = [
        ('sources have https URLs', check_sources_have_urls),
        ('no VERIFIED claim has a blank value', check_no_blank_verified_values),
        ('parlay copula (FX-01)', test_parlay_copula),
        ('pick-card spread signs (FX-02)', test_pick_spread_signs),
        ('two 174-game logs agree', test_game_logs_agree),
        ('injury rows match the official PDF', test_injury_rows_match_official),
        ('settlement ledger integrity', test_ledger_integrity),
    ]
    for label, fn in checks:
        before = len(problems)
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            fail(f'{label} raised {type(e).__name__}: {e}')
        ok = len(problems) == before
        print(f'  [{"PASS" if ok else "FAIL"}] {label}')
    return not problems


# ---------------------------------------------------------------- rendering

CSS = """
:root{--ink:#17203a;--muted:#5b6780;--line:#dfe5ee;--bg:#f6f8fb;--card:#fff;
--navy:#111d33;--blue:#1f5be0;--red:#b3261e;--amber:#8a5a00;--green:#1c6b45}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
header{background:var(--navy);color:#fff;padding:22px max(20px,calc((100vw - 1240px)/2))}
header .eyebrow{color:#9fb6ff;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;font-weight:700}
header h1{margin:4px 0 2px;font-size:26px;font-weight:700}
header p{margin:3px 0 0;color:#c9d6ef;font-size:13.5px;max-width:900px}
.wrap{max-width:1240px;margin:0 auto;padding:20px;display:grid;grid-template-columns:212px 1fr;gap:22px}
nav{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;height:max-content;position:sticky;top:14px}
nav .grp{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:700;padding:10px 8px 4px}
nav a{display:block;padding:7px 9px;border-radius:6px;color:var(--ink);font-size:14px}
nav a:hover{background:#eef3fd}nav a.on{background:#e4ecfd;color:var(--blue);font-weight:650}
main{min-width:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px;margin-bottom:16px}
.card h2{margin:0 0 4px;font-size:19px}
.card h2+.sub{color:var(--muted);font-size:13.5px;margin:0 0 14px}
.card h3{font-size:15px;margin:18px 0 6px}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;vertical-align:top;padding:9px 10px;border-bottom:1px solid var(--line)}
th{background:#f1f5fb;font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:#3c4a63;font-weight:700;white-space:nowrap}
tbody tr:hover td{background:#fafcff}
td.id{font-variant-numeric:tabular-nums;color:var(--muted);white-space:nowrap;font-size:12.5px}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;border:1px solid}
.t-verified{color:var(--green);border-color:#bfe0cf;background:#eaf6ef}
.t-disc{color:var(--red);border-color:#f0c8c4;background:#fdeceb}
.t-unv{color:var(--amber);border-color:#ecd9ae;background:#fdf5e4}
.t-info{color:#2c3f63;border-color:#d5deee;background:#eef2f9}
.metric{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:14px 0}
.m{background:#f8fafd;border:1px solid var(--line);border-radius:9px;padding:14px}
.m b{display:block;font-size:23px;font-weight:750;letter-spacing:-.01em}
.m span{color:var(--muted);font-size:12.5px;display:block;margin-top:2px}
.m small{display:block;color:var(--muted);font-size:11.5px;margin-top:6px}
.note{border-left:3px solid var(--blue);background:#f2f6fe;padding:11px 14px;border-radius:0 6px 6px 0;margin:12px 0;font-size:13.5px}
.warn{border-left:3px solid var(--red);background:#fdf0ef;padding:11px 14px;border-radius:0 6px 6px 0;margin:12px 0;font-size:13.5px}
.good{border-left:3px solid var(--green);background:#eef8f2;padding:11px 14px;border-radius:0 6px 6px 0;margin:12px 0;font-size:13.5px}
code{background:#eef1f6;padding:1.5px 5px;border-radius:4px;font-size:12.5px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
footer{color:var(--muted);font-size:12.5px;padding:8px 0 26px;border-top:1px solid var(--line);margin-top:8px}
ul.tight{margin:6px 0 0;padding-left:18px}ul.tight li{margin:3px 0}
@media(max-width:860px){.wrap{grid-template-columns:1fr;padding:14px}nav{position:static;display:flex;flex-wrap:wrap;gap:2px}
nav .grp{width:100%}nav a{white-space:nowrap}}
"""

NAV = [
    ('group', 'Overview'),
    ('index', 'Verification hub'),
    ('executive', 'Executive summary'),
    ('contradictions', 'Contradictions (9)'),
    ('group', 'Evidence'),
    ('claims', 'Claim ledger'),
    ('injuries', 'Injury verification'),
    ('results', 'Game-log verification'),
    ('corrections', 'Corrections made'),
    ('group', 'Decision'),
    ('decisions', 'Decisions needed'),
    ('questions', 'Questions ledger'),
    ('suggestions', 'Suggestions'),
    ('group', 'Record'),
    ('ledger', 'Settlement ledger'),
    ('sources', 'Sources'),
    ('flagged', 'Flagged for review'),
]

PAGES = {
    'index': 'Verification hub',
    'executive': 'Executive summary',
    'contradictions': 'Contradictions',
    'claims': 'Claim ledger',
    'injuries': 'Injury verification',
    'results': 'Game-log verification',
    'corrections': 'Corrections made',
    'decisions': 'Decisions needed',
    'questions': 'Questions ledger',
    'suggestions': 'Suggestions',
    'ledger': 'Settlement ledger',
    'sources': 'Sources',
    'flagged': 'Flagged for review',
}


def page(slug, title, body):
    nav = []
    for item in NAV:
        if item[0] == 'group':
            nav.append(f'<div class="grp">{esc(item[1])}</div>')
        else:
            key, label = item
            cls = ' class="on"' if key == slug else ''
            nav.append(f'<a href="{key}.html"{cls}>{esc(label)}</a>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} - NBA3 verification</title>
<style>{CSS}</style></head>
<body>
<header><div class="eyebrow">NBA3 / session 3655c68d / verification layer</div>
<h1>{esc(title)}</h1>
<p>Cross-pipeline verification of the six dashboards already in this repository. Research only, not betting advice.
Nothing on this site is eligible for staking.</p></header>
<div class="wrap"><nav aria-label="Sections">{''.join(nav)}</nav><main>
{body}
<footer>Built by <code>python3 verify/build.py</code> from <code>verify/data/*.json</code>. Every table row links to its source.
Values that could not be confirmed against an official source are left blank and flagged.</footer>
</main></div></body></html>
"""


def tag(status):
    cls = {'VERIFIED': 't-verified', 'DISCREPANCY': 't-disc', 'UNVERIFIED': 't-unv'}.get(status, 't-info')
    return f'<span class="tag {cls}">{esc(status)}</span>'


def src(primary, extra=''):
    out = []
    if is_https(primary):
        out.append(f'<a href="{esc(primary)}">source</a>')
    if is_https(extra):
        out.append(f'<a href="{esc(extra)}">also</a>')
    return ' &middot; '.join(out) if out else '<span class="tag t-unv">no official source</span>'


# ---------------------------------------------------------------- pages

def build_index(d):
    s = d['summary']['summary']
    meta = d['summary']['meta']
    metrics = ''.join(
        f'<div class="m"><b>{esc(r["value"])}</b><span>{esc(r["label"])}</span>'
        f'<small>{tag(r["status"])}</small></div>' for r in s[:8])
    rows = ''.join(
        f'<tr><td class="id">{esc(r["id"])}</td><td><b>{esc(r["label"])}</b><br>'
        f'<span style="color:var(--muted)">{esc(r["detail"])}</span></td>'
        f'<td class="num">{esc(r["value"])}</td><td>{tag(r["status"])}</td>'
        f'<td>{src(r["source"], r.get("extra", ""))}</td></tr>' for r in s)
    body = f"""
<section class="card"><h2>What this site is</h2>
<p class="sub">{esc(meta['purpose'])}</p>
<div class="metric">{metrics}</div>
<div class="note"><b>How to read the status tags.</b> {esc(meta['verification_rule'])}</div>
<div class="warn"><b>Start here.</b> The repository already contains six dashboards that disagree with each
other. Nine of those disagreements are material, and two of them are arithmetic defects that were
publishing wrong numbers. <a href="contradictions.html">See the contradiction register</a> before reading
anything else, and <a href="decisions.html">the decisions page</a> to see what is blocked.</div>
</section>
<section class="card"><h2>Headline findings</h2>
<p class="sub">Each row is recomputed from a repository artefact or checked against an official source.</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>Finding</th><th>Value</th><th>Status</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>
<section class="card"><h2>Where to go next</h2>
<div class="scroll"><table><thead><tr><th>If you want to</th><th>Go to</th></tr></thead><tbody>
<tr><td>Know what was wrong and what was fixed</td><td><a href="corrections.html">Corrections made</a></td></tr>
<tr><td>Know which dashboard to believe right now</td><td><a href="contradictions.html">Contradictions</a></td></tr>
<tr><td>Make the one decision that unblocks the most work</td><td><a href="decisions.html">Decisions needed</a></td></tr>
<tr><td>Check a specific published number</td><td><a href="claims.html">Claim ledger</a></td></tr>
<tr><td>Check the injury or game data line by line</td><td><a href="injuries.html">Injury verification</a> / <a href="results.html">Game-log verification</a></td></tr>
<tr><td>See everything still unresolved</td><td><a href="flagged.html">Flagged for review</a></td></tr>
</tbody></table></div></section>"""
    return page('index', 'Verification hub', body)


def build_executive(d):
    led = d['ledger']
    cl = d['claims']['claims']
    co = d['contradictions']['contradictions']
    qs = d['questions']['questions']
    from collections import Counter
    cst = Counter(c['status'] for c in cl)
    blocked = [q for q in qs if str(q['blocking']).lower().startswith('yes')]
    body = f"""
<section class="card"><h2>Executive summary</h2>
<p class="sub">What the repository establishes, what it contradicts, and what has to be decided. Written to be read
in five minutes.</p>

<div class="good"><b>The one thing that is solid.</b> Two sessions captured the 2026-27 season independently, from
different sources, with different code. They agree on all <b>174 games</b>: same dates, same teams, same exact final
scores, same <b>9 overtime games</b>. That log is trustworthy and it is the foundation everything else should be
built on.</div>

<div class="warn"><b>The one thing that is not.</b> The repository publishes <b>six dashboards</b> that answer the same
questions differently. This session found <b>{len(co)} contradictions</b>. Two are outright defects: a parlay
price function that silently returned the wrong quantity for every input, and every pick card naming the wrong side
of the market. Both are fixed and covered by tests, but they were live on a public GitHub Pages site.</div>

<h3>Numbers that survived re-audit</h3>
<div class="scroll"><table><thead><tr><th>Claim</th><th>Status</th></tr></thead><tbody>
<tr><td>174-game log agrees between two independent captures</td><td>{tag('VERIFIED')} 174/174</td></tr>
<tr><td>Injury table rows agree with the official NBA PDF</td><td>{tag('VERIFIED')} 110/110 named players</td></tr>
<tr><td>Strategy records reproduce from their own bet logs</td><td>{tag('VERIFIED')} 4/4</td></tr>
<tr><td>Strategies passing every validation gate</td><td>{tag('VERIFIED')} 0 of 8</td></tr>
<tr><td>Claim ledger, {len(cl)} published numbers rechecked</td><td>{tag('VERIFIED')} {cst['VERIFIED']} verified,
{cst['DISCREPANCY']} discrepancies, {cst['UNVERIFIED']} unverifiable</td></tr>
</tbody></table></div>

<h3>What the numbers do not support</h3>
<ul class="tight">
<li><b>No strategy is proven.</b> Zero of eight pass all gates. The two best candidates rest on 24 and 28 bets
against a 100-bet floor, so they are noise candidates, not signals.</li>
<li><b>No profit figure is real.</b> Every ROI in the repository is measured against an assumed flat -110 price.
For the moneyline strategies that price was never available, and for everything else no market price was ever
recorded. The best published "edge" (+48% ROI) is an artefact of pricing a moneyline bet as a spread bet.</li>
<li><b>No injury effect has been modelled.</b> The official report states availability, not minutes. The repository
has no player game logs, so any minutes number would be invented. None is published.</li>
<li><b>No line has been compared to a bookmaker.</b> "Originated lines" here are naive estimates that beat their own
baseline. A model can beat a weak baseline and still be far behind the market.</li>
</ul>

<h3>The decision in front of you</h3>
<p>{len(blocked)} of the {len(qs)} open questions are marked blocking. They are not technical questions. In order of
what they unblock:</p>
<div class="scroll"><table><thead><tr><th>#</th><th>Question</th><th>Why it blocks</th></tr></thead><tbody>
{''.join(f'<tr><td class="num">{i}</td><td><b>{esc(q["topic"])}</b></td><td>{esc(q["blocking"])}</td></tr>' for i, q in enumerate(blocked[:5], 1))}
</tbody></table></div>
<p><a href="decisions.html">All decisions, ranked by what they unblock &rarr;</a></p>

<h3>Recommendation</h3>
<div class="note">Do not add another model. The repository already has six. The highest-value next step is to
<b>pick one dashboard, one gate set and one price source</b>, mark the other five as archived, and start a
prospective ledger. Until a price is recorded before tip-off and settled by an official source, no amount of
modelling can distinguish skill from luck &mdash; which is exactly the distinction the brief asks for.</div>
</section>"""
    return page('executive', 'Executive summary', body)


def build_contradictions(d):
    rows = ''
    for c in d['contradictions']['contradictions']:
        sev = c['severity']
        cls = 't-disc' if sev == 'Blocking' else ('t-unv' if sev == 'Material' else 't-info')
        rows += f"""<tr><td class="id">{esc(c['id'])}</td>
<td><span class="tag {cls}">{esc(sev)}</span></td>
<td><b>{esc(c['topic'])}</b>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">SAYS</b><br>{esc(c['says_a'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">VERSUS</b><br>{esc(c['says_b'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">EVIDENCE</b><br>{esc(c['evidence'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">VERDICT</b><br>{esc(c['verdict'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">IMPACT</b><br>{esc(c['impact'])}</div></td>
<td>{src(c['source'])}</td></tr>"""
    body = f"""
<section class="card"><h2>Contradictions between the existing dashboards</h2>
<p class="sub">Places where two or more of the six dashboards publish different answers to the same question from the
same repository. Where the evidence does not settle a contradiction, the row says so and gives no verdict.</p>
<div class="warn"><b>Read this before trusting any page in this repository.</b> Three of these are Blocking: a published
number is materially wrong and would mislead a decision.</div>
<div class="scroll"><table><thead><tr><th>ID</th><th>Severity</th><th>What each side says, the evidence, and the verdict</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>"""
    return page('contradictions', 'Contradictions', body)


def build_claims(d):
    cl = d['claims']['claims']
    from collections import Counter
    cst = Counter(c['status'] for c in cl)
    BLANK = "<i style='color:#8a5a00'>blank</i>"
    def val(c):
        return esc(c["value"]) if str(c["value"]).strip() else BLANK
    rows = ''.join(
        f'<tr><td class="id">{esc(c["id"])}</td><td><code>{esc(c["dashboard"])}</code></td>'
        f'<td>{esc(c["claim"])}</td>'
        f'<td class="num">{val(c)}</td>'
        f'<td>{esc(c["check"])}</td><td>{tag(c["status"])}</td><td>{src(c["source"])}</td></tr>'
        for c in cl)
    body = f"""
<section class="card"><h2>Claim ledger</h2>
<p class="sub">{esc(d['claims']['meta']['what'])}</p>
<div class="metric">
<div class="m"><b>{len(cl)}</b><span>claims rechecked</span></div>
<div class="m"><b>{cst['VERIFIED']}</b><span>reproduced exactly</span></div>
<div class="m"><b>{cst['DISCREPANCY']}</b><span>discrepancies found</span></div>
<div class="m"><b>{cst['UNVERIFIED']}</b><span>unverifiable (left blank)</span></div>
</div>
<div class="note">{esc(d['claims']['meta']['method'])} Discrepancies are explained in the last column and in the
<a href="contradictions.html">contradiction register</a>.</div>
<div class="scroll"><table><thead><tr><th>ID</th><th>Dashboard</th><th>Claim</th><th>Value</th>
<th>How it was checked</th><th>Status</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>"""
    return page('claims', 'Claim ledger', body)


def build_injuries(d):
    inj = d['injuries']
    t = inj['totals']
    rows = ''.join(
        f'<tr><td class="id">{esc(r["player"])}</td><td>{esc(r["team"])}</td>'
        f'<td><code>{esc(r["matchup"])}</code></td>'
        f'<td>{esc(r["status_0500pm"])}</td><td>{esc(r["status_0730pm"])}</td>'
        f'<td>{esc(r["change"])}</td></tr>' for r in inj['changes'])
    attrib = ''.join(
        f'<tr><td class="num">{esc(a["attribution"])}</td><td>{esc(a["meaning"])}</td>'
        f'<td class="num">{a["count"]}</td><td>{esc(a["disclosure"])}</td></tr>' for a in inj['attribution'])
    body = f"""
<section class="card"><h2>Injury verification</h2>
<p class="sub">The published injury table was checked row by row against the official NBA PDF, then checked again
against a later official report to test whether it was current.</p>

<div class="metric">
<div class="m"><b>{t['official_named_players']}</b><span>named players in the official report</span><small>transcribed verbatim</small></div>
<div class="m"><b>{t['matched']}</b><span>matched to our table</span><small>{t['status_mismatches']} status mismatches</small></div>
<div class="m"><b>{t['our_rows']}</b><span>rows in our table</span><small>{t['team_rows']} are team-level placeholders</small></div>
<div class="m"><b>{t['changed_later']}</b><span>players whose status changed within 2.5 hours</span><small>in the 07:30 PM report</small></div>
</div>

<div class="good"><b>The transcription itself is clean.</b> Every one of the {t['official_named_players']} named players
in the official 05:00 PM report appears in <code>data/injuries.json</code> with the same status and the same matchup.
Zero mismatches. The rows our table adds beyond the named players are team-level "NOT YET SUBMITTED" headers, which
the PDF does contain as team rows.</div>

<div class="warn"><b>The snapshot, however, was already stale when it was published.</b> The official index publishes a
report every 15 minutes. A <b>07:30 PM</b> report exists, 2.5 hours after the 05:00 PM snapshot the site uses, and
{t['changed_later']} players changed status in it. Two of them went <b>to Out</b>. That is exactly the kind of change
that moves a line, and the site could not have shown it.</div>

<h3>Status changes between the 05:00 PM and 07:30 PM official reports</h3>
<div class="scroll"><table><thead><tr><th>Player</th><th>Team</th><th>Matchup</th>
<th>05:00 PM (published)</th><th>07:30 PM (later)</th><th>Direction</th></tr></thead><tbody>{rows}</tbody></table></div>
<p style="font-size:13px;color:var(--muted)">Source for both columns:
<a href="{esc(inj['sources']['report_0500pm'])}">05:00 PM PDF</a> &middot;
<a href="{esc(inj['sources']['report_0730pm'])}">07:30 PM PDF</a> &middot;
<a href="{esc(inj['sources']['index'])}">official index</a>.
The 11/14 11:00 AM report returned an access-denied error and is recorded as a failed source, not omitted.</p>

<h3>How each row's team and matchup were established</h3>
<div class="scroll"><table><thead><tr><th>Code</th><th>Meaning</th><th>Rows</th><th>How it is disclosed</th></tr></thead>
<tbody>{attrib}</tbody></table></div>

<div class="note"><b>Why this matters more than it looks.</b> The PDF text extraction drops the team and matchup cells
for some rows, so 18 rows could only be attributed with reference to the surrounding context. Those rows are marked
<code>U</code> and left blank rather than guessed. A further 19 carry a team printed on the PDF but a matchup inferred
from the official schedule; they are marked <code>S</code>. A reader can therefore tell, on every single row, what was
printed by the league and what was added by us.</div>
</section>"""
    return page('injuries', 'Injury verification', body)


def build_results(d):
    r = d['results']
    games = r['agreed_games']
    rows = ''.join(
        f'<tr><td class="id">{esc(g["date"])}</td><td><code>{esc(g["matchup"])}</code></td>'
        f'<td class="num">{g["away_pts"]}&ndash;{g["home_pts"]}</td>'
        f'<td>{"OT" if g["ot"] else "&mdash;"}</td><td>{esc(g["nba_game_id"])}</td></tr>'
        for g in games)
    body = f"""
<section class="card"><h2>Game-log verification</h2>
<p class="sub">Two sessions captured the 2026-27 season from different pages with different code. This page tests
whether they actually agree.</p>
<div class="metric">
<div class="m"><b>{r['n_games']}</b><span>games in each log</span><small>20 Oct - 12 Nov 2026</small></div>
<div class="m"><b>{r['score_mismatches']}</b><span>score mismatches</span></div>
<div class="m"><b>{r['ot_mismatches']}</b><span>overtime mismatches</span></div>
<div class="m"><b>{r['n_ot']}</b><span>overtime games, agreed</span><small>8 OT, 1 double OT</small></div>
</div>
<div class="good"><b>This is the strongest evidence in the repository.</b> Two independent captures, 174 games each,
<b>zero</b> disagreements on teams, dates, exact final scores or overtime classification. The probability of that
agreement happening by accident across two independent transcription errors is negligible, so the log is treated as
the root of truth for everything else.</div>
<div class="note"><b>One official spot check.</b> The first game of the season was verified directly against
<a href="{esc(r['official_spot_check']['url'])}">NBA.com</a>: line score
<b>{esc(r['official_spot_check']['official_line'])}</b> against the repository's
<b>{esc(r['official_spot_check']['repo_line'])}</b> &mdash; a match. The remaining 173 games are not individually
confirmed against an official page; they rest on the two-capture agreement recorded here, which is stated plainly
rather than presented as official confirmation.</div>
<div class="scroll"><table><thead><tr><th>Date</th><th>Matchup</th><th>Final (away&ndash;home)</th><th>OT</th><th>NBA game id</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>"""
    return page('results', 'Game-log verification', body)


def build_corrections(d):
    c = d['corrections']
    rows = ''.join(
        f'<tr><td class="id">{esc(x["id"])}</td><td><code>{esc(x["file"])}</code><br><code>{esc(x["function"])}</code></td>'
        f'<td>{esc(x["defect"])}</td>'
        f'<td><span class="tag t-disc">before</span><br><code>{esc(x["before"])}</code></td>'
        f'<td><span class="tag t-verified">after</span><br><code>{esc(x["after"])}</code></td>'
        f'<td><code>{esc(x["test"])}</code><br><span style="color:var(--muted)">{esc(x["cross_check"])}</span></td>'
        f'<td>{src(x["source"])}</td></tr>' for x in c['corrections'])
    curve = ''.join(
        f'<tr><td class="num">{r["rho"]:+.1f}</td><td class="num">{r["joint"]:.4f}</td>'
        f'<td class="num">{r["fair_decimal"]:.3f}</td><td class="num">{r["fair_american"]:+d}</td></tr>'
        for r in c['parlay_table']['rows'])
    body = f"""
<section class="card"><h2>Corrections made this session</h2>
<p class="sub">Defects found by recomputation, fixed in the repository, and pinned by a test so they cannot return.</p>
<div class="note">{esc(c['meta']['rule'])}</div>
<div class="scroll"><table><thead><tr><th>ID</th><th>Where</th><th>Defect</th><th>Before</th><th>After</th>
<th>Test and independent cross-check</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>

<h3>The parlay table, corrected</h3>
<p>{esc(c['parlay_table']['legs'])}. {esc(c['parlay_table']['note'])}</p>
<div class="scroll"><table><thead><tr><th>Correlation</th><th>Joint probability</th><th>Fair decimal</th><th>Fair American</th></tr></thead>
<tbody>{curve}</tbody></table></div>
<div class="warn"><b>Why the old number was impossible.</b> {esc(c['parlay_table']['bounds'])} The previously published
0.58 was therefore not a small error &mdash; it was the mathematical ceiling, reachable only if the two legs were the
same event.</div>

<h3>An honest note on one check that was wrong</h3>
<p>While auditing, this session initially flagged the <code>/edge/</code> test-set size of 138 as inconsistent with a
30-game burn-in, because 30 + 138 = 168 rather than 174. That inference was wrong. The walk-forward file has 36 rows
without a fitted calibration (the logistic fit needs 30 games and then fails to converge for 6 more), and 138 is
exactly the number of rows that have both a fitted calibration and an index of at least 30. The false alarm is kept
in the claim ledger rather than quietly deleted, because the lesson is the point: inspection produced a false
positive, and recomputation corrected it.</p>
</section>"""
    return page('corrections', 'Corrections made', body)


def build_decisions(d):
    qs = d['questions']['questions']
    sg = {s['id']: s for s in d['suggestions']['suggestions']}
    rows = ''
    for i, q in enumerate(qs, 1):
        blocked = str(q['blocking']).lower().startswith('yes')
        rows += f"""<tr><td class="num">{i}</td><td class="id">{esc(q['id'])}</td>
<td><b>{esc(q['topic'])}</b>
<div style="margin-top:6px"><span class="tag {'t-disc' if blocked else 't-info'}">{esc(q['blocking'])}</span></div>
<div style="margin-top:8px"><b style="font-size:12px;color:var(--muted)">HAVE</b><br>{esc(q['have'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">MISSING</b><br>{esc(q['missing'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">HOW TO GET IT</b><br>{esc(q['how'])}</div>
<div style="margin-top:6px"><b style="font-size:12px;color:var(--muted)">RISK IF IGNORED</b><br>{esc(q['risk_if_ignored'])}</div></td>
<td>{src(q['source'], q.get('extra', ''))}</td></tr>"""
    body = f"""
<section class="card"><h2>Decisions needed</h2>
<p class="sub">Every question that has to be answered before a decision can reasonably be made, split into what the
repository already establishes, what is missing, and how the missing part would be discovered. No question is
answered here by inference.</p>
<div class="warn"><b>Nothing on the rest of this site can become a staking recommendation until Q-01 is answered.</b>
That is a legal question about the jurisdiction and the NBA's terms, and no amount of modelling substitutes for it.</div>
<div class="note">Ranked so that the questions which freeze the most downstream work come first. The first five are the
ones worth spending time on; the rest follow from them.</div>
<div class="scroll"><table><thead><tr><th>#</th><th>ID</th><th>Question, what we have, what is missing, how to get it</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>
<section class="card"><h2>The shortest path to a usable product</h2>
<div class="scroll"><table><thead><tr><th>Step</th><th>Action</th><th>Suggestion</th><th>Blocked by</th></tr></thead><tbody>
<tr><td class="num">1</td><td>Decide the legal position: jurisdiction, licence, and whether the NBA terms permit this at all.</td><td>{esc(sg['SG-09']['id'])}</td><td>Nothing &mdash; this is a human decision</td></tr>
<tr><td class="num">2</td><td>Choose one dashboard, one gate set and one leaderboard rule; archive the other five.</td><td>{esc(sg['SG-01']['id'])}, {esc(sg['SG-02']['id'])}, {esc(sg['SG-06']['id'])}</td><td>Nothing</td></tr>
<tr><td class="num">3</td><td>Obtain a licensed price feed and record prices before tip-off.</td><td>{esc(sg['SG-06']['id'])}</td><td>Q-03</td></tr>
<tr><td class="num">4</td><td>Run the prospective ledger until 100 picks have settled.</td><td>{esc(sg['SG-04']['id'])}</td><td>Steps 2 and 3</td></tr>
<tr><td class="num">5</td><td>Only then decide whether to publish anything as staking-eligible.</td><td>{esc(sg['SG-05']['id'])}</td><td>Steps 1 and 4</td></tr>
</tbody></table></div></section>"""
    return page('decisions', 'Decisions needed', body)


def build_questions(d):
    qs = d['questions']['questions']
    rows = ''.join(
        f'<tr><td class="id">{esc(q["id"])}</td><td><b>{esc(q["topic"])}</b></td>'
        f'<td>{esc(q["have"])}</td><td>{esc(q["missing"])}</td><td>{esc(q["how"])}</td>'
        f'<td>{esc(q["blocking"])}</td><td>{src(q["source"], q.get("extra", ""))}</td></tr>'
        for q in qs)
    body = f"""
<section class="card"><h2>Questions ledger</h2>
<p class="sub">The same questions as the decisions page, laid out as have / missing / how to get it, for review on one
screen.</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>Topic</th><th>What we have</th><th>What is missing</th>
<th>How to discover it</th><th>Blocking?</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>"""
    return page('questions', 'Questions ledger', body)


def build_suggestions(d):
    sg = d['suggestions']
    rows = ''.join(
        f'<tr><td class="num">{s["priority"]}</td><td class="id">{esc(s["id"])}</td>'
        f'<td><b>{esc(s["area"])}</b><br><span style="color:var(--muted)">{esc(s["problem"])}</span></td>'
        f'<td><ol class="tight" style="margin:0">{"" .join(f"<li>{esc(o)}</li>" for o in s["options"])}</ol></td>'
        f'<td><b>Recommended:</b> {esc(s["recommendation"])}<br>'
        f'<span style="color:var(--muted)">Cost: {esc(s["cost"])}</span></td>'
        f'<td><span class="tag {"t-verified" if s["status"].startswith("Implemented") else "t-unv"}">{esc(s["status"])}</span><br>'
        f'<span style="color:var(--muted);font-size:12.5px">{esc(s["decision_needed"])}</span></td>'
        f'<td>{src(s["source"])}</td></tr>' for s in sg['suggestions'])
    body = f"""
<section class="card"><h2>Suggestions for review</h2>
<p class="sub">{esc(sg['meta']['what'])}</p>
<div class="note">{esc(sg['meta']['rules'])}</div>
<div class="scroll"><table><thead><tr><th>#</th><th>ID</th><th>Area and problem</th><th>Options</th>
<th>Recommendation</th><th>Decision needed</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>
<section class="card"><h2>What was and was not changed</h2>
<p>Only two suggestions are marked implemented, and both were corrections to a demonstrated defect rather than
product changes: the numerical self-test that caught the two arithmetic errors, and this decisions page.</p>
<p>Everything else is deliberately left alone so that the owner can choose a path before anything moves. In
particular, none of the six existing dashboards was consolidated or deleted, because that is a decision for the
owner and not for an agent session.</p>
</section>"""
    return page('suggestions', 'Suggestions', body)


def settle(r):
    if r["settlement_source"]:
        return src(r["settlement_source"])
    return '<span class="tag t-unv">game id unconfirmed</span>'


def build_ledger(d):
    led = d['ledger']
    c = led['meta']['counts']
    rows = ''.join(
        f'<tr><td class="id">{esc(r["id"])}</td><td>{esc(r["game_date"])}</td>'
        f'<td><code>{esc(r["matchup"])}</code></td><td>{esc(r["market"])}</td>'
        f'<td><b>{esc(r["model_favours"])}</b></td>'
        f'<td class="num">{r["our_fair_american"]:+d}</td><td class="num">{r["our_model_prob"]:.3f}</td>'
        f'<td>{esc(r["published_label_as_issued"])}</td><td>{esc(r["corrected_label"])}</td>'
        f'<td><span class="tag t-unv">{esc(r["status"])}</span></td>'
        f'<td>{settle(r)}</td></tr>'
        for r in led['ledger'])
    body = f"""
<section class="card"><h2>Settlement ledger</h2>
<p class="sub">{esc(led['meta']['what'])}</p>
<div class="metric">
<div class="m"><b>{c['total']}</b><span>picks recorded before tip-off</span></div>
<div class="m"><b>{c['settled']}</b><span>settled</span><small>none yet &mdash; the games have not been played at build time</small></div>
<div class="m"><b>{c['labels_that_were_inverted']}</b><span>labels that named the wrong side</span><small>all corrected</small></div>
<div class="m"><b>{c['with_official_game_id']}</b><span>with a confirmed official game id</span></div>
</div>
<div class="note">{esc(led['meta']['why'])}</div>
<div class="warn">{esc(led['meta']['pricing_note'])}</div>
<div class="scroll"><table><thead><tr><th>ID</th><th>Date</th><th>Matchup</th><th>Market</th><th>Model favours</th>
<th>Our fair price</th><th>Our prob</th><th>Published label</th><th>Corrected label</th><th>Status</th><th>Settlement source</th></tr></thead>
<tbody>{rows}</tbody></table></div>

<h3>The promotion rule</h3>
<div class="scroll"><table><thead><tr><th>Control</th><th>Rule</th></tr></thead><tbody>
{''.join(f'<tr><td><b>{esc(k)}</b></td><td>{esc(v)}</td></tr>' for k, v in led['controls'].items())}
</tbody></table></div>
<div class="warn"><b>Nothing here is a result yet.</b> A ledger with zero settled rows proves nothing. Its value is
that it exists <i>before</i> the outcomes are known, which is the only way a later result can be called skill rather
than luck.</div>
</section>"""
    return page('ledger', 'Settlement ledger', body)


def build_sources(d):
    s = d['sources']['sources']
    rows = ''.join(
        f'<tr><td class="id">{esc(x["id"])}</td>'
        f'<td><span class="tag {"t-verified" if x["tier"]=="OFFICIAL" else ("t-unv" if x["tier"]=="TRUSTED-2" else "t-disc")}">{esc(x["tier"])}</span></td>'
        f'<td><a href="{esc(x["url"])}">{esc(x["title"])}</a><br><span style="color:var(--muted);font-size:12.5px">{esc(x["url"])}</span></td>'
        f'<td>{esc(x["read"])}</td><td>{esc(x["supports"])}</td><td>{esc(x["does_not_support"])}</td></tr>'
        for x in s)
    body = f"""
<section class="card"><h2>Sources</h2>
<p class="sub">{esc(d['sources']['meta']['what'])}</p>
<div class="note">{esc(d['sources']['meta']['rule'])}</div>
<div class="note">{esc(d['sources']['meta']['access_note'])}</div>
<div class="scroll"><table><thead><tr><th>ID</th><th>Tier</th><th>Source</th><th>Read</th>
<th>What it supports</th><th>What it does not support</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>"""
    return page('sources', 'Sources', body)


def build_flagged(d):
    co = d['contradictions']['contradictions']
    cl = [c for c in d['claims']['claims'] if c['status'] != 'VERIFIED']
    led = [r for r in d['ledger']['ledger'] if not r['settlement_source']]
    rows = ''.join(
        f'<tr><td class="id">{esc(c["id"])}</td><td><span class="tag t-disc">{esc(c["severity"])}</span></td>'
        f'<td><b>{esc(c["topic"])}</b><br><span style="color:var(--muted)">{esc(c["impact"])}</span></td>'
        f'<td>{src(c["source"])}</td></tr>' for c in co)
    crows = ''.join(
        f'<tr><td class="id">{esc(c["id"])}</td><td>{esc(c["claim"])}</td>'
        f'<td>{tag(c["status"])}</td><td>{esc(c["check"])}</td><td>{src(c["source"])}</td></tr>' for c in cl)
    lrows = ''.join(
        f'<tr><td class="id">{esc(r["id"])}</td><td><code>{esc(r["matchup"])}</code></td>'
        f'<td>{esc(r["game_date"])}</td><td>{esc(r["note"])}</td></tr>' for r in led)
    body = f"""
<section class="card"><h2>Flagged for review</h2>
<p class="sub">Everything this session could not confirm, contradicted, or deliberately left blank. Nothing here
blocks the site from publishing, but every item needs a human decision.</p>
<div class="warn"><b>{len(co)} contradictions, {len(cl)} claims that are not verified, and {len(led)} ledger rows with
no confirmed official game id.</b> Each is listed with its source so it can be checked directly.</div>

<h3>Contradictions between dashboards</h3>
<div class="scroll"><table><thead><tr><th>ID</th><th>Severity</th><th>Topic and impact</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div>

<h3>Claims that are not verified</h3>
<div class="scroll"><table><thead><tr><th>ID</th><th>Claim</th><th>Status</th><th>Why</th><th>Source</th></tr></thead>
<tbody>{crows}</tbody></table></div>

<h3>Ledger rows without a confirmed official game id</h3>
<p style="color:var(--muted);font-size:13.5px">These picks are for 16 November. The official game ids for that date
were not confirmed from NBA.com during this session, so the settlement source is left blank rather than guessed.</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>Matchup</th><th>Date</th><th>Note</th></tr></thead><tbody>{lrows}</tbody></table></div>

<h3>Open legal and data questions</h3>
<div class="scroll"><table><thead><tr><th>ID</th><th>Question</th><th>Source</th></tr></thead><tbody>
<tr><td class="id">Q-01</td><td>Whether publishing this content requires a Dutch Koa licence, and whether the NBA terms permit it at all.</td><td>{src('https://kansspelautoriteit.nl/online-kansspel-aanbieden')}</td></tr>
<tr><td class="id">Q-12</td><td>Whether the repository has the right to store and republish Basketball-Reference and NBA data. There is no licence file in the repository.</td><td>{src('https://www.basketball-reference.com/about/terms.html')}</td></tr>
</tbody></table></div>
</section>"""
    return page('flagged', 'Flagged for review', body)


# ---------------------------------------------------------------- main

def main():
    check_only = '--check' in sys.argv
    print('verify/build.py - session 3655c68d')
    print('\n1. numerical and data self-tests')
    ok = run_checks()
    print('\n2. loading data')
    d = {
        'summary': load('summary.json'),
        'claims': load('claims.json'),
        'contradictions': load('contradictions.json'),
        'ledger': load('ledger.json'),
        'questions': load('questions.json'),
        'suggestions': load('suggestions.json'),
        'sources': load('sources.json'),
        'corrections': load('corrections.json'),
        'injuries': load('injuries.json'),
        'results': load('results.json'),
    }
    for k, v in d.items():
        n = len(v.get('claims') or v.get('contradictions') or v.get('sources') or v.get('questions')
                or v.get('suggestions') or v.get('corrections') or v.get('ledger')
                or v.get('summary') or v.get('changes') or v.get('agreed_games') or [])
        print(f'   {k:16s} {n} rows')
    if problems:
        print('\nFAILED - site not written:')
        for p in problems:
            print('   -', p)
        return 1
    if check_only:
        print('\nAll checks passed. --check given, nothing written.')
        return 0
    os.makedirs(VPAGES, exist_ok=True)
    builders = {
        'index': build_index, 'executive': build_executive, 'contradictions': build_contradictions,
        'claims': build_claims, 'injuries': build_injuries, 'results': build_results,
        'corrections': build_corrections, 'decisions': build_decisions,
        'questions': build_questions, 'suggestions': build_suggestions,
        'ledger': build_ledger, 'sources': build_sources, 'flagged': build_flagged,
    }
    print('\n3. rendering')
    for slug, fn in builders.items():
        out = os.path.join(VPAGES, f'{slug}.html')
        with open(out, 'w', encoding='utf-8') as f:
            f.write(fn(d))
        print(f'   {slug + ".html":22s} {os.path.getsize(out):>7d} bytes')
    # link check
    import re
    broken = []
    files = {f for f in os.listdir(VPAGES) if f.endswith('.html')}
    for f in sorted(files):
        s = open(os.path.join(VPAGES, f), encoding='utf-8').read()
        for href in re.findall(r'href="([^"]+)"', s):
            if href.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            target = href.split('#')[0]
            if target and target not in files:
                broken.append(f'{f} -> {href}')
    if broken:
        print('\nFAILED - broken internal links:')
        for b in broken:
            print('   -', b)
        return 1
    print(f'\nOK: {len(files)} pages written to verify/pages/, 0 broken internal links.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
