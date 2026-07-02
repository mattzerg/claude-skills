---
name: gsc-skill
description: Read Google Search Console data for zergai.com and product subdomains — real queries hitting Zerg pages, click-through, position. Free signal critical for content-distribution, programmatic-seo, and growth-dashboard. Reads only — never modifies properties. Verbs — `properties` (list), `top-queries <site> [--days N]`, `top-pages <site> [--days N]`, `query <site> <q>`. **Requires Matt to complete OAuth bootstrap** once (`bootstrap` verb runs it); after that, tokens cached at `~/.claude/skills/gsc-skill/tokens/`.
---

# gsc-skill

Google Search Console read access. Free, real query data for SEO + content surfacing.

## One-time setup

Matt needs to do this once. Claude can prep the OAuth client but cannot complete the consent dance.

1. **Enable Search Console API** at https://console.cloud.google.com/apis/library/searchconsole.googleapis.com — pick the same GCP project gmail-skill uses (re-uses its OAuth client).
2. **Add the `webmasters.readonly` scope** to the OAuth consent screen if not already present.
3. Run `python3 ~/.claude/skills/gsc-skill/read_gsc.py bootstrap` — opens a browser for Google sign-in. On success, tokens cache at `~/.claude/skills/gsc-skill/tokens/<email>.json`.
4. Verify with `python3 ~/.claude/skills/gsc-skill/read_gsc.py properties`.

## Verbs

### `properties`
List GSC properties this Google account has access to.

```bash
python3 ~/.claude/skills/gsc-skill/read_gsc.py properties
```

### `top-queries <site> [--days N] [--limit N]`
Top search queries hitting the site in the last N days (default 28).

```bash
python3 ~/.claude/skills/gsc-skill/read_gsc.py top-queries https://zergai.com/ --days 7
```

### `top-pages <site> [--days N] [--limit N]`
Top pages by clicks in the period.

```bash
python3 ~/.claude/skills/gsc-skill/read_gsc.py top-pages https://zergai.com/ --days 28
```

### `query <site> <q> [--days N]`
Performance of a specific query on the site.

```bash
python3 ~/.claude/skills/gsc-skill/read_gsc.py query https://zergai.com/ "ai cro tool" --days 28
```

## Output

Per row: `<rank>. clicks=<N>  impressions=<N>  ctr=<pct>  position=<avg>  "<query-or-page>"`.

## Status

**SCAFFOLD ONLY — script not yet implemented.** This SKILL.md exists so the skill description is loadable; first `read_gsc.py` will land in a follow-up once Matt confirms (a) which Google account owns GSC for zergai.com, and (b) whether to re-use gmail-skill's OAuth client or create a dedicated one. **Do not invoke this skill yet** — it will fail with "not implemented." File this against next-action queue position 9 (GSC wire-up).

## When to use (post-implementation)

- programmatic-seo content scoring — pick topics with rising impressions, falling CTR.
- content-distribution — verify newly-launched blog post is getting search traffic within a week.
- growth-dashboard weekly run — add "top growing query last week."
- cro-auditor — pair with low-CTR queries to find pages needing TITLE/meta rewrites.
