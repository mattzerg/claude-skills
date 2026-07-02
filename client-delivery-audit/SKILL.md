---
name: client-delivery-audit
description: Run a rigorous, evidence-backed audit of a client-facing app before delivery/handoff, producing a severity-ranked FINDINGS report with proof per finding, coverage matrix, adversarial verification, and re-verification of prior findings. Two lanes — functionality (math/behavior correctness against DB/API/source, Michael Chen's pattern) and ux (persona/task usability with the same rigor). Use whenever Matt says "client delivery audit", "pre-delivery audit", "audit X before handoff", "functionality audit", "UX audit of <client app>", "run Michael's audit pattern", "re-verify findings", "re-run the audit", or is preparing ANY feedback round on a client deliverable (Cesium Astro / ca-org, Andesite, or any Zerg Solutions engagement app). Also use when Matt is about to post feedback to a client-internal Slack channel — this skill produces the report that feedback should come from. Never auto-posts; output is local + a draft message.
---

# Client-Delivery Audit

## Overview

Operationalizes the audit pattern Michael Chen ran on ca-org (2026-05-31 → 06-01) that Idan flagged as the bar for pre-delivery feedback: a self-contained GOAL file an agent executes end-to-end, producing findings that are proven (not asserted), adversarially checked (not just claimed), coverage-complete (no silent gaps), and re-runnable (prior findings re-verified on every new build — the audit becomes a regression suite).

Canonical pattern memory: `MattZerg/_agent_memory/shared/feedback_michael_client_delivery_audit_pattern.md`
Source exemplar: `MattZerg/Clients/CesiumAstro/delivery/source-artifacts/michael-audit-GOAL-2026-05-31.txt` + FINDINGS v1/v2 PDFs.
Companion for client technical/control **DOCS** (not the app): `feedback_ground_client_tech_docs_against_live_code.md` — ground every doc claim against live code (`file:line`) + the CURRENT status doc; the honesty bar is bidirectional (under-claiming a verified control is as damaging as over-claiming a missing one); ground role/permission claims against the role-seed migration. Apply the same UI==API==DB==source rigor to the doc's claims.

Two lanes, complementary and never overlapping:

| Lane | Question | Owner | Ground truth |
|---|---|---|---|
| `functionality` | Does the math/behavior work? | Michael's lane (Matt runs it only when asked) | UI == API == DB == source |
| `ux` | Can a human use it? | Matt's lane | Personas × tasks + heuristic corpus + client's stated goals |

A finding belongs in exactly one lane. Functionality findings never include design nits; UX findings never re-litigate math. If a visual defect corrupts data/meaning, it's functionality. Out-of-lane findings get routed to the right reviewer, not reported.

## When to invoke

- "Audit <client app> before delivery / before the demo / before handoff"
- "Run a functionality audit on X" / "Run a UX audit on X"
- "Re-verify the findings from last round" / "re-run the audit against the new build"
- "Do a feedback round on <client app>" (this skill IS the feedback round)
- Before Matt posts any feedback block to a client-internal channel
- A new build of a client app ships and prior findings exist (re-verification run)

Do NOT use for: Zerg's own marketing surfaces (use `cro-auditor` / `fakematt-feedback`), code diffs (use `qa-gate` / `pr-gate`), or content (use `review-pack`).

## Hard rules (from the pattern memory — non-negotiable)

1. **Read-only prime directive** on shared/live data. Never mutate to confirm a finding — tag SUSPECTED/UNVERIFIED and continue. One wrong click on shared live data is worse than a missed finding.
2. **No silent gaps.** Every in-scope item lands in the coverage matrix as Covered / Blocked / Skipped with reason.
3. **Adversarial refutation before reporting.** Independent checkers try to refute every candidate finding. Only survivors ship as CONFIRMED. Refuted claims are listed, not dropped.
4. **Re-verification first.** If a prior FINDINGS file exists, re-check every prior finding against the current build before hunting new ones.
5. **Never auto-post.** The report and draft Slack message stay local. Matt sends.

## Workflow

### 1. Intake

Collect (ask only for what can't be inferred):
- Target app URL + client name
- Lane(s): `functionality`, `ux`, or both (both = two separate reports)
- Modules/screens in scope
- Credentials (path or value — never echo into the report)
- Prior FINDINGS file, if any (check `MattZerg/Feedback/` for `*-<app-slug>-*` first)
- Client's stated goals for this delivery (drives UX severity)

### 2. GOAL file

Check for an existing target-specific GOAL file (`MattZerg/Feedback/goals/<app-slug>-<lane>.GOAL.md`). If none exists:
1. Run a **probing round**: log in, learn navigation, find the API patterns, establish (read-only) data access, note what does NOT work.
2. Instantiate `references/goal-template.md` with everything learned. The GOAL file must be executable by an agent with zero additional context.

If one exists: update its DATA-STATE section from a quick recon, since data changes between runs.

### 3. Execute the audit

Run the GOAL end-to-end. For substantial audits, orchestrate with the Workflow tool (user opt-in via this skill counts as the multi-agent opt-in): fan out per-module driver agents → reconcile → adversarial checkers. For smaller audits, run inline.

Phases (from the GOAL template — see `references/goal-template.md` for full detail):
- **Phase 0 — Recon**: access + screen↔endpoint↔table map (functionality) or persona×task map (ux). Re-verify prior findings here.
- **Phase 1 — Drive & capture**: walk every in-scope item, capture raw observations with evidence (numbers + payloads + queries, or screenshots + steps).
- **Phase 2 — Reconcile**: compute expected vs actual; tag PASS/FAIL/UNCERTAIN with layer-at-fault.
- **Phase 3 — Adversarial verification**: independent refuter per candidate finding; multiple refuters on high-impact claims; majority-confirm to ship.
- **Phase 4 — Report.**

### 4. Report

Write to `MattZerg/Feedback/YYYY-MM-DD-<app-slug>-<lane>.md` using the exact structure in `references/report-format.md`:
SUMMARY → TOP N TO FIX FIRST → COVERAGE MATRIX → RE-VERIFICATION OF PRIOR RUN → CONFIRMED FINDINGS → REFUTED/INCONCLUSIVE → METHOD & ACCESS.

Severity definitions:
- **Functionality**: Critical = wrong money/qty or data loss · High = wrong status/routing/match · Medium = wrong aggregate/filter · Low = cosmetic-but-functional
- **UX**: Critical = persona cannot complete core task / guaranteed data misread · High = needs outside help or misleads on first read · Medium = significant friction/trust damage · Low = polish

Optionally render to branded PDF via `document-styling-skill` (Michael ships PDFs to the channel; match that).

### 5. Handoff draft

Draft (do not send) a short Slack message for the client-internal channel in the shape Michael used: one line of context + "Top N" callout + attached report. Route the draft through `fakematt-slack` register if Matt wants it in his voice.

## Re-verification runs (the highest-value mode)

When Idan (or the client team) ships a fix build, re-run with the SAME GOAL file:
1. Re-check every prior finding first → mark ✅ Fixed / ❌ Still broken, each with fresh evidence
2. Then sweep for regressions/new findings
3. Report leads with the fixed/remaining scoreboard — this is what makes the feedback loop compound

## References

- `references/goal-template.md` — the full GOAL template (both lanes), generalized from Michael's ca-org GOAL. Read when creating a new GOAL file.
- `references/report-format.md` — exact FINDINGS report structure + example finding. Read before writing any report.
- Vault copies (canonical for the CA engagement): `MattZerg/Clients/CesiumAstro/delivery/client-delivery-audit-GOAL-template.md`
