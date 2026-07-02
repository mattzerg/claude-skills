---
name: brand-kit-creator
description: Collect, normalize, and package brand assets into a usable repository with logos, favicons, imagery, collateral, design tokens, provenance, and a concise asset catalog. Use when creating or refreshing a brand kit from scattered repo/vault assets.
---


# Brand Kit Creator

Use this skill when Matt asks to collect brand assets, make a brand kit, package logos, normalize design tokens, or turn scattered marketing files into a usable asset repository.

## Workflow

1. Inventory assets from the vault and relevant product repos. Prefer vector/source files first, then canonical rendered assets, then delivery PDFs.
2. Exclude generated noise by default: `node_modules`, `.git`, build outputs, screenshots from reviews, cache folders, and unrelated third-party logos.
3. Create or update a repository with this shape:

```
Brand/
  README.md
  brand-guide.md
  asset-catalog.md
  assets/
    logos/
    favicons/
    website/
    marketing/
    collateral/
  tokens/
  templates/
```

4. Copy assets, never move originals. Preserve filenames when useful; rename only when the destination needs clearer canonical names.
5. Record provenance in `asset-catalog.md`: destination path, source path, asset type, and notes.
6. Create machine-readable tokens when the source material supports it: JSON and CSS are enough unless the user asks for another format.
7. Mark gaps explicitly: missing Figma/design files, product marks that are only favicons, old assets, unclear currentness.

## Quality Bar

- The kit must be usable by an engineer or marketer without asking where the logo/color/PDF lives.
- Do not invent brand rules that are not supported by live assets or reviewed collateral. Inferences are allowed, but label them as derived.
- Keep source-of-truth clear: product repos or Claude skills can remain canonical; the brand repository is the packaged working set.
