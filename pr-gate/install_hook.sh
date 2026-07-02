#!/bin/bash
# Install pr-gate as a local pre-push hook in a git repo.
#
# Usage:
#   ~/.claude/skills/pr-gate/install_hook.sh <repo-path>
#   ~/.claude/skills/pr-gate/install_hook.sh --all
#
# Idempotent: re-running overwrites with the latest content.
# To uninstall hook: rm <repo>/.git/hooks/pre-push
#
# This installer intentionally does not write GitHub Actions or tracked repo
# metadata. PR Gate is Matt-local workflow hygiene, not repo CI/CD.

set -e

KNOWN_REPOS=(
    "$HOME/zerg"
    "$HOME/zerg/zergwallet"
    "$HOME/.claude/skills"
)

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
# Optional repo config:
#   git config pr-gate.identity matt-personal  # passes --matt-personal
#   git config pr-gate.identity matt-led       # passes --matt-led
#   git config pr-gate.identity ai-led         # passes --ai-led
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
        # Backup / archival pushes are NOT pull requests — they just preserve local
        # state off-machine. They must not require an Idan-reviewed PR / stale-base
        # rebase. Real feature branches (anything else) still go through pr-gate.
        refs/heads/backup/*|refs/heads/archive/*|refs/heads/*graveyard*|refs/heads/*-backup)
            echo "[pre-push] $remote_ref is a backup/archival branch — skipping pr-gate"
            continue ;;
    esac
    gate_needed=1
    gate_branch="$remote_ref"
done

if [ "$gate_needed" -eq 0 ]; then exit 0; fi

echo "[pre-push] running pr-gate on $gate_branch …"
echo "[pre-push] (skip with: git push --no-verify)"
echo

identity=$(git config --get pr-gate.identity || true)
identity_flag=""
case "$identity" in
    matt-personal) identity_flag="--matt-personal" ;;
    matt-led) identity_flag="--matt-led" ;;
    ai-led) identity_flag="--ai-led" ;;
    "") ;;
    *)
        echo "[pre-push] invalid pr-gate.identity=$identity"
        echo "[pre-push] expected one of: matt-personal, matt-led, ai-led"
        exit 2
        ;;
esac

PYTHON_BIN="$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3 || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "[pre-push] python3 not found in PATH"
    exit 2
fi

if "$PYTHON_BIN" "$PR_GATE" --dry-run --fast --no-prior-review $identity_flag; then
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
    mkdir -p "$repo/.git/info"
    touch "$repo/.git/info/exclude"
    for pattern in ".pr-gate-review.md" ".pr-gate-review-full.md" ".pr-gate-asset-previews.md"; do
        if ! grep -qxF "$pattern" "$repo/.git/info/exclude"; then
            printf '%s\n' "$pattern" >> "$repo/.git/info/exclude"
            echo "  [ok]   local exclude += $pattern"
        fi
    done
}

TARGETS=()

for arg in "$@"; do
    case "$arg" in
        --action)
            echo "error: --action was removed. PR Gate is local-only; do not install repo CI/CD for Matt-only workflow rules." >&2
            exit 2
            ;;
        --all) TARGETS=("${KNOWN_REPOS[@]}") ;;
        --help) echo "Usage: $0 [<repo-path>] [--all]"; exit 0 ;;
        *) TARGETS+=("$arg") ;;
    esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "Usage: $0 [<repo-path>] [--all]"
    exit 2
fi

echo "Installing local pre-push hook in ${#TARGETS[@]} repo(s):"
for repo in "${TARGETS[@]}"; do
    echo "[$repo]"
    write_hook "$repo"
done
