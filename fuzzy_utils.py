# fuzzy_utils.py
import re
from difflib import SequenceMatcher

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)   # keep letters/digits; space everything else
    return re.sub(r"\s+", " ", s).strip()

def _compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def fuzzy_in(text: str, phrases: list[str],
             cutoff: float = 0.82, compact_cutoff: float = 0.90) -> bool:
    """Return True if `text` matches any phrase by substring or fuzzy similarity.
    - Accepts missing spaces (compact) and small typos.
    """
    t_norm = _norm(text)
    t_comp = _compact(text)
    for p in phrases:
        pn = _norm(p)
        pc = _compact(p)
        # exact-ish substring matches
        if pn and pn in t_norm:
            return True
        if pc and pc in t_comp:
            return True
        # fuzzy similarity matches
        if _ratio(t_norm, pn) >= cutoff:
            return True
        if pc and _ratio(t_comp, pc) >= compact_cutoff:
            return True
    return False

def best_command_key(text: str, command_map: dict[str, list[str]]):
    """Return (best_key, best_phrase, score) across the entire command map."""
    t_norm = _norm(text)
    t_comp = _compact(text)
    best = (None, None, 0.0)
    for key, phrases in command_map.items():
        for p in phrases:
            pn = _norm(p)
            pc = _compact(p)
            s1 = _ratio(t_norm, pn) if pn else 0.0
            s2 = _ratio(t_comp, pc) if pc else 0.0
            s = max(s1, s2)
            if s > best[2]:
                best = (key, p, s)
    return best
