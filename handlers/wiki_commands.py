# 📂 handlers/wiki_commands.py

import re
import wikipedia
from difflib import get_close_matches
from command_map import COMMAND_MAP

def handle_wikipedia(command: str) -> None:
    # ✅ Lazy imports to avoid circular refs
    from utils import _speak_multilang, log_interaction, selected_language, speak, listen_command
    from gui_interface import nova_gui

    # Follow-up bridge is in the project root (not utils/)
    try:
        from followup import await_followup
        HAS_FOLLOWUP = True
    except Exception:
        await_followup = None
        HAS_FOLLOWUP = False

    cmd = (command or "").strip()
    wiki_phrases = COMMAND_MAP.get("wiki_search", [])
    matched_wiki = get_close_matches(cmd, wiki_phrases, n=1, cutoff=0.6)

    # If it doesn't look like a wiki request, just return silently.
    if not matched_wiki:
        return

    # ─────────────────────────────────────────────────────────────
    # 🌍 Language override parsing (“in Hindi / हिंदी में / en français / en español / auf deutsch”)
    # If not found, default to session selected_language (expected: 'en', 'hi', 'fr', 'es', 'de')
    # ─────────────────────────────────────────────────────────────
    lang_overrides = {
        # English
        r"\bin\s+hindi\b": "hi",
        r"\bin\s+spanish\b": "es",
        r"\bin\s+french\b": "fr",
        r"\bin\s+german\b": "de",
        # Localized forms
        r"\bहिंदी में\b": "hi",
        r"\ben français\b": "fr",
        r"\ben español\b": "es",
        r"\bauf deutsch\b": "de",
        # Short variants
        r"\bin\s+es\b": "es",
        r"\bin\s+fr\b": "fr",
        r"\bin\s+de\b": "de",
        r"\bin\s+hi\b": "hi",
    }

    wiki_lang = selected_language
    for pat, lang_code in lang_overrides.items():
        if re.search(pat, cmd, flags=re.I):
            wiki_lang = lang_code
            # Remove the override phrase so it doesn't pollute the topic text.
            cmd = re.sub(pat, "", cmd, flags=re.I).strip()

    # ─────────────────────────────────────────────────────────────
    # 🔍 Extract the topic by stripping trigger words in multiple languages
    # E.g. "what is graphene", "who is Newton", "qu'est-ce que la photosynthèse", etc.
    # ─────────────────────────────────────────────────────────────
    trigger_re = (
        r"(?:^|\b)("
        r"what is|who is|define|tell me about|"
        r"क्या है|कौन है|"
        r"qu'est-ce que|qui est|"
        r"qué es|quién es|"
        r"was ist|wer ist"
        r")\b"
    )
    topic = re.sub(trigger_re, "", cmd, flags=re.IGNORECASE).strip()
    topic = re.sub(r"^(of|about|:|-)\s+", "", topic, flags=re.I).strip()

    # If still empty → ask a follow-up (typed or voice)
    if not topic:
        prompt_map = {
            "en": "What should I look up on Wikipedia? You can type or say it.",
            "hi": "विकिपीडिया पर क्या देखूँ? आप टाइप कर सकते हैं या बोल सकते हैं।",
            "fr": "Que veux-tu que je recherche sur Wikipédia ? Tu peux écrire ou parler.",
            "es": "¿Qué debo buscar en Wikipedia? Puedes escribir o hablar.",
            "de": "Was soll ich auf Wikipedia nachschlagen? Du kannst tippen oder sprechen.",
        }
        prompt = prompt_map.get(selected_language, prompt_map["en"])

        def _show(who, text):
            try:
                nova_gui.show_message(who, text)
            except Exception:
                pass

        # Speak → Show
        try:
            speak(prompt)
        except Exception:
            pass
        _show("Nova", prompt)

        if HAS_FOLLOWUP and await_followup:
            topic = await_followup(
                prompt,
                speak_fn=speak,
                show_fn=_show,
                listen_fn=listen_command,
                allow_typed=True,
                allow_voice=True,
                timeout=18.0
            )
            topic = (topic or "").strip()
        else:
            try:
                heard = listen_command()
                topic = (heard or "").strip()
            except Exception:
                topic = ""

        if not topic:
            _speak_multilang(
                "Please specify what you want to know.",
                hi="कृपया बताइए कि आप क्या जानना चाहते हैं।",
                fr="Veuillez préciser ce que vous souhaitez savoir.",
                es="Por favor, especifica qué deseas saber.",
                de="Bitte sag mir, was du wissen möchtest."
            )
            return

    # ─────────────────────────────────────────────────────────────
    # 🌐 Query Wikipedia (with disambiguation follow-up handling)
    # ─────────────────────────────────────────────────────────────
    try:
        wikipedia.set_lang(wiki_lang)
        summary = wikipedia.summary(topic, sentences=4)

        # Localized header
        header_map = {
            "en": "📚 Wikipedia",
            "hi": "📚 विकिपीडिया",
            "fr": "📚 Wikipédia",
            "es": "📚 Wikipedia",
            "de": "📚 Wikipedia",
        }
        header_label = header_map.get(selected_language, header_map["en"])
        header = f"{header_label} • {topic} ({wiki_lang.upper()})"

        # Show → Speak
        try:
            nova_gui.show_message("Nova", header)
            nova_gui.show_message("Nova", summary)
        except Exception:
            pass

        _speak_multilang(summary, log_command=f"Wiki summary for: {topic}")

    except wikipedia.exceptions.DisambiguationError as e:
        # Offer a small set to choose from
        options = list(e.options or [])[:5]
        if not options:
            _speak_multilang(
                "That topic is too broad. Try something more specific.",
                hi="यह विषय बहुत व्यापक है। कृपया कुछ और विशिष्ट बताइए।",
                fr="Ce sujet est trop vaste. Essaie quelque chose de plus précis.",
                es="Ese tema es demasiado amplio. Intenta con algo más específico.",
                de="Dieses Thema ist zu allgemein. Versuche bitte etwas Konkreteres."
            )
            return

        # Localized “multiple results” header
        multi_header_map = {
            "en": f"Multiple results for “{topic}”:",
            "hi": f"“{topic}” के लिए कई परिणाम:",
            "fr": f"Plusieurs résultats pour « {topic} » :",
            "es": f"Varios resultados para «{topic}»:",
            "de": f"Mehrere Ergebnisse für „{topic}“:",
        }
        multi_header = multi_header_map.get(selected_language, multi_header_map["en"])

        choices_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
        try:
            nova_gui.show_message("Nova", f"{multi_header}\n{choices_text}")
        except Exception:
            pass

        ask_pick_map = {
            "en": "I found multiple pages. Say or type a number (1–5), or say cancel.",
            "hi": "कई पेज मिले। 1–5 में से नंबर बोलें/टाइप करें, या कैंसिल कहें।",
            "fr": "Plusieurs pages trouvées. Dis ou tape un numéro (1–5), ou dis annuler.",
            "es": "Encontré varias páginas. Di o escribe un número (1–5), o di cancelar.",
            "de": "Es gibt mehrere Treffer. Sag oder tippe eine Zahl (1–5) oder sag abbrechen.",
        }
        ask_pick = ask_pick_map.get(selected_language, ask_pick_map["en"])

        def _show(who, text):
            try:
                nova_gui.show_message(who, text)
            except Exception:
                pass

        # Speak → Show
        try:
            speak(ask_pick)
        except Exception:
            pass
        _show("Nova", ask_pick)

        # Get a typed/voice choice
        if HAS_FOLLOWUP and await_followup:
            reply = await_followup(
                ask_pick,
                speak_fn=speak,
                show_fn=_show,
                listen_fn=listen_command,
                allow_typed=True,
                allow_voice=True,
                timeout=18.0
            )
            reply = (reply or "").strip().lower()
        else:
            try:
                reply = (listen_command() or "").strip().lower()
            except Exception:
                reply = ""

        if not reply or any(w in reply for w in ["cancel", "कैंसिल", "annule", "cancelar", "abbrechen"]):
            _speak_multilang(
                "Okay, cancelled.",
                hi="ठीक है, रद्द कर दिया।",
                fr="D’accord, j’annule.",
                es="De acuerdo, cancelado.",
                de="Okay, abgebrochen."
            )
            return

        m = re.search(r"\d+", reply)
        if not m:
            _speak_multilang(
                "Sorry, I didn’t understand the number.",
                hi="माफ़ कीजिए, मैं नंबर नहीं समझ पाई।",
                fr="Désolé, je n’ai pas compris le numéro.",
                es="Lo siento, no entendí el número.",
                de="Entschuldigung, ich habe die Zahl nicht verstanden."
            )
            return

        idx = int(m.group())
        if not (1 <= idx <= len(options)):
            _speak_multilang(
                "That number is out of range.",
                hi="वह संख्या सीमा से बाहर है।",
                fr="Ce numéro est hors de portée.",
                es="Ese número está fuera de rango.",
                de="Diese Nummer ist außerhalb des gültigen Bereichs."
            )
            return

        # Fetch the chosen page
        chosen = options[idx - 1]
        try:
            summary = wikipedia.summary(chosen, sentences=4)

            header_map = {
                "en": "📚 Wikipedia",
                "hi": "📚 विकिपीडिया",
                "fr": "📚 Wikipédia",
                "es": "📚 Wikipedia",
                "de": "📚 Wikipedia",
            }
            header_label = header_map.get(selected_language, header_map["en"])
            header = f"{header_label} • {chosen} ({wiki_lang.upper()})"

            try:
                nova_gui.show_message("Nova", header)
                nova_gui.show_message("Nova", summary)
            except Exception:
                pass

            _speak_multilang(summary, log_command=f"Wiki summary for: {chosen}")

        except Exception as e2:
            _speak_multilang(
                "I couldn’t fetch the selected page.",
                hi="मैं चुने गए पेज को नहीं ला पाई।",
                fr="Je n’ai pas pu récupérer la page sélectionnée.",
                es="No pude obtener la página seleccionada.",
                de="Ich konnte die ausgewählte Seite nicht abrufen."
            )
            log_interaction("wiki_error", str(e2), selected_language)

    except wikipedia.exceptions.PageError:
        _speak_multilang(
            "I couldn't find anything on Wikipedia about that.",
            hi="मैं विकिपीडिया पर उस विषय के बारे में कुछ नहीं ढूँढ पाई।",
            fr="Je n’ai rien trouvé à ce sujet sur Wikipédia.",
            es="No he podido encontrar nada sobre eso en Wikipedia.",
            de="Ich habe dazu nichts auf Wikipedia gefunden."
        )

    except Exception as e:
        _speak_multilang(
            "Something went wrong while searching Wikipedia.",
            hi="विकिपीडिया खोजते समय कुछ गड़बड़ हो गई।",
            fr="Une erreur s’est produite lors de la recherche sur Wikipédia.",
            es="Algo salió mal mientras buscaba en Wikipedia.",
            de="Beim Durchsuchen von Wikipedia ist ein Fehler aufgetreten."
        )
        log_interaction("wiki_error", str(e), selected_language)
