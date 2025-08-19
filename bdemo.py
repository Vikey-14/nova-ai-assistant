# bdemo.py — VISUAL DEMO (animated stars + real Nova + music + confetti + voice gate)

import tkinter as tk
import utils
import time
import threading

# Optional helpers (fall back cleanly if not present)
try:
    from birthday_present import get_birthday_poem
except Exception:
    get_birthday_poem = None
try:
    from memory_handler import load_from_memory
except Exception:
    load_from_memory = lambda *_a, **_k: None

try:
    import birthday_manager as bm  # starfield, music, images, confetti
except Exception:
    bm = None

W, H = 520, 380
BG = "#1a103d"

# ---- Feathered avatar helper (bdemo-only; safe fallback if Pillow missing) ----
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk
except Exception:
    Image = None  # we’ll fall back to bm._circular_photo if Pillow isn’t available

def _feathered_avatar(
    path,
    size=(84, 84),
    *,
    feather_px=12,
    halo_px=10,
    halo_color="#8b7bff",
    halo_alpha=110,
    y_bias_px=2,
    overscan=1.05,
    pad_px=2,              # NEW: keep a transparent border so no edge shows
    halo_soften_px=1.5     # NEW: slight blur so halo has no hard edge
):
    """
    Smooth circular crop with a soft purple halo.
    pad_px ensures the PNG keeps a fully transparent frame, avoiding straight edges.
    y_bias_px nudges the mask upward a touch so the bottom rounds/merges better.
    """
    if Image is None:
        raise RuntimeError("Pillow not available")

    # Resolve relative path next to this file so it doesn't fail from cwd
    try:
        import os
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(__file__), path)
    except Exception:
        pass

    w, h = size
    im = Image.open(path).convert("RGBA")

    # Slight zoom + fit to trim hard corners cleanly
    im = ImageOps.fit(im, (int(w * overscan), int(h * overscan)), method=Image.LANCZOS, centering=(0.5, 0.5))
    im = ImageOps.fit(im, (w, h), method=Image.LANCZOS, centering=(0.5, 0.5))

    # High-res anti-aliased circular mask with small inward pad
    AA = 4
    mw, mh = w * AA, h * AA
    mask = Image.new("L", (mw, mh), 0)
    draw = ImageDraw.Draw(mask)

    cx, cy = mw // 2, mh // 2 - int(y_bias_px * AA)
    r = int(min(mw, mh) / 2 - (feather_px + pad_px) * AA)  # inset by feather + pad

    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_px * AA * 0.9))
    mask = mask.resize((w, h), Image.LANCZOS)
    im.putalpha(mask)

    # Build a slightly larger canvas for a soft halo that does NOT touch edges
    if halo_px > 0 and halo_alpha > 0:
        halo_w, halo_h = w + 2 * halo_px, h + 2 * halo_px
        out = Image.new("RGBA", (halo_w, halo_h), (0, 0, 0, 0))
        halo = Image.new("RGBA", (halo_w, halo_h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)

        # Inset the halo ellipse so a transparent frame remains
        inset = pad_px + 2
        rgb = tuple(int(halo_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (int(halo_alpha),)
        hd.ellipse((inset, inset, halo_w - inset - 1, halo_h - inset - 1), fill=rgb)

        if halo_soften_px > 0:
            halo = halo.filter(ImageFilter.GaussianBlur(halo_soften_px))

        out.alpha_composite(halo, (0, 0))
        out.alpha_composite(im, (halo_px, halo_px))
        im = out

    return ImageTk.PhotoImage(im)


# ---------------- Common helpers ----------------
def mk_top(title: str):
    win = tk.Toplevel()
    win.title(title)
    win.configure(bg=BG)
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass
    win.geometry(f"{W}x{H}")
    cvs = tk.Canvas(win, width=W, height=H, bg=BG, highlightthickness=0, bd=0)
    cvs.pack(fill="both", expand=True)
    return win, cvs

def style_btn(b: tk.Button, variant="primary"):
    colors = {
        "primary":  ("#5a4fcf", "white"),
        "raspberry":("#d16576", "white"),
        "indigo":   ("#4a3fc5", "white"),
    }
    bg, fg = colors.get(variant, colors["primary"])
    b.configure(bg=bg, fg=fg, relief="flat", padx=14, pady=8,
                cursor="hand2", font=("Segoe UI", 10, "bold"),
                activeforeground="white")
    base = b["bg"]
    b.bind("<Enter>", lambda e: b.config(bg="#b084ff"))
    b.bind("<Leave>", lambda e: b.config(bg=base))

def _play(asset: str, loop=False):
    if bm and hasattr(bm, "_play_music"):
        try:
            bm._play_music(asset, loop=loop)
        except Exception:
            pass

def _stop():
    if bm and hasattr(bm, "_stop_music"):
        try:
            bm._stop_music()
        except Exception:
            pass

def _use_starry(win, face_size=(64,64), face_y=84, orbit_radius=8):
    """Install manager's animated star canvas + real Nova image."""
    if not bm:
        # fallback plain canvas
        for child in win.winfo_children():
            if isinstance(child, tk.Canvas):
                return child, {}, None
        return tk.Canvas(win, width=W, height=H, bg=BG, highlightthickness=0), {}, None

    # replace plain canvas with starry
    for child in win.winfo_children():
        if isinstance(child, tk.Canvas):
            try: child.destroy()
            except Exception: pass
    cvs, layers = bm._make_starry_canvas(win, W, H)

    face_id = None
    try:
        imgTk = None

        # 1) Manager helper, if present
        if hasattr(bm, "_circular_photo_feathered"):
            try:
                imgTk = bm._circular_photo_feathered(
                    "nova_birthday_face.png", face_size,
                    feather_px=12, halo_px=10, halo_color="#8b7bff",
                    halo_alpha=110, y_bias_px=2, overscan=1.05
                )
            except Exception:
                imgTk = None

        # 2) Local feathered helper (adds transparent border + inset halo)
        if imgTk is None and Image is not None:
            try:
                imgTk = _feathered_avatar(
                    "nova_birthday_face.png", face_size,
                    feather_px=12, halo_px=10, halo_color="#8b7bff",
                    halo_alpha=110, y_bias_px=2, overscan=1.05,
                    pad_px=3, halo_soften_px=2
                )
            except Exception:
                imgTk = None

        # 3) Final fallback: original circular crop
        if imgTk is None and hasattr(bm, "_circular_photo"):
            try:
                imgTk = bm._circular_photo("nova_birthday_face.png", face_size)
            except Exception:
                imgTk = None

        if imgTk is not None:
            face_id = cvs.create_image(W // 2, face_y, image=imgTk, anchor="center")
            # keep references to avoid GC
            refs = getattr(win, "_img_refs", [])
            refs.append(imgTk)
            win._img_refs = refs
    except Exception:
        face_id = None

    try:
        bm._animate_stars_and_orbit(cvs, layers, face_id, W // 2, face_y, orbit_radius)
    except Exception:
        pass

    return cvs, layers, face_id


# ---------------- Voice gate (per-language, per-line timing; NO UI CHANGES) ----------------
def _estimate_ms(line: str, mpw: int, floor_ms: int, cushion_ms: int) -> int:
    """Duration estimate for non-blocking TTS."""
    words = max(1, len(line.split()))
    return max(floor_ms, words * mpw + cushion_ms)

def _fire_and_forget_speak(line: str):
    """Start Nova's voice immediately. Try async hooks; else run speak() on a thread."""
    try:
        if bm and hasattr(bm, "_speak_line_async"):
            bm._speak_line_async(line)  # returns immediately
            return
    except Exception:
        pass
    try:
        if hasattr(utils, "speak_async"):
            utils.speak_async(line)     # returns immediately
            return
    except Exception:
        pass
    # fallback: run blocking speak on a background thread
    try:
        if hasattr(utils, "speak"):
            threading.Thread(target=lambda: utils.speak(line), daemon=True).start()
    except Exception:
        pass

def _speak_then_show_exact(line: str, extra_hold_ms: int, show_fn, *args, **kwargs):
    """
    For blocking TTS: speak, then (optionally wait extra_hold_ms) and show popup.
    """
    def run():
        try:
            if hasattr(utils, "speak"):
                utils.speak(line)  # usually blocking
        except Exception:
            pass
        if extra_hold_ms > 0:
            time.sleep(max(0, extra_hold_ms) / 1000.0)
        root.after(0, lambda: show_fn(*args, **kwargs))
    threading.Thread(target=run, daemon=True).start()

def _speak_then_show_estimated(line: str, base_ms: int,
                               early_shift_ms: int,
                               hard_gate_ms: int,
                               extra_hold_ms: int,
                               show_fn, *args, **kwargs):
    """
    For non-blocking TTS: fire voice now, schedule popup by estimate.
    """
    _fire_and_forget_speak(line)
    delay = max(0, base_ms - max(0, early_shift_ms))
    if hard_gate_ms:
        delay = max(delay, hard_gate_ms)
    delay += max(0, extra_hold_ms)
    root.after(delay, lambda: show_fn(*args, **kwargs))

# 1) Lines Nova will say
VOICE_LINES = {
    "today": {
        "en": "Surprise! It’s your special day. Happy Birthday!",
        "hi": "सरप्राइज़! आज आपका जन्मदिन है। जन्मदिन की शुभकामनाएँ!",
        "de": "Überraschung! Heute ist dein Geburtstag. Alles Gute zum Geburtstag!",
        "fr": "Surprise ! C'est ton anniversaire. Joyeux anniversaire !",
        "es": "¡Sorpresa! Hoy es tu cumpleaños. ¡Feliz cumpleaños!"
    },
    "belated": {
        "en": "A little late, but with all my heart — Happy Belated Birthday!",
        "hi": "थोड़ा देर से सही, दिल से — जन्मदिन की ढेर सारी शुभकामनाएँ!",
        "de": "Etwas spät, aber von Herzen – alles Gute nachträglich zum Geburtstag!",
        "fr": "Avec un peu de retard, mais de tout cœur — joyeux anniversaire en retard !",
        "es": "¡Un poco tarde, pero con todo mi corazón! ¡Feliz cumpleaños atrasado!"
    }
}

def _cfg(use_estimate, mpw, min_ms, cushion, early_shift=0, hard_gate=0, extra_hold=0):
    return dict(
        use_estimate=use_estimate,
        mpw=mpw, min_ms=min_ms, cushion=cushion,
        early_shift=early_shift, hard_gate=hard_gate, extra_hold=extra_hold
    )

TIMING = {
    "today": {
        "en": _cfg(True, 300, 3800, 200, 0, 3800, 0),
        "hi": _cfg(True, 440, 6000, 320, 0, 6000, 150),
        "de": _cfg(True, 340, 4600, 240, 0, 4600, 1100),
        "fr": _cfg(True, 300, 3800, 200, 0, 3800, 1100),
        "es": _cfg(True, 280, 3600, 180, 0, 3600, 800),
    },
    "belated": {
        "en": _cfg(True, 260, 3150, 120, 0, 0, 0),
        "hi": _cfg(True, 400, 5200, 280, 0, 5200, 260),
        "de": _cfg(True, 300, 4000, 180, 0, 4000, 800),
        "fr": _cfg(True, 260, 3300, 140, 0, 0, 0),
        "es": _cfg(True, 260, 3200, 140, 0, 0, 1200),
    }
}

def _current_lang():
    return getattr(utils, "selected_language", "en") or "en"

def _pick(kind: str):
    lang = _current_lang()
    lines = VOICE_LINES[kind]
    cfgs  = TIMING[kind]
    line = lines.get(lang, lines["en"])
    cfg  = cfgs.get(lang, cfgs["en"])
    return line, cfg

# ---------- start functions (language-aware; visuals untouched) ----------
def start_celebration_today():
    line, cfg = _pick("today")
    if cfg["use_estimate"]:
        base = _estimate_ms(line, cfg["mpw"], cfg["min_ms"], cfg["cushion"])
        _speak_then_show_estimated(
            line, base,
            cfg["early_shift"], cfg["hard_gate"], cfg["extra_hold"],
            demo_celebration_popup, False
        )
    else:
        _speak_then_show_exact(line, cfg["extra_hold"], demo_celebration_popup, False)

def start_celebration_belated():
    line, cfg = _pick("belated")
    if cfg["use_estimate"]:
        base = _estimate_ms(line, cfg["mpw"], cfg["min_ms"], cfg["cushion"])
        _speak_then_show_estimated(
            line, base,
            cfg["early_shift"], cfg["hard_gate"], cfg["extra_hold"],
            demo_celebration_popup, True
        )
    else:
        _speak_then_show_exact(line, cfg["extra_hold"], demo_celebration_popup, True)

# ---------------- Poem overlay (animated stars + oval bubble + bigger/bold text) ----------------
POEM_CENTER_Y       = 210
POEM_RADIUS_X       = 244
POEM_RADIUS_Y       = 82
POEM_TEXT_INNER_PAD = 12
CTA_MARGIN_BOTTOM   = 48

def demo_poem_overlay(parent_popup=None, parent_canvas=None):
    win, cvs = mk_top("🎁 Your Birthday Poem")
    cvs, layers, face_id = _use_starry(win, face_size=(70,70), face_y=72, orbit_radius=8)

    cx = W // 2
    left   = cx - POEM_RADIUS_X
    right  = cx + POEM_RADIUS_X
    top    = POEM_CENTER_Y - POEM_RADIUS_Y
    bottom = POEM_CENTER_Y + POEM_RADIUS_Y

    cvs.create_oval(left, top, right, bottom, fill="#241a50", outline="")

    try:
        name = load_from_memory("name") or "Trainer"
    except Exception:
        name = "Trainer"

    poem = None
    if get_birthday_poem:
        try:
            poem = get_birthday_poem(name=name)
        except Exception:
            poem = None
    if not poem:
        poem = ("Nova remembers your love for bhasha,\n"
                "It shines through like a guiding star.\n"
                "On your birthday, Trainer, we celebrate you,\n"
                "From galaxies near and worlds afar.")

    text_wrap = (POEM_RADIUS_X - POEM_TEXT_INNER_PAD) * 2
    cvs.create_text(
        cx, POEM_CENTER_Y,
        text=poem,
        font=("Segoe UI", 11, "bold"),
        fill="#e8e6ff",
        width=text_wrap,
        justify="left",
    )

    def close_everything():
        if bm and hasattr(bm, "_mega_confetti_on"):
            try:
                bm._mega_confetti_on(win)
                if parent_popup and parent_popup.winfo_exists():
                    bm._mega_confetti_on(parent_popup)
            except Exception:
                pass
            win.after(1300, lambda: (win.destroy() if win.winfo_exists() else None))
            if parent_popup and parent_popup.winfo_exists():
                parent_popup.after(1300, lambda: (parent_popup.destroy()
                                                  if parent_popup.winfo_exists() else None))
        else:
            win.destroy()
            if parent_popup and parent_popup.winfo_exists():
                parent_popup.destroy()
        _stop()

    btn = tk.Button(win, text="Hope you liked the gesture ✨", command=close_everything)
    style_btn(btn, "raspberry")
    cvs.create_window(cx, H - CTA_MARGIN_BOTTOM, window=btn)

    win.bind("<Return>", lambda e: close_everything())
    win.bind("<Escape>", lambda e: close_everything())

# ---------------- Celebration popup (animated stars + compact layout + music + confetti) ----------------
LOGO_FACE_SIZE = (84, 84)
LOGO_Y         = 96
HEADING_Y      = 200

BTN_SPREAD     = 90
BTN_X_SHIFT    = 10
BTN_Y_MARGIN   = 105

def demo_celebration_popup(belated: bool = False):
    pop, _ = mk_top("🎉 Happy Birthday!")
    cvs, layers, face_id = _use_starry(pop, face_size=LOGO_FACE_SIZE, face_y=LOGO_Y, orbit_radius=8)

    _play("pokemon_center_birthday.mp3", loop=True)

    heading_text = "Happy Birthday, Trainer! 🎉"
    cvs.create_text(W // 2, HEADING_Y, text=heading_text, font=("Segoe UI", 18, "bold"), fill="#e8e6ff")

    def on_reveal():
        demo_poem_overlay(parent_popup=pop, parent_canvas=cvs)

    def on_thanks():
        if bm and hasattr(bm, "_mega_confetti_on"):
            try: bm._mega_confetti_on(pop)
            except Exception: pass
            pop.after(1300, lambda: (pop.destroy() if pop.winfo_exists() else None))
        else:
            pop.destroy()
        _stop()

    btn_reveal = tk.Button(pop, text="🎁 Reveal my surprise", command=on_reveal); style_btn(btn_reveal, "indigo")
    btn_thanks = tk.Button(pop, text="Thanks, Nova!", command=on_thanks);         style_btn(btn_thanks, "raspberry")

    cvs.create_window(W // 2 - BTN_SPREAD + BTN_X_SHIFT, H - BTN_Y_MARGIN, window=btn_reveal)
    cvs.create_window(W // 2 + BTN_SPREAD + BTN_X_SHIFT, H - BTN_Y_MARGIN, window=btn_thanks)

    pop.bind("<Escape>", lambda e: on_thanks())
    pop.bind("<Return>", lambda e: on_reveal())

# ---------------- Ask Birthday popup (animated stars + real Nova + chime + confetti) ----------------
def demo_ask_popup():
    win, cvs = mk_top("📅 What's Your Birthdate?")
    cvs, layers, face_id = _use_starry(win, face_size=(58,58), face_y=76, orbit_radius=6)

    _play("birthday_chime.mp3", loop=False)

    cvs.create_text(W//2, 148, text="When is your birthday?",
                    font=("Segoe UI", 14, "bold"), fill="#e8e6ff")

    entry = tk.Entry(win, width=22, justify="center")
    entry.insert(0, "August 18")
    cvs.create_window(W//2, 180, window=entry, width=240, height=26)

    cvs.create_text(W//2, 208, text="e.g., August 5 or 5th Aug",
                    font=("Segoe UI", 9), fill="#c9cfff")

    def on_save():
        if bm and hasattr(bm, "_confetti_burst_and_close"):
            try: bm._confetti_burst_and_close(win)
            except Exception:
                try: win.destroy()
                except Exception: pass
        else:
            try: win.destroy()
            except Exception: pass
        _stop()

    def on_later():
        if bm and hasattr(bm, "_confetti_burst_and_close"):
            try: bm._confetti_burst_and_close(win)
            except Exception:
                try: win.destroy()
                except Exception: pass
        else:
            try: win.destroy()
            except Exception: pass
        _stop()

    btn_save  = tk.Button(win, text="🎂 Save Birthday", command=on_save);  style_btn(btn_save, "raspberry")
    btn_later = tk.Button(win, text="Remind Me Later", command=on_later);  style_btn(btn_later, "indigo")

    cvs.create_window(W//2 - 90, H - 68, window=btn_save)
    cvs.create_window(W//2 + 90, H - 68, window=btn_later)

    win.bind("<Return>", lambda e: on_save())
    win.bind("<Escape>",  lambda e: on_later())

# ---------------- Hub ----------------
root = tk.Tk()
root.title("Nova Birthday Popups — Visual Demo")
root.configure(bg="#0f0a2a")
root.geometry("560x400")
root.resizable(False, False)

title = tk.Label(root, text="Nova Birthday Popups — Visual Demo",
                 font=("Segoe UI", 14, "bold"), fg="#e8e6ff", bg="#0f0a2a")
title.pack(pady=(14, 8))

# Language selector
LANGS = [("English","en"), ("हिन्दी","hi"), ("Deutsch","de"), ("Français","fr"), ("Español","es")]
lang_frame = tk.Frame(root, bg="#0f0a2a"); lang_frame.pack(pady=(4, 10))
tk.Label(lang_frame, text="Preview voice language:",
         font=("Segoe UI", 10), fg="#c9cfff", bg="#0f0a2a").pack(side="left", padx=(0,8))
lang_var = tk.StringVar(value=getattr(utils, "selected_language", "en"))
def on_lang_change(*_): setattr(utils, "selected_language", lang_var.get())
lang_menu = tk.OptionMenu(lang_frame, lang_var, *[code for _, code in LANGS])
lang_menu.configure(bg="#5a4fcf", fg="white", activeforeground="white",
                    activebackground="#b084ff", relief="flat", highlightthickness=0, padx=8)
lang_menu["menu"].configure(bg="#1a103d", fg="#e8e6ff", activebackground="#5a4fcf")
lang_menu.pack(side="left")
lang_var.trace_add("write", on_lang_change)

# Demo buttons
def hub_style(b): style_btn(b, "primary")
grid = tk.Frame(root, bg="#0f0a2a"); grid.pack(pady=6)
b1 = tk.Button(grid, text="Ask Birthday Popup",      command=demo_ask_popup);            hub_style(b1)
b2 = tk.Button(grid, text="Celebration (Today) — compact", command=start_celebration_today); hub_style(b2)
b3 = tk.Button(grid, text="Celebration (Belated)",   command=start_celebration_belated); hub_style(b3)
b4 = tk.Button(grid, text="Test Poem Overlay",       command=demo_poem_overlay);         hub_style(b4)

b1.grid(row=0, column=0, padx=8, pady=6)
b2.grid(row=0, column=1, padx=8, pady=6)
b3.grid(row=1, column=0, padx=8, pady=6)
b4.grid(row=1, column=1, padx=8, pady=6)

# Footer
footer = tk.Frame(root, bg="#0f0a2a"); footer.pack(pady=(8,10))
btn_stop  = tk.Button(footer, text="⏹ Stop Music",     command=_stop);      style_btn(btn_stop)
def close_all():
    for w in list(root.winfo_children()):
        if isinstance(w, tk.Toplevel):
            try: w.destroy()
            except Exception: pass
    _stop()
btn_close = tk.Button(footer, text="✖ Close All Popups", command=close_all); style_btn(btn_close)
btn_stop.pack(side="left", padx=8)
btn_close.pack(side="left", padx=8)

root.bind("<Escape>", lambda e: close_all())
root.after(50, lambda: setattr(utils, "selected_language", lang_var.get()))
root.mainloop()
