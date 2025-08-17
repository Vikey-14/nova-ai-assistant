# tray_app.py
# -*- coding: utf-8 -*-

import os, sys, time, socket, threading, subprocess, ctypes, platform, math
from pathlib import Path

# ---------- Optional GUI bits for popups ----------
import tkinter as tk
from tkinter import font as tkfont  # for precise text height (kept for future use)
from PIL import Image, ImageTk, Image as PILImage

# ---------- psutil for stricter process checks ----------
try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # graceful fallback to title-only matching

# ---------- pystray ----------
try:
    from pystray import Icon, Menu, MenuItem
except Exception:
    Icon = None
    Menu = None
    MenuItem = None

# Paths (robust in frozen + dev)
IS_FROZEN = getattr(sys, "frozen", False)
EXE_DIR = Path(sys.executable).parent if IS_FROZEN else Path(__file__).parent.resolve()
APP_DIR = Path(getattr(sys, "_MEIPASS", EXE_DIR)).resolve()
HERE = EXE_DIR

# Prefer the sibling NOVA.exe. Fallbacks kept for safety.
NOVA_CANDIDATES = [
    EXE_DIR / "NOVA.exe",
    EXE_DIR / "Nova.exe",
    HERE / "NOVA.exe",
    HERE / "Nova.exe",
]

# Single-instance TCP port (loopback only)
SINGLETON_PORT = 50573
SINGLETON_ADDR = ("127.0.0.1", SINGLETON_PORT)

# Windows flags
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# AppData + sentinel for first-run Quick Start
APPDATA_DIR = Path(os.environ.get("APPDATA", str(HERE))) / "Nova"
FIRST_TIP_SENTINEL = APPDATA_DIR / ".quick_start_shown"

# Tk globals
_root: tk.Tk | None = None
_tray_tip_win = [None]  # keep reference

# -------------------------------
# Utilities
# -------------------------------
def resource_path(name: str) -> str:
    for base in [EXE_DIR, APP_DIR, EXE_DIR / "assets", APP_DIR / "assets"]:
        p = Path(base) / name
        if p.exists():
            return str(p)
    return name

def is_windows() -> bool:
    return platform.system().lower().startswith("win")

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
# Windows window control helpers
# -------------------------------
def _enum_windows():
    if not is_windows():
        return
    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextLengthW = user32.GetWindowTextLengthW

    def foreach(hwnd, lParam):
        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value
        _found.append((hwnd, title))   # include hidden windows too
        return True

    _found = []
    EnumWindows(EnumWindowsProc(foreach), 0)
    for h, t in _found:
        yield h, t

def _window_pid(hwnd: int):
    try:
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return None

def _title_is_candidate(title: str) -> bool:
    t = (title or "").strip().lower()
    return t == "nova" or t.startswith("nova - ")

def _find_nova_hwnd():
    if not is_windows():
        return None

    if psutil is None:
        for hwnd, title in _enum_windows():
            if _title_is_candidate(title):
                return hwnd
        return None

    app_dir_l = str(APP_DIR).lower().replace("\\", "/")
    for hwnd, title in _enum_windows():
        if not _title_is_candidate(title):
            continue

        pid = _window_pid(hwnd)
        if not pid:
            continue

        try:
            p = psutil.Process(pid)
            pname = (p.name() or "").lower()
            if "tray" in pname:
                continue  # don't match the tray itself
            if pname in {"nova.exe"}:
                return hwnd
            if pname in {"pythonw.exe", "python.exe", "pythonw", "python"}:
                cmd = " ".join(p.cmdline()).lower().replace("\\", "/")
                if "main.py" in cmd and app_dir_l in cmd:
                    return hwnd
        except Exception:
            continue
    return None

def _bring_to_front(hwnd):
    if not is_windows() or not hwnd:
        return
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)

def _hide_window(hwnd):
    if not is_windows() or not hwnd:
        return
    ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

def _close_window(hwnd):
    if not is_windows() or not hwnd:
        return
    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE

