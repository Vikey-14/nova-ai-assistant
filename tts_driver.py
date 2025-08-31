# tts_driver.py
"""
Natural, Linux-only TTS routing for Nova.

Linux/WSL:
  - English -> Edge Neural TTS (male, e.g. en-US-GuyNeural)
  - Others  -> gTTS (female)

Windows/mac:
  - pyttsx3 (unchanged)

Env knobs (Linux/WSL only unless stated):
  NOVA_TTS=gtts|edge|pyttsx3     -> force a specific engine for ALL languages (discouraged)
  NOVA_TTS_VOICE_EN=male|female  -> English voice preference on Linux/WSL (default=male)
  NOVA_TTS_EDGE_VOICE_EN         -> set a specific Edge voice, e.g. en-GB-RyanNeural
  NOVA_TTS_RATE_EN               -> Edge Neural rate for English, e.g. "+12%" or "-10%" (default "+0%")

API expected by utils.py:
  get_tts() -> object with methods: speak(text, lang_code="en"), stop()
"""

from __future__ import annotations
import os
import sys
import shutil
import tempfile
import subprocess
import threading
from typing import Optional, List


# ---------------- Base ----------------
class _BaseTTS:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()

    def speak(self, text: str, lang_code: str = "en") -> None:  # pragma: no cover
        raise NotImplementedError

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def _run_and_wait(self, cmd: List[str]) -> None:
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        try:
            self._proc.wait()
        finally:
            self._proc = None

    # Robust MP3 player chain that works inside PyInstaller bundles.
    # Returns True if playback was attempted successfully.
    def _play_mp3(self, mp3_path: str) -> bool:
        linuxish = sys.platform.startswith("linux") or _is_wsl()
        if linuxish:
            # Prefer system players (PyInstaller-safe)
            for candidate in ("ffplay", "/usr/bin/ffplay", "/bin/ffplay"):
                exe = shutil.which(candidate) or (candidate if os.path.exists(candidate) else None)
                if exe:
                    self._run_and_wait([exe, "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path])
                    return True
            for candidate in ("mpg123", "/usr/bin/mpg123", "/bin/mpg123"):
                exe = shutil.which(candidate) or (candidate if os.path.exists(candidate) else None)
                if exe:
                    self._run_and_wait([exe, "-q", mp3_path])
                    return True
            # Fallbacks commonly present on Linux
            if shutil.which("paplay"):
                self._run_and_wait(["paplay", mp3_path]); return True
            if shutil.which("aplay"):
                self._run_and_wait(["aplay", "-q", mp3_path]); return True
            return False  # do NOT fall back to playsound in Linux/WSL bundles

        # Non-Linux fallback (Windows/macOS)
        try:
            from playsound import playsound
            playsound(mp3_path)  # blocking
            return True
        except Exception:
            return False


# ------------- Helpers ----------------
def _is_wsl() -> bool:
    try:
        return ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in os.uname().release.lower())
    except Exception:
        try:
            import platform
            return ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in platform.release().lower())
        except Exception:
            return False


def _normalize_lang(code: str | None, default: str = "en") -> str:
    c = (code or default).strip()
    if not c:
        return default
    c = c.replace("_", "-")
    parts = c.split("-", 1)
    base = parts[0].lower()
    if len(parts) == 2:
        region = parts[1].upper()
        return f"{base}-{region}"
    return base


def _is_english(code: str | None) -> bool:
    return _normalize_lang(code).lower().startswith("en")


# ------------- Engines ----------------
class EdgeSynth(_BaseTTS):
    """
    Microsoft Edge Neural TTS (online). Natural, multiple voices.
    Used for ENGLISH on Linux/WSL so we get a clear male voice.
    """
    def __init__(self) -> None:
        super().__init__()
        try:
            import edge_tts  # noqa: F401
            self._edge_ok = True
        except Exception:
            self._edge_ok = False

    # Returns True if audio was actually played; False otherwise.
    def speak(self, text: str, lang_code: str = "en") -> bool:  # type: ignore[override]
        if not text:
            return False
        if not self._edge_ok:
            return False

        # Only use Edge for English
        if not _is_english(lang_code):
            return False

        # Pick male English neural voice unless overridden; optional speed tweak
        voice = os.environ.get("NOVA_TTS_EDGE_VOICE_EN", "").strip() or "en-US-GuyNeural"
        rate = os.environ.get("NOVA_TTS_RATE_EN", "+0%").strip() or "+0%"

        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        played = False
        try:
            import asyncio
            from edge_tts import Communicate

            async def _run() -> None:
                comm = Communicate(text, voice=voice, rate=rate)
                await comm.save(mp3_path)

            # robust run (handles “event loop already running”)
            try:
                asyncio.run(_run())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(_run())
                finally:
                    loop.close()

            with self._lock:
                self.stop()
                played = self._play_mp3(mp3_path)
        except Exception:
            played = False
        finally:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass
        return played


