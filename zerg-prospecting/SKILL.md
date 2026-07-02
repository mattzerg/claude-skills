---
name: zerg-prospecting
description: Build and score Durable-like Zerg Solutions prospect lists from public signals, enrich accounts with source notes, draft direct prospect outreach, and export qualified accounts into the Zerg Solutions pipeline. Use when Matt asks for target accounts, clients like Durable, non-network Solutions outbound, prospect scoring, or account research for AI SaaS/platform teams.
allowed-tools: Bash, Read, Write
---


# Zerg Prospecting Skill

Find, score, and package Durable-like Zerg Solutions prospects.

## Segments

Two target tracks, each its own curated file under `Growth/target-accounts/`:

- `durable-like` (default) — the original software track: AI SaaS / platform teams shaped like Durable. File: `durable-like.yaml`.
- `hardware-bcd` — **Series B/C/D hardware-oriented companies** (aerospace/defense/space, robotics & autonomy, industrial/manufacturing/deep-tech, connected devices/IoT). File: `hardware-bcd.yaml`. Reference pattern is **CesiumAstro**, not Durable.

Pass `--segment hardware-bcd` to `score` / `sendability` / `enrich` / `draft` / `export` to operate on the hardware track. Omit it for the software track. The hardware file is authored directly (not auto-seeded).

## Core Workflow

1. Start from the curated account file for the segment:
   `Growth/target-accounts/durable-like.yaml` (software) or `Growth/target-accounts/hardware-bcd.yaml` (hardware).
2. Run `score` to rank accounts by reference-pattern similarity, public trigger strength, urgency, and offer fit.
3. Run `sendability` to rank accounts by execution readiness: route quality, buyer specificity, trigger recency, message relevance, and company-size fit.
4. Run `enrich <company>` before drafting. Enrichment uses local notes plus source URLs already in the account file; add web research manually when a public claim is missing.
5. Run `draft <company>` only for accounts with score `70+` or an explicit user override.
6. Run `export <company>` to append a qualified account into `Growth/prospects.md`.

## Commands

```bash
python3 ~/.claude/skills/zerg-prospecting/run.py seed --segment durable-like
python3 ~/.claude/skills/zerg-prospecting/run.py score [--segment hardware-bcd] [--min-score 70]
python3 ~/.claude/skills/zerg-prospecting/run.py sendability [--segment hardware-bcd] [--min-score 60]
python3 ~/.claude/skills/zerg-prospecting/run.py enrich <company> [--segment hardware-bcd]
python3 ~/.claude/skills/zerg-prospecting/run.py draft <company> [--segment hardware-bcd]
python3 ~/.claude/skills/zerg-prospecting/run.py export <company> [--segment hardware-bcd] [--stage inbound|qualified|scoped|proposal-out|won|lost]
```

`--segment` defaults to `durable-like` (the software track); pass `hardware-bcd` for the hardware track.

## Scoring

Total score:

`durable_similarity * 35 + public_signal * 30 + urgency * 20 + offer_fit * 15`

Inputs are 1–5 integers. The script normalizes the weighted score to 100.

**`durable_similarity` is the reference-pattern dimension.** For the `durable-like` segment it means similarity to Durable. For the `hardware-bcd` segment it means **similarity to the CesiumAstro pattern**: a hardware/deep-tech company with complex internal software (program ops, supply chain/BOM, org/financials, manufacturing/test systems) that needs migration, cloud (often GovCloud), or modernization, plus agent integration into the engineering workflow. The field name stays `durable_similarity` for engine compatibility; score it against the segment's reference pattern.

Default drafting threshold: `70`.

Sendability score:

`route_quality * 30 + buyer_specificity * 25 + trigger_recency * 20 + message_relevance * 15 + company_size_fit * 10`

Use sendability to separate "good fit" from "actionable now." A high fit score with low sendability should stay in research until channel and buyer-route quality improve.

## Offer Angles

Software track (`durable-like`):

- `agent-ops-audit` — 1-week diagnostic for teams shipping agents into product, support, GTM, or internal ops.
- `zcloud-harness` — distributed subservices, runtime wrapper, orchestration, observability.
- `migration-sprint` — JS→TS, codebase modernization, autonomous migration, type coverage.
- `zergboard-rollout` — agent-native PM/workflow setup for 5–50 person teams running agents.
- `custom-solutions` — broader agent product/platform workstream.

Hardware track (`hardware-bcd`) — the wedge is "hardware optimization + software management / migration / efficiency":

- `hardware-software-migration` — modernize/migrate internal & product software: legacy → modern stack, cloud / GovCloud migration, JS→TS, type coverage, codebase modernization. (extends `migration-sprint`)
- `software-efficiency` — runtime/cloud cost + performance, orchestration, observability for the software hardware ops depend on. (extends `zcloud-harness`)
- `hardware-optimization` — software as the lever on hardware throughput/yield/test: manufacturing systems, test/validation tooling, telemetry/data pipelines, BOM/supply-chain optimization.
- `program-ops-platform` — CesiumAstro/Atlas pattern: program + supply-chain + org + financials ops software, plus agent integration into the engineering workflow.

## Trigger Types

Software track:

- `generated-app-platform` — AI app/website builders moving from demos to production customer surfaces.
- `agent-workflow-platform` — AI agents coordinating recurring workflows across internal tools.
- `customer-agent-platform` — support/voice/customer-facing agents with escalation, QA, and policy surfaces.
- `ai-dev-platform` — coding agents, PR agents, IDEs, and dev workflow products.
- `enterprise-ai-platform` — knowledge, orchestration, or internal AI platforms with governance needs.

Hardware track (`hardware-bcd`):

- `aerospace-defense-hardware` — aerospace, space, and defense hardware companies; often GovCloud / FedRAMP / CMMC, program ops, BOM/supply chain.
- `robotics-autonomy` — robotics, autonomous systems, fleet/telemetry software, motion-planning, test rigs.
- `industrial-deeptech-hardware` — advanced manufacturing, energy/climate hardware, semiconductors; MES/PLM/ERP, yield/test, data pipelines.
- `connected-device-iot` — connected devices, sensors, edge hardware adding software/data platforms and supply-chain visibility.

## Hardware ICP + buyer routes (`hardware-bcd`)

- **Stage:** Series B / C / D only (private, sub-$5B). Exclude seed/A, public, and mega-late.
- **Buyers:** VP Eng / CTO / Head of Software / Head of Manufacturing Systems (or MES/PLM) / Head of Program Management / Head of Platform-Infra. Not product/CX owners.
- **Positive signals (fit, not blockers):** security/compliance/GovCloud needs, ERP/MES/PLM sprawl, legacy internal tooling, telemetry/data-pipeline load, new factory / production scale-up, software-engineering job posts at a hardware company.
- **Higher ACV, longer cycle** than the software track — qualify for budget authority and a real internal-software pain, not just a funding headline.

## Safety

- Treat Durable as an internal pattern unless named customer clearance is explicitly present.
- Treat **CesiumAstro** as an internal reference pattern only — NDA is unverified. Never name CesiumAstro (or Andesite/Durable) in hardware outbound; use anonymized pattern language ("a venture-backed aerospace/defense company we support").
- Do not cite publish-blocked case-study details in outbound copy.
- Every draft must include one company-specific relevance line and one source URL.
- Network paths are optional bonus context, not a gate.
- Never auto-send email, LinkedIn, Slack, or SMS.

## Pairs With

- `network-reach` only after an account is already qualified by public-signal fit.
- `fakematt-email` before any external send.
- `utm-attribution` before adding live links.
- `bd-tracker` only for Product BD; this skill writes Solutions prospects.
