# handlers/basic_math.py

import re
import math
import statistics
from sympy import sympify, trigsimp, pi

# guard requests import (graceful fallback if not bundled)
try:
    import requests
except Exception:
    requests = None

# === Popup render ===
from gui_interface import show_mode_solution  # kept (not removed), though popup now uses say_show_map

# -------------------------------
# Lazy utils import (no circulars)
# -------------------------------
def get_utils():
    from utils import _speak_multilang, selected_language, logger
    # ✅ also bring in the unified "say first, then show" helper
    from say_show import say_show_map
    return _speak_multilang, selected_language, logger, say_show_map

# -------------------------------
# Global behavior switches
# -------------------------------
DEC_PLACES = 2

# Quick vs Steps intent cues
FORCE_VERBOSE_PATTERNS = r"\b(show steps|explain|why|how|derivation|proof|walk me through|details|step by step|full steps|expand)\b"
FORCE_BRIEF_PATTERNS   = r"\b(brief|quick answer|just answer|no steps|one[- ]?liner|tldr|tl;dr|short|summary|summarize|quickly|fast)\b"

# When user does not explicitly ask for steps, complex problems will show concise hints
AUTO_HINTS = True

# Spoken → symbol map
OPERATOR_MAP = {
    # English
    "plus": "+", "minus": "-", "times": "*", "multiplied by": "*", "divided by": "/", "mod": "%",
    "remainder": "%", "power": "**", "raised to": "**", "to the power of": "**", "log": "log",
    "sqrt": "sqrt", "square root": "sqrt", "percentage": "%", "pi": "pi", "e": "e",
    "sin": "sin", "cos": "cos", "tan": "tan",
    # Hindi
    "जोड़ो": "+", "घटाओ": "-", "गुणा": "*", "भाग": "/", "शेषफल": "%", "प्रतिशत": "%",
    "घात": "**", "लॉग": "log", "वर्गमूल": "sqrt", "पाई": "pi", "ई": "e", "साइन": "sin",
    "कोस": "cos", "टैन": "tan",
    # French
    "moins": "-", "fois": "*", "divisé par": "/", "modulo": "%", "logarithme": "log",
    "puissance": "**", "racine carrée": "sqrt", "pourcentage": "%", "sinus": "sin",
    "cosinus": "cos", "tangente": "tan",
    # Spanish
    "más": "+", "menos": "-", "por": "*", "dividido por": "/", "residuo": "%", "potencia": "**",
    "logaritmo": "log", "raíz cuadrada": "sqrt", "porcentaje": "%", "seno": "sin",
    "coseno": "cos", "tangente": "tan",
    # German
    "plus": "+", "minus": "-", "mal": "*", "geteilt durch": "/", "rest": "%", "prozent": "%",
    "hoch": "**", "potenz": "**", "logarithmus": "log", "quadratwurzel": "sqrt",
    "sinus": "sin", "cosinus": "cos", "tangens": "tan"
}

# --- lightweight unit conversion (simple everyday units)
UNIT_CONVERSIONS = {
    "mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "inch": 0.0254, "foot": 0.3048, "yard": 0.9144, "mile": 1609.34,
    "mg": 0.001, "g": 1, "kg": 1000, "lb": 453.592, "oz": 28.3495,
    "ml": 0.001, "l": 1, "gallon": 3.78541, "pint": 0.473176,
    "sqft": 0.092903, "sqm": 1, "acre": 4046.86, "hectare": 10000,
    # Time here is normalized to hours for ease of mixed sums
    "sec": 1/3600, "second": 1/3600, "min": 1/60, "minute": 1/60, "hr": 1, "hour": 1, "day": 24
}
CATEGORY_MAP = {
    "Length": {"mm", "cm", "m", "km", "inch", "foot", "yard", "mile"},
    "Mass": {"mg", "g", "kg", "lb", "oz"},
    "Volume": {"ml", "l", "gallon", "pint"},
    "Area": {"sqft", "sqm", "acre", "hectare"},
    "Time": {"sec", "second", "min", "minute", "hr", "hour", "day"}
}

# --- Natural-language currency parsing (EUR, INR, etc.) ---
CURRENCY_SYNONYMS = {
    "USD": {"usd", "us dollar", "us dollars", "dollar", "dollars", "$", "bucks"},
    "EUR": {"eur", "euro", "euros", "€"},
    "INR": {"inr", "indian rupee", "indian rupees", "rupee", "rupees", "₹", "rs", "rs."},
    "GBP": {"gbp", "pound", "pounds", "british pound", "sterling", "£"},
    "JPY": {"jpy", "yen", "¥"},
    "CNY": {"cny", "yuan", "renminbi", "rmb", "元", "￥"},
    "AUD": {"aud", "australian dollar", "aussie dollar"},
    "CAD": {"cad", "canadian dollar"},
    "CHF": {"chf", "swiss franc", "franc"},
    "AED": {"aed", "dirham", "uae dirham"},
}

def _nlw(name: str) -> str:
    """Regex for a name with 'word' boundaries; works for symbols too."""
    return r'(?<!\w)' + re.escape(name) + r'(?!\w)'

