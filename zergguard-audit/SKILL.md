---
name: zergguard-audit
description: One-shot personal-cybersec audit. Phase 0 of the ZergGuard tool. USE PROACTIVELY whenever Matt suspects a compromise, sees a phishing attempt, or it's been 30+ days since last audit. Scans Mac for compromise indicators across browser history, launchd (LaunchAgents/Daemons), running processes, recent app installs, browser extensions, network listeners, device hygiene (SIP/Gatekeeper/FileVault), and `~/.zsh_history` against an IOC list (curl-pipe-sh, base64-pipe-sh, etc.). Read-only — never auto-quarantines. Writes a severity-tagged report + DMs Fake Matt on any HIGH findings, with non-tech-savvy "what this means" + "what to do." Verbs — `run` (default), `--setup`, `--last`, `--dry-run`.
---

# zergguard-audit

Phase 0 of ZergGuard. One command, full audit.

```bash
python3 ~/.claude/skills/zergguard-audit/audit.py
python3 ~/.claude/skills/zergguard-audit/audit.py --dry-run
python3 ~/.claude/skills/zergguard-audit/audit.py --setup
```

## What it checks

1. **Browser history IOC scan** — Chrome/Safari/Brave for known-bad domains (built-in list seeded from real attacks).
2. **LaunchAgents/Daemons inventory** — all 3 system paths, sorted by mtime, flags anything created in the attack window from config.
3. **Login Items** — apps that launch at login (osascript).
4. **Running processes** — matched against IOC pattern list (loader, stealer, Atomic, Banshee, etc.).
5. **Recent /Applications/** — apps installed since attack-window floor.
6. **Browser extensions** — Chrome/Brave extension inventory.
7. **SSH state** — `~/.ssh/` contents, authorized_keys presence.
8. **Shell RC tampering** — sha256 of `.zshrc`, `.zshenv`, `.bash_profile`, `.profile`, `.bashrc`.
9. **Open network listeners** — `lsof` listening ports.
10. **Device hygiene** — SIP status, Gatekeeper status, FileVault status, macOS version vs latest.
11. **Zsh history red flags** — base64|sh, curl|sh, eval $(curl), suspicious TLDs.

## Output

Two surfaces:
- **Markdown report** at `<report_dir>/audit-YYYY-MM-DD.md` (configurable; defaults to vault `MattZerg/Security/`)
- **DM to Fake Matt** if any HIGH findings (configurable channel; macOS notification fallback for end-users)

Every finding has: severity (HIGH/MED/LOW/INFO), title, detail, evidence (specific paths/hashes/URLs), and **recommended action in plain English**.

## When to use

- IMMEDIATELY after any suspected phishing exposure (paste-into-terminal scam, fake security update prompt).
- Monthly hygiene check.
- Before high-stakes activity (transferring funds, signing contracts on the laptop).
- After installing anything you're not 100% sure about.

## Setup

First run: `audit.py --setup` walks through config — your email(s), output dir, notification preference. Edits `~/.config/zerg-guard/config.toml`. Skippable if you're fine with defaults.

## Read-only

Never quarantines. Never kills processes. Never deletes files. Always reports + recommends.

## Sibling pieces of ZergGuard

- `zergguard-scam-check` — paste text/email/URL → SAFE/SUSPICIOUS/PHISH verdict
- `zergguard-state` — weekly risk-dashboard summary
- `~/.config/zerg/security-monitor/audit.py` — daily agent-supply-chain monitor (separate concern, pre-existing)
