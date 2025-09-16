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

# ------------ NEW: prefer DirectSound for pygame on Windows (reduces quirks)
if sys.platform.startswith("win"):
    os.environ.setdefault("SDL_AUDIODRIVER", "directsound")

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
import json, csv, tempfile, logging, threading, re, time, shutil, subprocess
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
_SR_WARNED = False
_SR_NOTICE_SHOWN = False

# ─────────────── helper: find bundled binaries (then PATH) ───────────────────
def _platform_key() -> str:
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"

def _candidate_roots() -> list[Path]:
    roots = [APP_DIR, APP_DIR / "_internal"]
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots += [Path(meipass), Path(meipass) / "_internal"]
    except Exception:
        pass
    return roots

def _find_in_roots(names: list[str]) -> Optional[str]:
    for r in _candidate_roots():
        for n in names:
            p = (r / n)
            try:
                if p.exists():
                    # ensure executable bit on Unix; Windows doesn't need this
                    if os.name != "nt":
                        try:
                            st = p.stat()
                            if not (st.st_mode & 0o111):
                                p.chmod(st.st_mode | 0o111)
                        except Exception:
                            pass
                    return str(p)
            except Exception:
                continue
    return None

def _which(cmd: str) -> Optional[str]:
    """
    Prefer a bundled binary (repo/bin/<os>/<cmd> or <bundle>/_internal/bin/...) then PATH.
    """
    exe_name = cmd + (".exe" if sys.platform.startswith("win") and not cmd.endswith(".exe") else "")
    plat = _platform_key()
    # check common bundle locations first
    names = [
        f"bin/{plat}/{exe_name}",
        f"bin/{exe_name}",
        exe_name,
    ]
    hit = _find_in_roots(names)
    if hit:
        return hit
    try:
        return shutil.which(cmd)
    except Exception:
        return None

def _ffplay_from_bundle_or_path() -> Optional[str]:
    """
    Prefer a bundled ffplay over PATH:
      - dev run:   <repo>/ffmpeg/bin/ffplay(.exe)
      - frozen exe:MEIPASS/ffmpeg/bin/ffplay(.exe)
      - else:      whatever is on PATH
    """
    exe = "ffplay.exe" if sys.platform.startswith("win") else "ffplay"
    bundle_candidates = [
        Path(__file__).resolve().parent / "ffmpeg" / "bin" / exe,         # dev layout
        Path(getattr(sys, "_MEIPASS", "")) / "ffmpeg" / "bin" / exe,      # frozen layout
    ]
    for p in bundle_candidates:
        try:
            if p and p.exists():
                return str(p)
        except Exception:
            pass
    return _which("ffplay")

# ─────────────── NEW: dedicated resolver for mac brightness CLI ──────────────
def _brightness_cmd() -> Optional[str]:
    """
    Resolve the macOS 'brightness' CLI, preferring the bundled copy.

    Search order:
      1) APP_DIR/macbin/brightness          (dev & source runs)
      2) MEIPASS/macbin/brightness          (PyInstaller bundle)
      3) PATH                               (last resort)
    """
    exe = "brightness"
    candidates: list[Optional[Union[str, Path]]] = [
        APP_DIR / "macbin" / exe,
        (Path(getattr(sys, "_MEIPASS", "")) / "macbin" / exe) if getattr(sys, "_MEIPASS", "") else None,
        shutil.which(exe),
    ]
    for c in candidates:
        try:
            if c and Path(str(c)).exists():
                p = Path(str(c))
                if os.name != "nt":  # ensure exec bit on Unix-y systems
                    try:
                        st = p.stat()
                        if not (st.st_mode & 0o111):
                            p.chmod(st.st_mode | 0o111)
                    except Exception:
                        pass
                return str(p)
        except Exception:
            pass
    return None

