# 📂 handlers/news_commands.py — SAY→SHOW + typed/voice follow-ups (Nova casing)
from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Optional, List

from command_map import COMMAND_MAP
from news_handler import get_headlines
from say_show import say_show  # central helper: speak first, then show localized bubble


# ─────────────────────────────────────────────────────────────────────────────
# Lazy utils (avoid circular imports)
def _get_utils():
    from utils import _speak_multilang, selected_language, listen_command, logger
    from followup import await_followup
    return _speak_multilang, selected_language, listen_command, logger, await_followup


# ─────────────────────────────────────────────────────────────────────────────
# Prompts (multilingual). We *SAY* all languages, and the bubble shows in UI lang.
_PROMPTS = {
    "ask_topic": {
        "en": "Which news topic would you like? You can type or say it.",
        "hi": "कौन-सा समाचार विषय चाहिए? आप टाइप कर सकते हैं या बोल सकते हैं।",
        "de": "Welches Nachrichtenthema möchtest du? Du kannst tippen oder sprechen.",
        "fr": "Quel sujet d’actualité veux-tu ? Tu peux écrire ou parler.",
        "es": "¿Qué tema de noticias deseas? Puedes escribir o hablar.",
    },
    "didnt_get_it": {
        "en": "I couldn't get the topic.",
        "hi": "मैं विषय नहीं समझ पाई।",
        "de": "Ich konnte das Thema nicht verstehen.",
        "fr": "Je n’ai pas compris le sujet.",
        "es": "No entendí el tema.",
    },
    "unclear_intent": {
        "en": "I can fetch headlines. Try “latest news on sports” or “show me headlines”.",
        "hi": "मैं खबरों की सुर्खियाँ ला सकती हूँ। जैसे “खेल की खबरें दिखाओ” कहें।",
        "de": "Ich kann Schlagzeilen holen. Z. B. „neueste Nachrichten über Sport“.",
        "fr": "Je peux récupérer des gros titres. Par exemple : « dernières actus sport ».",
        "es": "Puedo traer titulares. Por ejemplo: «últimas noticias de deportes».",
    },
    "header_with_topic": {
        "en": "Here are the top headlines about {topic}:",
        "hi": "{topic} से जुड़ी प्रमुख खबरें यह हैं:",
        "de": "Hier sind die wichtigsten Schlagzeilen über {topic}:",
        "fr": "Voici les principaux titres sur {topic} :",
        "es": "Aquí están los principales titulares sobre {topic}:",
    },
    "header_generic": {
        "en": "Here are the latest news headlines.",
        "hi": "यह हैं आज की मुख्य खबरें।",
        "de": "Hier sind die neuesten Nachrichten.",
        "fr": "Voici les derniers titres d’actualité.",
        "es": "Aquí están las últimas noticias.",
    },
    "no_results_with_topic": {
        "en": "Sorry, I couldn't find any news about {topic}.",
        "hi": "माफ़ कीजिए, {topic} से जुड़ी कोई खबर नहीं मिली।",
        "de": "Es tut mir leid, ich konnte keine Nachrichten über {topic} finden.",
        "fr": "Désolée, je n’ai trouvé aucune nouvelle sur {topic}.",
        "es": "Lo siento, no he encontrado noticias sobre {topic}.",
    },
    "no_results_generic": {
        "en": "No news available right now.",
        "hi": "इस समय कोई खबर उपलब्ध नहीं है।",
        "de": "Zurzeit sind keine Nachrichten verfügbar.",
        "fr": "Aucune nouvelle n’est disponible pour le moment.",
        "es": "No hay noticias disponibles en este momento.",
    },
}


def _ui_lang() -> str:
    _, selected_language, *_ = _get_utils()
    return (selected_language or "en").split("-")[0].lower()


def _pick_lang(d: dict, **fmt) -> str:
    txt = d.get(_ui_lang(), d.get("en", ""))
    try:
        return txt.format(**fmt) if fmt else txt
    except Exception:
        return txt


