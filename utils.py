# utils.py
from __future__ import annotations

# Sentinel so main.py can prefer THIS module if multiple "utils" exist
IS_NOVA_UTILS = True

# ── run-before-anything: keep Matplotlib quiet + cache local ───────────────────
import os, sys, platform
from pathlib import Path

from platform_adapter import get_backend
_backend = get_backend()

try:
    # Lower PulseAudio buffering to avoid stutter on Linux/WSL
    if sys.platform.startswith("linux"):
        os.environ.setdefault("PULSE_LATENCY_MSEC", "30")
except Exception:
    pass


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
import json, csv, tempfile, logging, threading, re, time
from datetime import datetime
from typing import Callable, Optional, Any, Union, Iterable

# ── third-party (SAFE at top-level)
import speech_recognition as sr
# ⚠️ Heavy/optional deps are imported lazily where used:
#    wmi, gTTS, playsound, comtypes/ctypes, pycaw.pycaw


# --- third-party (SAFE at top-level) -----------------------------------------
try:
    _SR_AVAILABLE = True
except Exception:
    sr = None  # type: ignore[assignment]
    _SR_AVAILABLE = False

# one-time guards
_SR_WARNED = False          # log once
_SR_NOTICE_SHOWN = False    # speak once


# NEW: cross-platform TTS driver
from tts_driver import get_tts
_tts = get_tts()

# ── centralized intents (NO locals duplicated here) ───────────────────────────
from intents import (
    SUPPORTED_LANGS as _INT_SUPPORTED_LANGS,
    guess_language_code as _intent_guess_language_code,
    said_change_language as _intent_said_change_language,
    get_language_prompt_text,
    get_invalid_language_line_typed,
    get_invalid_language_voice_to_typed,
)


# --- Linux/WSL detector (Windows untouched) -----------------------------------
def _is_linux_or_wsl() -> bool:
    try:
        return sys.platform.startswith("linux") or ("WSL_DISTRO_NAME" in os.environ)
    except Exception:
        return False

# --- First-boot English voice lock (Linux-only) -------------------------------
_BOOT_LANG_LOCK = False

def enable_boot_lang_lock_if_needed(initial_lang: str = "en") -> None:
    """
    Linux/WSL only: force TTS to speak in English until onboarding finishes.
    Has no effect on Windows/mac. Safe to call multiple times.
    """
    global _BOOT_LANG_LOCK, selected_language
    if _is_linux_or_wsl():
        _BOOT_LANG_LOCK = True
        try:
            # keep UI default sane during onboarding
            selected_language = (initial_lang or "en")
        except Exception:
            selected_language = "en"

def clear_boot_lang_lock() -> None:
    """Lift the first-boot TTS English lock (no-op on Windows)."""
    global _BOOT_LANG_LOCK
    _BOOT_LANG_LOCK = False

def is_boot_lang_lock_active() -> bool:
    return bool(_BOOT_LANG_LOCK)

# ── SSML sanitizer ------------------------------------------------------------
_SSML_TAG_RE = re.compile(r"</?[^>]+?>")  # removes <speak>, <break>, any <...>

def _strip_ssml(text: str) -> str:
    """Return plain text for TTS/UI; strips SSML/XML tags safely."""
    if not text:
        return ""
    return _SSML_TAG_RE.sub("", text)


# --- Global guard for language change flow ---
LANGUAGE_FLOW_ACTIVE = False

def set_language_flow(active: bool, suppress_ms: int = 0):
    """Mark language-change flow active/inactive and optionally mute SR prompts."""
    global LANGUAGE_FLOW_ACTIVE
    LANGUAGE_FLOW_ACTIVE = bool(active)
    if active and suppress_ms > 0:
        try:
            suppress_sr_prompts(int(suppress_ms))  # your existing helper
        except Exception:
            pass


# Back-compat for older callsites that expect get_invalid_language_line(ui_lang)
def get_invalid_language_line(ui_lang: str) -> str:
    # During spoken picker we want the "voice → typed" wording
    return get_invalid_language_voice_to_typed(ui_lang)

# small wrappers so existing callsites don’t break if they import from utils
SUPPORTED_LANGS = set(_INT_SUPPORTED_LANGS)
def guess_language_code(heard: str) -> Optional[str]:
    return _intent_guess_language_code(heard)
def said_change_language(text: str) -> bool:
    return _intent_said_change_language(text)

# =============================================================================
# APP BASE & PATH HELPERS
# =============================================================================

def _app_base_dir() -> Path:
    """Dev: folder containing this file • Frozen: dist/NOVA/ next to NOVA.exe"""
    return APP_DIR

BASE_DIR: Path = _app_base_dir()

