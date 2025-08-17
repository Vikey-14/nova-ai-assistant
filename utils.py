# utils.py
from __future__ import annotations

# Sentinel so main.py can prefer THIS module if multiple "utils" exist
IS_NOVA_UTILS = True

# ── run-before-anything: keep Matplotlib quiet + cache local ───────────────────
import os, sys
from pathlib import Path

def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(meipass) if meipass else Path(sys.executable).parent
    return Path(__file__).resolve().parent

APP_DIR = _app_dir()
mpl_cfg = APP_DIR / ".mplcache"
try:
    mpl_cfg.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cfg))
except Exception:
    pass
try:
    import logging as _logging
    _logging.getLogger("matplotlib").setLevel(_logging.ERROR)
except Exception:
    pass

# ── stdlib
import json, csv, tempfile, logging, threading, re
from datetime import datetime
from typing import Callable, Optional, Any, Union, Iterable
from difflib import SequenceMatcher

# ── third-party (SAFE at top-level)
import pyttsx3
import speech_recognition as sr
# ⚠️ Heavy/optional deps are imported lazily where used:
#    wmi, gTTS, playsound, comtypes/ctypes, pycaw.pycaw

# =============================================================================
# APP BASE & PATH HELPERS
# =============================================================================

def _app_base_dir() -> Path:
    """Dev: folder containing this file • Frozen: dist/NOVA/ next to NOVA.exe"""
    return APP_DIR

BASE_DIR: Path = _app_base_dir()

def pkg_path(*parts: str) -> Path:
    return BASE_DIR.joinpath(*parts)

def data_path(name: str) -> Path:
    return pkg_path("data", name)

def handlers_path(name: str) -> Path:
    return pkg_path("handlers", name)

def resource_path(relative_path: str) -> str:
    """
    Resolve a resource path across dev, PyInstaller onedir, and onefile.
    Also checks an optional '_internal' folder PyInstaller sometimes uses.
    Accepts paths like 'assets/nova_face_glow.png' or 'nova_icon.ico'.
    """
    p = Path(relative_path)

    # Absolute path that exists? return it.
    if p.is_absolute() and p.exists():
        return str(p)

    meipass = getattr(sys, "_MEIPASS", None)
    roots = [BASE_DIR, BASE_DIR / "_internal"]
    if meipass:
        m = Path(meipass)
        roots += [m, m / "_internal"]

    # Try as-is under each root (preserves subfolders like 'assets/...'):
    candidates = [r / p for r in roots]

    # Also try common buckets by filename (if caller passed just a name)
    name_only = p.name
    for r in roots:
        candidates += [
            r / "assets" / name_only,
            r / "data" / name_only,
            r / "handlers" / name_only,
            r / name_only,  # top-level next to NOVA.exe
        ]

    for c in candidates:
        if c.exists():
            return str(c)

    # Fallback
    return str(BASE_DIR / p)

# =============================================================================
# BUILD / VERSION ID (for "show tray tip once per build")
# =============================================================================

def current_build_id() -> str:
    """
    Returns a string that changes when the build changes.
    Frozen (EXE): uses NOVA.exe mtime; Dev: uses this file's mtime.
    """
    try:
        if getattr(sys, "frozen", False):
            exe = Path(sys.executable)
            return f"exe-{int(exe.stat().st_mtime_ns)}"
        src = Path(__file__).resolve()
        return f"src-{int(src.stat().st_mtime_ns)}"
    except Exception:
        # last-resort: fallback to today (changes rarely, but avoids crashes)
        return datetime.now().strftime("fallback-%Y%m%d")

# =============================================================================
# JSON / TEXT HELPERS
# =============================================================================

def load_json_utf8(path: Union[str, Path]):
    """Robust JSON loader that searches common locations in frozen builds."""
    p = Path(path)

    # 1) Exact path
    try:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    name = p.name
    meipass = getattr(sys, "_MEIPASS", None)
    roots = [BASE_DIR, BASE_DIR / "_internal"]
    if meipass:
        roots += [Path(meipass), Path(meipass) / "_internal"]

    candidates = []
    if not p.is_absolute():
        for r in roots:
            candidates.append(r / p)
    for r in roots:
        candidates.append(r / "handlers" / name)
        candidates.append(r / "data" / name)
        candidates.append(r / name)

    tried = []
    for c in candidates:
        try:
            tried.append(str(c))
            if c.exists():
                with c.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue

    msg = "Resource not found: {}\nLooked in:\n{}".format(path, "\n".join(f" - {t}" for t in tried))
    raise FileNotFoundError(msg)

