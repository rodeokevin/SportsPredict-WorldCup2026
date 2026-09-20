
"""Check all open SportsPredict markets against current Polymarket data."""
import sys, os
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from client import SportsPredictClient
from polymarket import PolymarketSource
from matcher import parse_market_question, probability_for_market
from teams import teams_match
from collections import defaultdict

key = os.environ.get('SPORTSPREDICT_API_KEY', '')
client = SportsPredictClient(key)
event = client.get_probability_cup_event()
lobby = client.get_lobby(event['id'])
preds = {p['market_id']: p for p in client.list_predictions(lobby['id'])}
all_markets = client.fetch_all_markets(event['id'], lobby['id'])
open_mkts = [m for m in all_markets if m.get('status') == 'open']

by_match = defaultdict(list)
for m in open_mkts:
    mn = (m.get('match') or {}).get('name', '')
    by_match[mn].append(m)

src = PolymarketSource()
pm_odds = src.fetch_match_odds()


def find_pm(match_name):
    parts = match_name.split(' vs ')
    if len(parts) != 2:
        return None
    h, a = parts[0].strip(), parts[1].strip()
    for o in pm_odds:
        if (teams_match(h, o.home_team) or teams_match(h, o.away_team)) and \
           (teams_match(a, o.home_team) or teams_match(a, o.away_team)):
            return o
    return None


# Show SUI vs ALG first
target = ['SUI vs ALG'] + sorted(k for k in by_match if k != 'SUI vs ALG')

for mn in target:
    markets = by_match.get(mn, [])
    if not markets:
        continue
    pm = find_pm(mn)

    print(f'\n{"="*75}')
    print(f'  {mn}')
    print(f'{"="*75}')

    if pm:
        ht_draw = (pm.first_half_totals or {}).get('halftime_draw')
        print(f'  Polymarket: win={round(pm.home_win*100) if pm.home_win else "?"}'
              f'% draw={round(pm.draw*100) if pm.draw else "?"}%'
              f'  ht_draw={round(ht_draw*100) if ht_draw else "?"}%'
              f'  shootout={round(pm.penalty_shootout_prob*100) if pm.penalty_shootout_prob else "?"}%'
              f'  advance={round(pm.advance_prob*100) if pm.advance_prob else "?"}%')
        if pm.first_goal_probs:
            print(f'  First goal: {", ".join(f"{t}={round(v*100)}%" for t,v in pm.first_goal_probs.items())}')
        if pm.player_props:
            corners = [(k, round(v*100,1)) for k, v in pm.player_props.items() if 'corner' in k[1]]
            if corners:
                print(f'  Corners ({len(corners)} lines): e.g. {corners[0]}')
            sot_players = sorted(set(k[0] for k in pm.player_props if k[1] == 'player_shots_on_target'))
            goal_players = sorted(set(k[0] for k in pm.player_props if k[1] == 'player_anytime_goalscorer'))
            if goal_players:
                print(f'  Goal props: {goal_players[:6]}')
            if sot_players:
                print(f'  SOT props:  {sot_players[:6]}')
    else:
        print('  Polymarket: not found')

    print()
    for m in markets:
        mid = m['id']
        q = m.get('question', '')
        our_prob = preds.get(mid, {}).get('probability', '---')

        # Try computing from Polymarket
        pm_prob = None
        if pm:
            lookup = parse_market_question(q, mn)
            if lookup:
                try:
                    computed = probability_for_market(lookup, pm, mn)
                    if computed is not None:
                        pm_prob = round(computed * 100)
                except Exception:
                    pass

        match_indicator = ''
        if our_prob != '---' and pm_prob is not None:
            diff = abs(int(our_prob) - pm_prob)
            if diff >= 10:
                match_indicator = f'  *** DIFF={diff}%'
            elif diff >= 5:
                match_indicator = f'  (diff={diff}%)'

        pm_str = f'  PM={pm_prob}%' if pm_prob is not None else '  PM=?'
        print(f'  [{our_prob:>3}%]{pm_str}  {q[:70]}{match_indicator}')
