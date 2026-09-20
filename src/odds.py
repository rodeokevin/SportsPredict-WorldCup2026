"""Convert betting odds to SportsPredict probabilities (1–99)."""

from __future__ import annotations


def decimal_to_implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError(f"Invalid decimal odds: {decimal_odds}")
    return 1.0 / decimal_odds


def american_to_implied_probability(american: int) -> float:
    if american == 0:
        raise ValueError("American odds cannot be zero")
    if american > 0:
        return 100.0 / (american + 100.0)
    return abs(american) / (abs(american) + 100.0)


def remove_vig(probabilities: list[float]) -> list[float]:
    """Normalize implied probabilities so they sum to 1 (fair odds)."""
    total = sum(probabilities)
    if total <= 0:
        raise ValueError("Probabilities must sum to a positive value")
    return [p / total for p in probabilities]


def to_sp_probability(probability: float) -> int:
    """Scale 0–1 probability to SportsPredict's 1–99 integer range."""
    pct = round(probability * 100)
    return max(1, min(99, pct))


def average_decimal_odds(odds_list: list[float]) -> float | None:
    if not odds_list:
        return None
    return sum(odds_list) / len(odds_list)
