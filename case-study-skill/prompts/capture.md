You are doing a **capture pass** for the Zerg case-study skill: turning raw vault evidence into a structured brief that a separate `scaffold` step will later turn into a draft case study.

This is NOT writing the case study. It is producing an evidence ledger. The brief you emit is the ONLY source of truth for the eventual draft — if a fact is not in this brief with a citation, it cannot appear in the draft. So be thorough, and be honest about what you don't have.

# Your job

1. Read the raw vault snippets below. Each is tagged with its source path and a weight (HIGH/MEDIUM).
2. Synthesize a structured brief in the exact format below.
3. For every outcome / metric / quote, attach a confidence tier (HIGH/MEDIUM/LOW) and at least one evidence path.
4. Populate `gaps[]` for everything that's missing — especially Linear/Zergboard pulls that the script didn't do, customer quotes that don't yet exist, and metrics without baselines.
5. Default `nda_status: unknown`. Never auto-clear NDA status. If the evidence explicitly mentions NDA on a codebase or component, set `nda_status: restricted` and explain in `risks`.

# Confidence rubric

- **HIGH** — Verifiable in vault evidence with at least two corroborating sources OR a direct shipped artifact (Linear issue, deployed URL, named customer signoff).
- **MEDIUM** — Single source, plausible but unverified.
- **LOW** — Claim made in a Slack/Claude conversation but not corroborated by an artifact, OR any metric without a baseline. LOW outcomes feed the eventual interview file.

# What goes in the brief

- **Identity** — client name, sector, kind (delivery vs. advisory), timeframe.
- **Team** — Zerg team members involved, named where vault attests it.
- **Products used** — Zerg products (Atlas, ZCloud, ZTC, Metamorph, Zergboard, etc.) named in evidence.
- **Scope** — what Zerg was hired/asked to do, in 2-3 sentences.
- **Deliverables** — concrete things shipped or in flight, with status.
- **Outcomes** — every metric/result, each with `value`, `unit`, `baseline` (if known), `timeframe`, `evidence_path`, `confidence`. If the source has no baseline, mark confidence LOW and add a gap entry.
- **Candidate quotes** — ONLY quotes that appear verbatim in the evidence (Testimonials.md, conversation transcripts, etc.). Attribute by name + title + company. If you have to paraphrase, don't — leave the field empty and add a gap.
- **Evidence links** — full vault paths or URLs of every source used.
- **Gaps** — what's missing and what would close each gap (e.g., "Linear issues for Durable v2 not in evidence; query linear-skill"; "no customer quote yet; ask André or client COO for one").
- **Risks** — NDA, sensitivity, attribution ambiguity, anything that should block publication.

# Hard rules — do not violate

- **Cite or omit.** Every claim has an `evidence_path`. No `evidence_path` → drop the claim.
- **No fabricated metrics.** If you can't find a number in the evidence, don't make one up. Mark it as a gap.
- **No paraphrased quotes in `candidate_quotes`.** That field is for verbatim quotes only. Paraphrases go in `gaps[]` as "need verbatim quote from X".
- **No round numbers** ("50%", "10×") unless verbatim in source.
- **NDA defaults to unknown.** If evidence explicitly says "NDA" or "confidential codebase", set `restricted` instead.

# Output format (markdown — DO NOT WRAP IN A CODE FENCE)

Output exactly this structure:

```
---
client: <ClientName>
project_slug: <slug-from-script>
sector: <industry — aerospace-defense, enterprise-software, ai-hardware, fintech, etc.>
kind: <delivery | advisory>
timeframe_start: <YYYY-MM-DD or "unknown">
timeframe_end: <YYYY-MM-DD or "ongoing" or "unknown">
team: [<names attested in vault>]
products_used: [<Zerg products named in evidence>]
nda_status: <unknown (default) | cleared | restricted>
status: brief
created: <today YYYY-MM-DD>
---

# <ClientName> — case study brief

**Brief produced by:** case-study-skill capture
**Evidence sources scanned:** see Evidence links below

## Scope

<2-3 sentence summary of what Zerg was hired/asked to do. Cite at least one evidence path inline.>

## Deliverables

- **<deliverable>** — <status (live / in flight / planned)>. <One concrete fact.> _(evidence: <path>)_
- ...

## Outcomes

For each measurable outcome, this exact shape:

### O1 — <one-line outcome title>
- **Value:** <number + unit, verbatim from source if possible>
- **Baseline:** <prior value, or "unknown — gap">
- **Timeframe:** <"by Q2 2026", "in 6 weeks", "ongoing", or "unknown">
- **Confidence:** HIGH | MEDIUM | LOW
- **Evidence:** `<vault path or URL>`

If there are no measurable outcomes yet, say so explicitly: "No measurable outcomes documented in evidence. Gap: customer-side metrics needed before case study can scaffold."

## Candidate quotes

For each verbatim quote found in evidence:

### Q1 — <speaker>
- **Quote:** > <verbatim text>
- **Speaker:** <name>, <title>, <company>
- **Source:** `<evidence path>`

If no verbatim quotes exist, write: "No verbatim quotes in evidence. Gap: ask <named contact> for a 1-2 sentence quote covering <topic>."

## Evidence links

- `<full vault path>` — <one-line description of what's there>
- ...

## Gaps

Anything missing that the scaffold step will need. Be specific.

- **Linear pulls not done by script.** Run: `linear-skill search "<client>"` to surface in-flight issues; expect HIGH confidence on shipped, MEDIUM on in-progress.
- **Zergboard pulls not done by script.** Run: `zergboard-skill search "<client>"` to surface card scope.
- **<other gaps>** — what's missing, where it might live, how to fill it.

## Risks

- **NDA status:** <restate frontmatter value + reasoning. If `restricted`, name the component or codebase under NDA.>
- **<other risks>** — attribution ambiguity, sensitive sector, missing client signoff, etc.

## Notes for scaffold

Anything the scaffold step should know before generating a draft. E.g., "primary outcome is the AWS GovCloud deployment going live; lead the case study with that metric." Or, "this engagement is mid-flight — frame as in-progress, not as a finished win."
```

# Calibrated rules (apply, don't re-flag)

- **Zerg client list per memory.** Real clients to date: CesiumAstro, Andesite, Durable, d-Matrix (proposal), Rubrik (POC), Apple (exploratory), VIA, The Sandbox Game. Pre-Zerg work (Vang, Dinari, Touch Surgery, Hackster) is OUT OF SCOPE — if asked to capture for those, return a brief that says "out of scope; this skill is for Zerg solution-delivery only" and stop.
- **NDA defaults for sectors.** Defense / aerospace / hardware = `unknown` until proven cleared. Andesite metamorph codebase is explicitly NDA per `Client Pipeline.md` — that brief should be `restricted`.
- **Product names.** Zerg products (Atlas, ZCloud, ZDE, ZTC, Metamorph, Zergboard, ZergChat, etc.) come from `Product Glossary.md`. Don't invent product names; if a product mentioned in conversations isn't in the Glossary, flag it as a gap.

# Anchors

The case study style guide and 12-exemplar corpus are loaded as context below. The brief should set up the eventual draft to land the genre's beats — but the brief itself is structured evidence, not narrative.
