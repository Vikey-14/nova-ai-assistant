from __future__ import annotations
import os, sys, shutil, subprocess
from typing import List

def _run(cmd: List[str]) -> None:
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True).wait()

def _linux_players() -> list[str]:
    cands = ["/usr/bin/ffplay", "/bin/ffplay", "ffplay",
             "/usr/bin/mpg123", "/bin/mpg123", "mpg123"]
    out = []
    for c in cands:
        exe = shutil.which(c) or (c if os.path.exists(c) else None)
        if exe and exe not in out:
            out.append(exe)
    return out

def play_audio_file(path: str, block: bool = True) -> None:
    if not path or not os.path.exists(path):
        return
    linuxish = sys.platform.startswith("linux") or "WSL_DISTRO_NAME" in os.environ
    if linuxish:
        for exe in _linux_players():
            try:
                if exe.endswith("ffplay"):
                    cmd = [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", path]
                elif exe.endswith("mpg123"):
                    cmd = [exe, "-q", path]
                else:
                    continue
                if block: _run(cmd)
                else: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                return
            except Exception:
                continue
        return  # no crash if missing players
    # Windows/mac: keep playsound behavior
    try:
        from audio_player import play_audio_file
        if block:
            play_audio_file(path)
        else:
            subprocess.Popen([sys.executable, "-c",
                              f"from audio_player import play_audio_file; play_audio_file(r'''{path}''')"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    except Exception:
        pass
