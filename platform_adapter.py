# platform_adapter.py
# -*- coding: utf-8 -*-
"""
Cross-platform adapter for Nova.
One tiny API that main.py / tray_app.py can call without caring about the OS.
"""

from __future__ import annotations
import os, sys, platform, subprocess, shlex
from pathlib import Path

try:
    import psutil  # type: ignore
except Exception:
    psutil = None

# ---------- paths ----------
IS_FROZEN = getattr(sys, "frozen", False)
EXE_DIR: Path = Path(sys.executable).parent if IS_FROZEN else Path(__file__).parent.resolve()
APP_DIR: Path = Path(getattr(sys, "_MEIPASS", EXE_DIR)).resolve()  # PyInstaller _MEIPASS safe

def _norm(p: str) -> str:
    return p.lower().replace("\\", "/")

def _main_candidates() -> list[Path]:
    """
    Possible main app entry points across OS / build modes.
    Order matters (first hit wins).
    """
    cands: list[Path] = []

    # Windows / Linux standalone exe names (ONLY the correct branding)
    # (Intentionally DO NOT include "NOVA.exe" or "NOVA")
    for name in ("Nova.exe", "Nova"):
        cands += [EXE_DIR / name, APP_DIR / name]

    # macOS app bundle (Nova.app)
    cands += [
        EXE_DIR / "Nova.app" / "Contents" / "MacOS" / "Nova",
        APP_DIR / "Nova.app" / "Contents" / "MacOS" / "Nova",
    ]

    # Dev mode (python script)
    for base in (EXE_DIR, APP_DIR, Path(__file__).parent):
        cands.append(base / "main.py")

    # De-dup while preserving order
    seen = set()
    out: list[Path] = []
    for p in cands:
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(p)
    return out

# ---------- base backend ----------

class Backend:
    # What users see in menus / titles:
    app_name  = "Nova"
    # Internal token for Windows Run key; user sees “Nova Tray” via file version metadata:
    tray_name = "NovaTray"

    # ---- filesystem
    def user_data_dir(self) -> Path:
        """OS-appropriate per-user app data folder: .../Nova"""
        try:
            from platformdirs import user_data_dir as p_ud
            return Path(p_ud(self.app_name, False)).resolve()
        except Exception:
            sysname = platform.system().lower()
            home = Path.home()
            if "windows" in sysname:
                root = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
                return (root / self.app_name).resolve()
            if "darwin" in sysname or "mac" in sysname:
                return (home / "Library" / "Application Support" / self.app_name).resolve()
            # linux / other unix
            root = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
            return (root / self.app_name).resolve()

    # ---- process discovery
    def _looks_like_our_python(self, p) -> bool:
        try:
            name = (p.info.get("name") or p.name() or "").lower()
            if name in {"python", "python3", "pythonw", "pythonw.exe"}:
                cmd = " ".join(p.info.get("cmdline") or p.cmdline() or [])
                cmdl = _norm(cmd)
                return "main.py" in cmdl and _norm(str(APP_DIR)) in cmdl
        except Exception:
            pass
        return False

    def _looks_like_our_binary(self, p) -> bool:
        try:
            # Keep it generic; this check doesn't influence branding/launch choice
            name = (p.info.get("name") or p.name() or "").lower()
            return name in {"nova", "nova.exe"}
        except Exception:
            return False

    def is_main_running(self) -> bool:
        if psutil is None:
            return False
        try:
            for p in psutil.process_iter(["name", "cmdline"]):
                if self._looks_like_our_binary(p) or self._looks_like_our_python(p):
                    return True
        except Exception:
            pass
        return False

    # ---- launching
    def launch_main_app(self) -> bool:
        # Try native/bundled binary first
        for cand in _main_candidates():
            if not cand.exists():
                continue
            try:
                if cand.suffix in {".exe", ""} and os.access(str(cand), os.X_OK):
                    subprocess.Popen([str(cand)], cwd=str(cand.parent), close_fds=True)
                    return True
            except Exception:
                pass

        # Dev script fallback via pythonw/python
        py = Path(sys.executable)
        pyw = py.with_name("pythonw.exe") if os.name == "nt" else py
        for cand in _main_candidates():
            if cand.name == "main.py" and cand.exists():
                for interp in (pyw, py):
                    try:
                        subprocess.Popen([str(interp), str(cand)], cwd=str(cand.parent), close_fds=True)
                        return True
                    except Exception:
                        continue
        return False

    # ---- window control (safe defaults)
    def bring_to_front(self) -> bool:  # pragma: no cover
        return False

    def hide_window(self) -> bool:  # pragma: no cover
        return False

    def close_window(self) -> bool:  # pragma: no cover
        if psutil is None:
            return False
        ok = False
        try:
            for p in psutil.process_iter(["name", "cmdline"]):
                if self._looks_like_our_binary(p) or self._looks_like_our_python(p):
                    try:
                        p.terminate()
                        ok = True
                    except Exception:
                        pass
        except Exception:
            pass
        return ok

    # ---- autostart (optional)
    def install_autostart(self, tray: bool = True) -> bool:  # pragma: no cover
        return False

    def uninstall_autostart(self, tray: bool = True) -> bool:  # pragma: no cover
        return False


