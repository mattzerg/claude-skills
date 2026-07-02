# Post-#284 follow-up — ready-to-apply recipe

Audit findings remaining after PR #284 merges. Apply against `development` AFTER #284 lands.

Estimated total diff: ~250 lines across 3 products.

## Branch shape

```bash
git fetch origin development
git checkout -b matt/zstack-tracker-and-zergbox-bringup origin/development
# (apply patches below)
git push -u origin matt/zstack-tracker-and-zergbox-bringup
gh pr create --title "zstack: ZergAlytics tracker (zergboard/zergwallet/zsend) + zergbox bringup" --base development
```

Per `feedback_minimize_prs.md`: bundle ALL of this in ONE PR. Don't split.

Per `feedback_pr_body_unlocks.md`: PR body needs "why now + what this unlocks" — see template at the bottom.

---

## Fix A — ZergAlytics tracker (zergboard, zergwallet, zsend)

**Why HIGH:** Every page view, signup, CTA click goes unmeasured today. Growth dashboard line 3 (activation rate) is starved. Closes audit finding **A1** for 3 products.

**Reference source:** `~/zerg/web/src/composables/useAnalytics.ts` (the canonical tracker, currently only embedded on the marketing site).

**Per memory `feedback_zb_tracker_cross_origin.md`:** beacon endpoint MUST derive from `<script src>` URL. Don't re-introduce a relative default — silently 404s on every cross-origin host.

### A.1 — `<slug>/composables/useAnalytics.ts` (NEW file, 3 products)

Copy the file verbatim from `~/zerg/web/src/composables/useAnalytics.ts`. No edits needed — it's already cross-origin-safe.

```bash
for slug in zergboard zergwallet zsend; do
  cp ~/zerg/web/src/composables/useAnalytics.ts ~/zerg/$slug/composables/useAnalytics.ts
done
```

### A.2 — `<slug>/nuxt.config.ts` runtimeConfig (3 products)

Add the public analytics endpoint to runtimeConfig if not already present:

```diff
   runtimeConfig: {
     databaseUrl: process.env.DATABASE_URL,
     sessionSecret: process.env.SESSION_SECRET || 'dev-secret-change-me',
     // ... existing entries ...
     public: {
-      appName: 'Zergboard'
+      appName: 'Zergboard',
+      analyticsEndpoint: process.env.NUXT_PUBLIC_ANALYTICS_ENDPOINT || ''
     }
   },
```

Async: provision `NUXT_PUBLIC_ANALYTICS_ENDPOINT` env var per Fly app before deploying.

### A.3 — `<slug>/app.vue` or `<slug>/layouts/default.vue` page-view auto-fire

Add at the top of the script setup block:

```ts
const { track } = useAnalytics()
const route = useRoute()
watch(() => route.fullPath, () => track('page_view'), { immediate: true })
```

---

## Fix B — Zergbox bringup (signup wiring + server/lib materialization)

zergbox is the only Nuxt product not in PR #284. Same gaps zergboard had pre-#284.

### B.1 — `zergbox/server/lib/` materialization (closes A3)

Copy from zsend (the canonical server/lib/ reference per `reference-products.md`):

```bash
cp ~/zerg/zsend/server/lib/auth.ts     ~/zerg/zergbox/server/lib/auth.ts
cp ~/zerg/zsend/server/lib/db.ts       ~/zerg/zergbox/server/lib/db.ts
cp ~/zerg/zsend/server/lib/crypto.ts   ~/zerg/zergbox/server/lib/crypto.ts
cp ~/zerg/zsend/server/lib/validation.ts ~/zerg/zergbox/server/lib/validation.ts
```

Then update SESSION_COOKIE constant in the copied auth.ts: `'zsend_session'` → `'zergbox_session'`.

### B.2 — `zergbox/server/lib/zsend.ts` (NEW file, closes A2)

Use the canonical `recordZsendContact` helper from `bootstrap.py` (look for the `SERVER_LIB_ZSEND` constant). Copy that template verbatim into `zergbox/server/lib/zsend.ts`.

