# 📂 handlers/alarm_commands.py — SAY→SHOW + typed/voice follow-ups + multilingual + barge-in

import re
import time
import threading
import datetime as _dt
import logging
from typing import Optional, Tuple

# Natural language times like "tomorrow 7am", "in 20 minutes"
try:
    import dateparser
except Exception:
    dateparser = None

# Nova helpers (centralized)
from say_show import say_show                      # TTS first → then bubble (localized)
from followup import await_followup                # typed/voice follow-ups; barge-in safe
from utils import selected_language, listen_command

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Localization helpers
# ─────────────────────────────────────────────────────────────────────────────
def _lang() -> str:
    return (selected_language or "en").lower()

def _pick(d: dict) -> str:
    return d.get(_lang(), d.get("en", ""))

# Multilingual follow-up prompts & messages
_PROMPTS = {
    "ask_alarm_time": {
        "en": "What time should I set the alarm for? You can type or say it.",
        "hi": "अलार्म किस समय सेट करूँ? आप टाइप करके या बोलकर बता सकते हैं।",
        "de": "Für welche Uhrzeit soll ich den Alarm stellen? Du kannst tippen oder sprechen.",
        "fr": "Pour quelle heure dois-je régler l’alarme ? Vous pouvez écrire ou parler.",
        "es": "¿Para qué hora debo configurar la alarma? Puedes escribir o hablar.",
    },
    "ask_reminder_time": {
        "en": "When should I remind you? You can type or say it.",
        "hi": "मैं आपको कब याद दिलाऊँ? आप टाइप करके या बोलकर बता सकते हैं।",
        "de": "Wann soll ich dich erinnern? Du kannst tippen oder sprechen.",
        "fr": "Quand dois-je vous le rappeler ? Vous pouvez écrire ou parler.",
        "es": "¿Cuándo debo recordártelo? Puedes escribir o hablar.",
    },
    "ask_reminder_task": {
        "en": "What should I remind you about? You can type or say it.",
        "hi": "किस बारे में याद दिलाना है? आप टाइप करके या बोलकर बता सकते हैं।",
        "de": "Woran soll ich dich erinnern? Du kannst tippen oder sprechen.",
        "fr": "De quoi dois-je vous rappeler ? Vous pouvez écrire ou parler.",
        "es": "¿Sobre qué debo recordarte? Puedes escribir o hablar.",
    },
    "didnt_get_it": {
        "en": "I couldn't get that.",
        "hi": "मैं समझ नहीं पाई।",
        "de": "Ich habe das nicht verstanden.",
        "fr": "Je n’ai pas compris.",
        "es": "No entendí eso.",
    },
    "alarm_set": {
        "en": "Done. Alarm set for {t}.",
        "hi": "हो गया। {t} के लिए अलार्म सेट कर दिया है।",
        "de": "Fertig. Alarm für {t} gestellt.",
        "fr": "C’est fait. Alarme réglée pour {t}.",
        "es": "Listo. Alarma configurada para {t}.",
    },
    "reminder_set": {
        "en": "Done. Reminder set for {t}: {task}.",
        "hi": "हो गया। {t} के लिए रिमाइंडर सेट किया: {task}।",
        "de": "Fertig. Erinnerung für {t} eingerichtet: {task}.",
        "fr": "C’est fait. Rappel réglé pour {t} : {task}.",
        "es": "Listo. Recordatorio configurado para {t}: {task}.",
    },
    # Lines spoken/shown when the scheduled time arrives:
    "alarm_ring": {
        "en": "It's {t}. Time to wake up!",
        "hi": "{t} बज गए हैं। अब उठने का समय हो गया है!",
        "de": "Es ist {t}. Zeit, aufzuwachen!",
        "fr": "Il est {t}. Il est temps de te réveiller !",
        "es": "Son las {t}. ¡Es hora de levantarte!",
    },
    "reminder_fire": {
        "en": "Reminder: {task}",
        "hi": "रिमाइंडर: {task}",
        "de": "Erinnerung: {task}",
        "fr": "Rappel : {task}",
        "es": "Recordatorio: {task}",
    },
}

