# -*- mode: python ; coding: utf-8 -*-
import os, sysconfig
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.datastruct import Tree
import encodings as _enc

BASE = Path.cwd()
STDLIB = sysconfig.get_paths().get("stdlib", "")

# ---------------- utils ----------------
def add_dir_files(root_dir, target_prefix, allow_ext=None):
    pairs = []
    root = BASE / root_dir
    if root.is_dir():
        for dp, _, fnames in os.walk(root):
            rel_dir = Path(dp).relative_to(root)
            dest_dir = str(Path(target_prefix) / rel_dir).replace("\\", "/") or "."
            for fn in fnames:
                if allow_ext and Path(fn).suffix.lower() not in allow_ext:
                    continue
                src = Path(dp) / fn
                pairs.append((str(src), dest_dir))
    return pairs

def add_broken_zip_assets(target_prefix="assets"):
    pairs = []
    for p in BASE.iterdir():
        if p.is_file() and p.name.startswith("assets\\"):
            _after = p.name.split("\\", 1)[1] or p.name
            pairs.append((str(p), f"{target_prefix}"))
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

# ---------------- hidden imports ----------------
hidden = []
hidden += collect_submodules("handlers")
hidden += [
    # GUI / imaging
    "tkinter", "PIL", "PIL.Image", "PIL.ImageTk",

    # Speech / TTS / audio / tray
    "speech_recognition", "gtts", "playsound", "pyttsx3", "pystray",

    # Net / parsing / NLP / math / plotting
    "requests", "bs4", "wikipedia", "dateparser", "dateparser_data",
    "langdetect", "dotenv", "numpy", "sympy", "matplotlib",

    # System helpers
    "platformdirs", "psutil", "pygame",

    # Your modules
    "platform_adapter", "tts_driver", "wake_word_listener",
    "weather_handler", "gui_interface", "intents", "core_engine",
    "audio_player",

    # stdlib codecs
    "encodings", "codecs", "zlib", "bz2", "lzma", "unicodedata",
]
hidden += collect_submodules("encodings")

# NEW: ASR/VAD engines
try:
    hidden += collect_submodules("vosk")
except Exception:
    pass
try:
    hidden += collect_submodules("webrtcvad")
except Exception:
    pass

try:
    hidden += collect_submodules("edge_tts")
except Exception:
    pass

hidden += ["PIL._tkinter_finder", "PIL.ImageTk", "PIL._imagingtk"]

# GTK/AppIndicator GI backends for pystray on Linux
hidden += [
    "gi", "gi.repository", "gi.overrides",
    "gi.repository.GObject", "gi.repository.Gio", "gi.repository.GLib",
    "gi.repository.GdkPixbuf", "gi.repository.Gtk",
    "gi.repository.AyatanaAppIndicator3", "gi.repository.AppIndicator3",
]

# ---------------- datas ----------------
datas = []

# settings files (include if present)
for fn in ("settings.json", "settings.wsl.json", "settings.linux.json"):
    p = BASE / fn
    if p.exists():
        datas.append((str(p), "."))

# root-level hashed blocklist
p_hashed = BASE / "hashed.txt"
if p_hashed.exists():
    datas.append((str(p_hashed), "."))

# top-level odds & ends
for fn in ("nova_icon_big.ico", "nova icon.ico", "nova_icon.ico",
           "nova_icon_256.png", "nova_face_glow.png", "poem_bank.json"):
    p = BASE / fn
    if p.exists():
        datas.append((str(p), "."))

# assets/, and rescue incorrectly extracted assets
if (BASE / "assets").is_dir():
    datas += add_dir_files("assets", "assets")
datas += add_broken_zip_assets("assets")

# data/ and handlers/ side-files
datas += add_dir_files("data", "data")
datas += add_dir_files(
    "handlers", "handlers",
    allow_ext={".json", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".ico"}
)

# lib data expected by deps
for mod in ("matplotlib", "dateparser", "dateparser_data", "certifi"):
    try:
        datas += collect_data_files(mod)
    except Exception:
        pass

# Piper (offline) — manifest, models, both Linux arch bins
man = BASE / "third_party/piper/models_manifest.json"
if man.is_file():
    datas.append((str(man), "third_party/piper"))
datas += add_dir_files("third_party/piper/models",      "third_party/piper/models")
datas += add_dir_files("third_party/piper/linux-x64",   "third_party/piper/linux-x64")
datas += add_dir_files("third_party/piper/linux-arm64", "third_party/piper/linux-arm64")

# NEW: ship Vosk models directory
datas += add_dir_files("vosk_models", "vosk_models")

# stdlib encodings as a Tree so they’re available in MEIPASS
ENC_DIR = str(Path(_enc.__file__).parent)
enc_tree = Tree(ENC_DIR, prefix="encodings")

# exclude Windows-only things from Linux build
excludes = [
    "win32api", "win32gui", "win32con", "win32com",
    "pycaw", "comtypes", "wmi", "pywin32", "pythoncom", "pywintypes",
    "win32com.client", "win32com.server",
]

icon_path = first_icon()

# ================= main app =================
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
    noarchive=True,
)
pyz1 = PYZ(a1.pure, a1.zipped_data)
exe1 = EXE(
    pyz1,
    a1.scripts,
    a1.binaries,
    a1.zipfiles,
    a1.datas + enc_tree,
    [],
    name="Nova",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=icon_path,
)

# ================= tray (Linux) =================
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
    a2.datas + enc_tree,
    [],
    name="NovaTray",
    debug=False,
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
