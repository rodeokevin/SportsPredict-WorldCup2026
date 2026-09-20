"""Diagnose Julián Álvarez goal or assist probability."""
import sys, math
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from teams import teams_match
from player_stats import get_player_stat, estimate_player_goal_probability, estimate_player_assist_probability, estimate_player_goal_or_assist_probability

src = PolymarketSource()
odds_list = src.fetch_match_odds()
arg = next((o for o in odds_list if teams_match('Argentina', o.home_team) or teams_match('Argentina', o.away_team)), None)
print(f'ARG match: {arg.home_team} vs {arg.away_team}' if arg else 'not found')

# What does Polymarket have for Álvarez?
if arg and arg.player_props:
    for k, v in sorted(arg.player_props.items()):
        if 'alvarez' in k[0] or 'julian' in k[0]:
            print(f'  PM: {k} -> {round(v*100)}%')

print()
# What does get_player_prop return?
if arg:
    g_a = arg.get_player_prop('Julián Álvarez', 'player_goal_or_assist', None)
    g_a2 = arg.get_player_prop('Julian Alvarez', 'player_goal_or_assist', None)
    g_a3 = arg.get_player_prop('Julián Álvarez', 'player_goal_or_assist', 1.0)
    print(f'get_player_prop("Julián Álvarez", goal_or_assist, None) = {g_a}')
    print(f'get_player_prop("Julian Alvarez", goal_or_assist, None) = {g_a2}')
    print(f'get_player_prop("Julián Álvarez", goal_or_assist, 1.0)  = {g_a3}')

print()
# Historical data
d = get_player_stat('Julián Álvarez', 'Argentina')
print(f'Historical data: {d}')
m = d.get('matches', 0)
g = d.get('goals', 0)
a = d.get('assists', 0)
print(f'  goals/game={g/m:.3f}  assists/game={a/m:.3f}' if m > 0 else '  no data')

p_goal = estimate_player_goal_probability('Julián Álvarez', 'Argentina')
p_assist = estimate_player_assist_probability('Julián Álvarez', 'Argentina')
p_ga = estimate_player_goal_or_assist_probability('Julián Álvarez', 'Argentina')
print(f'  Model P(goal)={p_goal:.3f}  P(assist)={p_assist:.3f}  P(g+a)={p_ga:.3f} ({round(p_ga*100)}%)')

print()
# +110 implies:
implied = 100/210
total_implied = implied + 100/210  # symmetric would be -110/-110
# Actually +110 with no listed under odds - de-vig assuming -115 for No
over_implied = 100/210
under_implied = 115/215
total = over_implied + under_implied
fair = over_implied / total
print(f'+110 over:  implied={over_implied:.3f}')
print(f'-115 under: implied={under_implied:.3f}')
print(f'Fair P(goal or assist): {fair:.3f} ({round(fair*100)}%)')
print()
print('Polymarket has 26% but bookmaker implies ~47%. What does PM actually have?')
