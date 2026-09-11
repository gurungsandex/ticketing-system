#!/usr/bin/env bash
# ============================================================
#  IT Ticketing System — macOS client uninstaller
#
#  Removes the LaunchAgent so nothing tries to start the client
#  again, then optionally removes the app and its stored data.
#
#  Usage:  ./uninstall.sh [--purge]
#            --purge  also delete the client's saved data
#                     (client id, settings, offline queue)
# ============================================================
set -euo pipefail

LABEL="com.ticketing.helpdesk.client"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
APP="/Applications/HelpdeskClient.app"
DATA="$HOME/Library/Application Support/HelpdeskClient"

PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

echo "Uninstalling IT Ticketing client..."

# 1. Stop it and remove the login agent.
if launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null; then
    echo "  Stopped background agent."
fi
if [ -f "$PLIST" ]; then
    rm -f "$PLIST"
    echo "  Removed LaunchAgent: $PLIST"
else
    echo "  No LaunchAgent found (already removed)."
fi

# 2. Stop any copy still running.
pkill -f "HelpdeskClient" 2>/dev/null && echo "  Stopped running client." || true

# 3. Remove the application bundle.
if [ -d "$APP" ]; then
    rm -rf "$APP"
    echo "  Removed $APP"
fi

# 4. Optionally remove stored data.
if [ "$PURGE" -eq 1 ]; then
    if [ -d "$DATA" ]; then
        rm -rf "$DATA"
        echo "  Removed client data: $DATA"
    fi
else
    echo "  Kept client data at: $DATA"
    echo "  (re-run with --purge to remove it)"
fi

echo "Done."
