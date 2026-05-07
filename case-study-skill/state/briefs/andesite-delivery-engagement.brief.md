---
client: Andesite
project_slug: delivery-engagement
sector: cybersecurity
kind: delivery
timeframe_start: unknown
timeframe_end: ongoing
team: [Alex Liu, Idan Beck, Franklin]
products_used: [Metamorph harness, ZCloud, ZTC, Cybersec-Sim, Zergboard]
nda_status: unknown
nda_note: "Per Matt 2026-05-06: NDA gates publish, not drafting. Scaffolding allowed; do not publish without explicit clearance from client."
status: brief
created: 2026-05-06
---

# Andesite — case study brief

**Brief produced by:** case-study-skill capture
**Evidence sources scanned:** see Evidence links below

## Scope

Andesite is a cybersecurity vendor whose own product (Metamorph) generates connectors and agents for client security stacks. Zerg is building the harness layer that drives Metamorph's connector generation, plus a connector-report system that surfaces error "whys," a cybersecurity simulation rig, and ZCloud integration so Andesite can run generations against Zerg infrastructure (`MattZerg/Epoch/Projects/Client Pipeline.md`, `MattZerg/Epoch/Projects/Product Glossary.md`). The engagement is active with an August 2026 delivery deadline (`Client Pipeline.md`).

## Deliverables

- **Metamorph harness — connector generation suite** — in flight. Generates connectors/adapters for Andesite's Metamorph product. _(evidence: `MattZerg/Epoch/Projects/Product Glossary.md`)_
- **ThreatConnect connector** — manually tested against Metamorph; passed most tests; quality-pass changes underway; PR pending. _(evidence: `MattZerg/Conversations/Slack/standup/2026-04-20.md`, `2026-04-14.md`)_
- **Bitbucket adaptation** — successfully ran adaptation, generation converged, integrated into Metamorph, unit tests added, manual-test doc created. _(evidence: `2026-04-27.md`, `2026-04-28.md`)_
- **Axiom connector report system** — connector report runs full test suite in one go and writes results as a markdown doc; tests query Metamorph chat API and capture pass/fail per query; format/coverage iterations in progress. _(evidence: `2026-04-24.md`, `2026-04-28.md`)_
- **Connector report "whys"** — in flight; investigating dynamic generation of error rationales inside the report. _(evidence: `2026-04-28.md`)_
- **emailrep PR** — opened on Andesite shared channel. _(evidence: `2026-04-07.md`)_
- **EPO-324 three-layer refactor + EPO-609 / EPO-610 / EPO-684** — in flight Linear work referenced in standups; details not in evidence. _(evidence: `2026-04-07.md`, `2026-04-14.md`, `2026-04-22.md`, `2026-04-27.md`)_
- **Cybersec-Sim** — demo with Alex (Andesite) on 2026-05-01; landed well per Idan; positioned to "drive" the Metamorph product via simulation. _(evidence: `MattZerg/Epoch/Projects/Product Glossary.md`, `2026-04-24.md`)_
- **Local ZCloud harness changes** — being adjusted so Andesite can run generations on it directly. _(evidence: `2026-04-14.md`)_

## Outcomes

No measurable outcomes documented in evidence. **Gap:** customer-side metrics (connectors shipped to production, error-rate deltas on connector reports, hours saved per connector vs. prior tooling, harness generation success rate, time-from-spec-to-deployed-connector) are needed before this case study can scaffold. Idan's 2026-04-24 note that there is "a shortening runway on pure generation of new connectors" implies validation pressure but is not a metric.

## Candidate quotes

No verbatim quotes in evidence. **Gap:** ask Alex Liu (primary Zerg owner) to relay an Andesite-side quote, or arrange a direct ask of the Andesite engineering counterpart who attended the 2026-04-28 weekly sync ("they seem excited for the connector report ZCV stuff"). Topic should cover either (a) connector report value or (b) harness-driven generation cadence.

## Evidence links

- `MattZerg/Epoch/Projects/Client Pipeline.md` — engagement status, August deadline, named scope (harness, connector reports with "whys", bitbucket, ZCloud), Alex Liu as primary owner.
- `MattZerg/Epoch/Projects/Product Glossary.md` — Metamorph definition, ThreatConnect/Bitbucket/Axiom subprojects, Cybersec-Sim attribution.
- `MattZerg/Conversations/Slack/standup/2026-04-07.md` through `2026-04-28.md` — week-by-week deliverable status from Alex Liu and Idan; weekly Andesite syncs; April 28 sync went well per Alex.
- `MattZerg/Roadmap/2026-05-03-zergboard-roadmap.md` — references Andesite as a production Zergboard user (alongside CesiumAstro) but does not detail Zergboard usage there.
- `MattZerg/Projects/Zstack/ZergStack.one-pager.md` — marketing claim that Andesite "runs their teams and their agents on it today" via Zergboard. Marketing copy; flag confidence.
- `MattZerg/Projects/Zstack/Case-Studies/andesite.md` — prior capture-stub noting Andesite as "the most-referenced Zerg Solutions client (60+ production cards on Zergboard per memory)" and target publish Day 30.
- `MattZerg/Projects/Zstack/Growth/weekly/2026-05-05.md`, `2026-05-06.md` — andesite case-study-in-flight tracker, status=capture, nda=unverified.

