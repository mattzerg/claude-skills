---
name: obsidian-markdown
description: Create and edit valid Obsidian Flavored Markdown — wikilinks, embeds, callouts, properties/frontmatter, tags, comments, highlights, math, mermaid, footnotes. USE PROACTIVELY whenever writing or editing .md files in Matt's Obsidian vault (the Zerg vault), or when the task mentions wikilinks, callouts, frontmatter, tags, or embeds. Ensures agent-written vault notes use correct Obsidian syntax (renames track, links resolve, callouts render) instead of plain GFM.
---

# Obsidian Flavored Markdown

Create and edit valid Obsidian Flavored Markdown. Obsidian extends CommonMark and GFM with wikilinks, embeds, callouts, properties, comments, and more. This skill covers only the Obsidian-specific extensions — standard Markdown (headings, bold, lists, tables, code blocks) is assumed.

Ported from `kepano/obsidian-skills` (Steph Ango / Obsidian, MIT), adopted 2026-06-07 — see `MattZerg/Skills/setup-ideas-evaluation-2026-06.md`. Matt's vault lives at `~/Obsidian/Zerg`; agents write to it constantly, so use this syntax for every vault note.

## Workflow: creating a note
1. **Frontmatter** with properties (title, tags, aliases) at the top.
2. **Content** in standard Markdown plus the Obsidian syntax below.
3. **Link** related notes with `[[wikilinks]]` (Obsidian tracks renames); use `[text](url)` for external URLs only.
4. **Embed** notes/images/PDFs with `![[embed]]`.
5. **Callouts** for highlighted info via `> [!type]`.
6. **Verify** it renders in reading view.

## Internal links (wikilinks)
```markdown
[[Note Name]]                 Link to note
[[Note Name|Display Text]]    Custom display text
[[Note Name#Heading]]         Link to heading
[[Note Name#^block-id]]       Link to block
[[#Heading in same note]]     Same-note heading link
```
Define a block ID by appending `^block-id` to a paragraph. For lists/quotes, put the block ID on its own line after the block.

## Embeds
Prefix any wikilink with `!` to embed inline:
```markdown
![[Note Name]]            Embed full note
![[Note Name#Heading]]    Embed section
![[image.png|300]]        Embed image with width
![[document.pdf#page=3]]  Embed PDF page
```

## Callouts
```markdown
> [!note]
> Basic callout.

> [!warning] Custom Title
> Callout with a custom title.

> [!faq]- Collapsed by default
> Foldable callout (- collapsed, + expanded).
```
Common types: `note`, `tip`, `warning`, `info`, `example`, `quote`, `bug`, `danger`, `success`, `failure`, `question`, `abstract`, `todo`.

## Properties (frontmatter)
```yaml
---
title: My Note
date: 2024-01-15
tags:
  - project
  - active
aliases:
  - Alternative Name
cssclasses:
  - custom-class
---
```
Default properties: `tags` (searchable labels), `aliases` (alt note names for link suggestions), `cssclasses` (styling).

## Tags
```markdown
#tag            Inline tag
#nested/tag     Nested tag hierarchy
```
Tags allow letters, numbers (not first char), underscores, hyphens, and forward slashes. Can also be set in frontmatter under `tags`.

## Other syntax
```markdown
%%hidden comment%%            Comment (hidden in reading view)
==highlighted text==          Highlight
$e^{i\pi}+1=0$  /  $$block$$  Math (LaTeX)
Text with a footnote[^1].     Footnote ([^1]: content) — or inline ^[note]
```
Mermaid diagrams in a ```mermaid fenced block; link nodes to notes with `class NodeName internal-link;`.

## Complete example
````markdown
---
title: Project Alpha
date: 2024-01-15
tags:
  - project
  - active
status: in-progress
---

# Project Alpha

This project aims to [[improve workflow]] using modern techniques.

> [!important] Key Deadline
> The first milestone is due on ==January 30th==.

## Tasks
- [x] Initial planning
- [ ] Development phase

The algorithm uses $O(n \log n)$ sorting. See [[Algorithm Notes#Sorting]].

![[Architecture Diagram.png|600]]
````

## References
- Obsidian Flavored Markdown: https://help.obsidian.md/obsidian-flavored-markdown
- Upstream skill (incl. PROPERTIES/EMBEDS/CALLOUTS deep-dives): https://github.com/kepano/obsidian-skills
- Siblings in this stack: `defuddle` (clean web→markdown before saving to the vault), `vault-coherence`, `document-styling-skill`.
