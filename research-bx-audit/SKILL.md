---
name: research-bx-audit
description: Pre-commit / pre-load validator for the behavioral-sciences knowledge layer. Lint-checks framework cards against the schema, citation allowlist, and replication ledger. Run before any card is committed, before advise-bx loads cards, and before any research-track preprint cites a card. Hard refusals on missing citations, schema violations, blacklisted-construct positive recommendations, stale verifications (over 180 days), and orphaned bibtex keys. Trigger phrases — "audit the knowledge layer", "lint the cards", "validate a card", "audit before commit", "card health check", "is the bx knowledge layer clean".
---

# Research / Behavioral-Sciences — Audit Gate

Validates that every framework card in `MattZerg/_knowledge/behavioral-sciences/` conforms to schema, has DOI-verified citations, respects the replication ledger, and is internally consistent. Runs before commits, before advisor loads, and before any preprint citation.

## When to invoke

- Before committing a new or modified card.
- Before `advise-bx` loads cards for an audit.
- Before `research-bx-write` renders a preprint draft.
- Periodically (Phase 1 follow-up: a pre-commit hook will wrap this).
- After `research-bx-litsearch` runs `verify-batch` on a card (audit confirms allowlist consistency).

## Modes

### `card <path>` — single-card lint

Runs the 10 lint rules from `_schema/card-schema.md` plus consistency checks against `_replication-ledger.md` and `_citations/verified-doi-allowlist.md`.

### `corpus` — whole knowledge layer

Iterates every `.md` in every domain folder + cross-references. Outputs `state/audit-report-YYYY-MM-DD.md` with per-card pass/fail and aggregate stats.

### `pre-commit <changed-paths>` — git-hook entry-point

Same as `card` mode but limited to changed files. Exits non-zero on any failure → blocks commit.

## Lint rules (machine-checked)

| # | Rule | Failure mode |
|---|---|---|
| L1 | Frontmatter parses as YAML | ParseError |
| L2 | All required frontmatter fields present | MissingField |
| L3 | `domain` matches parent folder name | DomainMismatch |
| L4 | Every `canonical_citations` bibtex key exists in `library.bib` | OrphanedKey |
| L5 | Every key in L4 also exists in `verified-doi-allowlist.md` | UnverifiedCitation |
| L6 | Every `contested_by` key (if present) passes L4 and L5 | OrphanedContestation |
| L7 | If `replication_status` ∈ {mixed, failed, contested} → `contested_by` must be non-empty | MissingContestation |
| L8 | All 6 required body sections present in order | MissingSection |
| L9 | `last_verified` ≤ today | FutureVerification |
| L10 | `confidence` consistent with `replication_status` (robust → high\|medium; failed → low) | ConfidenceMismatch |

## Cross-source consistency rules

| # | Rule | Failure |
|---|---|---|
| X1 | Construct on `_replication-ledger.md` blacklist → card MUST have `replication_status: failed` | BlacklistMismatch |
| X2 | Construct on contested-list → card MUST have `replication_status: contested` OR `mixed` and surface contestation | ContestedNotSurfaced |
| X3 | `related_cards` entries must resolve to existing card files | DanglingRelation |
| X4 | No two cards in different domains share the same `construct` slug (except scoped variants — those use distinct slugs) | CrossDomainDuplicate |
| X5 | If `last_verified` is >180 days old → STALE (warning, not error) | StaleVerification |

## Output

```markdown
# Audit Report — YYYY-MM-DD

## Summary
- Cards scanned: <N>
- Pass: <N>
- Warnings: <N> (stale verifications only)
- Fail: <N>
- Verdict: PASS | FAIL

## Per-card

### `<domain>/<construct>.md` — PASS | FAIL
- L1 ✓ / L2 ✓ / … / X5 ⚠️ (last_verified=2025-09-12, >180 days)

(repeat per card)

## Cross-source summary

- Blacklist mismatches: <N>
- Unverified citations: <list>
- Orphaned bibtex keys (in library.bib but not cited by any card): <list>
- Dangling relations: <list>
- Cross-domain duplicates: <list>

## Stale verifications (>180 days)

| Card | last_verified | Days stale |
|---|---|---|
```

## Exit codes

- 0 — all pass (warnings allowed)
- 2 — at least one lint failure
- 3 — at least one cross-source consistency failure
- 4 — corrupted vault tree (missing _schema, _citations, etc.)

## Hard refuses

- Refuses to mark a card as passing if any lint or consistency rule fails.
- Refuses to silently ignore stale verifications — they appear in output even when score is PASS.
- Refuses to load cards from outside `_knowledge/behavioral-sciences/`.

## Pairs with

- `research-bx-litsearch verify-batch` — refresh citations to clear stale warnings.
- `advise-bx` — runs `corpus` mode internally before loading (defensive check).
- Pre-commit hook (Phase 1 follow-up) — wraps `pre-commit` mode.

## Voice

Reports are short, factual, table-shaped. No prose. See `MattZerg/_style/expert_voice_behavioral_sciences.md`.
