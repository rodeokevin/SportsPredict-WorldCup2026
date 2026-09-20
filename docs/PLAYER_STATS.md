# Player Statistics Setup Guide

## Quick Start

Run the automated fetcher to populate `data/player_history.json`:

```powershell
python scripts/fetch_player_stats.py
```

This fetches international career stats for 30+ major World Cup 2026 players.

## Manual Updates

Edit `data/player_history.json` to add or update players:

```json
{
  "Player Name": {
    "team": "Country",
    "goals": 50,
    "matches": 100,
    "assists": 15,
    "shots_on_target": 120,
    "cards": 5,
    "source": "International career (2024)"
  }
}
```

## Finding Player Stats

### Easy Sources (Free)
- **Wikipedia:** Search "[Player] international footballer" → scroll to stats section
- **FB-Ref:** fbref.com/en/players/ → search by name → international tab
- **Transfermarkt:** transfermarkt.us → player page → international stats

### Key Metrics
- **goals** - Career international goals scored
- **matches** - Career international appearances
- **assists** - Career international assists
- **shots_on_target** - Estimated total shots on target
- **cards** - Yellow + red cards in international matches

## How It Works

Probabilities are calculated from historical performance:

### Player Goal
```
P(scores) = (career_goals / career_matches) × 1.05  # 1.05 = tournament boost
```

Example: Cristiano Ronaldo with 128 goals / 196 matches:
- Base rate: 65.3%
- With tournament boost: ~69%

### Player Shots On Target
```
P(≥N shots) = (career_SOT_avg / N) × adjustment
```

Conservative when player is below average.

### Player Goal Or Assist
```
P(goal OR assist) = P(goal) + P(assist) - (P(goal) × P(assist))
```

## Testing

View predictions before submission:

```powershell
python sync_odds.py --dry-run -v
```

Look for lines like:
```
POR vs CRO | Will Cristiano Ronaldo (Portugal) score a goal... -> 69%
```

## Adding New Players

1. Find their international stats online
2. Add to `data/player_history.json`:
```json
{
  "New Player": {
    "team": "Country",
    "goals": X,
    "matches": Y,
    "assists": Z,
    "shots_on_target": W,
    "cards": C,
    "source": "International career (2024)"
  }
}
```

3. Run sync again:
```powershell
python sync_odds.py --dry-run -v
```

## Tips

- **International stats only** - use national team matches, not club matches
- **Recent tournaments** - Euro 2024, World Cup 2022, qualifiers are most relevant
- **Youth players** - may have fewer matches; default estimates are conservative
- **Strikers** - usually have best goal conversion rates
- **Defenders** - focus more on cards than goals

## Troubleshooting

**Player not found:** Make sure exact name matches SportsPredict question
- SportsPredict: `"Will Lamine Yamal (Spain) score..."`
- JSON: `"Lamine Yamal": {"team": "Spain", ...}`

**Probability looks wrong:** Check the historical stats - if career goal rate is 10%, estimate will be ~10-11%, not 50%.

**Want better estimates:** Add more recent tournament/friendly data if available.
