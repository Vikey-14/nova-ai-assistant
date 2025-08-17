# -*- coding: utf-8 -*-
# intents.py
#
# Centralized phrase patterns + parsers used across voice and text paths.
# Import from here instead of re-defining in multiple files.

from difflib import SequenceMatcher
import re

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
# Change-language intent
# -------------------------------
CHANGE_LANG_PATTERNS = [
    "change language", "switch language", "set language", "language change",
    "भाषा बदलो", "भाषा बदलें", "भाषा बदल",
    "sprache ändern", "sprache aendern",
    "changer la langue", "changer langue",
    "cambiar el idioma", "cambia idioma",
]

def said_change_language(text: str) -> bool:
    """True if the text asks to change language (contains or fuzzy ~0.75)."""
    t = (text or "").lower().strip()
    if not t:
        return False
    for p in CHANGE_LANG_PATTERNS:
        if p in t:
            return True
    return any(_similar(t, p) >= 0.75 for p in CHANGE_LANG_PATTERNS)

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
