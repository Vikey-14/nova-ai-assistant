#!/usr/bin/env bash
set -e
PLIST="$HOME/Library/LaunchAgents/com.novaai.tray.plist"
launchctl unload "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "Nova Tray autostart removed."
