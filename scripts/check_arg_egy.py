import sys, math
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from teams import teams_match
from poisson import estimate_lambda_from_match_odds, prob_goal_in_window, poisson_pmf

src = PolymarketSource()
odds_list = src.fetch_match_odds()
o = next(o for o in odds_list if teams_match('Argentina', o.home_team))

# 1. Odd goals
print('Odd goals from exact_score_probs:')
p_odd  = sum(p for (h,a),p in o.exact_score_probs.items() if (h+a)%2==1)
p_even = sum(p for (h,a),p in o.exact_score_probs.items() if (h+a)%2==0)
print(f'  P(odd)={p_odd:.3f}  P(even)={p_even:.3f}  sum={p_odd+p_even:.3f}')

# Note: exact_score_probs don't sum to 1 (Polymarket covers only the most likely scores)
# So P(odd) from this is actually a lower bound — we need to scale
total = sum(o.exact_score_probs.values())
print(f'  Sum of all exact probs = {total:.3f} (Polymarket only covers subset of outcomes)')
p_odd_scaled = p_odd / total
print(f'  Scaled P(odd) = {p_odd:.3f}/{total:.3f} = {p_odd_scaled:.3f} ({round(p_odd_scaled*100)}%)')

# Also compute from Poisson
lam = estimate_lambda_from_match_odds(o)
print(f'\nlambda from totals = {lam:.3f}')
p_odd_poisson = sum(poisson_pmf(k, lam) for k in range(1, 15, 2))
print(f'Poisson P(odd goals) = {p_odd_poisson:.3f} ({round(p_odd_poisson*100)}%)')

# 2. Hydration windows
p_before = prob_goal_in_window(lam, 22.5, start=0.0)
p_after_h1 = prob_goal_in_window(lam, 22.5, start=22.5)
p_after_h2 = prob_goal_in_window(lam, 22.5, start=67.5)
print(f'\nGoal [0-22.5] before break:   {p_before:.3f} ({round(p_before*100)}%)')
print(f'Goal [22.5-45] after H1 break: {p_after_h1:.3f} ({round(p_after_h1*100)}%)')
print(f'Goal [67.5-90] after H2 break: {p_after_h2:.3f} ({round(p_after_h2*100)}%)')
print(f'Polymarket H1 over 0.5:        {o.first_half_totals.get(0.5)}')

# 3. First goal not Messi/Salah
print()
fgp = o.first_goal_probs
print(f'first_goal_probs: {fgp}')
messi_p = o.get_player_prop('lionel messi', 'player_anytime_goalscorer', 1.0)
salah_p  = o.get_player_prop('mohamed salah', 'player_anytime_goalscorer', 1.0)
print(f'Messi anytime goal: {messi_p}')
print(f'Salah anytime goal: {salah_p}')
lam_messi = -math.log(1 - messi_p) if messi_p and messi_p < 1 else 0
lam_salah = -math.log(1 - salah_p)  if salah_p and salah_p < 1 else 0
p_any_goal = 1 - math.exp(-lam)
p_messi_first = lam_messi / lam
p_salah_first = lam_salah / lam
p_not_named = p_any_goal - p_messi_first - p_salah_first
print(f'P(any goal)    = {p_any_goal:.3f}')
print(f'P(Messi first) = {p_messi_first:.3f}')
print(f'P(Salah first) = {p_salah_first:.3f}')
print(f'P(not named)   = {p_not_named:.3f} ({round(p_not_named*100)}%)')
