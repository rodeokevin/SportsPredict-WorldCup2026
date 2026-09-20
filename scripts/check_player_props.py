#!/usr/bin/env python3
"""
Fetch bookmaker player prop odds for upcoming World Cup fixtures from The Odds API
and compare them against our submitted predictions.

Usage:
    python scripts/check_player_props.py              # show all player props
    python scripts/check_player_props.py --match ESP  # filter by match name fragment
    python scripts/check_player_props.py --player yamal

Requires THE_ODDS_API_KEY in .env (free tier: 500 requests/month).
Sign up at: https://the-odds-api.com/

Each call costs:
    - 1 credit to list events (free, no cost)
    - 1 credit per market per region to fetch event odds
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from odds import decimal_to_implied_probability, remove_vig
from teams import normalize_team

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE = "https://api.the-odds-api.com/v4"
SPORT = "soccer_fifa_world_cup"

# Soccer player prop market keys supported by The Odds API.
# Each costs 1 credit per region per call.
PROP_MARKETS = [
    "player_anytime_goalscorer",       # anytime goal scorer
    "player_first_goalscorer",         # first goal scorer
    "player_shots_on_target",          # shots on target over/under
    "player_to_score_2_or_more",       # brace
    "player_goal_or_assist",           # goal or assist
    "player_cards",                    # to receive a card
]

# Fallback: broader markets that many bookmakers carry for soccer
FALLBACK_MARKETS = [
    "player_anytime_goalscorer",
    "player_first_goalscorer",
]


def _api(path: str, params: dict) -> dict | list:
    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        sys.exit("THE_ODDS_API_KEY not set in .env — sign up free at https://the-odds-api.com/")
    params["apiKey"] = key
    resp = requests.get(f"{BASE}{path}", params=params, timeout=30)
    remaining = resp.headers.get("x-requests-remaining", "?")
    used = resp.headers.get("x-requests-used", "?")
    cost = resp.headers.get("x-requests-last", "?")
    print(f"  [quota] used={used}  remaining={remaining}  this_call={cost}", file=sys.stderr)
    resp.raise_for_status()
    return resp.json()


def get_events() -> list[dict]:
    """List all upcoming WC events (free, no quota cost)."""
    return _api(f"/sports/{SPORT}/events", {})


def get_available_markets(event_id: str, region: str = "uk") -> set[str]:
    """Check which markets are available for an event (costs 1 credit)."""
    try:
        data = _api(f"/sports/{SPORT}/events/{event_id}/markets", {"regions": region})
        keys: set[str] = set()
        for bm in data.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                keys.add(mkt["key"])
        return keys
    except Exception:
        return set()


def get_event_props(event_id: str, markets: list[str], region: str = "uk") -> dict:
    """Fetch player prop odds for a single event."""
    return _api(
        f"/sports/{SPORT}/events/{event_id}/odds",
        {
            "regions": region,
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
        },
    )


def decimal_to_pct(price: float) -> float:
    """Convert decimal odds to fair implied probability %."""
    try:
        return round(decimal_to_implied_probability(price) * 100, 1)
    except Exception:
        return 0.0


def load_our_predictions() -> dict[str, int]:
    """Load latest submitted predictions: {question_lower -> probability}."""
    pred_dir = Path(__file__).resolve().parent.parent / "data" / "predictions"
    files = sorted(pred_dir.glob("*_submitted.json"))
    if not files:
        files = sorted(pred_dir.glob("*.json"))
    if not files:
        return {}
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    out = {}
    for match, preds in data.get("matches", {}).items():
        for p in preds:
            out[p["question"].lower()] = p["probability"]
    return out


def format_prop_market(market: dict, our_preds: dict) -> list[str]:
    """Format a single market's outcomes into readable lines."""
    lines = []
    key = market.get("key", "")
    outcomes = market.get("outcomes", [])

    # Group Over/Under by player name for shots-on-target style markets
    by_player: dict[str, dict[str, list]] = {}
    for o in outcomes:
        player = o.get("description") or o.get("name", "")
        side = o.get("name", "").lower()  # "over" / "under" / player name
        price = float(o.get("price", 0))
        point = o.get("point")
        by_player.setdefault(player, {}).setdefault(side, []).append((price, point))

    for player, sides in sorted(by_player.items()):
        if "over" in sides and "under" in sides:
            # Over/under market (shots on target etc.)
            over_prices = [p for p, _ in sides["over"]]
            under_prices = [p for p, _ in sides["under"]]
            point = sides["over"][0][1] if sides["over"] else None
            if over_prices and under_prices:
                avg_over = sum(over_prices) / len(over_prices)
                avg_under = sum(under_prices) / len(under_prices)
                try:
                    fair = remove_vig([
                        decimal_to_implied_probability(avg_over),
                        decimal_to_implied_probability(avg_under),
                    ])
                    fair_over_pct = round(fair[0] * 100, 1)
                except Exception:
                    fair_over_pct = decimal_to_pct(avg_over)
                threshold = f"O{point}" if point else ""
                lines.append(
                    f"  {player:30} {key:35} {threshold:8} "
                    f"fair={fair_over_pct:5.1f}%  "
                    f"(raw over={decimal_to_pct(avg_over):.1f}%)"
                )
        else:
            # Yes/No or anytime goalscorer style
            for side, price_list in sides.items():
                if not price_list:
                    continue
                avg_price = sum(p for p, _ in price_list) / len(price_list)
                raw_pct = decimal_to_pct(avg_price)
                lines.append(
                    f"  {player:30} {key:35}          "
                    f"raw={raw_pct:5.1f}%"
                )

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch bookmaker player props for WC fixtures")
    parser.add_argument("--match",  default="", help="Filter by match name fragment (e.g. ESP)")
    parser.add_argument("--player", default="", help="Filter by player name fragment")
    parser.add_argument("--region", default="uk", help="Bookmaker region (uk, eu, us). Default: uk")
    parser.add_argument("--markets", nargs="+", default=PROP_MARKETS,
                        help="Market keys to fetch. Defaults to all player prop markets.")
    args = parser.parse_args()

    our_preds = load_our_predictions()
    print(f"Loaded {len(our_preds)} of our predictions for comparison.\n")

    print("Fetching upcoming WC events...")
    events = get_events()
    print(f"Found {len(events)} events.\n")

    match_filter = args.match.lower()
    player_filter = args.player.lower()

    for event in events:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        event_id = event["id"]
        event_label = f"{home} vs {away}"

        if match_filter and match_filter not in event_label.lower():
            continue

        print(f"{'='*70}")
        print(f"  {event_label}  ({event.get('commence_time','')})")
        print(f"{'='*70}")

        # First check which markets are actually available (costs 1 credit, saves
        # wasting credits on fixtures with no props yet).
        available = get_available_markets(event_id, region=args.region)
        prop_markets_available = [m for m in args.markets if m in available]

        if not prop_markets_available:
            print("  No player prop markets open yet (check back closer to kickoff).\n")
            continue

        print(f"  Markets available: {', '.join(sorted(prop_markets_available))}")
        try:
            data = get_event_props(event_id, prop_markets_available, region=args.region)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:
                print("  No player prop markets available for this fixture yet.\n")
            else:
                print(f"  Error fetching odds: {e}\n")
            continue

        bookmakers = data.get("bookmakers", [])
        if not bookmakers:
            print("  No bookmaker data returned.\n")
            continue

        # Aggregate all markets across bookmakers
        markets_by_key: dict[str, list[dict]] = {}
        for bm in bookmakers:
            for mkt in bm.get("markets", []):
                markets_by_key.setdefault(mkt["key"], []).append(mkt)

        if not markets_by_key:
            print("  No player prop markets found for this fixture.\n")
            continue

        for mkt_key, mkt_list in sorted(markets_by_key.items()):
            # Merge all bookmaker outcomes for this market
            merged = {"key": mkt_key, "outcomes": []}
            for mkt in mkt_list:
                merged["outcomes"].extend(mkt.get("outcomes", []))

            lines = format_prop_market(merged, our_preds)
            if player_filter:
                lines = [l for l in lines if player_filter in l.lower()]
            if lines:
                print(f"\n  --- {mkt_key} ---")
                for line in lines:
                    print(line)

        print()


if __name__ == "__main__":
    main()
