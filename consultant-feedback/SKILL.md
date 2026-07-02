---
name: consultant-feedback
description: Review a McKinsey-style consultant deliverable holistically — deck, one-pager, framework artifact, minto-structured doc, SCQA, issue tree, hypothesis tree. Aggregator that severity-ranks findings across answer-first structure, MECE quality, framework choice, visual hierarchy, action titles, citation density. USE PROACTIVELY before sending any consultant deliverable externally, before a client gate, or before a workplan ships. Different from minto-pyramid (which generates) and consultant-deck (which renders) — this skill REVIEWS the finished artifact. Different from fakematt-feedback (UX) and fakeidan (code/prose Idan-bar) — this skill applies consultant-artifact patterns specifically.
references:
  - /Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md
  - /Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md
  - /Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_deck_visual_style.md
  - /Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md
  - /Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md
---

# consultant-feedback

Aggregator skill that reviews a McKinsey-style consultant deliverable holistically across the thinking layer (SCQA / issue tree / hypothesis tree / framework choice / Minto pyramid) and the deliverable layer (deck / one-pager / readout / appendix). Emits severity-ranked findings with cited pattern slugs and a ship/iterate/blocker verdict.

This skill REVIEWS finished artifacts. It does not generate or render.

## When to use

Invoke this skill in any of the following contexts:

- Before sending any consultant deliverable externally (client, advisor, internal exec).
- Before a client gate or signoff checkpoint on an engagement landing in `MattZerg/Engagements/`.
- Before a workplan, hypothesis tree, or issue tree ships to a downstream skill or workstream.
- Before a deck presentation — internal dry-run or client read-out.
- After multi-round iteration on a consultant artifact, to check whether HIGH findings closed and a scorecard delta is earned.
- Whenever the artifact spans more than one consultant-toolkit skill output (e.g., an issue tree feeding a Minto pyramid feeding a deck) and per-skill review would miss cross-layer drift.

Trigger phrases that should fire this skill: "review this deck", "consultant-feedback on...", "is this McKinsey deliverable ready", "before I send this to <advisor/client>", "ship-check this engagement artifact", "does this issue tree hold up", "audit this one-pager", "is the storyline tight".

## Inputs

Pass the path to the deliverable as the primary input. Supported types:

- `.md` — markdown source for SCQA, issue tree, hypothesis tree, framework output, Minto pyramid, one-pager, readout
- `.pdf` — rendered consultant-deck output, one-pager render, board memo
- `.pptx` — deck source (read structure: titles, layouts, slide count, source captions)
- `.gslides` link — Google Slides URL (read via available browser/sheet tooling)
- `.png` / `.jpg` — slide screenshots, framework artifacts, hand-drawn issue trees

Optional secondary inputs: prior-round review file (for scorecard delta), engagement frontmatter (`engagement` / `slug` / `date` / `inputs` / `source_citations`), and the upstream source-of-truth artifact (for X3 drift check).

## Anchors

Load and cite these files before producing the review:

- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md` — 21-entry pattern bank (T1–T8 thinking, D1–D8 deliverable, X1–X5 cross-cutting) with verbatim exemplar quotes and anti-pattern signals. This is the rule book.
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md` — voice + structural rules for SCQA, issue tree, hypothesis tree, framework choice, Minto pyramid. Source of T1–T8 dimension definitions.
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_deck_visual_style.md` — 8 deck rules (action title, one-thing-per-slide, chrome, layout-per-claim-type, two-accent palette, font discipline, slide-count discipline, source-on-quantitative). Source of D1–D8 dimension definitions.
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md` — voice anchor for the review output: paragraph-per-issue, ordered findings, evidence-cited, no hedging at the structural level, decisive verdict.
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` — cross-skill pattern catalog. Cite Section H (Consultant / process) slugs by name in the Patterns surfaced block.
- **Catalog patterns to cite by slug** (Section H Consultant / process): source-of-truth-drift, naming-reconciliation, harness-fidelity, product-type-detection
- `~/.claude/projects/.../memory/feedback_nick_consulting_doc_bar.md` — Nick's document-SET delivery bar (cross-doc consistency, page-break hygiene, clickable nav, Gantt-for-timelines, no naked-negative lede). Load when the artifact is a multi-page client document SET, not a single deck.
- `~/.claude/projects/.../memory/feedback_ground_client_tech_docs_against_live_code.md` — code-grounded technical-doc bar: ground claims against live code (`file:line`) + the CURRENT status doc; bidirectional honesty (don't under-claim a verified control); ground role/permission claims against the role-seed migration. Load when the deliverable is a client TECHNICAL / CONTROL / audit doc (security policy, controls readiness, integration guide), not just a consulting artifact.
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/voice_universals.md` — the cross-surface AI-tell / anti-pattern list. Load when the client artifact is PROSE (policy, guide, FAQ, onboarding doc), not a deck. Flag copy that reads AI-generated: uniform sentence cadence, em-dash overuse, rule-of-three padding, "In plain terms" / hand-holding sidebars to an expert reader, hollow superlatives, and defensive/assurance phrasing. Recurring client correction — Matt, Nick, and Byron (CesiumAstro) each flagged "reads AI-generated" on the CA docs (2026-06).

