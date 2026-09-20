"""Test five new markets for SUI vs COL."""
import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from matcher import parse_market_question, probability_for_market
from teams import teams_match

src = PolymarketSource()
odds_list = src.fetch_match_odds()
sui_col = next((o for o in odds_list if teams_match('Switzerland', o.home_team)), None)
print(f'SUI vs COL found: {sui_col is not None}')
print()

test_cases = [
    ('Will a substitute score or assist a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'SUI vs COL'),
    ('Will the first goal of the match be scored in the second half of regulation (90 minutes + stoppage time)?', 'SUI vs COL'),
    ('Will either team win both halves in regulation (90 minutes + stoppage time)?', 'SUI vs COL'),
    ('Will the match be decided by exactly one goal in regulation (90 minutes + stoppage time)?', 'SUI vs COL'),
    ('Will at least one card be shown in each half of regulation (90 minutes + stoppage time)?', 'SUI vs COL'),
    # Verify original SUB_SCORES still works
    ('Will a substitute score a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'SUI vs COL'),
]

for q, match in test_cases:
    lookup = parse_market_question(q, match)
    if lookup is None:
        print(f'UNMATCHED: {q[:80]}')
        continue
    p = probability_for_market(lookup, sui_col, match) if sui_col else None
    pct = f'{round(p*100):3}%' if p is not None else 'None'
    print(f'{pct}  [{lookup.kind.value:<35}]  {q[:65]}')
