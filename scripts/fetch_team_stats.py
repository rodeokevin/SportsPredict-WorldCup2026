#!/usr/bin/env python3
"""
Build data/team_history.json from StatsBomb open data.

Tracks both what each team PRODUCES and what they CONCEDE per match,
so opponent-adjusted models can be built (e.g. shots on target adjusted
for how many the opponent typically allows).

Stats per team per match:
    Attacking (produced):
        shots_on_target, shots_total, header_shots, header_goals,
        corners, offsides
    Disciplinary (produced):
        cards, red_cards, penalties_conceded, fouls, early_sub_matches
    Defensive (conceded from opponent):
        sot_conceded, shots_conceded, corners_conceded
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests

RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
TEAM_HISTORY_FILE = Path(__file__).parent.parent / "data" / "team_history.json"

COMPETITIONS: list[tuple[int, int, str]] = [
    (43,   3,   "FIFA World Cup 2018"),
    (43,   106, "FIFA World Cup 2022"),
    (55,   43,  "UEFA Euro 2020"),
    (55,   282, "UEFA Euro 2024"),
    (223,  282, "Copa America 2024"),
    (1267, 107, "Africa Cup of Nations 2023"),
]

ON_TARGET      = {"Goal", "Saved", "Saved To Post"}
CARD_NAMES     = {"Yellow Card", "Second Yellow", "Red Card"}
RED_CARD_NAMES = {"Second Yellow", "Red Card"}

_session = requests.Session()
_session.headers.update({"User-Agent": "SportsPredict-stats-builder/1.0"})


def _get(url: str) -> Any:
    resp = _session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _blank() -> dict[str, float]:
    return {
        "matches": 0,
        # Attacking
        "shots_on_target": 0,
        "shots_total": 0,
        "header_shots": 0,
        "header_goals": 0,
        "corners": 0,
        "offsides": 0,
        # Disciplinary
        "cards": 0,
        "red_cards": 0,
        "penalties_conceded": 0,
        "fouls": 0,
        "early_sub_matches": 0,
        # Defensive (what the opponent produced against this team)
        "sot_conceded": 0,
        "shots_conceded": 0,
        "corners_conceded": 0,
    }


def process_match(match_id: int, totals: dict[str, dict[str, float]]) -> None:
    events = _get(f"{RAW}/events/{match_id}.json")

    per_team: dict[str, dict[str, int]] = defaultdict(lambda: {
        "shots_on_target": 0, "shots_total": 0,
        "header_shots": 0, "header_goals": 0,
        "corners": 0, "offsides": 0,
        "cards": 0, "red_cards": 0,
        "penalties_conceded": 0, "fouls": 0,
        "early_sub": 0,
    })
    teams_seen: set[str] = set()

    for e in events:
        team  = (e.get("team") or {}).get("name")
        etype = (e.get("type") or {}).get("name")
        if team:
            teams_seen.add(team)
        if e.get("period") == 5:
            continue
        if not team or not etype:
            continue

        if etype == "Shot":
            shot_info = e.get("shot") or {}
            outcome   = (shot_info.get("outcome") or {}).get("name", "")
            body_part = (shot_info.get("body_part") or {}).get("name", "")
            per_team[team]["shots_total"] += 1
            if outcome in ON_TARGET:
                per_team[team]["shots_on_target"] += 1
            if body_part == "Head":
                per_team[team]["header_shots"] += 1
                if outcome == "Goal":
                    per_team[team]["header_goals"] += 1

        elif etype == "Pass":
            pass_info = e.get("pass") or {}
            if (pass_info.get("type") or {}).get("name") == "Corner":
                per_team[team]["corners"] += 1
            if (pass_info.get("outcome") or {}).get("name") == "Pass Offside":
                per_team[team]["offsides"] += 1

        elif etype == "Offside":
            per_team[team]["offsides"] += 1

        elif etype == "Foul Committed":
            per_team[team]["fouls"] += 1
            foul_info = e.get("foul_committed") or {}
            card = (foul_info.get("card") or {}).get("name", "")
            if card in CARD_NAMES:
                per_team[team]["cards"] += 1
            if card in RED_CARD_NAMES:
                per_team[team]["red_cards"] += 1
            if foul_info.get("penalty"):
                per_team[team]["penalties_conceded"] += 1

        elif etype == "Bad Behaviour":
            card = ((e.get("bad_behaviour") or {}).get("card") or {}).get("name", "")
            if card in CARD_NAMES:
                per_team[team]["cards"] += 1
            if card in RED_CARD_NAMES:
                per_team[team]["red_cards"] += 1

        elif etype == "Substitution":
            if e.get("period") == 1:
                per_team[team]["early_sub"] = 1

    # Fold into running totals. For exactly 2 teams in a match, each team's
    # "conceded" stats = the other team's attacking stats.
    team_list = list(teams_seen)
    for team in team_list:
        agg = totals.setdefault(team, _blank())
        agg["matches"] += 1
        stats = per_team.get(team, {})
        for key in (
            "shots_on_target", "shots_total", "header_shots", "header_goals",
            "corners", "offsides", "cards", "red_cards", "penalties_conceded", "fouls",
        ):
            agg[key] += stats.get(key, 0)
        agg["early_sub_matches"] += stats.get("early_sub", 0)

    # Credit conceded stats: each team concedes what the opponent produced.
    if len(team_list) == 2:
        t0, t1 = team_list[0], team_list[1]
        s0, s1 = per_team.get(t0, {}), per_team.get(t1, {})
        totals[t0]["sot_conceded"]     += s1.get("shots_on_target", 0)
        totals[t0]["shots_conceded"]   += s1.get("shots_total", 0)
        totals[t0]["corners_conceded"] += s1.get("corners", 0)
        totals[t1]["sot_conceded"]     += s0.get("shots_on_target", 0)
        totals[t1]["shots_conceded"]   += s0.get("shots_total", 0)
        totals[t1]["corners_conceded"] += s0.get("corners", 0)


def build() -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, float]] = {}

    for comp_id, season_id, label in COMPETITIONS:
        print(f"\n=== {label} (comp {comp_id}, season {season_id}) ===")
        try:
            matches = _get(f"{RAW}/matches/{comp_id}/{season_id}.json")
        except Exception as exc:
            print(f"  failed to load matches: {exc}")
            continue

        for i, match in enumerate(matches, 1):
            mid  = match["match_id"]
            home = match["home_team"]["home_team_name"]
            away = match["away_team"]["away_team_name"]
            try:
                process_match(mid, totals)
                print(f"  [{i}/{len(matches)}] {home} vs {away}")
            except Exception as exc:
                print(f"  [{i}/{len(matches)}] {home} vs {away} — skipped ({exc})")

    history: dict[str, dict[str, Any]] = {}
    for team, agg in totals.items():
        m = max(int(agg["matches"]), 1)
        total_goals = agg.get("header_goals", 0) + max(
            agg.get("shots_on_target", 0) - agg.get("header_goals", 0), 0
        )
        header_frac = agg["header_goals"] / total_goals if total_goals > 0 else 0.17

        history[team] = {
            "matches":                      int(agg["matches"]),
            # Attacking per match
            "shots_on_target_per_match":    round(agg["shots_on_target"]       / m, 3),
            "shots_total_per_match":        round(agg["shots_total"]           / m, 3),
            "header_shots_per_match":       round(agg["header_shots"]          / m, 3),
            "header_goal_fraction":         round(header_frac, 3),
            "corners_per_match":            round(agg["corners"]               / m, 3),
            "offsides_per_match":           round(agg["offsides"]              / m, 3),
            # Disciplinary per match
            "cards_per_match":              round(agg["cards"]                 / m, 3),
            "red_cards_per_match":          round(agg["red_cards"]             / m, 3),
            "penalties_conceded_per_match": round(agg["penalties_conceded"]    / m, 3),
            "fouls_per_match":              round(agg["fouls"]                 / m, 3),
            "early_sub_rate":               round(agg["early_sub_matches"]     / m, 3),
            # Defensive per match (what opponent produced against this team)
            "sot_conceded_per_match":       round(agg["sot_conceded"]          / m, 3),
            "shots_conceded_per_match":     round(agg["shots_conceded"]        / m, 3),
            "corners_conceded_per_match":   round(agg["corners_conceded"]      / m, 3),
            "source": "StatsBomb open data (WC 2018/2022, Euro 2020/2024, Copa 2024, AFCON 2023)",
        }
    return history


def main() -> None:
    history = build()
    TEAM_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEAM_HISTORY_FILE.write_text(
        json.dumps(dict(sorted(history.items())), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved {len(history)} teams to {TEAM_HISTORY_FILE}")


if __name__ == "__main__":
    main()
