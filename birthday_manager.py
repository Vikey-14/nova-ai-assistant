# birthday_manager.py
# -*- coding: utf-8 -*-

import datetime
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
import os, random, time, math, re

# pygame is optional at runtime
try:
    import pygame
except Exception:
    pygame = None  # degrade gracefully

from memory_handler import load_from_memory, save_to_memory
from birthday_present import get_birthday_poem
from utils import pkg_path
import utils  # for selected_language, logger, settings

# -------------------------------
# TK helpers (keep all UI on main thread + no corner flash)
# -------------------------------
def _root():
    """Return the default Tk root if available; otherwise try to create a hidden one."""
    r = tk._get_default_root()
    if r is None:
        try:
            r = tk.Tk()
            r.withdraw()
            try:
                r.iconbitmap(utils.resource_path("nova_icon_big.ico"))
            except Exception:
                pass
        except Exception:
            return None
    return r

def _tk_after(ms, fn, *args, **kwargs):
    r = _root()
    if r:
        try:
            r.after(ms, lambda: fn(*args, **kwargs))
            return
        except Exception:
            pass
    # fallback (best effort)
    try:
        fn(*args, **kwargs)
    except Exception:
        pass

def _center_and_show(win: tk.Toplevel):
    """Prevent top-left flash: withdraw → layout → center → deiconify."""
    try:
        win.withdraw()
    except Exception:
        pass
    try:
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.deiconify()
        win.lift()
        win.focus_force()
    except Exception:
        pass

# -------------------------------
# Gating: run *after* Nova window is visible and greeting line is done
# -------------------------------
def _after_greeting(run_fn, *, extra_delay_ms: int = 1000, poll_ms: int = 150, timeout_ms: int = 20000):
    """
    Calls run_fn after the main Tk window is visible (not withdrawn/iconic)
    and waits a further extra_delay_ms so the "Hello… how can I help you today?"
    greeting can print first.
    """
    start = time.time()

    def _visible() -> bool:
        r = _root()
        if not (r and r.winfo_exists()):
            return False
        try:
            st = r.state()
            return r.winfo_viewable() and st not in ("withdrawn", "iconic")
        except Exception:
            return False

    def _poll():
        if _visible():
            _tk_after(extra_delay_ms, run_fn)
            return
        if (time.time() - start) * 1000 >= timeout_ms:
            _tk_after(extra_delay_ms, run_fn)
            return
        _tk_after(poll_ms, _poll)

    _poll()

# -------------------------------
# Audio helpers (safe)
# -------------------------------
def _play_music(asset_name: str, loop: bool = False):
    if not pygame:
        return
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(str(pkg_path("assets", asset_name)))
        pygame.mixer.music.play(loops=-1 if loop else 0)
    except Exception:
        pass

def _stop_music():
    if not pygame:
        return
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

# -------------------------------
# Confetti helpers
# -------------------------------
def _confetti_burst_and_close(popup: tk.Toplevel, duration_ms: int = 700, count: int = 120):
    """Small burst used by the ask-birthday popup."""
    try:
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        overlay = tk.Canvas(popup, width=w, height=h, bg="#1a103d", highlightthickness=0, bd=0)
        overlay.place(x=0, y=0)

        dots = []
        colors = ["#ffd1dc", "#ffe6a7", "#b5e9ff", "#c8ffe0", "#fffacd", "#ffccff", "#b0e0e6"]
        for _ in range(count):
            x = w/2; y = h/3
            rdot = random.randint(2, 4)
            dot = overlay.create_oval(x, y, x+rdot, y+rdot, fill=random.choice(colors), outline="")
            vx = random.uniform(-4.0, 4.0)
            vy = random.uniform(-6.0, -2.0)
            dots.append([dot, vx, vy, 0])

        start = int(time.time() * 1000)

        def step():
            now = int(time.time() * 1000)
            alive = now - start < duration_ms
            for item in dots:
                dot, vx, vy, age = item
                vy += 0.22
                overlay.move(dot, vx, vy)
                item[2] = vy; item[3] = age + 1
            if alive and popup.winfo_exists():
                popup.after(16, step)
            else:
                try: popup.destroy()
                except Exception: pass

        step()
    except Exception:
        try: popup.destroy()
        except Exception: pass

