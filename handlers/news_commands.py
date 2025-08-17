# 📂 handlers/news_commands.py

import re
from difflib import get_close_matches
from command_map import COMMAND_MAP
from news_handler import get_headlines

# 🗞️ News Headlines Handler
def handle_news(command: str):
    # ✅ Delayed import to prevent circular import
    from utils import _speak_multilang, log_interaction, selected_language

    command = command.strip().lower()
    news_phrases = COMMAND_MAP["get_news"]
    matched_news = get_close_matches(command, news_phrases, n=1, cutoff=0.7)

    if matched_news:
        # 🔍 Try to extract topic from common phrases
        topic_match = re.search(
            r"(about|regarding|on|के बारे में|से जुड़ी|sur|über|sobre)\s+(.+)",
            command,
            re.IGNORECASE
        )
        topic = topic_match.group(2).strip() if topic_match else ""

        # 🔄 Fallback extraction: "news cricket", "update India", etc.
        if not topic:
            fallback = re.findall(
                r"(?:news|updates?)\s+(.+)",
                command,
                flags=re.IGNORECASE
            )
            topic = fallback[0].strip() if fallback else ""

        headlines = get_headlines(topic)
        if headlines:
            _speak_multilang(
                f"Here are the top headlines about {topic}:" if topic else "Here are the latest news headlines.",
                hi=f"{topic} से जुड़ी प्रमुख खबरें यह हैं:" if topic else "यह हैं आज की मुख्य खबरें।",
                fr=f"Voici les principaux titres sur {topic} :" if topic else "Voici les derniers titres d’actualité.",
                es=f"Aquí están los principales titulares sobre {topic}:" if topic else "Aquí están las últimas noticias.",
                de=f"Hier sind die wichtigsten Schlagzeilen über {topic}:" if topic else "Hier sind die neuesten Nachrichten."
            )

            for idx, news in enumerate(headlines, 1):
                print(f"{idx}. {news}")
                _speak_multilang(news)
        else:
            _speak_multilang(
                f"Sorry, I couldn't find any news about {topic}." if topic else "No news available right now.",
                hi=f"माफ़ कीजिए, {topic} से जुड़ी कोई खबर नहीं मिली।" if topic else "इस समय कोई खबर उपलब्ध नहीं है।",
                fr=f"Désolée, je n’ai trouvé aucune nouvelle sur {topic}." if topic else "Aucune nouvelle n’est disponible pour le moment.",
                es=f"Lo siento, no he encontrado noticias sobre {topic}." if topic else "No hay noticias disponibles en este momento.",
                de=f"Es tut mir leid, ich konnte keine Nachrichten über {topic} finden." if topic else "Zurzeit sind keine Nachrichten verfügbar."
            )
    else:
        log_interaction(
            "unmatched_news_command",
            "No matching news command",
            selected_language
        )
        _speak_multilang(
            "I’m not sure what news you want. You can say things like 'latest news on sports' or 'show me headlines'.",
            hi="मैं नहीं समझ पाई कि आप किस खबर की बात कर रहे हैं। आप कह सकते हैं: 'खेल की खबरें दिखाओ'।",
            fr="Je ne suis pas sûre des nouvelles que vous souhaitez. Essayez avec : 'les dernières nouvelles sur le sport'.",
            es="No estoy segura de qué noticias quieres. Puedes decir: 'últimas noticias sobre deportes'.",
            de="Ich bin mir nicht sicher, welche Nachrichten du meinst. Du kannst zum Beispiel sagen: 'Neueste Nachrichten über Sport'."
        )
