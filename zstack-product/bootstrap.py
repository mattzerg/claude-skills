#!/usr/bin/env python3
"""Bootstrap a new Zstack microproduct.

Stamps out:
- Code repo at ~/zerg/<slug>/ — Nuxt 3 + TS + canonical layout
- Vault positioning note at MattZerg/Projects/Zerg-Development/<Product>/<Product>.md
- Competitive folder at MattZerg/Competitive/<category>/ (8-file shape)

Pre-wires:
- ZergAlytics tracker composable
- ZergSend upsert_contact call from signup
- lifecycle-email trigger stub

Usage:
    python3 bootstrap.py <slug> --category <category> [--port <N>] [--display-name <Name>]

Example:
    python3 bootstrap.py zcrm-test --category crm --display-name "ZergCRM"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

ZERG_ROOT = Path.home() / "zerg"
SKILL_DIR = Path(__file__).resolve().parent
VAULT_ROOT = (
    Path.home()
    / "Obsidian/Zerg/MattZerg"
)
PORT_REGISTRY = SKILL_DIR / "port-registry.md"


def display_default(slug: str) -> str:
    return slug[:1].upper() + slug[1:]


def reserved_ports() -> set[int]:
    text = PORT_REGISTRY.read_text(encoding="utf-8") if PORT_REGISTRY.is_file() else ""
    return {int(m) for m in re.findall(r"\b(3\d{3})\b", text)}


def assign_port(requested: Optional[int]) -> int:
    used = reserved_ports()
    if requested is not None:
        if requested in used:
            print(f"warn: port {requested} already in registry; reusing anyway")
        return requested
    for p in range(3003, 3100):
        if p not in used:
            return p
    raise RuntimeError("no free port in 3003-3099")


PACKAGE_JSON = """{{
  "name": "{slug}",
  "private": true,
  "type": "module",
  "scripts": {{
    "dev": "nuxt dev",
    "build": "nuxt build",
    "preview": "nuxt preview",
    "typecheck": "nuxt typecheck",
    "db:migrate": "node db/migrate.mjs"
  }},
  "dependencies": {{
    "@nuxtjs/tailwindcss": "^6.13.1",
    "bcryptjs": "^2.4.3",
    "nuxt": "^3.17.2",
    "postgres": "^3.4.5",
    "zod": "^3.23.8"
  }},
  "devDependencies": {{
    "@types/bcryptjs": "^2.4.6",
    "@types/node": "^25.3.0",
    "typescript": "^5.6.3",
    "vue-tsc": "^3.2.4"
  }}
}}
"""

NUXT_CONFIG = """export default defineNuxtConfig({{
  compatibilityDate: '2025-01-15',
  devtools: {{ enabled: true }},
  app: {{
    head: {{
      title: '{display}',
      link: [
        {{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }}
      ]
    }}
  }},
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],
  runtimeConfig: {{
    databaseUrl: process.env.DATABASE_URL,
    sessionSecret: process.env.SESSION_SECRET || 'dev-secret-change-me',
    zsendBaseUrl: process.env.ZSEND_BASE_URL || '',
    zsendIngestToken: process.env.ZSEND_INGEST_TOKEN || '',
    zsendWorkspaceId: process.env.ZSEND_WORKSPACE_ID || '',
    public: {{
      appName: '{display}',
      analyticsEndpoint: process.env.NUXT_PUBLIC_ANALYTICS_ENDPOINT || ''
    }}
  }},
  typescript: {{
    strict: true,
    typeCheck: true
  }}
}})
"""

TAILWIND_CSS = """@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --brand-cream: #f4f0e7;
  --brand-charcoal: #111514;
  --brand-orange: #b3662f;
  --brand-orange-aa: #8a4a1f;
  --brand-green: #6FBE31;
}

body {
  font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif;
  background: var(--brand-cream);
  color: var(--brand-charcoal);
}
"""

DOCKERFILE = """FROM node:22-alpine AS base
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm install

FROM deps AS build
COPY . .
RUN npm run build

FROM base AS prod-deps
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NITRO_HOST=0.0.0.0
COPY --from=build /app/.output ./.output
COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=prod-deps /app/package.json ./package.json
COPY db ./db
EXPOSE {port}
CMD ["node", ".output/server/index.mjs"]
"""

FLY_TOML = """app = "{slug}"
primary_region = "lax"

[build]
  dockerfile = "Dockerfile"

