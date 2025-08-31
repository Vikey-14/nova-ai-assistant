# -*- mode: python ; coding: utf-8 -*-
import os, sysconfig
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.datastruct import Tree
import encodings as _enc

BASE = Path.cwd()
STDLIB = sysconfig.get_paths().get("stdlib", "")

def add_dir_files(root_dir, target_prefix, allow_ext=None):
    pairs = []
    root = BASE / root_dir
    if root.is_dir():
        for dp, dn, fnames in os.walk(root):
            rel_dir = Path(dp).relative_to(root)
            dest_dir = str(Path(target_prefix) / rel_dir).replace("\\", "/") or "."
            for fn in fnames:
                src = Path(dp) / fn
                if allow_ext and Path(fn).suffix.lower() not in allow_ext:
                    continue
                pairs.append((str(src), dest_dir))
    return pairs

def first_icon():
    for p in [
        BASE / "assets" / "nova_icon_big.ico",
        BASE / "nova_icon_big.ico",
        BASE / "nova icon.ico",
        BASE / "assets" / "nova_icon_256.png",
        BASE / "nova_icon_256.png",
    ]:
        if p.exists():
            return str(p)
    return None

# ---------- hidden imports ----------
hidden = []
hidden += collect_submodules("handlers")
hidden += [
    "tkinter", "PIL", "PIL.Image", "PIL.ImageTk",
    "speech_recognition", "gtts", "playsound", "pyttsx3", "pystray",
    "requests", "bs4", "wikipedia", "dateparser", "dateparser_data",
    "langdetect", "dotenv", "numpy", "sympy", "matplotlib",
    "platformdirs", "psutil", "pygame",
    "platform_adapter", "tts_driver", "wake_word_listener",
    "weather_handler", "gui_interface", "intents", "core_engine",
    "encodings", "codecs", "zlib", "bz2", "lzma", "unicodedata",
]
hidden += collect_submodules("encodings")
hidden += collect_submodules("edge_tts")  # Edge Neural TTS bundle
# Pillow/Tk pieces that are discovered dynamically
hidden += ["PIL._tkinter_finder", "PIL.ImageTk", "PIL._imagingtk"]
# Our Linux-safe audio wrapper
hidden += ["audio_player"]

# ---------- datas ----------
datas = []
for fn in ("settings.json", "settings.wsl.json", "settings.linux.json"):
    p = BASE / fn
    if p.exists():
        datas.append((str(p), "."))

for fn in ("nova_icon_big.ico", "nova icon.ico", "nova_icon.ico", "nova_icon_256.png", "poem_bank.json"):
    p = BASE / fn
    if p.exists():
        datas.append((str(p), "."))

datas += add_dir_files("assets", "assets")
datas += add_dir_files("data", "data")
datas += add_dir_files(
    "handlers", "handlers",
    allow_ext={".json", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".ico"}
)
for mod in ("matplotlib", "dateparser", "dateparser_data", "certifi"):
    try:
        datas += collect_data_files(mod)
    except Exception:
        pass

# ship stdlib encodings directly under MEIPASS
ENC_DIR = str(Path(_enc.__file__).parent)
enc_tree = Tree(ENC_DIR, prefix="encodings")

# exclude Windows-only stuff from Linux build
excludes = [
    "win32api", "win32gui", "win32con", "win32com",
    "pycaw", "comtypes", "wmi", "pywin32", "pythoncom", "pywintypes",
    "win32com.client", "win32com.server",
]

icon_path = first_icon()

# ===== main app =====
a1 = Analysis(
    ["main.py"],
    pathex=[str(BASE)] + ([STDLIB] if STDLIB else []),
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=True,  # unpacked stdlib -> safer bootstrap
)
pyz1 = PYZ(a1.pure, a1.zipped_data)
exe1 = EXE(
    pyz1,
    a1.scripts,
    a1.binaries,
    a1.zipfiles,
    a1.datas + enc_tree,   # add encodings/
    [],
    name="NOVA",
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=icon_path,
)

# ===== tray (Linux) =====
tray_entry = "tray_linux.py"
assert (BASE / tray_entry).exists(), "tray_linux.py not found in repo root."
a2 = Analysis(
    [tray_entry],
    pathex=[str(BASE)] + ([STDLIB] if STDLIB else []),
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=True,
)
pyz2 = PYZ(a2.pure, a2.zipped_data)
exe2 = EXE(
    pyz2,
    a2.scripts,
    a2.binaries,
    a2.zipfiles,
    a2.datas + enc_tree,   # add encodings/
    [],
    name="NovaTray",
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=icon_path,
)

coll = COLLECT(
    exe1, exe2,
    a1.binaries, a1.zipfiles, a1.datas,
    a2.binaries, a2.zipfiles, a2.datas,
    enc_tree,
    strip=False, upx=False, upx_exclude=[], name="NOVA_Linux"
)
