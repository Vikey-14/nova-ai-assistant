# -*- mode: python ; coding: utf-8 -*-

import os, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
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
    # TTS / audio / NLP
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
    'matplotlib.backends.backend_tkagg',

    # SAPI5 / COM
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'win32com.client',

    # Project modules
    'gui_interface',
    'core_engine',
    'memory_handler',
    'normalizer',
    'wake_word_listener',
    'intents',
    'handlers.memory_commands',
]

# Include all handlers.* automatically
try:
    hiddenimports += collect_submodules('handlers')
except Exception:
    pass

# Windows audio/COM helpers
hiddenimports += [
    *collect_submodules('comtypes'),
    'pythoncom',
    'pywintypes',
]

# Optional stacks (safe if missing)
for opt_pkg in [
    'boto3', 'botocore',
    'azure.cognitiveservices.speech',
    'google.cloud.texttospeech',
    'edge_tts',
]:
    try:
        hiddenimports += collect_submodules(opt_pkg)
    except Exception:
        pass

# === NEW: ASR/VAD hidden imports ===
try:
    hiddenimports += collect_submodules('vosk')
except Exception:
    pass

try:
    # webrtcvad is a small C-extension; no submodules, but this keeps PyInstaller honest
    hiddenimports += collect_submodules('webrtcvad')
except Exception:
    pass

# -----------------------------
# Data files
# -----------------------------
datas = []

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

# Library datasets
for lib in ('dateparser', 'dateparser_data', 'langdetect', 'certifi'):
    try:
        datas += collect_data_files(lib, include_py_files=(lib != 'langdetect'))
    except Exception:
        pass

# Top-level files referenced at runtime
for fname in [
    'settings.json',
    'chemistry_table.json',
    'curiosity_data.json',
    'poem_bank.json',
    'nova_icon.ico',
    'nova_icon_big.ico',
]:
    add_file_if_exists(fname, '.')

# Ensure local utils.py is present for runtime hook pinning
add_file_if_exists('utils.py', '.')

# Optional name list and entire data dir
add_file_if_exists('data/name_blocklist_en.txt', 'data')
add_dir_nonpy('handlers', 'handlers')
add_dir_nonpy('data', 'data')          # includes build_id.txt etc.
add_dir_nonpy('assets', 'assets')

# 🔒 FORCE-INCLUDE hashed blocklist (no matter what)
if (BASE / 'data' / 'hashed.txt').is_file():
    datas.append((str(BASE / 'data' / 'hashed.txt'), 'data'))
elif (BASE / 'hashed.txt').is_file():
    datas.append((str(BASE / 'hashed.txt'), '.'))

# Piper (optional; include if present)
add_file_if_exists('third_party/piper/models_manifest.json', 'third_party/piper')
add_dir_nonpy('third_party/piper/models',       'third_party/piper/models')
add_dir_nonpy('third_party/piper/windows-x64',  'third_party/piper/windows-x64')

# === NEW: bundle ffmpeg folder (so ffplay is available) ===
# Your repo has ffmpeg\bin\*.exe – include whole folder.
add_dir_nonpy('ffmpeg', 'ffmpeg')

# === NEW: bundle Vosk models folder ===
# You downloaded models to vosk_models/<lang>/model — ship that.
add_dir_nonpy('vosk_models', 'vosk_models')

# Optional hooks folder
hookspaths = [str(BASE / 'hooks_win')] if (BASE / 'hooks_win').is_dir() else []

# ============== MAIN APP ==============
a_main = Analysis(
    [str(BASE / 'main.py')],
    pathex=[str(BASE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspaths,
    hooksconfig={},
    runtime_hooks=[
        str(BASE / 'hooks_win' / 'rthook_force_local_utils.py'),
        str(BASE / 'hooks_win' / 'rthook_mpl_quiet.py'),
    ] if (BASE / 'hooks_win').is_dir() else [],
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
    name='Nova',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(BASE / 'nova_icon_big.ico'),
    version=str(BASE / 'version_info_main.txt'),
)

# ============== TRAY APP ==============
a_tray = Analysis(
    [str(BASE / 'tray_app.py')],
    pathex=[str(BASE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspaths,
    hooksconfig={},
    runtime_hooks=[
        str(BASE / 'hooks_win' / 'rthook_force_local_utils.py'),
    ] if (BASE / 'hooks_win').is_dir() else [],
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
    name='Nova Tray',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(BASE / 'nova_icon_big.ico'),
    version=str(BASE / 'version_info_tray.txt'),
)

collect_args = [
    exe_main, exe_tray,
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
    name='Nova',     # dist\Nova\...
)
