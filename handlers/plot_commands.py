# 📂 handlers/plot_commands.py

import numpy as np
import matplotlib.pyplot as plt
from sympy import sympify, lambdify, solve, expand
from datetime import datetime
import tkinter as tk
from audio_player import play_audio_file
from tkinter import messagebox, simpledialog
import re
import os
import threading
from tkinter import Toplevel, ttk
from PIL import Image, ImageTk
import math

# ✅ Nova preview + utils (EXACT demo look/feel)
from .nova_graph_ui import build_interactive_figure, open_graph_preview

# ✅ App helpers (paths, JSON loader, GUI bridge pieces)
from utils import announce_saved_graph, graphs_dir, handlers_path, load_json_utf8, pkg_path, resource_path

# ✅ Lazy import for Nova internal functions (speech + logger + GUI bridge)
def get_utils():
    from utils import _speak_multilang, logger, gui_callback
    return _speak_multilang, logger, gui_callback

# 🔎 Friendly “Saved” line for the popup (filename + short path like ~/Music)
def _format_saved_for_gui(path: str) -> str:
    try:
        filename = os.path.basename(path) or path
        folder = os.path.dirname(path)
        home = os.path.expanduser("~")
        if folder.startswith(home):
            rel = os.path.relpath(folder, home).replace("\\", "/")
            friendly = "~" if rel in (".", "") else f"~/{rel}"
        else:
            friendly = folder.replace("\\", "/")
        return f"📁 Saved: {filename}  •  📂 {friendly}"
    except Exception:
        # Fall back to original path if anything odd happens
        return f"📁 Graph saved: {path}"

# 🧠 Load physics formulas from JSON (UTF-8; works in dev & PyInstaller)
PHYSICS_FORMULAS = load_json_utf8(handlers_path("physics_formulas.json"))

# 🧠 Detect physics keyword and return RHS string
def detect_physics_equation(command: str):
    cmd_lower = command.lower()
    for topic in PHYSICS_FORMULAS.values():
        for keyword, formula in topic.items():
            if keyword.lower() in cmd_lower:
                return formula
    return None

# 🧠 Detect LHS = RHS
def extract_lhs_rhs(command: str):
    cleaned = re.sub(r'\b(plot|graph|draw|show)\b', '', command, flags=re.IGNORECASE).strip()
    match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)', cleaned)
    if match:
        lhs = match.group(1).strip()
        rhs = match.group(2).strip()
        return lhs, rhs
    else:
        return "y", cleaned.strip()

# ---------------------------------------------------------------------------
# 🔤 Axis unit & pretty-name coverage (FULL) — mirrors popup UNIT_MAP
#     + safe aliases so words like "theta", "pressure" still label correctly.
# ---------------------------------------------------------------------------

AXIS_UNIT_MAP = {
    # Kinematics / mechanics
    "s": "m",          # displacement / distance
    "x": "m",
    "d": "m",
    "u": "m/s",        # initial velocity
    "v": "m/s",        # velocity
    "a": "m/s²",       # acceleration
    "t": "s",          # time
    "R": "m",          # range (projectile)
    "H": "m",          # max height
    "T": "s",          # time of flight / period (per popup map)

    # Angles / rotational
    "θ": "rad",
    "ω": "rad/s",
    "α": "rad/s²",
    "τ": "N·m",

    # Dynamics / work-energy-power
    "W": "J",
    "KE": "J",
    "PE": "J",
    "E": "J",
    "P": "W",          # Power (pressure handled via alias P_pressure)
    "ΔK": "J",
    "m": "kg",
    "F": "N",
    "p": "kg·m/s",
    "J": "N·s",        # impulse
    "Δt": "s",
    "μ": "",
    "N": "N",
    "r": "m",
    "I": "kg·m²",
    "L": "kg·m²/s",

    # Fluids / thermo / gas-ish
    "Fb": "N",
    "ρ": "kg/m³",
    "V": "m³",
    "η": "Pa·s",
    "Q": "J / C",
    "ΔT": "°C",

    # Waves / oscillations / optics
    "f": "Hz",
    "λ": "m",          # wavelength
    "c": "m/s",
    "β": "m",
    "n": "",
    "l": "m",
    "k": "N/m",
    "x": "m",          # SHM displacement

    # Circuits / E&M
    "q": "C",
    "e": "C",
    "emf": "V",
    "V0": "V",
    "I0": "A",
    "Z": "Ω",
    "Φ": "Wb",
    "B": "T",
    "X_L": "Ω",
    "X_C": "Ω",
    "R1": "Ω", "R2": "Ω", "R3": "Ω",
    "C1": "F", "C2": "F", "C3": "F",
    "A": "m²", "A1": "m²", "A2": "m²",
    "dv": "m/s", "dx": "m",

    # Gravitation / constants / modern
    "G": "N·m²/kg²",
    "M": "kg",
    "v_e": "m/s",
    "h": "J·s",
    "Δm": "kg",
}

