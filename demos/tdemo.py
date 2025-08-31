# ready_tip_calibrator.py  — v3
# Fine-tune when the Tray Tip should appear after Nova says the ready line.

import tkinter as tk
from tkinter import ttk
import threading, time

# Try to use your project's multilingual TTS if available.
try:
    import utils  # expects utils._speak_multilang(en, hi=None, de=None, fr=None, es=None)
    HAVE_UTILS = True
except Exception:
    HAVE_UTILS = False

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

# ---------------- Minimal “tip” popup for the demo ----------------
def _show_tip(parent):
    w = tk.Toplevel(parent)
    w.withdraw()
    w.title("Nova • Tray Tip (demo)")
    w.configure(bg="#1a103d")
    w.resizable(False, False)

    tk.Label(
        w,
        text=("Nova is running in the system tray.\n\n"
              "Tip: If you don’t see the tray icon, click the ^ arrow near the clock.\n"
              "You can drag it out to keep it always visible."),
        font=("Segoe UI", 11), fg="#dcdcff", bg="#1a103d",
        justify="center", wraplength=360
    ).pack(padx=20, pady=20)

    tk.Button(
        w, text="Got it!", font=("Segoe UI", 10, "bold"),
        bg="#5a4fcf", fg="white", activebackground="#6a5df0",
        relief="flat", padx=16, pady=8, command=w.destroy, cursor="hand2"
    ).pack(pady=(0, 14))

    w.update_idletasks()
    ww, hh = w.winfo_width(), w.winfo_height()
    sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
    w.geometry(f"{ww}x{hh}+{(sw-ww)//2}+{(sh-hh)//2}")
    w.deiconify()
    try:
        w.lift(); w.focus_force()
        w.after(10, lambda: w.attributes("-topmost", False))
    except Exception:
        pass

# ---------------- TTS helper: speak ONLY the chosen language ----------------
# ---------------- TTS helper: speak in the chosen language (fix) ----------------
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
            # Tell your TTS which language to use right now
            utils.selected_language = lang_code

            # Provide strings for all languages (the chosen one uses `text`,
            # the others use the default ready line so the API signature matches)
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
        # Fallback timing so the popup scheduling still "feels" right without audio
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
    root.title("Nova • Ready-line → Tip timing calibrator")
    root.configure(bg="#110a2b")
    root.geometry("820x520")

    def lab(txt): return tk.Label(root, text=txt, fg="#cfd2ff", bg="#110a2b", font=("Segoe UI", 10))

    tk.Label(root, text="Fine-tune when the Tray Tip appears after Nova says the ready line",
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

    def on_lang_change(_evt=None):
        code = current_lang_code()
        line_var.set(READY.get(code, READY["en"]))
        _update_estimate()
    lang_menu.bind("<<ComboboxSelected>>", on_lang_change)

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

    # Status
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

    def speak_and_show_estimated():
        code = current_lang_code()
        text = (line_var.get() or "").strip()
        msw, mn, cu, es, hg, eh = _vals()
        sched, base = _scheduled_delay_ms(text, msw, mn, cu, es, hg, eh)
        status.config(text=f"Estimate: base={base} ms  →  scheduled tip at {sched} ms")

        # Speak ONLY the chosen language
        threading.Thread(target=lambda: _speak_chosen_language(code, text), daemon=True).start()
        root.after(sched, lambda: _show_tip(root))

    def speak_and_show_exact():
        code = current_lang_code()
        text = (line_var.get() or "").strip()
        msw, mn, cu, *_ = _vals()
        base = _estimate_ms(text, msw, mn, cu)
        status.config(text=f"Exact: schedule at base={base} ms")

        threading.Thread(target=lambda: _speak_chosen_language(code, text), daemon=True).start()
        root.after(base, lambda: _show_tip(root))

    tk.Button(btn_row, text="Speak & Show Tip (estimated)",
              command=speak_and_show_estimated,
              bg="#5a4fcf", fg="white", activebackground="#6a5df0",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    tk.Button(btn_row, text="Speak & Show Tip (exact)",
              command=speak_and_show_exact,
              bg="#5a4fcf", fg="white", activebackground="#6a5df0",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    # Initialize localized line on first paint
    on_lang_change()
    root.mainloop()

if __name__ == "__main__":
    main()
