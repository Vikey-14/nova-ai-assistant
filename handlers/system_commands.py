# 📂 handlers/system_commands.py — SAY→SHOW + typed/voice follow-ups (Nova casing)
from __future__ import annotations

import os
import re
import sys
import platform

from difflib import get_close_matches
from command_map import COMMAND_MAP
from say_show import say_show  # speak first, then show localized bubble

# ─────────────────────────────────────────────────────────────────────────────
# Lazy utils to avoid circular imports at module import time
def _lazy_utils():
    from utils import speak, listen_command, set_volume, change_brightness, logger as _logger
    from followup import await_followup
    return speak, listen_command, set_volume, change_brightness, await_followup, _logger

# ─────────────────────────────────────────────────────────────────────────────
# Multilingual prompts (ALL lines localized). SAY→SHOW is done via say_show.
_PROMPTS = {
    "ask_volume_level": {
        "en": "What volume level should I set? You can type or say a number from 0 to 100.",
        "hi": "वॉल्यूम कितना सेट करूँ? 0 से 100 के बीच कोई संख्या बोलें या टाइप करें।",
        "de": "Auf welche Lautstärke soll ich einstellen? Bitte eine Zahl von 0 bis 100 tippen oder sprechen.",
        "fr": "À quel niveau régler le volume ? Tapez ou dites un nombre de 0 à 100.",
        "es": "¿A qué nivel debo poner el volumen? Escribe o di un número de 0 a 100.",
    },
    "ask_brightness_level": {
        "en": "What brightness level should I set? You can type or say a number from 0 to 100.",
        "hi": "ब्राइटनेस कितना सेट करूँ? 0 से 100 के बीच कोई संख्या बोलें या टाइप करें।",
        "de": "Auf welche Helligkeit soll ich einstellen? Bitte eine Zahl von 0 bis 100 tippen oder sprechen.",
        "fr": "À quel niveau régler la luminosité ? Tapez ou dites un nombre de 0 à 100.",
        "es": "¿A qué nivel debo poner el brillo? Escribe o di un número de 0 a 100.",
    },
    "didnt_get_it": {
        "en": "I couldn't get that.",
        "hi": "मैं समझ नहीं पाई।",
        "de": "Ich habe das nicht verstanden.",
        "fr": "Je n’ai pas compris.",
        "es": "No entendí eso.",
    },
    "need_0_100": {
        "en": "Please give me a number between 0 and 100.",
        "hi": "कृपया 0 से 100 के बीच कोई संख्या बताइए।",
        "de": "Bitte nenne mir eine Zahl zwischen 0 und 100.",
        "fr": "Donnez-moi un nombre entre 0 et 100.",
        "es": "Dime un número entre 0 y 100.",
    },
    "vol_up_ok": {
        "en": "Volume increased.",
        "hi": "वॉल्यूम बढ़ा दिया है।",
        "de": "Ich habe die Lautstärke erhöht.",
        "fr": "Le volume a été augmenté.",
        "es": "He subido el volumen.",
    },
    "vol_down_ok": {
        "en": "Volume decreased.",
        "hi": "वॉल्यूम कम कर दिया है।",
        "de": "Ich habe die Lautstärke verringert.",
        "fr": "Le volume a été diminué.",
        "es": "He bajado el volumen.",
    },
    "vol_mute_ok": {
        "en": "Volume muted.",
        "hi": "वॉल्यूम म्यूट कर दिया है।",
        "de": "Ich habe den Ton stummgeschaltet.",
        "fr": "Le volume est coupé.",
        "es": "He silenciado el volumen.",
    },
    "vol_max_ok": {
        "en": "Volume set to maximum.",
        "hi": "वॉल्यूम अधिकतम पर सेट कर दिया है।",
        "de": "Ich habe die Lautstärke auf Maximum gestellt.",
        "fr": "Volume réglé au maximum.",
        "es": "He puesto el volumen al máximo.",
    },
    "vol_set_to": {
        "en": "Setting volume to {n} percent.",
        "hi": "वॉल्यूम {n} प्रतिशत पर सेट कर दिया है।",
        "de": "Lautstärke auf {n} Prozent eingestellt.",
        "fr": "Volume réglé à {n} pour cent.",
        "es": "Volumen ajustado al {n} por ciento.",
    },
    "bright_up_ok": {
        "en": "Increasing brightness.",
        "hi": "ब्राइटनेस बढ़ा रही हूँ।",
        "de": "Ich erhöhe die Helligkeit.",
        "fr": "J’augmente la luminosité.",
        "es": "Estoy aumentando el brillo.",
    },
    "bright_down_ok": {
        "en": "Decreasing brightness.",
        "hi": "ब्राइटनेस कम कर रही हूँ।",
        "de": "Ich verringere die Helligkeit.",
        "fr": "Je diminue la luminosité.",
        "es": "Estoy bajando el brillo.",
    },
    "bright_set_to": {
        "en": "Setting brightness to {n} percent.",
        "hi": "ब्राइटनेस को {n} प्रतिशत पर सेट कर रही हूँ।",
        "de": "Helligkeit auf {n} Prozent eingestellt.",
        "fr": "Luminosité réglée à {n} pour cent.",
        "es": "He ajustado el brillo al {n} por ciento.",
    },
    "shutdown": {
        "en": "Shutting down the system now.",
        "hi": "सिस्टम को बंद कर रही हूँ।",
        "de": "Ich fahre das System jetzt herunter.",
        "fr": "J’éteins le système maintenant.",
        "es": "Apagando el sistema ahora.",
    },
    "restart": {
        "en": "Restarting the system.",
        "hi": "सिस्टम को रीस्टार्ट कर रही हूँ।",
        "de": "Ich starte das System neu.",
        "fr": "Je redémarre le système.",
        "es": "Reiniciando el sistema.",
    },
    "sleep": {
        "en": "Putting the computer to sleep.",
        "hi": "कंप्यूटर को स्लीप मोड में डाल रही हूँ।",
        "de": "Ich versetze den Computer in den Ruhezustand.",
        "fr": "Je mets l’ordinateur en veille.",
        "es": "Poniendo el ordenador en suspensión.",
    },
    "lock": {
        "en": "Locking the screen now.",
        "hi": "स्क्रीन लॉक कर रही हूँ।",
        "de": "Ich sperre jetzt den Bildschirm.",
        "fr": "Je verrouille l’écran maintenant.",
        "es": "Bloqueando la pantalla ahora.",
    },
    "logout": {
        "en": "Logging you out now.",
        "hi": "आपको लॉग आउट कर रही हूँ।",
        "de": "Ich melde dich jetzt ab.",
        "fr": "Je vous déconnecte maintenant.",
        "es": "Cerrando tu sesión ahora.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
def _extract_number(text: str) -> int | None:
    m = re.search(r"\b(\d{1,3})\b", text or "")
    if not m:
        return None
    n = max(0, min(100, int(m.group(1))))
    return n

def _windows_key_event(vk_code: int) -> bool:
    """Try to send a Windows key event. Return True if attempted; False otherwise."""
    if platform.system().lower() != "windows":
        return False
    try:
        import ctypes  # local import to avoid issues on non-Windows
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────────────────
def handle_system_commands(command: str) -> None:
    speak, listen_command, set_volume, change_brightness, await_followup, logger = _lazy_utils()
    text = (command or "").lower()

    # 🛑 Exit (handled elsewhere typically, but included here if needed)
    exit_phrases = COMMAND_MAP.get("exit_app", [])
    if get_close_matches(text, exit_phrases, n=1, cutoff=0.7):
        from utils import begin_exit_with_goodbye_async
        begin_exit_with_goodbye_async()
        return

    # 🔊 Volume intents (increase/decrease/mute/max/set)
    all_volume_phrases, volume_intent_map = [], {}
    for intent, phrases in COMMAND_MAP.items():
        if "volume" in intent:
            for p in phrases:
                all_volume_phrases.append(p)
                volume_intent_map[p] = intent

    vol_match = get_close_matches(text, all_volume_phrases, n=1, cutoff=0.7)
    if vol_match:
        matched_intent = volume_intent_map[vol_match[0]]

        if matched_intent == "increase_volume":
            # Windows hardware key; if unavailable, just confirm verbally
            attempted = _windows_key_event(0xAF)  # VK_VOLUME_UP
            say_show(**_PROMPTS["vol_up_ok"], title="Nova")
            logger.info("[🔊] Volume increased (keybd_event=%s)", attempted)
            return

        if matched_intent == "decrease_volume":
            attempted = _windows_key_event(0xAE)  # VK_VOLUME_DOWN
            say_show(**_PROMPTS["vol_down_ok"], title="Nova")
            logger.info("[🔊] Volume decreased (keybd_event=%s)", attempted)
            return

        if matched_intent == "mute_volume":
            attempted = _windows_key_event(0xAD)  # VK_VOLUME_MUTE
            say_show(**_PROMPTS["vol_mute_ok"], title="Nova")
            logger.info("[🔊] Volume muted (keybd_event=%s)", attempted)
            return

        if matched_intent == "max_volume":
            # Try to hit the key several times on Windows; otherwise just confirm
            attempted = False
            if platform.system().lower() == "windows":
                for _ in range(10):
                    if _windows_key_event(0xAF):
                        attempted = True
            say_show(**_PROMPTS["vol_max_ok"], title="Nova")
            logger.info("[🔊] Volume set to maximum (keybd_event=%s)", attempted)
            return

        if matched_intent == "set_volume_to":
            n = _extract_number(text)
            if n is None:
                # SAY→SHOW prompt, then await (no re-say/show inside await)
                say_show(**_PROMPTS["ask_volume_level"], title="Nova")
                ans = await_followup(
                    _PROMPTS["ask_volume_level"]["en"],  # prompt key; we already spoke/shown localized
                    speak_fn=lambda *_a, **_k: None,
                    show_fn=lambda *_a, **_k: None,
                    listen_fn=listen_command,
                    allow_typed=True,
                    allow_voice=True,
                    timeout=18.0
                )
                if not ans:
                    say_show(**_PROMPTS["didnt_get_it"], title="Nova")
                    return
                n = _extract_number(ans)
                if n is None:
                    say_show(**_PROMPTS["need_0_100"], title="Nova")
                    return
            try:
                set_volume(n)
            except Exception as e:
                logger.warning("set_volume(%s) failed: %s", n, e)
            say_show(
                _PROMPTS["vol_set_to"]["en"].format(n=n),
                hi=_PROMPTS["vol_set_to"]["hi"].format(n=n),
                de=_PROMPTS["vol_set_to"]["de"].format(n=n),
                fr=_PROMPTS["vol_set_to"]["fr"].format(n=n),
                es=_PROMPTS["vol_set_to"]["es"].format(n=n),
                title="Nova",
            )
            logger.info("[🔊] Volume set to %s%%", n)
            return

    elif any(w in text for w in ["volume", "awaaz", "sound", "son", "ton", "volumen", "lautstärke"]):
        # Generic number in the sentence → direct set
        n = _extract_number(text)
        if n is not None:
            try:
                set_volume(n)
            except Exception as e:
                logger.warning("set_volume(%s) failed: %s", n, e)
            say_show(
                _PROMPTS["vol_set_to"]["en"].format(n=n),
                hi=_PROMPTS["vol_set_to"]["hi"].format(n=n),
                de=_PROMPTS["vol_set_to"]["de"].format(n=n),
                fr=_PROMPTS["vol_set_to"]["fr"].format(n=n),
                es=_PROMPTS["vol_set_to"]["es"].format(n=n),
                title="Nova",
            )
            logger.info("[🔊] Volume set to %s%% (generic path)", n)

    # 💡 Brightness intents (up/down/set)
    all_bright_phrases, bright_intent_map = [], {}
    for intent, phrases in COMMAND_MAP.items():
        if "brightness" in intent:
            for p in phrases:
                all_bright_phrases.append(p)
                bright_intent_map[p] = intent

    bright_match = get_close_matches(text, all_bright_phrases, n=1, cutoff=0.7)
    if bright_match:
        matched_intent = bright_intent_map[bright_match[0]]

        if matched_intent == "brightness_up":
            try:
                change_brightness(increase=True)
            except Exception as e:
                logger.warning("brightness_up failed: %s", e)
            say_show(**_PROMPTS["bright_up_ok"], title="Nova")
            logger.info("[💡] Brightness increased")
            return

        if matched_intent == "brightness_down":
            try:
                change_brightness(increase=False)
            except Exception as e:
                logger.warning("brightness_down failed: %s", e)
            say_show(**_PROMPTS["bright_down_ok"], title="Nova")
            logger.info("[💡] Brightness decreased")
            return

        if matched_intent == "set_brightness":
            n = _extract_number(text)
            if n is None:
                say_show(**_PROMPTS["ask_brightness_level"], title="Nova")
                ans = await_followup(
                    _PROMPTS["ask_brightness_level"]["en"],
                    speak_fn=lambda *_a, **_k: None,
                    show_fn=lambda *_a, **_k: None,
                    listen_fn=listen_command,
                    allow_typed=True,
                    allow_voice=True,
                    timeout=18.0
                )
                if not ans:
                    say_show(**_PROMPTS["didnt_get_it"], title="Nova")
                    return
                n = _extract_number(ans)
                if n is None:
                    say_show(**_PROMPTS["need_0_100"], title="Nova")
                    return
            try:
                change_brightness(level=n)
            except Exception as e:
                logger.warning("set_brightness(%s) failed: %s", n, e)
            say_show(
                _PROMPTS["bright_set_to"]["en"].format(n=n),
                hi=_PROMPTS["bright_set_to"]["hi"].format(n=n),
                de=_PROMPTS["bright_set_to"]["de"].format(n=n),
                fr=_PROMPTS["bright_set_to"]["fr"].format(n=n),
                es=_PROMPTS["bright_set_to"]["es"].format(n=n),
                title="Nova",
            )
            logger.info("[💡] Brightness set to %s%%", n)
            return

    elif any(w in text for w in ["brightness", "roshni", "light", "luminosité", "brillo", "helligkeit"]):
        n = _extract_number(text)
        if n is not None:
            try:
                change_brightness(level=n)
            except Exception as e:
                logger.warning("set_brightness(%s) failed: %s", n, e)
            say_show(
                _PROMPTS["bright_set_to"]["en"].format(n=n),
                hi=_PROMPTS["bright_set_to"]["hi"].format(n=n),
                de=_PROMPTS["bright_set_to"]["de"].format(n=n),
                fr=_PROMPTS["bright_set_to"]["fr"].format(n=n),
                es=_PROMPTS["bright_set_to"]["es"].format(n=n),
                title="Nova",
            )
            logger.info("[💡] Brightness set to %s%% (generic path)", n)

    # 💻 System actions — strict (no follow-ups for destructive actions)
    # We *SAY→SHOW* the confirmation, then execute the OS command.
    def _do(cmd_texts_key: str, os_call: str):
        say_show(**_PROMPTS[cmd_texts_key], title="Nova")
        os.system(os_call)

    if get_close_matches(text, COMMAND_MAP.get("shutdown_system", []), n=1, cutoff=0.7):
        _do("shutdown", "shutdown /s /t 1")
        return

    if get_close_matches(text, COMMAND_MAP.get("restart_system", []), n=1, cutoff=0.7):
        _do("restart", "shutdown /r /t 1")
        return

    if get_close_matches(text, COMMAND_MAP.get("sleep_system", []), n=1, cutoff=0.7):
        _do("sleep", "rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return

    if get_close_matches(text, COMMAND_MAP.get("lock_system", []), n=1, cutoff=0.7):
        _do("lock", "rundll32.exe user32.dll,LockWorkStation")
        return

    if get_close_matches(text, COMMAND_MAP.get("logout_system", []), n=1, cutoff=0.7):
        _do("logout", "shutdown /l")
        return