# Aliases so words map to symbols (optional but safe)
_UNIT_ALIASES = {
    # english words → symbols
    "time": "t",
    "displacement": "s",
    "distance": "d",
    "velocity": "v",
    "initial_velocity": "u",
    "acceleration": "a",
    "range": "R",
    "height": "H",
    "period": "T",
    "radius": "r",
    "area": "A",
    "mass": "m",
    "force": "F",
    "momentum": "p",
    "impulse": "J",
    "work": "W",
    "energy": "E",
    "power": "P_power",
    "spring_constant": "k",
    "moment_of_inertia": "I",
    "angular_momentum": "L",
    "buoyant_force": "Fb",
    "density": "ρ",
    "viscosity": "η",
    "volume": "V",
    "heat": "Q",
    "temperature_change": "ΔT",
    "frequency": "f",
    "wavelength": "λ",
    "speed_of_light": "c",
    "fringe_width": "β",
    "refractive_index": "n",
    "length": "l",
    "charge": "q",
    "emf": "emf",
    "magnetic_flux": "Φ",
    "magnetic_field": "B",
    "inductive_reactance": "X_L",
    "capacitive_reactance": "X_C",
    "escape_velocity": "v_e",
    "planck_constant": "h",
    "mass_defect": "Δm",

    # greek spell-outs
    "theta": "θ",
    "omega": "ω",
    "alpha": "α",
    "phi": "Φ",
    "mu": "μ",
    "rho": "ρ",
    "eta": "η",
    "lambda": "λ",

    # pressure vs power disambiguation
    "pressure": "P_pressure",

    # decay constant (to disambiguate wavelength λ)
    "lambda_decay": "λ_decay"
}

# Units for special aliases
_EXTRA_UNITS = {
    "P_pressure": "Pa",  # default pressure unit
    "P_power": "W",
    "λ_decay": "1/s",    # decay constant
}

# Pretty names for axis labels (full coverage)
_PRETTY_NAMES = {
    "s": "Displacement", "x": "Displacement", "d": "Distance",
    "u": "Initial Velocity", "v": "Velocity",
    "a": "Acceleration", "t": "Time",
    "R": "Range", "H": "Maximum Height", "T": "Time / Period",

    "θ": "Angle", "ω": "Angular Velocity", "α": "Angular Acceleration", "τ": "Torque",

    "W": "Work", "KE": "Kinetic Energy", "PE": "Potential Energy", "E": "Energy",
    "P": "Power", "P_power": "Power", "P_pressure": "Pressure",
    "ΔK": "Change in Kinetic Energy",
    "m": "Mass", "F": "Force", "p": "Momentum", "J": "Impulse",
    "Δt": "Time Interval", "μ": "Coefficient of Friction", "N": "Normal Force",
    "r": "Radius", "I": "Moment of Inertia", "L": "Angular Momentum",

    "Fb": "Buoyant Force", "ρ": "Density", "V": "Volume", "η": "Viscosity",
    "Q": "Heat", "ΔT": "Temperature Change",

    "f": "Frequency", "λ": "Wavelength", "λ_decay": "Decay Constant",
    "c": "Speed of Light", "β": "Fringe Width", "n": "Refractive Index",
    "l": "Length", "k": "Spring Constant",

    "q": "Charge", "e": "Elementary Charge",
    "emf": "EMF", "V0": "Peak Voltage", "I0": "Peak Current",
    "Z": "Impedance", "Φ": "Magnetic Flux", "B": "Magnetic Field",
    "X_L": "Inductive Reactance", "X_C": "Capacitive Reactance",
    "R1": "Resistance R1", "R2": "Resistance R2", "R3": "Resistance R3",
    "C1": "Capacitance C1", "C2": "Capacitance C2", "C3": "Capacitance C3",
    "A": "Area", "A1": "Area 1", "A2": "Area 2",
    "dv": "Velocity Increment", "dx": "Displacement Increment",

    "G": "Gravitational Constant", "M": "Mass", "v_e": "Escape Velocity",
    "h": "Planck Constant", "Δm": "Mass Defect",
}

