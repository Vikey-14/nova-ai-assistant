# -- main.py --

# --- ensure local modules (utils, gui_interface, etc.) are importable ---
import os, sys, atexit, importlib.util
import socket, subprocess
from pathlib import Path

def _app_dir():
    try:
        if getattr(sys, 'frozen', False):  # PyInstaller EXE
            return os.path.dirname(sys.executable)
    except Exception:
        pass
    return os.path.dirname(os.path.abspath(__file__))  # source

APP_DIR = _app_dir()
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# --- Hashed name-blocklist bootstrap (reads hashed.txt and sets env var) ---
def _bootstrap_hashed_blocklist():
    import os, sys
    from pathlib import Path

    def _log(msg: str):
        """Write logs to tidy locations only:
           - release build:   <app>\_internal\logs\nova_logs.txt
           - dev (from src):  <repo>\nova_logs.txt
        """
        try:
            app_dir = Path(getattr(sys, "executable", __file__)).parent
            dev_dir = Path(__file__).parent
            targets = [
                app_dir / "_internal" / "logs" / "nova_logs.txt",  # release
                dev_dir / "nova_logs.txt",                         # dev
            ]
            for lt in targets:
                try:
                    lt.parent.mkdir(parents=True, exist_ok=True)
                    with lt.open("a", encoding="utf-8") as lg:
                        lg.write(msg.rstrip() + "\n")
                    break
                except Exception:
                    continue
        except Exception:
            pass

    # If already provided via env, just note it and stop.
    if os.getenv("NOVA_HASHED_NAME_BLOCKLIST"):
        _log("[blocklist] NOVA_HASHED_NAME_BLOCKLIST already set in environment")
        return

    try:
        here    = Path(__file__).parent
        meipass = Path(getattr(sys, "_MEIPASS", here))
        app_dir = Path(getattr(sys, "executable", __file__)).parent  # onedir anchor

        # Candidate paths (highest priority first)
        candidates = [
            # what your build actually contains
            app_dir / "_internal" / "data" / "hashed.txt",
            app_dir / "data" / "hashed.txt",
            app_dir / "hashed.txt",

            # frozen temp dir / fallback
            meipass / "_internal" / "data" / "hashed.txt",
            meipass / "data" / "hashed.txt",
            meipass / "hashed.txt",

            # dev tree
            here / "data" / "hashed.txt",
            here / "hashed.txt",
        ]

        # Also try resource_path if present
        try:
            from utils import resource_path
            candidates += [
                Path(resource_path("data/hashed.txt")),
                Path(resource_path("hashed.txt")),
            ]
        except Exception:
            pass

        # de-dup while preserving order
        seen, uniq = set(), []
        for p in candidates:
            s = str(p)
            if s not in seen:
                uniq.append(p); seen.add(s)

        _log("[blocklist] candidates:")
        for p in uniq:
            _log(f"  - {p}")

        chosen = None
        hashes = []
        for p in uniq:
            try:
                if p.exists():
                    lines = p.read_text(encoding="utf-8").splitlines()
                    hashes = [ln.strip().lower() for ln in lines if ln.strip()]
                    if hashes:
                        os.environ["NOVA_HASHED_NAME_BLOCKLIST"] = ",".join(hashes)
                        chosen = p
                        break
            except Exception:
                continue

        _log(f"[blocklist] loaded {len(hashes)} hashes from {chosen if chosen else 'NO FILE FOUND'}")

    except Exception as e:
        _log(f"[blocklist] bootstrap error: {e!r}")
        # never block startup
        pass

# Run the bootstrap FIRST (no import from hash_blocklist)
_bootstrap_hashed_blocklist()

def _pin_local_utils() -> bool:
    utils_path = os.path.join(APP_DIR, "utils.py")
    if not os.path.exists(utils_path):
        return False
    try:
        spec = importlib.util.spec_from_file_location("utils", utils_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        sys.modules["utils"] = mod
        return True
    except Exception:
        return False

_pin_local_utils()

# --- .env support (project-wide) ---
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # load .env so every module sees env vars
except Exception:
    pass

# --- DEV: reset onboarding when build id changes (RUN THIS NOW) ---
from memory_handler import clear_memory, load_from_memory, save_to_memory
from utils import current_build_id, _settings_path  # note: _settings_path import

def _maybe_reset_on_new_build():
    # enabled by default; export DEV_RESET_ON_UPDATE=0 to disable
    if os.getenv("DEV_RESET_ON_UPDATE", "1") not in ("1","true","True","YES","yes"):
        return
    bid  = current_build_id()
    seen = load_from_memory("onboarded_build_id")
    if seen != bid:
        # wipe onboarding keys so first-boot flow runs on this build
        for k in ("name", "language", "language_confirmed", "first_boot"):
            try: clear_memory(k)
            except Exception: pass
        # nuke settings.json so defaults (English, tray ON, no name) are recreated
        try:
            p = _settings_path()
            if p.exists():
                p.unlink()
        except Exception:
            pass
        save_to_memory("onboarded_build_id", bid)

_maybe_reset_on_new_build()  # ← run BEFORE any settings read / GUI / wake


# 📂 main.py

from utils import (
    listen_command,
    speak,
    _speak_multilang,
    log_interaction,
    load_settings,
    get_wake_mode,
    set_wake_mode,          # ⬅️ keep imported
    logger,
    wait_for_tts_quiet,
    set_language_flow,
)

# --- First-run default for Wake: persist ON if unset ---
try:
    # If no user setting exists yet, write wake_mode=True so both main GUI and tray
    # read a real, persisted boolean on disk from the very start.
    wm = get_wake_mode()  # may return None/False/True depending on your utils impl
    if wm is None:
        # Persist ON once so future reads don't depend on defaults/fallbacks
        set_wake_mode(True, persist=True, notify=False)
except Exception:
    # Never allow startup to fail just because of wake initialization
    pass


from utils import extract_name
import utils  # load_settings/save_settings/current_build_id

import tkinter as tk
import math, threading, time, traceback, re, random

# Ensure in-memory language matches persisted settings from first boot onward
try:
    _cfg = load_settings()
    utils.selected_language = (_cfg.get("language") or "en").lower()
except Exception:
    utils.selected_language = "en"

# ---- Guarded import: langdetect is optional ----
try:
    from langdetect import detect  # real detector
except Exception:
    def detect(_text: str) -> str:  # fallback
        return "unknown"

from platform_adapter import get_backend
_backend = get_backend()


from normalizer import normalize_hinglish
from memory_handler import save_to_memory, load_from_memory


# ---- Linux/WSL: force a clean first-boot if requested ------------------------
import os, sys
IS_LINUX_OR_WSL = sys.platform.startswith("linux") or ("WSL_DISTRO_NAME" in os.environ)
FORCE_FIRST_BOOT = IS_LINUX_OR_WSL and (os.environ.get("NOVA_FIRST_BOOT") == "1" or "--first-boot" in sys.argv)

if FORCE_FIRST_BOOT:
    try:
        # wipe stored name/lang so onboarding runs fresh
        from memory_handler import save_to_memory
        save_to_memory("name", "")
        save_to_memory("language", "")
    except Exception:
        pass
    utils.selected_language = "en"
    try:
        utils.enable_boot_lang_lock_if_needed("en")
    except Exception:
        pass


# ❌ removed any wake_word_listener start/stop imports per the new design

from intents import (
    said_change_language,
    TELL_ME_TRIGGERS,
    parse_category_from_choice,
    parse_typed_name_command,
    is_followup_text,
    guess_language_code,
    SUPPORTED_LANGS,
    CURIOSITY_MENU,
    is_yes, is_no,
    extract_name_freeform,
    parse_confirmation_or_name,
    get_language_prompt_text,
    get_invalid_language_line_typed,
    get_invalid_language_voice_to_typed,
)

_LANG_PICKER_RUNNING = threading.Event()
_EXITING = threading.Event()
_LAST_CHANGE_LANG_PROBE = [0.0]
ENABLE_CHANGE_LANG_HOTPHRASE_PROBE = True  # set True to allow saying "change language" even when Wake is ON

# ---- first-run Quick Start (main-preferred, tray fallback, cross-proc lock) ---
SINGLETON_ADDR = ("127.0.0.1", 50573)

# ---- polite exit server (for tray -> main) ----
EXIT_ADDR = ("127.0.0.1", 50574)

def _start_exit_server():
    import socket, threading, time, os
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(EXIT_ADDR)
    except OSError:
        # already bound by the main process
        return
    s.listen(2)

    def _serve():
        while True:
            try:
                conn, _ = s.accept()
            except Exception:
                break
            with conn:
                try:
                    cmd = (conn.recv(64) or b"").decode("utf-8", "ignore").strip().upper()
                except Exception:
                    cmd = ""
                if cmd == "EXIT":
                    try:
                        if not _EXITING.is_set():
                            _EXITING.set()
                            import utils
                            utils.begin_exit_with_goodbye_async()  # speak → close (event-driven)
                        try:
                            conn.sendall(b"OK\n")
                        except Exception:
                            pass
                    except Exception:
                        try:
                            _shutdown_main()
                        except Exception:
                            os._exit(0)

    threading.Thread(target=_serve, daemon=True).start()

# Start this very early
_start_exit_server()


APPDATA_DIR = _backend.user_data_dir()
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

FIRST_TIP_SENTINEL = APPDATA_DIR / ".quick_start_shown"

# NEW: cross-process "tip is open" lock
TIP_LOCK_PATH = APPDATA_DIR / ".quick_start_open"

import atexit, os
from pathlib import Path

_PIDFILE = APPDATA_DIR / "nova_main.pid"

def _write_pidfile():
    try:
        _PIDFILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

def _remove_pidfile():
    try:
        if _PIDFILE.exists():
            _PIDFILE.unlink()
    except Exception:
        pass



def _acquire_tip_lock() -> bool:
    try:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        TIP_LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        return False

def _release_tip_lock_safely():
    try:
        if TIP_LOCK_PATH.exists():
            TIP_LOCK_PATH.unlink()
    except Exception:
        pass

# ensure lock is removed on normal shutdown
atexit.register(_release_tip_lock_safely)

# also remove the PID file on normal interpreter exits
atexit.register(_remove_pidfile)

_TIP_TIMER_ID = None
TIP_WIN = None

# Fixed delays measured FROM the instant the ready line speech begins
TIP_DELAY_MS = {"en": 1800, "hi": 5700, "de": 2650, "fr": 3100, "es": 3050}

def _schedule_tip_after_ready_line(code: str):
    try:
        try:
            logger.info(
                f"Tip: scheduling after ready line (lang={code}, sentinel_exists={FIRST_TIP_SENTINEL.exists()}, lock_exists={TIP_LOCK_PATH.exists()})"
            )
        except Exception:
            pass

        if FIRST_TIP_SENTINEL.exists() or TIP_LOCK_PATH.exists():
            return

        # cancel any prior pending timer in this session (safety)
        global _TIP_TIMER_ID
        if _TIP_TIMER_ID:
            try:
                nova_gui.root.after_cancel(_TIP_TIMER_ID)
            except Exception:
                pass
            _TIP_TIMER_ID = None

        delay = TIP_DELAY_MS.get(code or "en", TIP_DELAY_MS["en"])

        # fire helper (prefer main GUI)
        def _fire_tip():
            try:
                _signal_tray_show_tip_once()
            except Exception:
                pass

        # schedule via Tk; fall back to thread timer if needed
        try:
            _TIP_TIMER_ID = nova_gui.root.after(delay, _fire_tip)
        except Exception:
            threading.Timer(delay / 1000.0, _fire_tip).start()

        # --- watchdog: if nothing shows, try again after delay + 4s ---
        def _tip_watchdog():
            try:
                if (not FIRST_TIP_SENTINEL.exists()) and (not TIP_LOCK_PATH.exists()):
                    _signal_tray_show_tip_once()  # normal (non-force) path
            except Exception:
                try:
                    _signal_tray_show_tip_once()
                except Exception:
                    pass

        try:
            wd_delay_ms = delay + 4000
            if "nova_gui" in globals() and getattr(nova_gui, "root", None):
                nova_gui.root.after(wd_delay_ms, _tip_watchdog)
            else:
                threading.Timer(wd_delay_ms / 1000.0, _tip_watchdog).start()
        except Exception:
            threading.Timer((delay + 4000) / 1000.0, _tip_watchdog).start()

    except Exception:
        # if scheduling itself errors, just try now (preferred path wrapper decides)
        try:
            _signal_tray_show_tip_once()
        except Exception:
            pass


# -------------------------------
# Optional: make sure the Tray is running (so TIP/wake sync just work)
# -------------------------------

def _ensure_tray_running():
    # 0) Skip tray in WSL or when user disabled it
    try:
        import os, platform
        if ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in platform.release().lower()):
            return False
    except Exception:
        pass

    try:
        s = load_settings()  # respect settings (WSL override turned it off)
        if not s.get("enable_tray", True):
            return False
    except Exception:
        pass

    # 1) Ping tray
    try:
        with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c:
            c.sendall(b"HELLO\n")
            if b"NOVA_TRAY" in c.recv(64):
                return True
    except Exception:
        pass

    # 2) Prefer a backend method if available
    try:
        launcher = getattr(_backend, "launch_tray_app", None)
        if callable(launcher) and launcher():
            for _ in range(10):
                try:
                    with socket.create_connection(SINGLETON_ADDR, timeout=0.4) as c:
                        c.sendall(b"HELLO\n")
                        if b"NOVA_TRAY" in c.recv(64):
                            return True
                except Exception:
                    time.sleep(0.2)
    except Exception:
        pass

    # 3) Try common sibling binaries (all OSes)
    base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) \
               else Path(__file__).parent

    names = ["NovaTray", "nova_tray", "tray_app", "Nova Tray"]
    exts  = ["", ".exe"]  # "" works on macOS/Linux

    for stem in names:
        for ext in exts:
            p = base_dir / f"{stem}{ext}"
            if p.exists():
                try:
                    if sys.platform == "darwin" and p.suffix == ".app":
                        subprocess.Popen(["open", "-a", str(p)], close_fds=True)
                    else:
                        subprocess.Popen([str(p)], cwd=str(p.parent), close_fds=True)
                    break
                except Exception:
                    pass

    # 4) Fallback: run the Python script if present
    if not getattr(sys, "frozen", False):
        tray_py = base_dir / "tray_app.py"
        if tray_py.exists():
            py = Path(sys.executable)
            pyw = py.with_name("pythonw.exe") if os.name == "nt" else py
            try:
                subprocess.Popen([str(pyw), str(tray_py)], cwd=str(tray_py.parent), close_fds=True)
            except Exception:
                pass

    # 5) Re-ping
    for _ in range(10):
        try:
            with socket.create_connection(SINGLETON_ADDR, timeout=0.4) as c:
                c.sendall(b"HELLO\n")
                if b"NOVA_TRAY" in c.recv(64):
                    return True
        except Exception:
            time.sleep(0.2)
    return False