[env]
  NITRO_HOST = "0.0.0.0"
  NITRO_PORT = "{port}"

[http_service]
  internal_port = {port}
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

  [[http_service.checks]]
    grace_period = "15s"
    interval = "30s"
    method = "GET"
    timeout = "5s"
    path = "/api/health"
"""

DB_SCHEMA = """CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
"""

DB_MIGRATE = """import fs from 'node:fs/promises'
import postgres from 'postgres'

const databaseUrl = process.env.DATABASE_URL

if (!databaseUrl) {
  console.error('DATABASE_URL is required to run migrations')
  process.exit(1)
}

const sql = postgres(databaseUrl, { ssl: 'prefer' })

try {
  const schema = await fs.readFile(new URL('./schema.sql', import.meta.url), 'utf8')
  await sql.unsafe(schema)
  console.log('Migrations applied successfully')
} catch (error) {
  console.error('Migration failed')
  console.error(error)
  process.exit(1)
} finally {
  await sql.end()
}
"""

SERVER_LIB_DB = """import postgres from 'postgres'
import type { H3Event } from 'h3'

let _sql: ReturnType<typeof postgres> | null = null

export function useDb(_event?: H3Event): ReturnType<typeof postgres> {
  if (!_sql) {
    const config = useRuntimeConfig()
    const dbUrl = (config.databaseUrl as string) || process.env.DATABASE_URL || ''

    if (!dbUrl) {
      throw createError({ statusCode: 500, statusMessage: 'DATABASE_URL is not configured' })
    }

    const sslDisabled = dbUrl.includes('sslmode=disable')
    _sql = postgres(dbUrl, sslDisabled ? {} : { ssl: 'prefer' })
  }

  return _sql
}
"""

SERVER_LIB_CRYPTO = """import { createHash, randomBytes } from 'node:crypto'

export function randomToken(lengthBytes: number): string {
  return randomBytes(lengthBytes).toString('hex')
}

export function sha256(input: string): string {
  return createHash('sha256').update(input).digest('hex')
}
"""

SERVER_LIB_AUTH = """import type {{ H3Event }} from 'h3'
import bcrypt from 'bcryptjs'

import {{ randomToken, sha256 }} from './crypto'
import {{ useDb }} from './db'

const SESSION_COOKIE = '{slug}_session'
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000

export type CurrentUser = {{
  id: string
  email: string
  full_name: string
  is_superuser: boolean
}}

export async function hashPassword(password: string): Promise<string> {{
  return bcrypt.hash(password, 10)
}}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {{
  return bcrypt.compare(password, hash)
}}

export async function createSession(event: H3Event, userId: string): Promise<void> {{
  const sql = useDb(event)
  const rawToken = randomToken(32)
  const tokenHash = sha256(rawToken)
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS)

  await sql`
    INSERT INTO sessions (user_id, token_hash, expires_at)
    VALUES (${{userId}}, ${{tokenHash}}, ${{expiresAt}})
  `

  setCookie(event, SESSION_COOKIE, rawToken, {{
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: Math.floor(SESSION_TTL_MS / 1000)
  }})
}}

export async function clearSession(event: H3Event): Promise<void> {{
  const sql = useDb(event)
  const rawToken = getCookie(event, SESSION_COOKIE)
  if (rawToken) {{
    const tokenHash = sha256(rawToken)
    await sql`DELETE FROM sessions WHERE token_hash = ${{tokenHash}}`
  }}
  deleteCookie(event, SESSION_COOKIE, {{ path: '/' }})
}}

export async function getCurrentUser(event: H3Event): Promise<CurrentUser | null> {{
  const sql = useDb(event)
  const rawToken = getCookie(event, SESSION_COOKIE)
  if (!rawToken) return null

  const tokenHash = sha256(rawToken)
  const rows = await sql<CurrentUser[]>`
    SELECT u.id, u.email, u.full_name, u.is_superuser
    FROM sessions s
    JOIN users u ON u.id = s.user_id
    WHERE s.token_hash = ${{tokenHash}}
      AND s.expires_at > NOW()
    LIMIT 1
  `
  return rows[0] ?? null
}}
"""

SERVER_LIB_VALIDATION = """import { readBody } from 'h3'
import type { H3Event } from 'h3'
import type { ZodSchema } from 'zod'

