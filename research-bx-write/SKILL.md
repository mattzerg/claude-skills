---
name: research-bx-write
description: Scaffold a preprint or paper draft from meta-analytic results + protocol. Produces APA-formatted manuscript with DOI-verified citations. Targets PsyArXiv preprint by default; flag --target=blog|journal|internal forks output style. Trigger phrases — "draft the preprint", "write the manuscript", "scaffold the paper".
---

# Research / Behavioral-Sciences — Manuscript Drafting

Stage 5 of the pipeline. Scaffolds a preprint or journal manuscript from `hypotheses.md` + `protocol.md` + `results.md`. Voice anchored on `MattZerg/_style/expert_voice_behavioral_sciences.md` adapted to academic-manuscript register.

## Modes

- `preprint` (default) — PsyArXiv-ready markdown; APA citations; methodology section verbose.
- `blog` — Zerg blog format; long-form but accessible; methodology in a separate "How we did it" section.
- `journal --target <journal>` — journal-specific length + section conventions (e.g., JDM, JCR).
- `internal` — vault-only summary; relaxed format.

## Hard rules

- Every citation must trace to `_citations/library.bib` AND `_citations/verified-doi-allowlist.md`.
- Every effect size must trace to `state/extracted-data.csv` row.
- `hypotheses.md` lock timestamp ≤ extraction start timestamp.
- No "research shows" / "studies suggest" without DOI.
- `research-bx-audit` runs as a final gate before output is rendered.

## Implementation status

**v0 stub.** Phase 4 deliverable. Mirrors `case-study-skill`'s scaffold/render anatomy.

## Pairs with

- `research-bx-meta` — provides results to write up.
- `research-bx-audit` — pre-render validation.
- `case-study-skill` — template for the runner pattern (scaffold mode).
