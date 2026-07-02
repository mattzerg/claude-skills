# Skill Audit Checklist

Use this checklist when reviewing a skill for discoverability, maintainability, and practical usefulness.

## Trigger Quality

- The YAML frontmatter contains only `name` and `description`.
- `name` matches the folder name and uses lowercase hyphen-case.
- `description` says what the skill does and when to use it.
- Trigger language includes concrete task contexts, not just a category label.
- The description is not so broad that it competes with unrelated skills.
- Overlap with sibling skills is handled by sharper descriptions or clear ordering.

## Body Quality

- The body starts with a compact overview.
- Workflow steps are imperative and actionable.
- Instructions add procedural knowledge Codex would not reliably infer.
- Generic explanations, motivational language, and user-facing docs are absent.
- The skill avoids repeating the system `skill-creator` guide unless a local rule differs.

## Resource Hygiene

- `references/` files are loaded only when needed and are linked from `SKILL.md`.
- Long examples, schemas, rubrics, and catalogs live in references rather than the main body.
- `scripts/` exist only for deterministic or repeatedly rewritten operations.
- `assets/` exist only for files used directly in outputs.
- Placeholder files from initialization have been deleted.
- No extra `README.md`, changelog, installation guide, or process notes exist unless the skill itself truly requires them.

## UI Metadata

- `agents/openai.yaml` matches the current skill purpose.
- `display_name` is human-readable.
- `short_description` is 25-64 characters and useful in a skill picker.
- `default_prompt` explicitly mentions `$skill-name`.
- Optional icons, colors, or dependencies are present only when intentionally provided.

## Validation

- Run:

```bash
python3 /Users/mattheweisner/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-folder>
```

- Fix all validation errors before considering the skill complete.
- For complex skills, test with direct, implicit, and near-miss prompts.
