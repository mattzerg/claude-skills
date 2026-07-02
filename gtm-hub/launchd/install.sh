#!/usr/bin/env bash
# Install gtm-hub LaunchAgents (FDA-bearing) and retire the crontab entries.
#
# MUST be run from Matt's Terminal (not via cron, not via launchctl) so that
# the LaunchAgents inherit Full Disk Access from the interactive shell.
# See project_vault_mirror.md + feedback_launchd_tcc_sidestep.md.
#
# What this does:
#   1. Copies the three .plist files into ~/Library/LaunchAgents/
#   2. Runs `launchctl bootstrap` on each — they start running immediately
#   3. Comments out the matching crontab entries (with timestamp)
#   4. Verifies all three are loaded
#
# Re-runnable: kicks existing agents and reloads the plists.

set -euo pipefail

PLIST_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHAGENTS_DIR="${HOME}/Library/LaunchAgents"
TODAY="$(date +%Y-%m-%d)"

AGENTS=(
  "com.matteisn.gtm-hub-regenerate"
  "com.matteisn.gtm-hub-post"
  "com.matteisn.gtm-hub-slack-listener"
)

mkdir -p "${LAUNCHAGENTS_DIR}"

echo "→ Installing LaunchAgents from ${PLIST_SRC}"
for agent in "${AGENTS[@]}"; do
  src="${PLIST_SRC}/${agent}.plist"
  dst="${LAUNCHAGENTS_DIR}/${agent}.plist"
  if [[ ! -f "$src" ]]; then
    echo "  ! Missing source: $src" >&2
    exit 1
  fi
  cp "$src" "$dst"
  echo "  ✓ Copied → ${dst}"

  # Unload any prior instance (silently) so the new plist takes effect
  launchctl bootout "gui/$(id -u)/${agent}" 2>/dev/null || true

  # Bootstrap from interactive shell — confers FDA to the agent
  launchctl bootstrap "gui/$(id -u)" "$dst"
  echo "  ✓ Bootstrapped ${agent}"
done

echo
echo "→ Retiring matching crontab entries (commented out, not deleted)"
TMP="$(mktemp)"
crontab -l 2>/dev/null > "$TMP" || true
sed -i '' \
  -e "s|^\([^#].*gtm_hub_regenerate.py.*\)|# RETIRED ${TODAY} (moved to LaunchAgent): \1|" \
  -e "s|^\([^#].*gtm_hub_post.py.*\)|# RETIRED ${TODAY} (moved to LaunchAgent): \1|" \
  -e "s|^\([^#].*gtm_slack_listener.py.*\)|# RETIRED ${TODAY} (moved to LaunchAgent): \1|" \
  "$TMP"
crontab "$TMP"
rm "$TMP"
echo "  ✓ Crontab updated (old entries commented with RETIRED prefix)"

echo
echo "→ Verifying agents are loaded"
for agent in "${AGENTS[@]}"; do
  if launchctl list 2>/dev/null | grep -q "${agent}\$"; then
    echo "  ✓ ${agent} — loaded"
  else
    echo "  ✗ ${agent} — NOT loaded; check syslog" >&2
  fi
done

echo
cat <<EOF
═══════════════════════════════════════════════════════════════════
LaunchAgent install complete.

Schedules:
  com.matteisn.gtm-hub-regenerate       every 15 min
  com.matteisn.gtm-hub-post             Monday 7:15 AM PT
  com.matteisn.gtm-hub-slack-listener   every 5 min

Watch logs:
  tail -f ~/.claude/fakematt-today/gtm_hub.log
  tail -f ~/.claude/fakematt-today/gtm_slack.log

Trigger an immediate run (e.g. to test the listener):
  launchctl kickstart -k gui/\$(id -u)/com.matteisn.gtm-hub-slack-listener

Uninstall (one-shot):
  for a in ${AGENTS[*]}; do
    launchctl bootout gui/\$(id -u)/\$a
    rm ~/Library/LaunchAgents/\$a.plist
  done
═══════════════════════════════════════════════════════════════════
EOF
