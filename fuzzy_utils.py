# fuzzy_utils.py
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Core normalization helpers
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy membership & best-match search
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# Match classifier (use to decide if you should ask “Did you mean …?”)
# ─────────────────────────────────────────────────────────────────────────────

def classify_best_command(
    text: str,
    command_map: Dict[str, List[str]],
    strong_cutoff: float = 0.88,
    ask_cutoff: float = 0.74,
    short_relax: float = 0.02
) -> Tuple[Optional[str], Optional[str], float, str]:
    """
    Returns (best_key, best_phrase, score, decision)

    decision ∈ {"accept", "ask", "reject"}
      - "accept": score >= strong_cutoff         → auto-run (e.g., minor typos like "electrik")
      - "ask":    ask_cutoff ≤ score < strong    → ask “Did you mean ___?”
      - "reject": score < ask_cutoff             → unrecognized; fall back to help

    For very short inputs, we relax both cutoffs slightly by `short_relax`.
    """
    key, phrase, score = best_command_key(text, command_map)

    if phrase:
        # short phrase relaxation (e.g., "list", "help", "team")
        short = max(len(_norm(text)), len(_norm(phrase))) <= 6
        if short:
            strong_cutoff = max(0.0, strong_cutoff - short_relax)
            ask_cutoff = max(0.0, ask_cutoff - short_relax)

    if score >= strong_cutoff:
        decision = "accept"
    elif score >= ask_cutoff:
        decision = "ask"
    else:
        decision = "reject"

    return key, phrase, score, decision

def is_confident_match(score: float, strong_cutoff: float = 0.88) -> bool:
    return score >= strong_cutoff

def should_ask_confirmation(score: float, strong_cutoff: float = 0.88, ask_cutoff: float = 0.74) -> bool:
    return ask_cutoff <= score < strong_cutoff

def is_reject(score: float, ask_cutoff: float = 0.74) -> bool:
    return score < ask_cutoff

# ─────────────────────────────────────────────────────────────────────────────
# Multilingual yes/no normalization (EN, HI, FR, DE, ES)
# ─────────────────────────────────────────────────────────────────────────────

_YES_WORDS = {
    "en": [
        "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay", "alright",
        "affirmative", "correct", "do it", "please do", "go ahead", "proceed"
    ],
    "hi": [
        "हाँ", "हां", "जी", "ठीक है",
        "haan", "han", "haanji", "hanji", "theek hai"
    ],
    "fr": [
        "oui", "ouais", "d'accord", "ok", "okay", "c'est bon", "vas-y", "allez", "faites-le"
    ],
    "de": [
        "ja", "jep", "jo", "klar", "okay", "ok", "mach das", "leg los", "bitte", "in ordnung"
    ],
    "es": [
        "sí", "si", "claro", "vale", "ok", "okay", "de acuerdo", "hazlo", "adelante", "procede", "proceda"
    ],
}

_NO_WORDS = {
    "en": ["no", "n", "nope", "nah", "don’t", "dont", "do not", "stop", "cancel", "negative"],
    "hi": ["नहीं", "नहि", "मत", "रुकें", "न करो", "नहीं करना", "रद्द"],
    "fr": ["non", "pas", "ne fais pas", "annule", "arrête", "stop"],
    "de": ["nein", "nee", "nicht", "mach nicht", "abbrechen", "stopp", "halt"],
    "es": ["no", "nope", "no lo hagas", "detente", "para", "cancela", "anula"]
}

def _any_match(tokens: List[str], hay: str) -> bool:
    """Check if any token/phrase from `tokens` appears as a whole word or clean substring in normalized `hay`."""
    for t in tokens:
        t_norm = _norm(t)
        if not t_norm:
            continue
        # word boundary or clear space boundaries
        if re.search(rf"(?:^|\b|\s){re.escape(t_norm)}(?:$|\b|\s)", hay):
            return True
    return False

def normalize_yes_no(text: str, lang: Optional[str] = None) -> Optional[bool]:
    """
    Multilingual yes/no detector.
    - Uses the same normalization as other fuzzy helpers (accent-/case-insensitive).
    - If `lang` is provided ('en'|'hi'|'fr'|'de'|'es'), it checks that language first.
    - Falls back to cross-language scan to catch mixed inputs.
    - Returns True (yes) / False (no) / None (unclear).
    """
    if not text:
        return None

    s = _norm(text)

    def check_sets(yes_words: List[str], no_words: List[str]) -> Optional[bool]:
        yes_hit = _any_match(yes_words, s)
        no_hit  = _any_match(no_words,  s)
        if yes_hit and not no_hit:
            return True
        if no_hit and not yes_hit:
            return False
        return None

    # 1) Prefer the specified language if given
    if lang in _YES_WORDS and lang in _NO_WORDS:
        res = check_sets(_YES_WORDS[lang], _NO_WORDS[lang])
        if res is not None:
            return res

    # 2) Cross-language sweep
    yes_found = False
    no_found  = False
    for l in ("en", "hi", "fr", "de", "es"):
        res = check_sets(_YES_WORDS[l], _NO_WORDS[l])
        if res is True:
            yes_found = True
        elif res is False:
            no_found = True

    if yes_found and not no_found:
        return True
    if no_found and not yes_found:
        return False

    # 3) Heuristic for one-word affirmatives like "ok", "vale", "ja"
    if len(s.split()) == 1 and s in { _norm(w) for l in _YES_WORDS for w in _YES_WORDS[l] }:
        return True

    return None
