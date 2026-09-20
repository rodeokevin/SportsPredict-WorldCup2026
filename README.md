# SportsPredict Odds Sync

Automatically generate and submit probability predictions for the [Probability Cup](https://sportspredict.com/probabilitycup) contest using a multi-source pipeline: Polymarket prediction markets, bookmaker player props, and a statistical model built on StatsBomb international match data.

## Quick start

1. Enter the contest at [bit.ly/probabilitycup](https://bit.ly/probabilitycup)
2. Create a bot key: Profile & History → My Bots → Generate New Bot
3. Get a free player props key at [the-odds-api.com](https://the-odds-api.com) (500 requests/month, no credit card)
4. Install and configure:

```powershell
pip install -r requirements.txt
# Edit .env — add your keys (see .env for field descriptions)
```

5. Preview predictions without submitting:

```powershell
python sync_odds.py --dry-run --save
python scripts/print_predictions.py        # readable view of latest saved file
```

6. Submit:

```powershell
python sync_odds.py
```

7. Update existing predictions (e.g. run again closer to kickoff for fresher odds):

```powershell
python sync_odds.py --update
```

---

## How predictions are made

Markets are handled in priority order:

### 1. Direct from Polymarket (free, no key)
Match winner, draw, both-teams-score, over/under goals, and related markets are pulled directly from Polymarket's live prediction prices and used as-is after de-vig.

### 2. Bookmaker player props (The Odds API — free tier)
For player-specific markets (anytime goalscorer, shots on target, goal or assist, cards), bookmaker odds from The Odds API are de-vigged and used directly when available. This is more accurate than the statistical model because bookmakers have access to current-season club data.

Falls back to the statistical model when bookmaker props are not yet posted (typically opens 24–48h before kickoff).

### 3. Statistical model — team historical data
For count-based markets (corners, total shots, cards, offsides, early sub, header goal, penalty/red card), each team's historical per-match rate is taken from **StatsBomb open data** across six recent international tournaments:

- FIFA World Cup 2018 & 2022
- UEFA Euro 2020 & 2024
- Copa America 2024
- Africa Cup of Nations 2023

**Opponent adjustment:** shot and corner markets are adjusted for the opponent's defensive permissiveness — a team attacking a leaky defence gets a higher expected count, and vice versa.

### 4. Statistical model — player historical data
For player props when bookmaker odds are unavailable, each player's historical rate per match (goals, assists, shots on target, cards) is derived from the same StatsBomb tournaments plus supplementary La Liga, Ligue 1, and Bundesliga club data (3,694 players total). Modelled as Poisson.

### 5. Poisson goal model (fixture-specific)
Markets not covered by any external source — halftime scoreline, hydration break goals, clean sheet, second-half vs first-half goals, under goals — are derived from the fixture's expected total goals (back-calculated from Polymarket's over/under line) using a Poisson process.

---

## Commands

```powershell
# Core workflow
python sync_odds.py                        # submit new predictions
python sync_odds.py --update               # re-submit changed predictions
python sync_odds.py --dry-run              # preview without submitting
python sync_odds.py --dry-run --save       # preview and save to data/predictions/
python sync_odds.py --update --dry-run --save  # see what would change

# View saved predictions
python scripts/print_predictions.py                          # latest file
python scripts/print_predictions.py data/predictions/xyz.json  # specific file

# Check bookmaker player props (comparison tool)
python scripts/check_player_props.py                         # all fixtures
python scripts/check_player_props.py --match Spain           # filter by match
python scripts/check_player_props.py --player yamal          # filter by player
python scripts/check_player_props.py --region eu             # EU bookmakers

# Rebuild historical data (run once, or to refresh)
python scripts/fetch_team_stats.py         # team history → data/team_history.json
python scripts/fetch_player_stats_statsbomb.py  # player history → data/player_history.json

# Odds source overrides
python sync_odds.py --source polymarket    # Polymarket only
python sync_odds.py --source odds_api      # The Odds API only (player props)
python sync_odds.py --source manual --manual-file data/odds.json
```

---

## Saving predictions

Every real submission automatically saves a timestamped file to `data/predictions/`. Dry runs save when you pass `--save`.

```
data/predictions/
  20260702T031213Z_submitted.json   ← real submission
  20260702T034555Z_dry_run.json     ← dry run with --save
```

Each file is JSON grouped by match:

```json
{
  "saved_at": "2026-07-02T03:45:55Z",
  "submitted": 90,
  "matches": {
    "ESP vs AUT": [
      { "question": "Will Spain win...", "probability": 75, "action": "submit" },
      ...
    ]
  }
}
```

`action` is one of `submit`, `update`, `existing`, or `dry_run`.

---

## Scheduling (keep odds fresh before kickoff)

Run with `--update` every few hours on matchdays to pick up bookmaker line movements:

**Windows Task Scheduler:**
1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily, repeat every 4 hours
3. Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-File "C:\path\to\SportsPredict\scripts\run_sync.ps1" -Update`
   - Start in: `C:\path\to\SportsPredict`

Markets close at match start — your last submission before kickoff is what gets scored.

---

## .env keys

| Key | Required | Description |
|---|---|---|
| `SPORTSPREDICT_API_KEY` | ✅ | Bot key from Profile → My Bots |
| `THE_ODDS_API_KEY` | Recommended | Bookmaker player props. Free at [the-odds-api.com](https://the-odds-api.com) |
| `FOOTBALL_DATA_ORG_KEY` | Optional | Extra match odds. Free at [football-data.org](https://football-data.org) |
| `API_FOOTBALL_KEY` | Optional | Match statistics via RapidAPI |

---

## Project layout

```
sync_odds.py                     CLI entry point
src/
  client.py                      SportsPredict REST client
  matcher.py                     Question parsing + probability routing
  sync_engine.py                 Orchestrates fetch → predict → submit
  sources.py                     Polymarket, TheOddsAPI, FBRef, composite
  polymarket.py                  Polymarket Gamma API source
  merge.py                       Merge multiple sources per fixture
  player_stats.py                Player prop probability model
  team_stats.py                  Team stat probability model (opponent-adjusted)
  poisson.py                     Poisson goal model utilities
  odds.py                        De-vig and probability conversion helpers
  teams.py                       Team name normalisation + FIFA code aliases
scripts/
  fetch_team_stats.py            Build data/team_history.json from StatsBomb
  fetch_player_stats_statsbomb.py  Build data/player_history.json from StatsBomb
  check_player_props.py          Fetch bookmaker player prop odds for comparison
  print_predictions.py           Print a saved predictions file
  run_sync.ps1                   Task Scheduler wrapper
data/
  team_history.json              Per-team match stats (324 international matches)
  player_history.json            Per-player stats (3,694 players)
  predictions/                   Timestamped prediction snapshots
  odds.example.json              Manual odds file format
```

---

## Scoring note

[Brier scoring](https://sportspredict.com/probabilitycup/scoring) rewards calibration. Copying market prices is a solid baseline — the edge comes from finding markets where our model diverges meaningfully from the bookmaker consensus.
