# Citation Style

Rules for citing cards and underlying DOIs in advisor output.

## Format

Every finding cites in this order:

1. **Card path**: `<domain>/<construct>` (filename without `.md`)
2. **Replication status from the card**: robust | mixed | failed | contested
3. **Bibtex key(s)**: from card's `canonical_citations` frontmatter
4. **DOI(s)**: looked up from `_citations/library.bib`

Inline format:

> Card: `behavioral-economics/default-effect` (robust). Citations: Johnson2003 (DOI: 10.1126/science.1091721), Madrian2001 (DOI: 10.1162/003355301753265543).

## Citation sourcing rules

- **Never cite from training data.** Citations come from the card's frontmatter. Period.
- **If a card cites multiple sources, name the strongest one** — typically the most-recent meta-analysis or the largest preregistered replication.
- **Verify the DOI is in the allowlist** before quoting. Skip findings that depend on uncited papers.
- **Effect sizes are stripped from the card** — quote them when they exist (`d≈0.68`, `r≈.15`, `p<.001`). Don't invent.
- **Year matters.** Prefer post-replication-crisis citations (2015+) when the original is older and the card's status is `mixed` or `contested`. Surface the pre/post split.

## Hedging vocabulary by replication status

| Card status | Allowed phrasing |
|---|---|
| robust | "Evidence is robust." "Replicates across N samples." "Meta-analytic d≈X." |
| mixed | "Evidence is mixed." "Replicates in some paradigms, not others." "Effect sizes vary by domain." |
| contested | "The original claim is contested." "Post-replication-crisis evidence weakens the magnitude originally reported." "The construct exists, the magnitude is disputed." |
| failed | (Should not appear in positive recommendations. If appearing in refusal context: "This finding has failed preregistered replication.") |

## When to surface replication detail

Always surface when:
- The card's status is not `robust`.
- The original paper has a famous name (lay reader will assume robustness without the hedge).
- The recommended intervention is a high-cost change.

Surface lightly when:
- The card's status is `robust` and the literature is uncontroversial.
- The advisor's finding is `LOW` severity.

## Forbidden phrases

These tells suggest training-data confabulation or marketing voice. Never use:

- "Research shows…" (which research?)
- "Studies prove…" (studies can't prove)
- "It's well-established that…" (cite the meta-analysis)
- "Behavioral science suggests…" (which behavioral science?)
- "X is a powerful nudge" (which mechanism? what effect size?)
- "A landmark study by…" (just give the year and DOI)
- "Compelling," "transformative," "drive significant uplift" (marketing varnish)

## When a citation is missing

If the card lacks `canonical_citations` (shouldn't happen after Phase 2 audit, but as a defensive check):

- Refuse to use the card as the basis for a HIGH-severity finding.
- May use as MEDIUM if the boundary check is otherwise tight, flagged with `[citation-missing-from-card]` inline.
- Always trigger an audit-log entry: `state/findings-with-missing-citations.jsonl`.

## Effect size translation

When a card frontmatter or body lists effect sizes, translate them for non-technical Matt without losing precision:

| Cohen's d | Translation |
|---|---|
| d ≥ 0.8 | "large" + numeric (`d=0.85, robust replication`) |
| 0.5 ≤ d < 0.8 | "medium" + numeric |
| 0.2 ≤ d < 0.5 | "small" + numeric (always note this is the post-replication-crisis benchmark for "real but small") |
| d < 0.2 | "very small" + numeric + warn that this size is hard to detect outside well-powered studies |

For r (correlations):

| r | Translation |
|---|---|
| r ≥ 0.5 | "strong correlation" + numeric |
| 0.3 ≤ r < 0.5 | "moderate" + numeric |
| 0.1 ≤ r < 0.3 | "weak" + numeric (the IAT-discrimination relationship is here) |
| r < 0.1 | "very weak; near-zero" + numeric |

## DOI presentation

- Inline: `DOI: 10.1037/0022-3514.74.5.1252`
- In linked-text contexts (if the output is markdown for the vault or rendered HTML): `[Johnson & Goldstein 2003](https://doi.org/10.1126/science.1091721)`
- Never link to publisher-specific URLs (those rot). Always use `https://doi.org/<DOI>`.
