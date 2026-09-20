import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from teams import teams_match
import math

src = PolymarketSource()
odds_list = src.fetch_match_odds()

for o in odds_list:
    if teams_match('Argentina', o.home_team):
        print(f'ARG vs SUI - halftime 0-0')
        ft = o.first_half_totals or {}
        p_no_goal_h1 = 1 - ft.get(0.5, 0)
        print(f'  P(no goal H1) = 1 - {ft.get(0.5)} = {p_no_goal_h1:.3f} ({round(p_no_goal_h1*100)}%)')
        # Also from exact scores: P(0-0 HT) = P(H1 scoreless)
        # exact_score_probs are full-time, not half-time
        # But P(0-0 FT) gives lower bound
        p_00_ft = (o.exact_score_probs or {}).get((0,0), 0)
        print(f'  P(0-0 FT) from exact scores = {p_00_ft:.3f}')
        # halftime_draw includes 0-0, 1-1 etc - not just 0-0
        ht_draw = ft.get('halftime_draw')
        print(f'  P(halftime draw) from Polymarket = {ht_draw}')
        # P(0-0 at HT) is P(no goals in H1)
        # = 1 - first_half_totals[0.5] 
        print(f'  => P(0-0 at HT) = {p_no_goal_h1:.3f} ({round(p_no_goal_h1*100)}%)')

    if teams_match('Norway', o.home_team):
        print()
        print('NOR vs ENG - England more corners AND more shots')
        if o.player_props:
            eng_corners = {k: v for k, v in o.player_props.items() if 'corner' in k[1] and 'england' in k[0]}
            nor_corners = {k: v for k, v in o.player_props.items() if 'corner' in k[1] and 'norway' in k[0]}
            print(f'  England corner lines: {[(k[2], round(v*100)) for k,v in eng_corners.items()]}')
            print(f'  Norway corner lines: {[(k[2], round(v*100)) for k,v in nor_corners.items()]}')
        print(f'  This is a compound AND market:')
        print(f'  P(ENG more corners AND ENG more shots)')
        print(f'  These are correlated (dominant teams tend to have both)')
        print(f'  Can compute separately and multiply with correlation adjustment')

    if teams_match('Spain', o.home_team):
        print()
        print('ESP vs BEL - halftime substitution')
        # Historical: ~15-20% of teams make a halftime substitution
        # P(either team makes HT sub) = 1 - P(neither does) = 1 - 0.82*0.82 = 0.33
        p_either = 1 - (0.82 * 0.82)
        print(f'  P(either team subs at HT) = 1 - 0.82^2 = {p_either:.3f} ({round(p_either*100)}%)')