class GTTSSynth(_BaseTTS):
    """Google Translate TTS (online). Natural, single default female voice per language."""
    def speak(self, text: str, lang_code: str = "en") -> None:
        if not text:
            return

        # --- Linux/WSL: for English, prefer Edge Neural male unless explicitly disabled ---
        try:
            linuxish = sys.platform.startswith("linux") or _is_wsl()
            prefer_en = (os.environ.get("NOVA_TTS_VOICE_EN") or "male").strip().lower()
            is_en = (lang_code or "en").lower().startswith("en")
            if linuxish and is_en and prefer_en != "female":
                e = EdgeSynth()
                if getattr(e, "_edge_ok", False):
                    if e.speak(text, "en-US"):  # only return if Edge actually played
                        return
        except Exception:
            # Fall through to gTTS on any Edge error
            pass

        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            from gtts import gTTS
            base = _normalize_lang(lang_code).split("-", 1)[0]  # 'en', 'hi', 'fr', ...
            gTTS(text=text, lang=base).save(mp3_path)
            with self._lock:
                self.stop()
                self._play_mp3(mp3_path)
        finally:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass


class Pyttsx3Synth(_BaseTTS):
    """Offline, great on Windows (SAPI). We keep this for Windows/mac unchanged."""
    def __init__(self) -> None:
        super().__init__()
        import pyttsx3
        self._engine = pyttsx3.init()

    def speak(self, text: str, lang_code: str = "en") -> None:
        if not text:
            return
        with self._lock:
            self.stop()
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                pass

    def stop(self) -> None:
        with self._lock:
            try:
                self._engine.stop()
            except Exception:
                pass


# ------------- Router -----------------
def get_tts() -> _BaseTTS:
    """
    Router rules:
      - Linux/WSL:
          English -> EdgeSynth (male, natural) unless NOVA_TTS_VOICE_EN=female
          Others  -> GTTSSynth (female, natural)
          You can override globally with NOVA_TTS.
      - Windows/mac:
          pyttsx3 (unchanged), unless NOVA_TTS forces a different engine.
    """
    prefer = (os.environ.get("NOVA_TTS") or "").strip().lower()
    linuxish = sys.platform.startswith("linux") or _is_wsl()

    if linuxish:
        # Global overrides if you *really* want them
        if prefer == "pyttsx3":
            try:
                return Pyttsx3Synth()
            except Exception:
                return GTTSSynth()
        if prefer == "edge":
            e = EdgeSynth()
            if getattr(e, "_edge_ok", False):
                return e
            return GTTSSynth()
        if prefer == "gtts":
            return GTTSSynth()
        # Default on Linux/WSL: return GTTSSynth; English will auto-route to Edge inside GTTSSynth
        return GTTSSynth()

    # Windows/mac default
    if prefer == "gtts":
        return GTTSSynth()
    if prefer == "edge":
        e = EdgeSynth()
        if getattr(e, "_edge_ok", False):
            return e
    try:
        return Pyttsx3Synth()
    except Exception:
        return GTTSSynth()


# Convenience used by utils.py (optional)
def speak_natural(text: str, lang_code: str = "en") -> None:
    """
    On Linux/WSL:
      - If lang is English and NOVA_TTS_VOICE_EN != 'female' -> Edge (male)
      - Else -> gTTS (female)
    Elsewhere:
      - Defer to get_tts() default
    """
    linuxish = sys.platform.startswith("linux") or _is_wsl()
    if linuxish:
        en_pref = (os.environ.get("NOVA_TTS_VOICE_EN") or "male").strip().lower()
        if _is_english(lang_code) and en_pref != "female":
            e = EdgeSynth()
            if getattr(e, "_edge_ok", False) and e.speak(text, "en-US"):
                return
        GTTSSynth().speak(text, lang_code)
        return
    get_tts().speak(text, lang_code)
