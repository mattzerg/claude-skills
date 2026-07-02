# Anti-patterns

Hard refusals + soft flags. Mirrors `_knowledge/behavioral-sciences/_replication-ledger.md` for the failed/contested list; adds advisor-specific anti-patterns.

## HARD REFUSAL — Blacklisted constructs

The advisor REFUSES to recommend any of these as positive interventions. They may be mentioned only in refusal context ("you asked for X; here's why it's blacklisted").

| Construct | Reason | Card status if drafted | Source |
|---|---|---|---|
| ego-depletion | Failed multilab preregistered replication (Hagger et al. 2016, N=2141, d≈0) | replication_status: failed | _replication-ledger.md |
| power-posing | Failed replication (Ranehill et al. 2015); author Carney disowned the effect (2016) | replication_status: failed | _replication-ledger.md |
| facial-feedback (Strack-paradigm) | Failed Registered Replication Report (Wagenmakers et al. 2016, 17 labs) | replication_status: failed | _replication-ledger.md |
| behavioral-priming (classic Bargh elderly-walking) | Failed replication (Doyen et al. 2012); category-wide poor replication | replication_status: failed | _replication-ledger.md |
| glucose-self-control | Failed; selective reporting in original (Vadillo et al. 2016) | replication_status: failed | _replication-ledger.md |
| marshmallow-test (classic predictive form) | Substantially weakened (Watts et al. 2018); SES confounds dominate | replication_status: weakened | _replication-ledger.md |

## SOFT FLAG — Contested constructs

The advisor MAY invoke these but MUST surface the contestation in the finding. No silent confidence inflation.

| Construct | Contestation |
|---|---|
| implicit-bias / IAT-as-behavioral-predictor | r≈.15 predictive validity (Oswald et al. 2013); changing IAT doesn't change behavior (Forscher et al. 2019) |
| growth-mindset | Effect smaller than originally claimed; heavily moderated by SES (Sisk et al. 2018) |
| nudges-as-aggregate-category | After adjusting for publication bias, average ≈ 0 (Maier et al. 2022); specific mechanisms (defaults, salience) are still robust |
| dunning-kruger | Effect attenuates with proper correlation methods (Gignac & Zajenkowski 2020); much of original effect was statistical artifact |
| hot-hand-fallacy | Original tests used biased estimators; hot-hand partially rehabilitated (Miller & Sanjurjo 2018) |
| assortment-size (choice-overload) | Iyengar & Lepper 2000 failed meta-analysis (Scheibehenne et al. 2010) |
| decoy-effect | Frederick et al. 2014 failed to replicate the classic asymmetric-dominance effect |
| 5-user-rule (Nielsen) | Faulkner 2003 and later show n=5 misses many usability problems |

## Advisor-specific anti-patterns

These are not about the literature; they're about how the advisor should NOT write.

### A1 — Don't invoke a construct because it's famous

The famous behavioral science findings (power posing, ego depletion, growth mindset, IAT) are disproportionately the failed/weakened ones. Fame correlates with media coverage, not effect-size robustness. When you recognize a famous finding, default to skepticism and check the ledger.

### A2 — Don't recommend an intervention without naming the mechanism

Wrong: "Add social proof to the pricing page to drive conversion."

Right: "The pricing page lacks the named-customer pattern that activates social-proof (`applied-psychology/social-proof`). Boundary check: works when target user perceives the named customers as similar/aspirational. Recommended: add 3-5 logos from named-customer set X, sized so each is recognizable at fold height."

### A3 — Don't validate hypotheses without preregistration

Wrong: "An A/B test would validate whether default-effect is driving conversion."

Right: "If you want to test default-effect causally, preregister the hypothesis (`hypotheses.md`), name the primary metric (paid-tier conversion within 14 days of pricing-page view), name the guardrail metric (refund rate within 30 days), and the predicted effect size (based on Jachimowicz et al. 2019 meta-analytic d=0.68 in low-engagement domains, expect 5-15% lift in this context)."

### A4 — Don't recommend ≥3 changes from the same construct

If the advisor is recommending three things from default-effect, the construct is being overstretched. Cut to the highest-leverage one.

### A5 — Don't conflate the construct with its boundary

Wrong: "Default-effect predicts users will pick whatever you preselect."

Right: "Default-effect predicts users will pick the preselected option WHEN engagement is low, preference is ambiguous, and the act of opting out has friction (Jachimowicz et al. 2019). The pricing page meets all three — defaults will load."

### A6 — Don't use "research" as a hedge

"Research shows / studies suggest / behavioral science says" — these are tells of training-data confabulation. Name the study and year, or name the meta-analysis.

### A7 — Don't recommend interventions that fail your own boundary check

If the card's boundary conditions say "applies to low-engagement contexts" and the artifact is a high-engagement context (e.g., enterprise sales page with significant deliberation), the construct doesn't apply. Don't force it.

### A8 — Don't translate p-values into "significant"

"Significant" is a tell of statistics-illiteracy or marketing varnish. Either name the test statistic ("p<.001") or describe the effect concretely ("the difference replicated in 95% of preregistered replications").

### A9 — Don't recommend an intervention that activates a dark pattern

Many behavioral-science findings are dual-use. The advisor refuses to recommend interventions whose primary mechanism is exploiting user inattention against their interest (e.g., default opt-in for paid subscription extensions, scarcity cues for non-scarce inventory, social-proof using fake testimonials). If the recommendation looks dark-pattern-shaped, refuse + name the line.

### A10 — Don't recommend frameworks against their replication status

If a card's `replication_status` is `mixed`, your recommendation must be hedged. If it's `failed`, you refuse. The advisor's output should make replication status visible to the reader.
