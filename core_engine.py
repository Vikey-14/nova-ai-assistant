import webbrowser
import os
import ctypes
import re
import threading
import datetime
import time
import wikipedia
from weather_handler import get_weather
from news_handler import get_headlines
from memory_handler import search_notes, print_all_notes, delete_specific_note, clear_all_notes, update_note, load_notes, save_note, read_notes
from utils import _speak_multilang, speak, listen_command, change_brightness, set_volume, selected_language

def process_command(command):
    command = command.lower()

    # 🌐 Multilingual Trigger Phrases for Alarm
    alarm_phrases = [
        "set alarm for",                            # English
        "अलार्म सेट करें",                              # Hindi
        "alarme pour",                              # French
        "alarma para",                              # Spanish
        "wecker für"                                # German
    ]

    # 🌐 Multilingual Trigger Phrases for Reminder
    reminder_phrases = [
        "remind me at",                             # English
        "rappelle-moi à",                           # French
        "recuérdame a las",                         # Spanish
        "erinnere mich um"                          # German
    ]

    # 🛑 Exit Command — Multilingual Trigger + Spoken + Printed
    if any(kw in command for kw in [
        "exit", "shutdown", "stop listening", "quit",           # English
        "बंद करो", "बाहर निकलो",                                 # Hindi
        "arrête", "quitte",                                     # French
        "apagar", "salir",                                      # Spanish
        "beenden", "verlassen"                                  # German
    ]):
        print("👋 NOVA: Exiting.")
        _speak_multilang(
            "Shutting down. Goodbye!",
            hi="बंद किया जा रहा है। अलविदा!",
            de="Herunterfahren. Auf Wiedersehen!",
            fr="Fermeture. Au revoir!",
            es="Apagando. ¡Adiós!"
        )
        exit()


    # 🌐 Web Commands — Multilingual Trigger + Response + Print

    # 🟥 YouTube
    elif any(kw in command for kw in [
        "open youtube", "youtube खोलो", "youtube खोलिए", "ouvre youtube",
        "abre youtube", "öffne youtube"
    ]):
        print("🌐 Opening YouTube...")
        _speak_multilang(
            "Opening YouTube.",
            hi="यूट्यूब खोल रहा हूँ।",
            de="YouTube wird geöffnet.",
            fr="Ouverture de YouTube.",
            es="Abriendo YouTube."
        )
        webbrowser.open("https://www.youtube.com")

    # 🟩 ChatGPT
    elif any(kw in command for kw in [
        "open chat g p t", "open chatgpt", "chatgpt खोलो", "ouvre chatgpt",
        "abre chatgpt", "öffne chatgpt"
    ]):
        print("🌐 Opening ChatGPT...")
        _speak_multilang(
            "Opening ChatGPT.",
            hi="चैटजीपीटी खोल रहा हूँ।",
            de="ChatGPT wird geöffnet.",
            fr="Ouverture de ChatGPT.",
            es="Abriendo ChatGPT."
        )
        webbrowser.open("https://chat.openai.com")

    # 🟦 Google Search
    elif any(kw in command for kw in [
        "search on google", "google पर खोजें", "google खोजो",
        "recherche sur google", "buscar en google", "google durchsuchen"
    ]):
        print("🌐 Preparing for Google search...")
        _speak_multilang(
            "What should I search for?",
            hi="मुझे क्या खोजना चाहिए?",
            de="Wonach soll ich suchen?",
            fr="Que dois-je rechercher ?",
            es="¿Qué debo buscar?"
        )
        for _ in range(2):
            query = listen_command()
            if query:
                print(f"🌐 Searching: {query}")
                webbrowser.open(f"https://www.google.com/search?q={query}")
                _speak_multilang(
                    f"Searching Google for {query}.",
                    hi=f"{query} के लिए गूगल पर खोज रहा हूँ।",
                    de=f"Suche Google nach {query}.",
                    fr=f"Recherche de {query} sur Google.",
                    es=f"Buscando {query} en Google."
                )
                return
        print("❌ No valid search term detected.")
        _speak_multilang(
            "Sorry, I couldn't understand the search term.",
            hi="माफ़ कीजिए, मैं खोज शब्द समझ नहीं पाया।",
            de="Entschuldigung, ich konnte den Suchbegriff nicht verstehen.",
            fr="Désolé, je n'ai pas compris le terme de recherche.",
            es="Lo siento, no entendí el término de búsqueda."
        )

    # 🟨 Play Music
    elif any(kw in command for kw in [
        "play music", "गाना चलाओ", "गीत बजाओ",
        "jouer de la musique", "reproducir música", "musik abspielen"
    ]):
        print("🎵 Asking for music to play...")
        _speak_multilang(
            "What song should I play?",
            hi="मैं कौन सा गाना चलाऊं?",
            de="Welches Lied soll ich spielen?",
            fr="Quelle chanson dois-je jouer ?",
            es="¿Qué canción debo reproducir?"
        )
        query = listen_command()
        if query:
            print(f"🎵 Playing on YouTube: {query}")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
            _speak_multilang(
                f"Playing {query} on YouTube.",
                hi=f"यूट्यूब पर {query} चला रहा हूँ।",
                de=f"{query} wird auf YouTube abgespielt.",
                fr=f"Lecture de {query} sur YouTube.",
                es=f"Reproduciendo {query} en YouTube."
            )
        else:
            print("❌ No song detected.")
            _speak_multilang(
                "I couldn't understand the song name.",
                hi="मैं गाने का नाम समझ नहीं पाया।",
                de="Ich konnte den Liednamen nicht verstehen.",
                fr="Je n'ai pas compris le nom de la chanson.",
                es="No entendí el nombre de la canción."
            )

    # 🔊 Volume Control — Multilingual Trigger + Multilingual Response
    elif any(phrase in command for phrase in [
        "increase volume", "turn up the volume",
        "वॉल्यूम बढ़ाओ", "आवाज़ बढ़ाओ",                       # Hindi
        "augmenter le volume", "monte le son",             # French
        "subir el volumen", "aumentar volumen",            # Spanish
        "lautstärke erhöhen", "ton lauter machen"          # German
    ]):
        print("🔊 Increasing volume...")
        for _ in range(5):
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
        _speak_multilang(
            "Volume increased.",
            hi="वॉल्यूम बढ़ा दिया गया है।",
            de="Lautstärke erhöht.",
            fr="Le volume a été augmenté.",
            es="Volumen aumentado."
        )

    elif any(phrase in command for phrase in [
        "decrease volume", "turn down the volume",
        "वॉल्यूम घटाओ", "आवाज़ कम करो",                      # Hindi
        "baisser le volume", "réduire le volume",          # French
        "bajar el volumen", "reducir volumen",             # Spanish
        "lautstärke verringern", "ton leiser machen"       # German
    ]):
        print("🔊 Decreasing volume...")
        for _ in range(5):
            ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
        _speak_multilang(
            "Volume decreased.",
            hi="वॉल्यूम घटा दिया गया है।",
            de="Lautstärke verringert.",
            fr="Le volume a été diminué.",
            es="Volumen disminuido."
        )

    elif any(phrase in command for phrase in [
        "mute volume", "mute sound",
        "वॉल्यूम म्यूट करो", "आवाज़ बंद करो",                     # Hindi
        "couper le son", "mettre en sourdine",              # French
        "silenciar volumen", "silenciar el sonido",         # Spanish
        "lautstärke stummschalten", "ton stumm"             # German
    ]):
        print("🔇 Muting volume...")
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        _speak_multilang(
            "Volume muted.",
            hi="वॉल्यूम म्यूट कर दिया गया है।",
            de="Lautstärke stummgeschaltet.",
            fr="Volume coupé.",
            es="Volumen silenciado."
        )

    elif any(phrase in command for phrase in [
        "max volume", "set volume to maximum",
        "अधिकतम वॉल्यूम", "वॉल्यूम फुल करो",                     # Hindi
        "volume maximum", "mettre le volume à fond",         # French
        "volumen máximo", "subir volumen al máximo",         # Spanish
        "maximale lautstärke", "lautstärke ganz hoch"        # German
    ]):
        print("🔊 Setting volume to MAX...")
        for _ in range(10):
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
        _speak_multilang(
            "Volume set to maximum.",
            hi="वॉल्यूम अधिकतम पर सेट कर दिया गया है।",
            de="Lautstärke auf Maximum eingestellt.",
            fr="Volume réglé au maximum.",
            es="Volumen establecido al máximo."
        )

    elif any(phrase in command for phrase in [
        "set volume to", "adjust volume to",
        "वॉल्यूम सेट करो", "वॉल्यूम को सेट करो",                   # Hindi
        "régler le volume à", "ajuster le volume à",         # French
        "establecer volumen a", "ajustar el volumen a",      # Spanish
        "lautstärke einstellen auf", "lautstärke setzen auf" # German
    ]):
        match = re.search(r"(\d+)", command)
        if match:
            vol = int(match.group(1))
            print(f"🔊 Setting volume to {vol}%...")
            set_volume(vol)
            _speak_multilang(
                f"Setting volume to {vol} percent.",
                hi=f"वॉल्यूम {vol} प्रतिशत पर सेट किया जा रहा है।",
                de=f"Lautstärke wird auf {vol} Prozent eingestellt.",
                fr=f"Réglage du volume à {vol} pour cent.",
                es=f"Estableciendo el volumen al {vol} por ciento."
            )
        else:
            _speak_multilang(
                "Please say a volume level like set volume to 50 percent.",
                hi="कृपया वॉल्यूम स्तर बताएं, जैसे कि 'वॉल्यूम 50 प्रतिशत पर सेट करें'।",
                de="Bitte sagen Sie eine Lautstärke wie 'Lautstärke auf 50 Prozent setzen'.",
                fr="Veuillez indiquer un niveau de volume comme 'régler le volume à 50 pour cent'.",
                es="Por favor, diga un nivel de volumen como 'establecer el volumen al 50 por ciento'."
            )
     
    
    # 🌦️ Weather — Multilingual Trigger
    elif any(kw in command for kw in [
        "weather", "temperature", "मौसम", "clima", "temps", "wetter"
    ]):
        city_match = re.search(r"in (\w+)", command)
        if city_match:
            city = city_match.group(1)
            get_weather(city)
        else:
            _speak_multilang(
                "Please tell me the city you want weather for.",
                hi="कृपया बताएं किस शहर का मौसम चाहिए।",
                fr="Veuillez indiquer la ville pour la météo.",
                es="Por favor, di el nombre de la ciudad para el clima.",
                de="Bitte sagen Sie den Stadtnamen für das Wetter."
            )

    
    # 🗞️ News — Multilingual Trigger
    elif any(kw in command for kw in [
        "news", "headlines", "latest news",
        "खबरें", "ताज़ा समाचार",                      # Hindi
        "nachrichten", "schlagzeilen",            # German
        "actualités", "nouvelles",                # French
        "noticias", "titulares"                   # Spanish
    ]):
        get_headlines()


    
    # 💡 Brightness — Multilingual Trigger + Multilingual Response
    elif any(phrase in command for phrase in [
        "increase brightness", "brighten my screen",
        "ब्राइटनेस बढ़ाओ", "स्क्रीन चमक बढ़ाओ",                           # Hindi
        "augmenter la luminosité", "rendre l'écran plus lumineux",  # French
        "aumentar el brillo", "subir el brillo",                    # Spanish
        "helligkeit erhöhen", "bildschirm heller machen"            # German
    ]):
        print("💡 Brightness: Increasing")
        _speak_multilang(
            "Increasing brightness.",
            hi="ब्राइटनेस बढ़ाई जा रही है।",
            fr="Augmentation de la luminosité.",
            es="Aumentando el brillo.",
            de="Helligkeit wird erhöht."
        )
        change_brightness(increase=True)

    elif any(phrase in command for phrase in [
        "decrease brightness", "dim my screen",
        "ब्राइटनेस कम करो", "स्क्रीन कम रोशनी करो",                      # Hindi
        "réduire la luminosité", "assombrir l'écran",               # French
        "bajar el brillo", "reducir el brillo",                     # Spanish
        "helligkeit verringern", "bildschirm abdunkeln"             # German
    ]):
        print("💡 Brightness: Decreasing")
        _speak_multilang(
            "Decreasing brightness.",
            hi="ब्राइटनेस कम की जा रही है।",
            fr="Réduction de la luminosité.",
            es="Disminuyendo el brillo.",
            de="Helligkeit wird verringert."
        )
        change_brightness(increase=False)

    elif any(phrase in command for phrase in [
        "set brightness to", "adjust brightness to",                
        "ब्राइटनेस सेट करो", "ब्राइटनेस को सेट करो",                       # Hindi
        "régler la luminosité à", "ajuster la luminosité à",        # French
        "establecer brillo a", "ajustar el brillo a",               # Spanish
        "helligkeit einstellen auf", "helligkeit setzen auf"        # German
    ]):
        match = re.search(r"(\d+)", command)
        if match:
            level = int(match.group(1))
            print(f"💡 Brightness: Setting to {level}%")
            _speak_multilang(
                f"Setting brightness to {level} percent.",
                hi=f"ब्राइटनेस को {level} प्रतिशत पर सेट किया जा रहा है।",
                fr=f"Luminosité réglée à {level} pour cent.",
                es=f"Ajustando el brillo al {level} por ciento.",
                de=f"Helligkeit wird auf {level} Prozent eingestellt."
            )
            change_brightness(level=level)
        else:
            _speak_multilang(
                "Please say a brightness level like 'set brightness to 70 percent'.",
                hi="कृपया ऐसा कहें: 'ब्राइटनेस को 70 प्रतिशत पर सेट करें'।",
                fr="Veuillez dire quelque chose comme 'régler la luminosité à 70 pour cent'.",
                es="Por favor, di algo como 'ajustar el brillo al 70 por ciento'.",
                de="Bitte sagen Sie etwas wie 'Helligkeit auf 70 Prozent einstellen'."
            )


    # 💻 System Control — Multilingual Trigger + Multilingual Response
    elif any(phrase in command for phrase in [
        "shutdown system", "turn off computer", "power off",
        "सिस्टम बंद", "कंप्यूटर बंद",
        "arrêter le système", "éteindre l'ordinateur",
        "apagar el sistema", "apagar la computadora",
        "system herunterfahren", "computer ausschalten"
    ]):
        print("🖥️ System: Shutdown initiated")
        _speak_multilang(
            "Shutting down the system now.",
            hi="सिस्टम को अभी बंद किया जा रहा है।",
            fr="Arrêt du système maintenant.",
            es="Apagando el sistema ahora.",
            de="Das System wird jetzt heruntergefahren."
        )
        os.system("shutdown /s /t 1")

    elif any(phrase in command for phrase in [
        "restart", "reboot", "system restart",
        "सिस्टम पुनः आरंभ", "रीस्टार्ट",
        "redémarrer", "redémarrage du système",
        "reiniciar", "reiniciar el sistema",
        "neu starten", "system neu starten"
    ]):
        print("🔁 System: Restarting now")
        _speak_multilang(
            "Restarting the system.",
            hi="सिस्टम को पुनः आरंभ किया जा रहा है।",
            fr="Redémarrage du système.",
            es="Reiniciando el sistema.",
            de="System wird neu gestartet."
        )
        os.system("shutdown /r /t 1")

    elif any(phrase in command for phrase in [
        "sleep", "put to sleep", "go to sleep",
        "स्लीप मोड", "नींद मोड",
        "mettre en veille", "mode veille",
        "modo de suspensión", "poner en reposo",
        "schlafmodus", "in den schlafmodus versetzen"
    ]):
        print("😴 System: Going to sleep")
        _speak_multilang(
            "Putting the computer to sleep.",
            hi="कंप्यूटर को स्लीप मोड में डाला जा रहा है।",
            fr="Mise en veille de l'ordinateur.",
            es="Poniendo el ordenador en suspensión.",
            de="Computer wird in den Ruhezustand versetzt."
        )
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    elif any(phrase in command for phrase in [
        "lock", "lock screen",
        "स्क्रीन लॉक", "लॉक करें",
        "verrouiller l'écran", "verrouiller",
        "bloquear pantalla", "bloquear",
        "bildschirm sperren", "sperren"
    ]):
        print("🔒 System: Locking screen")
        _speak_multilang(
            "Locking the screen now.",
            hi="स्क्रीन को लॉक किया जा रहा है।",
            fr="Verrouillage de l'écran maintenant.",
            es="Bloqueando la pantalla ahora.",
            de="Bildschirm wird jetzt gesperrt."
        )
        os.system("rundll32.exe user32.dll,LockWorkStation")

    elif any(phrase in command for phrase in [
        "log out", "sign out",
        "लॉग आउट", "साइन आउट",
        "se déconnecter", "déconnexion",
        "cerrar sesión", "desconectar",
        "abmelden", "ausloggen"
    ]):
        print("🚪 System: Logging out")
        _speak_multilang(
            "Logging you out now.",
            hi="अब आपको लॉग आउट किया जा रहा है।",
            fr="Déconnexion en cours.",
            es="Cerrando sesión ahora.",
            de="Sie werden jetzt abgemeldet."
        )
        os.system("shutdown /l")

    # ⏰ Alarm (Multilingual Trigger)
    elif any(phrase in command for phrase in alarm_phrases):
        match = re.search(r"(\d{1,2})[\s:](\d{1,2})", command)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))

            def alarm_checker():
                _speak_multilang(
                    f"Alarm set for {hour:02d}:{minute:02d}. I’ll notify you.",
                    hi=f"अलार्म {hour:02d}:{minute:02d} पर सेट कर दिया गया है। मैं आपको सूचित करूँगा।",
                    de=f"Alarm für {hour:02d}:{minute:02d} eingestellt. Ich werde Sie benachrichtigen.",
                    fr=f"Alarme réglée pour {hour:02d}:{minute:02d}. Je vous avertirai.",
                    es=f"Alarma configurada para las {hour:02d}:{minute:02d}. Te lo recordaré."
                )
                while True:
                    now = datetime.datetime.now()
                    if now.hour == hour and now.minute == minute:
                        _speak_multilang(
                            f"It's {hour:02d}:{minute:02d}. Time to wake up!",
                            hi=f"{hour:02d}:{minute:02d} हो गया है। अब उठने का समय है!",
                            de=f"Es ist {hour:02d}:{minute:02d}. Zeit zum Aufstehen!",
                            fr=f"Il est {hour:02d}:{minute:02d}. Il est temps de se lever !",
                            es=f"Son las {hour:02d}:{minute:02d}. ¡Es hora de despertarse!"
                        )
                        break
                    time.sleep(10)

            threading.Thread(target=alarm_checker, daemon=True).start()

        else:
            _speak_multilang(
                "Say something like 'set alarm for 6 30'.",
                hi="कुछ ऐसा कहें जैसे '6 30 के लिए अलार्म सेट करें'।",
                de="Sagen Sie etwas wie 'Wecker auf 6 30 stellen'.",
                fr="Dites quelque chose comme 'régler l'alarme pour 6h30'.",
                es="Di algo como 'configura la alarma para las 6 30'."
            )


    # 📝 Reminder (Multilingual Trigger)
    elif any(phrase in command for phrase in reminder_phrases):
        match = re.search(r"(\d{1,2})[\s:](\d{1,2}).*?(to|कि|à|para|um)\s(.+)", command)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            task = match.group(4).strip()

            def reminder_checker():
                _speak_multilang(
                    f"Reminder set for {hour:02d}:{minute:02d} to {task}.",
                    hi=f"{hour:02d}:{minute:02d} बजे के लिए रिमाइंडर सेट किया गया है: {task}",
                    de=f"Erinnerung um {hour:02d}:{minute:02d} eingestellt für: {task}",
                    fr=f"Rappel défini pour {hour:02d}:{minute:02d} pour : {task}",
                    es=f"Recordatorio establecido para las {hour:02d}:{minute:02d} para: {task}"
                )
                while True:
                    now = datetime.datetime.now()
                    if now.hour == hour and now.minute == minute:
                        _speak_multilang(
                            f"This is your reminder: {task}",
                            hi=f"यह आपकी याद दिलाने वाली बात है: {task}",
                            de=f"Das ist Ihre Erinnerung: {task}",
                            fr=f"Voici votre rappel : {task}",
                            es=f"Aquí está tu recordatorio: {task}"
                        )
                        break
                    time.sleep(10)

            threading.Thread(target=reminder_checker, daemon=True).start()

        else:
            _speak_multilang(
                "Say something like 'Remind me at 3 30 to watch the match'.",
                hi="ऐसा कुछ कहें जैसे 'मुझे 3 30 बजे मैच देखने के लिए याद दिलाएं'।",
                de="Sagen Sie etwas wie 'Erinnere mich um 3 30 an das Spiel'.",
                fr="Dites quelque chose comme 'Rappelle-moi à 3 30 de regarder le match'.",
                es="Di algo como 'Recuérdame a las 3 30 ver el partido'."
            )


    # 📚 Wikipedia (Multilingual query + language override + terminal display)
    elif any(kw in command for kw in [
        "what is", "who is", "define", "tell me about",         # English
        "क्या है", "कौन है",                                       # Hindi
        "qu'est-ce que", "qui est",                             # French
        "qué es", "quién es",                                   # Spanish
        "was ist", "wer ist"                                    # German
    ]):
        try:
            wiki_lang = selected_language  # 🌐 Default to current session language

            # 🌍 Manual override if user specifies language
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

            # 🔍 Extract actual topic
            topic = re.sub(
                r"(what is|who is|define|tell me about|क्या है|कौन है|qu'est-ce que|qui est|qué es|quién es|was ist|wer ist)",
                "", command, flags=re.IGNORECASE
            ).strip()

            if not topic:
                _speak_multilang(
                    "Please specify what you want to know.",
                    hi="कृपया बताएं कि आप क्या जानना चाहते हैं।",
                    fr="Veuillez préciser ce que vous voulez savoir.",
                    es="Por favor, especifica lo que quieres saber.",
                    de="Bitte geben Sie an, was Sie wissen möchten."
                )
                return

            # 🌐 Set Wikipedia language and search
            wikipedia.set_lang(wiki_lang)
            summary = wikipedia.summary(topic, sentences=2)

            # 🖥️ Terminal output
            print("\n📚 NOVA WIKIPEDIA ANSWER")
            print("──────────────────────────────")
            print(f"🔎 Topic: {topic}")
            print(f"🌐 Language: {wiki_lang.upper()}")
            print(f"📖 Answer: {summary}\n")

            # 🗣️ Voice output
            _speak_multilang(summary)

        except wikipedia.exceptions.DisambiguationError:
            _speak_multilang(
                "That topic is too broad. Try something more specific.",
                hi="विषय बहुत व्यापक है। कृपया कुछ और विशिष्ट कहें।",
                fr="Ce sujet est trop vaste. Essayez quelque chose de plus précis.",
                es="Ese tema es demasiado amplio. Intenta algo más específico.",
                de="Dieses Thema ist zu allgemein. Versuchen Sie etwas Spezifischeres."
            )

        except wikipedia.exceptions.PageError:
            _speak_multilang(
                "I couldn't find anything on Wikipedia about that.",
                hi="मैं उस विषय पर विकिपीडिया पर कुछ नहीं ढूंढ पाया।",
                fr="Je n'ai rien trouvé sur Wikipédia à ce sujet.",
                es="No pude encontrar nada sobre eso en Wikipedia.",
                de="Ich konnte nichts darüber auf Wikipedia finden."
            )

        except Exception:
            _speak_multilang(
                "Something went wrong while searching Wikipedia.",
                hi="विकिपीडिया खोजते समय कुछ गड़बड़ हो गई।",
                fr="Une erreur s'est produite lors de la recherche sur Wikipédia.",
                es="Algo salió mal al buscar en Wikipedia.",
                de="Beim Durchsuchen von Wikipedia ist ein Fehler aufgetreten."
            )


    # 🧠 Remember Name — Multilingual Trigger
    elif any(kw in command for kw in [
        "my name is", "मेरा नाम", "je m'appelle", "me llamo", "ich heiße"
    ]):
        name = None

        # 🌍 Try to extract name using regex patterns in multiple languages
        match = re.search(r"(my name is|मेरा नाम|je m'appelle|me llamo|ich heiße)\s+([a-zA-ZÀ-ÿ\u0900-\u097F]+)", command)
        if match:
            name = match.group(2).strip()

        if name:
            # 🔒 Save to memory.json
            from memory_handler import save_memory
            save_memory("name", name)

            # 🗣️ Confirm aloud in the chosen language
            _speak_multilang(
                f"Nice to meet you, {name}!",
                hi=f"आपसे मिलकर खुशी हुई, {name}!",
                fr=f"Ravi de vous rencontrer, {name}!",
                es=f"Encantado de conocerte, {name}!",
                de=f"Freut mich, dich kennenzulernen, {name}!"
            )
        else:
            _speak_multilang(
                "Sorry, I couldn't catch your name.",
                hi="माफ़ कीजिए, मैं आपका नाम नहीं समझ पाया।",
                fr="Désolé, je n'ai pas compris votre nom.",
                es="Lo siento, no entendí tu nombre.",
                de="Entschuldigung, ich habe deinen Namen nicht verstanden."
            )


    # 🧠 Recall Name — Multilingual Trigger
    elif any(kw in command for kw in [
        "what's my name", "what is my name",         # English
        "मेरा नाम क्या है",                              # Hindi
        "quel est mon nom",                          # French
        "cuál es mi nombre",                         # Spanish
        "wie heiße ich"                              # German
    ]):
        from memory_handler import load_memory
        name = load_memory("name")

        if name:
            _speak_multilang(
                f"Your name is {name}.",
                hi=f"आपका नाम {name} है।",
                fr=f"Votre nom est {name}.",
                es=f"Tu nombre es {name}.",
                de=f"Dein Name ist {name}."
            )
        else:
            _speak_multilang(
                "I don’t know your name yet. You can tell me by saying, 'My name is...'",
                hi="मुझे अभी आपका नाम नहीं पता। आप कह सकते हैं, 'मेरा नाम ... है'।",
                fr="Je ne connais pas encore votre nom. Vous pouvez me dire, 'Je m'appelle...'",
                es="Aún no sé tu nombre. Puedes decir, 'Me llamo...'",
                de="Ich kenne deinen Namen noch nicht. Du kannst sagen: 'Ich heiße...'"
            )
    

    # 🧠 Store general preferences — multilingual support
    elif any(phrase in command for phrase in [
        "i like", "i love", "my favorite",           # English
        "मुझे पसंद है", "मेरा पसंदीदा",                    # Hindi
        "j'aime", "mon préféré",                     # French
        "me gusta", "mi favorito",                   # Spanish
        "ich mag", "mein lieblings"                  # German
    ]):
        from memory_handler import save_memory

        try:
            # Remove trigger phrase to isolate preference
            preference = re.sub(
                r"(i like|i love|my favorite|मुझे पसंद है|मेरा पसंदीदा|j'aime|mon préféré|me gusta|mi favorito|ich mag|mein lieblings)",
                "", command, flags=re.IGNORECASE
            ).strip()

            if preference:
                save_memory("preference", preference)

                _speak_multilang(
                    f"Got it! I'll remember that you like {preference}.",
                    hi=f"समझ गया! मैं याद रखूंगा कि आपको {preference} पसंद है।",
                    fr=f"Compris ! Je me souviendrai que vous aimez {preference}.",
                    es=f"Entendido. Recordaré que te gusta {preference}.",
                    de=f"Alles klar! Ich werde mir merken, dass du {preference} magst."
                )
            else:
                raise ValueError("Empty preference")

        except:
            _speak_multilang(
                "Sorry, I couldn't understand your preference.",
                hi="माफ़ कीजिए, मैं आपकी पसंद नहीं समझ पाया।",
                fr="Désolé, je n'ai pas compris votre préférence.",
                es="Lo siento, no entendí tu preferencia.",
                de="Entschuldigung, ich habe deine Vorliebe nicht verstanden."
            )


    # 🔁 Update memory values — multilingual support
    elif any(phrase in command for phrase in ["update my", "change my", "मेरा नाम बदलो", "modifie mon", "cambia mi", "ändere meinen"]):
        from memory_handler import save_memory

        try:
            # 🌍 Try to extract key and new value
            match = re.search(r"(update|change|बदलो|modifie|cambia|ändere)\s+my\s+(\w+)\s+(to|से|en|a|zu)\s+([a-zA-ZÀ-ÿ\u0900-\u097F]+)", command)
            if match:
                key = match.group(2).strip().lower()
                new_value = match.group(4).strip()
                save_memory(key, new_value)

                _speak_multilang(
                    f"Got it. I've updated your {key} to {new_value}.",
                    hi=f"ठीक है। मैंने आपका {key} {new_value} कर दिया है।",
                    fr=f"D'accord. J'ai mis à jour votre {key} en {new_value}.",
                    es=f"Entendido. He actualizado tu {key} a {new_value}.",
                    de=f"Alles klar. Ich habe deinen {key} auf {new_value} aktualisiert."
                )
            else:
                raise ValueError("Could not extract key/value")

        except:
            _speak_multilang(
                "Sorry, I couldn't understand what to update.",
                hi="माफ़ कीजिए, मैं समझ नहीं पाया कि क्या बदलना है।",
                fr="Désolé, je n'ai pas compris ce qu'il faut changer.",
                es="Lo siento, no entendí qué actualizar.",
                de="Entschuldigung, ich habe nicht verstanden, was aktualisiert werden soll."
            )


    # 🧹 Clear memory — specific or all
    elif any(phrase in command for phrase in ["forget", "delete", "remove", "मिटा दो", "oublie", "olvida", "vergiss"]):
        from memory_handler import clear_memory

        try:
            if "everything" in command or "सब कुछ" in command or "tout" in command or "todo" in command or "alles" in command:
                clear_memory()  # Wipe all keys
                _speak_multilang(
                    "Memory cleared completely.",
                    hi="सारी मेमोरी हटा दी गई है।",
                    fr="La mémoire a été complètement effacée.",
                    es="La memoria se ha borrado completamente.",
                    de="Der gesamte Speicher wurde gelöscht."
                )
            else:
                # Try to guess the specific key to delete (e.g., name, preference)
                key = None
                if "name" in command or "नाम" in command or "nom" in command or "nombre" in command:
                    key = "name"
                elif "preference" in command or "पसंद" in command or "préférence" in command or "preferencia" in command or "Vorliebe" in command:
                    key = "preference"

                if key:
                    clear_memory(key)
                    _speak_multilang(
                        f"I've forgotten your {key}.",
                        hi=f"मैंने आपका {key} भूल गया हूँ।",
                        fr=f"J'ai oublié votre {key}.",
                        es=f"He olvidado tu {key}.",
                        de=f"Ich habe deine {key} vergessen."
                    )
                else:
                    raise ValueError("Unknown key")

        except:
            _speak_multilang(
                "Sorry, I couldn't clear the memory properly.",
                hi="माफ़ कीजिए, मैं मेमोरी साफ़ नहीं कर पाया।",
                fr="Désolé, je n'ai pas pu effacer la mémoire.",
                es="Lo siento, no pude borrar la memoria.",
                de="Entschuldigung, ich konnte den Speicher nicht löschen."
            )

    
    # 📝 Voice Note — multilingual note-taking
    elif any(phrase in command for phrase in [
        "take a note", "write this down", "make a note",       # English
        "नोट बनाओ",                                            # Hindi
        "prends une note",                                     # French
        "toma una nota",                                       # Spanish
        "notiere etwas"                                        # German
    ]):
        from memory_handler import save_note
        try:
            speak("What would you like me to note down?")
            note_content = listen_command().strip()

            if note_content:
                save_note(note_content)

                _speak_multilang(
                    "Noted successfully.",
                    hi="नोट बना लिया गया है।",
                    fr="Note enregistrée avec succès.",
                    es="Nota guardada con éxito.",
                    de="Notiz erfolgreich gespeichert."
                )
            else:
                raise ValueError("Empty note")

        except Exception:
            _speak_multilang(
                "Sorry, I couldn’t save your note.",
                hi="माफ़ कीजिए, मैं आपकी नोट नहीं सहेज पाया।",
                fr="Désolé, je n'ai pas pu enregistrer votre note.",
                es="Lo siento, no pude guardar tu nota.",
                de="Entschuldigung, ich konnte deine Notiz nicht speichern."
            )


    # 📖 Read all saved notes — multilingual support
    elif any(phrase in command for phrase in [
        "read my notes", "show my notes", "नोट्स पढ़ो", "मेरे नोट्स दिखाओ",
        "lire mes notes", "montre mes notes",
        "lee mis notas", "muéstrame mis notas",
        "lies meine notizen", "zeige meine notizen"
    ]):
        from memory_handler import load_notes
        notes = load_notes()

        if not notes:
            _speak_multilang(
                "You have no saved notes.",
                hi="आपके पास कोई सहेजे गए नोट्स नहीं हैं।",
                fr="Vous n'avez aucune note enregistrée.",
                es="No tienes notas guardadas.",
                de="Du hast keine gespeicherten Notizen."
            )
        else:
            _speak_multilang(
                f"You have {len(notes)} notes. Reading them now.",
                hi=f"आपके पास {len(notes)} नोट्स हैं। मैं उन्हें अब पढ़ रहा हूँ।",
                fr=f"Vous avez {len(notes)} notes. Je vais les lire.",
                es=f"Tienes {len(notes)} notas. Leyéndolas ahora.",
                de=f"Du hast {len(notes)} Notizen. Ich lese sie vor."
            )

            # 🖨️ Print all notes with index and timestamp in terminal
            for idx, note in enumerate(notes, start=1):
                print(f"📝 [{idx}] ({note['timestamp']}): {note['content']}")

            # 🔊 Speak each note
            for note in notes:
                _speak_multilang(note['content'])
    


    # ✏️ Update a note by number or keyword
    elif any(phrase in command for phrase in [
        "update note", "change note", "edit note", "नोट बदलो",
        "modifie la note", "cambia la nota", "ändere die notiz"
    ]):
        from memory_handler import update_note

        try:
            index = None
            keyword = None
            new_content = None

            # 🎯 Try to extract index
            match = re.search(r"note\s*(number\s*)?(\d+)\s*(to|into)?\s*(.+)", command)
            if match:
                index = int(match.group(2))
                new_content = match.group(4).strip()
            else:
                # 🔍 Try keyword-based update
                match_kw = re.search(r"(?:update|change|edit)\s+note\s+(.*?)\s+(to|into)\s+(.+)", command)
                if match_kw:
                    keyword = match_kw.group(1).strip()
                    new_content = match_kw.group(3).strip()

            if new_content and (index or keyword):
                success = update_note(index=index, keyword=keyword, new_content=new_content)
                if success:
                    _speak_multilang(
                        "Note updated successfully.",
                        hi="नोट सफलतापूर्वक अपडेट किया गया।",
                        fr="Note mise à jour avec succès.",
                        es="Nota actualizada con éxito.",
                        de="Notiz erfolgreich aktualisiert."
                    )
                else:
                    raise ValueError("Note not found")
            else:
                raise ValueError("Could not parse command")

        except:
            _speak_multilang(
                "Sorry, I couldn't update the note.",
                hi="माफ़ कीजिए, मैं नोट अपडेट नहीं कर पाया।",
                fr="Désolé, je n'ai pas pu mettre à jour la note.",
                es="Lo siento, no pude actualizar la nota.",
                de="Entschuldigung, ich konnte die Notiz nicht aktualisieren."
            )


    # 🔍 Search notes by keyword and read — multilingual trigger
    elif any(phrase in command for phrase in [
        "search notes", "find notes", "look for note", "नोट खोजें", "नोट ढूंढो",
        "chercher des notes", "trouve des notes",
        "buscar notas", "encontrar notas",
        "suche notizen", "finde notizen"
    ]):
        try:
            # 🎯 Extract keyword from command
            keyword = re.sub(
                r"(search notes|find notes|look for note|नोट खोजें|नोट ढूंढो|chercher des notes|trouve des notes|buscar notas|encontrar notas|suche notizen|finde notizen)",
                "", command, flags=re.IGNORECASE
            ).strip()

            results = search_notes(keyword)

            if not results:
                _speak_multilang(
                    "No notes found with that keyword.",
                    hi="उस कीवर्ड से कोई नोट्स नहीं मिले।",
                    fr="Aucune note trouvée avec ce mot-clé.",
                    es="No se encontraron notas con esa palabra clave.",
                    de="Keine Notizen mit diesem Stichwort gefunden."
                )
            else:
                _speak_multilang(
                    f"I found {len(results)} notes with that keyword.",
                    hi=f"मुझे उस कीवर्ड से {len(results)} नोट्स मिले।",
                    fr=f"J'ai trouvé {len(results)} notes avec ce mot-clé.",
                    es=f"Encontré {len(results)} notas con esa palabra clave.",
                    de=f"Ich habe {len(results)} Notizen mit diesem Stichwort gefunden."
                )

                # 🖨️ Print notes with index in terminal
                print("\n🔎 Matching Notes:")
                for i, note in enumerate(results, 1):
                    print(f"{i}. [{note['timestamp']}] {note['content']}")

                # 📣 Ask if user wants to hear one
                _speak_multilang(
                    "Would you like me to read one of them? Say the note number or say cancel.",
                    hi="क्या आप उनमें से एक नोट सुनना चाहेंगे? नंबर बताइए या कैंसिल कहिए।",
                    fr="Souhaitez-vous que je lise l'une d'elles ? Dites le numéro ou annulez.",
                    es="¿Quieres que lea una de ellas? Di el número o cancela.",
                    de="Möchtest du, dass ich eine davon vorlese? Sag die Nummer oder abbrechen."
                )

                user_reply = listen_command().lower()
                if user_reply and any(word in user_reply for word in ["cancel", "कैंसिल", "annule", "cancela", "abbrechen"]):
                    _speak_multilang(
                        "Okay, cancelled reading.",
                        hi="ठीक है, पढ़ना रद्द किया।",
                        fr="D'accord, lecture annulée.",
                        es="Vale, lectura cancelada.",
                        de="Okay, Lesen abgebrochen."
                    )
                else:
                    # 🔢 Try extracting number
                    match = re.search(r"\d+", user_reply)
                    if match:
                        index = int(match.group())
                        if 1 <= index <= len(results):
                            selected_note = results[index - 1]['content']
                            _speak_multilang(selected_note)
                        else:
                            _speak_multilang(
                                "That number is out of range.",
                                hi="वह संख्या सीमा से बाहर है।",
                                fr="Ce numéro est hors de portée.",
                                es="Ese número está fuera de rango.",
                                de="Diese Nummer ist außerhalb des Bereichs."
                            )
                    else:
                        _speak_multilang(
                            "Sorry, I didn't understand the number.",
                            hi="माफ़ कीजिए, मैं संख्या नहीं समझ पाया।",
                            fr="Désolé, je n'ai pas compris le numéro.",
                            es="Lo siento, no entendí el número.",
                            de="Entschuldigung, ich habe die Nummer nicht verstanden."
                        )

        except Exception as e:
            _speak_multilang(
                "Something went wrong while searching the notes.",
                hi="नोट्स खोजने में कुछ गड़बड़ हो गई।",
                fr="Une erreur s'est produite lors de la recherche des notes.",
                es="Algo salió mal al buscar las notas.",
                de="Beim Durchsuchen der Notizen ist ein Fehler aufgetreten."
            )
            print("❌ Search error:", e)


    # 🧽 Delete notes — by number, keyword, or everything
    elif any(phrase in command for phrase in [
        "delete note", "remove note", "delete my note", "remove my note",
        "delete all notes", "remove all notes", "सभी नोट्स हटाओ",
        "नोट हटाओ", "मेरी नोट हटाओ", "supprime la note", "supprime toutes les notes",
        "borra la nota", "borra todas las notas",
        "lösche die notiz", "alle notizen löschen", "meine notiz löschen"
    ]):
        try:
            # 🌪️ Case 1: Delete ALL notes
            if "all notes" in command or "सभी" in command or "toutes" in command or "todas" in command or "alle" in command:
                clear_all_notes()
                _speak_multilang(
                    "All notes deleted successfully.",
                    hi="सभी नोट्स सफलतापूर्वक हटा दिए गए।",
                    fr="Toutes les notes ont été supprimées avec succès.",
                    es="Todas las notas se han eliminado con éxito.",
                    de="Alle Notizen wurden erfolgreich gelöscht."
                )
            else:
                # 🎯 Case 2: Delete by number
                index = None
                keyword = None

                match = re.search(r"note\s*(number\s*)?(\d+)", command)
                if match:
                    index = int(match.group(2))
                else:
                    # 🔍 Case 3: Delete by keyword
                    keyword = re.sub(
                        r"(delete note|remove note|delete my note|remove my note|नोट हटाओ|मेरी नोट हटाओ|supprime la note|borra la nota|lösche die notiz|meine notiz löschen)",
                        "", command, flags=re.IGNORECASE
                    ).strip()

                success = delete_specific_note(index=index, keyword=keyword)

                if success:
                    _speak_multilang(
                        "Note deleted successfully.",
                        hi="नोट सफलतापूर्वक हटा दिया गया।",
                        fr="Note supprimée avec succès.",
                        es="Nota eliminada con éxito.",
                        de="Notiz erfolgreich gelöscht."
                    )
                else:
                    _speak_multilang(
                        "Sorry, I couldn't find that note.",
                        hi="माफ़ कीजिए, मैं वह नोट नहीं ढूंढ पाया।",
                        fr="Désolé, je n'ai pas trouvé cette note.",
                        es="Lo siento, no encontré esa nota.",
                        de="Entschuldigung, ich konnte die Notiz nicht finden."
                    )

        except Exception:
            _speak_multilang(
                "Something went wrong while trying to delete the note.",
                hi="नोट हटाने में कुछ गड़बड़ हो गई।",
                fr="Une erreur s'est produite lors de la suppression de la note.",
                es="Algo salió mal al intentar eliminar la nota.",
                de="Beim Löschen der Notiz ist ein Fehler aufgetreten."
            )
    
    
    # 💬 Chat Mode — Friendly Responses
    elif any(kw in command for kw in [
        "how are you", "what's up", "how’s it going",
        "कैसे हो", "क्या चल रहा है",                     # Hindi
        "comment ça va", "ça va",                       # French
        "wie geht's", "wie läuft's",                    # German
        "cómo estás", "qué tal"                         # Spanish
    ]):
        _speak_multilang(
            "I'm doing great, Commander V. Ready for our next mission!",
            hi="मैं बढ़िया हूँ, कमांडर V। अगले मिशन के लिए तैयार हूँ!",
            fr="Je vais très bien, Commandant V. Prêt pour notre prochaine mission !",
            de="Mir geht’s großartig, Commander V. Bereit für unsere nächste Mission!",
            es="Estoy genial, Comandante V. ¡Listo para la próxima misión!"
        )
    
    elif "your name" in command or "who are you" in command:
        _speak_multilang(
            "I am NOVA, your AI assistant — designed to serve, protect, and sometimes make you laugh.",
            hi="मैं NOVA हूँ, आपका AI सहायक — सेवा, सुरक्षा और कभी-कभी हंसी के लिए।",
            fr="Je suis NOVA, votre assistant IA — conçu pour servir, protéger et parfois vous faire rire.",
            de="Ich bin NOVA, dein KI-Assistent – entwickelt, um zu helfen, zu schützen und dich manchmal zum Lachen zu bringen.",
            es="Soy NOVA, tu asistente de IA — creado para ayudarte, protegerte y hacerte reír."
        )
    
    elif "joke" in command or "tell me a joke" in command:
        _speak_multilang(
            "Why don’t scientists trust atoms? Because they make up everything!",
            hi="वैज्ञानिक परमाणुओं पर भरोसा क्यों नहीं करते? क्योंकि वे हर चीज बना देते हैं!",
            fr="Pourquoi les scientifiques ne font-ils pas confiance aux atomes ? Parce qu’ils inventent tout !",
            de="Warum vertrauen Wissenschaftler Atomen nicht? Weil sie alles erfinden!",
            es="¿Por qué los científicos no confían en los átomos? ¡Porque lo inventan todo!"
        )
        

    # 🤷 Fallback
    else:
        _speak_multilang(
            "Sorry, I don't recognize that command yet.",
            hi="माफ़ कीजिए, मैं अभी उस आदेश को नहीं समझ पाया।",
            fr="Désolé, je ne reconnais pas encore cette commande.",
            es="Lo siento, no reconozco ese comando todavía.",
            de="Entschuldigung, ich erkenne diesen Befehl noch nicht."
        )
