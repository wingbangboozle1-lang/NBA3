#!/usr/bin/env python3
"""
Originate sample player-prop lines for the 3-day window.

* Season averages are SOURCED data (Basketball-Reference 2026-27 per-game table,
  retrieved 2026-11-13 — link embedded per row).
* Our originated line = rounded season average; over/under probabilities use a normal
  approximation with a DOCUMENTED, UNVALIDATED volatility assumption (sd = 0.30 x mean
  for points, 0.35 x mean for rebounds/assists). This is a research prototype.
* The props strategy is NOT validated: no player-level backtest sample exists yet.
  Every row is published as research-only and flagged accordingly.
"""
import json, math, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "https://www.basketball-reference.com/leagues/NBA_2027_per_game.html"

AVG = {  # player: team, games, pts, trb, ast (2026-27 season, BBR per game, as of 2026-11-13)
  "Luka Dončić": ("LAL", 11, 38.6, 7.5, 7.6),
  "Anthony Edwards": ("MIN", 4, 33.3, 4.8, 3.5),
  "Victor Wembanyama": ("SAS", 12, 30.3, 11.7, 2.8),
  "Shai Gilgeous-Alexander": ("OKC", 12, 29.7, 4.3, 4.5),
  "Giannis Antetokounmpo": ("MIA", 11, 27.7, 12.6, 5.2),
  "Tyrese Maxey": ("PHI", 13, 26.7, 3.4, 5.5),
  "Jayson Tatum": ("BOS", 11, 26.3, 6.1, 7.5),
  "Jalen Brunson": ("NYK", 11, 26.0, 3.1, 5.2),
  "Anthony Davis": ("WAS", 11, 25.6, 10.5, 2.0),
  "Devin Booker": ("PHO", 11, 25.5, 2.5, 5.0),
  "Cade Cunningham": ("DET", 11, 25.0, 5.2, 7.9),
  "Cooper Flagg": ("DAL", 11, 24.6, 6.9, 6.5),
  "Nikola Jokić": ("DEN", 10, 23.5, 10.8, 9.0),
  "Donovan Mitchell": ("CLE", 12, 22.8, 5.0, 5.5),
  "Pascal Siakam": ("IND", 11, 22.7, 6.9, 4.4),
}

GAMES = json.load(open(f'{ROOT}/data/model/lines_2026-27.json'))
INJ = json.load(open(f'{ROOT}/data/injuries/injury_report_2026-11-13.json'))

def game_for(team, date):
    for g in GAMES:
        if g['date'] == date and team in (g['home'], g['away']):
            return g
    return None

def status_note(team, date):
    for d, games in INJ['games'].items():
        if d != date or not isinstance(games, dict): continue
        for key, teams in games.items():
            if team in key.split('@') and isinstance(teams, dict):
                for t, rows in teams.items():
                    if t == team and isinstance(rows, list):
                        for r in rows:
                            if r['player'].split(',')[0].lower() in ''.join(AVG).lower() or True:
                                pass
    return None

def p_over(line, mean, sd):
    if sd <= 0: return 0.5
    return 0.5 * (1 + math.erf((mean - line) / (sd * math.sqrt(2))))

props = []
window = ["2026-11-14", "2026-11-15", "2026-11-16"]
targets = [
    ("Luka Dončić", "2026-11-15"), ("Devin Booker", "2026-11-15"),
    ("Jayson Tatum", "2026-11-15"), ("Nikola Jokić", "2026-11-14"),
    ("Cade Cunningham", "2026-11-14"), ("Giannis Antetokounmpo", "2026-11-14"),
    ("Anthony Davis", "2026-11-15"), ("Cooper Flagg", "2026-11-15"),
    ("Victor Wembanyama", "2026-11-15"), ("Tyrese Maxey", "2026-11-15"),
]
for player, date in targets:
    team, g, pts, trb, ast = AVG[player]
    game = game_for(team, date)
    if not game:
        continue
    opp = game['away'] if game['home'] == team else game['home']
    row = dict(player=player, team=team, date=date, matchup=f"{game['away']} @ {game['home']}",
               games_played=g, source=SRC, source_note="2026-27 per-game averages, retrieved 2026-11-13",
               markets=[])
    for stat, mean, sd_mult in (("points", pts, 0.30), ("rebounds", trb, 0.35), ("assists", ast, 0.35)):
        if mean <= 0: continue
        line = round(mean)
        sd = sd_mult * mean
        p_over_line = p_over(line + 0.5, mean, sd)  # continuous correction
        row['markets'].append(dict(stat=stat, origin_line=line,
                                   p_over=round(1 - p_over_line, 3), p_under=round(p_over_line, 3),
                                   fair_over_price=int(-100 * (1 - p_over_line) / p_over_line) if p_over_line > 0.5
                                   else int(100 * p_over_line / (1 - p_over_line)),
                                   vol_assumption=f"sd = {sd_mult} x mean (UNVALIDATED assumption)"))
    props.append(row)

out = dict(
    generated_on=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    window=window,
    validation_status="NOT VALIDATED — player-prop strategy has no backtest sample yet; research only.",
    props=props)
json.dump(out, open(f'{ROOT}/data/picks/props_2026-11-14_to_16.json', 'w'), indent=1)
print(f"props originated: {len(props)} players / {sum(len(p['markets']) for p in props)} markets")
