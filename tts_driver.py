# tts_driver.py — Nova TTS router (mac English uses local NSSpeech; non-EN uses Piper;
# Windows EN uses SAPI; Spanish forces female via Piper speaker=1; safe fallbacks to Edge/gTTS)
from __future__ import annotations

import os, sys, stat, json, platform, tempfile, subprocess, shutil, asyncio, threading
from typing import Optional, List
from pathlib import Path

# -----------------------------------------------------------------------------
# Paths / manifest (handle PyInstaller bundles via _MEIPASS)
# -----------------------------------------------------------------------------
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # Running from a PyInstaller bundle; datas are unpacked here
    REPO_ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    # Running from source
    REPO_ROOT = Path(__file__).resolve().parent

PIPER_MANIFEST = str(REPO_ROOT / "third_party" / "piper" / "models_manifest.json")


def _load_piper_manifest(path: str = PIPER_MANIFEST) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        man = json.load(f)

    # Make model/config paths absolute (relative to REPO_ROOT)
    models = man.get("models") or {}
    for _, v in models.items():
        v["model"] = str((REPO_ROOT / v["model"]).resolve())
        v["config"] = str((REPO_ROOT / v["config"]).resolve())

    # Make exe paths absolute only if they're relative.
    # Keep absolute paths and bare command names (e.g., "piper") unchanged.
    ex = man.get("exe") or {}

    def _is_cmd_name(p: str) -> bool:
        return (os.path.sep not in p) and (os.altsep is None or os.altsep not in p)

    for k, v in list(ex.items()):
        if not v:
            continue
        if os.path.isabs(v) or _is_cmd_name(v):
            ex[k] = v  # leave as-is
        else:
            ex[k] = str((REPO_ROOT / v).resolve())

    man["models"] = models
    man["exe"] = ex
    return man


def _is_wsl() -> bool:
    try:
        return ("WSL_DISTRO_NAME" in os.environ) or ("microsoft" in platform.release().lower())
    except Exception:
        return False


def _normalize_lang(code: str | None, default: str = "en-US") -> str:
    c = (code or default).strip()
    if not c:
        return default
    c = c.replace("_", "-")
    parts = c.split("-", 1)
    base = parts[0].lower()
    if len(parts) == 2:
        return f"{base}-{parts[1].upper()}"
    return base


def _base_lang(code: str | None) -> str:
    return _normalize_lang(code).split("-", 1)[0]


# -----------------------------------------------------------------------------
# Tiny audio player (WAV/MP3 helpers)
# -----------------------------------------------------------------------------
class _Player:
    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()

    def stop(self):
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

    def _spawn(self, cmd: List[str]):
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
        )
        try:
            self._proc.wait()
        finally:
            self._proc = None

    def play_wav(self, path: str) -> bool:
        sysname = platform.system()
        if sysname == "Windows":
            try:
                import winsound

                winsound.PlaySound(path, winsound.SND_FILENAME)
                return True
            except Exception:
                return False
        if sysname == "Darwin":
            if shutil.which("afplay"):
                self._spawn(["afplay", path])
                return True
            return False
        # Linux / WSL
        if shutil.which("ffplay"):
            self._spawn(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path])
            return True
        if shutil.which("paplay"):
            self._spawn(["paplay", path])
            return True
        if shutil.which("aplay"):
            self._spawn(["aplay", "-q", path])
            return True
        return False

    def play_mp3(self, path: str) -> bool:
        sysname = platform.system()
        if sysname == "Windows":
            # winsound can't MP3; try ffplay or transcode
            ff = shutil.which("ffplay")
            if ff:
                self._spawn([ff, "-nodisp", "-autoexit", "-loglevel", "quiet", path])
                return True
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                fd, wav_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                subprocess.run([ffmpeg, "-y", "-loglevel", "quiet", "-i", path, wav_path], check=False)
                ok = self.play_wav(wav_path)
                try:
                    os.unlink(wav_path)
                except Exception:
                    pass
                return ok
            return False
        if sysname == "Darwin":
            if shutil.which("afplay"):
                self._spawn(["afplay", path])
                return True
            return False
        # Linux / WSL
        if shutil.which("ffplay"):
            self._spawn(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path])
            return True
        if shutil.which("mpg123"):
            self._spawn(["mpg123", "-q", path])
            return True
        return False


