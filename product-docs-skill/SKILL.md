---
name: product-docs-skill
description: Scaffold or audit a Zerg product's docs surface. Two verbs — `scaffold <slug>` copies `~/zerg/_templates/zerg-product/product-docs/` into `~/zerg/<slug>/docs/` and token-substitutes; `audit <slug>` checks presence of 7 canonical sections, dead internal links, and freshness (changelog vs git log staleness). USE PROACTIVELY when Matt creates a new product OR before any product ships externally. Anchored on canonical-patterns.md §17. Never auto-publishes.
allowed-tools: Bash, Read, Write
---


# Product Docs Skill

Owns the per-product docs surface for every Zerg microproduct. Scaffolds from the canonical template, then audits for drift before launch.

## When to use

- "Scaffold docs for `<slug>`"
- "Audit docs for `<slug>`" / "Is `<slug>`'s docs ready?"
- "Set up product-docs for the new product"
- Before any product ships externally — gate via `launch-ops` `product-docs-present`
- After a refactor that changes API surface — audit catches drift

## Verbs

### `scaffold <slug>`

```bash
python3 ~/.claude/skills/product-docs-skill/run.py scaffold <slug> \
  [--from-backlog PATH]
```

Copies `~/zerg/_templates/zerg-product/product-docs/` into `~/zerg/<slug>/docs/` and token-substitutes from the launch-backlog frontmatter. Idempotent — files that already exist are left untouched.

Token substitutions:
- `{{PRODUCT_SLUG}}` — the slug
- `{{PRODUCT_NAME}}` — `name` field from backlog frontmatter
- `{{PRODUCT_DOMAIN}}` — `domain` field
- `{{PRODUCT_TAGLINE}}` — `tagline` field
- `{{PRODUCT_DESCRIPTION}}` — `description` field

Default backlog path: `MattZerg/Projects/Zerg-Production/Growth/launch-backlog/<slug>.md`. Override with `--from-backlog`.

### `audit <slug>`

```bash
python3 ~/.claude/skills/product-docs-skill/run.py audit <slug> \
  [--output PATH] [--strict]
```

Runs 5 checks against `~/zerg/<slug>/docs/`. `--strict` promotes D5 from MED to HIGH. With `--output`, writes a markdown report; without, prints to stdout. Exit code = number of HIGH findings (0 = clean).

## Audit checks

| Code | Severity | Check |
|------|----------|-------|
| D1 | HIGH | `docs/README.md` exists |
| D2 | HIGH | README has all 6 canonical H2 sections (What it is / Quick start / Concepts / API / Frontend / Status) — per canonical-patterns.md §17 |
| D3 | HIGH | All 7 sibling files present: `getting-started.md`, `architecture.md`, `what-can-i-build.md`, `api-backend.md`, `web-frontend.md`, `faq.md`, `changelog.md` |
| D4 | HIGH | No dead internal links — every relative link in any `.md` resolves to an existing file under `docs/` |
| D5 | MED | `changelog.md` last entry is within 90 days OR git log shows no commits to `~/zerg/<slug>/` since last entry |

## Anchoring sources

- `canonical-patterns.md §17` — canonical docs shape (6 H2 sections + 7 sibling files)
- `~/zerg/web/docs/` — reference product, the shape every other product mirrors
- `~/zerg/_templates/zerg-product/product-docs/` — source template the scaffold verb copies from

## Output

Stdout (default) or `--output` markdown file:
- Findings table: code, severity, message, file path
- Manifest: files checked, total HIGH, total MED, exit code
- Suggested next action when HIGH findings exist

## Hard rules

- Never auto-publishes. Writes inside `~/zerg/<slug>/docs/` only.
- Scaffold is idempotent — never overwrites an existing file. Audit issues drift findings; humans resolve.
- Audit is read-only. No fixes applied automatically.
