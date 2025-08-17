# 📂 handlers/web_commands.py

import webbrowser
from difflib import get_close_matches
from command_map import COMMAND_MAP

# ▶️ Open YouTube
def handle_open_youtube(command: str) -> None:
    from utils import _speak_multilang  # ✅ Lazy import

    if get_close_matches(command, COMMAND_MAP["open_youtube"], n=1, cutoff=0.7):
        print("🌐 Opening YouTube...")
        _speak_multilang(
            "Opening YouTube.",
            hi="मैं यूट्यूब खोल रही हूँ।",
            de="Ich öffne YouTube.",
            fr="Je suis en train d’ouvrir YouTube.",
            es="Estoy abriendo YouTube.",
            log_command="Opened YouTube"
        )
        webbrowser.open("https://www.youtube.com")


# ▶️ Open ChatGPT
def handle_open_chatgpt(command: str) -> None:
    from utils import _speak_multilang  # ✅ Lazy import

    if get_close_matches(command, COMMAND_MAP["open_chatgpt"], n=1, cutoff=0.7):
        print("🌐 Opening ChatGPT...")
        _speak_multilang(
            "Opening ChatGPT.",
            hi="मैं चैटजीपीटी खोल रही हूँ।",
            de="Ich öffne ChatGPT.",
            fr="Je suis en train d’ouvrir ChatGPT.",
            es="Estoy abriendo ChatGPT.",
            log_command="Opened ChatGPT"
        )
        webbrowser.open("https://chat.openai.com")


# 🔎 Google Search
def handle_search_google(command: str) -> None:
    from utils import _speak_multilang, listen_command  # ✅ Lazy import

    if get_close_matches(command, COMMAND_MAP["search_google"], n=1, cutoff=0.7):
        print("🌐 Preparing for Google search...")
        _speak_multilang(
            "What should I search for?",
            hi="मुझे क्या खोजने के लिए कहोगे?",
            de="Was soll ich für dich suchen?",
            fr="Que veux-tu que je recherche ?",
            es="¿Qué quieres que busque?"
        )
        for _ in range(2):
            query = listen_command()
            if query:
                print(f"🌐 Searching: {query}")
                webbrowser.open(f"https://www.google.com/search?q={query}")
                _speak_multilang(
                    f"Searching Google for {query}.",
                    hi=f"मैं {query} के लिए गूगल पर खोज रही हूँ।",
                    de=f"Ich suche auf Google nach {query}.",
                    fr=f"Je cherche {query} sur Google.",
                    es=f"Estoy buscando {query} en Google.",
                    log_command=f"Searched Google: {query}"
                )
                return
        print("❌ No valid search term detected.")
        _speak_multilang(
            "Sorry, I couldn't understand the search term.",
            hi="माफ़ कीजिए, मैं खोज शब्द समझ नहीं पाई।",
            de="Désolée, je n’ai pas compris le terme de recherche.",
            fr="Désolée, je n’ai pas compris le terme de recherche.",
            es="Lo siento, no entendí el término de búsqueda."
        )


# 🎵 Play Music
def handle_play_music(command: str) -> None:
    from utils import _speak_multilang, listen_command  # ✅ Lazy import

    if get_close_matches(command, COMMAND_MAP["play_music"], n=1, cutoff=0.7):
        print("🎵 Asking for music to play...")
        _speak_multilang(
            "What song should I play?",
            hi="मैं कौन सा गाना चलाऊँ?",
            de="Welches Lied soll ich abspielen?",
            fr="Quelle chanson veux-tu que je joue ?",
            es="¿Qué canción quieres que reproduzca?"
        )
        query = listen_command()
        if query:
            print(f"🎵 Playing on YouTube: {query}")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
            _speak_multilang(
                f"Playing {query} on YouTube.",
                hi=f"मैं यूट्यूब पर {query} चला रही हूँ।",
                de=f"Ich spiele {query} auf YouTube ab.",
                fr=f"Je joue {query} sur YouTube.",
                es=f"Estoy reproduciendo {query} en YouTube.",
                log_command=f"Played music on YouTube: {query}"
            )
        else:
            print("❌ No song detected.")
            _speak_multilang(
                "I couldn't understand the song name.",
                hi="माफ़ कीजिए, मैं गाने का नाम समझ नहीं पाई।",
                de="Désolée, ich habe den Liedtitel nicht verstanden.",
                fr="Désolée, je n’ai pas compris le nom de la chanson.",
                es="Lo siento, no entendí el nombre de la canción."
            )
