import requests
import os
from dotenv import load_dotenv
from utils import _speak_multilang, selected_language

# 🚀 Load env vars
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def get_headlines(country="in", count=5):
    if not NEWS_API_KEY:
        print("❌ NEWS_API_KEY not set.")
        return

    try:
        url = (
            f"https://newsapi.org/v2/top-headlines?"
            f"country={country}&pageSize={count}&apiKey={NEWS_API_KEY}"
        )
        response = requests.get(url)
        data = response.json()

        if data["status"] != "ok":
            raise Exception("NewsAPI error")

        articles = data["articles"]
        if not articles:
            _speak_multilang(
                "No news articles found.",
                hi="कोई समाचार नहीं मिला।",
                fr="Aucun article trouvé.",
                es="No se encontraron noticias.",
                de="Keine Nachrichten gefunden."
            )
            return

        _speak_multilang(
            f"Here are the top {count} news headlines:",
            hi=f"यहाँ शीर्ष {count} खबरें हैं:",
            fr=f"Voici les {count} principaux titres :",
            es=f"Aquí están las {count} principales noticias:",
            de=f"Hier sind die Top {count} Schlagzeilen:"
        )

        for i, article in enumerate(articles, start=1):
            headline = article["title"]
            print(f"📰 {i}. {headline}")
            _speak_multilang(headline)

    except Exception as e:
        print("💥 Error fetching news:", e)
        _speak_multilang(
            "Could not fetch news right now.",
            hi="अभी समाचार नहीं मिल सका।",
            fr="Impossible de récupérer les nouvelles pour le moment.",
            es="No se pudieron obtener noticias.",
            de="Nachrichten konnten nicht abgerufen werden."
        )
