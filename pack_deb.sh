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

# Binaries from PyInstaller (must already exist)
cp dist_linux/NOVA_Linux/NOVA     "$PKGROOT/usr/bin/NOVA"
cp dist_linux/NOVA_Linux/NovaTray "$PKGROOT/usr/bin/NovaTray"
chmod 0755 "$PKGROOT/usr/bin/NOVA" "$PKGROOT/usr/bin/NovaTray"

# Icon
cp assets/nova_icon_256.png "$PKGROOT/usr/share/icons/hicolor/256x256/apps/nova.png"
chmod 0644 "$PKGROOT/usr/share/icons/hicolor/256x256/apps/nova.png"

# Launcher (.desktop)
cat > "$PKGROOT/usr/share/applications/nova.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Nova (AI Assistant)
Comment=Talk to Nova
Exec=/usr/bin/NOVA
Icon=nova
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=Nova
EOF
chmod 0644 "$PKGROOT/usr/share/applications/nova.desktop"

# Autostart for tray
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

# Minimal Debian docs (non-native version like 1.0.2-1)
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

# Control metadata
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

# Post-install/remove hooks
cat > "$PKGROOT/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 0755 "$PKGROOT/DEBIAN/postinst"

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

# Build with root ownership in the archive
dpkg-deb --build --root-owner-group "$PKGROOT" "/tmp/${PKGFILE}"
mkdir -p dist_linux
mv "/tmp/${PKGFILE}" dist_linux/
echo "Built: dist_linux/${PKGFILE}"
