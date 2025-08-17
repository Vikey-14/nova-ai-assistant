# 📢 wake_word_listener.py

import threading
import random
import json
import speech_recognition as sr
from difflib import get_close_matches
import os
import re
import time
import datetime
import sys
import csv
from pathlib import Path

# ====== Shared utils (PyInstaller-safe) ======
from utils import (
    load_settings,
    get_wake_mode,
    data_path,
    load_json_utf8,
    LOG_DIR,
    MIC_LOCK,
)
import utils  # so we can set utils.selected_language

# 🔁 Persist chosen language
from memory_handler import save_to_memory

# ====== Intents: single source of truth ======
from intents import (
    TELL_ME_TRIGGERS,
    POSITIVE_RESPONSES,
    LANG_CODE_TO_ALIAS,
    LANG_CODE_TO_FULL,
    is_followup_text,
    parse_category_from_choice,
    said_change_language,
    guess_language_code,
    SUPPORTED_LANGS,
    CURIOSITY_MENU
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
_wake_thread = None

# ✅ SSML probe flag
_ssml_probed = False

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
    "en": ["nova", "hey nova", "okay nova", "nova listen", "hello nova", "nova please", "nova are you there",
           "listen nova", "nova start", "wake up nova", "are you there nova"],
    "hi": ["नवा", "नवा सुनो", "सुनो नवा", "नवा स्टार्ट", "नवा कहा हो", "নवा शुरू हो जाओ", "नवा कृपया", "नवा मौजूद हो"],
    "fr": ["écoute nova", "salut nova", "nova écoute", "bonjour nova", "nova commence", "nova es-tu là", "nova réveille-toi"],
    "de": ["höre nova", "hallo nova", "nova hallo", "nova hör zu", "nova bitte", "nova bist du da", "nova wach auf"],
    "es": ["escucha nova", "hola nova", "nova escucha", "nova empieza", "nova estás ahí", "nova por favor", "nova despierta"]
}

# 🗣️ Bare wake word acks (kept here)
BARE_WAKE_ACKS = {
    "en": ["Yes?", "How can I help?", "I’m here — what’s on your mind?", "Standing by.", "Reporting to duty!"],
    "hi": ["हाँ जी?", "मैं आपकी कैसे मदद कर सकती हूँ?", "मैं यहाँ हूँ — क्या सोच रहे हैं?", "तैयार हूँ।", "सेवा के लिए हाज़िर हूँ!"],
    "fr": ["Oui ?", "Comment puis-je vous aider ?", "Je suis là — à quoi pensez-vous ?", "En attente.", "Prête pour le service !"],
    "de": ["Ja?", "Wie kann ich helfen?", "Ich bin hier — was haben Sie im Sinn?", "Bereit.", "Bereit zum Dienst!"],
    "es": ["¿Sí?", "¿Cómo puedo ayudarle?", "Estoy aquí — ¿en qué piensa?", "En espera.", "¡Lista para servir!"]
}

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
def speak_text(_speak_multilang, text: str, lang_code: str, log_command: str = None):
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
        mode = get_wake_mode()
        mode = (str(mode) or "").lower().replace("-", "_").strip()
        return mode in ("on", "always_on")
    except Exception:
        return False

# ✅ Voice change-language flow (self-contained, no circular import)
def run_change_language_flow(_speak_multilang, listen_command, current_lang: str) -> bool:
    prompt = {
        "en": "Sure — say the language you want: English, Hindi, German, French, or Spanish.",
        "hi": "ठीक है — वह भाषा बोलिए जिसमें आप बात करना चाहते हैं: अंग्रेज़ी, हिन्दी, जर्मन, फ्रेंच या स्पेनिश।",
        "fr": "D’accord — dites la langue que vous voulez : anglais, hindi, allemand, français ou espagnol.",
        "de": "Alles klar — sagen Sie die gewünschte Sprache: Englisch, Hindi, Deutsch, Französisch oder Spanisch.",
        "es": "De acuerdo — di el idioma que quieres: inglés, hindi, alemán, francés o español.",
    }.get(current_lang, "Sure — say the language you want: English, Hindi, German, French, or Spanish.")
    speak_text(_speak_multilang, prompt, current_lang, log_command="change_language_prompt")

    for _ in range(2):
        heard = (listen_command() or "").strip()
        if not heard:
            continue
        code = guess_language_code(heard)
        if code in SUPPORTED_LANGS:
            # persist + switch immediately
            utils.selected_language = code
            try:
                save_to_memory("language", code)
            except Exception:
                pass
            confirmations = {
                "en": ("Language set to English.", "en"),
                "hi": ("भाषा हिन्दी पर सेट कर दी गई है।", "hi"),
                "de": ("Sprache auf Deutsch eingestellt.", "de"),
                "fr": ("La langue a été définie sur le français.", "fr"),
                "es": ("El idioma se ha configurado en español.", "es"),
            }
            msg, lc = confirmations.get(code, ("Language updated.", code))
            speak_text(_speak_multilang, msg, lc, log_command="change_language_done")
            return True

    # fallback if not recognized
    speak_text(_speak_multilang, "I couldn't catch a supported language. Keeping the current one.", current_lang, log_command="change_language_failed")
    return False

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

            # 🔒 Single mic user
            with MIC_LOCK:
                with sr.Microphone() as source:
                    recognizer.dynamic_energy_threshold = True
                    recognizer.energy_threshold = 300
                    recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)

            lang_code = selected_language
            google_lang = _GOOGLE_LOCALE.get(lang_code, "en-US")
            try:
                said = recognizer.recognize_google(audio, language=google_lang).lower().strip()
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                file_log_csv("wake_sr_request_error", str(e), lang_code)
                time.sleep(0.4)
                continue

            candidates = WAKE_WORDS.get(lang_code, WAKE_WORDS["en"])
            matches = get_close_matches(said, candidates, n=1, cutoff=0.6)

            if matches:
                phrase = matches[0]
                log_interaction("wake_word_detected", phrase, lang_code)
                file_log_csv("wake_word_detected", phrase, lang_code)

                # Wake + follow-up or change-language in one go
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
                    speak_text(_speak_multilang, response, lang_code, log_command="wake_ack")

                    user_cmd = (listen_command() or "").lower().strip()

                    # Follow-up / change-language after bare wake
                    if is_followup_text(user_cmd, lang_code):
                        serve_followup(_speak_multilang, log_interaction, lang_code)
                        continue
                    if said_change_language(user_cmd):
                        run_change_language_flow(_speak_multilang, listen_command, lang_code)
                        continue

                    # Curiosity menu?
                    if any(trigger in user_cmd for trigger in TELL_ME_TRIGGERS.get(lang_code, [])):
                        speak_text(_speak_multilang, CURIOSITY_MENU.get(lang_code, CURIOSITY_MENU["en"]), lang_code, log_command="curiosity_menu")
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

                    if any(trigger in said for trigger in TELL_ME_TRIGGERS.get(lang_code, [])):
                        speak_text(_speak_multilang, CURIOSITY_MENU.get(lang_code, CURIOSITY_MENU["en"]), lang_code, log_command="curiosity_menu")
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
                _speak_multilang, log_interaction, lang_code, _ = get_utils()
                _speak_multilang(**{lang_code: "Sorry, I had a small issue — try again."})
                log_interaction("wake_error", str(e), lang_code)
                file_log(f"ERROR | {e}")
                file_log_csv("wake_error", str(e), lang_code)
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
    _stop_event.set()
    from utils import log_interaction, selected_language
    log_interaction("wake_listener", "stopped via toggle", selected_language)  