def _normalize_symbol(name: str) -> str:
    """Map words/aliases to canonical symbol keys when possible."""
    s = str(name)
    if s in AXIS_UNIT_MAP or s in _EXTRA_UNITS or s in _PRETTY_NAMES:
        return s
    alias = _UNIT_ALIASES.get(s.lower())
    return alias if alias else s

def _label_with_unit(name: str) -> str:
    """Return pretty label with unit, covering all symbols in your unit map."""
    key = _normalize_symbol(name)
    unit = _EXTRA_UNITS.get(key, AXIS_UNIT_MAP.get(key, ""))
    pretty = _PRETTY_NAMES.get(key, str(name))
    return f"{pretty} ({unit})" if unit else pretty

def _infer_curve_label(sym_expr, x_symbol, lhs_symbol_str: str) -> str:
    """
    Name the curve intelligently. Recognize families (polynomial degree,
    rational/reciprocal, power/sqrt, exp/log, trig/hyperbolic/inverse trig,
    gaussian-like, absolute, piecewise/step). Fallback: 'Y(units) vs X(units)'.
    """
    import sympy as sp

    # ---------- 1) Polynomial degree ----------
    try:
        poly = sp.Poly(sym_expr, x_symbol)
        deg = poly.degree()
        if deg == 0: return "Constant"
        if deg == 1: return "Linear"
        if deg == 2: return "Quadratic"
        if deg == 3: return "Cubic"
        return f"Polynomial (deg {deg})"
    except sp.PolynomialError:
        pass

    # ---------- 2) Rational / reciprocal ----------
    num, den = sp.fraction(sp.simplify(sym_expr))
    if den.has(x_symbol):
        try:
            ndeg = sp.degree(num, x_symbol)
            ddeg = sp.degree(den, x_symbol)
        except Exception:
            ndeg = ddeg = None
        if (ndeg in (None, 0)) and ddeg == 1:
            return "Reciprocal"
        return "Rational Function"

    # ---------- 3) Power law / sqrt / inverse powers ----------
    for pw in sym_expr.atoms(sp.Pow):
        if pw.base.has(x_symbol) and not pw.exp.has(x_symbol):
            expv = pw.exp
            try:
                expv = sp.nsimplify(expv)
            except Exception:
                pass
            if expv == sp.Rational(1, 2):  return "Square Root"
            if expv == -sp.Rational(1, 2): return "Inverse Square Root"
            if expv == 2:                  return "Quadratic"
            if expv == -1:                 return "Reciprocal"
            if expv.is_real:
                if expv < 0: return "Inverse Power Law"
                if expv > 0: return "Power Law"
            return "Power Law"

    # ---------- 4) Exponential / Logarithmic / Gaussian-like ----------
    has_exp = sym_expr.has(sp.exp) or any(
        isinstance(pw, sp.Pow) and pw.base == sp.E and pw.exp.has(x_symbol)
        for pw in sym_expr.atoms(sp.Pow)
    )
    if has_exp:
        for pw in sym_expr.atoms(sp.Pow):
            if getattr(pw, "base", None) == sp.E:
                exponent = pw.exp
                ex = sp.expand(exponent)
                try:
                    a2 = ex.coeff(x_symbol, 2)
                    if a2.is_real and a2 < 0:
                        return "Gaussian-like"
                except Exception:
                    pass
        return "Exponential"

    if sym_expr.has(sp.log):
        return "Logarithmic"

    # ---------- 5) Trig / Hyperbolic / Inverse trig ----------
    if sym_expr.has(sp.sin):   return "Sine Wave"
    if sym_expr.has(sp.cos):   return "Cosine Wave"
    if sym_expr.has(sp.tan):   return "Tangent"
    if sym_expr.has(sp.sinh):  return "Hyperbolic Sine"
    if sym_expr.has(sp.cosh):  return "Hyperbolic Cosine"
    if sym_expr.has(sp.tanh):  return "Hyperbolic Tangent"
    if sym_expr.has(sp.asin) or sym_expr.has(sp.acos) or sym_expr.has(sp.atan):
        return "Inverse Trigonometric"

    # ---------- 6) Absolute / Piecewise / Step ----------
    if sym_expr.has(sp.Abs):
        return "Absolute Value"
    if sym_expr.has(sp.Piecewise) or sym_expr.has(sp.Heaviside) or sym_expr.has(sp.sign):
        return "Piecewise / Step"

    # ---------- Fallback ----------
    x_lab = _label_with_unit(str(x_symbol))
    y_lab = _label_with_unit(str(lhs_symbol_str))
    return f"{y_lab} vs {x_lab}"