### B.3 — `zergbox/server/api/auth/signup.post.ts` — call upsert after createSession

```diff
   await createSession(event, user.id)

+  await recordZsendContact(event, {
+    email: user.email,
+    source: 'account_creation',
+    product: 'zergbox',
+    first_name: user.full_name.split(' ')[0],
+    last_name: user.full_name.split(' ').slice(1).join(' ') || undefined,
+    metadata: { user_id: user.id }
+  })
+
   return { user }
```

Add the import at top: `import { recordZsendContact } from '../../lib/zsend'`

### B.4 — `zergbox/nuxt.config.ts` runtimeConfig

Same pattern as A.2 plus the zsend wiring fields:

```diff
   runtimeConfig: {
     databaseUrl: process.env.DATABASE_URL,
+    zsendBaseUrl: process.env.ZSEND_BASE_URL || '',
+    zsendIngestToken: process.env.ZSEND_INGEST_TOKEN || '',
+    zsendWorkspaceId: process.env.ZSEND_WORKSPACE_ID || '',
     // ...
     public: {
       appName: 'Zergbox',
+      analyticsEndpoint: process.env.NUXT_PUBLIC_ANALYTICS_ENDPOINT || ''
     }
   },
```

---

## Verification

After applying all of the above:

```bash
# Re-audit each product — expect ZERO HIGH findings post-merge
python3 ~/.claude/skills/zstack-product/audit.py zergboard
python3 ~/.claude/skills/zstack-product/audit.py zergwallet
python3 ~/.claude/skills/zstack-product/audit.py zsend
python3 ~/.claude/skills/zstack-product/audit.py zergbox

# Smoke-test the tracker locally (each product on its registered port)
cd ~/zerg/zergboard && npm run dev
# Visit http://localhost:3000, open devtools network tab, confirm beacon to NUXT_PUBLIC_ANALYTICS_ENDPOINT

# Smoke-test upsert_contact for zergbox
curl -X POST http://localhost:3000/api/auth/signup -H 'content-type: application/json' \
  -d '{"email":"smoke-test@zerg.local","password":"smoke1234","fullName":"Smoke Test"}'
# Confirm the corresponding `account_created` event appears in zsend dev logs
```

---

## PR body template

```markdown
## Why now + what this unlocks

**Why now:** Cross-product audit (`MattZerg/Projects/Zerg-Production/Zstack/audit-sweep-2026-05-07.md`) flagged 4 HIGH findings on the same 3 patterns across 4 Nuxt products. PR #284 closed `upsert_contact` wiring for zergboard/zergwallet/zsend/zcal. This PR closes the remaining HIGH findings:
- ZergAlytics tracker not embedded → growth-dashboard line 3 (activation rate) starved
- Zergbox missing signup → zsend wiring (parity with #284 for the one product not included)
- Zergbox missing `server/lib/` materialization (same ghost-import gotcha as zergboard, documented in `feedback_zergboard_server_lib_ghost_import.md`)

**What this unlocks:**
- Activation rate measurement starts firing across all Nuxt products
- Lifecycle email triggers (welcome drip, churn-save) get real signup events to consume
- Re-auditing each product post-merge returns 0 HIGH findings — proves the canonical-pattern catalog holds

## Test plan

- [ ] `audit zergboard` returns 0 HIGH
- [ ] `audit zergwallet` returns 0 HIGH
- [ ] `audit zsend` returns 0 HIGH
- [ ] `audit zergbox` returns 0 HIGH
- [ ] Tracker beacon fires on page navigation (devtools network)
- [ ] Zergbox signup creates `account_created` event in zsend
```

---

## Async dependencies

- `NUXT_PUBLIC_ANALYTICS_ENDPOINT` env var per Fly app (zergboard / zergwallet / zsend / zergbox)
- `ZSEND_INGEST_TOKEN` per app (zergbox needs one)
- `ZSEND_WORKSPACE_ID` per app

These are config-only — set via `flyctl secrets set` once, no code change needed after the PR merges.
