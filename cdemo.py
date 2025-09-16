# coding: utf-8
"""
goodbye_calibrator.py — Calibrate when the app should CLOSE after Nova says the goodbye line.

What you get:
- Language picker (en/hi/de/fr/es)
- Goodbye line editor
- Measure end timing: press SPACE (or ENTER) the moment you hear the line finish
- Slider to tweak the delay in ms
- "Speak & Show Close" to preview a popup at that delay
- One-click copy of the Python snippet to paste into your main app

Run:
  python demo/goodbye_calibrator.py
"""

import sys, time, threading, json, tkinter as tk
from tkinter import ttk

# Prefer Nova's real speak() (so audio path matches the app exactly)
HAVE_UTILS = False
try:
    import utils
    HAVE_UTILS = True
except Exception:
    HAVE_UTILS = False

print("[goodbye_calibrator] HAVE_UTILS =", HAVE_UTILS)

# ---------- TTS glue ----------
def _speak_line(lang_code: str, text: str):
    if not text:
        return
    if HAVE_UTILS and hasattr(utils, "speak"):
        # Use Nova's TTS router (handles Windows-English quirks, Piper, etc.)
        try:
            # Force language if caller picked a specific one
            utils.speak(text, tts_lang=lang_code, blocking=False)
            return
        except Exception:
            pass
    # Fallback: very small best-effort stub (only if utils missing)
    try:
        import pyttsx3
        def _run():
            eng = pyttsx3.init()
            eng.say(text)
            eng.runAndWait()
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        # Ultimate fallback: just sleep so timers feel right
        words = max(1, len(text.split()))
        threading.Thread(target=lambda: time.sleep(max(0.8, words*0.2)), daemon=True).start()


# ---------- Data ----------
GOODBYE = {
    "en": "Goodbye! See you soon.",
    "hi": "अलविदा! फिर मिलेंगे।",
    "de": "Tschüss! Bis bald.",
    "fr": "Au revoir ! À bientôt.",
    "es": "¡Adiós! Hasta pronto.",
}

# Start with a conservative baseline; you'll overwrite these while calibrating.
GOODBYE_MS = {
    "en": 1700,
    "hi": 1900,
    "de": 1800,
    "fr": 1800,
    "es": 1700,
}

LANGS = [("English", "en"), ("हिन्दी", "hi"), ("Deutsch", "de"), ("Français", "fr"), ("Español", "es")]

def now_ms() -> int:
    return int(time.perf_counter() * 1000)

