---
name: process-streamliner
description: Audit a repeated workflow, find bottlenecks and manual waste, then redesign it into a cleaner operating process with SOPs, automation opportunities, tool choices, and rollout sequencing. Use for internal ops, onboarding, delivery workflows, marketing operations, handoffs, and recurring team processes.
---


# Process Streamliner

This skill turns a messy recurring workflow into an explicit operating system. It is for the point where people are repeating steps, handing work across tools, and patching over drift with memory.

## When to invoke

- "This process is messy"
- "How should we streamline onboarding / delivery / support / launch ops?"
- "Map this workflow and tell me what to automate"
- "Turn this set of notes into an SOP"
- When Matt has scattered docs, Loom notes, spreadsheets, or bullets describing how work currently happens

Use it for internal operations, client delivery, go-to-market workflows, support queues, recruiting pipelines, and recurring product/marketing handoffs.

## Core outputs

Pick the smallest output that solves the ask. Default shapes:

1. **Process map** — actors, systems, inputs, outputs, dependencies, failure points
2. **Bottleneck audit** — manual work, duplicated work, missing ownership, fragile steps, latency
3. **Redesigned process** — cleaner target-state workflow with explicit decision points
4. **Automation brief** — what to automate, with what trigger, where human review stays
5. **SOP pack** — operator checklist, owner cadence, handoff rules, exceptions

## Modes

### Mode 1 — Audit

Use when the current process exists but is inefficient.

Output:
- current-state map
- failure and drag points
- ranked intervention list

### Mode 2 — Redesign

Use when the user wants the future-state operating model.

Output:
- target-state flow
- role ownership
- tool/system boundaries
- transition plan

### Mode 3 — SOP / Handoff

Use when the process mostly exists and needs operational clarity.

Output:
- step-by-step SOP
- handoff checklist
- edge cases / escalation rules

## Anchors

- `references/process_patterns.md`
- local roadmap, launch, delivery, and meeting docs the user points at
- adjacent skills when relevant:
  - `fakematt-launch` for launch-package workflows
  - `utm-attribution` for UTM publishing discipline
  - `landing-page-skill` when the workflow includes page iteration

Read only what the task needs. Keep the skill lean.

## Working rules

- Start by naming the **unit of work** clearly: what enters the process, what exits it, and what “done” means.
- Name the **source of truth** for status. If the process spans docs, sheets, Slack, and product state, say which one actually governs the state machine.
- Separate **human judgment** from **mechanical execution**. Only automate the latter unless the user explicitly wants decision support.
- Treat handoffs as first-class failure points. Missing ownership and ambiguous state changes are usually more expensive than tool friction.
- Optimize for **clear operating rhythm**, not just fewer steps.
- Prefer explicit checklists, templates, and triggers over “remember to.”
- Use status labels when the process mixes shipped, blocked, and aspirational work. `live` / `to-build` / `blocked` is better than prose ambiguity.
- When the process touches customers or regulated work, preserve review gates instead of flattening them blindly.

## Hard rules

- Do not pretend a process is fixed by naming a tool. Tool choice is downstream of workflow shape.
- Do not remove human approval on high-stakes steps without calling it out explicitly.
- Do not write giant theoretical frameworks when a checklist, map, or automation brief would do.

## Relationship to sibling skills

- `fakematt-launch` — use when the process is specifically a launch package / rollout
- `fakematt-feedback` — use when the broken process is actually a product UX issue
- `ui-designer` — use when the output should become an interface rather than an SOP
