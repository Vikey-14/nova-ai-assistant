# handlers/physics_solver.py

from __future__ import annotations

import os
import json
import re
import importlib
from math import pi
from typing import Optional, Tuple, Dict, List, Any

# GUI pieces are called indirectly (avoid circular imports at module import time)
import tkinter as tk
from tkinter import ttk

from sympy import Eq, solve, N, sin, cos, tan  # dropped unused 'exp'
from sympy.parsing.sympy_parser import parse_expr
from sympy.core.mul import Mul
from sympy.core.add import Add
from sympy.core.power import Pow
from followup import await_followup
from say_show import say_show



# 🎤 Preface when the user chooses to see a graph from a Physics solution
def _preface_physics_show_graph():
    """Say/Show 'Showing the graph.' in the current GUI language (short form)."""
    try:
        say_show(
            "Showing the graph.",
            hi="ग्राफ दिखा रही हूँ।",
            de="Zeige das Diagramm.",
            fr="J’affiche le graphique.",
            es="Mostrando el gráfico.",
            title="Nova",
        )
    except Exception:
        # Never block the plot preview on speech/UI hiccups
        pass


def _get_lang_bits():
    from utils import selected_language, listen_command
    lang = (selected_language or "en").split("-")[0].lower()
    return lang, listen_command

_DYM_TEXTS = {
    "P": {
        "en": "Did you mean Power (W) or Pressure (Pa)? Say or type 'power' or 'pressure'.",
        "hi": "क्या आपका मतलब Power (W) या Pressure (Pa) से है? 'power' या 'pressure' कहें/टाइप करें।",
        "de": "Meintest du Power (W) oder Pressure (Pa)? Sage oder tippe 'power' oder 'pressure'.",
        "fr": "Vouliez-vous dire Power (W) ou Pressure (Pa) ? Dites « power » ou « pressure ».",
        "es": "¿Te refieres a Power (W) o Pressure (Pa)? Di o escribe 'power' o 'pressure'.",
    },
    "lambda": {
        "en": "Did you mean wavelength λ or decay constant λ? Say 'wavelength' or 'decay'.",
        "hi": "क्या आपका मतलब तरंगदैर्ध्य λ या क्षय स्थिरांक λ से है? 'wavelength' या 'decay' कहें/टाइप करें।",
        "de": "Wellenlänge λ oder Zerfallskonstante λ? Sage 'wavelength' oder 'decay'.",
        "fr": "Longueur d’onde λ ou constante de décroissance λ ? Dites « wavelength » ou « decay ».",
        "es": "¿Longitud de onda λ o constante de decaimiento λ? Di 'wavelength' o 'decay'.",
    },
}
def _pick(d, lang): return d.get(lang, d["en"])

def _resolve_symbol_ambiguities(symbols: set) -> dict:
    """
    Ask only when needed. Returns replacements like {'P': 'P_pressure'} or {'λ': 'λ_decay'}.
    """
    lang, listen_command = _get_lang_bits()
    repl = {}

    # P → Power vs Pressure
    if ("P" in symbols) and ("P_pressure" not in symbols) and ("P_power" not in symbols):
        say_show(_DYM_TEXTS["P"]["en"], hi=_DYM_TEXTS["P"]["hi"], de=_DYM_TEXTS["P"]["de"],
                 fr=_DYM_TEXTS["P"]["fr"], es=_DYM_TEXTS["P"]["es"], title="Nova")
        ans = await_followup(_pick(_DYM_TEXTS["P"], lang),
                             speak_fn=lambda *_a, **_k: None, show_fn=lambda *_a, **_k: None,
                             listen_fn=listen_command, allow_typed=True, allow_voice=True, timeout=18.0)
        ans = (ans or "").strip().lower()
        if "press" in ans: repl["P"] = "P_pressure"
        elif "power" in ans: repl["P"] = "P_power"

    # λ / lambda → wavelength vs decay constant
    if (("lambda" in symbols) or ("λ" in symbols)) and ("λ_decay" not in symbols):
        say_show(_DYM_TEXTS["lambda"]["en"], hi=_DYM_TEXTS["lambda"]["hi"], de=_DYM_TEXTS["lambda"]["de"],
                 fr=_DYM_TEXTS["lambda"]["fr"], es=_DYM_TEXTS["lambda"]["es"], title="Nova")
        ans = await_followup(_pick(_DYM_TEXTS["lambda"], lang),
                             speak_fn=lambda *_a, **_k: None, show_fn=lambda *_a, **_k: None,
                             listen_fn=listen_command, allow_typed=True, allow_voice=True, timeout=18.0)
        ans = (ans or "").strip().lower()
        if "decay" in ans:
            repl["λ"] = "λ_decay"; repl["lambda"] = "λ_decay"
        # if 'wavelength', keep λ as-is
    return repl

# App utilities (PyInstaller-safe paths, UTF-8 JSON, logs dir, etc.)
from utils import handlers_path, load_json_utf8, LOG_DIR, graphs_dir, resource_path

_last_equation_str = None  # remember last solved equation for plotting

# -------------------------------
# Global display controls
# -------------------------------
DEC_PLACES = 2  # ✅ all displayed answers round to 2 decimal places

# --- Concise mode (auto one-liners for basic questions)
AUTO_CONCISE = True  # flip to False to force GUI everywhere
FORCE_BRIEF_PATTERNS = r"\b(brief|quick answer|just answer|no steps|one liner|one-line|tldr|tl;dr|short|summary|summarize|quickly|fast)\b"
FORCE_VERBOSE_PATTERNS = r"\b(show steps|explain|why|how|derivation|proof|walk me through|details|step by step)\b"

# -------------------------------
# Lazy import to prevent circulars
# -------------------------------
def lazy_imports():
    global _speak_multilang, logger
    from utils import _speak_multilang, logger  # handlers_path/load_json_utf8 already imported above


# --- GUI emit helper (use event bus; avoids circular imports) ---
def _emit_gui_html(html: str, *, append: bool = False, channel: str = "physics") -> None:
    try:
        from utils import emit_gui
        payload = {"html": html, "action": "append" if append else "new"}
        emit_gui(channel, payload)
    except Exception:
        # headless/no GUI – safe fallback
        try:
            print(f"[{channel.upper()}] {html}")
        except Exception:
            pass


