---
name: skill-editor
description: Edit, audit, refactor, validate, and maintain Codex skills. Use when improving an existing skill, creating a local skill from a rough idea, tightening trigger descriptions, splitting or merging overlapping skills, regenerating agents/openai.yaml, validating skill folders, comparing Claude and Codex skill versions, or deciding whether a workflow deserves a skill.
---

# Skill Editor

## Overview

Use this skill to turn rough skill ideas and existing skill folders into compact, discoverable, maintainable Codex skills. Treat it as a practical maintenance layer over the system `skill-creator` workflow, not a replacement for it.

## First Move

Classify the request before editing:

- **New skill from idea**: clarify concrete trigger examples, choose a hyphen-case name, and initialize with the `skill-creator` initializer unless the folder already exists.
- **Existing skill edit**: read the current `SKILL.md` and `agents/openai.yaml`, then make the smallest change that improves triggering, workflow quality, or validation.
- **Skill audit**: inspect one or more skills for trigger overlap, vague descriptions, unnecessary references, stale UI metadata, missing validation, or over-broad instructions.
- **Skill refactor**: propose splits, merges, renames, or reference-file moves before making structural changes.
- **Skill sync**: compare equivalent Claude/Codex skill folders and preserve the version that is more concise, more current, or better adapted to Codex.

## Workflow

1. **Scope the target**
   - Identify the skill path, desired behavior, and two or three user prompts that should trigger it.
   - Default new skills to `${CODEX_HOME:-$HOME/.codex}/skills` so they are auto-discovered.
   - Use lowercase hyphen-case names under 64 characters.

2. **Read before changing**
   - Open the target `SKILL.md`.
   - Read `agents/openai.yaml` when UI metadata exists or should be regenerated.
   - Load only directly relevant reference files. Avoid bulk-loading every bundled resource.

3. **Improve the trigger**
   - Put all "when to use" language in the YAML `description`; the body is only loaded after triggering.
   - Include both positive triggers and concrete task contexts.
   - Prefer specific verbs over broad labels: "audit", "refactor", "validate", "draft", "extract", "sync".
   - If two skills could trigger for the same request, either sharpen the descriptions or document the intended ordering.

4. **Tighten the body**
   - Keep `SKILL.md` procedural and concise.
   - Remove generic explanations Codex already knows.
   - Move detailed examples, schemas, rubrics, and long checklists into `references/`.
   - Keep references one level deep and name when to read each one.
   - Delete placeholder files and auxiliary docs that do not directly support the skill.

5. **Preserve user work**
   - Check existing files before overwriting.
   - Do not delete or rename a skill unless the user asked for that operation or approved the proposed change.
   - When touching a shared or synced skill, avoid unrelated formatting churn.

6. **Validate**
   - Run the skill validator:

```bash
python3 /Users/mattheweisner/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-folder>
```

   - For a full installed-skill audit, run:

```bash
python3 /Users/mattheweisner/.codex/skills/skill-editor/scripts/validate_all_skills.py
```

   - If the upstream validator fails because the active Python lacks PyYAML, read `references/maintenance-notes.md`.

   - Regenerate `agents/openai.yaml` if it is stale or mismatched:

```bash
python3 /Users/mattheweisner/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py <skill-folder> --interface display_name="..." --interface short_description="..." --interface default_prompt="Use $skill-name to ..."
```

7. **Report**
   - Summarize changed files.
   - State validation results.
   - Call out unresolved trigger overlap, missing examples, or follow-up testing needs.

## Audit Checklist

For deeper reviews, read `references/audit-checklist.md`.

Use the checklist when the user asks to review a skill, clean up the skill set, compare multiple skills, or decide whether an existing workflow should become a skill.

## Routing Map

For trigger precedence across common skill clusters, read `references/routing-map.md`.

Use the routing map when multiple skills could plausibly handle the same request, especially review/ship, brand/assets, Matt voice, launch, and connector tasks.

## Good Skill Tests

Before calling a skill finished, test it against realistic prompts:

- A direct invocation: "Use `$skill-name` to..."
- An implicit trigger: a user asks for the task without naming the skill.
- A near miss: a related request that should use a different skill or no skill.

If the skill would only work when the user names it explicitly, improve the YAML description.
