"""Estimate team stat-market probabilities from historical international data.

All estimates use team-specific historical rates from data/team_history.json
(StatsBomb open data: WC 2018/2022, Euro 2020/2024, Copa America 2024, AFCON 2023).

Opponent adjustment (used for shot/corner markets):
    A team's shots on target in a given match depends on both how many they
    generate AND how many the opponent typically allows. We model this as a
    geometric mean of the attacker's own rate and the opponent's concession rate,
    normalised by the league average:

        adjusted_lam = attacker_rate * (opponent_conceded / league_average)

    Markets that don't depend on the opponent (cards, fouls, early subs, offsides,
    penalties, red cards) use the team's own rate directly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from poisson import poisson_pmf, prob_at_least, split_lambda
from teams import teams_match

TEAM_HISTORY_FILE = Path(__file__).parent.parent / "data" / "team_history.json"

# League-average rates across all 76 teams in the dataset (used as the
# normalising denominator in opponent adjustments).
_LEAGUE_AVG: dict[str, float] = {
    "shots_on_target_per_match":  4.0,
    "shots_total_per_match":     13.0,
    "corners_per_match":          5.0,
    "sot_conceded_per_match":     4.0,
    "shots_conceded_per_match":  13.0,
    "corners_conceded_per_match": 5.0,
}

# Fallbacks for teams absent from the historical data (neutral rates).
FALLBACK_RATES: dict[str, float] = {
    "shots_on_target_per_match":      4.0,
    "shots_total_per_match":         13.0,
    "corners_per_match":              5.0,
    "cards_per_match":                1.9,
    "red_cards_per_match":            0.06,
    "penalties_conceded_per_match":   0.15,
    "offsides_per_match":             1.7,
    "fouls_per_match":               13.5,
    "header_goal_fraction":           0.17,
    "early_sub_rate":                 0.12,
    "sot_conceded_per_match":         4.0,
    "shots_conceded_per_match":      13.0,
    "corners_conceded_per_match":     5.0,
}

# Calibration scalar for cards.
#
# Our historical per-team rates come from StatsBomb data spanning Copa America,
# AFCON, and Euros — competitions that run hotter than World Cup knockout games.
# The combined (home + away) mean across 76 teams is ~3.8 cards/game, but real
# WC 2022/2018 averages were ~3.0-3.2 total cards/game, and bookmakers typically
# price combined totals around 2.5-3.5 for most fixtures.
#
# Scaling the raw historical rate by 0.65 brings the dataset mean from ~3.8 to
# ~2.5 per team pair, consistent with WC bookmaker lines.  Teams with genuinely
# higher rates (e.g. Colombia 2.3, Ghana 2.83) will still show elevated lambdas
# relative to quieter teams, preserving the relative ordering.
_CARDS_SCALE: float = 0.65

_cache: dict[str, dict[str, Any]] | None = None


def _load() -> dict[str, dict[str, Any]]:
    global _cache
    if _cache is None:
        if TEAM_HISTORY_FILE.exists():
            _cache = json.loads(TEAM_HISTORY_FILE.read_text(encoding="utf-8"))
            # Compute true league averages from the loaded data.
            if _cache:
                for key in list(_LEAGUE_AVG):
                    vals = [v[key] for v in _cache.values() if key in v and v[key] is not None]
                    if vals:
                        _LEAGUE_AVG[key] = sum(vals) / len(vals)
        else:
            _cache = {}
    return _cache


def get_team_rates(team: str) -> dict[str, Any] | None:
    for name, data in _load().items():
        if teams_match(team, name):
            return data
    return None


def _rate(team: str, key: str) -> float:
    data = get_team_rates(team)
    if data and data.get(key) is not None:
        return float(data[key])
    return FALLBACK_RATES.get(key, 0.0)


def _threshold(line: float) -> int:
    return int(math.ceil(line))


def _opponent_adjusted_lam(attacker: str, defender: str, atk_key: str, def_key: str) -> float:
    """
    Lightly adjust attacker's rate for how permissive the defender is.

    Uses a blended formula with ALPHA=0.25 so the opponent's defensive record
    nudges the estimate without dominating it — a small defensive sample can't
    swing the result by more than ~15-20%.

        adjusted = own_rate × (1 - α + α × defender_conceded/league_avg)

    At α=0: opponent ignored (pure own rate).
    At α=1: full multiplicative adjustment (original aggressive behaviour).
    α=0.25 is a middle ground validated against bookmaker lines.
    """
    ALPHA = 0.25
    atk_rate = _rate(attacker, atk_key)
    def_conc = _rate(defender, def_key)
    avg_conc = _LEAGUE_AVG.get(def_key, FALLBACK_RATES.get(def_key, 1.0))
    if avg_conc <= 0:
        return atk_rate
    factor = def_conc / avg_conc
    return atk_rate * (1.0 - ALPHA + ALPHA * factor)


def _possession_adjusted_corners(
    attacker: str,
    defender: str,
    home_win: float | None = None,
    away_win: float | None = None,
    is_home: bool = True,
) -> float:
    """
    Corners adjusted for expected possession share.

    Weaker teams have their corner rate suppressed (they won't attack much),
    while stronger teams get a modest boost. The scaling is asymmetric:
    - Suppression (below 50% possession) is applied at full strength (k=1.0)
    - Boost (above 50% possession) is applied at half strength (k=0.5)
    This reflects that dominant possession teams generate proportionally
    more corners but not as dramatically as weak teams lose them.
    """
    base = _opponent_adjusted_lam(
        attacker, defender, "corners_per_match", "corners_conceded_per_match"
    )
    if home_win is None or away_win is None:
        return base

    total = home_win + away_win
    if total <= 0:
        return base

    raw_share = home_win / total if is_home else away_win / total
    possession_share = 0.5 + 0.5 * (raw_share - 0.5)  # dampened from win prob
    possession_share = max(0.25, min(0.75, possession_share))

    diff = possession_share - 0.5  # negative for underdog, positive for favourite
    if diff < 0:
        # Underdog: full suppression (k=1.0)
        scaling = 1.0 + 1.0 * diff / 0.5
    else:
        # Favourite: half boost (k=0.5)
        scaling = 1.0 + 0.5 * diff / 0.5

    scaling = max(0.3, scaling)  # floor to avoid going to zero
    return base * scaling


# ---------------------------------------------------------------------------
# Shots on target  (opponent-adjusted)
# ---------------------------------------------------------------------------

def estimate_team_shots_on_target_probability(
    team: str, line: float, opponent: str | None = None
) -> float:
    if opponent:
        lam = _opponent_adjusted_lam(
            team, opponent,
            "shots_on_target_per_match", "sot_conceded_per_match",
        )
    else:
        lam = _rate(team, "shots_on_target_per_match")
    return round(prob_at_least(_threshold(line), lam), 3)


# ---------------------------------------------------------------------------
# Total shots on+off target  (opponent-adjusted, both teams combined)
# ---------------------------------------------------------------------------

def estimate_total_shots_probability(home: str, away: str, line: float) -> float:
    lam_home = _opponent_adjusted_lam(
        home, away, "shots_total_per_match", "shots_conceded_per_match"
    )
    lam_away = _opponent_adjusted_lam(
        away, home, "shots_total_per_match", "shots_conceded_per_match"
    )
    return round(prob_at_least(_threshold(line), lam_home + lam_away), 3)


# ---------------------------------------------------------------------------
# Corners  (opponent-adjusted)
# ---------------------------------------------------------------------------

def estimate_team_corners_probability(
    team: str, line: float, opponent: str | None = None,
    home_win: float | None = None, away_win: float | None = None,
    is_home: bool = True,
) -> float:
    if opponent:
        lam = _possession_adjusted_corners(
            team, opponent, home_win=home_win, away_win=away_win, is_home=is_home
        )
    else:
        lam = _rate(team, "corners_per_match")
    return round(prob_at_least(_threshold(line), lam), 3)


def estimate_total_corners_probability(home: str, away: str, line: float,
                                       home_win: float | None = None,
                                       away_win: float | None = None) -> float:
    lam_home = _possession_adjusted_corners(
        home, away, home_win=home_win, away_win=away_win, is_home=True
    )
    lam_away = _possession_adjusted_corners(
        away, home, home_win=home_win, away_win=away_win, is_home=False
    )
    return round(prob_at_least(_threshold(line), lam_home + lam_away), 3)


def estimate_more_corners_than(team_a: str, team_b: str, max_corners: int = 25,
                                home_win: float | None = None,
                                away_win: float | None = None) -> float:
    """P(team_a takes more corners than team_b) — possession-adjusted Poisson."""
    lam_a = _possession_adjusted_corners(
        team_a, team_b, home_win=home_win, away_win=away_win, is_home=True
    )
    lam_b = _possession_adjusted_corners(
        team_b, team_a, home_win=home_win, away_win=away_win, is_home=False
    )
    prob = 0.0
    for a in range(max_corners + 1):
        pa = poisson_pmf(a, lam_a)
        for b in range(a):
            prob += pa * poisson_pmf(b, lam_b)
    return round(prob, 3)


# ---------------------------------------------------------------------------
# Cards  (own rate only — opponent doesn't change how many cards YOU receive)
# ---------------------------------------------------------------------------


def estimate_team_cards_probability(team: str, line: float) -> float:
    lam = _rate(team, "cards_per_match") * _CARDS_SCALE
    return round(prob_at_least(_threshold(line), lam), 3)


def estimate_total_cards_probability(home: str, away: str, line: float) -> float:
    lam = (_rate(home, "cards_per_match") + _rate(away, "cards_per_match")) * _CARDS_SCALE
    return round(prob_at_least(_threshold(line), lam), 3)


def estimate_both_teams_card_probability(home: str, away: str) -> float:
    lam_home = _rate(home, "cards_per_match") * _CARDS_SCALE
    lam_away = _rate(away, "cards_per_match") * _CARDS_SCALE
    p_home = 1.0 - math.exp(-lam_home)
    p_away = 1.0 - math.exp(-lam_away)
    return round(p_home * p_away, 3)


# ---------------------------------------------------------------------------
# Offsides  (own rate only — offsides depend on your own attacking movement)
# ---------------------------------------------------------------------------

def estimate_total_offsides_probability(home: str, away: str, line: float) -> float:
    lam = _rate(home, "offsides_per_match") + _rate(away, "offsides_per_match")
    return round(prob_at_least(_threshold(line), lam), 3)


# ---------------------------------------------------------------------------
# Penalty awarded OR red card  (own rates only)
# ---------------------------------------------------------------------------

def estimate_penalty_or_red_probability(home: str, away: str) -> float:
    lam_pen = (_rate(home, "penalties_conceded_per_match")
               + _rate(away, "penalties_conceded_per_match"))
    lam_red = (_rate(home, "red_cards_per_match")
               + _rate(away, "red_cards_per_match"))
    return round(1.0 - math.exp(-lam_pen) * math.exp(-lam_red), 3)


# ---------------------------------------------------------------------------
# Header goal  (opponent-adjusted SOT split, team header fraction)
# ---------------------------------------------------------------------------

def estimate_header_goal_probability(
    home: str,
    away: str,
    lam_total: float,
    home_win: float | None = None,
    away_win: float | None = None,
) -> float:
    """
    P(>=1 header goal).  Uses win-probability-weighted goal split so that the
    stronger team contributes a larger share of expected goals.
    Each team's share is then scaled by their historical header-goal fraction.
    """
    lam_home, lam_away = split_lambda(lam_total, home_win, away_win)
    lam_headers = (lam_home * _rate(home, "header_goal_fraction")
                   + lam_away * _rate(away, "header_goal_fraction"))
    return round(1.0 - math.exp(-lam_headers), 3)


# ---------------------------------------------------------------------------
# Early substitution  (own rate only)
# ---------------------------------------------------------------------------

def estimate_early_sub_probability(home: str, away: str) -> float:
    p_no_home = 1.0 - _rate(home, "early_sub_rate")
    p_no_away = 1.0 - _rate(away, "early_sub_rate")
    return round(1.0 - p_no_home * p_no_away, 3)
