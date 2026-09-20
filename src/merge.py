"""Merge and combine odds from multiple sources."""

from __future__ import annotations

from matcher import MatchOdds
from teams import teams_match


def _avg(a: float | None, b: float | None) -> float | None:
    if a is not None and b is not None:
        return (a + b) / 2
    return a if a is not None else b


def _merge_float_dicts(
    left: dict[float, float] | None,
    right: dict[float, float] | None,
) -> dict[float, float] | None:
    if not left and not right:
        return None
    left = left or {}
    right = right or {}
    keys = set(left) | set(right)
    merged = {k: _avg(left.get(k), right.get(k)) for k in keys}
    return {k: v for k, v in merged.items() if v is not None}


def _merge_team_totals(
    left: dict[str, dict[float, float]] | None,
    right: dict[str, dict[float, float]] | None,
) -> dict[str, dict[float, float]] | None:
    if not left and not right:
        return None
    left = dict(left or {})
    right = dict(right or {})
    merged = dict(left)
    for rt_team, rt_lines in right.items():
        matched = False
        for lt_team in list(merged.keys()):
            if teams_match(lt_team, rt_team):
                combined = _merge_float_dicts(merged[lt_team], rt_lines)
                if combined:
                    merged[lt_team] = combined
                matched = True
                break
        if not matched:
            merged[rt_team] = rt_lines
    return merged or None


def _merge_player_props(
    left: dict | None,
    right: dict | None,
) -> dict | None:
    """Average overlapping player props; keep unique entries from each source."""
    if not left and not right:
        return None
    merged = dict(left or {})
    for key, prob in (right or {}).items():
        if key in merged:
            merged[key] = (merged[key] + prob) / 2.0
        else:
            merged[key] = prob
    return merged or None


def merge_match_odds(left: MatchOdds, right: MatchOdds) -> MatchOdds:
    """Average overlapping fields; keep whichever source has data for gaps."""
    return MatchOdds(
        home_team=left.home_team,
        away_team=left.away_team,
        home_win=_avg(left.home_win, right.home_win),
        away_win=_avg(left.away_win, right.away_win),
        draw=_avg(left.draw, right.draw),
        btts_yes=_avg(left.btts_yes, right.btts_yes),
        totals=_merge_float_dicts(left.totals, right.totals),
        team_totals=_merge_team_totals(left.team_totals, right.team_totals),
        player_props=_merge_player_props(left.player_props, right.player_props),
        first_half_totals=_merge_float_dicts(left.first_half_totals, right.first_half_totals),
        second_half_totals=_merge_float_dicts(left.second_half_totals, right.second_half_totals),
        first_half_team_totals=_merge_team_totals(left.first_half_team_totals, right.first_half_team_totals),
        second_half_team_totals=_merge_team_totals(left.second_half_team_totals, right.second_half_team_totals),
        advance_prob=_avg(left.advance_prob, right.advance_prob),
        extra_time_prob=_avg(left.extra_time_prob, right.extra_time_prob),
        penalty_shootout_prob=_avg(left.penalty_shootout_prob, right.penalty_shootout_prob),
        first_goal_probs=_merge_player_props(left.first_goal_probs, right.first_goal_probs),
        exact_score_probs={**( left.exact_score_probs or {}), **(right.exact_score_probs or {})} or None,
        # Preserve match statistics — take whichever side has data
        home_corners=left.home_corners if left.home_corners is not None else right.home_corners,
        away_corners=left.away_corners if left.away_corners is not None else right.away_corners,
        home_cards=left.home_cards if left.home_cards is not None else right.home_cards,
        away_cards=left.away_cards if left.away_cards is not None else right.away_cards,
        home_possession=left.home_possession if left.home_possession is not None else right.home_possession,
        home_shots=left.home_shots if left.home_shots is not None else right.home_shots,
        away_shots=left.away_shots if left.away_shots is not None else right.away_shots,
        home_shots_on_target=left.home_shots_on_target if left.home_shots_on_target is not None else right.home_shots_on_target,
        away_shots_on_target=left.away_shots_on_target if left.away_shots_on_target is not None else right.away_shots_on_target,
        home_fouls=left.home_fouls if left.home_fouls is not None else right.home_fouls,
        away_fouls=left.away_fouls if left.away_fouls is not None else right.away_fouls,
    )


def merge_fixture_lists(rows: list[MatchOdds]) -> list[MatchOdds]:
    """Collapse multiple MatchOdds rows for the same fixture into one."""
    by_fixture: dict[tuple[str, str], MatchOdds] = {}
    for row in rows:
        key = (row.home_team.lower(), row.away_team.lower())
        if key in by_fixture:
            by_fixture[key] = merge_match_odds(by_fixture[key], row)
        else:
            by_fixture[key] = row
    return list(by_fixture.values())
