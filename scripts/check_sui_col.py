import sys, math
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from teams import teams_match

src = PolymarketSource()
odds_list = src.fetch_match_odds()
o = next(o for o in odds_list if teams_match('Switzerland', o.home_team))

# First goal H2: P(no goal H1) * P(goal H2)
p_h1 = o.first_half_totals[0.5]
p_h2 = o.second_half_totals[0.5]
p_no_h1 = 1 - p_h1
print(f'P(goal H1)={p_h1:.3f}  P(no goal H1)={p_no_h1:.3f}  P(goal H2)={p_h2:.3f}')
print(f'P(first goal H2) = {p_no_h1:.3f} * {p_h2:.3f} = {p_no_h1*p_h2:.3f} ({round(p_no_h1*p_h2*100)}%)')

# Win by one goal from exact scores
exact = o.exact_score_probs
total = sum(exact.values())
p_one = sum(p for (h,a),p in exact.items() if abs(h-a)==1)
print(f'\nExact score sum={total:.3f}')
print(f'P(|h-a|=1) raw={p_one:.3f}  scaled={p_one/total:.3f} ({round(p_one/total*100)}%)')
scores_by_diff = {}
for (h,a),p in exact.items():
    d = abs(h-a)
    scores_by_diff.setdefault(d, []).append(((h,a), round(p*100)))
print('  diff=1:', scores_by_diff.get(1))

# Either team wins both halves
ht1 = o.first_half_team_totals
ht2 = o.second_half_team_totals
print(f'\nH1 team totals: {ht1}')
print(f'H2 team totals: {ht2}')
# Switzerland H1 lead: 0.215, Colombia H1 lead: 0.305 (from halftime_lead)
# Switzerland H2 win: need to compute from lams
sui_h1_lead = ht1.get('Switzerland', {}).get('halftime_lead', '?')
col_h1_lead = ht1.get('Colombia', {}).get('halftime_lead', '?')
print(f'SUI leads H1: {sui_h1_lead}  COL leads H1: {col_h1_lead}')
sui_h1_05 = ht1.get('Switzerland', {}).get(0.5, '?')
col_h1_05 = ht1.get('Colombia', {}).get(0.5, '?')
sui_h2_05 = ht2.get('Switzerland', {}).get(0.5, '?')
col_h2_05 = ht2.get('Colombia', {}).get(0.5, '?')
print(f'SUI scores H1: {sui_h1_05}  COL scores H1: {col_h1_05}')
print(f'SUI scores H2: {sui_h2_05}  COL scores H2: {col_h2_05}')

# Card each half
from team_stats import _rate, _load, _CARDS_SCALE
_load()
lam_total = (_rate('Switzerland','cards_per_match') + _rate('Colombia','cards_per_match')) * _CARDS_SCALE
lam_half = lam_total / 2.0
p_card_h1 = 1 - math.exp(-lam_half)
p_card_h2 = 1 - math.exp(-lam_half)
print(f'\nCards lambda={lam_total:.2f}  half_lam={lam_half:.2f}')
print(f'P(card H1)={p_card_h1:.3f}  P(card H2)={p_card_h2:.3f}')
print(f'P(card each half)={p_card_h1*p_card_h2:.3f} ({round(p_card_h1*p_card_h2*100)}%)')
