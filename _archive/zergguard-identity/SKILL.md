---
name: zergguard-identity
description: One-shot identity-exposure audit. Three checks — (1) browser saved-login inventory (Chrome + Brave; metadata only, NOT plaintext passwords); (2) HIBP breach lookup for configured emails (free k-anonymity for password-check; HIBP API key needed for email-breach lookup, gated); (3) 2FA enrollment audit (cross-references configured high-stakes-service list against browser saved-login URLs). Verbs — `python3 audit.py` (run full identity audit), `python3 audit.py --check-password "<password>"` (k-anonymity HIBP check for a single password; never sends plaintext), `python3 audit.py --setup-2fa-list` (open the list of services that should have 2FA so you can mark which you've enabled). Pairs with zergguard-state (rolled-up posture).
---

# zergguard-identity

Identity-exposure surface. What accounts you have, where they're saved, which need 2FA, which passwords are breached.

## Verbs

### `python3 audit.py`
Full audit: dumps saved-login inventory by browser + identifies any high-stakes services with no 2FA known + checks each configured email for HIBP breaches (if API key set).

### `python3 audit.py --check-password "<password>"`
K-anonymity password check. SHA1's the password locally; sends only the first 5 hex chars to HIBP; checks the returned hash list. Plaintext password NEVER leaves your machine. Returns "appears in N known breaches" or "not in any known breach."

### `python3 audit.py --setup-2fa-list`
Opens `~/.config/zerg-guard/2fa_status.toml` for editing. List of services with `enabled = true/false`. Audit cross-references against your browser-saved-login inventory.

## Output

Writes to vault `Security/identity-YYYY-MM-DD.md`. Findings include:
- HIGH: high-stakes service (bank, primary email, Apple ID) without 2FA confirmed
- HIGH: password you checked appears in breaches
- MED: low-stakes service without 2FA
- INFO: counts of saved logins per browser

## Privacy stance

- Never extracts saved password PLAINTEXT (would require Keychain unlock).
- Never sends full password hashes anywhere — only k-anonymity prefix (industry standard).
- Email breach lookup against haveibeenpwned.com requires their paid API key. Set `HIBP_API_KEY` env to enable.

## High-stakes service list (default)

Banks: chase, bofa, wellsfargo, citi, capitalone, americanexpress
Email: gmail, icloud, outlook, fastmail, proton
Apple: apple.com, icloud.com
Crypto: coinbase, kraken, binance, gemini, metamask
Dev: github, gitlab, npmjs, pypi
Hosting: aws.amazon, gcp.google, fly.io, vercel
Auth: 1password, bitwarden, lastpass

Customize in `~/.config/zerg-guard/2fa_status.toml`.
