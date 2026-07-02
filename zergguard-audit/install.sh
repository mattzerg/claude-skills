#!/usr/bin/env bash
# ZergGuard installer — wires up all skills + LaunchAgents on a fresh Mac.
# Works for Matt (vault paths) AND end-users (Documents paths).

set -euo pipefail

REPO_ROOT="${ZERGGUARD_REPO:-$HOME/.claude/skills}"
CONFIG_DIR="$HOME/.config/zerg-guard"

echo "ZergGuard installer"
echo "==================="
echo

# 1) Create config dir
mkdir -p "$CONFIG_DIR/lib"
echo "✓ created $CONFIG_DIR"

# 2) Run setup wizard if no config
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
  echo
  echo "→ running setup wizard"
  python3 "$REPO_ROOT/zergguard-audit/setup.py"
fi

# 3) Threat intel first pull
echo
echo "→ pulling threat intel (URLhaus + OpenPhish)"
python3 "$CONFIG_DIR/lib/threat_intel.py" || echo "  (threat intel pull failed — non-fatal)"

# 4) First audit
echo
echo "→ running first audit"
python3 "$REPO_ROOT/zergguard-audit/audit.py"

# 5) Baseline daily monitor
echo
echo "→ baselining daily monitor"
python3 "$CONFIG_DIR/lib/daily_monitor.py" --baseline

# 6) Identity audit
echo
echo "→ running identity audit"
python3 "$REPO_ROOT/zergguard-identity/audit.py"

# 7) iMessage watch baseline
echo
echo "→ baselining iMessage watch"
python3 "$REPO_ROOT/zergguard-imessage-watch/watch.py" --baseline

# 8) Load LaunchAgents
echo
echo "→ loading LaunchAgents"
for plist in "$HOME"/Library/LaunchAgents/com.matteisner.zergguard-*.plist; do
  if [[ -f "$plist" ]]; then
    launchctl load "$plist" 2>/dev/null || true
    echo "   ✓ $(basename "$plist")"
  fi
done

echo
echo "✅ ZergGuard installed."
echo "   Latest audit: $(ls -t "$HOME"/Documents/ZergGuard/audit-*.md 2>/dev/null | head -1 || echo "see report_dir from config")"
echo "   Run: python3 $REPO_ROOT/zergguard-state/dashboard.py    # weekly posture summary"
