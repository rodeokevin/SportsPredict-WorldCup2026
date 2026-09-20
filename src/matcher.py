"""Map SportsPredict market questions to external odds lookups."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from teams import normalize_team, parse_match_name, teams_match


class MarketKind(str, Enum):
    TEAM_WIN_REGULATION = "team_win_regulation"
    BOTH_TEAMS_SCORE = "both_teams_score"
    OVER_GOALS = "over_goals"
    UNDER_GOALS = "under_goals"
    DRAW_REGULATION = "draw_regulation"
    TEAM_SCORE = "team_score"
    PLAYER_GOAL = "player_goal"
    PLAYER_BRACE = "player_brace"
    PLAYER_ASSISTS = "player_assists"
    PLAYER_SHOTS_ON_TARGET = "player_shots_on_target"
    PLAYER_GOAL_OR_ASSIST = "player_goal_or_assist"
    PLAYER_CARDS = "player_cards"
    TEAM_CORNERS = "team_corners"
    TEAM_SHOTS_ON_TARGET = "team_shots_on_target"
    BOTH_TEAMS_CORNERS = "both_teams_corners"
    TOTAL_CORNERS = "total_corners"
    MORE_CORNERS_THAN = "more_corners_than"
    TEAM_CARDS = "team_cards"
    BOTH_TEAMS_CARDS = "both_teams_cards"
    GOAL_BEFORE_FIRST_HYDRATION = "goal_before_first_hydration"
    GOAL_AFTER_SECOND_HYDRATION = "goal_after_second_hydration"
    AHEAD_AT_HALFTIME = "ahead_at_halftime"
    TIED_AT_HALFTIME = "tied_at_halftime"
    CLEAN_SHEET = "clean_sheet"
    SECOND_HALF_MORE_GOALS = "second_half_more_goals"
    TOTAL_OFFSIDES = "total_offsides"
    TOTAL_SHOTS = "total_shots"
    HEADER_GOAL = "header_goal"
    PENALTY_OR_RED = "penalty_or_red"
    EARLY_SUB = "early_sub"
    MANUAL = "manual"
    FIRST_GOAL_SCORER = "first_goal_scorer"
    SCORE_BOTH_HALVES = "score_both_halves"
    TEAM_ADVANCE = "team_advance"
    PENALTY_SHOOTOUT = "penalty_shootout"
    GOAL_EACH_HALF = "goal_each_half"
    MORE_SHOTS_THAN = "more_shots_than"
    EXACT_GOALS = "exact_goals"
    MORE_CARDS_THAN_GOALS = "more_cards_than_goals"
    SUB_SCORES = "sub_scores"
    TEAM_HOLDS_LEAD = "team_holds_lead"
    PENALTY_AWARDED = "penalty_awarded"
    HALVES_SAME_GOALS = "halves_same_goals"
    FIRST_CARD_BEFORE_GOAL = "first_card_before_goal"
    GK_SAVES = "gk_saves"
    TOTAL_SUBS = "total_subs"
    EXTRA_TIME = "extra_time"
    PLAYER_PLAYS_FULL = "player_plays_full"
    ODD_GOALS = "odd_goals"
    GOAL_AFTER_FIRST_HYDRATION_H1 = "goal_after_first_hydration_h1"
    FIRST_GOAL_NOT_NAMED = "first_goal_not_named"
    SUB_SCORES_OR_ASSISTS = "sub_scores_or_assists"
    FIRST_GOAL_SECOND_HALF = "first_goal_second_half"
    EITHER_TEAM_WINS_BOTH_HALVES = "either_team_wins_both_halves"
    WIN_BY_ONE_GOAL = "win_by_one_goal"
    CARD_EACH_HALF = "card_each_half"
    CARD_IN_STOPPAGE = "card_in_stoppage"
    HALFTIME_NIL_NIL = "halftime_nil_nil"
    HALFTIME_SUB = "halftime_sub"
    TEAM_MORE_CORNERS_AND_SHOTS = "team_more_corners_and_shots"
    VAR_REVIEW = "var_review"
    GOES_TO_EXTRA_TIME = "goes_to_extra_time"
    FIRST_GOAL_SINGLE_DIGIT = "first_goal_single_digit"
    GOAL_BETWEEN_HYDRATION_BREAKS = "goal_between_hydration_breaks"
    TEAM_FIRST_SUB = "team_first_sub"
    GOAL_IN_STOPPAGE = "goal_in_stoppage"
    EACH_TEAM_SOT = "each_team_sot"
    FIRST_GOAL_HAS_ASSIST = "first_goal_has_assist"
    PENALTY_SCORED = "penalty_scored"
    PLAYER_MORE_SOT_THAN = "player_more_sot_than"
    TEAM_N_DIFFERENT_SHOOTERS = "team_n_different_shooters"


@dataclass(frozen=True)
class MarketLookup:
    kind: MarketKind
    team: str | None = None
    player: str | None = None  # e.g. "Cristiano Ronaldo"
    line: float | None = None  # e.g. 2.5 for over/under, 1 for anytime goal
    team_b: str | None = None  # second team, for comparison markets
    players: tuple[str, ...] = ()  # list of named players (for exclusion markets)


# Suffix that appears on many SportsPredict questions — strip it before matching
_REGULATION_SUFFIX = re.compile(
    r"\s+in\s+regulation\s*(?:\([^)]*\))?\s*$",
    re.IGNORECASE,
)


def _strip_suffix(q: str) -> str:
    """Remove trailing '...in regulation (90 minutes + stoppage time)' if present."""
    return _REGULATION_SUFFIX.sub("", q.strip())


WIN_REGULATION = re.compile(
    r"will\s+(.+?)\s+win\s+(?:the\s+match\s+)?(?:in\s+regulation)?",
    re.IGNORECASE,
)
BTTS = re.compile(
    r"will\s+both\s+teams\s+score",
    re.IGNORECASE,
)
OVER_GOALS = re.compile(
    r"will\s+(?:there\s+be|the\s+match\s+have)\s+(?:over\s+)?(\d+(?:\.\d+)?)\s+or\s+more\s+(?:total\s+)?goals?|"
    r"will\s+there\s+be\s+over\s+(\d+(?:\.\d+)?)\s+goals?",
    re.IGNORECASE,
)
UNDER_GOALS = re.compile(
    r"will\s+(?:there\s+be|the\s+match\s+have)\s+(\d+(?:\.\d+)?)\s+or\s+fewer\s+(?:total\s+)?goals?|"
    r"will\s+there\s+be\s+under\s+(\d+(?:\.\d+)?)\s+goals?",
    re.IGNORECASE,
)
CLEAN_SHEET = re.compile(
    r"will\s+(.+?)\s+keep\s+a\s+clean\s+sheet",
    re.IGNORECASE,
)
SECOND_HALF_MORE = re.compile(
    r"will\s+the\s+second\s+half\s+produce\s+more\s+goals\s+than\s+the\s+first\s+half",
    re.IGNORECASE,
)
DRAW_REGULATION = re.compile(
    r"will\s+(?:the\s+match\s+)?end\s+in\s+a\s+draw|"
    r"will\s+there\s+be\s+a\s+draw",
    re.IGNORECASE,
)
TEAM_SCORE = re.compile(
    r"will\s+(.+?)\s+score\s+(?:at\s+least\s+)?(\d+)\s+(?:or\s+more\s+)?goals?",
    re.IGNORECASE,
)
DEFEAT = re.compile(
    r"will\s+(.+?)\s+defeat\s+",
    re.IGNORECASE,
)
ADVANCE = re.compile(
    r"will\s+(.+?)\s+advance\s+to\s+the\s+(round\s+of\s+\d+|quarterfinals?|semi.?finals?|final)|"
    r"will\s+(.+?)\s+win\s+the\s+(world\s+cup|tournament|third.?place\s+match|bronze\s+final)",
    re.IGNORECASE,
)
PENALTY_SHOOTOUT = re.compile(
    r"will\s+the\s+match\s+be\s+decided\s+by\s+a\s+penalty\s+shootout",
    re.IGNORECASE,
)
GOAL_EACH_HALF = re.compile(
    r"will\s+at\s+least\s+one\s+goal\s+be\s+scored\s+in\s+each\s+half",
    re.IGNORECASE,
)
MORE_SHOTS_THAN = re.compile(
    r"will\s+(.+?)\s+have\s+more\s+shots?\s+on\s+target\s+than\s+(.+?)(?:\s+in\s+regulation.*)?$",
    re.IGNORECASE,
)
EXACT_GOALS = re.compile(
    r"will\s+(?:the\s+match\s+(?:finish|have|be\s+decided\s+by))?\s*(?:with\s+)?exactly\s+(\d+)\s+(?:total\s+)?goals?",
    re.IGNORECASE,
)
MORE_CARDS_THAN_GOALS_RE = re.compile(
    r"will\s+there\s+be\s+more\s+total\s+cards?\s+than\s+total\s+goals?",
    re.IGNORECASE,
)
FIRST_GOAL = re.compile(
    r"will\s+(.+?)\s+score\s+the\s+first\s+goal",
    re.IGNORECASE,
)
AHEAD_HALFTIME = re.compile(
    r"will\s+(.+?)\s+(?:be\s+ahead|lead)\s+at\s+halftime",
    re.IGNORECASE,
)
TIED_HALFTIME = re.compile(
    r"will\s+(?:the\s+match\s+be\s+)?tied\s+at\s+halftime|"
    r"will\s+the\s+match\s+be\s+tied\s+at\s+halftime",
    re.IGNORECASE,
)
SCORE_BOTH_HALVES = re.compile(
    r"will\s+(.+?)\s+score\s+in\s+both\s+halves",
    re.IGNORECASE,
)
# Hydration breaks: first ~22.5', second ~67.5' (halfway through each half)
GOAL_BEFORE_FIRST_HYDRATION = re.compile(
    r"will\s+a\s+goal\s+be\s+scored\s+before\s+the\s+first\s+hydration\s+break",
    re.IGNORECASE,
)
GOAL_AFTER_SECOND_HYDRATION = re.compile(
    r"will\s+a\s+goal\s+be\s+scored\s+after\s+the\s+second\s+hydration\s+break",
    re.IGNORECASE,
)

# --- New market patterns ---

# "Will a substitute score a goal"
SUB_SCORES = re.compile(
    r"will\s+a\s+substitute\s+score\s+a\s+goal",
    re.IGNORECASE,
)
# "Will a substitute score or assist a goal"
SUB_SCORES_OR_ASSISTS = re.compile(
    r"will\s+a\s+substitute\s+score\s+or\s+assist",
    re.IGNORECASE,
)
# "Will <Team> hold a lead at any point"
TEAM_HOLDS_LEAD = re.compile(
    r"will\s+(.+?)\s+hold\s+a\s+lead\s+at\s+any\s+point",
    re.IGNORECASE,
)
# "Will a penalty kick be awarded" (no red card clause)
PENALTY_AWARDED = re.compile(
    r"will\s+a\s+penalty\s+kick\s+be\s+awarded",
    re.IGNORECASE,
)
# "Will both halves have the same number of goals"
HALVES_SAME_GOALS = re.compile(
    r"will\s+both\s+halves\s+have\s+the\s+same\s+number\s+of\s+goals",
    re.IGNORECASE,
)
# "Will the first card of the match be shown before the first goal"
# OR "Will a card be shown before the first goal"
FIRST_CARD_BEFORE_GOAL = re.compile(
    r"will\s+(?:the\s+first\s+)?(?:a\s+)?card\s+.*\s+before\s+the\s+first\s+goal",
    re.IGNORECASE,
)
# "Will <Player> (Team) make N or more saves"
GK_SAVES = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+make\s+(\d+)\s+or\s+more\s+saves?",
    re.IGNORECASE,
)
# "Will there be N or more total substitutions"
TOTAL_SUBS = re.compile(
    r"will\s+there\s+be\s+(\d+)\s+or\s+more\s+total\s+substitutions?",
    re.IGNORECASE,
)
# "Will the match go to extra time"
EXTRA_TIME_RE = re.compile(
    r"will\s+the\s+match\s+go\s+to\s+extra\s+time",
    re.IGNORECASE,
)
# "Will <Player> (Team) play the entire match"
PLAYER_PLAYS_FULL = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+play\s+the\s+entire\s+match",
    re.IGNORECASE,
)

# "Will the total number of goals be an odd number"
ODD_GOALS = re.compile(
    r"will\s+the\s+total\s+number\s+of\s+goals\s+.*\s+be\s+an\s+odd\s+number",
    re.IGNORECASE,
)
# "Will a goal be scored in the first half after the first hydration break"
GOAL_AFTER_FIRST_HYDRATION_H1 = re.compile(
    r"will\s+a\s+goal\s+be\s+scored\s+in\s+the\s+first\s+half\s+after\s+the\s+first\s+hydration\s+break",
    re.IGNORECASE,
)
# "Will the first goal be scored by a player other than X and Y"
# Captures the excluded player names from the question text
FIRST_GOAL_NOT_NAMED = re.compile(
    r"will\s+the\s+first\s+goal\s+of\s+the\s+match\s+be\s+scored\s+by\s+a\s+player\s+other\s+than\s+(.+)",
    re.IGNORECASE,
)
# "Will the first goal be scored in the second half"
FIRST_GOAL_SECOND_HALF = re.compile(
    r"will\s+the\s+first\s+goal\s+of\s+the\s+match\s+be\s+scored\s+in\s+the\s+second\s+half",
    re.IGNORECASE,
)
# "Will either team win both halves"
EITHER_TEAM_WINS_BOTH_HALVES = re.compile(
    r"will\s+either\s+team\s+win\s+both\s+halves",
    re.IGNORECASE,
)
# "Will the match be decided by exactly one goal"
WIN_BY_ONE_GOAL = re.compile(
    r"will\s+the\s+match\s+be\s+decided\s+by\s+exactly\s+one\s+goal",
    re.IGNORECASE,
)
# "Will at least one card be shown in each half"
CARD_EACH_HALF = re.compile(
    r"will\s+at\s+least\s+one\s+card\s+be\s+shown\s+in\s+each\s+half",
    re.IGNORECASE,
)
# "Will a card be shown during first- or second-half stoppage time"
CARD_IN_STOPPAGE = re.compile(
    r"will\s+a\s+card\s+be\s+shown\s+during\s+.{0,30}stoppage\s+time",
    re.IGNORECASE,
)
# "Will the match be 0-0 at halftime"
HALFTIME_NIL_NIL = re.compile(
    r"will\s+the\s+match\s+be\s+0.?0\s+at\s+halftime",
    re.IGNORECASE,
)
# "Will either team make a substitution at halftime"
HALFTIME_SUB = re.compile(
    r"will\s+.{0,20}\s+make\s+a\s+substitution\s+at\s+halftime",
    re.IGNORECASE,
)
# "Will <Team> have more corner kicks AND more total shots than <Team>"
TEAM_MORE_CORNERS_AND_SHOTS = re.compile(
    r"will\s+(.+?)\s+have\s+more\s+corner\s+kicks?\s+and\s+more\s+total\s+shots?\s+than\s+(.+?)(?:\s+in\s+regulation.*)?$",
    re.IGNORECASE,
)
# "Will the referee conduct an on-field review at the pitchside VAR monitor"
VAR_REVIEW = re.compile(
    r"will\s+the\s+referee\s+conduct\s+.{0,30}(?:on-field|pitchside|VAR)\s+",
    re.IGNORECASE,
)
# "Will the match be tied at the end of regulation ... go to extra time"
GOES_TO_EXTRA_TIME = re.compile(
    r"will\s+the\s+match\s+be\s+tied\s+at\s+the\s+end\s+of\s+regulation.*go\s+to\s+extra\s+time",
    re.IGNORECASE,
)
# "Will the first goal ... be scored by a player wearing a single-digit shirt number"
FIRST_GOAL_SINGLE_DIGIT = re.compile(
    r"will\s+the\s+first\s+goal\s+.*single.?digit\s+shirt\s+number",
    re.IGNORECASE,
)
# "Will a goal be scored after the first hydration break but before the second"
GOAL_BETWEEN_HYDRATION_BREAKS = re.compile(
    r"will\s+a\s+goal\s+be\s+scored\s+after\s+the\s+first\s+hydration\s+break\s+but\s+before\s+the\s+second",
    re.IGNORECASE,
)
# "Will <Team> make the first substitution of the match"
TEAM_FIRST_SUB = re.compile(
    r"will\s+(.+?)\s+make\s+the\s+first\s+substitution\s+of\s+the\s+match",
    re.IGNORECASE,
)
# "Will a goal be scored during first- or second-half stoppage time"
GOAL_IN_STOPPAGE = re.compile(
    r"will\s+a\s+goal\s+be\s+scored\s+during\s+.{0,30}stoppage\s+time",
    re.IGNORECASE,
)
# "Will each team record N or more shots on target"
EACH_TEAM_SOT = re.compile(
    r"will\s+each\s+team\s+record\s+(\d+)\s+or\s+more\s+shots?\s+on\s+target",
    re.IGNORECASE,
)
# "Will the first goal be credited with an assist"
FIRST_GOAL_HAS_ASSIST = re.compile(
    r"will\s+the\s+first\s+goal\s+.*\s+(?:credited|assisted)\s+with\s+an\s+assist",
    re.IGNORECASE,
)
# "Will a penalty kick be scored"
PENALTY_SCORED = re.compile(
    r"will\s+a\s+penalty\s+kick\s+be\s+scored",
    re.IGNORECASE,
)
# "Will <Player> (Team) record more shots on target than <Player> (Team)"
PLAYER_MORE_SOT_THAN = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+record\s+more\s+shots?\s+on\s+target\s+than\s+(.+?)\s+\(([^)]+)\)",
    re.IGNORECASE,
)
# "Will N or more different <Team> players attempt a shot"
TEAM_N_DIFFERENT_SHOOTERS = re.compile(
    r"will\s+(\d+)\s+or\s+more\s+different\s+(.+?)\s+players?\s+attempt\s+a\s+shot",
    re.IGNORECASE,
)

# Player prop patterns
PLAYER_GOAL = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+score\s+a\s+goal",
    re.IGNORECASE,
)
PLAYER_GOAL_OR_ASSIST = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+score\s+or\s+assist",
    re.IGNORECASE,
)
PLAYER_SHOTS_ON_TARGET = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+have\s+(\d+)\s+or\s+more\s+shots?\s+on\s+target",
    re.IGNORECASE,
)
PLAYER_ASSISTS = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+(?:have\s+)?(\d+)\s+or\s+more\s+assist",
    re.IGNORECASE,
)
PLAYER_CARDS = re.compile(
    r"will\s+(.+?)\s+\(([^)]+)\)\s+(?:receive|get)\s+(?:a\s+)?(yellow|red|any)\s+card",
    re.IGNORECASE,
)

# Team stat patterns
TEAM_SHOTS_ON_TARGET = re.compile(
    r"will\s+(.+?)\s+have\s+(\d+)\s+or\s+more\s+shots?\s+on\s+target",
    re.IGNORECASE,
)
TEAM_CORNERS = re.compile(
    r"will\s+(.+?)\s+have\s+(?:at\s+least\s+)?(\d+)\s+or\s+more\s+corner(?:\s+kicks?)?",
    re.IGNORECASE,
)
BOTH_TEAMS_CORNERS = re.compile(
    r"will\s+both\s+teams\s+(?:combined\s+)?have\s+(?:at\s+least\s+)?(\d+)\s+or\s+more\s+corner(?:\s+kicks?)?",
    re.IGNORECASE,
)
TOTAL_CORNERS = re.compile(
    r"will\s+there\s+be\s+(\d+)\s+or\s+more\s+total\s+corner(?:\s+kicks?)?",
    re.IGNORECASE,
)
MORE_CORNERS_THAN = re.compile(
    r"will\s+(.+?)\s+have\s+more\s+corner(?:\s+kicks?)?\s+than\s+(.+?)(?:\s+in\s+regulation.*)?$",
    re.IGNORECASE,
)
TEAM_CARDS = re.compile(
    r"will\s+(.+?)\s+receive\s+(?:at\s+least\s+)?(\d+)\s+(?:yellow\s+)?cards?",
    re.IGNORECASE,
)
BOTH_TEAMS_CARDS = re.compile(
    r"will\s+both\s+teams\s+receive\s+(?:at\s+least\s+)?(?:one|1|a)\s+card",
    re.IGNORECASE,
)
TOTAL_CARDS = re.compile(
    r"will\s+there\s+be\s+(\d+)\s+or\s+more\s+total\s+cards?",
    re.IGNORECASE,
)
TOTAL_OFFSIDES = re.compile(
    r"will\s+there\s+be\s+(\d+)\s+or\s+more\s+(?:total\s+)?offside",
    re.IGNORECASE,
)
TOTAL_SHOTS = re.compile(
    r"will\s+there\s+be\s+(\d+)\s+or\s+more\s+total\s+shots?",
    re.IGNORECASE,
)
HEADER_GOAL = re.compile(
    r"will\s+a\s+header\s+goal\s+be\s+scored",
    re.IGNORECASE,
)
ANY_PLAYER_BRACE = re.compile(
    r"will\s+any\s+player\s+score\s+(\d+)\s+or\s+more\s+goals?",
    re.IGNORECASE,
)
PENALTY_OR_RED = re.compile(
    r"will\s+a\s+penalty\s+kick\s+be\s+awarded\s+or\s+a\s+red\s+card\s+be\s+shown",
    re.IGNORECASE,
)
EARLY_SUB = re.compile(
    r"will\s+a\s+substitution\s+be\s+made\s+before\s+halftime",
    re.IGNORECASE,
)


def parse_market_question(question: str, match_name: str) -> MarketLookup | None:
    # Strip the trailing "in regulation (90 minutes + stoppage time)" suffix
    # that SportsPredict appends to every question, so all patterns work cleanly.
    q = _strip_suffix(question)

    # Check specific compound patterns before generic "win" to avoid mis-routing
    if EITHER_TEAM_WINS_BOTH_HALVES.search(q):
        return MarketLookup(MarketKind.EITHER_TEAM_WINS_BOTH_HALVES)

    # "advance to the Round of 16 / quarterfinals / etc."
    # OR "win the World Cup / tournament / third-place match"
    # Must come BEFORE WIN_REGULATION since that regex also matches "win the ..."
    if m := ADVANCE.search(q):
        team = (m.group(1) or m.group(3) or "").strip()
        return MarketLookup(MarketKind.TEAM_ADVANCE, team=team)

    if m := WIN_REGULATION.search(q):
        return MarketLookup(MarketKind.TEAM_WIN_REGULATION, team=m.group(1).strip())

    if m := DEFEAT.search(q):
        return MarketLookup(MarketKind.TEAM_WIN_REGULATION, team=m.group(1).strip())

    # Penalty shootout
    if PENALTY_SHOOTOUT.search(q):
        return MarketLookup(MarketKind.PENALTY_SHOOTOUT)

    # Exactly N goals
    if m := EXACT_GOALS.search(q):
        return MarketLookup(MarketKind.EXACT_GOALS, line=float(m.group(1)))

    # More total cards than total goals
    if MORE_CARDS_THAN_GOALS_RE.search(q):
        return MarketLookup(MarketKind.MORE_CARDS_THAN_GOALS)

    # Goal in each half
    if GOAL_EACH_HALF.search(q):
        return MarketLookup(MarketKind.GOAL_EACH_HALF)

    # Team SOT comparison
    if m := MORE_SHOTS_THAN.search(q):
        return MarketLookup(
            MarketKind.MORE_SHOTS_THAN,
            team=m.group(1).strip(),
            team_b=m.group(2).strip(),
        )

    if BTTS.search(q):
        return MarketLookup(MarketKind.BOTH_TEAMS_SCORE)

    if DRAW_REGULATION.search(q):
        return MarketLookup(MarketKind.DRAW_REGULATION)

    # "3 or more total goals" or "over 2.5 goals"
    if m := OVER_GOALS.search(q):
        # Group 1 = "N or more" form, group 2 = "over N" form
        raw = m.group(1) or m.group(2)
        if raw:
            n = float(raw)
            # "3 or more" → over 2.5; "over 2.5" → 2.5
            line = (n - 0.5) if m.group(1) else n
            return MarketLookup(MarketKind.OVER_GOALS, line=line)

    # "2 or fewer total goals" or "under 2.5 goals"
    if m := UNDER_GOALS.search(q):
        raw = m.group(1) or m.group(2)
        if raw:
            n = float(raw)
            # "2 or fewer" → under 2.5 (line 2.5); "under 2.5" → 2.5
            line = (n + 0.5) if m.group(1) else n
            return MarketLookup(MarketKind.UNDER_GOALS, line=line)

    if m := CLEAN_SHEET.search(q):
        return MarketLookup(MarketKind.CLEAN_SHEET, team=m.group(1).strip())

    if SECOND_HALF_MORE.search(q):
        return MarketLookup(MarketKind.SECOND_HALF_MORE_GOALS)

    # Any player scores N or more goals (brace etc.) — must come before TEAM_SCORE
    if m := ANY_PLAYER_BRACE.search(q):
        return MarketLookup(MarketKind.PLAYER_BRACE, line=float(m.group(1)))

    if m := TEAM_SCORE.search(q):
        return MarketLookup(
            MarketKind.TEAM_SCORE,
            team=m.group(1).strip(),
            line=float(m.group(2)) - 0.5,
        )

    # Halftime / first-goal markets
    if m := FIRST_GOAL.search(q):
        return MarketLookup(MarketKind.FIRST_GOAL_SCORER, team=m.group(1).strip())

    if m := AHEAD_HALFTIME.search(q):
        return MarketLookup(MarketKind.AHEAD_AT_HALFTIME, team=m.group(1).strip())

    if TIED_HALFTIME.search(q):
        return MarketLookup(MarketKind.TIED_AT_HALFTIME)

    if m := SCORE_BOTH_HALVES.search(q):
        return MarketLookup(MarketKind.SCORE_BOTH_HALVES, team=m.group(1).strip())

    # Hydration-break goal-timing markets (Poisson time-window model)
    if GOAL_BEFORE_FIRST_HYDRATION.search(q):
        return MarketLookup(MarketKind.GOAL_BEFORE_FIRST_HYDRATION)

    if GOAL_AFTER_SECOND_HYDRATION.search(q):
        return MarketLookup(MarketKind.GOAL_AFTER_SECOND_HYDRATION)

    # Total cards across both teams
    if m := TOTAL_CARDS.search(q):
        return MarketLookup(MarketKind.TEAM_CARDS, line=float(m.group(1)))

    # Both teams each receive at least one card
    if BOTH_TEAMS_CARDS.search(q):
        return MarketLookup(MarketKind.BOTH_TEAMS_CARDS)

    # Total offside calls across both teams
    if m := TOTAL_OFFSIDES.search(q):
        return MarketLookup(MarketKind.TOTAL_OFFSIDES, line=float(m.group(1)))

    # Total shots (on and off target) across both teams
    if m := TOTAL_SHOTS.search(q):
        return MarketLookup(MarketKind.TOTAL_SHOTS, line=float(m.group(1)))

    # Header goal
    if HEADER_GOAL.search(q):
        return MarketLookup(MarketKind.HEADER_GOAL)

    # Penalty awarded OR red card shown
    if PENALTY_OR_RED.search(q):
        return MarketLookup(MarketKind.PENALTY_OR_RED)

    # Substitution before halftime
    if EARLY_SUB.search(q):
        return MarketLookup(MarketKind.EARLY_SUB)

    # Player prop patterns
    if m := PLAYER_GOAL.search(q):
        return MarketLookup(
            MarketKind.PLAYER_GOAL,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
        )

    if m := PLAYER_GOAL_OR_ASSIST.search(q):
        return MarketLookup(
            MarketKind.PLAYER_GOAL_OR_ASSIST,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
        )

    if m := PLAYER_SHOTS_ON_TARGET.search(q):
        return MarketLookup(
            MarketKind.PLAYER_SHOTS_ON_TARGET,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
            line=float(m.group(3)),
        )

    if m := PLAYER_ASSISTS.search(q):
        return MarketLookup(
            MarketKind.PLAYER_ASSISTS,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
            line=float(m.group(3)),
        )

    if m := PLAYER_CARDS.search(q):
        return MarketLookup(
            MarketKind.PLAYER_CARDS,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
        )

    # Team stat patterns
    if m := TEAM_SHOTS_ON_TARGET.search(q):
        return MarketLookup(
            MarketKind.TEAM_SHOTS_ON_TARGET,
            team=m.group(1).strip(),
            line=float(m.group(2)),
        )

    if m := TEAM_MORE_CORNERS_AND_SHOTS.search(q):
        return MarketLookup(
            MarketKind.TEAM_MORE_CORNERS_AND_SHOTS,
            team=m.group(1).strip(),
            team_b=m.group(2).strip(),
        )

    if m := MORE_CORNERS_THAN.search(q):
        return MarketLookup(
            MarketKind.MORE_CORNERS_THAN,
            team=m.group(1).strip(),
            team_b=m.group(2).strip(),
        )

    if m := TOTAL_CORNERS.search(q):
        return MarketLookup(MarketKind.TOTAL_CORNERS, line=float(m.group(1)))

    if m := BOTH_TEAMS_CORNERS.search(q):
        return MarketLookup(
            MarketKind.BOTH_TEAMS_CORNERS,
            line=float(m.group(1)),
        )

    if m := TEAM_CORNERS.search(q):
        return MarketLookup(
            MarketKind.TEAM_CORNERS,
            team=m.group(1).strip(),
            line=float(m.group(2)),
        )

    if m := TEAM_CARDS.search(q):
        return MarketLookup(
            MarketKind.TEAM_CARDS,
            team=m.group(1).strip(),
            line=float(m.group(2)),
        )

    # --- New markets ---

    # "Will a substitute score or assist" — must check before SUB_SCORES (more specific)
    if SUB_SCORES_OR_ASSISTS.search(q):
        return MarketLookup(MarketKind.SUB_SCORES_OR_ASSISTS)

    # "Will a substitute score a goal" — statistical model
    if SUB_SCORES.search(q):
        return MarketLookup(MarketKind.SUB_SCORES)
    # "Will <Team> hold a lead at any point" — derived from first-goal + win/draw
    if m := TEAM_HOLDS_LEAD.search(q):
        return MarketLookup(MarketKind.TEAM_HOLDS_LEAD, team=m.group(1).strip())

    # "Will a penalty kick be awarded" (no red card clause)
    # Must come BEFORE PENALTY_OR_RED so it doesn't absorb the OR-red variant
    if PENALTY_AWARDED.search(q):
        return MarketLookup(MarketKind.PENALTY_AWARDED)

    # "Will both halves have the same number of goals" — derived from H1/H2 distributions
    if HALVES_SAME_GOALS.search(q):
        return MarketLookup(MarketKind.HALVES_SAME_GOALS)

    # "Will the first card be shown before the first goal" — statistical model
    if FIRST_CARD_BEFORE_GOAL.search(q):
        return MarketLookup(MarketKind.FIRST_CARD_BEFORE_GOAL)

    # "Will <Player> (Team) make N or more saves" — model from opponent SOT
    if m := GK_SAVES.search(q):
        return MarketLookup(
            MarketKind.GK_SAVES,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
            line=float(m.group(3)),
        )

    # "Will there be N or more total substitutions" — model
    if m := TOTAL_SUBS.search(q):
        return MarketLookup(MarketKind.TOTAL_SUBS, line=float(m.group(1)))

    # "Will the match go to extra time" — Polymarket extra_time_prob
    if EXTRA_TIME_RE.search(q):
        return MarketLookup(MarketKind.EXTRA_TIME)

    # "Will <Player> (Team) play the entire match" — model (sub-out rate)
    if m := PLAYER_PLAYS_FULL.search(q):
        return MarketLookup(
            MarketKind.PLAYER_PLAYS_FULL,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
        )

    # "Will the first goal be scored in the second half"
    if FIRST_GOAL_SECOND_HALF.search(q):
        return MarketLookup(MarketKind.FIRST_GOAL_SECOND_HALF)

    # "Will either team win both halves"
    if EITHER_TEAM_WINS_BOTH_HALVES.search(q):
        return MarketLookup(MarketKind.EITHER_TEAM_WINS_BOTH_HALVES)

    # "Will the match be decided by exactly one goal"
    if WIN_BY_ONE_GOAL.search(q):
        return MarketLookup(MarketKind.WIN_BY_ONE_GOAL)

    # "Will at least one card be shown in each half"
    if CARD_EACH_HALF.search(q):
        return MarketLookup(MarketKind.CARD_EACH_HALF)

    # "Will a card be shown during stoppage time"
    if CARD_IN_STOPPAGE.search(q):
        return MarketLookup(MarketKind.CARD_IN_STOPPAGE)

    # "Will the match be 0-0 at halftime"
    if HALFTIME_NIL_NIL.search(q):
        return MarketLookup(MarketKind.HALFTIME_NIL_NIL)

    # "Will either team make a substitution at halftime"
    if HALFTIME_SUB.search(q):
        return MarketLookup(MarketKind.HALFTIME_SUB)

    # "Will <Team> have more corners AND more shots than <Team>" — must come before
    # MORE_CORNERS_THAN so the AND variant doesn't fall through to the simpler pattern
    if m := TEAM_MORE_CORNERS_AND_SHOTS.search(q):
        return MarketLookup(
            MarketKind.TEAM_MORE_CORNERS_AND_SHOTS,
            team=m.group(1).strip(),
            team_b=m.group(2).strip(),
        )

    # VAR on-field review
    if VAR_REVIEW.search(q):
        return MarketLookup(MarketKind.VAR_REVIEW)

    # Match goes to extra time (tied at end of regulation)
    if GOES_TO_EXTRA_TIME.search(q):
        return MarketLookup(MarketKind.GOES_TO_EXTRA_TIME)

    # First goal by single-digit shirt number
    if FIRST_GOAL_SINGLE_DIGIT.search(q):
        return MarketLookup(MarketKind.FIRST_GOAL_SINGLE_DIGIT)

    # Goal between hydration breaks [22.5, 67.5]
    if GOAL_BETWEEN_HYDRATION_BREAKS.search(q):
        return MarketLookup(MarketKind.GOAL_BETWEEN_HYDRATION_BREAKS)

    # Goal in stoppage time
    if GOAL_IN_STOPPAGE.search(q):
        return MarketLookup(MarketKind.GOAL_IN_STOPPAGE)

    # Each team N+ SOT
    if m := EACH_TEAM_SOT.search(q):
        return MarketLookup(MarketKind.EACH_TEAM_SOT, line=float(m.group(1)))

    # First goal has assist
    if FIRST_GOAL_HAS_ASSIST.search(q):
        return MarketLookup(MarketKind.FIRST_GOAL_HAS_ASSIST)

    # Penalty scored (not just awarded)
    if PENALTY_SCORED.search(q):
        return MarketLookup(MarketKind.PENALTY_SCORED)

    # Player A more SOT than Player B
    if m := PLAYER_MORE_SOT_THAN.search(q):
        return MarketLookup(
            MarketKind.PLAYER_MORE_SOT_THAN,
            player=m.group(1).strip(),
            team=m.group(2).strip(),
            team_b=m.group(4).strip(),
            players=(m.group(1).strip(), m.group(3).strip()),
        )

    # N+ different team players attempt a shot
    if m := TEAM_N_DIFFERENT_SHOOTERS.search(q):
        return MarketLookup(
            MarketKind.TEAM_N_DIFFERENT_SHOOTERS,
            team=m.group(2).strip(),
            line=float(m.group(1)),
        )

    # Team makes first substitution
    if m := TEAM_FIRST_SUB.search(q):
        return MarketLookup(MarketKind.TEAM_FIRST_SUB, team=m.group(1).strip())

    if ODD_GOALS.search(q):
        return MarketLookup(MarketKind.ODD_GOALS)

    # "Will a goal be scored in the first half after the first hydration break"
    if GOAL_AFTER_FIRST_HYDRATION_H1.search(q):
        return MarketLookup(MarketKind.GOAL_AFTER_FIRST_HYDRATION_H1)

    # "Will the first goal be scored by a player other than X and Y"
    if m := FIRST_GOAL_NOT_NAMED.search(q):
        # Parse out the named players: "Lionel Messi and Mohamed Salah" → two names
        raw = m.group(1).strip().rstrip("?")
        # Split on " and " to get individual names; strip team annotations in parens
        parts = re.split(r"\s+and\s+", raw, flags=re.IGNORECASE)
        # Strip team annotations like "(Argentina, #10)"
        names = tuple(re.sub(r"\s*\([^)]*\)", "", p).strip() for p in parts)
        return MarketLookup(MarketKind.FIRST_GOAL_NOT_NAMED, players=names)

    return None


@dataclass
class MatchOdds:
    """Aggregated odds for one fixture from an external source."""

    home_team: str
    away_team: str
    # Fair probabilities after de-vig
    home_win: float | None = None
    away_win: float | None = None
    draw: float | None = None
    btts_yes: float | None = None
    totals: dict[float, float] | None = None  # line -> P(over)
    team_totals: dict[str, dict[float, float]] | None = None  # team -> line -> P(over)

    # Player prop fair probabilities from bookmakers.
    # Key: (player_name_normalised, market_key, line_or_none)
    # Value: fair P(over/yes) after de-vig
    # e.g. ("lamine yamal", "player_shots_on_target", 1.5) -> 0.50
    player_props: dict[tuple[str, str, float | None], float] | None = None

    # Match statistics (from API-Football or similar sources)
    home_corners: int | None = None
    away_corners: int | None = None
    home_cards: int | None = None
    away_cards: int | None = None
    home_possession: float | None = None
    home_shots: int | None = None
    away_shots: int | None = None
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None
    home_fouls: int | None = None
    away_fouls: int | None = None

    # Half-specific totals from Polymarket More Markets
    # Structure: {line: P(over)} — same shape as totals
    first_half_totals: dict[float, float] | None = None
    second_half_totals: dict[float, float] | None = None
    # Per-team first/second half O/U: {team_name: {line: P(over)}}
    first_half_team_totals: dict[str, dict[float, float]] | None = None
    second_half_team_totals: dict[str, dict[float, float]] | None = None
    # Progression / special markets
    advance_prob: float | None = None        # P(home team advances)
    extra_time_prob: float | None = None     # P(match goes to ET)
    penalty_shootout_prob: float | None = None  # P(match goes to penalties)
    # First team to score: {team_name_lower: probability}
    first_goal_probs: dict[str, float] | None = None
    # Exact score probabilities: {(home_goals, away_goals): probability}
    exact_score_probs: dict[tuple[int, int], float] | None = None

    def has_any_odds(self) -> bool:
        if any(v is not None for v in (self.home_win, self.away_win, self.draw, self.btts_yes)):
            return True
        if self.totals or self.team_totals:
            return True
        if self.first_half_totals or self.first_half_team_totals:
            return True
        if self.advance_prob is not None:
            return True
        return False

    def get_player_prop(
        self,
        player_name: str,
        market_key: str,
        line: float | None = None,
    ) -> float | None:
        """
        Look up a bookmaker fair probability for a player prop.

        Tries exact line match first, then nearest available line (within 0.5).
        For anytime markets (no line), use line=None.
        """
        if not self.player_props:
            return None
        import unicodedata

        def _norm(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

        norm_player = _norm(player_name)

        # Exact match
        exact = self.player_props.get((norm_player, market_key, line))
        if exact is not None:
            return exact

        # Partial name match + nearest line
        best_prob: float | None = None
        best_line_diff = float("inf")
        for (stored_player, stored_market, stored_line), prob in self.player_props.items():
            if stored_market != market_key:
                continue
            query_words = norm_player.split()
            stored_words = stored_player.split()
            # Match if: all query words in stored, OR all stored words in query
            # (handles "Mahmoud Trezeguet" ↔ "Trezeguet")
            name_match = (
                all(w in stored_player for w in query_words) or
                all(w in norm_player for w in stored_words)
            )
            if not name_match:
                continue
            if line is None and stored_line is None:
                return prob
            # For anytime markets (line=None), also match threshold=1.0
            if line is None and stored_line == 1.0:
                return prob
            if line is not None and stored_line is not None:
                diff = abs(stored_line - line)
                if diff < best_line_diff and diff <= 0.6:
                    best_line_diff = diff
                    best_prob = prob

        return best_prob


def team_win_probability(match_odds: MatchOdds, team: str, match_name: str) -> float | None:
    """P(team wins in regulation) from 1X2 fair probabilities."""
    parsed = parse_match_name(match_name)
    if not parsed:
        return None
    home_name, away_name = parsed

    if teams_match(team, home_name):
        return match_odds.home_win
    if teams_match(team, away_name):
        return match_odds.away_win

    # Fallback: match against feed team names directly
    if teams_match(team, match_odds.home_team):
        return match_odds.home_win
    if teams_match(team, match_odds.away_team):
        return match_odds.away_win

    return None


def probability_for_market(
    lookup: MarketLookup,
    match_odds: MatchOdds,
    match_name: str,
) -> float | None:
    # Advance to next round (any stage) — Polymarket → bookmaker → win prob fallback.
    if lookup.kind == MarketKind.TEAM_ADVANCE and lookup.team:
        if match_odds.advance_prob is not None:
            parsed = parse_match_name(match_name)
            if parsed:
                home_name, away_name = parsed
                if teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team):
                    return round(match_odds.advance_prob, 3)
                else:
                    return round(1.0 - match_odds.advance_prob, 3)
        import unicodedata
        def _n(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
        if match_odds.player_props:
            norm_team = _n(lookup.team)
            for (stored_player, stored_market, _), prob in match_odds.player_props.items():
                if stored_market == "to_qualify":
                    stored_words = set(stored_player.split())
                    query_words = set(norm_team.split())
                    if query_words and query_words.issubset(stored_words):
                        return round(prob, 3)
        return team_win_probability(match_odds, lookup.team, match_name)

    # Penalty shootout — use Polymarket penalty_shootout_prob directly.
    if lookup.kind == MarketKind.PENALTY_SHOOTOUT:
        if match_odds.penalty_shootout_prob is not None:
            return round(match_odds.penalty_shootout_prob, 3)
        if match_odds.extra_time_prob is not None:
            return round(match_odds.extra_time_prob * 0.5, 3)
        return None

    # More total cards than total goals — independent Poisson comparison.
    if lookup.kind == MarketKind.MORE_CARDS_THAN_GOALS:
        import math
        from poisson import estimate_lambda_from_match_odds, poisson_pmf
        from team_stats import estimate_total_cards_probability, _rate, _load
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        lam_goals = estimate_lambda_from_match_odds(match_odds)
        if lam_goals is None:
            return None
        lam_cards = _rate(home_name, "cards_per_match") + _rate(away_name, "cards_per_match")
        # P(cards > goals) = sum over c > g: P(C=c) * P(G=g)
        prob = 0.0
        for c in range(15):
            pc = poisson_pmf(c, lam_cards)
            for g in range(c):  # g < c means cards > goals
                prob += pc * poisson_pmf(g, lam_goals)
        return round(max(min(prob, 0.99), 0.01), 3)
    if lookup.kind == MarketKind.EXACT_GOALS and lookup.line is not None:
        n = int(lookup.line)
        if match_odds.exact_score_probs:
            total = sum(
                prob for (h, a), prob in match_odds.exact_score_probs.items()
                if h + a == n
            )
            if total > 0:
                return round(min(total, 0.99), 3)
        # Fallback: Poisson P(X = n) from match totals
        from poisson import estimate_lambda_from_match_odds, poisson_pmf
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is not None:
            return round(poisson_pmf(n, lam), 3)
        return None

    # Goal in each half — P(≥1 goal H1) × P(≥1 goal H2), using Polymarket H1/H2 totals.
    if lookup.kind == MarketKind.GOAL_EACH_HALF:
        p_h1 = (match_odds.first_half_totals or {}).get(0.5)
        p_h2 = (match_odds.second_half_totals or {}).get(0.5)
        if p_h1 is not None and p_h2 is not None:
            return round(max(min(p_h1 * p_h2, 0.99), 0.01), 3)
        import math
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, split_lambda as _split
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_h, lam_a = _split(lam, match_odds.home_win, match_odds.away_win)
        half_total = (lam_h + lam_a) / 2.0
        p_h1 = 1.0 - math.exp(-half_total)
        p_h2 = 1.0 - math.exp(-half_total)
        return round(max(min(p_h1 * p_h2, 0.99), 0.01), 3)

    # Team shots on target comparison (e.g. USA more SOT than Belgium).
    if lookup.kind == MarketKind.MORE_SHOTS_THAN and lookup.team and lookup.team_b:
        from team_stats import _rate, _LEAGUE_AVG, _load, _opponent_adjusted_lam
        from poisson import poisson_pmf
        _load()
        lam_a = _opponent_adjusted_lam(
            lookup.team, lookup.team_b,
            "shots_on_target_per_match", "sot_conceded_per_match",
        )
        lam_b = _opponent_adjusted_lam(
            lookup.team_b, lookup.team,
            "shots_on_target_per_match", "sot_conceded_per_match",
        )
        prob = 0.0
        for a in range(30):
            pa = poisson_pmf(a, lam_a)
            for b in range(a):
                prob += pa * poisson_pmf(b, lam_b)
        return round(prob, 3)

    # First goal scorer — use Polymarket "First Team to Score" event directly.
    if lookup.kind == MarketKind.FIRST_GOAL_SCORER and lookup.team:
        # Direct from Polymarket First Team to Score event
        if match_odds.first_goal_probs:
            import unicodedata
            def _fn(s: str) -> str:
                nfkd = unicodedata.normalize("NFKD", s)
                return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
            norm = _fn(lookup.team)
            # Try exact then partial word match
            if norm in match_odds.first_goal_probs:
                return round(match_odds.first_goal_probs[norm], 3)
            for stored_team, prob in match_odds.first_goal_probs.items():
                stored_words = set(stored_team.split())
                query_words = set(norm.split())
                if query_words and query_words.issubset(stored_words):
                    return round(prob, 3)
        # Fallback: Poisson model from totals
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, split_lambda as _split
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is not None:
            lam_home, lam_away = _split(lam, match_odds.home_win, match_odds.away_win)
            parsed = parse_match_name(match_name)
            if parsed:
                home_name, away_name = parsed
                if teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team):
                    import math
                    p_any_goal = 1.0 - math.exp(-(lam_home + lam_away))
                    p_home_first = lam_home / (lam_home + lam_away) * p_any_goal
                    return round(max(min(p_home_first, 0.99), 0.01), 3)
                if teams_match(lookup.team, away_name) or teams_match(lookup.team, match_odds.away_team):
                    import math
                    p_any_goal = 1.0 - math.exp(-(lam_home + lam_away))
                    p_away_first = lam_away / (lam_home + lam_away) * p_any_goal
                    return round(max(min(p_away_first, 0.99), 0.01), 3)
        return team_win_probability(match_odds, lookup.team, match_name)

    # Score in both halves — use Polymarket team half totals when available.
    if lookup.kind == MarketKind.SCORE_BOTH_HALVES and lookup.team:
        import math
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed

        ht1 = match_odds.first_half_team_totals or {}
        ht2 = match_odds.second_half_team_totals or {}

        is_home = teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team)
        key_name = home_name if is_home else away_name

        team_h1 = next((v for k, v in ht1.items() if teams_match(k, key_name)), None)
        team_h2 = next((v for k, v in ht2.items() if teams_match(k, key_name)), None)

        if team_h1 and team_h2 and 0.5 in team_h1 and 0.5 in team_h2:
            # P(score ≥1 in H1) × P(score ≥1 in H2)
            return round(max(min(team_h1[0.5] * team_h2[0.5], 0.99), 0.01), 3)

        # Fallback: Poisson model
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, split_lambda as _split
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_home, lam_away = _split(lam, match_odds.home_win, match_odds.away_win)
        team_lam = lam_home if is_home else lam_away
        half_lam = team_lam / 2.0
        p_score_h1 = 1.0 - math.exp(-half_lam)
        p_score_h2 = 1.0 - math.exp(-half_lam)
        return round(max(min(p_score_h1 * p_score_h2, 0.99), 0.01), 3)

    if lookup.kind == MarketKind.TEAM_WIN_REGULATION and lookup.team:
        return team_win_probability(match_odds, lookup.team, match_name)

    if lookup.kind == MarketKind.BOTH_TEAMS_SCORE:
        return match_odds.btts_yes

    if lookup.kind == MarketKind.DRAW_REGULATION:
        return match_odds.draw

    if lookup.kind == MarketKind.OVER_GOALS and lookup.line is not None:
        return _lookup_total_line(match_odds.totals, lookup.line)

    # Under goals — inverse of the over line. Prefer the direct market line,
    # fall back to the Poisson CDF when that exact line isn't published.
    if lookup.kind == MarketKind.UNDER_GOALS and lookup.line is not None:
        over = _lookup_total_line(match_odds.totals, lookup.line)
        if over is not None:
            return 1.0 - over
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, poisson_cdf
        import math

        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        # "N or fewer" with line = N + 0.5 → P(X <= N)
        return poisson_cdf(math.floor(lookup.line), lam)

    # Clean sheet — P(the opposing team scores zero) from the Poisson model.
    if lookup.kind == MarketKind.CLEAN_SHEET and lookup.team:
        import math
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, split_lambda

        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_home, lam_away = split_lambda(lam, match_odds.home_win, match_odds.away_win)
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        # Clean sheet for the home team means the away team scores 0, and vice versa.
        if teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team):
            return math.exp(-lam_away)
        if teams_match(lookup.team, away_name) or teams_match(lookup.team, match_odds.away_team):
            return math.exp(-lam_home)
        return None

    # Second half produces more goals than the first (symmetric Poisson split).
    if lookup.kind == MarketKind.SECOND_HALF_MORE_GOALS:
        # Use Polymarket H1 and H2 total O/U lines when available
        p_over_h1 = (match_odds.first_half_totals or {}).get(0.5)
        p_over_h2 = (match_odds.second_half_totals or {}).get(0.5)
        if p_over_h1 is not None and p_over_h2 is not None:
            # Derive lambdas for each half from Polymarket's O/U 0.5 prices
            import math
            def _lam_from_p(p: float) -> float:
                lo, hi = 0.01, 8.0
                for _ in range(60):
                    mid = (lo + hi) / 2
                    if (1.0 - math.exp(-mid)) < p:
                        lo = mid
                    else:
                        hi = mid
                return (lo + hi) / 2
            lam_h1 = _lam_from_p(p_over_h1)
            lam_h2 = _lam_from_p(p_over_h2)
            from poisson import prob_second_half_more_goals as _pshm
            # Use the ratio of second-half to first-half lambda to scale
            # the symmetric computation
            lam_avg = (lam_h1 + lam_h2) / 2.0
            # P(H2 > H1): compute directly from independent Poisson with each half's lambda
            from poisson import poisson_pmf
            max_g = 10
            p_more = 0.0
            for h2 in range(max_g + 1):
                p2 = poisson_pmf(h2, lam_h2)
                for h1 in range(h2):
                    p_more += p2 * poisson_pmf(h1, lam_h1)
            return round(max(min(p_more, 0.99), 0.01), 3)

        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, prob_second_half_more_goals
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        return prob_second_half_more_goals(lam)

    # Total offside calls — sum both teams' historical offside rates (Poisson).
    if lookup.kind == MarketKind.TOTAL_OFFSIDES and lookup.line is not None:
        from team_stats import estimate_total_offsides_probability
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        return estimate_total_offsides_probability(home_name, away_name, lookup.line)

    # Total shots on+off target — sum both teams' historical total-shot rates.
    if lookup.kind == MarketKind.TOTAL_SHOTS and lookup.line is not None:
        from team_stats import estimate_total_shots_probability
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        return estimate_total_shots_probability(home_name, away_name, lookup.line)

    # Header goal — per-team header-goal fractions scaled to expected goals.
    # Pass win probabilities so the goal split is team-weighted, not 50/50.
    if lookup.kind == MarketKind.HEADER_GOAL:
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds
        from team_stats import estimate_header_goal_probability
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        return estimate_header_goal_probability(
            home_name, away_name, lam,
            home_win=match_odds.home_win,
            away_win=match_odds.away_win,
        )

    # Penalty awarded OR red card shown.
    if lookup.kind == MarketKind.PENALTY_OR_RED:
        from team_stats import estimate_penalty_or_red_probability
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        return estimate_penalty_or_red_probability(home_name, away_name)

    # Substitution before halftime — historical first-half sub rates.
    if lookup.kind == MarketKind.EARLY_SUB:
        from team_stats import estimate_early_sub_probability
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        return estimate_early_sub_probability(home_name, away_name)

    # Time-window goal markets — hydration breaks split each half in two.
    # Break 1 sits at ~22.5 min (halfway through 1st half).
    # Break 2 sits at ~67.5 min (halfway through 2nd half).
    # "Before first break"  = goal in [0, 22.5]   — early, low-rate segment
    # "After second break"  = goal in [67.5, 90]  — late, high-rate segment
    # Uses a non-uniform rate model: goals cluster toward end of each half.
    if lookup.kind in (
        MarketKind.GOAL_BEFORE_FIRST_HYDRATION,
        MarketKind.GOAL_AFTER_SECOND_HYDRATION,
    ):
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, prob_goal_in_window

        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        if lookup.kind == MarketKind.GOAL_BEFORE_FIRST_HYDRATION:
            # [0, 22.5] — early window, rate below average
            return round(prob_goal_in_window(lam, minutes=22.5, start=0.0), 3)
        else:
            # [67.5, 90] — late window, rate above average
            return round(prob_goal_in_window(lam, minutes=22.5, start=67.5), 3)

    # Halftime scoreline markets — use Polymarket 1st half O/U lines when available
    # (much more accurate than Poisson model), falling back to Poisson.
    if lookup.kind in (MarketKind.AHEAD_AT_HALFTIME, MarketKind.TIED_AT_HALFTIME):
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed

        # Try to use Polymarket first-half team totals directly.
        # Spain 1st Half O/U 0.5 = P(Spain score ≥1 in H1)
        # Austria 1st Half O/U 0.5 = P(Austria score ≥1 in H1)
        ht = match_odds.first_half_team_totals or {}
        home_ht = None
        away_ht = None
        for team_name, lines in ht.items():
            if teams_match(team_name, home_name) or teams_match(team_name, match_odds.home_team):
                home_ht = lines
            elif teams_match(team_name, away_name) or teams_match(team_name, match_odds.away_team):
                away_ht = lines

        # Check for direct halftime lead probability from Polymarket Halftime Result event
        if lookup.kind == MarketKind.AHEAD_AT_HALFTIME:
            for team_name, lines in ht.items():
                if (teams_match(team_name, home_name) or teams_match(team_name, match_odds.home_team)):
                    if "halftime_lead" in lines and lookup.team and (teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team)):
                        return round(lines["halftime_lead"], 3)
                elif (teams_match(team_name, away_name) or teams_match(team_name, match_odds.away_team)):
                    if "halftime_lead" in lines and lookup.team and (teams_match(lookup.team, away_name) or teams_match(lookup.team, match_odds.away_team)):
                        return round(lines["halftime_lead"], 3)

        if lookup.kind == MarketKind.TIED_AT_HALFTIME:
            ft = match_odds.first_half_totals or {}
            if "halftime_draw" in ft:
                return round(ft["halftime_draw"], 3)

        if home_ht and away_ht and 0.5 in home_ht and 0.5 in away_ht:
            # Derive half-lambdas by bisection from P(over 0.5)
            from poisson import prob_over
            def _lam_from_p_over05(p: float) -> float:
                import math
                lo, hi = 0.01, 8.0
                for _ in range(60):
                    mid = (lo + hi) / 2.0
                    if (1.0 - math.exp(-mid)) < p:
                        lo = mid
                    else:
                        hi = mid
                return (lo + hi) / 2.0

            lam_home_ht = _lam_from_p_over05(home_ht[0.5])
            lam_away_ht = _lam_from_p_over05(away_ht[0.5])

            from poisson import scoreline_probs
            p_home_lead, p_tie, p_away_lead = scoreline_probs(lam_home_ht, lam_away_ht)

            if lookup.kind == MarketKind.TIED_AT_HALFTIME:
                return p_tie
            if lookup.team and teams_match(lookup.team, home_name):
                return p_home_lead
            if lookup.team and teams_match(lookup.team, away_name):
                return p_away_lead
            if lookup.team and teams_match(lookup.team, match_odds.home_team):
                return p_home_lead
            if lookup.team and teams_match(lookup.team, match_odds.away_team):
                return p_away_lead
            return None

        # Fallback: Poisson model from full-match odds
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, scoreline_probs, split_lambda
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_home, lam_away = split_lambda(lam, match_odds.home_win, match_odds.away_win)
        p_home_lead, p_tie, p_away_lead = scoreline_probs(lam_home / 2.0, lam_away / 2.0)

        if lookup.kind == MarketKind.TIED_AT_HALFTIME:
            return p_tie
        if lookup.team and teams_match(lookup.team, home_name):
            return p_home_lead
        if lookup.team and teams_match(lookup.team, away_name):
            return p_away_lead
        if lookup.team and teams_match(lookup.team, match_odds.home_team):
            return p_home_lead
        if lookup.team and teams_match(lookup.team, match_odds.away_team):
            return p_away_lead
        return None

    if lookup.kind == MarketKind.TEAM_SCORE and lookup.team and lookup.line is not None:
        team_totals = match_odds.team_totals or {}
        for team_name, lines in team_totals.items():
            if teams_match(lookup.team, team_name):
                return _lookup_total_line(lines, lookup.line)
        parsed = parse_match_name(match_name)
        if parsed:
            home_name, away_name = parsed
            if teams_match(lookup.team, home_name):
                p = _lookup_total_line((match_odds.team_totals or {}).get(home_name), lookup.line)
                if p is not None:
                    return p
            if teams_match(lookup.team, away_name):
                p = _lookup_total_line((match_odds.team_totals or {}).get(away_name), lookup.line)
                if p is not None:
                    return p
        # Fallback: use the team's historical goals-per-match as Poisson λ.
        from poisson import prob_at_least
        import math
        from team_stats import _rate as team_rate
        lam_goals = team_rate(lookup.team, "shots_on_target_per_match") * 0.30  # ~30% conversion
        return round(prob_at_least(math.ceil(lookup.line + 0.5), lam_goals), 3)

    # Player prop lookups — bookmaker odds take priority, fall back to stats model.
    if lookup.kind == MarketKind.PLAYER_GOAL and lookup.player and lookup.team:
        bm = match_odds.get_player_prop(lookup.player, "player_anytime_goalscorer")
        if bm is not None:
            return bm
        from player_stats import estimate_player_goal_probability
        return estimate_player_goal_probability(lookup.player, lookup.team)

    if lookup.kind == MarketKind.PLAYER_GOAL_OR_ASSIST and lookup.player and lookup.team:
        # Polymarket's "player_goal_or_assist" combined lines are unreliable —
        # they are priced as independent yes/no binary markets per threshold,
        # not as cumulative "at least N" probabilities.
        # Derive P(goal OR assist ≥ 1) from individual goal + assist Polymarket markets.
        p_goal   = match_odds.get_player_prop(lookup.player, "player_anytime_goalscorer", 1.0)
        p_assist = match_odds.get_player_prop(lookup.player, "player_assists", 1.0)
        if p_goal is not None:
            if p_assist is None:
                from player_stats import estimate_player_assist_probability
                p_assist = estimate_player_assist_probability(lookup.player, lookup.team)
            return round(max(min(1.0 - (1.0 - p_goal) * (1.0 - p_assist), 0.99), 0.01), 3)
        from player_stats import estimate_player_goal_or_assist_probability
        return estimate_player_goal_or_assist_probability(lookup.player, lookup.team)

    if lookup.kind == MarketKind.PLAYER_ASSISTS and lookup.player and lookup.team and lookup.line:
        from player_stats import estimate_player_assists_threshold_probability
        return estimate_player_assists_threshold_probability(lookup.player, lookup.team, lookup.line)

    if lookup.kind == MarketKind.PLAYER_SHOTS_ON_TARGET and lookup.player and lookup.team and lookup.line:
        bm = match_odds.get_player_prop(lookup.player, "player_shots_on_target", lookup.line)
        if bm is not None:
            return bm
        from player_stats import estimate_player_shots_on_target_probability
        return estimate_player_shots_on_target_probability(
            lookup.player, lookup.team, lookup.line
        )

    if lookup.kind == MarketKind.PLAYER_CARDS and lookup.player and lookup.team:
        bm = match_odds.get_player_prop(lookup.player, "player_cards")
        if bm is not None:
            return bm
        from player_stats import estimate_player_card_probability
        return estimate_player_card_probability(lookup.player, lookup.team)

    # Any player scores N+ goals (brace/hat-trick) — Poisson over all tracked players.
    if lookup.kind == MarketKind.PLAYER_BRACE and lookup.line is not None:
        from player_stats import estimate_any_player_brace_probability
        from poisson import estimate_lambda_from_totals, estimate_lambda_from_match_odds, split_lambda as _split
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        # Pass fixture expected goals so the fallback is fixture-specific
        lam = estimate_lambda_from_match_odds(match_odds)
        lam_home = lam_away = None
        if lam is not None:
            lam_home, lam_away = _split(lam, match_odds.home_win, match_odds.away_win)
        return estimate_any_player_brace_probability(
            home_name, away_name, int(lookup.line),
            lam_a=lam_home, lam_b=lam_away,
        )

    # Team stat lookups — historical international rates (Poisson model).
    if lookup.kind == MarketKind.TEAM_SHOTS_ON_TARGET and lookup.team and lookup.line is not None:
        from team_stats import estimate_team_shots_on_target_probability
        parsed = parse_match_name(match_name)
        opponent = None
        if parsed:
            home_name, away_name = parsed
            opponent = away_name if teams_match(lookup.team, home_name) else home_name
        return estimate_team_shots_on_target_probability(lookup.team, lookup.line, opponent=opponent)

    if lookup.kind == MarketKind.TEAM_CORNERS and lookup.team and lookup.line is not None:
        # Use bookmaker corner O/U line when available
        bm = match_odds.get_player_prop(lookup.team, "team_corners_line", lookup.line)
        if bm is not None:
            return bm
        from team_stats import estimate_team_corners_probability
        parsed = parse_match_name(match_name)
        opponent = None
        is_home = True
        if parsed:
            home_name, away_name = parsed
            if teams_match(lookup.team, home_name):
                opponent = away_name
                is_home = True
            else:
                opponent = home_name
                is_home = False
        return estimate_team_corners_probability(
            lookup.team, lookup.line, opponent=opponent,
            home_win=match_odds.home_win, away_win=match_odds.away_win,
            is_home=is_home,
        )

    if lookup.kind in (MarketKind.TOTAL_CORNERS, MarketKind.BOTH_TEAMS_CORNERS) and lookup.line is not None:
        # Check Polymarket total corners line first
        if match_odds.player_props:
            bm = match_odds.player_props.get(("", "total_corners_line", lookup.line))
            if bm is None:
                # Try nearest line
                bm = match_odds.get_player_prop("", "total_corners_line", lookup.line)
            if bm is not None:
                return bm
        from team_stats import estimate_total_corners_probability
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name2, away_name2 = parsed
        return estimate_total_corners_probability(
            home_name2, away_name2, lookup.line,
            home_win=match_odds.home_win, away_win=match_odds.away_win,
        )

    if lookup.kind == MarketKind.MORE_CORNERS_THAN and lookup.team and lookup.team_b:
        # Try to derive from Polymarket team corner O/U lines
        if match_odds and match_odds.player_props:
            import unicodedata, math
            from poisson import poisson_pmf, prob_at_least

            def _norm_team(s: str) -> str:
                nfkd = unicodedata.normalize("NFKD", s)
                return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

            def _lam_from_ou(team_norm: str, line: float, p_over: float) -> float:
                """Bisection: find lambda where P(X >= ceil(line+0.5)) = p_over."""
                n = int(math.ceil(line + 0.5))
                lo, hi = 0.01, 25.0
                for _ in range(80):
                    mid = (lo + hi) / 2
                    if prob_at_least(n, mid) < p_over:
                        lo = mid
                    else:
                        hi = mid
                return (lo + hi) / 2

            # Collect all team_corners_line entries for each team
            team_a_norm = _norm_team(lookup.team)
            team_b_norm = _norm_team(lookup.team_b)
            lines_a: dict[float, float] = {}
            lines_b: dict[float, float] = {}
            for (stored_player, stored_market, stored_line), prob in match_odds.player_props.items():
                if stored_market != "team_corners_line" or stored_line is None:
                    continue
                sp_words = set(stored_player.split())
                if set(team_a_norm.split()).issubset(sp_words):
                    lines_a[stored_line] = prob
                elif set(team_b_norm.split()).issubset(sp_words):
                    lines_b[stored_line] = prob

            if lines_a and lines_b:
                # Use the most informative line (closest to 50%) to back-solve lambda
                best_a = min(lines_a.items(), key=lambda kv: abs(kv[1] - 0.5))
                best_b = min(lines_b.items(), key=lambda kv: abs(kv[1] - 0.5))
                lam_a = _lam_from_ou(team_a_norm, best_a[0], best_a[1])
                lam_b = _lam_from_ou(team_b_norm, best_b[0], best_b[1])
                # P(A > B) from independent Poisson
                prob = 0.0
                for a in range(26):
                    pa = poisson_pmf(a, lam_a)
                    for b in range(a):
                        prob += pa * poisson_pmf(b, lam_b)
                return round(prob, 3)

        from team_stats import estimate_more_corners_than
        return estimate_more_corners_than(
            lookup.team, lookup.team_b,
            home_win=match_odds.home_win, away_win=match_odds.away_win,
        )

    if lookup.kind == MarketKind.BOTH_TEAMS_CARDS:
        from team_stats import estimate_both_teams_card_probability
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        return estimate_both_teams_card_probability(home_name, away_name)

    if lookup.kind == MarketKind.TEAM_CARDS and lookup.line is not None:
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        if lookup.team:
            # Team-specific card count.
            from team_stats import estimate_team_cards_probability
            return estimate_team_cards_probability(lookup.team, lookup.line)
        # No team → total cards across both sides.
        from team_stats import estimate_total_cards_probability
        return estimate_total_cards_probability(home_name, away_name, lookup.line)

    # --- New markets ---

    # "Will the match go to extra time" — direct from Polymarket extra_time_prob.
    if lookup.kind == MarketKind.EXTRA_TIME:
        if match_odds.extra_time_prob is not None:
            return round(match_odds.extra_time_prob, 3)
        return None

    # "Will a substitute score a goal" — ~15% base rate for WC; scales with
    # expected total goals since more goals = more chances for a sub to score.
    if lookup.kind == MarketKind.SUB_SCORES:
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            lam = 2.5  # neutral fallback
        # ~15% of WC goals are scored by substitutes (conservative vs 30% all comps).
        # P(at least one sub goal) = 1 - exp(-0.15 * lam)
        import math
        p = 1.0 - math.exp(-0.15 * lam)
        return round(max(min(p, 0.99), 0.01), 3)

    # "Will <Team> hold a lead at any point" — P(team scores at least once)
    # times a boost for drawing level after trailing, using Polymarket first-goal
    # and win/draw/loss probabilities for calibration.
    if lookup.kind == MarketKind.TEAM_HOLDS_LEAD and lookup.team:
        import math
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        is_home = teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team)

        # Use Polymarket team O/U 0.5 if available (P team scores ≥1)
        team_totals = match_odds.team_totals or {}
        key_name = home_name if is_home else away_name
        p_scores = None
        for t, lines in team_totals.items():
            if teams_match(t, key_name) and 0.5 in lines:
                p_scores = lines[0.5]
                break

        if p_scores is None:
            # Fallback: derive from lambda split
            from poisson import estimate_lambda_from_match_odds, split_lambda
            lam = estimate_lambda_from_match_odds(match_odds)
            if lam is None:
                return None
            lam_home, lam_away = split_lambda(lam, match_odds.home_win, match_odds.away_win)
            team_lam = lam_home if is_home else lam_away
            p_scores = 1.0 - math.exp(-team_lam)

        # If team scores, they lead at some point (unless they only score from
        # behind after going down first — rare at this level).
        # Additional small chance: team scores first-half equaliser after falling
        # behind but then the opponent goes ahead again. We treat P(holds lead) ≈
        # P(scores ≥ 1) as a practical approximation.
        return round(max(min(p_scores, 0.99), 0.01), 3)

    # "Will a penalty kick be awarded" — uses only penalty rate, no red card.
    # Penalty rates in small samples can be inflated; cap the combined lambda
    # to a realistic WC ceiling (~0.35 per match = ~30% P(penalty)).
    if lookup.kind == MarketKind.PENALTY_AWARDED:
        import math
        from team_stats import _rate, _load
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        lam_raw = _rate(home_name, "penalties_conceded_per_match") + _rate(away_name, "penalties_conceded_per_match")
        # Cap at WC average (~0.27 pens per game combined) blended with team rates.
        # Use a 25/75 blend (mostly neutral) to avoid small-sample inflation.
        WC_PEN_RATE = 0.27
        lam = 0.25 * lam_raw + 0.75 * WC_PEN_RATE
        return round(1.0 - math.exp(-lam), 3)

    # "Will both halves have the same number of goals" — i.e. H1 goals == H2 goals.
    # Computed from independent Poisson distributions for each half.
    if lookup.kind == MarketKind.HALVES_SAME_GOALS:
        import math
        from poisson import estimate_lambda_from_match_odds, poisson_pmf

        # Prefer Polymarket half O/U lines to derive per-half lambdas
        ft1 = match_odds.first_half_totals or {}
        ft2 = match_odds.second_half_totals or {}

        def _lam_from_p05(p: float) -> float:
            lo, hi = 0.01, 8.0
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if (1.0 - math.exp(-mid)) < p:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2.0

        if ft1.get(0.5) and ft2.get(0.5):
            lam_h1 = _lam_from_p05(ft1[0.5])
            lam_h2 = _lam_from_p05(ft2[0.5])
        else:
            lam = estimate_lambda_from_match_odds(match_odds)
            if lam is None:
                return None
            lam_h1 = lam_h2 = lam / 2.0

        # P(H1 == H2) = sum_k P(H1=k) * P(H2=k)
        p_equal = sum(poisson_pmf(k, lam_h1) * poisson_pmf(k, lam_h2) for k in range(12))
        return round(max(min(p_equal, 0.99), 0.01), 3)

    # "Will the first card be shown before the first goal" —
    # Race between first card time and first goal time. Cards are roughly
    # uniform; goals non-uniform (front-loaded early, but still: the first
    # event comparison can be modelled as P(card rate > goal rate in the race).
    # Empirically in WC ~35-40% of matches see a card before a goal.
    if lookup.kind == MarketKind.FIRST_CARD_BEFORE_GOAL:
        import math
        from team_stats import _rate, _load, _CARDS_SCALE
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        from poisson import estimate_lambda_from_match_odds
        lam_goals = estimate_lambda_from_match_odds(match_odds) or 2.5
        lam_cards = (_rate(home_name, "cards_per_match") + _rate(away_name, "cards_per_match")) * _CARDS_SCALE
        p = lam_cards / (lam_cards + lam_goals)
        return round(max(min(p, 0.99), 0.01), 3)

    # "Will <Player> (Team) make N or more saves" — model from opponent's expected SOT.
    if lookup.kind == MarketKind.GK_SAVES and lookup.player and lookup.team and lookup.line is not None:
        import math
        from team_stats import _opponent_adjusted_lam, _rate, _load
        from poisson import prob_at_least
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        # The GK's saves ≈ opponent's shots on target that don't result in goals
        # We model: saves ~ opponent SOT. Find who is the opponent.
        if teams_match(lookup.team, home_name):
            opponent = away_name
        else:
            opponent = home_name
        lam_sot = _opponent_adjusted_lam(opponent, lookup.team,
                                          "shots_on_target_per_match", "sot_conceded_per_match")
        # Saves = SOT that don't score. If ~30% of SOT become goals, saves ≈ 0.7 * SOT.
        lam_saves = lam_sot * 0.7
        return round(prob_at_least(int(lookup.line), lam_saves), 3)

    # "Will there be N or more total substitutions" — both teams combined.
    # Top-level international teams make 4-5 subs per game. Combined ~9-10.
    if lookup.kind == MarketKind.TOTAL_SUBS and lookup.line is not None:
        import math
        from team_stats import _rate, _load
        from poisson import prob_at_least
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        # Average subs per team in a WC match: ~4.5 (max 5 allowed).
        # We don't track this directly but can use early_sub_rate as a proxy
        # or just use a fixed combined lambda of 9.0 (4.5 per team).
        lam_subs = 9.0  # typical combined subs in 90 min international
        return round(prob_at_least(int(lookup.line), lam_subs), 3)

    # "Will a substitute score or assist" — scales like SUB_SCORES but ~25% of
    # goal involvements (goals + assists) come from substitutes.
    if lookup.kind == MarketKind.SUB_SCORES_OR_ASSISTS:
        import math
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            lam = 2.5
        # ~25% of goal involvements come from subs (goals + assists each at 15%)
        # model as a combined Poisson with rate = 0.25 * lam
        p = 1.0 - math.exp(-0.25 * lam)
        return round(max(min(p, 0.99), 0.01), 3)

    # "Will the first goal be scored in the second half"
    # = P(no goal in H1) × P(at least one goal in H2)
    if lookup.kind == MarketKind.FIRST_GOAL_SECOND_HALF:
        import math
        ft1 = match_odds.first_half_totals or {}
        ft2 = match_odds.second_half_totals or {}
        p_h1_goal = ft1.get(0.5)   # P(≥1 goal H1)
        p_h2_goal = ft2.get(0.5)   # P(≥1 goal H2)
        if p_h1_goal is not None and p_h2_goal is not None:
            p_no_h1 = 1.0 - p_h1_goal
            return round(max(min(p_no_h1 * p_h2_goal, 0.99), 0.01), 3)
        # Fallback: Poisson half-lambdas
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_half = lam / 2.0
        p_no_h1 = math.exp(-lam_half)
        p_h2    = 1.0 - math.exp(-lam_half)
        return round(max(min(p_no_h1 * p_h2, 0.99), 0.01), 3)

    # "Will either team win both halves"
    # = P(home wins H1 AND home wins H2) + P(away wins H1 AND away wins H2)
    # Uses per-team half O/U 0.5 from Polymarket to derive P(team scores ≥1 in each half).
    # A team "wins a half" if they score more than the other in that half, which we
    # approximate using the H1/H2 scoreline model (independent Poisson per half).
    if lookup.kind == MarketKind.EITHER_TEAM_WINS_BOTH_HALVES:
        import math
        from poisson import scoreline_probs

        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed

        def _lam_from_p05(p: float) -> float:
            """Bisect to find λ where P(X≥1) = p, i.e. 1-exp(-λ)=p."""
            lo, hi = 0.001, 8.0
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if (1.0 - math.exp(-mid)) < p:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2.0

        ht1 = match_odds.first_half_team_totals or {}
        ht2 = match_odds.second_half_team_totals or {}

        # Get per-team, per-half lambdas
        def _team_half_lam(team_totals: dict, team: str, fallback_lam: float) -> float:
            for t, lines in team_totals.items():
                if teams_match(t, team):
                    p = lines.get(0.5)
                    if p and 0 < p < 1:
                        return _lam_from_p05(p)
            return fallback_lam

        from poisson import estimate_lambda_from_match_odds, split_lambda
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_home, lam_away = split_lambda(lam, match_odds.home_win, match_odds.away_win)
        lam_h_h1 = _team_half_lam(ht1, home_name, lam_home / 2.0)
        lam_a_h1 = _team_half_lam(ht1, away_name, lam_away / 2.0)
        lam_h_h2 = _team_half_lam(ht2, home_name, lam_home / 2.0)
        lam_a_h2 = _team_half_lam(ht2, away_name, lam_away / 2.0)

        p_h_h1, _, p_a_h1 = scoreline_probs(lam_h_h1, lam_a_h1)
        p_h_h2, _, p_a_h2 = scoreline_probs(lam_h_h2, lam_a_h2)

        # Assume H1 and H2 independent
        p_home_both = p_h_h1 * p_h_h2
        p_away_both = p_a_h1 * p_a_h2
        return round(max(min(p_home_both + p_away_both, 0.99), 0.01), 3)

    # "Will match be decided by exactly one goal"
    # = sum of P(exact scores where |home - away| == 1)
    if lookup.kind == MarketKind.WIN_BY_ONE_GOAL:
        if match_odds.exact_score_probs:
            p_one = sum(
                prob for (h, a), prob in match_odds.exact_score_probs.items()
                if abs(h - a) == 1
            )
            p_not_draw = sum(
                prob for (h, a), prob in match_odds.exact_score_probs.items()
                if h != a
            )
            total = sum(match_odds.exact_score_probs.values())
            if total > 0.3:
                # Scale to account for uncovered outcomes
                p_one_scaled = p_one / total
                return round(max(min(p_one_scaled, 0.99), 0.01), 3)
        # Fallback: Poisson model — P(|H-A|=1) from independent Poisson per team
        from poisson import estimate_lambda_from_match_odds, split_lambda, poisson_pmf
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        lam_home, lam_away = split_lambda(lam, match_odds.home_win, match_odds.away_win)
        p_one = sum(
            poisson_pmf(h, lam_home) * poisson_pmf(a, lam_away)
            for h in range(9) for a in range(9)
            if abs(h - a) == 1
        )
        return round(max(min(p_one, 0.99), 0.01), 3)

    # "Will at least one card be shown in each half"
    # P(≥1 card H1) × P(≥1 card H2). Assume cards split evenly across halves
    # (no strong evidence for front/back loading in international data).
    if lookup.kind == MarketKind.CARD_EACH_HALF:
        import math
        from team_stats import _rate, _load, _CARDS_SCALE
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        lam_total = (_rate(home_name, "cards_per_match") + _rate(away_name, "cards_per_match")) * _CARDS_SCALE
        lam_half = lam_total / 2.0
        p_card_h1 = 1.0 - math.exp(-lam_half)
        p_card_h2 = 1.0 - math.exp(-lam_half)
        return round(max(min(p_card_h1 * p_card_h2, 0.99), 0.01), 3)

    # "Will a card be shown during first- or second-half stoppage time"
    # Cards are heavily concentrated in stoppage time (~3× the average per-minute rate).
    if lookup.kind == MarketKind.CARD_IN_STOPPAGE:
        import math
        from team_stats import _rate, _load, _CARDS_SCALE
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        lam_total = (_rate(home_name, "cards_per_match") + _rate(away_name, "cards_per_match")) * _CARDS_SCALE
        lam_stoppage = lam_total * (8.0 / 90.0) * 3.0
        p = 1.0 - math.exp(-lam_stoppage)
        return round(max(min(p, 0.99), 0.01), 3)

    # "Will the referee conduct an on-field VAR review"
    # ~30% of WC matches feature at least one pitchside monitor review.
    # Higher in knockout stages with more at stake.
    if lookup.kind == MarketKind.VAR_REVIEW:
        return 0.35

    # "Will the match be tied at end of regulation / go to extra time"
    # Use Polymarket extra_time_prob directly (or draw prob as fallback).
    if lookup.kind == MarketKind.GOES_TO_EXTRA_TIME:
        if match_odds.extra_time_prob is not None:
            return round(match_odds.extra_time_prob, 3)
        if match_odds.draw is not None:
            return round(match_odds.draw, 3)
        return None

    # "Will the first goal be scored by a player wearing a single-digit shirt (1-9)"
    # Historically ~45-55% of WC goals scored by players in shirts 1-9.
    if lookup.kind == MarketKind.FIRST_GOAL_SINGLE_DIGIT:
        import math
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        p_any_goal = 1.0 - math.exp(-lam) if lam else 0.92
        p_first_goal_single = 0.50 * p_any_goal
        return round(max(min(p_first_goal_single, 0.99), 0.01), 3)

    # "Will a goal be scored after the first hydration break but before the second"
    # = goal in [22.5, 67.5] — 45-minute window covering mid-first-half to mid-second-half
    if lookup.kind == MarketKind.GOAL_BETWEEN_HYDRATION_BREAKS:
        from poisson import estimate_lambda_from_match_odds, prob_goal_in_window
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        return round(prob_goal_in_window(lam, minutes=45.0, start=22.5), 3)

    # "Will a goal be scored during stoppage time"
    # Goals are highly concentrated in stoppage time (~15-20% of all goals in ~8 min).
    # WC data shows ~4x the per-minute rate in stoppage vs average.
    if lookup.kind == MarketKind.GOAL_IN_STOPPAGE:
        import math
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        # ~8 min total stoppage, goals at ~4x per-minute rate
        lam_stoppage = lam * (8.0 / 90.0) * 4.0
        p = 1.0 - math.exp(-lam_stoppage)
        return round(max(min(p, 0.99), 0.01), 3)

    # "Will each team record N or more shots on target"
    # P(home ≥ N SOT) × P(away ≥ N SOT), using opponent-adjusted lambdas.
    if lookup.kind == MarketKind.EACH_TEAM_SOT and lookup.line is not None:
        from team_stats import _opponent_adjusted_lam, _load
        from poisson import prob_at_least
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        lam_home = _opponent_adjusted_lam(home_name, away_name,
                                          "shots_on_target_per_match", "sot_conceded_per_match")
        lam_away = _opponent_adjusted_lam(away_name, home_name,
                                          "shots_on_target_per_match", "sot_conceded_per_match")
        n = int(lookup.line)
        p_home = prob_at_least(n, lam_home)
        p_away = prob_at_least(n, lam_away)
        return round(max(min(p_home * p_away, 0.99), 0.01), 3)

    # "Will the first goal be credited with an assist"
    # ~60-65% of WC goals have an assist. P(first goal has assist) × P(goal scored).
    if lookup.kind == MarketKind.FIRST_GOAL_HAS_ASSIST:
        import math
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        p_any_goal = 1.0 - math.exp(-lam) if lam else 0.92
        # ~62% of goals in international football have an assist
        return round(max(min(0.62 * p_any_goal, 0.99), 0.01), 3)

    # "Will a penalty kick be scored"
    # P(pen awarded) × P(pen converted | awarded). WC conversion rate ~75%.
    if lookup.kind == MarketKind.PENALTY_SCORED:
        import math
        from team_stats import _rate, _load, _CARDS_SCALE
        _load()
        parsed = parse_match_name(match_name)
        if not parsed:
            return None
        home_name, away_name = parsed
        lam_pen = _rate(home_name, "penalties_conceded_per_match") + _rate(away_name, "penalties_conceded_per_match")
        # Shrink toward WC baseline (same as PENALTY_AWARDED)
        WC_PEN_RATE = 0.27
        lam = 0.25 * lam_pen + 0.75 * WC_PEN_RATE
        p_awarded = 1.0 - math.exp(-lam)
        p_scored = p_awarded * 0.75  # 75% conversion
        return round(max(min(p_scored, 0.99), 0.01), 3)

    # "Will Player A record more SOT than Player B"
    # Compare individual player SOT lambdas using independent Poisson.
    if lookup.kind == MarketKind.PLAYER_MORE_SOT_THAN and lookup.players and len(lookup.players) == 2:
        import math
        from player_stats import get_player_stat, CLUB_SOT_PRIOR, _norm_name
        from poisson import poisson_pmf

        def _get_lam(name: str) -> float:
            d = get_player_stat(name, "")
            m = d.get("matches", 0)
            s = d.get("shots_on_target", 0)
            intl_lam = s / m if m > 0 else 0.0
            club_raw = CLUB_SOT_PRIOR.get(_norm_name(name))
            club_lam = club_raw * 0.75 if club_raw else None
            if m >= 15 or club_lam is None:
                return intl_lam if m > 0 else 0.5
            w = m / 15.0
            return w * intl_lam + (1 - w) * club_lam

        lam_a = _get_lam(lookup.players[0])
        lam_b = _get_lam(lookup.players[1])
        # P(A > B) from independent Poisson
        p_more = sum(
            poisson_pmf(a, lam_a) * poisson_pmf(b, lam_b)
            for a in range(15) for b in range(a)
        )
        return round(max(min(p_more, 0.99), 0.01), 3)

    # "Will N+ different team players attempt a shot"
    # A top WC team typically has 7-9 different players taking at least one shot.
    # 5 is a low threshold for any decent team — P is high (~85-95%).
    if lookup.kind == MarketKind.TEAM_N_DIFFERENT_SHOOTERS and lookup.team and lookup.line is not None:
        n = int(lookup.line)
        # Average different shooters per game for a top team: ~7-8
        # For a weaker team: ~5-6
        # Model: Poisson with lambda ~7 for top teams, ~5.5 for average
        from team_stats import _rate, _load
        from poisson import prob_at_least
        _load()
        # Use total shots as a proxy for how spread out the shots are.
        total_shots = _rate(lookup.team, "shots_total_per_match")
        # Approximate different shooters: ~60% of total shots come from unique players
        # (diminishing returns as shot volume increases)
        lam_shooters = total_shots * 0.55
        return round(max(min(prob_at_least(n, lam_shooters), 0.99), 0.01), 3)

    # "Will <Team> make the first substitution of the match"
    # Roughly 50/50 — the weaker team tends to sub first slightly more often.
    if lookup.kind == MarketKind.TEAM_FIRST_SUB and lookup.team:
        parsed = parse_match_name(match_name)
        if not parsed:
            return 0.50
        home_name, away_name = parsed
        p_team_first = 0.50
        if match_odds.home_win is not None and match_odds.away_win is not None:
            is_home = teams_match(lookup.team, home_name) or teams_match(lookup.team, match_odds.home_team)
            team_win = match_odds.home_win if is_home else match_odds.away_win
            p_team_first = 0.5 + 0.15 * (0.5 - team_win)
        return round(max(min(p_team_first, 0.99), 0.01), 3)

    # "Will the match be 0-0 at halftime" = P(no goals in H1)
    # = 1 - P(over 0.5 H1) from Polymarket first_half_totals
    if lookup.kind == MarketKind.HALFTIME_NIL_NIL:
        import math
        ft1 = match_odds.first_half_totals or {}
        p_goal_h1 = ft1.get(0.5)
        if p_goal_h1 is not None:
            return round(max(min(1.0 - p_goal_h1, 0.99), 0.01), 3)
        # Fallback: Poisson
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        return round(math.exp(-lam / 2.0), 3)

    # "Will either team make a substitution at halftime"
    # ~18% of teams make a halftime substitution in WC matches.
    # P(at least one of two teams does) = 1 - P(neither) = 1 - 0.82^2
    if lookup.kind == MarketKind.HALFTIME_SUB:
        import math
        p_neither = 0.82 * 0.82
        return round(1.0 - p_neither, 3)

    # "Will <Team> have more corners AND more total shots than <Team>"
    # Compound AND market. Both are correlated (dominant teams get both),
    # so: P(A and B) ≈ P(A) * P(B|A) ≈ P(A) * P(B) * (1 + correlation_boost)
    # We estimate using independent Poisson lambdas for corners and shots,
    # then apply a moderate positive correlation boost of ~1.3.
    if lookup.kind == MarketKind.TEAM_MORE_CORNERS_AND_SHOTS and lookup.team and lookup.team_b:
        import math, unicodedata
        from poisson import poisson_pmf, prob_at_least
        from team_stats import _opponent_adjusted_lam, _load
        _load()

        def _norm_t(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

        def _lam_from_ou(line: float, p_over: float) -> float:
            n = int(math.ceil(line + 0.5))
            lo, hi = 0.01, 25.0
            for _ in range(80):
                mid = (lo + hi) / 2
                if prob_at_least(n, mid) < p_over:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2

        # --- Corners: use Polymarket team corner O/U lines ---
        lam_corners_a = lam_corners_b = None
        if match_odds.player_props:
            norm_a = _norm_t(lookup.team)
            norm_b = _norm_t(lookup.team_b)
            lines_a: dict[float, float] = {}
            lines_b: dict[float, float] = {}
            for (pname, mkt, line), prob in match_odds.player_props.items():
                if mkt != "team_corners_line" or line is None:
                    continue
                if set(norm_a.split()).issubset(set(pname.split())):
                    lines_a[line] = prob
                elif set(norm_b.split()).issubset(set(pname.split())):
                    lines_b[line] = prob
            if lines_a and lines_b:
                best_a = min(lines_a.items(), key=lambda kv: abs(kv[1] - 0.5))
                best_b = min(lines_b.items(), key=lambda kv: abs(kv[1] - 0.5))
                lam_corners_a = _lam_from_ou(best_a[0], best_a[1])
                lam_corners_b = _lam_from_ou(best_b[0], best_b[1])

        if lam_corners_a is None:
            from team_stats import _rate
            lam_corners_a = _rate(lookup.team, "corners_per_match")
            lam_corners_b = _rate(lookup.team_b, "corners_per_match")

        # P(A more corners than B)
        p_more_corners = sum(
            poisson_pmf(a, lam_corners_a) * poisson_pmf(b, lam_corners_b)
            for a in range(26) for b in range(a)
        )

        # --- Shots: use opponent-adjusted SOT model ---
        lam_shots_a = _opponent_adjusted_lam(
            lookup.team, lookup.team_b,
            "shots_total_per_match", "shots_conceded_per_match",
        )
        lam_shots_b = _opponent_adjusted_lam(
            lookup.team_b, lookup.team,
            "shots_total_per_match", "shots_conceded_per_match",
        )
        p_more_shots = sum(
            poisson_pmf(a, lam_shots_a) * poisson_pmf(b, lam_shots_b)
            for a in range(40) for b in range(a)
        )

        # Combine with correlation: dominant teams tend to win both,
        # so joint probability > product. Boost factor ~1.3 (moderate correlation).
        p_joint = min(p_more_corners * p_more_shots * 1.3, min(p_more_corners, p_more_shots))
        return round(max(min(p_joint, 0.99), 0.01), 3)

    # "Will <Player> (Team) play the entire match" — P(player not subbed off).
    # Roughly: ~55-65% of starters play the full 90 min in WC games.
    if lookup.kind == MarketKind.PLAYER_PLAYS_FULL and lookup.player and lookup.team:
        # No per-player data; use a flat 60% probability (40% chance of sub).
        return 0.60

    # "Will total goals be an odd number" — sum P(X=1) + P(X=3) + P(X=5) + ...
    # Use exact_score_probs if available (most accurate), else Poisson PMF.
    if lookup.kind == MarketKind.ODD_GOALS:
        if match_odds.exact_score_probs:
            p_odd  = sum(prob for (h, a), prob in match_odds.exact_score_probs.items() if (h + a) % 2 == 1)
            p_even = sum(prob for (h, a), prob in match_odds.exact_score_probs.items() if (h + a) % 2 == 0)
            total  = p_odd + p_even
            if total > 0.3:  # enough coverage to be meaningful
                # Scale so odd + even = 1 (Polymarket only covers subset of outcomes)
                return round(max(min(p_odd / total, 0.99), 0.01), 3)
        # Fallback: Poisson PMF sum over odd k
        from poisson import estimate_lambda_from_match_odds, poisson_pmf
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        p_odd = sum(poisson_pmf(k, lam) for k in range(1, 15, 2))  # k=1,3,5,...
        return round(max(min(p_odd, 0.99), 0.01), 3)

    # "Will a goal be scored in the first half after the first hydration break"
    # = goal in window [22.5, 45] min (the second quarter of play).
    if lookup.kind == MarketKind.GOAL_AFTER_FIRST_HYDRATION_H1:
        from poisson import estimate_lambda_from_match_odds, prob_goal_in_window
        lam = estimate_lambda_from_match_odds(match_odds)
        if lam is None:
            return None
        # 22.5-minute window starting at 22.5 min (mid-first-half to half-time)
        return round(prob_goal_in_window(lam, minutes=22.5, start=22.5), 3)

    # "Will the first goal be scored by a player other than X and Y"
    # P(first goal NOT by any named player) = 1 - sum P(named player scores first)
    # Use Polymarket first_goal_probs + player_anytime_goalscorer to split within teams.
    if lookup.kind == MarketKind.FIRST_GOAL_NOT_NAMED and lookup.players:
        import unicodedata, math

        def _norm(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

        named_norms = [_norm(p) for p in lookup.players]

        # P(a goal is scored at all) from totals
        from poisson import estimate_lambda_from_match_odds
        lam = estimate_lambda_from_match_odds(match_odds)
        p_any_goal = 1.0 - math.exp(-lam) if lam else 0.925  # fallback

        # Get team first-goal probs from Polymarket
        fgp = match_odds.first_goal_probs or {}
        parsed = parse_match_name(match_name)
        home_name, away_name = parsed if parsed else ("", "")

        # For each named player, estimate P(that player scores first goal).
        # = P(their team scores first) × P(player scores | team scores) × P(any goal)
        # P(player scores | team scores) ≈ player_goal_prob / sum_of_team_goal_probs
        p_named_first_total = 0.0

        if match_odds.player_props and fgp:
            # Build team goal share from anytime goalscorer props (threshold=1)
            def _team_goal_share(team_name: str) -> dict[str, float]:
                share = {}
                for (pname, mkt, line), prob in match_odds.player_props.items():
                    if mkt == "player_anytime_goalscorer" and line == 1.0:
                        share[pname] = prob
                return share

            # Get first-goal prob for each team
            home_fg = 0.0
            away_fg = 0.0
            for t, prob in fgp.items():
                if teams_match(t, home_name) or teams_match(t, match_odds.home_team):
                    home_fg = prob
                elif teams_match(t, away_name) or teams_match(t, match_odds.away_team):
                    away_fg = prob

            all_shares = _team_goal_share("")  # all players
            home_share_sum = sum(
                p for name, p in all_shares.items()
                if any(
                    w in _norm(home_name) or w in _norm(match_odds.home_team)
                    for w in name.split()
                ) or True  # we'll filter by checking both teams
            )
            # Simpler: just look up each named player's anytime goal prob directly
            for named in named_norms:
                # P(named player scores first) = P(team first goal) × P(named | team scores first)
                # P(named | team scores first) ≈ named_goal_prob / team_total_goal_prob_sum
                # But easiest: use their anytime prob as a fraction of team first-goal prob
                named_prob = match_odds.get_player_prop(named, "player_anytime_goalscorer", 1.0)
                if named_prob is not None:
                    # Determine which team first-goal prob to use
                    # Rough: P(named scores first) ≈ named_anytime_prob * P(any goal) * k
                    # where k scales so sum over team = team_first_goal_prob
                    # We approximate: P(named scores first) = named_prob * P(any goal) / mean_goals
                    # For simplicity: P(first goal by named) ≈ named_anytime_prob × (P(no goal)=0, so)
                    # Use: P(first goal by player i) = λ_i / λ_total  (competing Poisson races)
                    # λ_i ≈ -log(1 - named_prob) from anytime prob
                    # λ_total = lam (from match totals)
                    if lam and lam > 0:
                        lam_i = -math.log(1.0 - named_prob) if named_prob < 1.0 else lam
                        p_named_first_total += lam_i / lam
        else:
            # Fallback: use first_goal_probs if player is a team name match
            for named in named_norms:
                if named in fgp:
                    p_named_first_total += fgp[named] * p_any_goal

        # P(first goal not by any named player) = P(goal scored) - P(named scores first)
        p_not_named = p_any_goal - p_named_first_total
        return round(max(min(p_not_named, 0.99), 0.01), 3)

    return None


def _lookup_total_line(totals: dict[float, float] | None, line: float) -> float | None:
    if not totals:
        return None
    if line in totals:
        return totals[line]
    nearest = min(totals.keys(), key=lambda k: abs(k - line), default=None)
    if nearest is not None and abs(nearest - line) <= 0.55:
        return totals[nearest]
    return None