PLAYER = _Player()

# -----------------------------------------------------------------------------
# Base synth class
# -----------------------------------------------------------------------------
class _BaseTTS:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()

    def stop(self) -> None:
        PLAYER.stop()
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

    def speak(self, text: str, lang_code: str = "en-US") -> bool:  # pragma: no cover
        raise NotImplementedError


# -----------------------------------------------------------------------------
# Edge Neural (edge-tts, online)
# -----------------------------------------------------------------------------
EDGE_MALE_EN = os.environ.get("NOVA_TTS_EDGE_VOICE_EN", "en-US-GuyNeural")
EDGE_FEMALE = {
    "hi": "hi-IN-SwaraNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",  # female
    "fr": "fr-FR-DeniseNeural",
}


class EdgeSynth(_BaseTTS):
    def __init__(self) -> None:
        super().__init__()
        try:
            import edge_tts  # noqa: F401

            self._ok = True
        except Exception:
            self._ok = False

    async def _edge_to(self, out_mp3: str, text: str, voice: str, rate: str = "+0%"):
        import edge_tts

        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        with open(out_mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])

    def speak(self, text: str, lang_code: str = "en-US", *, voice: Optional[str] = None, rate: str = "+0%") -> bool:
        if not text or not self._ok:
            return False
        base = _base_lang(lang_code)
        v = voice
        if v is None:
            v = EDGE_MALE_EN if base == "en" else EDGE_FEMALE.get(base, None)

        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            try:
                asyncio.run(self._edge_to(mp3_path, text, v or EDGE_MALE_EN, rate))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self._edge_to(mp3_path, text, v or EDGE_MALE_EN, rate))
                finally:
                    loop.close()
            with self._lock:
                self.stop()
                return PLAYER.play_mp3(mp3_path)
        except Exception:
            return False
        finally:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass


# -----------------------------------------------------------------------------
# gTTS (online last resort)
# -----------------------------------------------------------------------------
class GTTSSynth(_BaseTTS):
    def speak(self, text: str, lang_code: str = "en-US") -> bool:
        if not text:
            return False
        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            from gtts import gTTS

            gTTS(text=text, lang=_base_lang(lang_code)).save(mp3_path)
            with self._lock:
                self.stop()
                return PLAYER.play_mp3(mp3_path)
        except Exception:
            return False
        finally:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass


# -----------------------------------------------------------------------------
# pyttsx3 (SAPI on Windows, NSSpeech on macOS)
# -----------------------------------------------------------------------------
class Pyttsx3Synth(_BaseTTS):
    def __init__(self, platform_hint: str = "") -> None:
        super().__init__()
        import pyttsx3

        self._engine = pyttsx3.init()
        self._voices = self._engine.getProperty("voices") or []
        self._platform = platform_hint or (
            "win" if sys.platform.startswith("win") else "mac" if sys.platform == "darwin" else "other"
        )

    @staticmethod
    def _lc(s: str) -> str:
        return (s or "").lower()

    def _voice_blob(self, v) -> str:
        parts = [getattr(v, "name", ""), getattr(v, "id", "")]
        try:
            for L in getattr(v, "languages", []) or []:
                parts.append(L.decode() if hasattr(L, "decode") else str(L))
        except Exception:
            pass
        return self._lc(" ".join(parts))

    def _pick_by_names(self, name_frags: list[str]) -> str | None:
        if not self._voices:
            return None
        frags = [self._lc(x) for x in name_frags if x]
        for v in self._voices:
            if any(f in self._voice_blob(v) for f in frags):
                return v.id
        return None

    def choose_windows_en(self) -> bool:
        vid = self._pick_by_names(
            [(os.environ.get("_WIN_EN_VOICE_NAME") or "david"), "microsoft david", "david"]
        )
        if vid:
            try:
                self._engine.setProperty("voice", vid)
                return True
            except Exception:
                return False
        return False

    def choose_windows_locale(self, base_lang: str) -> bool:
        lang_hints = {
            "de": ["de", "german"],
            "fr": ["fr", "french"],
            "es": ["es", "spanish"],
            "hi": ["hi", "hindi"],
        }.get(base_lang, [])
        if not lang_hints:
            return False
        vid = self._pick_by_names(lang_hints)
        if vid:
            try:
                self._engine.setProperty("voice", vid)
                return True
            except Exception:
                return False
        return False

    def choose_macos_voice(self, base_lang: str) -> bool:
        if base_lang == "en":
            vid = self._pick_by_names([(os.environ.get("_MAC_EN_VOICE_NAME") or "alex"), "alex", "daniel"])
        else:
            prefs = {
                "de": ["anna"],
                "es": ["monica", "paulina", "lucia"],
                "fr": ["amelie", "aurelie"],
                "hi": ["lekha"],
            }.get(base_lang, [])
            vid = self._pick_by_names(prefs)
        if vid:
            try:
                self._engine.setProperty("voice", vid)
                return True
            except Exception:
                return False
        return False

    def speak(self, text: str, lang_code: str = "en-US") -> bool:
        if not text:
            return False
        base = _base_lang(lang_code)
        try:
            if self._platform == "win":
                if base == "en":
                    self.choose_windows_en()
                else:
                    self.choose_windows_locale(base)
            elif self._platform == "mac":
                self.choose_macos_voice(base)
            self._engine.say(text)
            self._engine.runAndWait()
            return True
        except Exception:
            return False


