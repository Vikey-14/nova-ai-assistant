# tts_driver.py
"""
Nova TTS router.

Linux/WSL:
  - English -> Edge Neural TTS (male, e.g. en-US-GuyNeural)
              -> Piper male (if installed)
              -> gTTS (last resort)
  - HI/DE/ES/FR -> Edge Neural female (if available) -> gTTS (female default)

Windows:
  - EN -> male (prefer Microsoft David Desktop; backup other male EN; then Edge Neural male)
  - HI/DE/ES/FR -> female (Edge Neural female fallback; then gTTS)
  - No rate change unless NOVA_TTS_RATE_WIN is set.

macOS:
  - EN -> male (prefer Alex, then Daniel; fallback `say -v Alex`; then Edge Neural male)
  - HI/DE/ES/FR -> female (prefer system female; fallback `say -v` female; then Edge Neural female; then gTTS)
  - No rate change unless NOVA_TTS_RATE_MAC is set.

API expected by utils.py:
  get_tts() -> object with .speak(text, lang_code="en") and .stop()
"""

from __future__ import annotations
import os, sys, shutil, tempfile, subprocess, threading
from typing import Optional, List

# ---------------- Shared voice maps ----------------
EDGE_MALE_EN = os.environ.get("NOVA_TTS_EDGE_VOICE_EN", "en-US-GuyNeural")
EDGE_FEMALE = {
    "hi": "hi-IN-SwaraNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
}

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
                try: self._proc.terminate()
                except Exception: pass
                try: self._proc.kill()
                except Exception: pass
            self._proc = None

    def _run_and_wait(self, cmd: List[str]) -> None:
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
        )
        try: self._proc.wait()
        finally: self._proc = None

    # Plays wav/mp3 using system players (Linux) or playsound (Win/Mac).
    def _play_audio(self, path: str) -> bool:
        linuxish = sys.platform.startswith("linux") or _is_wsl()
        if linuxish:
            for candidate in ("ffplay", "/usr/bin/ffplay", "/bin/ffplay"):
                exe = shutil.which(candidate) or (candidate if os.path.exists(candidate) else None)
                if exe:
                    self._run_and_wait([exe, "-nodisp", "-autoexit", "-loglevel", "quiet", path])
                    return True
            if shutil.which("paplay"):
                self._run_and_wait(["paplay", path]); return True
            if shutil.which("aplay"):
                self._run_and_wait(["aplay", "-q", path]); return True
            if shutil.which("mpg123") and path.lower().endswith(".mp3"):
                self._run_and_wait(["mpg123", "-q", path]); return True
            return False
        try:
            from playsound import playsound
            playsound(path)
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
    if not c: return default
    c = c.replace("_", "-")
    parts = c.split("-", 1)
    base = parts[0].lower()
    if len(parts) == 2:
        region = parts[1].upper()
        return f"{base}-{region}"
    return base

def _is_english(code: str | None) -> bool:
    return _normalize_lang(code).lower().startswith("en")

# ------------- Edge Neural ----------------
class EdgeSynth(_BaseTTS):
    """Microsoft Edge Neural TTS (online)."""
    def __init__(self) -> None:
        super().__init__()
        try:
            import edge_tts  # noqa: F401
            self._edge_ok = True
        except Exception:
            self._edge_ok = False

    def speak(self, text: str, lang_code: str = "en",
              *, voice: Optional[str] = None, rate: Optional[str] = None) -> bool:
        if not text or not self._edge_ok: return False
        if voice is None and _is_english(lang_code):
            voice = EDGE_MALE_EN
        rate = (rate or os.environ.get("NOVA_TTS_RATE_EN", "+0%").strip() or "+0%")

        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        played = False
        try:
            import asyncio
            from edge_tts import Communicate
            async def _run() -> None:
                await Communicate(text, voice=voice, rate=rate).save(mp3_path)
            try:
                asyncio.run(_run())
            except RuntimeError:
                loop = __import__("asyncio").new_event_loop()
                try: loop.run_until_complete(_run())
                finally: loop.close()
            with self._lock:
                self.stop()
                played = self._play_audio(mp3_path)
        except Exception:
            played = False
        finally:
            try: os.unlink(mp3_path)
            except Exception: pass
        return played

