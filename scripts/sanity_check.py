import sys; sys.path.insert(0, 'src')
from team_stats import _rate, _LEAGUE_AVG, _load, _opponent_adjusted_lam
from poisson import prob_at_least
import math
_load()

print("=== League averages ===")
for k, v in _LEAGUE_AVG.items():
    print(f"  {k}: {v:.3f}")

print()
print("=== Opponent-adjusted lambdas for shot/corner markets ===")
checks = [
    ("Spain 8+ SOT vs Austria",      "Spain",     "Austria",          "shots_on_target_per_match", "sot_conceded_per_match",      8),
    ("Austria 4+ SOT vs Spain",      "Austria",   "Spain",            "shots_on_target_per_match", "sot_conceded_per_match",      4),
    ("Spain 7+ corners vs Austria",  "Spain",     "Austria",          "corners_per_match",         "corners_conceded_per_match",  7),
    ("Algeria corners vs Switz",     "Algeria",   "Switzerland",      "corners_per_match",         "corners_conceded_per_match",  1),
    ("Arg 8+ SOT vs Cape Verde",     "Argentina", "Cape Verde Islands","shots_on_target_per_match","sot_conceded_per_match",      8),
    ("Colombia 7+ SOT vs Ghana",     "Colombia",  "Ghana",            "shots_on_target_per_match", "sot_conceded_per_match",      7),
    ("Egypt 5+ SOT vs Australia",    "Egypt",     "Australia",        "shots_on_target_per_match", "sot_conceded_per_match",      5),
]
for desc, atk, dfn, atk_key, def_key, threshold in checks:
    own = _rate(atk, atk_key)
    opp = _rate(dfn, def_key)
    avg = _LEAGUE_AVG.get(def_key, 1.0)
    adj = _opponent_adjusted_lam(atk, dfn, atk_key, def_key)
    prob = prob_at_least(threshold, adj)
    print(f"{desc}")
    print(f"  own={own:.2f}  opp_conc={opp:.2f}  avg={avg:.2f}  adj_lam={adj:.2f}  P({threshold}+)={prob:.0%}")

print()
print("=== Player lookups ===")
from player_stats import get_player_stat
players = [
    ("Lamine Yamal",    "Spain"),
    ("Cristiano Ronaldo","Portugal"),
    ("Lautaro Martinez","Argentina"),
    ("Breel Embolo",    "Switzerland"),
    ("Luka Modric",     "Croatia"),
    ("James Rodriguez", "Colombia"),
    ("Riyad Mahrez",    "Algeria"),
    ("Nestory Irankunda","Australia"),
    ("Amine Gouiri",    "Algeria"),
]
for name, team in players:
    d = get_player_stat(name, "goals")
    m = d.get("matches", 0)
    g = d.get("goals", 0)
    sot = d.get("shots_on_target", 0)
    src = "DATA" if m > 0 else "FALLBACK"
    print(f"  {name:30} [{src}] m={m} g={g} sot={sot} sot/m={sot/max(m,1):.2f}")
