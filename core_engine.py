# 📦 core_engine.py

import re
from difflib import get_close_matches

from command_registry import COMMAND_REGISTRY
from normalizer import normalize_hinglish
from command_map import COMMAND_MAP

# 🖼️ GUI popup helpers (thread-safe) + "show steps" detector
from gui_interface import show_mode_solution, append_mode_solution
ASK_STEPS_RE = re.compile(r"(show steps|explain|why|how|details|step by step)", re.I)

# 🚦 Wake mode tracker
wake_mode_enabled = False

# 🌍 Multilingual wake toggle phrases
WAKE_ON_COMMANDS = {
    "en": ["enable wake mode", "start wake mode", "activate listening"],
    "hi": ["वेेक मोड शुरू करो", "सुनना चालू करो", "सुनना शुरू करो"],
    "fr": ["activer le mode d'écoute", "commencer le mode réveil", "écoute activée"],
    "de": ["wachmodus aktivieren", "hörmodus starten", "zuhören aktivieren"],
    "es": ["activar modo escucha", "iniciar modo de activación", "activar escuchar"]
}

WAKE_OFF_COMMANDS = {
    "en": ["stop listening", "disable wake mode", "exit wake mode"],
    "hi": ["सुनना बंद करो", "वेेक मोड बंद करो", "सुनना रोकें"],
    "fr": ["arrêter d'écouter", "désactiver le mode écoute", "quitter le mode réveil"],
    "de": ["hörmodus beenden", "wachmodus ausschalten", "nicht mehr zuhören"],
    "es": ["detener escucha", "desactivar modo escucha", "salir del modo de activación"]
}

# ✅ Helper to get current language
def get_lang():
    from utils import selected_language
    return selected_language

def is_wake_toggle(command: str, phrases: dict):
    return any(kw in command for kw in phrases.get(get_lang(), []))

# ✅ Start or stop wake listener with threading
def toggle_wake_mode(enable: bool):
    global wake_mode_enabled
    from utils import _speak_multilang, log_interaction, set_wake_mode
    from wake_word_listener import start_wake_listener_thread, stop_wake_listener_thread

    current_lang = get_lang()

    if enable and not wake_mode_enabled:
        wake_mode_enabled = True
        start_wake_listener_thread()
        set_wake_mode(True)
        print("✅ Wake mode ENABLED")
        _speak_multilang(
            en="Wake mode is now enabled.",
            hi="वेेक मोड चालू कर दिया गया है।",
            fr="Le mode d'écoute est activé.",
            de="Der Wachmodus ist jetzt aktiviert.",
            es="El modo de activación está habilitado."
        )
        log_interaction("wake_toggle", "enabled", current_lang)

    elif not enable and wake_mode_enabled:
        wake_mode_enabled = False
        stop_wake_listener_thread()
        set_wake_mode(False)
        print("🛑 Wake mode DISABLED")
        _speak_multilang(
            en="Wake mode is now disabled.",
            hi="वेेक मोड बंद कर दिया गया है।",
            fr="Le mode d'écoute est désactivé.",
            de="Der Wachmodus ist deaktiviert.",
            es="El modo de activación está deshabilitado."
        )
        log_interaction("wake_toggle", "disabled", current_lang)

    else:
        print("⚠️ Wake mode already in that state.")

# 🔹 Small helper for quick one-liners when checkbox = OFF
def _quick_line(final_text: str) -> str:
    if not isinstance(final_text, str):
        return ""
    for line in final_text.splitlines():
        s = line.strip()
        if s:
            return (s[:160] + "…") if len(s) > 160 else s
    return (final_text[:160] + "…") if len(final_text) > 160 else final_text


# ======================================================================
# 📈 Plot routing (multilingual keywords + “looks plottable” detection)
# ======================================================================

PLOT_KEYWORDS = {
    "en": ["plot", "graph", "draw", "show"],
    "hi": [
        "ग्राफ", "ग्राफ़", "आरेख", "प्लॉट",
        "चित्रित", "चित्र", "रेखाचित्र",
        "बनाओ", "बनाइए", "दिखाओ", "दिखाएँ"
    ],
    "de": [
        "plotten", "grafik", "diagramm", "diagramme",
        "zeichnen", "darstellen", "darstellung",
        "zeigen", "anzeigen"
    ],
    "fr": [
        "tracer", "graphe", "graphique", "diagramme",
        "dessine", "dessiner", "afficher", "montrer", "courbe"
    ],
    "es": [
        "graficar", "gráfico", "grafico", "gráfica", "grafica",
        "diagrama", "trazar", "dibujar", "mostrar"
    ],
}

def _build_plot_keywords_re():
    all_kw = []
    for lst in PLOT_KEYWORDS.values():
        all_kw.extend(lst)
    pattern = r"(?i)\b(" + "|".join(re.escape(k) for k in all_kw) + r")\b"
    return re.compile(pattern, re.UNICODE)

PLOT_KEYWORDS_RE = _build_plot_keywords_re()

