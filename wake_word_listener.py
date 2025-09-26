# 📢 wake_word_listener.py

from __future__ import annotations

import threading
import random
import speech_recognition as sr
from difflib import get_close_matches
import os
import re
import time
import datetime
import csv
from typing import Optional

# ====== Shared utils (PyInstaller-safe) ======
from utils import (
    load_settings,
    is_wake_paused,
    data_path,
    load_json_utf8,
    LOG_DIR,
    MIC_LOCK,                 # 🔒 shared mic lock (must be the same as utils.listen_command)
    LANGUAGE_FLOW_ACTIVE,
    set_language_flow,
)
import utils  # so we can set utils.selected_language

# 🔁 Persist chosen language
from memory_handler import save_to_memory

# ====== SAY→SHOW (central helper) ======
from say_show import say_show  # Speak first, then show bubble (multilingual)

def say_show_lang(text: str, lang_code: str, title: str = "Nova"):
    """
    Speak & then show `text` in the current UI language with an English fallback.
    Keeps all SAY→SHOW behavior centralized in say_show.py.
    """
    kwargs = {"title": title}
    kwargs[lang_code] = text
    kwargs["en"] = text
    say_show(**kwargs)

# ====== Intents: single source of truth ======
from intents import (
    TELL_ME_TRIGGERS,
    POSITIVE_RESPONSES,
    LANG_CODE_TO_FULL,
    is_followup_text,
    parse_category_from_choice,
    said_change_language,
    guess_language_code,
    SUPPORTED_LANGS,
    CURIOSITY_MENU,
    # 🔹 unified language texts
    get_language_prompt_text,
    get_invalid_language_voice_to_typed,   # final voice→typed fallback (existing)
    get_language_already_set_line,         # “<Lang> is already set…” (localized)
    get_invalid_language_voice_retry,      # “Please say OR type…” (keeps listening)
)

# =========================
# 🔊 TTS Delivery Settings
# =========================
SUPPORTS_SSML = False
SSML_VENDOR = "generic"  # "generic" | "polly" | "azure" | "google"

ELLIPSIS_MS = 250
PAUSE_MS = 700

# ✅ Thread control
_stop_event = threading.Event()
_wake_thread: Optional[threading.Thread] = None

# ✅ SSML probe flag
_ssml_probed = False

# === SR quiet-window gate
__sr_quiet_until = 0.0


def _sr_quiet(ms: int | float):
    """Keep SR/wake from arming for the given number of milliseconds."""
    import time as _t
    global __sr_quiet_until
    __sr_quiet_until = max(__sr_quiet_until, _t.time() + max(0.0, float(ms)) / 1000.0)


def _sr_is_quiet() -> bool:
    import time as _t
    return _t.time() < __sr_quiet_until


# ✅ Lazy import of runtime helpers (avoid circulars)
def get_utils():
    # _speak_multilang(**{lang_code: text}, tts_format="text"/"ssml", log_command="...")
    # log_interaction(event, detail, lang)
    # selected_language -> "en" | "hi" | "fr" | "de" | "es"
    # listen_command() -> str
    from utils import _speak_multilang, log_interaction, selected_language, listen_command
    return _speak_multilang, log_interaction, selected_language, listen_command


def _process_command_proxy(*args, **kwargs):
    from core_engine import process_command
    return process_command(*args, **kwargs)


# 🌍 Map to Google SR locales
_GOOGLE_LOCALE = {
    "en": "en-US",
    "hi": "hi-IN",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
}

# 🌍 Wake words per language (wake-specific; keep here)
WAKE_WORDS = {
    "en": [
        "nova", "hey nova", "okay nova", "ok nova", "nova listen", "hello nova",
        "nova please", "please nova", "nova are you there",
        "listen nova", "nova start", "wake up nova", "are you there nova"
    ],
    "hi": ["नोवा", "नोवा सुनो", "सुनो नोवा", "नोवा शुरू हो जाओ", "नोवा कहाँ हो", "नोवा कृपया", "क्या आप यहाँ हैं नोवा", "नोवा मौजूद हो"],
    "fr": ["écoute nova", "salut nova", "nova écoute", "bonjour nova", "nova commence", "nova es-tu là", "nova réveille-toi"],
    "de": ["höre nova", "hallo nova", "nova hallo", "nova hör zu", "nova bitte", "nova bist du da", "nova wach auf"],
    "es": ["escucha nova", "hola nova", "nova escucha", "nova empieza", "nova estás ahí", "nova por favor", "nova despierta"],
}

