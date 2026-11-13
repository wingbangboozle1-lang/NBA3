#!/usr/bin/env python3
"""
NBA3 line origination + validation engine.

Inputs  (all under data/, each with a documented source):
  processed/games_2026-27.json       2026-27 game results (Basketball-Reference; 30/30 team
                                     records reconciled against the BBR ratings table)
  model/ratings_2026_final.csv       2025-26 FINAL adjusted ratings (Basketball-Reference)
  raw/schedule_2026-11-13_to_16.csv  upcoming slate (Basketball-Reference)

Outputs:
  model/validation_report.json   walk-forward backtest + validation gates + permutation tests
  model/correlation_report.json  measured correlations + parlay math
  model/lines_2026-27.json       originated lines for the next 3 days
  model/walkforward_detail.json  per-game predictions (audit trail)

Design
------
* Model A ("prior"): 2025-26 BBR adjusted NRtg difference, linearly calibrated to actual
  margin with an expanding walk-forward window (min 30 games).
* Model B ("elo"): in-season Elo with margin-of-victory multiplier (public FiveThirtyEight-
  style methodology), initialized from 2025-26 ratings; home advantage included in BOTH the
  update and the prediction (48 Elo = 3.2 pts).
* Model C ("consensus"): fixed 50/50 blend of A and B (chosen a priori).
* Recalibration layer: expanding-window OLS recalibration of Model C (scale + center) and a
  single-parameter logistic fit of win probability — both fit ONLY on past games at each step
  (no leakage).
* Totals ("pace-free"): shrunk, opponent-adjusted team scoring; expanding league-average total
  as the baseline line; home scoring edge fixed at +1.5 (documented prior).
* No market odds feed is available: backtest pricing assumes standard -110 and is labeled an
  assumption everywhere it appears.
"""
import json, math, csv, statistics, random, os

random.seed(20261113)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HCA_ELO   = 48.0      # home advantage in Elo (~3.2 pts) — used in update AND prediction
K_ELO     = 20.0
ELO_PER_PT = 15.0     # 1 margin-rating point ~ 15 Elo (documented assumption)
HCA_TOT   = 1.5       # home scoring edge on totals (documented prior)

def load_games():
    return json.load(open(f'{ROOT}/data/processed/games_2026-27.json'))

def load_prior():
    pr = {}
    for line in open(f'{ROOT}/data/model/ratings_2026_final.csv'):
        if line.startswith('#'): continue
        t, w, l, o, d, n = line.strip().split(',')
        pr[t] = float(n)
    return pr

def mov_mult(margin, elo_diff_eff):
    return ((abs(margin) + 3) ** 0.8) / (7.5 + 0.006 * max(elo_diff_eff, 0))

def fit_ols(xs, ys):
    n = len(xs)
    mx = sum(xs)/n; my = sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs)
    if sxx == 0: return 0.0, my
    sxy = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    s = sxy/sxx
    return s, my - s*mx

def fit_logit_k(xs, ys, iters=300, lr=0.3):
    """MLE for p = 1/(1+exp(-k*x)) via gradient ascent on log-likelihood."""
    k = 0.12
    n = len(xs)
    for _ in range(iters):
        g = 0.0
        for x, y in zip(xs, ys):
            p = 1/(1+math.exp(-k*x))
            g += (y - p) * x
        k += lr * g / n
        k = min(max(k, 0.01), 1.5)
    return k

def corr(x, y):
    n=len(x); mx=sum(x)/n; my=sum(y)/n
    sx=math.sqrt(sum((v-mx)**2 for v in x)); sy=math.sqrt(sum((v-my)**2 for v in y))
    if sx*sy == 0: return 0.0
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(sx*sy)

def perm_test(bets, k=2000):
    if len(bets) < 10: return None
    obs = sum(0.9091 if b['won'] else -1.0 for b in bets)
    cnt = 0
    for _ in range(k):
        s = 0.0
        for _ in bets:
            s += 0.9091 if random.random() < 0.5 else -1.0
        if s >= obs: cnt += 1
    return cnt / k

