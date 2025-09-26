# command_registry.py

from __future__ import annotations

from typing import Callable
import importlib, re

from command_map import COMMAND_MAP
from utils import _speak_multilang, selected_language

# NEW: fuzzy matcher (tolerates joined words & small typos)
from fuzzy_utils import fuzzy_in

# === Checkbox modes (render to Solution Popup) ===
from handlers.basic_math_commands import handle_basic_math            # → popup "math"
from handlers.chemistry_solver import handle_chemistry_query          # → popup "chemistry"
from handlers.plot_commands import handle_plotting                    # → popup "plot"

# ⚛️ Physics
# OLD voice-confirm path used handle_graph_confirmation.
# NEW UX: direct “Plot it” action (button/voice) uses the last physics equation.
from handlers.physics_solver import (
    handle_physics_question,   # main physics → Solution Popup (with inline “Plot it”)
    on_plot_it_button,         # new follow-up entrypoint: plots last physics equation
)


# ── Prevent dates like 2025-08-26 or 12/09/2025 from triggering Math ──
_ISO_DATE_RE = re.compile(r'^\s*(?:19|20|21)\d{2}[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\s*$')
_DMY_DATE_RE = re.compile(r'^\s*(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/]((?:19|20|21)\d{2})\s*$')
_MDY_DATE_RE = re.compile(r'^\s*(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/]((?:19|20|21)\d{2})\s*$')

def _looks_like_standalone_date(cmd: str) -> bool:
    s = (cmd or "").strip()
    if any(pat.match(s) for pat in (_ISO_DATE_RE, _DMY_DATE_RE, _MDY_DATE_RE)):
        return True
    return False

# 🧮 Symbolic Math (derivatives/integrals/limits/linear algebra)
# If your project names this file differently, adjust the import below.
try:
    from handlers.symbolic_math_commands import handle_symbolic_math
except Exception:
    # Friendly no-op if symbolic math module isn't present
    def handle_symbolic_math(*_a, **_k):
        _speak_multilang(**{selected_language: "Symbolic math feature is unavailable right now."},
                         log_command="symbolic_math_missing")

# === Other domains (normal GUI pathways)
from handlers.pokemon_commands import is_pokemon_command, handle_pokemon_command
from handlers.news_commands import handle_news
from handlers.system_commands import handle_system_commands
from handlers.wiki_commands import handle_wikipedia
from handlers.date_commands import handle_date_queries
from handlers.holiday_commands import handle_holiday_queries

# === Memory / Notes / Reminders / Web shortcuts
from handlers.memory_commands import (
    handle_remember_name,
    handle_recall_name,
    handle_store_preference,
    handle_update_memory,
    handle_clear_memory,
)
from handlers.notes_commands import (
    create_note,
    read_notes,
    search_notes_by_keyword,
    update_note_handler,
    delete_note_handler,
)
from handlers.alarm_commands import (
    handle_set_alarm,
    handle_set_reminder,
)
from handlers.web_commands import (
    handle_open_youtube,
    handle_open_chatgpt,
    handle_search_google,
    handle_play_music,
)

# ────────────────────────────────────────────────────────────────
# 🌦️ Robust weather handler resolver (accepts several function names)
#     Avoids hard crashes if the function or file is renamed.
#     Also allows PyInstaller to bundle the module when added to hiddenimports.
# ────────────────────────────────────────────────────────────────
def _resolve_handler(module_name: str, candidates: tuple[str, ...], missing_msg: str):
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        def _stub(*_a, **_k):
            _speak_multilang(**{selected_language: "Weather module failed to import."},
                             log_command="weather_import_error")
        return _stub

    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn

    def _stub(*_a, **_k):
        _speak_multilang(**{selected_language: missing_msg},
                         log_command="weather_missing")
    return _stub

handle_weather = _resolve_handler(
    "handlers.weather_commands",
    ("handle_weather", "handle_weather_command", "get_weather", "process_weather", "fetch_weather"),
    "Weather feature is unavailable right now.",
)

# ────────────────────────────────────────────────────────────────
# 🔗 Command Registry container
# ────────────────────────────────────────────────────────────────
COMMAND_REGISTRY: list[tuple[Callable[[str], bool], Callable[[str], None]]] = []

# ────────────────────────────────────────────────────────────────
# 🧠 Memory (keep strict natural phrases; fuzzy not required here)
# ────────────────────────────────────────────────────────────────
def is_remember_name(command: str) -> bool:
    cmd = (command or "").lower()
    return any(p in cmd for p in ["my name is", "मेरा नाम", "je m'appelle", "me llamo", "ich heiße"])
COMMAND_REGISTRY.append((is_remember_name, handle_remember_name))

