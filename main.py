# -*- coding: utf-8 -*-

# --- ensure local modules (utils, gui_interface, etc.) are importable ---
import os, sys, re, importlib.util
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

# 📂 main.py

from utils import (
    listen_command,
    speak,
    _speak_multilang,
    log_interaction,
    get_wake_mode,
    logger,
    selected_language,
    resource_path,
)
import utils  # load_settings/save_settings/current_build_id

import tkinter as tk
from PIL import Image, ImageTk, Image as PILImage
import math, threading, time, traceback, re, random
from langdetect import detect

from core_engine import process_command
from normalizer import normalize_hinglish
from handlers.chemistry_solver import _start_autorefresh_once
from memory_handler import save_to_memory, load_from_memory

from wake_word_listener import (
    start_wake_listener_thread,
    serve_curiosity,
    serve_followup,
)

from intents import (
    said_change_language,
    TELL_ME_TRIGGERS,
    POSITIVE_RESPONSES,
    parse_category_from_choice,
    is_followup_text,
    guess_language_code,
    SUPPORTED_LANGS,
    CURIOSITY_MENU
)

from utils import extract_name


# ---- first-run Quick Start (tray-driven with local fallback) ----
SINGLETON_ADDR = ("127.0.0.1", 50573)
APPDATA_DIR = Path(os.environ.get("APPDATA", str(_app_dir()))) / "Nova"
FIRST_TIP_SENTINEL = APPDATA_DIR / ".quick_start_shown"

_TIP_AFTER_ID = None
TIP_WIN = None


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

def _safe_show(who: str, text: str):
    """Insert into chat only if it's not identical to the immediately previous line."""
    try:
        if text.strip() == _last_chat_line[0].strip():
            return
        _last_chat_line[0] = text
        nova_gui.show_message(who, text)
    except Exception:
        pass

def _show_once(who: str, text: str, key: str | None = None, delay_ms: int = 220):
    """Schedule a bubble only once per logical key."""
    if key and key in _POSTED_KEYS:
        return
    try:
        def _do():
            if key:
                _POSTED_KEYS.add(key)
            _safe_show(who, text)
        nova_gui.root.after(delay_ms, _do)
    except Exception:
        if key:
            _POSTED_KEYS.add(key)
        _safe_show(who, text)


# -------------------------------
# Speak first, then show helpers (ONLY for setup flow as discussed)
# -------------------------------
def _say_then_show(text: str, delay_ms: int = 220, key: str | None = None):
    """Speak first, then add Nova bubble after a short delay (dedup by key)."""
    speak_async(text)
    _show_once("NOVA", text, key=key, delay_ms=delay_ms)

def _bubble_localized_say_first(
    en: str,
    hi: str | None = None,
    de: str | None = None,
    fr: str | None = None,
    es: str | None = None,
    delay_ms: int = 220,
    key: str | None = None,
):
    """
    Speak (multilang) first, then show the chosen localized line after a short delay.
    Used for greeting/ready + validation prompts in the setup flow.
    """
    lang = utils.selected_language or "en"
    lang_map = {"en": en, "hi": hi, "de": de, "fr": fr, "es": es}
    chosen = lang_map.get(lang) or en
    _speak_multilang_async(en, hi=hi, de=de, fr=fr, es=es)
    _show_once("NOVA", chosen, key=key, delay_ms=delay_ms)