def _find_currency_mentions(text: str):
    """Return [(start, end, CODE, matched_name), ...] ordered by position."""
    t = text.lower()
    hits = []
    for code, names in CURRENCY_SYNONYMS.items():
        for name in sorted(names, key=len, reverse=True):
            m = re.search(_nlw(name), t)
            if m:
                hits.append((m.start(), m.end(), code, name))
    hits.sort(key=lambda x: x[0])
    # dedupe by code, keep first occurrence order
    seen = set()
    out = []
    for s, e, code, nm in hits:
        if code not in seen:
            seen.add(code)
            out.append((s, e, code, nm))
    return out

def parse_currency_request(command: str):
    """
    Heuristics:
    - find first number as amount
    - find 2 currency mentions by synonyms/symbols
    - assume first mention = FROM, second = TO
    - supports phrasings like:
      "how much is 20 euros in indian currency"
      "convert 20 euro to inr"
      "₹500 in usd" / "€99 to pounds"
    """
    t = command.lower()
    am = re.search(r'([-+]?\d+(?:\.\d+)?)', t)
    if not am:
        return None  # no amount

    amount = float(am.group(1))
    mentions = _find_currency_mentions(t)
    if len(mentions) >= 2:
        from_code = mentions[0][2]
        to_code   = mentions[1][2]
        return amount, from_code, to_code
    return None

# --------------------------------------
# Helpers: Quick/Complex detection logic
# --------------------------------------
_SIMPLE_TOKENS = set(list("0123456789.+-*/()%^ "))  # minimal arithmetic set

def is_simple_expression(text: str) -> bool:
    """
    True if the input looks like trivial calculator arithmetic:
    - Only digits, ., +, -, *, /, %, ^, parentheses and spaces
    - Not too long, and no keywords like nCr/nPr, log base, gcd/lcm, units, etc.
    """
    t = text.strip().lower()
    if not t:
        return False

    # must be subset of simple tokens
    if any(ch not in _SIMPLE_TOKENS for ch in t):
        return False

    # length / operands heuristic
    nums = re.findall(r'[-+]?\d*\.?\d+', t)
    if len(nums) <= 3 and len(t) <= 32:
        return True
    return False

def wants_steps(text: str) -> bool:
    return bool(re.search(FORCE_VERBOSE_PATTERNS, text.lower()))

def wants_brief(text: str) -> bool:
    return bool(re.search(FORCE_BRIEF_PATTERNS, text.lower()))

# --------------------------------------
# Popup helpers (render + speech)
# --------------------------------------
def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\n", "<br>")
    )

def _html(title: str, result, steps: list, *, showing: str = "steps", topic=None) -> str:
    parts = [f"<h3>{_esc(title)}</h3>"]
    parts.append(f"<p><b>Result:</b> {_esc(result)}</p>")
    if steps:
        parts.append("<ol>" if showing == "steps" else "<ul>")
        for s in steps:
            parts.append(f"<li>{_esc(s)}</li>")
        parts.append("</ol>" if showing == "steps" else "</ul>")
    if topic:
        parts.append(f"<p style='opacity:.7'>Topic: {_esc(topic)}</p>")
    return "\n".join(parts)

def speak_result_ml(value, *, target=None, unit=None, command=None, popup_hint=True):
    """
    Multilingual speech line.
    - When popup_hint=False (quick answers): DON'T mention the popup.
    - When popup_hint=True (non-quick): Physics-style "check the solution popup".
    """
    _speak_multilang, _, _, _ = get_utils()
    value_str = str(value)

    # Base sentences (no popup mention)
    if target and unit:
        en = f"{target} is {value_str} {unit}."
        hi = f"{target} {value_str} {unit} है."
        fr = f"{target} est {value_str} {unit}."
        es = f"{target} es {value_str} {unit}."
        de = f"{target} beträgt {value_str} {unit}."
    elif target:
        en = f"{target} is {value_str}."
        hi = f"{target} {value_str} है."
        fr = f"{target} est {value_str}."
        es = f"{target} es {value_str}."
        de = f"{target} beträgt {value_str}."
    else:
        en = f"The answer is {value_str}."
        hi = f"उत्तर {value_str} है।"
        fr = f"La réponse est {value_str}."
        es = f"La respuesta es {value_str}."
        de = f"Die Antwort ist {value_str}."

    if popup_hint:
        en += " I’ve calculated it — check the solution popup."
        hi += " मैंने गणना कर दी है — पूरी जानकारी पॉप-अप में देखें।"
        fr += " J’ai fait le calcul — consultez la fenêtre contextuelle pour la solution complète."
        es += " He hecho el cálculo — revisa la ventana emergente para la solución completa."
        de += " Ich habe es berechnet — sieh im Popup die vollständige Lösung."

    log_msg = f"🧮 Math: {command} = {value_str}" if command else f"🧮 Math: {value_str}"
    _speak_multilang(en, hi=hi, fr=fr, es=es, de=de, log_command=log_msg)