# 🧠 Custom popup for constant input (kept as-is for constants collection)
def themed_input_popup(variable_name):

    # 💫 Local sparkle animation
    def create_sparkles(canvas, num=6):
        sparkles = []
        for _ in range(num):
            sparkle = canvas.create_oval(0, 0, 4, 4, fill="#00ffee", outline="")
            sparkles.append(sparkle)
        return sparkles

    def animate_sparkles():
        nonlocal sparkle_angle
        sparkle_angle += 2
        r = 60
        cx, cy = 160, 130
        for i, sparkle in enumerate(sparkles):
            angle = math.radians(sparkle_angle + (360 / len(sparkles)) * i)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            sparkle_canvas.coords(sparkle, x, y, x + 4, y + 4)
        popup.after(50, animate_sparkles)

 
    # 🧊 Smooth fade-in animation
    def fade_in(window, steps=20, delay=15):
        try:
            window.attributes("-alpha", 0.0)
            for i in range(steps):
                window.attributes("-alpha", i / steps)
                window.update()
                window.after(delay)
            window.attributes("-alpha", 1.0)
        except Exception:
            pass

    # 🎵 Play open chime (optional)
    def play_open_chime():
        try:
            chime_path = str(pkg_path("assets", "ui_popup_open.mp3"))
            threading.Thread(target=lambda: play_audio_file(chime_path), daemon=True).start()
        except Exception:
            pass

    # 🎵 Play submit chime (non-blocking)
    def play_submit_chime():
        try:
            chime_path = str(pkg_path("assets", "popup_submit_chime.mp3"))
            threading.Thread(target=lambda: play_audio_file(chime_path), daemon=True).start()
        except Exception:
            pass

    # 🎵 Play error/cancel beep (non-blocking)
    def play_error_beep():
        try:
            chime_path = str(pkg_path("assets", "error_beep.mp3"))
            threading.Thread(target=lambda: play_audio_file(chime_path), daemon=True).start()
        except Exception:
            pass

    result = [None]
    popup = Toplevel()
    popup.title("Enter Constant")
    try:
        popup.iconbitmap(resource_path("nova_icon_big.ico"))
    except Exception:
        pass

    popup.geometry("360x360")
    popup.configure(bg="#0f0f0f")
    popup.resizable(False, False)
    popup.attributes("-topmost", True)
    popup.grab_set()
    fade_in(popup)
    play_open_chime()

    # 🌌 Sparkle background
    sparkle_canvas = tk.Canvas(popup, width=360, height=360, bg="#0f0f0f", highlightthickness=0)
    sparkle_canvas.place(x=0, y=0)
    sparkle_angle = 0
    sparkles = create_sparkles(sparkle_canvas)
    animate_sparkles()

    # 👽 Nova logo
    try:
        logo_path = str(pkg_path("assets", "nova_face.png"))
        logo_img = Image.open(logo_path).resize((80, 80))
        logo = ImageTk.PhotoImage(logo_img)
        logo_label = tk.Label(popup, image=logo, bg="#0f0f0f")
        logo_label.image = logo
        logo_label.place(relx=0.5, y=40, anchor="center")
    except Exception:
        pass

    # 📏 Unit map for display
    UNIT_MAP = {
        "s": "m",        # displacement / distance → meters
        "u": "m/s",      # initial velocity
        "v": "m/s",      # velocity
        "a": "m/s²",     # acceleration
        "t": "s",        # time
        "d": "m",        # distance
        "R": "m",        # range
        "H": "m",        # max height
        "T": "s",        # time of flight or period
        "θ": "rad",      # angle in radians
        "W": "J",        # work
        "KE": "J",       # kinetic energy
        "PE": "J",       # potential energy
        "E": "J",        # energy
        "P": "W",        # power
        "ΔK": "J",       # change in kinetic energy
        "m": "kg",       # mass
        "F": "N",        # force
        "p": "kg·m/s",   # momentum
        "J": "N·s",      # impulse
        "Δt": "s",       # time interval
        "μ": "",         # coefficient of friction (unitless)
        "N": "N",        # normal force
        "r": "m",        # radius / distance
        "ω": "rad/s",    # angular velocity
        "I": "kg·m²",    # moment of inertia
        "L": "kg·m²/s",  # angular momentum
        "τ": "N·m",      # torque
        "α": "rad/s²",   # angular acceleration
        "G": "N·m²/kg²", # gravitational constant
        "M": "kg",       # planetary mass
        "v_e": "m/s",    # escape velocity
        "Fb": "N",       # buoyant force
        "ρ": "kg/m³",    # density
        "V": "m³",       # volume
        "η": "Pa·s",     # viscosity
        "A": "m²",       # area
        "x": "m",        # SHM displacement
        "l": "m",        # length of pendulum
        "k": "N/m",      # spring constant
        "f": "Hz",       # frequency
        "λ": "m",        # wavelength
        "n": "",         # refractive index / quantum level (unitless)
        "c": "m/s",      # speed of light
        "β": "m",        # fringe width
        "Q": "J / C",    # heat (context-dependent)
        "ΔT": "°C",      # temperature change
        "R1": "Ω", "R2": "Ω", "R3": "Ω",
        "C1": "F", "C2": "F", "C3": "F",
        "V0": "V",       # peak voltage
        "I0": "A",       # peak current
        "Z": "Ω",        # impedance
        "Φ": "Wb",       # magnetic flux
        "emf": "V",      # electromotive force
        "X_L": "Ω",      # inductive reactance
        "X_C": "Ω",      # capacitive reactance
        "q": "C",        # charge
        "B": "T",        # magnetic field
        "e": "C",        # elementary charge
        "h": "J·s",      # Planck constant
        "Δm": "kg",      # mass defect
        "λ_decay": "1/s",# decay constant
        "Φ": "Wb",       # magnetic flux
        "A1": "m²", "A2": "m²",
        "dv": "m/s", "dx": "m"
    }


    unit = UNIT_MAP.get(variable_name, "")
    unit_text = f" [{unit}]" if unit else ""

    # 🧠 Prompt with unit shown
    label = tk.Label(
        popup,
        text=f"Enter value for: {variable_name}{unit_text}",
        bg="#0f0f0f", fg="#00ffee", font=("Consolas", 12)
    )
    label.place(relx=0.5, y=120, anchor="center")

    # 📥 Entry
    entry = tk.Entry(
        popup, font=("Consolas", 12), justify="center",
        bg="#1a1a1a", fg="white", insertbackground="white", relief="flat", width=15
    )
    entry.place(relx=0.5, y=155, anchor="center")
    entry.focus_set()

    # 🌈 Rounded button style
    style = ttk.Style(popup)
    style.theme_use("clam")
    style.configure("Rounded.TButton",
        background="#202020",
        foreground="white",
        font=("Consolas", 10),
        padding=6,
        borderwidth=0,
        focusthickness=3,
        focuscolor="none"
    )
    style.map("Rounded.TButton", background=[("active", "#008080")])

    # ✅ Submit button
    def submit():
        try:
            val = float(entry.get())
            result[0] = val
            play_submit_chime()
            popup.destroy()
        except ValueError:
            play_error_beep()
            label.config(text="⚠️ Enter a valid number", fg="red")

    result = [None]
    submit_btn = ttk.Button(popup, text="✦ Submit", command=submit, style="Rounded.TButton")
    submit_btn.place(relx=0.32, y=220, anchor="center")

    # ❌ Cancel button (with error beep)
    cancel_btn = ttk.Button(
        popup,
        text="Cancel",
        command=lambda: (play_error_beep(), popup.destroy()),
        style="Rounded.TButton"
    )
    cancel_btn.place(relx=0.68, y=220, anchor="center")

    # 🔒 BLOCK until the window is closed, then RETURN the value
    popup.wait_window()
    return result[0]