# ─────────────── NEW: robust audio player + playsound monkey-patch ───────────
def _play_mp3_windows(path: str, *, block: bool = True) -> None:
    """
    Reliable MP3 playback on Windows without MCI:
      1) ffplay (if available)
      2) pygame.mixer
      3) shell open (last resort)
    """
    # 1) ffplay (most robust; no UI)
    ff = _ffplay_from_bundle_or_path()
    if ff:
        try:
            if block:
                subprocess.run([ff, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                subprocess.Popen([ff, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass

    # 2) pygame mixer
    try:
        import pygame
        if not pygame.mixer.get_init():
            # 24k is fine for Edge 24k outputs; mixer will resample if needed
            pygame.mixer.init(frequency=24000, channels=1)
        snd = pygame.mixer.Sound(path)
        ch = snd.play()
        if block:
            while ch.get_busy():
                time.sleep(0.02)
        return
    except Exception:
        pass

    # 3) Last resort: shell open (may show a player app)
    try:
        os.startfile(path)
        if block:
            time.sleep(1.2)  # crude wait if caller expects blocking
    except Exception:
        pass

def _play_audio_file_cross(path: str, *, block: bool = True) -> None:
    """Cross-platform helper: winsound for WAV on Windows, pygame/ffplay/afplay/etc for others."""
    if not path:
        return
    p = str(path)
    ext = os.path.splitext(p)[1].lower()

    if sys.platform.startswith("win"):
        if ext in (".wav", ".wave"):
            try:
                import winsound
                flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
                if not block:
                    flags |= winsound.SND_ASYNC
                winsound.PlaySound(p, flags)
                return
            except Exception:
                pass
        _play_mp3_windows(p, block=block)
        return

    # macOS: prefer afplay
    if sys.platform == "darwin":
        af = _which("afplay")
        if af:
            try:
                if block:
                    subprocess.run([af, p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen([af, p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass

    # Linux/WSL: try ffplay, then paplay/aplay
    ff = _which("ffplay")
    if ff:
        try:
            if block:
                subprocess.run([ff, "-nodisp", "-autoexit", "-loglevel", "quiet", p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen([ff, "-nodisp", "-autoexit", "-loglevel", "quiet", p],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    for cmd in ("paplay", "aplay"):
        exe = _which(cmd)
        if exe:
            try:
                if block:
                    subprocess.run([exe, p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen([exe, p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass

# Monkey-patch playsound on Windows to avoid MCI (root cause of your Error 277)
try:
    if sys.platform.startswith("win"):
        import playsound as _playsound_mod  # type: ignore[import-not-found]
        _original_playsound = getattr(_playsound_mod, "playsound", None)

        def _playsound_safe(path, block=True):
            try:
                _play_audio_file_cross(path, block=bool(block))
            except Exception:
                if callable(_original_playsound):
                    try: _original_playsound(path, block)
                    except Exception: pass

        if callable(_original_playsound):
            _playsound_mod.playsound = _playsound_safe  # type: ignore[assignment]
except Exception:
    pass
# ───────────────────────────── end robust player patch ────────────────────────


# ── cross-platform TTS (session-locked per language) ──────────────────────────
from tts_driver import get_tts
try:
    from tts_driver import init_tts_for as _init_tts_for  # new session initializer
except Exception:
    _init_tts_for = None  # fallback path below

_TTS_SESSIONS: dict[str, dict] = {}   # e.g. { "en": {...}, "hi": {...} }
_tts_legacy = None
_tts_lock = threading.RLock()

def _ensure_legacy_router():
    """Legacy router for older tts_driver versions (kept for back-compat)."""
    global _tts_legacy
    with _tts_lock:
        if _tts_legacy is None:
            _tts_legacy = get_tts()
    return _tts_legacy

def _make_session(lang_code: str) -> dict:
    """
    Create a session object for a base language (en/hi/de/fr/es).
    Prefers tts_driver.init_tts_for. Falls back to a router shim.
    """
    base = (lang_code or "en").split("-", 1)[0].lower()
    if _init_tts_for:
        try:
            sess = _init_tts_for(base)  # expected: {"engine": ..., "engine_name": "...", "voice_id": ..., "lang": "..."}
            if isinstance(sess, dict):
                return sess
        except Exception:
            pass
    eng = _ensure_legacy_router()
    return {"engine": eng, "engine_name": "router", "voice_id": None, "lang": base}

def get_session_tts(lang_code: str) -> dict:
    """Return the pre-initialized TTS session for a base language (create if missing)."""
    base = (lang_code or "en").split("-", 1)[0].lower()
    with _tts_lock:
        if base not in _TTS_SESSIONS:
            _TTS_SESSIONS[base] = _make_session(base)
            try:
                _real_speak(_TTS_SESSIONS[base], " ", wait=True)  # optional warmup
            except Exception:
                pass
        return _TTS_SESSIONS[base]

# ── centralized intents (NO locals duplicated here) ──────────────────────────
from intents import (
    SUPPORTED_LANGS as _INT_SUPPORTED_LANGS,
    guess_language_code as _intent_guess_language_code,
    said_change_language as _intent_said_change_language,
    get_language_prompt_text,
    get_invalid_language_voice_to_typed,
)

# --- Linux/WSL detector (Windows untouched) -----------------------------------
def _is_linux_or_wsl() -> bool:
    try:
        return sys.platform.startswith("linux") or ("WSL_DISTRO_NAME" in os.environ)
    except Exception:
        return False

# --- First-boot English voice lock (Linux-only) --------------------------------
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
            selected_language = (initial_lang or "en")
        except Exception:
            selected_language = "en"

def clear_boot_lang_lock() -> None:
    global _BOOT_LANG_LOCK
    _BOOT_LANG_LOCK = False

def is_boot_lang_lock_active() -> bool:
    return bool(_BOOT_LANG_LOCK)

# ── SSML sanitizer -------------------------------------------------------------
_SSML_TAG_RE = re.compile(r"</?[^>]+?>")

def _strip_ssml(text: str) -> str:
    if not text:
        return ""
    return _SSML_TAG_RE.sub("", text)

# --- Global guard for language change flow ---
LANGUAGE_FLOW_ACTIVE = False

def set_language_flow(active: bool, suppress_ms: int = 0):
    global LANGUAGE_FLOW_ACTIVE
    LANGUAGE_FLOW_ACTIVE = bool(active)
    if active and suppress_ms > 0:
        try:
            suppress_sr_prompts(int(suppress_ms))
        except Exception:
            pass


SUPPORTED_LANGS = set(_INT_SUPPORTED_LANGS)
def guess_language_code(heard: str) -> Optional[str]:
    return _intent_guess_language_code(heard)
def said_change_language(text: str) -> bool:
    return _intent_said_change_language(text)

# =============================================================================
# APP BASE & PATH HELPERS
# =============================================================================
def _app_base_dir() -> Path:
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
    p = Path(relative_path)
    if p.is_absolute() and p.exists():
        return str(p)
    meipass = getattr(sys, "_MEIPASS", None)
    roots = [BASE_DIR, BASE_DIR / "_internal"]
    if meipass:
        m = Path(meipass)
        roots += [m, m / "_internal"]
    candidates = [r / p for r in roots]
    name_only = p.name
    for r in roots:
        candidates += [r / "assets" / name_only, r / "data" / name_only, r / "handlers" / name_only, r / name_only]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(BASE_DIR / p)

# =============================================================================
# BUILD / VERSION ID (for "show tray tip once per build")
# =============================================================================
def current_build_id() -> str:
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
    p = Path(path)
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
# LOGGER
# =============================================================================
logger = logging.getLogger("NOVA")
logger.setLevel(logging.INFO)

LOG_DIR = _backend.user_data_dir() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_log_file = LOG_DIR / "nova_logs.txt"
try:
    _file_handler = logging.FileHandler(_log_file, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
    if not logger.handlers:
        logger.addHandler(_file_handler)
    logger.propagate = False
except Exception:
    pass

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

selected_language = "en"

# --- Goodbye line + hard-timed close delays (NO FALLBACKS) --------------------
GOODBYE_LINES = {
    "en": "Goodbye! See you soon.",
    "hi": "अलविदा! फिर मिलेंगे।",
    "de": "Tschüss! Bis bald.",
    "fr": "Au revoir ! À bientôt.",
    "es": "¡Adiós! Hasta pronto.",
}

# Paste your EXACT calibrated values (milliseconds) here (base values)
GOODBYE_MS = {
    "en": 2000,  # Windows English baseline (timer-based)
    "hi": 4300,
    "de": 2450,
    "fr": 3400,
    "es": 3150,
}

def _platform_goodbye_ms(base_lang: str) -> int:
    """
    Return the platform-adjusted goodbye delay for the given base language.
    We always use a timer on every OS. English values by platform:
      - Windows: 2000 ms
      - Linux/WSL (Edge Neural): 4450 ms
      - macOS: 4500 ms
    Other languages use GOODBYE_MS as-is.
    """
    ms = int(GOODBYE_MS.get(base_lang, 2000))
    try:
        if base_lang == "en":
            if sys.platform.startswith("linux") or ("WSL_DISTRO_NAME" in os.environ):
                return 4450
            if sys.platform == "darwin":
                return 4500
            if sys.platform.startswith("win"):
                return 2000
    except Exception:
        pass
    return ms

_EXIT_IN_PROGRESS = threading.Event()

def _base_ui_lang() -> str:
    return (globals().get("selected_language") or "en").split("-", 1)[0].lower()

def _settings_path() -> Path:
    d = _backend.user_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "settings.json"

_DEFAULT_SETTINGS = {
    "language": "en",
    "wake_mode": True,
    "enable_tray": True,
    "user_name": ""
}

def load_settings() -> dict:
    out = dict(_DEFAULT_SETTINGS)
    repo_base = BASE_DIR
    try:
        p = repo_base / "settings.json"
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    out.update(data)
    except Exception as e:
        try: logger.error(f"load repo settings.json failed: {e}")
        except Exception: pass

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
            try: logger.error(f"load {override_name} failed: {e}")
            except Exception: pass

    user_path = _settings_path()
    first_user_settings_write = False
    try:
        if user_path.exists():
            with user_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    out.update(data)
        else:
            user_path.parent.mkdir(parents=True, exist_ok=True)
            with user_path.open("w", encoding="utf-8") as f:
                json.dump(out, f, indent=4, ensure_ascii=False)
            first_user_settings_write = True
    except Exception as e:
        try: logger.error(f"load user settings failed: {e}")
        except Exception: pass

    try:
        if _is_wsl():
            out["enable_tray"] = False
            out["auto_restart_on_crash"] = False
            out.setdefault("tts_engine", "gtts")
    except Exception:
        pass

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

def get_user_name(default: str | None = None) -> str | None:
    try:
        s = load_settings()
        name = str(s.get("user_name", "")).strip()
        return name or default
    except Exception:
        return default

def set_user_name(name: str) -> None:
    try:
        s = load_settings()
        s["user_name"] = (name or "").strip()
        save_settings(s)
    except Exception:
        pass

def _normalize_for_tts(text: str, *, lang: str | None = None) -> str:
    lg = (lang or selected_language or "en")
    lg = lg.split("-", 1)[0].lower()
    s = "" if text is None else str(text)
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s{2,}", " ", s).strip()
    rules = {
        "en": [(r"\b[eE]\.?g\.?\b", "for example"), (r"\b[iI]\.?e\.?\b", "that is")],
        "hi": [(r"\b[eE]\.?g\.?\b", "उदाहरण के लिए"), (r"\b[iI]\.?e\.?\b", "अर्थात")],
        "de": [(r"\b[eE]\.?g\.?\b", "zum Beispiel"), (r"\b[iI]\.?e\.?\b", "das heißt")],
        "fr": [(r"\b[eE]\.?g\.?\b", "par exemple"), (r"\b[iI]\.?e\.?\b", "c’est-à-dire")],
        "es": [(r"\b[eE]\.?g\.?\b", "por ejemplo"), (r"\b[iI]\.?e\.?\b", "es decir")],
    }
    subs = rules.get(lg, rules["en"])
    for pat, repl in subs:
        s = re.sub(pat + r"(?=\s*\w)", repl + ",", s)
        s = re.sub(pat, repl, s)
    s = re.sub(r",\s*,+", ", ", s)
    return s

# ---------------- TTS core + VOICE GATE ------------------------------
_speak_lock = threading.RLock()
tts_busy = threading.Event()

def wait_for_tts_quiet(buffer_ms: int = 400):
    try:
        while tts_busy.is_set():
            time.sleep(0.02)
        if buffer_ms > 0:
            time.sleep(buffer_ms / 1000.0)
    except Exception:
        pass

def _estimate_tts_ms(text: str) -> int:
    try:
        t = _strip_ssml(text or "")
        ms = max(600, int(len(t) * 12))
        return min(ms, 12000)
    except Exception:
        return 1000

def _normalize_tts_lang(code: str) -> str:
    c = (code or "en").lower()
    if c == "en": return "en-US"
    if c == "hi": return "hi-IN"
    if c == "de": return "de-DE"
    if c == "fr": return "fr-FR"
    if c == "es": return "es-ES"
    return c

def _real_speak(sess: dict, text: str, *, wait: bool) -> None:
    if not text:
        return

    def _do():
        try:
            eng = sess.get("engine")
            name = (sess.get("engine_name") or "").lower()
            lang = (sess.get("lang") or "en")
            if hasattr(eng, "say") and hasattr(eng, "runAndWait"):
                eng.say(text)
                eng.runAndWait()
                return
            if hasattr(eng, "speak"):
                try:
                    eng.speak(text, lang_code=lang)
                except TypeError:
                    eng.speak(text)
                return
            _ensure_legacy_router().speak(text, lang_code=lang)
        except Exception:
            try:
                print("🗣️ " + text)
            except Exception:
                pass

    if wait:
        _do()
    else:
        t = threading.Thread(target=_do, daemon=True)
        t.start()

def speak(message: str, *, tts_lang: str | None = None, blocking: bool = False):
    intended = (tts_lang or selected_language or "en")
    if _is_linux_or_wsl() and is_boot_lang_lock_active():
        intended = "en"
    intended_norm = _normalize_tts_lang(intended)
    clean = _strip_ssml(_normalize_for_tts(message, lang=intended_norm))

    # Note: we do not depend on blocking behavior for shutdown timing anymore.
    suppress_sr_prompts(_estimate_tts_ms(clean) + 250)

    sess = get_session_tts(intended_norm)

    tts_busy.set()
    try:
        with _speak_lock:
            try:
                try_stop_tts_playback()
            except Exception:
                pass
            _real_speak(sess, clean, wait=blocking)
    finally:
        if blocking:
            tts_busy.clear()
        else:
            def _drain():
                time.sleep(0.05)
                tts_busy.clear()
            threading.Thread(target=_drain, daemon=True).start()

def speak_async(message: str, *, tts_lang: str | None = None):
    speak(message, tts_lang=tts_lang, blocking=False)

def _speak_multilang(en, hi="", de="", fr="", es="", log_command=None, tts_format: str = "text"):
    raw_map = {"en": en, "hi": hi, "de": de, "fr": fr, "es": es}
    ui = (selected_language or "en").lower()
    msg = raw_map.get(ui) or en
    lg = ui if raw_map.get(ui) else "en"
    clean = _strip_ssml(msg)
    speak(clean, tts_lang=lg, blocking=False)
    try:
        emit_gui("Nova", clean)
    except Exception:
        pass
    if log_command:
        log_interaction(log_command, clean, selected_language)

def _speak_multilang_async(en, hi="", de="", fr="", es="", log_command=None, tts_format: str = "text"):
    _speak_multilang(en, hi, de, fr, es, log_command, tts_format)

def try_stop_tts_playback():
    """Best-effort stop using all active session engines + legacy router."""
    try:
        for sess in list(_TTS_SESSIONS.values()):
            eng = sess.get("engine")
            try:
                if hasattr(eng, "stop"):
                    eng.stop()
            except Exception:
                pass
    except Exception:
        pass
    try:
        eng = _ensure_legacy_router()
        if hasattr(eng, "stop"):
            eng.stop()
    except Exception:
        pass

def begin_exit_with_goodbye_async(grace_timeout_s: float | None = None):
    import threading, os, sys, time

    # prevent double-triggering from multiple UI paths
    if _EXIT_IN_PROGRESS.is_set():
        return
    _EXIT_IN_PROGRESS.set()

    _shutdown = None
    try:
        from __main__ import _shutdown_main as _shutdown
    except Exception:
        try:
            from main import _shutdown_main as _shutdown
        except Exception:
            _shutdown = None

    def _worker():
        # 1) Stop wake-word listener cleanly
        try:
            from wake_word_listener import stop_wake_listener_thread, wait_for_wake_quiet
            try: stop_wake_listener_thread()
            except Exception: pass
            try: wait_for_wake_quiet(1.2)
            except Exception: pass
        except Exception:
            pass

        # 2) Stop any ongoing TTS to avoid overlap
        try:
            try_stop_tts_playback()
        except Exception:
            pass

        # 3) Speak goodbye and close using a HARD TIMER (cross-platform, no blocking reliance)
        base = _base_ui_lang()  # 'en' | 'hi' | 'de' | 'fr' | 'es'
        msg  = GOODBYE_LINES[base]
        ms   = int(_platform_goodbye_ms(base))

        try:
            # Timer starts exactly when we request speech:
            speak(msg, tts_lang=base, blocking=False)
            time.sleep(ms / 1000.0)
        except Exception:
            # even if TTS fails, fall through to shutdown
            pass

        # 4) Final drain (minimal) and exit
        try:
            wait_for_tts_quiet(150)
        except Exception:
            pass

        try:
            if callable(_shutdown):
                _shutdown()
                return
        except Exception:
            pass
        os._exit(0)

    threading.Thread(target=_worker, daemon=True).start()

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
    if not text:
        return None
    original = str(text).strip()
    low = original.lower()
    STOP_TOKENS = {
        "yes", "no", "yeah", "nope", "yup", "ok", "okay", "thanks", "thank",
        "you", "please", "hey", "hi", "hello"
    }
    STOP_TOKENS |= {
        "change", "language",
        "english", "german", "deutsch", "french", "français", "spanish", "español", "hindi",
    }
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
MIC_LOCK = threading.RLock()
NAME_CAPTURE_IN_PROGRESS: bool = False

SUPPRESS_SR_TTS_PROMPTS_UNTIL = 0.0
def suppress_sr_prompts(ms: int):
    import time as _t
    global SUPPRESS_SR_TTS_PROMPTS_UNTIL
    try:
        SUPPRESS_SR_TTS_PROMPTS_UNTIL = _t.time() + (ms / 1000.0)
    except Exception:
        SUPPRESS_SR_TTS_PROMPTS_UNTIL = 0.0

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
    global _SR_WARNED, _SR_NOTICE_SHOWN
    if not _SR_AVAILABLE:
        if not _SR_WARNED:
            try: logger.warning("listen_command not available (speech_recognition missing).")
            except Exception: pass
            _SR_WARNED = True
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

    if tts_busy.is_set() or LANGUAGE_FLOW_ACTIVE:
        return ""

    if not skip_tts_gate:
        wait_for_tts_quiet(150)
    else:
        if tts_busy.is_set() or LANGUAGE_FLOW_ACTIVE:
            return ""

    dev_index = None
    try:
        s = load_settings()
        di = s.get("mic_device_index", None)
        if isinstance(di, int):
            dev_index = di
    except Exception:
        pass

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

    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = max(150, getattr(r, "energy_threshold", 300))
    r.pause_threshold = 0.6
    r.phrase_threshold = 0.25
    r.non_speaking_duration = 0.3

    attempts = 3
    for attempt in range(attempts):
        with MIC_LOCK:
            try:
                with sr.Microphone(device_index=dev_index) as source:
                    try:
                        r.adjust_for_ambient_noise(source, duration=ambient_calib_s)
                    except Exception:
                        pass
                    audio = r.listen(source, timeout=timeout_s, phrase_time_limit=phrase_time_limit_s)
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                logger.error(f"[listen_command] mic error: {e}")
                continue

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
                            try: logger.info("[listen_command] dropped self-echo")
                            except Exception: pass
                            recognized = ""
                            break
                        recognized = txt
                        try: logger.info(f"🗣️ Recognized ({lang}): {recognized}")
                        except Exception: pass
                        break
            except sr.UnknownValueError as e:
                last_unknown_error = e
                continue
            except sr.RequestError as e:
                logger.error(f"Google STT request failed: {e}")
                break

        if recognized:
            try: _mark_command_activity()
            except Exception: pass
            return recognized

        is_last_attempt = (attempt == attempts - 1)
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
            or tts_busy.is_set()
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
    return ""

# =============================================================================
# LANGUAGE SELECTION (FUZZY + PERSISTED)
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
    set_language_flow(True, suppress_ms=8000)
    def _say_prompt():
        try:
            _speak_multilang(
                prompts["en"], hi=prompts["hi"], de=prompts["de"], fr=prompts["fr"], es=prompts["es"]
            )
        except Exception:
            try: speak(prompts.get(selected_language, prompts["en"]))
            except Exception: pass
    try:
        for attempt in range(2):
            try:
                threading.Thread(target=_say_prompt, daemon=True).start()
            except Exception:
                _say_prompt()
            heard = listen_command(skip_tts_gate=True, timeout_s=12, phrase_time_limit_s=15)
            if heard:
                try: try_stop_tts_playback()
                except Exception: pass
                code = guess_language_code(heard)
                if code in SUPPORTED_LANGS:
                    selected_language = code
                    _save_language_choice(code)
                    text, kwargs = confirm_map[code]
                    _speak_multilang(text, **kwargs)
                    return code
                _speak_multilang(
                    invalid_line["en"],
                    hi=invalid_line["hi"], de=invalid_line["de"], fr=invalid_line["fr"], es=invalid_line["es"],
                )
                continue
            if attempt == 0:
                try: _speak_multilang("Sorry, I didn't catch that. Please try again.")
                except Exception: pass
        selected_language = "en"
        _save_language_choice("en")
        _speak_multilang("Defaulting to English.")
        return "en"
    finally:
        set_language_flow(False)

# =============================================================================
# BRIGHTNESS / VOLUME (Cross-platform)
# =============================================================================
def change_brightness(increase=True, level=None):
    """
    Cross-platform brightness control (no end-user installs):
    - Windows: WMI
    - macOS: bundled 'brightness' CLI (we look inside app bundle), fallback to PATH
    - Linux/WSL: bundled 'brightnessctl' → 'xbacklight' → 'light' → PATH
    """
    try:
        if sys.platform == "win32":
            import wmi  # type: ignore[import-not-found]
            c = wmi.WMI(namespace="wmi")
            methods = c.WmiMonitorBrightnessMethods()[0]
            current_level = c.WmiMonitorBrightness()[0].CurrentBrightness
            val = max(0, min(100, int(level))) if level is not None else (
                min(100, current_level + 30) if increase else max(0, current_level - 30)
            )
            methods.WmiSetBrightness(val, 0)

        elif sys.platform == "darwin":
            # NEW: prefer bundled macbin/brightness, then MEIPASS, then PATH
            b = _brightness_cmd()
            if b:
                # Try to read current (best-effort)
                cur = None
                try:
                    out = subprocess.check_output([b, "-l"], text=True, stderr=subprocess.DEVNULL)
                    m = re.search(r"brightness (\d+\.\d+)", out)
                    if m: cur = float(m.group(1)) * 100.0
                except Exception:
                    pass
                if level is None:
                    cur = 50 if cur is None else cur
                    val = min(100, cur + 30) if increase else max(0, cur - 30)
                else:
                    val = max(0, min(100, int(level)))
                subprocess.run([b, f"{val/100:.2f}"],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # Packaging issue if we ever hit this (macbin/brightness missing)
                raise RuntimeError("brightness tool not found in bundle")

        else:
            # Linux / WSL: brightnessctl → xbacklight → light
            for tool in ("brightnessctl", "xbacklight", "light"):
                exe = _which(tool)
                if not exe:
                    continue
                try:
                    if tool == "brightnessctl":
                        if level is None:
                            step = "30%+" if increase else "30%-"
                            subprocess.run([exe, "set", step],
                                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            val = None
                        else:
                            val = max(0, min(100, int(level)))
                            subprocess.run([exe, "set", f"{val}%"],
                                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    elif tool == "xbacklight":
                        if level is None:
                            subprocess.run([exe, "-inc" if increase else "-dec", "30"],
                                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            val = None
                        else:
                            val = max(0, min(100, int(level)))
                            subprocess.run([exe, "-set", str(val)],
                                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    elif tool == "light":
                        if level is None:
                            step = "30" if increase else "-30"
                            subprocess.run([exe, "-A" if increase else "-U", step],
                                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            val = None
                        else:
                            val = max(0, min(100, int(level)))
                            subprocess.run([exe, "-S", str(val)],
                                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                except Exception:
                    # try next tool
                    continue
            else:
                raise RuntimeError("No brightness tool found")

        msg_val = f"{val} percent" if isinstance(val, (int, float)) else "the requested level"
        _speak_multilang(
            f"Brightness adjusted to {msg_val}.",
            hi="ब्राइटनेस समायोजित कर दी गई है।",
            de="Helligkeit wurde angepasst.",
            fr="La luminosité a été ajustée.",
            es="La luminosidad se ha ajustado."
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
    """
    Cross-platform volume control:
    - Windows: pycaw
    - macOS: osascript
    - Linux/WSL: pactl → pamixer → amixer
    """
    level = max(0, min(100, int(level)))
    try:
        if sys.platform == "win32":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-not-found]
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            min_vol, max_vol, _ = volume.GetVolumeRange()
            new_level = min_vol + (level / 100.0) * (max_vol - min_vol)
            volume.SetMasterVolumeLevel(new_level, None)

        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        else:
            if _which("pactl"):
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif _which("pamixer"):
                subprocess.run(["pamixer", "--set-volume", str(level)],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif _which("amixer"):
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                raise RuntimeError("No mixer tool found")

        _speak_multilang(
            f"Volume set to {level} percent.",
            hi=f"वॉल्यूम {level} प्रतिशत पर सेट कर दी गई है।",
            de=f"Lautstärke wurde auf {level} Prozent eingestellt.",
            fr=f"Le volume a été réglé à {level} %.",
            es=f"El volumen se ha ajustado al {level} %."
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
        if s in {"on", "true", "1", "yes", "enabled", "always_on"}: return True
        if s in {"off", "false", "0", "no", "disabled", "always_off"}: return False
        return False
    return bool(v)

def get_wake_mode() -> bool:
    s = load_settings()
    v = s.get("wake_mode", True)
    b = _to_bool(v)
    if not isinstance(v, bool):
        s["wake_mode"] = b
        save_settings(s)
    return b

def set_wake_mode(enabled, *_, **__) -> None:
    b = _to_bool(enabled)
    s = load_settings()
    s["wake_mode"] = b
    save_settings(s)

# =============================================================================
# GRAPH HELPERS
# =============================================================================
def graphs_dir() -> str:
    gd = _backend.user_data_dir() / "graphs"
    gd.mkdir(parents=True, exist_ok=True)
    return str(gd)

def announce_saved_graph(path: str) -> str:
    filename = os.path.basename(path)
    parent   = os.path.dirname(path.rstrip(os.sep))
    folder   = os.path.basename(parent) or parent or "folder"
    msg = f"Your graph has been saved as {filename} in {folder} folder."
    try:
        speak(msg)
    except Exception:
        try: print(msg)
        except Exception: pass
    return msg

# =============================================================================
# USER ACTIVITY TIMESTAMP
# =============================================================================
_LAST_ACTIVITY_TS: float = 0.0

def _mark_command_activity():
    global _LAST_ACTIVITY_TS
    _LAST_ACTIVITY_TS = time.time()

def last_activity_ts() -> float:
    return _LAST_ACTIVITY_TS