export async function readValidatedBody<T>(event: H3Event, schema: ZodSchema<T>): Promise<T> {
  const body = await readBody(event)
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    throw createError({ statusCode: 422, statusMessage: parsed.error.message })
  }
  return parsed.data
}
"""

SERVER_LIB_ZSEND = """import type {{ H3Event }} from 'h3'

export type ZsendEventInput = {{
  email: string
  source: 'account_creation' | 'newsletter_form' | 'contact_form' | 'inbound_email' | 'waitlist' | 'csv_import' | 'api'
  product: string
  first_name?: string
  last_name?: string
  metadata?: Record<string, unknown>
}}

export async function recordZsendContact(event: H3Event, input: ZsendEventInput): Promise<void> {{
  const config = useRuntimeConfig()
  const baseUrl = (config.zsendBaseUrl as string) || ''
  const token = (config.zsendIngestToken as string) || ''
  const workspaceId = (config.zsendWorkspaceId as string) || ''

  if (!baseUrl || !token || !workspaceId) {{
    console.warn('[zsend] not configured (ZSEND_BASE_URL/INGEST_TOKEN/WORKSPACE_ID); skipping contact record')
    return
  }}

  try {{
    await $fetch(`${{baseUrl}}/api/v1/contacts`, {{
      method: 'POST',
      headers: {{ 'x-ingest-token': token }},
      body: {{
        workspace_id: workspaceId,
        email: input.email,
        first_name: input.first_name ?? null,
        last_name: input.last_name ?? null,
        source: input.source,
        product: input.product,
        metadata: input.metadata ?? {{}}
      }}
    }})
  }} catch (err) {{
    console.warn('[zsend] failed to record contact', err)
  }}
}}
"""

API_HEALTH = """export default defineEventHandler(() => ({ ok: true }))
"""

API_LOGIN = """import { z } from 'zod'

import { createSession } from '../../lib/auth'
import { useDb } from '../../lib/db'
import { readValidatedBody } from '../../lib/validation'
import bcrypt from 'bcryptjs'

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8)
})

export default defineEventHandler(async (event) => {
  const sql = useDb(event)
  const body = await readValidatedBody(event, loginSchema)

  const users = await sql<{ id: string; password_hash: string; email: string; full_name: string }[]>`
    SELECT id, password_hash, email, full_name FROM users WHERE email = ${body.email} LIMIT 1
  `

  const user = users[0]
  if (!user) {
    throw createError({ statusCode: 401, statusMessage: 'Invalid credentials' })
  }

  const ok = await bcrypt.compare(body.password, user.password_hash)
  if (!ok) {
    throw createError({ statusCode: 401, statusMessage: 'Invalid credentials' })
  }

  await createSession(event, user.id)
  return { user: { id: user.id, email: user.email, full_name: user.full_name } }
})
"""

API_LOGOUT = """import { clearSession } from '../../lib/auth'

export default defineEventHandler(async (event) => {
  await clearSession(event)
  return { ok: true }
})
"""

API_ME = """import { getCurrentUser } from '../../lib/auth'

export default defineEventHandler(async (event) => {
  const user = await getCurrentUser(event)
  if (!user) {
    throw createError({ statusCode: 401, statusMessage: 'Not authenticated' })
  }
  return { user }
})
"""

API_SIGNUP = """import {{ z }} from 'zod'

import {{ createSession, hashPassword }} from '../../lib/auth'
import {{ useDb }} from '../../lib/db'
import {{ readValidatedBody }} from '../../lib/validation'
import {{ recordZsendContact }} from '../../lib/zsend'

const signupSchema = z.object({{
  email: z.string().email(),
  password: z.string().min(8),
  fullName: z.string().min(2)
}})

export default defineEventHandler(async (event) => {{
  const sql = useDb(event)
  const body = await readValidatedBody(event, signupSchema)

  const existing = await sql<{{ id: string }}[]>`
    SELECT id FROM users WHERE email = ${{body.email}} LIMIT 1
  `
  if (existing[0]) {{
    throw createError({{ statusCode: 409, statusMessage: 'Email already in use' }})
  }}

  const passwordHash = await hashPassword(body.password)
  const inserted = await sql<{{ id: string; email: string; full_name: string }}[]>`
    INSERT INTO users (email, password_hash, full_name)
    VALUES (${{body.email}}, ${{passwordHash}}, ${{body.fullName}})
    RETURNING id, email, full_name
  `
  const user = inserted[0]

  await createSession(event, user.id)

  // Wire to ZergSend canonical contact pipeline (account_creation event)
  await recordZsendContact(event, {{
    email: user.email,
    source: 'account_creation',
    product: '{slug}',
    first_name: user.full_name.split(' ')[0],
    last_name: user.full_name.split(' ').slice(1).join(' ') || undefined,
    metadata: {{ user_id: user.id }}
  }})

  return {{ user }}
}})
"""

USE_ANALYTICS = """// ZergAlytics tracker composable.
// Pattern: beacon endpoint derives from <script src> origin (no data-api needed).
// See feedback_zb_tracker_cross_origin.md.

