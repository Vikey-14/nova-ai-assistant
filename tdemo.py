# ready_tip_calibrator.py — v4 (Linux tip visual parity preview on any OS)
# Fine-tune when the Tray Tip should appear after Nova says the ready line.

import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import threading, time, sys, math
from pathlib import Path

# Try to use your project's multilingual TTS if available.
try:
    import utils  # expects utils._speak_multilang(en, hi=None, de=None, fr=None, es=None)
    HAVE_UTILS = True
except Exception:
    HAVE_UTILS = False

print("[ready_tip_calibrator/linux] HAVE_UTILS =", HAVE_UTILS)

# ---------------- Timing helpers (same structure as main) ----------------
def _estimate_ms(text: str, ms_per_word: int, min_ms: int, cushion_ms: int) -> int:
    words = max(1, len((text or "").split()))
    return max(min_ms, words * ms_per_word + cushion_ms)

def _scheduled_delay_ms(text: str, ms_per_word: int, min_ms: int, cushion_ms: int,
                        early_shift_ms: int, hard_gate_ms: int, extra_hold_ms: int) -> tuple[int, int]:
    base = _estimate_ms(text, ms_per_word, min_ms, cushion_ms)
    delay = max(0, base - max(0, early_shift_ms))
    if hard_gate_ms > 0:
        delay = max(delay, hard_gate_ms)
    delay += max(0, extra_hold_ms)
    return int(delay), int(base)

# ---------------- Utilities (resource path) ----------------
def resource_path(name: str) -> str:
    # same pattern as tray/main: look in exe dir and assets
    try:
        EXE_DIR = Path(getattr(sys, "frozen", False) and Path(sys.executable).parent or Path(__file__).parent).resolve()
    except Exception:
        EXE_DIR = Path(".").resolve()
    for base in [EXE_DIR, EXE_DIR / "assets"]:
        p = (base / name)
        if p.exists():
            return str(p)
    return name  # let PIL try cwd

# ---------------- Linux-style Tray Tip (starfield + orbiting logo) ----------------
def _linux_font_pair(root) -> tuple[str, tuple, tuple]:
    """
    Return (family_name, f_title, f_tip) using a Linux-ish stack:
      Noto Sans → DejaVu Sans → Segoe UI → Arial → TkDefault
    """
    fams = {f.lower() for f in tkfont.families(root)}
    def pick(*candidates):
        for fam in candidates:
            if fam.lower() in fams:
                return fam
        try:
            return tkfont.nametofont("TkDefaultFont").actual("family")
        except Exception:
            return "Sans"
    family = pick("Noto Sans", "DejaVu Sans", "Segoe UI", "Arial")
    return family, (family, 11), (family, 10)

def _center_no_flash(win: tk.Toplevel, w: int, h: int):
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