# -------------------------------
# Async TTS wrappers (non-blocking)
# -------------------------------
def speak_async(text: str):
    threading.Thread(target=lambda: speak(text), daemon=True).start()

def _speak_multilang_async(en: str, hi: str | None = None, de: str | None = None,
                           fr: str | None = None, es: str | None = None):
    threading.Thread(
        target=lambda: _speak_multilang(en, hi=hi, de=de, fr=fr, es=es),
        daemon=True
    ).start()


# -------------------------------
# Post-once chat helpers (prevent duplicate bubbles)
# -------------------------------
_POSTED_KEYS = set()
_last_chat_line = [""]

# NEW: allow cancelling a scheduled once-per-key bubble
_CANCELLED_KEYS = set()
def _cancel_post(key: str):
    if not key:
        return
    try:
        _CANCELLED_KEYS.add(key)
    except Exception:
        pass


def _safe_show(who: str, text: str, *, allow_duplicate: bool = False):
    try:
        if (not allow_duplicate) and (text.strip() == _last_chat_line[0].strip()):
            return
        _last_chat_line[0] = text
        nova_gui.show_message(who, text)
    except Exception:
        pass

def _show_once(who: str, text: str, key: str | None = None, delay_ms: int = 220, *, allow_duplicate: bool = False):
    if key and (key in _POSTED_KEYS or key in _CANCELLED_KEYS):
        return
    try:
        def _do():
            if key and key in _CANCELLED_KEYS:
                return
            if key:
                _POSTED_KEYS.add(key)
            _safe_show(who, text, allow_duplicate=allow_duplicate)
        nova_gui.root.after(delay_ms, _do)
    except Exception:
        if key:
            if key in _CANCELLED_KEYS:
                return
            _POSTED_KEYS.add(key)
        _safe_show(who, text, allow_duplicate=allow_duplicate)


def _flush_langpicker_bubbles():
    """Cancel any scheduled 'repeat/prompt' bubbles from the language picker and cut their TTS."""
    try:
        for k in (
            "lang_picker_prompt",
            "lang_repeat_once",
            "lang_try_another_way",
            "lang_type_fallback",
            "lang_type_prompt_again",
        ):
            _cancel_post(k)
    except Exception:
        pass
    try:
        utils.try_stop_tts_playback()
    except Exception:
        pass


def _handoff_after_language(code: str):

    # Lift the first-boot English TTS lock now that language is set (all OS)
    try:
        utils.clear_boot_lang_lock()
    except Exception:
        pass

    # Warm the newly selected Piper voice immediately so the ready line is instant
    try:
        utils.get_session_tts(code)
    except Exception:
        pass

    _flush_langpicker_bubbles()

    # Speak & show the ready line. Only when it fully finishes, un-gate language flow.
    def _after_ready():
        try:
            wait_for_tts_quiet(500)   # small safety cushion after TTS stops
        except Exception:
            pass
        set_language_flow(False)       # language flow done; tray handles wake state
        # NEW: arm idle AFTER the ready line fully finishes
        try:
            schedule_idle_prompt()
        except Exception:
            pass
        # ❌ (removed) do not start mic here; tray owns it

    # Show the ready line EVERY time language changes (no dedupe key here)
    _speak_ready_and_schedule_tip(code, key=None, after_speech=_after_ready)

# -------------------------------
# Speak first, then show helpers (ONLY for setup flow as discussed)
# -------------------------------
def _estimate_tts_ms(text: str) -> int:
    words = max(1, len((text or "").split()))
    secs = words / (160 / 60.0)
    return int(min(7000, max(800, secs * 1000)))  # clamp 800ms–7000ms


def _say_then_show(text: str, key: str | None = None, after_speech=None, *, force_bubble: bool = False):
    def worker():
        try:
            speak(text, blocking=True)
            wait_for_tts_quiet(200)
        finally:
            try:
                if key and key in _CANCELLED_KEYS:
                    return
                nova_gui.root.after(0, lambda: _show_once(
                    "Nova", text, key=key, delay_ms=0, allow_duplicate=force_bubble
                ))
            finally:
                if callable(after_speech):
                    try:
                        nova_gui.root.after(0, after_speech)
                    except Exception:
                        try:
                            after_speech()
                        except Exception:
                            pass
    threading.Thread(target=worker, daemon=True).start()


def _bubble_localized_say_first(
    en: str,
    hi: str | None = None,
    de: str | None = None,
    fr: str | None = None,
    es: str | None = None,
    key: str | None = None,
    after_speech=None,
    *, force_bubble: bool = False
):
    lang = utils.selected_language or "en"
    chosen = {"en": en, "hi": hi, "de": de, "fr": fr, "es": es}.get(lang) or en
    _say_then_show(chosen, key=key, after_speech=after_speech, force_bubble=force_bubble)


def _speak_ready_and_schedule_tip(code: str, *, key: str | None = None, after_speech=None):
    # (Your ready-line speech/handoff happens before this function is called)
    _sr_mute(20000)

    # 1) Schedule the Quick Tip (existing line)
    _schedule_tip_after_ready_line(code)

    # 2) ROBUST WAKE RE-ARM (fires even if the tip is skipped/sentinel exists)
    #    We schedule two timers:
    #      - Tk .after(...)      -> preferred (ms)
    #      - threading.Timer(...) -> backup (seconds) in case Tk loop is busy
    try:
        delay_ms = TIP_DELAY_MS.get(code or "en", TIP_DELAY_MS["en"])  # tip delay (ms) from ready-line start
        fallback_ms = delay_ms + 6000  # ~6s after the tip window (feel free to change to +200 for snappier)

        def _force_wake():
            try:
                logger.info(f"[wake-fallback] forcing wake after {fallback_ms}ms (lang={code})")
                set_wake_mode(True)
                _sync_wake_ui_from_settings()
            except Exception as e:
                try:
                    logger.exception(f"[wake-fallback] error: {e}")
                except Exception:
                    pass

        # Prefer Tk timer (milliseconds)
        try:
            if getattr(nova_gui, "root", None):
                nova_gui.root.after(fallback_ms, _force_wake)
        except Exception:
            pass

        # Always set a backup thread timer (seconds)
        import threading
        threading.Timer(fallback_ms / 1000.0 + 0.5, _force_wake).start()

    except Exception as e:
        try:
            logger.exception(f"[wake-fallback] scheduling failed: {e}")
        except Exception:
            pass

    # 3) First line after ready (unchanged)
    _bubble_localized_say_first(
        "How can I help you today?",
        hi="मैं आज आपकी कैसे मदद कर सकती हूँ?",
        de="Wie kann ich dir heute helfen?",
        fr="Comment puis-je t'aider aujourd'hui ?",
        es="¿Cómo puedo ayudarte hoy?",
        key=key,
        after_speech=after_speech,
    )


def _interruptible_lang_prompt_and_listen(
    prompt_texts: dict[str, str],
    min_wait_s: int = 12,
    hard_timeout_s: int = 15
) -> str:
    ui = (utils.selected_language or "en")
    full = (
        prompt_texts.get(ui)
        or prompt_texts.get("en")
        or "Please tell me the language you'd like to use."
    )

    _bubble_localized_say_first(
        en=prompt_texts.get("en", full),
        hi=prompt_texts.get("hi"),
        de=prompt_texts.get("de"),
        fr=prompt_texts.get("fr"),
        es=prompt_texts.get("es"),
        key=None,
        after_speech=lambda: _sr_mute(7000),
    )

    heard = _listen_with_min_wait(
        min_wait_s=min_wait_s,
        hard_timeout_s=hard_timeout_s,
        skip_tts_gate=True
    )

    if heard:
        try:
            utils.try_stop_tts_playback()
        except Exception:
            pass
        return heard

    return ""

