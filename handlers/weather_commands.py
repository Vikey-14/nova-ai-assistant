# 📦 handlers/weather_commands.py

import re
from datetime import datetime, timedelta
import dateparser
from difflib import get_close_matches

from command_map import COMMAND_MAP
from weather_handler import get_weather, get_forecast

# ✅ Lazy import to avoid circular import
def get_utils():
    from utils import _speak_multilang, logger, selected_language
    return _speak_multilang, logger, selected_language


# 🔤 Multilingual forecast keywords
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
    "mañana", "pasado mañana", "próximo", "fin de semana", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
]


# 🧠 Extract multilingual weekdays and weekend
def extract_multiple_days(command: str):
    command_lower = command.lower()

    # 🌐 Multilingual weekday map
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
        "jueves": "thursday", "viernes": "friday", "sábado": "saturday", "domingo": "sunday"
    }

    # 🌐 Weekend terms
    weekend_words = [
        "weekend", "wochenende", "सप्ताहांत", "week-end", "fin de semana"
    ]
    if any(word in command_lower for word in weekend_words):
        today = datetime.now().weekday()
        saturday = datetime.now() + timedelta((5 - today) % 7)
        sunday = saturday + timedelta(days=1)
        return [saturday, sunday]

    # 📅 Regex to match all multilingual weekday terms
    pattern = r"(" + "|".join(re.escape(day) for day in day_map.keys()) + ")"
    matches = re.findall(pattern, command_lower)

    # 📅 Handle "next" modifiers
    base = datetime.now()
    if "next" in command_lower or "अगला" in command_lower or "nächste" in command_lower or "prochain" in command_lower or "próximo" in command_lower:
        base += timedelta(weeks=1)

    dates = []
    for match in matches:
        english_day = day_map[match]
        index = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(english_day)
        days_ahead = (index - base.weekday() + 7) % 7
        target_day = base + timedelta(days=days_ahead)
        dates.append(target_day)

    return dates if dates else None


# ✅ Main command handler for weather
def handle_weather_command(command: str):
    _speak_multilang, logger, _ = get_utils()
    command_lower = command.lower()

    # 🌦 Detect weather intent
    weather_phrases = COMMAND_MAP.get("get_weather", [])
    weather_match = any(phrase in command_lower for phrase in weather_phrases)
    forecast_match = any(keyword in command_lower for keyword in FORECAST_KEYWORDS)
    is_forecast = bool(forecast_match)

    # 🏙 Extract city (e.g., "in Mumbai" / "in बर्लिन")
    city_match = re.search(r"in ([a-zA-ZÀ-ÿ\u0900-\u097F\s]+)", command)
    city = city_match.group(1).strip() if city_match else None

    if not city:
        _speak_multilang(
            "Please specify the city to check the weather.",
            hi="कृपया उस शहर का नाम बताएं जिसका मौसम जानना है।",
            de="Bitte gib die Stadt an, für die du das Wetter wissen möchtest.",
            fr="Veuillez préciser la ville pour laquelle vous souhaitez connaître la météo.",
            es="Por favor, especifica la ciudad para consultar el clima.",
            log_command="weather_missing_city"
        )
        return

    if is_forecast:
        # 🧠 Try weekday extraction first
        days = extract_multiple_days(command)

        if days:
            for target_date in days:
                get_forecast(city_name=city, target_date=target_date, command=command)
        else:
            # 🧠 Try NLP parsing fallback (e.g., "in 3 days")
            parsed = dateparser.parse(command)
            if parsed:
                get_forecast(city_name=city, target_date=parsed, command=command)
            else:
                _speak_multilang(
                    "I couldn't understand which date you meant.",
                    hi="मैं तारीख नहीं समझ पाया। कृपया फिर से बताएं।",
                    de="Ich konnte das Datum nicht verstehen.",
                    fr="Je n’ai pas compris la date.",
                    es="No entendí qué fecha querías.",
                    log_command="forecast_date_parse_failed"
                )
    else:
        # 🌤️ Current weather
        get_weather(city_name=city, command=command)

# --- Back-compat export expected by the registry ---
handle_weather = handle_weather_command
