---
name: crm-bridge
description: Real-time polling daemon that connects the Investor CRM (epoch-pipeline-q1.fly.dev) to Claude Code — pulls incoming chat messages, auto-responds with codebase + vault context. Use when Matt asks to start, stop, or check the CRM bridge daemon; or to send a manual reply through it.
---

# CRM Bridge

Polling daemon. NOT an active conversational skill — it's launched by Matt explicitly when he wants the CRM to feed messages into a Claude session.

## Status

Dormant as of 2026-05-10. Target Fly app is alive (`epoch-pipeline-q1.fly.dev` returns 200 OK), but no bridge process is running. Last bridge.log activity: none (never recently used in this install).

## When to invoke

- Matt says "start the CRM bridge" / "turn on the investor CRM bridge"
- Matt asks for status (`--status`)
- Matt asks why investor-CRM messages aren't getting through

## How to invoke

```bash
# auto-respond mode (long-running)
python3 ~/.claude/skills/crm-bridge/crm_bridge.py --auto

# status check (one-shot)
python3 ~/.claude/skills/crm-bridge/crm_bridge.py --status
```

## What it does NOT do

- Does not auto-start on session boot
- Does not poll any Zerg CRM (Zerg uses Zergboard + Zergalytics, separate stack)
- Does not bridge personal CRM (`MattZerg/People/CRM/`)

## Related

- Pairs with the investor pipeline app at `epoch-pipeline-q1.fly.dev`
- Vang Capital infrastructure, not Zerg
- For Zerg CRM operations: `zergboard-skill`
- For personal contact lookup: `MattZerg/People/` via `gmail-skill` contact search
