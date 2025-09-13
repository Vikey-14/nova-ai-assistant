# tray_linux.py — Linux tray with Windows/Mac parity (green dot when ON; nothing when OFF)
from __future__ import annotations

import os, sys, threading, time, math, signal
from pathlib import Path

# --- .env support (tray uses same keys as main) ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=True)
except Exception:
    pass

# ---------- soft deps (required for a tray) ----------
try:
    import pystray
    from pystray import Menu, MenuItem
    from PIL import Image as PILImage
    from PIL import ImageDraw as PILImageDraw
except Exception:  # if missing, we simply don't start a tray
    pystray = None
    Menu = MenuItem = None
    PILImage = PILImageDraw = None

# ---------- optional deps used for popups ----------
try:
    import tkinter as tk
    from tkinter import font as tkfont
    from PIL import ImageTk, Image as _PILImage  # noqa: F401 (logo for tip/confirm)
except Exception:
    tk = None
    tkfont = None

# ---------- backend + utils ----------
try:
    from platform_adapter import get_backend
    _backend = get_backend()
except Exception:
    _backend = None

# Reuse your project helpers (parity with Win/Mac)
try:
    from utils import resource_path, get_wake_mode, set_wake_mode, load_settings  # load_settings kept for parity
except Exception:
    # Safe fallbacks (tray still works without persistence) — default ON for first-run UX
    def resource_path(name: str) -> str: return name
    def get_wake_mode() -> bool | None: return None   # "unset" so we can treat None ⇒ ON
    def set_wake_mode(_v: bool, *_, **__): return None
    def load_settings() -> dict: return {}


# ---------- wake listener plumbing ----------
try:
    from wake_word_listener import start_wake_listener_thread, stop_wake_listener_thread
except Exception:
    def start_wake_listener_thread(): pass
    def stop_wake_listener_thread(): pass

# ---------- app-data (use backend dir for parity) ----------
try:
    APPDATA_DIR = _backend.user_data_dir() if _backend else None
except Exception:
    APPDATA_DIR = None
if not APPDATA_DIR:
    import pathlib
    APPDATA_DIR = pathlib.Path.home() / ".local" / "share" / "Nova"
APPDATA_DIR = Path(APPDATA_DIR)
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------- PID fast-path (matches main.py writer) ----------
PIDFILE = APPDATA_DIR / "nova_main.pid"

def _read_pidfile() -> int | None:
    try:
        if PIDFILE.exists():
            v = PIDFILE.read_text(encoding="utf-8").strip()
            return int(v) if v else None
    except Exception:
        pass
    return None

def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        try:
            # kill(pid, 0) → no signal, just error check
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False

def _main_is_running_fast() -> bool:
    pid = _read_pidfile()
    if pid:
        return _pid_alive(pid)
    # Rare fallback if PID file missing
    try:
        return bool(_backend and _backend.is_main_running())
    except Exception:
        return False

# ---------- tiny hidden Tk root (for popups) ----------
_root: "tk.Tk|None" = None
def _init_tk():
    global _root
    if tk is None:
        return None
    try:
        _root = tk.Tk()
        _root.withdraw()
    except Exception:
        _root = None
    return _root

def _tk_after(fn, *args, delay_ms: int = 0, **kwargs):
    if _root and _root.winfo_exists():
        _root.after(delay_ms, lambda: fn(*args, **kwargs))
    else:
        try: fn(*args, **kwargs)
        except Exception: pass

# ---------- tray icon drawing ----------
def _tray_icon_size() -> int:
    return 32  # typical Linux panel size

def _load_tray_image() -> PILImage.Image:
    for name in ("nova_icon_big.ico", "assets/nova_icon_big.ico",
                 "nova_icon.ico", "assets/nova_icon.ico",
                 "assets/nova_icon.png", "nova_icon.png",
                 "assets/nova_icon_256.png"):
        try:
            img = PILImage.open(resource_path(name))
            return img.copy().resize((_tray_icon_size(), _tray_icon_size()), PILImage.LANCZOS)
        except Exception:
            continue
    return PILImage.new("RGBA", (_tray_icon_size(), _tray_icon_size()), (90, 79, 207, 255))

