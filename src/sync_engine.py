"""Core sync logic: map external odds → SportsPredict predictions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client import SportsPredictClient
from matcher import MarketKind, parse_market_question, probability_for_market
from odds import to_sp_probability
from sources import OddsSource, find_match_odds


# Market kinds whose probability comes directly from Polymarket / bookmaker odds
# (not from the statistical model).
_ODDS_SOURCED = {
    MarketKind.TEAM_WIN_REGULATION,
    MarketKind.BOTH_TEAMS_SCORE,
    MarketKind.DRAW_REGULATION,
    MarketKind.OVER_GOALS,
    MarketKind.UNDER_GOALS,
    MarketKind.TEAM_SCORE,
    MarketKind.TEAM_ADVANCE,
    MarketKind.PENALTY_SHOOTOUT,
    MarketKind.GOAL_EACH_HALF,
}

_POISSON_SOURCED = {
    MarketKind.CLEAN_SHEET,
    MarketKind.SECOND_HALF_MORE_GOALS,
    MarketKind.GOAL_BEFORE_FIRST_HYDRATION,
    MarketKind.GOAL_AFTER_SECOND_HYDRATION,
    MarketKind.AHEAD_AT_HALFTIME,
    MarketKind.TIED_AT_HALFTIME,
    MarketKind.SCORE_BOTH_HALVES,
    MarketKind.HEADER_GOAL,
}

# Market kinds using pure historical team/player stats
_MODEL_SOURCED = {
    MarketKind.TEAM_SHOTS_ON_TARGET,
    MarketKind.TOTAL_SHOTS,
    MarketKind.TEAM_CORNERS,
    MarketKind.BOTH_TEAMS_CORNERS,
    MarketKind.TOTAL_CORNERS,
    MarketKind.MORE_CORNERS_THAN,
    MarketKind.TEAM_CARDS,
    MarketKind.BOTH_TEAMS_CARDS,
    MarketKind.TOTAL_OFFSIDES,
    MarketKind.PENALTY_OR_RED,
    MarketKind.EARLY_SUB,
    MarketKind.PLAYER_BRACE,
    # New markets
    MarketKind.SUB_SCORES,
    MarketKind.SUB_SCORES_OR_ASSISTS,
    MarketKind.TEAM_HOLDS_LEAD,
    MarketKind.PENALTY_AWARDED,
    MarketKind.HALVES_SAME_GOALS,
    MarketKind.FIRST_CARD_BEFORE_GOAL,
    MarketKind.GK_SAVES,
    MarketKind.TOTAL_SUBS,
    MarketKind.PLAYER_PLAYS_FULL,
    MarketKind.CARD_EACH_HALF,
    MarketKind.CARD_IN_STOPPAGE,
    MarketKind.HALFTIME_NIL_NIL,
    MarketKind.HALFTIME_SUB,
    MarketKind.TEAM_MORE_CORNERS_AND_SHOTS,
    MarketKind.VAR_REVIEW,
    MarketKind.FIRST_GOAL_SINGLE_DIGIT,
    MarketKind.TEAM_FIRST_SUB,
    MarketKind.GOAL_IN_STOPPAGE,
    MarketKind.EACH_TEAM_SOT,
    MarketKind.FIRST_GOAL_HAS_ASSIST,
    MarketKind.PENALTY_SCORED,
    MarketKind.PLAYER_MORE_SOT_THAN,
    MarketKind.TEAM_N_DIFFERENT_SHOOTERS,
}

def _detect_source(lookup, match_odds) -> str:
    """Return a human-readable source tag for a prediction."""
    from matcher import MarketKind

    if lookup.kind in _ODDS_SOURCED:
        return "polymarket"

    if lookup.kind in _POISSON_SOURCED:
        # AHEAD_AT_HALFTIME and TIED_AT_HALFTIME may use Polymarket directly
        if lookup.kind in (MarketKind.AHEAD_AT_HALFTIME, MarketKind.TIED_AT_HALFTIME):
            ft = match_odds.first_half_totals if match_odds else None
            ftt = match_odds.first_half_team_totals if match_odds else None
            if lookup.kind == MarketKind.TIED_AT_HALFTIME and ft and "halftime_draw" in ft:
                return "polymarket"
            if lookup.kind == MarketKind.AHEAD_AT_HALFTIME and ftt:
                for lines in ftt.values():
                    if "halftime_lead" in lines:
                        return "polymarket"
        # SECOND_HALF_MORE_GOALS uses Polymarket half O/U lines when available
        if lookup.kind == MarketKind.SECOND_HALF_MORE_GOALS:
            ft1 = match_odds.first_half_totals if match_odds else None
            ft2 = match_odds.second_half_totals if match_odds else None
            if ft1 and 0.5 in ft1 and ft2 and 0.5 in ft2:
                return "polymarket"
        return "poisson(odds)"

    # Penalty shootout and goal-each-half use Polymarket directly
    if lookup.kind == MarketKind.PENALTY_SHOOTOUT:
        return "polymarket" if match_odds and match_odds.penalty_shootout_prob is not None else "poisson(odds)"
    if lookup.kind == MarketKind.EXTRA_TIME:
        return "polymarket" if match_odds and match_odds.extra_time_prob is not None else "model"
    # Odd goals — use exact scores if available, else Poisson
    if lookup.kind == MarketKind.ODD_GOALS:
        has_pm = match_odds and match_odds.exact_score_probs
        return "polymarket" if has_pm else "poisson(odds)"
    # Goal after first hydration break in H1 — Poisson window model
    if lookup.kind == MarketKind.GOAL_AFTER_FIRST_HYDRATION_H1:
        return "poisson(odds)"
    # First goal not by named players — Polymarket first_goal_probs + anytime props
    if lookup.kind == MarketKind.FIRST_GOAL_NOT_NAMED:
        has_pm = match_odds and (match_odds.first_goal_probs or match_odds.player_props)
        return "polymarket" if has_pm else "model"
    # First goal in second half — Polymarket H1/H2 totals
    if lookup.kind == MarketKind.FIRST_GOAL_SECOND_HALF:
        has_pm = (match_odds and match_odds.first_half_totals and 0.5 in match_odds.first_half_totals
                  and match_odds.second_half_totals and 0.5 in match_odds.second_half_totals)
        return "polymarket" if has_pm else "poisson(odds)"
    # Either team wins both halves — Polymarket team half totals
    if lookup.kind == MarketKind.EITHER_TEAM_WINS_BOTH_HALVES:
        has_pm = match_odds and match_odds.first_half_team_totals and match_odds.second_half_team_totals
        return "polymarket" if has_pm else "poisson(odds)"
    # Win by exactly one goal — Polymarket exact scores
    if lookup.kind == MarketKind.WIN_BY_ONE_GOAL:
        has_pm = match_odds and match_odds.exact_score_probs
        return "polymarket" if has_pm else "poisson(odds)"
    # 0-0 at halftime — Polymarket H1 totals
    if lookup.kind == MarketKind.HALFTIME_NIL_NIL:
        has_pm = match_odds and match_odds.first_half_totals and 0.5 in match_odds.first_half_totals
        return "polymarket" if has_pm else "poisson(odds)"
    # Corners AND shots compound — Polymarket corners + model shots
    if lookup.kind == MarketKind.TEAM_MORE_CORNERS_AND_SHOTS:
        has_pm = match_odds and match_odds.player_props
        return "polymarket" if has_pm else "model"
    # Goes to extra time — Polymarket extra_time_prob
    if lookup.kind == MarketKind.GOES_TO_EXTRA_TIME:
        return "polymarket" if match_odds and match_odds.extra_time_prob is not None else "model"
    # Goal between hydration breaks — Poisson window model
    if lookup.kind == MarketKind.GOAL_BETWEEN_HYDRATION_BREAKS:
        return "poisson(odds)"
    if lookup.kind == MarketKind.EXACT_GOALS:
        n = int(lookup.line) if lookup.line else 0
        has_pm = (match_odds and match_odds.exact_score_probs and
                  any(h + a == n for h, a in match_odds.exact_score_probs))
        return "polymarket" if has_pm else "poisson(odds)"
    if lookup.kind == MarketKind.GOAL_EACH_HALF:
        has_pm = (match_odds and match_odds.first_half_totals and
                  0.5 in match_odds.first_half_totals and
                  match_odds.second_half_totals and 0.5 in match_odds.second_half_totals)
        return "polymarket" if has_pm else "poisson(odds)"
    if lookup.kind == MarketKind.MORE_SHOTS_THAN:
        return "model"

    if lookup.kind == MarketKind.MORE_CORNERS_THAN:
        if match_odds and match_odds.player_props:
            import unicodedata
            def _n(s: str) -> str:
                nfkd = unicodedata.normalize("NFKD", s)
                return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
            if lookup.team and lookup.team_b:
                norm_a = _n(lookup.team)
                norm_b = _n(lookup.team_b)
                has_a = any(
                    k[1] == "team_corners_line" and set(norm_a.split()).issubset(set(k[0].split()))
                    for k in match_odds.player_props
                )
                has_b = any(
                    k[1] == "team_corners_line" and set(norm_b.split()).issubset(set(k[0].split()))
                    for k in match_odds.player_props
                )
                if has_a and has_b:
                    return "polymarket"
        return "polymarket*"

    # First goal scorer — Polymarket "First Team to Score" event
    if lookup.kind == MarketKind.FIRST_GOAL_SCORER:
        if match_odds and match_odds.first_goal_probs and lookup.team:
            import unicodedata
            norm = unicodedata.normalize("NFKD", lookup.team)
            norm = "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()
            if norm in match_odds.first_goal_probs:
                return "polymarket"
            for stored in match_odds.first_goal_probs:
                if set(norm.split()).issubset(set(stored.split())):
                    return "polymarket"
        return "polymarket*"

    # Player props — Polymarket Player Props events are the primary source.
    # The Odds API bookmaker props are secondary (require credits).
    if lookup.kind in (
        MarketKind.PLAYER_GOAL,
        MarketKind.PLAYER_GOAL_OR_ASSIST,
        MarketKind.PLAYER_SHOTS_ON_TARGET,
        MarketKind.PLAYER_CARDS,
    ):
        if match_odds and match_odds.player_props and lookup.player:
            key_map = {
                MarketKind.PLAYER_GOAL:            "player_anytime_goalscorer",
                MarketKind.PLAYER_GOAL_OR_ASSIST:  "player_goal_or_assist",
                MarketKind.PLAYER_SHOTS_ON_TARGET: "player_shots_on_target",
                MarketKind.PLAYER_CARDS:           "player_cards",
            }
            key = key_map.get(lookup.kind)
            if key and match_odds.get_player_prop(lookup.player, key, lookup.line) is not None:
                return "polymarket"
        # Market not open yet — Polymarket Player Props events open ~2h before kickoff
        return "polymarket*"

    # Team corner lines — Polymarket Total Corners event
    if lookup.kind in (MarketKind.TEAM_CORNERS, MarketKind.TOTAL_CORNERS, MarketKind.BOTH_TEAMS_CORNERS):
        if match_odds and match_odds.player_props:
            if lookup.team:
                import unicodedata
                norm = unicodedata.normalize("NFKD", lookup.team)
                norm = "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()
                if match_odds.get_player_prop(norm, "team_corners_line", lookup.line) is not None:
                    return "polymarket"
            if match_odds.get_player_prop("", "total_corners_line", lookup.line) is not None:
                return "polymarket"
        # Polymarket Total Corners event opens ~2-4h before kickoff
        return "polymarket*"

    if lookup.kind in _MODEL_SOURCED:
        return "model"

    if lookup.kind == MarketKind.PLAYER_ASSISTS:
        return "model"

    return "model"

PREDICTIONS_DIR = Path(__file__).parent.parent / "data" / "predictions"


@dataclass
class PredictionRecord:
    match:       str
    question:    str
    probability: int    # 1–99 integer submitted to SportsPredict
    market_id:   str
    action:      str    # "submit" | "update" | "dry_run" | "existing"
    source:      str = "model"  # "polymarket" | "bookmaker" | "model" | "mixed"


@dataclass
class SyncResult:
    submitted: int = 0
    updated:   int = 0
    skipped:   int = 0
    failed:    int = 0
    preview:   list[str]             = field(default_factory=list)
    records:   list[PredictionRecord] = field(default_factory=list)
    open_matches: set[str]           = field(default_factory=set)


def save_predictions(result: SyncResult, label: str = "") -> Path:
    """
    Write all prediction records to data/predictions/<timestamp>.json.

    Returns the path of the saved file.
    """
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = f"_{label}" if label else ""
    path = PREDICTIONS_DIR / f"{ts}{slug}.json"

    # Group records by match for readability — only include open matches.
    by_match: dict[str, list[dict[str, Any]]] = {}
    for r in result.records:
        if result.open_matches and r.match not in result.open_matches:
            continue   # skip closed/finished matches
        by_match.setdefault(r.match, []).append({
            "question":    r.question,
            "probability": r.probability,
            "market_id":   r.market_id,
            "action":      r.action,
            "source":      r.source,
            "match":       r.match,   # duplicate for cross-reference lookups
        })

    payload = {
        "saved_at":  datetime.now(timezone.utc).isoformat(),
        "submitted": result.submitted,
        "updated":   result.updated,
        "skipped":   result.skipped,
        "failed":    result.failed,
        "matches":   by_match,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run_sync(
    source: OddsSource,
    client: SportsPredictClient,
    *,
    dry_run: bool = False,
    update: bool = False,
    verbose: bool = False,
) -> SyncResult:
    external_odds = source.fetch_match_odds()

    event = client.get_probability_cup_event()
    lobby = client.get_lobby(event["id"])
    client.ensure_joined(lobby["id"])

    existing = {p["market_id"]: p for p in client.list_predictions(lobby["id"])}

    # Fetch ALL markets (open + closed) to get complete question/match metadata
    all_markets = client.fetch_all_markets(event["id"], lobby["id"])
    all_market_info: dict[str, tuple[str, str]] = {}
    open_matches: set[str] = set()   # match names that have at least one open market
    for m in all_markets:
        match_name_m = (m.get("match") or {}).get("name", "")
        all_market_info[m["id"]] = (match_name_m, m.get("question", ""))
        if m.get("status") == "open":
            open_matches.add(match_name_m)

    # Also build the open-markets list for the sync loop
    markets = [m for m in all_markets if m.get("status") == "open"]

    result = SyncResult(open_matches=open_matches)

    # Seed result.records with every prediction already on SportsPredict,
    # using all_market_info for question/match text (works for closed markets too).
    # Fall back to the previous predictions file for anything not in all_market_info.
    seeded_ids: set[str] = set()
    prev_by_market_id: dict[str, dict] = {}
    pred_files = sorted(PREDICTIONS_DIR.glob("*.json"))
    submitted_files = [f for f in pred_files if "submitted" in f.name]
    for ref_file in submitted_files:
        try:
            prev_data = json.loads(ref_file.read_text(encoding="utf-8"))
            for match_name_prev, preds in prev_data.get("matches", {}).items():
                for p in preds:
                    entry = dict(p)
                    entry["match"] = match_name_prev
                    prev_by_market_id[p["market_id"]] = entry
        except Exception:
            pass

    for pred in existing.values():
        mid = pred["market_id"]
        if mid in all_market_info:
            mkt_match, mkt_question = all_market_info[mid]
        elif mid in prev_by_market_id:
            mkt_match  = prev_by_market_id[mid].get("match", "")
            mkt_question = prev_by_market_id[mid].get("question", "")
        else:
            mkt_match = mkt_question = ""
        result.records.append(PredictionRecord(
            match=mkt_match,
            question=mkt_question,
            probability=pred["probability"],
            market_id=mid,
            action="existing",
            source=prev_by_market_id.get(mid, {}).get("source", "existing"),
        ))
        seeded_ids.add(mid)

    to_submit: list[dict] = []
    to_update: list[tuple[str, int, str, str]] = []  # (pred_id, prob, question, market_id)

    for market in markets:
        if market.get("status") != "open":
            continue

        match_info = market.get("match") or {}
        match_name = match_info.get("name", "")
        question   = market.get("question", "")
        market_id  = market["id"]

        lookup = parse_market_question(question, match_name)
        if not lookup:
            result.skipped += 1
            if verbose:
                result.preview.append(f"[unsupported] {match_name}: {question}")
            continue

        match_odds = find_match_odds(external_odds, match_name)
        if not match_odds:
            result.skipped += 1
            if verbose:
                result.preview.append(f"[no fixture] {match_name}: {question}")
            continue

        prob = probability_for_market(lookup, match_odds, match_name)
        if prob is None:
            result.skipped += 1
            if verbose:
                result.preview.append(f"[no odds] {match_name}: {question}")
            continue

        sp_prob = to_sp_probability(prob)
        src_tag = _detect_source(lookup, match_odds)
        line = f"{match_name} | {question} -> {sp_prob}%"

        if market_id in existing:
            if update and existing[market_id]["probability"] != sp_prob:
                to_update.append((existing[market_id]["id"], sp_prob, question, market_id))
                result.preview.append(f"UPDATE {line}")
                # Replace the seeded record with updated info
                result.records = [r for r in result.records if r.market_id != market_id]
                result.records.append(PredictionRecord(
                    match=match_name, question=question,
                    probability=sp_prob, market_id=market_id, action="update",
                    source=src_tag,
                ))
            else:
                # Replace seeded record with full question/match info
                result.records = [r for r in result.records if r.market_id != market_id]
                result.records.append(PredictionRecord(
                    match=match_name, question=question,
                    probability=existing[market_id]["probability"],
                    market_id=market_id, action="existing",
                    source=src_tag,
                ))
            continue

        to_submit.append({
            "market_id": market_id,
            "lobby_id":  lobby["id"],
            "probability": sp_prob,
        })
        result.preview.append(line)
        result.records.append(PredictionRecord(
            match=match_name, question=question,
            probability=sp_prob, market_id=market_id,
            action="dry_run" if dry_run else "submit",
            source=src_tag,
        ))

    if dry_run:
        result.submitted = len(to_submit)
        result.updated   = len(to_update)
        # Add missing market placeholders AFTER all dry_run records are recorded
        submitted_market_ids = {r.market_id for r in result.records}
        for m in markets:
            mid = m["id"]
            if mid not in submitted_market_ids:
                result.records.append(PredictionRecord(
                    match=(m.get("match") or {}).get("name", ""),
                    question=m.get("question", ""),
                    probability=0,
                    market_id=mid,
                    action="unsubmitted",
                    source="",
                ))
        return result

    for i in range(0, len(to_submit), 50):
        chunk = to_submit[i : i + 50]
        batch = client.submit_predictions_batch(chunk)
        result.submitted += batch["succeeded"]
        result.failed    += batch["failed"]

    for pred_id, prob, _question, mid in to_update:
        client.update_prediction(pred_id, prob)
        result.updated += 1

    # Add missing market placeholders for any open markets still unsubmitted
    submitted_market_ids = {r.market_id for r in result.records}
    for m in markets:
        mid = m["id"]
        if mid not in submitted_market_ids:
            result.records.append(PredictionRecord(
                match=(m.get("match") or {}).get("name", ""),
                question=m.get("question", ""),
                probability=0,
                market_id=mid,
                action="unsubmitted",
                source="",
            ))

    return result
