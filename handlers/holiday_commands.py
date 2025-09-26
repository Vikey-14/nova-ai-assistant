# 📂 handlers/holiday_commands.py — unified with say_show helpers
import datetime
import re
from typing import Optional, Tuple, List
from difflib import SequenceMatcher

from followup import confirm_did_you_mean, await_followup   # yes/no + typed/voice follow-ups
from say_show import say_show                               # say → then show (localized bubble)
from utils import selected_language, listen_command, logger # minimal deps


# ─────────────────────────────────────────────────────────────────────────────
# Localize helpers
# ─────────────────────────────────────────────────────────────────────────────
def _lang() -> str:
    return (selected_language or "en").lower()

def _pick_lang_text(d: dict) -> str:
    return d.get(_lang(), d.get("en", ""))

# Multilingual follow-up prompts (bubble shows localized)
_PROMPTS = {
    "ask_holiday_name": {
        "en": "Which holiday are you asking about? You can type or say it.",
        "hi": "किस त्योहार के बारे में पूछ रहे हैं? आप टाइप या बोल सकते हैं।",
        "de": "Über welchen Feiertag fragst du? Du kannst tippen oder sprechen.",
        "fr": "De quel jour férié parlez-vous ? Vous pouvez écrire ou parler.",
        "es": "¿De qué feriado preguntas? Puedes escribir o hablar.",
    },
    "ask_holiday_country": {
        "en": "For which country should I check the holiday? You can type or say it.",
        "hi": "किस देश के लिए छुट्टी देखूँ? आप टाइप या बोल सकते हैं।",
        "de": "Für welches Land soll ich den Feiertag prüfen? Du kannst tippen oder sprechen.",
        "fr": "Pour quel pays dois-je vérifier le jour férié ? Vous pouvez écrire ou parler.",
        "es": "¿Para qué país debo verificar el feriado? Puedes escribir o hablar.",
    },
    "ask_holiday_year": {
        "en": "For which year?",
        "hi": "किस वर्ष के लिए?",
        "de": "Für welches Jahr?",
        "fr": "Pour quelle année ?",
        "es": "¿Para qué año?",
    },
    "didnt_get_it": {
        "en": "I couldn't get that.",
        "hi": "मैं समझ नहीं पाई।",
        "de": "Ich habe das nicht verstanden.",
        "fr": "Je n’ai pas compris.",
        "es": "No entendí eso.",
    },
}

def _say_then_show_prompt(key: str) -> str:
    """Speak in all langs (via say_show) and show the bubble in the current UI language.
    Returns the localized bubble text (handy to pass into await_followup)."""
    p = _PROMPTS[key]
    # say_show: speaks EN (and we pass localized variants) → then shows localized bubble
    say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"], title="Nova")
    return _pick_lang_text(p)


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy helpers
# ─────────────────────────────────────────────────────────────────────────────
def _best_match(candidate: str, choices: List[str]) -> Tuple[Optional[str], float]:
    cand = (candidate or "").strip()
    if not cand or not choices:
        return None, 0.0

    def _compact(s: str) -> str:
        return "".join(ch for ch in s.casefold() if ch.isalnum())

    c_norm, c_comp = cand.casefold(), _compact(cand)
    best = None
    best_score = 0.0
    for ch in choices:
        n, k = ch.casefold(), _compact(ch)
        s = max(SequenceMatcher(None, c_norm, n).ratio(),
                SequenceMatcher(None, c_comp, k).ratio())
        if s > best_score:
            best, best_score = ch, s
    return best, best_score


# ─────────────────────────────────────────────────────────────────────────────
# Country + Holiday vocab
# ─────────────────────────────────────────────────────────────────────────────
_COUNTRY_MAP = {
    # English
    "india": "IN", "in": "IN", "bharat": "IN",
    "united states": "US", "usa": "US", "us": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
    "germany": "DE", "de": "DE",
    "france": "FR", "fr": "FR",
    "spain": "ES", "es": "ES",
    # Hindi
    "भारत": "IN", "अमेरिका": "US", "जर्मनी": "DE", "फ्रांस": "FR", "स्पेन": "ES",
    # FR / DE / ES
    "allemagne": "DE", "france": "FR", "espagne": "ES", "royaume-uni": "GB", "états-unis": "US",
    "deutschland": "DE", "vereinigte staaten": "US", "vereinigtes königreich": "GB", "spanien": "ES",
    "estados unidos": "US", "reino unido": "GB", "alemania": "DE", "francia": "FR", "españa": "ES",
}

