# 📦 handlers/weather_commands.py — SAY→SHOW + typed/voice follow-ups + Did-You-Mean (Nova casing)
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional

import dateparser
from difflib import get_close_matches

from command_map import COMMAND_MAP
from weather_handler import get_weather, get_forecast
from followup import await_followup, confirm_did_you_mean  # ← reuse existing helper
from say_show import say_show  # speak first, then show localized bubble


# ─────────────────────────────────────────────────────────────────────────────
# Lazy utils (avoid circular imports)
def _get_utils():
    from utils import logger, selected_language, listen_command
    return logger, selected_language, listen_command

def _ui_lang() -> str:
    _, selected_language, _ = _get_utils()
    return (selected_language or "en").split("-")[0].lower()

def _pick(d: dict, **fmt) -> str:
    txt = d.get(_ui_lang(), d.get("en", ""))
    try:
        return txt.format(**fmt) if fmt else txt
    except Exception:
        return txt


# ─────────────────────────────────────────────────────────────────────────────
# Multilingual texts (ALL lines localized; bubbles follow UI language)
T = {
    "ask_city": {
        "en": "Which city should I check? You can type or say it.",
        "hi": "किस शहर का मौसम देखूँ? आप टाइप कर सकते हैं या बोल सकते हैं।",
        "de": "Für welche Stadt soll ich das Wetter prüfen? Du kannst tippen oder sprechen.",
        "fr": "Pour quelle ville veux-tu la météo ? Tu peux écrire ou parler.",
        "es": "¿De qué ciudad quieres saber el clima? Puedes escribir o hablar.",
    },
    "no_city": {
        "en": "I couldn't get the city name.",
        "hi": "मैं शहर का नाम नहीं समझ पाई।",
        "de": "Ich konnte den Stadtnamen nicht verstehen.",
        "fr": "Je n’ai pas compris le nom de la ville.",
        "es": "No entendí el nombre de la ciudad.",
    },
    "no_date": {
        "en": "I couldn't understand which date you meant.",
        "hi": "मैं तारीख नहीं समझ पाई। कृपया फिर से बताएं।",
        "de": "Ich konnte das Datum nicht verstehen.",
        "fr": "Je n’ai pas compris la date.",
        "es": "No entendí qué fecha querías.",
    },
}


# 🔤 Forecast keywords (multi-lingual)
FORECAST_KEYWORDS = [
    # English
    "forecast", "tomorrow", "day after tomorrow", "next", "weekend", "in",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    # Hindi
    "कल", "परसों", "अगला", "सप्ताहांत", "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार",
    # German
    "morgen", "übermorgen", "nächste", "wochenende", "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag",
    # French
    "demain", "après-demain", "prochain", "week-end", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    # Spanish
    "mañana", "pasado mañana", "próximo", "fin de semana", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]