# 🗣️ Bare wake word acks (kept here)
BARE_WAKE_ACKS = {
    "en": ["Yes?", "How can I help?", "I’m here — what’s on your mind?", "Standing by.", "Reporting to duty!"],
    "hi": ["हाँ जी?", "मैं आपकी कैसे मदद कर सकती हूँ?", "मैं यहाँ हूँ — क्या सोच रहे हैं?", "तैयार हूँ।", "सेवा के लिए हाज़िर हूँ!"],
    "fr": ["Oui ?", "Comment puis-je vous aider ?", "Je suis là — à quoi pensez-vous ?", "En attente.", "Prête pour le service !"],
    "de": ["Ja?", "Wie kann ich helfen?", "Ich bin hier — was haben Sie im Sinn?", "Bereit.", "Bereit zum Dienst!"],
    "es": ["¿Sí?", "¿Cómo puedo ayudarle?", "Estoy aquí — ¿en qué piensa?", "En espera.", "¡Lista para servir!"],
}

# 🔊 Flexible hotword prefix (supports “please nova…”, “hi nova…”, etc.)
WAKE_PREFIX_RE = re.compile(
    r"^(?:(?:hey|ok|okay|hi|hello|yo|please|pls)\s+)?nova\b[,\s]*",
    re.I
)

# ===========================
# 🧾 Logging (shared folder)
# ===========================
LOG_TXT_PATH = LOG_DIR / "interaction_log.txt"
LOG_CSV_PATH = LOG_DIR / "interaction_log.csv"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_lock = threading.Lock()


