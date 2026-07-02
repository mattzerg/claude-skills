# Canonical Patterns — Zstack Microproducts

The frozen WHAT. Code snippets are NOT here — see `reference-products.md` for live pointers.

Patterns extracted from cross-product survey of zergboard, zsend, zergwallet, zmail, zmsg as of 2026-05-07.

---

## 1. Tech Stack (Nuxt fullstack tier)

| Component | Pin | Source |
|-----------|-----|--------|
| Framework | Nuxt `^3.17.2` | zergboard `package.json` |
| Language | TypeScript `^5.6.3` (strict + typeCheck) | zergboard `nuxt.config.ts` |
| Package manager | npm | all products |
| DB client | `postgres@^3.4.5` (no ORM) | zergboard, zsend |
| Password hashing | `bcryptjs@^2.4.3` | zergboard, zsend |
| Validation | `zod@^3.23.8` | zergboard, zsend |
| Tailwind | `@nuxtjs/tailwindcss@^6.13.1` | all Nuxt products |

**Backend service tier** (zmail, zmsg) is FastAPI + Python 3.11 — out of scope for the Nuxt-template bootstrap; treat separately.

---

## 2. Project Layout (Nuxt)

```
<slug>/
├── pages/                  # File-based routing
├── server/
│   ├── api/                # Nitro route handlers
│   │   ├── health.get.ts   # Required: /api/health (Fly healthcheck)
│   │   └── auth/
│   │       ├── login.post.ts
│   │       ├── logout.post.ts
│   │       ├── signup.post.ts
│   │       └── me.get.ts
│   └── lib/                # Helpers — auth, db, validation, etc.
│       ├── auth.ts
│       ├── db.ts
│       ├── crypto.ts
│       └── validation.ts
├── components/             # Vue SFCs
├── composables/            # Vue 3 composition utilities
├── layouts/
├── assets/
│   └── css/
│       └── main.css        # Tailwind imports + brand vars
├── db/
│   ├── schema.sql          # Raw SQL (NOT an ORM migrations file)
│   └── migrate.mjs         # Runs schema.sql via postgres.unsafe()
├── public/
├── Dockerfile
├── fly.toml
├── nuxt.config.ts
├── package.json
└── README.md
```

**Audit rule**: `server/lib/` MUST exist with at minimum `auth.ts` + `db.ts`. Zergboard's signup imports from `../../lib/auth` but the dir is missing — that is itself a drift finding.

---

## 3. Auth Pattern

- **Hash**: bcryptjs round 10 (`bcrypt.hash(password, 10)`)
- **Sessions**: HTTP-only cookies; token = 32-byte random; `token_hash` (sha256) stored server-side
- **Cookie**: `<slug>_session`, sameSite `lax`, secure in production, 30-day maxAge
- **Helpers**: `hashPassword`, `verifyPassword`, `createSession`, `clearSession`, `getCurrentUser` — all from `server/lib/auth.ts`
- **DB tables required**: `users` (id UUID, email, password_hash, full_name, is_superuser), `sessions` (token_hash, expires_at)

**Audit rule**: Token-based auth (Djoser-style, like `~/zerg/web/`) is NOT canonical for new microproducts. Stick to session cookies unless the product is API-only.

---

## 4. DB Pattern

- **DB**: PostgreSQL with `pgcrypto` extension (UUID via `gen_random_uuid()`)
- **Client**: `postgres` npm package (NOT Drizzle, NOT Prisma)
- **Migrations**: Single `db/schema.sql` with idempotent `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE … ADD COLUMN IF NOT EXISTS`. Re-run safe.
- **Runner**: `db/migrate.mjs` reads schema.sql + `sql.unsafe(schema)`. Wired as `npm run db:migrate`.
- **Connection**: Singleton `useDb(event)` in `server/lib/db.ts`; reads `DATABASE_URL`; SSL `prefer` unless `sslmode=disable` in URL.

**Audit rule**: ORMs are not canonical. Schema evolution = idempotent ALTERs. No separate migration files (e.g., `001_create_users.sql`).

---

## 5. Build (Dockerfile)

- **Base**: `node:22-alpine`
- **Stages**: `base` → `deps` (npm install) → `build` (npm run build) → `prod-deps` (npm install --omit=dev) → `runtime`
- **Install command**: `npm install` (NOT `npm ci`) — workaround for `zerg-ztc 0.1.72` workspace packaging bug
- **Runtime copies**: `.output/`, `node_modules/` (from prod-deps), `package.json`, `db/`
- **Expose**: assigned port (default 3000)
- **CMD**: `node .output/server/index.mjs`

zsend has the most optimized template (separate prod-deps stage). Use zsend's Dockerfile shape.

**Audit rule**: `npm ci` is forbidden in the Dockerfile until the ztc workspace bug is fixed.

---

## 6. Deploy (Fly.io)