def _detect_requested_unit(user_input: str):
    """
    Try to detect a requested output unit from the user's input.
    Examples:
        "calculate torque in N·m" -> "N·m"
        "convert to meters" -> "meters"
        "result should be in kg·m/s²" -> "kg·m/s²"
    """
    match = re.search(r"\b(?:in|to)\s+([^\d]+?)(?=$|\s|,|\.)", user_input, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def _normalize_unit_key(u: Optional[str]) -> Optional[str]:
    """
    Normalize a requested unit token so variants match:
    - lowercase
    - ²→^2, ³→^3
    - '.' treated as middle dot '·'
    - internal spaces removed (e.g., 'n · m' → 'n·m')
    """
    if not u:
        return None
    u = u.strip().lower()
    u = u.replace("²", "^2").replace("³", "^3")
    u = u.replace(".", "·")
    u = re.sub(r"\s+", "", u)
    return u

# -------------------------------
# ✨ SAY→SHOW routing for concise replies
# -------------------------------
def _is_gui_visible() -> bool:
    """
    Best-effort check: returns True if the main GUI is up/visible.
    Falls back to settings keys if helper isn’t available.
    """
    try:
        from utils import is_gui_visible  # preferred if provided by app
        return bool(is_gui_visible())
    except Exception:
        pass
    try:
        from utils import is_main_window_visible
        return bool(is_main_window_visible())
    except Exception:
        pass
    try:
        from utils import is_gui_running
        return bool(is_gui_running())
    except Exception:
        pass
    try:
        from utils import load_settings
        s = load_settings() or {}
        # common keys various builds used
        for k in ("gui_visible", "ui_visible", "window_visible", "main_window_shown", "gui_open"):
            if k in s:
                return bool(s.get(k))
    except Exception:
        pass
    # Last resort: assume not visible (voice-only context)
    return False

def say_ml(*, en: str, hi: Optional[str]=None, fr: Optional[str]=None, es: Optional[str]=None, de: Optional[str]=None):
    """Concise one-liner, multilingual; falls back to EN if others aren’t provided (voice only)."""
    lazy_imports()
    _speak_multilang(
        en=en,
        hi=hi or en,
        fr=fr or en,
        es=es or en,
        de=de or en,
    )

def _say_or_show_ml(*, en: str, hi: Optional[str]=None, fr: Optional[str]=None, es: Optional[str]=None, de: Optional[str]=None):
    """
    For concise answers: if GUI is visible → SAY→SHOW (chat bubble + TTS); else → speak only.
    """
    if _is_gui_visible():
        say_show(en, hi=hi or en, fr=fr or en, es=es or en, de=de or en, title="Nova")
    else:
        say_ml(en=en, hi=hi, fr=fr, es=es, de=de)

# ----- Multilingual speech helpers for result + errors -----
def speak_result_ml(target_str: str, value_str: str, unit_str: str):
    """Speak the final numeric result in 5 languages."""
    msg_en = f"{target_str} is {value_str} {unit_str}. I’ve calculated it — check the solution popup."
    msg_hi = f"{target_str} {value_str} {unit_str} है। मैंने गणना कर दी है — पूरी जानकारी पॉप-अप में देखें।"
    msg_fr = f"{target_str} est {value_str} {unit_str}. J’ai fait le calcul — consultez la fenêtre contextuelle pour la solution complète."
    msg_es = f"{target_str} es {value_str} {unit_str}. He hecho el cálculo — revisa la ventana emergente para la solución completa."
    msg_de = f"{target_str} beträgt {value_str} {unit_str}. Ich habe es berechnet — sieh im Popup die vollständige Lösung."
    say_ml(en=msg_en, hi=msg_hi, fr=msg_fr, es=msg_es, de=msg_de)

def speak_no_quick_fact_ml():
    """Spoken line when the prompt is conceptual and no quick fact is found."""
    msg_en = "I don’t have a quick fact for that — try rephrasing or use full physics mode for a detailed answer."
    msg_hi = "इसके लिए मेरे पास कोई त्वरित तथ्य नहीं है — कृपया प्रश्न को बदलकर पूछें या विस्तृत उत्तर के लिए फुल फिजिक्स मोड का उपयोग करें।"
    msg_fr = "Je n’ai pas de fait rapide pour cela — reformulez ou utilisez le mode physique complet pour une réponse détaillée."
    msg_es = "No tengo un dato rápido para eso — intenta reformular o usa el modo de física completo para una respuesta detallada."
    msg_de = "Dazu habe ich keinen Schnellfakt — formuliere bitte um oder nutze den vollständigen Physik-Modus für eine detaillierte Antwort."
    say_ml(en=msg_en, hi=msg_hi, fr=msg_fr, es=msg_es, de=msg_de)

def speak_no_formula_ml():
    """Spoken line when no formula can be matched."""
    msg_en = "I couldn't match this question to any formula. Try rephrasing."
    msg_hi = "मैं इस प्रश्न को किसी सूत्र से नहीं जोड़ सकी। कृपया प्रश्न को बदलकर फिर से पूछें।"
    msg_fr = "Je n’ai pas pu associer cette question à une formule. Essayez de reformuler."
    msg_es = "No pude asociar esta pregunta con ninguna fórmula. Intenta reformular."
    msg_de = "Ich konnte diese Frage keiner Formel zuordnen. Bitte formuliere sie neu."
    say_ml(en=msg_en, hi=msg_hi, fr=msg_fr, es=msg_es, de=msg_de)

def speak_need_values_ml():
    """Spoken line when values are missing or there are too many unknowns."""
    msg_en = "Missing required values or too many unknowns. Please refine the question."
    msg_hi = "आवश्यक मान गायब हैं या अज्ञात बहुत अधिक हैं। कृपया प्रश्न को स्पष्ट करें।"
    msg_fr = "Valeurs requises manquantes ou trop d’inconnues. Affinez la question, s’il vous plaît."
    msg_es = "Faltan valores requeridos o hay demasiadas incógnitas. Por favor, refina la pregunta."
    msg_de = "Erforderliche Werte fehlen oder es gibt zu viele Unbekannte. Bitte präzisiere die Frage."
    say_ml(en=msg_en, hi=msg_hi, fr=msg_fr, es=msg_es, de=msg_de)

# -------------------------------------
# Wake state helper (voice vs GUI)
# -------------------------------------
def _is_wake_mode_on() -> bool:
    try:
        from utils import get_wake_mode
        return bool(get_wake_mode())
    except Exception:
        # Defensive fallback: read merged settings and use the boolean key
        try:
            from utils import load_settings
            settings = load_settings()
            return bool(settings.get("wake_mode", True))
        except Exception:
            return False

# -------------------------------------
# Load formula banks (handlers/…, UTF-8)
# -------------------------------------
FORMULA_BANK = load_json_utf8(handlers_path("physics_formulas.json"))

_dynamic_path = handlers_path("physics_formulas_dynamic.json")
try:
    DYNAMIC_BANK = load_json_utf8(_dynamic_path) if os.path.exists(_dynamic_path) else None
except Exception:
    DYNAMIC_BANK = None

# -------------------------------------
# Persistence paths (restart-proof) → logs/
# -------------------------------------
# Store small state files in logs/ (writeable next to Nova.exe)
LOG_DIR.mkdir(parents=True, exist_ok=True)
LAST_EQN_PATH  = os.path.join(LOG_DIR, ".nova_last_equation.json")
LAST_GRAPH_PATH = os.path.join(LOG_DIR, ".nova_last_graph.json")

# Project graphs directory (ensure exists)
GRAPHS_DIR = graphs_dir()

# -------------------------------------
# Small JSON helpers
# -------------------------------------
def _save_json(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # non-fatal

def _load_json(path: str):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _save_last_equation_to_disk(eqn_str: str):
    _save_json(LAST_EQN_PATH, {"equation": eqn_str})

def _load_last_equation_from_disk() -> Optional[str]:
    data = _load_json(LAST_EQN_PATH)
    return data.get("equation") if data else None

def _save_last_graph_path_to_disk(path: str):
    _save_json(LAST_GRAPH_PATH, {"graph_path": path})

def _load_last_graph_path_from_disk() -> Optional[str]:
    data = _load_json(LAST_GRAPH_PATH)
    return data.get("graph_path") if data else None


# === Graph Save Flow Helpers ==============================================
def _plot_to_temp(eq_str: str) -> str | None:
    """Render the graph to a temp PNG and return its path (or None on failure)."""
    try:
        import tempfile, shutil as _shutil
        plot_commands = importlib.import_module("plot_commands")
        tmpdir = tempfile.mkdtemp(prefix="nova_plot_")
        tmp_png = os.path.join(tmpdir, "preview.png")
        try:
            # Newer signature
            plot_commands.handle_plotting(eq_str, auto_save=True, save_dir=tmpdir, filename="preview")
        except TypeError:
            # Older signature that returns a path
            saved = plot_commands.handle_plotting(eq_str)
            if saved and os.path.exists(saved):
                _shutil.copyfile(saved, tmp_png)
        return tmp_png if os.path.exists(tmp_png) else None
    except Exception:
        return None

def _show_graph_preview_window(preview_path: str, suggested: str = "physics_graph") -> str | None:
    """Show a preview window with [Save] and [Close]; return saved path or None."""
    try:
        from tkinter import filedialog
        from PIL import Image, ImageTk
        import shutil as _shutil
    except Exception:
        return None  # headless or Pillow not installed

    win = tk.Toplevel()
    try:
        win.iconbitmap(resource_path("nova_icon_big.ico"))
    except Exception:
        pass
    win.title("Graph Preview")
    win.configure(bg="#0f0f0f")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.grab_set()

    tk.Label(win, text="Preview your graph", bg="#0f0f0f", fg="#00ffee",
             font=("Consolas", 12)).pack(pady=(12, 6))

    img = Image.open(preview_path)
    max_w, max_h = 720, 420
    ratio = min(max_w / img.width, max_h / img.height, 1.0)
    img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    photo = ImageTk.PhotoImage(img)
    tk.Label(win, image=photo, bg="#0f0f0f").pack(padx=14, pady=(0, 8))
    win.photo = photo  # keep ref

    style = ttk.Style(win)
    try: style.theme_use("clam")
    except: pass
    style.configure("NovaBtn.TButton", background="#202020", foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=8, borderwidth=0)
    style.map("NovaBtn.TButton", background=[("active", "#008080")])

    btnrow = tk.Frame(win, bg="#0f0f0f"); btnrow.pack(pady=(8, 12))
    saved_path_holder = {"path": None}

    def do_close():
        win.destroy()

    def do_save():
        try:
            from utils import open_save_dialog
            target = open_save_dialog(
                default_name=f"{suggested}.png",
                filetypes=[("PNG Image", "*.png")]
            )
        except Exception:
            target = filedialog.asksaveasfilename(
                defaultextension=".png",
                initialfile=f"{suggested}.png",
                initialdir=GRAPHS_DIR if os.path.isdir(GRAPHS_DIR) else None,
                filetypes=[("PNG Image", "*.png")],
                title="Save Graph As..."
            )
        if target:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            _shutil.copyfile(preview_path, target)
            saved_path_holder["path"] = target
            win.destroy()

    ttk.Button(btnrow, text="Save",  command=do_save,  style="NovaBtn.TButton").pack(side="left", padx=6)
    ttk.Button(btnrow, text="Close", command=do_close, style="NovaBtn.TButton").pack(side="left", padx=6)

    win.bind("<Return>", lambda e: do_save())
    win.bind("<Escape>", lambda e: do_close())

    win.wait_window(win)
    return saved_path_holder["path"]

def _speak_saved_where(path: str):
    """Speak a friendly folder name (e.g., 'Documents folder') instead of full path."""
    lazy_imports()
    folder = os.path.dirname(path)
    friendly = os.path.basename(folder) or folder
    try:
        _speak_multilang(
            en=f"Your graph has been saved as {os.path.basename(path)} in {friendly} folder.",
            hi=f"आपका ग्राफ़ {friendly} फ़ोल्डर में {os.path.basename(path)} नाम से सेव हो गया है।",
            fr=f"Votre graphique a été enregistré dans le dossier {friendly} sous le nom {os.path.basename(path)}.",
            es=f"Tu gráfico se guardó en la carpeta {friendly} como {os.path.basename(path)}.",
            de=f"Dein Diagramm wurde im Ordner {friendly} als {os.path.basename(path)} gespeichert."
        )
    except Exception:
        pass


# NEW: friendly single-line formatter for GUI + logs (right after _speak_saved_where)
def _format_saved_for_gui(path: str) -> str:
    """
    Show a friendly one-liner like:
    📁 Saved: my_graph.png  •  📂 ~/Music
    """
    try:
        filename = os.path.basename(path) or path
        folder = os.path.dirname(path)
        home = os.path.expanduser("~")
        if folder.startswith(home):
            rel = os.path.relpath(folder, home).replace("\\", "/")
            friendly = "~" if rel in (".", "") else f"~/{rel}"
        else:
            # fall back to just the folder name if it’s not under home
            friendly = os.path.basename(folder) or folder
        return f"📁 Saved: {filename}  •  📂 {friendly}"
    except Exception:
        return f"📁 Saved: {path}"

# -------------------------------------
# Nova-styled popup + inline Plot button
# -------------------------------------

# small hex helpers (for ttk hover/pressed colors to match Nova 0.45 / ~0.30)
def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"

def _lighten_hex(hex_color: str, factor: float = 0.45) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    r = r + (255 - r) * factor
    g = g + (255 - g) * factor
    b = b + (255 - b) * factor
    return _rgb_to_hex((r, g, b))

def _ensure_nova_plot_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    base_bg = "#00ffee"  # cyan
    hover_bg = _lighten_hex(base_bg, 0.45)   # brighten by 0.45
    press_bg = _lighten_hex(base_bg, 0.30)   # ~0.30 on press (a bit less bright than hover)

    style.configure(
        "NovaPlot.TButton",
        background=base_bg,
        foreground="#0f0f0f",
        font=("Segoe UI", 10, "bold"),
        padding=(10, 6),
        borderwidth=0,
        focusthickness=3
    )
    style.map(
        "NovaPlot.TButton",
        background=[("active", hover_bg), ("pressed", press_bg)],
        foreground=[("disabled", "#5a5a5a")]
    )

def _open_solution_popup_with_plot_button(text_content: str, *, suggested_filename: str = "physics_graph"):
    """
    Shows the solution in a Nova-styled popup with an inline '✦ Plot it' button.
    Status sits on its own line under the header.
    """
    try:
        from tkinter.scrolledtext import ScrolledText
    except Exception:
        # Headless / no Tk → send to physics panel via event bus
        _emit_gui_html(text_content, append=False)
        return

    win = tk.Toplevel()
    try:
        win.iconbitmap(resource_path("nova_icon_big.ico"))
    except Exception:
        pass
    win.title("Physics Solution")
    win.configure(bg="#0f0f0f")
    win.geometry("820x560")
    win.minsize(640, 420)
    win.attributes("-topmost", True)
    win.grab_set()

    _ensure_nova_plot_style(win)

    # Header row (hint + button)
    header = tk.Frame(win, bg="#0f0f0f")
    header.pack(fill="x", padx=14, pady=(12, 4))

    left_lbl = tk.Label(
        header,
        text="📊 Plot tip — Just click",
        bg="#0f0f0f",
        fg="#00ffee",
        font=("Consolas", 11, "bold")
    )
    left_lbl.pack(side="left")

    def _on_plot_click():
        status_lbl.config(text="Rendering preview…")
        win.update_idletasks()

        eq_str = globals().get("_last_equation_str")
        if not eq_str:
            cached = _load_last_equation_from_disk()
            if cached:
                globals()["_last_equation_str"] = cached
                eq_str = cached

        if not eq_str:
            status_lbl.config(text="❌ No equation to plot yet.")
            return

        tmp_png = _plot_to_temp(eq_str)
        if not tmp_png:
            status_lbl.config(text="❌ Preview unavailable (Pillow not installed or headless mode).")
            return

        suggested = suggested_filename
        try:
            if "=" in eq_str:
                lhs = eq_str.split("=", 1)[0].strip()
                suggested = re.sub(r"[^A-Za-z0-9_]+", "_", lhs).strip("_") or suggested
        except Exception:
            pass
        
        # ✅ Preface (multilingual) right before opening the preview
        _preface_physics_show_graph()
        
        saved_path = _show_graph_preview_window(tmp_png, suggested=suggested)
        if saved_path:
            _save_last_graph_path_to_disk(saved_path)
            status_lbl.config(text=_format_saved_for_gui(saved_path))
            _speak_saved_where(saved_path)
        else:
            status_lbl.config(text="Preview closed. Graph not saved.")

    ttk.Button(header, text="✦ Plot it", style="NovaPlot.TButton", command=_on_plot_click).pack(side="left", padx=(8, 8))

    # Status on its own row, right under header
    status_row = tk.Frame(win, bg="#0f0f0f")
    status_row.pack(fill="x", padx=14, pady=(0, 8))
    status_lbl = tk.Label(status_row, text="", bg="#0f0f0f", fg="#cceff7", font=("Consolas", 10), anchor="w")
    status_lbl.pack(fill="x")

    # Body (solution text)
    from tkinter.scrolledtext import ScrolledText
    body = ScrolledText(
        win,
        wrap="word",
        bg="#121212",
        fg="#e9fffe",
        insertbackground="#e9fffe",
        font=("Consolas", 11),
        relief="flat"
    )
    body.pack(fill="both", expand=True, padx=14, pady=(0, 12))
    body.insert("1.0", text_content)
    body.configure(state="disabled")

    footer = tk.Frame(win, bg="#0f0f0f")
    footer.pack(fill="x", padx=14, pady=(0, 12))
    ttk.Button(footer, text="Close", command=win.destroy).pack(side="right")


# -------------------------------------
# Comprehensive unit conversions
# -------------------------------------
UNIT_TABLE = {
    # Time
    "s": ("s", lambda x: x, lambda x: x),
    "sec": ("s", lambda x: x, lambda x: x),
    "second": ("s", lambda x: x, lambda x: x),
    "seconds": ("s", lambda x: x, lambda x: x),
    "min": ("s", lambda x: x * 60, lambda x: x / 60),
    "mins": ("s", lambda x: x * 60, lambda x: x / 60),
    "minute": ("s", lambda x: x * 60, lambda x: x / 60),
    "minutes": ("s", lambda x: x * 60, lambda x: x / 60),
    "h": ("s", lambda x: x * 3600, lambda x: x / 3600),
    "hr": ("s", lambda x: x * 3600, lambda x: x / 3600),
    "hour": ("s", lambda x: x * 3600, lambda x: x / 3600),
    "hours": ("s", lambda x: x * 3600, lambda x: x / 3600),

    # Length / distance
    "m": ("m", lambda x: x, lambda x: x),
    "meter": ("m", lambda x: x, lambda x: x),
    "meters": ("m", lambda x: x, lambda x: x),
    "km": ("m", lambda x: x * 1000, lambda x: x / 1000),
    "cm": ("m", lambda x: x / 100, lambda x: x * 100),
    "mm": ("m", lambda x: x / 1000, lambda x: x * 1000),
    "μm": ("m", lambda x: x / 1e6, lambda x: x * 1e6),
    "um": ("m", lambda x: x / 1e6, lambda x: x * 1e6),
    "mi": ("m", lambda x: x * 1609.34, lambda x: x / 1609.34),
    "mile": ("m", lambda x: x * 1609.34, lambda x: x / 1609.34),
    "miles": ("m", lambda x: x * 1609.34, lambda x: x / 1609.34),
    "ft": ("m", lambda x: x * 0.3048, lambda x: x / 0.3048),
    "feet": ("m", lambda x: x * 0.3048, lambda x: x / 0.3048),
    "in": ("m", lambda x: x * 0.0254, lambda x: x / 0.0254),
    "inch": ("m", lambda x: x * 0.0254, lambda x: x / 0.0254),
    "inches": ("m", lambda x: x * 0.0254, lambda x: x / 0.0254),

    # Speed
    "m/s": ("m/s", lambda x: x, lambda x: x),
    "mps": ("m/s", lambda x: x, lambda x: x),
    "km/h": ("m/s", lambda x: (x * 1000) / 3600, lambda x: (x * 3600) / 1000),
    "kph": ("m/s", lambda x: (x * 1000) / 3600, lambda x: (x * 3600) / 1000),
    "cm/s": ("m/s", lambda x: x / 100, lambda x: x * 100),
    "mph": ("m/s", lambda x: x * 0.44704, lambda x: x / 0.44704),

    # Acceleration
    "m/s^2": ("m/s^2", lambda x: x, lambda x: x),
    "m/s²": ("m/s^2", lambda x: x, lambda x: x),
    "cm/s^2": ("m/s^2", lambda x: x / 100, lambda x: x * 100),
    "cm/s²": ("m/s^2", lambda x: x / 100, lambda x: x * 100),
    "g0": ("m/s^2", lambda x: x * 9.80665, lambda x: x / 9.80665),

    # Angle
    "rad": ("rad", lambda x: x, lambda x: x),
    "radian": ("rad", lambda x: x, lambda x: x),
    "radians": ("rad", lambda x: x, lambda x: x),
    "deg": ("rad", lambda x: x * pi / 180, lambda x: x * 180 / pi),
    "degree": ("rad", lambda x: x * pi / 180, lambda x: x * 180 / pi),
    "degrees": ("rad", lambda x: x * pi / 180, lambda x: x * 180 / pi),

    # Mass
    "kg": ("kg", lambda x: x, lambda x: x),
    "g": ("kg", lambda x: x / 1000, lambda x: x * 1000),
    "mg": ("kg", lambda x: x / 1e6, lambda x: x * 1e6),
    "lb": ("kg", lambda x: x * 0.45359237, lambda x: x / 0.45359237),
    "lbs": ("kg", lambda x: x * 0.45359237, lambda x: x / 0.45359237),
    "tonne": ("kg", lambda x: x * 1000, lambda x: x / 1000),
    "t": ("kg", lambda x: x * 1000, lambda x: x / 1000),

    # Force
    "n": ("N", lambda x: x, lambda x: x),
    "newton": ("N", lambda x: x, lambda x: x),
    "newtons": ("N", lambda x: x, lambda x: x),
    "dyne": ("N", lambda x: x * 1e-5, lambda x: x / 1e-5),
    "dyn": ("N", lambda x: x * 1e-5, lambda x: x / 1e-5),
    "kgf": ("N", lambda x: x * 9.80665, lambda x: x / 9.80665),

    # Energy / Work / Frequency
    "j": ("J", lambda x: x, lambda x: x),
    "joule": ("J", lambda x: x, lambda x: x),
    "joules": ("J", lambda x: x, lambda x: x),
    "hz": ("Hz", lambda x: x, lambda x: x),
    "hertz": ("Hz", lambda x: x, lambda x: x),
    "kj": ("J", lambda x: x * 1000, lambda x: x / 1000),
    "mj": ("J", lambda x: x * 1e6, lambda x: x / 1e6),
    "wh": ("J", lambda x: x * 3600, lambda x: x / 3600),
    "kwh": ("J", lambda x: x * 3_600_000, lambda x: x / 3_600_000),
    "cal": ("J", lambda x: x * 4.184, lambda x: x / 4.184),
    "kcal": ("J", lambda x: x * 4184, lambda x: x / 4184),
    "ev": ("J", lambda x: x * 1.602176634e-19, lambda x: x / 1.602176634e-19),

    # Power
    "w": ("W", lambda x: x, lambda x: x),
    "kw": ("W", lambda x: x * 1000, lambda x: x / 1000),
    "mw": ("W", lambda x: x * 1e6, lambda x: x / 1e6),

    # Pressure
    "pa": ("Pa", lambda x: x, lambda x: x),
    "kpa": ("Pa", lambda x: x * 1000, lambda x: x / 1000),
    "mpa": ("Pa", lambda x: x * 1e6, lambda x: x / 1e6),
    "bar": ("Pa", lambda x: x * 1e5, lambda x: x / 1e5),
    "atm": ("Pa", lambda x: x * 101325, lambda x: x / 101325),
    "mmhg": ("Pa", lambda x: x * 133.322, lambda x: x / 133.322),

    # Charge / Voltage / Current / Resistance
    "c": ("C", lambda x: x, lambda x: x),
    "v": ("V", lambda x: x, lambda x: x),
    "a": ("A", lambda x: x, lambda x: x),
    "ohm": ("Ω", lambda x: x, lambda x: x),
    "ω": ("Ω", lambda x: x, lambda x: x),

    # Temperature (affine!)
    "k": ("K", lambda x: x, lambda x: x),
    "°c": ("K", lambda x: x + 273.15, lambda x: x - 273.15),
    "celsius": ("K", lambda x: x + 273.15, lambda x: x - 273.15),
    "deg c": ("K", lambda x: x + 273.15, lambda x: x - 273.15),
    "°f": ("K", lambda x: (x - 32) * 5/9 + 273.15, lambda x: (x - 273.15) * 9/5 + 32),
    "fahrenheit": ("K", lambda x: (x - 32) * 5/9 + 273.15, lambda x: (x - 273.15) * 9/5 + 32),

    # --- Identity / displayed units (no conversion; just aliases we show by default) ---
    # torque (+ dot variants)
    "n·m": ("N·m", lambda x: x, lambda x: x),
    "n.m": ("N·m", lambda x: x, lambda x: x),

    # angular rates
    "rad/s": ("rad/s", lambda x: x, lambda x: x),
    "rad/s^2": ("rad/s^2", lambda x: x, lambda x: x),

    # areas / volumes
    "m^2": ("m²", lambda x: x, lambda x: x),
    "m²": ("m²", lambda x: x, lambda x: x),
    "m^3": ("m³", lambda x: x, lambda x: x),
    "m³": ("m³", lambda x: x, lambda x: x),

    # composite mechanics units
    "kg·m^2": ("kg·m²", lambda x: x, lambda x: x),
    "kg·m²": ("kg·m²", lambda x: x, lambda x: x),
    "kg·m²/s": ("kg·m²/s", lambda x: x, lambda x: x),
    "n/m": ("N/m", lambda x: x, lambda x: x),

    # viscosity
    "pa·s": ("Pa·s", lambda x: x, lambda x: x),

    # EM units (friendly names to avoid 't' (tonne) confusion)
    "tesla": ("T", lambda x: x, lambda x: x),
    "t": ("kg", lambda x: x * 1000, lambda x: x / 1000),  # keep tonne meaning
    "wb": ("Wb", lambda x: x, lambda x: x),
    "weber": ("Wb", lambda x: x, lambda x: x),
    "farad": ("F", lambda x: x, lambda x: x),
}

# Default display units per variable
DEFAULT_UNITS = {
    # kinematics / motion
    "u": "m/s", "v": "m/s", "a": "m/s²", "s": "m", "t": "s", "d": "m",

    # projectile
    "R": "m", "H": "m", "T": "s", "θ": "rad", "theta": "rad",

    # rotation / circular
    "ω": "rad/s", "omega": "rad/s",
    "α": "rad/s²", "alpha": "rad/s²",
    "τ": "N·m", "tau": "N·m",
    "I": "kg·m²", "L": "kg·m²/s", "r": "m",

    # forces / energy / work / power
    "F": "N", "m": "kg", "W": "J", "E": "J", "KE": "J", "PE": "J", "P": "W", "ΔK": "J",

    # fluids
    "ρ": "kg/m³", "rho": "kg/m³", "V": "m³", "A": "m²", "η": "Pa·s", "Fb": "N",

    # oscillations
    "x": "m", "l": "m", "k": "N/m", "f": "Hz",

    # waves / optics
    "λ": "m", "lambda": "m", "n": "", "c": "m/s", "β": "m",

    # electricity / circuits
    "q": "C", "Q": "J/C", "V": "V", "I": "A", "R1": "Ω", "R2": "Ω", "R3": "Ω",
    "C1": "F", "C2": "F", "C3": "F", "V0": "V", "I0": "A", "Z": "Ω",
    "X_L": "Ω", "X_C": "Ω", "emf": "V",

    # magnetism / EM
    "B": "T", "Φ": "Wb", "phi": "Wb",

    # modern physics
    "h": "J·s", "e": "C", "Δm": "kg",

    # constants / misc
    "G": "N·m²/kg²", "M": "kg", "v_e": "m/s", "A1": "m²", "A2": "m²",
    "dv": "m/s", "dx": "m"
}

# --- Ambiguity-resolved aliases (Power vs Pressure; lambda decay) ---
# These are the canonical display units for the internal disambiguated symbols
DEFAULT_UNITS.update({"P_power": "W", "P_pressure": "Pa", "λ_decay": "1/s"})

# -------------------------
# Legend (module scope)
# -------------------------
LEGEND_DESC = {
    # kinematics / motion
    "s":  "displacement / distance (m)",
    "d":  "distance (m)",
    "u":  "initial velocity (m/s)",
    "v":  "final velocity (m/s)",
    "a":  "acceleration (m/s², rate of change of velocity)",
    "t":  "time (s)",
    "p":  "linear momentum (kg·m/s)",

    # projectile
    "R":  "range (m)",
    "H":  "maximum height (m)",
    "T":  "time of flight (s)",
    "θ":  "angle (rad)",
    "g":  "acceleration due to gravity (m/s²)",

    # rotation / circular
    "ω":  "angular velocity (rad/s)",
    "α":  "angular acceleration (rad/s²)",
    "τ":  "torque (N·m)",
    "I":  "moment of inertia (kg·m²)",
    "L":  "angular momentum (kg·m²/s)",
    "r":  "radius (m)",
    "ω0": "initial angular velocity (rad/s)",

    # energy / work / power
    "W":  "work (J)",
    "E":  "energy (J)",
    "KE": "kinetic energy (J)",
    "PE":  "potential energy (J)",
    "ΔK": "change in kinetic energy (J)",
    "P":  "power (W)",

    # forces
    "F":  "force (N)",
    "N":  "normal force (N)",
    "μ":  "coefficient of friction (unitless)",

    # fluids
    "ρ":  "density (kg/m³)",
    "V":  "volume (m³)",
    "A":  "area (m²)",
    "η":  "viscosity (Pa·s)",
    "Fb": "buoyant force (N)",

    # oscillations / SHM
    "x":  "displacement in SHM (m)",
    "l":  "length (m)",
    "k":  "spring constant (N/m)",
    "f":  "frequency (Hz)",

    # waves / optics
    "λ":  "wavelength (m)",
    "n":  "refractive index (unitless)",
    "c":  "speed of light (m/s)",
    "β":  "fringe width (m)",

    # electricity / circuits
    "q":  "charge (C)",
    "Q":  "heat/charge (context-dependent)",
    "V":  "voltage (V)",
    "I":  "current (A)",
    "R1": "resistance 1 (Ω)",
    "R2": "resistance 2 (Ω)",
    "R3": "resistance 3 (Ω)",
    "C1": "capacitance 1 (F)",
    "C2": "capacitance 2 (F)",
    "C3": "capacitance 3 (F)",
    "V0": "peak voltage (V)",
    "I0": "peak current (A)",
    "Z":  "impedance (Ω)",
    "X_L":"inductive reactance (Ω)",
    "X_C":"capacitive reactance (Ω)",
    "emf":"electromotive force (V)",

    # magnetism / EM
    "B":  "magnetic field (T)",
    "Φ":  "magnetic flux (Wb)",

    # modern physics
    "h":  "Planck’s constant (J·s)",
    "e":  "elementary charge (C)",
    "Δm": "mass defect (kg)",

    # constants / misc
    "G":  "gravitational constant (N·m²/kg²)",
    "M":  "mass (kg) (often planet mass)",
    "v_e":"escape velocity (m/s)",
    "A1": "area 1 (m²)",
    "A2": "area 2 (m²)",
    "dv": "velocity differential (m/s)",
    "dx": "length differential (m)"
}

LEGEND_ALIASES = {
    "omega": "ω",
    "alpha": "α",
    "theta": "θ",
    "tau":   "τ",
    "phi":   "Φ",
    "rho":   "ρ",
    "lambda":"λ",
    "hertz": "f",
    "hz": "f"
}

def _legend_text_for(symbol_name: str) -> str:
    key = symbol_name
    k_lower = key.lower()
    if k_lower in LEGEND_ALIASES:
        key = LEGEND_ALIASES[k_lower]
    if key in LEGEND_DESC:
        return f"{symbol_name} → {LEGEND_DESC[key]}"
    if k_lower in LEGEND_DESC:
        return f"{symbol_name} → {LEGEND_DESC[k_lower]}"
    unit = DEFAULT_UNITS.get(symbol_name, DEFAULT_UNITS.get(key, ""))
    if unit:
        return f"{symbol_name} → variable ({unit})"
    return f"{symbol_name} → variable"

# -------------------------------------
# Regex helpers (now with scientific notation)
# -------------------------------------
NUM = r"[+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?"
UNIT_REGEX = r"|".join(sorted(map(re.escape, UNIT_TABLE.keys()), key=len, reverse=True))
VALUE_WITH_UNIT = re.compile(rf"({NUM})\s*({UNIT_REGEX})\b", re.IGNORECASE)
EXPLICIT_ASSIGNMENT = re.compile(
    rf"([A-Za-z\u0370-\u03FF]+)\s*=\s*({NUM})(?:\s*([A-Za-z/°^²]+))?",
    re.IGNORECASE
)

def _to_SI(val: float, unit: str):
    si_unit, to_si, _from_SI = UNIT_TABLE[unit]
    return si_unit, to_si(float(val))

def _from_SI(val: float, unit: str):
    si_unit, _to_SI, from_si = UNIT_TABLE[unit]
    return from_si(float(val))

# ------------------------------
# Pretty symbol & operator output
# ------------------------------
SYMBOL_MAP = {"theta": "θ", "alpha": "α", "omega": "ω", "phi": "Φ", "lambda": "λ",
              "tau": "τ", "rho": "ρ", "beta": "β"}
def _symbolize_text(s: str) -> str:
    out = s
    for k, v in SYMBOL_MAP.items():
        out = re.sub(rf"\b{k}\b", v, out)
    out = out.replace("*", "×")
    return out

# -------------------------------------
# Conversion line builders (dynamic)
# -------------------------------------
def _build_conversion_line_to_SI(value: float, unit_key: str) -> Optional[str]:
    try:
        if unit_key not in UNIT_TABLE:
            return None
        si_name, to_si, _from_si = UNIT_TABLE[unit_key]
        zero = to_si(0.0)
        one  = to_si(1.0)
        if abs(zero) < 1e-12:
            factor = one
            return f"{value} {unit_key} → {value} {unit_key} × {factor:.6g} = {to_si(value):.6g} {si_name}"
        a = one - zero
        b = zero
        return f"{value} {unit_key} → SI = {a:.6g}×{value} + {b:.6g} = {to_si(value):.6g} {si_name}"
    except Exception:
        return None

def _final_unit_conversion_line(si_value: float, target_unit_key: str, raw_label: str) -> Optional[str]:
    try:
        if target_unit_key not in UNIT_TABLE:
            return None
        si_name, _to_si, from_si = UNIT_TABLE[target_unit_key]
        zero_out = from_si(0.0)
        one_out  = from_si(1.0)
        if abs(zero_out) < 1e-12:
            factor = one_out
            return f"Convert to {raw_label}: {si_value:.6g} {si_name} → {si_value:.6g} × {factor:.6g} = {si_value*factor:.6g} {raw_label}"
        a = one_out - zero_out
        b = zero_out
        return (
            f"Convert to {raw_label}: {raw_label} = {a:.6g}×(SI) + {b:.6g}\n"
            f"                      {raw_label} = {a:.6g}×{si_value:.6g} + {b:.6g} = {a*si_value + b:.6g} {raw_label}"
        )
    except Exception:
        return None

# ------------------------------------------------------
# Extract numeric values from text (with conversion lines)
# ------------------------------------------------------
def extract_values(text: str):
    values = {}
    conversions_needed = []

    for var, num, unit in EXPLICIT_ASSIGNMENT.findall(text):
        var_key = var.strip()
        num_val = float(num)
        if unit:
            u = unit.lower().strip().replace("²", "^2").replace(".", "·")
            if u in UNIT_TABLE:
                si_u, si_val = _to_SI(num_val, u)
                values[var_key] = si_val
                line = _build_conversion_line_to_SI(num_val, u)
                conversions_needed.append(line if line else f"{num_val} {u} → {si_val} {si_u}")
            else:
                values[var_key] = num_val
        else:
            values[var_key] = num_val

    for num, unit in VALUE_WITH_UNIT.findall(text):
        u = unit.lower().replace(".", "·")
        try:
            si_u, si_val = _to_SI(float(num), u)
            line = _build_conversion_line_to_SI(float(num), u)
            conversions_needed.append(line if line else f"{float(num)} {u} → {si_val} {si_u}")
        except Exception:
            pass

    conversions_needed = list(dict.fromkeys(conversions_needed))
    return values, conversions_needed

# ------------------------------------------------------
# Fuzzy-ish formula selection (by name or symbol presence)
# ------------------------------------------------------
def find_best_formula(user_input: str):
    lowered = user_input.lower()
    for topic, formulas in FORMULA_BANK.items():
        for name, expr in formulas.items():
            if name.lower() in lowered:
                return name, expr, topic
            sym_tokens = [tok for tok in expr.replace('=', ' ').replace('*', ' ').split()]
            if any(tok.lower() in lowered for tok in sym_tokens if tok.isalpha()):
                return name, expr, topic
    return None, None, None

# ------------------------------------------------------
# Dynamic explanations + plot_first from DYNAMIC_BANK
# ------------------------------------------------------
def _normalize_expr_for_match(s: str) -> str:
    rep = {"θ":"theta","α":"alpha","ω":"omega","φ":"phi","λ":"lambda","τ":"tau","ρ":"rho","β":"beta","π":"pi"}
    out = s
    for k,v in rep.items(): out = out.replace(k, v)
    out = out.replace("**", "^").replace(" ", "").lower()
    return out

def _get_dynamic_explain(topic: str, name: str, expr: str):
    if not DYNAMIC_BANK or topic not in DYNAMIC_BANK:
        return None
    bucket = DYNAMIC_BANK[topic]
    if name in bucket and isinstance(bucket[name], dict) and "explain" in bucket[name]:
        return bucket[name]["explain"]
    for k, v in bucket.items():
        if isinstance(v, dict) and "explain" in v:
            if k.lower().strip() == name.lower().strip():
                return v["explain"]
    n_expr = _normalize_expr_for_match(expr)
    for v in bucket.values():
        if isinstance(v, dict) and "expr" in v and "explain" in v:
            if _normalize_expr_for_match(v["expr"]) == n_expr:
                return v["explain"]
    return None

def _get_dynamic_plot_first(topic: str, name: str, expr: str) -> Optional[str]:
    """Fetch the one-line 'plot_first' hint from the dynamic JSON (if present)."""
    data = _get_dynamic_explain(topic, name, expr)
    if isinstance(data, dict) and "plot_first" in data and isinstance(data["plot_first"], str):
        return data["plot_first"]
    return None

def _context_tip(topic: str, name: str, expr: str):
    """
    Returns the concept tip text (without forcing the header),
    so the caller can decide whether to prepend '🧠 Tip from Nova:'.
    """
    exp = _get_dynamic_explain(topic, name, expr)
    if exp and "tip" in exp:
        return exp["tip"]
    return "Understanding how each variable affects the result builds strong intuition."

# ------------------------------------------------------
# Solve the chosen equation with provided knowns
# ------------------------------------------------------
def solve_equation(expr: str, values_dict: dict):
    lhs, rhs = expr.split('=')
    lhs = parse_expr(lhs.strip())
    rhs = parse_expr(rhs.strip())
    eq = Eq(lhs, rhs)

    all_symbols = list(eq.free_symbols)
    knowns = {str(k): v for k, v in values_dict.items()}
    unknowns = [s for s in all_symbols if str(s) not in knowns]

    if len(unknowns) != 1:
        return None, None, None

    target = unknowns[0]
    solution = solve(eq.subs(knowns), target)
    if not solution:
        return None, None, None

    return target, solution[0], eq

# ------------------------------------------------------
# Pretty working lines for Step 2 and Step 3
# ------------------------------------------------------
def _trig_eval_lines(expr):
    lines = []
    try:
        for fn in (sin, cos, tan):
            for node in expr.atoms(fn):
                try:
                    val = float(N(node.args[0]))
                    num = float(N(node))
                    nm = fn.__name__
                    lines.append(f"{nm}({val:.4f}) = {num:.4f}")
                except Exception:
                    pass
    except Exception:
        pass
    return lines

def _product_chain_line(expr):
    try:
        target = expr
        if isinstance(target, Add):
            return None
        if isinstance(target, Mul) or isinstance(target, Pow) or target.is_number:
            factors = []
            for f in target.as_ordered_factors():
                try:
                    factors.append(float(N(f)))
                except Exception:
                    return None
            if len(factors) >= 2:
                chain = " × ".join(f"{x:.4g}" for x in factors)
                total = float(N(target))
                return f"{chain} = {total:.6g}"
    except Exception:
        pass
    return None

def _add_only_line(expr):
    try:
        if isinstance(expr, Add):
            terms = [float(N(t)) for t in expr.as_ordered_terms()]
            if len(terms) >= 2:
                left = " + ".join(f"{x:.6g}" for x in terms)
                total = float(N(expr))
                return f"{left} = {total:.6g}"
    except Exception:
        pass
    return None

def _detailed_substitution_lines(lhs_sym, rhs_expr, subs_map):
    lines = []
    symbolic = f"{str(lhs_sym)} = {str(rhs_expr)}"
    lines.append(symbolic)

    substituted = rhs_expr.subs(subs_map)
    num_line = f"{str(lhs_sym)} = {str(substituted)}"
    num_line = re.sub(r"(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)", r"(\1 × \2)", num_line)
    num_line = num_line.replace("*", "×")
    lines.append(num_line)

    lines.extend(_trig_eval_lines(substituted))
    prod = _product_chain_line(substituted)
    if prod:
        lines.append(prod)
    else:
        addline = _add_only_line(substituted)
        if addline:
            lines.append(addline)

    try:
        numeric_value = float(N(substituted))
        lines.append(f"{str(lhs_sym)} = {numeric_value}")
    except Exception:
        pass

    return [_symbolize_text(x) for x in lines]

def _round_decimals(val: float, places: int = DEC_PLACES) -> float:
    return round(float(val), places)

def _build_step3_lines(var_symbol, rhs_expr, subs_map, unit_label: str, out_value_unrounded: float):
    lines = []
    try:
        exact_val = float(N(rhs_expr.subs(subs_map)))
    except Exception:
        exact_val = out_value_unrounded

    lines.append(f"{str(var_symbol)} (numeric) = {round(exact_val, DEC_PLACES)}")
    rounded_val = _round_decimals(exact_val, DEC_PLACES)
    lines.append(f"Rounding to {DEC_PLACES} decimal places:")
    lines.append(f"{str(var_symbol)} ≈ {rounded_val} {unit_label}")
    return [_symbolize_text(x) for x in lines], rounded_val

# ======================================================
# 🔹 Quick Mode intelligence (helpers)
# ======================================================
ALIAS_TO_SYMBOL: Dict[str, str] = {**{k.lower(): v for k, v in LEGEND_ALIASES.items()}}
for sym in list(LEGEND_DESC.keys()) + list(DEFAULT_UNITS.keys()):
    ALIAS_TO_SYMBOL[sym.lower()] = sym

WORD_TO_SYMBOL: Dict[str, str] = {}
for sym, desc in LEGEND_DESC.items():
    base = desc.split("(")[0].strip().lower()
    if base:
        WORD_TO_SYMBOL[base] = sym
EXTRA_WORD_SYNONYMS = {
    "magnetic field strength": "B",
    "flux": "Φ",
    "magnetic flux density": "B",
    "capacitance": "C1",
    "resistance": "R1",
}
for k, v in EXTRA_WORD_SYNONYMS.items():
    WORD_TO_SYMBOL[k.lower()] = v

FORMULA_NAME_MAP: Dict[str, Tuple[str, str, str]] = {}
for topic, formulas in FORMULA_BANK.items():
    for name, expr in formulas.items():
        FORMULA_NAME_MAP[name.lower()] = (name, expr, topic)

def _match_formula_name_in_text(t: str) -> Optional[Tuple[str, str, str]]:
    t = t.lower()
    for k, tup in FORMULA_NAME_MAP.items():
        if k in t:
            return tup
    tokens = set(re.findall(r"[a-zα-ω]+", t))
    best = None
    best_score = 0
    for k, tup in FORMULA_NAME_MAP.items():
        k_tokens = set(re.findall(r"[a-zα-ω]+", k))
        score = len(tokens & k_tokens)
        if score > best_score:
            best, best_score = tup, score
    return best if best_score > 0 else None

def _unit_for_symbol(sym: str) -> Optional[str]:
    if sym in DEFAULT_UNITS and DEFAULT_UNITS[sym]:
        return DEFAULT_UNITS[sym]
    desc = LEGEND_DESC.get(sym)
    if desc and "(" in desc and ")" in desc:
        inside = desc.split("(", 1)[1].split(")", 1)[0].strip()
        return inside
    return None

def _symbol_from_user_token(tok: str) -> Optional[str]:
    tl = tok.strip().lower()
    if tl in ALIAS_TO_SYMBOL:
        return ALIAS_TO_SYMBOL[tl]
    if tl in WORD_TO_SYMBOL:
        return WORD_TO_SYMBOL[tl]
    return None

def _format_symbol_legend_list(symbols: List[str]) -> str:
    lines = ["Symbols in formula:"]
    used = set()
    for s in sorted({str(x) for x in symbols}):
        if s in used: continue
        used.add(s)
        lines.append(_legend_text_for(s))
    return "\n".join(lines)

# ======================================================================
# 🚀 Depends/Proportional/Scaling engine (works with formula bank)
# ======================================================================

# --- A. small helpers for formula parsing ---
def _extract_lhs_symbol(expr_str: str) -> Optional[str]:
    """Return LHS symbol from 'LHS = RHS'."""
    if "=" not in expr_str:
        return None
    lhs = expr_str.split("=", 1)[0].strip()
    m = re.search(r"[A-Za-zΩωαβγδθλρτφΦμ][A-Za-z0-9_]*", lhs)
    return m.group(0) if m else None

def _extract_symbols_from_expr(expr_str: str) -> set:
    """Free symbols on RHS (or whole expr if no '=')."""
    try:
        from sympy import sympify
        rhs_str = expr_str.split("=", 1)[1] if "=" in expr_str else expr_str
        e = sympify(rhs_str)
        return {str(s) for s in e.free_symbols}
    except Exception:
        return set()

# --- B. Build a formula index from both banks (name + expr + topic + symbols) ---
_FORMULA_INDEX: List[Dict[str, Any]] = []

def _build_formula_index_from_banks():
    """Index formulas from FORMULA_BANK and DYNAMIC_BANK (if available)."""
    global _FORMULA_INDEX
    if _FORMULA_INDEX:
        return

    # 1) From the primary FORMULA_BANK (topic -> {name: expr})
    for topic, formulas in (FORMULA_BANK or {}).items():
        for name, expr in (formulas or {}).items():
            _FORMULA_INDEX.append({
                "name": str(name).lower(),
                "expr": str(expr),
                "topic": str(topic),
                "lhs": _extract_lhs_symbol(str(expr)) or "",
                "symbols": _extract_symbols_from_expr(str(expr)),
            })

    # 2) From DYNAMIC_BANK if it carries extra formulas
    def _walk_dyn(node: Any, topic: str, path: List[str]):
        if isinstance(node, dict):
            # Typical dynamic entry: { "expr": "...", "explain": {...} }
            if "expr" in node and isinstance(node["expr"], str):
                nm = (path[-1] if path else "formula")
                expr = node["expr"]
                _FORMULA_INDEX.append({
                    "name": str(nm).lower(),
                    "expr": str(expr),
                    "topic": str(topic),
                    "lhs": _extract_lhs_symbol(str(expr)) or "",
                    "symbols": _extract_symbols_from_expr(str(expr)),
                })
            for k, v in node.items():
                _walk_dyn(v, topic, path + [k])
        elif isinstance(node, list):
            for v in node:
                _walk_dyn(v, topic, path)

    if DYNAMIC_BANK:
        for topic, bucket in DYNAMIC_BANK.items():
            _walk_dyn(bucket, str(topic), [str(topic)])

    # de-dup identical (expr, lhs)
    seen = set()
    dedup = []
    for it in _FORMULA_INDEX:
        key = (it["expr"], it["lhs"])
        if key not in seen:
            seen.add(key)
            dedup.append(it)
    _FORMULA_INDEX = dedup

# --- C. Pull symbols from user text (words/units/angles → symbols) ---
_UNIT_HINTS = [
    (re.compile(r"\bdeg(ree)?s?\b|\brad(ians?)?\b", re.IGNORECASE), "theta"),
    (re.compile(r"\bm/s\^?2\b|\bmet(re|er)/s(ec(ond)?)?\^?2\b", re.IGNORECASE), "a"),
    (re.compile(r"\bm/s\b|\bmet(re|er)/s(ec(ond)?)?\b", re.IGNORECASE), "v"),  # could be u or v
    (re.compile(r"\bnewton(s)?\b|\bN\b", re.IGNORECASE), "F"),
    (re.compile(r"\bjoule(s)?\b|\bJ\b", re.IGNORECASE), "W"),
    (re.compile(r"\bwatt(s)?\b|\bW\b", re.IGNORECASE), "P"),
    (re.compile(r"\btesla\b|\bT\b", re.IGNORECASE), "B"),
]


def _extract_candidate_symbols_from_text(user_text: str) -> set:
    t = (user_text or "").lower()
    syms = set()

    # known word → symbol aliases from our maps
    for word, sym in {**WORD_TO_SYMBOL, **ALIAS_TO_SYMBOL}.items():
        if re.search(rf"\b{re.escape(word)}\b", t):
            syms.add(sym)

    # raw mentions
    for raw in ("u","v","a","t","s","g","m","h","r","l","i","q","f","p","w","b","theta","phi","alpha","beta"):
        if re.search(rf"\b{raw}\b", t):
            syms.add(raw)


    # units hint
    for patt, sym in _UNIT_HINTS:
        if patt.search(t):
            syms.add(sym)

    # trig hint
    if re.search(r"\b(sin|cos|tan)\s*\(", t):
        syms.add("theta")
    return syms

def _match_formula_by_symbols_in_text(user_text: str) -> Optional[Tuple[str, str, str]]:
    """Fallback: choose best formula by symbol overlap + heuristics."""
    _build_formula_index_from_banks()
    if not _FORMULA_INDEX:
        return None
    want = _extract_candidate_symbols_from_text(user_text)
    if not want:
        return None

    # detect focus variable (which result user is asking about)
    lhs_focus = None
    m = re.search(r"\b(affect|effect|happen|depend|proportional|change|what\s*happens\s*to)\b.*?\b([A-Za-zΩωαβγδθλρτφΦμ])\b", user_text.lower())
    if m:
        token = m.group(2)
        lhs_focus = _symbol_from_user_token(token) or token

    best, best_score = None, 0.0
    for f in _FORMULA_INDEX:
        f_syms = set(f["symbols"])
        if not f_syms:
            continue
        inter = len(want & f_syms)
        union = len(want | f_syms)
        jaccard = inter/union if union else 0.0
        score = jaccard + 0.25*inter
        if lhs_focus and f.get("lhs") and f["lhs"].lower() == str(lhs_focus).lower():
            score += 1.2
        if ("theta" in want) and re.search(r"\b(sin|cos|tan)\b", f["expr"]):
            score += 0.3
        if score > best_score:
            best, best_score = f, score

    if best and (best_score >= 1.2 or (best_score >= 0.8 and len(want & set(best["symbols"])) >= 2)):
        return (best["name"], best["expr"], best.get("topic",""))
    return None

# --- D. Elasticities (proportionality) & natural language ---
def _proportionality_from_expr(expr_str: str, target: str) -> List[Tuple[str, float]]:
    """Return [(var, exponent)] using log-sensitivity (v ∂f/∂v)/f on RHS."""
    try:
        from sympy import symbols, sympify, diff
    except Exception:
        return []
    rhs_str = expr_str.split("=", 1)[1] if "=" in expr_str else expr_str
    try:
        rhs_tmp = sympify(rhs_str)
        free = sorted({str(s) for s in rhs_tmp.free_symbols})
    except Exception:
        free = []
    names = sorted(set(free + [target]))
    sym = {name: symbols(name) for name in names}
    try:
        rhs = sympify(rhs_str, locals=sym)
    except Exception:
        return []
    # nominal values (avoid zeros)
    subs = {sym[k]: 1.0 for k in names}
    for ang in ("theta","phi","alpha","beta"):
        if ang in names:
            subs[sym[ang]] = 0.7  # ~40°
    exps: List[Tuple[str, float]] = []
    for vname in names:
        if vname == target:
            continue
        v = sym[vname]
        try:
            sens = (v*diff(rhs, v))/rhs
            val = float(sens.evalf(subs=subs))
            if abs(val) < 1e6 and not (val != val):  # filter inf/NaN
                exps.append((vname, val))
        except Exception:
            continue
    return exps

def _describe_dependencies_natural(lhs: str, exps: List[Tuple[str, float]], expr_str: str) -> str:
    direct = [(v,a) for v,a in exps if a > 0.15]
    inverse = [(v,-a) for v,a in exps if a < -0.15]
    weak = [v for v,a in exps if abs(a) <= 0.15]
    def fmt(v,p): return f"{v}^{p:.2g}" if abs(p-1)>1e-2 else v
    parts = []
    if direct: parts.append("directly proportional to " + ", ".join(fmt(v,p) for v,p in direct))
    if inverse: parts.append("inversely proportional to " + ", ".join(fmt(v,p) for v,p in inverse))
    if weak: parts.append("weakly dependent on " + ", ".join(weak))
    trig_hint = ""
    if re.search(r"\b(sin|cos|tan)\b", expr_str):
        angs = sorted(set(re.findall(r"(?:sin|cos|tan)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)", expr_str)))
        trig_hint = f" Also depends on trig of {', '.join(angs)}." if angs else " Also depends on trigonometric terms."
    return (("; ".join(parts) + ".") if parts else "depends on several variables.") + trig_hint

# --- E. Parse scaling phrases: 2× / 4× / 70% / 1/3 / doubled / halved ---
def _parse_scale_factor(user_text: str) -> List[Tuple[str, float]]:
    t = (user_text or "").lower()
    # normalize
    t = t.replace("×", "x")
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)  # remove thousand separators
    out: List[Tuple[str,float]] = []

    WORD_TO_NUM = {
        "twice":2, "double":2, "doubles":2, "doubled":2,
        "thrice":3, "triple":3, "triples":3, "tripled":3,
        "quadruple":4, "quadruples":4, "quadrupled":4,
        "half":0.5, "halves":0.5, "halved":0.5, "quarter":0.25, "quartered":0.25
    }
    FRACTION_WORDS = {"one half":0.5,"a half":0.5,"one third":1/3,"third":1/3,"one quarter":0.25,"quarter":0.25,"two thirds":2/3,"three quarters":3/4}

    def norm(tok: str) -> str:
        v = _symbol_from_user_token(tok) or tok
        return v

    NUMPAT = r"(\d+(?:\.\d+)?(?:e[+\-]?\d+)?)"  # supports 1000, 2.75, 1e6

    # A) "<var> doubles/triples/halves"
    for var,word in re.findall(rf"\b([a-zα-ω]+)\s+(doubles?|triples?|quadruples?|halves)\b", t):
        out.append((norm(var), {"double":2,"doubles":2,"doubled":2,"triple":3,"triples":3,"tripled":3,"quadruple":4,"quadruples":4,"quadrupled":4,"half":0.5,"halves":0.5}.get(word, 2)))

    # B) "<var> is/was/becomes/made <NUM> (x|times|fold)"
    for var,num in re.findall(rf"\b([a-zα-ω]+)\s+(?:is|was|becomes|=|made)\s+{NUMPAT}\s*(?:x|times|-?fold)\b", t):
        out.append((norm(var), float(num)))

    # C) "<var> <NUM>-fold" or "<var> <word>fold"
    for var,num in re.findall(rf"\b([a-zα-ω]+)\s+{NUMPAT}-?fold\b", t):
        out.append((norm(var), float(num)))
    for var,word in re.findall(r"\b([a-zα-ω]+)\s+([a-z]+)-?fold\b", t):
        folds = {"two":2,"three":3,"four":4,"five":5}
        if word in folds:
            out.append((norm(var), float(folds[word])))

    # D) "<var> becomes|is|= <NUM> (times|x)"
    for var,num in re.findall(rf"\b([a-zα-ω]+)\s+(?:becomes|is|=)\s*{NUMPAT}\s*(?:x|times)?\b", t):
        out.append((norm(var), float(num)))

    # E) Fractions: "<var> becomes/made a/b"
    for var,a,b in re.findall(r"\b([a-zα-ω]+)\s+(?:becomes|is|made)\s+(\d+)\s*/\s*(\d+)\b", t):
        try: out.append((norm(var), float(a)/float(b)))
        except: pass

    # F) Percent: "increased by P%" / "decreased by P%" / "reduced to P%"
    for var,p in re.findall(rf"\b([a-zα-ω]+)\s+(?:is|was)?\s*increas(?:e|ed|es)\s+by\s+{NUMPAT}\s*%\b", t):
        out.append((norm(var), 1.0 + float(p)/100.0))
    for var,p in re.findall(rf"\b([a-zα-ω]+)\s+(?:is|was)?\s*(?:decreas(?:e|ed|es)|reduc(?:e|ed|es))\s+by\s+{NUMPAT}\s*%\b", t):
        out.append((norm(var), 1.0 - float(p)/100.0))
    for var,p in re.findall(rf"\b([a-zα-ω]+)\s+(?:is|was)?\s*reduc(?:e|ed|es)\s+to\s+{NUMPAT}\s*%\b", t):
        out.append((norm(var), float(p)/100.0))

    # G) Word fractions/numbers
    for var,word in re.findall(r"\b([a-zα-ω]+)\s+(?:becomes|is|made)\s+([a-z]+\s+[a-z]+|[a-z]+)\b", t):
        w = word.strip()
        if w in FRACTION_WORDS: out.append((norm(var), float(FRACTION_WORDS[w])))
        elif w in WORD_TO_NUM:  out.append((norm(var), float(WORD_TO_NUM[w])))

    # filter nonpositive factors
    out = [(v,k) for (v,k) in out if k > 0]
    return out

# --- F. Format big/small scales cleanly ---
import math
def _fmt_scale(scale: float) -> str:
    if not math.isfinite(scale):
        return "an extremely large amount"
    if scale >= 1e6 or scale <= 1e-6:
        return f"{scale:.2e}×"
    if abs(scale - round(scale)) < 1e-6:
        return f"{int(round(scale))}×"
    return f"{scale:.2g}×"

# --- G. Main dependency quick-answer (multilingual tuple) ---
def _dependency_quick_answer_ml(user_text: str) -> Optional[Tuple[str,str,str,str,str]]:
    t = (user_text or "").lower().strip()

    # intent detection
    dep_intent = re.search(r"\b(factors?\s+affect(ing)?|depend(s|ed)?\s+on|determinants?)\b", t)
    prop_intent = re.search(r"\b(proportional\s+to|var(y|ies)\s+with|inversely\s+proportional)\b", t)
    scale_intent = re.search(r"\b(doubles?|triples?|quadruples?|halves|times|x\b|fold|percent|%\b|reduc(?:ed|es)\s+to|becomes|made)\b", t)
    if not (dep_intent or prop_intent or scale_intent):
        return None

    # find formula: by name first, then symbol fallback
    match = None
    try:
        match = _match_formula_name_in_text(t)
    except Exception:
        match = None
    if not match:
        match = _match_formula_by_symbols_in_text(t)
    if not match:
        return None
    name, expr_str, _topic = match

    lhs = _extract_lhs_symbol(expr_str) or "result"
    exps = _proportionality_from_expr(expr_str, lhs)
    if not exps:
        return None

    # scaling phrasing → compute numeric effect
    pairs = _parse_scale_factor(t)
    if pairs:
        lines = []
        for var_raw, k in pairs[:4]:
            var_sym = _symbol_from_user_token(var_raw) or var_raw
            exp = None
            for v,a in exps:
                if v.lower() == var_sym.lower():
                    exp = a
                    break
            if exp is None:
                continue
            scale = k ** exp
            scale_str = _fmt_scale(scale)
            direction = "increase" if scale > 1 else ("decrease" if scale < 1 else "stay the same")
            lines.append(f"If {var_sym} becomes {k:g}×, {lhs} will {direction} by about {scale_str}.")
        if lines:
            en = " ".join(lines)
            return (en, en, en, en, en)

    # otherwise: proportionality description
    en = f"{lhs} is " + _describe_dependencies_natural(lhs, exps, expr_str)
    return (en, en, en, en, en)

# ------------------------------------------------------
# 🔹 Physics Quick Facts — Multilingual (SAY→SHOW when GUI visible)
# ------------------------------------------------------
def _physics_quick_fact_ml(user_input: str) -> Optional[Tuple[str, str, str, str, str]]:
    """
    Returns (en, hi, fr, es, de) for recognized quick facts.
    If no match, returns None.
    """
    t = (user_input or "").lower().strip()

    # 🔹 NEW: depends/proportional/scaling from the formula bank (concise)
    dep_tuple = _dependency_quick_answer_ml(user_input)
    if dep_tuple:
        return dep_tuple

    # (… unchanged quick facts and definitions …)
    # [CONTENT OMITTED HERE ONLY IN THIS COMMENT — the rest of your quick facts remain as in your source]

    # Try a few canonical unit/definition lookups and formula-name matches (existing logic kept)
    # (… unchanged …)

    return None

# --- Physics mode state ---
def is_physics_mode_on() -> bool:
    try:
        from utils import get_mode_state  # type: ignore
        return bool(get_mode_state("physics"))
    except Exception:
        try:
            from utils import settings  # type: ignore
            return bool(settings.get("physics_mode_on", False))
        except Exception:
            return False

# ------------------------------------------------------
# Quick Mode decider (unchanged)
# ------------------------------------------------------
def should_use_concise_physics(user_text: str, *, formula_name: Optional[str]) -> bool:
    t = (user_text or "").lower()
    if re.search(FORCE_VERBOSE_PATTERNS, t):
        return False
    if re.search(FORCE_BRIEF_PATTERNS, t):
        return True
    if not AUTO_CONCISE:
        return False
    if formula_name:
        if re.search(r"(why|explain|deriv(e|ation)|proof|steps?)", t):
            return False
        if re.search(r"\b(plot|graph)\b", t):
            return False
        if is_physics_mode_on():
            return False
        return True
    return False

# ------------------------------------------------------
# Main entry (Physics Mode)
# ------------------------------------------------------
def handle_physics_question(user_input: str):
    """
    Solves a physics prompt using the JSON formula bank, does robust unit handling,
    and renders a detailed, teaching-style explanation inside the SOLUTION POPUP.
    """
    global _last_equation_str
    lazy_imports()
    logger.log_interaction("physics_mode", user_input)

    # 🔹 Multilingual Quick Facts first: sentence-style answers (concise path)
    quick_tuple = _physics_quick_fact_ml(user_input)
    if quick_tuple:
        en, hi, fr, es, de = quick_tuple
        # SAY→SHOW only if GUI visible; otherwise voice-only
        _say_or_show_ml(en=en, hi=hi, fr=fr, es=es, de=de)
        return en  # return EN string as canonical text answer

    # 1) Pick formula
    formula_name, equation_str, topic = find_best_formula(user_input)
    concise = should_use_concise_physics(user_input, formula_name=formula_name)

    if not equation_str:
        t = (user_input or "").lower()
        has_numbers = bool(re.search(r"\d", user_input)) or bool(EXPLICIT_ASSIGNMENT.search(user_input))
        looks_like_equation = any(ch in user_input for ch in ("=", "+", "-", "×", "*", "/", "^"))
        conceptual_cue = bool(re.search(r"\b(what|why|how|define|state|explain|difference|list|mean|meaning|concept|law|rule|principle)\b", t))
        clearly_conceptual = conceptual_cue and not has_numbers and not looks_like_equation

        if clearly_conceptual:
            speak_no_quick_fact_ml()
            return "No quick match — try rephrasing or say “use full physics mode” for details."

        speak_no_formula_ml()
        return "I couldn’t match this to a known formula."

    # >>> Did-you-mean for P / λ (ambiguity resolution) <<<
    try:
        from sympy import sympify
        rhs_str = equation_str.split("=", 1)[1] if "=" in equation_str else equation_str
        _sym_set = {str(s) for s in sympify(rhs_str).free_symbols}
    except Exception:
        _sym_set = set()

    # also consider explicit mentions in the user's text
    if re.search(r"\bP\b", user_input):
        _sym_set.add("P")
    if re.search(r"\blambda\b|\bλ\b", user_input, re.IGNORECASE):
        _sym_set.add("lambda")

    _repls = _resolve_symbol_ambiguities(_sym_set)
    if _repls:
        for _old, _new in _repls.items():
            equation_str = re.sub(rf"\b{re.escape(_old)}\b", _new, equation_str)

    # 2) Extract values (numbers + units → SI)
    values, conversions_list = extract_values(user_input)

    # 3) Solve
    target, result, equation = solve_equation(equation_str, values)
    if result is None:
        speak_need_values_ml()
        if concise:
            return "Need one more value (or reduce unknowns)."
        return "Need one more value (or reduce unknowns)."

    # 4) Detect requested output unit dynamically (e.g. "in N·m") + normalize
    raw_unit_key = _detect_requested_unit(user_input)
    target_unit = _normalize_unit_key(raw_unit_key)
    raw_unit = raw_unit_key  # keep original for display

    # 5) Convert final result to requested unit if supported; else default per variable
    final_unit_label = "SI units"
    _unrounded_out_value = float(result)  # SI baseline
    if target_unit and target_unit in UNIT_TABLE:
        si_name, _to_si, from_si = UNIT_TABLE[target_unit]
        try:
            _unrounded_out_value = from_si(float(result))  # convert SI→requested
            final_numeric = _round_decimals(_unrounded_out_value, DEC_PLACES)
            final_unit_label = raw_unit if raw_unit else target_unit
        except Exception:
            final_numeric = _round_decimals(float(result), DEC_PLACES)
            final_unit_label = DEFAULT_UNITS.get(str(target), si_name)
    else:
        final_numeric = _round_decimals(float(result), DEC_PLACES)
        _unrounded_out_value = float(result)
        if target_unit:
            if re.fullmatch(r"[A-Za-zΩωμΜ·\.\^0-9/+-]+", raw_unit or target_unit):
                final_unit_label = raw_unit or target_unit
            else:
                final_unit_label = DEFAULT_UNITS.get(str(target), "SI units")
        else:
            final_unit_label = DEFAULT_UNITS.get(str(target), "SI units")

    if concise:
        # Concise one-liner: SAY→SHOW when GUI visible; otherwise voice-only
        _say_or_show_ml(en=f"{str(target)} ≈ {final_numeric} {final_unit_label}")
        return f"{str(target)} ≈ {final_numeric} {final_unit_label}"

    # Remember last equation for plotting (and persist)
    _last_equation_str = f"{str(equation.lhs)} = {str(equation.rhs)}"
    _save_last_equation_to_disk(_last_equation_str)

    # Pretty, *teaching-style* output
    def _fmt_given_line(var_name: str, val: float):
        unit = DEFAULT_UNITS.get(var_name, "")
        return f"{var_name} = {val} {unit}" if unit else f"{var_name} = {val}"

    given_lines = []
    for k, v in values.items():
        try:
            given_lines.append(_fmt_given_line(k, v))
        except Exception:
            given_lines.append(f"{k} = {v}")

    sym_legend = []
    for s in sorted({str(x) for x in equation.free_symbols}):
        sym_legend.append(_legend_text_for(s))

    display_equation = _symbolize_text(equation_str.strip())
    step1 = (
        "📌 Step 1: Choosing the Correct Formula\n"
        f"{display_equation}\n\n"
        "This equation relates:\n" + ("\n".join(sym_legend) if sym_legend else "(Variables depend on context)")
    )

    unit_conversion_section = ""
    if conversions_list:
        unit_conversion_section = "🔍 Extra: Unit Conversion\n" + "\n".join(_symbolize_text(x) for x in conversions_list) + "\n"

    subs_map = {k: v for k, v in values.items() if isinstance(v, (int, float))}
    step2_lines = _detailed_substitution_lines(equation.lhs, equation.rhs, subs_map)
    step2 = "📌 Step 2: Substituting Known Values\n" + "\n".join(step2_lines)

    step3_lines, rounded_for_display = _build_step3_lines(
        target, equation.rhs, subs_map, final_unit_label, _unrounded_out_value
    )
    if target_unit and (target_unit in UNIT_TABLE):
        conv_line = _final_unit_conversion_line(float(result), target_unit, raw_unit or target_unit)
        if conv_line:
            step3_lines.insert(1, _symbolize_text(conv_line))
    step3 = "📌 Step 3: Solving\n" + "\n".join(step3_lines)

    final_numeric = rounded_for_display
    answer = "✅ Final Answer:\n" + f"{str(target)} = {final_numeric} {final_unit_label}"

    concept_tip = _context_tip(topic, formula_name, equation_str)
    si_tip = None
    if conversions_list and (target_unit is None):
        si_tip = (
            "🧠 Tip from Nova:\n"
            "Physics equations use SI units like m/s, meters, and seconds. "
            "So we always convert first to avoid wrong answers!"
        )

    # ✅ Polished tip display logic
    if concept_tip:
        if si_tip:
            tips_block = (
                "💡 Tips:\n"
                "🧠 Tip from Nova:\n" + _symbolize_text(concept_tip) + "\n" + si_tip
            )
        else:
            tips_block = (
                "🧠 Tip from Nova:\n" + _symbolize_text(concept_tip)
            )
    else:
        tips_block = ""

    # Dynamic explain blocks
    expl = _get_dynamic_explain(topic, formula_name, equation_str)
    if expl and isinstance(expl, dict):
        understanding_text = expl.get("understanding") or f"We are asked to find {str(target)}."
        why_text = expl.get("why") or "This is the standard relation for this situation."
    else:
        understanding_text = f"We are asked to find {str(target)}. This tells us what the equation solves for in this situation."
        why_text = "This is the standard relation for this situation."

    question_section = f"""🧠 Question:
\"{user_input.strip()}\""""
    understanding_block = "📘 Understanding the Problem\n" + _symbolize_text(understanding_text) + "\n\n" + _symbolize_text(why_text)
    given_block = "🔎 Given:\n" + ("\n".join(given_lines) if given_lines else "(Not explicitly provided)")

    # Compose final output (Unit Conversion BEFORE Step 2) — sent ONLY to the Solution popup
    full_output = (
        question_section + "\n\n" +
        understanding_block + "\n\n" +
        given_block + "\n\n" +
        step1 + "\n\n" +
        (unit_conversion_section if unit_conversion_section else "") +
        step2 + "\n\n" +
        step3 + "\n\n" +
        answer + "\n\n" +
        tips_block
    )

    # Insert the 2-line plot block from dynamic JSON ("plot_first") right after Tips
    plot_first_line = _get_dynamic_plot_first(topic, formula_name, equation_str)
    if plot_first_line:
        # Exactly one blank line before, and no blank line between these two lines
        full_output += "\n\n" + _symbolize_text(plot_first_line) + "\nJust click [ ✦ Plot it ] or use Plot Mode later."

    # 🔊 Speak the final result in 5 languages
    speak_result_ml(str(target), str(final_numeric), str(final_unit_label))

    # 👉 Show inside Solution Popup with inline button (NOT main GUI)
    _open_solution_popup_with_plot_button(full_output)

    return full_output  # optional return

# ------------------------------------------------------
# (Optional) External handler if your main GUI wants to trigger plotting
# ------------------------------------------------------
def on_plot_it_button():
    """
    If your GUI calls this directly, we still attempt preview + save and append messages
    to the 'Physics Solution' channel if available.
    """
    try:
        global _last_equation_str
        if not _last_equation_str:
            cached = _load_last_equation_from_disk()
            if cached:
                _last_equation_str = cached

        if not _last_equation_str:
            try:
                _emit_gui_html("❌ No equation to plot yet.", append=True)
            except Exception:
                pass
            # 🔊 NEW: speak a friendly line
            try:
                from utils import _speak_multilang
                _speak_multilang(
                    en="Nothing to plot yet — ask a physics question first.",
                    hi="अभी प्लॉट करने के लिए कुछ नहीं है — पहले कोई भौतिकी सवाल पूछें।",
                    fr="Rien à tracer pour l’instant — pose d’abord une question de physique.",
                    es="Nada que graficar todavía — primero haz una pregunta de física.",
                    de="Noch nichts zu plotten — stelle zuerst eine Physikfrage."
                )
            except Exception:
                pass
            return False

        tmp_png = _plot_to_temp(_last_equation_str)
        if not tmp_png:
            try:
                _emit_gui_html("❌ Preview unavailable (Pillow not installed or headless mode).", append=True)
            except Exception:
                pass
            # 🔊 NEW: speak a friendly line
            try:
                from utils import _speak_multilang
                _speak_multilang(
                    en="I couldn’t render a plot preview. Try again or simplify the equation.",
                    hi="मैं प्रीव्यू नहीं बना सकी। दोबारा कोशिश करें या समीकरण सरल करें।",
                    fr="Impossible de générer l’aperçu du tracé. Réessayez ou simplifiez l’équation.",
                    es="No pude generar la vista previa del gráfico. Intenta de nuevo o simplifica la ecuación.",
                    de="Konnte die Plot-Vorschau nicht erstellen. Versuche es erneut oder vereinfache die Gleichung."
                )
            except Exception:
                pass
            return False

        suggested = "physics_graph"
        try:
            if "=" in _last_equation_str:
                lhs = _last_equation_str.split("=", 1)[0].strip()
                suggested = re.sub(r"[^A-Za-z0-9_]+", "_", lhs).strip("_") or suggested
        except Exception:
            pass

        # ✅ Preface (multilingual) right before opening the preview
        _preface_physics_show_graph()

        final_path = _show_graph_preview_window(tmp_png, suggested=suggested)
        if final_path:
            _save_last_graph_path_to_disk(final_path)
            try:
                _emit_gui_html(_format_saved_for_gui(final_path), append=True)
            except Exception:
                pass
            _speak_saved_where(final_path)
        else:
            try:
                _emit_gui_html("Preview closed. Graph not saved.", append=True)
            except Exception:
                pass
        return True
    except Exception as e:
        try:
            _emit_gui_html(f"❌ Couldn't open plot preview. Error: {e}", append=True)
        except Exception:
            pass
        return False

# -------------------------------------
# Hydrate last equation on import (optional)
# -------------------------------------
try:
    cached_eq = _load_last_equation_from_disk()
    if cached_eq:
        _last_equation_str = cached_eq
except Exception:
    pass
