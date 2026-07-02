#!/usr/bin/env bash
# Install the aitr Friday tuning-report cron (launchd).
# Run:  bash ~/.claude/skills/aitr/install_cron.sh
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/aitr"
TEMPLATE="$SKILL_DIR/com.matteisn.aitr-tuning.plist.template"
TARGET="$HOME/Library/LaunchAgents/com.matteisn.aitr-tuning.plist"
LABEL="com.matteisn.aitr-tuning"

if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: template not found at $TEMPLATE" >&2
  exit 1
fi

mkdir -p "$HOME/.cache/zerg/aitr"
mkdir -p "$HOME/Library/LaunchAgents"

cp "$TEMPLATE" "$TARGET"
echo "copied → $TARGET"

# Unload first if a previous version is loaded (idempotent re-install).
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

# Modern macOS prefers bootstrap; fall back to legacy load.
if launchctl bootstrap "gui/$(id -u)" "$TARGET" 2>/dev/null; then
  echo "loaded via bootstrap"
elif launchctl load "$TARGET" 2>/dev/null; then
  echo "loaded via legacy load"
else
  echo "ERROR: launchctl could not load $TARGET" >&2
  echo "Diagnose with: launchctl bootstrap gui/$(id -u) $TARGET" >&2
  exit 1
fi

echo ""
echo "Verification:"
launchctl list | grep "$LABEL" || { echo "ERROR: job not listed after load" >&2; exit 1; }
echo ""
echo "OK — $LABEL will run Fridays 4:15 PM and post the tuning report to Fake Matt DM."
echo "Run it manually anytime:  python3 $SKILL_DIR/scripts/weekly_report.py --days 7"
