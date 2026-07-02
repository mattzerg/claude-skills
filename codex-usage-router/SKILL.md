---
name: codex-usage-router
description: Check local Codex usage/rate-limit state across authenticated or previously observed accounts, recommend the account with lower usage, and switch accounts efficiently when a configured switch command is available. Use when the user asks to check Codex usage, avoid rate limits, rotate between OpenAI/Codex accounts, or choose which Codex account to use next.
---


# Codex Usage Router

Use this skill to route Codex work to the account with the most remaining capacity. It reads local Codex session logs for recent `rate_limits` events and avoids exposing auth tokens.

## Quick Start

Run:

```bash
python3 ~/.codex/skills/codex-usage-router/scripts/codex_usage_router.py status
```

For machine-readable output:

```bash
python3 ~/.codex/skills/codex-usage-router/scripts/codex_usage_router.py status --json
```

To try switching after a switch command is configured:

```bash
python3 ~/.codex/skills/codex-usage-router/scripts/codex_usage_router.py switch
```

## Workflow

1. Run `status` before long Codex work, after rate-limit warnings, or when the user asks which account to use.
2. Prefer the account with the lowest primary `used_percent`; break ties by lower secondary `used_percent`.
3. If the current account is already best, keep it.
4. If another account is better and a switch command is configured, run `switch`.
5. If no switch command is configured, report the recommended account and ask the user to log in or add a switch command.

## Account Labels

Codex logs expose `account_id`, not always email. Maintain labels in:

`~/.codex/account-router/accounts.json`

Example:

```json
{
  "accounts": {
    "6770e39d-e3f8-47c9-8e54-af5e8978640e": {
      "label": "matteisn@gmail.com",
      "switch_command": "codex login --device-auth"
    }
  }
}
```

`switch_command` is optional. Use it only for commands you are comfortable running to activate that account. Do not store auth tokens in this file.

## Safety

- Never print `~/.codex/auth.json` raw.
- Never copy refresh/access/id tokens between account files.
- Archive old auth snapshots only if the user explicitly asks.
- If account identity is ambiguous, refer to `account_id` plus the current auth file's `last_refresh`.
- Treat switching as session-affecting: tell the user which account is recommended and what command will run before making changes.

## Periodic Checks

Codex skills do not run background jobs by themselves. For periodic checks, create a cron/launchd job that runs:

```bash
python3 ~/.codex/skills/codex-usage-router/scripts/codex_usage_router.py status --json
```

Only automate `switch` after the account map is verified.
