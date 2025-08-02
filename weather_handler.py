import requests
import os
from dotenv import load_dotenv
from utils import _speak_multilang, selected_language

# 🌐 Load environment variables
load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")

def get_weather(city_name="Delhi"):
    if not API_KEY:
        print("❌ No API key found. Please set OPENWEATHER_API_KEY in .env")
        return

    try:
        # 🛰️ Make API request to OpenWeather
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        # 🧪 Handle bad response (e.g., city not found)
        if data.get("cod") != 200:
            msg = f"Could not find weather for {city_name}"
            print("⚠️", msg)
            _speak_multilang(
                msg,
                hi=f"{city_name} का मौसम नहीं मिला",
                de=f"Wetter für {city_name} wurde nicht gefunden",
                fr=f"Météo pour {city_name} introuvable",
                es=f"No se encontró el clima de {city_name}"
            )
            return

        # 🌡️ Extract data
        weather = data["weather"][0]["description"].capitalize()
        temp = data["main"]["temp"]
        city = data["name"]
        final_msg = f"The weather in {city} is {weather} with a temperature of {temp}°C."

        print("🌦️", final_msg)
        _speak_multilang(
            final_msg,
            hi=f"{city} का मौसम है {weather}, तापमान {temp} डिग्री सेल्सियस है।",
            de=f"Das Wetter in {city} ist {weather}, bei {temp} Grad Celsius.",
            fr=f"Le temps à {city} est {weather} avec une température de {temp} degrés.",
            es=f"El clima en {city} es {weather} con una temperatura de {temp} grados."
        )

    except Exception as e:
        print("💥 Error:", e)
        _speak_multilang(
            "Failed to fetch weather. Please try again later.",
            hi="मौसम नहीं मिल पाया। कृपया बाद में प्रयास करें।",
            de="Wetter konnte nicht abgerufen werden.",
            fr="Impossible de récupérer la météo.",
            es="No se pudo obtener el clima."
        )