# ------------- Piper (Linux male EN fallback) ----------------
class PiperSynth(_BaseTTS):
    """Piper neural TTS (offline). Used as Linux EN male fallback."""
    CANDIDATE_MODELS = [
        "en_US-ryan-high.onnx", "en_US-ryan-medium.onnx",
        "en_US-kyle-high.onnx", "en_US-joe-high.onnx",
        "en_GB-northern_english_male-medium.onnx", "en_GB-ryan-high.onnx",
    ]
    SEARCH_DIRS = [
        "/usr/share/piper/voices",
        "/usr/local/share/piper/voices",
        str(os.path.expanduser("~/.local/share/piper/voices")),
        "/usr/share/piper",
        "/usr/local/share/piper",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._piper = os.environ.get("NOVA_PIPER_BIN") or shutil.which("piper")
        self._model = os.environ.get("NOVA_PIPER_VOICE_EN") or self._find_model()

    def _find_model(self) -> Optional[str]:
        for d in self.SEARCH_DIRS:
            for name in self.CANDIDATE_MODELS:
                p = os.path.join(d, name)
                if os.path.exists(p):
                    return p
        return None

    def speak(self, text: str, lang_code: str = "en") -> bool:
        if not text or not _is_english(lang_code): return False
        if not self._piper or not self._model: return False
        fd, wav_path = tempfile.mkstemp(suffix=".wav"); os.close(fd)
        ok = False
        try:
            # echo "text" | piper -m model -f out.wav
            proc = subprocess.Popen(
                [self._piper, "-m", self._model, "-f", wav_path],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
            )
            proc.communicate(input=text.encode("utf-8"))
            ok = self._play_audio(wav_path)
        except Exception:
            ok = False
        finally:
            try: os.unlink(wav_path)
            except Exception: pass
        return ok

# ------------- Google TTS ----------------
class GTTSSynth(_BaseTTS):
    """Google Translate TTS (online)."""
    def speak(self, text: str, lang_code: str = "en") -> None:
        if not text: return
        linuxish = sys.platform.startswith("linux") or _is_wsl()

        # Linux EN: try Edge male → Piper male → else fall through to gTTS
        if linuxish and _is_english(lang_code) and (os.environ.get("NOVA_TTS_VOICE_EN","male").lower() != "female"):
            try:
                e = EdgeSynth()
                if getattr(e, "_edge_ok", False) and e.speak(text, "en-US"):
                    return
            except Exception:
                pass
            p = PiperSynth()
            if p.speak(text, "en"):
                return

        # Linux non-EN (HI/DE/ES/FR): try Edge Neural female first, then gTTS
        base = _normalize_lang(lang_code).split("-", 1)[0]
        if linuxish and base in EDGE_FEMALE:
            try:
                e = EdgeSynth()
                if getattr(e, "_edge_ok", False):
                    if e.speak(text, base, voice=EDGE_FEMALE[base], rate="+0%"):
                        return
            except Exception:
                pass

        # gTTS fallback
        fd, mp3_path = tempfile.mkstemp(suffix=".mp3"); os.close(fd)
        try:
            from gtts import gTTS
            gTTS(text=text, lang=base).save(mp3_path)
            with self._lock:
                self.stop()
                self._play_audio(mp3_path)
        finally:
            try: os.unlink(mp3_path)
            except Exception: pass

# ------------- Windows/mac via pyttsx3 (strict gender rules) ----------------
class Pyttsx3Synth(_BaseTTS):
    """
    Offline (Windows SAPI, macOS NSSpeech).

    WINDOWS:
      - EN -> male (prefer Microsoft David Desktop; then other male EN; then Edge Neural male)
      - HI/DE/ES/FR -> female (Edge Neural female fallback; then gTTS)

    MAC:
      - EN -> male (prefer Alex, then Daniel; fallback `say -v Alex`; then Edge Neural male)
      - HI/DE/ES/FR -> female (prefer system female; fallback `say -v` female; then Edge Neural female; then gTTS)

    We do NOT change speaking rate unless env vars are set (NOVA_TTS_RATE_WIN / NOVA_TTS_RATE_MAC).
    """
    EN_MALE_PREF_WIN = [
        (os.environ.get("NOVA_WIN_EN_VOICE_NAME") or "david").lower(),
        "microsoft david", "mark", "george", "ryan", "guy", "daniel"
    ]
    EN_MALE_PREF_MAC = [
        (os.environ.get("NOVA_MAC_EN_VOICE_NAME") or "alex").lower(),
        "daniel"
    ]
    FEMALE_PREF_WIN = {
        "hi": ["kalpana", "heera"],
        "de": ["hedda", "katja", "hedy"],
        "es": ["helena", "laura", "paulina", "sabina", "lucia", "susan"],
        "fr": ["julie", "hortense", "celine", "amelie"],
    }
    FEMALE_PREF_MAC = {
        "hi": ["lekha"],
        "de": ["anna"],
        "es": ["monica", "paulina", "lucia"],
        "fr": ["amelie", "aurelie"],
    }

    SAY_MALE_EN = "Alex"
    SAY_FEMALE = {"hi": "Lekha", "de": "Anna", "es": "Monica", "fr": "Amelie"}

    def __init__(self) -> None:
        super().__init__()
        import pyttsx3
        self._engine = pyttsx3.init()
        self._voices = self._engine.getProperty("voices") or []
        self._platform = "win" if sys.platform.startswith("win") else ("mac" if sys.platform == "darwin" else "other")
        self._apply_rate_override()

    def _apply_rate_override(self) -> None:
        try:
            if self._platform == "win":
                r = os.environ.get("NOVA_TTS_RATE_WIN")
                if r: self._engine.setProperty("rate", int(r))
            elif self._platform == "mac":
                r = os.environ.get("NOVA_TTS_RATE_MAC")
                if r: self._engine.setProperty("rate", int(r))
        except Exception:
            pass

    @staticmethod
    def _lc(s: str) -> str: return (s or "").lower()

    def _voice_blob(self, v) -> str:
        parts = [getattr(v, "name", ""), getattr(v, "id", "")]
        try:
            for L in getattr(v, "languages", []) or []:
                parts.append(L.decode() if hasattr(L, "decode") else str(L))
        except Exception:
            pass
        return self._lc(" ".join(parts))

    def _pick_by_names(self, name_frags: list[str]) -> str | None:
        if not self._voices: return None
        frags = [self._lc(x) for x in name_frags if x]
        for v in self._voices:
            if any(f in self._voice_blob(v) for f in frags):
                return v.id
        return None

    # ---- Windows pickers ----
    def _choose_windows_voice(self, lang: str) -> bool:
        try:
            if lang == "en":
                vid = self._pick_by_names(self.EN_MALE_PREF_WIN)
            else:
                vid = self._pick_by_names(self.FEMALE_PREF_WIN.get(lang, []))
            if vid:
                self._engine.setProperty("voice", vid)
                return True
        except Exception:
            pass
        return False

    # ---- macOS pickers ----
    def _choose_macos_voice(self, lang: str) -> bool:
        try:
            if lang == "en":
                vid = self._pick_by_names(self.EN_MALE_PREF_MAC)
            else:
                vid = self._pick_by_names(self.FEMALE_PREF_MAC.get(lang, []))
            if vid:
                self._engine.setProperty("voice", vid)
                return True
        except Exception:
            pass
        return False

    def _edge_fallback(self, text: str, lang: str) -> bool:
        try:
            e = EdgeSynth()
            if not getattr(e, "_edge_ok", False): return False
            if lang == "en":
                return e.speak(text, "en-US", voice=EDGE_MALE_EN, rate="+0%")
            v = EDGE_FEMALE.get(lang)
            if v:
                return e.speak(text, lang, voice=v, rate="+0%")
        except Exception:
            pass
        return False

    def _say_fallback(self, text: str, lang: str) -> bool:
        # macOS only: use `say` with explicit voice (male EN or female others)
        if self._platform != "mac": return False
        if not shutil.which("say"): return False
        try:
            if lang == "en":
                voice = os.environ.get("NOVA_MAC_EN_VOICE_NAME") or self.SAY_MALE_EN
            else:
                voice = {"hi": "Lekha", "de": "Anna", "es": "Monica", "fr": "Amelie"}.get(lang)
            if not voice: return False
            self._run_and_wait(["say", "-v", voice, text])
            return True
        except Exception:
            return False

    def speak(self, text: str, lang_code: str = "en") -> None:
        if not text: return
        base = (lang_code or "en").lower().split("-", 1)[0]

        with self._lock:
            self.stop()
            try:
                if self._platform == "win":
                    if self._choose_windows_voice(base):
                        self._engine.say(text); self._engine.runAndWait(); return
                    if self._edge_fallback(text, base): return
                    self._engine.say(text); self._engine.runAndWait(); return

                if self._platform == "mac":
                    if self._choose_macos_voice(base):
                        self._engine.say(text); self._engine.runAndWait(); return
                    if self._say_fallback(text, base): return
                    if self._edge_fallback(text, base): return
                    self._engine.say(text); self._engine.runAndWait(); return

                # other platforms (rare) -> system default
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                try: GTTSSynth().speak(text, lang_code)
                except Exception: pass

    def stop(self) -> None:
        with self._lock:
            try: self._engine.stop()
            except Exception: pass

# ------------- Router -----------------
def get_tts() -> _BaseTTS:
    prefer = (os.environ.get("NOVA_TTS") or "").strip().lower()
    linuxish = sys.platform.startswith("linux") or _is_wsl()

    if linuxish:
        if prefer == "pyttsx3":
            try: return Pyttsx3Synth()
            except Exception: return GTTSSynth()
        if prefer == "edge":
            e = EdgeSynth()
            if getattr(e, "_edge_ok", False): return e
            return GTTSSynth()
        if prefer == "gtts": return GTTSSynth()
        return GTTSSynth()

    if prefer == "gtts": return GTTSSynth()
    if prefer == "edge":
        e = EdgeSynth()
        if getattr(e, "_edge_ok", False): return e
    try: return Pyttsx3Synth()
    except Exception: return GTTSSynth()

# Convenience used by utils.py
def speak_natural(text: str, lang_code: str = "en") -> None:
    linuxish = sys.platform.startswith("linux") or _is_wsl()
    if linuxish:
        # EN: Edge male -> Piper male -> gTTS; non-EN: Edge female -> gTTS
        if _is_english(lang_code) and (os.environ.get("NOVA_TTS_VOICE_EN","male").lower() != "female"):
            e = EdgeSynth()
            if getattr(e, "_edge_ok", False) and e.speak(text, "en-US"): return
            p = PiperSynth()
            if p.speak(text, "en"): return
        else:
            base = _normalize_lang(lang_code).split("-",1)[0]
            if base in EDGE_FEMALE:
                e = EdgeSynth()
                if getattr(e, "_edge_ok", False) and e.speak(text, base, voice=EDGE_FEMALE[base]): return
        GTTSSynth().speak(text, lang_code); return
    get_tts().speak(text, lang_code)
