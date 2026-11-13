#!/usr/bin/env python3
"""Emit compact JSON for the Pages dashboard into site/data/."""
import json, os, csv, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f'{ROOT}/site/data'
os.makedirs(OUT, exist_ok=True)

def w(name, obj):
    json.dump(obj, open(f'{OUT}/{name}', 'w'), separators=(',', ':'))

# teams & records
teams = {}
for line in open(f'{ROOT}/data/model/ratings_2027_current.csv'):
    if line.startswith('#'): continue
    t, wl, l, o, d, n = line.strip().split(',')
    teams[t] = dict(w=int(wl), l=int(l), nrtg=float(n))
w('teams.json', teams)

# game log with derived stats
games = json.load(open(f'{ROOT}/data/processed/games_2026-27.json'))
rec = collections.defaultdict(lambda: dict(w=0, l=0, pf=0, pa=0))
for g in games:
    rec[g['home']]['pf'] += g['hps']; rec[g['home']]['pa'] += g['aps']
    rec[g['away']]['pf'] += g['aps']; rec[g['away']]['pa'] += g['hps']
    if g['aps'] > g['hps']: rec[g['away']]['w'] += 1; rec[g['home']]['l'] += 1
    else: rec[g['home']]['w'] += 1; rec[g['away']]['l'] += 1
w('standings.json', {t: dict(w=v['w'], l=v['l'], pct=round(v['w']/(v['w']+v['l']),3),
                             ppg=round(v['pf']/(v['w']+v['l']),1), papg=round(v['pa']/(v['w']+v['l']),1))
                     for t, v in rec.items()})
w('games.json', games)

# model outputs
for name in ('validation_report', 'correlation_report', 'lines_2026-27'):
    w(name.replace('_', '-') + '.json', json.load(open(f'{ROOT}/data/model/{name}.json')))

# picks & props
w('picks.json', json.load(open(f'{ROOT}/data/picks/picks_2026-11-14_to_16.json')))
w('props.json', json.load(open(f'{ROOT}/data/picks/props_2026-11-14_to_16.json')))
w('injuries.json', json.load(open(f'{ROOT}/data/injuries/injury_report_2026-11-13.json')))

# schedule
sched = []
for line in open(f'{ROOT}/data/raw/schedule_2026-11-13_to_16.csv'):
    if line.startswith('#'): continue
    p = [x for x in line.strip().split(',') if x != '']
    sched.append(dict(date=p[0], start_et=p[1], away=p[2], home=p[3], note=p[4] if len(p) > 4 else ''))
w('schedule.json', sched)
print("site data emitted:", sorted(os.listdir(OUT)))