# -------------------------------
# Local fallback Quick Start dialog (centered; Win11-safe)
# -------------------------------
import tkinter as tk
def show_quick_start_dialog(parent: tk.Tk | None = None):
    """
    Centered on screen, appears AFTER the main GUI is visible.
    Closes cleanly on Got it, window X, or Esc.
    """
    # reuse a single window if already open
    global _TIP_AFTER_ID, TIP_WIN
    try:
        if TIP_WIN is not None and TIP_WIN.winfo_exists():
            try:
                TIP_WIN.deiconify(); TIP_WIN.lift(); TIP_WIN.focus_force()
            except Exception:
                pass
            return
    except Exception:
        pass

    # Window
    popup = tk.Toplevel(master=parent)
    popup.withdraw()  # prevent corner flash
    TIP_WIN = popup
    popup.title("Nova • Quick Start")
    popup.configure(bg="#1a103d")
    popup.resizable(False, False)
    if parent:
        try:
            popup.transient(parent)
        except Exception:
            pass
    try:
        popup.attributes("-topmost", True)
    except Exception:
        pass

    # Size & header
    width, height = 540, 360
    header_h = 150
    popup.geometry(f"{width}x{height}")

    header = tk.Canvas(popup, width=width, height=header_h,
                       bg="#1a103d", highlightthickness=0, bd=0)
    header.pack()

    # tiny star field + glow face
    star_layers = {1: [], 2: [], 3: []}
    for layer in star_layers:
        for _ in range(12):
            x = random.randint(0, width)
            y = random.randint(0, header_h)
            size = layer  # 1..3
            star = header.create_oval(x, y, x+size, y+size, fill="#c9cfff", outline="")
            star_layers[layer].append(star)

    logo_id = None
    try:
        # use the same glow art as other tips
        from utils import pkg_path
        img = Image.open(str(pkg_path("assets", "nova_face_glow.png"))).resize((84, 84))
        logo = ImageTk.PhotoImage(img)
        logo_id = header.create_image(width//2, header_h//2, image=logo)
        popup._logo_ref = logo  # hold reference
    except Exception:
        pass

    # animate: drift stars + subtle logo orbit
    def animate():
        nonlocal logo_id
        # drift stars to the right
        for layer, stars in star_layers.items():
            dx = 0.25 * layer
            for s in stars:
                header.move(s, dx, 0)
                x0, y0, x1, y1 = header.coords(s)
                if x0 > width:
                    header.move(s, -width - (x1 - x0), 0)
        # subtle logo orbit
        if logo_id:
            r, cx, cy = 10, width//2, header_h//2
            animate.t = getattr(animate, "t", 0) + 2
            rad = math.radians(animate.t)
            header.coords(logo_id, cx + r*math.cos(rad), cy + r*math.sin(rad))
        # re-schedule and keep the id so we can cancel on close
        global _TIP_AFTER_ID
        _TIP_AFTER_ID = popup.after(50, animate)
    animate()

    # Body text (matches your first screenshot)
    body = tk.Frame(popup, bg="#1a103d")
    body.pack(padx=20, pady=(10, 10), fill="x")

    t1 = "Nova is running in the system tray."
    t2 = "Tip: If you don’t see the tray icon, click the ^ arrow near the clock.\nYou can drag it out to keep it always visible."
    tk.Label(body, text=t1, font=("Segoe UI", 11), fg="#dcdcff", bg="#1a103d",
             justify="center", wraplength=width-60).pack(pady=(6, 6))
    tk.Label(body, text=t2, font=("Segoe UI", 10), fg="#9aa0c7", bg="#1a103d",
             justify="center", wraplength=width-60).pack(pady=(0, 10))

    # --- Rectangular "Got it!" button ---
    btn_row = tk.Frame(popup, bg="#1a103d")
    btn_row.pack(pady=(8, 18))

    def _close():
        # stop animation first, then destroy
        global _TIP_AFTER_ID, TIP_WIN
        try:
            if _TIP_AFTER_ID is not None:
                try:
                    popup.after_cancel(_TIP_AFTER_ID)
                except Exception:
                    pass
                _TIP_AFTER_ID = None
        except Exception:
            pass
        # mark tip as completed ONLY when user actually closes it
        try:
            APPDATA_DIR.mkdir(parents=True, exist_ok=True)
            FIRST_TIP_SENTINEL.write_text("1", encoding="utf-8")
        except Exception:
            pass
        try:
            popup.destroy()
        finally:
            TIP_WIN = None

    base  = "#5a4fcf"
    hover = "#6a5df0"

    got_it = tk.Button(
        btn_row,
        text="Got it!",
        command=_close,
        font=("Segoe UI", 10, "bold"),
        bg=base, fg="white",
        activebackground=hover, activeforeground="white",
        relief="flat",
        padx=18, pady=8,
        cursor="hand2",
    )
    got_it.pack()
    got_it.bind("<Enter>", lambda e: got_it.config(bg=hover))
    got_it.bind("<Leave>", lambda e: got_it.config(bg=base))

    # X and Esc close the same way
    popup.protocol("WM_DELETE_WINDOW", _close)
    popup.bind("<Escape>", lambda e: _close())
    popup.bind("<Return>", lambda e: _close())

    # --- Center without flashing; then show ---
    popup.update_idletasks()
    ww, hh = popup.winfo_width(), popup.winfo_height()
    xx = (popup.winfo_screenwidth() // 2) - (ww // 2)
    yy = (popup.winfo_screenheight() // 2) - (hh // 2)
    popup.geometry(f"{ww}x{hh}+{xx}+{yy}")
    popup.deiconify()
    try:
        popup.lift()
        popup.focus_force()
        popup.after(10, lambda: popup.attributes("-topmost", False))
    except Exception:
        pass


def _signal_tray_show_tip_once():
    """
    Try to ask the tray to show the tip. If tray isn't reachable or the EXE
    isn't present, fall back to the local dialog above.
    IMPORTANT: we DO NOT write the sentinel here anymore; we only write it
    once the tip is actually closed, to avoid "marked shown but invisible".
    """
    try:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        if FIRST_TIP_SENTINEL.exists():
            return

        # 1) Try the running tray via socket
        try:
            with socket.create_connection(SINGLETON_ADDR, timeout=0.6) as c:
                c.sendall(b"TIP\n")
                # do not write sentinel here; tray will show, user will close
                return
        except Exception:
            pass

        # 2) Try to launch a tray binary near the executable
        candidates = [
            Path(sys.executable).parent / "Nova Tray.exe",
            Path(sys.executable).parent / "NovaTray.exe",
        ]
        for p in candidates:
            if p.exists():
                try:
                    CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
                    subprocess.Popen(
                        [str(p), "--show-tip"],
                        cwd=str(p.parent),
                        close_fds=True,
                        creationflags=CREATE_NO_WINDOW
                    )
                    # again, sentinel written on close in the dialog
                    return
                except Exception:
                    pass

        # 3) Fallback: show tip from main (after GUI is visible)
        try:
            parent = nova_gui.root if ("nova_gui" in globals() and getattr(nova_gui, "root", None)) else None
            if parent:
                parent.after(0, lambda: show_quick_start_dialog(parent))
            else:
                show_quick_start_dialog(None)
        except Exception:
            pass

    except Exception:
        pass


# -------------------------------
# Helper: run after GUI is visible (centered)
# -------------------------------
def _when_gui_visible(run, delay_ms: int = 200):
    """Call `run` after the main window becomes visible + an extra delay."""
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
            # last resort: just call it
            run()
    _poll()


# -------------------------------
# Run only after the window is truly visible *and stable*
# -------------------------------
_GUI_VISIBLE_AT = [0.0]        # when the window became visible (Map)
_GUI_LAST_CFG_AT = [0.0]       # timestamp of last Configure (move/resize)

def _track_map(_evt=None):
    import time as _t
    _GUI_VISIBLE_AT[0] = _t.time()

def _track_configure(_evt=None):
    import time as _t
    _GUI_LAST_CFG_AT[0] = _t.time()

def _when_gui_stable(run, min_visible_ms: int = 1200, quiet_ms: int = 900, timeout_s: int = 20):
    """
    Call `run` after:
      1) the Tk window is visible (mapped) for at least `min_visible_ms`, AND
      2) there has been no Configure event (resize/move/layout) for `quiet_ms`.
    Falls back after `timeout_s` seconds so we never get stuck.
    """
    import time as _t
    start = _t.time()

    def _poll():
        now = _t.time()
        try:
            visible = (nova_gui.root.state() == "normal") and bool(nova_gui.root.winfo_viewable())
        except Exception:
            visible = True  # best effort

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
_ANIM_READY_MAX_WAIT_MS = 3500  # hard cap so we never get stuck

def _is_animation_ready_flag() -> bool:
    """
    Prefer a single flag if GUI exposes it:
      nova_gui.animation_ready  (bool)
      nova_gui.anim_ready       (bool)
      nova_gui.is_animation_ready() / is_anim_ready() (callable)
      nova_gui.anim_started_at  (timestamp truthy when started)

    If GUI exposes multiple specific flags, we require all PRESENT ones:
      stars_anim_ready, face_anim_ready, pulse_ready, background_anim_ready
    """
    try:
        # unified booleans first
        for name in ("animation_ready", "anim_ready"):
            v = getattr(nova_gui, name, None)
            if isinstance(v, (bool, int)) and bool(v):
                return True
        # unified callables
        for name in ("is_animation_ready", "is_anim_ready"):
            v = getattr(nova_gui, name, None)
            if callable(v) and v():
                return True
        # composite: if any of these flags exist, all must be True
        composite_names = ("stars_anim_ready", "face_anim_ready", "pulse_ready", "background_anim_ready")
        present = [getattr(nova_gui, n, None) for n in composite_names if getattr(nova_gui, n, None) is not None]
        if present:
            if all(bool(x) for x in present):
                return True
            else:
                return False
        # timestamp hint
        t = getattr(nova_gui, "anim_started_at", None)
        if t:
            return True
    except Exception:
        pass
    return False

def _after_animation_ready(run, extra_wait_ms: int = 180, max_wait_ms: int = _ANIM_READY_MAX_WAIT_MS):
    """
    Calls `run` only after the GUI reports animation-ready,
    or after `max_wait_ms` as a fail-safe. Waits an extra
    `extra_wait_ms` so the first frames are visible.
    """
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
sys.excepthook = _log_excepthook

# -------------------------------
# Idle reminder (5 minutes, only when GUI is visible, only if wake is OFF)
# -------------------------------
_IDLE_SECONDS = 300
_idle_timer = [None]

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
        try:
            if _gui_is_visible() and get_wake_mode() not in ("on", "always_on"):
                _bubble_localized_say_first(
                    "Standing by. Let me know what you’d like to do next.",
                    hi="मैं तैयार हूँ। बताइए अगला काम क्या करना है।",
                    de="Ich bin bereit. Sag mir, was du als Nächstes tun möchtest.",
                    fr="Je suis prête. Dis-moi ce que tu veux faire ensuite.",
                    es="Estoy lista. Dime qué quieres hacer a continuación.",
                    key="idle_standby"
                )
        finally:
            nxt = threading.Timer(_IDLE_SECONDS, fire)
            nxt.daemon = True
            _idle_timer[0] = nxt
            nxt.start()

    first = threading.Timer(_IDLE_SECONDS, fire)
    first.daemon = True
    _idle_timer[0] = first
    first.start()

# -------------------------------
# Wrong-language warning
# -------------------------------
_LAST_LANG_WARN = [0.0]
_LANG_WARN_COOLDOWN = 6.0

def maybe_warn_wrong_language():
    now = time.time()
    if now - _LAST_LANG_WARN[0] < _LANG_WARN_COOLDOWN:
        return
    if getattr(nova_gui, "name_capture_active", False):
        return
    _bubble_localized_say_first(
        "Please speak in the selected language or say 'change language'.",
        hi="कृपया चयनित भाषा में बोलिए या कहिए 'भाषा बदलें'।",
        de="Bitte sprich in der ausgewählten Sprache oder sage 'Sprache ändern'.",
        fr="Parle dans la langue sélectionnée ou dis 'changer la langue'.",
        es="Por favor habla en el idioma seleccionado o di 'cambiar idioma'.",
        key="warn_wrong_lang"
    )
    _LAST_LANG_WARN[0] = now

# -------------------------------
# Language persistence + fuzzy picker (now async-friendly)
# -------------------------------
def _announce_language_set(code: str):
    """Speak first + show 'Language set to … You can change it anytime…' in the NEW language."""
    lines = {
        "en": ("Language set to English. You can change it anytime by saying 'change language'.", {}),
        "hi": ("भाषा हिन्दी पर सेट कर दी गई है। आप कभी भी 'भाषा बदलें' कहकर इसे बदल सकते हैं।", {"hi": "भाषा हिन्दी पर सेट कर दी गई है। आप कभी भी 'भाषा बदलें' कहकर इसे बदल सकते हैं।"}),
        "de": ("Sprache auf Deutsch eingestellt. Du kannst sie jederzeit mit 'Sprache ändern' wechseln.", {"de": "Sprache auf Deutsch eingestellt. Du kannst sie jederzeit mit 'Sprache ändern' wechseln."}),
        "fr": ("La langue est définie sur le français. Tu peux la changer à tout moment en disant « changer la langue ».", {"fr": "La langue est définie sur le français. Tu peux la changer à tout moment en disant « changer la langue »."}),
        "es": ("El idioma se ha configurado en español. Puedes cambiarlo en cualquier momento diciendo « cambiar idioma ».", {"es": "El idioma se ha configurado en español. Puedes cambiarlo en cualquier momento diciendo « cambiar idioma »."}),
    }
    text, kwargs = lines.get(code, lines["en"])
    # speak first then show (in the selected language)
    _speak_multilang_async(text, **kwargs)
    _show_once("NOVA", text, key=f"lang_set_{code}", delay_ms=220)

# --- helper to localize the list of language names in the prompt ---
def _join_with_or(words: list[str], conj: str) -> str:
    """Join words with localized Oxford-style 'or'."""
    words = [w for w in words if w]
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    if len(words) == 2:
        return f"{words[0]} {conj} {words[1]}"
    return f"{', '.join(words[:-1])}, {conj} {words[-1]}"

def _localized_language_prompt_texts() -> dict[str, str]:
    """
    Build the 'Please tell me the language...' sentence with the language
    names localized per UI language (en/hi/de/fr/es).
    """
    # Localized display names for each UI language
    NAMES = {
        "en": {"en":"English","hi":"Hindi","de":"German","fr":"French","es":"Spanish"},
        "hi": {"en":"अंग्रेज़ी","hi":"हिन्दी","de":"जर्मन","fr":"फ़्रेंच","es":"स्पैनिश"},
        "de": {"en":"Englisch","hi":"Hindi","de":"Deutsch","fr":"Französisch","es":"Spanisch"},
        "fr": {"en":"anglais","hi":"hindi","de":"allemand","fr":"français","es":"espagnol"},
        "es": {"en":"inglés","hi":"hindi","de":"alemán","fr":"francés","es":"español"},
    }
    # Localized 'or'
    OR = {"en":"or","hi":"या","de":"oder","fr":"ou","es":"o"}

    order = ["en","hi","de","fr","es"]  # consistent order
    lists = {}
    for ui in ["en","hi","de","fr","es"]:
        names = [NAMES[ui][code] for code in order]
        lists[ui] = _join_with_or(names, OR[ui])

    return {
        "en": f"Please tell me the language you'd like to use to communicate with me: {lists['en']}.",
        "hi": f"कृपया बताइए, आप मुझसे किस भाषा में बात करना चाहेंगे: {lists['hi']}?",
        "de": f"Bitte sag mir, in welcher Sprache du mit mir sprechen möchtest: {lists['de']}.",
        "fr": f"Dis-moi dans quelle langue tu veux parler avec moi : {lists['fr']}.",
        "es": f"Dime en qué idioma quieres hablar conmigo: {lists['es']}.",
    }

# --- typed language aliases (case-insensitive), incl. native spellings ---
_LANG_ALIAS = {
    "en": {"english", "eng", "en"},
    "hi": {"hindi", "हिंदी", "हिन्दी", "hin", "hi"},
    "de": {"german", "deutsch", "ger", "de"},
    "fr": {"french", "français", "francais", "fr"},
    "es": {"spanish", "español", "espanol", "esp", "es"},
}

def _alias_to_lang(txt: str) -> str | None:
    t = (txt or "").strip().casefold()
    if not t:
        return None
    for code, names in _LANG_ALIAS.items():
        for n in names:
            # accept "hindi language", "in spanish please", etc.
            if re.search(rf"\b{re.escape(n.casefold())}\b", t):
                return code
    c = guess_language_code(t)
    return c if c in SUPPORTED_LANGS else None

def pick_language_interactive_fuzzy() -> str:
    """
    Voice first: 2 attempts.
    If both fail → switch to typed fallback (do NOT default to English).
    On success (voice), also say ready line and show the tip.
    """
    texts = _localized_language_prompt_texts()
    _bubble_localized_say_first(
        texts["en"],
        hi=texts["hi"], de=texts["de"], fr=texts["fr"], es=texts["es"],
        key="lang_picker_prompt"
    )

    for _ in range(2):
        heard = listen_command()
        if not heard:
            continue
        code = guess_language_code(heard)
        if code in SUPPORTED_LANGS:
            utils.selected_language = code
            try:
                save_to_memory("language", code)
            except Exception:
                pass
            # Update UI colors on the main thread
            try:
                nova_gui.root.after(0, lambda c=code: nova_gui.apply_language_color(c))
            except Exception:
                pass

            # Announce + ready (speak first, then show) + TIP + housekeeping
            _announce_language_set(code)
            _bubble_localized_say_first(
                "How can I help you today?",
                hi="मैं आज आपकी कैसे मदद कर सकती हूँ?",
                de="Wie kann ich dir heute helfen?",
                fr="Comment puis-je t'aider aujourd'hui ?",
                es="¿Cómo puedo ayudarte hoy?",
                key="greet_help"
            )
            try:
                _signal_tray_show_tip_once()
            except Exception:
                pass
            schedule_idle_prompt()
            _mark_first_run_complete()
            return code

    # 👇 NEW: typed fallback (no defaulting to English)
    try:
        nova_gui.language_capture_active = True
    except Exception:
        pass
    _say_then_show("I couldn’t catch that. Please type your language below in the chatbox provided, e.g. English.",
                   key="lang_type_fallback")
    return ""  # caller shouldn’t rely on return when we enter typed mode

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
    """Run the blocking picker in a thread so the UI never freezes."""
    def worker():
        try:
            pick_language_interactive_fuzzy()
            schedule_idle_prompt()
        except Exception as e:
            try:
                logger.error(f"Language picker failed: {e}")
            except Exception:
                pass
    threading.Thread(target=worker, daemon=True).start()

# -------------------------------
# NAME VALIDATION
# -------------------------------
_NAME_MIN_LEN = 2
_NAME_MAX_LEN = 30
_ALLOWED_PUNCT = set([" ", "-", "'", "’"])
_NAME_BLOCKLIST = {"lol", "lmao", "wtf", "bruh", "bro", "dude", "admin", "test", "null", "undefined", "unknown"}

def _normalize_spaces(s: str) -> str:
    return " ".join((s or "").split())

def _is_letter_or_allowed(ch: str) -> bool:
    return ch.isalpha() or (ch in _ALLOWED_PUNCT)

def _looks_like_name(s: str) -> bool:
    return any(c.isalpha() for c in s)

def _tokens(s: str):
    return re.split(r"[ \-']", s)

def validate_name_strict(name_raw: str) -> tuple[bool, str, str]:
    cleaned = _normalize_spaces(name_raw or "")
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
    toks = [t.lower() for t in _tokens(cleaned) if t]
    if any(t in _NAME_BLOCKLIST for t in toks):
        return (False, "", "blocked")
    try:
        if all(ord(c) < 128 for c in cleaned):
            cleaned = " ".join(p.capitalize() for p in cleaned.split(" "))
    except Exception:
        pass
    return (True, cleaned, "")

# -------------------------------
# Quick Start dialog (owned by main)
# -------------------------------
# (handled above as a real implementation)

def _mark_first_run_complete():
    try:
        s = utils.load_settings()
        s["first_run"] = False
        s["show_quick_start_on_first_run"] = False
        utils.save_settings(s)
    except Exception:
        pass

# -------------------------------
# Name ask on first boot (voice → typed fallback)
# -------------------------------
def ask_user_name_on_boot_async():
    if load_from_memory("name"):
        return
    def worker():
        _say_then_show("May I know your name?", key="ask_name")
        for _ in range(2):
            spoken = listen_command()
            if not spoken:
                continue
            match = extract_name(spoken)
            if match:
                ok, cleaned, _reason = validate_name_strict(match)
                if not ok:
                    _say_then_show("Please enter a valid name: letters only, 2–30 characters, e.g. Alex.",
                                   key="name_invalid")
                    continue
                save_to_memory("name", cleaned)
                example_names = {"en": "Alex", "hi": "Ajay", "fr": "Alexandre", "es": "Alejandro", "de": "Alexander"}
                ex = example_names.get(utils.selected_language or "en", "Alex")
                line = f"Nice to meet you, {cleaned}! You can later change your name if you'd like by saying something like ‘My name is {ex}’."
                _say_then_show(line, key="name_ok")
                _run_language_picker_async()
                _mark_first_run_complete()
                return
        try: nova_gui.language_capture_active = True
        except Exception: pass
        msg = "I couldn’t catch your name. Please type your name below in the chatbox provided, e.g. Alex."
        _say_then_show(msg, key="name_type_fallback")
    threading.Thread(target=worker, daemon=True).start()

def _run_language_picker():
    # kept for compatibility (used nowhere on the UI thread now)
    _run_language_picker_async()

# -------------------------------
# Name & Language capture via chatbox + typed intents
# -------------------------------
_awaiting_curiosity_choice = False

def _install_chatbox_name_capture_intercept():
    """
    Intercept Send/Enter while we're waiting for a typed name or language.
    Also catch typed “change language” requests.
    """
    if not hasattr(nova_gui, "_on_send"):
        return

    original = nova_gui._on_send

    def _patched_on_send():
        try:
            text = nova_gui.input_entry.get().strip()
        except Exception:
            text = ""

        # 0) typed "change language" (clear the box immediately)
        if text and said_change_language(text):
            try:
                nova_gui.show_message("YOU", text)
            except Exception:
                pass
            try:
                nova_gui.input_entry.delete(0, tk.END)
            except Exception:
                pass
            _run_language_picker_async()
            schedule_idle_prompt()
            return

        # 1) Language capture via typed text (mirrors Name flow)
        if getattr(nova_gui, "language_capture_active", False):
            code = _alias_to_lang(text)
            if not code:
                _say_then_show("Please type a valid language from: English, Hindi, German, French, or Spanish.",
                               key="lang_type_prompt_again")
                return
            # valid language -> save, apply UI tint, clear entry
            try:
                save_to_memory("language", code)
            except Exception:
                pass
            utils.selected_language = code
            try:
                nova_gui.root.after(0, lambda c=code: nova_gui.apply_language_color(c))
            except Exception:
                pass
            try:
                nova_gui.input_entry.delete(0, tk.END)
            except Exception:
                pass
            try:
                nova_gui.language_capture_active = False
            except Exception:
                pass

            # Announce + ready (speak first, then show)
            _announce_language_set(code)
            _bubble_localized_say_first(
                "How can I help you today?",
                hi="मैं आज आपकी कैसे मदद कर सकती हूँ?",
                de="Wie kann ich dir heute helfen?",
                fr="Comment puis-je t'aider aujourd'hui ?",
                es="¿Cómo puedo ayudarte hoy?",
                key="greet_help"
            )

            # Tip only after ready line
            try:
                _signal_tray_show_tip_once()
            except Exception:
                pass

            schedule_idle_prompt()
            _mark_first_run_complete()
            return

        # 2) Name capture via typed text
        if getattr(nova_gui, "name_capture_active", False):
            ok, cleaned, _reason = validate_name_strict(text)
            if not ok:
                _say_then_show("Please enter a valid name: letters only, 2–30 characters, e.g. Alex.",
                               key="name_invalid_again")
                return
            try:
                save_to_memory("name", cleaned)
            except Exception:
                pass
            try:
                nova_gui.name_capture_active = False
            except Exception:
                pass
            try:
                nova_gui.input_entry.delete(0, tk.END)  # clear only on success
            except Exception:
                pass
            example_names = {"en": "Alex", "hi": "Ajay", "fr": "Alexandre", "es": "Alejandro", "de": "Alexander"}
            ex = example_names.get(utils.selected_language or "en", "Alex")
            line = f"Nice to meet you, {cleaned}! You can later change your name by saying ‘My name is {ex}’."
            _say_then_show(line, key="name_ok_2")
            _run_language_picker_async()
            _mark_first_run_complete()
            schedule_idle_prompt()
            return

        # 3) normal path
        return original()

    # swap in & refresh bindings
    nova_gui._on_send = _patched_on_send
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
            s["wake_mode"] = "on"
            utils.save_settings(s)
    except Exception as e:
        try: logger.warning(f"Could not set default wake_mode=on: {e}")
        except Exception: pass

def _sync_wake_ui_from_settings():
    try:
        is_on = get_wake_mode() in ("on", "always_on")
        label = f"Wake Mode: {'ON' if is_on else 'OFF'}"
        if getattr(nova_gui, "wake_mode_var", None):
            try: nova_gui.wake_mode_var.set(is_on)
            except Exception: pass
        for attr in ("wake_toggle_btn", "wake_button", "wake_label"):
            btn = getattr(nova_gui, attr, None)
            if btn:
                try: btn.config(text=label)
                except Exception: pass
        try:
            if hasattr(nova_gui, "update_mic_icon"):
                nova_gui.update_mic_icon(is_on)
        except Exception:
            pass
    except Exception:
        pass

# -------------------------------
# Unified EXIT handler
# -------------------------------
def _shutdown_main():
    global _TIP_AFTER_ID
    try:
        try:
            if _TIP_AFTER_ID is not None:
                nova_gui.root.after_cancel(_TIP_AFTER_ID)
        except Exception:
            pass
        try:
            t = _idle_timer[0]
            if t and hasattr(t, "cancel"):
                t.cancel()
        except Exception:
            pass
        try:
            nova_gui.root.destroy()
        except Exception:
            pass
    finally:
        os._exit(0)

def _bind_close_button_to_exit():
    try:
        nova_gui.root.protocol("WM_DELETE_WINDOW", _shutdown_main)
    except Exception:
        pass

# -------------------------------
# MAIN
# -------------------------------
def _wake_is_active() -> bool:
    try:
        return get_wake_mode() in ("on", "always_on")
    except Exception:
        return False

nova_gui = None
_GREETED_ONCE = False

if __name__ == "__main__":
    START_HIDDEN = any(arg in sys.argv for arg in ("--hidden", "--tray", "--minimized"))

    _ensure_wake_default_on()

    # --- Hydrate language BEFORE GUI import to avoid visible color flip ---
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

    # Import GUI after defaulting wake mode & hydrating language
    from gui_interface import nova_gui as _nova_gui_instance
    nova_gui = _nova_gui_instance

    # Track when the window appears and when it stops moving/resizing
    try:
        nova_gui.root.bind("<Map>", _track_map)
        nova_gui.root.bind("<Configure>", _track_configure)
    except Exception:
        pass

    # Preferred title
    try:
        nova_gui.root.title("NOVA - AI Assistant")
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
            key="greet_hello"
        )
        log_interaction("startup", "greet_ready_localized", code)

        _bubble_localized_say_first(
            "How can I help you today?",
            hi="मैं आज आपकी कैसे मदद कर सकती हूँ?",
            de="Wie kann ich dir heute helfen?",
            fr="Comment puis-je t'aider aujourd'hui ?",
            es="¿Cómo puedo ayudarte hoy?",
            key="greet_help"
        )

        # Post-greet follow-ups
        schedule_idle_prompt()
        _mark_first_run_complete()

        # Tip only AFTER ready line
        try:
            _signal_tray_show_tip_once()
        except Exception:
            pass

        # Birthday prompts after UI is up and greeting is done
        try:
            from birthday_manager import check_and_prompt_birthday
            check_and_prompt_birthday()
        except Exception as e:
            logger.error(f"Birthday prompt failed: {e}")

    def _greet_first_run():
        global _GREETED_ONCE
        if _GREETED_ONCE:
            return
        _GREETED_ONCE = True

        greet_text = "Hello! I’m Nova, your AI assistant. I’m online and ready to help you."
        _say_then_show(greet_text, key="greet_hello")
        log_interaction("startup", greet_text, "en")

        # Start the name flow a moment after the greeting
        try:
            nova_gui.root.after(800, ask_user_name_on_boot_async)
        except Exception:
            ask_user_name_on_boot_async()

        # NOTE: TIP is NOT triggered here anymore.
        # It will be triggered only after the ready line (post language set).

    if START_HIDDEN:
        try: nova_gui.root.withdraw()
        except Exception: pass

        # Schedule the appropriate greeting once the window becomes visible & stable,
        # then wait until animation is actually running
        def _when_shown_then_greet():
            if _has_name:
                _when_gui_stable(lambda: _after_animation_ready(_greet_known_user),
                                 min_visible_ms=1200, quiet_ms=900)
            else:
                _when_gui_stable(lambda: _after_animation_ready(_greet_first_run),
                                 min_visible_ms=1200, quiet_ms=900)

        _when_gui_visible(_when_shown_then_greet, delay_ms=200)

    else:
        # Window shows immediately; gate greeting until it settles & animation ready
        if _has_name:
            _when_gui_stable(lambda: _after_animation_ready(_greet_known_user),
                             min_visible_ms=1200, quiet_ms=900)
        else:
            _when_gui_stable(lambda: _after_animation_ready(_greet_first_run),
                             min_visible_ms=1200, quiet_ms=900)

    # Sync wake UI now and once more shortly after to catch late image loads
    _sync_wake_ui_from_settings()
    try:
        nova_gui.root.after(250, _sync_wake_ui_from_settings)
    except Exception:
        pass

    # (Birthday call moved into _greet_known_user so it never races early)

    _install_chatbox_name_capture_intercept()

    _start_autorefresh_once()

    nova_gui.external_callback = lambda cmd: process_command(
        cmd,
        is_math_override=nova_gui.math_mode_var.get(),
        is_plot_override=nova_gui.plot_mode_var.get(),
        is_physics_override=getattr(nova_gui, "physics_mode_var", None) and nova_gui.physics_mode_var.get(),
        is_chemistry_override=getattr(nova_gui, "chemistry_mode_var", None) and nova_gui.chemistry_mode_var.get()
    )

    try:
        start_wake_listener_thread()
    except Exception as e:
        logger.error(f"Could not start wake listener: {e}")

    def voice_loop():
        while True:
            # when wake is active, the wake-word listener handles speech;
            # this loop sleeps to avoid double-capturing audio
            if _wake_is_active():
                time.sleep(0.3)
                continue
            command = listen_command()
            if not command:
                continue

            # Voice “change language” (also non-blocking)
            if said_change_language(command):
                _run_language_picker_async()
                schedule_idle_prompt()
                continue

            if utils.selected_language == "hi":
                command = normalize_hinglish(command)
            try:
                detected_lang = detect(command)
            except Exception:
                detected_lang = "unknown"
            lang_map = {"en": "en", "hi": "hi", "de": "de", "fr": "fr", "es": "es"}
            supported = set(lang_map.values())
            if detected_lang in supported and detected_lang != lang_map.get(utils.selected_language, "en"):
                maybe_warn_wrong_language()
                continue
            process_command(command)
            schedule_idle_prompt()

    threading.Thread(target=voice_loop, daemon=True).start()

    nova_gui.root.mainloop()
