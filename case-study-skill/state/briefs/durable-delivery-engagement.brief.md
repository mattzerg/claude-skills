---
client: Durable
project_slug: delivery-engagement
sector: enterprise-software
kind: delivery
timeframe_start: unknown
timeframe_end: ongoing
team: [André Ricardo]
products_used: [ZCloud, ZTC]
nda_status: unknown
status: brief
created: 2026-05-06
---

# Durable — case study brief

**Brief produced by:** case-study-skill capture
**Evidence sources scanned:** see Evidence links below

## Scope

Zerg is building a cloud harness that orchestrates Durable's v2 platform via Zerg modules, including a probe/watcher system to surface subservice errors. _(evidence: `MattZerg/Epoch/Projects/Client Pipeline.md`)_ The engagement is mid-flight: as of mid-April 2026, André Ricardo had achieved full module-level orchestration of Durable v2 through Zerg cloud, with probe wiring still in iteration. _(evidence: `MattZerg/Conversations/Slack/standup/2026-04-15.md`, `MattZerg/Conversations/Slack/standup/2026-04-28.md`)_

## Deliverables

- **Durable v2 cloud harness** — in flight. André reports "fully orchestrated their v2 through modules" via Zerg cloud as of 2026-04-15. _(evidence: `MattZerg/Conversations/Slack/standup/2026-04-15.md`)_
- **Probe/watcher system** — in flight. Intended to bubble up subservice errors; probes "still not hitting" as of 2026-04-28; console logs surfacing correctly in the Zerg module tab. _(evidence: `MattZerg/Conversations/Slack/standup/2026-04-28.md`, `MattZerg/Epoch/Projects/Client Pipeline.md`)_
- **Module-level overseer logic** — planned next. André's stated next step after orchestration: "creating some logic to make it a good overseer." _(evidence: `MattZerg/Conversations/Slack/standup/2026-04-15.md`)_

## Outcomes

No measurable outcomes documented in evidence. Gap: customer-side metrics (deploy cadence, error-triage time, orchestration scope) needed before case study can scaffold. The only quantitative claim in evidence is the Fly.io deploy improvement ("2 minutes tops" from first click to fully setup app), which is adjacent to but not part of the Durable engagement. _(evidence: `MattZerg/Conversations/Slack/standup/2026-04-28.md`)_

## Candidate quotes

No verbatim quotes in evidence. Gap: ask Durable champion (name unknown — needs identification per `MattZerg/Projects/Zstack/Case-Studies/durable.md`) for a 1-2 sentence quote covering what the Zerg module orchestration of Durable v2 unlocked. André Ricardo's standup notes are internal Zerg voice, not publishable customer testimony.

## Evidence links

- `MattZerg/Epoch/Projects/Client Pipeline.md` — top-level pipeline entry naming Durable status, scope, owner, and next steps
- `MattZerg/Conversations/Slack/standup/2026-04-15.md` — André's standup confirming full v2 orchestration through Zerg modules
- `MattZerg/Conversations/Slack/standup/2026-04-28.md` — André's update on probe wiring still iterating, console logs working
- `MattZerg/Conversations/Slack/standup/2026-04-13.md` — Idan note: "follow up with Rubrik and Durable" (light signal of ongoing engagement cadence)
- `MattZerg/Projects/Zstack/Case-Studies/durable.md` — capture-mode placeholder noting NDA unverified and clearance still required
- `MattZerg/Projects/Zstack/Growth/weekly/2026-05-05.md`, `weekly/2026-05-06.md` — case-study-in-flight tracker confirming status=capture, nda=unverified
- `MattZerg/Projects/Zstack/Growth/utm-convention.md` — pre-allocated `case-study-durable` UTM slug
- `MattZerg/Projects/Zstack/Growth/journeys/solutions-buyer.md` — case study referenced as a planned inbound trigger

## Gaps

- **Linear pulls not done by script.** Run: `linear-skill search "durable"` and `linear-skill search "v2 harness"` to surface in-flight issues for the harness build, probe system, and overseer logic. Expect MEDIUM confidence on in-progress, HIGH on shipped.
- **Zergboard pulls not done by script.** Run: `zergboard-skill search "durable"` to surface card-level scope and status.
- **No Companies/Durable.md captured.** Per `MattZerg/Projects/Zstack/Case-Studies/durable.md`, this file may exist but was not surfaced by evidence gathering. Confirm presence; if absent, identify Durable as a company (sector, size, product) before drafting.
- **No People/CRM contacts surfaced.** No Durable champion or legal contact named in evidence. Required for NDA clearance and quote capture.
- **No timeframe start.** Engagement clearly active by 2026-04-13 but start date not in evidence. Ask André or check Linear ticket creation dates.
- **No measurable outcomes.** Need: orchestration scope (how many subservices, what error volume), probe-system error-triage delta, deploy/operate cadence change vs. prior tooling. Without baselines, current evidence supports zero HIGH-confidence outcomes.
- **Product Glossary check pending.** "Zerg cloud" / "Zerg modules" / "harness" / "probes" / "watcher" appear in evidence — verify these resolve to canonical Glossary entries (likely ZCloud + ZTC modules) or flag as Glossary gaps.
- **No customer-side voice.** Every evidence source is internal (André standups, Idan notes, Matt's pipeline doc, Matt's growth tracker). Need at least one inbound from Durable side — Slack DM, email, signed proposal — to anchor the case study in customer reality.

## Risks

- **NDA status: unknown.** `MattZerg/Projects/Zstack/Case-Studies/durable.md` explicitly notes "NDA: unverified — clearance needed Day 12–18." Cannot publish until cleared. The growth weekly trackers also flag `nda=unverified`.
- **Mid-flight engagement.** Probe system was not working as of 2026-04-28; the harness story is not yet a "shipped" story. Frame as in-progress at minimum, or wait until probes land + overseer logic ships before drafting.
- **Single-Zerg-source evidence.** All technical claims trace to André Ricardo's standup notes. No second corroborating source within Zerg, no customer-side artifact. MEDIUM at best on technical detail until Linear/Zergboard pulls add corroboration.
- **Product naming ambiguity.** "Zerg cloud" in standups vs. "ZCloud" in canonical naming — verify Product Glossary alignment before any draft uses product names.
- **Unverified Durable identity.** Brief assumes Durable is a B2B SaaS per `Case-Studies/durable.md` capture note ("Strong B2B SaaS adjacency story"), but no Companies/Durable.md or product description surfaced. Sector classification is best-guess.

## Notes for scaffold

- This brief is **not yet draftable**. Three blockers: NDA unverified, no customer-side voice, no measurable outcomes. Scaffold should refuse to draft and instead emit a "what to capture next" checklist.
- When draftable, lead with the orchestration shape — "Zerg modules orchestrate Durable v2 in cloud" — not with a metric, since metrics are missing. Frame as in-progress engagement (Thoughtworks × Mercado Libre era-by-era model is a closer fit than Stripe × Notion shipped-story model, but trimmed to one phase since this is single-quarter visible scope).
- Once probes land + first measurable outcome lands, the strongest framing candidate is **error-triage time delta** ("subservice errors that previously surfaced as silent failures now bubble up via Zerg's probe/watcher system in [X]") — pending baseline capture.
- Stack-used sidebar should list ZCloud + ZTC at minimum once Glossary alignment is confirmed; do not name "Zerg modules" or "harness" as products without Glossary precedent.
- Owner field in about-customer sidebar must omit André per genre rule; body prose can reference "a small dedicated Zerg team" without naming.