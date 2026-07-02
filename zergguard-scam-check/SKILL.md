---
name: zergguard-scam-check
description: Paste a suspicious text / email / URL / phone number / sender name, get a `SAFE / SUSPICIOUS / PHISH` verdict with plain-English reasoning. Phase 2 of ZergGuard. Heuristics — display-name spoofing ("Inc Apple" ≠ "Apple Inc."), urgency/fear keywords, refund-scam phrasing, suspicious URL signals (base64-in-URL, IP-instead-of-domain, lookalike domains, suspicious TLDs), known-bad domains from the IOC list. No daemon, no API needed for v1. Verbs — `check <text>` (auto-classifies text/url/phone), `check --url <url>`, `check --phone <number>`, `check --sender "Name <email>"`. Use this every time you see a message that feels off — before clicking, before replying, before forwarding.
---

# zergguard-scam-check

Paste anything that feels off. Get a verdict + reasons.

```bash
python3 ~/.claude/skills/zergguard-scam-check/check.py "Your iCloud has been locked. Click here: http://apple-secure.tk/verify"
python3 ~/.claude/skills/zergguard-scam-check/check.py --url "http://cvetochek75.com/loader.sh"
python3 ~/.claude/skills/zergguard-scam-check/check.py --phone "+1-555-INC-APPL"
python3 ~/.claude/skills/zergguard-scam-check/check.py --sender "Inc Apple <support@apple-billing.click>"
```

## Output

Three-line verdict:

```
VERDICT: PHISH
SCORE: 9/10
REASONS:
  - Display name "Inc Apple" is a spoof of "Apple Inc." (reversed word order)
  - URL uses suspicious TLD (.click) — abuse-heavy / cheap registration
  - Sender domain "apple-billing.click" is NOT an apple.com domain
  - Urgency keyword: "locked"
RECOMMENDED ACTION: Block sender. Do not click. Do not reply.
```

## When to use

- **Every time** a text/email feels off — before clicking, before replying.
- Forward-to-self check: if anyone in your family forwards you a "is this real?" message, paste it here.
- Cold-email triage — was this real outreach or scam?
- Suspicious phone calls — paste the number that called.

## Heuristics in v1 (no API key needed)

- **Display-name spoofing**: word-order swaps ("Inc Apple"), Unicode lookalikes (Аpple), brand names paired with non-brand domains.
- **Urgency / fear language**: "locked", "verify immediately", "within 24 hours", "your account will be suspended", "unauthorized charge", "click here now".
- **Refund-scam pattern**: "you have been charged $X", "to dispute", "to cancel call".
- **URL signals**: known-bad domains (IOC list); suspicious TLDs (`.tk .gq .cf .ml .click .top .xyz .online .support`); IP address instead of domain; base64 in URL; lookalike domains (apple-secure.com vs apple.com); deep redirects.
- **Phone signals**: VoIP-style numbers, sequential digits, unusual country codes.
- **Spoofed sender**: e.g. display "Apple Support" but the email domain isn't apple.com.

## v2 (deferred)

- Google Safe Browsing API integration (free, requires API key).
- whois lookup for domain age.
- Auto-scan unknown-sender iMessages via `imessage-skill` integration.

## Read-only

Pure analysis. Never reports the message to anyone. Never visits URLs (only parses them).
