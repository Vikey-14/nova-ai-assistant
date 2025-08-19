# -*- mode: python ; coding: utf-8 -*-

import os, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.datastruct import Tree

block_cipher = None

# -------- Robust project root detection --------
def _resolve_base():
    if '__file__' in globals() and __file__:
        return Path(__file__).parent.resolve()
    for arg in sys.argv[1:]:
        if str(arg).lower().endswith('.spec'):
            return Path(arg).resolve().parent
    return Path.cwd()

BASE = _resolve_base()

# -----------------------------
# Hidden imports (dynamic deps)
# -----------------------------
hiddenimports = [
    # TTS / audio / NLP stack
    *collect_submodules('pyttsx3'),
    *collect_submodules('pygame'),
    'speech_recognition',
    'pyaudio',
    'langdetect',
    'dateparser',
    'dateparser.languages',
    'dateparser.timezone_parser',

    # Real system tray
    *collect_submodules('pystray'),

    # Tk / PIL / Matplotlib glue
    'tkinter',
    'PIL._tkinter_finder',
    'matplotlib.backends.backend_tkagg'
]

# Ensure dynamically imported weather handler is frozen
hiddenimports += ['handlers.weather_commands']

# Windows audio/COM helpers
hiddenimports += [
    *collect_submodules('comtypes'),
    'pythoncom',
    'pywintypes',
]

# utils.py import-time deps (bundle so runtime has them)
hiddenimports += [
    'wmi',
    'win32com', 'win32com.client', 'win32com.server',
    'pycaw', 'pycaw.pycaw',
    'gtts',
    'playsound',
]

# NEW: used by tray’s stricter window/process detection
hiddenimports += ['psutil']

# Optional vendor TTS stacks (only if installed)
for opt_pkg in [
    'boto3', 'botocore',
    'azure.cognitiveservices.speech',
    'google.cloud.texttospeech',
]:
    try:
        hiddenimports += collect_submodules(opt_pkg)
    except Exception:
        pass

# Your local project modules (leave out 'utils' on purpose; runtime hook pins local utils.py)
hiddenimports += [
    'gui_interface',
    'core_engine',
    'memory_handler',
    'normalizer',
    'wake_word_listener',
    'intents',
    'handlers.memory_commands',
]

# Include all handlers.* submodules automatically (covers chemistry_solver, etc.)
try:
    hiddenimports += collect_submodules('handlers')
except Exception:
    pass

# -----------------------------
# Data files for Analysis (tuples only)
# -----------------------------
datas = []

# Library datasets
try:
    datas += collect_data_files('dateparser', include_py_files=True)
except Exception:
    pass
try:
    datas += collect_data_files('dateparser_data', include_py_files=True)
except Exception:
    pass
try:
    datas += collect_data_files('langdetect')
except Exception:
    pass

# Certifi CA bundle (HTTPS)
try:
    datas += collect_data_files('certifi')
    hiddenimports.append('certifi')
except Exception:
    pass

# Helpers
def _abs(p: str) -> Path:
    pth = Path(p)
    return pth if pth.is_absolute() else (BASE / pth)

def add_file_if_exists(path: str, dest: str = '.'):
    src = _abs(path)
    if src.is_file():
        datas.append((str(src), dest))

def add_dir_nonpy(root: str, prefix: str):
    root_path = _abs(root)
    if not root_path.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fn in filenames:
            if fn.endswith('.py') or fn.endswith('.pyc'):
                continue
            src = Path(dirpath) / fn
            rel = os.path.relpath(src, root_path)
            dest_dir = os.path.join(prefix, os.path.dirname(rel)).replace('\\', '/')
            if dest_dir in ('', '.'):
                dest_dir = prefix
            datas.append((str(src), dest_dir))

# Top-level files commonly referenced at runtime
for fname in [
    'settings.json',
    'chemistry_table.json',
    'curiosity_data.json',
    'poem_bank.json',
    'nova_icon.ico',
    'nova_logs.txt',
]:
    add_file_if_exists(fname, '.')

# Ensure local utils.py is present for the runtime hook to pin
add_file_if_exists('utils.py', '.')

# Catch-all for any other root-level JSONs
try:
    for fname in os.listdir(BASE):
        if str(fname).lower().endswith('.json'):
            add_file_if_exists(str(BASE / fname), '.')
except Exception:
    pass

# Include all non-.py content from handlers/ and data/
add_dir_nonpy('handlers', 'handlers')
add_dir_nonpy('data', 'data')
# Include assets (icons, images used by tray tip, etc.)
add_dir_nonpy('assets', 'assets')

# Optional hooks folder
hookspaths = [str(BASE / 'hooks')] if (BASE / 'hooks').is_dir() else []

# =========================================================
# ==============  MAIN APP: NOVA.exe  =====================
# =========================================================
a_main = Analysis(
    [str(BASE / 'main.py')],
    pathex=[str(BASE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspaths,
    hooksconfig={},
    # Runtime hooks: pin local utils + quiet Matplotlib cache/logs (main app uses them)
    runtime_hooks=[
        str(BASE / 'hooks' / 'rthook_force_local_utils.py'),
        str(BASE / 'hooks' / 'rthook_mpl_quiet.py'),
    ],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_main = PYZ(a_main.pure, a_main.zipped_data, cipher=block_cipher)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name='NOVA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / 'nova_icon.ico'),
)

# =========================================================
# ==============  TRAY APP: Nova Tray.exe  ================
# =========================================================
# Tray does not need the main runtime hooks; keep it lean.
a_tray = Analysis(
    [str(BASE / 'tray_app.py')],
    pathex=[str(BASE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspaths,
    hooksconfig={},
    runtime_hooks=[],   # no special hooks for the tray
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_tray = PYZ(a_tray.pure, a_tray.zipped_data, cipher=block_cipher)

exe_tray = EXE(
    pyz_tray,
    a_tray.scripts,
    [],
    exclude_binaries=True,
    name='Nova Tray',   # <-- produces "Nova Tray.exe"
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,      # tray is GUI-only too
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / 'nova_icon.ico'),
)

# =========================================================
# ==============  COLLECT (one folder)  ===================
# =========================================================
collect_args = [
    exe_main,
    exe_tray,
    # pack both analyses' artifacts
    a_main.binaries, a_main.zipfiles, a_main.datas,
    a_tray.binaries, a_tray.zipfiles, a_tray.datas,
]

for folder in ['assets', 'data', 'handlers', 'logs', 'icons', 'sounds']:
    folder_path = BASE / folder
    if folder_path.is_dir():
        collect_args.append(Tree(str(folder_path), prefix=folder))

coll = COLLECT(
    *collect_args,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NOVA',   # dist/NOVA/ will contain NOVA.exe and Nova Tray.exe
)
