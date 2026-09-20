# Match Statistics Integration

Unlocks **corners**, **team cards**, **possession**, and other match statistics for international matches.

## Quick Start (No API Key Needed)

The fastest way: **Fetch from Football-Data.org** (free tier, no sign-up required for basic access):

```powershell
# Add to .env
FOOTBALL_DATA_ORG_KEY=  # Leave blank for free tier

# Run sync
python sync_odds.py --dry-run -v
```

## Setup Options

### Option 1: Football-Data.org (Recommended — Free)

1. Visit [football-data.org](https://www.football-data.org/)
2. Click "Documentation" (free tier = 10 requests/min)
3. Optional: Sign up for API key (free tier includes international matches)
4. Add to .env:
   ```
   FOOTBALL_DATA_ORG_KEY=your_key_or_leave_blank
   ```

### Option 2: RapidAPI (If you prefer)

1. Go to [rapidapi.com](https://rapidapi.com)
2. Search for "football statistics" or "soccer statistics"
3. Look for free-tier APIs (many options available)
4. Copy API key and add to .env:
   ```
   API_FOOTBALL_KEY=your_key
   ```

### Option 3: Local FB-Ref Scraping (Slowest, Always Works)

```powershell
# No API key needed — scrapes from fbref.com directly
# Add to .env (blank = use scraping)
SCRAPE_FBREF=true
```

## Run with Statistics Enabled

```powershell
python sync_odds.py --dry-run -v
```

The system now fetches:
- **Match corners** (team and combined totals)
- **Yellow/red cards** (per team)
- **Possession %** (home team)
- **Shots** (total and on target)
- **Fouls** (per team)

## Recognized Markets

### Team Corners
```
"Will [Team] have 5 or more corners?"
→ Checks actual corner count from match
```

### Both Teams Corners
```
"Will both teams combined have 9 or more corners?"
→ Sums both teams' actual corners
```

### Team Cards
```
"Will [Team] receive 2 cards?"
→ Checks actual yellow + red cards from match
```

## How It Works

1. **Fetch data from international matches** - World Cup 2026, Euro 2024 qualifiers, friendly matches
2. **Parse match statistics** - Extract corners, cards, possession, shots per team
3. **Use actual counts** - If a match finished with 6 corners, "over 5 corners" = 1.0 probability

## Data Sources

- **League ID 1:** International matches (World Cup, Euro, qualifiers)
- **Status:** FT (finished matches only)
- **Season:** 2026 (World Cup year)

## Limitations

- **Free tier (100 requests/day):** Sufficient for 10-20 fixtures per sync
- **International matches only:** World Cup 2026, Euro 2024, international friendlies
- **Finished matches only:** Live/in-progress matches have incomplete stats
- **Rate limiting:** ~2 sec delay between requests (respectful)

## Extending Coverage

Add more statistics in `APIFootballSource._fetch_league_matches()`:

```python
home_stats = {}  # Team ID → {"Corners": 5, "Cards": 2, ...}

# Available stats in API response:
# - Corners, Fouls, Offsides
# - Yellow Cards, Red Cards
# - Possession %, Passes, Passes Accuracy
# - Shots, Shots on Goal, Shots off Goal
# - Tackles, Blocks, Interceptions, Clearances
```

## Testing

```powershell
# Dry run with API-Football only
python sync_odds.py --source api_football --dry-run -v

# Auto mode (Polymarket + API-Football + Odds API)
python sync_odds.py --dry-run -v
```

Expected output shows probabilities for corners and cards:
```
POR vs CRO | Will Portugal have 5 or more corners? -> 80%
COL vs GHA | Will Colombia receive 2 cards? -> 60%
```

## Troubleshooting

**"API_FOOTBALL_KEY not set in .env"**
- Add `API_FOOTBALL_KEY=your_key` to .env
- Restart the sync

**"No corners/cards data appearing"**
- API might not have finished the match yet
- Wait for official match completion
- Check API dashboard to verify quota usage

**Rate limit errors**
- Free tier: 100 requests/day
- Each fixture fetch = 1 request
- Distribute syncs throughout the day

## Cost

- **Free tier:** 100 requests/day → 10-20 fixtures
- **Pro tier:** $10/month → 1000 requests/day → unlimited fixtures
- Upgrade in RapidAPI dashboard as needed
