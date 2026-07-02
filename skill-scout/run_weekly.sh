#!/bin/zsh
set -euo pipefail

export HOME="/Users/mattheweisner"
export PATH="/Users/mattheweisner/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCOUT="/Users/mattheweisner/.claude/skills/skill-scout/scout.py"
LOG_DIR="/Users/mattheweisner/.claude/skills/skill-scout/logs"
PY="/usr/bin/python3"
TS="$(date '+%Y-%m-%d %H:%M:%S %Z')"

mkdir -p "$LOG_DIR"
{
  echo "## skill-scout weekly run - $TS"
  "$PY" "$SCOUT" ingest-gmail-links --days 14 --max-results 25
  "$PY" "$SCOUT" poll --post --vault
  echo
} >> "$LOG_DIR/weekly.log" 2>> "$LOG_DIR/weekly.err"
