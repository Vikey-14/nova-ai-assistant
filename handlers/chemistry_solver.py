# handlers/chemistry_solver.py

from __future__ import annotations

import os, json, re, math, difflib, threading, time, tempfile, contextlib
from typing import Any, Dict, List, Optional, Tuple
import ssl, importlib.util, urllib.request

import logging
logger = logging.getLogger("NOVA")

# === NEW: use utils for PyInstaller-safe paths and UTF-8 JSON ===
from utils import data_path, load_json_utf8, pkg_path


# --- SAY→SHOW helpers (match Physics behavior) ---
from say_show import say_show  # add this import near the top

def _is_gui_visible() -> bool:
    """
    Best-effort: returns True if the main GUI is visible.
    Mirrors the Physics helper so concise answers can SAY→SHOW.
    """
    try:
        from utils import is_gui_visible
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
        for k in ("gui_visible", "ui_visible", "window_visible", "main_window_shown", "gui_open"):
            if k in s:
                return bool(s.get(k))
    except Exception:
        pass
    return False

def _say_or_show_ml(*, en: str, hi: str=None, fr: str=None, es: str=None, de: str=None):
    """
    If GUI is up → send a chat bubble AND speak (say_show).
    If GUI isn't visible → speak only (uses say_ml you already have).
    """
    if _is_gui_visible():
        # fall back to EN if others not provided
        say_show(en, hi=hi or en, fr=fr or en, es=es or en, de=de or en, title="Nova")
    else:
        # chemistry already defines say_ml(..) later; this will work
        say_ml(en=en, hi=hi, fr=fr, es=es, de=de)


# --- Force-English speech (no fallback languages) ---
def _say_en(line: str):
    # Speak with English voice only (prevents Hindi/French voice reading English)
    from utils import _speak_multilang
    _speak_multilang(en=line)

def _say_or_show_en(line: str):
    # If GUI visible → show bubble + speak EN; else → speak EN only
    from say_show import say_show
    if _is_gui_visible():
        # show English bubble; speak English
        try:
            say_show(line, title="Nova")
        except Exception:
            pass
        _say_en(line)
    else:
        _say_en(line)

# -------------------------------
# Global config / paths
# -------------------------------
DEC_PLACES = 2  # ✅ standard rounding for displayed numbers

# --- Concise mode (auto one-liners for basic questions)
AUTO_CONCISE = True  # flip to False to force GUI everywhere
FORCE_BRIEF_PATTERNS = r"\b(brief|quick answer|just answer|no steps|one liner|one-line|tldr|tl;dr|short|summary|summarize|quickly|fast)\b"
FORCE_VERBOSE_PATTERNS = r"\b(show steps|explain|why|how|derivation|proof|walk me through|details|step by step)\b"

# Intents that are "calculational" (we always show steps when Chem Mode is ON)
CALC_INTENTS = {
    "molar_mass", "stoich", "molarity", "gas_law", "dilution",
    "acid_base", "range", "composition",
    "empirical_formula", "molality", "limiting_reagent", "mixing",
    "molarity_molality"
}

# Packaged (PyInstaller): <bundle>/data/chemistry_table.json
# Dev (source checkout):  <project_root>/data/chemistry_table.json
CHEM_JSON_PATH = str(data_path("chemistry_table.json"))

# Upstream fallback (when your local fetch script isn’t present)
CHEM_SRC_URL = "https://raw.githubusercontent.com/Bowserinator/Periodic-Table-JSON/master/PeriodicTableJSON.json"

# =========================
# Chemistry table auto-refresh (48h, zero-config)
# =========================
REFRESH_EVERY_SECS = 48 * 3600
_autorefresh_started = False
_REFRESH_LOCK: Optional[threading.Lock] = None

def _atomic_write_json(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=os.path.dirname(path)) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    os.replace(tmp_path, path)  # atomic on POSIX/Windows

