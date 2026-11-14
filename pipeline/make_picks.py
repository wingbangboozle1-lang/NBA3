#!/usr/bin/env python3
"""
Generate picks for every slate within the next 3 days from OUR originated lines.

Rules
-----
* Only strategies that PASS the validation gates (see validation_report.json) may be
  published as "eligible"; passing-except-sample-size strategies are published as
  "provisional" and must carry that label; failing strategies are NOT eligible.
* Games with material availability uncertainty (star/desk players Out or Doubtful on the
  official report, or no report submitted yet) are flagged; their picks carry a
  "wait for lineup confirmation" warning. The model does NOT apply an invented numeric
  injury adjustment (no player-level impact data available) — flagged instead.
* Parlay suggestions are only built between different games and only from
  provisional/eligible strategies, with the measured correlation caveat attached.
"""
import json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _spread_label(line):
    """Human-readable spread, written the way a sportsbook writes it:
    the FAVOURITE carries the minus sign and the underdog carries the plus.

    FIX 2026-11-14 (session 3655c68d, defect FX-02):
      the previous expression emitted the AWAY team with a '+' and the value -origin_spread_home.
      Because origin_spread_home is a projected home margin, that printed the underdog on the
      wrong side of the market on all 22 cards (e.g. 'DEN +8.6' where DEN is the -205 favourite).
    """
    mh = line['origin_spread_home']   # projected HOME MARGIN: negative => HOME loses
    home, away = line['home'], line['away']
    if abs(mh) < 0.05:
        return f"{home} 0.0"
    if mh > 0:
        return f"{home} -{mh:.1f}"   # HOME wins by mh  -> home is the favourite
    return f"{away} {mh:.1f}"        # mh<0 => away wins by |mh| -> away is the favourite


def main():
    lines = json.load(open(f'{ROOT}/data/model/lines_2026-27.json'))
    val   = json.load(open(f'{ROOT}/data/model/validation_report.json'))
    inj   = json.load(open(f'{ROOT}/data/injuries/injury_report_2026-11-13.json'))

    def strat_status(k):
        g = val['strategies'][k]
        fails = [x['gate'] for x in g['gates'] if not x['passed']]
        if not fails: return 'eligible'
        if fails == ['G1_sample>=100']: return 'provisional (passes all gates except minimum sample size)'
        return 'not eligible: ' + ', '.join(fails)
    status = {k: strat_status(k) for k in ('STRAT1','STRAT2','STRAT3','STRAT4')}

    # availability risk per team (from official report where submitted)
    def avail_risk(date, home, away):
        key = f"{away}@{home}" if f"{away}@{home}" in inj['games'].get(date, {}) else None
        if key is None:
            return dict(flag='NO_REPORT', detail='Official injury report not yet published for this game.',
                        out=[], doubtful=[], questionable=[])
        gdata = inj['games'][date][key]
        out, doub, quest = [], [], []
        for team in (away, home):
            rows = gdata.get(team)
            if rows == 'NOT YET SUBMITTED' or rows is None:
                continue
            for r in rows:
                st = r['status'].lower()
                if st == 'out': out.append(f"{team} {r['player']}")
                elif st == 'doubtful': doub.append(f"{team} {r['player']}")
                elif st == 'questionable': quest.append(f"{team} {r['player']}")
        if not out and not doub and not quest:
            g_has = any(v == 'NOT YET SUBMITTED' for v in gdata.values())
            if g_has:
                return dict(flag='PARTIAL_REPORT', detail='One or both teams had not submitted their report at publication time.',
                            out=out, doubtful=doub, questionable=quest)
            return dict(flag='OK', detail='No availability concerns listed on the official report.', out=out, doubtful=doub, questionable=quest)
        return dict(flag='AVAILABILITY_RISK', detail='Players listed Out/Doubtful/Questionable on the official report — wait for lineup confirmation before acting.',
                    out=out, doubtful=doub, questionable=quest)

    picks = []
    for L in lines:
        risk = avail_risk(L['date'], L['home'], L['away'])
        p_home = L['model_p_home']
        side = 'HOME' if p_home >= 0.5 else 'AWAY'
        spread_side = L['home'] if p_home >= 0.5 else L['away']
        pick = dict(
            date=L['date'], start_et=L['start_et'], matchup=f"{L['away']} @ {L['home']}",
            origin_spread=_spread_label(L),
            origin_total=L['origin_total'],
            fair_ml_home=L['fair_ml_home'], fair_ml_away=L['fair_ml_away'],
            model_p_home=p_home,
            confidence=L['confidence'],
            availability=risk,
            singles_view=None, ml_view=None, totals_view=None, parlay_leg_candidate=None)
        # views gated by strategy status
        s1 = status['STRAT1']; s2 = status['STRAT2']
        if L['confidence'] in ('MEDIUM','HIGH') and risk['flag'] != 'AVAILABILITY_RISK':
            pick['singles_view'] = f"Model side: {spread_side} (spread). Strategy status: {s1}."
            pick['ml_view'] = (f"Fair ML {L['home']} {L['fair_ml_home']:+d} / {L['away']} {L['fair_ml_away']:+d}. "
                               f"Strategy status: {s2}.")
        elif risk['flag'] == 'AVAILABILITY_RISK':
            pick['singles_view'] = f"Model side: {spread_side} (spread) — HELD: availability risk on official report; re-check after lineups post."
            pick['ml_view'] = "HELD: availability risk."
        pick['totals_view'] = (f"Originated total {L['origin_total']} (model projected {L['exp_home_score']} + {L['exp_away_score']}). "
                               f"Totals strategy status: {status['STRAT3']} — not eligible for betting.")
        pick['parlay_leg_candidate'] = (L['confidence'] == 'HIGH') and (risk['flag'] in ('OK','PARTIAL_REPORT'))
        picks.append(pick)

    # parlay combos: 2-leg, different games, same day, both HIGH confidence, no availability risk
    from itertools import combinations
    combos = []
    by_day = {}
    for p in picks:
        if p['parlay_leg_candidate']:
            by_day.setdefault(p['date'], []).append(p)
    for d, legs in sorted(by_day.items()):
        for a, b in combinations(legs, 2):
            combos.append(dict(date=d, legs=[f"{a['matchup']} — {a['singles_view'].split(' (')[0] if a['singles_view'] else a['matchup']}",
                                             f"{b['matchup']} — {b['singles_view'].split(' (')[0] if b['singles_view'] else b['matchup']}"],
                               status=status['STRAT4'],
                               caveat="Parlay strategy did NOT pass validation gates (n=15, permutation p=%.3f). Displayed for research only." % (val['strategies']['STRAT4']['perm_p'] or 1.0)))
    out = dict(
        generated_for_window="2026-11-14 .. 2026-11-16",
        generated_on=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        strategy_status=status,
        max_lookahead_days=3,
        pricing_note="Fair prices are OUR originated prices. No licensed odds feed is connected; no market comparison has been performed.",
        picks=picks, parlay_combos=combos)
    json.dump(out, open(f'{ROOT}/data/picks/picks_2026-11-14_to_16.json','w'), indent=1)
    print(f"picks: {len(picks)} games, parlay combos (research-only): {len(combos)}")
    for k,v in status.items(): print(f"  {k}: {v}")

if __name__ == '__main__':
    main()
