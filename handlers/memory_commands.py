# 📂 handlers/memory_commands.py — SAY→SHOW + typed/voice follow-ups + multilingual + barge-in

import re
from typing import Optional

from memory_handler import save_to_memory, load_from_memory, clear_memory

# Central SAY→SHOW and follow-ups
from say_show import say_show
from followup import await_followup
from utils import selected_language, listen_command, logger


# ─────────────────────────────────────────────────────────────────────────────
# Localization helpers
# ─────────────────────────────────────────────────────────────────────────────
def _lang() -> str:
    return (selected_language or "en").lower()

def _pick(d: dict) -> str:
    return d.get(_lang(), d.get("en", ""))

# Multilingual follow-up prompts / messages
_PROMPTS = {
    "ask_name": {
        "en": "What name should I remember? You can type or say it.",
        "hi": "मुझे कौन-सा नाम याद रखना चाहिए? आप टाइप करके या बोलकर बता सकते हैं।",
        "de": "Welchen Namen soll ich mir merken? Du kannst tippen oder sprechen.",
        "fr": "Quel nom dois-je mémoriser ? Vous pouvez écrire ou parler.",
        "es": "¿Qué nombre debo recordar? Puedes escribir o hablar.",
    },
    "ask_value": {
        "en": "What should I remember? You can type or say it.",
        "hi": "मुझे क्या याद रखना चाहिए? आप टाइप करके या बोलकर बता सकते हैं।",
        "de": "Was soll ich mir merken? Du kannst tippen oder sprechen.",
        "fr": "Que dois-je mémoriser ? Vous pouvez écrire ou parler.",
        "es": "¿Qué debo recordar? Puedes escribir o hablar.",
    },
    "ask_update_target": {
        "en": "Tell me what to update — your name or a preference?",
        "hi": "बताइए क्या अपडेट करना है — आपका नाम या कोई पसंद?",
        "de": "Was soll ich aktualisieren — deinen Namen oder eine Vorliebe?",
        "fr": "Que dois-je mettre à jour — votre nom ou une préférence ?",
        "es": "¿Qué debo actualizar: tu nombre o alguna preferencia?",
    },
    "ask_clear_which": {
        "en": "What should I forget — your name, a preference, or everything?",
        "hi": "क्या भूलना है — आपका नाम, कोई पसंद, या सब कुछ?",
        "de": "Was soll ich vergessen — deinen Namen, eine Vorliebe oder alles?",
        "fr": "Que dois-je oublier — votre nom, une préférence ou tout ?",
        "es": "¿Qué debo olvidar: tu nombre, una preferencia o todo?",
    },
    "didnt_get_it": {
        "en": "I couldn't get that.",
        "hi": "मैं समझ नहीं पाई।",
        "de": "Ich habe das nicht verstanden.",
        "fr": "Je n’ai pas compris.",
        "es": "No entendí eso.",
    },
}

def _say_then_show_prompt(key: str) -> str:
    """Speak all locales, then show the bubble in current UI language; return localized prompt text."""
    p = _PROMPTS[key]
    say_show(p["en"], hi=p.get("hi"), de=p.get("de"), fr=p.get("fr"), es=p.get("es"), title="Nova")
    return _pick(p)

def _say_msg(en: str, *, hi: str = "", de: str = "", fr: str = "", es: str = ""):
    """Helper to SAY→SHOW a one-off localized message."""
    say_show(en, hi=hi, de=de, fr=fr, es=es, title="Nova")