def _mega_confetti_on(popup: tk.Toplevel, duration_ms: int = 1200, count: int = 520):
    """Large burst used when closing both the celebration and poem popups."""
    if not popup or not popup.winfo_exists():
        return
    try:
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        overlay = tk.Canvas(popup, width=w, height=h, bg="#1a103d", highlightthickness=0, bd=0)
        overlay.place(x=0, y=0)

        dots = []
        colors = ["#ffd1dc", "#ffe6a7", "#b5e9ff", "#c8ffe0", "#fffacd", "#ffccff", "#b0e0e6"]
        for _ in range(count):
            x = w/2; y = h/3
            rdot = random.randint(2, 4)
            dot = overlay.create_oval(x, y, x+rdot, y+rdot, fill=random.choice(colors), outline="")
            vx = random.uniform(-5.0, 5.0)
            vy = random.uniform(-7.0, -3.0)
            dots.append([dot, vx, vy, 0])

        start = int(time.time() * 1000)

        def step():
            now = int(time.time() * 1000)
            alive = now - start < duration_ms
            for item in dots:
                dot, vx, vy, age = item
                vy += 0.20
                overlay.move(dot, vx, vy)
                item[2] = vy; item[3] = age + 1
            if alive and popup.winfo_exists():
                popup.after(16, step)
            else:
                try: overlay.destroy()
                except Exception: pass

        step()
    except Exception:
        pass

# -------------------------------
# Starry canvas + image helpers
# -------------------------------
def _make_starry_canvas(win: tk.Toplevel, width: int, height: int):
    """Full-window starry canvas."""
    cvs = tk.Canvas(win, width=width, height=height, bg="#1a103d", highlightthickness=0, bd=0)
    cvs.pack(fill="both", expand=False)
    star_layers = {1: [], 2: [], 3: []}
    for layer in star_layers:
        for _ in range(28 if layer == 1 else 18):
            x = random.randint(0, width); y = random.randint(0, height)
            size = layer  # 1..3
            star = cvs.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
            star_layers[layer].append(star)
    return cvs, star_layers

def _animate_stars_and_orbit(cvs: tk.Canvas, layers: dict, face_id, cx: int, cy: int, r_orbit: int):
    """Drift stars and orbit the face image."""
    def _anim():
        _anim.t = getattr(_anim, "t", 0) + 2
        # drift stars
        w = int(cvs.winfo_width() or 0) or int(cvs["width"])
        for layer, stars in layers.items():
            dx = 0.25 * layer
            for s in stars:
                cvs.move(s, dx, 0)
                x0, y0, x1, y1 = cvs.coords(s)
                if x0 > w:
                    cvs.move(s, -w - (x1 - x0), 0)
        # tiny orbit
        if face_id:
            rad = math.radians(_anim.t)
            cvs.coords(face_id, cx + r_orbit * math.cos(rad), cy + r_orbit * math.sin(rad))
        try:
            cvs.after(50, _anim)
        except Exception:
            pass
    _anim()

def _circular_photo(asset_name: str, size_xy: tuple[int, int]) -> ImageTk.PhotoImage:
    """Load an image and return a circular-masked PhotoImage (to avoid square backdrop)."""
    img = Image.open(str(pkg_path("assets", asset_name))).convert("RGBA").resize(size_xy, Image.LANCZOS)
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, w, h), fill=255)
    img.putalpha(mask)
    return ImageTk.PhotoImage(img)

# -------------------------------
# Date normalization & aliases
# -------------------------------
_MONTH_ALIASES = {
    "jan": "january", "jan.": "january", "january": "january",
    "feb": "february", "feb.": "february", "february": "february",
    "mar": "march", "mar.": "march", "march": "march",
    "apr": "april", "apr.": "april", "april": "april",
    "may": "may",
    "jun": "june", "jun.": "june", "june": "june",
    "jul": "july", "jul.": "july", "july": "july",
    "aug": "august", "aug.": "august", "august": "august",
    "sep": "september", "sep.": "september", "sept": "september", "sept.": "september", "september": "september",
    "oct": "october", "oct.": "october", "october": "october",
    "nov": "november", "nov.": "november", "november": "november",
    "dec": "december", "dec.": "december", "december": "december",
}