def _state_icon(on: bool) -> PILImage.Image:
    """
    Parity rule:
      - ON  → draw small GREEN dot bottom-right
      - OFF → plain base icon (NO dot)
    """
    base = _load_tray_image().copy()
    if not on:
        return base  # OFF => no overlay at all
    try:
        w, h = base.size
        draw = PILImageDraw.Draw(base, "RGBA")
        r = max(3, w // 7)
        m = max(2, w // 14)
        x1, y1 = w - (r + m), h - (r + m)
        x2, y2 = w - m,       h - m
        draw.ellipse([x1-1, y1-1, x2+1, y2+1], fill=(46, 204, 113, 255), outline=(255, 255, 255, 220))
    except Exception:
        pass
    return base

# ---------- wake helpers ----------
_last_wake_state = None

def _wake_is_on() -> bool:
    try:
        v = get_wake_mode()
        # Default to ON if unset/missing
        return True if v is None else bool(v)
    except Exception:
        return True  # be generous on errors for first-run UX

def _set_wake_on(on: bool):
    """Persist wake state in a way that works with both old/new utils signatures."""
    try:
        # legacy signature (Windows/Mac builds)
        set_wake_mode(bool(on), persist=True, notify=True)
    except TypeError:
        # Linux utils.set_wake_mode(enabled) only
        set_wake_mode(bool(on))
    except Exception:
        # keep tray usable even if persistence fails
        pass


def _wake_label() -> str:
    return f"Wake Mode   {'● ON' if _wake_is_on() else '○ OFF'}"

def _toggle_wake(icon: "pystray.Icon|None" = None):
    try:
        new_state = not _wake_is_on()
        _set_wake_on(new_state)
        if new_state: start_wake_listener_thread()
        else:         stop_wake_listener_thread()
    except Exception:
        pass
    # refresh menu/icon immediately
    if icon is not None:
        try: icon.icon = _state_icon(new_state)
        except Exception: pass
        try: icon.menu = _build_menu(icon); icon.update_menu()
        except Exception: pass

# ---------- UI bits (tip + exit) ----------
def _center_no_flash(win: "tk.Toplevel", w: int, h: int):
    win.withdraw()
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x, y = (sw - w)//2, (sh - h)//2
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.deiconify()
    try:
        win.lift(); win.focus_force()
        win.after(10, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

def _show_tray_tip():
    if tk is None: return
    try:
        pop = tk.Toplevel(master=_root)
        pop.title("Nova • Quick Start")
        pop.configure(bg="#1a103d")
        pop.resizable(False, False)
        pop.attributes("-topmost", True)

        WIDTH, HEIGHT = 420, 300
        canvas = tk.Canvas(pop, width=WIDTH, height=HEIGHT,
                           bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        # starfield (lightweight)
        layers = {1: [], 2: [], 3: []}
        import random, math as _m
        for layer in layers:
            count = 22 if layer == 1 else 14
            for _ in range(count):
                x = random.randint(0, WIDTH); y = random.randint(0, HEIGHT)
                s = layer
                layers[layer].append(canvas.create_oval(x, y, x+s, y+s, fill="#c9cfff", outline=""))
        def anim():
            for layer, stars in layers.items():
                dx = 0.2 * layer
                for s in stars:
                    canvas.move(s, dx, 0)
                    if (coords := canvas.coords(s)) and coords[0] > WIDTH:
                        canvas.move(s, -WIDTH, 0)
            if pop.winfo_exists(): pop.after(50, anim)
        pop.after(50, anim)

        # optional orbiting logo (parity with Win/Mac)
        try:
            img_path = resource_path("nova_face_glow.png")
            _img = _PILImage.open(img_path).resize((80, 80))
            _logo = ImageTk.PhotoImage(_img)
            logo_id = canvas.create_image(WIDTH // 2, 84, image=_logo)
            pop._logo_ref = _logo  # keep ref
            angle = 0; radius = 10; cx, cy = WIDTH // 2, 84
            def orbit():
                nonlocal angle
                if not pop.winfo_exists(): return
                angle += 2
                rad = _m.radians(angle)
                x = cx + radius * _m.cos(rad); y = cy + radius * _m.sin(rad)
                canvas.coords(logo_id, x, y)
                pop.after(50, orbit)
            pop.after(50, orbit)
        except Exception:
            pass

        canvas.create_text(WIDTH//2, 156, text="Nova is running in the system tray.",
                           font=("Segoe UI", 11), fill="#dcdcff", width=WIDTH-60, justify="center")
        canvas.create_text(WIDTH//2, 198,
                           text="Tip: If you don’t see the tray icon, click the ^ near the clock.",
                           font=("Segoe UI", 10), fill="#9aa0c7", width=WIDTH-60, justify="center")

        btn = tk.Button(pop, text="Got it!", command=pop.destroy,
                        font=("Segoe UI", 10, "bold"),
                        bg="#5a4fcf", fg="white", activebackground="#9b95ff",
                        activeforeground="white", relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        canvas.create_window(WIDTH//2, HEIGHT-36, window=btn)

        _center_no_flash(pop, WIDTH, HEIGHT)
    except Exception:
        pass

def _confirm_exit_tray() -> bool:
    if tk is None:
        return True
    try:
        w = tk.Toplevel(master=_root)
        w.title("Exit Tray?")
        w.configure(bg="#1a103d")
        w.resizable(False, False)
        w.attributes("-topmost", True)

        WIDTH, HEIGHT = 420, 300
        canvas = tk.Canvas(w, width=WIDTH, height=HEIGHT, bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        # starfield + (optional) orbiting logo
        layers = {1: [], 2: [], 3: []}
        import random, math as _m
        for layer in layers:
            count = 22 if layer == 1 else 14
            for _ in range(count):
                x = random.randint(0, WIDTH); y = random.randint(0, HEIGHT)
                s = layer
                layers[layer].append(canvas.create_oval(x, y, x+s, y+s, fill="#c9cfff", outline=""))
        def anim():
            for layer, stars in layers.items():
                dx = 0.2 * layer
                for s in stars:
                    canvas.move(s, dx, 0)
                    if (coords := canvas.coords(s)) and coords[0] > WIDTH:
                        canvas.move(s, -WIDTH, 0)
            if w.winfo_exists(): w.after(50, anim)
        w.after(50, anim)

        try:
            img_path = resource_path("nova_face_glow.png")
            _img = _PILImage.open(img_path).resize((80, 80))
            _logo = ImageTk.PhotoImage(_img)
            logo_id = canvas.create_image(WIDTH // 2, 72, image=_logo)
            w._logo_ref = _logo
            angle = 0; radius = 10; cx, cy = WIDTH // 2, 72
            def orbit():
                nonlocal angle
                if not w.winfo_exists(): return
                angle += 2
                rad = _m.radians(angle)
                x = cx + radius * _m.cos(rad); y = cy + radius * _m.sin(rad)
                canvas.coords(logo_id, x, y)
                w.after(50, orbit)
            w.after(50, orbit)
        except Exception:
            pass

        canvas.create_text(WIDTH//2, 160,
                           text="Are you sure you want to exit the tray?",
                           font=("Segoe UI", 11), fill="#dcdcff",
                           justify="center", width=WIDTH-60)
        canvas.create_text(WIDTH//2, 196,
                           text="Nova will stop running until you start it again (Nova Tray).",
                           font=("Segoe UI", 11), fill="#dcdcff",
                           justify="center", width=WIDTH-60)

        result = {"ok": False}
        row = tk.Frame(w, bg="#1a103d")

        def finish(ok):
            result["ok"] = ok
            try: w.destroy()
            finally: pass

        def _btn(parent, text, base, hover, cmd):
            b = tk.Canvas(parent, bg="#1a103d", highlightthickness=0, bd=0)
            f = ("Segoe UI", 10, "bold")
            label = b.create_text(0, 0, text=text, anchor="nw", fill="white", font=f)
            b.update_idletasks()
            tw = b.bbox(label)[2] - b.bbox(label)[0]
            W = tw + 24; H = 30
            b.config(width=W, height=H)
            rect = b.create_rectangle(0, 0, W, H, outline="", fill=base)
            b.tag_raise(label, rect)
            def over(_): b.itemconfigure(rect, fill=hover)
            def out(_):  b.itemconfigure(rect, fill=base)
            b.bind("<Enter>", over); b.bind("<Leave>", out); b.bind("<Button-1>", lambda e: cmd())
            b.coords(label, W//2, 6); b.itemconfigure(label, anchor="n")
            return b

        exit_btn  = _btn(row, "Exit Tray", "#b84b5f", "#e07b8d", lambda: finish(True))
        cancel_btn = _btn(row, "Cancel",   "#5a4fcf", "#9b95ff", lambda: finish(False))
        exit_btn.pack(side="left", padx=(0, 10))
        cancel_btn.pack(side="left", padx=(10, 0))
        canvas.create_window(WIDTH//2, HEIGHT-56, window=row)

        w.bind("<Escape>", lambda e: finish(False))
        w.bind("<Return>", lambda e: finish(False))

        _center_no_flash(w, WIDTH, HEIGHT)
        w.wait_window()
        return bool(result["ok"])
    except Exception:
        return True

# ---------- “seen once” guard (harmless to keep) ----------
_seen_once_lock = threading.Lock()
_seen_once = False

def _arm_seen_once():
    global _seen_once
    with _seen_once_lock:
        _seen_once = True

def _has_seen_once() -> bool:
    with _seen_once_lock:
        return _seen_once

# ---------- menu + actions ----------
def _open_nova_and_focus():
    if not _backend: return False
    if _main_is_running_fast():
        _arm_seen_once()
        return _backend.bring_to_front()
    if _backend.launch_main_app():
        time.sleep(1.0)
        _arm_seen_once()
        return _backend.bring_to_front()
    return False

def _hide_nova():
    if not _backend: return False
    return _backend.hide_window()

def _exit_nova():
    # 1) Polite IPC to main
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 50574), timeout=0.6) as c:
            c.sendall(b"EXIT\n")
            try:
                c.recv(16)
            except Exception:
                pass
            return True
    except Exception:
        pass

    # 2) OS-level fallback
    if not _backend:
        return False
    return _backend.close_window()


def _exit_tray(icon: "pystray.Icon"):
    try: stop_wake_listener_thread()
    except Exception: pass
    ok = _confirm_exit_tray()
    if ok:
        try: icon.visible = False; icon.stop()
        except Exception: pass
        try:
            if _root: _root.quit()
        except Exception:
            pass
        os._exit(0)

def _build_menu(icon: "pystray.Icon"):
    return Menu(
        MenuItem("Open Nova", lambda _i: _open_nova_and_focus()),
        MenuItem("Hide Nova",  lambda _i: _hide_nova()),
        MenuItem("Exit Nova",  lambda _i: _exit_nova()),
        MenuItem(_wake_label(), lambda _i: _toggle_wake(icon)),
        MenuItem("Help", Menu(
            MenuItem("Tray Tip", lambda _i: _tk_after(_show_tray_tip))
        )),
        MenuItem("Advanced", Menu(
            MenuItem("Exit Tray…", lambda _i: _exit_tray(icon))
        )),
    )

# ---------- background watchers ----------
def _watch_wake(icon: "pystray.Icon"):
    last = None
    while True:
        try:
            cur = _wake_is_on()
            if cur != last:
                last = cur
                if cur: start_wake_listener_thread()
                else:   stop_wake_listener_thread()
                try: icon.icon = _state_icon(cur)
                except Exception: pass
                try: icon.menu = _build_menu(icon); icon.update_menu()
                except Exception: pass
        except Exception:
            pass
        time.sleep(0.5)

# ---------- signal handling (clean shutdown) ----------
def _install_signal_handlers(icon: "pystray.Icon"):
    def _term(*_):
        try: icon.visible = False
        except Exception: pass
        try: icon.stop()
        except Exception: pass
        try:
            if _root: _root.quit()
        except Exception: pass
        os._exit(0)
    try:
        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)
    except Exception:
        pass

# ---------- entrypoints ----------
def start_tray_in_thread():
    if pystray is None or PILImage is None:
        return None
    t = threading.Thread(target=_run_tray, daemon=True)
    t.start()
    return t


def _run_tray():
    _init_tk()
    icon = pystray.Icon("NovaTray", icon=_state_icon(_wake_is_on()), title="Nova Tray")
    icon.menu = _build_menu(icon)

    _install_signal_handlers(icon)

    # --- Initial listener + icon/menu sync (so it starts in the correct state) ---
    try:
        cur = _wake_is_on()
        if cur:
            start_wake_listener_thread()
        else:
            stop_wake_listener_thread()
        # reflect the state immediately
        icon.icon = _state_icon(cur)
        icon.menu = _build_menu(icon)
        try:
            icon.update_menu()
        except Exception:
            pass
    except Exception:
        pass

    # Keep everything in sync thereafter
    threading.Thread(target=_watch_wake, args=(icon,), daemon=True).start()

    try:
        icon.run()
    except Exception:
        pass