# -------------------------------------------------------------------
# Local Quick Start dialog (IDENTICAL design/size as Tray; with lock)
# -------------------------------------------------------------------
def show_quick_start_dialog(parent: tk.Tk | None = None, platform_hint: str | None = None):

    global TIP_WIN

    try:
        if TIP_LOCK_PATH.exists():
            try:
                if TIP_WIN is not None and TIP_WIN.winfo_exists():
                    TIP_WIN.deiconify(); TIP_WIN.lift(); TIP_WIN.focus_force()
            except Exception:
                pass
            return
    except Exception:
        pass

    try:
        popup = tk.Toplevel(master=parent)
        popup.withdraw()
        TIP_WIN = popup
        popup.title("Nova • Quick Start")
        popup.geometry("420x300")
        popup.configure(bg="#1a103d")
        popup.resizable(False, False)
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass

        _acquire_tip_lock()

        try:
            from utils import resource_path
            ico = resource_path("nova_icon_big.ico")
            try:
                popup.iconbitmap(ico)
            except Exception:
                pass
        except Exception:
            pass

        _closing = [False]
        _orbit_after = [None]
        _stars_after = [None]

        def _safe_after(ms, fn):
            if _closing[0] or not popup.winfo_exists(): return None
            return popup.after(ms, fn)

        def _cancel_afters():
            for aid in (_orbit_after[0], _stars_after[0]):
                if aid:
                    try: popup.after_cancel(aid)
                    except Exception: pass

        def _close():
            global TIP_WIN
            _closing[0] = True
            _cancel_afters()
            _release_tip_lock_safely()
            try:
                APPDATA_DIR.mkdir(parents=True, exist_ok=True)
                if not FIRST_TIP_SENTINEL.exists():
                    FIRST_TIP_SENTINEL.write_text("1", encoding="utf-8")
            except Exception:
                pass
            try:
                popup.destroy()
            finally:
                TIP_WIN = None

        popup.protocol("WM_DELETE_WINDOW", _close)
        popup.bind("<Escape>", lambda e: _close())
        popup.bind("<Return>", lambda e: _close())

        WIDTH, HEIGHT = 420, 300
        canvas = tk.Canvas(popup, width=WIDTH, height=HEIGHT,
                           bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        star_layers = {1: [], 2: [], 3: []}
        import random, math
        for layer in star_layers:
            count = 22 if layer == 1 else 14
            for _ in range(count):
                x = random.randint(0, WIDTH); y = random.randint(0, HEIGHT)
                size = layer
                star = canvas.create_oval(x, y, x+size, y+size, fill="#c9cfff", outline="")
                star_layers[layer].append(star)

        def animate_stars():
            if _closing[0] or not popup.winfo_exists(): return
            for layer, stars in star_layers.items():
                dx = 0.2 * layer
                for s in stars:
                    canvas.move(s, dx, 0)
                    coords = canvas.coords(s)
                    if coords and coords[0] > WIDTH:
                        canvas.move(s, -WIDTH, 0)
            _stars_after[0] = _safe_after(50, animate_stars)
        _stars_after[0] = _safe_after(50, animate_stars)

        try:
            # ✅ Lazy-load PIL right before use (fixes your yellow warning)
            from PIL import Image, ImageTk
            from utils import pkg_path
            from pathlib import Path

            img_path = str(pkg_path("assets", "nova_face_glow.png"))
            if not Path(img_path).exists():
                img_path = str(Path(APP_DIR) / "assets" / "nova_face_glow.png")

            img = Image.open(img_path).resize((80, 80))
            logo = ImageTk.PhotoImage(img)
            logo_id = canvas.create_image(WIDTH // 2, 84, image=logo)
            popup._logo_ref = logo

            angle = 0; radius = 10; cx, cy = WIDTH // 2, 84
            def _orbit():
                nonlocal angle
                if _closing[0] or not popup.winfo_exists(): return
                angle += 2
                rad = math.radians(angle)
                canvas.coords(logo_id, cx + radius * math.cos(rad), cy + radius * math.sin(rad))
                _orbit_after[0] = _safe_after(50, _orbit)
            _orbit_after[0] = _safe_after(50, _orbit)
        except Exception:
            pass

        # --- choose platform-specific copy ---
        ph = (platform_hint or "").lower()
        if ph not in ("win", "mac", "linux"):
            import sys as _sys, os as _os, platform as _plat
            try:
                is_wsl = ("WSL_DISTRO_NAME" in _os.environ) or ("microsoft" in _plat.release().lower())
            except Exception:
                is_wsl = False
            if _sys.platform == "darwin":
                ph = "mac"
            elif _sys.platform.startswith("linux") and not is_wsl:
                ph = "linux"
            else:
                ph = "win"

        if ph == "win":
            line1 = "Nova is running in the system tray."
            line2 = ("Tip: If you don’t see the tray icon, click the ^ arrow near the clock.\n"
                     "You can drag it out to keep it always visible.")
        elif ph == "mac":
            line1 = "Nova is running in the menu bar."
            line2 = ("Tip: Look for the Nova icon in the top-right menu bar.\n"
                     "If you don’t see it, open System Settings → Control Center and show/pin Nova.")
        else:  # linux
            line1 = "Nova is running in your system tray."
            line2 = ("Tip: Tray location depends on your desktop (GNOME, KDE, etc.).\n"
                     "Check your panel’s system tray or status area and pin Nova there.")

        # === ONLY CHANGE: OS-aware fonts ===
        import sys
        from tkinter import font as tkfont
        if sys.platform == "darwin":            # macOS
            f_title = ("Helvetica", 11)
            f_tip   = ("Helvetica", 10)
        elif sys.platform.startswith("linux"):  # Linux
            try:
                f_title = ("Noto Sans", 11)
                f_tip   = ("Noto Sans", 10)
            except Exception:
                base = tkfont.nametofont("TkDefaultFont")
                fam  = base.actual("family")
                f_title = (fam, 11)
                f_tip   = (fam, 10)
        else:                                   # Windows
            f_title = ("Segoe UI", 11)
            f_tip   = ("Segoe UI", 10)

        # --- body copy (OS-aware Y: Linux headline at 148; others at 156) ---
        y_title = 148 if ph == "linux" else 156
        y_tip   = 198

        canvas.create_text(WIDTH // 2, y_title, text=line1,
                           font=f_title, fill="#dcdcff",
                           width=WIDTH - 60, justify="center")
        canvas.create_text(WIDTH // 2, y_tip, text=line2,
                           font=f_tip, fill="#9aa0c7",
                           width=WIDTH - 60, justify="center")

        base, hover = "#5a4fcf", "#9b95ff"
        btn = tk.Button(
            popup, text="Got it!", command=_close,
            font=(f_tip[0], 10, "bold"),
            bg=base, fg="white",
            activebackground=hover, activeforeground="white",
            relief="flat", bd=0, highlightthickness=0,
            padx=16, pady=8, cursor="hand2",
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=hover))
        btn.bind("<Leave>", lambda e: btn.config(bg=base))
        canvas.create_window(WIDTH // 2, HEIGHT - 36, window=btn)

        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        x = (sw - w) // 2; y = (sh - h) // 2
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.deiconify()
        try:
            popup.lift(); popup.focus_force()
            popup.after(10, lambda: popup.attributes("-topmost", False))
        except Exception:
            pass

    except Exception:
        _release_tip_lock_safely()
        raise

# ─────────────────────────────────────────────────────────────────────────────
# _signal_tray_show_tip_once with this cross-platform version (faster timeouts)
# ─────────────────────────────────────────────────────────────────────────────
def _signal_tray_show_tip_once(force: bool = False):
    import os, platform, socket, threading, sys

    # Detect platforms
    try:
        is_wsl = ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in platform.release().lower())
    except Exception:
        is_wsl = False
    is_windows = (os.name == "nt") and (not is_wsl)
    is_macos   = sys.platform == "darwin"
    is_linux   = sys.platform.startswith("linux") and (not is_wsl)

    # 1) Try to ping a running tray and ask it to show a tip (all OS)
    try:
        with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c:  # ↓ 0.6 → 0.2
            c.sendall(b"HELLO\n")
            try:
                banner = c.recv(64).decode("utf-8", "ignore").strip()
            except Exception:
                banner = ""
    except Exception:
        banner = ""

    if banner == "NOVA_TRAY":
        # Prefer to let the tray handle its own tip window
        try:
            with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c2:  # ↓ 0.6 → 0.2
                c2.sendall(b"TIP\n")
                return
        except Exception:
            pass
        # If that fails, fall through to local popup attempt below.

    # 2) Local popup fallback (Windows/macOS/Linux; WSL stays skipped)
    if is_wsl:
        return  # still skip in WSL (no real tray UX)

    # On Windows we keep the existing “focus existing / watchdog” logic.
    if is_windows:
        def _focus_existing_tip_if_any() -> bool:
            try:
                if TIP_WIN is not None and TIP_WIN.winfo_exists():
                    try:
                        TIP_WIN.deiconify(); TIP_WIN.lift(); TIP_WIN.focus_force()
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
            try:
                with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c:  # ↓ 0.6 → 0.2
                    c.sendall(b"TIP\n")
                return True
            except Exception:
                return False

        def _try_local() -> bool:
            lock_exists = False
            try:
                lock_exists = TIP_LOCK_PATH.exists()
            except Exception:
                pass

            if not force:
                if lock_exists or FIRST_TIP_SENTINEL.exists():
                    _focus_existing_tip_if_any()
                    return True

            try:
                parent = nova_gui.root if ("nova_gui" in globals() and getattr(nova_gui, "root", None)) else None
                if parent:
                    parent.after(0, lambda: show_quick_start_dialog(parent, platform_hint="win"))
                else:
                    show_quick_start_dialog(None, platform_hint="win")
                return True
            except Exception:
                return False

        def _fallback_tray_then_local_watchdog():
            try:
                banner2 = ""
                try:
                    with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c:  # ↓ 0.6 → 0.2
                        c.sendall(b"HELLO\n")
                        try:
                            banner2 = c.recv(64).decode("utf-8", "ignore").strip()
                        except Exception:
                            banner2 = ""
                except Exception:
                    banner2 = ""

                if banner2 == "NOVA_TRAY":
                    sent = False
                    try:
                        with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c3:  # ↓ 0.6 → 0.2
                            c3.sendall(b"OPEN_AND_TIP\n")
                            sent = True
                    except Exception:
                        pass

                    if not sent:
                        try:
                            with socket.create_connection(SINGLETON_ADDR, timeout=0.2) as c2:  # ↓ 0.6 → 0.2
                                c2.sendall(b"TIP\n")
                                sent = True
                        except Exception:
                            pass

                    def _wd():
                        try:
                            _try_local()
                        except Exception:
                            pass
                    try:
                        if "nova_gui" in globals() and getattr(nova_gui, "root", None):
                            nova_gui.root.after(1500, _wd)
                        else:
                            threading.Timer(1.5, _wd).start()
                    except Exception:
                        pass
                    return

                _try_local()

            except Exception:
                _try_local()

        if _try_local():
            return
        _fallback_tray_then_local_watchdog()
        return

    # macOS / Linux local popup (no Windows-specific watchdog needed)
    _try_local_popup_with_os_text()

# ─────────────────────────────────────────────────────────────────────────────
# ADD helper: tries to open the local popup with OS-specific text
# ─────────────────────────────────────────────────────────────────────────────
def _try_local_popup_with_os_text():
    # Use the shared lock/sentinel so we don’t double-show
    try:
        if TIP_LOCK_PATH.exists() or FIRST_TIP_SENTINEL.exists():
            try:
                if TIP_WIN is not None and TIP_WIN.winfo_exists():
                    TIP_WIN.deiconify(); TIP_WIN.lift(); TIP_WIN.focus_force()
                    return
            except Exception:
                pass
    except Exception:
        pass

    import os, sys, platform
    try:
        is_wsl = ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in platform.release().lower())
    except Exception:
        is_wsl = False
    if is_wsl:
        return

    if sys.platform == "darwin":
        platform_hint = "mac"
    elif sys.platform.startswith("linux"):
        platform_hint = "linux"
    else:
        platform_hint = "win"

    parent = nova_gui.root if ("nova_gui" in globals() and getattr(nova_gui, "root", None)) else None
    try:
        if parent:
            parent.after(0, lambda: show_quick_start_dialog(parent, platform_hint=platform_hint))
        else:
            show_quick_start_dialog(None, platform_hint=platform_hint)
    except Exception:
        pass


# -------------------------------
# Helper: run after GUI is visible (centered)
# -------------------------------
def _when_gui_visible(run, delay_ms: int = 200):
    def _poll():
        try:
            if (nova_gui.root.state() == "normal") and bool(nova_gui.root.winfo_viewable()):
                try:
                    nova_gui.root.after(delay_ms, run)
                except Exception:
                    run()
                return
        except Exception:
            pass
        try:
            nova_gui.root.after(120, _poll)
        except Exception:
            run()
    _poll()


# -------------------------------
# Run only after the window is truly visible *and stable*
# -------------------------------
_GUI_VISIBLE_AT = [0.0]
_GUI_LAST_CFG_AT = [0.0]

def _track_map(_evt=None):
    import time as _t
    _GUI_VISIBLE_AT[0] = _t.time()

def _track_configure(_evt=None):
    import time as _t
    _GUI_LAST_CFG_AT[0] = _t.time()

def _when_gui_stable(run, min_visible_ms: int = 1200, quiet_ms: int = 900, timeout_s: int = 20):
    import time as _t
    start = _t.time()

    def _poll():
        now = _t.time()
        try:
            visible = (nova_gui.root.state() == "normal") and bool(nova_gui.root.winfo_viewable())
        except Exception:
            visible = True

        vis_ok   = visible and (_GUI_VISIBLE_AT[0] > 0) and ((now - _GUI_VISIBLE_AT[0]) * 1000 >= min_visible_ms)
        quiet_ok = (_GUI_LAST_CFG_AT[0] > 0) and ((now - _GUI_LAST_CFG_AT[0]) * 1000 >= quiet_ms)

        if (vis_ok and quiet_ok) or ((now - start) >= timeout_s):
            try:
                nova_gui.root.after(0, run)
            except Exception:
                run()
            return

        try:
            nova_gui.root.after(120, _poll)
        except Exception:
            run()

    _poll()


# -------------------------------
# Wait for actual animation start before greeting
# -------------------------------
_ANIM_READY_MAX_WAIT_MS = 2000

def _is_animation_ready_flag() -> bool:
    try:
        for name in ("animation_ready", "anim_ready"):
            v = getattr(nova_gui, name, None)
            if isinstance(v, (bool, int)) and bool(v):
                return True
        for name in ("is_animation_ready", "is_anim_ready"):
            v = getattr(nova_gui, name, None)
            if callable(v) and v():
                return True
        composite_names = ("stars_anim_ready", "face_anim_ready", "pulse_ready", "background_anim_ready")
        present = [getattr(nova_gui, n, None) for n in composite_names if getattr(n, None) is not None]
        if present:
            if all(bool(x) for x in present):
                return True
            else:
                return False
        t = getattr(nova_gui, "anim_started_at", None)
        if t:
            return True
    except Exception:
        pass
    return False

def _after_animation_ready(run, extra_wait_ms: int = 180, max_wait_ms: int = _ANIM_READY_MAX_WAIT_MS):
    import time as _t
    start = _t.time()

    def _poll():
        now_ms = int((_t.time() - start) * 1000)
        ok = False
        try:
            ok = _is_animation_ready_flag()
        except Exception:
            ok = False

        if ok or now_ms >= max_wait_ms:
            try:
                nova_gui.root.after(extra_wait_ms, run)
            except Exception:
                run()
            return
        try:
            nova_gui.root.after(60, _poll)
        except Exception:
            run()

    _poll()


# -------------------------------
# Global crash logger
# -------------------------------

def _log_excepthook(exc_type, exc, tb):
    try:
        logger.error("UNCAUGHT EXCEPTION:\n" + "".join(traceback.format_exception(exc_type, exc, tb)))
    except Exception:
        pass

# Only install our logger when NOT frozen, so PyInstaller prints real tracebacks
try:
    if not getattr(sys, "frozen", False):
        sys.excepthook = _log_excepthook
except Exception:
    pass


def _mark_command_activity():
    try:
        import time as _t
        _LAST_CMD_DONE_AT[0] = _t.time()
    except Exception:
        _LAST_CMD_DONE_AT[0] = 1.0
    schedule_idle_prompt()

# -------------------------------
# Idle reminder (5 minutes, only when GUI is visible; fires ONCE per idle streak)
# -------------------------------
_IDLE_SECONDS = 300
_idle_timer = [None]

_LAST_CMD_DONE_AT = [0.0]

def _gui_is_visible() -> bool:
    try:
        return (nova_gui.root.state() == "normal") and bool(nova_gui.root.winfo_viewable())
    except Exception:
        return False