def is_recall_name(command: str) -> bool:
    cmd = (command or "").lower()
    return any(p in cmd for p in [
        "what is my name", "do you remember my name",
        "मेरा नाम क्या है", "tu te souviens de mon nom",
        "¿recuerdas mi nombre", "weißt du meinen namen"
    ])
COMMAND_REGISTRY.append((is_recall_name, handle_recall_name))

def is_store_preference(command: str) -> bool:
    cmd = (command or "").lower()
    return any(p in cmd for p in [
        "i like", "i love", "my favorite",
        "मुझे पसंद है", "मेरा पसंदीदा",
        "j'aime", "mon préféré",
        "me gusta", "mi favorito",
        "ich mag", "mein lieblings"
    ])
COMMAND_REGISTRY.append((is_store_preference, handle_store_preference))

def is_update_memory(command: str) -> bool:
    cmd = (command or "").lower()
    return any(p in cmd for p in ["update my", "change my", "बदलो", "modifie", "cambia", "ändere"])
COMMAND_REGISTRY.append((is_update_memory, handle_update_memory))

def is_clear_memory(command: str) -> bool:
    cmd = (command or "").lower()
    return any(p in cmd for p in [
        "forget", "clear memory", "erase memory",
        "याद मत रखो", "मेमोरी हटाओ",
        "efface", "oublie",
        "olvida", "borra memoria",
        "vergiss", "speicher löschen"
    ])
COMMAND_REGISTRY.append((is_clear_memory, handle_clear_memory))