def _is_wsl() -> bool:
    return ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in platform.release().lower())

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
            r / name_only,
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
# LOGGER (writes to per-user app data: …/Nova/logs/)
# =============================================================================

LOG_DIR = _backend.user_data_dir() / "logs"
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

# ⬇️ SR availability notice 
try:
    if not _SR_AVAILABLE:
        logger.warning("speech_recognition not available; voice capture will be disabled.")
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
    "es": "spanish",
}

# Selected language code (persisted via settings.json)
selected_language = "en"

def _settings_path() -> Path:
    d = _backend.user_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "settings.json"

_DEFAULT_SETTINGS = {
    "language": "en",
    "wake_mode": True,
    "enable_tray": True
}

def load_settings() -> dict:
    """
    Load settings with layered overrides:

      1) _DEFAULT_SETTINGS                            (built-in defaults)
      2) repo-level settings.json                     (Windows-friendly defaults you committed)
      3) repo-level per-OS override (WSL/Linux/Mac)   (e.g., settings.wsl.json)
      4) user-level settings.json in user_data_dir    (persisted choices)
      5) WSL hard overrides                           (enforce no tray/restart in WSL)
    """
    # ----- Layer 1: built-in defaults
    out = dict(_DEFAULT_SETTINGS)

    # Resolve repo base dir (where your code & settings.json live)
    repo_base = BASE_DIR

    # ----- Layer 2: repo-level settings.json (your committed file)
    try:
        p = repo_base / "settings.json"
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    out.update(data)
    except Exception as e:
        try:
            logger.error(f"load repo settings.json failed: {e}")
        except Exception:
            pass

    # ----- Layer 3: repo-level per-OS overrides (optional files)
    override_name = None
    if _is_wsl():
        override_name = "settings.wsl.json"
    elif sys.platform.startswith("linux"):
        override_name = "settings.linux.json"
    elif sys.platform.startswith("darwin"):
        override_name = "settings.mac.json"

    if override_name:
        try:
            p = repo_base / override_name
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        out.update(data)
        except Exception as e:
            try:
                logger.error(f"load {override_name} failed: {e}")
            except Exception:
                pass

    # ----- Layer 4: user-level persisted settings (per-user app data)
    user_path = _settings_path()
    first_user_settings_write = False
    try:
        if user_path.exists():
            with user_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    out.update(data)
        else:
            # first-run seed: write the merged defaults so user can tweak later
            user_path.parent.mkdir(parents=True, exist_ok=True)
            with user_path.open("w", encoding="utf-8") as f:
                json.dump(out, f, indent=4, ensure_ascii=False)
            first_user_settings_write = True
    except Exception as e:
        try:
            logger.error(f"load user settings failed: {e}")
        except Exception:
            pass

    # ----- Layer 5: WSL hard overrides (safety: prevent tray/restart loop in WSL)
    try:
        if _is_wsl():
            out["enable_tray"] = False
            out["auto_restart_on_crash"] = False
            out.setdefault("tts_engine", "gtts")
    except Exception:
        pass

    # ----- NEW: Linux-only first-boot English lock
    # Turn on the English TTS lock on Linux/WSL if this is the first ever run,
    # or the user explicitly forces first-boot via env/CLI.
    try:
        force_first_boot = bool(
            _is_linux_or_wsl()
            and (os.environ.get("NOVA_FIRST_BOOT") == "1" or "--first-boot" in sys.argv)
        )
        if _is_linux_or_wsl() and (first_user_settings_write or force_first_boot):
            enable_boot_lang_lock_if_needed("en")
    except Exception:
        pass

    return out


def save_settings(data: dict):
    try:
        p = _settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"save settings failed: {e}")

# --- Make TTS read abbreviations naturally ---
def _normalize_for_tts(text: str, *, lang: str | None = None) -> str:
    lang = (lang or selected_language or "en").lower()
    rules = {
        "en": [(r"\b[eE]\.?g\.?\b", "for example"), (r"\b[iI]\.?e\.?\b", "that is")],
        "hi": [(r"\b[eE]\.?g\.?\b", "उदाहरण के लिए"), (r"\b[iI]\.?e\.?\b", "अर्थात")],
        "de": [(r"\b[eE]\.?g\.?\b", "zum Beispiel"), (r"\b[iI]\.?e\.?\b", "das heißt")],
        "fr": [(r"\b[eE]\.?g\.?\b", "par exemple"), (r"\b[iI]\.?e\.?\b", "c’est-à-dire")],
        "es": [(r"\b[eE]\.?g\.?\b", "por ejemplo"), (r"\b[iI]\.?e\.?\b", "es decir")],
    }
    subs = rules.get(lang, rules["en"])
    out = str(text)
    for pat, repl in subs:
        out = re.sub(pat + r"(?=\s*\w)", repl + ",", out)
        out = re.sub(pat, repl, out)
    out = re.sub(r",\s*,", ", ", out)
    return out

