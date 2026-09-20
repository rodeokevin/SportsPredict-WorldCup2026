"""Check what StatsBomb club competitions are available."""
import requests, sys

RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
resp = requests.get(f"{RAW}/competitions.json", timeout=30)
comps = resp.json()

MAJOR_LEAGUES = {
    'La Liga', 'Premier League', 'Champions League', 'Ligue 1', 'Bundesliga',
    'Serie A', 'FA Cup'
}

print("Club competitions in StatsBomb open data:")
print(f"{'Competition':<35} {'Season':<20} ID")
print("-"*70)
seen = set()
for c in sorted(comps, key=lambda x: (x['competition_name'], x['season_name'])):
    name = c['competition_name']
    season = c['season_name']
    cid = c['competition_id']
    sid = c['season_id']
    # Only major club leagues
    if not any(m.lower() in name.lower() for m in MAJOR_LEAGUES):
        continue
    key = f"{name}-{season}"
    if key in seen:
        continue
    seen.add(key)
    print(f"  {name:<33} {season:<20} {cid}/{sid}")
