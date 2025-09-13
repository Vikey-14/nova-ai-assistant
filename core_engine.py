# 📦 core_engine.py

import re
from difflib import get_close_matches

from command_registry import COMMAND_REGISTRY
from normalizer import normalize_hinglish
from command_map import COMMAND_MAP

# 🖼️ GUI popup helpers (thread-safe) + "show steps" detector
from gui_interface import show_mode_solution, append_mode_solution
ASK_STEPS_RE = re.compile(r"(show steps|explain|why|how|details|step by step)", re.I)

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


# =========================
# ✅ Physics confirm gating
# =========================

# Conservative explicit “graph it” intents across languages (avoid generic "show")
EXPLICIT_GRAPH_INTENT_RE = re.compile(
    r"(?i)\b("
    r"graph( it)?|plot( it)?|draw( it)?|diagram"
    r"|ग्राफ|ग्राफ़|प्लॉट|आरेख|बनाओ|बनाइए|दिखाओ|दिखाएँ"
    r"|diagramm|zeichnen"
    r"|graphe|graphique|tracer|dessine(r)?"
    r"|gráfico|gráfica|graficar|trazar|dibujar"
    r")\b"
)

def _physics_is_waiting() -> bool:
    """
    Checks if the physics handler is *currently* awaiting a yes/no/confirm for graphing.
    Tries multiple symbols for compatibility; safely returns False if unknown.
    """
    try:
        from handlers.physics_solver import is_graph_confirmation_open
        return bool(is_graph_confirmation_open())
    except Exception:
        pass
    try:
        from handlers.physics_solver import PHYSICS_CTX  # common pattern
        return bool(getattr(PHYSICS_CTX, "get", lambda *_: False)("awaiting_graph_confirmation"))
    except Exception:
        pass
    # Fallback: unknown state → treat as not waiting
    return False


