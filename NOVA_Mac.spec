# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

BASE = Path.cwd()
ICON_ICNS = str(BASE / "icons" / "nova.icns")

# ---------------- Version (from env APPVER or VERSION.txt) ----------------
def resolve_version() -> str:
    v = os.environ.get("APPVER", "").strip()
    if not v:
        vt = BASE / "VERSION.txt"
        if vt.exists():
            v = vt.read_text(encoding="utf-8").strip()
    return v or "1.0.0"

APPVER = resolve_version()

# ---- data files as (src, dst) pairs ----
datas = []
for root in ["assets", "data", "handlers", "logs"]:
    p = BASE / root
    if p.is_dir():
        for f in p.rglob("*"):
            if f.is_file():
                datas.append((str(f), str(f.parent.relative_to(BASE))))

for fn in ["settings.json", "curiosity_data.json", "utils.py"]:
    if (BASE / fn).exists():
        datas.append((str(BASE / fn), "."))

# --- Include ONLY the mac Piper bits + all models & manifest ---
def add_tree(root: str):
    root = Path(root)
    if root.is_dir():
        for f in root.rglob("*"):
            if f.is_file():
                dst = str(f.parent.relative_to(BASE))
                datas.append((str(f), dst))

# Piper manifest + models for all languages you ship
add_tree("third_party/piper/models")
if (BASE / "third_party/piper/models_manifest.json").exists():
    datas.append(("third_party/piper/models_manifest.json", "third_party/piper"))

# Piper binaries for BOTH mac arches (don’t pull linux/windows to keep size down)
add_tree("third_party/piper/macos-x64")
add_tree("third_party/piper/macos-arm64")

# hidden imports & extra package data
hidden = []
hidden += collect_submodules("handlers")
hidden += [
    "tkinter", "PIL", "PIL.Image", "PIL.ImageTk", "PIL._tkinter_finder",
    "speech_recognition", "pyttsx3", "pystray", "requests", "bs4", "wikipedia",
    "dateparser", "dateparser_data", "langdetect", "platformdirs", "psutil",
    "numpy", "sympy", "matplotlib", "objc", "AppKit", "Foundation", "Quartz",
    "pyttsx3.drivers", "pyttsx3.drivers.nsss",
]
for m in ["matplotlib", "dateparser", "dateparser_data", "certifi"]:
    try:
        datas += collect_data_files(m)
    except Exception:
        pass

excludes = ["win32com", "comtypes", "pythoncom", "pywintypes", "wmi"]

# ---- main app ----
a1 = Analysis(["main.py"], pathex=[str(BASE)], datas=datas,
              hiddenimports=hidden, excludes=excludes)
pyz1 = PYZ(a1.pure, a1.zipped_data)
exe1 = EXE(pyz1, a1.scripts, a1.binaries, a1.zipfiles, a1.datas, [],
           name="Nova", console=False, icon=ICON_ICNS)

app_main = BUNDLE(
    exe1,
    name="Nova.app",
    icon=ICON_ICNS,
    bundle_identifier="com.novaai.Nova",
    info_plist={
        "CFBundleName": "Nova",
        "CFBundleDisplayName": "Nova",
        "CFBundleExecutable": "Nova",
        "CFBundleShortVersionString": APPVER,
        "CFBundleVersion": APPVER,
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSMicrophoneUsageDescription": "Nova needs microphone access to listen to you.",
    },
)

# ---- tray app ----
tray_entry = "tray_app.py" if (BASE / "tray_app.py").exists() else "tray_linux.py"
a2 = Analysis([tray_entry], pathex=[str(BASE)], datas=datas,
              hiddenimports=hidden, excludes=excludes, noarchive=True)
pyz2 = PYZ(a2.pure, a2.zipped_data)
exe2 = EXE(pyz2, a2.scripts, a2.binaries, a2.zipfiles, a2.datas, [],
           name="NovaTray", console=False, icon=ICON_ICNS)

app_tray = BUNDLE(
    exe2,
    name="Nova Tray.app",
    icon=ICON_ICNS,
    bundle_identifier="com.novaai.NovaTray",
    info_plist={
        "LSUIElement": True,
        "CFBundleName": "Nova Tray",
        "CFBundleDisplayName": "Nova Tray",
        "CFBundleExecutable": "NovaTray",
        "CFBundleShortVersionString": APPVER,
        "CFBundleVersion": APPVER,
        "NSMicrophoneUsageDescription": "Nova Tray listens for your wake word.",
    },
)

apps = [app_main, app_tray]
