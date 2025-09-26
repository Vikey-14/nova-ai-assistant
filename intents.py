# -*- coding: utf-8 -*-
# intents.py
#
# Centralized phrase patterns + parsers used across voice and text paths.
# Import from here instead of re-defining in multiple files.

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata

# ✨ NEW: fuzzy helper for intent matching
from fuzzy_utils import fuzzy_in

# -------------------------------
# Supported languages + aliases
# -------------------------------
SUPPORTED_LANGS = {"en", "hi", "de", "fr", "es"}

LANG_ALIASES = {
    "en": ["english", "inglish", "anglais", "inglés", "englisch", "angrezi"],
    "hi": ["hindi", "hindee", "हिंदी", "hindustani", "indi", "hindhi"],
    "de": ["german", "deutsch", "doych", "jermaan", "aleman", "allemand"],
    "fr": ["french", "francais", "français", "fransay", "fransae"],
    "es": ["spanish", "espanol", "español", "espanyol", "espaniol"],
}

def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()

def best_alias_match(text: str, alias_map: dict, threshold: float = 0.72):
    t = (text or "").lower().strip()
    if not t:
        return None, 0.0
    # direct containment wins
    for code, words in alias_map.items():
        for w in words:
            wl = w.lower()
            if wl in t or t in wl:
                return code, 1.0
    # fuzzy fallback
    best_code, best_score = None, 0.0
    for code, words in alias_map.items():
        for w in words:
            s = _similar(t, w.lower())
            if s > best_score:
                best_code, best_score = code, s
    return (best_code, best_score) if best_score >= threshold else (None, 0.0)

def guess_language_code(utterance: str) -> str | None:
    code, _ = best_alias_match(utterance, LANG_ALIASES, threshold=0.72)
    return code

# -------------------------------
# Shared, localized language prompts (used by main & wake)
# -------------------------------

# Localized display names of languages, per UI language
_LANGUAGE_DISPLAY_NAMES = {
    "en": {"en": "English", "hi": "Hindi", "de": "German", "fr": "French", "es": "Spanish"},
    "hi": {"en": "अंग्रेज़ी", "hi": "हिन्दी", "de": "जर्मन", "fr": "फ़्रेंच", "es": "स्पैनिश"},
    "de": {"en": "Englisch", "hi": "Hindi", "de": "Deutsch", "fr": "Französisch", "es": "Spanisch"},
    "fr": {"en": "anglais", "hi": "hindi", "de": "allemand", "fr": "français", "es": "espagnol"},
    "es": {"en": "inglés", "hi": "hindi", "de": "alemán", "fr": "francés", "es": "español"},
}
# Localized "or"
_OR_WORD = {"en": "or", "hi": "या", "de": "oder", "fr": "ou", "es": "o"}

def _join_with_or(words: list[str], conj: str) -> str:
    words = [w for w in words if w]
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    if len(words) == 2:
        return f"{words[0]} {conj} {words[1]}"
    return f"{', '.join(words[:-1])}, {conj} {words[-1]}"

def _build_language_list_for(ui_lang: str) -> str:
    order = ["en", "hi", "de", "fr", "es"]
    names = [_LANGUAGE_DISPLAY_NAMES.get(ui_lang, _LANGUAGE_DISPLAY_NAMES["en"])[code] for code in order]
    conj = _OR_WORD.get(ui_lang, "or")
    return _join_with_or(names, conj)

def _get_display_name(ui_lang: str, lang_code: str) -> str:
    return _LANGUAGE_DISPLAY_NAMES.get(ui_lang, _LANGUAGE_DISPLAY_NAMES["en"]).get(
        lang_code, _LANGUAGE_DISPLAY_NAMES["en"].get(lang_code, "English")
    )

def get_language_prompt_text(ui_lang: str) -> str:
    """Exact same wording as the first-boot language prompt in main.py."""
    return {
        "en": f"Please tell me the language you'd like to use to communicate with me: {_build_language_list_for('en')}.",
        "hi": f"कृपया बताइए, आप मुझसे किस भाषा में बात करना चाहेंगे: {_build_language_list_for('hi')}?",
        "de": f"Bitte sag mir, in welcher Sprache du mit mir sprechen möchtest: {_build_language_list_for('de')}.",
        "fr": f"Dis-moi dans quelle langue tu veux parler avec moi : {_build_language_list_for('fr')}.",
        "es": f"Dime en qué idioma quieres hablar conmigo: {_build_language_list_for('es')}.",
    }.get(ui_lang, f"Please tell me the language you'd like to use to communicate with me: {_build_language_list_for('en')}.")