def _show_tip(parent):
    """
    Render the EXACT Linux tip (copy, size, layout, animation)
    so you can preview Linux UX on any OS.
    """
    popup = tk.Toplevel(parent)
    popup.withdraw()
    popup.title("Nova • Quick Start (Linux preview)")
    popup.configure(bg="#1a103d")
    popup.resizable(False, False)
    try:
        popup.attributes("-topmost", True)
    except Exception:
        pass

    WIDTH, HEIGHT = 420, 300
    canvas = tk.Canvas(popup, width=WIDTH, height=HEIGHT,
                       bg="#1a103d", highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    # starfield layers (same counts/speeds as tray_linux.py)
    star_layers = {1: [], 2: [], 3: []}
    import random
    for layer in star_layers:
        count = 22 if layer == 1 else 14
        for _ in range(count):
            x = random.randint(0, WIDTH); y = random.randint(0, HEIGHT)
            size = layer
            star = canvas.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
            star_layers[layer].append(star)

    def animate_stars():
        for layer, stars in star_layers.items():
            dx = 0.2 * layer
            for s in stars:
                canvas.move(s, dx, 0)
                coords = canvas.coords(s)
                if coords and coords[0] > WIDTH:
                    canvas.move(s, -WIDTH, 0)
        if popup.winfo_exists():
            popup.after(50, animate_stars)
    popup.after(50, animate_stars)

    # orbiting logo (80px, y=84, radius=10) — matches Linux tray
    try:
        from PIL import Image as PILImage, ImageTk
        img_path = resource_path("nova_face_glow.png")
        if not Path(img_path).exists():
            img_path = resource_path("assets/nova_face_glow.png")
        img = PILImage.open(img_path).resize((80, 80))
        logo = ImageTk.PhotoImage(img)
        logo_id = canvas.create_image(WIDTH // 2, 84, image=logo)
        popup._logo_ref = logo
        angle = 0; radius = 10; cx, cy = WIDTH // 2, 84
        def orbit():
            nonlocal angle
            if not popup.winfo_exists(): return
            angle += 2
            rad = math.radians(angle)
            x = cx + radius * math.cos(rad)
            y = cy + radius * math.sin(rad)
            canvas.coords(logo_id, x, y)
            popup.after(50, orbit)
        popup.after(50, orbit)
    except Exception:
        pass

    # --------- LINUX COPY + FONTS ----------
    family, f_title, f_tip = _linux_font_pair(parent)

    line1 = "Nova is running in your system tray."
    line2 = ("Tip: Tray location depends on your desktop (GNOME, KDE, etc.).\n"
             "Check your panel’s system tray or status area and pin Nova there.")

    canvas.create_text(
        WIDTH // 2, 148,
        text=line1,
        font=f_title, fill="#dcdcff",
        width=WIDTH - 60, justify="center"
    )
    canvas.create_text(
        WIDTH // 2, 198,
        text=line2,
        font=f_tip, fill="#9aa0c7",
        width=WIDTH - 60, justify="center"
    )

    base, hover = "#5a4fcf", "#9b95ff"
    btn = tk.Button(
        popup, text="Got it!",
        font=(family, 10, "bold"),
        bg=base, fg="white",
        activebackground=hover, activeforeground="white",
        relief="flat", bd=0, highlightthickness=0,
        padx=16, pady=8, cursor="hand2",
        command=popup.destroy
    )
    def _enter(_): btn.config(bg=hover)
    def _leave(_): btn.config(bg=base)
    btn.bind("<Enter>", _enter); btn.bind("<Leave>", _leave)
    canvas.create_window(WIDTH // 2, HEIGHT - 36, window=btn)

    _center_no_flash(popup, WIDTH, HEIGHT)

# ---------------- TTS helper: speak in the chosen language ----------------
def _speak_chosen_language(lang_code: str, text: str):
    """
    Speak the given line using your project's _speak_multilang, honoring
    utils.selected_language. Falls back to a timed sleep if utils is missing.
    """
    if not text:
        return
    if HAVE_UTILS and hasattr(utils, "_speak_multilang"):
        prev = getattr(utils, "selected_language", "en")
        try:
            utils.selected_language = lang_code
            utils._speak_multilang(
                text if lang_code == "en" else READY["en"],
                hi=(text if lang_code == "hi" else READY["hi"]),
                de=(text if lang_code == "de" else READY["de"]),
                fr=(text if lang_code == "fr" else READY["fr"]),
                es=(text if lang_code == "es" else READY["es"]),
            )
        finally:
            utils.selected_language = prev
    else:
        words = max(1, len(text.split()))
        time.sleep(max(0.8, words * 0.18))

# ---------------- UI ----------------
READY = {
    "en": "How can I help you today?",
    "hi": "मैं आज आपकी कैसे मदद कर सकती हूँ?",
    "de": "Wie kann ich dir heute helfen?",
    "fr": "Comment puis-je t'aider aujourd'hui ?",
    "es": "¿Cómo puedo ayudarte hoy?",
}
LANGS = [("English", "en"), ("हिन्दी", "hi"), ("Deutsch", "de"), ("Français", "fr"), ("Español", "es")]

def main():
    root = tk.Tk()
    root.title("Nova • Ready-line → Tip timing calibrator (Linux tip preview)")
    root.configure(bg="#110a2b")
    root.geometry("820x520")

    def lab(txt): return tk.Label(root, text=txt, fg="#cfd2ff", bg="#110a2b", font=("Segoe UI", 10))

    tk.Label(root, text="Fine-tune the delay; preview shows the exact Linux-style tip",
             fg="#e9ebff", bg="#110a2b", font=("Segoe UI", 12, "bold")).pack(pady=(10, 6))

    # Top row: language + line
    top = tk.Frame(root, bg="#110a2b"); top.pack(padx=14, pady=(0, 6), fill="x")
    lab("Language:").grid(in_=top, row=0, column=0, sticky="w")
    lang_menu = ttk.Combobox(top, state="readonly", width=12,
                             values=[name for name, _ in LANGS])
    lang_menu.current(0)
    lang_menu.grid(row=0, column=1, sticky="w", padx=(6, 18))

    lab("Line:").grid(in_=top, row=0, column=2, sticky="e")
    line_var = tk.StringVar(value=READY["en"])
    entry = tk.Entry(top, textvariable=line_var, width=48)
    entry.grid(row=0, column=3, sticky="we", padx=(6, 0))
    top.columnconfigure(3, weight=1)

    def current_lang_code() -> str:
        name = lang_menu.get()
        for n, c in LANGS:
            if n == name:
                return c
        return "en"

    # Sliders
    mid = tk.Frame(root, bg="#110a2b"); mid.pack(padx=14, pady=(4, 6), fill="x")
    sliders = {}
    def add_slider(row, name, from_, to_, init, step=10):
        lab(name).grid(in_=mid, row=row, column=0, sticky="w")
        var = tk.IntVar(value=init)
        s = tk.Scale(mid, from_=from_, to=to_, orient="horizontal", resolution=step,
                     bg="#110a2b", fg="#cfd2ff", troughcolor="#2a2460",
                     highlightthickness=0, variable=var, length=520,
                     command=lambda e: _update_estimate())
        s.grid(row=row, column=1, sticky="we")
        sliders[name] = var

    add_slider(0, "ms_per_word",    120, 800, 340, 10)
    add_slider(1, "min_ms",         300, 8000, 1500, 50)
    add_slider(2, "cushion_ms",       0, 2000, 300, 10)
    add_slider(3, "early_shift_ms",   0, 4000,   0, 10)
    add_slider(4, "hard_gate_ms",     0, 8000,   0, 50)
    add_slider(5, "extra_hold_ms",    0, 3000,   0, 10)

    status = tk.Label(root, text="", fg="#9ea4ff", bg="#110a2b", font=("Segoe UI", 10))
    status.pack(pady=(2, 8))

    def _vals():
        return (
            sliders["ms_per_word"].get(),
            sliders["min_ms"].get(),
            sliders["cushion_ms"].get(),
            sliders["early_shift_ms"].get(),
            sliders["hard_gate_ms"].get(),
            sliders["extra_hold_ms"].get(),
        )

    def _update_estimate():
        text = (line_var.get() or "").strip()
        msw, mn, cu, es, hg, eh = _vals()
        sched, base = _scheduled_delay_ms(text, msw, mn, cu, es, hg, eh)
        status.config(text=f"Estimate: base={base} ms  →  scheduled tip at {sched} ms")

    _update_estimate()

    # Buttons
    btn_row = tk.Frame(root, bg="#110a2b"); btn_row.pack(pady=(6, 12))

    def _speak(code, text):
        threading.Thread(target=lambda: _speak_chosen_language(code, text), daemon=True).start()

    def speak_and_show_estimated():
        code = current_lang_code()
        text = (line_var.get() or "").strip()
        msw, mn, cu, es, hg, eh = _vals()
        sched, base = _scheduled_delay_ms(text, msw, mn, cu, es, hg, eh)
        status.config(text=f"Estimate: base={base} ms  →  scheduled tip at {sched} ms")
        _speak(code, text)
        root.after(sched, lambda: _show_tip(root))

    def speak_and_show_exact():
        code = current_lang_code()
        text = (line_var.get() or "").strip()
        msw, mn, cu, *_ = _vals()
        base = _estimate_ms(text, msw, mn, cu)
        status.config(text=f"Exact: schedule at base={base} ms")
        _speak(code, text)
        root.after(base, lambda: _show_tip(root))

    tk.Button(btn_row, text="Speak & Show Tip (estimated)",
              command=speak_and_show_estimated,
              bg="#5a4fcf", fg="white", activebackground="#6a5df0",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    tk.Button(btn_row, text="Speak & Show Tip (exact)",
              command=speak_and_show_exact,
              bg="#5a4fcf", fg="white", activebackground="#6a5df0",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    root.mainloop()

if __name__ == "__main__":
    main()
