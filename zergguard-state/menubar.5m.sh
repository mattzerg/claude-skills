#!/usr/bin/env bash
# SwiftBar / xbar plugin — single icon showing ZergGuard posture.
# Install: `brew install --cask swiftbar` then symlink this file into the
# SwiftBar plugin folder. Filename `.5m.sh` = refresh every 5 minutes.
#
#   ln -s ~/.claude/skills/zergguard-state/menubar.5m.sh \
#     ~/Library/Application\ Support/SwiftBar/Plugins/zergguard.5m.sh

# Find latest dashboard report
REPORT_DIR="/Users/mattheweisner/Obsidian/Zerg/MattZerg/Security"
LATEST=$(ls -t "$REPORT_DIR"/dashboard-*.md 2>/dev/null | head -1)

if [[ -z "$LATEST" ]]; then
  echo "🛡️ ?"
  echo "---"
  echo "No ZergGuard dashboard yet | refresh=true bash='/usr/bin/python3' param1='/Users/mattheweisner/.claude/skills/zergguard-state/dashboard.py' terminal=false"
  exit 0
fi

# Extract score
SCORE=$(grep "Risk score" "$LATEST" | head -1 | sed -E 's/.*: ([0-9]+).*/\1/')
LABEL=$(grep "Risk score" "$LATEST" | head -1 | sed -E 's/.*\(([^)]+)\)/\1/')

# Color emoji by score
if [[ "$SCORE" -ge 90 ]]; then
  ICON="🛡️🟢"
elif [[ "$SCORE" -ge 75 ]]; then
  ICON="🛡️🟢"
elif [[ "$SCORE" -ge 60 ]]; then
  ICON="🛡️🟡"
elif [[ "$SCORE" -ge 40 ]]; then
  ICON="🛡️🟠"
else
  ICON="🛡️🔴"
fi

# Menubar line
echo "$ICON $SCORE"

# Dropdown
echo "---"
echo "ZergGuard posture: $SCORE/100 ($LABEL)"
echo "---"
echo "Open latest report | bash='/usr/bin/open' param1='$LATEST' terminal=false"
echo "Run full audit now | refresh=true bash='/usr/bin/python3' param1='/Users/mattheweisner/.claude/skills/zergguard-audit/audit.py' terminal=false"
echo "Run identity audit | refresh=true bash='/usr/bin/python3' param1='/Users/mattheweisner/.claude/skills/zergguard-identity/audit.py' terminal=false"
echo "Refresh dashboard | refresh=true bash='/usr/bin/python3' param1='/Users/mattheweisner/.claude/skills/zergguard-state/dashboard.py' terminal=false"
echo "---"
echo "Show all reports | bash='/usr/bin/open' param1='$REPORT_DIR' terminal=false"