def _say_then_show_prompt(key: str) -> str:
    """
    SAY→SHOW once (localized) and return the localized string for passing
    into await_followup(prompt=...).
    """
    p = _PROMPTS[key]
    say_show(p["en"], hi=p.get("hi"), de=p.get("de"), fr=p.get("fr"), es=p.get("es"), title="Nova")
    return _pick(p)

def _say_msg(key: str, **fmt):
    """Speak + show a localized message with formatting placeholders."""
    p = _PROMPTS[key]
    say_show(
        (p["en"]).format(**fmt),
        hi=(p.get("hi", "") or "").format(**fmt),
        de=(p.get("de", "") or "").format(**fmt),
        fr=(p.get("fr", "") or "").format(**fmt),
        es=(p.get("es", "") or "").format(**fmt),
        title="Nova",
    )

# ─────────────────────────────────────────────────────────────────────────────
# Time parsing helpers
# ─────────────────────────────────────────────────────────────────────────────
def _parse_time_any(text: str, now: Optional[_dt.datetime] = None) -> Optional[_dt.datetime]:
    """
    Parse many formats: '7:30', '07 30', 'tomorrow 7am', 'in 20 minutes', 'next monday 8pm'
    Returns an absolute datetime in the future (rolls forward if needed).
    """
    if not text:
        return None
    now = now or _dt.datetime.now()

    # 1) dateparser (relative + absolute)
    if dateparser:
        try:
            dt = dateparser.parse(
                text,
                settings={"RELATIVE_BASE": now, "PREFER_DATES_FROM": "future"}
            )
        except Exception:
            dt = None
        if dt:
            return dt

    # 2) HH[: ]MM
    m = re.search(r"\b(\d{1,2})[:\s](\d{2})\b", text)
    if m:
        h = int(m.group(1)); mi = int(m.group(2))
        cand = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if cand <= now:
            cand += _dt.timedelta(days=1)
        return cand

    # 3) H am/pm
    m2 = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text, flags=re.IGNORECASE)
    if m2:
        h = int(m2.group(1)); ampm = m2.group(2).lower()
        if ampm == "pm" and h != 12: h += 12
        if ampm == "am" and h == 12: h = 0
        cand = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if cand <= now:
            cand += _dt.timedelta(days=1)
        return cand

    return None

def _format_hhmm(dt: _dt.datetime) -> str:
    return dt.strftime("%H:%M")

# ─────────────────────────────────────────────────────────────────────────────
# Scheduler (runs in a background thread; still uses SAY→SHOW for consistency)
# ─────────────────────────────────────────────────────────────────────────────
def _schedule_worker(at: _dt.datetime, task_type: str, task: str = ""):
    now = _dt.datetime.now()
    delay = max(0.0, (at - now).total_seconds())
    logger.info(f"[⏳ Scheduled] {task_type} at {at.isoformat()} (in {int(delay)}s) | {task}")
    try:
        time.sleep(delay)
    except Exception:
        pass

    tdisp = _format_hhmm(at)
    if task_type == "alarm":
        _say_msg("alarm_ring", t=tdisp)
    elif task_type == "reminder":
        _say_msg("reminder_fire", task=task)