# --- New multilingual error speakers ---
def speak_no_quick_fact_ml():
    _speak_multilang, _, _, _ = get_utils()
    en = "I don’t have a quick fact for that — try rephrasing or use full physics mode for a detailed answer."
    hi = "इसके लिए मेरे पास कोई त्वरित तथ्य नहीं है — कृपया प्रश्न को बदलकर पूछें या विस्तृत उत्तर के लिए फुल फिजिक्स मोड का उपयोग करें।"
    fr = "Je n’ai pas de fait rapide pour cela — reformulez ou utilisez le mode physique complet pour une réponse détaillée."
    es = "No tengo un dato rápido para eso — intenta reformular o usa el modo de física completo para una respuesta detallada."
    de = "Dazu habe ich keinen Schnellfakt — formuliere bitte um oder nutze den vollständigen Physik-Modus für eine detaillierte Antwort."
    _speak_multilang(en, hi=hi, fr=fr, es=es, de=de, log_command="ℹ️ No quick fact")

def speak_no_formula_ml():
    _speak_multilang, _, _, _ = get_utils()
    en = "I couldn't match this question to any formula. Try rephrasing."
    hi = "मैं इस प्रश्न को किसी सूत्र से नहीं जोड़ सकी। कृपया प्रश्न को बदलकर फिर से पूछें।"
    fr = "Je n’ai pas pu associer cette question à une formule. Essayez de reformuler."
    es = "No pude asociar esta pregunta con ninguna fórmula. Intenta reformular."
    de = "Ich konnte diese Frage keiner Formel zuordnen. Bitte formuliere sie neu."
    _speak_multilang(en, hi=hi, fr=fr, es=es, de=de, log_command="⚠️ No formula")

def speak_need_values_ml():
    _speak_multilang, _, _, _ = get_utils()
    en = "Missing required values or too many unknowns. Please refine the question."
    hi = "आवश्यक मान गायब हैं या अज्ञात बहुत अधिक हैं। कृपया प्रश्न को स्पष्ट करें।"
    fr = "Valeurs requises manquantes ou trop d’inconnues. Affinez la question, s’il vous plaît."
    es = "Faltan valores requeridos o hay demasiadas incógnitas. Por favor, refina la pregunta."
    de = "Erforderliche Werte fehlen oder es gibt zu viele Unbekannte. Bitte präzisiere die Frage."
    _speak_multilang(en, hi=hi, fr=fr, es=es, de=de, log_command="❗ Need values")

# --------------------------------------
# Unit conversions with breadcrumb steps
# --------------------------------------
def convert_units_with_steps(expr: str) -> tuple:
    steps = []
    unit_category = None
    matches = re.findall(r'(\d+(\.\d+)?)\s*(%s)\b' % "|".join(map(re.escape, UNIT_CONVERSIONS.keys())), expr)

    detected_units = set()
    for value, _, unit in matches:
        base = UNIT_CONVERSIONS.get(unit)
        if base is None:
            continue
        numeric_value = float(value)
        converted = numeric_value * base
        expr = re.sub(rf'\b{re.escape(value)}\s*{re.escape(unit)}\b', str(converted), expr, count=1)
        steps.append(f"Converted: {value} {unit} × {base} = {converted} (base units)")
        detected_units.add(unit)

    for category, unit_set in CATEGORY_MAP.items():
        if detected_units.intersection(unit_set):
            unit_category = category
            break

    if unit_category:
        steps.insert(0, f"📦 Category: {unit_category}")

    return expr, steps

# --------------------------------------
# Currency conversion (live)
# --------------------------------------
def handle_currency_conversion(command: str):
    # First try strict 3-letter pattern like "20 EUR to INR"
    m = re.search(
        r'(\d+(\.\d+)?)\s*([A-Za-z]{3})\s*(to|in|into)\s*([A-Za-z]{3})',
        command, re.I
    )
    if m:
        amount = float(m.group(1))
        from_curr = m.group(3).upper()
        to_curr = m.group(5).upper()
    else:
        # Fallback: natural-language parsing ("20 euros in indian currency")
        parsed = parse_currency_request(command)
        if not parsed:
            return None, []  # let other handlers try
        amount, from_curr, to_curr = parsed

    # guard: requests not available
    if requests is None:
        return None, ["❌ Currency lookup unavailable (network library missing)."]

    try:
        url = f"https://api.exchangerate.host/convert?from={from_curr}&to={to_curr}&amount={amount}"
        r = requests.get(url, timeout=6)
        data = r.json()
        result = data["result"]
        rate = data["info"]["rate"]
        steps = [f"Rate fetched: 1 {from_curr} = {rate} {to_curr}",
                 f"Converted: {amount} × {rate} = {result}"]
        return round(result, DEC_PLACES), steps
    except Exception:
        return None, [f"❌ Unable to fetch currency rates for {from_curr}→{to_curr}."]

# --------------------------------------
# Trig simplification
# --------------------------------------
def simplify_trig_expression(expr: str):
    try:
        simplified = trigsimp(sympify(expr))
        if simplified != sympify(expr):
            return simplified, ["Recognized a trigonometric identity:",
                                f"Original: {expr}",
                                f"Simplified: {simplified}"]
    except Exception:
        pass
    return None, []