- **Org**: `epoch-ai-in` (slug, NOT `epoch-ai`) — cite `feedback_fly_org.md`
- **Primary region**: `lax` for Nitro/Node; `sjc` for Python/FastAPI
- **fly.toml** required fields:
  - `app = "<slug>"`
  - `primary_region = "lax"`
  - `[build] dockerfile = "Dockerfile"`
  - `[env] NITRO_HOST = "0.0.0.0", NITRO_PORT = "<port>"`
  - `[http_service] internal_port = <port>, force_https = true, auto_stop_machines = "stop", auto_start_machines = true, min_machines_running = 0`
  - `[[http_service.checks]] path = "/api/health"`, grace 15s, interval 30s, timeout 5s, GET
- **Org check**: `flyctl status -a <slug>` shows org; not declarable in fly.toml — must be set at `flyctl apps create --org epoch-ai-in`.

**Audit rule**: missing `/api/health` check, wrong region, or org ≠ `epoch-ai-in` is HIGH.

---

## 7. Theme & Brand

- **Brand palette** (per `feedback_zerg_brand.md`):
  - Cream paper `#f4f0e7`
  - Charcoal `#111514`
  - Burnt-orange `#b3662f` (`#8a4a1f` on cream for AA contrast)
  - Brand green `#6FBE31`