# ---------- Windows backend ----------
class WindowsBackend(Backend):
    def __init__(self) -> None:
        import ctypes  # lazy
        self._user32 = ctypes.windll.user32  # type: ignore[attr-defined]

    def _enum_hwnds(self):
        import ctypes
        user32 = self._user32
        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextLengthW = user32.GetWindowTextLengthW

        items = []
        def foreach(hwnd, _lparam):
            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value or ""
            items.append((hwnd, title))
            return True

        EnumWindows(EnumWindowsProc(foreach), 0)
        return items

    @staticmethod
    def _title_is_nova(title: str) -> bool:
        t = (title or "").strip().lower()
        return t == "nova" or t.startswith("nova - ")

    def _find_hwnd(self):
        try:
            for hwnd, title in self._enum_hwnds():
                if self._title_is_nova(title):
                    return hwnd
        except Exception:
            pass
        return None

    def bring_to_front(self) -> bool:
        hwnd = self._find_hwnd()
        if not hwnd:
            return False
        SW_RESTORE = 9
        self._user32.ShowWindow(hwnd, SW_RESTORE)
        self._user32.SetForegroundWindow(hwnd)
        return True

    def hide_window(self) -> bool:
        hwnd = self._find_hwnd()
        if not hwnd:
            return False
        SW_HIDE = 0
        self._user32.ShowWindow(hwnd, SW_HIDE)
        return True

    def close_window(self) -> bool:
        hwnd = self._find_hwnd()
        if not hwnd:
            return False
        WM_CLOSE = 0x0010
        self._user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True

    def install_autostart(self, tray: bool = True) -> bool:
        # Adds Run registry entry for the tray (recommended) or main app.
        try:
            import winreg  # type: ignore
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE)
            target = None
            if tray:
                for name in ("Nova Tray.exe", "NovaTray.exe", "tray_app.exe", "nova_tray.exe"):
                    p = EXE_DIR / name
                    if p.exists():
                        target = str(p)
                        break
            if not target:
                for cand in _main_candidates():
                    if cand.exists():
                        target = str(cand)
                        break
            if not target:
                return False
            winreg.SetValueEx(key, self.tray_name if tray else self.app_name, 0, winreg.REG_SZ, target)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def uninstall_autostart(self, tray: bool = True) -> bool:
        try:
            import winreg  # type: ignore
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_ALL_ACCESS)
        # Remove both names just in case
            for value_name in (self.tray_name if tray else self.app_name,):
                try:
                    winreg.DeleteValue(key, value_name)
                except Exception:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception:
            return False