# --------------------------------------
# Geometry areas
# --------------------------------------
def handle_geometry_formulas(command: str):
    cmd = command.lower()
    steps = []
    try:
        if "area of circle" in cmd:
            r_m = re.search(r'radius\s+(\d+(\.\d+)?)', cmd)
            if not r_m:
                return None, ["❌ Missing radius."]
            r = float(r_m.group(1))
            area = math.pi * r**2
            steps += ["Formula: A = πr²", f"Substitute: π × {r}²", f"Compute: {round(area, DEC_PLACES)}"]
            return round(area, DEC_PLACES), steps

        if "area of square" in cmd:
            a_m = re.search(r'side\s+(\d+(\.\d+)?)', cmd)
            if not a_m:
                return None, ["❌ Missing side."]
            a = float(a_m.group(1))
            area = a**2
            steps += ["Formula: A = a²", f"Substitute: {a}²", f"Compute: {round(area, DEC_PLACES)}"]
            return round(area, DEC_PLACES), steps

        if "area of rectangle" in cmd:
            l_m = re.search(r'length\s+(\d+(\.\d+)?)', cmd)
            b_m = re.search(r'breadth\s+(\d+(\.\d+)?)', cmd)
            if not l_m or not b_m:
                return None, ["❌ Missing length or breadth."]
            l = float(l_m.group(1)); b = float(b_m.group(1))
            area = l * b
            steps += ["Formula: A = l × b", f"Substitute: {l} × {b}", f"Compute: {round(area, DEC_PLACES)}"]
            return round(area, DEC_PLACES), steps
    except Exception:
        return None, []
    return None, []

# --------------------------------------
# Degree ↔ Radian conversions
# --------------------------------------
def handle_angle_conversions(command: str):
    steps = []
    c = command.lower()
    try:
        if "degree" in c and "radian" in c:
            m = re.search(r'(\d+(\.\d+)?)\s*degree', c)
            if not m:
                return None, ["❌ Missing degree value."]
            deg = float(m.group(1))
            rad = deg * (pi / 180)
            steps += ["Formula: rad = deg × (π/180)", f"Substitute: {deg} × π/180 = {round(rad, DEC_PLACES)}"]
            return round(rad, DEC_PLACES), steps

        if "radian" in c and "degree" in c:
            m = re.search(r'(\d+(\.\d+)?)\s*radian', c)
            if not m:
                return None, ["❌ Missing radian value."]
            rad = float(m.group(1))
            deg = rad * (180 / pi)
            steps += ["Formula: deg = rad × (180/π)", f"Substitute: {rad} × 180/π = {round(deg, DEC_PLACES)}"]
            return round(deg, DEC_PLACES), steps
    except Exception:
        return None, []
    return None, []

# --------------------------------------
# Combinatorics (n!, nPr, nCr)
# --------------------------------------
def handle_combinatorics(command: str):
    steps = []
    cmd = command.lower().replace(" ", "")

    # factorial
    m_fact = re.search(r'factorial(\d+)|(\d+)!', cmd)
    if m_fact:
        n = int(m_fact.group(1) or m_fact.group(2))
        expansion = " × ".join(str(i) for i in range(n, 0, -1))
        val = math.factorial(n)
        steps += [f"Formula: {n}! = {expansion}", f"Compute: {val}"]
        return val, steps

    # permutation nPr
    m_pr = re.search(r'(\d+)[pP](\d+)', cmd)
    if m_pr:
        n, r = int(m_pr.group(1)), int(m_pr.group(2))
        if r > n:
            return None, [f"❌ Invalid: r ({r}) cannot be greater than n ({n})."]
        n_fact = math.factorial(n)
        nr_fact = math.factorial(n - r)
        result = n_fact / nr_fact
        steps += ["Formula: nPr = n! / (n - r)!",
                  f"Substitute: {n}! / {n-r}! = {n_fact} / {nr_fact}",
                  f"Compute: {result}"]
        return round(result, DEC_PLACES), steps

    # combination nCr
    m_cr = re.search(r'(\d+)[cC](\d+)', cmd)
    if m_cr:
        n, r = int(m_cr.group(1)), int(m_cr.group(2))
        if r > n:
            return None, [f"❌ Invalid: r ({r}) cannot be greater than n ({n})."]
        n_fact = math.factorial(n)
        r_fact = math.factorial(r)
        nr_fact = math.factorial(n - r)
        result = n_fact / (r_fact * nr_fact)
        steps += ["Formula: nCr = n! / (r!(n - r)!)",
                  f"Substitute: {n}! / ({r}! × {n-r}!)",
                  f"Compute: {result}"]
        return round(result, DEC_PLACES), steps

    return None, []