# ─────────────────────────────────────────────────────────────────────────────
# Public handlers (called by your COMMAND_REGISTRY)
# ─────────────────────────────────────────────────────────────────────────────
def handle_set_alarm(command: str):
    """
    Sets an alarm from natural language.
    If time is missing/unclear → SAY→SHOW prompt, then await typed OR voice follow-up.
    """
    now = _dt.datetime.now()
    when = _parse_time_any(command, now=now)

    # Ask once if missing (SAY→SHOW first; then await without re-speaking/re-showing)
    if not when:
        prompt = _say_then_show_prompt("ask_alarm_time")
        answer = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,        # no re-TTS; barge-in handled inside await_followup
            show_fn=lambda *_a, **_k: None,         # no duplicate bubble
            listen_fn=listen_command,               # Vosk streaming; stops lingering TTS on VAD start
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not answer:
            _say_msg("didnt_get_it")
            return
        when = _parse_time_any(answer, now=now)

    if not when:
        # Still unclear after follow-up
        say_show(
            "That still didn’t look like a time. Try “tomorrow 7 am”.",
            hi="यह समय जैसा नहीं लगा। जैसे “कल सुबह 7 बजे” कहें।",
            de="Das sah immer noch nicht nach einer Uhrzeit aus. Zum Beispiel: „morgen 7 Uhr“.",
            fr="Cela ne ressemble toujours pas à une heure. Essayez « demain 7 h ».",
            es="Aún no parece una hora. Prueba « mañana a las 7 am ».",
            title="Nova",
        )
        return

    threading.Thread(target=_schedule_worker, args=(when, "alarm", ""), daemon=True).start()

    tdisp = _format_hhmm(when)
    _say_msg("alarm_set", t=tdisp)

def handle_set_reminder(command: str):
    """
    Sets a reminder like “remind me at 7:30 to call mom”.
    If time or task is missing → follow-ups (typed/voice), SAY→SHOW first.
    """
    now = _dt.datetime.now()

    # Heuristic split: “… at 7:30 to call mom” / multilingual joiners
    m = re.search(
        r"\b(?:at|um|à|a|para|पर|को)?\s*(.+?)\s*(?:to|about|कि|के लिए|pour|para)\s+(.+)$",
        command, flags=re.IGNORECASE
    )
    when_text: Optional[str] = None
    task: Optional[str] = None
    if m:
        when_text = m.group(1).strip()
        task = m.group(2).strip()

    # Fallback: scan short windows to find a time-ish phrase
    if not when_text:
        tokens = command.split()
        for i in range(len(tokens)):
            for j in range(i + 1, min(len(tokens), i + 6)):  # up to 5-word window
                cand = " ".join(tokens[i:j])
                if _parse_time_any(cand, now=now):
                    when_text = cand
                    task = command.replace(cand, "", 1).strip(" ,.;:-")
                    break
            if when_text:
                break

    when = _parse_time_any(when_text, now=now) if when_text else None

    # Ask for missing pieces (time first, then task) — SAY→SHOW, then await
    if not when:
        prompt = _say_then_show_prompt("ask_reminder_time")
        ans_time = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not ans_time:
            _say_msg("didnt_get_it"); return
        when = _parse_time_any(ans_time, now=now)

    if not task:
        prompt = _say_then_show_prompt("ask_reminder_task")
        ans_task = await_followup(
            prompt,
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True, allow_voice=True, timeout=18.0
        )
        if not ans_task:
            _say_msg("didnt_get_it"); return
        task = ans_task.strip()

    if not when:
        say_show(
            "That still didn’t look like a time. Try “today 6 pm” or “in 20 minutes”.",
            hi="यह समय जैसा नहीं लगा। “आज शाम 6 बजे” या “20 मिनट बाद” जैसा कहें।",
            de="Das sah nicht nach einer Zeit aus. Versuche „heute 18 Uhr“ oder „in 20 Minuten“.",
            fr="Cela ne ressemble pas à une heure. Essayez « aujourd’hui 18 h » ou « dans 20 minutes ».",
            es="Eso no parece una hora. Prueba « hoy 6 pm » o « en 20 minutos ».",
            title="Nova",
        )
        return

    threading.Thread(target=_schedule_worker, args=(when, "reminder", task or ""), daemon=True).start()

    tdisp = _format_hhmm(when)
    _say_msg("reminder_set", t=tdisp, task=task or "")
