"""
Merge full-career international stats from fetch_player_stats.py FALLBACK_STATS
into data/player_history.json.

Strategy:
- If a player appears in FALLBACK_STATS and has significantly more matches than
  the StatsBomb entry (>= 1.5x), use the fallback as the authoritative source.
- If StatsBomb has more or comparable data, keep StatsBomb.
- If a player is missing from StatsBomb entirely, add the fallback.

This gives priority to the richer, full-career dataset while preserving
StatsBomb precision for players it covers well.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, 'src')

PLAYER_HISTORY_FILE = Path('data/player_history.json')

# Load current StatsBomb-based history
current = json.loads(PLAYER_HISTORY_FILE.read_text(encoding='utf-8'))

# Load fallback stats from fetch_player_stats.py
import importlib.machinery
loader = importlib.machinery.SourceFileLoader('fps', 'scripts/fetch_player_stats.py')
fps = loader.load_module()
fallback = fps.FALLBACK_STATS

merged = dict(current)
updated = 0
added = 0

for fb_name, fb_data in fallback.items():
    fb_matches = fb_data.get('matches', 0)
    if fb_matches == 0:
        continue

    # Find matching entry in current (handles accent variants)
    import unicodedata
    def _norm(s):
        nfkd = unicodedata.normalize('NFKD', s)
        return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    norm_fb = _norm(fb_name)
    current_key = None
    current_matches = 0
    for k in current:
        if _norm(k) == norm_fb or all(w in _norm(k) for w in norm_fb.split()):
            current_key = k
            current_matches = current[k].get('matches', 0)
            break

    if current_key is None:
        # Player not in StatsBomb at all — add fallback
        merged[fb_name] = {**fb_data}
        added += 1
        print(f'  ADDED:   {fb_name} ({fb_matches}m, {fb_data.get("shots_on_target",0)} SOT)')
    elif fb_matches >= current_matches * 1.5 and fb_matches > current_matches + 5:
        # Fallback has substantially more data — use it
        old_lam = current[current_key].get('shots_on_target', 0) / max(current_matches, 1)
        new_lam = fb_data.get('shots_on_target', 0) / fb_matches
        merged[current_key] = {**fb_data}
        updated += 1
        print(f'  UPDATED: {current_key} ({current_matches}m→{fb_matches}m, SOT/g {old_lam:.2f}→{new_lam:.2f})')
    # else: keep StatsBomb data

print(f'\nAdded {added} players, updated {updated} players.')
print(f'Total players: {len(merged)}')

PLAYER_HISTORY_FILE.write_text(
    json.dumps(dict(sorted(merged.items())), indent=2, ensure_ascii=False),
    encoding='utf-8'
)
print(f'Saved to {PLAYER_HISTORY_FILE}')
