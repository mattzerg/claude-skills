# OpenAlex API — Reference

OpenAlex is the primary discovery + verification backend. Free, no key required, comprehensive coverage of scholarly papers.

## Base URL

`https://api.openalex.org/works`

## Key endpoints

### Verify a single DOI

```bash
curl -s "https://api.openalex.org/works/doi:10.1037/0022-3514.74.5.1252" | jq '{
  doi: .doi,
  title: .title,
  year: .publication_year,
  authors: [.authorships[].author.display_name],
  cited_by_count,
  is_retracted,
  primary_location: .primary_location.source.display_name
}'
```

Success criterion: `.doi` field matches the input (case-insensitive), HTTP 200, `is_retracted` is false.

### Discover by concept/topic

```bash
# Top-cited papers on "prospect theory"
curl -s "https://api.openalex.org/works?search=prospect%20theory&per_page=25&sort=cited_by_count:desc" | \
  jq '.results[] | {doi, title, year: .publication_year, cited_by_count}'
```

### Find replication failures explicitly

```bash
# Search for "replication" + construct
curl -s "https://api.openalex.org/works?search=ego%20depletion%20replication%20failure&per_page=25&sort=cited_by_count:desc" | \
  jq '.results[] | {doi, title, year: .publication_year}'
```

### Filter by concept ID

OpenAlex assigns concept IDs (e.g., behavioral economics ≈ C162324750). Use these for cleaner filtering than free-text:

```bash
curl -s "https://api.openalex.org/works?filter=concepts.id:C162324750&per_page=50&sort=cited_by_count:desc"
```

Concept lookup:
```bash
curl -s "https://api.openalex.org/concepts?search=behavioral%20economics" | jq '.results[0] | {id, display_name}'
```

## Useful concept IDs for our 7 domains

| Domain | Concept | OpenAlex ID |
|---|---|---|
| jdm | Judgment and decision making | search at runtime |
| behavioral-economics | Behavioral economics | C162324750 (verify) |
| consumer-behavior | Consumer behaviour | search at runtime |
| user-research | Usability / UX research | search at runtime |
| market-research | Marketing research | search at runtime |
| applied-psychology | Applied psychology | search at runtime |
| hci | Human-computer interaction | search at runtime |

(Skill resolves these at runtime via `/concepts?search=...` rather than hardcoding — IDs are stable but the canonical list lives at the API.)

## Rate limits

- Polite pool (with email in User-Agent): 100,000 calls/day
- Default per-second: 10
- Use `mailto=matthew@matteisn.com` in query string or `User-Agent: research-bx-litsearch/0.1 (mailto:matthew@matteisn.com)`

```bash
curl -s -A "research-bx-litsearch/0.1 (mailto:matthew@matteisn.com)" \
  "https://api.openalex.org/works/doi:10.1126/science.1091721"
```

## Retraction detection

`is_retracted: true` in the response → flag immediately. The pipeline:

1. Update `verified-doi-allowlist.md` entry: change `Verified Source` to `RETRACTED-YYYY-MM-DD`.
2. Grep all cards for the bibtex key; for each, update `replication_status` to `failed` and add a `retraction_note` to frontmatter.
3. Push the retraction to `_replication-ledger.md` under a new `## Retractions` section.

## When OpenAlex misses

OpenAlex coverage is broad but not exhaustive. Fallback chain:

1. OpenAlex (primary)
2. Crossref (`https://api.crossref.org/works/<DOI>`)
3. Semantic Scholar (`https://api.semanticscholar.org/graph/v1/paper/DOI:<DOI>`)
4. `doi.org` HEAD redirect (lowest signal — confirms DOI resolves but no metadata)

If all four fail → reject the citation. Don't write it to `library.bib`.

## Common failure modes

- **DOI typo**: ".5" vs ".05" in the issue number. Always copy-paste, never retype.
- **DOI for a different version**: preprint vs published version have different DOIs. Prefer the published version when both exist.
- **Mirror/redirect DOIs**: some publishers issue multiple DOIs for the same work. OpenAlex resolves these; trust its canonical answer.
- **Non-research outputs**: editorials, retraction notices, book reviews. Check `.type` — accept only `article`, `book-chapter`, `book`, `dissertation` for our purposes.
