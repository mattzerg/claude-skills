---
name: product-ux-review
description: >-
  Run a structured, evidence-backed UX/UI/design audit (or adversarial bug sweep) of a live or local
  product by driving it in a real browser and dispatching adversarial verification subagents. Use when Matt
  says "UX audit", "design review", "UI review", "review this page/app", "what's wrong with this page/app",
  "go look at <url/localhost>", "find UI issues / bugs", "bug sweep", "adversarial review", or wants
  pre-ship / pre-demo product feedback. Pure methodology — drives the chrome-devtools MCP, cites NN/g / WCAG
  2.2 AA / Baymard / graphic-layout / frontend-design principles, refutes every finding adversarially, and
  writes a versioned FINDINGS doc + PDF to the vault. No feedback-corpus, ANTHROPIC_API_KEY, or pip/python
  deps required — runs on ANY Mac (it's the stopgap-safe front door; fakematt-feedback is its optional
  accelerated backend on the main Mac). Never auto-posts to shared channels.
---

# Product UX Review

A live-driven, evidence-backed product UX/UI audit at the "Michael bar" (the
`client-delivery-audit` GOAL→FINDINGS pattern). It packages the proven hand-workflow so a review is
one invocation, not re-derived each time. **It needs no corpus, API key, or pip installs** — it drives
the chrome-devtools MCP + dispatches subagents + renders PDF via headless Chrome, all of which work on
the stopgap Mac. `graphic-layout` is the precedent: a pure-methodology skill, no `run.py`.

## When to invoke
Trigger on: "UX/UI audit", "design/UI review", "review this page/app", "what's wrong with this <page/app>",
"go look at <url|localhost:port>", "find UI issues/bugs", "bug sweep", "adversarial review", or any
pre-ship/pre-demo feedback ask. When Matt drops a URL or a localhost target with little context, assume he
wants `audit` mode. **Announce** "Using product-ux-review (<mode>) on <target>" before starting.

## Modes
- **`audit`** (default) — the live UX/design pass → a versioned `FINDINGS` doc.
- **`bug-sweep`** — the adversarial code/bug pass → a triage-table `bug-review` doc. Run when Matt asks for
  "bugs", "adversarial review", or "find more issues". Compose both for a full pre-ship gate.

## Inputs / setup
Resolve the target into one of: live URL · local app (`http://127.0.0.1:port`) · static screenshots/PDF.
For a **local app**, capture the exact **start command + seed steps** into the run so the audit is
re-runnable (bake them into the GOAL — see below). Disposable local env ⇒ mutation is allowed (exercise
create/edit/send/schedule); shared/live data ⇒ strictly read-only (tag unverifiable findings, never mutate).

## Method — `audit` (phased; from `feedback_michael_client_delivery_audit_pattern.md`)
**Lane discipline first:** this is the UX/design lane (hierarchy, layout, responsive, comprehension, copy,
a11y). Route functional/auth/persistence/math bugs OUT to the builder as one-liners — never mix lanes.
(Use `bug-sweep` for code bugs.)

0. **Recon + RE-VERIFY.** Stand up + seed the target. If a prior FINDINGS file exists, re-check EVERY prior
   finding against the current build (Fixed / Partial / Still-open + evidence) BEFORE hunting new ones.
   Optionally emit/refresh a re-runnable **GOAL file** (template:
   `Clients/CesiumAstro/delivery/client-delivery-audit-GOAL-template.md`).
1. **Drive & capture (no conclusions).** Via chrome-devtools MCP: log in / navigate; sweep viewports
   **1440 / 1024 / 768 / 500**; per surface take a screenshot + `evaluate_script` for computed styles
   (fonts/sizes/serif, rail widths as % of viewport, breakpoint behavior), `list_console_messages`, and an
   a11y pass (nameless buttons, unlabeled inputs, and a **proper alpha-composited** contrast check — blend
   translucent layers to an opaque backdrop before measuring; do NOT load axe from a CDN, it's blocked as
   remote code). Save captures to an evidence dir. Walk each persona (super-admin / admin / end-user /
   external-viewer) through its real tasks.
2. **Reconcile** observations into findings: `persona · task · severity (by user impact) · principle citation
   · layer (IA/copy/state/interaction/typography/layout) · component file to fix · repro`.
3. **Adversarial refutation (the bar).** Dispatch independent subagents (Agent tool) to REFUTE each candidate
   ("real user problem or reviewer taste? does a heuristic back it? would the persona truly be blocked?").
   Default "not a finding" unless independently confirmed. Survivors → CONFIRMED; the rest → Refuted/
   Inconclusive (listed, never silently dropped). Self-refute your own measurements too (e.g. a contrast
   reading off a translucent bg is an artifact, not a failure).
4. **Report** — see Deliverable.

## Method — `bug-sweep`
Fan out N adversarial code-review subagents in parallel (one bug-class each: **state/race/lifecycle ·
error-handling/edge-case · a11y/responsive/CSS**), each told to read the actual code (file:line), reason
about real bugs, and **self-refute** its candidates (report only confident-real ones; list refuted
separately). Optionally add live runtime probing via chrome-devtools (XSS/injection in renderers, forced
error states by killing the server, console during real actions). De-dupe, severity-rank, and emit a
**triage table** (`ID | sev | area | file:line | bug | one-line fix`) + per-bug repro below + the refuted list.

## Deliverable
Write to `MattZerg/Feedback/<slug>-<lane>-FINDINGS-v<N>-YYYY-MM-DD.md` (audit) or
`<slug>-adversarial-bug-review-v<N>-YYYY-MM-DD.md` (bug-sweep), plus an evidence dir. Render a desktop/vault
PDF with `python3 ~/.claude/skills/product-ux-review/scripts/md2pdf.py <md> <out.pdf>` (headless Chrome,
stdlib-only — handles tables + fenced ASCII/code blocks; Zerg-branded). Report structure (the bar) is in
`references/findings-template.md`; the citation map is in `references/principle-corpus.md`. Versioned
filenames per the iteration-version rule. **Never auto-post** — vault + Fake Matt self-DM only.

## Optional accelerated backend (main Mac only)
If `~/.claude/feedback-corpus/voice/fingerprint.md` + `principles/library.md` exist AND an
`ANTHROPIC_API_KEY` (or `~/.claude/anthropic.json`) is present AND python `playwright`+`anthropic` are
installed, you MAY instead shell out to `~/.claude/skills/fakematt-feedback/run.py <target> [flags]` for the
SDK-cached Matt-voice critique + auto axe pass + self-DM digest. Otherwise execute the methodology above by
hand. **State which mode ran.** One entry point, two execution modes — don't fork into a second skill.

## Safety
- Read-only is the law on shared/live data; disposable local env ⇒ mutation OK, reset by restarting.
- One isolated browser context; clean up on success AND failure; kill any dev server you started.
- If you wire a provider/API key for a live-agent test, keep it ephemeral (env-only, never written to disk).
- Lane discipline is the law in `audit` mode (UX only). Output stays local — Matt routes it himself.

## Anchors (read on demand, don't duplicate)
- `_agent_memory/shared/feedback_michael_client_delivery_audit_pattern.md` — the 12-point methodology spine.
- `Clients/CesiumAstro/delivery/client-delivery-audit-GOAL-template.md` — the re-runnable GOAL template.
- `references/findings-template.md` — the report skeleton. `references/principle-corpus.md` — citation map.
- Worked example: the 2026-06-24 ZergChat run (`Feedback/zergchat-ux-FINDINGS-v2-*` +
  `zergchat-adversarial-bug-review-v1-*` + the GOAL in `Projects/Zerg-Production/ZergChat/`).
