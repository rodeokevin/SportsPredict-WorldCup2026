"""Calculate player prop probabilities from historical performance data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Historical player statistics (can be updated from external data sources)
# Format: { "player_name": {"team": "country", "goals": 5, "matches": 10, "assists": 2, "shots_on_target": 15, "cards": 1} }
PLAYER_HISTORY_FILE = Path(__file__).parent.parent / "data" / "player_history.json"


def load_player_history() -> dict[str, dict[str, Any]]:
    """Load historical player performance data."""
    if PLAYER_HISTORY_FILE.exists():
        return json.loads(PLAYER_HISTORY_FILE.read_text(encoding="utf-8"))
    return {}


def get_player_stat(player_name: str, stat: str) -> dict[str, Any]:
    """Get aggregated stat for a player using progressive fuzzy matching."""
    import unicodedata

    def _norm(s: str) -> str:
        """Lowercase, strip accents, collapse whitespace."""
        nfkd = unicodedata.normalize("NFKD", s)
        ascii_s = "".join(c for c in nfkd if not unicodedata.combining(c))
        return " ".join(ascii_s.lower().split())

    history = load_player_history()
    query = _norm(player_name)
    query_words = query.split()

    # Build a normalised key cache for efficiency
    norm_cache = {k: _norm(k) for k in history}

    # 1. Exact normalised match
    for k, nk in norm_cache.items():
        if nk == query:
            return history[k]

    # 2. Every word in query appears in the stored name
    for k, nk in norm_cache.items():
        if all(w in nk for w in query_words):
            return history[k]

    # 3. Every word in stored name appears in query (handles short stored names)
    for k, nk in norm_cache.items():
        key_words = nk.split()
        if key_words and all(w in query for w in key_words):
            return history[k]

    # 4. Last-name match (last word of query vs last word of stored name)
    if query_words:
        query_last = query_words[-1]
        for k, nk in norm_cache.items():
            nk_words = nk.split()
            if len(nk_words) >= 2 and nk_words[-1] == query_last:
                return history[k]

    # Not found — return neutral defaults signalling "unknown player"
    return {
        "goals": 0,
        "matches": 0,
        "assists": 0,
        "shots_on_target": 0,
        "cards": 0,
        "team": "unknown",
    }


def estimate_player_goal_probability(player_name: str, team: str) -> float:
    """P(player scores >= 1 goal) using Poisson on historical goals/match rate."""
    import math
    player_data = get_player_stat(player_name, "goals")
    matches = player_data.get("matches", 0)
    if matches == 0:
        lam = 0.08  # unknown player fallback: ~0.08 goals/match (squad average)
    else:
        lam = player_data.get("goals", 0) / matches
    prob = 1.0 - math.exp(-lam)
    return round(max(min(prob, 0.99), 0.01), 3)


def estimate_player_assist_probability(player_name: str, team: str) -> float:
    """P(player gets >= 1 assist) using Poisson on historical assists/match rate."""
    import math
    player_data = get_player_stat(player_name, "assists")
    matches = player_data.get("matches", 0)
    if matches == 0:
        lam = 0.05  # unknown player fallback
    else:
        lam = player_data.get("assists", 0) / matches
    prob = 1.0 - math.exp(-lam)
    return round(max(min(prob, 0.99), 0.01), 3)


def estimate_player_assists_threshold_probability(
    player_name: str, team: str, threshold: float
) -> float:
    """P(player gets >= threshold assists) using Poisson on historical assists/match."""
    import math
    player_data = get_player_stat(player_name, "assists")
    matches = player_data.get("matches", 0)
    if matches == 0:
        lam = 0.05
    else:
        lam = player_data.get("assists", 0) / matches
    n = int(math.ceil(threshold))
    cdf = sum(math.exp(-lam) * (lam ** k) / math.factorial(k) for k in range(n))
    return round(max(min(1.0 - cdf, 0.99), 0.01), 3)


def estimate_player_shots_on_target_probability(
    player_name: str, team: str, threshold: float,
) -> float:
    """
    P(player has >= threshold SOT) using Poisson on historical SOT/match rate.

    Blends international career data (primary) with club-level estimates (secondary)
    when international sample is small (< 15 matches).

    Club stats are discounted by 0.75 relative to international level — international
    football is more physical and defensive, so players generate ~25% fewer SOT than
    at club level.

    International weight = min(matches / 15, 1.0) so it ramps from pure club prior
    at 0 international matches to pure international at 15+ matches.
    """
    import math
    player_data = get_player_stat(player_name, "shots_on_target")
    intl_matches = player_data.get("matches", 0)
    intl_sot = player_data.get("shots_on_target", 0)

    if intl_matches == 0:
        intl_lam = 0.0
    else:
        intl_lam = intl_sot / intl_matches

    # Club SOT prior: look up in CLUB_SOT_PRIOR (known values for current top players)
    club_lam_raw = CLUB_SOT_PRIOR.get(_norm_name(player_name))
    if club_lam_raw is not None:
        club_lam = club_lam_raw * 0.75  # discount: club → international
    else:
        club_lam = None

    if intl_matches >= 15 or club_lam is None:
        # Sufficient international data — use it directly
        lam = intl_lam if intl_matches > 0 else 0.5
    else:
        # Blend: international weight ramps up with sample size
        w_intl = intl_matches / 15.0
        w_club = 1.0 - w_intl
        lam = w_intl * intl_lam + w_club * club_lam

    n = int(math.ceil(threshold))
    cdf = sum(math.exp(-lam) * (lam ** k) / math.factorial(k) for k in range(n))
    return round(max(min(1.0 - cdf, 0.99), 0.01), 3)


def _norm_name(s: str) -> str:
    """Normalize player name for CLUB_SOT_PRIOR lookup."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


