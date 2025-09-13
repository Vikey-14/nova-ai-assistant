#!/usr/bin/env bash
set -euo pipefail

APPVER="${1:-1.0.2-1}"
ARCH=amd64
PKGNAME=nova-ai-assistant
PKGROOT="/tmp/nova_ai_assistant_${APPVER}_${ARCH}"
PKGFILE="nova_ai_assistant_${APPVER}_${ARCH}.deb"

# Where the PyInstaller output ends up
SRC_DIR="dist_linux/NOVA_Linux"
# Where we'll install the full app payload
APPDIR="/opt/nova"

rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/DEBIAN" \
         "$PKGROOT/usr/bin" \
         "$PKGROOT/usr/share/applications" \
         "$PKGROOT/usr/share/icons/hicolor/256x256/apps" \
         "$PKGROOT/etc/xdg/autostart" \
         "$PKGROOT/usr/share/doc/${PKGNAME}" \
         "$PKGROOT${APPDIR}"

# ---------------- App payload: copy EVERYTHING from PyInstaller ----------------
# This preserves hashed.txt, assets/, data/, handlers/, third_party/piper, etc.
cp -a "${SRC_DIR}/." "$PKGROOT${APPDIR}/"

# Ensure main binaries are executable (PyInstaller usually does this already)
chmod 0755 "$PKGROOT${APPDIR}/Nova" "$PKGROOT${APPDIR}/NovaTray" 2>/dev/null || true

# Helper: resolve Piper dir (prefer linux-x64, else linux-arm64)
piper_dir_snippet='
APPDIR="/opt/nova"
if [ -d "$APPDIR/third_party/piper/linux-x64" ]; then
  PIPDIR="$APPDIR/third_party/piper/linux-x64"
elif [ -d "$APPDIR/third_party/piper/linux-arm64" ]; then
  PIPDIR="$APPDIR/third_party/piper/linux-arm64"
else
  PIPDIR=""
fi
if [ -n "$PIPDIR" ]; then
  export LD_LIBRARY_PATH="$PIPDIR:${LD_LIBRARY_PATH:-}"
  export ESPEAK_DATA="$PIPDIR/espeak-ng-data"
  if [ -f "$PIPDIR/libpiper_phonemize.so" ]; then
    export PIPER_PHONEMIZE_LIBRARY="$PIPDIR/libpiper_phonemize.so"
  fi
fi
'

# ---------------- Lightweight wrappers in /usr/bin ----------------
# They set working dir and the Piper env so libs/data are always found.
cat > "$PKGROOT/usr/bin/Nova" <<EOF
#!/bin/sh
${piper_dir_snippet}
cd "/opt/nova" || exit 1
exec "/opt/nova/Nova" "\$@"
EOF
chmod 0755 "$PKGROOT/usr/bin/Nova"

cat > "$PKGROOT/usr/bin/NovaTray" <<EOF
#!/bin/sh
${piper_dir_snippet}
cd "/opt/nova" || exit 1
exec "/opt/nova/NovaTray" "\$@"
EOF
chmod 0755 "$PKGROOT/usr/bin/NovaTray"

# ---------------- Icon ----------------
cp assets/nova_icon_256.png "$PKGROOT/usr/share/icons/hicolor/256x256/apps/nova.png"
chmod 0644 "$PKGROOT/usr/share/icons/hicolor/256x256/apps/nova.png"

# ---------------- App menu launchers (visible) ----------------
cat > "$PKGROOT/usr/share/applications/nova.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Nova
Comment=Talk to Nova
Exec=/usr/bin/Nova
Icon=nova
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=Nova
EOF
chmod 0644 "$PKGROOT/usr/share/applications/nova.desktop"

cat > "$PKGROOT/usr/share/applications/nova-tray.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Nova Tray
Comment=Nova system tray helper
Exec=/usr/bin/NovaTray
Icon=nova
Terminal=false
Categories=Utility;
StartupNotify=false
EOF
chmod 0644 "$PKGROOT/usr/share/applications/nova-tray.desktop"

# ---------------- Autostart entry (hidden) ----------------
cat > "$PKGROOT/etc/xdg/autostart/nova-tray.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Nova Tray (Autostart)
Comment=Auto-start Nova tray helper
Exec=/usr/bin/NovaTray
Icon=nova
X-GNOME-Autostart-enabled=true
NoDisplay=true
Terminal=false
EOF
chmod 0644 "$PKGROOT/etc/xdg/autostart/nova-tray.desktop"

# ---------------- Minimal Debian docs ----------------
printf "nova-ai-assistant (%s) stable; urgency=low\n\n  * Nova release.\n\n -- Nova Team <support@example.com>  %s\n" \
  "$APPVER" "$(date -R)" | gzip -n9 > "$PKGROOT/usr/share/doc/${PKGNAME}/changelog.Debian.gz"
