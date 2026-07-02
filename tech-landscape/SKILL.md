---
name: tech-landscape
description: Emerging-tech landscape scan — vendor map, adoption-curve placement, standards/protocols snapshot. Reads a category brief, composes `exa:search` / `firecrawl:firecrawl-search` for external evidence, and `competitive-review-skill` for product-side detail. Outputs `.md` landscape map (vendors × stage × signal) + adoption-curve placement chart. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `competitive-review-skill` (single category, single Zerg product comparator), `market-sizing` (TAM/SAM/SOM numbers only). USE PROACTIVELY when Matt says "tech landscape", "emerging tech", "adoption curve", "vendor map", "category scan", "what's the landscape for", "tech scan", or before any forward-looking tech-stack call. Composes external search — refused in life-mgmt mode (air-gapped). Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Tech Landscape

Phase 3 deliverable-layer. Forward-looking tech-stack / vendor scan.

## When to invoke

- Matt says "tech landscape", "emerging tech", "adoption curve", "vendor map", "category scan".
- Forward-looking tech-stack decisions ("which vector DB?", "what does the agent-orchestration landscape look like?").

## Modes

### `scan`

```bash
python3 ~/.claude/skills/tech-landscape/run.py scan "<category>" \
  --engagement <slug> --mode <mode> \
  [--vendors "v1,v2,v3"] [--horizon 12-mo|24-mo]
```

Writes `<engagement>/05-analysis/tech-landscape-<category>.md` with:
- Adoption-curve placement (innovators / early adopters / early majority / late majority / laggards)
- Vendor map: vendor × stage × signal-strength × notable customers
- Standards / protocols snapshot
- Forward-looking risks (technology turnover, platform consolidation)
- Composition refs: `exa:search` queries + `firecrawl:firecrawl-search` URLs

## Air-gap rule

Refuses to run in `--mode life` (life-mgmt is air-gapped from external search per the consultant-engagement orchestrator).

## Composition

Phase-1 build of this skill only scaffolds the structure + records the queries you'd run via `exa:search` / `firecrawl:firecrawl-search`. Actual external search dispatched by the orchestrator or user — this skill captures the structure so the data lands in the right slots.