def file_log(entry: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {entry}\n"
    with _log_lock:
        with open(LOG_TXT_PATH, "a", encoding="utf-8") as f:
            f.write(line)


def file_log_csv(event: str, detail: str = "", lang: str = ""):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = ["timestamp", "event", "detail", "lang"]
    with _log_lock:
        new_file = not LOG_CSV_PATH.exists()
        with open(LOG_CSV_PATH, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(header)
            w.writerow([ts, event, detail, lang])


# ========== TTS capability detection
def detect_tts_vendor_from_env():
    if os.environ.get("AWS_REGION") or os.environ.get("AWS_ACCESS_KEY_ID"):
        return "polly"
    if os.environ.get("AZURE_TTS_KEY") or os.environ.get("SPEECH_KEY"):
        return "azure"
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return "google"
    return None


def init_tts_capabilities():
    global SUPPORTS_SSML, SSML_VENDOR
    cfg = load_settings()
    if "supports_ssml" in cfg:
        SUPPORTS_SSML = bool(cfg["supports_ssml"])
    vendor = cfg.get("tts_vendor")
    if isinstance(vendor, str) and vendor.strip():
        SSML_VENDOR = vendor.strip().lower()

    if not vendor:
        env_vendor = detect_tts_vendor_from_env()
        if env_vendor:
            SSML_VENDOR = env_vendor
            SUPPORTS_SSML = True

    file_log(f"TTS CAPABILITIES | supports_ssml={SUPPORTS_SSML} vendor={SSML_VENDOR}")
    file_log_csv("tts_capabilities", f"supports_ssml={SUPPORTS_SSML} vendor={SSML_VENDOR}", "")


# 📁 Curiosity data
def load_curiosity_data():
    try:
        return load_json_utf8(data_path("curiosity_data.json"))
    except Exception as e:
        print(f"⚠ Could not load curiosity_data.json: {e}")
        return {}


CURIOSITY_DATA = load_curiosity_data()

# ================ SSML converter
def to_ssml(text: str, vendor: str = "generic") -> str:
    def _esc(s: str) -> str:
        if s is None:
            return ""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    s = _esc(text)
    s = re.sub(r"\(pause\)", f'<break time="{PAUSE_MS}ms"/>', s, flags=re.I)
    s = s.replace("…", f'<break time="{ELLIPSIS_MS}ms"/>')

    if vendor.lower() == "polly":
        opened_prosody = False
        opened_amazon = False
        s, n = re.subn(r"\(whisper tone\)", '<amazon:effect name="whispered">', s, flags=re.I); opened_amazon |= n > 0
        s, n = re.subn(r"\(slower\)", '<prosody rate="slow">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(slightly deeper tone\)", '<prosody pitch="-2st">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(slightly faster\)", '<prosody rate="fast">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(warmer tone\)", '<prosody pitch="-1st" volume="medium">', s, flags=re.I); opened_prosody |= n > 0
        if opened_prosody or opened_amazon:
            closing_seq = ("</prosody>" if opened_prosody else "") + ("</amazon:effect>" if opened_amazon else "")
            s = re.sub(r"([\.!?।])", r"\1" + closing_seq, s)
    else:
        opened_prosody = False
        s, n = re.subn(r"\(whisper tone\)", '<prosody volume="x-soft">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(slower\)", '<prosody rate="slow">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(slightly deeper tone\)", '<prosody pitch="-2st">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(slightly faster\)", '<prosody rate="fast">', s, flags=re.I); opened_prosody |= n > 0
        s, n = re.subn(r"\(warmer tone\)", '<prosody pitch="-1st" volume="medium">', s, flags=re.I); opened_prosody |= n > 0
        if opened_prosody:
            s = re.sub(r"([\.!?।])", r"\1</prosody>", s)

    return f"<speak>{s}</speak>"


# 🔎 Runtime SSML probe
def _probe_ssml_support(_speak_multilang, lang_code: str) -> bool:
    try:
        test_ssml = "<speak><break time='1ms'/></speak>"
        _speak_multilang(**{lang_code: test_ssml}, tts_format="ssml", log_command="ssml_probe")
        return True
    except Exception:
        return False


# 🔧 TTS helpers
def speak_text(_speak_multilang, text: str, lang_code: str, log_command: str | None = None):
    kwargs = {lang_code: text}
    if log_command:
        _speak_multilang(log_command=log_command, **kwargs)
    else:
        _speak_multilang(**kwargs)


def speak_dramatic_fun_fact(_speak_multilang, text: str, lang_code: str):
    if SUPPORTS_SSML:
        try:
            ssml = to_ssml(text, vendor=SSML_VENDOR)
            _speak_multilang(**{lang_code: ssml}, tts_format="ssml", log_command="fun_fact")
            return
        except Exception:
            pass
    cleaned = re.sub(
        r"\((?:slower|whisper tone|warmer tone|slightly faster|slightly deeper tone)\)",
        "",
        text,
        flags=re.I
    )
    chunks = re.split(r"\(pause\)", cleaned, flags=re.I)
    for ci, chunk in enumerate(chunks):
        parts = chunk.split("…")
        for pi, p in enumerate(parts):
            p = p.strip()
            if p:
                speak_text(_speak_multilang, p, lang_code, log_command="fun_fact")
            if pi < len(parts) - 1:
                time.sleep(ELLIPSIS_MS / 1000.0)
        if ci < len(chunks) - 1:
            time.sleep(PAUSE_MS / 1000.0)


# ================ Curiosity data helpers
def get_items_for_category(category_key: str, lang_code: str):
    cat = CURIOSITY_DATA.get(category_key, {})
    if not isinstance(cat, dict):
        return []
    full_name = LANG_CODE_TO_FULL.get(lang_code, "english")
    candidates = [lang_code, full_name]  # e.g. ["hi", "hindi"]
    result = []
    for key in sorted(cat.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
        entry = cat[key]
        if not isinstance(entry, dict):
            continue
        text = None
        for lk in candidates:
            if lk in entry:
                text = entry[lk]
                break
        if text is None:
            for lk in ["en", "english"]:
                if lk in entry:
                    text = entry[lk]
                    break
        if isinstance(text, str):
            result.append(text)
    return result


last_curiosity_category = None
used_curiosity_items = {}


def ensure_used_state(lang_code: str, category_key: str):
    if lang_code not in used_curiosity_items:
        used_curiosity_items[lang_code] = {}
    if category_key not in used_curiosity_items[lang_code]:
        used_curiosity_items[lang_code][category_key] = set()


def pick_next_item(category_key: str, lang_code: str):
    items = get_items_for_category(category_key, lang_code)
    if not items:
        return None, None
    ensure_used_state(lang_code, category_key)
    used = used_curiosity_items[lang_code][category_key]
    available_indices = [i for i in range(len(items)) if i not in used]
    if not available_indices:
        used.clear()
        available_indices = list(range(len(items)))
    idx = random.choice(available_indices)
    used.add(idx)
    return items[idx], idx


# 🎙 Serve a curiosity item
def serve_curiosity(_speak_multilang, log_interaction, category_key: str, lang_code: str):
    global last_curiosity_category
    text, idx = pick_next_item(category_key, lang_code)
    if not text:
        speak_text(_speak_multilang, "I don’t have anything in that category right now.", lang_code, log_command=f"{category_key}_empty")
        file_log(f"Curiosity EMPTY | category={category_key} lang={lang_code}")
        file_log_csv("curiosity_empty", f"{category_key}:{lang_code}", lang_code)
        log_interaction("curiosity_empty", f"{category_key}:{lang_code}", lang_code)
        return
    last_curiosity_category = category_key
    if category_key == "fun_facts":
        speak_dramatic_fun_fact(_speak_multilang, text, lang_code)
    else:
        speak_text(_speak_multilang, text, lang_code, log_command=category_key)
    file_log(f"Curiosity | category={category_key} lang={lang_code} idx={idx} text={text}")
    file_log_csv("curiosity_item", f"{category_key}:{idx}", lang_code)
    log_interaction("curiosity_item", f"{category_key}:{idx}", lang_code)


def serve_followup(_speak_multilang, log_interaction, lang_code: str):
    if not last_curiosity_category:
        speak_text(_speak_multilang, "Pick a category first — then ask for another one.", lang_code)
        return
    serve_curiosity(_speak_multilang, log_interaction, last_curiosity_category, lang_code)


# ✅ Wake toggle
def _wake_enabled() -> bool:
    try:
        from utils import get_wake_mode, load_settings
        return bool(get_wake_mode())
    except Exception:
        try:
            settings = load_settings()
            return bool(settings.get("wake_mode", True))
        except Exception:
            return False


def run_change_language_flow(_speak_multilang, listen_command, current_lang: str) -> bool:
    """
    Voice-only change-language flow used from Wake/PTT:
    - Prompts using intents.py (no local strings)
    - If user repeats the current language → speak 'already set' (intents) and keep listening
    - If unsupported → speak localized 'say OR type' retry (intents) and keep listening
    - On success → delegate confirmation + GUI tint to main.py
    - After several failed attempts → fall back to voice→typed line (intents)
    """
    try:
        set_language_flow(True, suppress_ms=8000)
    except Exception:
        pass

    try:
        # SAY→SHOW the main prompt from intents
        prompt = get_language_prompt_text(current_lang)
        say_show_lang(prompt, current_lang, title="Nova")

        MAX_TRIES = 4
        tries = 0

        while tries < MAX_TRIES:
            heard = (listen_command() or "").strip()
            tries += 1

            if not heard:
                if tries < MAX_TRIES:
                    retry_line = get_invalid_language_voice_retry(current_lang)
                    speak_text(_speak_multilang, retry_line, current_lang, log_command="lang_retry_silent")
                continue

            code = guess_language_code(heard)

            if code in SUPPORTED_LANGS:
                # If same language as current → announce and keep listening
                cur = (utils.selected_language or current_lang)
                if code == cur:
                    already = get_language_already_set_line(code, current_lang)  # (lang_code, ui_lang)
                    speak_text(_speak_multilang, already, current_lang, log_command="lang_already_set")
                    if tries < MAX_TRIES:
                        continue
                    break

                # Persist & mirror to settings
                utils.selected_language = code
                try:
                    save_to_memory("language", code)
                    try:
                        s = utils.load_settings()
                        s["language"] = code
                        utils.save_settings(s)
                    except Exception:
                        pass
                except Exception:
                    pass

                # Hand off final announce + GUI tint to main.py
                try:
                    import main as _main
                    _main._announce_language_set(code, after_speech=lambda c=code: _main._handoff_after_language(c))
                except Exception:
                    # Minimal neutral fallback only if main helpers are unavailable
                    speak_text(_speak_multilang, "Language updated.", code, log_command="change_language_done")
                    _sr_quiet(6500)

                return True

            # Unsupported → localized retry (keeps listening while tries remain)
            if tries < MAX_TRIES:
                retry_line = get_invalid_language_voice_retry(current_lang)
                speak_text(_speak_multilang, retry_line, current_lang, log_command="lang_retry_unsupported")
                continue

        # Out of tries → localized voice→typed fallback from intents
        invalid_line = get_invalid_language_voice_to_typed(current_lang)
        say_show_lang(invalid_line, current_lang, title="Nova")
        return False

    finally:
        try:
            set_language_flow(False)
        except Exception:
            pass

# === NEW: short Vosk window for wake (reuse the same engine as post-wake)
def _listen_short_vosk(listen_command, timeout_s: float = 4.0, phrase_time_limit_s: float = 4.0) -> str:
    """
    Use Vosk-streaming in a short window for hotword+command (“Nova, tell me something”).
    Returns lowercased, stripped text or "".
    """
    try:
        said = listen_command(
            skip_tts_gate=True,
            timeout_s=timeout_s,
            phrase_time_limit_s=phrase_time_limit_s
        )
        return (said or "").lower().strip()
    except Exception:
        return ""


# 🔁 Wake loop
def _wake_loop():
    init_tts_capabilities()
    _speak_multilang, log_interaction, selected_language, listen_command = get_utils()

    # 🔎 SSML probe once
    global SUPPORTS_SSML, SSML_VENDOR, _ssml_probed
    if not _ssml_probed and not SUPPORTS_SSML:
        if _probe_ssml_support(_speak_multilang, selected_language):
            SUPPORTS_SSML = True
            SSML_VENDOR = SSML_VENDOR or "generic"
            file_log("SSML PROBE | success → enabling SSML (generic)")
            file_log_csv("ssml_probe", "enabled_generic", selected_language)
        else:
            file_log("SSML PROBE | failed → staying in text mode")
            file_log_csv("ssml_probe", "disabled", selected_language)
        _ssml_probed = True

    recognizer = sr.Recognizer()

    print("👂 Wake loop started. Waiting for wake word...")
    while not _stop_event.is_set():
        try:
            if not _wake_enabled():
                return

            if LANGUAGE_FLOW_ACTIVE:
                time.sleep(0.15)
                continue

            if _sr_is_quiet():
                time.sleep(0.12)
                continue

            if is_wake_paused():
                time.sleep(0.05)
                continue

            # --- VOSK-FIRST HOTWORD CAPTURE (no MIC_LOCK here; utils.listen_command manages it) ---
            said = _listen_short_vosk(listen_command, timeout_s=3.5, phrase_time_limit_s=3.5)

            # --- Fallback: Google SR only if Vosk heard nothing ---
            if not said:
                with MIC_LOCK:
                    if _stop_event.is_set() or not _wake_enabled():
                        break
                    with sr.Microphone() as source:
                        recognizer.dynamic_energy_threshold = True
                        recognizer.energy_threshold = 300
                        recognizer.adjust_for_ambient_noise(source, duration=0.3)
                        if _stop_event.is_set() or not _wake_enabled():
                            break
                        try:
                            audio = recognizer.listen(
                                source,
                                timeout=1.5,
                                phrase_time_limit=3.8
                            )
                        except sr.WaitTimeoutError:
                            if _stop_event.is_set() or not _wake_enabled():
                                break
                            continue

                if _stop_event.is_set() or not _wake_enabled():
                    break

                lang_code = selected_language
                google_lang = _GOOGLE_LOCALE.get(lang_code, "en-US")
                try:
                    said = recognizer.recognize_google(audio, language=google_lang).lower().strip()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    file_log_csv("wake_sr_request_error", str(e), lang_code)
                    time.sleep(0.25)
                    continue

            # 0) Flexible hotword prefix: "please/ok/hi ... nova <command>"
            m = WAKE_PREFIX_RE.match(said)
            if m:
                remainder = said[m.end():].strip(" ,")
                if remainder:
                    if is_followup_text(remainder, selected_language):
                        serve_followup(_speak_multilang, log_interaction, selected_language)
                        continue
                    if said_change_language(remainder):
                        run_change_language_flow(_speak_multilang, listen_command, selected_language)
                        continue
                    if any(trigger in remainder for trigger in TELL_ME_TRIGGERS.get(selected_language, TELL_ME_TRIGGERS["en"])):
                        # SAY→SHOW the curiosity menu
                        say_show_lang(CURIOSITY_MENU.get(selected_language, CURIOSITY_MENU["en"]), selected_language, title="Nova")
                        user_choice = (listen_command() or "").lower().strip()
                        if user_choice in POSITIVE_RESPONSES.get(selected_language, POSITIVE_RESPONSES["en"]):
                            category_key = random.choice(["deep_life_insight", "fun_facts", "jokes", "cosmic_riddles_or_quotes", "witty_poems"])
                            serve_curiosity(_speak_multilang, log_interaction, category_key, selected_language)
                        else:
                            chosen_category = parse_category_from_choice(user_choice, selected_language)
                            if chosen_category:
                                serve_curiosity(_speak_multilang, log_interaction, chosen_category, selected_language)
                            else:
                                _process_command_proxy(user_choice)
                        continue
                    chosen_category = parse_category_from_choice(remainder, selected_language)
                    if chosen_category:
                        serve_curiosity(_speak_multilang, log_interaction, chosen_category, selected_language)
                    else:
                        _process_command_proxy(remainder)
                    continue  # handled via prefix path
                # If no remainder → treat like bare wake (“Yes?” then listen)

            # 1) Legacy candidate matching
            lang_code = selected_language
            candidates = WAKE_WORDS.get(lang_code, WAKE_WORDS["en"])
            matches = get_close_matches(said, candidates, n=1, cutoff=0.6)

            if matches:
                phrase = matches[0]
                log_interaction("wake_word_detected", phrase, lang_code)
                file_log_csv("wake_word_detected", phrase, lang_code)

                # Follow-up or change-language in one go
                if is_followup_text(said, lang_code):
                    serve_followup(_speak_multilang, log_interaction, lang_code)
                    continue
                if said_change_language(said):
                    run_change_language_flow(_speak_multilang, listen_command, lang_code)
                    continue

                # Bare wake → ack → capture next utterance
                if said in candidates:
                    ack_list = BARE_WAKE_ACKS.get(lang_code, BARE_WAKE_ACKS["en"])
                    response = random.choice(ack_list)
                    # keep acks voice-only to avoid bubble spam
                    speak_text(_speak_multilang, response, lang_code, log_command="wake_ack")

                    user_cmd = (listen_command() or "").lower().strip()

                    if is_followup_text(user_cmd, lang_code):
                        serve_followup(_speak_multilang, log_interaction, lang_code)
                        continue
                    if said_change_language(user_cmd):
                        run_change_language_flow(_speak_multilang, listen_command, lang_code)
                        continue

                    if any(trigger in user_cmd for trigger in TELL_ME_TRIGGERS.get(lang_code, TELL_ME_TRIGGERS["en"])):
                        # SAY→SHOW menu
                        say_show_lang(CURIOSITY_MENU.get(lang_code, CURIOSITY_MENU["en"]), lang_code, title="Nova")
                        user_choice = (listen_command() or "").lower().strip()

                        if user_choice in POSITIVE_RESPONSES.get(lang_code, POSITIVE_RESPONSES["en"]):
                            category_key = random.choice(["deep_life_insight", "fun_facts", "jokes", "cosmic_riddles_or_quotes", "witty_poems"])
                            serve_curiosity(_speak_multilang, log_interaction, category_key, lang_code)
                            continue

                        chosen_category = parse_category_from_choice(user_choice, lang_code)
                        if chosen_category:
                            serve_curiosity(_speak_multilang, log_interaction, chosen_category, lang_code)
                        else:
                            _process_command_proxy(user_choice)
                    else:
                        _process_command_proxy(user_cmd)

                else:
                    # Not a bare wake; maybe direct category, "tell me something", follow-up, or change-language
                    if is_followup_text(said, lang_code):
                        serve_followup(_speak_multilang, log_interaction, lang_code)
                        continue

                    if said_change_language(said):
                        run_change_language_flow(_speak_multilang, listen_command, lang_code)
                        continue

                    if any(trigger in said for trigger in TELL_ME_TRIGGERS.get(lang_code, TELL_ME_TRIGGERS["en"])):
                        # SAY→SHOW menu
                        say_show_lang(CURIOSITY_MENU.get(lang_code, CURIOSITY_MENU["en"]), lang_code, title="Nova")
                        user_choice = (listen_command() or "").lower().strip()

                        if user_choice in POSITIVE_RESPONSES.get(lang_code, POSITIVE_RESPONSES["en"]):
                            category_key = random.choice(["deep_life_insight", "fun_facts", "jokes", "cosmic_riddles_or_quotes", "witty_poems"])
                            serve_curiosity(_speak_multilang, log_interaction, category_key, lang_code)
                        else:
                            chosen_category = parse_category_from_choice(user_choice, lang_code)
                            if chosen_category:
                                serve_curiosity(_speak_multilang, log_interaction, chosen_category, lang_code)
                            else:
                                _process_command_proxy(user_choice)
                        continue

                    chosen_category = parse_category_from_choice(said, lang_code)
                    if chosen_category:
                        serve_curiosity(_speak_multilang, log_interaction, chosen_category, lang_code)
                    else:
                        _process_command_proxy(said)

        except sr.WaitTimeoutError:
            continue
        except Exception as e:
            try:
                if not LANGUAGE_FLOW_ACTIVE:
                    # brief error spoken; if you want this in chat too, swap to say_show_lang(...)
                    _speak_multilang, log_interaction, lang_code, _ = get_utils()
                    _speak_multilang(**{lang_code: "Sorry, I had a small issue — try again."})
                log_interaction("wake_error", str(e), (selected_language or "en"))
                file_log(f"ERROR | {e}")
                file_log_csv("wake_error", str(e), (selected_language or "en"))
            except Exception:
                pass
            continue


# 🔌 Start listener
def start_wake_listener_thread():
    global _wake_thread
    if _wake_thread and _wake_thread.is_alive():
        return
    if not _wake_enabled():
        return
    _stop_event.clear()
    _wake_thread = threading.Thread(target=_wake_loop, daemon=True)
    _wake_thread.start()


# 🛑 Stop listener
def stop_wake_listener_thread():
    global _wake_thread
    _stop_event.set()
    try:
        from utils import log_interaction, selected_language
        log_interaction("wake_listener", "stopped via toggle", selected_language)
    except Exception:
        pass

    t = _wake_thread
    if t and t.is_alive():
        try:
            t.join(timeout=1.8)
        except Exception:
            pass
    _wake_thread = None


# ⏳ Helper for callers: wait until the wake thread is gone (mic quiet)
def wait_for_wake_quiet(timeout: float = 1.2):
    """Block briefly until the wake thread is stopped (mic is free)."""
    end = time.time() + max(0.1, timeout)
    t = _wake_thread
    while t and t.is_alive() and time.time() < end:
        time.sleep(0.05)