_HOLIDAY_KEYWORDS = [
    "christmas", "diwali", "eid", "new year",
    "क्रिसमस", "दिवाली", "ईद", "नया साल",
    "noël", "aïd", "nouvel an",
    "navidad", "año nuevo",
    "weihnachten", "neujahr"
]

_HOLIDAY_MAP = {
    "christmas": "Christmas Day",
    "क्रिसमस": "Christmas Day",
    "noël": "Christmas Day",
    "navidad": "Christmas Day",
    "weihnachten": "Christmas Day",

    "new year": "New Year's Day",
    "नया साल": "New Year's Day",
    "nouvel an": "New Year's Day",
    "año nuevo": "New Year's Day",
    "neujahr": "New Year's Day",

    "diwali": "Diwali",
    "दिवाली": "Diwali",

    "eid": "Eid",
    "ईद": "Eid",
}

_STATIC_FALLBACK = {
    "christmas": "December 25",
    "new year": "January 1",
    "diwali": "November 4",  # varies by lunar calendar
    "eid": "April 21",       # varies by lunar calendar
}


# ─────────────────────────────────────────────────────────────────────────────
# Slot extractors
# ─────────────────────────────────────────────────────────────────────────────
def _extract_holiday_token(command: str) -> Optional[str]:
    cmd = (command or "").strip().lower()
    # direct
    for kw in _HOLIDAY_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", cmd, flags=re.IGNORECASE):
            return kw
    # fuzzy
    best, score = _best_match(cmd, _HOLIDAY_KEYWORDS)
    if best and score >= 0.80:
        return best
    if best and 0.60 <= score < 0.80:
        ok = confirm_did_you_mean(best)
        if ok is True:
            return best
    return None

def _extract_country_code(command: str) -> Optional[str]:
    cmd = (command or "").strip().lower()
    for k, code in _COUNTRY_MAP.items():
        if re.search(rf"\b{re.escape(k)}\b", cmd, flags=re.IGNORECASE):
            return code
    best, score = _best_match(cmd, list(_COUNTRY_MAP.keys()))
    if best and score >= 0.80:
        return _COUNTRY_MAP.get(best)
    if best and 0.60 <= score < 0.80:
        ok = confirm_did_you_mean(best)
        if ok is True:
            return _COUNTRY_MAP.get(best)
    return None

def _extract_year(command: str, now: datetime.datetime) -> Optional[int]:
    cmd = (command or "").lower()
    if any(kw in cmd for kw in ["last year", "पिछला साल", "l'année dernière", "el año pasado", "letztes jahr"]):
        return now.year - 1
    if any(kw in cmd for kw in ["next year", "अगला साल", "l'année prochaine", "el próximo año", "nächstes jahr"]):
        return now.year + 1
    m = re.search(r"\b(20\d{2}|19\d{2})\b", cmd)
    if m:
        return int(m.group(1))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main handler