# (Kept here if you still need it elsewhere; not used by the Nova preview flow)
def themed_save_graph_popup():

    def create_sparkles(canvas, num=6):
        sparkles = []
        for _ in range(num):
            sparkle = canvas.create_oval(0, 0, 4, 4, fill="#00ffee", outline="")
            sparkles.append(sparkle)
        return sparkles
    def animate_sparkles():
        nonlocal sparkle_angle
        sparkle_angle += 2
        r = 60
        cx, cy = 160, 130
        for i, sparkle in enumerate(sparkles):
            angle = math.radians(sparkle_angle + (360 / len(sparkles)) * i)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            sparkle_canvas.coords(sparkle, x, y, x + 4, y + 4)
        popup.after(50, animate_sparkles)
    def play_open_chime():
        try:
            chime_path = str(pkg_path("assets", "ui_popup_open.mp3"))
            threading.Thread(target=lambda: play_audio_file(chime_path), daemon=True).start()
        except Exception:
            pass
    def play_submit_chime():
        try:
            chime_path = str(pkg_path("assets", "popup_submit_chime.mp3"))
            threading.Thread(target=lambda: play_audio_file(chime_path), daemon=True).start()
        except Exception:
            pass
    def play_error_beep():
        try:
            chime_path = str(pkg_path("assets", "error_beep.mp3"))
            threading.Thread(target=lambda: play_audio_file(chime_path), daemon=True).start()
        except Exception:
            pass
    def fade_in(window, steps=20, delay=15):
        try:
            window.attributes("-alpha", 0.0)
            for i in range(steps):
                window.attributes("-alpha", i / steps)
                window.update()
                window.after(delay)
            window.attributes("-alpha", 1.0)
        except Exception:
            pass
    result = [None]
    popup = Toplevel()
    popup.title("Save Graph")
    try:
        popup.iconbitmap(resource_path("nova_icon_big.ico"))
    except Exception:
        pass
    popup.geometry("360x360")
    popup.configure(bg="#0f0f0f")
    popup.resizable(False, False)
    popup.attributes("-topmost", True)
    popup.grab_set()
    fade_in(popup)
    play_open_chime()
    sparkle_canvas = tk.Canvas(popup, width=360, height=360, bg="#0f0f0f", highlightthickness=0)
    sparkle_canvas.place(x=0, y=0)
    sparkle_angle = 0
    sparkles = create_sparkles(sparkle_canvas)
    animate_sparkles()
    try:
        logo_path = str(pkg_path("assets", "nova_face.png"))
        logo_img = Image.open(logo_path).resize((80, 80))
        logo = ImageTk.PhotoImage(logo_img)
        logo_label = tk.Label(popup, image=logo, bg="#0f0f0f")
        logo_label.image = logo
        logo_label.place(relx=0.5, y=40, anchor="center")
    except Exception:
        pass
    label = tk.Label(
        popup,
        text="Would you like to save this graph?\n(Leave blank for auto name)",
        bg="#0f0f0f", fg="#00ffee", font=("Consolas", 11), justify="center"
    )
    label.place(relx=0.5, y=120, anchor="center")
    entry = tk.Entry(
        popup, font=("Consolas", 12), justify="center",
        bg="#1a1a1a", fg="white", insertbackground="white", relief="flat", width=24
    )
    entry.place(relx=0.5, y=160, anchor="center")
    entry.focus_set()
    style = ttk.Style(popup)
    style.theme_use("clam")
    style.configure("Rounded.TButton",
        background="#202020",
        foreground="white",
        font=("Consolas", 10),
        padding=6,
        borderwidth=0,
        focusthickness=3,
        focuscolor="none"
    )
    style.map("Rounded.TButton", background=[("active", "#008080")])
    def save():
        filename = entry.get().strip()
        if filename:
            filename = re.sub(r'[^a-zA-Z0-9_-]', '_', filename)
        else:
            filename = f"graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result[0] = f"{filename}.png"
        popup.destroy()
    def cancel():
        result[0] = None
        popup.destroy()
    ttk.Button(popup, text="✦ Save", command=save, style="Rounded.TButton").place(relx=0.32, y=220, anchor="center")
    ttk.Button(popup, text="Cancel", command=cancel, style="Rounded.TButton").place(relx=0.68, y=220, anchor="center")
    popup.wait_window()
    return result[0]