# --------------------------------------
# Logs / exponents / scientific notation
# --------------------------------------
def handle_logarithmic_expression(command: str):
    steps = []
    cmd = command.lower().replace(" ", "")
    try:
        m_log10 = re.search(r'log(?:base10)?\(?(\d+(\.\d+)?)\)?', cmd)
        if m_log10:
            x = float(m_log10.group(1))
            val = math.log10(x)
            steps += [f"Recognized: log₁₀({x})", f"Compute: {round(val, DEC_PLACES)}"]
            return round(val, DEC_PLACES), steps

        m_ln = re.search(r'(ln|loge)\(?([a-z0-9\.]+)\)?', cmd)
        if m_ln:
            token = m_ln.group(2)
            x = math.e if token == "e" else float(token)
            val = math.log(x)
            steps += [f"Recognized: ln({token})", f"Compute: {round(val, DEC_PLACES)}"]
            return round(val, DEC_PLACES), steps

        m_base = re.search(r'logbase(\d+(\.\d+)?)of(\d+(\.\d+)?)', cmd)
        if m_base:
            base = float(m_base.group(1)); num = float(m_base.group(3))
            val = math.log(num, base)
            steps += [f"Recognized: log base {base} of {num}",
                      "Identity: log_b(x) = log(x)/log(b)",
                      f"Compute: {round(val, DEC_PLACES)}"]
            return round(val, DEC_PLACES), steps

        m_exp = re.search(r'(\d+(\.\d+)?)\^(\d+(\.\d+)?)', cmd)
        if m_exp:
            a = float(m_exp.group(1)); b = float(m_exp.group(3))
            val = a ** b
            steps += [f"Recognized: {a}^{b}", f"Compute: {round(val, DEC_PLACES)}"]
            return round(val, DEC_PLACES), steps
    except Exception:
        return None, []
    return None, []

def handle_scientific_notation(command: str):
    steps = []; c = command.lower()

    m_e = re.search(r'([-+]?\d+(\.\d+)?)[eE]([-+]?\d+)', c)
    if m_e:
        base = float(m_e.group(1)); exp = int(m_e.group(3))
        val = base * (10 ** exp)
        steps += [f"Detected: {base}e{exp}", f"= {base} × 10^{exp} = {val}"]
        return round(val, DEC_PLACES), steps

    m_caret = re.search(r'([-+]?\d+(\.\d+)?)\s*[x×*]\s*10\s*\^?\s*(-?\d+)', c)
    if m_caret:
        base = float(m_caret.group(1)); exp = int(m_caret.group(3))
        val = base * (10 ** exp)
        steps += [f"Detected: {base} × 10^{exp}", f"Compute: {val}"]
        return round(val, DEC_PLACES), steps

    m_uni = re.search(r'([-+]?\d+(\.\d+)?)\s*[x×*]\s*10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)', c)
    if m_uni:
        base = float(m_uni.group(1))
        supmap = {'⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9','⁻':'-'}
        exp = int("".join(supmap.get(ch, '') for ch in m_uni.group(3)))
        val = base * (10 ** exp)
        steps += [f"Detected: {base} × 10^{exp}", f"Compute: {val}"]
        return round(val, DEC_PLACES), steps

    return None, []

# --------------------------------------
# Temperature conversions
# --------------------------------------
def handle_temperature_conversion(command: str):
    c = command.lower().strip()
    steps = []
    try:
        if "celsius" in c and ("fahrenheit" in c or re.search(r'\b\d+\s*f\b', c)):
            m = re.search(r'(\d+(\.\d+)?)\s*(celsius|c)\b', c)
            if not m:
                return None, ["❌ Missing °C value."]
            C = float(m.group(1))
            F = (C * 9/5) + 32
            steps += ["Formula: °F = (°C × 9/5) + 32", f"Substitute: ({C} × 9/5) + 32 = {round(F, DEC_PLACES)}"]
            return round(F, DEC_PLACES), steps

        if ("fahrenheit" in c or re.search(r'\b\d+\s*f\b', c)) and "celsius" in c:
            m = re.search(r'(\d+(\.\d+)?)\s*(fahrenheit|f)\b', c)
            if not m:
                return None, ["❌ Missing °F value."]
            F = float(m.group(1))
            C = (F - 32) * 5/9
            steps += ["Formula: °C = (°F − 32) × 5/9", f"Substitute: ({F} − 32) × 5/9 = {round(C, DEC_PLACES)}"]
            return round(C, DEC_PLACES), steps

        if "celsius" in c and "kelvin" in c:
            m = re.search(r'(\d+(\.\d+)?)\s*(celsius|c)\b', c)
            if not m:
                return None, ["❌ Missing °C value."]
            C = float(m.group(1))
            K = C + 273.15
            steps += ["Formula: K = °C + 273.15", f"Substitute: {C} + 273.15 = {round(K, DEC_PLACES)}"]
            return round(K, DEC_PLACES), steps

        if "kelvin" in c and "celsius" in c:
            m = re.search(r'(\d+(\.\d+)?)\s*(kelvin|k)\b', c)
            if not m:
                return None, ["❌ Missing K value."]
            K = float(m.group(1))
            C = K - 273.15
            steps += ["Formula: °C = K − 273.15", f"Substitute: {K} − 273.15 = {round(C, DEC_PLACES)}"]
            return round(C, DEC_PLACES), steps

        if ("fahrenheit" in c or re.search(r'\b\d+\s*f\b', c)) and "kelvin" in c:
            m = re.search(r'(\d+(\.\d+)?)\s*(fahrenheit|f)\b', c)
            if not m:
                return None, ["❌ Missing °F value."]
            F = float(m.group(1))
            K = ((F - 32) * 5/9) + 273.15
            steps += ["Formula: K = ((°F − 32) × 5/9) + 273.15", f"Substitute: (({F} − 32) × 5/9) + 273.15 = {round(K, DEC_PLACES)}"]
            return round(K, DEC_PLACES), steps

        if "kelvin" in c and ("fahrenheit" in c or re.search(r'\b\d+\s*f\b', c)):
            m = re.search(r'(\d+(\.\d+)?)\s*(kelvin|k)\b', c)
            if not m:
                return None, ["❌ Missing K value."]
            K = float(m.group(1))
            F = ((K - 273.15) * 9/5) + 32
            steps += ["Formula: °F = ((K − 273.15) × 9/5) + 32", f"Substitute: (({K} − 273.15) × 9/5) + 32 = {round(F, DEC_PLACES)}"]
            return round(F, DEC_PLACES), steps
    except Exception:
        return None, []
    return None, []

