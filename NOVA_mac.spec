# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.datastruct import Tree

BASE = Path.cwd()
ICON_ICNS = str(BASE / "icons" / "nova.icns")

datas = []
for root in ["assets","data","handlers","logs"]:
    p = BASE / root
    if p.is_dir():
        datas += Tree(str(p), prefix=root)
for fn in ["settings.json","curiosity_data.json","utils.py"]:
    if (BASE / fn).exists():
        datas.append((str(BASE / fn), "."))

hidden = []
hidden += collect_submodules("handlers")
hidden += ["tkinter","PIL","PIL.Image","PIL.ImageTk","PIL._tkinter_finder",
           "speech_recognition","pyttsx3","pystray","requests","bs4","wikipedia",
           "dateparser","dateparser_data","langdetect","platformdirs","psutil",
           "numpy","sympy","matplotlib","objc","AppKit","Foundation","Quartz"]
for m in ["matplotlib","dateparser","dateparser_data","certifi"]:
    try: datas += collect_data_files(m)
    except Exception: pass

excludes = ["win32com","comtypes","pythoncom","pywintypes","wmi"]

a1 = Analysis(["main.py"], pathex=[str(BASE)], datas=datas,
              hiddenimports=hidden, excludes=excludes)
pyz1 = PYZ(a1.pure, a1.zipped_data)
exe1 = EXE(pyz1, a1.scripts, a1.binaries, a1.zipfiles, a1.datas, [],
           name="Nova", console=False, icon=ICON_ICNS)
app_main = BUNDLE(exe1, name="Nova.app", icon=ICON_ICNS,
                  bundle_identifier="com.novaai.Nova",
                  info_plist={"NSMicrophoneUsageDescription":
                              "Nova needs microphone access to listen to you.",
                              "LSApplicationCategoryType":"public.app-category.utilities"})

a2 = Analysis(["tray_app.py"], pathex=[str(BASE)], datas=[],
              hiddenimports=hidden, excludes=excludes, noarchive=True)
pyz2 = PYZ(a2.pure, a2.zipped_data)
exe2 = EXE(pyz2, a2.scripts, a2.binaries, a2.zipfiles, a2.datas, [],
           name="NovaTray", console=False, icon=ICON_ICNS)
app_tray = BUNDLE(exe2, name="NovaTray.app", icon=ICON_ICNS,
                  bundle_identifier="com.novaai.NovaTray",
                  info_plist={"LSUIElement": True,
                              "NSMicrophoneUsageDescription":
                              "Nova Tray listens for your wake word."})

coll = COLLECT(app_main, app_tray, a1.binaries, a1.zipfiles, a1.datas,
               a2.binaries, a2.zipfiles, a2.datas, name="NOVA_mac")
