---
name: cloudflare-skill
description: Manage Cloudflare zones, DNS records, and Pages projects via the Cloudflare REST API. Adds zones, lists/creates/updates/deletes DNS records (A/AAAA/CNAME/MX/TXT), attaches custom domains to Pages projects, checks zone activation status. Reads credentials from macOS Keychain (Global API Key — works across all accounts the user owns). Use whenever Matt mentions adding a zone to Cloudflare, editing DNS in the Cloudflare dashboard, configuring a custom domain on a Pages project, or checking nameserver propagation.
allowed-tools: Bash, Read
---


# Cloudflare Skill — Zones, DNS, Pages

Cloudflare's REST API surface for the operations Matt actually does: add zones, set DNS records, hook up Pages custom domains. Pairs with `namecheap-skill` for the nameserver-handoff workflow (Namecheap registrar → Cloudflare DNS).

## CRITICAL: Confirmation before destructive ops

Adding/changing/deleting DNS records can break live traffic. For any non-list operation:
1. Show current state
2. Show proposed change
3. Ask user to confirm
4. Only then run

Especially: deleting zones, deleting records, changing apex (`@`) CNAME/A — these can take a domain offline.

## First-time setup (~2 minutes)

### 1. Get Global API Key

Open https://dash.cloudflare.com/profile/api-tokens

- Scroll past "API Tokens" section to **"API Keys"** section.
- On the row labeled **Global API Key**, click **View** (re-prompts password).
- Copy the 37–52 char key.

### 2. Save credentials to macOS Keychain

```bash
security add-generic-password -s 'cloudflare-email'      -a matteisn -w 'YOUR_CF_LOGIN_EMAIL' -U
security add-generic-password -s 'cloudflare-global-key' -a matteisn -w 'YOUR_GLOBAL_KEY' -U
```

### 3. Verify

```bash
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py whoami
```

## Commands

### Account / zones

```bash
# Show authenticated user + accounts
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py whoami

# List zones
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py list-zones

# Add a zone (returns Cloudflare nameservers to set at registrar)
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py add-zone <domain> [--account ACCOUNT_ID]

# Get zone details (including activation status)
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py get-zone <domain>

# Delete a zone
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py delete-zone <domain>
```

### DNS records

```bash
# List all DNS records on a zone
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py list-records <domain>

# Add a DNS record
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py add-record <domain> <type> <name> <value> [--proxied] [--ttl SECONDS]
# e.g.:
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py add-record matteisn.com CNAME @   matteisn.pages.dev --proxied
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py add-record matteisn.com CNAME www matteisn.pages.dev --proxied

# Update an existing record
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py update-record <domain> <record-id> [--type T] [--name N] [--value V] [--proxied] [--ttl S]

# Delete a record
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py delete-record <domain> <record-id>
```

### Cloudflare Pages

```bash
# List Pages projects
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py pages-list [--account ACCOUNT_ID]

# Attach a custom domain to a Pages project
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py pages-add-domain <project> <domain>

# List custom domains on a Pages project
python3 ~/.claude/skills/cloudflare-skill/cloudflare_skill.py pages-list-domains <project>
```

## Pairing

- **`namecheap-skill` → `cloudflare-skill`**: nameserver handoff workflow. Set custom NS at Namecheap pointing at Cloudflare, then manage all DNS at Cloudflare.
- **wrangler CLI**: complements this skill. Wrangler handles Pages deploys + Workers; this skill handles zones + DNS + Pages custom domains.

## Why API instead of dashboard

Cloudflare dashboard is fine but every time Claude needs to make a DNS change there's friction (login, navigate, click through forms). API calls are zero-touch once Keychain is set up.

## Endpoint

`https://api.cloudflare.com/client/v4` (JSON, REST). Authenticated via Global API Key (`X-Auth-Email` + `X-Auth-Key` headers).

## Limitations

- Global API Key has full account access; can't be scoped. For long-term shared access, switch to scoped API Tokens. For single-user workflows, Global API Key is fine.
- DNS changes propagate ~5 min – 24 hr. Use `dig` to verify propagation before declaring success.
