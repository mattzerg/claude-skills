---
name: linkedin-sales-nav
description: Sales Navigator-specific extension to linkedin-skill. Real prospect filters (geography, headcount, industry, seniority, function, recent-job-change, decision-maker) that the public LinkedIn API can't reach. Backed by Playwright + Matt's logged-in SN session (sibling to instagram-skill / playwright-skill). Verbs — `search <SN-URL-or-filter-spec>` (returns candidate list with title/company/profile-url), `account-search <filters>` (companies, not people), `export <result-set>` (drops to MattZerg/Projects/Zerg-Production/Growth/prospects/). **Requires active Sales Navigator seat — Matt must purchase first.**
---

# linkedin-sales-nav

Sales Navigator filters via authenticated browser session. Built on top of the existing `linkedin-skill` browser context.

## Status

**SCAFFOLD ONLY — blocked on Sales Navigator seat purchase by Matt.** The implementation pattern is clear (Playwright + reuse `linkedin-skill/tokens/` session), but no script ships until the seat is active and we can authenticate against `linkedin.com/sales/`.

Once seat is active, plan is:

1. Add `linkedin.com/sales/` to the existing Playwright persistent context used by `linkedin-skill`.
2. Implement `lead-search` verb — accepts either (a) a raw SN search URL or (b) a structured filter spec (geography, headcount, industry, seniority, recent-job-change, etc.); returns top-25 results.
3. Implement `account-search` verb — same shape but for accounts (companies), feeds `zerg-prospecting`.
4. Implement `export` verb — writes a versioned `.md` file to `MattZerg/Projects/Zerg-Production/Growth/prospects/` with frontmatter Claude can re-read.
5. Wire `zerg-prospecting` skill to call this for "non-network Solutions outbound" prompts.

## When to use (post-implementation)

- `zerg-prospecting` for Durable-like accounts — currently constrained to public signals; SN filters unlock the 10x ICP refinement.
- BD list building for specific verticals or funding stages.
- Re-engagement of contacts who've recently changed jobs (SN's killer filter).

## Reference

- Sibling pattern: `~/.claude/skills/instagram-skill/` (Playwright + persistent context).
- Outreach drafting handoff: `fakematt-email` for cold-email register.
- Vault dest: `MattZerg/Projects/Zerg-Production/Growth/prospects/`.
- Memory: `feedback_no_outreach_to_vang_capital_portfolio.md` — even with SN filters, never directly outreach Vang Capital portfolio companies.

## Do not invoke

Until Matt confirms seat is active. The skill description exists so the capability is discoverable in skill listings.