def _say_then_show_prompt(key: str) -> str:
    """SAY in all langs (keeps Nova’s mouth anim) → SHOW bubble in UI language."""
    _speak_multilang, *_ = _get_utils()
    p = _PROMPTS[key]
    _speak_multilang(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
    return _pick_lang(p)


# ─────────────────────────────────────────────────────────────────────────────
# Topic extractors
def _extract_topic(command: str) -> Optional[str]:
    cmd = (command or "").strip()

    # “… about/on/regarding …” (multi-lang preps)
    m = re.search(r"(?:about|regarding|on|के बारे में|से जुड़ी|sur|über|sobre)\s+(.+)", cmd, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # “news cricket”, “updates india”
    m2 = re.search(r"\b(?:news|updates?)\s+(.+)", cmd, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()

    return None


def _format_headlines_for_gui(headlines: List[str], topic: str) -> str:
    header = _pick_lang(_PROMPTS["header_with_topic"], topic=topic) if topic else _PROMPTS["header_generic"][_ui_lang()]
    lines = [f"{i+1}. {h}" for i, h in enumerate(headlines)]
    return header + "\n" + "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main handler
def handle_news(command: str) -> None:
    """
    Latest headlines with optional topic.
    • say→then→show prompts (localized bubbles) using say_show
    • typed OR voice follow-ups via await_followup (barge-in handled inside)
    • short clarifier on unclear intent
    """
    _speak_multilang, _, listen_command, logger, await_followup = _get_utils()

    text = (command or "").strip().lower()
    news_phrases = COMMAND_MAP.get("get_news", [])
    matched = get_close_matches(text, news_phrases, n=1, cutoff=0.7)

    if not matched and not re.search(r"\bnews|headline|updates?\b", text, re.I):
        # Unclear-intent guardrail
        say_show(
            _PROMPTS["unclear_intent"]["en"],
            hi=_PROMPTS["unclear_intent"]["hi"],
            de=_PROMPTS["unclear_intent"]["de"],
            fr=_PROMPTS["unclear_intent"]["fr"],
            es=_PROMPTS["unclear_intent"]["es"],
            title="Nova",
        )
        return

    # Try to extract topic from the initial utterance
    topic = _extract_topic(text)

    # If missing, ask once (SAY→SHOW), then await (no re-say/show inside await)
    if not topic:
        prompt = _say_then_show_prompt("ask_topic")
        # We already spoke & showed; avoid duplicate TTS/bubble inside await_followup
        answer = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0,
        )
        topic = (answer or "").strip()
        if not topic:
            # Graceful bail-out
            say_show(
                _PROMPTS["didnt_get_it"]["en"],
                hi=_PROMPTS["didnt_get_it"]["hi"],
                de=_PROMPTS["didnt_get_it"]["de"],
                fr=_PROMPTS["didnt_get_it"]["fr"],
                es=_PROMPTS["didnt_get_it"]["es"],
                title="Nova",
            )
            return

    # Fetch headlines (empty topic is allowed for generic)
    try:
        headlines = get_headlines(topic)
    except Exception as e:
        logger = _get_utils()[3]
        logger.error(f"[news] get_headlines failed: {e}")
        say_show(
            _PROMPTS["no_results_with_topic"]["en"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["en"],
            hi=_PROMPTS["no_results_with_topic"]["hi"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["hi"],
            de=_PROMPTS["no_results_with_topic"]["de"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["de"],
            fr=_PROMPTS["no_results_with_topic"]["fr"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["fr"],
            es=_PROMPTS["no_results_with_topic"]["es"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["es"],
            title="Nova",
        )
        return

    if headlines:
        # SAY a concise header, SHOW the full list (localized header + numbered items)
        header_map = _PROMPTS["header_with_topic"] if topic else _PROMPTS["header_generic"]
        say_show(
            header_map["en"].format(topic=topic) if topic else header_map["en"],
            hi=header_map["hi"].format(topic=topic) if topic else header_map["hi"],
            de=header_map["de"].format(topic=topic) if topic else header_map["de"],
            fr=header_map["fr"].format(topic=topic) if topic else header_map["fr"],
            es=header_map["es"].format(topic=topic) if topic else header_map["es"],
            title="Nova",
        )

        gui_text = _format_headlines_for_gui(headlines, topic)
        # show the full list without re-speaking (bubble only)
        say_show(gui_text, title="Nova")

    else:
        say_show(
            _PROMPTS["no_results_with_topic"]["en"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["en"],
            hi=_PROMPTS["no_results_with_topic"]["hi"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["hi"],
            de=_PROMPTS["no_results_with_topic"]["de"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["de"],
            fr=_PROMPTS["no_results_with_topic"]["fr"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["fr"],
            es=_PROMPTS["no_results_with_topic"]["es"].format(topic=topic) if topic else _PROMPTS["no_results_generic"]["es"],
            title="Nova",
        )
