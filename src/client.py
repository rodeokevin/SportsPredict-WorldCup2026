"""SportsPredict Probability Cup API client."""

from __future__ import annotations

from typing import Any

import requests

API_BASE = "https://api.sportspredict.com/api/v1"


class SportsPredictClient:
    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _get(self, path: str, **params: Any) -> Any:
        resp = self.session.get(f"{API_BASE}{path}", params=params or None, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: Any = None) -> Any:
        resp = self.session.post(f"{API_BASE}{path}", json=json, timeout=30)
        if resp.status_code == 409:
            return {"status": 409, "body": resp.json()}
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, json: Any) -> Any:
        resp = self.session.patch(f"{API_BASE}{path}", json=json, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_probability_cup_event(self) -> dict[str, Any]:
        events = self._get("/events")
        for event in events:
            # Check type field (may be "probability" or UUID depending on API version/sandbox)
            # Also check for "Probability Cup" in title as fallback
            if event.get("type") == "probability" or "Probability" in event.get("title", ""):
                return event
        raise RuntimeError("No probability event found. Is Probability Cup active?")

    def get_lobby(self, event_id: str) -> dict[str, Any]:
        lobbies = self._get("/lobbies", event_id=event_id)
        if not lobbies:
            raise RuntimeError(f"No lobby for event {event_id}")
        return lobbies[0]

    def ensure_joined(self, lobby_id: str) -> None:
        result = self._post(f"/lobbies/{lobby_id}/join")
        if isinstance(result, dict) and result.get("status") == 409:
            return

    def list_matches(self, event_id: str, lobby_id: str) -> list[dict[str, Any]]:
        return self._get("/matches", event_id=event_id, lobby_id=lobby_id)

    def list_markets(self, lobby_id: str, match_id: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"lobby_id": lobby_id}
        if match_id:
            params["match_id"] = match_id
        return self._get("/markets", **params)

    def list_predictions(self, lobby_id: str) -> list[dict[str, Any]]:
        return self._get("/predictions", lobby_id=lobby_id)

    def submit_predictions_batch(self, predictions: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post("/predictions/batch", json={"predictions": predictions})

    def update_prediction(self, prediction_id: str, probability: int) -> dict[str, Any]:
        return self._patch(f"/predictions/{prediction_id}", json={"probability": probability})

    def fetch_all_open_markets(self, event_id: str, lobby_id: str) -> list[dict[str, Any]]:
        matches = self.list_matches(event_id, lobby_id)
        markets: list[dict[str, Any]] = []
        for match in matches:
            if match.get("open_market_count", 0) == 0:
                continue
            markets.extend(self.list_markets(lobby_id, match["id"]))
        return markets

    def fetch_all_markets(self, event_id: str, lobby_id: str) -> list[dict[str, Any]]:
        """Fetch ALL markets (open and closed) for every match in the event."""
        matches = self.list_matches(event_id, lobby_id)
        markets: list[dict[str, Any]] = []
        for match in matches:
            markets.extend(self.list_markets(lobby_id, match["id"]))
        return markets
