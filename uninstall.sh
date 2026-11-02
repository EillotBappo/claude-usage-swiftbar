#!/bin/bash
# Removes the SwiftBar link and the install dir. --purge also deletes settings + cached data.
set -euo pipefail
DEST="${CLAUDE_USAGE_INSTALL_DIR:-$HOME/.claude-usage-swiftbar}"
PLUGIN_DIR="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || echo "$HOME/.swiftbar")"
rm -f "$PLUGIN_DIR/claude-usage.1m.sh"; rm -rf "$DEST"
pkill -f "claude_usage.server" 2>/dev/null || true
[ "${1:-}" = "--purge" ] && rm -rf "${CLAUDE_USAGE_HOME:-$HOME/.config/claude-usage}" "${CLAUDE_USAGE_CACHE:-$HOME/.cache/claude-usage}"
open -g "swiftbar://refreshallplugins" 2>/dev/null || true
echo "✓ removed"