# --------------------------------------
# Basic statistics
# --------------------------------------
def handle_statistics(command: str):
    steps = []
    nums = [float(x) for x in re.findall(r'[-+]?\d*\.?\d+', command)]
    if not nums:
        return None, ["❌ No numbers detected for statistical analysis."]
    n = len(nums); s = sorted(nums)
    mean_val = statistics.mean(nums)
    median_val = statistics.median(nums)

    # stdev (sample)
    std_steps = []
    if n >= 2:
        diffs = [x - mean_val for x in nums]
        squares = [round(d*d, 4) for d in diffs]
        var = sum(squares) / (n - 1)
        stdev = math.sqrt(var)
        std_steps = [
            "Formula (sample stdev): √(Σ(xᵢ−mean)²/(n−1))",
            f"Mean = {round(mean_val, DEC_PLACES)}",
            f"Deviations = {[round(x, 4) for x in diffs]}",
            f"Squares = {squares}",
            f"Variance ≈ {round(var, DEC_PLACES)}",
            f"stdev ≈ {round(stdev, DEC_PLACES)}"
        ]
    else:
        std_steps = ["❌ Standard Deviation requires at least 2 values."]

    steps += ["📊 Basic Statistics",
              f"Numbers: {nums}",
              "— Mean —",
              f"Mean = (Σ)/n = " + " + ".join(map(str, nums)) + f" / {n} = {round(mean_val, DEC_PLACES)}",
              "— Median —",
              f"Sorted: {s}",
              f"Median = {round(median_val, DEC_PLACES)}",
              "— Standard Deviation —"] + std_steps

    return round(mean_val, DEC_PLACES), steps

# --------------------------------------
# Time math (hours/minutes add/sub)
# --------------------------------------
def handle_time_math(command: str):
    steps = []
    c = command.lower()
    matches = re.findall(r'([-+]?\d*\.?\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)', c)
    if not matches:
        return None, ["❌ No valid time units detected (hours/minutes)."]

    parts_min = []
    steps += ["🕒 Time Math", f"Expression: {command.strip()}", "Convert each to minutes:"]
    for val, unit in matches:
        x = float(val)
        if "hour" in unit or "hr" in unit:
            m = int(round(x * 60))
            steps.append(f"{x} hours → {m} minutes")
        else:
            m = int(round(x))
            steps.append(f"{x} minutes → {m} minutes")
        parts_min.append(m)

    # add or subtract based on presence of "minus" / "-"
    if " minus " in c or re.search(r'\d\s*-\s*\d', c):
        total = parts_min[0] - sum(parts_min[1:])
        op = " - "
    else:
        total = sum(parts_min)
        op = " + "

    steps.append(f"Combine: {'{}'} minutes".format(op.join(map(str, parts_min))) + f" = {total} minutes")

    if total < 0:
        return None, steps + ["❌ Resulting time is negative. Check your input."]

    h = total // 60; m = total % 60
    steps += [f"Back to HH:MM → {h} hours {m} minutes"]
    return f"{h} hours {m} minutes", steps

# --------------------------------------
# Spoken phrase → evaluable expression
# --------------------------------------
def translate_to_expression(command: str):
    expr = command.lower()
    steps = []

    # replace words with symbols
    for word, sym in sorted(OPERATOR_MAP.items(), key=lambda kv: -len(kv[0])):
        if word in expr:
            expr = expr.replace(word, sym)
            steps.append(f"Replaced '{word}' → '{sym}'")

    # units → base numbers
    expr, unit_steps = convert_units_with_steps(expr)
    steps += unit_steps

    # percentages
    expr = re.sub(r'(\d+(\.\d+)?)\s*%\s*of\s*(\d+(\.\d+)?)',
                  lambda m: f"({float(m.group(1))/100} * {m.group(3)})", expr)
    expr = re.sub(r'(\d+(\.\d+)?)\s*%', lambda m: f"({m.group(1)} * 0.01)", expr)
    if "%" in command:
        steps.append("Converted percent to decimal.")

    return expr, steps

def evaluate_expression(expr: str):
    try:
        return eval(expr, {"__builtins__": None}, math.__dict__)
    except Exception:
        raise ValueError("Invalid math expression.")