cat > "$PKGROOT/usr/share/doc/${PKGNAME}/copyright" << 'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Nova
Source: https://example.com

Files: *
Copyright: 2025 Nova Team
License: Proprietary
 Permission is granted to install and use this software. Redistribution of
 the binaries or source without permission is prohibited.
EOF
chmod 0644 "$PKGROOT/usr/share/doc/${PKGNAME}/changelog.Debian.gz" \
           "$PKGROOT/usr/share/doc/${PKGNAME}/copyright"

# ---------------- Control metadata ----------------
cat > "$PKGROOT/DEBIAN/control" << EOF
Package: ${PKGNAME}
Version: ${APPVER}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Nova Team <support@example.com>
Homepage: https://your-site.example
Description: Nova – voice AI assistant with tray helper
 Installs Nova (main app) and Nova Tray (system tray helper).
Depends: libc6 (>= 2.31), libstdc++6 (>= 10), libx11-6, libxcb1, libxext6, libxrender1, libxrandr2, libxi6, libxfixes3, libxcursor1, libxinerama1, libxss1, libgtk-3-0, libgirepository-1.0-1, gir1.2-gtk-3.0, libayatana-appindicator3-1 | libappindicator3-1, gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1, libasound2t64 | libasound2, libpulse0, libportaudio2, libsndfile1, libespeak-ng1, wmctrl
Recommends: ffmpeg | mpg123, libayatana-appindicator3-1
EOF

# Preserve user edits to the /etc autostart file
cat > "$PKGROOT/DEBIAN/conffiles" << 'EOF'
/etc/xdg/autostart/nova-tray.desktop
EOF

# ---------------- Post-install: caches + Desktop icons + start tray now ----------------
cat > "$PKGROOT/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e

# 0) Refresh desktop + icon caches
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

is_wsl() {
  grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null
}

# 1) Put a Nova launcher on each existing user's Desktop
APP_DESKTOP="/usr/share/applications/nova.desktop"
for d in /home/*; do
  u="$(basename "$d")"
  desk="$d/Desktop"
  [ -d "$desk" ] || mkdir -p "$desk"
  cp -f "$APP_DESKTOP" "$desk/Nova.desktop" 2>/dev/null || true
  chmod +x "$desk/Nova.desktop" 2>/dev/null || true
  chown "$u":"$u" "$desk/Nova.desktop" 2>/dev/null || true
  if ! is_wsl && command -v gio >/dev/null 2>&1; then
    su - "$u" -c "gio set \"$desk/Nova.desktop\" metadata::trusted true" 2>/dev/null || true
  fi
done

# 1b) Seed future users via /etc/skel
if [ -d /etc/skel ]; then
  mkdir -p /etc/skel/Desktop
  cp -f "$APP_DESKTOP" /etc/skel/Desktop/Nova.desktop 2>/dev/null || true
  chmod +x /etc/skel/Desktop/Nova.desktop 2>/dev/null || true
fi

# 2) Start the tray immediately (best effort; autostart covers next logins)
TRAY_BIN="/usr/bin/NovaTray"
if [ -x "$TRAY_BIN" ]; then
  if [ -n "${SUDO_USER:-}" ] && ! is_wsl; then
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "${XDG_RUNTIME_DIR:-}" ]; then
      su - "$SUDO_USER" -c "nohup \"$TRAY_BIN\" >/dev/null 2>&1 &" || true
    fi
  fi
fi

exit 0
EOF
chmod 0755 "$PKGROOT/DEBIAN/postinst"

# ---------------- Post-remove ----------------
cat > "$PKGROOT/DEBIAN/postrm" << 'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 0755 "$PKGROOT/DEBIAN/postrm"

# ---------------- Build ----------------
dpkg-deb --build --root-owner-group "$PKGROOT" "/tmp/${PKGFILE}"
mkdir -p dist_linux
mv "/tmp/${PKGFILE}" dist_linux/

# ---------------- Stable-name artifact ----------------
(
  cd dist_linux
  if [ -n "${WSL_DISTRO_NAME:-}" ]; then
    cp -f "$PKGFILE" nova_ai_assistant_amd64.deb
  else
    ln -sfn "$PKGFILE" nova_ai_assistant_amd64.deb 2>/dev/null || cp -f "$PKGFILE" nova_ai_assistant_amd64.deb
  fi
)

echo "Built: dist_linux/${PKGFILE}"
echo "Stable: dist_linux/nova_ai_assistant_amd64.deb -> ${PKGFILE}"