def _launch_nova(visible=True):
    for p in NOVA_CANDIDATES:
        if p.exists():
            try:
                subprocess.Popen([str(p)], cwd=str(p.parent), close_fds=True,
                                 creationflags=CREATE_NO_WINDOW)
                return True
            except Exception:
                pass
    if not IS_FROZEN:
        main_py = EXE_DIR / "main.py"
        if main_py.exists():
            py = Path(sys.executable)
            pyw = py.with_name("pythonw.exe") if os.name == "nt" else py
            try:
                subprocess.Popen([str(pyw), str(main_py)], cwd=str(main_py.parent),
                                 close_fds=True, creationflags=CREATE_NO_WINDOW)
                return True
            except Exception:
                return False
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
        _root.iconbitmap(resource_path("nova_icon.ico"))
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
# Tip popup (no flash + safe close)
# -------------------------------
def show_quick_start():
    global _tray_tip_win
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
            popup.iconbitmap(resource_path("nova_icon.ico"))
        except Exception:
            pass

        # track scheduled callbacks so we can cancel on close
        _closing = [False]
        _orbit_after = [None]
        _stars_after = [None]

        def _safe_after(ms, fn):
            if _closing[0] or not popup.winfo_exists():
                return None
            return popup.after(ms, fn)

        def _cancel_afters():
            for aid in (_orbit_after[0], _stars_after[0]):
                if aid:
                    try:
                        popup.after_cancel(aid)
                    except Exception:
                        pass

        def _on_close():
            _closing[0] = True
            _cancel_afters()
            try:
                _ensure_dirs()
                if not FIRST_TIP_SENTINEL.exists():
                    FIRST_TIP_SENTINEL.write_text("1", encoding="utf-8")
            except Exception:
                pass
            try:
                popup.destroy()
            finally:
                _tray_tip_win[0] = None

        popup.protocol("WM_DELETE_WINDOW", _on_close)
        popup.bind("<Escape>", lambda e: _on_close())

        canvas = tk.Canvas(popup, width=420, height=120, bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack()

        # twinkling stars
        star_layers = {1: [], 2: [], 3: []}
        for layer in star_layers:
            for _ in range(10):
                x = __import__("random").randint(0, 420)
                y = __import__("random").randint(0, 120)
                size = layer
                star = canvas.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
                star_layers[layer].append(star)

        # rotating/orbiting logo
        try:
            img_path = resource_path("nova_face_glow.png")
            if not Path(img_path).exists():
                img_path = resource_path("assets/nova_face_glow.png")
            img = PILImage.open(img_path).resize((80, 80))
            logo = ImageTk.PhotoImage(img)
            logo_id = canvas.create_image(210, 60, image=logo)
            popup._logo_ref = logo
            angle = 0
            radius = 10
            cx, cy = 210, 60
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
                    if coords and coords[0] > 420:
                        canvas.move(star, -420, 0)
            _stars_after[0] = _safe_after(50, animate_stars)
        _stars_after[0] = _safe_after(50, animate_stars)

        tk.Label(
            popup,
            text=("Nova is running in the system tray.\n\n"
                  "Tip: If you don’t see the tray icon, click the ^ arrow near the clock.\n"
                  "You can drag it out to keep it always visible."),
            font=("Segoe UI", 11),
            fg="#dcdcff",
            bg="#1a103d",
            justify="center",
            wraplength=360
        ).pack(pady=(6, 10))

        # --- Standard "Got it!" button ---
        btn_row = tk.Frame(popup, bg="#1a103d")
        btn_row.pack(pady=(8, 22))

        base, hover = "#5a4fcf", "#6a5df0"
        got_it = tk.Button(
            btn_row,
            text="Got it!",
            command=_on_close,
            font=("Segoe UI", 10, "bold"),
            bg=base, fg="white",
            activebackground=hover, activeforeground="white",
            relief="flat",
            bd=0, highlightthickness=0,
            padx=16, pady=8,
            anchor="center",
            cursor="hand2",
        )
        got_it.pack()
        got_it.bind("<Enter>", lambda e: got_it.config(bg=hover))
        got_it.bind("<Leave>", lambda e: got_it.config(bg=base))
        popup.bind("<Return>", lambda e: _on_close())

        # Center then reveal (no flash)
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.deiconify()
        try:
            popup.lift()
            popup.focus_force()
            popup.after(10, lambda: popup.attributes("-topmost", False))
        except Exception:
            pass

    except Exception:
        pass

# -------------------------------
# Exit Tray confirmation (no flash + hover + moving logo)
# -------------------------------
def confirm_exit_tray() -> bool:
    """Exit Tray confirmation (star header + perfectly centered canvas-buttons)."""
    import tkinter.font as tkfont  # local import to be safe

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
        w.withdraw()
        w.title("Exit Tray?")
        w.geometry("420x300")
        w.configure(bg="#1a103d")
        w.resizable(False, False)
        w.attributes("-topmost", True)
        try: w.iconbitmap(resource_path("nova_icon.ico"))
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

        canvas = tk.Canvas(w, width=420, height=120, bg="#1a103d", highlightthickness=0, bd=0)
        canvas.pack()
        star_layers = {1: [], 2: [], 3: []}
        import random
        for layer in star_layers:
            for _ in range(10):
                x = random.randint(0, 420); y = random.randint(0, 120)
                size = layer
                star = canvas.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
                star_layers[layer].append(star)
        try:
            img_path = resource_path("nova_face_glow.png")
            if not Path(img_path).exists():
                img_path = resource_path("assets/nova_face_glow.png")
            _img = PILImage.open(img_path).resize((80, 80))
            _logo = ImageTk.PhotoImage(_img)
            logo_id = canvas.create_image(210, 60, image=_logo)
            w._logo_ref = _logo
            angle = 0; radius = 10; cx, cy = 210, 60
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
                    if (coords := canvas.coords(star)) and coords[0] > 420:
                        canvas.move(star, -420, 0)
            _stars_after[0] = _safe_after(50, animate_stars)
        _stars_after[0] = _safe_after(50, animate_stars)

        frm = tk.Frame(w, bg="#1a103d")
        frm.pack(fill="both", expand=True, padx=18, pady=(8, 8))
        tk.Label(
            frm,
            text=("Are you sure you want to exit the tray?\n\n"
                  "Nova will stop running until you start it again from the Start Menu (Nova Tray)."),
            font=("Segoe UI", 11), fg="#dcdcff", bg="#1a103d",
            justify="center", wraplength=360
        ).pack(pady=(4, 10))

        result = {"ok": False}
        def _finish(ok):
            _closing[0] = True
            _cancel_afters()
            result["ok"] = ok
            try: w.destroy()
            except Exception: pass

        row = tk.Frame(frm, bg="#1a103d"); row.pack(pady=(12, 18))
        btn_font = ("Segoe UI", 10, "bold")
        f = tkfont.Font(font=btn_font)
        fixed_w = max(f.measure("Exit Tray"), f.measure("Cancel")) + 14 * 2

        exit_base, exit_hover = "#b84b5f", "#e07b8d"
        can_base,  can_hover  = "#5a4fcf", "#6a5df0"

        # Keep top slightly tighter for symmetry on all machines
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
    for name in ("nova_icon.ico", "assets/nova_icon.ico", "assets/nova_icon.png", "nova_icon.png"):
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

def build_tray():
    if Icon is None:
        raise RuntimeError("pystray not available")

    image = _load_tray_image()

    def on_open(icon, item):
        open_nova_and_focus()

    def on_hide(icon, item):
        hide_nova()

    def on_exit_nova(icon, item):
        exit_nova()

    def on_quick_start(icon, item):
        _tk_after(show_quick_start)

    def on_exit_tray(icon, item):
        # Show Advanced popup on the Tk thread (prevents corner flash),
        # but block this tray-handler thread until the user decides.
        evt = threading.Event()
        result = {"ok": False}

        def _ask():
            try:
                ok = confirm_exit_tray()
            except Exception:
                ok = True  # conservative: allow exit if dialog fails
            result["ok"] = ok
            evt.set()

        _tk_after(_ask)
        evt.wait()

        if result["ok"]:
            try:
                icon.visible = False
                icon.stop()
            except Exception:
                pass
            try:
                if _root:
                    _root.quit()
            except Exception:
                pass
            os._exit(0)

    help_menu = Menu(MenuItem("Quick Start", on_quick_start))

    menu = Menu(
        MenuItem("Open Nova", on_open),
        MenuItem("Hide Nova", on_hide),
        MenuItem("Exit Nova", on_exit_nova),
        MenuItem("Help", help_menu),
        MenuItem("Advanced", Menu(MenuItem("Exit Tray…", on_exit_tray))),
    )

    icon = Icon("NovaTray", image, "Nova", menu)
    return icon

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
            with conn:
                try:
                    data = conn.recv(64)
                except Exception:
                    continue
                if not data:
                    continue
                cmd = data.decode("utf-8", "ignore").strip().upper()
                if cmd == "OPEN":
                    _tk_after(open_nova_and_focus)
                elif cmd == "TIP":
                    _tk_after(show_quick_start)
                elif cmd == "OPEN_AND_TIP":
                    _tk_after(open_nova_and_focus)
                    _tk_after(show_quick_start, delay_ms=250)

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

    # If launched with --show-tip, show it now (sentinel written on close).
    if any(a.lower() in {"--show-tip", "/showtip"} for a in sys.argv[1:]):
        _tk_after(show_quick_start)

    _root.mainloop()

if __name__ == "__main__":
    # small wrappers referenced above
    def open_nova_and_focus():
        hwnd = _find_nova_hwnd()
        if hwnd:
            _bring_to_front(hwnd)
            return True
        if _launch_nova(visible=True):
            for _ in range(40):
                time.sleep(0.1)
                hwnd = _find_nova_hwnd()
                if hwnd:
                    _bring_to_front(hwnd)
                    return True
        return False

    def hide_nova():
        hwnd = _find_nova_hwnd()
        if hwnd:
            _hide_window(hwnd)
            return True
        return False

    def exit_nova():
        hwnd = _find_nova_hwnd()
        if hwnd:
            _close_window(hwnd)
            return True
        return False

    main()
