# 📂 handlers/wiki_commands.py

import re
import wikipedia
from difflib import get_close_matches
from command_map import COMMAND_MAP

def handle_wikipedia(command: str) -> None:
    # ✅ Delayed import to prevent circular dependency
    from utils import _speak_multilang, log_interaction, selected_language

    # 📚 Wikipedia (Multilingual query + language override + terminal display)
    wiki_phrases = COMMAND_MAP["wiki_search"]
    matched_wiki = get_close_matches(command, wiki_phrases, n=1, cutoff=0.6)

    if matched_wiki:
        try:
            wiki_lang = selected_language  # 🌐 Default to session language

            # 🌍 Manual override if user says "in hindi/french/etc"
            if " in hindi" in command:
                wiki_lang = "hi"
                command = command.replace(" in hindi", "")
            elif " in spanish" in command:
                wiki_lang = "es"
                command = command.replace(" in spanish", "")
            elif " in french" in command:
                wiki_lang = "fr"
                command = command.replace(" in french", "")
            elif " in german" in command or " in deutsch" in command:
                wiki_lang = "de"
                command = command.replace(" in german", "").replace(" in deutsch", "")

            # 🔍 Extract actual search topic
            topic = re.sub(
                r"(what is|who is|define|tell me about|क्या है|कौन है|qu'est-ce que|qui est|qué es|quién es|was ist|wer ist)",
                "", command, flags=re.IGNORECASE
            ).strip()

            if not topic:
                _speak_multilang(
                    "Please specify what you want to know.",
                    hi="कृपया बताओ कि तुम क्या जानना चाहती हो।",
                    fr="Veuillez préciser ce que vous souhaitez savoir.",
                    es="Por favor, especifica qué deseas saber.",
                    de="Bitte sag mir, was du wissen möchtest."
                )
                return

            # 🌐 Query Wikipedia
            wikipedia.set_lang(wiki_lang)
            summary = wikipedia.summary(topic, sentences=4)

            # 📺 Terminal output
            print("\n📚 NOVA WIKIPEDIA ANSWER")
            print("──────────────────────────────")
            print(f"🔎 Topic: {topic}")
            print(f"🌐 Language: {wiki_lang.upper()}")
            print(f"📖 Answer: {summary}\n")

            # 🔊 Voice + log
            _speak_multilang(
                summary,
                log_command=f"Wiki summary for: {topic}"
            )

        except wikipedia.exceptions.DisambiguationError:
            _speak_multilang(
                "That topic is too broad. Try something more specific.",
                hi="यह विषय बहुत व्यापक है। कृपया कुछ और विशिष्ट बताओ।",
                fr="Ce sujet est trop vaste. Essaie quelque chose de plus précis.",
                es="Ese tema es demasiado amplio. Intenta con algo más específico.",
                de="Dieses Thema ist zu allgemein. Versuch bitte etwas Konkreteres."
            )

        except wikipedia.exceptions.PageError:
            _speak_multilang(
                "I couldn't find anything on Wikipedia about that.",
                hi="मैं विकिपीडिया पर उस विषय के बारे में कुछ नहीं ढूंढ पाई।",
                fr="Je n’ai rien trouvé à ce sujet sur Wikipédia.",
                es="No he podido encontrar nada sobre eso en Wikipedia.",
                de="Ich habe dazu nichts auf Wikipedia gefunden."
            )

        except Exception as e:
            from utils import selected_language
            _speak_multilang(
                "Something went wrong while searching Wikipedia.",
                hi="विकिपीडिया खोजते समय कुछ गड़बड़ हो गई है।",
                fr="Une erreur s’est produite lors de la recherche sur Wikipédia.",
                es="Algo salió mal mientras buscaba en Wikipedia.",
                de="Beim Durchsuchen von Wikipedia ist ein Fehler aufgetreten."
            )
            log_interaction("wiki_error", str(e), selected_language)