# -----------------------------------------------------------------------------
# Piper (offline) using models_manifest.json
# -----------------------------------------------------------------------------
_PIPER_DEFAULT_KEYS = {"en": "en-US", "hi": "hi-IN", "fr": "fr-FR", "es": "es-ES", "de": "de-DE"}


def _resolve_piper_exe(manifest: dict) -> str | None:
    exes = manifest.get("exe") or {}

    # Pick the manifest key for this OS/arch
    if sys.platform.startswith("win"):
        exe = exes.get("windows")
    elif sys.platform == "darwin":
        mach = (platform.machine() or "").lower()
        key = "darwin-arm64" if ("arm" in mach or "aarch64" in mach) else "darwin-x64"
        exe = exes.get(key)
    else:  # linux / WSL
        mach = (platform.machine() or "").lower()
        key = "linux-arm64" if ("arm" in mach or "aarch64" in mach) else "linux-x64"
        exe = exes.get(key)

    if not exe:
        return None

    # If it's just a command name (e.g. "piper"), resolve via PATH
    is_cmd = (os.path.sep not in exe) and (os.altsep is None or os.altsep not in exe)
    if is_cmd:
        return shutil.which(exe)  # may be None if not installed

    # Otherwise it's a bundled path — ensure exec bit and set ESPEAK_DATA if present
    try:
        st = os.stat(exe)
        os.chmod(exe, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass

    esd = os.path.join(os.path.dirname(exe), "espeak-ng-data")
    if os.path.isdir(esd):
        os.environ.setdefault("ESPEAK_DATA", esd)

    return exe


def _pick_piper_model(manifest: dict, lang_code: str) -> Optional[dict]:
    models = manifest.get("models") or {}
    norm = _normalize_lang(lang_code)
    if norm in models:
        return models[norm]
    base = _base_lang(lang_code)
    k = _PIPER_DEFAULT_KEYS.get(base)
    if k and k in models:
        return models[k]
    return None


class PiperSynth(_BaseTTS):
    def __init__(self, manifest_path: str = PIPER_MANIFEST) -> None:
        super().__init__()
        self._manifest = _load_piper_manifest(manifest_path)
        self._exe = _resolve_piper_exe(self._manifest)
        self._bindir = os.path.dirname(self._exe) if self._exe else None  # for DYLD/LD paths

    def speak(self, text: str, lang_code: str = "en-US") -> bool:
        if not text or not self._exe:
            return False
        model = _pick_piper_model(self._manifest, lang_code)
        if not model:
            return False

        m = model["model"]
        c = model.get("config") or (m + ".json")
        spk = str(model.get("speaker", 0))
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        # We feed text on stdin; Piper writes to -o <file>
        cmd = [self._exe, "-m", m, "-c", c, "-s", spk, "-o", wav_path, "-q"]

        # Make sure the bundled libs & espeak data are visible to the child process
        env = os.environ.copy()
        if self._bindir:
            if sys.platform.startswith("linux"):
                env["LD_LIBRARY_PATH"] = f"{self._bindir}:{env.get('LD_LIBRARY_PATH','')}".rstrip(":")
            elif sys.platform == "darwin":
                env["DYLD_LIBRARY_PATH"] = f"{self._bindir}:{env.get('DYLD_LIBRARY_PATH','')}".rstrip(":")
            esd = os.path.join(self._bindir, "espeak-ng-data")
            if os.path.isdir(esd):
                env.setdefault("ESPEAK_DATA", esd)

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=env,
            )
            try:
                self._proc.communicate(input=text.encode("utf-8"), timeout=None)
            finally:
                self._proc = None
            with self._lock:
                self.stop()
                return PLAYER.play_wav(wav_path)
        except Exception:
            return False
        finally:
            try:
                os.unlink(wav_path)
            except Exception:
                pass