def _try_import_fetch_script():
    """
    Try to import your fetch_chem_table.py and return its main().
    Search order:
      1) Normal import (if on PYTHONPATH)
      2) <app>/scripts/fetch_chem_table.py (dev & PyInstaller onedir)
    """
    try:
        from fetch_chem_table import main as _fetch_main  # type: ignore
        return _fetch_main
    except Exception:
        pass

    fetch_path = str(pkg_path("scripts", "fetch_chem_table.py"))
    if os.path.exists(fetch_path):
        spec = importlib.util.spec_from_file_location("fetch_chem_table", fetch_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            if hasattr(mod, "main"):
                return getattr(mod, "main")
    return None

def _download_direct(url: str) -> bytes:
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
        return r.read()

def _file_is_stale(path: str) -> bool:
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        return True
    return (time.time() - mtime) > REFRESH_EVERY_SECS

def _clear_element_caches():
    """
    If you cache parsed elements elsewhere in this module, clear them here.
    (Keep the names in sync with your module-level globals.)
    """
    globals_to_clear = ["_ELEMENTS", "_BY_SYMBOL", "_BY_NAME", "_CATEGORIES_LOWER", "_SYMBOLS_SET"]
    for g in globals_to_clear:
        if g in globals():
            try:
                if isinstance(globals()[g], dict):
                    globals()[g].clear()
                elif isinstance(globals()[g], list):
                    globals()[g].clear()
                else:
                    globals()[g] = None
            except Exception:
                globals()[g] = None

def _refresh_if_stale(force: bool = False, log: bool = True):
    """
    Refresh chemistry_table.json if older than 48h (or force=True).
    Prefers your fetch_chem_table.py; falls back to direct download.
    Writes to CHEM_JSON_PATH (UTF-8). Clears in-memory caches afterward.
    """
    global _REFRESH_LOCK
    if _REFRESH_LOCK is None:
        _REFRESH_LOCK = threading.Lock()

    if not force and not _file_is_stale(CHEM_JSON_PATH):
        return

    if not _REFRESH_LOCK.acquire(blocking=False):
        return  # another thread is refreshing

    try:
        fetch_main = _try_import_fetch_script()
        if fetch_main:
            try:
                logger.info("Chem table: refreshing via fetch_chem_table.py")
            except Exception:
                pass
            # Expected to write to CHEM_JSON_PATH (root/data/chemistry_table.json)
            fetch_main()
        else:
            try:
                logger.info("Chem table: refreshing via direct download")
            except Exception:
                pass
            data = _download_direct(CHEM_SRC_URL)

            # Optional: add tiny attribution block
            try:
                j = json.loads(data.decode("utf-8"))
                j["_nova_attribution"] = {
                    "source": "Bowserinator/Periodic-Table-JSON",
                    "license": "CC BY-SA 3.0",
                    "url": "https://github.com/Bowserinator/Periodic-Table-JSON",
                }
                data = json.dumps(j, ensure_ascii=False, indent=2).encode("utf-8")
            except Exception:
                pass

            _atomic_write_json(CHEM_JSON_PATH, data)

        _clear_element_caches()  # next load picks up the new file
        if log:
            try:
                logger.info("Chem table: refresh complete")
            except Exception:
                pass
    except Exception as e:
        if log:
            try:
                logger.warning(f"Chem table refresh failed: {e}")
            except Exception:
                pass
    finally:
        try:
            _REFRESH_LOCK.release()
        except Exception:
            pass

def _autorefresh_worker():
    # One opportunistic refresh on startup (non-blocking)
    _refresh_if_stale(force=False, log=False)
    while True:
        time.sleep(REFRESH_EVERY_SECS)
        _refresh_if_stale(force=False, log=True)

def _start_autorefresh_once():
    """Public: called from main.py to start background refresh thread once."""
    global _autorefresh_started
    if _autorefresh_started:
        return
    _autorefresh_started = True
    t = threading.Thread(target=_autorefresh_worker, daemon=True, name="chem-json-autorefresh")
    t.start()

# -------------------------------
# Lazy import (avoids circular deps)
# -------------------------------
def lazy_imports():
    """
    Pull in the stable GUI/event + logging hooks at runtime so we avoid
    circular imports. Falls back to safe no-ops if utils/GUI isn't ready.
    """
    from typing import Any
    global emit_to_gui_bus, log_interaction, selected_language, _speak_multilang

    # Prefer the stable event bus
    try:
        from utils import emit_gui as _bus  # type: ignore
    except Exception:
        def _bus(channel: str, payload: Any) -> None:
            return None
    emit_to_gui_bus = _bus

    # Logging + language + optional speak helper
    try:
        from utils import log_interaction, selected_language, _speak_multilang  # type: ignore
    except Exception:
        def log_interaction(*args, **kwargs) -> None:
            return None
        try:
            selected_language = "en"  # type: ignore
        except Exception:
            pass
        def _speak_multilang(*args, **kwargs) -> None:
            return None

def say_ml(*, en: str, hi: Optional[str] = None, fr: Optional[str] = None,
           es: Optional[str] = None, de: Optional[str] = None):
    """Concise one-liner, multilingual; falls back to EN if others aren’t provided."""
    lazy_imports()
    _speak_multilang(
        en=en,
        hi=hi or en,
        fr=fr or en,
        es=es or en,
        de=de or en,
    )

def speak_answer(*, target: str, value: str, unit: str = ""):
    """Long-form (GUI) summary line, multilingual, feminine tone where applicable."""
    lazy_imports()
    unit_part = f" {unit}" if unit else ""
    _speak_multilang(
        en=f"{target} is {value}{unit_part}. I’ve calculated it — check the popup for the full solution.",
        hi=f"{target} {value}{unit_part} है। मैंने गणना कर दी है — पूरी जानकारी पॉपअप में देखें।", 
        fr=f"{target} est {value}{unit_part}. J’ai fait le calcul — consultez la fenêtre contextuelle pour la solution complète.",  
        es=f"{target} es {value}{unit_part}. He hecho el cálculo — revisa la ventana emergente para la solución completa.",  
        de=f"{target} beträgt {value}{unit_part}. Ich habe es berechnet — sieh im Popup für die vollständige Lösung nach."  
    )

def speak_error(msg_en: str = "I couldn’t complete that. Please add one more detail."):
    lazy_imports()
    _speak_multilang(
        en=msg_en,
        hi="मैं यह पूरा नहीं कर सकी। कृपया थोड़ी और जानकारी दें।",
        fr="Je n’ai pas pu terminer. Pourriez-vous ajouter un détail de plus, s’il vous plaît ?",
        es="No pude completarlo. ¿Podrías añadir un detalle más, por favor?",
        de="Ich konnte das nicht abschließen. Bitte gib noch ein Detail an.",
    )

# -------------------------------
# Friendly nudges / tips (multilingual)
# -------------------------------
def _chem_mode_tip() -> Dict[str, str]:
    # short, domain-aware nudge; “chemistry mode” in lowercase
    return {
        "en": "Tip: say “use full chemistry mode” for a step-by-step explanation.",
        "hi": "सुझाव: विस्तृत चरणों के लिए “use full chemistry mode” कहें。",
        "fr": "Astuce : dites « use full chemistry mode » pour une explication détaillée。",
        "es": "Consejo: di «use full chemistry mode» para una explicación paso a paso。",
        "de": "Tipp: Sage „use full chemistry mode“ für eine ausführliche Schritt-für-Schritt-Erklärung。",
    }

def _friendly_nudge_followups() -> List[str]:
    return [
        "Show Hydrogen",
        "Boiling point of Na",
        "Molar mass of H2SO4",
        "Compare electronegativity: Cl vs Br",
        "List noble gas elements",
    ]

# =========================
# Nova UI actions (buttons)
# =========================
NOVA_UI = {
    "primary_color": "#00ffee",  # ✦ More detail pill fill
    "chip_bg": "#202020",        # ghost chip background
    "chip_text": "#00ffee",      # ghost chip text/border
}

def _build_followups(intent: str, context: Dict[str, Any]) -> List[str]:
    """
    Ghost follow-ups only for calculational intents.
    Generic intents must return [] so no chips are rendered.
    """
    # calculational buckets
    CALC_INTENTS = {
        "molar_mass", "composition", "stoich", "molarity", "dilution",
        "gas_law", "acid_base", "empirical_formula", "molality",
        "limiting_reagent", "mixing", "molarity_molality"
    }

    if intent not in CALC_INTENTS:
        return []  # <- critical: no chips for generic/voice answers

    # context-derived helpers (optional)
    e = context.get("last_element") or {}
    sym = e.get("symbol")

    # intent-specific chips
    if intent in {"molar_mass"}:
        return ["Percent composition", "Mass from moles", "Moles from grams"]
    if intent in {"composition"}:
        return ["Show steps", "Molar mass", "Grams of an element…"]
    if intent == "stoich":
        return ["Limiting reagent", "Theoretical yield", "Percent yield"]
    if intent == "molarity":
        return ["Do a dilution", "Mass needed for target M", "Convert to molality"]
    if intent == "dilution":
        return ["Make 250 mL of 0.2 M", "New M after doubling V?", "Back-calc stock needed"]
    if intent == "gas_law":
        return ["Solve PV=nRT", "Boyle’s example", "Charles’ example"]
    if intent == "acid_base":
        return ["pH → [H+]", "Buffer calc", "Titration steps"]
    if intent == "empirical_formula":
        return ["Assume 100 g sample", "Use % composition", "Find molecular formula"]
    if intent == "molality":
        return ["Given grams + formula", "Given moles + solvent kg", "Convert to molarity"]
    if intent == "limiting_reagent":
        return ["Show ICE table", "Compute excess left", "Theoretical yield from ξ"]
    if intent == "mixing":
        return ["Moles after mixing", "What if volumes change?", "Relate to M1V1=M2V2"]
    if intent == "molarity_molality":
        return ["Convert M → m", "Convert m → M", "Assume ρ = 1 g/mL?"]

    # fallback for any future calc intent
    return ["Show steps", "Units check", "Similar problem"]

def _emit_gui(block_html: str, intent: str, show_more: bool, ctx: Dict[str, Any], action: str = "new"):
    """
    Send the block + Nova actions to the UI.
    - Primary CTA: ✦ More detail (only when show_more=True)
    - Chips: labels only; GUI decides styling
    - action: "new" or "append"
    """
    try:
        chip_labels = _build_followups(intent, ctx)
    except Exception:
        chip_labels = []

    actions = {"chips": [{"label": lab} for lab in chip_labels]}
    if show_more:
        actions["primary"] = {"id": "more_detail", "label": "✦ More detail"}

    payload = {
        "html": block_html,
        "action": "append" if action == "append" else "new",
        "actions": actions,
        "ctx": {"original_text": ctx.get("original_text", "")},
    }

    # log exactly what we showed
    try:
        log_interaction(ctx.get("original_text", ""), block_html, selected_language)
    except Exception:
        pass

    # push to GUI via the stable bus grabbed in lazy_imports()
    try:
        emit_to_gui_bus("chemistry", payload)
    except Exception:
        pass


def _should_show_more(concise: bool, intent: str, ctx: Dict[str, Any]) -> bool:
    # Hide "More detail" when Chem Mode is ON and the intent is calculational (already verbose).
    if ctx.get("chem_mode_on") and intent in CALC_INTENTS:
        return False
    # Show the popup only for concise + calculational intents (generic quick facts stay clean).
    return concise and (intent in CALC_INTENTS)

# Property labels i18n (lowercase for inline use)
PROP_I18N = {
    "boil": {"en": "boiling point"},
    "melt": {"en": "melting point"},
    "density": {"en": "density"},
    "atomic_mass": {"en": "atomic mass"},
    "electronegativity_pauling": {"en": "electronegativity"},
    "electron_affinity": {"en": "electron affinity"},
    "ionization_energies": {"en": "first ionization energy"},
    "phase": {"en": "phase"},
    "category": {"en": "category"},
    "number": {"en": "atomic number"},
    "electron_configuration_semantic": {"en": "electron configuration"},
    "molality": {"en": "molality"},
    "molarity": {"en": "molarity"},
    "limiting_reagent": {"en": "limiting reagent"},
    "empirical_formula": {"en": "empirical formula"},
}

def _label(prop_key: str) -> str:
    return PROP_I18N.get(prop_key, {}).get("en", prop_key.replace("_", " ").title())

# -------------------------------
# Dataset loader (cached)
# -------------------------------
_ELEMENTS: List[Dict[str, Any]] = []
_BY_SYMBOL: Dict[str, Dict[str, Any]] = {}
_BY_NAME: Dict[str, Dict[str, Any]] = {}
_CATEGORIES_LOWER: Dict[str, List[Dict[str, Any]]] = {}

def _load_dataset_if_needed():
    """Load chemistry_table.json once, using PyInstaller-safe paths + UTF-8."""
    global _ELEMENTS, _BY_SYMBOL, _BY_NAME, _CATEGORIES_LOWER

    # opportunistic refresh (non-blocking if already fresh)
    try:
        _refresh_if_stale(force=False, log=False)
    except Exception:
        pass

    if _ELEMENTS:
        return  # already loaded

    # ✅ resolve to packaged data folder (dev: <repo>/data, build: dist/Nova/data)
    chem_json = data_path("chemistry_table.json")
    if not chem_json.exists():
        raise FileNotFoundError(f"chemistry_table.json not found at {chem_json}")

    data = load_json_utf8(chem_json)

    # build caches
    _ELEMENTS = data.get("elements", []) or []
    _BY_SYMBOL = {e.get("symbol", "").lower(): e for e in _ELEMENTS if e.get("symbol")}
    _BY_NAME   = {e.get("name",   "").lower(): e for e in _ELEMENTS if e.get("name")}


    _CATEGORIES_LOWER = {}
    for e in _ELEMENTS:
        cat = (e.get("category") or "").lower().strip()
        if cat:
            _CATEGORIES_LOWER.setdefault(cat, []).append(e)


            
# -------------------------------
# Helpers: formatting & units
# -------------------------------
def _fmt_num(x: Optional[float], places: int = DEC_PLACES) -> str:
    if x is None: return "—"
    try: return f"{round(float(x), places)}"
    except Exception: return str(x)

def k_to_c(k: Optional[float]) -> Optional[float]:
    if k is None: return None
    return float(k) - 273.15

def k_to_f(k: Optional[float]) -> Optional[float]:
    if k is None: return None
    return (float(k) * 9/5) - 459.67

def ensure_list(x) -> List[Any]:
    if x is None: return []
    return x if isinstance(x, list) else [x]

def _safe_lower(s: Any) -> str:
    return str(s).lower().strip()

def _short(e: Dict[str, Any]) -> str:
    return f"{e.get('name')} ({e.get('symbol')})"

def _mk_element_stub(e: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": e.get("name"), "symbol": e.get("symbol"), "number": e.get("number")}

# -------------------------------
# Fuzzy matching (symbols/names/categories)
# -------------------------------
def _closest_match(query: str, candidates: List[str], cutoff: float = 0.65) -> Optional[str]:
    matches = difflib.get_close_matches(query, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None

def resolve_element_any(target: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    _load_dataset_if_needed()
    t = _safe_lower(target)
    suggestions: List[str] = []

    if t.isdigit():
        z = int(t)
        for e in _ELEMENTS:
            if e.get("number") == z:
                return e, suggestions

    if t in _BY_SYMBOL: return _BY_SYMBOL[t], suggestions
    if t in _BY_NAME:   return _BY_NAME[t], suggestions

    name_candidates = list(_BY_NAME.keys())
    sym_candidates  = list(_BY_SYMBOL.keys())
    best_name = _closest_match(t, name_candidates)
    best_sym  = _closest_match(t, sym_candidates)
    candidate_strings = []
    if best_name: candidate_strings.append(best_name)
    if best_sym:  candidate_strings.append(best_sym)
    if len(candidate_strings) == 1:
        key = candidate_strings[0]
        e = _BY_NAME.get(key) or _BY_SYMBOL.get(key)
        return e, suggestions
    elif len(candidate_strings) > 1:
        all_candidates = set(candidate_strings)
        more_names = difflib.get_close_matches(t, name_candidates, n=3, cutoff=0.5)
        more_syms  = difflib.get_close_matches(t, sym_candidates,  n=3, cutoff=0.5)
        suggestions = list(dict.fromkeys(list(all_candidates) + more_names + more_syms))[:5]
        return None, suggestions

    starts = [n for n in name_candidates if n.startswith(t)]
    if starts: suggestions = starts[:3]
    return None, suggestions

def filter_by_category_like(text: str) -> Optional[List[Dict[str, Any]]]:
    _load_dataset_if_needed()
    t = _safe_lower(text)

    for cat in _CATEGORIES_LOWER.keys():
        if cat in t:
            return list(_CATEGORIES_LOWER.get(cat, []))

    alias = {
        "noble gases": "noble gas",
        "noble gas": "noble gas",
        "alkali metals": "alkali metal",
        "alkaline earth metals": "alkaline earth metal",
        "halogens": "halogen",
        "transition metals": "transition metal",
        "post transition metals": "post-transition metal",
        "post-transition metals": "post-transition metal",
        "metalloids": "metalloid",
        "polyatomic nonmetals": "polyatomic nonmetal",
        "diatomic nonmetals": "diatomic nonmetal",
        "lanthanides": "lanthanide",
        "actinides": "actinide",
    }
    for k, v in alias.items():
        if k in t:
            return list(_CATEGORIES_LOWER.get(v, []))

    m = re.search(r"\bperiod\s+(\d{1,2})\b", t)
    if m:
        p = int(m.group(1))
        return [e for e in _ELEMENTS if e.get("period") == p]
    m = re.search(r"\bgroup\s+(\d{1,2})\b", t)
    if m:
        g = int(m.group(1))
        return [e for e in _ELEMENTS if e.get("group") == g]

    return None

# -------------------------------
# Property normalization
# -------------------------------
PROPERTY_MAP = {
    "boiling": "boil", "boiling point": "boil", "bp": "boil",
    "melting": "melt", "melting point": "melt", "mp": "melt",
    "density": "density",
    "atomic mass": "atomic_mass", "mass": "atomic_mass",
    "electronegativity": "electronegativity_pauling",
    "pauling electronegativity": "electronegativity_pauling",
    "electron affinity": "electron_affinity",
    "first ionization energy": "ionization_energies",
    "ionization energy": "ionization_energies",
    "phase": "phase",
    "category": "category",
    "standard state": "phase", "state": "phase",
}

def normalize_property(text: str) -> Optional[str]:
    t = _safe_lower(text)
    for k, v in PROPERTY_MAP.items():
        if k in t:
            return v
    if re.search(r"\batomic\s+number\b|\bZ\b", t):
        return "number"
    if re.search(r"\belectron\s+configuration\b", t):
        return "electron_configuration_semantic"
    return None

def extract_compare_targets(text: str) -> Optional[Tuple[str, str]]:
    t = _safe_lower(text)
    for sep in [" vs ", " versus ", " or ", " compared to ", " and "]:
        if sep in t:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if len(parts) == 2:
                return parts[0], parts[1]
    return None

def extract_range_query(text: str) -> Optional[Tuple[str, str, float, Optional[float], bool]]:
    t = _safe_lower(text)
    prop = normalize_property(t)
    temp_prop = False
    if not prop:
        if "boil" in t: prop = "boil"; temp_prop = True
        elif "melt" in t: prop = "melt"; temp_prop = True
        elif "den" in t: prop = "density"
        elif "mass" in t: prop = "atomic_mass"
    if not prop: return None

    m = re.search(r"between\s+(-?\d+\.?\d*)\s*(k|c|f)?\s*(?:and|to)\s*(-?\d+\.?\d*)\s*(k|c|f)?", t, re.I)
    if m:
        v1, u1, v2, u2 = m.groups()
        if prop in ("boil","melt"):
            temp_prop = True
        return (prop, "between", _to_kelvin(float(v1), u1), _to_kelvin(float(v2), u2), temp_prop)

    m = re.search(r"(>=|<=|>|<|=)\s*(-?\d+\.?\d*)\s*(k|c|f)?", t)
    if m:
        op, v, u = m.groups()
        val = _to_kelvin(float(v), u) if prop in ("boil", "melt") else float(v)
        if prop in ("boil","melt"):
            temp_prop = True
        return (prop, op, val, None, temp_prop)
    return None

def _to_kelvin(value: float, unit: Optional[str]) -> float:
    if unit is None: return value
    u = unit.lower()
    if u == "k": return value
    if u == "c": return value + 273.15
    if u == "f": return (value + 459.67) * 5/9
    return value

# -------------------------------
# Concise-mode helpers
# -------------------------------
QUICK_FACT_KEYS = {
    "lightest": ("atomic_mass", "min"),
    "heaviest": ("atomic_mass", "max"),
    "highest boiling": ("boil", "max"),
    "lowest boiling": ("boil", "min"),
    "highest melting": ("melt", "max"),
    "lowest melting": ("melt", "min"),
    "highest density": ("density", "max"),
    "lowest density": ("density", "min"),
    "highest electronegativity": ("electronegativity_pauling", "max"),
    "lowest electronegativity": ("electronegativity_pauling", "min"),
    "highest electron affinity": ("electron_affinity", "max"),
    "lowest electron affinity": ("electron_affinity", "min"),
    "highest ionization energy": ("ionization_energies", "max"),
    "lowest ionization energy": ("ionization_energies", "min"),
    "highest atomic number": ("number", "max"),
    "lowest atomic number": ("number", "min"),
}

_QUICK_PATTERNS: List[Tuple[re.Pattern, Tuple[str, str]]] = [
    (re.compile(r"\b(most|highest|max(imum)?)\s+(electronegative|electronegativity)\b"), ("electronegativity_pauling", "max")),
    (re.compile(r"\b(least|lowest|min(imum)?)\s+(electronegative|electronegativity)\b"), ("electronegativity_pauling", "min")),
    (re.compile(r"\b(most|highest|max(imum)?)\s+(dense|density)\b"), ("density", "max")),
    (re.compile(r"\b(least|lowest|min(imum)?)\s+(dense|density)\b"), ("density", "min")),
    (re.compile(r"\b(most|highest|max(imum)?)\s+(boil(ing)?( point)?|bp)\b"), ("boil", "max")),
    (re.compile(r"\b(least|lowest|min(imum)?)\s+(boil(ing)?( point)?|bp)\b"), ("boil", "min")),
    (re.compile(r"\b(most|highest|max(imum)?)\s+(melt(ing)?( point)?|mp)\b"), ("melt", "max")),
    (re.compile(r"\b(least|lowest|min(imum)?)\s+(melt(ing)?( point)?|mp)\b"), ("melt", "min")),
    (re.compile(r"\blightest|min(imum)?\b.*\b(element\b|atomic mass)\b"), ("atomic_mass", "min")),
    (re.compile(r"\bheaviest|max(imum)?\b.*\b(element\b|atomic mass)\b"), ("atomic_mass", "max")),
    (re.compile(r"\bmax\b.*\bbp\b|\bbp\b.*\bmax\b"), ("boil", "max")),
    (re.compile(r"\bmin\b.*\bbp\b|\bbp\b.*\bmin\b"), ("boil", "min")),
    (re.compile(r"\bmax\b.*\bmp\b|\bmp\b.*\bmax\b"), ("melt", "max")),
    (re.compile(r"\bmin\b.*\bmp\b|\bmp\b.*\bmin\b"), ("melt", "min")),
    (re.compile(r"\bmax\b.*\bdensity|density\b.*\bmax\b"), ("density", "max")),
    (re.compile(r"\bmin\b.*\bdensity|density\b.*\bmin\b"), ("density", "min")),
    (re.compile(r"\b(highest|max(imum)?|largest)\s+atomic\s+number\b|\bhighest\s+Z\b"), ("number", "max")),
    (re.compile(r"\b(lowest|min(imum)?|smallest)\s+atomic\s+number\b|\blowest\s+Z\b"), ("number", "min")),
    (re.compile(r"\b(most|highest|max(imum)?)\s+(electron affinity|ea)\b"), ("electron_affinity", "max")),
    (re.compile(r"\b(least|lowest|min(imum)?)\s+(electron affinity|ea)\b"), ("electron_affinity", "min")),
    (re.compile(r"\b(most|highest|max(imum)?)\s+((first\s+)?ionization energy|ie1?)\b"), ("ionization_energies", "max")),
    (re.compile(r"\b(least|lowest|min(imum)?)\s+((first\s+)?ionization energy|ie1?)\b"), ("ionization_energies", "min")),
]

def _pick_extreme(prop_key: str, how: str):
    _load_dataset_if_needed()
    elems: List[Tuple[Dict[str, Any], float]] = []
    for e in _ELEMENTS:
        val = e.get(prop_key)
        if val is None:
            continue
        if prop_key == "ionization_energies":
            arr = ensure_list(val)
            if not arr:
                continue
            try:
                val = float(arr[0])
            except Exception:
                continue
        try:
            val = float(val)
        except Exception:
            continue
        elems.append((e, val))
    if not elems:
        return None
    chosen = (min if how == "min" else max)(elems, key=lambda t: t[1])
    return chosen[0]

def _parse_quick_fact_query(t: str):
    t = _safe_lower(t)
    for k in QUICK_FACT_KEYS.keys():
        if k in t:
            return QUICK_FACT_KEYS[k], k
    for pat, mapping in _QUICK_PATTERNS:
        if pat.search(t):
            prop_key, how = mapping
            ph = f"{'highest' if how=='max' else 'lowest'} {PROP_I18N.get(prop_key, {}).get('en', prop_key)}"
            return mapping, ph
    if "lightest" in t: return (("atomic_mass", "min"), "lightest")
    if "heaviest" in t: return (("atomic_mass", "max"), "heaviest")
    return None, None

def should_use_concise(text: str, intent: str, ctx: Optional[Dict[str, Any]] = None) -> bool:
    """
    Chem-mode–aware verbosity:
    - If force_verbose_once: always verbose (return False), then UI should reset the flag.
    - If Chem Mode ON and intent is calculational: verbose (return False).
    - Else: concise for simple asks; verbose for complex/tabular.
    """
    t = _safe_lower(text)
    ctx = ctx or {}

    # One-shot override (e.g., after a "More detail" click)
    if ctx.get("force_verbose_once"):
        return False

    # Full chemistry mode: always show steps for calculational intents
    if ctx.get("chem_mode_on") and intent in CALC_INTENTS:
        return False

    # Heuristic overrides
    if re.search(FORCE_VERBOSE_PATTERNS, t): return False
    if re.search(FORCE_BRIEF_PATTERNS, t):   return True
    if not AUTO_CONCISE:                     return False

    # Always concise
    if intent in ("quick_fact", "overview"):
        return True

    # Often concise (unless user asks "why/explain/trend")
    if intent == "property":
        if not re.search(r"(trend|across|down|period|group|why|explain)", t):
            return True
    if intent == "compare":
        if not re.search(r"(why|explain)", t):
            return True

    # ✅ Calculational intents default to concise in Chem Mode OFF,
    # unless user explicitly asks for steps.
    CALC_CONCISE_DEFAULT = {
        "molar_mass", "stoich", "molarity", "gas_law", "dilution",
        "acid_base", "composition",
        "empirical_formula", "molality", "limiting_reagent", "mixing", "molarity_molality"
    }
    if intent in CALC_CONCISE_DEFAULT:
        if not re.search(r"(steps|show|explain|why|how)", t):
            return True

    # Ranges/lists and other complex outputs: verbose by default
    return False

# -------------------------------
# GUI block
# -------------------------------
def _format_gui_block(question: str, understanding: str, lines: List[str],
                      short_answer: str, followups: Optional[List[str]] = None) -> str:
    s = []
    s.append(f"🧠 Question:\n{question}\n")
    s.append(f"📘 Understanding\n{understanding}\n")
    if lines:
        s.append("🧮 Data & Units\n" + "\n".join(lines) + "\n")
    # Renamed heading per spec (no '(Short)')
    s.append(f"✅ Answer\n{short_answer}\n")
    if followups:
        s.append("🔁 Follow-ups you can ask\n" + " • ".join(followups))
    return "\n".join(s)

def _fmt_temp_bundle(kval: Optional[float], label: str) -> str:
    c = k_to_c(kval)
    f = k_to_f(kval)
    return (
        f"{label}: **{_fmt_num(kval)} K**"
        + (f" (≈ **{_fmt_num(c)} °C**, **{_fmt_num(f)} °F**)" if kval is not None else "")
    )

# -------------------------------
# Core answering primitives
# -------------------------------
def answer_element_overview(e: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    understanding = "You’re asking for an element overview."
    lines = [
        f"Name: **{e.get('name')}**  |  Symbol: **{e.get('symbol')}**  |  Z: **{e.get('number')}**",
        f"Atomic mass: **{_fmt_num(e.get('atomic_mass'))} u**",
        f"Category: **{e.get('category','—')}**  •  Period: **{e.get('period','—')}**  •  Group: **{e.get('group','—')}**",
        f"Standard state (STP): **{e.get('phase','—')}**  •  Density: **{_fmt_num(e.get('density'))} g/cm³**",
        _fmt_temp_bundle(e.get('melt'), "Melting point"),
        _fmt_temp_bundle(e.get('boil'), "Boiling point"),
        f"Electronegativity (Pauling): **{_fmt_num(e.get('electronegativity_pauling'))}**",
        f"Electron configuration: {e.get('electron_configuration_semantic') or e.get('electron_configuration') or '—'}",
        f"Discovered by: **{e.get('discovered_by','—')}**",
    ]
    short = f"{_short(e)} — Z={e.get('number')}, mass {_fmt_num(e.get('atomic_mass'))} u, {_fmt_num(e.get('density'))} g/cm³, mp {_fmt_num(e.get('melt'))} K, bp {_fmt_num(e.get('boil'))} K."
    return understanding, short, lines

def answer_property(e: Dict[str, Any], prop_key: str) -> Tuple[str, str, List[str]]:
    prop_val = e.get(prop_key)
    understanding = "You’re asking for a single property of a known element."
    lines: List[str] = []
    if prop_key in ("boil", "melt"):
        lines.append(_fmt_temp_bundle(prop_val, _label(prop_key).title()))
    elif prop_key == "density":
        lines.append(f"Density: **{_fmt_num(prop_val)} g/cm³**")
    elif prop_key == "atomic_mass":
        lines.append(f"Atomic mass: **{_fmt_num(prop_val)} u**")
    elif prop_key == "electronegativity_pauling":
        lines.append(f"Electronegativity (Pauling): **{_fmt_num(prop_val)}**")
    elif prop_key == "electron_affinity":
        lines.append(f"Electron affinity: **{_fmt_num(prop_val)} kJ/mol**")
    elif prop_key == "ionization_energies":
        ie = ensure_list(prop_val)
        lines.append(f"First ionization energy: **{_fmt_num(ie[0] if ie else None)} kJ/mol**")
    elif prop_key in ("number","phase","category","electron_configuration_semantic"):
        pretty = {
            "number": f"Atomic number (Z): **{prop_val}**",
            "phase": f"Standard state (STP): **{prop_val or '—'}**",
            "category": f"Category: **{prop_val or '—'}**",
            "electron_configuration_semantic": f"Electron configuration: {prop_val or '—'}"
        }
        lines.append(pretty[prop_key])
    else:
        lines.append(f"{_label(prop_key).title()}: **{prop_val}**")

    human = _label(prop_key)
    short = f"{_short(e)} — {human} = " + (
        f"{_fmt_num(prop_val)}" if prop_key not in ("boil","melt") else f"{_fmt_num(prop_val)} K"
    )
    return understanding, short, lines

def answer_list(title: str, items: List[Dict[str, Any]], limit: int = 12) -> Tuple[str, str, List[str]]:
    understanding = f"You’re asking for a set of elements: {title}."
    head = "Symbol  |  Name  |  Z  |  State"
    rows = []
    for e in items[:limit]:
        z = e.get("number")
        rows.append(f"{e.get('symbol'):>2}  |  {e.get('name'):12}  |  {str(z or '—').rjust(2)}  |  {e.get('phase','—')}")
    if len(items) > limit:
        rows.append(f"... and {len(items)-limit} more")
    short = f"{title}: {', '.join([e.get('symbol') for e in items[:6]])}" + ("…" if len(items) > 6 else "")
    return understanding, short, [head] + rows

def answer_compare(prop_key: str, e1: Dict[str, Any], e2: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    understanding = "You’re comparing a property between two elements."
    v1 = _value_for_compare(prop_key, e1)
    v2 = _value_for_compare(prop_key, e2)
    lines = []
    human = _label(prop_key)

    if prop_key in ("boil","melt"):
        lines.append(_fmt_temp_bundle(v1, f"{_short(e1)} — {human}"))
        lines.append(_fmt_temp_bundle(v2, f"{_short(e2)} — {human}"))
    else:
        label = {
            "density": "Density (g/cm³)",
            "atomic_mass": "Atomic mass (u)",
            "electronegativity_pauling": "Electronegativity (Pauling)"
        }.get(prop_key, human.title())
        lines.append(f"{_short(e1)} — {label}: **{_fmt_num(v1)}**")
        lines.append(f"{_short(e2)} — {label}: **{_fmt_num(v2)}**")

    verdict = _compare_verdict(prop_key, v1, v2, e1, e2)
    short = verdict
    return understanding, short, lines

def _value_for_compare(prop_key: str, e: Dict[str, Any]) -> Optional[float]:
    if prop_key == "ionization_energies":
        arr = ensure_list(e.get(prop_key))
        return arr[0] if arr else None
    return e.get(prop_key)

def _compare_verdict(prop_key: str, v1: Optional[float], v2: Optional[float], e1: Dict[str, Any], e2: Dict[str, Any]) -> str:
    human = _label(prop_key)
    if v1 is None or v2 is None:
        return f"Data insufficient to compare {_short(e1)} and {_short(e2)} for {human}."
    if v1 > v2:
        return f"{_short(e1)} has a higher {human} than {_short(e2)}."
    elif v2 > v1:
        return f"{_short(e2)} has a higher {human} than {_short(e1)}."
    else:
        return f"{_short(e1)} and {_short(e2)} have the same {human}."


# -------------------------------
# Calculators
# -------------------------------
_SYMBOLS_SET = None
def _symbols_set():
    global _SYMBOLS_SET
    if _SYMBOLS_SET is None:
        _load_dataset_if_needed()
        _SYMBOLS_SET = set(s.upper() for s in _BY_SYMBOL.keys())
    return _SYMBOLS_SET

def parse_formula(formula: str) -> Dict[str, int]:
    f = formula.replace("·", ".").strip()
    tokens = re.findall(r"([A-Z][a-z]?|\d+|[().])", f)
    if not tokens:
        raise ValueError("Invalid chemical formula.")

    def read_group(idx=0):
        counts: Dict[str, int] = {}
        i = idx
        while i < len(tokens):
            tok = tokens[i]
            if tok == "(":
                inner, j = read_group(i + 1)
                i = j
                mult = 1
                if i < len(tokens) and tokens[i].isdigit():
                    mult = int(tokens[i]); i += 1
                for el, c in inner.items():
                    counts[el] = counts.get(el, 0) + c * mult
            elif tok == ")":
                return counts, i + 1
            elif tok == ".":
                i += 1
            elif tok.isdigit():
                raise ValueError("Malformed formula near number.")
            else:
                el = tok
                if el.upper() not in _symbols_set():
                    raise ValueError(f"Unknown element symbol '{el}'.")
                i += 1
                mult = 1
                if i < len(tokens) and tokens[i].isdigit():
                    mult = int(tokens[i]); i += 1
                counts[el] = counts.get(el, 0) + mult
        return counts, i

    counts, _ = read_group(0)
    return counts

def molar_mass(formula: str) -> float:
    _load_dataset_if_needed()
    counts = parse_formula(formula)
    mass = 0.0
    for el, n in counts.items():
        e = _BY_SYMBOL.get(el.lower())
        if not e:
            raise ValueError(f"Symbol '{el}' not found in table.")
        mass += float(e.get("atomic_mass", 0)) * n
    return mass

def percent_composition(formula: str) -> Tuple[float, List[Tuple[str, int, float, float]]]:
    """
    Returns total molar mass and a list of tuples:
    (element_symbol, count, mass_contribution_u, percent_by_mass)
    """
    _load_dataset_if_needed()
    counts = parse_formula(formula)
    total_u = 0.0
    contributions: List[Tuple[str, int, float]] = []
    for el, n in counts.items():
        e = _BY_SYMBOL.get(el.lower())
        if not e:
            raise ValueError(f"Symbol '{el}' not found in table.")
        aw = float(e.get("atomic_mass", 0.0))
        contrib = aw * n
        contributions.append((el, n, contrib))
        total_u += contrib
    details: List[Tuple[str, int, float, float]] = []
    for el, n, contrib in contributions:
        pct = (contrib / total_u) * 100.0 if total_u > 0 else 0.0
        details.append((el, n, contrib, pct))
    return total_u, details

def stoich_moles_from_grams(grams: float, formula: str) -> Tuple[float, float]:
    M = molar_mass(formula)
    n = grams / M
    return M, n

def stoich_grams_from_moles(moles: float, formula: str) -> Tuple[float, float]:
    M = molar_mass(formula)
    g = M * moles
    return M, g

# Gas laws
def pv_nrt(p: float = None, v: float = None, n: float = None, T: float = None, R: float = 0.082057) -> Dict[str, float]:
    """
    Solve PV = nRT given exactly three of (p, v, n, T).
    Units must be consistent with R (default R = 0.082057 L·atm·mol⁻¹·K⁻¹).
    """
    known = {'p': p, 'v': v, 'n': n, 'T': T}
    missing = [k for k, vv in known.items() if vv is None]
    if len(missing) != 1:
        raise ValueError("Provide exactly three of p, v, n, T with consistent units.")

    k = missing[0]
    if k == 'p':
        if known['v'] == 0:
            raise ValueError("Volume must be nonzero.")
        known['p'] = (known['n'] * R * known['T']) / known['v']
    elif k == 'v':
        if known['p'] == 0:
            raise ValueError("Pressure must be nonzero.")
        known['v'] = (known['n'] * R * known['T']) / known['p']
    elif k == 'n':
        denom = R * known['T']
        if denom == 0:
            raise ValueError("R * T must be nonzero.")
        known['n'] = (known['p'] * known['v']) / denom
    elif k == 'T':
        denom = R * known['n']
        if denom == 0:
            raise ValueError("R * n must be nonzero.")
        known['T'] = (known['p'] * known['v']) / denom

    return known


def boyle(p1: float, v1: float, p2: Optional[float] = None, v2: Optional[float] = None) -> Dict[str, float]:
    if (p2 is None) == (v2 is None):
        raise ValueError("Provide exactly one of p2 or v2.")
    if p2 is None:
        p2 = (p1 * v1) / v2
    else:
        v2 = (p1 * v1) / p2
    return {"p2": p2, "v2": v2}

def charles(v1: float, T1: float, v2: Optional[float] = None, T2: Optional[float] = None) -> Dict[str, float]:
    if (v2 is None) == (T2 is None):
        raise ValueError("Provide exactly one of v2 or T2 (Kelvin).")
    if v2 is None:
        v2 = v1 * T2 / T1
    else:
        T2 = v2 * T1 / v1
    return {"v2": v2, "T2": T2}

# Concentration
def molarity(moles: float = None, grams: float = None, formula: Optional[str] = None, volume_L: float = None) -> Tuple[float, float]:
    if moles is None:
        if grams is None or not formula:
            raise ValueError("Provide moles, or grams with a formula.")
        M_r = molar_mass(formula)
        moles = grams / M_r
    if volume_L is None or volume_L <= 0:
        raise ValueError("Provide a positive volume in liters.")
    return moles / volume_L, moles

def dilution(M1: float = None, V1_L: float = None, M2: float = None, V2_L: float = None) -> Dict[str, float]:
    known = {'M1': M1, 'V1': V1_L, 'M2': M2, 'V2': V2_L}
    missing = [k for k, v in known.items() if v is None]
    if len(missing) != 1:
        raise ValueError("Provide exactly three of M1,V1,M2,V2 (volumes in L).")
    k = missing[0]
    if k == 'M1': known['M1'] = (known['M2'] * known['V2']) / known['V1']
    if k == 'V1': known['V1'] = (known['M2'] * known['V2']) / known['M1']
    if k == 'M2': known['M2'] = (known['M1'] * known['V1']) / known['V2']
    if k == 'V2': known['V2'] = (known['M1'] * known['V1']) / known['M2']
    return known

# Acid/base (strong, mono-protic)
def ph_strong_acid(M: float) -> float:
    return -math.log10(M)

def poh_strong_base(M: float) -> float:
    return -math.log10(M)

def ph_from_poh(poh: float) -> float:
    return 14.0 - poh

# --- Empirical Formula ---
def empirical_formula_from_composition(comp: Dict[str, float]) -> Dict[str, int]:
    """
    Build an empirical formula from a composition dict:
      comp = {"C": 40.0, "H": 6.7, "O": 53.3}  # percent by mass OR grams (any proportional units)
    Returns a dict of simplest whole-number subscripts, e.g. {"C": 1, "H": 2, "O": 1}.
    """
    _load_dataset_if_needed()
    if not comp:
        raise ValueError("Provide a composition like {'C': 40.0, 'H': 6.7, 'O': 53.3}")

    # Convert masses/percents -> moles
    symbols, mole_vals = [], []
    for el, mass in comp.items():
        key = el.lower()
        e = _BY_SYMBOL.get(key)
        if not e:
            raise ValueError(f"Unknown element symbol '{el}'.")
        aw = float(e.get("atomic_mass", 0.0))
        if aw <= 0:
            raise ValueError(f"No atomic mass for '{el}'.")
        symbols.append(e.get("symbol"))
        mole_vals.append(float(mass) / aw)

    mn = min(mole_vals)
    if mn <= 0:
        raise ValueError("All masses/percents must be positive.")

    ratios = [x / mn for x in mole_vals]

    # Try to clear fractional noise with small multipliers
    def as_int(x: float, tol: float = 1e-3) -> Optional[int]:
        r = round(x)
        return r if abs(x - r) < tol else None

    for k in range(1, 9):  # up to ×8 usually fits common fractions (1/2, 1/3, 2/3, 1/4, 3/4, 5/2, etc.)
        ints = [as_int(r * k) for r in ratios]
        if all(v is not None and v > 0 for v in ints):
            return {symbols[i]: ints[i] for i in range(len(symbols))}

    # Fallback: rounded integers (ensuring >=1)
    ints = [max(1, round(r)) for r in ratios]
    return {symbols[i]: ints[i] for i in range(len(symbols))}


# --- Molality ---
def molality(moles: float = None, grams: float = None, formula: Optional[str] = None,
             solvent_mass_kg: float = None) -> Tuple[float, float]:
    """
    Molality (m) = moles of solute / kg of solvent.
    Supply either moles directly OR (grams, formula) to compute moles.
    Returns (molality_m, moles_solute).
    """
    if solvent_mass_kg is None or solvent_mass_kg <= 0:
        raise ValueError("Provide solvent_mass_kg (>0).")
    if moles is None:
        if grams is None or not formula:
            raise ValueError("Provide moles, or (grams and formula) to compute moles.")
        moles = grams / molar_mass(formula)
    return moles / solvent_mass_kg, moles


# --- Limiting Reagent ---
def limiting_reagent(stoich: Dict[str, float], available_moles: Dict[str, float]) -> Tuple[str, float]:
    """
    Determine the limiting reactant and reaction extent ξ.

    stoich: reactant -> stoichiometric coefficient (ν, positive)
    available_moles: reactant -> available moles (n_i)

    Returns (limiting_reactant_symbol, extent_xi_mol) where
      extent ξ = min_i ( n_i / ν_i ) across provided reactants.
    """
    if not stoich or not available_moles:
        raise ValueError("Provide both stoich and available_moles dicts.")
    ratios: List[Tuple[str, float]] = []
    for r, nu in stoich.items():
        if nu <= 0:
            raise ValueError("Stoichiometric coefficients must be positive.")
        if r not in available_moles:
            raise ValueError(f"Missing available moles for reactant '{r}'.")
        n = available_moles[r]
        if n < 0:
            raise ValueError(f"Negative moles for reactant '{r}'.")
        ratios.append((r, n / nu))
    if not ratios:
        raise ValueError("No reactants to evaluate.")
    limiting, xi = min(ratios, key=lambda t: t[1])
    return limiting, xi


# --- Mixing Molarity ---
def mixing_molarity(C1: float, V1_L: float, C2: float, V2_L: float) -> Dict[str, float]:
    """
    Mix two solutions of the same solute (assume volumes add; no reaction).
    Returns {'Mf': final_molarity, 'Vf_L': final_volume_L}.
    """
    if V1_L < 0 or V2_L < 0:
        raise ValueError("Volumes must be >= 0.")
    moles_total = C1 * V1_L + C2 * V2_L
    Vf = V1_L + V2_L
    if Vf <= 0:
        raise ValueError("Total volume must be > 0.")
    return {"Mf": moles_total / Vf, "Vf_L": Vf}


# --- Convert Molarity Molality ---
def convert_molarity_molality(*, direction: str,
                              M: Optional[float] = None,  # mol/L solution
                              m: Optional[float] = None,  # mol/kg solvent
                              density_g_per_mL: Optional[float] = None,
                              molar_mass_solute_g_per_mol: Optional[float] = None) -> Dict[str, float]:
    """
    Convert between molarity (M) and molality (m). Requires:
      - density_g_per_mL (ρ) of solution
      - molar_mass_solute_g_per_mol (Ms)

    Conventions:
      - For M->m: assume 1 L solution.
          mass_solution_g = ρ * 1000
          mass_solute_g   = M * Ms
          mass_solvent_kg = (mass_solution_g - mass_solute_g) / 1000
          m = M / mass_solvent_kg
      - For m->M: assume 1 kg solvent.
          moles_solute    = m
          mass_solution_g = 1000 + m*Ms
          volume_L        = mass_solution_g / (ρ*1000)
          M = m / volume_L
    """
    ρ = density_g_per_mL
    Ms = molar_mass_solute_g_per_mol
    if not ρ or not Ms or ρ <= 0 or Ms <= 0:
        raise ValueError("Provide positive density_g_per_mL and molar_mass_solute_g_per_mol.")

    d = direction.strip().lower()

    # Molality → Molarity
    if d in ("m_to_molarity", "m->molarity", "m→molarity"):
        if m is None or m < 0:
            raise ValueError("Provide molality 'm' (>=0).")
        mass_solution_g = 1000.0 + m * Ms
        volume_L = mass_solution_g / (ρ * 1000.0)
        return {"M": m / volume_L, "m": m, "density_g_per_mL": ρ}

    # Molarity → Molality
    elif d in ("molarity_to_m", "molarity->m", "molarity→m"):
        if M is None or M < 0:
            raise ValueError("Provide molarity 'M' (>=0).")
        mass_solution_g = ρ * 1000.0
        mass_solute_g = M * Ms
        mass_solvent_kg = (mass_solution_g - mass_solute_g) / 1000.0
        if mass_solvent_kg <= 0:
            raise ValueError("Infeasible parameters: solvent mass <= 0.")
        return {"m": M / mass_solvent_kg, "M": M, "density_g_per_mL": ρ}

    raise ValueError("direction must be one of: 'm_to_molarity' or 'molarity_to_m'")

# -------------------------------
# Intent detection
# -------------------------------
def detect_intent(text: str) -> str:
    t = _safe_lower(text)

    if re.search(r"\blightest\b|\bheaviest\b|\bhighest\b|\blowest\b|\b(most|least)\b", t):
        return "quick_fact"

    if re.search(r"\bpercent(age)?\s+composition\b|\b% composition\b|\bpercent\s+by\s+mass\b|\b% by mass\b", t):
        return "composition"

    if re.search(r"\bmolar\s+mass\b|\bmw\b|\bmr\b", t):
        return "molar_mass"
    if re.search(r"\bmoles?\b.*\bfrom\b.*\bgrams?\b", t) or re.search(r"\bgrams?\b.*\bfrom\b.*\bmoles?\b", t):
        return "stoich"
    if "pv=nrt" in t or re.search(r"\bideal gas\b|\bboyle'?s\b|\bcharles\b", t):
        return "gas_law"
    if re.search(r"\bmolarity\b|\bconcentration\b|\bM\s*=\s*", t):
        return "molarity"
    if re.search(r"\bdilution\b|\bM1V1\s*=\s*M2V2\b", t):
        return "dilution"
    if re.search(r"\bpH\b|\bpOH\b", t):
        return "acid_base"
    
    if re.search(r"\bempirical\s+formula\b|\bmolecular\s+formula\b", t):
        return "empirical_formula"
    if re.search(r"\b(percent|%)\s+composition\b.*\b(empirical|molecular)\b", t):
        return "empirical_formula"
    if re.search(r"\b(by\s+mass|mass\s+percent|% by mass)\b.*\bformula\b", t):
        return "empirical_formula"

    if re.search(r"\bmolality\b|\bmolal\b|\bm\s*=\s*", t):
        return "molality"

    if re.search(r"\blimiting\s+(reagent|reactant)\b|\blimit(?:ing)?\s+reag", t):
        return "limiting_reagent"

    if re.search(r"\bmix(?:ing)?\b.*\bsolutions?\b|\bfinal\s+concentration\b.*\bmix", t):
        return "mixing"

    if re.search(r"\bmolarity\s*(?:↔|to|into)\s*molality\b|\bmolality\s*(?:↔|to|into)\s*molarity\b", t):
        return "molarity_molality"


    if extract_compare_targets(t):
        return "compare"
    if filter_by_category_like(t):
        return "list"
    if extract_range_query(t):
        return "range"
    if normalize_property(t):
        return "property"
    return "overview"

# -------------------------------
# Main handler
# -------------------------------
def handle_chemistry_query(command: str, ctx: Optional[Dict[str, Any]] = None) -> str:
    lazy_imports()
    # opportunistic freshness
    try: _refresh_if_stale(force=False, log=False)
    except Exception: pass
    _load_dataset_if_needed()

    user_text = command.strip()
    # project log (goes to logs/interaction_log.*)
    log_interaction(user_text, "[chemistry] query received", selected_language)

    global CHEM_CTX
    if ctx is None:
        ctx = CHEM_CTX
    ctx["original_text"] = user_text   
    intent = detect_intent(user_text)
    concise = should_use_concise(user_text, intent, ctx)

    # one-shot verbose flag is consumed here (always reset after a call)
    if ctx.get("force_verbose_once"):
        ctx["force_verbose_once"] = False

    # ---- Conceptual friendly fallback (parity with physics; chemistry-specific) ----
    t = user_text.lower()
    has_numbers = bool(re.search(r"\d", user_text))
    # quick cues that it's a calculational/factual chemistry query, not purely conceptual
    has_chem_cues = (
        bool(re.search(
            r"\b(mol|molar|molarity|grams?|g\b|mL|L\b|ph|poh|pv=nrt|boyle|charles|density|boil|melt|electronegativity|"
            r"ionization|electron\s+affinity|atomic\s+mass|atomic\s+number|configuration|period|group|noble|halogen)\b",
            t
        ))
        or (normalize_property(t) is not None)
        or (filter_by_category_like(t) is not None)
    )
    conceptual_cue = bool(re.search(
        r"\b(what|why|how|define|state|explain|difference|list|mean|meaning|concept|law|rule|principle)\b", t
    ))

    if conceptual_cue and not has_numbers and not has_chem_cues:
        # wording tweaked for chemistry context
        _speak_multilang(
            en="I don’t have a quick chemistry fact for that — it sounds conceptual. Try rephrasing or use full chemistry mode for a detailed answer.",
            hi="उसके लिए मेरे पास कोई त्वरित रसायन विज्ञान तथ्य नहीं है — यह वैचारिक लगता है। कृपया इसे फिर से लिखें या विस्तृत उत्तर के लिए full chemistry mode का उपयोग करें।",
            fr="Je n’ai pas de fait rapide en chimie pour cela — cela semble conceptuel. Reformulez ou utilisez le full chemistry mode pour une réponse détaillée.",
            es="No tengo un dato rápido de química para eso — suena conceptual. Intenta reformularlo o usa el full chemistry mode para una respuesta detallada.",
            de="Dazu habe ich keinen schnellen Chemie-Fakt — das klingt konzeptionell. Formuliere bitte um oder nutze den full chemistry mode für eine ausführliche Antwort."
        )
        return "No quick match — try rephrasing or say “use full chemistry mode” for details."

    try:

        # ---------- QUICK FACTS ----------
        if intent == "quick_fact":
            (parsed, phrase) = _parse_quick_fact_query(user_text)
            if not parsed:
                parsed, phrase = ("atomic_mass", "min"), "lightest"
            prop_key, how = parsed
            e = _pick_extreme(prop_key, how)
            if not e:
                if concise:
                    _say_or_show_en("I couldn’t find that in the periodic table.")
                    return "I couldn’t find that in the periodic table."
                # verbose fallback: small GUI message (no actions)
                gui = _format_gui_block(
                    question=user_text,
                    understanding="Quick fact lookup failed.",
                    lines=["No matching element found for that query."],
                    short_answer="No result found.",
                    followups=[],
                )
                _emit_gui(gui, intent="quick_fact", show_more=False, ctx=ctx, action="new")
                return gui

            name = e.get("name")
            label_en = PROP_I18N.get(prop_key, {}).get("en", prop_key)

            # Handle list property value (IE1)
            out_val = e.get(prop_key)
            if prop_key == "ionization_energies":
                arr = ensure_list(out_val); out_val = arr[0] if arr else None

            # Unit mapping for reason text
            unit = (
                "u" if prop_key == "atomic_mass"
                else ("K" if prop_key in ("boil","melt")
                      else ("g/cm³" if prop_key == "density"
                            else ("kJ/mol" if prop_key in ("electron_affinity","ionization_energies")
                                  else "")))
            )

            if concise:
                # ✅ Concise + reason (voice only, no popup)
                qualifier = (
                    "lightest" if (phrase and "lightest" in phrase) else
                    "heaviest" if (phrase and "heaviest" in phrase) else
                    ("highest " + label_en if how == "max" else "lowest " + label_en)
                )
                comp_word = (
                    "smallest" if (how == "min" and prop_key == "atomic_mass") else
                    "largest"  if (how == "max" and prop_key == "atomic_mass") else
                    ("highest" if how == "max" else "lowest")
                )
                value_bit = _fmt_num(out_val)
                unit_part = f" ({value_bit} {unit})" if unit else f" ({value_bit})"
                line = f"{name} is the {qualifier} element because it has the {comp_word} {label_en}{unit_part}."
                _say_or_show_en(line)
                return line

            # 🪟 Verbose GUI (generic facts: no ✦ + no chips)
            short = f"{name} has {('the '+('highest' if how=='max' else 'lowest')+' ') if phrase and 'est' not in phrase else ''}{label_en} ({_fmt_num(out_val)} {unit}).".strip()
            gui = _format_gui_block(
                question=user_text,
                understanding=f"Quick fact on {label_en} ({how}).",
                lines=[f"{label_en}: **{_fmt_num(out_val)} {unit}**", f"Element: **{_short(e)}**"],
                short_answer=short,
                followups=[],  # keep empty so GUI shows no chips
            )
            _emit_gui(gui, intent="quick_fact", show_more=False, ctx=ctx, action="new")
            CHEM_CTX["last_element"] = _mk_element_stub(e)
            CHEM_CTX["last_property"] = prop_key
            return gui


        # ---------- MOLAR MASS ----------
        if intent == "molar_mass":
            # Detect phrasing the user used (for adaptive speech label)
            lt = user_text.lower()
            if re.search(r"\bmolecular\s+weight\b", lt):
                speech_label = "Molecular weight"
            elif re.search(r"\bformula\s+mass\b", lt):
                speech_label = "Formula mass"
            elif re.search(r"\b(?:relative\s+formula\s+mass|mr)\b", lt):
                speech_label = "Relative formula mass"
            else:
                speech_label = "Molar mass"

            # Try to extract a formula after keywords; otherwise grab the last token that looks like a formula
            m = re.search(r"(?:molar\s+mass|molecular\s+weight|formula\s+mass|mr)\s+of\s+([A-Za-z0-9().]+)", lt)
            formula = m.group(1) if m else re.findall(r"[A-Za-z][A-Za-z0-9().]*", user_text)[-1]

            # compute first to use in both concise and detailed
            M_r = molar_mass(formula)

            # Determine if it's a single element (for even nicer speech)
            is_single_element = bool(re.fullmatch(r"[A-Z][a-z]?", formula))

            # ✅ Even in concise mode, show in Solution popup + speak
            if concise:
                en = f"The {speech_label.lower()} of {formula} is {_fmt_num(M_r)} g/mol."
                _say_or_show_en(en)

                gui = _format_gui_block(
                    question=command,
                    understanding=f"You’re asking for the {speech_label.lower()} of the compound {formula}.",
                    lines=[f"{speech_label} = **{_fmt_num(M_r)} g/mol**"],
                    short_answer=en,
                    followups=[
                        f"Percent composition of {formula}",
                        f"Mass of O in 50 g {formula}",
                        f"Compare molar mass with Fe2(SO4)3"
                    ]
                )
                _emit_gui(
                    gui,
                    intent="molar_mass",
                    show_more=_should_show_more(concise, "molar_mass", ctx),  # will be True in concise
                    ctx=ctx,              # carries ctx["original_text"] you added in Step 1
                    action="new"          # first block in the popup thread
                )
                return gui

            # Detailed, self-contained breakdown in the finalized step style
            counts = parse_formula(formula)  # e.g., {'Al': 2, 'S': 3, 'O': 12}
            ordered_items = [(el, counts[el]) for el in sorted(counts.keys())]

            # Build "Al:2, S:3, O:12"
            counts_bits = [f"{el}:{n}" for (el, n) in ordered_items]

            # Atomic weights line (from periodic table)
            aw_bits = []
            per_element_lines = []
            contrib_values = []
            total_u = 0.0
            for (el, n) in ordered_items:
                e = _BY_SYMBOL.get(el.lower()) or {}
                aw = float(e.get("atomic_mass", 0.0))
                contrib = aw * n
                total_u += contrib
                contrib_values.append(contrib)
                aw_bits.append(f"{el} = {_fmt_num(aw)} u")
                per_element_lines.append(f"• {el}: {n} × {_fmt_num(aw)} u = {_fmt_num(contrib)} u")

            lines = [
                f"Formula parsed: {formula} → " + ", ".join(counts_bits),
                "",
                "Atomic weights (from periodic table, u):",
                "• " + " • ".join(aw_bits),
                "",
                "Step 1 — Per-element mass contributions:",
                *per_element_lines,
                "",
                "Step 2 — Total molar mass:",
                "• M_total = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = {_fmt_num(total_u)} u",
                f"(numerically equals {_fmt_num(M_r)} g/mol)",
            ]

            gui = _format_gui_block(
                question=command,
                understanding=f"You’re asking for the {speech_label.lower()} of the compound {formula}.",
                lines=lines,
                short_answer=f"{speech_label} of {formula} = {_fmt_num(M_r)} g/mol",
                followups=[
                    f"Percent composition of {formula}",
                    f"Mass of O in 50 g {formula}",
                    f"Compare molar mass with Fe2(SO4)3"
                ]
            )

            # 🔊 Adaptive speech: pick a friendly target based on the query
            if is_single_element and speech_label == "Molar mass":
                speak_answer(target=f"Atomic mass of {formula}", value=_fmt_num(M_r), unit="g per mole")
            else:
                speak_answer(target=f"{speech_label} of {formula}", value=_fmt_num(M_r), unit="g per mole")

            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui

        

        # ---------- STOICHIOMETRY ----------
        if intent == "stoich":
            grams_match = re.search(r"(\d+\.?\d*)\s*g(?:rams?)?\s+of\s+([A-Za-z0-9().]+)", user_text, re.I)
            moles_match = re.search(r"(\d+\.?\d*)\s*mol(?:es?)?\s+(?:of\s+)?([A-Za-z0-9().]+)", user_text, re.I)

            lines: List[str] = []
            if grams_match:
                # Case A: grams → moles (unknown is n)
                grams = float(grams_match.group(1))
                formula = grams_match.group(2)
                M_r, n = stoich_moles_from_grams(grams, formula)

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"{_fmt_num(grams)} g {formula} is about {_fmt_num(n)} mol."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding=f"Convert mass to moles for {formula}.",
                        lines=[],  # concise => no steps yet
                        short_answer=en,
                        followups=[
                            f"Show steps for {formula}",
                            f"Molar mass of {formula}",
                            f"Percent composition of {formula}",
                        ],
                    )
                    _emit_gui(
                        gui,
                        intent=intent,
                        show_more=True,  # ✦ in concise calc answers
                        ctx=ctx,         # use ctx carrying original_text
                        action="new"     # first block in this popup thread
                    )
                    return gui

                # Step-style verbose
                counts = parse_formula(formula)  # e.g., {'H':2,'S':1,'O':4}
                ordered_items = [(el, counts[el]) for el in sorted(counts.keys())]
                counts_bits = [f"{el}:{n_el}" for (el, n_el) in ordered_items]

                aw_bits = []
                per_element_lines = []
                contrib_values = []
                total_u = 0.0
                for (el, n_el) in ordered_items:
                    e = _BY_SYMBOL.get(el.lower()) or {}
                    aw = float(e.get("atomic_mass", 0.0))
                    contrib = aw * n_el
                    total_u += contrib
                    contrib_values.append(contrib)
                    aw_bits.append(f"{el} = {_fmt_num(aw)} u")
                    per_element_lines.append(f"• {el}: {n_el} × {_fmt_num(aw)} u = {_fmt_num(contrib)} u")

                lines = [
                    f"Givens: m = **{_fmt_num(grams)} g**, substance **{formula}**",
                    "",
                    f"Formula parsed: {formula} → " + ", ".join(counts_bits),
                    "",
                    "Atomic weights (from periodic table, u):",
                    "• " + " • ".join(aw_bits),
                    "",
                    "Step 1 — Derive molar mass (u → g/mol):",
                    *per_element_lines,
                    "",
                    "Step 1 result — Molar mass:",
                    "• M = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = {_fmt_num(total_u)} g/mol",
                    "",
                    "Step 2 — Use the relation:",
                    "• n = m / M",
                    "",
                    "Step 3 — Substitute and compute:",
                    f"• n = {_fmt_num(grams)} g / {_fmt_num(M_r)} g·mol⁻¹ = **{_fmt_num(n)} mol**",
                ]
                short = f"{_fmt_num(grams)} g {formula} ≈ **{_fmt_num(n)} mol**."

                # 🔊 adaptive speech: focuses on unknown (moles)
                speak_answer(target=f"Moles of {formula}", value=_fmt_num(n), unit="mol")

            elif moles_match:
                # Case B: moles → grams (unknown is mass)
                moles = float(moles_match.group(1))
                formula = moles_match.group(2)
                M_r, g = stoich_grams_from_moles(moles, formula)

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"{_fmt_num(moles)} mol {formula} is about {_fmt_num(g)} g."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding=f"Convert moles to mass for {formula}.",
                        lines=[],  # concise => no steps yet
                        short_answer=en,
                        followups=[
                            f"Show steps for {formula}",
                            f"Molar mass of {formula}",
                            f"Percent composition of {formula}",
                        ],
                    )
                    _emit_gui(
                        gui,
                        intent=intent,
                        show_more=True,  # ✦ in concise calc answers
                        ctx=ctx,         # use ctx carrying original_text
                        action="new"     # first block in this popup thread
                    )
                    return gui

                # Step-style verbose
                counts = parse_formula(formula)
                ordered_items = [(el, counts[el]) for el in sorted(counts.keys())]
                counts_bits = [f"{el}:{n_el}" for (el, n_el) in ordered_items]

                aw_bits = []
                per_element_lines = []
                contrib_values = []
                total_u = 0.0
                for (el, n_el) in ordered_items:
                    e = _BY_SYMBOL.get(el.lower()) or {}
                    aw = float(e.get("atomic_mass", 0.0))
                    contrib = aw * n_el
                    total_u += contrib
                    contrib_values.append(contrib)
                    aw_bits.append(f"{el} = {_fmt_num(aw)} u")
                    per_element_lines.append(f"• {el}: {n_el} × {_fmt_num(aw)} u = {_fmt_num(contrib)} u")

                lines = [
                    f"Givens: n = **{_fmt_num(moles)} mol**, substance **{formula}**",
                    "",
                    f"Formula parsed: {formula} → " + ", ".join(counts_bits),
                    "",
                    "Atomic weights (from periodic table, u):",
                    "• " + " • ".join(aw_bits),
                    "",
                    "Step 1 — Derive molar mass (u → g/mol):",
                    *per_element_lines,
                    "",
                    "Step 1 result — Molar mass:",
                    "• M = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = {_fmt_num(total_u)} g/mol",
                    "",
                    "Step 2 — Use the relation:",
                    "• m = n × M",
                    "",
                    "Step 3 — Substitute and compute:",
                    f"• m = {_fmt_num(moles)} mol × {_fmt_num(M_r)} g·mol⁻¹ = **{_fmt_num(g)} g**",
                ]
                short = f"{_fmt_num(moles)} mol {formula} ≈ **{_fmt_num(g)} g**."

                # 🔊 adaptive speech: focuses on unknown (mass)
                speak_answer(target=f"Mass of {formula}", value=_fmt_num(g), unit="g")

            else:
                raise ValueError("Please specify either grams of a compound or moles of a compound.")

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking a stoichiometry conversion between mass and moles.",
                lines=lines,
                short_answer=short,
                followups=[
                    f"Show steps for {formula}",            # handy even after verbose; router can ignore if already expanded
                    "What’s the molarity from moles and volume?",
                    "Do a dilution with M1V1 = M2V2",
                    "Balance a chemical equation",
                ],
            )
            _emit_gui(
                gui,
                intent=intent,
                show_more=_should_show_more(concise, intent, ctx),
                ctx=ctx,
                action="new"
            )
            return gui



        # ---------- GAS LAWS ----------
        if intent == "gas_law":
            t = user_text.lower()
            lines, short = [], ""

            # ========= local helpers =========
            def _norm_temp_unit(u):
                if not u: return None
                return (
                    u.strip()
                     .lower()
                     .replace("°", "")
                     .replace("k ", "k")
                     .replace("c ", "c")
                     .replace("f ", "f")
                )

            def _count_sig_figs(num_str: str) -> int:
                s = (num_str or "").strip().lower().replace("+", "")
                if "e" in s:
                    s = s.split("e", 1)[0]
                s = s.replace(",", "")
                if s.startswith("-"): s = s[1:]
                if "." in s:
                    s = s.strip("0")
                    if s in {"", "."}: return 1
                    return max(1, sum(ch.isdigit() for ch in s))
                s = s.lstrip("0")
                return max(1, len(s)) if s else 1

            def _fewest_sig_figs(tokens, lo=2, hi=6):
                toks = [x for x in tokens if x]
                if not toks: return 3
                return max(lo, min(hi, min(_count_sig_figs(x) for x in toks)))

            def _fmt_sig(x, sig):
                if x is None: return "—"
                try: return f"{float(x):.{sig}g}"
                except: return str(x)

            # pressure + volume units
            P_UNITS = {"atm", "pa", "kpa", "bar", "torr", "mmhg"}
            V_UNITS = {"l", "ml", "m3", "m^3"}

            def _norm_p_unit(u):
                if not u: return None
                u = u.strip().lower()
                return "torr" if u == "mmhg" else (u if u in P_UNITS else None)

            def _norm_v_unit(u):
                if not u: return None
                u = u.strip().lower().replace("ℓ", "l")
                if u in {"m^3", "m3"}: return "m3"
                return u if u in V_UNITS else None

            # labels for speech
            def _label_p(u):  # pressure
                return {"atm": "atm", "kpa": "kPa", "pa": "Pa", "bar": "bar", "torr": "torr"}.get(u, u or "")

            def _label_v(u):  # volume
                return {"l": "L", "m3": "m³", "ml": "mL"}.get(u, u or "")

            # central conversion logs we’ll show in GUI
            conversion_log = []

            def _to_kelvin_verbose(val: float, unit: str):
                """Convert C/F/K -> K; also record factor-label line(s)."""
                u = _norm_temp_unit(unit) or "k"
                if u == "k":
                    conversion_log.append(f"T already in K: T = {val}")
                    return float(val)
                if u == "c":
                    K = float(val) + 273.15
                    conversion_log.append(f"T(K) = T(°C) + 273.15 = {val} + 273.15 = {K}")
                    return K
                if u == "f":
                    K = (float(val) - 32.0) * (5/9) + 273.15
                    conversion_log.append(f"T(K) = (T(°F) − 32) × 5/9 + 273.15 = ({val} − 32) × 5/9 + 273.15 = {K}")
                    return K
                conversion_log.append(f"T assumed K: T = {val}")
                return float(val)

            # P↔Pa hub; V↔m3 hub
            def _p_to(unit_to: str, p_val: float, p_unit: str) -> float:
                if p_unit == unit_to: return p_val
                to_pa = {"pa": 1.0, "kpa": 1000.0, "bar": 1e5, "atm": 101325.0, "torr": 133.322368}[p_unit]
                pa = p_val * to_pa
                from_pa = {"pa": 1.0, "kpa": 1/1000.0, "bar": 1e-5, "atm": 1/101325.0, "torr": 1/133.322368}[unit_to]
                converted = pa * from_pa
                conversion_log.append(f"P: {p_val} {p_unit} → {converted} {unit_to}")
                return converted

            def _v_to(unit_to: str, v_val: float, v_unit: str) -> float:
                if v_unit == unit_to: return v_val
                to_m3 = {"m3": 1.0, "l": 1e-3, "ml": 1e-6}[v_unit]
                m3 = v_val * to_m3
                from_m3 = {"m3": 1.0, "l": 1000.0, "ml": 1e6}[unit_to]
                converted = m3 * from_m3
                conversion_log.append(f"V: {v_val} {v_unit} → {converted} {unit_to}")
                return converted

            def _choose_R(p_unit: str, v_unit: str):
                # return (R numeric, label, p_unit_final, v_unit_final)
                if p_unit == "pa" and v_unit == "m3":   return (8.314462618, "Pa·m³·mol⁻¹·K⁻¹", "pa", "m3")
                if p_unit == "kpa" and v_unit == "l":   return (8.314462618, "kPa·L·mol⁻¹·K⁻¹", "kpa", "l")
                if p_unit == "bar" and v_unit == "l":   return (0.08314462618, "bar·L·mol⁻¹·K⁻¹", "bar", "l")
                if p_unit == "torr" and v_unit == "l":  return (62.36367, "torr·L·mol⁻¹·K⁻¹", "torr", "l")
                return (0.082057, "L·atm·mol⁻¹·K⁻¹", "atm", "l")  # default

            # ====== BOYLE ======
            if "boyle" in t:
                pairs = re.findall(r"(p1|v1|p2|v2)\s*=\s*([-\d.]+)\s*([a-z°^3]+)?", t, re.I)
                raw = {}
                for k, v, u in pairs:
                    raw.setdefault(k.lower(), (v, u))

                sig = _fewest_sig_figs([v for (v, _u) in raw.values()])

                kvp, kvv = {}, {}
                for k, (val, u) in raw.items():
                    if k.startswith("p"):
                        pu = _norm_p_unit(u) or "atm"
                        pv = float(val);  assert pv > 0, "Pressure must be > 0."
                        kvp[k] = (pv, pu)
                    else:
                        vu = _norm_v_unit(u) or "l"
                        vv = float(val);  assert vv > 0, "Volume must be > 0."
                        kvv[k] = (vv, vu)

                if ("p1" not in kvp) or ("v1" not in kvv) or (("p2" in kvp) and ("v2" in kvv)) or (("p2" not in kvp) and ("v2" not in kvv)):
                    raise ValueError("For Boyle’s law, provide P1, V1, and exactly one of P2 or V2 (with units).")

                base_pu = kvp["p1"][1]
                base_vu = kvv["v1"][1]
                R_val, R_lab, base_pu, base_vu = _choose_R(base_pu, base_vu)

                p1 = _p_to(base_pu, kvp["p1"][0], kvp["p1"][1])
                v1 = _v_to(base_vu, kvv["v1"][0], kvv["v1"][1])
                p2 = _p_to(base_pu, kvp["p2"][0], kvp["p2"][1]) if "p2" in kvp else None
                v2 = _v_to(base_vu, kvv["v2"][0], kvv["v2"][1]) if "v2" in kvv else None

                res = boyle(p1, v1, p2, v2)

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"Boyle: P2={_fmt_sig(res['p2'], sig)} {base_pu}, V2={_fmt_sig(res['v2'], sig)} {base_vu}."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Boyle’s law (P₁V₁ = P₂V₂).",
                        lines=[],  # concise => no steps yet
                        short_answer=en,
                        followups=[
                            "Show steps (Boyle’s law)",
                            "Do a Charles’ law example",
                            "Try a PV=nRT with three knowns",
                        ],
                    )
                    _emit_gui(gui, intent=intent, show_more=True, ctx=ctx, action="new")
                    return gui

                unknown = "p2" if p2 is None else "v2"
                rearr = "P₂ = (P₁·V₁)/V₂" if unknown == "p2" else "V₂ = (P₁·V₁)/P₂"

                unit_block = ["Unit conversions (factor-label):"] + [f"• {s}" for s in conversion_log] if conversion_log else []
                givens = f"P₁={_fmt_sig(p1, sig)} {base_pu}, V₁={_fmt_sig(v1, sig)} {base_vu}" + \
                         (f", P₂={_fmt_sig(p2, sig)} {base_pu}" if p2 is not None else "") + \
                         (f", V₂={_fmt_sig(v2, sig)} {base_vu}" if v2 is not None else "")

                lines = [
                    "Step 1 — State the law & givens:",
                    "• Law: **P₁V₁ = P₂V₂** (T constant)",
                    "• " + givens,
                    *unit_block, "",
                    "Step 2 — Rearrange for the unknown:",
                    f"• {rearr}", "",
                    "Step 3 — Substitute and compute:",
                    "• " + rearr.replace("P₁", _fmt_sig(p1, sig)).replace("V₁", _fmt_sig(v1, sig)) \
                                .replace("P₂", _fmt_sig(p2 or 0, sig)).replace("V₂", _fmt_sig(v2 or 0, sig)),
                    "", "Result:",
                    f"• **P₂={_fmt_sig(res['p2'], sig)} {base_pu}**, **V₂={_fmt_sig(res['v2'], sig)} {base_vu}**",
                ]
                short = f"Boyle: P₂={_fmt_sig(res['p2'], sig)} {base_pu}, V₂={_fmt_sig(res['v2'], sig)} {base_vu}."

                # 🔊 adaptive speech
                if unknown == "p2":
                    speak_answer(target="Final pressure", value=_fmt_sig(res['p2'], sig), unit=_label_p(base_pu))
                else:
                    speak_answer(target="Final volume", value=_fmt_sig(res['v2'], sig), unit=_label_v(base_vu))

            # ====== CHARLES ======
            elif "charles" in t:
                pairs = re.findall(r"(v1|t1|v2|t2)\s*=\s*([-\d.]+)\s*([a-z°^3]+)?", t, re.I)
                raw = {}
                for k, v, u in pairs:
                    raw.setdefault(k.lower(), (v, u))

                sig = _fewest_sig_figs([v for (v, _u) in raw.values()])
                kv = {}

                # volumes
                for k, (val, unit) in raw.items():
                    if k.startswith("v"):
                        vu = _norm_v_unit(unit) or "l"
                        vv = float(val);  assert vv > 0, "Volume must be > 0."
                        kv.setdefault("_vunit", vu if "v1" not in kv else kv["_vunit"])
                        base_vu = kv["_vunit"]
                        kv[k] = _v_to(base_vu, vv, vu)

                # temperatures (with explicit conversion log)
                for k, (val, unit) in raw.items():
                    if k.startswith("t"):
                        TK = _to_kelvin_verbose(float(val), unit)
                        assert TK > 0, "Temperature in Kelvin must be > 0."
                        kv[k] = TK

                if (("v1" not in kv) or ("t1" not in kv)) or (("v2" in kv) and ("t2" in kv)) or (("v2" not in kv) and ("t2" not in kv)):
                    raise ValueError("For Charles’ law, provide V1, T1, and exactly one of V2 or T2 (T may be in C/F/K).")

                res = charles(kv.get("v1"), kv.get("t1"), kv.get("v2"), kv.get("t2"))

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"Charles: V2={_fmt_sig(res['v2'], sig)} {kv['_vunit']}, T2={_fmt_sig(res['T2'], sig)} K."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Charles’ law (V₁/T₁ = V₂/T₂).",
                        lines=[],  # concise => no steps yet
                        short_answer=en,
                        followups=[
                            "Show steps (Charles’ law)",
                            "Do a Boyle’s law example",
                            "Try a PV=nRT with three knowns",
                        ],
                    )
                    _emit_gui(gui, intent=intent, show_more=True, ctx=ctx, action="new")
                    return gui

                unit_block = ["Unit conversions (factor-label):"] + [f"• {s}" for s in conversion_log] if conversion_log else []
                unknown = "v2" if "v2" not in raw else "t2"
                rearr = "V₂ = V₁·T₂/T₁" if unknown == "v2" else "T₂ = V₂·T₁/V₁"

                lines = [
                    "Step 1 — State the law & givens:",
                    "• Law: **V₁/T₁ = V₂/T₂** (P constant; T in Kelvin)",
                    f"• V₁={_fmt_sig(kv.get('v1'), sig)} {kv['_vunit']}, T₁={_fmt_sig(kv.get('t1'), sig)} K" +
                    (f", V₂={_fmt_sig(kv.get('v2'), sig)} {kv['_vunit']}" if kv.get('v2') is not None else "") +
                    (f", T₂={_fmt_sig(kv.get('t2'), sig)} K" if kv.get('t2') is not None else ""),
                    *unit_block, "",
                    "Step 2 — Rearrange for the unknown:",
                    f"• {rearr}", "",
                    "Step 3 — Substitute and compute:",
                    "• " + rearr.replace("V₁", _fmt_sig(kv.get('v1'), sig)) \
                                .replace("T₁", _fmt_sig(kv.get('t1'), sig)) \
                                .replace("V₂", _fmt_sig(res['v2'], sig)) \
                                .replace("T₂", _fmt_sig(res['T2'], sig)),
                    "", "Result:",
                    f"• **V₂={_fmt_sig(res['v2'], sig)} {kv['_vunit']}**, **T₂={_fmt_sig(res['T2'], sig)} K**",
                ]
                short = f"Charles: V₂={_fmt_sig(res['v2'], sig)} {kv['_vunit']}, T₂={_fmt_sig(res['T2'], sig)} K."

                # 🔊 adaptive speech
                if unknown == "v2":
                    speak_answer(target="Final volume", value=_fmt_sig(res['v2'], sig), unit=_label_v(kv["_vunit"]))
                else:
                    speak_answer(target="Final temperature", value=_fmt_sig(res['T2'], sig), unit="K")

            # ====== PV = nRT (auto units + explicit conversion math) ======
            else:
                pairs = re.findall(r"\b([pvnt])\s*=\s*([-\d.]+)\s*([a-z°^3]+)?", t, re.I)
                raw = {}
                for k, v, u in pairs:
                    raw.setdefault(k.lower(), (v, u))

                sig = _fewest_sig_figs([v for (v, _u) in raw.values()])

                # parse + units
                p = v = n = T = None
                p_u = v_u = None

                if "p" in raw:
                    val, u = raw["p"]; p_u = _norm_p_unit(u) or "atm"
                    p = float(val);  assert p > 0, "Pressure must be > 0."
                if "v" in raw:
                    val, u = raw["v"]; v_u = _norm_v_unit(u) or "l"
                    v = float(val);  assert v > 0, "Volume must be > 0."
                if "n" in raw:
                    val, _ = raw["n"]; n = float(val);  assert n > 0, "Amount (n) must be > 0."
                if "t" in raw:
                    val, u = raw["t"]; T = _to_kelvin_verbose(float(val), u);  assert T > 0, "Temperature in Kelvin must be > 0."

                provided = [x for x in [p, v, n, T] if x is not None]
                if len(provided) != 3:
                    raise ValueError("Provide exactly three of p, v, n, T. Units allowed: atm/Pa/kPa/bar/torr and L/mL/m³; T in C/F/K.")

                # choose family + R
                base_pu = p_u or "atm"
                base_vu = v_u or "l"
                if base_pu == "pa" and base_vu != "m3": base_vu = "m3"
                if base_pu in {"atm", "kpa", "bar", "torr"} and base_vu == "m3": base_vu = "l"
                R_val, R_lab, base_pu, base_vu = _choose_R(base_pu, base_vu)

                # convert to base units (with logged steps)
                if (p is not None) and (p_u is not None): p = _p_to(base_pu, p, p_u)
                if (v is not None) and (v_u is not None): v = _v_to(base_vu, v, v_u)

                # solve
                res = pv_nrt(p=p, v=v, n=n, T=T)

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"PV=nRT: p={_fmt_sig(res['p'], sig)} {base_pu}, v={_fmt_sig(res['v'], sig)} {base_vu}, n={_fmt_sig(res['n'], sig)} mol, T={_fmt_sig(res['T'], sig)} K (R={R_val} {R_lab})."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Ideal gas law (PV = nRT).",
                        lines=[],  # concise => no steps yet
                        short_answer=en,
                        followups=[
                            "Show steps (PV=nRT)",
                            "Do a Boyle’s law example",
                            "Do a Charles’ law example",
                        ],
                    )
                    _emit_gui(gui, intent=intent, show_more=True, ctx=ctx, action="new")
                    return gui

                unit_block = ["Unit conversions (factor-label):"] + [f"• {s}" for s in conversion_log] if conversion_log else []
                givens_bits = []
                if p is not None:    givens_bits.append(f"p={_fmt_sig(p, sig)} {base_pu}")
                if v is not None:    givens_bits.append(f"v={_fmt_sig(v, sig)} {base_vu}")
                if n is not None:    givens_bits.append(f"n={_fmt_sig(n, sig)} mol")
                if T is not None:    givens_bits.append(f"T={_fmt_sig(T, sig)} K")
                givens = ", ".join(givens_bits) + f" (R={R_val} {R_lab})"

                missing = "p" if p is None else ("v" if v is None else ("n" if n is None else "T"))
                rearr = {
                    "p": "p = n·R·T / v",
                    "v": "v = n·R·T / p",
                    "n": "n = p·v / (R·T)",
                    "T": "T = p·v / (R·n)",
                }[missing]
                sub = rearr.replace("n", _fmt_sig(res['n'], sig)).replace("R", str(R_val)).replace("T", _fmt_sig(res['T'], sig)) \
                           .replace("p", _fmt_sig(res['p'], sig)).replace("v", _fmt_sig(res['v'], sig))

                lines = [
                    "Step 1 — State the law & givens:",
                    "• Law: **PV = nRT**",
                    "• Givens (normalized): " + givens,
                    *unit_block, "",
                    "Step 2 — Rearrange for the unknown:",
                    f"• {rearr}", "",
                    "Step 3 — Substitute and compute:",
                    f"• {sub}", "",
                    "Result:",
                    f"• p={_fmt_sig(res['p'], sig)} {base_pu}, v={_fmt_sig(res['v'], sig)} {base_vu}, n={_fmt_sig(res['n'], sig)} mol, T={_fmt_sig(res['T'], sig)} K",
                ]
                short = f"PV=nRT solved: p={_fmt_sig(res['p'], sig)} {base_pu}, v={_fmt_sig(res['v'], sig)} {base_vu}, n={_fmt_sig(res['n'], sig)} mol, T={_fmt_sig(res['T'], sig)} K."

                # 🔊 adaptive speech (only the unknown, in its unit)
                if missing == "n":
                    speak_answer(target="Amount of gas", value=_fmt_sig(res['n'], sig), unit="mol")
                elif missing == "p":
                    speak_answer(target="Pressure", value=_fmt_sig(res['p'], sig), unit=_label_p(base_pu))
                elif missing == "v":
                    speak_answer(target="Volume", value=_fmt_sig(res['v'], sig), unit=_label_v(base_vu))
                else:  # missing == "T"
                    speak_answer(target="Temperature", value=_fmt_sig(res['T'], sig), unit="K")

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking a gas law calculation.",
                lines=lines,
                short_answer=short,
                followups=["Try a PV=nRT with three knowns", "Do a Boyle’s law example", "What pressure if no leak?"]
            )
            _emit_gui(
                gui,
                intent=intent,
                show_more=_should_show_more(concise, intent, ctx),
                ctx=ctx,
                action="new"
            )
            return gui



        # ---------- MOLARITY ----------
        if intent == "molarity":
            lt = user_text.lower()

            # Parse solute amount
            grams_match = re.search(r"(\d+\.?\d*)\s*g(?:rams?)?\s+([A-Za-z0-9().]+)", user_text, re.I)
            moles_match = re.search(r"\bn\s*=\s*([-\d.]+)", lt)
            # Optional % w/v like "5% w/v NaCl" or "5 % w/v of NaCl"
            wv_match = re.search(r"(\d+\.?\d*)\s*%\s*w\s*/?\s*v(?:\s+of)?\s+([A-Za-z0-9().]+)", lt, re.I)

            # Parse volume with units (show every conversion explicitly)
            conversion_log = []
            vol_L = None
            vol_val, vol_unit = None, None

            mL = re.search(r"(\d+\.?\d*)\s*mL\b", user_text, re.I)
            Lq = re.search(r"(\d+\.?\d*)\s*L\b", user_text, re.I)
            m3 = re.search(r"(\d+\.?\d*)\s*m\^?3\b", user_text, re.I)

            if Lq:
                vol_val, vol_unit = float(Lq.group(1)), "L"
                vol_L = vol_val
                conversion_log.append(f"V already in L: V = {_fmt_num(vol_L)} L")
            elif mL:
                vol_val, vol_unit = float(mL.group(1)), "mL"
                vol_L = vol_val / 1000.0
                conversion_log.append(f"V: {_fmt_num(vol_val)} mL × (1 L / 1000 mL) = **{_fmt_num(vol_L)} L**")
            elif m3:
                vol_val, vol_unit = float(m3.group(1)), "m³"
                vol_L = vol_val * 1000.0
                conversion_log.append(f"V: {_fmt_num(vol_val)} m³ × (1000 L / 1 m³) = **{_fmt_num(vol_L)} L**")

            if vol_L is None:
                raise ValueError("Please specify volume with units (mL, L, or m³).")

            lines, short = [], ""

            # ===== Case A: grams + formula → M =====
            if grams_match:
                grams = float(grams_match.group(1))
                formula = grams_match.group(2)

                M, n_used = molarity(moles=None, grams=grams, formula=formula, volume_L=vol_L)

                if concise:
                    en = f"Molarity is about {_fmt_num(M)} mol/L."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Molarity (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Do a dilution", "Mass needed for target M", "Convert to molality"]
                    )
                    _emit_gui(gui, intent="molarity", show_more=True, ctx=ctx, action="new")
                    return gui

                # Derive molar mass for GUI (explicit, step-style)
                counts = parse_formula(formula)
                ordered = [(el, counts[el]) for el in sorted(counts.keys())]
                aw_bits, per_terms, contrib_values, total_u = [], [], [], 0.0
                for el, cnt in ordered:
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    contrib = aw * cnt
                    total_u += contrib
                    contrib_values.append(contrib)
                    aw_bits.append(f"{el} = {_fmt_num(aw)} u")
                    per_terms.append(f"• {el}: {cnt} × {_fmt_num(aw)} u = {_fmt_num(contrib)} u")

                unit_block = ["Unit conversions:"] + [f"• {s}" for s in conversion_log] if conversion_log else []

                lines = [
                    f"Givens: m = **{_fmt_num(grams)} g** of **{formula}**, V = **{_fmt_num(vol_val)} {vol_unit}**",
                    *unit_block, "",
                    "Molar mass derivation (u → g/mol):",
                    "• " + " • ".join(aw_bits),
                    *per_terms,
                    "• Total M = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = **{_fmt_num(total_u)} g/mol**",
                    "",
                    "Equation:",
                    "• **M = n / V**  with  **n = m / M**",
                    "",
                    "Step 1 — Find moles of solute:",
                    f"• n = {_fmt_num(grams)} g ÷ {_fmt_num(total_u)} g·mol⁻¹ = **{_fmt_num(n_used)} mol**",
                    "",
                    "Step 2 — Compute molarity:",
                    f"• M = {_fmt_num(n_used)} mol ÷ {_fmt_num(vol_L)} L = **{_fmt_num(M)} mol/L**",
                ]
                short = f"Molarity ≈ **{_fmt_num(M)} M**."
                speak_answer(target="Molarity", value=_fmt_num(M), unit="mol per liter")

            # ===== Case B: moles given → M =====
            elif moles_match:
                n_val = float(moles_match.group(1))
                M, _ = molarity(moles=n_val, volume_L=vol_L)

                if concise:
                    en = f"Molarity is about {_fmt_num(M)} mol/L."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Molarity (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Do a dilution", "Mass needed for target M", "Convert to molality"]
                    )
                    _emit_gui(gui, intent="molarity", show_more=True, ctx=ctx, action="new")
                    return gui

                unit_block = ["Unit conversions:"] + [f"• {s}" for s in conversion_log] if conversion_log else []

                lines = [
                    f"Givens: n = **{_fmt_num(n_val)} mol**, V = **{_fmt_num(vol_val)} {vol_unit}**",
                    *unit_block, "",
                    "Equation:",
                    "• **M = n / V**",
                    "",
                    "Substitution:",
                    f"• M = {_fmt_num(n_val)} mol ÷ {_fmt_num(vol_L)} L = **{_fmt_num(M)} mol/L**",
                ]
                short = f"Molarity ≈ **{_fmt_num(M)} M**."
                speak_answer(target="Molarity", value=_fmt_num(M), unit="mol per liter")

            # ===== Case C: % w/v + formula + volume → M (explicit grams-from-% step) =====
            elif wv_match:
                pct = float(wv_match.group(1))
                formula = wv_match.group(2)

                if vol_val is None or vol_unit is None:
                    raise ValueError("For % w/v, please include a volume (mL, L, or m³).")

                # Convert volume to mL explicitly (show factor-label)
                if vol_unit == "mL":
                    V_mL = vol_val
                    conversion_log.append(f"V in mL already: V = {_fmt_num(V_mL)} mL")
                elif vol_unit == "L":
                    V_mL = vol_val * 1000.0
                    conversion_log.append(f"V: {_fmt_num(vol_val)} L × (1000 mL / 1 L) = **{_fmt_num(V_mL)} mL**")
                else:  # m³
                    V_mL = vol_val * 1_000_000.0
                    conversion_log.append(f"V: {_fmt_num(vol_val)} m³ × (10⁶ mL / 1 m³) = **{_fmt_num(V_mL)} mL**")

                # Grams from % w/v (g per 100 mL)
                grams = pct * V_mL / 100.0
                conversion_log.append(f"m from %w/v: {pct} g / 100 mL × {_fmt_num(V_mL)} mL = **{_fmt_num(grams)} g**")

                # Now proceed like Case A, but show all steps
                M_r = molar_mass(formula)
                n_used = grams / M_r
                M = n_used / vol_L

                if concise:
                    en = f"Molarity is about {_fmt_num(M)} mol/L."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Molarity (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Do a dilution", "Mass needed for target M", "Convert to molality"]
                    )
                    _emit_gui(gui, intent="molarity", show_more=True, ctx=ctx, action="new")
                    return gui

                counts = parse_formula(formula)
                ordered = [(el, counts[el]) for el in sorted(counts.keys())]
                aw_bits, per_terms, contrib_values, total_u = [], [], [], 0.0
                for el, cnt in ordered:
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    contrib = aw * cnt
                    total_u += contrib
                    contrib_values.append(contrib)
                    aw_bits.append(f"{el} = {_fmt_num(aw)} u")
                    per_terms.append(f"• {el}: {cnt} × {_fmt_num(aw)} u = {_fmt_num(contrib)} u")

                unit_block = ["Unit conversions:"] + [f"• {s}" for s in conversion_log] if conversion_log else []

                lines = [
                    f"Givens: c = **{_fmt_num(pct)}% w/v** of **{formula}**, V = **{_fmt_num(vol_val)} {vol_unit}**",
                    *unit_block, "",
                    "Molar mass derivation (u → g/mol):",
                    "• " + " • ".join(aw_bits),
                    *per_terms,
                    f"• Total M = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = **{_fmt_num(total_u)} g/mol**",
                    "",
                    "Equations:",
                    "• **m (g) = (% w/v) × V(mL) / 100**",
                    "• **n = m / M**,   **Molarity = n / V(L)**",
                    "",
                    "Step 1 — Grams from % w/v:",
                    f"• m = {pct} g/100 mL × {_fmt_num(V_mL)} mL = **{_fmt_num(grams)} g**",
                    "",
                    "Step 2 — Moles of solute:",
                    f"• n = {_fmt_num(grams)} g ÷ {_fmt_num(total_u)} g·mol⁻¹ = **{_fmt_num(n_used)} mol**",
                    "",
                    "Step 3 — Molarity:",
                    f"• M = {_fmt_num(n_used)} mol ÷ {_fmt_num(vol_L)} L = **{_fmt_num(M)} mol/L**",
                ]
                short = f"Molarity ≈ **{_fmt_num(M)} M**."
                speak_answer(target="Molarity", value=_fmt_num(M), unit="mol per liter")

            else:
                raise ValueError("Provide moles (n=...), or grams + formula, or % w/v + formula.")

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking a solution concentration (molarity).",
                lines=lines,
                short_answer=short,
                followups=[
                    "Now do a dilution (M1V1 = M2V2)",
                    "Mass needed for 1 L of 0.50 M NaCl?",
                    "How many moles in 250 mL of 0.20 M?"
                ]
            )
            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui

        

        # ---------- MOLALITY ----------
        if intent == "molality":
            lt = user_text.lower()

            # Recognize inputs
            # Solute amount: either grams + formula, or moles (n=...)
            grams_match = re.search(r"(\d+\.?\d*)\s*g(?:rams?)?\s+([A-Za-z0-9().]+)", user_text, re.I)
            moles_match = re.search(r"\bn\s*=\s*([-\d.]+)", lt)

            # Solvent mass (required): accept "solvent = 750 g" / "solvent 0.250 kg" / "750 g solvent"
            solv1 = re.search(r"solvent\s*[:=]?\s*([-\d.]+)\s*(kg|g)\b", lt)  # solvent = 200 g
            solv2 = re.search(r"([-\d.]+)\s*(kg|g)\s+solvent\b", lt)          # 200 g solvent

            # Optional: % w/w case — needs total solution mass
            wwm = re.search(r"([-\d.]+)\s*%\s*w\s*/\s*w\s+(?:of\s+)?([A-Za-z0-9().]+)", lt, re.I)
            total_mass = None
            # total mass patterns: "total mass = 2.0 kg", "500 g solution", "2 kg total"
            tot1 = re.search(r"total\s*mass\s*[:=]?\s*([-\d.]+)\s*(kg|g)\b", lt)
            tot2 = re.search(r"([-\d.]+)\s*(kg|g)\s*(?:solution|total)\b", lt, re.I)

            # Build solvent mass (kg) with explicit "Unit conversions:" lines
            conversions = []
            m_solvent_kg = None
            if solv1:
                val, u = float(solv1.group(1)), solv1.group(2).lower()
                if u == "kg":
                    m_solvent_kg = val
                    conversions.append(f"Solvent mass already in kg: **{_fmt_num(m_solvent_kg)} kg**")
                else:
                    m_solvent_kg = val / 1000.0
                    conversions.append(f"Solvent mass: {_fmt_num(val)} g → **{_fmt_num(m_solvent_kg)} kg**")
            elif solv2:
                val, u = float(solv2.group(1)), solv2.group(2).lower()
                if u == "kg":
                    m_solvent_kg = val
                    conversions.append(f"Solvent mass already in kg: **{_fmt_num(m_solvent_kg)} kg**")
                else:
                    m_solvent_kg = val / 1000.0
                    conversions.append(f"Solvent mass: {_fmt_num(val)} g → **{_fmt_num(m_solvent_kg)} kg**")

            # Helper: derive molar mass breakdown text (like your other chem steps)
            def _molar_mass_block(formula: str):
                counts = parse_formula(formula)
                ordered = [(el, counts[el]) for el in sorted(counts.keys())]
                aw_bits, per_terms, contrib_values, total_u = [], [], [], 0.0
                for el, cnt in ordered:
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    contrib = aw * cnt
                    total_u += contrib
                    contrib_values.append(contrib)
                    aw_bits.append(f"{el} = {_fmt_num(aw)} u")
                    per_terms.append(f"• {el}: {cnt} × {_fmt_num(aw)} u = {_fmt_num(contrib)} u")
                return ordered, aw_bits, per_terms, contrib_values, total_u

            lines, short = [], ""

            # ===== Case A: grams of solute + formula + solvent mass → molality (m) =====
            if grams_match and m_solvent_kg is not None:
                grams = float(grams_match.group(1))
                formula = grams_match.group(2)

                ordered, aw_bits, per_terms, contrib_values, M_r = _molar_mass_block(formula)
                n_solute = grams / M_r
                m_molality = n_solute / m_solvent_kg  # mol/kg

                if concise:
                    en = f"Molality is about {_fmt_num(m_molality)} mol/kg."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Molality (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Convert to molarity", "Mass of solute for given m", "Find mole fraction"]
                    )
                    _emit_gui(gui, intent="molality", show_more=True, ctx=ctx, action="new")
                    return gui

                # GUI
                lines = [
                    f"Givens: m_solute = **{_fmt_num(grams)} g** of **{formula}**, m_solvent = **{_fmt_num(m_solvent_kg)} kg**",
                ]
                if conversions:
                    lines += ["Unit conversions:", *[f"• {s}" for s in conversions], ""]
                lines += [
                    "Molar mass derivation (u → g/mol):",
                    "• " + " • ".join(aw_bits),
                    *per_terms,
                    "• Total M = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = **{_fmt_num(M_r)} g/mol**",
                    "",
                    "Equations:",
                    "• **n = m / M**",
                    "• **molality (m) = n / m_solvent(kg)**",
                    "",
                    "Step 1 — Moles of solute:",
                    f"• n = {_fmt_num(grams)} g ÷ {_fmt_num(M_r)} g·mol⁻¹ = **{_fmt_num(n_solute)} mol**",
                    "",
                    "Step 2 — Molality:",
                    f"• m = {_fmt_num(n_solute)} mol ÷ {_fmt_num(m_solvent_kg)} kg = **{_fmt_num(m_molality)} mol/kg**",
                ]
                short = f"Molality ≈ **{_fmt_num(m_molality)} m**."
                # 🔊 adaptive speech
                speak_answer(target="Molality", value=_fmt_num(m_molality), unit="mol per kilogram")

            # ===== Case B: moles of solute + solvent mass → molality =====
            elif moles_match and m_solvent_kg is not None:
                n_val = float(moles_match.group(1))
                m_molality = n_val / m_solvent_kg

                if concise:
                    en = f"Molality is about {_fmt_num(m_molality)} mol/kg."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Molality (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Convert to molarity", "Mass of solute for given m", "Find mole fraction"]
                    )
                    _emit_gui(gui, intent="molality", show_more=True, ctx=ctx, action="new")
                    return gui

                lines = [
                    f"Givens: n_solute = **{_fmt_num(n_val)} mol**, m_solvent = **{_fmt_num(m_solvent_kg)} kg**",
                ]
                if conversions:
                    lines += ["Unit conversions:", *[f"• {s}" for s in conversions], ""]
                lines += [
                    "Equation:",
                    "• **molality (m) = n / m_solvent(kg)**",
                    "",
                    "Substitution:",
                    f"• m = {_fmt_num(n_val)} mol ÷ {_fmt_num(m_solvent_kg)} kg = **{_fmt_num(m_molality)} mol/kg**",
                ]
                short = f"Molality ≈ **{_fmt_num(m_molality)} m**."
                speak_answer(target="Molality", value=_fmt_num(m_molality), unit="mol per kilogram")

            # ===== Case C: % w/w of solute + total solution mass + formula → molality =====
            elif wwm and (tot1 or tot2):
                pct = float(wwm.group(1))
                formula = wwm.group(2)
                # total mass (solution)
                if tot1:
                    tm_val, tm_u = float(tot1.group(1)), tot1.group(2).lower()
                else:
                    tm_val, tm_u = float(tot2.group(1)), tot2.group(2).lower()

                # Convert total mass to grams for easy % math; show conversions; then to kg for solvent
                conv_local = []
                if tm_u == "kg":
                    total_mass_g = tm_val * 1000.0
                    conv_local.append(f"Total solution: {_fmt_num(tm_val)} kg → **{_fmt_num(total_mass_g)} g**")
                else:
                    total_mass_g = tm_val
                    conv_local.append(f"Total solution already in g: **{_fmt_num(total_mass_g)} g**")

                # % w/w: pct g solute per 100 g solution
                m_solute_g = pct * total_mass_g / 100.0
                conv_local.append(f"Solute mass from % w/w: {pct} g / 100 g × {_fmt_num(total_mass_g)} g = **{_fmt_num(m_solute_g)} g**")

                # solvent mass = total − solute
                m_solvent_g = total_mass_g - m_solute_g
                m_solvent_kg_local = m_solvent_g / 1000.0
                conv_local.append(f"Solvent mass: {_fmt_num(total_mass_g)} g − {_fmt_num(m_solute_g)} g = **{_fmt_num(m_solvent_g)} g** → **{_fmt_num(m_solvent_kg_local)} kg**")

                # Now compute moles and molality
                _, aw_bits, per_terms, contrib_values, M_r = _molar_mass_block(formula)
                n_solute = m_solute_g / M_r
                m_molality = n_solute / m_solvent_kg_local

                if concise:
                    en = f"Molality is about {_fmt_num(m_molality)} mol/kg."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Molality (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Convert to molarity", "Mass of solute for given m", "Find mole fraction"]
                    )
                    _emit_gui(gui, intent="molality", show_more=True, ctx=ctx, action="new")
                    return gui

                lines = [
                    f"Givens: c = **{_fmt_num(pct)}% w/w** {formula}, total solution mass = **{_fmt_num(tm_val)} {tm_u}**",
                    "Unit conversions:",
                    *[f"• {s}" for s in conv_local], "",
                    "Molar mass derivation (u → g/mol):",
                    "• " + " • ".join(aw_bits),
                    *per_terms,
                    "• Total M = " + " + ".join([_fmt_num(v) for v in contrib_values]) + f" = **{_fmt_num(M_r)} g/mol**",
                    "",
                    "Equations:",
                    "• **n = m_solute / M**",
                    "• **molality (m) = n / m_solvent(kg)**",
                    "",
                    "Step 1 — Moles of solute:",
                    f"• n = {_fmt_num(m_solute_g)} g ÷ {_fmt_num(M_r)} g·mol⁻¹ = **{_fmt_num(n_solute)} mol**",
                    "",
                    "Step 2 — Molality:",
                    f"• m = {_fmt_num(n_solute)} mol ÷ {_fmt_num(m_solvent_kg_local)} kg = **{_fmt_num(m_molality)} mol/kg**",
                ]
                short = f"Molality ≈ **{_fmt_num(m_molality)} m**."
                speak_answer(target="Molality", value=_fmt_num(m_molality), unit="mol per kilogram")

            else:
                # Guidance for users on what to include
                raise ValueError(
                    "For molality, provide either:\n"
                    "• grams of solute + formula + solvent mass (g or kg), or\n"
                    "• moles of solute (n=...) + solvent mass (g or kg), or\n"
                    "• % w/w of solute + total solution mass + formula."
                )

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking for solution concentration as molality (m = moles of solute per kg of solvent).",
                lines=lines,
                short_answer=short,
                followups=[
                    "Convert molality to molarity (needs density)",
                    "Mass of solute needed for 1.00 kg solvent at given m",
                    "Find mole fraction from molality"
                ]
            )
            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui


        # ---------- MOLARITY ↔ MOLALITY CONVERSION ----------
        if intent == "molarity_molality":
            lt = user_text.lower()

            # Parse inputs
            m_match  = re.search(r"\bm\s*=\s*([-\d.]+)\b", lt)         # mol/kg
            M_match  = re.search(r"\bM\s*=\s*([-\d.]+)\b", lt)         # mol/L
            rho1     = re.search(r"(?:rho|ρ|density)\s*[:=]?\s*([-\d.]+)\s*(g/ml|g\/ml|kg\/l|kg/l|g\/cm3|g/cm3)", lt)
            Mr_match = re.search(r"\b(?:Mr|M_r|molar\s*mass)\s*[:=]?\s*([-\d.]+)", lt)
            formula_m = re.search(r"(?:of|for)\s+([A-Za-z][A-Za-z0-9().]*)", lt)

            # Density → g/mL (show conversion)
            conversions = []
            rho_g_per_mL = None
            if rho1:
                rho_val = float(rho1.group(1))
                rho_u = rho1.group(2).lower()
                if rho_u in {"g/ml", "g/cm3"}:
                    rho_g_per_mL = rho_val
                    conversions.append(f"Density already in g/mL: **{_fmt_num(rho_g_per_mL)} g/mL**")
                elif rho_u in {"kg/l"}:
                    rho_g_per_mL = rho_val  # 1 kg/L = 1 g/mL
                    conversions.append(f"Density: {_fmt_num(rho_val)} kg/L → **{_fmt_num(rho_g_per_mL)} g/mL**")
                else:
                    rho_g_per_mL = rho_val
                    conversions.append(f"Density treated as g/mL: **{_fmt_num(rho_g_per_mL)} g/mL**")

            # Mr either provided or computed from formula
            Mr = float(Mr_match.group(1)) if Mr_match else None
            if Mr is None and formula_m:
                Mr = molar_mass(formula_m.group(1))

            if rho_g_per_mL is None:
                raise ValueError("Please provide density (e.g., rho=1.12 g/mL or density 1.12 kg/L).")
            if Mr is None:
                raise ValueError("Provide molar mass (Mr=...) or specify a chemical formula (e.g., of NaCl).")

            lines, short = [], ""

            # m → M (basis: 1.000 kg solvent)
            if m_match and not M_match:
                m_val = float(m_match.group(1))
                numerator   = 1000.0 * m_val * rho_g_per_mL
                denominator = 1000.0 + m_val * Mr
                if denominator <= 0:
                    raise ValueError("Invalid combination of m, Mr, and density.")
                M_val = numerator / denominator

                if concise:
                    en = f"Molarity is about {_fmt_num(M_val)} mol/L."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Convert molality (m) → molarity (M) (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Convert the other way", "Use a new density", "Show steps"]
                    )
                    _emit_gui(gui, intent="molarity_molality", show_more=True, ctx=ctx, action="new")
                    return gui

                lines = [
                    f"Givens: m = **{_fmt_num(m_val)} mol/kg**, Mr = **{_fmt_num(Mr)} g/mol**, ρ = **{_fmt_num(rho_g_per_mL)} g/mL**",
                ]
                if conversions:
                    lines += ["Unit conversions:", *[f"• {s}" for s in conversions], ""]
                lines += [
                    "Basis: **1.000 kg solvent**",
                    f"• Mass of solute = m × Mr = {_fmt_num(m_val)} × {_fmt_num(Mr)} = **{_fmt_num(m_val*Mr)} g**",
                    f"• Mass of solution = 1000 g + {_fmt_num(m_val*Mr)} g = **{_fmt_num(1000 + m_val*Mr)} g**",
                    f"• Volume of solution = mass ÷ ρ = {_fmt_num(1000 + m_val*Mr)} g ÷ {_fmt_num(rho_g_per_mL)} g/mL = **{_fmt_num((1000 + m_val*Mr)/rho_g_per_mL)} mL**",
                    f"• Volume in liters = **{_fmt_num(((1000 + m_val*Mr)/rho_g_per_mL)/1000)} L**",
                    "",
                    "Molarity:",
                    f"• M = n ÷ V = {_fmt_num(m_val)} mol ÷ {_fmt_num(((1000 + m_val*Mr)/rho_g_per_mL)/1000)} L = **{_fmt_num(M_val)} mol/L**",
                ]
                short = f"Molarity ≈ **{_fmt_num(M_val)} M**."
                speak_answer(target="Molarity", value=_fmt_num(M_val), unit="mol per liter")

            # M → m (basis: 1.000 L solution)
            elif M_match and not m_match:
                M_val = float(M_match.group(1))
                mass_solution_g = rho_g_per_mL * 1000.0
                mass_solute_g   = M_val * Mr
                mass_solvent_kg = (mass_solution_g - mass_solute_g) / 1000.0
                if mass_solvent_kg <= 0:
                    raise ValueError("Calculated solvent mass is non-positive. Check density, M, and Mr.")
                m_val = M_val / mass_solvent_kg

                if concise:
                    en = f"Molality is about {_fmt_num(m_val)} mol/kg."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Convert molarity (M) → molality (m) (concise).",
                        lines=[],
                        short_answer=en,
                        followups=["Convert the other way", "Use a new density", "Show steps"]
                    )
                    _emit_gui(gui, intent="molarity_molality", show_more=True, ctx=ctx, action="new")
                    return gui

                lines = [
                    f"Givens: M = **{_fmt_num(M_val)} mol/L**, Mr = **{_fmt_num(Mr)} g/mol**, ρ = **{_fmt_num(rho_g_per_mL)} g/mL**",
                ]
                if conversions:
                    lines += ["Unit conversions:", *[f"• {s}" for s in conversions], ""]
                lines += [
                    "Basis: **1.000 L solution**",
                    f"• Mass of solution = ρ × 1000 mL = {_fmt_num(rho_g_per_mL)} × 1000 = **{_fmt_num(mass_solution_g)} g**",
                    f"• Mass of solute = M × Mr = {_fmt_num(M_val)} × {_fmt_num(Mr)} = **{_fmt_num(mass_solute_g)} g**",
                    f"• Mass of solvent = {_fmt_num(mass_solution_g)} g − {_fmt_num(mass_solute_g)} g = **{_fmt_num(mass_solution_g - mass_solute_g)} g**",
                    f"• Solvent in kg = **{_fmt_num(mass_solvent_kg)} kg**",
                    "",
                    "Molality:",
                    f"• m = n ÷ kg_solvent = {_fmt_num(M_val)} mol ÷ {_fmt_num(mass_solvent_kg)} kg = **{_fmt_num(m_val)} mol/kg**",
                ]
                short = f"Molality ≈ **{_fmt_num(m_val)} m**."
                speak_answer(target="Molality", value=_fmt_num(m_val), unit="mol per kilogram")

            else:
                raise ValueError("Provide either m=... (with density and Mr/formula) to get M, or M=... (with density and Mr/formula) to get m.")

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking to convert between molarity (M) and molality (m) using density.",
                lines=lines,
                short_answer=short,
                followups=[
                    "Convert molality to molarity for a new density",
                    "Find mass percent from M and density",
                    "Compute mole fraction from molality"
                ]
            )
            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui


        # ---------- MIXING TWO SOLUTIONS ----------
        if intent == "mixing":
            lt = user_text.lower()

            # Helper to show volume normalization
            def _vol_to_L_show(val_str, unit_str):
                v = float(val_str)
                u = (unit_str or "").lower()
                if u == "l":
                    return v, f"Volume already in L: **{_fmt_num(v)} L**"
                else:
                    L = v / 1000.0
                    return L, f"Volume: {_fmt_num(v)} mL → **{_fmt_num(L)} L**"

            # Parse M1, V1, M2, V2 (V in mL or L)
            M1m = re.search(r"\bM1\s*=\s*([-\d.]+)\b", lt)
            V1m = re.search(r"\bV1\s*=\s*([-\d.]+)\s*(mL|L)\b", user_text, re.I)
            M2m = re.search(r"\bM2\s*=\s*([-\d.]+)\b", lt)
            V2m = re.search(r"\bV2\s*=\s*([-\d.]+)\s*(mL|L)\b", user_text, re.I)

            if not (M1m and V1m and M2m and V2m):
                raise ValueError("Please provide M1, V1 (mL/L), M2, and V2 (mL/L).")

            M1 = float(M1m.group(1))
            V1_L, conv1 = _vol_to_L_show(V1m.group(1), V1m.group(2))
            M2 = float(M2m.group(1))
            V2_L, conv2 = _vol_to_L_show(V2m.group(1), V2m.group(2))

            # Compute final concentration
            n1 = M1 * V1_L
            n2 = M2 * V2_L
            Vt = V1_L + V2_L
            if Vt <= 0:
                raise ValueError("Total volume must be > 0.")
            M_final = (n1 + n2) / Vt

            # ✅ Concise → speak + Solution popup (with chips)
            if concise:
                en = f"Final concentration ≈ {_fmt_num(M_final)} mol/L."
                _say_or_show_en(en)

                gui = _format_gui_block(
                    question=command,
                    understanding="Mixing two solutions (concise).",
                    lines=[],  # concise => no steps yet
                    short_answer=en,
                    followups=[
                        "Moles after mixing…",
                        "What if volumes change?…",
                        "Relate to M1V1=M2V2…"
                    ]
                )
                _emit_gui(gui, intent="mixing", show_more=True, ctx=ctx, action="new")
                return gui

            # ----- verbose steps -----
            lines = [
                "We’ll compute total moles and total volume, then use **M = n / V**.",
                f"Givens: M₁={_fmt_num(M1)} mol/L, V₁={_fmt_num(V1_L)} L; M₂={_fmt_num(M2)} mol/L, V₂={_fmt_num(V2_L)} L",
                "Unit conversions:",
                f"• {conv1}",
                f"• {conv2}",
                "",
                "Step 1 — Moles from each solution:",
                f"• n₁ = M₁ × V₁ = {_fmt_num(M1)} × {_fmt_num(V1_L)} = **{_fmt_num(n1)} mol**",
                f"• n₂ = M₂ × V₂ = {_fmt_num(M2)} × {_fmt_num(V2_L)} = **{_fmt_num(n2)} mol**",
                "",
                "Step 2 — Total volume:",
                f"• V_total = V₁ + V₂ = {_fmt_num(V1_L)} + {_fmt_num(V2_L)} = **{_fmt_num(Vt)} L**",
                "",
                "Step 3 — Final concentration:",
                f"• M_final = (n₁ + n₂) / V_total = ({_fmt_num(n1)} + {_fmt_num(n2)}) / {_fmt_num(Vt)} = **{_fmt_num(M_final)} mol/L**",
            ]
            short = f"Final concentration ≈ **{_fmt_num(M_final)} M**."
            speak_answer(target="Final concentration", value=_fmt_num(M_final), unit="mol per liter")

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking the concentration after mixing two solutions.",
                lines=lines,
                short_answer=short,
                followups=[
                    "If one part is pure water (M=0), recompute",
                    "What volume of stock is needed to reach a target M?",
                    "Assume volumes are additive — show % error if density changes"
                ]
            )
            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui



        # ---------- DILUTION (2-pair and 3-pair) ----------
        if intent == "dilution":
            lt = user_text.lower()

            # Parse M1, M2, M3 (mol/L)
            M1m = re.search(r"\bM1\s*=\s*([-\d.]+)\b", lt)
            M2m = re.search(r"\bM2\s*=\s*([-\d.]+)\b", lt)
            M3m = re.search(r"\bM3\s*=\s*([-\d.]+)\b", lt)

            # Parse V1, V2, V3 with units (mL, L, m^3/m³). If unitless, treat as L.
            def _parse_vol(tag: str):
                m = re.search(rf"\b{tag}\s*=\s*([-\d.]+)\s*(mL|L|m\^?3|m³)?\b", user_text, re.I)
                if not m: return None, None, None
                val = float(m.group(1))
                unit = (m.group(2) or "L").upper().replace("M³", "M^3")
                return val, unit, m.group(0)

            V1_val, V1_unit, _ = _parse_vol("V1")
            V2_val, V2_unit, _ = _parse_vol("V2")
            V3_val, V3_unit, _ = _parse_vol("V3")

            # Collect raw numbers
            nums_raw = {}
            if M1m: nums_raw["M1"] = float(M1m.group(1))
            if M2m: nums_raw["M2"] = float(M2m.group(1))
            if M3m: nums_raw["M3"] = float(M3m.group(1))
            if V1_val is not None: nums_raw["V1"] = (V1_val, V1_unit)
            if V2_val is not None: nums_raw["V2"] = (V2_val, V2_unit)
            if V3_val is not None: nums_raw["V3"] = (V3_val, V3_unit)

            # Determine which tags are even in play (mentioned)
            mentioned = set(nums_raw.keys())

            # Count unknowns among the mentioned slots; allow either 2-pair or 3-pair mode
            all_tags = ["M1", "V1", "M2", "V2", "M3", "V3"]
            provided_vals = {k: v for k, v in nums_raw.items()}
            unknowns = [k for k in mentioned if (isinstance(provided_vals.get(k), tuple) and provided_vals[k][0] is None) or (provided_vals.get(k) is None)]

            # Normalize volumes to liters and log conversions (only for those present)
            conv_lines = []
            def _to_L(val: float, unit: str, tag: str) -> float:
                u = unit.upper()
                if u == "L":
                    conv_lines.append(f"{tag} already in L: **{_fmt_num(val)} L**")
                    return val
                if u == "ML":
                    L = val / 1000.0
                    conv_lines.append(f"{tag}: {_fmt_num(val)} mL → **{_fmt_num(L)} L**")
                    return L
                if u in {"M^3"}:
                    L = val * 1000.0
                    conv_lines.append(f"{tag}: {_fmt_num(val)} m³ → **{_fmt_num(L)} L**")
                    return L
                # default assume mL
                L = val / 1000.0
                conv_lines.append(f"{tag}: {_fmt_num(val)} mL → **{_fmt_num(L)} L**")
                return L

            V1_L = _to_L(V1_val, V1_unit, "V₁") if V1_val is not None else None
            V2_L = _to_L(V2_val, V2_unit, "V₂") if V2_val is not None else None
            V3_L = _to_L(V3_val, V3_unit, "V₃") if V3_val is not None else None

            # Build pairs (only those with any data mentioned)
            pairs = {
                "1": {"M": (nums_raw.get("M1") if "M1" in mentioned else None), "V": (V1_L if "V1" in mentioned else None)},
                "2": {"M": (nums_raw.get("M2") if "M2" in mentioned else None), "V": (V2_L if "V2" in mentioned else None)},
                "3": {"M": (nums_raw.get("M3") if "M3" in mentioned else None), "V": (V3_L if "V3" in mentioned else None)},
            }

            # Helper: is a pair complete?
            def complete(p): return (p["M"] is not None) and (p["V"] is not None)

            # Identify mode (2-pair vs 3-pair) from how many indices are mentioned
            active_idxs = [i for i in ["1","2","3"] if (("M"+i) in mentioned) or (("V"+i) in mentioned)]
            complete_idxs = [i for i in active_idxs if complete(pairs[i])]

            # Need at least one complete pair; exactly one variable overall must be unknown
            active_tags = []
            for i in active_idxs:
                if ("M"+i) in mentioned: active_tags.append("M"+i)
                if ("V"+i) in mentioned: active_tags.append("V"+i)
            unknown = [t for t in active_tags if (t.startswith("M") and pairs[t[-1]]["M"] is None) or (t.startswith("V") and pairs[t[-1]]["V"] is None)]
            if len(unknown) != 1:
                raise ValueError("Please provide exactly one unknown among the mentioned variables. Include at least one full pair (Mi and Vi).")
            unknown = unknown[0]  # e.g., 'V1' or 'M3'

            if len(complete_idxs) < 1:
                raise ValueError("Please provide at least one complete pair (both M and V for the same index).")

            # Choose a base complete pair to define K = M · V (use the first complete)
            base_idx = complete_idxs[0]
            K = pairs[base_idx]["M"] * pairs[base_idx]["V"]  # common n (moles) reference

            # Basic validation
            if K <= 0:
                raise ValueError("M and V must be positive.")

            # Solve the unknown using K
            u_idx = unknown[-1]            # '1'/'2'/'3'
            u_is_M = unknown.startswith("M")
            mate_V = pairs[u_idx]["V"]
            mate_M = pairs[u_idx]["M"]
            if u_is_M:
                if mate_V is None:
                    raise ValueError(f"Missing V{u_idx} to solve for M{u_idx}.")
                solved_val = K / mate_V
            else:
                if mate_M is None:
                    raise ValueError(f"Missing M{u_idx} to solve for V{u_idx}.")
                solved_val = K / mate_M

            # Assemble resolved dictionary (for unified output)
            res = {
                "M1": pairs["1"]["M"] if "M1" in mentioned else None,
                "V1": pairs["1"]["V"] if "V1" in mentioned else None,
                "M2": pairs["2"]["M"] if "M2" in mentioned else None,
                "V2": pairs["2"]["V"] if "V2" in mentioned else None,
                "M3": pairs["3"]["M"] if "M3" in mentioned else None,
                "V3": pairs["3"]["V"] if "V3" in mentioned else None,
            }
            if u_is_M:
                res["M"+u_idx] = solved_val
            else:
                res["V"+u_idx] = solved_val

            # ✅ Concise → speak + Solution popup (with chips)
            if concise:
                if u_is_M:
                    en = f"M{u_idx} ≈ {_fmt_num(solved_val)} mol/L."
                    _say_or_show_en(en)
                else:
                    en = f"V{u_idx} ≈ {_fmt_num(solved_val)} L."
                    _say_or_show_en(en)

                gui = _format_gui_block(
                    question=command,
                    understanding="Dilution (concise).",
                    lines=[],
                    short_answer=en,
                    followups=[
                        "Make 250 mL of 0.20 M from 1.00 M",
                        "What volume of stock for 500 mL at 0.50 M?",
                        "If volume doubles, what’s the new molarity?"
                    ]
                )
                _emit_gui(gui, intent="dilution", show_more=True, ctx=ctx, action="new")
                return gui

            # Pretty subscript helper
            sub = {"1":"₁","2":"₂","3":"₃"}

            # Rearrangement line depends on which complete pair we used
            base_M = f"M{sub[base_idx]}"; base_V = f"V{sub[base_idx]}"
            unk_M = f"M{sub[u_idx]}";     unk_V = f"V{sub[u_idx]}"
            if u_is_M:
                rearr = f"{unk_M} = ({base_M} · {base_V}) / {unk_V}"
                sub_line = f"• {unk_M} = ({_fmt_num(pairs[base_idx]['M'])} × {_fmt_num(pairs[base_idx]['V'])} L) ÷ {_fmt_num(mate_V)} L = **{_fmt_num(solved_val)} mol/L**"
            else:
                rearr = f"{unk_V} = ({base_M} · {base_V}) / {unk_M}"
                sub_line = f"• {unk_V} = ({_fmt_num(pairs[base_idx]['M'])} × {_fmt_num(pairs[base_idx]['V'])} L) ÷ {_fmt_num(mate_M)} = **{_fmt_num(solved_val)} L**"

            # Build normalized "Givens" (only for mentioned tags)
            givens_bits = []
            if "M1" in mentioned: givens_bits.append(f"M₁={_fmt_num(res['M1'])} mol/L" if res["M1"] is not None else "M₁=—")
            if "V1" in mentioned: givens_bits.append(f"V₁={_fmt_num(res['V1'])} L"    if res["V1"] is not None else "V₁=—")
            if "M2" in mentioned: givens_bits.append(f"M₂={_fmt_num(res['M2'])} mol/L" if res["M2"] is not None else "M₂=—")
            if "V2" in mentioned: givens_bits.append(f"V₂={_fmt_num(res['V2'])} L"    if res["V2"] is not None else "V₂=—")
            if "M3" in mentioned: givens_bits.append(f"M₃={_fmt_num(res['M3'])} mol/L" if res["M3"] is not None else "M₃=—")
            if "V3" in mentioned: givens_bits.append(f"V₃={_fmt_num(res['V3'])} L"    if res["V3"] is not None else "V₃=—")
            givens_line = ", ".join(givens_bits)

            # GUI lines
            header_relation = "Relation: **M₁V₁ = M₂V₂**" if ("M3" not in mentioned and "V3" not in mentioned) else "Relation: **M₁V₁ = M₂V₂ = M₃V₃**"
            lines = [header_relation + " (volumes in liters)"]
            if conv_lines:
                lines += ["Unit conversions:", *[f"• {s}" for s in conv_lines]]
            lines += [
                "",
                f"Givens (normalized): {givens_line}",
                f"Unknown: **{'M' if u_is_M else 'V'}{u_idx}**",
                "",
                "Rearrange for the unknown (using a known pair):",
                f"• {rearr}",
                "",
                "Substitute and compute:",
                sub_line,
                "",
                "Solved values (for provided indices):",
            ]
            solved_bits = []
            for key in ["M1","V1","M2","V2","M3","V3"]:
                if key in mentioned and res.get(key) is not None:
                    unit = " mol/L" if key.startswith("M") else " L"
                    label = key.replace("1","₁").replace("2","₂").replace("3","₃")
                    solved_bits.append(f"{label}={_fmt_num(res[key])}{unit}")
            if solved_bits:
                lines.append("• " + ", ".join(solved_bits))

            # Short + adaptive speech
            short = f"Dilution solved: {('M' if u_is_M else 'V')}{u_idx} = " + (
                f"{_fmt_num(solved_val)} mol/L." if u_is_M else f"{_fmt_num(solved_val)} L."
            )
            target_names = {"M":"Molarity", "V":"Volume"}
            speak_answer(
                target=f"{target_names['M' if u_is_M else 'V']} {u_idx}",
                value=_fmt_num(solved_val),
                unit=("mol per liter" if u_is_M else "liters")
            )

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking a dilution problem (supports both two-pair and three-pair forms).",
                lines=lines,
                short_answer=short,
                followups=[
                    "Make 250 mL of 0.20 M from 1.00 M",
                    "What volume of stock for 500 mL at 0.50 M?",
                    "If volume doubles, what’s the new molarity?"
                ]
            )
            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui


        # ---------- ACID / BASE ----------
        if intent == "acid_base":
            lt = user_text.lower()

            # Local pretty formatter just for acid/base (tiny numbers → scientific notation)
            def _fmt_ab(x: float) -> str:
                try:
                    x = float(x)
                except Exception:
                    return str(x)
                ax = abs(x)
                if x != 0.0 and (ax < 0.01 or ax >= 1e5):
                    return f"{x:.2e}"  # e.g., 6.00e-07
                return f"{x:.2f}"  # default: 2 decimals (matches your app)

            # Accept:
            #   "pH of 0.10 M acid", "ph of 25 mM hcl", "pH of 1.0 μM strong acid"
            #   "pOH of 0.05 M base", "poh of 3 mM NaOH", "pOH of 2.5 μM strong base"
            acidM = re.search(
                r"\bph\s+of\s+([-\d.]+)\s*(m|mm|μm|um)?\s*(?:acid|hcl|strong\s+acid)\b",
                lt, re.I
            )
            baseM = re.search(
                r"\bpoh\s+of\s+([-\d.]+)\s*(m|mm|μm|um)?\s*(?:base|naoh|koh|strong\s+base)\b",
                lt, re.I
            )

            # Unit conversions (explicitly shown in GUI)
            conv_lines = []

            def _conc_to_M_show(val_str: str, unit: str | None) -> float:
                """Convert M/mM/μM -> M; append factor-label line for GUI (using acid/base formatter)."""
                v = float(val_str)
                u = (unit or "m").lower()
                if u == "m":
                    conv_lines.append(f"Concentration: **{_fmt_ab(v)} M** (already in mol/L)")
                    return v
                if u == "mm":
                    M = v / 1000.0
                    conv_lines.append(
                        f"Concentration: **{_fmt_ab(v)} mM × (1 mol / 1000 mM) = {_fmt_ab(M)} mol/L**"
                    )
                    return M
                if u in {"μm", "um"}:
                    M = v / 1_000_000.0
                    conv_lines.append(
                        f"Concentration: **{_fmt_ab(v)} μM × (1 mol / 10⁶ μM) = {_fmt_ab(M)} mol/L**"
                    )
                    return M
                conv_lines.append(f"Concentration treated as **{_fmt_ab(v)} M**")
                return v

            # 25 °C water auto-ionization constant
            KW = 1.0e-14  # mol^2/L^2 at 25 °C

            def _acid_ph_with_correction(C_M: float):
                reasoning = []
                if C_M <= 1e-6:
                    reasoning += [
                        "Pure water at 25 °C: **Kᵥ = 1.0×10⁻¹⁴ ⇒ [H⁺] = 1.0×10⁻⁷ M**.",
                        f"Given **C = {_fmt_ab(C_M)} M**, which is close to 10⁻⁷ M, so water’s contribution is significant.",
                        "Therefore, use the exact expression for total [H⁺].",
                    ]
                    H = 0.5 * (C_M + (C_M**2 + 4*KW) ** 0.5)
                    return {"pH": -math.log10(H), "corrected": True, "H": H, "reasoning": reasoning}
                H = C_M
                return {"pH": -math.log10(H), "corrected": False, "H": H, "reasoning": reasoning}

            def _base_ph_with_correction(C_M: float):
                reasoning = []
                if C_M <= 1e-6:
                    reasoning += [
                        "Pure water at 25 °C: **Kᵥ = 1.0×10⁻¹⁴ ⇒ [OH⁻] = 1.0×10⁻⁷ M**.",
                        f"Given **C = {_fmt_ab(C_M)} M**, comparable to 10⁻⁷ M, so water’s [OH⁻] matters.",
                        "Therefore, use the exact expression for total [OH⁻].",
                    ]
                    OH = 0.5 * (C_M + (C_M**2 + 4*KW) ** 0.5)
                    pOH = -math.log10(OH)
                    return {"pOH": pOH, "pH": 14.0 - pOH, "corrected": True, "OH": OH, "reasoning": reasoning}
                OH = C_M
                pOH = -math.log10(OH)
                return {"pOH": pOH, "pH": 14.0 - pOH, "corrected": False, "OH": OH, "reasoning": reasoning}

            lines, short = [], ""

            if acidM:
                C_M = _conc_to_M_show(acidM.group(1), acidM.group(2))
                out = _acid_ph_with_correction(C_M)

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"pH is about {_fmt_ab(out['pH'])}."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Strong acid pH (concise, 25 °C).",
                        lines=[],
                        short_answer=en,
                        followups=["pH → [H+]", "Buffer calculation", "Titration steps"]
                    )
                    _emit_gui(gui, intent="acid_base", show_more=True, ctx=ctx, action="new")
                    return gui

                lines = [
                    "Assumption: **strong monoprotic acid** (e.g., HCl) ⇒ nominally **[H⁺] ≈ C**; 25 °C ⇒ **pH + pOH = 14**",
                    "Unit conversions:",
                    *[f"• {s}" for s in conv_lines],
                    "",
                ]

                if not out["corrected"]:
                    lines += [
                        "Equations:",
                        "• **pH = −log₁₀([H⁺])** with **[H⁺] ≈ C**",
                        "",
                        "Substitution:",
                        f"• [H⁺] = {_fmt_ab(C_M)} mol/L",
                        f"• pH = −log₁₀({_fmt_ab(C_M)}) = **{_fmt_ab(out['pH'])}**",
                    ]
                else:
                    lines += [
                        "Why Kw correction is required:",
                        *[f"• {s}" for s in out["reasoning"]],
                        "",
                        "Exact expression (25 °C):",
                        "• **[H⁺] = (C + √(C² + 4Kᵥ)) / 2**  with  **Kᵥ = 1.0×10⁻¹⁴**",
                        "",
                        "Substitution:",
                        f"• [H⁺] = ({_fmt_ab(C_M)} + √({_fmt_ab(C_M)}² + 4×1.0×10⁻¹⁴)) / 2 = **{_fmt_ab(out['H'])} mol/L**",
                        f"• pH = −log₁₀({_fmt_ab(out['H'])}) = **{_fmt_ab(out['pH'])}**",
                    ]

                short = f"pH ≈ **{_fmt_ab(out['pH'])}**."
                speak_answer(target="pH", value=_fmt_ab(out['pH']))

            elif baseM:
                C_M = _conc_to_M_show(baseM.group(1), baseM.group(2))
                out = _base_ph_with_correction(C_M)

                # ✅ Concise → speak + Solution popup (with chips)
                if concise:
                    en = f"pH is about {_fmt_ab(out['pH'])}."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Strong base pH (concise, 25 °C).",
                        lines=[],
                        short_answer=en,
                        followups=["pOH → [OH−]", "Buffer calculation", "Titration steps"]
                    )
                    _emit_gui(gui, intent="acid_base", show_more=True, ctx=ctx, action="new")
                    return gui

                lines = [
                    "Assumption: **strong monoprotic base** (e.g., NaOH) ⇒ nominally **[OH⁻] ≈ C**; 25 °C ⇒ **pH + pOH = 14**",
                    "Unit conversions:",
                    *[f"• {s}" for s in conv_lines],
                    "",
                ]

                if not out["corrected"]:
                    lines += [
                        "Step 1:",
                        "• **pOH = −log₁₀([OH⁻])** with **[OH⁻] ≈ C**",
                        f"• pOH = −log₁₀({_fmt_ab(C_M)}) = **{_fmt_ab(out['pOH'])}**",
                        "",
                        "Step 2:",
                        "• **pH = 14 − pOH** (at 25 °C)",
                        f"• pH = 14 − {_fmt_ab(out['pOH'])} = **{_fmt_ab(out['pH'])}**",
                    ]
                else:
                    lines += [
                        "Why Kw correction is required:",
                        *[f"• {s}" for s in out["reasoning"]],
                        "",
                        "Exact expression (25 °C):",
                        "• **[OH⁻] = (C + √(C² + 4Kᵥ)) / 2**  with  **Kᵥ = 1.0×10⁻¹⁴**",
                        "",
                        "Substitution:",
                        f"• [OH⁻] = ({_fmt_ab(C_M)} + √({_fmt_ab(C_M)}² + 4×1.0×10⁻¹⁴)) / 2 = **{_fmt_ab(out['OH'])} mol/L**",
                        f"• pOH = −log₁₀({_fmt_ab(out['OH'])}) = **{_fmt_ab(out['pOH'])}**",
                        "",
                        "Then:",
                        "• **pH = 14 − pOH** (at 25 °C)",
                        f"• pH = 14 − {_fmt_ab(out['pOH'])} = **{_fmt_ab(out['pH'])}**",
                    ]

                short = f"pH ≈ **{_fmt_ab(out['pH'])}**" + (f" (pOH ≈ **{_fmt_ab(out['pOH'])}**)" if "pOH" in out else "")
                speak_answer(target="pH", value=_fmt_ab(out['pH']))

            else:
                raise ValueError("Specify like: 'pH of 0.10 M acid' or 'pOH of 25 mM base' (strong, monoprotic). Units: M, mM, μM.")

            gui = _format_gui_block(
                question=command,
                understanding="You’re asking a pH/pOH calculation for a strong monoprotic acid/base (25 °C).",
                lines=lines,
                short_answer=short,
                followups=[
                    "What is pOH (or pH) for the same solution?",
                    "If concentration is in μM, include water auto-ionization reasoning",
                    "How does 10× dilution change the pH?"
                ]
            )
            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui


        
        # ---------- EMPIRICAL / MOLECULAR FORMULA ----------
        if intent == "empirical_formula":
            lt = user_text.lower()

            # ========= helpers =========
            def _digit_sub(n: int) -> str:
                m = str(n)
                table = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
                return m.translate(table)

            def _fmt_formula(parts):
                # parts: list of (El, integer count>=1)
                out = []
                for el, cnt in parts:
                    if cnt == 1:
                        out.append(el)
                    else:
                        out.append(el + _digit_sub(int(round(cnt))))
                return "".join(out)

            def _empirical_from_masses(mass_map):
                # mass_map: {El: grams}
                # 1) grams -> moles
                moles = {}
                steps = []
                for el, g in mass_map.items():
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    n = g / aw if aw > 0 else 0.0
                    moles[el] = n
                    steps.append((el, g, aw, n))
                # 2) divide by smallest
                smallest = min(v for v in moles.values() if v > 0)
                ratios = {el: (moles[el] / smallest if smallest > 0 else 0) for el in moles}

                # 3) try to clear fractions → integers
                def _near(x, target, tol=0.05):  # generous but safe
                    return abs(x - target) <= tol

                # primary quick rounding
                ints = {el: round(r) for el, r in ratios.items()}
                if all(abs(ratios[el] - ints[el]) <= 0.05 for el in ratios):
                    mult = 1
                    final = {el: int(max(1, int(round(ints[el])))) for el in ratios}
                    return steps, smallest, ratios, mult, final

                # structured fraction detection
                candidates = [2, 3, 4, 5, 6, 7, 8]
                for k in candidates:
                    scaled = {el: ratios[el] * k for el in ratios}
                    if all(abs(s - round(s)) <= 0.05 for s in scaled.values()):
                        final = {el: int(round(scaled[el])) for el in ratios}
                        from math import gcd
                        from functools import reduce
                        g = reduce(gcd, [v for v in final.values() if v > 0]) if final else 1
                        final = {el: (v // g if v % g == 0 else v) for el, v in final.items()}
                        return steps, smallest, ratios, k, final

                # fallback: just round
                mult = 1
                final = {el: max(1, int(round(ratios[el]))) for el in ratios}
                return steps, smallest, ratios, mult, final

            def _emp_mass(parts):
                # parts list of (El, count)
                total = 0.0
                terms = []
                for el, cnt in parts:
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    if cnt == 1:
                        terms.append(f"{aw:.3f}")
                        total += aw
                    else:
                        terms.append(f"{cnt} × {aw:.3f}")
                        total += cnt * aw
                return total, terms

            def _order_keys_like_input(keys, original_text):
                # try to preserve the order elements first appeared in user text
                order = []
                seen = set()
                pattern = re.findall(r"\b([A-Z][a-z]?)\b", original_text)
                for tok in pattern:
                    el = tok
                    if el in keys and el not in seen:
                        seen.add(el); order.append(el)
                for el in keys:
                    if el not in seen: order.append(el)
                return order

            # ========= parse inputs: elements with % or g, optional Mr =========
            perc_pairs = []
            mass_pairs = []
            for (el, val) in re.findall(r"\b([A-Z][a-z]?)\s*([0-9]*\.?[0-9]+)\s*%\b", user_text):
                perc_pairs.append((el, float(val)))
            for (val, el) in re.findall(r"\b([0-9]*\.?[0-9]+)\s*%\s*([A-Z][a-z]?)\b", user_text):
                perc_pairs.append((el, float(val)))
            for (el, val) in re.findall(r"\b([A-Z][a-z]?)\s*([0-9]*\.?[0-9]+)\s*g\b", user_text):
                mass_pairs.append((el, float(val)))
            for (val, el) in re.findall(r"\b([0-9]*\.?[0-9]+)\s*g\s*([A-Z][a-z]?)\b", user_text):
                mass_pairs.append((el, float(val)))

            # optional Mr
            Mr = None
            m1 = re.search(r"\bMr\s*[=:]?\s*([0-9]*\.?[0-9]+)", user_text, re.I)
            if not m1:
                m1 = re.search(r"\bmolecular\s+(?:mass|weight)\s*[:=]?\s*([0-9]*\.?[0-9]+)", user_text, re.I)
            if m1:
                Mr = float(m1.group(1))

            # Build grams map
            grams = {}
            lines = []
            step1_lines = []
            used_basis_100 = False

            if perc_pairs:
                tmp = {}
                for el, p in perc_pairs:
                    tmp[el] = p
                total_pct = sum(tmp.values())
                used_basis_100 = True
                step1_lines.append("From 100 g total:")
                if total_pct > 0 and abs(total_pct - 100.0) > 0.5:
                    scale = 100.0 / total_pct
                    for el in _order_keys_like_input(tmp.keys(), user_text):
                        g = tmp[el] * scale
                        grams[el] = g
                        step1_lines.append(f"{el}: {_fmt_num(tmp[el])}% → {_fmt_num(g)} g")
                else:
                    for el in _order_keys_like_input(tmp.keys(), user_text):
                        g = tmp[el]
                        grams[el] = g
                        step1_lines.append(f"{el}: {_fmt_num(tmp[el])}% → {_fmt_num(g)} g")

            if mass_pairs:
                tmp = {}
                for el, g in mass_pairs:
                    tmp[el] = tmp.get(el, 0.0) + float(g)
                if not used_basis_100:
                    step1_lines.append("Givens:")
                for el in _order_keys_like_input(tmp.keys(), user_text):
                    grams[el] = grams.get(el, 0.0) + tmp[el]
                    step1_lines.append(f"{el} = {_fmt_num(tmp[el])} g")

            if not grams:
                raise ValueError("Please provide element amounts as percentages (e.g., 40% C) or masses (e.g., 10 g C).")

            # 1) grams -> moles, gather for Step 2
            steps, smallest, ratios, mult, finals = _empirical_from_masses(grams)

            # keep element order stable
            ordered_els = _order_keys_like_input(list(grams.keys()), user_text)

            # ========= concise mode =========
            if concise:
                emp_parts = [(el, finals[el]) for el in ordered_els]
                emp_formula = _fmt_formula(emp_parts)

                if Mr is not None:
                    M_emp, _terms = _emp_mass([(el, finals[el]) for el in ordered_els])
                    k = max(1, int(round(Mr / M_emp))) if M_emp > 0 else 1
                    mol_parts = [(el, finals[el] * k) for el in ordered_els]
                    mol_formula = _fmt_formula(mol_parts)

                    en = f"Empirical = {emp_formula}; Molecular = {mol_formula}."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Empirical & molecular formula (concise).",
                        lines=[],
                        short_answer=en,
                        followups=[
                            "Show steps",
                            f"Percent composition of {mol_formula}",
                            "Similar problem"
                        ]
                    )
                    _emit_gui(gui, intent="empirical_formula", show_more=True, ctx=ctx, action="new")
                    return gui
                else:
                    en = f"Empirical = {emp_formula}."
                    _say_or_show_en(en)

                    gui = _format_gui_block(
                        question=command,
                        understanding="Empirical formula (concise).",
                        lines=[],
                        short_answer=en,
                        followups=[
                            "Show steps",
                            "Use Mr to get molecular formula",
                            f"Percent composition of {emp_formula}"
                        ]
                    )
                    _emit_gui(gui, intent="empirical_formula", show_more=True, ctx=ctx, action="new")
                    return gui

            # ========= verbose GUI lines =========
            step1_title = "Step 1 — Givens (100 g basis)" if used_basis_100 else "Step 1 — Givens"
            lines.append(step1_title)
            lines.extend(step1_lines)
            lines.append("")

            # Step 2 — Convert masses to moles
            lines.append("Step 2 — Convert masses to moles")
            for el, g, aw, n in steps:
                lines.append(f"{el}: {_fmt_num(g)} g ÷ {_fmt_num(aw)} g·mol⁻¹ = {_fmt_num(n)} mol")
            lines.append("")

            # Step 3 — Divide by the smallest
            lines.append("Step 3 — Divide by the smallest")
            lines.append(f"Smallest ≈ {_fmt_num(smallest)} mol")
            for el in ordered_els:
                lines.append(f"{el}: {_fmt_num(grams[el] / steps[[s[0] for s in steps].index(el)][2])} / {_fmt_num(smallest)} = {_fmt_num(ratios[el])}")
            lines.append("")

            # Step 4 — Clear fractions
            lines.append("Step 4 — Clear fractions")
            if mult == 1 and all(abs(ratios[el] - round(ratios[el])) <= 0.05 for el in ratios):
                ratio_bits = " : ".join([f"{int(round(ratios[el]))}" for el in ordered_els])
                lines.append(f"Ratios are already whole numbers → {ratio_bits}")
                lines.append("")
            else:
                for el in ordered_els:
                    lines.append(f"{el}: {_fmt_num(ratios[el])} × {mult} = {_fmt_num(ratios[el]*mult)}")
                lines.append("")
            
            # Step 5 — Empirical formula
            emp_parts = [(el, finals[el]) for el in ordered_els]
            emp_formula = _fmt_formula(emp_parts)
            lines.append("Step 5 — Empirical formula")
            lines.append(emp_formula)
            lines.append("")

            # Step 6 — Molecular formula from Mr (what is Mr and how we use it?)
            mol_formula = None
            if Mr is not None:
                lines.append("Step 6 — Molecular formula from Mr (what is Mr and how we use it?)")
                lines.append("")
                lines.append("Mr (molar mass of the molecule) = mass per mole of the actual molecule (sum of all its atoms’ masses).")
                lines.append("")
                M_emp, terms = _emp_mass(emp_parts)
                term_bits = []
                for (el, cnt) in emp_parts:
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    if cnt == 1:
                        term_bits.append(f"{_fmt_num(aw)}")
                    else:
                        term_bits.append(f"({cnt} × {_fmt_num(aw)})")
                lines.append("Empirical-formula mass (M_emp):")
                lines.append(f"M_emp = {emp_formula} = " + " + ".join(term_bits) + f" = {_fmt_num(M_emp)} g·mol⁻¹")
                lines.append("")
                k = max(1, int(round(Mr / M_emp))) if M_emp > 0 else 1
                mol_parts = [(el, finals[el] * k) for el in ordered_els]
                mol_formula = _fmt_formula(mol_parts)
                lines.append("")
                lines.append(f"Scale subscripts: ({emp_formula}) × {k} ⇒ {mol_formula}")
                lines.append("")

            # ✅ Answer + Follow-ups (bulleted)
            short_lines = [
                "✅ Answer",
                f"Empirical formula: {emp_formula}",
            ]
            if mol_formula:
                short_lines.append(f"Molecular formula: {mol_formula}")

            followups = [
                "Show empirical mass calculation for another example",
                "Try with direct mass inputs (g) instead of %",
                f"Compute % composition of {mol_formula or emp_formula}",
            ]

            gui = _format_gui_block(
                question=user_text.strip(),
                understanding="We’ll use a 100 g basis so that each % directly converts to mass in grams, then:\n\nConvert g → mol\n\nDivide by the smallest to get ratios\n\nClear fractions (if any)\n\nIf Mr is given, compute the molecular formula.",
                lines=lines,
                short_answer="\n".join(short_lines),
                followups=followups
            )

            # 🔊 Adaptive speech
            if mol_formula:
                speak_answer(target="Empirical formula", value=emp_formula)
                speak_answer(target="Molecular formula", value=mol_formula)
            else:
                speak_answer(target="Empirical formula", value=emp_formula)

            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui


        
        # ---------- LIMITING REAGENT ----------
        if intent == "limiting_reagent":
            lt = user_text.lower()

            # ================== small helpers ==================
            def _digit_sub(n: int) -> str:
                table = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
                return str(n).translate(table)

            def _elements_in_formula(formula: str):
                try:
                    return parse_formula(formula)  # dict: el->count
                except Exception:
                    tokens = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
                    d = {}
                    for el, num in tokens:
                        d[el] = d.get(el, 0) + (int(num) if num else 1)
                    return d

            def _parse_equation(text: str):
                m = re.split(r"->|→", text)
                if len(m) != 2:
                    return None, None
                left, right = m[0], m[1]
                def split_side(s):
                    toks = [t.strip() for t in re.split(r"\+", s) if t.strip()]
                    comps = []
                    for t in toks:
                        mm = re.match(r"^\s*(\d+)\s*([A-Za-z0-9()]+)\s*$", t)
                        if mm:
                            comps.append((mm.group(2), int(mm.group(1))))
                        else:
                            mm2 = re.match(r"^\s*([A-Za-z0-9()]+)\s*$", t)
                            if mm2: comps.append((mm2.group(1), None))
                    return comps
                return split_side(left), split_side(right)

            def _balance(left_list, right_list):
                # Respect given integer coeffs; else compute minimal integers
                if all(c is not None for _, c in left_list + right_list):
                    L = [c for _, c in left_list]; R = [c for _, c in right_list]
                    from math import gcd; from functools import reduce
                    g = reduce(gcd, L + R)
                    if g > 1: L = [x // g for x in L]; R = [x // g for x in R]
                    return L, R, False

                species = [f for f,_ in left_list] + [f for f,_ in right_list]
                side_sign = [1]*len(left_list) + [-1]*len(right_list)
                elements = sorted({el for f,_ in left_list+right_list for el in _elements_in_formula(f).keys()})

                from fractions import Fraction
                rows = len(elements); cols = len(species)
                A = []
                for el in elements:
                    row = []
                    for (f,_), sgn in zip([(f,c) for f,c in left_list+right_list], side_sign):
                        row.append(Fraction(sgn * _elements_in_formula(f).get(el,0), 1))
                    A.append(row)

                # RREF for nullspace
                r=c=0; pivots=[]
                while r < rows and c < cols:
                    pr = next((i for i in range(r, rows) if A[i][c] != 0), None)
                    if pr is None: c += 1; continue
                    A[r], A[pr] = A[pr], A[r]
                    piv = A[r][c]
                    A[r] = [v/piv for v in A[r]]
                    for i in range(rows):
                        if i != r and A[i][c] != 0:
                            fac = A[i][c]
                            A[i] = [A[i][j] - fac*A[r][j] for j in range(cols)]
                    pivots.append((r,c)); r += 1; c += 1

                pivot_cols = {pc for (_r,pc) in pivots}
                free_cols = [j for j in range(cols) if j not in pivot_cols] or [cols-1]
                x = [Fraction(0,1)]*cols
                x[free_cols[-1]] = Fraction(1,1)
                for (ri,ci) in reversed(pivots):
                    s = sum(A[ri][j]*x[j] for j in range(ci+1, cols))
                    x[ci] = -s

                from math import gcd
                def lcm(a,b): return a*b // gcd(a,b)
                den_lcm = 1
                for xi in x: den_lcm = lcm(den_lcm, xi.denominator)
                vals = [int(xi*den_lcm) for xi in x]
                if any(v<0 for v in vals): vals = [-v for v in vals]
                g = 0
                for v in vals: g = v if g==0 else gcd(g, v)
                if g>1: vals = [v//g for v in vals]

                L = vals[:len(left_list)]; R = vals[len(left_list):]
                return L, R, True

            def _parse_amounts_for_species(text, species_names):
                grams = {}; moles = {}
                for val, chem in re.findall(r"\b([0-9]*\.?[0-9]+)\s*g(?:rams?)?\s*([A-Za-z0-9()]+)", text, re.I):
                    if chem in species_names: grams[chem] = grams.get(chem, 0.0) + float(val)
                for chem, val in re.findall(r"\b([A-Za-z0-9()]+)\s*([0-9]*\.?[0-9]+)\s*g(?:rams?)?\b", text, re.I):
                    if chem in species_names: grams[chem] = grams.get(chem, 0.0) + float(val)
                for val, chem in re.findall(r"\b([0-9]*\.?[0-9]+)\s*mol(?:es?)?\s*([A-Za-z0-9()]+)", text, re.I):
                    if chem in species_names: moles[chem] = moles.get(chem, 0.0) + float(val)
                for chem, val in re.findall(r"\b([A-Za-z0-9()]+)\s*([0-9]*\.?[0-9]+)\s*mol(?:es?)?\b", text, re.I):
                    if chem in species_names: moles[chem] = moles.get(chem, 0.0) + float(val)
                for chem, val in re.findall(r"\bn\(\s*([A-Za-z0-9()]+)\s*\)\s*=\s*([0-9]*\.?[0-9]+)", text, re.I):
                    if chem in species_names: moles[chem] = moles.get(chem, 0.0) + float(val)
                return grams, moles

            # ================== parse the equation ==================
            eq_match = re.search(r"([A-Za-z0-9()+\s]+)(?:->|→)([A-Za-z0-9()+\s]+)", user_text)
            if eq_match:
                left_raw, right_raw = _parse_equation(eq_match.group(0))
            else:
                if all(w in user_text for w in ["H2","O2"]) and ("H2O" in user_text):
                    left_raw = [("H2", None), ("O2", None)]; right_raw = [("H2O", None)]
                elif ("Al" in user_text) and ("Cl2" in user_text) and ("AlCl3" in user_text):
                    left_raw = [("Al", None), ("Cl2", None)]; right_raw = [("AlCl3", None)]
                else:
                    raise ValueError("Please include a reaction like 'A + B -> C' or mention reactants & product (e.g., H2 + O2 -> H2O).")

            if not left_raw or not right_raw:
                raise ValueError("Could not parse the reaction. Please write it like '2 H2 + O2 -> 2 H2O'.")

            # Balance
            L_coeffs, R_coeffs, auto_bal = _balance(left_raw, right_raw)
            left_species  = [f for (f,_) in left_raw]
            right_species = [f for (f,_) in right_raw]

            # ================== collect amounts (reactants only) ==================
            grams_map, moles_map = _parse_amounts_for_species(user_text, set(left_species))
            if not grams_map and not moles_map:
                raise ValueError("Provide amounts for at least one reactant (e.g., '5.00 g H2' or '0.25 mol O2').")

            # molar masses
            molar = {}
            for sp in left_species + right_species:
                try:
                    molar[sp] = molar_mass(sp)
                except Exception:
                    counts = _elements_in_formula(sp)
                    molar[sp] = float(sum((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0) * cnt for el,cnt in counts.items()))

            # moles available for reactants
            n_avail = {}; step2_lines = []
            for sp in left_species:
                n = 0.0
                if sp in moles_map:
                    n += moles_map[sp]; step2_lines.append(f"• n({sp}) = {_fmt_num(moles_map[sp])} mol (given)")
                if sp in grams_map:
                    add = grams_map[sp] / molar[sp]; n += add
                    step2_lines.append(f"• n({sp}) += {_fmt_num(grams_map[sp])} g ÷ {_fmt_num(molar[sp])} g·mol⁻¹ = {_fmt_num(add)} mol")
                if n <= 0:
                    step2_lines.append(f"• n({sp}) = 0 mol (no amount provided)")
                n_avail[sp] = n

            # extents and limiting
            extents = []
            for sp, a in zip(left_species, L_coeffs):
                extents.append(n_avail[sp]/a if a>0 else 0.0)
            xi = min(extents)
            lr_index = extents.index(xi)
            limiting = left_species[lr_index]
            a_lim = L_coeffs[lr_index]
            n_lim_avail = n_avail[limiting]

            # target product = first product
            target_product = right_species[0]
            b_target = R_coeffs[0]
            n_prod = xi * b_target
            m_prod = n_prod * molar[target_product]

            # leftovers (for all reactants; we’ll display excess ones in Step 6)
            leftovers = []
            for sp, a in zip(left_species, L_coeffs):
                n_cons = xi * a
                n_left = max(0.0, n_avail[sp] - n_cons)
                m_left = n_left * molar[sp]
                leftovers.append((sp, a, n_cons, n_left, m_left))

            # ================== concise mode ==================
            if concise:
                en = f"Limiting reagent: {limiting}; theoretical yield ≈ {_fmt_num(m_prod)} g {target_product}."
                _say_or_show_en(en)

                gui = _format_gui_block(
                    question=command,
                    understanding="Limiting reagent & theoretical yield (concise).",
                    lines=[],
                    short_answer=en,
                    followups=[
                        "Show ICE table…",
                        "Compute excess left…",
                        "Theoretical yield from ξ…"
                    ]
                )
                _emit_gui(gui, intent="limiting_reagent", show_more=True, ctx=ctx, action="new")
                return gui

            # ================== build VERBOSE GUI ==================
            lines = []

            # Step 1 — Balance + counts + molar masses
            lines.append("Step 1 — Balance the equation & compute molar masses")
            start_eq = " + ".join([f for f,_ in left_raw]) + " → " + " + ".join([f for f,_ in right_raw])
            lines.append("")
            lines.append(f"Balancing (start with {start_eq}):")
            def _count_side(species, coeffs):
                tallies = {}
                for sp, c in zip(species, coeffs):
                    for el, cnt in _elements_in_formula(sp).items():
                        tallies[el] = tallies.get(el, 0) + cnt * c
                return tallies
            elements_all = sorted({el for f,_ in left_raw+right_raw for el in _elements_in_formula(f).keys()})
            start_L = _count_side([f for f,_ in left_raw], [1]*len(left_raw))
            start_R = _count_side([f for f,_ in right_raw], [1]*len(right_raw))
            fin_L   = _count_side(left_species, L_coeffs)
            fin_R   = _count_side(right_species, R_coeffs)
            for el in elements_all:
                l0 = start_L.get(el,0); r0 = start_R.get(el,0)
                lb = fin_L.get(el,0);   rb = fin_R.get(el,0)
                if l0 == r0:
                    lines.append(f"{el} count: left {l0}, right {r0} → already matched; balanced left {lb}, right {rb}.")
                else:
                    lines.append(f"{el} count: left {l0}, right {r0} → adjust via coefficients → balanced left {lb}, right {rb}.")
            def _fmt_side(species, coeffs):
                return " + ".join([f"{c} {sp}" if c!=1 else f"{sp}" for sp,c in zip(species, coeffs)])
            lines.append(f"Balanced: {_fmt_side(left_species, L_coeffs)} → {_fmt_side(right_species, R_coeffs)}")
            lines.append("")
            lines.append("Molar masses (from atomic masses):")
            for sp in left_species + right_species:
                counts = _elements_in_formula(sp)
                terms = []
                total = 0.0
                for el, cnt in sorted(counts.items()):
                    aw = float((_BY_SYMBOL.get(el.lower()) or {}).get("atomic_mass", 0.0))
                    total += aw*cnt
                    terms.append(f"{cnt} × {_fmt_num(aw)}" if cnt != 1 else f"{_fmt_num(aw)}")
                if len(terms) > 1:
                    lines.append(f"{sp} = " + " + ".join(t if "×" not in t else f"({t})" for t in terms) + f" = {_fmt_num(total)} g·mol⁻¹")
                else:
                    lines.append(f"{sp} = {terms[0]} = {_fmt_num(total)} g·mol⁻¹")
            lines.append("")

            # Step 2 — amounts to moles
            lines.append("Step 2 — Convert given masses to moles")
            lines.extend(step2_lines if step2_lines else ["• No amounts parsed."])
            lines.append("")

            # ---------STEP 3–---------
            if len(left_species) == 2 and len(R_coeffs) >= 1:
                coeff_hdr = f"{L_coeffs[0]}:{L_coeffs[1]}:{R_coeffs[0]}"
                lines.append(f"Step 3 — Stoichiometric requirement (use coefficients {coeff_hdr})")
                r1, r2 = left_species[0], left_species[1]
                a1, a2 = L_coeffs[0], L_coeffs[1]
                n1, n2 = n_avail[r1], n_avail[r2]
                need_r2_for_all_r1 = (a2/a1) * n1
                lines.append(
                    f"• {r2} needed for {_fmt_num(n1)} mol {r1} = "
                    f"({a2} {r2} / {a1} {r1}) × {_fmt_num(n1)} = "
                    f"({a2}/{a1}) × {_fmt_num(n1)} = {_fmt_num(need_r2_for_all_r1)} mol {r2}"
                )
                need_r1_for_all_r2 = (a1/a2) * n2
                lines.append(
                    f"• {r1} needed for {_fmt_num(n2)} mol {r2} = "
                    f"({a1} {r1} / {a2} {r2}) × {_fmt_num(n2)} = "
                    f"({a1}/{a2}) × {_fmt_num(n2)} = {_fmt_num(need_r1_for_all_r2)} mol {r1}"
                )
            else:
                lines.append("Step 3 — Stoichiometric requirement (use balanced coefficients)")
                for i, (spi, ai) in enumerate(zip(left_species, L_coeffs)):
                    for j, (spj, aj) in enumerate(zip(left_species, L_coeffs)):
                        if i == j: continue
                        need = (aj/ai) * n_avail[spi]
                        lines.append(
                            f"• {spj} needed for {_fmt_num(n_avail[spi])} mol {spi} = "
                            f"({aj} {spj} / {ai} {spi}) × {_fmt_num(n_avail[spi])} = "
                            f"({aj}/{ai}) × {_fmt_num(n_avail[spi])} = {_fmt_num(need)} mol {spj}"
                        )
            lines.append("")

            # Step 4 — Identify limiting reagent
            if len(left_species) == 2:
                other = left_species[1-lr_index]
                a_other = L_coeffs[1-lr_index]
                req_lim_for_all_other = (a_lim/a_other) * n_avail[other]
                lines.append("Step 4 — Identify the limiting reagent")
                lines.append(
                    f"Only {_fmt_num(n_lim_avail)} mol {limiting} available but "
                    f"{_fmt_num(req_lim_for_all_other)} mol {limiting} required to consume all {other} → {limiting} is limiting."
                )
            else:
                lines.append("Step 4 — Identify the limiting reagent")
                lines.append(f"Smallest extent controls progress: {_fmt_num(xi)} (from {limiting}) → {limiting} is limiting.")
            lines.append("")

            # Step 5 — Theoretical yield (with numeric fraction step)
            lines.append("Step 5 — Theoretical yield of product")
            lines.append(f"From limiting {limiting}: {limiting} → {R_coeffs[0]} {target_product}")
            n_prod_via_lim = (b_target / a_lim) * n_lim_avail
            lines.append(
                f"• n({target_product}) = ({b_target} {target_product} / {a_lim} {limiting}) × {_fmt_num(n_lim_avail)} = "
                f"({b_target}/{a_lim}) × {_fmt_num(n_lim_avail)} = {_fmt_num(n_prod_via_lim)} mol"
            )
            lines.append(
                f"• m({target_product}) = {_fmt_num(n_prod_via_lim)} × {_fmt_num(molar[target_product])} = "
                f"{_fmt_num(n_prod_via_lim * molar[target_product])} g"
            )
            lines.append("")

            # Step 6 — Leftover (excess reagent)
            lines.append("Step 6 — Leftover (excess reagent)")
            for sp, a, _n_cons, _n_left, _m_left in leftovers:
                if sp == limiting:
                    continue
                n_cons_via_lim = (a / a_lim) * n_lim_avail
                lines.append(
                    f"{sp} consumed = ({a} {sp} / {a_lim} {limiting}) × {_fmt_num(n_lim_avail)} = "
                    f"({a}/{a_lim}) × {_fmt_num(n_lim_avail)} = {_fmt_num(n_cons_via_lim)} mol"
                )
                left_mol = max(0.0, n_avail[sp] - n_cons_via_lim)
                lines.append(
                    f"{sp} left = {_fmt_num(n_avail[sp])} − {_fmt_num(n_cons_via_lim)} = {_fmt_num(left_mol)} mol → "
                    f"m = {_fmt_num(left_mol * molar[sp])} g"
                )
            lines.append("")

            # ✅ Answer (concise block in the popup)
            short_lines = [
                "✅ Answer",
                f"Limiting reagent: {limiting}",
                f"Theoretical yield: {_fmt_num(n_prod_via_lim * molar[target_product])} g {target_product}",
            ]
            excess = None
            if leftovers:
                ex = []
                for sp, a, _c, _l, _m in leftovers:
                    if sp == limiting: continue
                    n_left = max(0.0, n_avail[sp] - (a/a_lim)*n_lim_avail)
                    ex.append((sp, n_left * molar[sp]))
                if ex:
                    excess = max(ex, key=lambda t: t[1])
            if excess:
                short_lines.append(f"Leftover (excess): {_fmt_num(excess[1])} g {excess[0]}")

            followups = [
                "Compute percent yield from an actual yield",
                f"How many liters of {target_product}(g) at STP would that be?",
                "If I change one reactant amount, recompute everything",
            ]

            gui = _format_gui_block(
                question=user_text.strip(),
                understanding="Balance the equation → g→mol for each reactant → compare needs vs. available to find the limiting reagent → compute theoretical product → compute leftover.",
                lines=lines,
                short_answer="\n".join(short_lines),
                followups=followups
            )

            # 🔊 Adaptive speech
            speak_answer(target="Limiting reagent", value=limiting)
            speak_answer(target="Theoretical yield", value=_fmt_num(n_prod_via_lim * molar[target_product]), unit="grams")

            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            return gui


        # ---------- COMPARE ----------
        if intent == "compare":
            prop = normalize_property(user_text) or "boil"
            pair = extract_compare_targets(user_text)
            if not pair:
                raise ValueError("Please specify two elements to compare (e.g., 'Na vs K boiling point').")
            t1, t2 = pair
            e1, sug1 = resolve_element_any(t1)
            e2, sug2 = resolve_element_any(t2)
            if not e1 or not e2:
                raise ValueError(f"Couldn’t resolve both elements. Suggestions: {', '.join((sug1 or []) + (sug2 or [])) or '—'}")

            understanding, short, lines = answer_compare(prop, e1, e2)

            # Build dynamic follow-ups early so we can reuse them in concise mode too
            try:
                name1 = (e1.get("name") or e1.get("symbol") or "").strip()
                name2 = (e2.get("name") or e2.get("symbol") or "").strip()
            except Exception:
                name1 = e1.get("symbol", "")
                name2 = e2.get("symbol", "")

            follow_props = [
                "density", "melt", "boil", "electronegativity_pauling",
                "atomic_mass", "electron_affinity", "ionization_energies",
            ]
            dyn_followups = []
            for p in follow_props:
                if p == prop:
                    continue
                try:
                    label = _label(p)  # e.g., "Boiling point"
                    dyn_followups.append(f"Compare {label.lower()}: {name1} vs {name2}")
                except Exception:
                    continue
            dyn_followups = dyn_followups[:5] or [
                f"Compare density: {name1} vs {name2}",
                f"Compare melting point: {name1} vs {name2}",
            ]

            if concise:
                # Speak a natural concise line with reason
                unit = {
                    "atomic_mass": "u",
                    "density": "g/cm³",
                    "electronegativity_pauling": "",
                    "boil": "K",
                    "melt": "K",
                    "electron_affinity": "kJ/mol",
                    "ionization_energies": "kJ/mol",
                }.get(prop, "")
                v1 = _value_for_compare(prop, e1)
                v2 = _value_for_compare(prop, e2)
                prop_label = _label(prop).lower()
                n1 = (e1.get("name") or e1.get("symbol") or "").strip()
                n2 = (e2.get("name") or e2.get("symbol") or "").strip()
                def _possessive(s: str) -> str:
                    return f"{s}'" if s.endswith(("s", "S")) else f"{s}'s"
                s_v1 = f"{_fmt_num(v1)}{(' ' + unit) if unit else ''}"
                s_v2 = f"{_fmt_num(v2)}{(' ' + unit) if unit else ''}"
                msg = f"{short} because {n1} has a {prop_label} of {s_v1} compared to {_possessive(n2)} {s_v2}."
                say_ml(en=msg)

                # ✅ Concise now goes to the popup with ✦ + chips
                gui = _format_gui_block(
                    question=command,
                    understanding=understanding,
                    lines=[],                 # concise => keep body minimal
                    short_answer=msg,         # one-liner summary
                    followups=dyn_followups,  # ghost chips
                )
                _emit_gui(gui, intent="compare", show_more=True, ctx=ctx, action="new")

                CHEM_CTX["last_set"] = [e1, e2]
                CHEM_CTX["last_property"] = prop
                return gui

            # Verbose path → full explanation + proper emit
            gui = _format_gui_block(
                question=command,
                understanding=understanding,
                lines=[f"Property compared: **{_label(prop)}**", *lines],
                short_answer=short,
                followups=dyn_followups,
            )
            speak_answer(target=f"Comparison by {_label(prop)}", value=short)

            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            CHEM_CTX["last_set"] = [e1, e2]
            CHEM_CTX["last_property"] = prop
            return gui



                # ---------- LIST ----------
        if intent == "list":
            items = filter_by_category_like(user_text)
            if not items:
                raise ValueError("I couldn’t match a category/period/group.")

            title = "Filtered set"
            for k in list(_CATEGORIES_LOWER.keys()):
                if k in user_text.lower():
                    title = k.title()
                    break

            understanding, short, lines = answer_list(title, items)

            # Build a few intent-aware ghost chips
            try:
                name1 = (items[0].get("name") or items[0].get("symbol") or "").strip()
                name2 = (items[1].get("name") or items[1].get("symbol") or "").strip() if len(items) > 1 else ""
            except Exception:
                name1, name2 = "", ""

            dyn_followups = [
                "Sort by highest",
                (f"Compare {name1} vs {name2}" if (name1 and name2) else "Compare top two…"),
                "Show periodic trend",
            ]

            if concise:
                # 🔁 Speak NAMES instead of symbols (fallback to symbol if name missing)
                top_names = ", ".join([(e.get("name") or e.get("symbol") or "").strip() for e in items[:10]])
                msg_en = f"{title}: {top_names}" + ("…" if len(items) > 10 else "")
                say_ml(en=msg_en)

                # ✅ Concise → minimal popup + ✦ + chips
                gui = _format_gui_block(
                    question=command,
                    understanding=understanding,
                    lines=[],                 # keep concise body minimal
                    short_answer=msg_en,
                    followups=dyn_followups,  # ghost chips
                )
                _emit_gui(gui, intent="list", show_more=True, ctx=ctx, action="new")

                CHEM_CTX["last_set"] = items
                CHEM_CTX["last_property"] = None
                return gui

            # Verbose GUI block
            gui = _format_gui_block(
                question=command,
                understanding=understanding,
                lines=lines,
                short_answer=short,
                followups=dyn_followups or ["Which has highest melting point?", "Show only gases at STP"],
            )
            speak_answer(target=title or "Your list", value="shown")

            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            CHEM_CTX["last_set"] = items
            CHEM_CTX["last_property"] = None
            return gui


        # ---------- RANGE ----------
        if intent == "range":
            parsed = extract_range_query(user_text)
            if not parsed:
                raise ValueError("Please specify a property and threshold/interval.")
            prop, op, v1, v2, temp_prop = parsed

            def passes(e):
                val = e.get(prop)
                if val is None:
                    return False
                x = float(val)
                if op == "between":
                    return x >= v1 and x <= (v2 if v2 is not None else v1)
                if op == ">":
                    return x > v1
                if op == "<":
                    return x < v1
                if op == ">=":
                    return x >= v1
                if op == "<=":
                    return x <= v1
                if op == "=":
                    return abs(x - v1) < 1e-9
                return False

            res = [e for e in _ELEMENTS if passes(e)]
            title = f"{_label(prop)} {op} {v1}" + (f" to {v2}" if v2 is not None else "")

            understanding, short, rows = answer_list(title, res)

            # Notes + body lines (temperature normalization note if relevant)
            notes = []
            if temp_prop:
                notes.append("Note: temperature thresholds were normalized to **K** (Kelvin).")
            lines = notes + rows

            # ---------- Dynamic follow-ups (use for concise and verbose) ----------
            followups = ["Sort by highest"]
            if len(res) >= 2:
                a = (res[0].get("name") or res[0].get("symbol") or "").strip()
                b = (res[1].get("name") or res[1].get("symbol") or "").strip()
                try:
                    label = _label(prop).lower()  # e.g., "boiling point"
                except Exception:
                    label = "property"
                followups.insert(0, f"Compare {label}: {a} vs {b}")

            if concise:
                # 🔁 Speak NAMES instead of symbols (fallback to symbol if name missing)
                head = ", ".join([(e.get("name") or e.get("symbol") or "").strip() for e in res[:10]])
                msg_en = f"{len(res)} elements: {head}" + ("…" if len(res) > 10 else "")
                say_ml(en=msg_en)

                # ✅ Concise → minimal popup + ✦ + chips
                gui = _format_gui_block(
                    question=command,
                    understanding=understanding,
                    lines=[],                 # keep concise body minimal
                    short_answer=msg_en,
                    followups=followups,
                )
                _emit_gui(gui, intent="range", show_more=True, ctx=ctx, action="new")

                CHEM_CTX["last_set"] = res
                CHEM_CTX["last_property"] = prop
                return gui

            # Verbose GUI block
            gui = _format_gui_block(
                question=command,
                understanding=understanding,
                lines=lines,
                short_answer=short,
                followups=followups
            )
            speak_answer(target="Filtered elements", value="listed")

            _emit_gui(gui, intent=intent, show_more=_should_show_more(concise, intent, ctx), ctx=ctx, action="new")
            CHEM_CTX["last_set"] = res
            CHEM_CTX["last_property"] = prop
            return gui


        # ---------- PROPERTY or OVERVIEW ----------
        prop = normalize_property(user_text)
        target = None

        tok = re.findall(r"[A-Za-z][a-z]?", user_text)
        if tok:
            candidates = sorted(set(tok), key=len, reverse=True)
            for c in candidates:
                el, _sug = resolve_element_any(c)
                if el:
                    target = el
                    break

        if not target and ctx.get("last_element"):
            target_stub = ctx["last_element"]
            el, _ = resolve_element_any(
                target_stub.get("symbol") or target_stub.get("name") or str(target_stub.get("number"))
            )
            if el:
                target = el

        if not target:
            words = re.findall(r"\b[A-Z][a-z]?\w*\b", command)
            for w in words:
                el, _ = resolve_element_any(w)
                if el:
                    target = el
                    break

        if not target:
            words = re.findall(r"[A-Za-z][A-Za-z-]*", user_text.lower())
            suggs = []
            for w in words:
                _el, s = resolve_element_any(w)
                if s:
                    suggs.extend(s)
            suggs = list(dict.fromkeys(suggs))[:5]
            raise ValueError("I couldn’t find an element." + (f" Did you mean: {', '.join(suggs)}?" if suggs else ""))

        # Respect ✦ one-shot verbose + append if GUI sent it
        if ctx.get("force_verbose_once"):
            concise = False
        emit_action = ctx.get("ui_action", "new")

        if prop:
            understanding, short, lines = answer_property(target, prop)
            ctx["last_property"] = prop
            ctx["last_element"] = _mk_element_stub(target)

            if concise:
                # Voice-only (no actions for generic facts)
                val = target.get(prop)
                if prop in ("boil", "melt"):
                    unit = "K"
                elif prop == "density":
                    unit = "g/cm³"
                elif prop == "atomic_mass":
                    unit = "u"
                elif prop in ("electron_affinity", "ionization_energies"):
                    unit = "kJ/mol"
                    if prop == "ionization_energies":
                        arr = ensure_list(val)
                        val = arr[0] if arr else None
                else:
                    unit = ""
                num = _fmt_num(val)
                label_en = PROP_I18N.get(prop, {}).get("en", prop)
                line = f"{_short(target)} {label_en}: {num}" + (f" {unit}" if unit else "") + "."
                _say_or_show_en(line)
                return line

            # ---------- Dynamic follow-ups (PROPERTY path) ----------
            def _name_or_symbol(e):
                return (e.get("name") or e.get("symbol") or "").strip()

            counterpart_name = None
            counterpart_symbol = None

            last_set = ctx.get("last_set") or []
            if last_set:
                for _cand in last_set:
                    if (_cand.get("number") != target.get("number")):
                        counterpart_name = _name_or_symbol(_cand)
                        counterpart_symbol = _cand.get("symbol")
                        break

            if not counterpart_name and ctx.get("last_element"):
                le = ctx["last_element"]
                if (le.get("number") != target.get("number")):
                    counterpart_name = (le.get("name") or le.get("symbol") or "").strip()
                    counterpart_symbol = le.get("symbol")

            if not counterpart_name:
                try:
                    _na, _ = resolve_element_any("Na")
                    counterpart_name = (_na.get("name") or _na.get("symbol") or "Sodium").strip()
                    counterpart_symbol = _na.get("symbol") or "Na"
                except Exception:
                    counterpart_name = "Sodium"
                    counterpart_symbol = "Na"

            follow_props = [
                "density",
                "melt",
                "boil",
                "electronegativity_pauling",
                "atomic_mass",
                "electron_affinity",
                "ionization_energies",
            ]
            dyn_followups = []
            try:
                curr_label = _label(prop)
                dyn_followups.append(f"Compare {curr_label.lower()}: {_name_or_symbol(target)} vs {counterpart_name}")
            except Exception:
                pass
            for p in follow_props:
                if p == prop:
                    continue
                try:
                    label = _label(p)
                    dyn_followups.append(f"Compare {label.lower()}: {_name_or_symbol(target)} vs {counterpart_name}")
                except Exception:
                    continue
            dyn_followups = dyn_followups[:5]

            gui = _format_gui_block(
                question=command,
                understanding=understanding + f"\n🔎 Matched Element\n{_short(target)}, Atomic No. {target.get('number')}",
                lines=lines,
                short_answer=short,
                followups=dyn_followups or ["melting point?", "density?"]
            )

            # Voice (long-form)
            if prop in ("boil", "melt"):
                speak_answer(target=f"{_short(target)} {_label(prop)}", value=_fmt_num(target.get(prop)), unit="K")
            elif prop == "density":
                speak_answer(target=f"{_short(target)} {_label(prop)}", value=_fmt_num(target.get(prop)), unit="g/cm³")
            elif prop == "atomic_mass":
                speak_answer(target=f"{_short(target)} {_label(prop)}", value=_fmt_num(target.get(prop)), unit="u")
            elif prop == "ionization_energies":
                ie = ensure_list(target.get(prop))
                v = ie[0] if ie else None
                speak_answer(target=f"{_short(target)} {_label(prop)}", value=_fmt_num(v), unit="kJ/mol")
            elif prop == "electron_affinity":
                speak_answer(target=f"{_short(target)} {_label(prop)}", value=_fmt_num(target.get(prop)), unit="kJ/mol")
            else:
                speak_answer(target=f"{_short(target)} {_label(prop)}", value=str(target.get(prop)))

            # Generic fact ⇒ no ✦
            _emit_gui(gui, intent="property", show_more=False, ctx=ctx, action=emit_action)
            return gui

        # ---------- OVERVIEW ----------
        understanding, short, lines = answer_element_overview(target)
        ctx["last_property"] = None
        ctx["last_element"] = _mk_element_stub(target)

        if concise:
            # Voice-only (no actions)
            line = f"{target.get('name')} (#{target.get('number')}, {target.get('symbol')})."
            _say_or_show_en(line)
            return line

        # Dynamic follow-ups (OVERVIEW path)
        def _name_or_symbol(e):
            return (e.get("name") or e.get("symbol") or "").strip()

        counterpart_name = None
        last_set = ctx.get("last_set") or []
        if last_set:
            for _cand in last_set:
                if (_cand.get("number") != target.get("number")):
                    counterpart_name = _name_or_symbol(_cand)
                    break

        if not counterpart_name and ctx.get("last_element"):
            le = ctx["last_element"]
            if (le.get("number") != target.get("number")):
                counterpart_name = (le.get("name") or le.get("symbol") or "").strip()

        if not counterpart_name:
            try:
                _na, _ = resolve_element_any("Na")
                counterpart_name = (_na.get("name") or _na.get("symbol") or "Sodium").strip()
            except Exception:
                counterpart_name = "Sodium"

        follow_props = [
            "density",
            "melt",
            "boil",
            "electronegativity_pauling",
            "atomic_mass",
            "electron_affinity",
            "ionization_energies",
        ]
        dyn_followups = []
        for p in follow_props:
            try:
                label = _label(p)
                dyn_followups.append(f"Compare {label.lower()}: {_name_or_symbol(target)} vs {counterpart_name}")
            except Exception:
                continue
        dyn_followups = dyn_followups[:5]

        gui = _format_gui_block(
            question=command,
            understanding=understanding + f"\n🔎 Matched Element\n{_short(target)}, Atomic No. {target.get('number')}",
            lines=lines,
            short_answer=short,
            followups=dyn_followups or ["melting point?", "density?", "compare with Na"]
        )
        speak_answer(target=f"Overview of {target.get('name')}", value="ready")
        _emit_gui(gui, intent="overview", show_more=False, ctx=ctx, action=emit_action)
        return gui


    except Exception as e:
        msg = str(e)
        tip = _chem_mode_tip()

        if concise:
            _speak_multilang(
                en=f"I couldn’t complete that. Please add one more detail. {tip['en']}",
                hi=f"मैं यह पूरा नहीं कर सकी। कृपया थोड़ी और जानकारी दें। {tip['hi']}",
                fr=f"Je n’ai pas pu terminer. Ajoutez un détail de plus, s’il vous plaît. {tip['fr']}",
                es=f"No pude completarlo. Añade un detalle más, por favor. {tip['es']}",
                de=f"Ich konnte das nicht abschließen. Bitte gib noch ein Detail an. {tip['de']}",
            )
            return "I couldn’t complete that. Please add one more detail."

        gui = _format_gui_block(
            question=command,
            understanding="I ran into a problem understanding or solving this chemistry query.",
            lines=[msg, tip["en"]],
            short_answer="I couldn’t complete that. Try rephrasing or provide one more detail.",
            followups=_friendly_nudge_followups()
        )

        _speak_multilang(
            en=f"I couldn’t complete that. Please add one more detail. {tip['en']}",
            hi=f"मैं यह पूरा नहीं कर सकी। कृपया थोड़ी और जानकारी दें। {tip['hi']}",
            fr=f"Je n’ai pas pu terminer. Ajoutez un détail de plus, s’il vous plaît. {tip['fr']}",
            es=f"No pude completarlo. Añade un detalle más, por favor. {tip['es']}",
            de=f"Ich konnte das nicht abschließen. Bitte gib noch ein Detail an. {tip['de']}",
        )

        try:
            _emit_gui(gui, intent="error", show_more=False, ctx=ctx, action=ctx.get("ui_action","new"))
        except Exception:
            pass
        return gui
