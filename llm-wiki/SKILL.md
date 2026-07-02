---
name: llm-wiki
description: Distill a pile of raw sources (papers, scraped articles, notes, data) into a compact, interlinked Obsidian wiki the agent reads instead of the originals — the Karpathy LLM Wiki / raw→wiki→outputs pattern, for token-efficient knowledge bases. USE PROACTIVELY when Matt has a research corpus to compress and reuse (competitive-review insights, the Sci-Fi Innovation Tracker, a topic deep-dive), says "build a knowledge base / second brain on X", "distill these sources", "raw/wiki/outputs", or when a task keeps re-reading the same big raw files. Pairs with defuddle (clean web→raw) and obsidian-markdown (wiki syntax).
---

# llm-wiki

A knowledge base where an LLM reads raw sources **once**, distills them into a
compact interlinked `wiki/`, and from then on the agent reads only the wiki —
never the bulky originals. That's the token-saving payoff (Karpathy's LLM Wiki,
16M views). Three folders: `raw/` (sources, append-only) → `wiki/` (distilled
articles + index) → `outputs/` (deliverables built from the wiki).

Built 2026-06-07 from the pattern surfaced in two self-sent reels — see
`MattZerg/Skills/setup-ideas-evaluation-2026-06.md`. Knowledge bases live under
`MattZerg/KnowledgeBases/<kb>/` by default (Obsidian-native).

## Plumbing (deterministic — `distill.py`)

```bash
python3 ~/.claude/skills/llm-wiki/distill.py init   <kb>                 # scaffold + CLAUDE.md schema
python3 ~/.claude/skills/llm-wiki/distill.py ingest <kb> <url|path> ...  # URLs via defuddle, files copied
python3 ~/.claude/skills/llm-wiki/distill.py plan   <kb>                 # propose article worklist from raw/
python3 ~/.claude/skills/llm-wiki/distill.py index  <kb>                 # rebuild wiki/index.md
python3 ~/.claude/skills/llm-wiki/distill.py status <kb>                 # counts + staleness
# --root DIR to put the KB somewhere other than the vault default.
```

## Distillation (the LLM step — you do this)

After `ingest` + `plan`, open `<kb>/CLAUDE.md` (the per-KB schema) and `wiki/_worklist.md`:
1. For each worklist article, read **only its mapped raw sources**.
2. Write a dense `wiki/<Concept>.md` — frontmatter (`tags`, `sources:`), encyclopedia
   tone, `[[wikilinks]]` to related articles (use the `obsidian-markdown` skill).
3. Deduplicate across articles — one fact, one home; link don't repeat.
4. `distill.py index <kb>` to refresh the index.
5. Downstream tasks now read `wiki/` only.

## Workflow example

```bash
distill.py init sci-fi-innovations
distill.py ingest sci-fi-innovations https://example.com/some-essay ~/Downloads/notes.md
distill.py plan sci-fi-innovations      # -> wiki/_worklist.md
# ...agent distills raw -> wiki articles per CLAUDE.md...
distill.py index sci-fi-innovations
```

## When to use vs. siblings
- `claude-mem` = automatic session memory; `llm-wiki` = a deliberate, curated corpus you control.
- `defuddle` = get clean markdown into `raw/`; `obsidian-markdown` = wiki article syntax.
- The vault at large = your notes; a `llm-wiki` KB = a distilled, agent-read slice of it.

## Anti-patterns
- Don't make one stub article per raw file — cluster sources into concepts.
- Don't edit `raw/` (append-only); don't let wiki articles balloon (distill, don't copy).
- Don't keep re-reading `raw/` once distilled — that defeats the token savings.
