---
name: harness-audit
description: Read-only security self-audit of Matt's own Claude Code config surface (~/.claude). Scans settings.json, hooks, agents, skills, and MCP config for leaked secrets, over-broad permission rules, dangerous shell in automation (curl|sh, rm -rf, force-push), and MCP injection surface — then writes a severity-ranked report. Pure standard library, no network, nothing reads tokens or phones home. The Matt-native rebuild of ECC's "AgentShield" idea. USE PROACTIVELY before sharing/syncing dotfiles, after adding or editing a hook/MCP server/agent, or as a monthly hygiene pass. Pairs with skill-scout (audits the outside world) and silo-scan (vault silos) — this audits the inside config.
---

# harness-audit

**Purpose.** Matt's `~/.claude` is a large, bespoke attack surface — a 9KB `settings.json` with 10 hook events, ~25 hook scripts, 15 orchestrator agents, 170+ skills, and multiple MCP servers. A hardcoded token in a hook, an over-broad `Bash(*)` allow rule, or a `curl … | sh` in automation would all be easy to miss by eye. `harness-audit` is the read-only scanner that catches them.

It is the Matt-native rebuild of the idea behind ECC's `AgentShield` (`everything-claude-code`): same goal, but **no third-party code runs** — nothing reads your credentials or makes network calls. (Decision: 2026-06-07, see `MattZerg/Skills/setup-ideas-evaluation-2026-06.md`.)

## Usage

```bash
python3 ~/.claude/skills/harness-audit/scan.py            # human summary + writes report
python3 ~/.claude/skills/harness-audit/scan.py --json     # machine-readable findings
python3 ~/.claude/skills/harness-audit/scan.py --quiet    # just write the report
python3 ~/.claude/skills/harness-audit/scan.py --root DIR # scan a different config root
```

Every run writes `~/.claude/logs/harness-audit-YYYYMMDD.md` (severity-ranked) and prints a summary. Exit code is always 0 — this informs, it never blocks.

**Scheduled:** `monthly_audit.py` runs via crontab on the 1st of each month (6am), scans **both** `~/.claude` and `~/.codex`, writes a combined report, and DMs Matt via Fake Matt → Slack **only if HIGH findings appear**. Run it by hand anytime: `python3 ~/.claude/skills/harness-audit/monthly_audit.py`.

## What it checks

| Category | Severity | Looks for |
|---|---|---|
| `SECRET` | HIGH / MED | Provider tokens (OpenAI/Anthropic `sk-…`, GitHub `ghp_…`, Slack `xox…`, AWS `AKIA…`, Google `AIza…`, Stripe `sk_live_…`, private-key blocks, `user:pass@` URLs) = HIGH; generic `api_key="…"`-style assignments = MED. Placeholder/env-ref lines (`${…}`, `os.environ`, `your-…`, `example`) are skipped. |
| `PERMISSION` | MED | `skipDangerousModePermissionPrompt` / `skipAutoPermissionPrompt` = true; `permissions.allow` rules with bare wildcards like `Bash(*)`. |
| `HOOK_DANGER` | HIGH / MED / LOW | In hooks + skill scripts: remote pipe-to-shell (`curl…\|sh`) = HIGH; `rm -rf`, `git push --force` = MED; `eval(`, `shell=True` = LOW. |
| `MCP` | MED / LOW | `~/.claude.json` MCP servers with inline tokens (MED) or plaintext `http://` non-localhost endpoints (LOW). |

## Scope & exclusions

Scans `~/.claude` text files only. Skips generated/transient/backup trees (`backups/`, `file-history/`, `session-env/`, `sessions/`, `logs/`, `__pycache__/`, `.venv/`, `node_modules/`, `*.bak`) and the `harness-audit/` dir itself (so its own regexes aren't flagged as secrets). Files over ~2MB are skipped.

## Triage guidance

- **HIGH SECRET** → real finding. Move the value to an env var / secret file and `chmod 600`; rotate the credential if it was committed or synced.
- **MED PERMISSION** → posture note, not a vuln. Matt intentionally runs some auto-approve flags; confirm each is deliberate.
- **MED/LOW HOOK_DANGER** → most are legitimate in Matt's own automation. Confirm the dangerous line is guarded (not reachable from untrusted input).
- **MCP** → confirm tokens come from env, not inline; prefer `https`/localhost endpoints.

## Anti-patterns

- Don't treat this as a blocker/gate — it's read-only and advisory by design.
- Don't scan the whole home dir; it's scoped to the config surface on purpose.
- Don't add network calls or auto-fix — keep it a pure, trustable read.
