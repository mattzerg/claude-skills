#!/bin/bash
# install_launchagents.sh — load all decision-queue + Phase 1/2 LaunchAgents.
#
# Phase 1 auto-mode classifier declined to load these autonomously. Run this
# once after the Phase 1+2 build to wire daily ingestion.
#
# Idempotent: unloads first, then loads. Reports per-agent.

set -u

AGENTS=(
    com.zerg.decision-queue-regen      # 15min aggregate.py
    com.zerg.decision-queue-serve      # Flask server, KeepAlive
    com.zerg.pr-comment-miner          # daily 6:15
    com.zerg.slack-dm-miner            # daily 6:20
    com.zerg.codex-claude-drift        # weekly Mon 7:00
    com.zerg.mining-to-composite       # weekly Mon 7:30
    com.zerg.feedback-inbox-router     # daily 6:25 (Phase 2 Q1.1)
)

LA_DIR="$HOME/Library/LaunchAgents"
echo "Loading ${#AGENTS[@]} LaunchAgents from $LA_DIR ..."
echo

for label in "${AGENTS[@]}"; do
    plist="$LA_DIR/$label.plist"
    if [ ! -f "$plist" ]; then
        printf "  SKIP   %s  (plist missing)\n" "$label"
        continue
    fi
    launchctl unload "$plist" 2>/dev/null
    if launchctl load "$plist" 2>&1; then
        printf "  LOADED %s\n" "$label"
    else
        printf "  ERROR  %s\n" "$label"
    fi
done

echo
echo "Verifying with launchctl list:"
launchctl list | grep -E "^[^\t]+\s+(-|[0-9]+)\s+com\.zerg\." | head -20

echo
echo "Run zinflight --window 1440 to confirm all agents visible."