def _looks_plottable(text: str) -> bool:
    """
    Heuristics to see if a string is likely a direct equation or data arrays.
    Used when Plot Mode checkbox is ON to allow keyword-less plotting.
    """
    t = (text or "").strip()
    # custom arrays: x=[...], y=[...]
    if re.search(r"[a-zA-Z_]\w*\s*=\s*\[[^\]]+\].*?[a-zA-Z_]\w*\s*=\s*\[[^\]]+\]", t):
        return True
    # simple equation var = expression with mathy cues
    m = re.search(r"\b([a-zA-Z_]\w*)\s*=\s*([^=]+)$", t)
    if not m:
        return False
    rhs = m.group(2)
    math_tokens = ("+", "-", "*", "/", "^", "**", "√", "sin", "cos", "tan", "log", "ln", "exp", "(", ")")
    if any(tok in rhs for tok in math_tokens):
        return True
    if re.search(r"\d\s*[a-zA-Z_]", rhs):  # e.g., 2x + 3
        return True
    return False

def _should_route_to_plot(user_text: str) -> bool:
    """
    Plot Mode OFF  -> only route if ANY multilingual keyword matches
    Plot Mode ON   -> keyword OR looks-plottable
    """
    txt = user_text or ""
    if PLOT_KEYWORDS_RE.search(txt):
        return True
    try:
        from utils import get_mode_state
        if get_mode_state("plot") and _looks_plottable(txt):
            return True
    except Exception:
        pass
    return False