# ---------------- TTS core + VOICE GATE ------------------------------
_speak_lock = threading.RLock()
tts_busy = threading.Event()

def wait_for_tts_quiet(buffer_ms: int = 400):
    """Block until TTS finishes speaking, then wait a small buffer."""
    try:
        while tts_busy.is_set():
            time.sleep(0.02)
        if buffer_ms > 0:
            time.sleep(buffer_ms / 1000.0)
    except Exception:
        pass


def _normalize_tts_lang(code: str) -> str:
    c = (code or "en").lower()
    # Use explicit regional tags so Linux TTS doesn’t pick odd defaults
    if c == "en": return "en-US"   # switch to "en-GB" if you prefer
    if c == "hi": return "hi-IN"
    if c == "de": return "de-DE"
    if c == "fr": return "fr-FR"
    if c == "es": return "es-ES"
    return c


def _speak_driver_sync(message: str, *, tts_lang: str | None = None):
    """Blocking TTS via cross-platform driver (do NOT call from Tk main thread)."""
    # Pick the intended language
    intended = (tts_lang or selected_language or "en")
    # Linux/WSL first-boot guard: force English voice for onboarding text
    if _is_linux_or_wsl() and is_boot_lang_lock_active():
        intended = "en"
    # Normalize to regional tags so engines pick the right voice
    intended = _normalize_tts_lang(intended)

    clean = _strip_ssml(_normalize_for_tts(message, lang=intended))
    tts_busy.set()
    try:
        with _speak_lock:
            # NEW: ensure any old playback is fully stopped before starting
            try:
                _tts.stop()
            except Exception:
                pass

            try:
                _tts.speak(clean, lang_code=intended)
            except Exception:
                # Fallback: try the base language (e.g., "en" from "en-US")
                base = intended.split("-")[0]
                if base != intended:
                    _tts.speak(clean, lang_code=base)
                else:
                    raise
    except Exception:
        # Don’t crash if TTS engine is missing; at least print it.
        try:
            print("🗣️ " + clean)
        except Exception:
            pass
    finally:
        tts_busy.clear()


def speak(message: str, *, tts_lang: str | None = None):
    """AUTO-ASYNC GUARD: speak on a worker thread if called from MainThread."""
    if threading.current_thread().name == "MainThread":
        threading.Thread(
            target=_speak_driver_sync,
            args=(message,),
            kwargs={"tts_lang": tts_lang},
            daemon=True
        ).start()
        return
    _speak_driver_sync(message, tts_lang=tts_lang)

def speak_async(message: str, *, tts_lang: str | None = None):
    threading.Thread(
        target=_speak_driver_sync,
        args=(message,),
        kwargs={"tts_lang": tts_lang},
        daemon=True
    ).start()

def _speak_multilang_sync(en, hi="", de="", fr="", es="", log_command=None, tts_format: str = "text"):
    # Keep raw map so we know whether a real translation exists
    raw_map = {"en": en, "hi": hi, "de": de, "fr": fr, "es": es}
    ui = (selected_language or "en").lower()
    ui_text = raw_map.get(ui)

    if ui_text is None or ui_text == "":
        # No localized string → speak English text with English voice
        chosen_text = en
        chosen_lang = "en"
    else:
        chosen_text = ui_text
        chosen_lang = ui

    clean = _strip_ssml(chosen_text)
    # Speak with voice that matches the text we actually chose
    _speak_driver_sync(clean, tts_lang=chosen_lang)
    try:
        emit_gui("NOVA", clean)
    except Exception:
        pass
    if log_command:
        log_interaction(log_command, clean, selected_language)

def _speak_multilang(en, hi="", de="", fr="", es="", log_command=None, tts_format: str = "text"):
    if threading.current_thread().name == "MainThread":
        threading.Thread(
            target=lambda: _speak_multilang_sync(en, hi, de, fr, es, log_command, tts_format),
            daemon=True
        ).start()
        return
    _speak_multilang_sync(en, hi, de, fr, es, log_command, tts_format)

def _speak_multilang_async(en, hi="", de="", fr="", es="", log_command=None, tts_format: str = "text"):
    threading.Thread(
        target=lambda: _speak_multilang_sync(en, hi, de, fr, es, log_command, tts_format),
        daemon=True
    ).start()

def try_stop_tts_playback():
    """Best-effort stop using the active driver (pyttsx3/say/espeak)."""
    try:
        _tts.stop()
    except Exception:
        pass


