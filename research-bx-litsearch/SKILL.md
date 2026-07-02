---
name: research-bx-litsearch
description: Literature search and citation verification for the behavioral-sciences knowledge layer and research-track meta-analyses. Use when adding a new framework card to MattZerg/_knowledge/behavioral-sciences/, when populating a meta-analysis candidate corpus, or when verifying a single DOI before any card or research-track artifact may cite it. Anchors on real OpenAlex / Crossref / Semantic Scholar / exa+firecrawl hits — never on training-data citations. Outputs candidate paper list (SQLite + markdown), writes verified entries to _citations/library.bib and _citations/verified-doi-allowlist.md. Mandatory entry-point for any card creation. Trigger phrases — "lit-search prospect theory", "find papers on default effect", "verify DOI 10.xxxx", "build candidate corpus for meta-analysis on X", "add card for a construct".
---

# Literature Search & Citation Verification (Behavioral Sciences)

Source-grounded literature search for the behavioral-sciences knowledge layer (`MattZerg/_knowledge/behavioral-sciences/`) and the research-track meta-analysis pipeline.

## Hard gate

**No card and no research-track output may cite a paper that has not passed through this skill's verification.** Training-data citations are forbidden. The only allowed citation sources are:

1. OpenAlex API (`https://api.openalex.org/works/doi:<DOI>`)
2. Crossref API (`https://api.crossref.org/works/<DOI>`)
3. Semantic Scholar API (`https://api.semanticscholar.org/graph/v1/paper/DOI:<DOI>`)
4. doi.org redirect resolution (HTTP 30x to a real publisher URL)
5. `exa:search` + `firecrawl-search` for discovery, but the resulting DOI MUST still be verified via 1–4

## Modes

### Mode 1 — `discover` (find candidate papers for a construct)

Input: construct name (e.g., `prospect-theory`) + optional inclusion criteria.

Steps:
1. Query OpenAlex `/works?search=<construct>&filter=...` for high-cited papers
2. Query Semantic Scholar for the seminal paper and its top-cited references
3. Run `exa:search` for "<construct> review meta-analysis replication"
4. Run `firecrawl-search` against psychology-section preprint servers (PsyArXiv, SSRN)
5. Dedup by DOI. Sort by citation count + recency.
6. Write candidate list to `state/candidates/<construct>-YYYY-MM-DD.md` (top 20 by citation count, plus top 5 most-recent reviews, plus any replication-failure hits).
7. For meta-analysis use, also write to SQLite at `state/candidates/<construct>.sqlite` with full metadata.

Output: candidate list ready for screening (Phase 2 of pipeline) or card drafting.

### Mode 2 — `verify` (single DOI)

Input: a DOI string.

Steps:
1. Query Crossref: `curl -s "https://api.crossref.org/works/<DOI>"`. If 200 and `.message.DOI` matches input → verified=true, source=crossref.
2. If 4xx, query OpenAlex: `curl -s "https://api.openalex.org/works/doi:<DOI>"`. If valid → verified=true, source=openalex.
3. If both fail, query doi.org HEAD: `curl -sI "https://doi.org/<DOI>"`. If 30x to a publisher → verified=true, source=doi.org.
4. If all fail → verified=false, reason= unresolved.
5. On verified=true: extract canonical metadata (authors, year, title, journal, volume, pages). Append to `_citations/library.bib` if not present (compose bibtex key from first-author-lastname + year). Append a row to `_citations/verified-doi-allowlist.md`.
6. Return: bibtex key + DOI + verified source + verified date.

### Mode 3 — `verify-batch` (a card's `canonical_citations`)

Input: a card .md path.

Steps:
1. Parse the card's frontmatter. Extract `canonical_citations` and `contested_by` bibtex keys.
2. For each key, look up DOI in `library.bib`. If absent → error: missing bibtex entry.
3. For each DOI, run `verify` mode.
4. Update `last_verified` in the card's frontmatter on success.
5. Block (refuse to mark verified) if ANY citation fails.

## Anti-hallucination rules

- **Never invent a DOI.** If you don't have one in hand, run mode 1 and find one.
- **Never invent author names.** Author lists come from API responses, period.
- **Never invent a year.** Year comes from the verified API response.
- **Never assume "this is well-known so I can write it from memory."** The whole point of this skill is to break that habit.
- **A bibtex key in `library.bib` without a row in `verified-doi-allowlist.md` is invalid.** Both must exist before any card may cite it.
- **A construct on the `_replication-ledger.md` blacklist cannot be invoked positively** regardless of how many DOIs you verify for the original paper. The original paper's DOI being real does not make the claim true.

## Inputs / outputs (file paths)

| Path | Purpose |
|---|---|
| `state/candidates/<construct>-YYYY-MM-DD.md` | Candidate list for screening |
| `state/candidates/<construct>.sqlite` | Same data, queryable for meta-analysis |
| `MattZerg/_knowledge/behavioral-sciences/_citations/library.bib` | Appended on verify |
| `MattZerg/_knowledge/behavioral-sciences/_citations/verified-doi-allowlist.md` | Appended on verify |
| `state/audit-log.jsonl` | Append-only log of all verifications and failures |

## When to invoke

- **Always** before drafting any card for `_knowledge/behavioral-sciences/<domain>/<construct>.md`.
- **Always** before adding a citation to a research-track meta-analysis manuscript.
- **Always** before flipping a card's `last_verified` date.
- **Always** when a user hands you a "famous study" claim to verify ("did Tversky really say…").

## When NOT to invoke

- General web research that won't end up in a card or paper.
- Drafting non-academic Zerg content (marketing copy, internal notes).
- Quoting from memory in casual conversation (still mark uncertainty, but don't run this skill).

## Pairs with

- `research-bx-screen` — takes this skill's candidate list, applies inclusion/exclusion criteria.
- `research-bx-extract` — extracts effect sizes from the included papers.
- `research-bx-audit` — validates that every citation in a card or paper passed through this skill.

## Hard refuse

- Refuse to write to `library.bib` or `verified-doi-allowlist.md` if any verification step failed.
- Refuse to verify a DOI that returns a retraction notice — instead, update the original entry's row in `verified-doi-allowlist.md` to `RETRACTED-YYYY-MM-DD` and flag any citing cards.
- Refuse to add a paper to a candidate list if its DOI does not resolve via API.

## Voice

Outputs are short, factual, structured. No marketing language. Lists and tables preferred over prose. See `MattZerg/_style/expert_voice_behavioral_sciences.md`.
