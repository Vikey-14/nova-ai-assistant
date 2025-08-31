#!/usr/bin/env bash
set -euo pipefail

# --- locations ---
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SPEC="NOVA_linux.spec"
APPDIR="build/AppDir"

# --- sanity ---
if [ ! -f "$SPEC" ]; then
  echo "ERROR: $SPEC not found at project root." >&2
  exit 1
fi

# --- build with PyInstaller (uses your spec) ---
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools pyinstaller
# If you have requirements.txt, this will speed things up (ok if missing)
pip install -r requirements.txt || true
pyinstaller -y "$SPEC"       # -> dist/NOVA/{NOVA, NovaTray, assets...}

# --- AppDir layout ---
rm -rf build
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a dist/NOVA/* "$APPDIR/usr/bin/"

# --- icon (use 256px PNG) ---
ICON_SRC="assets/nova_icon_256.png"
if [ ! -f "$ICON_SRC" ]; then
  if command -v ffmpeg >/dev/null 2>&1 && [ -f assets/nova_icon_big.ico ]; then
    ffmpeg -y -i assets/nova_icon_big.ico -vf scale=256:256 "$ICON_SRC"
  else
    echo "WARNING: Missing assets/nova_icon_256.png (and ffmpeg not available to convert .ico)."
  fi
fi
[ -f "$ICON_SRC" ] && cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nova.png"

# --- AppRun (supports --tray) ---
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
set -e
export NOVA_TTS=${NOVA_TTS:-gtts}  # natural Google voices by default
DIR="$(dirname "$0")/usr/bin"
if [ "${1:-}" = "--tray" ]; then
  shift
  exec "$DIR/NovaTray" "$@"
else
  exec "$DIR/NOVA" "$@"
fi
EOF
chmod +x "$APPDIR/AppRun"

# --- desktop entries (menus) ---
cat > "$APPDIR/usr/share/applications/nova.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Nova
Comment=Nova AI Assistant
Exec=NOVA
Icon=nova
Terminal=false
Categories=Utility;Education;
EOF

cat > "$APPDIR/usr/share/applications/novatray.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Nova Tray
Comment=Nova tray helper
Exec=NovaTray
Icon=nova
Terminal=false
Categories=Utility;
NoDisplay=true
EOF

# --- appimagetool fetch (once) ---
mkdir -p tools
if [ ! -x tools/appimagetool ]; then
  curl -L -o tools/appimagetool https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage
  chmod +x tools/appimagetool
fi

# --- build AppImage ---
ARCH=x86_64 tools/appimagetool "$APPDIR" "Nova-x86_64.AppImage"

echo
echo "✅ Built Nova-x86_64.AppImage"
echo "• Run assistant:   ./Nova-x86_64.AppImage"
echo "• Run tray only:   ./Nova-x86_64.AppImage --tray"
