#!/bin/bash
# <swiftbar.title>Claude Usage</swiftbar.title>
# <swiftbar.version>v1.0.0</swiftbar.version>
# <swiftbar.author>Ethan Cloete</swiftbar.author>
# <swiftbar.author.github>EillotBappo</swiftbar.author.github>
# <swiftbar.desc>Claude Code quota (5h / 7-day) and token usage in the menubar, with a local dashboard.</swiftbar.desc>
# <swiftbar.dependencies>python3</swiftbar.dependencies>
# <swiftbar.abouturl>https://github.com/EillotBappo/claude-usage-swiftbar</swiftbar.abouturl>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# Resolve the symlink SwiftBar runs so lib/ is found wherever the repo lives.
SELF="$0"; while [ -L "$SELF" ]; do SELF="$(readlink "$SELF")"; done
ROOT="$(cd "$(dirname "$SELF")" && pwd)"
export PYTHONPATH="$ROOT/lib" SWIFTBAR_PLUGIN_PATH="${SWIFTBAR_PLUGIN_PATH:-$0}"
# Prefer an interpreter with Pillow (crisp dropdown rows); any python3 works without it.
if [ -n "${CLAUDE_USAGE_PYTHON:-}" ]; then PY="$CLAUDE_USAGE_PYTHON"; else
  PY=""; for c in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 "$(command -v python3)"; do
    [ -x "$c" ] && "$c" -c 'import PIL' 2>/dev/null && { PY="$c"; break; }; done
  [ -n "$PY" ] || PY="$(command -v python3 || echo /usr/bin/python3)"
fi

case "$1" in
  refresh)  # expire the quota cache + clear backoff so the next tick refetches
    C="${CLAUDE_USAGE_CACHE:-$HOME/.cache/claude-usage}"
    rm -f "$C/quota.backoff"; [ -f "$C/quota.json" ] && touch -t 200001010000 "$C/quota.json"; exit 0 ;;
  open)     # open [tab] → start dashboard server if needed, open browser
    exec "$PY" -m claude_usage.server "${2:-overview}" ;;
  serve)    # foreground server (debugging)
    exec "$PY" -m claude_usage.server --serve ;;
esac

"$PY" -m claude_usage.menubar 2>>"${CLAUDE_USAGE_CACHE:-$HOME/.cache/claude-usage}/menubar.log" || {
  echo "✳︎ ?"; echo "---"; echo "claude-usage failed — see ~/.cache/claude-usage/menubar.log | color=#FF3B30"
  echo "Open dashboard | bash='$0' param1=open terminal=false"
}