## Review dimensions

Severity-rank every finding HIGH / MED / LOW against the dimensions below. Dimension definitions are pulled from `consultant_thinking_style.md` and `consultant_artifact_feedback_corpus.md` — do not redefine in this file; cite the source.

### Thinking layer

- **answer-first-structure** (corpus T1) — top of artifact is the current best answer to the root question with `[confidence: low/med/high]` tag. Setup-first inversion is the canonical Minto failure. HIGH when the reader must read past the lead to find the recommendation.
- **mece-quality** (corpus T2) — issue-tree categories are Mutually Exclusive AND Collectively Exhaustive. 3–5 children per node. Overlapping leaves or missing siblings are HIGH; node-count drift is MED.
- **so-what-test** (corpus T3) — every issue-tree node, hypothesis leaf, and Minto key line passes "so what?" — its answer must change a decision. Nodes that fail are MED unless the artifact's main recommendation depends on them (then HIGH).
- **hypothesis-density** (corpus T4) — every issue-tree leaf carries (a) initial answer stated now, (b) evidence-required to prove + disprove, (c) named analyses to run, (d) confidence label. Missing any of (a)–(d) is MED; unfalsifiable hypothesis is HIGH (cross-references T8).
- **framework-choice-justification** (corpus T5) — one framework per question, citing recipe-card `when_to_use` / `when_not_to_use`. Framework whose output doesn't change the recommendation is "chrome" — HIGH. Two frameworks on the same question is HIGH. 3-vs-1 quadrant skew is MED (axes are wrong).
- **scqa-tension-clarity** (corpus T6) — Situation ≤3 sentences, Complication ≤2 sentences, Question one sentence ending in `?`, Answer ≤2 sentences with `[confidence]`. Question that doesn't surprise = Situation/Complication is wrong (HIGH). Missing `[confidence]` tag is MED.
- **named-numbers-discipline** (corpus T7) — every number carries `[source: …]` or `[needs-verification]` inline. Floating numbers are HIGH. Client-mode storyline with surviving `[needs-verification]` is HIGH.
- **falsifiability-discipline** (corpus T8) — every hypothesis names what would disprove it; analysis run on independent data, not data the system being tested generated. Evidence-laundering is HIGH. Unfalsifiable claim is HIGH (demote to blog post or kill).

### Deliverable layer

- **action-title-discipline** (corpus D1) — every slide title (except `title` / `section-divider`) is a complete claim: subject + verb + numeric backing. Topic-titles are HIGH on `consultant-deck` review. Title < 5 words or noun-only is MED.
- **one-idea-per-slide** (corpus D2) — one chart, one table, or one structured callout per slide. Two charts or chart+table is HIGH. `support` fallback layout used because "I had too much content" is MED.
- **source-citation-density** (corpus D3) — every quantitative claim has a footnote / caption / source field. Chart without source in caption is HIGH. `appendix-sources` slide missing despite cited body claims is HIGH. Client-mode render with surviving `[needs-verification]` is HIGH.
- **visual-hierarchy** (corpus D4) — lead with the chart when chart is the proof; lead with text when text frames the chart. Chrome must not outweigh body. Chart smaller than the title is MED; chrome eating hierarchy from content is HIGH.
- **executive-summary-front** (corpus D5) — exec-summary is slide 2 (after title), not slide 22. Governing thought italicized at top; 3 keys numbered (1./2./3.); each key ≤ 80 chars. Missing or buried exec-summary is HIGH. >3 keys is MED.
- **appendix-discipline** (corpus D6) — appendix carries working (sources, supporting data, alternative analyses) and nothing that belongs in the main storyline. Load-bearing claim hidden in appendix is HIGH. Source numbering breaks ([1], [2], [4]) is LOW.

Additional dimensions to apply when the artifact triggers them:

