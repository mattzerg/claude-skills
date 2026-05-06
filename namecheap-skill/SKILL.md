---
name: namecheap-skill
description: Manage Namecheap domains via the Namecheap public API. Set nameservers (e.g., switch to Cloudflare), set/get DNS host records (A/AAAA/CNAME/MX/TXT), list domains. Reads credentials from macOS Keychain (no plaintext config). Skips browser/UI entirely — all operations are HTTP API calls. Use whenever Matt mentions a Namecheap domain, nameserver change, or DNS edit on a Namecheap-registered domain.
allowed-tools: Bash, Read
---

# Namecheap Skill — Domain & DNS Management

Manage Namecheap domains via their public REST API. **No browser UI** — defeats the Cloudflare bot challenge that blocks Namecheap's web admin under Playwright.

## CRITICAL: Confirmation before destructive ops

For nameserver changes, host record sets, or domain transfers:
1. Show current state (`get-nameservers`, `get-records`)
2. Show proposed change
3. Ask the user to confirm
4. Only then run the destructive command

## First-time setup (~3 minutes)

### 1. Enable API access at Namecheap

Open https://ap.www.namecheap.com/profile/tools/apiaccess/

- Toggle **API Access** ON.
- ⚠️ Namecheap requires: $50 account balance OR ≥20 active domains OR ≥$50 spending in last year. If blocked, add $50 credit (applies to future renewals).
- Note the **API Key** shown (~32 chars).
- In **Whitelisted IPs**, add the public IP that will make API calls (find via `curl https://api.ipify.org`). All API requests must come from a whitelisted IP.

### 2. Save credentials to macOS Keychain

```bash
security add-generic-password -s 'namecheap-api-user'   -a matteisn -w 'YOUR_NAMECHEAP_USERNAME' -U
security add-generic-password -s 'namecheap-api-key'    -a matteisn -w 'YOUR_API_KEY' -U
security add-generic-password -s 'namecheap-api-ip'     -a matteisn -w 'YOUR_PUBLIC_IP' -U
```

The skill auto-loads these via `security find-generic-password ... -w`.

### 3. Verify

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py whoami
```

## Commands

### List domains

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py list-domains
```

### Get current nameservers

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py get-nameservers <domain>
# e.g.:
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py get-nameservers matteisn.com
```

### Set custom nameservers (e.g., switch to Cloudflare)

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py set-nameservers <domain> <ns1> <ns2> [<ns3> ...]
# e.g.:
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py set-nameservers matteisn.com chris.ns.cloudflare.com sasha.ns.cloudflare.com
```

### Reset to Namecheap default nameservers

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py set-default-nameservers <domain>
```

### Get host records

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py get-records <domain>
```

### Set host records (replaces ALL records for the domain)

`set-records` is a full replacement. To add one record without losing others, first `get-records`, build the new full list, then `set-records`.

```bash
python3 ~/.claude/skills/namecheap-skill/namecheap_skill.py set-records <domain> <records.json>
```

`records.json` shape:
```json
[
  {"type": "CNAME", "host": "www", "value": "matteisn.pages.dev", "ttl": 1800},
  {"type": "ALIAS", "host": "@", "value": "matteisn.pages.dev", "ttl": 1800}
]
```

## Pairing

- **Pair with `cloudflare-skill`**: when migrating a domain from Namecheap-managed DNS to Cloudflare-managed DNS:
  1. `cloudflare-skill add-zone <domain>` — get Cloudflare nameservers
  2. `namecheap-skill set-nameservers <domain> <ns1> <ns2>` — point at Cloudflare
  3. Wait 5 min – 1 hr for nameserver propagation
  4. `cloudflare-skill add-record <domain> ...` — manage DNS at Cloudflare from here on

## Why API instead of UI

Namecheap's web admin sits behind Cloudflare bot challenge. Playwright can't reliably auto-fill or auto-submit forms there — it forces repeated logins and breaks mid-edit. The public API has no such restriction. Setup is one-time (3 min); all future operations are zero-touch.

## Endpoint

`https://api.namecheap.com/xml.response` (XML response, parsed internally).

Sandbox: `https://api.sandbox.namecheap.com/xml.response` — NOT used by default; switch via `--sandbox` flag.

## Limitations

- API requires whitelisted IP. If Matt's home IP changes (most ISPs), the API stops working until he re-whitelists. Mitigation: use the skill from a server with a static IP, or set up auto-IP-update.
- Some Namecheap features aren't API-exposed (e.g., domain registration discounts, certain SSL operations).
