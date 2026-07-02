---
name: careful
description: |
  Safety guardrails for destructive shell commands. Warns + requires confirmation
  before `rm -rf`, `DROP TABLE`, `git push --force`, `git reset --hard`, `kubectl
  delete`, and similar destructive operations. Each warning is overrideable.
  USE PROACTIVELY whenever Matt says "be careful", "safety mode", "prod mode",
  or "careful mode", or is operating against production data, shared infra, or
  a live system. Pairs with `freeze` (scope edits to a single directory).
allowed-tools:
  - Bash
  - Read
---

## Skill Metadata (non-frontmatter)

The fields below were previously declared in YAML frontmatter under custom keys
(`version`, `triggers`, `hooks`). The Anthropic skill validator only accepts
`name | description | license | allowed-tools | metadata | compatibility`, so
they live here for human reference. Hook wiring belongs in `~/.claude/settings.json`
under `PreToolUse`; declaring it in SKILL.md frontmatter is not parsed by Claude
Code.

- version: 0.1.0
- triggers:
  - be careful
  - warn before destructive
  - safety mode

### Legacy hook declaration (not parsed — see settings.json)

```yaml
PreToolUse:
  - matcher: "Bash"
    hooks:
      - type: command
        command: "bash ${CLAUDE_SKILL_DIR}/bin/check-careful.sh"
        statusMessage: "Checking for destructive commands..."
```
---
<!-- AUTO-GENERATED from SKILL.md.tmpl — do not edit directly -->
<!-- Regenerate: bun run gen:skill-docs -->

# /careful — Destructive Command Guardrails

Safety mode is now **active**. Every bash command will be checked for destructive
patterns before running. If a destructive command is detected, you'll be warned
and can choose to proceed or cancel.

```bash
mkdir -p ~/.gstack/analytics
echo '{"skill":"careful","ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","repo":"'$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || echo "unknown")'"}'  >> ~/.gstack/analytics/skill-usage.jsonl 2>/dev/null || true
```

## What's protected

| Pattern | Example | Risk |
|---------|---------|------|
| `rm -rf` / `rm -r` / `rm --recursive` | `rm -rf /var/data` | Recursive delete |
| `DROP TABLE` / `DROP DATABASE` | `DROP TABLE users;` | Data loss |
| `TRUNCATE` | `TRUNCATE orders;` | Data loss |
| `git push --force` / `-f` | `git push -f origin main` | History rewrite |
| `git reset --hard` | `git reset --hard HEAD~3` | Uncommitted work loss |
| `git checkout .` / `git restore .` | `git checkout .` | Uncommitted work loss |
| `kubectl delete` | `kubectl delete pod` | Production impact |
| `docker rm -f` / `docker system prune` | `docker system prune -a` | Container/image loss |

## Safe exceptions

These patterns are allowed without warning:
- `rm -rf node_modules` / `.next` / `dist` / `__pycache__` / `.cache` / `build` / `.turbo` / `coverage`

## How it works

The hook reads the command from the tool input JSON, checks it against the
patterns above, and returns `permissionDecision: "ask"` with a warning message
if a match is found. You can always override the warning and proceed.

To deactivate, end the conversation or start a new one. Hooks are session-scoped.
