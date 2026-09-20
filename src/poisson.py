"""Poisson goal model for time-window and scoreline markets.

Football goals are well approximated by a Poisson process. Given a fixture's
expected total goals (lambda), we can estimate:
  - P(at least one goal in a given time window) — used for hydration-break markets
  - First-half scoreline distribution — used for "ahead/tied at halftime" markets
"""

from __future__ import annotations

import math

# Regulation length used to scale goal rates to a time window.
MATCH_MINUTES = 90.0

# League-average combined offside calls per match (both teams).
# International fixtures typically see ~4-5 offsides total; 4.5 is a reasonable
# neutral baseline when no team-specific offside data is available.


def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(lam)."""
    return math.exp(-lam) * lam**k / math.factorial(k)


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for X ~ Poisson(lam)."""
    return sum(poisson_pmf(i, lam) for i in range(k + 1))


def prob_over(line: float, lam: float) -> float:
    """P(total goals > line) for a half-integer line (e.g. 2.5 -> P(X >= 3))."""
    k = math.floor(line)
    return 1.0 - poisson_cdf(k, lam)


def prob_at_least(n: int, lam: float) -> float:
    """P(X >= n) for X ~ Poisson(lam)."""
    if n <= 0:
        return 1.0
    return 1.0 - poisson_cdf(n - 1, lam)


def estimate_lambda_from_totals(totals: dict[float, float] | None) -> float | None:
    """
    Back out expected total goals (lambda) from over/under fair probabilities.

    Picks the line whose P(over) is closest to 0.5 (most informative), then
    bisection-solves for the lambda that reproduces that probability.
    """
    if not totals:
        return None

    usable = [(line, p) for line, p in totals.items()
              if isinstance(line, (int, float)) and 0.0 < p < 1.0]
    if not usable:
        return None

    line, target = min(usable, key=lambda kv: abs(kv[1] - 0.5))

    lo, hi = 0.05, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if prob_over(line, mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def estimate_lambda_from_match_odds(match_odds) -> float | None:
    """
    Back out expected total goals from any available source on MatchOdds.

    Priority:
    1. match_odds.totals (direct O/U goal lines from Polymarket More Markets)
    2. match_odds.first_half_totals + second_half_totals (Polymarket half O/U lines)
    3. None
    """
    lam = estimate_lambda_from_totals(match_odds.totals)
    if lam is not None:
        return lam

    # Derive from half totals: lambda_total ≈ lambda_H1 + lambda_H2
    ft1 = match_odds.first_half_totals or {}
    ft2 = match_odds.second_half_totals or {}

    # P(X >= 1 in half) = 1 - e^(-lambda_half) → lambda_half = -ln(1 - p)
    import math
    p_h1 = ft1.get(0.5)
    p_h2 = ft2.get(0.5)
    if p_h1 is not None and p_h2 is not None and 0 < p_h1 < 1 and 0 < p_h2 < 1:
        lam_h1 = -math.log(1 - p_h1)
        lam_h2 = -math.log(1 - p_h2)
        return lam_h1 + lam_h2

    # Try 1st half O/U 1.5 line if 0.5 not available
    p_h1_15 = ft1.get(1.5)
    if p_h1_15 is not None and 0 < p_h1_15 < 1:
        lam_h1 = _bisect_lam_from_over(1.5, p_h1_15)
        # Assume 2nd half similar to 1st
        return lam_h1 * 2.0

    return None


def _bisect_lam_from_over(line: float, target: float) -> float:
    lo, hi = 0.05, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if prob_over(line, mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def prob_goal_in_window(lam: float, minutes: float, start: float = 0.0) -> float:
    """
    P(at least one goal scored in a window [start, start+minutes]).

    Goals are NOT uniformly distributed across 90 minutes — they cluster toward
    the end of each half (injury-time pile-up) and are less frequent early on.
    WC historical data shows roughly:
      - First 30 min: ~22% of goals  (vs 33% uniform)
      - 30–60 min:    ~33% of goals  (close to uniform)
      - 60–90 min:    ~45% of goals  (vs 33% uniform)

    We model this with a simple piecewise-linear rate multiplier:
      - [0,  30): multiplier = 0.67
      - [30, 60): multiplier = 1.00
      - [60, 90): multiplier = 1.33

    The multipliers integrate to 90 min × 1.0 average = 90 min, preserving lambda.
    """
    BREAKPOINTS = [(0.0, 30.0, 0.67), (30.0, 60.0, 1.00), (60.0, 90.0, 1.33)]
    end = start + minutes
    effective_minutes = 0.0
    for seg_start, seg_end, mult in BREAKPOINTS:
        overlap_start = max(start, seg_start)
        overlap_end   = min(end,   seg_end)
        if overlap_end > overlap_start:
            effective_minutes += (overlap_end - overlap_start) * mult
    rate = lam * effective_minutes / MATCH_MINUTES
    return 1.0 - math.exp(-rate)


def split_lambda(
    lam_total: float,
    home_win: float | None,
    away_win: float | None,
) -> tuple[float, float]:
    """
    Split total expected goals into (home, away) shares.

    Uses a lightly dampened formula calibrated so that:
    - A ~60/40 win probability split → ~60/40 goal split
    - A ~90/10 win probability split → ~80/20 goal split (not 90/10)

    Dampening factor of 0.7 limits extreme skew while still giving the
    dominant team a meaningful majority of expected goals.
    Falls back to even split when win probabilities are unavailable.
    """
    if home_win is not None and away_win is not None and (home_win + away_win) > 0:
        raw_share = home_win / (home_win + away_win)
        # Dampening factor 0.7: limits extreme skew while preserving the signal.
        home_share = 0.5 + 0.7 * (raw_share - 0.5)
    else:
        home_share = 0.5
    return lam_total * home_share, lam_total * (1.0 - home_share)


def scoreline_probs(
    lam_home: float,
    lam_away: float,
    max_goals: int = 8,
) -> tuple[float, float, float]:
    """
    Independent-Poisson scoreline model.

    Returns (P(home leads), P(tied), P(away leads)) over the modelled period.
    """
    p_home_lead = p_tie = p_away_lead = 0.0
    for h in range(max_goals + 1):
        ph = poisson_pmf(h, lam_home)
        for a in range(max_goals + 1):
            pa = poisson_pmf(a, lam_away)
            joint = ph * pa
            if h > a:
                p_home_lead += joint
            elif h == a:
                p_tie += joint
            else:
                p_away_lead += joint
    return p_home_lead, p_tie, p_away_lead


def prob_second_half_more_goals(lam: float, max_goals: int = 10) -> float:
    """
    P(more goals in the second half than the first).

    Both halves are modelled as independent Poisson(lam / 2) over total match
    goals. The comparison is symmetric, so this sits just under 0.5 (the
    remainder is the probability the two halves tie).
    """
    half = lam / 2.0
    p_more = 0.0
    for second in range(max_goals + 1):
        p_second = poisson_pmf(second, half)
        for first in range(second):
            p_more += p_second * poisson_pmf(first, half)
    return p_more