# 🧠 Process user commands
def process_command(
    raw_command: str,
    is_math_override: bool = False,
    is_plot_override: bool = False,
    is_physics_override: bool = False,
    is_chemistry_override: bool = False,   # 🧪 NEW
):
    # ---- English-only name confirmation guard (pre-language-change) ----
    try:
        from main import (
            _PENDING_NAME_CONFIRM,
            _clear_pending_name_confirm,
            validate_name_strict,
            _accept_and_continue_with_name,
        )

        # Build YES/NO synonym sets from intents (use everything defined there)
        try:
            import intents as _int
            def _collect(name_list):
                out = []
                for nm in name_list:
                    if hasattr(_int, nm):
                        val = getattr(_int, nm)
                        if isinstance(val, (list, tuple, set)):
                            out.extend(val)
                        elif isinstance(val, str):
                            out.append(val)
                return out

            yes_syns = _collect([
                "YES_SYNONYMS", "YES_WORDS", "AFFIRMATIVE", "YES_TOKENS",
                "YES", "YES_LIST", "YES_VARIANTS"
            ])
            no_syns = _collect([
                "NO_SYNONYMS", "NO_WORDS", "NEGATIVE", "NO_TOKENS",
                "NO", "NO_LIST", "NO_VARIANTS"
            ])
        except Exception:
            yes_syns, no_syns = [], []

        YES_SET = {str(w).strip().lower() for w in yes_syns if str(w).strip()}
        NO_SET  = {str(w).strip().lower() for w in no_syns if str(w).strip()}
        # Always include the basics
        YES_SET.update({"yes", "y"})
        NO_SET.update({"no", "n"})

        txt_guard = (raw_command or "").strip()
        low = txt_guard.lower()

        # Normalize lightweight punctuation for equality/starts-with checks
        def _clean(s: str) -> str:
            # keep letters, numbers, spaces, common apostrophes/dashes, and Indic/Latin ranges
            s = re.sub(r"[^\w \-’'À-ÿ\u0900-\u097F]", " ", s, flags=re.UNICODE)
            s = re.sub(r"\s{2,}", " ", s).strip()
            return s.lower()

        low_clean = _clean(low)
        cand = _PENDING_NAME_CONFIRM.get("candidate") or ""

        # Helper: does the message equal or start with any token in the set?
        def _matches_token(token_set, text):
            if not token_set:
                return False
            for tok in token_set:
                if not tok:
                    continue
                t = _clean(tok)
                if not t:
                    continue
                if text == t or text.startswith(t + " "):
                    return True
            return False

        if _PENDING_NAME_CONFIRM.get("active") and not _PENDING_NAME_CONFIRM.get("handled"):
            # yes → accept candidate name via onboarding finisher (speaks English-only inside)
            if _matches_token(YES_SET, low_clean) and cand:
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_pending_name_confirm()
                _accept_and_continue_with_name(cand)
                return

            # "no, it's <name>" or "no it is <name>" (basic English form)
            m = re.search(r"(?i)^\s*no[\s,.:;-]+(?:it\s*'?s|it\s+is)\s+(.+)$", txt_guard)
            if m:
                proposed = m.group(1).strip(" \t:,-.'’")
                ok, cleaned, _ = validate_name_strict(proposed)
                if ok:
                    _PENDING_NAME_CONFIRM["handled"] = True
                    _clear_pending_name_confirm()
                    _accept_and_continue_with_name(cleaned)
                    return

            # plain/other "no" → mark handled; upstream flow will prompt for typed name
            if _matches_token(NO_SET, low_clean):
                _PENDING_NAME_CONFIRM["handled"] = True
                _clear_pending_name_confirm()
                return
    except Exception:
        pass

    from utils import _speak_multilang, log_interaction, selected_language
    current_lang = selected_language

    print(f"🎧 RAW: {raw_command}")
    command = normalize_hinglish(raw_command.lower().strip())
    print(f"✅ Normalized: {command}")
    log_interaction("command_received", command, current_lang)

    # 👀 Does the user explicitly want detailed steps/explanations?
    wants_steps = bool(ASK_STEPS_RE.search(command))

    # ⚡ physics follow-up (GATED):
    try:
        from handlers.physics_solver import handle_graph_confirmation
        if _physics_is_waiting() or EXPLICIT_GRAPH_INTENT_RE.search(command):
            if handle_graph_confirmation(command):
                return
    except Exception:
        pass

    # 🔢 Math Mode (UI override → centralized popup logic)
    if is_math_override:
        try:
            from handlers.symbolic_math_commands import handle_symbolic_math
            from handlers.basic_math_commands import handle_basic_math

            symbolic_keywords = [
                "differentiate", "derivative", "integrate", "limit", "solve",
                "matrix", "transpose", "eigen", "determinant", "inverse", "rank"
            ]

            if any(kw in command for kw in symbolic_keywords):
                handle_symbolic_math(command)   # popup inside handler
            else:
                handle_basic_math(command)      # popup inside handler
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

    # 🧪 Chemistry Mode (UI override)
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
                    if is_chemistry_override or wants_steps:
                        show_mode_solution("chemistry", final_chem_text)
                    else:
                        _speak_multilang(en=_quick_line(final_chem_text))
                return
            finally:
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

    # 🔘 Wake Mode Commands — set the flag only; the tray watcher controls the mic.
    if is_wake_toggle(command, WAKE_ON_COMMANDS):
        try:
            from utils import set_wake_mode, log_interaction
            set_wake_mode(True)
            log_interaction("wake_toggle", "enabled", get_lang())
        except Exception:
            pass
        _speak_multilang(
            en="Wake mode is now enabled.",
            hi="वेेक मोड चालू कर दिया गया है।",
            fr="Le mode d'écoute est activé.",
            de="Der Wachmodus ist jetzt aktiviert.",
            es="El modo de activación está habilitado."
        )
        return

    if is_wake_toggle(command, WAKE_OFF_COMMANDS):
        try:
            from utils import set_wake_mode, log_interaction
            set_wake_mode(False)
            log_interaction("wake_toggle", "disabled", get_lang())
        except Exception:
            pass
        _speak_multilang(
            en="Wake mode is now disabled.",
            hi="वेेक मोड बंद कर दिया गया है।",
            fr="Le mode d'écoute est désactivé.",
            de="Der Wachmodus ist deaktiviert.",
            es="El modo de activación está deshabilitado."
        )
        return


    # 🔎 Auto-route to Plot when keywords present or looks-plottable with Plot Mode ON
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

    # 🔍 Fuzzy final-chance router (before unrecognized fallback)
    try:
        from fuzzy_utils import best_command_key
        try:
            from command_registry import KEY_TO_HANDLER  # optional export
        except Exception:
            KEY_TO_HANDLER = {}

        key, phrase, score = best_command_key(command, COMMAND_MAP)

        # strong hit → execute directly
        if key in KEY_TO_HANDLER and score >= 0.86:
            print(f"✨ Fuzzy direct match: {key} via '{phrase}' (score={score:.2f})")
            log_interaction("fuzzy_match", f"{key}:{phrase}:{score:.2f}", current_lang)
            return KEY_TO_HANDLER[key](command)

        # near hit → ask for confirmation (prevents wrong actions)
        if key and score >= 0.70:
            print(f"❓ Fuzzy 'did you mean': {key} via '{phrase}' (score={score:.2f})")
            log_interaction("fuzzy_confirm", f"{key}:{phrase}:{score:.2f}", current_lang)
            _speak_multilang(
                en=f"Did you mean “{phrase}”?",
                hi=f"क्या आपका मतलब “{phrase}” था?",
                fr=f"Vouliez-vous dire « {phrase} » ?",
                es=f"¿Quisiste decir « {phrase} »?",
                de=f"Meintest du „{phrase}“?"
            )
            return
    except Exception as e:
        print(f"⚠️ Fuzzy fallback error: {e}")

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
