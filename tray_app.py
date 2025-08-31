# tray_app.py
# -*- coding: utf-8 -*-

import os, sys, time, socket, threading, math
from pathlib import Path
import json
from datetime import datetime, timedelta

# ---------- Optional GUI bits for popups ----------
import tkinter as tk
from tkinter import font as tkfont  # for precise text height (kept for future use)
from PIL import ImageTk, Image as PILImage

# ---------- pystray ----------
try:
    from pystray import Icon, Menu, MenuItem
except Exception:
    Icon = None
    Menu = None
    MenuItem = None

# ---------- Cross-platform backend ----------
from platform_adapter import get_backend
_backend = get_backend()

# ---------- Wake toggle plumbing (safe fallbacks if modules missing) ----------
try:
    from utils import get_wake_mode, set_wake_mode
except Exception:
    def get_wake_mode() -> bool: return False
    def set_wake_mode(_v: bool) -> None: pass

try:
    from wake_word_listener import start_wake_listener_thread, stop_wake_listener_thread
except Exception:
    def start_wake_listener_thread(): pass
    def stop_wake_listener_thread(): pass

# Paths (robust in frozen + dev)
IS_FROZEN = getattr(sys, "frozen", False)
EXE_DIR = Path(sys.executable).parent if IS_FROZEN else Path(__file__).parent.resolve()
APP_DIR = Path(getattr(sys, "_MEIPASS", EXE_DIR)).resolve()
HERE = EXE_DIR

# Single-instance TCP port (loopback only)
SINGLETON_PORT = 50573
SINGLETON_ADDR = ("127.0.0.1", SINGLETON_PORT)

# AppData + sentinels (cross-platform)
APPDATA_DIR = _backend.user_data_dir()
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

FIRST_TIP_SENTINEL = APPDATA_DIR / ".quick_start_shown"
TIP_LOCK_PATH      = APPDATA_DIR / ".quick_start_open"

# ✅ Intentional-exit sentinel (prevents auto-relaunch for a short cooldown)
WATCHDOG_SENTINEL = APPDATA_DIR / ".user_exited_nova"
USER_EXIT_COOLDOWN_SEC = 30  # default; can be overridden in settings.json

# Tk globals
_root: tk.Tk | None = None
_tray_tip_win = [None]  # keep reference
_exit_win = [None]      # single-instance "Exit Tray" confirmation

# ===============================
# NEW: Wake state helpers + watcher
# ===============================
_last_wake_state = None

def _wake_is_on() -> bool:
    """Use pure booleans; utils already auto-migrates."""
    try:
        return bool(get_wake_mode())
    except Exception:
        return False

def _set_wake_on(on: bool):
    """Persist as a boolean."""
    try:
        set_wake_mode(bool(on))
    except Exception:
        pass

def _wake_label() -> str:
    # label first, indicator after (iPhone-style: green when on, grey/white when off)
    return f"Wake Mode   {'🟢 ON' if _wake_is_on() else '⚪ OFF'}"

def _toggle_wake(icon=None):
    """Toggle saved wake flag and start/stop the listener. Refresh menu label."""
    try:
        new_state = not _wake_is_on()
        _set_wake_on(new_state)
        if new_state:
            start_wake_listener_thread()
        else:
            stop_wake_listener_thread()
    except Exception:
        pass
    # rebuild menu so label updates immediately
    if icon is not None:
        try:
            icon.menu = _build_menu(icon)
            icon.update_menu()
        except Exception:
            pass

def _watch_wake_setting(icon):
    """Poll the saved setting to keep the mic + menu in sync with GUI/voice flips."""
    global _last_wake_state
    while True:
        try:
            cur = _wake_is_on()
            if cur != _last_wake_state:
                if cur:
                    start_wake_listener_thread()
                else:
                    stop_wake_listener_thread()
                _last_wake_state = cur
                try:
                    icon.menu = _build_menu(icon)
                    icon.update_menu()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)  # snappier sync