def schedule_idle_prompt():
    try:
        t = _idle_timer[0]
        if t and t.is_alive():
            t.cancel()
    except Exception:
        pass

    def fire():
        _idle_timer[0] = None
        try:
            if _LAST_CMD_DONE_AT[0] > 0 and _gui_is_visible():
                _bubble_localized_say_first(
                    "Standing by. Let me know what you’d like to do next.",
                    hi="मैं तैयार हूँ। बताइए अगला काम क्या करना है।",
                    de="Ich bin bereit. Sag mir, was du als Nächstes tun möchtest.",
                    fr="Je suis prête. Dis-moi ce que tu veux faire ensuite.",
                    es="Estoy lista. Dime qué quieres hacer a continuación.",
                    key="idle_standby"
                )
        except Exception:
            pass

    t = threading.Timer(_IDLE_SECONDS, fire)
    t.daemon = True
    _idle_timer[0] = t
    t.start()


# -------------------------------
# Wrong-language warning
# -------------------------------
_LAST_LANG_WARN = [0.0]
_LANG_WARN_COOLDOWN = 6.0

_NOINPUT_SUPPRESS_UNTIL = [0.0]
def _suppress_noinput_for(ms: int):
    try:
        _NOINPUT_SUPPRESS_UNTIL[0] = time.time() + (ms / 1000.0)
    except Exception:
        pass
def _noinput_suppressed() -> bool:
    try:
        return time.time() < _NOINPUT_SUPPRESS_UNTIL[0]
    except Exception:
        return False

def _sr_mute(ms: int):
    try:
        suppressor = getattr(utils, "suppress_sr_prompts", None)
        if callable(suppressor):
            suppressor(int(ms))
    except Exception:
        pass
    _suppress_noinput_for(int(ms))


def _maybe_prompt_repeat(key: str):
    import time
    from utils import get_wake_mode
    # 🔒 Only apologize during a real input session:
    #  - guided flows (language/name) OR
    #  - Wake Mode is ON (i.e., after a wake event handled by the tray)
    try:
        if not (
            utils.LANGUAGE_FLOW_ACTIVE
            or getattr(nova_gui, "name_capture_active", False)
            or getattr(nova_gui, "awaiting_name_confirmation", False)
            or bool(get_wake_mode())
        ):
            return
    except Exception:
        pass

    try:
        sr_muted = time.time() < getattr(utils, "SUPPRESS_SR_TTS_PROMPTS_UNTIL", 0.0)
    except Exception:
        sr_muted = False

    if _noinput_suppressed() or sr_muted:
        return

    _say_then_show("Sorry, I didn't catch that. Could you please repeat?", key=key)


def maybe_warn_wrong_language():
    if _noinput_suppressed():
        return
    now = time.time()
    if now - _LAST_LANG_WARN[0] < _LANG_WARN_COOLDOWN:
        return
    if getattr(nova_gui, "name_capture_active", False):
        return
    _bubble_localized_say_first(
        "Please speak in the selected language, or say or type 'change language' in the chatbox.",
        hi="कृपया चयनित भाषा में बोलें, या चैटबॉक्स में 'change language' बोलें या टाइप करके बदल सकते हैं।",
        de="Bitte sprich in der ausgewählten Sprache oder sage bzw. tippe „change language“ im Chatfeld.",
        fr="Parle dans la langue sélectionnée, ou dis ou tape « change language » dans la zone de discussion.",
        es="Por favor, habla en el idioma seleccionado, o di o escribe « change language » en el cuadro de chat.",
        key="warn_wrong_lang"
    )
    _LAST_LANG_WARN[0] = now

# -------------------------------
# Language persistence + fuzzy picker (now async-friendly)
# -------------------------------
def _announce_language_set(code: str, after_speech=None):
    lines = {
        "en": "Language set to English. You can change it anytime by saying or typing 'change language' in the chatbox provided.",
        "hi": "भाषा हिन्दी पर सेट कर दी गई है। आप इसे किसी भी समय 'change language' कहकर या दिए गए चैटबॉक्स में टाइप करके बदल सकते हैं।",
        "de": "Sprache auf Deutsch eingestellt. Du kannst sie jederzeit ändern, indem du im Chatfeld „change language“ sagst oder eingibst.",
        "fr": "La langue est définie sur le français. Tu peux la changer à tout moment en disant ou en tapant « change language » dans la zone de discussion.",
        "es": "El idioma se ha configurado en español. Puedes cambiarlo en cualquier momento diciendo o escribiendo « change language » en el cuadro de chat.",
    }
    line = lines.get(code, lines["en"])
    _sr_mute(7000)
    _say_then_show(line, key=None, after_speech=after_speech)


def _language_prompt_texts_from_intents() -> dict[str, str]:
    return {
        "en": get_language_prompt_text("en"),
        "hi": get_language_prompt_text("hi"),
        "de": get_language_prompt_text("de"),
        "fr": get_language_prompt_text("fr"),
        "es": get_language_prompt_text("es"),
    }

_LANG_ALIAS = {
    "en": {"english", "eng", "en"},
    "hi": {"hindi", "हिंदी", "हिन्दी", "hin", "hi"},
    "de": {"german", "deutsch", "ger", "de"},
    "fr": {"french", "français", "francais", "fr"},
    "es": {"spanish", "español", "espanol", "esp", "es"},
}

def _display_lang_name(ui_code: str, lang_code: str) -> str:
    NAMES = {
        "en": {"en":"English","hi":"Hindi","de":"German","fr":"French","es":"Spanish"},
        "hi": {"en":"अंग्रेज़ी","hi":"हिन्दी","de":"जर्मन","fr":"फ़्रेंच","es":"स्पैनिश"},
        "de": {"en":"Englisch","hi":"Hindi","de":"Deutsch","fr":"Französisch","es":"Spanisch"},
        "fr": {"en":"anglais","hi":"hindi","de":"allemand","fr":"français","es":"espagnol"},
        "es": {"en":"inglés","hi":"hindi","de":"alemán","fr":"francés","es":"español"},
    }
    ui = (ui_code or "en")
    return NAMES.get(ui, NAMES["en"]).get(lang_code, lang_code)

def _say_already_set_localized(code: str):
    _bubble_localized_say_first(
        en=f"{_display_lang_name('en', code)} is already set. Please choose a different language.",
        hi=f"{_display_lang_name('hi', code)} पहले से चयनित है। कृपया कोई अन्य भाषा चुनें।",
        de=f"{_display_lang_name('de', code)} ist bereits eingestellt. Bitte wähle eine andere Sprache.",
        fr=f"{_display_lang_name('fr', code)} est déjà sélectionnée. Merci de choisir une autre langue.",
        es=f"{_display_lang_name('es', code)} ya está seleccionada. Por favor, elige otro idioma.",
        key="lang_already_set",
        after_speech=lambda: _suppress_noinput_for(4000)
    )

def _alias_to_lang(txt: str) -> str | None:
    t = (txt or "").strip().casefold()
    if not t:
        return None
    for code, names in _LANG_ALIAS.items():
        for n in names:
            if re.search(rf"(^|\b){re.escape(n.casefold())}(\b|$)", t):
                return code
    m = re.fullmatch(r"(en|hi|de|fr|es)", t)
    return m.group(1) if m else None

LANG_PICKER_FROM_ONBOARDING = [False]

def pick_language_interactive_fuzzy() -> str:
    from_onboarding = bool(LANG_PICKER_FROM_ONBOARDING[0])

    try:
        nova_gui.language_capture_active = True
    except Exception:
        pass

    texts = _language_prompt_texts_from_intents()

    for attempt in range(2):
        try:
            if not getattr(nova_gui, "language_capture_active", True):
                LANG_PICKER_FROM_ONBOARDING[0] = False
                return utils.selected_language
        except Exception:
            pass

        heard = _interruptible_lang_prompt_and_listen(texts, min_wait_s=12, hard_timeout_s=15)

        if not heard:
            if attempt == 0:
                _maybe_prompt_repeat("lang_repeat_once")
            continue

        code = guess_language_code(heard)

        if code in SUPPORTED_LANGS:
            try:
                current = utils.selected_language or "en"
            except Exception:
                current = "en"

            # ── (A) SAME language during onboarding ─────────────────────────────
            if code == current and from_onboarding:
                try:
                    from memory_handler import save_to_memory, clear_memory  # ← local import (safe)
                    save_to_memory("language", code)

                    # mirror to settings.json
                    try:
                        s = utils.load_settings()
                        s["language"] = code
                        utils.save_settings(s)
                    except Exception:
                        pass

                    # ✅ NEW: mark onboarding done for this build
                    save_to_memory("onboarded_build_id", utils.current_build_id())
                    try:
                        clear_memory("pending_onboard_build_id")
                    except Exception:
                        pass

                except Exception:
                    pass

                try:
                    nova_gui.root.after(0, lambda c=code: nova_gui.apply_language_color(c))
                except Exception:
                    pass

             
                # Lift the first-boot English TTS lock now that language is set (all OS)
                try:
                    utils.clear_boot_lang_lock()
                except Exception:
                    pass

                try:
                    utils.try_stop_tts_playback()
                except Exception:
                    pass
                try:
                    utils.suppress_sr_prompts(2500)
                except Exception:
                    pass
                _flush_langpicker_bubbles()
                _announce_language_set(code, after_speech=lambda c=code: _handoff_after_language(c))

                try:
                    nova_gui.language_capture_active = False
                except Exception:
                    pass
                _mark_first_run_complete()
                LANG_PICKER_FROM_ONBOARDING[0] = False
                return code

            # ── Already set (not onboarding) ─────────────────────────────────────
            if code == current:
                _say_already_set_localized(code)
                continue

            # ── (B) NEW language chosen ─────────────────────────────────────────
            utils.selected_language = code
            try:
                from memory_handler import save_to_memory, clear_memory  # ← local import (safe)
                save_to_memory("language", code)

                # mirror to settings.json
                try:
                    s = utils.load_settings()
                    s["language"] = code
                    utils.save_settings(s)
                except Exception:
                    pass

                # ✅ NEW: mark onboarding done for this build
                save_to_memory("onboarded_build_id", utils.current_build_id())
                try:
                    clear_memory("pending_onboard_build_id")
                except Exception:
                    pass

            except Exception:
                pass

            try:
                nova_gui.root.after(0, lambda c=code: nova_gui.apply_language_color(c))
            except Exception:
                pass

            
            # Lift the first-boot English TTS lock now that language is set (all OS)
            try:
                utils.clear_boot_lang_lock()
            except Exception:
                pass

            try:
                utils.try_stop_tts_playback()
            except Exception:
                pass
            try:
                utils.suppress_sr_prompts(2500)
            except Exception:
                pass
            _flush_langpicker_bubbles()
            _announce_language_set(code, after_speech=lambda c=code: _handoff_after_language(c))

            try:
                nova_gui.language_capture_active = False
            except Exception:
                pass
            _mark_first_run_complete()
            LANG_PICKER_FROM_ONBOARDING[0] = False
            return code

        ui = (utils.selected_language or "en")
        _say_then_show(get_invalid_language_voice_to_typed(ui), key="lang_type_prompt_again")

        if attempt == 0:
            continue

    try:
        if not getattr(nova_gui, "language_capture_active", True):
            LANG_PICKER_FROM_ONBOARDING[0] = False
            return utils.selected_language
    except Exception:
        pass

    try:
        nova_gui.language_capture_active = True
    except Exception:
        pass
    _say_then_show("Still couldn't understand. Let's try this another way.",
                   key="lang_try_another_way")
    _say_then_show("I couldn’t catch that. Please type your language below in the chatbox provided, e.g. English.",
                   key="lang_type_fallback")
    LANG_PICKER_FROM_ONBOARDING[0] = False
    return ""


def set_language_persisted(force: bool = False):
    try:
        saved = load_from_memory("language") if not force else None
    except Exception:
        saved = None

    if saved in SUPPORTED_LANGS and not force:
        utils.selected_language = saved
        return saved, False

    code = pick_language_interactive_fuzzy()
    return code, True


def _run_language_picker_async():
    def worker():
        if _LANG_PICKER_RUNNING.is_set():
            return
        _LANG_PICKER_RUNNING.set()
        try:
            utils.NAME_CAPTURE_IN_PROGRESS = True
            set_language_flow(True, suppress_ms=8000)

            # ── QUIET EVERYTHING DURING THE LANGUAGE FLOW ───────────────────────
            # 1) kill any pending idle/standby reminder so it won't speak mid-flow
            try:
                t = _idle_timer[0]
                if t and hasattr(t, "cancel"):
                    t.cancel()
                _idle_timer[0] = None
            except Exception:
                pass

            # 2) cut any TTS that might still be playing as we open the picker
            try:
                utils.try_stop_tts_playback()
            except Exception:
                pass

            # 3) mute recognizer apologies ("Sorry, could you repeat?") for ~12 s
            #    (you can also call _sr_mute(12000); both route to the same suppressor)
            try:
                utils.suppress_sr_prompts(12000)
            except Exception:
                pass

            # --- boolean wake handling ---
            prev_wake = bool(get_wake_mode())
            turned_off = False
            try:
                if prev_wake:
                    set_wake_mode(False)  # boolean off
                    turned_off = True
                    try:
                        _sync_wake_ui_from_settings()
                    except Exception:
                        pass

                # Run the (voice-first) interactive language capture
                pick_language_interactive_fuzzy()

            except Exception as e:
                try:
                    logger.error(f"Language picker failed: {e}")
                except Exception:
                    pass
            finally:
                # Restore wake boolean exactly as it was
                try:
                    if turned_off:
                        set_wake_mode(prev_wake)  # restore boolean
                        try:
                            _sync_wake_ui_from_settings()
                        except Exception:
                            pass
                except Exception:
                    pass

                # re-arm the idle reminder after the flow is fully wrapped up
                try:
                    schedule_idle_prompt()
                except Exception:
                    pass

                utils.NAME_CAPTURE_IN_PROGRESS = False

        finally:
            # ✅ SAFETY NET: ALWAYS drop the language-flow gate so Wake isn't muted
            try:
                set_language_flow(False)
            except Exception:
                pass
            # Clear the running sentinel no matter what
            try:
                _LANG_PICKER_RUNNING.clear()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()

