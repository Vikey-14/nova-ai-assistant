# birthday_manager.py
# -*- coding: utf-8 -*-

import datetime
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os, random, time, math

# pygame is optional at runtime
try:
    import pygame
except Exception:
    pygame = None  # degrade gracefully

from memory_handler import load_from_memory, save_to_memory
from birthday_present import get_birthday_poem
from utils import pkg_path

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

    If we never detect visibility within timeout_ms, we still run (best-effort).
    """
    start = time.time()

    def _visible() -> bool:
        r = _root()
        if not (r and r.winfo_exists()):
            return False
        try:
            # mapped and not minimized/withdrawn
            st = r.state()
            return r.winfo_viewable() and st not in ("withdrawn", "iconic")
        except Exception:
            return False

    def _poll():
        if _visible():
            _tk_after(extra_delay_ms, run_fn)
            return
        if (time.time() - start) * 1000 >= timeout_ms:
            # fail-safe: don't block forever
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
# Boot check and deferred prompts (after greeting)
# -------------------------------
def check_and_prompt_birthday():
    # Use multi-lang speech from utils, and remember settings
    from utils import _speak_multilang, load_settings, save_settings, logger

    settings = load_settings()
    settings["boot_count"] = settings.get("boot_count", 0) + 1
    boot = settings["boot_count"]
    # Persist the increment immediately so boot milestones (3/10) are reached.
    save_settings(settings)

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

        # Reset once-per-day marker (so same-day popup doesn’t replay on the same day)
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

                # If user had a pending same-day surprise from last session → show now
                if show_next_boot and show_next_boot_date == today_str:
                    logger.info("🎂 Pending same-day celebration from last session → showing after greeting")
                    _after_greeting(_celebrate_now)
                    settings["birthday_show_next_boot"] = False
                    settings["birthday_show_next_boot_date"] = ""
                    settings["birthday_celebration_scheduled"] = True
                    settings["birthday_celebrated_year"] = this_year
                    save_settings(settings)

                # Normal day-of logic (when saved earlier; no 5-minute timer)
                elif not settings.get("birthday_celebration_scheduled", False):
                    logger.info("🎂 Birthday today — showing celebration after greeting (no timer for earlier-saved birthdays)")
                    _after_greeting(_celebrate_now)
                    settings["birthday_celebration_scheduled"] = True
                    settings["birthday_celebrated_year"] = this_year
                    save_settings(settings)

            # ---- CASE B: Belated window (1–7 days after birthday) ----
            else:
                # If we already celebrated this year (either normal or belated), skip
                if celebrated_year == this_year:
                    pass
                else:
                    # only look back at this year's birthday
                    if today_date > bday_this_year:
                        delta = (today_date - bday_this_year).days
                        if 1 <= delta <= 7:
                            def _celebrate_belated():
                                _tk_after(0, show_birthday_celebration_popup, True)  # belated=True
                            logger.info(f"🎈 Belated birthday window ({delta} days) — showing belated wish after greeting")
                            _after_greeting(_celebrate_belated)
                            settings["birthday_celebration_scheduled"] = True
                            settings["birthday_celebrated_year"] = this_year
                            # clear any stale “same-day” carry-over flags
                            settings["birthday_show_next_boot"] = False
                            settings["birthday_show_next_boot_date"] = ""
                            save_settings(settings)

    # --- Ask for birthday on boot #3 and #10, after greeting ---
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

        if boot == 3 and not asked_before:
            _after_greeting(_ask_now_first)
            settings["birthday_asked"] = True
            save_settings(settings)

        elif boot == 10 and not final_prompt_shown:
            _after_greeting(_ask_now_final)
            settings["birthday_final_prompt_shown"] = True
            save_settings(settings)

# -------------------------------
# Birthday entry popup (tip-style header)
# -------------------------------
def show_birthday_input_popup():
    from utils import load_settings, save_settings, logger
    import dateparser

    r = _root()
    if not r:
        return

    # Soft chime (best effort)
    _play_music("birthday_chime.mp3", loop=False)

    popup = tk.Toplevel(master=r)
    popup.title("🎂 What's Your Birthdate?")
    popup.configure(bg="#1a103d")
    popup.resizable(False, False)
    try:
        popup.attributes("-topmost", True)
    except Exception:
        pass

    # Size first (prevents geometry jitter), then we'll center
    popup.geometry("480x360")

    # ----- starry header like the tip -----
    header_h = 140
    canvas = tk.Canvas(popup, width=480, height=header_h, bg="#1a103d", highlightthickness=0, bd=0)
    canvas.pack()

    star_layers = {1: [], 2: [], 3: []}
    for layer in star_layers:
        for _ in range(12):
            x = random.randint(0, 480)
            y = random.randint(0, header_h)
            size = layer  # 1..3
            star = canvas.create_oval(x, y, x + size, y + size, fill="#c9cfff", outline="")
            star_layers[layer].append(star)

    # glow face (tip-style) with tiny orbit
    logo_id = None
    try:
        img_path = str(pkg_path("assets", "nova_face_glow.png"))
        img = Image.open(img_path).resize((84, 84))
        logo = ImageTk.PhotoImage(img)
        logo_id = canvas.create_image(240, header_h // 2, image=logo)
        popup._logo_ref = logo  # keep reference
    except Exception:
        pass

    def animate():
        animate.t = getattr(animate, "t", 0) + 2
        # drift stars
        for layer, stars in star_layers.items():
            dx = 0.25 * layer
            for s in stars:
                canvas.move(s, dx, 0)
                x0, y0, x1, y1 = canvas.coords(s)
                if x0 > 480:
                    canvas.move(s, -480 - (x1 - x0), 0)
        # tiny orbit for the logo
        if logo_id:
            r_orb, cx, cy = 10, 240, header_h // 2
            rad = math.radians(animate.t)
            canvas.coords(logo_id, cx + r_orb * math.cos(rad), cy + r_orb * math.sin(rad))
        try:
            popup.after(50, animate)
        except Exception:
            pass
    animate()

    # ----- form -----
    tk.Label(
        popup, text="When is your birthday?",
        font=("Segoe UI", 12, "bold"), fg="#dcdcff", bg="#1a103d"
    ).pack(pady=(12, 4))

    entry = tk.Entry(popup, font=("Segoe UI", 12), justify="center")
    entry.pack(pady=4)
    entry.focus_set()

    tk.Label(
        popup, text="e.g., August 5 or 5th Aug",
        font=("Segoe UI", 10), fg="#9aa0c7", bg="#1a103d"
    ).pack(pady=(2, 10))

    # button styles (exact palette + hover)
    def style_indigo(btn):
        # primary indigo (#5a4fcf) → hover #b084ff
        btn.configure(bg="#5a4fcf", fg="white", relief="flat",
                      padx=14, pady=7, cursor="hand2", font=("Segoe UI", 10, "bold"), activeforeground="white")
        btn.bind("<Enter>", lambda e: btn.config(bg="#b084ff"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#5a4fcf"))

    def style_raspberry(btn):
        # raspberry/rose (#b84b5f) → hover #e07b8d
        btn.configure(bg="#b84b5f", fg="white", relief="flat",
                      padx=14, pady=7, cursor="hand2", font=("Segoe UI", 10), activeforeground="white")
        btn.bind("<Enter>", lambda e: btn.config(bg="#e07b8d"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#b84b5f"))

    def save_birthday():
        date_text = entry.get().strip()
        parsed = None
        try:
            parsed = dateparser.parse(date_text)
        except Exception:
            parsed = None
        if parsed:
            formatted = parsed.strftime("%d-%m")
            save_to_memory("birthday", formatted)
            s = load_settings()
            s["birthday_asked"] = True
            s["birthday_final_prompt_shown"] = True
            # reset day-of orchestration so today's celebration logic can run
            s["birthday_celebration_scheduled"] = False
            save_settings(s)

            # NEW: log the save + same-day scheduling breadcrumbs
            logger.info(f"🎂 Birthday saved as {formatted}")
            if formatted == datetime.datetime.now().strftime("%d-%m"):
                logger.info("Scheduling 5-minute same-session surprise + next-boot carry-over")

            try:
                messagebox.showinfo("🎉 Saved", "Got it. Nova has stored your birthday.")
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass

            # Same-session handling: if the saved date is today, schedule 5-minute surprise
            if formatted == datetime.datetime.now().strftime("%d-%m"):
                # also persist a "show on next boot" fallback in case the app closes before 5 minutes
                s2 = load_settings()
                s2["birthday_show_next_boot"] = True
                s2["birthday_show_next_boot_date"] = formatted
                save_settings(s2)

                def _fire():
                    _tk_after(0, show_birthday_celebration_popup, False)  # belated=False
                t = threading.Timer(300, _fire)  # 5 minutes
                t.daemon = True
                t.start()

        else:
            try:
                messagebox.showerror("Oops!", "Couldn't understand the date. Try something like 'August 5'.")
            except Exception:
                pass

    def remind_later():
        s = load_settings()
        s["birthday_asked"] = True
        s["birthday_final_prompt_shown"] = True
        save_settings(s)
        try:
            popup.destroy()
        except Exception:
            pass

    row = tk.Frame(popup, bg="#1a103d"); row.pack(pady=(6, 12))
    btn_save  = tk.Button(row, text="🎂 Save Birthday", command=save_birthday)
    btn_later = tk.Button(row, text="Remind Me Later", command=remind_later)
    btn_save.pack(side="left", padx=8); btn_later.pack(side="left", padx=8)

    # Save = raspberry, Remind = indigo
    style_raspberry(btn_save)
    style_indigo(btn_later)

    # shortcuts + close behavior
    popup.bind("<Return>", lambda e: save_birthday())  # Enter = Save
    popup.bind("<Escape>", lambda e: remind_later())   # Esc   = Remind
    popup.protocol("WM_DELETE_WINDOW", remind_later)

    _center_and_show(popup)

# -------------------------------
# Birthday celebration popup
# -------------------------------
def show_birthday_celebration_popup(belated: bool = False):
    from utils import _speak_multilang, load_settings, save_settings, logger

    r = _root()
    if not r:
        return

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

    _play_music("pokemon_center_birthday.mp3", loop=True)

    popup = tk.Toplevel(master=r)
    popup.title("🎉 Happy Belated Birthday!" if belated else "🎉 Happy Birthday!")
    popup.configure(bg="#1a103d")
    popup.resizable(False, False)
    try:
        popup.attributes("-topmost", True)
    except Exception:
        pass

    popup.geometry("500x420")

    header_h = 160
    canvas = tk.Canvas(popup, width=500, height=header_h, bg="#1a103d", highlightthickness=0, bd=0)
    canvas.pack()

    # starry header
    star_layers = {1: [], 2: [], 3: []}
    for layer in star_layers:
        for _ in range(12):
            x = random.randint(0, 500); y = random.randint(0, header_h)
            sdot = layer
            star = canvas.create_oval(x, y, x+sdot, y+sdot, fill="#c9cfff", outline="")
            star_layers[layer].append(star)

    # birthday face (kept, not the glow one) with gentle orbit
    logo_id = None
    try:
        img = Image.open(str(pkg_path("assets", "nova_birthday_face.png"))).resize((84, 84))
        logo = ImageTk.PhotoImage(img)
        logo_id = canvas.create_image(250, header_h//2, image=logo)
        popup._logo_ref = logo
    except Exception:
        pass

    # ambient confetti
    confetti = []
    for _ in range(28):
        x = random.randint(0, 500); y = random.randint(0, header_h)
        rdot = random.randint(2, 4)
        c = canvas.create_oval(x, y, x+rdot, y+rdot,
                               fill=random.choice(["#ffccff", "#fffacd", "#b0e0e6"]),
                               outline="")
        confetti.append(c)

    def _anim():
        _anim.t = getattr(_anim, "t", 0) + 2
        # stars drift
        for layer, stars in star_layers.items():
            dx = 0.25 * layer
            for s in stars:
                canvas.move(s, dx, 0)
                x0, y0, x1, y1 = canvas.coords(s)
                if x0 > 500:
                    canvas.move(s, -500 - (x1 - x0), 0)
        # face orbit
        if logo_id:
            r_orb, cx, cy = 10, 250, header_h//2
            rad = math.radians(_anim.t)
            canvas.coords(logo_id, cx + r_orb*math.cos(rad), cy + r_orb*math.sin(rad))
        # ambient confetti fall
        for d in confetti:
            canvas.move(d, 0, 1.2)
            x0, y0, x1, y1 = canvas.coords(d)
            if y0 > header_h:
                canvas.move(d, 0, -header_h - (y1 - y0))
        try:
            popup.after(50, _anim)
        except Exception:
            pass
    _anim()

    # message
    name = load_from_memory("name") or "Trainer"
    if belated:
        heading = f"Happy Belated Birthday, {name}! 🎉"
        voice = dict(
            en="A little late, but with all my heart — Happy Belated Birthday!",
            hi="थोड़ा देर से सही, दिल से — जन्मदिन की ढेर सारी शुभकामनाएँ!",
            de="Etwas spät, aber von Herzen – alles Gute nachträglich zum Geburtstag!",
            fr="Avec un peu de retard, mais de tout cœur — joyeux anniversaire en retard !",
            es="Un poco tarde, ¡pero con todo mi corazón! ¡Feliz cumpleaños atrasado!"
        )
    else:
        heading = f"Happy Birthday, {name}! 🎉"
        voice = dict(
            en="Surprise! It’s your special day. Happy Birthday!",
            hi="सरप्राइज़! आज आपका जन्मदिन है। जन्मदिन की शुभकामनाएँ!",
            de="Überraschung! Heute ist dein Geburtstag. Alles Gute zum Geburtstag!",
            fr="Surprise ! C'est ton anniversaire. Joyeux anniversaire !",
            es="¡Sorpresa! Hoy es tu cumpleaños. ¡Feliz cumpleaños!"
        )

    tk.Label(popup, text=heading, font=("Segoe UI", 13, "bold"),
             fg="#e8e6ff", bg="#1a103d", justify="center", wraplength=460).pack(pady=(10, 12))

    # button styles (exact palette + hover)
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

    # actions
    def reveal_surprise():
        poem = get_birthday_poem(name=(load_from_memory("name") or "Trainer"))
        try: messagebox.showinfo("🎁 Your Birthday Poem", poem)
        except Exception: pass

    # Thanks burst (keeps popup/music)
    def thanks_burst():
        burst = []
        for _ in range(36):
            x = 250; y = header_h//2
            rdot = random.randint(2, 4)
            dot = canvas.create_oval(x, y, x+rdot, y+rdot,
                                     fill=random.choice(["#ffd1dc","#ffe6a7","#b5e9ff","#c8ffe0"]),
                                     outline="")
            vx = random.uniform(-3.2, 3.2)
            vy = random.uniform(-2.0, -4.0)
            burst.append([dot, vx, vy, 0])
        def step():
            alive = False
            for item in burst:
                dot, vx, vy, age = item
                vy += 0.18
                canvas.move(dot, vx, vy)
                item[2] = vy; item[3] = age + 1
                if age < 45:
                    alive = True
                else:
                    try: canvas.delete(dot)
                    except Exception: pass
            if alive and popup.winfo_exists():
                popup.after(16, step)
        step()

    def on_thanks():
        thanks_btn.config(state="disabled")
        thanks_burst()
        def fade_out(a=1.0):
            a -= 0.15
            if a <= 0:
                try: thanks_btn.pack_forget()
                except Exception: pass
                return
            try:
                thanks_btn.configure(activebackground="#b84b5f")
            except Exception:
                pass
            if popup.winfo_exists():
                popup.after(30, fade_out, a)
        fade_out()

    row = tk.Frame(popup, bg="#1a103d"); row.pack(pady=(0, 12))
    btn_reveal = tk.Button(row, text="🎁 Reveal my surprise", command=reveal_surprise); style_indigo(btn_reveal)
    thanks_btn = tk.Button(row, text="Thanks, Nova!", command=on_thanks); style_raspberry(thanks_btn)
    btn_reveal.pack(side="left", padx=8); thanks_btn.pack(side="left", padx=8)

    # keys: Enter reveals; Esc/X closes (and only there we stop music)
    popup.bind("<Return>", lambda e: reveal_surprise())
    def _close():
        _stop_music()
        try: popup.destroy()
        except Exception: pass
    popup.bind("<Escape>", lambda e: _close())
    popup.protocol("WM_DELETE_WINDOW", _close)  # pass function, don’t call

    # Log which popup we’re showing (normal/belated)
    logger.info("Showing %s birthday popup", "belated" if belated else "normal")

    _center_and_show(popup)

    # localized voice line
    threading.Thread(target=lambda: _speak_multilang(
        voice["en"], hi=voice["hi"], de=voice["de"], fr=voice["fr"], es=voice["es"]
    ), daemon=True).start()
