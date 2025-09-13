#!/usr/bin/env bash
set -euo pipefail

# ================================
# Nova AppImage builder (Linux)
# ================================
# Usage:
#   ./scripts/build_appimage.sh [VERSION]
# If VERSION is omitted, we try the latest git tag (vX.Y.Z) or fall back to plain name.

# ---- Resolve paths ----
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SPEC="NOVA_Linux.spec"           # matches repo/spec casing
DISTDIR="dist_linux"
APPDIR="build/AppDir"

# ---- Version for output filename ----
APPVER="${1:-}"
if [[ -z "$APPVER" ]]; then
  APPVER="$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')" || true
fi
OUTNAME="Nova-x86_64.AppImage"
[[ -n "$APPVER" ]] && OUTNAME="Nova_${APPVER}-x86_64.AppImage"

# ---- Sanity ----
if [[ ! -f "$SPEC" ]]; then
  echo "ERROR: $SPEC not found at project root." >&2
  exit 1
fi

# ---- Build with PyInstaller (uses your Linux spec) ----
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools pyinstaller
# Optional deps file (ok if missing):
pip install -r requirements.linux.txt || pip install -r requirements.txt || true

# Build into dist_linux to keep things tidy
pyinstaller --distpath "$DISTDIR" -y "$SPEC"   # -> dist_linux/NOVA_Linux/{Nova,NovaTray,...}

# ---- AppDir layout ----
rm -rf build
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy built payload
if [[ ! -d "$DISTDIR/NOVA_Linux" ]]; then
  echo "ERROR: expected $DISTDIR/NOVA_Linux to exist after build." >&2
  exit 1
fi
cp -a "$DISTDIR/NOVA_Linux/." "$APPDIR/usr/bin/"

# ---- Icon (256px PNG expected) ----
ICON_SRC="assets/nova_icon_256.png"
if [[ ! -f "$ICON_SRC" ]]; then
  if command -v ffmpeg >/dev/null 2>&1 && [[ -f assets/nova_icon_big.ico ]]; then
    ffmpeg -y -i assets/nova_icon_big.ico -vf scale=256:256 "$ICON_SRC"
  else
    echo "WARNING: Missing assets/nova_icon_256.png (and cannot convert from .ico)."
  fi
fi
if [[ -f "$ICON_SRC" ]]; then
  install -m 0644 "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nova.png"
fi

# ---- AppRun (supports --tray) ----
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
set -e
# Prefer gTTS by default on Linux (tweak if needed)
export NOVA_TTS="${NOVA_TTS:-gtts}"
DIR="$(cd "$(dirname "$0")/usr/bin" && pwd)"
if [[ "${1:-}" == "--tray" ]]; then
  shift
  exec "$DIR/NovaTray" "$@"
else
  exec "$DIR/Nova" "$@"
fi
EOF
chmod +x "$APPDIR/AppRun"

# ---- Desktop entries (menus) ----
# Main app launcher (visible)
cat > "$APPDIR/usr/share/applications/nova.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Nova
Comment=Nova
Exec=Nova
TryExec=Nova
Icon=nova
Terminal=false
Categories=Utility;Education;
EOF

# Tray helper (hidden from menus; still useful for integration)
cat > "$APPDIR/usr/share/applications/novatray.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Nova Tray
Comment=Nova system tray helper
Exec=NovaTray
TryExec=NovaTray
Icon=nova
Terminal=false
Categories=Utility;
NoDisplay=true
EOF

# ---- Fetch appimagetool (once) ----
mkdir -p tools
if [[ ! -x tools/appimagetool ]]; then
  curl -fsSL -o tools/appimagetool \
    https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage
  chmod +x tools/appimagetool
fi

# ---- Build AppImage ----
ARCH=x86_64 tools/appimagetool "$APPDIR" "$OUTNAME"

echo
echo "✅ Built $OUTNAME"
echo "• Run assistant:   ./$OUTNAME"
echo "• Run tray only:   ./$OUTNAME --tray"
