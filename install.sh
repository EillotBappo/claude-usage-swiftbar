#!/bin/bash
# claude-usage-swiftbar installer. Usage: curl -fsSL https://raw.githubusercontent.com/EillotBappo/claude-usage-swiftbar/main/install.sh | bash
set -euo pipefail
REPO="https://github.com/EillotBappo/claude-usage-swiftbar.git"
DEST="${CLAUDE_USAGE_INSTALL_DIR:-$HOME/.claude-usage-swiftbar}"
PLUGIN_DIR="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
PLUGIN_DIR="${PLUGIN_DIR:-$HOME/.swiftbar}"

command -v python3 >/dev/null || { echo "python3 is required (xcode-select --install)"; exit 1; }
[ -d /Applications/SwiftBar.app ] || [ -d "$HOME/Applications/SwiftBar.app" ] || echo "note: SwiftBar.app not found — install from https://swiftbar.app or 'brew install swiftbar'"

if [ -f "$(dirname "$0")/claude-usage.1m.sh" ] && [ "$(cd "$(dirname "$0")" && pwd)" != "$DEST" ]; then
  echo "→ copying $(cd "$(dirname "$0")" && pwd) to $DEST"; rm -rf "$DEST"; cp -R "$(cd "$(dirname "$0")" && pwd)" "$DEST"
elif [ -d "$DEST/.git" ]; then
  echo "→ updating $DEST"; git -C "$DEST" pull -q --ff-only
elif [ ! -d "$DEST" ]; then
  echo "→ cloning to $DEST"; git clone -q "$REPO" "$DEST"
fi
chmod +x "$DEST/claude-usage.1m.sh"

mkdir -p "$PLUGIN_DIR"
# Replace the older single-file plugin if present.
for old in "$PLUGIN_DIR/claude-usage.1m.sh" "$PLUGIN_DIR/lib/claude-usage.py"; do
  if [ -e "$old" ] && [ ! -L "$old" ]; then mv "$old" "$old.bak"; echo "→ backed up $old → $old.bak"; fi
done
ln -sfn "$DEST/claude-usage.1m.sh" "$PLUGIN_DIR/claude-usage.1m.sh"
echo "→ linked $PLUGIN_DIR/claude-usage.1m.sh"

CFG="${CLAUDE_USAGE_HOME:-$HOME/.config/claude-usage}"; mkdir -p "$CFG"
[ -f "$CFG/settings.json" ] || { echo '{}' > "$CFG/settings.json"; echo "→ created $CFG/settings.json (defaults)"; }

echo "→ indexing transcripts (first run can take a few seconds)…"
PYTHONPATH="$DEST/lib" python3 -c 'from claude_usage import db, scan, settings; c=db.connect(); r=scan.run(c, settings.load()); print(f"   {r[\"added\"]} messages from {r[\"files\"]} files")'

open -g "swiftbar://refreshallplugins" 2>/dev/null || true
echo "✓ installed. Dashboard: $DEST/claude-usage.1m.sh open   ·   Settings: $CFG/settings.json"
