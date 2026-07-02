---
name: launch-ops
description: Turn a launch from scattered drafts and tasks into an executable rollout plan with blockers, owners, source-of-truth artifacts, channel sequence, measurement readiness, and day-of operations. Use for product launches, feature launches, pricing changes, waitlist launches, and coordinated distribution pushes.
---


# Launch Ops

This skill owns the operational layer of a launch. It is not the announcement post and it is not the social copy. It is the execution system that makes the launch actually fire in the right order with the right dependencies resolved.

## Verbs (run.py)

The deterministic gate set is script-driven via `~/.claude/skills/launch-ops/run.py`. The human-in-loop Modes 1/2/3 below still exist for readiness audits, rollout plans, and slip/recovery work — the script handles the rule-bound pass/fail gates that the launch-pack runner consumes at Step 8.

- `python3 ~/.claude/skills/launch-ops/run.py check <slug>` — run all 10 gates against the slug. Exit 0 = all PASS, exit 1 = any HIGH unresolved, exit 2 = missing required inputs (brief, measurement YAML, or measurement checklist). Accepts `--json` for machine-readable output (used by `launch-pack.py` Step 8) and `--product <slug>` as an alias for the positional slug arg.
- `python3 ~/.claude/skills/launch-ops/run.py list` — enumerate all gates with severity + source (canonical-patterns.md §16/§17 or launch_distribution_playbook.md gates 11–17).

Inputs the script reads:
- `Growth/launches/<slug>.md` — HARD-fail if missing (exit 2)
- `Growth/measurement/<slug>.yaml` — HARD-fail if missing (exit 2)
- `Growth/measurement/<slug>.checklist.md` — HARD-fail if missing (exit 2)
- `Growth/launches/<slug>/{announcement,distribution,assets/,social/}` — optional; gates that depend on these emit MED with `not yet produced by launch-pack` when absent
- `~/zerg/<slug>/docs/` — read via subprocess to `product-docs-skill audit <slug>` (G1)
- Zergalytics `GET /api/v1/stats/<event>?days=1` for kill_readiness verification (G3); auth via Keychain (`security find-generic-password -a matt -s ZERGLYTICS_API_KEY -w`); network failure emits MED, not HIGH

Pre-launch handling: when `measurement.launch_phase=pre-launch`, G3 is informational (MED) — it'll block at the `launch_phase=shipped` transition once prod traffic exists.

## When to invoke

- "What is still blocking this launch?"
- "Turn these launch notes into an executable plan"
- "Who owns what and what is the day-of sequence?"
- "Audit our launch readiness"
- Before any coordinated product launch, feature launch, pricing rollout, or campaign push

Use it when the launch already has copy and assets in motion, but the operational state is fragmented across docs, PRs, infra, checklists, and reminders.

## Core outputs

1. **Launch readiness audit** — blockers, risks, missing assets, unresolved decisions
2. **Source-of-truth map** — which file/system governs date, publish state, domain state, attribution state, and comms state
3. **Owner matrix** — workstream, owner, dependency, detection rule
4. **Fire plan** — pre-launch, day-of, and post-launch sequence
5. **Recovery plan** — what to do if launch slips, a dependency breaks, or measurement is blind

## Modes

### Mode 1 — Readiness audit

Use when the team has many pieces but unclear confidence.

Output:
- blocker list
- dependency map
- launch/no-launch recommendation

### Mode 2 — Rollout plan

Use when the launch is real and needs a concrete operating sequence.

Output:
- workstreams
- owners
- day-of runbook
- fallback rules

### Mode 3 — Slip / recovery

Use when the launch date, publish state, or infra state is unstable.

Output:
- what moves
- what stays valid
- what must be regenerated
- what communication changes

## Anchors

- `references/launch_ops_patterns.md`
- `MattZerg/_style/launch_distribution_playbook.md` — **post-publish operating playbook (T+0 through T+30 cadence + 17-surface distribution checklist)**. Required reading for any readiness audit since 2026-05-27.
- `MattZerg/_style/launch_announcement_style.md` — pre-publish structural + distribution-readiness checklist (gates 1–17).
- `fakematt-launch` for message and asset package
- `launch-announcement` for blog-post structure
- `utm-attribution` for tracked links
- `content-distribution` for 17-surface variant generation + Day-2 quote-post wave coordination
- `growth-dashboard` for measurement destination
- `process-streamliner` when the launch process itself should become a standing SOP

## Working rules

- Name the **source of truth** for launch date, publish state, domain/DNS state, tracking state, and distribution state.
- Separate **blocked**, **ready**, **to-fire**, and **done** states clearly.
- Treat unresolved measurement as a blocker when the launch depends on attribution or activation learning.
- Keep launch-day actions manual unless the user explicitly wants automation.
- Surface dependencies that are easy to miss: DNS, CTA destinations, event logging, reply-to addresses, allowlists, secrets, and owners.
- Distinguish between **content complete** and **launch ready**. Those are not the same state.

## Pre-ship gates (HIGH severity)

In addition to gates 1–17 from `launch_announcement_style.md` and `launch_distribution_playbook.md`, every launch must clear these three product-readiness gates:

- **`product-docs-present` (HIGH, cite canonical-patterns.md §17)** — `product-docs-skill audit <slug>` returns 0 HIGH findings. Clears via `python3 ~/.claude/skills/product-docs-skill/run.py audit <slug>`. Consults `~/zerg/<slug>/docs/` against the 7-file canonical shape. Resolve HIGH findings (missing README, missing canonical H2 sections, missing sibling files, dead internal links) before declaring launch-ready.
- **`measurement-spec-present` (HIGH, cite canonical-patterns.md §16)** — `MattZerg/Projects/Zerg-Production/Growth/measurement/<slug>.yaml` exists and parses as valid YAML; the companion `MattZerg/Projects/Zerg-Production/Growth/measurement/<slug>.checklist.md` exists and has 0 unchecked boxes. Clears by completing measurement spec + checklist with the product owner. No measurement spec = no launch — a launch without an instrumented funnel is a measurement-blind launch.
- **`kill_readiness_gate green` (HIGH, cite canonical-patterns.md §16)** — In `measurement/<slug>.yaml`, every event under `kill_readiness_gate.must_emit_in_prod` has ≥1 occurrence in the last 24h of prod traffic per Zergalytics. Phase 3 wiring of `growth-dashboard` automates the check; until then, this is a **manual verify** placeholder — confirm by checking Zergalytics dashboards or running a HogQL spot-check before clearing.

## Hard rules

- Do not collapse a launch into a generic checklist when multiple hidden sources of truth exist.
- Do not let aspirational channels sit in the same state bucket as ready-to-fire ones.
- Do not assume the launch date is stable unless a specific artifact or config is named as the governing source.
- Do not call a launch ready if the measurement path or CTA path is broken.
- Do not call a launch ready if `launch_distribution_playbook.md` gates 11–17 fail (quote engineering, waitlist-share CTA, UTM-instrumented links, quote-post wave plan, asset format match, reposter DMs drafted, cadence calendar entry). Content complete ≠ launch ready — Gigacontext Threshold (2026-05-21) passed structurally and failed distribution; the playbook now blocks that recurrence.
- Do not call a launch ready if any of `product-docs-present`, `measurement-spec-present`, or `kill_readiness_gate green` fails. Product-readiness is independent of content-readiness — both must clear.

## Relationship to sibling skills

- `fakematt-launch` — copy and asset package
- `launch-announcement` — structural quality of the launch post
- `process-streamliner` — convert the launch workflow into a reusable operating process
- `cro-auditor` — conversion readiness of the pages and signup funnel the launch points at
