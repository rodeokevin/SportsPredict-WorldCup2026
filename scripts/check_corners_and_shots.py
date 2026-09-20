"""Trace the England more corners AND more shots calculation."""
import sys, math
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from polymarket import PolymarketSource
from teams import teams_match
from team_stats import _opponent_adjusted_lam, _rate, _load
from poisson import poisson_pmf, prob_at_least
import unicodedata

_load()

src = PolymarketSource()
odds_list = src.fetch_match_odds()
nor_eng = next((o for o in odds_list if teams_match('Norway', o.home_team)), None)
print(f'NOR vs ENG found: {nor_eng is not None}')
print()

team_a = 'England'
team_b = 'Norway'

def _norm_t(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

def _lam_from_ou(line, p_over):
    n = int(math.ceil(line + 0.5))
    lo, hi = 0.01, 25.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if prob_at_least(n, mid) < p_over:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

# ---- CORNERS from Polymarket ----
print('=== CORNERS ===')
norm_a = _norm_t(team_a)
norm_b = _norm_t(team_b)
lines_a = {}
lines_b = {}
if nor_eng and nor_eng.player_props:
    for (pname, mkt, line), prob in nor_eng.player_props.items():
        if mkt != 'team_corners_line' or line is None:
            continue
        if set(norm_a.split()).issubset(set(pname.split())):
            lines_a[line] = prob
        elif set(norm_b.split()).issubset(set(pname.split())):
            lines_b[line] = prob

print(f'England corner O/U lines: {dict(sorted(lines_a.items()))}')
print(f'Norway  corner O/U lines: {dict(sorted(lines_b.items()))}')

if lines_a and lines_b:
    best_a = min(lines_a.items(), key=lambda kv: abs(kv[1] - 0.5))
    best_b = min(lines_b.items(), key=lambda kv: abs(kv[1] - 0.5))
    lam_corners_a = _lam_from_ou(best_a[0], best_a[1])
    lam_corners_b = _lam_from_ou(best_b[0], best_b[1])
    print(f'Best England line: O{best_a[0]} at {best_a[1]:.1%} -> lambda={lam_corners_a:.2f}')
    print(f'Best Norway  line: O{best_b[0]} at {best_b[1]:.1%} -> lambda={lam_corners_b:.2f}')
else:
    lam_corners_a = _rate(team_a, 'corners_per_match')
    lam_corners_b = _rate(team_b, 'corners_per_match')
    print(f'No Polymarket lines — using historical: ENG={lam_corners_a:.2f}  NOR={lam_corners_b:.2f}')

p_more_corners = sum(
    poisson_pmf(a, lam_corners_a) * poisson_pmf(b, lam_corners_b)
    for a in range(26) for b in range(a)
)
print(f'P(England more corners) = {p_more_corners:.3f} ({round(p_more_corners*100)}%)')

# ---- SHOTS from historical model ----
print()
print('=== SHOTS ===')
lam_shots_a = _opponent_adjusted_lam(team_a, team_b, 'shots_total_per_match', 'shots_conceded_per_match')
lam_shots_b = _opponent_adjusted_lam(team_b, team_a, 'shots_total_per_match', 'shots_conceded_per_match')
print(f'England shots lambda (opponent-adjusted): {lam_shots_a:.2f}')
print(f'Norway  shots lambda (opponent-adjusted): {lam_shots_b:.2f}')
print(f'  England raw shots/game: {_rate(team_a, "shots_total_per_match"):.2f}')
print(f'  Norway  raw shots/game: {_rate(team_b, "shots_total_per_match"):.2f}')
print(f'  England shots conceded/game: {_rate(team_a, "shots_conceded_per_match"):.2f}')
print(f'  Norway  shots conceded/game: {_rate(team_b, "shots_conceded_per_match"):.2f}')

p_more_shots = sum(
    poisson_pmf(a, lam_shots_a) * poisson_pmf(b, lam_shots_b)
    for a in range(40) for b in range(a)
)
print(f'P(England more shots) = {p_more_shots:.3f} ({round(p_more_shots*100)}%)')

# ---- JOINT with correlation boost ----
print()
print('=== JOINT ===')
p_joint_independent = p_more_corners * p_more_shots
p_joint_boosted = min(p_more_corners * p_more_shots * 1.3, min(p_more_corners, p_more_shots))
print(f'P(corners) * P(shots) = {p_more_corners:.3f} * {p_more_shots:.3f} = {p_joint_independent:.3f} ({round(p_joint_independent*100)}%)')
print(f'With 1.3x correlation boost: {p_joint_boosted:.3f} ({round(p_joint_boosted*100)}%)')
print()
print(f'Final submitted: 32%')

# ---- Does this make sense? ----
print()
print('=== SANITY CHECK ===')
print(f'England win prob from Polymarket: {nor_eng.away_win if nor_eng else "?"}')
print(f'Note: If England are favourites, P(more corners AND more shots) should be')
print(f'      roughly 40-55% for a team with 50-60% win probability.')
print(f'      32% seems somewhat low if England are favourites.')
