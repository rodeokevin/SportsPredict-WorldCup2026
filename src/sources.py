"""Pluggable odds sources."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from merge import merge_fixture_lists
from matcher import MatchOdds
from odds import average_decimal_odds, decimal_to_implied_probability, remove_vig
from polymarket import PolymarketSource  # noqa: F401 — re-exported for CLI
from teams import teams_match


class OddsSource(ABC):
    @abstractmethod
    def fetch_match_odds(self) -> list[MatchOdds]:
        """Return fair probabilities for all available fixtures."""


class ManualOddsSource(OddsSource):
    """
    Load odds from a JSON file you maintain (Polymarket exports, scraped data, etc.).

    Example format:
    [
      {
        "home_team": "Mexico",
        "away_team": "South Africa",
        "home_win": 0.55,
        "away_win": 0.18,
        "draw": 0.27,
        "btts_yes": 0.52,
        "totals": {"2.5": 0.48}
      }
    ]
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch_match_odds(self) -> list[MatchOdds]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        results: list[MatchOdds] = []
        for row in data:
            totals_raw = row.get("totals") or {}
            totals = {float(k): float(v) for k, v in totals_raw.items()}
            results.append(
                MatchOdds(
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    home_win=row.get("home_win"),
                    away_win=row.get("away_win"),
                    draw=row.get("draw"),
                    btts_yes=row.get("btts_yes"),
                    totals=totals or None,
                    team_totals={
                        team: {float(k): float(v) for k, v in lines.items()}
                        for team, lines in (row.get("team_totals") or {}).items()
                    }
                    or None,
                )
            )
        return results


