# followup.py
from threading import Event
from typing import Optional
import time

# Single outstanding follow-up at a time
FOLLOWUP_WAIT = {
    "active": False,
    "prompt": None,
    "text": None,
    "event": None,
    "voice_ok": True,
    "typed_ok": True,
}

def start_followup(prompt: str, allow_typed: bool = True, allow_voice: bool = True):
    ev = Event()
    FOLLOWUP_WAIT.update({
        "active": True,
        "prompt": prompt,
        "text": None,
        "event": ev,
        "voice_ok": allow_voice,
        "typed_ok": allow_typed
    })
    return ev

def submit_typed_followup(text: str):
    if FOLLOWUP_WAIT.get("active") and FOLLOWUP_WAIT.get("typed_ok"):
        FOLLOWUP_WAIT["text"] = (text or "").strip()
        ev = FOLLOWUP_WAIT.get("event")
        if ev:
            ev.set()
        return True
    return False

def await_followup(
    prompt: str,
    speak_fn,
    show_fn,
    listen_fn=None,
    allow_typed: bool = True,
    allow_voice: bool = True,
    timeout: float = 18.0
) -> Optional[str]:
    """
    Say ΓåÆ then Show:
      1) Nova speaks the prompt (blocking if supported).
      2) When speech ends, the UI bubble appears.
      3) We barge-in: we ensure TTS is stopped before opening the mic, and
         (optionally) again when speech starts (if your listener supports a hook).
      4) We wait for a typed reply (submit_typed_followup) or a voice reply.

    Returns the raw string, or None on timeout.
    """
    ev = start_followup(prompt, allow_typed=allow_typed, allow_voice=allow_voice)
    try:
        # ΓöÇΓöÇ SAY (prefer blocking so bubble pops after speech finishes)
        try:
            # If your speak() supports a blocking flag, this will ensure bubble appears after TTS.
            speak_fn(prompt, blocking=True)  # type: ignore[call-arg]
        except TypeError:
            # Older speak() without blocking flag ΓÇô best effort.
            speak_fn(prompt)
            # Small grace period so the bubble doesn't jump ahead of speech on very short prompts.
            time.sleep(0.05)
        except Exception:
            # If speak fails, continue gracefully.
            pass

        # ΓöÇΓöÇ SHOW (bubble after speech)
        try:
            show_fn("Nova", prompt)   # correct casing as per your UI
        except Exception:
            pass

        # ≡ƒöæ Barge-in: stop any lingering TTS *before* we start listening
        try:
            from utils import stop_speaking
            stop_speaking()
        except Exception:
            pass

        start = time.time()

        # Optional: if your listen_fn supports an on_start hook, stop TTS immediately on VAD.
        def _on_speech_start():
            try:
                from utils import stop_speaking
                stop_speaking()
            except Exception:
                pass

        while time.time() - start < timeout:
            # typed path (GUI)
            if FOLLOWUP_WAIT.get("text"):
                return FOLLOWUP_WAIT["text"]

            # voice path (ASR)
            if listen_fn and allow_voice and (time.time() - start) > 0.0:
                try:
                    # Try modern signature with timeout + on_start barge-in hook
                    heard = listen_fn(timeout=max(0.5, timeout - (time.time() - start)),
                                      allow_partial=False,
                                      on_start=_on_speech_start)
                except TypeError:
                    # Fallback to older signature(s)
                    try:
                        heard = listen_fn(timeout=max(0.5, timeout - (time.time() - start)))
                    except TypeError:
                        heard = listen_fn()
                if heard:
                    return heard

            ev.wait(0.2)

        return None
    finally:
        FOLLOWUP_WAIT.update({
            "active": False,
            "prompt": None,
            "text": None,
            "event": None
        })

# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# New reusable helpers: yes/no and "Did you mean ΓÇª?"
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def ask_yes_no(
    prompt_en: str,
    *,
    hi: Optional[str] = None,
    fr: Optional[str] = None,
    es: Optional[str] = None,
    de: Optional[str] = None,
    timeout: float = 12.0,
    lang: Optional[str] = None
) -> Optional[bool]:
    """
    Speak + show a yes/no question (Nova bubble), accept typed or voice reply.
    Returns:
      True  ΓåÆ yes
      False ΓåÆ no
      None  ΓåÆ timeout/unclear
    """
    from utils import _speak_multilang, speak, listen_command, selected_language
    from gui_interface import nova_gui
    from fuzzy_utils import normalize_yes_no

    # SAY (multilingual TTS lines), then SHOW in EN per your style
    _speak_multilang(
        prompt_en,
        hi=hi or prompt_en,
        fr=fr or prompt_en,
        es=es or prompt_en,
        de=de or prompt_en,
    )

    # We still want the bubble to appear only after speech finishes:
    try:
        speak(prompt_en, blocking=True)  # ensure ΓÇ£say then showΓÇ¥ timing matches main theme
    except TypeError:
        speak(prompt_en)
    except Exception:
        pass

    try:
        nova_gui.show_message("Nova", prompt_en)
    except Exception:
        pass

    # Now use await_followup (it will NOT re-say; it will just show again, which is a no-op)
    ans = await_followup(
        prompt_en,
        speak_fn=lambda *_args, **_kwargs: None,  # don't re-speak inside await_followup
        show_fn=lambda who, msg: nova_gui.show_message("Nova", msg),
        listen_fn=listen_command,
        allow_typed=True,
        allow_voice=True,
        timeout=timeout,
    )

    yn = normalize_yes_no(ans or "", lang=(lang or selected_language))
    return yn  # True / False / None

def confirm_did_you_mean(
    candidate: str,
    *,
    timeout: float = 12.0,
    lang: Optional[str] = None
) -> Optional[bool]:
    """
    Convenience wrapper to ask: ΓÇ£Did you mean ΓÇÿ<candidate>ΓÇÖ?ΓÇ¥
    Localized voice lines; EN shown in bubble per your UI style.
    Returns True/False/None.
    """
    en = f"Did you mean ΓÇ£{candidate}ΓÇ¥?"
    hi = f"αñòαÑìαñ»αñ╛ αñåαñ¬αñòαñ╛ αñ«αññαñ▓αñ¼ ΓÇ£{candidate}ΓÇ¥ αñÑαñ╛?"
    fr = f"Vouliez-vous dire ΓÇ£{candidate}ΓÇ¥ ?"
    es = f"┬┐Quisiste decir ΓÇ£{candidate}ΓÇ¥?"
    de = f"Meintest du ΓÇ₧{candidate}ΓÇ£?"

    return ask_yes_no(en, hi=hi, fr=fr, es=es, de=de, timeout=timeout, lang=lang)
