---
name: frictionless-setup
description: Use when a task involves credentials, API keys, shell setup, environment variables, local launchers, or user copy/paste instructions; ensures the workflow is one-action, durable, validated, and recoverable instead of asking the user to manually run fragile command sequences.
metadata:
  short-description: Make setup flows one-action and durable
---

# Frictionless Setup

Use this skill whenever a user needs to provide secrets, run shell setup, configure environment variables, launch a local process, or perform repetitive mechanical steps.

## Required Default

Prefer a working launcher over instructions. The user should have one obvious action:
- double-click/open a `.command` file,
- press Return after copying a value,
- or paste one already-prepared command into a clearly opened terminal.

Do not ask the user to assemble commands, choose a terminal, infer where to paste, or repeat setup if a script can do it.

## Credential Handling

For API keys and secrets:
1. Open the provider page automatically when possible.
2. Tell the user exactly what to copy, in the launcher itself.
3. Before asking the user to paste or recreate a key, check whether the key is already recoverable from the current environment, clipboard, Keychain, or non-secret command state. Do not make the user repeat work until those paths are exhausted.
4. Prefer reading the copied secret from the clipboard after the user confirms it is copied.
5. Save secrets to macOS Keychain or another appropriate secure store.
6. Verify the saved secret can be read back before spending API calls.
7. Never echo the secret, log it, or include it in final output.
8. If an API call reaches the provider, treat the key as valid; diagnose billing/quota/model errors separately instead of asking for another key.
9. If a secret appears in chat, screenshots, terminal scrollback, or shell history, tell the user to revoke it and help clean local traces.

## OpenAI Key Helper

For OpenAI API work, use `/Users/mattheweisner/.codex/bin/openai-key-helper.zsh` before asking the user for a key.

Required pattern:
1. Check availability: `.../openai-key-helper.zsh exists`.
2. If missing and the clipboard has a key, store it with `.../openai-key-helper.zsh store-clipboard`.
3. For API commands, set `OPENAI_API_KEY="$(.../openai-key-helper.zsh read)"` in the command environment.
4. Do not proceed to paid calls unless `exists` passes.
5. Do not ask the user for another key until env, helper storage, Keychain, and clipboard have all been checked.

## Launcher Rules

When creating a macOS setup flow:
- Create a `.command` file with `#!/bin/zsh` and `chmod +x`.
- Launch it with `open /absolute/path/to/file.command`, not by asking the user to paste the path into a shell.
- The launcher must log non-secret errors to a known file.
- The launcher must keep the terminal window open on failure.
- The launcher must validate prerequisites before doing paid or destructive work.
- If using pipes, preserve the real command exit status.

## Avoid

- Do not hand the user a multi-command block unless explicitly requested.
- Do not rely on ephemeral `export SECRET=...` for keys the user may need again.
- Do not assume a browser page showing an old key can reveal the secret again.
- Do not ask the user to paste a raw secret into a normal shell prompt.