def read_text_utf8(path: Union[str, Path]) -> str:
    return Path(path).read_text(encoding="utf-8")

# =============================================================================
# LOGGER (writes next to NOVA.exe: dist/NOVA/logs/)
# =============================================================================

LOG_DIR = pkg_path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("NOVA")
logger.setLevel(logging.INFO)

_log_file = LOG_DIR / "nova_logs.txt"
try:
    _file_handler = logging.FileHandler(_log_file, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
    if not logger.handlers:
        logger.addHandler(_file_handler)
    logger.propagate = False
except Exception:
    pass

# =============================================================================
# MODE STATE (for GUI toggles)
# =============================================================================

_mode_state = {"math": False, "plot": False, "physics": False, "chemistry": False}

def set_mode_state(name: str, enabled: bool):
    try:
        key = str(name).lower()
        if key in _mode_state:
            _mode_state[key] = bool(enabled)
    except Exception:
        pass

def get_mode_state(name: str) -> bool:
    try:
        return bool(_mode_state.get(str(name).lower(), False))
    except Exception:
        return False

# =============================================================================
# LANGUAGE / SETTINGS / TTS
# =============================================================================

language_voice_map = {
    "en": "david",
    "hi": "hindi",
    "de": "german",
    "fr": "french",
    "es": "spanish"
}

# Selected language code (persisted via settings.json)
selected_language = "en"

def _settings_path() -> Path:
    return pkg_path("settings.json")

_DEFAULT_SETTINGS = {
    "language": "en",
    # per your preference: ON by default on first boot
    "wake_mode": "on"
}

def load_settings() -> dict:
    """
    Quiet, robust settings loader. If missing, create with defaults.
    Never prints warnings to stdout; just returns a dict.
    """
    p = _settings_path()
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                json.dump(_DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
            return dict(_DEFAULT_SETTINGS)
        except Exception as e:
            logger.error(f"create default settings failed: {e}")
            return dict(_DEFAULT_SETTINGS)

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # ensure required keys exist
            out = dict(_DEFAULT_SETTINGS)
            if isinstance(data, dict):
                out.update(data)
            return out
    except Exception as e:
        logger.error(f"load settings failed: {e}")
        return dict(_DEFAULT_SETTINGS)

def save_settings(data: dict):
    try:
        p = _settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"save settings failed: {e}")

# --- Make TTS read abbreviations naturally ---
def _normalize_for_tts(text: str) -> str:
    lang = (selected_language or "en").lower()
    rules = {
        "en": [(r"\b[eE]\.?g\.?\b", "for example"), (r"\b[iI]\.?e\.?\b", "that is")],
        "hi": [(r"\b[eE]\.?g\.?\b", "उदाहरण के लिए"), (r"\b[iI]\.?e\.?\b", "अर्थात")],
        "de": [(r"\b[eE]\.?g\.?\b", "zum Beispiel"), (r"\b[iI]\.?e\.?\b", "das heißt")],
        "fr": [(r"\b[eE]\.?g\.?\b", "par exemple"), (r"\b[iI]\.?e\.?\b", "c’est-à-dire")],
        "es": [(r"\b[eE]\.?g\.?\b", "por ejemplo"), (r"\b[iI]\.?e\.?\b", "es decir")],
    }
    subs = rules.get(lang, rules["en"])

    out = str(text)

    # Replace and add a natural pause if a word follows (comma helps TTS)
    for pat, repl in subs:
        out = re.sub(pat + r"(?=\s*\w)", repl + ",", out)
        out = re.sub(pat, repl, out)

    # Tidy accidental double commas
    out = re.sub(r",\s*,", ", ", out)
    return out

# ---------------- TTS core + AUTO-ASYNC WRAPPERS ------------------------------
_speak_lock = threading.RLock()

def _speak_sync(message: str):
    """Blocking TTS (do NOT call this from the Tk main thread)."""
    message = _normalize_for_tts(message)
    with _speak_lock:
        if selected_language == "hi":
            # Hindi path: gTTS + playsound (lazy imports)
            try:
                from gtts import gTTS
                from playsound import playsound
                tmp = Path(tempfile.gettempdir()) / "nova_hindi_output.mp3"
                gTTS(text=message, lang='hi').save(str(tmp))
                playsound(str(tmp))
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            except Exception as e:
                logger.warning(f"Hindi TTS error: {e}")
                # fall back to pyttsx3 below

        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            sel = language_voice_map.get(selected_language, "david")
            vid = None
            for v in voices:
                if sel.lower() in v.name.lower():
                    vid = v.id
                    break
            if not vid:
                for v in voices:
                    if "david" in v.name.lower():
                        vid = v.id
                        break
            if vid:
                engine.setProperty('voice', vid)
            engine.setProperty('rate', 175)
            engine.say(message)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 speak failed: {e}")
            try:
                print("🗣️ " + message)
            except Exception:
                pass

def speak(message: str):
    """
    AUTO-ASYNC GUARD:
    If called on the Tk main thread, run TTS on a daemon thread to avoid
    blocking animations/UI. If already on a worker thread, run sync.
    """
    if threading.current_thread().name == "MainThread":
        threading.Thread(target=lambda: _speak_sync(message), daemon=True).start()
        return
    _speak_sync(message)

def speak_async(message: str):
    """Always speak on a background thread (explicit async helper)."""
    threading.Thread(target=lambda: _speak_sync(message), daemon=True).start()

def _speak_multilang_sync(en, hi="", de="", fr="", es="", log_command=None):
    lang_map = {"en": en, "hi": hi or en, "de": de or en, "fr": fr or en, "es": es or en}
    response = lang_map.get(selected_language, en)
    # TTS (may block): let speak() decide thread strategy
    speak(response)
    # GUI echo (safe; emit_gui uses root.after internally)
    try:
        emit_gui("NOVA", response)
    except Exception:
        pass
    if log_command:
        log_interaction(log_command, response, selected_language)

def _speak_multilang(en, hi="", de="", fr="", es="", log_command=None):
    """
    AUTO-ASYNC GUARD for multi-language speak+echo.
    """
    if threading.current_thread().name == "MainThread":
        threading.Thread(
            target=lambda: _speak_multilang_sync(en, hi, de, fr, es, log_command),
            daemon=True
        ).start()
        return
    _speak_multilang_sync(en, hi, de, fr, es, log_command)

def _speak_multilang_async(en, hi="", de="", fr="", es="", log_command=None):
    """Always run multi-lang speak on a background thread."""
    threading.Thread(
        target=lambda: _speak_multilang_sync(en, hi, de, fr, es, log_command),
        daemon=True
    ).start()

# =============================================================================
# GUI EVENT BUS (lightweight fallback)
# =============================================================================

_gui_bus: Optional[Callable[[str, Any], None]] = None

def set_gui_callback(fn: Callable[[str, Any], None]):
    global _gui_bus
    _gui_bus = fn
    return fn

def gui_callback(*args, **kwargs):
    try:
        from gui_interface import show_mode_solution, append_mode_solution, nova_gui
    except Exception:
        return

    if args:
        # ("plot", "text")
        if isinstance(args[0], str) and len(args) >= 2 and isinstance(args[1], str):
            ch, text = args[0], args[1]
            try:
                nova_gui.root.after(0, lambda: show_mode_solution(ch, text))
            except Exception:
                pass
            return
        # ("physics", {payload})
        if isinstance(args[0], str) and len(args) >= 2 and isinstance(args[1], dict):
            ch, payload = args[0], args[1]
            html = payload.get("html") or payload.get("text")
            action = (payload.get("action") or "new").lower()
            try:
                if html:
                    if action == "append":
                        nova_gui.root.after(0, lambda: append_mode_solution(ch, html))
                    else:
                        nova_gui.root.after(0, lambda: show_mode_solution(ch, html))
                else:
                    nova_gui.root.after(0, lambda: nova_gui.show_message("NOVA", str(payload)))
            except Exception:
                pass
            return

    if kwargs:
        parts = []
        if kwargs.get("solution_en"):
            parts.append(str(kwargs["solution_en"]))
        if kwargs.get("stepwise"):
            parts.append(str(kwargs["stepwise"]))
        if kwargs.get("result"):
            parts.append(f"\nResult:\n{kwargs['result']}")
        text = "\n".join([p for p in parts if p])
        try:
            from gui_interface import show_mode_solution, nova_gui
            nova_gui.root.after(0, lambda: show_mode_solution("math", text))
        except Exception:
            pass

def _default_gui_bus(channel: str, payload: Any) -> None:
    try:
        gui_callback(channel, payload)
    except Exception:
        try:
            logger.info(f"[fallback GUI] channel={channel}, payload={payload}")
        except Exception:
            pass

def emit_gui(channel: str, payload: Any) -> None:
    ( _gui_bus or _default_gui_bus )(channel, payload)

# =============================================================================
# NAME EXTRACTION
# =============================================================================

def extract_name(text: str) -> Optional[str]:
    if not text:
        return None
    original = text.strip()
    low = original.lower()
    pats: Iterable[str] = (
        r"(?:my\s+name\s+is)\s+(?P<n>.+)$",
        r"(?:i\s*am)\s+(?P<n>.+)$",
        r"(?:i'm)\s+(?P<n>.+)$",
        r"(?:this\s+is)\s+(?P<n>.+)$",
        r"(?:call\s+me)\s+(?P<n>.+)$",
        r"(?:mein\s+naam\s+)\s+(?P<n>.+)$",
        r"(?:mera\s+naam\s+)\s+(?P<n>.+)$",
    )
    name = None
    for pat in pats:
        m = re.search(pat, low)
        if m:
            start, end = m.span("n")
            name = original[start:end]
            break
    if not name:
        toks = [t for t in original.replace(",", " ").split() if t]
        cand = [t for t in toks if (t[0].isalpha() and t[0].isupper() and t.lower() != "i")]
        if cand:
            name = cand[0]
        elif toks and toks[0].isalpha():
            name = toks[0]
    if not name:
        return None
    name = name.strip().strip(",.;:!?'\"()[]{}")
    parts = [p for p in name.split() if p.isalpha()]
    if not parts:
        return None
    return " ".join(w.capitalize() for w in parts[:3])

# =============================================================================
# VOICE — shared mic lock + silent retries
# =============================================================================

# 🔒 Single global lock to prevent concurrent microphone access
MIC_LOCK = threading.Lock()

def listen_command() -> str:
    recognizer = sr.Recognizer()
    for attempt in range(2):
        # Ensure only one thread opens the mic at a time
        with MIC_LOCK:
            try:
                with sr.Microphone() as source:
                    print("🎙️  Calibrating for background noise...")
                    recognizer.dynamic_energy_threshold = True
                    recognizer.energy_threshold = 300
                    recognizer.adjust_for_ambient_noise(source, duration=1)
                    print("🎙️  Listening for your command...")
                    # generous windows; silent on timeout
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=12)
            except sr.WaitTimeoutError:
                # ✅ no TTS here — just retry silently
                continue
            except Exception as e:
                logger.error(f"[listen_command] mic error: {e}")
                # back off briefly and retry once
                continue

        try:
            command = recognizer.recognize_google(audio)
            print(f"🗣️  You said: {command}")
            logger.info(f"🗣️ Recognized command: {command}")
            return command.lower()

        except sr.UnknownValueError:
            logger.warning("⚠️ Could not understand audio.")
            if attempt == 0:
                _speak_multilang("Sorry, I didn't catch that. Could you please repeat?",
                                 hi="माफ़ कीजिए, मैं समझ नहीं सकी। कृपया दोहराएं।",
                                 de="Entschuldigung, ich habe das nicht verstanden. Bitte wiederhole es.",
                                 fr="Désolée, je n'ai pas compris. Peux-tu répéter ?",
                                 es="Lo siento, no entendí eso. ¿Puedes repetirlo?")
            else:
                _speak_multilang("Still couldn't understand. Let's try this another way.",
                                 hi="अब भी समझ नहीं पाई। चलिए इसे किसी और तरीके से आज़माते हैं।",
                                 de="Ich habe es immer noch nicht verstanden. Probieren wir es anders.",
                                 fr="Je ne comprends toujours pas. Essayons autrement.",
                                 es="Todavía no lo entendí. Probemos de otra forma.")
                return ""
            
        except sr.RequestError:
            logger.error("🛑 Speech recognition service is down.")
            _speak_multilang("Network issue. Try again later.",
                             hi="नेटवर्क में समस्या है। कृपया बाद में प्रयास करें।",
                             de="Netzwerkproblem. Versuch es später erneut.",
                             fr="Problème de réseau. Réessaie plus tard.",
                             es="Problema de red. Inténtalo más tarde.")
            return ""

    # If both attempts timed out silently, just return empty
    return ""

