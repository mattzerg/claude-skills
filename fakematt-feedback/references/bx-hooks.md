# Behavioral-Sciences Hooks for fakematt-feedback

Mapping of fakematt-feedback's existing UX/IA checklist items to behavioral-sciences card constructs in `MattZerg/_knowledge/behavioral-sciences/`. When this reference is loaded, fakematt-feedback's report gains a `## Behavioral-science lens` section that auto-cites the matching cards.

## How this works

When fakematt-feedback runs, after its standard UX walkthrough findings, it consults this file. For each checklist item that surfaced a finding, it looks up the relevant card(s) and adds a behavioral-science citation to the finding — augmenting the UX-heuristic explanation with a framework-level explanation.

The lens is additive, not a replacement. UX findings keep their UX framing; the behavioral-science lens adds "the underlying mechanism is X (card: Y)".

## Hooks

| fakematt-feedback checklist item | Relevant card(s) | When to invoke |
|---|---|---|
| Confusing CTA placement | `hci/recognition-over-recall`, `hci/fitts-law`, `jdm/framing-effects` | Always when CTA placement is flagged |
| Unclear value proposition above the fold | `applied-psychology/social-proof`, `consumer-behavior/brand-asset-distinctiveness`, `hci/above-the-fold-effect` (with contestation surfaced) | When hero/value-prop is the issue |
| Missing social proof | `applied-psychology/social-proof`, `consumer-behavior/review-valence-and-volume` | Always |
| Too many choices (decision paralysis suggested) | `consumer-behavior/assortment-size` (CONTESTED — surface the contestation), `jdm/availability-heuristic` | Always — note the assortment-size meta-analytic failure |
| Hidden / unclear pricing | `behavioral-economics/partitioned-pricing`, `jdm/ambiguity-aversion` | When pricing is opaque |
| Default option ambiguous on settings/forms/pricing | `behavioral-economics/default-effect`, `behavioral-economics/status-quo-bias` | Always |
| Form too long / over-asks | `hci/chunking-in-form-design`, `hci/progressive-disclosure`, `behavioral-economics/goal-gradient-effect` | When form length is flagged |
| Error messages unhelpful | `hci/error-prevention-vs-error-message`, `hci/mental-models-and-conceptual-mismatch` | Always |
| Onboarding feels long / drop-off risk | `behavioral-economics/endowed-progress-effect`, `behavioral-economics/goal-gradient-effect`, `applied-psychology/implementation-intentions` | When onboarding is the artifact |
| Trust / credibility gaps | `applied-psychology/authority-cue`, `applied-psychology/social-proof`, `applied-psychology/liking` | When trust is flagged |
| Notification copy ineffective | `applied-psychology/implementation-intentions`, `jdm/framing-effects`, `applied-psychology/fresh-start-effect` | When notifications are reviewed |
| Above-the-fold hero design | `hci/f-pattern-vs-z-pattern-scanning` (CONTESTED), `consumer-behavior/brand-asset-distinctiveness`, `applied-psychology/mere-exposure` | Always — surface contestation |
| Pricing tier middle-bias suspected | `consumer-behavior/price-tier-mid-bias`, `behavioral-economics/decoy-effect` (MIXED — note Frederick 2014 replication failure) | When pricing tiers reviewed |
| Mobile vs desktop scanning differences | `hci/recognition-over-recall`, `hci/cognitive-load-theory` | When mobile UX flagged |

## Behavioral-science lens output template

When this reference fires, fakematt-feedback appends:

```markdown
## Behavioral-science lens

For each finding above, the underlying behavioral-science mechanism (where applicable):

### Re: <UX finding title>
**Card**: `<domain>/<construct>` (`replication_status: ...`)
**Mechanism**: <one-sentence framework explanation>
**Citation**: <bibtex key> → <DOI>
**Boundary check**: <are the conditions for the construct met here>
**Confidence**: high | medium | low — adjusted by replication status
```

## Hard rules (mirrored from advise-bx)

1. Never invoke a card on the `_replication-ledger.md` blacklist.
2. Always surface replication status for non-robust cards.
3. Hedge language to match the literature (no "research shows" without naming a study).
4. Card path must resolve to an existing file in `_knowledge/behavioral-sciences/`. Refuse to phantom-cite.

## Pre-Phase-2 behavior

If the knowledge layer is empty (Phase 2 not yet run), the lens does NOT inject — fakematt-feedback's normal UX report ships without the behavioral-science section. The lens silently no-ops; no error.