# Club-level SOT/game estimates for players likely to appear in international matches.
# These are raw club rates — the function applies a 0.75 discount before blending.
# Sources: 24/25 season league stats (approximate).
CLUB_SOT_PRIOR: dict[str, float] = {
    # England
    "jude bellingham":      2.0,   # Real Madrid La Liga
    "bukayo saka":          1.8,   # Arsenal PL
    "harry kane":           2.6,   # Bayern Bundesliga
    "phil foden":           2.0,   # Man City PL
    "cole palmer":          2.2,   # Chelsea PL
    "ollie watkins":        2.0,   # Aston Villa PL
    "marcus rashford":      1.6,   # Man Utd PL
    "declan rice":          0.8,   # Arsenal PL (DM)
    # Norway
    "erling haaland":       3.5,   # Man City PL
    "martin odegaard":      1.5,   # Arsenal PL
    "alexander sorloth":    1.8,   # Atletico La Liga
    # Argentina
    "lionel messi":         2.4,   # Inter Miami / Barcelona era
    "julian alvarez":       1.8,   # Atletico La Liga
    "lautaro martinez":     2.2,   # Inter Serie A
    # Spain
    "lamine yamal":         2.4,   # Barcelona La Liga
    "pedri":                1.4,   # Barcelona La Liga
    "alvaro morata":        1.6,   # AC Milan Serie A
    "dani olmo":            1.8,   # Barcelona La Liga
    # France
    "kylian mbappe":        2.8,   # Real Madrid / PSG
    "ousmane dembele":      1.8,   # PSG Ligue 1
    "antoine griezmann":    1.5,   # Atletico La Liga
    # Portugal
    "cristiano ronaldo":    2.2,   # Al Nassr (top scorer)
    "bruno fernandes":      1.8,   # Man Utd PL
    "diogo jota":           2.0,   # Liverpool PL
    # Belgium
    "romelu lukaku":        2.0,   # Roma / various clubs
    "kevin de bruyne":      1.4,   # Man City PL
    "leandro trossard":     1.4,   # Arsenal PL
    # Switzerland
    "breel embolo":         1.4,   # Monaco Ligue 1
    "ruben vargas":         1.6,   # Augsburg Bundesliga
    # Morocco
    "achraf hakimi":        1.2,   # PSG (wing-back)
    "hakim ziyech":         1.8,   # Galatasaray
    "brahim diaz":          1.6,   # Real Madrid / AC Milan
    # Colombia
    "luis diaz":            2.0,   # Liverpool PL
    "james rodriguez":      1.4,   # Rayo Vallecano
    # Egypt
    "mohamed salah":        2.8,   # Liverpool PL
    "omar marmoush":        2.2,   # Man City PL
}


