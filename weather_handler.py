# 📦 weather_handler.py

import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 🌐 Load environment variables
load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")

# 🔁 Lazy import utils
def get_utils():
    from utils import _speak_multilang, selected_language, logger, speak, listen_command
    return _speak_multilang, selected_language, logger, speak, listen_command


# 🌡️ Convert Celsius to Fahrenheit
def to_fahrenheit(celsius):
    return round((celsius * 9 / 5) + 32, 1)


# 🟣 Check if user asked for Fahrenheit
def wants_fahrenheit(command: str) -> bool:
    return any(word in command.lower() for word in ["fahrenheit", "f-degrees", "in f", "°f", "fahrenheit please"])


# 🧠 Ask for city if not provided
def get_city_if_missing(city_name: str) -> str:
    if city_name and city_name.strip() and city_name.lower() != "none":
        return city_name
    _speak_multilang, _, _, speak, listen_command = get_utils()
    speak("Please tell me the city you’re asking about.")
    city = listen_command()
    return city if city else "Delhi"  # Final fallback


# ✅ CURRENT WEATHER
def get_weather(city_name=None, command=""):
    _speak_multilang, selected_language, logger, _, _ = get_utils()
    city_name = get_city_if_missing(city_name)

    if not API_KEY:
        print("❌ No API key found.")
        return

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            _speak_multilang(
                f"Could not find weather for {city_name}",
                hi=f"{city_name} का मौसम नहीं मिला",
                de=f"Ich konnte das Wetter für {city_name} nicht finden.",
                fr=f"Je n’ai pas pu trouver la météo pour {city_name}.",
                es=f"No he podido encontrar el clima para {city_name}.",
                log_command=f"weather_error: {city_name}"
            )
            return

        weather = data["weather"][0]["description"].capitalize()
        temp_c = data["main"]["temp"]
        city = data["name"]

        if wants_fahrenheit(command):
            temp = to_fahrenheit(temp_c)
            unit = "°F"
        else:
            temp = temp_c
            unit = "°C"

        msg = f"The weather in {city} is {weather} with a temperature of {temp}{unit}."
        _speak_multilang(
            msg,
            hi=f"{city} का मौसम है {weather}, तापमान {temp} {unit} है।",
            de=f"Das Wetter in {city} ist {weather}, bei einer Temperatur von {temp}{unit}.",
            fr=f"Le temps à {city} est {weather}, avec une température de {temp}{unit}.",
            es=f"El clima en {city} es {weather} con una temperatura de {temp}{unit}.",
            log_command=f"weather_success: {city}, {temp}{unit}"
        )
        logger.info(f"🌤️ {msg}")

    except Exception as e:
        print("💥 Weather Error:", e)
        _speak_multilang(
            "Failed to fetch weather. Please try again later.",
            hi="मौसम नहीं मिल पाया। कृपया बाद में प्रयास करें।",
            de="Ich konnte das Wetter leider nicht abrufen.",
            fr="Je n’ai pas pu récupérer la météo.",
            es="No he podido obtener el clima.",
            log_command=f"weather_crash: {str(e)}"
        )


# ✅ FORECAST WEATHER (1-day or 7-day)
def get_forecast(city_name=None, target_date=None, command=""):
    _speak_multilang, selected_language, logger, _, _ = get_utils()
    city_name = get_city_if_missing(city_name)

    if not API_KEY or not target_date:
        return

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != "200":
            _speak_multilang(
                f"Could not find forecast for {city_name}",
                hi=f"{city_name} का पूर्वानुमान नहीं मिला",
                fr=f"Je n’ai pas pu trouver la prévision météo pour {city_name}.",
                de=f"Ich konnte die Vorhersage für {city_name} nicht finden.",
                es=f"No he podido encontrar el pronóstico para {city_name}.",
                log_command=f"forecast_error: {city_name}"
            )
            return

        forecast_list = data.get("list", [])
        command_lower = command.lower()

        multi_day = any(kw in command_lower for kw in [
            "next week", "7 days", "entire week", "full week", "whole week", "weekend forecast", "full forecast"
        ])
        weekend_request = any(kw in command_lower for kw in ["next weekend", "weekend forecast", "saturday and sunday"])

        if multi_day or weekend_request:
            today = datetime.now().date()
            daily_data = {}

            for entry in forecast_list:
                date_str = entry["dt_txt"].split(" ")[0]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (date_obj - today).days > 6:
                    continue
                if date_obj not in daily_data:
                    daily_data[date_obj] = []
                daily_data[date_obj].append(entry)

            msg = f"📆 Forecast for {city_name}:\n"
            for date_obj, entries in daily_data.items():
                if weekend_request and date_obj.weekday() not in [5, 6]:
                    continue  # Only Saturday (5) and Sunday (6)
                mid = next((e for e in entries if "12:00:00" in e["dt_txt"]), entries[len(entries)//2])
                desc = mid["weather"][0]["description"].capitalize()
                temp_c = mid["main"]["temp"]

                if wants_fahrenheit(command):
                    temp = to_fahrenheit(temp_c)
                    unit = "°F"
                else:
                    temp = temp_c
                    unit = "°C"

                msg += f"• {date_obj.strftime('%A')}: {desc}, around {temp}{unit}\n"

            _speak_multilang(msg.strip(), log_command=f"forecast_7day_success: {city_name}")
            logger.info(f"📅 Multi-day forecast for {city_name} sent.")

        else:
            target_str = target_date.strftime("%Y-%m-%d")
            filtered = [f for f in forecast_list if f["dt_txt"].startswith(target_str)]

            if not filtered:
                _speak_multilang(
                    f"No forecast available for that day in {city_name}.",
                    hi="उस दिन का मौसम डेटा उपलब्ध नहीं है।",
                    log_command=f"forecast_no_data: {city_name}, {target_str}"
                )
                return

            mid = next((f for f in filtered if "12:00:00" in f["dt_txt"]), filtered[len(filtered)//2])
            desc = mid["weather"][0]["description"].capitalize()
            temp_c = mid["main"]["temp"]

            if wants_fahrenheit(command):
                temp = to_fahrenheit(temp_c)
                unit = "°F"
            else:
                temp = temp_c
                unit = "°C"

            day_name = target_date.strftime("%A")
            msg = f"On {day_name}, the weather in {city_name} will be {desc}, around {temp}{unit}."

            _speak_multilang(
                msg,
                hi=f"{city_name} में {day_name} को मौसम {desc} रहेगा, तापमान लगभग {temp}{unit} होगा।",
                de=f"Am {day_name} wird das Wetter in {city_name} {desc} sein, mit etwa {temp}{unit}.",
                fr=f"Le {day_name}, le temps à {city_name} sera {desc}, avec environ {temp}{unit}.",
                es=f"El {day_name}, el clima en {city_name} será {desc}, con una temperatura de aproximadamente {temp}{unit}.",
                log_command=f"forecast_success: {city_name}, {target_str}, {desc}, {temp}{unit}"
            )
            logger.info(f"📅 Forecast for {city_name} on {target_str}: {desc}, {temp}{unit}")

    except Exception as e:
        print("💥 Forecast error:", e)
        _speak_multilang(
            "Could not get the forecast. Please try again.",
            hi="मौसम पूर्वानुमान नहीं मिल पाया।",
            de="Ich konnte den Wetterbericht nicht abrufen. Bitte versuche es erneut.",
            fr="Je n’ai pas pu récupérer les prévisions météo. Veuillez réessayer.",
            es="No he podido obtener el pronóstico. Por favor, intenta de nuevo.",
            log_command=f"forecast_crash: {str(e)}"
        )