def get_invalid_language_voice_retry(ui: str) -> str:
    lines = {
        "en": "I didn’t recognize that language. Please say or type a supported language (English, Hindi, French, German, or Spanish).",
        "hi": "मैं उस भाषा को पहचान नहीं पाई। कृपया कोई समर्थित भाषा बोलें या टाइप करें (अंग्रेज़ी, हिन्दी, फ़्रेंच, जर्मन या स्पैनिश)।",
        "de": "Diese Sprache habe ich nicht erkannt. Bitte sag oder tippe eine unterstützte Sprache (Englisch, Hindi, Französisch, Deutsch oder Spanisch).",
        "fr": "Je n’ai pas reconnu cette langue. Dis ou tape une langue prise en charge (anglais, hindi, français, allemand ou espagnol).",
        "es": "No reconocí ese idioma. Di o escribe un idioma compatible (inglés, hindi, francés, alemán o español).",
    }
    return lines.get((ui or "en").lower(), lines["en"])

# Spoken invalid → jump to typing (localized, mentions the chatbox)
_INVALID_LANGUAGE_VOICE_TO_TYPED = {
    "en": "Please provide a valid language below in the chatbox provided, such as English, Hindi, German, French, or Spanish.",
    "hi": "कृपया नीचे दिए गए चैट बॉक्स में एक मान्य भाषा बताइए, जैसे अंग्रेज़ी, हिन्दी, जर्मन, फ़्रेंच या स्पैनिश।",
    "de": "Bitte gib unten im Chatfeld eine gültige Sprache an, z. B. Englisch, Hindi, Deutsch, Französisch oder Spanisch.",
    "fr": "Veuillez indiquer ci-dessous dans la boîte de discussion une langue valide, par exemple l’anglais, le hindi, l’allemand, le français ou l’espagnol.",
    "es": "Indica a continuación en el cuadro de chat un idioma válido, por ejemplo inglés, hindi, alemán, francés o español.",
}
def get_invalid_language_voice_to_typed(ui_lang: str) -> str:
    return _INVALID_LANGUAGE_VOICE_TO_TYPED.get(ui_lang, _INVALID_LANGUAGE_VOICE_TO_TYPED["en"])

# Typed-path invalid language (localized; wording = "enter")
_INVALID_LANGUAGE_TYPED_LINE = {
    "en": "Please enter a valid language such as English, Hindi, German, French, or Spanish.",
    "hi": "कृपया एक मान्य भाषा दर्ज करें, जैसे अंग्रेज़ी, हिन्दी, जर्मन, फ़्रेंच या स्पैनिश।",
    "de": "Bitte gib eine gültige Sprache ein, zum Beispiel Englisch, Hindi, Deutsch, Französisch oder Spanisch.",
    "fr": "Veuillez saisir une langue valide, par exemple l’anglais, le hindi, l’allemand, le français ou l’espagnol.",
    "es": "Introduce un idioma válido, por ejemplo inglés, hindi, alemán, francés o español.",
}
def get_invalid_language_line_typed(ui_lang: str) -> str:
    return _INVALID_LANGUAGE_TYPED_LINE.get(ui_lang, _INVALID_LANGUAGE_TYPED_LINE["en"])

def get_language_already_set_line(lang_code: str, ui_lang: str) -> str:
    """
    Localized: "<Lang> is already set. Please choose a different language."
    <Lang> will be rendered in the UI language (e.g., 'हिन्दी' when ui_lang='hi').
    """
    lang_name = _get_display_name(ui_lang, lang_code)
    templates = {
        "en": f"{lang_name} is already set. Please choose a different language.",
        "hi": f"{lang_name} पहले से चयनित है। कृपया कोई अन्य भाषा चुनें।",
        "de": f"{lang_name} ist bereits eingestellt. Bitte wähle eine andere Sprache.",
        "fr": f"{lang_name} est déjà sélectionnée. Veuillez choisir une autre langue.",
        "es": f"{lang_name} ya está seleccionada. Por favor elige otro idioma.",
    }
    return templates.get(ui_lang, templates["en"])

