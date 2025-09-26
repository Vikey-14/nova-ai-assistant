# 📂 handlers/date_commands.py — SAY→SHOW + typed/voice follow-ups + barge-in + multilingual

import datetime
import calendar
import re
from difflib import get_close_matches
from typing import Optional, Tuple, List

# Optional: natural language parsing for "next friday", "26/01/1950", etc.
try:
    import dateparser
except Exception:
    dateparser = None

# ─────────────────────────────────────────────────────────────────────────────
# Lazy utils (avoid circulars)
def _lazy_utils():
    from utils import listen_command, logger, selected_language
    from followup import await_followup
    return listen_command, logger, selected_language, await_followup

# SAY→SHOW helper (centralized; picks current UI language & shows bubble)
from say_show import say_show

def _pick_lang_text(msg_map: dict[str, str]) -> str:
    lang = (_lazy_utils()[2] or "en").lower()
    return msg_map.get(lang) or msg_map.get("en") or next(iter(msg_map.values()), "")

# ─────────────────────────────────────────────────────────────────────────────
# Multilingual follow-up prompts (SAY in current locale via say_show; we also
# return the localized text to use as the prompt string passed to await_followup)
_PROMPTS = {
    "ask_date_kind": {
        "en": "Do you want the current date, time, month, or a specific date? You can type or say it.",
        "hi": "क्या आप वर्तमान तारीख, समय, महीना या कोई विशेष तारीख जानना चाहते हैं? आप टाइप करें या बोलें।",
        "de": "Möchtest du das aktuelle Datum, die Zeit, den Monat oder ein bestimmtes Datum? Du kannst tippen oder sprechen.",
        "fr": "Souhaitez-vous la date du jour, l’heure, le mois, ou une date précise ? Vous pouvez écrire ou parler.",
        "es": "¿Quieres la fecha actual, la hora, el mes o una fecha específica? Puedes escribir o hablar.",
    },
    "ask_specific_date": {
        "en": "Tell me the date you want (e.g., 26 Jan 1950 or next Friday). You can type or say it.",
        "hi": "वह तारीख बताइए जो आप चाहते हैं (जैसे 26 Jan 1950 या अगला शुक्रवार)। आप टाइप करें या बोलें।",
        "de": "Sag mir das Datum (z. B. 26 Jan 1950 oder nächsten Freitag). Du kannst tippen oder sprechen.",
        "fr": "Dites-moi la date souhaitée (ex. 26 jan 1950 ou vendredi prochain). Vous pouvez écrire ou parler.",
        "es": "Dime la fecha (p. ej., 26 Ene 1950 o el próximo viernes). Puedes escribir o hablar.",
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
    p = _PROMPTS[key]
    # Speak + bubble (localized) once:
    say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
    # Return the localized text for await_followup’s prompt string:
    return _pick_lang_text(p)

# ─────────────────────────────────────────────────────────────────────────────
# Matching helpers
def fuzzy_match_any(command: str, phrase_list: List[str], cutoff=0.7) -> bool:
    matches = get_close_matches(command, phrase_list, n=1, cutoff=cutoff)
    return len(matches) > 0

def contains_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)

# Keyword sets for sub-intents / quick follow-ups
TIME_KWS       = ["time", "समय", "heure", "hora", "uhr"]
MONTH_KWS      = ["month", "महीना", "mois", "mes", "monat"]
TODAY_KWS      = ["today", "date", "aujourd'hui", "hoy", "heute", "आज", "तारीख"]
YESTERDAY_KWS  = ["yesterday", "hier", "ayer", "gestern"]
TOMORROW_KWS   = ["tomorrow", "demain", "mañana", "morgen"]

# ─────────────────────────────────────────────────────────────────────────────
def _respond_time(now: datetime.datetime):
    time_str = now.strftime("%H:%M")
    say_show(
        f"The current time is {time_str}.",
        hi=f"वर्तमान समय है {time_str}।",
        fr=f"L'heure actuelle est {time_str}.",
        es=f"La hora actual es {time_str}.",
        de=f"Die aktuelle Uhrzeit ist {time_str}."
    )

def _respond_month(now: datetime.datetime):
    month_name = now.strftime("%B")
    say_show(
        f"The current month is {month_name}.",
        hi=f"वर्तमान महीना {month_name} है।",
        fr=f"Le mois en cours est {month_name}.",
        es=f"El mes actual es {month_name}.",
        de=f"Der aktuelle Monat ist {month_name}."
    )

def _respond_today(now: datetime.datetime):
    weekday = calendar.day_name[now.weekday()]
    date_str = now.strftime("%B %d, %Y")
    say_show(
        f"Today is {weekday}, {date_str}.",
        hi=f"आज {weekday} है, तारीख {date_str} है।",
        fr=f"Aujourd'hui, c'est {weekday}, le {date_str}.",
        es=f"Hoy es {weekday}, {date_str}.",
        de=f"Heute ist {weekday}, der {date_str}."
    )

def _respond_relative(now: datetime.datetime, delta_days: int, label_en: str):
    target = (now + datetime.timedelta(days=delta_days)).date()
    weekday = calendar.day_name[target.weekday()]
    date_str = target.strftime("%B %d, %Y")
    en = f"{label_en} is {weekday}, {date_str}." if delta_days >= 0 else f"{label_en} was {weekday}, {date_str}."
    say_show(
        en,
        hi=f"{'कल' if delta_days in (-1, 1) else label_en} {weekday}, {date_str} " + ("होगा।" if delta_days >= 0 else "था।"),
        fr=f"{'Demain' if delta_days == 1 else ('Hier' if delta_days == -1 else label_en)} " +
           (f"est {weekday}, {date_str}." if delta_days >= 0 else f"était {weekday}, {date_str}."),
        es=f"{'Mañana' if delta_days == 1 else ('Ayer' if delta_days == -1 else label_en)} " +
           (f"es {weekday}, {date_str}." if delta_days >= 0 else f"fue {weekday}, {date_str}."),
        de=f"{'Morgen' if delta_days == 1 else ('Gestern' if delta_days == -1 else label_en)} " +
           (f"ist {weekday}, {date_str}." if delta_days >= 0 else f"war {weekday}, {date_str}.")
    )

def _try_parse_specific_date(text: str) -> Tuple[bool, str]:
    """
    Try to parse a specific date from free text and return (ok, response_text).
    Accepts '26 Jan 1950', '26/01/1950', 'next friday', etc. (if dateparser present).
    """
    _, logger, _, _ = _lazy_utils()
    if not text:
        return False, ""
    text = text.strip()

    prefer_future = bool(re.search(r"\b(next|tomorrow|mañana|demain|morgen|अगला|कल)\b", text, re.I))
    if dateparser:
        dt = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future" if prefer_future else "past"})
        if dt:
            try:
                date_obj = dt.date()
                weekday = calendar.day_name[date_obj.weekday()]
                today = datetime.date.today()
                if date_obj >= today:
                    resp = f"{date_obj.strftime('%B %d, %Y')} will be a {weekday}."
                else:
                    resp = f"{date_obj.strftime('%B %d, %Y')} was a {weekday}."
                logger.info(f"DateParser success: '{text}' -> {resp}")
                return True, resp
            except Exception:
                pass

    # Numeric format: DD/MM/YYYY or MM/DD/YYYY — try both interpretations
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
    if m:
        d1, d2, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        for day, month in [(d1, d2), (d2, d1)]:
            try:
                date_obj = datetime.date(y, month, day)
                weekday = calendar.day_name[date_obj.weekday()]
                today = datetime.date.today()
                if date_obj >= today:
                    return True, f"{date_obj.strftime('%B %d, %Y')} will be a {weekday}."
                else:
                    return True, f"{date_obj.strftime('%B %d, %Y')} was a {weekday}."
            except ValueError:
                continue

    return False, ""

# ─────────────────────────────────────────────────────────────────────────────
# Leap-year helpers (using Python's correct 100/400 rules via calendar.isleap)
def _next_leap_year(from_year: int) -> int:
    y = from_year + 1
    while not calendar.isleap(y):
        y += 1
    return y

def _last_leap_year(from_year: int) -> int:
    y = from_year - 1
    while not calendar.isleap(y):
        y -= 1
    return y

# ─────────────────────────────────────────────────────────────────────────────
def handle_date_queries(command: str) -> None:
    """
    Answers:
      • Current date/time/month
      • Leap year queries
      • Specific date → weekday (regex & dateparser)
      • Ambiguous → follow-ups (typed/voice) with SAY→SHOW + barge-in
      • Quick 'yesterday' / 'tomorrow'
    """
    command = (command or "")
    lower_cmd = command.lower()
    listen_command, logger, _, await_followup = _lazy_utils()

    # Quick routes
    now = datetime.datetime.now()
    if contains_any(lower_cmd, TIME_KWS):
        logger.info(f"Date Quick (Time): '{command}'"); _respond_time(now); return
    if contains_any(lower_cmd, MONTH_KWS):
        logger.info(f"Date Quick (Month): '{command}'"); _respond_month(now); return
    if contains_any(lower_cmd, TODAY_KWS):
        logger.info(f"Date Quick (Today): '{command}'"); _respond_today(now); return
    if contains_any(lower_cmd, YESTERDAY_KWS):
        logger.info(f"Date Quick (Yesterday): '{command}'"); _respond_relative(now, -1, "Yesterday"); return
    if contains_any(lower_cmd, TOMORROW_KWS):
        logger.info(f"Date Quick (Tomorrow): '{command}'"); _respond_relative(now, +1, "Tomorrow"); return

    # Fuzzy “what is date/time/month…”
    date_phrases = [
        "what is the date", "what day is it", "what day is today", "what's the date today", "today's date",
        "what is the time", "current time", "time now", "what month is it", "which month is it",
        "आज तारीख क्या है", "आज कौन सा दिन है", "तारीख बताओ", "समय क्या है", "वर्तमान समय", "समय अभी क्या है",
        "कौन सा महीना है", "महीना कौन सा है",
        "quelle est la date", "quel jour sommes-nous", "quelle est la date aujourd'hui", "quelle heure est-il",
        "quel mois sommes-nous", "quel est le mois",
        "cuál es la fecha", "qué día es hoy", "cuál es la fecha hoy", "qué hora es",
        "qué mes es", "cuál es el mes",
        "was ist das datum", "welcher tag ist heute", "was ist das heutige datum", "wie spät ist es",
        "welcher monat ist es", "was ist der monat"
    ]
    if fuzzy_match_any(lower_cmd, date_phrases):
        if contains_any(lower_cmd, TIME_KWS):
            logger.info(f"Date Query (Time): '{command}'"); _respond_time(now); return
        elif contains_any(lower_cmd, MONTH_KWS):
            logger.info(f"Date Query (Month): '{command}'"); _respond_month(now); return
        else:
            logger.info(f"Date Query (Date): '{command}'"); _respond_today(now); return

    # Leap year
    leap_phrases = [
        "is this year a leap year", "when is the next leap year", "which year is a leap year",
        "when was the last leap year",
        "क्या यह वर्ष लीप वर्ष है", "अगला लीप वर्ष कब है", "पिछला लीप वर्ष कब था",
        "est-ce que c'est une année bissextile", "quand est la prochaine année bissextile", "quelle était la dernière année bissextile",
        "es este año bisiesto", "cuándo es el próximo año bisiesto", "cuándo fue el último año bisiesto",
        "ist dieses jahr ein schaltjahr", "wann ist das nächste schaltjahr", "wann war das letzte schaltjahr"
    ]
    if fuzzy_match_any(lower_cmd, leap_phrases) or contains_any(lower_cmd, ["leap year", "bissextile", "bisiesto", "schaltjahr"]):
        year = now.year
        if contains_any(lower_cmd, ["next", "prochaine", "próximo", "nächste", "अगला"]):
            nl = _next_leap_year(year)
            say_show(
                f"The next leap year is {nl}.",
                hi=f"अगला लीप वर्ष {nl} है।",
                fr=f"L'année bissextile suivante est {nl}.",
                es=f"El próximo año bisiesto es {nl}.",
                de=f"Das nächste Schaltjahr ist {nl}."
            ); return
        elif contains_any(lower_cmd, ["last", "dernière", "último", "letzte", "पिछला"]):
            ll = _last_leap_year(year)
            say_show(
                f"The last leap year was {ll}.",
                hi=f"पिछला लीप वर्ष {ll} था।",
                fr=f"La dernière année bissextile était {ll}.",
                es=f"El último año bisiesto fue {ll}.",
                de=f"Das letzte Schaltjahr war {ll}."
            ); return
        else:
            is_leap = calendar.isleap(year)
            say_show(
                f"This year {year} is " + ("a leap year." if is_leap else "not a leap year."),
                hi=f"यह वर्ष {year} {'लीप वर्ष है।' if is_leap else 'लीप वर्ष नहीं है।'}",
                fr=f"Cette année {year} est {'bissextile.' if is_leap else 'pas bissextile.'}",
                es=f"Este año {year} {'es bisiesto.' if is_leap else 'no es bisiesto.'}",
                de=f"Dieses Jahr {year} ist {'ein Schaltjahr.' if is_leap else 'kein Schaltjahr.'}"
            ); return

    # Explicit “what/which day was/is …”
    date_regex = r"(?:what|which)\s+day\s+(?:was|is)\s+(\d{1,2})\s?(?:st|nd|rd|th)?\s?([a-zA-Z]+)\s?,?\s?(\d{4})"
    match = re.search(date_regex, command, re.I)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)
        year = int(match.group(3))
        try:
            try:
                month = datetime.datetime.strptime(month_str, "%B").month
            except ValueError:
                month = datetime.datetime.strptime(month_str, "%b").month
            date_obj = datetime.date(year, month, day)
            weekday = calendar.day_name[date_obj.weekday()]
            today = datetime.date.today()
            if date_obj >= today:
                response = f"{month_str.capitalize()} {day}, {year} will be a {weekday}."
            else:
                response = f"{month_str.capitalize()} {day}, {year} was a {weekday}."
            say_show(
                response,
                hi=f"{year} का {month_str.capitalize()} {day} दिन {weekday} " + ("होगा।" if date_obj >= today else "था।"),
                fr=f"Le {day} {month_str.capitalize()} {year} " + (f"sera un {weekday}." if date_obj >= today else f"était un {weekday}."),
                es=f"El {day} de {month_str.capitalize()} de {year} " + (f"será {weekday}." if date_obj >= today else f"fue {weekday}."),
                de=f"Der {day}. {month_str.capitalize()} {year} " + (f"wird ein {weekday} sein." if date_obj >= today else f"war ein {weekday}.")
            ); return
        except ValueError:
            _, logger, _, _ = _lazy_utils()
            logger.error(f"Date Query: Invalid date {day}-{month_str}-{year} in '{command}'")
            p = _PROMPTS["didnt_get_it"]
            say_show(
                "That date is invalid. Please check and try again.",
                hi="यह तारीख अमान्य है। कृपया जांचें और पुनः प्रयास करें।",
                fr="Cette date est invalide. Veuillez vérifier et réessayer.",
                es="Esa fecha no es válida. Por favor, verifique e intente de nuevo.",
                de="Dieses Datum ist ungültig. Bitte überprüfen Sie es und versuchen Sie es erneut."
            ); return

    # Try to parse a specific date from free text
    ok, resp = _try_parse_specific_date(lower_cmd)
    if ok:
        say_show(resp); return

    # ── Follow-up 1: ask what they want (SAY→SHOW), then await (no re-speak/show inside await)
    prompt = _say_then_show_prompt("ask_date_kind")
    ans = await_followup(
        prompt,
        speak_fn=lambda *_a, **_k: None,      # do NOT re-say (barge-in safe)
        show_fn=lambda *_a, **_k: None,       # no duplicate bubble
        listen_fn=listen_command,
        allow_typed=True,
        allow_voice=True,
        timeout=18.0
    )
    if not ans:
        p = _PROMPTS["didnt_get_it"]
        say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
        return

    ans_low = (ans or "").lower()
    now = datetime.datetime.now()

    # Interpret follow-up
    if contains_any(ans_low, TIME_KWS):       _respond_time(now); return
    if contains_any(ans_low, MONTH_KWS):      _respond_month(now); return
    if contains_any(ans_low, TODAY_KWS):      _respond_today(now); return
    if contains_any(ans_low, YESTERDAY_KWS):  _respond_relative(now, -1, "Yesterday"); return
    if contains_any(ans_low, TOMORROW_KWS):   _respond_relative(now, +1, "Tomorrow"); return

    ok, resp = _try_parse_specific_date(ans)
    if ok:
        say_show(resp); return

    # ── Follow-up 2: ask for the specific date (SAY→SHOW), then await (no re-say/show)
    prompt2 = _say_then_show_prompt("ask_specific_date")
    ans2 = await_followup(
        prompt2,
        speak_fn=lambda *_a, **_k: None,
        show_fn=lambda *_a, **_k: None,
        listen_fn=listen_command,
        allow_typed=True,
        allow_voice=True,
        timeout=18.0
    )
    if not ans2:
        p = _PROMPTS["didnt_get_it"]
        say_show(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
        return

    ok, resp = _try_parse_specific_date(ans2)
    if ok:
        say_show(resp); return

    # Fallback
    say_show(
        "Sorry, I couldn't understand your date query. Please try rephrasing.",
        hi="माफ़ करें, मैं आपकी तारीख पूछताछ समझ नहीं पाया। कृपया पुनः प्रयास करें।",
        fr="Désolé, je n'ai pas compris votre question sur la date. Veuillez reformuler.",
        es="Lo siento, no entendí su consulta de fecha. Por favor reformule.",
        de="Entschuldigung, ich habe Ihre Datumsanfrage nicht verstanden. Bitte formulieren Sie es neu."
    )

# ─────────────────────────────────────────────────────────────────────────────
# (Optional) Router helpers
def is_date_command(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ["date", "time", "month", "leap year", "bissextile", "bisiesto", "schaltjahr"])
