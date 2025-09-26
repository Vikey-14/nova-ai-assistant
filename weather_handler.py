# 📦 weather_handler.py — SAY→SHOW everywhere + typed/voice follow-ups

from __future__ import annotations

import os
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

from say_show import say_show  # speak first, then show localized bubble

# 🌐 Load environment variables for BYO-key fallback
load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()

# 🔁 Lazy utils (your existing pattern)
def get_utils():
    from utils import selected_language, logger, speak, listen_command
    return selected_language, logger, speak, listen_command


# ─────────────────────────────────────────────────────────────────────────────
# Relay helpers (Managed Services)
# ─────────────────────────────────────────────────────────────────────────────
def _relay_conf():
    """
    Reads relay settings from generated settings.json:
      - use_managed_services: bool
      - relay_base_url: str
      - relay_token: str
    """
    try:
        from utils import load_settings
        s = load_settings()
    except Exception:
        s = {}
    base = (s.get("relay_base_url") or "").rstrip("/")
    token = s.get("relay_token") or ""
    use = bool(s.get("use_managed_services")) and bool(base)
    return use, base, token

def _relay_get(path: str, params: dict, timeout_s: float = 8.0):
    """
    Calls the relay if enabled. Returns JSON dict on success, or None on any failure.
    """
    use, base, token = _relay_conf()
    if not use or not base:
        return None
    try:
        r = requests.get(
            f"{base}{path}",
            params=params,
            headers=({"X-Nova-Key": token} if token else {}),
            timeout=timeout_s
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Core utilities
# ─────────────────────────────────────────────────────────────────────────────
def to_fahrenheit(celsius: float) -> float:
    return round((celsius * 9 / 5) + 32, 1)

def wants_fahrenheit(command: str) -> bool:
    c = (command or "").lower()
    return any(w in c for w in ["fahrenheit", "f-degrees", "in f", "°f", "fahrenheit please"])

def _ui_lang() -> str:
    selected_language, *_ = get_utils()
    return (selected_language or "en").split("-")[0].lower()


# 🧠 Ask for city if not provided (typed OR voice; SAY→SHOW; localized)
def get_city_if_missing(city_name: str) -> str:
    if city_name and city_name.strip() and city_name.lower() != "none":
        return city_name

    selected_language, _, speak, listen_command = get_utils()
    lang = (selected_language or "en").split("-")[0].lower()
    prompts = {
        "en": "Which city should I check? You can type or say it.",
        "hi": "किस शहर का मौसम देखूँ? आप टाइप कर सकते हैं या बोल सकते हैं।",
        "de": "Für welche Stadt soll ich das Wetter prüfen? Du kannst tippen oder sprechen.",
        "fr": "Pour quelle ville veux-tu la météo ? Tu peux écrire ou parler.",
        "es": "¿De qué ciudad quieres saber el clima? Puedes escribir o hablar.",
    }
    prompt_txt = prompts.get(lang, prompts["en"])

    # SAY→SHOW
    say_show(
        prompts["en"], hi=prompts["hi"], de=prompts["de"], fr=prompts["fr"], es=prompts["es"],
        title="Nova",
    )

    try:
        from followup import await_followup
        # suppress re-say/re-show inside await
        city = await_followup(
            prompt_txt,
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0
        )
        city = (city or "").strip()
    except Exception:
        # Minimal fallback
        try:
            speak(prompt_txt)
            city = (listen_command() or "").strip()
        except Exception:
            city = ""

    if not city:
        say_show(
            "I couldn't get the city name.",
            hi="मैं शहर का नाम नहीं समझ पाई।",
            de="Ich konnte den Stadtnamen nicht verstehen.",
            fr="Je n’ai pas compris le nom de la ville.",
            es="No entendí el nombre de la ciudad.",
            title="Nova",
        )
        return "Delhi"  # last-resort fallback to keep UX moving

    return city


# ─────────────────────────────────────────────────────────────────────────────
# ✅ CURRENT WEATHER (Relay → fallback to direct OpenWeather)
# ─────────────────────────────────────────────────────────────────────────────
def get_weather(city_name=None, command: str = ""):
    selected_language, logger, *_ = get_utils()
    city_name = get_city_if_missing(city_name)

    data = None

    # 1) Managed relay
    rel = _relay_get("/weather", {"city": city_name, "units": "metric"}, timeout_s=8.0)
    if rel is not None:
        data = rel
    else:
        # 2) Direct call (client key)
        if not API_KEY:
            say_show(
                f"Weather service is unavailable right now for {city_name}.",
                hi=f"{city_name} के लिए मौसम सेवा अभी उपलब्ध नहीं है।",
                de=f"Der Wetterdienst ist derzeit für {city_name} nicht verfügbar.",
                fr=f"Le service météo n’est pas disponible pour {city_name} pour le moment.",
                es=f"El servicio del clima no está disponible para {city_name} en este momento.",
                title="Nova",
            )
            return
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            resp = requests.get(url, params={"q": city_name, "appid": API_KEY, "units": "metric"}, timeout=8)
            data = resp.json()
        except Exception as e:
            logger.error(f"[weather] direct fetch failed: {e}")
            say_show(
                "Failed to fetch weather. Please try again later.",
                hi="मौसम नहीं मिल पाया। कृपया बाद में प्रयास करें।",
                de="Ich konnte das Wetter leider nicht abrufen.",
                fr="Je n’ai pas pu récupérer la météo.",
                es="No he podido obtener el clima.",
                title="Nova",
            )
            return

    # Parse and respond
    try:
        if data.get("cod") not in (200, "200"):
            say_show(
                f"Could not find weather for {city_name}",
                hi=f"{city_name} का मौसम नहीं मिला",
                de=f"Ich konnte das Wetter für {city_name} nicht finden.",
                fr=f"Je n’ai pas pu trouver la météo pour {city_name}.",
                es=f"No he podido encontrar el clima para {city_name}.",
                title="Nova",
            )
            return

        weather = data["weather"][0]["description"].capitalize()
        temp_c = data["main"]["temp"]
        city = data.get("name") or city_name

        if wants_fahrenheit(command):
            temp = to_fahrenheit(temp_c)
            unit = "°F"
        else:
            temp = temp_c
            unit = "°C"

        # SAY→SHOW (build per-language lines with variables baked in)
        say_show(
            f"The weather in {city} is {weather} with a temperature of {temp}{unit}.",
            hi=f"{city} का मौसम {weather} है, तापमान {temp}{unit} है।",
            de=f"Das Wetter in {city} ist {weather}, bei {temp}{unit}.",
            fr=f"Le temps à {city} est {weather}, avec une température de {temp}{unit}.",
            es=f"El clima en {city} es {weather} con una temperatura de {temp}{unit}.",
            title="Nova",
        )
        logger.info(f"🌤️ Weather | {city}: {weather}, {temp}{unit}")

    except Exception as e:
        logger.error(f"[weather] parse failed: {e}")
        say_show(
            "Failed to process the weather data. Please try again later.",
            hi="मौसम डेटा संसाधित नहीं हो पाया। कृपया बाद में प्रयास करें।",
            de="Die Wetterdaten konnten nicht verarbeitet werden.",
            fr="Impossible de traiter les données météo.",
            es="No se pudieron procesar los datos del clima.",
            title="Nova",
        )


# ─────────────────────────────────────────────────────────────────────────────
# ✅ FORECAST (Relay → fallback to direct OpenWeather 5-day/3-hour)
# ─────────────────────────────────────────────────────────────────────────────
def get_forecast(city_name=None, target_date=None, command: str = ""):
    selected_language, logger, *_ = get_utils()
    city_name = get_city_if_missing(city_name)
    if not target_date:
        return

    data = None

    # 1) Relay
    rel = _relay_get("/forecast", {"city": city_name, "units": "metric"}, timeout_s=12.0)
    if rel is not None and isinstance(rel, dict) and rel.get("list"):
        data = rel
    else:
        # 2) Direct
        if not API_KEY:
            say_show(
                f"Forecast service is unavailable right now for {city_name}.",
                hi=f"{city_name} के लिए पूर्वानुमान सेवा अभी उपलब्ध नहीं है।",
                de=f"Der Vorhersagedienst ist derzeit für {city_name} nicht verfügbar.",
                fr=f"Le service de prévision n’est pas disponible pour {city_name} pour le moment.",
                es=f"El servicio de pronóstico no está disponible para {city_name} en este momento.",
                title="Nova",
            )
            return
        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            resp = requests.get(url, params={"q": city_name, "appid": API_KEY, "units": "metric"}, timeout=12)
            data = resp.json()
        except Exception as e:
            logger.error(f"[forecast] direct fetch failed: {e}")
            say_show(
                "Could not get the forecast. Please try again.",
                hi="मौसम पूर्वानुमान नहीं मिल पाया।",
                de="Ich konnte den Wetterbericht nicht abrufen. Bitte versuche es erneut.",
                fr="Je n’ai pas pu récupérer les prévisions météo. Veuillez réessayer.",
                es="No he podido obtener el pronóstico. Por favor, intenta de nuevo.",
                title="Nova",
            )
            return

    try:
        if data.get("cod") not in (200, "200"):
            say_show(
                f"Could not find forecast for {city_name}",
                hi=f"{city_name} का पूर्वानुमान नहीं मिला",
                de=f"Ich konnte die Vorhersage für {city_name} nicht finden.",
                fr=f"Je n’ai pas pu trouver la prévision météo pour {city_name}.",
                es=f"No he podido encontrar el pronóstico para {city_name}.",
                title="Nova",
            )
            return

        forecast_list = data.get("list", [])
        cmd = (command or "").lower()

        multi_day = any(k in cmd for k in [
            "next week", "7 days", "entire week", "full week", "whole week", "weekend forecast", "full forecast"
        ])
        weekend_request = any(k in cmd for k in ["next weekend", "weekend forecast", "saturday and sunday"])

        if multi_day or weekend_request:
            today = datetime.now().date()
            daily = {}

            for entry in forecast_list:
                date_str = entry["dt_txt"].split(" ")[0]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (date_obj - today).days > 6:
                    continue
                daily.setdefault(date_obj, []).append(entry)

            # Build a simple multiline summary
            lines = [f"📆 Forecast for {city_name}:"]
            for date_obj, entries in daily.items():
                if weekend_request and date_obj.weekday() not in (5, 6):
                    continue
                mid = next((e for e in entries if "12:00:00" in e["dt_txt"]), entries[len(entries)//2])
                desc = mid["weather"][0]["description"].capitalize()
                temp_c = mid["main"]["temp"]
                if wants_fahrenheit(command):
                    temp = to_fahrenheit(temp_c); unit = "°F"
                else:
                    temp = temp_c; unit = "°C"
                lines.append(f"• {date_obj.strftime('%A')}: {desc}, around {temp}{unit}")

            msg_en = "\n".join(lines)
            # Keep the same content for other languages (contents are neutral/city+temps)
            say_show(
                msg_en,
                hi=msg_en, de=msg_en, fr=msg_en, es=msg_en,
                title="Nova",
            )
            logger.info(f"📅 Multi-day forecast for {city_name} sent.")
            return

        # Single-day target
        target_str = target_date.strftime("%Y-%m-%d")
        day_entries = [f for f in forecast_list if f["dt_txt"].startswith(target_str)]
        if not day_entries:
            say_show(
                f"No forecast available for that day in {city_name}.",
                hi="उस दिन का मौसम डेटा उपलब्ध नहीं है।",
                de=f"Keine Vorhersagedaten für diesen Tag in {city_name}.",
                fr=f"Aucune prévision disponible pour ce jour à {city_name}.",
                es=f"No hay pronóstico disponible para ese día en {city_name}.",
                title="Nova",
            )
            return

        mid = next((f for f in day_entries if "12:00:00" in f["dt_txt"]), day_entries[len(day_entries)//2])
        desc = mid["weather"][0]["description"].capitalize()
        temp_c = mid["main"]["temp"]
        if wants_fahrenheit(command):
            temp = to_fahrenheit(temp_c); unit = "°F"
        else:
            temp = temp_c; unit = "°C"

        day_name = target_date.strftime("%A")

        say_show(
            f"On {day_name}, the weather in {city_name} will be {desc}, around {temp}{unit}.",
            hi=f"{city_name} में {day_name} को मौसम {desc} रहेगा, तापमान लगभग {temp}{unit} होगा।",
            de=f"Am {day_name} wird das Wetter in {city_name} {desc} sein, etwa {temp}{unit}.",
            fr=f"Le {day_name}, le temps à {city_name} sera {desc}, avec environ {temp}{unit}.",
            es=f"El {day_name}, el clima en {city_name} será {desc}, con una temperatura de aproximadamente {temp}{unit}.",
            title="Nova",
        )
        logger.info(f"📅 Forecast | {city_name} {target_str}: {desc}, {temp}{unit}")

    except Exception as e:
        logger.error(f"[forecast] parse failed: {e}")
        say_show(
            "Could not get the forecast. Please try again.",
            hi="मौसम पूर्वानुमान नहीं मिल पाया।",
            de="Ich konnte den Wetterbericht nicht abrufen. Bitte versuche es erneut.",
            fr="Je n’ai pas pu récupérer les prévisions météo. Veuillez réessayer.",
            es="No he podido obtener el pronóstico. Por favor, intenta de nuevo.",
            title="Nova",
        )
