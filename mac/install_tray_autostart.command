#!/usr/bin/env bash
set -e
PLIST="$HOME/Library/LaunchAgents/com.novaai.tray.plist"
mkdir -p "$(dirname "$PLIST")"
cp "$(dirname "$0")/LaunchAgents/com.novaai.tray.plist" "$PLIST"
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"
echo "Nova Tray set to start on login."