- **layout-type-per-claim-type** (corpus D7) — `support` fallback indicates incomplete storyline. Multiple `recommendation` slides in one deck is HIGH.
- **slide-count-discipline** (corpus D8) — soft cap 25, hard cap 35. Tight engagement = 7–13 slides.
- **universal-review-structure** (corpus X1) — ship-blockers / should-fix / strong moves / craft / net. Use this as the verdict-section grammar when emitting the review.
- **scorecard-with-deltas** (corpus X2) — multi-round reviews emit a scorecard with delta vs prior round; stop-rule at round 3.
- **source-of-truth-discipline** (corpus X3) — drift between vault canonical and deployed/rendered version is HIGH. Cross-references Section H `source-of-truth-drift` slug.
- **voice-cosplay-guard** (corpus X4) — critique stays professional/structured; generation follows `consultant_thinking_style.md` voice (no hedging adjectives, no corporate-strategy nouns). Neither cosplays Matt-voice.
- **banned-terminology-hook** (corpus X5) — Zstack-as-product-umbrella phrasing in any consultant artifact is HIGH. Use "Zerg products". Zstack alone (infra / control plane) is fine.
- **client-prose-de-ai-voice** (memory `voice_universals.md`) — apply when the artifact is client PROSE (policy / guide / FAQ / onboarding), not a deck. Copy that reads AI-generated is a MED finding (HIGH for an external audit/exec audience): flag uniform sentence cadence, em-dash density, rule-of-three padding, "In plain terms" hand-holding to an expert reader, hollow superlatives, and defensive/assurance phrasing before evidence exists. Recurring miss — Matt, Nick, and Byron all flagged it on the CA set (2026-06); a de-AI voice pass is now part of the pre-ship bar for client prose.
- **document-set-delivery-bar** (memory `feedback_nick_consulting_doc_bar.md`) — apply when the artifact is a multi-page client document SET (policy + strategy + guides), not a single deck. Judge the bundle as one artifact: cross-doc consistency (same theme / Document-Control header / white background), page-break hygiene (no stranded headings, no split tables/glossaries, figure kept with its key), clickable TOC + cross-references in the rendered PDF, a Gantt/timeline for any phased plan, a diagram for any flow written as ≤2 sentences, bulleted exec summaries with selective bold + color-coded tiers (no yellow), and no doc leading with a naked negative. Visible set inconsistency or dead TOC/links in the PDF is HIGH. Render hygiene is enforced by `document-styling-skill` — flag if it didn't land.

## Voice

Review output follows `matt_considered_voice.md` — the post-hoc structural review voice Matt uses when reading an artifact top-to-bottom and producing an ordered set of findings.

Operative tells to apply:

- **Paragraph-per-issue** (Tell 5). Each finding is a paragraph with a file path, page number, or quoted line. Bullets only for the structural skeleton (the H1/H2/M1/L1 list); the content of each finding is prose with concrete anchors.
- **Ordered findings** (Tell 1). H1 / H2 / H3 for HIGH, M1 / M2 / M3 for MED, L1 / L2 / L3 for LOW. Do NOT originate `C1`/`S1` numbering — that scheme belongs to Idan's response shape (per anti-pattern 4 in `matt_considered_voice.md`).
- **Evidence-cited.** Every finding points at a specific artifact path, slide number, line range, or quoted phrase. No floating critique.
- **No hedging at the structural level** (anti-pattern 1). Once a finding is named, it's named. "H2 — exec-summary is slide 19 of 22" is the right shape. "H2 — exec-summary maybe could be earlier" is the wrong shape. Hedges belong in the deferred-with-reason call-out ("not blocking signoff," "cherry on top"), not in the finding itself.
- **Decisive verdict** (Tell 11 / X1 universal review structure). Closing line commits — `ship`, `iterate`, or `blocker`. Do not equivocate.
- **No Idan cosplay** (anti-pattern 3). The shape mirrors Idan's review structure (ship-blockers / should-fix / strong moves / craft / net per X1), but the vocabulary stays neutral-professional. Do not use "right shape," "load-bearing," or "schema-enforced invariants beat documented-but-trusted ones" as primary review vocabulary — those are Idan tells.

Critique register is professional/structured per X4. Do not cosplay Matt-voice in the output.

## Output format

```
## Consultant-feedback review — <artifact name>

**Verdict:** [ship / iterate / blocker]

### HIGH findings
- **H1 [dimension-slug]** [Finding statement, 1 sentence.] Evidence: [quote / page# / slide# / file path:line]. Fix: [recommendation].
- **H2 [dimension-slug]** ...

### MED findings
- **M1 [dimension-slug]** ...
- **M2 [dimension-slug]** ...

### LOW findings
- **L1 [dimension-slug]** ...

### Strong moves to keep
- [Brief callout of what works — universal-review-structure X1 requires recognition, not all critique.]

### Patterns surfaced
- [Section H slug from `feedback_patterns_catalog.md`, e.g., `source-of-truth-drift`, `naming-reconciliation`, `harness-fidelity`]
- [Corpus pattern slug, e.g., `T1 answer-first-structure`, `D3 source-citation-density`, `X3 source-of-truth-discipline`]

### Scorecard (multi-round only)
[Round N: X/100 (vs round N-1: Y/100). Delta: ±Z. Stop-rule check: round N of K. Cap: applied / no cap.]
```

