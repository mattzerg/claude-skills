# Domain Routing

Map an artifact type to the domains most likely to surface useful constructs.

## Default routing matrix

| Artifact type | Primary domains | Secondary domains |
|---|---|---|
| CTA copy (button text, hero copy) | jdm, consumer-behavior, applied-psychology | hci |
| Pricing page | behavioral-economics, consumer-behavior, jdm | hci |
| Onboarding flow / activation | behavioral-economics, applied-psychology, hci | user-research |
| Form / input UI | hci, user-research | applied-psychology |
| Email subject lines | applied-psychology, consumer-behavior | jdm |
| Email body / lifecycle | applied-psychology, behavioral-economics | consumer-behavior |
| Landing page hero | applied-psychology, consumer-behavior, hci | jdm |
| Dashboard / data UI | hci, jdm | user-research |
| Strategy doc / pitch | jdm, market-research | behavioral-economics |
| Survey / instrument design | user-research, market-research | jdm |
| Notification copy | applied-psychology, jdm | hci |
| Settings / defaults UI | behavioral-economics, hci | applied-psychology |
| Error message | hci, applied-psychology | (none) |
| Social proof element | applied-psychology, consumer-behavior | behavioral-economics |
| Referral / sharing UI | applied-psychology, consumer-behavior | behavioral-economics |
| Checkout / payment flow | behavioral-economics, hci, applied-psychology | consumer-behavior |
| Trial-to-paid conversion | behavioral-economics, consumer-behavior, applied-psychology | jdm |

## Routing rules

1. Match the artifact's primary purpose to the matrix.
2. Load all constructs in the primary domains where `applies_to_zerg` includes the artifact's tag (`pricing`, `copy`, `onboarding`, `checkout`, `defaults`, etc.).
3. Pull a smaller set from secondary domains, scoped to constructs explicitly tagged for the artifact type.
4. Always run anti-pattern check across all 7 domains (any blacklisted construct that might apply).

## When to ignore the matrix

- Matt names the domain explicitly ("apply JDM lens to this") — use only that domain.
- The artifact is multi-purpose (pricing page that also functions as social-proof page) — load primary domains for each purpose and dedup.
- Cross-domain construct (social-proof, reciprocity, default-effect) is suggested by the artifact — load the construct's primary domain card regardless of routing.

## Anti-routing (when NOT to apply a domain)

- Market research domain is rarely relevant to a tactical artifact (button copy, form field). Reserve for strategy / segmentation / measurement-design work.
- JDM is sometimes wrong-tool for HCI tasks (a form field has interaction-design constructs, not just judgment heuristics). Don't force-fit.
- Behavioral economics applies to choice contexts. Don't apply to non-choice artifacts (e.g., a dashboard whose purpose is information display).

## Per-artifact construct shortlists

These are the constructs MOST likely to apply per artifact type. Use as a heuristic, not a hard list — actual loading runs frontmatter queries.

### Pricing page
- behavioral-economics: default-effect, anchoring-in-pricing, decoy-effect (if applicable), left-digit-effect, partitioned-pricing, transaction-utility
- consumer-behavior: price-quality-heuristic, price-tier-mid-bias, decoy-pricing, scarcity-cues-in-marketing
- jdm: framing-effects, loss-aversion, ambiguity-aversion

### Onboarding flow
- behavioral-economics: default-effect, status-quo-bias, commitment-devices, goal-gradient-effect, endowed-progress-effect
- applied-psychology: implementation-intentions, habit-formation-cue-routine-reward, identity-based-motivation, self-efficacy
- hci: progressive-disclosure, recognition-over-recall, mental-models-and-conceptual-mismatch

### CTA copy
- jdm: framing-effects, loss-aversion, regret-aversion, certainty-effect
- consumer-behavior: scarcity-cues-in-marketing (with hedge), category-entry-points
- applied-psychology: social-proof, authority-cue, commitment-consistency (with care — refuse manipulative framings)

### Form / input UI
- hci: chunking-in-form-design, error-prevention-vs-error-message, progressive-disclosure, recognition-over-recall, fitts-law
- user-research: leading-questions-in-interviews (transferred to form-question design)

### Landing page hero
- applied-psychology: mere-exposure, social-proof
- consumer-behavior: brand-attachment, lay-theories-in-product-judgment, brand-asset-distinctiveness
- hci: f-pattern-vs-z-pattern-scanning (with hedge — contested)