type EventType =
  | 'page_view'
  | 'form_submit'
  | 'outbound_click'
  | 'internal_click'
  | 'cta_click'
  | 'signup_complete'
  | 'login_complete'
  | 'custom'

export function useAnalytics() {
  const config = useRuntimeConfig()
  const endpoint = (config.public.analyticsEndpoint as string) || ''

  function track(eventType: EventType, payload: Record<string, unknown> = {}) {
    if (!endpoint || typeof window === 'undefined') return
    const body = JSON.stringify({
      event_type: eventType,
      page_path: window.location.pathname,
      page_url: window.location.href,
      referrer: document.referrer,
      timestamp: new Date().toISOString(),
      ...payload
    })
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, body)
    } else {
      fetch(endpoint, { method: 'POST', body, keepalive: true }).catch(() => {})
    }
  }

  return { track }
}
"""

README = """# {display}

[1-2 sentence intro — fill in.]

## Features

- Email/password auth with secure session cookies
- Multi-tenant ready
- ZergAlytics tracker pre-wired
- ZergSend contact pipeline pre-wired
- Fly.io deployment-ready

## Local Setup

1. Install dependencies:

```bash
npm install
```

2. Configure environment (`.env`):

```
DATABASE_URL=postgres://localhost:5432/{slug}
SESSION_SECRET=change-me
ZSEND_BASE_URL=http://localhost:3002
ZSEND_INGEST_TOKEN=
ZSEND_WORKSPACE_ID=
NUXT_PUBLIC_ANALYTICS_ENDPOINT=
```

3. Run migrations:

```bash
npm run db:migrate
```

4. Start dev server:

```bash
npm run dev
```

App boots on http://localhost:{port}.

## Tech Stack

- Nuxt 3 (Nitro/h3)
- TypeScript (strict)
- PostgreSQL via `postgres` client
- Tailwind CSS
- bcryptjs (password hashing)
- zod (validation)

## API Surface

- `GET  /api/health` — Fly healthcheck
- `POST /api/auth/signup` — create user
- `POST /api/auth/login` — issue session cookie
- `POST /api/auth/logout` — clear session
- `GET  /api/auth/me` — current user

## Deployment

Fly.io app `{slug}` in `epoch-ai-in` org:

```bash
flyctl apps create {slug} --org epoch-ai-in   # one-time
flyctl secrets set DATABASE_URL=... SESSION_SECRET=... -a {slug}
flyctl deploy -a {slug}
```

## Notes

- Session TTL: 30 days
- ZergAlytics endpoint set via `NUXT_PUBLIC_ANALYTICS_ENDPOINT`
- ZergSend integration: set `ZSEND_BASE_URL` + `ZSEND_INGEST_TOKEN` + `ZSEND_WORKSPACE_ID` to ship `account_creation` events to canonical contact store
"""

VAULT_POSITIONING = """# {display}

## Positioning tagline

[One-liner — fill in.]

## ICP

[1-sentence ICP — who buys this and why.]

## Hook

[1-line hook — why anyone cares right now.]

## 4 Differentiation Pillars

1. **AI-native** — agents are first-class participants, not bolted-on bots, webhooks, or sidebar widgets.
2. **Zstack-interconnected** — shared auth, agents, and data primitives; adopting {display} lowers the cost of adopting the next Zstack product.
3. **Much cheaper** — undercuts category leaders by design (see Pricing, below). Not a promo.
4. **Easy to automate** — agent context flows without webhook scaffolding.

## Product-specific differentiators

