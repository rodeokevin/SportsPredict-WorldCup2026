"""Verify the goal_or_assist fix across all active matches."""
import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from matcher import parse_market_question, probability_for_market, MarketKind, MarketLookup
from teams import teams_match

src = PolymarketSource()
odds_list = src.fetch_match_odds()

test_questions = [
    ('Will Julián Álvarez (Argentina, #9) score or assist a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'ARG vs SUI'),
    ('Will Lamine Yamal (Spain, #19) score or assist a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'ESP vs BEL'),
    ('Will Kevin De Bruyne (Belgium, #7) score or assist a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'ESP vs BEL'),
    ('Will Achraf Hakimi (Morocco, #2) score or assist a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'FRA vs MAR'),
]

def find_odds(match_name, odds_list):
    parts = match_name.split(' vs ')
    if len(parts) != 2:
        return None
    h, a = parts
    for o in odds_list:
        if (teams_match(h.strip(), o.home_team) or teams_match(h.strip(), o.away_team)) and \
           (teams_match(a.strip(), o.home_team) or teams_match(a.strip(), o.away_team)):
            return o
    return None

for q, match in test_questions:
    odds = find_odds(match, odds_list)
    lookup = parse_market_question(q, match)
    if not lookup or not odds:
        print(f'  SKIP: {match}')
        continue

    p = probability_for_market(lookup, odds, match)

    # Also show the raw components
    player = lookup.player or ''
    p_goal  = odds.get_player_prop(player, 'player_anytime_goalscorer', 1.0)
    p_assist = odds.get_player_prop(player, 'player_assists', 1.0)
    p_ga_raw = odds.get_player_prop(player, 'player_goal_or_assist', None)

    print(f'{match}: {player}')
    print(f'  PM goal={round(p_goal*100) if p_goal else "?"  }%  '
          f'PM assist={round(p_assist*100) if p_assist else "?"}%  '
          f'PM combined_raw={round(p_ga_raw*100) if p_ga_raw else "?"}%')
    print(f'  => New P(goal or assist) = {round(p*100) if p else "?"}%')
    print()
