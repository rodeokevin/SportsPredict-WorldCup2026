"""Normalize team names between SportsPredict and external odds feeds."""

from __future__ import annotations

import re
import unicodedata


# SportsPredict / FIFA names → common bookmaker names
ALIASES: dict[str, str] = {
    # Standard variations
    "turkiye": "turkey",
    "turkey": "turkey",
    "usa": "united states",
    "united states": "united states",
    "korea republic": "south korea",
    "south korea": "south korea",
    "korea dpr": "north korea",
    "north korea": "north korea",
    "cabo verde": "cape verde",
    "cape verde": "cape verde",
    "cabo": "cape verde",
    "cpv": "cape verde",
    "ivory coast": "ivory coast",
    "cote d'ivoire": "ivory coast",
    "dr congo": "dr congo",
    "democratic republic of the congo": "dr congo",
    "congo dr": "dr congo",
    "scotland": "scotland",
    "england": "england",
    "netherlands": "netherlands",
    "holland": "netherlands",
    
    # FIFA 3-letter country codes (World Cup teams)
    "arg": "argentina",
    "aut": "austria",
    "aus": "australia",
    "bih": "bosnia and herzegovina",
    "bel": "belgium",
    "bra": "brazil",
    "bgr": "bulgaria",
    "can": "canada",
    "cro": "croatia",
    "cyp": "cyprus",
    "cze": "czech republic",
    "den": "denmark",
    "ecu": "ecuador",
    "eng": "england",
    "esp": "spain",
    "est": "estonia",
    "fin": "finland",
    "fra": "france",
    "geo": "georgia",
    "deu": "germany",
    "gre": "greece",
    "hun": "hungary",
    "isl": "iceland",
    "ind": "india",
    "irl": "ireland",
    "ita": "italy",
    "jpn": "japan",
    "khm": "cambodia",
    "kor": "south korea",
    "lbn": "lebanon",
    "ltu": "lithuania",
    "mex": "mexico",
    "mar": "morocco",
    "nld": "netherlands",
    "nzl": "new zealand",
    "nor": "norway",
    "per": "peru",
    "pol": "poland",
    "prt": "portugal",
    "rou": "romania",
    "rus": "russia",
    "sgp": "singapore",
    "srb": "serbia",
    "svk": "slovakia",
    "svn": "slovenia",
    "swe": "sweden",
    "sui": "switzerland",
    "tha": "thailand",
    "tur": "turkey",
    "ukr": "ukraine",
    "ury": "uruguay",
    "viet": "vietnam",
    "wls": "wales",
    "zaf": "south africa",
    # Common abbreviations for African teams
    "alg": "algeria",
    "egy": "egypt",
    "gha": "ghana",
    "col": "colombia",
    "rsa": "south africa",
    # FIFA 3-letter codes that differ from the existing aliases above
    "por": "portugal",
    "cro": "croatia",
    "ger": "germany",
    "ned": "netherlands",
    "swi": "switzerland",
    "sco": "scotland",
    "wal": "wales",
    "ire": "ireland",
    "mne": "montenegro",
    "srb": "serbia",
    "bih": "bosnia and herzegovina",
    "mkd": "north macedonia",
    "alb": "albania",
    "kos": "kosovo",
    "arm": "armenia",
    "aze": "azerbaijan",
    "bel": "belgium",
    "lux": "luxembourg",
    "pan": "panama",
    "usa": "united states",
    "mex": "mexico",
    "arg": "argentina",
    "bra": "brazil",
    "uru": "uruguay",
    "chi": "chile",
    "par": "paraguay",
    "bol": "bolivia",
    "ven": "venezuela",
    "ecu": "ecuador",
    "col": "colombia",
    "pen": "peru",
    "ksa": "saudi arabia",
    "uae": "united arab emirates",
    "qat": "qatar",
    "irn": "iran",
    "irq": "iraq",
    "jor": "jordan",
    "syr": "syria",
    "yem": "yemen",
    "cmr": "cameroon",
    "nga": "nigeria",
    "sen": "senegal",
    "mar": "morocco",
    "tun": "tunisia",
    "egy": "egypt",
    "rsa": "south africa",
    "zim": "zimbabwe",
    "ken": "kenya",
    "eth": "ethiopia",
    "uga": "uganda",
    "tan": "tanzania",
    "mli": "mali",
    "ben": "benin",
    "tgo": "togo",
    "bfa": "burkina faso",
    "civ": "ivory coast",
    "lib": "liberia",
    "gnb": "guinea-bissau",
    "gui": "guinea",
    "slv": "el salvador",
    "gtm": "guatemala",
    "hnd": "honduras",
    "cri": "costa rica",
    "jam": "jamaica",
    "tto": "trinidad and tobago",
    "cub": "cuba",
    "dom": "dominican republic",
    "hat": "haiti",
}


def normalize_team(name: str) -> str:
    """Lowercase, strip accents/punctuation for fuzzy matching."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ALIASES.get(text, text)


def teams_match(a: str, b: str) -> bool:
    na, nb = normalize_team(a), normalize_team(b)
    if na == nb:
        return True
    # Word-boundary containment: all words of the shorter name must appear
    # as whole words in the longer name. This prevents "iran" matching "ukraine".
    words_a = set(na.split())
    words_b = set(nb.split())
    if len(words_a) <= len(words_b):
        return words_a.issubset(words_b)
    return words_b.issubset(words_a)


def parse_match_name(match_name: str) -> tuple[str, str] | None:
    """Parse 'Mexico vs South Africa' into (home, away) team names."""
    for sep in (" vs ", " v ", " - "):
        if sep in match_name.lower():
            parts = re.split(re.escape(sep), match_name, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
    return None