# ─────────────────────────────────────────────────────────────────────────────
# Name extraction (kept; minor guard tweaks)
# ─────────────────────────────────────────────────────────────────────────────
def extract_name(command: str) -> Optional[str]:
    command = (command or "").strip()
    patterns = [
        r"(?:\bmy\s+name\s+is\b|\bi\s+am\b|\bi’m\b|\bi\s+am\s+called\b|\bcall\s+me\b|je m'appelle|me llamo|ich heiße|mein name ist|मेरा नाम)\s+([a-zA-ZÀ-ÿ\u0900-\u097F][\wÀ-ÿ\u0900-\u097F\-']+)",
        r"(?:update|change|set)\s+(?:my\s+)?name\s+(?:to|as)?\s*([a-zA-ZÀ-ÿ\u0900-\u097F][\wÀ-ÿ\u0900-\u097F\-']+)",
        r"^\s*([A-Za-zÀ-ÿ\u0900-\u097F][\wÀ-ÿ\u0900-\u097F\-']{1,})\s*$",
    ]
    for pattern in patterns:
        m = re.search(pattern, command, flags=re.IGNORECASE)
        if m:
            name = (m.group(1) or "").strip()
            if name.lower() in {"yes", "no", "ok", "okay"}:
                continue
            return name
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Remember / Update Name (with follow-up if missing)
# ─────────────────────────────────────────────────────────────────────────────
def handle_remember_name(command: str):
    name = extract_name(command)

    if not name:
        prompt = _say_then_show_prompt("ask_name")
        answer = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,   # no re-TTS (we already said it)
            show_fn=lambda *_a, **_k: None,    # no duplicate bubble
            listen_fn=listen_command,          # barge-in handled inside await_followup
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not answer:
            p = _PROMPTS["didnt_get_it"]
            _say_msg(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
            return
        name = extract_name(answer) or (answer or "").strip()

    if not name:
        _say_msg(
            "Sorry, I couldn't catch your name.",
            hi="माफ़ कीजिए, मैं आपका नाम नहीं समझ पाई।",
            fr="Désolé, je n'ai pas compris votre nom.",
            es="Lo siento, no entendí tu nombre.",
            de="Entschuldigung, ich habe deinen Namen nicht verstanden.",
        )
        return

    save_to_memory("name", name)
    logger.info(f"🧠 Name remembered: {name}")
    # Localized confirmation (SAY→SHOW)
    _say_msg(
        f"Got it — I’ll call you {name} from now on.",
        hi=f"ठीक है — अब से मैं आपको {name} कहूँगी।",
        fr=f"D'accord — je vous appellerai {name} désormais.",
        es=f"Entendido — te llamaré {name} de ahora en adelante.",
        de=f"Alles klar — ich nenne dich ab jetzt {name}.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Recall Name
# ─────────────────────────────────────────────────────────────────────────────
def handle_recall_name(command: str):
    name = load_from_memory("name")
    if name:
        _say_msg(
            f"Your name is {name}.",
            hi=f"आपका नाम {name} है।",
            fr=f"Votre nom est {name}.",
            es=f"Tu nombre es {name}.",
            de=f"Dein Name ist {name}.",
        )
    else:
        _say_msg(
            "I don’t know your name yet. You can tell me by saying “My name is …”.",
            hi="मुझे अभी आपका नाम नहीं पता। आप कह सकती हैं, “मेरा नाम … है”。",
            fr="Je ne connais pas encore votre nom. Vous pouvez dire « Je m'appelle … ».",
            es="Aún no sé tu nombre. Puedes decir « Me llamo … ».",
            de="Ich kenne deinen Namen noch nicht. Du kannst sagen: „Ich heiße …“.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Store Preference (with follow-up if missing)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_preference_text(command: str) -> str:
    return re.sub(
        r"(i like|i love|my favorite|मुझे पसंद है|मेरा पसंदीदा|j'aime|mon préféré|me gusta|mi favorito|ich mag|mein lieblings)",
        "",
        command or "",
        flags=re.IGNORECASE,
    ).strip()

def handle_store_preference(command: str):
    try:
        preference = _extract_preference_text(command)

        if not preference:
            prompt = _say_then_show_prompt("ask_value")
            answer = await_followup(
                prompt,
                speak_fn=lambda *_a, **_k: None,
                show_fn=lambda *_a, **_k: None,
                listen_fn=listen_command,
                allow_typed=True, allow_voice=True, timeout=18.0
            )
            if not answer:
                p = _PROMPTS["didnt_get_it"]; _say_msg(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
                return
            preference = _extract_preference_text(answer) or (answer or "").strip()

        if not preference:
            raise ValueError("Empty preference")

        save_to_memory("preference", preference)
        logger.info(f"🧠 Preference stored: {preference}")
        _say_msg(
            f"Got it! I’ll remember that you like {preference}.",
            hi=f"समझ गई! मैं याद रखूँगी कि आपको {preference} पसंद है।",
            fr=f"Compris ! Je me souviendrai que vous aimez {preference}.",
            es=f"¡Entendido! Recordaré que te gusta {preference}.",
            de=f"Alles klar! Ich werde mir merken, dass du {preference} magst.",
        )

    except Exception as e:
        logger.error(f"❌ Failed to store preference: {e}")
        _say_msg(
            "Sorry, I couldn't understand your preference.",
            hi="माफ़ कीजिए, मैं आपकी पसंद नहीं समझ पाई।",
            fr="Désolé, je n'ai pas compris votre préférence.",
            es="Lo siento, no entendí tu preferencia.",
            de="Entschuldigung, ich habe deine Vorliebe nicht verstanden.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Clear Memory (with follow-up if unclear key)
# ─────────────────────────────────────────────────────────────────────────────
def handle_clear_memory(command: str):
    try:
        cmd = (command or "").lower()

        # Quick “everything” paths
        if any(phrase in cmd for phrase in ["everything", "सब कुछ", "tout", "todo", "alles"]):
            clear_memory()
            logger.info("🧠 Cleared entire memory")
            _say_msg(
                "Memory cleared completely.",
                hi="सारी मेमोरी हटा दी गई है।",
                fr="La mémoire a été complètement effacée.",
                es="La memoria se ha borrado completamente.",
                de="Der gesamte Speicher wurde gelöscht.",
            )
            return

        key = None
        if any(k in cmd for k in ["name", "नाम", "nom", "nombre"]):
            key = "name"
        elif any(k in cmd for k in ["preference", "पसंद", "préférence", "preferencia", "vorliebe"]):
            key = "preference"

        # Ask once if still unclear
        if not key:
            prompt = _say_then_show_prompt("ask_clear_which")
            ans = await_followup(
                prompt,
                speak_fn=lambda *_a, **_k: None,
                show_fn=lambda *_a, **_k: None,
                listen_fn=listen_command,
                allow_typed=True, allow_voice=True, timeout=18.0
            )
            if not ans:
                p = _PROMPTS["didnt_get_it"]; _say_msg(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
                return
            al = (ans or "").lower()
            if "name" in al or "नाम" in al or "nom" in al or "nombre" in al:
                key = "name"
            elif "preference" in al or "पसंद" in al or "préférence" in al or "preferencia" in al or "vorliebe" in al:
                key = "preference"
            elif "everything" in al or "सब कुछ" in al or "tout" in al or "todo" in al or "alles" in al:
                key = "everything"

        if key == "everything":
            clear_memory()
            logger.info("🧠 Cleared entire memory (via follow-up)")
            _say_msg(
                "Memory cleared completely.",
                hi="सारी मेमोरी हटा दी गई है।",
                fr="La mémoire a été complètement effacée.",
                es="La memoria se ha borrado completamente.",
                de="Der gesamte Speicher wurde gelöscht.",
            )
            return

        if key:
            clear_memory(key)
            logger.info(f"🧠 Cleared memory key: {key}")
            _say_msg(
                f"I've forgotten your {key}.",
                hi=f"मैंने आपकी {key} को भुला दिया है।",
                fr=f"J'ai oublié votre {key}.",
                es=f"He olvidado tu {key}.",
                de=f"Ich habe deine {key} vergessen.",
            )
        else:
            raise ValueError("Unknown key")

    except Exception as e:
        logger.error(f"❌ Error clearing memory: {e}")
        _say_msg(
            "Sorry, I couldn't clear the memory properly.",
            hi="माफ़ कीजिए, मैं मेमोरी साफ़ नहीं कर पाई।",
            fr="Désolé, je n'ai pas pu effacer la mémoire.",
            es="Lo siento, no pude borrar la memoria.",
            de="Entschuldigung, ich konnte den Speicher nicht löschen.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Note delegates (unchanged behavior; just logged)
# ─────────────────────────────────────────────────────────────────────────────
def handle_take_note(command: str):
    logger.info("📝 Delegating to core engine: create note")
    from core_engine import process_command
    process_command(f"create note {command}")

def handle_read_notes(command: str):
    logger.info("📖 Delegating to core engine: read notes")
    from core_engine import process_command
    process_command("read notes")

def handle_delete_notes(command: str):
    logger.info("❌ Delegating to core engine: delete note")
    from core_engine import process_command
    process_command(f"delete note {command}")


# ─────────────────────────────────────────────────────────────────────────────
# Update Memory (name or preference) — with follow-ups where needed
# ─────────────────────────────────────────────────────────────────────────────
def handle_update_memory(command: str):
    cmd = (command or "").strip()
    low = cmd.lower()

    # 1) Mentions of name across languages → reuse name path
    if any(k in low for k in ["name", "नाम", "nom", "nombre", "mein name", "je m'appelle", "me llamo", "ich heiße"]):
        return handle_remember_name(cmd)

    # 2) Explicit preference update patterns
    m = re.search(
        r"(?:update|change|set)\s+(?:my\s+)?(?:favorite|preference)\s+(?:to|as)?\s*(.+)$",
        cmd, flags=re.IGNORECASE
    )
    if m:
        pref = (m.group(1) or "").strip()
        if not pref:
            prompt = _say_then_show_prompt("ask_value")
            ans = await_followup(
                prompt,
                speak_fn=lambda *_a, **_k: None,
                show_fn=lambda *_a, **_k: None,
                listen_fn=listen_command,
                allow_typed=True, allow_voice=True, timeout=18.0
            )
            if not ans:
                p = _PROMPTS["didnt_get_it"]; _say_msg(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
                return
            pref = _extract_preference_text(ans) or (ans or "").strip()

        save_to_memory("preference", pref)
        logger.info(f"🧠 Preference updated: {pref}")
        _say_msg(
            f"Done! I’ll remember you prefer {pref}.",
            hi=f"हो गया! मैं याद रखूँगी कि आपको {pref} पसंद है।",
            fr=f"C’est fait ! Je retiens que vous préférez {pref}.",
            es=f"¡Listo! Recordaré que prefieres {pref}.",
            de=f"Erledigt! Ich merke mir, dass du {pref} bevorzugst.",
        )
        return

    # 3) “Liking” statements → reuse preference path
    like_triggers = (
        "i like", "i love", "my favorite",
        "मुझे पसंद है", "मेरा पसंदीदा",
        "j'aime", "mon préféré",
        "me gusta", "mi favorito",
        "ich mag", "mein lieblings",
    )
    if any(t in low for t in like_triggers):
        return handle_store_preference(cmd)

    # 4) Still unclear → ask what to update
    prompt = _say_then_show_prompt("ask_update_target")
    ans = await_followup(
        prompt,
        speak_fn=lambda *_a, **_k: None,
        show_fn=lambda *_a, **_k: None,
        listen_fn=listen_command,
        allow_typed=True, allow_voice=True, timeout=18.0
    )
    if not ans:
        p = _PROMPTS["didnt_get_it"]; _say_msg(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
        return
    al = ans.lower()
    if "name" in al or "नाम" in al or "nom" in al or "nombre" in al:
        return handle_remember_name("")     # triggers name follow-up
    if "preference" in al or "पसंद" in al or "préférence" in al or "preferencia" in al or "vorliebe" in al:
        return handle_store_preference("")  # triggers value follow-up

    p = _PROMPTS["didnt_get_it"]; _say_msg(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