def begin_exit_with_goodbye_async(grace_timeout_s: float = 8.0):
    """
    Speak a localized goodbye without freezing the UI/animation,
    then trigger main's clean shutdown (clears timers/locks).
    Returns immediately; work happens on background threads.
    """
    # 0) Stop wake listener quickly (best effort)
    try:
        from wake_word_listener import stop_wake_listener_thread, wait_for_wake_quiet
        try: stop_wake_listener_thread()
        except Exception: pass
        try: wait_for_wake_quiet(1.2)
        except Exception: pass
    except Exception:
        pass

    # 1) Cut any ongoing TTS so goodbye doesn't overlap
    try:
        try_stop_tts_playback()
    except Exception:
        pass

    # 2) Say goodbye asynchronously (localized)
    _speak_multilang_async(
        "Goodbye! See you soon.",
        hi="अलविदा! फिर मिलेंगे।",
        de="Tschüss! Bis bald.",
        fr="Au revoir ! À bientôt.",
        es="¡Adiós! Hasta pronto.",
    )

    # 3) Watch TTS flag; when clear (or timeout), shut down cleanly
    def _watch_and_exit():
        start = time.time()
        while tts_busy.is_set() and (time.time() - start) < grace_timeout_s:
            time.sleep(0.05)
        time.sleep(0.12)  # tiny drain

        # Prefer the app’s clean shutdown
        _shutdown = None
        try:
            from __main__ import _shutdown_main as _shutdown  # main is running as __main__
        except Exception:
            try:
                from main import _shutdown_main as _shutdown    # fallback if packaged oddly
            except Exception:
                _shutdown = None

        if callable(_shutdown):
            try:
                _shutdown()
                return
            except Exception:
                pass

        # Last resort
        try:
            from gui_interface import gui_if_ready
            g = gui_if_ready()
            if g:
                try:
                    g.root.after(0, g.root.quit)
                    time.sleep(0.15)
                except Exception:
                    pass
        except Exception:
            pass
        os._exit(0)

    threading.Thread(target=_watch_and_exit, daemon=True).start()


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
        if isinstance(args[0], str) and len(args) >= 2 and isinstance(args[1], str):
            ch, text = args[0], args[1]
            try:
                nova_gui.root.after(0, lambda: show_mode_solution(ch, text))
            except Exception:
                pass
            return
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
    """
    Extract a plausible human name from free speech.
    """
    if not text:
        return None

    original = str(text).strip()
    low = original.lower()

    STOP_TOKENS = {
        "yes", "no", "yeah", "nope", "yup", "ok", "okay", "thanks", "thank",
        "you", "please", "hey", "hi", "hello"
    }
    
    # Don't treat language-change requests as a "name"
    # We already import intents in utils and expose a wrapper: said_change_language(...)
    STOP_TOKENS |= {
        "change", "language",
        "english", "german", "deutsch", "french", "français", "spanish", "español", "hindi",
    }

    # If the whole utterance is a change-language intent, bail out early
    if said_change_language(low):
        return None

    PATTERNS: Iterable[str] = (
        r"(?:^|\b)(?:my\s+name\s+is)\s+(?P<n>.+)$",
        r"(?:^|\b)(?:i\s*am)\s+(?P<n>.+)$",
        r"(?:^|\b)(?:i['’]m)\s+(?P<n>.+)$",
        r"(?:^|\b)(?:this\s+is)\s+(?P<n>.+)$",
        r"(?:^|\b)(?:call\s+me)\s+(?P<n>.+)$",
        r"(?:^|\b)(?:mein\s+naam)\s+(?P<n>.+)$",
        r"(?:^|\b)(?:mera\s+naam)\s+(?P<n>.+)$",
    )

    def _smart_title(tok: str) -> str:
        parts = re.split(r"([-'’])", tok)
        return "".join(p.capitalize() if p and p.isalpha() else p for p in parts)

    def _clean_candidate(s: str) -> Optional[str]:
        s = s.strip(" ,.;:!?\"'()[]{}")
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"[^A-Za-z \-’']", " ", s)
        toks = [t for t in s.split() if t and t.lower() not in STOP_TOKENS]
        toks = [t for t in toks if re.fullmatch(r"[A-Za-z][A-Za-z'’-]*", t)]
        if not toks:
            return None
        toks = toks[:3]
        return " ".join(_smart_title(t) for t in toks)

    for pat in PATTERNS:
        m = re.search(pat, low)
        if m:
            start, end = m.span("n")
            cand = _clean_candidate(original[start:end])
            if cand:
                return cand
            break

    toks_orig = [t for t in re.split(r"[,\s]+", original) if t]
    caps = [t for t in toks_orig if t and t[0].isupper() and t.lower() not in STOP_TOKENS]
    if caps:
        cand = _clean_candidate(caps[0])
        if cand:
            return cand

    for t in toks_orig:
        if re.match(r"[A-Za-z]", t) and t.lower() not in STOP_TOKENS:
            cand = _clean_candidate(t)
            if cand:
                return cand

    return None

