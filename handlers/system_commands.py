# 📂 handlers/system_commands.py

import os
import re
import ctypes
from difflib import get_close_matches
from command_map import COMMAND_MAP

def handle_system_commands(command: str) -> None:
    command = command.lower()

    # 🛑 Exit (Multilingual + Fuzzy)
    exit_phrases = COMMAND_MAP["exit_app"]
    matched_exit = get_close_matches(command, exit_phrases, n=1, cutoff=0.7)
    if matched_exit:
        # Use the unified closer: plays goodbye in current UI language,
        # waits for audio to finish, then closes the Tk app cleanly.
        from utils import begin_exit_with_goodbye_async
        begin_exit_with_goodbye_async()
        return


    # 🔊 Volume Control
    all_volume_phrases = []
    volume_intent_map = {}
    for intent, phrases in COMMAND_MAP.items():
        if "volume" in intent:
            for phrase in phrases:
                all_volume_phrases.append(phrase)
                volume_intent_map[phrase] = intent

    volume_match = get_close_matches(command, all_volume_phrases, n=1, cutoff=0.7)
    if volume_match:
        from utils import _speak_multilang, set_volume
        matched_intent = volume_intent_map[volume_match[0]]
        if matched_intent == "increase_volume":
            for _ in range(5):
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            _speak_multilang(
                "Volume increased.",
                hi="वॉल्यूम बढ़ा दिया है।",
                fr="Le volume a été augmenté.",
                es="He subido el volumen.",
                de="Ich habe die Lautstärke erhöht.",
                log_command="Increased volume"
            )
        elif matched_intent == "decrease_volume":
            for _ in range(5):
                ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
            _speak_multilang(
                "Volume decreased.",
                hi="वॉल्यूम कम कर दिया है।",
                fr="Le volume a été diminué.",
                es="He bajado el volumen.",
                de="Ich habe die Lautstärke verringert.",
                log_command="Decreased volume"
            )
        elif matched_intent == "mute_volume":
            ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
            _speak_multilang(
                "Volume muted.",
                hi="वॉल्यूम म्यूट कर दिया है।",
                fr="Le volume est coupé.",
                es="He silenciado el volumen.",
                de="Ich habe den Ton stummgeschaltet.",
                log_command="Muted volume"
            )
        elif matched_intent == "max_volume":
            for _ in range(10):
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            _speak_multilang(
                "Volume set to maximum.",
                hi="वॉल्यूम अधिकतम पर सेट कर दिया है।",
                fr="Volume réglé au maximum.",
                es="He puesto el volumen al máximo.",
                de="Ich habe die Lautstärke auf Maximum gestellt.",
                log_command="Max volume set"
            )
        elif matched_intent == "set_volume_to":
            match = re.search(r"(\d+)", command)
            if match:
                vol = int(match.group(1))
                set_volume(vol)
                _speak_multilang(
                    f"Setting volume to {vol} percent.",
                    hi=f"वॉल्यूम {vol} प्रतिशत पर सेट कर दिया है।",
                    fr=f"Volume réglé à {vol} pour cent.",
                    es=f"Volumen ajustado al {vol} por ciento.",
                    de=f"Lautstärke auf {vol} Prozent eingestellt.",
                    log_command=f"Set volume to {vol}%"
                )
    elif any(word in command for word in ["volume", "awaaz", "sound", "ton", "volumen", "lautstärke"]):
        from utils import _speak_multilang, set_volume
        match = re.search(r"(\d+)", command)
        if match:
            vol = int(match.group(1))
            set_volume(vol)
            _speak_multilang(
                f"Setting volume to {vol} percent.",
                hi=f"वॉल्यूम {vol} प्रतिशत पर सेट कर दिया है।",
                fr=f"Volume réglé à {vol} pour cent.",
                es=f"Volumen ajustado al {vol} por ciento.",
                de=f"Lautstärke auf {vol} Prozent eingestellt.",
                log_command=f"Set volume to {vol}%"
            )

    # 💡 Brightness Control
    all_brightness_phrases = []
    brightness_intent_map = {}
    for intent, phrases in COMMAND_MAP.items():
        if "brightness" in intent:
            for phrase in phrases:
                all_brightness_phrases.append(phrase)
                brightness_intent_map[phrase] = intent

    brightness_match = get_close_matches(command, all_brightness_phrases, n=1, cutoff=0.7)
    if brightness_match:
        from utils import _speak_multilang, change_brightness
        matched_intent = brightness_intent_map[brightness_match[0]]
        if matched_intent == "brightness_up":
            change_brightness(increase=True)
            _speak_multilang(
                "Increasing brightness.",
                hi="ब्राइटनेस बढ़ा रही हूँ।",
                fr="J’augmente la luminosité.",
                es="Estoy aumentando el brillo.",
                de="Ich erhöhe die Helligkeit.",
                log_command="Increased brightness"
            )
        elif matched_intent == "brightness_down":
            change_brightness(increase=False)
            _speak_multilang(
                "Decreasing brightness.",
                hi="ब्राइटनेस कम कर रही हूँ।",
                fr="Je diminue la luminosité.",
                es="Estoy bajando el brillo.",
                de="Ich verringere die Helligkeit.",
                log_command="Decreased brightness"
            )
        elif matched_intent == "set_brightness":
            match = re.search(r"(\d+)", command)
            if match:
                level = int(match.group(1))
                change_brightness(level=level)
                _speak_multilang(
                    f"Setting brightness to {level} percent.",
                    hi=f"ब्राइटनेस को {level} प्रतिशत पर सेट कर रही हूँ।",
                    fr=f"Luminosité réglée à {level} pour cent.",
                    es=f"He ajustado el brillo al {level} por ciento.",
                    de=f"Helligkeit auf {level} Prozent eingestellt.",
                    log_command=f"Set brightness to {level}%"
                )
    elif any(word in command for word in ["brightness", "roshni", "light", "luminosité", "brillo", "helligkeit"]):
        from utils import _speak_multilang, change_brightness
        match = re.search(r"(\d+)", command)
        if match:
            level = int(match.group(1))
            change_brightness(level=level)
            _speak_multilang(
                f"Setting brightness to {level} percent.",
                hi=f"ब्राइटनेस को {level} प्रतिशत पर सेट कर रही हूँ।",
                fr=f"Luminosité réglée à {level} pour cent.",
                es=f"He ajustado el brillo al {level} por ciento.",
                de=f"Helligkeit auf {level} Prozent eingestellt.",
                log_command=f"Set brightness to {level}%"
            )

    # 💻 System Control
    from utils import _speak_multilang
    matched_shutdown = get_close_matches(command, COMMAND_MAP["shutdown_system"], n=1, cutoff=0.7)
    matched_restart = get_close_matches(command, COMMAND_MAP["restart_system"], n=1, cutoff=0.7)
    matched_sleep = get_close_matches(command, COMMAND_MAP["sleep_system"], n=1, cutoff=0.7)
    matched_lock = get_close_matches(command, COMMAND_MAP["lock_system"], n=1, cutoff=0.7)
    matched_logout = get_close_matches(command, COMMAND_MAP["logout_system"], n=1, cutoff=0.7)

    if matched_shutdown:
        _speak_multilang(
            "Shutting down the system now.",
            hi="सिस्टम को बंद कर रही हूँ।",
            fr="J’éteins le système maintenant.",
            es="Apagando el sistema ahora.",
            de="Ich fahre das System jetzt herunter.",
            log_command="Shutdown system"
        )
        os.system("shutdown /s /t 1")
    elif matched_restart:
        _speak_multilang(
            "Restarting the system.",
            hi="सिस्टम को रीस्टार्ट कर रही हूँ।",
            fr="Je redémarre le système.",
            es="Reiniciando el sistema.",
            de="Ich starte das System neu.",
            log_command="Restart system"
        )
        os.system("shutdown /r /t 1")
    elif matched_sleep:
        _speak_multilang(
            "Putting the computer to sleep.",
            hi="कंप्यूटर को स्लीप मोड में डाल रही हूँ।",
            fr="Je mets l’ordinateur en veille.",
            es="Poniendo el ordenador en suspensión.",
            de="Ich versetze den Computer in den Ruhezustand.",
            log_command="Sleep mode triggered"
        )
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    elif matched_lock:
        _speak_multilang(
            "Locking the screen now.",
            hi="स्क्रीन लॉक कर रही हूँ।",
            fr="Je verrouille l’écran maintenant.",
            es="Bloqueando la pantalla ahora.",
            de="Ich sperre jetzt den Bildschirm.",
            log_command="Screen locked"
        )
        os.system("rundll32.exe user32.dll,LockWorkStation")
    elif matched_logout:
        _speak_multilang(
            "Logging you out now.",
            hi="आपको लॉग आउट कर रही हूँ।",
            fr="Je vous déconnecte maintenant.",
            es="Cerrando tu sesión ahora.",
            de="Ich melde dich jetzt ab.",
            log_command="User logged out"
        )
        os.system("shutdown /l")
