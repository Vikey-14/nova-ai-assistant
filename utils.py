import pyttsx3
import speech_recognition as sr
import wmi
from ctypes import cast, POINTER
from gui_interface import nova_gui
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# 🌍 Supported languages map for pyttsx3 voice filtering
language_voice_map = {
    "en": "english",
    "hi": "hindi",
    "de": "german",
    "fr": "french",
    "es": "spanish"
}

# 🧠 Store selected language globally (default to English)
selected_language = "en"

# 🗣️ Text-to-Speech
def speak(message):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    selected_voice_lang = language_voice_map.get(selected_language, "english")
    for voice in voices:
        if selected_voice_lang.lower() in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.setProperty('rate', 175)
    engine.say(message)
    engine.runAndWait()

# 🧠 Multilingual speaker helper
def _speak_multilang(en, hi="", de="", fr="", es=""):
    lang_map = {
        "en": en,
        "hi": hi or en,
        "de": de or en,
        "fr": fr or en,
        "es": es or en
    }
    response = lang_map.get(selected_language, en)

    # 🔊 Speak out loud
    speak(response)

    # 💬 Show in GUI if available
    try:
        nova_gui.show_message("NOVA", response)
    except:
        pass

# 👋 Greet user (before language is set — always in English)
def greet_user():
    print("🟢 NOVA: Hello! I’m Nova, your AI assistant. I’m online and ready to help you.")
    speak("Hello! I’m Nova, your AI assistant. I’m online and ready to help you.")


# 🎙️ Recognize user voice
def listen_command():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎙️  Listening for your command...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        command = recognizer.recognize_google(audio)
        print(f"🗣️  You said: {command}")
        return command.lower()
    except sr.UnknownValueError:
        _speak_multilang(
            "Sorry, I didn’t catch that.",
            hi="माफ़ कीजिए, मैं समझ नहीं पाया।",
            de="Entschuldigung, das habe ich nicht verstanden.",
            fr="Désolé, je n'ai pas compris.",
            es="Lo siento, no entendí eso."
        )
        return ""
    except sr.RequestError:
        _speak_multilang(
            "Network issue. Try again later.",
            hi="नेटवर्क में समस्या है। बाद में प्रयास करें।",
            de="Netzwerkproblem. Versuchen Sie es später erneut.",
            fr="Problème de réseau. Réessayez plus tard.",
            es="Problema de red. Inténtalo de nuevo más tarde."
        )
        return ""

# 🌐 Ask for language preference
def set_language():
    global selected_language
    speak("Please say your preferred language: English, Hindi, German, French, or Spanish?")
    
    for _ in range(2):
        lang = listen_command()
        if "hindi" in lang:
            selected_language = "hi"
            _speak_multilang("Language set to Hindi.", hi="भाषा हिन्दी पर सेट की गई है। यह सत्र में उपयोग की जाएगी।")
            return
        elif "german" in lang or "deutsch" in lang:
            selected_language = "de"
            _speak_multilang("Language set to German.", de="Die Sprache wurde auf Deutsch eingestellt.")
            return
        elif "french" in lang or "français" in lang:
            selected_language = "fr"
            _speak_multilang("Language set to French.", fr="La langue a été définie sur le français.")
            return
        elif "spanish" in lang or "español" in lang:
            selected_language = "es"
            _speak_multilang("Language set to Spanish.", es="El idioma se ha configurado en español.")
            return
        elif "english" in lang:
            selected_language = "en"
            _speak_multilang("Language set to English.")
            return
    selected_language = "en"
    _speak_multilang("Defaulting to English.")

# 💡 Brightness control
def change_brightness(increase=True, level=None):
    try:
        c = wmi.WMI(namespace='wmi')
        methods = c.WmiMonitorBrightnessMethods()[0]
        current_level = c.WmiMonitorBrightness()[0].CurrentBrightness

        if level is not None:
            level = max(0, min(100, level))
            methods.WmiSetBrightness(level, 0)
            _speak_multilang(f"Brightness set to {level} percent.",
                             hi=f"ब्राइटनेस {level} प्रतिशत पर सेट कर दी गई है।",
                             de=f"Helligkeit auf {level} Prozent eingestellt.",
                             fr=f"La luminosité a été réglée à {level} pour cent.",
                             es=f"El brillo se ha ajustado al {level} por ciento.")
        else:
            new_level = min(100, current_level + 30) if increase else max(0, current_level - 30)
            methods.WmiSetBrightness(new_level, 0)
            direction = "increased" if increase else "decreased"
            _speak_multilang(f"Brightness {direction} to {new_level} percent.",
                             hi=f"ब्राइटनेस {new_level} प्रतिशत तक {('बढ़ाई' if increase else 'घटाई')} गई है।",
                             de=f"Helligkeit auf {new_level} Prozent {('erhöht' if increase else 'verringert')}.",
                             fr=f"La luminosité a été {('augmentée' if increase else 'diminuée')} à {new_level} pour cent.",
                             es=f"El brillo se ha {('aumentado' if increase else 'reducido')} al {new_level} por ciento.")
        _speak_multilang("Command completed.",
                         hi="कमांड पूरा हुआ।",
                         de="Befehl abgeschlossen.",
                         fr="Commande terminée.",
                         es="Comando completado.")
    except Exception:
        _speak_multilang("Sorry, brightness control is not available on this system.",
                         hi="माफ़ कीजिए, इस सिस्टम पर ब्राइटनेस नियंत्रण उपलब्ध नहीं है।",
                         de="Entschuldigung, die Helligkeit kann auf diesem System nicht gesteuert werden.",
                         fr="Désolé, le contrôle de la luminosité n'est pas disponible sur ce système.",
                         es="Lo siento, el control de brillo no está disponible en este sistema.")

# 🔊 Volume control using pycaw
def set_volume(level):
    try:
        level = max(0, min(100, level))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        min_vol, max_vol, _ = volume.GetVolumeRange()
        new_volume = min_vol + (level / 100.0) * (max_vol - min_vol)
        volume.SetMasterVolumeLevel(new_volume, None)

        _speak_multilang(f"Volume set to {level} percent.",
                         hi=f"वॉल्यूम {level} प्रतिशत पर सेट किया गया है।",
                         de=f"Lautstärke auf {level} Prozent eingestellt.",
                         fr=f"Le volume a été réglé à {level} pour cent.",
                         es=f"El volumen se ha ajustado al {level} por ciento.")
        _speak_multilang("Command completed.",
                         hi="कमांड पूरा हुआ।",
                         de="Befehl abgeschlossen.",
                         fr="Commande terminée.",
                         es="Comando completado.")
    except Exception:
        _speak_multilang("Sorry, I couldn’t change the volume.",
                         hi="माफ़ कीजिए, वॉल्यूम बदलने में असमर्थ हूँ।",
                         de="Entschuldigung, ich konnte die Lautstärke nicht ändern.",
                         fr="Désolé, je n'ai pas pu modifier le volume.",
                         es="Lo siento, no pude cambiar el volumen.")