# 🧠 Extract multilingual weekdays/weekend → list[datetime]
def extract_multiple_days(command: str) -> Optional[List[datetime]]:
    cmd = (command or "").lower()

    day_map = {
        # English
        "monday": "monday", "tuesday": "tuesday", "wednesday": "wednesday",
        "thursday": "thursday", "friday": "friday", "saturday": "saturday", "sunday": "sunday",
        # Hindi
        "सोमवार": "monday", "मंगलवार": "tuesday", "बुधवार": "wednesday",
        "गुरुवार": "thursday", "शुक्रवार": "friday", "शनिवार": "saturday", "रविवार": "sunday",
        # German
        "montag": "monday", "dienstag": "tuesday", "mittwoch": "wednesday",
        "donnerstag": "thursday", "freitag": "friday", "samstag": "saturday", "sonntag": "sunday",
        # French
        "lundi": "monday", "mardi": "tuesday", "mercredi": "wednesday",
        "jeudi": "thursday", "vendredi": "friday", "samedi": "saturday", "dimanche": "sunday",
        # Spanish
        "lunes": "monday", "martes": "tuesday", "miércoles": "wednesday",
        "jueves": "thursday", "viernes": "friday", "sábado": "saturday", "domingo": "sunday",
    }

    # Weekend
    if any(w in cmd for w in ["weekend", "wochenende", "सप्ताहांत", "week-end", "fin de semana"]):
        today = datetime.now().weekday()
        saturday = datetime.now() + timedelta((5 - today) % 7)
        sunday = saturday + timedelta(days=1)
        return [saturday, sunday]

    pattern = r"(" + "|".join(re.escape(d) for d in day_map.keys()) + ")"
    matches = re.findall(pattern, cmd)
    if not matches:
        return None

    base = datetime.now()
    if any(w in cmd for w in ["next", "अगला", "nächste", "prochain", "próximo"]):
        base += timedelta(weeks=1)

    idx_map = {d: i for i, d in enumerate(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"])}
    dates: List[datetime] = []
    for m in matches:
        english_day = day_map[m]
        index = idx_map[english_day]
        days_ahead = (index - base.weekday() + 7) % 7
        target = base + timedelta(days=days_ahead)
        dates.append(target)

    return dates or None


# ─────────────────────────────────────────────────────────────────────────────
# Main handler
def handle_weather_command(command: str) -> None:
    logger, _, listen_command = _get_utils()
    cmd = (command or "").strip()
    cmd_low = cmd.lower()

    # Detect weather vs forecast intent
    weather_phrases = COMMAND_MAP.get("get_weather", [])
    is_weather_intent = any(p in cmd_low for p in weather_phrases)
    is_forecast = any(k in cmd_low for k in FORECAST_KEYWORDS) or ("forecast" in cmd_low or "पूर्वानुमान" in cmd_low)

    # ── Did-You-Mean for fuzzy/unclear weather requests (reuse helper)
    if not (is_weather_intent or is_forecast):
        # Try to guess closest intended phrase from your command map + common tokens
        candidates = list(set(weather_phrases + ["weather", "forecast", "show weather", "get weather"]))
        guess = get_close_matches(cmd_low, candidates, n=1, cutoff=0.55)
        if guess:
            confirmed = confirm_did_you_mean(guess[0])  # ← uses global yes/no follow-up
            if confirmed is False:
                return
            # If confirmed True (or None), proceed anyway so flow isn’t blocked

    # Extract city (supports simple "in <city>" pattern; city may be multilingual chars)
    m_city = re.search(r"\bin\s+([a-zA-ZÀ-ÿ\u0900-\u097F\s]+)$", cmd)
    city = m_city.group(1).strip() if m_city else None

    # If city missing → ASK ONCE (SAY→SHOW), then await (no re-say/show inside await)
    if not city:
        say_show(
            T["ask_city"]["en"],
            hi=T["ask_city"]["hi"],
            de=T["ask_city"]["de"],
            fr=T["ask_city"]["fr"],
            es=T["ask_city"]["es"],
            title="Nova",
        )
        answer = await_followup(
            _pick(T["ask_city"]),
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0,
        )
        city = (answer or "").strip()
        if not city:
            say_show(
                T["no_city"]["en"],
                hi=T["no_city"]["hi"],
                de=T["no_city"]["de"],
                fr=T["no_city"]["fr"],
                es=T["no_city"]["es"],
                title="Nova",
            )
            return

    # Route: forecast vs current
    if is_forecast:
        # Try explicit weekdays/weekend first
        days = extract_multiple_days(cmd)
        if days:
            for dt in days:
                try:
                    get_forecast(city_name=city, target_date=dt, command=cmd)
                except Exception as e:
                    logger.error("[weather] get_forecast failed for %s (%s): %s", city, dt, e)
            return

        # Fallback: natural language date (e.g., "in 3 days", "next Friday")
        parsed = None
        try:
            parsed = dateparser.parse(cmd, settings={"PREFER_DATES_FROM": "future"})
        except Exception:
            parsed = None

        if parsed:
            try:
                get_forecast(city_name=city, target_date=parsed, command=cmd)
            except Exception as e:
                logger.error("[weather] get_forecast failed for %s (%s): %s", city, parsed, e)
        else:
            say_show(
                T["no_date"]["en"],
                hi=T["no_date"]["hi"],
                de=T["no_date"]["de"],
                fr=T["no_date"]["fr"],
                es=T["no_date"]["es"],
                title="Nova",
            )
    else:
        # Current conditions
        try:
            get_weather(city_name=city, command=cmd)
        except Exception as e:
            logger.error("[weather] get_weather failed for %s: %s", city, e)


# Back-compat export expected by the registry
handle_weather = handle_weather_command