def _normalize_date_text(s: str) -> str:
    """Lowercase, remove ordinals/fillers, normalize month aliases, collapse punctuation/spaces."""
    s0 = (s or "").strip().lower()
    s0 = s0.replace(",", " ").replace("/", " ").replace("-", " ")
    s0 = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", s0)
    s0 = re.sub(r"\bof\b", " ", s0)
    for alias, canon in _MONTH_ALIASES.items():
        s0 = re.sub(rf"\b{re.escape(alias)}\b", canon, s0)
    s0 = re.sub(r"\s+", " ", s0).strip()
    return s0

# -------------------------------
# Boot check and deferred prompts (after greeting)
# -------------------------------
def check_and_prompt_birthday():
    # Use multi-lang speech from utils, and remember settings
    from utils import _speak_multilang, load_settings, save_settings, logger

    settings = load_settings()
    settings["boot_count"] = settings.get("boot_count", 0) + 1
    boot = settings["boot_count"]
    save_settings(settings)  # persist increment

    birthday = load_from_memory("birthday")  # "dd-mm"
    asked_before = settings.get("birthday_asked", False)
    final_prompt_shown = settings.get("birthday_final_prompt_shown", False)

    # Cross-session “show on next boot” persistence (for same-day 5-min fallback)
    show_next_boot = settings.get("birthday_show_next_boot", False)
    show_next_boot_date = settings.get("birthday_show_next_boot_date", "")

    # Per-year guard: ensure we only celebrate once per year (normal OR belated)
    celebrated_year = settings.get("birthday_celebrated_year")

    # Day string & date objects
    today_str = datetime.datetime.now().strftime("%d-%m")
    today_date = datetime.date.today()
    this_year = today_date.year

    # --- If today is the user's birthday, plan the celebration ---
    if birthday:
        try:
            d, m = map(int, birthday.split("-"))
            bday_this_year = datetime.date(this_year, m, d)
        except Exception:
            bday_this_year = None

        # Reset once-per-day marker so same-day popup doesn’t replay
        flags_day = settings.get("birthday_flags_day", "")
        if flags_day != today_str:
            settings["birthday_flags_day"] = today_str
            settings["birthday_celebration_scheduled"] = False
            save_settings(settings)

        if bday_this_year:
            # ---- CASE A: Today IS birthday ----
            if today_date == bday_this_year:
                def _celebrate_now():
                    _tk_after(0, show_birthday_celebration_popup, False)  # belated=False

                # Same-day surprise carried from previous session
                if show_next_boot and show_next_boot_date == today_str:
                    logger.info("🎂 Pending same-day celebration from last session → showing after greeting")
                    _after_greeting(_celebrate_now, extra_delay_ms=10000)
                    settings["birthday_show_next_boot"] = False
                    settings["birthday_show_next_boot_date"] = ""
                    settings["birthday_celebration_scheduled"] = True
                    settings["birthday_celebrated_year"] = this_year
                    save_settings(settings)

                # Normal day-of logic (earlier-saved birthdays)
                elif not settings.get("birthday_celebration_scheduled", False):
                    logger.info("🎂 Birthday today — showing celebration after greeting (10s delay)")
                    _after_greeting(_celebrate_now, extra_delay_ms=10000)
                    settings["birthday_celebration_scheduled"] = True
                    settings["birthday_celebrated_year"] = this_year
                    save_settings(settings)

            # ---- CASE B: Belated window (1–7 days after birthday) ----
            else:
                if celebrated_year != this_year and today_date > bday_this_year:
                    delta = (today_date - bday_this_year).days
                    if 1 <= delta <= 7:
                        def _celebrate_belated():
                            _tk_after(0, show_birthday_celebration_popup, True)  # belated=True
                        logger.info(f"🎈 Belated birthday window ({delta} days) — showing after greeting (10s delay)")
                        _after_greeting(_celebrate_belated, extra_delay_ms=10000)
                        settings["birthday_celebration_scheduled"] = True
                        settings["birthday_celebrated_year"] = this_year
                        settings["birthday_show_next_boot"] = False
                        settings["birthday_show_next_boot_date"] = ""
                        save_settings(settings)

    # --- Ask for birthday on boot #3 and #10, after greeting (10s delay) ---
    if not birthday:
        def _ask_now_first():
            _speak_multilang(
                "Hey, I’d love to surprise you someday — but I need one tiny clue first. Would you like to tell me your birthday?",
                hi="हाय! मैं किसी दिन आपको सरप्राइज़ देना चाहूँगी — पर उसके लिए आपकी जन्मतिथि चाहिए। क्या आप मुझे अपना जन्मदिन बताना चाहेंगे?",
                de="Hey! Ich würde dich gern irgendwann überraschen – dafür brauche ich nur dein Geburtsdatum. Möchtest du es mir sagen?",
                fr="Coucou ! J’aimerais te préparer une surprise un jour — dis-moi juste ta date d’anniversaire. Tu veux me la donner ?",
                es="¡Hola! Me encantaría sorprenderte algún día — pero necesito tu cumpleaños. ¿Quieres decírmelo?"
            )
            _tk_after(0, show_birthday_input_popup)

        def _ask_now_final():
            _speak_multilang(
                "I’m still wondering when your birthday is! Tell me now so I can plan something special someday?",
                hi="मैं अब भी आपके जन्मदिन के बारे में सोच रही हूँ! क्या आप अभी बता देंगे ताकि मैं कभी आपके लिए कुछ खास प्लान कर सकूँ?",
                de="Ich frage mich immer noch, wann du Geburtstag hast! Sag es mir jetzt, damit ich später etwas Besonderes planen kann?",
                fr="Je me demande toujours quand est ton anniversaire ! Dis-le moi pour que je puisse préparer quelque chose un jour.",
                es="¡Aún me pregunto cuándo es tu cumpleaños! Dímelo ahora para poder preparar algo especial algún día."
            )
            _tk_after(0, show_birthday_input_popup)

        settings = utils.load_settings()
        boot = settings.get("boot_count", 0)
        asked_before = settings.get("birthday_asked", False)
        final_prompt_shown = settings.get("birthday_final_prompt_shown", False)

        if boot == 3 and not asked_before:
            _after_greeting(_ask_now_first, extra_delay_ms=10000)
            settings["birthday_asked"] = True
            utils.save_settings(settings)

        elif boot == 10 and not final_prompt_shown:
            _after_greeting(_ask_now_final, extra_delay_ms=10000)
            settings["birthday_final_prompt_shown"] = True
            utils.save_settings(settings)

