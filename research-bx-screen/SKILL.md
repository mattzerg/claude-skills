---
name: research-bx-screen
description: Apply inclusion / exclusion criteria to a candidate corpus from research-bx-litsearch, producing an included / excluded list with documented reasons. PRISMA-style dual-coder screening for meta-analyses, single-coder for card seeding. Trigger phrases — "screen the candidates", "PRISMA screen", "apply inclusion criteria", "first-pass title abstract screen".
---

# Research / Behavioral-Sciences — Screening

Takes a candidate corpus from `research-bx-litsearch discover` and applies inclusion/exclusion criteria, producing an included list with rationale per excluded paper.

Stage 2 of the meta-analysis pipeline (litsearch → SCREEN → extract → meta → write → audit).

## Modes

- `card-seed <candidates-file>` — single-coder screen, ~3-6 included per construct (fast, for Phase 2 card seeding).
- `meta-analysis <candidates-file> --hypotheses <hypotheses.md>` — dual-coder screen with adjudication, PRISMA-style.

## Outputs

- `<construct>-screened-YYYY-MM-DD.md` with included + excluded tables; reasons cited from `references/inclusion-criteria.md` (rules borrowed from litsearch references).
- `state/screening-log.jsonl` for audit trail.

## Implementation status

**v0 stub.** Full implementation pending Phase 4 sprint. For Phase 2 card seeding, manual screening is acceptable — record decisions in `state/audit-log.jsonl` alongside litsearch.

See sister skills:
- `research-bx-litsearch` — produces the candidate list this skill screens.
- `research-bx-extract` — extracts effect sizes from included papers.
- `research-bx-audit` — validates the screening log.
