import sys; sys.path.insert(0,'src')
from polymarket import PolymarketSource
from teams import teams_match
from team_stats import _rate, _LEAGUE_AVG, _load, _opponent_adjusted_lam
from poisson import prob_at_least, estimate_lambda_from_match_odds
_load()

src = PolymarketSource()
odds = src.fetch_match_odds()
arg = next(o for o in odds if teams_match('Argentina', o.home_team) or teams_match('Argentina', o.away_team))

print('=== Model calculation ===')
own = _rate('Argentina', 'shots_on_target_per_match')
opp = _rate('Cape Verde Islands', 'sot_conceded_per_match')
avg = _LEAGUE_AVG['sot_conceded_per_match']
adj = _opponent_adjusted_lam('Argentina','Cape Verde Islands','shots_on_target_per_match','sot_conceded_per_match')
print(f'Argentina own SOT/match: {own}')
print(f'Cape Verde concedes SOT/match: {opp} (league avg={round(avg,2)})')
print(f'Adjusted lambda (alpha=0.25): {round(adj,3)}')
print()
for t in [5,6,7,8,9,10,12]:
    print(f'  P({t}+): {round(prob_at_least(t, adj)*100,1)}%')

print()
print('=== Polymarket player SOT data for ARG vs CPV ===')
if arg.player_props:
    sot = [(k,round(v*100,1)) for k,v in arg.player_props.items() if k[1]=='player_shots_on_target']
    print(f'{len(sot)} player SOT lines:')
    for k,v in sorted(sot, key=lambda x:(x[0][0],x[0][2] or 0)):
        print(f'  {k} -> {v}%')
else:
    print('No player props yet')

print()
print('=== Team total SOT estimate from player SOT sum ===')
if arg.player_props:
    import math
    from poisson import poisson_pmf
    # For each player, derive their SOT lambda from their P(1+ SOT) market
    # lambda = -ln(1 - P(1+))
    player_lams = {}
    for (player, mkt, threshold), prob in arg.player_props.items():
        if mkt == 'player_shots_on_target' and threshold == 1.0 and 0 < prob < 0.98:
            lam = -math.log(1 - prob)
            player_lams[player] = lam

    if player_lams:
        total_lam = sum(player_lams.values())
        print(f'Sum of tracked player SOT lambdas: {round(total_lam, 2)}')
        print('(This is a lower bound — not all players tracked)')
        for t in [6,7,8,9,10]:
            p = prob_at_least(t, total_lam)
            print(f'  P({t}+ team SOT from player sum): {round(p*100,1)}%')
    else:
        print('No player SOT 1+ markets found')
