---
name: zstack-product
description: Bootstrap or audit a Zstack microproduct (Zergboard/ZergSend/ZergCal/ZergMail/etc.) against the canonical pattern catalog extracted from existing products. Two modes — `bootstrap <slug>` scaffolds a new product end-to-end (code repo at `~/zerg/<slug>/` + vault note at `MattZerg/Projects/Zerg-Production/Zstack/<Product>.md` + competitive folder at `MattZerg/Competitive/<category>/`); `audit <slug>` checks an existing product for drift against canonical patterns and emits severity-tagged findings (HIGH/MED/LOW) with cited rule + concrete fix recipe. Hybrid sourcing — frozen rules in `canonical-patterns.md`, live snippets pulled from reference products at runtime. USE PROACTIVELY when Matt mentions starting a new Zstack microproduct, asks "what's the pattern for X", or before any new product ships. Never auto-fixes — outputs findings + scaffolds files only.
---


# zstack-product

Two modes:

## bootstrap

```
python3 ~/.claude/skills/zstack-product/bootstrap.py <slug> --category <competitive-category> [--port <N>]
```

Scaffolds:
- `~/zerg/<slug>/` — Nuxt 3.17.2 + TS code repo cloned from canonical references (zergboard for `db/`, signup flow, README; zsend for `server/lib/` and Dockerfile shape)
- `MattZerg/Projects/Zerg-Production/Zstack/<Product>.md` — positioning template with all 4 pillars + Free/$1/$9/Enterprise pricing
- `MattZerg/Competitive/<category>/` — 8-file folder (creates if missing, augments if exists)
- Pre-wires the gaps the audit catches: ZergAlytics tracker embed, `upsert_contact` call from signup, lifecycle-email trigger stub

## audit

```
python3 ~/.claude/skills/zstack-product/audit.py <slug> [--tier <tier>] [--reconcile-prs]
```

Severity-tagged findings:
- **HIGH** — ships-blocking drift (missing tracker, orphaned signup events, wrong Fly org, divergent auth)
- **MED** — pattern drift that should be fixed soon (free-tier cap unstated, brand color drift, README missing sections)
- **LOW** — product-specific divergence (added deps, optional patterns)

Each finding cites the rule from `canonical-patterns.md` or `anti-patterns.md` + a concrete fix recipe with file path + diff hint.

**Flags:**
- `--tier {nuxt,fastapi,tauri,auto}` — auto-detect from package.json/main.py by default. Non-Nuxt tiers skip Nuxt-specific rules so FastAPI products like zmail/zmsg don't false-positive as 8 HIGH.
- `--reconcile-prs` — cross-references open PRs in `Epoch-ML/zerg` via `gh` CLI. Findings whose target file is already touched by an open PR get downgraded one severity (HIGH → MED) and annotated `(addressed in PR #N)`. Closes the gap documented in `feedback_audit_misses_in_flight_prs.md`.

## Reference docs

- `canonical-patterns.md` — frozen rules (the WHAT)
- `reference-products.md` — live snippet pointers (the HOW)
- `anti-patterns.md` — drift catalog from cross-product exploration
- `port-registry.md` — cross-product port allocation
- `free-tier-cap-matrix.md` — standardized cap table per product
- `new-product-playbook.md` — the launch playbook the vault is missing

## Verification

1. `audit zergboard` flags ≥3 HIGH findings (tracker, upsert_contact, app-switcher)
2. `audit zsend` flags missing tracker
3. `audit zergwallet` flags Fly org `personal` ≠ `epoch-ai-in`
4. `bootstrap zcrm-test --category crm` produces a runnable Nuxt scaffold; immediate re-audit returns ZERO HIGH findings

## Stacks with

- `pr-gate` — catches drift before PR opens
- `competitive-review-skill` — fills the 8-file competitive folder content
- `landing-page-skill` — generates marketing page using same canonical brand palette
- `launch-announcement` — drafts the launch post using positioning fields the bootstrap fills
- `one-pager-skill` — uses the positioning doc the bootstrap creates
- `funnel-analyzer` — once tracker is wired (audit A1 fix), funnel-analyzer can query measured drop-off per product
- `ux-flow-mapper` — maps multi-screen onboarding flow for the new product (pairs with funnel-analyzer)
- `content-calendar` — queues launch announcement + post-launch content as editorial pieces with dates