# -------------------------------
# Change-language intent (robust + multilingual)
# -------------------------------
# Keep a basic list for backwards compatibility (may be used elsewhere)
CHANGE_LANG_PATTERNS = [
    "change language", "switch language", "set language", "language change",
    "भाषा बदलो", "भाषा बदलें", "भाषा बदल",
    "sprache ändern", "sprache aendern",
    "changer la langue", "changer langue",
    "cambiar el idioma", "cambia idioma",
]

# Build a vocabulary of language words from your existing LANG_ALIASES
_ALL_LANG_WORDS = sorted({w.lower() for lst in LANG_ALIASES.values() for w in lst})
_LANG_WORDS_RE = r"(?:%s)" % "|".join(map(re.escape, _ALL_LANG_WORDS))

# Regex patterns covering EN/HI/DE/FR/ES and "change/switch to <language>" forms
_CHANGE_LANG_PATTERNS = [
    # --- English ---
    r"\b(?:change|switch|set|update|modify)\s+(?:the\s+)?language\b",
    r"\blanguage\s+(?:change|switch|setting|settings)\b",
    rf"\b(?:change|switch|set|update)\s+(?:the\s+)?(?:language\s+)?(?:to|into)\s+{_LANG_WORDS_RE}\b",
    rf"\b(?:switch|change)\s+to\s+{_LANG_WORDS_RE}\b",

    # --- Hindi / Hinglish ---
    r"\b(भाषा|bhasha)\s*(bad(lo|ल[ोए])|badal[^\s]*)\b",
    r"\b(भाषा|bhasha)\s*badal\s*(do|dijiye)?\b",

    # --- German ---
    r"\b(sprache)\s*(ändern|wechseln|umstellen)\b",
    rf"\bauf\s+{_LANG_WORDS_RE}\s*(wechseln)?\b",

    # --- French ---
    r"\b(langue)\s*(changer|modifier|basculer)\b",
    rf"\bpass(?:er)?\s+en\s+{_LANG_WORDS_RE}\b",

    # --- Spanish ---
    r"\b(idioma)\s*(cambiar|modificar)\b",
    rf"\bcambiar\s+(?:a|al)\s+{_LANG_WORDS_RE}\b",
]
_CHANGE_LANG_RE = re.compile("|".join(f"(?:{p})" for p in _CHANGE_LANG_PATTERNS), re.I | re.U)

# ✨ NEW: common typo normalization for the change-language intent
_COMMON_REPLACEMENTS = {
    "chnage": "change",
    "chagne": "change",
    "chaneg": "change",
    "langauge": "language",
    "languaeg": "language",
    "lanaguage": "language",
    "languge": "language",
    "langugage": "language",
    "lang": "language",  # short-hand to help "switch lang", "set lang"
}
def _fix_common_typos(s: str) -> str:
    t = (s or "").lower()
    for bad, good in _COMMON_REPLACEMENTS.items():
        t = t.replace(bad, good)
    return t

# ✨ NEW: fuzzy phrases for tolerant matching
_FUZZY_CHANGE_LANG_PHRASES = [
    "change language",
    "switch language",
    "set language",
    "language change",
    "change lang",
    "switch lang",
    "set lang",
]

def said_change_language(text: str) -> bool:
    """True if the user is asking to change the app language."""
    if not text:
        return False

    # 1) Normalize common misspellings and spacing
    t = _fix_common_typos(text.strip().lower())

    # 2) Fuzzy first: handles minor typos and joined words (e.g., 'changelanguage')
    #    cutoff ~0.72 matches small mistakes; compact_cutoff keeps very-tight joins strict
    if fuzzy_in(t, _FUZZY_CHANGE_LANG_PHRASES, cutoff=0.72, compact_cutoff=0.90):
        return True

    # 3) Existing fast paths
    if "change language" in t or "switch language" in t:
        return True

    if _CHANGE_LANG_RE.search(t):
        return True

    # 4) Heuristic: change/switch verb + any known language token anywhere
    verb_hints = (
        "change", "switch", "set", "update", "modify",
        "भाषा", "bhasha", "sprache", "langue", "idioma",
        "cambiar", "changer", "ändern", "wechseln",
        "language",  # include noun to help after normalization
    )
    if any(v in t for v in verb_hints):
        for w in _ALL_LANG_WORDS:
            if w in t:
                return True
    return False