# =============================================================================
# LANGUAGE SELECTION (FUZZY + PERSISTED)
# =============================================================================

SUPPORTED_LANGS = {"en", "hi", "de", "fr", "es"}

_LANG_ALIASES = {
    "en": ["en", "english", "inglish", "angrezi", "anglais", "inglés", "eng", "english language"],
    "hi": ["hi", "hindi", "hindee", "हिंदी", "hindustani", "hinglish"],
    "de": ["de", "german", "deutsch", "doitch", "allemand", "alemán", "germany language"],
    "fr": ["fr", "french", "francais", "français", "fransh", "franshe", "frensh", "france language"],
    "es": ["es", "spanish", "espanol", "español", "espaniol", "espanish", "espanish language"],
}
_CHANGE_LANG = [
    "change language", "switch language", "set language", "language change",
    "cambiar idioma", "changer la langue", "sprache ändern", "bhāṣā badal", "भाषा बदल"
]

def _similar(a: str, b: str) -> float:
    return SequenceMatcher(a=a.lower().strip(), b=b.lower().strip()).ratio()

def _best_alias_match(text: str) -> Optional[str]:
    text = (text or "").strip().lower()
    if not text:
        return None
    for code, aliases in _LANG_ALIASES.items():
        for ali in aliases:
            if ali in text:
                return code
    best_code, best_score = None, 0.0
    for code, aliases in _LANG_ALIASES.items():
        for ali in aliases:
            score = _similar(text, ali)
            if score > best_score:
                best_code, best_score = code, score
    return best_code if (best_score >= 0.72) else None