# -------------------------------
# Utilities
# -------------------------------
def resource_path(name: str) -> str:
    for base in [EXE_DIR, APP_DIR, EXE_DIR / "assets", APP_DIR / "assets"]:
        p = Path(base) / name
        if p.exists():
            return str(p)
    return name

def _ensure_dirs():
    try:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def _tk_after(fn, *args, delay_ms: int = 0, **kwargs):
    """Run on the Tk thread if _root exists; else run inline."""
    global _root
    if _root and _root.winfo_exists():
        _root.after(delay_ms, lambda: fn(*args, **kwargs))
    else:
        try:
            fn(*args, **kwargs)
        except Exception:
            pass

# -------------------------------
# Watchdog settings + sentinel helpers
# -------------------------------
def _load_settings_dict():
    """Load settings.json (works in dev & frozen). Defaults if missing."""
    try:
        path = Path(resource_path("settings.json"))
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}

def _cfg_auto_restart() -> bool:
    d = _load_settings_dict()
    v = str(d.get("auto_restart_on_crash", True)).strip().lower()
    return v in ("1", "true", "yes", "on")

def _cfg_backoff_cap_sec() -> int:
    d = _load_settings_dict()
    try:
        return int(d.get("auto_restart_backoff_max_sec", 60))
    except Exception:
        return 60

def _cfg_user_exit_cooldown_sec() -> int:
    d = _load_settings_dict()
    try:
        # default 30s to match current behavior
        return int(d.get("auto_restart_user_exit_cooldown_sec", USER_EXIT_COOLDOWN_SEC))
    except Exception:
        return USER_EXIT_COOLDOWN_SEC

def _mark_user_exit():
    """Mark that the user intentionally exited Nova just now."""
    try:
        _ensure_dirs()
        WATCHDOG_SENTINEL.write_text(str(int(time.time())), encoding="utf-8")
    except Exception:
        pass

def _user_exit_cooldown_active() -> bool:
    """Return True if we should NOT auto-relaunch yet (respect user’s exit)."""
    try:
        if not WATCHDOG_SENTINEL.exists():
            return False
        ts = WATCHDOG_SENTINEL.read_text(encoding="utf-8").strip()
        t0 = datetime.fromtimestamp(int(ts))
        cooldown = max(0, _cfg_user_exit_cooldown_sec())
        return (datetime.now() - t0) < timedelta(seconds=cooldown)
    except Exception:
        return False

# -------------------------------
# First-run tip helpers
# -------------------------------
def _maybe_show_quick_start_once():
    # NOTE: We no longer write the sentinel here; it's written on close.
    _ensure_dirs()
    try:
        if FIRST_TIP_SENTINEL.exists():
            return
        _tk_after(show_quick_start, delay_ms=300)
    except Exception:
        pass

# -------------------------------
# Tk bits (hidden root)
# -------------------------------
def _init_tk():
    global _root
    _root = tk.Tk()
    _root.withdraw()
    try:
        _root.iconbitmap(resource_path("nova_icon_big.ico"))
    except Exception:
        pass
    return _root

def _focus_existing(win):
    try:
        win.deiconify()
        win.lift()
        win.focus_force()
    except Exception:
        pass