class TheOddsAPISource(OddsSource):
    """
    Fetch live odds from The Odds API (https://the-odds-api.com).

    Fetches match odds (h2h, totals, btts) plus player prop markets
    (anytime goalscorer, shots on target, goal or assist, cards).

    World Cup (`soccer_fifa_world_cup`) h2h/totals needs Business tier.
    Player props are available on the free tier via the event odds endpoint.
    Free tier: 500 requests/month.
    """

    BASE = "https://api.the-odds-api.com/v4"

    # Player prop market keys to fetch per event.
    # Cost = len(PLAYER_PROP_MARKETS) × num_regions per event.
    # Keep this list lean — only markets we have SportsPredict questions for.
    PLAYER_PROP_MARKETS = [
        "player_goal_scorer_anytime",   # player to score
        "player_shots_on_target",       # player SOT over/under
        "player_to_score_or_assist",    # goal or assist
        "player_to_receive_card",       # player cards
        "to_qualify",                   # advance to next round
        "alternate_totals_corners",     # team corner O/U
    ]

    # Map from API key → our internal market key (for get_player_prop lookups).
    PROP_KEY_MAP = {
        "player_goal_scorer_anytime": "player_anytime_goalscorer",
        "player_to_score_or_assist":  "player_goal_or_assist",
        "player_to_receive_card":     "player_cards",
        "player_assists":             "player_assists",
        "player_shots_on_target":     "player_shots_on_target",
        "player_shots":               "player_shots",
        "to_qualify":                 "to_qualify",
        # Team stat markets
        "alternate_totals_corners":   "team_corners_line",
        "team_totals":                "team_goals_line",
        "alternate_totals_cards":     "total_cards_line",
        "totals":                     "total_goals_line",
        "h2h":                        "match_winner",
        "btts":                       "btts",
    }

    def __init__(
        self,
        api_key: str,
        sport_key: str = "soccer_fifa_world_cup",
        regions: str = "uk,eu",
        bookmakers: list[str] | None = None,
        markets: str = "h2h,totals,btts",
        fetch_player_props: bool = True,
    ):
        self.api_key = api_key
        self.sport_key = sport_key
        self.regions = regions
        self.bookmakers = bookmakers
        self.markets = markets
        self.fetch_player_props = fetch_player_props

    def fetch_match_odds(self) -> list[MatchOdds]:
        # Step 1: get events list (free, no quota cost).
        events_resp = requests.get(
            f"{self.BASE}/sports/{self.sport_key}/events",
            params={"apiKey": self.api_key},
            timeout=30,
        )
        events_resp.raise_for_status()
        events: list[dict[str, Any]] = events_resp.json()

        # Step 2: fetch featured market odds (h2h/totals/btts) via bulk endpoint.
        # This requires Business tier for WC — falls back gracefully on free tier.
        by_id: dict[str, MatchOdds] = {}
        try:
            params: dict[str, str] = {
                "apiKey": self.api_key,
                "regions": self.regions,
                "markets": self.markets,
                "oddsFormat": "decimal",
            }
            if self.bookmakers:
                params["bookmakers"] = ",".join(self.bookmakers)

            resp = requests.get(
                f"{self.BASE}/sports/{self.sport_key}/odds",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            odds_events: list[dict[str, Any]] = resp.json()

            remaining = resp.headers.get("x-requests-remaining")
            if remaining is not None:
                print(f"  TheOddsAPI credits remaining: {remaining}")

            for event in odds_events:
                mo = self._parse_event(event)
                by_id[event["id"]] = mo

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (401, 429):
                remaining = e.response.headers.get("x-requests-remaining", "0") if e.response is not None else "0"
                print(f"  TheOddsAPI: out of credits (remaining={remaining}) — player props unavailable, keeping previous predictions")
                # Return empty: Polymarket odds still work, player props stay as-is
                results = [mo for mo in by_id.values() if mo.has_any_odds()]
                return results
            elif status == 422:
                print("  TheOddsAPI: featured markets (h2h/totals) need Business tier — fetching player props only")
            else:
                print(f"  TheOddsAPI: featured markets unavailable ({e})")

        # Fill in any events missing from featured odds.
        for event in events:
            if event["id"] not in by_id:
                by_id[event["id"]] = MatchOdds(
                    home_team=event.get("home_team", ""),
                    away_team=event.get("away_team", ""),
                )

        if self.fetch_player_props:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(hours=48)

            for event in events:
                eid = event["id"]
                # Parse commence_time
                try:
                    ct_str = event.get("commence_time", "")
                    ct = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                    if ct > cutoff:
                        continue  # too far out, props won't be available
                except Exception:
                    pass

                mo = by_id.get(eid)
                if mo is None:
                    continue
                # Use single region for props to halve credit cost
                props = self._fetch_player_props(eid, region="uk")
                if props:
                    mo.player_props = self._remap_props(props)

        results = [mo for mo in by_id.values() if mo.has_any_odds() or mo.player_props]
        return results

    def _fetch_player_props(
        self, event_id: str, region: str | None = None
    ) -> dict[tuple[str, str, float | None], float] | None:
        """
        Fetch player prop and team stat odds for a single event.
        Cost: 1 credit per market returned × 1 region.
        With 6 markets and 1 region = 6 credits per event.
        """
        import unicodedata
        use_region = region or self.regions.split(",")[0]  # use first region only

        def _norm(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

        try:
            props_resp = requests.get(
                f"{self.BASE}/sports/{self.sport_key}/events/{event_id}/odds",
                params={
                    "apiKey": self.api_key,
                    "regions": use_region,
                    "markets": ",".join(self.PLAYER_PROP_MARKETS),
                    "oddsFormat": "decimal",
                },
                timeout=30,
            )
            props_resp.raise_for_status()
            data = props_resp.json()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (401, 429):
                print("  TheOddsAPI: credits exhausted — skipping player props for this event")
            return None
        except Exception:
            return None

        # Parse outcomes into (player_norm, market_key, line) -> fair_prob.
        # Accumulate over/under pairs per bookmaker then average.
        AccumKey = tuple[str, str, float | None]
        over_prices: dict[AccumKey, list[float]] = {}
        under_prices: dict[AccumKey, list[float]] = {}
        yes_prices: dict[AccumKey, list[float]] = {}
        no_prices: dict[AccumKey, list[float]] = {}

        for bm in data.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                mkt_key = mkt["key"]
                for outcome in mkt.get("outcomes", []):
                    player_raw = outcome.get("description") or outcome.get("name", "")
                    player = _norm(player_raw)
                    side = outcome.get("name", "").lower()
                    price = float(outcome.get("price", 0))
                    if price <= 1.0:   # invalid decimal odds — skip
                        continue
                    line = outcome.get("point")
                    if line is not None:
                        line = float(line)
                    key: AccumKey = (player, mkt_key, line)

                    if side == "over":
                        over_prices.setdefault(key, []).append(price)
                    elif side == "under":
                        under_prices.setdefault(key, []).append(price)
                    elif side == "yes":
                        yes_prices.setdefault(key, []).append(price)
                    elif side == "no":
                        no_prices.setdefault(key, []).append(price)
                    else:
                        # Anytime goalscorer: outcome name IS the player name,
                        # treat as a yes price for the player.
                        yes_prices.setdefault(key, []).append(price)

        result: dict[AccumKey, float] = {}

        # Over/under markets (shots on target).
        for key, op_list in over_prices.items():
            up_list = under_prices.get(key, [])
            avg_over = sum(op_list) / len(op_list)
            if up_list:
                avg_under = sum(up_list) / len(up_list)
                try:
                    fair = remove_vig([
                        decimal_to_implied_probability(avg_over),
                        decimal_to_implied_probability(avg_under),
                    ])
                    result[key] = round(fair[0], 4)
                except Exception:
                    result[key] = round(decimal_to_implied_probability(avg_over), 4)
            else:
                result[key] = round(decimal_to_implied_probability(avg_over), 4)

        # Yes/No markets (anytime goalscorer, goal_or_assist, cards).
        for key, yp_list in yes_prices.items():
            np_list = no_prices.get(key, [])
            avg_yes = sum(yp_list) / len(yp_list)
            if np_list:
                avg_no = sum(np_list) / len(np_list)
                try:
                    fair = remove_vig([
                        decimal_to_implied_probability(avg_yes),
                        decimal_to_implied_probability(avg_no),
                    ])
                    result[key] = round(fair[0], 4)
                except Exception:
                    result[key] = round(decimal_to_implied_probability(avg_yes), 4)
            else:
                result[key] = round(decimal_to_implied_probability(avg_yes), 4)

        return result or None

    def _remap_props(
        self, raw: dict[tuple[str, str, float | None], float]
    ) -> dict[tuple[str, str, float | None], float]:
        """Remap API market keys to our internal market key names."""
        out = {}
        for (player, mkt_key, line), prob in raw.items():
            internal_key = self.PROP_KEY_MAP.get(mkt_key, mkt_key)
            out[(player, internal_key, line)] = prob
        return out

    def _parse_event(self, event: dict[str, Any]) -> MatchOdds:
        home = event["home_team"]
        away = event["away_team"]

        home_odds: list[float] = []
        away_odds: list[float] = []
        draw_odds: list[float] = []
        btts_yes_fair: list[float] = []
        totals_over_by_line: dict[float, list[float]] = {}

        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                key = market["key"]
                if key == "h2h":
                    for outcome in market["outcomes"]:
                        price = float(outcome["price"])
                        name = outcome["name"]
                        if name.lower() == "draw":
                            draw_odds.append(price)
                        elif teams_match(name, home):
                            home_odds.append(price)
                        elif teams_match(name, away):
                            away_odds.append(price)
                elif key == "btts":
                    yes_price = no_price = None
                    for outcome in market["outcomes"]:
                        if outcome["name"].lower() == "yes":
                            yes_price = float(outcome["price"])
                        elif outcome["name"].lower() == "no":
                            no_price = float(outcome["price"])
                    if yes_price and no_price:
                        fair = remove_vig([
                            decimal_to_implied_probability(yes_price),
                            decimal_to_implied_probability(no_price),
                        ])
                        btts_yes_fair.append(fair[0])
                elif key == "totals":
                    by_line: dict[float, dict[str, float]] = {}
                    for outcome in market["outcomes"]:
                        if "point" not in outcome:
                            continue
                        line = float(outcome["point"])
                        side = outcome["name"].lower()
                        by_line.setdefault(line, {})[side] = float(outcome["price"])
                    for line, sides in by_line.items():
                        over = sides.get("over")
                        under = sides.get("under")
                        if over and under:
                            fair = remove_vig([
                                decimal_to_implied_probability(over),
                                decimal_to_implied_probability(under),
                            ])
                            totals_over_by_line.setdefault(line, []).append(fair[0])
                        elif over:
                            totals_over_by_line.setdefault(line, []).append(
                                decimal_to_implied_probability(over)
                            )

        home_win = away_win = draw = btts_yes = None
        if home_odds and away_odds and draw_odds:
            avg_home = average_decimal_odds(home_odds)
            avg_away = average_decimal_odds(away_odds)
            avg_draw = average_decimal_odds(draw_odds)
            if avg_home and avg_away and avg_draw:
                fair = remove_vig([
                    decimal_to_implied_probability(avg_home),
                    decimal_to_implied_probability(avg_draw),
                    decimal_to_implied_probability(avg_away),
                ])
                home_win, draw, away_win = fair

        if btts_yes_fair:
            btts_yes = sum(btts_yes_fair) / len(btts_yes_fair)

        totals_fair: dict[float, float] = {}
        for line, probs in totals_over_by_line.items():
            totals_fair[line] = sum(probs) / len(probs)

        return MatchOdds(
            home_team=home,
            away_team=away,
            home_win=home_win,
            away_win=away_win,
            draw=draw,
            btts_yes=btts_yes,
            totals=totals_fair or None,
        )


class APIFootballSource(OddsSource):
    """
    Fetch match statistics from API-Football (https://api-football.com via RapidAPI).
    
    Provides: corners, cards, possession, shots, fouls from international matches.
    Requires API key from RapidAPI (free tier: 100 requests/day).
    """

    BASE = "https://api-football-v3.p.rapidapi.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-rapidapi-host": "api-football-v3.p.rapidapi.com",
            "x-rapidapi-key": api_key,
        }

    def fetch_match_odds(self) -> list[MatchOdds]:
        """Fetch international matches (World Cup, Euro, etc.) with full statistics."""
        results: list[MatchOdds] = []
        
        # Fetch World Cup matches (league_id=1 for international)
        league_ids = [1]  # International matches
        season = 2026
        
        for league_id in league_ids:
            try:
                matches = self._fetch_league_matches(league_id, season)
                results.extend(matches)
            except Exception as e:
                print(f"  APIFootballSource (league {league_id}): failed ({e})")
        
        return results

    def _fetch_league_matches(self, league_id: int, season: int) -> list[MatchOdds]:
        """Fetch all matches in a league with their statistics."""
        results: list[MatchOdds] = []
        
        params = {
            "league": str(league_id),
            "season": str(season),
            "status": "FT",  # Finished matches
        }
        
        resp = requests.get(
            f"{self.BASE}/fixtures",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if "response" not in data:
            return results
        
        for match in data.get("response", []):
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            statistics = match.get("statistics", [])
            
            home_team = teams.get("home", {}).get("name", "")
            away_team = teams.get("away", {}).get("name", "")
            
            if not home_team or not away_team:
                continue
            
            # Parse statistics by team
            home_stats = {}
            away_stats = {}
            
            for stat_group in statistics:
                team_idx = stat_group.get("team", {}).get("id")
                team_stats = stat_group.get("statistics", [])
                
                for stat in team_stats:
                    stat_type = stat.get("type", "")
                    stat_value = stat.get("value")
                    
                    # Home team (index 0) or away team (index 1)
                    target_dict = home_stats if stat_group.get("team", {}).get("id") == teams.get("home", {}).get("id") else away_stats
                    target_dict[stat_type] = stat_value
            
            # Extract key statistics
            home_corners = self._safe_int(home_stats.get("Corners"))
            away_corners = self._safe_int(away_stats.get("Corners"))
            home_cards = self._count_cards(home_stats)
            away_cards = self._count_cards(away_stats)
            home_fouls = self._safe_int(home_stats.get("Fouls"))
            away_fouls = self._safe_int(away_stats.get("Fouls"))
            home_shots = self._safe_int(home_stats.get("Shots total"))
            away_shots = self._safe_int(away_stats.get("Shots total"))
            home_sot = self._safe_int(home_stats.get("Shots on Goal"))
            away_sot = self._safe_int(away_stats.get("Shots on Goal"))
            
            # Only include if we have statistics
            if any([home_corners, away_corners, home_cards, away_cards]):
                results.append(
                    MatchOdds(
                        home_team=home_team,
                        away_team=away_team,
                        home_corners=home_corners,
                        away_corners=away_corners,
                        home_cards=home_cards,
                        away_cards=away_cards,
                        home_fouls=home_fouls,
                        away_fouls=away_fouls,
                        home_shots=home_shots,
                        away_shots=away_shots,
                        home_shots_on_target=home_sot,
                        away_shots_on_target=away_sot,
                    )
                )
        
        return results

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """Safely convert value to int, handling None and string types."""
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _count_cards(stat_dict: dict[str, Any]) -> int | None:
        """Sum yellow + red cards."""
        yellow = APIFootballSource._safe_int(stat_dict.get("Yellow Cards"))
        red = APIFootballSource._safe_int(stat_dict.get("Red Cards"))
        
        if yellow is None and red is None:
            return None
        return (yellow or 0) + (red or 0)


class FBRefSource(OddsSource):
    """
    Scrape international match statistics from Football-Reference (FB-Ref).
    
    Provides: corners, cards, possession, shots, fouls from international matches.
    No API key required. Respectful scraping with delays between requests.
    """

    BASE = "https://fbref.com"

    def fetch_match_odds(self) -> list[MatchOdds]:
        """Fetch recent international matches with statistics."""
        results: list[MatchOdds] = []

        try:
            # Fetch the international matches calendar page
            resp = requests.get(
                f"{self.BASE}/en/international/",
                timeout=10,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # Find recent match links
            match_links = self._extract_recent_match_links(soup)

            for link in match_links[:15]:  # Limit to avoid excessive requests
                try:
                    time.sleep(1)  # Respectful delay between requests
                    match_stats = self._fetch_match_details(link)
                    if match_stats:
                        results.append(match_stats)
                except Exception:
                    pass  # Skip individual match failures

        except Exception as e:
            print(f"  FBRefSource: failed to fetch ({e})")

        return results

    def _extract_recent_match_links(self, soup: BeautifulSoup) -> list[str]:
        """Extract match report links from the international matches page."""
        links = []

        # Find all match rows in the schedule table
        for row in soup.find_all("tr"):
            # Look for links to match reports
            match_link = row.find("a", href=lambda x: x and "/matches/" in x if x else False)
            if match_link and match_link.get("href"):
                href = match_link["href"]
                if href.startswith("/"):
                    href = self.BASE + href
                links.append(href)

        return links

    def _fetch_match_details(self, match_url: str) -> MatchOdds | None:
        """Fetch detailed match stats from match report page."""
        resp = requests.get(match_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # Extract team names from match page
        h1 = soup.find("h1")
        if not h1:
            return None

        match_title = h1.get_text(strip=True)
        # Expected format includes "vs" somewhere
        if " vs " not in match_title:
            return None

        parts = match_title.split(" vs ")
        if len(parts) < 2:
            return None

        home_team = parts[0].strip()
        away_part = parts[1].split("|")[0].strip() if "|" in parts[1] else parts[1].strip()

        # Extract statistics from the match stats section
        stats = self._extract_match_stats(soup)

        if not stats:
            return None

        return MatchOdds(
            home_team=home_team,
            away_team=away_part,
            home_corners=stats.get("home_corners"),
            away_corners=stats.get("away_corners"),
            home_cards=stats.get("home_cards"),
            away_cards=stats.get("away_cards"),
            home_possession=stats.get("home_possession"),
            home_shots=stats.get("home_shots"),
            away_shots=stats.get("away_shots"),
            home_shots_on_target=stats.get("home_shots_on_target"),
            away_shots_on_target=stats.get("away_shots_on_target"),
            home_fouls=stats.get("home_fouls"),
            away_fouls=stats.get("away_fouls"),
        )

    @staticmethod
    def _extract_match_stats(soup: BeautifulSoup) -> dict[str, Any] | None:
        """Extract match statistics from stats tables."""
        stats: dict[str, Any] = {}

        # Find all rows that contain stats (usually in a comparison format)
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            stat_name = cells[0].get_text(strip=True).lower()
            
            try:
                home_val = cells[1].get_text(strip=True)
                away_val = cells[2].get_text(strip=True)
            except IndexError:
                continue

            # Extract numeric values
            try:
                home_num = int(home_val.split()[0]) if home_val else None
                away_num = int(away_val.split()[0]) if away_val else None
            except (ValueError, IndexError):
                continue

            # Parse different stat types
            if "corner" in stat_name:
                stats["home_corners"] = home_num
                stats["away_corners"] = away_num

            elif "yellow" in stat_name and "card" in stat_name:
                stats["home_cards"] = home_num
                stats["away_cards"] = away_num

            elif stat_name.startswith("possession"):
                try:
                    stats["home_possession"] = float(home_val.rstrip("%"))
                except ValueError:
                    pass

            elif "shot" in stat_name and "target" not in stat_name:
                stats["home_shots"] = home_num
                stats["away_shots"] = away_num

            elif "shot" in stat_name and "target" in stat_name:
                stats["home_shots_on_target"] = home_num
                stats["away_shots_on_target"] = away_num

            elif "fouls" in stat_name or "foul committed" in stat_name:
                stats["home_fouls"] = home_num
                stats["away_fouls"] = away_num

        return stats if stats else None


class FootballDataOrgSource(OddsSource):
    """
    Fetch live match odds from football-data.org (free tier, no sign-up required).

    Provides: 1X2 match odds (home_win, draw, away_win) for World Cup fixtures.
    Free tier: 10 requests/min, no API key needed for basic access.
    API key optional (set FOOTBALL_DATA_ORG_KEY in .env) for higher limits.

    Docs: https://www.football-data.org/documentation/quickstart
    """

    BASE = "https://api.football-data.org/v4"
    # World Cup 2026 competition code
    WC_CODE = "WC"

    def __init__(self, api_key: str | None = None):
        self.headers: dict[str, str] = {}
        if api_key:
            self.headers["X-Auth-Token"] = api_key

    def fetch_match_odds(self) -> list[MatchOdds]:
        results: list[MatchOdds] = []
        try:
            resp = requests.get(
                f"{self.BASE}/competitions/{self.WC_CODE}/matches",
                headers=self.headers,
                params={"status": "SCHEDULED,LIVE,IN_PLAY,PAUSED,FINISHED"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for match in data.get("matches", []):
                parsed = self._parse_match(match)
                if parsed:
                    results.append(parsed)

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status in (403, 429):
                print(
                    "  FootballDataOrgSource: World Cup needs a free API token "
                    "(set FOOTBALL_DATA_ORG_KEY in .env from football-data.org) — skipping"
                )
            else:
                print(f"  FootballDataOrgSource: failed ({e})")
        except Exception as e:
            print(f"  FootballDataOrgSource: failed ({e})")

        return results

    def _parse_match(self, match: dict[str, Any]) -> MatchOdds | None:
        home = (match.get("homeTeam") or {}).get("name", "")
        away = (match.get("awayTeam") or {}).get("name", "")
        if not home or not away:
            return None

        odds_data = match.get("odds") or {}
        home_win = away_win = draw = None

        # football-data.org returns decimal odds under match.odds
        try:
            home_d = float(odds_data.get("homeWin", 0) or 0)
            draw_d = float(odds_data.get("draw", 0) or 0)
            away_d = float(odds_data.get("awayWin", 0) or 0)

            if home_d > 1 and draw_d > 1 and away_d > 1:
                from odds import decimal_to_implied_probability, remove_vig
                fair = remove_vig([
                    decimal_to_implied_probability(home_d),
                    decimal_to_implied_probability(draw_d),
                    decimal_to_implied_probability(away_d),
                ])
                home_win, draw, away_win = fair
        except (TypeError, ValueError, ZeroDivisionError):
            pass

        if home_win is None and away_win is None and draw is None:
            return None

        return MatchOdds(
            home_team=home,
            away_team=away,
            home_win=home_win,
            away_win=away_win,
            draw=draw,
        )


class CompositeSource(OddsSource):
    """Fetch from multiple sources and merge per-fixture odds."""

    def __init__(self, sources: list[OddsSource]):
        if not sources:
            raise ValueError("CompositeSource requires at least one source")
        self.sources = sources

    def fetch_match_odds(self) -> list[MatchOdds]:
        rows: list[MatchOdds] = []
        for source in self.sources:
            name = source.__class__.__name__
            try:
                fetched = source.fetch_match_odds()
                print(f"  {name}: {len(fetched)} fixtures")
                rows.extend(fetched)
            except Exception as exc:
                print(f"  {name}: failed ({exc})")
        return merge_fixture_lists(rows)


def build_best_source(
    *,
    manual_file: str | None = None,
    odds_api_key: str | None = None,
    odds_sport_key: str = "soccer_fifa_world_cup",
    odds_regions: str = "uk,eu",
    odds_bookmakers: list[str] | None = None,
    api_football_key: str | None = None,
    football_data_org_key: str | None = None,
    fbref_scraping: bool = True,
    polymarket_tag: str = "102232",
) -> OddsSource:
    """
    Default pipeline: Polymarket (free) + football-data.org (free) + FB-Ref scraping.

    Polymarket covers World Cup prediction markets (win/draw/BTTS/totals).
    football-data.org adds bookmaker consensus odds (free, no sign-up required).
    FB-Ref scraping adds match statistics (corners, cards, possession).
    API-Football (optional) provides alternative statistics via RapidAPI.
    The Odds API (optional) fills gaps with bookmaker consensus when configured.
    """
    sources: list[OddsSource] = [PolymarketSource(tag_id=polymarket_tag)]

    # football-data.org: free, no key required, great for odds consensus
    sources.append(FootballDataOrgSource(api_key=football_data_org_key))

    # Add FB-Ref scraping by default (free, no API key needed)
    if fbref_scraping:
        sources.append(FBRefSource())

    if api_football_key:
        sources.append(APIFootballSource(api_key=api_football_key))

    if odds_api_key:
        sources.append(
            TheOddsAPISource(
                api_key=odds_api_key,
                sport_key=odds_sport_key,
                regions=odds_regions,
                bookmakers=odds_bookmakers,
                fetch_player_props=True,
            )
        )

    if manual_file:
        path = Path(manual_file)
        if path.exists():
            sources.append(ManualOddsSource(path))

    if len(sources) == 1:
        return sources[0]
    return CompositeSource(sources)


def find_match_odds(
    external: list[MatchOdds],
    match_name: str,
) -> MatchOdds | None:
    """Find external odds row for a SportsPredict match name."""
    from teams import parse_match_name

    parsed = parse_match_name(match_name)
    if not parsed:
        return None
    home, away = parsed

    for row in external:
        if (teams_match(home, row.home_team) and teams_match(away, row.away_team)) or (
            teams_match(home, row.away_team) and teams_match(away, row.home_team)
        ):
            return row
    return None
