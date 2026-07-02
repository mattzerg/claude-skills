# Reference Products — Live Snippet Pointers

The HOW. For each canonical pattern, this maps to a real file the skill reads at runtime.

If a reference product drifts (e.g., adds a new field, changes a dep), the skill picks it up automatically — that's the upside of hybrid sourcing. The downside: the skill can also pick up REGRESSIONS. Mitigation: audit mode runs against reference products on every invocation and warns if they fail their own rules.

---

## Reference products by domain

| Pattern | Primary reference | Why |
|---------|-------------------|-----|
| `db/schema.sql` + `migrate.mjs` | `~/zerg/zergboard/db/` | Most evolved schema (users, orgs, memberships, invites, boards, cards, workspace-sessions) |
| `server/lib/auth.ts`, `db.ts`, `crypto.ts`, `validation.ts` | `~/zerg/zsend/server/lib/` | zergboard imports from `../../lib/auth` but `server/lib/` is missing — zsend has the actual canonical layout |
| `server/api/auth/{login,logout,signup,me}.post.ts` | `~/zerg/zergboard/server/api/auth/` | Most complete (incl. tokens) |
| `server/api/health.get.ts` | `~/zerg/zergboard/server/api/health.get.ts` | Required for Fly healthcheck |
| `server/lib/upsert_contact.ts` | `~/zerg/zsend/server/lib/upsert_contact.ts` | Canonical contact-event payload |
| `Dockerfile` | `~/zerg/zsend/Dockerfile` | Has prod-deps stage (more optimal than zergboard's) |
| `fly.toml` | `~/zerg/zergboard/fly.toml` | Reference shape; bootstrap edits app name + port |
| `nuxt.config.ts` | `~/zerg/zergboard/nuxt.config.ts` | Has prepaint skin script + runtimeConfig pattern |
| `package.json` | `~/zerg/zergboard/package.json` | Pinned dep versions |
| `README.md` shape | `~/zerg/zergboard/README.md` | Canonical 7-section structure |
| Tracker composable | `~/zerg/web/src/composables/useAnalytics.ts` | The only place it's wired today; bootstrap inlines a copy |

---

## Vault references

| Artifact | Vault path |
|----------|------------|
| Positioning template anchor | `MattZerg/Projects/Zerg-Production/Zstack/Zergboard.md` |
| Pricing source of truth | `MattZerg/Projects/Zerg-Production/Zstack/Pricing-Snapshot.md` |
| One-pager checklist | `MattZerg/Projects/Zerg-Production/Zstack/ZergStack.checklist.md` |
| Integration narrative | `MattZerg/Projects/Zerg-Production/Zstack/Integration.md` |
| Voice anchor | `MattZerg/_style/voice_universals.md` |
| Competitive gold-standard folder | `MattZerg/Competitive/pm-software/` |

---

## Caveats

- **zergboard `server/lib/` does NOT exist on disk** as of 2026-05-07 — `signup.post.ts` imports from a path that's missing. The audit MUST flag this as a HIGH finding against zergboard itself. Bootstrap copies `server/lib/` from zsend, NOT zergboard.
- **zergboard's `--skin-*` presets** (terminal/light/ocean/amber) do NOT match the brand palette. They're for in-app theming. Marketing pages must use brand palette from `~/zerg/web/src/pages/index.vue`.
- **No `zstack.yaml` manifest exists** at `~/zerg/zstack.yaml` despite memory `project_zerg_monorepo_layout.md` claiming it does. There is a `~/zerg/zstack/` directory. Treat the memory entry as stale.
- **`web/` uses Djoser-style token auth** (`useAuth.ts`), not session cookies. That is the marketing-site auth, NOT a microproduct pattern. Don't copy from `web/` for new microproduct auth.