# -------------------------------
# Tip popup (now full-window starfield; no flash + safe close)
# -------------------------------
def show_quick_start(*, write_sentinel: bool = True):
    """
    Show the Quick Start tip window centered.
    write_sentinel=True (default): closing writes the first-run sentinel.
    Use write_sentinel=False for manual Help→Tray Tip so it never blocks first-boot auto.
    """
    global _tray_tip_win

    # If any process already has a tip open, don't open another — but DO focus ours if we own it.
    try:
        _ensure_dirs()
        if TIP_LOCK_PATH.exists():
            # If this process owns a tip window, bring it to front.
            try:
                w = _tray_tip_win[0]
                if w is not None and w.winfo_exists():
                    _focus_existing(w)
            except Exception:
                pass
            return
    except Exception:
        pass

    try:
        w = _tray_tip_win[0]
        if w is not None and w.winfo_exists():
            _focus_existing(w)
            return
    except Exception:
        pass

    try:
        popup = tk.Toplevel(master=_root)
        popup.withdraw()  # prevent corner flash
        _tray_tip_win[0] = popup
        popup.title("Nova • Quick Start")
        popup.geometry("420x300")
        popup.configure(bg="#1a103d")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        try:
            popup.iconbitmap(resource_path("nova_icon_big.ico"))
        except Exception:
            pass

        # mark "tip is open" right after creating the window
        try:
            _ensure_dirs()
            TIP_LOCK_PATH.write_text("1", encoding="utf-8")
        except Exception:
            pass

        _closing = [False]; _orbit_after = [None]; _stars_after = [None]

        def _safe_after(ms, fn):
            if _closing[0] or not popup.winfo_exists():
                return None
            return popup.after(ms, fn)

        def _cancel_afters():
            for aid in (_orbit_after[0], _stars_after[0]):
                if aid:
                    try: popup.after_cancel(aid)
                    except Exception: pass

        def _on_close():
            _closing[0] = True
            _cancel_afters()

            # remove the "tip open" lock
            try:
                if TIP_LOCK_PATH.exists():
                    TIP_LOCK_PATH.unlink()
            except Exception:
                pass

            # write the first-run sentinel only when appropriate
            try:
                _ensure_dirs()
                if write_sentinel and not FIRST_TIP_SENTINEL.exists():
                    FIRST_TIP_SENTINEL.write_text("1", encoding="utf-8")
            except Exception:
                pass

            try:
                popup.destroy()
            finally:
                _tray_tip_win[0] = None

        popup.protocol("WM_DELETE_WINDOW", _on_close)
        popup.bind("<Escape>", lambda e: _on_close())

        # === FULL-WINDOW starfield canvas ===
        WIDTH, HEIGHT = 420, 300
        canvas = tk.Canvas(popup, width=WIDTH, height=HEIGHT,
                           bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        star_layers = {1: [], 2: [], 3: []}
        for layer in star_layers:
            count = 22 if layer == 1 else 14
            for _ in range(count):
                x = __import__("random").randint(0, WIDTH)
                y = __import__("random").randint(0, HEIGHT)
                size = layer
                star = canvas.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
                star_layers[layer].append(star)

        # rotating/orbiting logo near the top center
        try:
            img_path = resource_path("nova_face_glow.png")
            if not Path(img_path).exists():
                img_path = resource_path("assets/nova_face_glow.png")
            img = PILImage.open(img_path).resize((80, 80))
            logo = ImageTk.PhotoImage(img)
            logo_id = canvas.create_image(WIDTH // 2, 84, image=logo)
            popup._logo_ref = logo
            angle = 0; radius = 10; cx, cy = WIDTH // 2, 84
            def rotate_logo():
                nonlocal angle
                if _closing[0] or not popup.winfo_exists():
                    return
                angle += 2
                rad = math.radians(angle)
                x = cx + radius * math.cos(rad)
                y = cy + radius * math.sin(rad)
                canvas.coords(logo_id, x, y)
                _orbit_after[0] = _safe_after(50, rotate_logo)
            _orbit_after[0] = _safe_after(50, rotate_logo)
        except Exception:
            pass

        def animate_stars():
            if _closing[0] or not popup.winfo_exists():
                return
            for layer, stars in star_layers.items():
                dx = 0.2 * layer
                for star in stars:
                    canvas.move(star, dx, 0)
                    coords = canvas.coords(star)
                    if coords and coords[0] > WIDTH:
                        canvas.move(star, -WIDTH, 0)
            _stars_after[0] = _safe_after(50, animate_stars)
        _stars_after[0] = _safe_after(50, animate_stars)

        canvas.create_text(WIDTH // 2, 156,
                           text="Nova is running in the system tray.",
                           font=("Segoe UI", 11), fill="#dcdcff",
                           width=WIDTH - 60, justify="center")
        canvas.create_text(WIDTH // 2, 198,
                           text=("Tip: If you don’t see the tray icon, click the ^ arrow near the clock.\n"
                                 "You can drag it out to keep it always visible."),
                           font=("Segoe UI", 10), fill="#9aa0c7",
                           width=WIDTH - 60, justify="center")

        base, hover = "#5a4fcf", "#9b95ff"
        got_it = tk.Button(popup, text="Got it!", command=_on_close,
                           font=("Segoe UI", 10, "bold"),
                           bg=base, fg="white",
                           activebackground=hover, activeforeground="white",
                           relief="flat", bd=0, highlightthickness=0,
                           padx=16, pady=8, cursor="hand2")
        got_it.bind("<Enter>", lambda e: got_it.config(bg=hover))
        got_it.bind("<Leave>", lambda e: got_it.config(bg=base))
        canvas.create_window(WIDTH // 2, HEIGHT - 36, window=got_it)

        popup.bind("<Return>", lambda e: _on_close())

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
        try:
            if TIP_LOCK_PATH.exists():
                TIP_LOCK_PATH.unlink()
        except Exception:
            pass

# -------------------------------
# Exit Tray confirmation (now full-window starfield)
# -------------------------------
def confirm_exit_tray() -> bool:
    """Exit Tray confirmation with full-window starfield + centered canvas-buttons."""
    import tkinter.font as tkfont  # local import to be safe

    # If dialog already open, focus and reuse it
    try:
        w0 = _exit_win[0]
        if w0 is not None and w0.winfo_exists():
            try:
                w0.deiconify(); w0.lift(); w0.focus_force()
            except Exception:
                pass
            w0.wait_window()
            return bool(getattr(w0, "_exit_ok", False))
    except Exception:
        pass

    class PaintButton(tk.Canvas):
        def __init__(self, parent, text, base, hover, command,
                     font=("Segoe UI", 10, "bold"),
                     width=None, pad_x=14, pad_y=8,
                     extra_top=1, extra_bottom=2):
            self._font = tkfont.Font(font=font)
            self._text = text
            self._base = base
            self._hover = hover
            self._command = command

            # --- robust font metrics (works across DPI/scaling) ---
            asc  = int(self._font.metrics("ascent"))
            desc = int(self._font.metrics("descent"))
            line = int(self._font.metrics("linespace"))
            internal_leading = max(0, line - (asc + desc))
            auto_bias = internal_leading // 2  # ✅ platform-consistent nudge

            # Measure width with actual font
            tw = int(self._font.measure(text))
            W = max(int(width or 0), tw + pad_x * 2)
            H = int(line + pad_y * 2 + extra_top + extra_bottom)  # use linespace

            super().__init__(parent, width=W, height=H,
                             bg=parent["bg"], highlightthickness=0, bd=0)
            self._rect = self.create_rectangle(0, 0, W, H, outline="", fill=base)

            # Anchor at TOP; apply auto bias once (no per-user tuning)
            top_y = extra_top + pad_y + auto_bias
            self._label = self.create_text(W // 2, top_y, text=text,
                                           fill="white", font=self._font, anchor="n")

            self.bind("<Enter>", lambda e: self.itemconfigure(self._rect, fill=self._hover))
            self.bind("<Leave>", lambda e: self.itemconfigure(self._rect, fill=self._base))
            self.bind("<Button-1>", lambda e: self._command())

    try:
        w = tk.Toplevel(master=_root)
        _exit_win[0] = w
        w.withdraw()
        w.title("Exit Tray?")
        w.geometry("420x300")
        w.configure(bg="#1a103d")
        w.resizable(False, False)
        w.attributes("-topmost", True)
        try: w.iconbitmap(resource_path("nova_icon_big.ico"))
        except Exception: pass
        try: w.grab_set()
        except Exception: pass

        _closing = [False]; _orbit_after = [None]; _stars_after = [None]
        def _safe_after(ms, fn):
            if _closing[0] or not w.winfo_exists(): return None
            return w.after(ms, fn)
        def _cancel_afters():
            for aid in (_orbit_after[0], _stars_after[0]):
                if aid:
                    try: w.after_cancel(aid)
                    except Exception: pass

        # === FULL-WINDOW starfield canvas ===
        WIDTH, HEIGHT = 420, 300
        canvas = tk.Canvas(w, width=WIDTH, height=HEIGHT, bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        star_layers = {1: [], 2: [], 3: []}
        import random
        for layer in star_layers:
            count = 22 if layer == 1 else 14
            for _ in range(count):
                x = random.randint(0, WIDTH); y = random.randint(0, HEIGHT)
                size = layer
                star = canvas.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
                star_layers[layer].append(star)

        # orbiting logo near the top center (slightly higher)
        try:
            img_path = resource_path("nova_face_glow.png")
            if not Path(img_path).exists():
                img_path = resource_path("assets/nova_face_glow.png")
            _img = PILImage.open(img_path).resize((80, 80))
            _logo = ImageTk.PhotoImage(_img)
            logo_id = canvas.create_image(WIDTH // 2, 72, image=_logo)
            w._logo_ref = _logo
            angle = 0; radius = 10; cx, cy = WIDTH // 2, 72
            def _orbit():
                nonlocal angle
                if _closing[0] or not w.winfo_exists(): return
                angle += 2
                import math
                rad = math.radians(angle)
                x = cx + radius * math.cos(rad); y = cy + radius * math.sin(rad)
                canvas.coords(logo_id, x, y)
                _orbit_after[0] = _safe_after(50, _orbit)
            _orbit_after[0] = _safe_after(50, _orbit)
        except Exception:
            pass

        def animate_stars():
            if _closing[0] or not w.winfo_exists(): return
            for layer, stars in star_layers.items():
                dx = 0.2 * layer
                for star in stars:
                    canvas.move(star, dx, 0)
                    if (coords := canvas.coords(star)) and coords[0] > WIDTH:
                        canvas.move(star, -WIDTH, 0)
            _stars_after[0] = _safe_after(50, animate_stars)
        _stars_after[0] = _safe_after(50, animate_stars)

        # body text split into two lines (so we can offset only the first)
        canvas.create_text(
            WIDTH // 2, 160,
            text="Are you sure you want to exit the tray?",
            font=("Segoe UI", 11),
            fill="#dcdcff",
            justify="center",
            width=WIDTH - 60,
        )
        canvas.create_text(
            WIDTH // 2, 196,
            text="Nova will stop running until you start it again from the Start Menu (Nova Tray).",
            font=("Segoe UI", 11),
            fill="#dcdcff",
            justify="center",
            width=WIDTH - 60,
        )

        result = {"ok": False}
        def _finish(ok):
            _closing[0] = True
            _cancel_afters()
            result["ok"] = ok
            try:
                w._exit_ok = ok
            except Exception:
                pass
            try:
                w.destroy()
            finally:
                _exit_win[0] = None

        # buttons (same style), centered on a row; moved UP a touch
        row = tk.Frame(w, bg="#1a103d")
        btn_font = ("Segoe UI", 10, "bold")
        f = tkfont.Font(font=btn_font)
        fixed_w = max(f.measure("Exit Tray"), f.measure("Cancel")) + 14 * 2

        exit_base, exit_hover = "#b84b5f", "#e07b8d"
        can_base,  can_hover  = "#5a4fcf", "#9b95ff"  # brighter hover

        btn_exit = PaintButton(row, "Exit Tray", exit_base, exit_hover,
                               command=lambda: _finish(True),
                               font=btn_font, width=fixed_w, pad_x=12, pad_y=6,
                               extra_top=1, extra_bottom=2)
        btn_cancel = PaintButton(row, "Cancel", can_base, can_hover,
                                 command=lambda: _finish(False),
                                 font=btn_font, width=fixed_w, pad_x=12, pad_y=6,
                                 extra_top=1, extra_bottom=2)
        btn_exit.pack(side="left", padx=(0, 10))
        btn_cancel.pack(side="left", padx=(10, 0))

        # place the row slightly higher than before
        canvas.create_window(WIDTH // 2, HEIGHT - 56, window=row)

        w.bind("<Escape>", lambda e: _finish(False))
        w.bind("<Return>", lambda e: _finish(False))

        w.update_idletasks()
        ww, hh = w.winfo_width(), w.winfo_height()
        xx = (w.winfo_screenwidth() // 2) - (ww // 2)
        yy = (w.winfo_screenheight() // 2) - (hh // 2)
        w.geometry(f"{ww}x{hh}+{xx}+{yy}")
        w.deiconify()
        try:
            w.lift(); w.focus_force()
            w.after(10, lambda: w.attributes("-topmost", False))
        except Exception:
            pass

        w.wait_window()
        return bool(result["ok"])
    except Exception:
        try:
            from tkinter import messagebox
            return bool(messagebox.askyesno("Exit Tray?", "Exit the tray and stop Nova until next launch?"))
        except Exception:
            return True

# -------------------------------
# pystray icon + menu
# -------------------------------
def _load_tray_image():
    for name in ("nova_icon_big.ico", "assets/nova_icon_big.ico",
                 "nova_icon.ico", "assets/nova_icon.ico",
                 "assets/nova_icon.png", "nova_icon.png"):
        path = resource_path(name)
        try:
            img = PILImage.open(path)
            try:
                img = img.copy().resize((32, 32), PILImage.LANCZOS)
            except Exception:
                pass
            return img
        except Exception:
            continue
    return PILImage.new("RGBA", (32, 32), (90, 79, 207, 255))

def _build_menu(icon):
    """Menu with Wake Mode as item #4 (dynamic ON/OFF label, label first)."""
    if Menu is None or MenuItem is None:
        return None

    # Callbacks in the same scope so they still exist after rebuilds
    def on_open(_icon=None, _item=None): open_nova_and_focus()
    def on_hide(_icon=None, _item=None): hide_nova()
    def on_exit_nova(_icon=None, _item=None): exit_nova()
    def on_quick_start(_icon=None, _item=None): _tk_after(show_quick_start, write_sentinel=False)
    def on_exit_tray_cb(_icon=None, _item=None):
        # stop mic before quitting tray
        try: stop_wake_listener_thread()
        except Exception: pass
        # ask user with the nice dialog
        evt = threading.Event(); result = {"ok": False}
        def _ask():
            try: result["ok"] = confirm_exit_tray()
            except Exception: result["ok"] = True
            evt.set()
        _tk_after(_ask)
        evt.wait()
        if result["ok"]:
            try: icon.visible = False; icon.stop()
            except Exception: pass
            try:
                if _root: _root.quit()
            except Exception: pass
            try:
                if TIP_LOCK_PATH.exists(): TIP_LOCK_PATH.unlink()
            except Exception: pass
            os._exit(0)

    help_menu = Menu(MenuItem("Tray Tip", on_quick_start))

    # Order:
    # 1 Open Nova, 2 Hide Nova, 3 Exit Nova, 4 Wake Mode, 5 Help, 6 Advanced
    return Menu(
        MenuItem("Open Nova", on_open),
        MenuItem("Hide Nova", on_hide),
        MenuItem("Exit Nova", on_exit_nova),
        # 4 — label first, then the ON/OFF indicator
        MenuItem(_wake_label(), lambda _i, _it: _toggle_wake(icon)),
        MenuItem("Help", help_menu),
        MenuItem("Advanced", Menu(MenuItem("Exit Tray…", on_exit_tray_cb))),
    )

def build_tray():
    if Icon is None:
        raise RuntimeError("pystray not available")
    image = _load_tray_image()
    icon = Icon("NovaTray", image, "Nova")
    icon.menu = _build_menu(icon)
    return icon

# -------------------------------
# Watchdog: auto-relaunch Nova if it dies
# -------------------------------
def _watch_main_app_and_restart():
    """
    Background watchdog:
      - If main app is not running AND user didn’t just exit it, relaunch it.
      - Uses exponential backoff capped by auto_restart_backoff_max_sec.
    """
    backoff = 2  # seconds (start small)
    cap = max(10, _cfg_backoff_cap_sec())
    while True:
        try:
            # If feature disabled, check rarely and skip.
            if not _cfg_auto_restart():
                time.sleep(10)
                continue

            # If Nova is running, reset backoff and chill.
            if _backend.is_main_running():
                backoff = 2
                time.sleep(3)
                continue

            # Respect user’s intentional exit cooldown.
            if _user_exit_cooldown_active():
                time.sleep(2)
                continue

            # Not running → try to relaunch
            ok = _backend.launch_main_app()
            if ok:
                # Give it a moment to create its window / settle
                time.sleep(5)
                backoff = 2
            else:
                # Failed — backoff (exponential up to cap)
                time.sleep(min(backoff, cap))
                backoff = min(backoff * 2, cap)

        except Exception:
            # Never die; wait a bit then keep watching
            time.sleep(5)

# -------------------------------
# Single-instance guard (TCP loopback)
# -------------------------------
def try_become_primary():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(SINGLETON_ADDR)
    except OSError:
        try:
            with socket.create_connection(SINGLETON_ADDR, timeout=1.0) as c:
                c.sendall(b"OPEN\n")
        except Exception:
            pass
        return False

    s.listen(2)

    def server():
        while True:
            try:
                conn, _ = s.accept()
            except Exception:
                break
            # accept loop
            with conn:
                try:
                    data = conn.recv(64)
                except Exception:
                    continue
                if not data:
                    continue
                cmd = data.decode("utf-8", "ignore").strip().upper()

                # HELLO handshake so main.py can verify it’s our tray
                if cmd == "HELLO":
                    try:
                        conn.sendall(b"NOVA_TRAY\n")
                    except Exception:
                        pass
                    continue

                if cmd == "OPEN":
                    _tk_after(open_nova_and_focus)
                elif cmd == "TIP":
                    _tk_after(show_quick_start)  # default: write sentinel on close
                elif cmd == "OPEN_AND_TIP":
                    _tk_after(open_nova_and_focus)
                    _tk_after(show_quick_start, delay_ms=250)  # default: write sentinel
                elif cmd == "BYE":  # <-- new: mark intentional exit right now
                    _mark_user_exit()
                    try:
                        conn.sendall(b"OK\n")
                    except Exception:
                        pass

    t = threading.Thread(target=server, daemon=True)
    t.start()
    return True

# -------------------------------
# Main
# -------------------------------
def main():
    if not try_become_primary():
        return

    _init_tk()

    icon = build_tray()
    icon.run_detached()

    # Start/restore wake listener according to saved setting
    global _last_wake_state
    try:
        if _wake_is_on():
            start_wake_listener_thread()
        _last_wake_state = _wake_is_on()
    except Exception:
        pass

    # Keep tray menu + listener in sync with any external changes
    threading.Thread(target=_watch_wake_setting, args=(icon,), daemon=True).start()

    # ✅ Start watchdog so Nova auto-relaunches if it crashes
    threading.Thread(target=_watch_main_app_and_restart, daemon=True).start()

    # If launched with --show-tip, show it now (sentinel written on close).
    if any(a.lower() in {"--show-tip", "/showtip"} for a in sys.argv[1:]):
        _tk_after(show_quick_start)

    _root.mainloop()

# -------------------------------
# Adapter-backed wrappers
# -------------------------------
def open_nova_and_focus():
    if _backend.is_main_running():
        _backend.bring_to_front()
        return True
    if _backend.launch_main_app():
        time.sleep(1.0)
        _backend.bring_to_front()
        return True
    return False

def hide_nova():
    return _backend.hide_window()

def exit_nova():
    # ✅ Mark user-intent so watchdog won't instantly relaunch
    _mark_user_exit()
    return _backend.close_window()

if __name__ == "__main__":
    main()