# -----------------------------------------------------------------------------
# Deterministic Router
# -----------------------------------------------------------------------------
class PolicyTTS(_BaseTTS):
    def __init__(self) -> None:
        super().__init__()
        self._linuxish = sys.platform.startswith("linux") or _is_wsl()
        self._is_win = sys.platform.startswith("win")
        self._is_mac = sys.platform == "darwin"

        self._edge = EdgeSynth()
        self._gtts = GTTSSynth()
        self._piper = PiperSynth()

        self._sapi_en: Optional[Pyttsx3Synth] = Pyttsx3Synth(platform_hint="win") if self._is_win else None
        self._nsss: Optional[Pyttsx3Synth] = Pyttsx3Synth(platform_hint="mac") if self._is_mac else None

    def speak(self, text: str, lang_code: str = "en-US") -> None:
        if not text:
            return
        base = _base_lang(lang_code)

        # Linux / WSL
        if self._linuxish:
            if base == "en":
                if self._edge.speak(text, "en-US", voice=EDGE_MALE_EN):
                    return
                if self._piper.speak(text, "en-US"):
                    return
                self._gtts.speak(text, "en")
                return
            # Non-English: Piper first (Spanish female guaranteed by manifest)
            if self._piper.speak(text, base):
                return
            if self._edge.speak(text, base):
                return
            self._gtts.speak(text, base)
            return

        # Windows
        if self._is_win:
            if base == "en":
                if self._sapi_en and self._sapi_en.speak(text, "en-US"):
                    return
                if self._piper.speak(text, "en-US"):
                    return
                if self._edge.speak(text, "en-US", voice=EDGE_MALE_EN):
                    return
                self._gtts.speak(text, "en")
                return
            # Spanish: FORCE female by using Piper first (speaker=1 in manifest)
            if base == "es":
                if self._piper.speak(text, "es-ES"):
                    return
                if self._edge.speak(text, "es-ES"):
                    return
                self._gtts.speak(text, "es")
                return
            # Other non-English (hi/de/fr): try local SAPI voice, then Piper, then Edge/gTTS
            try:
                sapi_loc = Pyttsx3Synth(platform_hint="win")
                if sapi_loc.choose_windows_locale(base) and sapi_loc.speak(text, base):
                    return
            except Exception:
                pass
            if self._piper.speak(text, base):
                return
            if self._edge.speak(text, base):
                return
            self._gtts.speak(text, base)
            return

        # macOS
        if self._is_mac:
            if base == "en":
                if self._nsss and self._nsss.speak(text, "en-US"):
                    return
                if self._piper.speak(text, "en-US"):
                    return
                if self._edge.speak(text, "en-US", voice=EDGE_MALE_EN):
                    return
                self._gtts.speak(text, "en")
                return
            # Non-English: Piper first (Spanish female guaranteed by manifest)
            if self._piper.speak(text, base):
                return
            if self._edge.speak(text, base):
                return
            self._gtts.speak(text, base)
            return

        # Other unknown platform
        if self._piper.speak(text, base):
            return
        self._gtts.speak(text, base)


# Public API
def get_tts() -> _BaseTTS:
    return PolicyTTS()


def speak_natural(text: str, lang_code: str = "en-US") -> None:
    get_tts().speak(text, lang_code)