# ---------- Linux backend ----------
class LinuxBackend(Backend):
    def close_window(self) -> bool:
        # Prefer WM_CLASS (lowercase usually ok)
        for target in ("nova", "Nova"):
            try:
                subprocess.run(["wmctrl", "-x", "-c", target],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                return True
            except Exception:
                pass
        # Fallback: by window title (brand = "Nova")
        try:
            subprocess.run(["wmctrl", "-c", "Nova - AI Assistant"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return True
        except Exception:
            pass
        # Last resort: polite terminate
        return super().close_window()

    def install_autostart(self, tray: bool = True) -> bool:
        try:
            autostart = Path.home() / ".config" / "autostart"
            autostart.mkdir(parents=True, exist_ok=True)
            target = None
            if tray:
                for name in ("NovaTray", "Nova Tray", "nova_tray", "tray_app"):
                    for ext in (".exe", "",):
                        p = EXE_DIR / f"{name}{ext}"
                        if p.exists():
                            target = p
                            break
            if not target:
                for cand in _main_candidates():
                    if cand.exists():
                        target = cand
                        break
            if not target:
                return False
            desktop = autostart / ("nova-tray.desktop" if tray else "nova.desktop")
            desktop.write_text(
                "[Desktop Entry]\n"
                f"Type=Application\n"
                f"Name={'Nova Tray' if tray else 'Nova'}\n"
                f"Exec={shlex.quote(str(target))}\n"
                "X-GNOME-Autostart-enabled=true\n",
                encoding="utf-8"
            )
            return True
        except Exception:
            return False

    def uninstall_autostart(self, tray: bool = True) -> bool:
        try:
            f = Path.home() / ".config" / "autostart" / ("nova-tray.desktop" if tray else "nova.desktop")
            if f.exists():
                f.unlink()
            return True
        except Exception:
            return False


# ---------- macOS backend ----------
class MacBackend(Backend):
    def bring_to_front(self) -> bool:
        app = EXE_DIR / "Nova.app"
        if app.exists():
            try:
                subprocess.run(["osascript", "-e", 'tell application "Nova" to activate'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
        try:
            subprocess.run(["osascript", "-e",
                            'tell application "System Events" to set frontmost of process "Python" to true'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def hide_window(self) -> bool:
        return False

    def close_window(self) -> bool:
        app = EXE_DIR / "Nova.app"
        if app.exists():
            try:
                subprocess.run(["osascript", "-e", 'tell application "Nova" to quit'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
        return super().close_window()

    def install_autostart(self, tray: bool = True) -> bool:
        try:
            launch_agents = Path.home() / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True, exist_ok=True)
            label = "com.nova.tray" if tray else "com.nova.app"
            plist = launch_agents / f"{label}.plist"

            target = None
            if tray:
                # Prefer inside app bundle
                app_bin = EXE_DIR / "Nova Tray.app" / "Contents" / "MacOS" / "NovaTray"
                if app_bin.exists():
                    target = [str(app_bin)]
                else:
                    for name in ("NovaTray", "Nova Tray", "nova_tray", "tray_app"):
                        for ext in (".exe", "",):
                            p = EXE_DIR / f"{name}{ext}"
                            if p.exists():
                                target = [str(p)]
                                break
            if not target:
                for cand in _main_candidates():
                    if cand.exists():
                        target = [str(cand)]
                        break
            if not target:
                return False

            payload = {
                "Label": label,
                "RunAtLoad": True,
                "KeepAlive": False,
                "ProgramArguments": target,
                "WorkingDirectory": str(EXE_DIR),
            }
            plist.write_text(_plist(payload), encoding="utf-8")
            subprocess.run(["launchctl", "load", str(plist)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False


def _plist(d: dict) -> str:
    import xml.sax.saxutils as su
    def k(v: str) -> str: return f"<key>{su.escape(v)}</key>"
    def s(v: str) -> str: return f"<string>{su.escape(v)}</string>"
    def arr(a: list[str]) -> str:
        return "<array>\n" + "\n".join(s(x) for x in a) + "\n</array>"
    body = []
    for key, val in d.items():
        body.append(k(str(key)))
        if isinstance(val, list):
            body.append(arr(val))
        elif isinstance(val, bool):
            body.append("<true/>" if val else "<false/>")
        else:
            body.append(s(str(val)))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n' + "\n".join(body) + "\n</dict>\n</plist>\n"
    )

# ---------- factory ----------
def get_backend() -> Backend:
    sysname = platform.system().lower()
    if "windows" in sysname:
        return WindowsBackend()
    if "darwin" in sysname or "mac" in sysname:
        return MacBackend()
    return LinuxBackend()
