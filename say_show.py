# say_show.py
from typing import Dict, Optional
from utils import selected_language, speak, gui_callback  # gui_callback exists per your utils.py


def _pick_lang(msg_map: Dict[str, str]) -> str:
    """
    Choose the right-language string based on current UI language.
    Falls back to 'en', then to any value in the map.
    """
    lang = (selected_language or "en").lower()
    return msg_map.get(lang) or msg_map.get("en") or next(iter(msg_map.values()), "")


def _show_bubble(title: str, text: str) -> None:
    """
    Try the registered GUI callback first; if not present, lazily get the GUI instance.
    Never triggers TTS; safe if GUI isn't available yet.
    """
    try:
        cb = gui_callback("show_message")  # returns a callable or None
        if cb:
            cb(title, text)
            return
    except Exception:
        pass

    # Fallback: lazy import to avoid circular dependencies
    try:
        from gui_interface import get_gui  # imported only when needed
        gui = get_gui()
        show_fn = getattr(gui, "safe_show_message", None) or getattr(gui, "show_message", None)
        if show_fn:
            show_fn(title, text)
    except Exception:
        # final fallback: do nothing (avoid crashing handlers)
        pass


def say_show_texts(tts_text: str, gui_text: Optional[str] = None, *, title: str = "Nova") -> None:
    """
    Speak first (blocking), then show the bubble.
    Use this when TTS text and GUI text are DIFFERENT.

    Example:
        say_show_texts("Opening the gallery.", "Opening Pok├⌐mon gallery:\\nhttps://ΓÇª")
    """
    if not (tts_text or gui_text):
        return
    # SAY (blocking so bubble appears AFTER speech finishes)
    if tts_text:
        try:
            speak(tts_text, blocking=True)
        except TypeError:
            speak(tts_text)
    # SHOW
    if gui_text:
        _show_bubble(title, gui_text)


def say_show_map(msg_map: Dict[str, str], *, title: str = "Nova") -> None:
    """
    Speak first (blocking), then show the SAME text in the current UI language.
    Expected keys: 'en','hi','de','fr','es' (falls back to 'en').
    """
    text = _pick_lang(msg_map)
    if not text:
        return
    try:
        speak(text, blocking=True)  # TTS only; no GUI side-effects
    except TypeError:
        speak(text)
    _show_bubble(title, text)


def say_show(
    en: str,
    *,
    hi: str = "",
    de: str = "",
    fr: str = "",
    es: str = "",
    title: str = "Nova"
) -> None:
    """
    Convenience when TTS and bubble text are the SAME sentence,
    with multilingual variants.
    """
    say_show_map(
        {"en": en, "hi": hi or en, "de": de or en, "fr": fr or en, "es": es or en},
        title=title,
    )