# 🧠 Process user commands
def process_command(
    raw_command: str,
    is_math_override: bool = False,
    is_plot_override: bool = False,
    is_physics_override: bool = False,
    is_chemistry_override: bool = False,   # 🧪 NEW
):
    from utils import _speak_multilang, log_interaction, selected_language
    current_lang = selected_language

    print(f"🎧 RAW: {raw_command}")
    command = normalize_hinglish(raw_command.lower().strip())
    print(f"✅ Normalized: {command}")
    log_interaction("command_received", command, current_lang)

    # 👀 Does the user explicitly want detailed steps/explanations?
    wants_steps = bool(ASK_STEPS_RE.search(command))

    # ⚡ ultra-fast physics follow-up: “graph it / yes / ok …”
    # keep this FIRST so typed confirmations work with wake mode OFF
    try:
        from handlers.physics_solver import handle_graph_confirmation
        if handle_graph_confirmation(command):
            return
    except Exception as _:
        pass

    # 🔢 Math Mode (UI override → centralized popup logic)
    if is_math_override:
        # Use your two existing math handlers; they already push the popup
        try:
            from handlers.symbolic_math_commands import handle_symbolic_math
            from handlers.basic_math_commands import handle_basic_math

            symbolic_keywords = [
                "differentiate", "derivative", "integrate", "limit", "solve",
                "matrix", "transpose", "eigen", "determinant", "inverse", "rank"
            ]

            if any(kw in command for kw in symbolic_keywords):
                handle_symbolic_math(command)   # popup emitted inside the handler
            else:
                handle_basic_math(command)      # popup emitted inside the handler
            return

        except Exception as e:
            print(f"❌ Math Mode error: {e}")
            _speak_multilang(
                en="There was a problem processing your math request.",
                hi="आपके गणितीय अनुरोध को संसाधित करते समय कोई समस्या हुई।",
                fr="Un problème est survenu lors du traitement de votre requête mathématique.",
                es="Hubo un problema al procesar tu solicitud matemática.",
                de="Bei der Verarbeitung deiner mathematischen Anfrage ist ein Fehler aufgetreten."
            )
            return
    
    # 📈 Plot Mode (UI override → centralized popup logic)
    if is_plot_override:
        try:
            from handlers.plot_commands import handle_plotting
            final_plot_text = handle_plotting(command)  # Graph UI handled inside
            if isinstance(final_plot_text, str) and final_plot_text.strip():
                if is_plot_override or wants_steps:
                    show_mode_solution("plot", final_plot_text)
                else:
                    _speak_multilang(en=_quick_line(final_plot_text))
            return
        except Exception as e:
            print(f"❌ Plot Mode error: {e}")
            _speak_multilang(
                en="There was a problem plotting your expression.",
                hi="आपके प्लॉट अनुरोध में समस्या हुई।",
                fr="Un problème est survenu lors de la création du graphique.",
                es="Hubo un problema al trazar tu expresión.",
                de="Beim Plotten deines Ausdrucks ist ein Fehler aufgetreten."
            )
            return

    # ⚛️ Physics Mode (UI override → centralized popup logic)
    if is_physics_override:
        try:
            from handlers.physics_solver import handle_physics_question
            final_physics_text = handle_physics_question(command)

            if isinstance(final_physics_text, str) and final_physics_text.strip():
                if is_physics_override or wants_steps:
                    show_mode_solution("physics", final_physics_text)
                else:
                    _speak_multilang(en=_quick_line(final_physics_text))
            return
        except Exception as e:
            print(f"❌ Physics Mode error: {e}")
            _speak_multilang(
                en="There was a problem solving your physics question.",
                hi="आपके भौतिकी प्रश्न को हल करते समय समस्या हुई।",
                fr="Un problème est survenu lors de la résolution de votre question de physique.",
                es="Hubo un problema al resolver tu pregunta de física.",
                de="Beim Lösen deiner Physikfrage ist ein Problem aufgetreten."
            )
            return

    # 🧪 Chemistry Mode (UI override) — force full GUI steps, keep your prior state logic
    if is_chemistry_override:
        try:
            from handlers.chemistry_solver import handle_chemistry_query
            # Temporarily force chemistry mode ON via utils (if available)
            prev_state = None
            try:
                from utils import get_mode_state, set_mode_state
                prev_state = get_mode_state("chemistry") if callable(get_mode_state) else None
                if callable(set_mode_state):
                    set_mode_state("chemistry", True)
            except Exception:
                prev_state = None
            try:
                final_chem_text = handle_chemistry_query(command)
                if isinstance(final_chem_text, str) and final_chem_text.strip():
                    # Chemistry checkbox ON always shows popup; "wants_steps" also qualifies
                    if is_chemistry_override or wants_steps:
                        show_mode_solution("chemistry", final_chem_text)
                    else:
                        _speak_multilang(en=_quick_line(final_chem_text))
                return
            finally:
                # Restore previous state to avoid side effects
                try:
                    from utils import set_mode_state
                    if prev_state is not None and callable(set_mode_state):
                        set_mode_state("chemistry", prev_state)
                except Exception:
                    pass
        except Exception as e:
            print(f"❌ Chemistry Mode error: {e}")
            _speak_multilang(
                en="There was a problem solving your chemistry question.",
                hi="आपके रसायन विज्ञान प्रश्न को हल करते समय समस्या हुई।",
                fr="Un problème est survenu lors de la résolution de votre question de chimie.",
                es="Hubo un problema al resolver tu pregunta de química.",
                de="Beim Lösen deiner Chemiefrage ist ein Problem aufgetreten."
            )
            return

    # 🔁 Command chaining (keeps overrides for each part)
    chaining_keywords = [" and ", " और ", " et ", " y ", " und "]
    for keyword in chaining_keywords:
        if keyword in command:
            parts = command.split(keyword)
            for part in parts:
                if part.strip():
                    print(f"🔗 Chained Part: {part.strip()}")
                    process_command(
                        part.strip(),
                        is_math_override=is_math_override,
                        is_plot_override=is_plot_override,
                        is_physics_override=is_physics_override,
                        is_chemistry_override=is_chemistry_override,
                    )
            return

    # 🔘 Wake Mode Commands
    if is_wake_toggle(command, WAKE_ON_COMMANDS):
        toggle_wake_mode(True)
        return
    if is_wake_toggle(command, WAKE_OFF_COMMANDS):
        toggle_wake_mode(False)
        return

    # 🔎 Auto-route to Plot when keywords present (any language),
    #     or when Plot Mode is ON and the input looks like an equation/arrays.
    try:
        if _should_route_to_plot(command):
            from handlers.plot_commands import handle_plotting
            handle_plotting(command)  # Graph preview & save handled inside
            return
    except Exception as e:
        print(f"⚠️ Plot routing error: {e}")

    # ✅ Registered handlers (first match wins)
    for matcher, handler in COMMAND_REGISTRY:
        try:
            if matcher(command):
                print(f"✅ Matched handler: {handler.__name__}")
                log_interaction("handler_match", handler.__name__, current_lang)
                return handler(command)
        except Exception as e:
            print(f"❌ Error in handler {handler.__name__}: {e}")
            log_interaction("handler_error", str(e), current_lang)
            _speak_multilang(
                en="Something went wrong while executing your command.",
                hi="आपका आदेश पूरा करते समय कोई त्रुटि हुई है।",
                fr="Une erreur s'est produite lors de l'exécution de votre commande.",
                es="Se produjo un error al ejecutar tu comando.",
                de="Beim Ausführen deiner Befehls ist ein Fehler aufgetreten."
            )
            return

    # 🤷 Fallback
    _speak_multilang(
        en="Sorry, I don't recognize that command yet.",
        hi="माफ़ कीजिए, मैं अभी उस आदेश को नहीं समझ पाई।",
        fr="Désolée, je ne reconnais pas encore cette commande.",
        es="Lo siento, no reconozco ese comando todavía.",
        de="Entschuldigung, ich erkenne diesen Befehl noch nicht."
    )
    log_interaction("fallback_unrecognized", command, current_lang)

# 🚀 Optional CLI loop
def run_nova():
    from utils import speak, listen_command, log_interaction
    speak("Hello! I’m Nova, your AI assistant. I’m online and ready to help you.")
    log_interaction("startup", "Nova launched via run_nova()", "en")
    while True:
        command = listen_command()
        if command:
            process_command(command)