# =============================================================================
# VOICE — shared mic lock + silent retries
# =============================================================================

MIC_LOCK = threading.RLock()  # RLock so nested acquisitions are safe

# Global flag to keep name-capture attempts silent (toggled from main.py)
NAME_CAPTURE_IN_PROGRESS: bool = False

# 🔴 NEW: Globally mute recognizer apology TTS for a short window (ms-based)
SUPPRESS_SR_TTS_PROMPTS_UNTIL = 0.0
def suppress_sr_prompts(ms: int):
    """Mute 'didn't catch that' style lines from listen_command for ms milliseconds."""
    import time as _t
    global SUPPRESS_SR_TTS_PROMPTS_UNTIL
    try:
        SUPPRESS_SR_TTS_PROMPTS_UNTIL = _t.time() + (ms / 1000.0)
    except Exception:
        SUPPRESS_SR_TTS_PROMPTS_UNTIL = 0.0

# Phrases that indicate the recognizer picked up our own prompt (self-echo)
SELF_ECHO_MARKERS = [
    "may i know your name",
    "is that correct",
    "yes or no",
    "please type 'yes' or 'no'",
    "please type your name below in the chatbox provided",
    "please enter a valid name below in the chatbox provided",
    "please enter a valid name: letters only, 2–30 characters, e.g. alex.",
    "please tell me the language you'd like to use",
    "please enter a valid language",
    "please provide a valid language",
    "how can i help you today",
    "standing by. let me know what you'd like to do next",
    "standing by. let me know what you’d like to do next",
    "sorry, i didn't catch that",
    "could you please repeat",
    "still couldn't understand. let's try this another way",
    "hello! i’m nova", "hello i'm nova",
]

SELF_ECHO_REGEXES = [
    re.compile(r"\bplease\s+type\b.*\b['\"“”‘’]?yes['\"“”‘’]?\s+or\s+['\"“”‘’]?no['\"“”‘’]?\b", re.I),
    re.compile(r"\bplease\s+type\s+your\s+name\b.*\bchat\s*box|chatbox\b", re.I),
    re.compile(r"\bplease\s+enter\s+a\s+valid\s+name\b.*\bletters\s+only\b.*\b2[\u2013-]-?30\s*characters\b", re.I),
    re.compile(r"\bplease\s+(say|tell|enter|type)\b.*\blanguage\b", re.I),
    re.compile(r"\bi\s+heard\b.*\bis\s+that\s+correct\b", re.I),
    re.compile(r"\bmay\s+i\s+know\s+your\s+name\b", re.I),
    re.compile(r"\bhello[!,.]?\s*i['’]m\s+nova\b", re.I),
]

def _is_self_echo(text: str) -> bool:
    if not text:
        return False
    t = text.lower().strip()
    if len(t) <= 1:
        return True
    if any(m in t for m in SELF_ECHO_MARKERS):
        return True
    return any(rx.search(t) for rx in SELF_ECHO_REGEXES)