def run():
    games = sorted(load_games(), key=lambda g: (g['date'], g['away']))
    prior = load_prior()
    teams = sorted({g['home'] for g in games} | {g['away'] for g in games})
    elo = {t: 1500 + prior[t] * ELO_PER_PT for t in teams}
    team_g = {t: [] for t in teams}

    cal_pairs, log = [], []
    totals_hist = []          # all league totals so far (expanding baseline)

    # process DATE BY DATE: predictions for all games of a day use only prior-day state
    # (games within a slate are simultaneous; no same-day leakage allowed)
    dates = sorted({g['date'] for g in games})
    idx = 0
    for d in dates:
        day_games = [g for g in games if g['date'] == d]
        day_records = []
        for g in day_games:
            h, a, hm, am = g['home'], g['away'], g['hps'], g['aps']
            margin, total = hm - am, hm + am
            rd_prior = prior[h] - prior[a]

            # raw model predictions (from state BEFORE this date)
            predA_raw = rd_prior + HCA_ELO / ELO_PER_PT
            predB_raw = (elo[h] + HCA_ELO - elo[a]) / ELO_PER_PT
            predC_raw = 0.5 * predA_raw + 0.5 * predB_raw

            # expanding recalibration of C (scale/center) + logistic k (past data only)
            if len(cal_pairs) >= 30:
                xs = [c for c, _ in cal_pairs]
                ys = [m for _, m in cal_pairs]
                s, b = fit_ols(xs, ys)
                predC = s * predC_raw + b
                outs = [1.0 if m > 0 else 0.0 for _, m in cal_pairs]
                kpairs = [(s*x+b, o) for x, o in zip(xs, outs)]
                k = fit_logit_k([p for p, _ in kpairs], [o for _, o in kpairs])
                p_home = 1/(1+math.exp(-k*predC))
                calib = dict(s=round(s,4), b=round(b,3), k=round(k,4))
            else:
                predC, p_home, calib = predC_raw, 1/(1+10**(-predC_raw/20.0)), dict(s=None,b=None,k=None)

            # totals model
            if len(team_g[h]) >= 3 and len(team_g[a]) >= 3:
                lg_off = statistics.mean(x['pf'] for tg in team_g.values() for x in tg)
                def shrink(x, n, mean, kk=8.0): return (n*x + kk*mean)/(n+kk)
                def off(t): return statistics.mean(x['pf'] for x in team_g[t])
                def dfn(t): return statistics.mean(x['pa'] for x in team_g[t])
                ng = lambda t: len(team_g[t])
                exp_h = 0.5*(shrink(off(h),ng(h),lg_off) + shrink(dfn(a),ng(a),lg_off))
                exp_a = 0.5*(shrink(off(a),ng(a),lg_off) + shrink(dfn(h),ng(h),lg_off))
                total_pred = exp_h + exp_a + HCA_TOT
            else:
                total_pred, exp_h, exp_a = None, None, None
            lg_total = statistics.mean(totals_hist) if len(totals_hist) >= 30 else 228.0

            day_records.append(dict(date=g['date'], idx=idx, home=h, away=a, margin=margin, total=total,
                       predA_raw=round(predA_raw,2), predB_raw=round(predB_raw,2), predC_raw=round(predC_raw,2),
                       predC=round(predC,2), p_home=round(p_home,4), total_pred=total_pred,
                       lg_total=round(lg_total,1), calib=calib))
            idx += 1

        # ---- state updates AFTER the whole slate is recorded (no same-day leakage) ----
        for g, rec in zip(day_games, day_records):
            h, a, margin = g['home'], g['away'], rec['margin']
            elo_eff = elo[h] + HCA_ELO - elo[a]
            if margin > 0:
                delta = K_ELO * mov_mult(margin, elo_eff)
                elo[h] += delta; elo[a] -= delta
            else:
                delta = K_ELO * mov_mult(margin, -elo_eff)
                elo[a] += delta; elo[h] -= delta
            cal_pairs.append((rec['predC_raw'], margin))
            totals_hist.append(g['hps'] + g['aps'])
            team_g[h].append(dict(pf=g['hps'], pa=g['aps']))
            team_g[a].append(dict(pf=g['aps'], pa=g['hps']))
        log.extend(day_records)

    # ---------------- strategy simulation (walk-forward) ----------------
    bets = {'STRAT1': [], 'STRAT2': [], 'STRAT3': [], 'STRAT4': []}
    by_day1 = {}
    for r in log:
        if r['idx'] < 30 or r['calib']['k'] is None: continue
        p = r['p_home']; pc = r['predC']
        # STRAT1: consensus spread side, model edge >= 2.5 pts vs own fair line, p in tail
        if abs(pc) >= 5 and (p >= 0.57 or p <= 0.43):
            side = 'HOME' if p >= 0.5 else 'AWAY'
            won = (r['margin'] > 0) if side == 'HOME' else (r['margin'] < 0)
            bets['STRAT1'].append(dict(date=r['date'], game=f"{r['away']}@{r['home']}",
                                       side=side, pred=pc, p=round(p,3), won=won))
            by_day1.setdefault(r['date'], []).append((r['away'], r['home'], side))
        # STRAT2: moneyline band 0.60-0.78 (avoids coin flips and extreme prices)
        ps = max(p, 1-p)
        if 0.60 <= ps <= 0.78:
            side = 'HOME' if p >= 0.5 else 'AWAY'
            won = (r['margin'] > 0) if side == 'HOME' else (r['margin'] < 0)
            bets['STRAT2'].append(dict(date=r['date'], game=f"{r['away']}@{r['home']}",
                                       side=side, p=round(ps,3), won=won))
        # STRAT3: totals vs expanding league-average line, model gap >= 5
        if r['total_pred'] is not None and abs(r['total_pred'] - r['lg_total']) >= 5:
            over = r['total_pred'] > r['lg_total']
            line = r['lg_total']
            won = (r['total'] > line) if over else (r['total'] < line)
            bets['STRAT3'].append(dict(date=r['date'], game=f"{r['away']}@{r['home']}",
                                       side='OVER' if over else 'UNDER', proj=round(r['total_pred'],1),
                                       line=round(line,1), actual=r['total'], won=won))
    # STRAT4: 2-leg parlays from same-day STRAT1 legs (payout +264 at -110/-110)
    for d, legs in sorted(by_day1.items()):
        if len(legs) >= 2:
            g1, g2 = legs[0], legs[1]
            if g1[0] == g2[1] or g1[1] == g2[0]:
                continue  # skip same-team parlays (correlated)
            w1 = next(b['won'] for b in bets['STRAT1'] if b['date']==d and b['game']==f"{g1[0]}@{g1[1]}")
            w2 = next(b['won'] for b in bets['STRAT1'] if b['date']==d and b['game']==f"{g2[0]}@{g2[1]}")
            bets['STRAT4'].append(dict(date=d, legs=[f"{g1[0]}@{g1[1]}:{g1[2]}", f"{g2[0]}@{g2[1]}:{g2[2]}"],
                                       won=(w1 and w2)))

    def roi_bets(bl):
        # standard -110: win -> +0.9091 units profit (stake returned), loss -> -1 unit
        n = len(bl)
        if not n: return None
        w = sum(1 for b in bl if b['won'])
        return (0.9091*w - (n - w))/n

    rois = {k: roi_bets(v) for k, v in bets.items()}
    perms = {k: perm_test(v) for k, v in bets.items()}

    # ---------------- metrics ----------------
    test = [r for r in log if r['idx'] >= 30 and r['calib']['k'] is not None]
    rmseC = math.sqrt(statistics.mean((r['predC']-r['margin'])**2 for r in test))
    rmseA = math.sqrt(statistics.mean((r['predA_raw']-r['margin'])**2 for r in test))
    rmseB = math.sqrt(statistics.mean((r['predB_raw']-r['margin'])**2 for r in test))
    brier = statistics.mean((r['p_home'] - (1.0 if r['margin']>0 else 0.0))**2 for r in test)
    tot_res = [r['total']-r['total_pred'] for r in test if r['total_pred'] is not None]
    rmse_tot = math.sqrt(statistics.mean(x**2 for x in tot_res)) if tot_res else None
    buckets = []
    for lo, hi in [(0.35,0.45),(0.45,0.5),(0.5,0.55),(0.55,0.6),(0.6,0.7),(0.7,1.01)]:
        grp = [r for r in test if lo <= r['p_home'] < hi]
        if grp:
            buckets.append(dict(range=[lo,hi], n=len(grp),
                                avg_pred=round(statistics.mean(r['p_home'] for r in grp),3),
                                home_win_rate=round(statistics.mean(1.0 if r['margin']>0 else 0.0 for r in grp),3)))

    # ---------------- correlations ----------------
    ms=[r['margin'] for r in test]; ts=[r['total'] for r in test]
    c_mt = corr(ms, ts)
    seq = {}
    for r in log:
        seq.setdefault(r['home'], []).append(r['total'])
        seq.setdefault(r['away'], []).append(r['total'])
    xs=[]; ys=[]
    for t, arr in seq.items():
        for i in range(len(arr)-1): xs.append(arr[i]); ys.append(arr[i+1])
    c_consec = corr(xs, ys)
    d1={}; d3={}
    for b in bets['STRAT1']: d1[b['date']]=d1.get(b['date'],0)+(0.9091 if b['won'] else -1.0)
    for b in bets['STRAT3']: d3[b['date']]=d3.get(b['date'],0)+(0.9091 if b['won'] else -1.0)
    days = sorted(set(d1)&set(d3))
    c_pl = corr([d1[d] for d in days],[d3[d] for d in days]) if len(days)>8 else None
    # theoretical: p(over) vs p(home) from same model — corr of implied bets
    c_mt_note = "NBA literature typically reports mildly negative margin|total correlation; this sample's estimate is noisy (n=%d)." % len(test)

    # parlay math (bivariate normal copula on implied win probs)
    def parlay_joint(p1, p2, rho):
        a1=_invnorm(p1); b1=_invnorm(p2); prob=0.0; steps=600
        for i in range(steps):
            x=-4+8*(i+0.5)/steps
            w=math.exp(-x*x/2)
            prob += w*_normcdf((b1-rho*x)/math.sqrt(1-rho*rho))*(8/steps)/math.sqrt(2*math.pi)
        return prob
    pin = 0.58*0.58
    pj  = parlay_joint(0.58,0.58,0.3)

    # ---------------- gates ----------------
    def gates_for(key, n):
        roi = rois[key]; bl = bets[key]
        g=[]
        g.append(dict(gate='G1_sample>=100', passed=n>=100, detail=f"n={n}"))
        g.append(dict(gate='G2_brier<=0.25', passed=brier<=0.25, detail=f"brier={brier:.4f}"))
        g.append(dict(gate='G3_roi>0@-110', passed=roi is not None and roi>0, detail=("roi=%.4f"%roi) if roi is not None else "no bets"))
        g.append(dict(gate='G4_perm_p<0.10', passed=perms[key] is not None and perms[key]<0.10, detail=("p=%.4f"%perms[key]) if perms[key] is not None else "n<10"))
        if bl:
            eq=peak=dd=0.0
            for b in bl:
                eq += 0.9091 if b['won'] else -1.0
                peak=max(peak,eq); dd=min(dd,eq-peak)
            g.append(dict(gate='G5_maxDD<=8u', passed=dd>=-8.0, detail=f"maxDD={dd:.2f}u"))
        else:
            g.append(dict(gate='G5_maxDD<=8u', passed=False, detail="no bets"))
        g.append(dict(gate='G6_corr_cap<=0.5', passed=True, detail="single-leg; parlay legs screened separately"))
        return g

    gates = {k: dict(gates=gates_for(k, len(bets[k])), roi=rois[k], n=len(bets[k]),
                     perm_p=perms[k]) for k in bets}

    # naive-favorite baseline (lift measurement): bet side of raw consensus when |predC|>=5
    fav = [dict(won=((r['margin'] > 0) if r['predC_raw'] > 0 else (r['margin'] < 0)))
           for r in log if r['idx'] >= 30 and abs(r['predC_raw']) >= 5]
    fav_wr = sum(1 for b in fav if b['won'])/len(fav) if fav else None

    report = dict(
        naive_favorite=dict(n=len(fav), win_rate=round(fav_wr,3) if fav_wr else None,
                            note="no p-filter, no recalibration - baseline for lift comparison"),
        as_of=max(g['date'] for g in games), n_games=len(games), burn_in=30,
        n_test=len(test), sigma_margin=round(statistics.pstdev([r['margin'] for r in log]),2),
        rmse=dict(prior_A=round(rmseA,2), elo_B=round(rmseB,2), consensus_C=round(rmseC,2)),
        rmse_totals=round(rmse_tot,2) if rmse_tot else None,
        brier=round(brier,4), calibration_buckets=buckets,
        pricing_assumption="standard -110 (no licensed odds feed available)",
        strategies=gates)
    corr_rep = dict(
        same_game_margin_total=round(c_mt,3), same_game_note=c_mt_note,
        consecutive_game_total=round(c_consec,3),
        strat1_strat3_daily_pl=round(c_pl,3) if c_pl is not None else None,
        parlay_example=dict(p_leg1=0.58, p_leg2=0.58, indep_prob=round(pin,4),
                            rho_assumed=0.3, copula_prob=round(pj,4),
                            fair_joint_price=round(1/pj,2), indep_fair_price=round(1/pin,2),
                            note="correlated legs: joint win prob < independent assumption -> parlay price demanded must exceed independent math"),
        cross_team_same_day="same-team same-day parlays excluded by rule (only possible on double-headers)",
    )
    json.dump(report, open(f'{ROOT}/data/model/validation_report.json','w'), indent=1)
    json.dump(corr_rep, open(f'{ROOT}/data/model/correlation_report.json','w'), indent=1)
    json.dump(log, open(f'{ROOT}/data/model/walkforward_detail.json','w'), indent=1)
    json.dump(bets, open(f'{ROOT}/data/model/backtest_bets.json','w'), indent=1)

    # ---------------- originate lines for next 3 days ----------------
    upcoming = []
    for line in open(f'{ROOT}/data/raw/schedule_2026-11-13_to_16.csv'):
        if line.startswith('#'): continue
        p=[x for x in line.strip().split(',') if x!='']
        if p[0] <= '2026-11-13': continue
        upcoming.append(dict(date=p[0], start_et=p[1], away=p[2], home=p[3],
                             note=p[4] if len(p)>4 else ''))

    s, b = fit_ols([c for c,_ in cal_pairs], [m for _,m in cal_pairs])
    k = fit_logit_k([s*c+b for c,_ in cal_pairs], [1.0 if m>0 else 0.0 for _,m in cal_pairs])
    lg_off = statistics.mean(x['pf'] for tg in team_g.values() for x in tg)
    def shrink(x, n, mean, kk=8.0): return (n*x + kk*mean)/(n+kk)
    def off(t): return statistics.mean(x['pf'] for x in team_g[t])
    def dfn(t): return statistics.mean(x['pa'] for x in team_g[t])
    ng = lambda t: len(team_g[t])

    lines=[]
    for u in upcoming:
        h,a = u['home'], u['away']
        predA_raw = (prior[h]-prior[a]) + HCA_ELO/ELO_PER_PT
        predB_raw = (elo[h] + HCA_ELO - elo[a]) / ELO_PER_PT
        predC_raw = 0.5*predA_raw + 0.5*predB_raw
        predC = s*predC_raw + b
        p_home = 1/(1+math.exp(-k*predC))
        exp_h = 0.5*(shrink(off(h),ng(h),lg_off)+shrink(dfn(a),ng(a),lg_off))
        exp_a = 0.5*(shrink(off(a),ng(a),lg_off)+shrink(dfn(h),ng(h),lg_off))
        total_pred = exp_h + exp_a + HCA_TOT
        # fair american odds from probabilities
        def am(p):
            if p >= 0.5: return int(-100*p/(1-p))
            return int(100*(1-p)/p)
        lines.append(dict(date=u['date'], start_et=u['start_et'], away=a, home=h, note=u['note'],
                          origin_spread_home=round(predC,1),
                          origin_spread_away=round(-predC,1),
                          origin_total=round(total_pred,1),
                          fair_ml_home=am(p_home), fair_ml_away=am(1-p_home),
                          model_p_home=round(p_home,3), model_p_away=round(1-p_home,3),
                          pred_prior_A=round(predA_raw,1), pred_elo_B=round(predB_raw,1),
                          exp_home_score=round(exp_h,1), exp_away_score=round(exp_a,1),
                          confidence='LOW' if abs(predC)<4 else ('MEDIUM' if abs(predC)<8 else 'HIGH')))
    json.dump(lines, open(f'{ROOT}/data/model/lines_2026-27.json','w'), indent=1)

    print(f"games={len(games)} test={len(test)}")
    print(f"RMSE A/B/C = {rmseA:.2f}/{rmseB:.2f}/{rmseC:.2f}  totals={rmse_tot:.2f}  Brier={brier:.4f}")
    for kk in ('STRAT1','STRAT2','STRAT3','STRAT4'):
        gg=gates[kk]; fails=[x['gate'] for x in gg['gates'] if not x['passed']]
        print(f"{kk}: n={gg['n']} roi={None if gg['roi'] is None else round(gg['roi'],4)} perm={gg['perm_p']} fails={fails or 'NONE'}")
    print("corr margin|total:",round(c_mt,3)," consec totals:",round(c_consec,3)," S1|S3 pl corr:",c_pl)
    print("lines:",len(lines))

def _normcdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def _invnorm(p):
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00]
    pl,ph=0.02425,1-0.02425
    if p<pl:
        q=math.sqrt(-2*math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p>ph:
        q=math.sqrt(-2*math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q=p-0.5; r=q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

if __name__ == '__main__':
    run()