[3-5 bullets the 4 pillars don't capture.]

## Free-tier cap

[Cap goes here — must match ~/.claude/skills/zstack-product/free-tier-cap-matrix.md]

## Pricing

| Tier | Price | What |
|------|-------|------|
| Free | $0 | [cap] |
| Basic | $1/seat/mo | Full feature surface, no agent governance |
| Pro | $9/seat/mo | + scoped per-agent API tokens, tenant-safe routes, SSO, audit |
| Enterprise | Custom | + SLA, BYO-KMS, on-prem, SOC 2 / DPA |

## Integration narrative

[How {display} fits the Zstack arc — does it produce signal for Zergboard cards? Receive triggers from ZergMeeting? Etc.]

## Status

- Phase: bootstrapped (not yet shipped)
- Repo: ~/zerg/{slug}/
- Local dev port: {port}
- Fly app: {slug} (epoch-ai-in org, when deployed)
- Bootstrapped: {date}
"""

COMPETITIVE_INDEX = """# {category}

## Overview

[1-2 sentence category summary — what problem this solves, who plays in it.]

## At-a-glance

| Player | URL | Funded | ICP | Notes |
|--------|-----|--------|-----|-------|
| [competitor] | | | | |

## TL;DR

[3-5 bullets on the category landscape and where {display} fits.]
"""

COMPETITIVE_TEMPLATES = {
    "matrix.md": "# Feature × Competitor Matrix — {category}\n\n| Feature | {display} | [comp1] | [comp2] | Confidence |\n|---------|-----------|---------|---------|-----------|\n| | | | | |\n",
    "gaps.md": "# Gap Classification — {category}\n\n## Table stakes (we must have)\n\n## Differentiator parity (close enough)\n\n## Whitespace (we can own)\n\n## We have, they don't\n",
    "positioning.md": "# Positioning Brief — {display} ({category})\n\n## Elevator (1 line)\n\n## 5-line pitch\n\n## 3 candidate headlines\n",
    "positioning-deep.md": "# Deep Positioning — {display} ({category})\n\n## 4 Pillars (cite for {category})\n\n1. AI-native — \n2. Zstack-interconnected — \n3. Much cheaper — \n4. Easy to automate — \n\n## Anti-pitch\n\n## Objection handling\n",
    "pricing.md": "# Pricing — {category}\n\n## {display}\n\n- Free | Basic $1 | Pro $9 | Enterprise (per Pricing-Snapshot.md)\n\n## Competitor pricing\n\n| Player | Free | Lowest paid | Mid | Top |\n|--------|------|-------------|-----|-----|\n| | | | | |\n",
    "differentiation-opportunities.md": "# Differentiation Opportunities — {category}\n\n10 candidate hunt-phase ideas (rank by RICE):\n\n1. \n2. \n3. \n4. \n5. \n6. \n7. \n8. \n9. \n10. \n",
    "drift.md": "# Spec vs Live Drift — {category}\n\n[Mismatches between what the {display} positioning claims and what the live product/marketing actually delivers.]\n",
}


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(Path.home())}")


def bootstrap_code_repo(slug: str, display: str, port: int) -> Path:
    repo = ZERG_ROOT / slug
    if repo.exists():
        raise RuntimeError(f"{repo} already exists — refusing to overwrite. Move or delete it first.")
    print(f"\n== code repo: ~/zerg/{slug}/")

    write_file(repo / "package.json", PACKAGE_JSON.format(slug=slug))
    write_file(repo / "nuxt.config.ts", NUXT_CONFIG.format(display=display))
    write_file(repo / "assets/css/main.css", TAILWIND_CSS)
    write_file(repo / "Dockerfile", DOCKERFILE.format(port=port))
    write_file(repo / "fly.toml", FLY_TOML.format(slug=slug, port=port))
    write_file(repo / "db/schema.sql", DB_SCHEMA)
    write_file(repo / "db/migrate.mjs", DB_MIGRATE)
    write_file(repo / "server/lib/db.ts", SERVER_LIB_DB)
    write_file(repo / "server/lib/crypto.ts", SERVER_LIB_CRYPTO)
    write_file(repo / "server/lib/auth.ts", SERVER_LIB_AUTH.format(slug=slug))
    write_file(repo / "server/lib/validation.ts", SERVER_LIB_VALIDATION)
    write_file(repo / "server/lib/zsend.ts", SERVER_LIB_ZSEND)
    write_file(repo / "server/api/health.get.ts", API_HEALTH)
    write_file(repo / "server/api/auth/login.post.ts", API_LOGIN)
    write_file(repo / "server/api/auth/logout.post.ts", API_LOGOUT)
    write_file(repo / "server/api/auth/me.get.ts", API_ME)
    write_file(repo / "server/api/auth/signup.post.ts", API_SIGNUP.format(slug=slug))
    write_file(repo / "composables/useAnalytics.ts", USE_ANALYTICS)
    write_file(
        repo / "README.md",
        README.format(display=display, slug=slug, port=port),
    )
    # Pages dir + minimal layout to keep Nuxt happy
    write_file(repo / "pages/index.vue", '<template><div class="p-8"><h1 class="text-3xl">' + display + '</h1></div></template>\n')
    write_file(repo / "components/.gitkeep", "")
    write_file(repo / ".gitignore", "node_modules\n.output\n.nuxt\n.env\n.DS_Store\n")
    return repo


def bootstrap_vault(slug: str, display: str, port: int) -> Optional[Path]:
    if not VAULT_ROOT.is_dir():
        print(f"\n== vault: SKIPPED (vault not present at {VAULT_ROOT})")
        return None
    # New microproducts start in the Development layer as folder-per-product
    # (commitment model: just-starting → Zerg-Development; promote to Zerg-Production later).
    proj_dir = VAULT_ROOT / "Projects" / "Zerg-Development" / display
    proj_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n== vault: {proj_dir}/{display}.md")
    from datetime import date
    pos = proj_dir / f"{display}.md"
    if pos.exists():
        print(f"  exists; not overwriting: {pos}")
        return pos
    write_file(
        pos,
        VAULT_POSITIONING.format(display=display, slug=slug, port=port, date=date.today().isoformat()),
    )
    return pos


def bootstrap_competitive(category: str, slug: str, display: str) -> Optional[Path]:
    if not VAULT_ROOT.is_dir():
        return None
    comp_dir = VAULT_ROOT / "Competitive" / category
    print(f"\n== competitive: {comp_dir}/")
    if comp_dir.is_dir():
        print(f"  category folder exists; only filling missing files")
    if not (comp_dir / "index.md").is_file():
        write_file(comp_dir / "index.md", COMPETITIVE_INDEX.format(category=category, display=display))
    for fname, tmpl in COMPETITIVE_TEMPLATES.items():
        target = comp_dir / fname
        if target.is_file():
            print(f"  exists; skipping {fname}")
            continue
        write_file(target, tmpl.format(category=category, display=display))
    return comp_dir


def update_port_registry(slug: str, port: int) -> None:
    if not PORT_REGISTRY.is_file():
        return
    text = PORT_REGISTRY.read_text(encoding="utf-8")
    if f"| {port} |" in text and slug not in text:
        print(f"  warn: port {port} row exists; not updating registry. Add manually if desired.")
        return
    if slug in text:
        return
    addition = f"| {port} | {slug} | Nitro | bootstrapped |\n"
    # naive: append after the last 30xx row
    lines = text.splitlines(keepends=True)
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("| 30") or line.startswith("| 31"):
            insert_at = i + 1
    if insert_at is None:
        return
    lines.insert(insert_at, addition)
    PORT_REGISTRY.write_text("".join(lines), encoding="utf-8")
    print(f"  updated port-registry.md: {port} → {slug}")


def main() -> int:
    p = argparse.ArgumentParser(description="Bootstrap a new Zstack microproduct")
    p.add_argument("slug", help="Product slug (e.g. zcrm-test)")
    p.add_argument("--category", required=True, help="Competitive category (e.g. crm, pm-software)")
    p.add_argument("--port", type=int, default=None, help="Localhost port (auto-assigned if omitted)")
    p.add_argument("--display-name", default=None, help="Display name (e.g. ZergCRM)")
    args = p.parse_args()

    slug = args.slug
    display = args.display_name or display_default(slug)
    port = assign_port(args.port)

    print(f"Bootstrapping {display} (slug={slug}, port={port}, category={args.category})")

    repo = bootstrap_code_repo(slug, display, port)
    bootstrap_vault(slug, display, port)
    bootstrap_competitive(args.category, slug, display)
    update_port_registry(slug, port)

    print()
    print("Next steps:")
    print(f"  cd {repo}")
    print(f"  npm install && npm run db:migrate && npm run dev   # dev server on http://localhost:{port}")
    print(f"  python3 {SKILL_DIR}/audit.py {slug} --category {args.category}   # confirm zero HIGH findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