# --------------------------------------
# Hint builder (concise scaffolding)
# --------------------------------------
def build_hints(command: str, topic: str, full_steps: list):
    """
    Produce concise guidance bullets (no '💡 Hints' label in the UI).
    """
    hints = []  # <— no header item; just bullets
    t = topic

    formula_line = next((s for s in full_steps if "Formula" in s or "Identity" in s), None)

    if t == "combinatorics":
        hints += [
            "Identify whether it’s nPr (order matters) or nCr (order doesn’t).",
            formula_line or "Recall: nCr = n! / (r!(n−r)!) and nPr = n! / (n−r)!",
            "Compute factorials carefully; reduce before multiplying to avoid overflow."
        ]
    elif t == "log":
        hints += [
            "Check the requested base: log base 10, e, or b?",
            formula_line or "Use: log_b(x) = log(x)/log(b).",
            "Evaluate and round to 2 decimal places."
        ]
    elif t == "geometry":
        hints += [
            "Write down the geometry formula.",
            formula_line or "Circle: A = πr², Rectangle: A = l×b, Square: A = a².",
            "Substitute the given dimensions and compute."
        ]
    elif t == "stats":
        hints += [
            "Sort the numbers; compute mean = (sum)/n.",
            "For median: middle value (or average of two middles).",
            "Sample stdev: √(Σ(x−mean)²/(n−1))."
        ]
    elif t == "time":
        hints += [
            "Convert all hours to minutes.",
            "Add or subtract minutes as requested.",
            "Convert the total back to hours:minutes."
        ]
    elif t == "currency":
        hints += [
            "Fetch the current FX rate.",
            "Multiply the amount by the rate.",
            "Mind rounding/formatting to 2 decimals."
        ]
    elif t == "angles":
        hints += [
            "Identify direction: degrees→radians or radians→degrees.",
            formula_line or "Use π/180 or 180/π to convert.",
            "Round to 2 decimals."
        ]
    elif t == "sci":
        hints += [
            "Rewrite a×10^b as a * (10**b).",
            "Compute the power of 10 first, then multiply.",
            "Mind positive vs negative exponents."
        ]
    elif t == "temp":
        hints += [
            "Pick the right conversion pair (°C↔°F↔K).",
            formula_line or "E.g., °F = (°C×9/5)+32, K=°C+273.15.",
            "Substitute and compute."
        ]
    elif t == "units":
        hints += [
            "Convert every quantity to the same base unit first.",
            "Carry the conversion factors explicitly.",
            "Compute after all units match."
        ]
    else:
        hints += [
            "Rewrite the spoken expression as symbols.",
            "Respect operator precedence ((), ^, ×, ÷, +, −).",
            "Compute and round to 2 decimals."
        ]
    return hints

# --- Failure classifier (drives which error line to speak) ---
def _classify_failure(text: str):
    t = (text or "").lower()
    has_number = bool(re.search(r'\d', t))
    has_operator = bool(re.search(r'[\+\-\*/\^%()]', t)) or any(k in t for k in OPERATOR_MAP.keys())
    has_keyword = bool(re.search(
        r'\b(area|mean|median|stdev|standard deviation|log|ln|degree|radian|celsius|fahrenheit|kelvin|'
        r'permutation|combination|ncr|npr|factorial|percent|percentage|sqrt|square root|statistics|time|hour|minute)\b', t))

    if has_keyword and not has_number:
        return "need_values"
    if has_number and not has_operator:
        return "no_formula"
    return "no_quick_fact"