# -------------------------------
# Curiosity / fun content intents
# -------------------------------
TELL_ME_TRIGGERS = {
    "en": ["tell me something", "say something", "entertain me", "do something fun", "give me something", "say anything"],
    "hi": ["मुझे कुछ बताओ", "कुछ कहो", "मुझे हंसाओ", "कुछ मजेदार करो", "कुछ सुनाओ", "कुछ भी कहो"],
    "fr": ["dis-moi quelque chose", "dis quelque chose", "divertis-moi", "fais quelque chose de drôle", "donne-moi quelque chose", "dis n'importe quoi"],
    "de": ["erzähl mir etwas", "sag etwas", "unterhalte mich", "mach etwas lustiges", "gib mir etwas", "sag irgendwas"],
    "es": ["dime algo", "di algo", "entreténme", "haz algo divertido", "dame algo", "di cualquier cosa"]
}

# Keep this dict for backward compatibility / other modules.
POSITIVE_RESPONSES = {
    "en": ["yes", "yes please", "sure", "go ahead", "alright", "let’s do it", "okay", "yeah", "ok please"],
    "hi": ["हाँ", "हाँ कृपया", "ठीक है", "आगे बढ़ो", "चलो करते हैं", "ठीक", "हाँ बिल्कुल"],
    "fr": ["oui", "oui s'il vous plaît", "d'accord", "vas-y", "allons-y", "ok", "ouais"],
    "de": ["ja", "ja bitte", "sicher", "mach weiter", "in ordnung", "ok", "klar"],
    "es": ["sí", "sí por favor", "claro", "adelante", "vamos a hacerlo", "ok", "sí claro"]
}

# 📋 Curiosity menu per language
CURIOSITY_MENU = {
    "en": "Would you like…\n• A deep life insight?\n• A fun fact?\n• A joke?\n• A cosmic riddle or quote?\n• A line from a witty poem?",
    "hi": "क्या आप चाहेंगे…\n• जीवन का कोई गहरा विचार?\n• एक मजेदार तथ्य?\n• एक चुटकुला?\n• कोई रहस्यमय पहेली या उद्धरण?\n• एक मजेदार कविता की पंक्ति?",
    "fr": "Voulez-vous…\n• Une réflexion profonde sur la vie ?\n• Un fait amusant ?\n• Une blague ?\n• Une énigme ou citation cosmique ?\n• Une ligne d'un poème drôle ?",
    "de": "Möchten Sie…\n• Eine tiefgründige Lebensweisheit?\n• Eine interessante Tatsache?\n• Einen Witz?\n• Ein kosmisches Rätsel oder Zitat?\n• Eine Zeile aus einem witzigen Gedicht?",
    "es": "¿Le gustaría…\n• Una profunda reflexión sobre la vida?\n• Un dato curioso?\n• Un chiste?\n• Un acertijo o cita cósmica?\n• Una línea de un poema gracioso?"
}

CURIOSITY_FOLLOWUP_ALIASES = {
    "english": {
        "tell me more", "another one", "give me another", "more please",
        "one more", "again", "hit me again", "tell another", "next one",
        "next please", "something else", "more facts", "another fact",
        "more jokes", "one more joke", "give me one more", "go again",
        "keep going", "keep them coming"
    },
    "hindi": {
        "और बताओ", "एक और", "मुझे एक और दो", "और चाहिए",
        "फिर से", "दोबारा", "एक और सुनाओ", "कुछ और", "अगला",
        "और तथ्य", "एक और तथ्य", "एक और चुटकुला", "दोबरा सुनाओ"
    },
    "french": {
        "dis m'en plus", "encore un", "donne-moi un autre", "plus s'il te plaît",
        "un de plus", "encore", "raconte-en un autre", "quelque chose d'autre",
        "prochain", "plus de faits", "un autre fait", "plus de blagues",
        "une autre blague", "continue", "vas-y encore"
    },
    "german": {
        "erzähl mir mehr", "noch eins", "gib mir noch eins", "mehr bitte",
        "eins mehr", "nochmal", "erzähl noch eins", "etwas anderes",
        "nächstes", "mehr fakten", "ein weiterer fakt", "mehr witze",
        "noch ein witz", "mach weiter", "weiter so"
    },
    "spanish": {
        "cuéntame más", "otro más", "dame otro", "más por favor",
        "uno más", "de nuevo", "cuenta otro", "algo más", "siguiente",
        "más datos", "otro dato", "más chistes", "otro chiste",
        "continúa", "sigue así"
    }
}

