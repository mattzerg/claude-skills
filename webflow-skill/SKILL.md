---
name: webflow-skill
description: Manage Webflow sites + custom domains via the Webflow REST API. List sites, list/remove/add custom domains, find which site has a given domain bound, publish sites. Reads API token from macOS Keychain. Use whenever Matt mentions a Webflow site, needs to release a domain from Webflow (e.g., migrating to Cloudflare Pages), or wants to publish/republish. Pairs with cloudflare-skill + namecheap-skill for full domain-handoff workflows.
allowed-tools: Bash, Read
---

# Webflow Skill — Sites, Custom Domains, Publish

Webflow REST API for the operations Matt actually does: find which Webflow site a domain is bound to, release that binding (so a different host like Cloudflare Pages can serve it), publish.

## CRITICAL: Confirmation before destructive ops

For domain removals, site deletions, or unpublishes — these can take live sites offline:
1. Show what's currently bound (`list-domains <site>` or `find-domain <domain>`)
2. Show the proposed removal
3. Ask the user to confirm
4. Then run the destructive command

## First-time setup (~2 minutes)

### 1. Create API token at Webflow

Open https://webflow.com/dashboard/account/integrations or → your workspace → **Apps & Integrations** → **API Access** → **Generate API Token**.

- Name: e.g. `Matt CLI`
- Workspace scope: select the workspace containing your sites
- Permissions: at minimum **Sites: Read + Write**, **CMS: Read** (Read+Write CMS optional)

Copy the token (shown once, ~64 chars).

### 2. Save to macOS Keychain

```bash
security add-generic-password -s 'webflow-api-token' -a matteisn -w 'YOUR_TOKEN' -U
```

### 3. Verify

```bash
python3 ~/.claude/skills/webflow-skill/webflow_skill.py whoami
python3 ~/.claude/skills/webflow-skill/webflow_skill.py list-sites
```

## Commands

### Sites

```bash
# Auth check
python3 ~/.claude/skills/webflow-skill/webflow_skill.py whoami

# List all sites in your workspace
python3 ~/.claude/skills/webflow-skill/webflow_skill.py list-sites

# Get a site's details by short name (e.g. "matteisn") or site ID
python3 ~/.claude/skills/webflow-skill/webflow_skill.py get-site <site>
```

### Custom domains

```bash
# List custom domains bound to a site
python3 ~/.claude/skills/webflow-skill/webflow_skill.py list-domains <site>

# Find which site has a given domain bound (searches all sites)
python3 ~/.claude/skills/webflow-skill/webflow_skill.py find-domain <domain>
# e.g.:
python3 ~/.claude/skills/webflow-skill/webflow_skill.py find-domain matteisn.com

# Remove a custom domain from a site (releases Cloudflare/Webflow's edge binding)
python3 ~/.claude/skills/webflow-skill/webflow_skill.py remove-domain <site> <domain>

# Convenience: find + remove a domain from whichever site has it bound
python3 ~/.claude/skills/webflow-skill/webflow_skill.py unbind <domain>
# e.g. (the typical migration step):
python3 ~/.claude/skills/webflow-skill/webflow_skill.py unbind matteisn.com
```

### Publish

```bash
# Publish a site (push live changes)
python3 ~/.claude/skills/webflow-skill/webflow_skill.py publish <site>
```

## Migration workflow

Webflow + Cloudflare Pages are both on Cloudflare's edge. If you migrate DNS to Cloudflare but DON'T release the domain on Webflow's side, Webflow's pre-existing domain binding intercepts requests at the Cloudflare edge before they reach your Pages project.

**Standard handoff** (Webflow → Cloudflare Pages, no downtime):

1. `cloudflare-skill add-zone <domain>` — get Cloudflare nameservers
2. Add CNAME records at Cloudflare for `@` and `www` → `<project>.pages.dev` (proxied)
3. Preserve any TXT/MX records via `cloudflare-skill add-record`
4. `namecheap-skill set-nameservers <domain> chris.ns.cloudflare.com sasha.ns.cloudflare.com`
5. **`webflow-skill unbind <domain>`** ← this skill, releases Webflow's edge claim
6. Verify: `curl -sI https://<domain>` should show your Pages site, not Webflow's `x-wf-region` header

After all 3 are confirmed serving correctly, cancel the Webflow subscription.

## Endpoint

`https://api.webflow.com/v2` (REST, JSON). Authenticated via `Authorization: Bearer <token>`.

## Limitations

- Token is per-workspace. If you have multiple workspaces, generate one per workspace OR scope to the right one.
- Rate limit: 60 req/min standard, more on paid plans.
- Some paid features (memberships, ecommerce orders, etc.) require additional scope on the token.