def listen_command(
    *,
    skip_tts_gate: bool = False,
    disable_self_echo_filter: bool = False,
    timeout_s: int = 8,
    phrase_time_limit_s: int = 10,
    ambient_calib_s: float = 0.6
) -> str:
    """
    Robust speech capture with:
      - optional TTS gate skip,
      - self-echo filter,
      - short ambient calibration,
      - tuned thresholds for snappy short phrases,
      - language-aware decoding with multi-alternative pick.
    """
    # ⛔ If speech_recognition isn't installed, disable voice input gracefully (log once)
    global _SR_WARNED, _SR_NOTICE_SHOWN
    if not _SR_AVAILABLE:
        if not _SR_WARNED:
            try:
                logger.warning("listen_command called but speech_recognition is unavailable.")
            except Exception:
                pass
            _SR_WARNED = True


        # Speak once, honoring your suppression flags
        try:
            now = time.time()
        except Exception:
            now = 0.0

        if (not _SR_NOTICE_SHOWN) and (now >= SUPPRESS_SR_TTS_PROMPTS_UNTIL) and (not NAME_CAPTURE_IN_PROGRESS):
            _SR_NOTICE_SHOWN = True
            _speak_multilang(
                "Speech recognition isn’t installed, so I can’t listen right now.",
                hi="Speech recognition इंस्टॉल नहीं है, इसलिए मैं अभी सुन नहीं सकती।",
                de="Spracherkennung ist nicht installiert, daher kann ich gerade nicht zuhören.",
                fr="La reconnaissance vocale n’est pas installée, je ne peux donc pas écouter.",
                es="El reconocimiento de voz no está instalado, así que no puedo escuchar ahora."
            )

        return ""

    # 1) Never capture our own TTS (unless caller already gated)
    if not skip_tts_gate:
        wait_for_tts_quiet(150)  # bump to 200–250ms if needed on very fast machines

    # 2) Optional mic device
    dev_index = None
    try:
        s = load_settings()
        di = s.get("mic_device_index", None)
        if isinstance(di, int):
            dev_index = di
    except Exception:
        pass

    # 3) Map UI language to preferred STT languages
    def _lang_candidates(sel: str | None) -> list[str]:
        sel = (sel or "en").lower()
        order = {
            "hi": ["hi-IN", "en-IN", "en-US"],
            "en": ["en-IN", "en-US", "en-GB"],
            "de": ["de-DE", "en-US"],
            "fr": ["fr-FR", "en-US"],
            "es": ["es-ES", "en-US"],
        }
        return order.get(sel, ["en-IN", "en-US"])

    # 4) Recognizer tuning
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = max(150, getattr(r, "energy_threshold", 300))
    r.pause_threshold = 0.6
    r.phrase_threshold = 0.25
    r.non_speaking_duration = 0.3

    attempts = 3

    for attempt in range(attempts):
        # 5) Capture audio
        with MIC_LOCK:
            try:
                with sr.Microphone(device_index=dev_index) as source:
                    try:
                        r.adjust_for_ambient_noise(source, duration=ambient_calib_s)
                    except Exception:
                        pass
                    audio = r.listen(
                        source,
                        timeout=timeout_s,
                        phrase_time_limit=phrase_time_limit_s
                    )
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                logger.error(f"[listen_command] mic error: {e}")
                continue

        # 6) Decode
        recognized = ""
        last_unknown_error = None
        for lang in _lang_candidates(selected_language):
            try:
                result = r.recognize_google(audio, language=lang, show_all=True)
                transcript = None
                if isinstance(result, dict) and result.get("alternative"):
                    best = result["alternative"][0]
                    best_conf = best.get("confidence", 0.0) if isinstance(best, dict) else 0.0
                    for alt in result["alternative"]:
                        if isinstance(alt, dict):
                            conf = alt.get("confidence", 0.0)
                            if conf > best_conf and "transcript" in alt:
                                best, best_conf = alt, conf
                    transcript = best.get("transcript") if isinstance(best, dict) else None

                if not transcript:
                    transcript = r.recognize_google(audio, language=lang)

                if transcript:
                    txt = transcript.strip()
                    if txt:
                        if (not disable_self_echo_filter) and _is_self_echo(txt):
                            try:
                                logger.info("[listen_command] dropped self-echo")
                            except Exception:
                                pass
                            recognized = ""
                            break
                        recognized = txt
                        try:
                            logger.info(f"🗣️ Recognized ({lang}): {recognized}")
                        except Exception:
                            pass
                        break
            except sr.UnknownValueError as e:
                last_unknown_error = e
                continue
            except sr.RequestError as e:
                logger.error(f"Google STT request failed: {e}")
                break

        if recognized:
            # 🔹 Count this as activity so the main can schedule/reset its idle nudge
            try:
                _mark_command_activity()
            except Exception:
                pass
            return recognized

        # 7) If we’re here, decoding failed this attempt → maybe apologize
        is_last_attempt = (attempt == attempts - 1)

        # 🔴 compute suppress_prompts (mutes recognizer apologies during guided flows or timed windows)
        lang_capture_active = False
        try:
            from gui_interface import nova_gui as _gui_ref
            lang_capture_active = bool(getattr(_gui_ref, "language_capture_active", False))
        except Exception:
            lang_capture_active = False

        suppress_prompts = (
            NAME_CAPTURE_IN_PROGRESS
            or lang_capture_active
            or LANGUAGE_FLOW_ACTIVE
            or time.time() < SUPPRESS_SR_TTS_PROMPTS_UNTIL
        )

        if not suppress_prompts:
            if is_last_attempt:
                _speak_multilang(
                    "Still couldn't understand. Let's try this another way.",
                    hi="अब भी समझ नहीं पाई। चलिए इसे किसी और तरीके से आज़माते हैं।",
                    de="Ich habe es immer noch nicht verstanden. Probieren wir es anders.",
                    fr="Je ne comprends toujours pas. Essayons autrement.",
                    es="Todavía no lo entendí. Probemos de otra forma."
                )
            else:
                _speak_multilang(
                    "Sorry, I didn't catch that. Could you please repeat?",
                    hi="माफ़ कीजिए, मैं समझ नहीं सकी। कृपया दोहराएं।",
                    de="Entschuldigung, ich habe das nicht verstanden. Bitte wiederhole es.",
                    fr="Je n’ai pas compris. Peux-tu répéter ?",
                    es="No entendí eso. ¿Puedes repetirlo?"
                )

        continue

    # 8) All attempts failed
    return ""

