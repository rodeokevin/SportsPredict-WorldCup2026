"""Audit player data quality for active match players."""
import sys, json
sys.path.insert(0, 'src')
from player_stats import load_player_history, get_player_stat

history = load_player_history()

active_players = [
    ('Jude Bellingham', 'England'),
    ('Harry Kane', 'England'),
    ('Bukayo Saka', 'England'),
    ('Phil Foden', 'England'),
    ('Erling Haaland', 'Norway'),
    ('Martin Odegaard', 'Norway'),
    ('Lionel Messi', 'Argentina'),
    ('Julian Alvarez', 'Argentina'),
    ('Lautaro Martinez', 'Argentina'),
    ('Breel Embolo', 'Switzerland'),
    ('Granit Xhaka', 'Switzerland'),
    ('Lamine Yamal', 'Spain'),
    ('Pedri', 'Spain'),
    ('Alvaro Morata', 'Spain'),
    ('Kylian Mbappe', 'France'),
    ('Antoine Griezmann', 'France'),
    ('Ousmane Dembele', 'France'),
    ('Cristiano Ronaldo', 'Portugal'),
    ('Bruno Fernandes', 'Portugal'),
    ('Romelu Lukaku', 'Belgium'),
    ('Kevin De Bruyne', 'Belgium'),
    ('Mohamed Salah', 'Egypt'),
    ('Omar Marmoush', 'Egypt'),
]

print(f'Total players in history: {len(history)}')
print()
print(f'{"Player":<28} {"Matches":>8} {"Goals":>6} {"SOT":>5} {"SOT/g":>7} {"G/g":>6} {"Note"}')
print('-' * 80)
for name, team in active_players:
    d = get_player_stat(name, team)
    m = d.get('matches', 0)
    g = d.get('goals', 0)
    s = d.get('shots_on_target', 0)
    lam_s = s/m if m > 0 else 0
    lam_g = g/m if m > 0 else 0
    note = ''
    if m == 0:
        note = '*** NO DATA'
    elif m < 5:
        note = '* very low'
    elif m < 10:
        note = '* low'
    elif lam_s < 0.4 and lam_g > 0.1:
        note = '^ SOT low vs goal rate'
    print(f'{name:<28} {m:>8} {g:>6} {s:>5} {lam_s:>7.2f} {lam_g:>6.2f} {note}')

print()
print('--- StatsBomb data covers: WC 2018/2022, Euro 2020/2024, Copa 2024, AFCON 2023 ---')
print('--- Supplementary: La Liga, Ligue 1, Bundesliga (limited) ---')
print()

# Check what competitions are covered
sources = set()
for name, d in history.items():
    src = d.get('source', '')
    if src:
        sources.add(src)
for s in sorted(sources):
    print(f'  Source: {s}')
