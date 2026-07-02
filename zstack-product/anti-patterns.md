# Anti-Patterns — Drift Catalog

Every drift below was found in the cross-product survey 2026-05-07. Audit mode looks for each.

---

## HIGH — ships-blocking

### A1. Tracker not embedded
- **Where seen**: zergboard `nuxt.config.ts`, zsend `nuxt.config.ts` — neither imports `useAnalytics`
- **Why bad**: every page view, every signup, every CTA click goes unmeasured; growth dashboard is starved
- **Fix recipe**: copy `~/zerg/web/src/composables/useAnalytics.ts` → `<slug>/composables/useAnalytics.ts`; wire in `app.vue` or layouts; ZergAlytics endpoint derives from script src per `feedback_zb_tracker_cross_origin.md`

### A2. `upsert_contact` not called from signup
- **Where seen**: `~/zerg/zergboard/server/api/auth/signup.post.ts` — creates user, never POSTs to ZergSend
- **Why bad**: every account creation is orphaned from canonical contact + lifecycle-email pipeline
- **Fix recipe**: after `createSession`, POST `{ workspace_id, email, source: 'account_creation', product: '<slug>', metadata: { user_id } }` to `${ZSEND_BASE_URL}/api/v1/contacts` with header `x-ingest-token: ${ZSEND_INGEST_TOKEN}`. Payload shape from `~/zerg/zsend/server/lib/upsert_contact.ts` `UpsertContactInput`.

### A3. `server/lib/` directory missing
- **Where seen**: `~/zerg/zergboard/server/` — `lib/` directory absent despite imports `from '../../lib/auth'` in `signup.post.ts`. Either build alias is masking, or this is broken in prod and silent in dev.
- **Why bad**: refactor risk; new contributors can't find auth helpers; matches zsend pattern in spirit but not in fact.
- **Fix recipe**: Either materialize `server/lib/auth.ts` etc. (copy from zsend) or change imports to wherever the helpers actually live.

### A4. Fly app in wrong org
- **Where seen**: zerglytics in `personal` org, per memory `feedback_fly_org.md`
- **Why bad**: not on org billing; missing audit/observability shared across Zerg apps
- **Fix recipe**: `flyctl apps move <slug> --org epoch-ai-in` (verify behavior; some flyctl versions require app-recreate)

### A5. `npm ci` in Dockerfile
- **Where seen**: not seen in surveyed Nuxt products yet, but called out in memory `feedback_zerg_ztc_workspace_bug.md`
- **Why bad**: zerg-ztc 0.1.72 publishes workspaces field referencing non-shipped packages; npm ci fails
- **Fix recipe**: replace with `npm install` until ztc fix lands

### A6. Positioning doc missing
- **Where seen**: hypothetically — every new product without `MattZerg/Projects/Zerg-Production/Zstack/<Product>.md`
- **Why bad**: launch announcement, one-pager, landing page all read positioning from this file; missing = no canonical claims
- **Fix recipe**: bootstrap mode generates from template

### A7. Auth uses Djoser-style token auth
- **Where seen**: `~/zerg/web/src/composables/useAuth.ts` — but this is marketing site, not a microproduct, so not really a finding
- **Why bad** (if found in a microproduct): diverges from session-cookie standard; cross-product session sharing impossible
- **Fix recipe**: replace with session-cookie pattern from zsend's `server/lib/auth.ts`

---

## MED — pattern drift to fix soon

### B1. Brand palette drift
- **Where seen**: zergboard `--skin-*` presets are terminal/light/ocean/amber — NOT brand cream/charcoal/orange/green
- **Why bad** (for marketing pages): inconsistent visual identity; OG cards render in wrong palette
- **Caveat**: in-app theming may legitimately use product-specific skins. Audit only flags marketing pages + OG/social cards.
- **Fix recipe**: marketing pages set CSS vars from `~/zerg/web/src/pages/index.vue` brand block; in-app pages keep their skin presets

### B2. Free-tier cap unstated
- **Where seen**: positioning docs vary — "3 users", "5 meetings/mo", "50 msgs/day", "1 calendar"
- **Why bad**: each product invents its own; bundle pricing math gets fuzzy
- **Fix recipe**: bootstrap fills cap from `free-tier-cap-matrix.md`

### B3. README missing sections
- **Where seen**: some products skip "API Surface" or "Notes / Advanced"
- **Why bad**: onboarding new contributors slows; deploy details get lost
- **Fix recipe**: bootstrap stamps the 7-section shape; audit checks for each H2

### B4. Pillar missing from positioning
- **Where seen**: surveyed positioning docs all claim 4, but if any drift…
- **Why bad**: launch copy + competitive briefs lose pillar coverage
- **Fix recipe**: positioning doc must include all 4 pillars verbatim

### B5. Competitive folder gaps
- **Where seen**: some categories have only 4–5 of the 8 canonical files
- **Why bad**: positioning + landing page generation is starved of source data
- **Fix recipe**: bootstrap creates 8-file shape; audit checks each file present

### B6. App-switcher missing
- **Where seen**: every product. zergboard's CommandPalette is internal-only.
- **Why bad**: bundle narrative ("adopt one product, lower cost of next") falls flat without a UI affordance
- **Fix recipe**: stub component in bootstrap; first product to populate sets the pattern

### B7. lifecycle-email trigger stub missing
- **Where seen**: no product fires lifecycle events to email-drip skill yet
- **Why bad**: welcome drips, churn-save, expansion — all untriggered
- **Fix recipe**: bootstrap stamps a trigger stub in signup endpoint

### B8. Pricing not Free/$1/$9/Enterprise
- **Where seen**: in positioning docs — should be locked but worth checking
- **Fix recipe**: positioning doc claims tier prices verbatim

---

## LOW — product-specific divergence

### C1. Extra deps (e.g., zerg-ztc)
- **Where seen**: zergwallet imports `zerg-ztc@0.1.68`
- **Why ok**: legitimate product-specific need (session/crypto utilities for wallet)
- **Audit note**: flag for awareness, not action

### C2. Persistent volume mounts
- **Where seen**: zmail, zmsg, zergbox have `[mounts]`
- **Why ok**: stateful services need them; Nitro serverless products don't
- **Audit note**: flag inconsistency only if mount appears on a stateless Nitro product

### C3. Distinct port assignment
- **Where seen**: zergwallet on 3001 (instead of 3000 default)
- **Why ok**: avoids collision with zergboard
- **Audit note**: must match registry

### C4. Custom zergboard `--skin-*` presets
- **Why ok**: in-app theming legitimate divergence (see B1)

---

## Anti-patterns NOT yet seen but to watch for

- **OAuth provider divergence** — first product to add Google/GitHub OAuth sets the pattern; canonical lib path TBD
- **Per-agent vs per-seat pricing** — ZergMail and ZergCal may go per-agent; resolve before second per-agent product ships
- **Zergalytics naming** — spelled both Zergalytics and Zerglytics; pick one (probably ZergAlytics for prose, zerglytics for filesystem)