# =============================================================================
# LANGUAGE SELECTION (FUZZY + PERSISTED) — centralized text via intents.py
# =============================================================================

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
    """
    Interruptible, localized (utils-side) picker.
    """
    import threading
    global selected_language

    ORDER = ["en", "hi", "de", "fr", "es"]
    prompts = {code: get_language_prompt_text(code) for code in ORDER}
    invalid_line = {code: get_invalid_language_voice_to_typed(code) for code in ORDER}

    confirm_map = {
        "en": ("Language set to English.", {}),
        "hi": ("Language set to Hindi.",   {"hi": "भाषा हिन्दी पर सेट कर दी गई है।"}),
        "de": ("Language set to German.",  {"de": "Sprache auf Deutsch eingestellt."}),
        "fr": ("Language set to French.",  {"fr": "La langue a été définie sur le français."}),
        "es": ("Language set to Spanish.", {"es": "El idioma se ha configurado al español."}),
    }

    def _say_prompt():
        try:
            _speak_multilang(
                prompts["en"], hi=prompts["hi"], de=prompts["de"], fr=prompts["fr"], es=prompts["es"]
            )
        except Exception:
            try:
                speak(prompts.get(selected_language, prompts["en"]))
            except Exception:
                pass

    for attempt in range(2):
        try:
            threading.Thread(target=_say_prompt, daemon=True).start()
        except Exception:
            _say_prompt()

        heard = listen_command(skip_tts_gate=True, timeout_s=12, phrase_time_limit_s=15)

        if heard:
            try:
                try_stop_tts_playback()
            except Exception:
                pass

            code = guess_language_code(heard)
            if code in SUPPORTED_LANGS:
                selected_language = code
                text, kwargs = confirm_map[code]
                _speak_multilang(text, **kwargs)
                return code

            _speak_multilang(
                invalid_line["en"],
                hi=invalid_line["hi"],
                de=invalid_line["de"],
                fr=invalid_line["fr"],
                es=invalid_line["es"],
            )
            continue

        if attempt == 0:
            try:
                _speak_multilang("Sorry, I didn't catch that. Please try again.")
            except Exception:
                pass

    selected_language = "en"
    _speak_multilang("Defaulting to English.")
    return "en"

# =============================================================================
# BRIGHTNESS / VOLUME  (lazy imports; Windows-only features guarded)
# =============================================================================

def change_brightness(increase=True, level=None):
    # Not supported on non-Windows (avoids import errors on Linux/macOS/WSL)
    if sys.platform != "win32":
        _speak_multilang(
            "Sorry, brightness control is not available on this system.",
            hi="माफ़ कीजिए, ब्राइटनेस नियंत्रण उपलब्ध नहीं है।",
            de="Helligkeitssteuerung ist auf diesem System nicht verfügbar.",
            fr="Le contrôle de la luminosité n'est pas disponible sur ce système.",
            es="El control de brillo no está disponible en este sistema."
        )
        return

    try:
        import wmi  # type: ignore[import-not-found]
        c = wmi.WMI(namespace="wmi")
        methods = c.WmiMonitorBrightnessMethods()[0]
        current_level = c.WmiMonitorBrightness()[0].CurrentBrightness

        if level is not None:
            level = max(0, min(100, int(level)))
            methods.WmiSetBrightness(level, 0)
            _speak_multilang(
                f"Brightness set to {level} percent.",
                hi=f"ब्राइटनेस {level} प्रतिशत पर सेट कर दी गई है।",
                de=f"Helligkeit wurde auf {level} Prozent eingestellt.",
                fr=f"La luminosité a été réglée à {level} pour cent.",
                es=f"La luminosidad se ha ajustado al {level} por ciento."
            )
        else:
            new_level = min(100, current_level + 30) if increase else max(0, current_level - 30)
            methods.WmiSetBrightness(new_level, 0)
            _speak_multilang(
                f"Brightness adjusted to {new_level} percent.",
                hi=f"ब्राइटनेस {new_level} प्रतिशत तक समायोजित की गई है।",
                de=f"Helligkeit wurde auf {new_level} Prozent angepasst.",
                fr=f"La luminosité a été ajustée au {new_level} pour cent.",
                es=f"La luminosidad se ha ajustado al {new_level} por ciento."
            )

        _speak_multilang(
            "Command completed.",
            hi="कमांड पूरी कर दी गई है।",
            de="Befehl abgeschlossen.",
            fr="Commande terminée.",
            es="Comando completado."
        )
    except Exception:
        _speak_multilang(
            "Sorry, brightness control is not available on this system.",
            hi="माफ़ कीजिए, ब्राइटनेस नियंत्रण उपलब्ध नहीं है।",
            de="Helligkeitssteuerung ist auf diesem System nicht verfügbar.",
            fr="Le contrôle de la luminosité n'est pas disponible sur ce système.",
            es="El control de brillo no está disponible en este sistema."
        )


