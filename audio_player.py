from __future__ import annotations
import os, sys, shutil, subprocess
from typing import List

def _run(cmd: List[str]) -> None:
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True).wait()

def _linux_players() -> list[str]:
    # Prefer ffplay (handles wav/mp3), then mpg123 (mp3)
    cands = [
        "/usr/bin/ffplay", "/bin/ffplay", "ffplay",
        "/usr/bin/mpg123", "/bin/mpg123", "mpg123",
    ]
    out: list[str] = []
    for c in cands:
        exe = shutil.which(c) or (c if os.path.exists(c) else None)
        if exe and exe not in out:
            out.append(exe)
    return out

def play_audio_file(path: str, block: bool = True) -> None:
    if not path or not os.path.exists(path):
        return

    linuxish = sys.platform.startswith("linux") or ("WSL_DISTRO_NAME" in os.environ)
    if linuxish:
        # Try system players
        for exe in _linux_players():
            try:
                if exe.endswith("ffplay"):
                    cmd = [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", path]
                elif exe.endswith("mpg123"):
                    cmd = [exe, "-q", path]
                else:
                    continue
                if block:
                    _run(cmd)
                else:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                return
            except Exception:
                continue
        # No crash if we couldn't play
        return

    # Windows/mac: use playsound (unchanged behavior)
    try:
        from playsound import playsound
        if block:
            playsound(path)
        else:
            subprocess.Popen(
                [sys.executable, "-c", f"from playsound import playsound; playsound(r'''{path}''')"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
            )
    except Exception:
        pass   