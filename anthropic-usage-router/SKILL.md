---
name: anthropic-usage-router
description: Deprecated. Do not route Claude through Anthropic API keys. Use account-based Claude.ai OAuth routing via zclaude / claude_account_router instead, preferring Max and Team plans before any API key.
---

# Anthropic Usage Router

Deprecated. Do not use this skill to route Claude through `ANTHROPIC_API_KEY`.

Claude work should use account-based Claude.ai login through `zclaude` and `~/.config/zerg/claude_account_router.py`. Max and Team plans should always be preferred before API keys. The zergai.com Anthropic API-key route has been eliminated and should not be recreated.

## Required behavior: account login, NOT API

Per-token API billing is more expensive than Matt's Max/Team subscriptions. `zclaude` clears `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` and routes through saved Claude.ai OAuth accounts.

A second layer of protection — a `claude()` zsh function in `~/.zshrc` — also strips `ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL` for bare `claude` invocations that bypass `zclaude`. Matters when scripts or tab-completion call `claude` directly.

There is no normal opt-in API path for Claude Code. If account OAuth is broken or rate-limited, refresh/switch the saved Max/Team account instead of falling back to a zergai.com Anthropic API key.

## Quick start

```bash
~/.config/zerg/zclaude router-status
```

For machine-readable output:

```bash
~/.config/zerg/zclaude router-status --json
```

To return just the picked label:

```bash
~/.config/zerg/zclaude router-route
```

To switch/refresh a specific account, use the account-login stash commands:

```bash
~/.config/zerg/zclaude max-use <label>
~/.config/zerg/zclaude max-refresh <label>
```

The CLI surface for daily use is the `zclaude` wrapper at `~/.config/zerg/zclaude`.

## Workflow

1. Run `~/.config/zerg/zclaude router-status` whenever Matt asks "why was I throttled" or "which account am I on" or "what's my headroom?".
2. Prefer valid Max/Team OAuth stashes.
3. If an account is invalid, refresh or re-login that account.
4. Do not use `ANTHROPIC_API_KEY` as a fallback.

## Surfaces and how rotation flows through them

| Surface | How rotation happens |
|---|---|
| Surface | Behavior |
|---|---|
| `zclaude` / `claude` | Clears `ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL`; routes through saved Claude.ai OAuth accounts. |
| `zX` zsh aliases (`zboard`, `zwallet`, ...) | Call `zclaude`; inherit account-login routing. |
| SDK callers | Should use account-login workflows where available. Do not revive the zergai.com API-key router. |

## Account labels

Account labels live in `~/.config/anthropic-router/max-creds/` and are managed by `zclaude max-*` commands.

## Safety

- `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` are cleared by `zclaude`.
- `ANTHROPIC_API_KEY` and key-shaped strings are excluded from shell history via the `HISTORY_IGNORE` rule in `~/.zshrc`.
- Do not add Keychain entries or files for zergai.com Anthropic API keys.

## Periodic checks

Skills do not run background jobs by themselves. Account-login state is checked through `zclaude router-status`.

## Disable

No API-key router should be enabled. If you find an `accounts.json` for API keys, disable it rather than using it.

## When to invoke this skill

- "Why am I throttled?" → run `~/.config/zerg/zclaude router-status`, identify which account/window is limiting.
- "Switch me to my Zerg account" → use `~/.config/zerg/zclaude max-use matthew-zergai` only for the saved account-login stash.
- "Are all keys live?" → answer that Claude should not use Anthropic API keys; check OAuth stashes instead.
- "Is rotation working?" → test `claude -p` through `zclaude` and verify `ANTHROPIC_API_KEY` is not present.