# ────────────────────────────────────────────────────────────────
# 📝 Notes (additive fuzzy)
# ────────────────────────────────────────────────────────────────
def is_save_note(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("save_note", ["take a note", "note that", "लिखो", "noter", "notiz", "anotar"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_save_note, create_note))

def is_read_notes(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("read_notes", ["read notes", "show my notes", "मेरे नोट", "affiche mes notes", "zeige meine notizen", "mostrar mis notas"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_read_notes, read_notes))

def is_search_notes(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("search_notes", ["find note", "search note", "look for note", "नोट खोजें", "chercher", "buscar", "suche"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_search_notes, search_notes_by_keyword))

def is_update_note(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("update_note", ["update note", "change note", "edit note", "नोट अपडेट", "modifie la note", "cambiar nota", "notiz bearbeiten"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_update_note, update_note_handler))

def is_delete_note(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("delete_note", ["delete note", "remove note", "delete my note", "नोट हटाओ", "supprime", "borra", "lösche"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_delete_note, delete_note_handler))

# ────────────────────────────────────────────────────────────────
# ⏰ Alarm & Reminder (additive fuzzy)
# ────────────────────────────────────────────────────────────────
def is_set_alarm(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("set_alarm", ["set alarm", "alarm for", "wake me", "अलार्म", "réveille", "despiértame", "wecker"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_set_alarm, handle_set_alarm))

def is_set_reminder(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("set_reminder", ["remind me", "set reminder", "रिमाइंडर", "rappelle", "recuérdame", "erinnere"])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_set_reminder, handle_set_reminder))


# ────────────────────────────────────────────────────────────────
# 🐾 Pokémon (voice + typed)
# ────────────────────────────────────────────────────────────────
COMMAND_REGISTRY.append((is_pokemon_command, handle_pokemon_command))



# ────────────────────────────────────────────────────────────────
# 🌐 Web (additive fuzzy)
# ────────────────────────────────────────────────────────────────
def is_open_youtube(command: str) -> bool:
    cmd = (command or "").lower()
    # 🚫 Short-circuit so "open youtube and play ..." routes to play_music
    if "and play" in cmd:
        return False
    kws = COMMAND_MAP.get("open_youtube", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_open_youtube, handle_open_youtube))

def is_open_chatgpt(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("open_chatgpt", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_open_chatgpt, handle_open_chatgpt))

def is_search_google(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("search_google", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_search_google, handle_search_google))

def is_play_music(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("play_music", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_play_music, handle_play_music))

# ────────────────────────────────────────────────────────────────
# 📅 Date / 🏖️ Holidays (additive fuzzy for date; holidays keeps fallback too)
# ────────────────────────────────────────────────────────────────
def is_date_query(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("date_queries", [])
    return any(p in cmd for p in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_date_query, handle_date_queries))

def is_holiday_query(command: str) -> bool:
    cmd = (command or "").lower()
    if any(p in cmd for p in COMMAND_MAP.get("holiday_queries", [])) or \
       fuzzy_in(cmd, COMMAND_MAP.get("holiday_queries", [])):
        return True
    # fallback if not split out:
    holiday_terms = (
        # English
        "christmas", "diwali", "eid", "holiday", "new year",
        # French
        "noël", "férié",
        # Spanish
        "navidad", "feriado",
        # German
        "feiertag", "weihnachten",
        # Hindi (added)
        "क्रिसमस", "दिवाली", "ईद", "त्योहार", "छुट्टी", "नया साल"
    )
    return any(t in cmd for t in holiday_terms)

COMMAND_REGISTRY.append((is_holiday_query, handle_holiday_queries))


# ────────────────────────────────────────────────────────────────
# 🌦️ Weather / 🗞️ News / 📚 Wikipedia (additive fuzzy)
# ────────────────────────────────────────────────────────────────
def is_weather(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("get_weather", [])
    return any(p in cmd for p in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_weather, handle_weather))

def is_news(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("get_news", [])
    return any(p in cmd for p in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_news, handle_news))

def is_wikipedia_query(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("wiki_search", [])
    return any(p in cmd for p in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_wikipedia_query, handle_wikipedia))

# ────────────────────────────────────────────────────────────────
# 🖥️ System (SPLIT: strict power/exit vs fuzzy volume/brightness)
# ────────────────────────────────────────────────────────────────
def is_power_or_exit(command: str) -> bool:
    """STRICT: no fuzzy; avoids accidental destructive actions."""
    cmd = (command or "").lower()
    keywords = (
        COMMAND_MAP.get("shutdown_system", []) +
        COMMAND_MAP.get("restart_system", []) +
        COMMAND_MAP.get("sleep_system", []) +
        COMMAND_MAP.get("lock_system", []) +
        COMMAND_MAP.get("logout_system", []) +
        COMMAND_MAP.get("exit_app", [])
    )
    return any(kw in cmd for kw in keywords)

def is_volume_or_brightness(command: str) -> bool:
    """FUZZY: allow typos for safe adjustments."""
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("adjust_volume", []) + COMMAND_MAP.get("adjust_brightness", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws, cutoff=0.72, compact_cutoff=0.90)

# Order matters: strict first, then fuzzy V/B
COMMAND_REGISTRY.append((is_power_or_exit, handle_system_commands))
COMMAND_REGISTRY.append((is_volume_or_brightness, handle_system_commands))

# ────────────────────────────────────────────────────────────────
# 🧠 Symbolic Math (Derivatives, Integrals, Limits, Equations, Matrix Ops)
# → Solution Popup (channel "math")
#   (additive fuzzy on the base math_query keywords; feature words stay as-is)
# ────────────────────────────────────────────────────────────────
def is_symbolic_math(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("math_query", [])
    return (any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)) and (
        "differentiate" in cmd or "derivative" in cmd or
        "integrate" in cmd or "integral" in cmd or
        "solve" in cmd or "find x" in cmd or
        "limit" in cmd or "approaches" in cmd or
        "simplify" in cmd or "expand" in cmd or
        "with respect to" in cmd or "wrt" in cmd or
        "matrix" in cmd or "transpose" in cmd or
        "determinant" in cmd or "inverse" in cmd or
        "rank" in cmd or "eigenvalue" in cmd or
        "minor" in cmd or "cofactor" in cmd or
        "adjoint" in cmd
    )
COMMAND_REGISTRY.append((is_symbolic_math, handle_symbolic_math))

# ────────────────────────────────────────────────────────────────
# ➕ Math & Calculator (Basic + Advanced)
# → Solution Popup (channel "math")
# ────────────────────────────────────────────────────────────────
def is_math_query(command: str) -> bool:
    cmd = (command or "").lower().strip()

    # ⛔ guard: if it's a plain date string, don't treat as math
    if _looks_like_standalone_date(cmd):
        return False

    kws = COMMAND_MAP.get("math_query", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)


# ────────────────────────────────────────────────────────────────
# ⚛️ Physics Mode (units + equations)
# → Solution Popup (channel "physics")
#   (additive fuzzy on keyword list; your heuristic remains unchanged)
# ────────────────────────────────────────────────────────────────
def is_physics_query(command: str) -> bool:
    cmd = (command or "").lower()

    # (1) Primary: explicit keywords from COMMAND_MAP (augmented with fuzzy)
    if any(kw in cmd for kw in COMMAND_MAP.get("physics_query", [])) or \
       fuzzy_in(cmd, COMMAND_MAP.get("physics_query", [])):
        return True

    # (2) Fallback heuristic so “v = u + a*t” etc. still match
    has_equals = "=" in cmd
    phys_vars = any(x in cmd for x in [
        " v ", " u ", " a ", " s ", " t ", " f ", " m ", " r ",
        " theta", " omega", " alpha", " tau", " lambda", " rho", " phi",
        " ω", " α", " τ", " λ", " ρ", " φ"
    ])
    phys_units = any(u in cmd for u in [
        "m/s", "mps", "m/s^2", "m/s²", " n ", " newton", " kg", " j ", " joule",
        " w ", " pa", " kpa", " mpa", " bar", " atm", " mmhg",
        " c ", " v ", " a ", " ohm", " ω ", " °c", " celsius", " fahrenheit", " k ",
        " wb", " weber", " hz", " n·m", " n*m", " n.m", " rad", " deg"
    ])
    return (has_equals and phys_vars) or phys_units
COMMAND_REGISTRY.append((is_physics_query, handle_physics_question))

# ────────────────────────────────────────────────────────────────
# ✅ Physics follow-up: “plot it / graph it / yes / ok …”
#     → call the new on_plot_it_button() (uses last physics equation)
#     (Placed BEFORE generic plot command so “plot it” isn’t misrouted)
#     KEEP STRICT (no fuzzy) to avoid accidental confirms
# ────────────────────────────────────────────────────────────────
def is_graph_followup(command: str) -> bool:
    cmd = (command or "").strip().lower()
    confirm_list = COMMAND_MAP.get("physics_graph_confirm", [])
    if any(kw in cmd for kw in confirm_list):
        return True
    fallback = ("yes", "yeah", "yup", "ok", "okay", "sure",
                "graph it", "plot it", "please do", "show graph", "show the graph")
    return any(t == cmd or t in cmd for t in fallback)

def handle_plot_followup(_command: str) -> None:
    try:
        on_plot_it_button()
    except Exception:
        # swallow: physics may not have a last equation yet
        pass

COMMAND_REGISTRY.append((is_graph_followup, handle_plot_followup))

# ────────────────────────────────────────────────────────────────
# 📈 Plotting Commands (Symbolic, Physics, Custom)
# → Solution Popup (channel "plot")
# ────────────────────────────────────────────────────────────────
def is_plot_command(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("plot_command", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_plot_command, handle_plotting))

# ────────────────────────────────────────────────────────────────
# 🧪 Chemistry (calculations + quick facts)
# → Solution Popup (channel "chemistry")
#   (additive fuzzy on keyword list; lenient triggers remain)
# ────────────────────────────────────────────────────────────────
def is_chemistry_query(command: str) -> bool:
    cmd = (command or "").lower()
    if any(kw in cmd for kw in COMMAND_MAP.get("chemistry_query", [])) or \
       fuzzy_in(cmd, COMMAND_MAP.get("chemistry_query", [])):
        return True
    # Lenient patterns (e.g., “molar mass of H2SO4”, “pH of 0.10 M acid”)
    triggers = ("molar mass of", "molecular weight of", "ph of", "poh of", "pv=nrt", "stoichiometry")
    return any(t in cmd for t in triggers)
COMMAND_REGISTRY.append((is_chemistry_query, handle_chemistry_query))

def is_chemistry_fact(command: str) -> bool:
    cmd = (command or "").lower()
    kws = COMMAND_MAP.get("chemistry_fact", [])
    return any(kw in cmd for kw in kws) or fuzzy_in(cmd, kws)
COMMAND_REGISTRY.append((is_chemistry_fact, handle_chemistry_query))

# ────────────────────────────────────────────────────────────────
# 📤 Export a SAFE handler map for fuzzy fallback in core_engine
#   (Exclude destructive/system keys: shutdown/restart/sleep/lock/logout/exit)
# ────────────────────────────────────────────────────────────────
KEY_TO_HANDLER = {
    # Web & info
    "open_youtube": handle_open_youtube,
    "open_chatgpt": handle_open_chatgpt,
    "search_google": handle_search_google,
    "get_weather": handle_weather,
    "get_news": handle_news,
    "wiki_search": handle_wikipedia,
    "date_queries": handle_date_queries,

    # Notes / reminders (safe)
    "save_note": create_note,
    "read_notes": read_notes,
    "search_notes": search_notes_by_keyword,
    "update_note": update_note_handler,
    "delete_note": delete_note_handler,
    "set_alarm": handle_set_alarm,
    "set_reminder": handle_set_reminder,

    # Domain solvers (safe)
    "plot_command": handle_plotting,
    "math_query": handle_basic_math,
    "physics_query": handle_physics_question,
    "chemistry_query": handle_chemistry_query,
    "chemistry_fact": handle_chemistry_query,   # ← keep this

    # If you want: memory ops can be added too; generally safe:
    "remember_name": handle_remember_name,
    "recall_name": handle_recall_name,
    "store_preference": handle_store_preference,
    "update_memory": handle_update_memory,
    "clear_memory": handle_clear_memory,
}
