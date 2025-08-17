# 📂 handlers/alarm_commands.py

import re
import time
import threading
import datetime
import dateparser
import logging
from difflib import get_close_matches

from command_map import COMMAND_MAP

# 📘 Configure logger
logger = logging.getLogger(__name__)

# 🔁 Background alarm/reminder thread
def _schedule_checker(hour: int, minute: int, task_type: str, task: str = ""):
    from utils import _speak_multilang

    while True:
        now = datetime.datetime.now()
        if now.hour >= hour and now.minute >= minute:
            logger.info(f"[✅ {task_type.capitalize()} Triggered] {task or f'{hour:02d}:{minute:02d}'}")
            if task_type == "alarm":
                _speak_multilang(
                    f"It's {hour:02d}:{minute:02d}. Time to wake up!",
                    hi=f"{hour:02d}:{minute:02d} बज गए हैं। अब उठने का समय हो गया है!",
                    de=f"Es ist {hour:02d}:{minute:02d}. Zeit, aufzuwachen!",
                    fr=f"Il est {hour:02d}:{minute:02d}. Il est temps de te réveiller !",
                    es=f"Son las {hour:02d}:{minute:02d}. ¡Es hora de levantarte!"
                )
            elif task_type == "reminder":
                _speak_multilang(
                    f"Reminder: {task}",
                    hi=f"रिमाइंडर: {task}",
                    de=f"Erinnerung: {task}",
                    fr=f"Rappel : {task}",
                    es=f"Recordatorio: {task}"
                )
            break
        time.sleep(30)

# ⏰ Alarm Command Handler
def handle_set_alarm(command: str):
    from utils import _speak_multilang

    match = re.search(r"(\d{1,2})[:\s](\d{1,2})", command)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        threading.Thread(target=_schedule_checker, args=(hour, minute, "alarm"), daemon=True).start()
        logger.info(f"[⏰ Alarm Set] {hour:02d}:{minute:02d}")
        _speak_multilang(
            f"Alarm set for {hour:02d}:{minute:02d}.",
            hi=f"{hour:02d}:{minute:02d} के लिए अलार्म सेट किया गया है।",
            de=f"Ich habe den Alarm für {hour:02d}:{minute:02d} eingestellt.",
            fr=f"J’ai réglé l’alarme pour {hour:02d} h {minute:02d}.",
            es=f"He configurado la alarma para las {hour:02d}:{minute:02d}."
        )
    else:
        logger.warning("[⏰ Alarm Parse Failed] No valid time found.")
        _speak_multilang(
            "I couldn't understand the alarm time.",
            hi="मैं अलार्म का समय नहीं समझ पाई।",
            de="Désolée, je n’ai pas compris l’heure de l’alarme.",
            fr="Désolée, je n’ai pas compris l’heure de l’alarme.",
            es="Lo siento, no entendí la hora de la alarma."
        )

# 🔔 Reminder Command Handler
def handle_set_reminder(command: str):
    from utils import _speak_multilang

    match = re.search(r"(\d{1,2})[:\s](\d{1,2}).*?(to|कि|à|para|um)\s(.+)", command)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        task = match.group(4).strip()
        threading.Thread(target=_schedule_checker, args=(hour, minute, "reminder", task), daemon=True).start()
        logger.info(f"[🔔 Reminder Set] {hour:02d}:{minute:02d} → {task}")
        _speak_multilang(
            f"Reminder set for {hour:02d}:{minute:02d} to {task}.",
            hi=f"{hour:02d}:{minute:02d} बजे के लिए रिमाइंडर सेट किया गया है: {task}",
            de=f"Ich habe eine Erinnerung um {hour:02d}:{minute:02d} eingerichtet: {task}",
            fr=f"J’ai créé un rappel à {hour:02d} h {minute:02d} pour : {task}",
            es=f"He configurado un recordatorio a las {hour:02d}:{minute:02d} para: {task}"
        )
    else:
        logger.warning("[🔔 Reminder Parse Failed] Invalid time or task.")
        _speak_multilang(
            "I couldn't understand the reminder details.",
            hi="मैं रिमाइंडर की जानकारी नहीं समझ पाई।",
            de="Désolée, je n’ai pas compris les détails du rappel.",
            fr="Désolée, je n’ai pas compris les détails du rappel.",
            es="Lo siento, no entendí los detalles del recordatorio."
        )