# -------------------------------
# Birthday entry popup — UPDATED: full starfield + lower Nova logo
# -------------------------------
def show_birthday_input_popup():
    from utils import load_settings, save_settings, logger, _speak_multilang
    import dateparser

    r = _root()
    if not r:
        return

    # Soft chime (best effort)
    _play_music("birthday_chime.mp3", loop=False)

    # --- Window ---
    W, H = 480, 360
    popup = tk.Toplevel(master=r)
    try:
        popup.iconbitmap(utils.resource_path("nova_icon_big.ico"))
    except Exception:
        pass

    popup.title("🎂 What's Your Birthdate?")
    popup.configure(bg="#1a103d")
    popup.resizable(False, False)
    try:
        popup.attributes("-topmost", True)
    except Exception:
        pass
    popup.geometry(f"{W}x{H}")

    # === FULL-WINDOW starfield (was header-only) ===
    canvas, layers = _make_starry_canvas(popup, W, H)

    # === Nova logo a little lower (y=96) with gentle orbit ===
    face_id = None
    try:
        img_path = str(pkg_path("assets", "nova_face_glow.png"))
        img = Image.open(img_path).resize((84, 84))
        face = ImageTk.PhotoImage(img)
        face_id = canvas.create_image(W // 2, 96, image=face)
        popup._ask_face_ref = face  # keep ref
    except Exception:
        pass
    _animate_stars_and_orbit(canvas, layers, face_id, W // 2, 96, 8)

    # --- Form content on the canvas so stars fill the whole popup ---
    canvas.create_text(
        W // 2, 166,
        text="When is your birthday?",
        font=("Segoe UI", 12, "bold"),
        fill="#dcdcff",
        width=W - 40,
        justify="center"
    )

    entry = tk.Entry(popup, font=("Segoe UI", 12), justify="center")
    canvas.create_window(W // 2, 198, window=entry, width=264)
    entry.focus_set()

    hint = tk.Label(
        popup, text="e.g., August 5 or 5th Aug",
        font=("Segoe UI", 10), fg="#9aa0c7", bg="#1a103d"
    )
    canvas.create_window(W // 2, 226, window=hint)

    # button styles (exact palette + hover)
    def style_indigo(btn):
        btn.configure(bg="#5a4fcf", fg="white", relief="flat",
                      padx=14, pady=7, cursor="hand2",
                      font=("Segoe UI", 10, "bold"), activeforeground="white")
        btn.bind("<Enter>", lambda e: btn.config(bg="#b084ff"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#5a4fcf"))

    def style_raspberry(btn):
        btn.configure(bg="#b84b5f", fg="white", relief="flat",
                      padx=14, pady=7, cursor="hand2",
                      font=("Segoe UI", 10), activeforeground="white")
        btn.bind("<Enter>", lambda e: btn.config(bg="#e07b8d"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#b84b5f"))

    def save_birthday():
        import dateparser
        date_text = entry.get().strip()
        # normalize & parse with DMY bias
        norm = _normalize_date_text(date_text)
        parsed = None
        try:
            parsed = dateparser.parse(norm, settings={"DATE_ORDER": "DMY"})
        except Exception:
            parsed = None
        if parsed:
            formatted = parsed.strftime("%d-%m")
            save_to_memory("birthday", formatted)
            s = utils.load_settings()
            s["birthday_asked"] = True
            s["birthday_final_prompt_shown"] = True
            # reset day-of orchestration so today's celebration logic can run
            s["birthday_celebration_scheduled"] = False
            utils.save_settings(s)

            # log & carry-over for same-day
            utils.logger.info(f"🎂 Birthday saved as {formatted}")
            if formatted == datetime.datetime.now().strftime("%d-%m"):
                utils.logger.info("Scheduling 5-minute same-session surprise + next-boot carry-over")

            # Close with confetti (no 'Saved!' dialog)
            _confetti_burst_and_close(popup)

            # Same-session handling: if the saved date is today, schedule 5-minute surprise
            if formatted == datetime.datetime.now().strftime("%d-%m"):
                s2 = utils.load_settings()
                s2["birthday_show_next_boot"] = True
                s2["birthday_show_next_boot_date"] = formatted
                utils.save_settings(s2)

                def _fire():
                    _tk_after(0, show_birthday_celebration_popup, False)  # belated=False
                t = threading.Timer(300, _fire)  # 5 minutes
                t.daemon = True
                t.start()
        else:
            # ❌ Invalid date → speak localized prompt and keep popup open
            utils._speak_multilang(
                "Please enter a valid date, for example 'August 5' or '5 Aug'.",
                hi="कृपया सही तारीख लिखें, जैसे '5 अगस्त' या 'August 5'.",
                de="Bitte gib ein gültiges Datum ein, z. B. „5 Aug“ oder „5. August“.",
                fr="Veuillez entrer une date valide, par ex. « 5 août » ou « 5 Aug ». ",
                es="Introduce una fecha válida, por ejemplo « 5 de agosto » o « 5 Aug »."
            )
            try:
                entry.selection_range(0, tk.END)
                entry.focus_set()
                entry.configure(highlightthickness=1, highlightbackground="#b84b5f")
                popup.after(900, lambda: entry.configure(highlightthickness=0))
            except Exception:
                pass

    def remind_later():
        s = utils.load_settings()
        # If this is before boot 10, snooze to final ask; on/after 10th, never ask again.
        boot = s.get("boot_count", 0)
        s["birthday_asked"] = True
        if boot >= 10:
            s["birthday_final_prompt_shown"] = True
        utils.save_settings(s)
        # Close with confetti
        _confetti_burst_and_close(popup)

    # Put buttons onto the canvas so bg remains starry
    btn_save  = tk.Button(popup, text="🎂 Save Birthday", command=save_birthday)
    btn_later = tk.Button(popup, text="Remind Me Later", command=remind_later)
    style_raspberry(btn_save)
    style_indigo(btn_later)
    canvas.create_window(W // 2 - 95, H - 34, window=btn_save)
    canvas.create_window(W // 2 + 95, H - 34, window=btn_later)

    # shortcuts + close behavior
    popup.bind("<Return>", lambda e: save_birthday())  # Enter = Save
    popup.bind("<Escape>", lambda e: remind_later())   # Esc   = Remind
    popup.protocol("WM_DELETE_WINDOW", remind_later)   # X = Remind (with confetti)

    _center_and_show(popup)

# -------------------------------
# Celebration popup — language-aware TTS timing, music starts with popup
# -------------------------------

# Per-language timing (ported from your demo)
def _cfg(use_estimate, mpw, min_ms, cushion, early_shift=0, hard_gate=0, extra_hold=0):
    return dict(
        use_estimate=use_estimate,
        mpw=mpw, min_ms=min_ms, cushion=cushion,
        early_shift=early_shift, hard_gate=hard_gate, extra_hold=extra_hold
    )

_TIMING = {
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

def _estimate_ms(line: str, mpw: int, floor_ms: int, cushion_ms: int) -> int:
    words = max(1, len((line or "").split()))
    return max(floor_ms, words * mpw + cushion_ms)

def _delay_for_line(kind: str, lang: str, line: str) -> int:
    cfgs = _TIMING.get(kind, _TIMING["today"])
    cfg  = cfgs.get(lang, cfgs["en"])
    if not cfg["use_estimate"]:
        return max(0, cfg.get("extra_hold", 0))
    base = _estimate_ms(line, cfg["mpw"], cfg["min_ms"], cfg["cushion"])
    delay = max(0, base - max(0, cfg["early_shift"]))
    if cfg.get("hard_gate", 0):
        delay = max(delay, cfg["hard_gate"])
    delay += max(0, cfg.get("extra_hold", 0))
    return delay

def show_birthday_celebration_popup(belated: bool = False):
    from utils import _speak_multilang, load_settings, save_settings, logger

    r = _root()
    if not r:
        return

    # Choose localized voice lines (we'll speak these first)
    name = load_from_memory("name") or "Trainer"
    if belated:
        heading_tpl = "Happy Belated Birthday, {name}! 🎉"
        voice = dict(
            en="A little late, but with all my heart — Happy Belated Birthday!",
            hi="थोड़ा देर से सही, दिल से — जन्मदिन की ढेर सारी शुभकामनाएँ!",
            de="Etwas spät, aber von Herzen – alles Gute nachträglich zum Geburtstag!",
            fr="Avec un peu de retard, mais de tout cœur — joyeux anniversaire en retard !",
            es="Un poco tarde, ¡pero con todo mi corazón! ¡Feliz cumpleaños atrasado!"
        )
        kind = "belated"
    else:
        heading_tpl = "Happy Birthday, {name}! 🎉"
        voice = dict(
            en="Surprise! It’s your special day. Happy Birthday!",
            hi="सरप्राइज़! आज आपका जन्मदिन है। जन्मदिन की शुभकामनाएँ!",
            de="Überraschung! Heute ist dein Geburtstag. Alles Gute zum Geburtstag!",
            fr="Surprise ! C'est ton anniversaire. Joyeux anniversaire !",
            es="¡Sorpresa! Hoy es tu cumpleaños. ¡Feliz cumpleaños!"
        )
        kind = "today"

    # Speak now (multilang), then build popup right when the wish line finishes (language-aware)
    chosen_lang = getattr(utils, "selected_language", "en")
    chosen_line = voice.get(chosen_lang, voice["en"])
    threading.Thread(target=lambda: _speak_multilang(
        voice["en"], hi=voice["hi"], de=voice["de"], fr=voice["fr"], es=voice["es"]
    ), daemon=True).start()
    delay_ms = _delay_for_line(kind, chosen_lang, chosen_line)

    def _build_popup_after_speech():
        # Mark that this year's celebration has happened (normal OR belated)
        try:
            s = load_settings()
            s["birthday_show_next_boot"] = False
            s["birthday_show_next_boot_date"] = ""
            s["birthday_celebration_scheduled"] = True
            s["birthday_celebrated_year"] = datetime.date.today().year
            save_settings(s)
        except Exception:
            pass

        # Start music exactly when the popup appears
        _play_music("pokemon_center_birthday.mp3", loop=True)

        # Celebration popup (match demo visuals)
        W, H = 520, 380
        popup = tk.Toplevel(master=r)
        try:
            popup.iconbitmap(utils.resource_path("nova_icon_big.ico"))
        except Exception:
            pass

        popup.title("🎉 Happy Belated Birthday!" if belated else "🎉 Happy Birthday!")
        popup.configure(bg="#1a103d")
        popup.resizable(False, False)
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass
        popup.geometry(f"{W}x{H}")

        # Full-window starry background
        canvas, layers = _make_starry_canvas(popup, W, H)

        # circular Nova face with gentle orbit (84×84 at y=96)
        face_id = None
        try:
            imgTk = _circular_photo("nova_birthday_face.png", (84, 84))
            face_id = canvas.create_image(W // 2, 96, image=imgTk)
            popup._cele_face_ref = imgTk
        except Exception:
            pass
        _animate_stars_and_orbit(canvas, layers, face_id, W // 2, 96, 8)

        # Heading text (y=200, bold 18)
        heading = heading_tpl.format(name=name)
        canvas.create_text(W // 2, 200, text=heading, font=("Segoe UI", 18, "bold"),
                           fill="#e8e6ff", width=W - 40, justify="center")

        # Buttons
        def style_indigo(btn):
            btn.configure(bg="#5a4fcf", fg="white", relief="flat",
                          padx=14, pady=7, cursor="hand2", font=("Segoe UI", 10, "bold"), activeforeground="white")
            btn.bind("<Enter>", lambda e: btn.config(bg="#b084ff"))
            btn.bind("<Leave>", lambda e: btn.config(bg="#5a4fcf"))

        def style_raspberry(btn):
            btn.configure(bg="#b84b5f", fg="white", relief="flat",
                          padx=14, pady=7, cursor="hand2", font=("Segoe UI", 10), activeforeground="white")
            btn.bind("<Enter>", lambda e: btn.config(bg="#e07b8d"))
            btn.bind("<Leave>", lambda e: btn.config(bg="#b84b5f"))

        def reveal_surprise():
            _show_poem_popup(popup, canvas)

        # Thanks burst (keeps popup/music)
        def thanks_burst():
            burst = []
            for _ in range(60):  # more particles than before
                x = W // 2; y = 96
                rdot = random.randint(2, 4)
                dot = canvas.create_oval(x, y, x + rdot, y + rdot,
                                         fill=random.choice(["#ffd1dc", "#ffe6a7", "#b5e9ff", "#c8ffe0"]),
                                         outline="")
                vx = random.uniform(-3.5, 3.5)
                vy = random.uniform(-2.5, -4.5)
                burst.append([dot, vx, vy, 0])
            def step():
                alive = False
                for item in burst:
                    dot, vx, vy, age = item
                    vy += 0.18
                    canvas.move(dot, vx, vy)
                    item[2] = vy; item[3] = age + 1
                    if age < 52:
                        alive = True
                    else:
                        try: canvas.delete(dot)
                        except Exception: pass
                if alive and popup.winfo_exists():
                    popup.after(16, step)
            step()

        def on_thanks():
            btn_thanks.config(state="disabled")
            thanks_burst()
            def fade_out(a=1.0):
                a -= 0.15
                if a <= 0:
                    try: btn_thanks.place_forget()
                    except Exception: pass
                    return
                try:
                    btn_thanks.configure(activebackground="#b84b5f")
                except Exception:
                    pass
                if popup.winfo_exists():
                    popup.after(30, fade_out, a)
            fade_out()

        # place buttons near bottom with balanced spacing (match demo)
        btn_reveal = tk.Button(popup, text="🎁 Reveal my surprise", command=reveal_surprise)
        style_indigo(btn_reveal)
        btn_thanks = tk.Button(popup, text="Thanks, Nova!", command=on_thanks)
        style_raspberry(btn_thanks)

        canvas.create_window(W // 2 - 90 + 10, H - 105, window=btn_reveal)
        canvas.create_window(W // 2 + 90 + 10, H - 105, window=btn_thanks)

        # keys: Enter reveals; Esc/X closes (and only there we stop music)
        popup.bind("<Return>", lambda e: reveal_surprise())
        def _close():
            _stop_music()
            try: popup.destroy()
            except Exception: pass
        popup.bind("<Escape>", lambda e: _close())
        popup.protocol("WM_DELETE_WINDOW", _close)

        utils.logger.info("Showing %s birthday popup", "belated" if belated else "normal")
        _center_and_show(popup)

    # schedule popup build after speech finishes (per-language exact timing)
    _tk_after(delay_ms, _build_popup_after_speech)

# -------------------------------
# Poem popup — starry bg, circular Nova, centered oval, CTA; closes both cleanly
# -------------------------------
def _show_poem_popup(parent_popup: tk.Toplevel, parent_canvas: tk.Canvas):
    r = _root()
    if not r or not parent_popup or not parent_popup.winfo_exists():
        return

    W, H = 520, 380
    win = tk.Toplevel(master=parent_popup)
    try:
        win.iconbitmap(utils.resource_path("nova_icon_big.ico"))
    except Exception:
        pass

    win.title("🎁 Your Birthday Poem")
    win.configure(bg="#1a103d")
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
        win.transient(parent_popup)
    except Exception:
        pass
    win.geometry(f"{W}x{H}")

    cvs, layers = _make_starry_canvas(win, W, H)

    # small circular glow face (≈70 at y=72)
    face_id = None
    try:
        imgTk = _circular_photo("nova_birthday_face.png", (70, 70))
        face_id = cvs.create_image(W // 2, 72, image=imgTk)
        win._poem_face_ref = imgTk
    except Exception:
        pass
    _animate_stars_and_orbit(cvs, layers, face_id, W // 2, 72, 8)

    # Oval poem bubble (match demo geometry)
    POEM_CENTER_Y       = 210
    POEM_RADIUS_X       = 244
    POEM_RADIUS_Y       = 82
    POEM_TEXT_INNER_PAD = 12
    CTA_MARGIN_BOTTOM   = 48

    cx = W // 2
    left   = cx - POEM_RADIUS_X
    right  = cx + POEM_RADIUS_X
    top    = POEM_CENTER_Y - POEM_RADIUS_Y
    bottom = POEM_CENTER_Y + POEM_RADIUS_Y
    cvs.create_oval(left, top, right, bottom, fill="#241a50", outline="")

    poem = get_birthday_poem(name=(load_from_memory("name") or "Trainer"))
    text_wrap = (POEM_RADIUS_X - POEM_TEXT_INNER_PAD) * 2
    cvs.create_text(cx, POEM_CENTER_Y, text=poem, font=("Segoe UI", 11, "bold"),
                    fill="#e8e6ff", width=text_wrap, justify="left")

    # CTA button
    def style_raspberry(btn):
        btn.configure(bg="#b84b5f", fg="white", relief="flat",
                      padx=16, pady=8, cursor="hand2", font=("Segoe UI", 10, "bold"), activeforeground="white")
        btn.bind("<Enter>", lambda e: btn.config(bg="#e07b8d"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#b84b5f"))

    def close_everything():
        # big confetti on poem AND celebration, then stop music and close both (after overlay completes)
        try:
            _mega_confetti_on(win)
            if parent_popup and parent_popup.winfo_exists():
                _mega_confetti_on(parent_popup)
        except Exception:
            pass
        _stop_music()
        # destroy *after* overlay finishes to avoid any glimpse
        win.after(1300, lambda: (win.destroy() if win.winfo_exists() else None))
        if parent_popup and parent_popup.winfo_exists():
            parent_popup.after(1300, lambda: (parent_popup.destroy() if parent_popup.winfo_exists() else None))

    btn = tk.Button(win, text="Hope you liked the gesture ✨", command=close_everything)
    style_raspberry(btn)
    cvs.create_window(W // 2, H - CTA_MARGIN_BOTTOM, window=btn)

    win.bind("<Return>", lambda e: close_everything())
    win.bind("<Escape>", lambda e: close_everything())
    win.protocol("WM_DELETE_WINDOW", close_everything)

    _center_and_show(win)