# --------------------------------------
# Master handler (Quick + Hint Mode)
# --------------------------------------
def handle_basic_math(command: str):
    _speak_multilang, selected_language, log, say_show_map = get_utils()
    text = command or ""
    try:
        # QUICK PATH: trivial arithmetic → speech only (NO popup mention)
        if is_simple_expression(text) and not wants_steps(text):
            expr, _ = translate_to_expression(text)
            result = evaluate_expression(expr)
            result = round(result, DEC_PLACES)
            speak_result_ml(result, command=command, popup_hint=False)  # <-- no popup mention
            return result  # no popup

        # Otherwise, try specialized handlers (complex topics)
        topic = None
        result = None
        steps = []

        # 1) trig simplify
        if result is None:
            simp, s = simplify_trig_expression(text)
            if simp is not None:
                result = float(simp) if getattr(simp, "is_number", False) else str(simp)
                steps = s
                topic = "expr"

        # 2) currency
        if result is None:
            result, s = handle_currency_conversion(text)
            if result is not None:
                steps = s; topic = "currency"

        # 3) geometry
        if result is None:
            result, s = handle_geometry_formulas(text)
            if result is not None:
                steps = s; topic = "geometry"

        # 4) gcd/lcm, factorial, nPr, nCr
        if result is None:
            result, s = handle_combinatorics(text)
            if result is not None:
                steps = s; topic = "combinatorics"

        # 5) angles
        if result is None:
            result, s = handle_angle_conversions(text)
            if result is not None:
                steps = s; topic = "angles"

        # 6) scientific notation
        if result is None:
            result, s = handle_scientific_notation(text)
            if result is not None:
                steps = s; topic = "sci"

        # 7) statistics
        if result is None:
            result, s = handle_statistics(text)
            if result is not None:
                steps = s; topic = "stats"

        # 8) logs/exponents
        if result is None:
            result, s = handle_logarithmic_expression(text)
            if result is not None:
                steps = s; topic = "log"

        # 9) temperatures
        if result is None:
            result, s = handle_temperature_conversion(text)
            if result is not None:
                steps = s; topic = "temp"

        # 10) time math
        if result is None:
            result, s = handle_time_math(text)
            if result is not None:
                steps = s; topic = "time"

        # 11) generic expression evaluation (with spoken→symbol + units)
        if result is None:
            expr, extra = translate_to_expression(text)
            if not expr:
                raise ValueError("Could not parse expression.")
            val = evaluate_expression(expr)
            result = round(val, DEC_PLACES) if isinstance(val, (int, float)) else val
            steps = extra + [f"Evaluated: {expr} = {result}"]
            topic = "expr"

        # Decide whether to show full steps or hint mode
        present_steps = steps
        showing = "steps"
        if AUTO_HINTS and not wants_steps(text):
            complex_topics = {"combinatorics","log","geometry","stats","time","currency","angles","sci","temp","units"}
            if topic in complex_topics:
                present_steps = build_hints(command, topic, steps)
                showing = "hints"

        # POPUP HTML
        topic_title = {
            "currency": "Currency Conversion",
            "geometry": "Geometry",
            "combinatorics": "Combinatorics",
            "angles": "Angle Conversion",
            "sci": "Scientific Notation",
            "stats": "Statistics",
            "log": "Logarithms/Exponents",
            "temp": "Temperature",
            "time": "Time Math",
            "units": "Unit Conversion",
            "expr": "Expression"
        }.get(topic or "expr", "Expression")

        html = _html(f"Math — {topic_title}", result, present_steps, showing=showing)

        # ✅ SAY (multilingual) → THEN SHOW POPUP (after speech)
        # (Keep wording simple; the popup itself carries the detailed steps)
        value_str = str(result)
        en = f"The answer is {value_str}."
        hi = f"उत्तर {value_str} है।"
        fr = f"La réponse est {value_str}."
        es = f"La respuesta es {value_str}."
        de = f"Die Antwort ist {value_str}."
        say_show_map(
            title=f"Math — {topic_title}",
            en=en, hi=hi, fr=fr, es=es, de=de,
            html=html,
            log_command=f"🧮 Math: {command} = {value_str}"
        )

        return result

    except Exception as e:
        _speak_multilang, _, log, say_show_map = get_utils()
        log.error(f"❌ Math Error: {e}")

        # Classify failure → sentence + title
        kind = _classify_failure(text)
        if kind == "need_values":
            en = "Missing required values or too many unknowns. Please refine the question."
            hi = "आवश्यक मान गायब हैं या अज्ञात बहुत अधिक हैं। कृपया प्रश्न को स्पष्ट करें।"
            fr = "Valeurs requises manquantes ou trop d’inconnues. Affinez la question, s’il vous plaît."
            es = "Faltan valores requeridos o hay demasiadas incógnitas. Por favor, refina la pregunta."
            de = "Erforderliche Werte fehlen oder es gibt zu viele Unbekannte. Bitte präzisiere die Frage."
            title = "Math — Need Values"
        elif kind == "no_formula":
            en = "I couldn't match this question to any formula. Try rephrasing."
            hi = "मैं इस प्रश्न को किसी सूत्र से नहीं जोड़ सकी। कृपया प्रश्न को बदलकर फिर से पूछें।"
            fr = "Je n’ai pas pu associer cette question à une formule. Essayez de reformuler."
            es = "No pude asociar esta pregunta con ninguna fórmula. Intenta reformular."
            de = "Ich konnte diese Frage keiner Formel zuordnen. Bitte formuliere sie neu."
            title = "Math — No Formula"
        else:
            en = "I don’t have a quick fact for that — try rephrasing or use full physics mode for a detailed answer."
            hi = "इसके लिए मेरे पास कोई त्वरित तथ्य नहीं है — कृपया प्रश्न को बदलकर पूछें या विस्तृत उत्तर के लिए फुल फिजिक्स मोड का उपयोग करें।"
            fr = "Je n’ai pas de fait rapide pour cela — reformulez ou utilisez le mode physique complet pour une réponse détaillée."
            es = "No tengo un dato rápido para eso — intenta reformular o usa el modo de física completo para una respuesta detallada."
            de = "Dazu habe ich keinen Schnellfakt — formuliere bitte um oder nutze den vollständigen Physik-Modus für eine detaillierte Antwort."
            title = "Math — Not a Quick Fact"

        err_steps = [
            "❌ Could not evaluate expression.",
            f"Input: {text}",
            f"Reason class: {kind}",
            f"Details: {e}"
        ]
        html = _html(title, "—", err_steps, showing="steps")

        # ✅ Speak the appropriate error line first, then show the error popup
        say_show_map(
            title=title,
            en=en, hi=hi, fr=fr, es=es, de=de,
            html=html,
            log_command="❌ Math Error"
        )
        return None