def estimate_player_goal_or_assist_probability(player_name: str, team: str) -> float:
    """P(player scores OR assists >= 1)."""
    g = estimate_player_goal_probability(player_name, team)
    a = estimate_player_assist_probability(player_name, team)
    return round(max(min(g + a - g * a, 0.99), 0.01), 3)


def estimate_player_card_probability(player_name: str, team: str) -> float:
    """P(player receives any card) using Poisson on historical cards/match."""
    import math
    player_data = get_player_stat(player_name, "cards")
    matches = player_data.get("matches", 0)
    if matches == 0:
        lam = 0.12  # unknown player fallback (~squad average)
    else:
        lam = player_data.get("cards", 0) / matches
    prob = 1.0 - math.exp(-lam)
    return round(max(min(prob, 0.99), 0.01), 3)


def initialize_player_history_template():
    """Create a template player_history.json file for manual population."""
    template = {
        "Cristiano Ronaldo": {
            "team": "Portugal",
            "goals": 15,
            "matches": 20,
            "assists": 5,
            "shots_on_target": 35,
            "cards": 2
        },
        "Kylian Mbappé": {
            "team": "France",
            "goals": 12,
            "matches": 15,
            "assists": 4,
            "shots_on_target": 28,
            "cards": 1
        },
    }
    
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    history_file = data_dir / "player_history.json"
    if not history_file.exists():
        history_file.write_text(json.dumps(template, indent=2))
        print(f"Created template: {history_file}")
    
    return history_file


if __name__ == "__main__":
    initialize_player_history_template()
    print("Player stats module ready")


def estimate_any_player_brace_probability(
    team_a: str, team_b: str, n: int = 2,
    lam_a: float | None = None, lam_b: float | None = None,
) -> float:
    """
    P(any tracked player scores >= n goals) using independent Poisson per player.

    For each tracked player on either team, compute P(player scores >= n) then
    combine as P(at least one does) = 1 - product(1 - P_i).

    Fallback when no tracked players are found: uses the fixture's expected
    goals (lam_a / lam_b) split across ~4 attackers per team using a realistic
    goals-concentration distribution (top scorer gets ~30% of team goals,
    second scorer ~20%, etc.). Falls back to a league-average estimate if
    no fixture lambda is provided either.
    """
    import math
    from teams import normalize_team

    history = load_player_history()
    norm_a = normalize_team(team_a)
    norm_b = normalize_team(team_b)

    team_players = [
        data for _, data in history.items()
        if normalize_team(data.get("team", "")) in (norm_a, norm_b)
    ]

    if not team_players:
        # Fixture-specific fallback: distribute team expected goals among attackers
        # using typical WC top-scorer concentration fractions.
        ATTACKER_FRACS = [0.30, 0.20, 0.14, 0.10]  # top 4 attackers per team

        if lam_a is None:
            lam_a = 1.4  # league-average team expected goals
        if lam_b is None:
            lam_b = 1.4

        p_none = 1.0
        for team_lam in (lam_a, lam_b):
            for frac in ATTACKER_FRACS:
                player_lam = team_lam * frac
                cdf = sum(
                    math.exp(-player_lam) * (player_lam ** k) / math.factorial(k)
                    for k in range(n)
                )
                p_at_least_n = 1.0 - cdf
                p_none *= (1.0 - p_at_least_n)
        return round(max(1.0 - p_none, 0.01), 3)

    p_none = 1.0
    for data in team_players:
        matches = max(data.get("matches", 1), 1)
        goals = data.get("goals", 0)
        lam = goals / matches
        cdf = sum(
            math.exp(-lam) * (lam ** k) / math.factorial(k)
            for k in range(n)
        )
        p_at_least_n = 1.0 - cdf
        p_none *= (1.0 - p_at_least_n)

    return round(max(1.0 - p_none, 0.01), 3)
