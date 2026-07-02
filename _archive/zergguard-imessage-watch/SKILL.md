---
name: zergguard-imessage-watch
description: "Continuous iMessage watcher. Polls `~/Library/Messages/chat.db` every 60s; for any NEW message from a sender Matt has never replied to, runs the message body through `zergguard-scam-check`. PHISH-scored messages fire an immediate macOS notification — \"ZergGuard: possible phishing from [sender].\" Steady state is silent. State-tracks last-seen ROWID at `~/.config/zerg-guard/imessage_watch.state`. The single biggest \"ZergGuard works for me without me thinking about it\" feature for non-technical users."
---

# zergguard-imessage-watch

Auto-scans incoming iMessages from unknown senders. You never have to remember to run scam-check — it runs itself.

## How it works

1. LaunchAgent `com.matteisner.zergguard-imessage-watch` runs `watch.py` continuously.
2. Polls `chat.db` every 60s for NEW messages (rowid > last_seen_rowid).
3. For each new inbound message from a sender that has NEVER received an outgoing message from Matt (= "unknown sender"), pipes the message body into `zergguard-scam-check`.
4. PHISH → macOS notification with sender + first line.
5. SUSPICIOUS → logged but not notified (to avoid alert fatigue).
6. SAFE → silent.

## State

`~/.config/zerg-guard/imessage_watch.state` stores the highest message ROWID processed. First run baselines; subsequent runs only process new messages.

## Tuning

- Poll frequency: 60s (in `watch.py` constant `POLL_SECS`).
- "Unknown sender" definition: handle has zero messages with `is_from_me=1`. Stricter would be "in last N days" — current setup is most cautious.
- Suppressed for senders containing keywords your bank / 2FA codes use (configurable in ioc.py if you find false positives).

## Why this matters

You got phished via SMS + call once (2026-05-01). The next time it happens you might miss it because you're busy or trusting. This daemon makes the check automatic.

## Disable

```bash
launchctl unload ~/Library/LaunchAgents/com.matteisner.zergguard-imessage-watch.plist
```