- **Font**: Space Grotesk
- **Source of truth**: `~/zerg/web/src/pages/index.vue` (NOT `main.css`)
- **Apply via**: Tailwind config + `--skin-*` CSS variables in `nuxt.config.ts` prepaint script
- **Marketing/external surfaces** must use brand palette. Internal app-chrome may use product-specific skins (zergboard's terminal/light/ocean/amber presets are valid for in-app theming, NOT for marketing pages).

**Audit rule**: Marketing pages and OG/social cards MUST use brand palette. In-app skins may diverge.

---

## 8. Pricing

Locked 2026-05-05, all 9 products:

| Tier | Price | Notes |
|------|-------|-------|
| Free | $0 | Volume-capped per product (see `free-tier-cap-matrix.md`) |
| Basic | $1/seat/mo | Full feature surface, no agent governance |
| Pro | $9/seat/mo | + scoped per-agent API tokens, tenant-safe routes, SSO, audit |
| Enterprise | Custom | + SLA, BYO-KMS, on-prem, SOC 2 / DPA |

Bundle SKUs:
- Zstack Basic: $4/seat/mo
- Zstack Pro: $19/seat/mo

**Audit rule**: positioning doc must claim these tier prices verbatim. Drift = MED.

---

## 9. Differentiation Pillars

All products explicitly claim these 4 pillars in their positioning doc:

1. **AI-native** — agents are first-class participants, not bolted-on bots
2. **Zstack-interconnected** — shared auth, agents, data primitives; one adoption lowers next-product cost
3. **Much cheaper** — 7–19× undercut on category leaders
4. **Easy to automate** — agent context flows without webhook scaffolding

**Audit rule**: positioning doc missing any of the 4 = MED finding.

---

## 10. Vault layout

- **Positioning**: `MattZerg/Projects/Zerg-Production/Zstack/<Product>.md` — required sections: positioning tagline, ICP, hook, 4 pillars, product-specific differentiators, Free-tier cap, pricing tiers, integration narrative slot
- **Pricing source of truth**: `MattZerg/Projects/Zerg-Production/Zstack/Pricing-Snapshot.md`
- **Integration narrative**: `MattZerg/Projects/Zerg-Production/Zstack/Integration.md`
- **Voice anchor**: `MattZerg/_style/voice_universals.md` (loaded by all prose-related skills)

**Audit rule**: positioning doc not present at canonical path = HIGH.

---

## 11. Competitive folder (8-file shape)

`MattZerg/Competitive/<category>/`:

```
<category>/
├── index.md                              # Overview + at-a-glance + TL;DR
├── matrix.md                             # Feature × competitor matrix (with confidence column)
├── gaps.md                               # 4-bucket classification: table-stakes / parity / whitespace / we-have
├── positioning.md                        # Short brief (elevator + 5 lines + 3 headlines)
├── positioning-deep.md                   # Full pillars + anti-pitch + objection handling
├── pricing.md                            # Tier prices + per-competitor detail
├── differentiation-opportunities.md      # 10 candidate hunt phase outputs
└── drift.md                              # Spec vs live mismatches on Zerg's own pages
```

Plus optional `competitors/<name>.md` deep notes and `archive/<date>/` for prior runs.

**Audit rule**: missing any of 8 files = MED. Folder absent entirely = HIGH (positioning has no competitive context).

---

## 12. Cross-product wiring

These integrations MUST be wired in every new product:

- **ZergAlytics tracker**: composable based on `~/zerg/web/src/composables/useAnalytics.ts`; embed in `nuxt.config.ts`. Cite `feedback_zb_tracker_cross_origin.md` — beacon endpoint derives from `<script src>`, no `data-api` needed.
- **ZergSend `upsert_contact` call**: signup endpoint MUST POST `account_created` event to ZergSend. Payload shape from `~/zerg/zsend/server/lib/upsert_contact.ts` `UpsertContactInput`. Use `ZSEND_INGEST_TOKEN` env var.
- **lifecycle-email trigger stub**: emit `signup`, `aha-event`, `pro-upgrade` events; consumed by `lifecycle-email` skill.
- **App-switcher**: stub component for cross-product navigation. Currently no product has this; first product to ship it sets the pattern.

**Audit rule**: tracker missing = HIGH. upsert_contact missing = HIGH. app-switcher missing = MED (no product has it yet, so this is a forward-looking finding).

---

## 13. Severity guide

- **HIGH**: ships-blocking. Examples: wrong Fly org, no healthcheck, npm ci, missing tracker, orphaned signup events, missing positioning doc.
- **MED**: pattern drift to fix soon. Examples: brand color drift, README missing sections, free-tier cap unstated, missing competitive folder file, missing pillar in positioning.
- **LOW**: product-specific divergence. Examples: added deps (zerg-ztc), optional patterns, in-app skin presets.

---

## 14. README canonical shape (7 sections)

1. **Intro** — 1–2 sentences
2. **Features** — bullet list
3. **Local Setup** — install, env, migrate, run
4. **Tech Stack** — key deps
5. **API Surface** — endpoint listing
6. **Deployment** — Fly.io secrets + deploy command
7. **Notes / Advanced** — session TTL, admin panel, superuser provisioning

**Audit rule**: missing section = MED.

---

## 15. Port registry

See `port-registry.md`. Bootstrap MUST consult registry before assigning a port.

| Slug | Port |
|------|------|
| zergboard | 3000 |
| zergwallet | 3001 |
| zsend | 3002 |
| zergbox | 3000 (conflict — shared dev with zergboard) |
| zmail | 8080 (FastAPI) |
| zmsg | 8080 (FastAPI) |
| (next) | 3003+ |

---

## §16 — Per-product Zerglytics measurement spec (HIGH)

Every Zstack product MUST have a per-product measurement spec at:

    MattZerg/Projects/Zerg-Production/Growth/measurement/<product_id>.yaml

The file declares: required events (signup / aha / pro_upgrade / bundle_upgrade /
last_active_at / churn_risk), optional events, funnels (acquisition / conversion /
expansion), cohorts, dashboard line bindings, UTM allowlist, and a kill_readiness_gate.

Event taxonomy convention: `<product_id>_<event_name>` (snake_case, both sides).
product_id matches the port-registry slug from §15.

The spec is the source-of-truth for:
- `funnel-analyzer bind --product <slug>` (expands funnels into per-funnel YAMLs)
- `growth-dashboard` lines 1-4 + 7-11 (resolves event names per product)
- `launch-ops` Phase 2 gate (parses sibling `.checklist.md` for ship-readiness)
- `utm-attribution` (validates utm_campaign_prefix on every link)

Template lives at `Growth/measurement/_template.yaml`. The companion file
`Growth/measurement/<product_id>.checklist.md` is created from
`Growth/measurement/_checklist-template.md` and parsed by `launch-ops`.

**Audit check:** `zstack-product audit <slug>` HIGH-fails if either the YAML or
the checklist is missing. MED-fails if optional events or expansion funnel are absent.

---

## §17 — Per-product docs surface (HIGH)

Every Zstack product MUST ship a docs directory at `~/zerg/<slug>/docs/`
scaffolded from `~/zerg/_templates/zerg-product/product-docs/`. The docs README
MUST contain exactly these 6 canonical H2 sections (in order):

    ## What it is
    ## Quick start
    ## Concepts
    ## API
    ## Frontend
    ## Status

Plus the 7 sibling files: getting-started.md, architecture.md, what-can-i-build.md,
api-backend.md, web-frontend.md, faq.md, changelog.md.

The docs scaffold is dropped by `zerg-new-product.sh` alongside the waitlist or
product-website variant. After ship, the docs are maintained by `product-docs-skill`
(verbs: `scaffold`, `audit`). `product-docs-skill audit <slug>` HIGH-fails on
missing required section, dead internal link, or staleness (changelog.md not
updated in 90 days while git log shows shipped commits).

The docs surface is a launch gate. `launch-ops check <slug>` blocks ship until
`product-docs-skill audit <slug>` returns 0 HIGH findings.

---

## Refresh discipline

This catalog is FROZEN. To refresh:

1. Re-run `audit` against all reference products (zergboard, zsend, zergwallet)
2. If a reference product fails its own canonical-patterns check → either reference drifted or the rule is stale; pick one
3. Bump the dep pin section against current `package.json` files quarterly
4. Cite memory entries by name (`feedback_zerg_brand.md`, etc.) so the rule's source is traceable
