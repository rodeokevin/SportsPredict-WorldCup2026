"""Fetch match statistics from Football-Reference (FB-Ref) for international matches."""

from __future__ import annotations

import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from matcher import MatchOdds
from teams import normalize_team, teams_match


class FBRefStatsSource:
    """
    Scrape international match statistics from Football-Reference.
    
    Data available: corners, cards, possession, shots, fouls from finished matches.
    No API key required. Respectful scraping with delays between requests.
    """

    BASE = "https://fbref.com"
    INTERNATIONAL_COMP_IDS = {
        "FIFA World Cup": "96",
        "UEFA Euro": "106",
        "Copa América": "3",
        "Africa Cup of Nations": "206",
    }

    def fetch_recent_matches(self, days_back: int = 7) -> list[MatchOdds]:
        """Fetch recent international matches with statistics."""
        results: list[MatchOdds] = []

        try:
            # Fetch the international matches calendar
            resp = requests.get(
                f"{self.BASE}/en/international/",
                timeout=10,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # Find recent match links
            match_links = self._extract_recent_match_links(soup, days_back)

            for link in match_links[:10]:  # Limit to avoid rate limiting
                try:
                    time.sleep(1)  # Respectful delay
                    match_stats = self._fetch_match_details(link)
                    if match_stats:
                        results.append(match_stats)
                except Exception as e:
                    print(f"    Failed to parse match {link}: {e}")

        except Exception as e:
            print(f"  FBRefStatsSource: failed to fetch ({e})")

        return results

    def _extract_recent_match_links(self, soup: BeautifulSoup, days_back: int) -> list[str]:
        """Extract match report links from the international matches page."""
        links = []

        # Find all match rows in the schedule table
        for row in soup.find_all("tr", class_=""):
            cells = row.find_all("td")
            if not cells or len(cells) < 6:
                continue

            # Check if match is finished (has a link to match report)
            match_link = row.find("a", href=lambda x: x and "/matches/" in x)
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

        # Extract team names
        h1 = soup.find("h1")
        if not h1:
            return None

        match_title = h1.get_text(strip=True)
        # Expected format: "Team A vs Team B | Match Report | ..."
        if " vs " not in match_title:
            return None

        parts = match_title.split(" vs ")
        if len(parts) < 2:
            return None

        home_team = parts[0].strip()
        away_part = parts[1].split("|")[0].strip()

        # Extract statistics from the match stats table
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
        """Extract match statistics from stats table."""
        stats = {}

        # Find the team stats table
        # FB-Ref format: table with rows like "Corners: 5 vs 3"
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            stat_name = cells[0].get_text(strip=True)
            home_val = cells[1].get_text(strip=True)
            away_val = cells[2].get_text(strip=True)

            stat_lower = stat_name.lower()

            if "corner" in stat_lower:
                try:
                    stats["home_corners"] = int(home_val.split()[0])
                    stats["away_corners"] = int(away_val.split()[0])
                except (ValueError, IndexError):
                    pass

            elif "yellow" in stat_lower or "card" in stat_lower:
                try:
                    # Format might be "2 Yellow" or "2"
                    home_yellows = int(home_val.split()[0]) if home_val else 0
                    away_yellows = int(away_val.split()[0]) if away_val else 0
                    stats["home_cards"] = home_yellows
                    stats["away_cards"] = away_yellows
                except (ValueError, IndexError):
                    pass

            elif "possession" in stat_lower:
                try:
                    home_pct = int(home_val.rstrip("%"))
                    stats["home_possession"] = float(home_pct)
                except (ValueError, IndexError):
                    pass

            elif "shot" in stat_lower and "target" not in stat_lower:
                try:
                    stats["home_shots"] = int(home_val.split()[0])
                    stats["away_shots"] = int(away_val.split()[0])
                except (ValueError, IndexError):
                    pass

            elif "shot" in stat_lower and "target" in stat_lower:
                try:
                    stats["home_shots_on_target"] = int(home_val.split()[0])
                    stats["away_shots_on_target"] = int(away_val.split()[0])
                except (ValueError, IndexError):
                    pass

            elif "fouls" in stat_lower or "foul" in stat_lower:
                try:
                    stats["home_fouls"] = int(home_val.split()[0])
                    stats["away_fouls"] = int(away_val.split()[0])
                except (ValueError, IndexError):
                    pass

        return stats if stats else None
