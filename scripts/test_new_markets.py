"""Test new market parsers and probability calculations."""
import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from matcher import parse_market_question, probability_for_market
from teams import teams_match

src = PolymarketSource()
odds_list = src.fetch_match_odds()

par_fra = next((o for o in odds_list if teams_match('Paraguay', o.home_team)), None)
por_esp = next((o for o in odds_list if teams_match('Portugal', o.home_team)), None)
usa_bel = next((o for o in odds_list if teams_match('United States', o.home_team)), None)

print(f'PAR vs FRA found: {par_fra is not None}')
print(f'POR vs ESP found: {por_esp is not None}')
print(f'USA vs BEL found: {usa_bel is not None}')
print()

test_cases = [
    ('Will a substitute score a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'PAR vs FRA', par_fra),
    ('Will Paraguay hold a lead at any point in the match (excluding a penalty shootout)?', 'PAR vs FRA', par_fra),
    ('Will a penalty kick be awarded during regulation (90 minutes + stoppage time)?', 'PAR vs FRA', par_fra),
    ('Will both halves have the same number of goals in regulation (90 minutes + stoppage time)?', 'POR vs ESP', por_esp),
    ('Will the first card of the match be shown before the first goal is scored?', 'POR vs ESP', por_esp),
    ('Will Diogo Costa (Portugal) make 4 or more saves in regulation (90 minutes + stoppage time)?', 'POR vs ESP', por_esp),
    ('Will a substitute score a goal (excluding own goals) in regulation (90 minutes + stoppage time)?', 'POR vs ESP', por_esp),
    ('Will there be 9 or more total substitutions (both teams combined) in regulation (90 minutes + stoppage time)?', 'POR vs ESP', por_esp),
    ('Will the match go to extra time?', 'POR vs ESP', por_esp),
    ('Will Christian Pulisic (United States) play the entire match in regulation (90 minutes + stoppage time)?', 'USA vs BEL', usa_bel),
]

for q, match, odds in test_cases:
    lookup = parse_market_question(q, match)
    if lookup is None:
        print(f'UNMATCHED: {q[:70]}')
        continue
    if odds:
        p = probability_for_market(lookup, odds, match)
        pct = f'{round(p*100):3}%' if p is not None else 'None'
        print(f'{pct}  [{lookup.kind.value:<28}]  {q[:65]}')
    else:
        print(f'  NO ODDS  [{lookup.kind.value}]  {q[:65]}')