# --------------------------------------------------
# NAME VALIDATION (embedded + optional hashed list)
# --------------------------------------------------
import re as _re2, unicodedata, hashlib, os

_NAME_MIN_LEN = 2
_NAME_MAX_LEN = 15
_ALLOWED_PUNCT = {" ", "-", "'", "’"}
# Collapse all vowels to 'a' to unify laude/laudi/lauda -> laada
_VOWEL_CLASS = str.maketrans({"a": "a", "e": "a", "i": "a", "o": "a", "u": "a"})


def _normalize_unicode(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    return s.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")

# --- embedded plain (multi-lang, common items) ---
def _load_name_blocklist_plain() -> set[str]:
    return {
        # reserved/confusing
        "nova","admin","root","system","null","undefined","unknown","test",

        # dialogue / acknowledgements (multi-lang)
        "yes","no","ok","okay","yep","yeah","nope","nah","thanks","thank","thank you",
        "sí","si","gracias",
        "oui","non","merci",
        "ja","nein","danke",
        "हाँ","हां","नहीं","haan","han","nahin","nahi","shukriya","dhanyavaad","धन्यवाद","शुक्रिया","theek","thik","ठीक",

        # meme-y / non-names
        "lol","lmao","wtf","omg","rofl","xd","bruh","bro","dude",

        # profanity/adult (EN)
        "fuck","shit","sex","porn","xxx","hoe","whore","bitch",

        # profanity/adult (ES)
        "puta","puto","mierda","coño","culo","polla","sexo","porno",

        # profanity/adult (FR)
        "merde","putain","salope","connard","con","sexe","porno",

        # profanity/adult (DE)
        "scheiße","scheisse","hure","fotze","wichser","arsch","sex","porno","hurensohn",

        # profanity/adult (HI + common romanizations)
        "सेक्स","पोर्न","वेश्या","चूतिया","गांडू","कमिना","बहनचोद","मादरचोद",
        "chutiya","gaandu","kamina","kaminaa","behenchod","madarchod","vashya","veshya","rand","randi",
        "bokachoda","lawda","lawdu",

        # extra romanized variants (common one-edit neighbors)
        "benchod","behnchod","bhenchod","behenchode",
        "madarchode","maadarchod",
        "gaand","gandu","ganduu",
        "rundi","raand","bc","mc",
    }

_NAME_BLOCKLIST = _load_name_blocklist_plain()

# --- hashed high-severity list (optional) ---
# Option A: paste hashes here (one per item), or
# Option B: inject via env var NOVA_HASHED_NAME_BLOCKLIST="hash1,hash2,..."
_HASHED_BLOCKLIST: set[str] = set(
    h.strip().lower()
    for h in (os.getenv("NOVA_HASHED_NAME_BLOCKLIST", "")).split(",")
    if h.strip()
)
# If you prefer pasting directly, change to: _HASHED_BLOCKLIST = {"abc123...", "def456...", ...}

# --- canonicalization for hashing (must match the helper script) ---
_LEET_MAP = {"0":"o","1":"i","3":"e","4":"a","5":"s","7":"t","$":"s","@":"a"}

def _strip_diacritics(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

def _collapse_repeats(s: str) -> str:
    out = []
    prev = None
    for ch in s:
        if ch != prev:
            out.append(ch)
            prev = ch
    return "".join(out)

def _apply_leet(s: str) -> str:
    return "".join(_LEET_MAP.get(ch, ch) for ch in s)

def _canonicalize_for_hash(tok: str) -> str:
    t = (tok or "").casefold().strip()
    # keep letters across scripts
    t = "".join(ch for ch in t if ch.isalpha())
    t = _apply_leet(t)
    t = _strip_diacritics(t)
    t = _collapse_repeats(t)

    # family normalization (GLOBAL; applies to every token)
    if os.getenv("NOVA_STRICT_NAME_FAMILY", "1") == "1":
        t = t.replace("w", "u")        # lawda ≈ lauda/laudi/laude
        t = t.translate(_VOWEL_CLASS)  # laude/laudi/lauda -> laada
        t = t.replace("dh", "d")       # chodh -> chod (romanization wiggle)
    return t

def _normalize_spaces(s: str) -> str:
    return " ".join((s or "").split())

def _is_letter_or_allowed(ch: str) -> bool:
    return ch.isalpha() or (ch in _ALLOWED_PUNCT)

def _looks_like_name(s: str) -> bool:
    return any(c.isalpha() for c in s)

_TOKEN_SPLIT = _re2.compile(r"[ \-\u2010-\u2015'’]+")
def _tokens(s: str):
    return _TOKEN_SPLIT.split(s)

def validate_name_strict(name_raw: str) -> tuple[bool, str, str]:
    cleaned = _normalize_unicode(name_raw or "")
    cleaned = _normalize_spaces(cleaned)
    if not cleaned:
        return (False, "", "empty")
    if len(cleaned) < _NAME_MIN_LEN:
        return (False, "", "too_short")
    if len(cleaned) > _NAME_MAX_LEN:
        return (False, "", "too_long")
    if not all(_is_letter_or_allowed(ch) for ch in cleaned):
        return (False, "", "invalid_chars")
    if not _looks_like_name(cleaned):
        return (False, "", "no_letters")

    toks = [t for t in (_t.casefold() for _t in _tokens(cleaned)) if t]

    # --- FULL-STRING canonical check (catches "l a w d a", "l-a-w-d-a", "l’awda", etc.) ---
    full_canon = _canonicalize_for_hash(cleaned)
    if full_canon:
        h_full = hashlib.sha256(full_canon.encode("utf-8")).hexdigest()
        # hashed (authoritative)
        if _HASHED_BLOCKLIST and h_full in _HASHED_BLOCKLIST:
            return (False, "", "blocked")
        # plain (fallback)
        if full_canon in _NAME_BLOCKLIST:
            return (False, "", "blocked")

    # --- PRIORITIZE HASHED LIST (per-token) ---
    if _HASHED_BLOCKLIST:
        for t in toks:
            c = _canonicalize_for_hash(t)
            if not c:
                continue
            h = hashlib.sha256(c.encode("utf-8")).hexdigest()
            if h in _HASHED_BLOCKLIST:
                return (False, "", "blocked")

    # Fallback: plain list (per-token, exact token, case-insensitive)
    if any(t in _NAME_BLOCKLIST for t in toks):
        return (False, "", "blocked")

    # 3) language word guard (relies on _LANG_ALIAS defined elsewhere)
    try:
        lang_alias_union = set().union(*_LANG_ALIAS.values())  # noqa: F821 (assumed defined elsewhere)
        if cleaned.casefold() in lang_alias_union:
            return (False, "", "looks_like_language")
    except Exception:
        # If _LANG_ALIAS isn't in scope here, skip the guard gracefully.
        pass

    # 4) nice-case ASCII names
    try:
        if all(ord(c) < 128 for c in cleaned):
            cleaned = " ".join(p.capitalize() for p in cleaned.split(" "))
    except Exception:
        pass

    return (True, cleaned, "")

def reload_name_blocklist(*_args, **_kwargs):
    # Nothing to reload for the embedded set.
    # If you inject hashes via env var at runtime, you can update _HASHED_BLOCKLIST here.
    global _HASHED_BLOCKLIST
    _HASHED_BLOCKLIST = set(
        h.strip().lower()
        for h in (os.getenv("NOVA_HASHED_NAME_BLOCKLIST", "")).split(",")
        if h.strip()
    )

# -------------------------------
# Quick Start dialog (owned by main)
# -------------------------------
def _mark_first_run_complete():
    try:
        s = utils.load_settings()
        s["first_run"] = False
        s["show_quick_start_on_first_run"] = False
        utils.save_settings(s)
    except Exception:
        pass


# -------------------------------
# 10s listen helper for name attempts
# -------------------------------
def _listen_with_min_wait(
    min_wait_s: int = 10,
    hard_timeout_s: int = 12,
    *,
    skip_tts_gate: bool = False,
    disable_self_echo_filter: bool = False,
) -> str:
    """
    Keep trying to listen until at least `min_wait_s` passes.
    Stop earlier if we hear something; hard cap at `hard_timeout_s`.
    """
    start = time.time()
    deadline = start + max(hard_timeout_s, min_wait_s)
    heard = ""

    while time.time() < deadline:
        try:
            text = listen_command(
                skip_tts_gate=skip_tts_gate,
                disable_self_echo_filter=disable_self_echo_filter,
                timeout_s=None  # use utils' default
            )
        except Exception:
            text = None

        if text:
            heard = text
            break

        # Keep trying until min window satisfied
        if (time.time() - start) < min_wait_s:
            time.sleep(0.25)
            continue
        else:
            break

    return heard


# ------------------------------------------------------------------------
# Voice “name change” (ANYTIME) — but NEVER during onboarding/confirmation
# ------------------------------------------------------------------------
def _maybe_handle_voice_name_change(utterance: str) -> bool:
    """
    If the utterance sounds like 'my name is ...' (or similar), validate and save it.
    Returns True if we handled it (so the caller should skip normal processing).
    """
    # 🚧 Don't hijack first boot or an active Yes/No confirm step
    try:
        if (
            _PENDING_NAME_CONFIRM.get("active")                    # waiting on Yes/No
            or getattr(utils, "NAME_CAPTURE_IN_PROGRESS", False)   # guided capture running
            or not load_from_memory("name")                        # no saved name yet → onboarding
        ):
            return False
    except Exception:
        # If anything is weird/missing, do nothing (fail open)
        return False

    # Try to pull a candidate name out of the utterance
    try:
        raw = extract_name_freeform(utterance) or parse_typed_name_command(utterance)
    except Exception:
        raw = None
    if not raw:
        return False

    ok, cleaned, _reason = validate_name_strict(raw)
    if not ok:
        _say_then_show(
            "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
            key="name_invalid_voice_anytime"
        )
        return True

    # ✅ NEW: if the provided name is the same as the current one, don't re-set it
    try:
        current = load_from_memory("name")
        if not current:
            import utils as _u2
            current = _u2.get_user_name() or None
    except Exception:
        current = None

    if current and current.strip().casefold() == cleaned.strip().casefold():
        _say_name_already_set_localized(cleaned)
        return True

    # Save the *new* name since it’s different
    try:
        save_to_memory("name", cleaned)
    except Exception:
        pass

    # persist to settings.json
    try:
        import utils
        utils.set_user_name(cleaned)
    except Exception:
        pass

    _say_name_set_localized(cleaned)
    return True


# ----------------------------------------------------------
# Localized “name set” confirmation (used for later changes)
# ----------------------------------------------------------
def _say_name_set_localized(cleaned: str):
    _bubble_localized_say_first(
        en=f"Got it — I’ll call you {cleaned} from now on.",
        hi=f"ठीक है — अब से मैं आपको {cleaned} कहूँगी।",
        de=f"Alles klar — ich nenne dich ab jetzt {cleaned}.",
        fr=f"Compris — je t’appellerai {cleaned} à partir de maintenant.", 
        es=f"Entendido — te llamaré {cleaned} de ahora en adelante.",
        key=None,
        force_bubble=True,
    )


# -------------------------------
# Localized “already set” message
# -------------------------------
def _say_name_already_set_localized(cleaned: str):
    _bubble_localized_say_first(
        en=f"I already call you {cleaned}. If you'd like a different name, just say it or type a new name in the chatbox provided.",
        hi=f"मैं पहले से ही आपको {cleaned} कहती हूँ। अगर बदलना है, तो नया नाम चैटबॉक्स में टाइप करें या बोल दें।",
        de=f"Ich nenne dich bereits {cleaned}. Wenn du einen anderen Namen möchtest, sag ihn einfach oder tippe einen neuen Namen im bereitgestellten Chatfeld.",
        fr=f"Je t’appelle déjà {cleaned}. Si tu veux changer, dis-le simplement ou tape un nouveau nom dans la zone de discussion fournie.",
        es=f"Ya te llamo {cleaned}. Si quieres cambiar, dilo o escribe un nombre nuevo en el cuadro de chat proporcionado.",
        key=None,
        force_bubble=True,
    )
# -------------------------------
# Typed confirmation & correction helpers
# -------------------------------
_PENDING_NAME_CONFIRM = {"candidate": None, "active": False, "handled": False}
NAME_FLOW_DONE = [False]

def _clear_pending_name_confirm():
    _PENDING_NAME_CONFIRM["candidate"] = None
    _PENDING_NAME_CONFIRM["active"] = False
    _PENDING_NAME_CONFIRM["handled"] = False
    try:
        nova_gui.awaiting_name_confirmation = False
    except Exception:
        pass

def _accept_and_continue_with_name(cleaned: str):
    """Save name, confirm, and continue to language picker."""
    NAME_FLOW_DONE[0] = True  # ← stop any remaining name-capture logic

    try:
        save_to_memory("name", cleaned)
    except Exception:
        pass
    # persist to settings.json
    try:
        import utils
        utils.set_user_name(cleaned)
    except Exception:
        pass

    example_names = {"en": "Alex", "hi": "Ajay", "fr": "Alexandre", "es": "Alejandro", "de": "Alexander"}
    ex = example_names.get(utils.selected_language or "en", "Alex")
    line = f"Nice to meet you, {cleaned}! You can later change your name by saying or typing 'My name is {ex}'."

    # 🔹 tell the picker this run is part of onboarding
    LANG_PICKER_FROM_ONBOARDING[0] = True

    _sr_mute(4500)
    _say_then_show(line, key="name_ok_confirmed", after_speech=_run_language_picker_async)
    _mark_first_run_complete()
    _clear_pending_name_confirm()


# -------------------------------
# Name ask on first boot (voice → typed confirm → fallback)
# -------------------------------
def ask_user_name_on_boot_async():
    if load_from_memory("name"):
        return

    def worker():
        # Mute listen_command prompts while name capture is running.
        utils.NAME_CAPTURE_IN_PROGRESS = True

        # Reset the sentinel at the very start of the name thread
        NAME_FLOW_DONE[0] = False

        # 🔧 Pause wake while we’re in name-capture so replies don’t get routed
        prev_wake = bool(get_wake_mode())
        turned_off = False
        try:
            if prev_wake:
                # ✅ Only flip the stored wake flag; the TRAY reacts
                set_wake_mode(False)  # boolean off
                turned_off = True
                try:
                    _sync_wake_ui_from_settings()  # reflect change in UI icon/label
                except Exception:
                    pass

            _say_then_show("May I know your name?", key="ask_name", after_speech=lambda: _sr_mute(1800))

            # Two attempts; each attempt waits up to ~10s for speech
            for attempt in range(2):
                # if language flow already started, stop the name loop silently
                if NAME_FLOW_DONE[0]:
                    return

                # >>> CHANGED: allow safe barge-in on attempt 1; keep echo filter ON
                # Optional extra safety (usually not needed):
                # wait_for_tts_quiet(250)
                spoken = _listen_with_min_wait(
                    min_wait_s = 6 if attempt == 0 else 10,
                    hard_timeout_s = 12,
                    skip_tts_gate = True,            # listen immediately after short mute
                    disable_self_echo_filter = False  # keep echo guard ON for attempt 1
                )

                if not spoken:
                    if attempt == 0 and not NAME_FLOW_DONE[0]:
                        _maybe_prompt_repeat("name_repeat_once")
                    continue

                match = extract_name(spoken)
                if not match:
                    if attempt == 0 and not NAME_FLOW_DONE[0]:
                        _maybe_prompt_repeat("name_repeat_once")
                    continue

                ok, cleaned, reason = validate_name_strict(match)

                # Unified rule: ANY invalid or blocked spoken name → typed validation line
                if not ok:
                    try:
                        nova_gui.name_capture_active = True
                    except Exception:
                        pass
                    _say_then_show(
                        "Please enter a valid name below in the chatbox provided: letters only, 2–15 characters, e.g. Alex.",
                        key="name_invalid_voice_anytime"
                    )
                    return

                # Guard: don't accept language words as a name
                if cleaned.casefold() in set().union(*_LANG_ALIAS.values()):
                    try:
                        nova_gui.name_capture_active = True
                    except Exception:
                        pass
                    _say_then_show(
                        "That looks like a language. To change language, say or type 'change language'. Otherwise, please type a real name (e.g. Alex).",
                        key="name_looks_like_language"
                    )
                    return

                # ✅ Only valid names reach typed confirmation
                candidate = cleaned

                # Enable typed confirmation & corrections
                _PENDING_NAME_CONFIRM["candidate"] = candidate
                _PENDING_NAME_CONFIRM["active"] = True
                _PENDING_NAME_CONFIRM["handled"] = False
                try:
                    nova_gui.awaiting_name_confirmation = True
                except Exception:
                    pass

                _say_then_show(
                    f"I heard '{candidate}'. Is that correct? Please type 'Yes' or 'No' below in the chatbox provided.",
                    key=f"confirm_name_{attempt}"
                )

                # Force-show the full confirm sentence immediately (dedup by key)
                try:
                    nova_gui.root.after(0, lambda: _show_once(
                        "Nova",
                        f"I heard '{candidate}'. Is that correct? Please type 'Yes' or 'No' below in the chatbox provided.",
                        key=f"confirm_name_{attempt}",
                        delay_ms=0
                    ))
                except Exception:
                    _show_once(
                        "Nova",
                        f"I heard '{candidate}'. Is that correct? Please type 'Yes' or 'No' below in the chatbox provided.",
                        key=f"confirm_name_{attempt}",
                        delay_ms=0
                    )

                # Make sure speech finishes, then hand off to the typed chat intercept.
                wait_for_tts_quiet(300)
                try:
                    utils.try_stop_tts_playback()
                except Exception:
                    pass

                # 🚫 Removed time-bound wait: let the chat intercept handle typed Yes/No indefinitely.
                return

            # Safety net (normally we return above)
            if not NAME_FLOW_DONE[0]:
                try:
                    nova_gui.name_capture_active = True
                except Exception:
                    pass
                _say_then_show(
                    "Still couldn't understand. Let's try this another way.",
                    key="name_try_another_way"
                )
                _say_then_show(
                    "I couldn’t catch your name. Please type your name below in the chatbox provided, e.g. Alex.",
                    key="name_type_fallback"
                )

        finally:
            # Restore wake state and end silent mode
            try:
                if turned_off:
                    set_wake_mode(prev_wake)  # restore boolean
                    try:
                        _sync_wake_ui_from_settings()
                    except Exception:
                        pass
            except Exception:
                pass
            utils.NAME_CAPTURE_IN_PROGRESS = False

    threading.Thread(target=worker, daemon=True).start()

def _run_language_picker():
    # kept for compatibility (not used directly on the UI thread now)
    _run_language_picker_async()



# -------------------------------
# Name & Language capture via chatbox + typed intents
# -------------------------------
_awaiting_curiosity_choice = False

def _install_chatbox_name_capture_intercept():
    """
    Intercept Send/Enter while we're waiting for a typed name or language.
    Also catch typed “change language” requests, and allow 'my name is ...'
    style commands at any time.
    """
    # ⛑️ prevent double-patching
    if getattr(nova_gui, "_on_send_patched", False):
        return
    if not hasattr(nova_gui, "_on_send"):
        return

    original = nova_gui._on_send

    def _patched_on_send():
        # ✅ use module-level utils safely (no inner import)
        _u = utils

        try:
            text = nova_gui.input_entry.get().strip()
        except Exception:
            text = ""

        # 0) typed "change language" (clear the box immediately)
        #    🔽 Normalize Hinglish when UI is Hindi so the matcher sees canonical text
        norm_text = text
        if text and (_u.selected_language == "hi"):
            try:
                from normalizer import normalize_hinglish
                norm_text = normalize_hinglish(text)
            except Exception:
                norm_text = text

        if norm_text and said_change_language(norm_text):
            try:
                nova_gui.show_message("YOU", text)
            except Exception:
                pass

            _clear_entry_safe()  # ← replaced

            # ✅ CUT ANY CURRENT TTS BEFORE OPENING THE PICKER
            try:
                _u.try_stop_tts_playback()
            except Exception:
                pass

            _run_language_picker_async()
            return

        # 0.5) Typed response while awaiting name confirmation
        if _PENDING_NAME_CONFIRM.get("active") or getattr(nova_gui, "awaiting_name_confirmation", False):
            # 🔎 DEBUG TRACE: prove we intercepted the reply
            try:
                logger.info(f"[name-confirm] typed='{text}'  pending='{_PENDING_NAME_CONFIRM.get('candidate')}'")
            except Exception:
                pass

            # hard-cut any ongoing confirm prompt TTS (typed barge-in)
            try:
                _u.try_stop_tts_playback()
            except Exception:
                pass
            try:
                nova_gui.show_message("YOU", text)
            except Exception:
                pass

            # ✅ NEW: clear the input immediately on *any* typed confirm reply
            _clear_entry_safe()

            state, new_name = parse_confirmation_or_name(
                text, previous_name=_PENDING_NAME_CONFIRM.get("candidate")
            )

            if state == "confirm":
                cand = _PENDING_NAME_CONFIRM.get("candidate") or ""
                ok2, cleaned2, _reason2 = validate_name_strict(cand)
                if not ok2:
                    _say_then_show(
                        "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                        key="name_invalid_post_confirm_typed"
                    )
                    # move to typed name entry
                    try: nova_gui.name_capture_active = True
                    except Exception: pass
                    _PENDING_NAME_CONFIRM["handled"] = True
                    _clear_pending_name_confirm()
                    return
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_entry_safe()  # harmless double-clear
                _accept_and_continue_with_name(cleaned2)
                return

            if (state == "corrected") and new_name:
                ok3, cleaned3, _reason3 = validate_name_strict(new_name)
                if not ok3:
                    _say_then_show(
                        "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                        key="name_invalid_correction"
                    )
                    # ❌ invalid → keep box already cleared; user can type again
                    return
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_entry_safe()  # harmless double-clear
                _accept_and_continue_with_name(cleaned3)
                return

            if state == "deny":
                # Ask them to type the correct name
                try: nova_gui.name_capture_active = True
                except Exception: pass
                _say_then_show(
                    "Okay — Please type your name below in the chatbox provided, e.g. Alex.",
                    key="name_after_no_typed"
                )
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_pending_name_confirm()
                _clear_entry_safe()  # harmless double-clear
                return

            # Ambiguous → prompt again (we already cleared so they start fresh)
            _say_then_show(
                "Please reply with Yes/No, or type your correct name (e.g. Alex).",
                key="name_confirm_clarify"
            )
            return

        # A) typed "my name is … / call me … / name is …" command (works anytime)
        try:
            from intents import parse_typed_name_command
        except Exception:
            parse_typed_name_command = None  # safety if import fails unexpectedly

        raw = parse_typed_name_command(text) if parse_typed_name_command else None
        if raw:
            # Cut TTS immediately on typed answer
            try:
                _u.try_stop_tts_playback()
            except Exception:
                pass

            ok, cleaned, _reason = validate_name_strict(raw)
            if not ok:
                _say_then_show(
                    "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                    key="name_invalid_typed_cmd"
                )
                return

            # Also block language words as names
            if cleaned.casefold() in set().union(*_LANG_ALIAS.values()):
                _say_then_show(
                    "That looks like a language. To change language, say or type 'change language'. Otherwise, please type a real name (e.g. Alex).",
                    key="name_looks_like_language_typed"
                )
                return

            # Echo the user's message and clear the entry immediately
            try:
                nova_gui.show_message("YOU", text)
            except Exception:
                pass

            _clear_entry_safe()  # ← replaced

            # If we're in onboarding or mid-confirmation, finish name flow and start language picker
            first_run = not bool(load_from_memory("name"))
            if first_run or getattr(nova_gui, "name_capture_active", False) or getattr(nova_gui, "awaiting_name_confirmation", False):
                try:
                    nova_gui.name_capture_active = False
                except Exception:
                    pass
                _accept_and_continue_with_name(cleaned)  # sets NAME_FLOW_DONE[0]=True and starts language picker
                return

            # -------------------------------
            # Later name change (typed path)
            # -------------------------------
            # ✅ don't re-set if it's the same name (case/space-insensitive)
            try:
                current = load_from_memory("name")
                if not current:
                    current = _u.get_user_name() or None
            except Exception:
                current = None

            if current and current.strip().casefold() == cleaned.strip().casefold():
                _say_name_already_set_localized(cleaned)
                return

            # Different → save and confirm
            try:
                save_to_memory("name", cleaned)
            except Exception:
                pass
            # persist to settings.json
            try:
                _u.set_user_name(cleaned)
            except Exception:
                pass
            _say_name_set_localized(cleaned)
            return

        # 1) Language capture via typed text (mirrors Name flow)
        if getattr(nova_gui, "language_capture_active", False):
            # Cut TTS + cancel any pending prompt bubble immediately on typed barge-in
            try:
                _u.try_stop_tts_playback()
            except Exception:
                pass
            # keep recognizer/GUI quiet during the handoff
            try:
                _u.suppress_sr_prompts(2500)
            except Exception:
                pass

            code = _alias_to_lang(text)
            if not code:
                # LOCALIZED invalid-language (CURRENT UI language)
                ui = (_u.selected_language or "en")
                _say_then_show(get_invalid_language_line_typed(ui), key="lang_type_prompt_again")
                # keep capture ON so they can try again
                return

            # Determine current
            try:
                current = _u.selected_language or "en"
            except Exception:
                current = "en"

            # Same language chosen
            if code == current:
                # Echo + clear so it feels acknowledged
                try:
                    nova_gui.show_message("YOU", text)
                except Exception: pass

                _clear_entry_safe()  # ← replaced

                # If this is onboarding, accept and finish; else gently say "already set"
                if LANG_PICKER_FROM_ONBOARDING[0]:
                    try:
                        save_to_memory("language", code)
                        try:
                            s = _u.load_settings()   # read current settings.json
                            s["language"] = code     # update just the language
                            _u.save_settings(s)      # write it back
                        except Exception:
                            pass

                        # ✅ NEW (typed, onboarding branch): mark onboarding complete for this build
                        save_to_memory("onboarded_build_id", _u.current_build_id())
                        try:
                            from memory_handler import clear_memory as _clear_memory
                            _clear_memory("pending_onboard_build_id")
                        except Exception:
                            pass

                    except Exception:
                        pass
                    _u.selected_language = code

                    # 🔓 Linux/WSL only: lift the first-boot English TTS lock now that language is set
                    try:
                        _u.clear_boot_lang_lock()
                    except Exception:
                        pass

                    try:
                        nova_gui.root.after(0, lambda c=code: nova_gui.apply_language_color(c))
                    except Exception:
                        pass
                    try:
                        nova_gui.language_capture_active = False
                    except Exception:
                        pass
                    _flush_langpicker_bubbles()
                    _announce_language_set(code, after_speech=lambda c=code: _handoff_after_language(c))
                    _mark_first_run_complete()
                    return
                else:
                    _say_already_set_localized(code)
                    # stay in capture to allow picking a different one
                    return

            # valid new language -> save, apply UI tint
            try:
                save_to_memory("language", code)
                try:
                    s = _u.load_settings()   # read current settings.json
                    s["language"] = code     # update just the language
                    _u.save_settings(s)      # write it back
                except Exception:
                    pass

                # ✅ NEW (typed, non-onboarding new language): mark onboarding complete for this build
                save_to_memory("onboarded_build_id", _u.current_build_id())
                try:
                    from memory_handler import clear_memory as _clear_memory
                    _clear_memory("pending_onboard_build_id")
                except Exception:
                    pass

            except Exception:
                pass

            _u.selected_language = code

            # 🔓 Linux/WSL only: lift the first-boot English TTS lock now that language is set
            try:
                _u.clear_boot_lang_lock()
            except Exception:
                pass

            try:
                nova_gui.root.after(0, lambda c=code: nova_gui.apply_language_color(c))
            except Exception:
                pass

            # 👇 Echo the user's typed language choice
            try:
                nova_gui.show_message("YOU", text)
            except Exception:
                pass

            _clear_entry_safe()  # ← replaced

            # ✅ mark capture complete BEFORE announcing (guards other threads)
            try:
                nova_gui.language_capture_active = False
            except Exception:
                pass

            # ▶︎ announce + chain ready line + start tip timer from ready-line start)
            _flush_langpicker_bubbles()
            _announce_language_set(code, after_speech=lambda c=code: _handoff_after_language(c))

            _mark_first_run_complete()
            return

        # 2) Name capture via typed text (first-run simple path)
        if getattr(nova_gui, "name_capture_active", False):
            # Cut TTS immediately on typed answer
            try:
                _u.try_stop_tts_playback()
            except Exception:
                pass

            ok, cleaned, _reason = validate_name_strict(text)
            if not ok:
                _say_then_show(
                    "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                    key="name_invalid_again"
                )
                return

            # Also block language words as names here
            if cleaned.casefold() in set().union(*_LANG_ALIAS.values()):
                _say_then_show(
                    "That looks like a language. To change language, say or type 'change language'. Otherwise, please type a real name (e.g. Alex).",
                    key="name_looks_like_language_again"
                )
                return

            try:
                nova_gui.name_capture_active = False
            except Exception:
                pass

            _clear_entry_safe()  # ← replaced

            _accept_and_continue_with_name(cleaned)  # flips NAME_FLOW_DONE and starts language picker
            return

        # 3) normal path
        return original()

    # swap in & refresh bindings
    nova_gui._on_send = _patched_on_send
    setattr(nova_gui, "_on_send_patched", True)  # ← mark as patched (idempotent guard uses this)
    try:
        nova_gui.send_button.config(command=nova_gui._on_send)
    except Exception:
        pass
    try:
        nova_gui.input_entry.bind("<Return>", lambda e: nova_gui._on_send())
    except Exception:
        pass


# -------------------------------
# Wake defaults + UI sync
# -------------------------------
def _ensure_wake_default_on():
    try:
        s = utils.load_settings()
        if "wake_mode" not in s:
            s["wake_mode"] = True  # boolean default
            utils.save_settings(s)
    except Exception as e:
        try:
            logger.warning(f"Could not set default wake_mode=True: {e}")
        except Exception:
            pass
        

def _sync_wake_ui_from_settings():
    try:
        is_on = bool(get_wake_mode())
        label = f"Wake Mode: {'ON' if is_on else 'OFF'}"

        # Some UIs expose a boolean var used by the toggle
        if getattr(nova_gui, "wake_mode_var", None):
            try:
                nova_gui.wake_mode_var.set(is_on)
            except Exception:
                pass

        # Bottom status label often bound to a StringVar named wake_status
        if hasattr(nova_gui, "wake_status"):
            try:
                nova_gui.wake_status.set(label)
            except Exception:
                pass

        # Buttons/labels that show text directly
        for attr in ("wake_toggle_btn", "wake_button", "wake_label"):
            btn = getattr(nova_gui, attr, None)
            if btn:
                try:
                    btn.config(text=label)
                except Exception:
                    pass

        # Mic icon state
        try:
            if hasattr(nova_gui, "update_mic_icon"):
                nova_gui.update_mic_icon(is_on)
        except Exception:
            pass
    except Exception:
        pass


# --- Safe getter for GUI variables ---
def _gv(var_name, default=False):
    v = getattr(nova_gui, var_name, None)
    try:
        return v.get() if v is not None else default
    except Exception:
        return default


# -------------------------------
# Unified EXIT handler
# -------------------------------
def _shutdown_main():
    global _TIP_TIMER_ID

    # Remove the PID file early (clean shutdown path).
    try:
        _remove_pidfile()
    except Exception:
        pass

    try:
        # cancel the one-shot tray tip timer
        try:
            if _TIP_TIMER_ID is not None:
                try:
                    nova_gui.root.after_cancel(_TIP_TIMER_ID)
                except Exception:
                    pass
                _TIP_TIMER_ID = None
        except Exception:
            pass

        # cancel any Quick Start popup animations/timers
        try:
            if TIP_WIN is not None and TIP_WIN.winfo_exists():
                # common after ids we might have set on the popup
                for attr in ("_anim_after_id", "_orbit_after", "_stars_after"):
                    aid = getattr(TIP_WIN, attr, None)
                    if aid is not None:
                        try:
                            TIP_WIN.after_cancel(aid)
                        except Exception:
                            pass
                        try:
                            setattr(TIP_WIN, attr, None)
                        except Exception:
                            pass
        except Exception:
            pass

        # cancel idle reminder timer
        try:
            t = _idle_timer[0]
            if t and hasattr(t, "cancel"):
                t.cancel()
        except Exception:
            pass

        # destroy GUI
        try:
            nova_gui.root.destroy()
        except Exception:
            pass

    finally:
        # make sure the Quick Start cross-process lock is cleared
        try:
            _release_tip_lock_safely()
        except Exception:
            pass

        # try again in case we crashed before the early removal
        try:
            _remove_pidfile()
        except Exception:
            pass

        os._exit(0)


def _begin_exit_async():
    if _EXITING.is_set():
        return
    _EXITING.set()
    try:
        import utils
        utils.begin_exit_with_goodbye_async()   # ← no timeout
    except Exception:
        _shutdown_main()

def _bind_close_button_to_exit():
    try:
        nova_gui.root.protocol("WM_DELETE_WINDOW", _begin_exit_async)
    except Exception:
        pass



# ---------------------------------------------
# GLOBAL INTENT WRAPPER (works for wake ON/OFF)
# ---------------------------------------------
import core_engine
_ORIG_PROCESS_COMMAND = core_engine.process_command

def _process_command_with_global_intents(
    cmd: str,
    *args,
    **kwargs
):
    """
    Global intent gate + centralized 'activity after completion' arming.
    Ensures the idle reminder is always scheduled AFTER a real command
    finishes (i.e., a call to core_engine.process_command).
    """
    text = (cmd or "").strip()
    if not text:
        try:
            result = _ORIG_PROCESS_COMMAND(cmd, *args, **kwargs)
        finally:
            _mark_command_activity()
        return result

    # 🔽 normalize Hinglish first when UI is Hindi
    if (utils.selected_language == "hi") and text:
        try:
            from normalizer import normalize_hinglish
            text = normalize_hinglish(text)
        except Exception:
            pass

    # --- Optional safety net: handle Yes/No/corrected name if GUI hook isn't active ---
    if _PENDING_NAME_CONFIRM.get("active"):
        # echo to chat if the GUI didn't already
        try:
            if text:
                nova_gui.show_message("YOU", text)
        except Exception:
            pass

        # try: logger.info(f"[confirm] inbound (wrapper): {text!r}")
        # except Exception: pass

        state, new_name = parse_confirmation_or_name(
            text, previous_name=_PENDING_NAME_CONFIRM.get("candidate")
        )

        if state == "confirm":
            cand = _PENDING_NAME_CONFIRM.get("candidate") or ""
            ok2, cleaned2, _reason2 = validate_name_strict(cand)
            if not ok2:
                _say_then_show(
                    "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                    key="name_invalid_post_confirm_typed"
                )
                try: nova_gui.name_capture_active = True
                except Exception: pass
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_pending_name_confirm()
                return

            _PENDING_NAME_CONFIRM["handled"] = True
            # ✅ clear the entry box only on success (if present)
            try: nova_gui.input_entry.delete(0, tk.END)
            except Exception: pass
            _accept_and_continue_with_name(cleaned2)
            return

        if state == "corrected" and new_name:
            ok3, cleaned3, _reason3 = validate_name_strict(new_name)
            if not ok3:
                _say_then_show(
                    "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                    key="name_invalid_correction"
                )
                # ❌ keep box content so the user can edit/resend
                return
            _PENDING_NAME_CONFIRM["handled"] = True
            # ✅ clear on success
            try: nova_gui.input_entry.delete(0, tk.END)
            except Exception: pass
            _accept_and_continue_with_name(cleaned3)
            return

        if state == "deny":
            try: nova_gui.name_capture_active = True
            except Exception: pass
            _say_then_show(
                "Okay — Please type your name below in the chatbox provided, e.g. Alex.",
                key="name_after_no_typed"
            )
            _PENDING_NAME_CONFIRM["handled"] = True
            _clear_pending_name_confirm()
            # ✅ optional: clear so the box is ready for typing the real name
            try: nova_gui.input_entry.delete(0, tk.END)
            except Exception: pass
            return

        # Ambiguous → ask again, stay in confirmation (do NOT clear)
        _say_then_show(
            "Please reply with Yes/No, or type your correct name (e.g. Alex).",
            key="name_confirm_clarify"
        )
        return
    # --- END optional safety net ---

    # Global: voice or typed "change language"
    if said_change_language(text):
        from utils import _speak_multilang, selected_language, listen_command, try_stop_tts_playback
        try:
            from wake_word_listener import run_change_language_flow
        except Exception:
            run_change_language_flow = None

        try:
            try_stop_tts_playback()
        except Exception:
            pass

        ok = False
        if run_change_language_flow:
            try:
                # ✅ PTT path is wake-independent; this speaks prompt AND listens
                ok = run_change_language_flow(
                    _speak_multilang,
                    listen_command,
                    selected_language or "en"
                )
            except Exception:
                ok = False

        if not ok:
            # Graceful fallback to your existing typed picker
            _run_language_picker_async()
        return

    # Global: voice "my name is …" (typed handled earlier in chatbox intercept)
    if _maybe_handle_voice_name_change(text):
        # name changes are handled elsewhere; do not arm idle timer here
        return

    # Otherwise, continue as usual but arm the idle nudge AFTER completion
    try:
        result = _ORIG_PROCESS_COMMAND(cmd, *args, **kwargs)
    finally:
        try:
            _mark_command_activity()
        except Exception:
            pass

    return result

# Monkey-patch the engine so any module calling it gets intents handled
core_engine.process_command = _process_command_with_global_intents


# -------------------------------
# Voice loop  (DISABLED: tray owns Wake; GUI owns PTT)
# -------------------------------
def voice_loop():
    """
    No background listening here.

    - When Wake Mode is ON, the tray/hotword listener owns the mic.
    - When Wake Mode is OFF, the GUI push-to-talk (_on_mic_click → _ptt_capture_once)
      handles one-shot capture.

    We keep a tiny idle loop so any old references to voice_loop() won’t crash.
    """
    import time
    while True:
        time.sleep(0.3)


# -------------------------------
# MAIN
# -------------------------------
nova_gui = None
_GREETED_ONCE = False


def _clear_entry_safe():
    """
    Clear the chat input regardless of whether it's an Entry, Text/ScrolledText,
    or bound to a StringVar. Works on/off the Tk thread and never crashes.
    """
    def _do():
        try:
            w = getattr(nova_gui, "input_entry", None)
            if not w:
                return

            cleared = False

            # Case 1: tk/ttk Entry → delete(0, END)
            try:
                import tkinter as _tk
                w.delete(0, _tk.END)
                cleared = True
            except Exception:
                pass

            # Case 2: Text/ScrolledText → delete("1.0", END)
            if not cleared:
                try:
                    import tkinter as _tk
                    w.delete("1.0", _tk.END)
                    cleared = True
                except Exception:
                    pass

            # Case 3: widget is bound to a textvariable → set("")
            try:
                tv = w.cget("textvariable")
            except Exception:
                tv = ""
            if tv:
                try:
                    var = w.nametowidget(tv)
                    var.set("")
                    cleared = True
                except Exception:
                    pass

            try:
                w.update_idletasks()
            except Exception:
                pass
        except Exception:
            pass

    try:
        import threading
        if threading.current_thread().name == "MainThread":
            _do()
        else:
            nova_gui.root.after(0, _do)
    except Exception:
        try:
            _do()
        except Exception:
            pass



if __name__ == "__main__":
    START_HIDDEN = any(arg in sys.argv for arg in ("--hidden", "--tray", "--minimized"))

    _ensure_wake_default_on()

    # --- Hydrate language BEFORE GUI import to avoid visible color flip  ---
    try:
        saved_lang = load_from_memory("language")
    except Exception:
        saved_lang = None
    try:
        if isinstance(saved_lang, str) and saved_lang.lower() in SUPPORTED_LANGS:
            utils.selected_language = saved_lang.lower()
        else:
            # Fallback to settings.json if memory is empty
            try:
                s = utils.load_settings()
                cfg_lang = (s.get("language") or "").lower()
                if cfg_lang in SUPPORTED_LANGS:
                    utils.selected_language = cfg_lang
            except Exception:
                pass
    except Exception:
        # Never block startup on hydration
        pass

    # 👇 First run on ANY OS — force English TTS until the user picks a language in onboarding.
    try:
        if not saved_lang:
            utils.enable_boot_lang_lock_if_needed("en")
    except Exception:
        pass

    # === Pre-warm Piper TTS sessions (prioritize current UI language) ===
    # (GATED so it never contends with greet/name capture)
    def _prewarm_tts_all(current_code: str | None):
        import time
        try:
            ALL = tuple(SUPPORTED_LANGS)
        except Exception:
            ALL = ("en", "hi", "de", "fr", "es")

        cur = (current_code or "en").lower()

        # Warm ONLY the current voice first — but NOT while name flow is active
        try:
            if not getattr(utils, "NAME_CAPTURE_IN_PROGRESS", False):
                utils.get_session_tts(cur)
        except Exception:
            pass

        # Then warm others (staggered), but bail immediately if name flow starts
        for code in ALL:
            if code == cur:
                continue
            if getattr(utils, "NAME_CAPTURE_IN_PROGRESS", False):
                break  # do not contend with name capture
            try:
                utils.get_session_tts(code)
                time.sleep(0.1)
            except Exception:
                pass

    def _start_tts_prewarm():
        # Run pre-warm ONLY when it won't clash with greet/name capture.
        import threading as _th, time as _time

        def _gate_and_run():
            # 1) Wait until the greet actually ran (we flip _GREETED_ONCE there)
            while not _GREETED_ONCE:
                _time.sleep(0.1)

            # 2) If the name flow is running, wait for it to finish (max ~15s)
            waited = 0
            while getattr(utils, "NAME_CAPTURE_IN_PROGRESS", False) and waited < 15000:
                _time.sleep(0.1)
                waited += 100

            # 3) If still active after 15s, skip prewarm this session
            if getattr(utils, "NAME_CAPTURE_IN_PROGRESS", False):
                return

            _prewarm_tts_all(utils.selected_language or "en")

        _th.Thread(target=_gate_and_run, daemon=True).start()

    # If truly first run (no saved name), *schedule* pre-warm,
    # but the guarded starter above will wait for greet/name to clear.
    _is_first_run = not bool(load_from_memory("name"))
    if _is_first_run:
        import threading as _th
        _th.Timer(3.0, _start_tts_prewarm).start()  # ~3s nominal start (gated inside)
    else:
        _start_tts_prewarm()
    # ====================================================================

    # 👇👇👇 CREATE & SHOW the window immediately (before tray startup)
    from gui_interface import get_gui as _get_gui
    nova_gui = _get_gui()
    _write_pidfile()
    # 👆👆👆

    # Start Windows tray in the background ONLY if it isn't already running
    if os.name == "nt":
        import socket as _sock, threading as _th

        def _tray_is_running_fast() -> bool:
            try:
                with _sock.create_connection(SINGLETON_ADDR, timeout=0.2) as c:
                    c.sendall(b"HELLO\n")
                    banner = c.recv(64).decode("utf-8", "ignore").strip()
                return banner == "NOVA_TRAY"
            except Exception:
                return False

        if not _tray_is_running_fast():
            _th.Thread(target=_ensure_tray_running, daemon=True).start()

    # Native Linux (optional tray). Never in WSL. Safe no-op if file/deps missing.
    s = load_settings()
    if sys.platform.startswith("linux") and ("WSL_DISTRO_NAME" not in os.environ) and s.get("enable_tray", True):
        try:
            from tray_linux import start_tray_in_thread
            start_tray_in_thread()
        except Exception:
            pass

    # Track when the window appears and when it stops moving/resizing
    try:
        nova_gui.root.bind("<Map>", _track_map)
        nova_gui.root.bind("<Configure>", _track_configure)
    except Exception:
        pass

    # Preferred title
    try:
        nova_gui.root.title("Nova - AI Assistant")
    except Exception:
        pass

    _bind_close_button_to_exit()

    # Determine if we already know the user (name saved)
    _has_name = bool(load_from_memory("name"))

    # --- Functions that we gate until the GUI is stable ---
    def _greet_known_user():
        global _GREETED_ONCE
        if _GREETED_ONCE:
            return
        _GREETED_ONCE = True

        # Restore language + color FIRST
        code, _ = set_language_persisted(force=False)
        try:
            nova_gui.apply_language_color(code)
        except Exception:
            pass

        # Greeting (dedup keyed)
        _bubble_localized_say_first(
            "Hello! I’m Nova, your AI assistant. I’m online and ready to help you.",
            hi="नमस्ते! मैं नोवा हूँ, आपकी ए आई सहायक। मैं ऑनलाइन हूँ और मदद के लिए तैयार हूँ।",
            de="Hallo! Ich bin Nova, deine KI-Assistentin. Ich bin online und bereit zu helfen.",
            fr="Bonjour ! Je suis Nova, votre assistante IA. Je suis en ligne et prête à aider.",
            es="¡Hola! Soy Nova, tu asistente de IA. Estoy en línea y lista para ayudar.",
            key="greet_hello",
            after_speech=lambda: _speak_ready_and_schedule_tip(
                utils.selected_language or code or "en",
                key=f"greet_help_{utils.selected_language or code or 'en'}"
            )
        )
        log_interaction("startup", "greet_ready_localized", code)

        # Post-greet follow-ups
        schedule_idle_prompt()
        _mark_first_run_complete()

        # Birthday prompt after UI is up and greeting is done
        try:
            from birthday_manager import check_and_prompt_birthday
            check_and_prompt_birthday()
        except Exception as e:
            logger.error(f"Birthday prompt failed: {e}")

    def _greet_first_run():
        """First boot: greet, then start name flow exactly after speech finishes."""
        global _GREETED_ONCE
        if _GREETED_ONCE:
            return
        _GREETED_ONCE = True

        # Pause voice loop during greet and force Wake OFF so tray shows no green dot
        utils.NAME_CAPTURE_IN_PROGRESS = True
        try:
            if get_wake_mode():
                set_wake_mode(False)
                try:
                    _sync_wake_ui_from_settings()
                except Exception:
                    pass
        except Exception:
            pass

        greet_text = "Hello! I’m Nova, your AI assistant. I’m online and ready to help you."

        def _after_greet():
            try:
                _sr_mute(1200)  # keep SR prompts quiet after the greet (500–1200 is fine)
            except Exception:
                pass

            # 🔧 Non-blocking warm of the current voice (OFF the Tk thread)
            try:
                import threading as _th
                cur = (utils.selected_language or "en")
                _th.Thread(target=lambda: utils.get_session_tts(cur), daemon=True).start()
            except Exception:
                pass

            # start name flow immediately; do not wait for the warm-up
            try:
                ask_user_name_on_boot_async()
            except Exception:
                pass

        # Speak first, then show; chain name flow after speech
        _say_then_show(greet_text, key="greet_hello", after_speech=_after_greet)

        # Log the startup greet (first boot is English)
        try:
            log_interaction("startup", greet_text, "en")
        except Exception:
            pass

    if START_HIDDEN:
        try:
            nova_gui.root.withdraw()
        except Exception:
            pass

        # Schedule the appropriate greeting once the window becomes visible & stable,
        # then wait until animation is actually running
        def _when_shown_then_greet():
            if _has_name:
                _when_gui_stable(lambda: _after_animation_ready(_greet_known_user, extra_wait_ms=0),
                                 min_visible_ms=150, quiet_ms=120)
            else:
                _when_gui_stable(lambda: _after_animation_ready(_greet_first_run, extra_wait_ms=0),
                                 min_visible_ms=150, quiet_ms=120)

        _when_gui_visible(_when_shown_then_greet, delay_ms=120)

    else:
        # Window shows immediately; gate greeting until it settles & animation ready
        if _has_name:
            _when_gui_stable(lambda: _after_animation_ready(_greet_known_user, extra_wait_ms=0),
                             min_visible_ms=150, quiet_ms=120)
        else:
            _when_gui_stable(lambda: _after_animation_ready(_greet_first_run, extra_wait_ms=0),
                             min_visible_ms=150, quiet_ms=120)

    # Sync wake UI now and once more shortly after to catch late image loads
    _sync_wake_ui_from_settings()
    try:
        nova_gui.root.after(250, _sync_wake_ui_from_settings)
    except Exception:
        pass

    _install_chatbox_name_capture_intercept()

    # CHANGED: lazy-import chemistry refresher at call site
    try:
        from handlers.chemistry_solver import _start_autorefresh_once
        _start_autorefresh_once()
    except Exception:
        pass

    # --- typed-command handler (idle arming handled by global wrapper) ---
    def _external_cmd(cmd: str) -> None:
        text = (cmd or "").strip()
        if not text:
            return

        # Are we in the name confirmation step?
        if _PENDING_NAME_CONFIRM.get("active") or getattr(nova_gui, "awaiting_name_confirmation", False):
            try:
                utils.try_stop_tts_playback()
            except Exception:
                pass

            state, new_name = parse_confirmation_or_name(
                text, previous_name=_PENDING_NAME_CONFIRM.get("candidate")
            )

            if state == "confirm":
                cand = _PENDING_NAME_CONFIRM.get("candidate") or ""
                ok2, cleaned2, _ = validate_name_strict(cand)
                if not ok2:
                    nova_gui.root.after(0, lambda: _say_then_show(
                        "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                        key="name_invalid_post_confirm_typed",
                    ))
                    try:
                        nova_gui.name_capture_active = True
                    except Exception:
                        pass
                    _PENDING_NAME_CONFIRM["handled"] = True
                    _clear_pending_name_confirm()
                    return

                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_entry_safe()  # <<< changed
                nova_gui.root.after(0, lambda: _accept_and_continue_with_name(cleaned2))
                return

            if state == "corrected" and new_name:
                ok3, cleaned3, _ = validate_name_strict(new_name)
                if not ok3:
                    nova_gui.root.after(0, lambda: _say_then_show(
                        "Please enter a valid name: letters only, 2–15 characters, e.g. Alex.",
                        key="name_invalid_correction",
                    ))
                    return
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_entry_safe()  # <<< changed
                nova_gui.root.after(0, lambda: _accept_and_continue_with_name(cleaned3))
                return

            if state == "deny":
                try:
                    nova_gui.name_capture_active = True
                except Exception:
                    pass
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_pending_name_confirm()

                _clear_entry_safe()  # ✅ clears plain "no"  <<< changed

                nova_gui.root.after(0, lambda: _say_then_show(
                    "Okay — Please type your name below in the chatbox provided, e.g. Alex.",
                    key="name_after_no_typed",
                ))
                return

            # Ambiguous → clarify
            nova_gui.root.after(0, lambda: _say_then_show(
                "Please reply with Yes/No, or type your correct name (e.g. Alex).",
                key="name_confirm_clarify",
            ))
            return

        # Normal path (not in name confirmation)
        core_engine.process_command(
            text,
            is_math_override=_gv("math_mode_var"),
            is_plot_override=_gv("plot_mode_var"),
            is_physics_override=_gv("physics_mode_var"),
            is_chemistry_override=_gv("chemistry_mode_var"),
        )

    # Hook the typed-command handler (must match the name above)
    nova_gui.external_callback = _external_cmd

    # ❌ REMOVED: background mic thread (no continuous listening anymore)
    # if not any(th.name == "voice_loop" for th in threading.enumerate()'):
    #     threading.Thread(target=voice_loop, name="voice_loop", daemon=True).start()

    # Run the Tk main loop
    nova_gui.root.mainloop()
