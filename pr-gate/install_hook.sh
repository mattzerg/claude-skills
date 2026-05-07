#!/bin/bash
# Install pr-gate as a pre-push hook + GitHub Action in a git repo.
#
# Usage:
#   ~/.claude/skills/pr-gate/install_hook.sh <repo-path>             # local hook only
#   ~/.claude/skills/pr-gate/install_hook.sh --action <repo-path>    # local hook + .github action
#   ~/.claude/skills/pr-gate/install_hook.sh --all                   # local hook in all known repos
#   ~/.claude/skills/pr-gate/install_hook.sh --all --action          # local hook + actions in all
#
# Idempotent: re-running overwrites with the latest content.
# To uninstall hook: rm <repo>/.git/hooks/pre-push
# To uninstall action: rm <repo>/.github/workflows/pr-gate.yml

set -e

KNOWN_REPOS=(
    "$HOME/zerg"
    "$HOME/zerg/zergwallet"
    "$HOME/.claude/skills"
)

# The canonical Action source — copied from ~/zerg/.github/* (which is the source of truth).
ACTION_WORKFLOW_SRC="$HOME/zerg/.github/workflows/pr-gate.yml"
ACTION_SCRIPT_SRC="$HOME/zerg/.github/scripts/pr_gate_ci.py"

write_hook() {
    local repo="$1"
    if [ ! -d "$repo/.git" ]; then
        echo "  [skip] $repo (not a git repo)"
        return
    fi
    cat > "$repo/.git/hooks/pre-push" << 'HOOK_EOF'
#!/bin/bash
# pre-push hook — runs pr-gate before push to feature branches.
# Skips main/development/master pushes (those don't go through PR review).
# Override: git push --no-verify
# Source: ~/.claude/skills/pr-gate/install_hook.sh

set -e
PR_GATE="$HOME/.claude/skills/pr-gate/run.py"
ZERO_SHA="0000000000000000000000000000000000000000"

if [ ! -f "$PR_GATE" ]; then
    echo "[pre-push] pr-gate not found at $PR_GATE — skipping"
    exit 0
fi

gate_needed=0
gate_branch=""
while read local_ref local_sha remote_ref remote_sha; do
    if [ "$local_sha" = "$ZERO_SHA" ]; then continue; fi
    case "$remote_ref" in
        refs/heads/main|refs/heads/master|refs/heads/development|refs/heads/develop)
            continue ;;
    esac
    gate_needed=1
    gate_branch="$remote_ref"
done

if [ "$gate_needed" -eq 0 ]; then exit 0; fi

echo "[pre-push] running pr-gate on $gate_branch …"
echo "[pre-push] (skip with: git push --no-verify)"
echo

if /usr/bin/python3 "$PR_GATE" --dry-run; then
    echo
    echo "[pre-push] gate passed — push proceeding."
    exit 0
else
    rc=$?
    echo
    echo "[pre-push] gate BLOCKED push (exit $rc)"
    echo "[pre-push] See .pr-gate-review.md for findings."
    echo "[pre-push] Fix and re-push, or override with: git push --no-verify"
    exit $rc
fi
HOOK_EOF
    chmod +x "$repo/.git/hooks/pre-push"
    echo "  [ok]   hook → $repo/.git/hooks/pre-push"
}

write_action() {
    local repo="$1"
    if [ ! -d "$repo/.git" ]; then
        return
    fi
    if [ ! -f "$ACTION_WORKFLOW_SRC" ] || [ ! -f "$ACTION_SCRIPT_SRC" ]; then
        echo "  [skip] action not installed — source files missing at $ACTION_WORKFLOW_SRC"
        return
    fi
    mkdir -p "$repo/.github/workflows" "$repo/.github/scripts"
    cp "$ACTION_WORKFLOW_SRC" "$repo/.github/workflows/pr-gate.yml"
    cp "$ACTION_SCRIPT_SRC" "$repo/.github/scripts/pr_gate_ci.py"
    chmod +x "$repo/.github/scripts/pr_gate_ci.py"
    echo "  [ok]   action → $repo/.github/workflows/pr-gate.yml"
    echo "         (commit + add ANTHROPIC_API_KEY repo secret to enable)"
}

INSTALL_ACTION=0
TARGETS=()

for arg in "$@"; do
    case "$arg" in
        --action) INSTALL_ACTION=1 ;;
        --all) TARGETS=("${KNOWN_REPOS[@]}") ;;
        --help) echo "Usage: $0 [<repo-path>] [--action] [--all]"; exit 0 ;;
        *) TARGETS+=("$arg") ;;
    esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "Usage: $0 [<repo-path>] [--action] [--all]"
    exit 2
fi

echo "Installing pre-push hook${INSTALL_ACTION:+ + GitHub Action} in ${#TARGETS[@]} repo(s):"
for repo in "${TARGETS[@]}"; do
    echo "[$repo]"
    write_hook "$repo"
    if [ "$INSTALL_ACTION" -eq 1 ]; then
        # Don't write the action into the repo it's sourced from
        if [ "$repo" = "$HOME/zerg" ]; then
            echo "  [skip] action source repo — action already lives in $HOME/zerg/.github/"
        else
            write_action "$repo"
        fi
    fi
done
