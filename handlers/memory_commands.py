# 📂 handlers/memory_commands.py

import re
from memory_handler import save_to_memory, load_from_memory, clear_memory

# 🔍 Extract name from flexible user inputs
def extract_name(command: str):
    command = command.strip().lower()

    # Match known multilingual and fuzzy patterns
    patterns = [
        r"(?:my name is|i am|i’m|i am called|call me|je m'appelle|me llamo|ich heiße|mein name ist|मेरा नाम)\s+([a-zA-ZÀ-ÿ\u0900-\u097F]+)",
        r"(?:update|change|set)\s+(?:my\s+)?name\s+(?:to|as)?\s*([a-zA-ZÀ-ÿ\u0900-\u097F]+)",
        r"^\s*([a-zA-ZÀ-ÿ\u0900-\u097F]{3,})\s*$",  # just the name
    ]
    
    for pattern in patterns:
        match = re.search(pattern, command, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


# 🧠 Remember or Update Name
def handle_remember_name(command: str):
    from utils import _speak_multilang, logger

    name = extract_name(command)

    if name:
        save_to_memory("name", name)
        logger.info(f"🧠 Name remembered: {name}")

        # ✅ Consistent post-onboarding response:
        # Prefer the app's localized line; fall back to English-only if unavailable.
        try:
            from main import _say_name_set_localized  # speaks in current UI language
            _say_name_set_localized(name)
        except Exception:
            from utils import speak
            speak(f"Got it — I'll call you {name} from now on.")
    else:
        logger.warning("⚠️ Failed to extract name from command")
        _speak_multilang(
            "Sorry, I couldn't catch your name.",
            hi="माफ़ कीजिए, मैं आपका नाम नहीं समझ पाई।",
            fr="Désolée, je n'ai pas compris votre nom.",
            es="Lo siento, no entendí tu nombre.",
            de="Entschuldigung, ich habe deinen Namen nicht verstanden."
        )


# 🧠 Recall Name
def handle_recall_name(command: str):
    from utils import _speak_multilang, logger
    name = load_from_memory("name")
    if name:
        logger.info(f"🧠 Name recalled: {name}")
        _speak_multilang(
            f"Your name is {name}.",
            hi=f"आपका नाम {name} है।",
            fr=f"Votre nom est {name}.",
            es=f"Tu nombre es {name}.",
            de=f"Dein Name ist {name}."
        )
    else:
        logger.info("ℹ️ No name found in memory")
        _speak_multilang(
            "I don’t know your name yet. You can tell me by saying, 'My name is...'",
            hi="मुझे अभी आपका नाम नहीं पता। आप कह सकती हैं, 'मेरा नाम ... है'।",
            fr="Je ne connais pas encore votre nom. Vous pouvez me dire, 'Je m'appelle...'",
            es="Aún no sé tu nombre. Puedes decir, 'Me llamo...'",
            de="Ich kenne deinen Namen noch nicht. Du kannst sagen: 'Ich heiße...'"
        )


# 🧠 Store Preferences
def handle_store_preference(command: str):
    from utils import _speak_multilang, logger
    try:
        preference = re.sub(
            r"(i like|i love|my favorite|मुझे पसंद है|मेरा पसंदीदा|j'aime|mon préféré|me gusta|mi favorito|ich mag|mein lieblings)",
            "", command, flags=re.IGNORECASE).strip()

        if preference:
            save_to_memory("preference", preference)
            logger.info(f"🧠 Preference stored: {preference}")
            _speak_multilang(
                f"Got it! I'll remember that you like {preference}.",
                hi=f"समझ गई! मैं याद रखूंगी कि आपको {preference} पसंद है।",
                fr=f"Compris ! Je me souviendrai que vous aimez {preference}.",
                es=f"Entendido. Recordaré que te gusta {preference}.",
                de=f"Alles klar! Ich werde mir merken, dass du {preference} magst."
            )
        else:
            raise ValueError("Empty preference")

    except Exception as e:
        from utils import logger as _logger
        _logger.error(f"❌ Failed to store preference: {e}")
        _speak_multilang(
            "Sorry, I couldn't understand your preference.",
            hi="माफ़ कीजिए, मैं आपकी पसंद नहीं समझ पाई।",
            fr="Désolée, je n'ai pas compris votre préférence.",
            es="Lo siento, no entendí tu preferencia.",
            de="Entschuldigung, ich habe deine Vorliebe nicht verstanden."
        )


# 🧠 Clear Memory
def handle_clear_memory(command: str):
    from utils import _speak_multilang, logger
    try:
        if any(phrase in command for phrase in ["everything", "सब कुछ", "tout", "todo", "alles"]):
            clear_memory()
            logger.info("🧠 Cleared entire memory")
            _speak_multilang(
                "Memory cleared completely.",
                hi="सारी मेमोरी हटा दी गई है।",
                fr="La mémoire a été complètement effacée.",
                es="La memoria se ha borrado completamente.",
                de="Der gesamte Speicher wurde gelöscht."
            )
        else:
            key = None
            if any(k in command for k in ["name", "नाम", "nom", "nombre"]):
                key = "name"
            elif any(k in command for k in ["preference", "पसंद", "préférence", "preferencia", "Vorliebe"]):
                key = "preference"

            if key:
                clear_memory(key)
                logger.info(f"🧠 Cleared memory key: {key}")
                _speak_multilang(
                    f"I've forgotten your {key}.",
                    hi=f"मैंने आपकी {key} को भुला दिया है।",
                    fr=f"J'ai oublié votre {key}.",
                    es=f"He olvidado tu {key}.",
                    de=f"Ich habe deine {key} vergessen."
                )
            else:
                raise ValueError("Unknown key")

    except Exception as e:
        logger.error(f"❌ Error clearing memory: {e}")
        _speak_multilang(
            "Sorry, I couldn't clear the memory properly.",
            hi="माफ़ कीजिए, मैं मेमोरी साफ़ नहीं कर पाई।",
            fr="Désolée, je n'ai pas pu effacer la mémoire.",
            es="Lo siento, no pude borrar la memoria.",
            de="Entschuldigung, ich konnte den Speicher nicht löschen."
        )


# 📝 Note Delegates
def handle_take_note(command: str):
    from utils import logger
    from core_engine import process_command  # ✅ local import
    logger.info("📝 Delegating to core engine: create note")
    process_command(f"create note {command}")

def handle_read_notes(command: str):
    from utils import logger
    from core_engine import process_command  # ✅ local import
    logger.info("📖 Delegating to core engine: read notes")
    process_command("read notes")

def handle_delete_notes(command: str):
    from utils import logger
    from core_engine import process_command  # ✅ local import
    logger.info("❌ Delegating to core engine: delete note")
    process_command(f"delete note {command}")


# 🧠 Update Memory (name or preference)
def handle_update_memory(command: str):
    """
    Tries to update either the user's name or a preference.
    Examples:
      - "update my name to Alice"
      - "change my favorite to coffee"
      - "set my preference as lo-fi music"
      - "i like sushi" (falls back to store_preference)
    """
    from utils import _speak_multilang, logger

    cmd = command.strip()
    cmd_lower = cmd.lower()

    # 1) If the user mentions name → reuse the name handler
    if any(k in cmd_lower for k in ["name", "नाम", "nom", "nombre", "mein name", "je m'appelle", "me llamo", "ich heiße"]):
        # This also correctly handles "update my name to X"
        return handle_remember_name(cmd)

    # 2) Explicit preference update patterns
    m = re.search(
        r"(?:update|change|set)\s+(?:my\s+)?(?:favorite|preference)\s+(?:to|as)?\s*(.+)$",
        cmd, flags=re.IGNORECASE
    )
    if m:
        pref = m.group(1).strip()
        if pref:
            save_to_memory("preference", pref)
            logger.info(f"🧠 Preference updated: {pref}")
            return _speak_multilang(
                f"Done! I’ll remember you prefer {pref}.",
                hi=f"हो गया! मैं याद रखूंगी कि आपको {pref} पसंद है।",
                fr=f"C’est fait ! Je retiens que vous préférez {pref}.",
                es=f"¡Listo! Recordaré que prefieres {pref}.",
                de=f"Erledigt! Ich merke mir, dass du {pref} bevorzugst."
            )

    # 3) If the user phrased it like a liking statement → reuse preference handler
    like_triggers = (
        "i like", "i love", "my favorite",
        "मुझे पसंद है", "मेरा पसंदीदा",
        "j'aime", "mon préféré",
        "me gusta", "mi favorito",
        "ich mag", "mein lieblings"
    )
    if any(t in cmd_lower for t in like_triggers):
        return handle_store_preference(cmd)

    # 4) Couldn’t tell what to update
    _speak_multilang(
        "Tell me what to update — your name or a preference?",
        hi="मुझे बताइए क्या अपडेट करना है — आपका नाम या कोई पसंद?",
        fr="Dites-moi quoi mettre à jour — votre nom ou une préférence ?",
        es="Dime qué debo actualizar: tu nombre o alguna preferencia.",
        de="Sag mir, was ich aktualisieren soll — deinen Namen oder eine Vorliebe?"
    )
