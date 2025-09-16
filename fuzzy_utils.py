# fuzzy_utils.py
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional

def _strip_accents(s: str) -> str:
    """
    Remove diacritics (é -> e) but keep non-Latin scripts (e.g., Devanagari) intact.
    """
    # NFKD splits accents from base characters; drop combining marks.
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

def _norm(s: str) -> str:
    """
    Unicode-aware normalization:
      - casefold (better than lower for Unicode)
      - strip accents (Pokémon -> Pokemon)
      - replace non-word chars with spaces
      - collapse whitespace
    Keeps Hindi/Devanagari etc. so they can be matched fuzzily too.
    """
    s = _strip_accents(s).casefold()
    s = re.sub(r"\W+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()

def _compact(s: str) -> str:
    """
    Compact form: letters+digits only across ALL scripts (handles missing spaces).
    """
    s = _strip_accents(s).casefold()
    return "".join(ch for ch in s if ch.isalnum())

def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def fuzzy_in(text: str, phrases: List[str],
             cutoff: float = 0.82, compact_cutoff: float = 0.90) -> bool:
    """
    True if `text` matches any phrase by substring or fuzzy similarity.
    - Unicode-safe (Hindi, accented chars).
    - Accepts missing spaces via compact compare.
    - Tolerates small typos (SequenceMatcher).
    """
    t_norm = _norm(text)
    t_comp = _compact(text)

    for p in phrases:
        pn = _norm(p)
        pc = _compact(p)

        # Fast substring checks
        if pn and pn in t_norm:
            return True
        if pc and pc in t_comp:
            return True

        # Slightly relax thresholds for very short commands
        short = max(len(pn), len(t_norm)) <= 10
        c1 = cutoff - (0.06 if short else 0.0)
        c2 = compact_cutoff - (0.06 if short else 0.0)

        # Fuzzy similarity
        if pn and _ratio(t_norm, pn) >= c1:
            return True
        if pc and _ratio(t_comp, pc) >= c2:
            return True
    return False

def best_command_key(text: str, command_map: Dict[str, List[str]]) -> Tuple[Optional[str], Optional[str], float]:
    """
    Return (best_key, best_phrase, score) across the entire command map.
    Uses the higher of normalized/compact similarity.
    """
    t_norm = _norm(text)
    t_comp = _compact(text)

    best_key: Optional[str] = None
    best_phrase: Optional[str] = None
    best_score: float = 0.0

    for key, phrases in command_map.items():
        for p in phrases:
            pn = _norm(p)
            pc = _compact(p)
            s1 = _ratio(t_norm, pn) if pn else 0.0
            s2 = _ratio(t_comp, pc) if pc else 0.0
            s = max(s1, s2)
            if s > best_score:
                best_key, best_phrase, best_score = key, p, s

    return best_key, best_phrase, best_score
