# Behavioral-Sciences Hooks for landing-page-skill

Mapping of landing-page-skill's page-structure heuristics to behavioral-sciences card constructs. Adds a `## Behavioral-science lens` section to landing-page audits and (in generation mode) injects construct-grounded reasoning into page-section recommendations.

## How this works

landing-page-skill produces page-section findings: hero, value prop, social proof, feature blocks, pricing block, FAQ, footer CTA. Each of these maps to one or more behavioral-sciences cards. The lens adds the framework reasoning so the audit/generation explains WHY the recommended pattern works (or doesn't).

## Hooks by page section

### Hero / above-the-fold

| Sub-finding | Card |
|---|---|
| Generic / "AI stencil" hero copy | `consumer-behavior/brand-asset-distinctiveness`, `applied-psychology/mere-exposure` |
| Hero doesn't show product | `hci/recognition-over-recall`, `consumer-behavior/lay-theories-in-product-judgment` |
| Weak primary CTA | `jdm/framing-effects`, `applied-psychology/commitment-consistency` |
| Above-the-fold value-prop weak | `hci/above-the-fold-effect` (CONTESTED — surface contestation), `applied-psychology/mere-exposure` |

### Value proposition / benefits block

| Sub-finding | Card |
|---|---|
| Feature-list framing instead of benefit-framing | `jdm/framing-effects`, `consumer-behavior/lay-theories-in-product-judgment` |
| Loss-aversion frame missing where appropriate | `jdm/loss-aversion` |
| Reciprocity cue (free thing, no card-required trial) | `applied-psychology/reciprocity` |

### Social proof block

| Sub-finding | Card |
|---|---|
| No logos / testimonials | `applied-psychology/social-proof`, `consumer-behavior/review-valence-and-volume` |
| Logos too generic / not similar to user | `applied-psychology/social-proof` (boundary: similarity to target user) |
| Testimonials without face/name/role | `applied-psychology/authority-cue`, `applied-psychology/liking` |
| Stats / counts presented (X customers, Y reviews) | `consumer-behavior/review-valence-and-volume` (boundary: are they large enough to feel social-proof-worthy) |

### Pricing block

| Sub-finding | Card |
|---|---|
| No default tier | `behavioral-economics/default-effect`, `behavioral-economics/status-quo-bias` |
| Three tiers without decoy | `behavioral-economics/decoy-effect` (MIXED — surface that classic asymmetric-dominance failed Frederick 2014), `consumer-behavior/decoy-pricing` (MIXED) |
| Anchoring tier highest-first vs lowest-first | `behavioral-economics/anchoring-in-pricing`, `jdm/anchoring` |
| .99 / left-digit pricing | `behavioral-economics/left-digit-effect` |
| Hidden fees / partitioned pricing | `behavioral-economics/partitioned-pricing` |

### Feature blocks

| Sub-finding | Card |
|---|---|
| Too many features (cognitive overload) | `consumer-behavior/assortment-size` (CONTESTED), `hci/cognitive-load-theory`, `hci/millers-7-plus-minus-2` |
| Feature blocks scannable | `hci/f-pattern-vs-z-pattern-scanning` (MIXED — surface contestation), `hci/gestalt-grouping-principles` |
| Progressive disclosure used | `hci/progressive-disclosure` |

### FAQ / objection-handling

| Sub-finding | Card |
|---|---|
| Common objections addressed | `jdm/regret-aversion`, `consumer-behavior/regret-in-post-purchase` |
| Refund/guarantee | `jdm/ambiguity-aversion`, `jdm/loss-aversion` |
| FAQ in accordion vs full | `hci/recognition-over-recall`, `hci/progressive-disclosure` |

### Footer CTA / final push

| Sub-finding | Card |
|---|---|
| Repeat CTA at fold-bottom | `applied-psychology/mere-exposure`, `behavioral-economics/goal-gradient-effect` |
| Different CTA copy variant | `jdm/framing-effects` |

## Output augmentation (audit mode)

After landing-page-skill's standard findings:

```markdown
## Behavioral-science lens

### Re: <page section finding>
**Card**: `<domain>/<construct>` (`replication_status: ...`)
**Mechanism**: <how the construct explains the recommendation>
**Citation**: <bibtex key> → <DOI>
**Boundary check**: <are conditions met>
**Dark-pattern check**: <is the recommended pattern legitimate or manipulative>
```

## Output augmentation (generate mode)

When landing-page-skill generates a page, behavioral-sciences cards are listed inline next to each section's design rationale so the generated page comes with a framework-grounded design memo, not just markup.

## Hard rules

1. Never invoke a blacklisted card.
2. Surface contested cards (above-the-fold, f-pattern, assortment-size, decoy-effect, NPS-validity) with their contestation.
3. Dark-pattern check is mandatory: if the recommendation requires exploiting user inattention against their interest, REFUSE and recommend the legitimate alternative.
4. Pre-Phase-2: lens silently no-ops if `_knowledge/behavioral-sciences/` is empty.