# 📈 MAIN FUNCTION
def handle_plotting(command: str):
    _speak_multilang, logger, gui_callback = get_utils()
    command = command.lower()

    try:
        # ✅ Handle custom data points like x=[1,2], y=[3,4] (order-agnostic)
        generic_xy_match = re.search(
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\[([^\]]+)\]\s*,?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\[([^\]]+)\]',
            command
        )
        if generic_xy_match:
            try:
                x_var = generic_xy_match.group(1)
                x_list = [float(num.strip()) for num in generic_xy_match.group(2).split(",")]
                y_var = generic_xy_match.group(3)
                y_list = [float(num.strip()) for num in generic_xy_match.group(4).split(",")]

                if len(x_list) != len(y_list):
                    gui_callback("plot", "❌ Data arrays must be of the same length.")
                    return None

                # Sort by x so hover snapping is correct
                pairs = sorted(zip(x_list, y_list), key=lambda p: p[0])
                x_sorted = [p[0] for p in pairs]
                y_sorted = [p[1] for p in pairs]

                gui_callback("plot", f"📊 Plotting custom data points:\n{x_var} = {x_sorted}\n{y_var} = {y_sorted}")

                # Nova preview (exact same GUI as demo)
                series_label = "Custom Data"
                x_label = _label_with_unit(x_var)
                y_label = _label_with_unit(y_var)
                title_text = "Custom Data • Plot"
                suggested_name = "custom_data_graph"

                try:
                    fig, callbacks = build_interactive_figure(
                        x_sorted, y_sorted,
                        x_label=x_label, y_label=y_label, series_label=series_label
                    )
                    saved_path = open_graph_preview(
                        fig, callbacks,
                        title_text=title_text,
                        suggested_name=suggested_name
                    )
                except Exception:
                    # Fallback: headless/GUI error → auto-save
                    out = os.path.join(graphs_dir(), f"{suggested_name}_{int(datetime.now().timestamp())}.png")
                    plt.figure(figsize=(5.6, 3.3), dpi=120)
                    plt.plot(x_sorted, y_sorted, linewidth=2.4, color="#00ffee")
                    plt.gca().set_facecolor("#0f0f0f"); plt.gcf().patch.set_facecolor("#0f0f0f")
                    plt.savefig(out, facecolor="#0f0f0f", bbox_inches="tight")
                    plt.close()
                    saved_path = out

                if saved_path:
                    announce_saved_graph(saved_path)
                    gui_callback("plot", _format_saved_for_gui(saved_path))
                    logger.info(f"📁 Graph saved to {saved_path}")
                    return saved_path
                else:
                    logger.info("🛑 Preview closed. Graph not saved.")
                    return None

            except Exception as err:
                gui_callback("plot", f"❌ Could not parse custom data points.\nError: {err}")
                return None

        # 🎯 Range detection
        range_match = re.search(r'from\s*([-−–]?\d+\.?\d*)\s*to\s*([-−–]?\d+\.?\d*)', command)
        if range_match:
            x_min = float(range_match.group(1).replace("−", "-"))
            x_max = float(range_match.group(2).replace("−", "-"))
            range_msg = f"2. Range detected: x ∈ [{x_min}, {x_max}]"
        else:
            x_min, x_max = -10, 10
            range_msg = "2. No range provided. Defaulting to x ∈ [-10, 10]"

        # 🧠 Parse LHS & RHS
        lhs, expr_str = extract_lhs_rhs(command)

        # 🧠 Fallback: Physics keyword detection
        physics_used = False
        if expr_str == command or expr_str.strip() == "":
            detected_expr = detect_physics_equation(command)
            if detected_expr:
                lhs, expr_str = extract_lhs_rhs(detected_expr)
                physics_used = True
                gui_callback("plot", f"📘 Physics keyword detected → using equation: {lhs} = {expr_str}")
            else:
                gui_callback("plot", "❌ Couldn't find any equation or keyword to plot.")
                return None

        # 🧠 Convert to sympy expression
        sym_expr = sympify(expr_str)
        symbols_in_expr = list(sym_expr.free_symbols)

        # 🧠 Multiple variable handling
        if len(symbols_in_expr) > 1:
            gui_callback("plot", f"🔢 Multiple variables detected: {', '.join(str(s) for s in symbols_in_expr)}")
            x_symbol = symbols_in_expr[-1]  # often time, x, etc.
            constants = {}
            for sym in symbols_in_expr:
                if sym != x_symbol:
                    val = themed_input_popup(str(sym))
                    if val is None:
                        gui_callback("plot", f"❌ Cancelled. Missing value for {sym}.")
                        return None
                    constants[sym] = val
            sym_expr = sym_expr.subs(constants)
        else:
            x_symbol = symbols_in_expr[0]

        # 📊 Evaluate values
        f = lambdify(x_symbol, sym_expr, modules=["numpy"])
        x_vals = np.linspace(x_min, x_max, 1000)
        y_vals = f(x_vals)

        # 🧮 Sample examples
        example_points = []
        for sample_x in [-2, 0, 2]:
            if x_min <= sample_x <= x_max:
                try:
                    substituted = sym_expr.subs(x_symbol, sample_x)
                    detailed_steps = str(sym_expr).replace(str(x_symbol), f"({sample_x})")
                    evaluated = expand(substituted)
                    example_points.append(
                        f"→ For {x_symbol} = {sample_x}:\n"
                        f"   {lhs} = {sym_expr} → {lhs} = {detailed_steps}\n"
                        f"   → Evaluates to: {lhs} = {evaluated}"
                    )
                except Exception as eval_err:
                    example_points.append(f"→ For {x_symbol} = {sample_x}: ❌ Error evaluating: {eval_err}")

        gui_callback("plot", "\n".join([
            f"📘 Graphing {lhs} = {sym_expr}",
            f"1. Recognized equation: {lhs} = {sym_expr}",
            range_msg,
            f"3. Generated 1000 values from {x_min} to {x_max}",
            f"4. Calculated with variable {x_symbol}",
            "5. Example points:"
        ] + example_points + ["6. Displaying graph..."]))

        # 🌟 Build labels + legend + title dynamically
        x_label = _label_with_unit(str(x_symbol))
        y_label = _label_with_unit(str(lhs))
        series_label = _infer_curve_label(sym_expr, x_symbol, str(lhs))
        title_text = "Physics • Graph" if physics_used else f"Graph • {str(lhs)} vs {str(x_symbol)}"
        suggested_name = re.sub(r'[^a-zA-Z0-9_-]+', '_', f"{str(lhs)}_{str(x_symbol)}_graph").strip("_").lower()

        # 🎨 Nova preview (EXACT GUI as your demo)
        try:
            fig, callbacks = build_interactive_figure(
                x_vals, y_vals,
                x_label=x_label,
                y_label=y_label,
                series_label=series_label
            )
            saved_path = open_graph_preview(
                fig, callbacks,
                title_text=title_text,
                suggested_name=suggested_name
            )
        except Exception:
            # Fallback: headless/GUI error → auto-save
            out = os.path.join(graphs_dir(), f"{suggested_name}_{int(datetime.now().timestamp())}.png")
            plt.figure(figsize=(5.6, 3.3), dpi=120)
            plt.plot(x_vals, y_vals, linewidth=2.4, color="#00ffee")
            plt.gca().set_facecolor("#0f0f0f"); plt.gcf().patch.set_facecolor("#0f0f0f")
            plt.savefig(out, facecolor="#0f0f0f", bbox_inches="tight")
            plt.close()
            saved_path = out

        if saved_path:
            announce_saved_graph(saved_path)
            gui_callback("plot", _format_saved_for_gui(saved_path))
            logger.info(f"📁 Graph saved to {saved_path}")
            return saved_path
        else:
            logger.info("🛑 Preview closed. Graph not saved.")
            return None

    except Exception as e:
        _speak_multilang, logger, gui_callback = get_utils()
        gui_callback("plot", f"❌ Could not plot the expression.\nError: {str(e)}")
        _speak_multilang(
            "I couldn't graph that equation. Please check it and try again.",
            hi="मैं उस समीकरण का ग्राफ नहीं बना सकी। कृपया जांचें और फिर से प्रयास करें।",
            fr="Je n'ai pas pu tracer cette équation. Veuillez vérifier et réessayer.",
            es="No pude graficar esa ecuación. Por favor, verifica y vuelve a intentarlo.",
            de="Ich konnte diese Gleichung nicht darstellen. Bitte überprüfe sie und versuche es erneut.",
            log_command="Graphing failed"
        )
        logger.error(f"❌ Plotting failed: {e}")
        return None




 