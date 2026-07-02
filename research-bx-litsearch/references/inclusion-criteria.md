# Inclusion / Exclusion Criteria

Default inclusion criteria for adding a citation to a card or to a meta-analysis candidate corpus. Tighten per project.

## Default include

- Peer-reviewed journal article OR pre-registered preprint (PsyArXiv, SSRN, OSF Preprints)
- Reports an empirical study OR is a meta-analysis / systematic review
- Published 1970 or later (older only when seminal)
- Full text accessible (open access OR institutional access)
- DOI resolves via OpenAlex / Crossref
- Not retracted

## Default exclude

- Editorials, commentaries, opinion pieces (unless directly addressing a replication)
- Book reviews
- Conference abstracts without full paper
- Predatory journals (cross-check against Beall's list / DOAJ removal list)
- Retracted papers (flag in retraction section instead)
- Papers behind paywalls with no access path AND no preprint mirror

## For card seeding (≤20 candidate papers per construct)

Tier 1 (must include):
- The seminal paper(s) that introduced the construct
- The most-cited meta-analysis or systematic review on the construct
- Any large preregistered replication (success OR failure)

Tier 2 (include if available):
- 1-2 textbook chapters (for boundary conditions)
- 1-2 recent applications in the construct's primary domain

Tier 3 (often skip):
- Niche extensions / moderation studies
- Theoretical papers without new data
- Commentaries on the seminal paper (unless they raised the failure)

## For meta-analysis candidate corpus (target ≥40 papers)

Tier 1:
- All preregistered replications
- All published replications (success and failure)
- All meta-analyses (so you can use their reference lists)

Tier 2:
- All empirical papers reporting the effect with N > some minimum (often N ≥ 50)
- All empirical papers using a specific paradigm of interest

Tier 3:
- Theoretical papers (for citation completeness, not for effect-size extraction)

Exclude from meta-analysis:
- Original effect papers with no control group
- Non-quantitative replications (qualitative discussion)
- Papers that report only direction without effect size or test statistic

## PRISMA-style screening (for meta-analysis)

When using `research-bx-screen`, run two-coder agreement on the title+abstract pass, then full-text pass. Disagreements escalate to manual adjudication. Mirrors the CINU experiment's adjudication pattern.

## Practical heuristics

- **Citation count is a noisy signal of importance**, but it's better than nothing for triage. Top-50 by citations is a reasonable Tier-1 cut.
- **Recency matters more in domains with replication crises.** For JDM / behavioral econ / social psych: prefer post-2015 evidence whenever the original is older.
- **"Famous" is a red flag, not a green flag.** The most-famous findings in social psych have disproportionately failed replication. Default to skepticism when you recognize the construct.
- **Author has retracted other work** → flag for extra verification but don't auto-exclude. Look at the specific paper's replication record.

## Example: card seeding for "anchoring"

Tier 1:
- Tversky & Kahneman 1974, Science — seminal
- Furnham & Boo 2011, Journal of Socio-Economics — meta-analysis
- Klein et al. 2014, Social Psychology — Many Labs 1 replication (anchoring confirmed across 36 samples)
- Klein et al. 2018, AMPPS — Many Labs 2 replication

Tier 2:
- Mussweiler & Strack textbook chapter on selective accessibility
- Recent applied study in pricing or negotiation

Stop at ~6 candidates for a card. (Cards aren't meta-analyses.)