# ─────────────────────────────────────────────────────────────────────────────
def handle_holiday_queries(command: str) -> None:
    """
    Answers “When is <holiday>?” with:
      • say→then→show prompts (localized bubbles) using say_show
      • typed OR voice follow-ups via await_followup
      • “Did you mean …?” confirmation for fuzzy matches
      • holidays package when available, static fallback otherwise
    """
    now = datetime.datetime.now()
    cmd = (command or "").strip()

    # Try extracting from the initial utterance
    holiday_tok = _extract_holiday_token(cmd)
    country_code = _extract_country_code(cmd)
    year = _extract_year(cmd, now)

    # 1) Ask for missing holiday
    if not holiday_tok:
        prompt = _say_then_show_prompt("ask_holiday_name")
        ans = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,  # don't re-speak; we already did say→show
            show_fn=lambda *_a, **_k: None,   # don't re-show; bubble is already up
            listen_fn=listen_command,
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not ans:
            p = _PROMPTS["didnt_get_it"]; say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
            return
        holiday_tok = _extract_holiday_token(ans)
        if not holiday_tok:
            say_show(
                "Sorry, I couldn't understand the holiday.",
                hi="माफ़ करें, मैं त्योहार समझ नहीं पाई।",
                fr="Désolé, je n’ai pas compris le jour férié.",
                es="Lo siento, no entendí el feriado.",
                de="Entschuldigung, ich habe den Feiertag nicht verstanden."
            )
            return

    # 2) Ask for country if missing
    if not country_code:
        prompt = _say_then_show_prompt("ask_holiday_country")
        ans = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not ans:
            p = _PROMPTS["didnt_get_it"]; say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
            return
        country_code = _extract_country_code(ans)
        if not country_code:
            # Default to India if still unclear — tell the user (localized)
            say_show(
                "I couldn't recognize the country, so I'll check for India.",
                hi="देश पहचान नहीं पाई, इसलिए मैं भारत के लिए जाँच करूँगी।",
                fr="Je n’ai pas reconnu le pays, je vais donc vérifier pour l’Inde.",
                es="No reconocí el país, así que revisaré para India.",
                de="Ich konnte das Land nicht erkennen, daher prüfe ich für Indien."
            )
            country_code = "IN"

    # 3) Ask for year if missing
    if year is None:
        prompt = _say_then_show_prompt("ask_holiday_year")
        ans = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not ans:
            p = _PROMPTS["didnt_get_it"]; say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
            return
        try:
            m = re.search(r"\b(20\d{2}|19\d{2})\b", ans)
            year = int(m.group(1)) if m else now.year
        except Exception:
            year = now.year

    # Resolve to English holiday name for lookup
    eng_name = _HOLIDAY_MAP.get(holiday_tok, (holiday_tok or "").title())

    # 4) Try `holidays` package
    try:
        import holidays as _hol
        try:
            country_holidays = _hol.CountryHoliday(country_code, years=year)
        except Exception:
            country_holidays = None
            logger.warning(f"Holiday Query: unsupported country code '{country_code}', falling back to static")
    except ImportError:
        country_holidays = None

    date_of_holiday = None
    if country_holidays:
        for date, name in country_holidays.items():
            nlow = str(name or "").lower()
            if eng_name.lower() == nlow or eng_name.lower() in nlow:
                date_of_holiday = date
                break

    # 5) Static fallback (with lunar disclaimer where relevant)
    if not date_of_holiday:
        static_key = holiday_tok if holiday_tok in _STATIC_FALLBACK else (holiday_tok or "").split()[0]
        static_date = _STATIC_FALLBACK.get(static_key)
        if static_date:
            say_show(
                f"{eng_name} is usually on {static_date}. Exact date varies each year.",
                hi=f"{eng_name} आमतौर पर {static_date} को होता है। सही तारीख हर साल बदलती है।",
                fr=f"{eng_name} a généralement lieu le {static_date}. La date exacte varie chaque année.",
                es=f"{eng_name} suele ser el {static_date}. La fecha exacta varía cada año.",
                de=f"{eng_name} ist gewöhnlich am {static_date}. Das genaue Datum variiert jedes Jahr."
            )
            return
        else:
            say_show(
                "Sorry, I don't have information about that holiday.",
                hi="माफ़ करें, मेरे पास उस छुट्टी की जानकारी नहीं है।",
                fr="Désolé, je n'ai pas d'informations sur ce jour férié.",
                es="Lo siento, no tengo información sobre ese feriado.",
                de="Entschuldigung, ich habe keine Informationen zu diesem Feiertag."
            )
            return

    # 6) Speak + show result
    try:
        if hasattr(date_of_holiday, "year") and date_of_holiday.year != year:
            date_of_holiday = date_of_holiday.replace(year=year)
    except Exception:
        pass

    try:
        date_str = date_of_holiday.strftime("%B %d, %Y")
    except Exception:
        date_str = f"{date_of_holiday}"

    say_show(
        f"{eng_name} is on {date_str}.",
        hi=f"{eng_name} {date_str} को है।",
        fr=f"{eng_name} est le {date_str}.",
        es=f"{eng_name} es el {date_str}.",
        de=f"{eng_name} ist am {date_str}."
    )
