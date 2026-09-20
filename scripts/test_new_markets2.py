"""Test the three new markets for ARG vs EGY."""
import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from matcher import parse_market_question, probability_for_market
from teams import teams_match

src = PolymarketSource()
odds_list = src.fetch_match_odds()
arg_egy = next((o for o in odds_list if teams_match('Argentina', o.home_team)), None)
print(f'ARG vs EGY found: {arg_egy is not None}')
print()

test_cases = [
    ('Will the total number of goals in regulation (90 minutes + stoppage time) be an odd number?', 'ARG vs EGY'),
    ('Will a goal be scored in the first half after the first hydration break?', 'ARG vs EGY'),
    ('Will the first goal of the match be scored by a player other than Lionel Messi (Argentina, #10) and Mohamed Salah (Egypt, #10)?', 'ARG vs EGY'),
    # Verify original three hydration markets still work
    ('Will a goal be scored before the first hydration break in regulation (90 minutes + stoppage time)?', 'ARG vs EGY'),
    ('Will a goal be scored after the second hydration break in regulation (90 minutes + stoppage time)?', 'ARG vs EGY'),
]

for q, match in test_cases:
    lookup = parse_market_question(q, match)
    if lookup is None:
        print(f'UNMATCHED: {q[:80]}')
        continue
    p = probability_for_market(lookup, arg_egy, match) if arg_egy else None
    pct = f'{round(p*100):3}%' if p is not None else 'None'
    print(f'{pct}  [{lookup.kind.value:<32}]  {q[:70]}')
    if lookup.players:
        print(f'       players={lookup.players}')