LANG_CODE_TO_ALIAS = {"en": "english", "hi": "hindi", "fr": "french", "de": "german", "es": "spanish"}
LANG_CODE_TO_FULL  = {"en": "english", "hi": "hindi", "fr": "french", "de": "german", "es": "spanish"}

def is_followup_text(text: str, lang_code: str) -> bool:
    alias_key = LANG_CODE_TO_ALIAS.get(lang_code, "english")
    aliases = CURIOSITY_FOLLOWUP_ALIASES.get(alias_key, set())
    t = (text or "").lower().strip()
    if t in aliases:
        return True
    return any(a in t for a in aliases)

def parse_category_from_choice(choice_text: str, lang_code: str):
    t = (choice_text or "").lower().strip()
    if any(s in t for s in ["fun fact", "मजेदार तथ्य", "fait amusant", "interessante tatsache", "dato curioso"]):
        return "fun_facts"
    if any(s in t for s in ["joke", "चुटकुला", "blague", "witz", "chiste"]):
        return "jokes"
    if any(s in t for s in ["deep insight", "deep life insight", "विचार", "जीवन", "réflexion", "lebensweisheit", "reflexión"]):
        return "deep_life_insight"
    if any(s in t for s in ["riddle", "quote", "पहेली", "उद्धरण", "énigme", "citation", "rätsel", "zitat", "acertijo", "cita", "cosmic"]):
        return "cosmic_riddles_or_quotes"
    if any(s in t for s in ["poem", "कविता", "poème", "gedicht", "poema"]):
        return "witty_poems"
    return None

# =====================================================================
# YES / NO understanding (robust + multilingual + typed-friendly)
# =====================================================================

def _clean(s: str) -> str:
    """
    Normalize, strip punctuation (keep letters/numbers/underscore/space), casefold.
    This makes typed and transcribed inputs behave the same.
    """
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE)
    return s.casefold().strip()

# Flatten positive phrases (from dict) for matching
_POS_FLAT = frozenset(
    _clean(p)
    for vals in (POSITIVE_RESPONSES.values() if isinstance(POSITIVE_RESPONSES, dict) else [POSITIVE_RESPONSES])
    for p in vals
)

# Broader multilingual yes/no vocabulary (includes typed aliases)
YES_WORDS = {
    # EN
    "yes","y","yeah","yep","yup","sure","ok","okay","affirmative","correct","thats right","right","roger","absolutely","indeed","true",
    # HI (transliterations + Devanagari)
    "haan","haan ji","ha","ji haan","bilkul","thik hai","ठीक है","हाँ","जी हाँ","हाँजी",
    # DE
    "ja","genau","richtig","stimmt",
    # FR
    "oui","daccord","exact","juste",
    # ES
    "si","sí","claro","vale","correcto",
}
NO_WORDS = {
    # EN
    "no","n","nope","nah","negative","cancel","stop","dont","do not","not really","incorrect","thats wrong","wrong","no thanks","no thank you","never","no way",
    # HI
    "nahin","nahi","bilkul nahin","गलत","नहीं",
    # DE
    "nein","nicht","auf keinen fall","falsch",
    # FR
    "non","pas vraiment","faux",
    # ES
    "no","para nada","incorrecto","de ninguna manera",
}

# Build cleaned sets for fast matching
_YES_CLEAN = frozenset(_clean(w) for w in (YES_WORDS | _POS_FLAT))
_NO_CLEAN  = frozenset(_clean(w) for w in NO_WORDS)

def _contains_any_clean(text: str, vocab: frozenset[str]) -> bool:
    t = _clean(text)
    if not t:
        return False
    if t in vocab:
        return True
    # word-boundary containment
    for w in vocab:
        if not w:
            continue
        if re.search(rf"\b{re.escape(w)}\b", t):
            return True
    return False

def is_yes(text: str) -> bool:
    if _contains_any_clean(text, _YES_CLEAN):
        return True
    # heuristic fallback (keeps it tight to minimize false positives)
    t = _clean(text)
    return bool(re.search(r"\b(yes|yeah|yup|ok|okay|sure|correct|right|affirmative|ja|oui|si|sí|vale|claro|bilkul|हाँ)\b", t))

