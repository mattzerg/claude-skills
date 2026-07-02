---
name: defuddle
description: Extract clean markdown from a web page with the local Defuddle CLI — strips nav/ads/clutter to save tokens. Prefer over WebFetch for standard articles, blog posts, and online docs when you need the readable body text. Free and local (no API cost), unlike firecrawl-scrape. Do NOT use for URLs ending in .md (already markdown — use WebFetch) or for JS-heavy SPAs / login-walled pages (use firecrawl-scrape or playwright). USE PROACTIVELY whenever Matt pastes an article URL "read this / summarize this / pull this in" and the page is a normal content page.
---

# defuddle

Local, free, token-cheap web→clean-markdown. Adapted from `kepano/obsidian-skills` (Steph Ango / Obsidian), evaluated 2026-06-07 — see `MattZerg/Skills/setup-ideas-evaluation-2026-06.md`.

**CLI:** `defuddle` (installed globally via npm; `defuddle --version` to confirm). If missing: `npm install -g defuddle`.

## Usage

```bash
defuddle parse <url> --md                  # clean markdown body (default choice)
defuddle parse <url> --md -o content.md    # save to file
defuddle parse <url> -p title              # just a metadata field
defuddle parse <url> -p description
defuddle parse <url> --json                # both HTML + markdown
```

## When to use which web reader (Matt's stack)

| Tool | Use for | Cost |
|---|---|---|
| **defuddle** | standard articles / blog posts / docs — readable body, lowest tokens | free, local |
| `firecrawl-scrape` | JS-rendered SPAs, multiple URLs, structured extraction | paid API |
| `WebFetch` | quick Q&A over a page, or a `.md` URL | built-in |
| `playwright` / `chrome-devtools` | login-walled or interaction-required pages | local |

Default to **defuddle** for plain content pages — it's the token-cheapest and pairs well with saving the result into the Obsidian vault (use the `obsidian-markdown` skill for vault syntax).

## Anti-patterns
- `.md` URLs → use WebFetch (already markdown).
- SPA / paywalled / login-walled → defuddle returns clutter or nothing; switch to firecrawl/playwright.
- Don't pipe untrusted page output straight into a shell command.
