#!/usr/bin/env bash
set -euo pipefail

APPVER="${1:-1.0.2-1}"
ARCH=amd64
PKGNAME=nova-ai-assistant
PKGROOT="/tmp/nova_ai_assistant_${APPVER}_${ARCH}"
PKGFILE="nova_ai_assistant_${APPVER}_${ARCH}.deb"

rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/DEBIAN" \
         "$PKGROOT/usr/bin" \
         "$PKGROOT/usr/share/applications" \
         "$PKGROOT/usr/share/icons/hicolor/256x256/apps" \
         "$PKGROOT/etc/xdg/autostart" \
         "$PKGROOT/usr/share/doc/${PKGNAME}"

# ---------------- Binaries from PyInstaller (must already exist) ----------------
cp dist_linux/NOVA_Linux/NOVA     "$PKGROOT/usr/bin/NOVA"
cp dist_linux/NOVA_Linux/NovaTray "$PKGROOT/usr/bin/NovaTray"
chmod 0755 "$PKGROOT/usr/bin/NOVA" "$PKGROOT/usr/bin/NovaTray"

# ---------------- Icon ----------------
cp assets/nova_icon_256.png "$PKGROOT/usr/share/icons/hicolor/256x256/apps/nova.png"
chmod 0644 "$PKGROOT/usr/share/icons/hicolor/256x256/apps/nova.png"

# ---------------- Launcher (.desktop) — Applications menu entry ----------------
cat > "$PKGROOT/usr/share/applications/nova.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=NOVA
Comment=Nova AI Assistant
Exec=/usr/bin/NOVA
Icon=nova
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=Nova
EOF
chmod 0644 "$PKGROOT/usr/share/applications/nova.desktop"

# ---------------- Autostart for tray ----------------
cat > "$PKGROOT/etc/xdg/autostart/nova-tray.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Nova Tray
Comment=Nova system tray helper
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
Upstream-Name: Nova AI Assistant
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
 Installs Nova (main app) and NovaTray (system tray helper).
Depends: libc6 (>= 2.31), libstdc++6 (>= 10), libx11-6, libxcb1, libxext6, libxrender1, libxrandr2, libxi6, libxfixes3, libxcursor1, libxinerama1, libxss1, libgtk-3-0 | libgtk2.0-0, libasound2, libpulse0
Recommends: ffmpeg | mpg123
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

# 1) Put a NOVA launcher on each existing user's Desktop (like Windows)
APP_DESKTOP="/usr/share/applications/nova.desktop"
for d in /home/*; do
  u="$(basename "$d")"
  desk="$d/Desktop"
  [ -d "$desk" ] || mkdir -p "$desk"
  cp -f "$APP_DESKTOP" "$desk/NOVA.desktop" 2>/dev/null || true
  chmod +x "$desk/NOVA.desktop" 2>/dev/null || true
  chown "$u":"$u" "$desk/NOVA.desktop" 2>/dev/null || true
  # Mark trusted to avoid "untrusted launcher" (skip on WSL or no GUI bus)
  if ! is_wsl && command -v gio >/dev/null 2>&1; then
    if su - "$u" -c 'test -n "$DBUS_SESSION_BUS_ADDRESS"' 2>/dev/null; then
      su - "$u" -c "gio set \"$desk/NOVA.desktop\" metadata::trusted true" 2>/dev/null || true
    fi
  fi
done

# 1b) Seed future users with a Desktop icon via /etc/skel
if [ -d /etc/skel ]; then
  mkdir -p /etc/skel/Desktop
  cp -f "$APP_DESKTOP" /etc/skel/Desktop/NOVA.desktop 2>/dev/null || true
  chmod +x /etc/skel/Desktop/NOVA.desktop 2>/dev/null || true
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

# ---------------- Post-remove (unchanged) ----------------
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
echo "Built: dist_linux/${PKGFILE}"
