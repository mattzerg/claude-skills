# Maintenance Notes

Use these notes when validator behavior or local environment changes make skill maintenance confusing.

## Python And PyYAML

The upstream `skill-creator/scripts/quick_validate.py` imports `yaml` from PyYAML. Homebrew Python upgrades can change which interpreter `python3` resolves to, and the new interpreter may not have PyYAML installed yet.

`scripts/validate_all_skills.py` deliberately catches that specific `ModuleNotFoundError` and falls back to a small built-in validator that checks the same high-value invariants:

- `SKILL.md` exists and has frontmatter.
- Frontmatter uses allowed keys.
- `name` is hyphen-case and under the length limit.
- `description` exists, has no angle brackets, and is under the length limit.
- `agents/openai.yaml` uses `interface:` when present.
- `default_prompt` mentions `$skill-name` when present.
- Auxiliary docs like `README.md` are flagged.

Prefer fixing the Python environment eventually, but do not block routine skill audits on PyYAML when the fallback passes.

To check the active interpreter:

```bash
python3 -c 'import sys; print(sys.executable)'
```

To test whether PyYAML is installed:

```bash
python3 -c 'import yaml; print(yaml.__file__)'
```