def is_no(text: str) -> bool:
    if _contains_any_clean(text, _NO_CLEAN):
        return True
    # heuristic fallback (tight)
    t = _clean(text)
    return bool(re.search(r"\b(no|nope|nah|incorrect|wrong|nein|non|नहीं)\b", t))

# -------------------------------
# Name commands / extraction
# -------------------------------

# Accept typed commands like: "my name is Vikey", "call me Vikey", "i am Vikey", "i'm Vikey"
def parse_typed_name_command(text: str) -> str | None:
    if not text:
        return None
    m = re.search(
        r"(?:my\s+name\s+is|call\s+me|i\s*am|i['’]m)\s+(?P<n>.+)$",
        text, flags=re.IGNORECASE
    )
    return (m.group("n").strip()) if m else None

# Helper: join “spelled out” letters like “v i k e y” or “v-i-k-e-y”
def _squash_spelled_letters(s: str) -> str:
    s2 = re.sub(r"[-‐-–—·•\s]+", " ", s.strip())  # normalize separators to spaces
    parts = [p for p in s2.split() if p]
    if parts and all(len(p) == 1 and p.isalpha() for p in parts):
        return "".join(parts)
    return s.strip()

# Extract a *candidate* name from free-form corrections:
# e.g., "no, it's Vikey", "actually call me Vikey", "V I K E Y", "my name is Vikey Sharma"
def extract_name_freeform(text: str) -> str | None:
    if not text:
        return None
    original = text.strip()

    # Common grammars -> group 'n'
    patterns = [
        r"(?:my\s+name\s+is|call\s+me|i\s*am|i['’]m|it['’]?s|it\s+is|name\s+is)\s+(?P<n>[^,.;!?0-9]{1,60})",
        r"^(?:no[:,]?\s*)?(?:it['’]?s|it\s+is|just)\s+(?P<n>[^,.;!?0-9]{1,60})$",
        r"^(?P<n>[A-Za-z][A-Za-z'’\- ]{0,58})$",  # bare name only
    ]
    n = None
    for pat in patterns:
        m = re.search(pat, original, flags=re.IGNORECASE)
        if m:
            n = m.group("n")
            break
    if not n:
        return None

    # Clean up quotes/punctuation + handle spelled-out letters
    n = n.strip().strip(",.;:!?'\"()[]{}")
    n = _squash_spelled_letters(n)

    # Trim trailing fix-phrases like "is correct/right"
    n = re.sub(r"\b(is\s+)?(correct|right)\b\.?$", "", n, flags=re.IGNORECASE).strip()

    # Keep at most first 3 words that look like a name (letters or allowed punct)
    tokens = [t for t in re.split(r"\s+", n) if t]
    good = []
    for t in tokens:
        if re.fullmatch(r"[A-Za-z][A-Za-z'’\-]*", t):
            good.append(t)
        else:
            # stop on junk like numbers
            break
        if len(good) >= 3:
            break
    if not good:
        return None

    # Title-case ASCII names
    try:
        if all(ord(c) < 128 for c in " ".join(good)):
            good = [p.capitalize() for p in good]
    except Exception:
        pass

    return " ".join(good)

# Parse a confirmation/correction reply for the previously heard name.
# Returns (state, name_or_none) where state is one of:
#   "confirm"   -> user agreed the previous_name is correct
#   "deny"      -> user denied and did not supply a new name
#   "corrected" -> user supplied a replacement name (returned in slot 2)
#   "ambiguous" -> couldn’t decide
def parse_confirmation_or_name(utterance: str, previous_name: str | None = None) -> tuple[str, str | None]:
    t_raw = (utterance or "").strip()
    if not t_raw:
        return "ambiguous", None

    # Primary: explicit yes/no
    if is_yes(t_raw):
        return "confirm", previous_name

    # Candidate extraction (covers "no, it's Vikey" and bare-name like "Vikey")
    candidate = extract_name_freeform(t_raw) or parse_typed_name_command(t_raw)

    # If they denied AND gave a name → corrected
    if is_no(t_raw) and candidate:
        return "corrected", candidate

    # If candidate differs from previous, treat as correction
    if candidate and previous_name and candidate.lower() != (previous_name or "").lower():
        return "corrected", candidate

    # Pure deny without a new name
    if is_no(t_raw):
        return "deny", None

    # No explicit yes/no, but a clean candidate name → corrected
    if candidate:
        return "corrected", candidate

    return "ambiguous", None
