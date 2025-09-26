# 📂 handlers/web_commands.py — SAY→SHOW + typed/voice follow-ups (Nova casing)

from __future__ import annotations

import re
import urllib.parse
import webbrowser
from difflib import get_close_matches

from command_map import COMMAND_MAP
from followup import await_followup
from say_show import say_show  # speak first, then show localized bubble


# ─────────────────────────────────────────────────────────────────────────────
# Lazy utils (avoid circular imports)
def _get_utils():
    from utils import selected_language, listen_command
    return selected_language, listen_command


def _ui_lang() -> str:
    selected_language, *_ = _get_utils()
    return (selected_language or "en").split("-")[0].lower()


def _pick(d: dict) -> str:
    """Pick text for current UI lang; fallback to en."""
    return d.get(_ui_lang(), d.get("en", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Prompts / messages (ALL localized)
T = {
    "opening_youtube": {
        "en": "Opening YouTube.",
        "hi": "मैं यूट्यूब खोल रही हूँ।",
        "de": "Ich öffne YouTube.",
        "fr": "J’ouvre YouTube.",
        "es": "Estoy abriendo YouTube.",
    },
    "opening_chatgpt": {
        "en": "Opening ChatGPT.",
        "hi": "मैं चैटजीपीटी खोल रही हूँ।",
        "de": "Ich öffne ChatGPT.",
        "fr": "J’ouvre ChatGPT.",
        "es": "Estoy abriendo ChatGPT.",
    },
    "ask_google": {
        "en": "What should I search for? You can type or say it.",
        "hi": "मुझे क्या खोजने के लिए कहोगे? आप टाइप कर सकते हैं या बोल सकते हैं।",
        "de": "Wonach soll ich suchen? Du kannst tippen oder sprechen.",
        "fr": "Que veux-tu que je recherche ? Tu peux écrire ou parler.",
        "es": "¿Qué quieres que busque? Puedes escribir o hablar.",
    },
    "ask_song": {
        "en": "What song should I play? You can type or say it.",
        "hi": "मैं कौन सा गाना चलाऊँ? आप टाइप कर सकते हैं या बोल सकते हैं।",
        "de": "Welches Lied soll ich abspielen? Du kannst tippen oder sprechen.",
        "fr": "Quelle chanson veux-tu que je joue ? Tu peux écrire ou parler.",
        "es": "¿Qué canción quieres que reproduzca? Puedes escribir o hablar.",
    },
    "no_search_term": {
        "en": "Sorry, I couldn't understand the search term.",
        "hi": "माफ़ कीजिए, मैं खोज शब्द नहीं समझ पाई।",
        "de": "Entschuldigung, ich habe den Suchbegriff nicht verstanden.",
        "fr": "Désolée, je n’ai pas compris le terme de recherche.",
        "es": "Lo siento, no entendí el término de búsqueda.",
    },
    "no_song": {
        "en": "I couldn't understand the song name.",
        "hi": "मैं गाने का नाम नहीं समझ पाई।",
        "de": "Ich habe den Liedtitel nicht verstanden.",
        "fr": "Je n’ai pas compris le nom de la chanson.",
        "es": "No entendí el nombre de la canción.",
    },
    "searching_google": {
        "en": "Searching Google for {q}.",
        "hi": "{q} के लिए मैं गूगल पर खोज रही हूँ।",
        "de": "Ich suche auf Google nach {q}.",
        "fr": "Je cherche {q} sur Google.",
        "es": "Estoy buscando {q} en Google.",
    },
    "playing_on_youtube": {
        "en": "Playing {q} on YouTube.",
        "hi": "मैं यूट्यूब पर {q} चला रही हूँ।",
        "de": "Ich spiele {q} auf YouTube ab.",
        "fr": "Je joue {q} sur YouTube.",
        "es": "Estoy reproduciendo {q} en YouTube.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# ▶️ Open YouTube
def handle_open_youtube(command: str) -> None:
    cmd_lc = (command or "").lower()
    # If user typed "open youtube and play …", let the music handler take it.
    if "open youtube and play " in cmd_lc:
        return

    if get_close_matches(command, COMMAND_MAP["open_youtube"], n=1, cutoff=0.7):
        say_show(
            T["opening_youtube"]["en"],
            hi=T["opening_youtube"]["hi"],
            de=T["opening_youtube"]["de"],
            fr=T["opening_youtube"]["fr"],
            es=T["opening_youtube"]["es"],
            title="Nova",
        )
        webbrowser.open("https://www.youtube.com")


# ─────────────────────────────────────────────────────────────────────────────
# ▶️ Open ChatGPT
def handle_open_chatgpt(command: str) -> None:
    if get_close_matches(command, COMMAND_MAP["open_chatgpt"], n=1, cutoff=0.7):
        say_show(
            T["opening_chatgpt"]["en"],
            hi=T["opening_chatgpt"]["hi"],
            de=T["opening_chatgpt"]["de"],
            fr=T["opening_chatgpt"]["fr"],
            es=T["opening_chatgpt"]["es"],
            title="Nova",
        )
        webbrowser.open("https://chat.openai.com")


# ─────────────────────────────────────────────────────────────────────────────
# 🔎 Google Search — inline or follow-up (typed/voice)
def handle_search_google(command: str) -> None:
    cmd = (command or "").strip()

    # 1) Inline patterns like:
    #    "search on google hawking radiation"
    #    "google hawking radiation"
    #    "search for hawking radiation"
    m = re.search(r"(?:^|\b)(?:search on google|google|search for)\s+(.+)", cmd, flags=re.I)
    query = m.group(1).strip() if m else ""

    if query:
        q = query
        say_show(
            T["searching_google"]["en"].format(q=q),
            hi=T["searching_google"]["hi"].format(q=q),
            de=T["searching_google"]["de"].format(q=q),
            fr=T["searching_google"]["fr"].format(q=q),
            es=T["searching_google"]["es"].format(q=q),
            title="Nova",
        )
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(q))
        return

    # 2) Triggered flow via fuzzy match → ask once; accept typed OR voice
    if get_close_matches(command, COMMAND_MAP["search_google"], n=1, cutoff=0.7):
        # SAY→SHOW the prompt (localized); then await without re-speaking/showing
        say_show(
            T["ask_google"]["en"],
            hi=T["ask_google"]["hi"],
            de=T["ask_google"]["de"],
            fr=T["ask_google"]["fr"],
            es=T["ask_google"]["es"],
            title="Nova",
        )
        # During await: do not re-say/re-show (pass no-op lambdas)
        _, listen_command = _get_utils()
        q = await_followup(
            _pick(T["ask_google"]),
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0,
        )
        q = (q or "").strip()
        if not q:
            say_show(
                T["no_search_term"]["en"],
                hi=T["no_search_term"]["hi"],
                de=T["no_search_term"]["de"],
                fr=T["no_search_term"]["fr"],
                es=T["no_search_term"]["es"],
                title="Nova",
            )
            return

        say_show(
            T["searching_google"]["en"].format(q=q),
            hi=T["searching_google"]["hi"].format(q=q),
            de=T["searching_google"]["de"].format(q=q),
            fr=T["searching_google"]["fr"].format(q=q),
            es=T["searching_google"]["es"].format(q=q),
            title="Nova",
        )
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(q))


# ─────────────────────────────────────────────────────────────────────────────
# 🎵 Play Music on YouTube — inline or follow-up (typed/voice)
def handle_play_music(command: str) -> None:
    s = (command or "").strip()

    # 1) Inline patterns
    for pat in (
        r"^(?:play(?:\s+music|\s+song|\s+track)?\s+)(?P<q>.+)$",
        r"^(?:open\s+youtube\s+and\s+play\s+)(?P<q>.+)$",
    ):
        m = re.match(pat, s, flags=re.I)
        if m:
            q = (m.group("q") or "").strip()
            if q:
                say_show(
                    T["playing_on_youtube"]["en"].format(q=q),
                    hi=T["playing_on_youtube"]["hi"].format(q=q),
                    de=T["playing_on_youtube"]["de"].format(q=q),
                    fr=T["playing_on_youtube"]["fr"].format(q=q),
                    es=T["playing_on_youtube"]["es"].format(q=q),
                    title="Nova",
                )
                webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q))
                return

    # 2) Triggered flow via fuzzy match → ask once; accept typed OR voice
    if get_close_matches(command, COMMAND_MAP["play_music"], n=1, cutoff=0.7):
        # SAY→SHOW the prompt (localized); then await without re-speaking/showing
        say_show(
            T["ask_song"]["en"],
            hi=T["ask_song"]["hi"],
            de=T["ask_song"]["de"],
            fr=T["ask_song"]["fr"],
            es=T["ask_song"]["es"],
            title="Nova",
        )
        _, listen_command = _get_utils()
        q = await_followup(
            _pick(T["ask_song"]),
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0,
        )
        q = (q or "").strip()
        if not q:
            say_show(
                T["no_song"]["en"],
                hi=T["no_song"]["hi"],
                de=T["no_song"]["de"],
                fr=T["no_song"]["fr"],
                es=T["no_song"]["es"],
                title="Nova",
            )
            return

        say_show(
            T["playing_on_youtube"]["en"].format(q=q),
            hi=T["playing_on_youtube"]["hi"].format(q=q),
            de=T["playing_on_youtube"]["de"].format(q=q),
            fr=T["playing_on_youtube"]["fr"].format(q=q),
            es=T["playing_on_youtube"]["es"].format(q=q),
            title="Nova",
        )
        webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q))
