#!/usr/bin/env python3
"""Assemble + validate collected data. Sources are documented in data/SOURCES.md."""
import json, os, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOTE_KEYS = {"NBA Cup", "Mexico City"}

def parse(path):
    games = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'): continue
        p = [x for x in line.split(',') if x != '']
        date, away, aps, home, hps = p[0], p[1], int(p[2]), p[3], int(p[4])
        ot, note = False, ''
        for extra in p[5:]:
            if extra == 'OT': ot = True
            elif extra == '2OT': ot, note = True, '2OT'
            elif extra in NOTE_KEYS: note = extra
            else: note = extra
        if aps == hps and not ot:
            raise ValueError(f"tie without OT? {line}")
        games.append(dict(date=date, away=away, aps=aps, home=home, hps=hps, ot=ot, note=note))
    return games

def main():
    games = (parse(f'{ROOT}/data/raw/results_2026-27_october.csv')
             + parse(f'{ROOT}/data/raw/results_2026-27_november.csv'))
    games.sort(key=lambda g: (g['date'], g['away']))
    # sanity: records reconcile against the BBR ratings table (reference file)
    rec = collections.defaultdict(lambda: [0, 0])
    for g in games:
        if g['aps'] > g['hps']: rec[g['away']][0] += 1; rec[g['home']][1] += 1
        elif g['hps'] > g['aps']: rec[g['home']][0] += 1; rec[g['away']][1] += 1
    ref = {}
    for line in open(f'{ROOT}/data/model/ratings_2027_current.csv'):
        if line.startswith('#'): continue
        t, w, l = line.strip().split(',')[:3]
        ref[t] = (int(w), int(l))
    mismatch = {t: (rec[t], ref[t]) for t in ref if tuple(rec[t]) != ref[t]}
    if mismatch:
        raise SystemExit(f"RECORD MISMATCH vs reference: {mismatch}")
    json.dump(games, open(f'{ROOT}/data/processed/games_2026-27.json', 'w'), indent=1)
    ot = sum(1 for g in games if g['ot'])
    print(f"games={len(games)} records_reconciled=30/30 OT={ot} ({ot/len(games):.1%})")

if __name__ == '__main__':
    main()