## Gaps

- **Linear pulls not done by script.** Run: `linear-skill search "andesite"` and pull EPO-324, EPO-609, EPO-610, EPO-645, EPO-647, EPO-684 directly to surface scope, ship status, and dates. Expect HIGH confidence on shipped issues, MEDIUM on in-progress.
- **Zergboard pulls not done by script.** Run: `zergboard-skill search "andesite"`. Prior capture-stub claims 60+ production cards — confirm and pull card titles/scope to enrich Deliverables.
- **GitHub PR pulls.** PRs referenced (emailrep, EPO-609/610 bundle, EPO-324, ZAAI code review) not retrieved; pulling shipped PR titles + merge dates would let several deliverables move to confidence HIGH.
- **No customer-side baseline.** Need from Alex Liu or Andesite counterpart: connector volume before/after harness-driven generation; error rates on Axiom connector reports; engineer hours per connector under prior workflow. Without baselines, every potential outcome is LOW.
- **No verbatim quote.** See Candidate quotes; ask Alex to broker.
- **No engagement start date.** Evidence shows active April 2026; engagement clearly began earlier. Pull from Companies/Andesite.md, Linear creation dates, or earliest #andesite Slack history.
- **Cybersec-Sim status post-May 1 demo.** Demo happened; no follow-up evidence in scanned set. Pull May 2026 standups + Idan messages.
- **August 2026 deadline scope.** Client Pipeline names the deadline but does not specify what ships by August. Confirm with Alex Liu / Idan.
- **Zergboard usage at Andesite.** Roadmap doc + ZergStack one-pager both claim Andesite uses Zergboard in production; no engagement-level evidence in scanned set. Pull Zergboard analytics or org membership to confirm before claiming.
- **Companies/Andesite.md and any People/CRM/ entries for Andesite contacts** were not in the scanned snippets. Pull to confirm sector classification (cybersecurity), funding/stage context, and named champion.

## Risks

- **NDA status: restricted.** Per calibrated rule, Andesite Metamorph codebase is explicitly NDA. The Metamorph harness, connector source (ThreatConnect, Bitbucket, Axiom), and connector report internals cannot be surfaced in published copy. Cybersec-Sim and ZCloud integration may have separate NDA scoping; verify before publication. NDA clearance must be cleared in writing by Andesite legal before `nda_status` flips to `cleared`.
- **Sensitive sector.** Cybersecurity client + connectors to security-vendor systems (ThreatConnect, Axiom) raise the bar on what specifics are publishable; expect named-tool references to be redacted or generalized in any client-approved draft.
- **In-flight engagement.** August 2026 deadline implies the case study would publish on a moving target. Frame outcomes as in-progress or "as of <date>", not as a finished win.
- **No customer signoff in evidence.** Champion identification needed before any draft circulates.
- **Attribution ambiguity.** Cybersec-Sim is co-attributed to Idan + Andesite; unclear whether it is a Zerg deliverable, a joint research artifact, or an Andesite-internal project. Clarify before claiming as a delivery item.

## Notes for scaffold

- This engagement is mid-flight with an August 2026 milestone. Frame as in-progress delivery, not as a finished win. Default headline pattern A ("Andesite: <verb-led specific outcome> with Zerg") will need to wait for a metric; pattern B ("Andesite drives Metamorph connector generation with Zerg's harness") is defensible from current evidence.
- Default the approach to the 3-phase delivery shape: Discovery → Build → Operate. Build phase is where the Metamorph harness, ThreatConnect, Bitbucket adaptation, and connector reports live; Operate is the harness-driven generation Andesite is increasingly running themselves.
- The strongest borrowable corpus moves for this brief: **Stack-used sidebar (Stripe × Notion)** listing Metamorph harness / ZCloud / ZTC / Cybersec-Sim; **Equivalent-workload framing (OpenAI × Klarna)** once a baseline exists for connector authoring time; **Indexed-sources sidebar (Glean × Reddit)** as a variant listing the security tools Metamorph generates connectors for (ThreatConnect, Bitbucket, Axiom) — but only if NDA permits naming them publicly.
- Do **not** name Zerg engineers (Alex Liu, André, Franklin) in the published case study body or about-customer sidebar per the project-owner discipline rule. They appear here in `team` for internal sourcing only.
- Architecture diagram (Block 7) is mandatory for `kind: delivery` — but only if NDA clears the harness → Metamorph → connector report shape. If NDA blocks, swap for an abstracted "harness generation pipeline" diagram with no client-system names.
- The case study cannot scaffold until at least one of: (a) a verbatim Andesite quote, (b) one outcome metric with a baseline, (c) NDA cleared in writing. The capture-stub at `MattZerg/Projects/Zstack/Case-Studies/andesite.md` flags the same: clearance gate is Day 12–18 of the publish plan.