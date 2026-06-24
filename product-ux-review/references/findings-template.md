# FINDINGS report skeleton (the bar)

The structure every `audit` FINDINGS doc must hit. Mirrors the michael pattern. Keep it scannable.

```
---
type: findings
product: <name>
lane: ux
version: v<N>
created: YYYY-MM-DD
from: <author>
to: <builder>
build: <branch / commit>
evidence: <evidence dir>
method: chrome-devtools driver · alpha-composited contrast · (Lighthouse) · adversarial refutation
---

# <Product> — UX/Design FINDINGS v<N>

> Lane note for the builder: UX/design lane only. No functionality/auth/persistence findings (those are
> the builder's lane — list any spotted as one-liners, not as UX findings).

## Summary
2-sentence headline + severity counts. UX severity:
  Critical = persona cannot complete a core task / data misread guaranteed
  High     = completable only with help, or misleads on first read
  Medium   = significant friction / trust / space cost
  Low      = polish

## Prod-readiness gate (must-have launch gates vs polish)   ← headline framing

## Top N to fix first   (quick wins, ordered by impact ÷ effort)

## Coverage matrix   (every scope item Covered / Blocked / Skipped + reason — NO SILENT GAPS)

## Re-verification of prior findings (if a prior FINDINGS exists)   (Fixed / Partial / Still-open + evidence)

## Confirmed findings   (each:)
  F<n> · screen · severity · one-line title
  Expected (principle/heuristic citation, with proof)
  Actual (screenshot / measurement / payload)
  Layer (IA / copy / state / interaction / typography / layout)
  Repro steps
  How the checker confirmed it (the adversarial pass)
  Concrete fix (NAME the component file)

## Especially good   (verified strengths worth keeping/propagating — not just gaps)

## Refuted / inconclusive   (candidates that did NOT survive refutation — listed, never silently dropped)

## Method & access   (exact reproduction: build, seed, drive, tools)
```

## `bug-sweep` doc structure
```
Summary (counts: confirmed / refuted / runtime-passes) → Top fixes → Triage table
(ID | sev | area | file:line | bug | one-line fix) → detailed repro per bug grouped by class →
Refuted/cleared (shows the bar) → Method (the parallel adversarial agents + any live probing) →
cross-ref to the UX FINDINGS.
```

## Render to PDF
`python3 ~/.claude/skills/product-ux-review/scripts/md2pdf.py <findings.md> <out.pdf>`
(headless Chrome, stdlib-only; renders tables + fenced ASCII/code blocks; Zerg brick-red brand).