Notes on the format:

- Dimension slug in brackets after the finding ID, e.g., `H1 [action-title-discipline]` or `M2 [mece-quality]`.
- Evidence must be a concrete anchor: slide number, page number, file path + line, or a verbatim quote. No "the exec-summary section" without saying which slide.
- "Strong moves to keep" is required even when the artifact is mostly broken — per X1, a review missing the strong-moves section is itself an anti-pattern.
- Scorecard block only appears on multi-round reviews (X2). On first-round, omit the section entirely rather than emit `Round 1: N/A`.

## Workflow

1. **Read the deliverable end-to-end.** Open the file with the appropriate tool (Read for `.md` / `.pdf`, `.pptx` parsing or screenshots for decks, image read for `.png` / `.jpg`). Do not start dimension-checking mid-read.
2. **Identify the artifact layer.** Thinking layer (SCQA / issue tree / hypothesis tree / framework choice / Minto pyramid) or deliverable layer (deck / one-pager / readout / appendix), per the corpus "How to use" section. Some artifacts span both.
3. **For each applicable dimension, check against rules in `consultant_artifact_feedback_corpus.md`.** Run T1–T8 first (thinking-layer audit before deliverable-layer audit — per the corpus closing summary, bad thinking renders as bad deliverable). Then D1–D8. Then the X-series cross-cutting checks.
4. **For each finding, record the dimension slug, severity, evidence anchor, and fix recommendation.** Severity grammar follows the corpus rules above (HIGH / MED / LOW per dimension).
5. **Run X3 source-of-truth-discipline.** Compare the artifact path against the vault canonical (frontmatter `engagement` + `slug` + `inputs`). Drift between source and rendered version is HIGH and gets a Section H `source-of-truth-drift` pattern citation.
6. **Run X5 banned-terminology-hook.** Scan for Zstack-as-product-umbrella phrasing per `~/.claude/hooks/zerg_product_terminology_hook.py`. Any hit is HIGH.
7. **Group findings by severity into the output template.** Order within severity by load-bearing impact on the recommendation, not alphabetically.
8. **Cite Section H pattern slugs.** Reference `feedback_patterns_catalog.md` Section H — `source-of-truth-drift`, `naming-reconciliation`, `harness-fidelity`, `product-type-detection` — when the finding matches. Also cite the corpus dimension slug (T1–T8, D1–D8, X1–X5).
9. **Voice-check the output against `matt_considered_voice.md`.** Paragraph density on findings, no hedging at the structural level, ordered HX/MX/LX scheme (not Idan's C/S), decisive verdict on the closing line.
10. **Emit the verdict.** `ship` = no HIGH findings, MED findings have deferred-with-reason call-outs. `iterate` = HIGH findings exist but are addressable in one round. `blocker` = HIGH findings span multiple layers (thinking + deliverable) or include X3 source-of-truth drift / X5 terminology drift.

## What this skill does NOT do

- **Does not GENERATE consultant artifacts.** Drafting SCQA, issue tree, hypothesis tree, framework output, Minto pyramid, or deck is the job of `minto-pyramid`, `scqa-framing`, `issue-tree`, `hypothesis-tree`, `framework-library`, or `consultant-deck`. This skill only reviews finished artifacts.
- **Does not RENDER decks.** Slide rendering, layout assembly, and PDF/PPTX/Google-Slides composition is `consultant-deck`'s job.
- **Does not REVIEW funnel or conversion surfaces.** Marketing-page / signup-funnel / pricing-page conversion review is `cro-auditor`. Page UX walkthroughs are `fakematt-feedback`. Landing-page-against-corpus scoring is `webpage-layout`.
- **Does not REVIEW prose voice.** Blog / launch / thought-piece copyediting is `fakematt-copyedit`. Email voice is `fakematt-email`.
- **Does not run security or code review.** Code-bar review is `fakeidan`. PR-gate orchestration is `pr-gate`.

## Examples

Trigger phrases that should fire this skill:

```
user: "review this deck before I send it to Vang"
user: "consultant-feedback on the Q2 strategy one-pager"
user: "is this McKinsey deliverable ready for the client?"
```

Other valid triggers: "audit this issue tree", "does the Minto storyline hold up", "ship-check this engagement artifact", "before I send the readout to the board", "is this hypothesis tree falsifiable", "review the SCQA framing on this engagement brief".
