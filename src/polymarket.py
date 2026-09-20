"""Fetch World Cup match odds from Polymarket (free, no API key)."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from matcher import MatchOdds
from odds import remove_vig
from teams import teams_match

GAMMA_API = "https://gamma-api.polymarket.com"
DEFAULT_WC_TAG = "102232"

WIN_ON = re.compile(r"will\s+(.+?)\s+win\s+on\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE)
MORE_MARKETS_SUFFIX = re.compile(r"\s*-\s*More Markets\s*$", re.IGNORECASE)
MATCH_OU = re.compile(r":\s*O/U\s+(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
MATCH_BTTS = re.compile(r":\s*Both Teams to Score\s*$", re.IGNORECASE)
TEAM_OU = re.compile(r":\s*(.+?)\s+O/U\s+(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
# First Team to Score patterns: "Spain to score first vs. Austria?"
FIRST_TO_SCORE = re.compile(r"^(.+?)\s+to\s+score\s+first\s+vs\.?\s+(.+?)\??$", re.IGNORECASE)
# Exact score: "Exact Score: Team1 N - N Team2?"  (home goals first)
EXACT_SCORE = re.compile(
    r"^Exact Score:\s*.+?\s+(\d+)\s*-\s*(\d+)\s+.+?\??$",
    re.IGNORECASE,
)
# New More Markets patterns
FIRST_HALF_OU   = re.compile(r":\s*1st Half O/U\s+(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
SECOND_HALF_OU  = re.compile(r":\s*2nd Half O/U\s+(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
TEAM_FIRST_HALF_OU  = re.compile(r":\s*(.+?)\s+1st Half O/U\s+(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
TEAM_SECOND_HALF_OU = re.compile(r":\s*(.+?)\s+2nd Half O/U\s+(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
TEAM_ADVANCE    = re.compile(r":\s*Team to Advance\s*$", re.IGNORECASE)
EXTRA_TIME      = re.compile(r"will\s+the\s+match\s+go\s+to\s+extra\s+time", re.IGNORECASE)
PENALTY_SHOOT   = re.compile(r"will\s+the\s+match\s+go\s+to\s+a\s+penalty\s+shootout", re.IGNORECASE)
BTTS_FIRST_HALF = re.compile(r":\s*Both Teams to Score in First Half\s*$", re.IGNORECASE)
BTTS_SECOND_HALF= re.compile(r":\s*Both Teams to Score in Second Half\s*$", re.IGNORECASE)


def _parse_json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _yes_probability(outcomes: list[str], prices: list[str]) -> float | None:
    for name, price in zip(outcomes, prices):
        if name.lower() == "yes":
            prob = float(price)
            if 0.0 < prob < 1.0:
                return prob
            if prob >= 1.0:
                return 1.0
            if prob <= 0.0:
                return 0.0
    # Two-outcome markets named after teams (e.g. knockout moneyline)
    return None


def _over_probability(outcomes: list[str], prices: list[str]) -> float | None:
    over = under = None
    for name, price in zip(outcomes, prices):
        label = name.lower()
        val = float(price)
        if label.startswith("over"):
            over = val
        elif label.startswith("under"):
            under = val
    if over is not None and under is not None and over + under > 0:
        fair = remove_vig([over, under])
        return fair[0]
    if over is not None and 0.0 < over < 1.0:
        return over
    return None


def _teams_from_title(title: str) -> tuple[str, str] | None:
    """Extract (home, away) from event titles including suffix variants."""
    # Strip known suffixes before extracting teams
    suffixes = [
        r"\s*-\s*More Markets\s*$",
        r"\s*-\s*Halftime Result\s*$",
        r"\s*-\s*Second Half Result\s*$",
        r"\s*-\s*Exact Score\s*$",
        r"\s*-\s*First Team to Score\s*$",
        r"\s*-\s*Total Corners\s*$",
        r"\s*-\s*Player Props\s*$",
        r"\s*-\s*First Half\s*$",
        r"\s*-\s*Second Half\s*$",
    ]
    clean = title.strip()
    for suffix in suffixes:
        clean = re.sub(suffix, "", clean, flags=re.IGNORECASE).strip()

    for sep in (" vs. ", " vs ", " v "):
        if sep in clean.lower():
            idx = clean.lower().index(sep.lower())
            home = clean[:idx].strip()
            away = clean[idx + len(sep):].strip()
            if home and away:
                return home, away
    return None


def _match_key(home: str, away: str) -> tuple[str, str]:
    """Canonical key so main + More Markets events merge reliably."""
    return (home.lower(), away.lower())


class PolymarketSource:
    """
    Pull World Cup fixture odds from Polymarket's Gamma API.

    Uses tag 102232 (FIFA World Cup). Each fixture has:
    - Main event: moneyline + draw
    - \"- More Markets\" sibling: O/U goals, BTTS, team totals
    """

    def __init__(self, tag_id: str = DEFAULT_WC_TAG):
        self.tag_id = tag_id

    def fetch_match_odds(self) -> list[MatchOdds]:
        events = self._fetch_all_events()
        by_key: dict[tuple[str, str], MatchOdds] = {}

        for event in events:
            title = event.get("title") or ""
            if "announcer" in title.lower():
                continue

            teams = _teams_from_title(title)
            if not teams:
                continue

            home, away = teams
            key = _match_key(home, away)
            row = by_key.setdefault(key, MatchOdds(home_team=home, away_team=away))

            is_more = "more markets" in title.lower() or any(
                suffix in title.lower() for suffix in (
                    "halftime result", "second half result", "exact score",
                    "first team to score", "total corners", "player props",
                )
            )
            for market in event.get("markets") or []:
                self._apply_market(row, market, home, away, is_more)

        results = []
        for row in by_key.values():
            if row.has_any_odds():
                results.append(row)
        return results

    def _fetch_all_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        offset = 0
        while True:
            resp = requests.get(
                f"{GAMMA_API}/events",
                params={
                    "tag_id": self.tag_id,
                    "active": "true",
                    "closed": "false",
                    "limit": 100,
                    "offset": offset,
                },
                timeout=30,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            events.extend(batch)
            if len(batch) < 100:
                break
            offset += 100
        return events

    def _apply_market(
        self,
        row: MatchOdds,
        market: dict[str, Any],
        home: str,
        away: str,
        is_more: bool,
    ) -> None:
        question = market.get("question") or ""
        if "announcer" in question.lower():
            return

        outcomes = _parse_json_field(market.get("outcomes")) or []
        prices = _parse_json_field(market.get("outcomePrices")) or []
        if not outcomes or not prices:
            return

        if not is_more:
            if m := WIN_ON.search(question):
                team = m.group(1).strip()
                prob = _yes_probability(outcomes, prices)
                if prob is None:
                    return
                if teams_match(team, home):
                    row.home_win = prob
                elif teams_match(team, away):
                    row.away_win = prob
            elif "end in a draw" in question.lower():
                row.draw = _yes_probability(outcomes, prices)
            return

        if m := MATCH_BTTS.search(question):
            prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.btts_yes = prob
            return

        if BTTS_FIRST_HALF.search(question):
            return  # not yet used

        if BTTS_SECOND_HALF.search(question):
            return  # not yet used

        # Team to Advance — first price = home team advancing
        if TEAM_ADVANCE.search(question):
            if len(prices) >= 2:
                try:
                    row.advance_prob = float(prices[0])
                except (ValueError, TypeError):
                    pass
            return

        # Extra time / penalty shootout
        if EXTRA_TIME.search(question):
            prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.extra_time_prob = prob
            return

        if PENALTY_SHOOT.search(question):
            prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.penalty_shootout_prob = prob
            return

        # --- Halftime Result dedicated event questions ---
        # "Spain leading at halftime?" → home team leading
        if re.search(r"^(.+?)\s+leading\s+at\s+halftime", question, re.IGNORECASE):
            m = re.search(r"^(.+?)\s+leading\s+at\s+halftime", question, re.IGNORECASE)
            team = m.group(1).strip()
            prob = _yes_probability(outcomes, prices)
            if prob is None:
                return
            # Store in first_half_team_totals under special key "halftime_lead"
            row.first_half_team_totals = row.first_half_team_totals or {}
            for candidate in (home, away):
                if teams_match(team, candidate):
                    row.first_half_team_totals.setdefault(candidate, {})["halftime_lead"] = prob
                    break
            return

        if re.search(r"draw\s+at\s+halftime", question, re.IGNORECASE):
            prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.first_half_totals = row.first_half_totals or {}
                row.first_half_totals["halftime_draw"] = prob
            return

        # --- First Team to Score dedicated event ---
        # "Spain to score first vs. Austria?" → Spain first goal probability
        if m := FIRST_TO_SCORE.search(question):
            team = m.group(1).strip()
            prob = _yes_probability(outcomes, prices)
            if prob is None:
                return
            import unicodedata
            norm = unicodedata.normalize("NFKD", team)
            norm = "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()
            row.first_goal_probs = row.first_goal_probs or {}
            row.first_goal_probs[norm] = prob
            return

        # --- Exact Score dedicated event ---
        # "Exact Score: Brazil 2 - 1 Norway?" → store (2,1) → probability
        if m := EXACT_SCORE.search(question):
            home_g = int(m.group(1))
            away_g = int(m.group(2))
            prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.exact_score_probs = row.exact_score_probs or {}
                row.exact_score_probs[(home_g, away_g)] = prob
            return

        # --- Total Corners dedicated event ---
        # "Spain vs. Austria: Spain O/U 6.5 Corners"
        CORNERS_TEAM_OU = re.compile(
            r":\s*(.+?)\s+O/U\s+(\d+(?:\.\d+)?)\s+Corners?\s*$", re.IGNORECASE
        )
        CORNERS_TOTAL_OU = re.compile(
            r":\s*O/U\s+(\d+(?:\.\d+)?)\s+Total\s+Corners?\s*$", re.IGNORECASE
        )
        if m := CORNERS_TEAM_OU.search(question):
            team = m.group(1).strip()
            line = float(m.group(2))
            prob = _over_probability(outcomes, prices)
            if prob is not None:
                row.player_props = row.player_props or {}
                for candidate in (home, away):
                    if teams_match(team, candidate):
                        import unicodedata
                        norm = unicodedata.normalize("NFKD", candidate)
                        norm = "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()
                        row.player_props[(norm, "team_corners_line", line)] = prob
                        break
            return

        if m := CORNERS_TOTAL_OU.search(question):
            line = float(m.group(1))
            prob = _over_probability(outcomes, prices)
            if prob is not None:
                row.player_props = row.player_props or {}
                row.player_props[("", "total_corners_line", line)] = prob
            return

        # --- Player Props dedicated event ---
        # "Lamine Yamal: 2+ goals" / "Lamine Yamal: 2+ shots on target" etc.
        PLAYER_PROP_Q = re.compile(
            r"^(.+?):\s*(\d+)\+\s+(goals?|shots?\s+on\s+target|shots?|assists?|goals?\s*\+\s*assists?)\s*$",
            re.IGNORECASE,
        )
        if m := PLAYER_PROP_Q.search(question):
            player = m.group(1).strip()
            threshold = int(m.group(2))
            stat_raw = m.group(3).strip().lower()
            prob = _yes_probability(outcomes, prices)
            if prob is None or not (0.0 < prob < 1.0):
                return

            import unicodedata
            def _norm(s: str) -> str:
                nfkd = unicodedata.normalize("NFKD", s)
                return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

            norm_player = _norm(player)

            if "shot" in stat_raw and "target" in stat_raw:
                mkt_key = "player_shots_on_target"
            elif "goal" in stat_raw and "assist" in stat_raw:
                mkt_key = "player_goal_or_assist"
            elif "goal" in stat_raw:
                mkt_key = "player_anytime_goalscorer"
            elif "assist" in stat_raw:
                mkt_key = "player_assists"
            elif "shot" in stat_raw:
                mkt_key = "player_shots"
            else:
                return

            row.player_props = row.player_props or {}
            row.player_props[(norm_player, mkt_key, float(threshold))] = prob
            return

        # Per-team half totals — MUST be checked before TEAM_OU and MATCH_OU
        # since TEAM_OU would also match "Spain 1st Half O/U 0.5"
        if m := TEAM_FIRST_HALF_OU.search(question):
            team = m.group(1).strip()
            line = float(m.group(2))
            prob = _over_probability(outcomes, prices)
            if prob is None:
                prob = _yes_probability(outcomes, prices)
            if prob is None:
                return
            row.first_half_team_totals = row.first_half_team_totals or {}
            for candidate in (home, away):
                if teams_match(team, candidate):
                    row.first_half_team_totals.setdefault(candidate, {})[line] = prob
                    break
            return

        if m := TEAM_SECOND_HALF_OU.search(question):
            team = m.group(1).strip()
            line = float(m.group(2))
            prob = _over_probability(outcomes, prices)
            if prob is None:
                prob = _yes_probability(outcomes, prices)
            if prob is None:
                return
            row.second_half_team_totals = row.second_half_team_totals or {}
            for candidate in (home, away):
                if teams_match(team, candidate):
                    row.second_half_team_totals.setdefault(candidate, {})[line] = prob
                    break
            return

        # Match-level half totals — only matches if no team name precedes "1st Half"
        if m := FIRST_HALF_OU.search(question):
            try:
                line = float(m.group(1))
            except ValueError:
                return  # team name captured, skip
            prob = _over_probability(outcomes, prices)
            if prob is None:
                prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.first_half_totals = row.first_half_totals or {}
                row.first_half_totals[line] = prob
            return

        if m := SECOND_HALF_OU.search(question):
            try:
                line = float(m.group(1))
            except ValueError:
                return
            prob = _over_probability(outcomes, prices)
            if prob is None:
                prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.second_half_totals = row.second_half_totals or {}
                row.second_half_totals[line] = prob
            return

        if m := MATCH_OU.search(question):
            line = float(m.group(1))
            # Try Over/Under format first, then Yes/No
            prob = _over_probability(outcomes, prices)
            if prob is None:
                prob = _yes_probability(outcomes, prices)
            if prob is not None:
                row.totals = row.totals or {}
                row.totals[line] = prob
            return

        if m := TEAM_OU.search(question):
            team = m.group(1).strip()
            line = float(m.group(2))
            # Try Over/Under format first, then Yes/No
            prob = _over_probability(outcomes, prices)
            if prob is None:
                prob = _yes_probability(outcomes, prices)
            if prob is None:
                return
            row.team_totals = row.team_totals or {}
            for candidate in (home, away):
                if teams_match(team, candidate):
                    row.team_totals.setdefault(candidate, {})[line] = prob
                    break
