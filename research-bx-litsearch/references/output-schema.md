# Output Schema

## `state/candidates/<construct>-YYYY-MM-DD.md`

Human-readable candidate list, produced by `discover` mode.

```markdown
# Candidate corpus — <construct> — YYYY-MM-DD

**Construct**: <construct>
**Domain**: <domain>
**Search queries**: <list of queries run>
**Concept ID (OpenAlex)**: <ID if used>
**Hits before dedup**: <N>
**Hits after dedup**: <N>
**Selected (Tier 1+2+3)**: <N>

## Tier 1 — Must include

| # | DOI | Year | Authors | Title | Cited | Type | Notes |
|---|-----|------|---------|-------|-------|------|-------|

## Tier 2 — Include if available

(same columns)

## Tier 3 — Likely skip for card; relevant for meta-analysis

(same columns)

## Replication record

- Seminal paper: <DOI> (<year>)
- Replication failure(s): <list of DOIs with year>
- Meta-analysis: <DOI with pooled effect size if extracted>
- Status (inferred): robust | mixed | failed | contested | untested

## Audit notes

- Verifications performed: <count>
- Verifications failed: <count>
- Bibtex keys added to library.bib: <list>
- Bibtex keys already present: <list>
- Verified-doi-allowlist rows written: <count>

## Next step

- Card draft: <link to draft once written>
- Audit by research-bx-audit: <pending | passed | failed>
```

## `state/candidates/<construct>.sqlite`

For meta-analysis use. Schema:

```sql
CREATE TABLE candidates (
  id INTEGER PRIMARY KEY,
  doi TEXT UNIQUE NOT NULL,
  bibtex_key TEXT NOT NULL,
  year INTEGER,
  authors TEXT,  -- JSON array
  title TEXT,
  journal TEXT,
  cited_by_count INTEGER,
  type TEXT,  -- article | book-chapter | book | dissertation | review | meta-analysis
  tier INTEGER,  -- 1, 2, or 3
  is_retracted BOOLEAN DEFAULT 0,
  has_full_text BOOLEAN,
  abstract TEXT,
  openalex_id TEXT,
  verified_at TEXT,  -- ISO-8601
  verified_source TEXT,  -- openalex | crossref | semanticscholar | doi.org | manual
  notes TEXT
);

CREATE TABLE search_log (
  id INTEGER PRIMARY KEY,
  ran_at TEXT NOT NULL,
  query TEXT,
  source TEXT,  -- openalex | exa | firecrawl | semanticscholar
  hits INTEGER,
  notes TEXT
);

CREATE INDEX idx_candidates_doi ON candidates(doi);
CREATE INDEX idx_candidates_tier ON candidates(tier);
CREATE INDEX idx_candidates_year ON candidates(year);
```

## `state/audit-log.jsonl`

Append-only. Each line:

```json
{"ts": "2026-05-29T03:14:15Z", "action": "verify", "doi": "10.xxxx/yyyy", "source": "openalex", "result": "ok", "bibtex_key": "Smith2020"}
{"ts": "2026-05-29T03:14:18Z", "action": "verify", "doi": "10.xxxx/zzzz", "source": "openalex", "result": "fail", "reason": "not_found_in_openalex_or_crossref"}
{"ts": "2026-05-29T03:15:01Z", "action": "discover", "construct": "anchoring", "hits": 247, "after_dedup": 198, "selected": 12}
```

Read by `research-bx-audit` to verify that every citation in a card or paper passed through this skill.

## Frontmatter updates to cards

When `verify-batch` mode runs on a card:

- Updates `last_verified: YYYY-MM-DD` in card frontmatter
- Does NOT modify any other field (cards are otherwise human-edited)

## Errors and refusals

`research-bx-litsearch` writes to `state/audit-log.jsonl` and refuses to:

- Add a row to `verified-doi-allowlist.md` if verification failed
- Add a bibtex entry to `library.bib` without a paired allowlist row
- Update a card's `last_verified` if any `canonical_citations` entry failed verification
- Discover candidates for a construct on the `_replication-ledger.md` blacklist without explicit `--ledger-aware` flag (which biases search toward replication-failure papers)
