# New Product Playbook — Zstack Microproducts

The vault was missing this. Skill ships it. Use as the canonical sequence.

## Canonical entrypoint (preferred)

As of 2026-05-28, the canonical way to bootstrap a new product is:

    ~/zerg/_templates/scripts/zerg-new-product.sh <slug>

This script wraps the manual steps below: copies templates, substitutes tokens,
patches the API allowlist, creates the Fly app, registers with Zergalytics,
scaffolds the Growth/ entries, and registers with zpub.

The manual playbook below remains as a fallback when the script can't be used
(e.g., partial bootstrap, recovery, learning the underlying pattern).

## Phase 0: Decide

Before any code or vault note:

1. **Category** — does an existing `MattZerg/Competitive/<category>/` folder exist? If not, create one + run `competitive-review-skill` to populate.
2. **ICP** — who buys this? 1 sentence.
3. **Hook** — 1 line that captures why anyone cares.
4. **Free-tier cap** — declare before signup ships.
5. **Positioning vs existing products** — does this overlap with Zergboard / ZergChat / etc.? If yes, what's the wedge?

## Phase 1: Bootstrap

```
python3 ~/.claude/skills/zstack-product/bootstrap.py <slug> --category <category>
```

Produces:
- `~/zerg/<slug>/` — Nuxt 3 + TS scaffold
- `MattZerg/Projects/Zerg-Production/Zstack/<Product>.md` — positioning template
- `MattZerg/Competitive/<category>/` — 8-file folder (if missing)

## Phase 2: Pre-launch

1. **Positioning** — fill the positioning doc; run `fakematt-copyedit` against it
2. **Competitive** — run `competitive-review-skill` on the category
3. **Landing page** — run `landing-page-skill` against the category folder
4. **One-pager** — run `one-pager-skill product` variant
5. **Tracker wiring** — verify `useAnalytics` fires on signup + key CTAs
6. **upsert_contact** — verify zsend dev sees `account_created` events from local signup

## Phase 3: Launch

1. **Launch announcement** — run `launch-announcement scaffold` from positioning doc
2. **Distribution** — once blog post lives, run `content-distribution` to file 14-surface checklist
3. **Audit pre-flight** — `audit <slug>` returns ZERO HIGH findings
4. **PR-gate** — open PR; pr-gate skill runs fakematt-* + fakeidan
5. **Fly deploy** — `flyctl deploy -a <slug>` (verify org = `epoch-ai-in`)

## Phase 4: Post-launch

1. **growth-dashboard** — verify product appears in Monday 7am dashboard with non-zero events
2. **lifecycle-email** — wire welcome drip via `email-drip` skill
3. **referral-tracker** — invitation flow ships in Pro tier (Phase 2 build)
4. **Bundle** — once 2+ products both have pro tier, list bundle SKU on pricing page

## Phase 5: Sustain

- Monthly: re-run `audit <slug>` to catch drift
- Quarterly: refresh `canonical-patterns.md` dep pins against current package.json
- Whenever a reference product changes pattern: update reference-products.md + audit findings

## Decision log slot

Record decisions Matt made about THIS product (per-seat vs per-agent, OAuth providers, integration priorities) in `MattZerg/Projects/Zerg-Production/Zstack/<Product>.decisions.md`. Audit doesn't enforce this file — it's for future you, not the system.
