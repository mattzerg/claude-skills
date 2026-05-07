#!/bin/bash
# setup_ci.sh — set ANTHROPIC_API_KEY as a repo secret for each known Zerg repo.
#
# Loads the key via ~/.config/zerg/load_anthropic_key.sh (Keychain), then runs
# `gh secret set ANTHROPIC_API_KEY --repo <repo>` for each repo with a GitHub origin.
#
# Idempotent: re-running just overwrites the secret with the current value.
#
# Usage:
#   ~/.claude/skills/pr-gate/setup_ci.sh             # all known repos
#   ~/.claude/skills/pr-gate/setup_ci.sh <repo-path> # one repo
#   ~/.claude/skills/pr-gate/setup_ci.sh --check     # list repos + secret state, don't change anything

# Don't `set -e` — each helper does its own error handling and we want to
# continue past per-repo failures (no-origin, gh-auth-issues, etc.) so one
# bad repo doesn't kill the whole batch.

KNOWN_REPOS=(
    "$HOME/zerg"
    "$HOME/zerg/zergwallet"
    "$HOME/.claude/skills"
)

KEY_LOADER="$HOME/.config/zerg/load_anthropic_key.sh"

load_key() {
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        return 0
    fi
    if [ -f "$KEY_LOADER" ]; then
        # shellcheck disable=SC1090
        source "$KEY_LOADER"
    fi
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "error: ANTHROPIC_API_KEY not in env and $KEY_LOADER did not provide one"
        echo "       Make sure the Keychain entry exists, or `export ANTHROPIC_API_KEY=...` first"
        return 1
    fi
}

repo_origin() {
    local local_path="$1"
    git -C "$local_path" remote get-url origin 2>/dev/null
}

origin_to_nwo() {
    # Convert any of these to "owner/repo":
    #   git@github.com:owner/repo.git
    #   https://github.com/owner/repo.git
    #   https://github.com/owner/repo
    local url="$1"
    # strip protocol
    url="${url#git@github.com:}"
    url="${url#https://github.com/}"
    url="${url#http://github.com/}"
    # strip trailing .git
    url="${url%.git}"
    echo "$url"
}

check_one() {
    local local_path="$1"
    if [ ! -d "$local_path/.git" ]; then
        echo "  [skip] $local_path (not a git repo)"
        return
    fi
    local origin
    origin=$(repo_origin "$local_path")
    if [ -z "$origin" ]; then
        echo "  [skip] $local_path (no origin remote — local-only repo)"
        return
    fi
    if [[ "$origin" != *github.com* ]]; then
        echo "  [skip] $local_path (origin not on github.com: $origin)"
        return
    fi
    local nwo
    nwo=$(origin_to_nwo "$origin")
    local present
    present=$(gh secret list --repo "$nwo" 2>/dev/null | grep -c "^ANTHROPIC_API_KEY" || true)
    if [ "$present" -gt 0 ]; then
        echo "  [present] $nwo  (ANTHROPIC_API_KEY already set)"
    else
        echo "  [missing] $nwo  (will set on apply)"
    fi
}

apply_one() {
    local local_path="$1"
    if [ ! -d "$local_path/.git" ]; then
        echo "  [skip] $local_path (not a git repo)"
        return
    fi
    local origin
    origin=$(repo_origin "$local_path")
    if [ -z "$origin" ]; then
        echo "  [skip] $local_path (no origin remote)"
        return
    fi
    if [[ "$origin" != *github.com* ]]; then
        echo "  [skip] $local_path (origin not on github.com)"
        return
    fi
    local nwo
    nwo=$(origin_to_nwo "$origin")
    if printf '%s' "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY --repo "$nwo" --body - > /dev/null 2>&1; then
        echo "  [ok] $nwo  (ANTHROPIC_API_KEY set)"
    else
        echo "  [fail] $nwo  (gh secret set returned nonzero — check 'gh auth status')"
    fi
}

# Parse args
MODE="apply"
TARGETS=()
for arg in "$@"; do
    case "$arg" in
        --check) MODE="check" ;;
        --help) echo "Usage: $0 [--check] [<repo-path>]"; exit 0 ;;
        *) TARGETS+=("$arg") ;;
    esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    TARGETS=("${KNOWN_REPOS[@]}")
fi

if [ "$MODE" = "apply" ]; then
    if ! load_key; then exit 1; fi
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "error: gh CLI not on PATH"
    exit 2
fi

if [ "$MODE" = "check" ]; then
    echo "Checking ANTHROPIC_API_KEY across ${#TARGETS[@]} repo(s):"
    for r in "${TARGETS[@]}"; do
        check_one "$r"
    done
else
    echo "Setting ANTHROPIC_API_KEY across ${#TARGETS[@]} repo(s):"
    for r in "${TARGETS[@]}"; do
        apply_one "$r"
    done
fi
