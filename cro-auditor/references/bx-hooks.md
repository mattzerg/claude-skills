# Behavioral-Sciences Hooks for cro-auditor

Mapping of cro-auditor's funnel/conversion checklist items to behavioral-sciences card constructs in `MattZerg/_knowledge/behavioral-sciences/`. Adds a `## Behavioral-science lens` section to cro-auditor reports.

## How this works

cro-auditor produces funnel/conversion-focused heuristic findings. This hook augments each finding with the underlying behavioral-science mechanism + card citation, so Matt sees both the conversion implication (CRO frame) and the framework-level reasoning (BX frame) for the same observation.

## Hooks

| cro-auditor finding type | Relevant card(s) |
|---|---|
| Weak / missing primary CTA | `jdm/framing-effects`, `jdm/regret-aversion`, `applied-psychology/commitment-consistency` |
| Pricing-page mid-tier bias / decoy missing | `consumer-behavior/price-tier-mid-bias`, `behavioral-economics/decoy-effect` (MIXED), `consumer-behavior/decoy-pricing` (MIXED) |
| Pricing anchors weak | `behavioral-economics/anchoring-in-pricing`, `jdm/anchoring` |
| Default tier ambiguous | `behavioral-economics/default-effect`, `behavioral-economics/status-quo-bias` |
| Friction in checkout | `behavioral-economics/present-bias`, `hci/chunking-in-form-design`, `hci/progressive-disclosure` |
| Social proof missing | `applied-psychology/social-proof`, `consumer-behavior/review-valence-and-volume` |
| Scarcity / urgency cues weak (or, conversely, manipulative) | `consumer-behavior/scarcity-cues-in-marketing` (MIXED), `applied-psychology/scarcity-cialdini` (MIXED) — surface dark-pattern risk if non-scarce inventory |
| Number formatting (price psychology) | `behavioral-economics/left-digit-effect`, `behavioral-economics/partitioned-pricing` |
| Sign-up form over-asks | `hci/chunking-in-form-design`, `behavioral-economics/goal-gradient-effect`, `behavioral-economics/endowed-progress-effect` |
| Trial-to-paid framing | `jdm/loss-aversion`, `jdm/endowment-effect`, `consumer-behavior/post-purchase-rationalization` |
| Onboarding drop-off | `behavioral-economics/goal-gradient-effect`, `applied-psychology/implementation-intentions`, `applied-psychology/habit-formation-cue-routine-reward` |
| Referral / sharing flow | `applied-psychology/reciprocity`, `applied-psychology/social-proof`, `consumer-behavior/referral-likelihood-vs-NPS-validity` (CONTESTED) |
| Email subject lines / CTA buttons | `jdm/framing-effects`, `applied-psychology/social-proof`, `applied-psychology/scarcity-cialdini` (MIXED) |
| Above-the-fold value-prop | `consumer-behavior/brand-asset-distinctiveness`, `applied-psychology/mere-exposure`, `hci/above-the-fold-effect` (CONTESTED) |
| Experiment hypothesis design | `jdm/framing-effects`, `behavioral-economics/default-effect`, plus the construct under test from `~/.claude/skills/advise-bx/references/domain-routing.md` |

## Output augmentation

When the lens fires, cro-auditor appends:

```markdown
## Behavioral-science lens

For each CRO finding above, the underlying mechanism (where applicable):

### Re: <CRO finding>
**Card**: `<domain>/<construct>` (`replication_status: ...`)
**Mechanism**: <how the construct explains the conversion impact>
**Citation**: <bibtex key> → <DOI>
**Effect-size benchmark**: <if the card carries one, quote it as a calibration point>
**Boundary check**: <are this artifact's boundary conditions met>
```

## Special interaction with experiment design

cro-auditor often recommends an A/B test. When it does and the bx-hooks lens fires, add:

```markdown
### Preregistration prompt
If you run this experiment, preregister the hypothesis in a `hypotheses.md` file:
- Primary metric: <name>
- Guardrail metric: <name>
- Predicted direction: <up | down | neutral>
- Predicted effect size: <from the card's effect-size benchmark or a hedge>
- Construct under test: `<domain>/<construct>`
```

This mirrors the discipline in `MattZerg/Research/Experiments/<slug>/HYPOTHESES.md` patterns from Concord-Bench / CINU.

## Hard rules (mirrored from advise-bx)

1. Never invoke a card on `_replication-ledger.md` blacklist.
2. Surface replication status for non-robust cards.
3. Refuse to recommend interventions that activate dark patterns (per advise-bx anti-pattern A9).
4. Card path must resolve to existing file.

## Pre-Phase-2 behavior

If `_knowledge/behavioral-sciences/` has no cards, lens silently no-ops. cro-auditor's normal CRO report ships unchanged.
