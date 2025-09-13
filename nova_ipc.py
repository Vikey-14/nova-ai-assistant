# nova_ipc.py
# -*- coding: utf-8 -*-
"""
Shared tray IPC + launcher utilities (cross-platform).

Use from main.py and tray_app.py so we don't duplicate:
  - SINGLETON_ADDR      # (host, port) the tray listens on
  - send_tray_command() # "HELLO", "OPEN", "TIP", "OPEN_AND_TIP", "BYE"
  - is_tray_alive()
  - ensure_tray_running()
  - notify_tray_user_exit()
"""

from __future__ import annotations
import os, sys, socket, subprocess, time, platform
from pathlib import Path

# ---------- paths ----------
IS_FROZEN = getattr(sys, "frozen", False)
EXE_DIR = Path(sys.executable).parent if IS_FROZEN else Path(__file__).parent.resolve()
APP_DIR = Path(getattr(sys, "_MEIPASS", EXE_DIR)).resolve()

# ---------- singleton socket ----------
SINGLETON_PORT = 50573
SINGLETON_ADDR = ("127.0.0.1", SINGLETON_PORT)

# ---------- platform helpers ----------
def _is_windows() -> bool:
    return platform.system().lower().startswith("win")

def _is_macos() -> bool:
    s = platform.system().lower()
    return "darwin" in s or "mac" in s

# Windows flag (ignored elsewhere)
CREATE_NO_WINDOW = 0x08000000 if _is_windows() else 0

# ---------- tray candidates ----------
def _tray_candidates() -> list[Path]:
    """
    Candidate tray binaries/scripts in likely locations.
    Order matters; first that exists is launched.
    """
    names = [
        # common Windows / Linux names (prefer the spaced one first)
        "Nova Tray.exe", "NovaTray.exe", "nova_tray.exe", "tray_app.exe",
        "Nova Tray", "NovaTray", "nova_tray", "tray_app",
    ]
    cands: list[Path] = []
    for base in (EXE_DIR, APP_DIR, Path(__file__).parent):
        for n in names:
            cands.append(base / n)

    # macOS app bundles + internal binaries (support both spellings)
    cands += [
        # spaced bundle
        EXE_DIR / "Nova Tray.app",
        APP_DIR / "Nova Tray.app",
        EXE_DIR / "Nova Tray.app" / "Contents" / "MacOS" / "NovaTray",
        APP_DIR / "Nova Tray.app" / "Contents" / "MacOS" / "NovaTray",
        # no-space bundle (legacy)
        EXE_DIR / "NovaTray.app",
        APP_DIR / "NovaTray.app",
        EXE_DIR / "NovaTray.app" / "Contents" / "MacOS" / "NovaTray",
        APP_DIR / "NovaTray.app" / "Contents" / "MacOS" / "NovaTray",
    ]

    # dev mode Python fallback
    for base in (EXE_DIR, APP_DIR, Path(__file__).parent):
        cands.append(base / "tray_app.py")

    # de-dup while preserving order
    seen = set(); out = []
    for p in cands:
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(p)
    return out

# ---------- IPC ----------
def send_tray_command(cmd: str, *, timeout: float = 0.6) -> tuple[bool, str]:
    """
    Send a single command, return (ok, reply_text).
    ok means we connected and sent; reply_text may be "".
    """
    try:
        with socket.create_connection(SINGLETON_ADDR, timeout=timeout) as c:
            c.sendall((cmd.strip().upper() + "\n").encode("utf-8"))
            try:
                c.settimeout(timeout)
                data = c.recv(128)
                return True, (data.decode("utf-8", "ignore").strip() if data else "")
            except Exception:
                return True, ""
    except Exception:
        return False, ""

def is_tray_alive(*, timeout: float = 0.6) -> bool:
    ok, reply = send_tray_command("HELLO", timeout=timeout)
    if not ok:
        return False
    token = (reply or "").strip().upper().replace("-", " ").replace("_", " ")
    return token in {"NOVA TRAY", "OK"}

# ---------- launcher ----------
def _spawn_tray_once() -> bool:
    for cand in _tray_candidates():
        if not cand.exists():
            continue
        try:
            # macOS .app bundle: open by path (no -a)
            if _is_macos() and cand.suffix.lower() == ".app":
                subprocess.Popen(["open", str(cand)], close_fds=True)
                return True

            # Python script fallback
            if cand.name.lower() == "tray_app.py":
                py = Path(sys.executable)
                pyw = py.with_name("pythonw.exe") if _is_windows() else py
                try:
                    subprocess.Popen([str(pyw), str(cand)], cwd=str(cand.parent),
                                     close_fds=True, creationflags=CREATE_NO_WINDOW)
                    return True
                except Exception:
                    subprocess.Popen([str(py), str(cand)], cwd=str(cand.parent),
                                     close_fds=True, creationflags=CREATE_NO_WINDOW)
                    return True

            # Native binary
            subprocess.Popen([str(cand)], cwd=str(cand.parent), close_fds=True,
                             creationflags=CREATE_NO_WINDOW)
            return True
        except Exception:
            continue
    return False

def ensure_tray_running(*, wait_seconds: float = 2.5) -> bool:
    """
    If tray is up -> True.
    Else try to spawn candidates, then poll HELLO briefly.
    """
    if is_tray_alive():
        return True
    _spawn_tray_once()
    deadline = time.time() + max(0.5, wait_seconds)
    while time.time() < deadline:
        if is_tray_alive():
            return True
        time.sleep(0.15)
    return is_tray_alive()

def notify_tray_user_exit() -> None:
    """
    Tell the tray "BYE" so it can set a cooldown sentinel and not relaunch Nova immediately.
    Fire-and-forget; ignore errors (e.g., tray isn’t running).
    """
    try:
        send_tray_command("BYE", timeout=0.4)
    except Exception:
        pass

# Convenience wrappers
def tray_open():         return send_tray_command("OPEN")[0]
def tray_tip():          return send_tray_command("TIP")[0]
def tray_open_and_tip(): return send_tray_command("OPEN_AND_TIP")[0]
def tray_hello() -> str: return send_tray_command("HELLO")[1]
