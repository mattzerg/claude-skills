#!/usr/bin/env bash
# Monthly competitive-review refresh.
# Re-runs every category that has a folder under MattZerg/Competitive/, then writes a
# "what changed" summary note + posts a digest to Fake Matt self-DM.
#
# Triggered by crontab on the 1st of each month at 2 AM PT.
# Logs to ~/.claude/skills/competitive-review-skill/insights/monthly.log

set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/competitive-review-skill"
LOG="$SKILL_DIR/insights/monthly.log"
PY=/usr/bin/python3

mkdir -p "$SKILL_DIR/insights"

echo "[$(date -Iseconds)] monthly refresh starting" >> "$LOG"

# Re-run the full queue (config in run_queue.py). The skill itself handles archiving
# prior runs and computing diffs in each category's index.md.
"$PY" "$SKILL_DIR/run_queue.py" --no-wait >> "$LOG" 2>&1 || {
  echo "[$(date -Iseconds)] queue runner exited non-zero (continuing to summary)" >> "$LOG"
}

# Generate cross-category summary + post digest
"$PY" "$SKILL_DIR/monthly_summary.py" >> "$LOG" 2>&1 || {
  echo "[$(date -Iseconds)] monthly_summary exited non-zero" >> "$LOG"
}

echo "[$(date -Iseconds)] monthly refresh done" >> "$LOG"
