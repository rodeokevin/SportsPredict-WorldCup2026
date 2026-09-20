#!/usr/bin/env python3
"""
Build data/player_history.json from StatsBomb open data.

Aggregates per-player international match statistics across:
    - FIFA World Cup 2018 & 2022
    - UEFA Euro 2020 & 2024
    - Copa America 2024
    - Africa Cup of Nations 2023

Per-player stats derived from events:
    - matches          : distinct matches the player appeared in
    - goals            : Shot events with outcome == Goal (excl. own goals)
    - assists          : Passes whose id appears as key_pass_id on a Goal shot
    - shots_on_target  : Shot outcome in {Goal, Saved, Saved To Post}
    - cards            : Yellow / Second Yellow / Red Card events
    - source           : "StatsBomb open data (...)"
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests

RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
PLAYER_HISTORY_FILE = Path(__file__).parent.parent / "data" / "player_history.json"

COMPETITIONS: list[tuple[int, int, str]] = [
    # International tournaments (primary source)
    (43,   3,   "FIFA World Cup 2018"),
    (43,   106, "FIFA World Cup 2022"),
    (55,   43,  "UEFA Euro 2020"),
    (55,   282, "UEFA Euro 2024"),
    (223,  282, "Copa America 2024"),
    (1267, 107, "Africa Cup of Nations 2023"),
    # Club leagues (supplementary — widens player coverage)
    (11,   90,  "La Liga 2020/2021"),
    (11,   42,  "La Liga 2019/2020"),
    (11,   1,   "La Liga 2017/2018"),
    (7,    235, "Ligue 1 2022/2023"),
    (7,    108, "Ligue 1 2021/2022"),
    (9,    281, "Bundesliga 2023/2024"),
    (9,    27,  "Bundesliga 2015/2016"),
]

ON_TARGET      = {"Goal", "Saved", "Saved To Post"}
CARD_NAMES     = {"Yellow Card", "Second Yellow", "Red Card"}

_session = requests.Session()
_session.headers.update({"User-Agent": "SportsPredict-player-stats-builder/1.0"})


def _get(url: str) -> Any:
    resp = _session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _blank_player() -> dict[str, Any]:
    return {
        "team": "",
        "matches": 0,
        "goals": 0,
        "assists": 0,
        "shots_on_target": 0,
        "cards": 0,
        "_match_ids": set(),  # deduplicate appearances
    }


def process_match(
    match_id: int,
    home_team: str,
    away_team: str,
    totals: dict[str, dict[str, Any]],
) -> None:
    events = _get(f"{RAW}/events/{match_id}.json")

    # Build id -> event lookup for assist tracing.
    ev_by_id: dict[str, dict] = {e["id"]: e for e in events}

    for e in events:
        # Skip penalty shootout.
        if e.get("period") == 5:
            continue

        etype  = (e.get("type") or {}).get("name")
        player = e.get("player") or {}
        pname  = player.get("name")
        team   = (e.get("team") or {}).get("name", "")

        if not pname or not etype:
            continue

        agg = totals.setdefault(pname, _blank_player())
        # Track team (may appear for multiple national teams across tournaments —
        # keep the most recent).
        agg["team"] = team
        # Record appearance in this match (set deduplicates).
        agg["_match_ids"].add(match_id)

        if etype == "Shot":
            shot_info = e.get("shot") or {}
            outcome   = (shot_info.get("outcome") or {}).get("name", "")
            # Skip own goals.
            if outcome == "Own Goal For":
                continue
            if outcome in ON_TARGET:
                agg["shots_on_target"] += 1
            if outcome == "Goal":
                agg["goals"] += 1
                # Credit the assist to the key-passer.
                kp_id = shot_info.get("key_pass_id")
                if kp_id and kp_id in ev_by_id:
                    kp_event  = ev_by_id[kp_id]
                    kp_player = (kp_event.get("player") or {}).get("name")
                    if kp_player and kp_player != pname:
                        kp_agg = totals.setdefault(kp_player, _blank_player())
                        kp_agg["team"] = (kp_event.get("team") or {}).get("name", "")
                        kp_agg["_match_ids"].add(match_id)
                        kp_agg["assists"] += 1

        elif etype == "Foul Committed":
            card = ((e.get("foul_committed") or {}).get("card") or {}).get("name", "")
            if card in CARD_NAMES:
                agg["cards"] += 1

        elif etype == "Bad Behaviour":
            card = ((e.get("bad_behaviour") or {}).get("card") or {}).get("name", "")
            if card in CARD_NAMES:
                agg["cards"] += 1


def build() -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}

    for comp_id, season_id, label in COMPETITIONS:
        print(f"\n=== {label} ===")
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
                process_match(mid, home, away, totals)
                print(f"  [{i}/{len(matches)}] {home} vs {away}")
            except Exception as exc:
                print(f"  [{i}/{len(matches)}] {home} vs {away} — skipped ({exc})")

    # Convert to final format — replace _match_ids set with match count.
    history: dict[str, dict[str, Any]] = {}
    for player, agg in totals.items():
        m = len(agg["_match_ids"])
        if m == 0:
            continue
        history[player] = {
            "team":             agg["team"],
            "matches":          m,
            "goals":            agg["goals"],
            "assists":          agg["assists"],
            "shots_on_target":  agg["shots_on_target"],
            "cards":            agg["cards"],
            "source": "StatsBomb open data (WC 2018/2022, Euro 2020/2024, Copa 2024, AFCON 2023)",
        }

    return history


def main() -> None:
    history = build()
    PLAYER_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAYER_HISTORY_FILE.write_text(
        json.dumps(dict(sorted(history.items())), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved {len(history)} players to {PLAYER_HISTORY_FILE}")


if __name__ == "__main__":
    main()