# ---------- UI ----------
def main():
    root = tk.Tk()
    root.title("Nova • Goodbye → Close timing calibrator")
    root.configure(bg="#110a2b")
    root.geometry("860x560")

    def lab(txt, f=("Segoe UI", 10), c="#cfd2ff", bg="#110a2b"):
        return tk.Label(root, text=txt, fg=c, bg=bg, font=f)

    lab("Calibrate when the APP should close after Nova says the goodbye line",
        f=("Segoe UI", 12, "bold"), c="#e9ebff").pack(pady=(10, 6))

    # Top row
    top = tk.Frame(root, bg="#110a2b")
    top.pack(padx=14, pady=(0, 6), fill="x")

    lab("Language:").grid(in_=top, row=0, column=0, sticky="w")
    lang_menu = ttk.Combobox(top, state="readonly", width=14,
                             values=[name for name, _ in LANGS])
    lang_menu.current(0)
    lang_menu.grid(row=0, column=1, sticky="w", padx=(6, 18))

    lab("Goodbye line:").grid(in_=top, row=0, column=2, sticky="e")
    line_var = tk.StringVar(value=GOODBYE["en"])
    entry = tk.Entry(top, textvariable=line_var, width=52)
    entry.grid(row=0, column=3, sticky="we", padx=(6, 0))
    top.columnconfigure(3, weight=1)

    # Current delay (ms)
    delay_var = tk.IntVar(value=GOODBYE_MS["en"])

    # Status
    status = tk.Label(root, text="", fg="#9ea4ff", bg="#110a2b", font=("Segoe UI", 10))
    status.pack(pady=(2, 8))

    # Popup ("app closed") for demo
    def _show_close_popup(ms_delay: int, lang_code: str):
        try:
            import winsound
            winsound.MessageBeep(-1)
        except Exception:
            pass

        w = tk.Toplevel(root)
        w.withdraw()
        w.title("APP CLOSED (demo)")
        w.configure(bg="#1a103d")
        w.resizable(False, False)

        tk.Label(w, text="APP CLOSED (demo)", font=("Segoe UI", 18, "bold"),
                 fg="#ffffff", bg="#1a103d").pack(padx=20, pady=(18, 6))
        tk.Label(w, text=f"Popup at {ms_delay} ms for [{lang_code}]", font=("Segoe UI", 11),
                 fg="#dcdcff", bg="#1a103d").pack(pady=(0, 14))
        tk.Button(w, text="Close", font=("Segoe UI", 10, "bold"),
                  bg="#5a4fcf", fg="white", activebackground="#6a5df0",
                  relief="flat", padx=16, pady=8, command=w.destroy, cursor="hand2").pack(pady=(0, 14))

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

    # Helpers
    def current_lang_code() -> str:
        name = lang_menu.get()
        for n, c in LANGS:
            if n == name:
                return c
        return "en"

    def on_lang_change(_evt=None):
        code = current_lang_code()
        line_var.set(GOODBYE.get(code, GOODBYE["en"]))
        delay_var.set(GOODBYE_MS.get(code, GOODBYE_MS["en"]))
        status.config(text=f"[{code}] current delay = {delay_var.get()} ms")

    lang_menu.bind("<<ComboboxSelected>>", on_lang_change)

    # Slider for delay
    mid = tk.Frame(root, bg="#110a2b")
    mid.pack(padx=14, pady=(6, 8), fill="x")

    lab("Close delay (ms):").grid(in_=mid, row=0, column=0, sticky="w")
    s = tk.Scale(mid, from_=200, to=6000, orient="horizontal", resolution=10,
                 bg="#110a2b", fg="#cfd2ff", troughcolor="#2a2460",
                 highlightthickness=0, variable=delay_var, length=560,
                 command=lambda e: status.config(text=f"[{current_lang_code()}] delay = {delay_var.get()} ms"))
    s.grid(row=0, column=1, sticky="we")

    # Buttons row
    btn_row = tk.Frame(root, bg="#110a2b")
    btn_row.pack(pady=(6, 12))

    measuring = {"active": False, "t0": 0, "bind_id_space": None, "bind_id_return": None}

    def _start_measure():
        """Start speaking and let the user press SPACE/ENTER when audio ends."""
        if measuring["active"]:
            return
        code = current_lang_code()
        text = (line_var.get() or "").strip()
        if not text:
            return

        measuring["active"] = True
        measuring["t0"] = now_ms()

        # Speak on a worker thread so UI doesn't freeze (English/Windows may block in utils.speak)
        threading.Thread(target=lambda: _speak_line(code, text), daemon=True).start()
        status.config(text=f"[{code}] Measuring… Press SPACE/ENTER when the goodbye line FINISHES.")

        def _finish_measure(_evt=None):
            if not measuring["active"]:
                return
            elapsed = now_ms() - measuring["t0"]
            measuring["active"] = False
            # unbind
            try:
                if measuring["bind_id_space"]:
                    root.unbind("<space>", measuring["bind_id_space"])
                if measuring["bind_id_return"]:
                    root.unbind("<Return>", measuring["bind_id_return"])
            except Exception:
                pass
            delay_var.set(elapsed)
            GOODBYE_MS[code] = int(elapsed)
            status.config(text=f"[{code}] Measured ≈ {elapsed} ms → saved for this language. (Use preview to confirm)")

        # Bind keys for user to mark the end
        measuring["bind_id_space"]  = root.bind("<space>",  _finish_measure, add="+")
        measuring["bind_id_return"] = root.bind("<Return>", _finish_measure, add="+")

    def _speak_and_show():
        code = current_lang_code()
        text = (line_var.get() or "").strip()
        ms = max(0, int(delay_var.get()))
        status.config(text=f"[{code}] Preview: popup at {ms} ms after speech starts.")
        threading.Thread(target=lambda: _speak_line(code, text), daemon=True).start()
        root.after(ms, lambda: _show_close_popup(ms, code))

    def _save_lang_value():
        code = current_lang_code()
        ms = int(delay_var.get())
        GOODBYE_MS[code] = ms
        status.config(text=f"[{code}] Saved delay = {ms} ms.")

    def _copy_snippet():
        # Create a neat Python dict snippet for pasting into main app
        snippet = (
            "GOODBYE_MS = " + json.dumps(GOODBYE_MS, indent=2, ensure_ascii=False)
        )
        try:
            root.clipboard_clear()
            root.clipboard_append(snippet)
        except Exception:
            pass
        status.config(text="Copied Python snippet for GOODBYE_MS to clipboard (paste into your main app).")

    tk.Button(btn_row, text="Measure end (press SPACE/ENTER)",
              command=_start_measure,
              bg="#5a4fcf", fg="white", activebackground="#6a5df0",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    tk.Button(btn_row, text="Speak & Show Close (use delay)",
              command=_speak_and_show,
              bg="#5a4fcf", fg="white", activebackground="#6a5df0",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    tk.Button(btn_row, text="Save value for this language",
              command=_save_lang_value,
              bg="#2a925a", fg="white", activebackground="#36b06e",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    tk.Button(btn_row, text="Copy GOODBYE_MS snippet",
              command=_copy_snippet,
              bg="#3a6edc", fg="white", activebackground="#4a84ff",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    # Initialize
    on_lang_change()
    root.mainloop()

if __name__ == "__main__":
    main()