def guess_language_code(heard: str) -> Optional[str]:
    if not heard:
        return None
    heard = heard.strip().lower()
    # Quick contains
    if "english" in heard: return "en"
    if "hindi" in heard or "हिंदी" in heard or "hindee" in heard: return "hi"
    if "deutsch" in heard or "german" in heard: return "de"
    if "french" in heard or "français" in heard or "francais" in heard: return "fr"
    if "spanish" in heard or "español" in heard or "espanol" in heard: return "es"
    return _best_alias_match(heard)

def said_change_language(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    if any(p in t for p in _CHANGE_LANG):
        return True
    return max((_similar(t, p) for p in _CHANGE_LANG), default=0.0) >= 0.75

def _save_language_choice(code: str):
    try:
        s = load_settings()
        s["language"] = code
        save_settings(s)
    except Exception as e:
        logger.error(f"save language failed: {e}")

def _load_saved_language() -> Optional[str]:
    try:
        s = load_settings()
        lang = s.get("language")
        if isinstance(lang, str) and lang.lower() in SUPPORTED_LANGS:
            return lang.lower()
    except Exception:
        pass
    return None

def pick_language_interactive_fuzzy() -> str:
    global selected_language  # single global at top

    speak("Please tell me the language you'd like to use to communicate with me: English, Hindi, German, French, or Spanish.")
    for _ in range(2):
        heard = listen_command()
        if not heard:
            continue
        code = guess_language_code(heard)
        if code in SUPPORTED_LANGS:
            names = {
                "en": ("Language set to English.", {}),
                "hi": ("Language set to Hindi.", {"hi": "भाषा हिन्दी पर सेट कर दी गई है।"}),
                "de": ("Language set to German.", {"de": "Sprache auf Deutsch eingestellt."}),
                "fr": ("Language set to French.", {"fr": "La langue a été définie sur le français."}),
                "es": ("Language set to Spanish.", {"es": "El idioma se ha configurado en español."}),
            }
            text, kwargs = names[code]
            selected_language = code
            _speak_multilang(text, **kwargs)
            return code
    selected_language = "en"
    _speak_multilang("Defaulting to English.")
    return "en"

def set_language_persisted(force: bool = False, speak_when_loaded: bool = False) -> str:
    global selected_language  # single global at top

    saved = None if force else _load_saved_language()
    if saved in SUPPORTED_LANGS:
        selected_language = saved
        if speak_when_loaded:
            _speak_multilang(
                "Using your previously selected language.",
                hi="आपकी पहले चुनी हुई भाषा का उपयोग हो रहा है।",
                de="Ihre zuvor ausgewählte Sprache wird verwendet.",
                fr="Utilisation de votre langue précédemment choisie.",
                es="Usando tu idioma seleccionado anteriormente.",
            )
        return selected_language
    code = pick_language_interactive_fuzzy()
    _save_language_choice(code)
    return code

# Back-compat wrapper
def set_language():
    return set_language_persisted(force=False, speak_when_loaded=False)

# =============================================================================
# BRIGHTNESS / VOLUME  (lazy imports so startup can’t fail)
# =============================================================================

def change_brightness(increase=True, level=None):
    try:
        import wmi
        c = wmi.WMI(namespace='wmi')
        methods = c.WmiMonitorBrightnessMethods()[0]
        current_level = c.WmiMonitorBrightness()[0].CurrentBrightness
        if level is not None:
            level = max(0, min(100, level)); methods.WmiSetBrightness(level, 0)
            _speak_multilang(f"Brightness set to {level} percent.",
                             hi=f"ब्राइटनेस {level} प्रतिशत पर सेट कर दी गई है।",
                             de=f"Helligkeit wurde auf {level} Prozent eingestellt.",
                             fr=f"La luminosité a été réglée à {level} pour cent.",
                             es=f"El brillo se ha ajustado al {level} por ciento.")
        else:
            new_level = min(100, current_level + 30) if increase else max(0, current_level - 30)
            methods.WmiSetBrightness(new_level, 0)
            _speak_multilang(f"Brightness adjusted to {new_level} percent.",
                             hi=f"ब्राइटनेस {new_level} प्रतिशत तक समायोजित की गई है।",
                             de=f"Helligkeit wurde auf {new_level} Prozent angepasst.",
                             fr=f"La luminosité a été ajustée à {new_level} pour cent.",
                             es=f"El brillo se ha ajustado al {new_level} por ciento.")
        _speak_multilang("Command completed.",
                         hi="कमांड पूरी कर दी गई है।",
                         de="Befehl abgeschlossen.",
                         fr="Commande terminée.",
                         es="Comando completado.")
    except Exception:
        _speak_multilang("Sorry, brightness control is not available on this system.",
                         hi="माफ़ कीजिए, ब्राइटनेस नियंत्रण उपलब्ध नहीं है।",
                         de="Helligkeitssteuerung ist auf diesem System nicht verfügbar.",
                         fr="Le contrôle de la luminosité n'est pas disponible sur ce système.",
                         es="El control de brillo no está disponible en este sistema.")

def set_volume(level):
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        level = max(0, min(100, level))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        min_vol, max_vol, _ = volume.GetVolumeRange()
        new_volume = min_vol + (level / 100.0) * (max_vol - min_vol)
        volume.SetMasterVolumeLevel(new_volume, None)
        _speak_multilang(f"Volume set to {level} percent.",
                         hi=f"वॉल्यूम {level} प्रतिशत पर सेट कर दी गई है।",
                         de=f"Lautstärke wurde auf {level} Prozent eingestellt.",
                         fr=f"Le volume a été réglé à {level} pour cent.",
                         es=f"El volumen se ha ajustado al {level} por ciento.")
        _speak_multilang("Command completed.",
                         hi="कमांड पूरी कर दी गई है।",
                         de="Befehl abgeschlossen.",
                         fr="Commande terminée.",
                         es="Comando completado.")
    except Exception:
        _speak_multilang("Sorry, I couldn’t change the volume.",
                         hi="माफ़ कीजिए, वॉल्यूम बदला नहीं जा सका।",
                         de="Entschuldigung, die Lautstärke konnte nicht geändert werden.",
                         fr="Désolée, le volume n'a pas pu être modifié.",
                         es="Lo siento, no se pudo cambiar el volumen.")

# =============================================================================
# INTERACTION LOGS
# =============================================================================

def log_interaction(command, response, lang):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "interaction_log.txt").open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] ({lang})\nUser: {command}\nNOVA: {response}\n\n")
        with (LOG_DIR / "interaction_log.csv").open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, lang, command, response])
    except Exception as e:
        logger.error(f"[log_interaction] failed: {e}")

# =============================================================================
# WAKE MODE
# =============================================================================

def get_wake_mode():
    settings = load_settings()
    return settings.get("wake_mode", "on")  # default ON as discussed

def set_wake_mode(enabled: bool):
    settings = load_settings()
    settings["wake_mode"] = "on" if enabled else "off"
    save_settings(settings)

# =============================================================================
# GRAPH HELPERS
# =============================================================================

def graphs_dir() -> str:
    gd = pkg_path("graphs")
    gd.mkdir(parents=True, exist_ok=True)
    return str(gd)

def announce_saved_graph(path: str) -> str:
    """Speak + return a friendly message about where the graph was saved."""
    filename = os.path.basename(path)
    parent   = os.path.dirname(path.rstrip(os.sep))
    folder   = os.path.basename(parent) or parent or "folder"
    msg = f"Your graph has been saved as {filename} in {folder} folder."
    try:
        speak(msg)  # auto-async now
    except Exception:
        try:
            print(msg)
        except Exception:
            pass
    return msg