def set_volume(level):
    # Not supported on non-Windows (avoids import errors on Linux/macOS/WSL)
    if sys.platform != "win32":
        _speak_multilang(
            "Sorry, I couldn’t change the volume.",
            hi="माफ़ कीजिए, वॉल्यूम बदला नहीं जा सका।",
            de="Entschuldigung, die Lautstärke konnte nicht geändert werden.",
            fr="Désolée, le volume n'a pas pu être modifié.",
            es="Lo siento, no se pudo cambiar el volumen."
        )
        return

    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-not-found]

        level = max(0, min(100, int(level)))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        min_vol, max_vol, _ = volume.GetVolumeRange()
        new_level = min_vol + (level / 100.0) * (max_vol - min_vol)
        volume.SetMasterVolumeLevel(new_level, None)

        _speak_multilang(
            f"Volume set to {level} percent.",
            hi=f"वॉल्यूम {level} प्रतिशत पर सेट कर दी गई है।",
            de=f"Lautstärke wurde auf {level} Prozent eingestellt.",
            fr=f"Le volume a été réglé à {level} pour cent.",
            es=f"El volumen se ha ajustado al {level} por ciento."
        )
        _speak_multilang(
            "Command completed.",
            hi="कमांड पूरी कर दी गई है।",
            de="Befehl abgeschlossen.",
            fr="Commande terminée.",
            es="Comando completado."
        )
    except Exception:
        _speak_multilang(
            "Sorry, I couldn’t change the volume.",
            hi="माफ़ कीजिए, वॉल्यूम बदला नहीं जा सका।",
            de="Entschuldigung, die Lautstärke konnte nicht geändert werden.",
            fr="Désolée, le volume n'a pas pu être modifié.",
            es="Lo siento, no se pudo cambiar el volumen."
        )

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

def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        # accept legacy/string variants
        if s in {"on", "true", "1", "yes", "enabled", "always_on"}:
            return True
        if s in {"off", "false", "0", "no", "disabled", "always_off"}:
            return False
        # unknown strings default to False (conservative)
        return False
    return bool(v)

def get_wake_mode() -> bool:
    s = load_settings()
    v = s.get("wake_mode", True)  # default = True
    b = _to_bool(v)
    # 🔄 auto-migrate to a boolean so future runs are clean
    if not isinstance(v, bool):
        s["wake_mode"] = b
        save_settings(s)
    return b

def set_wake_mode(enabled) -> None:
    b = _to_bool(enabled)
    s = load_settings()
    s["wake_mode"] = b
    save_settings(s)


# =============================================================================
# GRAPH HELPERS
# =============================================================================


def graphs_dir() -> str:
    # Save graphs under the per-user app data folder on every OS
    gd = _backend.user_data_dir() / "graphs"
    gd.mkdir(parents=True, exist_ok=True)
    return str(gd)

def announce_saved_graph(path: str) -> str:
    """Speak + return a friendly message about where the graph was saved."""
    filename = os.path.basename(path)
    parent   = os.path.dirname(path.rstrip(os.sep))
    folder   = os.path.basename(parent) or parent or "folder"
    msg = f"Your graph has been saved as {filename} in {folder} folder."
    try:
        speak(msg)
    except Exception:
        try:
            print(msg)
        except Exception:
            pass
    return msg


# =============================================================================
# USER ACTIVITY TIMESTAMP (for main.py idle-nudge scheduling)
# =============================================================================

_LAST_ACTIVITY_TS: float = 0.0

def _mark_command_activity():
    """Record that the user or a command just did something meaningful."""
    global _LAST_ACTIVITY_TS
    _LAST_ACTIVITY_TS = time.time()

def last_activity_ts() -> float:
    """Return the last activity timestamp (epoch seconds)."""
    return _LAST_ACTIVITY_TS
