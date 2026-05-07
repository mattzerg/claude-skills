---
name: send-gate
description: Lightweight pre-flight check before sending an email via gmail-skill. Soft-warns on AI-template anti-patterns, missing voice tells, or wrong-register-for-recipient. Deliberately MUCH lighter than pr-gate — emails are varied + low-stakes, friction would just stop Matt from sending. USE PROACTIVELY before any outbound email send via gmail-skill (NOT before draft creation — draft is the right time for fakematt-email/personal review). Never blocks unless `--strict`. Wraps `gmail-skill send`.
allowed-tools: Bash, Read
---

# Send Gate

Lightweight wrapper around `gmail-skill send`. Catches the few catastrophic email mistakes (AI-template anti-patterns, register mismatch with a Tier A recipient) without adding ceremony to every send.

**Per `feedback_gate_thresholds.md`:** this gate is intentionally MUCH lighter than `pr-gate`. PRs flow to one reviewer (Idan) and need bundling. Emails go to varied recipients with no single bar; friction here would just stop Matt from sending entirely.

## When to invoke

- About to send an email via gmail-skill `send` (not `draft`)
- Especially before sending to Tier A contacts (formal-warm — accountants, fund partners, hiring managers)

## When NOT to invoke

- Draft creation — that's already covered by `fakematt-email` / `fakematt-personal` skills
- Internal Slack DMs — not an email surface
- Emails Matt is replying to within Gmail UI directly (we can't intercept those)

## Default invocation

```bash
python3 ~/.claude/skills/send-gate/run.py [gmail-skill-send-args...] [gate-flags...]

# gate-flags:
#   --strict       hard-block on warnings (default: soft-warn + send)
#   --dry-run      run gate, print findings, do NOT send
#   --skip-gate    bypass entirely (logged)
```

## Workflow

1. Parse `--to` + `--body` from passed args
2. Look up recipient register via `~/.claude/skills/fakematt-email/tier_map.json`
3. Run regex-based AI-template scan on `--body`:
   - "I hope this email finds you well" → soft-warn (use "Hope all is well!")
   - "Please don't hesitate to reach out" → soft-warn (use "Let me know if...")
   - "Sincerely," / "Regards," / "Kind regards," → soft-warn (use "Best,")
   - All-caps for emphasis → soft-warn (use *italics*)
   - `Co-Authored-By: Claude` / `Generated with Claude Code` → silent scrub (never appears in outbound email)
4. Register-mismatch check:
   - Tier A recipient + "Hey" greeting → soft-warn (Register A uses "Hi")
   - Tier C recipient + "Best, Matthew" closer → soft-warn (Register C drops or uses "Matt")
   - EXCLUDED recipient (family) + professional voice → soft-warn (route through fakematt-personal)
5. **Soft-warn behavior**: print findings, ask y/N to send anyway (default Y in non-interactive mode — `--strict` flips this)
6. **Hard-block triggers** (only with `--strict`): any soft-warn becomes a block
7. Pass through to `gmail-skill send` on approval; log to `logs/sends.log`

## Hard rules

- **Default is permissive.** Sends through with warnings unless `--strict`.
- **Never modifies the body** except to strip AI-coauthor lines (silent scrub).
- **No volume cap** — emails are not PRs.
- **No CI/Action mirror** — gmail-skill is local-only.
- **Logs every send** but doesn't surface them in standup (would be noise).

## See also

- `feedback_gate_thresholds.md` — why this gate is lighter than pr-gate
- `feedback_email_reply_voice.md` — Matt's reply voice patterns
- `MattZerg/_style/voice_universals.md` — anti-patterns this scans for
